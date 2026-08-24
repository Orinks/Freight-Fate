"""Position real named-place checkpoints on a leg's ORS route geometry.

The repeatable core of the map-enrichment recipe (see
``docs/map-enrichment-recipe.md``): given a leg and a list of candidate towns
(name + coordinates), match each town to the nearest point on the leg's real
driving-hgv polyline, reject candidates that sit too far off the route (the
sanity gate against wrong or misplaced towns), and emit checkpoint entries
whose name/state are spoken text.

Dry-run by default; ``--write`` merges the accepted checkpoints into the
world source (sorted by mile, deduped by name) and drops the synthetic
"corridor between" placeholder once at least one real checkpoint covers the
leg. Run ``tools/index_world.py`` after writing, as with any world edit.

Example:
    uv run --group tooling python tools/place_checkpoints.py \
        --leg "flagstaff_az_us:kingman_az_us" \
        --candidate "Seligman|35.3258|-112.8747|AZ" \
        --candidate "Williams|35.2494|-112.1910|AZ" \
        --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import enrich_routes as er  # noqa: E402  (needs sys.path above)
import leg_geometry  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

# A candidate further off the route than this is probably the wrong town, a
# coordinate typo, or a place on a different road -- reject it rather than
# inventing a checkpoint the driver never actually passes.
MAX_OFF_ROUTE_MI = 2.0
PLACEHOLDER_MARKER = "corridor between"

# How close two checkpoints may sit when they were discovered rather than
# hand-picked. Not a taste call: measured against the 2,103 gaps between the
# real place checkpoints already curated across the network, whose 1st
# percentile is 8.9 miles -- so in the whole world today, essentially no two
# checkpoints are closer than this. A discovery pass that packed them tighter
# would be talking over the curated corridors, not matching them.
MIN_DISCOVERED_GAP_MI = 8.9

# Which polyline a discovered checkpoint was positioned against.
ARCHIVE_ROUTE_NOTE = "the leg's checked-in route geometry"
ORS_ROUTE_NOTE = "the real ORS driving-hgv route geometry"

# A discovered candidate's precedence when two crowd each other out: the
# bigger settlement is the one a driver orients by.
PLACE_RANK = {"city": 3, "town": 2, "village": 1}


def position_on_route(
    coordinates: list[list[float]],
    route_miles: float,
    leg_miles: float,
    lat: float,
    lon: float,
) -> tuple[float, float]:
    """(at_mi, off_route_mi) for a point against a route polyline.

    Nearest-vertex match: the cumulative along-route distance to the closest
    vertex, rescaled from the polyline's own length to the leg's adopted
    mileage (curated ``miles`` drive pay/deadlines and may differ slightly
    from the raw route length).
    """
    if len(coordinates) < 2:
        raise ValueError("route geometry needs at least 2 vertices")
    best_index = 0
    best_off = float("inf")
    cumulative = [0.0]
    for i in range(1, len(coordinates)):
        lon1, lat1 = coordinates[i - 1][0], coordinates[i - 1][1]
        lon2, lat2 = coordinates[i][0], coordinates[i][1]
        cumulative.append(cumulative[-1] + er._haversine_miles(lat1, lon1, lat2, lon2))
    for i, coord in enumerate(coordinates):
        off = er._haversine_miles(lat, lon, coord[1], coord[0])
        if off < best_off:
            best_off = off
            best_index = i
    total = cumulative[-1] or route_miles or 1.0
    at_mi = cumulative[best_index] / total * leg_miles
    return round(max(1.0, min(leg_miles - 1.0, at_mi)), 1), round(best_off, 2)


def merge_checkpoints(
    existing: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Existing + new checkpoints, deduped by name, placeholder dropped.

    The synthetic "corridor between" placeholder only exists to keep a leg
    dispatchable before real curation; once a real named place covers the
    leg it is spoken noise, so it goes.
    """
    names = {str(c.get("name", "")).lower() for c in existing}
    merged = list(existing)
    for cand in accepted:
        if cand["name"].lower() in names:
            continue
        merged.append(cand)
        names.add(cand["name"].lower())
    has_real = any(PLACEHOLDER_MARKER not in str(c.get("name", "")) for c in merged)
    if has_real:
        merged = [c for c in merged if PLACEHOLDER_MARKER not in str(c.get("name", ""))]
    merged.sort(key=lambda c: float(c["at_mi"]))
    return merged


