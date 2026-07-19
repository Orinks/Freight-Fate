"""Stop details screen, ETA-to-stop with HOS context, and planned stops."""

import pygame
from driving_feature_helpers import key_event

from freight_fate.sim.trip_models import RoadStop


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Planner", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles,
        1000.0,
        12.0,
        destination_location="Rochester freight market",
    )
    return DrivingState(app.ctx, job, route, phase="delivery")


def _stops(position_mi):
    return [
        RoadStop(
            "Willow Creek Travel Center",
            position_mi + 3.0,
            actions=("fuel", "break"),
            services=("diesel", "food"),
            parking="confirmed",
            exit_label="exit 12",
        ),
        RoadStop(
            "Cedar Rapids Rest Area",
            position_mi + 20.0,
            type="rest_area",
            actions=("break",),
            parking="limited",
        ),
    ]


def test_enter_on_map_stop_opens_structured_detail_view():
    from freight_fate.app import App
    from freight_fate.states.driving_menu_states import DrivingStatusScreenState
    from freight_fate.states.driving_stop_detail import StopDetailState

    app = App()
    try:
        d = _driving(app)
        d.trip.stops = _stops(d.trip.position_mi)
        stop = d.trip.stops[0]
        screen = DrivingStatusScreenState(app.ctx, d, "map")
        app.push_state(screen)

        while not screen.items[screen.index].text.startswith("Stop in"):
            screen.index += 1
        screen.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, StopDetailState)
        texts = [item.text for item in app.state.items]
        joined = " ".join(texts)
        assert texts[0] == f"Stop: {stop.spoken_name}."
        assert "Exit: exit 12." in texts
        assert "Distance:" in joined
        assert "Offers: fuel, and 30-minute rest break." in texts
        assert "Listed services: diesel, and food." in texts
        assert "Parking: confirmed truck parking." in texts
        # The ETA line sits below the services and distance lines.
        eta_index = next(i for i, t in enumerate(texts) if t.startswith("Estimated time"))
        assert eta_index > texts.index("Listed services: diesel, and food.")
        assert texts[-2] == f"Plan to stop at {stop.name}"
        assert texts[-1] == "Back"
    finally:
        app.shutdown()


def test_eta_line_mirrors_eld_pace_rules():
    from freight_fate.app import App
    from freight_fate.states.driving_stop_detail import StopDetailState

    app = App()
    try:
        d = _driving(app)
        far = RoadStop("Far Travel Center", d.trip.position_mi + 110.0, actions=("break",))
        d.trip.stops = [far]
        state = StopDetailState(app.ctx, d, far)

        d.truck.velocity_mps = 0.0  # parked -> typical highway pace at 55
        line = state._eta_line(110.0)
        assert "at a typical highway pace" in line
        assert f"{110.0 / 55.0:.1f} hours" in line

        d.truck.velocity_mps = 60.0 / 2.23694  # rolling -> your actual speed
        line = state._eta_line(110.0)
        assert "at your current speed" in line
        assert f"{110.0 / d.truck.speed_mph:.1f} hours" in line
    finally:
        app.shutdown()


def test_arrival_note_names_only_the_limit_that_matters():
    from freight_fate.sim.hos import HosClock

    clock = HosClock()
    # Fresh clock: the 8-hour break is the nearest limit.
    assert "break is due" in clock.arrival_note("realistic", 60.0)
    # Arriving after the nearest limit warns instead.
    late = clock.arrival_note("realistic", 10 * 60.0)
    assert "before you would reach it" in late
    assert "break" in late
    # Duty window closing before the break drops the break entirely.
    clock.duty_min = 13.5 * 60.0
    note = clock.arrival_note("realistic", 15.0)
    assert "duty window closes" in note
    assert "break" not in note
    # Non-enforced modes stay quiet.
    assert HosClock().arrival_note("off", 60.0) == ""


def test_plan_cancel_and_supersede():
    from freight_fate.app import App
    from freight_fate.states.driving_menu_states import DrivingStatusScreenState
    from freight_fate.states.driving_stop_detail import StopDetailState

    app = App()
    try:
        d = _driving(app)
        d.trip.stops = _stops(d.trip.position_mi)
        first, second = d.trip.stops

        detail = StopDetailState(app.ctx, d, first)
        app.push_state(detail)
        plan = next(i for i in detail.items if i.text == f"Plan to stop at {first.name}")
        plan.action()
        assert d.trip.planned_stop_name == first.name
        texts = [i.text for i in detail.items]
        assert f"Cancel planned stop at {first.name}" in texts
        assert f"Plan to stop at {first.name}" not in texts

        # A different stop's details offer only plan-here, never cancel-the-other.
        other = StopDetailState(app.ctx, d, second)
        app.push_state(other)
        texts = [i.text for i in other.items]
        assert f"Plan to stop at {second.name}" in texts
        assert not any(t.startswith("Cancel planned stop") for t in texts)

        # Planning the second stop while the first is planned confirms the move
        # rather than switching silently.
        from freight_fate.states.driving_stop_detail import ConfirmMovePlanState

        next(i for i in other.items if i.text == f"Plan to stop at {second.name}").action()
        assert isinstance(app.state, ConfirmMovePlanState)
        assert d.trip.planned_stop_name == first.name  # unchanged until confirmed
        confirm = app.state
        yes = next(i for i in confirm.items if i.text.startswith("Yes,"))
        assert confirm.items.index(yes) == 0  # lands on Yes
        yes.action()
        assert d.trip.planned_stop_name == second.name  # moved after confirming
        assert app.state is other  # back on the second stop's details

        # The Map screen carries a standalone cancel button while a plan exists.
        screen = DrivingStatusScreenState(app.ctx, d, "map")
        app.push_state(screen)
        cancel = next(i for i in screen.items if i.text == f"Cancel planned stop at {second.name}")
        cancel.action()
        assert d.trip.planned_stop_name is None
        assert not any(i.text.startswith("Cancel planned stop") for i in screen.items)
    finally:
        app.shutdown()


