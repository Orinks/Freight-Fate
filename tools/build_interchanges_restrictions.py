# ruff: noqa: F401,F403,F405,F821,I001
"""Posted clearance/weight restriction bake: low bridges and weight limits.

Loaded into ``build_interchanges.py`` (the ``--restrictions`` mode) the same
way the maxspeed module is. It reads OSM ``maxheight`` and ``maxweight`` tags
on mainline highway ways from the local per-state Geofabrik extracts, snaps
them to checked-in route geometry, and bakes a ``corridor.restrictions`` list
of route-positioned advisories the GPS can speak ahead of the point.

The ORS driving-hgv routing already avoids impassable restrictions when the
route geometry is generated, so what lands here is the *posted signage a legal
truck still drives past* -- a 14-foot bridge or a 30-ton limit worth an
advisory cue, not a reroute. An empty baked list means the sweep ran and the
corridor is clean; the runtime stays quiet either way until data exists.

A restriction way must run *along* the leg (bearing-aligned within
``RESTRICTION_ALIGN_DEG``), which rejects the classic false positive: a
restricted surface street crossing over the highway right at the corridor.
"""

from __future__ import annotations

from build_interchanges_base import *
from build_interchanges_maxspeed import (
    OSM_REGION_CACHE_DIR,
    _interpolated_geometry,
    _leg_states,
    _pbf_for_states,
    _route_digits,
)

# Mainline classes only: link/service/residential ways under a low bridge are
# not the driven corridor, and crossings are rejected by the bearing gate.
RESTRICTION_HIGHWAY_CLASSES = ("motorway", "trunk", "primary", "secondary")
RESTRICTION_CORRIDOR_M = 100.0  # a restriction way must snap this close
RESTRICTION_CORRIDOR_REFLESS_M = 60.0  # tighter when the way has no route ref
RESTRICTION_ALIGN_DEG = 35.0  # way must run along the leg, not across it
RESTRICTION_MERGE_MI = 0.3  # collapse duplicate carriageway tags, keep lowest
# Bake only values a driver would hear called out: legal-but-tight clearances
# and sub-Interstate weight limits. 16ft+ and 40+ short tons are unposted noise.
RESTRICTION_HEIGHT_MAX_FT = 16.0
RESTRICTION_WEIGHT_MAX_TONS = 40.0
RESTRICTION_HEIGHT_MIN_FT = 9.0  # under this is a data error, not a road
RESTRICTION_WEIGHT_MIN_TONS = 3.0
RESTRICTION_INDEX_CACHE_VERSION = 1
M_TO_FT = 3.28084
TONNE_TO_SHORT_TON = 1.1023113
LB_TO_SHORT_TON = 1.0 / 2000.0
KG_TO_SHORT_TON = 1.0 / 907.18474
RESTRICTIONS_SOURCE = (
    "OpenStreetMap maxheight/maxweight tags on the corridor highway ways, read "
    "from a local Geofabrik extract and snapped to checked-in route geometry, "
    f"accessed {ACCESSED_DATE}. https://www.openstreetmap.org/"
)

_UNTAGGED_VALUES = {
    "",
    "default",
    "none",
    "no",
    "unsigned",
    "no_indications",
    "no_sign",
    "below_default",
    "physical",
    "unknown",
}


def parse_osm_maxheight_ft(raw: Any) -> float | None:
    """An OSM ``maxheight`` value in feet, or None when unusable.

    Handles the tagging reality: bare meters ("4.1"), explicit meters
    ("4.1 m"), feet-and-inches ("13'6\""), and explicit feet ("13.5 ft")."""
    text = str(raw or "").strip().lower().replace(",", ".")
    if text in _UNTAGGED_VALUES:
        return None
    m = re.match(r"^(\d+)\s*'\s*(\d+(?:\.\d+)?)?\s*\"?$", text)
    if m:
        inches = float(m.group(2)) if m.group(2) else 0.0
        return float(m.group(1)) + inches / 12.0
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(m|meter|meters|ft|feet)?$", text)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2) or "m"  # OSM default unit is meters
    if unit in {"ft", "feet"}:
        return value
    return value * M_TO_FT


