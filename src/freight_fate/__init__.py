"""Freight Fate: an accessible, audio-first trucking simulation."""

from __future__ import annotations

import json
import sys
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


def _baked_version() -> str | None:
    """The version tools/build_release.py stamped into this build, if any.

    A frozen build's ``build_info.json`` sits right beside its executable
    (see ``stamp_build_info``); reading that one small file is a lot less
    work at every launch than the importlib.metadata scan below, which walks
    installed-package metadata that a Nuitka standalone build does not even
    carry the normal way. A source checkout (no such file next to whatever
    Python interpreter is running it) falls through to the paths below.
    """
    try:
        info_path = Path(sys.executable).resolve().parent / "build_info.json"
        data = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = data.get("package_version") if isinstance(data, dict) else None
    return str(version) if version else None


_baked = _baked_version()
if _baked is not None:
    __version__ = _baked
else:
    try:
        __version__ = metadata.version("freight-fate")
    except metadata.PackageNotFoundError:
        __version__ = _read_pyproject_version()
