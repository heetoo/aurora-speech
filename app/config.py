"""Application configuration, loaded from environment variables and ``.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the Aurora Speech service.

    Every field maps to an environment variable of the same name (case
    insensitive). See ``.env.example`` for the supported keys.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Aurora Speech")
    app_version: str = Field(default="1.0.0")

    # Where synthesized audio is cached. In the container this is always
    # ``/app/cache`` (set via the Dockerfile) and bind-mounted to a persistent
    # volume. Locally it defaults to a relative ``./cache`` directory.
    cache_dir: Path = Field(default=Path("cache"))

    # Logical engine identifier. Part of the cache key, so bumping it
    # transparently invalidates every previously cached file. Bump it whenever a
    # change alters the audio output (engine, voices, or the post-processing
    # below). ``v2`` = adds the trailing-hiss clean-up (HF de-emphasis, long
    # fade-out, tail noise gate).
    engine_name: str = Field(default="kokoro-82m-v2")
    default_voice: str = Field(default="teacher_female_v1")

    # Fixed language contract. This service is pt-BR only.
    language: str = Field(default="pt-BR")
    kokoro_lang_code: str = Field(default="p")
    kokoro_repo_id: str = Field(default="hexgrad/Kokoro-82M")

    # Waveform post-processing applied before encoding, to tame the trailing
    # breath/hiss the pt-BR Kokoro voices append (see scratch/FINDINGS.md).
    audio_lowpass_hz: int = Field(default=3500)  # one-pole HF de-emphasis; 0 = off
    audio_fade_in_ms: int = Field(default=10)
    audio_fade_out_ms: int = Field(default=200)  # raised-cosine fade-out; 0 = off
    audio_gate_enabled: bool = Field(default=True)  # trailing noise gate
    audio_gate_floor_db: float = Field(default=-30.0)  # RMS below this is ramped out

    # Maximum accepted input length, in characters.
    max_text_length: int = Field(default=500)

    # When true, the Kokoro model is loaded during application startup so the
    # first request does not pay the cold-start cost. Disabled by default (and
    # in tests) to keep startup cheap.
    eager_engine_init: bool = Field(default=False)

    # Error tracking. Sentry is only initialised when ``sentry_dsn`` is set, so
    # local runs and tests never send anything. ``app_git_sha`` is injected at
    # image build time and becomes the Sentry release.
    sentry_dsn: str | None = Field(default=None)
    sentry_environment: str = Field(default="production")
    sentry_traces_sample_rate: float = Field(default=0.05)
    app_git_sha: str = Field(default="dev")


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance."""
    return Settings()
