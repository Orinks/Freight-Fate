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


def in_town(_kind: str, _lat: float, _lon: float) -> bool:
    """The fixture town judge: every fixture street is in town. The real
    bake judges by the Census boundaries, a local download CI does not have."""
    return True


def out_of_town(_kind: str, _lat: float, _lon: float) -> bool:
    return False


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
    payload = tool.build_facility_approaches(
        tmp_path, states=("Illinois",), max_route_mi=2.0, town_judge=in_town
    )
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
            town_judge=in_town,
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


def test_a_kept_chain_gets_its_detail_by_matching_its_own_streets(baked, tmp_path):
    """A chain from an earlier bake carries names and miles, not geometry.
    Its path is read back off the map by those, never re-routed."""
    _payload, record = baked
    tool = sys.modules["build_facility_approaches"]
    local_geometry = tool._load_local_geometry_tool()
    import chain_match

    recorded = [
        {k: seg[k] for k in ("road", "miles", "cue", "speed_mph", "turn_deg")}
        for seg in record["segments"]
    ]
    target = local_geometry.Target(
        target_id="fixture:warehouse",
        target_type="facility",
        city="fixture_city",
        state="Illinois",
        name="Real Warehouse",
        lat=41.0080,
        lon=-86.9950,
        start_lat=41.0,
        start_lon=-87.0,
        role="warehouse",
        estimated=False,
        fallback_reason="",
        approach_road="Terminal Road",
        approach_miles=0.8,
        source_note="fixture",
    )
    osm_path = tmp_path / "match.osm"
    osm_path.write_text(FIXTURE, encoding="utf-8")
    renamed = [{**recorded[0], "road": "Elsewhere Road"}, recorded[1]]
    matched: dict = {}
    local_geometry.route_state_targets(
        osm_path,
        [target],
        yard_roads=True,
        street_detail=True,
        match_chains={"fixture:warehouse": recorded},
        matched=matched,
        town_judge=in_town,
    )
    found = matched["fixture:warehouse"]
    assert [seg["limit_source"] for seg in found.segments] == ["statutory", "assumed"]
    kept = chain_match.apply_match(
        {"turn_level": True, "segments": recorded},
        chain_match.detail_of(found, tool.clean_segment),
    )
    assert kept["street_detail"] == "matched"
    assert [seg["road"] for seg in kept["segments"]] == ["Terminal Road", "Warehouse Drive"]
    assert kept["segments"][0]["controls"][0]["kind"] == "stop"
    assert kept["driveway"]["node"] == 4
    local_geometry.route_state_targets(
        osm_path,
        [target],
        yard_roads=True,
        street_detail=True,
        match_chains={"fixture:warehouse": renamed},
        matched=matched,
        town_judge=in_town,
    )
    assert matched["fixture:warehouse"] == chain_match.MATCH_NO_PATH


def test_a_street_split_under_two_refs_is_matched_as_one_run():
    import chain_match

    recorded = [
        {"road": "13th Street (I 35 Business)", "miles": 0.05},
        {"road": "13th Street", "miles": 0.89},
        {"road": "a service road", "miles": 0.2},
    ]
    assert chain_match.groups(recorded, chain_match.GENERIC_LABELS) == [[0, 1], [2]]
    fresh = [
        {
            "road": "13th Street (I 35 Business)",
            "miles": 0.94,
            "limit_mph": 30.0,
            "limit_source": "read",
            "controls": [{"at_mi": 0.5, "kind": "signal"}],
        },
        {
            "road": "a service road",
            "miles": 0.2,
            "limit_mph": 15.0,
            "limit_source": "assumed",
            "controls": [],
        },
    ]
    assert chain_match.same_chain(fresh, recorded, chain_match.GENERIC_LABELS)
    out = chain_match.adopt(recorded, fresh)
    assert [seg["limit_mph"] for seg in out] == [30.0, 30.0, 15.0]
    assert out[0]["controls"] == [] and out[1]["controls"] == [{"at_mi": 0.45, "kind": "signal"}]


def test_the_generic_labels_are_the_builders_own():
    import chain_match

    tool = _load_tool()
    assert chain_match.GENERIC_LABELS == tool._load_local_geometry_tool().GENERIC_ROADS


