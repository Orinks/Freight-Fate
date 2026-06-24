"""Development-time interchange builder tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
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


def test_build_local_index_prefilters_streamed_features(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[dict[str, Any]] = []

    class FakeLocation:
        def __init__(self, lat: float, lon: float) -> None:
            self.lat = lat
            self.lon = lon

        def valid(self) -> bool:
            return True

    class FakeNode:
        def __init__(
            self,
            node_id: int,
            lat: float,
            lon: float,
            tags: dict[str, str],
        ) -> None:
            self.id = node_id
            self.location = FakeLocation(lat, lon)
            self.tags = list(tags.items())

    class FakeWay:
        def __init__(
            self,
            node_ids: list[int],
            tags: dict[str, str],
        ) -> None:
            self.nodes = [SimpleNamespace(ref=node_id) for node_id in node_ids]
            self.tags = list(tags.items())

    class FakeSimpleHandler:
        def __init__(self) -> None:
            pass

        def apply_file(
            self,
            filename: str,
            filters: list[Any] | None = None,
        ) -> None:
            calls.append({
                "filename": filename,
                "handler": type(self).__name__,
                "filters": len(filters or []),
            })
            if hasattr(self, "node"):
                self.node(FakeNode(
                    1,
                    40.0500,
                    -75.0000,
                    {"highway": "motorway_junction", "ref": "27"},
                ))
                self.node(FakeNode(
                    2,
                    41.0000,
                    -75.0000,
                    {"highway": "motorway_junction", "ref": "99"},
                ))
                self.node(FakeNode(10, 40.0500, -75.0000, {}))
                self.node(FakeNode(11, 40.0502, -75.0001, {}))
                self.node(FakeNode(20, 41.0000, -75.0000, {}))
                self.node(FakeNode(21, 41.0002, -75.0001, {}))
            if hasattr(self, "way"):
                self.way(FakeWay(
                    [10, 11],
                    {"highway": "motorway_link", "destination": "Trenton"},
                ))
                self.way(FakeWay(
                    [20, 21],
                    {"highway": "motorway_link", "destination": "Wrong Road"},
                ))

    fake_filter = SimpleNamespace(
        TagFilter=lambda *_args: "tag-filter",
        IdFilter=lambda *_args: "id-filter",
    )
    fake_osmium = SimpleNamespace(SimpleHandler=FakeSimpleHandler, filter=fake_filter)
    monkeypatch.setitem(sys.modules, "osmium", fake_osmium)
    bounds = build_interchanges._route_corridor_bounds([
        {"lat": 40.0000, "lon": -75.0000},
        {"lat": 40.1000, "lon": -75.0000},
    ])

    index = build_interchanges.build_local_index(
        Path("fake.osm.pbf"),
        bounds,
        progress_interval_sec=0,
    )

    assert calls == [
        {"filename": "fake.osm.pbf", "handler": "InterchangeHandler", "filters": 1},
        {"filename": "fake.osm.pbf", "handler": "RampNodeHandler", "filters": 1},
    ]
    assert [feature.tags["ref"] for feature in index.junctions] == ["27"]
    assert [feature.tags["destination"] for feature in index.ramps] == ["Trenton"]


def test_local_index_cache_round_trips(tmp_path: Path):
    pbf = tmp_path / "tiny.osm.pbf"
    pbf.write_bytes(b"pbf")
    cache = tmp_path / "tiny.interchanges.json"
    bounds = [(39.9, 40.2, -75.1, -74.9)]
    index = build_interchanges.LocalOsmIndex(
        junctions=[
            build_interchanges.LocalOsmFeature(
                40.0,
                -75.0,
                {"highway": "motorway_junction", "ref": "27"},
            )
        ],
        ramps=[
            build_interchanges.LocalOsmFeature(
                40.01,
                -75.0,
                {"highway": "motorway_link", "destination": "Trenton"},
            )
        ],
    )

    build_interchanges._write_local_index_cache(cache, index, [pbf], bounds)
    loaded = build_interchanges._read_local_index_cache(cache, [pbf], bounds)

    assert loaded == index
    assert build_interchanges._read_local_index_cache(
        cache, [pbf], [(41.0, 41.1, -75.1, -74.9)]
    ) is None


def test_load_or_build_local_index_uses_valid_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pbf = tmp_path / "tiny.osm.pbf"
    pbf.write_bytes(b"pbf")
    cache = tmp_path / "tiny.interchanges.json"
    bounds = [(39.9, 40.2, -75.1, -74.9)]
    index = build_interchanges.LocalOsmIndex(
        junctions=[],
        ramps=[
            build_interchanges.LocalOsmFeature(
                40.01,
                -75.0,
                {"highway": "motorway_link", "destination": "Trenton"},
            )
        ],
    )
    build_interchanges._write_local_index_cache(cache, index, [pbf], bounds)

    def fail_build(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("cache hit should not rescan the PBF")

    monkeypatch.setattr(build_interchanges, "build_local_index", fail_build)

    assert build_interchanges.load_or_build_local_index([pbf], bounds, cache) == index


def test_load_local_index_cache_only_does_not_need_pbf(
    tmp_path: Path,
):
    pbf = tmp_path / "tiny.osm.pbf"
    pbf.write_bytes(b"pbf")
    cache = tmp_path / "tiny.interchanges.json"
    bounds = [(39.9, 40.2, -75.1, -74.9)]
    index = build_interchanges.LocalOsmIndex(
        junctions=[
            build_interchanges.LocalOsmFeature(
                40.0,
                -75.0,
                {"highway": "motorway_junction", "ref": "27"},
            )
        ],
        ramps=[],
    )
    build_interchanges._write_local_index_cache(cache, index, [pbf], bounds)
    pbf.unlink()

    assert build_interchanges.load_local_index_cache_only(cache, bounds) == index
