"""Response parsers for the state 511 traffic APIs.

Split out of ``real_traffic`` to keep both halves at a reviewable size:
this module owns the per-platform response formats and the ``TrafficEvent``
model they produce; ``real_traffic`` owns the endpoint registry, caching,
and background fetching.

Parsers:
  ``ohgo``   — Ohio OHGO native JSON format (reference implementation).
  ``iteris`` — Shared Iteris/INRIX-platform ``/Events`` endpoint format.
               No state currently rides it (their REST APIs are gone) but
               the CARS parser reuses its closure/location helpers.
  ``wzdx``   — Work Zone Data Exchange standard (GeoJSON FeatureCollection).
               Handles both the older camelCase property layout and the
               v4.x snake_case ``core_details`` layout the live state feeds
               publish today (checked 2026-08-09).
  ``cars``   — Castle Rock CARS GraphQL platform (``POST /api/graphql``
               MapFeatures query).  Used by Indiana 511IN, Minnesota 511MN,
               and Colorado COtrip.
  ``list511`` — The 511 sites' own list-page JSON rows joined with the
               map-pin locations (Florida FL511 and New York 511NY
               incidents).  Lives in ``real_traffic_list511``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrafficEvent:
    """A traffic incident or construction event."""

    id: str
    event_type: str  # "incident", "construction", "weather"
    severity: str  # "low", "medium", "high"
    description: str
    county: str
    latitude: float | None = None
    longitude: float | None = None
    start_time: str | None = None
    estimated_end: str | None = None
    lanes_affected: str | None = None
    road_name: str = ""  # highway/road name for construction events
    location_text: str = ""  # "near milepost 45" or "between exits 43 and 47"
    work_type: str = ""  # "construction", "maintenance", "utility", "bridge", "paving"
    closure: str = ""  # "alternating", "single lane", "shoulder", "full closure"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "severity": self.severity,
            "description": self.description,
            "county": self.county,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "start_time": self.start_time,
            "estimated_end": self.estimated_end,
            "lanes_affected": self.lanes_affected,
            "road_name": self.road_name,
            "location_text": self.location_text,
            "work_type": self.work_type,
            "closure": self.closure,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TrafficEvent | None:
        try:
            # Require at least basic identification
            if not data or not isinstance(data, dict):
                return None

            event_id = str(data.get("id", ""))
            if not event_id:
                return None

            return cls(
                id=event_id,
                event_type=str(data.get("event_type", "incident")),
                severity=str(data.get("severity", "low")),
                description=str(data.get("description", "")),
                county=str(data.get("county", "")),
                latitude=float(data["latitude"]) if data.get("latitude") else None,
                longitude=float(data["longitude"]) if data.get("longitude") else None,
                start_time=data.get("start_time"),
                estimated_end=data.get("estimated_end"),
                lanes_affected=data.get("lanes_affected"),
                road_name=str(data.get("road_name", "")),
                location_text=str(data.get("location_text", "")),
                work_type=str(data.get("work_type", "")),
                closure=str(data.get("closure", "")),
            )
        except (TypeError, ValueError, KeyError):
            return None


class TrafficEventParsers:
    """Mixin with the per-platform response parsers for RealTrafficProvider."""

    def _parse_construction_events(self, data: dict, state: str) -> list[TrafficEvent]:
        """Parse construction work zone events from API response.

        This is the reference parser for Ohio OHGO. Iteris-platform states
        use ``_parse_iteris_construction_events`` instead.
        """
        events: list[TrafficEvent] = []

        raw_events = data.get("construction", data.get("events", data.get("results", [])))
        if isinstance(raw_events, dict):
            raw_events = [raw_events]
        if not isinstance(raw_events, list):
            return events

        for construction in raw_events:
            if not isinstance(construction, dict):
                continue
            try:
                event_id = str(construction.get("id", "") or "")
                if not event_id:
                    continue

                lat, lon = self._extract_construction_coordinates(construction)
                location_text = self._build_construction_location_text(construction)
                closure = self._determine_closure_type(construction)
                lanes = self._describe_lanes_affected(construction)
                work_type = self._classify_work_type(construction)
                severity = self._construction_severity(closure)

                road_name = str(construction.get("road", construction.get("route", "")))
                description = str(construction.get("description", construction.get("details", "")))
                county = str(construction.get("county", ""))
                start_time = str(construction.get("start_date", construction.get("start_time", "")))
                estimated_end = str(construction.get("end_date", construction.get("end_time", "")))

                event = TrafficEvent(
                    id=event_id,
                    event_type="construction",
                    severity=severity,
                    description=description,
                    county=county,
                    latitude=lat,
                    longitude=lon,
                    start_time=start_time,
                    estimated_end=estimated_end,
                    lanes_affected=lanes,
                    road_name=road_name,
                    location_text=location_text,
                    work_type=work_type,
                    closure=closure,
                )
                events.append(event)
            except (TypeError, ValueError, KeyError) as e:
                log.debug(f"Failed to parse construction event: {e}")
                continue

        return events

    # ---- Shared Iteris-platform parser ------------------------------------

    def _parse_iteris_events(self, data: dict | list, state: str) -> list[TrafficEvent]:
        """Parse general traffic incidents from an Iteris-platform API response.

        The Iteris platform returns an array of event objects with ``id``,
        ``event_type``, ``severity``, ``headline``, ``location``,
        ``road_name``, and date fields.  No state currently serves this
        format (their ``/Events`` REST APIs are gone) but the closure and
        location helpers below are shared with the CARS parser.
        """
        events: list[TrafficEvent] = []

        raw = data if isinstance(data, list) else data.get("events", data.get("results", []))
        if isinstance(raw, dict):
            raw = [raw]
        if not isinstance(raw, list):
            return events

        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                event_id = str(item.get("id", item.get("event_id", "")))
                if not event_id:
                    continue

                # Determine event type (only incidents here)
                api_type = str(item.get("event_type", item.get("type", "incident"))).lower()
                event_type = (
                    "construction"
                    if api_type in ("construction", "roadwork", "work_zone")
                    else "incident"
                )

                # Coordinates: Iteris puts lat/lon in a sub-object or top-level fields
                lat, lon = self._parse_iteris_coordinates(item)

                # Severity
                severity = self._map_severity(str(item.get("severity", "low")))

                # Road name
                road_name = str(item.get("road_name", item.get("road", item.get("route", ""))))

                description = str(
                    item.get("headline", item.get("description", item.get("event_text", "")))
                )
                county = str(item.get("county", item.get("region", "")))
                start_time = str(item.get("start_date", item.get("start_time", "")))
                estimated_end = str(item.get("end_date", item.get("end_time", "")))
                lanes = str(item.get("lanes_affected", item.get("lanes", "")))

                event = TrafficEvent(
                    id=event_id,
                    event_type=event_type,
                    severity=severity,
                    description=description,
                    county=county,
                    latitude=lat,
                    longitude=lon,
                    start_time=start_time,
                    estimated_end=estimated_end,
                    lanes_affected=lanes,
                    road_name=road_name,
                )
                events.append(event)
            except (TypeError, ValueError, KeyError) as e:
                log.debug(f"Failed to parse Iteris event: {e}")
                continue

        return events

    def _parse_iteris_construction_events(
        self, data: dict | list, state: str
    ) -> list[TrafficEvent]:
        """Parse construction work-zone events from an Iteris-platform API.

        The Iteris-platform ``/Events`` endpoint mixes incidents and
        construction events.  This parser filters to construction-type events
        only, then applies the same enrichment helpers
        (``_determine_closure_type``, ``_classify_work_type``, …) used by the
        Ohio parser so downstream zone conversion behaves identically.
        """
        all_events = self._parse_iteris_events(data, state)

        construction_events: list[TrafficEvent] = []
        for event in all_events:
            if event.event_type != "construction":
                continue

            # Re-parse with construction-specific enrichment
            # We need the raw dict item again for richer field access.
            raw = data if isinstance(data, list) else data.get("events", data.get("results", []))
            if isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, list):
                continue

            matching = [
                r
                for r in raw
                if isinstance(r, dict) and str(r.get("id", r.get("event_id", ""))) == event.id
            ]
            if not matching:
                log.debug(f"No raw Iteris item for event {event.id}, appending unenriched")
                construction_events.append(event)
                continue

            item = matching[0]

            # Enrich with construction-specific fields using the shared helpers
            location_text = self._build_iteris_location_text(item)
            closure = self._determine_iteris_closure(item, event.description)
            lanes = self._describe_lanes_affected(item)  # Uses the same logic
            work_type = self._classify_work_type(item)
            severity = self._construction_severity(closure)

            enriched = TrafficEvent(
                id=event.id,
                event_type="construction",
                severity=severity,
                description=event.description,
                county=event.county,
                latitude=event.latitude,
                longitude=event.longitude,
                start_time=event.start_time,
                estimated_end=event.estimated_end,
                lanes_affected=lanes or event.lanes_affected or "",
                road_name=event.road_name,
                location_text=location_text,
                work_type=work_type,
                closure=closure,
            )
            construction_events.append(enriched)

        return construction_events

    def _parse_iteris_coordinates(self, item: dict) -> tuple[float | None, float | None]:
        """Extract coordinates from an Iteris-platform event.

        Iteris puts ``lat``/``lon`` directly on the object, or inside a
        ``location`` sub-object."""
        # Direct top-level fields
        lat = item.get("lat", item.get("latitude"))
        lon = item.get("lon", item.get("lng", item.get("longitude")))
        if lat is not None and lon is not None:
            try:
                return float(lat), float(lon)
            except (TypeError, ValueError):
                pass

        # Sub-object (location: {lat: ..., lon: ...})
        loc = item.get("location", {})
        if isinstance(loc, dict):
            lat = loc.get("lat", loc.get("latitude"))
            lon = loc.get("lon", loc.get("lng", loc.get("longitude")))
            if lat is not None and lon is not None:
                try:
                    return float(lat), float(lon)
                except (TypeError, ValueError):
                    pass

        return None, None

    def _build_iteris_location_text(self, item: dict) -> str:
        """Build a location description from Iteris fields."""
        # Direct location text
        text = str(item.get("location_text", item.get("location", "")))
        if text:
            return text

        # Cross streets / intersection
        cross = item.get("cross_street", "")
        if cross:
            return f"At {cross}"

        # Milepost / mile range
        start = item.get("start_milepost", item.get("milepost", ""))
        end = item.get("end_milepost", "")
        if start and end:
            return f"Between milepost {start} and {end}"
        if start:
            return f"Near milepost {start}"

        return ""

    def _determine_iteris_closure(self, item: dict, description: str) -> str:
        """Determine closure type from Iteris fields."""
        # Direct field
        closure = str(item.get("closure", item.get("closure_type", ""))).lower()
        if closure:
            return closure

        # Check the description for closure keywords
        desc = description.lower()
        if any(w in desc for w in ("full closure", "road closed", "detour")):
            return "full closure"
        if any(w in desc for w in ("alternating", "flag", "one-way")):
            return "alternating"
        if "shoulder" in desc:
            return "shoulder"
        if any(w in desc for w in ("lane closure", "right lane", "left lane")):
            return "single lane"

        return "single lane"

    # ---- Castle Rock CARS GraphQL parser ---------------------------------

    def _parse_cars_events(self, data: dict, state: str, construction: bool) -> list[TrafficEvent]:
        """Parse traffic events from a CARS MapFeatures GraphQL response.

        The Castle Rock CARS platform (Indiana 511IN, Minnesota 511MN,
        Colorado COtrip) answers ``POST /api/graphql`` with one map feature
        per event inside ``data.mapFeaturesQuery.mapFeatures``: a ``uri``
        ("event/CARSy-30"), a ``title`` that packs road, mile range, and
        text ("US 20 (Mile Point 42.5 - 42.61): Lane closed."), a bbox, a
        Point feature with the marker position, and a ``priority`` where 1
        is most urgent.  The layer slug requested in the query decides
        whether the whole batch is construction or incidents.
        """
        events: list[TrafficEvent] = []

        query = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(query, dict):
            return events
        features_query = query.get("mapFeaturesQuery", {})
        if not isinstance(features_query, dict):
            return events
        raw = features_query.get("mapFeatures") or []
        if not isinstance(raw, list):
            return events

        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                # Zoom 15 keeps the server from clustering, but skip any
                # non-event feature type (Cluster, Sign, ...) defensively.
                if item.get("__typename") not in (None, "Event"):
                    continue

                uri = str(item.get("uri", ""))
                event_id = uri.rsplit("/", 1)[-1]
                if not event_id:
                    continue

                title = str(item.get("title", "")).strip()
                # Scheduled-but-inactive events ride the same layer with a
                # "STARTS FRIDAY." style prefix; they are not on the road yet.
                if title.upper().startswith("STARTS "):
                    continue

                road_name, location_text, remainder = self._split_cars_title(title)
                description = title or str(item.get("tooltip", ""))
                lat, lon = self._extract_cars_coordinates(item)

                if construction:
                    closure = self._determine_iteris_closure({}, remainder or title)
                    severity = self._construction_severity(closure)
                    lanes = self._describe_lanes_affected({"closure": closure})
                    work_type = self._classify_work_type({"description": remainder or title})
                else:
                    closure = ""
                    severity = self._cars_priority_severity(item.get("priority"))
                    lanes = ""
                    work_type = ""

                event = TrafficEvent(
                    id=event_id,
                    event_type="construction" if construction else "incident",
                    severity=severity,
                    description=description,
                    county="",
                    latitude=lat,
                    longitude=lon,
                    lanes_affected=lanes,
                    road_name=road_name,
                    location_text=location_text,
                    work_type=work_type,
                    closure=closure,
                )
                events.append(event)
            except (TypeError, ValueError, KeyError) as e:
                log.debug(f"Failed to parse CARS event: {e}")
                continue

        return events

    def _split_cars_title(self, title: str) -> tuple[str, str, str]:
        """Split a CARS event title into (road_name, location_text, text).

        Titles look like "US 20 (Mile Point 42.5 - 42.61): Lane closed." or
        "I-35W southbound: Crash."; the road part may carry a parenthesised
        mile range and a direction suffix that would break road matching.
        """
        text = title.strip()
        location_text = ""
        match = re.search(r"\(([^)]*)\)\s*", text)
        if match:
            location_text = match.group(1).strip()
            text = (text[: match.start()] + text[match.end() :]).strip()

        road_part, sep, remainder = text.partition(": ")
        if not sep:
            return "", location_text, text

        # Drop any leading sentence ("ends Friday." style notes) and the
        # direction suffix so _road_name_matches sees a bare designation.
        road = road_part.split(". ")[-1].strip()
        lowered = road.lower()
        for suffix in (
            " northbound",
            " southbound",
            " eastbound",
            " westbound",
            " in both directions",
        ):
            if lowered.endswith(suffix):
                road = road[: len(road) - len(suffix)].strip()
                break
        return road, location_text, remainder.strip()

    def _extract_cars_coordinates(self, item: dict) -> tuple[float | None, float | None]:
        """Extract lat/lon from a CARS map feature.

        Prefers the marker Point geometry; falls back to the bbox midpoint
        (bbox is [west, south, east, north])."""
        features = item.get("features")
        if isinstance(features, list):
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                geometry = feature.get("geometry", {})
                if not isinstance(geometry, dict) or geometry.get("type") != "Point":
                    continue
                coords = geometry.get("coordinates")
                if isinstance(coords, list) and len(coords) >= 2:
                    try:
                        return float(coords[1]), float(coords[0])  # [lon, lat]
                    except (TypeError, ValueError):
                        pass

        bbox = item.get("bbox")
        if isinstance(bbox, list) and len(bbox) >= 4:
            try:
                return (
                    (float(bbox[1]) + float(bbox[3])) / 2,
                    (float(bbox[0]) + float(bbox[2])) / 2,
                )
            except (TypeError, ValueError):
                pass

        return None, None

    def _cars_priority_severity(self, priority: object) -> str:
        """Map a CARS event priority (1 = most urgent) to severity levels."""
        try:
            value = int(priority)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return "low"
        if value <= 2:
            return "high"
        if value <= 5:
            return "medium"
        return "low"

    # ---- WZDx standard parser (GeoJSON FeatureCollection) ----------------

    def _parse_wzdx_events(self, data: dict | list, state: str) -> list[TrafficEvent]:
        """Parse incidents from a WZDx GeoJSON FeatureCollection.

        The WZDx standard (Work Zone Data Exchange) is a USDOT-specified
        format.  Responses are GeoJSON FeatureCollections; older feeds carry
        camelCase properties (optionally ``wzdx:``-namespaced), while the
        v4.x feeds every live state publishes today move the shared fields
        into a snake_case ``core_details`` object.
        """
        events: list[TrafficEvent] = []

        features = data
        if isinstance(data, dict):
            # GeoJSON FeatureCollection
            features = data.get("features", data.get("events", data.get("results", [])))
            if isinstance(features, dict):
                features = [features]
        if not isinstance(features, list):
            return events

        for feature in features:
            if not isinstance(feature, dict):
                continue
            try:
                event_id = str(feature.get("id", feature.get("feature_id", "")))
                if not event_id:
                    continue

                # Extract coordinates from GeoJSON Point geometry
                lat, lon = self._extract_wzdx_coordinates(feature)

                # Properties may be namespaced (wzdx:roadName) or flat (roadName)
                props = feature.get("properties", feature)
                if not isinstance(props, dict):
                    props = feature

                # WZDx v4.x: shared fields moved into core_details
                core = props.get("core_details")
                if isinstance(core, dict):
                    event = self._build_wzdx_v4_event(event_id, core, props, lat, lon)
                    if event is not None:
                        events.append(event)
                    continue

                road_name = self._wzdx_prop(props, "roadName", "")
                event_type = self._wzdx_prop(props, "workZoneType", "construction").lower()
                # Normalize to our standard types
                if event_type in ("construction", "maintenance", "bridge", "paving"):
                    mapped_type = "construction"
                else:
                    mapped_type = "incident"

                description = self._wzdx_prop(props, "description", "") or self._wzdx_prop(
                    props, "workZoneName", ""
                )
                county = self._wzdx_prop(props, "county", "")
                start_time = self._wzdx_prop(props, "startDate", "")
                estimated_end = self._wzdx_prop(props, "endDate", "")

                # Vehicle impact → closure type
                vehicle_impact = self._wzdx_prop(props, "vehicleImpact", "").lower()
                closure = self._wzdx_impact_to_closure(vehicle_impact)
                severity = self._construction_severity(closure)

                # Lane info
                lanes = self._wzdx_prop(props, "lanesAffected", "")
                if not lanes:
                    lanes = self._describe_lanes_affected({"closure": closure})

                # Location text
                location_text = self._build_wzdx_location_text(props)

                event = TrafficEvent(
                    id=event_id,
                    event_type=mapped_type,
                    severity=severity,
                    description=description,
                    county=county,
                    latitude=lat,
                    longitude=lon,
                    start_time=start_time,
                    estimated_end=estimated_end,
                    lanes_affected=lanes,
                    road_name=road_name,
                    location_text=location_text,
                    closure=closure,
                    work_type="construction",
                )
                events.append(event)
            except (TypeError, ValueError, KeyError) as e:
                log.debug(f"Failed to parse WZDx feature: {e}")
                continue

        return events

    def _build_wzdx_v4_event(
        self,
        event_id: str,
        core: dict,
        props: dict,
        lat: float | None,
        lon: float | None,
    ) -> TrafficEvent | None:
        """Build a TrafficEvent from a WZDx v4.x feature.

        v4.x renamed everything to snake_case and nested the shared fields
        under ``core_details`` (checked 2026-08-09: 511wi.gov, az511.com,
        511ny.org, and fl511.com all publish v4.2 this way).
        """
        road_names = core.get("road_names")
        road_name = str(road_names[0]) if isinstance(road_names, list) and road_names else ""
        event_type = str(core.get("event_type", "work-zone")).lower()
        mapped_type = "construction" if event_type in ("work-zone", "detour") else "incident"

        description = str(core.get("description", "") or core.get("name", ""))
        start_time = str(props.get("start_date", "") or "")
        estimated_end = str(props.get("end_date", "") or "")

        vehicle_impact = str(props.get("vehicle_impact", "")).lower()
        closure = self._wzdx_impact_to_closure(vehicle_impact)
        severity = self._construction_severity(closure)

        lanes = self._describe_wzdx_v4_lanes(props.get("lanes"))
        if not lanes:
            lanes = self._describe_lanes_affected({"closure": closure})

        begin = str(props.get("beginning_cross_street", "") or "")
        end = str(props.get("ending_cross_street", "") or "")
        if begin and end:
            location_text = f"Between {begin} and {end}"
        elif begin:
            location_text = f"Near {begin}"
        else:
            begin_mp = props.get("beginning_milepost", "")
            end_mp = props.get("ending_milepost", "")
            if begin_mp and end_mp:
                location_text = f"Between milepost {begin_mp} and {end_mp}"
            elif begin_mp:
                location_text = f"Near milepost {begin_mp}"
            else:
                location_text = ""

        return TrafficEvent(
            id=event_id,
            event_type=mapped_type,
            severity=severity,
            description=description,
            county="",
            latitude=lat,
            longitude=lon,
            start_time=start_time,
            estimated_end=estimated_end,
            lanes_affected=lanes,
            road_name=road_name,
            location_text=location_text,
            closure=closure,
            work_type="construction" if mapped_type == "construction" else "",
        )

    def _describe_wzdx_v4_lanes(self, lanes: object) -> str:
        """Describe closed lanes from a WZDx v4 ``lanes`` array."""
        if not isinstance(lanes, list) or not lanes:
            return ""
        closed = [
            lane
            for lane in lanes
            if isinstance(lane, dict) and str(lane.get("status", "")).lower() == "closed"
        ]
        closed_general = [
            lane for lane in closed if str(lane.get("type", "")).lower() != "shoulder"
        ]
        if closed_general:
            total_general = sum(
                1
                for lane in lanes
                if isinstance(lane, dict) and str(lane.get("type", "")).lower() != "shoulder"
            )
            return f"{len(closed_general)} of {total_general} lanes closed"
        if closed:
            return "shoulder closed"
        return ""

    def _parse_wzdx_construction_events(self, data: dict | list, state: str) -> list[TrafficEvent]:
        """Parse construction work-zone events from a WZDx feed.

        Most WZDx feeds are construction-specific (the standard is designed for
        work zones), but we still filter to ``event_type == 'construction'``
        for safety.
        """
        all_events = self._parse_wzdx_events(data, state)
        return [e for e in all_events if e.event_type == "construction"]

    def _extract_wzdx_coordinates(self, feature: dict) -> tuple[float | None, float | None]:
        """Extract lat/lon from a WZDx GeoJSON feature."""
        # Point geometry: {"type": "Point", "coordinates": [lon, lat]}
        # LineString/MultiPoint nest the pairs one level deeper (511ny.org
        # publishes MultiPoint, checked 2026-08-09); take the midpoint pair.
        geometry = feature.get("geometry", {})
        if isinstance(geometry, dict):
            coords = geometry.get("coordinates")
            if isinstance(coords, list) and coords:
                pair = coords if not isinstance(coords[0], list) else coords[len(coords) // 2]
                if isinstance(pair, list) and len(pair) >= 2:
                    try:
                        return float(pair[1]), float(pair[0])  # [lon, lat]
                    except (TypeError, ValueError):
                        pass

        # Fall back to properties lat/lon (uncommon but possible)
        props = feature.get("properties", {})
        if isinstance(props, dict):
            lat = props.get("lat", props.get("latitude"))
            lon = props.get("lon", props.get("lng", props.get("longitude")))
            if lat is not None and lon is not None:
                try:
                    return float(lat), float(lon)
                except (TypeError, ValueError):
                    pass

        return None, None

    def _wzdx_prop(self, props: dict, key: str, default: str) -> str:
        """Read a WZDx property, trying both namespaced and flat keys."""
        # Try with namespace first
        value = props.get(f"wzdx:{key}", props.get(key, default))
        if value is None:
            return default
        return str(value)

    def _wzdx_impact_to_closure(self, impact: str) -> str:
        """Map WZDx vehicleImpact enum to closure type string."""
        mapping = {
            "all-lanes-closed": "full closure",
            "some-lanes-closed": "single lane",
            "shoulder-closed": "shoulder",
            "alternating-one-way": "alternating",
            "flow-of-traffic": "single lane",
            "no-impact": "single lane",
            "": "single lane",
        }
        return mapping.get(impact, "single lane")

    def _build_wzdx_location_text(self, props: dict) -> str:
        """Build a location description from WZDx properties."""
        loc = self._wzdx_prop(props, "locationDescription", "")
        if loc:
            return loc

        begin = self._wzdx_prop(props, "beginningMilepost", "")
        end = self._wzdx_prop(props, "endingMilepost", "")
        if begin and end:
            return f"Between milepost {begin} and {end}"
        if begin:
            return f"Near milepost {begin}"

        return ""

    # ---- Shared construction-field helpers -------------------------------

    def _extract_construction_coordinates(
        self, construction: dict
    ) -> tuple[float | None, float | None]:
        """Extract lat/lon from a construction event, handling various API formats."""
        # Direct lat/lon fields (OHGO format)
        lat = construction.get("lat", construction.get("latitude"))
        lon = construction.get("lon", construction.get("lng", construction.get("longitude")))
        if lat is not None and lon is not None:
            try:
                return float(lat), float(lon)
            except (TypeError, ValueError):
                pass

        # Geometry object with coordinates array (GeoJSON format used by some 511 APIs)
        geometry = construction.get("geometry", {})
        if isinstance(geometry, dict):
            coords = geometry.get("coordinates")
            if isinstance(coords, list) and len(coords) >= 2:
                try:
                    return float(coords[1]), float(coords[0])  # [lon, lat] GeoJSON convention
                except (TypeError, ValueError):
                    pass

        # Start/end point objects
        start_point = construction.get("start_point", {})
        end_point = construction.get("end_point", {})
        for point in (start_point, end_point):
            slat = point.get("lat", point.get("latitude"))
            slon = point.get("lon", point.get("lng", point.get("longitude")))
            if slat is not None and slon is not None:
                try:
                    return float(slat), float(slon)
                except (TypeError, ValueError):
                    pass

        return None, None

    def _build_construction_location_text(self, construction: dict) -> str:
        """Build a human-readable location reference from construction data."""
        # Direct location text field
        text = str(construction.get("location", construction.get("location_text", "")))
        if text:
            return text

        # Milepost range
        start_mile = construction.get("start_milepost", construction.get("beg_mm", ""))
        end_mile = construction.get("end_milepost", construction.get("end_mm", ""))
        if start_mile and end_mile:
            return f"Between milepost {start_mile} and {end_mile}"
        if start_mile:
            return f"Near milepost {start_mile}"

        # Street/intersection reference
        cross = construction.get("cross_street", construction.get("intersection", ""))
        if cross:
            return f"At {cross}"

        return ""

    def _determine_closure_type(self, construction: dict) -> str:
        """Determine the type of lane or road closure."""
        # Direct closure field
        closure = str(construction.get("closure", construction.get("closure_type", ""))).lower()
        if closure:
            return closure

        # Look for closure keywords in description
        desc = str(construction.get("description", "")).lower()
        if "full closure" in desc or "road closed" in desc or "detour" in desc:
            return "full closure"
        if "alternating" in desc or "flag" in desc or "one-way" in desc:
            return "alternating"
        if "shoulder" in desc:
            return "shoulder"
        if "lane closure" in desc:
            return "single lane"

        # Default: implied lane restriction for construction
        return "single lane"

    def _describe_lanes_affected(self, construction: dict) -> str:
        """Build a description of which lanes are affected."""
        # Direct lanes affected field
        lanes = construction.get("lanes_affected", construction.get("lanes", ""))
        if lanes:
            return str(lanes)

        # Infer from closure type
        closure = self._determine_closure_type(construction)
        if closure == "full closure":
            return "all lanes closed"
        if closure == "alternating":
            return "alternating single lane"
        if closure == "shoulder":
            return "right shoulder closed"
        return "left lane closed"

    def _classify_work_type(self, construction: dict) -> str:
        """Classify the type of work being performed."""
        work_type = str(construction.get("work_type", construction.get("type", ""))).lower()
        if work_type:
            return work_type

        # Infer from description keywords
        desc = str(construction.get("description", "")).lower()
        if any(w in desc for w in ("bridge", "overpass", "structure")):
            return "bridge"
        if any(w in desc for w in ("pave", "paving", "resurface", "mill")):
            return "paving"
        if any(w in desc for w in ("utility", "pipe", "gas")):
            return "utility"
        if any(w in desc for w in ("inspect", "repair", "maintain")):
            return "maintenance"

        return "construction"

    def _construction_severity(self, closure: str) -> str:
        """Map construction closure type to severity."""
        if closure in ("full closure",):
            return "high"
        if closure in ("alternating", "single lane"):
            return "medium"
        return "low"

    # ---- Ohio OHGO incident parser ---------------------------------------

    def _parse_events(self, data: dict, state: str) -> list[TrafficEvent]:
        """Parse traffic events from API response.

        This is a reference implementation for Ohio OHGO. Other states will
        need their own parsers as API formats vary.
        """
        events = []

        # Ohio OHGO format parsing
        if "incidents" in data:
            for incident in data["incidents"]:
                try:
                    event = TrafficEvent(
                        id=str(incident.get("id", "")),
                        event_type="incident",
                        severity=self._map_severity(incident.get("severity", "low")),
                        description=str(incident.get("description", "")),
                        county=str(incident.get("county", "")),
                        latitude=float(incident["lat"]) if incident.get("lat") else None,
                        longitude=float(incident["lon"]) if incident.get("lon") else None,
                        start_time=incident.get("start_time"),
                        estimated_end=incident.get("estimated_end"),
                        lanes_affected=incident.get("lanes_affected"),
                    )
                    events.append(event)
                except (TypeError, ValueError, KeyError) as e:
                    log.debug(f"Failed to parse incident: {e}")
                    continue

        return events

    def _map_severity(self, api_severity: str) -> str:
        """Map API severity to our standard severity levels."""
        severity_map = {
            "low": "low",
            "minor": "low",
            "medium": "medium",
            "moderate": "medium",
            "intermediate": "medium",  # FL511's middle tier
            "high": "high",
            "major": "high",
            "severe": "high",
            "critical": "high",
        }
        return severity_map.get(api_severity.lower(), "low")


__all__ = [
    "TrafficEvent",
    "TrafficEventParsers",
]
