"""Shared pytest fixtures.

The real Kokoro engine is never loaded in tests. A lightweight stub produces a
valid short OGG file so the HTTP layer, headers and cache can be exercised for
real.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.engine import SpeechEngine, get_engine
from app.main import create_app

_SAMPLE_RATE = 24_000


class StubEngine(SpeechEngine):
    """Deterministic fake engine that returns a real short OGG file."""

    name = "kokoro-82m-v1"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []

    def synthesize(self, text: str, voice: str, speed: float) -> bytes:
        self.calls.append((text, voice, speed))
        samples = int(_SAMPLE_RATE * 0.2)
        tone = 0.05 * np.sin(2 * np.pi * 220 * np.arange(samples) / _SAMPLE_RATE)
        buffer = io.BytesIO()
        sf.write(buffer, tone.astype("float32"), _SAMPLE_RATE, format="OGG", subtype="VORBIS")
        return buffer.getvalue()


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    path = tmp_path / "cache"
    path.mkdir()
    return path


@pytest.fixture
def stub_engine() -> StubEngine:
    return StubEngine()


@pytest.fixture
def client(cache_dir: Path, stub_engine: StubEngine) -> Iterator[TestClient]:
    settings = Settings(cache_dir=cache_dir, eager_engine_init=False)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_engine] = lambda: stub_engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
