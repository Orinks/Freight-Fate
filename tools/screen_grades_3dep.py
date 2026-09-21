"""Check the steepest baked grades against USGS 3DEP, and report. Never edit.

The world's 146,496 grade segments all come from one OpenRouteService
elevation profile over SRTM, and `ffworld.grades` already screens
them at load -- but it screens for SELF-CONTRADICTION, capping any slope
steeper than the road's class and terrain can hold. That is the right rule
with no second opinion available. This tool is the second opinion.

USGS 3DEP is keyless, public domain, and 1 to 10 metres where SRTM is 30, so
for a US-only map it is the authoritative reading. Sampling it along the same
span the profile measured answers the question the load screen cannot:

  * the profile says 14 percent, 3DEP says 2 -- an artifact, and the clamp
    was right to cap it, though it is still capping to a ceiling rather than
    to the truth;
  * the profile says 6.4 percent and 3DEP agrees, on a US route the clamp is
    holding at 6 -- a real grade the driver is not getting.

What the first full run taught, and why the verdicts are not just those two:
two elevation models agreeing does NOT make a slope real. Both read ground,
and over three tenths of a mile in the Appalachians the ground under a bridge
is not the road on it. 47 spans came back with 3DEP confirming 10 to 13
percent on an INTERSTATE, which is not a grade any interstate holds. That is a
shared blind spot, not a measurement, and no second elevation model can close
it -- which is why `grades.py` leads with road class rather than terrain.

By default nothing is written: the provenance rule in `CLAUDE.md` is that a
screen reports and the bake stays readable, because a screen that deletes what
it rejects cannot be re-judged when the rule turns out too broad. `--write`
does the one thing that is not a screen -- it RE-SOURCES a slope, replacing a
profile reading with a 3DEP reading and recording the profile's own number in
`source`, so the swap is reversible by reading rather than by guessing. It
only ever writes a value the road class could hold, so the shared bridge
blind spot above is never baked in.

Samples are cached by coordinate, so a second run costs nothing and works
offline over whatever the first run already read.

Usage::

    uv run python tools/screen_grades_3dep.py --limit 40
    uv run python tools/screen_grades_3dep.py --over-ceiling --report grades.md
    uv run python tools/screen_grades_3dep.py --over-ceiling --offline --write
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import leg_geometry as lg  # noqa: E402
from ffworld.grades import (  # noqa: E402
    CLASS_CEILING_PCT,
    grade_ceiling_pct,
    road_class,
)
from world_source import load_world, save_world  # noqa: E402

SAMPLES_URL = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/getSamples"
)
USER_AGENT = "FreightFate/1.9 (accessible trucking game; https://orinks.net)"

CACHE_PATH = Path(
    os.environ.get("FF_3DEP_CACHE", Path.home() / ".cache" / "freight-fate-3dep" / "samples.json")
)

#: The service takes a multipoint and answers in about 0.2 s a point. A
#: hundred at a time keeps one request inside a sane timeout.
BATCH = 100
REQUEST_TIMEOUT_S = 120
RETRIES = 3

METRES_TO_FEET = 3.280839895
FEET_PER_MILE = 5280.0

#: Coordinates are keyed to six decimals, which is about 0.1 m -- finer than
#: the data and fine enough that two runs over the same polyline hit the cache.
COORD_PRECISION = 6

#: Below this the span is too short to read a slope off two elevations: a
#: bridge deck, a ramp nose, one vertex of noise. Reported, not judged.
MIN_SPAN_MI = 0.05

#: How far the two readings may differ before the row is worth a human. In
#: percent of slope, not relative -- half a percent of grade is about the
#: resolution of the question a driver can hear.
AGREE_WITHIN_PCT = 1.5

#: Written into a re-sourced segment's `source`, and the thing a second run
#: looks for so it never re-reads its own reading as if it were the profile's.
MEASURED_MARKER = "Slope re-read at USGS 3DEP"
MEASURED_NOTE = (
    " {marker}: {measured:+.2f} percent measured over this span, replacing the "
    "{profile:+.2f} the OpenRouteService/SRTM profile gave -- READ, not derived "
    "(USGS 3DEP, public domain, 1 to 10 m; sampled {accessed} by "
    "tools/screen_grades_3dep.py)."
).replace("{marker}", MEASURED_MARKER)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Screen this many of the steepest segments (default 40).",
    )
    parser.add_argument(
        "--over-ceiling",
        action="store_true",
        help="Screen every segment the load-time clamp would cap, instead of --limit.",
    )
    parser.add_argument("--report", type=Path, help="Write the table to this file too.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use only cached samples; skip anything not already read.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Re-source segments whose 3DEP reading the road class can hold.",
    )
    args = parser.parse_args(argv)

    world = load_world()
    candidates = steepest_segments(world, over_ceiling=args.over_ceiling)
    if not args.over_ceiling:
        candidates = candidates[: args.limit]
    if not candidates:
        print("nothing to screen")
        return 0

    cache = _load_cache()
    wanted = {pt for row in candidates for pt in row["points"]}
    missing = sorted(wanted - cache.keys())
    print(
        f"{len(candidates)} segments, {len(wanted)} points "
        f"({len(missing)} to read, {len(wanted) - len(missing)} cached)",
        file=sys.stderr,
    )
    if missing and not args.offline:
        _fill_cache(cache, missing)

    rows = [judged(row, cache) for row in candidates]
    rows = [row for row in rows if row is not None]
    text = render(rows)
    print(text)
    if args.report:
        args.report.write_text(text, encoding="utf-8")

    if args.write:
        written = write_measurements(rows)
        save_world(world)
        print(f"\nre-sourced {written} segments from 3DEP; world_source written", file=sys.stderr)
    return 0


def write_measurements(rows: list[dict[str, Any]]) -> int:
    """Replace a profile slope with the 3DEP reading where the class allows it.

    A measurement beats a clamp: the load screen's ceiling is a guess at what
    the road can hold, and where 3DEP has read the same span there is a number
    instead. But only where the road class could hold it -- the 165 spans
    where 3DEP itself reads 10 to 13 percent on an interstate are the shared
    bridge blind spot, and writing those would bake the artifact in for good.
    Those are left exactly as they are, for the load screen to clamp as now.

    The profile's own value goes into `source`, so this is reversible by
    reading rather than by guessing.
    """
    written = 0
    for row in rows:
        segment = row.get("segment")
        if segment is None or MEASURED_MARKER in str(segment.get("source") or ""):
            continue
        if abs(row["dep_pct"]) > CLASS_CEILING_PCT[road_class(row["highway"])]:
            continue
        segment["source"] = (
            str(segment.get("source") or "").strip()
            + MEASURED_NOTE.format(
                measured=row["dep_pct"],
                profile=row["profile_pct"],
                accessed=date.today().isoformat(),
            )
        ).strip()
        segment["avg_grade_pct"] = row["dep_pct"]
        written += 1
    return written


def steepest_segments(world: dict[str, Any], *, over_ceiling: bool) -> list[dict[str, Any]]:
    """Grade segments worth a second reading, steepest first.

    Each row carries the leg, the span, what the profile said, the ceiling the
    load screen would apply, and the coordinates to sample.
    """
    rows: list[dict[str, Any]] = []
    for leg in world.get("legs", []):
        corridor = leg.get("corridor") or {}
        segments = corridor.get("grade_segments") or []
        if not segments:
            continue
        highway = leg.get("highway") or ""
        # The corridor stores the whole HPMS record; the load screen reads
        # only its Green Book class number off `type`.
        hpms_record = corridor.get("hpms_terrain") or {}
        hpms = hpms_record.get("type") if isinstance(hpms_record, dict) else hpms_record
        polyline: list[tuple[float, float, float]] | None = None
        for segment in segments:
            start = float(segment["start_mi"])
            end = float(segment["end_mi"])
            if end - start < MIN_SPAN_MI:
                continue
            terrain = _terrain_label(hpms) or segment.get("terrain") or "flat"
            ceiling = grade_ceiling_pct(highway, terrain)
            profile_pct = float(segment["avg_grade_pct"])
            if over_ceiling and abs(profile_pct) <= ceiling:
                continue
            if polyline is None:
                polyline = lg.corridor_geometry(leg) or []
            points = _span_points(polyline, start, end)
            if len(points) < 2:
                continue
            rows.append(
                {
                    "leg": f"{leg.get('from')} -> {leg.get('to')}",
                    "highway": highway,
                    "class": road_class(highway),
                    "terrain": terrain,
                    "start_mi": start,
                    "end_mi": end,
                    "profile_pct": profile_pct,
                    "ceiling_pct": ceiling,
                    "points": points,
                    # The segment dict itself, so --write can re-source it in
                    # place without matching the row back to the world.
                    "segment": segment,
                }
            )
    rows.sort(key=lambda r: abs(r["profile_pct"]), reverse=True)
    return rows


def judged(row: dict[str, Any], cache: dict[str, float]) -> dict[str, Any] | None:
    """Add 3DEP's own slope over the same span, and a verdict."""
    read = [cache[pt] for pt in row["points"] if pt in cache]
    if len(read) < 2:
        return None
    rise_ft = (read[-1] - read[0]) * METRES_TO_FEET
    run_ft = (row["end_mi"] - row["start_mi"]) * FEET_PER_MILE
    row["dep_pct"] = round(rise_ft / run_ft * 100.0, 2)
    row["gap_pct"] = round(row["profile_pct"] - row["dep_pct"], 2)

    clamped = abs(row["profile_pct"]) > row["ceiling_pct"]
    agrees = abs(row["gap_pct"]) <= AGREE_WITHIN_PCT
    # Two elevation models agreeing is NOT proof a slope is real: both read the
    # ground, and over a tenth of a mile in the Appalachians the ground under a
    # bridge is not the road on it. The first run found 47 spans where 3DEP
    # confirmed the profile at 10 to 13 percent on an interstate, which is not
    # a grade any interstate holds. A confirmation the road class forbids is a
    # shared blind spot, so it gets its own verdict rather than counting as a
    # real grade the clamp is taking away.
    class_ceiling = CLASS_CEILING_PCT[road_class(row["highway"])]
    impossible = abs(row["dep_pct"]) > class_ceiling
    if agrees and not clamped:
        row["verdict"] = "confirmed"
    elif agrees and impossible:
        row["verdict"] = "both models, class forbids"
    elif agrees:
        row["verdict"] = "REAL, CLAMPED"
    elif clamped and abs(row["dep_pct"]) <= row["ceiling_pct"]:
        row["verdict"] = "artifact, clamp right"
    else:
        row["verdict"] = "disagrees"
    return row


