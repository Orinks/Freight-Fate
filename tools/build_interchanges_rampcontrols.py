# ruff: noqa: F401,F403,F405,F821,I001
"""Ramp-terminal control bake: which interchanges end at a light or a sign.

Loaded into ``build_interchanges.py`` (the ``--ramp-controls`` mode) the same
way the maxspeed module is. For every baked interchange it looks for OSM
``highway=traffic_signals`` and ``highway=stop`` nodes that are *members of a
motorway_link way* near the exit -- that membership is exactly the ramp
terminal control, no surface-road topology needed. Positive findings bake a
``ramp_control`` of ``signal`` or ``stop`` onto the interchange record.

Where neither is tagged, absence is not evidence of free flow -- so the pass
also walks the exit's motorway_link topology (see the far-end section below):
an exit whose every ramp chain merges back onto a motorway bakes an explicit
``ramp_control: none`` plus ``ramp_far_end: motorway``, and a chain that
touches a surface road bakes ``ramp_far_end: surface`` so the runtime stops
guessing free flow off signage. Only exits neither half could judge are left
to the runtime's seeded heuristic.
"""

from __future__ import annotations

from build_interchanges_base import *
from build_interchanges_maxspeed import (
    OSM_REGION_CACHE_DIR,
    _leg_states,
    _pbf_for_states,
    corridor_geometry,
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
            points = [(float(p[0]), float(p[1]), str(p[2])) for p in payload.get("points", ())]
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
    topo: dict[str, Any] | None = None,
    stats: dict[str, int] | None = None,
) -> int:
    """Set ``ramp_control`` and ``ramp_far_end`` on the leg's interchanges.

    Control precedence, best evidence first: a control read within
    RAMP_TERMINAL_CONTROL_M of a WALKED TERMINAL NODE (the walk says where
    the ramp ends, the tag says what stands there); then the exit-wide
    radius match against ramp-link control nodes, kept for exits the walk
    could not judge; then ``none`` derived from an all-motorway far end.
    Exits none of that reaches stay empty for the runtime's seeded weights.
    Yields and roundabouts found at terminals bake as ``yield`` and
    ``roundabout`` (the game plays both by gap acceptance against the cross
    bubble since 2026-08-20). Precedence within a terminal's kinds: signal,
    then roundabout, then stop, then yield -- a give_way node AT a
    roundabout entry is the roundabout's own furniture, and a signalized
    roundabout or terminal is worked as its light.

    Returns how many interchanges got a control or a far end."""
    interchanges = list(leg.get("corridor", {}).get("interchanges", ()))
    if not interchanges:
        return 0
    geom, _note = corridor_geometry(leg, rate_limit)
    if not geom:
        return 0
    leg_miles = float(leg["miles"])
    stats = stats if stats is not None else {}
    baked = 0
    for ix in interchanges:
        had_control = bool(ix.get("ramp_control"))
        had_far_end = bool(ix.get("ramp_far_end"))
        if had_control and had_far_end and not force:
            continue
        estimate = _exit_location(geom, float(ix.get("at_mi", 0.0)), leg_miles)
        (lat, lon), radius_m = _pinned_exit_location(ix, estimate, junction_refs or {})
        touched = False
        if force:
            # Re-judging: clear anything a previous run derived so a changed
            # verdict cannot leave a contradictory record behind. Reads are
            # re-derived below from the same evidence, so clearing them only
            # ever swaps them for equal or better provenance.
            if str(ix.get("ramp_control_source", "")).startswith("derived from ramp_far_end"):
                ix.pop("ramp_control", None)
                ix.pop("ramp_control_source", None)
            ix.pop("ramp_far_end", None)
            ix.pop("ramp_far_end_source", None)

        # -- walked topology first: it decides both the far end and where a
        # control could stand.
        far_end = ""
        terminal_kinds: set[str] = set()
        if topo is not None and (not had_far_end or force):
            # The gore sits at the junction itself, so the search is tighter
            # than the control radius by design.
            far_radius = (
                RAMP_FAR_END_NEAR_JUNCTION_M
                if radius_m == RAMP_CONTROL_NEAR_JUNCTION_M
                else RAMP_FAR_END_NEAR_GEOM_M
            )
            far_end, gores, terminal_ids = classify_exit_far_end(lat, lon, topo, far_radius)
            stats["exits"] = stats.get("exits", 0) + 1
            if not gores:
                stats["no_gore"] = stats.get("no_gore", 0) + 1
            if terminal_ids:
                terminal_kinds = controls_at_terminals(terminal_ids, topo)
                if "give_way" in terminal_kinds or "roundabout" in terminal_kinds:
                    stats["yieldish_terminals"] = stats.get("yieldish_terminals", 0) + 1

        # -- the control, best evidence first.
        wide_read = "motorway_link way at this exit" in str(ix.get("ramp_control_source", ""))
        precise = (
            "signal"
            if "signal" in terminal_kinds
            else "roundabout"
            if "roundabout" in terminal_kinds
            else "stop"
            if "stop" in terminal_kinds
            else "yield"
            if "give_way" in terminal_kinds
            else ""
        )
        if precise and (not ix.get("ramp_control") or force):
            if wide_read and ix.get("ramp_control") not in ("", precise, None):
                stats["wide_read_corrected"] = stats.get("wide_read_corrected", 0) + 1
            ix["ramp_control"] = precise
            ix["ramp_control_source"] = RAMP_CONTROL_TERMINAL_SOURCE
            stats["precise_reads"] = stats.get("precise_reads", 0) + 1
            touched = True
        elif not precise and far_end == "motorway" and force and wide_read:
            # An exit-wide match on a topology-proven merge with nothing at
            # any walked terminal: that is the neighbor's control. Drop it
            # and let the merge bake ``none`` below.
            ix.pop("ramp_control", None)
            ix.pop("ramp_control_source", None)
            stats["wide_read_dropped_at_merge"] = stats.get("wide_read_dropped_at_merge", 0) + 1
        elif not precise and not far_end and (not ix.get("ramp_control") or force):
            # The walk could not judge this exit; the exit-wide radius match
            # is the only read available and stays, contamination risk and
            # all -- it is still a real control nearby, and the alternative
            # is the dice.
            kinds = {
                kind
                for plat, plon, kind in points
                if _haversine_mi(lat, lon, plat, plon) * 1609.34 <= radius_m
            }
            control = "signal" if "signal" in kinds else "stop" if "stop" in kinds else ""
            if control:
                ix["ramp_control"] = control
                ix["ramp_control_source"] = RAMP_CONTROL_SOURCE
                stats["wide_reads"] = stats.get("wide_reads", 0) + 1
                touched = True

        # -- the far end, and the derived ``none`` it can carry.
        if far_end == "motorway" and ix.get("ramp_control") in ("signal", "stop"):
            # Still contradictory after the precise pass: a control read AT
            # a terminal of a proven merge, or a non-force run keeping an
            # old wide read. Trust the reading, bake no far end, count it.
            stats["contradictions"] = stats.get("contradictions", 0) + 1
        elif far_end:
            stats[f"far_{far_end}"] = stats.get(f"far_{far_end}", 0) + 1
            ix["ramp_far_end"] = far_end
            ix["ramp_far_end_source"] = RAMP_FAR_END_SOURCE
            touched = True
            if far_end == "motorway" and not ix.get("ramp_control"):
                ix["ramp_control"] = "none"
                ix["ramp_control_source"] = RAMP_CONTROL_NONE_SOURCE
                stats["none_baked"] = stats.get("none_baked", 0) + 1
        # Measure the signage guess the far end replaces: how often would
        # FREEWAY_VIA_RE's call have disagreed with walked topology?
        if far_end:
            via_says_freeway = bool(re.search(r"\bI[-\s]?\d", str(ix.get("via", "")).upper()))
            if via_says_freeway != (far_end == "motorway"):
                stats["via_disagrees"] = stats.get("via_disagrees", 0) + 1
        if touched:
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
            ix.get("ramp_control") and ix.get("ramp_far_end") for ix in corridor["interchanges"]
        ):
            # Done means a control AND a far-end verdict. Exits topology could
            # not judge (no gore in range) keep the leg eligible and are
            # re-walked on later runs, which costs a lookup and nothing else.
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
    topo = load_or_build_ramp_topo_index(
        pbf_paths, bounds, _ramp_topo_cache_path(pbf_paths), rebuild=args.rebuild_local_index
    )
    print(
        f"    using ramp topology: {topo['gore_count']:,} gores over "
        f"{topo['link_way_count']:,} link ways "
        f"({topo['untagged_oneway_ways']:,} untagged oneway, treated as "
        f"drawn-forward; {len(topo['toll']):,} toll booths, "
        f"{len(topo['give_way']):,} give-way nodes on ramp links)",
        flush=True,
    )
    junction_refs: dict[str, list[tuple[float, float]]] = {}
    if JUNCTION_INDEX_DEFAULT.exists():
        junction_refs = load_junction_ref_map(JUNCTION_INDEX_DEFAULT)

    stats: dict[str, int] = {}
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
                leg,
                points,
                args.rate_limit,
                force=args.force,
                junction_refs=junction_refs,
                topo=topo,
                stats=stats,
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
            save_world(data)
            print(f"    ...checkpointed the world source ({baked_legs} legs so far)", flush=True)

    print(
        f"\n{processed} legs processed, {baked_legs} touched, "
        f"{baked_total} interchanges given ramp controls or far ends."
    )
    examined = stats.get("exits", 0)
    if examined:
        # The loud accounting the provenance rule asks for: how much of this
        # bake is walked topology, how much is still nothing, and how often
        # the old signage guess it replaces would have called it wrong.
        motorway = stats.get("far_motorway", 0)
        surface = stats.get("far_surface", 0)
        print(
            f"Far-end topology over {examined:,} exits: "
            f"{motorway:,} merge onto a motorway "
            f"({stats.get('none_baked', 0):,} baked ramp_control=none, derived), "
            f"{surface:,} end at a surface road, "
            f"{stats.get('no_gore', 0):,} had no gore in range, "
            f"{examined - motorway - surface - stats.get('no_gore', 0):,} "
            "walked without a verdict (toll plaza or overrun)."
        )
        print(
            f"    Controls: {stats.get('precise_reads', 0):,} read at the "
            f"walked terminal ({stats.get('wide_read_corrected', 0):,} "
            "corrected a different exit-wide read), "
            f"{stats.get('wide_reads', 0):,} exit-wide fallback reads, "
            f"{stats.get('wide_read_dropped_at_merge', 0):,} exit-wide reads "
            "dropped as a neighbor's control at a proven merge."
        )
        print(
            f"    {stats.get('yieldish_terminals', 0):,} exits end at a "
            "give-way or roundabout terminal (baked as yield/roundabout "
            "where that outranked the other kinds present)."
        )
        print(
            f"    {stats.get('contradictions', 0):,} exits carry a READ "
            "signal/stop at a topology-proven merge (reading kept, no far "
            "end baked)."
        )
        judged = motorway + surface
        if judged:
            print(
                f"    The via-signage guess would have disagreed with walked "
                f"topology on {stats.get('via_disagrees', 0):,} of "
                f"{judged:,} judged exits "
                f"({100.0 * stats.get('via_disagrees', 0) / judged:.1f}%)."
            )
    if args.write and baked_legs:
        save_world(data)
        print(f"Wrote {WORLD_SOURCE_PATH}")
    elif not args.write:
        print("(dry run; pass --write to update the world source)")
    return 0


