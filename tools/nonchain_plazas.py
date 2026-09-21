"""Say what each unbranded service plaza really is, from OpenStreetMap.

A ``service_plaza`` in this game is a toll road's own plaza, entered from the
mainline. The map import (``tools/enrich_routes_pois.py``) gave that type to
every OpenStreetMap feature tagged ``highway=services``, and U.S. mappers put
that tag on a good many things that are not one: the lot of an independent
truck stop, a convenience store at an interchange, and now and then a welder
or an industrial supplier. ff-core's ``data::branded_plazas`` already reads
the chain-named ones as travel centers at load. This tool handles the rest:
the service plazas with no chain at the head of their name and no "service
plaza" or "service area" in it.

Two steps, so the second is deterministic and offline:

    uv run --group tooling python tools/nonchain_plazas.py --read-osm
    uv run --group tooling python tools/nonchain_plazas.py --read-osm --second-pass
    uv run python tools/nonchain_plazas.py --compile
        Reads the cached Geofabrik state extracts, one at a time, into raw
        dumps under ``.route-cache/nonchain-plazas/``: first around each
        record's coordinate, then at the feature of every record that was only
        matched by name. ``--compile`` merges what was found into
        ``tools/nonchain_plazas_evidence.json``, which is committed. READ
        values.

    uv run python tools/nonchain_plazas.py            # dry run
    uv run python tools/nonchain_plazas.py --write    # apply
        Decides each record from the evidence file (``decide_place`` holds the
        rules, in order, each saying read or derived) and corrects the source.
        Then ``tools/index_world.py``.

Idempotent: a corrected record no longer matches the candidate rule, and a
removed record is gone.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from world_source import load_world, save_world  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PBF_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
RAW_DIR = ROOT / ".route-cache" / "nonchain-plazas"
EVIDENCE_PATH = Path(__file__).resolve().parent / "nonchain_plazas_evidence.json"
EARTH_RADIUS_MI = 3958.7613

# Mirrors ff-core `data::world_constants::TRUCK_STOP_CHAINS`.
CHAINS = (
    "love's", "pilot", "flying j", "ta ", "travelcenters", "petro", "road ranger",
    "one9", "sapp bros", "sapp brothers", "bosselman", "iowa 80", "little america",
    "ambest", "roady's", "stamart", "onvo", "kwik trip", "kwik star",
)  # fmt: skip
# Mirrors ff-core `data::branded_plazas::PLAZA_NAME_PHRASES`.
PLAZA_NAME_PHRASES = ("service plaza", "service area")

# Every tagged feature this close to a record is written to the raw dump, and
# a feature of the same name is looked for this much farther out. Both are
# search windows, not verdicts: the cut is made on the measured distances.
NEAR_MI = 0.35
SAME_NAME_MI = 6.0
# A record with no coordinate of its own is placed from its mile marker on the
# leg's geometry, which is a projection, so only a name can identify it.

OSM_KEYS = (
    "name", "brand", "operator", "amenity", "shop", "highway", "hgv",
    "fuel:HGV_diesel", "fuel:diesel", "capacity:hgv", "man_made", "industrial",
    "craft", "office", "building", "landuse", "tourism", "toll", "access",
    "disused:amenity", "abandoned:amenity", "was:amenity", "disused:highway",
)  # fmt: skip
FEATURE_KEYS = (
    "amenity", "shop", "man_made", "industrial", "craft", "office", "tourism",
    "disused:amenity", "abandoned:amenity", "was:amenity",
)  # fmt: skip


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


def norm_name(name: Any) -> str:
    text = str(name or "").lower().replace("’", "'").replace("&", " and ")
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text).split())


def chain_of(name: str) -> str | None:
    lowered = " ".join(str(name).lower().replace("’", "'").split())
    for chain in CHAINS:
        if lowered.startswith(chain) or lowered == chain.strip():
            return chain
    return None


def is_candidate(stop: dict[str, Any]) -> bool:
    """A service plaza with no chain at the head of its name that does not
    name itself a service plaza or a service area."""
    if stop.get("type") != "service_plaza":
        return False
    name = str(stop.get("name") or "")
    if chain_of(name) is not None or CONFIRMED_NOTE in str(stop.get("source") or ""):
        return False
    return not any(phrase in name.lower() for phrase in PLAZA_NAME_PHRASES)


def state_at(leg: dict[str, Any], cities: dict[str, Any], at_mi: float) -> list[str]:
    """Full state names the record may be in, likeliest first."""
    crossings = sorted(
        (leg.get("corridor") or {}).get("state_crossings") or [],
        key=lambda c: float(c.get("at_mi", 0.0)),
    )
    names: list[str] = []
    if crossings:
        current = str(crossings[0].get("from_state") or "")
        for crossing in crossings:
            if float(crossing.get("at_mi", 0.0)) <= at_mi:
                current = str(crossing.get("state") or current)
        names.append(current)
        # A mile marker is a projection: near a line, either side is possible.
        for crossing in crossings:
            if abs(float(crossing.get("at_mi", 0.0)) - at_mi) <= 15.0:
                names.extend([str(crossing.get("from_state")), str(crossing.get("state"))])
    out: list[str] = []
    for name in names:
        if name and name not in out:
            out.append(name)
    return out


def record_key(stop: dict[str, Any], lat: float, lon: float) -> str:
    return f"{stop.get('name')}|{lat:.5f}|{lon:.5f}"


def list_candidates(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Every candidate with the coordinate it is looked up at."""
    from reverse_pair_stops import _point_at, _polyline  # heavy import, lazy

    cities = data["cities"]
    rows: list[dict[str, Any]] = []
    for leg in data["legs"]:
        line = None
        for stop in leg.get("stops") or []:
            if not is_candidate(stop):
                continue
            lat, lon = stop.get("lat"), stop.get("lon")
            coordinate = "read"
            if lat is None or lon is None:
                if line is None:
                    line = _polyline(leg)
                point = _point_at(line, float(stop.get("at_mi") or 0.0))
                if point is None:
                    continue
                lat, lon = point
                coordinate = "derived from the mile marker on the leg's geometry"
            states = state_at(leg, cities, float(stop.get("at_mi") or 0.0))
            if not states:
                states = []
            rows.append(
                {
                    "key": record_key(stop, float(lat), float(lon)),
                    "leg": f"{leg['from']}->{leg['to']}",
                    "name": stop.get("name"),
                    "at_mi": stop.get("at_mi"),
                    "lat": round(float(lat), 6),
                    "lon": round(float(lon), 6),
                    "coordinate": coordinate,
                    "states": states,
                    "end_states": [
                        str(cities.get(leg[end], {}).get("state", "")) for end in ("from", "to")
                    ],
                    "source": stop.get("source"),
                    "services": stop.get("services"),
                    "parking": stop.get("parking"),
                    "parking_spaces": stop.get("parking_spaces"),
                    "vehicle_access": stop.get("vehicle_access"),
                    "directions": stop.get("directions"),
                }
            )
    return rows