def parse_osm_maxweight_tons(raw: Any) -> float | None:
    """An OSM ``maxweight`` value in US short tons, or None when unusable.

    Bare numbers and "t" are metric tonnes (the OSM default), "st" is short
    tons, and pound/kilogram taggings convert."""
    text = str(raw or "").strip().lower().replace(",", ".")
    if text in _UNTAGGED_VALUES:
        return None
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(t|st|lbs|lb|kg)?$", text)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2) or "t"
    if unit == "st":
        return value
    if unit in {"lb", "lbs"}:
        return value * LB_TO_SHORT_TON
    if unit == "kg":
        return value * KG_TO_SHORT_TON
    return value * TONNE_TO_SHORT_TON


@dataclass(frozen=True, slots=True)
class LocalRestrictionWay:
    coords: tuple[tuple[float, float], ...]
    kind: str  # low_clearance | weight_limit
    value: float  # feet | short tons
    ref: str


@dataclass(frozen=True, slots=True)
class _RestrictionWayRaw:
    node_ids: tuple[int, ...]
    kind: str
    value: float
    ref: str


def _way_restrictions(tags: dict[str, str]) -> list[tuple[str, float]]:
    """The bakeable (kind, value) restrictions a way's tags declare."""
    out: list[tuple[str, float]] = []
    feet = parse_osm_maxheight_ft(tags.get("maxheight"))
    if feet is not None and RESTRICTION_HEIGHT_MIN_FT <= feet <= RESTRICTION_HEIGHT_MAX_FT:
        out.append(("low_clearance", round(feet, 2)))
    tons = parse_osm_maxweight_tons(tags.get("maxweight"))
    if tons is not None and RESTRICTION_WEIGHT_MIN_TONS <= tons < RESTRICTION_WEIGHT_MAX_TONS:
        out.append(("weight_limit", round(tons, 1)))
    return out


def _build_restriction_index_from_pbf(
    pbf_path: Path,
    bounds: list[LocalBounds],
    label: str = "1/1",
) -> list[LocalRestrictionWay]:
    """Mainline highway ways carrying a bakeable restriction near the routes.

    Two passes, matching the maxspeed reader: pass 1 keeps mainline-class ways
    whose ``maxheight``/``maxweight`` parses under the bake thresholds; pass 2
    resolves those ways' node coordinates inside the route corridor bounds."""
    try:
        import osmium  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Reading --pbf requires the tooling dependency group: "
            "uv sync --group dev --group tooling"
        ) from exc

    tag_filters = [
        osmium.filter.TagFilter(  # type: ignore[attr-defined]
            *(("highway", value) for value in RESTRICTION_HIGHWAY_CLASSES)
        )
    ]
    pass1 = _LocalIndexProgress(
        f"PBF {label} restrictions pass 1", LOCAL_INDEX_PROGRESS_INTERVAL_SEC
    )

    class RestrictionWayHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
        def __init__(self) -> None:
            super().__init__()
            self.ways: list[_RestrictionWayRaw] = []
            self.wanted: set[int] = set()
            self.ways_seen = 0

        def way(self, way: Any) -> None:
            self.ways_seen += 1
            pass1.maybe(f"{self.ways_seen:,} ways; retained {len(self.ways):,} restriction ways")
            tags = {str(k): str(v) for k, v in way.tags}
            if tags.get("highway") not in RESTRICTION_HIGHWAY_CLASSES:
                return
            restrictions = _way_restrictions(tags)
            if not restrictions:
                return
            node_ids = [int(ref.ref) for ref in way.nodes if getattr(ref, "ref", None) is not None]
            if len(node_ids) < 2:
                return
            for kind, value in restrictions:
                self.ways.append(
                    _RestrictionWayRaw(
                        node_ids=tuple(node_ids),
                        kind=kind,
                        value=value,
                        ref=str(tags.get("ref", "")).strip(),
                    )
                )
            self.wanted.update(node_ids)

    handler = RestrictionWayHandler()
    try:
        print(f"    building restriction index from PBF {label} pass 1: {pbf_path}", flush=True)
        handler.apply_file(str(pbf_path), filters=tag_filters)
    except RuntimeError as exc:
        raise SystemExit(f"Could not read OSM PBF {pbf_path}: {exc}") from exc

    if not handler.wanted:
        return []

    pass2 = _LocalIndexProgress(
        f"PBF {label} restrictions pass 2", LOCAL_INDEX_PROGRESS_INTERVAL_SEC
    )

    class RestrictionNodeHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
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

    node_handler = RestrictionNodeHandler(handler.wanted)
    id_filters = [osmium.filter.IdFilter(handler.wanted)]  # type: ignore[attr-defined]
    try:
        print(
            f"    resolving {len(handler.wanted):,} restriction-way node locations "
            f"from PBF {label} pass 2",
            flush=True,
        )
        node_handler.apply_file(str(pbf_path), filters=id_filters)
    except RuntimeError as exc:
        raise SystemExit(f"Could not read OSM PBF {pbf_path}: {exc}") from exc

    ways: list[LocalRestrictionWay] = []
    for raw in handler.ways:
        coords = tuple(
            node_handler.coords[node_id]
            for node_id in raw.node_ids
            if node_id in node_handler.coords
        )
        if len(coords) >= 2:
            ways.append(
                LocalRestrictionWay(coords=coords, kind=raw.kind, value=raw.value, ref=raw.ref)
            )
    print(f"    retained {len(ways):,} route-corridor restriction ways from {label}", flush=True)
    return ways