# --- Ramp far-end topology: whether the exit's ramps merge onto another ---
# --- motorway, walked from OSM link-way connectivity (ROADMAP 2026-08-20) ---
#
# OSM tags controls that exist and is silent where a ramp merges freely, so
# "no control" can never be read off a node. It CAN be read off topology: an
# exit whose every motorway_link chain ends by rejoining a highway=motorway
# way has nothing at its far end but a merge. That is baked as an explicit
# ``ramp_control: none`` (derived, and its source string says from what), and
# the far-end fact itself is baked as ``ramp_far_end`` so the runtime stops
# guessing free flow from `via` signage -- measured 34.9% wrong -- on exits
# whose ramps provably end at a surface road.
#
# The gore sits AT the junction, unlike the terminal control at the ramp's
# far end, so the match radii are much tighter than the control pass's.
RAMP_FAR_END_NEAR_JUNCTION_M = 500.0
RAMP_FAR_END_NEAR_GEOM_M = 1200.0
RAMP_TOPO_CACHE_VERSION = 4
RAMP_TOPO_WALK_CAP = 600  # visited nodes per gore; a real ramp complex is far smaller
# Ways that can meet a ramp at a node without being a road the ramp ends at:
# a marked footpath crossing a system ramp is not a terminal, and counting it
# as one turned real freeway-to-freeway merges into "surface" verdicts on the
# first national run. Vehicular service ways stay in -- a ramp meeting a
# frontage or access road at grade genuinely is a controllable terminal.
NON_VEHICULAR_HIGHWAYS = frozenset(
    (
        "footway",
        "cycleway",
        "path",
        "steps",
        "pedestrian",
        "bridleway",
        "corridor",
        "platform",
        "crossing",
        "elevator",
        "escape",
        "proposed",
        "construction",
        "abandoned",
        "razed",
    )
)
RAMP_FAR_END_SOURCE = (
    "derived: this exit's motorway_link chains walked from the gore in a "
    f"local Geofabrik extract, accessed {ACCESSED_DATE}. 'motorway' means "
    "every chain merges onto a highway=motorway way; 'surface' means at "
    "least one chain ends off the motorway network: "
    "https://www.openstreetmap.org/"
)
# A signal mapped per-approach sits within a few dozen meters of the
# intersection it controls; 120m keeps a wide arterial's far-side heads in
# range while staying an order of magnitude tighter than the exit-wide radii
# above, which is what let a neighbor's light bake onto a system interchange.
RAMP_TERMINAL_CONTROL_M = 120.0
RAMP_CONTROL_TERMINAL_SOURCE = (
    "OpenStreetMap highway=traffic_signals/highway=stop node within 120 m of "
    "the walked terminal node where this exit's ramp chain ends (read; the "
    "walk supplies the node, the tag supplies the control), from a local "
    f"Geofabrik extract, accessed {ACCESSED_DATE}: https://www.openstreetmap.org/"
)
RAMP_CONTROL_NONE_SOURCE = (
    "derived from ramp_far_end=motorway: every exit-ramp chain merges onto "
    "another motorway, so nothing stops traffic at the far end. Free flow is "
    "inferred from read OSM link topology, not from a tag -- OSM does not "
    f"tag the absence of a control. Geofabrik extract accessed {ACCESSED_DATE}"
)


