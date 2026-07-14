# ruff: noqa: F403,F405
"""Parsing helpers for checked-in world data."""

from __future__ import annotations

import re
import zlib

from .legacy_aliases import LEGACY_CITY_SLUGS
from .world_constants import *
from .world_models import *


def _overlay_city_key(name: str, cities: dict) -> str:
    """The key an overlay city name lands on: itself, or the slug it aliases.

    Overlays written before the slug migration name cities by display name;
    treating those as the base city they alias keeps the merge additive
    instead of duplicating the city under its old name.
    """
    if name in cities:
        return name
    slug = LEGACY_CITY_SLUGS.get(name)
    return slug if slug in cities else name


def _leg_pair_key(leg: dict, cities: dict) -> frozenset:
    return frozenset(
        (_overlay_city_key(leg.get("from"), cities), _overlay_city_key(leg.get("to"), cities))
    )


def _merge_overlay(base: dict, overlay: dict) -> dict:
    """Return ``base`` with overlay cities and legs added, never overridden.

    The merge is purely additive so the checked-in base stays authoritative:
    a city already present (by key, or by a pre-slug legacy name aliasing one)
    keeps its base definition, and a leg already present (by unordered endpoint
    pair) keeps its base definition. Only genuinely new cities and legs from
    the overlay are appended. The base dict is not mutated.
    """
    merged = dict(base)
    cities = dict(base.get("cities", {}))
    for name, city in overlay.get("cities", {}).items():
        if _overlay_city_key(name, cities) not in cities:
            cities[name] = city
    merged["cities"] = cities

    legs = list(base.get("legs", []))
    seen = {_leg_pair_key(leg, cities) for leg in legs}
    for leg in overlay.get("legs", []):
        key = _leg_pair_key(leg, cities)
        if key not in seen:
            seen.add(key)
            legs.append(leg)
    merged["legs"] = legs
    return merged


def _parse_location(
    raw: dict, city_key: str, spoken_city: str, city_lat: float, city_lon: float
) -> Location:
    if not isinstance(raw, dict):
        raise ValueError(f"{spoken_city} facility must be an object")
    name = _clean_facility_name(spoken_city, str(raw.get("name", "")).strip())
    facility_type = str(raw.get("type", "")).strip()
    if facility_type not in FREIGHT_LOCATION_TYPES:
        raise ValueError(f"{spoken_city} facility {name!r} has unknown type {facility_type!r}")
    default_roles = FACILITY_CARGO_ROLES.get(facility_type, {})
    raw_cargo = tuple(str(cargo).strip() for cargo in raw.get("cargo", ()) if str(cargo).strip())
    default_cargo = _dedupe(default_roles.get("ships", ()) + default_roles.get("receives", ()))
    cargo = raw_cargo or default_cargo
    ships = _role_cargo(raw, "ships", cargo, default_roles.get("ships", ()))
    receives = _role_cargo(raw, "receives", cargo, default_roles.get("receives", ()))
    roles = tuple(role for role, values in (("shipper", ships), ("receiver", receives)) if values)
    source_note = str(
        raw.get("source_note")
        or raw.get("source")
        or FACILITY_SOURCE_NOTES.get(facility_type, "Curated representative facility.")
    ).strip()
    spoken = str(raw.get("spoken_name") or raw.get("spoken") or "").strip()
    locality = str(raw.get("locality", "")).strip()
    traits = tuple(str(trait).strip() for trait in raw.get("traits", ()) if str(trait).strip())
    return Location(
        name=name,
        type=facility_type,
        cargo=cargo,
        id=str(raw.get("id") or _stable_facility_id(city_key, facility_type, name)).strip(),
        city=city_key,
        locality=locality,
        roles=roles,
        ships=ships,
        receives=receives,
        lat=float(raw.get("lat", city_lat)),
        lon=float(raw.get("lon", city_lon)),
        traits=traits,
        source_note=source_note,
        spoken=spoken,
        template=bool(raw.get("template", False)),
        min_level=int(raw.get("min_level", FACILITY_LEVEL_UNLOCKS.get(facility_type, 1))),
    )


