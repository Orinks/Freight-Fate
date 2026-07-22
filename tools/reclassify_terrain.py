"""Relief-aware terrain reclassification for grade segments and legs.

Background
----------
The enrichment pipeline's ``_terrain_for_grade`` labels any grade segment
steeper than 3.0% "mountain" from *point steepness alone* -- no relief
context, no duration. A single 4-5% creek-crossing roller in the East
Texas piney woods or a Hill Country dip therefore reads "mountain," and
the status readout tells a Texan they are in the mountains. Josh reported
exactly this ("central Texas shows as mountains"), 2026-07-19.

This tool recomputes the ``terrain`` label of every grade segment and
every leg from the archived dense elevation profiles
(``world_data/us/geometry/<state>.jsonl``), using a +/-5 mile relief
window around each segment. It is label-only: ``avg_grade_pct`` and every
other number a physics model reads is left untouched.

The rule (terrain is relief in context, not one steep spot)
-----------------------------------------------------------
The leg's dense profile is median-filtered (``MEDIAN_MI``) to kill
bridge/overpass spikes, then classified in fixed ``0.25``-mile bins. Each
bin asks :func:`terrain_rules.terrain_for` with two measurements:

* steepness -- the steepest grade held a mile anywhere within
  ``LOCAL_STEEP_MI`` of the bin (tight enough not to smear a lone pitch,
  loose enough that a winding climb still reads steep).
* relief -- max minus min elevation in the wider ``WINDOW_MI`` context,
  plus a count of repeated stiff pitches for the big-relief path.

A grade segment's label becomes the terrain of the bins it spans (the
majority, mountain winning ties). A **runaway ramp** overrides to mountain:
a highway=escape way is built only on a real steep descent, so its bins and
the segment carrying it are mountain regardless of the smoothed profile
(a short pitch can average below the sustained bar).

Segment labels are the honest local truth and may fall -- that IS the Texas
fix. The **leg** label (the human-facing summary, two dozen of them pinned to
real geography in ``test_world``) only ever firms UP: a flat leg that really
crosses a pass becomes mountain (the Grapevine), but a curated hills/mountain
leg is never silently downgraded off a stricter geometric read. That is the
brief's rank-merge rule.

The verdict thresholds -- what counts as steep, as real relief, as a
mountain leg -- live in ``terrain_rules`` so the live enrichment pipeline
reaches the same verdict. They were tuned against the acceptance list in
``docs/terrain-audit-brief.md`` (``--acceptance`` runs it): Texas Hill
Country / East Texas read flat/hills (their steepest sustained mile tops out
at 4.2% statewide, under the 5% solo-mountain bar), while the Grapevine,
the Siskiyous, Monteagle, Denver-Silverthorne, and all 96 runaway-ramp
sites stay mountain.

Usage
-----
``uv run python tools/reclassify_terrain.py``            dry-run, full report
``uv run python tools/reclassify_terrain.py --acceptance`` add the acceptance harness
``uv run python tools/reclassify_terrain.py --state TX``  restrict the report
``uv run python tools/reclassify_terrain.py --write``     save via world_source, then
                                                          regenerate with index_world.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from terrain_rules import RANK, leg_terrain, terrain_for  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY_DIR = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "geometry"
RAMPS_PATH = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "gameplay" / "ramps.jsonl"

M_TO_FT = 3.280839895

# The verdict thresholds live in ``terrain_rules`` (shared with the enrichment
# pipeline so the two paths never drift). These are only how THIS tool measures
# the dense archived elevation profile before asking terrain_rules for a verdict.
WINDOW_MI = 5.0          # +/- relief window around a point (mountain-relief context)
LOCAL_STEEP_MI = 1.5     # +/- window for local steepness (the steepest held mile near here)
MEDIAN_MI = 0.6          # elevation median-filter window (kills bridge spikes)
SUSTAIN_MI = 1.0         # a grade must hold this far to count as "sustained"
PITCH_MI = 0.5           # a "pitch" is a run this long
PITCH_PCT = 3.0          # ...steeper than this


# --------------------------------------------------------------------------- #
# Geometry decode
# --------------------------------------------------------------------------- #
def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.7613  # earth radius, miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def decode_profile(geom: dict[str, Any], leg_miles: float) -> list[tuple[float, float]]:
    """Return [(mile, elevation_ft), ...] along the leg, scaled to leg_miles.

    ``geom`` is the delta-encoded record from a geometry shard: integer
    lat0/lon0 and dlat/dlon quantized at 10**q, delta elevations in meters.
    """
    q = geom["q"]
    scale = 10 ** q
    lat = geom["lat0"] / scale
    lon = geom["lon0"] / scale
    elev_m = float(geom["ele0_m"])
    dlat, dlon, dele = geom["dlat"], geom["dlon"], geom["dele_m"]

    raw: list[tuple[float, float, float]] = [(0.0, lat, elev_m)]  # (raw_mi, lat, elev_m)
    cum = 0.0
    plat, plon = lat, lon
    for i in range(len(dlat)):
        lat = plat + dlat[i] / scale
        lon = plon + dlon[i] / scale
        elev_m += dele[i]
        cum += _haversine_mi(plat, plon, lat, lon)
        raw.append((cum, lat, elev_m))
        plat, plon = lat, lon

    total_raw = raw[-1][0] or 1.0
    k = (leg_miles or total_raw) / total_raw
    return [(mi * k, em * M_TO_FT) for (mi, _lat, em) in raw]


def median_filter(profile: list[tuple[float, float]], window_mi: float) -> list[tuple[float, float]]:
    """Median-filter the elevation column over a +/- window_mi/2 window.

    Removes single-point river-bluff/overpass spikes the census caught
    faking a 7.5% grade in Minnesota farmland, without moving mileage.
    """
    if len(profile) < 3:
        return profile
    half = window_mi / 2.0
    miles = [p[0] for p in profile]
    out: list[tuple[float, float]] = []
    lo = 0
    hi = 0
    n = len(profile)
    for mi, _elev in profile:
        while lo < n and miles[lo] < mi - half:
            lo += 1
        while hi < n and miles[hi] <= mi + half:
            hi += 1
        window = sorted(profile[j][1] for j in range(lo, hi))
        m = len(window)
        med = window[m // 2] if m % 2 else (window[m // 2 - 1] + window[m // 2]) / 2.0
        out.append((mi, med))
    return out


# --------------------------------------------------------------------------- #
# Window measurements
# --------------------------------------------------------------------------- #
def _window(profile: list[tuple[float, float]], lo_mi: float, hi_mi: float) -> list[tuple[float, float]]:
    return [p for p in profile if lo_mi <= p[0] <= hi_mi]


def window_relief_ft(win: list[tuple[float, float]]) -> float:
    if not win:
        return 0.0
    elevs = [e for _, e in win]
    return max(elevs) - min(elevs)


def max_sustained_grade(win: list[tuple[float, float]], run_mi: float) -> float:
    """Steepest |grade %| held over any >= run_mi run inside the window."""
    if len(win) < 2:
        return 0.0
    best = 0.0
    j = 0
    n = len(win)
    for i in range(n):
        while j < n and win[j][0] - win[i][0] < run_mi:
            j += 1
        if j >= n:
            break
        dmi = win[j][0] - win[i][0]
        if dmi <= 0:
            continue
        grade = abs(win[j][1] - win[i][1]) / (dmi * 5280.0) * 100.0
        best = max(best, grade)
    return best


def count_pitches(win: list[tuple[float, float]], run_mi: float, pct: float) -> int:
    """Non-overlapping >= run_mi runs whose grade exceeds pct%."""
    if len(win) < 2:
        return 0
    pitches = 0
    i = 0
    n = len(win)
    while i < n - 1:
        j = i
        while j < n and win[j][0] - win[i][0] < run_mi:
            j += 1
        if j >= n:
            break
        dmi = win[j][0] - win[i][0]
        grade = abs(win[j][1] - win[i][1]) / (dmi * 5280.0) * 100.0 if dmi > 0 else 0.0
        if grade >= pct:
            pitches += 1
            i = j  # non-overlapping
        else:
            i += 1
    return pitches


def elev_at(profile: list[tuple[float, float]], mi: float) -> float:
    """Linearly-interpolated elevation at a mile along the (sorted) profile."""
    if mi <= profile[0][0]:
        return profile[0][1]
    if mi >= profile[-1][0]:
        return profile[-1][1]
    lo, hi = 0, len(profile) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if profile[mid][0] < mi:
            lo = mid
        else:
            hi = mid
    (m0, e0), (m1, e1) = profile[lo], profile[hi]
    if m1 == m0:
        return e0
    return e0 + (mi - m0) / (m1 - m0) * (e1 - e0)


def classify_point(profile: list[tuple[float, float]], center: float) -> str:
    """Terrain at one point: local steepness judged against nearby relief.

    Steepness is the steepest grade held over a mile anywhere within
    ``LOCAL_STEEP_MI`` of the point -- tight enough not to smear a lone pitch
    across the map, loose enough that a winding mountain climb (a switchback
    briefly levelling) still reads steep where a bare centred-mile net would
    wash it out. Relief is measured over the wider ``WINDOW_MI`` context.

    Mountain is genuinely steep grade, not one number: a mile held at
    ``MTN_SUSTAIN_SOLO``% (the East's escarpments), or a shade less with real
    window relief under it, or a big relief carrying repeated pitches. Hills is
    a gentler grade or moderate relief. Everything else is flat.
    """
    steep = max_sustained_grade(_window(profile, center - LOCAL_STEEP_MI, center + LOCAL_STEEP_MI), SUSTAIN_MI)
    win = _window(profile, center - WINDOW_MI, center + WINDOW_MI)
    return terrain_for(steep, window_relief_ft(win), count_pitches(win, PITCH_MI, PITCH_PCT))


def bin_profile(profile: list[tuple[float, float]], leg_miles: float, step: float = 0.25) -> list[tuple[float, str]]:
    """Classify the leg in fixed ``step``-mile bins; returns [(center_mi, kind)]."""
    if leg_miles <= 0 or len(profile) < 2:
        return []
    bins: list[tuple[float, str]] = []
    c = step / 2.0
    while c < leg_miles:
        bins.append((c, classify_point(profile, c)))
        c += step
    return bins


def dominant(kinds: list[str]) -> str:
    """The terrain covering the most bins, mountain winning a tie upward."""
    if not kinds:
        return "flat"
    counts = {k: kinds.count(k) for k in set(kinds)}
    return max(counts, key=lambda k: (counts[k], RANK[k]))


def leg_terrain_from_bins(bins: list[tuple[float, str]], leg_miles: float, step: float = 0.25) -> str:
    mtn_mi = sum(step for _, k in bins if k == "mountain")
    hill_mi = sum(step for _, k in bins if k == "hills")
    return leg_terrain(mtn_mi, hill_mi, leg_miles)


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def load_geometry() -> dict[str, dict[str, Any]]:
    geom: dict[str, dict[str, Any]] = {}
    for shard in sorted(GEOMETRY_DIR.glob("*.jsonl")):
        for i, line in enumerate(shard.read_text(encoding="utf-8").splitlines()):
            if i == 0 or not line.strip():
                continue
            rec = json.loads(line)
            geom[rec["leg"]] = rec
    return geom


def load_ramps() -> list[dict[str, Any]]:
    ramps: list[dict[str, Any]] = []
    for i, line in enumerate(RAMPS_PATH.read_text(encoding="utf-8").splitlines()):
        if i == 0 or not line.strip():
            continue
        ramps.append(json.loads(line))
    return ramps


def reclassify(
    data: dict[str, Any],
    geom: dict[str, dict[str, Any]],
    ramps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recompute segment and leg terrain in place. Returns a change report.

    Runaway ramps are authoritative ground truth: a highway=escape way is
    built only where a long steep descent runs a loaded truck out of brakes,
    so a segment carrying one is mountain regardless of what the smoothed
    profile shows (a short 6% pitch averages below the sustained bar). This
    is a uniform rule over the 96 harvested ramps, not a per-leg data edit,
    and no ramp sits in flat country (Texas has none).
    """
    cities = data["cities"]
    ramps_by_leg: dict[str, list[float]] = {}
    for r in ramps or []:
        ramps_by_leg.setdefault(r["leg"], []).append(float(r.get("at_mi", 0.0)))
    seg_changes: list[dict[str, Any]] = []
    leg_changes: list[dict[str, Any]] = []
    ramp_forced = 0
    missing_geo = 0

    for leg in data["legs"]:
        corridor = leg.get("corridor") or {}
        segs = corridor.get("grade_segments") or []
        if not segs:
            continue
        key = f"{leg['from']}:{leg['to']}"
        rec = geom.get(key)
        if rec is None:
            missing_geo += 1
            continue
        leg_miles = float(leg.get("miles") or rec.get("miles") or 0.0)
        profile = median_filter(decode_profile(rec["geom"], leg_miles), MEDIAN_MI)
        state = str(cities.get(leg["from"], {}).get("state", "??"))
        leg_ramps = ramps_by_leg.get(key, [])

        step = 0.25
        bins = bin_profile(profile, leg_miles, step)
        # A runaway ramp is ground truth: force its bin (and a short margin) to
        # mountain so both the segment it sits in and the leg fraction see it.
        if leg_ramps:
            bins = [
                (c, "mountain" if any(abs(c - at) <= 0.5 for at in leg_ramps) else k)
                for c, k in bins
            ]

        for seg in segs:
            span = [k for c, k in bins if seg["start_mi"] <= c <= seg["end_mi"]]
            new_kind = dominant(span) if span else classify_point(
                profile, (seg["start_mi"] + seg["end_mi"]) / 2.0
            )
            if new_kind != "mountain" and any(
                seg["start_mi"] <= at <= seg["end_mi"] for at in leg_ramps
            ):
                new_kind = "mountain"
                ramp_forced += 1
            old_kind = seg.get("terrain")
            if new_kind != old_kind:
                seg_changes.append(
                    {
                        "state": state,
                        "leg": key,
                        "start_mi": seg["start_mi"],
                        "end_mi": seg["end_mi"],
                        "old": old_kind,
                        "new": new_kind,
                        "avg_grade_pct": seg.get("avg_grade_pct"),
                    }
                )
                seg["terrain"] = new_kind

        # Segment labels above carry the honest local truth and may fall (that is
        # the Texas fix). The leg label is the human-facing summary and many are
        # hand-curated real geography (test_world pins two dozen). The brief's
        # rank-merge rule is never to silently downgrade a curated label, so the
        # leg label only ever firms UP: a flat leg that really crosses a pass
        # becomes mountain (the Grapevine), but a curated "hills" or "mountain"
        # leg is never quietly demoted off a stricter geometric read.
        derived_leg = leg_terrain_from_bins(bins, leg_miles, step)
        old_leg = leg.get("terrain")
        new_leg = derived_leg if RANK[derived_leg] > RANK.get(old_leg, 0) else old_leg
        if new_leg != old_leg:
            leg_changes.append(
                {
                    "state": state,
                    "leg": key,
                    "highway": leg.get("highway"),
                    "miles": leg_miles,
                    "old": old_leg,
                    "new": new_leg,
                }
            )
            leg["terrain"] = new_leg

    return {
        "segments": seg_changes,
        "legs": leg_changes,
        "missing_geometry": missing_geo,
        "ramp_forced_segments": ramp_forced,
    }


# --------------------------------------------------------------------------- #
# Reporting / acceptance
# --------------------------------------------------------------------------- #
def leg_terrain_map(data: dict[str, Any]) -> dict[str, str]:
    return {f"{lg['from']}:{lg['to']}": lg.get("terrain") for lg in data["legs"]}


def seg_terrains_by_leg(data: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for leg in data["legs"]:
        segs = (leg.get("corridor") or {}).get("grade_segments") or []
        out[f"{leg['from']}:{leg['to']}"] = [s["terrain"] for s in segs]
    return out


def print_report(report: dict[str, Any], state_filter: str | None) -> None:
    seg = report["segments"]
    legc = report["legs"]
    if state_filter:
        seg = [c for c in seg if c["state"] == state_filter]
        legc = [c for c in legc if c["state"] == state_filter]

    print("\n=== LEG-LEVEL terrain changes ===")
    from collections import Counter

    dirn = Counter((c["old"], c["new"]) for c in report["legs"])
    for (o, n), k in sorted(dirn.items(), key=lambda x: -x[1]):
        print(f"  {o:8s} -> {n:8s}  {k}")
    print(f"  total leg changes: {len(report['legs'])}")

    print("\n=== leg changes (detail) ===")
    for c in sorted(legc, key=lambda x: (x["state"], x["leg"])):
        print(f"  {c['state']:3s} {c['old']:8s} -> {c['new']:8s}  {c['leg']}  {c.get('highway')}  {c['miles']:.0f}mi")

    print("\n=== SEGMENT-LEVEL terrain changes (direction counts) ===")
    sdir = Counter((c["old"], c["new"]) for c in report["segments"])
    for (o, n), k in sorted(sdir.items(), key=lambda x: -x[1]):
        print(f"  {o:8s} -> {n:8s}  {k}")
    print(f"  total segment changes: {len(report['segments'])}")
    if report["missing_geometry"]:
        print(f"\n  WARNING: {report['missing_geometry']} legs had no geometry (unchanged)")


ACCEPTANCE_ZERO_MTN = [
    "palestine_tx_us:lufkin_tx_us",
    "lufkin_tx_us:tyler_tx_us",
    "palestine_tx_us:tyler_tx_us",
    "austin_tx_us:kerrville_tx_us",
    "san_antonio_tx_us:kerrville_tx_us",
    "tyler_tx_us:texarkana_ar_us",
]
ACCEPTANCE_KEEP_MTN = [
    "denver_co_us:silverthorne_co_us",   # I-70 Denver-Silverthorne
    "bakersfield_ca_us:los_angeles_ca_us",  # Grapevine (was flat)
    "yreka_ca_us:medford_or_us",         # Siskiyou
    "chattanooga_tn_us:nashville_tn_us",  # Monteagle (was flat)
]


def run_acceptance(data: dict[str, Any], ramps: list[dict[str, Any]]) -> bool:
    ok = True
    legmap = leg_terrain_map(data)
    segmap = seg_terrains_by_leg(data)

    print("\n=== ACCEPTANCE: Texas legs must have ZERO mountain segments ===")
    for key in ACCEPTANCE_ZERO_MTN:
        segs = segmap.get(key, [])
        n_mtn = segs.count("mountain")
        status = "PASS" if n_mtn == 0 else "FAIL"
        if n_mtn:
            ok = False
        print(f"  [{status}] {key:45s} mountain segs={n_mtn}  leg={legmap.get(key)}")

    print("\n=== ACCEPTANCE: famous grades must be mountain at both levels ===")
    for key in ACCEPTANCE_KEEP_MTN:
        segs = segmap.get(key, [])
        n_mtn = segs.count("mountain")
        leg_ok = legmap.get(key) == "mountain"
        seg_ok = n_mtn > 0
        status = "PASS" if (leg_ok and seg_ok) else "FAIL"
        if not (leg_ok and seg_ok):
            ok = False
        print(f"  [{status}] {key:45s} leg={legmap.get(key):8s} mountain segs={n_mtn}")

    print("\n=== ACCEPTANCE: every runaway ramp sits on a mountain segment/leg ===")
    off = []
    for r in ramps:
        key = r["leg"]  # already "from:to"
        at = r.get("at_mi", 0.0)
        leg = next((lg for lg in data["legs"] if f"{lg['from']}:{lg['to']}" == key), None)
        if leg is None:
            off.append((key, at, "no-leg"))
            continue
        segs = (leg.get("corridor") or {}).get("grade_segments") or []
        seg = next((s for s in segs if s["start_mi"] <= at <= s["end_mi"]), None)
        seg_kind = seg["terrain"] if seg else None
        if seg_kind != "mountain" and leg.get("terrain") != "mountain":
            off.append((key, at, f"seg={seg_kind} leg={leg.get('terrain')}"))
    if off:
        ok = False
        print(f"  FAIL: {len(off)} of {len(ramps)} ramps NOT on a mountain segment/leg:")
        for key, at, why in off[:20]:
            print(f"    {key} @ {at}mi  {why}")
    else:
        print(f"  PASS: all {len(ramps)} ramps on mountain segments/legs")

    print(f"\n=== ACCEPTANCE {'PASSED' if ok else 'FAILED'} ===")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="save changes via world_source (default: dry-run)")
    ap.add_argument("--state", help="restrict the printed report to one state code")
    ap.add_argument("--acceptance", action="store_true", help="run the acceptance harness")
    ap.add_argument("--json-out", type=Path, help="write the full change report as JSON here")
    args = ap.parse_args()

    data = load_world()
    geom = load_geometry()
    ramps = load_ramps()

    # Census BEFORE
    before_legs = {}
    from collections import Counter

    before_legs = Counter(lg.get("terrain") for lg in data["legs"])

    report = reclassify(data, geom, ramps)

    after_legs = Counter(lg.get("terrain") for lg in data["legs"])
    print("=== leg terrain census: before -> after ===")
    for kind in ("flat", "hills", "mountain"):
        print(f"  {kind:8s} {before_legs.get(kind, 0):5d} -> {after_legs.get(kind, 0):5d}")

    print_report(report, args.state)

    if args.acceptance:
        run_acceptance(data, ramps)

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote report -> {args.json_out}")

    if args.write:
        n = save_world(data)
        print(f"\n--write: saved {n} source shard(s). Now run:  uv run python tools/index_world.py")
    else:
        print("\n(dry-run; pass --write to save)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