# --------------------------------------------------------------------------
# Reading the extracts


def _slug(state: str) -> str:
    return state.strip().lower().replace(" ", "-")


STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
    "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin",
    "WY": "Wyoming",
}  # fmt: skip


def read_state(state: str, points: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Tagged OSM features near each point, from one state extract."""
    import osmium

    pbf = PBF_DIR / f"{_slug(state)}-latest.osm.pbf"
    if not pbf.exists():
        print(f"  no extract for {state}: {pbf}")
        return {}
    cell = 0.1  # degrees; SAME_NAME_MI is under 0.1 degree of latitude
    grid: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for point in points:
        ci, cj = int(math.floor(point["lat"] / cell)), int(math.floor(point["lon"] / cell))
        for di in (-1, 0, 1):
            for dj in (-2, -1, 0, 1, 2):
                grid[(ci + di, cj + dj)].append(point)
    found: dict[str, list[dict[str, Any]]] = defaultdict(list)

    entities = osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY
    processor = (
        osmium.FileProcessor(str(pbf), entities=entities)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter(*FEATURE_KEYS, "highway", "building", "landuse"))
    )
    for obj in processor:
        tags = obj.tags
        highway = tags.get("highway")
        featured = any(key in tags for key in FEATURE_KEYS)
        if highway not in (None, "services", "rest_area") and not featured:
            continue  # a road
        named = "name" in tags or "brand" in tags or "operator" in tags
        if highway not in ("services", "rest_area") and not featured and not named:
            continue  # a bare building or landuse polygon
        is_way = hasattr(obj, "nodes")
        bbox = None
        if is_way:
            lats, lons = [], []
            for node in obj.nodes:
                loc = node.location
                if loc.valid():
                    lats.append(loc.lat)
                    lons.append(loc.lon)
            if not lats:
                continue
            bbox = (min(lats), min(lons), max(lats), max(lons))
            lat, lon = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        else:
            loc = obj.location
            if not loc.valid():
                continue
            lat, lon = loc.lat, loc.lon
        nearby = grid.get((int(math.floor(lat / cell)), int(math.floor(lon / cell))))
        if not nearby:
            continue
        feature = None
        feature_names = {norm_name(tags.get(k)) for k in ("name", "brand", "operator")} - {""}
        for point in nearby:
            dist = haversine_mi(point["lat"], point["lon"], lat, lon)
            inside = bbox is not None and (
                bbox[0] <= point["lat"] <= bbox[2] and bbox[1] <= point["lon"] <= bbox[3]
            )
            same_name = norm_name(point["name"]) in feature_names
            similar = False
            if not same_name and point.get("loose"):
                # Second pass, for a record no same-named feature answered:
                # a services or fuel feature that shares the name's first
                # word. Kept apart from a same-name match and judged by eye.
                word = norm_name(point["name"]).split(" ")[0]
                similar = (
                    len(word) >= 4
                    and any(word in name.split(" ") for name in feature_names)
                    and (highway in ("services", "rest_area") or tags.get("amenity") == "fuel")
                )
            if not (dist <= NEAR_MI or inside or ((same_name or similar) and dist <= SAME_NAME_MI)):
                continue
            if feature is None:
                feature = {
                    "osm": ("way" if is_way else "node"),
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "tags": {k: tags.get(k) for k in OSM_KEYS if k in tags},
                }
                if bbox is not None:
                    feature["bbox"] = [round(v, 6) for v in bbox]
            found[point["key"]].append(
                {
                    **feature,
                    "dist_mi": round(dist, 4),
                    "inside": inside,
                    "same_name": same_name,
                    **({"similar_name": True} if similar else {}),
                }
            )
    return found


def _load_raw() -> dict[str, list[dict[str, Any]]]:
    raw: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(RAW_DIR.glob("*.json")):
        for key, features in json.loads(path.read_text(encoding="utf-8")).items():
            raw[key].extend(features)
    return raw


def _second_pass_points(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Where the first pass did not look.

    A record identified by name sits away from its feature, so what is mapped
    inside that feature was never dumped: look again at the feature ("@").
    A record nothing answered is looked for under a looser name ("?").
    """
    raw = _load_raw()
    points: dict[str, dict[str, Any]] = {}
    for row in rows:
        same = sorted(
            (f for f in raw.get(row["key"], []) if f["same_name"]), key=lambda f: f["dist_mi"]
        )
        if same and same[0]["dist_mi"] <= AT_COORDINATE_MI:
            continue
        if same:
            point = {**row, "key": "@" + row["key"], "lat": same[0]["lat"], "lon": same[0]["lon"]}
        else:
            point = {**row, "key": "?" + row["key"], "loose": True}
        points.setdefault(point["key"], point)
    return list(points.values())


def read_osm(data: dict[str, Any], only: list[str], second_pass: bool = False) -> None:
    rows = list_candidates(data)
    if second_pass:
        rows = _second_pass_points(rows)
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique.setdefault(row["key"], row)
    by_state: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unique.values():
        # A leg with no recorded crossing stays in its endpoints' state.
        states = list(row["states"]) or sorted(
            {STATE_NAMES[code] for code in row["end_states"] if code in STATE_NAMES}
        )
        for state in states:
            by_state[state].append(row)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for state in sorted(by_state):
        if only and _slug(state) not in only:
            continue
        out = RAW_DIR / f"{_slug(state)}{'.pass2' if second_pass else ''}.json"
        if out.exists():
            print(f"{state}: cached")
            continue
        print(f"{state}: {len(by_state[state])} record(s)", flush=True)
        found = read_state(state, by_state[state])
        out.write_text(json.dumps(found, indent=1, sort_keys=True), encoding="utf-8")
        print(f"  features near {len(found)} of them", flush=True)


# --------------------------------------------------------------------------
# From the raw dumps to one evidence record per place

# A same-named feature this close IS the record's feature. Measured
# 2026-09-17 over the 151 places with a same-named feature: 110 sit at 0.0000
# to 0.0004 miles (the rounding of a five-decimal coordinate), then nothing
# until 0.0254. The cut is the bottom of that gap, a factor of 60 wide. Every
# match past it is a record whose coordinate was projected from a mile marker
# or a feature OpenStreetMap has redrawn since the import.
AT_COORDINATE_MI = 0.001

# Tags that say nothing about what a place is.
_NOISE_KEYS = {"building", "landuse", "name", "operator", "access", "toll"}


def _is_noise(tags: dict[str, str]) -> bool:
    if tags.get("man_made") in {"pipeline", "bridge", "mast", "surveillance", "utility_pole"}:
        return True
    return set(tags) <= _NOISE_KEYS


def _inside(bbox: list[float], feature: dict[str, Any]) -> bool:
    return bbox[0] <= feature["lat"] <= bbox[2] and bbox[1] <= feature["lon"] <= bbox[3]


def _within(match: dict[str, Any], features: list[dict[str, Any]]) -> list[dict[str, str]]:
    """What OpenStreetMap maps inside the matched area's own bounds.

    Containment, not a radius: there is no distance to tune. A node has no
    bounds, so nothing is within it.
    """
    bbox = match.get("bbox")
    if not bbox:
        return []
    seen: dict[str, dict[str, str]] = {}
    for other in features:
        if other["tags"] == match["tags"] and other["lat"] == match["lat"]:
            continue
        if _is_noise(other["tags"]) or not _inside(bbox, other):
            continue
        seen.setdefault(json.dumps(other["tags"], sort_keys=True), other["tags"])
    return [seen[key] for key in sorted(seen)]


def compile_evidence(data: dict[str, Any]) -> dict[str, Any]:
    """One evidence record per place, merged into the committed file.

    Merged, not replaced: once the corrections are written the records stop
    being candidates, and their evidence must outlive that.
    """
    raw = _load_raw()
    places: dict[str, Any] = {}
    if EVIDENCE_PATH.exists():
        places = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))["places"]
    for row in list_candidates(data):
        key = row["key"]
        features = sorted(raw.get(key, []), key=lambda f: (f["dist_mi"], json.dumps(f["tags"])))
        same = [f for f in features if f["same_name"]]
        entry: dict[str, Any] = {
            "name": row["name"],
            "lat": row["lat"],
            "lon": row["lon"],
            "coordinate": row["coordinate"],
            "osm": None,
            "within": [],
        }
        if same:
            match = same[0]
            at_coordinate = match["dist_mi"] <= AT_COORDINATE_MI
            entry["osm"] = {
                "element": match["osm"],
                "dist_mi": match["dist_mi"],
                "identified": "at the coordinate" if at_coordinate else "by name",
                "tags": match["tags"],
            }
            if at_coordinate:
                entry["within"] = _within(match, features)
            else:
                again = [f for f in raw.get("@" + key, []) if f["same_name"]]
                again.sort(key=lambda f: f["dist_mi"])
                if again:
                    entry["within"] = _within(again[0], raw["@" + key])
        else:
            entry["nearest"] = [
                {"dist_mi": f["dist_mi"], "tags": f["tags"]}
                for f in features
                if not _is_noise(f["tags"]) and f["dist_mi"] <= NEAR_MI
            ][:4]
            similar = sorted(
                (f for f in raw.get("?" + key, []) if f.get("similar_name")),
                key=lambda f: f["dist_mi"],
            )
            entry["similar_name"] = [
                {"dist_mi": f["dist_mi"], "tags": f["tags"]} for f in similar[:3]
            ]
        places[key] = entry
    return places


