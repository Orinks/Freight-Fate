"""Mode-specific driving pressure without removing truck mechanics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DrivingModeTuning:
    name: str
    hazard_frequency: float
    reaction_window: float
    collision_damage: float
    fatigue_rate: float
    ambient_spacing_s: float
    routine_speech_interval_s: float


_MODES = {
    10.0: DrivingModeTuning("relaxed", 0.55, 1.5, 0.6, 0.8, 5.0, 18.0),
    20.0: DrivingModeTuning("standard", 1.0, 1.0, 1.0, 1.0, 2.5, 12.0),
    40.0: DrivingModeTuning("realistic", 1.0, 1.0, 1.0, 1.0, 2.5, 12.0),
}


def tuning_for_time_scale(time_scale: float) -> DrivingModeTuning:
    """Return deterministic tuning, defaulting custom scales to Standard."""
    return _MODES.get(float(time_scale), _MODES[20.0])


def mode_name(time_scale: float) -> str:
    return tuning_for_time_scale(time_scale).name
