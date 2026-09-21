"""Lazy per-leg corridor parsing for the world data layer.

``World.__init__`` used to build every leg's heavy per-mile detail (grades,
interchanges, landmarks, posted limits, state crossings, ...) for all fifty
states at startup, even though the route graph and dispatch never read any of
it -- roughly a second of pure latency before the menu. ``LazyLeg`` defers that
work to the first time a leg is driven; this module holds the two pieces of
that deferral that lean on the parse helpers:

* :func:`raw_metadata_complete` -- ``Leg.metadata_complete`` computed from raw
  corridor counts, so the route graph can gate dispatch without a parse.
* :func:`build_leg_corridor` -- the full parse of a single leg's corridor,
  byte-identical to the old eager construction.

Kept separate from ``world_parsing`` only to keep that module under the
1000-line ceiling; it depends on the ``_parse_*`` helpers that still live
there and that tests import from there.
"""

from __future__ import annotations

from .grades import screen_grade_segments
from .world_constants import LIMIT_EXPLAINING_CATEGORIES
from .world_parsing import (
    _parse_checkpoint,
    _parse_elevation_sample,
    _parse_grade_segment,
    _parse_hpms_terrain,
    _parse_interchange,
    _parse_landmarks,
    _parse_lane_segments,
    _parse_restrictions,
    _parse_route_point,
    _parse_speed_limits,
    _parse_state_crossing,
    _parse_state_mileage,
    _parse_toll_event,
    _parse_traffic_volumes,
)


def raw_metadata_complete(corridor: dict, from_state: str, to_state: str) -> bool:
    """``Leg.metadata_complete`` computed from raw corridor counts.

    The five fields dispatch gates on (route points, elevation samples, grade
    segments, state miles, state crossings) all parse one-for-one with no
    filtering, so counting the raw lists is byte-identical to constructing the
    leg and asking. That lets startup bake this flag without parsing the heavy
    per-mile detail, which ``LazyLeg`` then defers until a leg is driven."""
    if len(corridor.get("route_points", ())) < 2:
        return False
    if not corridor.get("state_miles"):
        return False
    if len(corridor.get("elevation_samples", ())) < 2 or not corridor.get("grade_segments"):
        return False
    return from_state == to_state or bool(corridor.get("state_crossings"))


def build_leg_corridor(
    corridor: dict,
    miles: float,
    leg_from: str,
    leg_to: str,
    from_state: str,
    highway: str,
) -> dict:
    """Parse a leg's heavy per-mile corridor detail into model tuples.

    Split out of ``World.__init__`` so ``LazyLeg`` can defer this work until a
    leg is actually driven: the route graph and dispatch never read these
    fields, so parsing all fifty states' worth at startup was pure latency.
    The result is byte-identical to the old eager construction -- same inputs,
    same parse, same order.
    """
    route_points = tuple(
        _parse_route_point(p, miles, leg_from, leg_to) for p in corridor.get("route_points", ())
    )
    elevation_samples = tuple(
        _parse_elevation_sample(s, miles, leg_from, leg_to)
        for s in corridor.get("elevation_samples", ())
    )
    # Screened on the way in: the elevation profile the grades were baked from
    # reads bridge decks as road, which put slopes on the map that no highway
    # of their class can hold. See ``grades.py`` -- the bake itself is left
    # untouched and a capped segment says so in its own source string.
    hpms_terrain = _parse_hpms_terrain(corridor.get("hpms_terrain"), leg_from, leg_to)
    grade_segments = screen_grade_segments(
        tuple(
            _parse_grade_segment(s, miles, leg_from, leg_to)
            for s in corridor.get("grade_segments", ())
        ),
        highway,
        hpms_terrain.type if hpms_terrain else None,
    )
    lane_segments = _parse_lane_segments(corridor.get("lane_segments", ()), miles, leg_from, leg_to)
    state_crossings = tuple(
        _parse_state_crossing(c, miles, leg_from, leg_to, from_state)
        for c in corridor.get("state_crossings", ())
    )
    checkpoints = tuple(
        _parse_checkpoint(c, miles, leg_from, leg_to) for c in corridor.get("checkpoints", ())
    )
    state_miles = tuple(
        _parse_state_mileage(m, leg_from, leg_to) for m in corridor.get("state_miles", ())
    )
    toll_events = tuple(
        _parse_toll_event(e, miles, leg_from, leg_to, highway)
        for e in corridor.get("toll_events", ())
    )
    interchanges = tuple(
        _parse_interchange(x, miles, leg_from, leg_to, highway)
        for x in corridor.get("interchanges", ())
    )
    traffic_volumes = _parse_traffic_volumes(
        corridor.get("traffic_aadt", ()), miles, leg_from, leg_to
    )
    landmarks = _parse_landmarks(corridor.get("landmarks", ()), miles, leg_from, leg_to)
    # Landmarks first: the dwell filter keeps a short posting that a place on
    # the road explains, and drops the ones nothing does.
    speed_limits = _parse_speed_limits(
        corridor.get("speed_limits", ()),
        miles,
        leg_from,
        leg_to,
        places=tuple(lm.at_mi for lm in landmarks if lm.category in LIMIT_EXPLAINING_CATEGORIES),
    )
    restrictions = _parse_restrictions(corridor.get("restrictions", ()), miles, leg_from, leg_to)
    return {
        "route_points": route_points,
        "elevation_samples": elevation_samples,
        "grade_segments": grade_segments,
        "state_crossings": state_crossings,
        "checkpoints": checkpoints,
        "state_miles": state_miles,
        "toll_events": toll_events,
        "interchanges": interchanges,
        "speed_limits": speed_limits,
        "traffic_volumes": traffic_volumes,
        "hpms_terrain": hpms_terrain,
        "landmarks": landmarks,
        "restrictions": restrictions,
        "lane_segments": lane_segments,
    }
