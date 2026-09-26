r"""Build compact local turn geometry from local OSM extracts.

Runtime gameplay reads ``local_geometry.json`` offline. This tool is build-time
only and never calls live routing APIs.

Example:
    uv run --group tooling python tools/build_local_geometry.py \
      --cache-dir C:\Users\joshu\.cache\freight-fate-osm\regions --write
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import osmium
from ffworld.world import get_world

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chain_match  # noqa: E402
from enrich_routes_pois import _maxspeed_from_tags  # noqa: E402  (shared OSM maxspeed parser)
from street_chain import MAJOR_HIGHWAYS, annotate, control_of  # noqa: E402
from yard_roads import (  # noqa: E402
    bans_trucks,
    is_blocking_barrier,
    is_yard_road,
    yard_road_path,
)

ROOT = Path(__file__).resolve().parents[1]
CITY_SERVICES_PATH = ROOT / "data" / "city_services.json"
LOCAL_APPROACHES_PATH = ROOT / "data" / "local_approaches.json"
LOCAL_GEOMETRY_PATH = ROOT / "data" / "local_geometry.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
ACCESSED_DATE = "2026-06-27"
EARTH_RADIUS_MI = 3958.7613
MAX_CITY_SERVICE_ROUTE_MI = 18.0
# Build-time fallback approach distance by service role, for services this
# tool could not fit a real routed geometry to. Gameplay no longer drives to
# city services (retired: feat(city)! "retire the drive to city services"),
# so this default lives only here now, not in the runtime world_services API.
CITY_SERVICE_APPROACH_MILES = {
    "freight_market": 3.0,
    "garage": 1.5,
    "truck_dealer": 2.5,
}
TARGET_SNAP_RADIUS_MI = 0.75
CITY_SNAP_RADIUS_MI = 1.25
GRAPH_PAD_MI = 1.5

# What to call a road OSM has no name for.
#
# Measured over the whole us-latest extract: of 24,671,936 drivable local ways
# carrying no `name`, 22,951,151 are `highway=service` -- driveways, delivery
# lanes and parking aisles -- and only 162,733 hold a recoverable TIGER name.
# So these roads are not missing their names; they do not have any. Valhalla
# cannot help either: it compiles OSM into a fixed schema that has no room for
# the tags a name might hide in.
#
# What CAN improve is the sentence. "Turn right onto unnamed public road" is
# heard at every turn onto one, on 12 percent of arrivals, and tells the
# driver nothing about what they are turning onto. The road class does know:
# a service way really is a service road, and an unnamed residential street
# really is a side street. Both are true, and both are worth more at the
# wheel than the absence of a name.
#
# The leading article is part of the label because every cue interpolates it
# directly -- "Turn right onto {road}." -- and "onto service road" is not
# English.
UNNAMED_SERVICE = "a service road"
UNNAMED_STREET = "a side street"
# The classes whose namelessness is honest rather than a data gap.
SERVICE_CLASSES = frozenset({"service", "living_street"})
# READ from OSM `service=*`: the service ways that are not roads a combination
# can be routed through, whatever else they are tagged.
#
# `highway=service` covers both the delivery road behind a warehouse and the
# queue lane at a coffee window, and until 2026-09-20 the router took either.
# A tester's approach to the Oshkosh dry warehouse turned off West Murdock
# Avenue, ran a chain of parking lanes, and was told "Continue onto Starbucks
# Drive-Through" -- OSM way 849313280, `highway=service`, `service=drive-
# through`, `oneway=yes`, and one car wide. Near Oshkosh alone the extract
# holds 120 drive-through ways, 1,010 parking aisles and 14 emergency accesses,
# all of which were routable.
#
# What each value asserts, from the OSM wiki's `Key:service`, and why a
# 53-foot combination cannot use it:
#   drive-through   a queue lane to a service window, kerbed and one lane wide
#   parking_aisle   the lane between two rows of parked cars
#   emergency_access a fire lane, usually gated or bollarded
#   bus             a busway, closed to other traffic
#   slipway         a boat ramp into the water
# `driveway`, `alley`, `yard` and an untagged service way stay routable: those
# are how a yard, a dock and a loading bay are actually reached.
# <https://wiki.openstreetmap.org/wiki/Key:service>
#
# `is_yard_road` has refused `emergency_access` since it was written; this is
# the same judgment applied to the public side of the graph.
UNROUTABLE_SERVICE = frozenset(
    {
        "drive-through",
        "drive_through",
        "drive-thru",
        "drive_thru",
        "parking_aisle",
        "emergency_access",
        "bus",
        "slipway",
    }
)

# READ from OSM `access=*`: who upstream says may use the way at all.
#
# `private`, `no` and `military` were refused from the start. The rest of
# this list came from the 2026-09-20 sweep: a chain into the Burlington
# grocery distribution centre ran 2.1 miles of "Route 127 Bike Path" (OSM way
# 1092499015, `highway=service`, `access=permit`) because a permit is not a
# refusal in the old set. Every value here is one upstream uses to say the
# way is closed to a truck that has not been let in:
#   permit       entry needs a permit issued in advance
#   residents    the people who live on it
#   employees    the staff of the site it belongs to
#   emergency    emergency vehicles
#   agricultural farm traffic; forestry, forest traffic
# `customers`, `delivery`, `destination`, `permissive`, `designated` and
# `official` stay routable: a truck bound for the site IS the traffic those
# name. <https://wiki.openstreetmap.org/wiki/Key:access>
CLOSED_ACCESS = frozenset(
    {
        "private",
        "no",
        "military",
        "permit",
        "residents",
        "employees",
        "emergency",
        "agricultural",
        "forestry",
    }
)
# Every label that stands in for a name rather than being one. Anything that
# has to ask "is this road actually named" tests membership here: the speed
# default used to compare against one literal string, so adding a second
# generic label would have silently moved 1,179 segments from 15 to 25 mph.
GENERIC_ROADS = frozenset({UNNAMED_SERVICE, UNNAMED_STREET, "unnamed public road"})
# A `*_link` way with no name of its own: the slip lane or short connector
# inside a junction. It is never spoken. Calling it "a side street" would be
# untrue and would announce a turn that is only the middle of one, so
# `collapse_segments` folds its length into the street it leaves and this
# label never reaches a segment.
JUNCTION_LINK = "<junction link>"
LINK_CLASSES = frozenset({"trunk_link", "primary_link", "secondary_link", "tertiary_link"})
# The most streets one chain speaks. A longer path keeps the streets at the
# DESTINATION end (see `collapse_segments`).
MAX_SPOKEN_SEGMENTS = 8


def is_named(road: str) -> bool:
    """Does this label name a road, or merely describe one?"""
    return bool(road) and road not in GENERIC_ROADS


# Surface roads a truck can be routed over. Motorways and their ramps stay
# out on purpose: a local chain is the streets between the yard and the
# highway, and the highway itself is the leg.
#
# `trunk` and the `*_link` connectors were missing until 2026-09-17, and that
# was the second-largest cause of "no connected public-road path": in
# California, New York and Texas 22 of 88 such failures were a town cut in two
# because its main street IS the US highway and OSM classes that at-grade road
# `trunk` (Main Street in Susanville, Redwood Highway in Crescent City), or
# because the only join between two carriageways is a `primary_link`. The
# endpoint then snapped to a fragment the start could not reach. A trunk road
# signed `motorroad=yes` is a motorway in all but class and stays out with
# them (see `road_label`).
ROUTABLE_HIGHWAYS = {
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "service",
    "living_street",
}
STATE_SLUGS = {"District of Columbia": "district-of-columbia"}
RAW_MARKERS = ("osm_id", "amenity=", "highway=", "operator=", "node/", "way/")


@dataclass(slots=True)
class Target:
    target_id: str
    target_type: str
    city: str
    state: str
    name: str
    lat: float
    lon: float
    start_lat: float
    start_lon: float
    role: str
    estimated: bool
    fallback_reason: str
    approach_road: str
    approach_miles: float
    source_note: str

    @property
    def source_backed_city_service(self) -> bool:
        return (
            self.target_type == "city_service" and not self.estimated and not self.fallback_reason
        )


@dataclass(slots=True)
class RouteGraph:
    nodes: dict[int, tuple[float, float]] = field(default_factory=dict)
    # each edge: (neighbor, miles, road, mph) -- mph is the way's real posted
    # limit or None where OSM does not tag one (honest absence).
    edges: dict[int, list[tuple[int, float, str, float | None]]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # The four below are only filled when a caller asks for yard roads (see
    # `yard_roads.py`). Private ways live apart from `nodes`/`edges` so the
    # public search and the public snap cannot see them.
    yard_nodes: dict[int, tuple[float, float]] = field(default_factory=dict)
    yard_edges: dict[int, list[tuple[int, float]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    # Public edges signed against trucks, both directions.
    no_truck: set[tuple[int, int]] = field(default_factory=set)
    # Blocking barrier nodes (gates, bollards), shared by every graph of a run.
    barriers: set[int] = field(default_factory=set)
    # Whether the PUBLIC search honours the two above. The yard-road fallback
    # always does. Off restores the search as it stood before 2026-09-20, so
    # the rule's cost can be measured rather than argued.
    truck_legal: bool = True

    # Filled only when a caller asks for street detail (`street_chain.py`):
    # edges drawn in their way's node order, edges on highway=service ways
    # (both directions), non-service ways meeting at each node, and the
    # signal/stop/give-way nodes, shared by every graph of a run.
    street_detail: bool = False
    forward: set[tuple[int, int]] = field(default_factory=set)
    service: set[tuple[int, int]] = field(default_factory=set)
    street_deg: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    controls: dict[int, tuple[str, str]] = field(default_factory=dict)
    # Edges on trunk/primary/secondary ways (both directions): the stand-in
    # for a numbered highway where a rural statute sets its own default.
    major: set[tuple[int, int]] = field(default_factory=set)
    # In town or out (``street_chain.TownJudge``), for the limit fill.
    town_judge: Any = None

    def add_edge(self, a: int, b: int, road: str, miles: float, mph: float | None) -> None:
        self.edges[a].append((b, miles, road, mph))
        self.edges[b].append((a, miles, road, mph))

    def add_yard_edge(self, a: int, b: int, miles: float) -> None:
        self.yard_edges[a].append((b, miles))
        self.yard_edges[b].append((a, miles))


@dataclass(frozen=True, slots=True)
class GeometryPath:
    miles: float
    segments: tuple[dict[str, Any], ...]
    # Miles of the facility's own private road at the target end, already
    # inside `miles` and spoken as `UNNAMED_SERVICE`. Zero for a public path.
    yard_miles: float = 0.0
    # With street detail only (`street_chain.annotate`): where the chain
    # leaves the public street, and the intersection counts for the meta.
    driveway: dict[str, Any] | None = None
    street_counts: dict[str, int] | None = None


def build_local_geometry(cache_dir: Path, only_states: set[str] | None = None) -> dict[str, Any]:
    targets = collect_targets()
    by_state: dict[str, list[Target]] = defaultdict(list)
    for target in targets:
        if only_states is not None and state_slug(target.state) not in only_states:
            continue
        by_state[target.state].append(target)

    geometries: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    routed: dict[str, GeometryPath] = {}
    state_count = len(by_state)
    for state_index, (state, state_targets) in enumerate(sorted(by_state.items()), start=1):
        print(
            f"[{state_index}/{state_count}] {state}: {len(state_targets)} targets",
            flush=True,
        )
        extract = state_extract_path(cache_dir, state)
        sources.append(source_record(state, extract))
        routable = [
            target
            for target in state_targets
            if target.source_backed_city_service
            and city_target_distance(target) <= MAX_CITY_SERVICE_ROUTE_MI
        ]
        if extract.exists() and routable:
            routed.update(route_state_targets(extract, routable))
        for target in state_targets:
            geometry = routed.get(target.target_id)
            geometries[target.target_id] = geometry_record(target, geometry, extract)

    payload = {
        "version": 1,
        "generated": {
            "accessed": ACCESSED_DATE,
            "family": "OpenStreetMap local Geofabrik extracts plus checked-in local approach data",
            "source_policy": "Build-time only; runtime reads this compact checked-in file.",
            "city_service_route_limit_mi": MAX_CITY_SERVICE_ROUTE_MI,
            "routing_decision": (
                "OpenRouteService driving-hgv is already used by the highway corridor "
                "pipeline, but this local batch uses a local OSM PBF road graph so it "
                "can rebuild without hundreds of live directions calls. These records "
                "are source-backed local street geometry, not ORS-certified HGV routes."
            ),
            "ors_hgv_status": (
                "Feasible as a credential-gated future refinement for selected sourced "
                "service endpoints; not used for this checked-in local geometry bake."
            ),
        },
        "sources": sources,
        "coverage": coverage_summary(geometries),
        "geometries": geometries,
    }
    return payload


def services_by_city_key(world, raw_cities: dict) -> dict[str, list]:
    """Remap city_services.json onto current city keys.

    The checked-in file predates the slug migration and the map expansion:
    keys are old display names and newer cities are absent. Cities without
    an entry simply have no sourced services yet and are skipped."""
    by_key: dict[str, list] = {}
    for name, entries in raw_cities.items():
        key = world.resolve_city_key(name)
        if key in world.cities:
            by_key[key] = entries
    return by_key


def collect_targets() -> list[Target]:
    world = get_world()
    services = services_by_city_key(
        world, json.loads(CITY_SERVICES_PATH.read_text(encoding="utf-8"))["cities"]
    )
    approaches = json.loads(LOCAL_APPROACHES_PATH.read_text(encoding="utf-8"))["approaches"]
    targets: list[Target] = []
    missing_facilities: list[str] = []
    for city_name in world.city_names():
        city = world.city(city_name)
        for entry in services.get(city_name, ()):
            target_id = f"city_service:{city_name}:{entry['key']}"
            approach = approaches[target_id]
            fallback = bool(entry.get("fallback")) or bool(approach.get("fallback"))
            targets.append(
                Target(
                    target_id=target_id,
                    target_type="city_service",
                    city=city_name,
                    state=city.state,
                    name=str(entry["name"]),
                    lat=float(entry["lat"]),
                    lon=float(entry["lon"]),
                    start_lat=city.lat,
                    start_lon=city.lon,
                    role=str(entry["key"]),
                    estimated=fallback,
                    fallback_reason=str(entry.get("fallback_reason", "")),
                    approach_road=str(approach.get("road", "")),
                    approach_miles=float(approach.get("approach_miles", entry["approach_miles"])),
                    source_note=str(entry.get("source_note", "")),
                )
            )
        for location in city.locations:
            target_id = f"facility:{location.id}"
            # A facility the world knows and local_approaches.json does not is
            # a stale INPUT, not a reason to abandon the build: the approaches
            # bake predates it. Crashing here threw away 6,910 good targets
            # over one quarry in Elberton, and named no way to find out how
            # many others were missing.
            approach = approaches.get(target_id)
            if approach is None:
                missing_facilities.append(target_id)
                continue
            targets.append(
                Target(
                    target_id=target_id,
                    target_type="facility",
                    city=city_name,
                    state=city.state,
                    name=location.name,
                    lat=float(approach.get("lat", location.lat or city.lat)),
                    lon=float(approach.get("lon", location.lon or city.lon)),
                    start_lat=city.lat,
                    start_lon=city.lon,
                    role=location.type,
                    estimated=True,
                    fallback_reason=(
                        "Facility target uses representative freight-market coordinates, "
                        "so turn-level gate, yard, or dock routing is not claimed yet."
                    ),
                    approach_road=str(approach.get("road", "")),
                    approach_miles=float(approach.get("approach_miles", 0.0)),
                    source_note=location.source_note,
                )
            )
    if missing_facilities:
        print(
            f"  {len(missing_facilities)} facilities have no approach record and were"
            " skipped -- rebuild local_approaches.json to cover them:"
        )
        for target_id in missing_facilities[:8]:
            print(f"    {target_id}")
        if len(missing_facilities) > 8:
            print(f"    ... and {len(missing_facilities) - 8} more")
    return targets


def read_object_tags(osm_path: Path, refs: set[str]) -> dict[str, dict[str, str]]:
    """The tags of the named OSM objects (``node/123``, ``way/456``), READ
    from the extract. A ref the extract no longer holds is simply absent."""
    wanted: dict[str, list[int]] = {"node": [], "way": []}
    for ref in refs:
        kind, _, number = ref.partition("/")
        if kind in wanted and number.isdigit():
            wanted[kind].append(int(number))
    if not wanted["node"] and not wanted["way"]:
        return {}
    bits = osmium.osm.osm_entity_bits
    processor = (
        osmium.FileProcessor(str(osm_path), entities=bits.NODE | bits.WAY)
        .with_filter(osmium.filter.EmptyTagFilter())
        # An id filter only judges the entity kind it is enabled for, and an
        # empty list would pass everything, hence the impossible id 0.
        .with_filter(osmium.filter.IdFilter(sorted(wanted["node"]) or [0]).enable_for(bits.NODE))
        .with_filter(osmium.filter.IdFilter(sorted(wanted["way"]) or [0]).enable_for(bits.WAY))
    )
    found: dict[str, dict[str, str]] = {}
    for obj in processor:
        kind = "way" if hasattr(obj, "nodes") else "node"
        found[f"{kind}/{obj.id}"] = {str(tag.k): str(tag.v) for tag in obj.tags}
    return found


def route_state_targets(
    osm_path: Path,
    targets: list[Target],
    failures: dict[str, str] | None = None,
    *,
    yard_roads: bool = False,
    truck_legal: bool = True,
    street_detail: bool = False,
    exit_starts: dict[str, list[dict[str, Any]]] | None = None,
    exit_routes: dict[tuple[str, int], GeometryPath | str] | None = None,
    match_chains: dict[str, list[dict[str, Any]]] | None = None,
    matched: dict[str, GeometryPath | str] | None = None,
    town_judge: Any = None,
) -> dict[str, GeometryPath]:
    """Route every target over its own clipped graph.

    ``failures``, when given, receives a ``ROUTE_FAILURE_*`` code per target
    that got no path, so a caller can record WHY instead of one catch-all
    sentence.

    ``yard_roads`` also reads ``access=private`` ways and barrier nodes, so a
    target the public roads do not reach may be reached over its own private
    road (``yard_roads.py`` holds the rule). Off, nothing changes.

    ``street_detail`` fills each segment's limit provenance and controls and
    the path's driveway (``street_chain.py``). ``exit_starts`` maps a target
    to extra start points (``node``, ``lat``, ``lon``, ``budget_mi``) -- the
    ramp terminals -- each routed over the same graph, whole (never cut to
    ``MAX_SPOKEN_SEGMENTS``), into ``exit_routes[(target_id, node)]``: the
    path, or its failure code. ``match_chains`` maps a target to the
    segments of a chain baked before the street detail; its path is read
    back off the same graph (``chain_match.py``) into ``matched``.

    ``town_judge`` says whether a point is in town (``street_chain``'s
    ``TownJudge``); street detail cannot be baked without one."""
    if street_detail and town_judge is None:
        raise ValueError("street detail needs a town judge (street_chain.census_town_judge)")
    barriers: set[int] = set()
    controls: dict[int, tuple[str, str]] = {}
    graphs = {
        target.target_id: RouteGraph(
            barriers=barriers,
            truck_legal=truck_legal,
            street_detail=street_detail,
            controls=controls,
            town_judge=town_judge,
        )
        for target in targets
    }
    exit_starts = exit_starts or {}
    boxes = {
        target.target_id: target_bounds(target, exit_starts.get(target.target_id, ()))
        for target in targets
    }
    grid = target_grid(targets, boxes)
    entities = osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY
    processor = (
        osmium.FileProcessor(str(osm_path), entities=entities)
        .with_locations()
        .with_filter(
            osmium.filter.KeyFilter("highway", "barrier")
            if yard_roads
            else osmium.filter.KeyFilter("highway")
        )
    )
    for way in processor:
        if not hasattr(way, "nodes"):
            # Nodes come before ways in an extract, so the barrier and
            # control sets are complete by the time the first way is read.
            if yard_roads or street_detail:
                node_tags = {str(t.k): str(t.v) for t in way.tags}
                if yard_roads and is_blocking_barrier(node_tags):
                    barriers.add(int(way.id))
                control = control_of(node_tags) if street_detail else None
                if control is not None:
                    controls[int(way.id)] = control
            continue
        tags = {str(tag.k): str(tag.v) for tag in way.tags}
        road = road_label(tags)
        private = not road and yard_roads and is_yard_road(tags, ROUTABLE_HIGHWAYS)
        if not road and not private:
            continue
        no_truck = yard_roads and bool(road) and bans_trucks(tags)
        service = tags.get("highway") == "service"
        major = tags.get("highway") in MAJOR_HIGHWAYS
        coords = way_coords(way)
        if len(coords) < 2:
            continue
        # Real posted limit for this street, or None where OSM does not tag one.
        parsed = _maxspeed_from_tags(tags)
        way_mph = parsed[0] if parsed is not None else None
        candidate_ids = way_target_ids(grid, coords)
        if not candidate_ids:
            continue
        way_box = bounds_for_points([(lat, lon) for _ref, lat, lon in coords])
        for target_id in candidate_ids:
            if not bounds_intersect(way_box, boxes[target_id]):
                continue
            graph = graphs[target_id]
            prev: tuple[int, float, float] | None = None
            for ref, lat, lon in coords:
                (graph.yard_nodes if private else graph.nodes)[ref] = (lat, lon)
                if prev is not None:
                    miles = haversine_mi(prev[1], prev[2], lat, lon)
                    if miles > 0 and private:
                        graph.add_yard_edge(prev[0], ref, miles)
                    elif miles > 0:
                        graph.add_edge(prev[0], ref, road, miles, way_mph)
                        if no_truck:
                            graph.no_truck.update({(prev[0], ref), (ref, prev[0])})
                        if street_detail:
                            graph.forward.add((prev[0], ref))
                            if major:
                                graph.major.update({(prev[0], ref), (ref, prev[0])})
                            if service:
                                graph.service.update({(prev[0], ref), (ref, prev[0])})
                            else:
                                graph.street_deg[prev[0]] += 1
                                graph.street_deg[ref] += 1
                prev = (ref, lat, lon)
    routed: dict[str, GeometryPath] = {}
    for target in targets:
        graph = graphs[target.target_id]
        path = shortest_geometry(target, graph, failures)
        if path is not None:
            routed[target.target_id] = path
        for start in exit_starts.get(target.target_id, ()):
            why: dict[str, str] = {}
            from_terminal = replace(
                target,
                start_lat=start["lat"],
                start_lon=start["lon"],
                approach_miles=start["budget_mi"],
            )
            found = shortest_geometry(
                from_terminal, graph, why, start_ref=start["node"], max_segments=None
            )
            if exit_routes is not None:
                exit_routes[(target.target_id, start["node"])] = (
                    found if found is not None else why.get(target.target_id, "")
                )
        recorded = (match_chains or {}).get(target.target_id)
        if recorded and matched is not None:
            matched[target.target_id] = match_recorded_chain(target, graph, recorded)
    return routed


def match_recorded_chain(
    target: Target, graph: RouteGraph, recorded: list[dict[str, Any]]
) -> GeometryPath | str:
    """A baked chain's own path, recovered by its street names and miles, with
    its street detail; or why it could not be (``chain_match.MATCH_*``)."""
    every_node = {**graph.yard_nodes, **graph.nodes}
    end = None
    for ref, (lat, lon) in every_node.items():
        miles = haversine_mi(target.lat, target.lon, lat, lon)
        if end is None or miles < end[1]:
            end = (ref, miles)
    if end is None or end[1] > TARGET_SNAP_RADIUS_MI:
        return chain_match.MATCH_NO_END
    found = chain_match.match_path(
        graph, end[0], recorded, GENERIC_ROADS, JUNCTION_LINK, UNNAMED_SERVICE
    )
    if isinstance(found, str):
        return found
    path_nodes, raw_edges, kinds = found
    coords = [every_node[ref] for ref in path_nodes]
    segments = collapse_segments(raw_edges, coords, None)
    if not chain_match.same_chain(segments, recorded, GENERIC_ROADS):
        return chain_match.MATCH_SHAPE
    total = round(sum(segment["miles"] for segment in segments), 2)
    yard = round(
        sum(edge[1] for edge, kind in zip(raw_edges, kinds, strict=True) if kind == "private"), 2
    )
    return _finish(target, graph, segments, path_nodes, coords, raw_edges, kinds, total, yard)


# Why `shortest_geometry` returned nothing. Four different facts used to share
# one "no connected path" sentence, which is how a search that merely ran out
# of budget read as a town with no roads for three sweeps.
ROUTE_FAILURE_NO_START_ROAD = "no_start_road"
ROUTE_FAILURE_NO_TARGET_ROAD = "no_target_road"
ROUTE_FAILURE_OVER_BUDGET = "over_budget"
ROUTE_FAILURE_DISCONNECTED = "disconnected"
# Split out of `disconnected` on 2026-09-20 so the two can be judged apart.
# A way signed against trucks is a SIGN: there is no reading in which a
# loaded truck may drive up it, so a chain that needs one is wrong and a
# prior chain that needed one is demoted. An untagged `barrier=gate` is a
# GUESS -- as often a farm gate standing open as a locked one, and at an
# industrial site it is usually the facility's own gate, which the owner's
# 2026-09-17 yard-road ruling already lets a truck with a load for that dock
# pass. So a gate refuses a NEW chain and never takes an existing one away.
ROUTE_FAILURE_TRUCK_BANNED = "truck_banned"
ROUTE_FAILURE_GATED = "gated"
# A ramp terminal node the surface graph does not carry: the ramp ends on a
# road this router refuses (a motorroad, a closed way) or where link data ends.
ROUTE_FAILURE_TERMINAL_OFF_GRAPH = "terminal_off_graph"


def _connected(
    graph: RouteGraph,
    start_ref: int,
    end_ref: int,
    *,
    barriers: bool = True,
    no_truck: bool = True,
) -> bool:
    """Is there any path at all, however long? Asked after a failure, to tell
    a search that ran out of budget from a town with no way through.

    ``barriers`` and ``no_truck`` say which of the two rules to honour, so a
    caller can ask the same question three ways and learn WHICH rule closed
    the route (:func:`why_disconnected`)."""
    honour_barriers = barriers and graph.truck_legal
    honour_no_truck = no_truck and graph.truck_legal
    seen = {start_ref}
    stack = [start_ref]
    while stack:
        node = stack.pop()
        if node == end_ref:
            return True  # arriving at a gate is fine; driving through is not
        if honour_barriers and node in graph.barriers:
            continue
        for nxt, _miles, _road, _mph in graph.edges.get(node, ()):
            if nxt not in seen and not (honour_no_truck and (node, nxt) in graph.no_truck):
                seen.add(nxt)
                stack.append(nxt)
    return False


def why_disconnected(graph: RouteGraph, start_ref: int, end_ref: int) -> str:
    """Which rule closed the route: the truck sign, the gate, or neither.

    Asked only when the truck-legal search found nothing. Opening the rules
    one at a time is what separates "a sign says no trucks" -- a fact -- from
    "there is a gate drawn here" -- a guess -- from "there is simply no road".
    The sign is reported first: where both apply, the sign is the one that
    settles it.
    """
    if _connected(graph, start_ref, end_ref, no_truck=False):
        return ROUTE_FAILURE_TRUCK_BANNED
    if _connected(graph, start_ref, end_ref, barriers=False):
        return ROUTE_FAILURE_GATED
    return ROUTE_FAILURE_DISCONNECTED


def shortest_geometry(
    target: Target,
    graph: RouteGraph,
    failures: dict[str, str] | None = None,
    *,
    start_ref: int | None = None,
    max_segments: int | None = MAX_SPOKEN_SEGMENTS,
) -> GeometryPath | None:
    """The shortest public path from the target's start to the target.

    ``start_ref`` pins the start to one OSM node (a ramp terminal), which
    must be on the graph: a terminal on a road this graph does not carry is
    a failure (``ROUTE_FAILURE_TERMINAL_OFF_GRAPH``), never a snap to some
    other road. ``max_segments`` None keeps every street of the path."""

    def fail(code: str) -> None:
        if failures is not None:
            failures[target.target_id] = code

    if not graph.nodes:
        return fail(ROUTE_FAILURE_NO_START_ROAD)
    if start_ref is not None:
        if start_ref not in graph.nodes:
            return fail(ROUTE_FAILURE_TERMINAL_OFF_GRAPH)
        start: tuple[int, float] | None = (start_ref, 0.0)
    else:
        start = nearest_node(graph, target.start_lat, target.start_lon)
    end = nearest_node(graph, target.lat, target.lon)
    if start is None or end is None:
        return fail(ROUTE_FAILURE_NO_START_ROAD)
    start_ref, start_dist = start
    end_ref, end_dist = end
    if start_dist > CITY_SNAP_RADIUS_MI:
        return fail(ROUTE_FAILURE_NO_START_ROAD)
    if end_dist > TARGET_SNAP_RADIUS_MI:
        return fail(ROUTE_FAILURE_NO_TARGET_ROAD)
    dist: dict[int, float] = {start_ref: 0.0}
    prev: dict[int, tuple[int, str, float | None]] = {}
    heap: list[tuple[float, int]] = [(0.0, start_ref)]
    while heap:
        miles, node = heapq.heappop(heap)
        if node == end_ref:
            break
        if miles > dist.get(node, float("inf")):
            continue
        if miles > max(target.approach_miles * 1.8, 3.0):
            continue
        # A gate is reached and never driven through, so a barrier ON the
        # facility's own snap node still lets the chain arrive there. Both
        # rules are the yard search's, applied to the public roads at last:
        # until 2026-09-20 only the private-road fallback honoured them, and a
        # public chain could be spoken straight through a locked gate or up a
        # street signed against trucks.
        if graph.truck_legal and node in graph.barriers:
            continue
        for nxt, edge_miles, road, mph in graph.edges.get(node, ()):
            if graph.truck_legal and (node, nxt) in graph.no_truck:
                continue
            nd = miles + edge_miles
            if nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                prev[nxt] = (node, road, mph)
                heapq.heappush(heap, (nd, nxt))
    if end_ref not in dist:
        if _connected(graph, start_ref, end_ref):
            return fail(ROUTE_FAILURE_OVER_BUDGET)
        if graph.yard_edges:
            return yard_road_geometry(target, graph, start_ref, fail, max_segments)
        return fail(why_disconnected(graph, start_ref, end_ref))
    node = end_ref
    path_nodes = [node]
    reversed_roads: list[str] = []
    reversed_speeds: list[float | None] = []
    while node != start_ref:
        prev_node, road, mph = prev[node]
        reversed_roads.append(road)
        reversed_speeds.append(mph)
        path_nodes.append(prev_node)
        node = prev_node
    path_nodes.reverse()
    roads = list(reversed(reversed_roads))  # one road label per edge
    speeds = list(reversed(reversed_speeds))  # one posted limit (or None) per edge
    coords = [graph.nodes[ref] for ref in path_nodes]
    raw_edges = [
        (roads[i], haversine_mi(*coords[i], *coords[i + 1]), speeds[i]) for i in range(len(roads))
    ]
    segments = collapse_segments(raw_edges, coords, max_segments)
    if not segments:
        return fail(ROUTE_FAILURE_DISCONNECTED)
    total = round(sum(segment["miles"] for segment in segments), 2)
    if total > max(target.approach_miles * 1.8, 3.0):
        return fail(ROUTE_FAILURE_OVER_BUDGET)
    kinds = [
        "service" if (a, b) in graph.service else "street"
        for a, b in zip(path_nodes, path_nodes[1:], strict=False)
    ]
    return _finish(target, graph, segments, path_nodes, coords, raw_edges, kinds, total, 0.0)


def _finish(
    target: Target,
    graph: RouteGraph,
    segments: list[dict[str, Any]],
    path_nodes: list[int],
    coords: list[tuple[float, float]],
    raw_edges: list[tuple[str, float, float | None]],
    kinds: list[str],
    total: float,
    yard_miles: float,
) -> GeometryPath:
    driveway = counts = None
    if graph.street_detail:
        driveway, counts = annotate(
            segments,
            path_nodes,
            coords,
            [edge[1] for edge in raw_edges],
            kinds,
            graph.forward,
            graph.controls,
            graph.street_deg,
            target.state,
            graph.major,
            town_judge=graph.town_judge,
        )
    return GeometryPath(total, tuple(segments), yard_miles, driveway, counts)


def yard_road_geometry(
    target: Target,
    graph: RouteGraph,
    start_ref: int,
    fail,
    max_segments: int | None = MAX_SPOKEN_SEGMENTS,
) -> GeometryPath | None:
    """The fallback for a target the public roads do not reach: a path whose
    last link is the target's own private road (rule: ``yard_roads.py``).

    The target is snapped again, this time to the nearest node of ANY road,
    public or private, inside the same snap radius: the yard's own road is
    the road the endpoint stands on. Every edge of the yard stretch is
    labelled ``UNNAMED_SERVICE`` with no posted limit of its own; nothing is
    read from a private way but its geometry."""
    every_node = {**graph.yard_nodes, **graph.nodes}
    end: tuple[int, float] | None = None
    for ref, (lat, lon) in every_node.items():
        miles = haversine_mi(target.lat, target.lon, lat, lon)
        if end is None or miles < end[1]:
            end = (ref, miles)
    if end is None or end[1] > TARGET_SNAP_RADIUS_MI:
        return fail(ROUTE_FAILURE_NO_TARGET_ROAD)
    found = yard_road_path(graph, start_ref, end[0])
    if found is None:
        print(
            f"  yard road refused: {target.target_id}: " + _yard_refusal(graph, start_ref, end[0]),
            flush=True,
        )
        return fail(ROUTE_FAILURE_DISCONNECTED)
    path_nodes, in_yard = found
    coords = [every_node[ref] for ref in path_nodes]
    raw_edges: list[tuple[str, float, float | None]] = []
    yard_miles = 0.0
    for i, yard in enumerate(in_yard):
        miles = haversine_mi(*coords[i], *coords[i + 1])
        if yard:
            yard_miles += miles
            raw_edges.append((UNNAMED_SERVICE, miles, None))
            continue
        # The public edge this step used: the shortest one between the pair.
        _nxt, _miles, road, mph = min(
            (edge for edge in graph.edges[path_nodes[i]] if edge[0] == path_nodes[i + 1]),
            key=lambda edge: edge[1],
        )
        raw_edges.append((road, miles, mph))
    segments = collapse_segments(raw_edges, coords, max_segments)
    if not segments:
        return fail(ROUTE_FAILURE_DISCONNECTED)
    total = round(sum(segment["miles"] for segment in segments), 2)
    if total > max(target.approach_miles * 1.8, 3.0):
        return fail(ROUTE_FAILURE_OVER_BUDGET)
    kinds = [
        "private" if yard else ("service" if (a, b) in graph.service else "street")
        for yard, a, b in zip(in_yard, path_nodes, path_nodes[1:], strict=False)
    ]
    return _finish(
        target, graph, segments, path_nodes, coords, raw_edges, kinds, total, round(yard_miles, 2)
    )


def _yard_refusal(graph: RouteGraph, start_ref: int, end_ref: int) -> str:
    """Why the yard-road rule found nothing, for the run log only: is the
    endpoint cut off even with every private way open, or did the rule's own
    limits (one stretch at the facility end, no gate on a public way, no
    way signed against trucks) refuse the only way through?"""
    seen = {end_ref}
    stack = [end_ref]
    while stack:
        node = stack.pop()
        steps = [edge[0] for edge in graph.edges.get(node, ())]
        steps += [edge[0] for edge in graph.yard_edges.get(node, ())]
        for nxt in steps:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    if start_ref not in seen:
        return "cut off even over private ways (water, a motorway or a closed road between)"
    return "the only way through breaks the rule (private mid-route, a public gate, no trucks)"


def _resolve_speed(speed_miles: dict[float, float], road: str) -> float:
    """The segment's posted limit: the real OSM value covering the most miles
    (ties broken toward the higher limit, deterministically), or the honest
    default where no way on this run carries a ``maxspeed`` -- 25 for a named
    street, 15 for a road carrying no name of its own."""
    if speed_miles:
        mph, _ = max(speed_miles.items(), key=lambda kv: (kv[1], kv[0]))
        return float(mph)
    return 25.0 if is_named(road) else 15.0


def collapse_segments(
    edges: list[tuple[str, float, float | None]],
    coords: list[tuple[float, float]] | None = None,
    max_segments: int | None = MAX_SPOKEN_SEGMENTS,
) -> list[dict[str, Any]]:
    """Merge same-road edge runs into spoken segments.

    ``coords`` is the node coordinate per path point (one more than edges).
    With it, each road-name boundary gets a turn direction from the signed
    bearing change through the junction, so the cue reads "Turn right onto
    Palm Street" and the runtime's panned turn earcon fires; near-straight
    name changes read "Continue onto". Without coords the cues stay
    directionless ("Turn onto"), the pre-existing wording.

    Each edge carries its way's posted limit (or None); a merged run keeps the
    real limit covering the most of its miles and otherwise falls back to the
    named/unnamed default -- honest absence, never a guessed number.

    An unnamed junction link is not a street: its miles join the run it
    leaves (or, at the very start, the run it enters), so the turn is heard
    once, onto the road the link delivers the truck to.

    A path with more than ``MAX_SPOKEN_SEGMENTS`` streets keeps the LAST
    ones. Paths run from the city context to the target, so the far end is
    the facility's own streets. Until 2026-09-17 the cap kept the first eight
    streets out of the city centre instead and dropped the ones at the yard:
    measured on the 287 California, New York and Texas chains, 109 real paths
    were longer than eight streets and the kept part covered a median 68
    percent of the path (19 percent at worst), so the chain stopped short of
    the facility it claimed to reach and a departure began on a street the
    yard is not on. The kept part is relabelled to start on its first street,
    and ``miles`` is the kept part only, as before. ``max_segments`` None
    keeps every street (a chain from a ramp terminal is kept whole; how much
    of it is spoken is the speech layer's call).

    Each segment also carries private keys for ``street_chain.annotate``,
    which strips them: ``_first_edge``/``_end_edge`` (its edge span, junction
    links included), ``_raw_miles`` and ``_read_miles`` (unrounded miles, and
    the miles a ``maxspeed`` tag covers)."""
    segments: list[dict[str, Any]] = []
    lead_link_miles = 0.0
    for i, (road, miles, mph) in enumerate(edges):
        if road == JUNCTION_LINK:
            if segments:
                segments[-1]["miles"] += miles
                segments[-1]["end_edge"] = i + 1
            else:
                lead_link_miles += miles
            continue
        if segments and segments[-1]["road"] == road:
            segments[-1]["miles"] += miles
            segments[-1]["end_edge"] = i + 1
        else:
            segments.append(
                {
                    "road": road,
                    "miles": miles + lead_link_miles,
                    "start_edge": i,
                    "first_edge": 0 if lead_link_miles else i,
                    "end_edge": i + 1,
                    "speed_miles": defaultdict(float),
                }
            )
            lead_link_miles = 0.0
        if mph is not None:
            segments[-1]["speed_miles"][mph] += miles
    segments = _merge_same_street(segments, coords)
    out: list[dict[str, Any]] = []
    for i, segment in enumerate(segments):
        miles = round(max(segment["miles"], 0.05), 2)
        road = segment["road"]
        # 0.0 is "no corner here": the first segment has no junction onto it,
        # and a route with no coordinates never measured one.
        turn_deg = 0.0
        if i == 0:
            cue = f"Start on {road}."
        else:
            direction = ""
            if coords is not None:
                direction, turn_deg = turn_geometry(
                    coords,
                    boundary=segment["start_edge"],
                    prev_start=segments[i - 1]["start_edge"],
                    next_end=segment["end_edge"],
                )
            if direction:
                cue = f"Turn {direction} onto {road}."
            elif coords is not None:
                cue = f"Continue onto {road}."
            else:
                cue = f"Turn onto {road}."
        out.append(
            {
                "road": road,
                "miles": miles,
                "cue": cue,
                "speed_mph": _resolve_speed(segment["speed_miles"], road),
                "turn_deg": round(turn_deg, 1),
                "_first_edge": segment["first_edge"],
                "_end_edge": segment["end_edge"],
                "_raw_miles": segment["miles"],
                "_read_miles": sum(segment["speed_miles"].values()),
            }
        )
    if max_segments is not None and len(out) > max_segments:
        out = out[-max_segments:]
        out[0]["cue"] = f"Start on {out[0]['road']}."
        # The junction onto this segment was cut off with the segments before
        # it, so its angle goes too: 0.0 is "no corner here", and a Start leg
        # that kept one would hand it to the reversed route's last corner.
        out[0]["turn_deg"] = 0.0
    return out


def _street_name(road: str) -> str:
    """The label without its trailing route ref: "Gateway Drive (US 2)" and
    "Gateway Drive" are one street whose ways are tagged unevenly."""
    if road.endswith(")") and " (" in road:
        return road[: road.rindex(" (")]
    return road


def _merge_same_street(
    segments: list[dict[str, Any]],
    coords: list[tuple[float, float]] | None,
) -> list[dict[str, Any]]:
    """Join runs that are one street heard as several.

    Measured on the checked-in facility chains (2026-09-17): 271 of 1,713
    spoke one street two or more times in a row because OSM carries the route
    ref on some of its ways and not others -- one chain spent five of its
    eight streets on "Saint John Avenue" under five refs. Two rules, neither
    with a threshold:

    * neighbouring runs with the same street name are one run, labelled as
      the longer of the two;
    * a run with no name of its own between two runs of the same street, with
      no turn at either end, is a gap in that street's name tag, not a side
      street. With a turn at either end it is a real detour and is kept.
      Without ``coords`` there is no way to tell, so nothing is folded.
    """

    def join(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
        keep = first if first["miles"] >= second["miles"] else second
        speed_miles: defaultdict[float, float] = defaultdict(float)
        for part in (first, second):
            for mph, miles in part["speed_miles"].items():
                speed_miles[mph] += miles
        return {
            "road": keep["road"],
            "miles": first["miles"] + second["miles"],
            "start_edge": first["start_edge"],
            "first_edge": first["first_edge"],
            "end_edge": second["end_edge"],
            "speed_miles": speed_miles,
        }

    def same_street(a: dict[str, Any], b: dict[str, Any]) -> bool:
        return is_named(a["road"]) and _street_name(a["road"]) == _street_name(b["road"])

    def straight_into(i: int) -> bool:
        return (
            coords is not None
            and not turn_geometry(
                coords,
                boundary=segments[i]["start_edge"],
                prev_start=segments[i - 1]["start_edge"],
                next_end=segments[i]["end_edge"],
            )[0]
        )

    segments = list(segments)
    merged = True
    while merged:
        merged = False
        for i in range(1, len(segments)):
            if same_street(segments[i - 1], segments[i]):
                segments[i - 1 : i + 1] = [join(segments[i - 1], segments[i])]
                merged = True
                break
        if merged:
            continue
        for i in range(1, len(segments) - 1):
            if (
                not is_named(segments[i]["road"])
                and same_street(segments[i - 1], segments[i + 1])
                and straight_into(i)
                and straight_into(i + 1)
            ):
                gap = join(segments[i - 1], segments[i])
                gap["road"] = segments[i - 1]["road"]
                segments[i - 1 : i + 2] = [join(gap, segments[i + 1])]
                merged = True
                break
    return segments


# A junction only counts as a real turn once the heading swings this far;
# gentler bends read as "Continue onto" so the earcon does not claim a
# steering move the street does not make.
TURN_MIN_DEG = 28.0
# Bearings are read this far out from the junction on each side, so a
# node-dense curb radius or lane jog does not decide the whole maneuver.
TURN_LOOKOUT_MI = 0.04


def turn_geometry(
    coords: list[tuple[float, float]],
    *,
    boundary: int,
    prev_start: int,
    next_end: int,
) -> tuple[str, float]:
    """Signed heading change at a road-name boundary, as ``(direction,
    degrees)``: "left", "right", or "" for near-straight, and the ANGLE the
    truck turns through. ``boundary`` indexes the shared junction node; the
    incoming and outgoing bearings are sampled ``TURN_LOOKOUT_MI`` along each
    road, clamped to that road's own extent so a short next street cannot
    borrow the maneuver after it.

    The magnitude is READ: it is the heading change between two bearings taken
    from OSM way geometry, with no model in between. It used to be computed
    here and thrown away, so every corner in the game was priced at the same
    assumed clamp (owner directive 2026-08-21, docs/turn-geometry-brief.md).
    A near-straight boundary reports 0.0 -- there is no corner to price."""
    junction = coords[boundary]
    before = _point_along(coords, boundary, -1, stop=prev_start)
    after = _point_along(coords, boundary, +1, stop=next_end)
    if before == junction or after == junction:
        return "", 0.0
    inbound = _bearing_deg(*before, *junction)
    outbound = _bearing_deg(*junction, *after)
    delta = ((outbound - inbound + 180.0) % 360.0) - 180.0
    if delta >= TURN_MIN_DEG:
        return "right", abs(delta)
    if delta <= -TURN_MIN_DEG:
        return "left", abs(delta)
    return "", 0.0


def _point_along(
    coords: list[tuple[float, float]],
    start: int,
    step: int,
    *,
    stop: int,
) -> tuple[float, float]:
    """Coordinate about ``TURN_LOOKOUT_MI`` from ``coords[start]`` walking by
    ``step``, never past index ``stop``."""
    total = 0.0
    i = start
    while i != stop and total < TURN_LOOKOUT_MI:
        j = i + step
        if j < 0 or j >= len(coords):
            break
        total += haversine_mi(*coords[i], *coords[j])
        i = j
    return coords[i]


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from point 1 to point 2, degrees 0..360."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    x = math.sin(dlmb) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlmb)
    return math.degrees(math.atan2(x, y)) % 360.0


def geometry_record(target: Target, geometry: GeometryPath | None, extract: Path) -> dict[str, Any]:
    turn_level = geometry is not None
    reason = target.fallback_reason
    source_type = "osm_local_road_graph" if turn_level else "nearest_road_context"
    if not turn_level and not reason:
        if not extract.exists():
            reason = f"Missing local OSM extract: {extract}"
        elif not target.source_backed_city_service:
            reason = "Target is estimated or fallback, so turn-level local routing is not claimed."
        elif city_target_distance(target) > MAX_CITY_SERVICE_ROUTE_MI:
            reason = "Target is beyond the bounded local route graph distance for this pass."
        else:
            reason = "No connected public-road path was found between the city context and target."
    # Safety net for the 30-mile-errand bug: never bake an approach longer than
    # the bounded local-route distance as one 25 mph segment. The match cap in
    # build_city_services keeps sourced services within ~10 road-miles, so a
    # real city service (a terminal or dealer on the city's industrial edge)
    # keeps its honest distance; only an absurd residual beyond
    # MAX_CITY_SERVICE_ROUTE_MI is clamped to the synthesized errand default.
    fallback_miles = geometry.miles if geometry else target.approach_miles
    if (
        not turn_level
        and target.target_type == "city_service"
        and target.approach_miles > MAX_CITY_SERVICE_ROUTE_MI
    ):
        default_miles = CITY_SERVICE_APPROACH_MILES.get(target.role, 3.0)
        reason = (
            f"{reason} Approach clamped from {target.approach_miles:.1f} "
            f"(beyond the {MAX_CITY_SERVICE_ROUTE_MI:.0f}-mile local-route limit) "
            f"to {default_miles:.1f} synthesized errand miles."
        ).strip()
        fallback_miles = default_miles
    segments = (
        list(geometry.segments)
        if geometry
        else [
            {
                "road": target.approach_road or "local approach road",
                "miles": round(max(fallback_miles, 0.4), 2),
                "cue": f"Use {target.approach_road or 'the local approach road'} for the local approach.",
                "speed_mph": 25.0,
            }
        ]
    )
    return {
        "target_type": target.target_type,
        "city": target.city,
        "name": target.name,
        "role": target.role,
        "turn_level": turn_level,
        "source_type": source_type,
        "estimated": bool(target.estimated or not turn_level),
        "fallback": not turn_level,
        "fallback_reason": reason,
        "total_miles": round(geometry.miles if geometry else fallback_miles, 2),
        "segments": clean_segments(segments),
        "final_hint": (
            "Final driveway, yard, gate, or dock path is not source-backed yet."
            if not turn_level
            else "Route reaches the sourced service vicinity; final driveway is not source-backed."
        ),
        "source_note": target.source_note,
    }


def clean_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for segment in segments:
        road = clean_text(str(segment["road"])) or UNNAMED_STREET
        cue = clean_text(str(segment["cue"]))
        out.append(
            {
                "road": road,
                "miles": round(float(segment["miles"]), 2),
                "cue": cue,
                "speed_mph": float(segment.get("speed_mph", 25.0)),
                # READ off the OSM bearings by collapse_segments, or 0.0 where
                # nothing was measured. This rebuild used to list four keys
                # and the angle was not one of them, so it was computed and
                # thrown away one step before the file was written.
                "turn_deg": round(float(segment.get("turn_deg", 0.0)), 1),
            }
        )
    return out


def coverage_summary(geometries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, dict[str, int]] = {}
    for record in geometries.values():
        item = by_type.setdefault(
            record["target_type"],
            {
                "total": 0,
                "turn_level": 0,
                "fallback": 0,
                "estimated": 0,
            },
        )
        item["total"] += 1
        if record["turn_level"]:
            item["turn_level"] += 1
        if record["fallback"]:
            item["fallback"] += 1
        if record["estimated"]:
            item["estimated"] += 1
    # Corner-angle provenance. A corner whose angle was READ off OSM geometry
    # is priced from its own shape; one without is priced as a square corner,
    # which is an ASSUMPTION. The ratio is reported here and on stdout so a bake
    # that mostly assumed says so, per AGENTS.md.
    corners = 0
    measured = 0
    for record in geometries.values():
        for segment in record.get("segments", []):
            if not segment["cue"].lower().startswith("turn "):
                continue
            corners += 1
            if segment.get("turn_deg", 0.0) > 0.0:
                measured += 1
    return {
        "targets": len(geometries),
        "turn_level": sum(1 for record in geometries.values() if record["turn_level"]),
        "fallback": sum(1 for record in geometries.values() if record["fallback"]),
        "estimated": sum(1 for record in geometries.values() if record["estimated"]),
        "corners": corners,
        "corners_angle_read": measured,
        "corners_angle_assumed": corners - measured,
        "corners_angle_read_ratio": round(measured / corners, 4) if corners else 0.0,
        "by_type": by_type,
    }


def nearest_node(graph: RouteGraph, lat: float, lon: float) -> tuple[int, float] | None:
    best: tuple[int, float] | None = None
    for ref, (node_lat, node_lon) in graph.nodes.items():
        miles = haversine_mi(lat, lon, node_lat, node_lon)
        if best is None or miles < best[1]:
            best = (ref, miles)
    return best


def target_bounds(target: Target, extra_starts: Any = ()) -> tuple[float, float, float, float]:
    lat_pad = GRAPH_PAD_MI / 69.0
    lon_pad = GRAPH_PAD_MI / max(20.0, 69.0 * math.cos(math.radians(target.lat)))
    lats = [target.start_lat, target.lat, *(start["lat"] for start in extra_starts)]
    lons = [target.start_lon, target.lon, *(start["lon"] for start in extra_starts)]
    return (min(lats) - lat_pad, max(lats) + lat_pad, min(lons) - lon_pad, max(lons) + lon_pad)


def target_grid(
    targets: list[Target],
    boxes: dict[str, tuple[float, float, float, float]],
) -> dict[tuple[int, int], list[str]]:
    grid: dict[tuple[int, int], list[str]] = defaultdict(list)
    for target in targets:
        min_lat, max_lat, min_lon, max_lon = boxes[target.target_id]
        for row in range(math.floor(min_lat * 10), math.floor(max_lat * 10) + 1):
            for col in range(math.floor(min_lon * 10), math.floor(max_lon * 10) + 1):
                grid[(row, col)].append(target.target_id)
    return grid


def way_target_ids(
    grid: dict[tuple[int, int], list[str]],
    coords: list[tuple[int, float, float]],
) -> set[str]:
    out: set[str] = set()
    for _ref, lat, lon in coords:
        out.update(grid.get((math.floor(lat * 10), math.floor(lon * 10)), ()))
    return out


def bounds_for_points(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    return (
        min(point[0] for point in points),
        max(point[0] for point in points),
        min(point[1] for point in points),
        max(point[1] for point in points),
    )


def bounds_intersect(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    return not (a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2])


def city_target_distance(target: Target) -> float:
    return haversine_mi(target.start_lat, target.start_lon, target.lat, target.lon)


def road_label(tags: dict[str, str]) -> str:
    highway = tags.get("highway", "")
    if highway not in ROUTABLE_HIGHWAYS:
        return ""
    if tags.get("service", "").strip().lower() in UNROUTABLE_SERVICE:
        return ""
    # `private` ways come back in only as a facility's own yard road
    # (`yard_roads.py`); a base's roads (`military`) never do.
    if tags.get("access", "").strip().lower() in CLOSED_ACCESS:
        return ""
    if tags.get("motorroad") == "yes":
        return ""
    name = clean_text(tags.get("name", ""))
    if highway in LINK_CLASSES:
        # A link's `ref` is as often an exit number as a route number, so
        # only a real name is spoken; without one it is part of the junction.
        return name or JUNCTION_LINK
    ref = clean_text(tags.get("ref", ""))
    if name and ref and name.lower() != ref.lower():
        # "FM 3183 (FM 3183)" is one fact said twice.
        return f"{name} ({ref})"
    if name or ref:
        return name or ref
    return UNNAMED_SERVICE if highway in SERVICE_CLASSES else UNNAMED_STREET


def way_coords(way) -> list[tuple[int, float, float]]:
    coords: list[tuple[int, float, float]] = []
    for node in way.nodes:
        try:
            if node.location.valid():
                coords.append((int(node.ref), float(node.location.lat), float(node.location.lon)))
        except osmium.InvalidLocationError:
            continue
    return coords


def clean_text(value: str) -> str:
    text = " ".join(str(value).split()).strip()
    lowered = text.lower()
    if any(marker in lowered for marker in RAW_MARKERS):
        return ""
    return text


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


def slug(value: str) -> str:
    out = []
    pending_dash = False
    for char in value.lower():
        if char.isalnum():
            if pending_dash and out:
                out.append("-")
            out.append(char)
            pending_dash = False
        else:
            pending_dash = True
    return "".join(out).strip("-") or "item"


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=LOCAL_GEOMETRY_PATH)
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--state",
        action="append",
        metavar="SLUG",
        help="limit to one or more state slugs (e.g. south-dakota) -- for testing "
        "against a temp --output; a full --write to the real file needs every state",
    )
    args = parser.parse_args()

    only_states = set(args.state) if args.state else None
    payload = build_local_geometry(args.cache_dir, only_states=only_states)
    print(json.dumps(payload["coverage"], indent=2, sort_keys=True))
    coverage = payload["coverage"]
    corners = coverage.get("corners", 0)
    if corners:
        ratio = coverage["corners_angle_read_ratio"]
        print(
            f"corner angles: {coverage['corners_angle_read']} of {corners} READ "
            f"from OSM geometry ({ratio:.1%}); the rest are priced as square "
            f"corners, which is an ASSUMPTION."
        )
        if ratio < 0.5:
            print("WARNING: most corner angles in this bake are assumed, not read.")
    if args.write:
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
