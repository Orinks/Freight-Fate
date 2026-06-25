"""The driving state: live truck control with a fully audio HUD.

Continuous controls (throttle, brake, clutch) are sampled from held keys
each frame. Everything the player needs to know is available on demand from
information keys, and important changes announce themselves.
"""

from __future__ import annotations

import logging
import random

import pygame

from ..achievements import add_unique_stat
from ..data.world import Route
from ..models.economy import pay_advance_grant, pay_advance_unavailable_reason
from ..models.jobs import Job, job_from_payload, job_payload
from ..models.settlement import (
    carrier_accessorial_charges,
    charge_summary,
    charge_total,
)
from ..music import (
    music_track_duration_s,
    select_drive_music_sequence,
    select_menu_music_sequence,
)
from ..sim import hos
from ..sim.hos import HosClock, clock_text, is_night, time_of_day
from ..sim.lane import LaneKeeping
from ..sim.transmission import REVERSE
from ..sim.trip import RoadStop, Trip, TripEventKind
from ..sim.vehicle import G, KG_PER_TON, TruckState
from ..sim.weather import WeatherKind, WeatherSystem
from .base import MenuItem, MenuState, State

log = logging.getLogger(__name__)

GEAR_KEYS = {
    pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3, pygame.K_4: 4, pygame.K_5: 5,
    pygame.K_6: 6, pygame.K_7: 7, pygame.K_8: 8, pygame.K_9: 9, pygame.K_0: 10,
}

HAZARD_SAFE_MPH = 25.0
MPH_PER_MPS = 2.23694

# Roadside mechanic: a field patch, not a garage restoration.
FIELD_REPAIR_DAMAGE_PCT = 25.0    # damage level the patch repairs down to
MECHANIC_CALLOUT_FEE = 500.0
MECHANIC_RATE_PER_PCT = 110.0     # premium over the garage's 85 per percent
MECHANIC_WAIT_MIN = 90.0          # game minutes waiting for the truck to be fixed
FUEL_STOP_MIN = 20.0              # fueling is on-duty-not-driving work
INSPECTION_MIN = 15.0             # routine scale/inspection check-in time
OUT_OF_SERVICE_MIN = hos.SLEEP_MIN

# Highway exits: signal inside the window, slow enough to make the ramp.
EXIT_WINDOW_MI = 5.0              # how far out X can arm the upcoming exit
RAMP_MAX_MPH = 45.0               # any faster and you blow past the exit
RAMP_LENGTH_MI = 0.5              # deceleration lane plus ramp to the stop
DESTINATION_EXIT_BEFORE_END_MI = 1.0

CRUISE_MIN_MPH = 20.0             # cruise control needs road speed to hold
ACC_BASE_GAP_SECONDS = 3.0        # clear-weather adaptive cruise gap
ENGINE_SHUTDOWN_SAFE_MPH = 5.0    # prevent accidental kill-switch use at speed
DELIVERY_PARK_MPH = 3.0           # within this, the gate prompts you to stop
DOCKING_MAX_MPH = 0.5            # dock/settle/rest actions need a complete stop
DRIVE_PHASE_PICKUP = "pickup"
DRIVE_PHASE_DELIVERY = "delivery"


def _route_event_sound(event) -> str | None:
    kind = event.kind
    if kind == TripEventKind.HAZARD:
        return "events/hazard_warning"
    if kind == TripEventKind.INSPECTION:
        return "events/inspection_warning"
    if kind == TripEventKind.TOLL_CHARGED:
        return "events/toll_charged"
    if kind in {TripEventKind.STATE_CROSSING, TripEventKind.CHECKPOINT}:
        return "events/state_crossing"
    if kind == TripEventKind.ZONE_ENTER:
        zone = event.data.get("zone")
        if zone is not None and zone.reason == "construction":
            return "events/construction_zone"
        return "events/traffic_slowing"
    if kind == TripEventKind.GPS_CUE:
        cue = event.data.get("cue")
        cue_kind = getattr(cue, "kind", None)
        if cue_kind == "traffic":
            return "events/traffic_slowing"
        if cue_kind == "toll":
            return "events/toll_charged"
    return None


def _poi_ambient_key(stop) -> str:
    if stop.type == "weigh_station":
        return "poi/weigh_station_lane"
    return "poi/rest_stop_night"


def _speeding_settlement_fine(strikes: int) -> float:
    return min(400.0, 80.0 * strikes) if strikes else 0.0


