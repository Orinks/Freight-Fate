"""Transcript-backed rest-stop selection and stopping-assist regressions."""

import pygame
import pytest
from driving_feature_helpers import quiet_trip, start_drive

from freight_fate.sim.trip_models import RoadStop
from freight_fate.states.driving import RestStopState


def key_event(key, *, mod=0):
    unicode = "t" if key == pygame.K_t else ""
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod, unicode=unicode)


def sleep_stop(driving, *, ahead=2.0):
    stop = RoadStop(
        "Prairie View Rest Area",
        driving.trip.position_mi + ahead,
        "public_rest_area",
        ("park", "save", "break", "sleep"),
        parking="confirmed",
        exit_label="exit 99",
    )
    driving.trip.stops = [stop]
    return stop


@pytest.fixture
def driving_app(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, **_kwargs: spoken.append(text))
    monkeypatch.setattr(app.ctx, "say_event", lambda text, **_kwargs: spoken.append(text))
    driving = start_drive(app)
    quiet_trip(driving)
    yield app, driving, spoken
    app.shutdown()


@pytest.mark.smoke
def test_rolling_t_plans_exact_sleep_stop_without_silently_selecting_exit(driving_app):
    app, driving, spoken = driving_app
    stop = sleep_stop(driving)
    driving.truck.velocity_mps = 40.0 / 2.23694

    driving.handle_event(key_event(pygame.K_t, mod=0))

    assert app.state is driving
    assert driving.trip.planned_stop_key == stop.key
    assert driving._selected_stop_key == stop.key
    assert driving._exit_stop is None
    assert not driving._exit_signal_on
    assert "Planned sleep stop selected: public rest area: Prairie View Rest Area" in spoken[-1]
    assert "Press X to signal for this exit" in spoken[-1]
    assert "Come to a complete stop first" not in spoken[-1]
    assert "Press X to signal for this exit" in driving._status_text

    driving.handle_event(key_event(pygame.K_t, mod=0))
    assert spoken[-1].startswith("Still selected: public rest area: Prairie View Rest Area")
    assert driving._selected_stop_key == stop.key


@pytest.mark.smoke
def test_selected_stop_assist_does_nothing_without_t_and_x(driving_app):
    app, driving, spoken = driving_app
    stop = sleep_stop(driving, ahead=0.2)
    app.ctx.settings.selected_stop_assist = True
    driving.truck.velocity_mps = 35.0 / 2.23694

    for _ in range(20):
        driving.update(1 / 60)

    assert app.state is driving
    assert driving.trip.planned_stop_key is None
    assert driving._selected_stop_key is None
    assert driving._exit_stop is None
    assert driving._ramp_stop is None
    assert not driving._selected_stop_assist_armed
    assert driving.truck.brake == pytest.approx(0.0)
    assert not any("stopping assistance braking" in line for line in spoken)
    assert stop.at_mi > driving.trip.position_mi


@pytest.mark.smoke
def test_x_cancel_clears_explicit_assist_but_keeps_route_plan(driving_app):
    app, driving, spoken = driving_app
    stop = sleep_stop(driving)
    app.ctx.settings.selected_stop_assist = True
    driving.truck.velocity_mps = 35.0 / 2.23694

    driving.handle_event(key_event(pygame.K_t, mod=0))
    driving.handle_event(key_event(pygame.K_x, mod=0))
    assert driving._selected_stop_assist_armed

    driving.handle_event(key_event(pygame.K_x, mod=0))

    assert not driving._exit_signal_on
    assert driving._selected_stop_key is None
    assert not driving._selected_stop_assist_armed
    assert driving.trip.planned_stop_key == stop.key
    assert "Signal canceled. Keep following the highway." in spoken[-1]
    assert "planned stop remains" in spoken[-1].lower()
    assert "stopping assistance disarmed" in spoken[-1].lower()

    driving.handle_event(key_event(pygame.K_t, mod=0))
    assert driving._selected_stop_key == stop.key
    assert "Press X to signal" in spoken[-1]
    assert "Press X to cancel" not in spoken[-1]
    driving.handle_event(key_event(pygame.K_x, mod=0))
    assert driving._exit_signal_on
    assert driving._selected_stop_assist_armed


