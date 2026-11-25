# A9 build plan

Work this file top to bottom. One task per PR. Do not start a phase whose predecessor's gate has not passed. Tick a task only when its **Done when** line is demonstrably true.

The reasoning behind the plan is in the PRD: https://claude.ai/artifact/MSPLb195x1dpwkZQQruyR9

Legend: **Done when** is the acceptance check. **Parallel** marks tasks with no dependency on each other, safe to fan out.

---

## Rules that constrain every task

Distilled from the PRD so they live next to the plan. If this section and the PRD disagree, the PRD wins; fix this file.

**Invariants**

1. Every stored unit carries the provenance envelope: paper id, section path, page, char start/end, parser version, extraction model and prompt version, run id. Nothing enters the index without it. A citation that cannot resolve is a bug that fails loudly.
2. Full text is stored only for open-access records whose licence permits it. The licence string is stored on the record. A missing or null licence means metadata only; the worker refuses to write full text rather than guessing.
3. Isolation is a mandatory filter, not a convention: one repository class owns every vector query and takes `conversation_id` as a constructor argument. Postgres row-level security on `user_id` is the backstop.
4. Degrade, do not fail. A source timeout is reported as named reduced coverage. A parse failure marks that paper abstract-only and continues. Only losing the database is a hard failure.
5. Retracted papers are flagged and kept, never dropped. A screening hit blocks the candidate and raises a review item, never a silent drop.
6. Job keys are deterministic from their inputs, so a retry is a no-op.
7. No bare numbers. Predictions carry the model, version, interval and in-domain flag; out of domain renders no prediction. No pass/fail language. The words *safe*, *effective* and *non-toxic* never appear in generated output.
8. Output is structures and predictions only: no synthesis routes, dosing, formulation or wet-lab procedure. Research use only, stated in the product and every export.
9. No export without a sign-off row against that dossier version.
10. Fixtures stay alive behind a per-surface flag until that phase's gate passes. Fixture shapes are the API contract; change the contract deliberately rather than leaving a field empty.
11. Schema-first: types come from `packages/contracts/schemas`, generated for TS and Pydantic. Never hand-edit generated files.
12. One event schema, one front-end reducer, for every long run.

**Stack table** (add any new external source or model here first, in the PR that introduces it)

| Concern | Pick |
|---|---|
| Web app | Next.js App Router, React, TypeScript, Tailwind |
| Streaming | SSE from the Python service, proxied by a Next route handler |
| Agent service | Python, FastAPI, LangGraph 1.x, Postgres checkpointer |
| Background work | Arq on Redis; Modal or RunPod for GPU bursts |
| LLM access | Claude through a LiteLLM gateway; Pydantic schema for every extraction |
| Relational | Postgres 16, Alembic migrations, row-level security |
| Vector | Qdrant (one collection, payload index on `conversation_ids`); SPECTER2 paper-level collection |
| Keyword | Postgres full-text first |
| Embeddings / rerank | BGE-M3 or Voyage; SPECTER2; bge-reranker-v2-m3 or Cohere Rerank |
| Objects | S3 or Cloudflare R2 |
| Cache / pub-sub | Redis |
| Literature sources | Europe PMC, PubMed E-utilities, OpenAlex, Crossref, arXiv, bioRxiv/medRxiv, Unpaywall |
| Web fetch | Firecrawl; httpx with tenacity for APIs |
| Parsing | GROBID (TEI) primary, Docling fallback, PyMuPDF for figures |
| Cheminformatics | RDKit, Open Babel |
| Reference data | ChEMBL, PubChem, BindingDB, UniProt, PDB, AlphaFold DB |
| Generation | REINVENT 4 behind a `Generator` interface |
| Docking | AutoDock Vina / smina via DockStream |
| Properties | ADMET-AI primary, Admetica second opinion; conformal intervals |
| Synthesizability | SA score, RAscore; AiZynthFinder on shortlist only (score only, route never surfaced) |
| Observability | LangSmith, OpenTelemetry, Sentry |
| Tooling | pnpm workspace, uv (Python), make, GitHub Actions |

