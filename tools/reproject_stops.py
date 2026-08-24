"""Put a rerouted leg's truck stops back on the road, or admit they are gone.

A leg's ``stops`` are its curated truck stops, rest areas, weigh stations and
service plazas -- the places a driver is told to pull into. They survive a
reroute because nothing drops them, and that is the problem: their ``at_mi``
was measured on the OLD polyline. A Love's at mile 24.5 of US-181 is not at
mile 24.5 of I-37, and may not be within thirty miles of it. The leg then
promises a blind driver a fuel stop that is not there, which is worse than a
leg with none.

Rescaling the milepost proportionally would be the easy fix and the wrong one:
it produces a number nobody can tell apart from a measurement, which is the
recurring bug this project's provenance rule exists to stop.

So each stop is READ rather than guessed, and only then kept or dropped:

* **It carries coordinates** (2,961 of 3,840 network-wide). Project them onto
  the leg's new polyline. The distance that comes back settles it.
* **It does not.** Look the facility up in OpenStreetMap along the new route
  by name -- these are real named places ("Pilot Travel Center Cornersville",
  "Flying J Travel Center Wells"), and if one is beside the new road, OSM has
  it. A match supplies real coordinates, so the stop comes back better off
  than it was.
* **Neither works.** The stop is not on this road any more. It is dropped and
  NAMED in the report, so it can be re-curated onto whatever leg now passes
  it rather than quietly disappearing.

HOW FAR OFF-ROUTE IS STILL "ON THIS LEG"
----------------------------------------
Measured, not chosen: across the 2,961 checked-in stops that carry
coordinates, the distance from the stop to its own leg's route runs 0.21 mi
at the median, 3.42 at the 95th percentile and 4.36 at the 99th. So 4.4 miles
is the outer edge of everything curation has ever accepted, and a stop
further out than that is not a stop this leg passes.

    uv run --group tooling python tools/reproject_stops.py --legs-file legs.txt
    uv run --group tooling python tools/reproject_stops.py --leg a:b --write
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import leg_geometry  # noqa: E402
from bake_landmarks import project_on_route, route_cum  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

# The 99th percentile of how far the network's own curated stops sit from
# their leg's route. See the module docstring.
MAX_OFF_ROUTE_MI = 4.4

# How often to drop an Overpass probe when hunting a stop that has no
# coordinates, and how wide each probe looks. The radius comfortably covers
# the gate above, and the spacing is under twice the radius so the corridor
# has no unsearched gaps.
PROBE_STEP_MI = 8.0
PROBE_RADIUS_M = 9_000

# Words that appear in half the truck stops in America. They say what kind of
# place it is, not which one, so a name match must not rest on them.
GENERIC_NAME_WORDS = {
    "travel",
    "center",
    "centre",
    "stop",
    "stops",
    "plaza",
    "truck",
    "trucks",
    "service",
    "services",
    "rest",
    "area",
    "station",
    "fuel",
    "weigh",
    "scales",
    "the",
    "and",
    "of",
    "at",
    "on",
}

# A candidate must share at least this share of the stop's own distinctive
# words. Half is deliberate: "Love's Travel Stop Cayce" against OSM's
# "Love's Travel Stop" shares "love's" and misses "cayce", and that is a
# match; it shares nothing with "Pilot", and that is not.
MIN_NAME_OVERLAP = 0.5

REPROJECT_SOURCE = (
    "Position re-measured on this leg's new route geometry after the reroute "
    "({off} mi off-route at closest approach); the facility's own coordinates "
    "are unchanged."
)
RECOVERED_SOURCE = (
    "Position read from OpenStreetMap after the reroute: {osm} matched by name "
    "beside the leg's new route ({off} mi off-route at closest approach). The "
    "previous milepost was measured on the polyline this leg no longer follows."
)


def _tokens(name: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", str(name or "").lower())
    return {w for w in words if w not in GENERIC_NAME_WORDS}


def name_score(stop_name: str, candidate_name: str) -> float:
    """Share of the stop's distinctive words the candidate also carries."""
    wanted = _tokens(stop_name)
    if not wanted:
        return 0.0
    return len(wanted & _tokens(candidate_name)) / len(wanted)


