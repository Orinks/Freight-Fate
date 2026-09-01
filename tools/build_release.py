"""Build a standalone Freight Fate distribution.

Produces a standalone build (fast startup, antivirus-friendly) and
archives it for release:

* Windows: ``dist/FreightFate-<label>-windows-portable.zip``
* Linux:   ``dist/FreightFate-<label>-linux-x64.tar.gz``
* macOS Apple Silicon: ``dist/FreightFate-<label>-macos-arm64.zip``
* macOS Intel: ``dist/FreightFate-<label>-macos.zip``

``<label>`` is the project version from pyproject.toml, or the value of
``--tag`` (used for nightly developer snapshots). Builds use Nuitka on all
platforms. macOS uses Nuitka's app mode with ad-hoc signing but no Apple
Developer ID or notarization, so downloaded apps can require the documented
first-launch Open Anyway step in System Settings.

Run from the repository root: ``uv run python tools/build_release.py``

``--rust`` packages the Rust port instead: ``cargo build --release -p
freight-fate`` (``--cargo-target-dir`` picks the Cargo target directory),
then ``ff-bake`` to turn the JSON data tree into ``world.ffdata``, then the
same ``FreightFate/`` folder layout -- executable renamed to ``FreightFate``,
On macOS it creates ``FreightFate.app`` with the executable under
``Contents/MacOS``, native libraries under ``Contents/Frameworks``, and data,
packs, build metadata, and documents under ``Contents/Resources``. Other
platforms retain the portable folder layout. The Python mode stays the default.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "FreightFate"
SRC_DIR = ROOT / "src"
PACKAGE_DIR = SRC_DIR / "freight_fate"
SOUND_LIB_NATIVE_EXTS = {".dll", ".dylib", ".so"}
SOUND_LIB_ARCH_DIR = "x64"
# Game-shipped BASS addon plugins (e.g. basshls for HLS radio streams);
# staged next to sound_lib's own libraries so one directory holds all of BASS.
ADDON_LIB_DIR = PACKAGE_DIR / "lib"
PRISM_NATIVE_EXTS = {".dll", ".dylib", ".so"}
PRISM_DEPENDENCY_DIR = "prismatoid.libs"
DEFAULT_MUSIC_URL = "https://dev.orinks.net/downloads/music.pak"
DEFAULT_MUSIC_SHA256 = "7787d682c4c289f7c0f33bb1fc714fb54221e10086cc9415d87304fdeffadfb3"


def platform_native_exts() -> set[str]:
    if sys.platform == "win32":
        return {".dll"}
    if sys.platform == "darwin":
        return {".dylib"}
    return {".so"}


def project_version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def nuitka_version(version: str) -> str:
    """Convert the project version into Nuitka's numeric metadata format."""
    base = version.split("+", 1)[0].split(".dev", 1)[0].split("a", 1)[0].split("b", 1)[0]
    parts = [part for part in base.split(".") if part.isdigit()]
    return ".".join((parts + ["0", "0", "0", "0"])[:4])


def repo_path(path: Path) -> str:
    """Return a POSIX path relative to the repository root."""
    return path.relative_to(ROOT).as_posix()


def write_entrypoint() -> Path:
    entry = ROOT / "tools" / "_entry.py"
    entry.write_text(
        "import sys\n\n"
        "from freight_fate.app import main\n\n"
        'if __name__ == "__main__":\n'
        "    sys.exit(main())\n",
        encoding="utf-8",
    )
    return entry


def sound_lib_lib_dir() -> Path:
    """Locate sound_lib's native BASS library directory."""
    spec = importlib.util.find_spec("sound_lib")
    if not spec or not spec.submodule_search_locations:
        raise RuntimeError("sound_lib is not installed; cannot build packaged audio support")
    lib_dir = Path(next(iter(spec.submodule_search_locations))) / "lib"
    if not lib_dir.exists():
        raise RuntimeError(f"sound_lib native library directory was not found: {lib_dir}")
    return lib_dir


def sound_lib_target_dir(build_dir: Path) -> Path:
    if build_dir.suffix == ".app":
        return build_dir / "Contents" / "MacOS" / "sound_lib" / "lib"
    return build_dir / "sound_lib" / "lib"


def package_dir(package_name: str) -> Path:
    spec = importlib.util.find_spec(package_name)
    if not spec or not spec.submodule_search_locations:
        raise RuntimeError(f"{package_name} is not installed; cannot package it")
    return Path(next(iter(spec.submodule_search_locations)))


def runtime_root(build_dir: Path) -> Path:
    if build_dir.suffix == ".app":
        return build_dir / "Contents" / "MacOS"
    return build_dir


def mirror_sound_lib_flat_files_to_arch_dir(target_dir: Path) -> None:
    """Support sound_lib loaders that still search sound_lib/lib/x64."""
    flat_files = [path for path in target_dir.iterdir() if path.is_file()]
    if not flat_files:
        return
    arch_dir = target_dir / SOUND_LIB_ARCH_DIR
    arch_dir.mkdir(exist_ok=True)
    for path in flat_files:
        shutil.copy2(path, arch_dir / path.name)


def add_macos_dylib_aliases(target_dir: Path) -> None:
    """Provide lib*.dylib names for sound_lib's macOS library finder."""
    if sys.platform != "darwin":
        return
    for path in target_dir.rglob("*.dylib"):
        if path.name.startswith("lib"):
            continue
        alias = path.with_name(f"lib{path.name}")
        if not alias.exists():
            shutil.copy2(path, alias)


def stage_sound_lib_runtime_files(build_dir: Path) -> None:
    source_dir = sound_lib_lib_dir()
    target_dir = sound_lib_target_dir(build_dir)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)
    if ADDON_LIB_DIR.exists():
        for path in ADDON_LIB_DIR.iterdir():
            if path.is_file() and path.suffix.lower() in SOUND_LIB_NATIVE_EXTS:
                shutil.copy2(path, target_dir / path.name)
    mirror_sound_lib_flat_files_to_arch_dir(target_dir)
    add_macos_dylib_aliases(target_dir)

    native_files = [
        path
        for path in target_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SOUND_LIB_NATIVE_EXTS
    ]
    if not native_files:
        raise RuntimeError(f"No sound_lib native libraries were staged under {target_dir}")


def prism_native_dir() -> Path:
    """Locate Prism's native screen reader bridge library directory."""
    native_dir = package_dir("prism") / "_native"
    if not native_dir.exists():
        raise RuntimeError(f"Prism native library directory was not found: {native_dir}")
    return native_dir


def prism_dependency_dir() -> Path | None:
    """Locate auditwheel-bundled Prism shared library dependencies."""
    dependency_dir = package_dir("prism").parent / PRISM_DEPENDENCY_DIR
    return dependency_dir if dependency_dir.exists() else None


def native_files(root: Path, exts: set[str] | None = None) -> list[Path]:
    suffixes = exts or platform_native_exts()
    return [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes]


def linux_shared_library_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file() and ".so" in path.name]


def verify_release_dependencies() -> None:
    """Fail early when a platform build lacks runtime dependencies."""
    importlib.import_module("pygame")
    importlib.import_module("numpy")
    importlib.import_module("certifi")
    importlib.import_module("prism")
    importlib.import_module("sound_lib")

    sound_lib_dir = sound_lib_lib_dir()
    if not native_files(sound_lib_dir):
        raise RuntimeError(
            f"sound_lib native audio libraries are missing for this platform: {sound_lib_dir}"
        )

    native_dir = prism_native_dir()
    if not native_files(native_dir):
        expected = ", ".join(sorted(platform_native_exts()))
        raise RuntimeError(
            "Prism native speech libraries are missing for this platform "
            f"({expected}) under {native_dir}"
        )
    verify_prism_native_linkage(native_dir, prism_dependency_dir())


