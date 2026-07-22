"""Spoken measurement wording, shared by the settings layer and the trip sim.

A leaf module on purpose: ``settings`` and ``sim.trip`` cannot import each
other (settings reaches the models package, which loads the sim package), so
the one pluralization rule for spoken distances lives here where both can
reach it.
"""

from __future__ import annotations


def spoken_distance(value: float, unit: str) -> str:
    """A whole-number distance with the unit pluralized for speech, so a
    screen reader never hears "in 1 miles"."""
    rounded = round(value)
    return f"{rounded:.0f} {unit if rounded == 1 else unit + 's'}"