def build_ramp_link_graph(
    link_ways: list[tuple[list[int], str]],
    motorway_node_ids: set[int],
    trunk_node_ids: set[int] | None = None,
    crossroad_node_ids: set[int] | None = None,
) -> dict[str, Any]:
    """Directed ramp-link graph from motorway_link ways.

    ``link_ways`` is (node id list, oneway tag value) per way. oneway is not
    implied on motorway_link, but ramps are overwhelmingly drawn in travel
    direction even when the tag is missing, so an untagged way is treated as
    forward and counted so the report can say how much rests on that.

    ``crossroad_node_ids`` are link nodes shared with any road that is not a
    motorway or another link -- the at-grade touch points where a control can
    stand. Without them the walk sails THROUGH a diamond's crossroad
    intersection onto the on-ramp and back to the mainline, and a plain
    service exit reads as a system merge (caught on the first smoke leg:
    every diamond whose off-ramp and on-ramp share the intersection node).

    Membership sets are intersected down to link nodes: the walk only ever
    asks "is this LINK node also on a motorway/trunk/crossroad way"."""
    out_edges: dict[int, list[int]] = {}
    link_nodes: set[int] = set()
    untagged = 0
    for node_ids, oneway in link_ways:
        ids = [int(n) for n in node_ids]
        if len(ids) < 2:
            continue
        link_nodes.update(ids)
        ow = (oneway or "").strip().lower()
        pairs = list(zip(ids, ids[1:], strict=False))
        if ow in ("-1", "reverse"):
            pairs = [(b, a) for a, b in pairs]
        elif ow in ("no", "false", "0"):
            pairs = pairs + [(b, a) for a, b in pairs]
        elif ow not in ("yes", "true", "1"):
            untagged += 1
        for a, b in pairs:
            out_edges.setdefault(a, []).append(b)
    mainline = link_nodes & set(motorway_node_ids)
    trunk = link_nodes & set(trunk_node_ids or ())
    crossroad = (link_nodes & set(crossroad_node_ids or ())) - mainline
    # A gore: a link node ON the mainline with a link edge leaving it. An
    # on-ramp's merge point is also on the mainline but has only an INBOUND
    # link edge, so requiring an out-edge keeps entrances out of the set.
    gores = sorted(n for n in mainline if out_edges.get(n))
    return {
        "out": out_edges,
        "mainline": mainline,
        "trunk": trunk,
        "crossroad": crossroad,
        "gores": gores,
        "untagged_oneway_ways": untagged,
    }