@pytest.mark.smoke
def test_selected_stop_assist_reaches_full_stop_and_sleep_menu(monkeypatch, driving_app):
    app, driving, spoken = driving_app
    stop = sleep_stop(driving, ahead=1.0)
    app.ctx.settings.selected_stop_assist = True
    app.ctx.settings.lane_keeping = "full"
    monkeypatch.setattr("freight_fate.sim.hos.parking_is_full", lambda *_args: False)
    driving.truck.start_engine()
    driving.truck.set_air_ready(parking_brake=False)
    driving.truck.transmission.automatic = True
    driving.truck.transmission.gear = 8
    driving.truck.velocity_mps = 40.0 / 2.23694

    driving.handle_event(key_event(pygame.K_t, mod=0))
    driving.handle_event(key_event(pygame.K_x, mod=0))
    assert driving._selected_stop_assist_armed
    assert driving._exit_signal_on
    assert any("stopping assistance armed" in line for line in spoken)
    assert "stopping assistance armed" in driving._status_text

    driving.trip.position_mi = stop.at_mi
    driving.update(1 / 60)
    assert driving._ramp_stop is stop
    # Isolate the entrance stop from the independently tested light/sign flow.
    driving._ramp_control = "none"
    driving._ramp_terminal_done = True

    for _ in range(4_000):
        app.state.update(1 / 60)
        if isinstance(app.state, RestStopState):
            break
    else:
        raise AssertionError("selected-stop assistance did not open the rest menu")

    assert driving.truck.speed_mph <= 0.5
    assert driving.truck.parking_brake
    assert driving._selected_stop_key is None
    assert driving.trip.planned_stop_key is None
    assert any("stopping assistance braking" in line for line in spoken)
    assert any("Stopped at public rest area: Prairie View Rest Area" in line for line in spoken)
    assert app.state.title == "public rest area: Prairie View Rest Area"
    assert app.state.items[app.state.index].text == "Sleep 2 hours in sleeper berth"
    assert any("Sleep 2 hours in sleeper berth" in line for line in spoken)
    labels = [item.text for item in app.state.items]
    for hours in (2, 3, 7, 8):
        assert f"Sleep {hours} hours in sleeper berth" in labels
    assert "Sleep 10 hours" in labels

    selected_i = next(i for i, line in enumerate(spoken) if "Planned sleep stop selected" in line)
    armed_i = next(i for i, line in enumerate(spoken) if "stopping assistance armed" in line)
    braking_i = next(i for i, line in enumerate(spoken) if "stopping assistance braking" in line)
    stopped_i = next(i for i, line in enumerate(spoken) if "Stopped at public rest area" in line)
    menu_i = next(i for i, line in enumerate(spoken) if "Sleep 2 hours in sleeper berth" in line)
    assert selected_i < armed_i < braking_i < stopped_i < menu_i

    app.state.handle_event(key_event(pygame.K_DOWN, mod=0))
    assert app.state.items[app.state.index].text == "Sleep 3 hours in sleeper berth"
    assert "Sleep 3 hours in sleeper berth" in spoken[-1]

    app.state.handle_event(key_event(pygame.K_HOME, mod=0))
    assert app.state.items[app.state.index].text.startswith("Loyalty program")
    app.state.handle_event(key_event(pygame.K_RETURN, mod=0))
    assert app.state is not driving
    app.state.handle_event(key_event(pygame.K_ESCAPE, mod=0))
    assert isinstance(app.state, RestStopState)
    assert app.state.items[app.state.index].text.startswith("Loyalty program")
    assert "Loyalty program" in spoken[-1]

    app.state.handle_event(key_event(pygame.K_ESCAPE, mod=0))
    assert app.state is driving
    assert driving.truck.parking_brake


@pytest.mark.smoke
def test_overshoot_clears_assist_then_stopped_t_recovers(driving_app):
    app, driving, spoken = driving_app
    stop = sleep_stop(driving, ahead=1.0)
    app.ctx.settings.selected_stop_assist = True
    driving.truck.velocity_mps = 35.0 / 2.23694
    driving.handle_event(key_event(pygame.K_t, mod=0))
    driving.handle_event(key_event(pygame.K_x, mod=0))
    assert driving._selected_stop_assist_armed

    driving._ramp_stop = stop
    driving._ramp_mi = -0.6
    driving._ramp_terminal_done = True
    driving._ramp_end_said = True
    driving._ramp_arrival_grace_s = 0.0
    driving.truck.velocity_mps = 10.0 / 2.23694
    driving._update_exit(0.0)

    assert driving._ramp_stop is None
    assert driving._selected_stop_key is None
    assert not driving._selected_stop_assist_armed
    assert driving.trip.planned_stop_key is None
    assert driving.truck.brake == pytest.approx(0.0)
    assert any("never stopped" in line.lower() for line in spoken)
    assert any("Continue safely" in line for line in spoken)

    driving.trip.position_mi = stop.at_mi + 0.7
    driving.truck.velocity_mps = 0.0
    driving.handle_event(key_event(pygame.K_t, mod=0))
    assert isinstance(app.state, RestStopState)


@pytest.mark.smoke
def test_rolling_t_without_sleep_stop_gives_recovery_guidance(driving_app):
    app, driving, spoken = driving_app
    driving.trip.stops = []
    driving.truck.velocity_mps = 30.0 / 2.23694

    driving.handle_event(key_event(pygame.K_t, mod=0))

    assert app.state is driving
    assert driving._selected_stop_key is None
    assert "No sleep-capable route stop is ahead on this route" in spoken[-1]
    assert "driving status menu" in spoken[-1]


