"""Fetch the BASS runtime the Rust audio backend loads.

BASS is un4seen's and proprietary. The game is free to ship it -- un4seen
charge nothing for non-commercial use -- but this repository is public
source, and hosting someone else's binaries there is a different thing from
bundling them in a release. So the libraries are fetched, not committed.

Where they land is what `crates/bass-sys` looks for:
`crates/bass-sys/vendor/<os>-<arch>/`, which its build script stages next to
the test and game binaries. `FREIGHT_FATE_BASS_PATH` overrides the lot if a
developer keeps BASS somewhere else.

Windows, macOS and Linux are all pinned. The macOS downloads are universal
binaries -- one file carrying the Intel and Apple silicon slices -- so the
same bytes are written into `macos-x86_64` and `macos-aarch64`, and a build
targeting either architecture finds its library. Linux takes the x86_64 or
the aarch64 slice of un4seen's `-linux` packages, whichever the machine is;
the aarch64 one is what the Blazie BT Speak and BT Braille (Raspberry Pi
Compute Module 4 and 5) run.

Every file is checked against a pinned sha256. A silent change upstream --
un4seen ship rolling updates behind stable URLs -- would otherwise walk into
a build with nothing said, and the audio backend is exactly where a quiet
substitution is hardest to notice.

    uv run python tools/fetch_bass.py            # fetch what is missing
    uv run python tools/fetch_bass.py --check    # verify, change nothing
    uv run python tools/fetch_bass.py --force    # re-fetch everything
"""

from __future__ import annotations

import argparse
import hashlib
import io
import platform
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR = REPO_ROOT / "crates" / "bass-sys" / "vendor"

# One entry per file: the archive it lives in, the member inside that archive,
# and the sha256 of the exact bytes this build was verified against. Update a
# hash only after listening to the result -- a decoder swap is audible before
# it is visible.
#
# The pins are the builds the game has actually been played against, which
# are the ones `sound_lib` ships and the Python release has always bundled.
# Checked against un4seen on 2026-08-23: `bass.dll` and `basshls.dll` are
# byte-identical to the current downloads; `bassflac.dll` and `bassopus.dll`
# are NOT -- upstream has moved on -- and the AAC add-on is no longer at a
# guessable URL at all (every candidate 404s; it is behind the add-ons page).
# So the local copy is the primary source and the network is a fallback that
# only succeeds where the pin still matches. Re-pinning to current upstream
# builds is a deliberate job: fetch them, listen to the engine ring and a
# radio stream, then update these hashes.
WINDOWS_X64 = {
    "bass.dll": (
        "https://www.un4seen.com/files/bass24.zip",
        "x64/bass.dll",
        "febb2cf1882d554c3a958280777da0b69f07de6e262df271de11c56e4a54afd4",
    ),
    "bass_aac.dll": (
        # No stable direct URL: un4seen serve the AAC add-on from the add-ons
        # page, not /files. Fetched from sound_lib, or by hand.
        "",
        "x64/bass_aac.dll",
        "9832f4e2d3716c7453b40b9e20284977f20f264c7c7b87381d63aa5c572be97c",
    ),
    "bassflac.dll": (
        "https://www.un4seen.com/files/bassflac24.zip",
        "x64/bassflac.dll",
        "ee6b3898275a42ee502cb73fce5a347ffed7b385190d6e11b11d413fe63625d5",
    ),
    "bassopus.dll": (
        "https://www.un4seen.com/files/bassopus24.zip",
        "x64/bassopus.dll",
        "eec4507ee7d8098b0fa5e90832e2d15eaaeadb6fac781997d3e0d8c0256186e2",
    ),
    "basshls.dll": (
        "https://www.un4seen.com/files/basshls24.zip",
        "x64/basshls.dll",
        "9e970d27bd2048514f38a8c6a87009f2bd8aaa6d4cb29a3ca7abf2035cfa3c6b",
    ),
}

