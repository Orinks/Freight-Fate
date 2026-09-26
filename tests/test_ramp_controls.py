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
        "node_locs": {3: (40.0, -80.0)},
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
        "node_locs": {3: (40.0, -80.0)},
        "control_grid": m._GoreGrid([]),
        "grid": m._GoreGrid([(40.001, -80.001, 1)]),
    }
    _, _, ends = m.classify_exit_far_end(40.001, -80.001, topo, 500.0)
    assert m.controls_at_terminals(ends, topo) == {"roundabout"}


def _path_m(m, locs, ids):
    return sum(m._gore_distance_m(*locs[a], *locs[b]) for a, b in zip(ids, ids[1:], strict=False))


def test_ramp_length_is_measured_along_the_way_to_the_surface_end():
    """The length follows the bent ramp, not the straight line, and a surface
    terminal wins over a nearer merge (a C-D branch rejoining the mainline)."""
    m = _topo_tools()
    locs = {
        1: (40.0, -80.0),  # gore
        2: (40.002, -80.0),
        3: (40.002, -80.002),  # crossroad
        4: (40.0025, -80.0),  # merge back onto the mainline, nearer than 3
    }
    graph = m.build_ramp_link_graph(
        [([1, 2, 3], "yes"), ([2, 4], "yes")],
        motorway_node_ids={1, 4},
        crossroad_node_ids={3},
    )
    length = m.ramp_length_m(graph, locs, 1)
    assert abs(length - _path_m(m, locs, [1, 2, 3])) < 1e-6
    assert length > m._gore_distance_m(*locs[1], *locs[3]) + 50.0
    # With no surface end at all, the merge is the terminal.
    system = m.build_ramp_link_graph([([1, 2, 4], "yes")], motorway_node_ids={1, 4})
    assert abs(m.ramp_length_m(system, locs, 1) - _path_m(m, locs, [1, 2, 4])) < 1e-6


def test_ramp_length_screen_drops_and_counts_contradictions():
    m = _topo_tools()
    stats: dict[str, int] = {}
    assert m.screen_ramp_length_ft(299.0, stats) is None
    assert m.screen_ramp_length_ft(1.5 * 5280.0 + 1.0, stats) is None
    assert m.screen_ramp_length_ft(None, stats) is None
    assert m.screen_ramp_length_ft(1200.0, stats) == 1200.0
    assert stats == {"length_too_short": 1, "length_too_long": 1, "length_unmeasured": 1}


def test_ramp_lengths_bake_per_direction_from_the_nearest_gore():
    """Northbound leg: a ramp leaving northward is the forward exit, one
    leaving southward the backward one. A farther forward gore in range loses
    to the nearer, and a too-short ramp bakes nothing for its direction."""
    m = _topo_tools()
    locs = {
        10: (40.049, -80.0),  # forward gore
        11: (40.051, -80.0005),
        12: (40.053, -80.001),  # crossroad
        20: (40.0515, -80.0002),  # backward gore
        21: (40.0495, -80.0007),
        22: (40.048, -80.001),  # crossroad
        30: (40.045, -80.0),  # farther forward gore (a neighbor's)
        31: (40.0452, -80.0003),  # crossroad after ~35 m
    }
    graph = m.build_ramp_link_graph(
        [([10, 11, 12], "yes"), ([20, 21, 22], "yes"), ([30, 31], "yes")],
        motorway_node_ids={10, 20, 30},
        crossroad_node_ids={12, 22, 31},
    )
    topo = {
        "graph": graph,
        "node_locs": locs,
        "grid": m._GoreGrid([(*locs[g], g) for g in (10, 20, 30)]),
    }
    geom = [(40.0, -80.0, 0.0), (40.05, -80.0, 3.45), (40.1, -80.0, 6.9)]
    leg = {"miles": 6.9, "corridor": {"interchanges": [{"at_mi": 3.45, "name": "Test"}]}}
    stats: dict[str, int] = {}
    assert m.bake_ramp_lengths_for_leg(leg, topo, geom, {}, stats) == 1
    ix = leg["corridor"]["interchanges"][0]
    assert ix["ramp_length_ft_forward"] == round(_path_m(m, locs, [10, 11, 12]) * m.M_TO_FT, 1)
    assert ix["ramp_length_ft_backward"] == round(_path_m(m, locs, [20, 21, 22]) * m.M_TO_FT, 1)
    assert ix["ramp_length_source"].startswith("derived from OpenStreetMap geometry")
    # The node each ramp ends at is kept, so a street chain can start there.
    assert ix["ramp_terminal_forward"] == {"node": 12, "lat": 40.053, "lon": -80.001}
    assert ix["ramp_terminal_backward"]["node"] == 22
    assert ix["ramp_terminal_source"].startswith("read from OpenStreetMap topology")
    # The neighbor's short ramp alone: its direction bakes nothing, counted.
    lone = {**topo, "grid": m._GoreGrid([(*locs[30], 30)])}
    leg2 = {"miles": 6.9, "corridor": {"interchanges": [{"at_mi": 3.45, "name": "Test"}]}}
    stats2: dict[str, int] = {}
    assert m.bake_ramp_lengths_for_leg(leg2, lone, geom, {}, stats2) == 0
    assert "ramp_length_ft_forward" not in leg2["corridor"]["interchanges"][0]
    assert "ramp_terminal_forward" not in leg2["corridor"]["interchanges"][0]
    assert stats2["length_too_short"] == 1