def write_evidence(places: dict[str, Any]) -> None:
    payload = {
        "meta": {
            "source": (
                "OpenStreetMap features read from the Geofabrik U.S. state extracts "
                f"(*-latest.osm.pbf), accessed {ACCESSED}. (c) OpenStreetMap contributors, "
                "ODbL. Written by tools/nonchain_plazas.py --read-osm, then --compile."
            ),
            "kind": "read",
            "at_coordinate_mi": AT_COORDINATE_MI,
            "same_name_window_mi": SAME_NAME_MI,
            "places": len(places),
        },
        "places": {key: places[key] for key in sorted(places)},
    }
    EVIDENCE_PATH.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Deciding

ACCESSED = "2026-09-17"
HGV_YES = {"yes", "designated"}
# An operator tag that names the road's own authority or concession.
TOLL_OPERATOR_WORDS = ("thruway", "turnpike", "toll road")
# Mirrors ff-core `data::branded_plazas::TRUCK_STOP_NAME_PHRASES`: the names
# the load-time screen retypes, so this tool leaves those records alone unless
# OpenStreetMap gives it something to READ.
TRUCK_STOP_NAME_PHRASES = ("truck", "travel center", "travel centre", "travel stop")
# Mirrors ff-core `data::world_constants::TRUCK_STOP_NAME_WORDS`.
STOP_NAME_WORDS = (
    "truck", "travel", "plaza", "rest area", "service area", "traffic center",
    "fuel center", "welcome center",
)  # fmt: skip
FUEL_NAME_WORDS = ("fuel", "gas", "diesel", "petroleum")
REST_AREA_NAME_WORDS = ("welcome center", "rest area")