**Opening budgets** (set as alerts in code from day one): first paper visible 20 s; ingest 150 papers 8 min p50; first chat token 2 s; retrieval p95 800 ms; design run 15 min; 3 concurrent runs per user.

---

## M0 — Pipeline spine

**Goal:** one topic produces a real, screened, cited paper list inside the existing UI.

### M0.1 Monorepo and contracts
- [x] pnpm workspace; `services/agents` and `services/workers` as a Python project; `packages/contracts`
- [x] Schema-first: JSON Schema in `packages/contracts/schemas`, one generator emitting TS types and Pydantic models
- [ ] CI: `pnpm typecheck`, `pnpm test`, `make lint`, `make test` on every PR — workflow is in `.github/workflows/ci.yml` and all four pass locally; tick once it has run green on a GitHub PR

**Done when:** an empty PR passes all four checks, and a deliberate schema change breaks compilation on both the TS and Python side.

*Notes:* the deliberate-break proof is `packages/contracts/tests/break-schema.test.ts` (control passes; renaming `seq` or `page` fails both `tsc` and `mypy`). Python uses its own env (`.venv-a9`, set in the Makefile) so `uv sync` never touches the legacy `.venv`. Setup: `make setup`; regenerate contracts: `pnpm generate`; `make check-generated` fails on drift.

### M0.2 Database and invariants
- [x] Alembic set up; migrate the core tables: users, projects, conversations, messages, runs, jobs, search_plans, papers, paper_assets, chunks, chunk_memberships, screening_verdicts, audit_log
- [x] Row-level security on `user_id`, enabled and tested
- [x] NOT NULL constraints encoding the invariants: provenance columns on chunks, licence checked before full-text write

**Done when:** `make migrate` is clean up and down, and a test proving a chunk insert without a complete provenance envelope raises, rather than defaults.

*Notes:* `make db-up` starts a project-local Postgres 16 on port 5544 (no Docker, no system service); `make migrate`, `make migrate-down`, `make migrate-check` (up, down, up). Migrations are plain SQL in `services/agents/migrations/sql/`. Two roles: `a9_app` (request path, RLS applies, scoped by `app.user_id`) and `a9_worker` (trusted ingestion). Child tables use composite `(id, user_id)` foreign keys so a row cannot point at another user's parent. The licence gate is a trigger on `chunks` and `paper_assets` (abstract chunks exempt). Tests are `services/agents/tests/test_db_invariants.py`; they skip locally when Postgres is down and fail in CI (`A9_REQUIRE_DB=1`). `chunks.run_id` is deliberately not a foreign key, so deleting a user's runs never touches shared chunks.

### M0.3 Runs, jobs and the event stream
- [x] runs and jobs with deterministic idempotent job keys
- [x] Arq worker skeleton on Redis
- [x] Event schema: `stage_started`, `progress`, `partial_result`, `needs_input`, `stage_finished`, `run_failed`, `run_finished`; monotonic `seq` per run
- [x] SSE endpoint on the agents service, Next route handler proxy, `Last-Event-ID` replay
- [x] One reducer on the front end for all stages

**Done when:** a dummy ten-step job streams to the browser, survives a worker kill mid-run, and replays the backlog after a reconnect instead of showing a spinner.

*Notes:* `make dev-up` starts Postgres and Redis locally (ports 5544 and 6390) and migrates; `make api` and `make worker` run the services; `/dev/runs` in the frontend starts and watches a dummy run (needs `A9_ENABLE_DEV_ENDPOINTS=1` and `A9_INTERNAL_KEY`). Design: Postgres is the source of truth for events (`run_events`, `seq` from `runs.last_seq`, written in the same transaction as the state change); Redis only wakes live listeners and the stream falls back to polling. Jobs are leased (`heartbeat_at`, fenced on `attempts`), checkpointed per step in the same transaction as the step's event, and a reaper cron re-enqueues stale jobs. Proof: `services/agents/tests/test_run_stream_e2e.py` (real API, two Arq workers, SIGKILL mid-run, replay by `Last-Event-ID`), `frontend/lib/runs/reducer.test.ts`, and a manual curl run through the Next proxy. *Not yet verified:* the `/dev/runs` page rendered in a real browser (the proxy, reducer and hook are tested; the page itself was only confirmed to return 200).

