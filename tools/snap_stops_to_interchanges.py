"""Give each truck stop the identity of the interchange that serves it.

The game finds a stop's exit number and the control at the end of its ramp by
mile marker: the interchange record nearest the stop's ``at_mi``, within 2.0
miles for the number and 0.15 for the control. A stop's ``at_mi`` is a
projection onto simplified geometry. Measured here against the 1,223 stops
whose read coordinates put them beside a junction, it is within 0.15 miles of
that junction for one stop in six and more than a mile off for half. So 29
ramps in 30 took a seeded urban or rural control, an ASSUMED value spoken as
if it were the ramp's. Where a stop's exit is now known and the 2.0 mile
search had found a number, that number was another exit's 464 times in 1,086.

This tool decides the interchange ONCE, from evidence, and writes it on the
stop so the runtime looks the control up by identity with no tolerance:

``exit_ref``        the signed exit number. READ: from the stop's own source
                    when that names the exit (a chain's store listing), else
                    from the ``ref`` tag of the OpenStreetMap
                    ``highway=motorway_junction`` node the stop snapped to.
``interchange_mi``  the ``at_mi`` of this leg's interchange record for that
                    exit, present only when the leg has one. DERIVED: a link,
                    by exit number, from the stop to a record already baked.
``exit_source``     which evidence decided it, in words.

Evidence, strongest first:

1. **The stop names its exit.** 275 curated records quote the chain's own
   listing ("on I-84, exit 211"). The leg's record with that number is the
   interchange, when it lies within ``NAMED_EXIT_MAX_MI`` of the stop's mile
   marker. A record further off than that contradicts itself (the stop is not
   where the exit it names is) and is listed, not linked.
2. **Read coordinates.** The nearest junction node ON THE LEG'S OWN HIGHWAY,
   within ``SNAP_CUT_MI``. "On the leg's own highway" is two tests: the node
   lies within 200 m of the leg's archived geometry (the corridor rule the
   interchange records were built with), and a motorway or trunk way through
   the node carries a route ref or name the leg or its records carry. The
   second test is why the state extracts are read: without it a stop at a
   system interchange snaps to the crossing freeway's exit (Little America in
   Cheyenne, I-80 exit 358 by its own listing, took I-25's "8B").
3. **The same store under another name.** A stop with neither inherits from
   its twin on the same leg: same chain, within four miles, one name bare or
   both naming one place (the ``data::stop_twins`` rule, which keeps the named
   record and drops the one that had the coordinates).

A stop none of these reaches gets no field, and the runtime keeps the old
mile-marker lookup for it.

Coordinates are evidence only when READ. ``reverse_pair_stops.py`` gave 485
opposite-direction copies a point on the source leg's line at the stop's mile
marker, stored as ``lat``/``lon``. Those are the mile marker again, not a
survey, and are ignored here: a copy's coordinates count only when a record
that is not a copy carries the same name and the same coordinates.

Where the numbers come from (printed by every run, so they can be re-judged):

``SNAP_CUT_MI = 0.6``  Stop-to-junction distances in 0.05 mile bins climb to a
    peak at 0.20 to 0.25, fall through 0.45, and from 0.60 on sit at the flat
    rate of stops that are simply somewhere along the road (the 1 to 2 mile
    bins). 0.6 is where the cluster meets that floor. The floor rate times the
    twelve bins under the cut bounds how many snaps could be chance.
``RECORD_MATCH_MAX_MI = 5.0``  A junction and the leg record with its exit
    number: the gap between the node's projected mile and the record's
    ``at_mi`` is under 2 miles for 19 in 20, thins to nothing between 5 and
    10, and returns beyond 10 as the same number in another state.
``NAMED_EXIT_MAX_MI = 5.3``  How wrong a stop's ``at_mi`` can honestly be,
    measured on stops whose read coordinates put them within the cut of a
    junction: the 99th percentile of the gap to that junction's mile (median
    0.9, 95th 4.1).

The snap has one check that owes nothing to the snap: a store whose listing
names its exit, beside a twin record of the same store that has coordinates.
40 such twins snap inside the cut, and all 40 land on the listed exit.

Only stops reached by an exit are snapped: travel centers, truck stops, fuel
stations, and service plazas that do not call themselves a service plaza or
service area. Rest areas, weigh stations, truck parking lots and turnpike
plazas have ramps of their own.

Development-time only. Reads the cached Geofabrik state extracts one at a
time (``~/.cache/freight-fate-osm/regions``), caches each state's junction
list beside it, and never touches the network.

Measured 2026-09-17 on the 3,936 stops reached by an exit, before and after:

    ramp control read from the map      133 (3.4%)  ->   574 (14.6%)
    ramp control seeded (ASSUMED)     3,803 (96.6%) -> 3,362 (85.4%)
    stop linked to its interchange        0         ->   890 (22.6%)
    exit number spoken                1,926 (48.9%) -> 2,230 (56.7%)
    exit number decided by identity       0         -> 1,390; for 464 of them
                                      the mile marker had named another exit

The controls are still mostly assumed, and the run says so. What is left is
not a snapping problem: 1,353 of the stops are on legs with no interchange
records at all, 390 snapped to an exit their leg does not record (the
interchange build drops exits closer than two miles to a richer neighbour),
and 1,291 have read coordinates more than 0.6 miles from any junction on the
leg's highway (stores in the endpoint town, or on a surface highway with a
driveway and no ramp). 48 stops name an exit the leg puts more than 5.3
miles away; ``--contradictions`` lists them.

    uv run --group tooling python tools/snap_stops_to_interchanges.py          # report only
    uv run --group tooling python tools/snap_stops_to_interchanges.py --write
    uv run python tools/index_world.py
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import leg_geometry as lg  # noqa: E402
from build_interchanges_base import LOCAL_CORRIDOR_M  # noqa: E402
from build_interchanges_maxspeed import (  # noqa: E402
    OSM_REGION_CACHE_DIR,
    _leg_states,
    _pbf_for_states,
)
from reverse_pair_stops import TWIN_STOP_MILES, _same_chain_store  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

ACCESSED_DATE = "2026-09-17"
SNAP_CUT_MI = 0.6
RECORD_MATCH_MAX_MI = 5.0
NAMED_EXIT_MAX_MI = 5.3
JUNCTION_CACHE_VERSION = 1
MI_PER_DEG = 69.0934

# The old runtime tolerances, kept here only to measure what they reached.
OLD_EXIT_LABEL_TOL_MI = 2.0
OLD_RAMP_CONTROL_TOL_MI = 0.15

SNAP_TYPES = frozenset({"travel_center", "truck_stop", "fuel_station", "service_plaza"})
OWN_RAMP_NAME_PHRASES = ("service plaza", "service area")
COPY_NOTE = "Opposite-direction copy"
FIELDS = ("exit_ref", "interchange_mi", "exit_source")
NAMED_EXIT_RE = re.compile(r"\bexit\s+(\d+\s?[A-Za-z]?)(?![A-Za-z0-9])", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Junction:
    lat: float
    lon: float
    ref: str
    roads: frozenset[str]


@dataclass(slots=True)
class Snap:
    exit_ref: str
    interchange_mi: float | None
    source: str
    kind: str


def _token(text: str) -> str:
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


def _ref(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).upper()


# ------------------------------------------------------------ junction index


def _junctions_from_pbf(pbf_path: Path) -> list[dict[str, Any]]:
    """Every motorway_junction node in one extract, with the roads through it."""
    try:
        import osmium  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Reading the state extracts needs the tooling group: "
            "uv run --group tooling python tools/snap_stops_to_interchanges.py"
        ) from exc

    class Handler(osmium.SimpleHandler):  # type: ignore[name-defined]
        def __init__(self) -> None:
            super().__init__()
            self.nodes: dict[int, tuple[float, float, str]] = {}
            self.roads: dict[int, set[str]] = {}

        def node(self, node: Any) -> None:
            if node.tags.get("highway") != "motorway_junction" or not node.location.valid():
                return
            self.nodes[int(node.id)] = (
                float(node.location.lat),
                float(node.location.lon),
                str(node.tags.get("ref", "")),
            )

        def way(self, way: Any) -> None:
            # Nodes come before ways in a PBF, so the junction set is complete.
            if way.tags.get("highway") not in ("motorway", "trunk"):
                return
            names = [piece for piece in str(way.tags.get("ref", "")).split(";")]
            names.append(str(way.tags.get("name", "")))
            tokens = {_token(name) for name in names} - {""}
            if not tokens:
                return
            for node_ref in way.nodes:
                if node_ref.ref in self.nodes:
                    self.roads.setdefault(int(node_ref.ref), set()).update(tokens)

    handler = Handler()
    tag_filter = osmium.filter.TagFilter(  # type: ignore[attr-defined]
        ("highway", "motorway_junction"), ("highway", "motorway"), ("highway", "trunk")
    )
    handler.apply_file(str(pbf_path), filters=[tag_filter])
    return [
        {"lat": lat, "lon": lon, "ref": ref, "roads": sorted(handler.roads.get(node_id, ()))}
        for node_id, (lat, lon, ref) in sorted(handler.nodes.items())
    ]


def load_junctions(pbf_paths: list[Path], rebuild: bool = False) -> list[Junction]:
    """All junction nodes, one extract at a time, each cached beside its PBF."""
    out: list[Junction] = []
    for pbf_path in pbf_paths:
        cache = pbf_path.with_name(pbf_path.name.replace(".osm.pbf", ".junctionroads.json"))
        stat = pbf_path.stat()
        stamp = {
            "version": JUNCTION_CACHE_VERSION,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
        rows = None
        if cache.exists() and not rebuild:
            try:
                payload = json.loads(cache.read_text(encoding="utf-8"))
                if payload.get("stamp") == stamp:
                    rows = payload["junctions"]
            except (OSError, json.JSONDecodeError, KeyError):
                rows = None
        if rows is None:
            print(f"    reading {pbf_path.name}", flush=True)
            rows = _junctions_from_pbf(pbf_path)
            cache.write_text(json.dumps({"stamp": stamp, "junctions": rows}), encoding="utf-8")
        out.extend(
            Junction(float(r["lat"]), float(r["lon"]), _ref(r["ref"]), frozenset(r["roads"]))
            for r in rows
        )
    return out


# ------------------------------------------------------------------ geometry


def project(
    points: np.ndarray, geom: list[tuple[float, float, float]]
) -> tuple[np.ndarray, np.ndarray]:
    """(miles off the polyline, leg mile of the foot) for each (lat, lon) row."""
    line = np.asarray(geom, dtype=float)
    lat0 = math.radians(float(line[:, 0].mean()))
    gx = line[:, 1] * math.cos(lat0) * MI_PER_DEG
    gy = line[:, 0] * MI_PER_DEG
    gm = line[:, 2]
    ax, ay = gx[:-1], gy[:-1]
    dx, dy = gx[1:] - ax, gy[1:] - ay
    length2 = dx * dx + dy * dy
    length2[length2 == 0.0] = 1e-12
    off = np.empty(len(points))
    mile = np.empty(len(points))
    for i, (lat, lon) in enumerate(points):
        px, py = lon * math.cos(lat0) * MI_PER_DEG, lat * MI_PER_DEG
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / length2, 0.0, 1.0)
        d2 = (px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2
        k = int(d2.argmin())
        off[i] = math.sqrt(float(d2[k]))
        mile[i] = gm[k] + float(t[k]) * (gm[k + 1] - gm[k])
    return off, mile


def _flat_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return math.hypot(
        (lat2 - lat1) * MI_PER_DEG,
        (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2.0)) * MI_PER_DEG,
    )


# --------------------------------------------------------------------- stops


def reached_by_an_exit(stop: dict[str, Any]) -> bool:
    name = str(stop.get("name", "")).lower()
    return stop.get("type") in SNAP_TYPES and not any(p in name for p in OWN_RAMP_NAME_PHRASES)


def fabricated_coordinates(legs: list[dict[str, Any]]) -> set[int]:
    """ids of copied stops whose lat/lon no original record backs."""
    originals: dict[str, list[tuple[float, float]]] = collections.defaultdict(list)
    for leg in legs:
        for stop in leg.get("stops", ()):
            if "lat" in stop and "lon" in stop and COPY_NOTE not in str(stop.get("source", "")):
                originals[stop["name"]].append((float(stop["lat"]), float(stop["lon"])))
    fabricated: set[int] = set()
    for leg in legs:
        for stop in leg.get("stops", ()):
            if "lat" not in stop or "lon" not in stop:
                continue
            if COPY_NOTE not in str(stop.get("source", "")):
                continue
            lat, lon = float(stop["lat"]), float(stop["lon"])
            if not any(
                abs(lat - a) < 1e-6 and abs(lon - b) < 1e-6 for a, b in originals[stop["name"]]
            ):
                fabricated.add(id(stop))
    return fabricated


def named_exit(stop: dict[str, Any]) -> str:
    match = NAMED_EXIT_RE.search(str(stop.get("source", "")))
    return _ref(match.group(1)) if match else ""


def leg_road_tokens(leg: dict[str, Any]) -> frozenset[str]:
    texts = [str(leg.get("highway", ""))]
    texts.extend(str(ix.get("highway", "")) for ix in _interchanges(leg))
    return frozenset(_token(piece) for text in texts for piece in re.split(r"[/;,]", text)) - {""}


def _interchanges(leg: dict[str, Any]) -> list[dict[str, Any]]:
    return list(leg.get("corridor", {}).get("interchanges", ()) or ())


def record_for(
    leg: dict[str, Any], ref: str, near_mi: float, max_mi: float
) -> dict[str, Any] | None:
    """This leg's interchange record carrying `ref`, nearest `near_mi`."""
    same = [ix for ix in _interchanges(leg) if ref and _ref(ix.get("exit_ref")) == ref]
    if not same:
        return None
    best = min(same, key=lambda ix: abs(float(ix["at_mi"]) - near_mi))
    return best if abs(float(best["at_mi"]) - near_mi) <= max_mi else None