def prism_target_dir(build_dir: Path) -> Path:
    return runtime_root(build_dir) / "prism" / "_native"


def prism_dependency_target_dir(build_dir: Path) -> Path:
    return runtime_root(build_dir) / PRISM_DEPENDENCY_DIR


def stage_prism_runtime_files(build_dir: Path) -> None:
    source_dir = prism_native_dir()
    target_dir = prism_target_dir(build_dir)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)

    native_files = [
        path
        for path in target_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in PRISM_NATIVE_EXTS
    ]
    if not native_files:
        raise RuntimeError(f"No Prism native libraries were staged under {target_dir}")

    dependency_dir = prism_dependency_dir()
    if dependency_dir is not None:
        dependency_target = prism_dependency_target_dir(build_dir)
        if dependency_target.exists():
            shutil.rmtree(dependency_target)
        shutil.copytree(dependency_dir, dependency_target)


def verify_prism_native_linkage(native_dir: Path, dependency_dir: Path | None = None) -> None:
    """On Linux, prove Prism's bundled shared libraries can be resolved."""
    if not sys.platform.startswith("linux"):
        return
    prism_libs = [
        path for path in native_files(native_dir, {".so"}) if path.name.startswith("libprism")
    ]
    if not prism_libs:
        return
    if dependency_dir is None or not linux_shared_library_files(dependency_dir):
        raise RuntimeError(
            "Prism Linux shared library dependencies are missing from the package: "
            f"{PRISM_DEPENDENCY_DIR}"
        )

    search_paths = os.pathsep.join(str(path) for path in (native_dir, dependency_dir))
    env = {**os.environ, "LD_LIBRARY_PATH": search_paths}
    for prism_lib in prism_libs:
        result = subprocess.run(
            ["ldd", str(prism_lib)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        output = f"{result.stdout}\n{result.stderr}".strip()
        if result.returncode != 0 or "not found" in output:
            raise RuntimeError(
                f"Prism native library has unresolved Linux dependencies: {prism_lib}\n{output}"
            )


def _load_tool(name: str):
    """Load a by-path tools module (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stage_sound_pack(build_dir: Path, root: Path | None = None) -> None:
    """Stage the approved encrypted packs and keep the credits readable."""
    root = root or runtime_root(build_dir)
    destination = root / "freight_fate" / "sounds.pak"
    music_destination = root / "freight_fate" / "music.pak"
    committed_pack = PACKAGE_DIR / "sounds.pak"
    committed_music_pack = PACKAGE_DIR / "music.pak"
    destination.parent.mkdir(parents=True, exist_ok=True)
    pack_sounds = _load_tool("pack_sounds")
    if committed_pack.exists():
        shutil.copy2(committed_pack, destination)
    else:
        # Retain the loose-asset fallback for branches that do not carry a pack.
        pack_sounds.pack_sounds_only(output=destination)
    if committed_music_pack.exists():
        shutil.copy2(committed_music_pack, music_destination)
    else:
        pack_sounds.pack_music_only(output=music_destination)
    credits = PACKAGE_DIR / "assets" / "sounds" / "CREDITS.md"
    if not credits.exists():
        raise RuntimeError(f"Sound credits were not found: {credits}")
    shutil.copy2(credits, root / "SOUND_CREDITS.md")


def stage_release_docs(build_dir: Path, root: Path | None = None) -> None:
    """Copy player-facing release documents into the packaged runtime."""
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.exists():
        raise RuntimeError(f"Changelog was not found: {changelog}")
    root = root or runtime_root(build_dir)
    shutil.copy2(changelog, root / "CHANGELOG.md")

    license_file = ROOT / "LICENSE"
    if not license_file.exists():
        raise RuntimeError(f"License was not found: {license_file}")
    # PolyForm's Notices term expects the terms to travel with every copy.
    shutil.copy2(license_file, root / "LICENSE.txt")

    manual = ROOT / "docs" / "user-manual.md"
    if not manual.exists():
        raise RuntimeError(f"User manual was not found: {manual}")
    shutil.copy2(manual, root / "USER_MANUAL.md")
    # Also ship a browser-friendly, accessible HTML rendering of the manual.
    manual_html = _load_tool("manual_html").markdown_to_html(
        manual.read_text(encoding="utf-8"), title="Freight Fate Player Manual"
    )
    (root / "USER_MANUAL.html").write_text(manual_html, encoding="utf-8")

    # The alpha test book travels with the build it describes. A tester who
    # has to go find the current copy in the repo ends up working an old one,
    # and its checklists are written against specific builds.
    test_book = ROOT / "docs" / "alpha-test-book.md"
    if not test_book.exists():
        raise RuntimeError(f"Alpha test book was not found: {test_book}")
    shutil.copy2(test_book, root / "ALPHA_TEST_BOOK.md")
    test_book_html = _load_tool("manual_html").markdown_to_html(
        test_book.read_text(encoding="utf-8"), title="Freight Fate Alpha Test Book"
    )
    (root / "ALPHA_TEST_BOOK.html").write_text(test_book_html, encoding="utf-8")


# keyring locates its platform backends through entry points rather than
# imports, so a build that loses either the backend modules or the metadata
# naming them keeps the online driver token in the fallback file instead -- on
# every platform, and with no visible symptom. Nuitka 4.1 was measured to
# include both on its own, so these are belt and braces, not a fix for a known
# break: they state the requirement so a future Nuitka cannot quietly drop it.
# What actually proves the outcome is tools/check_keyring_packaging.py, which
# CI compiles with these same flags on all three platforms -- so read them
# from here rather than repeating them in the workflow.
KEYRING_NUITKA_ARGS = [
    "--include-package=keyring.backends",
    "--include-distribution-metadata=keyring",
]


# Nuitka compiles one C file per CPU core in parallel. On a Windows machine
# without Visual Studio's C++ toolchain it silently falls back to a downloaded
# MinGW64 GCC whose processes each peak at over half a gigabyte, so one per
# core exhausts memory midway through the ~360-module compile on typical
# 8-16 GB machines -- the failure surfaces as GCC dying partway, and elevation
# does not help. One job per this many bytes keeps the compile inside physical
# memory; MSVC machines (CI, dev boxes) keep Nuitka's default.
MINGW_JOB_MEMORY_BYTES = 2 * 1024**3


def mingw_safe_job_count(cpu_count: int, memory_bytes: int | None) -> int:
    """Parallel compile jobs the MinGW64 fallback can afford on this machine."""
    if not memory_bytes:
        return cpu_count
    return max(1, min(cpu_count, memory_bytes // MINGW_JOB_MEMORY_BYTES))


def windows_total_memory_bytes() -> int | None:
    """Total physical RAM on Windows, or None when the query fails."""
    import ctypes

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_uint32),
            ("dwMemoryLoad", ctypes.c_uint32),
            ("ullTotalPhys", ctypes.c_uint64),
            ("ullAvailPhys", ctypes.c_uint64),
            ("ullTotalPageFile", ctypes.c_uint64),
            ("ullAvailPageFile", ctypes.c_uint64),
            ("ullTotalVirtual", ctypes.c_uint64),
            ("ullAvailVirtual", ctypes.c_uint64),
            ("ullAvailExtendedVirtual", ctypes.c_uint64),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullTotalPhys)


def windows_msvc_available() -> bool:
    """Whether Nuitka will find Visual Studio's C++ toolchain."""
    vswhere = (
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Microsoft Visual Studio"
        / "Installer"
        / "vswhere.exe"
    )
    if not vswhere.exists():
        return False
    result = subprocess.run(
        [
            str(vswhere),
            "-products",
            "*",
            "-latest",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def build_nuitka_command(entry: Path) -> list[str]:
    """Build the Nuitka command for the current platform."""
    system = platform.system()
    output_dir = BUILD / "nuitka"
    numeric_version = nuitka_version(project_version())
    mode = "--mode=app" if system == "Darwin" else "--mode=standalone"
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        mode,
        "--assume-yes-for-downloads",
        "--noinclude-pytest-mode=nofollow",
        "--include-package-data=prism:_native/*",
        "--include-package-data=sound_lib",
        # World data ships baked into the executable (tools/bake_world.py),
        # the loose runtime data files ship baked too (tools/bake_data.py),
        # and sounds ship as a masked pack (tools/pack_sounds.py), never as
        # editable files next to it.
        "--include-module=freight_fate.data._baked_world",
        "--include-module=freight_fate.data._baked_data",
        *KEYRING_NUITKA_ARGS,
        f"--output-dir={output_dir.as_posix()}",
        f"--output-filename={APP_NAME}",
        f"--product-name={APP_NAME}",
        f"--file-description={APP_NAME}",
        f"--product-version={numeric_version}",
        f"--file-version={numeric_version}",
        "--company-name=Orinks",
    ]

    if system == "Windows":
        cmd.append("--windows-console-mode=disable")
        if not windows_msvc_available():
            jobs = mingw_safe_job_count(os.cpu_count() or 1, windows_total_memory_bytes())
            cmd.append(f"--jobs={jobs}")
            print(
                "No Visual Studio C++ toolchain found; Nuitka will compile with its "
                f"downloaded MinGW64 GCC, capped at {jobs} parallel job(s) to fit "
                "this machine's memory."
            )
    elif system == "Darwin":
        cmd.append(f"--macos-app-name={APP_NAME}")

    cmd.append(repo_path(entry))
    return cmd


def find_nuitka_output(output_dir: Path) -> tuple[Path, str]:
    app_candidates = sorted(
        output_dir.glob("*.app"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    for candidate in app_candidates:
        if (candidate / "Contents" / "MacOS" / APP_NAME).exists():
            return candidate, "app"

    dist_candidates = sorted(
        output_dir.glob("*.dist"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    for candidate in dist_candidates:
        exe = APP_NAME + (".exe" if sys.platform == "win32" else "")
        if (candidate / exe).exists():
            return candidate, "dist"

    raise FileNotFoundError(f"Nuitka output was not found under {output_dir}")


def run_nuitka() -> Path:
    """Build and stage a standalone Nuitka distribution."""
    entry = write_entrypoint()
    output_dir = BUILD / "nuitka"
    baked = _load_tool("bake_world").bake()
    baked_data = _load_tool("bake_data").bake()
    try:
        subprocess.run(build_nuitka_command(entry), cwd=ROOT, check=True)
    finally:
        # A leftover baked module would shadow later edits to world_data/
        # (or the runtime data files) in this source checkout, so neither
        # must outlive the compile.
        baked.unlink(missing_ok=True)
        baked_data.unlink(missing_ok=True)

    source_dir, output_kind = find_nuitka_output(output_dir)
    build_dir = DIST / (f"{APP_NAME}.app" if output_kind == "app" else APP_NAME)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    DIST.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, build_dir)
    stage_sound_lib_runtime_files(build_dir)
    stage_prism_runtime_files(build_dir)
    stage_sound_pack(build_dir)
    return build_dir


def verify_sound_packs(root: Path) -> None:
    """Open the staged packs and prove they carry what the game reads."""
    if root.suffix == ".app":
        root = root / "Contents" / "Resources"
    assets_pack = _load_tool("pack_sounds")._load_assets_pack()
    pack_names = assets_pack.SoundPack(root / "freight_fate" / "sounds.pak").names()
    if not any(name.endswith((".ogg", ".wav")) for name in pack_names):
        raise RuntimeError("Packaged sound pack contains no audio files")

    if "engine_classic/idle.ogg" not in pack_names:
        raise RuntimeError(
            "Packaged sound pack predates the classic engine voice, so the "
            "Settings engine-voice option would fall back silently; rebuild "
            "the committed pack with tools/pack_sounds.py on a builder "
            "machine and commit it"
        )

    music_pack_names = assets_pack.SoundPack(root / "freight_fate" / "music.pak").names()
    if not any(name.startswith("music/") for name in music_pack_names):
        raise RuntimeError("Packaged music pack contains no music files")


def verify_packaged_payload(build_dir: Path) -> None:
    root = runtime_root(build_dir)
    exe = root / (APP_NAME + (".exe" if sys.platform == "win32" else ""))

    required = [
        exe,
        root / "build_info.json",
        root / "LICENSE.txt",
        root / "CHANGELOG.md",
        root / "USER_MANUAL.md",
        root / "USER_MANUAL.html",
        root / "ALPHA_TEST_BOOK.md",
        root / "ALPHA_TEST_BOOK.html",
        root / "freight_fate" / "sounds.pak",
        root / "freight_fate" / "music.pak",
        root / "SOUND_CREDITS.md",
        root / "sound_lib" / "lib",
        root / "prism" / "_native",
    ]
    if sys.platform.startswith("linux"):
        required.append(root / PRISM_DEPENDENCY_DIR)
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "Packaged payload is incomplete: "
            + ", ".join(str(path.relative_to(root)) for path in missing)
        )

    exposed_data = root / "freight_fate" / "data"
    if exposed_data.exists():
        raise RuntimeError(
            "Packaged payload exposes editable world data files; they must "
            f"stay baked into the executable: {exposed_data.relative_to(root)}"
        )

    exposed_assets = root / "freight_fate" / "assets"
    if exposed_assets.exists():
        raise RuntimeError(
            "Packaged payload exposes editable sound files; they must stay "
            f"packed in sounds.pak: {exposed_assets.relative_to(root)}"
        )

    verify_sound_packs(root)

    if sys.platform != "win32" and not exe.stat().st_mode & 0o111:
        raise RuntimeError(
            f"Packaged executable is not runnable, so updates cannot restart: "
            f"{exe.relative_to(root)}"
        )

    if not native_files(root / "prism" / "_native"):
        expected = ", ".join(sorted(platform_native_exts()))
        raise RuntimeError(
            "Prism native speech libraries are missing from the package "
            f"for this platform ({expected})"
        )
    verify_prism_native_linkage(
        root / "prism" / "_native",
        root / PRISM_DEPENDENCY_DIR if (root / PRISM_DEPENDENCY_DIR).exists() else None,
    )

    if not native_files(root / "sound_lib" / "lib"):
        expected = ", ".join(sorted(platform_native_exts()))
        raise RuntimeError(
            "sound_lib native audio libraries are missing from the package "
            f"for this platform ({expected})"
        )


def _is_snapshot_label(label: str) -> bool:
    """True for public 1.8 nightlies and Career 1.9 tester prereleases."""
    if label.startswith("nightly-"):
        return True
    prefix = "1.9-tester-"
    suffix = label[len(prefix) :] if label.startswith(prefix) else ""
    return len(suffix) == 8 and suffix.isdigit()


def stamp_build_info(build_dir: Path, label: str, root: Path | None = None) -> None:
    """Record what this build is, for the in-game updater.

    ``label`` is a snapshot tag (``nightly-20260611`` or
    ``1.9-tester-20260828``) or a plain version (``1.6.0``); the release
    tag for the latter is ``v``-prefixed.

    ``package_version`` is the exact ``pyproject.toml`` project version --
    not ``label``, which for a snapshot is a date-stamped tag, not a package
    version. freight_fate.__init__ reads it back to skip the
    importlib.metadata lookup that costs real time on every launch (the
    metadata a frozen build would otherwise scan for is not even installed
    the normal way in a Nuitka standalone build).
    """
    snapshot = _is_snapshot_label(label)
    info = {
        "tag": label if snapshot else f"v{label}",
        "channel": "dev" if snapshot else "stable",
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "package_version": project_version(),
    }
    info_path = (root or runtime_root(build_dir)) / "build_info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)


def sign_distribution(build_dir: Path) -> None:
    """Ad-hoc sign the finalized macOS app bundle."""
    if sys.platform != "darwin":
        return
    verify_macos_native_dependencies(build_dir)
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(build_dir)],
        check=True,
    )
    subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(build_dir)],
        check=True,
    )


def smoke_check(build_dir: Path) -> None:
    """Boot the packaged game for a few frames with dummy drivers."""
    import os

    if build_dir.suffix == ".app":
        exe = build_dir / "Contents" / "MacOS" / APP_NAME
    else:
        exe = build_dir / (APP_NAME + (".exe" if sys.platform == "win32" else ""))
    env = {
        **os.environ,
        "SDL_VIDEODRIVER": "dummy",
        "SDL_AUDIODRIVER": "dummy",
        "FREIGHT_FATE_NO_SPEECH": "1",
    }
    command = [str(exe), "--smoke"]
    if build_dir.suffix == ".app":
        # Stable Nuitka builds still use the generic packaged smoke. Career's
        # GitHub-hosted Rust job selects the explicit non-launch mode instead.
        command.append("--headless")
    with tempfile.TemporaryDirectory(prefix="freight-fate-smoke-") as temp_dir:
        smoke_root = Path(temp_dir)
        smoke_log = smoke_root / "game.log"
        env["FREIGHT_FATE_DATA_DIR"] = str(smoke_root / "player-data")
        env["FREIGHT_FATE_LOG_FILE"] = str(smoke_log)
        try:
            subprocess.run(command, check=True, cwd=exe.parent, env=env, timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if smoke_log.is_file():
                print("Packaged smoke log before failure:", file=sys.stderr)
                print(smoke_log.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
            raise
    print("Smoke check passed: the packaged runtime boots and loads its resources.")


def strip_user_data(build_dir: Path) -> None:
    """Remove any saves/logs left in the build before archiving.

    Freight Fate is portable: a frozen build keeps profiles in a ``saves`` folder
    next to the exe. The smoke check boots the build (and ``profile.py`` may even
    migrate a nearby dev save into it), so a ``saves`` folder appears in the
    build tree. It must NEVER ship -- it would leak the builder's profile and
    signing key, or on CI ship a throwaway profile. The real saves live in the
    user's own game folder / AppData and are untouched by this.
    """
    roots = [build_dir]
    if build_dir.suffix == ".app":
        roots.append(build_dir / "Contents" / "MacOS")
    for root in roots:
        for name in ("saves", "logs"):
            leftover = root / name
            if leftover.exists():
                shutil.rmtree(leftover, ignore_errors=True)
                print(f"Stripped bundled '{name}/' from the build (never ship user data).")


def _archive_entries(out: Path) -> dict[str, tuple[int, int]]:
    """Map an archive's file entries to (size, permission mode)."""
    if out.name.endswith(".tar.gz"):
        with tarfile.open(out, "r:gz") as tar:
            return {m.name: (m.size, m.mode) for m in tar.getmembers() if m.isfile()}
    with zipfile.ZipFile(out) as z:
        return {
            info.filename: (info.file_size, (info.external_attr >> 16) & 0o7777)
            for info in z.infolist()
            if not info.is_dir()
        }


def verify_archive(out: Path) -> None:
    """Re-open the finished archive and prove the payload survived archiving.

    ``verify_packaged_payload`` checks the staged build folder, but the
    archiving step after it is what players actually download. A bad glob,
    archiver quirk, or dropped permission bit here would ship a download with
    no runnable game inside (for example a Linux snapshot missing its
    executable) and nothing else would notice.
    """
    macos_archive = out.name.endswith(("-macos-arm64.zip", "-macos.zip"))
    if macos_archive:
        root = f"{APP_NAME}.app/Contents/MacOS"
        exe_entry = f"{root}/{APP_NAME}"
        needs_exec = True
    elif out.name.endswith("-linux-x64.tar.gz"):
        root = APP_NAME
        exe_entry = f"{root}/{APP_NAME}"
        needs_exec = True
    elif out.name.endswith("-windows-portable.zip"):
        root = APP_NAME
        exe_entry = f"{root}/{APP_NAME}.exe"
        needs_exec = False
    else:
        raise RuntimeError(f"Unrecognized release archive name: {out.name}")

    entries = _archive_entries(out)
    if exe_entry not in entries:
        raise RuntimeError(f"Release archive is missing the executable {exe_entry}: {out.name}")
    size, mode = entries[exe_entry]
    if size == 0:
        raise RuntimeError(f"Release archive executable is empty: {exe_entry} in {out.name}")
    if needs_exec and not mode & 0o111:
        raise RuntimeError(
            f"Release archive executable lost its executable permission: {exe_entry} in {out.name}"
        )

    payload_root = root
    resources_root = f"{APP_NAME}.app/Contents/Resources"
    if macos_archive and f"{resources_root}/build_info.json" in entries:
        payload_root = resources_root
    required = (
        "build_info.json",
        "LICENSE.txt",
        "USER_MANUAL.md",
        "freight_fate/sounds.pak",
        "freight_fate/music.pak",
    )
    missing = [name for name in required if f"{payload_root}/{name}" not in entries]
    if macos_archive and payload_root == resources_root:
        bundle_required = (
            f"{APP_NAME}.app/Contents/Info.plist",
            *(f"{APP_NAME}.app/Contents/Frameworks/{name}" for name in MACOS_REQUIRED_LIBRARIES),
        )
        missing.extend(name for name in bundle_required if name not in entries)
        # No libSDL2 requirement: SDL2 ships compiled into the executable.
    if missing:
        raise RuntimeError(
            f"Release archive is missing payload files: {', '.join(missing)} in {out.name}"
        )


def archive(build_dir: Path, label: str) -> Path:
    if sys.platform == "win32":
        out = DIST / f"{APP_NAME}-{label}-windows-portable.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for path in sorted(build_dir.rglob("*")):
                z.write(path, Path(APP_NAME) / path.relative_to(build_dir))
    elif sys.platform == "darwin":
        is_career_19_tester = label.startswith("1.9-tester-")
        is_apple_silicon = platform.machine().lower() in {"arm64", "aarch64"}
        mac_suffix = "macos-arm64" if is_career_19_tester and is_apple_silicon else "macos"
        out = DIST / f"{APP_NAME}-{label}-{mac_suffix}.zip"
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(build_dir), str(out)], check=True)
    else:
        out = DIST / f"{APP_NAME}-{label}-linux-x64.tar.gz"
        with tarfile.open(out, "w:gz") as tar:
            tar.add(build_dir, arcname=APP_NAME)
    return out


# -- Rust mode ----------------------------------------------------------------
#
# ``--rust`` packages the Rust port (``crates/freight-fate``) instead of the
# Nuitka build. The staged folder keeps the Python layout the in-game updater
# and ``verify_archive`` already expect -- a top-level ``FreightFate`` folder
# holding ``FreightFate(.exe)``, ``build_info.json``, the docs, and a
# ``freight_fate/`` package folder with the packs -- with two differences the
# Rust binary dictates: the runtime data tree ships on disk under
# ``freight_fate/data`` (``ff_core::data::data_resources::data_root`` looks
# for ``<exe dir>/freight_fate/data``; there is no baked module), and the
# native libraries (SDL2, BASS and its plugins, Prism) sit flat beside the
# executable, which is where the crates' build scripts stage them and where
# their loaders look first.

# ``[[bin]] name`` in crates/freight-fate/Cargo.toml. The staged copy is
# renamed to APP_NAME: ``updater::is_frozen`` (both ports) accepts the stem
# case-insensitively, but the apply script, ``extracted_root`` and
# ``verify_archive`` all spell it ``FreightFate``.
RUST_PACKAGE = "freight-fate"
RUST_BIN_STEM = "freightfate"
RUST_STAGE_DIR = BUILD / APP_NAME
# The baked binary data container. ``ff-bake`` builds it out of the JSON
# tree through the game's own loaders, and the release ships it INSTEAD of
# that tree: 142 MB of JSON becomes roughly 7 MB, and the game maps it rather
# than parsing 94 MB of leg shards before the menu. See
# ``ff_core::data::baked``.
RUST_BAKED_FILE = "world.ffdata"
# The container's first eight bytes (``ff_core::data::baked::MAGIC``). Checked
# in the staged payload so a wrong or truncated file fails the build.
BAKED_MAGIC = b"FFDATA\x00\x00"
RUST_BAKE_PACKAGE = "ff-core"
RUST_BAKE_BIN = "ff-bake"
# The runtime JSON files the container replaces. Nothing here is staged; the
# list is what ``verify_rust_payload`` checks did NOT leak into the payload,
# so a half-migrated build that ships both is caught rather than shipped.
RUST_BAKED_SOURCE_FILES = (
    "buffs.json",
    "city_services.json",
    "facility_approaches.json",
    "facility_endpoints.json",
    "local_approaches.json",
    "local_geometry.json",
    "radio_catalog.json",
    "radio_imported.json",
    "street_limits.json",
    "world_data/index.json",
    "world_data/geo.json",
    "world_data/us/cities.json",
    "world_data/us/gameplay/curves.jsonl",
    "world_data/us/gameplay/curve_artifacts.jsonl",
)
# Loose runtime data files still shipped as files, because the container does
# not cover them. Empty today -- everything the game loads is baked -- and
# kept so a new runtime data file has somewhere to be registered before
# anyone has to teach the baker about it.
RUST_DATA_FILES: tuple[str, ...] = ()
RUST_DATA_GLOBS: tuple[str, ...] = ()
# The committed loose sound tree (``assets/sounds``) travels as editable
# files: the Rust asset loader reads it beside the pack. The licensed overlay
# never ships loose.
LOOSE_SOUND_TREE = Path("assets") / "sounds"
LICENSED_SOUND_TREE = "sounds-licensed"
# Git LFS writes this text in place of a pack that was never fetched.
LFS_POINTER_PREFIX = b"version https://git-lfs"
# Build-only leftovers in the Cargo profile directory that are not runtime
# libraries even though they carry a native suffix on some platforms.
CARGO_NON_RUNTIME_SUFFIXES = {".pdb", ".d", ".rlib", ".lib", ".exp"}
MACOS_REQUIRED_LIBRARIES = (
    "libbass.dylib",
    "libbassopus.dylib",
    "libbasshls.dylib",
    "libbassflac.dylib",
    "libprism.dylib",
)


def rust_exe_name(platform_name: str = sys.platform) -> str:
    """The executable file name the staged build ships."""
    return APP_NAME + (".exe" if platform_name == "win32" else "")


def cargo_exe_name(platform_name: str = sys.platform) -> str:
    """The executable file name ``cargo build`` writes."""
    return RUST_BIN_STEM + (".exe" if platform_name == "win32" else "")


def cargo_build_command(target_dir: Path | None = None) -> list[str]:
    cmd = ["cargo", "build", "--release", "-p", RUST_PACKAGE]
    if target_dir is not None:
        cmd.extend(["--target-dir", str(target_dir)])
    return cmd


def cargo_profile_dir(target_dir: Path | None = None) -> Path:
    """Where ``cargo build --release`` leaves the binary and staged libraries."""
    return (target_dir if target_dir is not None else ROOT / "target") / "release"


def bake_command(out: Path, target_dir: Path | None = None, check: bool = False) -> list[str]:
    """``ff-bake`` over the checked-in data tree."""
    cmd = ["cargo", "run", "--release", "-p", RUST_BAKE_PACKAGE, "--bin", RUST_BAKE_BIN]
    if target_dir is not None:
        cmd.extend(["--target-dir", str(target_dir)])
    cmd.extend(["--", "--data-dir", str(PACKAGE_DIR / "data"), "--out", str(out)])
    if check:
        cmd.append("--check")
    return cmd


def bake_world_data(target_dir: Path | None = None, out: Path | None = None) -> Path:
    """Build the baked data container and return where it landed.

    Runs before staging so the container is just another file in the layout
    plan, and so a data tree that fails to load fails the build here rather
    than in front of a player.
    """
    source = PACKAGE_DIR / "data"
    if not (source / "world_data").is_dir():
        raise RuntimeError(f"Runtime data tree is missing from the checkout: {source}")
    destination = out if out is not None else BUILD / RUST_BAKED_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(bake_command(destination, target_dir), cwd=ROOT, check=True)
    if not destination.is_file():
        raise RuntimeError(f"ff-bake wrote no container at {destination}")
    return destination


def is_lfs_pointer(path: Path) -> bool:
    """True when ``path`` is a Git LFS pointer rather than the real file."""
    try:
        if path.stat().st_size > 1024:
            return False
        with open(path, "rb") as f:
            return f.read(len(LFS_POINTER_PREFIX)) == LFS_POINTER_PREFIX
    except OSError:
        return False


def require_real_pack(path: Path) -> None:
    """Refuse to stage a pack that is only a Git LFS pointer."""
    if not path.exists():
        raise RuntimeError(f"Sound pack was not found: {path}")
    if is_lfs_pointer(path):
        raise RuntimeError(
            f"{path.name} is a Git LFS pointer, not the pack itself; run "
            "`git lfs pull` in this checkout before building"
        )


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of ``path`` using bounded memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def music_download_config(env: Mapping[str, str] = os.environ) -> tuple[str, str]:
    """Return the music-pack URL and required lowercase SHA-256 digest."""
    url = env.get("FREIGHT_FATE_MUSIC_URL", DEFAULT_MUSIC_URL)
    expected_sha256 = env.get("FREIGHT_FATE_MUSIC_SHA256", DEFAULT_MUSIC_SHA256).lower()
    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_sha256
    ):
        raise RuntimeError("FREIGHT_FATE_MUSIC_SHA256 must be a 64-character hexadecimal digest")
    return url, expected_sha256


