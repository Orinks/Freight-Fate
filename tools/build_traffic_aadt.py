"""Bake FHWA HPMS traffic volumes onto legs as ``corridor.traffic_aadt``.

Development-time helper (never called at runtime). For every leg with route
geometry it queries the national HPMS layer hosted for the ArcGIS Living
Atlas (Federal User Community ``hpms_v2_view``, sourced from FHWA's Highway
Performance Monitoring System public release), pulls AADT and through-lane
counts for road sections inside the corridor, snaps them to the leg, and
writes a step-function volume profile plus a leg-level per-direction lane
count. The runtime prefers the baked profile over its class/metro heuristic
for scheduling congestion (see ``sim/trip_models.py``).

Every HTTP response is cached under ``.route-cache/``, so re-runs are free
and a crawl can be resumed after an interruption.

Run from the repo root:
    uv run python tools/build_traffic_aadt.py               # report only
    uv run python tools/build_traffic_aadt.py --write        # update world.json
    uv run python tools/build_traffic_aadt.py --only "Chicago->Indianapolis" --write

After a --write run, regenerate the runtime tree:
    uv run python tools/index_world.py
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_interchanges as bi  # noqa: E402

HPMS_QUERY_URL = (
    "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
    "hpms_v2_view/FeatureServer/0/query"
)
HPMS_SOURCE = (
    "FHWA Highway Performance Monitoring System (HPMS) AADT and through-lane "
    "counts, queried from the national ArcGIS Living Atlas layer "
    "(Federal User Community hpms_v2_view) and snapped to checked-in route "
    "geometry, accessed 2026-07-05: https://www.fhwa.dot.gov/policyinformation/hpms.cfm"
)

ENVELOPE_SPAN_MI = 60.0  # one HPMS query per this much corridor
ENVELOPE_PAD_M = 2500.0
QUERY_WORKERS = 4  # parallel envelope queries per leg
SNAP_CORRIDOR_M = 250.0  # an HPMS section must snap this close to the leg
AADT_SAMPLE_STRIDE_MI = 5.0  # profile resolution along the leg
AADT_ROUND = 500.0
PAGE_SIZE = 2000
# Contamination guards: interpolated route geometry cuts corners in urban
# bends, so a window can catch only a stray frontage stub or a misclassified
# ramp. A window needs real support to speak, no interstate mainline carries
# fewer than a few thousand vehicles a day, and a lone deep dip between two
# agreeing neighbors is junk, not a sudden empty freeway.
MIN_WINDOW_POINTS = 4
INTERSTATE_AADT_FLOOR = 3000.0
LONE_DIP_RATIO = 0.35
_GRID_DEG = 0.05  # coarse cell size for snap lookups (~5.5 km)


def _leg_f_system_where(highway: str) -> str:
    """HPMS functional-system filter for a leg's highway class.

    Interstate legs read only F_SYSTEM 1 -- that excludes parallel arterials
    and frontage roads outright. US and state highways span classes 2-4
    (freeway/expressway and principal/minor arterial)."""
    if re.match(r"^\s*I[-\s]", str(highway).strip(), re.IGNORECASE):
        return "F_SYSTEM=1"
    return "F_SYSTEM>=2 AND F_SYSTEM<=4"


def _leg_geometry(leg: dict[str, Any]) -> list[tuple[float, float, float]] | None:
    route_points = list(leg.get("corridor", {}).get("route_points", ()))
    return bi._osrm_geometry(route_points, 0.0, cached_only=True) or bi._interpolated_geometry(
        route_points
    )


def _corridor_envelopes(
    geom: list[tuple[float, float, float]],
) -> list[tuple[float, float, float, float]]:
    """(xmin, ymin, xmax, ymax) envelopes covering the leg in ~30-mile spans."""
    envelopes = []
    span: list[tuple[float, float, float]] = []
    span_start = 0.0
    for lat, lon, cum in geom:
        span.append((lat, lon, cum))
        if cum - span_start >= ENVELOPE_SPAN_MI:
            envelopes.append(span)
            span = [(lat, lon, cum)]
            span_start = cum
    if len(span) > 1:
        envelopes.append(span)
    out = []
    for chunk in envelopes:
        lats = [p[0] for p in chunk]
        lons = [p[1] for p in chunk]
        mid_lat = (min(lats) + max(lats)) / 2.0
        lat_pad = ENVELOPE_PAD_M / 111_320.0
        lon_pad = ENVELOPE_PAD_M / (111_320.0 * max(0.2, math.cos(math.radians(mid_lat))))
        out.append(
            (min(lons) - lon_pad, min(lats) - lat_pad, max(lons) + lon_pad, max(lats) + lat_pad)
        )
    return out


def _query_hpms(
    envelope: tuple[float, float, float, float], where: str, rate_limit: float
) -> list[dict[str, Any]]:
    """All HPMS features intersecting an envelope, paged and cached."""
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = urllib.parse.urlencode(
            {
                "where": f"({where}) AND AADT>0",
                "geometry": ",".join(f"{v:.5f}" for v in envelope),
                "geometryType": "esriGeometryEnvelope",
                "inSR": 4326,
                "outSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "AADT,THROUGH_LANES",
                "returnGeometry": "true",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
                "f": "json",
            }
        )
        payload = bi._cached_get(f"{HPMS_QUERY_URL}?{params}", "hpms", rate_limit)
        if payload is None or "features" not in payload:
            if payload is not None and payload.get("error"):
                print(f"    HPMS error: {payload['error']}", flush=True)
            break
        features.extend(payload["features"])
        if not payload.get("exceededTransferLimit"):
            break
        offset += PAGE_SIZE
    return features


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return (int(math.floor(lat / _GRID_DEG)), int(math.floor(lon / _GRID_DEG)))


def _neighbors(cell: tuple[int, int]) -> list[tuple[int, int]]:
    return [(cell[0] + dr, cell[1] + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)]


def _lane_floor(aadt: float, interstate: bool) -> int:
    """Physically plausible minimum lanes per direction for a volume.

    Some states inventory divided highways as one-way couplets, so
    THROUGH_LANES/2 can read absurdly low (I-5 through Seattle at one lane
    per direction). No interstate runs fewer than two per direction, and
    six-figure AADT does not move on four total lanes."""
    lanes = 2 if interstate else 1
    if aadt >= 100000:
        lanes = max(lanes, 3)
    if aadt >= 160000:
        lanes = max(lanes, 4)
    return lanes


def _snap_points(
    features: list[dict[str, Any]],
    geom: list[tuple[float, float, float]],
    leg_miles: float,
    *,
    interstate: bool,
) -> list[tuple[float, float, int]]:
    """(at_mi, aadt, per-direction lanes) for on-corridor HPMS vertices."""
    geom_grid: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
    for glat, glon, cum in geom:
        geom_grid.setdefault(_cell(glat, glon), []).append((glat, glon, cum))
    total = geom[-1][2] or leg_miles

    points: list[tuple[float, float, int]] = []
    for feature in features:
        attrs = feature.get("attributes", {})
        aadt = float(attrs.get("AADT") or 0.0)
        if aadt <= 0:
            continue
        through = attrs.get("THROUGH_LANES") or 0
        lanes_per_dir = max(1, round(float(through) / 2.0)) if through else 2
        lanes_per_dir = max(lanes_per_dir, _lane_floor(aadt, interstate))
        for path in feature.get("geometry", {}).get("paths", ()):
            for lon, lat in path[::2]:  # every other vertex is plenty at 250m
                best_d = float("inf")
                best_cum = 0.0
                for ncell in _neighbors(_cell(lat, lon)):
                    for glat, glon, cum in geom_grid.get(ncell, ()):
                        d = bi._haversine_mi(lat, lon, glat, glon)
                        if d < best_d:
                            best_d, best_cum = d, cum
                if best_d * 1609.34 <= SNAP_CORRIDOR_M:
                    points.append((best_cum / total * leg_miles, aadt, lanes_per_dir))
    return points


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def assemble_profile(
    points: list[tuple[float, float, int]], leg_miles: float, *, interstate: bool
) -> list[dict[str, Any]]:
    """Median-of-window step profile along the leg, collapsed over equal runs."""
    if interstate:
        points = [p for p in points if p[1] >= INTERSTATE_AADT_FLOOR]
    if not points:
        return []
    half = AADT_SAMPLE_STRIDE_MI
    picked: list[tuple[float, float, int]] = []
    mile = 0.0
    while mile <= leg_miles + 1e-9:
        window = [p for p in points if abs(p[0] - mile) <= half]
        if len(window) >= MIN_WINDOW_POINTS:
            aadt = _median([p[1] for p in window])
            lanes = int(_median([float(p[2]) for p in window]))
            picked.append((round(min(leg_miles, mile), 1), aadt, lanes))
        mile += AADT_SAMPLE_STRIDE_MI

    # A lone deep dip whose neighbors agree with each other is a snapping
    # artifact; carry the neighbor value across it.
    for i in range(1, len(picked) - 1):
        prev_a, next_a = picked[i - 1][1], picked[i + 1][1]
        if picked[i][1] < LONE_DIP_RATIO * min(prev_a, next_a) and max(prev_a, next_a) <= 2.0 * min(
            prev_a, next_a
        ):
            picked[i] = (picked[i][0], prev_a, picked[i - 1][2])

    profile: list[dict[str, Any]] = []
    for at_mi, aadt, lanes in picked:
        rounded = round(aadt / AADT_ROUND) * AADT_ROUND
        if profile and profile[-1]["aadt"] == rounded and profile[-1]["lanes"] == lanes:
            continue
        profile.append({"at_mi": at_mi, "aadt": rounded, "lanes": lanes, "source": HPMS_SOURCE})
    return profile


def bake_leg(leg: dict[str, Any], rate_limit: float) -> int:
    geom = _leg_geometry(leg)
    if not geom:
        return 0
    leg_miles = float(leg["miles"])
    where = _leg_f_system_where(str(leg.get("highway", "")))
    features: list[dict[str, Any]] = []
    envelopes = _corridor_envelopes(geom)
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=QUERY_WORKERS) as pool:
        for chunk in pool.map(lambda env: _query_hpms(env, where, rate_limit), envelopes):
            features.extend(chunk)
    interstate = where == "F_SYSTEM=1"
    points = _snap_points(features, geom, leg_miles, interstate=interstate)
    profile = assemble_profile(points, leg_miles, interstate=interstate)
    if not profile:
        return 0
    leg.setdefault("corridor", {})["traffic_aadt"] = profile
    # Leg-level per-direction lane count for the lane gameplay: the median
    # across the profile, so a short urban widening does not set the tone.
    leg["lanes"] = int(_median([float(s["lanes"]) for s in profile]))
    return len(profile)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bake HPMS AADT profiles into world.json.")
    parser.add_argument("--write", action="store_true", help="Write back into world.json.")
    parser.add_argument("--only", default="", help="Limit to one leg, e.g. 'A->B'.")
    parser.add_argument("--max-legs", type=int, default=0)
    parser.add_argument("--rate-limit", type=float, default=0.2)
    parser.add_argument(
        "--force", action="store_true", help="Re-bake legs that already have a profile."
    )
    args = parser.parse_args(argv)

    data = json.loads(bi.WORLD_PATH.read_text(encoding="utf-8"))
    legs = data["legs"]
    if args.only:
        a, _, b = args.only.partition("->")
        legs = [leg for leg in legs if leg["from"] == a.strip() and leg["to"] == b.strip()]
        if not legs:
            raise SystemExit(f"No leg {args.only!r}")

    targets = []
    for leg in legs:
        corridor = leg.get("corridor", {})
        if len(corridor.get("route_points", ())) < 2:
            continue
        if corridor.get("traffic_aadt") and not args.force:
            continue
        if not args.max_legs or len(targets) < args.max_legs:
            targets.append(leg)
    if not targets:
        print("No legs need a traffic profile (use --force to redo).")
        return 0

    baked_legs = 0
    baked_samples = 0
    for i, leg in enumerate(targets, start=1):
        print(f"[{i}/{len(targets)}] {leg['from']}->{leg['to']} ({leg['highway']})", flush=True)
        try:
            samples = bake_leg(leg, args.rate_limit)
        except Exception as exc:  # noqa: BLE001 - one bad leg must not abort the crawl
            print(f"    skipped: {type(exc).__name__}: {exc}", flush=True)
            samples = 0
        if samples:
            baked_legs += 1
            baked_samples += samples
            print(f"    {samples} volume samples, {leg.get('lanes')} lanes per direction")
        else:
            print("    no on-corridor HPMS sections; keeping the heuristic", flush=True)
        if args.write and baked_legs and i % 10 == 0:
            bi.WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"    ...checkpointed world.json ({baked_legs} legs so far)", flush=True)

    print(f"\n{len(targets)} legs processed, {baked_legs} baked, {baked_samples} samples.")
    if args.write and baked_legs:
        bi.WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {bi.WORLD_PATH}")
    elif not args.write:
        print("(dry run; pass --write to update world.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