# Records judged by hand, each with the evidence. Not a brand list: one entry
# is one place.
REVIEWED: dict[str, tuple[str, str]] = {
    "Rest Area CT-15 (South Bound)": (
        "remove",
        "its own name puts it on CT-15, the Wilbur Cross Parkway, and the legs that list it are "
        "I-95 and I-91; OpenStreetMap has the highway=services area 1.7 and 3.1 miles from "
        "where those legs place it. ConnDOT prohibits commercial vehicles on the Merritt and "
        "Wilbur Cross Parkways, so no truck can reach it",
    ),
    "Rocky Mountain Truck Centers": (
        "remove",
        "OpenStreetMap has a bare highway=services node; the business's own listings "
        "(truckstopsandservices.com, Yelp, read 2026-09-17) are a heavy-duty truck repair shop "
        "at 2515 E Butler Ave, Flagstaff, beside Little America, with no fuel, food or parking",
    ),
}


def hgv_evidence(entry: dict[str, Any]) -> list[str]:
    """What OpenStreetMap says about trucks at this place. READ values."""
    found: list[str] = []
    osm = entry.get("osm") or {}
    tags = osm.get("tags") or {}
    if tags.get("hgv") in HGV_YES:
        found.append(f"hgv={tags['hgv']} on the {tags.get('highway') or tags.get('amenity')} area")
    for inner in [tags, *entry.get("within", [])]:
        amenity = inner.get("amenity")
        if amenity == "fuel" and (
            (inner is not tags and inner.get("hgv") in HGV_YES)
            or inner.get("fuel:HGV_diesel") in HGV_YES
            or "capacity:hgv" in inner
        ):
            found.append("amenity=fuel with HGV lanes or HGV diesel")
        elif amenity == "parking" and (
            inner.get("hgv") in HGV_YES
            or "capacity:hgv" in inner
            or "truck" in str(inner.get("name") or "").lower()
        ):
            found.append("amenity=parking for HGVs")
        elif amenity == "weighbridge":
            found.append("a truck scale (amenity=weighbridge)")
        elif amenity == "truck_stop":
            found.append("amenity=truck_stop")
    out: list[str] = []
    for item in found:
        if item not in out:
            out.append(item)
    return out


