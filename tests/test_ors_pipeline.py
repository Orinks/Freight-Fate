"""OpenRouteService driving-hgv build-pipeline scaffold (no network).

These exercise the pure mapping and key handling so the pipeline is ready the
moment a real ORS key is available; the live request itself is covered by the
credential-gated ``--ors-smoke`` CLI, not the unit suite.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_enrich_routes():
    """Import tools/enrich_routes.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "enrich_routes", ROOT / "tools" / "enrich_routes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


enrich_routes = _load_enrich_routes()


def _mock_ors_payload():
    """A minimal driving-hgv GeoJSON response: 3D coords + steepness + tollways."""
    return {
        "features": [{
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-87.63, 41.88, 180.0],
                    [-86.90, 41.00, 200.0],
                    [-86.16, 39.77, 220.0],
                ],
            },
            "properties": {
                "summary": {"distance": 296000.0, "duration": 10000.0},
                "extras": {
                    "steepness": {"values": [[0, 1, 0], [1, 2, 2]]},
                    "tollways": {"values": [[0, 2, 1]]},
                },
            },
        }]
    }


def test_parse_ors_route_maps_geometry_distance_and_extras():
    parsed = enrich_routes.parse_ors_route(_mock_ors_payload())

    assert parsed["miles"] == pytest.approx(296000.0 / 1609.344, abs=0.1)
    # coordinates are flattened to 2D [lon, lat] for the corridor samplers
    assert parsed["coordinates"] == [[-87.63, 41.88], [-86.90, 41.00], [-86.16, 39.77]]
    # elevation comes back per-vertex in feet (metres * 3.28084)
    assert parsed["elevations_ft"][0] == pytest.approx(180.0 * 3.28084, abs=0.1)
    assert max(parsed["elevations_ft"]) == pytest.approx(220.0 * 3.28084, abs=0.1)
    assert len(parsed["steepness"]) == 2
    assert parsed["has_tollway"] is True


def test_parse_ors_route_elevation_feeds_existing_grade_helper():
    """ORS elevation + the existing _sample_geometry/_grade_segments produce a
    valid corridor grade segment, proving the mapping is wiring-ready."""
    parsed = enrich_routes.parse_ors_route(_mock_ors_payload())
    leg = {"miles": parsed["miles"], "terrain": "flat", "from": "A", "to": "B"}
    samples = enrich_routes._sample_geometry(parsed["coordinates"], leg["miles"])
    # one elevation per sample, drawn from the route's elevation profile
    elevations = [parsed["elevations_ft"][0] for _ in samples]
    segments = enrich_routes._grade_segments(samples, elevations, leg)
    assert segments and segments[0]["end_mi"] == pytest.approx(leg["miles"])
    assert "terrain" in segments[0]


def test_ors_corridor_samples_carry_elevation():
    parsed = enrich_routes.parse_ors_route(_mock_ors_payload())
    samples, elevations = enrich_routes.ors_corridor_samples(
        parsed, parsed["miles"], sample_count=3)
    assert len(samples) == 3 == len(elevations)
    assert samples[0]["at_mi"] == 0.0
    assert samples[-1]["at_mi"] == pytest.approx(parsed["miles"])
    # endpoints map to the route's first and last elevations (metres -> feet)
    assert elevations[0] == pytest.approx(180.0 * 3.28084, abs=0.1)
    assert elevations[-1] == pytest.approx(220.0 * 3.28084, abs=0.1)


def test_has_tollway_false_when_no_toll_segments():
    payload = _mock_ors_payload()
    payload["features"][0]["properties"]["extras"]["tollways"]["values"] = [[0, 2, 0]]
    assert enrich_routes.parse_ors_route(payload)["has_tollway"] is False


def test_parse_ors_route_rejects_empty_response():
    with pytest.raises(RuntimeError):
        enrich_routes.parse_ors_route({"features": []})


def test_ors_api_key_reads_environment(monkeypatch):
    monkeypatch.delenv(enrich_routes.ORS_API_KEY_ENV, raising=False)
    assert enrich_routes.ors_api_key() is None
    monkeypatch.setenv(enrich_routes.ORS_API_KEY_ENV, "  test-key  ")
    assert enrich_routes.ors_api_key() == "test-key"


def test_ors_directions_kwargs_request_hgv_with_elevation_and_extras():
    kwargs = enrich_routes._ors_directions_kwargs(
        {"lon": -87.63, "lat": 41.88}, {"lon": -86.16, "lat": 39.77})
    assert kwargs["coordinates"] == [[-87.63, 41.88], [-86.16, 39.77]]
    assert kwargs["profile"] == "driving-hgv"
    assert kwargs["format"] == "geojson"
    assert kwargs["elevation"] is True
    assert "steepness" in kwargs["extra_info"]
    assert "tollways" in kwargs["extra_info"]
