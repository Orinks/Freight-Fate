r"""Drop rows for facilities the world no longer has.

The endpoint, local-approach and facility-approach layers are keyed by
facility id and merged in place, so a facility the world stops generating
leaves its row behind. A record describing a place that does not exist is the
same blur this data works to avoid, and it skews every coverage count that
reads these files.

Example:
    uv run python tools/prune_retired_facility_rows.py --write
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from ffworld.world import get_world

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TOOLS = Path(__file__).resolve().parent
LAYERS = (
    (DATA / "facility_endpoints.json", "endpoints", "", "build_facility_endpoints"),
    (DATA / "local_approaches.json", "approaches", "facility:", "build_local_approaches"),
    (DATA / "facility_approaches.json", "approaches", "", "build_facility_approaches"),
    (DATA / "local_geometry.json", "geometries", "facility:", "build_local_geometry"),
)


def coverage_of(builder: str, rows: dict) -> dict:
    """The layer's own coverage summary, recomputed over what is left.

    A count that still describes the rows a prune removed is the same untruth
    as a row for a facility that does not exist.
    """
    spec = importlib.util.spec_from_file_location(builder, TOOLS / f"{builder}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[builder] = module
    spec.loader.exec_module(module)
    return module.coverage_summary(rows)


def live_facility_ids() -> set[str]:
    world = get_world()
    return {location.id for city in world.cities.values() for location in city.locations}


def prune(path: Path, section: str, prefix: str, builder: str, live: set[str], write: bool) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload[section]
    retired = [
        key
        for key in rows
        if (key.startswith(prefix) if prefix else True) and key.removeprefix(prefix) not in live
    ]
    for key in retired:
        del rows[key]
    print(f"{path.name}: {len(retired)} retired rows, {len(rows)} left")
    if retired:
        payload["coverage"] = coverage_of(builder, rows)
    if write and retired:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return len(retired)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    live = live_facility_ids()
    print(f"{len(live)} facilities in the world")
    for path, section, prefix, builder in LAYERS:
        prune(path, section, prefix, builder, live, args.write)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
