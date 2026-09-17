"""Name the chain truck stops: which store each bare record is.

About 1,300 chain truck stops reached the map from an OpenStreetMap amenity
query under the chain's bare name ("Love's Travel Stop"), typed
``service_plaza``. Two load-time screens paper over that
(``data::stop_twins``, ``data::branded_plazas``). This tool gives each record
its identity instead: it builds a table of chain stores and matches every
chain stop record to a store BY COORDINATE, never by mile marker.

    uv run --group tooling python tools/import_chain_locators.py --scan-osm
    uv run python tools/import_chain_locators.py              # dry run
    uv run python tools/import_chain_locators.py --calibrate  # the histograms
    uv run python tools/import_chain_locators.py --write

Idempotent: a second ``--write`` changes nothing. Dry run by default.

Where the store table comes from
--------------------------------
Terms of use were read for every chain's locator on 2026-09-17. Love's
("mine, scrape"), TA and Petro ("any robot, spider or other automatic
device") and Road Ranger ("scraping") forbid automated access in their terms.
Pilot Flying J (with ONE9) allows it at a human pace but licenses its
locator for personal use and forbids copying the compilation. None of those
was fetched. Sapp Bros. posts no terms and an open robots.txt; its one
locations page (a list of 17 towns) was read once.

So the table is **read** from OpenStreetMap: the Geofabrik state extracts
already cached for the other builders, scanned one state at a time for
``amenity=fuel`` and ``highway=services`` objects of the six chains. Objects
of one brand within ``CLUSTER_MI`` of each other are one store (a store is
usually mapped as a services area plus a car and a truck fuel island). A
store's town is read from, in order, its ``addr:city``, its ``branch``, or the
store-page address its ``website`` tag links to; the store number from ``ref``
or that link; the truck parking count from ``capacity:hgv``. A store with none
of the three town tags gets the nearest mapped city, town or village within
``NEAREST_PLACE_MI`` and the source says **derived**. Nothing is assumed: a
store with no town is matched but not named.

The radii, and where they come from
-----------------------------------
Calibrated against the map of 2026-09-17 (``--calibrate`` reprints them).

``CLUSTER_MI`` 0.2: nearest same-brand object, all 3,500 objects: 2,695 under
0.1 mi, 49 at 0.1 to 0.15, 7 at 0.15 to 0.2, 10 at 0.2 to 0.3, then rising
(the next store). 0.2 is the bottom of the trough.

``SITE_MATCH_MI`` 0.1: records that carry a mapped site's coordinates, distance
to the nearest same-chain object: 414 under 0.005 mi, 223 to 0.01, 477 to
0.02, 313 to 0.05, 33 to 0.1, then NONE from 0.1 to 0.2. The two populations
do not touch, so the cut separates them completely.

A record has a site's coordinates when they carry seven decimals or fewer.
``reverse_pair_stops.py`` gave a copied record that had none a point on the
source leg's line at its mile marker (14 or more decimals). That is a mile
marker written as a coordinate, and it is matched by the second rule.

``LEG_MATCH_MI`` 5.0: records with no site coordinates match only when EXACTLY
ONE store of their brand lies within this distance of the leg's own line at
the record's mile marker. 97% of the stores known by coordinate lie within
five miles of their own record's mile marker. Marked against the curated
records, which say which store they are: the town agrees for 179 of 186 and
the store number for 129 of 137, and a record whose source gives another
store number than the store in reach is refused. The comment on
``LEG_MATCH_MI`` carries the histogram.

``NAME_MATCH_MI`` 40.0: a curated record's mile marker was projected onto
simplified geometry and is 5 to 40 miles out on the long legs, so a NAMED
record that finds no store by position may find the one store of its brand
whose read town is the town in its own name. The comment on the constant
carries the counts; they stop growing at 40 miles.

What is written
---------------
For a bare record matched to a named store: the store's full name in the form
the curated records use (chain's store-type words plus the town, no store
number), ``type: travel_center`` when the record said ``service_plaza``, the
site's coordinates when the record had none or had a mile-marker point,
``parking_spaces`` only when the map states a count, and a ``source`` note
that says read, from where, which store and when. A named record is never
renamed, and a bare record is never given a name another record on its leg
already carries. Two records on one leg that match the same store and serve a
common direction are twins: the better-documented one stays (the rank
``data::stop_twins`` uses) and the other is deleted and listed. When the kept
twin's mile marker is more than ``LEG_MATCH_MI`` from the store and the deleted
twin's is not, the kept record takes the deleted one's mile marker, and its
source says the value is derived and from what.

All the numbers above are the map before the import (59df3a96); after it most
records carry their store's coordinates and ``--calibrate`` reads differently.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chain_store_table import (  # noqa: E402
    BRAND_LABEL,
    BRANDS,
    OSM_CACHE_DIR,
    READ_DATE,
    REGIONS_DIR,
    Store,
    StoreIndex,
    clean_town,
    load_stores,
    nearest_place,
    scan_osm,
    squash,
)
from leg_geometry import corridor_geometry  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

#: A record this close to a store's mapped object IS that store. Nothing on
#: the map falls between 0.1 and 0.2 mi (module docstring).
SITE_MATCH_MI = 0.1
#: A record with no site coordinates matches the only store of its brand
#: within this distance of the leg's line at its mile marker. Two measurements
#: (``--calibrate``), map of 2026-09-17:
#:
#: * The 1,462 records whose store is known by coordinate: how far is that
#:   store from the record's own mile marker? 456 under 0.5 mi, 152 to 1, 124
#:   to 1.5, 137 to 2, 264 to 3, 215 to 4, 71 to 5, then 23 from 5 to 7.5 and
#:   2 from 7.5 to 10. A mile marker is a projection onto simplified geometry
#:   and is this loose. The population ends at five miles: 97% inside.
#: * The labelled check: curated records name their town, and most give a
#:   store number, so the rule can be marked. With one store of their brand
#:   within 5 mi, 179 of 186 name the store's town (the others are one store
#:   under two town names: Mayer and Cordes Lake, 0.3 mi apart) and the store
#:   number is the store's for 129 of 137. The eight are a newer store the
#:   map lacks, with an older one of the same chain in reach (Love's 415 and
#:   467 are both in Fort Pierce), at distances from 0 to 4 mi: no radius
#:   separates them, so a record whose source gives another store number is
#:   refused outright. Bare records came from the map, so their store is on it.
#:
#: The uniqueness test, not the radius, is what keeps a wrong store out.
LEG_MATCH_MI = 5.0
#: How far from its mile marker a record may find the store that carries its
#: own name (same chain words, same town, town READ not derived, and only one
#: such store). The name is the evidence; the radius only keeps a second town
#: of the same name out. Measured on the map before the import: of 219 named
#: records no store was found for by position, 63 find one by name inside 10
#: mi, 80 inside 15, 111 inside 25, 126 inside 40 and 129 inside 60, and where
#: the record's source gives a store number it is the store's for 31 of 34 at
#: 25 mi (the other three are a second store the map lacks; the number refuses
#: them). The count flattens past 40, which is the longest mile-marker error
#: on the map and the radius used.
NAME_MATCH_MI = 40.0

#: ``data::stop_twins::TWIN_STOP_MILES``: the reach of the load-time twin screen.
TWIN_STOP_MILES = 4.0

IDENTITY_NOTE = "Store identity read from OpenStreetMap"
COORDINATE_NOTE = "Store coordinates read from OpenStreetMap"
OPPOSITE_DIRECTION_COPY = "Opposite-direction copy"

# The head of a stop record's name, for records (which may go on to name a
# town). Order matters: "ta express" before "ta".
_RECORD_PREFIXES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("loves", re.compile(r"^love'?s\b")),
    ("flyingj", re.compile(r"^flying j\b")),
    ("one9", re.compile(r"^one9\b")),
    ("pilot", re.compile(r"^pilot\b")),
    ("taexpress", re.compile(r"^ta express\b")),
    ("ta", re.compile(r"^(ta\b|travelcenters of america)")),
    ("petro", re.compile(r"^petro\b")),
    ("roadranger", re.compile(r"^road ranger\b")),
    ("sapp", re.compile(r"^sapp bro")),
)
# Words a chain puts in every store's name, which therefore name no place.
# ``data::stop_twins::GENERIC_NAME_WORDS`` plus what the fuel-island records
# say ("Flying J Truck Lanes", "Love's Diesel Lanes", "Pilot Flying J").
_GENERIC_WORDS = frozenset({
    "travel", "center", "centre", "centers", "travelcenter", "travelcenters", "stop", "stops",
    "stopping", "plaza", "truck", "the", "service", "area", "station", "store", "country",
    "dealer", "of", "america", "and", "express", "fuel", "shopping", "lanes", "diesel", "flying",
    "pilot", "love's", "loves", "ta", "petro", "road", "ranger", "one9", "sapp", "bros", "brothers",
})  # fmt: skip
_COMPANY_NAMES = {"pilot flying j", "travelcenters of america"}
# --------------------------------------------------------------------------
# Stop records
# --------------------------------------------------------------------------


def record_brand(name: str) -> str | None:
    lower = name.strip().lower()
    return next((key for key, pattern in _RECORD_PREFIXES if pattern.match(lower)), None)


def is_bare(name: str) -> bool:
    """The name says which chain and nothing about which store."""
    lower = name.strip().lower()
    if lower.startswith("pilot express"):
        return False  # a smaller format, not a travel center; left as it reads
    words = re.split(r"[^a-z0-9']+", lower)
    return not [w for w in words if len(w) > 1 and not w.isdigit() and w not in _GENERIC_WORDS]


def has_site_coordinates(stop: dict[str, Any]) -> bool:
    """Coordinates of a mapped site, not a mile marker written as a point."""
    lat, lon = stop.get("lat"), stop.get("lon")
    if lat is None or lon is None:
        return False
    return all(len(repr(float(v)).partition(".")[2]) <= 7 for v in (lat, lon))


def point_at(line: list[tuple[float, float, float]], at_mi: float) -> tuple[float, float]:
    if at_mi <= line[0][2]:
        return line[0][0], line[0][1]
    for (a_lat, a_lon, a_mi), (b_lat, b_lon, b_mi) in zip(line, line[1:], strict=False):
        if a_mi <= at_mi <= b_mi:
            t = 0.0 if b_mi <= a_mi else (at_mi - a_mi) / (b_mi - a_mi)
            return a_lat + (b_lat - a_lat) * t, a_lon + (b_lon - a_lon) * t
    return line[-1][0], line[-1][1]


def _leg_line(leg: dict[str, Any]) -> list[tuple[float, float, float]]:
    line = corridor_geometry(leg)
    if line and len(line) >= 2:
        return line
    points = (leg.get("corridor") or {}).get("route_points") or []
    rows = [
        (float(p["lat"]), float(p["lon"]), float(p["at_mi"]))
        for p in points
        if "lat" in p and "lon" in p and "at_mi" in p
    ]
    return sorted(rows, key=lambda row: row[2])


@dataclass
class Match:
    store: Store
    how: str  # "coordinate", "leg" or "name"
    distance_mi: float
    marker_mi: float  # the record's own mile marker to the store


def match_stop(
    stop: dict[str, Any], leg: dict[str, Any], index: StoreIndex, outcome: Counter[str]
) -> Match | None:
    brand = record_brand(str(stop.get("name") or ""))
    if brand is None:
        return None
    family = BRANDS[brand][1]
    if has_site_coordinates(stop):
        near = index.near(float(stop["lat"]), float(stop["lon"]), SITE_MATCH_MI, family)
        if not near:
            outcome["left: has a site's coordinates, no store of its chain within 0.1 mi"] += 1
            return None
        same = [pair for pair in near if pair[1].brand == brand] or near
        line = _leg_line(leg)
        marker = (
            same[0][1].distance_mi(*point_at(line, float(stop.get("at_mi") or 0.0)))
            if len(line) >= 2
            else 0.0
        )
        return Match(same[0][1], "coordinate", same[0][0], marker)
    line = _leg_line(leg)
    if len(line) < 2:
        outcome["left: no coordinates and the leg has no geometry"] += 1
        return None
    lat, lon = point_at(line, float(stop.get("at_mi") or 0.0))
    near = index.near(lat, lon, LEG_MATCH_MI, family)
    same = [pair for pair in near if pair[1].brand == brand]
    # "Pilot Flying J" and "TravelCenters of America" name the company, so any
    # of its brands will do; every other record is matched to its own brand.
    company = str(stop.get("name") or "").strip().lower() in _COMPANY_NAMES
    candidates = near if company else same
    how = "leg"
    if len(candidates) != 1:
        # A curated record says which store it is: the chain's words and the
        # town. Its mile marker can be 20 miles out on a 700-mile leg (it was
        # projected onto simplified geometry), so the name gets a longer reach.
        named = _stores_named_like(stop, brand, index.near(lat, lon, NAME_MATCH_MI, family))
        if len(named) == 1:
            candidates, how = named, "name"
    if len(candidates) != 1:
        key = "no store" if not candidates else "more than one store"
        outcome[f"left: no coordinates, {key} of its chain within {LEG_MATCH_MI:g} mi"] += 1
        return None
    # The map is missing some newer stores, and then the only store in reach
    # is the wrong one (Love's 415 and 467 are both in Fort Pierce). A curated
    # record's source gives its store number: a different number refuses.
    said = re.search(r"\bstore (\d+) in ", str(stop.get("source") or ""))
    number = candidates[0][1].number
    if said and number and said.group(1).lstrip("0") != number.lstrip("0"):
        outcome["left: its source names another store number than the only store in reach"] += 1
        return None
    return Match(candidates[0][1], how, candidates[0][0], candidates[0][0])


def _stores_named_like(
    stop: dict[str, Any], brand: str, near: list[tuple[float, Store]]
) -> list[tuple[float, Store]]:
    """Stores of the record's brand whose READ town is the town in its name."""
    name = str(stop.get("name") or "")
    words = BRANDS[brand][0] + " "
    if not name.startswith(words) or not squash(name[len(words) :]):
        return []
    town = squash(name[len(words) :])
    return [
        pair
        for pair in near
        if pair[1].brand == brand
        and "DERIVED" not in pair[1].town_kind
        and squash(pair[1].town) == town
    ]


