"""Corridor place generator: pure matching/thinning logic (no network).

tools/corridor_places.py lists real GeoNames places along a leg's route --
the candidate engine for both checkpoint enrichment and interstate spidering.
These pin the geometry match, the buffer, the node dedupe, and the cluster
thinning; the GeoNames download and ORS fetch are exercised live, not here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cp = _load("corridor_places")

# South-to-north line at lon -110, 35.0..36.0 lat (~69 mi), 101 vertices.
LINE = [[-110.0, 35.0 + i * 0.01] for i in range(101)]
LINE_MILES = 69.1


def _place(name, lat, lon, pop):
    return {"name": name, "state": "Nevada", "lat": lat, "lon": lon, "population": pop}


def test_lists_on_route_places_ordered_by_mile():
    places = [
        _place("North Town", 35.9, -110.005, 5000),
        _place("South Town", 35.1, -110.005, 5000),
        _place("Mid Town", 35.5, -110.005, 5000),
    ]
    out = cp.corridor_candidates(
        LINE, LINE_MILES, LINE_MILES, places, [],
        buffer_mi=2.0, dedupe_mi=6.0, min_pop=0, min_spacing_mi=8.0,
    )
    assert [p["name"] for p in out] == ["South Town", "Mid Town", "North Town"]
    assert all(p["off_mi"] < 0.5 for p in out)  # ~0.005deg lon off the line


def test_off_route_place_is_excluded_by_buffer():
    places = [_place("Far Town", 35.5, -110.5, 9000)]  # ~28 mi off
    out = cp.corridor_candidates(
        LINE, LINE_MILES, LINE_MILES, places, [],
        buffer_mi=2.0, dedupe_mi=6.0, min_pop=0, min_spacing_mi=8.0,
    )
    assert out == []


def test_existing_node_is_deduped_out():
    places = [_place("Is A Node", 35.5, -110.005, 20000)]
    out = cp.corridor_candidates(
        LINE, LINE_MILES, LINE_MILES, places, [(35.5, -110.0)],  # a node right there
        buffer_mi=2.0, dedupe_mi=6.0, min_pop=0, min_spacing_mi=8.0,
    )
    assert out == []


def test_cluster_thins_to_largest_within_spacing():
    # Three hamlets within a few miles; only the biggest should survive.
    places = [
        _place("Tiny", 35.50, -110.004, 150),
        _place("Big", 35.51, -110.004, 4000),
        _place("Small", 35.52, -110.004, 600),
    ]
    out = cp.corridor_candidates(
        LINE, LINE_MILES, LINE_MILES, places, [],
        buffer_mi=2.0, dedupe_mi=6.0, min_pop=0, min_spacing_mi=8.0,
    )
    assert [p["name"] for p in out] == ["Big"]


def test_min_pop_floor_filters_small_places():
    places = [
        _place("Hamlet", 35.3, -110.004, 200),
        _place("City", 35.7, -110.004, 9000),
    ]
    out = cp.corridor_candidates(
        LINE, LINE_MILES, LINE_MILES, places, [],
        buffer_mi=2.0, dedupe_mi=6.0, min_pop=3000, min_spacing_mi=8.0,
    )
    assert [p["name"] for p in out] == ["City"]


def test_positions_rescale_to_adopted_leg_miles():
    places = [_place("Mid", 35.5, -110.004, 5000)]
    out = cp.corridor_candidates(
        LINE, LINE_MILES, 100.0, places, [],  # leg curated to 100 mi
        buffer_mi=2.0, dedupe_mi=6.0, min_pop=0, min_spacing_mi=8.0,
    )
    assert out[0]["at_mi"] == 50.0  # halfway up the line, on the 100-mi scale
