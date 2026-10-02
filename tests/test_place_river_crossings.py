import copy
from pathlib import Path

import place_river_crossings as prc
import pytest


def _leg(landmarks):
    return {
        "from": "a_tx_us",
        "to": "b_tx_us",
        "miles": 100.0,
        "corridor": {
            "route_points": [
                {"lat": 0.0, "lon": 0.0},
                {"lat": 0.0, "lon": 4.0},
            ],
            "landmarks": landmarks,
        },
    }


def _install_geometry(monkeypatch, max_off_mi=0.0):
    monkeypatch.setattr(
        prc.lg,
        "corridor_geometry",
        lambda _leg: [(0.0, 0.0, 0.0), (0.0, 4.0, 100.0)],
    )
    monkeypatch.setattr(
        prc.lg,
        "archived_polyline",
        lambda *_args: ([[-0.0, 0.0], [4.0, 0.0]], []),
    )
    monkeypatch.setattr(
        prc.lg,
        "route_point_max_off_mi",
        lambda *_args: max_off_mi,
    )


def _two_crossings():
    return [
        {
            "geometry": "line",
            "feature_type": "waterway way",
            "feature_id": 10,
            "name": "River",
            "coords": [[1.0, -1.0], [1.0, 1.0]],
        },
        {
            "geometry": "line",
            "feature_type": "waterway way",
            "feature_id": 11,
            "name": "River",
            "coords": [[3.0, -1.0], [3.0, 1.0]],
        },
    ]


def test_route_point_max_off_uses_archived_lon_lat_segments():
    leg = {"corridor": {"route_points": [{"lat": 30.1, "lon": -89.5}]}}
    coords = [[-90.0, 30.0], [-89.0, 30.0]]

    expected = prc.lg.scs._haversine_m(30.1, -89.5, 30.0, -89.5) / 1609.344

    assert prc.lg.route_point_max_off_mi(leg, coords) == pytest.approx(expected)
    assert prc.lg.route_point_max_off_mi({"corridor": {}}, coords) is None


def test_filtered_water_feature_pbf_is_cached(monkeypatch, tmp_path):
    source = tmp_path / "us.osm.pbf"
    source.write_bytes(b"source")
    cache_dir = tmp_path / "cache"
    commands = []

    monkeypatch.setattr(prc.shutil, "which", lambda _name: "/usr/bin/osmium")

    def run(command, check):
        assert check
        commands.append(command)
        output = Path(command[command.index("--output") + 1])
        output.write_bytes(b"filtered")

    monkeypatch.setattr(prc.subprocess, "run", run)

    first = prc._water_feature_pbf(source, cache_dir)
    second = prc._water_feature_pbf(source, cache_dir)

    assert first == second
    assert first.read_bytes() == b"filtered"
    assert len(commands) == 1
    assert all(expression in commands[0] for expression in prc.WATER_FEATURE_FILTERS)
    assert "--remove-tags" not in commands[0]


def test_places_nearest_crossing_and_removes_unmatched_river_only(monkeypatch):
    river = {"name": "River", "category": "river", "at_mi": 30.0, "spoken": "say river"}
    unmatched = {"name": "Missing", "category": "river", "at_mi": 44.0, "rank": 2}
    billboard = {"name": "Sign", "category": "billboard_sign", "at_mi": 20.0}
    marker = {"name": "Marker", "category": "highway_marker", "at_mi": 40.0}
    forest = {"name": "Forest", "category": "forest", "at_mi": 50.0}
    leg = _leg([river, unmatched, billboard, marker, forest])
    untouched = [billboard, marker, forest, unmatched]
    before = copy.deepcopy(untouched)
    _install_geometry(monkeypatch)

    report = prc.process_world({"legs": [leg]}, _two_crossings(), pbf_date="2026-09-30")

    assert river["at_mi"] == 25.0
    assert (river["lat"], river["lon"]) == (0.0, 1.0)
    assert river["spoken"] == "say river"
    assert "tools/place_river_crossings.py" in river["source"]
    assert "way 10 (River)" in river["source"]
    assert "nearest the previous at_mi" in river["source"]
    assert "2026-09-30" in river["source"]
    assert unmatched == before[3]
    assert unmatched not in leg["corridor"]["landmarks"]
    for original, snapshot in zip(untouched[:3], before[:3], strict=True):
        assert original == snapshot
        assert any(item is original for item in leg["corridor"]["landmarks"])
    assert report["rivers_placed"] == 1
    assert report["unmatched"] == [{"leg": "a_tx_us:b_tx_us", "name": "Missing", "at_mi": 44.0}]
    assert report["changed_legs"] == 1
    assert report["histogram"]["5-10"] == 1


