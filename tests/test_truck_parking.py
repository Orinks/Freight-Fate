"""Truck parking availability via TPIMS."""

import time

from freight_fate.sim.truck_parking import (
    CACHE_TTL_S,
    RETRY_AFTER_S,
    STALE_AFTER_S,
    TPIMS_APIS,
    ParkingData,
    TruckParkingLocation,
    TruckParkingProvider,
)


def test_truck_parking_location_serialization():
    """Test that parking locations can be serialized and deserialized."""
    location = TruckParkingLocation(
        id="parking-123",
        name="I-70 Rest Area",
        location="I-70 mile marker 45",
        address="1234 Highway 70",
        capacity=50,
        available=20,
        latitude=39.96,
        longitude=-82.99,
        open=True,
    )

    data = location.to_dict()
    assert data["id"] == "parking-123"
    assert data["name"] == "I-70 Rest Area"
    assert data["capacity"] == 50
    assert data["available"] == 20

    restored = TruckParkingLocation.from_dict(data)
    assert restored is not None
    assert restored.id == "parking-123"
    assert restored.capacity == 50
    assert restored.available == 20


def test_truck_parking_location_from_invalid_dict():
    """Test that invalid data returns None."""
    assert TruckParkingLocation.from_dict({}) is None
    assert TruckParkingLocation.from_dict(None) is None
    assert TruckParkingLocation.from_dict([]) is None


def test_occupancy_percentage_calculation():
    """Test occupancy percentage calculation."""
    location = TruckParkingLocation(
        id="test-1",
        name="Test Location",
        location="Test Road",
        capacity=100,
        available=25,
    )

    assert location.occupancy_percentage == 75.0


def test_occupancy_percentage_without_capacity():
    """Test occupancy without capacity returns None."""
    location = TruckParkingLocation(
        id="test-1", name="Test Location", location="Test Road", capacity=None, available=10
    )

    assert location.occupancy_percentage is None


def test_availability_status_full():
    """Test availability status for full location."""
    location = TruckParkingLocation(
        id="test-1", name="Test Location", location="Test Road", capacity=50, available=0
    )

    assert location.availability_status == "full"


def test_availability_status_almost_full():
    """Test availability status for almost full location."""
    location = TruckParkingLocation(
        id="test-1", name="Test Location", location="Test Road", capacity=100, available=5
    )

    assert location.availability_status == "almost_full"


def test_availability_status_mostly_full():
    """Test availability status for mostly full location."""
    location = TruckParkingLocation(
        id="test-1", name="Test Location", location="Test Road", capacity=100, available=20
    )

    assert location.availability_status == "mostly_full"


def test_availability_status_available():
    """Test availability status for available location."""
    location = TruckParkingLocation(
        id="test-1", name="Test Location", location="Test Road", capacity=100, available=50
    )

    assert location.availability_status == "available"


def test_availability_status_closed():
    """Test availability status for closed location."""
    location = TruckParkingLocation(
        id="test-1",
        name="Test Location",
        location="Test Road",
        capacity=50,
        available=25,
        open=False,
    )

    assert location.availability_status == "closed"


def test_availability_status_unknown():
    """Test availability status when availability is unknown."""
    location = TruckParkingLocation(
        id="test-1", name="Test Location", location="Test Road", capacity=50, available=None
    )

    assert location.availability_status == "unknown"


