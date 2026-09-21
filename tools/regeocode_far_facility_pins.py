r"""Re-geocode facility endpoint pins with approach_miles > 8 within city bounds.

Uses the same OSM classify/match logic as ``build_facility_endpoints.py``, but
only touches flagged far pins and prefers candidates inside a city-bound
radius so approach_miles lands in Josh's ~1-9 mile band.

Build-time only. Prefers a pre-clipped PBF (city bounds of far pins) or
per-state Geofabrik extracts. Does not call live routing APIs.

Example:
    uv run --group tooling python tools/regeocode_far_facility_pins.py \
      --osm /workspace/osm/extracts/far_facility_cities.osm.pbf
    uv run --group tooling python tools/regeocode_far_facility_pins.py \
      --osm /workspace/osm/extracts/far_facility_cities.osm.pbf --write
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ffworld.world import get_world

ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS_PATH = ROOT / "data" / "facility_endpoints.json"
APPROACHES_PATH = ROOT / "data" / "facility_approaches.json"
ACCESSED_DATE = "2026-09-16"
# Inventory flags >8; Josh band is ~1-9. Match straight-line so approach_miles
# (= max(2.1, min(35, d*1.25))) stays <= 8.0 to clear the blocker.
DEFAULT_CITY_BOUND_MI = 6.4
APPROACH_FAR_MI = 8.0


def _load_endpoints_tool():
    path = ROOT / "tools" / "build_facility_endpoints.py"
    spec = importlib.util.spec_from_file_location("build_facility_endpoints", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class FarTarget:
    facility_id: str
    city: str
    state: str
    facility_name: str
    facility_type: str
    city_lat: float
    city_lon: float
    old: dict[str, Any]


def collect_far_targets(endpoints: dict[str, Any], *, threshold_mi: float) -> list[FarTarget]:
    world = get_world()
    targets: list[FarTarget] = []
    for facility_id, row in endpoints.items():
        miles = float(row.get("approach_miles") or 0.0)
        if miles <= threshold_mi:
            continue
        city_name = str(row["city"])
        city = world.city(city_name)
        # Prefer the world's facility lat/lon (city node / placement) as the
        # approach origin — same as build_facility_endpoints.collect_targets.
        loc_lat, loc_lon = city.lat, city.lon
        for location in city.locations:
            if location.id == facility_id:
                loc_lat = location.lat or city.lat
                loc_lon = location.lon or city.lon
                break
        targets.append(
            FarTarget(
                facility_id=facility_id,
                city=city_name,
                state=str(row.get("state") or city.state),
                facility_name=str(row.get("facility_name") or ""),
                facility_type=str(row.get("facility_type") or ""),
                city_lat=float(loc_lat),
                city_lon=float(loc_lon),
                old=row,
            )
        )
    targets.sort(key=lambda t: t.facility_id)
    return targets


def reserved_refs(endpoints: dict[str, Any], far_ids: set[str]) -> dict[str, set[str]]:
    """source_refs already owned by non-far endpoints in each city."""
    by_city: dict[str, set[str]] = defaultdict(set)
    for facility_id, row in endpoints.items():
        if facility_id in far_ids:
            continue
        ref = row.get("source_ref") or ""
        if ref:
            by_city[str(row["city"])].add(str(ref))
    return by_city


def collect_candidates_from_pbf(osm_path: Path, targets: list[FarTarget], radius_mi: float):
    endpoints_tool = _load_endpoints_tool()
    import osmium

    cities: dict[str, tuple[float, float]] = {}
    for target in targets:
        # One representative point per city (first far target's origin).
        cities.setdefault(target.city, (target.city_lat, target.city_lon))

    buckets: dict[str, list] = defaultdict(list)
    entities = osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY
    keys = [
        "name",
        "operator",
        "brand",
        "industrial",
        "landuse",
        "man_made",
        "building",
        "office",
        "amenity",
        "shop",
        "railway",
        "aeroway",
        "harbour",
        "seamark:type",
        "waterway",
    ]
    processor = (
        osmium.FileProcessor(str(osm_path), entities=entities)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter(*keys))
    )
    for obj in processor:
        tags = endpoints_tool._tags(obj.tags)
        if hasattr(obj, "nodes"):
            coords = endpoints_tool._way_coords(obj)
            if not coords:
                continue
            lat, lon = endpoints_tool._centroid(coords)
            candidate = endpoints_tool.candidate_from_tags(tags, lat, lon, f"way/{obj.id}")
            if candidate is None:
                continue
            for city in endpoints_tool.nearby_cities(cities, lat, lon, radius_mi):
                buckets[city].append(candidate)
            continue
        try:
            if not obj.location.valid():
                continue
            lat = float(obj.location.lat)
            lon = float(obj.location.lon)
        except osmium.InvalidLocationError:
            continue
        candidate = endpoints_tool.candidate_from_tags(tags, lat, lon, f"node/{obj.id}")
        if candidate is None:
            continue
        for city in endpoints_tool.nearby_cities(cities, lat, lon, radius_mi):
            buckets[city].append(candidate)
    return buckets, endpoints_tool


def estimated_near_city(target: FarTarget, endpoints_tool) -> dict[str, Any]:
    """Unresolvable far pin -> representative near-city placement."""
    record = endpoints_tool.fallback_record(
        endpoints_tool.FacilityTarget(
            facility_id=target.facility_id,
            city=target.city,
            state=target.state,
            name=target.facility_name,
            facility_type=target.facility_type,
            lat=target.city_lat,
            lon=target.city_lon,
            source_note="",
        ),
        reason=(
            "Re-geocode within city bounds found no high-confidence OSM "
            f"name+type match inside {DEFAULT_CITY_BOUND_MI:.1f} mi; "
            "estimated near city pending better source evidence."
        ),
    )
    # Floor at bake minimum so synthetic approaches stay in Josh's band.
    record["approach_miles"] = 2.1
    record["approach_road"] = "local facility access road"
    record["estimated"] = True
    record["source_note"] = (
        f"Estimated-near-city placement for {target.facility_name} in {target.city}; "
        "prior source-backed pin sat past 8 approach miles and no in-bound OSM "
        f"match was found; accessed {ACCESSED_DATE}."
    )
    return record


def matched_record(target: FarTarget, candidate, endpoints_tool) -> dict[str, Any]:
    miles = endpoints_tool.approach_miles(
        target.city_lat, target.city_lon, candidate.lat, candidate.lon
    )
    return {
        "facility_id": target.facility_id,
        "city": target.city,
        "state": target.state,
        "facility_name": target.facility_name,
        "facility_type": target.facility_type,
        "endpoint_name": candidate.name,
        "lat": round(candidate.lat, 6),
        "lon": round(candidate.lon, 6),
        "approach_miles": miles,
        "approach_road": "local facility access road",
        "source_type": "osm_facility_endpoint",
        "source_ref": candidate.source_ref,
        "source_backed": True,
        "fallback": False,
        "fallback_reason": "",
        "nearest_road_context": False,
        "turn_level_geometry": False,
        "gate_hint": False,
        "yard_hint": False,
        "dock_hint": False,
        "mapping": candidate.mapping,
        "source_note": (
            "Re-geocoded freight facility endpoint within city bounds from OpenStreetMap; "
            f"matched to {target.facility_type} by {candidate.mapping}; "
            f"prior pin had approach_miles={target.old.get('approach_miles')}; "
            "road snapping, gates, yards, and docks are not claimed by this layer; "
            f"accessed {ACCESSED_DATE}."
        ),
    }


def sync_approach_record(approach: dict[str, Any], endpoint: dict[str, Any]) -> dict[str, Any]:
    """Keep facility_approaches endpoint fields aligned after pin moves.

    Does not invent road-snap geometry; only refreshes endpoint metadata and
    estimated single-leg miles when the approach was not turn-level snapped.
    """
    updated = dict(approach)
    updated["endpoint_name"] = endpoint.get("endpoint_name", updated.get("endpoint_name"))
    updated["endpoint_source_backed"] = bool(endpoint.get("source_backed"))
    if endpoint.get("fallback"):
        updated["representative_fallback"] = True
        updated["fallback"] = True
        updated["estimated"] = True
        updated["road_snapped"] = False
        updated["turn_level_geometry"] = False
        miles = float(endpoint.get("approach_miles") or 2.1)
        road = (
            endpoint.get("approach_road") or updated.get("approach_road") or "facility access road"
        )
        updated["approach_road"] = road
        updated["total_miles"] = miles
        updated["segments"] = [
            {
                "cue": f"Use {road} for the facility approach.",
                "miles": miles,
                "road": road,
            }
        ]
        updated["final_hint"] = (
            "Facility approach uses estimated-near-city context after re-geocode; "
            "final gate, yard, dock, and driveway are not source-backed."
        )
        updated["fallback_reason"] = endpoint.get("fallback_reason") or updated.get(
            "fallback_reason", ""
        )
    elif not updated.get("road_snapped") and not updated.get("turn_level_geometry"):
        # Non-snapped estimated approaches: refresh miles to the new pin distance.
        miles = float(endpoint.get("approach_miles") or updated.get("total_miles") or 2.1)
        updated["total_miles"] = miles
        segments = updated.get("segments") or []
        if len(segments) == 1 and isinstance(segments[0], dict):
            seg = dict(segments[0])
            seg["miles"] = miles
            updated["segments"] = [seg]
        updated["estimated"] = True
    return updated


def regeocode(
    *,
    osm_path: Path,
    city_bound_mi: float,
    threshold_mi: float,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    endpoints_payload = json.loads(ENDPOINTS_PATH.read_text(encoding="utf-8"))
    approaches_payload = json.loads(APPROACHES_PATH.read_text(encoding="utf-8"))
    endpoints: dict[str, Any] = dict(endpoints_payload["endpoints"])
    approaches: dict[str, Any] = dict(approaches_payload.get("approaches") or {})

    targets = collect_far_targets(endpoints, threshold_mi=threshold_mi)
    far_ids = {t.facility_id for t in targets}
    reserved = reserved_refs(endpoints, far_ids)

    print(
        f"Scanning {osm_path} for {len(targets)} far pins "
        f"across {len({t.city for t in targets})} cities "
        f"(bound={city_bound_mi:.1f} mi)...",
        flush=True,
    )
    buckets, endpoints_tool = collect_candidates_from_pbf(osm_path, targets, city_bound_mi)

    used_refs: dict[str, set[str]] = {city: set(refs) for city, refs in reserved.items()}
    summary = {
        "before_far": len(targets),
        "matched": 0,
        "estimated_near_city": 0,
        "still_far_after_match": 0,
        "matched_by_band": defaultdict(int),
        "samples": [],
    }
    updates: list[dict[str, Any]] = []

    for target in targets:
        city_used = used_refs.setdefault(target.city, set())
        candidate = endpoints_tool.choose_candidate(
            endpoints_tool.FacilityTarget(
                facility_id=target.facility_id,
                city=target.city,
                state=target.state,
                name=target.facility_name,
                facility_type=target.facility_type,
                lat=target.city_lat,
                lon=target.city_lon,
                source_note="",
            ),
            buckets.get(target.city, []),
            city_used,
        )
        if candidate is None:
            record = estimated_near_city(target, endpoints_tool)
            summary["estimated_near_city"] += 1
            action = "estimated_near_city"
        else:
            record = matched_record(target, candidate, endpoints_tool)
            miles = float(record["approach_miles"])
            # Inventory clears at <=8; Josh band tops at ~9. Reject in-bound
            # matches that still land past the far threshold and estimate instead.
            if miles > threshold_mi:
                summary["still_far_after_match"] += 1
                record = estimated_near_city(target, endpoints_tool)
                summary["estimated_near_city"] += 1
                action = "estimated_after_far_match"
            else:
                city_used.add(candidate.source_ref)
                summary["matched"] += 1
                if miles >= 35:
                    band = "ge_35"
                elif miles >= 20:
                    band = "20_to_35"
                elif miles >= 12:
                    band = "12_to_20"
                elif miles > 8:
                    band = "8_to_12"
                else:
                    band = "le_8"
                summary["matched_by_band"][band] += 1
                action = "matched"

        updates.append(
            {
                "facility_id": target.facility_id,
                "action": action,
                "old_approach_miles": target.old.get("approach_miles"),
                "new_approach_miles": record["approach_miles"],
                "old_source_ref": target.old.get("source_ref"),
                "new_source_ref": record.get("source_ref"),
                "fallback": record.get("fallback"),
            }
        )
        if len(summary["samples"]) < 12:
            summary["samples"].append(updates[-1])

        endpoints[target.facility_id] = record
        if target.facility_id in approaches:
            approaches[target.facility_id] = sync_approach_record(
                approaches[target.facility_id], record
            )

    # Coverage recount for endpoints payload.
    endpoints_payload = dict(endpoints_payload)
    endpoints_payload["endpoints"] = endpoints
    endpoints_payload["coverage"] = endpoints_tool.coverage_summary(endpoints)
    gen = dict(endpoints_payload.get("generated") or {})
    gen["regeocode_far_pins"] = {
        "accessed": ACCESSED_DATE,
        "city_bound_mi": city_bound_mi,
        "threshold_mi": threshold_mi,
        "osm": str(osm_path),
        "matched": summary["matched"],
        "estimated_near_city": summary["estimated_near_city"],
    }
    endpoints_payload["generated"] = gen

    approaches_payload = dict(approaches_payload)
    approaches_payload["approaches"] = approaches
    approaches_payload["coverage"] = {
        "facilities": len(approaches),
        "source_backed_endpoints": sum(
            1 for item in approaches.values() if item.get("endpoint_source_backed")
        ),
        "road_snapped": sum(1 for item in approaches.values() if item.get("road_snapped")),
        "turn_level": sum(1 for item in approaches.values() if item.get("turn_level")),
        "nearest_road_fallback": sum(
            1
            for item in approaches.values()
            if item.get("endpoint_source_backed") and not item.get("road_snapped")
        ),
        "representative_fallback": sum(
            1 for item in approaches.values() if item.get("representative_fallback")
        ),
        "gate_yard_dock_hints": sum(
            1
            for item in approaches.values()
            if item.get("gate_hint") or item.get("yard_hint") or item.get("dock_hint")
        ),
    }
    agen = dict(approaches_payload.get("generated") or {})
    agen["regeocode_far_pins"] = gen["regeocode_far_pins"]
    approaches_payload["generated"] = agen

    summary["matched_by_band"] = dict(summary["matched_by_band"])
    summary["updates"] = updates
    after_far = sum(
        1 for row in endpoints.values() if float(row.get("approach_miles") or 0) > threshold_mi
    )
    summary["after_far"] = after_far
    return endpoints_payload, approaches_payload, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--osm",
        type=Path,
        required=True,
        help="PBF covering far-pin city bounds (or national/state extracts)",
    )
    parser.add_argument("--city-bound-mi", type=float, default=DEFAULT_CITY_BOUND_MI)
    parser.add_argument("--threshold-mi", type=float, default=APPROACH_FAR_MI)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--report", type=Path, help="optional JSON report path")
    args = parser.parse_args()

    if not args.osm.is_file():
        print(f"OSM file not found: {args.osm}", file=sys.stderr)
        return 2

    endpoints_payload, approaches_payload, summary = regeocode(
        osm_path=args.osm,
        city_bound_mi=args.city_bound_mi,
        threshold_mi=args.threshold_mi,
    )
    report = {
        "before_far": summary["before_far"],
        "after_far": summary["after_far"],
        "matched": summary["matched"],
        "estimated_near_city": summary["estimated_near_city"],
        "still_far_after_match": summary["still_far_after_match"],
        "matched_by_band": summary["matched_by_band"],
        "samples": summary["samples"],
        "write_paths": [str(ENDPOINTS_PATH), str(APPROACHES_PATH)],
    }
    print(json.dumps({k: report[k] for k in report if k != "samples"}, indent=2, sort_keys=True))
    print("samples:", flush=True)
    for row in summary["samples"]:
        print(
            f"  {row['action']:20} {row['facility_id']}: "
            f"{row['old_approach_miles']} -> {row['new_approach_miles']}",
            flush=True,
        )

    if args.report:
        args.report.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote report {args.report}")

    if args.write:
        ENDPOINTS_PATH.write_text(
            json.dumps(endpoints_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        APPROACHES_PATH.write_text(
            json.dumps(approaches_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {ENDPOINTS_PATH}")
        print(f"Wrote {APPROACHES_PATH}")
    else:
        print("Dry-run only (pass --write to persist).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
