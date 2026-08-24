"""The leg's real road, dense, for every builder that has been guessing at it.

WHAT WAS WRONG
--------------
Half a dozen enrichment builders locate a leg by ``corridor.route_points``.
Those are a summary, not the road: one point roughly every 25 miles. Three of
them (posted maxspeed, height/weight restrictions, ramp-terminal controls) and
the AADT bake handle that by asking OSRM to re-thread the waypoints, and when
that is not in the cache they fall back to ``_interpolated_geometry`` --
straight chords between points 25 miles apart.

On a straight prairie interstate a chord is the road. Everywhere else it is
not, and the failure is silent: a way sitting on the real curve is simply too
far from the chord to snap, so the layer comes back thin and reports success.
That is what produced 2 speed-limit rows on a rerouted Corpus Christi to San
Antonio where the leg had 24.

WHAT IS ACTUALLY AVAILABLE
--------------------------
``world_data/us/geometry/<state>.jsonl`` already carries the leg's real
polyline -- the one the curve baker reads -- adaptively simplified so that
bends keep their vertices and only genuinely straight runs are thinned. 1,290
of the 1,291 legs have one. It is the road, it is checked in, and it needs no
network at all.

So: decode it, re-densify the thinned straight runs back to a fixed stride,
and hand every builder the same ``[(lat, lon, at_mi), ...]`` shape they
already consume. Interpolating along a simplified polyline is not the same
mistake as interpolating between route points -- the simplifier only removes
vertices it has proven are within tolerance of the line through them, so the
segment being filled in really is straight.

Mileage is rescaled to the leg's adopted ``miles``, because that is the figure
pay, deadlines and every other layer's ``at_mi`` are keyed to.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import straw_curve_sample as scs  # noqa: E402

ROOT = TOOLS_DIR.parent
GEOMETRY_DIR = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "geometry"

M_TO_FT = 3.280839895
EARTH_RADIUS_MI = 3958.7613

# Stride for re-densifying thinned straight runs. 0.1 mi is comfortably inside
# the tightest corridor tolerance any consumer uses (the maxspeed snap accepts
# 60 m, about 0.037 mi, from a vertex), so a way on the corridor always has a
# vertex near enough to snap to.
DENSIFY_MI = 0.1

_GEOMETRY_CACHE: dict[str, dict[str, Any]] | None = None


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


def load_geometry(refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Every archived leg record, keyed by ``from:to``. Read once, then cached."""
    global _GEOMETRY_CACHE
    if _GEOMETRY_CACHE is None or refresh:
        records: dict[str, dict[str, Any]] = {}
        for shard in sorted(GEOMETRY_DIR.glob("*.jsonl")):
            for line in shard.read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.startswith('{"meta"'):
                    continue
                record = json.loads(line)
                records[record["leg"]] = record
        _GEOMETRY_CACHE = records
    return _GEOMETRY_CACHE


def archived_shape(leg_id: str) -> list[list[float]] | None:
    """The leg's archived polyline as ``[[lon, lat], ...]``, or None."""
    record = load_geometry().get(leg_id)
    if not record:
        return None
    coords = scs.decode_geometry(record["geom"])
    return coords if len(coords) >= 2 else None


def archived_profile(leg_id: str, leg_miles: float) -> list[tuple[float, float]] | None:
    """``[(at_mi, elevation_ft), ...]`` along the leg, scaled to ``leg_miles``.

    Elevation is stored quantized to whole metres, so read this as ground
    shape rather than as a survey: a single sample carries about +/-1.6 ft.
    Over anything longer than a few hundred feet that is well under the grade
    resolution any consumer cares about.
    """
    record = load_geometry().get(leg_id)
    if not record:
        return None
    geom = record["geom"]
    scale = 10 ** geom["q"]
    lat = geom["lat0"] / scale
    lon = geom["lon0"] / scale
    elev_m = float(geom["ele0_m"])
    profile: list[tuple[float, float]] = [(0.0, elev_m * M_TO_FT)]
    cum = 0.0
    prev_lat, prev_lon = lat, lon
    for dlat, dlon, dele in zip(geom["dlat"], geom["dlon"], geom["dele_m"], strict=False):
        lat = prev_lat + dlat / scale
        lon = prev_lon + dlon / scale
        elev_m += dele
        cum += _haversine_mi(prev_lat, prev_lon, lat, lon)
        profile.append((cum, elev_m * M_TO_FT))
        prev_lat, prev_lon = lat, lon
    total = profile[-1][0] or 1.0
    k = (leg_miles or total) / total
    return [(mi * k, ft) for mi, ft in profile]


