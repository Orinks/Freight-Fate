"""Shared helpers for driving-state feature tests."""

import pygame


class HeldKeys:
    def __init__(self, *pressed: int) -> None:
        self.pressed = set(pressed)

    def __getitem__(self, key: int) -> bool:
        return key in self.pressed


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def finish_timed_state(app):
    while getattr(app.state, "remaining", 0) > 0:
        app.state.update(1 / 60)


def release_air_brakes(driving):
    driving.truck.set_air_ready(parking_brake=False)


def set_trip_traffic(driving, vehicles):
    driving.trip.traffic_manager.vehicles = list(vehicles)


def start_drive(app):
    """New career, accept the assigned dispatch, depart; returns DrivingState.

    New company hires run the load and route dispatch assigns, so the board
    offers a single assignment and departure skips the route menu.
    """
    from freight_fate.states.city import CityMenuState, PickupFacilityState
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.main_menu import MainMenuState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # default name
    app.state.handle_event(key_event(pygame.K_RETURN))  # default career start
    app.state.handle_event(key_event(pygame.K_RETURN))  # default region
    app.state.handle_event(key_event(pygame.K_RETURN))  # default home terminal
    app.state.handle_event(key_event(pygame.K_RETURN))  # job board
    if isinstance(app.state, CityMenuState):
        app.state.handle_event(key_event(pygame.K_RETURN))  # dispatch board
    assert app.state.assigned_mode
    app.state.handle_event(key_event(pygame.K_RETURN))  # accept assigned job
    assert isinstance(app.state, DrivingState)
    assert app.state.phase == "pickup"
    app.state.trip.position_mi = app.state.trip.total_miles
    app.state.trip.finished = True
    app.state.truck.velocity_mps = 0.0
    app.state.update(1 / 60)
    finish_timed_state(app)
    assert isinstance(app.state, PickupFacilityState)
    app.state.handle_event(key_event(pygame.K_RETURN))  # check in at origin
    app.state.handle_event(key_event(pygame.K_RETURN))  # load at dock
    finish_timed_state(app)
    app.state.handle_event(key_event(pygame.K_RETURN))  # depart on assigned route
    assert isinstance(app.state, DrivingState)
    assert app.state.phase == "delivery"
    # The origin yard may carry a turn-level street chain; these feature
    # tests exercise highway machinery, so skip the departure chain (the
    # chain has its own coverage in the surface/departure-chain suites).
    app.state._departure_checked = True
    release_air_brakes(app.state)
    return app.state


def quiet_trip(driving):
    """Push random hazards and inspections beyond this test's horizon."""
    from freight_fate.sim.weather import WeatherKind

    driving.trip._hazard_check_mi = 1e9
    driving.trip._inspection_check_mi = 1e9
    # Emptying the list is not enough on its own: the bubble tops itself up
    # around the truck every update, so a test that cleared the road once
    # would find traffic back on it a frame later -- along with the pass
    # earcons and the slow-traffic badge that come with it.
    driving.trip.traffic_manager.rolling_bubble = False
    driving.trip.traffic_manager.vehicles = []
    # Congestion zones re-inject slow NPC traffic when entered, which would
    # steal the ACC's attention from whatever the test is isolating.
    driving.trip.zones = [z for z in driving.trip.zones if z.aadt is None]
    driving.weather.current = WeatherKind.CLEAR


def open_limits(driving):
    """Lift posted speed limits out of the way so a test can isolate cruise
    hold/follow behavior from the predictive-ACC limit cap."""
    driving.trip.speed_limit_at = lambda mile: (200.0, None)


def take_destination_exit(driving):
    """Move onto the delivery ramp and stop at the destination gate."""
    driving.ctx.settings.destination_approach_assist = False
    destination = driving._destination_exit_stop()
    assert destination is not None
    driving._exit_stop = destination
    driving._exit_lane_alignment = 1.0
    driving.trip.position_mi = destination.at_mi
    driving.truck.velocity_mps = 0.0
    driving._update_exit(0.0)
    driving._update_exit(driving._ramp_mi)
    if driving._surface_chain:
        # Chain-capable destinations flow off the ramp onto city streets;
        # fast-forward the street chain to the facility gate.
        driving.trip.position_mi = driving.trip.total_miles
        driving.trip.finished = True
        driving.truck.velocity_mps = 0.0
        driving._handle_arrival_gate()
    finish_timed_state(driving.ctx._app)
    if driving.ctx._app.state is driving:
        driving.trip.position_mi = driving.trip.total_miles
        driving.trip.finished = True
        driving._handle_arrival_gate()
        finish_timed_state(driving.ctx._app)
    if driving.ctx._app.state is driving and driving.ctx.settings.destination_approach_assist:
        driving._handle_arrival_gate()
        if driving._arrival_full_stop_said:
            driving.handle_event(key_event(pygame.K_RETURN))


