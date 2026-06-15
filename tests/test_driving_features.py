"""Highway exits and cruise control, end to end through the driving state."""

import pygame
import pytest


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def start_drive(app):
    """New career, accept an unlocked job, pick a route; returns DrivingState."""
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.main_menu import MainMenuState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # default name
    app.state.handle_event(key_event(pygame.K_RETURN))  # default home terminal
    app.state.handle_event(key_event(pygame.K_RETURN))  # job board
    board = app.state
    while board.jobs[board.index].cargo.endorsement:  # skip locked teasers
        board.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # accept job
    app.state.handle_event(key_event(pygame.K_RETURN))  # check in at origin
    app.state.handle_event(key_event(pygame.K_RETURN))  # load at dock
    app.state.handle_event(key_event(pygame.K_RETURN))  # plan destination route
    app.state.handle_event(key_event(pygame.K_RETURN))  # pick route
    assert isinstance(app.state, DrivingState)
    return app.state


def quiet_trip(driving):
    """Push random hazards and inspections beyond this test's horizon."""
    driving.trip._hazard_check_mi = 1e9
    driving.trip._inspection_check_mi = 1e9


def test_driving_f1_describes_safe_shutdown_and_destination_parking(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)

        driving.handle_event(key_event(pygame.K_F1))

        help_text = spoken[-1]
        assert "stops it only below 5 miles per hour" in help_text
        assert "dock and deliver from the facility menu" in help_text
    finally:
        app.shutdown()


def test_how_to_play_documents_new_gameplay_systems():
    from freight_fate.states.main_menu import HELP_PAGES

    help_text = " ".join(line for _title, lines in HELP_PAGES for line in lines).lower()

    assert "slow below 5 miles per hour" in help_text
    assert "destination facility" in help_text
    assert "check in at the origin facility" in help_text
    assert "loading requires a full stop" in help_text
    assert "loaded and sealed" in help_text
    assert "dock and deliver" in help_text
    assert "ports" in help_text
    assert "intermodal yards" in help_text
    assert "food terminals" in help_text
    assert "refrigerated, heavy-haul, and high-value freight" in help_text
    assert "full tank or full repair" in help_text


# -- highway exits -------------------------------------------------------------


@pytest.mark.smoke
def test_engine_shutdown_is_blocked_at_highway_speed(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.handle_event(key_event(pygame.K_e))
        assert driving.truck.engine_on
        driving.truck.velocity_mps = 31.3

        driving.handle_event(key_event(pygame.K_e))

        assert driving.truck.engine_on
        assert "Unsafe to shut the engine off" in spoken[-1]
        assert "70 miles per hour" in spoken[-1]
        assert "shutdown blocked" in driving.lines()[-1]
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_engine_shutdown_is_allowed_once_stopped():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.handle_event(key_event(pygame.K_e))
        assert driving.truck.engine_on
        driving.truck.velocity_mps = 0.0
        driving.handle_event(key_event(pygame.K_e))
        assert not driving.truck.engine_on
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_delivery_requires_parking_at_destination(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import ArrivalState, DrivingState, FacilityArrivalState

    app = App()
    events = []
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event",
                        lambda text, interrupt=True: events.append(text))
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.finished = True
        driving.trip.position_mi = driving.trip.total_miles
        driving.truck.velocity_mps = 26.8

        driving.update(1 / 60)

        assert isinstance(app.state, DrivingState)
        assert "Destination facility ahead" in events[-1]
        assert "full stop to open the facility menu" in events[-1]
        assert "slow down and park" in driving.lines()[-1]

        driving.truck.velocity_mps = 0.0
        driving.update(1 / 60)

        assert isinstance(app.state, FacilityArrivalState)
        assert app.state.items[app.state.index].text == "Dock and deliver"
        assert "Docking required before delivery settlement." in app.state.lines()
        assert app.ctx.profile.career.deliveries == 0

        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, ArrivalState)
        assert any("Trailer secured and paperwork signed" in text for text in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_facility_menu_waits_for_full_stop(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState, FacilityArrivalState

    app = App()
    events = []
    played = []
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event",
                        lambda text, interrupt=True: events.append(text))
    monkeypatch.setattr(app.ctx, "say",
                        lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(app.ctx.audio, "play",
                        lambda key, volume=1.0: played.append((key, volume)))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken.clear()
        played.clear()
        driving.trip.finished = True
        driving.trip.position_mi = driving.trip.total_miles
        driving.truck.velocity_mps = 1.1   # about 2.5 mph: parked, not docked

        driving.update(1 / 60)
        assert isinstance(app.state, DrivingState)
        assert app.ctx.profile.career.deliveries == 0
        assert "facility menu opens when stopped" in events[-1]
        assert "full stop to dock" in driving.lines()[-1]
        assert played[-1][0] == "ui/notify"

        driving.truck.velocity_mps = 0.0
        driving.update(1 / 60)

        assert isinstance(app.state, FacilityArrivalState)
        assert played[-1][0] == "facility/dock_gate"
        assert all(key != "ui/menu_open" for key, _volume in played)
        assert [item.text for item in app.state.items] == [
            "Dock and deliver", "Check paperwork", "Check arrival status"]

        app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, FacilityArrivalState)
        assert app.ctx.profile.career.deliveries == 0
        assert "Paperwork for" in spoken[-1]
        assert "current estimated payout" in spoken[-1]
        assert "hours remain before the deadline" in spoken[-1]
        assert "Cargo condition" in spoken[-1]
        assert "does not settle the load" in spoken[-1]

        app.state.handle_event(key_event(pygame.K_UP))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert not isinstance(app.state, FacilityArrivalState)
        assert app.ctx.profile.career.deliveries == 1
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_flow_reaches_the_rest_stop_menu():
    from freight_fate.app import App
    from freight_fate.states.driving import ParkingFullState, RestStopState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 2.0
        driving.truck.velocity_mps = 15.0   # ~34 mph: slow enough for the ramp
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop

        driving.trip.position_mi = stop.at_mi   # reach the exit point
        driving.update(1 / 60)
        assert driving._ramp_mi is not None     # on the ramp
        assert driving._exit_stop is None

        driving._ramp_mi = 0.0                  # end of the ramp...
        driving.truck.velocity_mps = 0.0        # ...braked to a stop
        driving.update(1 / 60)
        assert isinstance(app.state, (RestStopState, ParkingFullState))
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_missed_when_too_fast():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 29.0   # ~65 mph: way too fast for the ramp
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)
        assert driving._ramp_mi is None         # blew past it
        assert driving._exit_stop is None
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_key_is_a_toggle_and_needs_an_exit_nearby():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        # far from any stop: X does not arm
        driving.trip.position_mi = 0.0
        if driving.trip.stops[0].at_mi > 6.0:
            driving.handle_event(key_event(pygame.K_x))
            assert driving._exit_stop is None
        # in range it arms; pressing X again cancels
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 2.0
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is None
    finally:
        app.shutdown()


