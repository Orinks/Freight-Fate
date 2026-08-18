"""The map-pack builder: manifests, diffs, determinism, verification."""

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_map_pack as bmp  # noqa: E402


def _fake_data(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    (data / "world_data" / "us" / "legs").mkdir(parents=True)
    (data / "world_data" / "index.json").write_text('{"version": 1}')
    (data / "world_data" / "us" / "legs" / "TX.json").write_text('{"legs": []}')
    (data / "world_data" / "us" / "legs" / "AZ.json").write_text('{"legs": [1]}')
    (data / "radio_catalog.json").write_text('{"stations": []}')
    return data


def _build(data: Path, out: Path, version: str, previous: Path | None = None) -> dict:
    argv = [
        "--pack",
        "north-america",
        "--version",
        version,
        "--created",
        "2026-07-29",
        "--data-dir",
        str(data),
        "--out",
        str(out),
    ]
    if previous is not None:
        argv += ["--previous", str(previous)]
    assert bmp.main(argv) == 0
    return json.loads((out / bmp.MANIFEST_NAME).read_text())


def test_full_pack_carries_everything_and_verifies(tmp_path, capsys):
    data = _fake_data(tmp_path)
    manifest = _build(data, tmp_path / "out", "2026.07")
    assert manifest["file_count"] == 4
    assert manifest["payload"]["carries"] == 4
    assert manifest["min_game_version"] == bmp.MIN_GAME_VERSION
    with zipfile.ZipFile(tmp_path / "out" / manifest["payload"]["zip"]) as zf:
        assert "radio_catalog.json" in zf.namelist()
        assert "world_data/us/legs/TX.json" in zf.namelist()
    assert (
        bmp.main(["--verify", str(tmp_path / "out" / bmp.MANIFEST_NAME), "--data-dir", str(data)])
        == 0
    )


def test_diff_pack_carries_only_changes_and_lists_removed(tmp_path):
    data = _fake_data(tmp_path)
    _build(data, tmp_path / "v1", "2026.07")
    # One shard edited, one removed, radio healed.
    (data / "world_data" / "us" / "legs" / "TX.json").write_text('{"legs": [9]}')
    (data / "world_data" / "us" / "legs" / "AZ.json").unlink()
    (data / "radio_catalog.json").write_text('{"stations": ["fixed"]}')
    manifest = _build(
        data, tmp_path / "v2", "2026.08", previous=tmp_path / "v1" / bmp.MANIFEST_NAME
    )
    assert manifest["payload"]["carries"] == 2  # TX shard + radio only
    assert manifest["payload"]["removed"] == ["world_data/us/legs/AZ.json"]
    with zipfile.ZipFile(tmp_path / "v2" / manifest["payload"]["zip"]) as zf:
        assert sorted(zf.namelist()) == ["radio_catalog.json", "world_data/us/legs/TX.json"]


def test_same_inputs_build_byte_identical_packs(tmp_path):
    data = _fake_data(tmp_path)
    m1 = _build(data, tmp_path / "a", "2026.07")
    m2 = _build(data, tmp_path / "b", "2026.07")
    z1 = (tmp_path / "a" / m1["payload"]["zip"]).read_bytes()
    z2 = (tmp_path / "b" / m2["payload"]["zip"]).read_bytes()
    assert z1 == z2  # determinism: same bake, same bytes, same publish
    assert m1["payload"]["zip_sha256"] == m2["payload"]["zip_sha256"]


def test_verify_catches_drift(tmp_path, capsys):
    data = _fake_data(tmp_path)
    _build(data, tmp_path / "out", "2026.07")
    (data / "world_data" / "us" / "legs" / "TX.json").write_text('{"legs": [666]}')
    assert (
        bmp.main(["--verify", str(tmp_path / "out" / bmp.MANIFEST_NAME), "--data-dir", str(data)])
        == 1
    )
    assert "CHANGED" in capsys.readouterr().out
