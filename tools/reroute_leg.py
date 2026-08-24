"""Put a leg back on the road it is named for.

Thirty legs are labelled for an interstate their baked route never joins. A
truck router settles which fault it is (see ``tools/repair_leg_labels.py``):
where the interstate genuinely serves the pair, the LABEL is right and the
baked ROUTE is wrong. Corpus Christi to San Antonio is 98 percent I-37 by any
sane routing, and the archived polyline runs US-181 instead.

This replaces such a leg's route with the one a truck would actually take,
and re-derives the layers that ride on it.

WHY IT IS SAFE TO DO NOW, HAVING SAID IT WAS NOT
------------------------------------------------
The earlier reading of this was that rerouting would strip a leg of its 807
landmarks, 532 interchanges and 81 stops because those came from Overpass,
which is not running. That was wrong, and worth correcting rather than
quietly working around: ``build_interchanges.py`` already takes ``--pbf`` and
rebuilds interchanges, posted maxspeed, height and weight restrictions and
ramp-terminal controls from the local Geofabrik extracts. The enrichment was
never gone; it simply had never been pointed at a new route.

So the chain is::

    reroute_leg.py --leg a:b --write          # new shape, mileage, curves, grades
    reenrich_leg.py --leg a:b --write         # every layer keyed to the road
    build_interchanges.py --pbf <extract> --only "A->B" --force --write \\
        --maxspeed --restrictions --ramp-controls
    curve_valhalla_facts.py --all             # re-read the road under each bend
    bake_curve_connectors.py --write
    clamp_curve_advisories.py --write
    screen_curve_artifacts.py

PROVEN ON ONE LEG, AND NOT YET COMPLETE
---------------------------------------
Corpus Christi to San Antonio was rerouted and re-enriched as a trial, then
REVERTED, because the leg is not shippable until every layer is back. What
the trial established:

  works   new shape (1,190 vertices), mileage 147 -> 143.6, elevation at
          every vertex, 39 curves, and the route rides I-37 for 88 percent
          of its matched miles against 0 before
  works   build_interchanges.py --pbf rebuilt 35 interchanges, against 10 on
          the old US-181 route; --restrictions gave 12
  thin    --maxspeed produced 2 speed_limit rows against the old 24, because
          every corridor bake located the leg by interpolating straight
          chords between route points 25 miles apart. FIXED: they now read
          the checked-in dense geometry archive instead (tools/leg_geometry.py)
  FIXED   grade_segments. This tool is holding the full-precision /height
          reading, so it writes the whole quarter-mile profile itself rather
          than leaving the leg with no grade simulation at all -- which is why
          the trial was reverted rather than committed
  later   landmarks, checkpoints, state_miles, state_crossings, traffic_aadt,
          lane_segments, and the OSM layers, all of which need an index or a
          network this tool has no business fetching. Run
          ``tools/reenrich_leg.py`` after this; enrich_routes.py is NOT the
          entry point -- its --only flag only governs geometry refresh.

TWO TRAPS ALREADY PAID FOR
--------------------------
Dropping route_points as "stale" and stopping there leaves the enrichment
builders with no geometry to locate the leg by. build_interchanges then
retained 0 of 59,924 ramp nodes and exited 0 -- a tool that finds nothing
and reports success. That is why this writes the new route_points and
elevation_samples rather than only clearing the old.

The sub-mode flags do NOT compose. Passing --maxspeed --restrictions
--ramp-controls together dispatches to one and silently skips the rest, so
they must be run in sequence.

WHAT THIS TOOL DOES AND DOES NOT DO
-----------------------------------
It writes the new polyline into the geometry archive, sets ``leg.miles`` from
the router's own distance, and drops every corridor layer keyed to the OLD
polyline, because those are now wrong rather than merely stale -- a landmark
at mile 40 of a route that no longer passes it is worse than no landmark.
Rebuilding them is the enrichment pass above, and the leg is INCOMPLETE until
that has run. ``--check`` reports any leg left in that state.

Elevation is refetched from Valhalla ``/height`` along the new shape, because
grades are the one layer a driver feels immediately and a stale grade is a
lie the truck tells with its engine.

Usage
-----
    uv run python tools/reroute_leg.py --leg corpus_christi_tx_us:san_antonio_tx_us
    uv run python tools/reroute_leg.py --leg a:b --write
    uv run python tools/reroute_leg.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import straw_curve_sample as scs  # noqa: E402
from reclassify_terrain import build_grade_segments  # noqa: E402  (the shared grade rule)
from terrain_rules import RANK, leg_terrain  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GEOM_DIR = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "geometry"

VALHALLA = "https://valhalla1.openstreetmap.de"
USER_AGENT = "Freight-Fate rerouting (https://github.com/Orinks/Freight-Fate)"
COSTING = "truck"

# What the truck actually is. Valhalla's truck costing defaults to 21.77
# tonnes -- about 48,000 lb -- which is not a loaded US semi, and a weight
# limit it would clear at that figure it would not clear at 80,000. Measured
# on Newark to Hunts Point, truck costing already routes very differently from
# car (61.7 miles over the George Washington Bridge against 23 straight
# through the truck-banned tunnels), so the profile is doing real work; these
# numbers make it do it for the right vehicle.
#
# 80,000 lb gross and 13 ft 6 in are the federal maxima on the Interstate
# system (23 CFR 658.17 for weight, and the height every state signs to);
# 53 ft is the standard trailer, 8 ft 6 in the standard width, and 34,000 lb
# is the tandem-axle limit that goes with the 80,000.
TRUCK_OPTIONS = {
    "height": 4.11,  # metres, 13 ft 6 in
    "width": 2.59,  # 8 ft 6 in
    "length": 21.64,  # 71 ft tractor plus 53 ft trailer
    "weight": 36.29,  # tonnes, 80,000 lb
    "axle_load": 15.42,  # tonnes, 34,000 lb tandem
    "hazmat": False,
}

DELAY_S = 0.4  # a free community service; do not hammer it

GRADE_SOURCE = (
    "Read: Valhalla /height elevation along the leg's own truck route, sampled at "
    "every route vertex and binned at a quarter mile; terrain derived from the "
    "shared relief-in-context rule (tools/reclassify_terrain.py)."
)

# How often to drop a route point and an elevation sample along the new road.
# The downstream builders find a leg by its route_points bbox, so these are
# WRITTEN rather than merely dropped -- clearing them and stopping there left
# build_interchanges with no geometry to filter against, and it dutifully
# retained 0 of 59,924 ramp nodes.
SAMPLE_MI = 25.0
# ...but never fewer than this many points, however short the leg. At a flat
# 25 miles a 23-mile leg got two -- its endpoints -- where the ORS bake it
# replaced never gave any leg fewer than five.
MIN_ROUTE_POINTS = 5

# Layers keyed to the old polyline. After a reroute they describe a road the
# truck no longer drives, so they are dropped rather than carried over.
# route_points, elevation_samples and grade_segments are dropped here and
# rebuilt below from the new road; the rest wait on the enrichment pass.
STALE_AFTER_REROUTE = (
    "route_points",
    "elevation_samples",
    "grade_segments",
    "speed_limits",
    "interchanges",
    "landmarks",
    "checkpoints",
    "state_crossings",
    "state_miles",
    "traffic_aadt",
    "lane_segments",
    "restrictions",
    "toll_events",
)


def _post(path: str, body: dict) -> dict | None:
    request = urllib.request.Request(
        f"{VALHALLA}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                time.sleep(DELAY_S)
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                return None
            time.sleep(2.0 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(2.0 * (attempt + 1))
    return None


def decode_shape(encoded: str, precision: float = 1e-6) -> list[list[float]]:
    """Valhalla's encoded polyline -> ``[[lon, lat], ...]``.

    Precision 6, not the 5 that Google's format uses -- reading it as 5 puts
    the route in the wrong hemisphere, which is at least an obvious failure.
    """
    coords: list[list[float]] = []
    index = lat = lon = 0
    while index < len(encoded):
        for target in ("lat", "lon"):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if target == "lat":
                lat += delta
            else:
                lon += delta
        coords.append([lon * precision, lat * precision])
    return coords


def fetch_route(start: dict, end: dict) -> tuple[list[list[float]], float] | None:
    """``(polyline, miles)`` for the truck route between two city nodes."""
    result = _post(
        "/route",
        {
            "locations": [
                {"lat": start["lat"], "lon": start["lon"]},
                {"lat": end["lat"], "lon": end["lon"]},
            ],
            "costing": COSTING,
            "costing_options": {COSTING: TRUCK_OPTIONS},
            "directions_options": {"units": "miles"},
        },
    )
    if not result or "trip" not in result:
        return None
    shape: list[list[float]] = []
    for leg in result["trip"].get("legs", []):
        piece = decode_shape(leg.get("shape", ""))
        # Legs abut, so drop the duplicated joint rather than doubling a vertex.
        shape.extend(piece[1:] if shape else piece)
    return shape, float(result["trip"]["summary"]["length"])


def fetch_elevation(shape: list[list[float]]) -> list[float] | None:
    """Elevation in feet at every vertex, from Valhalla ``/height``."""
    out: list[float] = []
    for start in range(0, len(shape), 500):
        chunk = shape[start : start + 500]
        result = _post(
            "/height",
            {"shape": [{"lat": lat, "lon": lon} for lon, lat in chunk], "range": False},
        )
        if not result or "height" not in result:
            return None
        out.extend(float(h) * 3.280839895 for h in result["height"])
    return out if len(out) == len(shape) else None


def rides_its_label(shape: list[list[float]], highway: str) -> tuple[float, str]:
    """``(share of the new route on the leg's own shield, dominant road)``.

    The whole point of a reroute is to put the leg back on the road it is
    named for, so this checks that it did. A reroute that lands somewhere else
    is not an improvement, it is a different wrong answer, and the tool
    refuses rather than writing it.

    MEASURED IN MILES, and it has to be. Counting matched POINTS instead --
    which this did, and which read low on every leg it judged -- weights each
    vertex equally, and vertices are not spread evenly along a road: the
    simplifier keeps every bend and thins the straights, so a town street and
    a hundred miles of tangent interstate carry comparable numbers of them.
    Woodburn to Salem read 3 percent on I-5 by point count and named a city
    street as its dominant road; the leg is a straight 19-mile run down the
    freeway with two town approaches. Each matched point is therefore weighted
    by the length of road it stands for.
    """
    import collections
    import re

    shields = set(re.findall(r"\d+", highway))
    cum = scs._cumulative_m(shape)

    def span_m(i: int) -> float:
        """How much road one vertex stands for: half the gap either side."""
        before = cum[i] - cum[i - 1] if i > 0 else 0.0
        after = cum[i + 1] - cum[i] if i + 1 < len(shape) else 0.0
        return (before + after) / 2.0

    tally: collections.Counter[str] = collections.Counter()
    on_label = matched = 0.0
    seen: set[int] = set()  # chunks overlap; a vertex counts once
    start = 0
    while start < len(shape):
        stop = start + 1
        while stop < len(shape) and cum[stop] - cum[start] < 150_000.0 and stop - start < 1000:
            stop += 1
        chunk = shape[start:stop]
        if len(chunk) < 2:
            break
        result = _post(
            "/trace_attributes",
            {
                "shape": [{"lat": lat, "lon": lon} for lon, lat in chunk],
                "costing": COSTING,
                "costing_options": {COSTING: TRUCK_OPTIONS},
                "shape_match": "map_snap",
                "filters": {
                    "attributes": ["edge.names", "edge.use", "matched.edge_index"],
                    "action": "include",
                },
            },
        )
        if result:
            edges = result.get("edges") or []
            # trace_attributes returns one matched point per input vertex, in
            # order, so the offset into the chunk is the offset into the shape.
            for offset, point in enumerate(result.get("matched_points") or []):
                vertex = start + offset
                if vertex >= len(shape) or vertex in seen:
                    continue
                index = point.get("edge_index")
                if index is None or index >= len(edges):
                    continue
                names = edges[index].get("names") or []
                if str(edges[index].get("use")) in ("ramp", "turn_channel"):
                    continue
                seen.add(vertex)
                miles = span_m(vertex)
                matched += miles
                if names:
                    tally[str(names[0])] += miles
                if any(
                    set(re.findall(r"\d+", str(n))) & shields
                    and str(n).strip().upper().startswith("I")
                    for n in names
                ):
                    on_label += miles
        if stop >= len(shape):
            break
        back = stop - 1
        while back > start + 1 and cum[stop - 1] - cum[back] < 1_000.0:
            back -= 1
        start = back
    dominant = tally.most_common(1)[0][0] if tally else "(nothing matched)"
    return (on_label / matched if matched else 0.0), dominant


# A reroute must put at least this much of the leg on its own shield. Below
# it the router disagrees with the label and the leg wants investigating, not
# rewriting -- the same 25 percent the label split used, and for the same
# reason: the measured gap in that distribution sits far below it.
MIN_ON_LABEL = 0.25


def restamp_data_version(meta_line: str, records: list[str]) -> str:
    """The shard's meta line with its content hash re-derived from the records.

    A shard carries a ``data_version`` hashed over its own records, and the
    whole point of it is to notice when the file stops saying what it claims
    to. Rewriting a record and leaving the hash alone breaks exactly that, and
    it had already happened: all fifty checked-in geometry shards carried a
    hash that did not match their own contents -- records byte-identical to
    what the hash was supposedly taken over, hash different. Anything trusting
    it to spot drift would have been misled by it.
    """
    meta = json.loads(meta_line)
    if "meta" not in meta:
        return meta_line
    payload = "\n".join(records).encode("utf-8")
    meta["meta"]["data_version"] = "sha256:" + hashlib.sha256(payload).hexdigest()[:12]
    return json.dumps(meta, sort_keys=True)


def write_geometry(state_code: str, leg_id: str, record: dict) -> None:
    """Replace one leg's record in its state geometry shard."""
    path = GEOM_DIR / f"{state_code}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    meta_line, records, replaced = "", [], False
    for line in lines:
        if not line.strip():
            continue
        if line.startswith('{"meta"'):
            meta_line = line
            continue
        existing = json.loads(line)
        if existing.get("leg") == leg_id:
            records.append(json.dumps(record, sort_keys=True))
            replaced = True
        else:
            records.append(line)
    if not replaced:
        records.append(json.dumps(record, sort_keys=True))
    out = ([restamp_data_version(meta_line, records)] if meta_line else []) + records
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def incomplete_legs(world: dict) -> list[str]:
    """Legs that have been rerouted but not yet re-enriched."""
    out = []
    for leg in world["legs"]:
        corridor = leg.get("corridor") or {}
        if leg.get("rerouted") and not corridor.get("interchanges"):
            out.append(f"{leg['from']}:{leg['to']}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--leg", help="leg id, e.g. corpus_christi_tx_us:san_antonio_tx_us")
    ap.add_argument("--write", action="store_true", help="apply the reroute")
    ap.add_argument("--check", action="store_true", help="list legs awaiting re-enrichment")
    ap.add_argument(
        "--min-share",
        type=float,
        default=MIN_ON_LABEL,
        help="accept a reroute that rides the leg's own shield for at least this "
        "share of its matched miles. Lower it only for a leg whose share was "
        "measured and judged beforehand -- a long leg can be genuinely, "
        "correctly labelled for the interstate it spends its middle on while "
        "spending most of its miles on the roads either side of it "
        f"(default {MIN_ON_LABEL}).",
    )
    args = ap.parse_args()

    world = load_world()
    if args.check:
        pending = incomplete_legs(world)
        print(f"{len(pending)} legs rerouted but not re-enriched:")
        for leg_id in pending:
            print(f"  {leg_id}")
        return 1 if pending else 0

    if not args.leg:
        ap.error("--leg is required unless --check")
    cities = world["cities"]
    leg = next(
        (x for x in world["legs"] if f"{x['from']}:{x['to']}" == args.leg),
        None,
    )
    if leg is None:
        print(f"no such leg: {args.leg}")
        return 1

    fetched = fetch_route(cities[leg["from"]], cities[leg["to"]])
    if fetched is None:
        print("the router returned no route")
        return 1
    shape, miles = fetched
    old_miles = float(leg.get("miles") or 0)
    cum = scs._cumulative_m(shape)
    print(f"{args.leg} ({leg.get('highway')})")
    print(f"  was {old_miles:.0f} mi, router says {miles:.1f} mi over {len(shape)} vertices")
    print(f"  shape length checks out at {cum[-1] / 1609.344:.1f} mi")

    elevations = fetch_elevation(shape)
    if elevations is None:
        print("  elevation fetch failed -- refusing to write a leg with no profile")
        return 1
    print(f"  elevation read at all {len(elevations)} vertices")

    curvature = scs.analyse_curvature(shape, cum)
    print(f"  {len(curvature['curves'])} curves on the new route")

    profile = [(cum[i] / 1609.344, elevations[i]) for i in range(len(shape))]
    grades = build_grade_segments(profile, miles, GRADE_SOURCE)
    steepest = max((abs(g["avg_grade_pct"]) for g in grades), default=0.0)
    # The leg's own label follows the rank-merge rule the terrain sweep set: a
    # rerouted leg that now really crosses a pass firms up, but a curated
    # hills/mountain label is never quietly demoted off a new geometric read.
    spans = {"mountain": 0.0, "hills": 0.0}
    for segment in grades:
        span = float(segment["end_mi"]) - float(segment["start_mi"])
        if segment["terrain"] in spans:
            spans[segment["terrain"]] += span
    derived_terrain = leg_terrain(spans["mountain"], spans["hills"], miles)
    old_terrain = str(leg.get("terrain") or "flat")
    new_terrain = derived_terrain if RANK[derived_terrain] > RANK[old_terrain] else old_terrain
    print(
        f"  {len(grades)} grade segments, steepest {steepest:.2f}% "
        f"(new road reads {derived_terrain}; leg stays {new_terrain})"
    )

    share, dominant = rides_its_label(shape, str(leg.get("highway", "")))
    print(
        f"  the new route rides {leg.get('highway')} for {100 * share:.0f}% of its"
        f" matched miles (dominant road: {dominant})"
    )
    if share < args.min_share:
        print()
        print(
            f"  REFUSING: a reroute is meant to put this leg back on "
            f"{leg.get('highway')}, and this route does not. Investigate the leg, "
            f"or pass --min-share below {100 * share:.0f}% if this share was judged."
        )
        return 1
    if share < MIN_ON_LABEL:
        print(
            f"  (accepted under the usual {100 * MIN_ON_LABEL:.0f}% bar on an "
            f"explicit --min-share {args.min_share})"
        )

    if not args.write:
        print("\n(dry run; pass --write)")
        return 0

    # Archive the SIMPLIFIED polyline, the same way the curve bake does, so a
    # rerouted leg's record is the same kind of object as every other leg's:
    # bends kept verbatim, straight runs thinned to the shared point budget.
    # The grade profile above was taken from the full reading first, so no
    # fidelity is lost where it is felt.
    idx = scs.adaptive_simplify(shape, curvature["curving"], cum, scs.POINT_BUDGET)
    print(f"  archived at {len(idx)} of {len(shape)} vertices (curves kept verbatim)")
    encoded = scs.encode_geometry(shape, elevations, idx)
    write_geometry(
        str(cities[leg["from"]]["state"]).lower(),
        args.leg,
        {
            "leg": args.leg,
            "highway": leg.get("highway", ""),
            "miles": round(miles, 2),
            "geom": encoded,
        },
    )
    leg["miles"] = round(miles)
    leg["terrain"] = new_terrain
    leg["rerouted"] = True
    corridor = leg.get("corridor") or {}
    dropped = {k: len(corridor.get(k) or []) for k in STALE_AFTER_REROUTE if corridor.get(k)}
    for key in STALE_AFTER_REROUTE:
        corridor.pop(key, None)

    # The new road's own geometry, so the enrichment builders have something
    # to work from. Without this they cannot place the leg at all.
    source = (
        "Valhalla truck route over OpenStreetMap, resampled at development time "
        "(replaces the OpenRouteService route this leg was first baked from)."
    )
    points, elevation = [], []
    last = -1e9
    stride = max(0.5, min(SAMPLE_MI, miles / (MIN_ROUTE_POINTS - 1)))
    for i, (lon, lat) in enumerate(shape):
        at_mi = cum[i] / 1609.344
        if at_mi - last < stride and i not in (0, len(shape) - 1):
            continue
        last = at_mi
        points.append({"at_mi": round(at_mi, 2), "lat": round(lat, 5), "lon": round(lon, 5)})
        elevation.append(
            {
                "at_mi": round(at_mi, 2),
                "elevation_ft": round(elevations[i], 1),
                "source": source,
            }
        )
    corridor["route_points"] = points
    corridor["elevation_samples"] = elevation
    # Grades are the one layer a driver feels immediately, and the one this
    # tool can settle on its own: it is holding the full-precision /height
    # reading, so it writes the whole profile rather than leaving the leg with
    # no grade simulation until the enrichment pass runs.
    corridor["grade_segments"] = grades
    leg["corridor"] = corridor
    save_world(world)
    print(f"\n  wrote the new route; dropped {sum(dropped.values())} stale rows: {dropped}")
    print("  THIS LEG IS NOW INCOMPLETE -- run build_interchanges.py --pbf to re-enrich it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
