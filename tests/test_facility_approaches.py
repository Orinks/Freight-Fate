import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAW_MARKERS = ("osm_id", "amenity=", "highway=", "operator=", "node/", "way/", "source_ref")


def _load_tool():
    pytest.importorskip("osmium")
    path = Path(__file__).resolve().parents[1] / "tools" / "build_facility_approaches.py"
    spec = importlib.util.spec_from_file_location("build_facility_approaches", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_facility_approach_data_covers_full_facility_set(world):
    data = json.loads(
        Path("src/freight_fate/data/facility_approaches.json").read_text(encoding="utf-8")
    )
    coverage = data["coverage"]

    assert coverage["facilities"] == 2401
    assert coverage["source_backed_endpoints"] == 1838
    assert coverage["road_snapped"] == 916
    assert coverage["turn_level"] == 821
    assert coverage["nearest_road_fallback"] == 922
    assert coverage["representative_fallback"] == 563
    assert coverage["gate_yard_dock_hints"] == 0

    # The 2026-07-14 regen keys records by current slug facility ids and
    # covers every facility the endpoint/local-approach sweeps know about;
    # facilities added by map growth since those sweeps are simply absent
    # until the next data expansion pass (see ROADMAP).
    facilities = {
        location.id for city in world.city_names() for location in world.cities[city].locations
    }
    resolved, missing = set(), []
    for facility_id in data["approaches"]:
        try:
            resolved.add(world.facility_by_id(facility_id).id)
        except KeyError:
            missing.append(facility_id)
    assert resolved <= facilities
    assert not missing, missing[:10]
    assert len(resolved) == coverage["facilities"]


def test_facility_approach_records_are_clean_and_honest(world):
    data = json.loads(
        Path("src/freight_fate/data/facility_approaches.json").read_text(encoding="utf-8")
    )

    for facility_id, record in data["approaches"].items():
        try:
            world.facility_by_id(facility_id)
        except KeyError:
            continue  # facility retired by map growth; record is inert
        approach = world.facility_source_approach(record["city"], facility_id)
        assert approach is not None
        spoken = " ".join(
            [record["facility_name"], record["endpoint_name"], record["approach_road"]]
            + [segment["road"] for segment in record["segments"]]
            + [segment["cue"] for segment in record["segments"]]
        ).lower()
        assert not any(marker in spoken for marker in RAW_MARKERS)
        assert not record["gate_hint"]
        assert not record["yard_hint"]
        assert not record["dock_hint"]
        if record["turn_level"]:
            assert record["road_snapped"]
            assert record["nearest_road_context"]
            assert record["source_type"] == "osm_local_road_graph"
            assert not record["fallback"]
            assert record["total_miles"] > 0
            assert len(record["segments"]) >= 1
        else:
            assert record["fallback"]
            assert record["fallback_reason"]
            assert record["source_type"] == "facility_approach_fallback"


def test_facility_route_prefers_turn_level_source_approach(world):
    from freight_fate.sim.trip import Trip, TripEvent, TripEventKind
    from freight_fate.sim.vehicle import TruckState
    from freight_fate.sim.weather import WeatherSystem
    from freight_fate.states.driving import _route_event_sound

    data = json.loads(
        Path("src/freight_fate/data/facility_approaches.json").read_text(encoding="utf-8")
    )
    facility_id, record = next(item for item in data["approaches"].items() if item[1]["turn_level"])
    facility = world.facility_by_id(facility_id)
    route = world.facility_approach_route(record["city"], facility.name)
    approach = world.facility_source_approach(record["city"], facility.name)

    assert approach is not None
    assert approach.turn_level
    assert route.miles == pytest.approx(approach.total_miles)
    assert route.highways == [segment.road for segment in approach.segments]
    trip = Trip(route, TruckState(), WeatherSystem())
    start_cue = next(cue for cue in trip.navigation_cues if cue.key == "local:start")
    assert start_cue.direction == "ahead"
    assert (
        _route_event_sound(
            TripEvent(TripEventKind.GPS_CUE, start_cue.near_text, {"cue": start_cue})
        )
        == "events/turn_ahead"
    )


def test_facility_route_keeps_existing_fallback_when_no_source_geometry(world):
    facility = world.facility_by_id("abilene:grocery_retail_dc:abilene-grocery-distribution-center")
    source_approach = world.facility_source_approach("Abilene", facility.name)
    fallback_approach = world.facility_approach("Abilene", facility.name)
    route = world.facility_approach_route("Abilene", facility.name)

    assert source_approach is not None
    assert source_approach.fallback
    assert fallback_approach is not None
    assert route.miles == pytest.approx(fallback_approach.approach_miles)
    assert route.highways == [fallback_approach.road]


def test_build_tool_routes_tiny_facility_fixture(tmp_path, monkeypatch):
    tool = _load_tool()
    osm_path = tmp_path / "facility.osm"
    osm_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="fixture">
  <node id="1" lat="41.0000" lon="-87.0000" />
  <node id="2" lat="41.0000" lon="-86.9950" />
  <node id="3" lat="41.0000" lon="-86.9900" />
  <way id="10">
    <nd ref="1" />
    <nd ref="2" />
    <tag k="highway" v="tertiary" />
    <tag k="name" v="Terminal Road" />
  </way>
  <way id="20">
    <nd ref="2" />
    <nd ref="3" />
    <tag k="highway" v="service" />
    <tag k="name" v="Warehouse Drive" />
  </way>
</osm>
""",
        encoding="utf-8",
    )
    target = tool.FacilityTarget(
        facility_id="fixture:warehouse",
        city="Fixture City",
        state="Illinois",
        facility_name="Fixture Warehouse",
        facility_type="warehouse",
        endpoint_name="Real Warehouse",
        lat=41.0000,
        lon=-86.9900,
        start_lat=41.0000,
        start_lon=-87.0000,
        endpoint_source_backed=True,
        endpoint_fallback=False,
        endpoint_source_note="fixture",
        local_approach_miles=0.8,
        local_approach_road="Terminal Road",
    )
    monkeypatch.setattr(tool, "collect_targets", lambda: [target])
    monkeypatch.setattr(tool, "MIN_PLAYABLE_ROUTE_MI", 0.1)
    local_geometry = tool._load_local_geometry_tool()
    monkeypatch.setattr(local_geometry, "state_extract_path", lambda _cache, _state: osm_path)
    monkeypatch.setattr(tool, "_load_local_geometry_tool", lambda: local_geometry)

    payload = tool.build_facility_approaches(
        tmp_path,
        states=("Illinois",),
        max_route_mi=2.0,
    )
    record = payload["approaches"]["fixture:warehouse"]

    assert payload["coverage"]["road_snapped"] == 1
    assert record["turn_level"]
    assert record["approach_road"] == "Terminal Road"
    assert [segment["road"] for segment in record["segments"]] == [
        "Terminal Road",
        "Warehouse Drive",
    ]