def test_parking_data_freshness():
    """Test cache freshness calculations."""
    data = ParkingData(
        state="ohio",
        locations=[],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    assert data.is_fresh()
    assert not data.is_stale()

    # Simulate old data
    old_data = ParkingData(
        state="ohio",
        locations=[],
        last_updated=time.time() - CACHE_TTL_S - 1,
        cache_time=time.time() - CACHE_TTL_S - 1,
        source="test",
    )

    assert not old_data.is_fresh()
    assert not old_data.is_stale()  # Not yet stale

    # Simulate stale data
    stale_data = ParkingData(
        state="ohio",
        locations=[],
        last_updated=time.time() - STALE_AFTER_S - 1,
        cache_time=time.time() - STALE_AFTER_S - 1,
        source="test",
    )

    assert not stale_data.is_fresh()
    assert stale_data.is_stale()


def test_parking_data_serialization():
    """Test that parking data can be serialized."""
    location = TruckParkingLocation(
        id="test-123",
        name="Test Parking",
        location="I-70",
        capacity=50,
        available=20,
    )

    data = ParkingData(
        state="ohio",
        locations=[location],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    serialized = data.to_dict()
    assert serialized["state"] == "ohio"
    assert len(serialized["locations"]) == 1
    assert serialized["locations"][0]["id"] == "test-123"


def test_provider_initialization():
    """Test that provider initializes with empty cache."""
    provider = TruckParkingProvider()
    assert provider._cache == {}
    assert provider._failed_until == {}
    assert provider._locks == {}


def test_provider_unsupported_state():
    """Test that unsupported states return empty data."""
    provider = TruckParkingProvider()
    data = provider.request("california")

    assert data.state == "california"
    assert data.locations == []
    assert data.source == "unsupported"


def test_provider_supported_state_returns_empty_initially():
    """Test that supported states return empty data on first request."""
    provider = TruckParkingProvider()
    data = provider.request("ohio")

    assert data.state == "ohio"
    assert data.locations == []
    assert data.source == "empty"


def test_get_locations_near_filters_by_distance():
    """Test that nearby locations are filtered by distance."""
    provider = TruckParkingProvider()

    # Create test locations
    location_near = TruckParkingLocation(
        id="near-1",
        name="Nearby Parking",
        location="I-70",
        capacity=50,
        available=20,
        latitude=40.0,
        longitude=-83.0,
    )

    location_far = TruckParkingLocation(
        id="far-1",
        name="Far Parking",
        location="I-90",
        capacity=30,
        available=10,
        latitude=41.5,
        longitude=-81.7,
    )

    # Mock cache with test data
    provider._cache["ohio"] = ParkingData(
        state="ohio",
        locations=[location_near, location_far],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    # Search for locations within 50 miles of Columbus
    nearby = provider.get_locations_near("ohio", 39.96, -82.99, 50.0)

    # Should only include the nearby location
    assert len(nearby) == 1
    assert nearby[0].id == "near-1"


def test_get_available_locations_near_filters_availability():
    """Test that only available locations are returned."""
    provider = TruckParkingProvider()

    # Create test locations with different availability
    location_available = TruckParkingLocation(
        id="avail-1",
        name="Available Parking",
        location="I-70",
        capacity=50,
        available=20,
        latitude=40.0,
        longitude=-83.0,
        open=True,
    )

    location_full = TruckParkingLocation(
        id="full-1",
        name="Full Parking",
        location="I-70",
        capacity=30,
        available=0,
        latitude=40.1,
        longitude=-83.0,
        open=True,
    )

    location_closed = TruckParkingLocation(
        id="closed-1",
        name="Closed Parking",
        location="I-70",
        capacity=40,
        available=10,
        latitude=40.2,
        longitude=-83.0,
        open=False,
    )

    provider._cache["ohio"] = ParkingData(
        state="ohio",
        locations=[location_available, location_full, location_closed],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    # Search for available locations
    available = provider.get_available_locations_near("ohio", 39.96, -82.99, 50.0)

    # Should only include the available location
    assert len(available) == 1
    assert available[0].id == "avail-1"


def test_get_locations_near_excludes_locations_without_location():
    """Test that locations without coordinates are excluded."""
    provider = TruckParkingProvider()

    location_no_location = TruckParkingLocation(
        id="no-loc-1",
        name="Parking without location",
        location="Unknown",
        capacity=50,
        available=20,
        latitude=None,
        longitude=None,
    )

    provider._cache["ohio"] = ParkingData(
        state="ohio",
        locations=[location_no_location],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    nearby = provider.get_locations_near("ohio", 39.96, -82.99, 50.0)
    assert len(nearby) == 0


def test_haversine_distance():
    """Test distance calculation between two points."""
    provider = TruckParkingProvider()

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
    provider = TruckParkingProvider()
    distance = provider._haversine_distance(40.0, -83.0, 40.0, -83.0)
    assert distance == 0.0


def test_tpims_api_config():
    """Test that TPIMS API configuration is properly defined."""
    assert "ohio" in TPIMS_APIS
    ohio_config = TPIMS_APIS["ohio"]
    assert "base_url" in ohio_config
    assert "parking_endpoint" in ohio_config
    assert "name" in ohio_config
    assert ohio_config["name"] == "Ohio OHGO TPIMS"
    # OHGO's keyless API is gone (checked 2026-08-09), so Ohio never fetches
    assert ohio_config["parser"] == "no_api"


def test_wisconsin_tpims_config():
    """Wisconsin joined TPIMS 2026-08-09 with the two-endpoint 511wi.gov join."""
    config = TPIMS_APIS["wisconsin"]
    assert config["parser"] == "wi511"
    assert config["parking_endpoint"] == "/List/GetData/truckparking"
    assert config["icons_endpoint"] == "/map/mapIcons/TruckParking"


def test_no_api_state_serves_fresh_cache_without_fetching():
    """no_api states never fetch but still serve a fresh cache entry."""
    provider = TruckParkingProvider()
    now = time.time()
    location = TruckParkingLocation(id="seed-1", name="Seeded", location="I-70")
    provider._cache["ohio"] = ParkingData(
        state="ohio", locations=[location], last_updated=now, cache_time=now, source="test"
    )
    assert provider.request("ohio").locations[0].id == "seed-1"

    fresh_provider = TruckParkingProvider()
    data = fresh_provider.request("ohio")
    assert data.locations == []
    assert data.source == "empty"
    assert fresh_provider._failed_until == {}


# Trimmed real responses recorded 2026-08-09 from 511wi.gov:
# POST /List/GetData/truckparking (site names and live counts) and
# GET /map/mapIcons/TruckParking (coordinates keyed by the same site ids).
WI511_LIST_DATA = {
    "draw": 1,
    "recordsTotal": 13,
    "recordsFiltered": 13,
    "data": [
        {
            "DT_RowId": "1",
            "tooltipUrl": "/tooltip/TruckParking/1?lang=%7Blang%7D&noCss=true",
            "lastUpdated": "8/9/26, 11:00 AM",
            "organization": "WI-TPIMS",
            "name": "Portage Rest Area #11",
            "pageName": "Columbia County, WI",
            "roadway": "I-39/90/94 EB",
            "exit": "",
            "availableParkingSpaces": 68,
            "totalParkingSpaces": 68,
            "trend": "CLEARING",
            "trustData": "Yes",
            "open": "Yes",
        },
        {
            "DT_RowId": "2",
            "lastUpdated": "8/9/26, 11:00 AM",
            "organization": "WI-TPIMS",
            "name": "Millston Rest Area #22",
            "roadway": "I-94 EB",
            "availableParkingSpaces": 0,
            "totalParkingSpaces": 35,
            "open": "No",
        },
    ],
}

WI511_ICONS_DATA = {
    "item1": {"size": [29, 35], "origin": [0, 0], "anchor": [14, 34]},
    "item2": [
        {
            "itemId": "1",
            "location": [43.428772, -89.483492],
            "icon": {"url": "/Generated/Content/Images/511/map_truckParking.svg"},
            "title": "",
        },
        {
            "itemId": "2",
            "location": [44.225922, -90.707871],
            "icon": {"url": "/Generated/Content/Images/511/map_truckParking.svg"},
            "title": "",
        },
    ],
}


def test_parse_wi511_locations_joins_counts_and_coordinates():
    """The WI parser joins list rows with map icon coordinates by site id."""
    provider = TruckParkingProvider()
    locations = provider._parse_wi511_locations(WI511_LIST_DATA, WI511_ICONS_DATA)
    assert len(locations) == 2

    portage = locations[0]
    assert portage.id == "1"
    assert portage.name == "Portage Rest Area #11"
    assert portage.location == "I-39/90/94 EB"
    assert portage.capacity == 68
    assert portage.available == 68
    assert portage.latitude == 43.428772
    assert portage.longitude == -89.483492
    assert portage.open is True
    assert portage.last_reported == "8/9/26, 11:00 AM"
    assert portage.availability_status == "available"

    millston = locations[1]
    assert millston.available == 0
    assert millston.open is False
    assert millston.availability_status == "closed"


def test_parse_wi511_locations_without_matching_icon():
    """A list row with no map icon still parses, just without coordinates."""
    provider = TruckParkingProvider()
    icons = {"item1": {}, "item2": []}
    locations = provider._parse_wi511_locations(WI511_LIST_DATA, icons)
    assert len(locations) == 2
    assert locations[0].latitude is None
    assert locations[0].longitude is None


def test_parse_wi511_locations_malformed_data():
    """Malformed WI responses return no locations instead of raising."""
    provider = TruckParkingProvider()
    assert provider._parse_wi511_locations({}, {}) == []
    assert provider._parse_wi511_locations({"data": None}, {"item2": None}) == []
    assert provider._parse_wi511_locations({"data": [None, {}]}, WI511_ICONS_DATA) == []


def test_retry_cooldown_after_failure():
    """Test that failed states enter retry cooldown."""
    provider = TruckParkingProvider()

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
    provider = TruckParkingProvider()

    # Create fresh cached data
    location = TruckParkingLocation(
        id="cached-1",
        name="Cached Parking",
        location="I-70",
        capacity=50,
        available=20,
    )

    provider._cache["ohio"] = ParkingData(
        state="ohio",
        locations=[location],
        last_updated=time.time(),
        cache_time=time.time(),
        source="test",
    )

    # Request should return cached data
    data = provider.request("ohio")
    assert len(data.locations) == 1
    assert data.locations[0].id == "cached-1"
    assert data.source == "test"


def test_empty_data_creation():
    """Test that empty data is created correctly for unsupported states."""
    provider = TruckParkingProvider()
    empty = provider._empty_data("unsupported")

    assert empty.state == "unsupported"
    assert empty.locations == []
    assert empty.source == "empty"


def test_location_from_dict_with_id_only():
    """Test that location can be created with minimal valid data."""
    location = TruckParkingLocation.from_dict({"id": "test-123"})
    assert location is not None
    assert location.id == "test-123"
    assert location.name == ""
    assert location.capacity is None
    assert location.available is None
