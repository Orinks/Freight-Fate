"""Make legs that disagree with their own road describe one road.

A 2026-09-30 billboard placement audit found legs whose records describe two
different roads at once: Buffalo to New York speaks Pennsylvania and New
Jersey while its checkpoints stay on the Thruway, Dallas to St. Louis names
Arkansas exits on an I-44 leg, and so on. This script authors the curated
inputs those legs need; the existing tools then rebuild what rides on them::

    uv run python tools/repair_leg_road_agreement.py --write
    uv run python tools/reroute_leg.py --leg a:b --write        # each ROAD_PINS leg
    uv run python tools/reroute_enrich.py --leg a:b --pbf ... --write

Running it twice changes nothing the second time.

WHAT IT WRITES
--------------
* ``route_via`` pins (ROAD_PINS). Each point is READ: a vertex of a Valhalla
  truck route that was asked to pass the named town on the named road with its
  through locations restricted to non-ramp primary-or-better edges, and whose
  map-matched names were checked to be that road.
* A label (RELABEL) where every record but the label agrees on one road.
* Checkpoints for towns on a pinned road that replace ones the reroute drops
  (NEW_CHECKPOINTS); coordinates READ from OpenStreetMap via Nominatim, mile
  left to ``reroute_enrich`` to derive by projection.
* The Miami to Key West highway markers (KEYS_MARKERS), placed from the
  coordinates of the feature each one names.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import bake_landmarks as bl  # noqa: E402
import leg_geometry as lg  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

PIN_SOURCE = (
    "Read 2026-10-01: vertex of a Valhalla truck route through this town with "
    "through locations limited to non-ramp, primary-or-better edges; the edge "
    "map-matches to {road}."
)

THRUWAY = [
    (43.09222, -76.14719, "I-90", "Syracuse"),
    (43.11943, -75.22396, "I-90", "Utica"),
    (42.93989, -74.19001, "I-90", "Amsterdam"),
    (41.94971, -74.02812, "I-87", "Kingston"),
    (41.08045, -73.92125, "I-87", "Nyack"),
    (40.93341, -73.87712, "I-87", "Yonkers"),
]

ROAD_PINS: dict[str, tuple[str, list[tuple[float, float, str, str]]]] = {
    "buffalo_ny_us:new_york_ny_us": (
        "the New York State Thruway: I-90 to Albany, then I-87 down the west bank "
        "of the Hudson. The old route left it at Syracuse for I-81 and NY-17.",
        THRUWAY,
    ),
    "rochester_ny_us:new_york_ny_us": (
        "the New York State Thruway: I-90 to Albany, then I-87 down the west bank "
        "of the Hudson. The old route crossed to the east bank at Newburgh.",
        THRUWAY,
    ),
    "dallas_tx_us:st_louis_mo_us": (
        "I-35 to Oklahoma City, then I-44 through Tulsa and Joplin, which its "
        "route points and checkpoints already follow. The old route ran I-30 and "
        "US-67 through Arkansas.",
        [
            (34.17013, -97.14326, "I-35", "Ardmore"),
            (35.50004, -97.50316, "I-44", "Oklahoma City"),
            (36.09042, -95.94999, "I-44", "Tulsa"),
            (36.62180, -95.15111, "I-44", "Vinita"),
            (37.03953, -94.50987, "I-44", "Joplin"),
            (37.25021, -93.29000, "I-44", "Springfield"),
            (37.96439, -91.76154, "I-44", "Rolla"),
            (38.21576, -91.16718, "I-44", "Sullivan"),
        ],
    ),
    "washington_dc_us:charlottesville_va_us": (
        "US-29 through Warrenton, Culpeper and Madison, as its route points and checkpoints say.",
        [
            (38.70032, -77.78940, "US-29", "Warrenton"),
            (38.48088, -77.98027, "US-29", "Culpeper"),
            (38.37919, -78.25870, "US-29", "Madison"),
            (38.23042, -78.37102, "US-29", "Ruckersville"),
        ],
    ),
    "harrisburg_pa_us:wilmington_de_us": (
        "the Pennsylvania Turnpike (I-76) east toward Downingtown, then Exton and US-202 into "
        "Wilmington, which its route points, checkpoints and both stops follow. The "
        "old route ran PA-283, US-30 and PA-41.",
        [
            (40.056, -75.653, "US-202", "Exton"),
        ],
    ),
    "norfolk_va_us:petersburg_va_us": (
        "US-460 through Windsor, Wakefield and Waverly, the road it is labelled and "
        "its geometry drives. Its route points and checkpoints had followed VA-10 "
        "through Smithfield and Hopewell.",
        [
            (36.80729, -76.74133, "US-460", "Windsor"),
            (36.97339, -76.98741, "US-460", "Wakefield"),
            (37.03296, -77.10031, "US-460", "Waverly"),
        ],
    ),
    "green_bay_wi_us:grand_rapids_mi_us": (
        "I-43 to Milwaukee, I-94 through Chicago on the Dan Ryan and around the lake, "
        "then I-196, as its route points and checkpoints say.",
        [
            (44.10001, -87.72984, "I-43", "Manitowoc"),
            (42.73001, -87.95382, "I-94", "Racine"),
            (42.54999, -87.95229, "I-94", "Kenosha"),
            (41.79999, -87.63091, "I-94", "Chicago (Dan Ryan)"),
            (41.57994, -87.35624, "I-94", "Gary"),
            (42.10017, -86.43437, "I-94", "Benton Harbor"),
            (42.40002, -86.25221, "I-196", "South Haven"),
            (42.78319, -86.07002, "I-196", "Holland"),
        ],
    ),
    "binghamton_ny_us:utica_ny_us": (
        "NY-12 through Greene, Oxford, Norwich and Sherburne, as its checkpoints say.",
        [
            (42.32969, -75.77031, "NY-12", "Greene"),
            (42.43992, -75.59987, "NY-12", "Oxford"),
            (42.52981, -75.52366, "NY-12", "Norwich"),
            (42.68007, -75.49964, "NY-12", "Sherburne"),
            (42.93100, -75.38027, "NY-12", "Waterville"),
        ],
    ),
}

# Harrisburg to Wilmington was labelled US-1, a road none of its records touch.
# READ: map-matching the pinned truck route names the Pennsylvania Turnpike,
# I-76, for 62 percent of its miles; the next road, US-202, carries 17.
RELABEL = {"harrisburg_pa_us:wilmington_de_us": "I-76"}

NEW_CHECKPOINTS = {
    "norfolk_va_us:petersburg_va_us": [
        ("Windsor", "Virginia", 36.80848, -76.74412, "relation 207013"),
        ("Wakefield", "Virginia", 36.96821, -76.98969, "relation 207029"),
        ("Waverly", "Virginia", 37.03591, -77.09541, "relation 207030"),
    ],
}

KEYS_LEG = "miami_fl_us:key_west_fl_us"
# ASSUMED: how far before a feature a forward-only "is ahead" marker speaks,
# the lead the leg's own correctly placed African Queen marker already uses.
AHEAD_LEAD_MI = 3.0
# name -> (lat, lon, the OpenStreetMap element they are read from, at or ahead)
KEYS_MARKERS = {
    "Entering the Florida Keys on the Overseas Highway": (
        25.18241,
        -80.38488,
        "way 996764860, Jewfish Creek Bridge onto Key Largo",
        "at",
    ),
    "Christ of the Abyss": (25.12340, -80.29709, "node 6565241385, offshore of Key Largo", "at"),
    "The Hurricane Monument": (24.91712, -80.63597, "node 4723846456, Florida Keys Memorial", "at"),
    "National Key Deer Refuge": (
        24.67203,
        -81.35684,
        "node 889570872, refuge visitor center",
        "at",
    ),
    "Giant Lobster Betsy": (24.95933, -80.57195, "node 4972396622, Rain Barrel Village", "ahead"),
    "Theater of the Sea": (24.94443, -80.60359, "way 301762362", "ahead"),
    "Robbie's of Islamorada": (24.88274, -80.69074, "node 3058878543", "ahead"),
    "Seven Mile Bridge": (24.70634, -81.12845, "east end of way 996764821", "ahead"),
    "Crossing the Seven Mile Bridge": (24.70634, -81.12845, "east end of way 996764821", "at"),
    "Bahia Honda": (24.66473, -81.26152, "relation 5360500, Bahia Honda State Park", "ahead"),
    "No Name Pub": (24.69817, -81.35123, "way 147639029", "ahead"),
}


def find_leg(world: dict, leg_id: str) -> dict:
    return next(leg for leg in world["legs"] if lg.leg_id_of(leg) == leg_id)


def apply_pins(world: dict) -> list[str]:
    changed = []
    for leg_id, (why, pins) in ROAD_PINS.items():
        leg = find_leg(world, leg_id)
        route_via = [
            {
                "lat": lat,
                "lon": lon,
                "note": f"{town} on {road} -- pins this leg to {why} "
                + PIN_SOURCE.format(road=road)
                if i == 0
                else f"{town} on {road}. " + PIN_SOURCE.format(road=road),
            }
            for i, (lat, lon, road, town) in enumerate(pins)
        ]
        if leg.get("route_via") != route_via:
            leg["route_via"] = route_via
            changed.append(f"{leg_id}: route_via ({len(pins)} pins)")
    for leg_id, label in RELABEL.items():
        leg = find_leg(world, leg_id)
        if leg.get("highway") != label:
            leg["highway"] = label
            changed.append(f"{leg_id}: highway -> {label}")
        for cp in (leg.get("corridor") or {}).get("checkpoints") or []:
            if cp.get("highway") != label:
                cp["highway"] = label
    for leg_id, towns in NEW_CHECKPOINTS.items():
        leg = find_leg(world, leg_id)
        corridor = leg.setdefault("corridor", {})
        checkpoints = corridor.setdefault("checkpoints", [])
        have = {cp["name"] for cp in checkpoints}
        for name, state, lat, lon, element in towns:
            if name in have:
                continue
            checkpoints.append(
                {
                    "name": name,
                    "at_mi": 0.0,
                    "type": "place",
                    "state": state,
                    "highway": leg.get("highway"),
                    "lat": lat,
                    "lon": lon,
                    "source": (
                        f"Real town on {leg.get('highway')}; coordinates read 2026-10-01 from "
                        f"OpenStreetMap {element} via Nominatim; at_mi derived by projecting "
                        "them onto the leg's route geometry."
                    ),
                }
            )
            changed.append(f"{leg_id}: checkpoint {name}")
    return changed


def place_keys_markers(world: dict) -> list[str]:
    leg = find_leg(world, KEYS_LEG)
    geometry = lg.corridor_geometry(leg)
    if geometry is None:
        raise SystemExit(f"{KEYS_LEG} has no dense geometry to place markers on")
    route = [(lat, lon) for lat, lon, _ in geometry]
    raw = bl.route_cum(route)
    scale = float(leg["miles"]) / raw[-1]
    cum = [c * scale for c in raw]
    changed = []
    landmarks = leg["corridor"]["landmarks"]
    for record in landmarks:
        spec = KEYS_MARKERS.get(record.get("name"))
        if record.get("category") != "highway_marker" or spec is None:
            continue
        lat, lon, element, mode = spec
        feature_mi, off_mi, _, _ = bl.project_point_on_route(route, cum, lat, lon)
        lead = AHEAD_LEAD_MI if mode == "ahead" else 0.0
        at_mi = round(max(0.0, feature_mi - lead), 1)
        how = (
            f"at_mi = {feature_mi:.1f} (projection onto the leg's archived dense route "
            f"geometry, {off_mi:.1f} mi off the road) - {lead:.1f} mi assumed lead for a "
            "forward-only 'is ahead' callout"
            if lead
            else f"at_mi = its projection onto the leg's archived dense route geometry "
            f"({off_mi:.1f} mi off the road)"
        )
        source = (
            f"Coordinates read 2026-10-01 from OpenStreetMap {element} via Nominatim; "
            f"derived: {how}."
        )
        update = {"at_mi": at_mi, "lat": lat, "lon": lon, "source": source}
        if any(record.get(k) != v for k, v in update.items()):
            changed.append(f"{KEYS_LEG}: {record['name']} {record.get('at_mi')} -> {at_mi}")
            record.update(update)
    landmarks.sort(key=lambda r: float(r.get("at_mi") or 0.0))
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply (default is a dry run)")
    args = ap.parse_args()
    world = load_world()
    changed = apply_pins(world) + place_keys_markers(world)
    for line in changed:
        print(line)
    print(f"{len(changed)} changes")
    if args.write and changed:
        save_world(world)
    elif changed:
        print("(dry run; pass --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