# macOS, from un4seen's own osx packages. Verified against upstream on
# 2026-08-29, which is when these hashes were taken -- unlike the Windows
# pins there is no older build the game was played against first, because
# this is the first macOS support at all.
#
# There is no AAC add-on here and none is needed: BASS on macOS decodes
# AAC and MP4 through the platform's own codecs, and `bass_aac24-osx.zip`
# does not exist upstream (it 404s).
#
# Every file is a fat binary carrying x86_64, i386 and arm64, so one
# download serves both of the macOS vendor directories.
MACOS_UNIVERSAL = {
    "libbass.dylib": (
        "https://www.un4seen.com/files/bass24-osx.zip",
        "libbass.dylib",
        "e81fb7b4d0009ba6343fbfcd840620704dcb840686d405b9734cd37150d31974",
    ),
    "libbassflac.dylib": (
        "https://www.un4seen.com/files/bassflac24-osx.zip",
        "libbassflac.dylib",
        "8efe6c0e372328708f6926b15748f01002da7eba01c790e306121c9853201de2",
    ),
    "libbassopus.dylib": (
        "https://www.un4seen.com/files/bassopus24-osx.zip",
        "libbassopus.dylib",
        "3b59b7d63d684e78d8538d1ef0341da0c523a8ad1f7616038f272a7a4de361a2",
    ),
    "libbasshls.dylib": (
        "https://www.un4seen.com/files/basshls24-osx.zip",
        "libbasshls.dylib",
        "283a87ccdcc53892128150380bd489d9d210a4ebaa34a11ebccc9cff5b21743e",
    ),
}

# Linux, from un4seen's `-linux` packages, which carry one slice per
# architecture under `libs/`. Verified against upstream on 2026-09-02, the
# day the Rust Linux build first existed; like macOS there is no older build
# the game was played against first.
#
# No AAC add-on: `bass_aac24-linux.zip` does not exist upstream (it 404s),
# and the Python Linux build has always shipped without it too.
#
# These depend on nothing beyond libc, so the same files run on every glibc
# distribution; they are what the Linux tarball and AppImage ship. The same
# archives carry an `aarch64` slice (and `armhf` and `x86`, which nothing
# here builds for), pinned below from the same 2026-09-02 download.
LINUX_X86_64 = {
    "libbass.so": (
        "https://www.un4seen.com/files/bass24-linux.zip",
        "libs/x86_64/libbass.so",
        "bd0841d0c14f25065a16192be07c20b045e384199a86a00892cc3864474dbc51",
    ),
    "libbassflac.so": (
        "https://www.un4seen.com/files/bassflac24-linux.zip",
        "libs/x86_64/libbassflac.so",
        "fe7b929ea75636d3a6082f2f741ca616b6cad038d23e3cda56e6bbb66d8eae8e",
    ),
    "libbassopus.so": (
        "https://www.un4seen.com/files/bassopus24-linux.zip",
        "libs/x86_64/libbassopus.so",
        "662bc3131bd6c2a1d8241bcb31b8d728ee82b6436cd9e7a742c16a60dc5ecdda",
    ),
    "libbasshls.so": (
        "https://www.un4seen.com/files/basshls24-linux.zip",
        "libs/x86_64/libbasshls.so",
        "102bb7bad93199257348cfdb3280f51bdd003c0b6b7ea3ec7f04a7d68147defd",
    ),
}

LINUX_AARCH64 = {
    "libbass.so": (
        "https://www.un4seen.com/files/bass24-linux.zip",
        "libs/aarch64/libbass.so",
        "a05ba3afc880b03f36db8dea50fd1d912cacf2a2c85d785fbaef020f5a93adb2",
    ),
    "libbassflac.so": (
        "https://www.un4seen.com/files/bassflac24-linux.zip",
        "libs/aarch64/libbassflac.so",
        "f1860674dd841b297105ca16a1feb916d89458e8aa81c6c9556d085f306dffa4",
    ),
    "libbassopus.so": (
        "https://www.un4seen.com/files/bassopus24-linux.zip",
        "libs/aarch64/libbassopus.so",
        "b1fd77829909776c491a50a6330f2f0dd680de0bf56c45f9278bac680caef5bb",
    ),
    "libbasshls.so": (
        "https://www.un4seen.com/files/basshls24-linux.zip",
        "libs/aarch64/libbasshls.so",
        "bb4f035eb70021408de7c9dd0c5ada37fc885eb65779afb84de970444a8e00c2",
    ),
}

TARGETS = {
    "windows-x86_64": WINDOWS_X64,
    "macos-x86_64": MACOS_UNIVERSAL,
    "macos-aarch64": MACOS_UNIVERSAL,
    "linux-x86_64": LINUX_X86_64,
    "linux-aarch64": LINUX_AARCH64,
}


