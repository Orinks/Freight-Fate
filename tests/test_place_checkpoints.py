"""Checkpoint placement tool: pure geometry and merge logic (no network).

``tools/place_checkpoints.py`` is the mechanical core of the map-enrichment
recipe (docs/map-enrichment-recipe.md): candidate towns are position-matched
to the leg's real route polyline, rejected when they sit too far off the
route, and merged into the leg's checkpoints with the synthetic placeholder
dropped once a real named place covers the leg.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


place_checkpoints = _load("place_checkpoints")

# A straight south-to-north polyline at lon -110: 1 degree of latitude,
# about 69.1 miles, 11 evenly spaced vertices.
LINE = [[-110.0, 35.0 + i * 0.1] for i in range(11)]
LINE_MILES = 69.1


def test_position_on_route_matches_midpoint_town():
    at_mi, off_mi = place_checkpoints.position_on_route(
        LINE, LINE_MILES, LINE_MILES, lat=35.5, lon=-110.01
    )
    assert at_mi == pytest.approx(34.5, abs=0.5)  # halfway up the line
    assert off_mi == pytest.approx(0.56, abs=0.1)  # ~0.01 deg lon at lat 35.5


def test_position_on_route_rescales_to_adopted_leg_miles():
    # Curated leg mileage differs from the raw polyline length; positions
    # must land on the leg's own mile scale (it drives cues and HOS).
    at_mi, _ = place_checkpoints.position_on_route(LINE, LINE_MILES, 100.0, lat=35.5, lon=-110.0)
    assert at_mi == pytest.approx(50.0, abs=0.5)


def test_position_on_route_flags_far_off_route_towns():
    _, off_mi = place_checkpoints.position_on_route(
        LINE, LINE_MILES, LINE_MILES, lat=35.5, lon=-110.5
    )
    assert off_mi > place_checkpoints.MAX_OFF_ROUTE_MI  # ~28 mi: wrong town


def test_merge_drops_placeholder_once_real_checkpoint_exists():
    existing = [
        {"name": "I-40 corridor between Flagstaff and Kingman", "at_mi": 75.5},
        {"name": "Seligman", "at_mi": 77.5},
    ]
    accepted = [{"name": "Williams", "at_mi": 32.0}]
    merged = place_checkpoints.merge_checkpoints(existing, accepted)
    assert [c["name"] for c in merged] == ["Williams", "Seligman"]  # sorted, no placeholder


def test_merge_keeps_placeholder_when_no_real_checkpoint():
    existing = [{"name": "I-40 corridor between Flagstaff and Kingman", "at_mi": 75.5}]
    merged = place_checkpoints.merge_checkpoints(existing, [])
    assert [c["name"] for c in merged] == ["I-40 corridor between Flagstaff and Kingman"]


def test_merge_dedupes_by_name():
    existing = [{"name": "Seligman", "at_mi": 77.5}]
    accepted = [{"name": "Seligman", "at_mi": 77.0}, {"name": "Ash Fork", "at_mi": 52.0}]
    merged = place_checkpoints.merge_checkpoints(existing, accepted)
    assert [c["name"] for c in merged] == ["Ash Fork", "Seligman"]
    assert merged[1]["at_mi"] == 77.5  # the existing curated position wins
