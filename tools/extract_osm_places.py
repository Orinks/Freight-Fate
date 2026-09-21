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
    ap.add_argument("--pbf", type=Path, default=DEFAULT_PBF)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    if not args.pbf.exists():
        print(f"extract not found: {args.pbf}", file=sys.stderr)
        return 2
    places = extract_places(args.pbf)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(places), encoding="utf-8")
    towns = sum(1 for p in places if p["place"] == "town")
    print(f"places: {len(places)} ({towns} town, {len(places) - towns} village) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
