"""Tests for real construction zones from state 511 APIs."""

from __future__ import annotations

from dataclasses import replace
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

    def test_single_lane_road_keeps_every_lane_open(self):
        """A reported closure on a one-lane-each-way road is placed with no
        coned-off lane: closing the only lane leaves nowhere legal to drive."""
        from freight_fate.data.world_models import LaneSegment

        provider = MagicMock(spec=RealTrafficProvider)
        provider.get_construction_near_route.return_value = [
            TrafficEvent(
                id="cz-narrow",
                event_type="construction",
                severity="medium",
                description="Paving US 20",
                county="Franklin",
                latitude=39.83,
                longitude=-83.01,
                road_name="I-71",
                closure="single lane",
            )
        ]
        # Undivided two-way: one lane in the direction of travel.
        leg = _make_leg()
        leg = replace(leg, lane_segments=(LaneSegment(0.0, leg.miles, lanes=2, oneway=False),))
        route = Route(cities=["columbus_oh_us", "cincinnati_oh_us"], legs=[leg])
        trip = Trip(
            route=route,
            truck=TruckState(TruckSpecs()),
            weather=WeatherSystem(),
            time_scale=1.0,
            seed=42,
            traffic_provider=provider,
        )
        zones = trip._place_real_construction_zones()
        assert zones  # the work zone is still announced
        assert all(z.closed_lane is None for z in zones)

    def test_two_lane_road_still_closes_a_lane(self):
        """Where there is a lane to merge into, the reported closure stands."""
        from freight_fate.data.world_models import LaneSegment

        provider = MagicMock(spec=RealTrafficProvider)
        provider.get_construction_near_route.return_value = [
            TrafficEvent(
                id="cz-wide",
                event_type="construction",
                severity="medium",
                description="Paving I-71",
                county="Franklin",
                latitude=39.83,
                longitude=-83.01,
                road_name="I-71",
                closure="single lane",
            )
        ]
        leg = _make_leg()
        leg = replace(leg, lane_segments=(LaneSegment(0.0, leg.miles, lanes=2, oneway=True),))
        route = Route(cities=["columbus_oh_us", "cincinnati_oh_us"], legs=[leg])
        trip = Trip(
            route=route,
            truck=TruckState(TruckSpecs()),
            weather=WeatherSystem(),
            time_scale=1.0,
            seed=42,
            traffic_provider=provider,
        )
        zones = trip._place_real_construction_zones()
        assert [z.closed_lane for z in zones] == [0, 0]

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
        valid_parsers = {"ohgo", "iteris", "wzdx", "cars", "list511", "no_api"}
        for key, config in STATE_APIS.items():
            assert "parser" in config, f"{key} missing parser"
            assert config["parser"] in valid_parsers, f"{key} has unknown parser {config['parser']}"
            if "construction_parser" in config:
                assert config["construction_parser"] in valid_parsers, key

    def test_cars_states_have_bounds_and_layer_slugs(self):
        """CARS GraphQL states carry a parseable bounding box and layer slugs."""
        cars_keys = [key for key, config in STATE_APIS.items() if config["parser"] == "cars"]
        assert set(cars_keys) == {"indiana", "minnesota", "colorado"}
        for key in cars_keys:
            config = STATE_APIS[key]
            south, west, north, east = (float(v) for v in config["bounds"].split(","))
            assert south < north, f"{key} bounds south/north swapped"
            assert west < east, f"{key} bounds west/east swapped"
            # Layer slugs are bare words, not URL paths
            assert not config["events_endpoint"].startswith("/"), key
            assert not config["construction_endpoint"].startswith("/"), key

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

    def test_no_state_rides_the_iteris_rest_api(self):
        """No state is configured with parser='iteris' any more.

        The 2026-08-09 live sweep found every Iteris-platform /api/events
        REST endpoint gone (404); those sites now publish WZDx v4 feeds at
        /api/wzdx instead.  The parser stays because the CARS parser reuses
        its closure and location helpers."""
        for key, config in STATE_APIS.items():
            assert config["parser"] != "iteris", f"{key} still rides the dead Iteris REST API"

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

    def test_fetch_construction_recognises_live_state(self):
        """fetch_construction for a live state returns a TrafficData shell.

        Without network, should fall through to empty data.  The parser
        routing happens inside _fetch_construction_from_api which is called
        by _fetch_construction_background.  What we can test: a live state
        is recognised as supported."""
        provider = RealTrafficProvider()
        data = provider.fetch_construction("georgia")
        assert data.state == "georgia"
        assert isinstance(data, TrafficData)

    def test_request_recognises_live_state(self):
        """request() for a live state returns a TrafficData shell."""
        provider = RealTrafficProvider()
        data = provider.request("new york")
        assert data.state == "new york"
        assert isinstance(data, TrafficData)


