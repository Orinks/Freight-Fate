"""Keyless NTAD layer fetch with an on-disk snapshot, used at bake time.

The National Transportation Atlas Database is published by the Bureau of
Transportation Statistics as plain ArcGIS feature services. No key, no signup,
no OAuth -- a ``User-Agent`` and a query string is the whole protocol. Every
NTAD layer carries the same licence:

    This NTAD dataset is a work of the United States government as defined in
    17 U.S.C. Sec. 101 and as such are not protected by any U.S. copyrights.
    This work is available for unrestricted public use.

so the features can be redistributed inside the baked world with nothing owed
beyond the acknowledgment BTS asks for, which travels in the snapshot header.

Why a snapshot and not a live query: the shipped game reads one baked
container and never opens a socket for world data. Fetching happens here, once,
on a maintainer's machine; what players get is the bake. That also makes a
re-run reproducible -- the second run reads the cached file and asks BTS
nothing.

The cache is the offline story. ``load()`` prefers the snapshot on disk and
only reaches the network when there is nothing there. A ``refresh=True`` run
that cannot reach BTS keeps serving the snapshot it already has rather than
failing the bake around it; only a first run with no cache and no network is
an error, because there is genuinely no data to hand back.

Usage::

    uv run python tools/ntad.py --layer truck_parking --stats
    uv run python tools/ntad.py --layer truck_parking --refresh
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple

USER_AGENT = "FreightFate/1.9 (accessible trucking game; https://orinks.net)"

#: Where snapshots live. Matches the OSM extract cache convention
#: (``~/.cache/freight-fate-osm``) so a maintainer clearing one finds the other.
CACHE_DIR = Path(os.environ.get("FF_NTAD_CACHE", Path.home() / ".cache" / "freight-fate-ntad"))

#: ArcGIS caps a single response. Ask for a fixed page and keep going while a
#: page comes back full, rather than trusting one request to be the whole layer.
PAGE_SIZE = 1000

REQUEST_TIMEOUT_S = 90
RETRIES = 3

NTAD_LICENSE = (
    "Work of the United States government under 17 U.S.C. Sec. 101; not "
    "protected by U.S. copyright. Available for unrestricted public use."
)


class Layer(NamedTuple):
    """One NTAD feature layer and the provenance that has to ride with it."""

    url: str
    title: str
    acknowledgment: str
    about: str


LAYERS: dict[str, Layer] = {
    "truck_parking": Layer(
        url=(
            "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/"
            "NTAD_Truck_Stop_Parking/FeatureServer/0"
        ),
        title="Truck Stop Parking (FHWA Jason's Law inventory)",
        acknowledgment=(
            "Acknowledgment of the Federal Highway Administration (FHWA), State "
            "DOTs, Trucker's Friend database, and the Bureau of Transportation "
            "Statistics (BTS) [distributor]."
        ),
        about="https://geodata.bts.gov/datasets/usdot::truck-stop-parking/about",
    ),
    "weigh_in_motion": Layer(
        url=(
            "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/"
            "NTAD_Weigh_in_Motion_Stations/FeatureServer/0"
        ),
        title="Weigh-in-Motion (WIM) Stations",
        acknowledgment=(
            "Acknowledgment of the Federal Highway Administration (FHWA) and the "
            "Bureau of Transportation Statistics (BTS) [distributor]."
        ),
        about="https://geodata.bts.gov/datasets/usdot::weigh-in-motion-wim-stations/about",
    ),
}

Opener = Callable[[str], dict[str, Any]]


def snapshot_path(slug: str, cache_dir: Path | None = None) -> Path:
    return (cache_dir or CACHE_DIR) / f"{slug}.geojson"


def load(
    slug: str,
    *,
    refresh: bool = False,
    cache_dir: Path | None = None,
    opener: Opener | None = None,
) -> dict[str, Any]:
    """One NTAD layer as GeoJSON, from the snapshot where there is one.

    Reads the cached snapshot unless ``refresh`` is set. A refresh that cannot
    reach BTS falls back to the snapshot already on disk; with no snapshot and
    no network there is nothing to return, and that raises.
    """
    path = snapshot_path(slug, cache_dir)
    cached: dict[str, Any] | None = None
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if not refresh:
            return cached

    try:
        payload = fetch(slug, opener=opener)
    except (OSError, RuntimeError, ValueError) as exc:
        if cached is not None:
            print(
                f"ntad: refresh of {slug} failed ({exc}); serving the snapshot "
                f"read {cached.get('ff_source', {}).get('accessed', 'earlier')}",
                file=sys.stderr,
            )
            return cached
        raise

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def fetch(slug: str, *, opener: Opener | None = None) -> dict[str, Any]:
    """Every feature in one layer, paged, stamped with where it came from."""
    try:
        layer = LAYERS[slug]
    except KeyError:
        raise ValueError(f"unknown NTAD layer {slug!r}; have {sorted(LAYERS)}") from None

    read = opener or _read_json
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = urllib.parse.urlencode(
            {
                "where": "1=1",
                "outFields": "*",
                "outSR": "4326",
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
            }
        )
        page = read(f"{layer.url}/query?{params}")
        batch = page.get("features") or []
        features.extend(batch)
        # A short page is the end of the layer. Do NOT stop on a missing
        # `exceededTransferLimit`: that flag is an esriJSON field and the
        # GeoJSON responses these layers serve never carry it, so trusting it
        # read the first 1,000 of 1,915 truck parking records and reported
        # success. Length is the signal that survives both formats.
        if len(batch) < PAGE_SIZE:
            break
        offset += len(batch)

    return {
        "type": "FeatureCollection",
        "ff_source": {
            "kind": "read",
            "layer": slug,
            "title": layer.title,
            "url": layer.url,
            "about": layer.about,
            "license": NTAD_LICENSE,
            "acknowledgment": layer.acknowledgment,
            "accessed": date.today().isoformat(),
            "features": len(features),
        },
        "features": features,
    }


def _read_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
                return json.loads(response.read().decode("utf-8"))
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_error = exc
            if attempt == RETRIES - 1:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"unable to fetch NTAD layer {url}") from last_error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--layer", choices=sorted(LAYERS), default="truck_parking")
    parser.add_argument(
        "--refresh", action="store_true", help="Re-read BTS even if a snapshot exists."
    )
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--stats", action="store_true", help="Summarise by state.")
    args = parser.parse_args(argv)

    payload = load(args.layer, refresh=args.refresh, cache_dir=args.cache_dir)
    src = payload.get("ff_source", {})
    print(f"{src.get('title', args.layer)}: {len(payload['features'])} features")
    print(f"  snapshot: {snapshot_path(args.layer, args.cache_dir)}")
    print(f"  accessed: {src.get('accessed', 'unknown')}  ({src.get('kind', '?')})")
    print(f"  licence:  {src.get('license', 'unknown')}")

    if args.stats:
        by_state: dict[str, int] = {}
        for feature in payload["features"]:
            state = str((feature.get("properties") or {}).get("state") or "?").strip()
            by_state[state] = by_state.get(state, 0) + 1
        for state, count in sorted(by_state.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {state:<24} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