def _serves_a_common_direction(a: dict[str, Any], b: dict[str, Any]) -> bool:
    def both(stop: dict[str, Any]) -> bool:
        directions = stop.get("directions") or []
        return not directions or "both" in directions

    return (
        both(a) or both(b) or bool(set(a.get("directions") or []) & set(b.get("directions") or []))
    )


def _documentation_rank(stop: dict[str, Any], match: Match) -> tuple[int, ...]:
    """Lower sorts first: the record worth keeping (``data::stop_twins``)."""
    return (
        int(is_bare(str(stop.get("name") or ""))),
        int(stop.get("type") != "travel_center"),
        int(stop.get("parking") != "confirmed" and int(stop.get("parking_spaces") or 0) <= 0),
        int(OPPOSITE_DIRECTION_COPY in str(stop.get("source") or "")),
        int(match.how != "coordinate"),
        round(match.marker_mi),
    )


def _beside_an_unplaced_name(
    stops: list[dict[str, Any]], position: int, matches: dict[int, Match]
) -> bool:
    """A named record of the same chain within the twin screen's reach that
    matched no store: it may be this very store under the chain's own name."""
    stop = stops[position]
    family = BRANDS[record_brand(str(stop["name"])) or "loves"][1]
    for other_position, other in enumerate(stops):
        name = str(other.get("name") or "")
        brand = record_brand(name)
        if other_position in matches or brand is None or is_bare(name):
            continue
        if (
            BRANDS[brand][1] == family
            and abs(float(other.get("at_mi") or 0.0) - float(stop.get("at_mi") or 0.0))
            <= TWIN_STOP_MILES
            and _serves_a_common_direction(stop, other)
        ):
            return True
    return False