def walk_far_ends(
    graph: dict[str, Any], start: int, toll_nodes: set[int] | frozenset[int] = frozenset()
) -> tuple[set[str], bool, set[int]]:
    """(terminal kinds, passed a toll booth, off-motorway terminal node ids)
    for every chain leaving a gore. The terminal ids are where the chains
    actually end off the mainline -- the nodes a terminal control stands at,
    which is what lets controls be read precisely instead of exit-wide.

    Terminals: ``motorway`` (the chain rejoins a mainline node -- a merge),
    ``crossroad`` (the chain touches a node shared with a surface road -- an
    at-grade meeting where a control can stand; the walk stops there rather
    than sailing through a diamond's intersection onto the on-ramp),
    ``trunk`` (ends on a trunk way; free flow is LIKELY but trunks carry
    signals too, so it is not treated as one), ``road-end`` (the link data
    ends off the motorway network -- a surface terminal the crossroad set
    did not carry, or a data edge; either way, not a proven merge),
    ``overrun`` (walk cap hit)."""
    out = graph["out"]
    mainline = graph["mainline"]
    trunk = graph["trunk"]
    crossroad = graph.get("crossroad", frozenset())
    seen = {start}
    frontier = [start]
    terminals: set[str] = set()
    terminal_nodes: set[int] = set()
    tolled = False
    steps = 0
    while frontier:
        node = frontier.pop()
        for nxt in out.get(node, ()):
            if nxt in seen:
                continue
            seen.add(nxt)
            steps += 1
            if steps > RAMP_TOPO_WALK_CAP:
                terminals.add("overrun")
                return terminals, tolled, terminal_nodes
            if nxt in toll_nodes:
                tolled = True
            if nxt in mainline:
                terminals.add("motorway")
                continue
            if nxt in crossroad:
                terminals.add("trunk" if nxt in trunk else "crossroad")
                terminal_nodes.add(nxt)
                continue
            if not out.get(nxt):
                terminals.add("trunk" if nxt in trunk else "road-end")
                terminal_nodes.add(nxt)
                continue
            frontier.append(nxt)
    if not terminals:
        terminals.add("road-end")
        terminal_nodes.add(start)
    return terminals, tolled, terminal_nodes


