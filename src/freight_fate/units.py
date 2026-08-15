"""Spoken measurement wording, shared by the settings layer and the trip sim.

A leaf module on purpose: ``settings`` and ``sim.trip`` cannot import each
other (settings reaches the models package, which loads the sim package), so
the one pluralization rule for spoken distances lives here where both can
reach it.
"""

from __future__ import annotations

MILES_TO_KM = 1.609344


def spoken_distance(value: float, unit: str) -> str:
    """A whole-number distance with the unit pluralized for speech, so a
    screen reader never hears "in 1 miles"."""
    rounded = round(value)
    return f"{rounded:.0f} {unit if rounded == 1 else unit + 's'}"


def to_distance(miles: float, imperial: bool) -> float:
    """An internal mileage as the number the player's unit setting asks for.

    The sim measures everything in miles; this is the single conversion the
    readouts go through, so a metric player never hears one screen's
    kilometers next to another screen's raw miles.
    """
    return miles if imperial else miles * MILES_TO_KM


def distance_unit(imperial: bool, *, plural: bool = True) -> str:
    """The spoken name of the player's distance unit."""
    unit = "mile" if imperial else "kilometer"
    return unit + "s" if plural else unit


def spoken_feet_or_meters(miles: float, imperial: bool) -> str:
    """A very short distance in round feet or meters, never decimals.

    The last few hundred of them before a stop bar, a gate, or a turn, where
    every miles-based wording in the game has already bottomed out: 50-foot
    steps down to 50 feet, 20-meter steps down to 20 meters.
    """
    if imperial:
        feet = max(50, int(round(miles * 5280.0 / 50.0)) * 50)
        return f"{feet} feet"
    meters = max(20, int(round(miles * MILES_TO_KM * 1000.0 / 20.0)) * 20)
    return f"{meters} meters"


def spoken_gap(miles: float, imperial: bool) -> str:
    """A one-decimal distance, for cues close enough that rounding to whole
    units would hide the gap being announced."""
    return f"{to_distance(miles, imperial):.1f} {distance_unit(imperial)}"


def hud_speed(mph: float, imperial: bool) -> str:
    """Speed for the visual HUD, in the short written form."""
    return f"{mph:.0f} mph" if imperial else f"{to_distance(mph, imperial):.0f} km/h"
