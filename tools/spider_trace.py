"""Trace a highway-spider corridor: ORS driving-hgv route along its waypoint chain.

Phase 0 of the highway spider (see docs/highway-spider-methodology.md). Reads
``data/spider/corridors.json``; for ``--ref``, routes the corridor's waypoints
through the self-hosted OpenRouteService (driving-hgv, via ORS_BASE_URL /
ORS_API_KEY), then caches the polyline plus per-point cumulative miles under
``data/spider/traces/<ref>.json``. Verifies the pins by reporting how far each
waypoint sits off the returned trace -- a large offset means ORS ignored the pin
and the corridor needs another waypoint, never a wider gate. Read-only with
respect to world.json.

    ORS_BASE_URL=http://localhost:8080/ors ORS_API_KEY=selfhosted \
        uv run --group tooling python tools/spider_trace.py --ref I-70 [--write]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from enrich_routes_ors import fetch_ors_hgv_route, parse_ors_route  # noqa: E402

SPIDER = ROOT / "data" / "spider"
CORRIDORS = SPIDER / "corridors.json"
R_MI = 3958.8


def hav(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R_MI * 2 * math.asin(math.sqrt(a))


def cumulative(coords):
    """Cumulative haversine miles at each [lon,lat] vertex."""
    cum = [0.0]
    for i in range(1, len(coords)):
        lon1, lat1 = coords[i - 1]
        lon2, lat2 = coords[i]
        cum.append(cum[-1] + hav(lat1, lon1, lat2, lon2))
    return cum


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    corridors = json.loads(CORRIDORS.read_text(encoding="utf-8"))["corridors"]
    corridor = next((c for c in corridors if c["ref"] == a.ref), None)
    if corridor is None:
        raise SystemExit(f"no corridor {a.ref!r} in {CORRIDORS}")
    wps = corridor["waypoints"]
    key = os.environ.get("ORS_API_KEY", "selfhosted")

    payload = fetch_ors_hgv_route(wps[0], wps[-1], key, via=tuple(wps[1:-1]))
    parsed = parse_ors_route(payload)
    coords = parsed["coordinates"]  # [lon, lat]
    cum = cumulative(coords)
    hav_total = cum[-1] or 1.0

    print(
        f"{a.ref} ({corridor['spoken']}): {parsed['miles']:.1f} ORS truck miles, {len(coords)} points"
    )
    print("pin check (each waypoint's distance off the trace -- want ~0):")
    worst = 0.0
    for wp in wps:
        off = min(hav(wp["lat"], wp["lon"], ll[1], ll[0]) for ll in coords)
        worst = max(worst, off)
        flag = "  <-- OFF, add a pin" if off > 3.0 else ""
        print(f"  {wp['note'][:52]:52} {off:5.2f} mi{flag}")
    print(f"worst pin offset: {worst:.2f} mi")

    if a.write:
        (SPIDER / "traces").mkdir(parents=True, exist_ok=True)
        trace = {
            "ref": a.ref,
            "miles": round(parsed["miles"], 1),
            "points": [
                {
                    "lat": round(ll[1], 5),
                    "lon": round(ll[0], 5),
                    "at_mi": round(c * parsed["miles"] / hav_total, 1),
                }
                for ll, c in zip(coords, cum, strict=False)
            ],
        }
        out = SPIDER / "traces" / f"{a.ref}.json"
        out.write_text(json.dumps(trace) + "\n", encoding="utf-8")
        print(f"WROTE {out.relative_to(ROOT)} ({len(coords)} points)")


if __name__ == "__main__":
    raise SystemExit(main())
