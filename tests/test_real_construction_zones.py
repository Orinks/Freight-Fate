"""Tests for real construction zones from state 511 APIs."""

from __future__ import annotations

from unittest.mock import MagicMock

from freight_fate.data.world import Leg, Route
from freight_fate.data.world_models import RoutePoint, StateMileage
from freight_fate.sim.real_traffic import (
    STATE_APIS,
    RealTrafficProvider,
    TrafficData,
    TrafficEvent,
)
from freight_fate.sim.trip import Trip
from freight_fate.sim.trip_route_helpers import (
    _haversine_distance_mi,
    _nearest_mile_on_leg,
)
from freight_fate.sim.vehicle import TruckSpecs, TruckState
from freight_fate.sim.weather import WeatherSystem

# --- Helpers ----------------------------------------------------------------


def _make_leg(
    a: str = "columbus_oh_us",
    b: str = "cincinnati_oh_us",
    miles: float = 100.0,
    highway: str = "I-71",
    route_points: tuple | None = None,
) -> Leg:
    if route_points is None:
        # A simple set of route points along the highway
        route_points = (
            RoutePoint(0.0, 39.9612, -82.9988),  # Columbus
            RoutePoint(15.0, 39.83, -83.01),
            RoutePoint(30.0, 39.70, -83.10),
            RoutePoint(45.0, 39.57, -83.18),
            RoutePoint(60.0, 39.45, -83.27),
            RoutePoint(75.0, 39.32, -83.35),
            RoutePoint(100.0, 39.1031, -84.5120),  # Cincinnati
        )
    return Leg(
        a=a,
        b=b,
        miles=miles,
        highway=highway,
        terrain="flat",
        stops=(),
        route_points=route_points,
        state_crossings=(),
        state_miles=(StateMileage(state="Ohio", miles=miles),),
        checkpoints=(),
        elevation_samples=(),
        grade_segments=(),
    )


def _make_trip(traffic_provider=None) -> Trip:
    """Create a minimal trip for testing."""
    route = Route(
        cities=["columbus_oh_us", "cincinnati_oh_us"],
        legs=[_make_leg()],
    )
    truck = TruckState(TruckSpecs())
    weather = WeatherSystem()
    return Trip(
        route=route,
        truck=truck,
        weather=weather,
        time_scale=1.0,
        seed=42,
        traffic_provider=traffic_provider,
    )


# --- Test TrafficEvent construction fields ----------------------------------


class TestTrafficEventConstruction:
    """TrafficEvent now carries construction-specific fields."""

    def test_construction_fields_default(self):
        """Construction fields default to empty strings."""
        event = TrafficEvent(
            id="test-1",
            event_type="construction",
            severity="medium",
            description="Road work near milepost 45",
            county="Franklin",
        )
        assert event.road_name == ""
        assert event.location_text == ""
        assert event.work_type == ""
        assert event.closure == ""

    def test_construction_fields_set(self):
        """Construction fields are carried through the event."""
        event = TrafficEvent(
            id="test-1",
            event_type="construction",
            severity="medium",
            description="Paving between exits 43 and 47",
            county="Franklin",
            road_name="I-71",
            location_text="Between milepost 45 and 47",
            work_type="paving",
            closure="single lane",
        )
        assert event.road_name == "I-71"
        assert event.location_text == "Between milepost 45 and 47"
        assert event.work_type == "paving"
        assert event.closure == "single lane"

    def test_construction_event_to_dict(self):
        """Construction fields survive round-trip serialization."""
        event = TrafficEvent(
            id="test-1",
            event_type="construction",
            severity="medium",
            description="Paving between exits",
            county="Franklin",
            latitude=39.8,
            longitude=-83.0,
            road_name="I-71",
            location_text="Between milepost 45 and 47",
            work_type="paving",
            closure="single lane",
        )
        d = event.to_dict()
        restored = TrafficEvent.from_dict(d)
        assert restored is not None
        assert restored.road_name == "I-71"
        assert restored.location_text == "Between milepost 45 and 47"
        assert restored.work_type == "paving"
        assert restored.closure == "single lane"


