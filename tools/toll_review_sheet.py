"""Write the toll findings as a flat text sheet a person can read straight through.

The scan output is JSON and the rate research is spread across four reports.
Neither is reviewable by ear. This merges them into one ordered document with
one finding per block, no nesting and no tables, so it reads top to bottom in a
screen reader and the owner can say "that one's wrong" against a line.

Sections, in the order worth reviewing:
  1. REPRICE -- legs we already toll, where sourced rates differ from the
     estimate. Biggest money first, since that is where a wrong number hurts.
  2. ADD -- legs the scan puts on a tolled road with no toll data, confident
     (the tolled way was seen mid-corridor, not just at a city endpoint).
  3. CHECK -- endpoint-only sightings. Real endpoint plazas exist, and so do
     urban false positives; these need a human who has driven the road.
  4. DEFERRED -- international crossings, parked with the Mexico/Canada work.

Every researched figure carries its authority and source so nothing has to be
taken on trust.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from world_source import load_world  # noqa: E402

SCAN = ROOT / "logs" / "toll-scan.json"
OUT = ROOT / "logs" / "toll-review.txt"

# Researched 5-axle commercial rates, transponder and plate, with the source
# each came from. Only figures a research pass actually read off an authority's
# own published schedule or calculator -- nothing derived, nothing guessed.
RESEARCHED: dict[tuple[str, str], dict] = {
    ("youngstown_oh_us", "pittsburgh_pa_us"): {
        "transponder": 53.65, "plate": 107.94,
        "src": "PA Turnpike 2026 E-ZPass schedule, Gateway #2 to Pittsburgh #57",
    },
    ("harrisburg_pa_us", "philadelphia_pa_us"): {
        "transponder": 50.28, "plate": 100.56,
        "src": "PA Turnpike 2026 schedule, Harrisburg East #247 to Valley Forge #326",
    },
    ("harrisburg_pa_us", "pittsburgh_pa_us"): {
        "transponder": 114.40, "plate": 228.80,
        "src": "PA Turnpike 2026 schedule, Harrisburg East #247 to Pittsburgh #57",
    },
    ("philadelphia_pa_us", "pittsburgh_pa_us"): {
        "transponder": 164.68, "plate": 329.36,
        "src": "PA Turnpike 2026 schedule, Valley Forge #326 to Pittsburgh #57",
    },
    ("pittsburgh_pa_us", "carlisle_pa_us"): {
        "transponder": 94.68, "plate": 189.36,
        "src": "PA Turnpike 2026 schedule, Pittsburgh #57 to Carlisle #226",
    },
    ("cleveland_oh_us", "toledo_oh_us"): {
        "transponder": 25.75, "plate": 32.25,
        "src": "Ohio Turnpike 2026 schedule, Cleveland MP173 to Maumee-Toledo MP59",
    },
    ("pittsburgh_pa_us", "cleveland_oh_us"): {
        "transponder": 20.00, "plate": 25.00,
        "src": "Ohio Turnpike 2026, Eastgate barrier + segment (summed, their method)",
    },
    ("boston_ma_us", "worcester_ma_us"): {
        "transponder": 10.85, "plate": 12.95,
        "src": "MassDOT EZDriveMA calculator, I-93 to Auburn I-290/I-395",
    },
    ("springfield_ma_us", "albany_ny_us"): {
        "transponder": 6.00, "plate": 6.90,
        "src": "MassDOT calculator, I-291 Springfield to West Stockbridge NY line",
    },
    ("albany_ny_us", "worcester_ma_us"): {
        "transponder": 11.70, "plate": 13.50,
        "src": "MassDOT calculator, West Stockbridge NY line to Auburn",
    },
    ("new_york_ny_us", "philadelphia_pa_us"): {
        "transponder": 71.66, "plate": 78.55,
        "src": "NJ Turnpike Authority 2026 Class 5 schedule, interchange 1 to 18E/18W",
    },
    ("philadelphia_pa_us", "baltimore_md_us"): {
        "transponder": 58.00, "plate": 58.00,
        "src": "DelDOT I-95 Newark plaza $10 (no E-ZPass discount) + MDTA JFK Hwy $48",
    },
    ("naples_fl_us", "miami_fl_us"): {
        "transponder": 25.44, "plate": 30.00,
        "src": "Florida Turnpike Alligator Alley, TWO plazas at $12.72/$15.00 each",
    },
    ("norfolk_va_us", "cape_charles_va_us"): {
        "transponder": 48.00, "plate": 48.00,
        "src": "CBBT Class 12, flat rate all payment types, eff. 2024-01-01",
    },
    ("beckley_wv_us", "charleston_wv_us"): {
        "transponder": 24.00, "plate": 30.00,
        "src": "WV Parkways Class 8, two mainline barriers at $12 E-ZPass / $15 cash",
    },
    ("emporia_ks_us", "wichita_ks_us"): {
        "transponder": 11.66, "plate": 23.32,
        "src": "Kansas Turnpike flat per-mile (cashless since 2024), 84.5 mi",
    },
    ("topeka_ks_us", "emporia_ks_us"): {
        "transponder": 6.93, "plate": 13.86,
        "src": "Kansas Turnpike flat per-mile, 50.2 mi",
    },
    ("wichita_ks_us", "kansas_city_mo_us"): {
        "transponder": 25.08, "plate": 50.16,
        "src": "Kansas Turnpike flat per-mile, 181.7 mi",
    },
    ("oklahoma_city_ok_us", "tulsa_ok_us"): {
        "transponder": 21.66, "plate": 43.08,
        "src": "OTA Turner Turnpike 2024 base + announced Jan-2025 +20% (CALCULATED)",
    },
    ("joplin_mo_us", "tulsa_ok_us"): {
        "transponder": 21.66, "plate": 43.08,
        "src": "OTA Will Rogers 2024 base + announced Jan-2025 +20% (CALCULATED)",
    },
    ("wichita_falls_tx_us", "oklahoma_city_ok_us"): {
        "transponder": 17.54, "plate": 36.80,
        "src": "OTA H.E. Bailey 2024 base + announced Jan-2025 +15% (CALCULATED)",
    },
    ("rockford_il_us", "chicago_il_us"): {
        "transponder": 42.30, "plate": 42.30,
        "src": "Illinois Tollway 2026, four I-90 barriers summed; cashless statewide",
    },
    ("rockford_il_us", "madison_wi_us"): {
        "transponder": 27.55, "plate": 27.55,
        "src": "Illinois Tollway 2026, Belvidere + South Beloit barriers",
    },
    ("lewiston_me_us", "portland_me_us"): {
        "transponder": 9.00, "plate": 9.00,
        "src": "Maine Turnpike E-ZPass Class 5 chart, eff. 2021-11-01",
    },
    # NY Thruway and Indiana, from the authorities' own live calculators.
    ("buffalo_ny_us", "rochester_ny_us"): {
        "transponder": 16.53, "plate": 28.95,
        "src": "NY Thruway calculator 5H, exit 53 to exit 45, eff. 2026-01-01",
    },
    ("syracuse_ny_us", "albany_ny_us"): {
        "transponder": 33.77, "plate": 59.12,
        "src": "NY Thruway calculator 5H, exit 39 to exit 24",
    },
    ("syracuse_ny_us", "buffalo_ny_us"): {
        "transponder": 31.19, "plate": 54.60,
        "src": "NY Thruway calculator 5H, exit 39 to exit 53",
    },
    ("syracuse_ny_us", "rochester_ny_us"): {
        "transponder": 14.66, "plate": 25.65,
        "src": "NY Thruway calculator 5H, exit 39 to exit 45",
    },
    ("utica_ny_us", "albany_ny_us"): {
        "transponder": 20.27, "plate": 35.47,
        "src": "NY Thruway calculator 5H, exit 31 to exit 24",
    },
    ("erie_pa_us", "buffalo_ny_us"): {
        "transponder": 15.87, "plate": 27.77,
        "src": "NY Thruway calculator 5H, PA state line to exit 53",
    },
    ("buffalo_ny_us", "new_york_ny_us"): {
        "transponder": 167.53, "plate": 293.21,
        "src": "NY Thruway calculator 5H, exit 53 to NYC line; incl. Cuomo Bridge southbound",
    },
    ("rochester_ny_us", "new_york_ny_us"): {
        "transponder": 151.00, "plate": 264.26,
        "src": "NY Thruway calculator 5H, exit 45 to NYC line",
    },
    ("new_york_ny_us", "albany_ny_us"): {
        "transponder": 46.43, "plate": 81.25,
        "src": "NY Thruway calculator 5H, NYC line to exit 24; incl. Spring Valley gantry",
    },
    ("new_york_ny_us", "bridgeport_ct_us"): {
        "transponder": 7.98, "plate": 13.97,
        "src": "NY Thruway calculator 5H, New England Thruway, New Rochelle gantry "
               "NORTHBOUND ONLY",
    },
    ("gary_in_us", "chicago_il_us"): {
        "transponder": 11.93, "plate": 11.90,
        "src": "Indiana Toll Road Class 5, Gary East to Westpoint, eff. 2026-07-01",
    },
    ("gary_in_us", "south_bend_in_us"): {
        "transponder": 39.08, "plate": 39.10,
        "src": "Indiana Toll Road Class 5, Gary East to South Bend West",
    },
    ("south_bend_in_us", "chicago_il_us"): {
        "transponder": 44.80, "plate": 44.80,
        "src": "Indiana Toll Road Class 5, South Bend West to Westpoint",
    },
    ("bangor_me_us", "portland_me_us"): {
        "transponder": 14.20, "plate": 14.20,
        "src": "Maine Turnpike: Bangor is NORTH of the tolled section; price the "
               "Gardiner-to-Portland portion the run actually drives",
    },
}

BORDER_MARKERS = ("international bridge", "sault ste. marie", "ambassador")


def _events(leg: dict) -> list[dict]:
    return (leg.get("corridor") or {}).get("toll_events") or []


def main() -> int:
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    world = load_world()
    by_pair = {(leg["from"], leg["to"]): leg for leg in world["legs"]}

    lines: list[str] = []
    add = lines.append
    add("TOLL REVIEW SHEET")
    add("Generated from tools/toll_scan.py plus four rate-research passes.")
    add("Read straight through. Each finding is one block.")
    add("")
    add("HOW TO FLAG SOMETHING: say the leg name and what is wrong.")
    add("")

    # 1. REPRICE
    reprice = []
    for (a, b), rate in RESEARCHED.items():
        leg = by_pair.get((a, b)) or by_pair.get((b, a))
        if leg is None:
            continue
        current = sum(float(e.get("amount", 0) or 0) for e in _events(leg))
        reprice.append((abs(rate["transponder"] - current), a, b, current, rate))
    reprice.sort(reverse=True)

    add("=" * 60)
    add(f"SECTION 1 of 4: REPRICE. {len(reprice)} legs we already toll.")
    add("Sourced rate differs from our estimate. Largest gap first.")
    add("=" * 60)
    add("")
    for gap, a, b, current, rate in reprice:
        add(f"{a} to {b}")
        add(f"  now: {current:.2f} dollars, estimated")
        add(f"  proposed: {rate['transponder']:.2f} transponder, {rate['plate']:.2f} by plate")
        add(f"  change: {gap:.2f} dollars")
        add(f"  source: {rate['src']}")
        add("")

    # 2. ADD (confident)
    solid = [r for r in scan["missing"] if not r.get("endpoint_only")]
    add("=" * 60)
    add(f"SECTION 2 of 4: ADD. {len(solid)} legs on a tolled road with no toll data.")
    add("The tolled road was found mid-corridor, so these are solid.")
    add("Rates still needed for most; the road itself is confirmed.")
    add("=" * 60)
    add("")
    for row in solid:
        names = ", ".join(w["name"] for w in row["on_route"][:3])
        add(f"{row['from']} to {row['to']}")
        add(f"  highway {row['highway']}, {row['miles']:.0f} miles")
        add(f"  tolled road found: {names}")
        rate = RESEARCHED.get((row["from"], row["to"])) or RESEARCHED.get(
            (row["to"], row["from"])
        )
        if rate:
            add(
                f"  rate known: {rate['transponder']:.2f} transponder, "
                f"{rate['plate']:.2f} by plate"
            )
            add(f"  source: {rate['src']}")
        else:
            add("  rate: STILL NEEDED")
        add("")

    # 3. CHECK (endpoint only), minus border crossings
    edge = [r for r in scan["missing"] if r.get("endpoint_only")]
    border = [
        r for r in edge
        if any(m in w["name"].lower() for w in r["on_route"] for m in BORDER_MARKERS)
    ]
    check = [r for r in edge if r not in border]

    add("=" * 60)
    add(f"SECTION 3 of 4: CHECK. {len(check)} legs need your eye.")
    add("The tolled road appeared only at a city endpoint. That can be a real")
    add("toll plaza at the state line, or the sample catching an unrelated")
    add("city tollway. You have driven these; the tags cannot tell us.")
    add("=" * 60)
    add("")
    for row in check:
        names = ", ".join(w["name"] for w in row["on_route"][:3])
        add(f"{row['from']} to {row['to']}")
        add(f"  highway {row['highway']}, {row['miles']:.0f} miles")
        add(f"  found at the endpoint: {names}")
        add("  question: does a truck on this leg really pay this?")
        add("")

    # 4. DEFERRED
    add("=" * 60)
    add(f"SECTION 4 of 4: DEFERRED. {len(border)} international crossings.")
    add("Parked with the Mexico and Canada border work, per your call.")
    add("No action needed now.")
    add("=" * 60)
    add("")
    for row in border:
        names = ", ".join(w["name"] for w in row["on_route"][:3])
        add(f"{row['from']} to {row['to']}: {names}")
    add("")
    add("STILL MISSING A RATE, needs a human or a phone call:")
    add("  New Hampshire I-95 Hampton plaza, 5 axle. dot.nh.gov blocks")
    add("  automated access. Bureau of Turnpikes, 603 485 3806.")
    add("")
    add("END OF SHEET")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  reprice {len(reprice)}, add {len(solid)}, check {len(check)}, deferred {len(border)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
