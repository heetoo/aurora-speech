# Architecture

## Responsibilities

`aurora-speech` owns exactly one capability: **pt-BR text → audio**, with a
cache to skip repeated work. It has no domain knowledge and no persistent state
other than the audio cache directory.

## Components

| Module          | Responsibility                                                                 |
| --------------- | ----------------------------------------------------------------------------- |
| `app/main.py`   | Application factory (`create_app`) and lifespan (cache dir, optional warm-up). |
| `app/api.py`    | The three HTTP routes. Orchestrates cache lookup → engine → cache store.       |
| `app/schemas.py`| Pydantic v2 request/response models and input validation.                      |
| `app/cache.py`  | Deterministic key derivation + sharded on-disk storage with atomic writes.     |
| `app/engine.py` | `SpeechEngine` abstract base and `KokoroEngine` implementation.                |
| `app/voices.py` | Public voice ids and their (private) mapping to engine-native voices.          |
| `app/modes.py`  | `SpeechMode` enum → internal `ModeConfig` (speed / prosody).                   |
| `app/config.py` | `pydantic-settings` configuration, environment-driven.                         |
| `app/utils.py`  | Canonical JSON, SHA-256, elapsed-time helpers.                                 |

## Request flow — `POST /v1/synthesize`

```
client
  │  JSON { text, voice, mode }
  ▼
SynthesizeRequest  ── validate: text 1..500 & not blank, voice known, mode known
  │
  ▼
cache.compute_key(engine_name, voice, mode, text)   ──►  sha256 hex
  │
  ▼
cache.get(key) ────────────► found ──►  return bytes           X-Cache: HIT
  │ not found
  ▼
mode -> ModeConfig.speed
voice -> engine-native voice           (app/voices.resolve_engine_voice)
  │
  ▼
engine.synthesize(text, engine_voice, speed)   (run in threadpool)
  │  OGG/Vorbis bytes
  ▼
cache.put(key, bytes)      atomic: temp file in shard dir + os.replace
  │
  ▼
return bytes                                            X-Cache: MISS
```

Every response carries `X-Cache`, `X-Cache-Key` and `X-Duration-Ms`.

## Cache flow

- **Key** = `sha256(canonical_json({engine, voice, mode, text}))`.
  Canonical JSON = sorted keys, no whitespace, UTF-8, `ensure_ascii=false`.
- **Path** = `<cache_dir>/<key[:2]>/<key>.ogg`. The first two hex characters
  form the shard directory; the text is never part of any path.
- **Writes** are atomic: content goes to a temporary file in the same shard
  directory and is renamed into place, so concurrent readers never observe a
  partial file and two concurrent misses converge on the same final bytes.
- **Invalidation** is implicit: change `engine`, `voice`, `mode` or `text` and
  you get a new key, hence a new file. Old files are simply never read again.

See [`cache.md`](cache.md) for the full policy.

## Statelessness

The process holds no request state. The only mutable state is the cache
directory on disk, which is mounted from a persistent volume
(`/storage/aurora-speech/cache` in the homelab). Restarting or replacing the
container loses nothing but in-memory model weights, which reload on demand.

## Engine abstraction & swappability

`app/api.py` depends only on `SpeechEngine.synthesize(text, voice, speed)
-> bytes`. Kokoro-specific concerns are isolated:

- model loading and OGG encoding live in `KokoroEngine`;
- the `pt-BR` language code and repo id live in `config.py`;
- the public-id → engine-voice table lives in `voices.py`.

To swap engines: add a new `SpeechEngine` subclass, point `build_engine()` at
it, and update the `engine_voice` column in `voices.py`. Request and response
shapes, headers and the cache key structure stay identical. Bumping
`ENGINE_NAME` then transparently invalidates the old cache.

## Waveform post-processing

`KokoroEngine.synthesize` does not encode the raw model output directly.
`_finalize_waveform` (in `app/engine.py`) runs first:

1. **Clip guard** — peak-normalise if any sample exceeds ±1.0.
2. **Silence trim** — drop the near-silent head/tail, keeping a ~10 ms margin.
3. **HF de-emphasis** — a one-pole low-pass at `AUDIO_LOWPASS_HZ` (default
   3.5 kHz), implemented as a truncated exponential FIR (no SciPy).
4. **Fades** — a short linear fade-in (`AUDIO_FADE_IN_MS`) and a long
   raised-cosine fade-out (`AUDIO_FADE_OUT_MS`, default 200 ms).
5. **Trailing noise gate** — walk back from the end in 20 ms windows while each
   is quieter than `AUDIO_GATE_FLOOR_DB` (default −30 dBFS), then quadratically
   ramp that whole span to zero.

Steps 3–5 exist because the pt-BR Kokoro voices append a low-level
high-frequency breath/hiss after the last phoneme (word-dependent — "bola" has
it, "escola" does not). Together they cut roughly 4–5× of that tail energy
while leaving louder, legitimate word-final fricatives (`s`, `z`, `x`) intact.
The parameters are settings; `ENGINE_NAME` (`kokoro-82m-v2`) encodes this
processing so a change to it invalidates the cache. Set `AUDIO_LOWPASS_HZ=0`,
`AUDIO_FADE_OUT_MS=0` or `AUDIO_GATE_ENABLED=false` to bypass a stage.

## Concurrency

`engine.synthesize` is synchronous and CPU-bound; the route awaits it via
`run_in_threadpool` so the event loop stays responsive. The cache's atomic
write makes concurrent identical misses safe.
