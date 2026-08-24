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
quietly working around: the enrichment was never gone, it had simply never
been pointed at a new route. Every corridor builder now reads the leg's
polyline from the geometry archive (``tools/leg_geometry.py``) instead of
re-routing it, and the archive is what this tool writes.

THIS IS THE FIRST HALF
----------------------
It settles the route and writes it. It does NOT re-derive the layers that
ride on it, and a leg is not shippable until they are back -- a leg without
``grade_segments`` has no grade simulation at all, which is why the first
trial of this was reverted rather than committed::

    reroute_leg.py    --leg a:b --write                    # the road
    reroute_enrich.py --leg a:b --pbf us.osm.pbf --write   # everything on it

``--check`` on either tool lists any leg left between the two.

TRAPS ALREADY PAID FOR
----------------------
Dropping route_points as "stale" and stopping there leaves the enrichment
builders with no bounds to prefilter a local OSM extract by, and
``build_interchanges`` then retained 0 of 59,924 ramp nodes and exited 0 -- a
tool that finds nothing and reports success. That is why this writes new
route_points and elevation_samples rather than only clearing the old.

``--only`` on every builder in the chain takes SLUGS, never spoken city
names, and the interchange sub-mode flags do not compose: passing
``--maxspeed --restrictions --ramp-controls`` together dispatches to one and
silently skips the rest. ``reroute_enrich.py`` runs them in sequence.

WHAT THIS TOOL DOES AND DOES NOT DO
-----------------------------------
It writes the new polyline into the geometry archive, sets ``leg.miles`` from
the router's own distance, and drops every corridor layer keyed to the OLD
polyline, because those are now wrong rather than merely stale -- a landmark
at mile 40 of a route that no longer passes it is worse than no landmark.
Rebuilding them is ``reroute_enrich.py``, and the leg is INCOMPLETE until
that has run. ``--check`` reports any leg left in that state.

Curated CHECKPOINTS are the exception and are re-positioned rather than
dropped: see ``CHECKPOINT_MAX_OFF_MI`` below.

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
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import leg_geometry as lg  # noqa: E402
import straw_curve_sample as scs  # noqa: E402
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

# How often to drop a route point and an elevation sample along the new road.
# The downstream builders find a leg by its route_points bbox, so these are
# WRITTEN rather than merely dropped -- clearing them and stopping there left
# build_interchanges with no geometry to filter against, and it dutifully
# retained 0 of 59,924 ramp nodes.
SAMPLE_MI = 25.0

# Layers keyed to the old polyline. After a reroute they describe a road the
# truck no longer drives, so they are dropped rather than carried over.
# route_points and elevation_samples are dropped here and rebuilt below.
STALE_AFTER_REROUTE = (
    "route_points",
    "elevation_samples",
    "grade_segments",
    "speed_limits",
    "interchanges",
    "landmarks",
    "state_crossings",
    "state_miles",
    "traffic_aadt",
    "lane_segments",
    "restrictions",
    "toll_events",
)

# Neither are STOPS, and for a different reason. A stop is a real named
# facility -- a Love's with a source URL and a counted 111 parking spaces --
# but unlike a checkpoint it carries no coordinates, only a mile. So there is
# nothing to re-position it against, and the two honest options are to drop
# the curation or to carry it across proportionally. It is carried: dropping
# seven truck stops off a leg takes its fuel, its parking and its food with
# them, which is a worse leg than one whose stop sits a mile out. The same
# proportional rule ``repair_leg_mileage.py`` uses for every other along-route
# position, and it is recorded in the stop's own source line so nobody later
# mistakes a carried mile for a surveyed one.
#
# A stop left past the end of a shorter leg is what made this necessary: the
# world refuses to load at all when one does.
#
# Checkpoints are NOT in that list. Every other layer above is a reading taken
# along the old polyline, and re-reading it against the new one is the whole
# job. A checkpoint is not a reading: it is a real named town, curated by
# hand, carrying its own coordinates. Beeville is on I-37 whichever way this
# leg was baked. So the reroute moves the mile it falls at and keeps the
# curation -- and drops only a town the new road now runs too far from, which
# is the one case where the truck genuinely stopped passing it.
CHECKPOINT_MAX_OFF_MI = 3.0


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