### M0.4 Feature flags and fixture fallback
- [x] Server-evaluated flag per surface
- [x] Fixture modules refactored behind the same interface the live implementation will use

**Done when:** with every flag off the app is byte-identical to today's behaviour.

*Notes:* flags live in `frontend/lib/flags.ts` (`A9_FLAG_<SURFACE>=1`, default off, one per PRD surface), read server-side only and exposed to client code through `GET /api/flags` and `useFlags()`. The only data fixture the frontend has today is the research dossier (`/api/research`); it now sits in `lib/fixtures/research.ts` behind the `ResearchSource` interface in `lib/surfaces/research.ts`, next to the legacy FastAPI source and the (stub) live A9 source. The other constants in the components (preset queries, recent chats) are UI copy, not data surfaces; molecule and human-effect fixtures get the same treatment when those surfaces are wired (M3.7). Proof of "byte-identical with every flag off": `lib/fixtures/research-route.golden.test.ts` replays 10 requests (demo x4, backend timeout / 500 / ok, empty query, no body, client abort) against goldens captured from the route *before* the refactor; a one-word mutation fails 4 of them. Also confirmed against the running legacy backend on :8000. Turning `paper_list` on today serves the labelled fixture with reason "The live A9 paper list is not available yet" until M0.9.

### M0.5 Planner node and the approval interrupt
- [ ] Planner: topic to concepts, synonyms, MeSH terms, include and exclude criteria, date bounds — structure, stub and LLM path built; tick once a real model has produced plans worth keeping (no model access yet)
- [x] LangGraph interrupt for approval; plan is editable in the UI before the search fires
- [x] Plan versioned in `search_plans` with `approved_by` and `approved_at`

**Done when:** a user edits a plan, closes the tab, reopens from another device, approves, and the run resumes on the same thread.

*Notes:* `SearchPlan` is a schema in `packages/contracts`. `Planner` has two implementations behind `A9_MODEL_PROVIDER` (default `stub`): `StubPlanner` is deterministic, invents no synonyms or MeSH terms, and stamps `generated_by: "stub"` (the UI shows a "placeholder plan" badge); `LlmPlanner` + `AnthropicModelClient` force one tool call with the plan schema. **The Anthropic path has only been tested against a fake client, never the real API.** The graph (`plan_graph.py`: plan, request approval, `interrupt()`, finish) checkpoints to Postgres under the run's `thread_id`; each node is idempotent per run. Edits create new `search_plans` versions (stale or post-approval edits get 409); approval sets `approved_by`/`approved_at`, writes the audit log, and enqueues a `resume_plan` job keyed on the plan so a double-click is a no-op. Proof: `test_plan_flow_e2e.py` kills the worker while parked, edits and approves while no worker runs, then starts a new worker that finishes the plan stage on the same thread. After approval the run stays `running` until the search stage exists (M0.6). UI: `components/plan/PlanEditor.tsx` and `/dev/plan` (ids are in the URL, so another device sees the same state); it is not yet mounted in the main workspace.

### M0.6 Source adapters — Parallel (one adapter per PR)
- [ ] `LiteratureSource` protocol: `search(plan) -> Iterable[Record]`
- [ ] Europe PMC
- [ ] PubMed E-utilities
- [ ] OpenAlex
- [ ] Crossref
- [ ] arXiv
- [ ] bioRxiv and medRxiv
- [ ] Per-source rate limit, retry with backoff, bounded semaphore

**Done when:** each adapter has contract tests against recorded cassettes, and killing one source mid-run produces a named reduced-coverage note on the run rather than a failure.

