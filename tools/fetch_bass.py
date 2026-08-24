"""Fetch the BASS runtime the Rust audio backend loads.

BASS is un4seen's and proprietary. The game is free to ship it -- un4seen
charge nothing for non-commercial use -- but this repository is public
source, and hosting someone else's binaries there is a different thing from
bundling them in a release. So the libraries are fetched, not committed.

Where they land is what `crates/bass-sys` looks for:
`crates/bass-sys/vendor/<os>-<arch>/`, which its build script stages next to
the test and game binaries. `FREIGHT_FATE_BASS_PATH` overrides the lot if a
developer keeps BASS somewhere else.

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

TARGETS = {"windows-x86_64": WINDOWS_X64}

# The same libraries ship inside the Python game's own dependency, so a
# checkout that has already run `uv sync` can be served without reaching the
# network at all. Offline machines and CI runners behind a proxy both land
# here.
LOCAL_FALLBACK = REPO_ROOT / ".venv" / "Lib" / "site-packages" / "sound_lib" / "lib"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def target_key() -> str:
    if sys.platform == "win32":
        return "windows-x86_64"
    # Only Windows is pinned today; the game's other targets have no vendored
    # BASS yet, and guessing a URL for them would be worse than saying so.
    raise SystemExit(
        f"fetch_bass: no pinned BASS build for {sys.platform}. "
        "Install BASS yourself and point FREIGHT_FATE_BASS_PATH at it."
    )


def from_local(name: str, want: str) -> bytes | None:
    candidate = LOCAL_FALLBACK / name
    if not candidate.is_file():
        return None
    data = candidate.read_bytes()
    return data if digest(data) == want else None


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

    key = target_key()
    out_dir = VENDOR / key
    out_dir.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []

    for name, (url, member, want) in TARGETS[key].items():
        path = out_dir / name
        if path.is_file() and not args.force:
            if digest(path.read_bytes()) == want:
                print(f"  ok       {name}")
                continue
            print(f"  stale    {name}")
        if args.check:
            missing.append(name)
            print(f"  MISSING  {name}")
            continue
        data = from_local(name, want)
        source = "sound_lib"
        if data is None and not url:
            raise SystemExit(
                f"fetch_bass: {name} has no download URL and is not in "
                f"{LOCAL_FALLBACK}. Run `uv sync` to install sound_lib, or "
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
        path.write_bytes(data)
        print(f"  fetched  {name}  <- {source}")

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