def _probe_query(lat: float, lon: float, radius_m: int) -> str:
    """The corridor POI query the original curation used, unchanged.

    Reused verbatim rather than narrowed so a stop is looked for exactly where
    it would have been found in the first place.
    """
    return f"""
    [out:json][timeout:60];
    (
      node["highway"~"services|rest_area"](around:{radius_m},{lat},{lon});
      way["highway"~"services|rest_area"](around:{radius_m},{lat},{lon});
      node["amenity"="fuel"](around:{radius_m},{lat},{lon});
      way["amenity"="fuel"](around:{radius_m},{lat},{lon});
      node["amenity"="parking"]["hgv"~"yes|designated"](around:{radius_m},{lat},{lon});
      way["amenity"="parking"]["hgv"~"yes|designated"](around:{radius_m},{lat},{lon});
      node["amenity"="weighbridge"](around:{radius_m},{lat},{lon});
      way["amenity"="weighbridge"](around:{radius_m},{lat},{lon});
      node["name"](around:{radius_m},{lat},{lon})["name"~"Love's|Pilot|Flying J|TravelCenters|TA |Petro|Road Ranger|Buc-ee|truck stop|travel center|weigh",i];
      way["name"](around:{radius_m},{lat},{lon})["name"~"Love's|Pilot|Flying J|TravelCenters|TA |Petro|Road Ranger|Buc-ee|truck stop|travel center|weigh",i];
    );
    out tags center 60;
    """  # noqa: E501


def corridor_pois(route: list[tuple[float, float]], cum: list[float]) -> list[dict[str, Any]]:
    """Every named POI OSM knows of beside the leg's new route."""
    import build_interchanges as bi

    found: dict[tuple, dict[str, Any]] = {}
    last = -1e9
    for (lat, lon), at_mi in zip(route, cum, strict=False):
        if at_mi - last < PROBE_STEP_MI and at_mi != cum[-1]:
            continue
        last = at_mi
        payload = bi._cached_post(_probe_query(lat, lon, PROBE_RADIUS_M), rate_limit=1.0)
        if payload is None:
            continue
        for element in payload.get("elements", ()):
            name = (element.get("tags") or {}).get("name")
            if not name:
                continue
            centre = element.get("center") or element
            if centre.get("lat") is None:
                continue
            found[(element["type"], element["id"])] = {
                "name": str(name),
                "lat": float(centre["lat"]),
                "lon": float(centre["lon"]),
                "kind": str((element.get("tags") or {}).get("amenity") or "")
                or str((element.get("tags") or {}).get("highway") or ""),
            }
    return list(found.values())