class DrivingState(State):
    def __init__(self, ctx, job: Job, route: Route, trip_seed: int | None = None,
                 phase: str = DRIVE_PHASE_DELIVERY,
                 start_hour: float | None = None) -> None:
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
        self.truck.cargo_kg = (
            job.weight_tons * KG_PER_TON
            if phase == DRIVE_PHASE_DELIVERY else 0.0)
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
        self.trip = Trip(route, self.truck, self.weather,
                         time_scale=ctx.settings.time_scale, seed=self.trip_seed,
                         start_hour=trip_start_hour,
                         imperial=ctx.settings.imperial_units,
                         hazard_scale=hos.hazard_scale(ctx.settings.hos_mode))
        self.lane = LaneKeeping(seed=self.trip_seed)
        self._day_music_sequence = select_drive_music_sequence(
            self.route, self.trip_seed, 12.0, self.weather.current)
        self._night_music_sequence = select_drive_music_sequence(
            self.route, self.trip_seed, 0.0, self.weather.current)
        self._day_music_index = 0
        self._night_music_index = 0
        self._music_elapsed_s = 0.0
        self._music_night = is_night(trip_start_hour)
        self.tutorial = Tutorial(ctx) if not profile.tutorial_done else None

        self.hos = profile.hos          # shift clock lives on the profile
        self.hos_fine_count = 0         # escalates with each failed inspection
        self.enforcement_events: set[str] = set()
        self.out_of_service_count = 0
        self._drowsy_said = False
        self._severe_said = False
        self._fatigue_cue_gm = 0.0      # game minutes since the last drowsy cue
        self._hazard_deadline: float | None = None
        self._speed_announce_timer = 0.0
        self._last_announced_mph = 0.0
        self._speeding_timer = 0.0
        self.speeding_strikes = 0
        self._rescue_offered = False
        self._signal_timer = 0.0
        self._exit_stop = None            # armed exit, set with X
        self._ramp_mi: float | None = None   # ramp distance left, once taken
        self._ramp_stop = None
        self._ramp_end_said = False
        self._destination_exit_taken = False
        self._missed_destination_exit_said = False
        self._destination_exit_announced_key = ""
        self._cruise_mph: float | None = None
        self._cruise_throttle = 0.0
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._arrival_stop_said = False
        self._arrival_full_stop_said = False
        self._arrival_menu_open = False
        self._air_ready_said = self.truck.air_ready
        self._low_air_said = False
        self._spring_brake_said = False
        self._brake_lockout_cue_timer = 0.0
        self._lane_rumble_timer = 0.0
        self._status_text = "Press E to start the engine."

    # -- save and resume -----------------------------------------------------------

    def snapshot(self) -> dict:
        """Everything needed to resume this active drive from a save."""
        job = self.job
        kind = "pickup_drive" if self.phase == DRIVE_PHASE_PICKUP else "delivery"
        return {
            "kind": kind,
            "job": job_payload(job),
            "route_cities": list(self.route.cities),
            "route_kind": ("facility_approach" if self.phase == DRIVE_PHASE_PICKUP
                           else "corridor_itinerary"),
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
            job = job_from_payload(j)
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
            state.trip.restore(float(data["position_mi"]), float(data["game_minutes"]))
            state.trip.restore_toll_charges(list(data.get("toll_charges", ())))
            state.truck.restore_air_brake_snapshot(
                data.get("air_brake"), default_ready=True)
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
            ctx.profile.fatigue = max(0.0, min(100.0, float(
                data.get("fatigue", ctx.profile.fatigue))))
            state.hos_fine_count = int(data.get("hos_fine_count", 0))
            state.enforcement_events = {
                str(key) for key in data.get("enforcement_events", [])
            }
            state.out_of_service_count = int(data.get("out_of_service_count", 0))
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
        now = clock_text(self.trip.current_hour)
        if self.resumed:
            hours_used = self.trip.game_minutes / 60.0
            drive_name = "pickup drive" if self.phase == DRIVE_PHASE_PICKUP else "loaded delivery"
            destination = (self._pickup_facility_text()
                           if self.phase == DRIVE_PHASE_PICKUP else self.job.destination)
            progress = (self._pickup_progress_summary()
                        if self.phase == DRIVE_PHASE_PICKUP else
                        self.trip.progress_summary(self.ctx.settings.imperial_units))
            self.ctx.say(
                f"Resuming your {drive_name}: {self.job.weight_tons:.0f} tons of "
                f"{self.job.cargo.label} to {destination}. "
                f"{progress} "
                f"{hours_used:.1f} hours used of {self.job.deadline_game_h:.0f}. "
                f"It is {now}. Transmission is {mode}. "
                f"Weather: {self.weather.describe()}. "
                f"You are parked. {self._engine_entry_instruction()} "
                "When air pressure is ready, press P to release the parking brake.",
                interrupt=False)
        else:
            objective = (f"Pickup dispatch: deadhead from the terminal to "
                         f"{self._pickup_facility_text()}. "
                         if self.phase == DRIVE_PHASE_PICKUP else
                         f"Loaded for {self._destination_facility_text()}. "
                         f"{self.trip.progress_summary(self.ctx.settings.imperial_units)} ")
            self.ctx.say(f"You are at the wheel. {objective}It is {now}. "
                         f"Transmission is {mode}. "
                         f"Weather: {self.weather.describe()}. "
                         f"{self._engine_entry_instruction()} "
                         "F1 lists the controls.",
                         interrupt=False)
        if self.tutorial:
            self.tutorial.begin()
        if self.phase == DRIVE_PHASE_DELIVERY:
            self._record_weather_achievement(event=False)
            if not self.truck.transmission.automatic:
                self.ctx.award_achievement("manual_driver", event=False, interrupt=False)

    def _engine_entry_instruction(self) -> str:
        if self.truck.engine_on:
            return "Engine idling; build air pressure if needed."
        return "Press E to start the engine and build air pressure."

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
        self.ctx.audio.stop_world()
        self.ctx.audio.stop_music(600)

    # -- input ---------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        tr = self.truck.transmission
        if key == pygame.K_ESCAPE:
            self.ctx.push_state(PauseMenuState(self.ctx, self))
        elif key == pygame.K_e:
            self._toggle_engine()
        elif key == pygame.K_n and not tr.automatic:
            result = tr.request_gear(0)
            if result.ok:
                self.ctx.audio.play("vehicle/gear_shift")
                self.ctx.say("Neutral.")
        elif key == pygame.K_BACKSPACE and not tr.automatic:
            self._manual_shift(REVERSE)
        elif key in GEAR_KEYS and not tr.automatic:
            self._manual_shift(GEAR_KEYS[key])
        elif key == pygame.K_j:
            self.truck.engine_brake = not self.truck.engine_brake
            self.ctx.say("Engine brake on." if self.truck.engine_brake
                         else "Engine brake off.")
        elif key == pygame.K_p:
            self._toggle_parking_brake()
        elif key == pygame.K_h:
            self.ctx.audio.play("vehicle/horn")
        elif key == pygame.K_t:
            self._try_rest_stop()
        elif key == pygame.K_x:
            self._take_exit()
        elif key == pygame.K_k:
            self._toggle_cruise()
        elif key == pygame.K_SPACE:
            self._speak_speed()
        elif key == pygame.K_TAB:
            self.ctx.push_state(DrivingStatusState(self.ctx, self))
        elif key == pygame.K_f:
            self._speak_fuel()
        elif key == pygame.K_c:
            self._speak_clock()
        elif key == pygame.K_r:
            if event.mod & pygame.KMOD_SHIFT:
                self.ctx.say(self.trip.next_exit_context())
            else:
                self.ctx.say(self.trip.progress_summary(self.ctx.settings.imperial_units))
        elif key == pygame.K_v:
            self._speak_weather()
        elif key == pygame.K_l:
            self.ctx.say(self.lane.describe())
        elif key == pygame.K_F1:
            objective_help = (
                f"Your current objective is pickup: drive to {self._pickup_facility_text()}, "
                "stop at the gate, then check in and load. "
                if self.phase == DRIVE_PHASE_PICKUP else
                "Pickup and loading are complete. At your destination, stop, "
                "then dock and deliver. ")
            self.ctx.say(
                "Hold Up arrow to accelerate, Down arrow to brake. "
                "When stopped in automatic, hold Down arrow to reverse slowly; "
                "touch Up arrow to brake and return to forward. "
                "Hold B for the emergency brake, the hardest possible stop. "
                "K sets adaptive cruise at your current speed; bad weather "
                "increases the following gap, and braking cancels. "
                "X takes the next announced exit, called out by its number "
                "when known: slow to 45 for the ramp, then brake to a stop for "
                "the rest stop menu. "
                "E starts the engine, and stops it only below 5 miles per hour. "
                "Air pressure must build before the truck can move. "
                "Press P to release or set the parking brake; if pressure is "
                "below 100 psi, wait with the engine running. "
                f"{objective_help}"
                "Space speed. Tab status menu. F fuel. "
                "C clock, deadline, and hours of service. "
                "R route. Shift R next listed highway exit. V weather. L lane position. "
                "Left and Right arrows steer when lane drift is enabled. "
                "T route POI menu when already stopped "
                "at one: available actions may include fuel, break, sleep, "
                "inspect, roadside assistance, or save when source-backed. H horn. "
                "J engine brake. Escape pause menu. "
                + ("" if self.truck.transmission.automatic else
                   "Hold Left Shift for clutch, then 1 through 0 for gears, "
                   "Backspace for reverse, N for neutral."))

    def _toggle_engine(self) -> None:
        t = self.truck
        if t.engine_on:
            if t.speed_mph > ENGINE_SHUTDOWN_SAFE_MPH:
                self.ctx.audio.play("ui/error")
                text = (f"Unsafe to shut the engine off at "
                        f"{self.ctx.settings.speed_text(t.speed_mph)}. "
                        "Brake below 5 miles per hour first.")
                self._set_status("Engine shutdown blocked: slow down first.")
                self.ctx.say(text)
                return
            t.stop_engine()
            self.ctx.audio.engine_stop()
            self._set_status("Engine off.")
            self.ctx.say("Engine off.")
        else:
            if t.start_engine():
                self.ctx.audio.engine_start()
                self._set_status("Engine running.")
                self.ctx.say("Engine running. " + self._air_start_instruction())
                if self.tutorial:
                    self.tutorial.on_engine_started()
            else:
                self.ctx.audio.play("ui/error")
                if t.fuel_gal <= 0:
                    # never a dead end: the roadside rescue always comes
                    self._handle_out_of_fuel()
                else:
                    self.ctx.say("The engine will not start.")

    def _air_start_instruction(self) -> str:
        t = self.truck
        if t.parking_brake:
            if t.air_ready:
                return "Air pressure ready. Press P to release the parking brake."
            return (f"Air pressure {t.air_pressure_psi:.0f} psi. "
                    "Wait for 100 psi, then press P to release the parking brake.")
        return "Air pressure ready. Hold the Up arrow to drive."

    def _toggle_parking_brake(self) -> None:
        t = self.truck
        if t.parking_brake:
            if t.release_parking_brake():
                self.ctx.audio.play("vehicle/brake_release", volume=0.65)
                self._set_status("Parking brake released.")
                self.ctx.say("Parking brake released. Air pressure "
                             f"{t.air_pressure_psi:.0f} psi.")
                if self.tutorial:
                    self.tutorial.on_parking_brake_released()
            else:
                self.ctx.audio.play("ui/error")
                self._set_status("Parking brake locked: build air pressure first.")
                self.ctx.say(
                    f"Parking brake stays set. Air pressure {t.air_pressure_psi:.0f} psi; "
                    "wait for 100 psi with the engine running.")
            return
        t.set_parking_brake()
        t.throttle = 0.0
        self._cancel_cruise()
        self.ctx.audio.play("vehicle/brake_set", volume=0.65)
        self._set_status("Parking brake set.")
        self.ctx.say(f"Parking brake set. Air pressure {t.air_pressure_psi:.0f} psi.")

    def _manual_shift(self, gear: int) -> None:
        result = self.truck.transmission.request_gear(gear)
        if result.ok:
            self.ctx.audio.play("vehicle/gear_shift")
            self.ctx.say(result.message)
            if self.tutorial:
                self.tutorial.on_gear_engaged()
        elif result.grind:
            self.ctx.audio.play("vehicle/gear_grind")
            self.ctx.say("Grinding gears! Hold Left Shift to press the clutch first.")
        else:
            self.ctx.say(result.message)

    # -- info keys ---------------------------------------------------------------------

    def _speak_speed(self) -> None:
        t = self.truck
        gear = self._gear_text()
        self.ctx.say(f"{self.ctx.settings.speed_text(t.speed_mph)}, {gear}, "
                     f"{t.rpm:.0f} RPM, {self._air_status_text()}.")

    def _gear_text(self) -> str:
        tr = self.truck.transmission
        if tr.in_neutral:
            return "neutral"
        if tr.in_reverse:
            return "reverse"
        return f"gear {tr.gear}"

    def status_lines(self) -> list[str]:
        t = self.truck
        limit, reason = self.trip.speed_limit_at(self.trip.position_mi)
        progress = (
            self._pickup_progress_summary()
            if self.phase == DRIVE_PHASE_PICKUP
            else self.trip.progress_summary(self.ctx.settings.imperial_units)
        )
        lines = [
            f"Speed: {self.ctx.settings.speed_text(t.speed_mph)}",
            f"Limit: {self.ctx.settings.speed_text(limit)}"
            + (f" in a {reason} zone" if reason else ""),
            f"Route: {progress}",
            f"Fuel: {t.fuel_fraction * 100:.0f} percent",
            f"Air brakes: {self._air_status_text(detailed=True)}",
            f"Weather: {self.weather.describe(self.ctx.settings.imperial_units)}",
            f"Clock: {time_of_day(self.trip.current_hour)}",
        ]
        if self._cruise_mph is not None:
            lines.insert(
                1,
                "Cruise: adaptive cruise set at "
                f"{self.ctx.settings.speed_text(self._cruise_mph)}",
            )
            context = self.trip.traffic_context()
            if context is not None:
                lines.insert(
                    2,
                    "Traffic: lead vehicle "
                    f"{self.ctx.settings.distance_text(context.gap_mi)} ahead, "
                    f"{self.ctx.settings.speed_text(context.lead.speed_mph)}",
                )
        if t.damage_pct - self.start_damage > 1:
            lines.append(
                f"Damage: new damage {t.damage_pct - self.start_damage:.0f} percent"
            )
        if self.ctx.settings.speech_verbosity >= 1:
            fatigue = self.ctx.profile.fatigue
            if fatigue >= hos.FATIGUE_DROWSY:
                lines.append(f"Fatigue: {fatigue:.0f} percent")
            lines.append(
                f"HOS: {self.hos.summary(self.ctx.settings.hos_mode).rstrip('.')}"
            )
            context = self._hos_route_context()
            if context:
                lines.append(f"Next legal stop: {context}")
        return lines

    def _air_status_text(self, *, detailed: bool = False) -> str:
        t = self.truck
        if t.spring_brakes_active:
            brake = "spring brakes active"
        elif t.parking_brake:
            brake = "parking brake set"
        else:
            brake = "parking brake released"
        if t.air_low_warning:
            pressure = "low air"
        elif t.air_ready:
            pressure = "air ready"
        else:
            pressure = "air building"
        compressor = "compressor building" if t.air_compressor_active else "compressor idle"
        heat = (
            "brakes hot" if t.brake_temp_c >= t.specs.brake_fade_temp_c
            else "brakes warm" if t.brake_temp_c >= 180.0
            else "brakes cool"
        )
        if detailed:
            return (
                f"primary {t.primary_air_psi:.0f} psi, "
                f"secondary {t.secondary_air_psi:.0f} psi, "
                f"trailer {t.trailer_air_psi:.0f} psi, "
                f"{pressure}, {brake}, {compressor}, {heat}"
            )
        return f"air {t.air_pressure_psi:.0f} psi, {pressure}, {brake}, {compressor}"

    def _speak_fuel(self) -> None:
        t = self.truck
        mpg = 6.0
        range_mi = t.fuel_gal * mpg
        self.ctx.say(f"Fuel {t.fuel_fraction * 100:.0f} percent, {t.fuel_gal:.0f} gallons. "
                     f"Estimated range {self.ctx.settings.distance_text(range_mi)}.")

    def _speak_clock(self) -> None:
        hours_used = self.trip.game_minutes / 60.0
        if self.phase == DRIVE_PHASE_PICKUP:
            now = f"It is {clock_text(self.trip.current_hour)}."
            self.ctx.say(
                f"{now} Pickup drive to {self._pickup_facility_text()}. "
                f"{self.ctx.settings.distance_text(self.trip.remaining_miles)} remain. "
                f"{hours_used:.1f} hours used before loading. "
                f"{self.hos.summary(self.ctx.settings.hos_mode)} "
                f"{self._hos_route_context()}")
            return
        remaining = self.job.deadline_game_h - hours_used
        eta = self.trip.eta_game_hours()
        basis = ("at your current speed"
                 if self.truck.speed_mph >= self.trip.ETA_MIN_MPH
                 else "at a typical highway pace")
        now = f"It is {clock_text(self.trip.current_hour)}."
        hos_part = self.hos.summary(self.ctx.settings.hos_mode)
        hos_route = self._hos_route_context()
        if hos_route:
            hos_part = f"{hos_part} {hos_route}"
        if remaining > 0:
            verdict = ("You are on schedule." if eta < remaining
                       else "You are running behind. Keep your speed up.")
            self.ctx.say(f"{now} {hours_used:.1f} hours on the road. "
                         f"{remaining:.1f} hours until the deadline. "
                         f"Estimated time to arrival {eta:.1f} hours {basis}. "
                         f"{verdict} {hos_part}")
        else:
            self.ctx.say(f"{now} You are {-remaining:.1f} hours past the deadline. "
                         f"The pay is shrinking, but finish the delivery. {hos_part}")

    def _hos_route_context(self) -> str:
        mode = self.ctx.settings.hos_mode
        next_limit = self.hos.next_limit(mode)
        if next_limit is None:
            return ""
        kind, remaining_min, _due = next_limit
        if remaining_min <= 0:
            return "Nearest legal action: stop for a compliant break or 10-hour reset."
        legal_miles = self._legal_miles_for_hos(remaining_min)
        next_stop = self.trip.upcoming_stop(max(legal_miles + 5.0, 5.0))
        action = "break" if kind == "break" else "sleep"
        if next_stop is None:
            return (f"No route stop is currently visible before the next {action} "
                    f"limit, due in {remaining_min / 60.0:.1f} hours.")
        ahead = max(0.0, next_stop.at_mi - self.trip.position_mi)
        verdict = "before" if ahead <= legal_miles else "after"
        return (
            f"Next legal stop: {next_stop.spoken_name} in "
            f"{self.ctx.settings.distance_text(ahead)}, {next_stop.parking_text}, "
            f"{verdict} the next {action} limit."
        )

    def _legal_miles_for_hos(self, remaining_min: float) -> float:
        pace = max(35.0, min(62.0, self.truck.speed_mph or 55.0))
        return max(0.0, remaining_min / 60.0 * pace)

    def _upcoming_stop_with_action(self, action: str, within_mi: float):
        best = None
        for stop in self.trip.stops:
            ahead = stop.at_mi - self.trip.position_mi
            if not 0 <= ahead <= within_mi:
                continue
            if action not in stop.actions or stop.parking == "none":
                continue
            if best is None or stop.at_mi < best.at_mi:
                best = stop
        return best

    def emergency_shoulder_sleep_reason(self) -> str | None:
        """Why shoulder sleep is available now, or None when it is not."""
        if self.truck.speed_mph > 3:
            return None
        if self.trip.nearest_stop_within() is not None:
            return None
        mode = self.ctx.settings.hos_mode
        fatigue = self.ctx.profile.fatigue
        if (fatigue >= hos.FATIGUE_SEVERE
                and self._upcoming_stop_with_action("sleep", 30.0) is None):
            return ("Fatigue is severe, and no sleep-capable route stop is "
                    "within 30 miles.")
        if mode in hos.HOS_NON_ENFORCED_MODES:
            return None
        if self.hos.in_violation(mode):
            return ("You are already past your hours-of-service limit, and "
                    "there is no route POI here.")
        next_limit = self.hos.next_limit(mode)
        if next_limit is None:
            return None
        kind, remaining_min, _due = next_limit
        if remaining_min > hos.SHOULDER_SLEEP_LIMIT_BUFFER_MIN:
            return None
        action = "break" if kind == "break" else "sleep"
        legal_miles = self._legal_miles_for_hos(remaining_min)
        if self._upcoming_stop_with_action(action, max(legal_miles + 5.0, 5.0)):
            return None
        return (f"Your next {action} limit is due in "
                f"{remaining_min / 60.0:.1f} hours, and no suitable route "
                "stop is visible before it.")

    def _speak_weather(self) -> None:
        source = "Live conditions" if self.weather.live else "Currently"
        parts = [f"It is {time_of_day(self.trip.current_hour)}.",
                 f"{source} {self.weather.describe()}.",
                 f"Safe speed about {self.weather.effects.safe_speed_mph:.0f}."]
        if not self.weather.live:
            ahead = ", then ".join(k.value for k in self.weather.forecast(2))
            parts.append(f"Ahead: {ahead}.")
        self.ctx.say(" ".join(parts))

    # -- per-frame update -----------------------------------------------------------------

    def update(self, dt: float) -> None:
        t = self.truck
        # pacing can be changed from the pause menu mid-trip; keep the trip's
        # clock compression in step with the setting
        self.trip.time_scale = self.ctx.settings.time_scale
        self._sync_weather_source()
        keys = pygame.key.get_pressed()
        ramp = dt * 2.2
        self._brake_lockout_cue_timer = max(0.0, self._brake_lockout_cue_timer - dt)
        self._lane_rumble_timer = max(0.0, self._lane_rumble_timer - dt)
        accelerating = keys[pygame.K_UP]
        braking_key = keys[pygame.K_DOWN]
        backing = self._update_reverse_controls(accelerating, braking_key)
        if accelerating and not backing and t.air_brakes_holding:
            self._maybe_say_air_brake_lockout()
        if accelerating and not backing:
            t.throttle = min(1.0, t.throttle + ramp)
        elif backing:
            t.throttle = min(0.45, t.throttle + ramp)
        else:
            t.throttle = max(0.0, t.throttle - ramp * 2)
        braking = (braking_key and not backing) or (accelerating and t.velocity_mps < -0.1)
        if braking:
            new_brake = min(1.0, t.brake + ramp * 1.5)
            if t.brake < 0.05 and new_brake >= 0.05 and abs(t.velocity_mps) > 1:
                self.ctx.audio.play("vehicle/brake_air", volume=0.6)
            t.brake = new_brake
        else:
            t.brake = max(0.0, t.brake - ramp * 3)
        emergency = keys[pygame.K_b]
        if emergency:
            # no ramp: slams to full application instantly, plus spring brakes
            if not t.emergency_brake and abs(t.velocity_mps) > 1:
                self.ctx.audio.play("vehicle/brake_air", volume=1.0)
            t.throttle = 0.0
            t.brake = 1.0
        t.emergency_brake = emergency
        t.transmission.clutch = 1.0 if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] else 0.0
        self._update_lane(keys, dt)
        self._update_cruise(dt, braking, accelerating)

        if t.transmission.automatic and t.engine_on:
            new_gear = t.auto_shift()
            if new_gear is not None:
                self.ctx.audio.play("vehicle/gear_shift", volume=0.65)

        was_on = t.engine_on
        was_air_ready = t.air_ready
        was_low_air = t.air_low_warning
        was_spring_brake = t.spring_brakes_active
        t.update(dt)
        self._update_air_brake_announcements(
            was_air_ready, was_low_air, was_spring_brake)
        if was_on and not t.engine_on:
            self.ctx.audio.engine_stop()
            if t.stalled:
                self.ctx.say_event("The engine stalled. Press E to restart, and "
                                   "use a lower gear at low speed.")
            elif t.fuel_gal <= 0:
                self._handle_out_of_fuel()

        # Keep the trip's spoken-distance units in step with a live settings
        # change; the setter only re-renders cues when the choice actually flips.
        self.trip.imperial = self.ctx.settings.imperial_units
        pos_before = self.trip.position_mi
        for event in self.trip.update(dt):
            self._handle_trip_event(event)
        self._check_destination_exit()
        self._update_exit(self.trip.position_mi - pos_before)

        self._update_hours_and_fatigue(dt)
        self._update_audio(dt)
        self._update_announcements(dt)
        self._update_hazard(dt)
        self._update_speeding(dt)
        if self.tutorial:
            self.tutorial.update(dt, t)
        if self.trip.finished:
            if self.phase == DRIVE_PHASE_PICKUP:
                self._handle_pickup_gate()
            elif self._ramp_mi is not None:
                return
            elif not self._destination_exit_taken:
                self._handle_missed_destination_exit()
            else:
                self._handle_arrival_gate()

    def _maybe_say_air_brake_lockout(self) -> None:
        if self._brake_lockout_cue_timer > 0:
            return
        self._brake_lockout_cue_timer = 4.0
        t = self.truck
        if not t.engine_on:
            self._set_status("Start the engine before releasing the brakes.")
            self.ctx.say_event("Start the engine first; air pressure cannot build "
                               "with the engine off.", interrupt=False)
        elif not t.air_ready:
            self._set_status("Waiting for air pressure before the truck can move.")
            self.ctx.say_event(
                f"Air pressure {t.air_pressure_psi:.0f} psi. Wait for 100 psi, "
                "then press P to release the parking brake.",
                interrupt=False)
        elif t.parking_brake:
            self._set_status("Parking brake set. Press P to release it.")
            self.ctx.say_event("Parking brake set. Press P to release it.",
                               interrupt=False)

    def _update_air_brake_announcements(
            self, was_ready: bool, was_low: bool, was_spring: bool) -> None:
        t = self.truck
        if t.air_low_warning and t.engine_on and (not was_low or not self._low_air_said):
            self._low_air_said = True
            self.ctx.audio.play("ui/warning", volume=0.7)
            self.ctx.say_event(
                f"Low air warning: {t.air_pressure_psi:.0f} psi. "
                "Keep the parking brake set until pressure builds.",
                interrupt=False)
        elif not t.air_low_warning:
            self._low_air_said = False

        if t.spring_brakes_active and not was_spring and not self._spring_brake_said:
            self._spring_brake_said = True
            self.ctx.audio.play("ui/warning", volume=0.9)
            self.ctx.say_event(
                "Spring brakes applied from low air pressure. Stop and let the "
                "compressor rebuild air before moving.",
                interrupt=True)
        elif not t.spring_brakes_active:
            self._spring_brake_said = False

        if t.air_ready and not was_ready and not self._air_ready_said:
            self._air_ready_said = True
            self.ctx.audio.play("ui/notify", volume=0.65)
            if t.parking_brake:
                text = (f"Air pressure ready at {t.air_pressure_psi:.0f} psi. "
                        "Press P to release the parking brake.")
                self._set_status("Air ready. Press P to release the parking brake.")
            else:
                text = f"Air pressure ready at {t.air_pressure_psi:.0f} psi."
                self._set_status("Air ready.")
            self.ctx.say_event(text, interrupt=False)
            self.ctx.award_achievement("air_ready", event=True)
        elif not t.air_ready:
            self._air_ready_said = False

    def _update_reverse_controls(self, accelerating: bool, braking_key: bool) -> bool:
        """Return True when the current key state means backing up."""
        t = self.truck
        tr = t.transmission
        if not tr.automatic:
            return tr.in_reverse and braking_key and not accelerating
        if tr.in_reverse:
            if accelerating and abs(t.velocity_mps) < 0.3:
                tr.gear = 1
                tr._shift_timer = 0.0
                self.ctx.audio.play("vehicle/gear_shift", volume=0.55)
                self._set_status("Forward gear selected.")
                return False
            return braking_key and not accelerating
        if braking_key and not accelerating and t.speed_mph < 0.5:
            tr.gear = REVERSE
            tr._shift_timer = 0.0
            self._cancel_cruise()
            self.ctx.audio.play("vehicle/gear_shift", volume=0.55)
            self._set_status("Reverse selected. Backing slowly.")
            return True
        return False

    def _update_hours_and_fatigue(self, dt: float) -> None:
        """Advance the HOS shift clock and fatigue on game time, not wall time."""
        gm = dt * self.trip.time_scale / 60.0   # game minutes this frame
        moving = self.truck.speed_mph > 5.0
        mode = self.ctx.settings.hos_mode
        p = self.ctx.profile

        if moving:
            self.hos.drive(gm)
        else:
            self.hos.on_duty(gm)   # the 14-hour window runs even while parked
        if mode not in hos.HOS_NON_ENFORCED_MODES:
            for message in self.hos.check_warnings(mode):
                self.ctx.audio.play("ui/warning")
                self.ctx.say_event(message, interrupt=False)
        self.trip.hos_violation = (
            mode not in hos.HOS_NON_ENFORCED_MODES and self.hos.in_violation(mode)
        )

        night = is_night(self.trip.current_hour)
        if moving:
            p.fatigue = min(100.0, p.fatigue + hos.fatigue_rate_per_min(night) * gm)
        fatigue = p.fatigue
        if fatigue >= hos.FATIGUE_SEVERE and not self._severe_said:
            self._severe_said = True
            self._fatigue_cue_gm = 0.0
            self.ctx.audio.play("vehicle/rumble_strip", volume=0.8)
            self.ctx.say_event("You are dangerously drowsy and drifting out of "
                               "your lane. Sleep at the next rest stop.",
                               interrupt=False)
        elif fatigue >= hos.FATIGUE_DROWSY and not self._drowsy_said:
            self._drowsy_said = True
            self._fatigue_cue_gm = 0.0
            self.ctx.audio.play("driver/yawn", volume=0.9)
            self.ctx.say_event("You are getting drowsy. Take a break or sleep "
                               "at a rest stop.", interrupt=False)
        if fatigue < hos.FATIGUE_DROWSY:
            self._drowsy_said = False
        if fatigue < hos.FATIGUE_SEVERE:
            self._severe_said = False
        # periodic audio cues while drowsiness persists
        if moving and fatigue >= hos.FATIGUE_DROWSY:
            self._fatigue_cue_gm += gm
            if self._fatigue_cue_gm >= 15.0:
                self._fatigue_cue_gm = 0.0
                if fatigue >= hos.FATIGUE_SEVERE:
                    self.ctx.audio.play("vehicle/rumble_strip", volume=0.8)
                else:
                    self.ctx.audio.play("driver/yawn", volume=0.8)

    def _update_lane(self, keys, dt: float) -> None:
        mode = self.ctx.settings.steering_assist
        steer = 0.0
        if keys[pygame.K_LEFT]:
            steer -= 1.0
        if keys[pygame.K_RIGHT]:
            steer += 1.0
        self.lane.steering = steer
        leg = self.route.legs[self.trip.current_leg_index]
        curve = 0.0
        if leg.terrain == "hills":
            curve = 0.25
        elif leg.terrain == "mountain":
            curve = 0.55
        if self._ramp_mi is not None:
            curve += 0.35
        wind = self.weather.effects.wind
        if self.lane.update(dt, self.truck.velocity_mps, curve=curve, wind=wind, assist=mode):
            self.ctx.audio.play("vehicle/rumble_strip", volume=1.0)
            self.truck.damage_pct = min(100.0, self.truck.damage_pct + 1.0)
            self.ctx.say_event(
                f"{self.lane.describe()} Steer back toward the lane center.",
                interrupt=False,
            )

    def _update_audio(self, dt: float = 0.0) -> None:
        t = self.truck
        audio = self.ctx.audio
        if t.engine_on and not audio.engine_running:
            audio.engine_start()
        audio.set_engine_rpm(t.rpm, t.throttle)
        audio.set_road_noise(t.velocity_mps)
        eff = self.weather.effects
        audio.set_weather(eff.sound)
        audio.set_wind(eff.wind)
        rumble = self.lane.rumble_level()
        if (
            rumble > 0.0
            and self.ctx.settings.steering_assist != "off"
            and self._lane_rumble_timer <= 0.0
        ):
            self._lane_rumble_timer = 0.8
            audio.play("vehicle/rumble_strip", volume=0.25 + rumble * 0.45)
        night = is_night(self.trip.current_hour)
        if night:
            audio.set_ambient("ambient/night")
        else:
            audio.set_ambient(None)
        self._update_music_rotation(night, dt)
        if self.weather.should_thunder():
            audio.play("weather/thunder")

    def _current_music_track(self) -> str:
        if self._music_night:
            return self._night_music_sequence[self._night_music_index]
        return self._day_music_sequence[self._day_music_index]

    def _play_current_music(self, fade_ms: int = 4000) -> None:
        self.ctx.audio.play_music(self._current_music_track(), fade_ms=fade_ms)

    def _update_music_rotation(self, night: bool, dt: float) -> None:
        if night != self._music_night:
            self._music_night = night
            self._music_elapsed_s = 0.0
            self._play_current_music(fade_ms=4000)
            return
        self._music_elapsed_s += max(0.0, dt)
        current = self._current_music_track()
        if self._music_elapsed_s < music_track_duration_s(current):
            return
        self._music_elapsed_s = 0.0
        if night:
            self._night_music_index = (
                self._night_music_index + 1
            ) % len(self._night_music_sequence)
        else:
            self._day_music_index = (
                self._day_music_index + 1
            ) % len(self._day_music_sequence)
        self._play_current_music(fade_ms=4000)

    def _sync_weather_source(self) -> None:
        real = self.ctx.settings.real_weather
        if real == self._weather_source_real:
            return
        self._weather_source_real = real
        self.weather.provider = self.ctx.real_weather_provider() if real else None
        if not real:
            self.weather.live = False
        self.ctx.audio.set_weather(self.weather.effects.sound)
        self.ctx.audio.set_wind(self.weather.effects.wind)

    def _update_announcements(self, dt: float) -> None:
        if self.ctx.settings.speech_verbosity == 0:
            return
        self._speed_announce_timer += dt
        interval = 12.0 if self.ctx.settings.speech_verbosity == 1 else 7.0
        if self._speed_announce_timer >= interval:
            self._speed_announce_timer = 0.0
            mph = self.truck.speed_mph
            if abs(mph - self._last_announced_mph) >= 5 and mph > 1:
                self._last_announced_mph = mph
                self.ctx.say_event(self.ctx.settings.speed_text(mph),
                                   interrupt=False)

    def _brake_budget_s(self) -> float:
        """Seconds of full service braking to reach the hazard-safe speed.

        Uses the truck's rated deceleration on the current surface, helped
        uphill and hurt downhill, so a warning at 65 in the snow allows the
        stop it actually takes there.
        """
        t = self.truck
        over_mps = max(0.0, (t.speed_mph - HAZARD_SAFE_MPH) / MPH_PER_MPS)
        decel = G * (t.specs.max_brake_decel_g * t.grip + t.grade)
        return over_mps / max(decel, 0.5)

    def _update_hazard(self, dt: float) -> None:
        if self._hazard_deadline is None:
            return
        if self.truck.speed_mph <= HAZARD_SAFE_MPH:
            self._hazard_deadline = None
            self.ctx.say_event("Hazard avoided. Well done.", interrupt=False)
            self.ctx.award_achievement("hazard_avoided", event=True)
            return
        self._hazard_deadline -= dt
        if self._hazard_deadline <= 0:
            self._hazard_deadline = None
            self.ctx.audio.play("vehicle/collision")
            severity = min(1.0, self.truck.speed_mph / 70.0)
            self.truck.apply_collision(severity)
            self.ctx.say_event(f"Collision! The truck took damage. "
                               f"Total damage {self.truck.damage_pct:.0f} percent.")

    def _update_speeding(self, dt: float) -> None:
        if self._ramp_mi is not None:
            return   # the ramp is off the highway and unpatrolled
        limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
        if self.truck.speed_mph > limit + 9:
            self._speeding_timer += dt
            if self._speeding_timer > 6.0:
                self._speeding_timer = 0.0
                self.speeding_strikes += 1
                self.ctx.audio.play("ui/warning")
                self.ctx.say_event(f"You are speeding. The limit is {limit:.0f}.",
                                   interrupt=False)
        else:
            self._speeding_timer = 0.0

    def _handle_trip_event(self, event) -> None:
        kind = event.kind
        sound = _route_event_sound(event)
        if kind == TripEventKind.HAZARD:
            if self._ramp_mi is not None:
                return   # off the highway: the hazard passes you by
            if self._cruise_mph is not None:
                self._cancel_cruise()   # hands back on the wheel to brake
            self.ctx.audio.play(sound or "ui/warning")
            # The deadline is braking physics plus reaction slack. The physics
            # part is whatever full service brakes need from the current speed
            # on this surface; the rolled window covers hearing the warning and
            # getting on the pedal, and fatigue eats into that part only --
            # a drowsy driver reacts late, but the truck stops no slower.
            slack = event.data.get("deadline_s", 4.0)
            self._hazard_deadline = (
                self._brake_budget_s()
                + slack * hos.reaction_window_mult(self.ctx.profile.fatigue))
            self.ctx.say_event(event.message, interrupt=True)
        elif kind == TripEventKind.INSPECTION:
            self._handle_inspection(event)
        elif kind == TripEventKind.WEATHER_CHANGE:
            self.ctx.say_event(event.message, interrupt=False)
            self._record_weather_achievement()
        elif kind == TripEventKind.TOLL_CHARGED:
            self.ctx.audio.play(sound or "ui/notify")
            self.ctx.say_event(event.message, interrupt=False)
            self.ctx.award_achievement("toll_paid", event=True)
        elif kind == TripEventKind.STATE_CROSSING:
            cue = event.data.get("cue")
            state = getattr(cue, "near_text", event.message)
            add_unique_stat(self.ctx.profile, "states_crossed", str(state))
            if sound is not None:
                self.ctx.audio.play(sound)
            self.ctx.say_event(event.message, interrupt=False)
            self.ctx.award_achievement("state_crossing", event=True)
        elif kind == TripEventKind.ARRIVED:
            pass  # handled by _arrive()
        elif self._event_disables_cruise(event):
            self._cancel_cruise_for_restricted_area(event.message)
        else:
            if sound is not None and kind != TripEventKind.ZONE_ENTER:
                self.ctx.audio.play(sound)
            self.ctx.say_event(event.message, interrupt=False)
        if kind == TripEventKind.ZONE_ENTER:
            self.ctx.audio.play(sound or "ui/notify")
            zone = event.data.get("zone")
            if getattr(zone, "reason", "") == "construction":
                self.ctx.award_achievement("construction_zone", event=True)
            elif getattr(zone, "reason", "") == "heavy traffic":
                self.ctx.award_achievement("traffic_slowing", event=True)
        if kind == TripEventKind.GPS_CUE:
            cue = event.data.get("cue")
            if getattr(cue, "kind", "") == "traffic":
                self.ctx.award_achievement("traffic_slowing", event=True)

    def _event_disables_cruise(self, event) -> bool:
        if self._cruise_mph is None:
            return False
        if event.kind == TripEventKind.ZONE_ENTER:
            return True
        if event.kind != TripEventKind.GPS_CUE:
            return False
        zone = event.data.get("zone")
        if zone is None:
            return False
        return zone.reason in {"construction", "heavy traffic"}

    def _cancel_cruise_for_restricted_area(self, message: str) -> None:
        self._cancel_cruise()
        self.ctx.audio.play("ui/notify")
        self.ctx.say_event(
            f"{message} Adaptive cruise disabled; take manual speed control.",
            interrupt=False,
        )

    def _handle_inspection(self, event) -> None:
        """Route-backed enforcement with stable evidence and no duplicate fines."""
        event_key = str(event.data.get(
            "key",
            f"{event.message}:{round(self.trip.position_mi, 1)}:{self.hos_fine_count}",
        ))
        if event_key in self.enforcement_events:
            return
        self.enforcement_events.add(event_key)
        p = self.ctx.profile
        fine = hos.HOS_FINES[min(self.hos_fine_count, len(hos.HOS_FINES) - 1)]
        self.hos_fine_count += 1
        p.money -= fine   # can go negative; never a game over
        p.career.reputation = max(0.0, p.career.reputation - hos.HOS_REPUTATION_HIT)
        evidence = list(event.data.get("evidence", ()))
        if not evidence:
            evidence = ["HOS/ELD violation"]
        evidence_text = ", ".join(evidence)
        self.ctx.audio.play("ui/error")
        serious_hos = (
            self.ctx.settings.hos_mode not in hos.HOS_NON_ENFORCED_MODES
            and self.hos.in_violation(self.ctx.settings.hos_mode)
        )
        message = (f"{event.message} Evidence: {evidence_text}. "
                   f"Fined {fine:,.0f} dollars, and your reputation took a hit.")
        if serious_hos:
            self.ctx.say_event(
                message + " Out of service order: parked for 10 hours to reset "
                "your ELD clock.",
                interrupt=True,
            )
            self.ctx.award_achievement("inspection", event=True)
            self._place_out_of_service()
            return
        self.ctx.say_event(message, interrupt=True)
        self.ctx.award_achievement("inspection", event=True)

    def _place_out_of_service(self) -> None:
        _advance_rest_clock(self, OUT_OF_SERVICE_MIN)
        self.hos.sleep()
        self.ctx.profile.fatigue = hos.rest_sleep(self.ctx.profile.fatigue)
        self.out_of_service_count += 1
        self.ctx.profile.active_trip = self.snapshot()
        self.ctx.save_profile()

    def _try_rest_stop(self) -> None:
        stop = self.trip.nearest_stop_within()
        if stop is None:
            self.ctx.say("There is no route POI here. Stops are announced as you "
                         "approach them.")
            return
        if self.truck.speed_mph > DOCKING_MAX_MPH:
            self.ctx.say("Come to a complete stop first.")
            return
        self._open_poi_stop(stop)

    def _open_poi_stop(self, stop) -> None:
        can_sleep = "sleep" in stop.actions
        if can_sleep and hos.parking_is_full(self.trip_seed, stop.at_mi,
                                             self.trip.current_hour):
            self.ctx.push_state(ParkingFullState(self.ctx, self, stop))
            return
        self.ctx.push_state(RestStopState(self.ctx, self, stop))
        self.ctx.award_achievement("first_rest_stop")

    def _take_exit(self) -> None:
        if self._ramp_mi is not None:
            self.ctx.say("You are already on the exit ramp. Brake to a stop.")
            return
        if self._exit_stop is not None:
            self._exit_stop = None
            self.ctx.say("Exit canceled. Staying on the highway.")
            return
        stop = self._upcoming_exit_stop()
        if stop is None:
            self.ctx.say("No exit coming up. Exits are announced as you "
                         "approach them.")
            return
        self._exit_stop = stop
        self.ctx.audio.play("ui/notify", volume=0.5)
        ahead = stop.at_mi - self.trip.position_mi
        if stop.type == "delivery_destination":
            head = (f"Signaling for {self._destination_exit_phrase(stop)}, "
                    f"destination exit for {stop.name},")
        elif stop.exit_label:
            head = f"Signaling for {stop.exit_label}, {stop.spoken_name},"
        else:
            head = f"Signaling for the {stop.spoken_name} exit,"
        self.ctx.say(f"{head} {ahead:.1f} miles ahead. "
                     f"Slow to {RAMP_MAX_MPH:.0f} or less for the ramp.")

    def _upcoming_exit_stop(self):
        stop = self.trip.upcoming_stop(EXIT_WINDOW_MI)
        destination = self._destination_exit_stop()
        if destination is None:
            return stop
        ahead = destination.at_mi - self.trip.position_mi
        if not (0 <= ahead <= EXIT_WINDOW_MI):
            return stop
        if stop is None or destination.at_mi <= stop.at_mi:
            return destination
        return stop

    def _destination_exit_stop(self):
        if self.phase != DRIVE_PHASE_DELIVERY or self._destination_exit_taken:
            return None
        details = self._destination_exit_details()
        if details is None:
            at_mi = max(0.0, self.trip.total_miles - DESTINATION_EXIT_BEFORE_END_MI)
            exit_label = ""
            exit_phrase = ""
        else:
            at_mi, exit_label, exit_phrase = details
        if at_mi <= self.trip.position_mi + 0.05:
            return None
        stop = RoadStop(
            self._destination_facility_text(),
            at_mi,
            "delivery_destination",
            ("deliver",),
            exit_label=exit_label,
        )
        stop.exit_phrase = exit_phrase
        return stop

    def _destination_exit_label(self) -> str:
        details = self._destination_exit_details()
        return "" if details is None else details[1]

    def _destination_exit_key(self, stop) -> str:
        return f"{stop.at_mi:.3f}:{stop.exit_label}:{stop.name}"

    def _destination_exit_phrase(self, stop) -> str:
        phrase = getattr(stop, "exit_phrase", "")
        if phrase:
            return phrase
        if stop.exit_label:
            return f"{stop.exit_label} for {stop.name}"
        return f"the exit for {stop.name}"

    def _destination_exit_announcement(self, stop, ahead: float) -> str:
        phrase = self._destination_exit_phrase(stop)
        return (f"In {ahead:.0f} miles, {phrase}, destination exit. "
                "Press X to take it.")

    def _check_destination_exit(self) -> None:
        stop = self._destination_exit_stop()
        if stop is None:
            return
        ahead = stop.at_mi - self.trip.position_mi
        if not (0 < ahead <= EXIT_WINDOW_MI):
            return
        key = self._destination_exit_key(stop)
        if key == self._destination_exit_announced_key:
            return
        self._destination_exit_announced_key = key
        message = self._destination_exit_announcement(stop, ahead)
        if self._cruise_mph is not None:
            self._cancel_cruise()
            message += " Adaptive cruise disabled; take manual speed control."
        self.ctx.audio.play("ui/notify", volume=0.7)
        self.ctx.say_event(message, interrupt=False)

    def _destination_exit_details(
            self, *, include_past: bool = False) -> tuple[float, str, str] | None:
        if not self.route.legs:
            return None
        destination = self.route.cities[-1].casefold()
        candidates = []
        for i in range(len(self.route.legs) - 1, -1, -1):
            leg = self.route.legs[i]
            forward = self.route.cities[i] == leg.a
            target = leg.miles if forward else 0.0
            for ix in leg.interchanges:
                if not ix.exit_label:
                    continue
                offset = ix.at_mi if forward else leg.miles - ix.at_mi
                route_mile = self.trip._leg_starts[i] + offset
                if not include_past and route_mile <= self.trip.position_mi + 0.05:
                    continue
                dist_from_destination = abs(ix.at_mi - target)
                matches_destination = any(
                    destination in part.casefold() for part in ix.destinations)
                candidates.append((
                    not matches_destination,
                    len(self.route.legs) - 1 - i,
                    dist_from_destination,
                    route_mile,
                    ix.exit_label,
                    ix.spoken_phrase,
                ))
            if candidates and not candidates[0][0]:
                break
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][3], candidates[0][4], candidates[0][5]

    def _update_exit(self, moved_mi: float) -> None:
        """Advance an armed exit or an active ramp; opens the stop menu."""
        if self._ramp_mi is not None:
            self._ramp_mi -= moved_mi
            if self._ramp_mi > 0:
                return
            if self.truck.speed_mph <= DOCKING_MAX_MPH:
                stop = self._ramp_stop
                self._ramp_mi = None
                self._ramp_stop = None
                if stop.type == "delivery_destination":
                    self._open_facility_arrival()
                else:
                    self._open_poi_stop(stop)
            elif not self._ramp_end_said:
                self._ramp_end_said = True
                place = (self._ramp_stop.name
                         if self._ramp_stop.type == "delivery_destination"
                         else self._ramp_stop.spoken_name)
                self.ctx.say_event(f"You are at {place}. Come to a complete stop.")
            return
        stop = self._exit_stop
        if stop is None or self.trip.position_mi < stop.at_mi:
            return
        self._exit_stop = None
        if self.truck.speed_mph <= RAMP_MAX_MPH:
            self._ramp_mi = RAMP_LENGTH_MI
            self._ramp_stop = stop
            self._ramp_end_said = False
            self._destination_exit_taken = stop.type == "delivery_destination"
            self._cancel_cruise()
            self.ctx.audio.play("ui/notify", volume=0.7)
            if stop.type == "delivery_destination":
                take = (f"You take {self._destination_exit_phrase(stop)}, "
                        f"destination exit for {stop.name}.")
            else:
                take = (f"You take {stop.exit_label} for {stop.spoken_name}."
                        if stop.exit_label
                        else f"You take the exit for {stop.spoken_name}.")
            self.ctx.say_event(f"{take} Half a mile of ramp; brake to a stop "
                               "at the end.")
        else:
            missed = stop.exit_label if stop.exit_label else "the exit"
            place = (self._destination_exit_phrase(stop)
                     if stop.type == "delivery_destination" else stop.spoken_name)
            self.ctx.say_event("You were going too fast for the ramp and "
                               f"missed {missed} for {place}.")

    def _toggle_cruise(self) -> None:
        t = self.truck
        if self._cruise_mph is not None:
            self._cancel_cruise()
            self.ctx.say("Adaptive cruise off.")
            return
        if not t.engine_on or t.speed_mph < CRUISE_MIN_MPH:
            self.ctx.say("Adaptive cruise needs the engine running and at "
                         f"least {CRUISE_MIN_MPH:.0f} miles per hour.")
            return
        self._cruise_mph = t.speed_mph
        self._cruise_throttle = t.throttle
        self._acc_following = False
        self._acc_weather_gap_said = False
        gap = self._acc_gap_seconds()
        self.ctx.audio.play("ui/notify", volume=0.5)
        self.ctx.say("Adaptive cruise set at "
                      f"{self.ctx.settings.speed_text(t.speed_mph)}. "
                      f"Following gap {gap:.0f} seconds. "
                      "K or braking cancels.")

    def _cancel_cruise(self) -> None:
        self._cruise_mph = None
        self._cruise_throttle = 0.0
        self._acc_following = False
        self._acc_weather_gap_said = False

    def _acc_gap_seconds(self) -> float:
        effects = self.weather.effects
        gap = ACC_BASE_GAP_SECONDS
        if effects.grip < 0.9:
            gap += (0.9 - effects.grip) * 4.2
        if effects.visibility_mi < 3.0:
            gap += (3.0 - effects.visibility_mi) * 0.5
        return min(6.0, max(ACC_BASE_GAP_SECONDS, gap))

    def _acc_weather_gap_text(self) -> str | None:
        effects = self.weather.effects
        if effects.grip < 0.9:
            return "Wet roads, adaptive cruise increasing following gap."
        if effects.visibility_mi < 3.0:
            return "Low visibility, adaptive cruise increasing following gap."
        return None

    def _update_cruise(self, dt: float, braking: bool,
                       accelerating: bool) -> None:
        """Hold speed when clear, and follow slower modeled traffic when present."""
        if self._cruise_mph is None:
            return
        t = self.truck
        if braking or t.emergency_brake or t.air_brakes_holding or not t.engine_on or t.stalled:
            self._cancel_cruise()
            self.ctx.say_event("Adaptive cruise canceled.", interrupt=False)
            return
        if accelerating:
            return   # manual override; cruise resumes when the key lifts
        target_mph = self._cruise_mph
        context = self.trip.traffic_context()
        following = False
        if context is not None:
            desired_gap = self._acc_gap_seconds()
            reason = self._acc_weather_gap_text()
            if (reason and not self._acc_weather_gap_said
                    and context.gap_seconds <= desired_gap + 1.5):
                self._acc_weather_gap_said = True
                self.ctx.say_event(reason, interrupt=False)
            if context.gap_seconds <= desired_gap + 1.0 or context.lead.speed_mph < target_mph:
                target_mph = min(target_mph, context.lead.speed_mph)
                following = True
        if following and not self._acc_following:
            self.ctx.audio.play("ui/notify", volume=0.55)
            self.ctx.say_event("Traffic ahead, adaptive cruise reducing speed.",
                               interrupt=False)
        self._acc_following = following
        error = target_mph - t.speed_mph
        self._cruise_throttle = max(0.0, min(
            1.0, self._cruise_throttle + error * 0.08 * dt))
        t.throttle = self._cruise_throttle
        if following and error < -2.0:
            weather_brake = 0.45 if self.weather.effects.grip < 0.7 else 0.65
            t.brake = max(t.brake, min(weather_brake, abs(error) / 30.0))

    def _handle_out_of_fuel(self) -> None:
        if self._rescue_offered:
            return
        self._rescue_offered = True
        p = self.ctx.profile
        fee = 750.0
        p.money -= fee  # can go negative: the rescue is not optional
        self.truck.refuel(30.0)
        self._rescue_offered = False
        self.ctx.audio.play("ui/error")
        self.ctx.say_event(f"You ran out of fuel. Roadside rescue brought thirty "
                           f"gallons for {fee:,.0f} dollars. Press E to restart "
                           "the engine, and plan your fuel stops.")

    def _handle_pickup_gate(self) -> None:
        if self.truck.speed_mph <= DOCKING_MAX_MPH:
            self._open_pickup_arrival()
            return
        if self.truck.speed_mph <= DELIVERY_PARK_MPH:
            self._handle_pickup_creep()
            return
        if self._arrival_stop_said:
            return
        self._arrival_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/warning")
        self._set_status("Pickup ahead: slow down and come to a complete stop.")
        self.ctx.say_event(
            f"Pickup ahead: {self._pickup_facility_text()}. "
            "Slow down and come to a complete stop at the gate.",
            interrupt=True)

    def _handle_pickup_creep(self) -> None:
        if self._arrival_full_stop_said:
            return
        self._arrival_full_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/notify", volume=0.7)
        self._set_status("Pickup gate: stop to check in.")
        self.ctx.say_event(
            f"At {self._pickup_facility_text()}. Stop to check in.",
            interrupt=False)

    def _open_pickup_arrival(self) -> None:
        if self._arrival_menu_open:
            return
        from .city import PickupFacilityState, pickup_snapshot

        p = self.ctx.profile
        self._arrival_menu_open = True
        self._cancel_cruise()
        self.truck.throttle = 0.0
        self.truck.brake = 1.0
        self.truck.set_parking_brake()
        p.truck_fuel_gal = self.truck.fuel_gal
        p.truck_damage_pct = self.truck.damage_pct
        p.game_hours += self.trip.game_minutes / 60.0
        p.market.advance_to(p.market_day())
        p.active_trip = pickup_snapshot(self.job, air_brake=self.truck.air_brake_snapshot())
        self.ctx.save_profile()
        self._set_status("Parked at pickup. Check in and load.")
        self.ctx.replace_state(PickupFacilityState(self.ctx, self.job, driving=self))

    def _arrive(self) -> None:
        self.ctx.replace_state(ArrivalState(self.ctx, self))

    def _handle_missed_destination_exit(self) -> None:
        self.trip.finished = False
        self._exit_stop = None
        self._cancel_cruise()
        if self._missed_destination_exit_said:
            return
        self._missed_destination_exit_said = True
        self.ctx.audio.play("ui/warning")
        self._set_status("Destination exit missed. Back up until it is ahead, then press X.")
        self.ctx.say_event(
            f"You missed the destination exit for {self._destination_facility_text()}. "
            "Back up until the exit is ahead, then press X to signal for it.",
            interrupt=True,
        )

    def _handle_arrival_gate(self) -> None:
        if self.truck.speed_mph <= DOCKING_MAX_MPH:
            self._open_facility_arrival()
            return
        if self.truck.speed_mph <= DELIVERY_PARK_MPH:
            self._handle_arrival_creep()
            return
        if self._arrival_stop_said:
            return
        self._arrival_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/warning")
        self._set_status("Destination ahead: slow down and come to a complete stop.")
        self.ctx.say_event(
            f"Destination ahead: {self._destination_facility_text()}. "
            "Slow down and come to a complete stop at the gate.",
            interrupt=True)

    def _handle_arrival_creep(self) -> None:
        if self._arrival_full_stop_said:
            return
        self._arrival_full_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/notify", volume=0.7)
        self._set_status("Destination gate: stop to dock.")
        self.ctx.say_event(
            f"At {self._destination_facility_text()}. Stop to dock.",
            interrupt=False)

    def _open_facility_arrival(self) -> None:
        if self._arrival_menu_open:
            return
        self._arrival_menu_open = True
        self._cancel_cruise()
        self.truck.throttle = 0.0
        self.truck.brake = 1.0
        self.truck.set_parking_brake()
        self._set_status("Parked at destination. Dock and deliver.")
        self.ctx.replace_state(FacilityArrivalState(self.ctx, self))

    def _destination_facility_text(self) -> str:
        return self.job.destination_facility_text()

    def _pickup_facility_text(self) -> str:
        return self.job.origin_facility_text()

    def _pickup_progress_summary(self) -> str:
        return (f"{self.trip.remaining_miles:.1f} miles remaining of "
                f"{self.trip.total_miles:.1f} to pickup at "
                f"{self._pickup_facility_text()}.")

    def _set_status(self, text: str) -> None:
        self._status_text = text

    def presence(self):
        from ..discord_presence import driving_presence
        from ..models.trucks import TRUCK_CATALOG

        total = self.trip.total_miles or 1.0
        fraction = self.trip.position_mi / total
        moving = self.truck.speed_mph >= 1.0
        truck = TRUCK_CATALOG.get(self.ctx.profile.truck) if self.ctx.profile else None
        return driving_presence(
            phase=self.phase,
            origin=self.job.origin,
            destination=self.job.destination,
            cargo=self.job.cargo.label,
            fraction=fraction,
            moving=moving,
            truck_label=truck.label if truck else "",
        )

    def lines(self) -> list[str]:
        t = self.truck
        limit, reason = self.trip.speed_limit_at(self.trip.position_mi)
        gear = "N" if t.transmission.in_neutral else str(t.transmission.gear)
        title = (f"Deadheading to pickup at {self._pickup_facility_text()}"
                 if self.phase == DRIVE_PHASE_PICKUP else
                 f"Driving loaded to {self.job.destination}")
        remaining = (f"{self.trip.remaining_miles:.1f} of "
                     f"{self.trip.total_miles:.1f} miles"
                     if self.phase == DRIVE_PHASE_PICKUP else
                     f"{self.trip.remaining_miles:.0f} of {self.trip.total_miles:.0f} miles")
        return [
            title,
            "",
            f"Speed: {t.speed_mph:.0f} mph (limit {limit:.0f}{', ' + reason if reason else ''})",
            f"Gear: {gear}   RPM: {t.rpm:.0f}   {'ENGINE ON' if t.engine_on else 'engine off'}"
            + (f"   CRUISE {self._cruise_mph:.0f}" if self._cruise_mph is not None else ""),
            f"Air: {t.air_pressure_psi:.0f} psi   "
            f"{'LOW AIR' if t.air_low_warning else 'air ready' if t.air_ready else 'building'}   "
            f"{'spring brakes' if t.spring_brakes_active else 'parking set' if t.parking_brake else 'parking released'}",
            f"Fuel: {t.fuel_fraction * 100:.0f}%   Damage: {t.damage_pct:.0f}%",
            f"Remaining: {remaining}",
            f"Weather: {self.weather.current.value}",
            f"Clock: {clock_text(self.trip.current_hour)} "
            f"({time_of_day(self.trip.current_hour)})   "
            f"Fatigue: {self.ctx.profile.fatigue:.0f}%",
            "",
            self._status_text,
        ]