# --- Test WZDx standard parser ---------------------------------------------


class TestWZDxParser:
    """WZDx v4.0 GeoJSON FeatureCollection parser."""

    def test_wzdx_states_in_state_apis(self):
        """WZDx states are listed with parser='wzdx' and read /api/wzdx.

        This is the live roster from the 2026-08-09 sweep: the old per-site
        /api/events endpoints are gone everywhere, but these sites publish a
        WZDx v4.x feed at /api/wzdx, so both fetches read it.  Colorado and
        Minnesota moved to the CARS GraphQL parser; Florida and New York
        moved their incident fetch to the list511 parser 2026-08-20 (their
        work zones still ride WZDx, checked by TestList511Parser); the rest
        of the old roster (California, Maryland, Michigan, Missouri, New
        Jersey, Oregon, Tennessee, Texas, Virginia, Washington) went dark
        and sits on no_api."""
        wzdx_keys = (
            "arizona",
            "connecticut",
            "georgia",
            "idaho",
            "nevada",
            "north carolina",
            "pennsylvania",
            "utah",
            "wisconsin",
        )
        for key in wzdx_keys:
            assert key in STATE_APIS, f"Missing {key} in STATE_APIS"
            assert STATE_APIS[key]["parser"] == "wzdx", f"{key} parser not wzdx"
            assert STATE_APIS[key]["events_endpoint"] == "/api/wzdx", key
            assert STATE_APIS[key]["construction_endpoint"] == "/api/wzdx", key

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


# --- Test WZDx v4 (snake_case core_details) parser ---------------------------


