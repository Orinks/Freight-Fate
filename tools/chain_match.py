"""Recover the path of a facility chain baked before the street detail was.

671 turn-level city-centre chains came from earlier bakes that today's
route could not reproduce (rules have tightened since: gates and truck bans,
the endpoint screen). Their records carry street names, miles and cues, not
geometry. A chain is a sequence of named streets ending at a known endpoint,
though, so its path can be read back off the map: search backwards from the
endpoint over the OSM graph, allowed onto an edge only when it carries the
street the chain says comes next, until the chain's own mileage is used up.
The recovered path is only accepted when collapsing it reproduces the
chain's streets one for one, each after the first within rounding of its
recorded miles (``same_chain`` says why the first is exempt) --
then its limits, controls and driveway are the chain's, READ off the same
ways, and nothing about the chain itself changes.
"""

from __future__ import annotations

import heapq
from typing import Any

GENERIC = "~generic"
# The record rounds each street to 0.01 mi (``collapse_segments``); two
# roundings apart is the most an honest match can differ by.
MILES_TOLERANCE = 0.02
# ``collapse_segments`` floors a street at 0.05 mi, so a recorded 0.05 is any
# length up to it.
MILES_FLOOR = 0.05

# build_local_geometry.GENERIC_ROADS: every label standing in for a missing
# name (a test holds the two equal).
GENERIC_LABELS = frozenset({"a service road", "a side street", "unnamed public road"})

MATCH_NO_END = "no_endpoint_road"
MATCH_NO_PATH = "no_path_with_these_streets"
MATCH_SHAPE = "streets_or_miles_differ"


def norm(road: str, generic: frozenset[str]) -> str:
    """A street's identity for matching: its name without route refs; every
    stand-in for a missing name is one identity (the class labels replaced
    "unnamed public road" on 2026-08-25, so old and new records differ)."""
    if road in generic:
        return GENERIC
    text = road.split(";", 1)[0]
    if text.endswith(")") and " (" in text:
        text = text[: text.rindex(" (")]
    return text.strip().lower()


def match_path(
    graph: Any,
    end_ref: int,
    segments: list[dict[str, Any]],
    generic: frozenset[str],
    junction_link: str,
    private_label: str,
) -> tuple[list[int], list[tuple[str, float, float | None]], list[str]] | str:
    """Travel-order ``(path nodes, raw edges, edge kinds)`` whose streets are
    ``segments`` in order and whose length is theirs, or a failure code.

    ``graph`` is a ``RouteGraph``; private yard edges count as the street
    ``private_label`` and are kind ``private``."""
    wanted = [
        norm(str(segments[group[0]]["road"]), generic)
        for group in reversed(groups(segments, generic))
    ]
    total = sum(float(seg["miles"]) for seg in segments)
    slack = MILES_TOLERANCE * len(segments) + MILES_FLOOR
    last = len(wanted) - 1

    def edges(node: int):
        for nxt, miles, road, mph in graph.edges.get(node, ()):
            kind = "service" if (node, nxt) in graph.service else "street"
            yield nxt, miles, road, mph, kind
        for nxt, miles in graph.yard_edges.get(node, ()):
            yield nxt, miles, private_label, None, "private"

    start = (end_ref, 0)
    dist = {start: 0.0}
    prev: dict[tuple[int, int], tuple[tuple[int, int], str, float, float | None, str]] = {}
    heap = [(0.0, end_ref, 0)]
    best: tuple[float, tuple[int, int]] | None = None
    while heap:
        miles, node, k = heapq.heappop(heap)
        if miles > dist.get((node, k), float("inf")) or miles > total + slack:
            continue
        if k == last and (best is None or abs(miles - total) < best[0]):
            best = (abs(miles - total), (node, k))
        for nxt, edge_miles, road, mph, kind in edges(node):
            if road == junction_link:
                nk = k
            else:
                label = norm(road, generic)
                if label == wanted[k]:
                    nk = k
                elif k < last and label == wanted[k + 1]:
                    nk = k + 1
                else:
                    continue
            nd = miles + edge_miles
            if nd < dist.get((nxt, nk), float("inf")):
                dist[(nxt, nk)] = nd
                prev[(nxt, nk)] = ((node, k), road, edge_miles, mph, kind)
                heapq.heappush(heap, (nd, nxt, nk))
    if best is None or best[0] > slack:
        return MATCH_NO_PATH
    # Walk back to the endpoint: that walk IS travel order.
    state = best[1]
    nodes = [state[0]]
    raw: list[tuple[str, float, float | None]] = []
    kinds: list[str] = []
    while state != start:
        before, road, edge_miles, mph, kind = prev[state]
        raw.append((road, edge_miles, mph))
        kinds.append(kind)
        nodes.append(before[0])
        state = before
    return nodes, raw, kinds


def groups(recorded: list[dict[str, Any]], generic: frozenset[str]) -> list[list[int]]:
    """Runs of recorded streets that today's collapse would hear as one.

    Chains baked before 2026-09-17 split one street under several route refs
    ("13th Street (I 35 Business)", "13th Street"); ``collapse_segments`` now
    joins a named street's neighbours with the same name, and any two equal
    labels. The recorded split is kept; the match compares per run."""
    out: list[list[int]] = []
    for i, seg in enumerate(recorded):
        road = str(seg["road"])
        if out:
            prev = str(recorded[out[-1][-1]]["road"])
            named = road not in generic and prev not in generic
            if road == prev or (named and norm(road, generic) == norm(prev, generic)):
                out[-1].append(i)
                continue
        out.append([i])
    return out


