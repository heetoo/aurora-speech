# Development

Dependency management is done with [uv](https://docs.astral.sh/uv/). A `Makefile`
wraps the common tasks — run `make help` for the list. Every target below has a
`make` shortcut (`make sync`, `make run`, `make test`, `make check`, ...).

## Requirements

- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Python 3.12 — uv provisions it automatically from `.python-version`

That's it. `uv sync` pulls Kokoro, torch and a bundled `espeak-ng`
(`espeakng-loader`). Only if you hit a phonemizer error, install the system
package as a fallback: `brew install espeak-ng` (macOS) /
`sudo apt-get install espeak-ng libsndfile1` (Debian/Ubuntu).

## Setup

```bash
uv sync
```

This creates `.venv/` and installs everything: the locked runtime deps
(including the Kokoro engine and torch) plus the `dev` group (pytest, Ruff,
mypy, pre-commit). Kokoro/torch are a large download the first time.

The test suite stubs the engine, so it never loads a model — but torch is still
installed as a normal dependency.

Run commands inside the environment with `uv run <cmd>` (no manual activation
needed), or `source .venv/bin/activate`.

### Lockfile

`uv.lock` is committed and is the source of truth for exact versions. After
changing dependencies in `pyproject.toml`, run `uv lock` and commit the result.
CI / Docker use `uv sync --frozen` to fail if the lock is stale.

## Configuration

```bash
cp .env.example .env
# for a local run without /storage:
echo "CACHE_DIR=./cache" >> .env
```

Settings are defined in `app/config.py` (`pydantic-settings`). Environment
variables and `.env` both work; env vars win.

## Run the server

```bash
make run           # uv run uvicorn app.main:app --reload
# http://localhost:8000/docs
```

The first `POST /v1/synthesize` (a cache MISS) downloads the Kokoro-82M weights
(~330 MB, cached by Hugging Face afterwards), so it is slow. Subsequent MISSes
are fast; a cache HIT never touches the engine at all.

Smoke test:

```bash
curl -s -X POST localhost:8000/v1/synthesize \
  -H 'content-type: application/json' \
  -d '{"text":"bola"}' --output bola.ogg -D -
```

## Tests

```bash
uv run pytest
```

Covered:

- `/health` response shape
- `/voices` list + no engine-name leakage
- cache key determinism and per-field sensitivity
- cache `HIT` / `MISS` behaviour end-to-end (engine called once)
- sharded file layout, text never used as a filename
- Pydantic validation (missing/blank/too-long text, unknown voice, bad mode)

The engine is replaced by `tests/conftest.py::StubEngine`, which returns a real
short OGG file via `soundfile`, so headers and cache paths are exercised for
real without loading a model.

## Lint, format, types

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

- **Ruff** — lint + formatter. Config in `pyproject.toml` (`line-length = 100`,
  rule sets `E,F,I,UP,B,SIM,N,D,RUF`, Google docstring convention).
- **mypy** — `strict = true` over `app/` and `tests/` (tests relax
  `disallow_untyped_defs`). `soundfile`/`kokoro` are treated as untyped.

## pre-commit

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Runs the pre-commit-hooks basics, Ruff (with `--fix`) + `ruff-format`, and mypy
over `app/`.

## Conventions

- Full type hints across `app/`.
- Docstrings in **English**, Google style.
- Keep the public API (routes, request/response shapes, headers, cache key
  fields) stable. Engine-specific behaviour stays behind `SpeechEngine` and
  `app/voices.py`.