class Tutorial:
    """First-drive guidance, spoken step by step as the player succeeds."""

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self.stage = 0
        self._timer = 0.0
        self._hinted = False

    def begin(self) -> None:
        self.ctx.say(
            "This is your first run, so let's walk through it. "
            "First: press E to start the engine.", interrupt=False)

    def on_engine_started(self) -> None:
        if self.stage == 0:
            self.stage = 1
            self._timer = 0.0
            self._hinted = False
            if self.ctx.settings.automatic_transmission:
                self.ctx.say("Now let air pressure build. When you hear air ready, "
                             "press P to release the parking brake, then hold the "
                             "Up arrow to accelerate. The transmission shifts for you.",
                             interrupt=False)
            else:
                self.ctx.say("Now let air pressure build. When you hear air ready, "
                             "press P to release the parking brake, then hold Left "
                             "Shift, press 1 for first gear, and release the clutch.",
                             interrupt=False)

    def on_parking_brake_released(self) -> None:
        if self.stage == 1 and self.ctx.settings.automatic_transmission:
            self.stage = 2
            self._timer = 0.0
            self._hinted = False
            self.ctx.say("Parking brake released. Now hold the Up arrow to accelerate.",
                         interrupt=False)
        elif self.stage == 1:
            self._timer = 0.0
            self._hinted = False
            self.ctx.say("Parking brake released. Now shift into first gear.",
                         interrupt=False)

    def on_gear_engaged(self) -> None:
        if self.stage == 1:
            self.stage = 2
            self._timer = 0.0
            self._hinted = False
            self.ctx.say("In gear. Now hold the Up arrow to accelerate.",
                         interrupt=False)

    def update(self, dt: float, truck) -> None:
        self._timer += dt
        if self.stage == 2 and truck.speed_mph > 20:
            self.stage = 3
            self.ctx.say(
                "You are rolling. Press Space anytime for your speed, Tab for a "
                "full report, and F1 to hear all the controls. Watch for hazard "
                "warnings, and brake hard when you hear them. Hold B for the "
                "emergency brake when you need to stop fast. Safe travels.",
                interrupt=False)
            self.ctx.profile.tutorial_done = True
            self.ctx.save_profile()
        elif self.stage in (0, 1) and self._timer > 25 and not self._hinted:
            self._hinted = True
            if self.stage == 0:
                self.ctx.say("Reminder: press E to start the engine.", interrupt=False)
            elif truck.parking_brake:
                self.ctx.say("Reminder: wait for air pressure to reach 100 psi, "
                             "then press P to release the parking brake.",
                             interrupt=False)
            else:
                self.ctx.say("Reminder: hold Left Shift, press 1, then release "
                             "the shift key.", interrupt=False)


