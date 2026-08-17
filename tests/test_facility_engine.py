"""Shutting the engine down while parked at a pickup or delivery facility.

The kill switch has always existed on the road, but a facility arrival takes
the truck over at half a mile an hour and hands straight to a menu, so the one
moment a driver actually reaches for it -- sitting at the shipper waiting to be
loaded -- was the one moment the game did not offer it. Idling through that
wait now costs fuel, which is what makes the switch worth reaching for.
"""

import pygame
from speech_capture import speech_stub
from test_pickup_loading import (
    accept_pickup_drive,
    arrive_at_pickup,
    finish_timed_state,
    key_event,
)

SHUT_DOWN = "Shut down the engine"
START = "Start the engine"


def item_labels(menu):
    return [item.text for item in menu.items]


def choose(menu, label):
    """Select a named item, failing loudly rather than arrowing forever.

    ``test_pickup_loading.select_item`` spins if the label is absent, and the
    primary row is worded per job (a drop-and-hook yard has no dock to load
    at), so every named selection here has to assert first.
    """
    assert label in item_labels(menu), f"{label!r} not in {item_labels(menu)}"
    while menu.items[menu.index].text != label:
        menu.handle_event(key_event(pygame.K_DOWN))
    menu.handle_event(key_event(pygame.K_RETURN))


def choose_primary(app):
    """Take whatever the facility's first row is: load, or drop and hook."""
    state = app.state
    while state.index:
        state.handle_event(key_event(pygame.K_UP))
    state.handle_event(key_event(pygame.K_RETURN))


def arrive_running(app):
    """Reach the pickup facility with the engine idling, as a drive-in does."""
    pickup_drive = accept_pickup_drive(app)
    pickup_drive.truck.start_engine()
    pickup = arrive_at_pickup(app)
    assert pickup.truck.engine_on
    return pickup


def load_out(app, pickup):
    """Check in and get the freight on, whichever way this facility does it."""
    choose_primary(app)  # check in at the shipping office
    choose_primary(app)  # load at the dock, or drop and hook in the yard
    finish_timed_state(app)
    assert app.state.loaded


def reach_destination_facility(app, pickup):
    from freight_fate.states.driving import FacilityArrivalState

    load_out(app, pickup)
    choose(app.state, "Depart for destination")

    driving = app.state
    driving.trip.position_mi = driving.trip.total_miles
    driving.trip.finished = True
    driving._destination_exit_taken = True
    driving.truck.velocity_mps = 0.0
    driving._handle_arrival_gate()
    finish_timed_state(app)
    assert isinstance(app.state, FacilityArrivalState)
    return app.state


def test_pickup_facility_offers_shutdown_and_then_restart():
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        pickup = arrive_running(app)
        assert SHUT_DOWN in item_labels(pickup)

        choose(pickup, SHUT_DOWN)
        assert not pickup.truck.engine_on
        assert "Engine off." in spoken[-1]

        # One row that changes face, not two: a screen reader user arrows past
        # a single engine line either way.
        assert SHUT_DOWN not in item_labels(pickup)
        assert START in item_labels(pickup)

        choose(pickup, START)
        assert pickup.truck.engine_on
        assert "Engine running." in spoken[-1]
        assert SHUT_DOWN in item_labels(pickup)
    finally:
        app.shutdown()


def test_the_primary_action_stays_the_first_item():
    from freight_fate.app import App

    app = App()
    try:
        pickup = arrive_running(app)
        # Enter on arrival must still check in. The engine row sits with the
        # other truck actions, never in front of the flow the facility is for.
        first = pickup.items[0].text
        assert first == "Check in at shipping office"
        choose(pickup, SHUT_DOWN)
        assert pickup.items[0].text == first
    finally:
        app.shutdown()


def test_engine_off_at_the_pickup_survives_save_and_quit():
    from freight_fate.app import App
    from freight_fate.states.city import PickupFacilityState

    app = App()
    try:
        pickup = arrive_running(app)
        choose(pickup, SHUT_DOWN)
        assert app.ctx.profile.active_trip["engine_on"] is False

        choose(pickup, "Save and quit to main menu")
        while not app.state.items[app.state.index].text.startswith("Continue latest career"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, PickupFacilityState)
        assert not app.state.truck.engine_on
        assert START in item_labels(app.state)
    finally:
        app.shutdown()


