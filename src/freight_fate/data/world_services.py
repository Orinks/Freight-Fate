"""Source-backed city service and local route helpers for world data."""

from __future__ import annotations

import zlib

from .world_constants import (
    CITY_SERVICE_ORDER,
    CITY_SERVICE_SOURCE_NOTES,
    FACILITY_APPROACH_MILES,
    FACILITY_APPROACH_ROADS,
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

CITY_SERVICE_APPROACH_MILES = {
    "freight_market": 3.0,
    "garage": 1.5,
    "truck_dealer": 2.5,
}

CITY_SERVICE_APPROACH_ROADS = {
    "freight_market": "local freight office access road",
    "garage": "terminal service lane",
    "truck_dealer": "dealer access road",
}


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

    def city_service_approach(self, city: str, key: str) -> LocalApproach | None:
        return self.local_approach(f"city_service:{self.resolve_city_key(city)}:{key}")

    def city_service_geometry(self, city: str, key: str) -> LocalGeometry | None:
        return self.local_geometry(f"city_service:{self.resolve_city_key(city)}:{key}")

    def facility_approach(self, city: str, location_name: str) -> LocalApproach | None:
        location = self.facility_location(city, location_name)
        return self.local_approach(f"facility:{location.id}")

    def facility_endpoint(self, city: str, location_name: str) -> FacilityEndpoint | None:
        location = self.facility_location(city, location_name)
        return self._facility_endpoints.get(location.id)

    def facility_source_approach(self, city: str, location_name: str) -> FacilityApproach | None:
        location = self.facility_location(city, location_name)
        return self._facility_approaches.get(location.id)

    def facility_geometry(self, city: str, location_name: str) -> LocalGeometry | None:
        location = self.facility_location(city, location_name)
        return self.local_geometry(f"facility:{location.id}")

    def city_service_route(self, city: str, key: str) -> Route:
        """A short, drivable local route from the terminal to a city service."""
        city = self.resolve_city_key(city)
        service = self.city_service(city, key)
        geometry = self.city_service_geometry(city, key)
        if geometry is not None and geometry.turn_level and geometry.segments:
            legs = [
                Leg(
                    city,
                    city,
                    segment.miles,
                    segment.road,
                    "flat",
                    (),
                    local_cue=segment.cue,
                    local_speed_mph=segment.speed_mph,
                )
                for segment in geometry.segments
            ]
            return Route([city] * (len(legs) + 1), legs)
        approach = self.city_service_approach(city, key)
        if approach is not None:
            miles = approach.approach_miles
            road = approach.road
        elif service.approach_miles > 0:
            miles = service.approach_miles
            road = service.approach_road or CITY_SERVICE_APPROACH_ROADS.get(
                service.kind, "city service road"
            )
        else:
            base_miles = CITY_SERVICE_APPROACH_MILES.get(service.kind, 3.0)
            seed = zlib.crc32(f"{city}:service:{service.key}".encode())
            offset = (seed % 5) * 0.2
            miles = round(base_miles + offset, 1)
            road = CITY_SERVICE_APPROACH_ROADS.get(service.kind, "city service road")
        leg = Leg(city, city, miles, road, "flat", ())
        return Route([city, city], [leg])

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
                    segment.road,
                    "flat",
                    (),
                    local_cue=segment.cue,
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
        leg = Leg(city, city, miles, road, "flat", ())
        return Route([city, city], [leg])
