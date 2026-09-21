"""Ramp terminal controls (owner, 2026-08-17: "no stop signs at the end of
ramps").

The one case that is never a matter of taste is a ramp onto another
freeway -- an interstate meeting an interstate ends in a merge, and nothing
stops traffic there. The bake reads controls off OSM nodes where they exist,
walks link topology for the far end everywhere else, and the seeded heuristic
only decides the exits neither could judge.
"""

import json
from pathlib import Path


def _topo_tools():
    import sys
    from pathlib import Path

    tools = str(Path(__file__).resolve().parents[1] / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import build_interchanges

    return build_interchanges._RAMPCONTROL_MODULE


def test_production_harvester_bakes_directional_advisories_end_to_end():
    """A deterministic PBF-boundary fixture exercises the production path."""
    m = _topo_tools()
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "ramp_advisory_harvest.json").read_text()
    )
    observations = []
    for way in fixture["ways"]:
        locations = {int(k): tuple(v) for k, v in way["locations"].items()}
        observations.extend(
            m.advisory_observations_for_way(way["refs"], way["oneway"], way["tags"], locations)
        )
    geom = [
        (point["lat"], point["lon"], point["at_mi"])
        for point in fixture["leg"]["corridor"]["route_points"]
    ]
    assert m.bake_ramp_advisories_for_leg(fixture["leg"], observations, geom) == 1
    interchange = fixture["leg"]["corridor"]["interchanges"][0]
    assert interchange == fixture["expected_interchange"]
    assert "(read; directional suffix resolved" in interchange["ramp_advisory_source"]


def test_a_gore_is_a_departure_not_a_merge():
    """An on-ramp's mainline touch point has only an inbound link edge and
    must not be walked as an exit."""
    m = _topo_tools()
    # Way A: off-ramp 1 -> 2 -> 3. Way B: on-ramp 4 -> 5 -> 6. Mainline
    # carries 1 (gore of A) and 6 (merge of B).
    graph = m.build_ramp_link_graph(
        [([1, 2, 3], "yes"), ([4, 5, 6], "yes")],
        motorway_node_ids={1, 6},
    )
    assert graph["gores"] == [1]


def test_a_service_ramp_walks_to_a_road_end():
    m = _topo_tools()
    graph = m.build_ramp_link_graph([([1, 2, 3], "yes")], motorway_node_ids={1})
    terminals, tolled, ends = m.walk_far_ends(graph, 1)
    assert terminals == {"road-end"} and not tolled
    assert ends == {3}
    assert m.classify_gore(terminals, tolled) == "surface"


def test_a_system_ramp_walks_back_onto_the_mainline():
    m = _topo_tools()
    graph = m.build_ramp_link_graph([([1, 2, 3], "yes")], motorway_node_ids={1, 3})
    terminals, tolled, ends = m.walk_far_ends(graph, 1)
    assert terminals == {"motorway"}
    assert ends == set()
    assert m.classify_gore(terminals, tolled) == "motorway"


def test_a_reversed_oneway_ramp_walks_against_node_order():
    m = _topo_tools()
    # Drawn 3 -> 2 -> 1 with oneway=-1: travel is 1 -> 2 -> 3.
    graph = m.build_ramp_link_graph([([3, 2, 1], "-1")], motorway_node_ids={1, 3})
    assert graph["gores"] == [1]
    terminals, _, _ = m.walk_far_ends(graph, 1)
    assert terminals == {"motorway"}


def test_a_toll_booth_on_the_chain_vetoes_free_flow():
    """A turnpike trumpet merges motorway-to-motorway THROUGH a plaza;
    nothing about that is free flow."""
    m = _topo_tools()
    graph = m.build_ramp_link_graph([([1, 2, 3], "yes")], motorway_node_ids={1, 3})
    terminals, tolled, _ = m.walk_far_ends(graph, 1, toll_nodes={2})
    assert tolled
    assert m.classify_gore(terminals, tolled) == ""


def test_a_ramp_ending_on_a_trunk_is_not_a_proven_merge():
    """Free flow onto an expressway is LIKELY but trunks carry signals too;
    the walk reports it and the verdict stays conservative."""
    m = _topo_tools()
    graph = m.build_ramp_link_graph([([1, 2, 3], "yes")], motorway_node_ids={1}, trunk_node_ids={3})
    terminals, tolled, ends = m.walk_far_ends(graph, 1)
    assert terminals == {"trunk"}
    assert ends == {3}
    assert m.classify_gore(terminals, tolled) == "surface"