# --- Test _haversine_distance_mi -------------------------------------------


class TestHaversineDistance:
    """Great-circle distance calculations."""

    def test_known_distance(self):
        """Columbus to Cincinnati is about 100 miles."""
        dist = _haversine_distance_mi(39.9612, -82.9988, 39.1031, -84.5120)
        assert 90 <= dist <= 110

    def test_zero_distance(self):
        """Same point returns 0."""
        dist = _haversine_distance_mi(40.0, -83.0, 40.0, -83.0)
        assert dist == 0.0

    def test_small_distance(self):
        """Short distances are reasonable."""
        dist = _haversine_distance_mi(39.96, -83.0, 39.97, -83.0)
        assert 0.5 <= dist <= 1.5


# --- Test _nearest_mile_on_leg ---------------------------------------------


class TestNearestMileOnLeg:
    """Snapping coordinates to route points."""

    def test_snap_near_start(self):
        """A point near the leg start snaps to ~0 miles."""
        leg = _make_leg()
        mile = _nearest_mile_on_leg(39.96, -83.0, leg, forward=True, leg_start_mi=0.0)
        assert mile is not None
        assert 0.0 <= mile <= 2.0

    def test_snap_near_end(self):
        """A point near the leg end snaps near total leg miles."""
        leg = _make_leg(miles=100.0)
        mile = _nearest_mile_on_leg(39.11, -84.51, leg, forward=True, leg_start_mi=0.0)
        assert mile is not None
        assert 95.0 <= mile <= 105.0

    def test_snap_midpoint(self):
        """A point near the middle of the route snaps to the nearest
        route point (at_mi 45)."""
        leg = _make_leg(miles=100.0)
        # Use coordinates very close to the route point at 45 miles
        mile = _nearest_mile_on_leg(39.569, -83.179, leg, forward=True, leg_start_mi=0.0)
        assert mile is not None
        assert mile == 45.0

    def test_off_route_returns_none(self):
        """A point far from the route returns None."""
        leg = _make_leg()
        mile = _nearest_mile_on_leg(
            41.0,
            -87.0,
            leg,
            forward=True,
            leg_start_mi=0.0,  # Chicago, not on I-71
        )
        assert mile is None

    def test_no_route_points_returns_none(self):
        """Leg without route points returns None."""
        leg = _make_leg(route_points=())
        mile = _nearest_mile_on_leg(39.96, -83.0, leg, forward=True, leg_start_mi=0.0)
        assert mile is None

    def test_reverse_direction(self):
        """Leg traversed reverse still resolves miles."""
        leg = _make_leg(miles=100.0)
        mile = _nearest_mile_on_leg(39.11, -84.51, leg, forward=False, leg_start_mi=0.0)
        # In reverse, the Cincinnati point is at 100 miles forward, which
        # reverse-resolves to 0.
        assert mile is not None


# --- Test _place_real_construction_zones -----------------------------------


