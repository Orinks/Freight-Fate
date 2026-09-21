"""Package the staged Linux build as a cross-distro AppImage.

Runs after ``tools/build_release.py`` and expects the staged folder to
exist: ``dist/FreightFate`` for the Nuitka build, ``build/FreightFate`` for
the Rust one (``--rust``). linuxdeploy bundles the shared libraries the
Ubuntu build links against (Ubuntu-specific sonames do not exist on
Fedora/Arch/openSUSE, and the SDL/X11 chain pygame needs is not installed
everywhere), while the host-integration stacks below stay excluded so the
game keeps using the target system's GLib, D-Bus, AT-SPI/speech stack, and
OpenSSL.

The Rust build needs almost none of that -- SDL2 is compiled in, BASS and
Prism carry their own dependencies beside the executable -- so for it the
AppImage is mostly the launcher, the desktop entry and the self-update
path the tarball cannot offer.

Run from the repository root:
``uv run python tools/build_appimage.py --tag <label>``
``uv run python tools/build_appimage.py --rust --tag <label>``
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
APP_NAME = "FreightFate"
STAGED_DIR = DIST_DIR / APP_NAME
RUST_STAGED_DIR = ROOT / "build" / APP_NAME
WORK_DIR = ROOT / "build" / "appimage"
TOOLS_DIR = WORK_DIR / "tools"
APPDIR = WORK_DIR / "AppDir"
APPIMAGE_ASSETS_DIR = ROOT / "tools" / "appimage"
ICON_SOURCE = APPIMAGE_ASSETS_DIR / "freightfate.png"

# Both tools are published per architecture under the same release, named
# by `uname -m`: x86_64 for the PC build, aarch64 for the ARM64 one (the
# Blazie BT Speak and BT Braille, Raspberry Pi). The AppImage is named the
# same way, which is the AppImage convention; the tarball's `arm64` label is
# build_release.py's.
LINUXDEPLOY_URL = (
    "https://github.com/linuxdeploy/linuxdeploy/releases/download/"
    "1-alpha-20251107-1/linuxdeploy-{arch}.AppImage"
)
APPIMAGE_RUNTIME_URL = (
    "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-{arch}"
)
SUPPORTED_ARCHITECTURES = ("x86_64", "aarch64")


def appimage_architecture(machine: str | None = None) -> str:
    """The `uname -m` name the AppImage tools and the output file use."""
    machine = (machine or platform.machine()).lower()
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    if machine in {"aarch64", "arm64"}:
        return "aarch64"
    raise RuntimeError(f"No AppImage tooling pinned for machine {machine!r}.")


# Libraries that must come from the target system, not the AppImage.
# Grouped by why bundling them would break users:
EXCLUDED_LIBRARY_GLOBS = (
    # GLib/GIO: host gio modules (GVFS, etc.) load into whichever GLib is in
    # the process; shipping our own triggers duplicate-GType registration
    # crashes ("cannot register existing type 'GTask'").
    "libglib-2.0*",
    "libgio-2.0*",
    "libgobject-2.0*",
    "libgmodule-2.0*",
    "libgthread-2.0*",
    # GTK/desktop + accessibility stack: must be the host's so AT-SPI (screen
    # readers), themes, and input methods work.
    "libgtk-3*",
    "libgdk-3*",
    "libgdk_pixbuf-2.0*",
    "libpango*",
    "libcairo*",
    "libpixman*",
    "libatk*",
    "libatspi*",
    "libnotify*",
    "libthai*",
    "libdatrie*",
    "libfribidi*",
    "libgraphite2*",
    "libharfbuzz*",
    # Host system plumbing tied to the running OS.
    "libdbus-1*",
    "libsystemd*",
    "libselinux*",
    "libcap*",
    "libmount*",
    "libblkid*",
    "liblz4*",
    "libgcrypt*",
    "libgpg-error*",
    # TLS/HTTP: use the distro's security-patched OpenSSL/curl stack.
    "libssl*",
    "libcrypto*",
    "libcurl*",
    "libgnutls*",
    "libnettle*",
    "libhogweed*",
    "libtasn1*",
    "libp11-kit*",
    "libidn2*",
    "libunistring*",
    "libpsl*",
    "libnghttp2*",
    "libssh*",
    "librtmp*",
    "liblber*",
    "libldap*",
    "libsasl2*",
    "libgssapi_krb5*",
    "libkrb5*",
    "libk5crypto*",
    "libkeyutils*",
    # Already shipped at the dist top level by Nuitka.
    "libpython*",
    "libreadline*",
    "libtinfo*",
)

# Sonames that must never appear in usr/lib (subset of the globs above that
# CI treats as hard failures — same philosophy as the archive OpenSSL check).
FORBIDDEN_BUNDLED_PREFIXES = (
    "libssl",
    "libcrypto",
    "libglib-2.0",
    "libgio-2.0",
    "libgobject-2.0",
    "libgtk-3",
    "libgdk-3",
    "libatk",
    "libatspi",
)

# Sonames that must be present for other distros to work. pygame's manylinux
# wheel already ships its SDL chain auditwheel-mangled inside the Nuitka dist,
# so what linuxdeploy adds here are the unmangled Ubuntu-soname dependencies of
# the compiled stdlib/native modules (verified deployed during Fedora 43
# validation of the 1.8.5.1 build).
REQUIRED_BUNDLED_SONAMES = (
    "libffi.so.8",
    "libpcre2-8.so.0",
    "libbz2.so.1.0",
    "liblzma.so.5",
)


def project_version() -> str:
    """Read the package version from pyproject.toml."""
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def download(url: str, target: Path, attempts: int = 4) -> Path:
    """Download url to target with simple retries; keep an existing file."""
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            print(f"Downloading {url} (attempt {attempt})")
            with urllib.request.urlopen(url, timeout=120) as response:
                target.write_bytes(response.read())
            if target.stat().st_size == 0:
                raise OSError("downloaded file is empty")
            return target
        except OSError as exc:
            if attempt == attempts:
                raise RuntimeError(f"Failed to download {url}: {exc}") from exc
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def assemble_appdir(staged_dir: Path = STAGED_DIR) -> None:
    """Build the AppDir skeleton from the staged distribution."""
    if APPDIR.exists():
        shutil.rmtree(APPDIR)
    (APPDIR / "opt").mkdir(parents=True)
    print(f"Copying {staged_dir} into AppDir")
    shutil.copytree(staged_dir, APPDIR / "opt" / "freightfate")


def run_linuxdeploy(linuxdeploy: Path, runtime: Path, label: str) -> Path:
    """Run linuxdeploy and return the produced AppImage path."""
    command = [
        str(linuxdeploy),
        # Runner images ship without FUSE; run the AppImage tool extracted.
        "--appimage-extract-and-run",
        f"--appdir={APPDIR}",
        f"--deploy-deps-only={APPDIR / 'opt' / 'freightfate'}",
        f"--desktop-file={APPIMAGE_ASSETS_DIR / 'freightfate.desktop'}",
        f"--icon-file={WORK_DIR / 'freightfate.png'}",
        f"--custom-apprun={APPIMAGE_ASSETS_DIR / 'AppRun'}",
        "--output=appimage",
    ]
    command.extend(f"--exclude-library={glob}" for glob in EXCLUDED_LIBRARY_GLOBS)

    env = os.environ.copy()
    env["LINUXDEPLOY_OUTPUT_VERSION"] = label
    env["LDAI_RUNTIME_FILE"] = str(runtime)

    shutil.copy2(ICON_SOURCE, WORK_DIR / "freightfate.png")
    print("Running:", " ".join(command))
    subprocess.run(command, cwd=WORK_DIR, check=True, env=env)

    produced = sorted(WORK_DIR.glob("*.AppImage"), key=lambda p: p.stat().st_mtime)
    produced = [path for path in produced if path.name != linuxdeploy.name]
    if not produced:
        raise RuntimeError("linuxdeploy did not produce an AppImage")
    return produced[-1]


def verify_bundled_libraries(nuitka: bool = True) -> None:
    """Fail the build when usr/lib bundles host stacks or misses portability libs."""
    lib_dir = APPDIR / "usr" / "lib"
    bundled = {path.name for path in lib_dir.iterdir()} if lib_dir.exists() else set()

    forbidden = sorted(name for name in bundled if name.startswith(FORBIDDEN_BUNDLED_PREFIXES))
    if forbidden:
        raise RuntimeError(
            "AppImage must not bundle host-integration libraries "
            f"(GLib/GTK/OpenSSL stay on the target system): {forbidden}"
        )

    # The Rust executable links nothing but libc, so there is nothing for
    # linuxdeploy to add and the Nuitka list would only fail it.
    missing = sorted(set(REQUIRED_BUNDLED_SONAMES) - bundled) if nuitka else []
    if missing:
        raise RuntimeError(f"AppImage is missing libraries needed on non-Debian distros: {missing}")
    print(f"Verified {len(bundled)} bundled libraries in usr/lib")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="", help="release label override, e.g. nightly-20260610")
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Keep build/appimage for debugging instead of reusing it clean.",
    )
    parser.add_argument(
        "--rust",
        action="store_true",
        help=f"package the Rust build tools/build_release.py --rust staged under {RUST_STAGED_DIR}",
    )
    args = parser.parse_args()

    if platform.system() != "Linux":
        print("AppImage packaging only runs on Linux.")
        return 1
    staged_dir = RUST_STAGED_DIR if args.rust else STAGED_DIR
    if not (staged_dir / APP_NAME).exists():
        hint = "tools/build_release.py --rust" if args.rust else "tools/build_release.py"
        print(f"Staged build not found at {staged_dir}; run {hint} first.")
        return 1

    label = args.tag or project_version()
    print(f"Freight Fate AppImage build, label {label}")

    if WORK_DIR.exists() and not args.keep_workdir:
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    arch = appimage_architecture()
    linuxdeploy = download(
        LINUXDEPLOY_URL.format(arch=arch), TOOLS_DIR / f"linuxdeploy-{arch}.AppImage"
    )
    linuxdeploy.chmod(0o755)
    runtime = download(APPIMAGE_RUNTIME_URL.format(arch=arch), TOOLS_DIR / f"runtime-{arch}")

    assemble_appdir(staged_dir)
    produced = run_linuxdeploy(linuxdeploy, runtime, label)
    verify_bundled_libraries(nuitka=not args.rust)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target = DIST_DIR / f"{APP_NAME}-{label}-linux-{arch}.AppImage"
    if target.exists():
        target.unlink()
    shutil.move(produced, target)
    target.chmod(0o755)
    print(f"Created {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
