"""The street detail a facility chain carries (owner order, 2026-09-24: the
streets from the ramp end to the facility made realistic): the posted limit
and what kind of value it is, the controls at the intersections, the
driveway, and one chain from every ramp terminal a delivery can arrive at."""

import importlib.util
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import street_chain  # noqa: E402

FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="fixture">
  <node id="100" lat="41.0000" lon="-87.0100" />
  <node id="101" lat="41.0000" lon="-87.0050" />
  <node id="1" lat="41.0000" lon="-87.0000">
    <tag k="highway" v="traffic_signals" />
  </node>
  <node id="2" lat="41.0030" lon="-87.0000" />
  <node id="21" lat="41.0048" lon="-87.0000">
    <tag k="highway" v="stop" />
    <tag k="direction" v="forward" />
  </node>
  <node id="3" lat="41.0050" lon="-87.0000" />
  <node id="30" lat="41.0050" lon="-86.9950" />
  <node id="4" lat="41.0080" lon="-87.0000" />
  <node id="5" lat="41.0080" lon="-86.9950" />
  <node id="6" lat="41.0085" lon="-86.9950" />
  <way id="50">
    <nd ref="100" /><nd ref="101" /><nd ref="1" />
    <tag k="highway" v="primary" />
    <tag k="name" v="Exit Road" />
    <tag k="maxspeed" v="45 mph" />
  </way>
  <way id="10">
    <nd ref="1" /><nd ref="2" /><nd ref="21" /><nd ref="3" /><nd ref="4" />
    <tag k="highway" v="tertiary" />
    <tag k="name" v="Terminal Road" />
  </way>
  <way id="60">
    <nd ref="3" /><nd ref="30" />
    <tag k="highway" v="residential" />
    <tag k="name" v="Side Street" />
  </way>
  <way id="20">
    <nd ref="4" /><nd ref="5" />
    <tag k="highway" v="service" />
    <tag k="name" v="Warehouse Drive" />
  </way>
  <way id="40">
    <nd ref="5" /><nd ref="6" />
    <tag k="building" v="warehouse" />
    <tag k="name" v="Real Warehouse" />
  </way>
