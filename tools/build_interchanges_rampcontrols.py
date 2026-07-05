# ruff: noqa: F401,F403,F405,F821,I001
"""Ramp-terminal control bake: which interchanges end at a light or a sign.

Loaded into ``build_interchanges.py`` (the ``--ramp-controls`` mode) the same
way the maxspeed module is. For every baked interchange it looks for OSM
``highway=traffic_signals`` and ``highway=stop`` nodes that are *members of a
motorway_link way* near the exit -- that membership is exactly the ramp
terminal control, no surface-road topology needed. Positive findings bake a
``ramp_control`` of ``signal`` or ``stop`` onto the interchange record; when
neither is tagged the field is left absent so the runtime keeps its seeded
heuristic (absence of a tag is not evidence of free flow).
"""

from __future__ import annotations

from build_interchanges_base import *
from build_interchanges_maxspeed import (
    OSM_REGION_CACHE_DIR,
    _interpolated_geometry,
    _leg_states,
    _pbf_for_states,
)

# The terminal control sits at the far end of the ramp -- routinely 300m to
# 2km from the mainline junction (long turnpike ramps, toll plazas). Radii are
# sized to ramp length, not just snap error; contamination is limited because
# only motorway_link member nodes are candidates, and adjacent urban terminals
# almost always share a control type anyway. When the junction index pins the
# exit to its real OSM node the radius is tighter than when the location is
# estimated from (sometimes interpolated) leg geometry and a rounded at_mi.
RAMP_CONTROL_NEAR_JUNCTION_M = 1400.0
RAMP_CONTROL_NEAR_GEOM_M = 2000.0
# A ref-matched junction node must sit near the geometry estimate, or it is
# the same exit number on some other road entirely.
JUNCTION_MATCH_MAX_M = 8000.0
JUNCTION_INDEX_DEFAULT = Path.home() / ".cache" / "freight-fate-osm" / "interchanges-regions.json"
RAMP_CONTROL_INDEX_CACHE_VERSION = 1
RAMP_CONTROL_SOURCE = (
    "OpenStreetMap highway=traffic_signals/highway=stop node on a "
    "motorway_link way at this exit, read from a local Geofabrik extract, "
    f"accessed {ACCESSED_DATE}: https://www.openstreetmap.org/"
)

# (lat, lon, kind) where kind is "signal" or "stop"
RampControlPoint = tuple[float, float, str]


def _build_ramp_control_index_from_pbf(
    pbf_path: Path,
    bounds: list[LocalBounds],
    label: str = "1/1",
) -> list[RampControlPoint]:
    """Signal/stop nodes that sit on motorway_link ways near the routes.

    A single pass works because PBFs store nodes before ways: the node
    handler collects candidate control nodes (bounds-filtered), and the way
    handler then marks the ones a ramp link actually passes through."""
    try:
        import osmium  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Reading --pbf requires the tooling dependency group: "
            "uv sync --group dev --group tooling"
        ) from exc

    tag_filters = [
        osmium.filter.TagFilter(  # type: ignore[attr-defined]
            ("highway", "traffic_signals"),
            ("highway", "stop"),
            ("highway", "motorway_link"),
        )
    ]
    progress = _LocalIndexProgress(f"PBF {label} ramp controls", LOCAL_INDEX_PROGRESS_INTERVAL_SEC)

    class RampControlHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
        def __init__(self) -> None:
            super().__init__()
            self.candidates: dict[int, RampControlPoint] = {}
            self.on_ramp: list[RampControlPoint] = []
            self.nodes_seen = 0
            self.ways_seen = 0

        def node(self, node: Any) -> None:
            self.nodes_seen += 1
            progress.maybe(
                f"{self.nodes_seen:,} nodes, {self.ways_seen:,} ways; "
                f"{len(self.candidates):,} control nodes, "
                f"{len(self.on_ramp):,} on ramp links"
            )
            tags = {str(k): str(v) for k, v in node.tags}
            highway = tags.get("highway")
            if highway not in ("traffic_signals", "stop"):
                return
            # Ramp meters are signals on ramp links too, but they meter the
            # on-ramp flow -- they are not the terminal intersection light.
            if tags.get("traffic_signals") == "ramp_meter":
                return
            if not node.location.valid():
                return
            lat = float(node.location.lat)
            lon = float(node.location.lon)
            if not _inside_any_bounds(lat, lon, bounds):
                return
            kind = "signal" if highway == "traffic_signals" else "stop"
            self.candidates[int(node.id)] = (lat, lon, kind)

        def way(self, way: Any) -> None:
            self.ways_seen += 1
            progress.maybe(
                f"{self.nodes_seen:,} nodes, {self.ways_seen:,} ways; "
                f"{len(self.candidates):,} control nodes, "
                f"{len(self.on_ramp):,} on ramp links"
            )
            tags = {str(k): str(v) for k, v in way.tags}
            if tags.get("highway") != "motorway_link":
                return
            for node_ref in way.nodes:
                node_id = getattr(node_ref, "ref", None)
                if node_id is None:
                    continue
                point = self.candidates.get(int(node_id))
                if point is not None:
                    self.on_ramp.append(point)

    handler = RampControlHandler()
    try:
        print(f"    reading ramp controls from PBF {label}: {pbf_path}", flush=True)
        handler.apply_file(str(pbf_path), filters=tag_filters)
    except RuntimeError as exc:
        raise SystemExit(f"Could not read OSM PBF {pbf_path}: {exc}") from exc
    unique = sorted(set(handler.on_ramp))
    print(
        f"    retained {len(unique):,} ramp-link control nodes "
        f"(of {len(handler.candidates):,} corridor control nodes) from {label}",
        flush=True,
    )
    return unique


