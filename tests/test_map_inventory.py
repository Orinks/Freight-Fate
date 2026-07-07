"""map_inventory lists cities by region and real checkpoints by leg."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


map_inventory = _load("map_inventory")


def test_inventory_lists_cities_and_real_checkpoints_only():
    data = {
        "cities": {
            "atlanta_ga_us": {"spoken_city": "Atlanta", "state": "GA", "region": "atlantic_southeast"},
            "dallas_tx_us": {"spoken_city": "Dallas", "state": "TX", "region": "southern_plains"},
        },
        "legs": [
            {
                "from": "atlanta_ga_us",
                "to": "dallas_tx_us",
                "highway": "I-20",
                "corridor": {
                    "checkpoints": [
                        {"name": "Real Town", "state": "Alabama", "at_mi": 120.0},
                        {"name": "I-20 corridor between atlanta and dallas", "at_mi": 60.0},
                    ]
                },
            }
        ],
    }
    text = map_inventory.build_inventory(data)

    # full state names expanded from postal codes
    assert "Atlanta, Georgia" in text
    assert "Dallas, Texas" in text
    # region headers are prettified
    assert "Atlantic Southeast (1):" in text
    # real checkpoint shown with mile marker + full state, endpoints readable
    assert "Atlanta -> Dallas (I-20)" in text
    assert "at 120 mi: Real Town (Alabama)" in text
    # placeholder checkpoint excluded
    assert "corridor between" not in text
    # counts in the header
    assert "Cities (freight nodes): 2" in text
    assert "Real named checkpoints: 1" in text