def test_unselected_stop_passes_without_braking_or_menu(driving_app):
    app, driving, spoken = driving_app
    stop = sleep_stop(driving, ahead=0.01)
    app.ctx.settings.selected_stop_assist = True
    driving.truck.velocity_mps = 35.0 / 2.23694

    driving.trip.position_mi = stop.at_mi + 0.2
    driving.update(1 / 60)

    assert app.state is driving
    assert driving.truck.brake == pytest.approx(0.0)
    assert driving._ramp_stop is None
    assert not any("stopping assistance braking" in line for line in spoken)


def test_selected_stop_outranks_unsignaled_destination_exit(driving_app):
    _app, driving, spoken = driving_app
    stop = sleep_stop(driving, ahead=1.0)
    destination = RoadStop(
        "Warehouse",
        stop.at_mi + 0.1,
        "delivery_destination",
        ("deliver",),
        parking="confirmed",
        exit_label="exit 100",
    )
    driving.trip.stops.append(destination)
    driving._exit_stop = destination
    driving.truck.velocity_mps = 35.0 / 2.23694

    driving.handle_event(key_event(pygame.K_t, mod=0))
    driving.handle_event(key_event(pygame.K_x, mod=0))

    assert driving._exit_stop is stop
    assert driving._exit_signal_on
    assert "Prairie View Rest Area" in spoken[-1]
    assert "Warehouse" not in spoken[-1]


def test_t_during_police_stop_names_the_trooper_action(driving_app):
    _app, driving, spoken = driving_app
    sleep_stop(driving)
    driving._pull_over = "lights"
    driving.truck.velocity_mps = 35.0 / 2.23694

    driving.handle_event(key_event(pygame.K_t, mod=0))

    assert driving._selected_stop_key is None
    assert "Resolve the police stop" in spoken[-1]
    assert "Press X to signal the trooper stop" in spoken[-1]


def test_t_on_selected_ramp_reports_live_assist_state(driving_app):
    app, driving, spoken = driving_app
    stop = sleep_stop(driving)
    app.ctx.settings.selected_stop_assist = True
    driving._selected_stop_key = stop.key
    driving._selected_stop_assist_armed = True
    driving._ramp_stop = stop
    driving._ramp_mi = 0.4
    driving.truck.velocity_mps = 20.0 / 2.23694

    driving.handle_event(key_event(pygame.K_t, mod=0))

    assert "On the selected ramp" in spoken[-1]
    assert "assistance is armed" in spoken[-1]
    assert "behind you" not in spoken[-1]

    driving.ctx.settings.selected_stop_assist = False
    driving.handle_event(key_event(pygame.K_t, mod=0))
    assert "assistance is off" in spoken[-1]
    assert "will stop" not in spoken[-1]


def test_controller_rest_planning_names_controller_exit_control(monkeypatch, driving_app):
    _app, driving, spoken = driving_app
    sleep_stop(driving)
    driving.truck.velocity_mps = 35.0 / 2.23694
    original = driving.ctx.control_hint
    monkeypatch.setattr(
        driving.ctx,
        "control_hint",
        lambda action: {
            "rest": "right bumper plus D-pad down",
            "take_exit": "D-pad down",
            "status_menu": "right bumper plus Start",
        }.get(action, original(action)),
    )

    driving._try_rest_stop()

    assert "Press D-pad down to signal" in spoken[-1]
    assert "Press X" not in spoken[-1]


@pytest.mark.smoke
def test_t_plans_a_sleep_stop_well_beyond_the_exit_window(driving_app):
    """Owner, Hanging Lake, 2026-08-22: T seven miles out answered "no
    sleep-capable route stop is close enough ahead to plan", and worked a
    minute later with nothing changed but the odometer. Planning was bounded
    by the exit window -- the five-odd miles inside which an exit can be
    SIGNALLED -- which has nothing to do with deciding where to sleep.

    T plans the next sleep-capable stop however far ahead it is. Inside the
    window it says press X; beyond it, it says you will be told when the
    exit comes up, because X does nothing out there yet."""
    app, driving, spoken = driving_app
    stop = sleep_stop(driving, ahead=20.0)
    assert driving._exit_window_mi() < 20.0
    driving.truck.velocity_mps = 60.0 / 2.23694

    driving.handle_event(key_event(pygame.K_t, mod=0))

    assert driving.trip.planned_stop_key == stop.key
    assert driving._selected_stop_key == stop.key
    assert "Planned sleep stop selected: public rest area: Prairie View Rest Area" in spoken[-1]
    assert "20 miles ahead" in spoken[-1] or "20.0 miles ahead" in spoken[-1]
    assert "You will be told when its exit comes up; press X to signal then." in spoken[-1]
    assert "Press X to signal for this exit." not in spoken[-1]
    # Nothing is armed or signalled by the plan itself.
    assert driving._exit_stop is None
    assert not driving._exit_signal_on
