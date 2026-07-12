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
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


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

        self.app.state.trip.position_mi = self.app.state.trip.total_miles
        self.app.state.trip.finished = True
        self.app.state.truck.velocity_mps = 0.0
        self.app.state.update(1 / 60)
        _finish_timed_state(self.app)
        assert isinstance(self.app.state, PickupFacilityState)
        if stop_at_pickup:
            return self.result
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        _finish_timed_state(self.app)
        self.app.state.handle_event(key_event(pygame.K_RETURN))
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
        route = self.app.ctx.world.route_from_cities([origin, destination])
        if route is None:
            raise SystemExit(f"No supported route {origin} -> {destination}")
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
        driving = DrivingState(self.app.ctx, job, route, phase="delivery")
        self.app.push_state(driving)
        self.driving = driving
        self._neutralize_random_trip_friction()
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