# -- cruise control -------------------------------------------------------------


@pytest.mark.smoke
def test_cruise_control_holds_the_set_speed():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))   # engine on
        t.transmission.gear = 10
        t.velocity_mps = 26.8                          # ~60 mph
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph == pytest.approx(60.0, abs=1.0)
        for _ in range(60 * 15):                       # 15 seconds, no keys held
            driving.update(1 / 60)
        assert driving._cruise_mph is not None
        assert abs(t.speed_mph - 60.0) < 5.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_automatic_shift_uses_shift_cue_not_brake_air(monkeypatch):
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    app = App()
    played = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())
        monkeypatch.setattr(app.ctx.audio, "play",
                            lambda key, volume=1.0: played.append((key, volume)))
        driving.truck.start_engine()
        driving.truck.transmission.gear = 3
        driving.truck.velocity_mps = 5.0

        driving.update(0.0)

        assert ("vehicle/gear_shift", 0.65) in played
        assert all(key != "vehicle/brake_air" for key, _volume in played)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_cruise_control_requires_road_speed_and_cancels_on_hazard():
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        # parked: refuses to engage
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is None
        # engaged at speed, a hazard hands control back to the driver
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None
        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 4.0})
        driving._handle_trip_event(hazard)
        assert driving._cruise_mph is None
    finally:
        app.shutdown()


# -- hazard reaction windows ---------------------------------------------------


def clear_weather(driving):
    """Pin the trip's weather to clear so grip stays 1.0 for the whole test."""
    from freight_fate.sim.weather import WeatherKind

    weather = driving.trip.weather
    weather.provider = None
    weather.live = False
    weather.current = WeatherKind.CLEAR
    weather.minutes_until_change = 1e9


@pytest.mark.smoke
def test_hazard_deadline_covers_braking_time_from_current_speed():
    """A fixed 3-4.5 s window was unbeatable at highway speed: a full-service
    stop from 65 to 25 mph alone takes ~5 s. The deadline must be the braking
    time from the current speed plus the rolled reaction slack."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import HAZARD_SAFE_MPH, MPH_PER_MPS, G

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        t.velocity_mps = 29.0          # ~65 mph
        t.grip, t.grade = 1.0, 0.0
        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 3.0})
        driving._handle_trip_event(hazard)
        brake_s = ((t.speed_mph - HAZARD_SAFE_MPH) / MPH_PER_MPS
                   / (G * t.specs.max_brake_decel_g))
        assert driving._hazard_deadline == pytest.approx(brake_s + 3.0, abs=0.01)
        assert driving._hazard_deadline > 7.5
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_service_brakes_beat_a_highway_hazard_after_human_reaction(monkeypatch):
    """The taught response -- hear the warning, hold Down -- must succeed from
    highway speed even with a slow human reaction, without the emergency brake."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        clear_weather(driving)
        t = driving.truck
        t.transmission.gear = 10
        t.velocity_mps = 29.0          # ~65 mph
        damage_before = t.damage_pct

        held = set()

        class FakeKeys:
            def __getitem__(self, key):
                return key in held

        monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys())

        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 3.0})
        driving._handle_trip_event(hazard)
        for _ in range(int(60 * 1.5)):      # hearing the warning: no input yet
            driving.update(1 / 60)
        held.add(pygame.K_DOWN)             # then service brakes only
        for _ in range(60 * 20):
            driving.update(1 / 60)
            if driving._hazard_deadline is None:
                break
        assert driving._hazard_deadline is None
        assert t.damage_pct == damage_before    # avoided, not collided
    finally:
        app.shutdown()