def test_the_first_street_is_aligned_at_the_junction_it_shares():
    import chain_match

    recorded = [{"road": "A Street", "miles": 0.5}, {"road": "B Street", "miles": 0.3}]
    fresh = [
        {
            "road": "A Street",
            "miles": 0.54,
            "limit_mph": 30.0,
            "limit_source": "read",
            "controls": [{"at_mi": 0.24, "kind": "stop"}],
        },
        {
            "road": "B Street",
            "miles": 0.3,
            "limit_mph": 25.0,
            "limit_source": "statutory",
            "controls": [{"at_mi": 0.0, "kind": "signal"}],
        },
    ]
    # The first street's length is not evidence; the second's is.
    assert chain_match.same_chain(fresh, recorded, chain_match.GENERIC_LABELS)
    assert not chain_match.same_chain(
        [fresh[0], {**fresh[1], "miles": 0.4}], recorded, chain_match.GENERIC_LABELS
    )
    out = chain_match.adopt(recorded, fresh)
    assert out[0]["controls"] == [{"at_mi": 0.2, "kind": "stop"}]
    assert out[1]["controls"] == [{"at_mi": 0.0, "kind": "signal"}]


def _stop_leg(node, lat, lon):
    return {
        "from": "a",
        "to": "b",
        "miles": 2.0,
        "highway": "I-1",
        "corridor": {
            "interchanges": [
                {
                    "at_mi": 1.0,
                    "exit_ref": "7",
                    "ramp_terminal_forward": {"node": node, "lat": lat, "lon": lon},
                }
            ],
            "state_miles": [{"state": "Illinois", "miles": 2.0}],
        },
        "stops": [
            {
                "name": "Fixture Plaza",
                "type": "travel_center",
                "at_mi": 1.0,
                "interchange_mi": 1.0,
                "lat": 41.0080,
                "lon": -86.9950,
                "source": "fixture",
            },
            {"name": "Rest Area", "type": "public_rest_area", "at_mi": 1.5, "source": "x"},
        ],
    }


def test_a_stop_off_an_exit_gets_the_streets_from_its_ramp(tmp_path, monkeypatch):
    pytest.importorskip("osmium")
    import build_stop_approaches as stops

    osm_path = tmp_path / "stop.osm"
    osm_path.write_text(FIXTURE, encoding="utf-8")
    lg = stops._local_geometry()
    monkeypatch.setattr(lg, "state_extract_path", lambda _cache, _state: osm_path)
    monkeypatch.setattr(stops, "_local_geometry", lambda: lg)
    legs = [_stop_leg(100, 41.0, -87.01)]
    work, counts = stops.stop_targets(legs)
    assert counts["no_serving_exit"] == 1 and len(work) == 1
    found = stops.route_stops(tmp_path, work, None, in_town)[(0, 0)]
    [chain] = found["approach_chains"]
    assert [seg["road"] for seg in chain["segments"]] == [
        "Exit Road",
        "Terminal Road",
        "Warehouse Drive",
    ]
    assert chain["driveway"]["node"] == 4
    # A ramp that leads straight into the lot is on the mainline: no chain.
    legs = [_stop_leg(4, 41.0080, -87.0000)]
    work, _counts = stops.stop_targets(legs)
    found = stops.route_stops(tmp_path, work, None, in_town)[(0, 0)]
    assert found["approach_chains"] == []
    assert found["approach_chains_failed"][0]["route_failure"] == stops.ON_MAINLINE


def test_a_stop_whose_exit_is_gone_loses_its_old_chain(monkeypatch):
    """A rebake of some legs judges every stop on them afresh. A stop whose
    exit moved or lost its terminal used to keep the chain from a ramp that
    is not there; stops on legs outside the rebake keep theirs."""
    from types import SimpleNamespace

    import build_stop_approaches as stops

    def leg(start):
        stop = {"name": "Truck Stop", "type": "travel_center", "at_mi": 5.0, "lat": 41.0}
        stop |= {"lon": -87.0, "approach_chains": [{"terminal_node": 1}]}
        state_miles = [{"state": "Illinois", "miles": 10.0}]
        return {
            "from": start,
            "to": "b_il_us",
            "corridor": {"state_miles": state_miles},
            "stops": [stop],
        }

    rebaked, other = leg("a_il_us"), leg("c_il_us")
    monkeypatch.setattr(stops, "load_world", lambda: {"legs": [rebaked, other]})
    monkeypatch.setattr(stops, "save_world", lambda _data: None)
    monkeypatch.setattr(stops, "route_stops", lambda *_args: {})
    extract = SimpleNamespace(state_extract_path=lambda _cache, _state: Path(__file__))
    monkeypatch.setattr(stops, "_local_geometry", lambda: extract)
    assert stops.main(["--only", "a_il_us->b_il_us", "--write"]) == 0
    assert "approach_chains" not in rebaked["stops"][0]
    assert other["stops"][0]["approach_chains"] == [{"terminal_node": 1}]