def _extract_title(slug: str) -> str:
    return slug.replace("-", " ").title().replace(" Of ", " of ")


def _note(stop: dict[str, Any], match: Match, identified: bool) -> str:
    store = match.store
    origin = (
        f"OpenStreetMap (Geofabrik {_extract_title(store.extract)} extract dated "
        f"{store.dated}, read {READ_DATE})"
    )
    which = BRAND_LABEL[store.brand] + (f" store {store.number}" if store.number else " store")
    if store.town:
        which += f" at {store.town}"
    if match.how == "coordinate":
        matched = f"matched by coordinate, {match.distance_mi:.2f} mi from the mapped site"
    elif match.how == "name":
        matched = (
            f"matched by name, the only {BRAND_LABEL[store.brand]} the map has at "
            f"{store.town} within {NAME_MATCH_MI:g} mi of mile "
            f"{float(stop.get('at_mi') or 0.0):g} of this leg ({match.distance_mi:.1f} mi); "
            "coordinates read from the mapped site"
        )
    else:
        matched = (
            f"matched by position, the only {BRAND_LABEL[store.brand]} within "
            f"{LEG_MATCH_MI:g} mi of mile {float(stop.get('at_mi') or 0.0):g} of this leg "
            f"({match.distance_mi:.1f} mi); coordinates read from the mapped site"
        )
    if not identified:
        return f"{COORDINATE_NOTE.replace('OpenStreetMap', origin)}: {which}; {matched}."
    town = store.town_kind or "no town is mapped for it, so the record keeps the chain's name"
    parts = [which, town, matched]
    if store.parking_spaces:
        parts.append(f"{store.parking_spaces} truck parking spaces read from the mapped site")
    return f"{IDENTITY_NOTE.replace('OpenStreetMap', origin)}: {'; '.join(parts)}."


