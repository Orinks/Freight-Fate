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
        city_service_key: str = "",
        start_hour: float | None = None,
    ) -> None:
        super().__init__(ctx)
        self.job = job
        self.route = route
        self.phase = phase
        self.city_service_key = city_service_key
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
        region = ctx.world.cities[job.origin].region
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
            career_hours=profile.game_hours,
        )
        self.lane = LaneKeeping(seed=self.trip_seed)
        self._day_music_sequence = select_drive_music_sequence(
            self.route, self.trip_seed, 12.0, self.weather.current
        )
        self._night_music_sequence = select_drive_music_sequence(
            self.route, self.trip_seed, 0.0, self.weather.current
        )
        self._music_night = is_night(trip_start_hour)
        self.radio = RadioState.from_settings(ctx.settings)
        self._radio_backend = _DrivingRadioBackend(self)
        # Station rotation: per-station shuffled song order, with host breaks
        # every few songs on the stations that have a live host.
        self._radio_station_id = ""
        self._radio_playlist: tuple[str, ...] = ()
        self._radio_hosts: tuple[str, ...] = ()
        self._radio_track_index = 0
        self._radio_host_index = 0
        self._radio_elapsed_s = 0.0
        self._radio_tracks_since_host = 0
        self._radio_playing_host = False
        # Reception: signal re-checked on a slow cadence while driving so
        # ranged stations fade with distance and drop past their contour.
        self._radio_signal_timer = 0.0
        self._radio_static_timer = 0.0
        self._radio_signal_factor = 1.0
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
        # Congestion badges: both kinds of slow inside one trip earns a nod.
        self.construction_seen = False
        self.traffic_seen = False
        self._brake_squeal_cooldown_s = 0.0  # hot-brake squeal cue spacing
        # Trooper pull-overs: a strike inside a patrol window may get you stopped
        # for an immediate ticket, separate from the silent at-delivery strikes.
        self.speeding_tickets = 0
        self.ticket_fines_paid = 0.0
        self._pull_over: str | None = None  # None | "lights" | "stopping"
        self._pull_over_start_mi = 0.0
        self._pull_over_signaled = False
        self._pull_over_over = 0.0  # mph over the limit when clocked
        self._pull_over_limit = 0.0  # posted limit when clocked
        self._pull_over_kind = "speeding"
        self._pull_over_title = "Traffic stop"
        self._pull_over_summary = ""
        self._pull_over_fine = 0.0
        self._pull_over_reputation_hit = 0.0
        self._pull_over_return = "Back on the highway. Watch your speed."
        self._pull_over_warning_level = 0
        self.failure_to_stop_count = 0
        self._weigh_station_notice_key = ""
        self._unsafe_damage_stop_key = ""
        # Deterministic, save-safe stream for "did a patrol catch you" rolls, kept
        # apart from the trip's hazard/zone/inspection streams.
        self._patrol_rng = random.Random(None if trip_seed is None else trip_seed ^ 0xB0A1)
        self._rescue_offered = False
        self._signal_timer = 0.0
        self._exit_stop = None  # active route exit
        self._exit_signal_on = False
        self._exit_signal_canceled = False
        self._exit_lane_alignment = 0.0
        self._exit_lane_prompt_said = False
        self._exit_lane_ready_said = False
        self._exit_commit_said = False
        self._ramp_mi: float | None = None  # ramp distance left, once taken
        self._ramp_stop = None
        self._ramp_end_said = False
        # Ramp terminal control for the active ramp: what meets you where the
        # ramp joins the surface road, and the light's cycle state if a signal.
        self._ramp_control = ""  # "signal" | "stop" | "none" | "" (no ramp)
        self._ramp_light_offset_s = 0.0  # seeded phase into the light cycle
        self._ramp_light_timer = 0.0  # real seconds since the ramp was taken
        self._ramp_light_announced = False
        self._ramp_light_was_red = False
        self._ramp_light_flip_said = False
        self._ramp_terminal_done = False
        self._ramp_waiting_at_light = False
        self._destination_exit_taken = False
        self._missed_destination_exit_said = False
        self._destination_exit_announced_key = ""
        # Surface chain: after the destination ramp, the drive continues on
        # the facility's real street chain to the gate instead of a scripted
        # arrival. The highway trip is kept for records; the active trip
        # becomes the surface route.
        self._surface_chain = False
        self._highway_trip = None
        self._cruise_mph: float | None = None
        self._cruise_throttle = 0.0
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False
        self._arrival_stop_said = False
        self._arrival_full_stop_said = False
        self._arrival_menu_open = False
        self._city_service_enter_ready = False
        self._air_ready_said = self.truck.air_ready
        self._low_air_said = self.truck.air_low_warning
        self._spring_brake_said = self.truck.spring_brakes_active
        self._brake_lockout_cue_timer = 0.0
        self._brake_air_hissed = False  # rising-edge guard for the brake-apply hiss
        self._lane_rumble_timer = 0.0
        # Discrete lanes: tap-change progress (assist off), closed-lane
        # policing, hazard-dodge context, and keep-right pressure.
        self._lane_change_target: int | None = None
        self._lane_change_timer = 0.0
        self._lane_signal_timer = 0.0
        self._merge_deadline: float | None = None
        self._hazard_dodgeable = False
        self._hazard_lane = 0
        self._left_lane_s = 0.0
        self._keep_right_nags = 0
        self._ambient_event_cooldown_s = 0.0
        self._pending_ambient_event: tuple[str, str | None] | None = None
        self._lane_guidance_state = "center"
        self._reverse_cue_active = False
        self._status_text = f"Press {self.ctx.control_hint('engine')} to start the engine."

    def _terse_speech(self) -> bool:
        return self.ctx.settings.speech_verbosity == 0

    def _absolute_game_hour(self, trip_minutes: float | None = None) -> float:
        if trip_minutes is None:
            trip_minutes = self.trip.game_minutes
        return self.ctx.profile.game_hours + trip_minutes / 60.0

    def _logbook_location(self) -> str:
        if self.phase == DRIVE_PHASE_PICKUP:
            return f"local route to {self._pickup_facility_text()}"
        route = self.trip.route  # the surface chain once off the highway
        if not route.legs:
            return self.job.destination
        index = max(0, min(self.trip.current_leg_index, len(route.legs) - 1))
        leg = route.legs[index]
        if self._surface_chain:
            return f"{leg.highway} in {self.job.destination}"
        start = route.cities[index]
        end = route.cities[index + 1]
        return f"{leg.highway} from {start} to {end}"

    # -- save and resume -----------------------------------------------------------

    def snapshot(self) -> dict:
        """Everything needed to resume this active drive from a save."""
        job = self.job
        if self.phase == DRIVE_PHASE_PICKUP:
            kind = "pickup_drive"
        elif self.phase == DRIVE_PHASE_CITY_SERVICE:
            kind = "city_service_drive"
        else:
            kind = "delivery"
        return {
            "kind": kind,
            "job": job_payload(job),
            "route_cities": list(self.route.cities),
            "route_kind": (
                "facility_approach"
                if self.phase == DRIVE_PHASE_PICKUP
                else "city_service_approach"
                if self.phase == DRIVE_PHASE_CITY_SERVICE
                else "corridor_itinerary"
            ),
            "city_service_key": self.city_service_key,
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
            "failure_to_stop_count": self.failure_to_stop_count,
            "lane_offset": self.lane.offset,
            "lane_index": self.lane.lane,
            # Mid-surface-chain saves resume on the street chain; absent on
            # older saves, which resume exactly as before.
            "surface_chain": self._surface_chain,
        }

    @classmethod
    def from_snapshot(cls, ctx, data: dict) -> DrivingState | None:
        """Rebuild a saved active drive; None if the snapshot is unreadable."""
        try:
            j = data["job"]
            kind = str(data.get("kind", "delivery"))
            if kind == "pickup_drive":
                phase = DRIVE_PHASE_PICKUP
            elif kind == "city_service_drive":
                phase = DRIVE_PHASE_CITY_SERVICE
            else:
                phase = DRIVE_PHASE_DELIVERY
            if phase == DRIVE_PHASE_PICKUP:
                route = ctx.world.facility_approach_route(j["origin"], j["origin_location"])
            elif phase == DRIVE_PHASE_CITY_SERVICE:
                route = ctx.world.city_service_route(
                    j["origin"], str(data.get("city_service_key", ""))
                )
            else:
                route = ctx.world.route_from_cities(data["route_cities"])
            if route is None:
                return None
            job = job_from_payload(j)
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
                city_service_key=str(data.get("city_service_key", "")),
                start_hour=float(data.get("start_hour", ctx.profile.game_hours % 24.0)),
            )
            state.resumed = True
            state.start_damage = float(data["start_damage"])
            state.speeding_strikes = int(data["speeding_strikes"])
            state.trip.restore(position_mi, game_minutes)
            state.trip.restore_toll_charges(list(data.get("toll_charges", ())))
            if bool(data.get("surface_chain", False)):
                # The save was made on the facility's street chain: re-enter
                # it (deterministic rebuild; the chain shares the restored
                # toll ledger). If the data no longer offers a chain, fall
                # back to the highway route just short of the destination
                # exit so the player simply takes it again.
                state._destination_exit_taken = True
                if state._begin_surface_chain(announce=False):
                    state.trip.restore(position_mi, game_minutes)
                else:
                    state._destination_exit_taken = False
                    state.trip.restore(
                        max(0.0, state.trip.total_miles - 2.0), game_minutes
                    )
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
            state.failure_to_stop_count = int(data.get("failure_to_stop_count", 0))
            state.lane.offset = float(data.get("lane_offset", 0.0))
            state.lane.lane = max(0, int(data.get("lane_index", 0)))
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
        self._play_radio_current()
        self.ctx.audio.set_weather(self.weather.effects.sound)
        self.ctx.audio.set_wind(self.weather.effects.wind)
        mode = "automatic" if self.truck.transmission.automatic else "manual"
        now = clock_text(self.trip.current_hour)
        if self.resumed:
            hours_used = self.trip.game_minutes / 60.0
            if self.phase == DRIVE_PHASE_PICKUP:
                drive_name = "pickup drive"
                destination = self._pickup_facility_text()
            elif self.phase == DRIVE_PHASE_CITY_SERVICE:
                drive_name = "city service drive"
                destination = self._city_service_text()
            else:
                drive_name = "loaded delivery"
                destination = self.job.destination
            progress = (
                self._pickup_progress_summary()
                if self.phase == DRIVE_PHASE_PICKUP
                else self._city_service_progress_summary()
                if self.phase == DRIVE_PHASE_CITY_SERVICE
                else self.trip.progress_summary(self.ctx.settings.imperial_units)
            )
            if self.phase == DRIVE_PHASE_CITY_SERVICE:
                self.ctx.say(
                    f"Resuming your {drive_name} to {destination}. "
                    f"{progress} "
                    f"{hours_used:.1f} hours used. It is {now}. "
                    f"Transmission is {mode}. Weather: {self.weather.describe()}. "
                    f"You are parked. {self._engine_entry_instruction()} "
                    "When air pressure is ready, press P to release the parking brake.",
                    interrupt=False,
                )
            elif self._terse_speech():
                self.ctx.say(
                    f"Resuming {drive_name}: {destination}. {progress} "
                    f"{hours_used:.1f} of {self.job.deadline_game_h:.0f} hours used. "
                    f"{now}. {mode}. {self.weather.describe()}. "
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
                    f"Weather: {self.weather.describe()}. "
                    f"You are parked. {self._engine_entry_instruction()} "
                    "When air pressure is ready, press "
                    f"{self.ctx.control_hint('parking_brake')} to release the parking brake.",
                    interrupt=False,
                )
        else:
            if self.phase == DRIVE_PHASE_PICKUP:
                objective = (
                    f"Pickup dispatch: deadhead from the terminal to "
                    f"{self._pickup_facility_text()}. "
                )
            elif self.phase == DRIVE_PHASE_CITY_SERVICE:
                objective = (
                    f"City service drive: follow the GPS to "
                    f"{self._city_service_text()}. Stop there, then press Enter "
                    "to go inside. "
                )
            else:
                objective = (
                    f"Loaded for {self._destination_facility_text()}. "
                    f"{self.trip.progress_summary(self.ctx.settings.imperial_units)} "
                )
            if self._terse_speech():
                self.ctx.say(
                    f"{objective}{now}. {mode}. {self.weather.describe()}. "
                    f"{self._parked_entry_status()}",
                    interrupt=False,
                )
            else:
                self.ctx.say(
                    f"You are at the wheel. {objective}It is {now}. "
                    f"Transmission is {mode}. "
                    f"Weather: {self.weather.describe()}. "
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
        seen = add_unique_stat(p, "weather_seen", kind.name)
        if kind in {WeatherKind.RAIN, WeatherKind.HEAVY_RAIN}:
            self.ctx.award_achievement("rain_driver", event=event)
        elif kind in {WeatherKind.SNOW, WeatherKind.WIND}:
            self.ctx.award_achievement("winter_or_wind", event=event)
        elif kind in {WeatherKind.FOG, WeatherKind.THUNDERSTORM}:
            self.ctx.award_achievement("low_visibility", event=event)
        if kind == WeatherKind.THUNDERSTORM:
            self.ctx.award_achievement("storm_driving", event=event)
        if seen >= len(WeatherKind):
            self.ctx.award_achievement("weather_collector", event=event)

    def exit(self) -> None:
        self.ctx.audio.horn_stop()
        self.radio.write_settings(self.ctx.settings)
        self.ctx.settings.save()
        self.ctx.audio.stop_world()
        self.ctx.audio.stop_music(600)
        self.ctx.apply_volumes()

    # -- input ---------------------------------------------------------------------


from .driving_menu_states import (  # noqa: E402,F401
    ArrivalState,
    DriverAppsState,
    DriverAppScreenState,
    DrivingStatusScreenState,
    DrivingStatusState,
    FacilityArrivalState,
    PauseMenuState,
)
from .driving_rest_states import (  # noqa: E402,F401
    EnforcementStopState,
    FelonyStopState,
    ParkingFullState,
    RestStopState,
    ShoulderSleepConfirmationState,
    TrafficStopState,
)