def test_a_ramp_that_ends_in_a_merge_has_no_street_terminal():
    m = _topo_tools()
    locs = {1: (40.0, -80.0), 2: (40.002, -80.0), 4: (40.0025, -80.0)}
    system = m.build_ramp_link_graph([([1, 2, 4], "yes")], motorway_node_ids={1, 4})
    length, node = m.ramp_end(system, locs, 1)
    assert node is None and length > 0


def test_only_a_public_road_ends_a_ramp_mid_link():
    """Baltimore, node 9879536272: a two-node service stub touching a ramp
    before its real terminal became "the terminal", and the street chain
    from it had no street to start on."""
    m = _topo_tools()
    assert m.is_public_crossroad("residential")
    assert m.is_public_crossroad("trunk")
    assert not m.is_public_crossroad("service")
    assert not m.is_public_crossroad("track")
    assert not m.is_public_crossroad("footway")
    assert not m.is_public_crossroad("tertiary", "private")


def _leg_with_saved_control(m, monkeypatch, at_mi):
    graph = m.build_ramp_link_graph(
        [([1, 2, 3], "yes")], motorway_node_ids={1}, crossroad_node_ids={3}
    )
    topo = {
        "graph": graph,
        "toll": set(),
        "roundabout": set(),
        "node_locs": {3: (40.0503, -80.0)},
        "control_grid": m._GoreGrid([(40.0503, -80.0, "signal")]),
        "grid": m._GoreGrid([(40.05, -80.0, 1)]),
    }
    geom = [(40.0, -80.0, 0.0), (40.05, -80.0, 3.45), (40.1, -80.0, 6.9)]
    monkeypatch.setattr(m, "leg_corridor_geometry", lambda _leg, _rate: geom)
    ix = {
        "at_mi": at_mi,
        "name": "Test",
        "ramp_control": "stop",
        "ramp_control_source": "an older bake",
        "ramp_far_end": "surface",
    }
    return {"miles": 6.9, "corridor": {"interchanges": [ix]}}, topo, ix


def test_every_run_rejudges_an_exit_from_the_evidence(monkeypatch):
    """--force and a plain run disagreed on 40 exits: the plain run kept any
    exit that already had a control and a far end, whatever bake made it."""
    m = _topo_tools()
    leg, topo, ix = _leg_with_saved_control(m, monkeypatch, 3.45)
    m.bake_ramp_controls_for_leg(leg, [], 1.0, junction_refs={}, topo=topo, stats={})
    assert ix["ramp_control"] == "signal"
    assert ix["ramp_control_source"] == m.RAMP_CONTROL_TERMINAL_SOURCE
    assert ix["ramp_far_end"] == "surface"


def test_an_unpinned_exit_on_a_drifted_leg_gets_no_new_verdict(monkeypatch):
    m = _topo_tools()
    leg, topo, ix = _leg_with_saved_control(m, monkeypatch, 3.45)
    stats: dict[str, int] = {}
    m.bake_ramp_controls_for_leg(
        leg, [], 1.0, junction_refs={}, topo=topo, stats=stats, withhold_unpinned=True
    )
    assert ix["ramp_control"] == "stop" and stats["withheld"] == 1


def test_an_exit_mid_tangent_is_looked_up_where_it_is():
    """The archive keeps two vertices for a ten-mile straight; the exit at
    mile 5 is halfway between them, not at either end."""
    m = _topo_tools()
    geom = [(40.0, -80.0, 0.0), (40.2, -80.0, 10.0)]
    lat, lon = m._exit_location(geom, 5.0, 10.0)
    assert abs(lat - 40.1) < 1e-9 and lon == -80.0
    assert m._exit_location(geom, 12.0, 10.0) == (40.2, -80.0)


def test_exit_mileage_is_measured_against_its_own_junctions():
    import exit_position_screen as screen

    geom = [(40.0 + i * 0.01, -80.0, i * 0.69) for i in range(11)]
    refs = {"1": [(40.01, -80.0)], "2": [(40.05, -80.0)], "3": [(40.09, -80.0)]}
    on_time = [
        {"exit_ref": "1", "at_mi": 0.69},
        {"exit_ref": "2", "at_mi": 3.45},
        {"exit_ref": "3", "at_mi": 6.21},
    ]
    assert screen.leg_position_drift_mi(geom, on_time, 6.9, refs, 500.0) == 0.0
    shifted = [{**ix, "at_mi": ix["at_mi"] + 2.0} for ix in on_time]
    assert screen.leg_position_drift_mi(geom, shifted, 6.9, refs, 500.0) > 1.9
    # Too few matches to judge.
    assert screen.leg_position_drift_mi(geom, on_time[:2], 6.9, refs, 500.0) is None
