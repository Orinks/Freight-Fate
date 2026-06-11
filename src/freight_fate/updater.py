"""In-game auto-updater.

Checks GitHub releases for a newer build, downloads the right archive for
this platform, and swaps it in with a tiny detached helper script that waits
for the game to exit, copies the new files over the install folder, and
relaunches.

Channels mirror the release pipeline: ``stable`` follows tagged releases
(``v1.6.0``), ``dev`` follows the nightly prerelease snapshots
(``nightly-20260611``). The packaged build carries a ``build_info.json``
next to the executable (written by ``tools/build_release.py``) recording its
tag, channel, and build date; that is how a nightly knows a newer nightly
exists even though the project version number has not changed.

Updates only apply to frozen (PyInstaller) builds. Source checkouts are
managed by git and the updater stays out of the way.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

REPO = "Orinks/Freight-fate"
APP_NAME = "FreightFate"
API_BASE = f"https://api.github.com/repos/{REPO}"
USER_AGENT = f"{APP_NAME}-updater"
TIMEOUT = 15  # seconds, per HTTP request

CHANNELS = ("stable", "dev")


# -- build identity ---------------------------------------------------------


@dataclass
class BuildInfo:
    """What this running copy of the game is."""

    tag: str        # "v1.5.0" or "nightly-20260611"
    channel: str    # "stable" or "dev"
    built_at: str   # "2026-06-11" (UTC date); "" when unknown


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_root() -> Path:
    """The folder holding the executable (and ``_internal``)."""
    return Path(sys.executable).resolve().parent


@lru_cache(maxsize=1)
def load_build_info(version: str) -> BuildInfo | None:
    """Read build_info.json from the install folder; cached, since menu
    labels ask every frame and the answer never changes mid-session.

    Returns None when running from source. Frozen builds that predate the
    stamp fall back to a stable identity derived from the package version.
    """
    if not is_frozen():
        return None
    try:
        with open(install_root() / "build_info.json", encoding="utf-8") as f:
            data = json.load(f)
        return BuildInfo(tag=str(data["tag"]), channel=str(data["channel"]),
                         built_at=str(data.get("built_at", "")))
    except (OSError, ValueError, KeyError):
        return BuildInfo(tag=f"v{version}", channel="stable", built_at="")


def resolve_channel(setting: str, build: BuildInfo | None) -> str:
    """The effective update channel: the player's explicit choice, else
    whatever channel this build came from."""
    if setting in CHANNELS:
        return setting
    if build is not None and build.channel in CHANNELS:
        return build.channel
    return "stable"


# -- release discovery ------------------------------------------------------


@dataclass
class UpdateInfo:
    tag: str            # release tag to install
    title: str          # spoken name, e.g. "Freight Fate version 1.6.0"
    notes: list[str]    # release notes flattened to speakable lines
    asset_name: str
    asset_url: str
    asset_size: int     # bytes


def _api_get(path: str):
    req = urllib.request.Request(
        API_BASE + path,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.6.0' -> (1, 6, 0). Unparseable text compares lowest."""
    nums = re.findall(r"\d+", text)
    return tuple(int(n) for n in nums) if nums else (0,)


def _platform_suffix() -> str:
    if sys.platform == "win32":
        return "-windows-portable.zip"
    if sys.platform == "darwin":
        return "-macos.zip"
    return "-linux-x64.tar.gz"


def pick_asset(release: dict, suffix: str | None = None):
    """The (name, url, size) of this platform's archive, or None."""
    suffix = suffix or _platform_suffix()
    for asset in release.get("assets", ()):
        name = asset.get("name", "")
        if name.endswith(suffix):
            return name, asset["browser_download_url"], int(asset.get("size", 0))
    return None


def flatten_markdown(body: str) -> list[str]:
    """Release-notes markdown as plain, speakable lines."""
    lines: list[str] = []
    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line or set(line) <= {"-", "=", "*", "_"}:
            continue
        line = re.sub(r"^#{1,6}\s+", "", line)          # headings
        line = re.sub(r"^[-*+]\s+", "", line)            # bullets
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)  # links
        line = re.sub(r"(\*\*|__|\*|_|`)", "", line)     # emphasis/code
        if line:
            lines.append(line)
    return lines


def _nightly_date(tag: str) -> str:
    """'nightly-20260611' -> '20260611'; '' when not a nightly tag."""
    m = re.fullmatch(r"nightly-(\d{8})", tag)
    return m.group(1) if m else ""


def _update_from_release(release: dict, title: str) -> UpdateInfo | None:
    asset = pick_asset(release)
    if asset is None:
        return None
    name, url, size = asset
    return UpdateInfo(tag=release["tag_name"], title=title,
                      notes=flatten_markdown(release.get("body", "")),
                      asset_name=name, asset_url=url, asset_size=size)


def stable_update_from(release: dict, current_version: str) -> UpdateInfo | None:
    tag = release.get("tag_name", "")
    if parse_version(tag) <= parse_version(current_version):
        return None
    return _update_from_release(
        release, f"Freight Fate version {tag.lstrip('v')}")


