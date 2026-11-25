# A9 workspace tasks. Legacy Streamlit code at the repo root is out of scope for these targets.
# A9's Python env is separate from the legacy .venv so `uv sync` never touches it.
export UV_PROJECT_ENVIRONMENT ?= .venv-a9

# Local Postgres for development and tests: a project-local cluster (no system service, no Docker).
PG_BIN  ?= /opt/homebrew/opt/postgresql@16/bin
PG_PORT ?= 5544
PGDATA  ?= $(CURDIR)/.pgdata
export A9_DATABASE_URL  ?= postgresql+psycopg://localhost:$(PG_PORT)/a9
export A9_PG_ADMIN_URL  ?= postgresql://localhost:$(PG_PORT)/postgres

ALEMBIC = uv run --no-sync alembic -c services/agents/alembic.ini

.PHONY: setup generate check-generated lint test typecheck db-up db-down migrate migrate-down migrate-check

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
