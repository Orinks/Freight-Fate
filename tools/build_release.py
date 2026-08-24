"""Build a standalone Freight Fate distribution.

Produces a standalone build (fast startup, antivirus-friendly) and
archives it for release:

* Windows: ``dist/FreightFate-<label>-windows-portable.zip``
* Linux:   ``dist/FreightFate-<label>-linux-x64.tar.gz``
* macOS:   ``dist/FreightFate-<label>-macos.zip``

``<label>`` is the project version from pyproject.toml, or the value of
``--tag`` (used for nightly developer snapshots). Builds use Nuitka on all
platforms. macOS uses Nuitka's app mode with ad-hoc signing so Gatekeeper
does not block the unsigned bundle on downloaded builds, while still not
requiring an Apple Developer ID.

Run from the repository root: ``uv run python tools/build_release.py``

``--rust`` packages the Rust port instead: ``cargo build --release -p
freight-fate`` (``--cargo-target-dir`` picks the Cargo target directory),
then ``ff-bake`` to turn the JSON data tree into ``world.ffdata``, then the
same ``FreightFate/`` folder layout -- executable renamed to ``FreightFate``,
the vendored SDL2/BASS/Prism libraries beside it, the baked data container
under ``freight_fate/data``, the packs, ``build_info.json`` and the docs --
staged under ``build/FreightFate`` and archived exactly as the Python build
is. The Python mode stays the default.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
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


def stage_sound_pack(build_dir: Path) -> None:
    """Stage the approved encrypted packs and keep the credits readable."""
    root = runtime_root(build_dir)
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


def stage_release_docs(build_dir: Path) -> None:
    """Copy player-facing release documents into the packaged runtime."""
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.exists():
        raise RuntimeError(f"Changelog was not found: {changelog}")
    root = runtime_root(build_dir)
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


def stamp_build_info(build_dir: Path, label: str) -> None:
    """Record what this build is, for the in-game updater.

    ``label`` is either a nightly tag (``nightly-20260611``) or a plain
    version (``1.6.0``); the release tag for the latter is ``v``-prefixed.

    ``package_version`` is the exact ``pyproject.toml`` project version --
    not ``label``, which for a nightly is a date-stamped tag, not a package
    version. freight_fate.__init__ reads it back to skip the
    importlib.metadata lookup that costs real time on every launch (the
    metadata a frozen build would otherwise scan for is not even installed
    the normal way in a Nuitka standalone build).
    """
    nightly = label.startswith("nightly-")
    info = {
        "tag": label if nightly else f"v{label}",
        "channel": "dev" if nightly else "stable",
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "package_version": project_version(),
    }
    if build_dir.suffix == ".app":
        info_path = build_dir / "Contents" / "MacOS" / "build_info.json"
    else:
        info_path = build_dir / "build_info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)


def sign_distribution(build_dir: Path) -> None:
    """Ad-hoc sign the finalized macOS app bundle."""
    if sys.platform != "darwin":
        return
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(build_dir)],
        check=True,
    )


def smoke_check(build_dir: Path) -> None:
    """Boot the frozen game for a few frames with dummy drivers."""
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
    subprocess.run([str(exe), "--smoke"], check=True, cwd=exe.parent, env=env, timeout=120)
    print("Smoke check passed: the frozen build boots and renders.")


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
    if out.name.endswith("-macos.zip"):
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

    required = (
        "build_info.json",
        "LICENSE.txt",
        "USER_MANUAL.md",
        "freight_fate/sounds.pak",
        "freight_fate/music.pak",
    )
    missing = [name for name in required if f"{root}/{name}" not in entries]
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
        out = DIST / f"{APP_NAME}-{label}-macos.zip"
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
    """
    tree = package_dir / LOOSE_SOUND_TREE
    if not tree.is_dir():
        raise RuntimeError(f"Committed sound tree was not found: {tree}")
    listed = subprocess.run(
        ["git", "ls-files", str(tree.relative_to(ROOT))],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    tracked = [ROOT / name for name in listed.splitlines() if name]
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


def stage_rust_build(
    profile_dir: Path,
    build_dir: Path = RUST_STAGE_DIR,
    baked_data: Path | None = None,
) -> Path:
    """Assemble the Rust release folder from the plan plus the packs and docs."""
    require_real_pack(PACKAGE_DIR / "sounds.pak")
    require_real_pack(PACKAGE_DIR / "music.pak")
    plan = plan_rust_layout(profile_dir, baked_data=baked_data)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)
    for source, relative in plan:
        destination = build_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    if sys.platform != "win32":
        exe = build_dir / rust_exe_name()
        exe.chmod(exe.stat().st_mode | 0o755)
    stage_sound_pack(build_dir)
    return build_dir


