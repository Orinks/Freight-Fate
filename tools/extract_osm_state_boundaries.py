"""Extract U.S. state boundary relations and ways from a local OSM PBF.

The state-context bake uses this cache instead of simplified state polygons:

    uv run --group tooling python tools/extract_osm_state_boundaries.py \
        --pbf ~/osm/us-latest.osm.pbf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import osmium

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PBF = Path("D:/ors/files/us-latest.osm.pbf")
DEFAULT_OUT = ROOT / ".route-cache" / "osm_state_boundaries.json"
STATE_ISO_RE = re.compile(r"^US-[A-Z]{2}$")
STATE_ISOS = {
    "US-AL",
    "US-AK",
    "US-AZ",
    "US-AR",
    "US-CA",
    "US-CO",
    "US-CT",
    "US-DE",
    "US-DC",
    "US-FL",
    "US-GA",
    "US-HI",
    "US-ID",
    "US-IL",
    "US-IN",
    "US-IA",
    "US-KS",
    "US-KY",
    "US-LA",
    "US-ME",
    "US-MD",
    "US-MA",
    "US-MI",
    "US-MN",
    "US-MS",
    "US-MO",
    "US-MT",
    "US-NE",
    "US-NV",
    "US-NH",
    "US-NJ",
    "US-NM",
    "US-NY",
    "US-NC",
    "US-ND",
    "US-OH",
    "US-OK",
    "US-OR",
    "US-PA",
    "US-RI",
    "US-SC",
    "US-SD",
    "US-TN",
    "US-TX",
    "US-UT",
    "US-VT",
    "US-VA",
    "US-WA",
    "US-WV",
    "US-WI",
    "US-WY",
}
ALLOWED_ROLES = {"", "outer", "inner"}


def _source_timestamp(pbf_path: Path) -> str:
    reader = osmium.io.Reader(str(pbf_path))
    try:
        timestamp = reader.header().get("osmosis_replication_timestamp")
    finally:
        reader.close()
    if timestamp:
        return str(timestamp)
    return datetime.fromtimestamp(pbf_path.stat().st_mtime, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _tag_map(obj: Any) -> dict[str, str]:
    return {tag.k: tag.v for tag in obj.tags}


def extract_boundaries(pbf_path: Path) -> tuple[dict[str, Any], list[str]]:
    """Return boundary cache payload and structural validation errors."""
    relations: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    processor = osmium.FileProcessor(
        str(pbf_path), entities=osmium.osm.osm_entity_bits.RELATION
    ).with_filter(osmium.filter.KeyFilter("type"))
    for relation in processor:
        tags = _tag_map(relation)
        iso = tags.get("ISO3166-2", "")
        if (
            tags.get("type") != "boundary"
            or tags.get("boundary") != "administrative"
            or tags.get("admin_level") != "4"
            or not STATE_ISO_RE.fullmatch(iso)
        ):
            continue
        if iso in relations:
            errors.append(
                f"{iso}: multiple matching relations "
                f"{relations[iso]['relation_id']} and {int(relation.id)}"
            )
            continue
        way_ids = sorted(
            {
                int(member.ref)
                for member in relation.members
                if member.type == "w" and member.role in ALLOWED_ROLES
            }
        )
        if not way_ids:
            errors.append(f"{iso}: relation {int(relation.id)} has no boundary member ways")
        name = tags.get("name", "").strip()
        if iso == "US-DC":
            name = "District of Columbia"
        if not name:
            errors.append(f"{iso}: relation {int(relation.id)} has no name")
            continue
        relations[iso] = {
            "name": name,
            "iso": iso,
            "relation_id": int(relation.id),
            "way_ids": way_ids,
        }

    found = set(relations)
    for iso in sorted(STATE_ISOS - found):
        errors.append(f"{iso}: no matching boundary relation found")

    all_way_ids = sorted({way_id for state in relations.values() for way_id in state["way_ids"]})
    way_nodes: dict[int, list[int]] = {}
    processor = osmium.FileProcessor(
        str(pbf_path), entities=osmium.osm.osm_entity_bits.WAY
    ).with_filter(osmium.filter.IdFilter(all_way_ids))
    for way in processor:
        way_nodes[int(way.id)] = [int(node.ref) for node in way.nodes]

    needed_nodes: set[int] = set()
    for state in relations.values():
        missing_ways = sorted(set(state["way_ids"]) - set(way_nodes))
        if missing_ways:
            errors.append(f"{state['iso']}: missing member ways {missing_ways[:8]}")
        for way_id in state["way_ids"]:
            needed_nodes.update(way_nodes.get(way_id, ()))

    node_locations: dict[int, tuple[float, float]] = {}
    processor = osmium.FileProcessor(
        str(pbf_path), entities=osmium.osm.osm_entity_bits.NODE
    ).with_filter(osmium.filter.IdFilter(sorted(needed_nodes)))
    for node in processor:
        if node.location.valid():
            node_locations[int(node.id)] = (float(node.location.lon), float(node.location.lat))

    states = []
    for iso, state in sorted(relations.items()):
        endpoint_degrees: Counter[int] = Counter()
        ways = []
        missing_nodes: set[int] = set()
        for way_id in state["way_ids"]:
            refs = way_nodes.get(way_id, [])
            if len(refs) < 2:
                errors.append(f"{iso}: member way {way_id} has fewer than two nodes")
                continue
            endpoint_degrees.update((refs[0], refs[-1]))
            coords = []
            for node_id in refs:
                location = node_locations.get(node_id)
                if location is None:
                    missing_nodes.add(node_id)
                else:
                    coords.append([location[0], location[1]])
            if len(coords) == len(refs):
                ways.append(coords)
        odd_endpoints = sorted(
            node_id for node_id, degree in endpoint_degrees.items() if degree % 2
        )
        if odd_endpoints:
            errors.append(
                f"{iso}: {len(odd_endpoints)} odd-degree way endpoints "
                f"(example node ids {odd_endpoints[:8]})"
            )
        if missing_nodes:
            errors.append(
                f"{iso}: {len(missing_nodes)} member-node locations missing "
                f"(example node ids {sorted(missing_nodes)[:8]})"
            )
        states.append(
            {
                "name": state["name"],
                "iso": iso,
                "relation_id": state["relation_id"],
                "ways": ways,
            }
        )

    return {
        "source_timestamp": _source_timestamp(pbf_path),
        "states": states,
    }, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", type=Path, default=DEFAULT_PBF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--allow-incomplete-state",
        action="append",
        default=[],
        metavar="US-XX",
        help="allow a reviewed state-boundary validation failure (repeatable)",
    )
    args = parser.parse_args(argv)
    if not args.pbf.exists():
        print(f"extract not found: {args.pbf}", file=sys.stderr)
        return 2

    payload, errors = extract_boundaries(args.pbf)
    allowed = set(args.allow_incomplete_state)
    failed_states = {error.partition(":")[0] for error in errors}
    payload_states = {state["iso"] for state in payload["states"]}
    if allowed - payload_states or allowed - failed_states:
        invalid = sorted((allowed - payload_states) | (allowed - failed_states))
        print(
            f"ERROR: incomplete-state allowance does not match a failed extracted state: {invalid}",
            file=sys.stderr,
        )
        return 1
    for error in errors:
        level = "WARNING" if error.partition(":")[0] in allowed else "ERROR"
        print(f"{level}: {error}", file=sys.stderr)
    unallowed_errors = [error for error in errors if error.partition(":")[0] not in allowed]
    if unallowed_errors:
        print(
            f"State boundary extraction failed validation: {len(unallowed_errors)} error(s); "
            "cache was not written.",
            file=sys.stderr,
        )
        return 1
    if errors:
        print(
            "Proceeding with the explicitly allowed incomplete state boundary above.",
            file=sys.stderr,
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"states: {len(payload['states'])}; "
        f"source timestamp: {payload['source_timestamp']} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
