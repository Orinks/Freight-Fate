"""A street chain may begin on the facility's own private road, and nowhere
else (owner ruling 2026-09-17; the rule is in ``tools/yard_roads.py``).

Every case is a tiny OSM fixture run through the real facility builder, so
the tag reading, the search and the row it writes are all under test. East
of the city context along one parallel, 0.01 degrees of longitude is about
0.52 miles.
"""

import importlib.util
import sys
from pathlib import Path

TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "build_facility_approaches.py"
YARD = "a service road"


def _load_tool():
    spec = importlib.util.spec_from_file_location("build_facility_approaches", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _osm(nodes: dict[int, tuple[float, float]], ways: list[tuple[list[int], dict[str, str]]]):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<osm version="0.6" generator="fixture">']
    for ref, (lat, lon, *tags) in nodes.items():
        inner = "".join(f'<tag k="{k}" v="{v}" />' for k, v in (tags[0] if tags else {}).items())
        lines.append(f'<node id="{ref}" lat="{lat:.4f}" lon="{lon:.4f}">{inner}</node>')
    for way_id, (refs, tags) in enumerate(ways, start=100):
        nds = "".join(f'<nd ref="{ref}" />' for ref in refs)
        inner = "".join(f'<tag k="{k}" v="{v}" />' for k, v in tags.items())
        lines.append(f'<way id="{way_id}">{nds}{inner}</way>')
    lines.append("</osm>")
    return "\n".join(lines)


def _route(tmp_path, monkeypatch, nodes, ways, *, end: int):
    """Run the real builder over the fixture; return the facility's row."""
    tool = _load_tool()
    osm_path = tmp_path / "yard.osm"
    osm_path.write_text(_osm(nodes, ways), encoding="utf-8")
    target = tool.FacilityTarget(
        facility_id="fixture:warehouse",
        city="Fixture City",
        state="Illinois",
        facility_name="Fixture Warehouse",
        facility_type="warehouse",
        endpoint_name="Real Warehouse",
        lat=nodes[end][0],
        lon=nodes[end][1],
        start_lat=41.0,
        start_lon=-87.0,
        endpoint_source_backed=True,
        endpoint_fallback=False,
        endpoint_source_note="fixture",
        local_approach_miles=2.1,
        local_approach_road="Main Street",
    )
    monkeypatch.setattr(tool, "collect_targets", lambda: [target])
    local_geometry = tool._load_local_geometry_tool()
    monkeypatch.setattr(local_geometry, "state_extract_path", lambda _cache, _state: osm_path)
    monkeypatch.setattr(tool, "_load_local_geometry_tool", lambda: local_geometry)
    payload = tool.build_facility_approaches(
        tmp_path, states=("Illinois",), endpoint_screen=False, accessed="2026-09-17"
    )
    return payload["approaches"]["fixture:warehouse"]


# Main Street runs east from the city context (1) to the plant entrance (4),
# 1.57 miles. Beyond it the plant's road is private (4-5-6), and inside the
# fence a short public-tagged lane (6-7) reaches the dock at 7.
MAIN = {
    1: (41.0, -87.00),
    2: (41.0, -86.99),
    3: (41.0, -86.98),
    4: (41.0, -86.97),
}
PLANT = {5: (41.0, -86.966), 6: (41.0, -86.963), 7: (41.0, -86.961)}
MAIN_STREET = ([1, 2, 3, 4], {"highway": "tertiary", "name": "Main Street"})
DOCK_LANE = ([6, 7], {"highway": "service", "name": "Dock Lane"})


def _plant_road(**tags):
    return ([4, 5, 6], {"highway": "service", "name": "Acme Private Drive", "ref": "PVT 1", **tags})


def test_a_yard_reached_only_over_its_own_private_road_gains_a_chain(tmp_path, monkeypatch):
    row = _route(
        tmp_path,
        monkeypatch,
        {**MAIN, **PLANT},
        [MAIN_STREET, _plant_road(access="private"), DOCK_LANE],
        end=7,
    )
    assert row["turn_level"]
    roads = [segment["road"] for segment in row["segments"]]
    # Departures read the chain backwards, so the LAST segment is the first
    # link out of the yard. It is the canonical phrase, never the way's name.
    assert roads == ["Main Street", YARD]
    spoken = " ".join(segment["cue"] + segment["road"] for segment in row["segments"])
    assert "Acme" not in spoken and "PVT" not in spoken and "private" not in spoken.lower()
    # The fragment inside the fence is part of the yard stretch, not a street.
    assert "Dock Lane" not in spoken
    yard = row["yard_road"]
    assert yard["spoken_as"] == YARD
    assert 0.4 <= yard["miles"] <= 0.5
    assert 1.5 <= yard["public_miles"] <= 1.65
    assert "access=private" in yard["source"] and "2026-09-17" in yard["source"]
    assert "private road" in row["final_hint"]


def test_a_gate_on_the_yards_own_road_is_a_yards_gate(tmp_path, monkeypatch):
    nodes = {**MAIN, **PLANT, 5: (41.0, -86.966, {"barrier": "gate"})}
    row = _route(
        tmp_path,
        monkeypatch,
        nodes,
        [MAIN_STREET, _plant_road(access="private"), DOCK_LANE],
        end=7,
    )
    assert row["turn_level"] and row["segments"][-1]["road"] == YARD


def test_a_private_way_is_never_a_shortcut_mid_route(tmp_path, monkeypatch):
    # The public way round is a 3-mile dogleg north (1-10-11-4); another
    # plant's private road cuts straight across (1-4, 1.57 miles). Both the
    # public search and the yard-road fallback must take the dogleg.
    nodes = {**MAIN, **PLANT, 10: (41.012, -87.00), 11: (41.012, -86.97)}
    dogleg = ([1, 10, 11, 4], {"highway": "secondary", "name": "Ring Road"})
    shortcut = ([1, 2, 3, 4], {"highway": "service", "access": "private", "name": "Other Plant"})
    row = _route(
        tmp_path,
        monkeypatch,
        nodes,
        [dogleg, shortcut, _plant_road(access="private"), DOCK_LANE],
        end=7,
    )
    assert row["turn_level"]
    assert [segment["road"] for segment in row["segments"]] == ["Ring Road", YARD]
    assert row["yard_road"]["public_miles"] > 3.0
    assert 0.4 <= row["yard_road"]["miles"] <= 0.5

    # With a public street to the dock, the private cut is not looked at at all.
    public_row = _route(
        tmp_path,
        monkeypatch,
        nodes,
        [dogleg, shortcut, _plant_road(), DOCK_LANE],
        end=7,
    )
    assert public_row["turn_level"] and "yard_road" not in public_row
    assert public_row["segments"][0]["road"] == "Ring Road"
    assert public_row["total_miles"] > 3.0


def test_the_chain_floor_is_met_by_public_miles_alone(tmp_path, monkeypatch):
    # 0.26 public miles, then 0.9 miles of private road: over the half-mile
    # floor in total, under it on public streets, so it stays refused.
    nodes = {
        1: (41.0, -87.00),
        4: (41.0, -86.995),
        5: (41.0, -86.985),
        6: (41.0, -86.978),
        7: (41.0, -86.976),
    }
    row = _route(
        tmp_path,
        monkeypatch,
        nodes,
        [
            ([1, 4], {"highway": "tertiary", "name": "Main Street"}),
            _plant_road(access="private"),
            DOCK_LANE,
        ],
        end=7,
    )
    assert not row["turn_level"]
    assert "shorter than the playable" in row["fallback_reason"]
    assert "yard_road" not in row


def test_ways_closed_to_the_truck_stay_refused(tmp_path, monkeypatch):
    for tags in (
        {"access": "no"},
        {"access": "military"},
        {"access": "private", "military": "base"},
        {"access": "private", "hgv": "no"},
        {"access": "private", "motor_vehicle": "no"},
        {"access": "private", "service": "emergency_access"},
    ):
        row = _route(
            tmp_path,
            monkeypatch,
            {**MAIN, **PLANT},
            [MAIN_STREET, _plant_road(**tags), DOCK_LANE],
            end=7,
        )
        assert not row["turn_level"], tags
        assert "do not join" in row["fallback_reason"], tags


def test_a_gate_on_a_public_way_is_not_routed_through(tmp_path, monkeypatch):
    # Main Street itself is gated at node 3, short of the plant entrance.
    nodes = {**MAIN, **PLANT, 3: (41.0, -86.98, {"barrier": "gate"})}
    row = _route(
        tmp_path,
        monkeypatch,
        nodes,
        [MAIN_STREET, _plant_road(access="private"), DOCK_LANE],
        end=7,
    )
    assert not row["turn_level"]


def test_the_rule_reads_tags_and_nothing_else():
    _load_tool()
    import yard_roads

    routable = {"service", "residential"}
    assert yard_roads.is_yard_road({"highway": "service", "access": "private"}, routable)
    assert not yard_roads.is_yard_road({"highway": "service"}, routable)
    assert not yard_roads.is_yard_road({"highway": "motorway", "access": "private"}, routable)
    assert not yard_roads.is_yard_road({"highway": "track", "access": "private"}, routable)
    assert yard_roads.is_blocking_barrier({"barrier": "lift_gate"})
    assert not yard_roads.is_blocking_barrier({"barrier": "cattle_grid"})
    assert not yard_roads.is_blocking_barrier({"barrier": "gate", "access": "yes"})
