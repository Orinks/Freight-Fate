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

The ``dev`` channel is not a one-way nightly track: once dev work is promoted
to a stable release, the nightly that follows is content-identical. So when a
stable release is at least as new (by date) as the newest nightly, dev
followers are steered onto stable instead of the equivalent nightly.

Updates only apply to frozen packaged builds. Source checkouts are managed
by git and the updater stays out of the way.
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

from .net import ssl_context

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

    tag: str  # "v1.5.0" or "nightly-20260611"
    channel: str  # "stable" or "dev"
    built_at: str  # "2026-06-11" (UTC date); "" when unknown


def is_frozen() -> bool:
    """True when running as a packaged build rather than a source checkout.

    Covers PyInstaller / cx_Freeze, which set ``sys.frozen``, and Nuitka --
    the current build backend (see ``tools/build_release.py``) -- which does
    not set ``sys.frozen``. Nuitka instead marks every compiled module with a
    ``__compiled__`` global, so a packaged build is detectable here even
    though ``sys.frozen`` is absent.
    """
    if bool(getattr(sys, "frozen", False)) or "__compiled__" in globals():
        return True
    root = install_root()
    exe_name = Path(sys.executable).stem.lower()
    return exe_name == APP_NAME.lower() and (
        (root / "build_info.json").exists()
        or (root / "freight_fate").exists()
        or (root / "_internal").exists()
    )


def install_root() -> Path:
    """The folder holding the executable (and ``_internal``)."""
    return Path(sys.executable).resolve().parent


def install_target() -> Path:
    """What the apply script replaces: the enclosing ``.app`` bundle on
    macOS (the executable sits in ``Contents/MacOS`` inside it), else the
    folder holding the executable."""
    root = install_root()
    if sys.platform == "darwin":
        for parent in (root, *root.parents):
            if parent.suffix == ".app":
                return parent
    return root


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
    except (OSError, ValueError):
        return BuildInfo(tag=f"v{version}", channel="stable", built_at="")
    return build_info_from_dict(data, version)


def build_info_from_dict(data: object, version: str) -> BuildInfo:
    """Normalize a packaged build stamp, preserving useful partial data."""
    if not isinstance(data, dict):
        return BuildInfo(tag=f"v{version}", channel="stable", built_at="")
    tag = str(data.get("tag") or f"v{version}")
    channel = str(data.get("channel") or "")
    if channel not in CHANNELS:
        channel = "dev" if _nightly_date(tag) else "stable"
    return BuildInfo(tag=tag, channel=channel, built_at=str(data.get("built_at") or ""))


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
    tag: str  # release tag to install
    title: str  # spoken name, e.g. "Freight Fate version 1.6.0"
    notes: list[str]  # release notes flattened to speakable lines
    asset_name: str
    asset_url: str
    asset_size: int  # bytes