def reproject_leg(leg: dict[str, Any], max_off_mi: float) -> dict[str, Any]:
    """Re-place every stop on the leg's new route. Returns a per-stop report."""
    stops = list(leg.get("stops") or ())
    result: dict[str, Any] = {"kept": [], "recovered": [], "dropped": [], "stops": []}
    if not stops:
        return result
    shape = leg_geometry.archived_shape(f"{leg['from']}:{leg['to']}")
    if shape is None:
        result["dropped"] = [(s.get("name"), "no archived route geometry") for s in stops]
        result["stops"] = stops
        return result

    route = [(lat, lon) for lon, lat in shape]
    raw_cum = route_cum(route)
    scale = float(leg["miles"]) / (raw_cum[-1] or 1.0)
    cum = [c * scale for c in raw_cum]

    pois: list[dict[str, Any]] | None = None
    kept: list[dict[str, Any]] = []
    for stop in stops:
        lat, lon = stop.get("lat"), stop.get("lon")
        recovered_from = None
        if lat is None or lon is None:
            # Read it off the map rather than rescaling a number nobody can
            # then tell apart from a measurement.
            if pois is None:
                pois = corridor_pois(route, cum)
            best, best_score, best_off = None, 0.0, float("inf")
            for poi in pois:
                score = name_score(str(stop.get("name", "")), poi["name"])
                if score < MIN_NAME_OVERLAP:
                    continue
                _, off = project_on_route(route, cum, poi["lat"], poi["lon"])
                if (score, -off) > (best_score, -best_off):
                    best, best_score, best_off = poi, score, off
            if best is None:
                result["dropped"].append(
                    (stop.get("name"), "no such facility beside the new route")
                )
                continue
            lat, lon = best["lat"], best["lon"]
            recovered_from = f'{best["kind"] or "POI"} "{best["name"]}"'

        at_mi, off_mi = project_on_route(route, cum, float(lat), float(lon))
        if off_mi > max_off_mi:
            result["dropped"].append((stop.get("name"), f"{off_mi:.1f} mi off the new route"))
            continue
        moved = stop.copy()
        moved["at_mi"] = round(max(0.0, min(float(leg["miles"]), at_mi)), 1)
        moved["lat"] = round(float(lat), 5)
        moved["lon"] = round(float(lon), 5)
        note = (
            RECOVERED_SOURCE.format(osm=recovered_from, off=round(off_mi, 2))
            if recovered_from
            else REPROJECT_SOURCE.format(off=round(off_mi, 2))
        )
        moved["source"] = f"{stop.get('source', '').rstrip()} {note}".strip()
        kept.append(moved)
        (result["recovered"] if recovered_from else result["kept"]).append(
            (stop.get("name"), moved["at_mi"], round(off_mi, 2))
        )

    kept.sort(key=lambda s: float(s["at_mi"]))
    result["stops"] = kept
    return result


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--leg", action="append", default=[], help="repeatable, 'from_slug:to_slug'")
    ap.add_argument("--legs-file", type=Path, help="one leg id per line")
    ap.add_argument("--max-off-mi", type=float, default=MAX_OFF_ROUTE_MI)
    ap.add_argument("--write", action="store_true", help="apply (default is a dry run)")
    args = ap.parse_args()

    keys = list(args.leg)
    if args.legs_file:
        keys += [
            line.strip()
            for line in args.legs_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    if not keys:
        ap.error("--leg or --legs-file is required")

    data = load_world()
    by_key = {f"{leg['from']}:{leg['to']}": leg for leg in data["legs"]}
    totals = {"kept": 0, "recovered": 0, "dropped": 0}
    for key in keys:
        leg = by_key.get(key)
        if leg is None:
            print(f"{key}: no such leg")
            continue
        report = reproject_leg(leg, args.max_off_mi)
        if not (report["kept"] or report["recovered"] or report["dropped"]):
            continue
        print(f"\n{key} ({leg.get('highway')}), {leg.get('miles')} mi")
        for name, at_mi, off in report["kept"]:
            print(f"    kept       {name} -> mile {at_mi} ({off} mi off-route)")
        for name, at_mi, off in report["recovered"]:
            print(f"    RECOVERED  {name} -> mile {at_mi} ({off} mi off-route, found in OSM)")
        for name, why in report["dropped"]:
            print(f"    DROPPED    {name}: {why}")
        for bucket in totals:
            totals[bucket] += len(report[bucket])
        leg["stops"] = report["stops"]

    print(
        f"\n{totals['kept']} stops re-measured, {totals['recovered']} recovered from OSM, "
        f"{totals['dropped']} dropped as no longer on the road"
    )
    if totals["dropped"]:
        print("A dropped stop is real and still exists -- it is simply not on THIS leg")
        print("any more. Re-curate it onto whichever leg now passes it.")
    if args.write:
        save_world(data)
        print("\nWrote the world source -- now run: uv run python tools/index_world.py")
    else:
        print("\n(dry run; pass --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