# ---------------------------------------------------------------------- snap


@dataclass(slots=True)
class Report:
    distances: list[float]
    at_mi_errors: list[float]
    record_gaps: list[float]
    contradictions: list[str]
    twin_checks: list[tuple[float, bool]]
    misses: collections.Counter[str]


@dataclass(slots=True)
class LegWork:
    """One leg's stops part way through the evidence."""

    leg: dict[str, Any]
    stops: list[dict[str, Any]]
    snaps: dict[int, Snap]
    contradicted: set[int]
    located: list[dict[str, Any]]
    on_road: list[tuple[Junction, float]]
    why_not: dict[int, str]


def _contradicts(leg: dict[str, Any], ref: str, near_mi: float, max_mi: float) -> bool:
    """The leg records exit `ref`, but too far from `near_mi` for both to be right."""
    return (
        record_for(leg, ref, near_mi, max_mi) is None
        and record_for(leg, ref, near_mi, math.inf) is not None
    )


def _linked(leg: dict[str, Any], ref: str, near_mi: float, max_mi: float, how: str) -> Snap:
    """The snap for a stop at exit `ref`: linked to the leg's record of that
    exit when one lies within `max_mi`, the number alone when none does."""
    record = record_for(leg, ref, near_mi, max_mi)
    where = (
        "interchange_mi derived: this leg's interchange record with that exit number"
        if record is not None
        else "this leg has no interchange record with that number"
    )
    return Snap(
        exit_ref=str(record["exit_ref"]) if record is not None else ref,
        interchange_mi=float(record["at_mi"]) if record is not None else None,
        source=f"{how}; {where}.",
        kind="",
    )