def fetch_route(start: dict, end: dict) -> tuple[list[list[float]], float, bool] | None:
    """``(polyline, miles, whether it tolls)`` for the truck route between two
    city nodes."""
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
    summary = result["trip"]["summary"]
    return shape, float(summary["length"]), bool(summary.get("has_toll"))


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

    The match is on the shield's CLASS AND NUMBER (``scs.matches_shield``).
    This used to require the matched road's name to begin with "I", which
    scored every US and state route at zero however faithfully it drove its
    own road -- so this tool would have refused to reroute any of them, and
    the leg-label probe filtered them out before anyone found out.
    """
    import collections

    cum = scs._cumulative_m(shape)
    tally: collections.Counter[str] = collections.Counter()
    on_label = matched = 0
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
            for point in result.get("matched_points") or []:
                index = point.get("edge_index")
                if index is None or index >= len(edges):
                    continue
                names = edges[index].get("names") or []
                if str(edges[index].get("use")) in ("ramp", "turn_channel"):
                    continue
                matched += 1
                if names:
                    tally[str(names[0])] += 1
                if any(scs.matches_shield(str(n), highway) for n in names):
                    on_label += 1
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


def write_geometry(state_code: str, leg_id: str, record: dict) -> None:
    """Replace one leg's record in its state geometry shard."""
    path = GEOM_DIR / f"{state_code}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out, replaced = [], False
    for line in lines:
        if not line.strip():
            continue
        if line.startswith('{"meta"'):
            out.append(line)
            continue
        existing = json.loads(line)
        if existing.get("leg") == leg_id:
            out.append(json.dumps(record, sort_keys=True))
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(json.dumps(record, sort_keys=True))
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
    shape, miles, has_toll = fetched
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

    curves = scs.analyse_curvature(shape, cum)["curves"]
    print(f"  {len(curves)} curves on the new route")

    share, dominant = rides_its_label(shape, str(leg.get("highway", "")))
    print(
        f"  the new route rides {leg.get('highway')} for {100 * share:.0f}% of its"
        f" matched miles (dominant road: {dominant})"
    )
    if share < MIN_ON_LABEL:
        print()
        print(
            f"  REFUSING: a reroute is meant to put this leg back on "
            f"{leg.get('highway')}, and this route does not. Investigate the leg."
        )
        return 1

    if not args.write:
        print("\n(dry run; pass --write)")
        return 0

    encoded = scs.encode_geometry(shape, elevations, list(range(len(shape))))
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
    leg["rerouted"] = True
    corridor = leg.get("corridor") or {}
    dropped = {k: len(corridor.get(k) or []) for k in STALE_AFTER_REROUTE if corridor.get(k)}
    tolls = corridor.get("toll_events") or []
    for key in STALE_AFTER_REROUTE:
        corridor.pop(key, None)

    stops = list(leg.get("stops") or [])
    if stops and old_miles > 0:
        scale = miles / old_miles
        for stop in stops:
            at_mi = stop.get("at_mi")
            if at_mi is None:
                continue
            stop["at_mi"] = round(min(max(float(at_mi) * scale, 0.0), miles), 1)
            note = stop.get("source") or ""
            marker = " Mile carried across proportionally when the leg was rerouted."
            if marker.strip() not in note:
                stop["source"] = (note + marker).strip()
        leg["stops"] = stops

    kept, left_behind = lg.reposition_on_route(
        list(corridor.get("checkpoints") or []),
        shape,
        miles,
        CHECKPOINT_MAX_OFF_MI,
    )
    for record in kept:
        off_mi = record.pop("_off_mi")
        record["source"] = (
            f"Real town on {leg.get('highway')} between {leg['from']} and {leg['to']}; "
            "position matched to the nearest point on the leg's checked-in route "
            f"geometry ({off_mi:.2f} mi off-route at closest approach)."
        )
    if kept or left_behind:
        corridor["checkpoints"] = kept
    # The old value described the old road. Valhalla says whether the route it
    # returned uses a toll, so the advisory that asks a curator to look at a
    # tolled leg with no toll events is answered about the RIGHT road.
    corridor["tollway_detected"] = has_toll

    # The new road's own geometry, so the enrichment builders have something
    # to work from. Without this they cannot place the leg at all.
    source = (
        "Valhalla truck route over OpenStreetMap, resampled at development time "
        "(replaces the OpenRouteService route this leg was first baked from)."
    )
    # Positions run on the leg's ADOPTED mileage, which is the router's
    # distance rounded to a whole mile. Writing them on the raw route length
    # instead put the last route point at mile 140.16 of a 140-mile leg, and
    # the world refuses to load a position past the end of its own leg.
    adopted = float(leg["miles"])
    raw_mi = cum[-1] / 1609.344
    mile_scale = (adopted / raw_mi) if raw_mi else 1.0
    points, elevation = [], []
    last = -1e9
    for i, (lon, lat) in enumerate(shape):
        at_mi = cum[i] / 1609.344 * mile_scale
        if at_mi - last < SAMPLE_MI and i not in (0, len(shape) - 1):
            continue
        last = at_mi
        at_mi = min(at_mi, adopted)
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
    leg["corridor"] = corridor
    save_world(world)
    print(f"\n  wrote the new route; dropped {sum(dropped.values())} stale rows: {dropped}")
    print(f"  kept {len(kept)} curated checkpoints, re-positioned onto the new road")
    if stops:
        print(f"  carried {len(stops)} curated stops across on the new mileage")
    for record, off_mi in left_behind:
        where = "no coordinates" if off_mi == float("inf") else f"{off_mi:.1f} mi off the new road"
        print(f"    dropped checkpoint {record.get('name')!r} ({where})")
    print(f"  the new route {'does' if has_toll else 'does not'} use a toll road")
    if tolls:
        # A curated toll is a real plaza on a named road, and this leg just
        # changed roads. Rescaling it would move a plaza onto pavement that
        # may not charge, so it goes -- and it is said out loud, because
        # nothing downstream will put it back.
        print(f"  DROPPED {len(tolls)} CURATED TOLL EVENTS -- re-curate if the new road tolls:")
        for toll in tolls:
            print(f"    {toll.get('name')} on {toll.get('road')} (${toll.get('amount')})")
    print("  THIS LEG IS NOW INCOMPLETE -- run tools/reroute_enrich.py to finish it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
