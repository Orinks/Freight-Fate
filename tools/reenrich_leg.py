"""Put every corridor layer back on a leg that has been rerouted.

``reroute_leg.py`` replaces a leg's polyline, mileage, curves and grades, and
drops every other corridor layer, because a landmark at mile 40 of a route
that no longer passes it is worse than no landmark. This runs the builders
that put those layers back, in the one order that works, and then CHECKS that
each of them actually produced something.

The checking is the point. Twice now a builder on a rerouted leg has found
nothing and exited 0: ``build_interchanges`` retained 0 of 59,924 ramp nodes
and reported success, and ``--maxspeed`` wrote 2 speed-limit rows where the
leg had 24. Both had the same cause -- they located the leg by interpolating
straight chords between route points 25 miles apart -- and both are fixed
(``tools/leg_geometry.py``), but a tool that can fail silently needs a floor
under it rather than trust.

    uv run python tools/reenrich_leg.py --snapshot before.json --all
    uv run python tools/reroute_leg.py --leg a:b --write
    uv run --group tooling python tools/reenrich_leg.py --leg a:b --write \\
        --baseline before.json

ORDER, AND WHY IT IS THAT ORDER
-------------------------------
1.  ``route_points`` / ``elevation_samples``, re-derived from the archived
    road, then ``state_miles`` / ``state_crossings`` -- ``_leg_states`` picks
    which Geofabrik extracts to read from the states, and a checkpoint's
    spoken state name is read out of them.
2.  The curve bake, from the archive. It owns curves, runaway ramps and the
    dense posted-limit profile, all off one polyline -- and on a rerouted leg
    those shards otherwise still describe bends and ramps on the road the leg
    was moved off.
3.  Interchanges, then restrictions, then ramp controls -- each its own run.
    The sub-mode flags DO NOT COMPOSE: passing them together dispatches to one
    and silently skips the rest.
4.  ``lane_segments`` and ``traffic_aadt``, which need only the road.
5.  Checkpoints, then landmarks, then villages. Landmarks REPLACES every
    non-curated landmark on the leg including villages, so villages must
    follow it; villages dedupe against checkpoint names and pull a callout
    ahead of the speed zone it explains, so both must precede villages.

Every step shells out to the builder that owns the layer rather than
reimplementing it, so each layer's own provenance, thresholds and reporting
stay in one place.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import enrich_routes as er  # noqa: E402
import leg_geometry  # noqa: E402
from build_interchanges_maxspeed import _leg_states, _pbf_for_states  # noqa: E402
from enrich_routes_states import _load_state_shapes, _state_context  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

ROOT = TOOLS_DIR.parent
OSM_REGION_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"

# Layers this rebuilds, in the order the report prints them.
LAYERS = (
    "state_miles",
    "state_crossings",
    "interchanges",
    "speed_limits",
    "restrictions",
    "lane_segments",
    "traffic_aadt",
    "checkpoints",
    "landmarks",
    "grade_segments",
    "route_points",
    "elevation_samples",
)

# A layer that came back at less than this share of what the leg had before
# the reroute is treated as a builder that no-opped, not as a road that
# genuinely has less on it. Half is deliberately loose: a reroute really does
# change what is out there (Corpus Christi to San Antonio gains interchanges
# moving from US-181 to I-37 and could as easily lose villages), so this is a
# floor against silence, not a claim the two routes should match.
FLOOR_SHARE = 0.5

# Layers where an empty result is a real finding rather than a failure: a leg
# with no posted low bridge or weight limit records a clean sweep, and a
# single-state leg has no crossings.
MAY_BE_EMPTY = ("restrictions", "state_crossings")

# ...and the state layers are not judged by row count AT ALL, because how many
# states a leg crosses is the most direct thing a reroute changes. Buffalo to
# New York used to leave the state -- down the Southern Tier, into
# Pennsylvania and New Jersey and back -- and that detour is exactly the bad
# route being replaced. The truck now runs I-90 to Albany and I-87 down the
# Hudson: 418 miles, all of it New York, one state and no crossings. Counting
# rows called that a regression. What is worth checking is that the per-state
# mileage still adds up to the leg.
COUNTED_LAYERS = tuple(name for name in LAYERS if name not in ("state_miles", "state_crossings"))
STATE_MILES_TOLERANCE = 1.0


def state_miles_add_up(leg: dict[str, Any]) -> tuple[bool, str]:
    """Whether the leg's per-state mileage still accounts for the whole leg."""
    entries = (leg.get("corridor") or {}).get("state_miles") or ()
    miles = float(leg.get("miles") or 0)
    if not entries:
        return False, "no per-state mileage at all"
    total = sum(float(entry["miles"]) for entry in entries)
    names = ", ".join(str(entry["state"]) for entry in entries)
    if abs(total - miles) > STATE_MILES_TOLERANCE:
        return False, f"{names} sum to {total:.0f} of {miles:.0f} mi"
    return True, names