def _one_street(state, town, major=frozenset()):
    segments = [
        {
            "road": "IA 175",
            "miles": 0.3,
            "speed_mph": 25.0,
            "_first_edge": 0,
            "_end_edge": 2,
            "_raw_miles": 0.3,
            "_read_miles": 0.0,
        }
    ]
    street_chain.annotate(
        segments,
        [0, 1, 2],
        [(42.31, -93.57)] * 3,
        [0.15, 0.15],
        ["street"] * 2,
        set(),
        {},
        {},
        state,
        major,
        town_judge=in_town if town else out_of_town,
    )
    return segments[0]


def test_outside_town_the_rural_statute_governs_not_the_district_one():
    """IA 175 beside the Love's off I-35: untagged, outside any Census urban
    area. It read 20 mph -- Iowa's business-district figure -- which no sign
    and no statute puts on that road; Iowa Code 321.285(3) says 55."""
    street = _one_street("Iowa", town=False)
    assert (street["limit_mph"], street["limit_source"], street["limit_basis"]) == (
        55.0,
        "statutory",
        "rural",
    )
    in_town = _one_street("Iowa", town=True)
    assert (in_town["limit_mph"], in_town["limit_basis"]) == (20.0, "town")


def test_a_rural_numbered_highway_and_a_county_road_differ_where_the_code_says():
    highway = _one_street("Kansas", town=False, major=frozenset({(0, 1), (1, 2)}))
    county = _one_street("Kansas", town=False)
    assert (highway["limit_mph"], county["limit_mph"]) == (65.0, 55.0)


def test_a_state_without_a_rural_default_takes_the_labelled_median():
    street = _one_street("Nevada", town=False)
    if street["limit_source"] == "assumed":
        assert street["limit_mph"] == street_chain.assumed_rural_mph()


def test_the_real_boundary_puts_the_iowa_love_s_outside_town():
    import census_boundaries

    if not census_boundaries.available():
        pytest.skip("Census boundaries are a local download")
    # Iowa keys on a density district: the Census urban area, not the city
    # limits the interchange was annexed into.
    assert street_chain.town_basis("Iowa") == "urban_area"
    assert not census_boundaries.in_town("urban_area", 42.3105, -93.5731)
    assert census_boundaries.in_town("urban_area", 41.5868, -93.6250)  # Des Moines


def test_every_state_has_a_cited_rural_row_and_the_table_is_current():
    import json

    import statutory_limits
    import statutory_rural

    assert statutory_rural.validate(statutory_rural.RURAL_LIMITS) == []
    assert set(statutory_rural.RURAL_LIMITS) == set(statutory_limits.STATUTORY_LIMITS)
    shipped = json.loads(statutory_limits.OUT_PATH.read_text(encoding="utf-8"))["limits"]
    assert shipped == statutory_limits._with_rural(statutory_limits.STATUTORY_LIMITS)


def test_the_real_bake_refuses_to_run_without_the_census_boundaries(tmp_path, monkeypatch):
    """A street limit cannot be judged in town or out without the boundaries,
    and a bake that guessed would ship statutory numbers under the wrong
    statute -- so the real entry points stop, loudly, before routing."""
    import census_boundaries

    monkeypatch.setattr(census_boundaries, "URBAN_AREAS", tmp_path / "missing" / "uac20")
    monkeypatch.setattr(census_boundaries, "PLACES", tmp_path / "missing" / "place")
    tool = _load_tool()
    monkeypatch.setattr(tool, "collect_targets", lambda: pytest.fail("routed anyway"))
    with pytest.raises(SystemExit, match="Census boundaries are missing"):
        tool.build_facility_approaches(tmp_path, states=("Illinois",))
    import build_stop_approaches as stops

    with pytest.raises(SystemExit, match="Census boundaries are missing"):
        stops.route_stops(tmp_path, [], None)
    # A library caller that asks for street detail must name its judge.
    lg = tool._load_local_geometry_tool()
    with pytest.raises(ValueError, match="town judge"):
        lg.route_state_targets(tmp_path / "none.osm", [], street_detail=True)
