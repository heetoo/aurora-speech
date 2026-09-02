# Deployment

## Image

The `Dockerfile` is a two-stage build:

1. **builder** — copies the `uv` binary from `ghcr.io/astral-sh/uv` and runs
   `uv sync --frozen --no-dev`, producing `/app/.venv` with the exact versions
   from `uv.lock` (FastAPI, Uvicorn, Pydantic, soundfile, Kokoro + torch; the
   `dev` group is excluded).
2. **runtime** — `python:3.12-slim` with only the runtime apt packages, the
   copied `/app` (including `.venv`) and `app/`. Runs as the non-root user
   `aurora` (uid 1000). `--frozen` makes the build fail if `uv.lock` is stale.

Runtime apt packages:

| Package       | Why                                             |
| ------------- | ---------------------------------------------- |
| `espeak-ng`   | phonemizer backend Kokoro needs for pt-BR       |
| `libsndfile1` | OGG/Vorbis encoding used by `soundfile`         |
| `curl`        | container `HEALTHCHECK`                         |

`HEALTHCHECK` polls `http://localhost:8000/health` every 30s (40s start period).

`CACHE_DIR` is baked to `/app/cache` via `ENV` so the container always caches in
the same place regardless of `.env`.

## docker compose

```bash
docker compose up --build
```

`docker-compose.yml` sets the environment from `.env.example`'s keys and mounts
the cache volume. The service listens on `:8000`.

### Configuration

All configuration is environment-driven (`app/config.py`, `pydantic-settings`).

| Variable         | Default             | Notes                                        |
| ---------------- | ------------------- | ------------------------------------------- |
| `APP_NAME`       | `Aurora Speech`     | OpenAPI title                                |
| `APP_VERSION`    | `1.0.0`             | Reported by `/health`                        |
| `CACHE_DIR`      | `/app/cache` (image)| Cache root; keep pointed at the mounted vol  |
| `ENGINE_NAME`    | `kokoro-82m-v2`     | Logical engine id; part of the cache key     |
| `DEFAULT_VOICE`  | `teacher_female_v1` | Fallback voice                               |
| `AUDIO_LOWPASS_HZ`   | `3500`         | One-pole HF de-emphasis cutoff; `0` disables |
| `AUDIO_FADE_IN_MS`   | `10`           | Linear fade-in length                        |
| `AUDIO_FADE_OUT_MS`  | `200`          | Raised-cosine fade-out length; `0` disables  |
| `AUDIO_GATE_ENABLED` | `true`         | Trailing noise gate on/off                   |
| `AUDIO_GATE_FLOOR_DB`| `-30.0`        | Tail RMS below this dBFS is ramped to zero   |

The `AUDIO_*` knobs shape the waveform post-processing that reduces the trailing
breath/hiss the pt-BR Kokoro voices append (see
[`architecture.md`](architecture.md#waveform-post-processing)). Changing any of
them changes the audio output, so bump `ENGINE_NAME` when you do.

Copy `.env.example` to `.env` to override locally.

## The `/storage` volume (homelab)

Every homelab service keeps persistent data under the single root volume
`/storage`. `aurora-speech` owns one subtree:

```
/storage/
└── aurora-speech/
    └── cache/            <- bind-mounted to /app/cache
        ├── 9d/
        │   └── 9d5d9b6f….ogg
        └── af/
            └── af18d2c7….ogg
```

`docker-compose.yml`:

```yaml
volumes:
  - /storage/aurora-speech/cache:/app/cache
```

### One-time host setup

```bash
sudo mkdir -p /storage/aurora-speech/cache
sudo chown -R 1000:1000 /storage/aurora-speech/cache   # uid of the 'aurora' user
```

The `1000:1000` ownership matches the non-root container user so it can write.

### Why this matters

Without the bind mount the cache lives in the container's ephemeral writable
layer. `docker compose down`, an image rebuild or a host move wipes it, and
every request silently becomes a `MISS` again — more CPU, slower responses, no
error. Treat the mount as mandatory in any real deployment.

## Running in the homelab

```bash
# on the homelab host
git clone <repo> aurora-speech && cd aurora-speech
sudo mkdir -p /storage/aurora-speech/cache
sudo chown -R 1000:1000 /storage/aurora-speech/cache
docker compose up --build -d
docker compose ps          # wait for "healthy"
curl -s localhost:8000/health
```

Other Aurora services reach it in-network as `http://aurora-speech:8000`.

### Local run without `/storage`

Edit the volume line in `docker-compose.yml` to:

```yaml
      - ./cache:/app/cache
```

or run the app directly (`uv run uvicorn app.main:app`) with `CACHE_DIR=./cache`.

## Upgrades

- Code/model change that alters audio output → bump `ENGINE_NAME`
  (`kokoro-82m-v1` → `-v2`). Old cache files stay on disk but are never read;
  delete them at leisure.
- Rolling restart is safe: the service is stateless and the cache is external.