</osm>
"""


def _load_tool():
    pytest.importorskip("osmium")
    path = TOOLS / "build_facility_approaches.py"
    spec = importlib.util.spec_from_file_location("build_facility_approaches", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def baked(tmp_path, monkeypatch):
    tool = _load_tool()
    osm_path = tmp_path / "streets.osm"
    osm_path.write_text(FIXTURE, encoding="utf-8")
    target = tool.FacilityTarget(
        facility_id="fixture:warehouse",
        city="fixture_city",
        state="Illinois",
        facility_name="Fixture Warehouse",
        facility_type="warehouse",
        endpoint_name="Real Warehouse",
        lat=41.0080,
        lon=-86.9950,
        start_lat=41.0000,
        start_lon=-87.0000,
        endpoint_source_backed=True,
        endpoint_fallback=False,
        endpoint_source_note="fixture",
        local_approach_miles=0.8,
        local_approach_road="Terminal Road",
        endpoint_source_ref="way/40",
    )
    exit_info = {"from": "a", "to": "fixture_city", "highway": "I-1", "exit_ref": "7"}
    terminals = {
        "fixture_city": [
            {"node": 100, "lat": 41.0, "lon": -87.01, "exit": exit_info},
            # A terminal on no road of the graph: a failure, never a snap.
            {"node": 999, "lat": 41.0, "lon": -87.0101, "exit": exit_info},
        ]
    }
    monkeypatch.setattr(tool, "collect_targets", lambda: [target])
    monkeypatch.setattr(tool, "city_exit_terminals", lambda: terminals)
    monkeypatch.setattr(tool, "MIN_PLAYABLE_ROUTE_MI", 0.1)
    local_geometry = tool._load_local_geometry_tool()
    monkeypatch.setattr(local_geometry, "state_extract_path", lambda _cache, _state: osm_path)
    monkeypatch.setattr(tool, "_load_local_geometry_tool", lambda: local_geometry)
    payload = tool.build_facility_approaches(tmp_path, states=("Illinois",), max_route_mi=2.0)
    return payload, payload["approaches"]["fixture:warehouse"]


def test_a_chain_starts_at_the_ramp_terminal_and_is_kept_whole(baked):
    _payload, record = baked
    [chain] = record["exit_chains"]
    assert chain["terminal_node"] == 100
    assert chain["exit"]["exit_ref"] == "7"
    assert [seg["road"] for seg in chain["segments"]] == [
        "Exit Road",
        "Terminal Road",
        "Warehouse Drive",
    ]
    assert chain["segments"][0]["cue"] == "Start on Exit Road."
    assert record["exit_chains_failed"] == [
        {"terminal_node": 999, "route_failure": "terminal_off_graph"}
    ]
    # The city-centre chain is still there for the departure.
    assert [seg["road"] for seg in record["segments"]] == ["Terminal Road", "Warehouse Drive"]


def test_each_street_says_whether_its_limit_was_read_or_filled_in(baked):
    _payload, record = baked
    exit_road, terminal_road, drive = record["exit_chains"][0]["segments"]
    assert (exit_road["limit_mph"], exit_road["limit_source"]) == (45.0, "read")
    assert terminal_road["limit_source"] == "statutory"
    assert terminal_road["limit_mph"] == street_chain.statutory_mph("Illinois") == 30.0
    # Past the driveway no district statute reaches: the old default, labelled.
    assert (drive["limit_mph"], drive["limit_source"]) == (25.0, "assumed")


def test_controls_are_read_at_the_turn_and_along_the_street(baked):
    _payload, record = baked
    exit_road, terminal_road, drive = record["exit_chains"][0]["segments"]
    # The signal on the turn node; the stop sign drawn before Side Street,
    # facing the truck, binds that intersection.
    assert terminal_road["controls"][0] == {"at_mi": 0.0, "kind": "signal"}
    assert terminal_road["controls"][1]["kind"] == "stop"
    assert 0.3 < terminal_road["controls"][1]["at_mi"] < terminal_road["miles"]
    assert exit_road["controls"] == []
    # OSM is silent at the turn into the driveway: no entry, never a guess.
    assert drive["controls"] == []
    # On the city-centre chain the signal is the start, not a corner.
    assert [c["kind"] for c in record["segments"][0]["controls"]] == ["stop"]


def test_the_driveway_is_where_the_public_street_ends(baked):
    payload, record = baked
    chain = record["exit_chains"][0]
    driveway = chain["driveway"]
    assert driveway["kind"] == "service_road"
    assert driveway["node"] == 4
    miles = [seg["miles"] for seg in chain["segments"]]
    assert driveway["at_mi"] == round(miles[0] + miles[1], 2)
    assert driveway["source"].startswith("derived")
    assert record["driveway"]["node"] == 4
    streets = payload["coverage"]["streets"]["exit_chains"]
    assert streets["chains"] == 1
    assert streets["driveways"] == 1
    assert streets["turns"] == 2
    assert streets["turns_with_control"] == 1
    assert streets["terminals_failed"] == {"terminal_off_graph": 1}


def test_a_stop_facing_the_other_way_binds_nothing_but_a_signal_binds_its_junction():
    # Path 0-1-2-3-4, junctions at 1 and 3; a control mid-block at 2, nearer 3.
    def run(control, forward_edges):
        segments = [
            {
                "road": "A",
                "miles": 0.4,
                "speed_mph": 25.0,
                "_first_edge": 0,
                "_end_edge": 4,
                "_raw_miles": 0.4,
                "_read_miles": 0.0,
            }
        ]
        street_chain.annotate(
            segments,
            [0, 1, 2, 3, 4],
            [(0.0, 0.0)] * 5,
            [0.1, 0.15, 0.05, 0.1],
            ["street"] * 4,
            forward_edges,
            {2: control},
            {1: 3, 3: 3},
            "Nowhere",
        )
        return segments[0]["controls"]

    # Drawn against the truck's travel: a stop binds nobody on this path...
    assert run(("stop", "backward"), {(1, 2)}) == []
    # ...a signal still means the junction behind it is signalled.
    assert run(("signal", "backward"), {(1, 2)}) == [{"at_mi": 0.1, "kind": "signal"}]
    # With the truck: the junction ahead.
    assert run(("stop", "forward"), {(1, 2)}) == [{"at_mi": 0.3, "kind": "stop"}]
    # Untagged: the nearer junction, here the one ahead.
    assert run(("stop", ""), set()) == [{"at_mi": 0.3, "kind": "stop"}]


def test_control_tags_are_read_as_written():
    assert street_chain.control_of({"highway": "stop", "stop": "all"}) == ("all_way_stop", "")
    assert street_chain.control_of(
        {"highway": "traffic_signals", "traffic_signals:direction": "backward"}
    ) == ("signal", "backward")
    assert street_chain.control_of({"highway": "give_way", "direction": "NE"}) == ("give_way", "")
    assert street_chain.control_of({"highway": "crossing"}) is None


def test_exit_terminals_follow_the_games_destination_exit_rule():
    def ix(at, ref, fwd=None, back=None):
        out = {"at_mi": at, "exit_ref": ref}
        if fwd:
            out["ramp_terminal_forward"] = {"node": fwd, "lat": 1.0, "lon": 2.0}
        if back:
            out["ramp_terminal_backward"] = {"node": back, "lat": 1.0, "lon": 2.0}
        return out

    legs = [
        {
            "from": "a",
            "to": "b",
            "miles": 50.0,
            "highway": "I-1",
            "corridor": {
                "interchanges": [
                    ix(1.0, "1", fwd=11, back=12),
                    ix(2.0, "", fwd=21, back=22),  # unlabelled: never the exit
                    ix(48.0, "48", fwd=481, back=482),
                ]
            },
        }
    ]
    found = street_chain.exit_terminals(legs)
    # Arriving at b (travel a->b): the labelled exit nearest b, forward ramp.
    assert [t["node"] for t in found["b"]] == [481]
    # Arriving at a (travel b->a): exit 1, backward ramp.
    assert [t["node"] for t in found["a"]] == [12]
    assert found["a"][0]["exit"]["direction"] == "backward"