def leg_route(
    data: dict[str, Any],
    leg: dict[str, Any],
    cache_dir: Path,
    rate_limit: float,
    api_key: str | None,
) -> tuple[list[list[float]], float, str]:
    """``(polyline as [[lon, lat], ...], its own miles, what it is)``.

    The checked-in archive first. Re-asking ORS returns the route the leg was
    ORIGINALLY baked from, which on a rerouted leg is a different road, and a
    checkpoint positioned against it lands nowhere in particular.
    """
    shape = leg_geometry.archived_shape(f"{leg['from']}:{leg['to']}")
    if shape is not None:
        # DENSIFIED, because ``position_on_route`` measures to the nearest
        # VERTEX. The archive thins straight runs, so a town sitting halfway
        # along one reads as tens of miles off-route and is rejected as the
        # wrong town -- silently, and worst exactly where a leg is straightest.
        # At a tenth of a mile apart, nearest-vertex is segment projection.
        shape = leg_geometry.densify(shape)
        miles = sum(
            er._haversine_miles(a[1], a[0], b[1], b[0])
            for a, b in zip(shape, shape[1:], strict=False)
        )
        return shape, miles, ARCHIVE_ROUTE_NOTE
    if api_key is None:
        raise SystemExit(
            f"{leg['from']}:{leg['to']} has no archived route geometry, so this "
            f"needs the {er.ORS_API_KEY_ENV} environment variable."
        )
    parsed = er._cached_ors_route(data, leg, cache_dir, rate_limit, api_key)
    return parsed["coordinates"], float(parsed["miles"]), ORS_ROUTE_NOTE


def discover_candidates(
    data: dict[str, Any],
    leg: dict[str, Any],
    coordinates: list[list[float]],
    route_miles: float,
    max_off_route_mi: float,
    min_gap_mi: float,
) -> list[dict[str, Any]]:
    """Real towns along this leg's route, from the baked OSM place index.

    The same index ``bake_villages`` reads, and the same speakability and
    city-dedupe rules, so a name that is refused as a village cue is not
    quietly admitted as a checkpoint. What differs is the gate: a checkpoint
    is a place the road actually runs through, so only the tight
    ``max_off_route_mi`` catchment survives, and survivors are thinned to the
    network's own working spacing (:data:`MIN_DISCOVERED_GAP_MI`) with the
    bigger settlement winning a crowd.
    """
    import bake_villages as bv

    leg_miles = float(leg["miles"])
    route = [(lat, lon) for lon, lat in coordinates]
    anchors = bv.city_anchors(data)
    index = bv.grid_index(bv.load_places())
    taken = {bv._norm(c.get("name")) for c in (leg.get("corridor") or {}).get("checkpoints", ())}
    for slug in (leg["from"], leg["to"]):
        taken.add(bv._norm(data["cities"][slug].get("spoken_city") or slug))

    found: list[dict[str, Any]] = []
    for place in bv.nearby_places(index, route, max_off_route_mi):
        name = bv.clean_landmark_name(place["name"])
        if not name or not bv.speakable(name) or bv._norm(name) in taken:
            continue
        at_mi, off_mi = position_on_route(
            coordinates, route_miles, leg_miles, float(place["lat"]), float(place["lon"])
        )
        if off_mi > max_off_route_mi:
            continue
        # A place sitting on a dispatchable city IS that city; the route
        # already speaks it as an endpoint.
        if any(
            bv.hav(place["lat"], place["lon"], lat, lon)
            <= (bv.CITY_NAME_DEDUPE_MI if bv._norm(city) == bv._norm(name) else bv.CITY_DEDUPE_MI)
            for lat, lon, city in anchors
        ):
            continue
        found.append(
            {
                "name": name,
                "lat": float(place["lat"]),
                "lon": float(place["lon"]),
                "at_mi": at_mi,
                "off_mi": off_mi,
                "state": str(place.get("state") or ""),
                "type": "place",
                "highway": "",
                "rank": (PLACE_RANK.get(str(place.get("place")), 0), -off_mi),
            }
        )

    # Thin to the network's spacing, best-first, so a crowded metro fringe
    # cannot bury the one town that actually orients the driver.
    kept: list[dict[str, Any]] = []
    for cand in sorted(found, key=lambda c: c["rank"], reverse=True):
        if all(abs(cand["at_mi"] - other["at_mi"]) >= min_gap_mi for other in kept):
            kept.append(cand)
    kept.sort(key=lambda c: c["at_mi"])
    for cand in kept:
        cand.pop("rank", None)
    return kept


