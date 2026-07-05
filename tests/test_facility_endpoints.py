import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAW_MARKERS = ("osm_id", "amenity=", "highway=", "operator=", "node/", "way/", "source_ref")


def _load_tool():
    pytest.importorskip("osmium")
    path = Path(__file__).resolve().parents[1] / "tools" / "build_facility_endpoints.py"
    spec = importlib.util.spec_from_file_location("build_facility_endpoints", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_facility_endpoint_data_covers_supported_facilities(world):
    data = json.loads(
        Path("src/freight_fate/data/facility_endpoints.json").read_text(encoding="utf-8-sig")
    )
    coverage = data["coverage"]

    assert coverage["facilities"] == 2405
    assert coverage["source_backed"] == 1842
    assert coverage["fallback"] == 563
    assert coverage["nearest_road_context"] == 0
    assert coverage["turn_level_geometry"] == 0
    assert coverage["gate_yard_dock_hints"] == 0

    facilities = sum(len(world.cities[city].locations) for city in world.city_names())
    assert facilities == coverage["facilities"]
    assert set(data["endpoints"]) == {
        location.id for city in world.city_names() for location in world.cities[city].locations
    }


def test_facility_endpoint_records_are_clean_and_honest(world):
    data = json.loads(
        Path("src/freight_fate/data/facility_endpoints.json").read_text(encoding="utf-8-sig")
    )

    for facility_id, record in data["endpoints"].items():
        endpoint = world.facility_endpoint(record["city"], facility_id)
        assert endpoint is not None
        spoken = " ".join(
            (
                record["facility_name"],
                record["endpoint_name"],
                record["approach_road"],
            )
        ).lower()
        assert not any(marker in spoken for marker in RAW_MARKERS)
        assert record["source_note"]
        assert not record["gate_hint"]
        assert not record["yard_hint"]
        assert not record["dock_hint"]
        assert not record["turn_level_geometry"]
        if record["source_backed"]:
            assert not record["fallback"]
            assert record["source_type"] == "osm_facility_endpoint"
            assert record["approach_miles"] > 0
            assert record["approach_road"] == "local facility access road"
            assert "not claimed by this layer" in record["source_note"]
        else:
            assert record["fallback"]
            assert record["fallback_reason"]
            assert record["source_type"] == "representative_fallback"
            assert record["approach_miles"] == 0.0


def test_facility_route_prefers_source_backed_endpoint_when_available(world):
    facility = world.facility_by_id("abilene:chemical_petroleum_terminal:abilene-energy-terminal")
    endpoint = world.facility_endpoint("Abilene", facility.id)
    route = world.facility_approach_route("Abilene", facility.name)

    assert endpoint is not None
    assert endpoint.source_backed
    assert route.miles == pytest.approx(endpoint.approach_miles)
    assert route.highways == [world.facility_approach("Abilene", facility.name).road]


def test_facility_route_falls_back_to_local_approach_for_representative_endpoint(world):
    facility = world.facility_by_id("abilene:grocery_retail_dc:abilene-grocery-distribution-center")
    endpoint = world.facility_endpoint("Abilene", facility.id)
    approach = world.facility_approach("Abilene", facility.name)
    route = world.facility_approach_route("Abilene", facility.name)

    assert endpoint is not None
    assert endpoint.fallback
    assert approach is not None
    assert route.miles == pytest.approx(approach.approach_miles)
    assert route.highways == [approach.road]


def test_build_tool_classifies_tiny_osm_fixture(tmp_path, monkeypatch):
    tool = _load_tool()
    osm_path = tmp_path / "facilities.osm"
    osm_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="fixture">
  <node id="1" lat="41.0" lon="-87.0" />
  <node id="2" lat="41.0" lon="-86.99" />
  <node id="3" lat="41.01" lon="-86.99" />
  <way id="10">
    <nd ref="1" />
    <nd ref="2" />
    <nd ref="3" />
    <tag k="name" v="Lakefront Distribution Warehouse" />
    <tag k="industrial" v="logistics" />
  </way>
</osm>
""",
        encoding="utf-8",
    )
    target = tool.FacilityTarget(
        facility_id="fixture:warehouse",
        city="Fixture City",
        state="Illinois",
        name="Fixture Warehouse",
        facility_type="warehouse",
        lat=41.0,
        lon=-87.0,
        source_note="fixture",
    )
    monkeypatch.setattr(tool, "collect_targets", lambda: [target])
    monkeypatch.setattr(tool, "state_extract_path", lambda _cache, _state: osm_path)

    payload = tool.build_facility_endpoints(tmp_path, radius_mi=10.0)
    record = payload["endpoints"]["fixture:warehouse"]

    assert payload["coverage"]["source_backed"] == 1
    assert record["endpoint_name"] == "Lakefront Distribution Warehouse"
    assert record["source_backed"]
    assert not record["nearest_road_context"]
    assert not record["gate_hint"]
    assert record["approach_road"] == "local facility access road"


def test_build_tool_marks_missing_extracts_as_fallback(tmp_path, monkeypatch):
    tool = _load_tool()
    target = tool.FacilityTarget(
        facility_id="fixture:fallback",
        city="Fixture City",
        state="Missing State",
        name="Fixture Yard",
        facility_type="construction_materials_yard",
        lat=41.0,
        lon=-87.0,
        source_note="fixture",
    )
    monkeypatch.setattr(tool, "collect_targets", lambda: [target])

    payload = tool.build_facility_endpoints(tmp_path)
    record = payload["endpoints"]["fixture:fallback"]

    assert payload["coverage"]["fallback"] == 1
    assert record["fallback"]
    assert (
        "No high-confidence source-backed OSM facility endpoint found" in record["fallback_reason"]
    )