def first_evidence(
    leg: dict[str, Any],
    junctions: list[Junction],
    grid: dict[tuple[int, int], list[int]],
    fabricated: set[int],
    report: Report,
) -> LegWork:
    """Evidence 1 and 2: what a stop's own record says about where it is."""
    stops = [s for s in leg.get("stops", ()) if reached_by_an_exit(s)]
    work = LegWork(leg, stops, {}, set(), [], [], {})
    leg_id = lg.leg_id_of(leg)

    # 1. the stop names its exit
    for stop in stops:
        ref = named_exit(stop)
        if not ref:
            continue
        at_mi = float(stop["at_mi"])
        if _contradicts(leg, ref, at_mi, NAMED_EXIT_MAX_MI):
            far = record_for(leg, ref, at_mi, math.inf)
            work.contradicted.add(id(stop))
            report.contradictions.append(
                f"{leg_id}: {stop['name']} at mile {at_mi:g} names exit {ref}, "
                f"which this leg puts at mile {float(far['at_mi']):g}"
            )
            continue
        how = f"exit_ref read: the stop's own source names exit {ref}"
        snap = _linked(leg, ref, at_mi, NAMED_EXIT_MAX_MI, how)
        snap.kind = "named"
        work.snaps[id(stop)] = snap

    # 2. read coordinates against junction nodes on the leg's own highway
    work.located = [
        s
        for s in stops
        if "lat" in s and "lon" in s and id(s) not in fabricated and id(s) not in work.contradicted
    ]
    work.on_road = on_road_junctions(leg, junctions, grid) if work.located else []
    roads = leg_road_tokens(leg)
    for stop in work.located if work.on_road else ():
        lat, lon = float(stop["lat"]), float(stop["lon"])
        junction, junction_mi = min(
            work.on_road, key=lambda c: _flat_mi(lat, lon, c[0].lat, c[0].lon)
        )
        dist = _flat_mi(lat, lon, junction.lat, junction.lon)
        report.distances.append(dist)
        if dist > SNAP_CUT_MI:
            work.why_not[id(stop)] = "read coordinates, nearest junction beyond the cut"
            continue
        report.at_mi_errors.append(abs(float(stop["at_mi"]) - junction_mi))
        if not junction.ref:
            work.why_not[id(stop)] = "read coordinates, junction carries no exit number"
            continue
        record = record_for(leg, junction.ref, junction_mi, math.inf)
        if record is not None:
            report.record_gaps.append(abs(float(record["at_mi"]) - junction_mi))
        if id(stop) in work.snaps:
            continue  # it names its exit, and its own listing outranks a snap
        road = "/".join(sorted(junction.roads & roads))
        how = (
            f"exit_ref read: ref tag of the nearest OpenStreetMap highway=motorway_junction "
            f"node on {road}, {dist:.2f} mi from the stop's read coordinates (derived snap, "
            f"cut {SNAP_CUT_MI} mi), local Geofabrik extract accessed {ACCESSED_DATE}"
        )
        # A record with this number beyond the bound is another state's exit
        # of the same number, so the stop keeps the number and takes no link.
        snap = _linked(leg, junction.ref, junction_mi, RECORD_MATCH_MAX_MI, how)
        snap.kind = "snapped"
        work.snaps[id(stop)] = snap
    return work


