"""Highway exits and cruise control, end to end through the driving state."""

import pygame
import pytest


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def release_air_brakes(driving):
    driving.truck.set_air_ready(parking_brake=False)


def start_drive(app):
    """New career, accept an unlocked job, pick a route; returns DrivingState."""
    from freight_fate.states.city import PickupFacilityState, RouteSelectState
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
    assert isinstance(app.state, DrivingState)
    assert app.state.phase == "pickup"
    app.state.trip.position_mi = app.state.trip.total_miles
    app.state.trip.finished = True
    app.state.truck.velocity_mps = 0.0
    app.state.update(1 / 60)
    assert isinstance(app.state, PickupFacilityState)
    app.state.handle_event(key_event(pygame.K_RETURN))  # check in at origin
    app.state.handle_event(key_event(pygame.K_RETURN))  # load at dock
    app.state.handle_event(key_event(pygame.K_RETURN))  # depart for destination
    assert isinstance(app.state, RouteSelectState)
    app.state.handle_event(key_event(pygame.K_RETURN))  # accept planned route
    assert isinstance(app.state, DrivingState)
    assert app.state.phase == "delivery"
    release_air_brakes(app.state)
    return app.state


def quiet_trip(driving):
    """Push random hazards and inspections beyond this test's horizon."""
    driving.trip._hazard_check_mi = 1e9
    driving.trip._inspection_check_mi = 1e9
    driving.trip.traffic_leads = []


def test_trip_event_sounds_use_contextual_cues():
    from freight_fate.sim.trip import TripEvent, TripEventKind, Zone
    from freight_fate.states.driving import _route_event_sound

    assert _route_event_sound(TripEvent(TripEventKind.HAZARD, "Brake now!")) == (
        "events/hazard_warning"
    )
    assert _route_event_sound(TripEvent(TripEventKind.TOLL_CHARGED, "Toll")) == (
        "events/toll_charged"
    )
    assert _route_event_sound(TripEvent(TripEventKind.STATE_CROSSING, "Crossing")) == (
        "events/state_crossing"
    )
    event = TripEvent(
        TripEventKind.ZONE_ENTER,
        "construction ahead",
        {"zone": Zone(1.0, 2.0, 45.0, "construction")},
    )
    assert _route_event_sound(event) == "events/construction_zone"


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
        assert "stop, then dock and deliver" in help_text
    finally:
        app.shutdown()


