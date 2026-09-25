"""What a facility street chain knows about each street, beyond its name.

Build-time only, used by ``build_local_geometry`` while it routes and by
``build_facility_approaches`` while it writes. Owner order, 2026-09-24: the
streets from the ramp end to the facility made realistic. This module owns
the data half of that; the driving half reads what it writes.

Four facts, each labelled with the kind of value it is:

* **Posted limit per street.** ``read`` where OpenStreetMap tags a
  ``maxspeed`` on most of the street's miles; ``statutory`` where it does not
  and the state's vehicle code sets a default for unposted district streets
  (``data/street_limits.json``, the same rule as the game's
  ``StreetLimits::statutory_mph``); ``assumed`` where neither holds -- the old
  25 for a named street and 15 for an unnamed one, which nothing stands
  behind. A mapped 25 and a filled-in 25 are no longer the same record.
* **Traffic control at each intersection the chain passes.** READ from OSM
  ``highway=traffic_signals|stop|give_way`` nodes (``stop=all`` for an
  all-way stop, ``direction`` / ``traffic_signals:direction`` where tagged).
  Where OSM is silent there is no entry: silence is never filled in here.
* **The driveway.** Where the chain leaves the public street for the
  facility's own way: the first node of its final run of ``highway=service``
  or private ways. OSM does not map property lines, so this is derived from
  road class, and absent when the chain ends on a public street.
* **The ramp terminal a chain starts at** (``exit_terminals``): see
  ``build_facility_approaches``.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STREET_LIMITS_PATH = ROOT / "data" / "street_limits.json"

# Precedence where one intersection carries more than one kind: the strongest
# control governs (the ramp-terminal bake uses the same order).
CONTROL_PRECEDENCE = ("signal", "all_way_stop", "stop", "give_way")
# Kinds that bind every approach, so a head mapped for the opposing
# direction still tells us the intersection is controlled.
ALL_APPROACH_KINDS = frozenset({"signal", "all_way_stop"})

LIMIT_READ = "read"
LIMIT_STATUTORY = "statutory"
LIMIT_ASSUMED = "assumed"

DRIVEWAY_SOURCE = (
    "derived from OpenStreetMap road class: the first node of the chain's final "
    "run of highway=service or access=private ways; no property line is mapped"
)
CONTROLS_SOURCE = (
    "read from OpenStreetMap highway=traffic_signals, highway=stop (stop=all "
    "for all-way) and highway=give_way nodes on the chain's own path. A node "
    "on an intersection binds it; a node between two intersections binds the "
    "one it faces (direction tag where present, else the nearer one). Where "
    "OpenStreetMap is silent there is no entry."
)


def street_sources(max_spoken_segments: int) -> dict[str, str]:
    """What each street field is, for the layer's ``generated`` block."""
    return {
        "limit": (
            "Per segment: read = OpenStreetMap maxspeed on most of the street's "
            "miles. Otherwise limit_basis says which statute governs, judged at "
            "each edge's midpoint by the boundary the state's code keys on "
            "(tools/census_boundaries.py: Census 2020 Urban Areas as the stand-in "
            "for a frontage-density district, incorporated places for corporate "
            "limits): town -> the state's in-town district default (statutory), "
            "or 25 named / 15 unnamed where the code sets none (assumed); rural "
            "-> the state's default for an unposted road outside town, numbered "
            "highway or local road by OSM class (statutory), or the table's "
            "median rural figure where the code sets none (assumed). Past the "
            "driveway no statute reaches: assumed 25/15, no basis. Citations in "
            "data/street_limits.json."
        ),
        "controls": CONTROLS_SOURCE,
        "driveway": DRIVEWAY_SOURCE,
        "exit_chains": (
            "One chain per ramp terminal a delivery into the city can arrive at: "
            "on each leg ending at the city, the labelled exit nearest that end "
            "(the game's own destination-exit rule), its ramp_terminal node "
            "(read) as the start. Kept whole; the default chain alone is cut to "
            f"the last {max_spoken_segments} streets."
        ),
    }