def _restriction_way_to_json(way: LocalRestrictionWay) -> dict[str, Any]:
    return {
        "coords": [list(c) for c in way.coords],
        "kind": way.kind,
        "value": way.value,
        "ref": way.ref,
    }


def _restriction_way_from_json(raw: dict[str, Any]) -> LocalRestrictionWay:
    return LocalRestrictionWay(
        coords=tuple((float(c[0]), float(c[1])) for c in raw.get("coords", ())),
        kind=str(raw["kind"]),
        value=float(raw["value"]),
        ref=str(raw.get("ref", "")),
    )


def _restriction_index_cache_path(pbf_paths: list[Path]) -> Path:
    if len(pbf_paths) == 1:
        name = pbf_paths[0].name
        for suffix in (".osm.pbf", ".pbf"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return pbf_paths[0].with_name(f"{name}.restrictions.json")
    return pbf_paths[0].with_name("freight-fate-restrictions.json")


def load_or_build_restriction_index(
    pbf_paths: list[Path],
    bounds: list[LocalBounds],
    cache_path: Path,
    rebuild: bool = False,
) -> list[LocalRestrictionWay]:
    if not rebuild and cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if (
            payload is not None
            and payload.get("version") == RESTRICTION_INDEX_CACHE_VERSION
            and payload.get("pbfs") == _pbf_set_metadata(pbf_paths)
            and payload.get("bounds_digest") == _bounds_digest(bounds)
        ):
            ways = [_restriction_way_from_json(w) for w in payload.get("ways", ())]
            print(
                f"Loaded local OSM restriction index cache: {cache_path} ({len(ways)} ways)",
                flush=True,
            )
            return ways
    ways: list[LocalRestrictionWay] = []
    for i, pbf_path in enumerate(pbf_paths, start=1):
        ways.extend(
            _build_restriction_index_from_pbf(pbf_path, bounds, label=f"{i}/{len(pbf_paths)}")
        )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "version": RESTRICTION_INDEX_CACHE_VERSION,
                "pbfs": _pbf_set_metadata(pbf_paths),
                "bounds_digest": _bounds_digest(bounds),
                "ways": [_restriction_way_to_json(w) for w in ways],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return ways


def _bearing_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Forward bearing from point a to point b in degrees."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360.0


def _axis_diff_deg(bearing_a: float, bearing_b: float) -> float:
    """Angle between two road axes, ignoring travel direction (0..90)."""
    diff = abs(bearing_a - bearing_b) % 180.0
    return min(diff, 180.0 - diff)


def _segment_bearing(
    points: list[tuple[float, float]] | tuple[tuple[float, float], ...], index: int
) -> float | None:
    """Bearing of the polyline around ``points[index]``, or None when degenerate."""
    if len(points) < 2:
        return None
    a = points[max(0, index - 1)]
    b = points[min(len(points) - 1, index + 1)]
    if a == b:
        return None
    return _bearing_deg(a, b)


def assemble_restrictions(
    ways: list[LocalRestrictionWay],
    geom: list[tuple[float, float, float]],
    leg_miles: float,
    highway: str,
) -> list[dict[str, Any]]:
    """Snap restriction ways onto a leg and collapse them into advisories.

    A way contributes when its closest vertex sits inside the snap corridor
    (tighter without a matching route ref) and the way runs along the leg's
    local bearing -- a restricted road *crossing over* the corridor never
    bakes. Duplicate per-carriageway tags within ``RESTRICTION_MERGE_MI``
    collapse to the most restrictive value."""
    if len(geom) < 2:
        return []
    shield = _route_digits(highway)
    total = geom[-1][2] or leg_miles
    geom_bounds = _geometry_bounds(geom, RESTRICTION_CORRIDOR_M * 2)

    points: list[tuple[float, float, str, float]] = []  # (at_mi, value, kind, snap_mi)
    for way in ways:
        if not any(_inside_bounds(lat, lon, geom_bounds) for lat, lon in way.coords):
            continue
        # The way's midpoint vertex is the advisory point: stable for long
        # restricted stretches (closest-vertex picks an arbitrary end) and
        # exact for the usual short bridge segment.
        best_way_i = len(way.coords) // 2
        wlat, wlon = way.coords[best_way_i]
        best_d = float("inf")
        best_cum = 0.0
        best_geom_i = 0
        for gi, (glat, glon, cum) in enumerate(geom):
            d = _haversine_mi(wlat, wlon, glat, glon)
            if d < best_d:
                best_d, best_cum, best_geom_i = d, cum, gi
        ref_digits = _route_digits(way.ref)
        on_shield = bool(shield) and ref_digits == shield
        corridor_m = RESTRICTION_CORRIDOR_M if on_shield else RESTRICTION_CORRIDOR_REFLESS_M
        if best_d * 1609.34 > corridor_m:
            continue
        way_bearing = _segment_bearing(way.coords, best_way_i)
        geom_bearing = _segment_bearing([(g[0], g[1]) for g in geom], best_geom_i)
        if (
            way_bearing is not None
            and geom_bearing is not None
            and _axis_diff_deg(way_bearing, geom_bearing) > RESTRICTION_ALIGN_DEG
        ):
            continue
        at_mi = best_cum / total * leg_miles
        if not 0.0 < at_mi < leg_miles:
            continue
        points.append((at_mi, way.value, way.kind, best_d))

    out: list[dict[str, Any]] = []
    for kind in ("low_clearance", "weight_limit"):
        cluster: list[tuple[float, float]] = []  # (at_mi, value)
        for at_mi, value, point_kind, _ in sorted(points):
            if point_kind != kind:
                continue
            if cluster and at_mi - cluster[-1][0] > RESTRICTION_MERGE_MI:
                out.append(_emit_restriction(kind, cluster))
                cluster = []
            cluster.append((at_mi, value))
        if cluster:
            out.append(_emit_restriction(kind, cluster))
    out.sort(key=lambda r: r["at_mi"])
    return out


def _emit_restriction(kind: str, cluster: list[tuple[float, float]]) -> dict[str, Any]:
    """One advisory for a cluster of tagged points: lowest value, first mile."""
    value = min(v for _, v in cluster)
    at_mi = round(min(m for m, _ in cluster), 1)
    record: dict[str, Any] = {"at_mi": at_mi, "kind": kind, "source": RESTRICTIONS_SOURCE}
    if kind == "low_clearance":
        record["feet"] = round(value, 2)
    else:
        record["tons"] = round(value, 1)
    return record


def bake_restrictions_for_leg(
    leg: dict[str, Any],
    ways: list[LocalRestrictionWay],
    rate_limit: float,
) -> list[dict[str, Any]]:
    route_points = list(leg.get("corridor", {}).get("route_points", ()))
    # Cached dense geometry only; never a live request (same policy as maxspeed).
    geom = _osrm_geometry(route_points, rate_limit, cached_only=True) or _interpolated_geometry(
        route_points
    )
    if not geom:
        return []
    return assemble_restrictions(ways, geom, float(leg["miles"]), str(leg.get("highway", "")))


def run_restrictions(data: dict[str, Any], args: argparse.Namespace) -> int:
    legs = data["legs"]
    if args.only:
        a, _, b = args.only.partition("->")
        legs = [leg for leg in legs if leg["from"] == a.strip() and leg["to"] == b.strip()]
        if not legs:
            raise SystemExit(f"No leg {args.only!r}")

    target_legs: list[dict[str, Any]] = []
    for leg in legs:
        if len(leg.get("corridor", {}).get("route_points", ())) < 2:
            continue
        # An empty baked list means "swept, corridor clean", so presence of the
        # key (not truthiness) marks a leg done.
        if "restrictions" in leg.get("corridor", {}) and not args.force:
            continue
        if not args.max_legs or len(target_legs) < args.max_legs:
            target_legs.append(leg)
    if not target_legs:
        print("No legs need a restrictions sweep (use --force to redo).")
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
    cache_path = args.local_index_cache or _restriction_index_cache_path(pbf_paths)
    print(
        f"Reading {len(pbf_paths)} local OSM extract(s) for restrictions "
        f"({len(bounds)} route segment bbox filters, cache {cache_path})",
        flush=True,
    )
    ways = load_or_build_restriction_index(
        pbf_paths, bounds, cache_path, rebuild=args.rebuild_local_index
    )
    print(f"    using {len(ways)} corridor restriction ways", flush=True)

    baked = 0
    processed = 0
    for leg in target_legs:
        processed += 1
        print(
            f"[{processed}/{len(target_legs)}] {leg['from']}->{leg['to']} ({leg['highway']})",
            flush=True,
        )
        try:
            profile = bake_restrictions_for_leg(leg, ways, args.rate_limit)
        except Exception as exc:  # noqa: BLE001 - one bad leg must not abort the batch
            print(f"    skipped: {type(exc).__name__}: {exc}", flush=True)
            continue
        leg.setdefault("corridor", {})["restrictions"] = profile
        if profile:
            baked += 1
            for record in profile:
                value = record.get("feet", record.get("tons"))
                print(f"    {record['kind']} {value} at mile {record['at_mi']}", flush=True)
        if args.write and processed % 100 == 0:
            _write_world_retrying(data)
            print(
                f"    ...checkpointed the world source ({baked} legs with advisories)", flush=True
            )

    print(f"\n{processed} legs swept, {baked} carry restriction advisories.")
    if args.write:
        _write_world_retrying(data)
        print(f"Wrote {WORLD_SOURCE_PATH}")
    else:
        print("(dry run; pass --write to update the world source)")
    return 0


def _write_world_retrying(data: dict[str, Any], attempts: int = 5) -> None:
    """Write the world source, riding out transient Windows locks on the shards.

    Antivirus/indexer scans intermittently fail the open with EINVAL/EACCES;
    a short backoff and retry recovers. The world stays intact on failure
    because the open itself is what errors."""
    for attempt in range(attempts):
        try:
            save_world(data)
            return
        except OSError as exc:
            if attempt == attempts - 1:
                raise
            wait = 2.0 * (attempt + 1)
            print(
                f"    world source write failed ({exc}); retrying in {wait:.0f}s",
                flush=True,
            )
            time.sleep(wait)


__all__ = [name for name in globals() if not name.startswith("__")]
