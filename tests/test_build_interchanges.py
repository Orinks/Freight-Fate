"""Interchange discovery reads the road a leg drives: its archived polyline.

Re-deriving the 81 legs whose exit mileage had drifted from their polyline
(2026-09-25) turned up three ways the builder still leaned on something else:
the PBF prefilter boxed route_points, which on 7 of those legs left most of
the polyline unread; junctions snapped to the nearest polyline VERTEX, and
the archive keeps a vertex only every few miles on a straight; and one exit
number seen twice along a leg was averaged into a single exit between them.
"""

from pathlib import Path

import build_interchanges as bi
import build_interchanges_maxspeed as maxspeed
import pytest

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


def test_bare_maxspeed_units_follow_geofabrik_extract_region():
    canadian_extracts = (
        "alberta",
        "british-columbia",
        "manitoba",
        "new-brunswick",
        "newfoundland-and-labrador",
        "northwest-territories",
        "nova-scotia",
        "nunavut",
        "ontario",
        "prince-edward-island",
        "quebec",
        "saskatchewan",
        "yukon",
    )
    assert all(
        maxspeed._is_canadian_extract(Path(f"{slug}-latest.osm.pbf")) for slug in canadian_extracts
    )
    assert len(maxspeed.CANADIAN_MAXSPEED_REF_CODES) == 14
    assert len(maxspeed.US_MAXSPEED_REF_CODES) == 51
    alaska = Path("alaska-latest.osm.pbf")
    assert not maxspeed._is_canadian_extract(alaska)
    assert (
        maxspeed._parse_osm_maxspeed(
            "90", default_kmh=maxspeed._bare_maxspeed_is_kmh({"ref": "YK 1;AK 2"}, False)
        )
        == 55.0
    )
    assert (
        maxspeed._parse_osm_maxspeed(
            "55", default_kmh=maxspeed._bare_maxspeed_is_kmh({"ref": "AK 2"}, True)
        )
        == 55.0
    )
    assert (
        maxspeed._parse_osm_maxspeed(
            "80",
            default_kmh=maxspeed._bare_maxspeed_is_kmh({"source:maxspeed": "CA:rural"}, False),
        )
        == 50.0
    )
    assert (
        maxspeed._parse_osm_maxspeed(
            "55",
            default_kmh=maxspeed._bare_maxspeed_is_kmh(
                {"maxspeed:type": "US:urban", "ref": "YK 1"}, True
            ),
        )
        == 55.0
    )
    assert (
        maxspeed._parse_osm_maxspeed("80", default_kmh=maxspeed._bare_maxspeed_is_kmh({}, True))
        == 50.0
    )
    assert (
        maxspeed._parse_osm_maxspeed("80", default_kmh=maxspeed._bare_maxspeed_is_kmh({}, False))
        == 80.0
    )
    assert (
        maxspeed._parse_osm_maxspeed(
            "90 km/h", default_kmh=maxspeed._bare_maxspeed_is_kmh({"ref": "AK 2"}, False)
        )
        == 55.0
    )
    assert (
        maxspeed._parse_osm_maxspeed(
            "55 mph", default_kmh=maxspeed._bare_maxspeed_is_kmh({"ref": "YK 1"}, True)
        )
        == 55.0
    )
    assert not maxspeed._bare_maxspeed_is_kmh({"ref": "WA 14"}, True)


def test_overlapping_maxspeed_extracts_deduplicate_osm_ways(monkeypatch, tmp_path):
    alaska = tmp_path / "alaska-latest.osm.pbf"
    yukon = tmp_path / "yukon-latest.osm.pbf"
    alaska.write_bytes(b"")
    yukon.write_bytes(b"")
    duplicate_ways = {
        alaska: [
            maxspeed.LocalMaxspeedWay(
                osm_id=346636394,
                coords=((62.615, -141.002), (62.415, -140.851)),
                mph=55.0,
                hgv=False,
                ref="YK 1",
            )
        ],
        yukon: [
            maxspeed.LocalMaxspeedWay(
                osm_id=346636394,
                coords=((62.615, -141.002), (62.415, -140.851)),
                mph=85.0,
                hgv=False,
                ref="YK 1",
            )
        ],
    }
    monkeypatch.setattr(
        maxspeed,
        "_build_maxspeed_index_from_pbf",
        lambda path, _bounds, default_kmh, label: duplicate_ways[path],
    )

    ways = maxspeed.load_or_build_maxspeed_index(
        [alaska, yukon], [], tmp_path / "maxspeed.json", rebuild=True
    )

    assert len(ways) == 1
    assert ways[0].osm_id == 346636394
    assert ways[0].mph == 55.0
    assert maxspeed.MAXSPEED_INDEX_CACHE_VERSION == 4


