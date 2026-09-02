"""Speech modes and their internal prosody configuration.

The public API never accepts a raw speed or prosody value. Callers pick a
*mode* that describes the pedagogical intent ("this is a single letter", "this
is an instruction sentence") and the service maps that to concrete synthesis
parameters here. This keeps the contract stable while leaving us free to tune
the numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SpeechMode(StrEnum):
    """Supported speaking modes exposed by the API."""

    PHONEME = "phoneme"
    LETTER = "letter"
    SYLLABLE = "syllable"
    WORD = "word"
    INSTRUCTION = "instruction"
    FEEDBACK = "feedback"


@dataclass(frozen=True, slots=True)
class ModeConfig:
    """Internal synthesis parameters for a single speaking mode."""

    speed: float
    description: str


_MODE_CONFIGS: dict[SpeechMode, ModeConfig] = {
    SpeechMode.PHONEME: ModeConfig(
        speed=0.70,
        description="Isolated phoneme: very slow and heavily articulated.",
    ),
    SpeechMode.LETTER: ModeConfig(
        speed=0.80,
        description="Single letter name: slow and clear.",
    ),
    SpeechMode.SYLLABLE: ModeConfig(
        speed=0.85,
        description="Single syllable: slightly slower than natural.",
    ),
    SpeechMode.WORD: ModeConfig(
        speed=0.95,
        description="Single word: near-natural pace.",
    ),
    SpeechMode.INSTRUCTION: ModeConfig(
        speed=1.00,
        description="Full instruction sentence: natural pace.",
    ),
    SpeechMode.FEEDBACK: ModeConfig(
        speed=1.02,
        description="Encouraging feedback: natural, slightly lively pace.",
    ),
}


def get_mode_config(mode: SpeechMode) -> ModeConfig:
    """Return the internal configuration for a speaking mode."""
    return _MODE_CONFIGS[mode]