def test_cancel_button_only_on_the_planned_stops_details():
    from freight_fate.app import App
    from freight_fate.states.driving_stop_detail import ConfirmMovePlanState, StopDetailState

    app = App()
    try:
        d = _driving(app)
        d.trip.stops = _stops(d.trip.position_mi)
        planned, other = d.trip.stops
        d.trip.planned_stop_name = planned.name

        # The planned stop's own details offer Cancel and no Plan.
        own = StopDetailState(app.ctx, d, planned)
        own_texts = [i.text for i in own.build_items()]
        assert f"Cancel planned stop at {planned.name}" in own_texts
        assert not any(t.startswith("Plan to stop") for t in own_texts)

        # Every other stop offers Plan and never a cancel button.
        elsewhere = StopDetailState(app.ctx, d, other)
        else_texts = [i.text for i in elsewhere.build_items()]
        assert f"Plan to stop at {other.name}" in else_texts
        assert not any(t.startswith("Cancel planned stop") for t in else_texts)

        # The move confirmation offers Yes (default) and a No that keeps the plan.
        confirm = ConfirmMovePlanState(app.ctx, d, other)
        labels = [i.text for i in confirm.build_items()]
        assert labels[0].startswith("Yes,")
        assert any(t.startswith("No,") for t in labels)
        next(i for i in confirm.build_items() if i.text.startswith("No,")).action()
        assert d.trip.planned_stop_name == planned.name  # No leaves it unchanged
    finally:
        app.shutdown()


def test_plan_button_skips_the_menu_click_so_only_the_chime_plays():
    from freight_fate.app import App
    from freight_fate.states.driving_stop_detail import StopDetailState

    app = App()
    try:
        d = _driving(app)
        d.trip.stops = _stops(d.trip.position_mi)
        stop = d.trip.stops[0]
        detail = StopDetailState(app.ctx, d, stop)
        app.push_state(detail)

        plan = next(i for i in detail.items if i.text == f"Plan to stop at {stop.name}")
        assert plan.select_sound is None  # _plan plays its own ui/notify chime
        # Every other row still gets the normal menu click.
        for item in detail.items:
            if item is not plan:
                assert item.select_sound == "ui/menu_select"
    finally:
        app.shutdown()


def test_planned_prefix_reaches_every_stop_announcement(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEventKind
    from freight_fate.states.driving_menu_states import DrivingStatusScreenState

    app = App()
    try:
        d = _driving(app)
        d.trip.stops = _stops(d.trip.position_mi)
        stop = d.trip.stops[0]
        d.trip.planned_stop_name = stop.name

        # Automatic in-visibility announcement (five-mile lookahead).
        d.trip._events.clear()
        d.trip._check_stops()
        ahead_events = [e for e in d.trip._events if e.kind == TripEventKind.STOP_AHEAD]
        assert ahead_events
        assert ahead_events[0].message.startswith(f"Planned stop, {stop.spoken_name}")

        # U-key upcoming readout.
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        d._speak_upcoming()
        assert any(f"Planned stop, {stop.spoken_name}" in text for text in spoken)

        # Map screen stop line.
        screen = DrivingStatusScreenState(app.ctx, d, "map")
        screen.items = screen.build_items()
        assert any(f"Planned stop, {stop.spoken_name}" in i.text for i in screen.items)

        # C-key rest-stop suggestion ("Next legal stop").
        context = d._hos_route_context()
        assert f"Next legal stop: Planned stop, {stop.spoken_name}" in context
    finally:
        app.shutdown()


def test_plan_clears_when_passed_or_taken_and_survives_saves():
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEventKind
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        d = _driving(app)
        d.trip.stops = _stops(d.trip.position_mi)
        stop = d.trip.stops[0]

        # Snapshot round-trip keeps the plan.
        d.trip.planned_stop_name = stop.name
        snap = d.snapshot()
        assert snap["planned_stop"] == stop.name
        resumed = DrivingState.from_snapshot(app.ctx, snap)
        assert resumed is not None
        assert resumed.trip.planned_stop_name == stop.name

        # Driving past the planned stop announces once and clears the plan.
        d.trip.position_mi = stop.at_mi + 0.5
        d.trip._events.clear()
        d.trip._check_stops()
        assert d.trip.planned_stop_name is None
        cues = [e for e in d.trip._events if e.kind == TripEventKind.GPS_CUE]
        assert any("drove past your planned stop" in e.message for e in cues)

        # Taking the exit fulfills the plan and clears it quietly.
        d.trip.position_mi = stop.at_mi
        d.trip.planned_stop_name = stop.name
        d._open_poi_stop(stop)
        assert d.trip.planned_stop_name is None
    finally:
        app.shutdown()
