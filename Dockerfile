# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ---------------------------------------------------------------------------
# Builder: resolve the locked environment into /app/.venv with uv
# ---------------------------------------------------------------------------
FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5.9 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY app ./app

# Exact versions from uv.lock, without the dev tooling group.
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Runtime: minimal image, non-root user, healthcheck
# ---------------------------------------------------------------------------
FROM base AS runtime

# Commit SHA, used as the Sentry release. Pass with --build-arg APP_GIT_SHA=...
ARG APP_GIT_SHA=unknown

# espeak-ng   -> phonemizer backend required for pt-BR in Kokoro
# libsndfile1 -> OGG/Vorbis encoding via soundfile
# curl        -> container healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng libsndfile1 curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 aurora

COPY --from=builder --chown=aurora:aurora /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    CACHE_DIR=/app/cache \
    APP_GIT_SHA=${APP_GIT_SHA}

WORKDIR /app
RUN mkdir -p /app/cache && chown -R aurora:aurora /app/cache

USER aurora
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
