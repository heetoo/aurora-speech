"""Speech engine abstraction and the local Kokoro implementation.

The rest of the app only depends on :class:`SpeechEngine`. Swapping Kokoro for
another local engine means adding one subclass and changing
:func:`build_engine`; the public HTTP API does not change.
"""

from __future__ import annotations

import io
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from fastapi import Depends

from app.config import Settings, get_settings

_SAMPLE_RATE = 24_000


class SpeechEngine(ABC):
    """Abstract text-to-speech engine that returns OGG/Vorbis audio bytes."""

    name: str

    @abstractmethod
    def synthesize(self, text: str, voice: str, speed: float) -> bytes:
        """Synthesize ``text`` with an engine-native ``voice`` at ``speed``.

        Returns a complete OGG/Vorbis file as bytes.
        """


class KokoroEngine(SpeechEngine):
    """Kokoro-82M engine, running fully locally with no external services."""

    def __init__(self, name: str, lang_code: str, repo_id: str) -> None:
        self.name = name
        self._lang_code = lang_code
        self._repo_id = repo_id
        self._pipeline: Any | None = None

    def _get_pipeline(self) -> Any:
        """Lazily construct and cache the Kokoro pipeline."""
        if self._pipeline is None:
            from kokoro import KPipeline

            self._pipeline = KPipeline(lang_code=self._lang_code, repo_id=self._repo_id)
        return self._pipeline

    def synthesize(self, text: str, voice: str, speed: float) -> bytes:
        """Run Kokoro and encode the waveform to OGG/Vorbis."""
        import numpy as np
        import soundfile as sf

        pipeline = self._get_pipeline()

        segments: list[Any] = []
        for item in pipeline(text, voice=voice, speed=speed):
            audio_part = getattr(item, "audio", None)
            if audio_part is None:
                # Legacy Kokoro yields (graphemes, phonemes, audio) tuples.
                audio_part = item[2]
            if hasattr(audio_part, "detach"):
                audio_part = audio_part.detach().cpu().numpy()
            segments.append(np.asarray(audio_part, dtype="float32"))

        if not segments:
            raise RuntimeError("kokoro produced no audio for the given input")

        audio = segments[0] if len(segments) == 1 else np.concatenate(segments)

        buffer = io.BytesIO()
        sf.write(buffer, audio, _SAMPLE_RATE, format="OGG", subtype="VORBIS")
        return buffer.getvalue()

    def warm_up(self) -> None:
        """Eagerly load the model so the first request does not pay cold start."""
        self._get_pipeline()


@lru_cache(maxsize=4)
def _build_kokoro_engine(name: str, lang_code: str, repo_id: str) -> KokoroEngine:
    return KokoroEngine(name=name, lang_code=lang_code, repo_id=repo_id)


def build_engine(settings: Settings) -> SpeechEngine:
    """Return a cached engine instance for the given settings."""
    return _build_kokoro_engine(
        settings.engine_name,
        settings.kokoro_lang_code,
        settings.kokoro_repo_id,
    )


def get_engine(settings: Settings = Depends(get_settings)) -> SpeechEngine:
    """FastAPI dependency returning the active :class:`SpeechEngine`."""
    return build_engine(settings)