def inherit_from_twin(work: LegWork) -> None:
    """Evidence 3: the same store under another name on the same leg."""
    for stop in work.stops:
        if id(stop) in work.snaps or id(stop) in work.contradicted:
            continue
        twins = [
            other
            for other in work.stops
            if id(other) in work.snaps
            and work.snaps[id(other)].kind != "twin"
            and abs(float(other["at_mi"]) - float(stop["at_mi"])) <= TWIN_STOP_MILES
            and _same_chain_store(str(stop["name"]), str(other["name"]))
        ]
        if not twins:
            continue
        twin = min(twins, key=lambda other: abs(float(other["at_mi"]) - float(stop["at_mi"])))
        found = work.snaps[id(twin)]
        work.snaps[id(stop)] = Snap(
            exit_ref=found.exit_ref,
            interchange_mi=found.interchange_mi,
            source=(
                f"derived: inherited from {twin['name']} at mile {float(twin['at_mi']):g} of "
                f"this leg, the same store under another name (same chain within "
                f"{TWIN_STOP_MILES:g} mi); that record says how its exit was decided."
            ),
            kind="twin",
        )


def account(work: LegWork, report: Report) -> None:
    """Why each unmatched stop was not, and the listed-exit calibration."""
    for stop in work.stops:
        if id(stop) in work.snaps:
            continue
        if id(stop) in work.contradicted:
            report.misses["names an exit the leg puts elsewhere"] += 1
        elif id(stop) in work.why_not:
            report.misses[work.why_not[id(stop)]] += 1
        elif any(stop is s for s in work.located):
            report.misses["read coordinates, no junction on the leg's own highway"] += 1
        else:
            report.misses["no read coordinates, no listed exit, no twin"] += 1
    # A store's listed exit and its coordinate twin's snap are two readings
    # of one exit: the one check on the snap that owes nothing to the snap.
    for stop in work.stops:
        ref = named_exit(stop)
        if not ref:
            continue
        for other in work.located:
            if other is stop or not _same_chain_store(str(stop["name"]), str(other["name"])):
                continue
            if abs(float(other["at_mi"]) - float(stop["at_mi"])) > TWIN_STOP_MILES:
                continue
            snapped = _nearest_numbered(other, work.on_road)
            if snapped is not None:
                report.twin_checks.append((snapped[1], _number(snapped[0]) == _number(ref)))