def _expand_market_locations(
    city_key: str,
    spoken_city: str,
    lat: float,
    lon: float,
    explicit_locations: tuple[Location, ...],
    market_tags: tuple[str, ...],
) -> tuple[Location, ...]:
    locations = list(explicit_locations)
    existing_types = {location.type for location in locations}
    existing_names = {location.name.lower() for location in locations}
    desired_types = list(BASE_MARKET_FACILITY_TYPES)
    for tag in market_tags:
        desired_types.extend(MARKET_TAG_FACILITY_TYPES.get(tag, ()))
    for facility_type in _dedupe(desired_types):
        if facility_type in existing_types:
            continue
        location = _template_location(city_key, spoken_city, lat, lon, facility_type, market_tags)
        if location.name.lower() in existing_names:
            location = _template_location(
                city_key,
                spoken_city,
                lat,
                lon,
                facility_type,
                market_tags,
                name_suffix=" Facility",
            )
        locations.append(location)
        existing_types.add(location.type)
        existing_names.add(location.name.lower())
    return tuple(locations)


def _template_location(
    city_key: str,
    spoken_city: str,
    lat: float,
    lon: float,
    facility_type: str,
    market_tags: tuple[str, ...],
    name_suffix: str = "",
) -> Location:
    template = FACILITY_NAME_TEMPLATES[facility_type]
    name = template.format(city=spoken_city) + name_suffix
    roles = FACILITY_CARGO_ROLES[facility_type]
    cargo = _dedupe(roles["ships"] + roles["receives"])
    source_note = (
        f"{FACILITY_SOURCE_NOTES[facility_type]} Generated offline as a "
        f"representative {spoken_city} metro-market facility; not a claim about a "
        "specific real-world shipper."
    )
    jitter_lat, jitter_lon = _jittered_coordinates(city_key, facility_type, lat, lon)
    return Location(
        name=name,
        type=facility_type,
        cargo=cargo,
        id=_stable_facility_id(city_key, facility_type, name),
        city=city_key,
        roles=("shipper", "receiver"),
        ships=roles["ships"],
        receives=roles["receives"],
        lat=jitter_lat,
        lon=jitter_lon,
        traits=("representative", "template") + market_tags,
        source_note=source_note,
        template=True,
        min_level=FACILITY_LEVEL_UNLOCKS.get(facility_type, 1),
    )


def _market_tags_for_city(
    city_key: str, state_code: str, raw_city: dict, locations: tuple[Location, ...]
) -> tuple[str, ...]:
    tags: set[str] = set(REGION_MARKET_TAGS.get(str(raw_city.get("region", "")), ()))
    tags.update(STATE_MARKET_TAGS.get(state_code, ()))
    tags.update(CITY_MARKET_TAGS.get(city_key, ()))
    for location in locations:
        tags.update(_tags_for_facility_type(location.type))
    return tuple(sorted(tags))


def _tags_for_facility_type(facility_type: str) -> tuple[str, ...]:
    return {
        "air_cargo": ("air",),
        "distribution": ("retail",),
        "food_terminal": ("food", "cold_chain"),
        "industrial_park": ("industrial",),
        "intermodal": ("intermodal",),
        "manufacturing": ("manufacturing",),
        "port": ("port",),
        "rail": ("intermodal",),
        "retail_distribution": ("retail",),
        "terminal": ("cross_dock",),
        "warehouse": ("retail",),
    }.get(facility_type, ())


def _role_cargo(
    raw: dict, key: str, cargo: tuple[str, ...], defaults: tuple[str, ...]
) -> tuple[str, ...]:
    values = tuple(str(value).strip() for value in raw.get(key, ()) if str(value).strip())
    if values:
        return values
    plausible = tuple(value for value in cargo if value in defaults)
    return plausible or tuple(value for value in cargo if value)