def _api_get(path: str):
    req = urllib.request.Request(
        API_BASE + path,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl_context()) as resp:
        return json.load(resp)


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.6.0' -> (1, 6, 0, 0); '1.8.6.dev0' -> (1, 8, 6, -1, 0).

    The trailing sentinel orders a ``.devN`` pre-release below the release
    it works toward and above the previous stable, so dev checkouts and
    nightlies are offered the stable they were promoted into. Unparseable
    text compares lowest."""
    base, sep, dev = text.partition(".dev")
    nums = re.findall(r"\d+", base)
    if not nums:
        return (0,)
    parts = tuple(int(n) for n in nums)
    if sep:
        return parts + (-1, *(int(n) for n in re.findall(r"\d+", dev)))
    return parts + (0,)


def spoken_version(version: str) -> str:
    """Player-facing wording for a version: '1.8.6.dev0' becomes
    '1.8.6 development build' so spoken menus never read packaging jargon."""
    base, sep, _ = version.partition(".dev")
    return f"{base} development build" if sep else version


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
        line = re.sub(r"^#{1,6}\s+", "", line)  # headings
        line = re.sub(r"^[-*+]\s+", "", line)  # bullets
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)  # links
        line = re.sub(r"(\*\*|__|\*|_|`)", "", line)  # emphasis/code
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
    return UpdateInfo(
        tag=release["tag_name"],
        title=title,
        notes=flatten_markdown(release.get("body", "")),
        asset_name=name,
        asset_url=url,
        asset_size=size,
    )


def stable_update_from(release: dict, current_version: str) -> UpdateInfo | None:
    tag = release.get("tag_name", "")
    if parse_version(tag) <= parse_version(current_version):
        return None
    return _update_from_release(release, f"Freight Fate version {tag.lstrip('v')}")


def _nightly_releases_newest_first(releases: list[dict]) -> list[dict]:
    nightlies = [
        release
        for release in releases
        if release.get("prerelease") and _nightly_date(release.get("tag_name", ""))
    ]
    return sorted(nightlies, key=lambda r: _nightly_date(r.get("tag_name", "")), reverse=True)


def _latest_stable_release(releases: list[dict]) -> dict | None:
    """The highest-versioned non-prerelease in the list, or None."""
    stables = [
        release
        for release in releases
        if not release.get("prerelease") and parse_version(release.get("tag_name", "")) > (0,)
    ]
    if not stables:
        return None
    return max(stables, key=lambda r: parse_version(r.get("tag_name", "")))


def _release_date(release: dict | None) -> str:
    """A release's date as ``YYYYMMDD``: the nightly tag date for snapshots,
    else the ``published_at`` date for tagged releases; '' when unknown."""
    if release is None:
        return ""
    nightly = _nightly_date(release.get("tag_name", ""))
    if nightly:
        return nightly
    published = str(release.get("published_at") or "")
    return published[:10].replace("-", "") if published else ""


def _build_date(build: BuildInfo | None) -> str:
    """This build's date as ``YYYYMMDD``: the nightly tag date, else the
    stamped build date; '' when unknown."""
    if build is None:
        return ""
    return _nightly_date(build.tag) or build.built_at.replace("-", "")


def _release_timestamp(release: dict | None) -> str:
    """A release's full ``published_at`` (ISO 8601, sortable as text); ''
    when unknown. Dates alone cannot order a same-day stable and nightly,
    and both orderings really happen: the 04:00 UTC cron nightly precedes
    an afternoon promotion, but a small-hours stable precedes that same
    cron -- which then carries fixes merged in between (v1.8.5.1 day,
    2026-07-23: stable 01:07, nightly 03:58 with two backports, and the
    date tie hid the nightly from every dev-channel player)."""
    if release is None:
        return ""
    return str(release.get("published_at") or "")


def _build_timestamp(build: BuildInfo | None, releases: list[dict], stable: dict | None) -> str:
    """The running build's publish moment, recovered from its own release.

    build_info carries only a date, so the release list is the one source
    of intra-day ordering for the copy the player is on."""
    if build is None:
        return ""
    if stable is not None and stable.get("tag_name", "") == build.tag:
        return _release_timestamp(stable)
    for release in releases:
        if release.get("tag_name", "") == build.tag:
            return _release_timestamp(release)
    return ""


def _stable_newer_than_build(
    release: dict, build: BuildInfo | None, build_date: str, build_ts: str = ""
) -> bool:
    """Whether ``release`` (a stable build) is an upgrade for the running copy.

    A stable build compares by version (two builds can share a date but differ
    in version); a nightly build compares by publish timestamp when both are
    known, else by date, since the version number is typically unchanged
    across the dev-to-stable promotion."""
    tag = release.get("tag_name", "")
    if build is not None and tag == build.tag:
        return False
    if build is not None and not _nightly_date(build.tag):
        return parse_version(tag) > parse_version(build.tag)
    stable_ts = _release_timestamp(release)
    if build_ts and stable_ts:
        return stable_ts > build_ts
    stable_date = _release_date(release)
    return not (build_date and stable_date and stable_date <= build_date)


def _nightly_newer_than_build(
    release: dict, build: BuildInfo | None, build_date: str, build_ts: str = ""
) -> bool:
    tag = release.get("tag_name", "")
    if build is not None:
        if tag == build.tag:
            return False
        nightly_ts = _release_timestamp(release)
        if build_ts and nightly_ts:
            return nightly_ts > build_ts
        if build_date and _nightly_date(tag) <= build_date:
            return False
    return True


def dev_update_from(
    releases: list[dict], build: BuildInfo | None, stable: dict | None = None
) -> UpdateInfo | None:
    """The update to offer a dev-channel player.

    Normally this is the newest nightly snapshot. But once dev work is
    promoted to a stable release, the nightly that follows is content-identical
    to that stable. So whenever the latest stable is at least as new (by date)
    as the newest nightly, steer the player onto stable instead -- ties favor
    stable, the promoted build -- so dev followers converge back rather than
    chasing an equivalent nightly. ``stable`` is the latest stable release
    (from ``/releases/latest``); when omitted it is derived from ``releases``.
    """
    nightlies = _nightly_releases_newest_first(releases)
    latest_nightly = nightlies[0] if nightlies else None
    if stable is None:
        stable = _latest_stable_release(releases)

    build_date = _build_date(build)
    build_ts = _build_timestamp(build, releases, stable)
    nightly_date = _release_date(latest_nightly)
    stable_date = _release_date(stable)
    nightly_ts = _release_timestamp(latest_nightly)
    stable_ts = _release_timestamp(stable)

    # Timestamps order a same-day stable and nightly; dates alone cannot,
    # and a date tie wrongly favored a small-hours stable over the 04:00
    # nightly that carried fixes merged between them (2026-07-23).
    if nightly_ts and stable_ts:
        stable_leads = stable_ts >= nightly_ts
    else:
        stable_leads = bool(stable_date) and stable_date >= nightly_date

    if stable is not None and stable_leads:
        if _stable_newer_than_build(stable, build, build_date, build_ts):
            tag = stable.get("tag_name", "")
            return _update_from_release(stable, f"Freight Fate version {tag.lstrip('v')}")
        return None  # already on the newest stable; nothing newer on dev

    if latest_nightly is not None and _nightly_newer_than_build(
        latest_nightly, build, build_date, build_ts
    ):
        date = _nightly_date(latest_nightly.get("tag_name", ""))
        spoken = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        return _update_from_release(latest_nightly, f"Freight Fate developer snapshot {spoken}")
    return None


def check_for_update(
    channel: str, current_version: str, build: BuildInfo | None
) -> UpdateInfo | None:
    """Query GitHub for a newer release on ``channel``. Raises OSError on
    network trouble; returns None when already up to date."""
    if channel == "dev":
        # Nightlies come from the release list; the latest stable is fetched
        # on its own so a long run of nightlies can't paginate it out of view.
        releases = _api_get("/releases?per_page=20")
        try:
            stable = _api_get("/releases/latest")
        except urllib.error.HTTPError as e:
            if e.code != 404:  # 404 == no stable release published yet
                raise
            stable = None
        return dev_update_from(releases, build, stable)
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


def download(info: UpdateInfo, dest_dir: Path, progress=None, cancelled=None) -> Path:
    """Fetch the release archive into ``dest_dir``.

    ``progress(done_bytes, total_bytes)`` is called as data arrives;
    ``cancelled`` is a ``threading.Event`` checked between chunks.
    """
    dest = dest_dir / info.asset_name
    req = urllib.request.Request(info.asset_url, headers={"User-Agent": USER_AGENT})
    done = 0
    with (
        urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl_context()) as resp,
        open(dest, "wb") as f,
    ):
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
        subprocess.run(["ditto", "-x", "-k", str(archive), str(staging)], check=True)
    else:
        import zipfile

        with zipfile.ZipFile(archive) as z:
            z.extractall(staging)
    return extracted_root(staging, archive.name)


def extracted_root(staging: Path, archive_name: str = "the archive") -> Path:
    """The new app folder inside an unpacked archive.

    Windows and Linux archives hold a plain ``FreightFate`` folder; the
    macOS archive holds the ``FreightFate.app`` bundle (``ditto
    --keepParent`` in ``tools/build_release.py``).
    """
    if sys.platform == "darwin":
        bundle = staging / f"{APP_NAME}.app"
        if bundle.is_dir():
            return bundle
    new_root = staging / APP_NAME
    if not new_root.is_dir():
        raise FileNotFoundError(f"{APP_NAME} folder missing from {archive_name}")
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
robocopy "{src}" "{dst}" /E /XD _internal saves /R:10 /W:1 >NUL
start "" "{dst}\\{exe}"
rmdir /s /q "{staging}"
del "%~f0"
"""