def _already_noted(stop: dict[str, Any]) -> bool:
    source = str(stop.get("source") or "")
    return "Store identity read from" in source or "Store coordinates read from" in source


def place_words(name: str) -> tuple[str, ...]:
    """What a name says beyond its chain (``data::stop_twins::place_words``)."""
    words = re.split(r"[^a-z0-9']+", name.strip().lower())
    return tuple(
        sorted({w for w in words if len(w) > 1 and not w.isdigit() and w not in _GENERIC_WORDS})
    )


def _curated_towns(found: list[tuple[dict[str, Any], Match]]) -> dict[str, str]:
    """Store key -> the town this map's curated records already call it by.

    The curated pass named its stores from the chains' own feeds ("Love's
    Travel Stop Frenchtown" for a site whose address tag says Monroe). One
    store should have one name on every leg, and the curated one came first.
    """
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    for stop, match in found:
        name = str(stop.get("name") or "")
        words = BRANDS[match.store.brand][0] + " "
        if _already_noted(stop) or not name.startswith(words):
            continue
        town = name[len(words) :]
        if town and town == clean_town(town):
            votes[match.store.key][town] += 1
    return {
        key: sorted(towns.items(), key=lambda item: (-item[1], item[0]))[0][0]
        for key, towns in votes.items()
    }


