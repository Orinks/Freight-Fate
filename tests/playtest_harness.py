"""Headless playtest harness for transcript-backed gameplay verification."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FREIGHT_FATE_NO_SPEECH", "1")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame


def key_event(key: int, unicode: str = ""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def _finish_timed_state(app) -> None:
    while getattr(app.state, "remaining", 0) > 0:
        app.state.update(1 / 60)


@dataclass
class PlaytestResult:
    transcript: list[str] = field(default_factory=list)
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
            line for line in lower_lines
            if "destination exit" in line or "exit for the destination" in line
        ]
        assert len(destination_exit_lines) <= 1, self.transcript_text
        assert not any("21 miles remaining" in line for line in lower_lines), self.transcript_text
        assert self.remaining_miles == 0.0


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
        self.result.transcript.append(text)

    def _say_event(self, text: str, interrupt: bool = True) -> None:
        self.result.transcript.append(f"[event] {text}")

    def start_delivery(
            self,
            *,
            profile_name: str = "Playtest",
            job_rank: int = 0,
            route_rank: int = 0) -> PlaytestResult:
        from freight_fate.states.city import (
            CityMenuState,
            JobBoardState,
            PickupFacilityState,
            RouteSelectState,
        )
        from freight_fate.states.driving import DrivingState
        from freight_fate.states.main_menu import (
            MainMenuState,
            NameEntryState,
        )

        assert self.app is not None
        self.app.push_state(MainMenuState(self.app.ctx))
        self._select_current_menu_text("New career")
        assert isinstance(self.app.state, NameEntryState)
        for ch in profile_name:
            if ch != " ":
                self.app.state.handle_event(key_event(ord(ch.lower()), ch))
        self.app.state.handle_event(key_event(pygame.K_RETURN))
        self._accept_default_onboarding_choices()
        assert isinstance(self.app.state, CityMenuState)

        self.app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(self.app.state, JobBoardState)
        self._choose_unlocked_job(job_rank)
        assert isinstance(self.app.state, DrivingState)
        assert self.app.state.phase == "pickup"

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
        assert isinstance(self.app.state, RouteSelectState)
        self._choose_route(route_rank)
        assert isinstance(self.app.state, DrivingState)
        assert self.app.state.phase == "delivery"

        self.driving = self.app.state
        self._neutralize_random_trip_friction()
        return self.result

    def drive_delivery_to_completion(self) -> PlaytestResult:
        from freight_fate.states.driving import ArrivalState, FacilityArrivalState

        assert self.app is not None
        assert self.driving is not None
        driving = self.driving
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.automatic = True
        driving.truck.set_air_ready(parking_brake=False)

        crawl_mph = 15.0
        max_frames = int(driving.trip.total_miles / crawl_mph * 3600 * 60) + 60 * 60
        for _frame in range(max_frames):
            self._drive_one_frame()
            if driving.trip.finished:
                driving.truck.velocity_mps = 0.0
                driving._handle_arrival_gate()
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

    def _select_current_menu_text(self, text: str) -> None:
        assert self.app is not None
        while self.app.state.items[self.app.state.index].text != text:
            self.app.state.handle_event(key_event(pygame.K_DOWN))
        self.app.state.handle_event(key_event(pygame.K_RETURN))

    def _accept_default_onboarding_choices(self) -> None:
        from freight_fate.states.city import CityMenuState

        assert self.app is not None
        for _step in range(6):
            if isinstance(self.app.state, CityMenuState):
                return
            assert hasattr(self.app.state, "handle_event")
            self.app.state.handle_event(key_event(pygame.K_RETURN))
        raise AssertionError(
            f"new career onboarding did not reach city menu; state={type(self.app.state).__name__}"
        )

    def _choose_unlocked_job(self, rank: int) -> None:
        assert self.app is not None
        board = self.app.state
        profile = self.app.ctx.profile
        unlocked = [
            (i, job)
            for i, job in enumerate(board.jobs)
            if not job.locked_reason(profile.career.endorsements, profile.career.level)
        ]
        assert unlocked
        unlocked.sort(key=lambda item: item[1].distance_mi)
        target_index, _job = unlocked[rank % len(unlocked)]
        while board.index != target_index:
            board.handle_event(key_event(pygame.K_DOWN))
        self.app.state.handle_event(key_event(pygame.K_RETURN))

    def _choose_route(self, rank: int) -> None:
        assert self.app is not None
        route_state = self.app.state
        target_index = rank % len(route_state.routes)
        while route_state.index != target_index:
            route_state.handle_event(key_event(pygame.K_DOWN))
        route_state.handle_event(key_event(pygame.K_RETURN))

    def _neutralize_random_trip_friction(self) -> None:
        assert self.driving is not None
        self.driving.trip._hazard_check_mi = 1e9
        self.driving.trip._inspection_check_mi = 1e9
        self.driving.trip.traffic_leads = []

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
