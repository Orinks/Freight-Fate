"""A facility's own private road, as the first link of its street chain.

Owner ruling, 2026-09-17. A truck leaves a yard over the yard's own road, and
OpenStreetMap tags that road ``access=private``: closed to the public, not to
the truck with a load for that dock. Until this rule the facility builder
refused every endpoint that joins the street network only over such ways.

The rule is a fallback. It is asked only after the public-road search has
come back ``disconnected``; a facility with a public path keeps it.

What may be used, and what kind of fact each rule rests on:

* READ: a way is a yard road when it is a routable surface class and carries
  ``access=private`` (:func:`is_yard_road`).
* READ, stays refused: ``access=no`` (closed to everyone), ``access=military``
  or any ``military`` tag, ``motor_vehicle``/``vehicle``/``hgv``/``goods`` =
  ``no``, ``service=emergency_access``, ``motorroad=yes``, and motorways,
  which are not surface roads and are never in the graph. Water is refused by
  there being no road across it.
* READ, stays refused on the public part: a public way signed
  ``motor_vehicle``/``vehicle``/``hgv`` = ``no`` (:func:`bans_trucks`), and a
  barrier node (``barrier=gate`` and the like) met on a PUBLIC way. A gate on
  the yard's own private stretch, or where the private road meets the street,
  is a yard's gate and is fine.
* DERIVED: the private stretch is ONLY AT THE FACILITY END. The search grows
  outward from the endpoint over private ways (and over any public fragment
  that itself reaches the street network only through them) and stops at the
  first node the city context can reach over public roads. The public search
  never sees a private way, so no chain can cut through another site.
* DERIVED: the stretch is not a street. Every edge of it is labelled
  ``a service road`` (the canonical noun in ``docs/ontology.md`` for a way
  with no name of its own), never a name or ref from a private way's tags,
  and its miles are reported apart (``GeometryPath.yard_miles``) so the
  caller can hold the chain floor against PUBLIC miles alone.
* ASSUMED: a military site is recognised only by tags on the way itself. A
  base's internal roads tagged plain ``access=private`` would pass here; the
  endpoint screen, which refuses military endpoints, is what keeps them out.

This module is pure graph code with no OSM reader, so it can be tested on a
synthetic graph.
"""

from __future__ import annotations

import heapq
from typing import Any

# Node barriers a vehicle drives over or through without being stopped.
# READ from the OSM barrier documentation: every other `barrier` value on a
# way node (gate, lift_gate, swing_gate, bollard, block, chain, ...) closes it.
PASSABLE_BARRIERS = frozenset(
    {"cattle_grid", "toll_booth", "entrance", "kerb", "height_restrictor", "bump_gate"}
)
# A node's own access tags can open its barrier to traffic.
_OPEN_ACCESS = frozenset({"yes", "permissive", "designated", "destination", "delivery"})
_TRUCK_KEYS = ("motor_vehicle", "vehicle", "hgv", "goods")


def bans_trucks(tags: dict[str, str]) -> bool:
    """READ: the way is signed closed to motor vehicles or to trucks."""
    return any(tags.get(key) == "no" for key in _TRUCK_KEYS)


def is_yard_road(tags: dict[str, str], routable_highways: set[str] | frozenset[str]) -> bool:
    """READ: a private surface road a truck bound for the site may use."""
    if tags.get("highway", "") not in routable_highways:
        return False
    if tags.get("access") != "private":
        return False
    if tags.get("motorroad") == "yes" or tags.get("service") == "emergency_access":
        return False
    if "military" in tags or tags.get("landuse") == "military":
        return False
    return not bans_trucks(tags)


def is_blocking_barrier(tags: dict[str, str]) -> bool:
    """READ: a node that stops a vehicle on the way it sits on."""
    barrier = tags.get("barrier", "")
    if not barrier or barrier in PASSABLE_BARRIERS:
        return False
    return not any(tags.get(key) in _OPEN_ACCESS for key in ("access", *_TRUCK_KEYS))


