# A9 workspace tasks. Legacy Streamlit code at the repo root is out of scope for these targets.
# A9's Python env is separate from the legacy .venv so `uv sync` never touches it.
export UV_PROJECT_ENVIRONMENT ?= .venv-a9

.PHONY: setup generate check-generated lint test typecheck

setup:
	uv sync --all-packages
	pnpm install

generate: ## regenerate TS + Pydantic from packages/contracts/schemas
	pnpm generate

check-generated: generate ## fail if committed generated files drift from the schemas
	git add -N packages/contracts/ts packages/contracts/python
	git diff --exit-code -- packages/contracts/ts packages/contracts/python

lint:
	uv run --no-sync ruff check services packages/contracts/tests
	uv run --no-sync ruff format --check services packages/contracts/tests
	uv run --no-sync mypy services packages/contracts/python

test:
	uv run --no-sync pytest services packages/contracts/tests -q

typecheck:
	pnpm typecheck