def fuel_evidence(entry: dict[str, Any]) -> bool:
    tags = (entry.get("osm") or {}).get("tags") or {}
    if tags.get("amenity") == "fuel" or tags.get("fuel:diesel") == "yes":
        return True
    return any(inner.get("amenity") == "fuel" for inner in entry.get("within", []))


def _is_bare(tags: dict[str, str]) -> bool:
    return set(tags) <= _NOISE_KEYS | {"highway"}


def _multi_store(entry: dict[str, Any]) -> bool:
    tags = (entry.get("osm") or {}).get("tags") or {}
    return bool(tags.get("brand")) and norm_name(tags["brand"]) == norm_name(entry["name"])


def decide_place(entry: dict[str, Any], tolled_leg: bool, curated_parking: bool) -> dict[str, str]:
    """The verdict for one place from its own evidence.

    ``verdict`` is a stop type, ``remove``, ``screen`` (the load-time screen
    retypes it from its name, so the data is left alone) or ``unverified``.
    """
    name = str(entry["name"])
    lowered = name.lower()
    if name in REVIEWED:
        verdict, why = REVIEWED[name]
        return {"verdict": verdict, "kind": "read", "why": why}
    osm = entry.get("osm")
    identified = bool(osm) and (osm["identified"] == "at the coordinate" or not _multi_store(entry))
    how = ""
    if identified:
        tags = osm["tags"]
        how = (
            "the OpenStreetMap feature at the record's coordinate"
            if osm["identified"] == "at the coordinate"
            else f"the OpenStreetMap feature of the same name {osm['dist_mi']:.1f} miles away"
        )
        operator = str(tags.get("operator") or "")
        if any(word in operator.lower() for word in TOLL_OPERATOR_WORDS):
            return {
                "verdict": "service_plaza",
                "kind": "read",
                "why": f"{how} is highway=services operated by {operator}",
            }
        if tags.get("highway") == "services" and tolled_leg and "travel plaza" in lowered:
            return {
                "verdict": "service_plaza",
                "kind": "derived",
                "why": (
                    f"{how} is highway=services, the name says travel plaza and the leg "
                    "carries a toll authority's charge"
                ),
            }
    if "concession" in lowered:
        return {
            "verdict": "service_plaza",
            "kind": "derived",
            "why": "the name says concession, a turnpike authority's word for its own plazas",
        }
    if curated_parking:
        return {
            "verdict": "service_plaza",
            "kind": "derived",
            "why": "a curated pass surveyed the truck parking and kept the type",
        }
    if identified:
        tags = osm["tags"]
        if tags.get("access") in {"customers", "private", "no"}:
            operator = str(tags.get("operator") or "")
            return {
                "verdict": "remove",
                "kind": "read",
                "why": f"{how} is tagged access={tags['access']}"
                + (f", operator {operator}" if operator else ""),
            }
        trucks = hgv_evidence(entry)
        if trucks:
            return {
                "verdict": "travel_center",
                "kind": "read",
                "why": f"{how} carries " + "; ".join(trucks),
            }
    if any(phrase in lowered for phrase in TRUCK_STOP_NAME_PHRASES):
        return {"verdict": "screen", "kind": "derived", "why": "the name says truck stop"}
    if identified:
        tags = osm["tags"]
        if any(word in lowered for word in REST_AREA_NAME_WORDS) and not fuel_evidence(entry):
            return {
                "verdict": "public_rest_area",
                "kind": "derived",
                "why": f"the name says so and {how} maps no fuel within it",
            }
        if any(word in lowered for word in FUEL_NAME_WORDS):
            return {
                "verdict": "fuel_station",
                "kind": "read" if fuel_evidence(entry) else "derived",
                "why": f"the name says fuel and {how} maps nothing for trucks",
            }
        if any(word in lowered for word in STOP_NAME_WORDS):
            return {
                "verdict": "travel_center",
                "kind": "derived",
                "why": (
                    "the name carries a word the access screen already reads as truck-serving, "
                    f"{how} names no toll authority and the leg carries no toll"
                ),
            }
        if fuel_evidence(entry) or tags.get("shop") == "convenience":
            return {
                "verdict": "fuel_station",
                "kind": "read",
                "why": f"{how} maps fuel or a convenience store and nothing for trucks",
            }
        if _is_bare(tags):
            return {
                "verdict": "remove",
                "kind": "read",
                "why": (
                    f"{how} is a bare highway=services {osm['element']} with no fuel, parking "
                    "or food mapped within it, and the name is another kind of business"
                ),
            }
    elif osm and (osm["tags"].get("amenity") == "fuel" or osm["tags"].get("shop")):
        return {
            "verdict": "fuel_station",
            "kind": "derived",
            "why": (
                f"the nearest OpenStreetMap feature of the brand, {osm['dist_mi']:.2f} miles away, "
                "is a fuel station or convenience store; this record's own feature was not found"
            ),
        }
    return {"verdict": "unverified", "kind": "assumed", "why": "nothing read"}