def test_closing_status_panel_does_not_restart_drive_music(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingStatusState

    app = App()
    played = []
    monkeypatch.setattr(
        app.ctx.audio,
        "play_music",
        lambda track, fade_ms=1500: played.append((track, fade_ms)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        played.clear()

        driving.handle_event(key_event(pygame.K_TAB))
        assert isinstance(app.state, DrivingStatusState)
        app.state.handle_event(key_event(pygame.K_ESCAPE))

        assert app.state is driving
        assert played == []
    finally:
        app.shutdown()


def test_how_to_play_documents_new_gameplay_systems():
    from freight_fate.states.main_menu import HELP_PAGES

    help_text = " ".join(line for _title, lines in HELP_PAGES for line in lines).lower()

    assert "air brakes need pressure" in help_text
    assert "wait for air pressure to reach 100 psi" in help_text
    assert "press p to release or set the parking brake" in help_text
    assert "low air" in help_text
    assert "tab opens a driving status menu" in help_text
    assert "slow below 5 miles per hour" in help_text
    assert "destination facility" in help_text
    assert "local deadhead moves to the origin facility" in help_text
    assert "company terminal or yard" in help_text
    assert "pickup gate" in help_text
    assert "loading requires the truck to be stopped" in help_text
    assert "loaded and sealed" in help_text
    assert "dispatch gives you the destination route" in help_text
    assert "route choice happens after pickup" in help_text
    assert "real highway corridors" in help_text
    assert "gps announces state lines" in help_text
    assert "grades and terrain come from the route" in help_text
    assert "weather, traffic, and construction still vary" in help_text
    assert "slow lead vehicles" in help_text
    assert "settings are grouped into categories" in help_text
    assert "open a category to see its settings" in help_text
    assert "trip pacing changes how quickly distance and game time pass" in help_text
    assert "standard pacing is the normal freight fate pace" in help_text
    assert "relaxed keeps the clock but gives a more forgiving schedule" in help_text
    assert "longer limits and fewer penalties" in help_text
    assert "adaptive cruise" in help_text
    assert "three second clear-weather gap" in help_text
    assert "increase the following gap" in help_text
    assert "highway stops use clear place names" in help_text
    assert "list the actions available there" in help_text
    assert "call for help" in help_text
    assert "tolls and approved company charges" in help_text
    assert "costs you caused, like speeding fines" in help_text
    assert "gross pay, carrier-paid or reimbursed charges" in help_text
    assert "net driver pay" in help_text
    assert "touch the brakes to cancel" in help_text
    assert "save" in help_text
    assert "dock and deliver" in help_text
    assert "wider freight area with many possible shippers" in help_text
    assert "rail and intermodal ramps" in help_text
    assert "parcel hubs" in help_text
    assert "farms and grain elevators" in help_text
    assert "chemical terminals" in help_text
    assert "not every market supports every cargo equally" in help_text
    assert "major freight areas instead of every town" in help_text
    assert "routes with enough stops" in help_text
    assert "refrigerated, heavy-haul, and high-value freight" in help_text
    assert "full tank or full repair" in help_text
    assert "emergency shoulder sleep" in help_text
    assert "resets your legal clock but leaves fatigue" in help_text
    assert "parking ticket or minor damage" in help_text


def test_dispatch_board_keeps_route_planning_out_of_load_offer():
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState, route_planning_summary

    app = App()
    try:
        app.ctx.profile = Profile(name="Dispatch Test", current_city="New York")
        jobs = JobBoard(app.ctx.world, seed=2).offers(
            "New York", {"refrigerated", "heavy_haul", "high_value"}, level=5)
        assert jobs
        state = JobBoardState(app.ctx, jobs)
        items = state.build_items()
        rows = [
            item.text if isinstance(item.text, str) else item.text()
            for item in items
        ]

        assert any("Equipment:" in row for row in rows)
        assert all("Legal HOS plan" not in row for row in rows)
        assert all("Route has" not in row for row in rows)
        assert all("Fuel-capable stops" not in row for row in rows)
        assert "Route inspection after pickup covers rest, fuel, toll" in items[0].help

        toll_route = app.ctx.world.route_from_cities(["New York", "Philadelphia"])
        summary = route_planning_summary(toll_route)
        assert "Legal HOS plan" in summary
        assert "Fuel-capable stops:" in summary
        assert "Estimated carrier-paid toll exposure" in summary
        assert "not a guaranteed open space" in summary
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_air_brake_startup_blocks_movement_until_ready_and_released(monkeypatch):
    from freight_fate.app import App

    class FakeKeys:
        def __init__(self, held):
            self.held = held

        def __getitem__(self, key):
            return key in self.held

    app = App()
    events = []
    spoken = []
    played = []
    held = {pygame.K_UP}
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event",
                        lambda text, interrupt=True: events.append(text))
    monkeypatch.setattr(app.ctx, "say",
                        lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(app.ctx.audio, "play",
                        lambda key, volume=1.0: played.append((key, volume)))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.set_cold_air_start()

        driving.handle_event(key_event(pygame.K_e))
        for _ in range(60):
            driving.update(1 / 60)

        assert driving.truck.speed_mph == 0.0
        assert driving.truck.parking_brake
        assert any("Wait for 100 psi" in text for text in events)

        driving.handle_event(key_event(pygame.K_p))
        assert driving.truck.parking_brake
        assert "Parking brake stays set" in spoken[-1]

        for _ in range(60 * 15):
            driving.update(1 / 60)
            if driving.truck.air_ready:
                break

        assert driving.truck.air_ready
        assert any("Air pressure ready" in text for text in events)

        driving.handle_event(key_event(pygame.K_p))
        assert not driving.truck.parking_brake
        assert ("vehicle/brake_release", 0.65) in played

        for _ in range(60 * 5):
            driving.update(1 / 60)
            if driving.truck.speed_mph > 1.0:
                break

        assert driving.truck.speed_mph > 1.0

        driving.handle_event(key_event(pygame.K_p))
        assert driving.truck.parking_brake
        assert ("vehicle/brake_set", 0.65) in played
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_air_brake_help_and_status_are_spoken(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState, DrivingStatusState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.set_cold_air_start()

        driving.handle_event(key_event(pygame.K_F1))
        assert "Air pressure must build" in spoken[-1]
        assert "Press P to release or set the parking brake" in spoken[-1]

        driving.handle_event(key_event(pygame.K_TAB))
        assert isinstance(app.state, DrivingStatusState)
        status_lines = [item.text for item in app.state.items]
        air_status = next(line for line in status_lines if line.startswith("Air brakes:"))
        assert "primary 55 psi" in air_status
        assert "secondary 55 psi" in air_status
        assert "trailer 55 psi" in air_status
        assert "parking brake set" in air_status
        assert "compressor idle" in air_status
        assert "brakes cool" in air_status
        assert any(line.startswith("Weather:") for line in status_lines)

        app.state.handle_event(key_event(pygame.K_RIGHT))
        assert app.state.screen_index == 1
        driver_lines = [item.text for item in app.state.items]
        assert any(line.startswith("Driver:") for line in driver_lines)
        assert any(line.startswith("Hours:") for line in driver_lines)

        app.state.handle_event(key_event(pygame.K_RIGHT))
        assert app.state.screen_index == 2
        map_lines = [item.text for item in app.state.items]
        assert any(line.startswith("Route:") for line in map_lines)
        assert any("offers" in line for line in map_lines)

        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, DrivingState)
        assert spoken[-1] == "Back to driving."

        driving.handle_event(key_event(pygame.K_SPACE))
        assert "air 55 psi" in spoken[-1]
        assert any(line.startswith("Air: 55 psi") for line in driving.lines())
    finally:
        app.shutdown()


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
        assert "Destination ahead" in events[-1]
        assert "Slow below 3 mph" in events[-1]
        assert "slow below 3 mph" in driving.lines()[-1].lower()

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
        assert "Stop to dock" in events[-1]
        assert "stop to dock" in driving.lines()[-1]
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
        assert "current gross payout" in spoken[-1]
        assert "Carrier-paid or reimbursed charges recorded so far" in spoken[-1]
        assert "Those charges do not reduce driver pay" in spoken[-1]
        assert "estimated net driver pay" in spoken[-1]
        assert "hours remain before the deadline" in spoken[-1]
        assert "Cargo condition" in spoken[-1]
        assert "Dock and deliver to settle" in spoken[-1]

        app.state.handle_event(key_event(pygame.K_UP))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert not isinstance(app.state, FacilityArrivalState)
        assert app.ctx.profile.career.deliveries == 1
        played_keys = [key for key, _volume in played]
        assert "poi/dock_and_deliver" in played_keys
        assert "ui/job_complete" in played_keys
        assert "ui/cash" in played_keys
        assert "ui/menu_open" not in played_keys
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
def test_rest_stop_menu_can_save_active_drive():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ParkingFullState, RestStopState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi
        driving.truck.velocity_mps = 0.0
        driving.handle_event(key_event(pygame.K_t))
        assert isinstance(app.state, (RestStopState, ParkingFullState))
        if isinstance(app.state, ParkingFullState):
            return

        while app.state.items[app.state.index].text != "Save at this stop":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        saved = app.ctx.profile.active_trip
        assert saved is not None
        assert saved["kind"] == "delivery"
        assert saved["route_kind"] == "corridor_itinerary"
        assert saved["position_mi"] == stop.at_mi
        loaded = Profile.load(app.ctx.profile.path)
        assert loaded.active_trip == saved
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_poi_menu_uses_curated_roadside_assistance_label():
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = RoadStop(
            "Example Turnpike Service Plaza",
            driving.trip.position_mi,
            "service_plaza",
            ("park", "save", "roadside_assistance"),
            ("parking", "roadside_assistance"),
        )
        state = RestStopState(app.ctx, driving, stop)
        texts = [
            item.text if isinstance(item.text, str) else item.text()
            for item in state.build_items()
        ]
        assert "Call roadside assistance" in texts
        assert all("osm" not in text.lower() for text in texts)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_status_map_screen_describes_source_backed_poi_services():
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState, DrivingStatusState

    app = App()
    try:
        app.ctx.profile = Profile(name="Map Test", current_city="New York")
        job = Job(
            CARGO_CATALOG["electronics"],
            18,
            "New York",
            "JFK Air Cargo",
            "Philadelphia",
            78,
            2500,
            12,
            origin_type="air_cargo",
            destination_location="Philadelphia Distribution Center",
            destination_type="retail_distribution",
        )
        route = app.ctx.world.route_from_cities(["New York", "Philadelphia"])
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        quiet_trip(driving)
        state = DrivingStatusState(app.ctx, driving)
        state.screen_index = 2
        app.push_state(state)

        text = " ".join(item.text for item in state.items)
        assert "offers" in text
        assert "fuel" in text
        assert "food" in text
        assert "sleep or long rest" in text or "30-minute rest break" in text
        assert "listed services" in text
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_toll_route_delivery_settlement_records_expense(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ArrivalState, DrivingState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        app.ctx.profile = Profile(name="Toll Test", current_city="New York")
        job = Job(
            CARGO_CATALOG["electronics"],
            18,
            "New York",
            "JFK Air Cargo",
            "Philadelphia",
            78,
            2500,
            12,
            origin_type="air_cargo",
            destination_location="Philadelphia Distribution Center",
            destination_type="retail_distribution",
        )
        route = app.ctx.world.route_from_cities(["New York", "Philadelphia"])
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        driving.trip.position_mi = 79.0
        driving.trip.update(0.0)
        assert driving.trip.toll_expense == 30.0

        app.ctx.profile.money = 1000.0
        app.ctx.push_state(ArrivalState(app.ctx, driving))

        assert app.ctx.profile.money == pytest.approx(3875.0)
        assert app.ctx.profile.career.total_earnings == pytest.approx(2875.0)
        text = " ".join(app.state.summary_parts)
        assert "Gross pay 2,875 dollars" in text
        assert "Carrier-paid or reimbursed charges 215 dollars" in text
        assert "tolls 30" in text
        assert "accessorials carrier-authorized unloading service 185 dollars" in text
        assert "not deducted from driver pay" in text
        assert "Driver-responsibility charges 0 dollars" in text
        assert "Net driver pay 2,875 dollars" in text

        assert app.state.screen_index == 0
        assert app.state.lines()[0] == "Delivery complete - Overview"
        app.state.handle_event(key_event(pygame.K_RIGHT))
        assert app.state.screen_index == 1
        pay_lines = [item.text for item in app.state.items]
        assert any(line.startswith("Gross pay: 2,875 dollars") for line in pay_lines)
        assert any("Carrier-paid or reimbursed charges" in line for line in pay_lines)
        app.state.handle_event(key_event(pygame.K_RIGHT))
        assert app.state.screen_index == 2
        route_lines = [item.text for item in app.state.items]
        assert any(line.startswith("Route: New York to Philadelphia") for line in route_lines)
    finally:
        app.shutdown()


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


@pytest.mark.smoke
def test_adaptive_cruise_follows_modeled_traffic(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TrafficLead

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
        driving.trip.traffic_leads = [
            TrafficLead(driving.trip.position_mi + 0.08, 45.0, "slow lead traffic", 4.0)
        ]
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0
        driving.truck.throttle = 0.9
        driving.handle_event(key_event(pygame.K_k))
        driving.update(1 / 60)

        assert driving._cruise_mph is not None
        assert driving._acc_following
        assert driving.truck.throttle < 0.9
        assert driving.truck.brake > 0.0
        assert "Traffic ahead, adaptive cruise reducing speed." in events
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_increases_gap_for_bad_weather(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TrafficLead
    from freight_fate.sim.weather import WeatherKind

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0
        driving.truck.throttle = 0.5
        driving.handle_event(key_event(pygame.K_k))

        driving.trip.traffic_leads = [
            TrafficLead(driving.trip.position_mi + 0.08, 65.0,
                        "slow lead traffic", 4.0)
        ]
        driving.weather.current = WeatherKind.CLEAR
        clear_gap = driving._acc_gap_seconds()
        driving.update(1 / 60)
        assert not driving._acc_following

        driving.weather.current = WeatherKind.HEAVY_RAIN
        wet_gap = driving._acc_gap_seconds()
        driving.update(1 / 60)

        assert wet_gap > clear_gap
        assert driving._acc_following
        assert "Wet roads, adaptive cruise increasing following gap." in events
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_disables_before_restricted_zone(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind, Zone

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None

        zone = Zone(10.0, 15.0, 45.0, "construction")
        event = TripEvent(
            TripEventKind.GPS_CUE,
            "In 2 miles, construction ahead. Speed limit 45.",
            {"zone": zone},
        )
        driving._handle_trip_event(event)

        assert driving._cruise_mph is None
        assert events[-1] == (
            "In 2 miles, construction ahead. Speed limit 45. "
            "Adaptive cruise disabled; take manual speed control."
        )
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_disables_for_heavy_traffic_zone_entry(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind, Zone

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
        monkeypatch.setattr(app.ctx, "say",
                            lambda text, interrupt=True: events.append(text))
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None

        zone = Zone(10.0, 15.0, 50.0, "heavy traffic")
        event = TripEvent(
            TripEventKind.ZONE_ENTER,
            "heavy traffic ahead. Speed limit 50.",
            {"zone": zone},
        )
        driving._handle_trip_event(event)

        assert driving._cruise_mph is None
        assert events[-2] == (
            "heavy traffic ahead. Speed limit 50. "
            "Adaptive cruise disabled; take manual speed control."
        )
        assert events[-1].startswith("New achievement! Mind the Bumper Gap.")
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