def download_to_path(request: urllib.request.Request, destination: Path) -> None:
    """Stream one authenticated HTTP request to disk with bounded memory."""
    with urllib.request.urlopen(request) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)


def ensure_music_pack(path: Path = PACKAGE_DIR / "music.pak") -> None:
    """Download and verify the public music pack when it is not already present."""
    url, expected_sha256 = music_download_config()
    if path.is_file() and not is_lfs_pointer(path) and file_sha256(path) == expected_sha256:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix="music.pak.", suffix=".download", delete=False
    ) as temp:
        temporary = Path(temp.name)
    try:
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Freight-Fate-release-builder/1.9"},
            )
            download_to_path(request, temporary)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Music-pack download failed with HTTP status {exc.code}. "
                "Check your connection and retry the build."
            ) from exc
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            detail = exc.reason if isinstance(exc, urllib.error.URLError) else str(exc)
            raise RuntimeError(
                f"Music-pack download failed: {detail}. Check your connection and retry the build."
            ) from exc
        actual_sha256 = file_sha256(temporary)
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                "Downloaded music.pak failed SHA-256 verification: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        temporary.replace(path)
        print(f"Downloaded and verified music.pak ({actual_sha256}).")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def rust_data_files(package_dir: Path = PACKAGE_DIR) -> list[Path]:
    """The data files to ship, as paths relative to ``package_dir``."""
    data_dir = package_dir / "data"
    files: list[Path] = []
    for relative in RUST_DATA_FILES:
        source = data_dir / relative
        if not source.is_file():
            raise RuntimeError(f"Runtime data file is missing from the checkout: {source}")
        files.append(Path("data") / relative)
    for pattern in RUST_DATA_GLOBS:
        matches = sorted(data_dir.glob(pattern))
        if not matches:
            raise RuntimeError(f"No runtime data files match {pattern} under {data_dir}")
        files.extend(Path("data") / path.relative_to(data_dir) for path in matches)
    return files


