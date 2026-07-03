"""Tests for the world-data baking used by frozen release builds."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import freight_fate.data as data_pkg
from freight_fate.data import world as world_module
from freight_fate.data.world_loader import load_world_data

ROOT = Path(__file__).resolve().parents[1]


def _load_bake_world():
    """Import tools/bake_world.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location("bake_world", ROOT / "tools" / "bake_world.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bw = _load_bake_world()


def _import_baked(path: Path):
    spec = importlib.util.spec_from_file_location("baked_world_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_baked_module(payload: dict) -> types.ModuleType:
    fake = types.ModuleType("freight_fate.data._baked_world")
    fake.load = lambda: payload
    return fake


def test_baked_module_round_trips_world_data(tmp_path):
    out = bw.bake(output=tmp_path / "_baked_world.py")
    baked = _import_baked(out)
    assert baked.load() == load_world_data(bw.WORLD_DATA_PATH)


def test_bake_is_deterministic(tmp_path):
    first = bw.bake(output=tmp_path / "a.py").read_text(encoding="utf-8")
    second = bw.bake(output=tmp_path / "b.py").read_text(encoding="utf-8")
    assert first == second


def test_default_root_prefers_baked_module(monkeypatch):
    sentinel = {"cities": {}, "legs": []}
    monkeypatch.setattr(data_pkg, "_baked_world", _fake_baked_module(sentinel), raising=False)
    assert world_module._load_base_world_data(world_module.WORLD_DATA_PATH) is sentinel


def test_explicit_root_reads_files_even_with_baked_module(monkeypatch, tmp_path):
    baked_payload = {"cities": {"Baked Only": {}}, "legs": []}
    monkeypatch.setattr(
        data_pkg, "_baked_world", _fake_baked_module(baked_payload), raising=False
    )
    root = tmp_path / "world_data"
    (root / "us").mkdir(parents=True)
    (root / "index.json").write_text(
        json.dumps({"countries": [{"code": "US", "path": "us"}]}), encoding="utf-8"
    )
    (root / "us" / "cities.json").write_text(
        json.dumps({"cities": {"Fileville": {"state": "Ohio"}}}), encoding="utf-8"
    )
    (root / "us" / "legs.json").write_text(json.dumps({"legs": []}), encoding="utf-8")

    data = world_module._load_base_world_data(root)
    assert "Fileville" in data["cities"]
    assert "Baked Only" not in data["cities"]


def test_source_checkout_falls_back_to_files():
    # The baked module never exists in a source checkout; the default root
    # must read the editable world_data/ tree.
    assert not (ROOT / "src" / "freight_fate" / "data" / "_baked_world.py").exists()
    data = world_module._load_base_world_data(world_module.WORLD_DATA_PATH)
    assert data["cities"]