def test_loading_still_works_with_the_engine_shut_down():
    from freight_fate.app import App

    app = App()
    try:
        pickup = arrive_running(app)
        choose(pickup, SHUT_DOWN)
        load_out(app, pickup)
        assert not app.state.truck.engine_on
    finally:
        app.shutdown()


def test_idling_through_the_load_burns_fuel_and_shutting_down_does_not():
    """Jake's point: an hour on the dock has to cost something, or the switch
    is decoration."""
    from freight_fate.app import App

    idled = App()
    try:
        pickup = arrive_running(idled)
        before = pickup.truck.fuel_gal
        load_out(idled, pickup)
        burned_idling = before - idled.state.truck.fuel_gal
    finally:
        idled.shutdown()

    shut = App()
    try:
        pickup = arrive_running(shut)
        before = pickup.truck.fuel_gal
        choose(pickup, SHUT_DOWN)
        load_out(shut, pickup)
        burned_shut_down = before - shut.state.truck.fuel_gal
    finally:
        shut.shutdown()

    # Check-in plus loading is over an hour of engine time at roughly
    # 0.8 gallons an hour.
    assert burned_idling > 0.3
    assert burned_shut_down == 0.0


def test_the_load_report_names_the_fuel_burned_idling():
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        pickup = arrive_running(app)
        load_out(app, pickup)
        loaded_line = spoken[-1]
        assert "idling" in loaded_line.lower()
        assert "gallon" in loaded_line.lower()
    finally:
        app.shutdown()


def test_a_shut_down_load_says_nothing_about_fuel():
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        pickup = arrive_running(app)
        choose(pickup, SHUT_DOWN)
        load_out(app, pickup)
        assert "idling" not in spoken[-1].lower()
    finally:
        app.shutdown()


def test_departing_with_the_engine_off_names_the_start_control():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        pickup = arrive_running(app)
        load_out(app, pickup)
        choose(app.state, SHUT_DOWN)
        choose(app.state, "Depart for destination")

        assert isinstance(app.state, DrivingState)
        assert not app.state.truck.engine_on
        # The first-run tutorial and any achievement speak after departure, so
        # find the departure line rather than trusting the last thing said.
        departure = next(line for line in spoken if "Loaded trip is" in line)
        # Never "Departing now" over a dead engine, and the key named is the
        # one this driver's settings actually bind.
        assert "Departing now" not in departure
        assert app.ctx.control_hint("engine") in departure
    finally:
        app.shutdown()


def test_departing_with_the_engine_running_still_just_departs():
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        pickup = arrive_running(app)
        load_out(app, pickup)
        choose(app.state, "Depart for destination")

        assert app.state.truck.engine_on
        departure = next(line for line in spoken if "Loaded trip is" in line)
        assert "Departing now" in departure
    finally:
        app.shutdown()


def test_pickup_status_and_screen_report_the_engine():
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        pickup = arrive_running(app)
        choose(pickup, "Pickup status")
        assert "engine running" in spoken[-1].lower()
        assert any("Engine: running" in line for line in pickup.lines())

        choose(pickup, SHUT_DOWN)
        choose(pickup, "Pickup status")
        assert "engine off" in spoken[-1].lower()
        assert any("Engine: off" in line for line in pickup.lines())
    finally:
        app.shutdown()


def test_destination_facility_offers_the_same_shutdown():
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        pickup = arrive_running(app)
        arrival = reach_destination_facility(app, pickup)

        assert arrival.items[0].text in (
            "Dock and deliver",
            "Drop the loaded trailer and hook an empty",
        )
        assert SHUT_DOWN in item_labels(arrival)

        choose(arrival, SHUT_DOWN)
        assert not arrival.driving.truck.engine_on
        assert "Engine off." in spoken[-1]
        assert START in item_labels(arrival)
    finally:
        app.shutdown()


def test_unloading_burns_fuel_only_while_the_engine_runs():
    from freight_fate.app import App
    from freight_fate.states.driving import ArrivalState

    app = App()
    try:
        pickup = arrive_running(app)
        arrival = reach_destination_facility(app, pickup)
        truck = arrival.driving.truck
        truck.start_engine()
        before = truck.fuel_gal
        choose(arrival, SHUT_DOWN)
        choose_primary(app)  # dock and deliver, or drop the loaded trailer
        finish_timed_state(app)
        assert isinstance(app.state, ArrivalState)
        assert truck.fuel_gal == before
    finally:
        app.shutdown()
