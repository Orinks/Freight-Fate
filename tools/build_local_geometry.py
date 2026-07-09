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
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import osmium

from freight_fate.data.world import get_world

ROOT = Path(__file__).resolve().parents[1]
CITY_SERVICES_PATH = ROOT / "src" / "freight_fate" / "data" / "city_services.json"
LOCAL_APPROACHES_PATH = ROOT / "src" / "freight_fate" / "data" / "local_approaches.json"
LOCAL_GEOMETRY_PATH = ROOT / "src" / "freight_fate" / "data" / "local_geometry.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
ACCESSED_DATE = "2026-06-27"
EARTH_RADIUS_MI = 3958.7613
MAX_CITY_SERVICE_ROUTE_MI = 18.0
TARGET_SNAP_RADIUS_MI = 0.75
CITY_SNAP_RADIUS_MI = 1.25
GRAPH_PAD_MI = 1.5

ROUTABLE_HIGHWAYS = {
    "primary",
    "secondary",
    "tertiary",
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
    edges: dict[int, list[tuple[int, float, str]]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def add_edge(self, a: int, b: int, road: str, miles: float) -> None:
        self.edges[a].append((b, miles, road))
        self.edges[b].append((a, miles, road))


@dataclass(frozen=True, slots=True)
class GeometryPath:
    miles: float
    segments: tuple[dict[str, Any], ...]


def build_local_geometry(cache_dir: Path) -> dict[str, Any]:
    targets = collect_targets()
    by_state: dict[str, list[Target]] = defaultdict(list)
    for target in targets:
        by_state[target.state].append(target)

    geometries: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    routed: dict[str, GeometryPath] = {}
    for state, state_targets in sorted(by_state.items()):
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


def collect_targets() -> list[Target]:
    world = get_world()
    services = json.loads(CITY_SERVICES_PATH.read_text(encoding="utf-8"))["cities"]
    approaches = json.loads(LOCAL_APPROACHES_PATH.read_text(encoding="utf-8"))["approaches"]
    targets: list[Target] = []
    for city_name in world.city_names():
        city = world.city(city_name)
        for entry in services[city_name]:
            target_id = f"city_service:{slug(city_name)}:{entry['key']}"
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
            approach = approaches[target_id]
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
    return targets


def route_state_targets(osm_path: Path, targets: list[Target]) -> dict[str, GeometryPath]:
    graphs = {target.target_id: RouteGraph() for target in targets}
    boxes = {target.target_id: target_bounds(target) for target in targets}
    grid = target_grid(targets, boxes)
    entities = osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY
    processor = (
        osmium.FileProcessor(str(osm_path), entities=entities)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    for way in processor:
        if not hasattr(way, "nodes"):
            continue
        tags = {str(tag.k): str(tag.v) for tag in way.tags}
        road = road_label(tags)
        if not road:
            continue
        coords = way_coords(way)
        if len(coords) < 2:
            continue
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
                graph.nodes[ref] = (lat, lon)
                if prev is not None:
                    miles = haversine_mi(prev[1], prev[2], lat, lon)
                    if miles > 0:
                        graph.add_edge(prev[0], ref, road, miles)
                prev = (ref, lat, lon)
    routed: dict[str, GeometryPath] = {}
    for target in targets:
        path = shortest_geometry(target, graphs[target.target_id])
        if path is not None:
            routed[target.target_id] = path
    return routed


def shortest_geometry(target: Target, graph: RouteGraph) -> GeometryPath | None:
    if not graph.nodes:
        return None
    start = nearest_node(graph, target.start_lat, target.start_lon)
    end = nearest_node(graph, target.lat, target.lon)
    if start is None or end is None:
        return None
    start_ref, start_dist = start
    end_ref, end_dist = end
    if start_dist > CITY_SNAP_RADIUS_MI or end_dist > TARGET_SNAP_RADIUS_MI:
        return None
    dist: dict[int, float] = {start_ref: 0.0}
    prev: dict[int, tuple[int, str]] = {}
    heap: list[tuple[float, int]] = [(0.0, start_ref)]
    while heap:
        miles, node = heapq.heappop(heap)
        if node == end_ref:
            break
        if miles > dist.get(node, float("inf")):
            continue
        if miles > max(target.approach_miles * 1.8, 3.0):
            continue
        for nxt, edge_miles, road in graph.edges.get(node, ()):
            nd = miles + edge_miles
            if nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                prev[nxt] = (node, road)
                heapq.heappush(heap, (nd, nxt))
    if end_ref not in dist:
        return None
    node = end_ref
    path_nodes = [node]
    reversed_roads: list[str] = []
    while node != start_ref:
        prev_node, road = prev[node]
        reversed_roads.append(road)
        path_nodes.append(prev_node)
        node = prev_node
    path_nodes.reverse()
    roads = list(reversed(reversed_roads))  # one road label per edge
    coords = [graph.nodes[ref] for ref in path_nodes]
    raw_edges = [(roads[i], haversine_mi(*coords[i], *coords[i + 1])) for i in range(len(roads))]
    segments = collapse_segments(raw_edges, coords)
    if not segments:
        return None
    total = round(sum(segment["miles"] for segment in segments), 2)
    if total > max(target.approach_miles * 1.8, 3.0):
        return None
    return GeometryPath(total, tuple(segments))


def collapse_segments(
    edges: list[tuple[str, float]],
    coords: list[tuple[float, float]] | None = None,
) -> list[dict[str, Any]]:
    """Merge same-road edge runs into spoken segments.

    ``coords`` is the node coordinate per path point (one more than edges).
    With it, each road-name boundary gets a turn direction from the signed
    bearing change through the junction, so the cue reads "Turn right onto
    Palm Street" and the runtime's panned turn earcon fires; near-straight
    name changes read "Continue onto". Without coords the cues stay
    directionless ("Turn onto"), the pre-existing wording."""
    segments: list[dict[str, Any]] = []
    for i, (road, miles) in enumerate(edges):
        if segments and segments[-1]["road"] == road:
            segments[-1]["miles"] += miles
            segments[-1]["end_edge"] = i + 1
        else:
            segments.append({"road": road, "miles": miles, "start_edge": i, "end_edge": i + 1})
    out: list[dict[str, Any]] = []
    for i, segment in enumerate(segments):
        miles = round(max(segment["miles"], 0.05), 2)
        road = segment["road"]
        if i == 0:
            cue = f"Start on {road}."
        else:
            direction = ""
            if coords is not None:
                direction = turn_direction(
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
                "speed_mph": 25.0 if road != "unnamed public road" else 15.0,
            }
        )
    return out[:8]


# A junction only counts as a real turn once the heading swings this far;
# gentler bends read as "Continue onto" so the earcon does not claim a
# steering move the street does not make.
TURN_MIN_DEG = 28.0
# Bearings are read this far out from the junction on each side, so a
# node-dense curb radius or lane jog does not decide the whole maneuver.
TURN_LOOKOUT_MI = 0.04


def turn_direction(
    coords: list[tuple[float, float]],
    *,
    boundary: int,
    prev_start: int,
    next_end: int,
) -> str:
    """Signed heading change at a road-name boundary: "left", "right", or ""
    for near-straight. ``boundary`` indexes the shared junction node; the
    incoming and outgoing bearings are sampled ``TURN_LOOKOUT_MI`` along each
    road, clamped to that road's own extent so a short next street cannot
    borrow the maneuver after it."""
    junction = coords[boundary]
    before = _point_along(coords, boundary, -1, stop=prev_start)
    after = _point_along(coords, boundary, +1, stop=next_end)
    if before == junction or after == junction:
        return ""
    inbound = _bearing_deg(*before, *junction)
    outbound = _bearing_deg(*junction, *after)
    delta = ((outbound - inbound + 180.0) % 360.0) - 180.0
    if delta >= TURN_MIN_DEG:
        return "right"
    if delta <= -TURN_MIN_DEG:
        return "left"
    return ""


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
    segments = (
        list(geometry.segments)
        if geometry
        else [
            {
                "road": target.approach_road or "local approach road",
                "miles": round(max(target.approach_miles, 0.4), 2),
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
        "total_miles": round(geometry.miles if geometry else target.approach_miles, 2),
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
        road = clean_text(str(segment["road"])) or "unnamed public road"
        cue = clean_text(str(segment["cue"]))
        out.append(
            {
                "road": road,
                "miles": round(float(segment["miles"]), 2),
                "cue": cue,
                "speed_mph": float(segment.get("speed_mph", 25.0)),
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
    return {
        "targets": len(geometries),
        "turn_level": sum(1 for record in geometries.values() if record["turn_level"]),
        "fallback": sum(1 for record in geometries.values() if record["fallback"]),
        "estimated": sum(1 for record in geometries.values() if record["estimated"]),
        "by_type": by_type,
    }


def nearest_node(graph: RouteGraph, lat: float, lon: float) -> tuple[int, float] | None:
    best: tuple[int, float] | None = None
    for ref, (node_lat, node_lon) in graph.nodes.items():
        miles = haversine_mi(lat, lon, node_lat, node_lon)
        if best is None or miles < best[1]:
            best = (ref, miles)
    return best


def target_bounds(target: Target) -> tuple[float, float, float, float]:
    lat_pad = GRAPH_PAD_MI / 69.0
    lon_pad = GRAPH_PAD_MI / max(20.0, 69.0 * math.cos(math.radians(target.lat)))
    return (
        min(target.start_lat, target.lat) - lat_pad,
        max(target.start_lat, target.lat) + lat_pad,
        min(target.start_lon, target.lon) - lon_pad,
        max(target.start_lon, target.lon) + lon_pad,
    )


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
    if tags.get("access") in {"private", "no"}:
        return ""
    name = clean_text(tags.get("name", ""))
    ref = clean_text(tags.get("ref", ""))
    if name and ref:
        return f"{name} ({ref})"
    return name or ref or "unnamed public road"


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
    args = parser.parse_args()

    payload = build_local_geometry(args.cache_dir)
    print(json.dumps(payload["coverage"], indent=2, sort_keys=True))
    if args.write:
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
