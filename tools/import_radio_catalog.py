"""Convert PR #150's automated station catalog into the imported dial tier.

The curated catalog (``radio_catalog.json``) is hand-maintained and always
wins. This tool layers the automated Radio Browser x Wikidata join built by
CatalystForChaos in PR #150 underneath it as ``radio_imported.json``: real
terrestrial broadcast stations with transmitter coordinates, receivable only
near their transmitter, every one gated behind the real-streams switch and
hidden in streamer-safe mode.

Only the ``local`` tier of the source file is taken. The web tier (5,000+
everywhere-available streams) would swamp the dial without adding any sense
of place, and the satellite tier duplicates the curated AFN lineup.

An imported station whose call sign matches a curated station's call sign is
dropped here (and again at load time, in case the curated file grows between
rebuilds): one call sign is one place on the dial, and the curated entry
carries data this join cannot supply.

Run from the repository root::

    uv run python tools/import_radio_catalog.py
    uv run python tools/import_radio_catalog.py --check

The input is the ``stations.json`` from PR #150, cached at
``data/radio-cache/pr150_stations.json`` (gitignored; re-fetch it from the PR
branch with ``git show pr150:src/freight_fate/data/radio/stations.json``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "radio-cache" / "pr150_stations.json"
CURATED_PATH = ROOT / "src" / "freight_fate" / "data" / "radio_catalog.json"
DEFAULT_OUTPUT = ROOT / "src" / "freight_fate" / "data" / "radio_imported.json"

# Spoken in station lists and status lines; player language, no tooling names.
IMPORTED_SOURCE_TEXT = "community radio directory"


def call_sign_base(call_sign: str) -> str:
    """The call sign without a -FM/-AM suffix: WNYC-FM and WNYC are one station."""
    return call_sign.split("-")[0].strip().upper()


def curated_call_signs(curated: dict) -> set[str]:
    return {call_sign_base(row.get("call_sign", "")) for row in curated["stations"]}


def convert_station(row: dict) -> dict:
    """One PR #150 local-tier record in the curated catalog's schema."""
    band = row["band"]
    tags = (row.get("tags") or "").strip()
    station = {
        "id": f"rb-{row['id']}",
        # Spoken as letters either way, but a dash in the middle is read as
        # the word "dash" by some screen readers.
        "call_sign": row["call_sign"].replace("-", " "),
        "name": row["name"],
        "format": tags or f"{band} radio",
        "source": IMPORTED_SOURCE_TEXT,
        "source_type": "imported",
        "station_type": "imported",
        "stream_url": row["url"],
        "stream_format": (row.get("codec") or "").lower(),
        "lat": row["lat"],
        "lon": row["lon"],
        "range_miles": row["radius_mi"],
        # The licensing of a directory stream is unknown, so imported
        # stations ride the same gates as every real stream: hidden in
        # streamer-safe mode, off until real streams are switched on.
        "safe_for_streaming": False,
        "real_stream": True,
        "supported": True,
    }
    if band == "FM":
        station["frequency_mhz"] = float(row["frequency"])
    return station


def build(source: dict, curated: dict) -> dict:
    reserved = curated_call_signs(curated)
    stations = []
    dropped = 0
    for row in source["local"]:
        if call_sign_base(row["call_sign"]) in reserved:
            dropped += 1
            continue
        stations.append(convert_station(row))
    stations.sort(key=lambda s: (s["call_sign"], s["id"]))
    return {
        "schema": 1,
        "notes": (
            "Automated tier under the curated radio_catalog.json. Built by "
            "tools/import_radio_catalog.py from the PR #150 catalog "
            "(CatalystForChaos): Radio Browser stream URLs joined to Wikidata "
            "transmitter coordinates (CC0) on FCC call sign. Coverage radii "
            "are that catalog's per-band defaults, not FCC contours. Curated "
            "call signs win: collisions are dropped at build and load time."
        ),
        "counts": {"stations": len(stations), "dropped_curated_collisions": dropped},
        "stations": stations,
    }


def render(catalog: dict) -> str:
    return json.dumps(catalog, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--curated", type=Path, default=CURATED_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the checked-in file matches a rebuild; write nothing",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        parser.error(f"missing input: {args.input}\nSee this tool's docstring for the source.")

    source = json.loads(args.input.read_text(encoding="utf-8"))
    curated = json.loads(args.curated.read_text(encoding="utf-8"))
    text = render(build(source, curated))

    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != text:
            print(
                f"Out of date: {args.output}\nRe-run tools/import_radio_catalog.py", file=sys.stderr
            )
            return 1
        print(f"{args.output.name} is up to date")
        return 0

    args.output.write_text(text, encoding="utf-8")
    counts = json.loads(text)["counts"]
    print(f"Wrote {args.output} ({counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
