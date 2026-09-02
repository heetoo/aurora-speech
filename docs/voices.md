# Voices

## Public contract

`GET /voices` returns a small, curated list of Aurora-branded voices:

```json
{
  "voices": [
    { "id": "teacher_female_v1", "description": "Voz principal da alfabetização" },
    { "id": "teacher_male_v1",   "description": "Voz masculina" },
    { "id": "mascot_v1",         "description": "Mascote Aurora" }
  ]
}
```

Each entry has exactly two fields:

| Field         | Meaning                                             |
| ------------- | ------------------------------------------------- |
| `id`          | Stable identifier callers pass as `voice`          |
| `description` | Human-readable label (pt-BR)                       |

`POST /v1/synthesize` accepts any of these `id` values in its `voice` field.
An unknown id is a `422`.

## Stability guarantees

- Voice **ids are stable**. `teacher_female_v1` will always refer to the same
  *role* (Aurora's primary literacy teacher voice).
- The **timbre behind an id may be retuned** over time. When a change would
  alter audio output, `ENGINE_NAME` is bumped so the cache regenerates.
- A materially different voice gets a **new id** (`…_v2`), it does not silently
  replace an existing one.
- The default voice is `teacher_female_v1` (`DEFAULT_VOICE`).

## What is never exposed

The mapping from a public id to the engine-native voice is an internal detail
and is **never returned by any endpoint**:

| Public id           | Role                         |
| ------------------- | --------------------------- |
| `teacher_female_v1` | Primary literacy teacher     |
| `teacher_male_v1`   | Alternate male teacher       |
| `mascot_v1`         | Aurora mascot                |

The concrete engine voice names live only in `app/voices.py` (`engine_voice`
column) and in the running process. Consumers must not depend on them; they
change when the engine changes.

## Adding a voice

1. Add a `Voice(id=…, description=…, engine_voice=…)` entry to `_VOICES` in
   `app/voices.py`.
2. Add a test asserting it appears in `GET /voices` without leaking
   `engine_voice`.
3. Document the role in the table above.

No API version bump is needed to add a voice; the response is an open list.
