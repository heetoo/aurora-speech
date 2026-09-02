from fastapi.testclient import TestClient


def test_voices_list(client: TestClient) -> None:
    response = client.get("/voices")

    assert response.status_code == 200
    voices = response.json()["voices"]
    ids = {entry["id"] for entry in voices}
    assert ids == {"teacher_female_v1", "teacher_male_v1", "mascot_v1"}
    for entry in voices:
        assert set(entry) == {"id", "description"}


def test_voices_do_not_leak_engine_names(client: TestClient) -> None:
    raw = client.get("/voices").text

    for internal_name in ("pf_dora", "pm_alex", "pm_santa", "kokoro"):
        assert internal_name not in raw
