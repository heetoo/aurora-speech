import numpy as np
import pytest

from app.engine import _finalize_waveform

SR = 24_000
_DRY = dict(lowpass_hz=0, fade_in_ms=0, fade_out_ms=0)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x.astype("float64") ** 2)))


def _tail_energy(x: np.ndarray, ms: int = 100) -> float:
    n = int(ms * SR / 1000)
    return float(np.sum(x.astype("float64")[-n:] ** 2))


def test_clipping_is_guarded() -> None:
    loud = np.full(4_000, 2.5, dtype="float32")

    out = _finalize_waveform(loud, **_DRY)

    assert float(np.max(np.abs(out))) <= 1.0


def test_trailing_silence_is_trimmed() -> None:
    voiced = np.full(1_000, 0.5, dtype="float32")
    silence = np.zeros(20_000, dtype="float32")
    raw = np.concatenate([voiced, silence])

    out = _finalize_waveform(raw, **_DRY)

    # Voiced part (plus a small margin) is kept; the long silent tail is gone.
    assert 1_000 <= out.size < raw.size
    assert out.size < 1_000 + 4 * 240


def test_fade_removes_hard_edges() -> None:
    raw = np.full(SR, 0.8, dtype="float32")  # 1 s, longer than any fade

    out = _finalize_waveform(raw, lowpass_hz=0, fade_in_ms=10, fade_out_ms=120)

    assert out[0] == 0.0
    assert out[-1] == 0.0
    # The body between the fades is untouched.
    assert out[out.size // 2] == pytest.approx(0.8, abs=2e-3)


def test_fades_can_be_disabled() -> None:
    raw = np.full(5_000, 0.5, dtype="float32")

    out = _finalize_waveform(raw, **_DRY)

    assert out[0] == pytest.approx(0.5)
    assert out[-1] == pytest.approx(0.5)


def test_lowpass_attenuates_high_frequencies() -> None:
    t = np.arange(int(0.2 * SR)) / SR
    tone_9k = np.sin(2 * np.pi * 9_000 * t).astype("float32")

    dry = _finalize_waveform(tone_9k, lowpass_hz=0, fade_in_ms=0, fade_out_ms=0)
    wet = _finalize_waveform(tone_9k, lowpass_hz=4_000, fade_in_ms=0, fade_out_ms=0)

    assert _rms(wet) < 0.6 * _rms(dry)


def test_longer_fade_out_lowers_tail_energy() -> None:
    raw = np.full(SR, 0.5, dtype="float32")

    short = _finalize_waveform(raw, lowpass_hz=0, fade_in_ms=0, fade_out_ms=15)
    long_ = _finalize_waveform(raw, lowpass_hz=0, fade_in_ms=0, fade_out_ms=120)

    assert _tail_energy(long_) < _tail_energy(short)


def test_empty_input_returns_empty() -> None:
    assert _finalize_waveform(np.zeros(0, dtype="float32")).size == 0
