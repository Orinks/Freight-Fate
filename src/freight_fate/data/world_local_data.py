"""Checked-in city service and local approach data loaders."""

from __future__ import annotations

import json
from pathlib import Path

from .data_resources import read_data_text
from .world_constants import (
    CITY_SERVICE_ORDER,
    CITY_SERVICE_SOURCE_TYPES,
    RAW_POI_TEXT_MARKERS,
)
from .world_models import (
    FacilityApproach,
    FacilityEndpoint,
    LocalApproach,
    LocalGeometry,
    LocalGeometrySegment,
)

CITY_SERVICES_PATH = Path(__file__).parent / "city_services.json"
LOCAL_APPROACHES_PATH = Path(__file__).parent / "local_approaches.json"
LOCAL_GEOMETRY_PATH = Path(__file__).parent / "local_geometry.json"
FACILITY_ENDPOINTS_PATH = Path(__file__).parent / "facility_endpoints.json"
FACILITY_APPROACHES_PATH = Path(__file__).parent / "facility_approaches.json"


def _read_runtime_json(path: Path, default_path: Path, name: str) -> dict | None:
    """Parse a runtime data file: baked in frozen builds when the caller
    kept the default path, read from disk when a test injected its own."""
    if path == default_path:
        text = read_data_text(name)
    elif path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = None
    if text is None:
        return None
    return json.loads(text.lstrip("﻿"))


def load_city_service_data(path: Path = CITY_SERVICES_PATH) -> dict[str, dict[str, dict]]:
    raw = _read_runtime_json(path, CITY_SERVICES_PATH, "city_services.json")
    if raw is None:
        return {}
    cities = raw.get("cities", {})
    if not isinstance(cities, dict):
        raise ValueError(f"{path} must contain a cities object")
    out: dict[str, dict[str, dict]] = {}
    for city, entries in cities.items():
        if not isinstance(entries, list):
            raise ValueError(f"{path} city {city!r} must contain a service list")
        city_services: dict[str, dict] = {}
        for entry in entries:
            key = str(entry.get("key", "")).strip()
            if key not in CITY_SERVICE_ORDER:
                raise ValueError(f"{path} city {city!r} has unknown service key {key!r}")
            if key in city_services:
                raise ValueError(f"{path} city {city!r} repeats service key {key!r}")
            name = str(entry.get("name", "")).strip()
            lowered = name.lower()
            if not name:
                raise ValueError(f"{path} city {city!r} service {key!r} has no name")
            if any(marker in lowered for marker in RAW_POI_TEXT_MARKERS):
                raise ValueError(
                    f"{path} city {city!r} service {name!r} exposes raw OSM/source text"
                )
            source_type = str(entry.get("source_type", "fallback")).strip()
            if source_type not in CITY_SERVICE_SOURCE_TYPES:
                raise ValueError(
                    f"{path} city {city!r} service {name!r} has unknown source_type {source_type!r}"
                )
            if not str(entry.get("source_note", "")).strip():
                raise ValueError(f"{path} city {city!r} service {name!r} has no source note")
            fallback = bool(entry.get("fallback", False))
            fallback_reason = str(entry.get("fallback_reason", "")).strip()
            if fallback and not fallback_reason:
                raise ValueError(
                    f"{path} city {city!r} service {name!r} is fallback without a reason"
                )
            approach_miles = float(entry.get("approach_miles", 0.0))
            if approach_miles <= 0.0 or approach_miles > 50.0:
                raise ValueError(
                    f"{path} city {city!r} service {name!r} has invalid approach miles"
                )
            lat = float(entry.get("lat", 0.0))
            lon = float(entry.get("lon", 0.0))
            if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
                raise ValueError(f"{path} city {city!r} service {name!r} has invalid coordinates")
            road = str(entry.get("approach_road", "")).strip()
            if not road:
                raise ValueError(f"{path} city {city!r} service {name!r} has no approach road")
            city_services[key] = dict(entry)
        out[str(city)] = city_services
    return out