def snap_world(
    legs: list[dict[str, Any]],
    junctions: list[Junction],
    grid: dict[tuple[int, int], list[int]],
    fabricated: set[int],
    report: Report,
) -> dict[int, Snap]:
    snaps: dict[int, Snap] = {}
    for leg in legs:
        work = first_evidence(leg, junctions, grid, fabricated, report)
        inherit_from_twin(work)
        account(work, report)
        snaps.update(work.snaps)
    return snaps


def _number(ref: str) -> str:
    return re.sub(r"[A-Z]+$", "", ref)


def on_road_junctions(
    leg: dict[str, Any],
    junctions: list[Junction],
    grid: dict[tuple[int, int], list[int]],
) -> list[tuple[Junction, float]]:
    """(junction, leg mile) for every junction node on the leg's own highway."""
    geom = lg.corridor_geometry(leg)
    if not geom or len(geom) < 2:
        return []
    line = np.asarray(geom, dtype=float)
    lat_cells = range(
        int(math.floor(line[:, 0].min() * 10)) - 1, int(math.floor(line[:, 0].max() * 10)) + 2
    )
    lon_cells = range(
        int(math.floor(line[:, 1].min() * 10)) - 1, int(math.floor(line[:, 1].max() * 10)) + 2
    )
    nearby = sorted({j for a in lat_cells for b in lon_cells for j in grid.get((a, b), ())})
    if not nearby:
        return []
    off, mile = project(np.array([(junctions[j].lat, junctions[j].lon) for j in nearby]), geom)
    roads = leg_road_tokens(leg)
    return [
        (junctions[j], float(mile[i]))
        for i, j in enumerate(nearby)
        if off[i] * 1609.344 <= LOCAL_CORRIDOR_M and junctions[j].roads & roads
    ]


