# Development

## Requirements

- Python 3.12
- (only to run real synthesis locally) `espeak-ng`
  - macOS: `brew install espeak-ng`
  - Debian/Ubuntu: `sudo apt-get install espeak-ng libsndfile1`

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`.[dev]` installs FastAPI, pytest, Ruff, mypy and pre-commit but **not** Kokoro
or torch, so it is fast. The test suite stubs the engine and never needs them.

To run actual synthesis locally, also install the engine extra:

```bash
pip install -e ".[dev,kokoro]"
```

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
uvicorn app.main:app --reload
# http://localhost:8000/docs
```

Smoke test:

```bash
curl -s -X POST localhost:8000/v1/synthesize \
  -H 'content-type: application/json' \
  -d '{"text":"bola"}' --output bola.ogg -D -
```

## Tests

```bash
pytest
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
ruff check .
ruff format --check .
mypy
```

- **Ruff** — lint + formatter. Config in `pyproject.toml` (`line-length = 100`,
  rule sets `E,F,I,UP,B,SIM,N,D,RUF`, Google docstring convention).
- **mypy** — `strict = true` over `app/` and `tests/` (tests relax
  `disallow_untyped_defs`). `soundfile`/`kokoro` are treated as untyped.

## pre-commit

```bash
pre-commit install
pre-commit run --all-files
```

Runs the pre-commit-hooks basics, Ruff (with `--fix`) + `ruff-format`, and mypy
over `app/`.

## Conventions

- Full type hints across `app/`.
- Docstrings in **English**, Google style.
- Keep the public API (routes, request/response shapes, headers, cache key
  fields) stable. Engine-specific behaviour stays behind `SpeechEngine` and
  `app/voices.py`.
