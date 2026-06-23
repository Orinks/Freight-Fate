"""Development-time interchange builder tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_build_interchanges():
    """Import tools/build_interchanges.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "build_interchanges", ROOT / "tools" / "build_interchanges.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_interchanges = _load_build_interchanges()


def _geom() -> list[tuple[float, float, float]]:
    return [
        (40.0000, -75.0000, 0.0),
        (40.0500, -75.0000, 5.0),
        (40.1000, -75.0000, 10.0),
    ]


def test_local_pbf_discovery_reuses_existing_assembly(monkeypatch: pytest.MonkeyPatch):
    def fail_overpass(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("local PBF mode must not call Overpass")

    monkeypatch.setattr(build_interchanges, "_osrm_geometry", lambda *_args: _geom())
    monkeypatch.setattr(build_interchanges, "_post_overpass", fail_overpass)

    index = build_interchanges.LocalOsmIndex(
        junctions=[
            build_interchanges.LocalOsmFeature(
                40.0500, -75.0000,
                {"highway": "motorway_junction", "ref": "27", "name": "Market Street"},
            ),
            # Same exit on the opposite carriageway; should group by ref.
            build_interchanges.LocalOsmFeature(
                40.0502, -75.0001,
                {"highway": "motorway_junction", "ref": "27"},
            ),
            # Close enough for the bounding box but too far from the route line.
            build_interchanges.LocalOsmFeature(
                40.0500, -74.9900,
                {"highway": "motorway_junction", "ref": "99"},
            ),
        ],
        ramps=[
            build_interchanges.LocalOsmFeature(
                40.0501, -75.0001,
                {
                    "highway": "motorway_link",
                    "destination": "Trenton;node/123;Cars Only;New York",
                    "destination:ref": "US 1",
                },
            ),
        ],
    )
    leg = {
        "from": "A",
        "to": "B",
        "highway": "I-95",
        "miles": 10.0,
        "corridor": {"route_points": [{"lat": 40.0, "lon": -75.0}]},
    }

    found = build_interchanges.discover_leg(leg, rate_limit=0, local_index=index)

    assert found == [{
        "at_mi": 5.0,
        "exit_ref": "27",
        "name": "Market Street",
        "destinations": ["Trenton", "New York"],
        "via": "US 1",
        "highway": "I-95",
        "source": (
            "OpenStreetMap highway=motorway_junction exit ref and "
            "destination sign tags on the leg's Interstate shield, snapped "
            "to checked-in OSRM route geometry, accessed 2026-06-23: "
            "https://www.openstreetmap.org/"
        ),
    }]


def test_local_candidates_keep_only_route_adjacent_features():
    index = build_interchanges.LocalOsmIndex(
        junctions=[
            build_interchanges.LocalOsmFeature(
                40.0500, -75.0000,
                {"highway": "motorway_junction", "ref": "27"},
            ),
            build_interchanges.LocalOsmFeature(
                40.0500, -74.9900,
                {"highway": "motorway_junction", "ref": "99"},
            ),
        ],
        ramps=[
            build_interchanges.LocalOsmFeature(
                40.0501, -75.0001,
                {"highway": "motorway_link", "destination": "Trenton"},
            ),
            build_interchanges.LocalOsmFeature(
                40.0500, -74.9900,
                {"highway": "motorway_link", "destination": "Wrong Road"},
            ),
        ],
    )

    junctions, ramps = build_interchanges._local_candidates(index, _geom(), 10.0)

    assert [item["ref"] for item in junctions.values()] == ["27"]
    assert [ramp["destinations"] for ramp in ramps] == [["Trenton"]]