def test_alaska_unposted_speed_fallback_stays_inside_state_range(monkeypatch):
    leg = {
        "miles": 387.0,
        "highway": "Alaska Highway",
        "corridor": {
            "state_miles": [
                {"state": "Yukon", "miles": 297.5},
                {"state": "Alaska", "miles": 89.5},
            ]
        },
    }
    geometry = [(63.0, -142.0, 0.0), (64.0, -141.0, 387.0)]
    monkeypatch.setattr(
        maxspeed,
        "leg_corridor_geometry_with_source",
        lambda _leg, _rate_limit: (geometry, "fixture route geometry"),
    )

    profile = maxspeed.bake_maxspeed_for_leg(leg, {}, rate_limit=0.0)

    assert profile
    assert profile[0]["at_mi"] == 297.5
    assert all(sample["at_mi"] >= 297.5 for sample in profile)
    assert all(sample["source"] == maxspeed.ALASKA_UNPOSTED_SPEED[1] for sample in profile)


def test_sparse_maxspeed_way_covers_a_parallel_route(monkeypatch):
    monkeypatch.setattr(maxspeed, "MAXSPEED_SAMPLE_STRIDE_MI", 1.0)
    sparse_way = maxspeed.LocalMaxspeedWay(
        osm_id=1,
        coords=((40.0, -79.999), (_north(10.0), -79.999)),
        mph=55.0,
        hgv=False,
        ref="",
    )
    route_way = maxspeed.LocalMaxspeedWay(
        osm_id=2,
        coords=tuple((_north(mile / 4), -80.0) for mile in range(41)),
        mph=45.0,
        hgv=False,
        ref="",
    )
    geometry = [(_north(mile), -80.0, float(mile)) for mile in range(101)]

    profile = maxspeed.assemble_maxspeed(
        maxspeed.build_maxspeed_grid([sparse_way, route_way]),
        geometry,
        10.0,
        "US 1",
        source="test",
    )

    for mile in range(11):
        active = next(sample for sample in reversed(profile) if sample["at_mi"] <= float(mile))
        assert active["mph"] == 55.0, f"mileage {mile} only found {active['mph']} mph"
    assert "accessed 2026-06-23" in maxspeed._maxspeed_source("fixture geometry")
    assert "accessed 2026-10-07" in maxspeed._maxspeed_source(
        "fixture geometry", accessed_date="2026-10-07"
    )


def test_maxspeed_break_samples_use_the_road_after_the_line():
    geometry = [(_north(mile), -80.0, float(mile)) for mile in range(101)]
    before_break = maxspeed.LocalMaxspeedWay(
        osm_id=3,
        coords=tuple((_north(mile), -80.0) for mile in range(70, 90)),
        mph=65.0,
        hgv=False,
        ref="",
    )
    after_break = maxspeed.LocalMaxspeedWay(
        osm_id=4,
        coords=tuple((_north(mile), -80.0) for mile in range(90, 101)),
        mph=55.0,
        hgv=False,
        ref="",
    )

    profile = maxspeed.assemble_maxspeed(
        maxspeed.build_maxspeed_grid([before_break, after_break]),
        geometry,
        100.0,
        "US 1",
        source="fixture",
        breaks=(89.5,),
    )

    at_break = [sample for sample in profile if sample["at_mi"] == 89.5]
    assert at_break and at_break[0]["mph"] == 55.0
    for mile in [89.5, *range(90, 101)]:
        active = next(sample for sample in reversed(profile) if sample["at_mi"] <= mile)
        assert active["mph"] == 55.0, f"mileage {mile} only found {active['mph']} mph"


def test_maxspeed_break_sample_ignores_pre_break_points():
    geometry = [(_north(mile), -80.0, float(mile)) for mile in range(101)]
    before_break = maxspeed.LocalMaxspeedWay(
        osm_id=5,
        coords=tuple((_north(mile), -80.0) for mile in range(70, 90)),
        mph=65.0,
        hgv=False,
        ref="",
    )

    profile = maxspeed.assemble_maxspeed(
        maxspeed.build_maxspeed_grid([before_break]),
        geometry,
        100.0,
        "US 1",
        source="fixture",
        breaks=(89.5,),
    )

    assert all(sample["at_mi"] < 89.5 for sample in profile)