def _advance_rest_clock(driving: DrivingState, minutes: float) -> None:
    """Resting advances game time, so deadlines keep counting."""
    driving.trip.game_minutes += minutes
    driving.weather.update(minutes)


def _deadline_text(driving: DrivingState) -> str:
    remaining = driving.job.deadline_game_h - driving.trip.game_minutes / 60.0
    if remaining > 0:
        return f"{remaining:.1f} hours left to deliver."
    return f"You are now {-remaining:.1f} hours past the deadline."


def _perform_shoulder_sleep(driving: DrivingState, anchor_mi: float) -> str:
    """Apply the emergency shoulder-sleep outcome and return spoken text."""
    p = driving.ctx.profile
    _advance_rest_clock(driving, hos.SLEEP_MIN)
    driving.hos.sleep()
    p.fatigue = hos.rest_shoulder(p.fatigue)
    parts = [f"You sleep poorly on the shoulder, woken again and again by "
             f"passing trucks. It is {clock_text(driving.trip.current_hour)}. "
             f"Hours of service reset, but you are still tired."]
    if hos.shoulder_fine_due(driving.trip_seed, anchor_mi):
        p.money -= hos.SHOULDER_FINE
        driving.ctx.audio.play("ui/error")
        parts.append(f"A trooper ticketed you for illegal parking: "
                     f"{hos.SHOULDER_FINE:,.0f} dollars. "
                     f"You have {p.money:,.0f} dollars.")
    if hos.shoulder_damage_due(driving.trip_seed, anchor_mi):
        driving.truck.damage_pct = min(
            100.0, driving.truck.damage_pct + hos.SHOULDER_DAMAGE_PCT)
        parts.append(f"Roadside debris and wake turbulence added "
                     f"{hos.SHOULDER_DAMAGE_PCT:.0f} percent truck damage.")
    p.truck_fuel_gal = driving.truck.fuel_gal
    p.truck_damage_pct = driving.truck.damage_pct
    p.active_trip = driving.snapshot()
    driving.ctx.save_profile()
    parts.append(_deadline_text(driving))
    return " ".join(parts)


