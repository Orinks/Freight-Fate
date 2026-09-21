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
    data = json.loads(Path("data/facility_endpoints.json").read_text(encoding="utf-8-sig"))
    coverage = data["coverage"]

    assert coverage["facilities"] == 4271
    # After far-pin regeocode: 357 OSM rematches stayed source-backed; 419
    # unresolvable pins became estimated-near-city fallbacks (2779/2258).
    # The 2026-09-17 re-sweep with the matcher that reads an object's own
    # tags then filled 155 fallbacks (2934/2103) and replaced 1,224 endpoints
    # that were railway lines, substations and shops. What the screen says of
    # every sourced row is in the row: 1,939 are freight sites, 995 still are
    # not (nothing better within 6.4 miles), and 175 of the sites state no
    # trade, so the match to this facility's trade is assumed and says so.
    # The 2026-09-20 sweep added the four families that had no matcher rule at
    # all -- grain elevators, quarries, construction materials yards, lumber
    # and paper. All 419 of their rows were fallbacks; 129 now have a sourced
    # endpoint and every one passes the screen, which is the whole of the +129.
    # `passed` rose by only 110 because 19 rows correctly STOPPED passing: a
    # lumber mill, a quarry and a grain company had been standing in as assumed
    # cross-docks, and the matcher now knows what they are.
    assert coverage["source_backed"] == 2874
    assert coverage["fallback"] == 1397
    assert coverage["screen"] == {
        "passed": 2049,
        "refused": 825,
        "not_screened": 0,
        "trade_assumed": 173,
    }
    assert coverage["nearest_road_context"] == 0
    assert coverage["turn_level_geometry"] == 0
    assert coverage["gate_yard_dock_hints"] == 0

    # The sweep predates the slug migration and the map expansion: its
    # records must keep resolving onto today's facilities (legacy-id
    # translation), while facilities added since the sweep are simply not
    # covered yet. A few records retire when map growth replaces a template
    # facility with a real one (Gulfport/Mobile), never more than a handful.
    facilities = {
        location.id for city in world.city_names() for location in world.cities[city].locations
    }
    resolved, missing = set(), []
    for facility_id in data["endpoints"]:
        try:
            resolved.add(world.facility_by_id(facility_id).id)
        except KeyError:
            missing.append(facility_id)
    assert resolved <= facilities
    assert len(resolved) >= coverage["facilities"] - 8, missing[:10]


def test_facility_endpoint_records_are_clean_and_honest(world):
    data = json.loads(Path("data/facility_endpoints.json").read_text(encoding="utf-8-sig"))

    for facility_id, record in data["endpoints"].items():
        try:
            world.facility_by_id(facility_id)
        except KeyError:
            continue  # facility retired by map growth; record is inert
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
            # The screen verdict rides in the row, so a railway line that
            # found no replacement is never mistaken for a yard gate.
            assert record["endpoint_screen"] in ("passed", "refused")
            if record["endpoint_screen"] == "refused":
                assert record["endpoint_screen_reason"]
            if "match_kind" in record:
                assert record["match_kind"] in ("read", "assumed")
            assert record["approach_miles"] <= 8.0
            assert record["approach_miles"] > 0
            assert record["approach_road"] == "local facility access road"
            assert "not claimed by this layer" in record["source_note"]
        else:
            assert record["fallback"]
            assert record["fallback_reason"]
            assert record["source_type"] == "representative_fallback"
            if record.get("estimated"):
                # Estimated-near-city pins keep a real offset; they must not
                # claim source-backed OSM at zero miles.
                assert record["approach_miles"] > 0
                assert "Estimated-near-city" in record["source_note"]
                assert "estimated near city" in record["fallback_reason"].lower()
            else:
                assert record["approach_miles"] == 0.0


def test_facility_route_prefers_source_backed_endpoint_when_available(world):
    # A sourced endpoint with NO street chain (it sits a few blocks from the
    # city anchor, under the chain floor). The Abilene energy terminal this
    # used to pin gained a chain in the 2026-09-17 re-sweep.
    facility = world.facility_by_id("muncie-in-us:cross_dock:muncie-cross-dock")
    endpoint = world.facility_endpoint("muncie_in_us", facility.id)
    route = world.facility_approach_route("muncie_in_us", facility.name)

    assert endpoint is not None
    assert endpoint.source_backed
    assert route.miles == pytest.approx(endpoint.approach_miles)
    assert route.highways == [world.facility_approach("muncie_in_us", facility.name).road]


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