def apply(world: dict[str, Any], stores: list[Store]) -> dict[str, Any]:
    """Match, rename and de-twin in place. Returns the report."""
    index = StoreIndex(stores)
    outcome: Counter[str] = Counter()
    per_brand: dict[str, Counter[str]] = defaultdict(Counter)
    deletions: list[dict[str, Any]] = []
    renames: Counter[str] = Counter()

    # Pass one: which store is every chain record?
    matched: list[tuple[dict[str, Any], dict[int, Match]]] = []
    for leg in world["legs"]:
        matches: dict[int, Match] = {}
        for position, stop in enumerate(leg.get("stops") or []):
            name = str(stop.get("name") or "")
            brand = record_brand(name)
            if brand is None:
                continue
            kind = "bare" if is_bare(name) else "named"
            per_brand[brand][f"{kind} records"] += 1
            reasons: Counter[str] = Counter()
            match = match_stop(stop, leg, index, reasons)
            if match is None:
                for reason in reasons:
                    outcome[f"{kind} record {reason}"] += 1
                    per_brand[brand][f"{kind} {reason}"] += 1
                continue
            matches[position] = match
            per_brand[brand][f"{kind} matched by {match.how}"] += 1
        matched.append((leg, matches))
    curated = _curated_towns(
        [(leg["stops"][p], m) for leg, matches in matched for p, m in matches.items()]
    )
    for store in stores:
        if store.key in curated and curated[store.key] != store.town:
            store.town = curated[store.key]
            store.town_kind = "town as this map's curated record of the same store names it"

    # Pass two: twins out, identity in.
    for leg, matches in matched:
        stops = leg.get("stops") or []
        by_store: dict[str, list[int]] = defaultdict(list)
        for position, match in matches.items():
            by_store[match.store.key].append(position)
        doomed: set[int] = set()
        borrowed: dict[int, tuple[Any, Any]] = {}
        miles = [float(stop.get("at_mi") or 0.0) for stop in stops]
        in_order = miles == sorted(miles)
        for positions in by_store.values():
            ranked = sorted(
                positions,
                key=lambda p: (
                    _documentation_rank(stops[p], matches[p]),
                    float(stops[p].get("at_mi") or 0.0),
                    p,
                ),
            )
            kept: list[int] = []
            for position in ranked:
                name = str(stops[position]["name"])
                twin = next(
                    (k for k in kept if _serves_a_common_direction(stops[k], stops[position])),
                    None,
                )
                if twin is None:
                    kept.append(position)
                    continue
                if not is_bare(name) and place_words(name) != place_words(stops[twin]["name"]):
                    # Two curated names for one store. Not this tool's call.
                    outcome["named record shares a store with another name, both kept"] += 1
                    kept.append(position)
                    continue
                doomed.add(position)
                per_brand[record_brand(name) or "?"]["twins deleted"] += 1
                if (
                    matches[twin].marker_mi > LEG_MATCH_MI
                    and matches[position].marker_mi <= LEG_MATCH_MI
                    and not _already_noted(stops[twin])
                ):
                    # The kept record's mile marker contradicts its own store;
                    # the twin's was placed from the store's coordinates.
                    borrowed[twin] = (stops[twin].get("at_mi"), stops[position].get("at_mi"))
                    stops[twin]["at_mi"] = stops[position].get("at_mi")
                    matches[twin].marker_mi = matches[position].marker_mi
                    outcome["kept twin took the deleted twin's mile marker"] += 1
                deletions.append(
                    {
                        "leg": f"{leg['from']} -> {leg['to']}",
                        "deleted": f"{name} at mile {stops[position].get('at_mi')}",
                        "kept": f"{stops[twin]['name']} at mile {stops[twin].get('at_mi')}",
                        "store": matches[position].store.full_name or matches[position].store.key,
                    }
                )

        for position, match in matches.items():
            if position in doomed:
                continue
            stop, store = stops[position], match.store
            if _already_noted(stop):
                outcome["already carries its store (an earlier run)"] += 1
                continue
            brand = record_brand(str(stop["name"])) or "?"
            bare = is_bare(str(stop.get("name") or ""))
            # A Love's Country Store is a Love's and is not a travel center:
            # the store has to say it serves trucks before the record does.
            identified = bare and store.serves_trucks
            if identified and _beside_an_unplaced_name(stops, position, matches):
                # The load-time twin screen reads this pair as one store
                # because this record is bare. Named after a town the named
                # record does not use, it would stop doing that.
                outcome["bare record left alone: beside a named record no store was found for"] += 1
                per_brand[brand]["bare left alone beside an unplaced named record"] += 1
                continue
            rename = identified and bool(store.town)
            if rename and any(
                str(other.get("name")) == store.full_name
                for other_position, other in enumerate(stops)
                if other_position != position
                and other_position not in doomed
                and not is_bare(str(other.get("name") or ""))
                and (
                    other_position not in matches or matches[other_position].store.key != store.key
                )
            ):
                # Two stores of one chain in one town, or a named record no
                # store was found for. Saying the name twice helps nobody.
                outcome["bare record left bare: its name is already on this leg"] += 1
                per_brand[brand]["bare left bare: its name is already on this leg"] += 1
                rename = False
            if bare and not rename:
                why = (
                    "nothing says it serves trucks"
                    if not identified
                    else "typed and sourced, but no town is known to name it by"
                )
                outcome[f"bare record matched a store and stays bare: {why}"] += 1
                per_brand[brand][f"bare matched, stays bare: {why}"] += 1
            needs_coordinates = not has_site_coordinates(stop)
            if not identified and not needs_coordinates and position not in borrowed:
                continue
            note = _note(stop, match, identified)
            if position in borrowed:
                was, now = borrowed[position]
                note += (
                    f" Mile marker moved from {was:g} to {now:g}: DERIVED from the map "
                    "import's record of this same store on this leg, which was placed from "
                    f"the store's coordinates; mile {was:g} is more than {LEG_MATCH_MI:g} mi "
                    "from the store."
                )
            if identified and stop.get("type") == "service_plaza":
                stop["type"] = "travel_center"
            if rename:
                renames[f"{stop['name']} -> {BRANDS[store.brand][0]} <town>"] += 1
                per_brand[brand]["bare named"] += 1
                if "DERIVED" in store.town_kind:
                    outcome["bare record named with a DERIVED town"] += 1
                stop["name"] = store.full_name
                if store.parking_spaces and not int(stop.get("parking_spaces") or 0):
                    stop["parking_spaces"] = store.parking_spaces
                    outcome["parking count read from the mapped site"] += 1
            if needs_coordinates:
                stop["lat"], stop["lon"] = store.lat, store.lon
                outcome["coordinates written from the mapped site"] += 1
            old = str(stop.get("source") or "").strip()
            # Curated notes end in a link; a full stop there would join it.
            joint = " " if old.endswith(".") or not old else "; "
            stop["source"] = f"{old}{joint}{note}"
        if doomed:
            leg["stops"] = [stop for position, stop in enumerate(stops) if position not in doomed]
        if borrowed and in_order:
            leg["stops"].sort(key=lambda stop: float(stop.get("at_mi") or 0.0))
    return {
        "stores": Counter(store.brand for store in stores),
        "stores_with_town": Counter(store.brand for store in stores if store.town),
        "stores_town_kind": Counter(
            store.town_kind.split(":")[0].split(",")[0] for store in stores if store.town
        ),
        "stores_with_number": Counter(store.brand for store in stores if store.number),
        "stores_with_parking": Counter(store.brand for store in stores if store.parking_spaces),
        "per_brand": {
            brand: dict(sorted(counts.items())) for brand, counts in sorted(per_brand.items())
        },
        "outcome": dict(outcome),
        "renames": dict(renames),
        "deletions": deletions,
    }


# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------


def _histogram(values: list[float], edges: list[float]) -> list[tuple[str, int]]:
    rows = []
    for low, high in zip(edges, edges[1:], strict=False):
        label = f"{low:g} to {high:g} mi" if high < 1e8 else f"over {low:g} mi"
        rows.append((label, sum(1 for v in values if low <= v < high)))
    return rows


def calibrate(world: dict[str, Any], stores: list[Store]) -> None:
    index = StoreIndex(stores)
    site: list[float] = []
    marker: list[float] = []
    for leg in world["legs"]:
        line: list[tuple[float, float, float]] | None = None
        for stop in leg.get("stops") or []:
            brand = record_brand(str(stop.get("name") or ""))
            if brand is None or not has_site_coordinates(stop):
                continue
            lat, lon = float(stop["lat"]), float(stop["lon"])
            near = index.near(lat, lon, 60.0, BRANDS[brand][1])
            if not near:
                site.append(1e9)
                continue
            site.append(near[0][0])
            if near[0][0] > SITE_MATCH_MI:
                continue
            line = line if line is not None else _leg_line(leg)
            if len(line) >= 2:
                m_lat, m_lon = point_at(line, float(stop.get("at_mi") or 0.0))
                marker.append(near[0][1].distance_mi(m_lat, m_lon))
    print("Record with a site's coordinates -> nearest store object of its chain:")
    for label, count in _histogram(
        site, [0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1, 2, 5, 1e9]
    ):
        print(f"  {label:>18}  {count}")
    print("\nA known store -> its own record's mile marker on the leg:")
    for label, count in _histogram(marker, [0, 0.5, 1, 1.5, 2, 3, 4, 5, 7.5, 10, 20, 1e9]):
        print(f"  {label:>18}  {count}")
    ordered = sorted(marker)
    for share in (0.5, 0.8, 0.9, 0.95, 0.96, 0.99):
        print(f"  {share:.0%} under {ordered[int(share * (len(ordered) - 1))]:.2f} mi")

    print("\nThe labelled check: named records with no site coordinates and exactly one")
    print(f"store of their brand within {LEG_MATCH_MI:g} mi of their mile marker:")
    towns, numbers = [0, 0], [0, 0]
    for leg in world["legs"]:
        for stop in leg.get("stops") or []:
            name = str(stop.get("name") or "")
            if has_site_coordinates(stop) or is_bare(name) or _already_noted(stop):
                continue
            brand, line = record_brand(name), _leg_line(leg)
            if brand is None or len(line) < 2:
                continue
            # The position rule alone: no match by name, no store-number guard.
            spot = point_at(line, float(stop.get("at_mi") or 0.0))
            near = index.near(*spot, LEG_MATCH_MI, BRANDS[brand][1])
            same = [pair[1] for pair in near if pair[1].brand == brand]
            if len(same) != 1:
                continue
            if same[0].town and "DERIVED" not in same[0].town_kind:
                towns[0] += 1
                towns[1] += int(squash(same[0].town) in squash(name))
            said = re.search(r"store (\d+) in ", str(stop.get("source") or ""))
            if said and same[0].number:
                numbers[0] += 1
                numbers[1] += int(said.group(1).lstrip("0") == same[0].number.lstrip("0"))
    print(f"  the store's town is in the record's name: {towns[1]} of {towns[0]}")
    print(f"  the store number in the record's source is the store's: {numbers[1]} of {numbers[0]}")

    print("\nNearest mapped place against the town a store's own address names:")
    places: dict[str, Any] = {}
    for path in sorted(OSM_CACHE_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        places[payload["extract"]] = payload["places"]
    bands: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for store in stores:
        if not store.town_kind.startswith("town read from the mapped site's address"):
            continue
        nearest = nearest_place(places.get(store.extract, ()), store.lat, store.lon)
        if nearest is None:
            continue
        band = next(
            label
            for limit, label in (
                (1, "under 1 mi"),
                (2, "1 to 2"),
                (3, "2 to 3"),
                (5, "3 to 5"),
                (1e9, "over 5"),
            )
            if nearest[1] < limit
        )
        bands[band][0] += 1
        bands[band][1] += int(squash(nearest[0]) == squash(store.town))
    for band in ("under 1 mi", "1 to 2", "2 to 3", "3 to 5", "over 5"):
        total, agree = bands[band]
        if total:
            print(f"  {band:>12}: {agree} of {total} agree ({agree / total:.0%})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scan-osm", action="store_true", help="rebuild the OSM cache and exit")
    parser.add_argument("--calibrate", action="store_true", help="print the distance histograms")
    parser.add_argument("--write", action="store_true", help="apply (default is a dry run)")
    parser.add_argument("--report", type=Path, help="write the full report as JSON here")
    args = parser.parse_args(argv)
    if args.scan_osm:
        scan_osm(REGIONS_DIR, OSM_CACHE_DIR)
        return 0
    stores = load_stores()
    world = load_world()
    if args.calibrate:
        calibrate(world, stores)
        return 0
    report = apply(world, stores)
    for key in (
        "stores",
        "stores_with_town",
        "stores_town_kind",
        "stores_with_number",
        "stores_with_parking",
    ):
        print(f"{key}: {dict(report[key])}")
    for brand, counts in report["per_brand"].items():
        print(f"{BRAND_LABEL[brand]:>12}: {counts}")
    for line, count in sorted(report["outcome"].items()):
        print(f"{count:>6}  {line}")
    print(f"{len(report['deletions'])} twins deleted")
    if args.report:
        args.report.write_text(json.dumps(report, indent=2, default=dict), encoding="utf-8")
    if args.write:
        save_world(world)
        print("written; now run tools/index_world.py")
    else:
        print("dry run; pass --write to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
