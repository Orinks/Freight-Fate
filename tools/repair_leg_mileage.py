"""Correct leg mileages that fall short of the road the leg was baked from.

WHAT IS WRONG
-------------
``leg.miles`` is a curated number, and on some legs it is simply too small.
Poplar Bluff to Jonesboro is stored as 55 miles; the route baked for it is
95. Altus to Wichita Falls says 50 and is 85. Greenville to New Bern says 35
and is 58.

36 of them are impossible on their own terms: the stored mileage is less
than the STRAIGHT-LINE distance between the two city nodes, and no road is
shorter than the straight line between its endpoints. That test needs no
other data and no judgement.

Nothing has caught this because everything agrees with it. The corridor bake
rescales every layer onto ``leg.miles`` (``mile_scale`` in
``bake_curve_geometry``), so the grades end exactly at the stored figure, the
landmarks stop there, and ``state_miles`` sums to it precisely. They are not
independent witnesses; they are the same number wearing different hats.

It matters because leg miles drive pay, deadlines, fuel and the odometer. A
leg that pays for 55 miles while the truck drives 95 is a bad deal the player
cannot see. And the same rescaling squeezes that leg's curve, grade and
speed-limit positions into 58 percent of the road they belong on.

THE CORRECT VALUE, AND WHY IT IS A LOWER BOUND
----------------------------------------------
``world_data/us/geometry/<state>.jsonl`` holds the polyline every corridor
layer was baked from. Its length is a LOWER BOUND on the real road, and
provably so: the archive is a Douglas-Peucker subset of the route's vertices,
and dropping a vertex replaces a two-segment path with its chord, which is
never longer. So archived <= what ORS returned <= the real road.

That is what makes the correction safe in one direction. A leg whose curated
mileage sits BELOW the archive is short of a proven floor, so raising it to
the floor can only move it toward the truth. Legs already above the archive
are left alone -- the archive understates, so being above it proves nothing.

Measured, the simplification costs about 0.1 percent: across the 852 legs
whose curated figure agrees with the archive to within rounding, the median
gap is a tenth of a mile in a hundred. So a corrected leg still reads a
touch short, and knowingly so.

THE LINE IS ROUNDING, NOT A THRESHOLD
-------------------------------------
Curated mileages are whole miles, so a leg whose true length is 55.4 stored
as 55 reads 0.4 short of the archive through rounding alone. ``ROUNDING_MI``
is that half-mile and nothing more; there is no tuned parameter here. The
shortfall distribution has no gap to cut at anyway -- it decays smoothly from
51 miles down to nothing -- which is exactly why the line has to come from
the arithmetic rather than from the shape.

RESCALING, AND THE ONE FIELD THAT MUST NOT MOVE
-----------------------------------------------
Every layer is keyed to leg-miles, so correcting the length without moving
them would misplace all of it. Each along-route position scales by
``new/old``. The fields are named explicitly in ``ALONG_ROUTE`` rather than
matched by pattern, and the run FAILS if it meets a mileage-looking field the
list does not know -- a schema addition must not be silently left behind.

``landmarks[].off_mi`` is deliberately absent from that list: it is how far a
village sits OFF the road, not where along it, and scaling it would push
every town further into the fields.

Usage
-----
    uv run python tools/repair_leg_mileage.py --report
    uv run python tools/repair_leg_mileage.py --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import straw_curve_sample as scs  # noqa: E402
from bake_divided import load_geometry_by_code  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORLD_DATA = ROOT / "src" / "freight_fate" / "data" / "world_data"
GEOM_DIR = WORLD_DATA / "us" / "geometry"
GAMEPLAY = WORLD_DATA / "us" / "gameplay"

# Curated mileages are whole miles, so a leg can read up to half a mile short
# of its own road through rounding alone. That is all this is.
ROUNDING_MI = 0.5

# Every along-route position inside a leg, as (container, field) pairs. Named
# rather than pattern-matched so a new one cannot join silently -- see
# ``unknown_mileage_fields``.
ALONG_ROUTE: dict[str, tuple[str, ...]] = {
    "grade_segments": ("start_mi", "end_mi"),
    "lane_segments": ("start_mi", "end_mi"),
    "landmarks": ("at_mi",),  # NOT off_mi -- that is distance off the road
    "interchanges": ("at_mi",),
    "speed_limits": ("at_mi",),
    "traffic_aadt": ("at_mi",),
    "route_points": ("at_mi",),
    "elevation_samples": ("at_mi",),
    "checkpoints": ("at_mi",),
    "state_crossings": ("at_mi",),
    "restrictions": ("at_mi",),
    "toll_events": ("at_mi",),
    "state_miles": ("miles",),  # a per-state LENGTH, so it scales like the whole
}
# Fields that look like mileages and must be left exactly as they are.
NOT_ALONG_ROUTE = {("landmarks", "off_mi")}

# Shard files keyed to leg-miles, and which of their fields are positions.
SHARDS = {
    "curves.jsonl": ("start_mi", "apex_mi", "end_mi"),
    "ramps.jsonl": ("at_mi",),
    "speed_limits.jsonl": ("at_mi",),
    "curve_artifacts.jsonl": ("start_mi", "apex_mi", "end_mi"),
}


def archived_miles(world: dict) -> dict[str, float]:
    """Length of the polyline each leg's corridor was baked from."""
    cities = world["cities"]
    cache: dict[str, dict[str, list]] = {}
    out: dict[str, float] = {}
    for leg in world["legs"]:
        city = cities.get(leg["from"])
        if not city:
            continue
        code = str(city["state"]).lower()
        if code not in cache:
            cache[code] = load_geometry_by_code(code)
        coords = cache[code].get(f"{leg['from']}:{leg['to']}")
        if coords and len(coords) > 1:
            out[f"{leg['from']}:{leg['to']}"] = scs._cumulative_m(coords)[-1] / 1609.344
    return out