### M0.7 Identity, dedup and retraction
- [ ] Identity resolution: DOI, then PMID, PMCID, arXiv id
- [ ] Dedup ladder: DOI, then title-and-author hash, then SPECTER2 similarity for preprint and journal pairs
- [ ] Crossref retraction and expression-of-concern check, stored as a flag

**Done when:** a known preprint and its published version collapse to one record, and a known retracted DOI appears flagged and present, never dropped.

### M0.8 Triage
- [ ] Hand-label 100 records across two topics as the triage golden set
- [ ] Schema-constrained verdict and reason against the plan's criteria, cheap model
- [ ] Counts streamed as `partial_result`; user override persisted to `screening_verdicts`

**Done when:** Cohen's kappa against the labelled set is 0.7 or better.

### M0.9 Wire the paper list
- [ ] Replace the fixture: live records with source, licence, verdict and counts
- [ ] Empty, partial and error states; a partial corpus renders as partial

**Done when:** **M0 gate** — fixtures off for the paper list, every record links to a resolvable source, and a source outage is visible to the user as named reduced coverage.

---

## M1 — Conversational RAG

**Goal:** per-conversation index, hybrid retrieval, verified answers.

### M1.1 Fetch and parse workers
- [ ] Open-access resolution through Unpaywall and Europe PMC; licence recorded on every record
- [ ] Firecrawl for HTML full text where licensed
- [ ] GROBID to TEI as primary, Docling fallback, PyMuPDF for figures
- [ ] Object storage layout: `papers/{id}/original.pdf`, `grobid.tei.xml`, `figures/{n}.png`

**Done when:** a 100-PDF corpus parses above 90 percent, and a test proves a record with a null licence stores metadata only.

### M1.2 Chunking and the provenance envelope
- [ ] Section-aware, 400 to 800 tokens, 15 percent overlap, never crossing a section boundary
- [ ] Tables stored whole and linearised; figure captions as their own chunks
- [ ] Context header (title, section path, one-line paper summary) prepended before embedding

**Done when:** every chunk round-trips to its exact source span, verified across the corpus, not sampled.

### M1.3 Extraction — Parallel with M1.4
- [ ] Schema-constrained claim extraction per section, offsets carried through
- [ ] Entity normalisation: InChIKey, UniProt, HGNC, MONDO; unnormalised stored raw and flagged
- [ ] Cache keyed on `(chunk_hash, prompt_version)`

**Done when:** a re-run of the same corpus is a cache hit end to end and costs near zero.

### M1.4 Index and membership — Parallel with M1.3
- [ ] Qdrant collection, payload index on `conversation_ids`
- [ ] `ConversationIndex(conversation_id)` as the only query path
- [ ] Second collection for SPECTER2 paper-level vectors

**Done when:** a lint rule or test fails the build if the raw Qdrant client is imported anywhere outside the repository class.

### M1.5 Retrieval
- [ ] Build the question golden set: 100 questions with known supporting spans
- [ ] Query rewrite against history; decompose multi-part questions
- [ ] Dense, BM25 and paper-level arms; reciprocal rank fusion to ~50
- [ ] Cross-encoder rerank to 8–12; parent or section expansion before the model

**Done when:** recall@20 is 0.85 or better on the golden set, retrieval p95 under 800 ms.

### M1.6 Synthesis and the verifier
- [ ] Cite-as-you-write generation with inline chunk ids
- [ ] Verifier agent seeing only the output and the cited chunks, never the generator's reasoning
- [ ] Unsupported sentences dropped or marked, never shipped quietly

**Done when:** **M1 gate** — grounding above 95 percent on the golden question set and citation resolution at 100 percent.

### M1.7 Memory and corpus growth
- [ ] Thread state in the Postgres checkpointer; rolling summary regenerated, not appended; user preferences in their own table
- [ ] A new search appends to the membership set with an ingestion timestamp; the UI shows what arrived since the last turn

**Done when:** a 40-turn conversation stays inside the prompt budget and widening the corpus mid-conversation does not reset the thread.

---

## M2 — Target and objective

**Goal:** target packages assembled from the corpus, versioned design objectives.