def same_chain(
    fresh: list[dict[str, Any]], recorded: list[dict[str, Any]], generic: frozenset[str]
) -> bool:
    """Whether a recovered path collapses to the recorded chain: the same
    streets in the same order, each run after the first within rounding of
    its recorded miles (every recorded street in it rounded once).

    The first run's length is not evidence: the search ends it wherever the
    chain's total is used up, within its slack, so its start is placed by
    arithmetic, not read. CALIBRATED on 71 chains in five states whose street
    names all matched: the inner runs agreed exactly on 57 and to 0.01-0.02 on
    5 more, and the rest differed by 0.03 to 0.20 (a different block of the
    same streets); the first run differed by up to 0.06 on chains whose inner
    runs agreed exactly, which is the search slack, not a different road."""
    runs = groups(recorded, generic)
    if len(fresh) != len(runs):
        return False
    for n, (new, run) in enumerate(zip(fresh, runs, strict=True)):
        if norm(str(new["road"]), generic) != norm(str(recorded[run[0]]["road"]), generic):
            return False
        if n == 0:
            continue
        a = float(new["miles"])
        b = sum(float(recorded[i]["miles"]) for i in run)
        if abs(a - b) > MILES_TOLERANCE * len(run) and not (a <= MILES_FLOOR and b <= MILES_FLOOR):
            return False
    return True


def adopt(
    recorded: list[dict[str, Any]],
    fresh: list[dict[str, Any]],
    generic: frozenset[str] = GENERIC_LABELS,
) -> list[dict[str, Any]]:
    """The recorded segments with the recovered path's street detail: each
    run's limit on every street in it, each control on the street its offset
    falls in. The first run is aligned at its END, the junction both chains
    share (its start is placed by arithmetic; see ``same_chain``)."""
    out = []
    for r, (new, run) in enumerate(zip(fresh, groups(recorded, generic), strict=True)):
        start = first_run_shift(recorded, fresh, generic) if r == 0 else 0.0
        for n, i in enumerate(run):
            old = recorded[i]
            miles = float(old["miles"])
            last = n == len(run) - 1
            controls = [
                {"at_mi": round(min(c["at_mi"] - start, miles), 2), "kind": c["kind"]}
                for c in new.get("controls") or []
                if c["at_mi"] >= start and (last or c["at_mi"] < start + miles)
            ]
            row = {
                **old,
                "limit_mph": new["limit_mph"],
                "limit_source": new["limit_source"],
                "controls": controls,
            }
            if new.get("limit_basis"):
                row["limit_basis"] = new["limit_basis"]
            out.append(row)
            start += miles
    return out


def first_run_shift(
    recorded: list[dict[str, Any]],
    fresh: list[dict[str, Any]],
    generic: frozenset[str] = GENERIC_LABELS,
) -> float:
    """How much longer the recovered first run is than the recorded one:
    the offset between the two chains' mileposts everywhere after it."""
    first = groups(recorded, generic)[0]
    return float(fresh[0]["miles"]) - sum(float(recorded[i]["miles"]) for i in first)


# Keys a match writes on a kept record, so a re-run can clear its own.
MATCH_KEYS = ("street_counts", "driveway", "street_detail", "street_match_failure")


def legacy_chains(existing: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    """Facility id -> recorded segments of every turn-level chain whose street
    detail can only come from a match: never measured, or matched before (a
    re-run matches it again). A chain leading to a replaced endpoint is left
    out: its endpoint is not the one on record, so there is nothing to match
    its end against."""
    out: dict[str, list[dict[str, Any]]] = {}
    for facility_id, record in ((existing or {}).get("approaches") or {}).items():
        if not record.get("turn_level") or not record.get("segments"):
            continue
        if record.get("stale_endpoint"):
            continue
        if "street_counts" in record and record.get("street_detail") != "matched":
            continue
        out[facility_id] = record["segments"]
    return out


def detail_of(found: Any, clean: Any) -> dict[str, Any]:
    """What a match hands the merge: the recovered chain's detail, or why."""
    if isinstance(found, str):
        return {"failure": found}
    return {
        "segments": [clean(segment) for segment in found.segments],
        "driveway": found.driveway,
        "street_counts": found.street_counts or {},
    }


def apply_match(old: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    """A kept chain with its matched street detail (the chain itself is
    unchanged), or labelled with why none could be matched."""
    bare = [
        {
            k: v
            for k, v in seg.items()
            if k not in ("limit_mph", "limit_source", "limit_basis", "controls")
        }
        for seg in old["segments"]
    ]
    out = {k: v for k, v in old.items() if k not in MATCH_KEYS}
    if "failure" in match:
        return {**out, "segments": bare, "street_match_failure": match["failure"]}
    out.update(
        segments=adopt(bare, match["segments"]),
        street_counts=match["street_counts"],
        street_detail="matched",
    )
    if match["driveway"]:
        shift = first_run_shift(bare, match["segments"])
        at = round(match["driveway"]["at_mi"] - shift, 2)
        if at >= 0.0:
            out["driveway"] = {**match["driveway"], "at_mi": at}
    return out
