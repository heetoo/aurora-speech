# API Reference (v1)

Base URL in the homelab: `http://aurora-speech:8000`.

The service exposes three endpoints. Only the synthesis route is versioned.

Interactive docs are served at `/docs` (Swagger UI) and `/openapi.json`.

---

## `POST /v1/synthesize`

Synthesize pt-BR text into audio. Serves from cache when possible.

### Request body

| Field   | Type   | Required | Default              | Rules                                              |
| ------- | ------ | -------- | -------------------- | ------------------------------------------------- |
| `text`  | string | yes      | —                    | Trimmed; 1–500 characters; must not be blank      |
| `voice` | string | no       | `teacher_female_v1`  | Must be a registered public voice (`GET /voices`) |
| `mode`  | string | no       | `word`               | One of the modes below                            |

Modes: `phoneme`, `letter`, `syllable`, `word`, `instruction`, `feedback`.
Each mode maps internally to a synthesis speed/prosody. The API never accepts a
raw speed value.

```json
{
  "text": "bola",
  "voice": "teacher_female_v1",
  "mode": "word"
}
```

### Success response — `200 OK`

- **Body:** raw `OGG/Vorbis` audio bytes. Never JSON.
- **Headers:**

| Header          | Example                              | Meaning                                     |
| --------------- | ----------------------------------- | ------------------------------------------- |
| `Content-Type`  | `audio/ogg`                         | Always                                      |
| `X-Cache`       | `HIT` or `MISS`                     | Whether the file was served from cache      |
| `X-Cache-Key`   | `9d5d9b6f…` (64 hex chars)          | SHA-256 of the synthesis inputs             |
| `X-Duration-Ms` | `812`                              | Whole milliseconds spent handling the call  |

### Error responses

| Status | When                                                               |
| ------ | ----------------------------------------------------------------- |
| `422`  | `text` missing, blank, or >500 chars; unknown `voice`; bad `mode` |

Errors are JSON (FastAPI's standard validation error shape).

### Examples

```bash
# Minimal — defaults for voice and mode
curl -s -X POST http://localhost:8000/v1/synthesize \
  -H 'content-type: application/json' \
  -d '{"text":"bola"}' \
  --output bola.ogg -D -

# Explicit voice + mode
curl -s -X POST http://localhost:8000/v1/synthesize \
  -H 'content-type: application/json' \
  -d '{"text":"Escute a palavra e repita","voice":"teacher_female_v1","mode":"instruction"}' \
  --output instrucao.ogg
```

Response headers on a first (uncached) call:

```
HTTP/1.1 200 OK
content-type: audio/ogg
x-cache: MISS
x-cache-key: 9d5d9b6f0b0e2f0a...
x-duration-ms: 934
```

Repeat the same request and it becomes:

```
x-cache: HIT
x-cache-key: 9d5d9b6f0b0e2f0a...
x-duration-ms: 1
```

---

## `GET /health`

Liveness probe and active-engine report. Used by the container `HEALTHCHECK`.

### Response — `200 OK`

```json
{
  "status": "healthy",
  "engine": "kokoro-82m-v2",
  "version": "1.0.0"
}
```

`engine` is the logical `ENGINE_NAME`; `version` is `APP_VERSION`.

---

## `GET /voices`

Public Aurora voice catalogue. Internal engine voice names are never exposed.

### Response — `200 OK`

```json
{
  "voices": [
    { "id": "teacher_female_v1", "description": "Voz principal da alfabetização" },
    { "id": "teacher_male_v1",   "description": "Voz masculina" },
    { "id": "mascot_v1",         "description": "Mascote Aurora" }
  ]
}
```

See [`voices.md`](voices.md) for the contract and stability guarantees.
