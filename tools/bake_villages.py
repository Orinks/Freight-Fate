"""Bake the small towns and villages a leg passes through as spoken callouts.

A speed limit that drops to 35 in the middle of a mountain highway reads as
arbitrary until something names the place causing it. Camp Verde to Payson is
the case that started this: the 35 zones around mile 37 to 57 are real, and
they are Strawberry and Pine -- but nothing spoke their names, so the leg's
only voice was forests and a river.

Sources OSM ``place=village|town`` points (via ``tools/extract_osm_places.py``,
because the self-hosted Overpass extract carries no ``place`` nodes), projects
each onto the leg's real ORS driving-hgv polyline, and writes them into the
leg's ``corridor.landmarks`` under category ``village`` -- the same cue
machinery as forests and rivers, filtered by its own chatter switch.

Two rules from the map owner (2026-07-20) shape it:

* **No hamlets.** A ``place=hamlet`` is a handful of houses. Announcing one as
  though the driver arrived somewhere is the same false promise the
  truck-access sweep removed. The extractor never collects them.
* **Bake wide, display tight.** Places are collected out to a wide catchment
  and each keeps its ``off_mi`` distance from the road. The ride-along names
  only the ones the route reaches (``VILLAGE_PASS_OFF_MI`` in the sim); the
  wider set stays in the map so an orientation readout can honestly answer
  "Winslow, eleven miles ahead" instead of pretending nothing is out there.
  One bake, one distance field, two consumers.

Where a baked speed zone of 45 or less starts just after a village point, the
callout is pulled to just BEFORE the zone start, so the name arrives in time to
explain the drop rather than confirming it afterwards.

    uv run --group tooling python tools/bake_villages.py [--only "a:b"] [--write]

Additive and idempotent: it regenerates only ``village`` landmarks and leaves
every other category on the leg untouched.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import enrich_routes as er  # noqa: E402  (the composed tool: ORS fetch + cache)
from bake_landmarks import hav, project_on_route, route_cum  # noqa: E402
from enrich_routes_landmarks import clean_landmark_name  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

PLACES_CACHE = ROOT / ".route-cache" / "osm_places_village_town.json"
CACHE_PATH = ROOT / ".route-cache"

# Collection catchment. Wide on purpose (see module docstring): the display
# radius lives in the sim, not here.
CATCHMENT_MI = 12.0
# A place this close to a dispatchable city node IS that city under another
# name (or its own centre node); the route already speaks the city. Kept tight
# on purpose: at 6 miles this rule swallowed Cornville and Mesa Del Caballo,
# which are real separate communities next door to a city node, not aliases of
# it. The generous radius is reserved for a NAME match, where OSM's centre node
# and our city anchor can legitimately sit miles apart in a spread-out town.
CITY_DEDUPE_MI = 4.0
CITY_NAME_DEDUPE_MI = 20.0
# Speed zones at or below this are the "you are in a town now" drops the names
# exist to explain.
TOWN_ZONE_MPH = 45
# Look this far ahead of a village point for the zone it explains, and place
# the callout this far before that zone starts.
ZONE_PAIR_WINDOW_MI = 1.5
ZONE_PAIR_LEAD_MI = 0.2
# Guard against a metro fringe dumping dozens of suburb points onto one leg.
# Nearest-to-the-road first, so the ones the driver actually reaches survive.
MAX_PER_LEG = 30
# Spoken phrasing: "Entering" only where the road runs through the place.
# Interstates bypass towns rather than enter them, so anything farther out is
# phrased as passing.
ENTER_OFF_MI = 0.5


def load_places() -> list[dict]:
    if not PLACES_CACHE.exists():
        raise SystemExit(
            f"no place cache at {PLACES_CACHE}\n"
            "Run: uv run --group tooling python tools/extract_osm_places.py"
        )
    return json.loads(PLACES_CACHE.read_text(encoding="utf-8"))


def grid_index(places: list[dict], cell_deg: float = 0.25) -> dict:
    """Bucket places into a coarse lat/lon grid for cheap corridor lookup."""
    index: dict[tuple[int, int], list[dict]] = {}
    for place in places:
        key = (int(place["lat"] / cell_deg), int(place["lon"] / cell_deg))
        index.setdefault(key, []).append(place)
    return index


def nearby_places(index: dict, route, radius_mi: float, cell_deg: float = 0.25) -> list[dict]:
    """Every indexed place in a cell touched by the route, plus a margin."""
    span = int(math.ceil(radius_mi / 69.0 / cell_deg)) + 1
    keys = set()
    for lat, lon in route:
        base = (int(lat / cell_deg), int(lon / cell_deg))
        for dy in range(-span, span + 1):
            for dx in range(-span, span + 1):
                keys.add((base[0] + dy, base[1] + dx))
    found = {}
    for key in keys:
        for place in index.get(key, ()):
            found[place["id"]] = place
    return list(found.values())


def city_anchors(data: dict) -> list[tuple[float, float, str]]:
    return [
        (float(c["lat"]), float(c["lon"]), str(c.get("spoken_city") or slug))
        for slug, c in data["cities"].items()
        if c.get("lat") is not None and c.get("lon") is not None
    ]


def _norm(name: str) -> str:
    return " ".join(str(name or "").lower().replace(".", " ").split())


# OSM carries multilingual and multi-script names for some places as one string
# ("Camp Verde / Matthi:wa / Gambudih"). There is no honest way to speak that
# automatically -- a screen reader reads the separators aloud, and picking one
# alternative is a guess about which name the place goes by. Such names are
# refused here and reported; a place that deserves its indigenous name deserves
# a curated entry, not a slash-joined tag.
UNSPEAKABLE_NAME_CHARS = ("/", ":", ";", "|", "(", ")", "=")


def speakable(name: str) -> bool:
    """False when a raw OSM name cannot be read aloud as one place name."""
    return not any(ch in name for ch in UNSPEAKABLE_NAME_CHARS)


def zone_starts(leg: dict) -> list[float]:
    """Miles where a baked speed limit of 45 or less drops on this leg.

    Any step DOWN into or within a town zone counts, not just the first one:
    a highway that drops 55 to 40 on the edge of a village and 40 to 35 in its
    centre has two drops, and the second is the one the village name explains.
    """
    samples = sorted(
        leg.get("corridor", {}).get("speed_limits", ()), key=lambda s: float(s["at_mi"])
    )
    starts = []
    previous = None
    for sample in samples:
        mph = sample.get("mph")
        if mph is None:
            continue
        mph = int(mph)
        if mph <= TOWN_ZONE_MPH and (previous is None or mph < previous):
            starts.append(float(sample["at_mi"]))
        previous = mph
    return starts


def paired_mile(at_mi: float, starts: list[float]) -> float | None:
    """The adjusted mile for a village whose name explains a nearby drop.

    The nearest qualifying drop wins, so a village between two zone steps is
    announced ahead of the one it is actually standing in."""
    window = [s for s in starts if -0.5 <= s - at_mi <= ZONE_PAIR_WINDOW_MI]
    if not window:
        return None
    start = min(window, key=lambda s: abs(s - at_mi))
    return max(0.0, round(start - ZONE_PAIR_LEAD_MI, 1))


def spoken_village(name: str, off_mi: float) -> str:
    """The finished cue line, composed here so runtime never sees a raw tag."""
    return f"Entering {name}" if off_mi <= ENTER_OFF_MI else f"Passing {name}"


def bake_leg(leg, data, index, anchors, api_key) -> tuple[list[dict], int, int]:
    parsed = er._cached_ors_route(data, leg, CACHE_PATH, 0.0, api_key)
    coords = parsed["coordinates"]
    if len(coords) < 2:
        return [], 0, 0
    route = [(lat, lon) for lon, lat in coords]
    raw_cum = route_cum(route)
    scale = float(leg["miles"]) / (raw_cum[-1] or 1.0)
    cum = [c * scale for c in raw_cum]

    corridor = leg.setdefault("corridor", {})
    taken = {_norm(lm.get("name")) for lm in corridor.get("landmarks", ())}
    taken |= {_norm(cp.get("name")) for cp in corridor.get("checkpoints", ())}
    for slug in (leg["from"], leg["to"]):
        taken.add(_norm(data["cities"][slug].get("spoken_city") or slug))

    best: dict[str, dict] = {}
    unspeakable = 0
    for place in nearby_places(index, route, CATCHMENT_MI):
        name = clean_landmark_name(place["name"])
        if not name:
            continue
        if not speakable(name):
            unspeakable += 1
            continue
        if _norm(name) in taken:
            continue
        at_mi, off_mi = project_on_route(route, cum, place["lat"], place["lon"])
        if off_mi > CATCHMENT_MI:
            continue
        # A place sitting on a dispatchable city is that city; the route speaks
        # it already as an endpoint or a checkpoint. Distance settles the
        # unnamed match, a name match settles the spread-out one.
        if any(
            hav(place["lat"], place["lon"], lat, lon)
            <= (CITY_NAME_DEDUPE_MI if _norm(city) == _norm(name) else CITY_DEDUPE_MI)
            for lat, lon, city in anchors
        ):
            continue
        record = {
            "name": name,
            "at_mi": round(min(max(at_mi, 0.0), float(leg["miles"])), 1),
            "off_mi": round(off_mi, 2),
            "category": "village",
            "kind": "point",
            "source": (
                f"OpenStreetMap place={place['place']} node {place['id']}, "
                "projected onto the leg's OpenRouteService driving-hgv route"
            ),
        }
        previous = best.get(_norm(name))
        if previous is None or record["off_mi"] < previous["off_mi"]:
            best[_norm(name)] = record

    records = sorted(best.values(), key=lambda r: r["off_mi"])[:MAX_PER_LEG]
    starts = zone_starts(leg)
    paired = 0
    for record in records:
        # Only a place the road runs through can explain a limit drop; a town
        # eight miles off the highway did not cause it.
        if record["off_mi"] <= ENTER_OFF_MI:
            adjusted = paired_mile(record["at_mi"], starts)
            if adjusted is not None:
                record["at_mi"] = adjusted
                record["source"] += ", placed ahead of the speed zone it explains"
                paired += 1
        record["spoken"] = spoken_village(record["name"], record["off_mi"])
    records.sort(key=lambda r: r["at_mi"])
    return records, paired, unspeakable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    only = {frozenset(p.split(":")) for p in args.only.split(";") if ":" in p}

    api_key = os.environ.get("ORS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("set ORS_API_KEY (use 'selfhosted' with the local ORS server)")

    data = load_world()
    index = grid_index(load_places())
    anchors = city_anchors(data)

    per_state: dict[str, int] = {}
    total = paired_total = touched = empty = failed = refused = 0
    empty_legs: list[str] = []
    failed_legs: list[str] = []
    for leg in data["legs"]:
        if only and frozenset((leg["from"], leg["to"])) not in only:
            continue
        try:
            records, paired, unspeakable = bake_leg(leg, data, index, anchors, api_key)
        except Exception as exc:  # a leg ORS cannot route is skipped, not guessed
            failed += 1
            failed_legs.append(f"{leg['from']}:{leg['to']}")
            print(f"  ! {leg['from']}->{leg['to']}: {exc}", file=sys.stderr)
            continue
        refused += unspeakable
        corridor = leg.setdefault("corridor", {})
        kept = [lm for lm in corridor.get("landmarks", ()) if lm.get("category") != "village"]
        corridor["landmarks"] = sorted(kept + records, key=lambda r: r["at_mi"])
        state = str(leg["from"]).rsplit("_", 2)[-2].upper()
        per_state[state] = per_state.get(state, 0) + len(records)
        total += len(records)
        paired_total += paired
        if records:
            touched += 1
        else:
            empty += 1
            empty_legs.append(f"{leg['from']}:{leg['to']}")
        if args.verbose:
            print(
                f"{leg['from']}->{leg['to']}: "
                f"{[(r['spoken'], r['at_mi'], r['off_mi']) for r in records]}"
            )
    print(f"villages: {total} across {touched} legs ({empty} legs with none, {failed} failed)")
    print(f"paired with a speed zone: {paired_total}")
    print(f"names refused as unspeakable: {refused}")
    print("per state: " + ", ".join(f"{k}={v}" for k, v in sorted(per_state.items())))
    report = {
        "total": total,
        "legs_with_villages": touched,
        "legs_without_villages": empty,
        "failed_leg_count": failed,
        "paired_with_zone": paired_total,
        "unspeakable_names_refused": refused,
        "per_state": per_state,
        "empty_legs": empty_legs,
        "failed_legs": failed_legs,
    }
    (CACHE_PATH / "village_bake_report.json").write_text(json.dumps(report, indent=2))
    if args.write:
        save_world(data)
        print("WRITTEN")
    else:
        print("(dry run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
