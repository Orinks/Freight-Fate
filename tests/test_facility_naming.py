"""R6: facilities are named in full on first mention, short on repeats, and
never with a type prefix the proper name already carries."""

from freight_fate.speech_text import type_prefix_is_redundant, typed_name


def test_a_redundant_type_prefix_is_dropped():
    assert type_prefix_is_redundant("cross-dock", "Chicago Cross-Dock")
    assert type_prefix_is_redundant("port", "Port of Indiana-Burns Harbor")
    assert type_prefix_is_redundant("travel center", "Flying J Travel Center Corfu")
    assert typed_name("cross-dock", "Chicago Cross-Dock", sep=": ") == "Chicago Cross-Dock"


def test_a_prefix_the_name_does_not_carry_survives():
    assert not type_prefix_is_redundant("travel center", "Love's")
    assert not type_prefix_is_redundant("service plaza", "Petro Stopping Centers")
    # A short label must not fire on a coincidental substring.
    assert not type_prefix_is_redundant("port", "Newport Terminal")
    assert typed_name("travel center", "Love's") == "travel center Love's"


def test_the_road_stop_name_drops_the_redundant_prefix():
    from freight_fate.sim.trip_models import RoadStop

    stop = RoadStop(at_mi=10.0, name="Flying J Travel Center Corfu", type="travel_center")
    assert stop.spoken_name == "Flying J Travel Center Corfu"

    plain = RoadStop(at_mi=10.0, name="Love's", type="travel_center")
    assert plain.spoken_name == "travel center: Love's"


def test_first_mention_is_full_then_short_and_resets():
    from freight_fate.sim.trip import Trip

    # A bare object is enough to exercise the register directly.
    trip = Trip.__new__(Trip)
    trip._facilities_named = set()

    assert trip.name_facility(
        "Petro Stopping Centers", "service plaza: Petro Stopping Centers"
    ) == ("service plaza: Petro Stopping Centers")
    # Repeat within the leg: the proper name alone.
    assert (
        trip.name_facility("Petro Stopping Centers", "service plaza: Petro Stopping Centers")
        == "Petro Stopping Centers"
    )
    # A reset (new leg, or resume from a pause) brings the full form back once.
    trip.reset_facility_mentions()
    assert trip.name_facility(
        "Petro Stopping Centers", "service plaza: Petro Stopping Centers"
    ) == ("service plaza: Petro Stopping Centers")
