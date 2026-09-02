import numpy as np

from app.engine import _finalize_waveform


def test_clipping_is_guarded() -> None:
    loud = np.full(2_000, 2.5, dtype="float32")

    out = _finalize_waveform(loud)

    assert float(np.max(np.abs(out))) <= 1.0


def test_trailing_silence_is_trimmed() -> None:
    voiced = np.full(1_000, 0.5, dtype="float32")
    silence = np.zeros(20_000, dtype="float32")
    raw = np.concatenate([voiced, silence])

    out = _finalize_waveform(raw)

    # Voiced part (plus a small margin) is kept; the long silent tail is gone.
    assert 1_000 <= out.size < raw.size
    assert out.size < 1_000 + 4 * 240


def test_fade_removes_hard_edges() -> None:
    raw = np.full(5_000, 0.8, dtype="float32")

    out = _finalize_waveform(raw)

    assert out[0] == 0.0
    assert out[-1] == 0.0
    # ...but the middle is untouched.
    assert out[out.size // 2] == np.float32(0.8)


def test_empty_input_returns_empty() -> None:
    assert _finalize_waveform(np.zeros(0, dtype="float32")).size == 0
