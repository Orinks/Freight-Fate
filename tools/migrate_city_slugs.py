"""One-shot migration: rekey ``world.json`` cities to stable slug keys.

The city dict key doubles as the spoken city name today, which breaks the
moment two cities share a name (Jackson MS vs Jackson TN) or the map leaves
the US. This transform separates identity from speech:

- key: ``{city}_{state}_{country}`` slug (``jackson_ms_us``), never spoken
- speech: each city keeps ``spoken_city`` (the old key) plus 2-letter
  ``state``/``country`` codes; a top-level ``geo`` table maps codes to spoken
  names ("MS" -> "Mississippi") so the game composes "Jackson, Mississippi"
  on demand
- every leg ``from``/``to`` is rewritten to the new slugs

It also generates ``src/freight_fate/data/legacy_aliases.py``, a frozen map
of every pre-migration city name to its slug. Old saves store bare city
names and facility IDs derived from them; the runtime resolves both through
this map forever, so a future city that reuses a name (Jackson TN) can never
capture a legacy save that meant the original (Jackson MS).

Usage::

    uv run python tools/migrate_city_slugs.py            # rewrite in place
    uv run python tools/migrate_city_slugs.py --dry-run  # report only

Idempotence: refuses to run if any city already carries ``spoken_city``.
After running, regenerate the split tree: ``uv run python tools/index_world.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
ALIASES_PATH = ROOT / "src" / "freight_fate" / "data" / "legacy_aliases.py"

COUNTRY_NAMES = {"US": "United States"}

STATE_CODES = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}


def slugify(text: str) -> str:
    """Lowercase with non-alphanumeric runs collapsed to single underscores.

    "St. Louis" -> "st_louis", "Winston-Salem" -> "winston_salem".
    """
    out: list[str] = []
    pending = False
    for char in text.lower():
        if char.isalnum():
            if pending and out:
                out.append("_")
            out.append(char)
            pending = False
        else:
            pending = True
    return "".join(out)


def city_slug(name: str, state_code: str, country_code: str) -> str:
    return f"{slugify(name)}_{state_code.lower()}_{country_code.lower()}"


def migrate(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Return (migrated world data, old-name -> slug map)."""
    cities = data.get("cities", {})
    already = [name for name, c in cities.items() if "spoken_city" in c]
    if already:
        raise SystemExit(
            f"Refusing to migrate: {len(already)} cities already carry spoken_city "
            f"(first: {already[0]!r}). world.json looks migrated."
        )

    name_to_slug: dict[str, str] = {}
    new_cities: dict[str, Any] = {}
    for name, city in cities.items():
        state_name = str(city.get("state", "")).strip()
        if state_name not in STATE_CODES:
            raise SystemExit(f"City {name!r} has unknown state {state_name!r}")
        code = STATE_CODES[state_name]
        country = str(city.get("country", "US")).strip() or "US"
        # A few old keys were state-disambiguated inline ("Jackson, Michigan").
        # The slug now carries the state, so the spoken city drops the suffix;
        # anything else after a comma is unexpected and needs a human look.
        spoken = name
        if "," in name:
            base, _, suffix = name.rpartition(",")
            if suffix.strip() != state_name:
                raise SystemExit(
                    f"City {name!r} has a comma suffix that is not its state "
                    f"{state_name!r}; resolve by hand before migrating."
                )
            spoken = base.strip()
        slug = city_slug(spoken, code, country)
        if slug in new_cities:
            raise SystemExit(f"Slug collision: {slug!r} from {name!r}")
        name_to_slug[name] = slug
        rebuilt: dict[str, Any] = {
            "spoken_city": spoken,
            "state": code,
            "country": country,
        }
        for key, value in city.items():
            if key not in ("state", "country"):
                rebuilt[key] = value
        new_cities[slug] = rebuilt

    new_legs: list[dict[str, Any]] = []
    for leg in data.get("legs", []):
        for end in ("from", "to"):
            if leg[end] not in name_to_slug:
                raise SystemExit(f"Leg references unknown city {leg[end]!r}")
        rebuilt_leg = dict(leg)
        rebuilt_leg["from"] = name_to_slug[leg["from"]]
        rebuilt_leg["to"] = name_to_slug[leg["to"]]
        new_legs.append(rebuilt_leg)

    used_countries = sorted({str(c["country"]) for c in new_cities.values()})
    geo = {
        "countries": {
            code: {
                "name": COUNTRY_NAMES[code],
                "states": {v: k for k, v in sorted(STATE_CODES.items(), key=lambda i: i[1])},
            }
            for code in used_countries
        }
    }

    migrated = dict(data)
    migrated["geo"] = geo
    migrated["cities"] = new_cities
    migrated["legs"] = new_legs
    return migrated, name_to_slug


def render_aliases(name_to_slug: dict[str, str]) -> str:
    lines = [
        '"""Frozen legacy city aliases for pre-slug saves.',
        "",
        "Generated once by tools/migrate_city_slugs.py when the city keys moved",
        "from bare display names to stable slugs. Old saves persist the bare",
        "names (current city, trip city sequences, job origins) and facility IDs",
        "derived from them; the world resolves both through this map. Do not",
        "regenerate or extend it for new cities -- a future city reusing one of",
        "these names must not capture saves that meant the original.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "LEGACY_CITY_SLUGS: dict[str, str] = {",
    ]
    for name in sorted(name_to_slug):
        lines.append(f"    {name!r}: {name_to_slug[name]!r},")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rekey world.json cities to slugs.")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing.")
    args = parser.parse_args(argv)

    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    migrated, name_to_slug = migrate(data)

    states = sorted({c["state"] for c in migrated["cities"].values()})
    print(f"cities: {len(name_to_slug)}, legs: {len(migrated['legs'])}, states: {len(states)}")
    sample = next(iter(name_to_slug.items()))
    print(f"sample: {sample[0]!r} -> {sample[1]!r}")
    if args.dry_run:
        return 0

    WORLD_PATH.write_text(json.dumps(migrated, indent=2) + "\n", encoding="utf-8")
    ALIASES_PATH.write_text(render_aliases(name_to_slug), encoding="utf-8")
    print(f"Wrote {WORLD_PATH.relative_to(ROOT)} and {ALIASES_PATH.relative_to(ROOT)}.")
    print("Now run: uv run python tools/index_world.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
