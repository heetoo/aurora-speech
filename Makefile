.DEFAULT_GOAL := help
.PHONY: help sync run run-prod test lint format typecheck check lock \
        docker-build docker-up docker-down clean

# Host/port for the local dev server
HOST ?= 0.0.0.0
PORT ?= 8000

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

sync: ## Install/refresh the environment with uv (runtime + engine + dev tools)
	uv sync

run: ## Run the API locally with autoreload (uses .venv via uv)
	uv run uvicorn app.main:app --reload --host $(HOST) --port $(PORT)

run-prod: ## Run the API without autoreload (production-style)
	uv run uvicorn app.main:app --host $(HOST) --port $(PORT)

test: ## Run the test suite
	uv run pytest

lint: ## Lint with Ruff
	uv run ruff check .

format: ## Format the codebase with Ruff
	uv run ruff format .

typecheck: ## Static type check with mypy (strict)
	uv run mypy

check: lint typecheck test ## Run lint + typecheck + tests
	uv run ruff format --check .

lock: ## Re-resolve and update uv.lock
	uv lock

docker-build: ## Build the container image
	docker compose build

docker-up: ## Build and start the service via docker compose
	docker compose up --build

docker-down: ## Stop the service
	docker compose down

clean: ## Remove caches and build artifacts (keeps .venv and cached audio)
	rm -rf .ruff_cache .mypy_cache .pytest_cache **/__pycache__ *.egg-info