def control_of(tags: dict[str, str]) -> tuple[str, str] | None:
    """``(kind, direction)`` for an OSM control node, or None.

    ``direction`` is ``forward``/``backward`` (relative to the way the node
    sits on) or ``""`` when untagged or given as a compass bearing."""
    highway = tags.get("highway", "")
    if highway == "traffic_signals":
        kind = "signal"
        direction = tags.get("traffic_signals:direction") or tags.get("direction", "")
    elif highway == "stop":
        kind = "all_way_stop" if tags.get("stop", "").strip().lower() == "all" else "stop"
        direction = tags.get("direction", "")
    elif highway == "give_way":
        kind = "give_way"
        direction = tags.get("direction", "")
    else:
        return None
    direction = direction.strip().lower()
    return kind, direction if direction in ("forward", "backward") else ""


def statutory_mph(state: str, limits: dict[str, Any] | None = None) -> float | None:
    """The state's default for an unposted district street, or None.

    A port of ``StreetLimits::statutory_mph`` + ``facility_street_mph`` in
    ``ff-core``: verified rows only, none where the figures bind only once
    signs are posted, then business, urban, residence in that order. A Rust
    test holds every baked ``statutory`` value to the game's own answer."""
    rows = limits if limits is not None else _street_limits()
    row = rows.get(state.strip())
    if not row or not row.get("verified") or row.get("signs_required"):
        return None
    for key in ("business_mph", "urban_mph", "residence_mph"):
        if row.get(key) is not None:
            return float(row[key])
    return None


# Where a statutory or assumed fill applies, which of the state's two
# statutory figures governs the street: the in-town district default, or
# the default for an unposted road outside town (``limit_basis``).
BASIS_TOWN = "town"
BASIS_RURAL = "rural"
# OSM classes standing in for a state or US numbered highway, where a code
# sets a different rural default for those than for county roads. DERIVED:
# OSM classes by function, the codes by who maintains the road.
MAJOR_HIGHWAYS = frozenset(
    ("trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link")
)


def rural_mph(state: str, highway: bool, limits: dict[str, Any] | None = None) -> tuple[float, str]:
    """``(mph, kind)`` for an unposted road outside town: the state's rural
    statutory default (``statutory``) for a numbered highway or a local road,
    or, where the code has none or it is unconfirmed, the table's median
    rural default (``assumed``; see ``assumed_rural_mph``)."""
    rows = limits if limits is not None else _street_limits()
    rural = (rows.get(state.strip()) or {}).get("rural") or {}
    value = rural.get("highway_mph" if highway else "local_mph")
    if rural.get("verified") and not rural.get("signs_required") and value is not None:
        return float(value), LIMIT_STATUTORY
    return assumed_rural_mph(rows), LIMIT_ASSUMED