def load_local_approaches(path: Path = LOCAL_APPROACHES_PATH) -> dict[str, LocalApproach]:
    raw = _read_runtime_json(path, LOCAL_APPROACHES_PATH, "local_approaches.json")
    if raw is None:
        return {}
    records = raw.get("approaches", {})
    if not isinstance(records, dict):
        raise ValueError(f"{path} must contain an approaches object")
    out: dict[str, LocalApproach] = {}
    for target_id, entry in records.items():
        name = str(entry.get("name", "")).strip()
        road = str(entry.get("road", "")).strip()
        target_type = str(entry.get("target_type", "")).strip()
        city = str(entry.get("city", "")).strip()
        source_type = str(entry.get("source_type", "")).strip()
        if not name or not road or not target_type or not city or not source_type:
            raise ValueError(f"{path} local approach {target_id!r} is missing required text")
        lowered = f"{name} {road}".lower()
        if any(marker in lowered for marker in RAW_POI_TEXT_MARKERS):
            raise ValueError(f"{path} local approach {target_id!r} exposes raw OSM/source text")
        approach_miles = float(entry.get("approach_miles", 0.0))
        if approach_miles <= 0.0 or approach_miles > 75.0:
            raise ValueError(f"{path} local approach {target_id!r} has invalid mileage")
        fallback = bool(entry.get("fallback", False))
        fallback_reason = str(entry.get("fallback_reason", "")).strip()
        if fallback and not fallback_reason:
            raise ValueError(f"{path} local approach {target_id!r} is fallback without reason")
        raw_segments = entry.get("turn_segments", ())
        segments = tuple(str(segment).strip() for segment in raw_segments if str(segment).strip())
        for segment in segments:
            lowered_segment = segment.lower()
            if any(marker in lowered_segment for marker in RAW_POI_TEXT_MARKERS):
                raise ValueError(
                    f"{path} local approach {target_id!r} segment exposes raw source text"
                )
        out[str(target_id)] = LocalApproach(
            target_id=str(target_id),
            target_type=target_type,
            city=city,
            name=name,
            approach_miles=round(approach_miles, 1),
            road=road,
            source_type=source_type,
            estimated=bool(entry.get("estimated", True)),
            fallback=fallback,
            fallback_reason=fallback_reason,
            distance_to_road_mi=round(float(entry.get("distance_to_road_mi", 0.0)), 2),
            turn_segments=segments,
        )
    return out


def load_local_geometries(path: Path = LOCAL_GEOMETRY_PATH) -> dict[str, LocalGeometry]:
    raw = _read_runtime_json(path, LOCAL_GEOMETRY_PATH, "local_geometry.json")
    if raw is None:
        return {}
    records = raw.get("geometries", {})
    if not isinstance(records, dict):
        raise ValueError(f"{path} must contain a geometries object")
    out: dict[str, LocalGeometry] = {}
    for target_id, entry in records.items():
        name = str(entry.get("name", "")).strip()
        target_type = str(entry.get("target_type", "")).strip()
        city = str(entry.get("city", "")).strip()
        source_type = str(entry.get("source_type", "")).strip()
        if not name or not target_type or not city or not source_type:
            raise ValueError(f"{path} local geometry {target_id!r} is missing required text")
        if any(marker in name.lower() for marker in RAW_POI_TEXT_MARKERS):
            raise ValueError(f"{path} local geometry {target_id!r} exposes raw source text")
        fallback = bool(entry.get("fallback", False))
        turn_level = bool(entry.get("turn_level", False))
        fallback_reason = str(entry.get("fallback_reason", "")).strip()
        if fallback and not fallback_reason:
            raise ValueError(f"{path} local geometry {target_id!r} is fallback without reason")
        raw_segments = entry.get("segments", ())
        segments: list[LocalGeometrySegment] = []
        for raw_segment in raw_segments:
            road = str(raw_segment.get("road", "")).strip()
            cue = str(raw_segment.get("cue", "")).strip()
            miles = float(raw_segment.get("miles", 0.0))
            if not road or not cue or miles <= 0.0:
                raise ValueError(f"{path} local geometry {target_id!r} has invalid segment")
            lowered = f"{road} {cue}".lower()
            if any(marker in lowered for marker in RAW_POI_TEXT_MARKERS):
                raise ValueError(
                    f"{path} local geometry {target_id!r} segment exposes raw source text"
                )
            segments.append(
                LocalGeometrySegment(
                    road=road,
                    miles=round(miles, 2),
                    cue=cue,
                    speed_mph=float(raw_segment.get("speed_mph", 25.0)),
                )
            )
        total_miles = round(float(entry.get("total_miles", 0.0)), 2)
        if turn_level:
            if not segments:
                raise ValueError(f"{path} local geometry {target_id!r} has no segments")
            if total_miles <= 0.0:
                raise ValueError(f"{path} local geometry {target_id!r} has invalid mileage")
        out[str(target_id)] = LocalGeometry(
            target_id=str(target_id),
            target_type=target_type,
            city=city,
            name=name,
            turn_level=turn_level,
            source_type=source_type,
            estimated=bool(entry.get("estimated", True)),
            fallback=fallback,
            fallback_reason=fallback_reason,
            total_miles=total_miles,
            segments=tuple(segments),
        )
    return out