def rust_loose_sound_files(package_dir: Path = PACKAGE_DIR) -> list[Path]:
    """The COMMITTED loose sound tree, relative to ``package_dir``.

    Committed means asked of git, not read off the disk. Globbing the working
    tree shipped whatever audio a developer happened to have sitting there:
    on 2026-08-24 that was 254 MB of loose source audio the packs already
    contain, in a release that should have been 284 MB and came out at 548.
    The checkout it had always been built from happened to have an almost
    empty tree, which is the only reason the sizes had looked right.

    A release is a statement about what the project ships, so it is built
    from what the project has committed. Anything else is a local accident.

    Git is asked about the repository the tree is actually in, not about
    this file's own checkout: ``package_dir`` is a parameter, and pinning
    the question to ``ROOT`` meant any tree outside it -- a second
    checkout, or the fake one the tests stage from -- raised on the way in
    rather than answering.
    """
    tree = package_dir / LOOSE_SOUND_TREE
    if not tree.is_dir():
        raise RuntimeError(f"Committed sound tree was not found: {tree}")
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "."],
        cwd=tree,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    tracked = [tree / name for name in listed.split("\0") if name]
    if not tracked:
        raise RuntimeError(f"git lists no committed files under {tree}")
    return [
        path.relative_to(package_dir)
        for path in sorted(tracked)
        if path.is_file() and "__pycache__" not in path.parts
    ]