def assumed_rural_mph(limits: dict[str, Any] | None = None) -> float:
    """The fill for a state whose code sets no rural default: the median of
    every confirmed state's rural local-road figure. DERIVED from the table,
    so it moves if the table does, and it is always labelled ``assumed``."""
    rows = limits if limits is not None else _street_limits()
    values = sorted(
        float(row["rural"]["local_mph"])
        for row in rows.values()
        if (row.get("rural") or {}).get("verified") and row["rural"].get("local_mph") is not None
    )
    return values[len(values) // 2] if values else 55.0


def town_basis(state: str, limits: dict[str, Any] | None = None) -> str:
    """Which boundary the state's in-town default keys on: ``municipal``
    (corporate limits) or ``urban_area`` (a density-defined district)."""
    rows = limits if limits is not None else _street_limits()
    return (rows.get(state.strip()) or {}).get("town_basis") or "urban_area"


def _street_setting(
    state: str,
    coords: list[tuple[float, float]],
    edge_miles: list[float],
    edges: range,
    major_edges: Any,
    path_nodes: list[int],
    limits: dict[str, Any],
    in_town: TownJudge,
) -> tuple[float, float, float]:
    """(miles in town, miles outside, miles on a numbered highway) over a
    street's edges, each judged at its midpoint."""
    kind = town_basis(state, limits)
    town = rural = major = 0.0
    for e in edges:
        lat = round((coords[e][0] + coords[e + 1][0]) / 2, 4)
        lon = round((coords[e][1] + coords[e + 1][1]) / 2, 4)
        if in_town(kind, lat, lon):
            town += edge_miles[e]
        else:
            rural += edge_miles[e]
            if (path_nodes[e], path_nodes[e + 1]) in major_edges:
                major += edge_miles[e]
    return town, rural, major


# Is a point in town? ``(kind, lat, lon) -> bool``, ``kind`` being the
# boundary the state's code keys on (``town_basis``). Every street-detail
# bake is handed one: the real bake builds it from the Census files
# (``census_town_judge``); tests hand in a fixture judge.
TownJudge = Callable[[str, float, float], bool]


def census_town_judge() -> TownJudge:
    """The real bake's judge, from the Census boundaries. Refuses loudly
    without them: a street limit cannot be judged in town or out, and a bake
    that guessed would ship statutory numbers under the wrong statute."""
    import census_boundaries

    if not census_boundaries.available():
        raise SystemExit(
            "The Census boundaries are missing; see tools/census_boundaries.py for the "
            "two files and where they go. A street limit cannot be judged in town or "
            "out without them."
        )
    return census_boundaries.in_town


_LIMITS_CACHE: dict[str, Any] | None = None


def _street_limits() -> dict[str, Any]:
    global _LIMITS_CACHE
    if _LIMITS_CACHE is None:
        _LIMITS_CACHE = json.loads(STREET_LIMITS_PATH.read_text(encoding="utf-8"))["limits"]
    return _LIMITS_CACHE


def annotate(
    segments: list[dict[str, Any]],
    path_nodes: list[int],
    coords: list[tuple[float, float]],
    edge_miles: list[float],
    edge_kinds: list[str],
    forward: set[tuple[int, int]],
    controls: dict[int, tuple[str, str]],
    street_deg: dict[int, int],
    state: str,
    major_edges: set[tuple[int, int]] | frozenset[tuple[int, int]] = frozenset(),
    *,
    town_judge: TownJudge,
) -> tuple[dict[str, Any] | None, dict[str, int]]:
    """Fill ``limit_mph``/``limit_source``/``controls`` on each segment, in
    place, and return ``(driveway, counts)``.

    ``segments`` are ``collapse_segments`` output with its private edge keys
    (``_first_edge``, ``_end_edge``, ``_raw_miles``, ``_read_miles``), which
    this strips. ``edge_kinds`` says per path edge ``street``, ``service`` or
    ``private``; ``forward`` holds the edges drawn in their way's node order;
    ``street_deg`` counts the non-service ways meeting at a node."""
    n = len(path_nodes) - 1
    driveway_edge = _driveway_edge(edge_kinds)
    boundaries = {seg["_first_edge"] for seg in segments[1:]}
    junctions = sorted(
        {k for k in range(1, n) if street_deg.get(path_nodes[k], 0) >= 3} | boundaries
    )
    counts = {
        "intersections": len(junctions),
        "controlled": 0,
        "ambiguous": 0,
        "conflicts": 0,
        # Edges on a public street (not service, not private): zero is a ramp
        # that leads straight into a lot.
        "street_edges": edge_kinds.count("street"),
    }
    kinds_at: dict[int, set[str]] = defaultdict(set)
    along = [0.0]
    for miles in edge_miles:
        along.append(along[-1] + miles)
    junction_set = set(junctions)
    for k in range(1, n):
        found = controls.get(path_nodes[k])
        if found is None:
            continue
        kind, direction = found
        faces = None
        if direction:
            faces = (direction == "forward") == ((path_nodes[k - 1], path_nodes[k]) in forward)
        if k in junction_set:
            if kind in ALL_APPROACH_KINDS or faces:
                kinds_at[k].add(kind)
            elif faces is None:
                # A stop or give-way drawn on the intersection node itself
                # with no direction: which approach it binds is not stated.
                counts["ambiguous"] += 1
            continue
        ahead = next((j for j in junctions if j > k), None)
        behind = next((j for j in reversed(junctions) if j < k), None)
        if faces is None:
            to_ahead = along[ahead] - along[k] if ahead is not None else float("inf")
            to_behind = along[k] - along[behind] if behind is not None else float("inf")
            faces = to_ahead <= to_behind
        target = ahead if faces else (behind if kind in ALL_APPROACH_KINDS else None)
        if target is not None:
            kinds_at[target].add(kind)
    chosen: dict[int, str] = {}
    for k, kinds in kinds_at.items():
        chosen[k] = next(kind for kind in CONTROL_PRECEDENCE if kind in kinds)
        if "signal" in kinds and len(kinds) > 1:
            counts["conflicts"] += 1
    counts["controlled"] = len(chosen)

    limits = _street_limits()
    town_fill = statutory_mph(state, limits)
    counts["crosses_town_line"] = 0
    offset = 0.0
    driveway: dict[str, Any] | None = None
    for i, seg in enumerate(segments):
        first, end = seg.pop("_first_edge"), seg.pop("_end_edge")
        raw, read = seg.pop("_raw_miles"), seg.pop("_read_miles")
        past_driveway = driveway_edge is not None and first >= driveway_edge
        if read > 0 and read * 2 >= raw:
            seg["limit_mph"], seg["limit_source"] = seg["speed_mph"], LIMIT_READ
        elif past_driveway:
            seg["limit_mph"], seg["limit_source"] = seg["speed_mph"], LIMIT_ASSUMED
        else:
            town, rural, major = _street_setting(
                state,
                coords,
                edge_miles,
                range(first, end),
                major_edges,
                path_nodes,
                limits,
                town_judge,
            )
            counts["crosses_town_line"] += 1 if town and rural else 0
            if town >= rural:
                seg["limit_basis"] = BASIS_TOWN
                if town_fill is not None:
                    seg["limit_mph"], seg["limit_source"] = town_fill, LIMIT_STATUTORY
                else:
                    seg["limit_mph"], seg["limit_source"] = seg["speed_mph"], LIMIT_ASSUMED
            else:
                seg["limit_basis"] = BASIS_RURAL
                mph, source = rural_mph(state, major * 2 >= rural, limits)
                seg["limit_mph"], seg["limit_source"] = mph, source
        entries = []
        for k in junctions:
            if k in chosen and (first < k < end or (i and k == first)):
                entries.append(
                    {"at_mi": _clip(along[k] - along[first], seg["miles"]), "kind": chosen[k]}
                )
        seg["controls"] = entries
        if driveway_edge is not None and driveway is None and first <= driveway_edge < end:
            driveway = {
                "at_mi": round(
                    offset + _clip(along[driveway_edge] - along[first], seg["miles"]), 2
                ),
                "node": int(path_nodes[driveway_edge]),
                "lat": round(coords[driveway_edge][0], 7),
                "lon": round(coords[driveway_edge][1], 7),
                "kind": "private_road"
                if edge_kinds[driveway_edge] == "private"
                else "service_road",
                "source": DRIVEWAY_SOURCE,
            }
        offset += seg["miles"]
    return driveway, counts


def _clip(miles: float, segment_miles: float) -> float:
    return round(min(max(miles, 0.0), segment_miles), 2)


def _driveway_edge(edge_kinds: list[str]) -> int | None:
    """Index of the first edge of the trailing non-street run, when a public
    street comes before it."""
    j = len(edge_kinds)
    while j > 0 and edge_kinds[j - 1] != "street":
        j -= 1
    return j if 0 < j < len(edge_kinds) else None


def street_coverage(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The loud accounting for the layer meta, recomputed from the records so
    a merged file always describes itself: per chain family, how many miles
    of each limit kind, how many corners and intersections carry a READ
    control, how many chains have a driveway, and what the screens counted.
    A turn-level chain with no ``limit_source`` predates this bake."""

    def block() -> dict[str, Any]:
        return {
            "chains": 0,
            "chains_unmeasured": 0,
            "unmeasured_why": {},
            # Kept chains whose path was read back off the map by their own
            # street names and miles (chain_match.py), not re-routed.
            "chains_matched_to_osm": 0,
            "limit_miles": {LIMIT_READ: 0.0, LIMIT_STATUTORY: 0.0, LIMIT_ASSUMED: 0.0},
            # Filled limits by which statute governed (limit_basis).
            "fill_miles_by_basis": {},
            # Miles at each posted number, read or filled.
            "limit_mph_miles": {},
            "screen_read_limit_not_multiple_of_5": 0,
            "segments_crossing_town_line": 0,
            "turns": 0,
            "turns_with_control": 0,
            "controls_by_kind": {kind: 0 for kind in CONTROL_PRECEDENCE},
            "intersections": 0,
            "intersections_with_control": 0,
            "screen_ambiguous_stop_on_intersection_node": 0,
            "screen_signal_and_sign_at_one_intersection": 0,
            "driveways": 0,
        }

    def add(out: dict[str, Any], chain: dict[str, Any]) -> None:
        segments = chain.get("segments") or []
        out["chains"] += 1
        if not any("limit_source" in seg for seg in segments):
            out["chains_unmeasured"] += 1
            why = chain.get("street_match_failure") or (
                "stale_endpoint" if chain.get("stale_endpoint") else "not_matched_yet"
            )
            out["unmeasured_why"][why] = out["unmeasured_why"].get(why, 0) + 1
            return
        if chain.get("street_detail") == "matched":
            out["chains_matched_to_osm"] += 1
        for i, seg in enumerate(segments):
            source = seg.get("limit_source", "")
            out["limit_miles"][source] = out["limit_miles"].get(source, 0.0) + seg["miles"]
            if source != LIMIT_READ:
                key = f"{source}_{seg.get('limit_basis') or 'past_driveway'}"
                out["fill_miles_by_basis"][key] = (
                    out["fill_miles_by_basis"].get(key, 0.0) + seg["miles"]
                )
            out["limit_mph_miles"][str(seg.get("limit_mph"))] = (
                out["limit_mph_miles"].get(str(seg.get("limit_mph")), 0.0) + seg["miles"]
            )
            if source == LIMIT_READ and float(seg["limit_mph"]) % 5:
                # MUTCD 11th ed. 2B.21 para 13: limits are posted in multiples
                # of 5 mph. Counted and kept: a screen never edits the bake.
                out["screen_read_limit_not_multiple_of_5"] += 1
            for entry in seg.get("controls") or []:
                out["controls_by_kind"][entry["kind"]] += 1
            if i and str(seg.get("cue", "")).lower().startswith("turn "):
                out["turns"] += 1
                if any(entry["at_mi"] == 0.0 for entry in seg.get("controls") or []):
                    out["turns_with_control"] += 1
        counts = chain.get("street_counts") or {}
        out["intersections"] += counts.get("intersections", 0)
        out["intersections_with_control"] += counts.get("controlled", 0)
        out["screen_ambiguous_stop_on_intersection_node"] += counts.get("ambiguous", 0)
        out["screen_signal_and_sign_at_one_intersection"] += counts.get("conflicts", 0)
        out["segments_crossing_town_line"] += counts.get("crosses_town_line", 0)
        out["driveways"] += 1 if chain.get("driveway") else 0

    default, exits = block(), block()
    failed: dict[str, int] = defaultdict(int)
    for record in records.values():
        if record.get("turn_level"):
            add(default, record)
        for chain in record.get("exit_chains") or []:
            add(exits, chain)
        for miss in record.get("exit_chains_failed") or []:
            failed[miss["route_failure"] or "unknown"] += 1
    for out in (default, exits):
        for key in ("limit_miles", "fill_miles_by_basis", "limit_mph_miles"):
            out[key] = {k: round(v, 2) for k, v in sorted(out[key].items())}
        miles = sum(out["limit_miles"].values())
        out["limit_read_ratio"] = round(out["limit_miles"][LIMIT_READ] / miles, 4) if miles else 0.0
    exits["terminals_failed"] = dict(sorted(failed.items()))
    return {"default_chains": default, "exit_chains": exits}


def exit_starts(
    lat: float, lon: float, terminals: Any, max_route_mi: float
) -> list[dict[str, Any]]:
    """The terminals to route a facility's exit chains from, each with its
    search budget: the same DERIVED straight line times 1.25 as the default
    chain's (``routed_approach_miles``), measured from the terminal. A
    terminal beyond ``max_route_mi`` by that measure is not routed;
    ``exit_chain_records`` says so."""
    starts = []
    for terminal in terminals:
        straight = _haversine_mi(terminal["lat"], terminal["lon"], lat, lon)
        budget = round(min(35.0, straight * 1.25), 1)
        if budget <= max_route_mi:
            starts.append({**terminal, "budget_mi": budget})
    return starts


def exit_chain_records(
    facility_id: str,
    terminals: Any,
    exit_routes: dict[tuple[str, int], Any],
    clean: Any,
    max_yard_mi: float,
) -> dict[str, Any]:
    """``exit_chains`` and ``exit_chains_failed`` for a facility this run
    routed. ``clean`` is the writer's per-segment cleaner.

    One chain per ramp terminal the city's deliveries can arrive at, from the
    terminal node itself to the endpoint, whole. The yard-stretch rule holds
    here as on the default chain (``max_yard_mi``); no other floor does,
    because a short chain from a terminal is simply a facility by the exit."""
    chains: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for terminal in terminals:
        node = terminal["node"]
        if (facility_id, node) not in exit_routes:
            failed.append({"terminal_node": node, "route_failure": "beyond_route_limit"})
            continue
        found = exit_routes[(facility_id, node)]
        if isinstance(found, str) or found is None:
            failed.append({"terminal_node": node, "route_failure": found or ""})
            continue
        if found.yard_miles > max_yard_mi:
            failed.append({"terminal_node": node, "route_failure": "yard_too_long"})
            continue
        chain: dict[str, Any] = {
            "terminal_node": node,
            "exit": terminal["exit"],
            "total_miles": found.miles,
            "segments": [clean(segment) for segment in found.segments],
            "street_counts": found.street_counts or {},
        }
        if found.yard_miles:
            chain["yard_miles"] = found.yard_miles
        if found.driveway:
            chain["driveway"] = found.driveway
        chains.append(chain)
    return {"exit_chains": chains, "exit_chains_failed": failed}


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * 3958.7613 * math.asin(math.sqrt(h))


def exit_terminals(legs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """City key -> the ramp terminals a delivery into that city can arrive at.

    For every leg with an end at the city, the labelled exit(s) nearest that
    end, in the direction of arrival. That is the game's own choice of
    destination exit (``scan_destination_exit``: the final leg, the exit
    nearest its destination end), so a chain is baked for each exit a route
    can actually hand over from. An exit whose ramp has no surface terminal
    (a merge, or a length the ramp screen dropped) offers none."""
    out: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for leg in legs:
        interchanges = leg.get("corridor", {}).get("interchanges") or []
        miles = float(leg.get("miles", 0.0))
        labelled = [ix for ix in interchanges if str(ix.get("exit_ref", "")).strip()]
        for city, direction in ((leg["to"], "forward"), (leg["from"], "backward")):
            # Miles from the city end, the game's first ranking key.
            gaps = [
                miles - float(ix.get("at_mi", 0.0))
                if direction == "forward"
                else float(ix.get("at_mi", 0.0))
                for ix in labelled
            ]
            if not gaps:
                continue
            nearest = min(gaps)
            for ix, gap in zip(labelled, gaps, strict=True):
                terminal = ix.get(f"ramp_terminal_{direction}")
                if abs(gap - nearest) > 1e-9 or not terminal:
                    continue
                node = int(terminal["node"])
                out[city].setdefault(
                    node,
                    {
                        "node": node,
                        "lat": float(terminal["lat"]),
                        "lon": float(terminal["lon"]),
                        "exit": {
                            "from": leg["from"],
                            "to": leg["to"],
                            "highway": leg.get("highway", ""),
                            "exit_ref": str(ix.get("exit_ref", "")),
                            "direction": direction,
                        },
                    },
                )
    return {city: [nodes[k] for k in sorted(nodes)] for city, nodes in out.items()}
