import copy

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
        {"way_id": 10, "name": "River", "coords": [[1.0, -1.0], [1.0, 1.0]]},
        {"way_id": 11, "name": "River", "coords": [[3.0, -1.0], [3.0, 1.0]]},
    ]


def test_route_point_max_off_uses_archived_lon_lat_vertices():
    leg = {"corridor": {"route_points": [{"lat": 30.0, "lon": -89.8}]}}
    coords = [[-90.0, 30.0], [-89.0, 30.0]]

    expected = prc.lg.scs._haversine_m(30.0, -89.8, 30.0, -90.0) / 1609.344

    assert prc.lg.route_point_max_off_mi(leg, coords) == pytest.approx(expected)
    assert prc.lg.route_point_max_off_mi({"corridor": {}}, coords) is None


def test_places_nearest_crossing_and_leaves_unmatched_and_other_categories_untouched(
    monkeypatch,
):
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
    assert "way 10 (River)" in river["source"]
    assert "nearest the previous at_mi" in river["source"]
    assert "2026-09-30" in river["source"]
    assert unmatched == before[3]
    for original, snapshot in zip(untouched, before, strict=True):
        assert original == snapshot
        assert any(item is original for item in leg["corridor"]["landmarks"])
    assert report["rivers_moved"] == 1
    assert report["unmatched"] == [{"leg": "a_tx_us:b_tx_us", "name": "Missing", "at_mi": 44.0}]
    assert report["histogram"]["5-10"] == 1


def test_route_point_disagreement_skips_all_landmark_changes(monkeypatch):
    river = {"name": "River", "category": "river", "at_mi": 30.0}
    leg = _leg([river])
    before = copy.deepcopy(river)
    _install_geometry(monkeypatch, max_off_mi=5.01)

    report = prc.process_world({"legs": [leg]}, _two_crossings(), pbf_date="2026-09-30")

    assert river == before
    assert report["legs_scanned"] == 0
    assert report["guard_skipped"] == [
        "a_tx_us:b_tx_us: route_points are 5.01 mi from archive (limit 5.00)"
    ]


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

    monkeypatch.setattr(prc, "load_or_extract_river_lines", extract)
    monkeypatch.setattr(prc, "save_world", saved.append)
    _install_geometry(monkeypatch)

    assert prc.main(["--pbf", str(pbf), "--only", "a_tx_us:b_tx_us"]) == 0

    output = capsys.readouterr().out
    assert "a_tx_us:b_tx_us River: 30.0 -> 25.0" in output
    assert "Dry run only" in output
    assert not saved