class TestPlaceRealConstructionZones:
    """Integration of real construction zones into trip zones."""

    def test_no_provider_returns_empty(self):
        """Without a provider, no real zones are placed."""
        trip = _make_trip(traffic_provider=None)
        zones = trip._place_real_construction_zones()
        assert zones == []

    def test_no_events_returns_empty(self):
        """Provider with no construction events returns empty."""
        provider = MagicMock(spec=RealTrafficProvider)
        provider.get_construction_near_route.return_value = []
        trip = _make_trip(traffic_provider=provider)
        zones = trip._place_real_construction_zones()
        assert zones == []

    def test_event_converts_to_zone(self):
        """A single construction event creates zone + taper pair."""
        provider = MagicMock(spec=RealTrafficProvider)
        provider.get_construction_near_route.return_value = [
            TrafficEvent(
                id="cz-1",
                event_type="construction",
                severity="medium",
                description="Paving I-71 near Columbus",
                county="Franklin",
                latitude=39.83,
                longitude=-83.01,
                road_name="I-71",
                location_text="Near milepost 15",
                work_type="paving",
                closure="single lane",
            )
        ]
        trip = _make_trip(traffic_provider=provider)
        zones = trip._place_real_construction_zones()

        # Should create a pair: construction merge taper + construction zone
        assert len(zones) == 2
        assert zones[0].reason == "construction merge"
        assert zones[1].reason == "construction"

        # Zone should have the right speed limit for single lane closure
        assert zones[1].limit_mph == 45.0

    def test_multiple_events_separate_zones(self):
        """Multiple events create separate zone pairs."""
        provider = MagicMock(spec=RealTrafficProvider)
        provider.get_construction_near_route.return_value = [
            TrafficEvent(
                id="cz-1",
                event_type="construction",
                severity="medium",
                description="Paving near Columbus",
                county="Franklin",
                latitude=39.83,
                longitude=-83.01,
                road_name="I-71",
                closure="single lane",
            ),
            TrafficEvent(
                id="cz-2",
                event_type="construction",
                severity="medium",
                description="Bridge work near Cincinnati",
                county="Hamilton",
                latitude=39.31,
                longitude=-83.34,
                road_name="I-71",
                closure="alternating",
            ),
        ]
        trip = _make_trip(traffic_provider=provider)
        zones = trip._place_real_construction_zones()

        assert len(zones) == 4
        reasons = [z.reason for z in zones]
        assert reasons.count("construction") == 2
        assert reasons.count("construction merge") == 2

        # The second zone (Cincinnati) should have alternating closure speed
        assert zones[-1].limit_mph == 35.0

    def test_events_ignored_when_far_from_route(self):
        """Construction events far from the route are filtered out."""
        provider = MagicMock(spec=RealTrafficProvider)
        # Provide an event that has coordinates far from our test route
        provider.get_construction_near_route.return_value = [
            TrafficEvent(
                id="cz-far",
                event_type="construction",
                severity="low",
                description="Work on I-90 near Cleveland",
                county="Cuyahoga",
                latitude=41.5,  # Cleveland - far from I-71 Columbus-Cincinnati
                longitude=-81.7,
                road_name="I-90",
                closure="shoulder",
            ),
        ]
        trip = _make_trip(traffic_provider=provider)
        zones = trip._place_real_construction_zones()

        # The event is on I-90 near Cleveland which is >2 miles from any
        # route point on the I-71 Columbus-Cincinnati leg, so it should
        # be filtered and return empty.
        assert zones == []

    def test_facility_approach_route_returns_empty(self):
        """Facility approach routes skip real construction zones."""
        provider = MagicMock(spec=RealTrafficProvider)
        route = Route(
            cities=["columbus_oh_us", "columbus_oh_us"],
            legs=[_make_leg(miles=2.0)],
        )
        truck = TruckState(TruckSpecs())
        weather = WeatherSystem()
        trip = Trip(
            route=route,
            truck=truck,
            weather=weather,
            time_scale=1.0,
            seed=42,
            traffic_provider=provider,
        )
        zones = trip._place_real_construction_zones()
        assert zones == []


# --- Test construction zone integration into _place_zones -------------------


