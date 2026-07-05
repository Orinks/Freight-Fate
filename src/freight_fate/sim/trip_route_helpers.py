# ruff: noqa: F403,F405
from __future__ import annotations

import math
import re

from ..data.world import get_world
from .trip_models import Zone


def _stop_offset_for_direction(at_mi: float, leg_miles: float, forward: bool) -> float:
    return at_mi if forward else leg_miles - at_mi


def _leg_heading(highway: str, from_city: str, to_city: str) -> str:
    """Signed heading for onramp/merge framing ("Merge onto I-95 South...").

    Uses the US route-numbering convention -- odd routes are signed
    north/south, even routes east/west -- so the spoken direction matches real
    signage even where a leg runs diagonally (I-95 NY->Philadelphia is signed
    South though the geometry trends southwest). The sign comes from the
    endpoints' coordinates on the route's primary axis. Empty when the highway
    has no number or a city lacks coordinates."""
    match = re.search(r"\d+", highway)
    if not match:
        return ""
    cities = get_world().cities
    a, b = cities.get(from_city), cities.get(to_city)
    if a is None or b is None or (a.lat == 0.0 and a.lon == 0.0):
        return ""
    if int(match.group()) % 2 == 1:  # odd -> north/south route
        return "North" if b.lat >= a.lat else "South"
    return "East" if b.lon >= a.lon else "West"  # even -> east/west route


def _nearest_exit_label(leg, at_mi: float, tol_mi: float = 2.0) -> str:
    """Signed exit label of the interchange nearest a stop on the same leg, in
    the leg's native (a->b) frame. Empty when none is within ``tol_mi`` or the
    nearest junction carries no exit number -- stops then keep generic wording."""
    best_label = ""
    best_dist = tol_mi
    for ix in leg.interchanges:
        dist = abs(ix.at_mi - at_mi)
        if dist <= best_dist and ix.exit_label:
            best_dist = dist
            best_label = ix.exit_label
    return best_label


def _zone_key(zone: Zone) -> str:
    # Keyed by place and reason only: a congestion zone's limit_mph is the
    # live traffic speed and changes with the clock, and a re-keyed zone
    # would re-announce itself every time the jam deepened a notch.
    return f"{zone.reason}:{zone.start_mi:.3f}:{zone.end_mi:.3f}"


def _fallback_grade(terrain: str, mile: float, highway: str) -> float:
    """Auditable fallback for legs without elevation samples.

    Flat roads stay level. Hills and mountains get a small deterministic profile
    from the curated terrain label, but corridor metadata should replace this
    as routes are enriched.
    """
    amplitude = {"flat": 0.0, "hills": 0.012, "mountain": 0.035}.get(terrain, 0.0)
    if amplitude == 0.0:
        return 0.0
    wavelength = {"hills": 14.0, "mountain": 8.0}.get(terrain, 16.0)
    phase = (sum(ord(ch) for ch in highway) % 628) / 100.0
    return amplitude * math.sin(2 * math.pi * mile / wavelength + phase)


__all__ = [name for name in globals() if not name.startswith("__")]
