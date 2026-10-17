# aurora-speech

Internal microservice of the **Aurora** platform. It turns short pieces of
**Brazilian Portuguese (pt-BR)** text into audio using a **local Kokoro TTS**
model, with a deterministic on-disk cache so identical requests are never
synthesized twice.

The service is intentionally tiny and self-contained:

- **pt-BR only.** No language parameter, no multilingual behaviour.
- **Stateless**, except for the audio cache on disk.
- **No database.**
- **Knows nothing about Aurora** — no curriculum, words, assets, MinIO, auth.
  Aurora is responsible for storing official assets; this service only avoids
  repeated synthesis.
- **Small, stable API** designed so Kokoro can later be replaced by another
  engine without changing a single public contract.

---

## API

| Method | Path              | Purpose                                  |
| ------ | ----------------- | ---------------------------------------- |
| `POST` | `/v1/synthesize`  | Synthesize text, returns `audio/ogg`     |
| `GET`  | `/health`         | Liveness + active engine                 |
| `GET`  | `/voices`         | Public Aurora voice catalogue           |

### `POST /v1/synthesize`

Request:

```json
{ "text": "bola", "voice": "teacher_female_v1", "mode": "word" }
```

- `text` — required, 1–500 characters.
- `voice` — optional, defaults to `teacher_female_v1`.
- `mode` — optional, defaults to `word`. One of `phoneme`, `letter`,
  `syllable`, `word`, `instruction`, `feedback`.

Response: raw **OGG/Vorbis** bytes (`Content-Type: audio/ogg`, never JSON) with
headers:

```
X-Cache: HIT | MISS
X-Cache-Key: <sha256 hex>
X-Duration-Ms: <int>
```

Full reference: [`docs/api.md`](docs/api.md).

---

## Quick start

### Docker (recommended)

```bash
docker compose up --build
curl -s -X POST http://localhost:8000/v1/synthesize \
  -H 'content-type: application/json' \
  -d '{"text":"bola"}' --output bola.ogg
```

> The compose file bind-mounts the cache to `/storage/aurora-speech/cache`.
> See [`docs/deployment.md`](docs/deployment.md) for the homelab volume layout
> and how to run it without `/storage`.

### Local development

Uses [uv](https://docs.astral.sh/uv/) for dependency management. A `Makefile`
wraps the common tasks (`make help` lists them).

```bash
make sync                          # runtime + engine (Kokoro/torch) + dev tools
make check                         # lint + typecheck + tests
make run                           # uv run uvicorn app.main:app --reload
```

`make sync` installs everything needed, including the phonemizer backend
(`espeakng-loader` bundles `espeak-ng`). If you hit a phonemizer error, install
the system package as a fallback: `brew install espeak-ng` (macOS) /
`sudo apt-get install espeak-ng` (Debian).

Equivalent raw commands: `uv sync`, `uv run pytest`, `uv run ruff check .`,
`uv run mypy`, `uv run uvicorn app.main:app --reload`.

More: [`docs/development.md`](docs/development.md).

### Error tracking (optional)

[Sentry](https://sentry.io) is only initialised when `SENTRY_DSN` is set, so
local runs and tests send nothing. Request bodies and stack-frame local
variables are never attached (the synthesized text never leaves the service),
and PII collection is off.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SENTRY_DSN` | empty | Enables Sentry |
| `SENTRY_ENVIRONMENT` | `production` | Event environment |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.05` | Share of requests traced (`/health`, `/voices` and docs are skipped) |

The release is the commit SHA:
`APP_GIT_SHA=$(git rev-parse --short HEAD) docker compose up --build`.

---

## Documentation

| File                                       | Contents                                            |
| ------------------------------------------ | --------------------------------------------------- |
| [`docs/README.md`](docs/README.md)         | Service overview                                    |
| [`docs/architecture.md`](docs/architecture.md) | Components, responsibilities, cache flow        |
| [`docs/api.md`](docs/api.md)               | Full endpoint reference with examples               |
| [`docs/cache.md`](docs/cache.md)           | Hashing, file layout, invalidation, `/storage`      |
| [`docs/deployment.md`](docs/deployment.md) | Docker, Compose, `/storage` volume, homelab         |
| [`docs/voices.md`](docs/voices.md)         | Public voice contract                               |
| [`docs/development.md`](docs/development.md) | Local setup, tests, lint                          |

---

## Project layout

```text
app/
  api.py        FastAPI routes
  main.py       Application factory + lifespan
  engine.py     SpeechEngine abstraction + KokoroEngine
  cache.py      Deterministic on-disk cache
  config.py     pydantic-settings configuration
  schemas.py    Request/response models
  voices.py     Public voice registry (id -> engine voice)
  modes.py      Speaking modes -> internal prosody
  utils.py      Hashing / timing helpers
tests/          pytest suite (engine is stubbed)
docs/           Markdown documentation
```

## Stack

Python 3.12 · uv · FastAPI · Uvicorn · Pydantic v2 · pydantic-settings ·
Kokoro TTS (local) · soundfile · Docker / Compose · pytest · Ruff · mypy ·
pre-commit.

## License

[MIT](LICENSE)
