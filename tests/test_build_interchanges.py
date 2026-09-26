"""Interchange discovery reads the road a leg drives: its archived polyline.

Re-deriving the 81 legs whose exit mileage had drifted from their polyline
(2026-09-25) turned up three ways the builder still leaned on something else:
the PBF prefilter boxed route_points, which on 7 of those legs left most of
the polyline unread; junctions snapped to the nearest polyline VERTEX, and
the archive keeps a vertex only every few miles on a straight; and one exit
number seen twice along a leg was averaged into a single exit between them.
"""

import build_interchanges as bi

MI_PER_DEG_LAT = bi._haversine_mi(40.0, -80.0, 41.0, -80.0)


def _north(mi: float) -> float:
    """Latitude ``mi`` miles north of 40N on the -80 meridian."""
    return 40.0 + mi / MI_PER_DEG_LAT


def _straight(miles: float) -> list[tuple[float, float, float]]:
    """A polyline the way the archive stores a tangent: two vertices."""
    return [(40.0, -80.0, 0.0), (_north(miles), -80.0, miles)]


def _junction(lat: float, ref: str) -> bi.LocalOsmFeature:
    return bi.LocalOsmFeature(lat=lat, lon=-80.0, tags={"highway": "motorway_junction", "ref": ref})


def _leg(miles: float) -> dict:
    return {"from": "a_pa_us", "to": "b_pa_us", "highway": "I-80", "miles": miles}


def test_prefilter_boxes_follow_the_polyline_not_the_route_points(monkeypatch):
    # Route points on a straight line; the road itself bows 70 miles north.
    leg = {
        "corridor": {
            "route_points": [
                {"lat": 40.0, "lon": -80.0, "at_mi": 0.0},
                {"lat": 40.0, "lon": -79.0, "at_mi": 53.0},
            ]
        }
    }
    bow = [(40.0, -80.0, 0.0), (41.0, -79.5, 60.0), (40.0, -79.0, 120.0)]
    monkeypatch.setattr(bi.lg, "corridor_geometry", lambda _leg: bow)
    bounds = bi._local_prefilter_bounds([leg])
    assert bi._inside_any_bounds(41.0, -79.5, bounds)
    assert bi._inside_any_bounds(40.5, -79.75, bounds)

    # A leg with no archived polyline still boxes its route points.
    monkeypatch.setattr(bi.lg, "corridor_geometry", lambda _leg: None)
    assert bi._local_prefilter_bounds([leg]) == bi._route_corridor_bounds(
        leg["corridor"]["route_points"]
    )


def test_a_junction_halfway_down_a_tangent_is_found_at_its_mile():
    # Five miles from either vertex: a vertex snap drops it at 200 m.
    index = bi.LocalOsmIndex(
        junctions=[_junction(_north(5.0), "12"), _junction(_north(5.1), "12")], ramps=[]
    )
    exits = bi.discover_leg(_leg(10.0), 0.0, index, geom=_straight(10.0))
    assert [ix["exit_ref"] for ix in exits] == ["12"]
    assert abs(exits[0]["at_mi"] - 5.05) <= 0.1
    assert "at_mi derived" in exits[0]["source"]


def test_a_relabelled_leg_that_passes_no_junction_loses_its_old_exits(monkeypatch, tmp_path):
    # Denver to Albuquerque kept 97 I-25 exits after it was relabelled US-285
    # for the road it drives now. From a local extract the label does not
    # matter, and finding nothing on the polyline clears the phantoms.
    leg = {
        **_leg(10.0),
        "highway": "US-285",
        "corridor": {"interchanges": [{"at_mi": 4.0, "exit_ref": "224"}]},
    }
    saved = []
    monkeypatch.setattr(bi, "load_world", lambda: {"legs": [leg]})
    monkeypatch.setattr(bi, "save_world", saved.append)
    monkeypatch.setattr(bi.lg, "corridor_geometry", lambda _leg: _straight(10.0))
    cache = tmp_path / "index.json"
    far_away = bi.LocalOsmIndex(junctions=[_junction(_north(50.0), "224")], ramps=[])
    bi._write_local_index_cache(cache, far_away, [], bi._local_prefilter_bounds([leg]))
    only = f"{leg['from']}->{leg['to']}"
    args = ["--only", only, "--force", "--local-index-cache", str(cache), "--write"]
    assert bi.main(args) == 0
    assert saved and leg["corridor"]["interchanges"] == []


def test_one_exit_number_twice_on_a_leg_is_two_exits():
    # Each state numbers its own exits, so a leg across a line can pass two
    # exit 5s. Averaged, they became one exit at mile 35 where there is none.
    index = bi.LocalOsmIndex(
        junctions=[
            _junction(_north(10.0), "5"),
            _junction(_north(10.3), "5"),
            _junction(_north(60.0), "5"),
        ],
        ramps=[],
    )
    dense = [(_north(mi), -80.0, float(mi)) for mi in range(81)]
    exits = bi.discover_leg(_leg(80.0), 0.0, index, geom=dense)
    assert [round(ix["at_mi"]) for ix in exits] == [10, 60]
