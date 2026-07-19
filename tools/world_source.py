"""Load and save the editable world source, sharded per state.

The build tools used to read and write a single 60 MB
``src/freight_fate/data/world.json``. That file (and the runtime
``world_data/us/legs.json`` it generates) had grown past GitHub's 50 MB
warning line and was heading for the 100 MB hard limit, and every data
sweep committed a 60 MB blob no reviewer could read. The source is now a
tree of per-state shards:

.. code-block:: text

    src/freight_fate/data/world_source/
      meta.json         # every top-level key that is not cities or legs
      cities.json       # {"cities": {...}} -- small enough to stay whole
      legs/TX.json      # {"legs": [...]} for legs starting in Texas
      legs/CA.json
      ...

``load_world()`` returns the same merged dict the tools have always seen,
so a tool migrates by swapping its ``json.loads(WORLD_PATH.read_text())``
for ``load_world()`` and its ``WORLD_PATH.write_text(json.dumps(...))``
for ``save_world(data)``. Nothing else about a tool changes.

A leg is filed under the state of its ``from`` city, so editing one leg
rewrites one small file instead of the monolith. Both shard files and the
leg order inside them are sorted, so the same data always produces the
same bytes -- the deterministic-and-offline rule the map data lives by.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORLD_SOURCE_PATH = ROOT / "src" / "freight_fate" / "data" / "world_source"

# Legs whose 'from' city has no state (or an unknown city) land here rather
# than failing the save -- an honest bucket beats a crash mid-sweep.
UNSHARDED = "_unsharded"


def _dumps(payload: Any) -> str:
    """The repo-canonical JSON text: indent 2, escaped non-ASCII, trailing newline."""
    return json.dumps(payload, indent=2) + "\n"


def shard_key(leg: dict[str, Any], cities: dict[str, Any]) -> str:
    """Which shard a leg belongs in: the state of the city it starts from."""
    state = str(cities.get(leg.get("from"), {}).get("state", "")).strip()
    return state or UNSHARDED


def load_world(root: Path = WORLD_SOURCE_PATH) -> dict[str, Any]:
    """Return the merged world source, shaped exactly like the old world.json."""
    data: dict[str, Any] = json.loads((root / "meta.json").read_text(encoding="utf-8"))
    data["cities"] = json.loads((root / "cities.json").read_text(encoding="utf-8"))["cities"]

    legs: list[dict[str, Any]] = []
    for shard in sorted((root / "legs").glob("*.json")):
        legs.extend(json.loads(shard.read_text(encoding="utf-8"))["legs"])
    data["legs"] = legs
    return data


def build_source_files(data: dict[str, Any], root: Path = WORLD_SOURCE_PATH) -> dict[Path, str]:
    """The exact JSON text every source file should hold, keyed by path.

    Pure (no I/O) so the writer and any verifier share one source of truth.
    """
    cities = data.get("cities", {})
    meta = {k: v for k, v in data.items() if k not in ("cities", "legs")}

    by_state: dict[str, list[dict[str, Any]]] = {}
    for leg in data.get("legs", []):
        by_state.setdefault(shard_key(leg, cities), []).append(leg)

    files: dict[Path, str] = {
        root / "meta.json": _dumps(meta),
        root / "cities.json": _dumps({"cities": cities}),
    }
    for state, legs in by_state.items():
        legs.sort(key=lambda leg: (leg.get("from", ""), leg.get("to", "")))
        files[root / "legs" / f"{state}.json"] = _dumps({"legs": legs})
    return files


def save_world(data: dict[str, Any], root: Path = WORLD_SOURCE_PATH) -> int:
    """Write the world source back out as shards; return the file count written.

    Only changed files are touched, so a one-leg edit leaves the other 48
    state shards' mtimes -- and their git diffs -- alone. Shards that no
    longer have any legs are removed so a renamed state cannot linger.
    """
    files = build_source_files(data, root)
    (root / "legs").mkdir(parents=True, exist_ok=True)

    written = 0
    for path, text in files.items():
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            written += 1
    for stale in (root / "legs").glob("*.json"):
        if stale not in files:
            stale.unlink()
            written += 1
    return written
