"""Re-bake every leg's posted speed limits from the local Geofabrik extracts.

``tools/bake_curve_geometry.py`` wrote ``corridor.speed_limits`` by asking a
self-hosted Overpass for the maxspeed-tagged ways along each leg. That server
is not part of the kit any more, and its import date was never recorded, so a
map refresh could not reach the leg limits. This reads the same ways -- the
Overpass filter ``way[highway~motorway|trunk|primary|secondary|tertiary]
[maxspeed]``, with their tags and node geometry -- straight out of the state
extracts in ``~/.cache/freight-fate-osm/regions`` and hands them to the same
``bake_speed_limits`` + anchor repair over the leg's archived polyline, so a
refresh changes only what OpenStreetMap changed.

    uv run --group tooling python tools/bake_leg_speed_limits.py --write
    uv run --group tooling python tools/bake_leg_speed_limits.py --only a:b;c:d

Like the Overpass sweep, a leg whose bake finds nothing keeps the profile it
had. A leg carrying hand-estimated rows (source "estimated ...") is left
alone: those fill a hole OpenStreetMap had, and a re-bake would drop them.
Values are READ (OSM ``maxspeed``/``maxspeed:hgv`` tags); the per-extract way
index is cached beside each extract, keyed by the extract's size and mtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bake_curve_geometry as bcg  # noqa: E402
import osm_extract  # noqa: E402
import straw_curve_sample as scs  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

REGION_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
CLASSES = ("motorway", "trunk", "primary", "secondary", "tertiary")
CACHE_VERSION = 1
CELL_DEG = 0.02  # way-index grid, ~2 km; a sample looks at its own and adjacent cells
# Vertex grid for the near-line test: one cell of latitude is 111 m and two of
# longitude at least 142 m up to 50 N, both past the 90 m match corridor.
FINE_DEG = 0.001
assert FINE_DEG * 111_000 > scs.MATCH_CORRIDOR_M
SOURCE = (
    "OpenStreetMap maxspeed tags on the corridor highway ways, read from the local "
    f"Geofabrik state extracts (OpenStreetMap as of {osm_extract.OSM_EXTRACT_DATE}), "
    "normalized to mph; maxspeed:hgv preferred where tagged."
)


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return math.floor(lat / CELL_DEG), math.floor(lon / CELL_DEG)


def _around(lat: float, lon: float) -> list[tuple[int, int]]:
    r, c = _cell(lat, lon)
    return [(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)]


def corridor_band(legs: list[dict[str, Any]]) -> set[tuple[int, int]]:
    """Grid cells within one cell of any leg's archived polyline."""
    band: set[tuple[int, int]] = set()
    for leg in legs:
        try:
            coords = bcg.route_from_archive(leg)["coordinates"]
        except RuntimeError:
            continue
        for lon, lat in coords:
            band.update(_around(lat, lon))
    return band


def _read_extract(pbf: Path, band: set[tuple[int, int]]) -> list[list[Any]]:
    """Maxspeed-tagged ways of the five classes with a vertex in the band, as
    compact ``[id, tags, [[lat, lon], ...]]`` rows."""
    import osmium

    ways: list[tuple[int, dict[str, str], list[int]]] = []
    wanted: set[int] = set()
    classes = osmium.filter.TagFilter(*(("highway", c) for c in CLASSES))
    for way in osmium.FileProcessor(str(pbf), osmium.osm.WAY).with_filter(classes):
        if "maxspeed" not in way.tags:
            continue
        tags = {k: v for k, v in way.tags if k.startswith("maxspeed") or k in ("ref", "highway")}
        refs = [n.ref for n in way.nodes]
        ways.append((way.id, tags, refs))
        wanted.update(refs)
    locs: dict[int, tuple[float, float]] = {}
    nodes = osmium.filter.IdFilter(wanted)
    for node in osmium.FileProcessor(str(pbf), osmium.osm.NODE).with_filter(nodes):
        if node.location.valid():
            locs[node.id] = (node.location.lat, node.location.lon)
    out = []
    for way_id, tags, refs in ways:
        geometry = [list(locs[r]) for r in refs if r in locs]
        if len(geometry) >= 2 and any(_cell(lat, lon) in band for lat, lon in geometry):
            out.append([way_id, tags, geometry])
    return out


