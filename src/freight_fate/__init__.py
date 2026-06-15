"""Freight Fate: an accessible, audio-first trucking simulation."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

import tomllib


def _read_pyproject_version() -> str:
    """Fallback for source checkouts before package metadata is installed."""
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        version = data.get("project", {}).get("version")
    except (OSError, tomllib.TOMLDecodeError):
        version = None
    return str(version or "0+unknown")


try:
    __version__ = metadata.version("freight-fate")
except metadata.PackageNotFoundError:
    __version__ = _read_pyproject_version()