def rust_native_libraries(profile_dir: Path, exts: set[str] | None = None) -> list[Path]:
    """Shared libraries the crates' build scripts staged beside the binary.

    Top level only: ``deps/`` holds proc-macro DLLs that are build-time
    artifacts, not runtime libraries.
    """
    suffixes = exts or platform_native_exts()
    return sorted(
        path
        for path in profile_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in suffixes
        and path.suffix.lower() not in CARGO_NON_RUNTIME_SUFFIXES
    )


def macos_linked_libraries(executable: Path) -> list[str]:
    """Return the install names recorded in a Mach-O executable."""
    result = subprocess.run(
        ["otool", "-L", str(executable)],
        check=True,
        capture_output=True,
        text=True,
    )
    install_names: list[str] = []
    for line in result.stdout.splitlines():
        # Dependency rows are indented.  A fat Mach-O repeats an unindented
        # ``<file> (architecture ...):`` header for every slice; that file
        # path is not an install name and must not fail the builder-path audit.
        if not line[:1].isspace():
            continue
        install_name = line.strip().split(" (", 1)[0]
        if install_name and install_name not in install_names:
            install_names.append(install_name)
    return install_names


def macos_dynamic_sdl_dependency(executable: Path) -> Path | None:
    """The SDL2 install name recorded in ``executable``, or ``None``.

    ``None`` is the only shippable answer: the `bundled` + `static-link`
    build compiles SDL2 in, so nothing SDL is loaded at run time. Any
    recorded SDL2 install name means Cargo linked a system SDL -- and since
    Homebrew retired the real SDL2, that library is sdl2-compat, which
    loads SDL3 dynamically where no install-name audit can see it and dies
    on every player Mac without Homebrew ("failed to load sdl3",
    2026-08-30). The staging step refuses to package such an executable.
    """
    for install_name in macos_linked_libraries(executable):
        candidate = Path(install_name)
        if candidate.name.startswith("libSDL2") and candidate.name.endswith(".dylib"):
            return candidate
    return None