def unknown_mileage_fields(leg: dict) -> list[str]:
    """Mileage-looking fields this tool has never been told about."""
    known = {(c, f) for c, fs in ALONG_ROUTE.items() for f in fs} | NOT_ALONG_ROUTE
    found: list[str] = []
    for container, rows in (leg.get("corridor") or {}).items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for field, value in row.items():
                if not isinstance(value, (int, float)):
                    continue
                if ("_mi" in field or field == "miles") and (container, field) not in known:
                    found.append(f"corridor.{container}[].{field}")
    return sorted(set(found))


def rescale_leg(leg: dict, factor: float) -> int:
    """Scale every along-route position on one leg. Returns values touched."""
    touched = 0
    corridor = leg.get("corridor") or {}
    for container, fields in ALONG_ROUTE.items():
        for row in corridor.get(container) or ():
            if not isinstance(row, dict):
                continue
            for field in fields:
                value = row.get(field)
                if isinstance(value, (int, float)):
                    row[field] = round(value * factor, 2)
                    touched += 1
    for stop in leg.get("stops") or ():
        if isinstance(stop, dict) and isinstance(stop.get("at_mi"), (int, float)):
            stop["at_mi"] = round(stop["at_mi"] * factor, 2)
            touched += 1
    return touched


def rescale_shards(factors: dict[str, float]) -> dict[str, int]:
    """Scale the gameplay shards' positions for every corrected leg."""
    counts: dict[str, int] = {}
    for name, fields in SHARDS.items():
        path = GAMEPLAY / name
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        meta = next((line for line in lines if line.startswith('{"meta"')), None)
        rows = [
            json.loads(line) for line in lines if line.strip() and not line.startswith('{"meta"')
        ]
        touched = 0
        for row in rows:
            factor = factors.get(row.get("leg", ""))
            if factor is None:
                continue
            for field in fields:
                if isinstance(row.get(field), (int, float)):
                    row[field] = round(row[field] * factor, 2)
                    touched += 1
        if not touched:
            continue
        payload = "\n".join(
            json.dumps(r, sort_keys=True)
            for r in sorted(rows, key=lambda r: (r["leg"], r.get("seq", 0)))
        )
        text = (meta + "\n" if meta else "") + payload + "\n"
        path.write_text(text, encoding="utf-8")
        counts[name] = touched
    return counts


