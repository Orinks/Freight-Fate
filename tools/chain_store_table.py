"""The chain truck stops the map knows, read from OpenStreetMap.

``tools/import_chain_locators.py`` matches stop records against this table;
its docstring says why the chains' own locators are not the source and where
every radius comes from. This module is the table: the scan of the cached
Geofabrik state extracts (one state in memory at a time), the clustering of
mapped objects into stores, and what is READ for each store (town, store
number, truck parking count) or, for a town only, DERIVED and labelled so.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm"
REGIONS_DIR = CACHE_DIR / "regions"
OSM_CACHE_DIR = CACHE_DIR / "locators" / "osm"
SAPP_TOWNS_PATH = CACHE_DIR / "locators" / "sapp" / "towns.json"
READ_DATE = "2026-09-17"
EARTH_RADIUS_MI = 3958.7613

#: Objects of one brand this close are one store. Bottom of the trough in the
#: nearest-same-brand-object histogram (module docstring).
CLUSTER_MI = 0.2
#: A town derived from the nearest mapped city, town or village is used only
#: this close. Against the stores whose own address tag names their town (the
#: known answers), the nearest place agrees for 82% under 1 mi and 79% from 1
#: to 2, then 62% from 2 to 3 and 51% from 3 to 5. The break is at two miles.
#: A disagreement is a neighbouring town, not a wrong store, and the source
#: note says DERIVED so the name can be re-judged.
NEAREST_PLACE_MI = 2.0
#: brand key -> (store-type words used in a full name, chain family).
BRANDS: dict[str, tuple[str, str]] = {
    "loves": ("Love's Travel Stop", "loves"),
    "pilot": ("Pilot Travel Center", "pilot"),
    "flyingj": ("Flying J Travel Center", "pilot"),
    "one9": ("ONE9 Travel Center", "pilot"),
    "ta": ("TA Travel Center", "ta"),
    "taexpress": ("TA Express", "ta"),
    "petro": ("Petro Stopping Center", "ta"),
    "roadranger": ("Road Ranger", "roadranger"),
    "sapp": ("Sapp Brothers Travel Center", "sapp"),
}
BRAND_LABEL = {
    "loves": "Love's",
    "pilot": "Pilot",
    "flyingj": "Flying J",
    "one9": "ONE9",
    "ta": "TA",
    "taexpress": "TA Express",
    "petro": "Petro",
    "roadranger": "Road Ranger",
    "sapp": "Sapp Bros.",
}

# What the ``brand`` tag says, lowercased.
_BRAND_TAGS = {
    "love's": "loves",
    "loves": "loves",
    "love's travel stop": "loves",
    "pilot": "pilot",
    "pilot flying j": "pilot",
    "pilot travel center": "pilot",
    "flying j": "flyingj",
    "one9": "one9",
    "one9 travel center": "one9",
    "one 9 fuel network": "one9",
    "ta": "ta",
    "travelcenters of america": "ta",
    "ta express": "taexpress",
    "petro": "petro",
    "petro stopping centers": "petro",
    "road ranger": "roadranger",
    "en:road ranger": "roadranger",
    "sapp bros.": "sapp",
    "sapp bros": "sapp",
}
# What a name must look like when there is no usable brand tag. Strict on
# purpose: "Petro Champ", "Petro-Card 24" and "Pilot Thomas Logistics" are not
# the chains.
_NAME_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("loves", re.compile(r"^love'?s( travel stops?| country stores?| diesel lanes)?$")),
    ("flyingj", re.compile(r"^flying j( travel (center|plaza)| truck lanes)?$")),
    ("one9", re.compile(r"^one ?9( travel center| fuel network)?$")),
    ("pilot", re.compile(r"^pilot( travel centers?| flying j| express)?$")),
    ("taexpress", re.compile(r"^ta express$")),
    ("ta", re.compile(r"^(ta( travel ?centers?)?|travel ?centers of america)$")),
    ("petro", re.compile(r"^petro( stopping centers?| truck stops?)?$")),
    ("roadranger", re.compile(r"^road ranger$")),
    ("sapp", re.compile(r"^sapp bro(s\.?|thers)( travel centers?)?$")),
)
_TRUCK_NAME_WORDS = ("travel", "stopping", "truck")
_STATE_CODES = {
    "alabama": "al", "arizona": "az", "arkansas": "ar", "california": "ca", "colorado": "co",
    "connecticut": "ct", "delaware": "de", "district-of-columbia": "dc", "florida": "fl",
    "georgia": "ga", "idaho": "id", "illinois": "il", "indiana": "in", "iowa": "ia",
    "kansas": "ks", "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md",
    "massachusetts": "ma", "michigan": "mi", "minnesota": "mn", "mississippi": "ms",
    "missouri": "mo", "montana": "mt", "nebraska": "ne", "nevada": "nv", "new-hampshire": "nh",
    "new-jersey": "nj", "new-mexico": "nm", "new-york": "ny", "north-carolina": "nc",
    "north-dakota": "nd", "ohio": "oh", "oklahoma": "ok", "oregon": "or", "pennsylvania": "pa",
    "rhode-island": "ri", "south-carolina": "sc", "south-dakota": "sd", "tennessee": "tn",
    "texas": "tx", "utah": "ut", "vermont": "vt", "virginia": "va", "washington": "wa",
    "west-virginia": "wv", "wisconsin": "wi", "wyoming": "wy",
}  # fmt: skip
_TRUCK_HGV = {"yes", "designated", "only"}
_STATE_OF_EXTRACT_SKIP = {"austria", "luxembourg", "manitoba", "netherlands", "switzerland"}
_KEEP_TAGS = (
    "name", "brand", "operator", "branch", "ref", "website", "contact:website",
    "addr:city", "addr:state", "hgv", "capacity:hgv", "highway",
)  # fmt: skip


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------
# The OpenStreetMap scan (build time, needs the ``tooling`` group)
# --------------------------------------------------------------------------


def osm_brand(tags: dict[str, str]) -> str | None:
    """Which chain an OSM object belongs to, or None."""
    name = re.sub(r"\s+", " ", tags.get("name", "").strip().lower())
    from_tag = _BRAND_TAGS.get(tags.get("brand", "").strip().lower())
    from_name = next((key for key, pattern in _NAME_PATTERNS if pattern.match(name)), None)
    if from_tag == "ta" and from_name == "taexpress":
        return "taexpress"
    return from_tag or from_name


def scan_osm(regions_dir: Path, out_dir: Path) -> None:
    """One cache file per state extract. One extract in memory at a time."""
    import osmium  # build-time only

    bits = osmium.osm.osm_entity_bits
    out_dir.mkdir(parents=True, exist_ok=True)
    for pbf in sorted(regions_dir.glob("*-latest.osm.pbf")):
        slug = pbf.name.removesuffix("-latest.osm.pbf")
        if slug in _STATE_OF_EXTRACT_SKIP:
            continue
        header = osmium.io.Reader(str(pbf), bits.NOTHING).header()
        dated = (header.get("osmosis_replication_timestamp") or "")[:10]
        objects: list[dict[str, Any]] = []
        way_nodes: dict[int, tuple[float, float] | None] = {}
        tagged = osmium.FileProcessor(str(pbf), entities=bits.NODE | bits.WAY).with_filter(
            osmium.filter.TagFilter(("amenity", "fuel"), ("highway", "services"))
        )
        for obj in tagged:
            tags = {tag.k: tag.v for tag in obj.tags}
            brand = osm_brand(tags)
            if brand is None:
                continue
            record: dict[str, Any] = {
                "id": f"{'n' if obj.is_node() else 'w'}{obj.id}",
                "brand": brand,
                "tags": {key: tags[key] for key in _KEEP_TAGS if key in tags},
            }
            if obj.is_node():
                if not obj.location.valid():
                    continue
                record["lat"] = round(obj.location.lat, 6)
                record["lon"] = round(obj.location.lon, 6)
            else:
                record["_refs"] = [node.ref for node in obj.nodes]
                way_nodes.update(dict.fromkeys(record["_refs"]))
            objects.append(record)
        if way_nodes:
            # Only the nodes of the ways just found: no location index, so a
            # 1 GB extract costs megabytes.
            for node in osmium.FileProcessor(str(pbf), entities=bits.NODE).with_filter(
                osmium.filter.IdFilter(list(way_nodes))
            ):
                if node.location.valid():
                    way_nodes[node.id] = (node.location.lat, node.location.lon)
        sites = []
        for record in objects:
            refs = record.pop("_refs", None)
            if refs is not None:
                points = [way_nodes[ref] for ref in dict.fromkeys(refs) if way_nodes.get(ref)]
                if not points:
                    continue
                record["lat"] = round(sum(p[0] for p in points) / len(points), 6)
                record["lon"] = round(sum(p[1] for p in points) / len(points), 6)
            sites.append(record)
        places = []
        for node in osmium.FileProcessor(str(pbf), entities=bits.NODE).with_filter(
            osmium.filter.KeyFilter("place")
        ):
            tags = {tag.k: tag.v for tag in node.tags}
            if tags.get("place") not in ("city", "town", "village") or not tags.get("name"):
                continue
            if node.location.valid():
                places.append(
                    [tags["name"], round(node.location.lat, 5), round(node.location.lon, 5)]
                )
        payload = {"extract": slug, "dated": dated, "sites": sites, "places": places}
        (out_dir / f"{slug}.json").write_text(json.dumps(payload), encoding="utf-8")
        print(f"{slug}: {len(sites)} chain objects, {len(places)} places, dated {dated}")


# --------------------------------------------------------------------------
# The store table
# --------------------------------------------------------------------------


@dataclass
class Store:
    key: str
    brand: str
    lat: float
    lon: float
    extract: str
    dated: str
    points: list[tuple[float, float]]
    town: str = ""
    town_kind: str = ""  # how the town is known; goes into the source note
    number: str = ""
    parking_spaces: int = 0
    serves_trucks: bool = False
    matched: int = field(default=0, compare=False)

    @property
    def family(self) -> str:
        return BRANDS[self.brand][1]

    @property
    def full_name(self) -> str:
        return f"{BRANDS[self.brand][0]} {self.town}" if self.town else ""

    def distance_mi(self, lat: float, lon: float) -> float:
        return min(haversine_mi(lat, lon, plat, plon) for plat, plon in self.points)


def clean_town(text: str) -> str:
    """A town fit to be spoken, or the empty string."""
    town = re.sub(r"\s+", " ", text.strip())
    if not town or len(town) > 30 or not re.fullmatch(r"[A-Za-z][A-Za-z .'\-]*", town):
        return ""
    if town.isupper() or town.islower():
        town = town.title()
    # Spoken: a screen reader spells "Ft." out letter by letter.
    town = re.sub(r"\bFt\.?(?= )", "Fort", town)
    town = re.sub(r"\bMt\.?(?= )", "Mount", town)
    # Title case flattens "McCammon"; a Mc name always has the capital.
    return re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), town)


def squash(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _town_from_link(url: str, spellings: dict[str, str], states: set[str]) -> str:
    """The town in a store-page address a ``website`` tag links to.

    Screened for self-contradiction: a link into another state is a mapping
    slip (a Virginia Pilot carries the page of the one in Beach, North
    Dakota), and names nothing.
    """
    found = re.search(
        r"locations\.pilotflyingj\.com/us/([a-z]{2})/([a-z0-9.'\-]+)/", url
    ) or re.search(
        r"ta-petro\.com/location/([a-z]{2})/(?:ta-express|petro|ta)-([a-z0-9.'\-]+)", url
    )
    if not found or found.group(1) not in states:
        return ""
    slug = found.group(2).rstrip("/")
    # The link is lowercase; the extract's own place names give the spelling
    # ("mccammon" is McCammon). Title case when the map has no such place.
    return clean_town(spellings.get(squash(slug)) or slug.replace("-", " ").title())


def _read_town(
    members: list[dict[str, Any]], spellings: dict[str, str], states: set[str]
) -> tuple[str, str]:
    """(town, how it is known) from the first tag that names one, else blanks."""
    for member in members:
        if town := clean_town(member["tags"].get("addr:city", "")):
            return town, "town read from the mapped site's address"
    for member in members:
        if town := clean_town(member["tags"].get("branch", "")):
            return town, "town read from the mapped site's branch name"
    for member in members:
        if town := _town_from_link(member["tags"].get("website", ""), spellings, states):
            return town, "town read from the store page the mapped site links to"
    return "", ""


def _number_from(tags: dict[str, str]) -> str:
    ref = tags.get("ref", "").strip()
    if re.fullmatch(r"#?\d{1,5}", ref):
        return ref.lstrip("#")
    link = tags.get("website", "") or tags.get("contact:website", "")
    loves = re.search(r"loves\.com/(?:en/)?locations/(?:.*?-)?(\d{2,4})/?$", link)
    return loves.group(1) if loves else ""


def load_stores(osm_dir: Path = OSM_CACHE_DIR) -> list[Store]:
    """Cluster the cached OSM objects into stores. Deterministic."""
    objects: dict[str, dict[str, Any]] = {}
    places: dict[str, list[list[Any]]] = {}
    for path in sorted(osm_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        places[payload["extract"]] = payload["places"]
        for site in payload["sites"]:
            # A border site is in two extracts; the first (sorted) wins.
            site = objects.setdefault(site["id"], site)
            site.setdefault("extract", payload["extract"])
            site.setdefault("dated", payload["dated"])
            site.setdefault("states", set()).add(_STATE_CODES.get(payload["extract"], ""))
    if not objects:
        raise SystemExit(f"no OSM cache under {osm_dir}; run with --scan-osm first")
    ordered = sorted(objects.values(), key=lambda o: o["id"])
    parent = list(range(len(ordered)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def cluster_brand(brand: str) -> str:
        return "ta" if brand == "taexpress" else brand

    grid: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    for index, obj in enumerate(ordered):
        cell = (
            cluster_brand(obj["brand"]),
            math.floor(obj["lat"] * 20),
            math.floor(obj["lon"] * 20),
        )
        grid[cell].append(index)
    for index, obj in enumerate(ordered):
        brand, row, col = (
            cluster_brand(obj["brand"]),
            math.floor(obj["lat"] * 20),
            math.floor(obj["lon"] * 20),
        )
        for d_row in (-1, 0, 1):
            for d_col in (-1, 0, 1):
                for other in grid.get((brand, row + d_row, col + d_col), ()):
                    if other > index and (
                        haversine_mi(
                            obj["lat"], obj["lon"], ordered[other]["lat"], ordered[other]["lon"]
                        )
                        <= CLUSTER_MI
                    ):
                        parent[find(other)] = find(index)
    clusters: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, obj in enumerate(ordered):
        clusters[find(index)].append(obj)

    sapp_towns = _sapp_towns()
    stores: list[Store] = []
    for members in clusters.values():
        extract = members[0]["extract"]
        spellings = {squash(name): name for name, _lat, _lon in places.get(extract, ())}
        states = set().union(*(m["states"] for m in members))
        brands = Counter(m["brand"] for m in members)
        brand = (
            "taexpress"
            if brands.get("taexpress") and not brands.get("ta")
            else (cluster_brand(brands.most_common(1)[0][0]))
        )
        lat = round(sum(m["lat"] for m in members) / len(members), 6)
        lon = round(sum(m["lon"] for m in members) / len(members), 6)
        store = Store(
            key=f"{brand}@{lat:.4f},{lon:.4f}",
            brand=brand,
            lat=lat,
            lon=lon,
            extract=extract,
            dated=members[0]["dated"],
            points=[(m["lat"], m["lon"]) for m in members],
        )
        for member in members:
            tags = member["tags"]
            if tags.get("hgv") in _TRUCK_HGV or tags.get("highway") == "services":
                store.serves_trucks = True
            if any(word in tags.get("name", "").lower() for word in _TRUCK_NAME_WORDS):
                store.serves_trucks = True
            store.number = store.number or _number_from(tags)
            spaces = tags.get("capacity:hgv", "")
            if spaces.isdigit() and 0 < int(spaces) <= 1000:
                store.parking_spaces = max(store.parking_spaces, int(spaces))
        store.town, store.town_kind = _read_town(members, spellings, states)
        nearest = nearest_place(places.get(extract, ()), lat, lon)
        if not store.town and brand == "sapp" and nearest and nearest[0] in sapp_towns:
            store.town = nearest[0]
            store.town_kind = (
                "town read from Sapp Bros.' own list of locations "
                f"(sappbros.net, read {READ_DATE}), joined by the nearest mapped town"
            )
        if not store.town and nearest and nearest[1] <= NEAREST_PLACE_MI:
            town = clean_town(nearest[0])
            if town:
                store.town = town
                store.town_kind = (
                    f"town DERIVED, not read: the nearest mapped place, {nearest[1]:.1f} mi away"
                )
        stores.append(store)
    stores.sort(key=lambda s: s.key)
    return stores


def _sapp_towns() -> set[str]:
    if not SAPP_TOWNS_PATH.exists():
        return set()
    return {town for town, _state in json.loads(SAPP_TOWNS_PATH.read_text(encoding="utf-8"))}


def nearest_place(places: Any, lat: float, lon: float) -> tuple[str, float] | None:
    best: tuple[str, float] | None = None
    for name, plat, plon in places:
        if abs(plat - lat) > 0.2 or abs(plon - lon) > 0.3:
            continue
        distance = haversine_mi(lat, lon, plat, plon)
        if best is None or distance < best[1]:
            best = (name, distance)
    return best


class StoreIndex:
    def __init__(self, stores: list[Store]) -> None:
        self.stores = stores
        self._grid: dict[tuple[int, int], list[Store]] = defaultdict(list)
        for store in stores:
            self._grid[(math.floor(store.lat * 5), math.floor(store.lon * 5))].append(store)

    def near(
        self, lat: float, lon: float, radius_mi: float, family: str
    ) -> list[tuple[float, Store]]:
        """Stores of a chain family within a radius, nearest first."""
        reach = 1 + int(radius_mi / 10.0)
        row, col = math.floor(lat * 5), math.floor(lon * 5)
        found = []
        for d_row in range(-reach, reach + 1):
            for d_col in range(-reach, reach + 1):
                for store in self._grid.get((row + d_row, col + d_col), ()):
                    if store.family != family:
                        continue
                    distance = store.distance_mi(lat, lon)
                    if distance <= radius_mi:
                        found.append((distance, store))
        found.sort(key=lambda pair: (pair[0], pair[1].key))
        return found
