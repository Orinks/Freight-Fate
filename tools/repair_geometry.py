"""Put a leg's archived line back on the road, without re-routing it.

bake_curve_geometry does this as part of a full re-bake, but that needs
Overpass for shields, postings and ramps, and Overpass refuses long-corridor
queries often enough that a 24-leg run died on leg five. The geometry itself
needs nothing but the router and an elevation service, both of which answer
every time, so this does that half alone.

What it will NOT do is move a leg to a different road. The leg's mileage is
curated -- pay, deadlines and every mile-keyed layer hang off it -- so a new
shape is only adopted when it agrees with that mileage. If the router has
picked a different road the length will disagree, and the leg is refused and
reported rather than quietly re-routed.

Two screens, both derived from the leg's own record rather than from a
threshold picked to look right:

  * length agreement -- the new shape's own length against the miles the leg
    is paid on. Beyond MAX_LENGTH_DRIFT the router chose a different road,
    whatever else is true.
  * it must actually help -- the new line's worst distance from any road has
    to beat the old one's. A repair that does not improve the thing it was
    called for is not adopted.

    uv run python tools/repair_geometry.py --from logs/offroad.json
    uv run python tools/repair_geometry.py --from logs/offroad.json --write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import leg_geometry as lg  # noqa: E402
import reroute_leg as rr  # noqa: E402
import straw_curve_sample as scs  # noqa: E402
from world_source import load_world  # noqa: E402

GEOM_DIR = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "geometry"
VALHALLA = os.environ.get("FF_VALHALLA_URL", "http://localhost:8002").rstrip("/")

# How far the new shape's own length may sit from the leg's adopted mileage
# before the router is taken to have chosen a different road. The 24 legs
# routed by this same router and profile all landed inside 3 percent; the
# allowance is a little wider so an equivalent road reached by a slightly
# different interchange is not refused, and far tighter than the smallest
# re-route worth worrying about.
MAX_LENGTH_DRIFT = 0.06
MIN_GAP_MI = 2.0
SAMPLES = 5
BATCH = 20


def locate(points: list[tuple[float, float]]) -> list[float | None]:
    """Distance in metres from each point to the nearest truck-drivable road."""
    if not points:
        return []
    out: list[float | None] = []
    for start in range(0, len(points), BATCH):
        chunk = points[start : start + BATCH]
        body = {
            "locations": [{"lat": la, "lon": lo} for la, lo in chunk],
            "costing": "truck",
            "verbose": True,
        }
        req = urllib.request.Request(
            f"{VALHALLA}/locate", json.dumps(body).encode(), {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as fh:
            for entry in json.load(fh):
                dists = [e["distance"] for e in (entry.get("edges") or []) if "distance" in e]
                out.append(min(dists) if dists else None)
    return out


def worst_off_road_m(coords: list[list[float]]) -> float:
    """The furthest this line ever sits from a real road, across its gaps.

    Only gaps are probed: every vertex came off the router and is on the road
    by construction, so the only question is what happens between two of them.
    """
    cum = scs._cumulative_m(coords)
    probes: list[tuple[float, float]] = []
    for i in range(len(coords) - 1):
        if cum[i + 1] - cum[i] < MIN_GAP_MI * 1609.344:
            continue
        (lon1, lat1), (lon2, lat2) = coords[i], coords[i + 1]
        for s in range(1, SAMPLES + 1):
            f = s / (SAMPLES + 1)
            probes.append((lat1 + (lat2 - lat1) * f, lon1 + (lon2 - lon1) * f))
    if not probes:
        return 0.0
    return max((1e6 if d is None else d) for d in locate(probes))


def refetch(leg: dict, cities: dict) -> dict[str, Any]:
    fetched = rr.fetch_route(cities[leg["from"]], cities[leg["to"]])
    if fetched is None:
        raise RuntimeError("the router returned no route")
    shape, _miles, _toll = fetched
    elevations = rr.fetch_elevation(shape)
    if elevations is None:
        raise RuntimeError("no elevation for this shape")
    return {"coordinates": shape, "elevations_ft": elevations}


def rebuild(parsed: dict) -> tuple[dict, list[list[float]]]:
    coords = parsed["coordinates"]
    elev = parsed["elevations_ft"]
    cum = scs._cumulative_m(coords)
    curv = scs.analyse_curvature(coords, cum)
    idx = scs.adaptive_simplify(coords, curv["curving"], cum, scs.POINT_BUDGET)
    geom = scs.encode_geometry(coords, elev, idx)
    return geom, scs.decode_geometry(geom)


def _shard_records(path: Path) -> tuple[dict, list[dict]]:
    meta: dict = {}
    records: list[dict] = []
    if not path.exists():
        return meta, records
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "meta" in row:
            meta = row
        else:
            records.append(row)
    return meta, records


def _write_shard(path: Path, meta: dict, records: list[dict]) -> None:
    lines = [json.dumps(r, sort_keys=True) for r in sorted(records, key=lambda r: r["leg"])]
    payload = "\n".join(lines)
    meta = json.loads(json.dumps(meta))
    meta.setdefault("meta", {})["data_version"] = (
        "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    )
    path.write_text(
        json.dumps(meta, sort_keys=True) + "\n" + payload + "\n", encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="src", type=Path, default=ROOT / "logs" / "offroad.json")
    ap.add_argument("--over", type=float, default=scs.MATCH_CORRIDOR_M)
    ap.add_argument("--only", default="")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    world = load_world()
    cities = world["cities"]
    legs = {f"{leg['from']}:{leg['to']}": leg for leg in world["legs"]}
    scores = json.loads(args.src.read_text(encoding="utf-8")) if args.src.exists() else {}

    if args.only:
        targets = [k for k in args.only.split(";") if k.strip()]
    else:
        targets = [k for k, v in scores.items() if v > args.over]
    targets = targets[: args.limit or None]
    print(f"{len(targets)} legs to repair (worse than {args.over:.0f} m off road)\n", flush=True)

    adopted: dict[str, dict] = {}
    refused: list[tuple[str, str]] = []
    for n, key in enumerate(targets, 1):
        leg = legs.get(key)
        if leg is None:
            refused.append((key, "no such leg"))
            continue
        paid_mi = float(leg.get("miles") or 0.0)
        try:
            parsed = refetch(leg, cities)
        except Exception as exc:  # noqa: BLE001 -- reported, never swallowed
            refused.append((key, f"re-fetch failed: {exc}"))
            print(f"[{n}/{len(targets)}] {key}: REFUSED, re-fetch failed: {exc}", flush=True)
            continue
        geom, coords_dec = rebuild(parsed)
        shape_mi = scs._cumulative_m(parsed["coordinates"])[-1] / 1609.344
        drift = (shape_mi - paid_mi) / paid_mi if paid_mi else 0.0
        if abs(drift) > MAX_LENGTH_DRIFT:
            refused.append((key, f"length drift {drift * 100:+.1f}% -- different road"))
            print(
                f"[{n}/{len(targets)}] {key}: REFUSED, {shape_mi:.1f} mi against "
                f"{paid_mi:.1f} paid ({drift * 100:+.1f}%)",
                flush=True,
            )
            continue
        before = scores.get(key)
        after = worst_off_road_m(coords_dec)
        if before is not None and after >= before:
            refused.append((key, f"no better: {before:.0f} m -> {after:.0f} m"))
            print(
                f"[{n}/{len(targets)}] {key}: REFUSED, no better "
                f"({before:.0f} m -> {after:.0f} m)",
                flush=True,
            )
            continue
        adopted[key] = {
            "leg": key,
            "geom": geom,
            "highway": leg.get("highway", ""),
            "miles": paid_mi,
            "state": lg.state_code_of(leg),
        }
        shown = f"{before:.0f}" if before is not None else "?"
        print(
            f"[{n}/{len(targets)}] {key}: {shown} m -> {after:.0f} m off road, "
            f"{len(coords_dec)} verts, {drift * 100:+.1f}% length",
            flush=True,
        )

    print(f"\n{len(adopted)} adopted, {len(refused)} refused")
    for key, why in refused:
        print(f"  {key:46s} {why}")

    if not args.write:
        print("\n(dry run -- pass --write to update the archive)")
        return 0

    by_state: dict[str, list[dict]] = {}
    for row in adopted.values():
        by_state.setdefault(row["state"], []).append(row)
    for state, rows in sorted(by_state.items()):
        path = GEOM_DIR / f"{state}.jsonl"
        meta, records = _shard_records(path)
        index = {r["leg"]: r for r in records}
        for row in rows:
            keep = index.get(row["leg"], {})
            index[row["leg"]] = {
                "leg": row["leg"],
                "geom": row["geom"],
                "highway": keep.get("highway", row["highway"]),
                "miles": keep.get("miles", row["miles"]),
            }
        _write_shard(path, meta, list(index.values()))
        print(f"  wrote {len(rows)} legs into {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
