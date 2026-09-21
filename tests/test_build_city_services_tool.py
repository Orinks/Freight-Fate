import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("osmium")


def _load_tool():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_city_services.py"
    spec = importlib.util.spec_from_file_location("build_city_services", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_city_services_from_tiny_osm_fixture(tmp_path):
    tool = _load_tool()
    osm_path = tmp_path / "services.osm"
    osm_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="fixture">
  <node id="1" lat="41.8781" lon="-87.6298" />
  <node id="2" lat="41.8800" lon="-87.6305" />
  <node id="3" lat="41.8820" lon="-87.6310" />
  <node id="4" lat="41.8810" lon="-87.6320" />
  <node id="10" lat="41.8790" lon="-87.6310">
    <tag k="name" v="Lakefront Freight Logistics" />
    <tag k="office" v="logistics" />
  </node>
  <way id="20">
    <nd ref="1" />
    <nd ref="2" />
    <tag k="name" v="Great Lakes Truck Repair" />
    <tag k="shop" v="truck_repair" />
  </way>
  <way id="30">
    <nd ref="3" />
    <nd ref="4" />
    <tag k="name" v="Prairie Freightliner" />
    <tag k="shop" v="truck" />
  </way>
  <way id="40">
    <nd ref="1" />
    <nd ref="2" />
    <nd ref="3" />
    <tag k="highway" v="service" />
    <tag k="name" v="Freight Yard Road" />
  </way>
</osm>
""",
        encoding="utf-8",
    )

    entries = tool.build_city_services(
        osm_path,
        "Chicago",
        "Illinois",
        41.8781,
        -87.6298,
        5.0,
    )

    by_key = {entry["key"]: entry for entry in entries}
    assert set(by_key) == {"freight_market", "garage", "truck_dealer"}
    assert by_key["freight_market"]["name"] == "Lakefront Freight Logistics"
    assert by_key["garage"]["name"] == "Great Lakes Truck Repair"
    assert by_key["truck_dealer"]["name"] == "Prairie Freightliner"
    assert all(entry["source_type"] == "osm" for entry in entries)
    assert all(entry["fallback"] is False for entry in entries)
    assert all(entry["approach_road"] == "Freight Yard Road" for entry in entries)
    assert not any("node/" in entry["name"].lower() for entry in entries)


def test_build_all_supported_marks_missing_extracts_as_fallback(tmp_path, monkeypatch):
    tool = _load_tool()
    # The city list is sourced from the loaded world (so the state resolves to a
    # full name for the per-state extract filename); inject a fixture city at
    # that seam and point at an empty cache so every service falls back.
    monkeypatch.setattr(
        tool,
        "load_world_cities",
        lambda *, radius_mi=tool.DEFAULT_RADIUS_MI: [
            tool.CityInfo("Fixture City", "Example State", 40.0, -90.0, radius_mi)
        ],
    )

    payload = tool.build_all_supported(tmp_path / "missing-cache")

    entries = payload["cities"]["Fixture City"]
    assert [entry["key"] for entry in entries] == [
        "freight_market",
        "garage",
        "truck_dealer",
    ]
    assert all(entry["fallback"] for entry in entries)
    assert all(entry["source_type"] == "fallback" for entry in entries)
    assert all("Missing local OSM extract" in entry["fallback_reason"] for entry in entries)
    assert payload["coverage"]["fallback"] == 3