class ShoulderSleepConfirmationState(MenuState):
    """Emergency shoulder sleep warning, shared by full lots and no-stop cases."""

    title = "Emergency shoulder sleep"
    intro_help = ("Use up and down arrows to navigate, Enter to select. "
                  "Escape cancels and returns to the road.")

    def __init__(self, ctx, driving: DrivingState, reason: str,
                 anchor_mi: float | None = None) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.reason = reason
        self.anchor_mi = anchor_mi

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.title}. {self.reason} Shoulder sleep is emergency-only. "
            "It advances ten hours and gives you poor rest: you will not wake "
            "fully rested. If hours of service are enforced, your ELD clock "
            "will reset. You may be ticketed for illegal parking, minor truck "
            "damage can happen, and the delivery deadline keeps counting. "
            f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem("Sleep on the shoulder anyway", self._sleep,
                     help="Accept poor emergency rest, possible ticket, "
                          "possible minor truck damage, and deadline time loss."),
            MenuItem("Cancel and keep looking for a safe stop", self.go_back,
                     help="Return to the road without resting here."),
        ]

    def _sleep(self) -> None:
        anchor = self.anchor_mi
        if anchor is None:
            anchor = self.driving.trip.position_mi
        text = _perform_shoulder_sleep(self.driving, anchor)
        self.ctx.pop_state()
        if self.ctx._app.state is not self.driving:
            self.ctx.pop_state()
        self.ctx.say(text, interrupt=True)


