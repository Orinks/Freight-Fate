"""Position real named-place checkpoints on a leg's ORS route geometry.

The repeatable core of the map-enrichment recipe (see
``docs/map-enrichment-recipe.md``): given a leg and a list of candidate towns
(name + coordinates), match each town to the nearest point on the leg's real
driving-hgv polyline, reject candidates that sit too far off the route (the
sanity gate against wrong or misplaced towns), and emit checkpoint entries
whose name/state are spoken text.

Dry-run by default; ``--write`` merges the accepted checkpoints into
``world.json`` (sorted by mile, deduped by name) and drops the synthetic
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
import json
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import enrich_routes as er  # noqa: E402  (needs sys.path above)

# A candidate further off the route than this is probably the wrong town, a
# coordinate typo, or a place on a different road -- reject it rather than
# inventing a checkpoint the driver never actually passes.
MAX_OFF_ROUTE_MI = 2.0
PLACEHOLDER_MARKER = "corridor between"


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


def _parse_candidate(raw: str) -> dict[str, Any]:
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) not in (4, 5, 6):
        raise SystemExit(
            f"--candidate must be 'Name|lat|lon|State[|type[|highway]]', got {raw!r}"
        )
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
    parser.add_argument("--leg", required=True, help="Leg as 'from_slug:to_slug' (direction matters).")
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        required=True,
        help="Repeatable: 'Name|lat|lon|State[|type]'. State may be a 2-letter "
        "code (resolved to the full spoken name) or the full name.",
    )
    parser.add_argument(
        "--max-off-route-mi",
        type=float,
        default=MAX_OFF_ROUTE_MI,
        help="Reject candidates further off the route than this (sanity gate).",
    )
    parser.add_argument("--write", action="store_true", help="Merge into world.json.")
    parser.add_argument("--cache-dir", default=str(er.CACHE_PATH))
    parser.add_argument("--rate-limit", type=float, default=1.0)
    args = parser.parse_args(argv)

    api_key = er.ors_api_key()
    if api_key is None:
        raise SystemExit(
            f"Needs the {er.ORS_API_KEY_ENV} environment variable and the "
            "tooling group (uv run --group tooling ...)."
        )
    data = json.loads(er.WORLD_PATH.read_text(encoding="utf-8"))
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
        raise SystemExit(f"No leg {args.leg!r} in world.json{hint}")

    parsed = er._cached_ors_route(data, leg, Path(args.cache_dir), args.rate_limit, api_key)
    leg_miles = float(leg["miles"])
    accepted: list[dict[str, Any]] = []
    for raw in args.candidate:
        cand = _parse_candidate(raw)
        at_mi, off_mi = position_on_route(
            parsed["coordinates"], float(parsed["miles"]), leg_miles, cand["lat"], cand["lon"]
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
                "source": (
                    f"Real town on {highway} between {leg['from']} and "
                    f"{leg['to']}; position matched to the nearest point on the "
                    f"real ORS driving-hgv route geometry ({off_mi} mi off-route "
                    "at closest approach)."
                ),
            }
        )
        print(f"ACCEPTED {cand['name']} at mile {at_mi} ({off_mi} mi off-route)")

    if not accepted:
        print("Nothing accepted; world.json unchanged.")
        return 1
    corridor = leg.setdefault("corridor", {})
    merged = merge_checkpoints(list(corridor.get("checkpoints", [])), accepted)
    corridor["checkpoints"] = merged
    print(f"\nLeg {leg['from']} -> {leg['to']} checkpoints ({len(merged)}):")
    for checkpoint in merged:
        print(f"  {checkpoint['at_mi']:>7.1f}  {checkpoint['name']}, {checkpoint['state']}")
    if args.write:
        er.WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print("\nWrote world.json -- now run: uv run python tools/index_world.py")
    else:
        print("\nDry run (pass --write to save).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