_POSIX_SCRIPT = """#!/bin/sh
# Keep portable saves under {dst}/saves intact even if a bad archive includes
# a top-level saves folder.
while kill -0 {pid} 2>/dev/null; do sleep 1; done
rm -rf "{dst}/_internal"
rm -rf "{src}/saves"
cp -a "{src}/." "{dst}/"
rm -rf "{staging}"
"{dst}/{exe}" &
rm -f "$0"
"""

_MACOS_SCRIPT = """#!/bin/sh
# Swap the whole app bundle. Saves live in ~/Library/Application Support,
# never inside the bundle. The old bundle is parked beside the install until
# the new one is in place, so a failed copy cannot leave the player with no
# game at all.
while kill -0 {pid} 2>/dev/null; do sleep 1; done
rm -rf "{dst}.old"
mv "{dst}" "{dst}.old"
if mv "{src}" "{dst}" 2>/dev/null || cp -R "{src}" "{dst}"; then
  rm -rf "{dst}.old"
else
  mv "{dst}.old" "{dst}"
fi
rm -rf "{staging}"
open "{dst}"
rm -f "$0"
"""


def write_apply_script(new_root: Path, install: Path, staging: Path, pid: int) -> Path:
    """The helper script that swaps in the update once the game exits."""
    exe = APP_NAME + (".exe" if sys.platform == "win32" else "")
    if sys.platform == "win32":
        template = _WINDOWS_SCRIPT
    elif sys.platform == "darwin" and install.suffix == ".app":
        template = _MACOS_SCRIPT
    else:
        template = _POSIX_SCRIPT
    text = template.format(pid=pid, src=new_root, dst=install, staging=staging, exe=exe)
    suffix = ".bat" if sys.platform == "win32" else ".sh"
    script = staging.parent / f"{APP_NAME.lower()}-apply-{pid}{suffix}"
    script.write_text(text, encoding="utf-8")
    if sys.platform != "win32":
        script.chmod(0o755)
    return script


def apply_and_restart(new_root: Path, staging: Path) -> None:
    """Spawn the detached apply script. The caller must then quit the game;
    the script waits for this process to exit before touching files."""
    script = write_apply_script(new_root, install_target(), staging, os.getpid())
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            ["cmd", "/c", str(script)],
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    else:
        subprocess.Popen(
            ["/bin/sh", str(script)],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    log.info("Update staged; apply script %s spawned", script)
