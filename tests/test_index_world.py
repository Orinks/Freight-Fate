"""Tests for the world.json -> world_data/ indexer."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_index_world():
    """Import tools/index_world.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location("index_world", ROOT / "tools" / "index_world.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


iw = _load_index_world()

_US_INDEX = {
    "countries": [{"code": "US", "path": "us", "cities": "cities.json", "legs": "legs.json"}]
}


def _text_for(files: dict[Path, str], suffix: str) -> str:
    matches = [text for path, text in files.items() if path.as_posix().endswith(suffix)]
    assert len(matches) == 1, f"expected one {suffix}, got {len(matches)}"
    return matches[0]


def test_split_places_cities_legs_and_route_stop_data():
    data = {
        "cities": {"A": {"state": "New York"}},
        "legs": [{"from": "A", "to": "A", "miles": 1}],
        "route_stop_data": {"schema": 1},
    }
    files = iw.build_country_files(data, _US_INDEX)
    assert json.loads(_text_for(files, "us/cities.json")) == {
        "cities": {"A": {"state": "New York"}}
    }
    assert json.loads(_text_for(files, "us/legs.json")) == {
        "legs": [{"from": "A", "to": "A", "miles": 1}]
    }
    assert json.loads(_text_for(files, "us/metadata.json"))["route_stop_data"] == {"schema": 1}
    # Trailing newline so the files match the repo's json.dumps(...)+"\n" style.
    assert _text_for(files, "us/legs.json").endswith("}\n")


def test_multi_country_requires_country_field():
    data = {"cities": {"A": {"state": "X"}}, "legs": []}
    index = {
        "countries": [
            {"code": "US", "path": "us"},
            {"code": "GB", "path": "gb"},
        ]
    }
    with pytest.raises(SystemExit):
        iw.build_country_files(data, index)


def test_cross_country_leg_is_rejected():
    data = {
        "cities": {"A": {"country": "US"}, "B": {"country": "GB"}},
        "legs": [{"from": "A", "to": "B"}],
    }
    index = {
        "countries": [
            {"code": "US", "path": "us"},
            {"code": "GB", "path": "gb"},
        ]
    }
    with pytest.raises(SystemExit):
        iw.build_country_files(data, index)


def test_checked_in_world_data_matches_world_json():
    """CI guard: the committed world_data/ must equal what the indexer would
    produce from world.json, so the two never drift (run
    `uv run python tools/index_world.py` if this fails)."""
    data = json.loads(iw.WORLD_PATH.read_text(encoding="utf-8"))
    index = json.loads((iw.WORLD_DATA_PATH / "index.json").read_text(encoding="utf-8"))
    for path, text in iw.build_country_files(data, index).items():
        assert path.exists(), f"{path} missing; run tools/index_world.py"
        assert path.read_text(encoding="utf-8") == text, (
            f"{path.relative_to(ROOT)} out of sync with world.json; "
            "run `uv run python tools/index_world.py`"
        )