def test_one_surface_chain_outvotes_any_number_of_merges():
    """A mixed service-plus-system interchange has a controllable terminal;
    only an all-merge exit may bake free flow."""
    m = _topo_tools()
    graph = m.build_ramp_link_graph(
        [([1, 2, 3], "yes"), ([10, 11, 12], "yes")],
        motorway_node_ids={1, 3, 10},
    )
    topo = {
        "graph": graph,
        "toll": set(),
        "grid": m._GoreGrid([(40.0, -80.0, 1), (40.001, -80.001, 10)]),
    }
    far_end, gores, ends = m.classify_exit_far_end(40.0005, -80.0005, topo, 500.0)
    assert gores == 2
    assert far_end == "surface"
    assert 12 in ends


def test_an_all_merge_exit_reads_as_motorway():
    m = _topo_tools()
    graph = m.build_ramp_link_graph(
        [([1, 2, 3], "yes"), ([10, 11, 12], "yes")],
        motorway_node_ids={1, 3, 10, 12},
    )
    topo = {
        "graph": graph,
        "toll": set(),
        "grid": m._GoreGrid([(40.0, -80.0, 1), (40.001, -80.001, 10)]),
    }
    far_end, gores, ends = m.classify_exit_far_end(40.0005, -80.0005, topo, 500.0)
    assert far_end == "motorway" and gores == 2
    assert ends == set()


def test_no_gore_in_range_is_no_verdict():
    m = _topo_tools()
    graph = m.build_ramp_link_graph([([1, 2, 3], "yes")], motorway_node_ids={1})
    topo = {"graph": graph, "toll": set(), "grid": m._GoreGrid([(41.0, -81.0, 1)])}
    far_end, gores, ends = m.classify_exit_far_end(40.0, -80.0, topo, 500.0)
    assert far_end == "" and gores == 0 and ends == set()


def test_the_walk_stops_at_the_crossroad_not_at_the_far_mainline():
    """A diamond whose off-ramp and on-ramp share the intersection node must
    read as a surface terminal, not as a merge reached THROUGH the
    intersection -- the first smoke leg classified every such diamond as a
    system interchange."""
    m = _topo_tools()
    # Off-ramp 1 -> 2 -> 3, crossroad at 3, on-ramp 3 -> 4 -> 5 back to the
    # mainline at 5.
    graph = m.build_ramp_link_graph(
        [([1, 2, 3], "yes"), ([3, 4, 5], "yes")],
        motorway_node_ids={1, 5},
        crossroad_node_ids={3},
    )
    terminals, tolled, ends = m.walk_far_ends(graph, 1)
    assert terminals == {"crossroad"}
    assert ends == {3}
    assert m.classify_gore(terminals, tolled) == "surface"


def test_controls_are_read_at_the_walked_terminal_itself():
    """A signal 60 m from where the chain actually ends is a reading; the
    same signal matched from an exit-wide 1400 m circle is how a neighbor's
    light ended up baked onto a system interchange."""
    m = _topo_tools()
    graph = m.build_ramp_link_graph(
        [([1, 2, 3], "yes")], motorway_node_ids={1}, crossroad_node_ids={3}
    )
    topo = {
        "graph": graph,
        "toll": set(),
        "roundabout": set(),
        "terminal_locs": {3: (40.0, -80.0)},
        # one signal ~50 m north of the terminal, one stop 3 km away
        "control_grid": m._GoreGrid([(40.00045, -80.0, "signal"), (40.027, -80.0, "stop")]),
        "grid": m._GoreGrid([(40.001, -80.001, 1)]),
    }
    _, _, ends = m.classify_exit_far_end(40.001, -80.001, topo, 500.0)
    kinds = m.controls_at_terminals(ends, topo)
    assert kinds == {"signal"}


def test_a_roundabout_terminal_reads_as_yieldish():
    m = _topo_tools()
    graph = m.build_ramp_link_graph(
        [([1, 2, 3], "yes")], motorway_node_ids={1}, crossroad_node_ids={3}
    )
    topo = {
        "graph": graph,
        "toll": set(),
        "roundabout": {3},
        "terminal_locs": {3: (40.0, -80.0)},
        "control_grid": m._GoreGrid([]),
        "grid": m._GoreGrid([(40.001, -80.001, 1)]),
    }
    _, _, ends = m.classify_exit_far_end(40.001, -80.001, topo, 500.0)
    assert m.controls_at_terminals(ends, topo) == {"roundabout"}