def test_stitches_empty_role_members_into_outer_ring_only():
    ways = {
        1: [[0.0, 0.0], [1.0, 0.0]],
        2: [[1.0, 0.0], [1.0, 1.0]],
        3: [[1.0, 1.0], [0.0, 1.0]],
        4: [[0.0, 1.0], [0.0, 0.0]],
        5: [[0.2, 0.2], [0.8, 0.2]],
        6: [[0.8, 0.2], [0.8, 0.8]],
        7: [[0.8, 0.8], [0.2, 0.8]],
        8: [[0.2, 0.8], [0.2, 0.2]],
    }
    members = [
        {"way_id": way_id, "role": role}
        for way_id, role in [
            (1, ""),
            (2, ""),
            (3, ""),
            (4, ""),
            (5, "inner"),
            (6, "inner"),
            (7, "inner"),
            (8, "inner"),
        ]
    ]

    outer, inner = prc._stitch_rings(members, ways)

    assert len(outer) == len(inner) == 1
    assert outer[0][0] == outer[0][-1]
    assert inner[0][0] == inner[0][-1]


def test_waterway_relation_name_applies_to_member_way_without_waterway_tag():
    relation_names = {123: {"St. Francis River"}}

    assert prc._waterway_names_for_way(123, "", None, relation_names, {"st. francis river"}) == [
        "St. Francis River"
    ]


@pytest.mark.parametrize("waterway_type", sorted(prc.WATERWAY_TYPES))
def test_named_waterway_types_match_named_river_landmarks(waterway_type):
    assert prc._waterway_names_for_way(
        123, "St. Francis River", waterway_type, {}, {"st. francis river"}
    ) == ["St. Francis River"]


def test_unlisted_waterway_types_do_not_match_by_way_name():
    assert (
        prc._waterway_names_for_way(123, "St. Francis River", "ditch", {}, {"st. francis river"})
        == []
    )


def test_river_polygon_uses_midpoint_of_route_span_inside_area(monkeypatch):
    _install_geometry(monkeypatch)
    polygon = {
        "geometry": "polygon",
        "feature_type": "river polygon way",
        "feature_id": 12,
        "name": "River",
        "outer": [[[1.0, -0.5], [3.0, -0.5], [3.0, 0.5], [1.0, 0.5], [1.0, -0.5]]],
        "inner": [],
    }
    route = [(0.0, 0.0), (0.0, 4.0)]
    cum = [0.0, 100.0]

    crossings = prc._crossings_for_name(
        route, cum, "River", {"river": [polygon]}, prc._route_segment_grid(route)
    )

    assert crossings == [(50.0, 0.0, 2.0, 12, "River", "river polygon way")]


def test_uses_archived_geometry_when_route_points_disagree(monkeypatch):
    river = {"name": "River", "category": "river", "at_mi": 30.0}
    leg = _leg([river])
    _install_geometry(monkeypatch, max_off_mi=10.01)

    report = prc.process_world({"legs": [leg]}, _two_crossings(), pbf_date="2026-09-30")

    assert river["at_mi"] == 25.0
    assert report["legs_scanned"] == 1
    assert report["geometry_skipped"] == []


def test_reports_legs_without_river_landmarks():
    leg = _leg([{"name": "Sign", "category": "billboard_sign", "at_mi": 1.0}])

    report = prc.process_world({"legs": [leg]}, [], pbf_date="2026-09-30")

    assert report["legs_without_rivers"] == 1
    assert report["legs_scanned"] == 0


