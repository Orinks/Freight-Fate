import importlib.util
import sys
from pathlib import Path

import pytest


def _load_tool():
    pytest.importorskip("osmium")
    path = Path(__file__).resolve().parents[1] / "tools" / "build_facility_endpoints.py"
    spec = importlib.util.spec_from_file_location("build_facility_endpoints", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
