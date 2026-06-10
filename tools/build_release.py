"""Build a standalone Freight Fate distribution with PyInstaller.

Produces a one-directory build (fast startup, antivirus-friendly) and
archives it for release:

* Windows: ``dist/FreightFate-<label>-windows-portable.zip``
* Linux:   ``dist/FreightFate-<label>-linux-x64.tar.gz``
* macOS:   ``dist/FreightFate-<label>-macos.zip``

``<label>`` is the project version from pyproject.toml, or the value of
``--tag`` (used for nightly developer snapshots). The bundle collects the
game's assets, the BASS libraries shipped inside sound_lib, and Prism's
native speech library.

Run from the repository root: ``uv run python tools/build_release.py``
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
APP_NAME = "FreightFate"


def project_version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def run_pyinstaller() -> Path:
    """Freeze the game; returns the onedir build directory."""
    entry = ROOT / "tools" / "_entry.py"
    entry.write_text(
        "import sys\n\n"
        "from freight_fate.app import main\n\n"
        'if __name__ == "__main__":\n'
        "    sys.exit(main())\n",
        encoding="utf-8",
    )
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", APP_NAME,
        "--distpath", str(DIST),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        # game package data: sounds, music, and the world map JSON
        "--collect-data", "freight_fate",
        # native libraries loaded at runtime via ctypes
        "--collect-all", "sound_lib",
        "--collect-all", "prism",
    ]
    if sys.platform == "win32":
        cmd.append("--windowed")
    cmd.append(str(entry))
    subprocess.run(cmd, check=True)
    return DIST / APP_NAME


def smoke_check(build_dir: Path) -> None:
    """Boot the frozen game for a few frames with dummy drivers."""
    import os

    exe = build_dir / (APP_NAME + (".exe" if sys.platform == "win32" else ""))
    env = {
        **os.environ,
        "SDL_VIDEODRIVER": "dummy",
        "SDL_AUDIODRIVER": "dummy",
        "FREIGHT_FATE_NO_SPEECH": "1",
    }
    subprocess.run([str(exe), "--smoke"], check=True, env=env, timeout=120)
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
    if (ROOT / "build").exists():
        shutil.rmtree(ROOT / "build")
    build_dir = run_pyinstaller()
    if not args.skip_smoke:
        smoke_check(build_dir)
    out = archive(build_dir, label)
    print(f"Built {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