def _nearest_numbered(
    stop: dict[str, Any], on_road: list[tuple[Junction, float]]
) -> tuple[str, float] | None:
    """(ref, miles) of the numbered on-road junction nearest a located stop."""
    candidates = [c for c in on_road if c[0].ref]
    if not candidates:
        return None
    lat, lon = float(stop["lat"]), float(stop["lon"])
    junction, _ = min(candidates, key=lambda c: _flat_mi(lat, lon, c[0].lat, c[0].lon))
    return junction.ref, _flat_mi(lat, lon, junction.lat, junction.lon)


# ------------------------------------------------------------------- measure


def measure(legs: list[dict[str, Any]], use_fields: bool) -> collections.Counter[str]:
    """What the runtime reaches for stops reached by an exit."""
    out: collections.Counter[str] = collections.Counter()
    for leg in legs:
        records = _interchanges(leg)
        for stop in leg.get("stops", ()):
            if not reached_by_an_exit(stop):
                continue
            out["stops"] += 1
            if not records:
                out["on a leg with no interchange records"] += 1
            at_mi = float(stop["at_mi"])
            linked = None
            if use_fields and "interchange_mi" in stop:
                linked = next(
                    (ix for ix in records if float(ix["at_mi"]) == float(stop["interchange_mi"])),
                    None,
                )
            # The runtime's order: the linked record, the stop's own number,
            # then the old mile-marker guess.
            by_identity = use_fields and bool(
                (linked or {}).get("exit_ref") or stop.get("exit_ref")
            )
            by_mile_marker = any(
                ix.get("exit_ref") and abs(float(ix["at_mi"]) - at_mi) <= OLD_EXIT_LABEL_TOL_MI
                for ix in records
            )
            if by_identity or by_mile_marker:
                out["exit number"] += 1
            if by_identity:
                out["exit number by identity"] += 1
                old = min(
                    (ix for ix in records if ix.get("exit_ref")),
                    key=lambda ix: abs(float(ix["at_mi"]) - at_mi),
                    default=None,
                )
                new = _ref((linked or {}).get("exit_ref") or stop.get("exit_ref"))
                if (
                    old is not None
                    and abs(float(old["at_mi"]) - at_mi) <= OLD_EXIT_LABEL_TOL_MI
                    and _ref(old["exit_ref"]) != new
                ):
                    out["of those, the mile marker named another exit"] += 1
            if linked is not None:
                out["interchange by identity"] += 1
                control, far_end = linked.get("ramp_control", ""), linked.get("ramp_far_end", "")
            else:
                near = [
                    ix
                    for ix in records
                    if abs(float(ix["at_mi"]) - at_mi) <= OLD_RAMP_CONTROL_TOL_MI
                ]
                control = next((ix["ramp_control"] for ix in near if ix.get("ramp_control")), "")
                far_end = near[0].get("ramp_far_end", "") if near else ""
            if control:
                out["ramp control read"] += 1
            elif far_end == "motorway":
                out["ramp control derived (ramp lands on a freeway)"] += 1
            else:
                out["ramp control seeded (assumed)"] += 1
    return out