# ``speed_limits`` and ``lane_segments`` are judged on COVERAGE, not on row
# count. A reroute changes which road the leg is on, and a row count follows
# that road's character rather than the bake's health, in both directions:
# Corpus Christi to San Antonio carried 24 speed steps as a US highway through
# five town zones and carries 9 as an interstate; Charlottesville to
# Harrisonburg went from 15 lane segments to 5 because I-64 holds the same two
# lanes the whole way. Both are complete. What a starved bake actually looks
# like is HOLES, so the question worth asking is how much of the leg the layer
# covers at all.
SPEED_SHARD = (
    ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "gameplay" / "speed_limits.jsonl"
)
# Where to draw the line, measured rather than picked. Across the 1,261
# untouched legs the posted-limit coverage runs 97 percent at the median, 53
# at the 10th percentile and 31 at the 5th -- OSM genuinely carries no
# maxspeed on some rural interstate (I-69 in western Kentucky has 37 unposted
# miles, checked way by way), which is exactly what the null gap markers
# record. Lane coverage is tighter: 97 median, 83 at the 5th percentile.
#
# So each bar is its layer's own 5th percentile: a rerouted leg below it is
# worse covered than 95 percent of the legs these bakes were healthy on, and
# the failure this is really here to catch -- the bake that found almost
# nothing -- lands near zero either way.
MIN_SPEED_COVERAGE = 0.31
MIN_LANE_COVERAGE = 0.83


def lane_coverage(leg: dict[str, Any]) -> float | None:
    """Share of the leg its baked lane segments actually span."""
    segments = (leg.get("corridor") or {}).get("lane_segments") or ()
    miles = float(leg.get("miles") or 0)
    if not segments or miles <= 0:
        return None
    covered = sum(float(s["end_mi"]) - float(s["start_mi"]) for s in segments)
    return min(1.0, covered / miles)


def speed_coverage(leg_key: str, leg_miles: float) -> float | None:
    """Share of the leg carrying a posted limit read from OSM, or None.

    The shard keeps the ``mph: null`` markers the curve bake writes where OSM
    has no maxspeed for more than a few miles; the world source strips them.
    Everything from a null to the next reading is a hole, and so is the run
    before the first reading.
    """
    if not SPEED_SHARD.exists() or leg_miles <= 0:
        return None
    rows = []
    for line in SPEED_SHARD.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith('{"meta"'):
            continue
        row = json.loads(line)
        if row.get("leg") == leg_key:
            rows.append(row)
    if not rows:
        return 0.0
    rows.sort(key=lambda r: float(r["at_mi"]))
    hole = float(rows[0]["at_mi"])
    for row, nxt in zip(rows, rows[1:] + [{"at_mi": leg_miles}], strict=False):
        if row.get("mph") is None:
            hole += float(nxt["at_mi"]) - float(row["at_mi"])
    return max(0.0, 1.0 - hole / leg_miles)


def leg_id(leg: dict[str, Any]) -> str:
    return f"{leg['from']}:{leg['to']}"


def layer_counts(leg: dict[str, Any]) -> dict[str, int]:
    corridor = leg.get("corridor") or {}
    return {name: len(corridor.get(name) or ()) for name in LAYERS}


def _run(argv: list[str], label: str) -> bool:
    print(f"\n=== {label}\n    {' '.join(argv)}", flush=True)
    result = subprocess.run(argv, cwd=ROOT, text=True)
    if result.returncode != 0:
        print(f"    ! {label} exited {result.returncode}", flush=True)
    return result.returncode == 0


def rebuild_states(data: dict[str, Any], leg: dict[str, Any], cache_dir: Path) -> None:
    """state_miles and state_crossings, from the leg's own new polyline.

    In-process rather than shelled out: ``enrich_routes.py --only`` governs
    geometry refresh, not per-leg enrichment, and running it here would fetch
    a fresh OSRM route and overwrite the polyline this whole exercise exists
    to install.
    """
    shape = leg_geometry.archived_shape(leg_id(leg))
    if shape is None:
        print("    ! no archived geometry; leaving state layers alone")
        return
    context = _state_context(data, leg, shape, _load_state_shapes(cache_dir, 0.0))
    corridor = leg.setdefault("corridor", {})
    corridor["state_miles"] = context["state_miles"]
    if context["state_crossings"]:
        corridor["state_crossings"] = context["state_crossings"]
    else:
        corridor.pop("state_crossings", None)
    spoken = ", ".join(f"{s['state']} {s['miles']:.0f} mi" for s in context["state_miles"])
    print(f"    {spoken}; {len(context['state_crossings'])} crossing(s)")


