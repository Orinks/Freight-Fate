"""Checked-in city service and local approach data loaders."""

from __future__ import annotations

import json
from pathlib import Path

from .world_constants import (
    CITY_SERVICE_ORDER,
    CITY_SERVICE_SOURCE_TYPES,
    RAW_POI_TEXT_MARKERS,
)
from .world_models import LocalApproach, LocalGeometry, LocalGeometrySegment

CITY_SERVICES_PATH = Path(__file__).parent / "city_services.json"
LOCAL_APPROACHES_PATH = Path(__file__).parent / "local_approaches.json"
LOCAL_GEOMETRY_PATH = Path(__file__).parent / "local_geometry.json"


def load_city_service_data(path: Path = CITY_SERVICES_PATH) -> dict[str, dict[str, dict]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
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
                    f"{path} city {city!r} service {name!r} has unknown source_type "
                    f"{source_type!r}"
                )
            if not str(entry.get("source_note", "")).strip():
                raise ValueError(
                    f"{path} city {city!r} service {name!r} has no source note"
                )
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
                raise ValueError(
                    f"{path} city {city!r} service {name!r} has invalid coordinates"
                )
            road = str(entry.get("approach_road", "")).strip()
            if not road:
                raise ValueError(
                    f"{path} city {city!r} service {name!r} has no approach road"
                )
            city_services[key] = dict(entry)
        out[str(city)] = city_services
    return out


def load_local_approaches(path: Path = LOCAL_APPROACHES_PATH) -> dict[str, LocalApproach]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
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
            raise ValueError(
                f"{path} local approach {target_id!r} exposes raw OSM/source text"
            )
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
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
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
            segments.append(LocalGeometrySegment(
                road=road,
                miles=round(miles, 2),
                cue=cue,
                speed_mph=float(raw_segment.get("speed_mph", 25.0)),
            ))
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
