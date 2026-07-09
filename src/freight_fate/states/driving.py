# ruff: noqa: F403,F405,I001
"""Compatibility facade for the driving state and related menu states."""

from __future__ import annotations

from .driving_core import *
from .driving_controls import DrivingControlsMixin
from .driving_events import DrivingEventMixin
from .driving_updates import DrivingUpdateMixin


class DrivingState(DrivingControlsMixin, DrivingUpdateMixin, DrivingEventMixin, State):
    def __init__(
        self,
        ctx,
        job: Job,
        route: Route,
        trip_seed: int | None = None,
        phase: str = DRIVE_PHASE_DELIVERY,
        start_hour: float | None = None,
    ) -> None:
        super().__init__(ctx)
        self.job = job
        self.route = route
        self.phase = phase
        self.trip_seed = trip_seed if trip_seed is not None else random.randrange(2**31)
        self.resumed = False
        profile = ctx.profile
        self.truck = TruckState(specs=profile.truck_specs())
        # Loaded delivery runs carry the job's payload; pickup deadheads and
        # empty bobtail repositions run light. Gross weight drives the physics,
        # so a heavy load pulls away gently and lugs on grades.
        self.truck.cargo_kg = job.weight_tons * KG_PER_TON if phase == DRIVE_PHASE_DELIVERY else 0.0
        self.truck.transmission.automatic = ctx.settings.automatic_transmission
        self.truck.fuel_gal = min(profile.truck_fuel_gal, self.truck.specs.fuel_tank_gal)
        self.truck.damage_pct = profile.truck_damage_pct
        self.truck.set_cold_air_start()
        self.start_damage = profile.truck_damage_pct
        region = ctx.world.city(job.origin).region
        self.weather = WeatherSystem(
            region,
            seed=self.trip_seed,
            provider=ctx.real_weather_provider(),
            game_hours=profile.game_hours,
        )
        self._weather_source_real = ctx.settings.real_weather
        trip_start_hour = profile.game_hours % 24.0 if start_hour is None else start_hour
        self.trip = Trip(
            route,
            self.truck,
            self.weather,
            time_scale=ctx.settings.time_scale,
            seed=self.trip_seed,
            start_hour=trip_start_hour,
            imperial=ctx.settings.imperial_units,
            hazard_scale=hos.hazard_scale(ctx.settings.hos_mode),
        )
        self.lane = LaneKeeping(seed=self.trip_seed)
        self._day_music_sequence = select_drive_music_sequence(
            self.route, self.trip_seed, 12.0, self.weather.current
        )
        self._night_music_sequence = select_drive_music_sequence(
            self.route, self.trip_seed, 0.0, self.weather.current
        )
        self._day_music_index = 0
        self._night_music_index = 0
        self._music_elapsed_s = 0.0
        self._music_night = is_night(self.trip.local_start_hour)
        self.tutorial = Tutorial(ctx) if not profile.tutorial_done else None

        self.hos = profile.hos  # shift clock lives on the profile
        self.hos_fine_count = 0  # escalates with each failed inspection
        self.enforcement_events: set[str] = set()
        self.out_of_service_count = 0
        self._drowsy_said = False
        self._severe_said = False
        self._fatigue_cue_gm = 0.0  # game minutes since the last drowsy cue
        self._microsleep_deadline: float | None = None  # reaction window, real seconds
        self._microsleep_gm = 0.0  # game minutes since the last nod
        self._microsleep_cooldown_gm = 0.0
        self._microsleep_misses = 0  # consecutive nods drifted off the road
        self._hazard_deadline: float | None = None
        self._last_event_message = ""  # last spoken route announcement, for replay
        self._speed_announce_timer = 0.0
        self._last_announced_mph = 0.0
        self._speeding_timer = 0.0
        self.speeding_strikes = 0
        # Trooper pull-overs: a strike inside a patrol window may get you stopped
        # for an immediate ticket, separate from the silent at-delivery strikes.
        self.speeding_tickets = 0
        self.ticket_fines_paid = 0.0
        self._pull_over: str | None = None  # None | "lights" | "stopping"
        self._pull_over_start_mi = 0.0
        self._pull_over_signaled = False
        self._pull_over_over = 0.0  # mph over the limit when clocked
        self._pull_over_limit = 0.0  # posted limit when clocked
        # Deterministic, save-safe stream for "did a patrol catch you" rolls, kept
        # apart from the trip's hazard/zone/inspection streams.
        self._patrol_rng = random.Random(None if trip_seed is None else trip_seed ^ 0xB0A1)
        self._rescue_offered = False
        self._signal_timer = 0.0
        self._exit_stop = None  # armed exit, set with X
        self._ramp_mi: float | None = None  # ramp distance left, once taken
        self._ramp_stop = None
        self._ramp_end_said = False
        self._destination_exit_taken = False
        self._missed_destination_exit_said = False
        self._destination_exit_announced_key = ""
        self._cruise_mph: float | None = None
        self._cruise_throttle = 0.0
        self._cruise_applied = 0.0
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False
        self._arrival_stop_said = False
        self._arrival_full_stop_said = False
        self._arrival_menu_open = False
        self._air_ready_said = self.truck.air_ready
        self._low_air_said = self.truck.air_low_warning
        self._spring_brake_said = self.truck.spring_brakes_active
        self._brake_lockout_cue_timer = 0.0
        self._brake_air_hissed = False  # rising-edge guard for the brake-apply hiss
        self._lane_rumble_timer = 0.0
        self._lane_guidance_state = "center"
        self._reverse_cue_active = False
        self._status_text = f"Press {self.ctx.control_hint('engine')} to start the engine."

    def _terse_speech(self) -> bool:
        return self.ctx.settings.speech_verbosity == 0

    # -- save and resume -----------------------------------------------------------

    def snapshot(self) -> dict:
        """Everything needed to resume this active drive from a save."""
        job = self.job
        kind = "pickup_drive" if self.phase == DRIVE_PHASE_PICKUP else "delivery"
        return {
            "kind": kind,
            "job": job_payload(job),
            "route_cities": list(self.route.cities),
            "route_kind": (
                "facility_approach" if self.phase == DRIVE_PHASE_PICKUP else "corridor_itinerary"
            ),
            "navigation_schema": 1,
            "trip_seed": self.trip_seed,
            "start_hour": self.trip.start_hour,
            "position_mi": self.trip.position_mi,
            "game_minutes": self.trip.game_minutes,
            "toll_charges": [
                {
                    "name": charge.name,
                    "amount": charge.amount,
                }
                for charge in self.trip.toll_charges
            ],
            "start_damage": self.start_damage,
            "speeding_strikes": self.speeding_strikes,
            "air_brake": self.truck.air_brake_snapshot(),
            "engine_on": self.truck.engine_on,
            "hos": self.hos.to_dict(),
            "fatigue": self.ctx.profile.fatigue,
            "hos_fine_count": self.hos_fine_count,
            "enforcement_events": sorted(self.enforcement_events),
            "out_of_service_count": self.out_of_service_count,
            "speeding_tickets": self.speeding_tickets,
            "ticket_fines_paid": self.ticket_fines_paid,
            "lane_offset": self.lane.offset,
        }

    @classmethod
    def from_snapshot(cls, ctx, data: dict) -> DrivingState | None:
        """Rebuild a saved active drive; None if the snapshot is unreadable."""
        try:
            j = data["job"]
            kind = str(data.get("kind", "delivery"))
            phase = DRIVE_PHASE_PICKUP if kind == "pickup_drive" else DRIVE_PHASE_DELIVERY
            if phase == DRIVE_PHASE_PICKUP:
                route = ctx.world.facility_approach_route(j["origin"], j["origin_location"])
            else:
                route = ctx.world.route_from_cities(data["route_cities"])
            if route is None:
                return None
            # Pre-slug saves store display names; canonicalize before any
            # world lookup so an old trip resumes instead of being dropped.
            job = normalize_job_cities(job_from_payload(j), ctx.world)
            position_mi = float(data.get("position_mi", 0.0))
            game_minutes = float(data.get("game_minutes", 0.0))
            job.deadline_game_h = fair_active_deadline(
                job,
                route,
                hours_used=game_minutes / 60.0,
                position_mi=position_mi,
                world=ctx.world,
            )
            state = cls(
                ctx,
                job,
                route,
                trip_seed=int(data["trip_seed"]),
                phase=phase,
                start_hour=float(data.get("start_hour", ctx.profile.game_hours % 24.0)),
            )
            state.resumed = True
            state.start_damage = float(data["start_damage"])
            state.speeding_strikes = int(data["speeding_strikes"])
            state.trip.restore(position_mi, game_minutes)
            state.trip.restore_toll_charges(list(data.get("toll_charges", ())))
            state.truck.restore_air_brake_snapshot(data.get("air_brake"), default_ready=True)
            if bool(data.get("engine_on", False)):
                state.truck.start_engine()
            state._air_ready_said = state.truck.air_ready
            state._low_air_said = state.truck.air_low_warning
            state._spring_brake_said = state.truck.spring_brakes_active
            # HOS and fatigue: absent in pre-1.5 snapshots, defaulting to a
            # fresh clock and a rested driver.
            if "hos" in data:
                ctx.profile.hos = HosClock.from_dict(data["hos"])
                state.hos = ctx.profile.hos
            ctx.profile.fatigue = max(
                0.0, min(100.0, float(data.get("fatigue", ctx.profile.fatigue)))
            )
            state.hos_fine_count = int(data.get("hos_fine_count", 0))
            state.enforcement_events = {str(key) for key in data.get("enforcement_events", [])}
            state.out_of_service_count = int(data.get("out_of_service_count", 0))
            state.speeding_tickets = int(data.get("speeding_tickets", 0))
            state.ticket_fines_paid = float(data.get("ticket_fines_paid", 0.0))
            state.lane.offset = float(data.get("lane_offset", 0.0))
            return state
        except (KeyError, TypeError, ValueError):
            log.warning("Could not resume saved trip", exc_info=True)
            return None

    # -- lifecycle ---------------------------------------------------------------

    def enter(self) -> None:
        if getattr(self, "_entered_once", False):
            return
        self._entered_once = True
        self.ctx.clear_music_rotation()
        self.ctx.audio.stop_music(800)
        self._play_current_music(fade_ms=2500)
        self.ctx.audio.set_weather(self.weather.effects.sound)
        self.ctx.audio.set_wind(self.weather.effects.wind)
        mode = "automatic" if self.truck.transmission.automatic else "manual"
        now = clock_text(self.trip.local_hour)
        if self.resumed:
            hours_used = self.trip.game_minutes / 60.0
            drive_name = "pickup drive" if self.phase == DRIVE_PHASE_PICKUP else "loaded delivery"
            destination = (
                self._pickup_facility_text()
                if self.phase == DRIVE_PHASE_PICKUP
                else self.job.spoken_destination
            )
            progress = (
                self._pickup_progress_summary()
                if self.phase == DRIVE_PHASE_PICKUP
                else self.trip.progress_summary(self.ctx.settings.imperial_units)
            )
            if self._terse_speech():
                self.ctx.say(
                    f"Resuming {drive_name}: {destination}. {progress} "
                    f"{hours_used:.1f} of {self.job.deadline_game_h:.0f} hours used. "
                    f"{now}. {mode}. {self.weather.describe(self.ctx.settings.imperial_units)}. "
                    f"{self._parked_entry_status()}",
                    interrupt=False,
                )
            else:
                self.ctx.say(
                    f"Resuming your {drive_name}: {self.job.weight_tons:.0f} tons of "
                    f"{self.job.cargo.label} to {destination}. "
                    f"{progress} "
                    f"{hours_used:.1f} hours used of {self.job.deadline_game_h:.0f}. "
                    f"It is {now}. Transmission is {mode}. "
                    f"Weather: {self.weather.describe(self.ctx.settings.imperial_units)}. "
                    f"You are parked. {self._engine_entry_instruction()} "
                    "When air pressure is ready, press "
                    f"{self.ctx.control_hint('parking_brake')} to release the parking brake.",
                    interrupt=False,
                )
        else:
            objective = (
                f"Pickup dispatch: deadhead from the terminal to {self._pickup_facility_text()}. "
                if self.phase == DRIVE_PHASE_PICKUP
                else f"Loaded for {self._destination_facility_text()}. "
                f"{self.trip.progress_summary(self.ctx.settings.imperial_units)} "
            )
            if self._terse_speech():
                self.ctx.say(
                    f"{objective}{now}. {mode}. {self.weather.describe(self.ctx.settings.imperial_units)}. "
                    f"{self._parked_entry_status()}",
                    interrupt=False,
                )
            else:
                self.ctx.say(
                    f"You are at the wheel. {objective}It is {now}. "
                    f"Transmission is {mode}. "
                    f"Weather: {self.weather.describe(self.ctx.settings.imperial_units)}. "
                    f"{self._engine_entry_instruction()} "
                    f"{self.ctx.control_hint('help')} lists the controls.",
                    interrupt=False,
                )
        if self.tutorial:
            self.tutorial.begin()
        if self.phase == DRIVE_PHASE_DELIVERY:
            self._record_weather_achievement(event=False)
            if not self.truck.transmission.automatic:
                self.ctx.award_achievement("manual_driver", event=False, interrupt=False)

    def _engine_entry_instruction(self) -> str:
        if self.truck.engine_on:
            return "Engine idling; build air pressure if needed."
        return (
            f"Press {self.ctx.control_hint('engine')} to start the engine and build air pressure."
        )

    def _parked_entry_status(self) -> str:
        engine = "Engine idling" if self.truck.engine_on else "Engine off"
        air = (
            f"air {self.truck.air_pressure_psi:.0f} psi"
            if not self.truck.air_ready
            else "air ready"
        )
        brake = "parking brake set" if self.truck.parking_brake else "parking brake released"
        return f"{engine}, {air}, {brake}."

    def _record_weather_achievement(self, *, event: bool = True) -> None:
        p = self.ctx.profile
        if p is None:
            return
        kind = self.weather.current
        add_unique_stat(p, "weather_seen", kind.name)
        if kind in {WeatherKind.RAIN, WeatherKind.HEAVY_RAIN}:
            self.ctx.award_achievement("rain_driver", event=event)
        elif kind in {WeatherKind.SNOW, WeatherKind.WIND}:
            self.ctx.award_achievement("winter_or_wind", event=event)
        elif kind in {WeatherKind.FOG, WeatherKind.THUNDERSTORM}:
            self.ctx.award_achievement("low_visibility", event=event)

    def exit(self) -> None:
        self.ctx.audio.horn_stop()
        self.ctx.audio.stop_world()
        self.ctx.audio.stop_music(600)

    # -- input ---------------------------------------------------------------------


from .driving_menu_states import (  # noqa: E402,F401
    AbandonJobConfirmationState,
    ArrivalState,
    DrivingStatusScreenState,
    DrivingStatusState,
    FacilityArrivalState,
    PauseMenuState,
)
from .driving_rest_states import (  # noqa: E402,F401
    ParkingFullState,
    RestStopState,
    ShoulderSleepConfirmationState,
    TrafficStopState,
)
