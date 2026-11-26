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

*Legacy:* the Streamlit/FastAPI prototype that predated this plan was deleted after M0.9; it lives in git history up to `0a733a27` (RDKit engine: `cheminformatics/rdkit_engine.py`; ChEMBL/PubChem loaders: `data_loaders/`), the likely starting points for M2 and M3.

*Notes:* the deliberate-break proof is `packages/contracts/tests/break-schema.test.ts` (control passes; renaming `seq` or `page` fails both `tsc` and `mypy`). Python uses its own env (`.venv-a9`, set in the Makefile). Setup: `make setup`; regenerate contracts: `pnpm generate`; `make check-generated` fails on drift.

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
- [x] `LiteratureSource` protocol: `search(plan) -> Iterable[Record]`
- [x] Europe PMC
- [x] PubMed E-utilities
- [x] OpenAlex
- [x] Crossref
- [x] arXiv
- [x] bioRxiv and medRxiv
- [x] Per-source rate limit, retry with backoff, bounded semaphore

**Done when:** each adapter has contract tests against recorded cassettes, and killing one source mid-run produces a named reduced-coverage note on the run rather than a failure.

*Notes:* adapters live in `services/agents/src/a9_agents/sources/`. The protocol is `search(plan, *, limit) -> SearchOutcome` (async, with an optional `partial_reason`) rather than a bare iterable, so a source that fails part-way keeps its records *and* says why. `search_all` runs sources concurrently; a down, slow, partial or crashing source becomes a `{source, reason}` coverage note on the run, and the run still finishes. Records are staged in `source_records` for M0.7. `A9_SOURCES` picks the sources (default: the seven live ones; `fixture`, `fixture_down`, `fixture_partial` need no network). Cassettes in `tests/cassettes` are real recorded responses; re-record deliberately with `A9_RECORD_CASSETTES=1 .venv-a9/bin/python services/agents/tests/record_cassettes.py [source]`. **Things worth knowing:** bioRxiv/medRxiv have no keyword search, so they scan a recent window and filter client-side (the note says exactly what was scanned); Europe PMC took ~16 s live, close to the 20 s first-paper budget; sources report licences as free text (`cc_no`, `cc by`, a URL), so the licence evaluator must default to *not permitted* for anything it does not recognise; requests carry no contact details unless `A9_CONTACT_EMAIL` is set. The adapters were committed together rather than one per PR because they share the HTTP layer, the cassette tool and the contract-test file.

### M0.7 Identity, dedup and retraction
- [x] Identity resolution: DOI, then PMID, PMCID, arXiv id
- [x] Dedup ladder: DOI, then title-and-author hash, then SPECTER2 similarity for preprint and journal pairs
- [x] Crossref retraction and expression-of-concern check, stored as a flag

**Done when:** a known preprint and its published version collapse to one record, and a known retracted DOI appears flagged and present, never dropped.

*Notes:* `identity.py` clusters a run's staged records; the ladder is identifiers (DOI, PMID, PMCID, arXiv id) then publisher-asserted links (`related_dois`: bioRxiv's `published`, Crossref's `has-preprint`/`is-preprint-of`) then normalised title + first-author surname (years within 2, titles of 5+ words) then embedding similarity (preprint vs non-preprint only, same first author, years within 2). Every merge records its rung (`source_records.merge_reasons`). `papers.py` only adds information (never overwrites; a preprint row is promoted when its journal version arrives and the preprint's licence is *not* carried over); if identifiers match two existing papers it attaches to the oldest and reports `ambiguous` instead of merging rows. `retractions.py` reads Crossref's `updated-by` (Retraction Watch data); status only ever rises, 'not in Crossref' is *unchecked*, never clean, and flagged papers stay in the corpus. Proof on real data: a bioRxiv preprint and its published version collapse to one paper (`test_identity.py`), and the 1998 Wakefield paper comes out `retracted` with its 2010 notice (the 2004 correction is ignored). A live run of four sources collapsed 50 records to 42 papers and flagged it. **Not verified:** SPECTER2 itself. The similarity rung runs on a dependency-free character n-gram embedder (`A9_EMBEDDER=hashing`, threshold 0.80 chosen without labelled pairs); `Specter2Embedder` is a stub. The third and fourth rungs are the least trustworthy: tune against real labelled pairs before relying on them. Observed live: four sources took 58 s end to end, which will not meet the 20 s first-paper budget unless results stream per source as they land (they do emit as they land; the UI wiring is M0.9).