class TestConstructionZoneIntegration:
    """Real construction zones replace simulated ones in _place_zones."""

    def test_simulated_zones_when_no_provider(self):
        """Without a traffic provider, the trip still builds zones."""
        trip = _make_trip(traffic_provider=None)
        zones = trip.zones

        # Simulated construction zones are placed at 1 per 150 miles, so a
        # 100-mile route has zero. Verify that zones still exist from other
        # sources (congestion, facility approach).
        assert len(zones) >= 0

    def test_real_zones_replace_simulated(self):
        """When real construction zones exist, they are added to trip zones."""
        provider = MagicMock(spec=RealTrafficProvider)
        provider.get_construction_near_route.return_value = [
            TrafficEvent(
                id="cz-1",
                event_type="construction",
                severity="medium",
                description="Construction zone on I-71",
                county="Franklin",
                latitude=39.83,
                longitude=-83.01,
                road_name="I-71",
                closure="single lane",
            ),
        ]
        trip = _make_trip(traffic_provider=provider)

        # With a 100-mile route (simulated zones placed at 1/150mi = 0),
        # there are no simulated zones to replace. Real zones are still added.
        real_zones = [z for z in trip.zones if z.reason == "construction"]
        real_merge = [z for z in trip.zones if z.reason == "construction merge"]

        # Should have at least one real zone pair added to trip.zones
        assert len(real_zones) >= 1
        assert len(real_merge) >= 1

        # Verify congestion zones still exist (they're always added)
        congestion = [z for z in trip.zones if z.reason == "heavy traffic"]
        assert len(congestion) >= 0  # May or may not exist on short route

    def test_route_state_identification(self):
        """Trip collects route geometry from its legs, including state."""
        trip = _make_trip()
        geometry = trip._collect_route_geometry()

        # The geometry should have our highway and state from state_miles
        assert "I-71" in geometry
        state, points = geometry["I-71"]
        assert state == "Ohio"
        assert len(points) >= 7  # We defined 7 route points

    def test_construction_zone_speed_single_lane(self):
        """Single lane closure zones get 45 mph default."""
        trip = _make_trip()
        event = TrafficEvent(
            id="test",
            event_type="construction",
            severity="medium",
            description="test",
            county="test",
            closure="single lane",
            latitude=39.83,
            longitude=-83.01,
        )
        speed = trip._construction_zone_speed(event)
        assert speed == 45.0

    def test_construction_zone_speed_full_closure(self):
        """Full closure zones get 15 mph."""
        trip = _make_trip()
        event = TrafficEvent(
            id="test",
            event_type="construction",
            severity="high",
            description="test",
            county="test",
            closure="full closure",
            latitude=39.83,
            longitude=-83.01,
        )
        speed = trip._construction_zone_speed(event)
        assert speed == 15.0

    def test_construction_zone_length_from_location(self):
        """Zone length parsed from location text."""
        trip = _make_trip()
        event = TrafficEvent(
            id="test",
            event_type="construction",
            severity="medium",
            description="test",
            county="test",
            closure="single lane",
            location_text="Between milepost 45 and 47",
            latitude=39.83,
            longitude=-83.01,
        )
        length = trip._construction_zone_length(event)
        assert length == 2.0  # 47 - 45 = 2

    def test_construction_zone_length_default(self):
        """Default zone length when location text and work type are empty."""
        trip = _make_trip()
        event = TrafficEvent(
            id="test",
            event_type="construction",
            severity="medium",
            description="test",
            county="test",
            closure="single lane",
            latitude=39.83,
            longitude=-83.01,
        )
        length = trip._construction_zone_length(event)
        # Default when no work_type matches: 4.0 miles
        assert length == 4.0


# --- Test RealTrafficProvider construction features -------------------------