def macos_bundle_version(label: str) -> str:
    """A numeric Finder build identity, including the snapshot date."""
    prefix = "1.9-tester-"
    if label.startswith(prefix) and label[len(prefix) :].isdigit():
        date = label[len(prefix) :]
        if len(date) == 8:
            return f"{date[:4]}.{date[4:6]}.{date[6:]}"
    numeric = ".".join(part for part in label.lstrip("v").split(".") if part.isdigit())
    return numeric or "1"


def write_macos_info_plist(app: Path, label: str) -> None:
    """Write the minimal metadata Finder and assistive technology need."""
    short_version = project_version().split(".dev", 1)[0]
    info = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": "Freight Fate",
        "CFBundleExecutable": APP_NAME,
        "CFBundleIdentifier": "net.orinks.freight-fate",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleGetInfoString": f"Freight Fate {short_version} ({label})",
        "CFBundleName": "Freight Fate",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": short_version,
        "CFBundleVersion": macos_bundle_version(label),
        "NSAppleEventsUsageDescription": (
            "Freight Fate uses VoiceOver to speak menus, driving information, and alerts."
        ),
    }
    info_path = app / "Contents" / "Info.plist"
    info_path.parent.mkdir(parents=True, exist_ok=True)
    with info_path.open("wb") as stream:
        plistlib.dump(info, stream, sort_keys=True)


def macos_bundle_binaries(app: Path) -> list[Path]:
    """Mach-O files whose dependencies must stay inside the app or macOS."""
    executable = app / "Contents" / "MacOS" / APP_NAME
    frameworks = app / "Contents" / "Frameworks"
    return [executable, *sorted(frameworks.rglob("*.dylib"))]


def macos_system_install_name(name: str) -> bool:
    return name.startswith(
        ("@rpath/", "@loader_path/", "@executable_path/", "/usr/lib/", "/System/Library/")
    )


def relocate_macos_libraries(app: Path) -> None:
    """Rewrite every bundled dependency away from the builder's filesystem."""
    executable = app / "Contents" / "MacOS" / APP_NAME
    frameworks = app / "Contents" / "Frameworks"
    bundled = {path.name: path for path in frameworks.rglob("*.dylib")}
    for binary in macos_bundle_binaries(app):
        if binary.suffix == ".dylib":
            subprocess.run(
                ["install_name_tool", "-id", f"@rpath/{binary.name}", str(binary)],
                check=True,
            )
        for dependency in macos_linked_libraries(binary):
            if macos_system_install_name(dependency):
                continue
            replacement = bundled.get(Path(dependency).name)
            if replacement is not None:
                subprocess.run(
                    [
                        "install_name_tool",
                        "-change",
                        dependency,
                        f"@rpath/{replacement.name}",
                        str(binary),
                    ],
                    check=True,
                )
    subprocess.run(
        [
            "install_name_tool",
            "-add_rpath",
            "@executable_path/../Frameworks",
            str(executable),
        ],
        check=True,
    )


def verify_macos_native_dependencies(app: Path) -> None:
    """Reject any Mach-O dependency the player's Mac cannot satisfy.

    Two failure shapes: an absolute path into the builder's disk (the
    classic Homebrew leak), and an ``@rpath`` name whose dylib was never
    bundled -- statically clean, dead on arrival. Neither is allowed out.
    """
    frameworks = app / "Contents" / "Frameworks"
    bundled = {path.name for path in frameworks.rglob("*.dylib")}
    forbidden: list[str] = []
    for binary in macos_bundle_binaries(app):
        for dependency in macos_linked_libraries(binary):
            if dependency.startswith("/") and not macos_system_install_name(dependency):
                forbidden.append(f"{binary.name}: {dependency}")
            elif dependency.startswith("@rpath/"):
                leaf = Path(dependency).name
                if leaf != binary.name and leaf not in bundled:
                    forbidden.append(f"{binary.name}: {dependency} (not bundled)")
    if forbidden:
        raise RuntimeError("macOS app contains a builder-local dependency: " + "; ".join(forbidden))