def decide(data: dict[str, Any], places: dict[str, Any]) -> dict[str, dict[str, str]]:
    """A verdict per place key, names inheriting where their own place is silent."""
    tolled: dict[str, bool] = defaultdict(bool)
    curated: dict[str, bool] = defaultdict(bool)
    legs = {f"{leg['from']}->{leg['to']}": leg for leg in data["legs"]}
    rows = list_candidates(data)
    for row in rows:
        corridor = legs[row["leg"]].get("corridor") or {}
        tolled[row["key"]] |= bool(corridor.get("toll_events"))
        curated[row["key"]] |= row["parking"] == "confirmed"
    verdicts = {
        key: decide_place(places[key], tolled[key], curated[key])
        for key in sorted({row["key"] for row in rows})
        if key in places
    }
    # A copy placed from a mile marker is the same place as the record it was
    # copied from. Where a name's identified places all agree, the ones with
    # no evidence of their own take that verdict. Never for a multi-store
    # brand: another QuikTrip is another store.
    by_name: dict[str, set[str]] = defaultdict(set)
    for key, verdict in verdicts.items():
        entry = places[key]
        at_coordinate = (entry.get("osm") or {}).get("identified") == "at the coordinate"
        decided = verdict["verdict"] not in {"unverified", "screen"}
        if decided and at_coordinate and not _multi_store(entry):
            by_name[entry["name"]].add(verdict["verdict"])
    for key, verdict in verdicts.items():
        name = places[key]["name"]
        if _multi_store(places[key]):
            continue
        if verdict["verdict"] in {"unverified", "screen"} and len(by_name.get(name, ())) == 1:
            inherited = next(iter(by_name[name]))
            if verdict["verdict"] == "screen" and inherited != "remove":
                continue
            verdicts[key] = {
                "verdict": inherited,
                "kind": "derived",
                "why": (
                    "same name as a record identified at its coordinate; this one has no "
                    "coordinate OpenStreetMap answers at"
                ),
            }
    return verdicts