def load_facility_endpoints(path: Path = FACILITY_ENDPOINTS_PATH) -> dict[str, FacilityEndpoint]:
    raw = _read_runtime_json(path, FACILITY_ENDPOINTS_PATH, "facility_endpoints.json")
    if raw is None:
        return {}
    records = raw.get("endpoints", {})
    if not isinstance(records, dict):
        raise ValueError(f"{path} must contain an endpoints object")
    out: dict[str, FacilityEndpoint] = {}
    for facility_id, entry in records.items():
        name = str(entry.get("endpoint_name", "")).strip()
        facility_name = str(entry.get("facility_name", "")).strip()
        road = str(entry.get("approach_road", "")).strip()
        source_type = str(entry.get("source_type", "")).strip()
        source_note = str(entry.get("source_note", "")).strip()
        city = str(entry.get("city", "")).strip()
        state = str(entry.get("state", "")).strip()
        facility_type = str(entry.get("facility_type", "")).strip()
        if not name or not facility_name or not source_type or not source_note:
            raise ValueError(f"{path} facility endpoint {facility_id!r} is missing text")
        lowered = f"{name} {facility_name} {road}".lower()
        if any(marker in lowered for marker in RAW_POI_TEXT_MARKERS):
            raise ValueError(f"{path} facility endpoint {facility_id!r} exposes raw source text")
        fallback = bool(entry.get("fallback", True))
        fallback_reason = str(entry.get("fallback_reason", "")).strip()
        if fallback and not fallback_reason:
            raise ValueError(f"{path} facility endpoint {facility_id!r} is fallback without reason")
        approach_miles = float(entry.get("approach_miles", 0.0))
        if not fallback and (approach_miles <= 0.0 or approach_miles > 50.0 or not road):
            raise ValueError(f"{path} facility endpoint {facility_id!r} has invalid approach")
        lat = float(entry.get("lat", 0.0))
        lon = float(entry.get("lon", 0.0))
        if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
            raise ValueError(f"{path} facility endpoint {facility_id!r} has invalid coordinates")
        out[str(facility_id)] = FacilityEndpoint(
            facility_id=str(facility_id),
            city=city,
            state=state,
            facility_name=facility_name,
            facility_type=facility_type,
            endpoint_name=name,
            source_type=source_type,
            source_note=source_note,
            lat=lat,
            lon=lon,
            approach_miles=round(approach_miles, 1),
            approach_road=road,
            source_ref=str(entry.get("source_ref", "")).strip(),
            source_backed=bool(entry.get("source_backed", False)),
            fallback=fallback,
            fallback_reason=fallback_reason,
            nearest_road_context=bool(entry.get("nearest_road_context", False)),
            turn_level_geometry=bool(entry.get("turn_level_geometry", False)),
            gate_hint=bool(entry.get("gate_hint", False)),
            yard_hint=bool(entry.get("yard_hint", False)),
            dock_hint=bool(entry.get("dock_hint", False)),
            mapping=str(entry.get("mapping", "")).strip(),
        )
    return out


