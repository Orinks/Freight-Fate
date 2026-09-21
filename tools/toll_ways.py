"""Every tolled road a truck could be routed onto, read from a local extract.

``toll_scan.py`` asks an Overpass one 3 km bubble at a time. That was written
for a self-hosted server; against the public one it is roughly 13,000 queries
for the network, which is most of a day and at the mercy of a service that
answers "too busy" when it feels like it.

The tolled set is SMALL and national -- turnpikes, bridges, tunnels -- so one
pass over the Geofabrik extract collects all of it, and every leg is then
matched offline against the same evidence. Deterministic, repeatable, and it
cannot silently report "no toll here" because a server was busy.

Two passes, no location index, the pattern the interchange reader already
uses: pass one keeps the ways whose tags matter and remembers their node ids,
pass two resolves just those nodes.

    uv run --group tooling python tools/toll_ways.py --pbf ~/osm/us-latest.osm.pbf
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import overpass_corridor as oc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".route-cache" / "toll-ways.json"

# What a loaded semi would actually be routed onto. A tolled residential
# street is not a leg's toll.
TRUCK_CLASSES = (
    "motorway",
    "trunk",
    "primary",
    "motorway_link",
    "trunk_link",
)
# Tags worth carrying: what it is, what it is called, and whether it tolls.
KEPT = ("highway", "toll", "name", "ref", "operator", "toll:hgv", "network")


def tolled_way_tags(pbf_path: Path) -> dict[int, dict[str, str]]:
    """``way id -> tags`` for every tolled road a truck could be routed onto.

    The tag filter runs in osmium's C++ side, so only the handful of objects
    carrying a ``toll`` key ever reach Python. Filtering here instead cut a
    two-hour crawl to minutes -- the naive version paid Python call overhead
    for all two hundred million ways to keep about two thousand.
    """
    try:
        import osmium
    except ImportError as exc:  # pragma: no cover - tooling group
        raise SystemExit(
            "Reading --pbf requires the tooling dependency group: "
            "uv sync --group dev --group tooling"
        ) from exc

    classes = frozenset(TRUCK_CLASSES)
    out: dict[int, dict[str, str]] = {}
    print(f"    reading {pbf_path} for tolled truck roads", flush=True)
    processor = osmium.FileProcessor(
        str(pbf_path), entities=osmium.osm.osm_entity_bits.WAY
    ).with_filter(osmium.filter.KeyFilter("toll"))
    seen = 0
    started = time.monotonic()
    for obj in processor:
        seen += 1
        tags = {str(k): str(v) for k, v in obj.tags}
        if tags.get("highway") not in classes:
            continue
        out[int(obj.id)] = {k: v for k, v in tags.items() if k in KEPT}
    print(
        f"    {seen:,} ways carry a toll tag; {len(out):,} of them are truck roads "
        f"({time.monotonic() - started:.0f}s)",
        flush=True,
    )
    return out


def geometry_for(way_ids: list[int]) -> dict[int, list[tuple[float, float]]]:
    """Shapes for specific way ids, from Overpass, a few hundred at a time.

    Resolving these out of the extract would mean a second pass over every
    node in the country to place a couple of thousand ways. Asking for them
    by id is a handful of queries instead, and an id query is small enough
    that the service answers it.
    """
    out: dict[int, list[tuple[float, float]]] = {}
    for start in range(0, len(way_ids), 200):
        batch = way_ids[start : start + 200]
        payload = oc.post(
            "[out:json][timeout:180];way(id:" + ",".join(str(i) for i in batch) + ");out geom;"
        )
        for element in payload.get("elements", ()):
            geometry = [
                (float(p["lat"]), float(p["lon"])) for p in element.get("geometry") or []
            ]
            if len(geometry) >= 2:
                out[int(element["id"])] = geometry
        print(f"    geometry for {len(out):,}/{len(way_ids):,} ways", flush=True)
    return out


def tolls(tags: dict[str, str]) -> bool:
    """Does this way charge a truck?

     is a reading too -- somebody stated the road is free -- and it
    is kept in the collection so a later question can tell "known free" from
    "nobody said". It just does not need a shape: nothing is ever priced from
    it. Skipping those took the geometry fetch from 77,000 ways to a few
    thousand.
    """
    return tags.get("toll") == "yes" or tags.get("toll:hgv") == "yes"


def collect(pbf_path: Path) -> list[dict[str, Any]]:
    tags_by_id = tolled_way_tags(pbf_path)
    charging = sorted(i for i, t in tags_by_id.items() if tolls(t))
    print(f"    {len(charging):,} of them actually charge; fetching those shapes", flush=True)
    shapes = geometry_for(charging)
    return [
        {"id": way_id, "tags": tags, "geometry": shapes[way_id]}
        for way_id, tags in sorted(tags_by_id.items())
        if way_id in shapes
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pbf", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    if not args.pbf.exists():
        raise SystemExit(f"no such extract: {args.pbf}")
    ways = collect(args.pbf)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ways), encoding="utf-8")
    tolled = sum(1 for w in ways if w["tags"].get("toll") == "yes")
    print(f"\n{len(ways):,} ways carry a toll tag; {tolled:,} of them toll=yes")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