def load_ways(job: tuple[Path, set[tuple[int, int]], str]) -> list[list[Any]]:
    """One extract's ways, cached beside it and keyed by the extract and the band."""
    pbf, band, band_digest = job
    stat = pbf.stat()
    stamp = {
        "version": CACHE_VERSION,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "band": band_digest,
    }
    cache = pbf.with_name(pbf.name.replace(".osm.pbf", ".legspeed.json"))
    if cache.exists():
        payload = json.loads(cache.read_text(encoding="utf-8"))
        if payload.get("stamp") == stamp:
            return payload["ways"]
    started = time.time()
    ways = _read_extract(pbf, band)
    cache.write_text(json.dumps({"stamp": stamp, "ways": ways}), encoding="utf-8")
    print(f"  {pbf.name}: {len(ways):,} ways in {time.time() - started:.0f}s", flush=True)
    return ways


class WayGrid:
    """Ways bucketed by every cell their segments' boxes touch, deduped by id
    (a way crossing a state line is in both extracts)."""

    def __init__(self, ways: list[list[Any]]) -> None:
        self.by_id: dict[int, list[Any]] = {}
        self.cells: dict[tuple[int, int], set[int]] = {}
        for way in ways:
            if way[0] in self.by_id:
                continue
            self.by_id[way[0]] = way
            for (lat_a, lon_a), (lat_b, lon_b) in zip(way[2], way[2][1:], strict=False):
                r0, c0 = _cell(min(lat_a, lat_b), min(lon_a, lon_b))
                r1, c1 = _cell(max(lat_a, lat_b), max(lon_a, lon_b))
                for r in range(r0, r1 + 1):
                    for c in range(c0, c1 + 1):
                        self.cells.setdefault((r, c), set()).add(way[0])

    def near(self, coords: list[list[float]]) -> list[dict[str, Any]]:
        """The ways that can govern a sample on the line (``[lon, lat]``), in
        Overpass ``out geom tags`` shape.

        ``bake_speed_limits`` samples the line's own vertices and lets a way
        govern one within ``MATCH_CORRIDOR_M``, so a way none of whose segments
        passes that close to a vertex cannot change the result; dropping those
        first keeps the bake's all-pairs scan short. The test is conservative
        (a segment's box grown by a fine cell and more against a vertex grid)."""
        ids: set[int] = set()
        seen: set[tuple[int, int]] = set()
        for lon, lat in coords:
            for cell in _around(lat, lon):
                if cell not in seen:
                    seen.add(cell)
                    ids |= self.cells.get(cell, set())
        vertices = {(math.floor(lat / FINE_DEG), math.floor(lon / FINE_DEG)) for lon, lat in coords}
        return [
            {
                "type": "way",
                "id": i,
                "tags": self.by_id[i][1],
                "geometry": [{"lat": lat, "lon": lon} for lat, lon in self.by_id[i][2]],
            }
            for i in sorted(ids)
            if _passes_near(self.by_id[i][2], vertices)
        ]


def _passes_near(geometry: list[list[float]], vertices: set[tuple[int, int]]) -> bool:
    """Whether any segment's box, grown past the match corridor, holds a line vertex."""
    for (lat_a, lon_a), (lat_b, lon_b) in zip(geometry, geometry[1:], strict=False):
        r0 = math.floor((min(lat_a, lat_b) - FINE_DEG) / FINE_DEG)
        r1 = math.floor((max(lat_a, lat_b) + FINE_DEG) / FINE_DEG)
        c0 = math.floor((min(lon_a, lon_b) - 2 * FINE_DEG) / FINE_DEG)
        c1 = math.floor((max(lon_a, lon_b) + 2 * FINE_DEG) / FINE_DEG)
        if (r1 - r0 + 1) * (c1 - c0 + 1) > 2500:
            return True  # a very long segment: keep it rather than walk its box
        if any((r, c) in vertices for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)):
            return True
    return False


def bake_leg(leg: dict[str, Any], grid: WayGrid) -> tuple[list[dict], list[dict]]:
    """(world profile, gap-aware shard rows) for one leg, as the Overpass sweep made them."""
    coords = bcg.route_from_archive(leg)["coordinates"]
    cum = scs._cumulative_m(coords)
    raw_mi = cum[-1] / 1609.344
    miles = float(leg.get("miles", 0)) or None
    scale = (miles / raw_mi) if miles else 1.0
    full = bcg.bake_speed_limits(
        leg.get("highway", ""), coords, cum, scale, grid.near(coords), source=SOURCE
    )
    return bcg.world_speed_profile(leg, miles or round(raw_mi, 2), full), full


