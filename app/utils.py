"""Small, dependency-free helpers shared across the service."""

from __future__ import annotations

import hashlib
import json
from time import perf_counter


def canonical_json(data: dict[str, str]) -> str:
    """Serialize a mapping to a deterministic JSON string.

    Keys are sorted and separators are tight so that the same logical payload
    always produces byte-identical output, which is what makes the cache key
    stable across processes and machines.
    """
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(payload: str) -> str:
    """Return the lowercase hex SHA-256 digest of a UTF-8 string."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def elapsed_ms(started: float) -> int:
    """Return whole milliseconds elapsed since a ``time.perf_counter()`` value."""
    return int((perf_counter() - started) * 1000)