class RestStopState(MenuState):
    """Spoken route POI menu: actions come from the corridor metadata."""

    intro_help = ("Use up and down arrows to navigate, Enter to select. "
                  "Escape returns to the road. Breaks and sleep advance the "
                  "clock, and your delivery deadline keeps counting.")

    def __init__(self, ctx, driving: DrivingState, stop) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.stop = stop

    @property
    def title(self) -> str:  # type: ignore[override]
        return self.stop.spoken_name

    def presence(self):
        from ..discord_presence import PresenceState

        base = self.driving.presence()
        detail = base.detail if base is not None else ""
        return PresenceState("Resting at a stop", detail)

    def announce_entry(self) -> None:
        self.ctx.audio.set_ambient(_poi_ambient_key(self.stop))
        self.ctx.say(f"{self.stop.spoken_name}. "
                     f"{self.stop.parking_text}. "
                     f"It is {clock_text(self.driving.trip.current_hour)}. "
                     f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        actions = set(self.stop.actions)
        items: list[MenuItem] = []
        if "fuel" in actions:
            items.append(MenuItem(
                self._fuel_label, self._refuel,
                help="Fill the tank at this region's diesel price, plus a "
                     "35 dollar service fee. If cash is short, buy as many "
                     "gallons as you can afford."))
        if "food" in actions:
            items.append(MenuItem(
                "Food and coffee break", self._food_break,
                help="A short off-duty break for food or coffee. The clock and "
                     "your deadline advance fifteen minutes."))
        if "break" in actions:
            items.append(MenuItem(
                "Take a 30-minute break", self._take_break,
                help="Satisfies the 30-minute break rule and eases fatigue. "
                     "The clock and your deadline advance half an hour."))
        if "sleep" in actions:
            items.append(MenuItem(
                "Sleep 10 hours", self._sleep,
                help="A full reset: fresh hours of service and zero fatigue. "
                     "The clock and your deadline advance 10 hours."))
        if "repair" in actions:
            items.append(MenuItem(
                "Use repair service", self._repair,
                help="Pay the shop to repair truck damage before returning "
                     "to the road."))
        if "roadside_assistance" in actions:
            items.append(MenuItem(
                "Call roadside assistance", self._roadside_assistance,
                help="Use the listed roadside assistance service for a field "
                     "repair before returning to the road."))
        if "towing" in actions:
            items.append(MenuItem(
                "Request towing service", self._roadside_assistance,
                help="Use the listed towing service for roadside help before "
                     "returning to the road."))
        if "inspect" in actions:
            items.append(MenuItem(
                "Check in at inspection station", self._inspect,
                help="Stop and record the inspection check-in before "
                     "continuing."))
        if "save" in actions:
            items.append(MenuItem(
                "Save at this stop", self._save_here,
                help="Save the active drive at this route POI without "
                     "leaving the road."))
        items.append(MenuItem(
            self._pay_advance_label, self._request_pay_advance,
            help="Draw cash against this load when you are broke and cannot "
                 "afford fuel. Repaid automatically out of your delivery "
                 "settlement."))
        items.append(MenuItem("Back to the road", self.go_back))
        return items

    def _pay_advance_label(self) -> str:
        p = self.ctx.profile
        grant = pay_advance_grant(p.money, p.pay_advance)
        if grant > 0:
            return f"Request pay advance: {grant:,.0f} dollars"
        return "Request pay advance"

    def _request_pay_advance(self) -> None:
        p = self.ctx.profile
        grant = pay_advance_grant(p.money, p.pay_advance)
        if grant <= 0:
            self.ctx.audio.play("ui/error")
            self.ctx.say(pay_advance_unavailable_reason(p.money, p.pay_advance))
            return
        p.money += grant
        p.pay_advance = round(p.pay_advance + grant, 2)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Pay advance approved: {grant:,.0f} dollars against your "
            f"{self.driving.job.destination} load. It will be deducted at "
            f"delivery. You have {p.money:,.0f} dollars, with "
            f"{p.pay_advance:,.0f} dollars of advance still to repay.")
        self.refresh()

    def _fuel_label(self) -> str:
        d = self.driving
        need = d.truck.specs.fuel_tank_gal - d.truck.fuel_gal
        if need < 1:
            return "Fuel: tank is full"
        cost = self.ctx.economy.fuel_cost(d.trip.current_region, need) + 35.0
        return f"Refuel {need:.0f} gallons for {cost:,.0f} dollars"

    def _refuel(self) -> None:
        d = self.driving
        p = self.ctx.profile
        region = d.trip.current_region
        need = d.truck.specs.fuel_tank_gal - d.truck.fuel_gal
        if need < 1:
            self.ctx.say("The tank is already full.")
            return
        cost = self.ctx.economy.fuel_cost(region, need) + 35.0
        if p.money < cost:
            partial_gal = max(0.0, (p.money - 35.0) / self.ctx.economy.fuel_price(region))
            if partial_gal < 5:
                self.ctx.audio.play("ui/error")
                self.ctx.say("You cannot afford fuel here.")
                return
            need = partial_gal
            cost = self.ctx.economy.fuel_cost(region, need) + 35.0
        p.money -= cost
        d.truck.refuel(need)
        _advance_rest_clock(d, FUEL_STOP_MIN)
        d.hos.on_duty(FUEL_STOP_MIN)
        self._save_here(silent=True)
        self.ctx.audio.play("vehicle/fuel_pump")
        self.ctx.say(f"Refueled {need:.0f} gallons for {cost:,.0f} dollars. "
                     f"You have {p.money:,.0f} dollars. Fueling took "
                     f"{FUEL_STOP_MIN:.0f} minutes.")
        self.ctx.award_achievement("route_refuel")
        self.refresh()

    def _take_break(self) -> None:
        d = self.driving
        p = self.ctx.profile
        _advance_rest_clock(d, 30.0)
        d.hos.take_break(30.0)
        p.fatigue = hos.rest_break(p.fatigue)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"You took a 30-minute break. "
                     f"It is {clock_text(d.trip.current_hour)}. "
                     f"Your break requirement is reset and you feel a little "
                     f"fresher. {_deadline_text(d)}")
        self.ctx.award_achievement("break_taken")

    def _food_break(self) -> None:
        d = self.driving
        p = self.ctx.profile
        _advance_rest_clock(d, 15.0)
        d.hos.take_break(15.0)
        p.fatigue = max(0.0, p.fatigue - 3.0)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"You took a short food and coffee break. "
                     f"It is {clock_text(d.trip.current_hour)}. "
                     f"{_deadline_text(d)}")

    def _sleep(self) -> None:
        d = self.driving
        p = self.ctx.profile
        before_fatigue = p.fatigue
        _advance_rest_clock(d, hos.SLEEP_MIN)
        d.hos.sleep()
        p.fatigue = hos.rest_sleep(p.fatigue)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"You slept 10 hours and woke rested. "
                     f"It is {clock_text(d.trip.current_hour)}. "
                     f"Hours of service reset. {_deadline_text(d)}")
        self.ctx.award_achievement("slept_on_route")
        if before_fatigue < hos.FATIGUE_SEVERE:
            self.ctx.award_achievement("sleep_before_exhaustion")

    def _repair(self) -> None:
        d = self.driving
        p = self.ctx.profile
        damage = d.truck.damage_pct
        if damage < 1.0:
            self.ctx.say("The truck does not need repair.")
            return
        cost = self.ctx.economy.repair_cost(damage)
        if p.money < cost:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"Repair costs {cost:,.0f} dollars. You cannot afford it.")
            return
        p.money -= cost
        d.truck.damage_pct = 0.0
        _advance_rest_clock(d, 60.0)
        d.hos.on_duty(60.0)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"Truck repaired for {cost:,.0f} dollars. "
                     f"It is {clock_text(d.trip.current_hour)}. "
                     f"You have {p.money:,.0f} dollars. {_deadline_text(d)}")
        self.ctx.award_achievement("garage_repair")

    def _roadside_assistance(self) -> None:
        d = self.driving
        p = self.ctx.profile
        damage = d.truck.damage_pct
        if damage < 1.0:
            self.ctx.say("The truck does not need roadside assistance.")
            return
        repaired = max(0.0, damage - FIELD_REPAIR_DAMAGE_PCT)
        cost = MECHANIC_CALLOUT_FEE + repaired * MECHANIC_RATE_PER_PCT
        p.money -= cost
        d.truck.damage_pct = min(damage, FIELD_REPAIR_DAMAGE_PCT)
        _advance_rest_clock(d, MECHANIC_WAIT_MIN)
        d.hos.on_duty(MECHANIC_WAIT_MIN)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"Roadside assistance patched the truck to "
                     f"{d.truck.damage_pct:.0f} percent damage for "
                     f"{cost:,.0f} dollars. It is "
                     f"{clock_text(d.trip.current_hour)}. {_deadline_text(d)}")

    def _inspect(self) -> None:
        d = self.driving
        _advance_rest_clock(d, INSPECTION_MIN)
        d.hos.on_duty(INSPECTION_MIN)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"Inspection check-in complete at {self.stop.spoken_name}. "
                     f"It is {clock_text(d.trip.current_hour)}. "
                     f"{_deadline_text(d)}")
        self.ctx.award_achievement("inspection")

    def _save_here(self, *, silent: bool = False) -> None:
        d = self.driving
        p = self.ctx.profile
        p.truck_fuel_gal = d.truck.fuel_gal
        p.truck_damage_pct = d.truck.damage_pct
        p.active_trip = d.snapshot()
        self.ctx.save_profile()
        if not silent:
            self.ctx.audio.play("ui/notify")
            self.ctx.say(f"Saved at {self.stop.spoken_name}. "
                         "Your drive will resume from this rest stop.")

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
        self.ctx.say("Back on the road. Press E to start the engine.",
                     interrupt=True)


class ParkingFullState(MenuState):
    """The overnight lot is full: push on, or risk the shoulder."""

    title = "Parking full"
    intro_help = ("The truck parking here is full. Use up and down arrows and "
                  "Enter to choose. Escape returns to the road to find "
                  "another stop.")

    def __init__(self, ctx, driving: DrivingState, stop) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.stop = stop

    def announce_entry(self) -> None:
        self.ctx.audio.set_ambient("poi/rest_stop_night")
        self.ctx.say(f"The truck parking at {self.stop.spoken_name} is full tonight. "
                     f"It is {clock_text(self.driving.trip.current_hour)}. "
                     f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem("Drive on to the next stop", self._drive_on,
                     help="Return to the road and try the next rest stop."),
            MenuItem("Park on the shoulder and sleep", self._shoulder,
                     help="Ten hours of poor sleep. Resets your hours of "
                          "service, but you will not wake fresh, and you risk "
                          "a fine for illegal parking or minor truck damage."),
        ]

    def go_back(self) -> None:
        self._drive_on()

    def _drive_on(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
        self.ctx.say("Back on the road. The next stop is announced as you "
                     "approach it. Press E to start the engine.", interrupt=True)

    def _shoulder(self) -> None:
        self.ctx.push_state(ShoulderSleepConfirmationState(
            self.ctx,
            self.driving,
            f"The truck parking at {self.stop.spoken_name} is full tonight.",
            self.stop.at_mi,
        ))


POI_ACTION_LABELS = {
    "park": "parking",
    "save": "save point",
    "fuel": "fuel",
    "food": "food and coffee",
    "break": "30-minute rest break",
    "sleep": "sleep or long rest",
    "repair": "repairs",
    "roadside_assistance": "roadside assistance",
    "towing": "towing",
    "inspect": "inspection check-in",
}

POI_SERVICE_LABELS = {
    "diesel": "diesel",
    "food": "food",
    "parking": "truck parking",
    "truck_parking": "truck parking",
    "restrooms": "restrooms",
    "scale": "scale",
    "repair": "repair",
    "roadside_assistance": "roadside assistance",
    "towing": "towing",
}


def _join_phrase(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def _poi_offers_text(stop) -> str:
    offers = [
        POI_ACTION_LABELS[action]
        for action in stop.actions
        if action in POI_ACTION_LABELS
    ]
    services = [
        POI_SERVICE_LABELS.get(service, service.replace("_", " "))
        for service in stop.services
    ]
    parts = []
    if offers:
        parts.append(f"offers {_join_phrase(offers)}")
    if services:
        parts.append(f"listed services: {_join_phrase(services)}")
    if getattr(stop, "parking_text", ""):
        parts.append(stop.parking_text)
    return "; ".join(parts) if parts else "services not listed"


class DrivingStatusState(MenuState):
    """Live driving status, grouped into screens you open one at a time.

    A tabbed layout (Right/Left to cycle Route, Driver, Map) needs visible tabs
    to make sense, so each screen is its own spoken submenu instead, matching
    the rest of the game's menus.
    """

    title = "Driving status"
    intro_help = (
        "Use up and down arrows to pick a status screen, Enter to open it, and "
        "Escape to return to driving. Each screen lists its status lines."
    )
    SCREENS = (("Route", "route"), ("Driver", "driver"), ("Map", "map"))

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(label, lambda key=key: self._open(key),
                     help=f"Open the {label.lower()} status screen.")
            for label, key in self.SCREENS
        ]
        items.append(
            MenuItem("Back to driving", self.go_back,
                     help="Close status and resume driving.")
        )
        return items

    def _open(self, screen: str) -> None:
        self.ctx.push_state(
            DrivingStatusScreenState(self.ctx, self.driving, screen))

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
        self.ctx.say("Back to driving.", interrupt=True)


class DrivingStatusScreenState(MenuState):
    """One screen of live driving status as a reviewable list of lines."""

    intro_help = (
        "Use up and down arrows to review each line. Enter repeats the current "
        "line. Escape goes back to the status screens."
    )
    TITLES = {"route": "Route", "driver": "Driver", "map": "Map"}

    def __init__(self, ctx, driving: DrivingState, screen: str) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.screen = screen

    @property
    def title(self) -> str:  # type: ignore[override]
        return self.TITLES.get(self.screen, "Status")

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                line,
                lambda line=line: self.ctx.say(line),
                help="Repeat this status line.",
            )
            for line in self._lines()
        ]
        items.append(MenuItem("Back", self.go_back,
                              help="Back to the status screens."))
        return items

    def _lines(self) -> list[str]:
        if self.screen == "driver":
            return self._driver_lines()
        if self.screen == "map":
            return self._map_lines()
        return self.driving.status_lines()

    def _driver_lines(self) -> list[str]:
        d = self.driving
        t = d.truck
        profile = self.ctx.profile
        hours_used = d.trip.game_minutes / 60.0
        deadline = d.job.deadline_game_h - hours_used
        deadline_text = (
            f"{deadline:.1f} hours before the deadline"
            if deadline >= 0
            else f"{-deadline:.1f} hours past the deadline"
        )
        return [
            f"Driver: {profile.name}",
            f"Money: {profile.money:,.0f} dollars",
            f"Load: {d.job.weight_tons:.0f} tons of {d.job.cargo.label}, "
            f"gross {d.truck.gross_mass_kg / KG_PER_TON:.0f} tons",
            f"Objective: {'pickup at ' + d._pickup_facility_text() if d.phase == DRIVE_PHASE_PICKUP else 'deliver to ' + d._destination_facility_text()}",
            f"Truck: fuel {t.fuel_fraction * 100:.0f} percent, damage {t.damage_pct:.0f} percent",
            f"Transmission: {'automatic' if t.transmission.automatic else 'manual'}, {d._gear_text()}",
            f"Fatigue: {profile.fatigue:.0f} percent",
            f"Hours: {d.hos.summary(self.ctx.settings.hos_mode).rstrip('.')}",
            f"Time: {clock_text(d.trip.current_hour)}, {deadline_text}",
        ]

    def _map_lines(self) -> list[str]:
        d = self.driving
        route = d.route
        settings = self.ctx.settings
        lines = [
            f"Route: {' to '.join(route.cities)}",
            f"Highways: {_join_phrase(route.highways)}",
            f"Progress: {settings.distance_text(d.trip.position_mi)} driven, "
            f"{settings.distance_text(d.trip.remaining_miles)} remaining",
            f"Guidance: {d.trip.next_navigation_context(settings.imperial_units)}",
        ]
        upcoming = [
            stop
            for stop in d.trip.stops
            if stop.at_mi >= d.trip.position_mi - 0.05
        ][:5]
        if upcoming:
            for stop in upcoming:
                ahead = max(0.0, stop.at_mi - d.trip.position_mi)
                lines.append(
                    f"Stop in {settings.distance_text(ahead)}: {stop.spoken_name}; "
                    f"{_poi_offers_text(stop)}."
                )
        else:
            lines.append("Stops: no more listed route stops before destination.")
        next_cues = [
            cue for cue in d.trip.navigation_cues
            if cue.at_mi > d.trip.position_mi + 0.05 and cue.kind != "rest_stop"
        ][:4]
        for cue in next_cues:
            ahead = max(0.0, cue.at_mi - d.trip.position_mi)
            speed = (f" at {settings.speed_text(cue.speed_mph)}"
                     if cue.speed_mph is not None else "")
            lines.append(
                f"Map point in {settings.distance_text(ahead)}: {cue.text}{speed}.")
        if route.estimated_tolls > 0:
            lines.append(
                f"Estimated carrier-paid toll exposure: {route.estimated_tolls:,.0f} dollars."
            )
        return lines


