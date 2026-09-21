"""Tests for tools/ntad.py: the keyless NTAD snapshot loader.

Nothing here touches the network. The fetch seam is an ``opener`` callable,
so the three things that can go wrong offline -- a layer that needs paging, a
refresh with the network down, and a first run with neither cache nor network
-- are all provoked without BTS being involved.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_tool():
    """Import tools/ntad.py by path (tools is not a package)."""
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location("ntad", ROOT / "tools" / "ntad.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ntad = _load_tool()


def _feature(object_id: int) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-93.29, 44.0]},
        "properties": {"OBJECTID": object_id, "state": "Minnesota", "number_of_spots": 40},
    }


class _Opener:
    """A fake ArcGIS that serves fixed pages and counts the calls."""

    def __init__(self, pages: list[dict]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def __call__(self, url: str) -> dict:
        self.calls.append(url)
        return self.pages[len(self.calls) - 1]


def test_fetch_pages_on_length_not_on_the_arcgis_flag(monkeypatch) -> None:
    """The real layers serve GeoJSON, which carries no `exceededTransferLimit`.

    Paging off that flag read the first 1,000 of 1,915 truck parking records
    and called it a complete survey. A full page has to keep the fetch going on
    its own.
    """
    monkeypatch.setattr(ntad, "PAGE_SIZE", 2)
    opener = _Opener(
        [
            {"features": [_feature(1), _feature(2)]},
            {"features": [_feature(3)]},
        ]
    )

    payload = ntad.fetch("truck_parking", opener=opener)

    assert len(payload["features"]) == 3
    assert len(opener.calls) == 2
    # The second page has to start after the first, or the fetch loops on the
    # same records forever.
    assert "resultOffset=2" in opener.calls[1]

    source = payload["ff_source"]
    assert source["kind"] == "read"
    assert source["features"] == 3
    assert "17 U.S.C." in source["license"]
    assert "Federal Highway Administration" in source["acknowledgment"]


def test_fetch_stops_on_an_exactly_full_last_page(monkeypatch) -> None:
    """A layer whose size is a multiple of the page size still terminates."""
    monkeypatch.setattr(ntad, "PAGE_SIZE", 2)
    opener = _Opener([{"features": [_feature(1), _feature(2)]}, {"features": []}])

    payload = ntad.fetch("truck_parking", opener=opener)

    assert len(payload["features"]) == 2
    assert len(opener.calls) == 2


def test_load_writes_a_snapshot_then_reads_it_without_the_network(tmp_path: Path) -> None:
    opener = _Opener([{"features": [_feature(1)], "exceededTransferLimit": False}])

    first = ntad.load("truck_parking", cache_dir=tmp_path, opener=opener)
    assert len(opener.calls) == 1
    assert ntad.snapshot_path("truck_parking", tmp_path).exists()

    def _no_network(url: str) -> dict:
        raise AssertionError("cached load must not reach the network")

    second = ntad.load("truck_parking", cache_dir=tmp_path, opener=_no_network)
    assert second == first


def test_a_failed_refresh_keeps_serving_the_snapshot(tmp_path: Path, capsys) -> None:
    path = ntad.snapshot_path("truck_parking", tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "ff_source": {"accessed": "2026-07-17"},
                "features": [_feature(9)],
            }
        ),
        encoding="utf-8",
    )

    def _offline(url: str) -> dict:
        raise OSError("no route to host")

    payload = ntad.load("truck_parking", refresh=True, cache_dir=tmp_path, opener=_offline)

    assert [f["properties"]["OBJECTID"] for f in payload["features"]] == [9]
    assert "2026-07-17" in capsys.readouterr().err


def test_a_first_run_with_no_cache_and_no_network_raises(tmp_path: Path) -> None:
    def _offline(url: str) -> dict:
        raise OSError("no route to host")

    with pytest.raises(OSError):
        ntad.load("truck_parking", cache_dir=tmp_path, opener=_offline)


def test_an_unknown_layer_names_the_ones_that_exist() -> None:
    with pytest.raises(ValueError, match="truck_parking"):
        ntad.fetch("moon_bases", opener=_Opener([]))