def yard_road_path(
    graph: Any,
    start_ref: int,
    end_ref: int,
) -> tuple[list[int], list[bool]] | None:
    """The shortest path city context -> endpoint whose private ways form one
    stretch at the endpoint, or None.

    Returns the node refs in travel order and, per edge, whether that edge
    belongs to the yard stretch. ``graph`` is a ``RouteGraph``: ``edges`` are
    public, ``yard_edges`` private, ``barriers`` the blocking barrier nodes,
    ``no_truck`` the public edges signed against trucks.
    """
    # 1. Everything the city context reaches over PUBLIC roads. A barrier node
    #    is reached but never driven through, and a no-truck edge is not used.
    pub_dist: dict[int, float] = {start_ref: 0.0}
    pub_prev: dict[int, int] = {}
    heap: list[tuple[float, int]] = [(0.0, start_ref)]
    while heap:
        miles, node = heapq.heappop(heap)
        if miles > pub_dist.get(node, float("inf")) or node in graph.barriers:
            continue
        for nxt, edge_miles, _road, _mph in graph.edges.get(node, ()):
            if (node, nxt) in graph.no_truck:
                continue
            nd = miles + edge_miles
            if nd < pub_dist.get(nxt, float("inf")):
                pub_dist[nxt] = nd
                pub_prev[nxt] = node
                heapq.heappush(heap, (nd, nxt))
    if end_ref in pub_dist:
        return None  # a public path exists; this rule has nothing to add

    # 2. Grow outward from the endpoint. State is (node, arrived over a private
    #    edge), because a barrier node may be crossed private <-> public (the
    #    yard's gate) but never public -> public (a gate on a public way).
    #    A node the public search reached is an exit and is never grown past,
    #    which is what keeps the private ways in one stretch at this end.
    first = (end_ref, True)
    yard_dist: dict[tuple[int, bool], float] = {first: 0.0}
    yard_prev: dict[tuple[int, bool], tuple[int, bool]] = {}
    exits: list[tuple[float, tuple[int, bool]]] = []
    yard_heap: list[tuple[float, int, bool]] = [(0.0, end_ref, True)]
    while yard_heap:
        miles, node, by_private = heapq.heappop(yard_heap)
        state = (node, by_private)
        if miles > yard_dist.get(state, float("inf")):
            continue
        steps = [(nxt, m, True) for nxt, m in graph.yard_edges.get(node, ())]
        steps += [
            (nxt, m, False)
            for nxt, m, _road, _mph in graph.edges.get(node, ())
            if (node, nxt) not in graph.no_truck
        ]
        for nxt, edge_miles, private in steps:
            if node in graph.barriers and not by_private and not private:
                continue
            nxt_state = (nxt, private)
            nd = miles + edge_miles
            if nd >= yard_dist.get(nxt_state, float("inf")):
                continue
            if nxt in pub_dist:
                if nxt in graph.barriers and not private:
                    continue  # public -> gate -> public
                yard_dist[nxt_state] = nd
                yard_prev[nxt_state] = state
                exits.append((nd + pub_dist[nxt], nxt_state))
                continue
            yard_dist[nxt_state] = nd
            yard_prev[nxt_state] = state
            heapq.heappush(yard_heap, (nd, nxt, private))
    if not exits:
        return None
    _total, exit_state = min(exits, key=lambda item: (item[0], item[1]))

    # 3. Stitch: city context -> exit over public roads, exit -> endpoint over
    #    the yard stretch.
    public_nodes = [exit_state[0]]
    while public_nodes[-1] != start_ref:
        public_nodes.append(pub_prev[public_nodes[-1]])
    public_nodes.reverse()
    yard_nodes: list[int] = []
    used_private = False
    state = exit_state
    while state != first:
        used_private = used_private or state[1]
        state = yard_prev[state]
        yard_nodes.append(state[0])
    if not used_private:
        return None
    nodes = public_nodes + yard_nodes
    flags = [False] * (len(public_nodes) - 1) + [True] * len(yard_nodes)
    return nodes, flags