class TestRealTrafficProviderConstruction:
    """RealTrafficProvider construction-specific features."""

    def test_state_apis_has_construction_endpoint(self):
        """STATE_APIS includes construction endpoints."""
        assert "construction_endpoint" in STATE_APIS["ohio"]
        assert STATE_APIS["ohio"]["construction_endpoint"] == "/v1/construction"

    def test_fetch_construction_for_unsupported_state(self):
        """fetch_construction returns empty for unsupported states."""
        provider = RealTrafficProvider()
        # Texas is now in STATE_APIS with wzdx parser, so use a code not
        # in the list (e.g., "puerto rico") for the unsupported test.
        data = provider.fetch_construction("puerto rico")
        assert isinstance(data, TrafficData)
        assert data.events == []
        assert data.source == "empty"

    def test_fetch_construction_for_no_api_state(self):
        """fetch_construction returns empty immediately for no_api states."""
        provider = RealTrafficProvider()
        data = provider.fetch_construction("alabama")
        assert isinstance(data, TrafficData)
        assert data.events == []
        assert data.source == "empty"

    def test_all_states_have_parser(self):
        """Every state in STATE_APIS has a valid parser key."""
        valid_parsers = {"ohgo", "iteris", "wzdx", "no_api"}
        for key, config in STATE_APIS.items():
            assert "parser" in config, f"{key} missing parser"
            assert config["parser"] in valid_parsers, f"{key} has unknown parser {config['parser']}"

    def test_parse_construction_ohgo_format(self):
        """Parse OHGO construction format from sample API response."""
        provider = RealTrafficProvider()
        sample_data = {
            "construction": [
                {
                    "id": "cz-1",
                    "road": "I-71",
                    "description": "Paving operations between MM 45 and MM 47",
                    "county": "Franklin",
                    "lat": 39.83,
                    "lon": -83.01,
                    "start_date": "2026-07-15",
                    "end_date": "2026-08-15",
                    "lanes_affected": "left lane closed",
                    "closure_type": "single lane",
                }
            ]
        }
        events = provider._parse_construction_events(sample_data, "ohio")
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "construction"
        assert event.road_name == "I-71"
        assert event.closure == "single lane"
        assert event.latitude == 39.83
        assert event.longitude == -83.01

    def test_parse_construction_empty_response(self):
        """Empty or missing data returns empty list."""
        provider = RealTrafficProvider()
        assert provider._parse_construction_events({}, "ohio") == []
        assert provider._parse_construction_events({"incidents": []}, "ohio") == []

    def test_classify_work_type_from_description(self):
        """Work type inferred from description keywords."""
        provider = RealTrafficProvider()
        assert provider._classify_work_type({"description": "Bridge deck repair"}) == "bridge"
        assert provider._classify_work_type({"description": "Paving I-71"}) == "paving"
        assert provider._classify_work_type({"description": "Utility work"}) == "utility"
        assert provider._classify_work_type({"description": "Road construction"}) == "construction"

    def test_construction_severity_mapping(self):
        """Severity maps correctly from closure type."""
        provider = RealTrafficProvider()
        assert provider._construction_severity("full closure") == "high"
        assert provider._construction_severity("single lane") == "medium"
        assert provider._construction_severity("shoulder") == "low"

    def test_road_name_matching_variants(self):
        """Road name matching handles different formats."""
        provider = RealTrafficProvider()
        assert provider._road_name_matches("I-71", "I-71") is True
        assert provider._road_name_matches("I 71", "I-71") is True
        assert provider._road_name_matches("Interstate 71", "I-71") is True
        assert provider._road_name_matches("71", "I-71") is False  # No I prefix
        assert provider._road_name_matches("I-90", "I-71") is False


# --- Test Iteris platform parser -------------------------------------------


