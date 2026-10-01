"""The road a leg actually drives, read from the geometry archive.

Every corridor builder needs the same thing: a dense [(lat, lon, at_mi)]
polyline for one leg, on the leg's own mileage scale. Until now each of them
reached for it differently, and the two older routes both go wrong after a
reroute:

  * a cached OpenRouteService/OSRM response, keyed to the OLD route -- a
    cache miss on a rerouted leg, or worse, a hit describing the road the
    truck no longer drives;
  * straight segments between route_points, which sit 25 miles apart. A
    25-mile chord across a bend can run several miles off the pavement, and
    every builder that matches OSM features within a corridor tolerance
    quietly loses the ones the chord swung away from.

world_data/us/geometry/<state>.jsonl already holds the real polyline, at
full curve fidelity, checked in and offline. It is written by
bake_curve_geometry.py for a baked leg and by reroute_leg.py for a
rerouted one, so it is the one source that is right in both cases.

Read it first; fall back only when a leg has no archived record.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import straw_curve_sample as scs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GEOM_DIR = ROOT / "data" / "world_data" / "us" / "geometry"

FT_PER_M = 0.3048


def _records(state_code: str) -> dict[str, dict[str, Any]]:
    path = GEOM_DIR / f"{state_code.lower()}.jsonl"
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith('{"meta"'):
            continue
        record = json.loads(line)
        out[record["leg"]] = record
    return out


_CACHE: dict[str, dict[str, dict[str, Any]]] = {}


def archived_record(leg_id: str, state_code: str) -> dict[str, Any] | None:
    if not state_code:
        return None
    code = state_code.lower()
    if code not in _CACHE:
        _CACHE[code] = _records(code)
    return _CACHE[code].get(leg_id)


def decode_elevations_ft(geom: dict[str, Any]) -> list[float]:
    """Elevation in feet at every archived vertex.

    The archive stores elevation the same way it stores position: a first
    value and integer metre deltas. scs.decode_geometry reconstructs the
    coordinates and drops this, which is fine for a curve read and useless
    for a grade.
    """
    metres = geom["ele0_m"]
    out = [float(metres)]
    for delta in geom["dele_m"]:
        metres += delta
        out.append(float(metres))
    return [m / FT_PER_M for m in out]


def archived_polyline(leg_id: str, state_code: str) -> tuple[list[list[float]], list[float]] | None:
    """([[lon, lat], ...], [elevation_ft, ...]) for one leg, or None."""
    record = archived_record(leg_id, state_code)
    if not record or not record.get("geom"):
        return None
    coords = scs.decode_geometry(record["geom"])
    if len(coords) < 2:
        return None
    return coords, decode_elevations_ft(record["geom"])


def archived_geometry(
    leg_id: str, state_code: str, leg_miles: float
) -> list[tuple[float, float, float]] | None:
    """[(lat, lon, at_mi), ...] on the leg's own mileage scale.

    The shape's own length and the leg's adopted miles can differ a little
    -- curated mileage drives pay and deadlines -- so positions are rescaled
    rather than taken raw, exactly as the route-point interpolation did.
    """
    polyline = archived_polyline(leg_id, state_code)
    if polyline is None:
        return None
    coords, _elevations = polyline
    cum_m = scs._cumulative_m(coords)
    raw_mi = cum_m[-1] / 1609.344
    if raw_mi <= 0:
        return None
    scale = (leg_miles / raw_mi) if leg_miles else 1.0
    return [
        (float(lat), float(lon), cum_m[i] / 1609.344 * scale) for i, (lon, lat) in enumerate(coords)
    ]


def leg_id_of(leg: dict[str, Any]) -> str:
    return f"{leg['from']}:{leg['to']}"


def state_code_of(leg: dict[str, Any]) -> str:
    """The state shard a leg lives in, from its own FROM slug.

    The archive is sharded by the state the leg starts in, and a city slug
    carries that state (corpus_christi_tx_us), so no cities table is
    needed to find a leg's record.

    A slug not shaped that way has no state to read and no archived record
    either, so it answers with the empty string rather than raising. This is
    reached from build_interchanges.discover_leg, which is called with
    hand-built leg dicts in tests as well as with real ones.
    """
    parts = str(leg.get("from") or "").rsplit("_", 2)
    return parts[-2].lower() if len(parts) == 3 else ""


def corridor_geometry(leg: dict[str, Any]) -> list[tuple[float, float, float]] | None:
    """The archived polyline for a leg dict, as [(lat, lon, at_mi), ...]."""
    return archived_geometry(leg_id_of(leg), state_code_of(leg), float(leg.get("miles") or 0.0))


def route_point_max_off_mi(leg: dict[str, Any], coords: list[list[float]]) -> float | None:
    """Maximum route-point distance to the archived ``[lon, lat]`` polyline."""
    route_points = (leg.get("corridor") or {}).get("route_points") or []
    vertices = [(float(coord[1]), float(coord[0])) for coord in coords if len(coord) >= 2]
    if not route_points or len(vertices) < 2:
        return None

    distances = []
    for point in route_points:
        if not isinstance(point, dict):
            continue
        lat, lon = point.get("lat"), point.get("lon")
        if (
            not isinstance(lat, (int, float))
            or isinstance(lat, bool)
            or not isinstance(lon, (int, float))
            or isinstance(lon, bool)
        ):
            continue
        lat, lon = float(lat), float(lon)
        lon_scale = math.cos(math.radians(lat))
        segment_distances = []
        for (lat1, lon1), (lat2, lon2) in zip(vertices, vertices[1:], strict=False):
            lon_delta = (lon2 - lon1 + 180.0) % 360.0 - 180.0
            dx = lon_delta * lon_scale
            dy = lat2 - lat1
            point_x = ((lon1 - lon + 180.0) % 360.0 - 180.0) * lon_scale
            point_y = lat1 - lat
            length_squared = dx * dx + dy * dy
            t = (
                max(0.0, min(1.0, -(point_x * dx + point_y * dy) / length_squared))
                if length_squared
                else 0.0
            )
            nearest_lat = lat1 + t * dy
            nearest_lon = lon1 + t * lon_delta
            segment_distances.append(scs._haversine_m(lat, lon, nearest_lat, nearest_lon))
        distances.append(min(segment_distances))
    if not distances:
        return None
    return max(distances) / 1609.344


def reposition_on_route(
    records: list[dict[str, Any]],
    coords: list[list[float]],
    leg_miles: float,
    max_off_mi: float,
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], float]]]:
    """Move coordinate-bearing corridor records onto a new polyline.

    (kept, dropped), where each dropped entry carries how far off the new
    road it landed. A record with real coordinates -- a curated checkpoint is
    a real named town -- survives a reroute: what changes is the MILE it falls
    at, not whether the truck passes it, so re-positioning keeps the curation
    that re-deriving would throw away. A record with no coordinates cannot be
    placed and is dropped; so is one the new road now runs too far from.
    """
    cum_m = scs._cumulative_m(coords)
    route_mi = cum_m[-1] / 1609.344
    scale = (leg_miles / route_mi) if route_mi else 1.0
    kept: list[dict[str, Any]] = []
    dropped: list[tuple[dict[str, Any], float]] = []
    for record in records:
        lat, lon = record.get("lat"), record.get("lon")
        if lat is None or lon is None:
            dropped.append((record, float("inf")))
            continue
        best_i, best_m = 0, float("inf")
        for i, (way_lon, way_lat) in enumerate(coords):
            metres = scs._haversine_m(float(lat), float(lon), way_lat, way_lon)
            if metres < best_m:
                best_i, best_m = i, metres
        off_mi = best_m / 1609.344
        if off_mi > max_off_mi:
            dropped.append((record, off_mi))
            continue
        moved = dict(record)
        moved["at_mi"] = round(min(max(cum_m[best_i] / 1609.344 * scale, 0.0), leg_miles), 1)
        moved["_off_mi"] = off_mi
        kept.append(moved)
    kept.sort(key=lambda row: row["at_mi"])
    return kept, dropped
