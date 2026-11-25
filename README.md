# A9

A9 turns a typed biomedical research topic into a cited, screened evidence base, and (later) a conversational RAG thread and candidate molecules with calibrated predictions. Research use only.

**Where things stand:** the literature pipeline (M0) is built and tested end to end: plan, approval, seven sources searched concurrently, deduplication, retraction flags, screening, and a paper list. Nothing has run against a real language model yet (no model access), and the screening gate is unmeasured. The honest status of every task, including what is *not* verified, is in [`docs/CLAUDE.md`](docs/CLAUDE.md). The reasoning behind the design is in the PRD linked from there.

## Layout

| Path | What |
|---|---|
| `frontend/` | Next.js app (existing UI plus the new plan editor and paper list) |
| `services/agents/` | FastAPI service, LangGraph ingest graph, source adapters, identity/dedup, triage, migrations, evals |
| `services/workers/` | Arq workers that run jobs |
| `packages/contracts/` | JSON Schemas; generates the TypeScript types and Pydantic models |
| `docs/CLAUDE.md` | The build plan, rules, stack and status |

## Run it

Needs `node` (24), `pnpm`, `uv`, and Homebrew `postgresql@16` and `redis` (no Docker).

```sh
make setup        # installs JS and Python dependencies
make dev-up       # project-local Postgres (5544) and Redis (6390), then migrates
cp .env.example .env   # then edit; at minimum set A9_INTERNAL_KEY
make api          # agents service on :8100
make worker       # background worker
pnpm --filter frontend dev
```

The new pipeline is behind a flag: set `A9_FLAG_PAPER_LIST=1` (and `A9_ENABLE_DEV_ENDPOINTS=1` while there is no auth provider) for the frontend. With every flag off the app behaves as it did before.

## Checks

```sh
pnpm typecheck && pnpm test
make lint && make test
make eval          # golden-set evaluations; says NOT MEASURED until the sets are labelled
make check-generated
```

## History

An earlier Streamlit and FastAPI prototype (`app.py`, `agents/`, `core/`, `data_loaders/`, `cheminformatics/`, `ui/`) lived at the repo root until it was removed. It is in git history up to commit `0a733a27`; `git checkout 0a733a27 -- cheminformatics/rdkit_engine.py` restores a file. The RDKit engine and the ChEMBL and PubChem loaders there are the likely starting points for the design modules (M2 and M3).