def plan_rust_layout(
    profile_dir: Path,
    package_dir: Path = PACKAGE_DIR,
    platform_name: str = sys.platform,
    native_exts: set[str] | None = None,
    baked_data: Path | None = None,
) -> list[tuple[Path, Path]]:
    """Every (source, destination relative to the staged folder) pair.

    Pure: nothing is copied, so tests can check the plan against a fake
    profile directory and package tree without running cargo. ``baked_data``
    is the container ``bake_world_data`` produced; it is required, because a
    payload without it has no world at all.
    """
    exe = profile_dir / cargo_exe_name(platform_name)
    if not exe.is_file():
        raise RuntimeError(f"cargo build left no executable at {exe}")
    if baked_data is None or not baked_data.is_file():
        raise RuntimeError(
            "the baked data container is missing; run bake_world_data() before staging"
        )
    plan: list[tuple[Path, Path]] = [(exe, Path(rust_exe_name(platform_name)))]
    for lib in rust_native_libraries(profile_dir, native_exts):
        plan.append((lib, Path(lib.name)))
    package = Path("freight_fate")
    plan.append((baked_data, package / "data" / RUST_BAKED_FILE))
    for relative in rust_data_files(package_dir):
        plan.append((package_dir / relative, package / relative))
    for relative in rust_loose_sound_files(package_dir):
        plan.append((package_dir / relative, package / relative))
    # The game's fallback location for BASS add-on plugins
    # (``audio::assets::plugin_lib_dir`` is ``<exe dir>/freight_fate/lib``);
    # the copy beside bass.dll is what normally loads, this one covers a
    # player who swaps in their own BASS.
    if ADDON_LIB_DIR.is_dir():
        suffixes = native_exts or platform_native_exts()
        for path in sorted(ADDON_LIB_DIR.iterdir()):
            if path.is_file() and path.suffix.lower() in suffixes:
                plan.append((path, package / "lib" / path.name))
    return plan


def run_cargo(target_dir: Path | None = None) -> Path:
    """Build the release binary and return the profile directory."""
    subprocess.run(cargo_build_command(target_dir), cwd=ROOT, check=True)
    return cargo_profile_dir(target_dir)


def fetch_bass_command() -> list[str]:
    """Return the checkout-local BASS preparation command."""
    return [sys.executable, str(TOOLS / "fetch_bass.py")]


def prepare_rust_release_dependencies() -> None:
    """Restore native audio and the verified music pack before Cargo runs."""
    subprocess.run(fetch_bass_command(), cwd=ROOT, check=True)
    ensure_music_pack()