def _histogram(values: list[float], width: float, upto: float) -> list[tuple[float, int]]:
    bins = [0] * int(round(upto / width))
    for value in values:
        if value < upto:
            bins[min(int(value / width), len(bins) - 1)] += 1
    return [(round(i * width, 2), n) for i, n in enumerate(bins)]


def print_report(
    before: collections.Counter[str], after: collections.Counter[str], report: Report
) -> None:
    print("\nStop to nearest junction on the leg's own highway, read coordinates only, miles:")
    for lo, n in _histogram(report.distances, 0.05, 1.2):
        mark = "  <- cut" if abs(lo - SNAP_CUT_MI) < 1e-9 else ""
        print(f"  {lo:4.2f}-{lo + 0.05:4.2f}  {n:4d}  {'#' * (n // 5)}{mark}")
    floor = sum(1 for d in report.distances if 1.0 <= d < 2.0) / 20.0
    under = sum(1 for d in report.distances if d <= SNAP_CUT_MI)
    print(
        f"  floor (1 to 2 mi) {floor:.1f} per 0.05 mi bin; {under} stops under the cut, of which "
        f"at most {floor * SNAP_CUT_MI / 0.05:.0f} ({floor * SNAP_CUT_MI / 0.05 / max(under, 1):.0%}) "
        f"could be there by chance"
    )
    if report.twin_checks:
        print("\nCalibration: a store's listed exit against its coordinate twin's snap:")
        for lo, hi in ((0.0, SNAP_CUT_MI), (SNAP_CUT_MI, 1.0), (1.0, 2.0), (2.0, math.inf)):
            rows = [ok for dist, ok in report.twin_checks if lo <= dist < hi]
            if rows:
                print(f"  snap {lo:g} to {hi:g} mi: {sum(rows)} of {len(rows)} agree")
    errors = sorted(report.at_mi_errors)
    if errors:
        pct = lambda q: errors[min(len(errors) - 1, int(q * len(errors)))]  # noqa: E731
        print(
            f"\nStop at_mi against its junction's mile ({len(errors)} snapped stops): within "
            f"{OLD_RAMP_CONTROL_TOL_MI} mi {sum(1 for e in errors if e <= OLD_RAMP_CONTROL_TOL_MI) / len(errors):.0%}, "
            f"over 1 mi {sum(1 for e in errors if e > 1.0) / len(errors):.0%}, "
            f"median {pct(0.5):.2f}, 95th {pct(0.95):.2f}, 99th {pct(0.99):.2f} mi"
        )
    gaps = report.record_gaps
    if gaps:
        edges = (0.5, 1.0, 2.0, 5.0, 10.0, math.inf)
        counts = [
            sum(1 for g in gaps if lo <= g < hi)
            for lo, hi in zip((0.0, *edges), edges, strict=False)
        ]
        print(f"Junction mile against the same-number record's at_mi, bins to {edges}: {counts}")
    print(f"\n{'':48s}{'before':>6s}{'after':>6s}")
    for key in (
        "stops",
        "on a leg with no interchange records",
        "exit number",
        "exit number by identity",
        "of those, the mile marker named another exit",
        "interchange by identity",
        "ramp control read",
        "ramp control derived (ramp lands on a freeway)",
        "ramp control seeded (assumed)",
    ):
        b, a = before[key], after[key]
        share = (
            f"  ({b / before['stops']:.1%} -> {a / after['stops']:.1%})" if key != "stops" else ""
        )
        print(f"{key:48s}{b:6d}{a:6d}{share}")
    read, seeded = after["ramp control read"], after["ramp control seeded (assumed)"]
    print(
        f"\nRAMP CONTROLS STILL MOSTLY ASSUMED: {read} read to {seeded} seeded "
        f"({read / max(read + seeded, 1):.0%} read)."
        if seeded > read
        else f"\nRamp controls: {read} read to {seeded} seeded."
    )


