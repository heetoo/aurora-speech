# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ---------------------------------------------------------------------------
# Builder: create a self-contained virtualenv with all dependencies
# ---------------------------------------------------------------------------
FROM base AS builder
WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --upgrade pip \
    && pip install ".[kokoro]"

# ---------------------------------------------------------------------------
# Runtime: minimal image, non-root user, healthcheck
# ---------------------------------------------------------------------------
FROM base AS runtime

# espeak-ng   -> phonemizer backend required for pt-BR in Kokoro
# libsndfile1 -> OGG/Vorbis encoding via soundfile
# curl        -> container healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng libsndfile1 curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 aurora

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    CACHE_DIR=/app/cache

WORKDIR /app
COPY app ./app
RUN mkdir -p /app/cache && chown -R aurora:aurora /app

USER aurora
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
