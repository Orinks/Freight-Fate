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
"""

from __future__ import annotations

import argparse
import importlib.util
import json
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
PRISM_NATIVE_EXTS = {".dll", ".dylib", ".so"}


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


def prism_target_dir(build_dir: Path) -> Path:
    return runtime_root(build_dir) / "prism" / "_native"


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
        f"--include-data-dir={repo_path(PACKAGE_DIR / 'assets')}=freight_fate/assets",
        f"--include-data-dir={repo_path(PACKAGE_DIR / 'data')}=freight_fate/data",
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
    subprocess.run(build_nuitka_command(entry), cwd=ROOT, check=True)

    source_dir, output_kind = find_nuitka_output(output_dir)
    build_dir = DIST / (f"{APP_NAME}.app" if output_kind == "app" else APP_NAME)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    DIST.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, build_dir)
    stage_sound_lib_runtime_files(build_dir)
    stage_prism_runtime_files(build_dir)
    return build_dir


def verify_packaged_payload(build_dir: Path) -> None:
    root = runtime_root(build_dir)

    required = [
        root / "freight_fate" / "assets" / "sounds",
        root / "freight_fate" / "data" / "world.json",
        root / "sound_lib" / "lib",
        root / "prism" / "_native",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "Packaged payload is incomplete: "
            + ", ".join(str(path.relative_to(root)) for path in missing)
        )

    prism_native = [
        path
        for path in (root / "prism" / "_native").rglob("*")
        if path.is_file() and path.suffix.lower() in PRISM_NATIVE_EXTS
    ]
    if not prism_native:
        raise RuntimeError("Prism native speech libraries are missing from the package")


def stamp_build_info(build_dir: Path, label: str) -> None:
    """Record what this build is, for the in-game updater.

    ``label`` is either a nightly tag (``nightly-20260611``) or a plain
    version (``1.6.0``); the release tag for the latter is ``v``-prefixed.
    """
    nightly = label.startswith("nightly-")
    info = {
        "tag": label if nightly else f"v{label}",
        "channel": "dev" if nightly else "stable",
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
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


def archive(build_dir: Path, label: str) -> Path:
    if sys.platform == "win32":
        out = DIST / f"{APP_NAME}-{label}-windows-portable.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for path in sorted(build_dir.rglob("*")):
                z.write(path, Path(APP_NAME) / path.relative_to(build_dir))
    elif sys.platform == "darwin":
        out = DIST / f"{APP_NAME}-{label}-macos.zip"
        subprocess.run(["ditto", "-c", "-k", "--keepParent",
                        str(build_dir), str(out)], check=True)
    else:
        out = DIST / f"{APP_NAME}-{label}-linux-x64.tar.gz"
        with tarfile.open(out, "w:gz") as tar:
            tar.add(build_dir, arcname=APP_NAME)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="",
                        help="release label override, e.g. nightly-20260610")
    parser.add_argument("--skip-smoke", action="store_true",
                        help="skip booting the frozen build")
    args = parser.parse_args()

    label = args.tag or project_version()
    if BUILD.exists():
        shutil.rmtree(BUILD)
    build_dir = run_nuitka()
    stamp_build_info(build_dir, label)
    verify_packaged_payload(build_dir)
    sign_distribution(build_dir)
    if not args.skip_smoke:
        smoke_check(build_dir)
    out = archive(build_dir, label)
    print(f"Built {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
