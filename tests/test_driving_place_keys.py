"""Alt with a number: one fact each about where the truck is.

Tim K. asked for four keystrokes that answer one question apiece -- state,
road, town, direction -- because R answers all four in one sentence and you
have to sit through the other three to hear the one you wanted.
"""

import pygame
import pytest
from driving_feature_helpers import facility_street_chain, quiet_trip, start_drive
from speech_capture import speech_stub


def alt_key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=pygame.KMOD_LALT)


def plain_key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0)


def _village(name, at_mi, off_mi):
    from freight_fate.data.world_models import Landmark

    return Landmark(
        name=name,
        at_mi=at_mi,
        category="village",
        kind="point",
        spoken=f"Passing {name}",
        off_mi=off_mi,
    )


def _set_leg_landmarks(driving, landmarks):
    """Replace the landmarks on the leg the truck is currently driving."""
    from dataclasses import replace

    trip = driving.trip
    index, _start = trip._leg_at_mile(trip.position_mi)
    legs = list(trip.route.legs)
    legs[index] = replace(legs[index], landmarks=tuple(landmarks))
    trip.route.legs = type(trip.route.legs)(legs)
    return legs[index]


@pytest.mark.smoke
def test_each_alt_number_speaks_one_place_fact(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

        driving.handle_event(alt_key(pygame.K_1))
        assert spoken[-1].startswith("In ")
        state = spoken[-1]

        driving.handle_event(alt_key(pygame.K_2))
        assert spoken[-1].startswith("On ")
        assert spoken[-1] != state

        driving.handle_event(alt_key(pygame.K_3))
        assert spoken[-1]

        driving.handle_event(alt_key(pygame.K_4))
        assert spoken[-1].endswith("bound.") or "No signed direction" in spoken[-1]

        # Four presses, four answers, and each one is a single sentence --
        # the whole point of the keys is that they are shorter than R.
        assert len(spoken) == 4
        for line in spoken:
            assert line.count(".") <= 2
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_alt_with_a_number_does_not_touch_the_engine_brake(monkeypatch):
    """The collision that made these keys unsafe before they existed.

    Alt+1 used to fall through to the jake-stage branch, so a driver asking
    what state they were in changed the engine brake instead.
    """
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say", speech_stub([]))
        driving.truck.engine_brake_stage = 3

        for key in (pygame.K_1, pygame.K_2, pygame.K_3):
            driving.handle_event(alt_key(key))
            assert driving.truck.engine_brake_stage == 3

        # Without Alt the stages still work exactly as they did.
        driving.handle_event(plain_key(pygame.K_2))
        assert driving.truck.engine_brake_stage == 2
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_town_key_names_the_town_the_truck_is_in(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

        trip = driving.trip
        index, start = trip._leg_at_mile(trip.position_mi)
        leg = trip.route.legs[index]
        forward = trip.route.cities[index] == leg.a
        offset = trip.position_mi - start
        native = offset if forward else leg.miles - offset

        # A village on the road, right where the truck is: that is the town
        # the driver is in, not one they can see.
        _set_leg_landmarks(driving, [_village("Pine", native, 0.1)])
        driving.handle_event(alt_key(pygame.K_3))
        assert spoken[-1] == "In Pine."
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_town_key_places_a_town_off_the_road(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

        trip = driving.trip
        index, start = trip._leg_at_mile(trip.position_mi)
        leg = trip.route.legs[index]
        forward = trip.route.cities[index] == leg.a
        offset = trip.position_mi - start
        native = offset if forward else leg.miles - offset

        ahead = native + 4.0 if forward else native - 4.0
        _set_leg_landmarks(driving, [_village("Fairfield", ahead, 6.3)])
        driving.handle_event(alt_key(pygame.K_3))
        said = spoken[-1]
        assert "Fairfield" in said
        assert "ahead" in said
        assert "off the road" in said
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_town_key_says_so_when_there_is_no_town(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

        _set_leg_landmarks(driving, [])
        driving.handle_event(alt_key(pygame.K_3))
        assert spoken[-1] == "No town near here."
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_place_keys_stay_honest_on_city_streets(monkeypatch):
    """A street chain has a street and a city but no shield and no heading."""
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        facility_street_chain(driving)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

        driving.handle_event(alt_key(pygame.K_4))
        assert "No signed direction here." in spoken[-1]

        driving.handle_event(alt_key(pygame.K_1))
        assert spoken[-1].startswith("In ")
        assert "None" not in spoken[-1]

        driving.handle_event(alt_key(pygame.K_3))
        assert spoken[-1].startswith("In ")
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_keypad_numbers_answer_the_same_way(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

        driving.handle_event(alt_key(pygame.K_1))
        driving.handle_event(alt_key(pygame.K_KP1))
        assert spoken[-1] == spoken[-2]
    finally:
        app.shutdown()