def rescale_geometry(new_miles: dict[str, float]) -> int:
    """The geometry shards carry the leg's mileage too."""
    touched = 0
    for shard in sorted(GEOM_DIR.glob("*.jsonl")):
        lines = shard.read_text(encoding="utf-8").splitlines()
        out, changed = [], False
        for line in lines:
            if not line.strip():
                continue
            if line.startswith('{"meta"'):
                out.append(line)
                continue
            rec = json.loads(line)
            miles = new_miles.get(rec.get("leg", ""))
            if miles is not None:
                rec["miles"] = miles
                changed = True
                touched += 1
            out.append(json.dumps(rec, sort_keys=True))
        if changed:
            shard.write_text("\n".join(out) + "\n", encoding="utf-8")
    return touched


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the correction")
    ap.add_argument("--report", action="store_true", help="print the plan, no write")
    args = ap.parse_args()

    world = load_world()
    archived = archived_miles(world)

    # A schema field this tool has never seen would be silently left behind at
    # the old scale, so refuse to run rather than misplace it.
    unknown: set[str] = set()
    for leg in world["legs"]:
        unknown.update(unknown_mileage_fields(leg))
    if unknown:
        print("REFUSING: mileage fields this tool does not know about:")
        for field in sorted(unknown):
            print(f"  {field}")
        print("Add them to ALONG_ROUTE (or NOT_ALONG_ROUTE) and re-run.")
        return 1

    plan = []
    for leg in world["legs"]:
        key = f"{leg['from']}:{leg['to']}"
        floor = archived.get(key)
        miles = float(leg.get("miles") or 0)
        if floor is None or miles <= 0:
            continue
        if miles >= floor - ROUNDING_MI:
            continue  # at or above the proven floor; nothing provable here
        plan.append((key, leg, miles, floor, float(round(floor))))

    plan.sort(key=lambda p: p[3] - p[2], reverse=True)
    total_old = sum(p[2] for p in plan)
    total_new = sum(p[4] for p in plan)
    print(f"{len(plan)} legs are below the archive's proven floor")
    print(
        f"  their curated total {total_old:,.0f} mi -> {total_new:,.0f} mi (+{total_new - total_old:,.0f})"
    )
    print(f"\n{'leg':52s} {'was':>6s} {'now':>6s} {'+mi':>6s}")
    for key, _leg, miles, _floor, new in plan[:25]:
        print(f"{key:52s} {miles:6.0f} {new:6.0f} {new - miles:6.0f}")
    if len(plan) > 25:
        print(f"  ... and {len(plan) - 25} more")

    if not args.write:
        return 0

    factors = {}
    touched = 0
    for key, leg, miles, _floor, new in plan:
        factor = new / miles
        factors[key] = factor
        touched += rescale_leg(leg, factor)
        leg["miles"] = new
    shard_counts = rescale_shards(factors)
    geom_touched = rescale_geometry({k: v[4] for k, v in ((p[0], p) for p in plan)})
    save_world(world)

    print(f"\nrescaled {touched} along-route values on {len(plan)} legs")
    for name, n in sorted(shard_counts.items()):
        print(f"  {name}: {n} positions")
    print(f"  geometry shards: {geom_touched} leg records")

    # Invariants, checked on the saved result rather than assumed.
    fresh = load_world()
    bad = []
    for leg in fresh["legs"]:
        key = f"{leg['from']}:{leg['to']}"
        if key not in factors:
            continue
        miles = float(leg["miles"])
        corridor = leg.get("corridor") or {}
        for container, fields in ALONG_ROUTE.items():
            if container == "state_miles":
                total = sum(float(r.get("miles") or 0) for r in corridor.get(container) or ())
                if total and abs(total - miles) > 1.0:
                    bad.append(f"{key}: state_miles sums to {total:.1f}, leg is {miles:.0f}")
                continue
            for row in corridor.get(container) or ():
                for field in fields:
                    value = row.get(field)
                    if isinstance(value, (int, float)) and value > miles + 1.0:
                        bad.append(
                            f"{key}: {container}.{field}={value} past the leg end {miles:.0f}"
                        )
    if bad:
        print(f"\nINVARIANT FAILURES ({len(bad)}):")
        for line in bad[:15]:
            print(f"  {line}")
        return 1
    print("\ninvariants hold: nothing sits past its leg end, state_miles sums true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