def state_at_mile(data: dict[str, Any], leg: dict[str, Any], at_mi: float) -> str:
    """The spoken state name at a mile along the leg.

    A discovered place carries a state tag only where OSM happens to have one,
    which in the US is rarely, so the leg's own baked state sequence answers
    instead -- it is the same fact, measured rather than tagged.
    """
    corridor = leg.get("corridor") or {}
    state = ""
    for crossing in sorted(corridor.get("state_crossings") or (), key=lambda c: float(c["at_mi"])):
        if float(crossing["at_mi"]) <= at_mi:
            state = str(crossing["state"])
        else:
            if not state:
                state = str(crossing.get("from_state") or "")
            break
    if state:
        return state
    miles = corridor.get("state_miles") or ()
    if len(miles) == 1:
        return str(miles[0]["state"])
    return er.spoken_state(data, data["cities"][leg["to"]]["state"])


def _parse_candidate(raw: str) -> dict[str, Any]:
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) not in (4, 5, 6):
        raise SystemExit(f"--candidate must be 'Name|lat|lon|State[|type[|highway]]', got {raw!r}")
    name, lat, lon, state = parts[:4]
    if not name or "_" in name:
        raise SystemExit(f"candidate name {name!r} must be spoken text (no slugs)")
    return {
        "name": name,
        "lat": float(lat),
        "lon": float(lon),
        "state": state,
        "type": parts[4] if len(parts) >= 5 and parts[4] else "place",
        # A leg's declared highway can oversimplify (Billings->SLC is "I-15"
        # but really I-90 + US-191 + US-20 + I-15); the spoken cue should name
        # the road the driver is actually on at that checkpoint.
        "highway": parts[5] if len(parts) == 6 and parts[5] else "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Position real named-place checkpoints on a leg's ORS geometry."
    )
    parser.add_argument(
        "--leg", required=True, help="Leg as 'from_slug:to_slug' (direction matters)."
    )
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="Repeatable: 'Name|lat|lon|State[|type]'. State may be a 2-letter "
        "code (resolved to the full spoken name) or the full name.",
    )
    parser.add_argument(
        "--from-places",
        action="store_true",
        help="Discover candidates from the baked OSM place index along this "
        "leg's route instead of typing them out. What a rerouted leg needs: "
        "its old checkpoints described a road it no longer drives.",
    )
    parser.add_argument(
        "--min-gap-mi",
        type=float,
        default=MIN_DISCOVERED_GAP_MI,
        help="Minimum spacing between DISCOVERED checkpoints (default is the "
        "network's own 1st-percentile gap between curated ones).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop the leg's existing checkpoints first, rather than merging. "
        "For a rerouted leg, where the old ones are on the wrong road.",
    )
    parser.add_argument(
        "--max-off-route-mi",
        type=float,
        default=MAX_OFF_ROUTE_MI,
        help="Reject candidates further off the route than this (sanity gate).",
    )
    parser.add_argument("--write", action="store_true", help="Merge into the world source.")
    parser.add_argument("--cache-dir", default=str(er.CACHE_PATH))
    parser.add_argument("--rate-limit", type=float, default=1.0)
    args = parser.parse_args(argv)

    if not args.candidate and not args.from_places:
        parser.error("pass --candidate at least once, or --from-places")
    # Only a leg with no archived polyline still needs ORS, so a missing key
    # is reported by leg_route at the point it actually blocks something.
    api_key = er.ors_api_key()
    data = load_world()
    from_city, _, to_city = args.leg.partition(":")
    leg = next(
        (
            candidate_leg
            for candidate_leg in data["legs"]
            if candidate_leg["from"] == from_city.strip() and candidate_leg["to"] == to_city.strip()
        ),
        None,
    )
    if leg is None:
        reverse = any(
            candidate_leg["from"] == to_city.strip() and candidate_leg["to"] == from_city.strip()
            for candidate_leg in data["legs"]
        )
        hint = " (the reverse direction exists -- at_mi is measured from 'from')" if reverse else ""
        raise SystemExit(f"No leg {args.leg!r} in the world source{hint}")

    coordinates, route_miles, route_note = leg_route(
        data, leg, Path(args.cache_dir), args.rate_limit, api_key
    )
    leg_miles = float(leg["miles"])
    candidates = [_parse_candidate(raw) for raw in args.candidate]
    if args.replace:
        # Before discovery, not after: the discovery pass skips any name the
        # leg already carries, so leaving the old list in place made a second
        # run find nothing and report "0 real places along the route".
        leg.setdefault("corridor", {}).pop("checkpoints", None)
    if args.from_places:
        discovered = discover_candidates(
            data, leg, coordinates, route_miles, args.max_off_route_mi, args.min_gap_mi
        )
        for cand in discovered:
            cand["state"] = cand["state"] or state_at_mile(data, leg, cand["at_mi"])
        candidates += discovered
        print(f"{len(discovered)} real places found along the route")
    accepted: list[dict[str, Any]] = []
    for cand in candidates:
        at_mi, off_mi = position_on_route(
            coordinates, route_miles, leg_miles, cand["lat"], cand["lon"]
        )
        if off_mi > args.max_off_route_mi:
            print(
                f"REJECTED {cand['name']}: {off_mi} mi off-route "
                f"(> {args.max_off_route_mi}) -- wrong town, typo'd coordinates, "
                "or a place not on this route."
            )
            continue
        highway = cand["highway"] or leg["highway"]
        accepted.append(
            {
                "name": cand["name"],
                "at_mi": at_mi,
                "type": cand["type"],
                "state": er.spoken_state(data, cand["state"]),
                "highway": highway,
                # Real coordinates alongside the along-leg position: the game
                # narrates by at_mi, but Josh's surface-street layer (1.9) can
                # route to a real lat/lon. Additive; the loader ignores it.
                "lat": round(cand["lat"], 5),
                "lon": round(cand["lon"], 5),
                "source": (
                    f"Real town on {highway} between {leg['from']} and "
                    f"{leg['to']}; position matched to the nearest point on "
                    f"{route_note} ({off_mi} mi off-route at closest approach)."
                ),
            }
        )
        print(f"ACCEPTED {cand['name']} at mile {at_mi} ({off_mi} mi off-route)")

    if not accepted:
        print("Nothing accepted; the world source is unchanged.")
        return 1
    corridor = leg.setdefault("corridor", {})
    existing = [] if args.replace else list(corridor.get("checkpoints", []))
    merged = merge_checkpoints(existing, accepted)
    corridor["checkpoints"] = merged
    print(f"\nLeg {leg['from']} -> {leg['to']} checkpoints ({len(merged)}):")
    for checkpoint in merged:
        print(f"  {checkpoint['at_mi']:>7.1f}  {checkpoint['name']}, {checkpoint['state']}")
    if args.write:
        save_world(data)
        print("\nWrote the world source -- now run: uv run python tools/index_world.py")
    else:
        print("\nDry run (pass --write to save).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
