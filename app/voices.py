"""Public Aurora voice registry.

The API exposes a small, stable set of Aurora-branded voice ids. Each one maps
internally to an engine-native voice. That mapping is an implementation detail
and is never returned by the API, so the underlying engine can be swapped
without changing the public contract.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Voice:
    """A public Aurora voice and its engine-native counterpart."""

    id: str
    description: str
    engine_voice: str


_VOICES: dict[str, Voice] = {
    "teacher_female_v1": Voice(
        id="teacher_female_v1",
        description="Voz principal da alfabetização",
        engine_voice="pf_dora",
    ),
    "teacher_male_v1": Voice(
        id="teacher_male_v1",
        description="Voz masculina",
        engine_voice="pm_alex",
    ),
    "mascot_v1": Voice(
        id="mascot_v1",
        description="Mascote Aurora",
        engine_voice="pm_santa",
    ),
}


def all_voice_ids() -> list[str]:
    """Return every registered public voice id."""
    return list(_VOICES)


def is_valid_voice(voice_id: str) -> bool:
    """Return whether ``voice_id`` is a registered public voice."""
    return voice_id in _VOICES


def get_voice(voice_id: str) -> Voice:
    """Return the registered :class:`Voice` or raise :class:`KeyError`."""
    return _VOICES[voice_id]


def resolve_engine_voice(voice_id: str) -> str:
    """Return the engine-native voice name for a public voice id."""
    return _VOICES[voice_id].engine_voice


def public_voices() -> list[dict[str, str]]:
    """Return the public voice catalogue (``id`` and ``description`` only)."""
    return [{"id": v.id, "description": v.description} for v in _VOICES.values()]