def classify_gore(terminals: set[str], tolled: bool) -> str:
    """One gore's verdict: ``motorway``, ``surface``, or ``""`` (no call).

    A toll plaza on an all-motorway chain vetoes free flow -- conventional
    booths stop every truck -- and an overrun walk proves nothing."""
    if "overrun" in terminals:
        return ""
    if terminals == {"motorway"}:
        return "" if tolled else "motorway"
    return "surface"


def _gore_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Local haversine so the pure topology half of this module imports and
    # tests standalone, without build_interchanges wiring its globals in.
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = rlat2 - rlat1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a)) * 1609.34


class _GoreGrid:
    """0.1-degree bucket index over (lat, lon, payload) points; radii here
    are under 1.3 km so a 3x3 neighborhood always covers the search circle.
    ``near`` returns the payloads -- gore node ids in the gore grid, control
    kinds in the control grid."""

    def __init__(self, points: list[tuple[float, float, Any]]) -> None:
        self.cells: dict[tuple[int, int], list[tuple[float, float, int]]] = {}
        for lat, lon, node_id in points:
            self.cells.setdefault((int(lat * 10), int(lon * 10)), []).append((lat, lon, node_id))

    def near(self, lat: float, lon: float, radius_m: float) -> list[int]:
        clat, clon = int(lat * 10), int(lon * 10)
        found: list[int] = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for plat, plon, node_id in self.cells.get((clat + dy, clon + dx), ()):
                    if _gore_distance_m(lat, lon, plat, plon) <= radius_m:
                        found.append(node_id)
        return found


def classify_exit_far_end(
    lat: float, lon: float, topo: dict[str, Any], radius_m: float
) -> tuple[str, int, set[int]]:
    """(far end, gores found, off-motorway terminal node ids) for the exit
    at a location.

    ``surface`` wins over ``motorway``: one ramp chain ending at a surface
    road means the interchange has a controlled or controllable terminal,
    whatever its other ramps do. ``motorway`` needs every gore in range to
    walk clean. Gores from the opposite carriageway land in range too; at a
    pure system interchange they are also merges, and at a service
    interchange they also end at the crossroad, so they push the verdict the
    right way in both shapes."""
    gore_ids = topo["grid"].near(lat, lon, radius_m)
    if not gore_ids:
        return "", 0, set()
    verdicts = set()
    terminal_ids: set[int] = set()
    for gore in gore_ids:
        terminals, tolled, ends = walk_far_ends(topo["graph"], gore, topo["toll"])
        verdicts.add(classify_gore(terminals, tolled))
        terminal_ids |= ends
    if "surface" in verdicts:
        return "surface", len(gore_ids), terminal_ids
    if verdicts == {"motorway"}:
        return "motorway", len(gore_ids), terminal_ids
    return "", len(gore_ids), terminal_ids


