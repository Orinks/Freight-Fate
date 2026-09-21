"""Do the unnamed local roads have a name OSM is holding somewhere else?

1,195 of the 12,820 turn-level segments a player drives say "unnamed public
road", and that line is spoken at every turn onto one. The question is whether
those roads are genuinely nameless or whether the name is present under a tag
nobody read.

The candidate is TIGER. Most US residential streets in OSM were imported from
the Census Bureau's TIGER/Line files, which carry the name split into parts --
``tiger:name_base`` ("Elm") and ``tiger:name_type`` ("St") -- and the import
did not always fold them into ``name``. Valhalla cannot help here at all: it
compiles the PBF into a fixed schema and those tags are not in it, so a road
nameless to the router may still be named in the source it was built from.

This counts, over drivable ways with no ``name``:

  * how many carry a usable TIGER name
  * what the alternatives look like (``alt_name``, ``old_name``, ``ref``)
  * how many are service ways, where namelessness is honest -- a parking
    aisle or a delivery drive has no name to find

    uv run python tools/tiger_name_probe.py --pbf ~/.cache/freight-fate-osm/us-latest.osm.pbf
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# The classes a local approach can put a truck on. Motorways and their ramps
# are excluded: those are named by shield elsewhere and never reach this text.
LOCAL_CLASSES = {
    "residential",
    "unclassified",
    "service",
    "tertiary",
    "secondary",
    "primary",
    "living_street",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pbf", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0, help="stop after this many ways")
    args = ap.parse_args()

    try:
        import osmium
    except ImportError:
        print("pyosmium is not installed: uv add --group tooling osmium")
        return 1

    counts: Counter[str] = Counter()
    samples: list[tuple[str, str]] = []

    # Filter on the C++ side, as tools/toll_ways.py does -- the same scan in
    # Python took roughly an hour and this takes minutes.
    processor = osmium.FileProcessor(str(args.pbf), osmium.osm.WAY).with_filter(
        osmium.filter.KeyFilter("highway")
    )
    for n, way in enumerate(processor):
        if args.limit and n >= args.limit:
            break
        tags = way.tags
        cls = tags.get("highway", "")
        if cls not in LOCAL_CLASSES:
            continue
        counts["drivable local ways"] += 1
        if tags.get("name"):
            counts["already named"] += 1
            continue
        counts["NO name"] += 1
        counts[f"  unnamed and highway={cls}"] += 1

        base = tags.get("tiger:name_base")
        if base:
            counts["  ...but has tiger:name_base"] += 1
            if cls != "service":
                counts["  ...and is not a service way (RECOVERABLE)"] += 1
                if len(samples) < 12:
                    kind = tags.get("tiger:name_type") or ""
                    samples.append((cls, f"{base} {kind}".strip()))
        elif tags.get("alt_name") or tags.get("old_name"):
            counts["  ...has alt_name or old_name"] += 1
        elif tags.get("ref"):
            counts["  ...has a ref only"] += 1
        else:
            counts["  ...genuinely nameless"] += 1

    width = max(len(k) for k in counts) if counts else 10
    for key, value in counts.most_common():
        print(f"{key:<{width}}  {value:>9,}")

    if samples:
        print("\nnames TIGER is holding that nothing reads:")
        for cls, name in samples:
            print(f"  highway={cls:<13} {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