def test_valhalla_geometry_joins_pairs_deduplicates_rescales_and_caches(monkeypatch, tmp_path):
    route_points = [
        {"lat": _north(0), "lon": -80.0, "at_mi": 0.0},
        {"lat": _north(5), "lon": -80.0, "at_mi": 5.1},
        {"lat": _north(10), "lon": -80.0, "at_mi": 10.2},
    ]
    leg = {
        "from": "a_pa_us",
        "to": "b_pa_us",
        "miles": 10.2,
        "corridor": {"route_points": route_points},
    }
    calls = []
    route_shapes = [
        [[-80.0, _north(0)], [-80.0, _north(5)]],
        [[-80.0, _north(5)], [-80.0, _north(10)]],
    ]

    def fetch_route(start, end):
        calls.append((start, end))
        return route_shapes[len(calls) - 1], 5.0, False

    monkeypatch.setattr(maxspeed.lg, "corridor_geometry", lambda _leg: None)
    monkeypatch.setattr(maxspeed.reroute_leg, "fetch_route", fetch_route)
    cache_path = tmp_path / "maxspeed-valhalla-geometry.json"

    geometry, source = maxspeed.leg_corridor_geometry_with_source(
        leg, 0.0, valhalla_geometry=True, valhalla_cache_path=cache_path
    )

    assert source == maxspeed.VALHALLA_GEOMETRY_SOURCE
    assert geometry is not None
    assert len(geometry) == 3
    assert [point[2] for point in geometry] == pytest.approx([0.0, 5.1, 10.2])
    assert calls == [
        (
            {"lat": route_points[0]["lat"], "lon": -80.0},
            {"lat": route_points[1]["lat"], "lon": -80.0},
        ),
        (
            {"lat": route_points[1]["lat"], "lon": -80.0},
            {"lat": route_points[2]["lat"], "lon": -80.0},
        ),
    ]

    cached_geometry, cached_source = maxspeed.leg_corridor_geometry_with_source(
        leg, 0.0, valhalla_geometry=True, valhalla_cache_path=cache_path
    )
    assert cached_source == source
    assert cached_geometry == geometry
    assert len(calls) == 2


def test_invalid_valhalla_geometry_returns_none_and_uses_existing_fallback(monkeypatch, tmp_path):
    route_points = [
        {"lat": _north(0), "lon": -80.0, "at_mi": 0.0},
        {"lat": _north(5), "lon": -80.0, "at_mi": 5.1},
        {"lat": _north(10), "lon": -80.0, "at_mi": 10.2},
    ]
    leg = {
        "from": "a_pa_us",
        "to": "b_pa_us",
        "miles": 10.2,
        "corridor": {"route_points": route_points},
    }
    route_shapes = [
        [[-80.0, _north(0)], [-80.0, _north(4.9)]],
        [[-80.0, _north(4.9)], [-80.0, _north(9.8)]],
    ]
    calls = 0

    def fetch_route(_start, _end):
        nonlocal calls
        shape = route_shapes[calls]
        calls += 1
        return shape, 4.9, False

    monkeypatch.setattr(maxspeed.lg, "corridor_geometry", lambda _leg: None)
    monkeypatch.setattr(maxspeed.reroute_leg, "fetch_route", fetch_route)
    cache_path = tmp_path / "maxspeed-valhalla-geometry.json"

    assert maxspeed._valhalla_geometry_for_leg(leg, cache_path) is None

    monkeypatch.setattr(maxspeed, "_valhalla_geometry_for_leg", lambda _leg, _cache_path: None)
    monkeypatch.setattr(maxspeed, "_osrm_geometry", lambda *_args, **_kwargs: None)
    geometry, source = maxspeed.leg_corridor_geometry_with_source(
        leg, 0.0, valhalla_geometry=True, valhalla_cache_path=cache_path
    )
    assert geometry == maxspeed._interpolated_geometry(route_points)
    assert "linear interpolation" in source


def test_alaska_fallback_range_excludes_the_jurisdiction_break():
    geometry = [(_north(mile), -80.0, float(mile)) for mile in range(101)]
    before_break = maxspeed.LocalMaxspeedWay(
        osm_id=7,
        coords=tuple((_north(mile), -80.0) for mile in range(70, 90)),
        mph=65.0,
        hgv=False,
        ref="",
    )

    profile = maxspeed.assemble_maxspeed(
        maxspeed.build_maxspeed_grid([before_break]),
        geometry,
        100.0,
        "US 1",
        source="OSM fixture",
        fallback=maxspeed.ALASKA_UNPOSTED_SPEED,
        fallback_range=(0.0, 89.5),
        breaks=(89.5,),
    )

    assert all(
        sample["at_mi"] < 89.5
        for sample in profile
        if sample["source"] == maxspeed.ALASKA_UNPOSTED_SPEED[1]
    )


def test_alaska_fallback_range_includes_leg_endpoint():
    geometry = [(_north(mile), -80.0, float(mile)) for mile in (0, 10)]

    profile = maxspeed.assemble_maxspeed(
        {},
        geometry,
        10.0,
        "US 1",
        fallback=maxspeed.ALASKA_UNPOSTED_SPEED,
        fallback_range=(10.0, 10.0),
    )

    assert profile == [
        {
            "at_mi": 10.0,
            "mph": 55.0,
            "source": maxspeed.ALASKA_UNPOSTED_SPEED[1],
            "hgv": False,
        }
    ]
