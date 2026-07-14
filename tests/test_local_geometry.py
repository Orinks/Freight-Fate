import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAW_MARKERS = ("osm_id", "amenity=", "highway=", "operator=", "node/", "way/", "source_ref")
ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "build_local_geometry.py"
TOOL_SPEC = importlib.util.spec_from_file_location("build_local_geometry", TOOL_PATH)
assert TOOL_SPEC is not None
build_local_geometry = importlib.util.module_from_spec(TOOL_SPEC)
assert TOOL_SPEC.loader is not None
sys.modules[TOOL_SPEC.name] = build_local_geometry
TOOL_SPEC.loader.exec_module(build_local_geometry)


def test_local_geometry_data_covers_supported_map(world):
    data = json.loads(Path("src/freight_fate/data/local_geometry.json").read_text(encoding="utf-8"))
    coverage = data["coverage"]

    assert "OpenRouteService driving-hgv" in data["generated"]["routing_decision"]
    assert "not ORS-certified HGV routes" in data["generated"]["routing_decision"]
    assert coverage["targets"] == 6233
    assert coverage["turn_level"] == 509
    assert coverage["fallback"] == 5724
    assert coverage["estimated"] == 5724
    assert coverage["by_type"]["city_service"] == {
        "estimated": 238,
        "fallback": 238,
        "total": 747,
        "turn_level": 509,
    }
    assert coverage["by_type"]["facility"] == {
        "estimated": 5486,
        "fallback": 5486,
        "total": 5486,
        "turn_level": 0,
    }

    # The coverage block records the sweep's own inventory; the map has grown
    # since, so today's world may only exceed it (new targets are simply not
    # covered until the next sweep re-runs).
    services = sum(len(world.city_services(city)) for city in world.city_names())
    facilities = sum(len(world.cities[city].locations) for city in world.city_names())
    assert services + facilities >= coverage["targets"]


def test_local_geometry_records_are_clean_and_honest(world):
    data = json.loads(Path("src/freight_fate/data/local_geometry.json").read_text(encoding="utf-8"))

    retired = []
    for target_id, record in data["geometries"].items():
        # Sweep ids predate the slug migration; the world canonicalizes them
        # at load. A record whose facility retired with map growth is inert.
        geometry = world.local_geometry(world._canonical_local_id(target_id))
        if geometry is None:
            retired.append(target_id)
            continue
        assert record["name"]
        assert record["segments"]
        assert record["total_miles"] > 0
        spoken = " ".join(
            [record["name"], record.get("final_hint", "")]
            + [segment["road"] for segment in record["segments"]]
            + [segment["cue"] for segment in record["segments"]]
        ).lower()
        assert not any(marker in spoken for marker in RAW_MARKERS)
        if record["turn_level"]:
            assert not record["fallback"]
            assert record["source_type"] == "osm_local_road_graph"
            assert record["target_type"] == "city_service"
            assert len(record["segments"]) >= 1
        else:
            assert record["fallback"]
            assert record["fallback_reason"]
            assert record["source_type"] == "nearest_road_context"
    assert len(retired) <= 8, retired


def test_city_service_route_prefers_turn_level_geometry(world):
    route = world.city_service_route("Chicago", "freight_market")
    geometry = world.city_service_geometry("Chicago", "freight_market")

    assert geometry is not None
    assert geometry.turn_level
    assert len(route.legs) == len(geometry.segments)
    assert route.miles == pytest.approx(geometry.total_miles)
    assert route.highways == [segment.road for segment in geometry.segments]


def test_facility_geometry_stays_estimated_fallback(world):
    facility = world.city("Chicago").locations[0]
    geometry = world.facility_geometry("Chicago", facility.name)

    assert geometry is not None
    assert not geometry.turn_level
    assert geometry.fallback
    assert geometry.estimated
    assert "representative freight-market coordinates" in geometry.fallback_reason


def test_local_geometry_trip_uses_local_turn_cues(world):
    from freight_fate.sim.trip import Trip
    from freight_fate.sim.vehicle import TruckState
    from freight_fate.sim.weather import WeatherKind, WeatherSystem

    route = world.city_service_route("Chicago", "freight_market")
    weather = WeatherSystem("great_lakes", seed=1)
    weather.current = WeatherKind.CLEAR
    trip = Trip(route, TruckState(), weather, seed=1)

    cues = [cue for cue in trip.navigation_cues if cue.kind == "local_turn"]

    assert cues
    assert cues[0].near_text.startswith("Start on ")
    assert not any("merge onto" in cue.near_text.lower() for cue in cues)
    # Directional bake: every boundary cue is a turn with a side or an
    # explicit continue, never the old directionless "Turn onto".
    assert all(
        cue.near_text.startswith(("Turn left onto", "Turn right onto", "Continue onto"))
        for cue in cues[1:]
    )
    assert any(cue.near_text.startswith("Turn ") for cue in cues[1:])


def test_build_tool_routes_tiny_osm_fixture(tmp_path):
    osm = tmp_path / "tiny.osm"
    osm.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="41.0000" lon="-87.0000" />
  <node id="2" lat="41.0005" lon="-87.0000" />
  <node id="3" lat="41.0005" lon="-86.9990" />
  <way id="10">
    <nd ref="1" />
    <nd ref="2" />
    <tag k="highway" v="service" />
    <tag k="name" v="Terminal Drive" />
  </way>
  <way id="20">
    <nd ref="2" />
    <nd ref="3" />
    <tag k="highway" v="tertiary" />
    <tag k="name" v="Market Street" />
  </way>
</osm>
""",
        encoding="utf-8",
    )
    target = build_local_geometry.Target(
        target_id="city_service:test:garage",
        target_type="city_service",
        city="Chicago",
        state="Illinois",
        name="Fixture Garage",
        lat=41.0005,
        lon=-86.9990,
        start_lat=41.0000,
        start_lon=-87.0000,
        role="garage",
        estimated=False,
        fallback_reason="",
        approach_road="Market Street",
        approach_miles=1.0,
        source_note="Fixture source.",
    )

    routes = build_local_geometry.route_state_targets(osm, [target])

    assert target.target_id in routes
    segments = routes[target.target_id].segments
    assert [segment["road"] for segment in segments] == [
        "Terminal Drive",
        "Market Street",
    ]
    # North up Terminal Drive, then east on Market Street: a right turn,
    # read out of the geometry so the panned earcon direction is baked in.
    assert segments[0]["cue"] == "Start on Terminal Drive."
    assert segments[1]["cue"] == "Turn right onto Market Street."
