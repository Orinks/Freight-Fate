"""Regenerate selected route_points from their archived dense geometry."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import leg_geometry as lg  # noqa: E402
import reroute_leg as reroute  # noqa: E402
import straw_curve_sample as scs  # noqa: E402
from world_source import load_world, save_world  # noqa: E402


def route_points_from_archive(leg: dict) -> list[dict[str, float]]:
    archived = lg.archived_polyline(lg.leg_id_of(leg), lg.state_code_of(leg))
    if archived is None:
        raise ValueError(f"No archived dense geometry for {lg.leg_id_of(leg)}")
    shape, _elevations = archived
    if len(shape) < 2:
        raise ValueError(f"Archived geometry for {lg.leg_id_of(leg)} has fewer than two points")
    cumulative_m = scs._cumulative_m(shape)
    return [
        {
            "at_mi": round(at_mi, 2),
            "lat": round(shape[index][1], 5),
            "lon": round(shape[index][0], 5),
        }
        for index, at_mi in reroute.sampled_route_indices(cumulative_m, float(leg["miles"]))
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--leg",
        action="append",
        required=True,
        help="Leg id, from_slug:to_slug.",
    )
    parser.add_argument("--write", action="store_true", help="Save the updated world source.")
    args = parser.parse_args(argv)

    world = load_world()
    legs = {f"{leg['from']}:{leg['to']}": leg for leg in world["legs"]}
    for leg_id in args.leg:
        leg = legs.get(leg_id)
        if leg is None:
            parser.error(f"No world leg {leg_id!r}")
        points = route_points_from_archive(leg)
        leg.setdefault("corridor", {})["route_points"] = points
        print(f"{leg_id}: regenerated {len(points)} route points from archived geometry")
    if args.write:
        save_world(world)
        print("Wrote the world source -- now run: uv run python tools/index_world.py")
    else:
        print("Dry run (pass --write to save).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
