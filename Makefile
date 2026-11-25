# A9 workspace tasks.
# A9's Python environment lives in .venv-a9 (not the default .venv).
export UV_PROJECT_ENVIRONMENT ?= .venv-a9

# Local Postgres for development and tests: a project-local cluster (no system service, no Docker).
PG_BIN  ?= /opt/homebrew/opt/postgresql@16/bin
PG_PORT ?= 5544
PGDATA  ?= $(CURDIR)/.pgdata
REDIS_BIN  ?= /opt/homebrew/bin/redis-server
REDIS_CLI  ?= /opt/homebrew/bin/redis-cli
REDIS_PORT ?= 6390
export A9_REDIS_URL     ?= redis://localhost:$(REDIS_PORT)/0
export A9_DATABASE_URL  ?= postgresql+psycopg://localhost:$(PG_PORT)/a9
export A9_PG_ADMIN_URL  ?= postgresql://localhost:$(PG_PORT)/postgres

ALEMBIC = uv run --no-sync alembic -c services/agents/alembic.ini

.PHONY: eval eval-update redis-up redis-down dev-up worker api setup generate check-generated lint test typecheck db-up db-down migrate migrate-down migrate-check

setup:
	uv sync --all-packages
	pnpm install

generate: ## regenerate TS + Pydantic from packages/contracts/schemas
	pnpm generate

check-generated: generate ## fail if committed generated files drift from the schemas
	git add -N packages/contracts/ts packages/contracts/python
	git diff --exit-code -- packages/contracts/ts packages/contracts/python

db-up: ## start the local Postgres cluster (creates it and the `a9` database on first run)
	@test -d "$(PGDATA)" || $(PG_BIN)/initdb -D "$(PGDATA)" -A trust -U "$$(whoami)" >/dev/null
	@$(PG_BIN)/pg_isready -q -p $(PG_PORT) || $(PG_BIN)/pg_ctl -D "$(PGDATA)" -l "$(PGDATA)/server.log" -o "-p $(PG_PORT) -c listen_addresses=localhost" -w start >/dev/null
	@$(PG_BIN)/psql -p $(PG_PORT) -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='a9'" | grep -q 1 || $(PG_BIN)/createdb -p $(PG_PORT) a9

db-down: ## stop the local Postgres cluster
	@$(PG_BIN)/pg_ctl -D "$(PGDATA)" stop -m fast >/dev/null 2>&1 || true

redis-up: ## start a project-local Redis
	@$(REDIS_CLI) -p $(REDIS_PORT) ping >/dev/null 2>&1 || (mkdir -p .redisdata && $(REDIS_BIN) --port $(REDIS_PORT) --dir "$(CURDIR)/.redisdata" --save "" --appendonly no --daemonize yes >/dev/null)

redis-down:
	@$(REDIS_CLI) -p $(REDIS_PORT) shutdown nosave >/dev/null 2>&1 || true

dev-up: db-up redis-up migrate ## everything the services need locally

worker: ## run an Arq worker
	uv run --no-sync arq a9_workers.worker.WorkerSettings

api: ## run the agents service (needs A9_INTERNAL_KEY; A9_ENABLE_DEV_ENDPOINTS=1 for the dummy run)
	uv run --no-sync uvicorn a9_agents.app:app --port 8100 --reload

migrate: ## apply all migrations to A9_DATABASE_URL
	$(ALEMBIC) upgrade head

migrate-down: ## revert all migrations
	$(ALEMBIC) downgrade base

migrate-check: ## up, down, up: a clean round trip
	$(ALEMBIC) upgrade head && $(ALEMBIC) downgrade base && $(ALEMBIC) upgrade head

lint:
	uv run --no-sync ruff check services packages/contracts/tests
	uv run --no-sync ruff format --check services packages/contracts/tests
	uv run --no-sync mypy services packages/contracts/python

test: ## DB tests need `make db-up` (they skip locally if Postgres is down; CI sets A9_REQUIRE_DB=1)
	uv run --no-sync pytest services packages/contracts/tests -q

typecheck:
	pnpm typecheck

eval: ## golden-set evaluations; fail on regression against the recorded baselines
	uv run --no-sync python -m a9_agents.evals.triage

eval-update: ## accept the current scores as the new baselines
	uv run --no-sync python -m a9_agents.evals.triage --update
