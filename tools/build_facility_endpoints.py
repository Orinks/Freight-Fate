r"""Build source-backed freight facility endpoints from local OSM extracts.

Runtime gameplay reads ``facility_endpoints.json`` offline. This tool is
build-time only and never calls OSM, ORS, OSRM, Overpass, or external APIs.

Example (re-sweep a few states into the checked-in file):
    uv run --group tooling python tools/build_facility_endpoints.py \
      --cache-dir C:\Users\joshu\.cache\freight-fate-osm\regions \
      --states Ohio Indiana --write

HOW A FACILITY IS MATCHED. One pass over a state extract collects every node
and way that carries a site identity tag (`SITE_KEYS`) and a name. Each is
classified by ``facility_endpoint_match.match_roles``, which reads the
object's own primary-key tags and whole words of its name and asks
``facility_endpoint_screen`` whether the object can be a truck destination at
all; both modules state their rules and the kind of every value. A facility
takes the best-ranked unused candidate within `DEFAULT_RADIUS_MI` of its
city.

THE RADIUS (read, not tuned). 6.4 miles is the city bound
``regeocode_far_facility_pins`` has enforced on every row since 2026-09-16
(straight line times the 1.25 detour factor stays inside the 8-mile approach
band). The first sweep searched 32 miles and produced the far pins that tool
had to repair; a whole rebuild must not bring them back.

ACROSS THE BORDER (read). A Geofabrik state extract keeps a strip of Mexico
or Canada a few hundred yards wide, enough to hold the maquiladoras on the
fence at Douglas. A candidate is dropped when the straight line from its
city crosses a way of an ``admin_level=2`` boundary relation.

THE RE-SWEEP MERGE (``--merge-existing``, the default). The checked-in file
is the base and only the named states are read:

* a sourced endpoint whose own OSM object PASSES the screen is kept byte for
  byte apart from the verdict, and its object is reserved: it is never
  replaced by a worse one and never lost. A row this matcher wrote itself
  (it carries ``match_kind``) must also still satisfy the matcher, so a rule
  that turns out too broad can be tightened and re-judged by a re-run;
* a sourced endpoint that FAILS is replaced when the fixed matcher finds a
  candidate; when it finds none the row keeps its endpoint and carries the
  verdict (``endpoint_screen: refused`` and the sentence why), so nobody
  takes a railway line for a yard gate;
* a representative fallback takes a candidate when there is one;
* an estimated-near-city row (owner ruling, 2026-09-16) is never touched.

Within a city the facility with the fewest candidates chooses first, so the
one cold store in town goes to the cold storage facility and not to the
company yard that could have had any warehouse.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import osmium
from ffworld.world import get_world

sys.path.insert(0, str(Path(__file__).resolve().parent))
from facility_endpoint_match import RoleMatch, match_roles  # noqa: E402
from facility_endpoint_screen import screen_endpoint  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
FACILITY_ENDPOINTS_PATH = ROOT / "data" / "facility_endpoints.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
ACCESSED_DATE = "2026-06-27"
EARTH_RADIUS_MI = 3958.7613
DEFAULT_RADIUS_MI = 6.4

RAW_MARKERS = (
    "osm_id",
    "amenity=",
    "highway=",
    "operator=",
    "node/",
    "way/",
    "relation/",
)
STATE_SLUGS = {"District of Columbia": "district-of-columbia"}
TARGET_FACILITY_TYPES = {
    "air_cargo",
    "automotive_plant",
    "chemical_petroleum_terminal",
    "cold_storage",
    "company_yard",
    "construction_materials_yard",
    "cross_dock",
    "distribution",
    "dry_warehouse",
    "farm_elevator",
    "food_processor",
    "food_terminal",
    "grocery_retail_dc",
    "industrial_park",
    "intermodal",
    "intermodal_ramp",
    "lumber_paper",
    "manufacturing",
    "manufacturing_plant",
    "mine_quarry",
    "parcel_hub",
    "port",
    "port_terminal",
    "rail",
    "retail_distribution",
    "steel_industrial",
    "terminal",
    "warehouse",
}
# The tag keys a freight site can state its identity with. An object with
# none of them cannot pass the screen, so it is never handed to Python.
SITE_KEYS = (
    "industrial",
    "landuse",
    "man_made",
    "building",
    "office",
    "amenity",
    "railway",
    "harbour",
    # A sawmill can carry its craft and nothing else.
    "craft",
)
BORDER_REFUSAL = "The sourced endpoint lies across the national border from its city."
MATCHER_REFUSAL = (
    "The sourced endpoint no longer states this facility's trade under the matcher's rules."
)


@dataclass(frozen=True)
class FacilityTarget:
    facility_id: str
    city: str
    state: str
    name: str
    facility_type: str
    lat: float
    lon: float
    source_note: str
    # The city's own coordinate. ``lat``/``lon`` are the facility's
    # REPRESENTATIVE pin, a synthetic offset that can sit in the river or
    # across it (Detroit's dry warehouse pin is in Windsor): distance is
    # measured from the pin, the border is judged from the city.
    city_lat: float | None = None
    city_lon: float | None = None

    @property
    def anchor(self) -> tuple[float, float]:
        if self.city_lat is None or self.city_lon is None:
            return (self.lat, self.lon)
        return (self.city_lat, self.city_lon)


@dataclass(frozen=True)
class Candidate:
    roles: tuple[str, ...]
    name: str
    lat: float
    lon: float
    score: int
    source_ref: str
    mapping: str
    # (role, tier, reason) per role; see facility_endpoint_match for the rank.
    matches: tuple[tuple[str, int, str], ...] = ()

    def match_for(self, role: str) -> RoleMatch | None:
        for name, tier, reason in self.matches:
            if name == role:
                return RoleMatch(tier, reason)
        return None


@dataclass
class CityBucket:
    targets: list[FacilityTarget] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)


def _load_local_geometry_tool():
    path = TOOLS_DIR / "build_local_geometry.py"
    spec = importlib.util.spec_from_file_location("build_local_geometry", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_facility_endpoints(
    cache_dir: Path,
    *,
    radius_mi: float = DEFAULT_RADIUS_MI,
    states: tuple[str, ...] | None = None,
    existing: dict[str, Any] | None = None,
    accessed: str = ACCESSED_DATE,
) -> dict[str, Any]:
    """Sweep the extracts and return the payload to write.

    Without ``existing`` this is a whole rebuild. With it (the checked-in
    payload) only ``states`` are read and the result is the re-sweep merge
    the module docstring describes.
    """
    targets = collect_targets()
    if existing is not None:
        return resweep(existing, targets, cache_dir, radius_mi, states, accessed)

    by_state: dict[str, dict[str, CityBucket]] = defaultdict(dict)
    for target in targets:
        by_state[target.state].setdefault(target.city, CityBucket()).targets.append(target)

    payload = {
        "version": 1,
        "generated": generated_block(radius_mi),
        "sources": [],
        "endpoints": {},
    }
    state_count = len(by_state)
    for state_index, state in enumerate(sorted(by_state), start=1):
        if states is not None and state not in states:
            continue
        extract = state_extract_path(cache_dir, state)
        payload["sources"].append(source_record(state, extract))
        buckets = by_state[state]
        print(
            f"[{state_index}/{state_count}] {state}: {len(buckets)} cities",
            flush=True,
        )
        if extract.exists():
            collect_state_candidates(extract, buckets, radius_mi)
        for city in sorted(buckets):
            for record in endpoint_records_for_city(buckets[city], extract, radius_mi):
                payload["endpoints"][record["facility_id"]] = record
    payload["coverage"] = coverage_summary(payload["endpoints"])
    return payload


def generated_block(radius_mi: float) -> dict[str, Any]:
    return {
        "accessed": ACCESSED_DATE,
        "family": "OpenStreetMap local Geofabrik extracts plus checked-in world facilities",
        "radius_mi": radius_mi,
        "source_policy": "Build-time only; runtime reads this compact checked-in file.",
        "gate_policy": (
            "OSM facility polygons/points are endpoint evidence. Gate, yard, driveway, "
            "and dock hints stay false unless a future source explicitly provides them."
        ),
        "road_policy": (
            "This layer does not snap sourced endpoints to roads. Runtime may combine "
            "it with local_approaches.json for existing nearest-road context."
        ),
    }


def collect_targets() -> list[FacilityTarget]:
    world = get_world()
    targets: list[FacilityTarget] = []
    for city_name in world.city_names():
        city = world.city(city_name)
        for location in city.locations:
            targets.append(
                FacilityTarget(
                    facility_id=location.id,
                    city=city_name,
                    state=city.state,
                    name=location.name,
                    facility_type=location.type,
                    lat=location.lat or city.lat,
                    lon=location.lon or city.lon,
                    source_note=location.source_note,
                    city_lat=city.lat,
                    city_lon=city.lon,
                )
            )
    return targets


def collect_state_candidates(
    osm_path: Path,
    buckets: dict[str, CityBucket],
    radius_mi: float,
) -> list[tuple[float, float, float, float]]:
    """Fill each city bucket with its classified candidates; returns the
    national border segments it screened them against."""
    cities = {city: bucket.targets[0].anchor for city, bucket in buckets.items() if bucket.targets}
    # A facility searches `radius_mi` around its own pin, so the city bucket
    # has to reach as far as its farthest pin plus the radius.
    reach = {
        city: radius_mi
        + max(_haversine_mi(*cities[city], target.lat, target.lon) for target in bucket.targets)
        for city, bucket in buckets.items()
        if bucket.targets
    }
    widest = max(reach.values(), default=radius_mi)
    border = national_border_segments(osm_path, cities, widest)
    entities = osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY
    processor = (
        osmium.FileProcessor(str(osm_path), entities=entities)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter(*SITE_KEYS))
    )
    for obj in processor:
        tags = _tags(obj.tags)
        if hasattr(obj, "nodes"):
            coords = _way_coords(obj)
            if not coords:
                continue
            lat, lon = _centroid(coords)
            source_ref = f"way/{obj.id}"
        else:
            try:
                if not obj.location.valid():
                    continue
                lat = float(obj.location.lat)
                lon = float(obj.location.lon)
            except osmium.InvalidLocationError:
                continue
            source_ref = f"node/{obj.id}"
        near = [
            city
            for city in nearby_cities(cities, lat, lon, widest)
            if _haversine_mi(*cities[city], lat, lon) <= reach[city]
        ]
        if not near:
            continue
        candidate = candidate_from_tags(tags, lat, lon, source_ref)
        if candidate is None:
            continue
        for city in near:
            if not crosses_border(cities[city], (lat, lon), border):
                buckets[city].candidates.append(candidate)
    return border


def national_border_segments(
    osm_path: Path,
    cities: dict[str, tuple[float, float]],
    radius_mi: float,
) -> list[tuple[float, float, float, float]]:
    """READ: the ways of every ``admin_level=2`` boundary relation in the
    extract, as ``(lat1, lon1, lat2, lon2)`` segments, kept only where they
    pass within reach of a target city. The tags live on the relation (the
    Rio Grande's ways carry none), hence the two passes; a state with no
    national border costs one quick relation scan."""
    bits = osmium.osm.osm_entity_bits
    way_ids: set[int] = set()
    relations = osmium.FileProcessor(str(osm_path), entities=bits.RELATION).with_filter(
        osmium.filter.TagFilter(("admin_level", "2"))
    )
    for relation in relations:
        if relation.tags.get("boundary") != "administrative":
            continue
        way_ids.update(member.ref for member in relation.members if member.type == "w")
    if not way_ids or not cities:
        return []
    reach = radius_mi * 1.5
    segments: list[tuple[float, float, float, float]] = []
    ways = (
        osmium.FileProcessor(str(osm_path), entities=bits.NODE | bits.WAY)
        .with_locations()
        .with_filter(osmium.filter.EntityFilter(bits.WAY))
        .with_filter(osmium.filter.IdFilter(sorted(way_ids)).enable_for(bits.WAY))
    )
    for way in ways:
        coords = _way_coords(way)
        for (lat1, lon1), (lat2, lon2) in zip(coords, coords[1:], strict=False):
            if nearby_cities(cities, lat1, lon1, reach) or nearby_cities(cities, lat2, lon2, reach):
                segments.append((lat1, lon1, lat2, lon2))
    return segments


def crosses_border(
    start: tuple[float, float],
    end: tuple[float, float],
    border: list[tuple[float, float, float, float]],
) -> bool:
    """Whether the straight line ``start`` -> ``end`` crosses a border segment.
    Planar on raw degrees: over six miles the error is far below the width of
    the strip being screened."""

    def side(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    sy, sx = start
    ey, ex = end
    for lat1, lon1, lat2, lon2 in border:
        d1 = side(sx, sy, ex, ey, lon1, lat1)
        d2 = side(sx, sy, ex, ey, lon2, lat2)
        d3 = side(lon1, lat1, lon2, lat2, sx, sy)
        d4 = side(lon1, lat1, lon2, lat2, ex, ey)
        if (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0):
            return True
    return False


def endpoint_records_for_city(
    bucket: CityBucket,
    extract: Path,
    radius_mi: float,
) -> list[dict[str, Any]]:
    used_refs: set[str] = set()
    records: list[dict[str, Any]] = []
    chosen = assign_candidates(bucket.targets, bucket.candidates, used_refs, radius_mi)
    for target in sorted(bucket.targets, key=lambda item: item.facility_id):
        candidate = chosen.get(target.facility_id)
        if candidate is None:
            records.append(
                fallback_record(
                    target,
                    reason=f"No high-confidence source-backed OSM facility endpoint found within {radius_mi:g} miles in {extract.name}.",
                )
            )
            continue
        records.append(sourced_record(target, candidate, ACCESSED_DATE))
    return records


def assign_candidates(
    targets: list[FacilityTarget],
    candidates: list[Candidate],
    used_refs: set[str],
    radius_mi: float | None = None,
) -> dict[str, Candidate]:
    """One candidate per target, the most constrained target choosing first
    (DERIVED order: fewest open candidates, then facility id). ``used_refs``
    is updated in place."""
    chosen: dict[str, Candidate] = {}
    waiting = list(targets)
    while waiting:
        open_counts = {
            target.facility_id: len(open_candidates(target, candidates, used_refs, radius_mi))
            for target in waiting
        }
        waiting.sort(key=lambda target: (open_counts[target.facility_id], target.facility_id))
        target = waiting.pop(0)
        candidate = choose_candidate(target, candidates, used_refs, radius_mi)
        if candidate is not None:
            used_refs.add(candidate.source_ref)
            chosen[target.facility_id] = candidate
    return chosen


def open_candidates(
    target: FacilityTarget,
    candidates: list[Candidate],
    used_refs: set[str],
    radius_mi: float | None = None,
) -> list[Candidate]:
    """Unused candidates of the target's type, within ``radius_mi`` of the
    facility's pin when a radius is given (so ``approach_miles`` stays in the
    8-mile band)."""
    if target.facility_type not in TARGET_FACILITY_TYPES:
        return []
    return [
        candidate
        for candidate in candidates
        if target.facility_type in candidate.roles
        and candidate.source_ref not in used_refs
        and (
            radius_mi is None
            or _haversine_mi(target.lat, target.lon, candidate.lat, candidate.lon) <= radius_mi
        )
    ]


def sourced_record(
    target: FacilityTarget,
    candidate: Candidate,
    accessed: str,
    *,
    facility_id: str | None = None,
    replaced: dict[str, Any] | None = None,
) -> dict[str, Any]:
    match = candidate.match_for(target.facility_type)
    kind = match.kind if match else "read"
    mapping = match.reason if match else candidate.mapping
    record = {
        "facility_id": facility_id or target.facility_id,
        "city": target.city,
        "state": target.state,
        "facility_name": target.name,
        "facility_type": target.facility_type,
        "endpoint_name": candidate.name,
        "lat": round(candidate.lat, 6),
        "lon": round(candidate.lon, 6),
        "approach_miles": approach_miles(target.lat, target.lon, candidate.lat, candidate.lon),
        "approach_road": "local facility access road",
        "source_type": "osm_facility_endpoint",
        "source_ref": candidate.source_ref,
        "source_backed": True,
        "fallback": False,
        "fallback_reason": "",
        "nearest_road_context": False,
        "turn_level_geometry": False,
        "gate_hint": False,
        "yard_hint": False,
        "dock_hint": False,
        "mapping": mapping,
        # The site is READ from the object's tags. The TRADE is read too,
        # unless this says assumed: then the object is a freight site that
        # states no trade and merely stands in for the template facility.
        "match_kind": kind,
        "endpoint_screen": "passed",
        "source_note": (
            "Source-backed freight facility endpoint from a local OpenStreetMap "
            f"extract for {target.city}, {target.state}; matched to "
            f"{target.facility_type} by {mapping} (trade {kind}); road snapping, gates, "
            f"yards, and docks are not claimed by this layer; accessed {accessed}."
        ),
    }
    if replaced:
        record["replaced"] = replaced
    return record


def choose_candidate(
    target: FacilityTarget,
    candidates: list[Candidate],
    used_refs: set[str],
    radius_mi: float | None = None,
) -> Candidate | None:
    choices = open_candidates(target, candidates, used_refs, radius_mi)
    if not choices:
        return None

    def rank(candidate: Candidate) -> tuple[int, float, str]:
        match = candidate.match_for(target.facility_type)
        return (
            -(match.tier if match else 0),
            _haversine_mi(target.lat, target.lon, candidate.lat, candidate.lon),
            candidate.name,
        )

    choices.sort(key=rank)
    return choices[0]


def fallback_record(target: FacilityTarget, reason: str) -> dict[str, Any]:
    return {
        "facility_id": target.facility_id,
        "city": target.city,
        "state": target.state,
        "facility_name": target.name,
        "facility_type": target.facility_type,
        "endpoint_name": target.name,
        "lat": round(target.lat, 6),
        "lon": round(target.lon, 6),
        "approach_miles": 0.0,
        "approach_road": "",
        "source_type": "representative_fallback",
        "source_ref": "",
        "source_backed": False,
        "fallback": True,
        "fallback_reason": reason,
        "nearest_road_context": False,
        "turn_level_geometry": False,
        "gate_hint": False,
        "yard_hint": False,
        "dock_hint": False,
        "mapping": "",
        "source_note": (
            f"Representative fallback for {target.name} in {target.city}; "
            "not a claim about a specific real-world shipper, gate, yard, or dock."
        ),
    }


def candidate_from_tags(
    tags: dict[str, str],
    lat: float,
    lon: float,
    source_ref: str,
) -> Candidate | None:
    name = clean_text(tags.get("name") or tags.get("operator") or tags.get("brand") or "")
    if not name:
        return None
    matches = match_roles(tags, name)
    if not matches:
        return None
    best = max(matches.values(), key=lambda match: match.tier)
    return Candidate(
        roles=tuple(sorted(matches)),
        name=name,
        lat=lat,
        lon=lon,
        score=best.tier,
        source_ref=source_ref,
        mapping=best.reason,
        matches=tuple((role, match.tier, match.reason) for role, match in sorted(matches.items())),
    )


def classify(tags: dict[str, str], name: str) -> tuple[set[str], int, str]:
    """``(roles, best tier, why)`` for an object. The rules, and the kind of
    every value they read, are stated in ``facility_endpoint_match``: the
    object's own primary-key tags and whole words of its name, gated by
    ``facility_endpoint_screen``. Never a substring, never a stray tag value."""
    matches = match_roles(tags, name)
    if not matches:
        return set(), 0, ""
    best = max(matches.values(), key=lambda match: match.tier)
    return set(matches), best.tier, best.reason


# ------------------------------------------------------------------ re-sweep


def resweep(
    existing: dict[str, Any],
    targets: list[FacilityTarget],
    cache_dir: Path,
    radius_mi: float,
    states: tuple[str, ...] | None,
    accessed: str,
) -> dict[str, Any]:
    """The merge the module docstring describes, one state at a time."""
    local_geometry = _load_local_geometry_tool()
    world = get_world()
    target_by_id = {target.facility_id: target for target in targets}
    rows: dict[str, dict[str, Any]] = dict(existing["endpoints"])
    # Checked-in keys may predate the slug migration: resolve through the world.
    target_for_key: dict[str, FacilityTarget] = {}
    for key in rows:
        try:
            target_for_key[key] = target_by_id[world.facility_by_id(key).id]
        except KeyError:
            continue
    keys_by_state: dict[str, list[str]] = defaultdict(list)
    for key, target in target_for_key.items():
        keys_by_state[target.state].append(key)

    summary: dict[str, int] = defaultdict(int)
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    batch = sorted(states if states is not None else keys_by_state)
    sources = {str(source.get("state")): source for source in existing.get("sources") or []}
    for index, state in enumerate(batch, start=1):
        extract = state_extract_path(cache_dir, state)
        sources[state] = source_record(state, extract)
        keys = sorted(keys_by_state.get(state, []))
        if not extract.exists() or not keys:
            print(f"[{index}/{len(batch)}] {state}: skipped (no extract or no facilities)")
            continue
        started = time.time()
        buckets: dict[str, CityBucket] = {}
        for key in keys:
            target = target_for_key[key]
            buckets.setdefault(target.city, CityBucket()).targets.append(target)
        border = collect_state_candidates(extract, buckets, radius_mi)
        cities = {city: bucket.targets[0].anchor for city, bucket in buckets.items()}
        object_tags = local_geometry.read_object_tags(
            extract,
            {str(rows[key].get("source_ref") or "") for key in keys if rows[key]["source_backed"]},
        )

        keys_by_city: dict[str, list[str]] = defaultdict(list)
        for key in keys:
            keys_by_city[target_for_key[key].city].append(key)
        for city, city_keys in sorted(keys_by_city.items()):
            used_refs: set[str] = set()
            open_targets: list[FacilityTarget] = []
            key_for_target: dict[str, str] = {}
            verdicts: dict[str, str] = {}
            for key in city_keys:
                row = rows[key]
                target = target_for_key[key]
                kind = target.facility_type
                if row.get("estimated"):
                    summary["estimated_untouched"] += 1
                    continue
                if row["source_backed"]:
                    accepted, why = screen_endpoint(
                        kind, row["endpoint_name"], object_tags.get(row["source_ref"])
                    )
                    if accepted and row.get("match_kind"):
                        tags = object_tags.get(row["source_ref"]) or {}
                        if kind not in match_roles(tags, row["endpoint_name"]):
                            accepted, why = False, MATCHER_REFUSAL
                    if accepted and crosses_border(
                        cities[city], (float(row["lat"]), float(row["lon"])), border
                    ):
                        accepted, why = False, BORDER_REFUSAL
                    if accepted:
                        used_refs.add(row["source_ref"])
                        rows[key] = {**row, "endpoint_screen": "passed"}
                        rows[key].pop("endpoint_screen_reason", None)
                        summary["kept_passing"] += 1
                        by_type[kind]["kept_passing"] += 1
                        continue
                    verdicts[key] = why
                open_targets.append(target)
                key_for_target[target.facility_id] = key
            chosen = assign_candidates(open_targets, buckets[city].candidates, used_refs, radius_mi)
            for target in open_targets:
                key = key_for_target[target.facility_id]
                row = rows[key]
                kind = target.facility_type
                candidate = chosen.get(target.facility_id)
                was_sourced = bool(row["source_backed"])
                if candidate is not None:
                    replaced = (
                        {
                            "endpoint_name": row["endpoint_name"],
                            "reason": verdicts[key],
                            "accessed": accessed,
                        }
                        if was_sourced
                        else None
                    )
                    rows[key] = sourced_record(
                        target, candidate, accessed, facility_id=key, replaced=replaced
                    )
                    label = "replaced" if was_sourced else "filled_fallback"
                    if rows[key]["match_kind"] == "assumed":
                        summary["trade_assumed"] += 1
                elif was_sourced:
                    rows[key] = {
                        **row,
                        "endpoint_screen": "refused",
                        "endpoint_screen_reason": verdicts[key],
                    }
                    label = "refused_unreplaced"
                else:
                    label = "fallback_unfilled"
                summary[label] += 1
                by_type[kind][label] += 1
        print(
            f"[{index}/{len(batch)}] {state}: {len(keys)} facilities, "
            f"{time.time() - started:.0f}s; running totals {dict(summary)}",
            flush=True,
        )

    generated = dict(existing.get("generated") or {})
    prior = (generated.get("resweep") or {}) if isinstance(generated.get("resweep"), dict) else {}
    swept = sorted(set(prior.get("states") or []) | set(batch))
    generated["resweep"] = {
        "accessed": accessed,
        "radius_mi": radius_mi,
        "states": swept,
        "matcher": "facility_endpoint_match.match_roles gated by facility_endpoint_screen",
        "last_batch": {"states": batch, **dict(summary)},
    }
    payload = {
        "version": existing.get("version", 1),
        "generated": generated,
        "sources": [sources[state] for state in sorted(sources)],
        "endpoints": rows,
    }
    payload["coverage"] = coverage_summary(rows)
    print("By type (this batch):")
    for kind in sorted(by_type):
        print(f"  {kind:30} {dict(by_type[kind])}")
    sourced = payload["coverage"]["source_backed"]
    screen = payload["coverage"]["screen"]
    if sourced:
        print(
            f"SCREEN, whole file: of {sourced} sourced endpoints {screen['refused']} are NOT "
            f"freight sites ({screen['refused'] / sourced:.0%}), {screen['not_screened']} are in "
            f"states not yet re-swept, and {screen['trade_assumed']} are freight sites whose "
            f"trade is ASSUMED ({screen['trade_assumed'] / sourced:.0%}).",
            flush=True,
        )
    return payload


def coverage_summary(endpoints: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, dict[str, int]] = {}
    source_backed = 0
    fallback = 0
    gate_hints = 0
    screen = {"passed": 0, "refused": 0, "not_screened": 0, "trade_assumed": 0}
    for record in endpoints.values():
        item = by_type.setdefault(
            record["facility_type"],
            {"total": 0, "source_backed": 0, "fallback": 0, "screen_passed": 0},
        )
        item["total"] += 1
        if record["source_backed"]:
            source_backed += 1
            item["source_backed"] += 1
            verdict = str(record.get("endpoint_screen") or "not_screened")
            screen[verdict] = screen.get(verdict, 0) + 1
            if verdict == "passed":
                item["screen_passed"] += 1
            if record.get("match_kind") == "assumed":
                screen["trade_assumed"] += 1
        else:
            fallback += 1
            item["fallback"] += 1
        if record["gate_hint"] or record["yard_hint"] or record["dock_hint"]:
            gate_hints += 1
    return {
        "facilities": len(endpoints),
        "source_backed": source_backed,
        "fallback": fallback,
        "nearest_road_context": sum(
            1 for record in endpoints.values() if record["nearest_road_context"]
        ),
        "turn_level_geometry": sum(
            1 for record in endpoints.values() if record["turn_level_geometry"]
        ),
        "gate_yard_dock_hints": gate_hints,
        # How much of "source-backed" is a freight site (the screen READ the
        # object's own tags), and how much of that only ASSUMES the trade.
        "screen": screen,
        "by_type": by_type,
    }


def nearby_cities(
    cities: dict[str, tuple[float, float]],
    lat: float,
    lon: float,
    radius_mi: float,
) -> list[str]:
    # One degree of latitude is 69 miles: a cheap reject before the haversine.
    reach = radius_mi / 69.0 + 0.01
    return [
        city
        for city, (city_lat, city_lon) in cities.items()
        if abs(city_lat - lat) <= reach and _haversine_mi(city_lat, city_lon, lat, lon) <= radius_mi
    ]


def approach_miles(start_lat: float, start_lon: float, lat: float, lon: float) -> float:
    straight_line = _haversine_mi(start_lat, start_lon, lat, lon)
    return round(max(2.1, min(35.0, straight_line * 1.25)), 1)


def state_slug(state: str) -> str:
    return STATE_SLUGS.get(state, state.lower().replace(" ", "-"))


def state_extract_path(cache_dir: Path, state: str) -> Path:
    return cache_dir / f"{state_slug(state)}-latest.osm.pbf"


def source_record(state: str, extract: Path) -> dict[str, Any]:
    record: dict[str, Any] = {"state": state, "file": str(extract), "available": extract.exists()}
    if extract.exists():
        stat = extract.stat()
        record["bytes"] = stat.st_size
        record["modified"] = stat.st_mtime
    return record


def _tags(tags) -> dict[str, str]:
    return {str(tag.k): str(tag.v) for tag in tags}


def _way_coords(way) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    for node in way.nodes:
        try:
            if node.location.valid():
                coords.append((float(node.location.lat), float(node.location.lon)))
        except osmium.InvalidLocationError:
            continue
    return coords


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(lat for lat, _lon in points) / len(points),
        sum(lon for _lat, lon in points) / len(points),
    )


def clean_text(value: str) -> str:
    text = " ".join(str(value).split()).strip()
    lowered = text.lower()
    if any(marker in lowered for marker in RAW_MARKERS):
        return ""
    return text


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=FACILITY_ENDPOINTS_PATH)
    parser.add_argument("--radius-mi", type=float, default=DEFAULT_RADIUS_MI)
    parser.add_argument(
        "--states",
        nargs="*",
        default=None,
        help="States to read (default: every state with a facility)",
    )
    parser.add_argument(
        "--merge-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Re-sweep into --existing: passing endpoints are kept, failing ones replaced "
            "or labelled (default on). Off rebuilds the whole file from nothing."
        ),
    )
    parser.add_argument("--existing", type=Path, default=FACILITY_ENDPOINTS_PATH)
    parser.add_argument("--accessed", default=time.strftime("%Y-%m-%d"))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    existing = None
    if args.merge_existing and args.existing.exists():
        existing = json.loads(args.existing.read_text(encoding="utf-8"))
    payload = build_facility_endpoints(
        args.cache_dir,
        radius_mi=args.radius_mi,
        states=tuple(args.states) if args.states else None,
        existing=existing,
        accessed=args.accessed,
    )
    print(json.dumps(payload["coverage"], indent=2, sort_keys=True))
    if args.write:
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
