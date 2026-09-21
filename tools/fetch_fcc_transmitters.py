#!/usr/bin/env python3
"""Cache FCC licensed transmitter sites, keyed by call sign.

The imported terrestrial tier places stations from a Wikidata join, which
only knows the stations Wikidata happens to cover, and gives every band the
same default coverage radius. The FCC licenses every US broadcast
transmitter and publishes where each one stands, how much power it runs,
and how high above average terrain it sits -- which is the real input to
where a truck can hear it.

This fetches the FCC's own FM and AM query output, one state at a time,
and caches it as JSON for the catalog builders. Public-domain US
government data. It is a *cache builder*: the game never reads this file,
and the fetch is never part of a test or a build.

Run from the repository root::

    uv run python tools/fetch_fcc_transmitters.py
    uv run python tools/fetch_fcc_transmitters.py --states NC RI

Output lands in ``data/radio-cache/`` (gitignored) alongside the other
catalog inputs. Re-run it when the licensed record moves; it is slow and
polite by design, one state at a time.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "radio-cache"

FM_QUERY = "https://transition.fcc.gov/fcc-bin/fmq"
AM_QUERY = "https://transition.fcc.gov/fcc-bin/amq"
# No URL in here. The FCC's front end answers 403 to a user agent carrying
# one, which reads as the query being broken rather than refused.
USER_AGENT = "FreightFate/1.9 (catalog build)"

# 50 states plus DC. Territories are outside the drivable world.
STATES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]

# Only licensed facilities: construction permits and applications describe
# transmitters that do not exist yet, and a station a driver cannot hear is
# worse than one that is missing.
LICENSED = {"LIC"}

_US_CALL_SIGN = re.compile(r"[KW][A-Z0-9]{2,5}")

# Column positions in the query's pipe-delimited "list=4" output. The two
# services share a layout; the sample row that pinned these down is in the
# tool's tests.
CALL, SERVICE, STATUS = 1, 3, 9
COMMUNITY, COMMUNITY_STATE = 10, 11
ERP_KW, HAAT_M, FACILITY_ID = 14, 16, 18
LAT_DIR, LAT_D, LAT_M, LAT_S = 19, 20, 21, 22
LON_DIR, LON_D, LON_M, LON_S = 23, 24, 25, 26
FREQUENCY = 2


def _dms(degrees: str, minutes: str, seconds: str, direction: str) -> float | None:
    """Decimal degrees from the query's degrees/minutes/seconds columns."""
    try:
        value = abs(float(degrees)) + float(minutes) / 60.0 + float(seconds) / 3600.0
    except ValueError:
        return None
    if direction.upper() in {"S", "W"}:
        value = -value
    return round(value, 5)


def _number(raw: str) -> float | None:
    """A leading number out of a column like ``84.    kW`` or ``322.0``."""
    token = raw.strip().split()[0] if raw.strip() else ""
    try:
        return float(token)
    except ValueError:
        return None


def parse_row(line: str) -> dict | None:
    """One licensed transmitter, or None for anything else in the output."""
    parts = line.split("|")
    if len(parts) <= LON_S:
        return None
    fields = [part.strip() for part in parts]
    if fields[STATUS] not in LICENSED or not _US_CALL_SIGN.fullmatch(fields[CALL].upper()):
        # The query carries former call signs with a "D" prefix (DKMWY,
        # DK217EK) for facilities whose licence has been deleted. A real US
        # broadcast call sign starts with K or W and nothing else.
        return None
    lat = _dms(fields[LAT_D], fields[LAT_M], fields[LAT_S], fields[LAT_DIR])
    lon = _dms(fields[LON_D], fields[LON_M], fields[LON_S], fields[LON_DIR])
    if lat is None or lon is None or (lat == 0 and lon == 0):
        return None
    # The bounding rows the FCC carries for maximum-facilities studies use
    # impossible coordinates; a real US transmitter is not at 90 degrees.
    if not (17.0 < lat < 72.0) or not (-180.0 < lon < -64.0):
        return None
    return {
        "call_sign": fields[CALL].upper(),
        "service": fields[SERVICE].upper(),
        "frequency": fields[FREQUENCY],
        "community": fields[COMMUNITY].title(),
        "state": fields[COMMUNITY_STATE].upper(),
        "facility_id": fields[FACILITY_ID],
        "lat": lat,
        "lon": lon,
        "erp_kw": _number(fields[ERP_KW]),
        "haat_m": _number(fields[HAAT_M]),
    }


def fetch_state(state: str, service: str, timeout: float) -> list[dict]:
    """Every licensed transmitter the query reports for one state."""
    if service == "FM":
        url = (
            f"{FM_QUERY}?state={state}&call=&city=&arn=&serv=&vac=&freq=0.0&fre2=107.9"
            "&facid=&class=&list=4&dist=&dlat2=&mlat2=&slat2=&dlon2=&mlon2=&slon2=&size=9"
        )
    else:
        url = (
            f"{AM_QUERY}?state={state}&call=&city=&arn=&serv=&freq=0&fre2=1700"
            "&facid=&class=&list=4&dist=&dlat2=&mlat2=&slat2=&dlon2=&mlon2=&slon2=&size=9"
        )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("latin-1")
    rows = []
    for line in text.splitlines():
        row = parse_row(line)
        if row:
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", nargs="*", default=STATES)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--pause", type=float, default=1.0, help="seconds between queries")
    parser.add_argument("--output", type=Path, default=CACHE_DIR / "fcc_transmitters.json")
    args = parser.parse_args(argv)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # One entry per call sign. A station with several licensed records (an
    # AM with day and night patterns, an FM with an auxiliary site) keeps
    # the strongest, which is the one a driver hears furthest out.
    best: dict[str, dict] = {}
    for state in args.states:
        found = 0
        for service in ("FM", "AM"):
            try:
                rows = fetch_state(state, service, args.timeout)
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                print(f"  {state} {service}: FAILED ({error})", file=sys.stderr)
                continue
            for row in rows:
                key = row["call_sign"]
                current = best.get(key)
                if current is None or (row["erp_kw"] or 0) > (current["erp_kw"] or 0):
                    best[key] = row
                found += 1
            time.sleep(args.pause)
        print(f"{state}: {found} licensed records ({len(best)} call signs so far)", flush=True)

    payload = {
        "schema": 1,
        "notes": (
            "Licensed US broadcast transmitter sites from the FCC FM and AM "
            "queries (public domain). Built by tools/fetch_fcc_transmitters.py. "
            "One row per call sign, keeping the highest-ERP licensed record. "
            "Coordinates are the transmitter, not the studio or the city."
        ),
        "counts": {"call_signs": len(best)},
        "transmitters": dict(sorted(best.items())),
    }
    args.output.write_text(
        json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output} ({len(best)} call signs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
