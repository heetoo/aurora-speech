from pathlib import Path

from app.cache import Cache

_BASE = dict(engine="kokoro-82m-v2", voice="teacher_female_v1", mode="word", text="bola")


def test_key_is_deterministic() -> None:
    first = Cache.compute_key(**_BASE)
    second = Cache.compute_key(**_BASE)

    assert first == second
    assert len(first) == 64
    assert first.islower()


def test_key_changes_with_any_field() -> None:
    base = Cache.compute_key(**_BASE)

    assert base != Cache.compute_key(**{**_BASE, "engine": "other-engine"})
    assert base != Cache.compute_key(**{**_BASE, "voice": "teacher_male_v1"})
    assert base != Cache.compute_key(**{**_BASE, "mode": "letter"})
    assert base != Cache.compute_key(**{**_BASE, "text": "casa"})


def test_shard_layout_and_roundtrip(tmp_path: Path) -> None:
    cache = Cache(tmp_path)
    key = "ab" + "0" * 62

    path = cache.put(key, b"audio-bytes")

    assert path == tmp_path / "ab" / f"{key}.ogg"
    assert path.read_bytes() == b"audio-bytes"
    assert cache.get(key) == b"audio-bytes"


def test_get_returns_none_on_miss(tmp_path: Path) -> None:
    cache = Cache(tmp_path)

    assert cache.get("f" * 64) is None


def test_text_is_never_used_as_filename(tmp_path: Path) -> None:
    cache = Cache(tmp_path)
    key = Cache.compute_key(**_BASE)

    cache.put(key, b"x")

    stored = list(tmp_path.rglob("*.ogg"))
    assert len(stored) == 1
    assert "bola" not in str(stored[0])
