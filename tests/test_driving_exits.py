"""Driving exit, rest-stop, and lane-prep smoke tests."""

import pygame
import pytest
from driving_feature_helpers import HeldKeys, key_event, quiet_trip, start_drive
from speech_capture import speech_stub


@pytest.mark.smoke
def test_can_back_up_to_a_missed_rest_stop_with_t_menu():
    from freight_fate.app import App
    from freight_fate.states.driving import ParkingFullState, RestStopState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi + 0.7
        driving.truck.velocity_mps = -1.0

        driving.trip.update(60)
        driving.truck.velocity_mps = 0.0
        assert abs(driving.trip.position_mi - stop.at_mi) <= 1.5

        driving.handle_event(key_event(pygame.K_t))

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
        driving.truck.velocity_mps = 29.0  # ~65 mph: way too fast for the ramp
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        driving._exit_lane_alignment = 1.0
        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)
        assert driving._ramp_mi is None  # blew past it
        assert driving._exit_stop is None
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_x_signals_for_upcoming_route_exit_without_taking_it(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "partial"
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.5

        driving.handle_event(key_event(pygame.K_x))

        assert driving._exit_stop is not None
        assert driving._exit_stop.type == "delivery_destination"
        assert driving._exit_signal_on
        assert any("Signal on" in line for line in spoken)

        driving.handle_event(key_event(pygame.K_x))

        assert driving._exit_stop is not None
        assert not driving._exit_signal_on
        assert any("Signal canceled" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_x_near_the_exit_keeps_the_signal_until_a_second_press(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "off"
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.5
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_signal_on

        # Inside the guard mile a stray press keeps the signal and says so;
        # a playtested X meant as "confirm" must not throw the exit away.
        driving.trip.position_mi = stop.at_mi - 0.5
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_signal_on
        assert any("Signal stays on" in line for line in spoken)
        assert not any("Signal canceled" in line for line in spoken)

        # A deliberate second press still cancels.
        driving.handle_event(key_event(pygame.K_x))
        assert not driving._exit_signal_on
        assert any("Signal canceled" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_right_taps_with_drift_on_earn_the_hold_hint_once(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "off"
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.5
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_signal_on
        spoken.clear()

        held = HeldKeys(pygame.K_RIGHT)
        released = HeldKeys()
        for _ in range(2):
            driving._update_exit_preparation(held, 1 / 60)
            driving._update_exit_preparation(released, 1 / 60)
        assert len([line for line in spoken if "Hold Right to steer" in line]) == 1

        # Further taps stay quiet: the hint speaks once per approach.
        driving._update_exit_preparation(held, 1 / 60)
        driving._update_exit_preparation(released, 1 / 60)
        assert len([line for line in spoken if "Hold Right to steer" in line]) == 1

        # Actually holding Right still builds the exit lane past the hint.
        for _ in range(180):
            driving._update_exit_preparation(held, 1 / 60)
        assert driving._exit_lane_ready()
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_missed_destination_exit_reroutes_every_time(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "off"
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None

        # Missing the destination exit twice must loop back both times; the
        # say-once latch used to swallow the second reposition and strand the
        # trip pinned at the end of the route with no exit left to signal for.
        for _ in range(2):
            driving.trip.position_mi = driving.trip.total_miles
            driving.trip.finished = True
            driving.truck.velocity_mps = 20.0
            driving.update(1 / 60)
            assert not driving.trip.finished
            assert driving.trip.position_mi < stop.at_mi

        assert len([s for s in spoken if "missed the destination exit" in s]) == 2

        # The re-approach leaves the full exit window: a real exit to signal
        # for, far enough out to hear, arm, and brake under time compression.
        assert stop.at_mi - driving.trip.position_mi >= 5.0
        driving.trip.position_mi = stop.at_mi - 1.5
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_signal_on
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_x_without_route_exit_reports_no_signal_target(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.position_mi = 0.0
        # The randomly assigned route may open with a truck stop inside the
        # signal window (a real Ubuntu CI draw had one at mile 1.0); clear
        # the en-route stops so "no exit target" is a property of the test,
        # not of the draw. The destination exit stays far beyond the window.
        driving.trip.stops = []
        assert driving._upcoming_exit_stop() is None

        driving.handle_event(key_event(pygame.K_x))

        assert not driving._exit_signal_on
        assert any("No route exit to signal for yet" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_canceled_exit_signal_does_not_prompt_lane_prep(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "partial"
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        speech_stub(spoken),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 1.5

        driving.handle_event(key_event(pygame.K_x))
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        assert not driving._exit_signal_on

        spoken.clear()
        driving._update_exit_preparation(HeldKeys(pygame.K_RIGHT), 1.5)

        assert all("Signal is on" not in line for line in spoken)
        assert all("Exit lane set" not in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_canceled_destination_exit_signal_stays_on_highway(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "full"
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 12.0

        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_lane_ready()
        # Inside the guard mile, canceling deliberately takes two presses;
        # the first keeps the signal so a stray X cannot throw the exit away.
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_signal_on
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is not None
        assert not driving._exit_signal_on
        assert not driving._exit_intent_ready(stop)

        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)

        assert driving._ramp_mi is None
        assert any("signal" in line.casefold() for line in spoken)
        assert any("stayed on the highway" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_destination_exit_auto_arms_and_takes_ramp_with_valid_setup(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "full"
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 15.0

        driving.update(1 / 60)
        assert driving._exit_stop is not None
        assert driving._exit_stop.type == "delivery_destination"

        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)

        assert driving._ramp_mi == pytest.approx(0.5)
        assert driving._destination_exit_taken
        assert any("You take" in line and "destination exit" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_full_lane_keeping_says_it_is_taking_the_destination_exit(monkeypatch):
    """The reported bug: exits took themselves with nothing said. Full lane
    keeping is allowed to take them; it is not allowed to be silent about it."""
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "full"
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 15.0
        driving.update(1 / 60)
        assert any("Lane keeping will take this exit" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_destination_exit_auto_grant_follows_full_lane_keeping(monkeypatch):
    """The auto-grant is keyed on the mode, not on the old string. Under
    partial or off the destination exit needs the signal like any other."""
    from freight_fate.app import App

    for mode, expected in (("full", True), ("partial", False), ("off", False)):
        app = App()
        app.ctx.settings.lane_keeping = mode
        monkeypatch.setattr(app.ctx, "say_event", speech_stub([]))
        try:
            driving = start_drive(app)
            quiet_trip(driving)
            stop = driving._destination_exit_stop()
            assert stop is not None
            assert driving._exit_intent_ready(stop) is expected
        finally:
            app.shutdown()


@pytest.mark.smoke
def test_destination_exit_no_longer_requires_x_to_take_ramp(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "full"
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 0.5
        driving.truck.velocity_mps = 12.0

        driving.update(1 / 60)
        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)

        assert driving._ramp_mi == pytest.approx(0.5)
        assert all("Press X to take" not in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
@pytest.mark.parametrize("lane_keeping", ("partial", "off"))
def test_manual_lane_keeping_requires_signal_for_destination_exit(monkeypatch, lane_keeping):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = lane_keeping
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 12.0
        driving._exit_lane_alignment = 1.0
        driving.update(1 / 60)

        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)

        assert driving._ramp_mi is None
        assert any("signal was not set" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_relaxed_lane_drift_infers_destination_exit_intent(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "full"
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 12.0
        driving.update(1 / 60)

        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)

        assert driving._ramp_mi == pytest.approx(0.5)
        assert any("You take" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_requires_right_lane_alignment(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "partial"
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        app.ctx.settings.lane_keeping = "partial"
        driving.trip.traffic_pressures = []
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 15.0
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)
        assert driving._ramp_mi is None
        assert driving._exit_stop is None
        assert any("not in the exit lane" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_traffic_pressure_changes_missed_lane_recovery(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TrafficPressure

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "partial"
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        app.ctx.settings.lane_keeping = "partial"
        stop = driving.trip.stops[0]
        driving.trip.traffic_pressures = [
            TrafficPressure(
                stop.at_mi - 2.0,
                stop.at_mi + 0.4,
                "exit",
                "right",
                0.75,
                42.0,
                "exit traffic for test ramp",
            )
        ]
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 15.0
        driving.handle_event(key_event(pygame.K_x))
        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)
        assert driving._ramp_mi is None
        assert any("Traffic boxed you out of the exit lane" in line for line in spoken)
        assert any("recover at the next safe exit" in line for line in spoken)
    finally:
        app.shutdown()


def _pressure_speech(driving, spoken):
    """Everything a pressure got to say -- spoken now or queued to speak.

    Traffic pressures are ambient events, and an ambient event either speaks
    at once or waits its turn in the ambient queue; both count as reaching
    the driver.
    """
    return list(spoken) + [p.message for p in driving._pending_ambient_events]


def _pressure_event(driving, pressure, ahead=1.0):
    """The GPS cue the trip emits for a pressure, built by the trip itself.

    Handed straight to the driving state rather than waited for over frames:
    a live tick also carries stop callouts and CB chatter that share the
    ambient slot, and which of them lands first is not what these tests are
    about.
    """
    from freight_fate.sim.trip import TripEvent, TripEventKind

    return TripEvent(
        TripEventKind.GPS_CUE,
        driving.trip._traffic_pressure_message(pressure, ahead),
        {"traffic_pressure": pressure},
    )


def _exit_pressure_run(app):
    """A drive with an exit-traffic pressure over the next route exit."""
    from freight_fate.sim.trip import TrafficPressure

    driving = start_drive(app)
    quiet_trip(driving)
    stop = driving.trip.stops[0]
    pressure = TrafficPressure(
        stop.at_mi - 2.0,
        stop.at_mi + 0.4,
        "exit",
        "right",
        0.75,
        42.0,
        f"exit traffic for {stop.spoken_name}",
    )
    driving.trip.traffic_pressures = [pressure]
    driving.trip._announced_traffic_pressures.clear()
    driving.trip.position_mi = stop.at_mi - 3.0
    driving.truck.velocity_mps = 25.0
    driving._pending_ambient_events.clear()
    driving._ambient_event_cooldown_s = 0.0
    return driving, stop, pressure


def test_exit_traffic_stays_quiet_for_an_exit_you_are_not_taking(monkeypatch):
    """Owner, 2026-08-15: the game announced the traffic at every exit coming
    up, none of them the driver's. Every route stop grows an exit-traffic
    pressure, so a corridor thick with truck stops narrated one after another.
    Un-signalled, the advisory says nothing at all."""
    from freight_fate.app import App

    spoken = []
    app = App()
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        driving, stop, pressure = _exit_pressure_run(app)
        assert not driving._exit_signal_on

        driving._handle_trip_event(_pressure_event(driving, pressure))

        assert not any("Exit traffic" in line for line in _pressure_speech(driving, spoken))

        # Marked announced by the trip all the same, so arming the exit late
        # cannot dump a stale advisory afterwards.
        driving.trip._check_traffic_pressures()
        assert driving.trip._announced_traffic_pressures
    finally:
        app.shutdown()


def test_exit_traffic_still_speaks_once_you_signal_for_that_exit(monkeypatch):
    """Signal first and the full advisory arrives in time to be useful."""
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.lane_keeping = "partial"
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        driving, stop, pressure = _exit_pressure_run(app)
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        assert driving._exit_signal_on
        spoken.clear()
        driving._pending_ambient_events.clear()
        driving._ambient_event_cooldown_s = 0.0

        driving._handle_trip_event(_pressure_event(driving, pressure))

        heard = _pressure_speech(driving, spoken)
        assert any("Exit traffic building" in line for line in heard), heard
        assert any("hold the right exit lane" in line for line in heard), heard
    finally:
        app.shutdown()


def test_merging_and_construction_pressures_still_speak_unsignalled(monkeypatch):
    """Only the exit ones are gated. A merge warns about the road the truck is
    already on, not a turn-off it is free to ignore."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TrafficPressure

    spoken = []
    app = App()
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        at = driving.trip.position_mi + 1.6
        for kind, direction, phrase in (
            ("route_merge", "right", "Merging traffic in"),
            ("construction_merge", "left", "Traffic squeezing at the construction taper"),
            ("traffic_pack", "right", "Traffic pack in"),
        ):
            spoken.clear()
            driving._pending_ambient_events.clear()
            driving._ambient_event_cooldown_s = 0.0
            pressure = TrafficPressure(at, at + 0.6, kind, direction, 0.75, 42.0, "test pressure")
            driving._handle_trip_event(_pressure_event(driving, pressure))
            heard = _pressure_speech(driving, spoken)
            assert any(phrase in line for line in heard), (kind, heard)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_lane_can_be_set_with_keyboard_steering(monkeypatch):
    from freight_fate.app import App

    spoken = []
    sounds = []
    app = App()
    app.ctx.settings.lane_keeping = "partial"
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(
        app.ctx.audio, "play", lambda key, volume=1.0, **_kw: sounds.append((key, volume))
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 1.5
        driving.handle_event(key_event(pygame.K_x))
        for _ in range(80):
            driving._update_exit_preparation(HeldKeys(pygame.K_RIGHT), 1 / 60)
        assert driving._exit_lane_ready()
        assert any("Exit lane set" in line for line in spoken)
        assert ("ui/notify", 0.6) in sounds
    finally:
        app.shutdown()


def test_lane_drift_off_sets_exit_lane_when_signaling(monkeypatch):
    from freight_fate.app import App

    spoken = []
    sounds = []
    app = App()
    app.ctx.settings.lane_keeping = "full"
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(
        app.ctx.audio, "play", lambda key, volume=1.0, **_kw: sounds.append((key, volume))
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 1.5

        driving.handle_event(key_event(pygame.K_x))

        assert driving._exit_lane_ready()
        assert any("Exit lane set" in line for line in spoken)
        assert all("Move right" not in line for line in spoken)
        assert ("ui/notify", 0.6) in sounds
    finally:
        app.shutdown()


def test_exit_speed_assist_slows_with_full_lane_keeping(monkeypatch):
    """Regression: the assist sat below the lane-work early return, so it
    never ran with lane keeping on full -- and the All assists preset selects
    full, silently disabling an assist it had just turned on."""
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.apply_driving_assistance_preset("all")
    assert app.ctx.settings.lane_keeping == "full"
    assert app.ctx.settings.exit_speed_assist is True
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 29.0  # ~65 mph, well over ramp speed
        driving.handle_event(key_event(pygame.K_x))
        driving._update_exit_preparation(HeldKeys(), 1 / 60)
        assert driving.truck.brake >= 0.35
        slowing = [line for line in spoken if "Exit speed assistance slowing" in line]
        assert slowing
        # Never name a key this driver does not have: with lane keeping on
        # full a tap changes lanes, and holding Right does nothing.
        assert "Tap Right" in slowing[-1]
        assert "Hold Right" not in slowing[-1]
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_lane_stays_set_after_keyboard_release():
    from freight_fate.app import App

    app = App()
    app.ctx.settings.lane_keeping = "partial"
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 1.5
        driving.handle_event(key_event(pygame.K_x))
        for _ in range(80):
            driving._update_exit_preparation(HeldKeys(pygame.K_RIGHT), 1 / 60)
        assert driving._exit_lane_ready()
        for _ in range(60 * 20):
            driving._update_exit_preparation(HeldKeys(), 1 / 60)
        assert driving._exit_lane_ready()
        driving._update_exit_preparation(HeldKeys(pygame.K_LEFT), 1.5)
        assert not driving._exit_lane_ready()
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_missed_after_gore_window(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 10.0
        driving.handle_event(key_event(pygame.K_x))
        driving._exit_lane_alignment = 1.0
        driving.trip.position_mi = stop.at_mi + 0.6
        driving.update(1 / 60)
        assert driving._ramp_mi is None
        assert driving._exit_stop is None
        assert any("missed the exit window" in line for line in spoken)
    finally:
        app.shutdown()


def test_destination_exit_scan_stays_on_the_final_approach():
    """Routes that finish on rural highways carry no baked interchanges, and
    the scan used to crown the last labeled exit anywhere on the route as the
    destination exit: player transcripts (2026-07-16) show a Lampasas run
    settled from Wichita Falls, 224 miles out, and a Havre, Montana run
    settled from I-39 in Wisconsin, 1,158 miles out. The scan must find an
    exit on the final approach or report none, so the synthetic end-of-route
    exit takes over."""
    from types import SimpleNamespace

    from freight_fate.data.world import get_world
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.driving_core import DESTINATION_EXIT_SCAN_WINDOW_MI

    world = get_world()
    for start, end in [
        ("springfield_il_us", "lampasas_tx_us"),
        ("jamestown_ny_us", "havre_mt_us"),
    ]:
        route = world.shortest_route(start, end, require_metadata=True)
        assert route is not None
        leg_starts: list[float] = []
        total = 0.0
        for leg in route.legs:
            leg_starts.append(total)
            total += leg.miles
        driving = SimpleNamespace(
            route=route,
            trip=SimpleNamespace(_leg_starts=leg_starts, position_mi=0.0, total_miles=total),
            ctx=SimpleNamespace(world=world),
        )
        details = DrivingState._scan_destination_exit_details(driving)
        if details is not None:
            assert details[0] >= total - DESTINATION_EXIT_SCAN_WINDOW_MI


def test_the_exit_speed_assist_runs_when_lane_keeping_takes_the_exit():
    """Owner playtest, Denver->Silverthorne, 2026-08-19: "why did all assists
    not stop at my destination exit?"

    Because the assist was gated on ``_exit_signal_on``, and the signal is
    how a DRIVER commits to an exit. With lane keeping automated they never
    press it -- the game itself says "lane keeping will take this exit" -- so
    the gate switched the assist off for precisely the preset that promises
    the most help. His transcript:

        In 5 miles, exit 209, destination exit. Lane keeping will take this
        exit. Adaptive cruise will ease to 40 miles per hour for the ramp.
        ...
        53 miles per hour ... adaptive cruise set at 53 miles per hour
        You were going too fast for the ramp and missed exit 209.

    Automated lane keeping IS the commitment, so it arms the assist the same
    way a signal does.
    """
    import inspect

    from freight_fate.states.driving_events import DrivingEventMixin

    src = inspect.getsource(DrivingEventMixin._update_exit_preparation)
    assert "lane_is_automated()" in src, "the assist is still signal-only"
    committed = src.split("committed =", 1)[1].split("\n", 1)[0]
    assert "_exit_signal_on" in committed and "lane_is_automated" in committed


def test_a_fresh_cruise_session_inherits_an_armed_exit_s_ramp_cap():
    """The other half of the same miss, and either alone was enough.

    Cancelling cruise clears ``_cruise_exit_mph``. On the Denver run the
    descent cancelled it about a mile from the ramp, the driver re-engaged at
    53, and the new session had forgotten the exit -- its own line said
    "adaptive cruise set at 53 miles per hour" with no "for the ramp" note,
    which is the tell. The cap belongs to the road ahead, not to whichever
    cruise session happened to be running when the exit was announced.
    """
    import inspect

    from freight_fate.states.driving_events import DrivingEventMixin

    src = inspect.getsource(DrivingEventMixin._engage_cruise)
    assert "_cruise_exit_mph" in src, "engaging cruise ignores an armed exit"
    assert "RAMP_CRUISE_TARGET_MPH" in src


def test_the_destination_approach_assist_actually_brings_the_truck_to_a_stop():
    """Owner, Odessa, 2026-08-19: "I did, and it's wrong. Never stopped."

    Simulated rather than inspected, because inspection is what let this
    through twice. The first version only ran inside ``if trip.finished`` --
    true once the truck is already AT the point -- so it could hold a stopped
    truck and nothing else. The second gated on
    ``_is_facility_approach_route``, which asks "is this route a same-city
    street chain to a gate": False for an ordinary city-to-city delivery, so
    it never ran on the deliveries it exists for and the owner went past the
    market at 38 mph.

    A fixed brake pressure then overshot the profile -- 0.4 on a loaded rig
    is about 1.5 m/s^2 against the 0.9 the curve is drawn for -- and parked
    the truck 143 feet short, where the cap no longer binds and the assist
    lets go. Stopping short and sitting there is its own failure.
    """
    from freight_fate.sim.vehicle import TruckState
    from freight_fate.states.driving_updates import DrivingUpdateMixin

    class _Trip:
        finished = False

        def __init__(self, remaining):
            self.remaining_miles = remaining

        def _is_facility_approach_route(self):
            return False  # an ordinary delivery, not a same-city street chain

    class _Ctx:
        class settings:
            destination_approach_assist = True

    class _Driving:
        _cruise_mph = None
        _keeper_mph = None
        _destination_exit_taken = True

        def __init__(self, truck, trip):
            self.truck, self.trip, self.ctx = truck, trip, _Ctx()

        def _pause_speed_control(self, **kwargs):
            pass

    for start_mph in (25.0, 38.0, 50.0):
        truck = TruckState()
        truck.velocity_mps = start_mph / 2.23694
        trip = _Trip(0.40)
        driving = _Driving(truck, trip)
        for _ in range(6000):
            truck.throttle = 0.0  # hands off: the assist is the only input
            DrivingUpdateMixin._update_destination_approach_assist(driving)
            truck.update(1 / 60)
            trip.remaining_miles -= abs(truck.velocity_mps) / 60 / 1609.344
            if truck.speed_mph <= 0.5 or trip.remaining_miles < -0.02:
                break
        feet = trip.remaining_miles * 5280.0
        assert truck.speed_mph <= 0.5, f"from {start_mph:.0f} mph it never stopped"
        assert -60.0 < feet < 60.0, (
            f"from {start_mph:.0f} mph it stopped {feet:+.0f} ft from the gate"
        )
