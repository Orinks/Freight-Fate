"""Brand-derived truck-stop amenities: classification and spoken surfacing."""

from freight_fate.data.amenities import (
    SIGNATURE_SERVICE_LABELS,
    classify_brand,
    signature_services,
    spoken_amenities,
)

# Real-world stop names as the map's truck-stop sweep would store them, paired
# with the brand key and the signature service the player learns to seek there.
BRANDED_STOPS = [
    ("Love's Travel Stop #472", "loves", "tires"),
    ("Speedco Lube and Tire", "speedco", "tires"),
    ("Pilot Travel Center", "pilot", "showers"),
    ("Flying J Travel Center", "flying_j", "showers"),
    ("TA Travel Center", "ta", "repair"),
    ("TravelCenters of America", "ta", "repair"),
    ("Petro Stopping Center", "petro", "repair"),
]


def test_classify_known_brands():
    for name, key, _ in BRANDED_STOPS:
        brand = classify_brand(name)
        assert brand is not None, name
        assert brand.key == key, name


def test_signature_service_is_the_differentiator():
    for name, _, service in BRANDED_STOPS:
        assert service in signature_services(name), name


def test_generic_stop_has_no_brand():
    assert classify_brand("Interstate 40 corridor rest area") is None
    assert classify_brand("Downtown Fuel Mart") is None
    assert signature_services("Municipal Truck Parking") == ()
    assert spoken_amenities("Municipal Truck Parking") == ""


def test_spoken_amenities_reads_cleanly():
    text = spoken_amenities("Love's Travel Stop #472")
    assert "Love's" in text
    assert "tire care and quick lube" in text
    # Player-facing speech: no raw map tags, codes, or stray markers.
    for marker in ("amenity=", "osm", "node/", "_", "#"):
        assert marker not in text


def test_big_bucks_landmark_announces_the_big_rig_ban():
    text = spoken_amenities("Big Buck's Travel Center")
    brand = classify_brand("Big Buck's Travel Center")
    assert brand is not None and brand.tier == "landmark"
    assert brand.bans_big_rigs
    assert "landmark" in text
    assert "big rigs" in text and "bobtail" in text


def test_real_bucees_name_classifies_as_the_landmark():
    # The sweep excludes Buc-ee's from truck stops, but if a landmark stop is
    # ever placed, the parody brand must own the no-big-rigs gag.
    for name in ("Buc-ee's", "Bucees", "Buckee's Beaver Stop"):
        brand = classify_brand(name)
        assert brand is not None and brand.key == "big_bucks", name


def test_every_signature_key_has_a_spoken_label():
    from freight_fate.data.amenities import BRANDS

    for brand in BRANDS:
        for key in brand.signature:
            assert key in SIGNATURE_SERVICE_LABELS, key


def test_new_amenities_have_spoken_labels():
    """Test that new realistic amenities have proper spoken labels."""
    new_amenities = [
        "cat_scale",
        "laundry",
        "game_room",
        "barber",
        "premium_wifi",
        "check_cashing",
        "def",
        "atm",
    ]
    for amenity in new_amenities:
        assert amenity in SIGNATURE_SERVICE_LABELS, f"Missing label for {amenity}"
        # Ensure labels are screen-reader friendly (no abbreviations that get spelled out)
        label = SIGNATURE_SERVICE_LABELS[amenity]
        # Cat is a brand name and should be preserved as-is
        if amenity == "cat_scale":
            assert "Cat" in label or "CAT" in label, "Cat brand name should be preserved"
        # Wi-Fi should be readable (WiFi, Wi-Fi, or wifi are all acceptable)
        if amenity == "premium_wifi":
            assert "Wi-Fi" in label or "WiFi" in label or "wifi" in label, (
                "Wi-Fi should be readable"
            )


def test_pilot_has_enhanced_amenities():
    """Test that Pilot centers now have more realistic amenities."""
    pilot = classify_brand("Pilot Travel Center")
    assert pilot is not None
    assert "showers" in pilot.signature
    assert "cat_scale" in pilot.signature
    assert "laundry" in pilot.signature
    assert "premium_wifi" in pilot.signature


def test_flying_j_has_enhanced_amenities():
    """Test that Flying J centers now have more realistic amenities."""
    flying_j = classify_brand("Flying J Travel Center")
    assert flying_j is not None
    assert "showers" in flying_j.signature
    assert "cat_scale" in flying_j.signature
    assert "laundry" in flying_j.signature
    assert "premium_wifi" in flying_j.signature
    assert "game_room" in flying_j.signature


def test_poi_offers_text_surfaces_brand_specialty():
    # Integration: the driving route-info menu speaks each stop through this.
    from freight_fate.sim.trip_models import RoadStop
    from freight_fate.states.driving_core import _poi_offers_text

    stop = RoadStop(
        name="Love's Travel Stop #472",
        at_mi=42.0,
        type="travel_center",
        actions=("fuel", "food", "park"),
        services=("diesel", "food", "parking"),
        parking="confirmed",
    )
    text = _poi_offers_text(stop)
    assert "listed services" in text
    assert "Love's specialty: tire care and quick lube" in text

    generic = RoadStop(name="Downtown Fuel Mart", at_mi=10.0, services=("diesel",))
    assert "specialty" not in _poi_offers_text(generic)