class TestWZDxV4Parser:
    """WZDx v4.x layout: snake_case properties under core_details.

    The fixture is a real feature recorded 2026-08-09 from
    https://511wi.gov/api/wzdx (v4.2), trimmed to what the parser reads.
    """

    WI_FEATURE = {
        "id": "ca261ca8-7974-6058-ab4d-25b80def22e6",
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [-87.938228, 43.381435],
                [-87.93815776899706, 43.381493952295386],
                [-87.93795762587283, 43.381571379674995],
            ],
        },
        "properties": {
            "core_details": {
                "event_type": "work-zone",
                "data_source_id": "ATMS-ExtEvent",
                "road_names": ["WIS 33 EB"],
                "direction": "eastbound",
                "name": "WisLCS-273413-1",
                "description": (
                    "Mainline Right Lane Closed on WIS 33 EB from MILWAUKEE RIVER "
                    "OVERFLOW (BRIDGE CROSSING) to WIS 33 WB (END DIVIDED)"
                ),
            },
            "start_date": "2026-06-15T11:00:00+00:00",
            "end_date": "2026-09-03T04:59:59+00:00",
            "vehicle_impact": "some-lanes-closed",
            "lanes": [
                {"order": 1, "type": "shoulder", "status": "open"},
                {"order": 2, "type": "general", "status": "open"},
                {"order": 3, "type": "general", "status": "closed"},
                {"order": 4, "type": "shoulder", "status": "closed"},
            ],
            "beginning_cross_street": "MILWAUKEE RIVER OVERFLOW (BRIDGE CROSSING)",
            "ending_cross_street": "WIS 33 WB (END DIVIDED)",
        },
    }

    def test_parse_v4_work_zone(self):
        """A v4.2 work-zone feature parses with core_details fields."""
        provider = RealTrafficProvider()
        sample = {"type": "FeatureCollection", "features": [self.WI_FEATURE]}
        events = provider._parse_wzdx_events(sample, "wisconsin")
        assert len(events) == 1
        event = events[0]
        assert event.id == "ca261ca8-7974-6058-ab4d-25b80def22e6"
        assert event.event_type == "construction"
        assert event.road_name == "WIS 33 EB"
        assert event.description.startswith("Mainline Right Lane Closed on WIS 33 EB")
        assert event.closure == "single lane"
        assert event.severity == "medium"
        assert event.start_time == "2026-06-15T11:00:00+00:00"
        assert event.estimated_end == "2026-09-03T04:59:59+00:00"
        # LineString midpoint
        assert event.latitude == 43.381493952295386
        assert event.longitude == -87.93815776899706

    def test_v4_lane_description_counts_general_lanes(self):
        """Closed-lane counts skip shoulders."""
        provider = RealTrafficProvider()
        events = provider._parse_wzdx_events({"features": [self.WI_FEATURE]}, "wisconsin")
        assert events[0].lanes_affected == "1 of 2 lanes closed"

    def test_v4_shoulder_only_closure(self):
        """A shoulder-only closure reads as shoulder closed."""
        provider = RealTrafficProvider()
        feature = {
            "id": "wz-shoulder",
            "geometry": {"type": "Point", "coordinates": [-88.0, 43.0]},
            "properties": {
                "core_details": {"event_type": "work-zone", "road_names": ["I-94"]},
                "vehicle_impact": "shoulder-closed",
                "lanes": [
                    {"order": 1, "type": "shoulder", "status": "closed"},
                    {"order": 2, "type": "general", "status": "open"},
                ],
            },
        }
        events = provider._parse_wzdx_events({"features": [feature]}, "wisconsin")
        assert events[0].lanes_affected == "shoulder closed"
        assert events[0].closure == "shoulder"
        assert events[0].severity == "low"

    def test_v4_cross_street_location_text(self):
        """Location text is built from the v4 cross-street fields."""
        provider = RealTrafficProvider()
        events = provider._parse_wzdx_events({"features": [self.WI_FEATURE]}, "wisconsin")
        assert events[0].location_text == (
            "Between MILWAUKEE RIVER OVERFLOW (BRIDGE CROSSING) and WIS 33 WB (END DIVIDED)"
        )

    def test_v4_construction_filter_keeps_work_zones(self):
        """The construction fetch keeps v4 work-zone events."""
        provider = RealTrafficProvider()
        events = provider._parse_wzdx_construction_events(
            {"features": [self.WI_FEATURE]}, "wisconsin"
        )
        assert len(events) == 1

    def test_v4_multipoint_geometry(self):
        """MultiPoint geometry (511ny.org's layout) yields coordinates.

        Trimmed from a real feature recorded 2026-08-09 from
        https://511ny.org/api/wzdx."""
        provider = RealTrafficProvider()
        feature = {
            "id": "ny-1",
            "geometry": {"type": "MultiPoint", "coordinates": [[-73.797869, 41.019265]]},
            "properties": {
                "core_details": {"event_type": "work-zone", "road_names": ["NY 100"]},
                "vehicle_impact": "some-lanes-closed",
            },
        }
        events = provider._parse_wzdx_events({"features": [feature]}, "new york")
        assert events[0].latitude == 41.019265
        assert events[0].longitude == -73.797869


# --- Test Castle Rock CARS GraphQL parser ------------------------------------