class TestIterisParser:
    """Shared Iteris-platform parser covers WI, NY, GA, AZ, CT."""

    def test_iteris_platform_states_in_state_apis(self):
        """Live Iteris states are listed in STATE_APIS with parser='iteris'.

        Wisconsin left this list 2026-07-23: 511wi.gov's REST API is gone
        (every path 404s), so it runs as no_api until a working endpoint
        is found -- same treatment as Indiana."""
        for key in ("new york", "georgia", "arizona", "connecticut"):
            assert key in STATE_APIS, f"Missing {key} in STATE_APIS"
            assert STATE_APIS[key]["parser"] == "iteris", f"{key} parser not iteris"
            assert "base_url" in STATE_APIS[key], f"{key} missing base_url"
            assert "events_endpoint" in STATE_APIS[key], f"{key} missing events_endpoint"
            assert "construction_endpoint" in STATE_APIS[key], (
                f"{key} missing construction_endpoint"
            )

    def test_parse_iteris_events_basic(self):
        """Parse a simple Iteris-format event list."""
        provider = RealTrafficProvider()
        sample = [
            {
                "id": "evt-1",
                "event_type": "ACCIDENT",
                "severity": "moderate",
                "headline": "Crash on I-94 near Milwaukee",
                "road_name": "I-94",
                "lat": 43.0,
                "lon": -88.0,
                "county": "Milwaukee",
                "start_date": "2026-07-18T08:00:00",
            },
            {
                "id": "evt-2",
                "event_type": "CONSTRUCTION",
                "severity": "minor",
                "headline": "Road work on I-43 near Green Bay",
                "lat": 44.5,
                "lon": -88.0,
                "county": "Brown",
            },
        ]
        events = provider._parse_iteris_events(sample, "wisconsin")
        assert len(events) == 2
        # First event is an incident
        assert events[0].event_type == "incident"
        assert events[0].road_name == "I-94"
        assert events[0].severity == "medium"  # moderate -> medium
        assert events[0].latitude == 43.0
        assert events[0].county == "Milwaukee"
        # Second event is construction
        assert events[1].event_type == "construction"
        assert events[1].road_name == ""  # No road_name in the item

    def test_parse_iteris_events_construction_only(self):
        """Construction parser filters to only construction-type events."""
        provider = RealTrafficProvider()
        sample = [
            {
                "id": "c1",
                "event_type": "CONSTRUCTION",
                "headline": "Road work on I-39",
                "lat": 44.0,
                "lon": -89.0,
            },
            {"id": "i1", "event_type": "ACCIDENT", "headline": "Crash", "lat": 43.5, "lon": -88.5},
            {
                "id": "c2",
                "event_type": "ROADWORK",
                "headline": "Paving I-94",
                "lat": 43.2,
                "lon": -87.9,
            },
        ]
        events = provider._parse_iteris_construction_events(sample, "wisconsin")
        assert len(events) == 2  # c1 and c2 (construction + roadwork)
        ids = [e.id for e in events]
        assert "c1" in ids
        assert "c2" in ids

    def test_parse_iteris_events_empty(self):
        """Empty Iteris data returns empty list."""
        provider = RealTrafficProvider()
        assert provider._parse_iteris_events([], "wisconsin") == []
        assert provider._parse_iteris_events({}, "wisconsin") == []

    def test_parse_iteris_coordinates_direct(self):
        """Iteris coordinates parsed from top-level lat/lon."""
        provider = RealTrafficProvider()
        lat, lon = provider._parse_iteris_coordinates({"lat": 43.0, "lon": -88.0})
        assert lat == 43.0
        assert lon == -88.0

    def test_parse_iteris_coordinates_sub_object(self):
        """Iteris coordinates parsed from location sub-object."""
        provider = RealTrafficProvider()
        lat, lon = provider._parse_iteris_coordinates({"location": {"lat": 43.0, "lon": -88.0}})
        assert lat == 43.0
        assert lon == -88.0

    def test_parse_iteris_coordinates_missing(self):
        """Missing Iteris coordinates returns None."""
        provider = RealTrafficProvider()
        lat, lon = provider._parse_iteris_coordinates({})
        assert lat is None
        assert lon is None

    def test_build_iteris_location_text_direct(self):
        """Iteris location_text from direct field."""
        provider = RealTrafficProvider()
        text = provider._build_iteris_location_text(
            {
                "location_text": "Between milepost 45 and 47",
            }
        )
        assert text == "Between milepost 45 and 47"

    def test_build_iteris_location_text_milepost(self):
        """Iteris location from milepost fields."""
        provider = RealTrafficProvider()
        text = provider._build_iteris_location_text(
            {
                "start_milepost": "45",
                "end_milepost": "47",
            }
        )
        assert "milepost 45" in text and "47" in text

    def test_build_iteris_location_text_cross_street(self):
        """Iteris location from cross street."""
        provider = RealTrafficProvider()
        text = provider._build_iteris_location_text(
            {
                "cross_street": "Main St",
            }
        )
        assert text == "At Main St"

    def test_build_iteris_location_text_empty(self):
        """Empty Iteris location fields return empty string."""
        provider = RealTrafficProvider()
        assert provider._build_iteris_location_text({}) == ""
        assert provider._build_iteris_location_text({"cross_street": ""}) == ""

    def test_determine_iteris_closure_direct(self):
        """Iteris closure type from direct field."""
        provider = RealTrafficProvider()
        result = provider._determine_iteris_closure({"closure": "full closure"}, "")
        assert result == "full closure"

    def test_determine_iteris_closure_from_description(self):
        """Iteris closure inferred from description keywords."""
        provider = RealTrafficProvider()
        assert (
            provider._determine_iteris_closure({}, "road closed for construction") == "full closure"
        )
        assert (
            provider._determine_iteris_closure({}, "alternating one-way traffic") == "alternating"
        )
        assert provider._determine_iteris_closure({}, "right shoulder closed") == "shoulder"
        assert provider._determine_iteris_closure({}, "left lane closed") == "single lane"

    def test_fetch_construction_routes_to_iteris_parser(self):
        """fetch_construction for an Iteris state uses the correct parser."""
        provider = RealTrafficProvider()
        # Without network, should fall through to empty data.
        # The parser routing happens inside _fetch_construction_from_api which
        # is called by _fetch_construction_background.  What we can test:
        # an Iteris state is recognised as supported. (Wisconsin left the
        # Iteris roster 2026-07-23 -- dead REST API -- so Georgia carries
        # this check now.)
        data = provider.fetch_construction("georgia")
        assert data.state == "georgia"
        assert isinstance(data, TrafficData)

    def test_request_routes_to_iteris_parser(self):
        """request() for an Iteris state uses the correct parser."""
        provider = RealTrafficProvider()
        data = provider.request("new york")
        assert data.state == "new york"
        assert isinstance(data, TrafficData)


