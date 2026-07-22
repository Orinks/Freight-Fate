# ruff: noqa: F403,F405,I001
"""Compatibility facade for the driving state and related menu states."""

from __future__ import annotations

from ..sim.pedal_latch import PedalLatch
from .driving_core import *
from .driving_controls import DrivingControlsMixin
from .driving_events import DrivingEventMixin
from .driving_location import DrivingLocationMixin
from .driving_pacenotes import DrivingPacenoteMixin
from .driving_pickup import DrivingPickupMixin
from .driving_speed_control import SpeedControlStateMixin
from .driving_updates import OVERREV_GRACE_S, DrivingUpdateMixin


class DrivingState(
    DrivingControlsMixin,
    DrivingUpdateMixin,
    SpeedControlStateMixin,
    DrivingLocationMixin,
    DrivingPickupMixin,
    DrivingEventMixin,
    DrivingPacenoteMixin,
    State,
):
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
        # A reposition run and city-service driving are the tractor alone --
        # nothing on the fifth wheel. Pickup deadheads haul their empty box.
        self.truck.trailer_attached = not (job.bobtail or phase == DRIVE_PHASE_CITY_SERVICE)
        self.truck.transmission.automatic = ctx.settings.automatic_transmission
        profile.load_truck_condition(self.truck)
        self.truck.set_cold_air_start()
        self.start_damage = profile.truck_damage_pct
        # Trip-start wear, for "this run added..." deltas at settlement
        # (mid-trip saves re-sync the profile, so the profile can't provide
        # these once the trip is underway).
        self.start_tire_wear = profile.tire_wear_pct
        self.start_brake_wear = profile.brake_wear_pct
        self.start_engine_wear = profile.engine_wear_pct
        # Rig-care buffs (quick lube, tire rotation) hold for the rest of
        # the trip and die with it -- keyed by buff group, see data/buffs.py.
        self.rig_buffs: dict[str, dict] = {}
        region = ctx.world.city(job.origin).region
        self.weather = WeatherSystem(
            region,
            seed=self.trip_seed,
            provider=ctx.real_weather_provider(),
            game_hours=profile.calendar_game_hours,
            live_weather_controls_calendar=ctx.settings.live_weather_controls_calendar,
        )
        self._weather_source_real = ctx.settings.real_weather
        self._live_weather_controls_calendar = ctx.settings.live_weather_controls_calendar
        self._traffic_source_real = ctx.settings.real_traffic
        self._parking_source_real = ctx.settings.real_parking
        trip_start_hour = profile.game_hours % 24.0 if start_hour is None else start_hour
        self.trip = Trip(
            route,
            self.truck,
            self.weather,
            time_scale=ctx.settings.time_scale,
            seed=self.trip_seed,
            start_hour=trip_start_hour,
            imperial=ctx.settings.imperial_units,
            hazard_scale=(
                hos.hazard_scale(ctx.settings.hos_mode)
                * tuning_for_time_scale(ctx.settings.time_scale).hazard_frequency
            ),
            career_hours=profile.game_hours,
            traffic_provider=ctx.real_traffic_provider(),
            parking_provider=ctx.truck_parking_provider(),
            bobtail=job.bobtail,
            destination_label=(
                job.origin_facility_text()
                if phase == DRIVE_PHASE_PICKUP
                else job.destination_facility_text()
            ),
        )
        if phase == DRIVE_PHASE_DELIVERY:
            # The destination exit, ramp terminal, and street chain own the
            # arrival speeds now. The trip's legacy last-miles arrival zones
            # were already silenced as freeway chatter, but they stayed
            # enforceable -- a silent 35 under a spoken 65, writing real
            # speeding fines on the final highway miles (owner-hit on I-10).
            self.trip.zones = [
                zone
                for zone in self.trip.zones
                if zone.reason not in ("destination approach", "facility gate")
            ]
        self.lane = LaneKeeping(seed=self.trip_seed)
        self._day_music_sequence = select_drive_music_sequence(
            self.route, self.trip_seed, 12.0, self.weather.current
        )
        self._night_music_sequence = select_drive_music_sequence(
            self.route, self.trip_seed, 0.0, self.weather.current
        )
        self._music_night = is_night(self.trip.local_start_hour)
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
        # Personal M3U stations: where each playlist left off this drive,
        # and a short hold between files so a fade-in never reads as ended.
        self._playlist_positions: dict[str, int] = {}
        self._playlist_wait_s = 0.0
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
        self._hazard_slow_hint_said = False
        self._automatic_braking_announced = False
        self._last_event_message = ""  # last spoken route announcement, for replay
        self._speed_announce_timer = 0.0
        self._last_announced_mph = 0.0
        self._speeding_timer = 0.0
        self.speeding_strikes = 0
        # Compliance grace after a posted-limit drop: braking time before
        # strikes accrue, earned only while actually slowing.
        self._enforced_limit_prev: float | None = None
        self._limit_drop_grace_s = 0.0
        # Dash overspeed alert: armed while over the limit, chiming on an
        # interval until the truck settles back under.
        self._overspeed_active = False
        self._overspeed_chime_timer = 0.0
        # Congestion badges: both kinds of slow inside one trip earns a nod.
        self.construction_seen = False
        self.traffic_seen = False
        self._brake_squeal_cooldown_s = 0.0  # hot-brake squeal cue spacing
        self._hydro_active = False  # spoken hydroplane warning edge tracking
        self._jake_slip_active = False  # spoken jake-slip warning edge tracking
        # The cylinder selector's position, like the real dash switch: J
        # engages at whatever stage was last chosen. Full retard by default
        # -- the setting every driver leaves it on until ice says otherwise.
        self._jake_selected_stage = JAKE_STAGES
        self._chains_fast_active = False  # spoken chains-over-speed warning edge tracking
        self._chain_law_warned: set[tuple[int, int]] = set()  # (area, level) spoken warnings
        self._chain_law_cited: set[tuple[int, int]] = set()  # checkpoint rolls already taken
        # Curve management: whether a hot-entry slip warning has been spoken
        # for the current curve.
        self._curve_slip_active = False
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
        # Compliance tracker for the active stop: 0..1, judged from behavior
        # (signaling and slowing), not distance. Reset on every stop-ending path.
        self._pull_over_compliance = 0.0  # seeded on begin
        self._pull_over_elapsed = 0.0  # s since the lights came on (signal grace)
        self._pull_over_prev_mph = 0.0  # last-tick speed, to classify accel vs decel
        self._pull_over_coast_s = 0.0  # consecutive s with no braking and no accel
        self._pull_over_signal_boost = False  # the one-time signal bump has fired
        self._pull_over_nosignal_hit = False  # the one-time no-signal 1/4 hit has fired
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
        self._exit_cancel_armed = False
        self._exit_right_hold_s = 0.0
        self._exit_right_taps = 0
        self._exit_tap_hint_said = False
        self._exit_countdown_said: set[float] = set()
        self._ramp_mi: float | None = None  # ramp distance left, once taken
        self._ramp_stop = None
        self._ramp_end_said = False
        # Ramp terminal control for the active ramp: what meets you where the
        # ramp joins the surface road, and the light's cycle state if a signal.
        self._ramp_control = ""  # "signal" | "stop" | "none" | "" (no ramp)
        self._ramp_light_offset_s = 0.0  # seeded phase into the light cycle
        self._ramp_light_timer = 0.0  # real seconds since the ramp was taken
        self._ramp_light_announced = False
        self._ramp_light_last_phase = ""  # "red" | "yellow" | "green", once announced
        self._ramp_terminal_done = False
        self._ramp_waiting_at_light = False
        self._ramp_creep_prompt_said = False
        self._ramp_gap_milestones_said: set[int] = set()
        self._ramp_bar_tick_timer = 0.0
        # Safety-call re-arm window (curve calls vs the Ctrl reflex).
        self._critical_curve = None
        self._critical_call_age_s = 0.0
        self._critical_respeak_at: float | None = None
        self._destination_exit_taken = False
        self._missed_destination_exit_said = False
        self._destination_exit_announced_key = ""
        # Surface chain: after the destination ramp, the drive continues on
        # the facility's real street chain to the gate instead of a scripted
        # arrival. The highway trip is kept for records; the active trip
        # becomes the surface route.
        self._surface_chain = False
        self._highway_trip = None
        # Departure chain: the mirror. A loaded run out of a chain-capable
        # origin facility starts on its streets and merges onto the highway.
        # Checked lazily on the first drive tick so restored mid-highway
        # saves are never pulled back onto the streets.
        self._departure_chain = False
        self._departure_checked = False
        # (position when computed, scan result) -- see _destination_exit_details
        self._destination_exit_cache: tuple[float, tuple[float, str, str] | None] | None = None
        self._cruise_mph: float | None = None
        self._cruise_throttle = 0.0
        self._cruise_applied = 0.0
        self._cruise_exit_mph: float | None = None
        # K arms one continuous speed-control session. The active controller
        # changes between adaptive cruise on open roads and the speed keeper in
        # restricted zones, while this target remembers what cruise should
        # resume at after the zone ends.
        self._speed_control_armed = False
        self._speed_control_target_mph: float | None = None
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False
        self._acc_follow_cue_s = 0.0  # quiet window between "Traffic ahead" cues
        self._descent_control_active = False
        self._descent_limit_state = ""
        self._descent_capture_active = False
        self._assist_exit_slowing_said = False
        self._curve_assist_active = False
        self._transition_assist_active = False
        self._keeper_mph: float | None = None
        self._keeper_throttle = 0.0
        self._keeper_zone = ""
        self._arrival_stop_said = False
        self._arrival_full_stop_said = False
        self._arrival_menu_open = False
        self._city_service_enter_ready = False
        self._air_ready_said = self.truck.air_ready
        self._low_air_said = self.truck.air_low_warning
        self._spring_brake_said = self.truck.spring_brakes_active
        self._brake_lockout_cue_timer = 0.0
        self._brake_air_hissed = False  # rising-edge guard for the brake-apply hiss
        self._pending_low_air_buzzer = False  # cold-start buzzer, held past the crank
        self._brake_peak_application = 0.0  # hardest press this application, shapes the release
        self._overrev_s = 0.0  # continuous seconds at damaging RPM
        self._overrev_warn_due = OVERREV_GRACE_S  # repeats push it out further
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
        self._air_cue_active = False  # compressor fill loop below governor release
        self._shift_recover_t = 1.0  # 0->1 recovery progress after an automatic shift ends
        self._shift_hold_rpm: float | None = None  # engine voice held here through a shift
        # Smooth only the audible engine load. Physics keeps the raw throttle,
        # while small controller and cruise changes blend into the engine bed.
        self._engine_audio_throttle = 0.0
        # Prev-frame accel/brake state, so a forward<->reverse shift needs a
        # fresh press (release then press) rather than a held control.
        self._reverse_brake_held = False
        self._reverse_accel_held = False
        # Direction-change gesture state: which change a fresh standstill
        # press has armed, and how long the control has been held since.
        # The gear engages only past DIRECTION_CHANGE_HOLD_S.
        self._direction_armed = ""
        self._direction_hold_s = 0.0
        # Latching pedals (double-tap-and-hold, see sim/pedal_latch.py):
        # a latched pedal reads as held everywhere downstream.
        self._throttle_latch = PedalLatch()
        self._brake_latch = PedalLatch()
        # Curve calls already made this trip (keys are curve entry miles).
        self._pacenote_spoken: set[int] = set()
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
        if self._departure_chain:
            return f"{leg.highway} in {self.job.origin}"
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
            "start_wear": {
                "tire": self.start_tire_wear,
                "brake": self.start_brake_wear,
                "engine": self.start_engine_wear,
            },
            "rig_buffs": self.rig_buffs,
            "speeding_strikes": self.speeding_strikes,
            "speed_control_armed": self._speed_control_armed,
            "speed_control_target_mph": self._speed_control_target_mph,
            "air_brake": self.truck.air_brake_snapshot(),
            "engine_on": self.truck.engine_on,
            "chains_on": self.truck.chains_on,
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
            # Mid-departure-chain saves resume on the origin's streets.
            "departure_chain": self._departure_chain,
            "planned_stop_key": self.trip.planned_stop_key,
            # Kept for a save opened by an older build, which knows only the name.
            "planned_stop": self.trip.planned_stop_label or None,
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
                city_service_key=str(data.get("city_service_key", "")),
                start_hour=float(data.get("start_hour", ctx.profile.game_hours % 24.0)),
            )
            state.resumed = True
            state.start_damage = float(data["start_damage"])
            # Saves from before the wear meters count deltas from the resume
            # point: the truck just loaded the profile's wear, so the run
            # simply reports a little less instead of failing to load.
            start_wear = data.get("start_wear", {})
            state.start_tire_wear = float(start_wear.get("tire", state.truck.tire_wear_pct))
            state.start_brake_wear = float(start_wear.get("brake", state.truck.brake_wear_pct))
            state.start_engine_wear = float(start_wear.get("engine", state.truck.engine_wear_pct))
            # Chains stay on the drives across a save; absent on older saves.
            state.truck.chains_on = bool(data.get("chains_on", False))
            state.rig_buffs = {
                str(group): dict(info) for group, info in dict(data.get("rig_buffs", {})).items()
            }
            state.speeding_strikes = int(data["speeding_strikes"])
            target = data.get("speed_control_target_mph")
            state._restore_speed_control_session(
                armed=bool(data.get("speed_control_armed", False)),
                target_mph=None if target is None else float(target),
            )
            state.trip.restore(position_mi, game_minutes)
            planned_key = data.get("planned_stop_key") or None
            if planned_key is None:
                # Saved before plans carried a stop identity: a bare name cannot
                # say which namesake was meant, so take the soonest reachable.
                legacy_name = data.get("planned_stop") or None
                planned_key = state.trip.resolve_stop_key(legacy_name) if legacy_name else None
            state.trip.planned_stop_key = planned_key
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
                    state.trip.restore(max(0.0, state.trip.total_miles - 2.0), game_minutes)
            elif bool(data.get("departure_chain", False)):
                # Saved on the origin facility's outbound streets: re-enter
                # the departure chain at the saved distance. If the data no
                # longer offers one, the highway trip simply starts from the
                # top -- the saved street miles were the first miles anyway.
                if state._begin_departure_chain(announce=False):
                    state.trip.restore(position_mi, game_minutes)
            state._departure_checked = True
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
        now = clock_text(self.trip.local_hour)
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
                destination = self.job.spoken_destination
            progress = (
                self._pickup_progress_summary()
                if self.phase == DRIVE_PHASE_PICKUP
                else self._city_service_progress_summary()
                if self.phase == DRIVE_PHASE_CITY_SERVICE
                else self.trip.progress_summary(self.ctx.settings.imperial_units)
            )
            speed_control = self._resumed_speed_control_status()
            if self.phase == DRIVE_PHASE_CITY_SERVICE:
                self.ctx.say(
                    f"Resuming your {drive_name} to {destination}. "
                    f"{progress} "
                    f"{hours_used:.1f} hours used. It is {now}. "
                    f"Transmission is {mode}. "
                    f"Weather: {self.weather.describe(self.ctx.settings.imperial_units)}. "
                    f"You are parked. {speed_control}{self._engine_entry_instruction()} "
                    "When air pressure is ready, press "
                    f"{self.ctx.control_hint('parking_brake')} to release the parking brake.",
                    interrupt=False,
                )
            elif self._terse_speech():
                self.ctx.say(
                    f"Resuming {drive_name}: {destination}. {progress} "
                    f"{hours_used:.1f} of {self.job.deadline_game_h:.0f} hours used. "
                    f"{now}. {mode}. {self.weather.describe(self.ctx.settings.imperial_units)}. "
                    f"{speed_control}{self._parked_entry_status()}",
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
                    f"You are parked. {speed_control}{self._engine_entry_instruction()} "
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

    def _resumed_speed_control_status(self) -> str:
        if not self._speed_control_armed:
            return ""
        target = (
            self.ctx.settings.speed_text(self._speed_control_target_mph)
            if self._speed_control_target_mph is not None
            else "the posted limit when the open road begins"
        )
        return (
            f"Automatic speed control is paused; open-road target {target}. "
            "It will resume once the truck is rolling. Press "
            f"{self.ctx.control_hint('cruise_set')} to cancel it. "
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
        elif kind in {WeatherKind.SNOW, WeatherKind.ICE, WeatherKind.WIND}:
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
    AbandonJobConfirmationState,
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