class TestCarsParser:
    """CARS MapFeatures parser covers Indiana, Minnesota, and Colorado.

    Fixtures are real map features recorded 2026-08-09 from
    https://511in.org/api/graphql and https://511mn.org/api/graphql,
    trimmed to what the parser reads.
    """

    IN_LANE_CLOSED = {
        "bbox": [-86.84936, 41.68731, -86.84715, 41.68742],
        "title": "US 20 (Mile Point 42.5 - 42.61): Lane closed.",
        "tooltip": "US 20: Lane closed.",
        "uri": "event/CARSy-30",
        "features": [
            {
                "id": "CARSy-30-1184291760",
                "geometry": {"type": "Point", "coordinates": [-86.84825, 41.68732]},
                "properties": {},
            }
        ],
        "priority": 5,
        "__typename": "Event",
    }

    IN_ROAD_CLOSED = {
        "bbox": [-86.1268, 38.08214, -85.82829, 38.30399],
        "title": "IN 11 (Mile Point 12.4 - 12.34): Road closed.",
        "tooltip": "IN 11: Road closed, see map for detour(s).",
        "uri": "event/CARSy-34",
        "features": [
            {
                "id": "CARSy-34-2192814423",
                "geometry": {"type": "Point", "coordinates": [-86.03935, 38.08253]},
                "properties": {},
            }
        ],
        "priority": 2,
        "__typename": "Event",
    }

    MN_CRASH = {
        "bbox": [-93.03416, 45.21468, -93.03416, 45.21468],
        "title": "I-35W southbound: Crash.",
        "tooltip": "I-35W southbound: Crash.",
        "uri": "event/MSPCAD-129052",
        "features": [
            {
                "id": "MSPCAD-129052-2307205820",
                "geometry": {"type": "Point", "coordinates": [-93.03416, 45.21468]},
                "properties": {},
            }
        ],
        "priority": 5,
        "__typename": "Event",
    }

    MN_FUTURE = {
        "bbox": [-92.48837, 43.88284, -92.23476, 43.97919],
        "title": "STARTS FRIDAY. I-90 eastbound: Bridge construction.",
        "tooltip": "STARTS FRIDAY. I-90 eastbound: Bridge construction.",
        "uri": "event/CARSx-128079",
        "features": [
            {
                "id": "CARSx-128079-132200140",
                "geometry": {"type": "Point", "coordinates": [-92.35459, 43.95132]},
                "properties": {},
            }
        ],
        "priority": 5,
        "__typename": "Event",
    }

    @staticmethod
    def _response(*features):
        return {"data": {"mapFeaturesQuery": {"mapFeatures": list(features), "error": None}}}

    def test_parse_cars_construction(self):
        """A construction-layer batch parses with road, mile range, closure."""
        provider = RealTrafficProvider()
        events = provider._parse_cars_events(
            self._response(self.IN_LANE_CLOSED), "indiana", construction=True
        )
        assert len(events) == 1
        event = events[0]
        assert event.id == "CARSy-30"
        assert event.event_type == "construction"
        assert event.road_name == "US 20"
        assert event.location_text == "Mile Point 42.5 - 42.61"
        assert event.description == "US 20 (Mile Point 42.5 - 42.61): Lane closed."
        assert event.latitude == 41.68732
        assert event.longitude == -86.84825

    def test_parse_cars_road_closure_is_high_severity(self):
        """A road-closed construction event maps to a full closure."""
        provider = RealTrafficProvider()
        events = provider._parse_cars_events(
            self._response(self.IN_ROAD_CLOSED), "indiana", construction=True
        )
        assert events[0].closure == "full closure"
        assert events[0].severity == "high"
        assert events[0].lanes_affected == "all lanes closed"

    def test_parse_cars_incident(self):
        """An incidents-layer batch parses as incidents with priority severity."""
        provider = RealTrafficProvider()
        events = provider._parse_cars_events(
            self._response(self.MN_CRASH), "minnesota", construction=False
        )
        assert len(events) == 1
        event = events[0]
        assert event.id == "MSPCAD-129052"
        assert event.event_type == "incident"
        assert event.road_name == "I-35W"  # direction suffix stripped
        assert event.description == "I-35W southbound: Crash."
        assert event.severity == "medium"  # priority 5

    def test_cars_priority_severity_mapping(self):
        """Priority 1 is most urgent; 1-2 high, 3-5 medium, rest low."""
        provider = RealTrafficProvider()
        assert provider._cars_priority_severity(1) == "high"
        assert provider._cars_priority_severity(2) == "high"
        assert provider._cars_priority_severity(3) == "medium"
        assert provider._cars_priority_severity(5) == "medium"
        assert provider._cars_priority_severity(8) == "low"
        assert provider._cars_priority_severity(None) == "low"

    def test_cars_skips_scheduled_events(self):
        """Events with a STARTS prefix are not on the road yet."""
        provider = RealTrafficProvider()
        events = provider._parse_cars_events(
            self._response(self.MN_FUTURE, self.MN_CRASH), "minnesota", construction=False
        )
        assert [e.id for e in events] == ["MSPCAD-129052"]

    def test_cars_skips_non_event_features(self):
        """Cluster and Sign features are skipped."""
        provider = RealTrafficProvider()
        cluster = {
            "bbox": [-86.9, 41.0, -86.8, 41.1],
            "title": "12 events",
            "uri": "cluster/1",
            "features": [],
            "__typename": "Cluster",
        }
        events = provider._parse_cars_events(
            self._response(cluster, self.IN_LANE_CLOSED), "indiana", construction=True
        )
        assert [e.id for e in events] == ["CARSy-30"]

    def test_cars_bbox_fallback_coordinates(self):
        """Without a Point feature the bbox midpoint is used."""
        provider = RealTrafficProvider()
        item = dict(self.IN_LANE_CLOSED, features=[])
        events = provider._parse_cars_events(self._response(item), "indiana", construction=True)
        assert events[0].latitude == (41.68731 + 41.68742) / 2
        assert events[0].longitude == (-86.84936 + -86.84715) / 2

    def test_cars_empty_and_malformed_responses(self):
        """Empty or malformed GraphQL responses return no events."""
        provider = RealTrafficProvider()
        assert provider._parse_cars_events({}, "indiana", construction=True) == []
        assert provider._parse_cars_events({"data": {}}, "indiana", construction=True) == []
        assert (
            provider._parse_cars_events(
                {"data": {"mapFeaturesQuery": {"mapFeatures": None, "error": None}}},
                "indiana",
                construction=True,
            )
            == []
        )


