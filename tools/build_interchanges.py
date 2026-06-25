"""Discover highway interchanges along each leg and curate them into world.json.

Development-time helper (never called at runtime). For every Interstate leg it:

1. Fetches densified OSRM geometry through the leg's checked-in ``route_points``
   so each exit can be snapped to an accurate ``at_mi``.
2. Reads a local OSM PBF extract when ``--pbf`` is passed, streaming only
   ``highway=motorway_junction`` nodes and ``highway=motorway_link`` ways with
   ``destination`` tags. Without ``--pbf`` it falls back to the slower Overpass
   crawl.
3. Collapses the two per-direction junction nodes for an exit into one record,
   snaps it, merges the ramp destinations, and enforces a minimum spacing so
   the spoken cues stay readable.
4. Writes an additive ``corridor.interchanges`` array, leaving every other
   field untouched. Runtime gameplay reads only the checked-in result.

Interchanges are an *additive* layer like curated POIs; they are not a dispatch
requirement, so a leg with no clean OSM exit data simply gets none.

Run from the repo root:
    uv run python tools/build_interchanges.py            # report only
    uv run python tools/build_interchanges.py --write     # update world.json
    uv run python tools/build_interchanges.py --only "New York->Philadelphia" --write
    uv run --group tooling python tools/build_interchanges.py --pbf us.osm.pbf --write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
CACHE_DIR = ROOT / ".route-cache" / "interchanges"
OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/{coords}"
USER_AGENT = "FreightFate interchange curation (https://github.com/Orinks/Freight-Fate)"
ACCESSED_DATE = "2026-06-23"
EARTH_RADIUS_MI = 3958.7613

SAMPLE_SPACING_MI = 10.0   # how often to drop an Overpass probe along the leg
PROBE_RADIUS_M = 9_000     # search radius per probe
RAMP_NEAR_M = 350.0        # a ramp this close to a junction belongs to it
LOCAL_CORRIDOR_M = 200.0   # local PBF features must snap this close to a leg
LOCAL_PBF_PREFILTER_PAD_M = PROBE_RADIUS_M
MIN_EXIT_SPACING_MI = 2.0  # collapse exits closer than this (keep the richer)
MAX_DESTINATIONS = 3       # cap control cities per exit for speech brevity
LOCAL_INDEX_CACHE_VERSION = 1
LOCAL_INDEX_PROGRESS_INTERVAL_SEC = 60.0


@dataclass(frozen=True, slots=True)
class LocalOsmFeature:
    lat: float
    lon: float
    tags: dict[str, str]


@dataclass(slots=True)
class LocalOsmIndex:
    junctions: list[LocalOsmFeature]
    ramps: list[LocalOsmFeature]


@dataclass(frozen=True, slots=True)
class _LocalRampWay:
    node_ids: tuple[int, ...]
    tags: dict[str, str]


LocalBounds = tuple[float, float, float, float]


@dataclass(slots=True)
class _LocalIndexProgress:
    label: str
    interval_sec: float = LOCAL_INDEX_PROGRESS_INTERVAL_SEC
    started: float = field(init=False)
    last: float = field(init=False)

    def __post_init__(self) -> None:
        self.started = time.monotonic()
        self.last = self.started

    def maybe(self, message: str) -> None:
        now = time.monotonic()
        if self.interval_sec <= 0 or now - self.last < self.interval_sec:
            return
        self.last = now
        elapsed = now - self.started
        print(f"    {self.label}: {message} after {elapsed / 60.0:.1f} min",
              flush=True)


# --- geometry ---------------------------------------------------------------

def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def _osrm_geometry(route_points: list[dict[str, Any]], rate_limit: float,
                   cached_only: bool = False
                   ) -> list[tuple[float, float, float]] | None:
    """Dense [(lat, lon, cumulative_mi), ...] following the leg's waypoints.

    With ``cached_only`` it never makes a live request, returning ``None`` on a
    cache miss so a batch can fall back to local interpolation instead of risking
    a hang on the public OSRM router."""
    if len(route_points) < 2:
        return None
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in route_points)
    params = urllib.parse.urlencode({
        "overview": "full", "geometries": "geojson",
        "alternatives": "false", "steps": "false",
    })
    url = OSRM_ROUTE_URL.format(coords=coords) + "?" + params
    payload = _cached_get(url, "osrm", rate_limit, cached_only=cached_only)
    if payload is None:
        return None
    try:
        geom = payload["routes"][0]["geometry"]["coordinates"]
    except (KeyError, IndexError):
        return None
    out: list[tuple[float, float, float]] = []
    cum = 0.0
    prev: tuple[float, float] | None = None
    for lon, lat in geom:
        if prev is not None:
            cum += _haversine_mi(prev[0], prev[1], lat, lon)
        out.append((lat, lon, cum))
        prev = (lat, lon)
    return out


def _snap_at_mi(lat: float, lon: float,
                geom: list[tuple[float, float, float]],
                leg_miles: float) -> tuple[float, float]:
    """Nearest geometry vertex -> (at_mi scaled into the leg's frame, dist_mi)."""
    best_d = float("inf")
    best_cum = 0.0
    for glat, glon, cum in geom:
        d = _haversine_mi(lat, lon, glat, glon)
        if d < best_d:
            best_d = d
            best_cum = cum
    total = geom[-1][2] or leg_miles
    at_mi = best_cum / total * leg_miles
    return at_mi, best_d


def _geometry_bounds(geom: list[tuple[float, float, float]],
                     pad_m: float) -> tuple[float, float, float, float]:
    min_lat = min(p[0] for p in geom)
    max_lat = max(p[0] for p in geom)
    min_lon = min(p[1] for p in geom)
    max_lon = max(p[1] for p in geom)
    mid_lat = (min_lat + max_lat) / 2.0
    lat_pad = pad_m / 111_320.0
    lon_scale = max(0.2, math.cos(math.radians(mid_lat)))
    lon_pad = pad_m / (111_320.0 * lon_scale)
    return min_lat - lat_pad, max_lat + lat_pad, min_lon - lon_pad, max_lon + lon_pad


def _inside_bounds(lat: float, lon: float,
                   bounds: LocalBounds) -> bool:
    min_lat, max_lat, min_lon, max_lon = bounds
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def _inside_any_bounds(lat: float, lon: float, bounds: list[LocalBounds]) -> bool:
    return any(_inside_bounds(lat, lon, item) for item in bounds)


def _segment_bounds(
    a: dict[str, Any], b: dict[str, Any], pad_m: float
) -> LocalBounds:
    min_lat = min(float(a["lat"]), float(b["lat"]))
    max_lat = max(float(a["lat"]), float(b["lat"]))
    min_lon = min(float(a["lon"]), float(b["lon"]))
    max_lon = max(float(a["lon"]), float(b["lon"]))
    mid_lat = (min_lat + max_lat) / 2.0
    lat_pad = pad_m / 111_320.0
    lon_scale = max(0.2, math.cos(math.radians(mid_lat)))
    lon_pad = pad_m / (111_320.0 * lon_scale)
    return min_lat - lat_pad, max_lat + lat_pad, min_lon - lon_pad, max_lon + lon_pad


def _route_corridor_bounds(
    route_points: list[dict[str, Any]], pad_m: float = LOCAL_PBF_PREFILTER_PAD_M
) -> list[LocalBounds]:
    if len(route_points) < 2:
        return []
    return [
        _segment_bounds(start, end, pad_m)
        for start, end in zip(route_points, route_points[1:], strict=False)
    ]


def _local_prefilter_bounds(legs: list[dict[str, Any]]) -> list[LocalBounds]:
    bounds: list[LocalBounds] = []
    for leg in legs:
        route_points = list(leg.get("corridor", {}).get("route_points", ()))
        bounds.extend(_route_corridor_bounds(route_points))
    return bounds


def _bounds_digest(bounds: list[LocalBounds]) -> str:
    payload = json.dumps(
        [[round(value, 7) for value in item] for item in bounds],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _pbf_metadata(pbf_path: Path) -> dict[str, Any]:
    resolved = pbf_path.resolve()
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _pbf_set_metadata(pbf_paths: list[Path]) -> list[dict[str, Any]]:
    return [_pbf_metadata(path) for path in pbf_paths]


def _default_local_index_cache(pbf_path: Path) -> Path:
    name = pbf_path.name
    for suffix in (".osm.pbf", ".pbf"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return pbf_path.with_name(f"{name}.interchanges.json")


def _feature_to_json(feature: LocalOsmFeature) -> dict[str, Any]:
    return {"lat": feature.lat, "lon": feature.lon, "tags": feature.tags}


def _feature_from_json(raw: dict[str, Any]) -> LocalOsmFeature:
    return LocalOsmFeature(
        lat=float(raw["lat"]),
        lon=float(raw["lon"]),
        tags={str(k): str(v) for k, v in raw.get("tags", {}).items()},
    )


def _write_local_index_cache(
    cache_path: Path,
    index: LocalOsmIndex,
    pbf_paths: list[Path],
    bounds: list[LocalBounds],
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": LOCAL_INDEX_CACHE_VERSION,
        "pbfs": _pbf_set_metadata(pbf_paths),
        "bounds_digest": _bounds_digest(bounds),
        "junctions": [_feature_to_json(feature) for feature in index.junctions],
        "ramps": [_feature_to_json(feature) for feature in index.ramps],
    }
    cache_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_local_index_cache(
    cache_path: Path,
    pbf_paths: list[Path] | None,
    bounds: list[LocalBounds],
) -> LocalOsmIndex | None:
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"    ignoring unreadable local index cache {cache_path}: {exc}",
              flush=True)
        return None
    if payload.get("version") != LOCAL_INDEX_CACHE_VERSION:
        return None
    if pbf_paths is not None and payload.get("pbfs") != _pbf_set_metadata(pbf_paths):
        return None
    if payload.get("bounds_digest") != _bounds_digest(bounds):
        return None
    return LocalOsmIndex(
        junctions=[_feature_from_json(item) for item in payload.get("junctions", [])],
        ramps=[_feature_from_json(item) for item in payload.get("ramps", [])],
    )


def load_or_build_local_index(
    pbf_paths: list[Path],
    bounds: list[LocalBounds],
    cache_path: Path,
    rebuild: bool = False,
) -> LocalOsmIndex:
    if not rebuild:
        cached = _read_local_index_cache(cache_path, pbf_paths, bounds)
        if cached is not None:
            print(
                f"Loaded local OSM interchange index cache: {cache_path} "
                f"({len(cached.junctions)} junctions, {len(cached.ramps)} ramps)",
                flush=True,
            )
            return cached
    index = build_local_index(pbf_paths, bounds)
    _write_local_index_cache(cache_path, index, pbf_paths, bounds)
    print(f"    wrote local OSM interchange index cache: {cache_path}", flush=True)
    return index


def load_local_index_cache_only(cache_path: Path, bounds: list[LocalBounds]) -> LocalOsmIndex:
    cached = _read_local_index_cache(cache_path, None, bounds)
    if cached is None:
        raise SystemExit(
            f"Local index cache is missing, stale, or incompatible: {cache_path}"
        )
    print(
        f"Loaded local OSM interchange index cache: {cache_path} "
        f"({len(cached.junctions)} junctions, {len(cached.ramps)} ramps)",
        flush=True,
    )
    return cached


# --- Overpass ---------------------------------------------------------------

def _shield_pattern(highway: str) -> str | None:
    """'I-95' -> regex 'I 95([^0-9]|$)'. Interstate shields only (clean OSM
    motorway_junction tagging); returns None for non-Interstate legs."""
    primary = highway.replace(",", "/").split("/")[0].strip()
    m = re.match(r"^I-(\d+)$", primary)
    if not m:
        return None
    return f"I {m.group(1)}([^0-9]|$)"


def _sample_points(geom: list[tuple[float, float, float]]
                   ) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    next_at = 0.0
    total = geom[-1][2]
    for lat, lon, cum in geom:
        if cum >= next_at:
            points.append((lat, lon))
            next_at += SAMPLE_SPACING_MI
    if total - (next_at - SAMPLE_SPACING_MI) > 1.0:  # always probe the tail
        points.append((geom[-1][0], geom[-1][1]))
    return points


def _overpass_query(shield_rx: str, lat: float, lon: float) -> str:
    r = PROBE_RADIUS_M
    return (
        f"[out:json][timeout:60];"
        f'way["highway"="motorway"]["ref"~"{shield_rx}"]'
        f"(around:{r},{lat},{lon})->.m;"
        f'node(w.m)["highway"="motorway_junction"]'
        f"(around:{r},{lat},{lon})->.jx;"
        f".jx out body;"
        f'way(around.jx:{int(RAMP_NEAR_M)})["highway"="motorway_link"]'
        f'["destination"]->.r;'
        f".r out tags center;"
    )


def _post_overpass(query: str, rate_limit: float) -> dict[str, Any] | None:
    return _cached_post(query, rate_limit)


# --- local OSM extracts -----------------------------------------------------

def _dedupe_features(features: list[LocalOsmFeature]) -> list[LocalOsmFeature]:
    seen: set[tuple[float, float, tuple[tuple[str, str], ...]]] = set()
    out: list[LocalOsmFeature] = []
    for feature in features:
        key = (
            round(feature.lat, 6),
            round(feature.lon, 6),
            tuple(sorted(feature.tags.items())),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(feature)
    return out


def build_local_index(
    pbf_paths: Path | list[Path],
    bounds: list[LocalBounds],
    progress_interval_sec: float = LOCAL_INDEX_PROGRESS_INTERVAL_SEC,
) -> LocalOsmIndex:
    paths = [pbf_paths] if isinstance(pbf_paths, Path) else list(pbf_paths)
    junctions: list[LocalOsmFeature] = []
    ramps: list[LocalOsmFeature] = []
    for i, pbf_path in enumerate(paths, 1):
        part = _build_local_index_from_pbf(
            pbf_path,
            bounds,
            progress_interval_sec,
            label=f"{i}/{len(paths)}",
        )
        junctions.extend(part.junctions)
        ramps.extend(part.ramps)
    return LocalOsmIndex(
        junctions=_dedupe_features(junctions),
        ramps=_dedupe_features(ramps),
    )


def _build_local_index_from_pbf(
    pbf_path: Path,
    bounds: list[LocalBounds],
    progress_interval_sec: float = LOCAL_INDEX_PROGRESS_INTERVAL_SEC,
    label: str = "1/1",
) -> LocalOsmIndex:
    try:
        import osmium  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Reading --pbf requires the tooling dependency group: "
            "uv sync --group dev --group tooling"
        ) from exc

    tag_filters = [
        osmium.filter.TagFilter(  # type: ignore[attr-defined]
            ("highway", "motorway_junction"),
            ("highway", "motorway_link"),
        )
    ]
    pass1 = _LocalIndexProgress(f"PBF {label} pass 1", progress_interval_sec)

    class InterchangeHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
        def __init__(self) -> None:
            super().__init__()
            self.junctions: list[LocalOsmFeature] = []
            self.ramp_ways: list[_LocalRampWay] = []
            self.ramp_node_ids: set[int] = set()
            self.nodes_seen = 0
            self.ways_seen = 0

        def node(self, node: Any) -> None:
            self.nodes_seen += 1
            pass1.maybe(
                f"{self.nodes_seen:,} nodes, {self.ways_seen:,} ways; "
                f"retained {len(self.junctions):,} junctions and "
                f"{len(self.ramp_ways):,} ramp ways"
            )
            tags = {str(k): str(v) for k, v in node.tags}
            if tags.get("highway") != "motorway_junction":
                return
            if not node.location.valid():
                return
            lat = float(node.location.lat)
            lon = float(node.location.lon)
            if not _inside_any_bounds(lat, lon, bounds):
                return
            self.junctions.append(LocalOsmFeature(
                lat=lat,
                lon=lon,
                tags=tags,
            ))

        def way(self, way: Any) -> None:
            self.ways_seen += 1
            pass1.maybe(
                f"{self.nodes_seen:,} nodes, {self.ways_seen:,} ways; "
                f"retained {len(self.junctions):,} junctions and "
                f"{len(self.ramp_ways):,} ramp ways"
            )
            tags = {str(k): str(v) for k, v in way.tags}
            if tags.get("highway") != "motorway_link" or not tags.get("destination"):
                return
            node_ids: list[int] = []
            for node_ref in way.nodes:
                node_id = getattr(node_ref, "ref", None)
                if node_id is not None:
                    node_ids.append(int(node_id))
            if not node_ids:
                return
            self.ramp_ways.append(_LocalRampWay(
                node_ids=tuple(node_ids),
                tags={
                    "highway": "motorway_link",
                    "destination": str(tags.get("destination", "")),
                    "destination:ref": str(tags.get("destination:ref", "")),
                },
            ))
            self.ramp_node_ids.update(node_ids)

    pass2 = _LocalIndexProgress(f"PBF {label} pass 2", progress_interval_sec)

    class RampNodeHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
        def __init__(self, wanted: set[int]) -> None:
            super().__init__()
            self.wanted = wanted
            self.coords: dict[int, tuple[float, float]] = {}
            self.nodes_seen = 0

        def node(self, node: Any) -> None:
            self.nodes_seen += 1
            pass2.maybe(
                f"{self.nodes_seen:,} nodes; resolved "
                f"{len(self.coords):,}/{len(self.wanted):,} ramp node locations"
            )
            node_id = int(node.id)
            if node_id not in self.wanted:
                return
            if not node.location.valid():
                return
            self.coords[node_id] = (
                float(node.location.lat),
                float(node.location.lon),
            )

    handler = InterchangeHandler()
    try:
        print(
            f"    building local index from PBF {label} pass 1: {pbf_path}",
            flush=True,
        )
        handler.apply_file(str(pbf_path), filters=tag_filters)
    except RuntimeError as exc:
        raise SystemExit(f"Could not read OSM PBF {pbf_path}: {exc}") from exc

    ramps: list[LocalOsmFeature] = []
    if handler.ramp_node_ids:
        ramp_nodes = RampNodeHandler(handler.ramp_node_ids)
        id_filters = [osmium.filter.IdFilter(handler.ramp_node_ids)]  # type: ignore[attr-defined]
        try:
            print(
                f"    resolving {len(handler.ramp_node_ids):,} ramp node locations "
                f"from PBF {label} pass 2",
                flush=True,
            )
            ramp_nodes.apply_file(str(pbf_path), filters=id_filters)
        except RuntimeError as exc:
            raise SystemExit(f"Could not read OSM PBF {pbf_path}: {exc}") from exc
        for ramp in handler.ramp_ways:
            coords = [
                ramp_nodes.coords[node_id]
                for node_id in ramp.node_ids
                if node_id in ramp_nodes.coords
            ]
            if not coords:
                continue
            lat = sum(p[0] for p in coords) / len(coords)
            lon = sum(p[1] for p in coords) / len(coords)
            if _inside_any_bounds(lat, lon, bounds):
                ramps.append(LocalOsmFeature(lat=lat, lon=lon, tags=ramp.tags))

    print(
        f"    retained {len(handler.junctions):,} route-bbox junctions and "
        f"{len(ramps):,} route-bbox destination ramps from local extract",
        flush=True,
    )
    return LocalOsmIndex(junctions=handler.junctions, ramps=ramps)


def _local_candidates(index: LocalOsmIndex,
                      geom: list[tuple[float, float, float]],
                      leg_miles: float) -> tuple[dict[int, dict[str, Any]],
                                                  list[dict[str, Any]]]:
    bounds = _geometry_bounds(geom, max(PROBE_RADIUS_M, 2_000.0))
    junctions: dict[int, dict[str, Any]] = {}
    ramps: list[dict[str, Any]] = []
    for i, feature in enumerate(index.junctions):
        if not _inside_bounds(feature.lat, feature.lon, bounds):
            continue
        at_mi, dist = _snap_at_mi(feature.lat, feature.lon, geom, leg_miles)
        if dist * 1609.34 > LOCAL_CORRIDOR_M:
            continue
        junctions[i] = {
            "lat": feature.lat,
            "lon": feature.lon,
            "ref": str(feature.tags.get("ref", "")).strip(),
            "name": _clean_place(feature.tags.get("name", "")),
        }
    for feature in index.ramps:
        if not _inside_bounds(feature.lat, feature.lon, bounds):
            continue
        _, dist = _snap_at_mi(feature.lat, feature.lon, geom, leg_miles)
        if dist * 1609.34 > max(RAMP_NEAR_M, LOCAL_CORRIDOR_M):
            continue
        ramps.append({
            "lat": feature.lat,
            "lon": feature.lon,
            "destinations": _split_destinations(feature.tags.get("destination", "")),
            "via": str(feature.tags.get("destination:ref", "")).strip(),
        })
    return junctions, ramps


# --- caching ----------------------------------------------------------------

def _cache_file(tag: str, key: str) -> Path:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{tag}-{digest}.json"


def _cached_get(url: str, tag: str, rate_limit: float,
                cached_only: bool = False) -> dict[str, Any] | None:
    cf = _cache_file(tag, url)
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    if cached_only:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (TimeoutError, OSError, urllib.error.URLError) as exc:
        print(f"    OSRM error: {type(exc).__name__}: {exc}")
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps(payload), encoding="utf-8")
    if rate_limit > 0:
        time.sleep(rate_limit)
    return payload


def _cached_post(query: str, rate_limit: float) -> dict[str, Any] | None:
    cf = _cache_file("overpass", query)
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    # Public Overpass throttles bulk use (429) and sheds load (504). Sweep the
    # mirrors a few times with exponential backoff so a long crawl rides out a
    # rate-limit window instead of dropping the leg. Cache makes a re-run free.
    for attempt in range(4):
        for url in OVERPASS_MIRRORS:
            req = urllib.request.Request(
                url, data=body,
                headers={"User-Agent": USER_AGENT,
                         "Content-Type": "application/x-www-form-urlencoded"})
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except (TimeoutError, OSError, urllib.error.URLError) as exc:
                code = getattr(exc, "code", "")
                print(f"    Overpass {url.split('/')[2]} -> {type(exc).__name__} "
                      f"{code}; trying next mirror")
                continue
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cf.write_text(json.dumps(payload), encoding="utf-8")
            if rate_limit > 0:
                time.sleep(rate_limit)
            return payload
        backoff = 15.0 * (attempt + 1)
        print(f"    all mirrors busy; backing off {backoff:.0f}s "
              f"(attempt {attempt + 1}/4)")
        time.sleep(backoff)
    return None


# --- discovery --------------------------------------------------------------

RAW_MARKERS = ("node/", "way/", "relation/", "amenity=", "highway=")
# Lane-control / vehicle-class words that ride in OSM destination tags. A
# destination made up *only* of these (e.g. "Cars Only", "Trucks - Buses",
# "Buses And Cars Only") is lane signage, not a place to head "toward".
VEHICLE_CONTROL_WORDS = {
    "cars", "car", "trucks", "truck", "buses", "bus", "vehicles", "only",
    "no", "hov", "express", "local", "left", "right", "lane", "lanes",
    "exit", "toll", "ezpass",
}
_CONNECTOR_WORDS = {"and"}


def _clean_place(value: str) -> str:
    text = " ".join(str(value).replace("\n", " ").split()).strip()
    lowered = text.lower()
    if not text or any(marker in lowered for marker in RAW_MARKERS):
        return ""
    words = [w for w in re.findall(r"[a-z]+", lowered) if w not in _CONNECTOR_WORDS]
    if words and all(w in VEHICLE_CONTROL_WORDS for w in words):
        return ""
    return text


def _split_destinations(raw: str) -> list[str]:
    out: list[str] = []
    for piece in str(raw).split(";"):
        place = _clean_place(piece)
        if place and place not in out:
            out.append(place)
    return out


def discover_leg(leg: dict[str, Any], rate_limit: float,
                 local_index: LocalOsmIndex | None = None) -> list[dict[str, Any]]:
    highway = str(leg.get("highway", ""))
    shield_rx = _shield_pattern(highway)
    if shield_rx is None:
        return []
    route_points = list(leg.get("corridor", {}).get("route_points", ()))
    geom = _osrm_geometry(route_points, rate_limit)
    if not geom:
        return []
    leg_miles = float(leg["miles"])

    if local_index is not None:
        junctions, ramps = _local_candidates(local_index, geom, leg_miles)
        return _assemble(junctions, ramps, geom, leg_miles, highway)

    junctions: dict[int, dict[str, Any]] = {}     # node id -> {lat, lon, ref, name}
    ramps: list[dict[str, Any]] = []              # {lat, lon, destination, via}
    for lat, lon in _sample_points(geom):
        payload = _post_overpass(_overpass_query(shield_rx, lat, lon), rate_limit)
        if payload is None:
            continue
        for el in payload.get("elements", []):
            tags = el.get("tags", {})
            if el.get("type") == "node" and tags.get("highway") == "motorway_junction":
                junctions[el["id"]] = {
                    "lat": el["lat"], "lon": el["lon"],
                    "ref": str(tags.get("ref", "")).strip(),
                    "name": _clean_place(tags.get("name", "")),
                }
            elif el.get("type") == "way" and tags.get("highway") == "motorway_link":
                center = el.get("center") or {}
                if "lat" not in center:
                    continue
                ramps.append({
                    "lat": center["lat"], "lon": center["lon"],
                    "destinations": _split_destinations(tags.get("destination", "")),
                    "via": str(tags.get("destination:ref", "")).strip(),
                })

    return _assemble(junctions, ramps, geom, leg_miles, highway)


def _assemble(junctions: dict[int, dict[str, Any]], ramps: list[dict[str, Any]],
              geom: list[tuple[float, float, float]], leg_miles: float,
              highway: str) -> list[dict[str, Any]]:
    # Collapse the two per-carriageway junction nodes that share an exit ref
    # into one logical exit; ref-less nodes are grouped by their snapped mile.
    by_key: dict[str, list[dict[str, Any]]] = {}
    for node in junctions.values():
        at_mi, dist = _snap_at_mi(node["lat"], node["lon"], geom, leg_miles)
        if dist > 1.5 or not (1.0 < at_mi < leg_miles - 1.0):
            continue  # off-corridor match or too close to an endpoint
        node["at_mi"] = at_mi
        key = f"ref:{node['ref']}" if node["ref"] else f"mi:{round(at_mi / 0.5)}"
        by_key.setdefault(key, []).append(node)

    exits: list[dict[str, Any]] = []
    for group in by_key.values():
        at_mi = sum(n["at_mi"] for n in group) / len(group)
        # Collapse stray internal spaces in OSM exit refs ("103 B" -> "103B").
        ref = re.sub(r"\s+", "", next((n["ref"] for n in group if n["ref"]), ""))
        name = next((n["name"] for n in group if n["name"]), "")
        # Gather destinations from ramps near any node in this group.
        dests: list[str] = []
        via = ""
        for node in group:
            for ramp in ramps:
                if _haversine_mi(node["lat"], node["lon"],
                                 ramp["lat"], ramp["lon"]) * 1609.34 > RAMP_NEAR_M:
                    continue
                for d in ramp["destinations"]:
                    if d not in dests:
                        dests.append(d)
                if not via and ramp["via"]:
                    via = ramp["via"]
        if not (ref or dests or name):
            continue
        exits.append({
            "at_mi": round(at_mi, 1),
            "exit_ref": ref,
            "name": name,
            "destinations": dests[:MAX_DESTINATIONS],
            "via": via,
            "highway": highway,
            "source": (
                "OpenStreetMap highway=motorway_junction exit ref and "
                "destination sign tags on the leg's Interstate shield, snapped "
                f"to checked-in OSRM route geometry, accessed {ACCESSED_DATE}: "
                "https://www.openstreetmap.org/"
            ),
        })

    return _space_out(exits)


def _richness(ex: dict[str, Any]) -> int:
    return (1 if ex["exit_ref"] else 0) + len(ex["destinations"])


def _space_out(exits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedily keep the richest exits, dropping any within MIN_EXIT_SPACING_MI
    of one already kept, so the spoken cues do not crowd each other."""
    kept: list[dict[str, Any]] = []
    for ex in sorted(exits, key=lambda e: (-_richness(e), e["at_mi"])):
        if all(abs(ex["at_mi"] - k["at_mi"]) >= MIN_EXIT_SPACING_MI for k in kept):
            kept.append(ex)
    kept.sort(key=lambda e: e["at_mi"])
    return kept


# --- maxspeed ---------------------------------------------------------------
#
# Bakes real OSM `maxspeed` onto each leg as a `corridor.speed_limits` step
# profile (mph), which the runtime prefers over the highway/region heuristic.
# Reuses this module's local-PBF reader and corridor snapping; the per-state
# extracts under ~/.cache/freight-fate-osm/regions are selected automatically
# from the states each leg touches, so the slow 12GB national file is not needed.

MAXSPEED_HIGHWAY_CLASSES = ("motorway", "trunk", "primary", "secondary")
MAXSPEED_CORRIDOR_M = 250.0       # a maxspeed way must snap this close to a leg
MAXSPEED_SAMPLE_STRIDE_MI = 5.0   # profile resolution along the leg
# The maxspeed index spans every route in the country, so snapping all of it to
# each leg is quadratic. A coarse lat/lon grid buckets way points (~5.5km cells)
# so a leg only snaps ways in the cells its geometry passes through. Way points
# are thinned to ~100m spacing first (well under the 250m snap corridor) to keep
# the grid small without losing coverage.
_MAXSPEED_GRID_DEG = 0.05
_MAXSPEED_THIN_DEG = 0.001
# A grid point: lat, lon, mph, hgv, and the way's route-number digits (so the
# per-leg shield match can be computed against whichever leg is being baked).
MaxspeedPoint = tuple[float, float, float, bool, str]
MaxspeedGrid = dict[tuple[int, int], list[MaxspeedPoint]]
MAXSPEED_INDEX_CACHE_VERSION = 1
OSM_REGION_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
MAXSPEED_SOURCE = (
    "OpenStreetMap maxspeed tags on the corridor highway ways, read from a local "
    f"Geofabrik extract and snapped to checked-in OSRM route geometry, accessed "
    f"{ACCESSED_DATE}; maxspeed:hgv preferred where tagged. "
    "https://www.openstreetmap.org/"
)


@dataclass(frozen=True, slots=True)
class LocalMaxspeedWay:
    coords: tuple[tuple[float, float], ...]
    mph: float
    hgv: bool
    ref: str


@dataclass(frozen=True, slots=True)
class _MaxspeedWayRaw:
    node_ids: tuple[int, ...]
    mph: float
    hgv: bool
    ref: str


_PARSE_OSM_MAXSPEED = None


def _parse_osm_maxspeed(raw: Any) -> float | None:
    """The canonical maxspeed normalizer, borrowed from enrich_routes.py."""
    global _PARSE_OSM_MAXSPEED
    if _PARSE_OSM_MAXSPEED is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "enrich_routes", Path(__file__).with_name("enrich_routes.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _PARSE_OSM_MAXSPEED = module.parse_osm_maxspeed
    return _PARSE_OSM_MAXSPEED(raw)


def _route_digits(highway: str) -> str:
    """Route number from a shield/ref, e.g. ``I-95`` or ``I 95`` -> ``95``."""
    digits = re.findall(r"\d+", str(highway))
    return digits[0] if digits else ""


def _state_slug(state: str) -> str:
    """Geofabrik region slug for a US state name, e.g. ``District of Columbia``
    -> ``district-of-columbia``."""
    return "-".join(str(state).strip().lower().split())


def _leg_states(data: dict[str, Any], leg: dict[str, Any]) -> set[str]:
    """Every state a leg touches: its per-state mileage plus both endpoints."""
    states: set[str] = set()
    for entry in leg.get("corridor", {}).get("state_miles", ()):
        state = str(entry.get("state", "")).strip()
        if state:
            states.add(state)
    for end in ("from", "to"):
        city = data["cities"].get(leg[end], {})
        state = str(city.get("state", "")).strip()
        if state:
            states.add(state)
    return states


def _pbf_for_states(states: set[str], region_dir: Path) -> list[Path]:
    """Existing per-state PBF extracts for the given states, plus a note of any
    that are missing from the cache."""
    found: list[Path] = []
    missing: list[str] = []
    for state in sorted(states):
        path = region_dir / f"{_state_slug(state)}-latest.osm.pbf"
        if path.exists():
            found.append(path)
        else:
            missing.append(state)
    if missing:
        print(f"    no local extract for: {', '.join(missing)} "
              f"(looked in {region_dir}); those stretches keep the heuristic",
              flush=True)
    return found


def _build_maxspeed_index_from_pbf(
    pbf_path: Path,
    bounds: list[LocalBounds],
    label: str = "1/1",
) -> list[LocalMaxspeedWay]:
    """Mainline highway ways carrying a usable ``maxspeed`` near the routes.

    Two passes (matching the interchange reader so no giant location index is
    needed): pass 1 keeps ways whose ``highway`` is a mainline class and whose
    ``maxspeed``/``maxspeed:hgv`` parses to mph; pass 2 resolves the coordinates
    of those ways' nodes that fall inside the route corridor bounds."""
    try:
        import osmium  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Reading --pbf requires the tooling dependency group: "
            "uv sync --group dev --group tooling"
        ) from exc

    tag_filters = [
        osmium.filter.TagFilter(  # type: ignore[attr-defined]
            *(("highway", value) for value in MAXSPEED_HIGHWAY_CLASSES)
        )
    ]
    pass1 = _LocalIndexProgress(f"PBF {label} maxspeed pass 1",
                                LOCAL_INDEX_PROGRESS_INTERVAL_SEC)

    class MaxspeedWayHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
        def __init__(self) -> None:
            super().__init__()
            self.ways: list[_MaxspeedWayRaw] = []
            self.wanted: set[int] = set()
            self.ways_seen = 0

        def way(self, way: Any) -> None:
            self.ways_seen += 1
            pass1.maybe(
                f"{self.ways_seen:,} ways; retained {len(self.ways):,} "
                f"maxspeed ways"
            )
            tags = {str(k): str(v) for k, v in way.tags}
            if tags.get("highway") not in MAXSPEED_HIGHWAY_CLASSES:
                return
            hgv_mph = _parse_osm_maxspeed(tags.get("maxspeed:hgv"))
            mph = hgv_mph if hgv_mph is not None else _parse_osm_maxspeed(
                tags.get("maxspeed"))
            if mph is None:
                return
            node_ids = [int(ref.ref) for ref in way.nodes
                        if getattr(ref, "ref", None) is not None]
            if len(node_ids) < 1:
                return
            self.ways.append(_MaxspeedWayRaw(
                node_ids=tuple(node_ids),
                mph=mph,
                hgv=hgv_mph is not None,
                ref=str(tags.get("ref", "")).strip(),
            ))
            self.wanted.update(node_ids)

    handler = MaxspeedWayHandler()
    try:
        print(f"    building maxspeed index from PBF {label} pass 1: {pbf_path}",
              flush=True)
        handler.apply_file(str(pbf_path), filters=tag_filters)
    except RuntimeError as exc:
        raise SystemExit(f"Could not read OSM PBF {pbf_path}: {exc}") from exc

    if not handler.wanted:
        return []

    pass2 = _LocalIndexProgress(f"PBF {label} maxspeed pass 2",
                                LOCAL_INDEX_PROGRESS_INTERVAL_SEC)

    class MaxspeedNodeHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
        def __init__(self, wanted: set[int]) -> None:
            super().__init__()
            self.wanted = wanted
            self.coords: dict[int, tuple[float, float]] = {}
            self.nodes_seen = 0

        def node(self, node: Any) -> None:
            self.nodes_seen += 1
            pass2.maybe(
                f"{self.nodes_seen:,} nodes; resolved "
                f"{len(self.coords):,}/{len(self.wanted):,} way node locations"
            )
            node_id = int(node.id)
            if node_id not in self.wanted or not node.location.valid():
                return
            lat = float(node.location.lat)
            lon = float(node.location.lon)
            if _inside_any_bounds(lat, lon, bounds):
                self.coords[node_id] = (lat, lon)

    node_handler = MaxspeedNodeHandler(handler.wanted)
    id_filters = [osmium.filter.IdFilter(handler.wanted)]  # type: ignore[attr-defined]
    try:
        print(f"    resolving {len(handler.wanted):,} maxspeed-way node locations "
              f"from PBF {label} pass 2", flush=True)
        node_handler.apply_file(str(pbf_path), filters=id_filters)
    except RuntimeError as exc:
        raise SystemExit(f"Could not read OSM PBF {pbf_path}: {exc}") from exc

    ways: list[LocalMaxspeedWay] = []
    for raw in handler.ways:
        coords = tuple(node_handler.coords[node_id] for node_id in raw.node_ids
                       if node_id in node_handler.coords)
        if coords:
            ways.append(LocalMaxspeedWay(
                coords=coords, mph=raw.mph, hgv=raw.hgv, ref=raw.ref))
    print(f"    retained {len(ways):,} route-corridor maxspeed ways from {label}",
          flush=True)
    return ways


def _maxspeed_index_cache_path(pbf_paths: list[Path]) -> Path:
    if len(pbf_paths) == 1:
        name = pbf_paths[0].name
        for suffix in (".osm.pbf", ".pbf"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        return pbf_paths[0].with_name(f"{name}.maxspeed.json")
    return pbf_paths[0].with_name("freight-fate-maxspeed.json")


def _maxspeed_way_to_json(way: LocalMaxspeedWay) -> dict[str, Any]:
    return {"coords": [list(c) for c in way.coords],
            "mph": way.mph, "hgv": way.hgv, "ref": way.ref}


def _maxspeed_way_from_json(raw: dict[str, Any]) -> LocalMaxspeedWay:
    return LocalMaxspeedWay(
        coords=tuple((float(c[0]), float(c[1])) for c in raw.get("coords", ())),
        mph=float(raw["mph"]), hgv=bool(raw.get("hgv", False)),
        ref=str(raw.get("ref", "")))


def load_or_build_maxspeed_index(
    pbf_paths: list[Path],
    bounds: list[LocalBounds],
    cache_path: Path,
    rebuild: bool = False,
) -> list[LocalMaxspeedWay]:
    if not rebuild and cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if (payload is not None
                and payload.get("version") == MAXSPEED_INDEX_CACHE_VERSION
                and payload.get("pbfs") == _pbf_set_metadata(pbf_paths)
                and payload.get("bounds_digest") == _bounds_digest(bounds)):
            ways = [_maxspeed_way_from_json(w) for w in payload.get("ways", ())]
            print(f"Loaded local OSM maxspeed index cache: {cache_path} "
                  f"({len(ways)} ways)", flush=True)
            return ways
    ways: list[LocalMaxspeedWay] = []
    for i, pbf_path in enumerate(pbf_paths, start=1):
        ways.extend(_build_maxspeed_index_from_pbf(
            pbf_path, bounds, label=f"{i}/{len(pbf_paths)}"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({
        "version": MAXSPEED_INDEX_CACHE_VERSION,
        "pbfs": _pbf_set_metadata(pbf_paths),
        "bounds_digest": _bounds_digest(bounds),
        "ways": [_maxspeed_way_to_json(w) for w in ways],
    }, indent=2) + "\n", encoding="utf-8")
    return ways


def _maxspeed_cell(lat: float, lon: float) -> tuple[int, int]:
    return (int(math.floor(lat / _MAXSPEED_GRID_DEG)),
            int(math.floor(lon / _MAXSPEED_GRID_DEG)))


def build_maxspeed_grid(ways: list[LocalMaxspeedWay]) -> MaxspeedGrid:
    """Bucket way points into a coarse lat/lon grid for fast per-leg lookup.

    Each way's vertices are thinned to ~100m spacing (the snap corridor is 250m,
    so this loses no coverage) and stored with the way's mph, hgv flag, and
    route-number digits, keyed by grid cell."""
    grid: MaxspeedGrid = {}
    for way in ways:
        ref_digits = _route_digits(way.ref)
        last: tuple[int, int] | None = None
        for lat, lon in way.coords:
            thin = (round(lat / _MAXSPEED_THIN_DEG), round(lon / _MAXSPEED_THIN_DEG))
            if thin == last:
                continue
            last = thin
            grid.setdefault(_maxspeed_cell(lat, lon), []).append(
                (lat, lon, way.mph, way.hgv, ref_digits))
    return grid


def assemble_maxspeed(
    grid: MaxspeedGrid,
    geom: list[tuple[float, float, float]],
    leg_miles: float,
    highway: str,
) -> list[dict[str, Any]]:
    """Build a step-function speed profile for a leg from snapped maxspeed ways.

    Gathers only the grid points in the cells the leg's geometry passes through,
    snaps them, keeps the on-corridor ones, resamples the limit at a fixed stride
    (preferring the leg's own shield and truck-specific limits), and collapses
    runs of the same value."""
    shield = _route_digits(highway)
    total = geom[-1][2] or leg_miles
    # Grid the leg geometry too, so each candidate snaps against only the few
    # geometry vertices in its own cell neighborhood -- not the whole leg. Scaning
    # the full geometry per candidate is what made dense metro legs crawl.
    geom_grid: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
    for glat, glon, cum in geom:
        geom_grid.setdefault(_maxspeed_cell(glat, glon), []).append(
            (glat, glon, cum))

    def neighbors(cell: tuple[int, int]) -> list[tuple[int, int]]:
        return [(cell[0] + dr, cell[1] + dc)
                for dr in (-1, 0, 1) for dc in (-1, 0, 1)]

    # A corridor-adjacent way point shares a cell (or a neighbor) with the geom
    # vertex it snaps to, so only visit way cells next to a geom cell.
    way_cells = {c for gcell in geom_grid for c in neighbors(gcell)}

    # (at_mi, mph, hgv, on_shield) for each on-corridor candidate point.
    points: list[tuple[float, float, bool, bool]] = []
    for cell in way_cells:
        candidates = grid.get(cell)
        if not candidates:
            continue
        for lat, lon, mph, hgv, ref_digits in candidates:
            best_d = float("inf")
            best_cum = 0.0
            for ncell in neighbors(_maxspeed_cell(lat, lon)):
                for glat, glon, cum in geom_grid.get(ncell, ()):
                    d = _haversine_mi(lat, lon, glat, glon)
                    if d < best_d:
                        best_d, best_cum = d, cum
            if best_d * 1609.34 <= MAXSPEED_CORRIDOR_M:
                on_shield = bool(shield) and ref_digits == shield
                points.append((best_cum / total * leg_miles, mph, hgv, on_shield))
    if not points:
        return []

    def choose(cands: list[tuple[float, float, bool, bool]]
               ) -> tuple[float, bool] | None:
        if not cands:
            return None
        on_shield = [c for c in cands if c[3]]
        pool = on_shield or cands
        hgv_pool = [c for c in pool if c[2]]
        chosen = hgv_pool or pool
        # The mainline limit, not a ramp/frontage outlier: take the highest in
        # the chosen pool (or the truck limit when hgv tags are present).
        return max(c[1] for c in chosen), bool(hgv_pool)

    half = MAXSPEED_SAMPLE_STRIDE_MI
    picked: list[tuple[float, float, bool]] = []   # (at_mi, mph, hgv)
    mile = 0.0
    while mile <= leg_miles + 1e-9:
        window = [p for p in points if abs(p[0] - mile) <= half]
        choice = choose(window)
        if choice is not None:
            picked.append((round(min(leg_miles, max(0.0, mile)), 1),
                           choice[0], choice[1]))
        mile += MAXSPEED_SAMPLE_STRIDE_MI

    # OSM tags a limit (especially maxspeed:hgv) on some ways but not their
    # neighbors, so a single stride can flip the value and then flip back. That
    # would read as choppy "speed limit 65... 70... 65" cues, so median-smooth a
    # lone blip whose neighbors agree before collapsing into the step function.
    smoothed = [s[1:] for s in picked]
    for i in range(1, len(smoothed) - 1):
        if smoothed[i] != smoothed[i - 1] and smoothed[i - 1] == smoothed[i + 1]:
            smoothed[i] = smoothed[i - 1]

    profile: list[dict[str, Any]] = []
    for (at_mi, _, _), (mph, hgv) in zip(picked, smoothed, strict=True):
        if not (profile and profile[-1]["mph"] == mph
                and profile[-1]["hgv"] == hgv):
            profile.append({"at_mi": at_mi, "mph": mph,
                            "source": MAXSPEED_SOURCE, "hgv": hgv})
    return profile


def _interpolated_geometry(route_points: list[dict[str, Any]]
                           ) -> list[tuple[float, float, float]] | None:
    """A dense [(lat, lon, at_mi), ...] polyline built locally from the
    checked-in route points (straight segments, ~0.5mi spacing).

    The network-free fallback when a leg has no cached OSRM geometry: it cuts
    corners where the real road curves between waypoints, so coverage is a touch
    lower on curvy legs, but it can never hang a batch on a live request."""
    pts = sorted(route_points, key=lambda p: float(p["at_mi"]))
    if len(pts) < 2:
        return None
    out: list[tuple[float, float, float]] = []
    for a, b in zip(pts, pts[1:], strict=False):
        a_mi, b_mi = float(a["at_mi"]), float(b["at_mi"])
        a_lat, a_lon = float(a["lat"]), float(a["lon"])
        b_lat, b_lon = float(b["lat"]), float(b["lon"])
        steps = max(1, int(max(0.0, b_mi - a_mi) / 0.5))
        for s in range(steps):
            t = s / steps
            out.append((a_lat + (b_lat - a_lat) * t,
                        a_lon + (b_lon - a_lon) * t,
                        a_mi + (b_mi - a_mi) * t))
    last = pts[-1]
    out.append((float(last["lat"]), float(last["lon"]), float(last["at_mi"])))
    return out


def bake_maxspeed_for_leg(
    leg: dict[str, Any],
    grid: MaxspeedGrid,
    rate_limit: float,
) -> list[dict[str, Any]]:
    route_points = list(leg.get("corridor", {}).get("route_points", ()))
    # Prefer cached dense OSRM geometry; never fetch live (a hung socket would
    # stall the whole batch). Fall back to local interpolation of route points.
    geom = (_osrm_geometry(route_points, rate_limit, cached_only=True)
            or _interpolated_geometry(route_points))
    if not geom:
        return []
    return assemble_maxspeed(grid, geom, float(leg["miles"]),
                             str(leg.get("highway", "")))


def run_maxspeed(data: dict[str, Any], args: argparse.Namespace) -> int:
    legs = data["legs"]
    if args.only:
        a, _, b = args.only.partition("->")
        legs = [leg for leg in legs
                if leg["from"] == a.strip() and leg["to"] == b.strip()]
        if not legs:
            raise SystemExit(f"No leg {args.only!r}")

    target_legs: list[dict[str, Any]] = []
    for leg in legs:
        if len(leg.get("corridor", {}).get("route_points", ())) < 2:
            continue
        if leg.get("corridor", {}).get("speed_limits") and not args.force:
            continue
        if not args.max_legs or len(target_legs) < args.max_legs:
            target_legs.append(leg)
    if not target_legs:
        print("No legs need a maxspeed profile (use --force to overwrite).")
        return 0

    pbf_paths = list(args.pbf)
    if not pbf_paths:
        states: set[str] = set()
        for leg in target_legs:
            states |= _leg_states(data, leg)
        pbf_paths = _pbf_for_states(states, args.osm_region_dir)
        if not pbf_paths:
            raise SystemExit(
                f"No per-state OSM extracts found in {args.osm_region_dir}. "
                "Pass --pbf explicitly or download the region files.")
        print(f"Auto-selected {len(pbf_paths)} per-state extract(s) for "
              f"{len(states)} state(s).", flush=True)
    missing = [p for p in pbf_paths if not p.exists()]
    if missing:
        raise SystemExit("OSM PBF not found: "
                         + ", ".join(str(p) for p in missing))

    bounds = _local_prefilter_bounds(target_legs)
    cache_path = args.local_index_cache or _maxspeed_index_cache_path(pbf_paths)
    print(f"Reading {len(pbf_paths)} local OSM extract(s) for maxspeed "
          f"({len(bounds)} route segment bbox filters, cache {cache_path})",
          flush=True)
    ways = load_or_build_maxspeed_index(
        pbf_paths, bounds, cache_path, rebuild=args.rebuild_local_index)
    grid = build_maxspeed_grid(ways)
    print(f"    using {len(ways)} corridor maxspeed ways "
          f"({len(grid)} grid cells)", flush=True)
    del ways

    baked = 0
    processed = 0
    for leg in target_legs:
        processed += 1
        print(f"[{processed}/{len(target_legs)}] {leg['from']}->{leg['to']} "
              f"({leg['highway']})", flush=True)
        try:
            profile = bake_maxspeed_for_leg(leg, grid, args.rate_limit)
        except Exception as exc:  # noqa: BLE001 - one bad leg must not abort the batch
            print(f"    skipped: {type(exc).__name__}: {exc}", flush=True)
            profile = []
        if profile:
            leg.setdefault("corridor", {})["speed_limits"] = profile
            baked += 1
            print(f"    {len(profile)} speed-limit samples", flush=True)
        else:
            print("    no on-corridor maxspeed; keeping the heuristic",
                  flush=True)
        if args.write and baked and processed % 10 == 0:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n",
                                  encoding="utf-8")
            print(f"    ...checkpointed world.json ({baked} legs so far)",
                  flush=True)

    print(f"\n{processed} legs processed, {baked} given a maxspeed profile.")
    if args.write and baked:
        WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {WORLD_PATH}")
    elif not args.write:
        print("(dry run; pass --write to update world.json)")
    return 0


# --- driver -----------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Curate OSM interchanges into world.json.")
    parser.add_argument("--write", action="store_true",
                        help="Write discovered interchanges back into world.json.")
    parser.add_argument("--only", default="",
                        help="Limit to one leg, e.g. 'New York->Philadelphia'.")
    parser.add_argument("--max-legs", type=int, default=0)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--force", action="store_true",
                        help="Re-discover legs that already have interchanges.")
    parser.add_argument("--pbf", type=Path, action="append", default=[],
                        help=("Read OSM interchange candidates from a local Geofabrik/"
                              "OpenStreetMap .osm.pbf extract instead of Overpass. "
                              "May be passed more than once."))
    parser.add_argument("--local-index-cache", type=Path,
                        help=("Reusable JSON cache for route-filtered local OSM "
                              "interchange features. Defaults beside --pbf."))
    parser.add_argument("--rebuild-local-index", action="store_true",
                        help="Ignore any existing --local-index-cache and rebuild it.")
    parser.add_argument("--maxspeed", action="store_true",
                        help="Bake real OSM maxspeed onto legs as a speed_limits "
                             "profile (the runtime prefers it over the heuristic) "
                             "instead of discovering interchanges. Reads local "
                             "per-state extracts, auto-selected from --osm-region-dir "
                             "unless --pbf is given.")
    parser.add_argument("--osm-region-dir", type=Path, default=OSM_REGION_CACHE_DIR,
                        help=("Directory of per-state Geofabrik extracts "
                              "(<state>-latest.osm.pbf) for --maxspeed auto-selection. "
                              f"Default: {OSM_REGION_CACHE_DIR}."))
    args = parser.parse_args(argv)

    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    if args.maxspeed:
        return run_maxspeed(data, args)
    legs = data["legs"]
    if args.only:
        a, _, b = args.only.partition("->")
        legs = [leg for leg in legs if leg["from"] == a.strip() and leg["to"] == b.strip()]
        if not legs:
            raise SystemExit(f"No leg {args.only!r}")

    eligible = 0
    index_legs: list[dict[str, Any]] = []
    process_legs: list[dict[str, Any]] = []
    for leg in legs:
        if _shield_pattern(str(leg.get("highway", ""))) is None:
            continue
        eligible += 1
        index_legs.append(leg)
        corridor = leg.setdefault("corridor", {})
        if corridor.get("interchanges") and not args.force:
            continue
        if not args.max_legs or len(process_legs) < args.max_legs:
            process_legs.append(leg)

    local_index: LocalOsmIndex | None = None
    pbf_paths = list(args.pbf)
    if pbf_paths:
        missing = [path for path in pbf_paths if not path.exists()]
        if missing:
            raise SystemExit(
                "OSM PBF not found: " + ", ".join(str(path) for path in missing)
            )
        bounds = _local_prefilter_bounds(index_legs)
        cache_path = (
            args.local_index_cache
            or (
                _default_local_index_cache(pbf_paths[0])
                if len(pbf_paths) == 1
                else pbf_paths[0].with_name("freight-fate-interchanges.json")
            )
        )
        print(
            f"Reading {len(pbf_paths)} local OSM extract(s) "
            f"({len(bounds)} route segment bbox filters, cache {cache_path})",
            flush=True,
        )
        local_index = load_or_build_local_index(
            pbf_paths,
            bounds,
            cache_path,
            rebuild=args.rebuild_local_index,
        )
        print(
            f"    using {len(local_index.junctions)} motorway junctions and "
            f"{len(local_index.ramps)} destination-tagged motorway ramps",
            flush=True,
        )
    elif args.local_index_cache:
        if args.rebuild_local_index:
            raise SystemExit("--rebuild-local-index requires at least one --pbf")
        bounds = _local_prefilter_bounds(index_legs)
        local_index = load_local_index_cache_only(args.local_index_cache, bounds)

    total_added = 0
    updated_legs = 0
    processed = 0
    for leg in process_legs:
        corridor = leg.setdefault("corridor", {})
        processed += 1
        label = f"{leg['from']}->{leg['to']} ({leg['highway']})"
        print(f"[{processed}] {label}", flush=True)
        found = discover_leg(leg, args.rate_limit, local_index)
        print(f"    {len(found)} interchanges", flush=True)
        if found:
            corridor["interchanges"] = found
            total_added += len(found)
            updated_legs += 1
        # Flush periodically so a long crawl is crash-safe and resumable: a
        # re-run without --force skips legs already written here.
        if args.write and updated_legs and processed % 10 == 0:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"    ...checkpointed world.json ({updated_legs} legs so far)",
                  flush=True)

    print(f"\n{eligible} Interstate legs eligible; "
          f"{processed} processed, {updated_legs} populated, "
          f"{total_added} interchanges total.")
    if args.write and updated_legs:
        WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {WORLD_PATH}")
    elif not args.write:
        print("(dry run; pass --write to update world.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
