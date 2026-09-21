r"""Write the list of cities whose freight market is a stand-in.

A city earns real facilities when at least one of its freight locations has an
OpenStreetMap endpoint that the freight-site screen accepts: the game then
sends the driver to a door that exists. A city with none has nothing surveyed
behind any of its facilities, and stamping it with four or more invented
warehouses is four lies where one would do.

Both runtimes need the list -- Rust because that is the game, Python because
the build tools read the world through the reference implementation -- so this
writes both, from the one source that can answer the question.

Run it after ``build_facility_endpoints`` and commit the result.

Example:
    uv run python tools/gen_stand_in_markets.py --write
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS = ROOT / "data" / "facility_endpoints.json"
OUT_RS = ROOT / "crates" / "ff-core" / "src" / "data" / "world_constants" / "stand_in_markets.rs"
OUT_PY = ROOT / "tools" / "ffworld" / "stand_in_markets.py"

WHY = (
    "Not one of these cities has a single facility whose endpoint the",
    "freight-site screen accepts, so nothing behind any of them was surveyed.",
    "They are stamped with ONE yard instead of the four-plus every other",
    "market gets: a town with no mapped freight is still a place a load can",
    "come from, and four invented warehouses there are four chances to hear a",
    "story the map cannot back (owner ruling, 2026-09-20 -- if it is real,",
    "bake it; if not, do not pretend).",
)


def stand_in_cities(endpoints: dict) -> list[str]:
    real: set[str] = set()
    every: set[str] = set()
    for row in endpoints["endpoints"].values():
        city = row.get("city", "")
        if not city:
            continue
        every.add(city)
        if (
            row.get("source_backed")
            and not row.get("fallback")
            and row.get("endpoint_screen") != "refused"
        ):
            real.add(city)
    return sorted(every - real)


def render_rs(cities: list[str]) -> str:
    why = "\n".join(f"//! {line}" for line in WHY)
    head = (
        "//! Cities whose freight market is a stand-in (generated;\n"
        "//! `tools/gen_stand_in_markets.py`).\n"
        "//!\n"
        f"{why}\n"
        "//!\n"
        "//! Regenerate after a facility-endpoint sweep; the count is reported\n"
        "//! in ROADMAP.md.\n\n"
        "pub const STAND_IN_MARKET_CITY_KEYS: &[&str] = &[\n"
    )
    body = "".join(f'    "{city}",\n' for city in cities)
    return f"{head}{body}];\n"


def render_py(cities: list[str]) -> str:
    why = "\n".join(WHY)
    head = (
        '"""Cities whose freight market is a stand-in (generated;\n'
        "``tools/gen_stand_in_markets.py``).\n\n"
        f"{why}\n\n"
        "The reference implementation's copy of the Rust\n"
        "``world_constants/stand_in_markets.rs``. The build tools read the world\n"
        "through this side, so the two have to agree or the data layers describe\n"
        "facilities the game does not create.\n"
        '"""\n\n'
        "STAND_IN_MARKET_CITY_KEYS = frozenset(\n"
        "    {\n"
    )
    body = "".join(f'        "{city}",\n' for city in cities)
    return f"{head}{body}    }}\n)\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoints", type=Path, default=ENDPOINTS)
    parser.add_argument("--output-rs", type=Path, default=OUT_RS)
    parser.add_argument("--output-py", type=Path, default=OUT_PY)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    endpoints = json.loads(args.endpoints.read_text(encoding="utf-8"))
    cities = stand_in_cities(endpoints)
    total = len({row.get("city", "") for row in endpoints["endpoints"].values()})
    print(f"{len(cities)} of {total} markets are stand-ins")
    if args.write:
        args.output_rs.write_text(render_rs(cities), encoding="utf-8")
        args.output_py.write_text(render_py(cities), encoding="utf-8")
        print(f"Wrote {args.output_rs}")
        print(f"Wrote {args.output_py}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
