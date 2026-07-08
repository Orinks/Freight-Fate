"""map_stats counts real checkpoints vs placeholders and coordinate coverage."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


map_stats = _load("map_stats")


def test_counts_reals_placeholders_stops_and_coordinates():
    data = {
        "cities": {
            "a_ok_us": {"region": "plains"},
            "b_tx_us": {"region": "plains"},
            "c_nm_us": {"region": "desert_southwest"},
        },
        "legs": [
            {
                "from": "a_ok_us",
                "to": "b_tx_us",
                "miles": 200,
                "corridor": {
                    "checkpoints": [
                        {"name": "Real Town"},
                        {"name": "I-40 corridor between a and b"},
                    ]
                },
                "stops": [
                    {"name": "Loves", "lat": 35.1, "lon": -99.0},
                    {"name": "Pilot"},  # no coordinate
                ],
            },
            {
                "from": "b_tx_us",
                "to": "c_nm_us",
                "miles": 300,
                "corridor": {"checkpoints": [{"name": "I-10 corridor between b and c"}]},
            },
        ],
    }
    s = map_stats.compute_stats(data)
    assert s["cities"] == 3
    assert s["legs"] == 2
    assert s["total_miles"] == 500
    assert s["real_checkpoints"] == 1
    assert s["placeholder_checkpoints"] == 2
    assert s["truck_stops"] == 2
    assert s["truck_stops_with_coordinate"] == 1
    assert s["legs_with_real_checkpoints"] == 1
    assert s["legs_placeholder_only"] == 1
    assert s["cities_by_region"] == {"plains": 2, "desert_southwest": 1}