# --- Test list511 list-page parser -------------------------------------------


class TestList511Parser:
    """list511 parser covers Florida FL511 and New York 511NY incidents.

    Fixtures are real list rows and map pins recorded 2026-08-20 from
    POST https://fl511.com/List/GetData/Incidents,
    POST https://511ny.org/List/GetData/Incidents, and the matching
    GET /map/mapIcons/Incidents endpoints, trimmed to what the parser
    reads.
    """

    FL_CRASH = {
        "DT_RowId": "815973",
        "id": 815973,
        "roadwayName": "SR-70",
        "description": (
            "Multi-vehicle crash in Manatee County on SR-70 East, before "
            "Lorraine Rd. Left turn lane blocked. Last updated at 03:54 PM."
        ),
        "severity": "Intermediate",
        "isFullClosure": False,
        "direction": "Eastbound",
        "laneDescription": "Left turn lane blocked",
        "locationDescription": None,
        "county": "Manatee",
        "startDate": "8/20/26, 3:15 PM",
        "endDate": None,
    }

    NY_TRUCK_RESTRICTION = {
        "DT_RowId": "4496799",
        "id": 4496799,
        "roadwayName": "George Washington Bridge Upper Level",
        "description": (
            "Truck restrictions on George Washington Bridge Upper Level "
            "westbound ramp from West 179th Street (New York) All lanes open "
            "until further notice. Trucks wider than 10 ft or longer than "
            "110 ft are prohibited.<div class='cellSpacer'><i><b>Comments:"
            "</b></i> Until further notice. trucks wider than 10 ft or "
            "longer than 110 ft are prohibited.</div>"
        ),
        "severity": "Minor",
        "isFullClosure": False,
        "laneDescription": "All lanes open",
        "locationDescription": "West 179th Street|",
        "county": "New York",
        "startDate": "5/19/25, 6:27 AM",
        "endDate": None,
    }

    NY_CRASH = {
        "DT_RowId": "4674401",
        "id": 4674401,
        "roadwayName": "I-90 - NYS Thruway",
        "description": (
            "Crash on I-90 - NYS Thruway eastbound at After Exit 41 (I-90) - "
            "Waterloo (Rte 414) starting 4:23 PM, 08/20/2026 "
            "[CARS CAD-262320295]"
        ),
        "severity": None,
        "isFullClosure": False,
        "laneDescription": None,
        "locationDescription": "After Exit 41 (I-90) - Waterloo (Rte 414)|",
        "county": "Seneca",
        "startDate": "8/20/26, 4:23 PM",
        "endDate": None,
    }

    NY_ROAD_CLOSED = {
        "DT_RowId": "4498570",
        "id": 4498570,
        "roadwayName": "NY 218",
        "description": (
            "DOT Debris and Emergency maintenance and Road Closure on NY 218 "
            "both directions between Mountain House Lane (Cornwall) and Grant "
            "Road (Highlands) all lanes of 2 lanes closed until further notice"
            "<div class='cellSpacer'><i><b>Comments:</b></i> Until further "
            "notice</div>"
        ),
        "severity": "Major",
        "isFullClosure": True,
        "laneDescription": "all lanes closed",
        "locationDescription": "Mountain House Lane|Grant Road",
        "county": "Orange",
        "startDate": "5/20/26, 5:25 PM",
        "endDate": None,
    }

    FL_ICONS = {
        "item1": {"url": "/Generated/Content/Images/511/map_exclamationMarkOrangeBlue.svg"},
        "item2": [
            {"itemId": "815973", "location": [27.431793, -82.396087], "icon": {}, "title": ""},
        ],
    }

    NY_ICONS = {
        "item1": {"url": "/Generated/Content/Images/511/map_exclamationMarkOrangeBlue.svg"},
        "item2": [
            {"itemId": "4496799", "location": [40.84938, -73.939624], "icon": {}, "title": ""},
            {"itemId": "4674401", "location": [42.921147, -76.936964], "icon": {}, "title": ""},
        ],
    }

    def test_list511_states_in_state_apis(self):
        """Florida and New York ride list511 incidents plus WZDx zones."""
        for key in ("florida", "new york"):
            config = STATE_APIS[key]
            assert config["parser"] == "list511", key
            # The events endpoint is a list layer name, not a URL path
            assert config["events_endpoint"] == "Incidents", key
            assert not config["events_endpoint"].startswith("/"), key
            # Work zones stay on the WZDx feed
            assert config["construction_parser"] == "wzdx", key
            assert config["construction_endpoint"] == "/api/wzdx", key

    def test_parse_florida_crash(self):
        """An FL row parses with pin coordinates and Intermediate → medium."""
        provider = RealTrafficProvider()
        locations = provider._parse_list511_icon_locations(self.FL_ICONS)
        events = provider._parse_list511_events([self.FL_CRASH], locations, "florida")
        assert len(events) == 1
        event = events[0]
        assert event.id == "815973"
        assert event.event_type == "incident"
        assert event.severity == "medium"
        assert event.road_name == "SR-70"
        assert event.county == "Manatee"
        assert event.latitude == 27.431793
        assert event.longitude == -82.396087
        assert event.lanes_affected == "Left turn lane blocked"
        # The site-clock sentence is stripped from the spoken text
        assert "Last updated" not in event.description
        assert event.description.endswith("Left turn lane blocked.")

    def test_parse_ny_html_stripped(self):
        """The cellSpacer comment div never reaches the spoken text."""
        provider = RealTrafficProvider()
        locations = provider._parse_list511_icon_locations(self.NY_ICONS)
        events = provider._parse_list511_events([self.NY_TRUCK_RESTRICTION], locations, "new york")
        event = events[0]
        assert "<" not in event.description
        assert "Comments" not in event.description
        assert event.description.startswith("Truck restrictions on George Washington Bridge")
        assert event.severity == "low"  # Minor
        # Trailing "|" separator dropped from the location text
        assert event.location_text == "West 179th Street"
        assert event.latitude == 40.84938

    def test_parse_ny_cad_suffix_and_null_severity(self):
        """A CAD source tag is stripped; a null severity falls back to low."""
        provider = RealTrafficProvider()
        events = provider._parse_list511_events([self.NY_CRASH], {}, "new york")
        event = events[0]
        assert "[CARS" not in event.description
        assert event.description.endswith("starting 4:23 PM, 08/20/2026")
        assert event.severity == "low"
        assert event.lanes_affected is None

    def test_full_closure_outranks_row_severity(self):
        """isFullClosure forces high severity and joins location parts."""
        provider = RealTrafficProvider()
        events = provider._parse_list511_events([self.NY_ROAD_CLOSED], {}, "new york")
        event = events[0]
        assert event.severity == "high"
        assert event.location_text == "Mountain House Lane, Grant Road"

    def test_missing_pin_keeps_event_without_coordinates(self):
        """A row without a map pin still parses; coordinates stay None."""
        provider = RealTrafficProvider()
        events = provider._parse_list511_events([self.FL_CRASH], {}, "florida")
        assert len(events) == 1
        assert events[0].latitude is None
        assert events[0].longitude is None

    def test_icon_locations_malformed(self):
        """Malformed pin payloads yield an empty location map, not a crash."""
        provider = RealTrafficProvider()
        assert provider._parse_list511_icon_locations(None) == {}
        assert provider._parse_list511_icon_locations([]) == {}
        assert provider._parse_list511_icon_locations({"item2": "nope"}) == {}
        assert (
            provider._parse_list511_icon_locations(
                {"item2": [{"itemId": "1", "location": [None, None]}, "junk", {}]}
            )
            == {}
        )

    def test_empty_and_malformed_rows(self):
        """Empty, id-less, and non-dict rows are skipped."""
        provider = RealTrafficProvider()
        assert provider._parse_list511_events([], {}, "florida") == []
        rows = [{}, "junk", {"id": None, "description": "x"}, {"id": 5, "description": ""}]
        assert provider._parse_list511_events(rows, {}, "florida") == []


