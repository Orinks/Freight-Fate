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
        "enrich_routes", ROOT / "tools" / "enrich_routes.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


enrich_routes = _load_enrich_routes()


def _mock_ors_payload():
    """A minimal driving-hgv GeoJSON response: 3D coords + steepness + tollways."""
    return {
        "features": [
            {
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
            }
        ]
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
        parsed, parsed["miles"], sample_count=3
    )
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


def test_grade_segments_from_samples_keeps_up_and_down_structure():
    at = [0.0, 20.0, 40.0, 60.0, 80.0]
    samples = [{"at_mi": m, "lat": 40.0, "lon": -100.0} for m in at]
    elevations = [1000.0, 6000.0, 6050.0, 1000.0, 1010.0]  # climb, flat, drop, flat
    leg = {"miles": 80.0, "terrain": "flat", "from": "A", "to": "B"}
    segs = enrich_routes.grade_segments_from_samples(samples, elevations, leg)
    assert len(segs) >= 3
    terrains = {s["terrain"] for s in segs}
    assert "mountain" in terrains and "flat" in terrains
    assert segs[0]["start_mi"] == 0.0 and segs[-1]["end_mi"] == 80.0
    for a, b in zip(segs, segs[1:], strict=False):  # contiguous coverage
        assert a["end_mi"] == b["start_mi"]
    assert all(-15.0 <= s["avg_grade_pct"] <= 15.0 for s in segs)


def test_grade_segments_from_samples_single_when_uniform():
    samples = [{"at_mi": m, "lat": 40.0, "lon": -100.0} for m in (0.0, 30.0, 60.0, 90.0)]
    elevations = [500.0, 505.0, 500.0, 505.0]  # all flat
    leg = {"miles": 90.0, "terrain": "flat", "from": "A", "to": "B"}
    segs = enrich_routes.grade_segments_from_samples(samples, elevations, leg)
    assert len(segs) == 1 and segs[0]["terrain"] == "flat"


def test_fine_grade_samples_matches_leg_miles_and_is_contiguous():
    # 5 evenly spaced vertices climbing steadily -- a sanity check that the
    # distance-walk sampler covers the whole leg with no gaps.
    parsed = {
        "coordinates": [[-110.0, 35.0 + 0.05 * i] for i in range(5)],
        "elevations_ft": [1000.0, 1500.0, 2000.0, 2500.0, 3000.0],
    }
    leg_miles = 20.0
    samples, elevations = enrich_routes.fine_grade_samples(parsed, leg_miles, bin_width_mi=1.0)
    assert samples[0]["at_mi"] == 0.0
    assert samples[-1]["at_mi"] == leg_miles
    assert len(samples) == len(elevations)
    assert all(a["at_mi"] <= b["at_mi"] for a, b in zip(samples, samples[1:], strict=False))


def test_fine_grade_samples_avoids_the_sparse_vertex_snap_artifact():
    """A long, flat, sparsely-vertexed stretch followed by a short, densely
    vertexed real climb must not produce a spurious grade spike.

    ors_corridor_samples at a high sample_count can snap several evenly
    *target*-spaced mileposts onto the same vertex once a stretch has fewer
    real vertices than requested samples, then show a huge jump once the
    scan reaches the next real vertex. fine_grade_samples walks the real
    polyline forward instead, so it must not reproduce that artifact.
    """
    # A -> B: one huge flat segment (only two vertices, ~97 mi, no gain).
    # B -> C -> D -> E -> F: a short, real ~7.4% climb over the last ~5 mi,
    # with vertices packed close together (the realistic shape for a real
    # pass -- OSM/ORS shape points get denser where the road curves).
    coords = [
        [-114.0, 35.0],  # A
        [-112.5, 35.2],  # B (~97 mi later, flat)
        [-112.48, 35.201],
        [-112.46, 35.202],
        [-112.44, 35.203],
        [-112.42, 35.204],  # F (climbing +2000 ft from B)
    ]
    elevations = [3000.0, 3000.0, 3500.0, 4000.0, 4500.0, 5000.0]
    parsed = {"coordinates": coords, "elevations_ft": elevations}

    samples, sample_elevations = enrich_routes.fine_grade_samples(
        parsed, leg_miles=102.0, bin_width_mi=0.25
    )
    leg = {"miles": 102.0, "terrain": "flat", "from": "a", "to": "f"}
    segs = enrich_routes.grade_segments_from_samples(samples, sample_elevations, leg)

    # The flat 100-mile stretch must not read as a spike -- every segment
    # must stay within a physically plausible bound for a real highway.
    assert all(abs(s["avg_grade_pct"]) <= 10.0 for s in segs)
    # The real climb must still show up as mountain-classified.
    assert any(s["terrain"] == "mountain" and s["avg_grade_pct"] > 3.0 for s in segs)


def test_fine_grade_samples_never_yields_a_zero_width_final_segment():
    """Regression: when the last real ORS vertex sits a hair's-breadth past
    the previous sample, the forced final close used to append a near-
    duplicate point. A stored grade segment rounds its endpoints to 1
    decimal place, so that tiny gap could round away to start_mi == end_mi
    -- exactly what world.py's parser rejects (observed live on a real
    Flagstaff -> Kingman route: a 151.0-151.0 segment). Needs at least 3
    real samples before the tiny final gap so the fix exercises the same
    merge/round path the real bug hit -- 2 samples fall back to the
    unrounded single-segment builder and would hide the bug."""
    coords = [
        [-110.0, 35.0],
        [-109.5, 35.0],  # ~28.7 mi later
        [-109.0, 35.0],  # ~57.4 mi later
        [-108.999, 35.0],  # ~0.06 mi further -- under the merge-safe gap
    ]
    elevations = [1000.0, 1000.0, 1000.0, 1200.0]
    parsed = {"coordinates": coords, "elevations_ft": elevations}
    samples, sample_elevations = enrich_routes.fine_grade_samples(parsed, leg_miles=57.46)
    assert len(samples) >= 3, "test setup must exercise the merge path, not the fallback"
    leg = {"miles": 57.46, "terrain": "flat", "from": "a", "to": "b"}
    segs = enrich_routes.grade_segments_from_samples(samples, sample_elevations, leg)

    assert all(s["end_mi"] > s["start_mi"] for s in segs)
    assert segs[0]["start_mi"] == 0.0
    assert segs[-1]["end_mi"] == 57.5  # world.py rounds leg.miles the same way


def test_ors_sample_count_scales_with_distance():
    assert enrich_routes._ors_sample_count(40) == 5  # short legs get a floor
    assert enrich_routes._ors_sample_count(490) == 18  # ~1 per 30 mi
    assert enrich_routes._ors_sample_count(2000) == 25  # capped


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
        {"lon": -87.63, "lat": 41.88}, {"lon": -86.16, "lat": 39.77}
    )
    assert kwargs["coordinates"] == [[-87.63, 41.88], [-86.16, 39.77]]
    assert kwargs["profile"] == "driving-hgv"
    assert kwargs["format"] == "geojson"
    assert kwargs["elevation"] is True
    assert "steepness" in kwargs["extra_info"]
    assert "tollways" in kwargs["extra_info"]
