"""Which platforms the Rust build can actually get its native libraries on.

A Mac tester found the port unbuildable for two reasons that no test would
have caught: `tools/fetch_bass.py` bailed out on anything but Windows, so
there was no BASS to load, and the `sdl2` crate linked with a bare `-lSDL2`
that never looks in Homebrew's prefix, so the link failed with SDL2 sitting
right there. Both are build configuration rather than gameplay, and both are
invisible from a Windows machine -- which is exactly why they are pinned
here rather than left to whoever next opens a Mac.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_fetch_bass():
    path = REPO_ROOT / "tools" / "fetch_bass.py"
    spec = importlib.util.spec_from_file_location("fetch_bass", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "platform, expected",
    [
        ("win32", ["windows-x86_64"]),
        # One universal download serves both, and filling both means a build
        # targeting either architecture finds its library.
        ("darwin", ["macos-x86_64", "macos-aarch64"]),
    ],
)
def test_fetch_bass_covers_the_platforms_the_game_ships_on(monkeypatch, platform, expected):
    fetch_bass = load_fetch_bass()
    monkeypatch.setattr(sys, "platform", platform)
    assert fetch_bass.target_keys() == expected


def test_every_fetch_bass_target_has_a_pinned_table():
    fetch_bass = load_fetch_bass()
    assert set(fetch_bass.TARGETS) == {"windows-x86_64", "macos-x86_64", "macos-aarch64"}
    for key, files in fetch_bass.TARGETS.items():
        assert files, f"{key} has no pinned files"
        for name, (_url, member, want) in files.items():
            assert len(want) == 64, f"{key}/{name} is not a sha256"
            assert member, f"{key}/{name} names no archive member"


def test_fetch_bass_refuses_a_platform_it_has_no_pins_for(monkeypatch):
    fetch_bass = load_fetch_bass()
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(SystemExit) as excinfo:
        fetch_bass.target_keys()
    assert "FREIGHT_FATE_BASS_PATH" in str(excinfo.value)


def test_macos_links_sdl2_through_pkg_config():
    """Homebrew installs SDL2 outside the linker's default search path.

    Windows must NOT get the feature: there is no pkg-config there, and the
    vendored import library is what the build script puts on the search path.
    """
    manifest = tomllib.loads(
        (REPO_ROOT / "crates" / "freight-fate" / "Cargo.toml").read_text(encoding="utf-8")
    )
    macos = manifest["target"]['cfg(target_os = "macos")']["dependencies"]["sdl2"]
    assert "use-pkgconfig" in macos["features"]

    windows = manifest["target"]["cfg(windows)"]["dependencies"]
    assert "sdl2" not in windows
    assert manifest["dependencies"]["sdl2"] == {"workspace": True}
