"""Additive world overlay loader (Workstream D foundation).

The overlay lets online-fetched cities and legs be cached and merged on top of
the checked-in base for later offline play, without ever overriding the base or
changing the offline/deterministic path when no overlay is present.
"""

from __future__ import annotations

import json
from pathlib import Path

from freight_fate.data.world import World


def _helena_city() -> dict:
    return {
        "state": "Montana",
        "region": "rockies",
        "lat": 46.5891,
        "lon": -112.0391,
        "locations": [{"name": "Helena Freight Terminal", "type": "terminal"}],
    }


def test_load_without_overlay_matches_base():
    base = World.load()
    missing = World.load(overlay=Path("definitely-not-a-real-overlay.json"))
    assert set(missing.cities) == set(base.cities)
    assert len(missing.legs) == len(base.legs)


def test_overlay_adds_new_city_and_leg(tmp_path):
    base = World.load()
    assert "Helena" not in base.cities
    overlay = {
        "cities": {"Helena": _helena_city()},
        "legs": [
            {
                "from": "Helena",
                "to": "Salt Lake City",
                "miles": 480,
                "highway": "I-15",
                "terrain": "mountain",
            }
        ],
    }
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(overlay), encoding="utf-8")

    world = World.load(overlay=path)
    assert "Helena" in world.cities
    assert len(world.cities) == len(base.cities) + 1
    assert len(world.legs) == len(base.legs) + 1
    # the new city is wired into the routable network
    assert world.neighbors("Helena")
    assert world.shortest_route("Helena", "Salt Lake City") is not None


def test_overlay_cannot_override_base_city(tmp_path):
    base = World.load()
    overlay = {
        "cities": {
            "Chicago": {
                "state": "Nowhere",
                "region": "rockies",
                "lat": 0.0,
                "lon": 0.0,
                "locations": [{"name": "Bogus Yard", "type": "terminal"}],
            }
        },
        "legs": [],
    }
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(overlay), encoding="utf-8")

    world = World.load(overlay=path)
    # base Chicago wins; the overlay's bogus definition is ignored
    assert world.cities["Chicago"].state == base.cities["Chicago"].state


def test_overlay_does_not_duplicate_an_existing_leg(tmp_path):
    base = World.load()
    leg = base.legs[0]
    # re-add the same leg with endpoints reversed; it must not be duplicated
    overlay = {
        "cities": {},
        "legs": [
            {
                "from": leg.b,
                "to": leg.a,
                "miles": leg.miles,
                "highway": leg.highway,
                "terrain": leg.terrain,
            }
        ],
    }
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(overlay), encoding="utf-8")

    world = World.load(overlay=path)
    assert len(world.legs) == len(base.legs)