def archived_route(leg_id: str) -> dict[str, Any] | None:
    """The archived polyline in the shape the route parsers hand around.

    ``{"coordinates": [[lon, lat], ...], "elevations_ft": [...], "miles": ...}``
    -- the same keys ``parse_ors_route`` produces, so a bake that was written
    against a live route fetch can read the checked-in road instead.
    """
    coords = archived_shape(leg_id)
    if coords is None:
        return None
    record = load_geometry()[leg_id]
    geom = record["geom"]
    elev_m = float(geom["ele0_m"])
    elevations = [elev_m * M_TO_FT]
    for dele in geom["dele_m"]:
        elev_m += dele
        elevations.append(elev_m * M_TO_FT)
    miles = sum(
        _haversine_mi(a[1], a[0], b[1], b[0]) for a, b in zip(coords, coords[1:], strict=False)
    )
    return {
        "coordinates": coords,
        "elevations_ft": elevations,
        "miles": miles,
        "has_tollway": False,
    }


def densify(coords: list[list[float]], step_mi: float = DENSIFY_MI) -> list[list[float]]:
    """``[[lon, lat], ...]`` with no gap longer than ``step_mi``.

    For readers that sample a road at a fixed stride rather than at its
    vertices. The archive thins straight runs, so a stride sampler walking its
    vertices silently drops to whatever resolution the simplifier left --
    which turned a quarter-mile speed-limit sweep into a handful of readings.
    A no-op on a polyline that is already denser than the stride.
    """
    out: list[list[float]] = []
    for i, (lon, lat) in enumerate(coords[:-1]):
        lon_next, lat_next = coords[i + 1]
        span = _haversine_mi(lat, lon, lat_next, lon_next)
        steps = max(1, int(span / step_mi))
        for s in range(steps):
            t = s / steps
            out.append([lon + (lon_next - lon) * t, lat + (lat_next - lat) * t])
    out.append(list(coords[-1]))
    return out


def dense_geometry(
    leg_id: str,
    leg_miles: float,
    step_mi: float = DENSIFY_MI,
) -> list[tuple[float, float, float]] | None:
    """``[(lat, lon, at_mi), ...]`` along the leg's real road, or None.

    The shape every corridor builder wants: dense enough that a way point on
    the corridor is always within snapping distance of a vertex, and keyed to
    the leg's adopted mileage.
    """
    coords = archived_shape(leg_id)
    if coords is None:
        return None
    raw: list[float] = [0.0]
    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:], strict=False):
        raw.append(raw[-1] + _haversine_mi(lat1, lon1, lat2, lon2))
    total = raw[-1] or 1.0
    k = (leg_miles or total) / total

    out: list[tuple[float, float, float]] = []
    for i, (lon, lat) in enumerate(coords[:-1]):
        lon_next, lat_next = coords[i + 1]
        span = (raw[i + 1] - raw[i]) * k
        steps = max(1, int(span / step_mi))
        for s in range(steps):
            t = s / steps
            out.append(
                (
                    lat + (lat_next - lat) * t,
                    lon + (lon_next - lon) * t,
                    raw[i] * k + span * t,
                )
            )
    last_lon, last_lat = coords[-1]
    out.append((last_lat, last_lon, raw[-1] * k))
    return out


def dense_route_points(leg_id: str, leg_miles: float) -> list[dict[str, float]] | None:
    """:func:`dense_geometry` in the ``route_points`` dict shape.

    For the builders that take a waypoint list rather than a polyline.
    """
    geometry = dense_geometry(leg_id, leg_miles)
    if geometry is None:
        return None
    return [{"at_mi": at_mi, "lat": lat, "lon": lon} for lat, lon, at_mi in geometry]


__all__ = [
    "DENSIFY_MI",
    "archived_profile",
    "archived_route",
    "archived_shape",
    "dense_geometry",
    "dense_route_points",
    "densify",
    "load_geometry",
]