def test_only_dry_run_uses_mocked_pbf_extraction_and_reports_old_to_new(
    monkeypatch, tmp_path, capsys
):
    pbf = tmp_path / "extract.osm.pbf"
    pbf.write_bytes(b"synthetic")
    leg = _leg([{"name": "River", "category": "river", "at_mi": 30.0}])
    data = {"legs": [leg]}
    saved = []
    monkeypatch.setattr(prc, "load_world", lambda: data)

    def extract(path, names):
        assert path == pbf
        assert names == {"river"}
        return _two_crossings()

    monkeypatch.setattr(prc, "load_or_extract_river_features", extract)
    monkeypatch.setattr(prc, "save_world", saved.append)
    _install_geometry(monkeypatch)

    assert prc.main(["--pbf", str(pbf), "--only", "a_tx_us:b_tx_us"]) == 0

    output = capsys.readouterr().out
    assert "a_tx_us:b_tx_us River: 30.0 -> 25.0" in output
    assert "Dry run only" in output
    assert not saved


def test_archived_river_landmarks_have_crossing_tool_provenance():
    data = prc.load_world()

    for leg in data["legs"]:
        if not prc.lg.archived_polyline(prc.lg.leg_id_of(leg), prc.lg.state_code_of(leg)):
            continue
        for landmark in (leg.get("corridor") or {}).get("landmarks", ()):
            if landmark.get("category") == "river":
                assert "tools/place_river_crossings.py" in landmark.get("source", ""), (
                    f"{prc._leg_id(leg)} {landmark.get('name')}"
                )


WATERWAY_RELATION_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="fixture">
  <node id="1" version="1" lat="35.00" lon="-90.00"/>
  <node id="2" version="1" lat="35.10" lon="-90.00"/>
  <node id="3" version="1" lat="35.20" lon="-90.00"/>
  <node id="4" version="1" lat="35.00" lon="-89.50"/>
  <node id="5" version="1" lat="35.10" lon="-89.50"/>
  <node id="6" version="1" lat="35.00" lon="-89.00"/>
  <node id="7" version="1" lat="35.10" lon="-89.00"/>
  <way id="10" version="1"><nd ref="1"/><nd ref="2"/></way>
  <way id="11" version="1"><nd ref="2"/><nd ref="3"/><tag k="waterway" v="river"/></way>
  <way id="20" version="1"><nd ref="4"/><nd ref="5"/></way>
  <way id="30" version="1"><nd ref="6"/><nd ref="7"/></way>
  <relation id="100" version="1">
    <member type="way" ref="10" role="main_stream"/>
    <member type="way" ref="11" role="main_stream"/>
    <tag k="type" v="waterway"/>
    <tag k="waterway" v="river"/>
    <tag k="name" v="Test River"/>
  </relation>
  <relation id="200" version="1">
    <member type="way" ref="30" role="main_stream"/>
    <tag k="type" v="waterway"/>
    <tag k="waterway" v="river"/>
    <tag k="name" v="Other River"/>
  </relation>
</osm>
"""


def _extract_fixture(monkeypatch, tmp_path):
    pytest.importorskip("osmium")
    fixture = tmp_path / "fixture.osm"
    fixture.write_text(WATERWAY_RELATION_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(prc, "_water_feature_pbf", lambda _pbf, _cache: fixture)
    features = prc.extract_river_lines(fixture, {"Test River"}, cache_dir=tmp_path / "cache")
    return {(feature["feature_id"], feature["name"]): feature for feature in features}


def test_untagged_member_way_of_named_waterway_relation_is_extracted(monkeypatch, tmp_path):
    features = _extract_fixture(monkeypatch, tmp_path)

    assert (10, "Test River") in features
    assert features[(10, "Test River")]["coords"] == [[-90.0, 35.0], [-90.0, 35.1]]
    assert (11, "Test River") in features


def test_untagged_ways_outside_wanted_waterway_relations_stay_excluded(monkeypatch, tmp_path):
    features = _extract_fixture(monkeypatch, tmp_path)

    assert not {feature_id for feature_id, _name in features} & {20, 30}
