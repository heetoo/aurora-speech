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


def _one_pole_lowpass(audio: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    """Apply a gentle first-order low-pass (high-frequency de-emphasis).

    Implemented as an exponentially decaying FIR, which is the exact one-pole
    IIR step response (zero initial state) truncated where the tap weight falls
    below 1e-6. Vectorised; no SciPy dependency.
    """
    alpha = 1.0 - float(np.exp(-2.0 * np.pi * cutoff_hz / sample_rate))
    if alpha <= 0.0 or alpha >= 1.0:
        return audio
    taps = int(np.ceil(np.log(1e-6) / np.log(1.0 - alpha)))
    taps = max(1, min(taps, 2048))
    kernel = alpha * (1.0 - alpha) ** np.arange(taps, dtype="float64")
    return np.convolve(audio.astype("float64"), kernel)[: audio.size].astype("float32")


def _finalize_waveform(
    audio: np.ndarray,
    *,
    sample_rate: int = _SAMPLE_RATE,
    lowpass_hz: float = 6000.0,
    fade_in_ms: float = 10.0,
    fade_out_ms: float = 120.0,
) -> np.ndarray:
    """Clean up a raw Kokoro waveform before encoding.

    Steps: guard against clipping, trim the near-silent head/tail (keeping a
    small margin), apply a one-pole HF de-emphasis, then a short fade-in and a
    long raised-cosine fade-out. The last two stages tame the trailing
    breath/hiss the pt-BR Kokoro voices append (see ``scratch/FINDINGS.md``);
    pass ``lowpass_hz=0`` or ``fade_out_ms=0`` to skip them.
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

    if lowpass_hz and lowpass_hz > 0:
        audio = _one_pole_lowpass(audio, sample_rate, lowpass_hz)

    audio = audio.copy()
    n_in = min(int(fade_in_ms * sample_rate / 1000), audio.size // 2)
    if n_in > 0:
        audio[:n_in] *= np.linspace(0.0, 1.0, n_in, dtype="float32")
    n_out = min(int(fade_out_ms * sample_rate / 1000), audio.size)
    if n_out > 0:
        t = np.linspace(0.0, 1.0, n_out, dtype="float32")
        audio[-n_out:] *= (0.5 * (1.0 + np.cos(np.pi * t))).astype("float32")

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

    def __init__(
        self,
        name: str,
        lang_code: str,
        repo_id: str,
        *,
        lowpass_hz: float = 0.0,
        fade_in_ms: float = 10.0,
        fade_out_ms: float = 15.0,
    ) -> None:
        self.name = name
        self._lang_code = lang_code
        self._repo_id = repo_id
        self._lowpass_hz = lowpass_hz
        self._fade_in_ms = fade_in_ms
        self._fade_out_ms = fade_out_ms
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
        audio = _finalize_waveform(
            audio,
            sample_rate=_SAMPLE_RATE,
            lowpass_hz=self._lowpass_hz,
            fade_in_ms=self._fade_in_ms,
            fade_out_ms=self._fade_out_ms,
        )
        if audio.size == 0:
            raise RuntimeError("kokoro produced only silence for the given input")

        buffer = io.BytesIO()
        sf.write(buffer, audio, _SAMPLE_RATE, format="OGG", subtype="VORBIS")
        return buffer.getvalue()

    def warm_up(self) -> None:
        """Eagerly load the model so the first request does not pay cold start."""
        self._get_pipeline()


@lru_cache(maxsize=4)
def _build_kokoro_engine(
    name: str,
    lang_code: str,
    repo_id: str,
    lowpass_hz: float,
    fade_in_ms: float,
    fade_out_ms: float,
) -> KokoroEngine:
    return KokoroEngine(
        name,
        lang_code,
        repo_id,
        lowpass_hz=lowpass_hz,
        fade_in_ms=fade_in_ms,
        fade_out_ms=fade_out_ms,
    )


def build_engine(settings: Settings) -> SpeechEngine:
    """Return a cached engine instance for the given settings."""
    return _build_kokoro_engine(
        settings.engine_name,
        settings.kokoro_lang_code,
        settings.kokoro_repo_id,
        float(settings.audio_lowpass_hz),
        float(settings.audio_fade_in_ms),
        float(settings.audio_fade_out_ms),
    )


def get_engine(settings: Settings = Depends(get_settings)) -> SpeechEngine:
    """FastAPI dependency returning the active :class:`SpeechEngine`."""
    return build_engine(settings)