def _clean_facility_name(city: str, name: str) -> str:
    if not name:
        raise ValueError(f"{city} has a facility without a name")
    lowered = name.lower()
    if any(marker in lowered for marker in RAW_FACILITY_TEXT_MARKERS):
        raise ValueError(f"{city} facility {name!r} exposes raw source text")
    return name


def _stable_facility_id(city: str, facility_type: str, name: str) -> str:
    return f"{_slug(city)}:{facility_type}:{_slug(name)}"


def _service_city_slug(text: str) -> str:
    """The city fragment of a local city-service id ("Sault Ste. Marie" ->
    "sault-ste-marie"), matching how the local-data sweep slugged names."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _slug(text: str) -> str:
    out: list[str] = []
    pending_dash = False
    for char in text.lower():
        if char.isalnum():
            if pending_dash and out:
                out.append("-")
            out.append(char)
            pending_dash = False
        else:
            pending_dash = True
    return "".join(out).strip("-") or "facility"


def _dedupe(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


def _jittered_coordinates(
    city: str, facility_type: str, lat: float, lon: float
) -> tuple[float, float]:
    if lat == 0.0 and lon == 0.0:
        return lat, lon
    seed = zlib.crc32(f"{city}:{facility_type}".encode())
    lat_offset = ((seed & 0xFF) - 128) / 5000.0
    lon_offset = (((seed >> 8) & 0xFF) - 128) / 5000.0
    return round(lat + lat_offset, 5), round(lon + lon_offset, 5)


def _is_legacy_market_name(city_names: tuple[str, ...], name: str) -> bool:
    """True when ``name`` is one of the old whole-city market placeholders.

    Checked against every name the city has answered to (current spoken plus
    frozen legacy display names) so pre-slug saves keep resolving."""
    normalized = name.strip().lower()
    if not normalized:
        return True
    for city_name in city_names:
        city_lower = city_name.lower()
        if normalized in {
            city_lower,
            f"{city_lower} freight market",
            f"{city_lower} metro freight market",
        }:
            return True
    return False


def _parse_stop(raw, leg_miles: float, from_city: str, to_city: str) -> Stop:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} stop {raw!r} is missing explicit at_mi")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} has a stop without a name")
    lowered_name = name.lower()
    if any(marker in lowered_name for marker in RAW_POI_TEXT_MARKERS):
        raise ValueError(f"{from_city} to {to_city} stop {name!r} exposes raw OSM/source text")
    if "at_mi" not in raw:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} is missing explicit at_mi")
    at_mi = float(raw["at_mi"])
    if not 0.0 < at_mi < leg_miles:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has at_mi {at_mi}, "
            f"outside leg mileage 0-{leg_miles}"
        )
    stop_type = str(raw.get("type", "")).strip() or _classify_stop(name)
    if stop_type not in STOP_TYPE_LABELS:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has unknown type {stop_type!r}")
    source = str(raw.get("source", "")).strip()
    actions = tuple(
        str(action).strip() for action in raw.get("actions", DEFAULT_POI_ACTIONS[stop_type])
    )
    if not actions:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has no actions")
    unknown = sorted(set(actions) - POI_ACTIONS)
    if unknown:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has unknown actions {unknown}")
    default_actions = set(DEFAULT_POI_ACTIONS[stop_type])
    disallowed = sorted(set(actions) - default_actions)
    if disallowed:
        source_backed = set(disallowed) <= SOURCE_BACKED_POI_ACTIONS
        if not source_backed:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} actions {disallowed} "
                f"do not match type {stop_type!r}"
            )
    services = tuple(
        str(service).strip() for service in raw.get("services", ()) if str(service).strip()
    )
    parking = str(raw.get("parking", "")).strip() or _default_parking_certainty(
        stop_type, services, actions
    )
    if parking not in PARKING_CERTAINTY_LABELS:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown parking certainty {parking!r}"
        )
    directions = tuple(
        str(direction).strip()
        for direction in raw.get("directions", ("both",))
        if str(direction).strip()
    )
    if not directions:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has no directions")
    unknown_directions = sorted(set(directions) - STOP_DIRECTIONS)
    if unknown_directions:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown directions {unknown_directions}"
        )
    if "both" in directions and len(directions) > 1:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} mixes 'both' with "
            "direction-specific applicability"
        )
    curation = str(raw.get("curation", "")).strip() or _infer_stop_curation(name, source)
    if curation not in STOP_CURATION_LEVELS:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown curation {curation!r}"
        )
    if curation == "curated" and _infer_stop_curation(name, source) == "placeholder":
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} looks synthetic but is marked curated"
        )
    for action in SOURCE_BACKED_POI_ACTIONS & set(actions):
        if action not in services:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} action {action!r} "
                "requires matching source-backed service metadata"
            )
        if not source:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} action {action!r} requires a source note"
            )
    return Stop(name, at_mi, stop_type, source, actions, services, parking, directions, curation)


def _parse_route_point(raw, leg_miles: float, from_city: str, to_city: str) -> RoutePoint:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} route point must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "route point", allow_endpoints=True)
    lat = float(raw["lat"])
    lon = float(raw["lon"])
    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        raise ValueError(f"{from_city} to {to_city} route point has invalid coordinates")
    return RoutePoint(at_mi, lat, lon)


def _parse_elevation_sample(raw, leg_miles: float, from_city: str, to_city: str) -> ElevationSample:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} elevation sample must be an object")
    at_mi = _parse_at_mi(
        raw, leg_miles, from_city, to_city, "elevation sample", allow_endpoints=True
    )
    elevation_ft = float(raw["elevation_ft"])
    if not -300.0 <= elevation_ft <= 20_500.0:
        raise ValueError(f"{from_city} to {to_city} elevation sample has invalid elevation")
    source = str(raw.get("source", "")).strip()
    return ElevationSample(at_mi, elevation_ft, source)


def _parse_grade_segment(raw, leg_miles: float, from_city: str, to_city: str) -> GradeSegment:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} grade segment must be an object")
    if "start_mi" not in raw:
        raise ValueError(f"{from_city} to {to_city} grade segment is missing explicit start_mi")
    start_mi = float(raw["start_mi"])
    if not 0.0 <= start_mi <= leg_miles:
        raise ValueError(
            f"{from_city} to {to_city} grade segment start has start_mi {start_mi}, "
            f"outside leg mileage 0-{leg_miles}"
        )
    end_mi = float(raw["end_mi"])
    if not 0.0 <= end_mi <= leg_miles or end_mi <= start_mi:
        raise ValueError(
            f"{from_city} to {to_city} grade segment has invalid range {start_mi}-{end_mi}"
        )
    avg_grade_pct = float(raw["avg_grade_pct"])
    if not -15.0 <= avg_grade_pct <= 15.0:
        raise ValueError(
            f"{from_city} to {to_city} grade segment has unrealistic grade {avg_grade_pct}"
        )
    terrain = str(raw.get("terrain", "")).strip() or "flat"
    if terrain not in {"flat", "hills", "mountain"}:
        raise ValueError(f"{from_city} to {to_city} grade segment has unknown terrain {terrain!r}")
    source = str(raw.get("source", "")).strip()
    return GradeSegment(start_mi, end_mi, avg_grade_pct, terrain, source)


def _parse_speed_limit(raw, leg_miles: float, from_city: str, to_city: str) -> SpeedLimitSample:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} speed limit must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "speed limit", allow_endpoints=True)
    mph = float(raw["mph"])
    if not 5.0 <= mph <= 85.0:
        raise ValueError(f"{from_city} to {to_city} speed limit has unrealistic mph {mph}")
    source = str(raw.get("source", "")).strip()
    return SpeedLimitSample(at_mi, mph, source, bool(raw.get("hgv", False)))


def _parse_speed_limits(
    raw_samples, leg_miles: float, from_city: str, to_city: str
) -> tuple[SpeedLimitSample, ...]:
    """Parse the baked maxspeed profile, ordered along the leg.

    Sorting by ``at_mi`` lets the runtime treat it as a step function without
    trusting the order the samples happen to be stored in."""
    samples = tuple(_parse_speed_limit(s, leg_miles, from_city, to_city) for s in raw_samples)
    return tuple(sorted(samples, key=lambda s: s.at_mi))


def _parse_traffic_volume(raw, leg_miles: float, from_city: str, to_city: str):
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} traffic volume must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "traffic volume", allow_endpoints=True)
    aadt = float(raw.get("aadt", 0.0))
    if aadt <= 0:
        raise ValueError(f"{from_city} to {to_city} traffic volume at {at_mi} has no AADT")
    lanes = max(1, int(raw.get("lanes", 2)))
    source = str(raw.get("source", "")).strip()
    return TrafficVolumeSample(at_mi=at_mi, aadt=aadt, lanes=lanes, source=source)


def _parse_traffic_volumes(raw_samples, leg_miles: float, from_city: str, to_city: str):
    """Parse the baked HPMS AADT profile, ordered along the leg."""
    samples = tuple(_parse_traffic_volume(s, leg_miles, from_city, to_city) for s in raw_samples)
    return tuple(sorted(samples, key=lambda s: s.at_mi))


# Mirrors the bake-side filter in tools/enrich_routes_landmarks.py, plus the
# hand-curated highway heritage markers ("the Loneliest Road in America");
# anything outside this set is a bake bug and should fail the load loudly.
LANDMARK_CATEGORIES = frozenset(
    {
        "national_park",
        "wilderness",
        "national_forest",
        "mountain_pass",
        "river",
        "museum",
        "protected_area",
        "highway_marker",
        # Real roadside signs baked by the 623-city map sweep; spoken under
        # the billboards chatter switch.
        "billboard_sign",
    }
)


def _parse_landmark(raw, leg_miles: float, from_city: str, to_city: str) -> Landmark:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} landmark must be an object")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} has a landmark without a name")
    at_mi = _parse_at_mi(
        raw, leg_miles, from_city, to_city, f"landmark {name!r}", allow_endpoints=True
    )
    category = str(raw.get("category", "")).strip()
    if category not in LANDMARK_CATEGORIES:
        raise ValueError(
            f"{from_city} to {to_city} landmark {name!r} has unknown category {category!r}"
        )
    kind = str(raw.get("kind", "")).strip()
    if kind not in ("zone", "point"):
        raise ValueError(f"{from_city} to {to_city} landmark {name!r} has unknown kind {kind!r}")
    spoken = str(raw.get("spoken", "")).strip()
    if not spoken:
        raise ValueError(f"{from_city} to {to_city} landmark {name!r} has no spoken line")
    blob = f"{name} {spoken}".lower()
    if any(marker in blob for marker in RAW_POI_TEXT_MARKERS):
        raise ValueError(f"{from_city} to {to_city} landmark {name!r} exposes raw OSM/source text")
    return Landmark(name, at_mi, category, kind, spoken)


def _parse_landmarks(raw_landmarks, leg_miles: float, from_city: str, to_city: str):
    """Parse the baked landmark list, ordered along the leg."""
    landmarks = tuple(_parse_landmark(x, leg_miles, from_city, to_city) for x in raw_landmarks)
    return tuple(sorted(landmarks, key=lambda x: x.at_mi))


def _parse_state_crossing(
    raw, leg_miles: float, from_city: str, to_city: str, default_from_state: str
) -> StateCrossing:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} state crossing must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "state crossing")
    state = str(raw.get("state", "")).strip()
    if not state:
        raise ValueError(f"{from_city} to {to_city} has a state crossing without a state")
    from_state = str(raw.get("from_state", "")).strip() or default_from_state
    place = str(raw.get("place", "")).strip() or "state line"
    source = str(raw.get("source", "")).strip()
    return StateCrossing(at_mi, from_state, state, place, source)


def _parse_checkpoint(raw, leg_miles: float, from_city: str, to_city: str) -> RouteCheckpoint:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} checkpoint must be an object")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} has a checkpoint without a name")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, f"checkpoint {name!r}")
    checkpoint_type = str(raw.get("type", "")).strip() or "place"
    state = str(raw.get("state", "")).strip()
    highway = str(raw.get("highway", "")).strip()
    source = str(raw.get("source", "")).strip()
    return RouteCheckpoint(name, at_mi, checkpoint_type, state, highway, source)


def _parse_state_mileage(raw, from_city: str, to_city: str) -> StateMileage:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} state mileage must be an object")
    state = str(raw.get("state", "")).strip()
    if not state:
        raise ValueError(f"{from_city} to {to_city} has state mileage without a state")
    miles = float(raw["miles"])
    if miles <= 0.0:
        raise ValueError(f"{from_city} to {to_city} state mileage must be positive")
    return StateMileage(state, miles)


def _parse_toll_event(
    raw, leg_miles: float, from_city: str, to_city: str, default_road: str
) -> TollEvent:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} toll event must be an object")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} toll event has no name")
    lowered_name = name.lower()
    if any(marker in lowered_name for marker in RAW_POI_TEXT_MARKERS):
        raise ValueError(
            f"{from_city} to {to_city} toll event {name!r} exposes raw OSM/source text"
        )
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, f"toll event {name!r}")
    road = str(raw.get("road", "")).strip() or default_road
    authority = str(raw.get("authority", "")).strip()
    method = str(raw.get("method", "")).strip()
    source = str(raw.get("source", "")).strip()
    if not authority:
        raise ValueError(f"{from_city} to {to_city} toll event {name!r} has no authority")
    if method not in TOLL_METHOD_LABELS:
        raise ValueError(
            f"{from_city} to {to_city} toll event {name!r} has unknown method {method!r}"
        )
    amount = float(raw["amount"])
    if amount < 0.0 or amount > 500.0:
        raise ValueError(f"{from_city} to {to_city} toll event {name!r} has invalid amount")
    if not source:
        raise ValueError(f"{from_city} to {to_city} toll event {name!r} has no source")
    return TollEvent(
        name=name,
        at_mi=at_mi,
        road=road,
        authority=authority,
        method=method,
        amount=amount,
        estimated=bool(raw.get("estimated", True)),
        source=source,
    )


def _parse_interchange(
    raw, leg_miles: float, from_city: str, to_city: str, default_highway: str
) -> Interchange:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} interchange must be an object")
    # OSM exit refs occasionally carry stray internal spaces ("103 B"); a real
    # exit number never does, so collapse them ("103 B" -> "103B").
    exit_ref = re.sub(r"\s+", "", str(raw.get("exit_ref", "")).strip())
    name = str(raw.get("name", "")).strip()
    via = str(raw.get("via", "")).strip()
    raw_dests = raw.get("destinations", ())
    if isinstance(raw_dests, str):
        raw_dests = [raw_dests]
    destinations = tuple(d for d in (str(item).strip() for item in raw_dests) if d)
    label = f"interchange {exit_ref or name or '(unnamed)'!r}"
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, label)
    # An interchange must carry *something* sayable beyond a milepost.
    if not (exit_ref or destinations or name):
        raise ValueError(
            f"{from_city} to {to_city} interchange at {at_mi} has no exit ref, "
            "destinations, or name"
        )
    blob = " ".join((name, via, *destinations)).lower()
    if any(marker in blob for marker in RAW_POI_TEXT_MARKERS):
        raise ValueError(f"{from_city} to {to_city} {label} exposes raw OSM/source text")
    highway = str(raw.get("highway", "")).strip() or default_highway
    source = str(raw.get("source", "")).strip()
    if not source:
        raise ValueError(f"{from_city} to {to_city} {label} has no source")
    ramp_control = str(raw.get("ramp_control", "")).strip().lower()
    if ramp_control not in ("", "signal", "stop", "none"):
        raise ValueError(f"{from_city} to {to_city} {label} has unknown ramp_control")
    return Interchange(
        at_mi=at_mi,
        exit_ref=exit_ref,
        name=name,
        destinations=destinations,
        via=via,
        highway=highway,
        source=source,
        ramp_control=ramp_control,
    )


def _route_token(value: str) -> str:
    """Leading route shield of a string, normalized for comparison:
    'I 70 East' -> 'I70', 'US 1 North' -> 'US1', 'Trenton' -> ''."""
    match = re.match(r"\s*((?:I|US|[A-Za-z]{2})[-\s]?\d+)", str(value).strip())
    return re.sub(r"[-\s]", "", match.group(1)).upper() if match else ""


def _destinations_without_via(via: str, destinations: tuple[str, ...]) -> tuple[str, ...]:
    """Drop destinations that merely restate the via route (via 'I 70' with a
    destination of 'I 70 East'), so the spoken phrase never says it twice. The
    via itself still carries the route, so emptying the list reads cleanly
    ('exit 101A for I-70')."""
    token = _route_token(via)
    if not token:
        return destinations
    return tuple(d for d in destinations if _route_token(d) != token)


def _join_destinations(destinations: tuple[str, ...]) -> str:
    """['Trenton', 'New York'] -> 'Trenton and New York'; Oxford-comma 3+."""
    items = [d for d in destinations if d]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _parse_at_mi(
    raw: dict,
    leg_miles: float,
    from_city: str,
    to_city: str,
    label: str,
    *,
    allow_endpoints: bool = False,
) -> float:
    if "at_mi" not in raw:
        raise ValueError(f"{from_city} to {to_city} {label} is missing explicit at_mi")
    at_mi = float(raw["at_mi"])
    in_range = 0.0 <= at_mi <= leg_miles if allow_endpoints else 0.0 < at_mi < leg_miles
    if not in_range:
        raise ValueError(
            f"{from_city} to {to_city} {label} has at_mi {at_mi}, outside leg mileage 0-{leg_miles}"
        )
    return at_mi


def _classify_stop(name: str) -> str:
    lower = name.lower()
    if "weigh" in lower:
        return "weigh_station"
    if "parking" in lower:
        return "truck_parking"
    if "rest area" in lower:
        return "public_rest_area"
    if "service plaza" in lower:
        return "service_plaza"
    if "truck" in lower:
        return "truck_stop"
    if any(word in lower for word in ("travel", "fuel", "plaza", "center")):
        return "travel_center"
    return "travel_center"


def _default_parking_certainty(
    stop_type: str,
    services: tuple[str, ...],
    actions: tuple[str, ...],
) -> str:
    if "parking" not in services and "park" not in actions:
        return "none"
    if stop_type in {"truck_stop", "travel_center", "service_plaza"}:
        return "likely"
    if stop_type in {"public_rest_area", "truck_parking"}:
        return "limited"
    return "unknown"


def _infer_stop_curation(name: str, source: str) -> str:
    text = f"{name} {source}".lower()
    synthetic_markers = (
        "corridor rest area",
        "corridor truck parking",
        "corridor fuel stop",
        "descriptive gameplay stop seeded",
        "seeded for offline route coverage",
        "no actionable overpass poi candidate",
    )
    return "placeholder" if any(marker in text for marker in synthetic_markers) else "curated"


def minimum_curated_pois(miles: float) -> int:
    if miles < POI_DENSITY_SHORT_LEG_MILES:
        return 1
    if miles <= POI_DENSITY_MEDIUM_LEG_MILES:
        return 2
    return 3


def minimum_fuel_capable_pois(miles: float) -> int:
    if miles < POI_DENSITY_SHORT_LEG_MILES:
        return 0
    return 1
