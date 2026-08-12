"""Version metadata should stay in sync with player-facing text."""

import json
from pathlib import Path

import tomllib

import freight_fate


def test_package_version_matches_pyproject():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert freight_fate.__version__ == data["project"]["version"]


def test_dev_checkout_has_no_baked_version():
    # A source checkout's sys.executable is the Python interpreter, which has
    # no build_info.json beside it -- __version__ must keep coming from the
    # importlib.metadata/pyproject.toml fallback, not a stray baked file.
    assert freight_fate._baked_version() is None


def test_baked_version_read_from_build_info_beside_the_executable(monkeypatch, tmp_path):
    exe = tmp_path / "FreightFate.exe"
    exe.write_bytes(b"")
    (tmp_path / "build_info.json").write_text(
        json.dumps({"tag": "v1.9.0", "channel": "stable", "package_version": "1.9.0"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.executable", str(exe))
    assert freight_fate._baked_version() == "1.9.0"


def test_baked_version_missing_file_falls_through(monkeypatch, tmp_path):
    exe = tmp_path / "FreightFate.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr("sys.executable", str(exe))
    assert freight_fate._baked_version() is None


def test_baked_version_malformed_json_falls_through(monkeypatch, tmp_path):
    exe = tmp_path / "FreightFate.exe"
    exe.write_bytes(b"")
    (tmp_path / "build_info.json").write_text("not json", encoding="utf-8")
    monkeypatch.setattr("sys.executable", str(exe))
    assert freight_fate._baked_version() is None
