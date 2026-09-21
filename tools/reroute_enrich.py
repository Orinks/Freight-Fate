"""Rebuild every layer a rerouted leg lost.

``tools/reroute_leg.py`` replaces a leg's polyline with the road a truck
actually takes and then drops every corridor layer keyed to the old one,
because a landmark at mile 40 of a route the truck no longer passes is worse
than no landmark at all. It says so itself, and leaves the leg INCOMPLETE.

This finishes it. A leg without ``grade_segments`` has no grade simulation --
the engine never loads, never fades, never asks for a downshift -- which is
why the trial reroute was reverted rather than shipped.

WHERE EACH LAYER COMES BACK FROM
--------------------------------
Nothing here invents a value. Every layer is re-read from the source that
produced it in the first place, against the NEW road:

    curves, ramps, posted limits   bake_curve_geometry.py --from-archive
    grade_segments                 Valhalla elevation, already in the archive
    state_miles, state_crossings   Census state boundaries
    checkpoints                    the curated towns, re-positioned
    interchanges                   build_interchanges.py, local OSM extract
    restrictions, ramp controls    the same, in sequence
    landmarks                      bake_landmarks.py (Overpass)
    villages                       bake_villages.py (checked-in OSM places)
    lane_segments                  bake_lane_segments.py (Overpass)
    traffic_aadt                   build_traffic_aadt.py (FHWA HPMS)
    hpms_terrain                   build_terrain_type.py (FHWA HPMS)

THE ARCHIVE IS THE ROUTE, NOT A ROUTER
--------------------------------------
Every builder above now reads the leg's polyline from
``world_data/us/geometry/`` (see ``tools/leg_geometry.py``) rather than
re-routing. That is not a convenience: a cached OpenRouteService or OSRM
answer for a rerouted leg is either a miss or, worse, a confident description
of the road the truck just left, and neither service is reachable from the
machine this bake runs on.

WHAT IT REFUSES TO CALL DONE
----------------------------
A builder that finds nothing and exits zero is the failure mode this whole
job has hit twice -- ``build_interchanges`` once retained 0 of 59,924 ramp
nodes and reported success. So the run ends by comparing every layer against
what the leg carried BEFORE, and a layer that comes back empty, or at less
than half its old size, fails the run and is named. Materially fewer rows
means a builder silently did nothing; it does not mean the new road is
quieter.

ORDER IS NOT ARBITRARY
----------------------
The curve/geometry bake goes first because it rewrites the archive at
production density and everything downstream reads it. Posted limits must
exist before the village bake, which pulls a town's name ahead of the speed
zone it explains. Interchanges must exist before ramp controls, which hang
off them. Landmarks and checkpoints must exist before villages, which dedupe
against both.

Usage
-----
    uv run python tools/reroute_enrich.py --check
    uv run python tools/reroute_enrich.py --leg a:b --pbf ~/osm/us-latest.osm.pbf
    uv run python tools/reroute_enrich.py --all-pending --pbf ... --write
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

# enrich_routes is the composed module: importing it is what wires the helper
# modules' private names into each other. Reaching into enrich_routes_ors
# directly gets a module whose own helpers are undefined -- fine_grade_samples
# raises NameError on _haversine_miles.
import enrich_routes as er  # noqa: E402
import enrich_routes_states as ers  # noqa: E402
import leg_geometry as lg  # noqa: E402
import reroute_leg as rr  # noqa: E402
import straw_curve_sample as scs  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

ROOT = TOOLS.parent
CACHE_PATH = ROOT / ".route-cache"

# How far apart to read the ground for the grade profile. The archive keeps
# every vertex a CURVE needs and thins the straights, which is right for
# steering and wrong for grade: a nine-mile tangent climb can survive as two
# vertices, and grading between them averages the whole climb into one number.
# So elevation is read afresh along the archived road at a fixed spacing.
# 0.1 mi is well under the 0.25 mi grade bin, so every bin has real ends.
ELEVATION_STEP_MI = 0.1

# READ, not derived: Valhalla returns the ground height at each point from its
# own DEM tiles. What is DERIVED from it -- named in the grade source below --
# is the rise over run between consecutive samples.
ELEVATION_SOURCE = (
    "Read from Valhalla /height (its own DEM tileset over OpenStreetMap) at "
    f"{ELEVATION_STEP_MI} mi spacing along the leg's checked-in route geometry."
)
GRADE_SOURCE = f"Derived: rise over run between elevation samples 0.25 mi apart. {ELEVATION_SOURCE}"

# A curated checkpoint carries the town's own coordinates, so a reroute moves
# WHERE on the leg it falls, not WHETHER the truck passes it. Re-position
# rather than re-curate -- but a town this far off the new road is one the
# truck no longer passes, and it goes.
MAX_OFF_ROUTE_MI = 3.0

# Layers this pass is responsible for. A leg that comes out of it missing one
# of these is not finished, whatever the builders said on their way past.
REBUILT_LAYERS = (
    "speed_limits",
    "grade_segments",
    "state_miles",
    "interchanges",
    "landmarks",
    "lane_segments",
    "traffic_aadt",
)
# ...of which these are only expected when a local OSM extract was supplied.
NEEDS_PBF = frozenset({"interchanges"})
# Layers that are legitimately empty on plenty of legs, so a change is
# reported and never fails the run.
SOFT_LAYERS = frozenset({"restrictions", "state_crossings", "checkpoints", "toll_events"})
# grade_segments is checked by COVERAGE, not by row count. The count is a
# function of how noisy the ground reads as much as of the terrain -- 147 flat
# Texas miles came back as 143 segments off one elevation source and 55 off
# another, and neither is "half missing". What must hold is that the profile
# covers the whole leg with no hole in it, because a hole is a stretch where
# the truck has no grade at all.
COVERAGE_LAYERS = frozenset({"grade_segments"})
COVERAGE_SLOP_MI = 0.2


def leg_id(leg: dict[str, Any]) -> str:
    return f"{leg['from']}:{leg['to']}"


def find_leg(world: dict[str, Any], wanted: str) -> dict[str, Any] | None:
    return next((leg for leg in world["legs"] if leg_id(leg) == wanted), None)


def layer_sizes(leg: dict[str, Any]) -> dict[str, int]:
    corridor = leg.get("corridor") or {}
    return {key: len(value) for key, value in corridor.items() if isinstance(value, list)}


# --- layers with no builder of their own ------------------------------------
def densify(coords: list[list[float]], step_mi: float = ELEVATION_STEP_MI) -> list[list[float]]:
    """The archived road with a point at least every ``step_mi``.

    Every archived vertex is kept -- they are where the road actually bends --
    and points are inserted along the long straights between them. Inserting
    on a tangent puts the sample on the pavement; the archive never thins a
    curve enough for that to be a guess.
    """
    out: list[list[float]] = [coords[0]]
    for start, end in zip(coords, coords[1:], strict=False):
        span_mi = scs._haversine_m(start[1], start[0], end[1], end[0]) / 1609.344
        steps = max(1, int(span_mi / step_mi))
        for i in range(1, steps):
            t = i / steps
            out.append([start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t])
        out.append(end)
    return out


def read_elevation(coords: list[list[float]]) -> list[float]:
    """Ground height in feet at every point, from Valhalla ``/height``."""
    out: list[float] = []
    for start in range(0, len(coords), 500):
        chunk = coords[start : start + 500]
        result = rr._post(
            "/height",
            {"shape": [{"lat": lat, "lon": lon} for lon, lat in chunk], "range": False},
        )
        if not result or "height" not in result:
            raise RuntimeError("Valhalla /height returned nothing for this leg")
        out.extend(float(metres) * 3.280839895 for metres in result["height"])
    if len(out) != len(coords):
        raise RuntimeError("Valhalla /height returned the wrong number of readings")
    return out


def rebuild_grades(leg: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(grade_segments, elevation_samples)`` for the road the leg now drives.

    Quarter-mile bins closed on accumulated distance, over a dense elevation
    read: fixed-width bins mean a sparse stretch cannot collapse several bins
    onto one vertex and report a 30 percent grade on flat interstate, and the
    dense read means a long tangent climb is not averaged away to nothing.
    """
    polyline = lg.archived_polyline(leg_id(leg), lg.state_code_of(leg))
    if polyline is None:
        raise RuntimeError(f"no archived geometry for {leg_id(leg)}")
    archived, _archived_elevations = polyline
    coords = densify(archived)
    elevations = read_elevation(coords)
    samples, sample_elevations = er.fine_grade_samples(
        {"coordinates": coords, "elevations_ft": elevations}, float(leg["miles"])
    )
    segments = er.grade_segments_from_samples(samples, sample_elevations, leg)
    for segment in segments:
        segment["source"] = GRADE_SOURCE
    # The stored elevation samples are the same read, thinned to the spacing
    # the rest of the network carries -- one every 25 miles.
    stored: list[dict[str, Any]] = []
    last = -1e9
    for sample, feet in zip(samples, sample_elevations, strict=False):
        if sample["at_mi"] - last < 25.0 and sample is not samples[-1]:
            continue
        last = sample["at_mi"]
        stored.append(
            {
                "at_mi": round(sample["at_mi"], 2),
                "elevation_ft": round(feet, 1),
                "source": ELEVATION_SOURCE,
            }
        )
    return segments, stored