def render(rows: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    out = [
        "# Baked grades against USGS 3DEP",
        "",
        f"{len(rows)} segments read. "
        + ", ".join(f"{v} {k}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])),
        "",
        "3DEP is public domain, 1 to 10 m, sampled over the same span the "
        "OpenRouteService/SRTM profile measured. A row is only ever re-sourced "
        "(--write) when the road class could hold the reading.",
        "",
        "| Leg | Highway | Span (mi) | Profile % | 3DEP % | Ceiling | Verdict |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        out.append(
            f"| {row['leg']} | {row['highway']} | "
            f"{row['start_mi']:.1f}-{row['end_mi']:.1f} | "
            f"{row['profile_pct']:+.2f} | {row['dep_pct']:+.2f} | "
            f"{row['ceiling_pct']:.0f} | {row['verdict']} |"
        )
    return "\n".join(out) + "\n"


# ---- sampling ------------------------------------------------------------


def _terrain_label(hpms: int | None) -> str | None:
    return {1: "flat", 2: "hills", 3: "mountain"}.get(hpms) if hpms else None


def _span_points(
    polyline: list[tuple[float, float, float]], start_mi: float, end_mi: float
) -> list[str]:
    """The archived vertices inside a span, as cache keys, ends first and last.

    Only the ends decide the slope; the vertices between them are carried so a
    later pass can look at the shape without re-reading the leg.
    """
    inside = [p for p in polyline if start_mi <= p[2] <= end_mi]
    if len(inside) < 2:
        # A span shorter than the archive's vertex spacing: take the vertex on
        # each side of it rather than nothing.
        before = [p for p in polyline if p[2] <= start_mi]
        after = [p for p in polyline if p[2] >= end_mi]
        if not before or not after:
            return []
        inside = [before[-1], after[0]]
    return [_key(p[0], p[1]) for p in inside]


def _key(lat: float, lon: float) -> str:
    return f"{round(lat, COORD_PRECISION)},{round(lon, COORD_PRECISION)}"


def _load_cache() -> dict[str, float]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict[str, float]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def _fill_cache(
    cache: dict[str, float],
    keys: list[str],
    *,
    sampler: Callable[[list[tuple[float, float]]], list[float | None]] | None = None,
) -> None:
    """Read every missing coordinate, saving after each batch.

    Saving per batch rather than at the end means a run that dies partway
    leaves its work behind instead of starting over.
    """
    read = sampler or _get_samples
    for index in range(0, len(keys), BATCH):
        chunk = keys[index : index + BATCH]
        points = [tuple(float(part) for part in key.split(",")) for key in chunk]
        try:
            values = read(points)  # type: ignore[arg-type]
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"3dep: batch failed ({exc}); keeping what is cached", file=sys.stderr)
            break
        for key, value in zip(chunk, values, strict=False):
            if value is not None:
                cache[key] = value
        _save_cache(cache)
        print(f"  read {min(index + BATCH, len(keys))}/{len(keys)}", file=sys.stderr)


def _get_samples(points: list[tuple[float, float]]) -> list[float | None]:
    """Elevation in metres for each (lat, lon), or None where 3DEP has none."""
    geometry = {
        "points": [[lon, lat] for lat, lon in points],
        "spatialReference": {"wkid": 4326},
    }
    body = urllib.parse.urlencode(
        {
            "geometry": json.dumps(geometry),
            "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true",
            "sampleCount": str(len(points)),
            "f": "json",
        }
    ).encode()
    payload = _post(body)
    # The service answers in its own order and drops points it cannot read, so
    # results are placed by locationId rather than by position.
    out: list[float | None] = [None] * len(points)
    for sample in payload.get("samples", []):
        try:
            slot = int(sample["locationId"])
            out[slot] = float(sample["value"])
        except (KeyError, ValueError, IndexError, TypeError):
            continue
    return out


def _post(body: bytes) -> dict[str, Any]:
    request = urllib.request.Request(SAMPLES_URL, data=body, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
                text = response.read().decode("utf-8")
            # 3DEP answers an out-of-coverage request with HTTP 200 and a
            # plain-text body ("Call failed."), so the status proves nothing.
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"3DEP returned a non-JSON body: {text[:80]!r}") from exc
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_error = exc
            if attempt == RETRIES - 1:
                break
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError("unable to reach the 3DEP sample service") from last_error


if __name__ == "__main__":
    raise SystemExit(main())
