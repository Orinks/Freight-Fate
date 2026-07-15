r"""Fetch per-state OpenStreetMap extracts for the local-data bakes.

The city-service pipeline (``build_city_services.py`` ->
``build_local_approaches.py`` -> ``build_local_geometry.py``) reads one
Geofabrik ``<state>-latest.osm.pbf`` per state from a cache directory. Those
extracts are large binary snapshots, so they are not checked in; this tool
downloads a fresh copy for every state that has a Freight Fate city.

It is the "run every once in a while" refresh mechanism: re-running it pulls
Geofabrik's current daily extract for each state, and a follow-up bake turns
that fresh OSM into the checked-in compact ``city_services``/``local_*`` JSON.

Network is used at build time only; runtime gameplay never touches the network.
Downloads are idempotent (an up-to-date file is skipped), atomic (written to a
``.part`` sidecar and renamed on success), and resumable across runs.

Examples:
    # Every state with a city, into the default cache dir.
    uv run --group tooling python tools/fetch_state_extracts.py

    # Just a few states, forcing a re-download.
    uv run --group tooling python tools/fetch_state_extracts.py \
      --states Texas "West Virginia" --force
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from freight_fate.data.world import get_world

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
GEOFABRIK_BASE = "https://download.geofabrik.de/north-america/us"
# Matches the slug the bake tools derive from the loaded (full-name) state.
STATE_SLUGS = {"District of Columbia": "district-of-columbia"}
MANIFEST_NAME = "extract-sources.json"
USER_AGENT = "FreightFate-map-tooling/1.0 (+build-time OSM extract fetch)"
CHUNK = 1 << 20  # 1 MiB streaming reads


@dataclass
class FetchResult:
    state: str
    slug: str
    path: Path
    status: str  # "downloaded", "skipped", "failed"
    bytes: int = 0
    resolved_url: str = ""
    detail: str = ""


def state_slug(state: str) -> str:
    return STATE_SLUGS.get(state, state.lower().replace(" ", "-"))


def world_states() -> list[str]:
    world = get_world()
    return sorted({world.city(name).state for name in world.city_names()})


def extract_url(slug: str) -> str:
    return f"{GEOFABRIK_BASE}/{slug}-latest.osm.pbf"


def remote_size(url: str, *, timeout: float) -> int | None:
    """Content-Length of the extract after following Geofabrik's redirect,
    or None if the server does not report one."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            length = response.headers.get("Content-Length")
            return int(length) if length is not None else None
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None


def fetch_state(
    state: str,
    cache_dir: Path,
    *,
    force: bool,
    timeout: float,
) -> FetchResult:
    slug = state_slug(state)
    url = extract_url(slug)
    target = cache_dir / f"{slug}-latest.osm.pbf"
    part = target.with_suffix(target.suffix + ".part")

    expected = remote_size(url, timeout=timeout)
    if target.exists() and not force:
        local = target.stat().st_size
        if expected is None or local == expected:
            return FetchResult(state, slug, target, "skipped", local, url, "up to date")
        detail = f"size {local} != remote {expected}, re-downloading"
    else:
        detail = ""

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            resolved = response.geturl()
            written = 0
            with part.open("wb") as handle:
                while True:
                    block = response.read(CHUNK)
                    if not block:
                        break
                    handle.write(block)
                    written += len(block)
        if expected is not None and written != expected:
            part.unlink(missing_ok=True)
            return FetchResult(
                state, slug, target, "failed", written, resolved,
                f"short read: got {written} of {expected} bytes",
            )
        if not _looks_like_pbf(part):
            part.unlink(missing_ok=True)
            return FetchResult(state, slug, target, "failed", written, resolved, "not a PBF")
        part.replace(target)
        return FetchResult(state, slug, target, "downloaded", written, resolved, detail)
    except (urllib.error.URLError, TimeoutError) as exc:
        part.unlink(missing_ok=True)
        return FetchResult(state, slug, target, "failed", 0, url, f"{type(exc).__name__}: {exc}")


def _looks_like_pbf(path: Path) -> bool:
    # An .osm.pbf starts with a 4-byte big-endian BlobHeader length followed by
    # the "OSMHeader" blob type. Cheap sanity check against an HTML error page.
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return False
    return b"OSMHeader" in head


def write_manifest(cache_dir: Path, results: list[FetchResult], accessed: str) -> None:
    manifest = {
        "accessed": accessed,
        "source": "Geofabrik North America / US state extracts",
        "base_url": GEOFABRIK_BASE,
        "license": "OpenStreetMap contributors, ODbL 1.0",
        "states": {
            result.state: {
                "slug": result.slug,
                "file": result.path.name,
                "bytes": result.bytes,
                "status": result.status,
                "resolved_url": result.resolved_url,
            }
            for result in sorted(results, key=lambda item: item.state)
        },
    }
    path = cache_dir / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def human(bytes_: int) -> str:
    value = float(bytes_)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--states",
        nargs="*",
        help="Full state names to fetch (default: every state with a city)",
    )
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--force", action="store_true", help="Re-download even if up to date")
    parser.add_argument("--jobs", type=int, default=3, help="Parallel downloads (be polite)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--accessed",
        default=time.strftime("%Y-%m-%d"),
        help="Accessed date stamped into the manifest (default: today)",
    )
    args = parser.parse_args()

    states = args.states or world_states()
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {len(states)} state extract(s) into {args.cache_dir}", flush=True)

    results: list[FetchResult] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {
            pool.submit(
                fetch_state, state, args.cache_dir, force=args.force, timeout=args.timeout
            ): state
            for state in states
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            marker = {"downloaded": "+", "skipped": "=", "failed": "!"}[result.status]
            extra = f" ({result.detail})" if result.detail else ""
            print(
                f"  {marker} {result.state:<22} {result.status:<10} "
                f"{human(result.bytes):>9}{extra}",
                flush=True,
            )

    write_manifest(args.cache_dir, results, args.accessed)
    downloaded = sum(1 for r in results if r.status == "downloaded")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = [r for r in results if r.status == "failed"]
    total = sum(r.bytes for r in results)
    print(
        f"\nDone: {downloaded} downloaded, {skipped} up to date, "
        f"{len(failed)} failed, {human(total)} on disk.",
        flush=True,
    )
    if failed:
        print("Failed states:", ", ".join(f"{r.state} ({r.detail})" for r in failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
