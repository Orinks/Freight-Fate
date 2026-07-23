"""Real-time traffic data via state 511 APIs."""

import time

from freight_fate.data.world import Leg, Route
from freight_fate.data.world_models import RoutePoint, StateMileage
from freight_fate.sim.real_traffic import (
    CACHE_TTL_S,
    RETRY_AFTER_S,
    STALE_AFTER_S,
    STATE_APIS,
    RealTrafficProvider,
    TrafficData,
    TrafficEvent,
)
from freight_fate.sim.trip import Trip
from freight_fate.sim.vehicle import TruckSpecs, TruckState
from freight_fate.sim.weather import WeatherSystem


def test_traffic_event_serialization():
    """Test that traffic events can be serialized and deserialized."""
    event = TrafficEvent(
        id="test-123",
        event_type="incident",
        severity="high",
        description="Accident on I-70",
        county="Franklin",
        latitude=39.96,
        longitude=-82.99,
        lanes_affected="2 right lanes",
    )

    data = event.to_dict()
    assert data["id"] == "test-123"
    assert data["event_type"] == "incident"
    assert data["severity"] == "high"
    assert data["description"] == "Accident on I-70"

    restored = TrafficEvent.from_dict(data)
    assert restored is not None
    assert restored.id == "test-123"
    assert restored.event_type == "incident"
    assert restored.latitude == 39.96


def test_traffic_event_from_invalid_dict():
    """Test that invalid data returns None."""
    assert TrafficEvent.from_dict({}) is None
    assert TrafficEvent.from_dict(None) is None
    assert TrafficEvent.from_dict([]) is None
    # With ID but missing other fields, should still create event with defaults
    event = TrafficEvent.from_dict({"id": "test-123"})
    assert event is not None
    assert event.id == "test-123"
    assert event.event_type == "incident"  # Default