def route_tolls(world: dict[str, Any], leg: dict[str, Any]) -> bool | None:
    """Does the road this leg now drives use a toll?

    ``tollway_detected`` is the flag behind the curation advisory that says
    "this leg is on a tollway and has no toll events on it". After a reroute
    the stored value answers that question about the road the truck left, so
    it is asked again -- of the same router, with the same loaded-semi
    profile, between the same two city nodes.
    """
    cities = world["cities"]
    fetched = rr.fetch_route(cities[leg["from"]], cities[leg["to"]])
    if fetched is None:
        return None
    _shape, _miles, has_toll = fetched
    return has_toll


def rebuild_states(
    world: dict[str, Any], leg: dict[str, Any], rate_limit: float
) -> dict[str, list[dict[str, Any]]]:
    """Which states the new road runs through, and for how many miles each."""
    polyline = lg.archived_polyline(leg_id(leg), lg.state_code_of(leg))
    if polyline is None:
        raise RuntimeError(f"no archived geometry for {leg_id(leg)}")
    coords, _elevations = polyline
    shapes = ers._load_state_shapes(CACHE_PATH, rate_limit)
    return ers._state_context(world, leg, coords, shapes)


def reposition_checkpoints(leg: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Move the curated towns onto the new road; drop the ones it left behind.

    A checkpoint is a real named place with real coordinates, curated once by
    hand. Rerouting changes the mile it falls at, not whether the town exists,
    so throwing the curation away and re-deriving it would be the expensive
    way to get a worse answer. A checkpoint with no coordinates cannot be
    placed -- that is the synthetic "corridor between" placeholder, which
    spoke as a place and should never have existed.
    """
    corridor = leg.get("corridor") or {}
    existing = list(corridor.get("checkpoints") or [])
    if not existing:
        return [], []
    polyline = lg.archived_polyline(leg_id(leg), lg.state_code_of(leg))
    if polyline is None:
        raise RuntimeError(f"no archived geometry for {leg_id(leg)}")
    coords, _elevations = polyline
    kept, dropped = lg.reposition_on_route(existing, coords, float(leg["miles"]), MAX_OFF_ROUTE_MI)
    for record in kept:
        off_mi = record.pop("_off_mi")
        record["source"] = (
            f"Real town on {leg.get('highway')} between {leg['from']} and {leg['to']}; "
            "position matched to the nearest point on the leg's checked-in route "
            f"geometry ({off_mi:.2f} mi off-route at closest approach)."
        )
    notes = [
        f"{record.get('name')} "
        + ("(no coordinates)" if off_mi == float("inf") else f"({off_mi:.1f} mi off the new road)")
        for record, off_mi in dropped
    ]
    return kept, notes


# --- delegated builders -----------------------------------------------------
def run(command: list[str], label: str) -> bool:
    print(f"\n=== {label} ===\n$ {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        print(f"    {label} exited {result.returncode}", flush=True)
    return result.returncode == 0


def python_tool(name: str, *args: str) -> list[str]:
    return [sys.executable, str(TOOLS / name), *args]


def delegated_steps(
    only_colon: str, only_arrow: str, pbf: Path | None, write: bool
) -> list[tuple[str, list[str]]]:
    """Every builder that already knows how to rebuild its own layer.

    The interchange family reads a local OSM extract and keys its index cache
    to the selected legs' bounds, so all the legs go through in ONE run per
    sub-mode. The sub-mode flags do not compose -- passing several dispatches
    to one and silently skips the rest -- so they are three separate runs.
    """
    write_flag = ["--write"] if write else []
    steps: list[tuple[str, list[str]]] = []
    if write:
        # bake_curve_geometry has no dry run: it always writes its shards.
        # So it is SKIPPED without --write, rather than quietly re-baking the
        # geometry archive during what the caller asked for as a rehearsal.
        steps.append(
            (
                "curves, ramps and posted limits",
                python_tool("bake_curve_geometry.py", "--only", only_colon, "--from-archive"),
            )
        )
    if pbf is not None:
        for label, extra in (
            ("interchanges", []),
            ("height and weight restrictions", ["--restrictions"]),
            ("ramp terminal controls", ["--ramp-controls"]),
        ):
            steps.append(
                (
                    label,
                    python_tool(
                        "build_interchanges.py",
                        "--pbf",
                        str(pbf),
                        "--only",
                        only_arrow,
                        "--force",
                        *write_flag,
                        *extra,
                    ),
                )
            )
    steps += [
        ("landmarks", python_tool("bake_landmarks.py", "--only", only_colon, *write_flag)),
        ("villages", python_tool("bake_villages.py", "--only", only_colon, *write_flag)),
        (
            "lane segments",
            python_tool("bake_lane_segments.py", "--only", only_colon, *write_flag),
        ),
        (
            "traffic volume",
            python_tool("build_traffic_aadt.py", "--only", only_arrow, "--force", *write_flag),
        ),
        (
            "HPMS terrain class",
            python_tool("build_terrain_type.py", "--only", only_arrow, "--force", *write_flag),
        ),
    ]
    return steps


# --- the pass ---------------------------------------------------------------
def pending_legs(world: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        leg
        for leg in world["legs"]
        if leg.get("rerouted") and not (leg.get("corridor") or {}).get("interchanges")
    ]


def grade_coverage_gaps(leg: dict[str, Any]) -> list[str]:
    """Stretches of the leg its grade profile does not describe."""
    segments = sorted(
        (leg.get("corridor") or {}).get("grade_segments") or [],
        key=lambda row: float(row["start_mi"]),
    )
    if not segments:
        return ["no grade profile at all"]
    gaps: list[str] = []
    miles = float(leg["miles"])
    if float(segments[0]["start_mi"]) > COVERAGE_SLOP_MI:
        gaps.append(f"starts at mile {segments[0]['start_mi']}, not 0")
    for before, after in zip(segments, segments[1:], strict=False):
        if float(after["start_mi"]) - float(before["end_mi"]) > COVERAGE_SLOP_MI:
            gaps.append(f"nothing between mile {before['end_mi']} and {after['start_mi']}")
    if miles - float(segments[-1]["end_mi"]) > COVERAGE_SLOP_MI:
        gaps.append(f"ends at mile {segments[-1]['end_mi']}, not {miles}")
    return gaps


def report_completeness(
    before: dict[str, dict[str, int]], world: dict[str, Any], expect_interchanges: bool
) -> int:
    """Name every layer that came back empty or materially thinner.

    A route change genuinely moves counts -- a shorter road passes fewer
    towns, and a re-read of today's OpenStreetMap is not the read that was
    taken a month ago. What it does not do is take a layer to zero, or halve
    it. Both are what a builder looks like when it silently did nothing,
    which has happened twice on this job, so both fail the run.
    """
    failures = 0
    print("\n\n=== what each leg carries now ===")
    for wanted, old in before.items():
        leg = find_leg(world, wanted)
        if leg is None:
            continue
        new = layer_sizes(leg)
        expected = [
            layer for layer in REBUILT_LAYERS if expect_interchanges or layer not in NEEDS_PBF
        ]
        print(f"\n{wanted}  ({leg.get('highway')}, {leg['miles']} mi)")
        for layer in sorted(set(old) | set(new) | set(expected)):
            was, now = old.get(layer, 0), new.get(layer, 0)
            verdict = ""
            if layer in COVERAGE_LAYERS:
                gaps = grade_coverage_gaps(leg)
                if gaps:
                    verdict = "  HOLES: " + "; ".join(gaps)
                    failures += 1
                else:
                    verdict = "  covers the leg end to end"
            elif layer in expected and now == 0:
                verdict, failures = "  EMPTY -- the builder did nothing", failures + 1
            elif layer in expected and was and now < was / 2:
                verdict, failures = "  THIN -- under half what it was", failures + 1
            elif layer in SOFT_LAYERS and was and not now:
                verdict = "  (gone; soft layer, not a failure)"
            print(f"  {layer:20s} {was:5d} -> {now:5d}{verdict}")
        if not expect_interchanges:
            print("  (interchanges, restrictions and ramp controls were not run: no --pbf)")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--leg", action="append", default=[], help="leg id a:b (repeatable)")
    ap.add_argument(
        "--all-pending",
        action="store_true",
        help="every leg reroute_leg.py left incomplete",
    )
    ap.add_argument("--check", action="store_true", help="list incomplete legs and stop")
    ap.add_argument("--pbf", type=Path, help="local OSM extract for the interchange family")
    ap.add_argument("--write", action="store_true", help="apply (default is a dry run)")
    ap.add_argument(
        "--derived-only",
        action="store_true",
        help="skip the builders that re-read OpenStreetMap and HPMS, and "
        "re-derive only what this tool owns: grades, elevation, state "
        "context, checkpoint positions and the tollway flag. Minutes rather "
        "than hours, for when only those changed.",
    )
    ap.add_argument("--rate-limit", type=float, default=1.0)
    args = ap.parse_args()

    world = load_world()
    if args.check:
        pending = pending_legs(world)
        print(f"{len(pending)} legs rerouted but not re-enriched:")
        for leg in pending:
            print(f"  {leg_id(leg)}")
        return 1 if pending else 0

    wanted: list[str] = []
    for entry in args.leg:
        wanted.extend(part.strip() for part in entry.split(";") if part.strip())
    if args.all_pending:
        wanted.extend(leg_id(leg) for leg in pending_legs(world))
    wanted = list(dict.fromkeys(wanted))
    if not wanted:
        ap.error("nothing selected: pass --leg, --all-pending or --check")

    legs = []
    for name in wanted:
        leg = find_leg(world, name)
        if leg is None:
            print(f"no such leg: {name}")
            return 1
        if lg.archived_polyline(name, lg.state_code_of(leg)) is None:
            print(f"{name} has no archived polyline -- run reroute_leg.py first")
            return 1
        legs.append(leg)

    before = {leg_id(leg): layer_sizes(leg) for leg in legs}
    only_colon = ";".join(wanted)
    only_arrow = ";".join(name.replace(":", "->") for name in wanted)
    print(f"finishing {len(legs)} rerouted legs:")
    for leg in legs:
        print(f"  {leg_id(leg):46s} {leg.get('highway'):10s} {leg['miles']} mi")
    if args.pbf is None:
        print("\n  no --pbf: interchanges, restrictions and ramp controls will be SKIPPED")
    if not args.write:
        print(
            "\n(dry run: the builders will not write, and the curve and "
            "geometry re-bake is skipped entirely -- it has no dry run of its own)"
        )

    failed_steps = []
    if args.derived_only:
        print("\n(--derived-only: the OpenStreetMap and HPMS builders are skipped)")
    else:
        for label, command in delegated_steps(only_colon, only_arrow, args.pbf, args.write):
            if not run(command, label):
                failed_steps.append(label)

    # The layers with no builder of their own, done in this process because
    # they are three short derivations rather than three more tools. Re-read
    # the world first: every step above wrote to it.
    world = load_world()
    print("\n=== grades, state context and checkpoints ===")
    for name in wanted:
        leg = find_leg(world, name)
        if leg is None:
            continue
        corridor = leg.setdefault("corridor", {})
        grades, elevation = rebuild_grades(leg)
        corridor["grade_segments"] = grades
        corridor["elevation_samples"] = elevation
        states = rebuild_states(world, leg, args.rate_limit)
        corridor["state_miles"] = states["state_miles"]
        if states["state_crossings"]:
            corridor["state_crossings"] = states["state_crossings"]
        else:
            corridor.pop("state_crossings", None)
        moved, dropped = reposition_checkpoints(leg)
        if moved or dropped:
            corridor["checkpoints"] = moved
        tolls = route_tolls(world, leg)
        if tolls is not None:
            corridor["tollway_detected"] = tolls
        terrain = {segment["terrain"] for segment in grades}
        print(
            f"  {name}: {len(grades)} grade segments ({', '.join(sorted(terrain))}), "
            f"{len(states['state_miles'])} states, "
            f"{len(states['state_crossings'])} crossings, "
            f"{len(moved)} checkpoints kept, "
            f"{'tolls' if tolls else 'no toll'}"
        )
        if tolls and not (corridor.get("toll_events") or []):
            print("      on a tollway with no toll events -- wants curating")
        for note in dropped:
            print(f"      dropped checkpoint: {note}")
    if args.write:
        save_world(world)
        print("\nwrote the world source")

    failures = report_completeness(before, world, args.pbf is not None or args.derived_only)
    if failed_steps:
        print("\nBUILDERS THAT EXITED NON-ZERO: " + ", ".join(failed_steps))
    if failures or failed_steps:
        print(
            f"\n{failures} layers came back empty or thin. That is what a builder "
            "looks like when it silently did nothing -- read the step output above "
            "before trusting this leg."
        )
        return 1
    print("\nevery rebuilt layer is present and no thinner than half what it was.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
