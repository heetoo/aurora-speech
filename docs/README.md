# Aurora Speech — Overview

`aurora-speech` is an internal microservice of the Aurora platform. Its only
job is to synthesize short pieces of **Brazilian Portuguese** text into audio
and to avoid doing the same synthesis twice.

## What it does

1. Accepts a text (max 500 characters), a public voice id and a speaking mode.
2. Computes a deterministic SHA-256 cache key from the synthesis inputs.
3. Returns the cached `audio/ogg` file if it exists (`X-Cache: HIT`).
4. Otherwise runs Kokoro locally, stores the result, and returns it
   (`X-Cache: MISS`).

## What it deliberately does NOT do

- No languages other than pt-BR.
- No database, no message queue, no object storage.
- No knowledge of Aurora's domain: curriculum, words, lessons, assets, users,
  MinIO, authentication. Those belong to Aurora.
- No permanent asset management. The cache is an optimization, not a system of
  record — Aurora stores the official assets it needs.
- No raw speed/pitch parameters in the API. Callers choose a *mode*.

## Design goals

- **Small and stable API.** Three endpoints, versioned synthesis route.
- **Engine-swappable.** All Kokoro specifics sit behind `SpeechEngine`
  (`app/engine.py`) and the voice registry (`app/voices.py`). Replacing the
  engine does not change request or response shapes.
- **Deterministic caching.** Same inputs → same key → same file, across
  processes and machines, backed by a persistent volume.
- **Production-ready container.** Small image, non-root user, healthcheck.

## Where to go next

- [`architecture.md`](architecture.md) — components and the cache flow.
- [`api.md`](api.md) — endpoint reference.
- [`cache.md`](cache.md) — hashing and file layout.
- [`deployment.md`](deployment.md) — running it in the homelab.
- [`voices.md`](voices.md) — the public voice contract.
- [`development.md`](development.md) — local setup.
