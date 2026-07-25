"""Headless playtest harness for transcript-backed gameplay verification."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FREIGHT_FATE_NO_SPEECH", "1")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from freight_fate.sim.trip_models import NPCVehicle, TrafficPressure


def key_event(key: int, unicode: str = ""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode, mod=0)


def _finish_timed_state(app) -> None:
    while getattr(app.state, "remaining", 0) > 0:
        app.state.update(1 / 60)


@dataclass
class SpokenEntry:
    sequence: int
    channel: str
    text: str
    interrupt: bool


@dataclass
class PlaytestResult:
    transcript: list[str] = field(default_factory=list)
    spoken: list[SpokenEntry] = field(default_factory=list)
    deliveries: int = 0
    destination: str = ""
    current_city: str = ""
    remaining_miles: float = 0.0
    speeding_strikes: int = 0
    speeding_tickets: int = 0
    speed_control_transitions: list[str] = field(default_factory=list)
    max_speeding_timer_s: float = 0.0
    destination_exit_speed_mph: float | None = None
    # Equipment and freight handling. A transcript alone cannot tell you which
    # tractor dispatch drew, whether the shipper staged a trailer or loaded at
    # a dock, or what was wrong with the box -- and those now decide how a run
    # reads, so a playtest that cannot see them is reviewing half the game.
    assigned_truck: str = ""
    assigned_truck_label: str = ""
    slip_seat_pool: list[str] = field(default_factory=list)
    pickup_mode: str = ""
    pickup_minutes: float = 0.0
    detention_minutes: float = 0.0
    detention_pay: float = 0.0
    trailer_number: str = ""
    trailer_condition: str = ""
    trailer_defect: str = ""
    trailer_refused: bool = False
    delivery_mode: str = ""
    delivery_minutes: float = 0.0

    def equipment_summary(self) -> str:
        """One plain-text block covering everything the truck came with."""
        lines = [f"Tractor: {self.assigned_truck_label or self.assigned_truck or 'unknown'}"]
        if self.slip_seat_pool:
            lines.append(f"Yard spares: {', '.join(self.slip_seat_pool)}")
        if self.pickup_mode:
            lines.append(f"Pickup: {self.pickup_mode}, {self.pickup_minutes:.0f} minutes")
        if self.detention_minutes:
            lines.append(
                f"Detention: {self.detention_minutes:.0f} minutes, "
                f"{self.detention_pay:,.0f} dollars"
            )
        if self.trailer_number:
            state = self.trailer_condition or "unknown condition"
            defect = f", {self.trailer_defect}" if self.trailer_defect else ""
            refused = " (refused and swapped)" if self.trailer_refused else ""
            lines.append(f"Trailer: {self.trailer_number}, {state}{defect}{refused}")
        if self.delivery_mode:
            lines.append(f"Delivery: {self.delivery_mode}, {self.delivery_minutes:.0f} minutes")
        return chr(10).join(lines)

    @property
    def transcript_text(self) -> str:
        return "\n".join(self.transcript)

    def assert_no_known_destination_exit_regressions(self) -> None:
        lower_lines = [line.lower() for line in self.transcript]
        destination_exit_lines = [
            line
            for line in lower_lines
            if "destination exit" in line or "exit for the destination" in line
        ]
        assert len(destination_exit_lines) <= 1, self.transcript_text
        assert not any(re.search(r"\b21 miles remaining\b", line) for line in lower_lines), (
            self.transcript_text
        )
        assert self.remaining_miles == 0.0

    def assert_ordered(self, *phrases: str) -> None:
        """Assert phrases occur in order, allowing unrelated speech between them."""
        cursor = 0
        for phrase in phrases:
            cursor = next(
                (
                    i + 1
                    for i, line in enumerate(self.transcript[cursor:], cursor)
                    if phrase in line
                ),
                0,
            )
            assert cursor, f"Missing or out-of-order phrase {phrase!r}\n{self.transcript_text}"

    def assert_screen_reader_friendly(self) -> None:
        assert self.transcript
        assert all(line.strip() == line and line for line in self.transcript)
        raw_markers = ("osm_id", "amenity=", "highway=", "node/", "way/")
        assert not any(marker in self.transcript_text.lower() for marker in raw_markers)
        assert all(entry.sequence == i for i, entry in enumerate(self.spoken))


class PlaytestHarness:
    """Drive real game states under pytest without opening a visible window."""

    def __init__(self, monkeypatch) -> None:
        self.monkeypatch = monkeypatch
        self.app = None
        self.result = PlaytestResult()
        self.driving = None

    def __enter__(self) -> PlaytestHarness:
        from freight_fate.app import App

        self.app = App()
        self.monkeypatch.setattr(self.app.ctx, "say", self._say)
        self.monkeypatch.setattr(self.app.ctx, "say_event", self._say_event)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.app is not None:
            self.app.shutdown()

    def _say(self, text: str, interrupt: bool = True) -> None:
        self.result.spoken.append(SpokenEntry(len(self.result.spoken), "main", text, interrupt))
        self.result.transcript.append(text)

    def _say_event(self, text: str, interrupt: bool = True) -> None:
        self.result.spoken.append(SpokenEntry(len(self.result.spoken), "event", text, interrupt))
        self.result.transcript.append(f"[event] {text}")

    def start_delivery(
        self,
        *,
        profile_name: str = "Playtest",
        job_rank: int = 0,
        route_rank: int = 0,
        configure_profile=None,
        stop_at_pickup: bool = False,
        arm_speed_control_on_deadhead: bool = False,
        walk_around_trailer: bool = False,
        refuse_bad_trailer: bool = False,
    ) -> PlaytestResult:
        from freight_fate.states.city import (
            CityMenuState,
            JobBoardState,
            PickupFacilityState,
            RouteSelectState,
        )
        from freight_fate.states.driving import DrivingState
        from freight_fate.states.main_menu import (
            CareerStartState,
            HomeCityState,
            HomeTerminalState,
            MainMenuState,
            NameEntryState,
        )

        assert self.app is not None
        self.app.push_state(MainMenuState(self.app.ctx))
        self._select_current_menu_text("New career")
        assert isinstance(self.app.state, NameEntryState)
        for ch in profile_name:
            key = pygame.K_SPACE if ch == " " else ord(ch.lower())
            self.app.state.handle_event(key_event(key, ch))
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(self.app.state, CareerStartState)
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(self.app.state, HomeTerminalState)
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(self.app.state, HomeCityState)
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(self.app.state, CityMenuState)
        if configure_profile is not None:
            assert self.app.ctx.profile is not None
            configure_profile(self.app.ctx.profile)

        self.app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(self.app.state, JobBoardState)
        if self.app.state.assigned_mode:
            # New company hires are assigned a load: job_rank spends declines
            # to reach an alternative instead of browsing the board.
            self._accept_assigned_job(job_rank)
        else:
            self._choose_unlocked_job(job_rank)
        assert isinstance(self.app.state, DrivingState)
        assert self.app.state.phase == "pickup"

        if arm_speed_control_on_deadhead:
            self.app.state.truck.start_engine()
            self.app.state.truck.set_air_ready(parking_brake=False)
            self.app.state.truck.velocity_mps = 5.0
            self.app.state.handle_event(key_event(pygame.K_k))
            assert self.app.state._speed_control_armed

        self.app.state.trip.position_mi = self.app.state.trip.total_miles
        self.app.state.trip.finished = True
        if arm_speed_control_on_deadhead:
            self.app.state.truck.velocity_mps = 26.8
            self.app.state.update(1 / 60)
            assert isinstance(self.app.state, DrivingState)
        self.app.state.truck.velocity_mps = 0.0
        self.app.state.update(1 / 60)
        _finish_timed_state(self.app)
        assert isinstance(self.app.state, PickupFacilityState)
        self.record_equipment()
        if stop_at_pickup:
            return self.result
        self.select_menu_item("Check in at shipping office")
        # Either way the freight gets aboard; naming both keeps the harness
        # working whichever kind of shipper dispatch drew.
        for label in ("Drop and hook in the yard", "Load cargo at dock"):
            if label in self.menu_labels():
                self.select_menu_item(label)
                break
        else:  # pragma: no cover - the pickup menu always offers one of them
            raise AssertionError(f"no way to load: {self.menu_labels()}")
        _finish_timed_state(self.app)
        if walk_around_trailer:
            self.walk_around_trailer()
            if refuse_bad_trailer:
                self.refuse_trailer()
        self.record_equipment()
        self.select_menu_item("Depart for destination")
        if isinstance(self.app.state, RouteSelectState):
            # Owner-operators and authority choose their routing.
            self._choose_route(route_rank)
        # Company drivers run dispatch's assigned route: route_rank is unused.
        assert isinstance(self.app.state, DrivingState)
        assert self.app.state.phase == "delivery"

        self.driving = self.app.state
        self._neutralize_random_trip_friction()
        return self.result

    def start_route(
        self,
        origin: str,
        destination: str,
        *,
        profile_name: str = "Route Playtest",
        cargo: str = "general",
        tons: int = 18,
        route_cities: list[str] | None = None,
        trip_seed: int | None = None,
    ) -> PlaytestResult:
        """Set up a delivery on a specific supported route, skipping the menus.

        Useful for exercising one corridor's routing/data (e.g. a leg whose
        geometry changed) rather than whatever job the dispatch board offers.
        Pair with :meth:`drive_delivery_to_completion`.
        """
        from freight_fate.models.jobs import CARGO_CATALOG, Job
        from freight_fate.models.profile import Profile
        from freight_fate.states.driving import DrivingState

        assert self.app is not None
        self.app.ctx.profile = Profile(name=profile_name, current_city=origin)
        city_path = route_cities or [origin, destination]
        if city_path[0] != origin or city_path[-1] != destination:
            raise ValueError("route_cities must start at origin and end at destination")
        route = self.app.ctx.world.route_from_cities(city_path)
        if route is None:
            raise SystemExit(f"No supported route {' -> '.join(city_path)}")
        miles = round(route.miles)
        job = Job(
            CARGO_CATALOG[cargo],
            tons,
            origin,
            f"{origin} Terminal",
            destination,
            miles,
            max(500, miles * 10),
            max(2.0, miles / 25.0),
            destination_location=f"{destination} Terminal",
        )
        driving = DrivingState(
            self.app.ctx,
            job,
            route,
            trip_seed=trip_seed,
            phase="delivery",
        )
        self.app.push_state(driving)
        self.driving = driving
        self._neutralize_random_trip_friction()
        return self.result

    def drive_speed_control_segment(
        self,
        *,
        start_mi: float,
        end_mi: float,
        set_mph: float,
    ) -> PlaytestResult:
        """Run real automatic speed control through a targeted route segment."""
        assert self.driving is not None
        driving = self.driving
        driving.tutorial = None
        driving.trip.position_mi = start_mi
        # Keep patrol randomness from converting the same overspeed incident
        # into a traffic stop instead of the settlement strike measured here.
        driving.trip.patrols = []
        driving.truck.start_engine()
        driving.truck.set_air_ready(parking_brake=False)
        driving.truck.transmission.automatic = True
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = set_mph / 2.23694
        driving.truck.throttle = 0.35
        driving.handle_event(key_event(pygame.K_k))

        last_mode = ""
        for _frame in range(120_000):
            driving.update(1 / 60)
            mode = (
                "keeper"
                if driving._keeper_mph is not None
                else "cruise"
                if driving._cruise_mph is not None
                else "off"
            )
            if mode != last_mode:
                self.result.speed_control_transitions.append(mode)
                last_mode = mode
            self.result.max_speeding_timer_s = max(
                self.result.max_speeding_timer_s,
                driving._speeding_timer,
            )
            if driving.trip.position_mi >= end_mi:
                break
        else:
            raise AssertionError(
                f"speed-control segment never reached {end_mi:.1f} miles; "
                f"stopped at {driving.trip.position_mi:.1f}"
            )

        self.result.speeding_strikes = driving.speeding_strikes
        self.result.speeding_tickets = driving.speeding_tickets
        return self.result

    def settle_delivery_after_segment(self) -> PlaytestResult:
        """Reach the spoken settlement without adding unrelated road events."""
        from freight_fate.states.driving import ArrivalState, FacilityArrivalState

        assert self.app is not None
        assert self.driving is not None
        driving = self.driving
        driving.trip.position_mi = driving.trip.total_miles
        driving.trip.finished = True
        driving._destination_exit_taken = True
        driving.truck.velocity_mps = 0.0
        driving._handle_arrival_gate()
        _finish_timed_state(self.app)
        assert isinstance(self.app.state, FacilityArrivalState)
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        _finish_timed_state(self.app)
        assert isinstance(self.app.state, ArrivalState)

        profile = self.app.ctx.profile
        assert profile is not None
        self.result.deliveries = profile.career.deliveries
        self.result.destination = driving.job.destination
        self.result.current_city = profile.current_city
        self.result.remaining_miles = driving.trip.remaining_miles
        return self.result

    def drive_destination_exit_with_speed_control(
        self,
        *,
        set_mph: float,
        restricted_zone_reason: str | None = None,
    ) -> PlaytestResult:
        """Follow the spoken destination-exit path with K, X, and ramp braking."""
        from freight_fate.sim.trip import Zone
        from freight_fate.states.driving import (
            RAMP_MAX_MPH,
            ArrivalState,
            FacilityArrivalState,
        )

        assert self.app is not None
        assert self.driving is not None
        driving = self.driving
        driving.tutorial = None
        driving.trip.patrols = []
        driving.truck.start_engine()
        driving.truck.set_air_ready(parking_brake=False)
        driving.truck.transmission.automatic = True
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = set_mph / 2.23694
        driving.truck.throttle = 0.35
        destination = driving._destination_exit_stop()
        if restricted_zone_reason is not None:
            zone_end = destination.at_mi - 2.5
            driving.trip.zones.append(
                Zone(
                    zone_end - 1.0,
                    zone_end,
                    RAMP_MAX_MPH,
                    restricted_zone_reason,
                )
            )
            driving.trip.zones.sort(key=lambda zone: zone.start_mi)
        driving.trip.position_mi = max(
            0.0,
            destination.at_mi - driving._exit_window_mi() - 0.25,
        )
        driving.handle_event(key_event(pygame.K_k))

        class ExitKeys:
            def __getitem__(self, key: int) -> bool:
                if driving._ramp_mi is None:
                    return False
                remaining = max(0.0, driving._ramp_mi)
                target_mph = 0.0 if remaining == 0.0 else max(4.0, remaining * 70.0)
                if key == pygame.K_DOWN:
                    return driving.truck.speed_mph > target_mph + 1.0
                if key == pygame.K_UP:
                    return remaining > 0.0 and driving.truck.speed_mph < target_mph - 1.0
                return False

        self.monkeypatch.setattr(pygame.key, "get_pressed", lambda: ExitKeys())
        signaled = False
        last_mode = ""
        for _frame in range(120_000):
            driving.truck.air_pressure_psi = driving.truck.specs.air_governor_cut_out_psi
            driving.truck.parking_brake = False
            driving.update(1 / 60)
            mode = (
                "keeper"
                if driving._keeper_mph is not None
                else "cruise"
                if driving._cruise_mph is not None
                else "off"
            )
            if mode != last_mode:
                self.result.speed_control_transitions.append(mode)
                last_mode = mode
            self.result.max_speeding_timer_s = max(
                self.result.max_speeding_timer_s,
                driving._speeding_timer,
            )
            if driving._destination_exit_announced_key and not signaled:
                driving.handle_event(key_event(pygame.K_x))
                signaled = True
            if driving._ramp_mi is not None and self.result.destination_exit_speed_mph is None:
                self.result.destination_exit_speed_mph = driving.truck.speed_mph
            # Arrival runs a short spoken pull-in beat before the dock menu, so
            # let it finish instead of driving frames at a state that is only
            # counting down.
            _finish_timed_state(self.app)
            if isinstance(self.app.state, FacilityArrivalState):
                break
        else:
            raise AssertionError(
                "automatic speed control never completed the destination exit: "
                f"state={type(self.app.state).__name__}, "
                f"position={driving.trip.position_mi:.2f}, "
                f"speed={driving.truck.speed_mph:.1f}, ramp={driving._ramp_mi}, "
                f"signaled={signaled}\n{self.result.transcript_text}"
            )

        self.result.speeding_strikes = driving.speeding_strikes
        self.result.speeding_tickets = driving.speeding_tickets
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        _finish_timed_state(self.app)
        assert isinstance(self.app.state, ArrivalState)
        profile = self.app.ctx.profile
        assert profile is not None
        self.result.deliveries = profile.career.deliveries
        self.result.destination = driving.job.destination
        self.result.current_city = profile.current_city
        self.result.remaining_miles = driving.trip.remaining_miles
        return self.result

    def drive_delivery_to_completion(self) -> PlaytestResult:
        from freight_fate.states.driving import ArrivalState, FacilityArrivalState

        assert self.app is not None
        assert self.driving is not None
        driving = self.driving
        self.prepare_for_driving()

        crawl_mph = 15.0
        max_frames = int(driving.trip.total_miles / crawl_mph * 3600 * 60) + 60 * 60
        for _frame in range(max_frames):
            self._drive_one_frame()
            if driving.trip.finished:
                driving.truck.velocity_mps = 0.0
                driving._handle_arrival_gate()
                if driving._arrival_full_stop_said:
                    driving.handle_event(key_event(pygame.K_RETURN))
                _finish_timed_state(self.app)
                break
        else:
            raise AssertionError(
                f"delivery never finished in {max_frames} frames: "
                f"{driving.trip.position_mi:.1f}/{driving.trip.total_miles:.1f} mi"
            )

        assert isinstance(self.app.state, FacilityArrivalState)
        self._finish_delivery()
        assert isinstance(self.app.state, ArrivalState)

        profile = self.app.ctx.profile
        assert profile is not None
        self.result.deliveries = profile.career.deliveries
        self.result.destination = driving.job.destination
        self.result.current_city = profile.current_city
        self.result.remaining_miles = driving.trip.remaining_miles
        return self.result

    def _finish_delivery(self) -> None:
        """End the delivery whichever way this receiver takes freight."""
        assert self.app is not None
        self.record_equipment()
        for label in ("Drop the loaded trailer and hook an empty", "Dock and deliver"):
            if label in self.menu_labels():
                self.select_menu_item(label)
                break
        else:  # pragma: no cover - the arrival menu always offers one of them
            raise AssertionError(f"no way to deliver: {self.menu_labels()}")
        _finish_timed_state(self.app)

    def settle_current_delivery(self) -> PlaytestResult:
        """Fast-forward the active delivery to its settlement screen.

        The career-arc playtests care about what settlement *says* --
        level-ups, tractor assignments, badges -- not the road in between,
        so this teleports to the destination gate instead of driving it.
        Pair with :meth:`read_settlement_lines` to walk the arrival menu
        the way a screen-reader player would.
        """
        from freight_fate.states.driving import ArrivalState, FacilityArrivalState

        assert self.app is not None
        assert self.driving is not None
        driving = self.driving
        self.prepare_for_driving()
        driving.trip.position_mi = driving.trip.total_miles
        driving.trip.finished = True
        driving.truck.velocity_mps = 0.0
        driving._handle_arrival_gate()
        _finish_timed_state(self.app)
        assert isinstance(self.app.state, FacilityArrivalState)
        self._finish_delivery()
        assert isinstance(self.app.state, ArrivalState)

        profile = self.app.ctx.profile
        assert profile is not None
        self.result.deliveries = profile.career.deliveries
        self.result.destination = driving.job.destination
        self.result.current_city = profile.current_city
        self.result.remaining_miles = driving.trip.remaining_miles
        return self.result

    def read_settlement_lines(self) -> PlaytestResult:
        """Arrow through every settlement line so each is spoken in order."""
        from freight_fate.states.driving import ArrivalState

        assert self.app is not None
        state = self.app.state
        assert isinstance(state, ArrivalState)
        for _ in range(len(state.items) - 1):
            state.handle_event(key_event(pygame.K_DOWN))
        return self.result

    def continue_to_next_delivery(self, *, job_rank: int = 0, route_rank: int = 0) -> None:
        """Leave settlement and dispatch another load on the same career."""
        from freight_fate.states.city import CityMenuState, JobBoardState, PickupFacilityState
        from freight_fate.states.driving import ArrivalState, DrivingState

        assert isinstance(self.app.state, ArrivalState)
        self.app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(self.app.state, CityMenuState)
        self._select_current_menu_text("Dispatch board")
        assert isinstance(self.app.state, JobBoardState)
        if self.app.state.assigned_mode:
            self._accept_assigned_job(job_rank)
        else:
            self._choose_unlocked_job(job_rank)
        assert isinstance(self.app.state, DrivingState)
        self.app.state.trip.position_mi = self.app.state.trip.total_miles
        self.app.state.trip.finished = True
        self.app.state.truck.velocity_mps = 0.0
        self.app.state.update(1 / 60)
        _finish_timed_state(self.app)
        assert isinstance(self.app.state, PickupFacilityState)
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        _finish_timed_state(self.app)
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        if self.app.state.__class__.__name__ == "RouteSelectState":
            self._choose_route(route_rank)
        assert isinstance(self.app.state, DrivingState)
        self.driving = self.app.state
        self._neutralize_random_trip_friction()

    def prepare_for_driving(self, *, speed_mph: float = 30.0) -> None:
        """Put the active delivery truck in a road-ready deterministic state."""
        assert self.driving is not None
        driving = self.driving
        if not driving.truck.engine_on:
            driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.automatic = True
        driving.truck.set_air_ready(parking_brake=False)
        driving.truck.velocity_mps = speed_mph / 2.2369362920544

    def press_key(self, key: int, unicode: str = "") -> None:
        assert self.driving is not None
        self.driving.handle_event(key_event(key, unicode))

    def drive_frames(self, frames: int) -> None:
        for _ in range(frames):
            self._drive_one_frame()

    def add_npc_traffic_ahead(
        self,
        *,
        behavior: str = "merging_vehicle",
        gap_mi: float = 0.8,
        speed_mph: float = 42.0,
        relative_lane: int = 1,
    ) -> NPCVehicle:
        assert self.driving is not None
        vehicle = NPCVehicle(
            "harness:npc",
            self.driving.trip.position_mi + gap_mi,
            speed_mph,
            speed_mph,
            relative_lane,
            behavior,
        )
        self.driving.trip.traffic_manager.vehicles = [vehicle]
        return vehicle

    def add_traffic_pressure_ahead(
        self,
        *,
        gap_mi: float = 2.0,
        kind: str = "exit",
        direction: str = "right",
        reason: str = "exit traffic for harness ramp",
    ) -> TrafficPressure:
        assert self.driving is not None
        start = self.driving.trip.position_mi + gap_mi
        pressure = TrafficPressure(
            start,
            start + 1.0,
            kind,
            direction,
            0.8,
            42.0,
            reason,
        )
        self.driving.trip.traffic_pressures = [pressure]
        return pressure

    def emit_trip_event(self, kind, text: str, data: dict | None = None) -> None:
        """Re-enable one deterministic trip event after default neutralization."""
        from freight_fate.sim.trip_models import TripEvent

        assert self.driving is not None
        self.driving._handle_trip_event(TripEvent(kind, text, data or {}))

    def select_menu_item(self, label: str) -> None:
        """Choose a menu item by its label instead of by blind Enter presses.

        The pickup and arrival menus grow items as features land -- the
        walk-around, refusing a trailer -- and a harness that presses Enter a
        fixed number of times silently starts driving a different button when
        that happens. Naming what it wants keeps a playtest honest.
        """
        assert self.app is not None
        state = self.app.state
        labels = [item.text for item in state.items]
        assert label in labels, f"{label!r} not in {labels}"
        while state.items[state.index].text != label:
            state.handle_event(key_event(pygame.K_DOWN))
        state.handle_event(key_event(pygame.K_RETURN))

    def menu_labels(self) -> list[str]:
        """Every option on the current menu, for reviewing what is reachable."""
        assert self.app is not None
        return [item.text for item in getattr(self.app.state, "items", [])]

    def record_equipment(self) -> PlaytestResult:
        """Capture the tractor, the trailer, and how the freight is handled.

        Read rather than driven, so it is safe to call at any point in a run.
        """
        from freight_fate.models.carrier_fleet import fleet_tier_for_level, slip_seat_pool
        from freight_fate.models.trailer_yard import delivery_plan, pickup_plan
        from freight_fate.models.trucks import TRUCK_CATALOG

        assert self.app is not None
        profile = self.app.ctx.profile
        assert profile is not None
        key = profile.active_truck_key()
        self.result.assigned_truck = key
        self.result.assigned_truck_label = TRUCK_CATALOG[key].label
        if not profile.owns_equipment():
            fleet_tier_for_level(int(profile.career.level))
            self.result.slip_seat_pool = [
                TRUCK_CATALOG[spare].label for spare in slip_seat_pool(profile)
            ]
        job = getattr(self.app.state, "job", None) or getattr(self.driving, "job", None)
        if job is None:
            return self.result
        plan = pickup_plan(job, profile)
        self.result.pickup_mode = "drop and hook" if plan.is_drop_hook else "live load"
        self.result.pickup_minutes = plan.minutes
        self.result.detention_minutes = plan.detention_minutes
        self.result.detention_pay = plan.detention_pay
        if plan.trailer is not None:
            self.result.trailer_number = plan.trailer.number
            self.result.trailer_condition = plan.trailer.condition_text
            self.result.trailer_defect = plan.trailer.defect or ""
        drop = delivery_plan(job, profile)
        self.result.delivery_mode = "drop the trailer" if drop.is_drop_hook else "live unload"
        self.result.delivery_minutes = drop.minutes
        return self.result

    def walk_around_trailer(self) -> PlaytestResult:
        """Do the pre-trip on the hooked trailer, if there is one to walk."""
        if "Walk around the trailer" not in self.menu_labels():
            return self.result
        self.select_menu_item("Walk around the trailer")
        return self.result

    def refuse_trailer(self) -> bool:
        """Send a defective trailer back; returns whether there was one to refuse."""
        if "Refuse this trailer" not in self.menu_labels():
            return False
        self.select_menu_item("Refuse this trailer")
        self.result.trailer_refused = True
        return True

    def _select_current_menu_text(self, text: str) -> None:
        assert self.app is not None
        for _ in range(len(self.app.state.items)):
            if self.app.state.items[self.app.state.index].text == text:
                break
            self.app.state.handle_event(key_event(pygame.K_DOWN))
        else:
            choices = [item.text for item in self.app.state.items]
            raise AssertionError(f"Menu item {text!r} not reachable with Down: {choices}")
        self.app.state.handle_event(key_event(pygame.K_RETURN))

    def _choose_unlocked_job(self, rank: int) -> None:
        assert self.app is not None
        board = self.app.state
        unlocked = [(i, job) for i, job in enumerate(board.jobs) if not board._locked_reason(job)]
        assert unlocked
        unlocked.sort(key=lambda item: item[1].distance_mi)
        target_index, _job = unlocked[rank % len(unlocked)]
        for _ in range(len(board.items)):
            if board.index == target_index:
                break
            board.handle_event(key_event(pygame.K_DOWN))
        else:
            raise AssertionError(f"Job index {target_index} not keyboard reachable")
        self.app.state.handle_event(key_event(pygame.K_RETURN))

    def _accept_assigned_job(self, rank: int) -> None:
        assert self.app is not None
        board = self.app.state
        for _ in range(rank):
            decline_index = next(
                (i for i, item in enumerate(board.items) if item.text.startswith("Decline")), None
            )
            if decline_index is None:
                break  # out of declines or no alternative freight
            for _ in range(len(board.items)):
                if board.index == decline_index:
                    break
                board.handle_event(key_event(pygame.K_DOWN))
            else:
                raise AssertionError("Decline action not keyboard reachable")
            board.handle_event(key_event(pygame.K_RETURN))
        board.handle_event(key_event(pygame.K_HOME))
        board.handle_event(key_event(pygame.K_RETURN))

    def _choose_route(self, rank: int) -> None:
        assert self.app is not None
        route_state = self.app.state
        target_index = rank % len(route_state.routes)
        for _ in range(len(route_state.items)):
            if route_state.index == target_index:
                break
            route_state.handle_event(key_event(pygame.K_DOWN))
        else:
            raise AssertionError(f"Route index {target_index} not keyboard reachable")
        route_state.handle_event(key_event(pygame.K_RETURN))

    def _neutralize_random_trip_friction(self) -> None:
        from freight_fate.sim.weather import WeatherKind

        assert self.driving is not None
        self.driving.trip._hazard_check_mi = 1e9
        self.driving.trip._inspection_check_mi = 1e9
        self.driving.trip.traffic_manager.vehicles = []
        self.driving.trip.traffic_pressures = []
        self.driving.weather.current = WeatherKind.CLEAR

    def _drive_one_frame(self) -> None:
        driving = self.driving
        assert driving is not None
        limit_mph, _reason = driving.trip.speed_limit_at(driving.trip.position_mi)
        target_mph = max(25.0, limit_mph + 5.0)
        if driving.truck.speed_mph > target_mph:
            driving.truck.throttle = 0.0
            driving.truck.brake = 0.5
        else:
            driving.truck.throttle = 0.8
            driving.truck.brake = 0.0

        driving.truck.grip = 1.0
        driving.truck.grade = 0.0
        driving.truck.fuel_gal = driving.truck.specs.fuel_tank_gal
        driving.truck.air_pressure_psi = driving.truck.specs.air_governor_cut_out_psi
        driving.truck.parking_brake = False
        driving.truck.auto_shift()
        driving.truck.update(1 / 60)
        for event in driving.trip.update(1 / 60):
            driving._handle_trip_event(event)
        driving._update_hazard(1 / 60)
        if driving._hazard_deadline is not None:
            driving.truck.velocity_mps = 5.0
