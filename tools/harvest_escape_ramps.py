"""Harvest runaway-truck (``highway=escape``) ramps from local Geofabrik PBFs.

The self-hosted Overpass extract is filtered to mainline travel-ways and carries
no ``highway=escape`` ways, so the curve-geometry sweep's ramp table
(``tools/bake_curve_geometry.py``) has no source. The per-state Geofabrik
extracts already on disk (downloaded by ``tools/fetch_state_extracts.py`` for
Job 1) DO carry them -- so this reads them straight off the PBFs, fully offline,
no re-import and no public Overpass.

Escape ramps are rare (a few hundred nationwide), so the output cache is tiny.
Each ramp is stored as its geometry centroid plus name/ref, keyed nowhere -- the
bake matches ramps to legs by proximity to each leg's route line.

    uv run --group tooling python tools/harvest_escape_ramps.py            # all states
    uv run --group tooling python tools/harvest_escape_ramps.py colorado   # one state

Writes ``src/freight_fate/data/escape_ramps.json`` (a build-time cache, not a
runtime file): a sorted, deterministic list of ramps with a source note.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import osmium

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
OUT = ROOT / "src" / "freight_fate" / "data" / "escape_ramps.json"
SOURCE = (
    "OpenStreetMap highway=escape ways, read from local Geofabrik state extracts; "
    "development-time. (c) OpenStreetMap contributors, ODbL."
)


def harvest_pbf(pbf: Path) -> list[dict]:
    """Every ``highway=escape`` way in one state extract, as centroid + tags."""
    ramps: list[dict] = []
    # NODE must be read for the location cache that populates way geometry; the
    # KeyFilter still keeps only highway-tagged objects, so nodes stream cheaply.
    entities = osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY
    processor = (
        osmium.FileProcessor(str(pbf), entities=entities)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    for way in processor:
        if not hasattr(way, "nodes") or way.tags.get("highway") != "escape":
            continue
        lats, lons = [], []
        for node in way.nodes:
            try:
                if node.location.valid():
                    lats.append(float(node.location.lat))
                    lons.append(float(node.location.lon))
            except osmium.InvalidLocationError:
                continue
        if not lats:
            continue
        name = str(way.tags.get("name", "") or "").strip()
        ref = str(way.tags.get("ref", "") or "").strip()
        ramps.append(
            {
                "lat": round(sum(lats) / len(lats), 6),
                "lon": round(sum(lons) / len(lons), 6),
                "name": name,
                "ref": ref,
                "source": SOURCE,
            }
        )
    return ramps


def main() -> int:
    if len(sys.argv) > 1:
        pbfs = [CACHE_DIR / f"{s}-latest.osm.pbf" for s in sys.argv[1:]]
    else:
        pbfs = sorted(CACHE_DIR.glob("*-latest.osm.pbf"))
    missing = [p for p in pbfs if not p.exists()]
    if missing:
        print("missing PBFs: " + ", ".join(p.name for p in missing), file=sys.stderr)
        return 1

    all_ramps: list[dict] = []
    for pbf in pbfs:
        found = harvest_pbf(pbf)
        all_ramps.extend(found)
        print(f"  {pbf.stem.replace('-latest.osm', ''):18s} {len(found):4d} escape ramps", flush=True)

    # dedupe on rounded centroid (state extracts overlap at borders) + sort for
    # a deterministic, diffable cache.
    seen: dict[tuple, dict] = {}
    for r in all_ramps:
        seen[(r["lat"], r["lon"])] = r
    ramps = sorted(seen.values(), key=lambda r: (r["lat"], r["lon"]))
    OUT.write_text(json.dumps({"ramps": ramps}, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"\n{len(ramps)} unique escape ramps -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