### M2.1 Target candidates from claims
- [ ] Roll up extracted claims into candidate targets with their supporting evidence ids

### M2.2 Target package
- [ ] Resolve to UniProt; pull structure from PDB or AlphaFold DB; assemble known actives from ChEMBL and BindingDB
- [ ] Carry the corpus evidence that justified the target

### M2.3 Objective builder
- [ ] Property windows, scaffold to retain or avoid, hard versus soft constraints
- [ ] Versioned and stored; LangGraph interrupt for user confirmation

### M2.4 Model registry
- [ ] `models` table; every predictor registered with version, training provenance, calibration date, domain notes
- [ ] Foreign key from `molecule_scores.model_id` enforced before M3 starts

**Done when:** **M2 gate** — a chemist reviews five target packages and agrees the evidence holds up, recorded as a structured review rather than a conversation.

---

## M3 — Design and profiling

**Goal:** generation, gates, docking, predictions with intervals.

### M3.1 Generator interface
- [ ] `Generator` protocol; REINVENT 4 as the first adapter; de novo, scaffold decoration, linker, R-group modes
- [ ] GPU job on Modal, bursted not warm

### M3.2 Cheap gates — Parallel with M3.3
- [ ] Validity, uniqueness, novelty against the corpus and ChEMBL
- [ ] PAINS and Brenk alerts, project alert set, property windows, SA score
- [ ] Results written to `molecule_gates` with pass and fail detail

### M3.3 Structure-based scoring
- [ ] Docking through DockStream on survivors only; treated as a ranking signal, never an affinity

### M3.4 Property profiling
- [ ] ADMET-AI primary, Admetica as an independent second opinion
- [ ] Disagreement beyond threshold renders the candidate as contested, never averaged

### M3.5 Applicability domain and intervals
- [ ] Nearest-neighbour similarity to each model's training set
- [ ] Conformal intervals; out of domain renders no prediction at all

### M3.6 Screening gate
- [ ] Automated screen on every generated structure before storage or display
- [ ] A hit blocks the candidate and raises a review item; repeated near-miss patterns alert

### M3.7 Wire the molecule and human-effect surfaces
- [ ] Cards with scores, gate flags, lineage
- [ ] Panel grouped by absorption, distribution, metabolism, excretion, safety liabilities
- [ ] No bare numbers, no pass or fail language, banned words linted in generated copy

**Done when:** **M3 gate** — on a blind review, 1 in 10 candidates is worth discussing; screens clean; conformal interval coverage within 5 points of nominal on the held-out molecule set.

---

## M4 — Dossier and scale

**Goal:** exports, sign-off, cost control, observability.

### M4.1 Dossier assembly
- [ ] Versioned document carrying the full chain: plan, corpus, target evidence, objective, candidate lineage

### M4.2 Sign-off and export gating
- [ ] Export blocked without a `signoffs` row against that dossier version

### M4.3 Cost control — Parallel with M4.4
- [ ] Three cache tiers: documents by DOI, embeddings by content hash, extractions by chunk hash and prompt version
- [ ] Hard per-project cap enforced in the LiteLLM gateway

### M4.4 Concurrency
- [ ] Three concurrent runs per user, queued beyond; per-user fairness in the queue

### M4.5 Observability
- [ ] One trace id from browser through route handler, agent service, workers and model calls
- [ ] Dashboards for every metric in the PRD's metrics table

### M4.6 Audit completeness
- [ ] Append-only log of runs, plan approvals, screening decisions, sign-offs and exports

**Done when:** **M4 gate** — cost per conversation under cap, the p95 budgets met, and any candidate's full lineage reconstructable from the audit log alone.

---

## Standing checks

Run on every PR, not at the end of a phase:

- [ ] `make eval` gates on regression against the golden sets, not absolute score
- [ ] Bumping `prompt_version` is called out in the PR description, with the cache cost
- [ ] Any new external source or model is added to the stack table in this file first
- [ ] Provenance traceable: pick any value in the UI, trace it to a source span
