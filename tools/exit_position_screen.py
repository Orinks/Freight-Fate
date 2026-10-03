"""Does a leg's interchange mileage still agree with the road it drives?

Every ramp fact the interchange bake reads (control, far end, length,
terminal) is looked up at the point of the leg's polyline where an exit's
``at_mi`` falls. An exit pinned to its own OSM junction node by ref does not
need that, but an unpinned one does, and on a leg rerouted after its
interchanges were discovered the two disagree: Charlotte to Knoxville's
exits sit a median 8 miles from where their own numbered junctions lie on
the polyline, Rochester to New York's by more. Looked up there, an unpinned
exit reads whatever ramp happens to be nearby, or none.

The screen is a self-contradiction test, not a tuned cut: for every labelled
exit, find a junction node carrying the same exit ref ON the polyline, take
the one nearest the exit's own mileage, and measure the gap. When the median
gap is wider than the far-end search radius around an unpinned exit, that
search cannot be looking at the right exit, so the bake withholds a verdict.
"""

from __future__ import annotations

import math
import re
import statistics
from typing import Any

EARTH_RADIUS_M = 6371008.8
# Fewer matches than this and the leg is not judged (the old behaviour).
MIN_MATCHES = 3


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def leg_position_drift_mi(
    geom: list[tuple[float, float, float]],
    interchanges: list[dict[str, Any]],
    leg_miles: float,
    junction_refs: dict[str, list[tuple[float, float]]],
    on_road_m: float,
) -> float | None:
    """Median gap, in polyline miles, between each labelled exit's ``at_mi``
    and the nearest junction node with its ref lying within ``on_road_m`` of
    a polyline vertex; None with fewer than ``MIN_MATCHES`` matches."""
    if not geom or not leg_miles:
        return None
    scale = (geom[-1][2] or leg_miles) / leg_miles
    grid: dict[tuple[int, int], list[int]] = {}
    for i, (lat, lon, _mi) in enumerate(geom):
        grid.setdefault((int(lat * 20), int(lon * 20)), []).append(i)
    gaps = []
    for ix in interchanges:
        ref = re.sub(r"\s+", "", str(ix.get("exit_ref", "")))
        target = float(ix.get("at_mi", 0.0)) * scale
        best = None
        for lat, lon in junction_refs.get(ref, ()) if ref else ():
            cell = (int(lat * 20), int(lon * 20))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    for i in grid.get((cell[0] + dy, cell[1] + dx), ()):
                        if _dist_m(lat, lon, geom[i][0], geom[i][1]) <= on_road_m:
                            gap = abs(geom[i][2] - target)
                            best = gap if best is None else min(best, gap)
        if best is not None:
            gaps.append(best)
    return statistics.median(gaps) if len(gaps) >= MIN_MATCHES else None
