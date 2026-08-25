"""How far does each leg's archived line stray from any real road?

The honest damage metric. An earlier one counted a long straight SEGMENT as
damage and made 985 legs look broken; on a dead-straight interstate, two
vertices thirty miles apart describe the road perfectly and Douglas-Peucker
is right to keep only those. Damage is the line lying where no road is.

So: for every gap longer than MIN_GAP_MI, sample along it and ask the router
how far the nearest truck-drivable road actually is. A leg's score is the
worst such distance. Anything inside the match corridor is not damage --
that is the radius within which the line is still governed by its own road.

    uv run python tools/offroad.py
    uv run python tools/offroad.py --json logs/offroad.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import leg_geometry as lg  # noqa: E402
import straw_curve_sample as scs  # noqa: E402
from world_source import load_world  # noqa: E402

import os  # noqa: E402

VALHALLA = os.environ.get("FF_VALHALLA_URL", "http://localhost:8002").rstrip("/")
# Gaps shorter than this cannot hide a meaningful excursion: a two-mile chord
# across a gentle interstate bend sits a few dozen metres off the arc.
MIN_GAP_MI = 2.0
# Points sampled inside each gap, excluding its endpoints (which are on the
# road by construction).
SAMPLES = 5
BATCH = 20


def locate(points: list[tuple[float, float]]) -> list[float | None]:
    body = {
        "locations": [{"lat": la, "lon": lo} for la, lo in points],
        "costing": "truck",
        "verbose": True,
    }
    req = urllib.request.Request(
        f"{VALHALLA}/locate", json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as fh:
        out = json.load(fh)
    res: list[float | None] = []
    for entry in out:
        edges = entry.get("edges") or []
        dists = [e["distance"] for e in edges if "distance" in e]
        res.append(min(dists) if dists else None)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=ROOT / "logs" / "offroad.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    probes: list[tuple[float, float]] = []
    owner: list[str] = []
    legs = {f"{leg['from']}:{leg['to']}": leg for leg in load_world()["legs"]}
    for key in sorted(legs)[: args.limit or None]:
        poly = lg.archived_polyline(key, lg.state_code_of(legs[key]))
        if not poly:
            continue
        coords = poly[0]
        cum = scs._cumulative_m(coords)
        for i in range(len(coords) - 1):
            if cum[i + 1] - cum[i] < MIN_GAP_MI * 1609.344:
                continue
            (lon1, lat1), (lon2, lat2) = coords[i], coords[i + 1]
            for s in range(1, SAMPLES + 1):
                f = s / (SAMPLES + 1)
                probes.append((lat1 + (lat2 - lat1) * f, lon1 + (lon2 - lon1) * f))
                owner.append(key)

    print(f"{len(probes):,} points inside gaps over {MIN_GAP_MI:.0f} mi, across "
          f"{len(set(owner)):,} legs", flush=True)

    worst: dict[str, float] = {}
    for start in range(0, len(probes), BATCH):
        for key, dist in zip(owner[start:start + BATCH], locate(probes[start:start + BATCH])):
            d = 1e6 if dist is None else dist
            if d > worst.get(key, -1.0):
                worst[key] = d
        if start % (BATCH * 50) == 0:
            print(f"  {start:,}/{len(probes):,}", flush=True)

    corridor = scs.MATCH_CORRIDOR_M
    off = {k: v for k, v in worst.items() if v > corridor}
    print(f"\n{len(off)} legs stray past the {corridor:.0f} m match corridor")
    for band in (100, 200, 500, 1000, 2000):
        n = sum(1 for v in off.values() if v > band)
        print(f"  over {band:5d} m: {n:4d} legs")
    print("\nworst twenty:")
    for key, d in sorted(off.items(), key=lambda kv: -kv[1])[:20]:
        shown = "no road found" if d >= 1e6 else f"{d:,.0f} m"
        print(f"  {key:46s} {shown}")

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(
        {k: round(v, 1) for k, v in sorted(off.items(), key=lambda kv: -kv[1])}, indent=1),
        encoding="utf-8")
    print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
