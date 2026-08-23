"""What road does each baked curve sit on? Ask a map matcher.

This replaces ``tools/curve_osm_facts.py``, which answered the same question
by streaming 14 GB of Geofabrik extracts and taking the nearest way segment to
each curve's apex. Nearest-distance is the wrong tool: at an interchange the
ramp and the mainline it leaves are metres apart, and a point has no way to
know which one the truck is on.

Map matching does know, because it snaps the WHOLE polyline at once and the
answer has to be a connected path. Valhalla's ``trace_attributes`` returns,
per matched edge, the road class, whether the edge is a ramp or turn channel,
its names and refs, and its speed limit -- so the readings the connector bake
needs come from one call to a purpose-built matcher.

Two fields carry the verdict, and they are separate on purpose where OSM
conflates them into ``highway=*_link``:

  ``edge.use``         ``ramp`` or ``turn_channel`` -- interchange geometry,
                       whatever class of road it carries. A ramp off a trunk
                       is still a ramp.
  ``edge.road_class``  ``motorway``, ``trunk``, ``primary`` ... the through
                       road's own importance, which is what the connector
                       rule compares a bend against.

Coverage is all or nothing per leg: a leg whose polyline leaves the built
tileset comes back partly unmatched, and an unmatched apex is recorded as
having NO reading rather than guessed at. Build tiles covering the whole
network before trusting a run.

Running the matcher
-------------------
The tileset is built by the ``valhalla-scripted`` image. Three things bite on
Windows and are worth writing down:

  * ``tile_urls`` must be passed even when empty -- the entrypoint runs under
    ``set -u`` and dies on the unbound variable.
  * Git Bash mangles the volume path. Use ``MSYS_NO_PATHCONV=1`` and a
    ``C:/...`` path, or the PBF is silently not mounted and the build reports
    "No local PBF files".
  * Do NOT disable ``build_admins``. The ``enhance`` stage uses the admin
    database and segfaults without it.

    MSYS_NO_PATHCONV=1 docker run -d --name valhalla -p 8002:8002 \\
      -v "C:/Users/joshu/.cache/valhalla/us:/custom_files" \\
      -e tile_urls= -e serve_tiles=True \\
      ghcr.io/valhalla/valhalla-scripted:latest

Usage
-----
    uv run python tools/curve_valhalla_facts.py --all
    uv run python tools/curve_valhalla_facts.py --state co --out facts.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import straw_curve_sample as scs  # noqa: E402
from bake_curve_connectors import FACTS  # noqa: E402
from bake_divided import load_geometry_by_code  # noqa: E402
from world_source import load_world  # noqa: E402

# The production bake widens the straw margin; the archive was written with
# it, so re-detection has to use the same value or the rows will not line up.
scs.CURVE_PAD_M = 150.0

ROOT = Path(__file__).resolve().parent.parent
CURVES = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "gameplay" / "curves.jsonl"

VALHALLA_URL = "http://localhost:8002/trace_attributes"
COSTING = "truck"  # the vehicle actually being routed, so its restrictions apply

# What ``edge.use`` calls interchange geometry.
RAMP_USES = frozenset({"ramp", "turn_channel"})

# Valhalla caps a single trace; long legs are matched in overlapping chunks so
# the matcher still sees context either side of every cut.
MAX_SHAPE_POINTS = 1000
CHUNK_OVERLAP = 20

# One mile between the route samples that say what a leg is MADE of.
COVERAGE_STEP_M = 1609.344


def load_curve_rows() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for line in CURVES.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith('{"meta"'):
            continue
        row = json.loads(line)
        out.setdefault(row["leg"], []).append(row)
    return out


def _post(body: dict) -> dict | None:
    request = urllib.request.Request(
        VALHALLA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def match_leg(coords: list[list[float]]) -> dict[int, dict]:
    """``vertex index -> matched edge`` for one leg's polyline.

    Chunked with overlap so a cut never robs the matcher of the context it
    needs to resolve which way a point belongs to. A vertex the matcher could
    not place is simply absent, and the caller records that as no reading.
    """
    out: dict[int, dict] = {}
    start = 0
    while start < len(coords):
        stop = min(len(coords), start + MAX_SHAPE_POINTS)
        chunk = coords[start:stop]
        if len(chunk) < 2:
            break
        result = _post(
            {
                "shape": [{"lat": lat, "lon": lon} for lon, lat in chunk],
                "costing": COSTING,
                "shape_match": "map_snap",
                "filters": {
                    "attributes": [
                        "edge.road_class",
                        "edge.use",
                        "edge.names",
                        "edge.speed_limit",
                        "edge.way_id",
                        "matched.point_index",
                        "matched.edge_index",
                        "matched.type",
                    ],
                    "action": "include",
                },
            }
        )
        if result:
            edges = result.get("edges") or []
            for offset, point in enumerate(result.get("matched_points") or []):
                index = point.get("edge_index")
                if index is None or index >= len(edges):
                    continue
                if str(point.get("type")) == "unmatched":
                    continue
                out[start + offset] = edges[index]
        if stop >= len(coords):
            break
        start = stop - CHUNK_OVERLAP
    return out


def facts_for(leg_id: str, seq: int, edge: dict | None) -> dict:
    """One curve's reading, in the shape ``bake_curve_connectors`` expects."""
    if edge is None:
        return {"leg": leg_id, "seq": seq, "near_m": None}
    use = str(edge.get("use") or "")
    road_class = str(edge.get("road_class") or "")
    names = edge.get("names") or []
    # The connector rule reads ``near_hw`` as an OSM highway value, so a ramp
    # is reported the way OSM would tag it. The matcher's own words are kept
    # alongside, because they are the evidence.
    near_hw = f"{road_class}_link" if use in RAMP_USES else road_class
    return {
        "leg": leg_id,
        "seq": seq,
        "near_m": 0.0,  # a matched edge IS the road; there is no offset to report
        "near_hw": near_hw,
        "near_ref": ";".join(str(n) for n in names),
        "near_name": names[0] if names else "",
        "valhalla_use": use,
        "valhalla_road_class": road_class,
        "valhalla_way_id": edge.get("way_id"),
        "valhalla_speed_limit": edge.get("speed_limit"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--state", help="comma-separated from-state codes")
    ap.add_argument("--out", help=f"facts file to write (default {FACTS})")
    args = ap.parse_args()

    if _post({"shape": [], "costing": COSTING}) is None:
        probe = urllib.request.Request("http://localhost:8002/status")
        try:
            urllib.request.urlopen(probe, timeout=10)
        except Exception:
            print("Valhalla is not answering on localhost:8002 -- see this module's docstring.")
            return 1

    out_path = Path(args.out) if args.out else FACTS
    wanted = None if args.all else {s.strip().lower() for s in args.state.split(",")}
    world = load_world()
    cities = world["cities"]
    rows_by_leg = load_curve_rows()

    geom_cache: dict[str, dict[str, list]] = {}
    lines: list[str] = []
    coverage: list[str] = []
    done = skipped = unread = 0
    legs = sorted(world["legs"], key=lambda L: (L["from"], L["to"]))
    for n, leg in enumerate(legs, 1):
        code = str(cities[leg["from"]]["state"]).lower()
        if wanted and code not in wanted:
            continue
        leg_id = f"{leg['from']}:{leg['to']}"
        rows = rows_by_leg.get(leg_id)
        if not rows:
            continue
        if code not in geom_cache:
            geom_cache[code] = load_geometry_by_code(code)
        coords = geom_cache[code].get(leg_id)
        if not coords or len(coords) < 3:
            skipped += 1
            continue
        cum = scs._cumulative_m(coords)
        detected = scs.analyse_curvature(coords, cum)["curves"]
        if len(detected) != len(rows):
            skipped += 1
            continue
        matched = match_leg(coords)
        for curve, row in zip(detected, rows, strict=False):
            fact = facts_for(leg_id, row["seq"], matched.get(curve["_apex"]))
            unread += fact.get("near_m") is None
            lines.append(json.dumps(fact, sort_keys=True))
        # What the leg is MADE of, from the same matching: one sample a mile.
        classes: dict[str, int] = {}
        refs: dict[str, int] = {}
        samples = 0
        last = -math.inf
        for i in range(len(coords)):
            if cum[i] - last < COVERAGE_STEP_M and i != len(coords) - 1:
                continue
            last = cum[i]
            samples += 1
            edge = matched.get(i)
            if edge is None or str(edge.get("use")) in RAMP_USES:
                continue
            road_class = str(edge.get("road_class") or "")
            if road_class:
                classes[road_class] = classes.get(road_class, 0) + 1
            for name in edge.get("names") or []:
                refs[str(name)] = refs.get(str(name), 0) + 1
        coverage.append(
            json.dumps(
                {
                    "leg": leg_id,
                    "coverage_samples": samples,
                    "coverage_on_motorway": classes.get("motorway", 0),
                    "coverage_on_shield": sum(
                        count
                        for ref, count in refs.items()
                        if scs._ref_matches_shield(ref, scs._shield_numbers(leg.get("highway", "")))
                    ),
                    "ridden_refs": dict(sorted(refs.items(), key=lambda kv: -kv[1])[:8]),
                    "ridden_classes": dict(sorted(classes.items(), key=lambda kv: -kv[1])),
                },
                sort_keys=True,
            )
        )
        done += 1
        if done % 25 == 0:
            print(f"  matched {done} legs ({n}/{len(legs)} scanned)", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(coverage + lines) + "\n", encoding="utf-8")
    total = len(lines)
    print(f"\n{done} legs matched, {skipped} skipped (rows did not re-detect or no geometry)")
    print(
        f"{total} curve readings, {unread} with no matched edge ({100 * unread / max(1, total):.1f}%)"
    )
    print(f"wrote {out_path}")
    if unread > total * 0.02:
        print("\nWARNING: more than 2 percent unmatched. The tileset probably does not")
        print("cover the whole network -- check the build before trusting this.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
