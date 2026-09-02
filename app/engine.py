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

import numpy as np
from fastapi import Depends

from app.config import Settings, get_settings

_SAMPLE_RATE = 24_000

# Waveform clean-up tuned for Kokoro's 24 kHz output.
_SILENCE_THRESHOLD = 0.01  # |sample| at or below this counts as silence
_EDGE_MARGIN = 240  # keep ~10 ms of context around trimmed edges
_FADE_LEN = 360  # ~15 ms linear fade applied to both ends


def _finalize_waveform(audio: np.ndarray) -> np.ndarray:
    """Clean up a raw Kokoro waveform before encoding.

    Guards against clipping, trims the near-silent head and tail (keeping a
    small margin), and applies a short linear fade in/out so the clip does not
    end on a hard sample discontinuity, which is audible as a click.
    """
    audio = np.asarray(audio, dtype="float32").reshape(-1)
    if audio.size == 0:
        return audio

    peak = float(np.max(np.abs(audio)))
    if peak > 1.0:
        audio = audio / peak

    voiced = np.flatnonzero(np.abs(audio) > _SILENCE_THRESHOLD)
    if voiced.size:
        start = max(0, int(voiced[0]) - _EDGE_MARGIN)
        stop = min(audio.size, int(voiced[-1]) + 1 + _EDGE_MARGIN)
        audio = audio[start:stop]

    ramp = min(_FADE_LEN, audio.size // 2)
    if ramp:
        window = np.linspace(0.0, 1.0, ramp, dtype="float32")
        audio = audio.copy()
        audio[:ramp] *= window
        audio[-ramp:] *= window[::-1]

    return audio


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
        """Lazily construct and cache the Kokoro pipeline.

        The import is deferred so that importing this module (and building the
        FastAPI app in tests) does not pull in torch or trigger a model load.
        """
        if self._pipeline is None:
            from kokoro import KPipeline

            self._pipeline = KPipeline(lang_code=self._lang_code, repo_id=self._repo_id)
        return self._pipeline

    def synthesize(self, text: str, voice: str, speed: float) -> bytes:
        """Run Kokoro, clean up the waveform, and encode it to OGG/Vorbis."""
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
        audio = _finalize_waveform(audio)
        if audio.size == 0:
            raise RuntimeError("kokoro produced only silence for the given input")

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
