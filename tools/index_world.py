"""Rebuild the indexed ``world_data/`` tree the runtime loads from the
editable ``world_source/`` tree the build tools edit.

The build-time route tools (``enrich_routes.py``, ``build_interchanges.py``)
read and write ``src/freight_fate/data/world_source/`` through
``tools/world_source.py``. The game loads
``src/freight_fate/data/world_data/`` via
``freight_fate.data.world_loader`` -- an index plus per-country
``cities.json``, per-state leg shards, and ``metadata.json``. This script
regenerates that tree from the source so the two never drift.

Usage::

    uv run python tools/index_world.py            # rewrite world_data/ from the source
    uv run python tools/index_world.py --check     # verify in sync (exit 1 if not)

The split follows ``world_data/index.json``: ``cities`` -> each country's
``cities.json`` (``{"cities": {...}}``), ``legs`` -> per-state shards under
the country's ``legs_dir`` (``legs/TX.json``, each ``{"legs": [...]}``), the
source's top-level ``geo`` lookup (state and country codes -> spoken names) ->
``world_data/geo.json``, and the top-level ``route_stop_data`` is merged into
each country's ``metadata.json``. A city is assigned to a country by its
``country`` field; when the index lists exactly one country every city and leg
belongs to it, so per-city tags are optional in single-country data.

Legs are sharded by the state of their ``from`` city and sorted within a
shard, the same rule ``tools/world_source.py`` files the source by, so both
trees stay reviewable and a one-leg edit rewrites one small file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from world_source import load_world, shard_key

ROOT = Path(__file__).resolve().parents[1]
WORLD_DATA_PATH = ROOT / "src" / "freight_fate" / "data" / "world_data"


def _dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2) + "\n"


def _country_of(city: dict[str, Any], default: str | None) -> str:
    code = str(city.get("country", "")).strip()
    if code:
        return code
    if default is None:
        raise SystemExit(
            "world.json cities need a 'country' field when world_data/index.json "
            "lists more than one country."
        )
    return default


def build_country_files(data: dict[str, Any], index: dict[str, Any]) -> dict[Path, str]:
    """The exact JSON text every world_data file should contain, keyed by path.

    Pure (no I/O) so both the writer and the ``--check`` verifier share one
    source of truth.
    """
    countries = index.get("countries")
    if not countries:
        raise SystemExit("world_data/index.json has no 'countries'")
    single = countries[0]["code"] if len(countries) == 1 else None

    by_country: dict[str, dict[str, Any]] = {
        c["code"]: {"cities": {}, "legs": []} for c in countries
    }
    for name, city in data.get("cities", {}).items():
        by_country[_country_of(city, single)]["cities"][name] = city
    for leg in data.get("legs", []):
        from_city = data["cities"].get(leg["from"], {})
        to_city = data["cities"].get(leg["to"], {})
        code = _country_of(from_city, single)
        if _country_of(to_city, single) != code:
            raise SystemExit(f"Cross-country leg {leg['from']}->{leg['to']} is not supported.")
        by_country[code]["legs"].append(leg)

    files: dict[Path, str] = {}
    if "geo" in data:
        files[WORLD_DATA_PATH / "geo.json"] = _dumps(data["geo"])
    for country in countries:
        code = country["code"]
        country_dir = WORLD_DATA_PATH / country["path"]
        cities_name = country.get("cities", "cities.json")
        files[country_dir / cities_name] = _dumps({"cities": by_country[code]["cities"]})

        legs_dir = country.get("legs_dir")
        if legs_dir:
            by_state: dict[str, list[dict[str, Any]]] = {}
            for leg in by_country[code]["legs"]:
                by_state.setdefault(shard_key(leg, data["cities"]), []).append(leg)
            for state, legs in by_state.items():
                legs.sort(key=lambda leg: (leg.get("from", ""), leg.get("to", "")))
                files[country_dir / legs_dir / f"{state}.json"] = _dumps({"legs": legs})
        else:
            legs_name = country.get("legs", "legs.json")
            files[country_dir / legs_name] = _dumps({"legs": by_country[code]["legs"]})
        # Merge route_stop_data into the country's metadata, preserving any other
        # metadata keys already on disk.
        metadata_path = country_dir / "metadata.json"
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if "route_stop_data" in data:
            metadata["route_stop_data"] = data["route_stop_data"]
        files[metadata_path] = _dumps(metadata)
    return files


def _stale_shards(index: dict[str, Any], files: dict[Path, str]) -> list[Path]:
    """Leg shards on disk that the source no longer produces.

    The loader globs the shard directory, so a shard left behind after its
    last leg moved away would keep feeding the game a leg that no longer
    exists in the source.
    """
    stale: list[Path] = []
    for country in index.get("countries", []):
        legs_dir = country.get("legs_dir")
        if not legs_dir:
            continue
        for path in (WORLD_DATA_PATH / country["path"] / legs_dir).glob("*.json"):
            if path not in files:
                stale.append(path)
    return sorted(stale)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate world_data/ from world.json.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify world_data/ matches world.json; exit 1 if it does not.",
    )
    args = parser.parse_args(argv)

    data = load_world()
    index = json.loads((WORLD_DATA_PATH / "index.json").read_text(encoding="utf-8"))
    files = build_country_files(data, index)
    stale = _stale_shards(index, files)

    if args.check:
        drifted = [
            path
            for path, text in files.items()
            if not path.exists() or path.read_text(encoding="utf-8") != text
        ]
        if drifted or stale:
            print(
                "world_data/ is out of sync with world_source/; run "
                "`uv run python tools/index_world.py`:"
            )
            for path in drifted + stale:
                print(f"  {path.relative_to(ROOT)}")
            return 1
        print("world_data/ is in sync with world_source/.")
        return 0

    written = 0
    for path, text in files.items():
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written += 1
    for path in stale:
        path.unlink()
        written += 1
    print(f"Wrote {written} world_data file(s) from world_source/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
