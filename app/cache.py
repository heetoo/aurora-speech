"""Deterministic, content-addressed on-disk cache for synthesized audio.

This is the core responsibility of the service. Identical synthesis requests
must never hit the engine twice, and the cache layout must be stable so a
persistent volume can be reused across deployments.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from fastapi import Depends

from app.config import Settings, get_settings
from app.utils import canonical_json, sha256_hex

_SUFFIX = ".ogg"
_SHARD_LEN = 2


class Cache:
    """Store OGG audio files addressed by a SHA-256 of their synthesis inputs.

    Files live under ``<root>/<first two hex chars>/<full hash>.ogg``. The text
    is never used as a filename.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_key(*, engine: str, voice: str, mode: str, text: str) -> str:
        """Return the SHA-256 cache key for a set of synthesis parameters.

        Any change to ``engine``, ``voice``, ``mode`` or ``text`` yields a new
        key and therefore a new cache entry.
        """
        payload = canonical_json({"engine": engine, "voice": voice, "mode": mode, "text": text})
        return sha256_hex(payload)

    def path_for(self, key: str) -> Path:
        """Return the on-disk path for a cache key (no I/O)."""
        return self.root / key[:_SHARD_LEN] / f"{key}{_SUFFIX}"

    def get(self, key: str) -> bytes | None:
        """Return cached audio bytes, or ``None`` on a cache miss."""
        path = self.path_for(key)
        if not path.is_file():
            return None
        return path.read_bytes()

    def put(self, key: str, data: bytes) -> Path:
        """Atomically store audio bytes for a key and return the final path.

        The write goes to a temp file in the same shard directory and is then
        renamed into place, so a concurrent reader never sees a partial file.
        """
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp_name, path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp_name)
            raise
        return path


def get_cache(settings: Settings = Depends(get_settings)) -> Cache:
    """FastAPI dependency returning a :class:`Cache` for the active settings."""
    return Cache(settings.cache_dir)
