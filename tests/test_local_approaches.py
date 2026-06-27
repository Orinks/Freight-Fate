import importlib.util
import json
import sys
from pathlib import Path

RAW_MARKERS = ("osm_id", "amenity=", "highway=", "operator=", "node/", "way/")
TOOL_PATH = Path("tools/build_local_approaches.py")
TOOL_SPEC = importlib.util.spec_from_file_location("build_local_approaches", TOOL_PATH)
assert TOOL_SPEC is not None
build_local_approaches = importlib.util.module_from_spec(TOOL_SPEC)
assert TOOL_SPEC.loader is not None
sys.modules[TOOL_SPEC.name] = build_local_approaches
TOOL_SPEC.loader.exec_module(build_local_approaches)


def test_local_approach_data_covers_supported_map(world):
    path = Path("src/freight_fate/data/local_approaches.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    coverage = data["coverage"]

    assert coverage["approaches"] == 2401
    assert coverage["osm_road"] == 2395
    assert coverage["fallback"] == 6
    assert coverage["estimated"] == 1907
    assert coverage["by_type"]["city_service"] == {
        "estimated": 88,
        "fallback": 0,
        "osm_road": 582,
        "total": 582,
    }
    assert coverage["by_type"]["facility"] == {
        "estimated": 1819,
        "fallback": 6,
        "osm_road": 1813,
        "total": 1819,
    }

    services = sum(len(world.city_services(city)) for city in world.city_names())
    facilities = sum(len(world.cities[city].locations) for city in world.city_names())
    assert services == coverage["by_type"]["city_service"]["total"]
    assert facilities == coverage["by_type"]["facility"]["total"]


def test_local_approach_records_are_clean_and_marked(world):
    path = Path("src/freight_fate/data/local_approaches.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    for target_id, record in data["approaches"].items():
        assert world.local_approach(target_id) is not None
        assert record["name"]
        assert record["road"]
        assert record["approach_miles"] > 0
        assert record["target_type"] in {"city_service", "facility"}
        spoken = " ".join((
            record["name"],
            record["road"],
            " ".join(record["turn_segments"]),
        )).lower()
        assert not any(marker in spoken for marker in RAW_MARKERS)
        if record["fallback"]:
            assert record["fallback_reason"]
            assert record["source_type"] == "fallback_context"
        else:
            assert record["distance_to_road_mi"] <= build_local_approaches.SEARCH_RADIUS_MI
            assert record["source_type"] in {
                "osm_nearest_road",
                "estimated_target_osm_nearest_road",
            }


def test_city_service_and_facility_routes_use_local_approach_layer(world):
    service_route = world.city_service_route("Chicago", "garage")
    service_approach = world.city_service_approach("Chicago", "garage")
    service_geometry = world.city_service_geometry("Chicago", "garage")
    assert service_approach is not None
    assert service_geometry is not None
    assert service_geometry.turn_level
    assert service_route.miles == service_geometry.total_miles
    assert service_route.highways == [segment.road for segment in service_geometry.segments]

    facility = world.cities["Chicago"].locations[0]
    facility_route = world.facility_approach_route("Chicago", facility.name)
    facility_approach = world.facility_approach("Chicago", facility.name)
    facility_endpoint = world.facility_endpoint("Chicago", facility.name)
    assert facility_approach is not None
    if facility_endpoint is not None and facility_endpoint.source_backed:
        assert facility_route.miles == facility_endpoint.approach_miles
    else:
        assert facility_route.miles == facility_approach.approach_miles
    assert facility_route.highways == [facility_approach.road]


def test_build_tool_snaps_tiny_osm_fixture_to_named_road(tmp_path):
    osm = tmp_path / "tiny.osm"
    osm.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="41.0000" lon="-87.0000" />
  <node id="2" lat="41.0010" lon="-87.0000" />
  <way id="10">
    <nd ref="1" />
    <nd ref="2" />
    <tag k="highway" v="service" />
    <tag k="name" v="Dock Road" />
  </way>
</osm>
""",
        encoding="utf-8",
    )
    target = build_local_approaches.Target(
        target_id="facility:test",
        target_type="facility",
        city="Chicago",
        state="Illinois",
        name="Fixture Dock",
        lat=41.0005,
        lon=-87.0001,
        role="terminal",
        estimated=False,
        source_note="Fixture source.",
    )

    build_local_approaches.snap_roads(osm, [target])

    assert target.best_road == "Dock Road"
    assert target.best_distance_mi < build_local_approaches.SEARCH_RADIUS_MI


def test_build_tool_marks_missing_road_context_as_fallback(monkeypatch):
    target = build_local_approaches.Target(
        target_id="facility:test",
        target_type="facility",
        city="Chicago",
        state="Illinois",
        name="Fixture Dock",
        lat=41.0,
        lon=-87.0,
        role="terminal",
        estimated=True,
        source_note="Fixture source.",
        fallback_reason="Representative fixture coordinate.",
    )
    monkeypatch.setattr(build_local_approaches, "city_lat_lon", lambda _target: (41.0, -87.0))

    record = build_local_approaches.approach_record(target)

    assert record["fallback"]
    assert record["estimated"]
    assert record["road"] == "local facility access road"
    assert record["fallback_reason"] == "Representative fixture coordinate."
