"""Driving exit, rest-stop, and lane-prep smoke tests."""

import pygame
import pytest
from driving_feature_helpers import HeldKeys, key_event, quiet_trip, start_drive


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
        driving.truck.velocity_mps = 29.0   # ~65 mph: way too fast for the ramp
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        driving._exit_lane_alignment = 1.0
        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)
        assert driving._ramp_mi is None         # blew past it
        assert driving._exit_stop is None
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_x_signals_for_upcoming_route_exit_without_taking_it(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.steering_assist = "light"
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
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
def test_x_without_route_exit_reports_no_signal_target(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.position_mi = 0.0
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
    app.ctx.settings.steering_assist = "light"
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: spoken.append(text),
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
    app.ctx.settings.steering_assist = "off"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 12.0

        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_lane_ready()
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is not None
        assert not driving._exit_signal_on

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
    app.ctx.settings.steering_assist = "off"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
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
def test_destination_exit_no_longer_requires_x_to_take_ramp(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.steering_assist = "off"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
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
def test_realistic_lane_drift_requires_signal_for_destination_exit(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.steering_assist = "light"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
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
    app.ctx.settings.steering_assist = "off"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
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
    app.ctx.settings.steering_assist = "light"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
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
    app.ctx.settings.steering_assist = "light"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
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


@pytest.mark.smoke
def test_exit_lane_can_be_set_with_keyboard_steering(monkeypatch):
    from freight_fate.app import App

    spoken = []
    sounds = []
    app = App()
    app.ctx.settings.steering_assist = "light"
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(app.ctx.audio, "play",
                        lambda key, volume=1.0, **_kw: sounds.append((key, volume)))
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
    app.ctx.settings.steering_assist = "off"
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(app.ctx.audio, "play",
                        lambda key, volume=1.0, **_kw: sounds.append((key, volume)))
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


@pytest.mark.smoke
def test_exit_lane_stays_set_after_keyboard_release():
    from freight_fate.app import App

    app = App()
    app.ctx.settings.steering_assist = "light"
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
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
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



