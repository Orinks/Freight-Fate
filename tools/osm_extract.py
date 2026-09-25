"""Which OpenStreetMap snapshot the checked-in bakes were read from.

Every builder that reads the per-state Geofabrik extracts in
``~/.cache/freight-fate-osm/regions`` stamps this date into its source strings
and its layer meta, so "how old is the map" has an answer in the data itself.
Bump both constants when ``tools/fetch_state_extracts.py`` pulls a new set,
before re-running the builders; ``check_extracts`` refuses to bake a date
the extracts on disk do not carry.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# The day Geofabrik's extracts were cut (the ``-YYMMDD`` in the resolved
# download name), i.e. OpenStreetMap as of this date. Read from the manifest.
OSM_EXTRACT_DATE = "2026-09-23"
# The day the extracts were downloaded.
OSM_EXTRACT_ACCESSED = "2026-09-24"
MANIFEST_NAME = "extract-sources.json"


def extract_dates(cache_dir: Path) -> set[str]:
    """The cut dates the fetcher's manifest records for the extracts on disk."""
    manifest = json.loads((cache_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    dates = set()
    for entry in manifest.get("states", {}).values():
        match = re.search(r"-(\d{2})(\d{2})(\d{2})\.osm\.pbf$", entry.get("resolved_url", ""))
        dates.add(f"20{match[1]}-{match[2]}-{match[3]}" if match else "unknown")
    return dates


def check_extracts(cache_dir: Path) -> None:
    """Stop a bake that would stamp a date the extracts on disk do not carry."""
    dates = extract_dates(cache_dir)
    if dates != {OSM_EXTRACT_DATE}:
        raise SystemExit(
            f"{cache_dir / MANIFEST_NAME} records extracts of {sorted(dates)}, but "
            f"tools/osm_extract.py says {OSM_EXTRACT_DATE}. Bump OSM_EXTRACT_DATE "
            "after a fetch, or fetch the extracts it names."
        )


def meta() -> dict[str, Any]:
    """The layer-meta record: read, from the fetcher's manifest."""
    return {
        "date": OSM_EXTRACT_DATE,
        "accessed": OSM_EXTRACT_ACCESSED,
        "source": (
            "read: Geofabrik North America / US state extracts "
            "(https://download.geofabrik.de/north-america/us), OpenStreetMap "
            f"data as of {OSM_EXTRACT_DATE}; (c) OpenStreetMap contributors, ODbL 1.0"
        ),
    }