def rebuild_route_points(leg: dict[str, Any]) -> None:
    """Refresh route_points and elevation_samples off the archived road.

    ``reroute_leg`` writes both so the enrichment builders have something to
    locate the leg by at all; this re-derives them from the checked-in
    polyline, so a leg fixed after the fact never needs the router again.
    """
    import reroute_leg

    key = leg_id(leg)
    miles = float(leg["miles"])
    shape = leg_geometry.archived_shape(key)
    profile = leg_geometry.archived_profile(key, miles)
    if shape is None or profile is None:
        print("    ! no archived geometry; leaving the route points alone")
        return
    stride = max(0.5, min(reroute_leg.SAMPLE_MI, miles / (reroute_leg.MIN_ROUTE_POINTS - 1)))
    source = (
        "Read: Valhalla /height elevation along the leg's own truck route, taken at "
        "development time and archived to the nearest metre (replaces the "
        "OpenRouteService route this leg was first baked from)."
    )
    points, elevations = [], []
    last = -1e9
    for i, ((lon, lat), (at_mi, elevation_ft)) in enumerate(zip(shape, profile, strict=False)):
        if at_mi - last < stride and i not in (0, len(shape) - 1):
            continue
        last = at_mi
        points.append({"at_mi": round(at_mi, 2), "lat": round(lat, 5), "lon": round(lon, 5)})
        elevations.append(
            {"at_mi": round(at_mi, 2), "elevation_ft": round(elevation_ft, 1), "source": source}
        )
    corridor = leg.setdefault("corridor", {})
    corridor["route_points"] = points
    corridor["elevation_samples"] = elevations
    print(f"    {len(points)} route points, one about every {stride:.1f} mi")


def reenrich(leg_key: str, write: bool, cache_dir: Path) -> int:
    data = load_world()
    leg = next((x for x in data["legs"] if leg_id(x) == leg_key), None)
    if leg is None:
        print(f"no such leg: {leg_key}")
        return 1

    print(f"=== {leg_key} ({leg.get('highway')}), {leg.get('miles')} mi")
    if not write:
        print("(dry run: nothing below will be saved; pass --write)")

    # 1. The road's own summary layers, then the states -- the extract picker
    #    and the checkpoint state names both read the states.
    print("\n=== route_points / elevation_samples")
    rebuild_route_points(leg)
    print("\n=== state_miles / state_crossings")
    rebuild_states(data, leg, cache_dir)
    if write:
        save_world(data)

    pair = f"{leg['from']}->{leg['to']}"
    colon = leg_key
    pbfs = _pbf_for_states(_leg_states(data, leg), OSM_REGION_DIR)
    if not pbfs:
        print(f"    ! no local extracts for this leg's states in {OSM_REGION_DIR}")
        return 1
    pbf_args: list[str] = []
    for path in pbfs:
        pbf_args += ["--pbf", str(path)]
    write_arg = ["--write"] if write else []
    uv = ["uv", "run", "--group", "tooling", "python"]

    steps: list[tuple[str, list[str]]] = [
        (
            "interchanges",
            [*uv, "tools/build_interchanges.py", "--only", pair, *pbf_args, "--force", *write_arg],
        ),
        # The sub-modes do NOT compose -- passing them together dispatches to
        # one and silently skips the rest. --force on each, because a re-run
        # otherwise skips a leg that already has the layer and reports success.
        (
            "restrictions",
            [
                *uv,
                "tools/build_interchanges.py",
                "--only",
                pair,
                "--restrictions",
                "--force",
                *write_arg,
            ],
        ),
        (
            "ramp controls",
            [
                *uv,
                "tools/build_interchanges.py",
                "--only",
                pair,
                "--ramp-controls",
                "--force",
                *write_arg,
            ],
        ),
        ("lane_segments", [*uv, "tools/bake_lane_segments.py", "--only", colon, *write_arg]),
        (
            "traffic_aadt",
            [*uv, "tools/build_traffic_aadt.py", "--only", pair, "--force", *write_arg],
        ),
        (
            "checkpoints",
            [
                *uv,
                "tools/place_checkpoints.py",
                "--leg",
                colon,
                "--from-places",
                "--replace",
                *write_arg,
            ],
        ),
        # Landmarks REPLACES every non-curated landmark including villages, so
        # villages have to come after it.
        ("landmarks", [*uv, "tools/bake_landmarks.py", "--only", colon, *write_arg]),
        ("villages", [*uv, "tools/bake_villages.py", "--only", colon, *write_arg]),
    ]

    # Curves, runaway ramps and the dense posted-limit profile all come off ONE
    # polyline, and on a rerouted leg that polyline has to be the archive: the
    # shards would otherwise still describe bends and ramps on the road the leg
    # was moved off. This is also where ``speed_limits`` comes from, at quarter
    # mile resolution -- ``build_interchanges --maxspeed`` is a coarser
    # mainline read of the same OSM tags and is deliberately NOT in this chain,
    # because running it afterwards would overwrite the good profile.
    #
    # It goes first, and only when writing: it has no dry run of its own.
    if write:
        steps.insert(
            0,
            (
                "curves / ramps / speed_limits",
                [*uv, "tools/bake_curve_geometry.py", "--only", colon, "--from-archive"],
            ),
        )

    failed = [label for label, argv in steps if not _run(argv, label)]
    if failed:
        print(f"\n! these builders exited non-zero: {', '.join(failed)}")
    return 1 if failed else 0