### M0.8 Triage
- [ ] Hand-label 100 records across two topics as the triage golden set — **needs a person**: `services/agents/evals/triage_golden.csv` is a template of 100 real records with a blank `label` column; see `evals/README.md`
- [ ] Schema-constrained verdict and reason against the plan's criteria, cheap model — built (`ScreeningVerdict` contract, `LlmTriager`) but never run against a real model; the default is a keyword heuristic, not a model
- [x] Counts streamed as `partial_result`; user override persisted to `screening_verdicts`

**Done when:** Cohen's kappa against the labelled set is 0.7 or better. **NOT MET: not measured.** No labels and no model exist yet; `make eval` says so rather than printing a number.

*Notes:* `triage` runs after `resolve` and screens each new paper in batches of five, emitting `progress` and a `verdicts` count (`include/exclude/unsure/unscreened`, where a user's verdict wins) after every batch. Papers a model could not screen are `unscreened` with a coverage note, never silently excluded; excluded papers stay in the corpus. A user override is a second `screening_verdicts` row beside the model's (`PUT`/`DELETE /conversations/:id/papers/:paper_id/verdict`, audited), so the model's call is visible and the override reversible. `HeuristicTriager` is deterministic keyword coverage of the plan's concepts in the title and abstract: useful as a floor and for tests, not a measure of what a model can do. Kappa is three-way (the model's `unsure` always counts as a disagreement) and checked against textbook values. `make eval` fails only on *regression* against `evals/triage_baseline.json` (allowed drop 0.02); until the set is labelled it prints NOT MEASURED. To finish this task: label the CSV, run `make eval-update` once to record a baseline, then try the LLM triager with a real key.

### M0.9 Wire the paper list
- [x] Replace the fixture: live records with source, licence, verdict and counts — behind the `paper_list` flag, the app's search box now opens `A9Workspace` (plan review, then the live `PaperList`); flag off is unchanged
- [x] Empty, partial and error states; a partial corpus renders as partial — unit-tested (`lib/papers/view.test.ts`) and driven in headless Chromium end to end (`frontend/e2e/`, manual, not in CI)

**Done when:** **M0 gate** — fixtures off for the paper list, every record links to a resolvable source, and a source outage is visible to the user as named reduced coverage.

*Notes:* `GET /conversations/:id/papers` (`paper_list.py`, contract `PaperList`) returns every paper in the corpus with sources, licence, retraction state (`checked` is separate from clean), model and user verdicts, merge reasons, a link that always exists (DOI, else the next identifier, else the source's own URL; a paper with none is a loud error), the latest run's coverage notes and counts. Excluded and retracted papers are present and labelled. `components/papers/PaperList.tsx` renders the loading, error (with retry; a failed refresh keeps the last good list), waiting-for-approval, still-searching, failed-run, empty, reduced-coverage and ready states, with excluded papers one filter away and per-paper override buttons. With `A9_FLAG_PAPER_LIST=1`, `/api/research` accepts a `conversation_id` and returns that corpus in the workspace's dossier shape (the briefing text is a factual coverage summary, not a synthesis); without one, or if the service is down, it serves the labelled fixture with the reason. Verified: the whole slice through real Next route handlers (fixture sources, one down and one failing part-way); the flag-off route is still byte-identical to the captured goldens; 49 of 49 DOIs from a live five-source search exist in the DOI handle system.

---

### M0 gate status: NOT PASSED (one part unmet)

The gate asks for fixtures off for the paper list, every record linking to a resolvable source, and a source outage visible as named reduced coverage, inside the existing UI.

| Gate part | Status |
|---|---|
| Live, screened, cited paper list from a topic, inside the existing UI | **Yes, behind `A9_FLAG_PAPER_LIST=1`.** The existing search box opens `A9Workspace`: plan review and approval, then a paper list that fills in. Verified in headless Chromium against the real API, worker, Redis and Postgres (fixture sources), with zero console errors, including editing and approving the plan, excluding and restoring a paper |
| Every record links to a resolvable source | Yes: 49 of 49 live DOIs resolve; every paper has a link by construction |
| A source outage is named reduced coverage | Yes: in events, on the run, in the list banner and in the header ("Finished with reduced coverage (…)") |
| With the flag off the app is unchanged | Yes: goldens byte-identical, and in the browser the existing workspace runs while `/api/topics` and `/dev/plan` return 404 |
| Triage kappa >= 0.7 (M0.8) | **Not measured.** Needs expert labels and a real model. This is the unmet part |
| Anything run against a real model | **No.** No model access: the planner and triager are placeholders and say so in the UI |
| Real users | **No auth provider.** The live path runs as one fixed dev user and needs `A9_ENABLE_DEV_ENDPOINTS=1` |

Browser checks used fixture sources, not the live internet, so they prove the wiring and the states, not search quality. Live-internet behaviour was checked separately at the API level (50 records to 42 papers; Wakefield flagged).

---

## M1 — Conversational RAG

**Goal:** per-conversation index, hybrid retrieval, verified answers.

### M1.1 Fetch and parse workers
- [ ] Open-access resolution through Unpaywall and Europe PMC; licence recorded on every record
- [ ] Firecrawl for HTML full text where licensed
- [ ] GROBID to TEI as primary, Docling fallback, PyMuPDF for figures
- [x] Object storage layout: `papers/{id}/original.pdf`, `fulltext.jats.xml`, `document.<parser>.json` (local filesystem store, content-addressed; the S3/R2 implementation is not written; figures are not extracted yet)

**Done when:** a 100-PDF corpus parses above 90 percent, and a test proves a record with a null licence stores metadata only. **Met for the paths built:** 100/100 real arXiv PDFs and 50/50 real PMC JATS papers parsed (`python -m a9_agents.evals.ingest_corpus`, needs network), and `test_ingest.py` proves null, unrecognised and restrictive licences store the abstract only and write nothing to object storage. Caveats: the PDF path is PyMuPDF (heuristic), not GROBID, so 'parses' means usable text and structure, not TEI quality; only 53 of 100 PDFs yielded an abstract chunk and 87 of 100 had 3+ body sections.

*Open in M1.1:* GROBID (needs Java/Docker, unavailable here), Docling, Unpaywall (needs `A9_CONTACT_EMAIL`; not built), Firecrawl HTML (not built). Routes that exist: PMC JATS (NCBI efetch with Europe PMC fallback; ~1.5 s vs 17-51 s) and arXiv PDF (the per-paper licence is read from the abstract page *before* the PDF is downloaded; arXiv's default licence is refused). `fulltext` is a graph stage after the retraction check (`A9_FULLTEXT=on|off`) covering papers not excluded; papers are reported as parsed / abstract_only / not_permitted / failed, never hidden. The licence default allows only CC0, CC BY, CC BY-SA and public domain (NC and ND are refused because chunking and extraction are derivatives); override with `A9_ALLOWED_LICENCES`.

### M1.2 Chunking and the provenance envelope
- [x] Section-aware, 400 to 800 tokens, 15 percent overlap, never crossing a section boundary
- [x] Tables stored whole and linearised; figure captions as their own chunks
- [x] Context header (title, section path, one-line paper summary) prepended before embedding

**Done when:** every chunk round-trips to its exact source span, verified across the corpus, not sampled. **Met:** all 4,986 chunks from the 150 real documents above round-trip exactly (0 failures); `resolve_chunk` re-verifies a stored chunk against its source on every citation lookup and fails loudly on mismatch.

*Notes:* tokens are counted with a word-and-punctuation estimator, not the embedding model's tokenizer. Chunks never cross a section, so papers with many short subsections give small chunks (median roughly 200-300 tokens). Non-paginated sources (JATS) use page 1. Chunk rows carry `extraction_model='chunker-v1'`, `prompt_version='none'` because chunking calls no model.

### M1.3 Extraction — Parallel with M1.4
- [ ] Schema-constrained claim extraction per section, offsets carried through — only a *rule-based* measured-value extractor (IC50/Ki/Kd/EC50/GI50 with units) exists; it records exact absolute offsets into `claims` with the full provenance envelope as NOT NULL columns; the LLM extractor (targets, pathways, cohorts, endpoints, limitations) is not built
- [ ] Entity normalisation: InChIKey, UniProt, HGNC, MONDO; unnormalised stored raw and flagged — the four normalisers work against real recorded responses (RDKit offline for SMILES; PubChem, UniProt, HGNC, OLS/MONDO) and fail closed with a flag, but they are not yet wired to the claims' entities
- [x] Cache keyed on `(chunk_hash, prompt_version)` — keyed on `(chunk text hash, extractor version)`, table `extractions`; offsets are cached relative to the chunk so identical text elsewhere reuses it

**Done when:** a re-run of the same corpus is a cache hit end to end and costs near zero. **Met for the extractor that exists:** `test_a_rerun_on_the_same_corpus_is_a_cache_hit_end_to_end` shows the second run makes zero extractor calls (every chunk a cache hit). It says nothing about LLM extraction cost, which does not exist yet.

*Not wired into the run graph.* `extract_corpus` is a library function; no graph stage calls it yet.

### M1.4 Index and membership — Parallel with M1.3
- [x] Qdrant collection, payload index on `conversation_ids`
- [x] `ConversationIndex(conversation_id)` as the only query path
- [x] Second collection for SPECTER2 paper-level vectors

**Done when:** a lint rule or test fails the build if the raw Qdrant client is imported anywhere outside the repository class. **Met:** ruff `TID251` bans `qdrant_client` everywhere except `index/conversation_index.py`, and `test_nothing_but_the_conversation_index_imports_the_vector_client` walks the AST of every Python file in the repo; `ConversationIndex` has no method that accepts a filter.

*Notes:* embedded Qdrant (no server: Docker is unavailable), where payload indexes are accepted but have no effect and only one process may open the store, so the API process owns it and indexes a conversation lazily from its memberships (`A9_QDRANT_URL` selects a server). The paper-level collection also carries `conversation_ids` (the PRD says only `paper_id` and `year`) so the paper pass is isolated by the same mandatory filter; its vectors are the chunk embedder, a stand-in for SPECTER2. Chunks are embedded once and joined by membership; removing a conversation deletes vectors nobody else uses. Models: `bge-small-en-v1.5` (384-d) stands in for BGE-M3.

### M1.5 Retrieval
- [ ] Build the question golden set: 100 questions with known supporting spans — a *synthetic* generator exists (`a9_agents.evals.retrieval`, templated from real sentences, so supporting spans are exact), but it is not expert-written and it shares vocabulary with its answers
- [ ] Query rewrite against history; decompose multi-part questions — rule-based only (anaphora anchoring, explicit separators); the LLM versions are not built
- [x] Dense, BM25 and paper-level arms; reciprocal rank fusion to ~50
- [x] Cross-encoder rerank to 8–12; parent or section expansion before the model

**Done when:** recall@20 is 0.85 or better on the golden set, retrieval p95 under 800 ms. **NOT MET.** Measured on 8 real PMC papers (190 chunks) and 40 synthetic questions: recall@10 = recall@20 = 1.000, which is a ceiling that cannot discriminate and is optimistic by construction; retrieval p50 1.28 s, p95 1.62 s on CPU, so the latency budget is missed (cross-encoder reranking of 50 candidates dominates; a GPU or hosted reranker, a smaller candidate set, or a smaller reranker is needed). A real expert-written question set is still required.

*Notes:* arms are Qdrant dense, Postgres full-text (`ts_rank_cd`, OR query built only from alphanumerics, scoped by memberships), and a paper-level pass; fused by RRF (k=60); reranked by `ms-marco-MiniLM-L-6` (stand-in for bge-reranker-v2-m3); each survivor gets its neighbouring chunks in the same section. Retrieval returns which arms surfaced each chunk.

### M1.6 Synthesis and the verifier
- [ ] Cite-as-you-write generation with inline chunk ids — the pipeline is cite-as-you-write, but the generator is an *extractive* stand-in (it quotes the best sentences); no language model writes prose yet
- [x] Verifier agent seeing only the output and the cited chunks, never the generator's reasoning — the interface guarantees it; the implementation is a lexical stand-in, not an LLM
- [x] Unsupported sentences dropped or marked, never shipped quietly

**Done when:** **M1 gate** — grounding above 95 percent on the golden question set and citation resolution at 100 percent. **NOT MET.** Citation resolution is 100% in the tests (every cited chunk resolves to its exact span; a tampered source is flagged unresolved), but grounding is not meaningfully measurable: an extractive generator is grounded by construction. What is measured: the lexical verifier accepts every verbatim quote and rejects every constructed number-change fabrication, off-topic sentence and wrong citation in the test set, which is a floor (subtle misreadings need an entailment model), not a grounding rate.

*Notes:* `POST /conversations/:id/messages` streams `retrieval`, `sentence` (with cites and the check's reason), `removed` (with why), `no_evidence` and `done` events and stores both messages; `GET /chunks/:id` resolves a citation (404 outside the caller's corpus, loud failure if the span no longer matches). An empty corpus, or no supported sentence, says so instead of answering. Quotation is capped at 60 words per sentence. The frontend chat surface is not built.

### M1.7 Memory and corpus growth
- [ ] Thread state in the Postgres checkpointer; rolling summary regenerated, not appended; user preferences in their own table
- [ ] A new search appends to the membership set with an ingestion timestamp; the UI shows what arrived since the last turn

**Done when:** a 40-turn conversation stays inside the prompt budget and widening the corpus mid-conversation does not reset the thread.

*Status: partly built.* `GET /conversations/:id/corpus?since=` reports corpus size and what arrived since a timestamp (from `chunk_memberships.ingested_at`), so widening the corpus mid-conversation is visible; the UI for it, the rolling summary, the preferences table and the 40-turn budget test are not built. Chat history passed to retrieval is the last four user questions, which is bounded but is not the planned regenerated summary.

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
- [x] `models` table; every predictor registered with version, training provenance, calibration date, domain notes
- [x] Foreign key from `molecule_scores.model_id` enforced before M3 starts

**Done when:** **M2 gate** — a chemist reviews five target packages and agrees the evidence holds up, recorded as a structured review rather than a conversation.

*Notes:* migration 0009. `models` rows are immutable (`register_model` returns the existing id) and cannot omit training data or domain notes. `molecule_scores` needs a registered `model_id`, a non-null `in_domain` and a `nn_similarity`; CHECK constraints forbid any value or interval when `in_domain` is false and require `lower <= value <= upper` when true. The M2 gate (a chemist reviewing five target packages) needs a person, and M2.1-M2.3 are not started.

---

## M3 — Design and profiling

**Goal:** generation, gates, docking, predictions with intervals.

### M3.1 Generator interface
- [ ] `Generator` protocol; REINVENT 4 as the first adapter; de novo, scaffold decoration, linker, R-group modes
- [ ] GPU job on Modal, bursted not warm

### M3.2 Cheap gates — Parallel with M3.3
- [x] Validity, uniqueness, novelty against the corpus and ChEMBL — novelty takes a known-set (corpus) and `ChemblNovelty` (InChIKey lookup, tested on real ChEMBL recordings; ChEMBL being unreachable gives None, never 'novel')
- [x] PAINS and Brenk alerts, project alert set, property windows, SA score — real RDKit catalogs (585 entries) and SA scorer; PAINS, project alerts, windows and SA are hard gates, Brenk is a soft warning
- [x] Results written to `molecule_gates` with pass and fail detail

### M3.3 Structure-based scoring
- [ ] Docking through DockStream on survivors only; treated as a ranking signal, never an affinity

### M3.4 Property profiling
- [ ] ADMET-AI primary, Admetica as an independent second opinion
- [ ] Disagreement beyond threshold renders the candidate as contested, never averaged

### M3.5 Applicability domain and intervals
- [x] Nearest-neighbour similarity to each model's training set (Morgan/Tanimoto)
- [x] Conformal intervals; out of domain renders no prediction at all

*Measured (real data):* split-conformal intervals and the domain, on a ridge model of ESOL solubility (public, 1,128 measurements; 60/20/20 train/calibration/test, seed 7), 227 held-out molecules: 92% inside the domain (the rest get no prediction); empirical coverage 91.4% at 90% nominal and 95.7% at 95% (both within 5 points), but 85.6% at 80% nominal (5.6 points over, a small-sample effect). Held-out MAE 0.70 log units. This proves the calibration machinery on one endpoint with a deliberately simple model. It is not ADMET-AI or Admetica (neither is installed), and the M3 gate's other parts (blind review of candidates, coverage on the ADMET endpoints the product will actually predict) are not met.

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