def test_traffic_data_freshness():
    """Test cache freshness calculations."""
    data = TrafficData(
        state="ohio",
        events=[],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    assert data.is_fresh()
    assert not data.is_stale()

    # Simulate old data
    old_data = TrafficData(
        state="ohio",
        events=[],
        last_updated=time.time() - CACHE_TTL_S - 1,
        cache_time=time.time() - CACHE_TTL_S - 1,
        source="test",
    )

    assert not old_data.is_fresh()
    assert not old_data.is_stale()  # Not yet stale

    # Simulate stale data
    stale_data = TrafficData(
        state="ohio",
        events=[],
        last_updated=time.time() - STALE_AFTER_S - 1,
        cache_time=time.time() - STALE_AFTER_S - 1,
        source="test",
    )

    assert not stale_data.is_fresh()
    assert stale_data.is_stale()


def test_traffic_data_serialization():
    """Test that traffic data can be serialized."""
    event = TrafficEvent(
        id="test-123",
        event_type="incident",
        severity="medium",
        description="Construction",
        county="Hamilton",
    )

    data = TrafficData(
        state="ohio",
        events=[event],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    serialized = data.to_dict()
    assert serialized["state"] == "ohio"
    assert len(serialized["events"]) == 1
    assert serialized["events"][0]["id"] == "test-123"


def test_provider_initialization():
    """Test that provider initializes with empty cache."""
    provider = RealTrafficProvider()
    assert provider._cache == {}
    assert provider._failed_until == {}
    assert provider._locks == {}


def test_provider_unsupported_state():
    """Test that states not in STATE_APIS return empty data."""
    provider = RealTrafficProvider()
    data = provider.request("atlantis")

    assert data.state == "atlantis"
    assert data.events == []
    assert data.source == "empty"


def test_provider_supported_state_returns_empty_initially():
    """Test that supported states return empty data on first request."""
    provider = RealTrafficProvider()
    data = provider.request("ohio")

    assert data.state == "ohio"
    assert data.events == []
    assert data.source == "empty"


def test_severity_mapping():
    """Test that API severity levels are mapped correctly."""
    provider = RealTrafficProvider()

    assert provider._map_severity("low") == "low"
    assert provider._map_severity("minor") == "low"
    assert provider._map_severity("medium") == "medium"
    assert provider._map_severity("moderate") == "medium"
    assert provider._map_severity("high") == "high"
    assert provider._map_severity("major") == "high"
    assert provider._map_severity("severe") == "high"
    assert provider._map_severity("critical") == "high"
    assert provider._map_severity("unknown") == "low"  # Default


def test_haversine_distance():
    """Test distance calculation between two points."""
    provider = RealTrafficProvider()

    # Test known distance (Columbus, OH to Cleveland, OH ≈ 126 miles)
    columbus_lat, columbus_lon = 39.96, -82.99
    cleveland_lat, cleveland_lon = 41.50, -81.69

    distance = provider._haversine_distance(
        columbus_lat, columbus_lon, cleveland_lat, cleveland_lon
    )

    # Should be approximately 126 miles (within 10% tolerance)
    assert 113 < distance < 139


def test_haversine_distance_same_point():
    """Test that distance to same point is zero."""
    provider = RealTrafficProvider()
    distance = provider._haversine_distance(40.0, -83.0, 40.0, -83.0)
    assert distance == 0.0


def test_get_events_near_filters_by_distance():
    """Test that nearby events are filtered by distance."""
    provider = RealTrafficProvider()

    # Create test events
    event_near = TrafficEvent(
        id="near-1",
        event_type="incident",
        severity="high",
        description="Nearby accident",
        county="Franklin",
        latitude=40.0,
        longitude=-83.0,
    )

    event_far = TrafficEvent(
        id="far-1",
        event_type="incident",
        severity="medium",
        description="Far accident",
        county="Cuyahoga",
        latitude=41.5,
        longitude=-81.7,
    )

    # Mock cache with test data
    provider._cache["ohio"] = TrafficData(
        state="ohio",
        events=[event_near, event_far],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    # Search for events within 50 miles of Columbus
    nearby = provider.get_events_near("ohio", 39.96, -82.99, 50.0)

    # Should only include the nearby event
    assert len(nearby) == 1
    assert nearby[0].id == "near-1"


def test_get_events_near_includes_events_within_radius():
    """Test that events exactly at radius boundary are included."""
    provider = RealTrafficProvider()

    event = TrafficEvent(
        id="boundary-1",
        event_type="incident",
        severity="low",
        description="Boundary event",
        county="Franklin",
        latitude=40.0,
        longitude=-83.0,
    )

    provider._cache["ohio"] = TrafficData(
        state="ohio",
        events=[event],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    # Search with 50 mile radius
    nearby = provider.get_events_near("ohio", 39.96, -82.99, 50.0)
    assert len(nearby) == 1


def test_get_events_near_excludes_events_without_location():
    """Test that events without coordinates are excluded."""
    provider = RealTrafficProvider()

    event_no_location = TrafficEvent(
        id="no-loc-1",
        event_type="incident",
        severity="medium",
        description="Event without location",
        county="Unknown",
        latitude=None,
        longitude=None,
    )

    provider._cache["ohio"] = TrafficData(
        state="ohio",
        events=[event_no_location],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    nearby = provider.get_events_near("ohio", 39.96, -82.99, 50.0)
    assert len(nearby) == 0


def test_state_api_config():
    """Test that state API configuration is properly defined."""
    assert "ohio" in STATE_APIS
    ohio_config = STATE_APIS["ohio"]
    assert "base_url" in ohio_config
    assert "events_endpoint" in ohio_config
    assert "name" in ohio_config
    assert ohio_config["name"] == "Ohio OHGO"


def test_retry_cooldown_after_failure():
    """Test that failed states enter retry cooldown."""
    provider = RealTrafficProvider()

    # Simulate a failed fetch by setting the cooldown directly
    provider._failed_until["ohio"] = time.time() + RETRY_AFTER_S

    # Request should return cached data and not trigger new fetch
    data = provider.request("ohio")
    assert data.source == "empty"  # No cache, so empty data

    # Verify cooldown is still active
    assert "ohio" in provider._failed_until
    assert provider._failed_until["ohio"] > time.time()


def test_cache_returned_when_fresh():
    """Test that fresh cache data is returned without new fetch."""
    provider = RealTrafficProvider()

    # Create fresh cached data
    event = TrafficEvent(
        id="cached-1",
        event_type="incident",
        severity="low",
        description="Cached event",
        county="Franklin",
    )

    provider._cache["ohio"] = TrafficData(
        state="ohio",
        events=[event],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    # Request should return cached data
    data = provider.request("ohio")
    assert len(data.events) == 1
    assert data.events[0].id == "cached-1"
    assert data.source == "test"


def test_empty_data_creation():
    """Test that empty data is created correctly for unsupported states."""
    provider = RealTrafficProvider()
    empty = provider._empty_data("unsupported")

    assert empty.state == "unsupported"
    assert empty.events == []
    assert empty.source == "empty"


# --- Trip-level incident announcements ---------------------------------------


def _incident_leg() -> Leg:
    return Leg(
        a="columbus_oh_us",
        b="cincinnati_oh_us",
        miles=100.0,
        highway="I-71",
        terrain="flat",
        stops=(),
        route_points=(
            RoutePoint(0.0, 39.9612, -82.9988),  # Columbus
            RoutePoint(50.0, 39.53, -83.65),
            RoutePoint(100.0, 39.1031, -84.5120),  # Cincinnati
        ),
        state_miles=(StateMileage(state="Ohio", miles=100.0),),
    )


def _incident_trip(provider: RealTrafficProvider) -> Trip:
    route = Route(
        cities=["columbus_oh_us", "cincinnati_oh_us"],
        legs=[_incident_leg()],
    )
    return Trip(
        route=route,
        truck=TruckState(TruckSpecs()),
        weather=WeatherSystem(),
        time_scale=1.0,
        seed=42,
        traffic_provider=provider,
    )


def _seed_ohio_cache(provider: RealTrafficProvider, *events: TrafficEvent) -> None:
    now = time.time()
    provider._cache["ohio"] = TrafficData(
        state="ohio",
        events=list(events),
        last_updated=now,
        cache_time=now,
        source="test",
    )
    # Trip construction also queries construction zones; a fresh empty entry
    # keeps these tests off the network.
    provider._cache["ohio:construction"] = TrafficData(
        state="ohio",
        events=[],
        last_updated=now,
        cache_time=now,
        source="test",
    )


def test_trip_announces_nearby_real_incident():
    """An incident near the truck's actual position is spoken once.

    Regression for the 1.9 crash: the checker called a nonexistent
    Trip._leg_at, so any drive with Traffic source set to real time died
    on the first simulation tick."""
    provider = RealTrafficProvider()
    _seed_ohio_cache(
        provider,
        TrafficEvent(
            id="inc-1",
            event_type="incident",
            severity="high",
            description="Jackknifed truck on I-71 southbound",
            county="Franklin",
            latitude=39.95,
            longitude=-83.0,
            lanes_affected="2 right lanes",
        ),
    )
    trip = _incident_trip(provider)

    trip._check_real_traffic_events()

    messages = [e.message for e in trip._events]
    assert any("Traffic alert" in m and "Jackknifed truck" in m for m in messages)
    assert any("2 right lanes affected" in m for m in messages)

    # A later check must not repeat the same incident.
    trip._next_real_traffic_check_mi = 0.0
    before = len(trip._events)
    trip._check_real_traffic_events()
    assert len(trip._events) == before


def test_trip_skips_incident_beyond_radius():
    """Incidents are filtered against the truck's position, not a fixed point.

    The truck sits at Columbus (mile 0); an incident near Cincinnati is
    about 100 miles away and must stay silent."""
    provider = RealTrafficProvider()
    _seed_ohio_cache(
        provider,
        TrafficEvent(
            id="inc-2",
            event_type="incident",
            severity="high",
            description="Bridge closure near Cincinnati",
            county="Hamilton",
            latitude=39.11,
            longitude=-84.50,
        ),
    )
    trip = _incident_trip(provider)

    trip._check_real_traffic_events()

    assert not any("Traffic alert" in e.message for e in trip._events)
