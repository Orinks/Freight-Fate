"""Ramp terminal controls (owner, 2026-08-17: "no stop signs at the end of
ramps").

The one case that is never a matter of taste is a ramp onto another
freeway -- an interstate meeting an interstate ends in a merge, and nothing
stops traffic there. The bake reads controls off OSM nodes where they exist,
walks link topology for the far end everywhere else, and the seeded heuristic
only decides the exits neither could judge.
"""

import pytest

from freight_fate.states.driving_core import FREEWAY_VIA_RE


@pytest.mark.parametrize(
    "via, is_freeway",
    [
        ("I 20 WEST;I 59 SOUTH", True),
        ("I-70", True),
        ("I 65 NORTH", True),
        ("US 31 SOUTH;US 280", False),
        ("AL 75 NORTH", False),
        ("STATE ROUTE 3", False),
        ("", False),
        # The boundary that a missing \b would swallow: these end in "I"
        # followed by a number and are not interstates.
        ("HAWAII 1", False),
        ("MISSISSIPPI 3", False),
    ],
)
def test_only_a_real_interstate_reads_as_a_freeway(via, is_freeway):
    assert bool(FREEWAY_VIA_RE.search(via)) is is_freeway


def test_the_pattern_carries_a_word_boundary():
    """Pinned because it was briefly a literal backspace character.

    A shell-escaping slip wrote 0x08 into the source instead of backslash-b.
    It still compiled, still matched every interstate, and silently matched
    "HAWAII 1" too -- invisible in an editor and in a diff. The check builds
    the backslash with chr(92) so this assertion cannot fall into the same
    hole it exists to catch.
    """
    backslash = chr(92)
    assert FREEWAY_VIA_RE.pattern.startswith(backslash + "b")
    assert chr(8) not in FREEWAY_VIA_RE.pattern


def test_a_ramp_onto_a_freeway_is_free_flow_not_a_dice_roll(world):
    """The rule has to beat the heuristic, at every seed."""
    from freight_fate.states.driving_events import DrivingEventMixin

    class _Stop:
        at_mi = 10.0

    class _Interchange:
        via = "I 59 SOUTH"
        ramp_far_end = ""

    class _Trip:
        def ramp_control_at(self, mi, tol_mi=2.0):
            return ""

        def interchange_at(self, mi, tol_mi=2.0):
            return _Interchange()

        def _near_city(self, mi):
            return False

    fake = type(
        "D",
        (),
        {
            "trip": _Trip(),
            "trip_seed": 0,
            "_ramp_meets_a_freeway": DrivingEventMixin._ramp_meets_a_freeway,
        },
    )()
    for seed in range(40):
        fake.trip_seed = seed
        got = DrivingEventMixin._ramp_control_for(fake, _Stop())
        assert got == "none", f"seed {seed} put a {got} where two freeways meet"


def test_a_surface_road_ramp_still_takes_its_chances(world):
    """The heuristic is untouched everywhere it was defensible -- a rural
    diamond onto a US route really can be a stop sign."""
    from freight_fate.states.driving_events import DrivingEventMixin

    class _Stop:
        at_mi = 10.0

    class _Interchange:
        via = "US 31 SOUTH"
        ramp_far_end = ""

    class _Trip:
        def ramp_control_at(self, mi, tol_mi=2.0):
            return ""

        def interchange_at(self, mi, tol_mi=2.0):
            return _Interchange()

        def _near_city(self, mi):
            return False

    fake = type(
        "D",
        (),
        {
            "trip": _Trip(),
            "trip_seed": 0,
            "_ramp_meets_a_freeway": DrivingEventMixin._ramp_meets_a_freeway,
        },
    )()
    seen = set()
    for seed in range(60):
        fake.trip_seed = seed
        seen.add(DrivingEventMixin._ramp_control_for(fake, _Stop()))
    assert seen - {"none"}, "a surface ramp should still vary"