def controls_at_terminals(
    terminal_ids: set[int], topo: dict[str, Any], radius_m: float = RAMP_TERMINAL_CONTROL_M
) -> set[str]:
    """Control kinds tagged within ``radius_m`` of any walked terminal node.

    This is the precise read: the walk supplies WHERE the ramp actually ends,
    so a control is only accepted standing at that spot -- including signals
    mapped per-approach on the crossroad way. Kinds: ``signal``, ``stop``,
    ``give_way``, plus ``roundabout`` when the terminal node sits on a
    junction=roundabout way."""
    kinds: set[str] = set()
    for tid in terminal_ids:
        loc = topo["terminal_locs"].get(tid)
        if loc is not None:
            kinds.update(topo["control_grid"].near(loc[0], loc[1], radius_m))
        if tid in topo["roundabout"]:
            kinds.add("roundabout")
    return kinds


def _build_ramp_topo_from_pbf(
    pbf_path: Path, bounds: list[LocalBounds], label: str = "1/1"
) -> dict[str, Any]:
    """One extract's pruned ramp topology: three filtered passes.

    Ways first (link ways + mainline/trunk membership), then tagged nodes
    (toll booths, give-way, for the veto and the report), then gore-candidate
    node locations by id -- and finally the graph is pruned to what the
    in-bounds gores can actually reach, so the cache stays small."""
    try:
        import osmium  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Reading --pbf requires the tooling dependency group: "
            "uv sync --group dev --group tooling"
        ) from exc

    progress = _LocalIndexProgress(f"PBF {label} ramp topology", LOCAL_INDEX_PROGRESS_INTERVAL_SEC)

    class WayHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
        def __init__(self) -> None:
            super().__init__()
            self.link_ways: list[tuple[list[int], str]] = []
            self.motorway_nodes: set[int] = set()
            self.trunk_nodes: set[int] = set()
            self.ways_seen = 0

        def way(self, way: Any) -> None:
            self.ways_seen += 1
            progress.maybe(f"{self.ways_seen:,} ways; {len(self.link_ways):,} link ways")
            tags = {str(k): str(v) for k, v in way.tags}
            highway = tags.get("highway")
            refs = [
                int(node_ref.ref)
                for node_ref in way.nodes
                if getattr(node_ref, "ref", None) is not None
            ]
            if highway == "motorway_link":
                self.link_ways.append((refs, tags.get("oneway", "")))
            elif highway == "motorway":
                self.motorway_nodes.update(refs)
            elif highway == "trunk":
                self.trunk_nodes.update(refs)

    ways = WayHandler()
    print(f"    reading ramp topology from PBF {label}: {pbf_path}", flush=True)
    ways.apply_file(
        str(pbf_path),
        filters=[
            osmium.filter.EntityFilter(osmium.osm.WAY),
            osmium.filter.TagFilter(
                ("highway", "motorway_link"),
                ("highway", "motorway"),
                ("highway", "trunk"),
            ),
        ],
    )
    link_node_ids: set[int] = set()
    for refs, _ in ways.link_ways:
        link_node_ids.update(refs)

    class CrossroadHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
        """Link nodes shared with any road that is not the motorway network:
        the at-grade points where a ramp actually meets the surface street.
        Scans every highway way, so it keeps only the intersection with the
        already-known link nodes."""

        def __init__(self) -> None:
            super().__init__()
            self.crossroad: set[int] = set()
            self.roundabout: set[int] = set()
            self.ways_seen = 0

        def way(self, way: Any) -> None:
            self.ways_seen += 1
            progress.maybe(f"crossroads: {self.ways_seen:,} ways; {len(self.crossroad):,} nodes")
            highway = ""
            roundabout = False
            for k, v in way.tags:
                key = str(k)
                if key == "highway":
                    highway = str(v)
                elif key == "junction" and str(v) in ("roundabout", "circular"):
                    roundabout = True
            if highway in ("motorway", "motorway_link") or highway in NON_VEHICULAR_HIGHWAYS:
                return
            for node_ref in way.nodes:
                ref = getattr(node_ref, "ref", None)
                if ref is not None and int(ref) in link_node_ids:
                    self.crossroad.add(int(ref))
                    if roundabout:
                        self.roundabout.add(int(ref))

    crossings = CrossroadHandler()
    crossings.apply_file(
        str(pbf_path),
        filters=[
            osmium.filter.EntityFilter(osmium.osm.WAY),
            osmium.filter.KeyFilter("highway"),
        ],
    )
    graph = build_ramp_link_graph(
        ways.link_ways, ways.motorway_nodes, ways.trunk_nodes, crossings.crossroad
    )

    class TaggedNodeHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
        """Toll booths and give-way by id (the walk needs membership), plus
        signal/stop/give-way LOCATIONS so controls can later be read within
        RAMP_TERMINAL_CONTROL_M of a walked terminal node -- including the
        per-approach signals mapped on the crossroad way, which link-way
        membership can never see."""

        def __init__(self) -> None:
            super().__init__()
            self.toll: set[int] = set()
            self.give_way: set[int] = set()
            self.control_points: list[tuple[float, float, str]] = []

        def node(self, node: Any) -> None:
            tags = {str(k): str(v) for k, v in node.tags}
            if tags.get("barrier") == "toll_booth":
                self.toll.add(int(node.id))
                return
            highway = tags.get("highway")
            if highway == "give_way":
                self.give_way.add(int(node.id))
            if highway not in ("traffic_signals", "stop", "give_way"):
                return
            if tags.get("traffic_signals") == "ramp_meter":
                return
            if not node.location.valid():
                return
            lat = float(node.location.lat)
            lon = float(node.location.lon)
            if not _inside_any_bounds(lat, lon, bounds):
                return
            kind = {"traffic_signals": "signal", "stop": "stop", "give_way": "give_way"}[highway]
            self.control_points.append((lat, lon, kind))

    tagged = TaggedNodeHandler()
    tagged.apply_file(
        str(pbf_path),
        filters=[
            osmium.filter.EntityFilter(osmium.osm.NODE),
            osmium.filter.TagFilter(
                ("barrier", "toll_booth"),
                ("highway", "give_way"),
                ("highway", "traffic_signals"),
                ("highway", "stop"),
            ),
        ],
    )

    gore_points: list[tuple[float, float, int]] = []
    if graph["gores"]:

        class GoreLocationHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
            def node(self, node: Any) -> None:
                if not node.location.valid():
                    return
                lat = float(node.location.lat)
                lon = float(node.location.lon)
                if _inside_any_bounds(lat, lon, bounds):
                    gore_points.append((lat, lon, int(node.id)))

        GoreLocationHandler().apply_file(
            str(pbf_path),
            filters=[
                osmium.filter.EntityFilter(osmium.osm.NODE),
                osmium.filter.IdFilter(graph["gores"]),
            ],
        )

    # Prune to what the in-bounds gores can reach: the cache carries exactly
    # the walkable subgraph, not a whole state's link network.
    reachable: set[int] = set()
    for _, _, gore in gore_points:
        if gore in reachable:
            continue
        seen = {gore}
        frontier = [gore]
        steps = 0
        while frontier and steps <= RAMP_TOPO_WALK_CAP * 4:
            node = frontier.pop()
            for nxt in graph["out"].get(node, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    steps += 1
                    if nxt not in graph["mainline"] and nxt not in graph["crossroad"]:
                        frontier.append(nxt)
        reachable |= seen
    out_pruned = {n: targets for n, targets in graph["out"].items() if n in reachable}
    # Locations for the walkable terminal candidates: crossroad touches and
    # dead ends. These are where walked chains stop, so a control read wants
    # their coordinates.
    terminal_candidates = {
        n for n in reachable if n in graph["crossroad"] or not graph["out"].get(n)
    }
    terminal_locs: dict[int, tuple[float, float]] = {}
    if terminal_candidates:

        class TerminalLocationHandler(osmium.SimpleHandler):  # type: ignore[name-defined]
            def node(self, node: Any) -> None:
                if node.location.valid():
                    terminal_locs[int(node.id)] = (
                        float(node.location.lat),
                        float(node.location.lon),
                    )

        TerminalLocationHandler().apply_file(
            str(pbf_path),
            filters=[
                osmium.filter.EntityFilter(osmium.osm.NODE),
                osmium.filter.IdFilter(sorted(terminal_candidates)),
            ],
        )
    print(
        f"    retained {len(gore_points):,} in-bounds gores, "
        f"{len(out_pruned):,} graph nodes "
        f"(of {len(ways.link_ways):,} link ways; "
        f"{graph['untagged_oneway_ways']:,} untagged oneway), {label}",
        flush=True,
    )
    return {
        "out": out_pruned,
        "mainline": sorted(graph["mainline"] & reachable),
        "trunk": sorted(graph["trunk"] & reachable),
        "crossroad": sorted(graph["crossroad"] & reachable),
        "roundabout": sorted(crossings.roundabout & reachable),
        "toll": sorted(tagged.toll & reachable),
        "give_way": sorted(tagged.give_way & reachable),
        "control_points": tagged.control_points,
        "terminal_locs": {str(k): v for k, v in terminal_locs.items()},
        "gores": gore_points,
        "untagged_oneway_ways": graph["untagged_oneway_ways"],
        "link_way_count": len(ways.link_ways),
    }


def _ramp_topo_cache_path(pbf_paths: list[Path]) -> Path:
    if len(pbf_paths) == 1:
        name = pbf_paths[0].name
        for suffix in (".osm.pbf", ".pbf"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return pbf_paths[0].with_name(f"{name}.ramptopo.json")
    return pbf_paths[0].with_name("freight-fate-ramptopo.json")


def load_or_build_ramp_topo_index(
    pbf_paths: list[Path],
    bounds: list[LocalBounds],
    cache_path: Path,
    rebuild: bool = False,
) -> dict[str, Any]:
    """Merged, walk-ready topology across the extracts, cached like the
    control-node index. Node ids are globally unique so merging is a union."""
    merged: dict[str, Any] | None = None
    if not rebuild and cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if (
            payload is not None
            and payload.get("version") == RAMP_TOPO_CACHE_VERSION
            and payload.get("pbfs") == _pbf_set_metadata(pbf_paths)
            and payload.get("bounds_digest") == _bounds_digest(bounds)
        ):
            merged = payload["topo"]
            print(
                f"Loaded ramp-topology cache: {cache_path} ({len(merged['gores']):,} gores)",
                flush=True,
            )
    if merged is None:
        merged = {
            "out": {},
            "mainline": [],
            "trunk": [],
            "crossroad": [],
            "roundabout": [],
            "toll": [],
            "give_way": [],
            "control_points": [],
            "terminal_locs": {},
            "gores": [],
            "untagged_oneway_ways": 0,
            "link_way_count": 0,
        }
        for i, pbf_path in enumerate(pbf_paths, start=1):
            part = _build_ramp_topo_from_pbf(pbf_path, bounds, label=f"{i}/{len(pbf_paths)}")
            merged["out"].update({str(k): v for k, v in part["out"].items()})
            merged["terminal_locs"].update(part["terminal_locs"])
            for key in (
                "mainline",
                "trunk",
                "crossroad",
                "roundabout",
                "toll",
                "give_way",
                "control_points",
                "gores",
            ):
                merged[key].extend(part[key])
            merged["untagged_oneway_ways"] += part["untagged_oneway_ways"]
            merged["link_way_count"] += part["link_way_count"]
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "version": RAMP_TOPO_CACHE_VERSION,
                    "pbfs": _pbf_set_metadata(pbf_paths),
                    "bounds_digest": _bounds_digest(bounds),
                    "topo": merged,
                }
            )
            + "\n",
            encoding="utf-8",
        )
    # Walk-ready shape: int keys, sets, and the spatial grid.
    return {
        "graph": {
            "out": {int(k): v for k, v in merged["out"].items()},
            "mainline": set(merged["mainline"]),
            "trunk": set(merged["trunk"]),
            "crossroad": set(merged["crossroad"]),
        },
        "toll": set(merged["toll"]),
        "give_way": set(merged["give_way"]),
        "roundabout": set(merged["roundabout"]),
        "control_grid": _GoreGrid([(c[0], c[1], str(c[2])) for c in merged["control_points"]]),
        "terminal_locs": {int(k): (v[0], v[1]) for k, v in merged["terminal_locs"].items()},
        "grid": _GoreGrid([(p[0], p[1], int(p[2])) for p in merged["gores"]]),
        "untagged_oneway_ways": merged["untagged_oneway_ways"],
        "link_way_count": merged["link_way_count"],
        "gore_count": len(merged["gores"]),
    }


__all__ = [name for name in globals() if not name.startswith("__")]
