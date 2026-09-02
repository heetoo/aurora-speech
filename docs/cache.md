# Cache

The cache is the core responsibility of `aurora-speech`. It guarantees that the
same synthesis request is never sent to the engine twice, and its layout is
stable enough to live on a long-lived persistent volume.

## Deterministic hash

The cache key is:

```
sha256( canonical_json({ "engine", "voice", "mode", "text" }) )
```

`canonical_json` produces a byte-stable string:

- keys sorted alphabetically (`engine`, `mode`, `text`, `voice`);
- no whitespace (`separators=(",", ":")`);
- UTF-8, `ensure_ascii=false` (accented pt-BR characters kept as-is).

Example input:

```json
{"engine":"kokoro-82m-v2","mode":"word","text":"bola","voice":"teacher_female_v1"}
```

The digest is 64 lowercase hex characters. The same four inputs always produce
the same key, in any process, on any machine.

### Fields and why each one matters

| Field    | Source                          | Changing it means…                            |
| -------- | ------------------------------- | -------------------------------------------- |
| `engine` | `ENGINE_NAME` setting          | New engine/version → full logical invalidation |
| `voice`  | request (`teacher_female_v1` …) | Different speaker                            |
| `mode`   | request (`word`, `letter` …)    | Different speed/prosody, so different audio  |
| `text`   | request, trimmed               | Different words                              |

`voice` is the **public** id, not the engine-native name. Swapping the engine
while keeping voice ids stable does not by itself change keys — bump
`ENGINE_NAME` to force regeneration.

## File organization

```
cache/
├── 9d/
│   └── 9d5d9b6f0b0e2f0a1c…​.ogg
├── af/
│   └── af18d2c7…​.ogg
└── …
```

- Path = `<cache_dir>/<key[:2]>/<key>.ogg`.
- The first two hex characters are the **shard directory** (256 buckets),
  keeping any single directory small.
- The filename is the full hash plus `.ogg`.
- **The text is never used as a filename or path component.**

## Write semantics

`Cache.put` is atomic:

1. Ensure the shard directory exists.
2. Write bytes to a temporary file *in the same shard directory*.
3. `os.replace(tmp, final)` — an atomic rename on the same filesystem.

Consequences:

- A reader never sees a truncated file.
- Two concurrent cache misses for the same key both succeed; the last rename
  wins and the bytes are equivalent.

## Read semantics

`Cache.get` returns the file bytes if `<cache_dir>/<key[:2]>/<key>.ogg` exists,
otherwise `None`. No locking, no TTL, no size cap.

## Invalidation policy

There is **no automatic expiry**. Invalidation is implicit and total:

- Change `engine`, `voice`, `mode` or `text` → new key → new file. The old file
  is simply never requested again.
- To force regeneration of everything, bump `ENGINE_NAME`
  (e.g. `kokoro-82m-v1` → `kokoro-82m-v2`).
- To reclaim space, delete files (or whole shard directories) from the cache
  volume. It is safe to delete any or all of them at any time — the next
  matching request just becomes a `MISS` and repopulates.

Aurora is the system of record for official assets; this cache is a disposable
optimization.

## Persistent volume — `/storage/aurora-speech/cache`

**Architectural decision.** In the homelab, every service stores persistent
data under the root volume `/storage`. `aurora-speech` owns:

```
/storage/aurora-speech/cache
```

`docker-compose.yml` mounts it into the container at `/app/cache` (the value of
`CACHE_DIR` inside the image):

```yaml
volumes:
  - /storage/aurora-speech/cache:/app/cache
```

Do not let this detail get lost: without the bind mount the cache lives inside
the container's writable layer and is destroyed on every `docker compose down`
/ image rebuild, silently turning every request back into a `MISS`. See
[`deployment.md`](deployment.md).