def report(baseline: dict[str, Any], leg_keys: list[str]) -> int:
    """Compare each leg's layers against its pre-reroute counts."""
    data = load_world()
    by_key = {leg_id(leg): leg for leg in data["legs"]}
    problems = 0
    for key in leg_keys:
        leg = by_key.get(key)
        if leg is None:
            print(f"{key}: gone from the world source")
            problems += 1
            continue
        before = baseline.get(key, {})
        after = layer_counts(leg)
        print(f"\n{key} ({leg.get('highway')}), {leg.get('miles')} mi")
        miles = float(leg.get("miles") or 0)
        for name in LAYERS:
            was, now = int(before.get(name, 0)), after[name]
            verdict, note = "  ", ""
            if name == "speed_limits":
                covered = speed_coverage(key, miles)
                if covered is not None:
                    note = f"  posted over {100 * covered:.0f}% of the leg"
                    if covered < MIN_SPEED_COVERAGE:
                        verdict, problems = "THIN", problems + 1
            elif name == "lane_segments":
                covered = lane_coverage(leg)
                if covered is None:
                    verdict, problems = "GONE", problems + 1
                else:
                    note = f"  spanning {100 * covered:.0f}% of the leg"
                    if covered < MIN_LANE_COVERAGE:
                        verdict, problems = "THIN", problems + 1
            elif name == "state_miles":
                ok, why = state_miles_add_up(leg)
                note = f"  {why}"
                if not ok:
                    verdict, problems = "GONE", problems + 1
            elif name not in COUNTED_LAYERS:
                pass
            elif now == 0 and was > 0 and name not in MAY_BE_EMPTY:
                verdict, problems = "GONE", problems + 1
            elif now and was and now < was * FLOOR_SHARE:
                verdict, problems = "THIN", problems + 1
            print(f"   {verdict} {name:20s} {was:5d} -> {now:5d}{note}")
    print(f"\n{problems} layer(s) below the floor")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--leg", action="append", default=[], help="repeatable, 'from_slug:to_slug'")
    ap.add_argument("--legs-file", type=Path, help="one leg id per line")
    ap.add_argument("--all", action="store_true", help="with --snapshot: every leg in the world")
    ap.add_argument("--write", action="store_true", help="apply (default is a dry run)")
    ap.add_argument("--snapshot", type=Path, help="write current layer counts here and stop")
    ap.add_argument("--baseline", type=Path, help="report the result against this snapshot")
    ap.add_argument("--report-only", action="store_true", help="skip the builders, just report")
    ap.add_argument("--cache-dir", type=Path, default=er.CACHE_PATH)
    args = ap.parse_args()

    keys = list(args.leg)
    if args.legs_file:
        keys += [
            line.strip()
            for line in args.legs_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]

    if args.snapshot:
        data = load_world()
        legs = data["legs"] if args.all else [x for x in data["legs"] if leg_id(x) in set(keys)]
        counts = {leg_id(leg): layer_counts(leg) for leg in legs}
        args.snapshot.write_text(json.dumps(counts, indent=1, sort_keys=True), encoding="utf-8")
        print(f"snapshotted {len(counts)} legs -> {args.snapshot}")
        return 0

    if not keys:
        ap.error("--leg or --legs-file is required")

    status = 0
    if not args.report_only:
        for key in keys:
            status |= reenrich(key, args.write, args.cache_dir)

    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        print("\n" + "=" * 70)
        print("LAYER CENSUS: before the reroute -> now")
        print("=" * 70)
        status |= report(baseline, keys)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