def mark_destination_exit_taken(driving):
    driving._destination_exit_taken = True
    driving.trip.finished = True
    driving.trip.position_mi = driving.trip.total_miles


def facility_street_chain(driving, *, time_scale: float = 1.0):
    """Swap the drive onto a deterministic two-block facility street chain.

    The deadhead shape a tester reported: 25 mph streets with a judged left
    turn between them, which advises the trailer corner cap of 20. Both blocks
    are long enough that the facility gate zone stays clear of the corner, so
    a test can watch the corner on its own.
    """
    from freight_fate.data.world_models import Leg, Route
    from freight_fate.sim import Trip

    city = driving.trip.route.cities[0]
    legs = [
        Leg(
            city,
            city,
            1.2,
            "East Navarre Street",
            "flat",
            (),
            local_cue="Start on East Navarre Street.",
            local_speed_mph=25.0,
        ),
        Leg(
            city,
            city,
            1.2,
            "North Michigan Street",
            "flat",
            (),
            local_cue="Turn left onto North Michigan Street.",
            local_speed_mph=25.0,
        ),
    ]
    trip = Trip(
        Route([city] * 3, legs), driving.truck, driving.trip.weather, seed=3, time_scale=time_scale
    )
    trip.traffic_manager.vehicles = []
    trip.traffic_manager.rolling_bubble = False
    trip._hazard_check_mi = 1e9
    trip._inspection_check_mi = 1e9
    trip.traffic_context = lambda: None
    driving.trip = trip
    driving._reset_turn_state_for_trip()
    driving._destination_exit_taken = True
    return trip


def short_block_street_chain(driving, *, block_mi: float = 0.08, time_scale: float = 1.0):
    """A street chain whose second corner arrives inside the first one's tail.

    The other half of the tester's deadhead report: turns "coming up really
    quickly". A 420-foot block is an ordinary city block and shorter than the
    stretch one corner stays in play for, so the second corner is already in
    front of the truck while the first is still being taken -- and it turns
    onto an unnamed service way, which advises the 15 mph gate crawl rather
    than the 20 a named street's corner gets.

    Returns ``(trip, first_cue, second_cue)``.
    """
    from freight_fate.data.world_models import Leg, Route
    from freight_fate.sim import Trip

    city = driving.trip.route.cities[0]
    legs = [
        Leg(
            city,
            city,
            1.2,
            "East Navarre Street",
            "flat",
            (),
            local_cue="Start on East Navarre Street.",
            local_speed_mph=25.0,
        ),
        Leg(
            city,
            city,
            block_mi,
            "North Michigan Street",
            "flat",
            (),
            local_cue="Turn left onto North Michigan Street.",
            local_speed_mph=25.0,
        ),
        Leg(
            city,
            city,
            1.2,
            "the service road",
            "flat",
            (),
            local_cue="Turn right onto the service road.",
            local_speed_mph=15.0,
        ),
    ]
    trip = Trip(
        Route([city] * 4, legs), driving.truck, driving.trip.weather, seed=3, time_scale=time_scale
    )
    trip.traffic_manager.vehicles = []
    trip.traffic_manager.rolling_bubble = False
    trip._hazard_check_mi = 1e9
    trip._inspection_check_mi = 1e9
    trip.traffic_context = lambda: None
    driving.trip = trip
    driving._reset_turn_state_for_trip()
    driving._destination_exit_taken = True
    turns = [c for c in trip.navigation_cues if c.key.startswith("local:turn:")]
    assert len(turns) == 2, "the short-block chain needs both corners"
    return trip, turns[0], turns[1]


def roll_to(driving, mile: float, *, limit_frames: int = 60 * 300):
    """Run frames until the truck reaches ``mile``; return the speed trace."""
    trace = []
    for _ in range(limit_frames):
        if driving.trip.position_mi >= mile:
            break
        driving.update(1 / 60)
        trace.append((driving.trip.position_mi, driving.truck.speed_mph))
    return trace


def open_status_screen(app, label):
    """From the open driving status picker, open a named screen submenu."""
    from freight_fate.states.driving import DrivingStatusScreenState

    picker = app.state
    while picker.items[picker.index].text != label:
        picker.handle_event(key_event(pygame.K_DOWN))
    picker.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, DrivingStatusScreenState)
    return app.state


def open_driver_apps(app):
    """From the open driving status picker, open the driver tablet menu."""
    from freight_fate.states.driving import DriverAppsState

    picker = app.state
    while picker.items[picker.index].text != "Driver apps":
        picker.handle_event(key_event(pygame.K_DOWN))
    picker.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, DriverAppsState)
    return app.state


def open_driver_app(app, label):
    """From the driver tablet menu, open one app."""
    from freight_fate.states.driving import DriverAppScreenState

    apps = app.state
    while apps.items[apps.index].text != label:
        apps.handle_event(key_event(pygame.K_DOWN))
    apps.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, DriverAppScreenState)
    return app.state