class PauseMenuState(MenuState):
    title = "Paused"

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def enter(self) -> None:
        self.ctx.audio.play("ui/pause")
        self.ctx.audio.stop_world()
        super().enter()

    def presence(self):
        from ..discord_presence import PresenceState

        base = self.driving.presence()
        detail = base.detail if base is not None else ""
        return PresenceState("Paused", detail)

    def build_items(self) -> list[MenuItem]:
        drive_label = "pickup drive" if self.driving.phase == DRIVE_PHASE_PICKUP else "delivery"
        items = [
            MenuItem("Resume driving", self._resume,
                     help=f"Return to the active {drive_label}."),
            MenuItem("Trip status", self._status,
                     help="Hear cargo, objective, route progress, and time used."),
            MenuItem(self._mechanic_label, self._mechanic,
                     help="A mobile mechanic patches the truck up enough to "
                          "drive on. Costs much more than a garage repair, "
                          "takes an hour and a half, and the bill is due even "
                          "if it puts you in debt."),
            MenuItem("Settings", self._settings,
                     help="Change units, transmission, volumes, weather, "
                          "voices, update channel, and trip pacing."),
            MenuItem("Abandon job", self._abandon,
                     help="Give up this job. Costs five hundred dollars and "
                          "reputation, and returns you to the origin city."),
            MenuItem("Quit to main menu", self._quit_to_menu,
                     help="You can only save at a stop, so this drive is not "
                          "saved in progress. It resumes from your last stop "
                          "when you continue. Use Abandon job to drop the load."),
        ]
        if self.driving.emergency_shoulder_sleep_reason() is not None:
            items.insert(3, MenuItem(
                "Emergency shoulder sleep",
                self._emergency_shoulder_sleep,
                help="Emergency-only poor sleep on the shoulder. Resets hours "
                     "of service, but fatigue remains, you may be ticketed, "
                     "minor truck damage can happen, and the deadline keeps "
                     "running."))
        return items

    def go_back(self) -> None:
        self._resume()

    def _mechanic_label(self) -> str:
        damage = self.driving.truck.damage_pct
        if damage <= FIELD_REPAIR_DAMAGE_PCT:
            return "Call a roadside mechanic: not needed yet"
        repaired = damage - FIELD_REPAIR_DAMAGE_PCT
        cost = MECHANIC_CALLOUT_FEE + repaired * MECHANIC_RATE_PER_PCT
        return f"Call a roadside mechanic: {cost:,.0f} dollars"

    def _mechanic(self) -> None:
        d = self.driving
        damage = d.truck.damage_pct
        if damage <= FIELD_REPAIR_DAMAGE_PCT:
            self.ctx.say("The truck is running well enough. A roadside mechanic "
                         f"can help once damage is past "
                         f"{FIELD_REPAIR_DAMAGE_PCT:.0f} percent.")
            return
        if d.truck.speed_mph > 3:
            self.ctx.say("Come to a complete stop first.")
            return
        p = self.ctx.profile
        repaired = damage - FIELD_REPAIR_DAMAGE_PCT
        cost = MECHANIC_CALLOUT_FEE + repaired * MECHANIC_RATE_PER_PCT
        p.money -= cost   # the rescue is never refused; money can go negative
        d.truck.damage_pct = FIELD_REPAIR_DAMAGE_PCT
        _advance_rest_clock(d, MECHANIC_WAIT_MIN)
        d.hos.on_duty(MECHANIC_WAIT_MIN)
        self.ctx.audio.play("ui/notify")
        self.refresh()
        self.ctx.say(f"A mobile mechanic patched the truck up to "
                     f"{FIELD_REPAIR_DAMAGE_PCT:.0f} percent damage for "
                     f"{cost:,.0f} dollars. You have {p.money:,.0f} dollars. "
                     f"The repair took an hour and a half: it is "
                     f"{clock_text(d.trip.current_hour)}. {_deadline_text(d)}")

    def _emergency_shoulder_sleep(self) -> None:
        reason = self.driving.emergency_shoulder_sleep_reason()
        if reason is None:
            self.ctx.say("Emergency shoulder sleep is not available right now. "
                         "Use a route stop for normal breaks and sleep.")
            self.refresh()
            return
        self.ctx.push_state(ShoulderSleepConfirmationState(
            self.ctx, self.driving, reason, self.driving.trip.position_mi))

    def _resume(self) -> None:
        self.ctx.audio.play("ui/unpause")
        self.ctx.pop_state()
        self.ctx.say("Resumed.", interrupt=True)

    def _status(self) -> None:
        d = self.driving
        hours_used = d.trip.game_minutes / 60.0
        if d.phase == DRIVE_PHASE_PICKUP:
            self.ctx.say(
                f"Driving to pickup at {d._pickup_facility_text()}. "
                f"{d.job.weight_tons:.0f} tons of {d.job.cargo.label} are "
                f"assigned for {d.job.destination}. "
                f"{d._pickup_progress_summary()} {hours_used:.1f} hours used. "
                f"{d._air_status_text()}.")
            return
        self.ctx.say(
            f"Hauling {d.job.weight_tons:.0f} tons of {d.job.cargo.label} "
            f"to {d.job.destination}. "
            f"{d.trip.progress_summary(self.ctx.settings.imperial_units)} "
            f"{hours_used:.1f} hours used of {d.job.deadline_game_h:.0f}. "
            f"{d._air_status_text()}.")

    def _settings(self) -> None:
        from .main_menu import SettingsState

        self.ctx.push_state(SettingsState(self.ctx))

    def _abandon(self) -> None:
        from .city import CityMenuState

        p = self.ctx.profile
        p.money -= 500.0
        p.career.reputation = max(0.0, p.career.reputation - 5.0)
        p.truck_fuel_gal = self.driving.truck.fuel_gal
        p.truck_damage_pct = self.driving.truck.damage_pct
        # the hours spent on the failed run still happened: keep the world
        # clock consistent with the HOS and fatigue already accrued
        p.game_hours += self.driving.trip.game_minutes / 60.0
        p.market.advance_to(p.market_day())
        p.active_trip = None
        self.ctx.save_profile()
        self.ctx.say(f"Job abandoned. You paid a five hundred dollar penalty and "
                     f"returned to {p.current_city}.", interrupt=True)
        self.ctx.pop_state()   # close pause menu
        self.ctx.replace_state(CityMenuState(self.ctx))

    def _quit_to_menu(self) -> None:
        from .main_menu import MainMenuState

        # Saving happens only at stops, so a mid-drive quit writes nothing: the
        # on-disk save still points at your last stop, and Continue resumes the
        # leg from there. In-progress leg driving is intentionally not preserved.
        drive_label = "pickup drive" if self.driving.phase == DRIVE_PHASE_PICKUP else "delivery"
        self.ctx.say(
            f"Returning to the title. You can only save at a stop, so this "
            f"{drive_label} will resume from your last stop, not from here.",
            interrupt=True)
        self.ctx.reset_to(MainMenuState(self.ctx))


class FacilityArrivalState(MenuState):
    title = "Destination facility"
    open_sound_key = "facility/dock_gate"
    intro_help = ("Use arrows to navigate, Enter to select. "
                  "Dock and deliver completes the job.")

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    @property
    def facility(self) -> str:
        return self.driving._destination_facility_text()

    def presence(self):
        from ..discord_presence import PresenceState

        return PresenceState("Delivering", f"{self.driving.job.cargo.label} to "
                             f"{self.driving.job.destination}")

    def enter(self) -> None:
        sequence = select_menu_music_sequence(self.ctx.profile)
        self.ctx.play_music_sequence("menu", sequence)
        super().enter()

    def announce_entry(self) -> None:
        self.ctx.audio.set_ambient("poi/facility_gate")
        self.ctx.say(
            f"At {self.facility}. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem("Dock and deliver", self._dock,
                     help="Back into the dock and complete this delivery."),
            MenuItem("Check paperwork", self._paperwork,
                     help="Review pay, deadline, cargo condition, and charges."),
            MenuItem("Check arrival status", self._status,
                     help="Hear the facility, cargo, speed, and next step."),
        ]

    def _dock(self) -> None:
        d = self.driving
        if d.truck.speed_mph > DOCKING_MAX_MPH:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Stop before docking.")
            return
        d.truck.throttle = 0.0
        d.truck.brake = 1.0
        d.truck.set_parking_brake()
        d._set_status("Docked. Delivery paperwork signed.")
        self.ctx.audio.play("poi/dock_and_deliver")
        self.ctx.say(
            f"Docked at {self.facility}. Trailer secured and paperwork signed.",
            interrupt=True)
        d._arrive()

    def _paperwork(self) -> None:
        d = self.driving
        job = d.job
        hours = d.trip.game_minutes / 60.0
        remaining = job.deadline_game_h - hours
        trip_damage = max(0.0, d.truck.damage_pct - d.start_damage)
        estimated_pay = job.payout(hours, trip_damage)
        tolls = d.trip.toll_expense
        accessorials = carrier_accessorial_charges(job)
        carrier_charges = tolls + charge_total(accessorials)
        driver_charges = _speeding_settlement_fine(d.speeding_strikes)
        net_estimated_pay = max(0.0, estimated_pay - driver_charges)
        advance_due = round(min(self.ctx.profile.pay_advance, net_estimated_pay), 2)
        net_estimated_pay = round(net_estimated_pay - advance_due, 2)
        advance_note = (
            f" A pay advance of {advance_due:,.0f} dollars will be repaid from "
            "this settlement." if advance_due > 0 else "")
        timing = (f"{remaining:.1f} hours remain before the deadline"
                  if remaining >= 0
                  else f"{-remaining:.1f} hours past the deadline")
        if trip_damage > 1:
            cargo_condition = (
                f"Damage consideration: this run added {trip_damage:.0f} "
                "percent truck damage, which may reduce final pay.")
        else:
            cargo_condition = "Cargo condition: no new damage recorded."
        self.ctx.say(
            f"Paperwork for {self.facility}: {job.weight_tons:.0f} tons of "
            f"{job.cargo.label}. Rate sheet lists {job.pay:,.0f} dollars; "
            f"current gross payout is {estimated_pay:,.0f} dollars. "
            f"Carrier-paid or reimbursed charges recorded so far are "
            f"{carrier_charges:,.0f} dollars, including tolls "
            f"{tolls:,.0f} and accessorials {charge_summary(accessorials)}. "
            "Those charges do not reduce driver pay. "
            f"Driver-responsibility charges are estimated at "
            f"{driver_charges:,.0f} dollars, for estimated net driver pay "
            f"{net_estimated_pay:,.0f}.{advance_note} "
            f"{timing}. {cargo_condition} Dock and deliver to settle.")

    def _status(self) -> None:
        d = self.driving
        self.ctx.say(
            f"At {self.facility}. Hauling {d.job.weight_tons:.0f} tons of "
            f"{d.job.cargo.label}. Current speed "
            f"{self.ctx.settings.speed_text(d.truck.speed_mph)}. "
            "Stop, then Dock and deliver.")

    def go_back(self) -> None:
        self.ctx.say("At destination. Dock and deliver to finish.")

    def lines(self) -> list[str]:
        return [
            self.title,
            "",
            f"Facility: {self.facility}",
            f"Speed: {self.driving.truck.speed_mph:.0f} mph",
            "Docking required before delivery settlement.",
            "",
        ] + [
            ("> " if i == self.index else "  ") + item.text
            for i, item in enumerate(self.items)
        ]


