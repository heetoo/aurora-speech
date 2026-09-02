import pytest
from fastapi.testclient import TestClient

from app.modes import SpeechMode
from app.schemas import SynthesizeRequest
from tests.conftest import StubEngine


def test_synthesize_miss_then_hit(client: TestClient, stub_engine: StubEngine) -> None:
    payload = {"text": "bola", "voice": "teacher_female_v1", "mode": "word"}

    first = client.post("/v1/synthesize", json=payload)

    assert first.status_code == 200
    assert first.headers["content-type"] == "audio/ogg"
    assert first.headers["x-cache"] == "MISS"
    assert len(first.headers["x-cache-key"]) == 64
    assert int(first.headers["x-duration-ms"]) >= 0
    assert first.content[:4] == b"OggS"
    assert len(stub_engine.calls) == 1

    key = first.headers["x-cache-key"]
    second = client.post("/v1/synthesize", json=payload)

    assert second.status_code == 200
    assert second.headers["x-cache"] == "HIT"
    assert second.headers["x-cache-key"] == key
    assert second.content == first.content
    # Engine was not invoked again.
    assert len(stub_engine.calls) == 1


def test_defaults_are_applied(client: TestClient, stub_engine: StubEngine) -> None:
    response = client.post("/v1/synthesize", json={"text": "oi"})

    assert response.status_code == 200
    assert response.headers["x-cache"] == "MISS"
    _, voice, speed = stub_engine.calls[0]
    assert voice == "pf_dora"  # teacher_female_v1 -> engine voice
    assert speed == pytest.approx(0.95)  # word mode


def test_mode_changes_cache_key(client: TestClient) -> None:
    word = client.post("/v1/synthesize", json={"text": "bola", "mode": "word"})
    letter = client.post("/v1/synthesize", json={"text": "bola", "mode": "letter"})

    assert word.headers["x-cache-key"] != letter.headers["x-cache-key"]


@pytest.mark.parametrize(
    "body",
    [
        {"voice": "teacher_female_v1"},  # missing text
        {"text": ""},  # empty text
        {"text": "   "},  # blank text
        {"text": "a" * 501},  # too long
        {"text": "bola", "voice": "hacker_v1"},  # unknown voice
        {"text": "bola", "mode": "singing"},  # unknown mode
    ],
)
def test_invalid_requests_return_422(client: TestClient, body: dict[str, str]) -> None:
    response = client.post("/v1/synthesize", json=body)

    assert response.status_code == 422


def test_pydantic_model_directly() -> None:
    request = SynthesizeRequest(text="  bola  ")

    assert request.text == "bola"
    assert request.voice == "teacher_female_v1"
    assert request.mode is SpeechMode.WORD

    with pytest.raises(ValueError):
        SynthesizeRequest(text="bola", voice="nope")

    with pytest.raises(ValueError):
        SynthesizeRequest(text="   ")