# The same libraries ship inside the Python game's own dependency, so a
# checkout that has already run `uv sync` can be served without reaching the
# network at all. Offline machines and CI runners behind a proxy both land
# here. Windows venvs put site-packages under `Lib/`; every other platform
# puts it under `lib/pythonX.Y/`.
def local_fallback_dirs() -> list[Path]:
    venv = REPO_ROOT / ".venv"
    return [
        venv / "Lib" / "site-packages" / "sound_lib" / "lib",
        *sorted(venv.glob("lib/python*/site-packages/sound_lib/lib")),
    ]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def target_keys() -> list[str]:
    """Vendor directories to fill for the machine running this script.

    macOS gets two, because the download is universal and the same bytes are
    correct for an Intel target and an Apple silicon one; filling both means
    a cross build does not go looking for a library nobody fetched.
    """
    if sys.platform == "win32":
        return ["windows-x86_64"]
    if sys.platform == "darwin":
        return ["macos-x86_64", "macos-aarch64"]
    if sys.platform.startswith("linux"):
        machine = platform.machine()
        if machine in ("x86_64", "AMD64"):
            return ["linux-x86_64"]
        if machine in ("aarch64", "arm64"):
            return ["linux-aarch64"]
    # Anything else has no pinned build, and guessing a URL for it would be
    # worse than saying so.
    raise SystemExit(
        f"fetch_bass: no pinned BASS build for {sys.platform} {platform.machine()}. "
        "Install BASS yourself and point FREIGHT_FATE_BASS_PATH at it."
    )


def from_local(name: str, want: str) -> bytes | None:
    for directory in local_fallback_dirs():
        candidate = directory / name
        if not candidate.is_file():
            continue
        data = candidate.read_bytes()
        if digest(data) == want:
            return data
    return None


def from_network(url: str, member: str, want: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        archive = response.read()
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        names = {n.lower(): n for n in zf.namelist()}
        actual = names.get(member.lower())
        if actual is None:
            raise SystemExit(f"fetch_bass: {url} has no {member}")
        data = zf.read(actual)
    got = digest(data)
    if got != want:
        raise SystemExit(
            f"fetch_bass: {member} from {url} is not the pinned build.\n"
            f"  expected sha256 {want}\n"
            f"  got      sha256 {got}\n"
            "un4seen ship rolling updates behind stable URLs. Listen to the "
            "result, then update the hash in this file if the new build is good."
        )
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify what is on disk and change nothing",
    )
    parser.add_argument(
        "--force", action="store_true", help="re-fetch even when the file is correct"
    )
    args = parser.parse_args()

    missing: list[str] = []
    # macOS fills two directories from one universal download, so bytes
    # already fetched in this run are reused rather than downloaded twice.
    fetched: dict[str, bytes] = {}

    for key in target_keys():
        out_dir = VENDOR / key
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, (url, member, want) in TARGETS[key].items():
            path = out_dir / name
            if path.is_file() and not args.force:
                if digest(path.read_bytes()) == want:
                    print(f"  ok       {key}/{name}")
                    continue
                print(f"  stale    {key}/{name}")
            if args.check:
                missing.append(f"{key}/{name}")
                print(f"  MISSING  {key}/{name}")
                continue
            data = fetched.get(want)
            source = "already fetched"
            if data is None:
                data = from_local(name, want)
                source = "sound_lib"
            if data is None and not url:
                where = ", ".join(str(d) for d in local_fallback_dirs())
                raise SystemExit(
                    f"fetch_bass: {name} has no download URL and is not in "
                    f"{where}. Run `uv sync` to install sound_lib, or "
                    "download the BASS AAC add-on from un4seen.com by hand and put "
                    f"it in {out_dir}."
                )
            if data is None:
                try:
                    data = from_network(url, member, want)
                    source = url
                except (urllib.error.URLError, TimeoutError) as err:
                    raise SystemExit(
                        f"fetch_bass: could not reach {url} ({err}).\n"
                        "Download it by hand, or run `uv sync` so the copy inside "
                        "sound_lib can be used instead."
                    ) from err
            fetched[want] = data
            path.write_bytes(data)
            print(f"  fetched  {key}/{name}  <- {source}")

    if args.check and missing:
        print(
            f"\nfetch_bass: {len(missing)} file(s) missing or stale. "
            "Run: uv run python tools/fetch_bass.py",
            file=sys.stderr,
        )
        return 1

    licence = VENDOR / "licenses" / "README.md"
    if not licence.is_file():
        print("fetch_bass: the licence note is missing from vendor/licenses", file=sys.stderr)
    if shutil.which("cargo") is None:
        print("fetch_bass: cargo is not on PATH; the libraries are staged anyway")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