# --------------------------------------------------------------------------
# Applying


def _retyped(stop: dict[str, Any], verdict: dict[str, str]) -> dict[str, Any]:
    from enrich_routes_pois import (  # heavy import, lazy
        _actions_for_stop_type,
        _parking_for_stop_type,
        _services_for_stop_type,
    )

    new_type = verdict["verdict"]
    out = dict(stop)
    note = (
        f"Type corrected from service_plaza to {new_type} ({verdict['kind']}): "
        f"{verdict['why']}. Geofabrik extract, accessed {ACCESSED}."
    )
    if new_type == "service_plaza":
        note = (
            f"{CONFIRMED_NOTE} ({verdict['kind']}): {verdict['why']}. "
            f"Geofabrik extract, accessed {ACCESSED}."
        )
    else:
        out["type"] = new_type
        if new_type != "travel_center":
            # Services, actions and parking were the import's assumptions for a
            # service plaza. The same table's assumptions for the real type.
            out["services"] = _services_for_stop_type(new_type)
            out["actions"] = _actions_for_stop_type(new_type)
            if out.get("parking") != "confirmed":
                out["parking"] = _parking_for_stop_type(new_type)
            note += " Services, actions and parking are the import's assumptions for that type."
    out["source"] = f"{str(stop.get('source') or '').strip()} {note}".strip()
    return out


CONFIRMED_NOTE = "Confirmed a service plaza"


