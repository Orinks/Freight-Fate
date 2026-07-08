"""Map inventory: a plain, screen-reader-friendly list of every city (freight
node) and every real named checkpoint on the map.

Companion to tools/map_stats.py (which reports counts). This one writes the
actual lists: the cities you can dispatch to and from, grouped by region, and
the checkpoints you drive past, grouped by the leg they sit on and ordered by
mile marker. Placeholder checkpoints are left out -- only real named places
show, one per line, no tables.

Read-only. Run any time:
    uv run python tools/map_inventory.py                  # writes map_inventory.txt
    uv run python tools/map_inventory.py --out other.txt  # custom path
    uv run python tools/map_inventory.py --print          # also echo to stdout
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
PLACEHOLDER_MARK = "corridor between"

# Compact offline map of postal code -> full state name, so the inventory reads
# naturally aloud ("Atlanta, Georgia"). Checkpoints already carry full names.
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
    "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


def _is_real_checkpoint(cp: dict[str, Any]) -> bool:
    return PLACEHOLDER_MARK not in str(cp.get("name", ""))


def _pretty_region(region: str) -> str:
    return region.replace("_", " ").title()


def _city_name(key: str, city: dict[str, Any]) -> str:
    """Human-readable 'City, State' for a city node."""
    name = city.get("spoken_city") or key
    state = city.get("state", "")
    full = STATE_NAMES.get(state, state)
    return f"{name}, {full}" if full else name


def build_inventory(data: dict[str, Any]) -> str:
    cities = data.get("cities", {})
    legs = data.get("legs", [])

    # --- Cities, grouped by region, alphabetical within region ---
    by_region: dict[str, list[str]] = defaultdict(list)
    for key, city in cities.items():
        by_region[str(city.get("region", "unknown"))].append(_city_name(key, city))

    city_lines: list[str] = []
    for region in sorted(by_region):
        names = sorted(by_region[region])
        city_lines.append(f"{_pretty_region(region)} ({len(names)}):")
        city_lines += [f"  {n}" for n in names]
        city_lines.append("")

    # --- Checkpoints, grouped by leg, ordered by mile marker ---
    def endpoint(slug: str) -> str:
        city = cities.get(slug)
        return city.get("spoken_city", slug) if city else slug

    cp_blocks: list[tuple[str, list[str]]] = []
    total_cps = 0
    for leg in legs:
        reals = [c for c in leg.get("corridor", {}).get("checkpoints", []) if _is_real_checkpoint(c)]
        if not reals:
            continue
        reals.sort(key=lambda c: float(c.get("at_mi", 0) or 0))
        total_cps += len(reals)
        header = f"{endpoint(leg.get('from',''))} -> {endpoint(leg.get('to',''))}"
        highway = leg.get("highway")
        if highway:
            header += f" ({highway})"
        rows = []
        for c in reals:
            at = c.get("at_mi")
            where = f"at {float(at):.0f} mi: " if at is not None else ""
            state = c.get("state")
            tail = f" ({state})" if state else ""
            rows.append(f"  {where}{c.get('name','')}{tail}")
        cp_blocks.append((header, rows))
    cp_blocks.sort(key=lambda b: b[0])

    cp_lines: list[str] = []
    for header, rows in cp_blocks:
        cp_lines.append(header)
        cp_lines += rows
        cp_lines.append("")

    out = [
        "FREIGHT FATE MAP INVENTORY",
        "==========================",
        f"Cities (freight nodes): {len(cities)}",
        f"Real named checkpoints: {total_cps}",
        f"Legs carrying at least one named checkpoint: {len(cp_blocks)}",
        "",
        "",
        "================================================",
        f"CITIES -- {len(cities)} places you can pick up and deliver freight",
        "================================================",
        "Grouped by region, alphabetical within each region.",
        "",
    ]
    out += city_lines
    out += [
        "",
        "================================================",
        f"CHECKPOINTS -- {total_cps} named places you drive past",
        "================================================",
        "Grouped by the leg they sit on, in mile order along the drive.",
        "",
    ]
    out += cp_lines
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a list of every city and checkpoint on the map.")
    parser.add_argument("--out", default=str(ROOT / "map_inventory.txt"), help="Output file path.")
    parser.add_argument("--print", action="store_true", dest="echo", help="Also echo to stdout.")
    args = parser.parse_args(argv)
    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    text = build_inventory(data)
    Path(args.out).write_text(text, encoding="utf-8")
    if args.echo:
        print(text)
    print(f"Wrote inventory to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
