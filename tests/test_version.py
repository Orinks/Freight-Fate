"""Version metadata should stay in sync with player-facing text."""

from pathlib import Path

import tomllib

import freight_fate


def test_package_version_matches_pyproject():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert freight_fate.__version__ == data["project"]["version"]