def _ramp_control_index_cache_path(pbf_paths: list[Path]) -> Path:
    if len(pbf_paths) == 1:
        name = pbf_paths[0].name
        for suffix in (".osm.pbf", ".pbf"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return pbf_paths[0].with_name(f"{name}.rampcontrols.json")
    return pbf_paths[0].with_name("freight-fate-rampcontrols.json")


def load_or_build_ramp_control_index(
    pbf_paths: list[Path],
    bounds: list[LocalBounds],
    cache_path: Path,
    rebuild: bool = False,
) -> list[RampControlPoint]:
    if not rebuild and cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if (
            payload is not None
            and payload.get("version") == RAMP_CONTROL_INDEX_CACHE_VERSION
            and payload.get("pbfs") == _pbf_set_metadata(pbf_paths)
            and payload.get("bounds_digest") == _bounds_digest(bounds)
        ):
            points = [
                (float(p[0]), float(p[1]), str(p[2])) for p in payload.get("points", ())
            ]
            print(
                f"Loaded ramp-control index cache: {cache_path} ({len(points)} nodes)",
                flush=True,
            )
            return points
    points: list[RampControlPoint] = []
    for i, pbf_path in enumerate(pbf_paths, start=1):
        points.extend(
            _build_ramp_control_index_from_pbf(pbf_path, bounds, label=f"{i}/{len(pbf_paths)}")
        )
    points = sorted(set(points))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "version": RAMP_CONTROL_INDEX_CACHE_VERSION,
                "pbfs": _pbf_set_metadata(pbf_paths),
                "bounds_digest": _bounds_digest(bounds),
                "points": [list(p) for p in points],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return points


def _exit_location(
    geom: list[tuple[float, float, float]], at_mi: float, leg_miles: float
) -> tuple[float, float]:
    """Geometry vertex at an interchange's leg-frame milepost."""
    total = geom[-1][2] or leg_miles
    target = at_mi / leg_miles * total if leg_miles else 0.0
    best = min(geom, key=lambda p: abs(p[2] - target))
    return best[0], best[1]


def load_junction_ref_map(path: Path) -> dict[str, list[tuple[float, float]]]:
    """Exit-ref -> junction node locations from a saved interchange index.

    The interchange crawl already banked every motorway_junction node with its
    exit ref and precise location; reusing it pins each baked exit to its real
    OSM node instead of a geometry estimate. Read leniently: any index built
    over these routes works, staleness only costs a few unmatched refs."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"    junction index unreadable ({exc}); using geometry estimates", flush=True)
        return {}
    by_ref: dict[str, list[tuple[float, float]]] = {}
    for raw in payload.get("junctions", ()):
        ref = re.sub(r"\s+", "", str(raw.get("tags", {}).get("ref", "")).strip())
        if not ref:
            continue
        by_ref.setdefault(ref, []).append((float(raw["lat"]), float(raw["lon"])))
    print(
        f"    junction index: {sum(len(v) for v in by_ref.values()):,} "
        f"ref-tagged junction nodes ({path})",
        flush=True,
    )
    return by_ref


def _pinned_exit_location(
    ix: dict[str, Any],
    estimate: tuple[float, float],
    junction_refs: dict[str, list[tuple[float, float]]],
) -> tuple[tuple[float, float], float]:
    """(location, match radius): the exit's real junction node when its ref
    matches one near the geometry estimate, else the estimate itself."""
    ref = re.sub(r"\s+", "", str(ix.get("exit_ref", "")).strip())
    candidates = junction_refs.get(ref, ()) if ref else ()
    best: tuple[float, float] | None = None
    best_m = JUNCTION_MATCH_MAX_M
    for lat, lon in candidates:
        dist_m = _haversine_mi(estimate[0], estimate[1], lat, lon) * 1609.34
        if dist_m <= best_m:
            best_m = dist_m
            best = (lat, lon)
    if best is not None:
        return best, RAMP_CONTROL_NEAR_JUNCTION_M
    return estimate, RAMP_CONTROL_NEAR_GEOM_M


def bake_ramp_controls_for_leg(
    leg: dict[str, Any],
    points: list[RampControlPoint],
    rate_limit: float,
    force: bool = False,
    junction_refs: dict[str, list[tuple[float, float]]] | None = None,
) -> int:
    """Set ``ramp_control`` on the leg's interchanges from nearby ramp-link
    control nodes. Returns how many interchanges got a control."""
    interchanges = list(leg.get("corridor", {}).get("interchanges", ()))
    if not interchanges:
        return 0
    route_points = list(leg.get("corridor", {}).get("route_points", ()))
    geom = _osrm_geometry(route_points, rate_limit, cached_only=True) or _interpolated_geometry(
        route_points
    )
    if not geom:
        return 0
    leg_miles = float(leg["miles"])
    baked = 0
    for ix in interchanges:
        if ix.get("ramp_control") and not force:
            continue
        estimate = _exit_location(geom, float(ix.get("at_mi", 0.0)), leg_miles)
        (lat, lon), radius_m = _pinned_exit_location(ix, estimate, junction_refs or {})
        kinds = {
            kind
            for plat, plon, kind in points
            if _haversine_mi(lat, lon, plat, plon) * 1609.34 <= radius_m
        }
        if "signal" in kinds:
            control = "signal"
        elif "stop" in kinds:
            control = "stop"
        else:
            continue  # untagged: the runtime heuristic stands in
        ix["ramp_control"] = control
        ix["ramp_control_source"] = RAMP_CONTROL_SOURCE
        baked += 1
    return baked


def run_ramp_controls(data: dict[str, Any], args: argparse.Namespace) -> int:
    legs = data["legs"]
    if args.only:
        a, _, b = args.only.partition("->")
        legs = [leg for leg in legs if leg["from"] == a.strip() and leg["to"] == b.strip()]
        if not legs:
            raise SystemExit(f"No leg {args.only!r}")

    target_legs: list[dict[str, Any]] = []
    for leg in legs:
        corridor = leg.get("corridor", {})
        if not corridor.get("interchanges") or len(corridor.get("route_points", ())) < 2:
            continue
        if not args.force and all(
            ix.get("ramp_control") for ix in corridor["interchanges"]
        ):
            continue
        if not args.max_legs or len(target_legs) < args.max_legs:
            target_legs.append(leg)
    if not target_legs:
        print("No legs need ramp controls (use --force to redo).")
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
                "Pass --pbf explicitly or download the region files."
            )
        print(
            f"Auto-selected {len(pbf_paths)} per-state extract(s) for {len(states)} state(s).",
            flush=True,
        )
    missing = [p for p in pbf_paths if not p.exists()]
    if missing:
        raise SystemExit("OSM PBF not found: " + ", ".join(str(p) for p in missing))

    bounds = _local_prefilter_bounds(target_legs)
    cache_path = args.local_index_cache or _ramp_control_index_cache_path(pbf_paths)
    print(
        f"Reading {len(pbf_paths)} local OSM extract(s) for ramp controls "
        f"({len(bounds)} route segment bbox filters, cache {cache_path})",
        flush=True,
    )
    points = load_or_build_ramp_control_index(
        pbf_paths, bounds, cache_path, rebuild=args.rebuild_local_index
    )
    print(f"    using {len(points)} ramp-link control nodes", flush=True)
    junction_refs: dict[str, list[tuple[float, float]]] = {}
    if JUNCTION_INDEX_DEFAULT.exists():
        junction_refs = load_junction_ref_map(JUNCTION_INDEX_DEFAULT)

    baked_total = 0
    baked_legs = 0
    processed = 0
    for leg in target_legs:
        processed += 1
        print(
            f"[{processed}/{len(target_legs)}] {leg['from']}->{leg['to']} ({leg['highway']})",
            flush=True,
        )
        try:
            baked = bake_ramp_controls_for_leg(
                leg, points, args.rate_limit, force=args.force, junction_refs=junction_refs
            )
        except Exception as exc:  # noqa: BLE001 - one bad leg must not abort the batch
            print(f"    skipped: {type(exc).__name__}: {exc}", flush=True)
            baked = 0
        total_ix = len(leg.get("corridor", {}).get("interchanges", ()))
        print(f"    {baked}/{total_ix} interchanges given a control", flush=True)
        if baked:
            baked_total += baked
            baked_legs += 1
        if args.write and baked_legs and processed % 10 == 0:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"    ...checkpointed world.json ({baked_legs} legs so far)", flush=True)

    print(
        f"\n{processed} legs processed, {baked_legs} touched, "
        f"{baked_total} interchanges given ramp controls."
    )
    if args.write and baked_legs:
        WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {WORLD_PATH}")
    elif not args.write:
        print("(dry run; pass --write to update world.json)")
    return 0


__all__ = [name for name in globals() if not name.startswith("__")]