def dev_update_from(releases: list[dict], build: BuildInfo | None) -> UpdateInfo | None:
    for release in releases:
        tag = release.get("tag_name", "")
        if not release.get("prerelease") or not _nightly_date(tag):
            continue
        if build is not None:
            if tag == build.tag:
                return None
            build_date = (_nightly_date(build.tag)
                          or build.built_at.replace("-", ""))
            if build_date and _nightly_date(tag) <= build_date:
                return None
        date = _nightly_date(tag)
        spoken = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        return _update_from_release(
            release, f"Freight Fate developer snapshot {spoken}")
    return None


def check_for_update(channel: str, current_version: str,
                     build: BuildInfo | None) -> UpdateInfo | None:
    """Query GitHub for a newer release on ``channel``. Raises OSError on
    network trouble; returns None when already up to date."""
    if channel == "dev":
        return dev_update_from(_api_get("/releases?per_page=20"), build)
    try:
        release = _api_get("/releases/latest")
    except urllib.error.HTTPError as e:
        if e.code == 404:  # no stable release published yet
            return None
        raise
    return stable_update_from(release, current_version)


# -- download and apply -----------------------------------------------------


class UpdateCancelled(Exception):
    pass


def download(info: UpdateInfo, dest_dir: Path, progress=None,
             cancelled=None) -> Path:
    """Fetch the release archive into ``dest_dir``.

    ``progress(done_bytes, total_bytes)`` is called as data arrives;
    ``cancelled`` is a ``threading.Event`` checked between chunks.
    """
    dest = dest_dir / info.asset_name
    req = urllib.request.Request(info.asset_url, headers={"User-Agent": USER_AGENT})
    done = 0
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(dest, "wb") as f:
        total = int(resp.headers.get("Content-Length") or info.asset_size or 0)
        while True:
            if cancelled is not None and cancelled.is_set():
                raise UpdateCancelled
            chunk = resp.read(65536)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress is not None:
                progress(done, total)
    return dest


def extract(archive: Path, staging: Path) -> Path:
    """Unpack the release archive; returns the new app folder inside it."""
    staging.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".tar.gz"):
        import tarfile

        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(staging, filter="data")
    elif sys.platform == "darwin":
        # ditto preserves the executable bits that zipfile would drop
        subprocess.run(["ditto", "-x", "-k", str(archive), str(staging)],
                       check=True)
    else:
        import zipfile

        with zipfile.ZipFile(archive) as z:
            z.extractall(staging)
    new_root = staging / APP_NAME
    if not new_root.is_dir():
        raise FileNotFoundError(f"{APP_NAME} folder missing from {archive.name}")
    return new_root


def make_staging_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix=f"{APP_NAME.lower()}-update-"))


_WINDOWS_SCRIPT = """@echo off
:wait
tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL
if not errorlevel 1 (
  ping -n 2 127.0.0.1 >NUL
  goto wait
)
robocopy "{src}\\_internal" "{dst}\\_internal" /MIR /R:10 /W:1 >NUL
robocopy "{src}" "{dst}" /R:10 /W:1 >NUL
start "" "{dst}\\{exe}"
rmdir /s /q "{staging}"
del "%~f0"
"""

_POSIX_SCRIPT = """#!/bin/sh
while kill -0 {pid} 2>/dev/null; do sleep 1; done
rm -rf "{dst}/_internal"
cp -a "{src}/." "{dst}/"
rm -rf "{staging}"
"{dst}/{exe}" &
rm -f "$0"
"""


def write_apply_script(new_root: Path, install: Path, staging: Path,
                       pid: int) -> Path:
    """The helper script that swaps in the update once the game exits."""
    exe = APP_NAME + (".exe" if sys.platform == "win32" else "")
    template = _WINDOWS_SCRIPT if sys.platform == "win32" else _POSIX_SCRIPT
    text = template.format(pid=pid, src=new_root, dst=install,
                           staging=staging, exe=exe)
    suffix = ".bat" if sys.platform == "win32" else ".sh"
    script = staging.parent / f"{APP_NAME.lower()}-apply-{pid}{suffix}"
    script.write_text(text, encoding="utf-8")
    if sys.platform != "win32":
        script.chmod(0o755)
    return script


def apply_and_restart(new_root: Path, staging: Path) -> None:
    """Spawn the detached apply script. The caller must then quit the game;
    the script waits for this process to exit before touching files."""
    script = write_apply_script(new_root, install_root(), staging, os.getpid())
    if sys.platform == "win32":
        flags = (subprocess.CREATE_NO_WINDOW
                 | subprocess.CREATE_NEW_PROCESS_GROUP)
        subprocess.Popen(["cmd", "/c", str(script)], creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)
    else:
        subprocess.Popen(["/bin/sh", str(script)], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)
    log.info("Update staged; apply script %s spawned", script)
