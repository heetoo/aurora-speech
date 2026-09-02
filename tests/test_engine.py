import numpy as np
import pytest

from app.engine import _finalize_waveform

SR = 24_000


def _bare(
    x: np.ndarray,
    *,
    lowpass_hz: float = 0.0,
    fade_in_ms: float = 0.0,
    fade_out_ms: float = 0.0,
    gate_floor_db: float | None = None,
) -> np.ndarray:
    """``_finalize_waveform`` with every optional stage off unless overridden."""
    return _finalize_waveform(
        x,
        lowpass_hz=lowpass_hz,
        fade_in_ms=fade_in_ms,
        fade_out_ms=fade_out_ms,
        gate_floor_db=gate_floor_db,
    )


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x.astype("float64") ** 2)))


def _tail_energy(x: np.ndarray, ms: int = 100) -> float:
    n = int(ms * SR / 1000)
    return float(np.sum(x.astype("float64")[-n:] ** 2))


def test_clipping_is_guarded() -> None:
    out = _bare(np.full(4_000, 2.5, dtype="float32"))

    assert float(np.max(np.abs(out))) <= 1.0


def test_trailing_silence_is_trimmed() -> None:
    voiced = np.full(1_000, 0.5, dtype="float32")
    raw = np.concatenate([voiced, np.zeros(20_000, dtype="float32")])

    out = _bare(raw)

    assert 1_000 <= out.size < raw.size
    assert out.size < 1_000 + 4 * 240


def test_fade_removes_hard_edges() -> None:
    raw = np.full(SR, 0.8, dtype="float32")  # 1 s, longer than any fade

    out = _bare(raw, fade_in_ms=10, fade_out_ms=120)

    assert out[0] == 0.0
    assert out[-1] == 0.0
    assert out[out.size // 2] == pytest.approx(0.8, abs=2e-3)


def test_fades_can_be_disabled() -> None:
    out = _bare(np.full(5_000, 0.5, dtype="float32"))

    assert out[0] == pytest.approx(0.5)
    assert out[-1] == pytest.approx(0.5)


def test_lowpass_attenuates_high_frequencies() -> None:
    t = np.arange(int(0.2 * SR)) / SR
    tone_9k = np.sin(2 * np.pi * 9_000 * t).astype("float32")

    assert _rms(_bare(tone_9k, lowpass_hz=4_000)) < 0.6 * _rms(_bare(tone_9k))


def test_longer_fade_out_lowers_tail_energy() -> None:
    raw = np.full(SR, 0.5, dtype="float32")

    short = _bare(raw, fade_out_ms=15)
    long_ = _bare(raw, fade_out_ms=120)

    assert _tail_energy(long_) < _tail_energy(short)


def test_noise_gate_ramps_out_quiet_tail() -> None:
    body = np.full(int(0.3 * SR), 0.2, dtype="float32")  # ~ -14 dB, above floor
    hiss = (0.01 * np.random.default_rng(0).standard_normal(int(0.2 * SR))).astype("float32")
    raw = np.concatenate([body, hiss])

    gated = _bare(raw, gate_floor_db=-30.0)
    kept = _bare(raw)

    assert _tail_energy(gated, ms=150) < 0.2 * _tail_energy(kept, ms=150)
    assert gated[SR // 10] == pytest.approx(0.2, abs=1e-3)


def test_gate_leaves_loud_endings_alone() -> None:
    raw = np.full(int(0.4 * SR), 0.3, dtype="float32")  # ~ -10 dB everywhere

    assert _bare(raw, gate_floor_db=-30.0)[-1] == pytest.approx(0.3, abs=1e-3)


def test_empty_input_returns_empty() -> None:
    assert _finalize_waveform(np.zeros(0, dtype="float32")).size == 0