def verify_rust_payload(build_dir: Path) -> None:
    """Prove the staged Rust folder holds what the binary loads."""
    exe = build_dir / rust_exe_name()
    required = [
        exe,
        build_dir / "build_info.json",
        build_dir / "LICENSE.txt",
        build_dir / "CHANGELOG.md",
        build_dir / "USER_MANUAL.md",
        build_dir / "USER_MANUAL.html",
        build_dir / "ALPHA_TEST_BOOK.md",
        build_dir / "ALPHA_TEST_BOOK.html",
        build_dir / "SOUND_CREDITS.md",
        build_dir / "freight_fate" / "sounds.pak",
        build_dir / "freight_fate" / "music.pak",
        build_dir / "freight_fate" / LOOSE_SOUND_TREE / "CREDITS.md",
    ]
    data_dir = build_dir / "freight_fate" / "data"
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

    package = build_dir / "freight_fate"
    leaked = [
        path.relative_to(build_dir).as_posix()
        for path in package.rglob("*")
        if path.name in ("world_source", "__pycache__", LICENSED_SOUND_TREE) or path.suffix == ".py"
    ]
    if leaked:
        raise RuntimeError(
            "Rust payload ships source-only files: " + ", ".join(sorted(leaked)[:10])
        )

    if sys.platform == "win32":
        for name in ("SDL2.dll", "bass.dll", "prism.dll"):
            if not (build_dir / name).exists():
                # BASS is fetched rather than committed, so a checkout that
                # skipped the fetch would otherwise build a silent release and
                # say nothing about why.
                hint = (
                    " Run `uv run python tools/fetch_bass.py` and build again."
                    if name.startswith("bass")
                    else ""
                )
                raise RuntimeError(f"Rust payload is missing the native library {name}.{hint}")
    elif not native_files(build_dir):
        print(
            "Warning: no native libraries staged beside the executable; the game "
            "will need system SDL2/BASS/Prism on this platform."
        )

    verify_sound_packs(build_dir)

    if sys.platform != "win32" and not exe.stat().st_mode & 0o111:
        raise RuntimeError(f"Packaged executable is not runnable: {exe.relative_to(build_dir)}")


def build_rust(label: str, target_dir: Path | None, run_smoke: bool) -> Path:
    """The whole ``--rust`` pipeline, ending with the verified archive."""
    profile_dir = run_cargo(target_dir)
    baked_data = bake_world_data(target_dir)
    build_dir = stage_rust_build(profile_dir, baked_data=baked_data)
    stamp_build_info(build_dir, label)
    stage_release_docs(build_dir)
    verify_rust_payload(build_dir)
    if sys.platform == "darwin":
        # No .app bundle yet for the Rust port: ad-hoc sign the bare binary
        # so Gatekeeper does not refuse it outright.
        subprocess.run(
            ["codesign", "--force", "--sign", "-", str(build_dir / rust_exe_name())], check=True
        )
    if run_smoke:
        smoke_check(build_dir)
    else:
        # The Rust binary's ``--smoke`` is not wired yet (main.rs is still
        # the stub); pass ``--smoke`` once it is.
        print("Skipped the smoke check (pass --smoke to boot the staged Rust build).")
    strip_user_data(build_dir)
    DIST.mkdir(parents=True, exist_ok=True)
    out = archive(build_dir, label)
    verify_archive(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="", help="release label override, e.g. nightly-20260610")
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
    args = parser.parse_args()

    if args.check_dependencies:
        verify_release_dependencies()
        print("Release dependency check passed.")
        return 0

    label = args.tag or project_version()

    if args.rust:
        target_dir = Path(args.cargo_target_dir).resolve() if args.cargo_target_dir else None
        out = build_rust(label, target_dir, run_smoke=args.smoke and not args.skip_smoke)
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