def test_the_seeded_ramp_control_weights_match_the_ramps_osm_did_tag():
    """The fallback split is calibrated against the bake, not invented.

    Of the baked interchanges OSM tags with a control, the signal-to-stop
    split is 88.7 / 11.3 near a route city and 64.3 / 35.7 away from one.
    Both halves are readings there -- a light and a stop sign are equally
    taggable -- so the ratio the heuristic hands out for an untagged ramp
    has no business disagreeing with them. It used to: the rural pair
    asserted 30 / 50, twice the stop signs reality carries.

    Free flow is the assumed share and is deliberately NOT pinned to data,
    because there is none: OSM records the controls that exist and is silent
    where a ramp merges freely, so absence of a tag is not evidence of free
    flow. It stays declared in the weights and called out in the comment.
    """
    from freight_fate.states.driving_core import (
        RAMP_CONTROL_RURAL_WEIGHTS,
        RAMP_CONTROL_URBAN_WEIGHTS,
    )

    for label, (signal_w, stop_w), measured in (
        ("urban", RAMP_CONTROL_URBAN_WEIGHTS, 0.887),
        ("rural", RAMP_CONTROL_RURAL_WEIGHTS, 0.643),
    ):
        controlled = stop_w  # everything below the free-flow line
        share = signal_w / controlled
        assert abs(share - measured) < 0.01, (
            f"{label}: {share:.3f} of controlled ramps get a light, but the "
            f"baked ramps OSM tagged say {measured:.3f}"
        )


# --- The walked far end: topology beats signage, and both beat the dice ---


def _topo_tools():
    import sys
    from pathlib import Path

    tools = str(Path(__file__).resolve().parents[1] / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import build_interchanges_rampcontrols as m

    return m


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


def _fake_driver(via, ramp_far_end):
    from freight_fate.states.driving_events import DrivingEventMixin

    class _Interchange:
        pass

    _Interchange.via = via
    _Interchange.ramp_far_end = ramp_far_end

    class _Trip:
        def ramp_control_at(self, mi, tol_mi=2.0):
            return ""

        def interchange_at(self, mi, tol_mi=2.0):
            return _Interchange()

        def _near_city(self, mi):
            return False

    return type(
        "D",
        (),
        {
            "trip": _Trip(),
            "trip_seed": 0,
            "_ramp_meets_a_freeway": DrivingEventMixin._ramp_meets_a_freeway,
        },
    )()


def test_a_baked_surface_far_end_silences_the_signage_guess(world):
    """An exit signed toward I-95 whose ramp provably ends at a surface road
    must NOT be called free flow -- this was the via guess's one-in-three
    wrong call, and the walked topology exists to overrule it."""
    from freight_fate.states.driving_events import DrivingEventMixin

    class _Stop:
        at_mi = 10.0

    fake = _fake_driver("I 95 NORTH", "surface")
    seen = set()
    for seed in range(60):
        fake.trip_seed = seed
        seen.add(DrivingEventMixin._ramp_control_for(fake, _Stop()))
    assert seen - {"none"}, "a proven surface terminal should roll for a control"


def test_a_baked_motorway_far_end_is_free_flow_whatever_the_via_says(world):
    from freight_fate.states.driving_events import DrivingEventMixin

    class _Stop:
        at_mi = 10.0

    fake = _fake_driver("US 30 WEST", "motorway")
    for seed in range(40):
        fake.trip_seed = seed
        got = DrivingEventMixin._ramp_control_for(fake, _Stop())
        assert got == "none", f"seed {seed} put a {got} at a proven merge"


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


def test_a_scale_ramp_flows_to_the_scale_not_a_dice_roll(world):
    """A weigh station's ramp is its own deceleration lane into the
    inspection queue -- no crossroad, no light, no stop sign. The dice used
    to put a stop sign there, spoken with the mainline's limit on its far
    side (owner playtest, 2026-08-20)."""
    from freight_fate.states.driving_events import DrivingEventMixin

    class _Stop:
        at_mi = 10.0
        type = "weigh_station"

    class _Trip:
        def ramp_control_at(self, mi, tol_mi=2.0):
            raise AssertionError("a scale ramp never consults the baked control")

        def interchange_at(self, mi, tol_mi=2.0):
            return None

        def _near_city(self, mi):
            return False

    fake = type(
        "D",
        (),
        {
            "trip": _Trip(),
            "trip_seed": 0,
            "_ramp_meets_a_freeway": DrivingEventMixin._ramp_meets_a_freeway,
        },
    )()
    for seed in range(20):
        fake.trip_seed = seed
        assert DrivingEventMixin._ramp_control_for(fake, _Stop()) == "none"