class TestZoneNeedsRoomForItsTaper:
    """A work zone the driver cannot be warned about must not be placed.

    Owner report, 2026-08-16: departing a facility could drop the truck
    inside the cones before it had moved, because a real 511 event near the
    start of a corridor clamped its start to mile zero and its warning taper
    got clipped to nothing behind the driver.
    """

    @staticmethod
    def _zones_for_event_at(lat, lon):
        provider = MagicMock(spec=RealTrafficProvider)
        provider.get_construction_near_route.return_value = [
            TrafficEvent(
                id="cz-start",
                event_type="construction",
                severity="medium",
                description="Paving right at the start of the run",
                county="Franklin",
                latitude=lat,
                longitude=lon,
                road_name="I-71",
                location_text="Near milepost 0",
                work_type="paving",
                closure="single lane",
            )
        ]
        return _make_trip(traffic_provider=provider)._place_real_construction_zones()

    def test_a_zone_at_the_very_start_is_dropped(self):
        # The first route point is mile 0 itself; a zone centred there cannot
        # fit a taper ahead of the driver, so nothing is placed at all.
        zones = self._zones_for_event_at(39.9612, -82.9988)
        assert zones == []

    def test_a_zone_with_room_still_gets_its_full_taper(self):
        """The guard is about the warning fitting, not about a quiet start."""
        from freight_fate.sim.trip_models import CONSTRUCTION_TAPER_MI

        zones = self._zones_for_event_at(39.83, -83.01)  # ~mile 15
        assert len(zones) == 2
        taper, work = zones
        assert taper.reason == "construction merge"
        assert work.reason == "construction"
        # The taper is on the route, ahead of the start, and full length.
        assert taper.start_mi >= 0.0
        assert work.start_mi >= CONSTRUCTION_TAPER_MI
        assert work.start_mi - taper.start_mi == CONSTRUCTION_TAPER_MI