def load_facility_approaches(path: Path = FACILITY_APPROACHES_PATH) -> dict[str, FacilityApproach]:
    raw = _read_runtime_json(path, FACILITY_APPROACHES_PATH, "facility_approaches.json")
    if raw is None:
        return {}
    records = raw.get("approaches", {})
    if not isinstance(records, dict):
        raise ValueError(f"{path} must contain an approaches object")
    out: dict[str, FacilityApproach] = {}
    for facility_id, entry in records.items():
        facility_name = str(entry.get("facility_name", "")).strip()
        endpoint_name = str(entry.get("endpoint_name", "")).strip()
        road = str(entry.get("approach_road", "")).strip()
        source_type = str(entry.get("source_type", "")).strip()
        if not facility_name or not endpoint_name or not road or not source_type:
            raise ValueError(f"{path} facility approach {facility_id!r} is missing text")
        spoken = f"{facility_name} {endpoint_name} {road}".lower()
        if any(marker in spoken for marker in RAW_POI_TEXT_MARKERS):
            raise ValueError(f"{path} facility approach {facility_id!r} exposes raw source text")
        fallback = bool(entry.get("fallback", True))
        fallback_reason = str(entry.get("fallback_reason", "")).strip()
        if fallback and not fallback_reason:
            raise ValueError(f"{path} facility approach {facility_id!r} is fallback without reason")
        segments = []
        for raw_segment in entry.get("segments", ()):
            segment_road = str(raw_segment.get("road", "")).strip()
            cue = str(raw_segment.get("cue", "")).strip()
            miles = float(raw_segment.get("miles", 0.0))
            if not segment_road or not cue or miles <= 0.0:
                raise ValueError(f"{path} facility approach {facility_id!r} has invalid segment")
            lowered = f"{segment_road} {cue}".lower()
            if any(marker in lowered for marker in RAW_POI_TEXT_MARKERS):
                raise ValueError(
                    f"{path} facility approach {facility_id!r} segment exposes raw text"
                )
            segments.append(
                LocalGeometrySegment(
                    road=segment_road,
                    miles=round(miles, 2),
                    cue=cue,
                    speed_mph=float(raw_segment.get("speed_mph", 25.0)),
                )
            )
        turn_level = bool(entry.get("turn_level", False))
        if turn_level and not segments:
            raise ValueError(f"{path} facility approach {facility_id!r} has no turn segments")
        out[str(facility_id)] = FacilityApproach(
            facility_id=str(facility_id),
            city=str(entry.get("city", "")).strip(),
            state=str(entry.get("state", "")).strip(),
            facility_name=facility_name,
            facility_type=str(entry.get("facility_type", "")).strip(),
            endpoint_name=endpoint_name,
            endpoint_source_backed=bool(entry.get("endpoint_source_backed", False)),
            road_snapped=bool(entry.get("road_snapped", False)),
            turn_level=turn_level,
            source_type=source_type,
            estimated=bool(entry.get("estimated", True)),
            fallback=fallback,
            fallback_reason=fallback_reason,
            nearest_road_context=bool(entry.get("nearest_road_context", False)),
            representative_fallback=bool(entry.get("representative_fallback", True)),
            total_miles=round(float(entry.get("total_miles", 0.0)), 2),
            approach_road=road,
            segments=tuple(segments),
            gate_hint=bool(entry.get("gate_hint", False)),
            yard_hint=bool(entry.get("yard_hint", False)),
            dock_hint=bool(entry.get("dock_hint", False)),
            final_hint=str(entry.get("final_hint", "")).strip(),
            source_note=str(entry.get("source_note", "")).strip(),
        )
    return out