class ArrivalState(MenuState):
    title = "Delivery complete"
    intro_help = (
        "Use up and down arrows to review the delivery summary. Enter repeats "
        "the current line. Escape continues."
    )

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.summary_parts: list[str] = []
        self._achievement_messages: list[str] = []
        self._announcements: list[str] = []
        self.summary_lines: list[str] = []
        self.terminal = ctx.world.home_terminal(driving.job.destination)
        self._settle()

    def _settle_bobtail(self, hours: float, trip_damage: float) -> None:
        """Empty reposition run: relocate to the destination city, no pay."""
        d = self.driving
        p = self.ctx.profile
        job = d.job
        self.title = "Repositioned"
        p.current_city = job.destination
        p.truck_fuel_gal = d.truck.fuel_gal
        p.truck_damage_pct = d.truck.damage_pct
        p.game_hours += hours
        p.market.advance_to(p.market_day())
        p.active_trip = None
        self.ctx.save_profile()
        self.summary_parts.insert(0, (
            f"Bobtailed empty to {job.destination} in {hours:.1f} hours. "
            f"It is {clock_text(p.game_hours)}. No load and no pay, but you are "
            f"parked at {self.terminal.name} and can shop the {job.destination} "
            f"dispatch board. Fuel {d.truck.fuel_fraction * 100:.0f} percent."))
        if trip_damage > 1:
            self.summary_parts.append(
                f"The empty run added {trip_damage:.0f} percent truck damage. "
                "Visit the garage when you can.")
        # The arrival screen and announcement read summary_lines, not parts.
        self.summary_lines = list(self.summary_parts)

    def _settle(self) -> None:
        d = self.driving
        p = self.ctx.profile
        job = d.job
        hours = d.trip.game_minutes / 60.0
        trip_damage = max(0.0, d.truck.damage_pct - d.start_damage)
        if job.bobtail:
            self._settle_bobtail(hours, trip_damage)
            return
        gross_pay = job.payout(hours, trip_damage)
        toll_expense = d.trip.toll_expense
        accessorials = carrier_accessorial_charges(job)
        carrier_charges = toll_expense + charge_total(accessorials)
        early_bonus = max(0.0, gross_pay - job.payout(job.deadline_game_h, trip_damage))
        driver_charges = _speeding_settlement_fine(d.speeding_strikes)
        if driver_charges:
            self.summary_parts.append(
                f"Driver-responsibility charges: speeding fines cost you "
                f"{driver_charges:,.0f} dollars.")
        net_pay = max(0.0, gross_pay - driver_charges)
        advance_repaid = round(min(p.pay_advance, net_pay), 2)
        if advance_repaid > 0:
            net_pay = round(net_pay - advance_repaid, 2)
            p.pay_advance = round(p.pay_advance - advance_repaid, 2)
            outstanding = (
                f" {p.pay_advance:,.0f} dollars of advance still outstanding."
                if p.pay_advance >= 1.0 else "")
            self.summary_parts.append(
                f"Pay advance repaid from this settlement: "
                f"{advance_repaid:,.0f} dollars.{outstanding}")
        on_time = hours <= job.deadline_game_h
        p.money += net_pay
        p.current_city = job.destination
        p.truck_fuel_gal = d.truck.fuel_gal
        p.truck_damage_pct = d.truck.damage_pct
        announcements = p.career.record_delivery(
            job.distance_mi, net_pay, on_time, trip_damage)
        p.game_hours += hours
        p.market.advance_to(p.market_day())
        p.active_trip = None
        self.ctx.save_profile()

        self.summary_parts.insert(0, (
            f"Delivered {job.weight_tons:.0f} tons of {job.cargo.label} to "
            f"{job.destination} in {hours:.1f} hours, "
            f"{'on time' if on_time else 'late'}. "
            f"It is {clock_text(p.game_hours)}. "
            f"Gross pay {gross_pay:,.0f} dollars. "
            f"Carrier-paid or reimbursed charges {carrier_charges:,.0f} dollars: "
            f"tolls {toll_expense:,.0f}, accessorials "
            f"{charge_summary(accessorials)}. "
            "These are billed to carrier settlement and not deducted from driver pay. "
            f"Driver-responsibility charges {driver_charges:,.0f} dollars. "
            f"Net driver pay {net_pay:,.0f} "
            f"dollars, and you now have {p.money:,.0f}. "
            f"After unloading, dispatch has you parked at "
            f"{self.terminal.name} for the {job.destination} service area."))
        if early_bonus >= 1.0:
            self.summary_parts.append(
                f"Early delivery bonus: {early_bonus:,.0f} dollars.")
        if trip_damage > 1:
            self.summary_parts.append(
                f"The cargo run added {trip_damage:.0f} percent truck damage. "
                "Visit the garage when you can.")
        self.summary_parts.extend(announcements)
        self._award_arrival_achievements(
            on_time=on_time,
            trip_damage=trip_damage,
            toll_expense=toll_expense,
            route_miles=d.route.miles,
            speeding_strikes=d.speeding_strikes,
            gross_pay=gross_pay,
        )
        self.summary_parts.extend(self._achievement_messages)
        timing = "On time" if on_time else "Late"
        bonus_text = (
            f"Early delivery bonus: {early_bonus:,.0f} dollars"
            if early_bonus >= 1.0 else "No early delivery bonus on this run"
        )
        cargo_condition = (
            f"Truck damage added on this run: {trip_damage:.0f} percent"
            if trip_damage > 1 else "No new damage recorded"
        )
        career_lines = announcements + self._achievement_messages
        if not career_lines:
            career_lines = ["No new career messages."]
        advance_lines = []
        if advance_repaid > 0:
            advance_lines.append(
                f"Pay advance repaid: {advance_repaid:,.0f} dollars.")
        if p.pay_advance >= 1.0:
            advance_lines.append(
                f"Pay advance still outstanding: {p.pay_advance:,.0f} dollars.")
        self.summary_lines = [
            f"Delivered {job.weight_tons:.0f} tons of {job.cargo.label} "
            f"to {job.destination}.",
            f"Trip time: {hours:.1f} hours, {timing.lower()}.",
            f"It is {clock_text(p.game_hours)}.",
            f"Parked at {self.terminal.name} for the "
            f"{job.destination} service area.",
            f"Gross pay: {gross_pay:,.0f} dollars.",
            f"Carrier-paid or reimbursed charges: {carrier_charges:,.0f} "
            f"dollars, including tolls {toll_expense:,.0f} and "
            f"accessorials {charge_summary(accessorials)}.",
            "Carrier charges are not deducted from driver pay.",
            f"Driver-responsibility charges: {driver_charges:,.0f} dollars.",
            *advance_lines,
            f"Net driver pay: {net_pay:,.0f} dollars.",
            f"Money after settlement: {p.money:,.0f} dollars.",
            bonus_text + ".",
            f"Route: {' to '.join(d.route.cities)}.",
            f"Distance credited: {job.distance_mi:.0f} miles.",
            cargo_condition + ".",
            f"Fuel remaining: {d.truck.fuel_fraction * 100:.0f} percent.",
            f"Truck damage now: {d.truck.damage_pct:.0f} percent.",
            *career_lines,
        ]
        self._announcements = announcements

    def _award_arrival_achievements(
            self,
            *,
            on_time: bool,
            trip_damage: float,
            toll_expense: float,
            route_miles: float,
            speeding_strikes: int,
            gross_pay: float = 0.0) -> None:
        p = self.ctx.profile
        route = self.driving.route
        world = self.ctx.world
        states = {world.cities[city].state for city in route.cities}
        regions = {world.cities[city].region for city in route.cities}
        region_count = 0
        for region in regions:
            region_count = add_unique_stat(p, "regions_visited", region)

        ids = ["first_delivery"]
        if on_time:
            ids.append("first_on_time")
        if trip_damage <= 1.0:
            ids.append("clean_delivery")
        if speeding_strikes == 0:
            ids.append("speed_limit_saint")
        if toll_expense > 0:
            ids.append("toll_paid")
        elif route_miles >= 300.0:
            ids.append("no_toll_long")
        if len(states) >= 2:
            ids.append("state_crossing")
        if len(states) >= 3:
            ids.append("multi_state")
        if len(regions) >= 3 or region_count >= 3:
            ids.append("three_regions")
        if route_miles >= 900.0:
            ids.append("long_haul")
        if p.career.deliveries >= 5:
            ids.append("five_deliveries")
        if p.career.deliveries >= 10:
            ids.append("ten_deliveries")
        if p.career.level >= 3:
            ids.append("level_three")
        if p.money >= 25_000.0:
            ids.append("twenty_five_grand")
        if p.career.total_miles >= 1_000.0:
            ids.append("thousand_miles")

        # -- Landmarks: direction, famous corridors, and city-arrival badges --
        origin, dest = route.cities[0], route.cities[-1]
        origin_lon = world.cities[origin].lon
        dest_lon = world.cities[dest].lon
        if dest_lon - origin_lon > 1.0:
            ids.append("eastbound_delivery")
        if origin_lon - dest_lon > 1.0:
            ids.append("westbound_delivery")
        if abs(dest_lon - origin_lon) >= 35.0:
            ids.append("coast_to_coast")
        route66 = {"Chicago", "St. Louis", "Tulsa", "Oklahoma City",
                   "Amarillo", "Albuquerque", "Flagstaff", "Los Angeles"}
        if origin in route66 and dest in route66:
            ids.append("route66_run")
        arrival_hour = self.driving.trip.current_hour
        # Plain "deliver into this city" badges (titles claim nothing extra).
        simple_arrival = {
            "Phoenix": "phoenix_arrival", "Wichita": "wichita_arrival",
            "Bakersfield": "bakersfield_arrival", "Las Vegas": "vegas_arrival",
        }
        if dest in simple_arrival:
            ids.append(simple_arrival[dest])
        # Badges whose title names a condition, so the condition is enforced:
        if dest == "Amarillo" and 5.0 <= arrival_hour < 12.0:   # "by Daybreak"
            ids.append("amarillo_arrival")
        if dest == "Tulsa" and on_time:                         # "Right on Schedule"
            ids.append("tulsa_arrival")
        if world.cities[dest].state == "Georgia" and is_night(arrival_hour):
            ids.append("georgia_arrival")                       # "Midnight Freight"
        # Departures: the title puts the city in the rearview / "out of" it.
        if origin == "Lubbock":                                 # "in the Rearview"
            ids.append("lubbock_arrival")
        if origin == "Detroit":                                 # "Last Load Out of"
            ids.append("detroit_run")

        # -- Challenges: grind milestones, long hauls, spotless runs ----------
        if region_count >= 14:
            ids.append("all_regions")
        if p.career.deliveries >= 50:
            ids.append("fifty_deliveries")
        if p.career.deliveries >= 100:
            ids.append("hundred_deliveries")
        if p.career.total_miles >= 10_000.0:
            ids.append("ten_thousand_miles")
        if p.career.total_miles >= 50_000.0:
            ids.append("fifty_thousand_miles")
        if p.money >= 100_000.0:
            ids.append("hundred_grand")
        if p.career.level >= 10:
            ids.append("max_level")
        if p.career.reputation >= 100.0:
            ids.append("top_reputation")
        if gross_pay >= 4_000.0:
            ids.append("big_payday")
        if route_miles >= 1_200.0 and on_time and trip_damage <= 1.0:
            ids.append("grueling_clean")
        if any(leg.terrain == "mountain" for leg in route.legs) and trip_damage <= 1.0:
            ids.append("mountain_clean")
        if len(route.legs) >= 4:
            ids.append("multi_leg_haul")
        # Five consecutive on-time, undamaged, ticket-free deliveries.
        stats = p.achievement_stats if isinstance(p.achievement_stats, dict) else {}
        p.achievement_stats = stats
        perfect = on_time and trip_damage <= 1.0 and speeding_strikes == 0
        streak = int(stats.get("perfect_streak", 0)) + 1 if perfect else 0
        stats["perfect_streak"] = streak
        if streak >= 5:
            ids.append("perfect_streak")

        for achievement_id in ids:
            result = self.ctx.award_achievement(achievement_id, announce=False)
            if result is not None:
                self._achievement_messages.append(result.message)
        self.ctx.save_profile()

    def enter(self) -> None:
        self.ctx.audio.stop_world()
        self.ctx.audio.play("ui/job_complete")
        if self._announcements or self._achievement_messages:
            self.ctx.audio.play("ui/level_up")
        self.ctx.audio.play("ui/cash")
        self.items = self.build_items()
        self.index = min(self.index, max(0, len(self.items) - 1))
        self.announce_entry()

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.title}. {self.current_text()}",
            interrupt=False,
        )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(line, lambda line=line: self.ctx.say(line),
                     help="Repeat this settlement line.")
            for line in self.summary_lines
        ]
        items.append(MenuItem("Continue to " + self.terminal.name, self._continue))
        return items

    def go_back(self) -> None:
        self._continue()

    def _continue(self) -> None:
        from .city import CityMenuState

        self.ctx.replace_state(CityMenuState(self.ctx))

    def lines(self) -> list[str]:
        return [self.title, ""] + self.summary_lines + [""] + [
            ("> " if i == self.index else "  ") + item.text
            for i, item in enumerate(self.items)
        ]