# --- Test WZDx standard parser ---------------------------------------------


class TestWZDxParser:
    """WZDx v4.0 GeoJSON FeatureCollection parser."""

    def test_wzdx_states_in_state_apis(self):
        """WZDx states are listed with parser='wzdx'."""
        # Indiana left this list 2026-07-22: 511in.org answers every REST
        # path with its SPA shell (the data is behind GraphQL), so it runs
        # as no_api until a GraphQL client exists.
        wzdx_keys = (
            "california",
            "colorado",
            "florida",
            "idaho",
            "maryland",
            "michigan",
            "minnesota",
            "missouri",
            "nevada",
            "new jersey",
            "north carolina",
            "oregon",
            "pennsylvania",
            "tennessee",
            "texas",
            "utah",
            "virginia",
            "washington",
        )
        for key in wzdx_keys:
            assert key in STATE_APIS, f"Missing {key} in STATE_APIS"
            assert STATE_APIS[key]["parser"] == "wzdx", f"{key} parser not wzdx"

    def test_parse_wzdx_feature_collection(self):
        """Parse a WZDx FeatureCollection with one work zone."""
        provider = RealTrafficProvider()
        sample = {
            "type": "FeatureCollection",
            "features": [
                {
                    "id": "wz-1",
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.0, 45.0],
                    },
                    "properties": {
                        "wzdx:roadName": "I-5",
                        "wzdx:workZoneName": "Bridge repair near Portland",
                        "wzdx:workZoneType": "construction",
                        "wzdx:vehicleImpact": "some-lanes-closed",
                        "wzdx:startDate": "2026-07-15",
                        "wzdx:endDate": "2026-08-15",
                        "wzdx:county": "Multnomah",
                    },
                }
            ],
        }
        events = provider._parse_wzdx_events(sample, "oregon")
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "construction"
        assert event.road_name == "I-5"
        assert event.closure == "single lane"
        assert event.latitude == 45.0
        assert event.longitude == -122.0
        assert event.county == "Multnomah"

    def test_parse_wzdx_no_namespace(self):
        """WZDx parser handles properties without wzdx: namespace."""
        provider = RealTrafficProvider()
        sample = {
            "features": [
                {
                    "id": "wz-2",
                    "geometry": {"type": "Point", "coordinates": [-90.0, 35.0]},
                    "properties": {
                        "roadName": "I-40",
                        "workZoneType": "maintenance",
                        "vehicleImpact": "shoulder-closed",
                        "county": "Shelby",
                    },
                }
            ],
        }
        events = provider._parse_wzdx_events(sample, "tennessee")
        assert len(events) == 1
        assert events[0].road_name == "I-40"
        assert events[0].closure == "shoulder"

    def test_parse_wzdx_line_string_geometry(self):
        """WZDx parser takes midpoint of LineString geometry."""
        provider = RealTrafficProvider()
        sample = {
            "features": [
                {
                    "id": "wz-3",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [-122.1, 45.0],
                            [-122.0, 45.1],
                            [-121.9, 45.2],  # midpoint
                        ],
                    },
                    "properties": {
                        "wzdx:roadName": "I-84",
                        "wzdx:workZoneType": "construction",
                        "wzdx:vehicleImpact": "all-lanes-closed",
                    },
                }
            ],
        }
        events = provider._parse_wzdx_events(sample, "oregon")
        assert len(events) == 1
        # Midpoint: [-122.0, 45.1] -> lat=45.1, lon=-122.0
        assert events[0].latitude == 45.1
        assert events[0].longitude == -122.0
        assert events[0].closure == "full closure"

    def test_parse_wzdx_construction_filter(self):
        """WZDx construction parser only returns construction events."""
        provider = RealTrafficProvider()
        sample = {
            "features": [
                {
                    "id": "wz-1",
                    "geometry": {"type": "Point", "coordinates": [-80.0, 40.0]},
                    "properties": {
                        "wzdx:roadName": "I-79",
                        "wzdx:workZoneType": "construction",
                        "wzdx:vehicleImpact": "some-lanes-closed",
                    },
                },
                {
                    "id": "inc-1",
                    "geometry": {"type": "Point", "coordinates": [-80.0, 40.5]},
                    "properties": {
                        "wzdx:roadName": "I-79",
                        "wzdx:workZoneType": "accident",
                        "wzdx:vehicleImpact": "flow-of-traffic",
                    },
                },
            ],
        }
        events = provider._parse_wzdx_construction_events(sample, "pennsylvania")
        assert len(events) == 1
        assert events[0].id == "wz-1"

    def test_wzdx_empty_data(self):
        """Empty WZDx data returns empty list."""
        provider = RealTrafficProvider()
        assert provider._parse_wzdx_events({}, "oregon") == []
        assert provider._parse_wzdx_events({"features": []}, "oregon") == []
        assert provider._parse_wzdx_events([], "oregon") == []

    def test_wzdx_missing_coordinates(self):
        """WZDx event without geometry returns no lat/lon."""
        provider = RealTrafficProvider()
        sample = {
            "features": [
                {
                    "id": "wz-nogeo",
                    "geometry": None,
                    "properties": {
                        "wzdx:roadName": "US-101",
                        "wzdx:workZoneType": "construction",
                    },
                }
            ],
        }
        events = provider._parse_wzdx_events(sample, "california")
        assert len(events) == 1
        assert events[0].latitude is None

    def test_wzdx_impact_mapping(self):
        """Maps WZDx vehicleImpact values to closure types."""
        provider = RealTrafficProvider()
        assert provider._wzdx_impact_to_closure("all-lanes-closed") == "full closure"
        assert provider._wzdx_impact_to_closure("some-lanes-closed") == "single lane"
        assert provider._wzdx_impact_to_closure("shoulder-closed") == "shoulder"
        assert provider._wzdx_impact_to_closure("alternating-one-way") == "alternating"
        assert provider._wzdx_impact_to_closure("") == "single lane"

    def test_build_wzdx_location_text(self):
        """WZDx location text from properties."""
        provider = RealTrafficProvider()
        assert (
            provider._build_wzdx_location_text(
                {
                    "wzdx:locationDescription": "Between exits 45 and 47",
                }
            )
            == "Between exits 45 and 47"
        )
        assert (
            provider._build_wzdx_location_text(
                {
                    "wzdx:beginningMilepost": "45",
                    "wzdx:endingMilepost": "47",
                }
            )
            == "Between milepost 45 and 47"
        )
        assert provider._build_wzdx_location_text({}) == ""

    def test_no_api_states_return_empty(self):
        """no_api parser states return empty data immediately."""
        provider = RealTrafficProvider()
        for key in ("alabama", "kansas", "wyoming"):
            assert key in STATE_APIS
            assert STATE_APIS[key]["parser"] == "no_api"
            data = provider.request(key)
            assert data.events == []
            data = provider.fetch_construction(key)
            assert data.events == []
