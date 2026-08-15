"""Source-backed city service and local route helpers for world data."""

from __future__ import annotations

import re
import zlib

from .world_constants import (
    CITY_SERVICE_ORDER,
    CITY_SERVICE_SOURCE_NOTES,
    FACILITY_APPROACH_MILES,
    FACILITY_APPROACH_ROADS,
    FACILITY_APPROACH_TRUSTED_MAX_MI,
)
from .world_models import (
    CityService,
    FacilityApproach,
    FacilityEndpoint,
    Leg,
    LocalApproach,
    LocalGeometry,
    Route,
)

_ROAD_REF_LIST = re.compile(r"\(([^()]*;[^()]*)\)")


# Josh's ruling (2026-07-24): local deadheads run 1 to 9 miles. The bake
# already floors facilities at 2.1; this caps the synthetic single-leg
# top end until the placement audit re-geocodes the misplaced pins.
SYNTHETIC_APPROACH_CAP_MI = 9.0


def _spoken_road_text(text: str) -> str:
    """Trim raw OSM ref lists out of player-facing street text.

    Source-backed street names sometimes carry the full multi-ref
    parenthetical straight from the map tags -- "North Michigan Street
    (SR 933;BUS US 31)". Read aloud, the semicolon list is tag soup, so
    keep the first ref only: "North Michigan Street (SR 933)"."""
    if not text or ";" not in text:
        return text
    return _ROAD_REF_LIST.sub(lambda m: f"({m.group(1).split(';')[0].strip()})", text)


def _local_cue_direction(cue: str) -> str:
    """Maneuver direction baked in a local segment cue, or ""."""
    lowered = cue.strip().lower()
    if lowered.startswith("turn left"):
        return "left"
    if lowered.startswith("turn right"):
        return "right"
    if lowered.startswith("continue"):
        return "ahead"
    return ""


def _reversed_local_legs(city: str, legs: list[Leg]) -> list[Leg]:
    """The same street chain driven outbound: leg order reversed, and each
    junction's turn direction flipped (an inbound right turn is an outbound
    left at the same corner). Near-straight boundaries stay "Continue onto";
    directionless legacy cues stay directionless."""
    arrival = list(legs)
    out: list[Leg] = []
    for i, src in enumerate(reversed(arrival)):
        if i == 0:
            cue = f"Start on {src.highway}."
        else:
            # Outbound, the junction onto this leg is the one the inbound
            # drive crossed *leaving* it: the cue baked on the leg after it.
            inbound = _local_cue_direction(arrival[len(arrival) - i].local_cue)
            if inbound == "left":
                cue = f"Turn right onto {src.highway}."
            elif inbound == "right":
                cue = f"Turn left onto {src.highway}."
            elif inbound == "ahead":
                cue = f"Continue onto {src.highway}."
            else:
                cue = f"Turn onto {src.highway}."
        out.append(
            Leg(
                city,
                city,
                src.miles,
                src.highway,
                "flat",
                (),
                local_cue=cue,
                local_speed_mph=src.local_speed_mph,
            )
        )
    return out


