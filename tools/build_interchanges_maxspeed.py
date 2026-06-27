# ruff: noqa: F401,F403,F405,F821,I001
from __future__ import annotations

from build_interchanges_base import *


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


__all__ = [name for name in globals() if not name.startswith("__")]
