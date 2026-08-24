"""Extract real OSM ``place=village|town`` points from a local US extract.

The village-callout bake needs the OSM place hierarchy, and the self-hosted
Overpass DB cannot supply it: its extract was tag-filtered to roads, landmark
polygons, and truck POIs, so ``node["place"]`` returns zero rows nationwide (a
missing tag in the import filter is not a fact about the world -- the same trap
``enrich_routes_landmarks`` documents). The full Geofabrik US extract on disk
does carry them, so this tool scans it once and caches the result as compact
JSON for ``tools/bake_villages.py``.

Villages and towns only. A ``place=hamlet`` is a handful of houses; naming one
as though the driver arrived somewhere is a false promise, so hamlets are never
collected (map owner, 2026-07-20).

    uv run --group tooling python tools/extract_osm_places.py \
        --pbf D:/ors/files/us-latest.osm.pbf

Build-time only, offline, and idempotent: the cache is rewritten from the same
extract with the same result. Runtime never reads it -- the baked world does.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import osmium

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PBF = Path("D:/ors/files/us-latest.osm.pbf")
DEFAULT_OUT = ROOT / ".route-cache" / "osm_places_village_town.json"
PLACE_RANKS = ("town", "village")


def extract_places(pbf_path: Path) -> list[dict]:
    """Every named ``place=town|village`` node in the extract, sorted by id."""
    processor = osmium.FileProcessor(
        str(pbf_path), entities=osmium.osm.osm_entity_bits.NODE
    ).with_filter(osmium.filter.KeyFilter("place"))
    places: list[dict] = []
    for obj in processor:
        tags = {tag.k: tag.v for tag in obj.tags}
        rank = tags.get("place", "")
        if rank not in PLACE_RANKS:
            continue
        name = (tags.get("name") or "").strip()
        if not name:
            continue  # you cannot announce a nameless place
        if not obj.location.valid():
            continue
        places.append(
            {
                "id": int(obj.id),
                "name": name,
                "place": rank,
                "lat": round(float(obj.location.lat), 6),
                "lon": round(float(obj.location.lon), 6),
                "state": (tags.get("is_in:state") or tags.get("addr:state") or "").strip(),
            }
        )
    places.sort(key=lambda p: p["id"])
    return places


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--pbf",
        type=Path,
        action="append",
        default=[],
        help="repeatable: one extract to scan (defaults to the full US extract)",
    )
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--merge",
        action="store_true",
        help="add to the existing cache instead of replacing it, so the "
        "per-state Geofabrik extracts can be scanned a few at a time",
    )
    args = ap.parse_args()
    sources = args.pbf or [DEFAULT_PBF]
    missing = [path for path in sources if not path.exists()]
    if missing:
        for path in missing:
            print(f"extract not found: {path}", file=sys.stderr)
        return 2

    # Keyed by OSM id: the state extracts overlap at their borders, and one
    # node scanned twice is still one place.
    by_id: dict[int, dict] = {}
    if args.merge and args.out.exists():
        for place in json.loads(args.out.read_text(encoding="utf-8")):
            by_id[int(place["id"])] = place
        print(f"merging into {len(by_id)} cached places")
    for path in sources:
        found = extract_places(path)
        fresh = sum(1 for place in found if int(place["id"]) not in by_id)
        for place in found:
            by_id[int(place["id"])] = place
        print(f"  {path.name}: {len(found)} places ({fresh} new)")

    places = sorted(by_id.values(), key=lambda p: p["id"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(places), encoding="utf-8")
    towns = sum(1 for p in places if p["place"] == "town")
    print(f"places: {len(places)} ({towns} town, {len(places) - towns} village) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
