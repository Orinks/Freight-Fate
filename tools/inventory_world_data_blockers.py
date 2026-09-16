"""Dry-run inventory for the three Career 1.9 world-data blockers on ROADMAP.

Reports current counts only -- never writes world data.

  1. Legs whose baked curves no longer re-detect against archived geometry
     (pre-repair curve/limit/ramp derived layers). Same skip rule as
     ``tools/curve_valhalla_facts.py``, offline, no Valhalla / Overpass.
  2. Legs a truck router refuses to adopt (length drift vs paid miles).
     Canonical list from ``docs/truck-router-refuse-legs.md``; cross-checked
     against ``logs/offroad.json`` when present.
  3. Facility endpoint pins with ``approach_miles`` > 8 (the placement
     audit that leaves synthetic deadheads past Josh's 1-9 mile band).

Usage::

    uv run python tools/inventory_world_data_blockers.py
    uv run python tools/inventory_world_data_blockers.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import straw_curve_sample as scs  # noqa: E402
from bake_divided import load_geometry_by_code  # noqa: E402
from world_source import load_world  # noqa: E402

# Match production bake / curve_valhalla_facts re-detect.
scs.CURVE_PAD_M = 150.0

ROOT = Path(__file__).resolve().parents[1]
CURVES = ROOT / "src/freight_fate/data/world_data/us/gameplay/curves.jsonl"
SPEED = ROOT / "src/freight_fate/data/world_data/us/gameplay/speed_limits.jsonl"
RAMPS = ROOT / "src/freight_fate/data/world_data/us/gameplay/ramps.jsonl"
ENDPOINTS = ROOT / "src/freight_fate/data/facility_endpoints.json"
OFFROAD = ROOT / "logs/offroad.json"
REFUSE_DOC = ROOT / "docs/truck-router-refuse-legs.md"

# Documented refusals from repair_geometry length-drift screen (owner still
# decides mileage vs road). Kept here so the inventory works without parsing
# markdown when the doc is absent; the doc is canonical for retirement notes.
TRUCK_ROUTER_REFUSE: tuple[tuple[str, float], ...] = (
    ("hazard_ky_us:london_ky_us", 83.6),
    ("evansville_in_us:clarksville_tn_us", 57.2),
    ("morristown_tn_us:london_ky_us", 42.7),
    ("payson_az_us:winslow_az_us", -41.4),
    ("charleston_wv_us:pikeville_ky_us", 38.7),
    ("allentown_pa_us:trenton_nj_us", 33.6),
    ("portland_me_us:montpelier_vt_us", 29.4),
    ("evansville_in_us:nashville_tn_us", 27.5),
    ("wenatchee_wa_us:everett_wa_us", -27.3),
    ("las_vegas_nv_us:phoenix_az_us", 21.6),
    ("charleston_sc_us:florence_sc_us", 18.1),
    ("coos_bay_or_us:roseburg_or_us", -16.2),
    ("hartford_ct_us:providence_ri_us", 15.9),
    ("chico_ca_us:santa_rosa_ca_us", 15.8),
    ("pikeville_ky_us:hazard_ky_us", 12.5),
    ("spokane_wa_us:boise_id_us", -11.7),
    ("austin_tx_us:kerrville_tx_us", -11.6),
    ("albany_ny_us:bridgeport_ct_us", 11.6),
    ("tampa_fl_us:miami_fl_us", 11.4),
    ("paintsville_ky_us:pikeville_ky_us", 10.8),
    ("charlotte_nc_us:knoxville_tn_us", -9.7),
    ("denver_co_us:salt_lake_city_ut_us", 9.2),
    ("charlotte_nc_us:lumberton_nc_us", -9.1),
    ("williamsport_pa_us:harrisburg_pa_us", -7.7),
    ("augusta_ga_us:savannah_ga_us", 7.5),
    ("roanoke_va_us:raleigh_nc_us", 7.5),
    ("elizabethtown_ky_us:evansville_in_us", 7.3),
    ("clarksville_tn_us:louisville_ky_us", -7.3),
    ("muskegon_mi_us:traverse_city_mi_us", -7.2),
    ("south_bend_in_us:fort_wayne_in_us", 7.2),
    ("denver_co_us:albuquerque_nm_us", 7.1),
    ("rochester_ny_us:new_york_ny_us", -6.6),
    ("santa_ana_ca_us:lancaster_ca_us", 6.4),
)

APPROACH_FAR_MI = 8.0


def _load_rows(path: Path) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in path.open(encoding="utf-8"):
        obj = json.loads(line)
        if "meta" in obj and len(obj) == 1:
            continue
        leg = obj.get("leg")
        if leg:
            by[str(leg)].append(obj)
    return by


def inventory_pre_repair_curves() -> dict[str, Any]:
    """Legs whose baked curve count disagrees with re-detect on archive geom."""
    world = load_world()
    cities = world["cities"]
    curve_by = _load_rows(CURVES)
    speed_by = _load_rows(SPEED)
    ramp_by = _load_rows(RAMPS)
    geom_cache: dict[str, dict[str, list]] = {}
    mismatch: list[dict[str, Any]] = []
    ok = 0
    with_curves = 0
    for leg in world["legs"]:
        leg_id = f"{leg['from']}:{leg['to']}"
        rows = curve_by.get(leg_id)
        if not rows:
            continue
        with_curves += 1
        code = str(cities[leg["from"]]["state"]).lower()
        if code not in geom_cache:
            geom_cache[code] = load_geometry_by_code(code)
        coords = geom_cache[code].get(leg_id)
        if not coords or len(coords) < 3:
            mismatch.append(
                {
                    "leg": leg_id,
                    "baked_curves": len(rows),
                    "detected": None,
                    "reason": "no_geometry",
                }
            )
            continue
        cum = scs._cumulative_m(coords)
        detected = scs.analyse_curvature(coords, cum)["curves"]
        if len(detected) != len(rows):
            mismatch.append(
                {
                    "leg": leg_id,
                    "baked_curves": len(rows),
                    "detected": len(detected),
                    "reason": "count_mismatch",
                }
            )
        else:
            ok += 1
    return {
        "count": len(mismatch),
        "ok": ok,
        "with_curves": with_curves,
        "with_speed_limits": sum(1 for row in mismatch if speed_by.get(row["leg"])),
        "with_ramps": sum(1 for row in mismatch if ramp_by.get(row["leg"])),
        "legs": mismatch,
        "entrypoint": (
            "curves-only re-bake still needed on tools/bake_curve_geometry.py "
            "(skip query_leg_ways / bake_speed_limits / harvest_ramps); "
            "today: uv run python tools/bake_curve_geometry.py --from-archive "
            "--only <legs> still hits Overpass for limits/ramps"
        ),
    }


def inventory_truck_router_refuse() -> dict[str, Any]:
    offroad: dict[str, float] = {}
    if OFFROAD.is_file():
        raw = json.loads(OFFROAD.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            offroad = {str(k): float(v) for k, v in raw.items()}
    legs = [
        {
            "leg": leg,
            "router_vs_paid_pct": pct,
            "in_offroad_log": leg in offroad,
            "offroad_m": offroad.get(leg),
        }
        for leg, pct in TRUCK_ROUTER_REFUSE
    ]
    return {
        "count": len(legs),
        "in_offroad_log": sum(1 for row in legs if row["in_offroad_log"]),
        "legs": legs,
        "doc": str(REFUSE_DOC.relative_to(ROOT)) if REFUSE_DOC.is_file() else None,
        "entrypoint": (
            "uv run python tools/repair_geometry.py --only <leg>  "
            "(prints router length vs paid; refuses rather than adopting); "
            "retirement plan in docs/truck-router-refuse-legs.md"
        ),
    }


def inventory_far_approach_pins() -> dict[str, Any]:
    payload = json.loads(ENDPOINTS.read_text(encoding="utf-8"))
    endpoints = payload.get("endpoints") or {}
    far: list[dict[str, Any]] = []
    bands: Counter[str] = Counter()
    for facility_id, row in endpoints.items():
        miles = float(row.get("approach_miles") or 0.0)
        if miles <= APPROACH_FAR_MI:
            continue
        if miles >= 35.0:
            band = "ge_35_cap"
        elif miles >= 20.0:
            band = "20_to_35"
        elif miles >= 12.0:
            band = "12_to_20"
        else:
            band = "8_to_12"
        bands[band] += 1
        far.append(
            {
                "facility_id": facility_id,
                "city": row.get("city"),
                "approach_miles": miles,
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "source_backed": row.get("source_backed"),
                "fallback": row.get("fallback"),
            }
        )
    far.sort(key=lambda r: (-float(r["approach_miles"]), str(r["facility_id"])))
    return {
        "count": len(far),
        "threshold_mi": APPROACH_FAR_MI,
        "bands": dict(bands),
        "exactly_35": sum(1 for r in far if abs(float(r["approach_miles"]) - 35.0) < 0.05),
        "write_paths": [
            "src/freight_fate/data/facility_endpoints.json",
            "src/freight_fate/data/facility_approaches.json",
        ],
        "do_not_touch_jade_stops": "src/freight_fate/data/world_data/us/legs/*.json",
        "entrypoint": (
            "re-geocode flagged pins (OSM name+type within city bounds), then "
            "uv run --group tooling python tools/build_facility_approaches.py "
            "--states ... --write; runtime clamp is SYNTHETIC_APPROACH_CAP_MI=9 "
            "in src/freight_fate/data/world_services.py"
        ),
        "legs": far,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit full machine-readable report")
    ap.add_argument(
        "--out",
        type=Path,
        help="optional path for the JSON report (implies full payload)",
    )
    args = ap.parse_args()

    print("inventorying pre-repair curve mismatch (offline)...", flush=True)
    curves = inventory_pre_repair_curves()
    refuse = inventory_truck_router_refuse()
    approaches = inventory_far_approach_pins()

    summary = {
        "pre_repair_curve_mismatch": {
            k: curves[k]
            for k in ("count", "ok", "with_curves", "with_speed_limits", "with_ramps", "entrypoint")
        },
        "truck_router_refuse": {
            k: refuse[k] for k in ("count", "in_offroad_log", "doc", "entrypoint")
        },
        "far_facility_approach_pins": {
            k: approaches[k]
            for k in (
                "count",
                "threshold_mi",
                "bands",
                "exactly_35",
                "write_paths",
                "do_not_touch_jade_stops",
                "entrypoint",
            )
        },
    }

    print()
    print("=== Career 1.9 world-data blockers (dry-run) ===")
    print(f"1) pre-repair curve/limit/ramp geometry: {curves['count']} legs")
    print(f"   re-detect OK {curves['ok']} / with curves {curves['with_curves']}")
    print(f"   also have speed_limits={curves['with_speed_limits']} ramps={curves['with_ramps']}")
    print(f"2) truck-router-refuse legs: {refuse['count']}")
    print(f"   also present in logs/offroad.json: {refuse['in_offroad_log']}")
    print(f"3) facility approach pins > {APPROACH_FAR_MI:g} mi: {approaches['count']}")
    print(f"   bands={approaches['bands']} exactly_35={approaches['exactly_35']}")
    print()
    print("Jade collision: do NOT edit", approaches["do_not_touch_jade_stops"])
    print("Approach write surface:", ", ".join(approaches["write_paths"]))

    payload = {
        "summary": summary,
        "pre_repair_curve_mismatch": curves,
        "truck_router_refuse": refuse,
        "far_facility_approach_pins": approaches,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    elif args.json:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
