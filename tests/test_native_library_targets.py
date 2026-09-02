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


def test_cargo_supplies_current_cmake_compatibility_for_bundled_sdl2():
    """Source builders should not need a private Cargo workaround on macOS."""
    config = tomllib.loads((REPO_ROOT / ".cargo" / "config.toml").read_text(encoding="utf-8"))
    assert config["env"]["CMAKE_POLICY_VERSION_MINIMUM"] == {
        "value": "3.5",
        "force": False,
    }


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
    assert set(fetch_bass.TARGETS) == {
        "windows-x86_64",
        "macos-x86_64",
        "macos-aarch64",
        "linux-x86_64",
        "linux-aarch64",
    }
    for key, files in fetch_bass.TARGETS.items():
        assert files, f"{key} has no pinned files"
        for name, (_url, member, want) in files.items():
            assert len(want) == 64, f"{key}/{name} is not a sha256"
            assert member, f"{key}/{name} names no archive member"


@pytest.mark.parametrize(
    "machine, expected",
    [
        ("x86_64", ["linux-x86_64"]),
        # The Blazie BT Speak and BT Braille, Raspberry Pi and the ARM CI
        # runner all report aarch64; macOS-style arm64 is accepted too.
        ("aarch64", ["linux-aarch64"]),
        ("arm64", ["linux-aarch64"]),
    ],
)
def test_fetch_bass_fills_the_linux_directory_for_its_architecture(monkeypatch, machine, expected):
    fetch_bass = load_fetch_bass()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(fetch_bass.platform, "machine", lambda: machine)
    assert fetch_bass.target_keys() == expected


def test_linux_aarch64_pins_the_aarch64_slice_of_the_same_archives():
    """One un4seen archive per add-on carries every slice, so the two Linux
    tables must name the same downloads and differ only in slice and hash."""
    fetch_bass = load_fetch_bass()
    x86 = fetch_bass.TARGETS["linux-x86_64"]
    arm = fetch_bass.TARGETS["linux-aarch64"]
    assert set(x86) == set(arm)
    for name, (url, member, want) in arm.items():
        x86_url, x86_member, x86_want = x86[name]
        assert url == x86_url
        assert member == x86_member.replace("x86_64", "aarch64")
        assert member.startswith("libs/aarch64/")
        assert want != x86_want, f"{name}: the aarch64 pin repeats the x86_64 hash"


def test_fetch_bass_refuses_a_platform_it_has_no_pins_for(monkeypatch):
    """A Linux machine that is neither x86_64 nor aarch64 has no pinned build;
    guessing an un4seen URL for it would be worse than saying so."""
    fetch_bass = load_fetch_bass()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(fetch_bass.platform, "machine", lambda: "riscv64")
    with pytest.raises(SystemExit) as excinfo:
        fetch_bass.target_keys()
    assert "FREIGHT_FATE_BASS_PATH" in str(excinfo.value)


def test_linux_carries_sdl2_statically():
    """Linux compiles SDL2 in too: every distribution ships a different
    libSDL2-2.0.so.0, and a tarball that has to start on all of them cannot
    link against any one. The static build still opens X11, Wayland and the
    audio servers by dlopen, so nothing is lost but the dependency."""
    manifest = tomllib.loads(
        (REPO_ROOT / "crates" / "freight-fate" / "Cargo.toml").read_text(encoding="utf-8")
    )
    linux = manifest["target"]['cfg(target_os = "linux")']["dependencies"]["sdl2"]
    assert "bundled" in linux["features"]
    assert "static-link" in linux["features"]


def test_macos_carries_sdl2_statically():
    """macOS compiles SDL2 in; it must never link a system SDL again.

    Homebrew's `sdl2` became sdl2-compat -- a shim that loads SDL3 at
    RUNTIME, invisible to every install-name audit -- and the 2026-08-30
    tester zip died with "failed to load sdl3" on Macs without Homebrew.
    `bundled` + `static-link` builds the real SDL2 from source into the
    executable, so the shipped app depends on no SDL library at all.
    Windows must NOT get these features: the vendored import library is
    what the build script puts on the search path there.
    """
    manifest = tomllib.loads(
        (REPO_ROOT / "crates" / "freight-fate" / "Cargo.toml").read_text(encoding="utf-8")
    )
    macos = manifest["target"]['cfg(target_os = "macos")']["dependencies"]["sdl2"]
    assert "bundled" in macos["features"]
    assert "static-link" in macos["features"]
    assert "use-pkgconfig" not in macos["features"]

    windows = manifest["target"]["cfg(windows)"]["dependencies"]
    assert "sdl2" not in windows
    # The base dependency may carry platform-neutral features (the window
    # handle for the nonblocking Windows shutdown); the static-link set is
    # what must stay macOS-only.
    base = manifest["dependencies"]["sdl2"]
    assert base["workspace"] is True
    assert not {"bundled", "static-link", "use-pkgconfig"} & set(base.get("features", []))