class WorldServiceMixin:
    def city_services(self, city: str) -> tuple[CityService, ...]:
        """Service POIs available for local city driving.

        Source-backed entries from ``city_services.json`` are preferred per
        service key. Missing keys stay available as representative fallback
        services so the existing offline menu contract remains complete.
        ``CityService.city`` carries the canonical city key so it round-trips
        through the other service lookups; spoken text uses ``name``.
        """
        city_key = self.resolve_city_key(city)
        if city_key not in self.cities:
            raise KeyError(f"Unknown city: {city}")
        source_entries = self._city_service_data.get(city_key, {})
        services: list[CityService] = []
        for key in CITY_SERVICE_ORDER:
            raw = source_entries.get(key)
            if raw is None:
                services.append(self._fallback_city_service(city_key, key))
                continue
            city_obj = self.cities[city_key]
            services.append(
                CityService(
                    key=key,
                    name=str(raw["name"]).strip(),
                    city=city_key,
                    state=city_obj.state,
                    kind=str(raw.get("kind", key)).strip() or key,
                    source_note=str(raw.get("source_note", "")).strip(),
                    lat=float(raw.get("lat", 0.0)),
                    lon=float(raw.get("lon", 0.0)),
                    approach_miles=round(float(raw["approach_miles"]), 1),
                    approach_road=str(raw["approach_road"]).strip(),
                    source_type=str(raw.get("source_type", "osm")).strip(),
                    source_ref=str(raw.get("source_ref", "")).strip(),
                    fallback=bool(raw.get("fallback", False)),
                    fallback_reason=str(raw.get("fallback_reason", "")).strip(),
                )
            )
        return tuple(services)

    def _fallback_city_service(self, city_key: str, key: str) -> CityService:
        city_obj = self.cities[city_key]
        terminal = self.home_terminal(city_key)
        names = {
            "freight_market": f"{city_obj.name} Freight Market Office",
            "garage": f"{terminal.name} Garage",
            "truck_dealer": f"{city_obj.name} Truck Dealer",
        }
        return CityService(
            key=key,
            name=names[key],
            city=city_key,
            state=city_obj.state,
            kind=key,
            source_note=CITY_SERVICE_SOURCE_NOTES[key],
            fallback_reason="No checked-in source-backed city service entry for this role.",
        )

    def city_service(self, city: str, key: str) -> CityService:
        for service in self.city_services(city):
            if service.key == key:
                return service
        raise KeyError(f"Unknown service in {city}: {key}")

    def local_approach(self, target_id: str) -> LocalApproach | None:
        return self._local_approaches.get(target_id)

    def local_geometry(self, target_id: str) -> LocalGeometry | None:
        return self._local_geometries.get(target_id)

    def facility_approach(self, city: str, location_name: str) -> LocalApproach | None:
        location = self.facility_location(city, location_name)
        return self.local_approach(f"facility:{location.id}")

    def facility_endpoint(self, city: str, location_name: str) -> FacilityEndpoint | None:
        location = self.facility_location(city, location_name)
        return self._facility_endpoints.get(location.id)

    def facility_source_approach(self, city: str, location_name: str) -> FacilityApproach | None:
        location = self.facility_location(city, location_name)
        return self._facility_approaches.get(location.id)

    def facility_approach_miles(self, city: str, location_name: str) -> float | None:
        """Local approach road a HIGHWAY run has to cover to reach this gate.

        The arrival zones size the destination approach from this rather than
        from a flat mileage: the facilities differ hugely, and a number that
        fits a dock two ramps off the interstate is a crawl for one sitting on
        the frontage road.

        ``None`` means "no usable geometry, size it synthetically", and it is
        the answer in two different cases. A facility with a genuine
        turn-level street chain has that chain driven as a route of its own
        once the highway run ends, so counting its mileage here as well would
        slow the freeway for road the truck has not reached. A facility whose
        record is a fallback, or whose endpoint estimate is longer than any
        real approach road (the misplaced pins the synthetic cap already
        guards), has nothing worth believing."""
        try:
            location = self.facility_location(city, location_name)
        except (KeyError, ValueError):
            return None
        approach = self._facility_approaches.get(location.id)
        if approach is not None and approach.turn_level and approach.segments:
            return None  # its own street chain covers this road
        if approach is not None and not approach.fallback and approach.total_miles > 0.0:
            return approach.total_miles
        endpoint = self._facility_endpoints.get(location.id)
        if endpoint is not None and endpoint.source_backed and not endpoint.fallback:
            miles = endpoint.approach_miles
            if 0.0 < miles <= FACILITY_APPROACH_TRUSTED_MAX_MI:
                return miles
        return None

    def facility_geometry(self, city: str, location_name: str) -> LocalGeometry | None:
        location = self.facility_location(city, location_name)
        return self.local_geometry(f"facility:{location.id}")

    def facility_departure_route(self, city: str, location_name: str) -> Route | None:
        """The facility's street chain driven outbound -- gate toward the
        highway on-ramp -- or ``None`` when the facility has no genuine
        multi-segment turn-level chain (those keep the scripted departure).
        Mirrors the arrival-side chain gating in the driving layer."""
        route = self.facility_approach_route(city, location_name)
        if route is None or len(route.legs) < 2:
            return None
        if not any(leg.local_speed_mph > 0 for leg in route.legs):
            return None
        city = self.resolve_city_key(city)
        legs = _reversed_local_legs(city, route.legs)
        return Route([city] * (len(legs) + 1), legs)

    def facility_approach_route(self, city: str, location_name: str) -> Route:
        """A short, drivable local route from the company terminal to a facility."""
        city = self.resolve_city_key(city)
        location = self.facility_location(city, location_name)
        source_approach = self._facility_approaches.get(location.id)
        if source_approach is not None and source_approach.turn_level and source_approach.segments:
            legs = [
                Leg(
                    city,
                    city,
                    segment.miles,
                    _spoken_road_text(segment.road),
                    "flat",
                    (),
                    local_cue=_spoken_road_text(segment.cue),
                    local_speed_mph=segment.speed_mph,
                )
                for segment in source_approach.segments
            ]
            return Route([city] * (len(legs) + 1), legs)
        endpoint = self._facility_endpoints.get(location.id)
        approach = self.local_approach(f"facility:{location.id}")
        if endpoint is not None and endpoint.source_backed and not endpoint.fallback:
            miles = endpoint.approach_miles
            road = approach.road if approach is not None else endpoint.approach_road
        elif approach is not None:
            miles = approach.approach_miles
            road = approach.road
        else:
            base_miles = FACILITY_APPROACH_MILES.get(location.type, 4.0)
            seed = zlib.crc32(f"{city}:{location.name}:{location.type}".encode())
            offset = (seed % 7) * 0.25
            miles = round(base_miles + offset, 1)
            road = FACILITY_APPROACH_ROADS.get(location.type, "facility access road")
        # Sanity clamp for the synthetic single-leg approach: 776 baked
        # records carry up to the bake tool's 35-mile cap because the
        # facility's geocoded pin landed tens of miles from its city --
        # Josh drew a 35-mile straight deadhead in Kenosha (2026-07-24).
        # Until the placement audit re-geocodes them (roadmap), no local
        # deadhead crawls half a county; real multi-leg street chains
        # above are never clamped.
        miles = min(miles, SYNTHETIC_APPROACH_CAP_MI)
        leg = Leg(city, city, miles, road, "flat", ())
        return Route([city, city], [leg])