def stage_rust_build(
    profile_dir: Path,
    build_dir: Path = RUST_STAGE_DIR,
    baked_data: Path | None = None,
    platform_name: str = sys.platform,
    label: str | None = None,
) -> Path:
    """Assemble the Rust release folder from the plan plus the packs and docs."""
    if platform_name == "darwin":
        for name in MACOS_REQUIRED_LIBRARIES:
            if not (profile_dir / name).is_file():
                raise RuntimeError(f"Rust build is missing macOS player library {name}")
    require_real_pack(PACKAGE_DIR / "sounds.pak")
    require_real_pack(PACKAGE_DIR / "music.pak")
    plan = plan_rust_layout(
        profile_dir,
        platform_name=platform_name,
        native_exts={".dylib"} if platform_name == "darwin" else None,
        baked_data=baked_data,
    )
    if platform_name == "darwin":
        build_dir = build_dir.with_suffix(".app")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    executable_root = runtime_root(build_dir)
    resource_root = (
        build_dir / "Contents" / "Resources" if platform_name == "darwin" else executable_root
    )
    executable_root.mkdir(parents=True)
    resource_root.mkdir(parents=True, exist_ok=True)
    frameworks = build_dir / "Contents" / "Frameworks"
    if platform_name == "darwin":
        frameworks.mkdir(parents=True)
    for source, relative in plan:
        destination = (
            frameworks / source.name
            if platform_name == "darwin" and source.suffix == ".dylib"
            else (
                executable_root / relative
                if relative == Path(rust_exe_name(platform_name))
                else resource_root / relative
            )
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    if platform_name == "darwin":
        # Fail fast, before any packaging: a dynamically linked SDL2 can
        # only be Homebrew's sdl2-compat, which needs an SDL3 the player
        # does not have. The build must carry SDL2 statically.
        sdl = macos_dynamic_sdl_dependency(profile_dir / cargo_exe_name(platform_name))
        if sdl is not None:
            raise RuntimeError(
                f"macOS executable links SDL2 dynamically ({sdl}); Homebrew's "
                "sdl2 is now sdl2-compat, which loads SDL3 at runtime and "
                "fails on player Macs. Build with the crate's `bundled` + "
                "`static-link` SDL2 features instead."
            )
        write_macos_info_plist(build_dir, label or project_version())
        relocate_macos_libraries(build_dir)
    if platform_name != "win32":
        exe = executable_root / rust_exe_name(platform_name)
        exe.chmod(exe.stat().st_mode | 0o755)
    stage_sound_pack(build_dir, resource_root)
    return build_dir


# A player's machine is hostile territory: anything in the payload can and
# will be read, so a leaked key is not a risk but a disclosure. The shapes
# below cover every kind of credential this project touches (Convex deploy
# keys, Vercel blob tokens, GitHub tokens, private key blocks) plus the
# common cloud formats, matched against the payload's text files. Binaries
# and media are skipped: the game's own code never embeds text credentials,
# and scanning a 100 MB executable for 20-character patterns is pure noise.
SECRET_CONTENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    (
        "Convex deploy key",
        re.compile(r"\b(?:prod|preview|dev):[A-Za-z0-9-]+\|[A-Za-z0-9+/=_-]{20,}"),
    ),
    ("Vercel blob token", re.compile(r"\bvercel_blob_rw_[A-Za-z0-9_]{10,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("OpenAI-style secret key", re.compile(r"\bsk-[A-Za-z0-9_-]{24,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{14,}\.eyJ[A-Za-z0-9_-]{14,}\.")),
)

SECRET_SCAN_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".plist",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def verify_no_shipped_secrets(build_dir: Path) -> None:
    """Fail the build if the staged payload carries anything secret-shaped.

    Two checks: file NAMES that only ever hold credentials (`.env*`,
    ``*.pem``, anything mentioning a deploy key), and file CONTENT matching
    a known token format. Both fail fast and name the file, because the one
    thing worse than a leaked key is a leaked key nobody noticed shipping.
    """
    findings: list[str] = []
    for path in sorted(build_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(build_dir).as_posix()
        name = path.name.lower()
        if name.startswith(".env") or name.endswith(".pem") or "deploy_key" in name:
            findings.append(f"{relative}: secret-shaped file name")
            continue
        if path.suffix.lower() not in SECRET_SCAN_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in SECRET_CONTENT_PATTERNS:
            if pattern.search(text):
                findings.append(f"{relative}: looks like a {label}")
    if findings:
        raise RuntimeError(
            "Release payload contains secret-shaped content and must not ship: "
            + "; ".join(findings)
        )


def verify_rust_payload(build_dir: Path, platform_name: str = sys.platform) -> None:
    """Prove the staged Rust folder holds what the binary loads."""
    executable_root = runtime_root(build_dir)
    root = build_dir / "Contents" / "Resources" if build_dir.suffix == ".app" else executable_root
    exe = executable_root / rust_exe_name(platform_name)
    required = [
        exe,
        root / "build_info.json",
        root / "LICENSE.txt",
        root / "CHANGELOG.md",
        root / "USER_MANUAL.md",
        root / "USER_MANUAL.html",
        root / "ALPHA_TEST_BOOK.md",
        root / "ALPHA_TEST_BOOK.html",
        root / "SOUND_CREDITS.md",
        root / "freight_fate" / "sounds.pak",
        root / "freight_fate" / "music.pak",
        root / "freight_fate" / LOOSE_SOUND_TREE / "CREDITS.md",
    ]
    data_dir = root / "freight_fate" / "data"
    container = data_dir / RUST_BAKED_FILE
    required.append(container)
    required.extend(data_dir / relative for relative in RUST_DATA_FILES)
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "Rust payload is incomplete: "
            + ", ".join(path.relative_to(build_dir).as_posix() for path in missing)
        )
    # Not just present: the real container. A truncated copy, or the wrong
    # file under the right name, must not reach a player as "no world data".
    with open(container, "rb") as f:
        if f.read(8) != BAKED_MAGIC:
            raise RuntimeError(f"{RUST_BAKED_FILE} is not a Freight Fate baked data container")
    if container.stat().st_size < 1_000_000:
        raise RuntimeError(
            f"{RUST_BAKED_FILE} is only {container.stat().st_size} bytes; "
            "the real container holds the whole map"
        )
    # And the JSON it replaced stays home: shipping both doubles the download
    # and leaves two answers to every question.
    doubled = [
        relative
        for relative in RUST_BAKED_SOURCE_FILES
        if (data_dir / relative).exists() and relative not in RUST_DATA_FILES
    ]
    if (data_dir / "world_data").exists():
        doubled.append("world_data/")
    if doubled:
        raise RuntimeError(
            "Rust payload ships the JSON the baked container replaced: "
            + ", ".join(sorted(doubled)[:10])
        )

    package = root / "freight_fate"
    leaked = [
        path.relative_to(build_dir).as_posix()
        for path in package.rglob("*")
        if path.name in ("world_source", "__pycache__", LICENSED_SOUND_TREE) or path.suffix == ".py"
    ]
    if leaked:
        raise RuntimeError(
            "Rust payload ships source-only files: " + ", ".join(sorted(leaked)[:10])
        )

    if platform_name == "win32":
        for name in ("SDL2.dll", "bass.dll", "prism.dll"):
            if not (root / name).exists():
                # BASS is fetched rather than committed, so a checkout that
                # skipped the fetch would otherwise build a silent release and
                # say nothing about why.
                hint = (
                    " Run `uv run python tools/fetch_bass.py` and build again."
                    if name.startswith("bass")
                    else ""
                )
                raise RuntimeError(f"Rust payload is missing the native library {name}.{hint}")
    elif platform_name == "darwin":
        frameworks = build_dir / "Contents" / "Frameworks"
        # SDL2 is deliberately absent: it is compiled into the executable
        # (`bundled` + `static-link`), and staging refuses a dynamic link.
        missing_macos = [
            name for name in MACOS_REQUIRED_LIBRARIES if not (frameworks / name).exists()
        ]
        if missing_macos:
            raise RuntimeError(
                "Rust macOS payload is missing native libraries: " + ", ".join(missing_macos)
            )
    elif not native_files(root):
        print(
            "Warning: no native libraries staged beside the executable; the game "
            "will need system SDL2/BASS/Prism on this platform."
        )

    verify_sound_packs(build_dir)
    verify_no_shipped_secrets(build_dir)

    if platform_name != "win32" and os.name != "nt" and not exe.stat().st_mode & 0o111:
        raise RuntimeError(f"Packaged executable is not runnable: {exe.relative_to(build_dir)}")


def build_rust(
    label: str,
    target_dir: Path | None,
    run_smoke: bool,
    *,
    macos_non_launch_verify: bool = False,
) -> Path:
    """The whole ``--rust`` pipeline, ending with the verified archive."""
    if run_smoke and macos_non_launch_verify:
        raise RuntimeError("process smoke and macOS non-launch verification are mutually exclusive")
    if macos_non_launch_verify and sys.platform != "darwin":
        raise RuntimeError("macOS non-launch verification requires macOS")

    prepare_rust_release_dependencies()
    profile_dir = run_cargo(target_dir)
    baked_data = bake_world_data(target_dir)
    build_dir = stage_rust_build(profile_dir, baked_data=baked_data, label=label)
    resource_root = (
        build_dir / "Contents" / "Resources" if build_dir.suffix == ".app" else build_dir
    )
    stamp_build_info(build_dir, label, resource_root)
    stage_release_docs(build_dir, resource_root)
    verify_rust_payload(build_dir)
    strip_user_data(build_dir)
    if run_smoke:
        smoke_check(build_dir)
        # Retain the last-line privacy defense even though smoke redirects its
        # data and log paths.  A runtime fallback must never enter the archive.
        strip_user_data(build_dir)
    elif macos_non_launch_verify:
        # GitHub-hosted macOS has repeatedly left a correctly relocated,
        # deeply signed arm64 process before Rust logging for the full bound.
        # The release proof therefore stays non-launching: payload structure
        # above, native dependency audit + strict signature verification below,
        # and archive structure/content verification after compression.
        print("Using non-launch macOS packaged verification on the hosted runner.")
    else:
        print("Skipped the packaged process smoke check.")
    if sys.platform == "darwin":
        # Prove the archive input after every possible smoke-side mutation.
        sign_distribution(build_dir)
    DIST.mkdir(parents=True, exist_ok=True)
    out = archive(build_dir, label)
    verify_archive(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag", default="", help="release label override, e.g. 1.9-tester-20260828"
    )
    parser.add_argument("--skip-smoke", action="store_true", help="skip booting the frozen build")
    parser.add_argument(
        "--check-dependencies",
        action="store_true",
        help="only verify release-critical runtime dependencies",
    )
    parser.add_argument(
        "--rust",
        action="store_true",
        help="package the Rust port (cargo build --release -p freight-fate) instead of Nuitka",
    )
    parser.add_argument(
        "--cargo-target-dir",
        default="",
        help="--rust only: Cargo target directory (default: target/)",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="--rust only: boot the staged Rust build headless (off until the binary supports --smoke)",
    )
    parser.add_argument(
        "--macos-non-launch-verify",
        action="store_true",
        help=(
            "--rust only: verify a macOS app's payload, native dependencies, signature, "
            "and archive without launching it"
        ),
    )
    args = parser.parse_args()

    if args.macos_non_launch_verify and not args.rust:
        parser.error("--macos-non-launch-verify requires --rust")
    if args.macos_non_launch_verify and args.smoke:
        parser.error("--macos-non-launch-verify cannot be combined with --smoke")
    if args.macos_non_launch_verify and args.skip_smoke:
        parser.error("--macos-non-launch-verify cannot be combined with --skip-smoke")
    if args.macos_non_launch_verify and sys.platform != "darwin":
        parser.error("--macos-non-launch-verify requires macOS")

    if args.check_dependencies:
        verify_release_dependencies()
        print("Release dependency check passed.")
        return 0

    label = args.tag or project_version()

    if args.rust:
        target_dir = Path(args.cargo_target_dir).resolve() if args.cargo_target_dir else None
        out = build_rust(
            label,
            target_dir,
            run_smoke=args.smoke and not args.skip_smoke,
            macos_non_launch_verify=args.macos_non_launch_verify,
        )
        print(f"Built {out} ({out.stat().st_size / 1e6:.1f} MB)")
        return 0

    verify_release_dependencies()
    if BUILD.exists():
        shutil.rmtree(BUILD)
    build_dir = run_nuitka()
    stamp_build_info(build_dir, label)
    stage_release_docs(build_dir)
    verify_packaged_payload(build_dir)
    sign_distribution(build_dir)
    if not args.skip_smoke:
        smoke_check(build_dir)
    strip_user_data(build_dir)  # smoke check leaves a saves/ folder; never ship it
    out = archive(build_dir, label)
    verify_archive(out)
    print(f"Built {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
