import math

import bake_landmarks as bl
import pytest
import reroute_leg as rr
from ffworld.world_parsing import _parse_landmark


def test_fetch_route_builds_through_locations_and_joins_leg_shapes(monkeypatch):
    payload = {
        "trip": {
            "summary": {"length": 123.4},
            "legs": [
                {"shape": "first", "summary": {"has_toll": False}},
                {"shape": "second", "summary": {"has_toll": True}},
            ],
        }
    }
    request = {}
    monkeypatch.setattr(
        rr, "_post", lambda path, body: request.update(path=path, body=body) or payload
    )
    shapes = {
        "first": [[-100.0, 30.0], [-99.0, 31.0]],
        "second": [[-99.0, 31.0], [-98.0, 32.0]],
    }
    monkeypatch.setattr(rr, "decode_shape", shapes.__getitem__)

    result = rr.fetch_route(
        {"lat": 30.0, "lon": -100.0},
        {"lat": 32.0, "lon": -98.0},
        via=[{"lat": 31.0, "lon": -99.0}],
    )

    assert request == {
        "path": "/route",
        "body": {
            "locations": [
                {"lat": 30.0, "lon": -100.0},
                {
                    "lat": 31.0,
                    "lon": -99.0,
                    "type": "through",
                    "search_filter": rr.VIA_SEARCH_FILTER,
                },
                {"lat": 32.0, "lon": -98.0},
            ],
            "costing": rr.COSTING,
            "costing_options": {rr.COSTING: rr.TRUCK_OPTIONS},
            "directions_options": {"units": "miles"},
        },
    }
    assert result == (
        [[-100.0, 30.0], [-99.0, 31.0], [-98.0, 32.0]],
        123.4,
        True,
    )
    assert rr.route_via_points(
        {
            "route_via": [
                {"lat": 30, "lon": -100},
                {"lat": "31", "lon": -99},
                None,
                {"lat": 32, "lon": -98},
            ]
        }
    ) == [{"lat": 30, "lon": -100}, {"lat": 32, "lon": -98}]


def test_fetch_route_refuses_more_than_ten_locations(monkeypatch):
    def post(*_args, **_kwargs):
        pytest.fail("request sent over Valhalla's location cap")

    monkeypatch.setattr(rr, "_post", post)

    with pytest.raises(ValueError, match="at most 10 locations"):
        rr.fetch_route(
            {"lat": 0, "lon": 0},
            {"lat": 1, "lon": 1},
            via=[{"lat": 0, "lon": 0}] * 9,
        )


def test_river_crossing_interpolates_first_of_two_route_crossings():
    route = [(0.0, 0.0), (0.0, 2.0), (0.0, 4.0)]
    cum = [0.0, 10.0, 30.0]
    line = [(1.0, 1.0), (-1.0, 1.0), (-1.0, 3.0), (1.0, 3.0)]

    assert bl.river_crossing_mi(route, cum, line) == (5.0, 0.0, 1.0)


def test_sample_route_spaces_bbox_queries_by_mileage():
    route = [(0.0, 0.0), (0.0, math.degrees(60.0 / bl.R_MI))]

    samples = bl.sample_route(route, [0.0, 60.0])

    assert len(samples) == 4
    assert [bl.hav(*a, *b) for a, b in zip(samples, samples[1:], strict=False)] == pytest.approx(
        [20.0, 20.0, 20.0], abs=0.01
    )


def test_bake_leg_uses_dense_geometry_and_writes_on_route_provenance(monkeypatch):
    dense = [(0.0, 0.0, 0.0), (0.0, 0.5, 34.5), (0.0, 1.0, 69.0)]
    monkeypatch.setattr(bl.lg, "corridor_geometry", lambda _leg: dense)
    boxes = []
    elements = [
        {
            "type": "way",
            "id": 101,
            "tags": {"name": "Test River", "category": "river"},
            "geometry": [{"lat": -1.0, "lon": 0.25}, {"lat": 1.0, "lon": 0.25}],
        },
        {
            "type": "node",
            "id": 202,
            "lat": 0.01,
            "lon": 0.75,
            "tags": {"name": "Test Pass", "category": "mountain_pass"},
        },
        {
            "type": "way",
            "id": 303,
            "tags": {"name": "Test Forest", "category": "national_forest"},
            "geometry": [
                {"lat": -0.1, "lon": 0.4},
                {"lat": -0.1, "lon": 0.6},
                {"lat": 0.1, "lon": 0.6},
                {"lat": 0.1, "lon": 0.4},
                {"lat": -0.1, "lon": 0.4},
            ],
        },
    ]

    def fake_overpass(bbox):
        boxes.append(bbox)
        return {"elements": elements}

    def fake_classify(tags):
        category = tags["category"]
        return {
            "name": tags["name"],
            "category": category,
            "kind": "zone" if category == "national_forest" else "point",
            "rank": 10,
        }

    monkeypatch.setattr(bl, "overpass", fake_overpass)
    monkeypatch.setattr(bl, "classify_narratable_feature", fake_classify)
    monkeypatch.setattr(bl, "spoken_landmark_text", lambda feat: f"Entering {feat['name']}")
    leg = {
        "miles": 69.0,
        "corridor": {
            "route_points": [
                {"lat": 1.0, "lon": 0.0},
                {"lat": 1.0, "lon": 1.0},
            ]
        },
    }

    records = bl.bake_leg(leg, per_leg=8)

    assert len(boxes) == 5
    samples = [
        (
            (float(box.split(",")[0]) + float(box.split(",")[2])) / 2,
            (float(box.split(",")[1]) + float(box.split(",")[3])) / 2,
        )
        for box in boxes
    ]
    assert [bl.hav(*a, *b) for a, b in zip(samples, samples[1:], strict=False)] == pytest.approx(
        [20.0, 20.0, 20.0, 9.0], abs=0.1
    )
    river, forest, pass_landmark = records
    assert (river["lat"], river["lon"]) == (0.0, 0.25)
    assert river["at_mi"] == pytest.approx(17.2, abs=0.1)
    assert (forest["lat"], forest["lon"]) == (0.0, 0.5)
    assert (pass_landmark["lat"], pass_landmark["lon"]) == (0.0, 0.75)
    for record in records:
        assert record["source"].startswith("derived 2026-10-01:")
        assert "OpenStreetMap via Overpass" in record["source"]
    assert "OSM waterway way 101 (Test River)" in river["source"]
    assert "archived dense route geometry" in river["source"]
    parsed = _parse_landmark(river, 69.0, "a", "b")
    assert parsed.name == river["name"]