def apply(data: dict[str, Any], verdicts: dict[str, dict[str, str]]) -> dict[str, list[Any]]:
    from reverse_pair_stops import _point_at, _polyline

    report: dict[str, list[Any]] = defaultdict(list)
    for leg in data["legs"]:
        stops = leg.get("stops") or []
        if not any(is_candidate(stop) or stop.get("name") in REVIEWED for stop in stops):
            continue
        line = None
        kept: list[dict[str, Any]] = []
        for stop in stops:
            label = f"{leg['from']}->{leg['to']} @ {stop.get('at_mi')}: {stop.get('name')}"
            reviewed = REVIEWED.get(str(stop.get("name")))
            if reviewed and reviewed[0] == "remove":
                # The evidence is about the place, whatever type a record gave it.
                report["remove"].append(f"{label} | {reviewed[1]}")
                continue
            if not is_candidate(stop):
                kept.append(stop)
                continue
            lat, lon = stop.get("lat"), stop.get("lon")
            if lat is None or lon is None:
                line = line or _polyline(leg)
                point = _point_at(line, float(stop.get("at_mi") or 0.0))
                lat, lon = point if point else (0.0, 0.0)
            verdict = verdicts.get(record_key(stop, float(lat), float(lon)))
            if verdict is None or verdict["verdict"] in {"unverified", "screen"}:
                report[verdict["verdict"] if verdict else "no evidence"].append(label)
                kept.append(stop)
            elif verdict["verdict"] == "remove":
                report["remove"].append(f"{label} | {verdict['why']}")
            else:
                report[f"{verdict['verdict']} ({verdict['kind']})"].append(label)
                kept.append(_retyped(stop, verdict))
        if stops and not kept:
            report["legs left with no stop"].append(f"{leg['from']}->{leg['to']}")
        leg["stops"] = kept
    return report


def save_keeping_spelling(data: dict[str, Any]) -> int:
    """``save_world``, without its escape churn.

    ``save_world`` writes every non-ASCII character as an escape, and a few
    shards spell theirs out ("La Cañada Flintridge" in ``legs/CA.json``), so
    a one-stop edit would rewrite lines this tool never touched. Each spelled-out
    string is put back as it was.
    """
    import re

    from world_source import WORLD_SOURCE_PATH

    token = re.compile(r'"(?:[^"\\\n]|\\.)*"')
    spelled: dict[Path, set[str]] = {}
    for shard in (WORLD_SOURCE_PATH / "legs").glob("*.json"):
        text = shard.read_bytes().decode("utf-8")
        found = {t for t in token.findall(text) if not t.isascii()}
        if found:
            spelled[shard] = found
    written = save_world(data)
    for shard, tokens in spelled.items():
        if not shard.exists():
            continue
        text = shard.read_bytes().decode("utf-8")
        restored = text
        for original in sorted(tokens):
            restored = restored.replace(json.dumps(json.loads(original)), original)
        if restored != text:
            shard.write_bytes(restored.encode("utf-8"))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-osm", action="store_true", help="read the state extracts")
    parser.add_argument("--second-pass", action="store_true", help="with --read-osm")
    parser.add_argument("--compile", action="store_true", help="raw dumps to the evidence file")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("states", nargs="*")
    args = parser.parse_args(argv)
    data = load_world()
    if args.read_osm:
        read_osm(data, [_slug(s) for s in args.states], args.second_pass)
        return 0
    if args.compile:
        places = compile_evidence(data)
        write_evidence(places)
        print(f"{len(places)} place(s) in {EVIDENCE_PATH.name}.")
        return 0
    rows = list_candidates(data)
    print(f"{len(rows)} candidate record(s), {len({r['key'] for r in rows})} distinct place(s).")
    if args.list:
        print(json.dumps(rows, indent=1))
        return 0
    places = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))["places"]
    verdicts = decide(data, places)
    report = apply(data, verdicts)
    for verdict in sorted(report):
        print(f"\n{verdict}: {len(report[verdict])} record(s)")
        for line in report[verdict]:
            print(f"  {line}")
    kinds = Counter(v["kind"] for v in verdicts.values())
    print(f"\nPlaces by kind of value: {dict(kinds)}")
    if args.write:
        print(f"Wrote {save_keeping_spelling(data)} shard(s).")
    else:
        print("Dry run. Re-run with --write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