# ---------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="update the world source")
    parser.add_argument("--osm-region-dir", type=Path, default=OSM_REGION_CACHE_DIR)
    parser.add_argument("--rebuild-junctions", action="store_true")
    parser.add_argument(
        "--contradictions",
        action="store_true",
        help="list every stop that names an exit it is not at",
    )
    args = parser.parse_args(argv)

    data = load_world()
    legs = data["legs"]
    states = set().union(*(_leg_states(data, leg) for leg in legs))
    pbf_paths = _pbf_for_states(states, args.osm_region_dir)
    if not pbf_paths:
        raise SystemExit(f"No state extracts in {args.osm_region_dir}; nothing to snap against.")
    junctions = load_junctions(pbf_paths, rebuild=args.rebuild_junctions)
    print(f"{len(junctions):,} junction nodes from {len(pbf_paths)} state extracts.")
    grid: dict[tuple[int, int], list[int]] = collections.defaultdict(list)
    for i, junction in enumerate(junctions):
        grid[(int(math.floor(junction.lat * 10)), int(math.floor(junction.lon * 10)))].append(i)

    fabricated = fabricated_coordinates(legs)
    print(
        f"{len(fabricated)} copied stops carry coordinates no original backs; ignored as evidence."
    )

    before = measure(legs, use_fields=False)
    report = Report([], [], [], [], [], collections.Counter())
    kinds: collections.Counter[str] = collections.Counter()
    changed = 0
    snaps = snap_world(legs, junctions, grid, fabricated, report)
    for leg in legs:
        for stop in leg.get("stops", ()):
            old = {key: stop.get(key) for key in FIELDS}
            for key in FIELDS:
                stop.pop(key, None)
            snap = snaps.get(id(stop))
            if snap is not None:
                kinds[
                    snap.kind
                    + (" with a record" if snap.interchange_mi is not None else ", number only")
                ] += 1
                stop["exit_ref"] = snap.exit_ref
                if snap.interchange_mi is not None:
                    stop["interchange_mi"] = snap.interchange_mi
                stop["exit_source"] = snap.source
            changed += old != {key: stop.get(key) for key in FIELDS}
    after = measure(legs, use_fields=True)

    print_report(before, after, report)
    print("\nHow each stop was decided:")
    for kind, n in sorted(kinds.items()):
        print(f"  {kind}: {n}")
    print("Why the rest were not:")
    for reason, n in report.misses.most_common():
        print(f"  {reason}: {n}")
    print(
        f"{len(report.contradictions)} stops name an exit this leg puts over {NAMED_EXIT_MAX_MI:g} mi away (not linked)."
    )
    if args.contradictions:
        for line in report.contradictions:
            print("  " + line)

    if not args.write:
        print(f"\nDry run: {changed} stop records would change. Pass --write to apply.")
        return 0
    written = save_world(data)
    print(
        f"\nWrote {written} source files; {changed} stop records changed. Now: uv run python tools/index_world.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
