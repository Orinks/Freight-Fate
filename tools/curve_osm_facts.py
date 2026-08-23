"""What road does each baked curve actually sit on? Read from OSM, offline.

The dense sweep (``tools/bake_curve_geometry.py``) decides ``connector`` by
POSITION alone: a curve inside ``CONNECTOR_WINDOW_MI`` of either end of the
leg is a connector, everything else is mainline. That window cannot see an
interchange in the middle of a leg, and it cannot see the ten miles of city
street and ramp a route rides before it reaches the interstate it is named
for. So interchange vertices and city-departure kinks were baked as
interstate MAINLINE, and the pacenote layer has been calling them.

This module answers the question the sweep never asked -- what kind of way is
under this curve? -- by READING OSM's own functional classification of the
nearest way to the curve's apex, and it writes down everything it read:
the nearest way of any kind, the nearest ramp, the nearest non-ramp, and the
nearest way carrying the leg's own route shield, each with its distance.
``tools/bake_curve_connectors.py`` decides the flag from those readings.

Nothing recorded here is derived from the curve. There is no radius,
deflection, advisory or severity input at all, so no rule built on this file
can tell a sharp curve from a gentle one, and none of them can delete a
design exception: I-70 through Glenwood Canyon is ``highway=motorway`` and
reads exactly like I-70 across Kansas.

The one derived number is ``CORRIDOR_M``, the distance beyond which no way is
close enough to be the road under the curve. See its comment -- and note that
the archived polyline turns out to sit within 0.6 m of its OSM way 99 percent
of the time, so the corridor is a sanity bound, not a decision.

This is the expensive half and it is cached: one stream per state PBF from
the local Geofabrik cache (``~/.cache/freight-fate-osm/regions``), keeping
only the segments that land near a curve apex. ``tools/bake_curve_connectors.py``
reads the facts file it writes and does the classifying, so the rule can be
re-judged without re-reading 14 GB.

Curve apexes are recovered from the ARCHIVE, not from a fresh route fetch:
``world_data/us/geometry/<state>.jsonl`` decodes to the exact polyline the
gameplay rows were baked from, and re-running ``analyse_curvature`` on it
reproduces those rows one for one (the sweep's own round-trip acceptance
check, verified here for all 1,290 legs). So this runs offline, with no ORS
or Overpass server.

Usage
-----
    uv run --group tooling python tools/curve_osm_facts.py --all
    uv run --group tooling python tools/curve_osm_facts.py --state co
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parent))

import straw_curve_sample as scs  # noqa: E402  (decode + curve detection primitives)
from bake_curve_connectors import CORRIDOR_M, FACTS  # noqa: E402  (the decider's contract)
from bake_divided import (  # noqa: E402
    _CODE_TO_NAME,
    CACHE_DIR,
    load_geometry_by_code,
    state_slug,
)
from world_source import load_world  # noqa: E402

# The production bake widens the straw margin; the archive was written with it,
# so re-detection has to use the same value or the rows will not line up.
scs.CURVE_PAD_M = 150.0

ROOT = Path(__file__).resolve().parent.parent
CURVES = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "gameplay" / "curves.jsonl"

# Every way class a truck route can ride. Links are in here on purpose -- they
# are the whole point -- and so are the small classes, because a city-departure
# curve sits on a residential street and the honest answer is to say so.
ROAD_CLASSES = frozenset(
    {
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "unclassified",
        "residential",
        "motorway_link",
        "trunk_link",
        "primary_link",
        "secondary_link",
        "tertiary_link",
    }
)

CELL_DEG = 0.005  # ~550 m; segment bucket size for the nearest-way lookup

# How often the route itself is sampled for the per-leg coverage reading --
# "does this leg ride the road it is named for at all?". A curve-apex census
# cannot answer that: I-25 Fort Collins to Cheyenne is dead straight, so every
# curve it has sits in the city geometry at the ends, and judging the leg by
# its curves alone would read 0 percent and call a real interstate mislabeled.
COVERAGE_STEP_M = 1609.344  # one mile


def load_curve_rows() -> dict[str, list[dict]]:
    """Baked gameplay curve rows, grouped by leg, in shard order."""
    out: dict[str, list[dict]] = {}
    for line in CURVES.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith('{"meta"'):
            continue
        row = json.loads(line)
        out.setdefault(row["leg"], []).append(row)
    return out


def curve_apexes(world: dict, rows_by_leg: dict[str, list[dict]], wanted_states: set[str] | None):
    """Per-curve apex points, plus per-leg route samples for the coverage read.

    The apex vertex comes from re-detecting curves on the decoded archive.
    A leg whose re-detection does not reproduce its shipped row count is
    SKIPPED rather than guessed at -- the rows could not be matched to
    vertices, so this tool has nothing to say about them.
    """
    cities = world["cities"]
    geom_cache: dict[str, dict[str, list[list[float]]]] = {}
    targets: list[dict] = []
    samples: list[dict] = []
    skipped: list[str] = []
    for leg in sorted(world["legs"], key=lambda L: (L["from"], L["to"])):
        code = str(cities[leg["from"]]["state"]).lower()
        if wanted_states and code not in wanted_states:
            continue
        lid = f"{leg['from']}:{leg['to']}"
        rows = rows_by_leg.get(lid)
        if not rows:
            continue
        if code not in geom_cache:
            geom_cache[code] = load_geometry_by_code(code)
        coords = geom_cache[code].get(lid)
        if not coords or len(coords) < 3:
            skipped.append(lid)
            continue
        cum = scs._cumulative_m(coords)
        rebaked = scs.analyse_curvature(coords, cum)["curves"]
        if len(rebaked) != len(rows):
            skipped.append(lid)
            continue
        shield = scs._shield_numbers(leg.get("highway", ""))
        for detected, row in zip(rebaked, rows, strict=False):
            lon, lat = coords[detected["_apex"]]
            targets.append(
                {
                    "leg": lid,
                    "seq": row["seq"],
                    "highway": leg.get("highway", ""),
                    "shield": shield,
                    "lat": lat,
                    "lon": lon,
                }
            )
        last = -math.inf
        for i, (lon, lat) in enumerate(coords):
            if cum[i] - last < COVERAGE_STEP_M and i != len(coords) - 1:
                continue
            last = cum[i]
            samples.append({"leg": lid, "shield": shield, "lat": lat, "lon": lon})
    return targets, samples, skipped


def cells_of_interest(*point_sets: list[dict]) -> set[tuple[int, int]]:
    """Grid cells a point could match a way in (its own cell plus neighbours)."""
    want: set[tuple[int, int]] = set()
    for points in point_sets:
        for p in points:
            row = math.floor(p["lat"] / CELL_DEG)
            col = math.floor(p["lon"] / CELL_DEG)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    want.add((row + dr, col + dc))
    return want


def collect_segments(
    pbf_path: Path,
    want: set[tuple[int, int]],
    segs: dict[tuple[int, int], list],
    metas: list[tuple[str, str, str]],
    meta_ids: dict[tuple[str, str, str], int],
) -> int:
    """Stream one state PBF, bucketing road segments that land near a curve.

    Segments are stored flat as ``(alat, alon, blat, blon, meta_id)`` with the
    ``(class, ref, name)`` triple interned: a network-wide run buckets several
    million of them and the nested form costs gigabytes for no gain.
    """
    processor = (
        osmium.FileProcessor(
            str(pbf_path),
            entities=osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY,
        )
        .with_locations()
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    kept = 0
    for way in processor:
        if not hasattr(way, "nodes"):
            continue
        tags = {str(t.k): str(t.v) for t in way.tags}
        klass = tags.get("highway", "")
        if klass not in ROAD_CLASSES:
            continue
        pts = []
        for node in way.nodes:
            try:
                if node.location.valid():
                    pts.append((float(node.location.lat), float(node.location.lon)))
            except osmium.InvalidLocationError:
                continue
        if len(pts) < 2:
            continue
        meta = (klass, tags.get("ref", ""), tags.get("name", ""))
        meta_id = meta_ids.get(meta)
        if meta_id is None:
            meta_id = meta_ids[meta] = len(metas)
            metas.append(meta)
        for a, b in zip(pts, pts[1:], strict=False):
            r0, r1 = sorted((math.floor(a[0] / CELL_DEG), math.floor(b[0] / CELL_DEG)))
            c0, c1 = sorted((math.floor(a[1] / CELL_DEG), math.floor(b[1] / CELL_DEG)))
            if r1 - r0 > 8 or c1 - c0 > 8:
                continue  # a segment this long is a rural way's single hop; skip
            hit = False
            seg = (a[0], a[1], b[0], b[1], meta_id)
            for rr in range(r0, r1 + 1):
                for cc in range(c0, c1 + 1):
                    if (rr, cc) in want:
                        segs.setdefault((rr, cc), []).append(seg)
                        hit = True
            kept += hit
    return kept


def _nearest(
    lat: float, lon: float, segs: dict[tuple[int, int], list], metas: list, accept
) -> tuple[float, tuple | None]:
    """Distance (m) and tags of the nearest accepted way segment, or (inf, None)."""
    row = math.floor(lat / CELL_DEG)
    col = math.floor(lon / CELL_DEG)
    coslat = math.cos(math.radians(lat))
    best_d, best = math.inf, None
    ok: dict[int, bool] = {}
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            for alat, alon, blat, blon, meta_id in segs.get((row + dr, col + dc), ()):
                good = ok.get(meta_id)
                if good is None:
                    good = ok[meta_id] = accept(metas[meta_id])
                if not good:
                    continue
                d = scs._point_seg_dist_m(
                    lat, lon, {"lat": alat, "lon": alon}, {"lat": blat, "lon": blon}, coslat
                )
                if d < best_d:
                    best_d, best = d, metas[meta_id]
    return best_d, best


def _is_link(meta: tuple) -> bool:
    return meta[0].endswith("_link")


def facts_for(target: dict, segs: dict[tuple[int, int], list], metas: list) -> dict:
    """Everything OSM has to say about the road under one curve apex."""
    lat, lon, shield = target["lat"], target["lon"], target["shield"]
    d_any, m_any = _nearest(lat, lon, segs, metas, lambda m: True)
    d_link, m_link = _nearest(lat, lon, segs, metas, _is_link)
    d_main, m_main = _nearest(lat, lon, segs, metas, lambda m: not _is_link(m))
    d_shield, m_shield = _nearest(
        lat, lon, segs, metas, lambda m: not _is_link(m) and scs._ref_matches_shield(m[1], shield)
    )

    def pack(prefix: str, dist: float, meta: tuple | None) -> dict:
        if meta is None or not math.isfinite(dist):
            return {f"{prefix}_m": None}
        return {
            f"{prefix}_m": round(dist, 1),
            f"{prefix}_hw": meta[0],
            f"{prefix}_ref": meta[1],
            f"{prefix}_name": meta[2],
        }

    return {
        "leg": target["leg"],
        "seq": target["seq"],
        "highway": target["highway"],
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        **pack("near", d_any, m_any),
        **pack("link", d_link, m_link),
        **pack("main", d_main, m_main),
        **pack("shield", d_shield, m_shield),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="every leg in the network")
    group.add_argument("--state", help="comma-separated from-state codes, e.g. co,az")
    ap.add_argument("--out", help=f"facts file to write (default {FACTS})")
    args = ap.parse_args()

    out_path = Path(args.out) if args.out else FACTS
    wanted = None if args.all else {s.strip().lower() for s in args.state.split(",")}

    world = load_world()
    rows_by_leg = load_curve_rows()
    targets, samples, skipped = curve_apexes(world, rows_by_leg, wanted)
    print(
        f"{len(targets)} curve apexes | {len(samples)} route samples | "
        f"{len(skipped)} legs skipped (rows did not re-detect)"
    )
    if not targets:
        return 1

    want = cells_of_interest(targets, samples)
    print(f"{len(want)} grid cells of interest", flush=True)

    cities = world["cities"]
    codes: set[str] = set()
    legs_seen = {t["leg"] for t in targets}
    for leg in world["legs"]:
        if f"{leg['from']}:{leg['to']}" in legs_seen:
            codes.add(str(cities[leg["from"]]["state"]).lower())
            codes.add(str(cities[leg["to"]]["state"]).lower())

    segs: dict[tuple[int, int], list] = {}
    metas: list[tuple[str, str, str]] = []
    meta_ids: dict[tuple[str, str, str], int] = {}
    missing: list[str] = []
    for code in sorted(codes):
        pbf = CACHE_DIR / f"{state_slug(_CODE_TO_NAME.get(code, code))}-latest.osm.pbf"
        if not pbf.exists():
            missing.append(pbf.name)
            print(f"  PBF MISSING: {pbf.name}", flush=True)
            continue
        kept = collect_segments(pbf, want, segs, metas, meta_ids)
        print(f"  scanned {code}: {kept} segments near a curve", flush=True)

    # Per-leg coverage first: does the route ride the road the leg is named
    # for at all? A leg that never does is MISLABELED, not full of connectors,
    # and the classifier must not read its off-shield curves as ramps.
    on_shield: dict[str, int] = {}
    on_motorway: dict[str, int] = {}
    total: dict[str, int] = {}
    # Which road each leg ACTUALLY rides, mile by mile. A leg whose label does
    # not appear here is mislabeled, and this says what it should have said.
    ridden: dict[str, dict[str, int]] = {}
    ridden_class: dict[str, dict[str, int]] = {}
    for n, sample in enumerate(samples, 1):
        lid = sample["leg"]
        total[lid] = total.get(lid, 0) + 1
        dist, meta = _nearest(sample["lat"], sample["lon"], segs, metas, lambda m: not _is_link(m))
        if dist <= CORRIDOR_M and meta is not None:
            if meta[0] == "motorway":
                on_motorway[lid] = on_motorway.get(lid, 0) + 1
            if scs._ref_matches_shield(meta[1], sample["shield"]):
                on_shield[lid] = on_shield.get(lid, 0) + 1
            # A concurrency ("I 70;US 6") credits every shield it carries --
            # the truck really is on both roads for that mile.
            for ref in str(meta[1]).split(";"):
                ref = ref.strip()
                if ref:
                    tally = ridden.setdefault(lid, {})
                    tally[ref] = tally.get(ref, 0) + 1
            # And the CLASS of road, mile by mile. This is what lets a bend be
            # judged against the road its leg is actually made of rather than
            # against the road its label claims -- a leg labelled I-65 whose
            # route rides US-231 end to end is made of trunk, and a trunk bend
            # on it is mainline, not a ramp.
            klasses = ridden_class.setdefault(lid, {})
            klasses[meta[0]] = klasses.get(meta[0], 0) + 1
        if n % 20000 == 0:
            print(f"  coverage {n}/{len(samples)}", flush=True)

    lines = [
        json.dumps(
            {
                "leg": lid,
                "coverage_samples": total[lid],
                "coverage_on_shield": on_shield.get(lid, 0),
                "coverage_on_motorway": on_motorway.get(lid, 0),
                "ridden_refs": dict(sorted(ridden.get(lid, {}).items(), key=lambda kv: -kv[1])[:8]),
                "ridden_classes": dict(
                    sorted(ridden_class.get(lid, {}).items(), key=lambda kv: -kv[1])
                ),
            },
            sort_keys=True,
        )
        for lid in sorted(total)
    ]
    for n, target in enumerate(targets, 1):
        lines.append(json.dumps(facts_for(target, segs, metas), sort_keys=True))
        if n % 5000 == 0:
            print(f"  read {n}/{len(targets)}", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} facts -> {out_path}")
    if missing:
        print(f"INCOMPLETE: {len(missing)} state extracts absent -- {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