def hand_estimated(leg: dict[str, Any]) -> bool:
    rows = leg.get("corridor", {}).get("speed_limits") or []
    return any(str(r.get("source", "")).startswith("estimated") for r in rows)


_GRID: WayGrid | None = None


def _load_grid(jobs: list[tuple[Path, set[tuple[int, int]], str]]) -> None:
    """Worker start-up: every extract's ways, from the caches the first pool wrote."""
    global _GRID
    _GRID = WayGrid([way for job in jobs for way in load_ways(job)])


def _bake_in_worker(leg: dict[str, Any]) -> tuple[list[dict], list[dict]] | str:
    assert _GRID is not None
    try:
        return bake_leg(leg, _GRID)
    except RuntimeError as exc:  # no archived polyline
        return str(exc)


def _ready(job: tuple[Path, set[tuple[int, int]], str]) -> int:
    return len(load_ways(job))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="semicolon-separated slug pairs, e.g. a:b;c:d")
    parser.add_argument("--osm-region-dir", type=Path, default=REGION_DIR)
    parser.add_argument("--jobs", type=int, default=4, help="worker processes")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--report", type=Path, help="write {leg id: profile} JSON here")
    args = parser.parse_args(argv)
    if args.write:
        osm_extract.check_extracts(args.osm_region_dir)

    world = load_world()
    legs = bcg.select_legs(world, argparse.Namespace(only=args.only, region=None, limit=None))
    legs.sort(key=lambda leg: (leg["from"], leg["to"]))
    pbfs = sorted(args.osm_region_dir.glob("*-latest.osm.pbf"))
    manifest = args.osm_region_dir / osm_extract.MANIFEST_NAME
    if manifest.exists():  # the state extracts, not other regions sharing the folder
        files = {v["file"] for v in json.loads(manifest.read_text())["states"].values()}
        pbfs = [p for p in pbfs if p.name in files]
    band = corridor_band(world["legs"])
    band_digest = hashlib.sha256(json.dumps(sorted(band)).encode()).hexdigest()[:16]
    jobs = [(pbf, band, band_digest) for pbf in pbfs]
    with ProcessPoolExecutor(args.jobs) as pool:
        ways = sum(pool.map(_ready, jobs))
    print(f"{ways:,} maxspeed ways from {len(pbfs)} extracts", flush=True)

    todo = [leg for leg in legs if not hand_estimated(leg)]
    estimated = len(legs) - len(todo)
    slim = [{k: leg.get(k) for k in ("from", "to", "highway", "miles")} for leg in todo]
    with ProcessPoolExecutor(args.jobs, initializer=_load_grid, initargs=(jobs,)) as pool:
        results = list(pool.map(_bake_in_worker, slim, chunksize=8))

    shard_path = bcg.GAMEPLAY_DIR / "speed_limits.jsonl"
    shard = bcg._read_records(shard_path)
    report: dict[str, list[dict]] = {}
    baked = kept = failed = 0
    for leg, result in zip(todo, results, strict=True):
        leg_id = f"{leg['from']}:{leg['to']}"
        if isinstance(result, str):
            failed += 1
            print(f"  {leg_id}: {result}", flush=True)
            continue
        profile, full = result
        report[leg_id] = profile
        if not profile:
            kept += 1
            continue
        leg.setdefault("corridor", {})["speed_limits"] = profile
        shard[leg_id] = [{"leg": leg_id, **row} for row in full]
        baked += 1
    print(
        f"{baked} legs re-baked, {kept} found nothing and kept their profile, "
        f"{estimated} with hand-estimated rows left alone, {failed} without geometry",
        flush=True,
    )
    if args.report:
        args.report.write_text(json.dumps(report), encoding="utf-8")
    if args.write:
        world["osm_extract"] = osm_extract.meta()
        save_world(world)
        bcg._write_shard(shard_path, shard, {"layer": "speed_limits"})
        print("wrote the world source and the speed-limit shard", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
