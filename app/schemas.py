"""Pydantic request and response models for the public API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.modes import SpeechMode
from app.voices import is_valid_voice

MAX_TEXT_LENGTH = 500


class SynthesizeRequest(BaseModel):
    """Body of ``POST /v1/synthesize``."""

    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    voice: str = Field(default="teacher_female_v1")
    mode: SpeechMode = Field(default=SpeechMode.WORD)

    @field_validator("text")
    @classmethod
    def _strip_and_check_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be blank")
        return stripped

    @field_validator("voice")
    @classmethod
    def _check_voice(cls, value: str) -> str:
        if not is_valid_voice(value):
            raise ValueError(f"unknown voice: {value!r}")
        return value


class HealthResponse(BaseModel):
    """Body of ``GET /health``."""

    status: str
    engine: str
    version: str


class VoiceInfo(BaseModel):
    """A single public voice entry."""

    id: str
    description: str


class VoicesResponse(BaseModel):
    """Body of ``GET /voices``."""

    voices: list[VoiceInfo]