def test_reroute_repositions_stops_and_drops_ones_farther_than_three_miles():
    stops = [
        {"name": "near", "lat": 30.0, "lon": -99.5, "at_mi": 8.0, "source": "read: stop"},
        {"name": "far", "lat": 31.0, "lon": -99.5, "at_mi": 8.0},
        {"name": "no coordinates", "at_mi": 5.0, "source": "read: stop"},
    ]
    shape = [[-100.0, 30.0], [-99.5, 30.0], [-99.0, 30.0]]

    kept, dropped = rr.reroute_stops(stops, shape, miles=100.0, old_miles=50.0)

    assert [stop["name"] for stop in kept] == ["no coordinates", "near"]
    assert kept[0]["at_mi"] == 10.0
    assert "old at_mi x new miles / old miles (the stop has no coordinates)" in kept[0]["source"]
    assert kept[1]["at_mi"] == pytest.approx(50.0)
    assert "the stop's own coordinates projected" in kept[1]["source"]
    assert len(dropped) == 1
    assert dropped[0][0]["name"] == "far"
    assert dropped[0][1] > rr.STOP_MAX_OFF_MI


def _reroute_world(landmarks):
    leg = {
        "from": "a",
        "to": "b",
        "highway": "I-5",
        "miles": 20,
        "corridor": {"landmarks": landmarks},
    }
    cities = {
        "a": {"lat": 30.0, "lon": -100.0, "state": "TX"},
        "b": {"lat": 31.0, "lon": -99.0, "state": "TX"},
    }
    return {"cities": cities, "legs": [leg]}, leg


def _mock_successful_reroute(monkeypatch, world):
    monkeypatch.setattr(rr, "load_world", lambda: world)
    monkeypatch.setattr(
        rr,
        "fetch_route",
        lambda _start, _end, via=(): ([[-100.0, 30.0], [-99.0, 31.0]], 10.0, False),
    )
    monkeypatch.setattr(rr, "fetch_elevation", lambda _shape: [10.0, 20.0])
    monkeypatch.setattr(rr.scs, "_cumulative_m", lambda _shape: [0.0, 160934.4])
    monkeypatch.setattr(rr.scs, "analyse_curvature", lambda *_args: {"curves": []})
    monkeypatch.setattr(rr, "rides_its_label", lambda *_args: (1.0, "I-5"))
    monkeypatch.setattr(rr.scs, "encode_geometry", lambda *_args: "geometry")
    monkeypatch.setattr(rr, "write_geometry", lambda *_args: None)
    monkeypatch.setattr(rr.lg, "reposition_on_route", lambda *_args: ([], []))
    saved = []
    monkeypatch.setattr(rr, "save_world", saved.append)
    return saved


def test_reroute_keeps_curated_landmark_records_unchanged(monkeypatch, capsys):
    marker = {"name": "Highway marker", "category": "highway_marker", "at_mi": 4.0}
    billboard = {"name": "Billboard", "category": "billboard_sign", "at_mi": 6.0}
    rebuilt = {"name": "River", "category": "river", "at_mi": 2.0}
    world, leg = _reroute_world([marker, billboard, rebuilt])
    saved = _mock_successful_reroute(monkeypatch, world)
    monkeypatch.setattr(rr.sys, "argv", ["reroute_leg.py", "--leg", "a:b", "--write"])

    assert rr.main() == 0

    assert saved == [world]
    assert leg["corridor"]["landmarks"] == [marker, billboard]
    assert leg["corridor"]["landmarks"][0] is marker
    assert leg["corridor"]["landmarks"][1] is billboard
    assert "kept 2 curated landmarks unchanged" in capsys.readouterr().out


def test_reroute_refuses_out_of_range_curated_landmark_before_any_write(monkeypatch, capsys):
    marker = {"name": "Highway marker", "category": "highway_marker", "at_mi": 10.1}
    world, _leg = _reroute_world([marker])
    monkeypatch.setattr(rr, "load_world", lambda: world)
    monkeypatch.setattr(
        rr,
        "fetch_route",
        lambda *_args, **_kwargs: ([[-100.0, 30.0], [-99.0, 31.0]], 10.0, False),
    )
    monkeypatch.setattr(rr, "write_geometry", lambda *_args: pytest.fail("geometry written"))
    monkeypatch.setattr(rr, "save_world", lambda *_args: pytest.fail("world written"))
    monkeypatch.setattr(
        rr, "fetch_elevation", lambda *_args: pytest.fail("continued past preflight")
    )
    monkeypatch.setattr(rr.sys, "argv", ["reroute_leg.py", "--leg", "a:b", "--write"])

    assert rr.main() == 1
    output = capsys.readouterr().out
    assert "REFUSING" in output
    assert "Highway marker" in output
