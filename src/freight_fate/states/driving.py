"""The driving state: live truck control with a fully audio HUD.

Continuous controls (throttle, brake, clutch) are sampled from held keys
each frame. Everything the player needs to know is available on demand from
information keys, and important changes announce themselves.
"""

from __future__ import annotations

import logging
import random

import pygame

from ..data.world import Route
from ..models.jobs import Job, job_from_payload, job_payload
from ..sim import hos
from ..sim.hos import HosClock, clock_text, is_night, time_of_day
from ..sim.transmission import REVERSE
from ..sim.trip import Trip, TripEventKind
from ..sim.vehicle import G, TruckState
from ..sim.weather import WeatherSystem
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

CRUISE_MIN_MPH = 20.0             # cruise control needs road speed to hold
ACC_BASE_GAP_SECONDS = 3.0        # clear-weather adaptive cruise gap
ENGINE_SHUTDOWN_SAFE_MPH = 5.0    # prevent accidental kill-switch use at speed
DELIVERY_PARK_MPH = 3.0           # destination settlement requires parking speed
DOCKING_MAX_MPH = 1.0             # final dock/park action needs a full stop
DRIVE_PHASE_PICKUP = "pickup"
DRIVE_PHASE_DELIVERY = "delivery"


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
        self.truck.transmission.automatic = ctx.settings.automatic_transmission
        self.truck.fuel_gal = min(profile.truck_fuel_gal, self.truck.specs.fuel_tank_gal)
        self.truck.damage_pct = profile.truck_damage_pct
        self.start_damage = profile.truck_damage_pct
        region = ctx.world.cities[job.origin].region
        self.weather = WeatherSystem(
            region,
            seed=self.trip_seed,
            provider=ctx.real_weather_provider(),
        )
        self._weather_source_real = ctx.settings.real_weather
        trip_start_hour = profile.game_hours % 24.0 if start_hour is None else start_hour
        self.trip = Trip(route, self.truck, self.weather,
                         time_scale=ctx.settings.time_scale, seed=self.trip_seed,
                         start_hour=trip_start_hour)
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
        self._cruise_mph: float | None = None
        self._cruise_throttle = 0.0
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._arrival_stop_said = False
        self._arrival_full_stop_said = False
        self._arrival_menu_open = False
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
            "hos": self.hos.to_dict(),
            "fatigue": self.ctx.profile.fatigue,
            "hos_fine_count": self.hos_fine_count,
            "enforcement_events": sorted(self.enforcement_events),
            "out_of_service_count": self.out_of_service_count,
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
            return state
        except (KeyError, TypeError, ValueError):
            log.warning("Could not resume saved trip", exc_info=True)
            return None

    # -- lifecycle ---------------------------------------------------------------

    def enter(self) -> None:
        self.ctx.audio.stop_music(800)
        self.ctx.audio.play_music("open_road", fade_ms=2500)
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
                "You are parked. Press E to start the engine.",
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
                         "Press E to start the engine, F1 for the controls.",
                         interrupt=False)
        if self.tutorial:
            self.tutorial.begin()

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
            self._speak_full_status()
        elif key == pygame.K_f:
            self._speak_fuel()
        elif key == pygame.K_c:
            self._speak_clock()
        elif key == pygame.K_r:
            self.ctx.say(self.trip.progress_summary(self.ctx.settings.imperial_units))
        elif key == pygame.K_v:
            self._speak_weather()
        elif key == pygame.K_F1:
            objective_help = (
                f"Your current objective is pickup: drive to {self._pickup_facility_text()}, "
                "come to a full stop at the gate, then use the pickup facility "
                "menu to check in and load. "
                if self.phase == DRIVE_PHASE_PICKUP else
                "Pickup and loading are complete. At your destination, come to a "
                "full stop, then dock and deliver from the facility menu. ")
            self.ctx.say(
                "Hold Up arrow to accelerate, Down arrow to brake. "
                "When stopped in automatic, hold Down arrow to reverse slowly; "
                "touch Up arrow to brake and return to forward. "
                "Hold B for the emergency brake, the hardest possible stop. "
                "K sets adaptive cruise at your current speed; bad weather "
                "increases the following gap, and braking cancels. "
                "X takes the next announced exit: slow to 45 for the ramp, "
                "then brake to a stop for the rest stop menu. "
                "E starts the engine, and stops it only below 5 miles per hour. "
                f"{objective_help}"
                "Space speed. Tab full status. F fuel. "
                "C clock, deadline, and hours of service. "
                "R route. V weather. T route POI menu when already stopped "
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
                self.ctx.say("Engine running." + (
                    "" if not t.transmission.automatic
                    else " Hold the Up arrow to drive."))
                if self.tutorial:
                    self.tutorial.on_engine_started()
            else:
                self.ctx.audio.play("ui/error")
                if t.fuel_gal <= 0:
                    # never a dead end: the roadside rescue always comes
                    self._handle_out_of_fuel()
                else:
                    self.ctx.say("The engine will not start.")

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
                     f"{t.rpm:.0f} RPM.")

    def _gear_text(self) -> str:
        tr = self.truck.transmission
        if tr.in_neutral:
            return "neutral"
        if tr.in_reverse:
            return "reverse"
        return f"gear {tr.gear}"

    def _speak_full_status(self) -> None:
        t = self.truck
        limit, reason = self.trip.speed_limit_at(self.trip.position_mi)
        progress = (self._pickup_progress_summary()
                    if self.phase == DRIVE_PHASE_PICKUP else
                    self.trip.progress_summary(self.ctx.settings.imperial_units))
        parts = [
            self.ctx.settings.speed_text(t.speed_mph),
            f"speed limit {limit:.0f}" + (f" in a {reason} zone" if reason else ""),
            progress,
            f"fuel {t.fuel_fraction * 100:.0f} percent",
            f"it is {time_of_day(self.trip.current_hour)}",
        ]
        if self._cruise_mph is not None:
            parts.insert(1, "adaptive cruise set at "
                            f"{self.ctx.settings.speed_text(self._cruise_mph)}")
            context = self.trip.traffic_context()
            if context is not None:
                parts.insert(2, f"traffic ahead {context.gap_mi:.1f} miles, "
                                f"{context.lead.speed_mph:.0f} miles per hour")
        if t.damage_pct - self.start_damage > 1:
            parts.append(f"new damage {t.damage_pct - self.start_damage:.0f} percent")
        if self.ctx.settings.speech_verbosity >= 1:
            fatigue = self.ctx.profile.fatigue
            if fatigue >= hos.FATIGUE_DROWSY:
                parts.append(f"fatigue {fatigue:.0f} percent")
            parts.append(self.hos.summary(self.ctx.settings.hos_mode).rstrip("."))
            context = self._hos_route_context()
            if context:
                parts.append(context)
        self.ctx.say(". ".join(parts) + ".")

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
                f"{self.trip.remaining_miles:.1f} miles remain. "
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
        legal_miles = max(0.0, remaining_min / 60.0 * max(35.0, min(62.0, self.truck.speed_mph or 55.0)))
        next_stop = self.trip.upcoming_stop(max(legal_miles + 5.0, 5.0))
        action = "break" if kind == "break" else "sleep"
        if next_stop is None:
            return (f"No route stop is currently visible before the next {action} "
                    f"limit, due in {remaining_min / 60.0:.1f} hours.")
        ahead = max(0.0, next_stop.at_mi - self.trip.position_mi)
        verdict = "before" if ahead <= legal_miles else "after"
        return (f"Next legal stop: {next_stop.spoken_name} in {ahead:.0f} miles, "
                f"{next_stop.parking_text}, {verdict} the next {action} limit.")

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
        accelerating = keys[pygame.K_UP]
        braking_key = keys[pygame.K_DOWN]
        backing = self._update_reverse_controls(accelerating, braking_key)
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
        self._update_cruise(dt, braking, accelerating)

        if t.transmission.automatic and t.engine_on:
            new_gear = t.auto_shift()
            if new_gear is not None:
                self.ctx.audio.play("vehicle/gear_shift", volume=0.65)

        was_on = t.engine_on
        t.update(dt)
        if was_on and not t.engine_on:
            self.ctx.audio.engine_stop()
            if t.stalled:
                self.ctx.say_event("The engine stalled. Press E to restart, and "
                                   "use a lower gear at low speed.")
            elif t.fuel_gal <= 0:
                self._handle_out_of_fuel()

        pos_before = self.trip.position_mi
        for event in self.trip.update(dt):
            self._handle_trip_event(event)
        self._update_exit(self.trip.position_mi - pos_before)

        self._update_hours_and_fatigue(dt)
        self._update_audio()
        self._update_announcements(dt)
        self._update_hazard(dt)
        self._update_speeding(dt)
        if self.tutorial:
            self.tutorial.update(dt, t)
        if self.trip.finished:
            if self.phase == DRIVE_PHASE_PICKUP:
                self._handle_pickup_gate()
            else:
                self._handle_arrival_gate()

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

    def _update_audio(self) -> None:
        t = self.truck
        audio = self.ctx.audio
        if t.engine_on and not audio.engine_running:
            audio.engine_start()
        audio.set_engine_rpm(t.rpm, t.throttle)
        audio.set_road_noise(t.velocity_mps)
        eff = self.weather.effects
        audio.set_weather(eff.sound)
        audio.set_wind(eff.wind)
        if is_night(self.trip.current_hour):
            audio.set_ambient("ambient/night", volume=0.3)
            audio.play_music("night_haul", fade_ms=4000)
        else:
            audio.set_ambient(None)
            audio.play_music("open_road", fade_ms=4000)
        if self.weather.should_thunder():
            audio.play("weather/thunder", volume=0.9)

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
        if kind == TripEventKind.HAZARD:
            if self._ramp_mi is not None:
                return   # off the highway: the hazard passes you by
            if self._cruise_mph is not None:
                self._cancel_cruise()   # hands back on the wheel to brake
            self.ctx.audio.play("ui/warning")
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
        elif kind == TripEventKind.TOLL_CHARGED:
            self.ctx.audio.play("ui/notify", volume=0.55)
            self.ctx.say_event(event.message, interrupt=False)
        elif kind == TripEventKind.ARRIVED:
            pass  # handled by _arrive()
        elif self._event_disables_cruise(event):
            self._cancel_cruise_for_restricted_area(event.message)
        else:
            self.ctx.say_event(event.message, interrupt=False)
        if kind == TripEventKind.ZONE_ENTER:
            self.ctx.audio.play("ui/notify", volume=0.7)

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
        self.ctx.audio.play("ui/notify", volume=0.55)
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
            self._place_out_of_service()
            return
        self.ctx.say_event(message, interrupt=True)

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
        if self.truck.speed_mph > 3:
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

    def _take_exit(self) -> None:
        if self._ramp_mi is not None:
            self.ctx.say("You are already on the exit ramp. Brake to a stop.")
            return
        if self._exit_stop is not None:
            self._exit_stop = None
            self.ctx.say("Exit canceled. Staying on the highway.")
            return
        stop = self.trip.upcoming_stop(EXIT_WINDOW_MI)
        if stop is None:
            self.ctx.say("No exit coming up. Exits are announced as you "
                         "approach them.")
            return
        self._exit_stop = stop
        self.ctx.audio.play("ui/notify", volume=0.5)
        ahead = stop.at_mi - self.trip.position_mi
        self.ctx.say(f"Signaling for the {stop.spoken_name} exit, "
                     f"{ahead:.1f} miles ahead. "
                     f"Slow to {RAMP_MAX_MPH:.0f} or less for the ramp.")

    def _update_exit(self, moved_mi: float) -> None:
        """Advance an armed exit or an active ramp; opens the stop menu."""
        if self._ramp_mi is not None:
            self._ramp_mi -= moved_mi
            if self._ramp_mi > 0:
                return
            if self.truck.speed_mph <= 3:
                stop = self._ramp_stop
                self._ramp_mi = None
                self._ramp_stop = None
                self._open_poi_stop(stop)
            elif not self._ramp_end_said:
                self._ramp_end_said = True
                self.ctx.say_event(f"You are at {self._ramp_stop.spoken_name}. "
                                   "Come to a complete stop.")
            return
        stop = self._exit_stop
        if stop is None or self.trip.position_mi < stop.at_mi:
            return
        self._exit_stop = None
        if self.truck.speed_mph <= RAMP_MAX_MPH:
            self._ramp_mi = RAMP_LENGTH_MI
            self._ramp_stop = stop
            self._ramp_end_said = False
            self._cancel_cruise()
            self.ctx.audio.play("ui/notify", volume=0.7)
            self.ctx.say_event(f"You take the exit for {stop.spoken_name}. "
                               "Half a mile of ramp; brake to a stop at "
                               "the end.")
        else:
            self.ctx.say_event("You were going too fast for the ramp and "
                               f"missed the exit for {stop.spoken_name}.")

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
        if braking or t.emergency_brake or not t.engine_on or t.stalled:
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
        self._set_status("Pickup facility ahead: slow down and park to load.")
        self.ctx.say_event(
            f"Pickup facility ahead: {self._pickup_facility_text()}. "
            f"Slow below {DELIVERY_PARK_MPH:.0f} miles per hour, then come "
            "to a full stop to check in and load.",
            interrupt=True)

    def _handle_pickup_creep(self) -> None:
        if self._arrival_full_stop_said:
            return
        self._arrival_full_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/notify", volume=0.7)
        self._set_status("Pickup gate reached: come to a full stop to load.")
        self.ctx.say_event(
            f"You are at {self._pickup_facility_text()}. Hold the brake and "
            "come to a full stop; the pickup facility menu opens when stopped.",
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
        p.truck_fuel_gal = self.truck.fuel_gal
        p.truck_damage_pct = self.truck.damage_pct
        p.game_hours += self.trip.game_minutes / 60.0
        p.market.advance_to(p.market_day())
        p.active_trip = pickup_snapshot(self.job)
        self.ctx.save_profile()
        self._set_status("Parked at pickup. Check in and load from the facility menu.")
        self.ctx.replace_state(PickupFacilityState(self.ctx, self.job, driving=self))

    def _arrive(self) -> None:
        self.ctx.replace_state(ArrivalState(self.ctx, self))

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
        self._set_status("Destination reached: slow down and park to deliver.")
        self.ctx.say_event(
            f"Destination facility ahead: {self._destination_facility_text()}. "
            f"Slow below {DELIVERY_PARK_MPH:.0f} miles per hour, then come "
            "to a full stop to open the facility menu.",
            interrupt=True)

    def _handle_arrival_creep(self) -> None:
        if self._arrival_full_stop_said:
            return
        self._arrival_full_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/notify", volume=0.7)
        self._set_status("Destination gate reached: come to a full stop to dock.")
        self.ctx.say_event(
            f"You are at {self._destination_facility_text()}. Hold the brake "
            "and come to a full stop; the facility menu opens when stopped.",
            interrupt=False)

    def _open_facility_arrival(self) -> None:
        if self._arrival_menu_open:
            return
        self._arrival_menu_open = True
        self._cancel_cruise()
        self.truck.throttle = 0.0
        self._set_status("Parked at destination. Dock and deliver from the facility menu.")
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
            if self.ctx.settings.automatic_transmission:
                self.stage = 2
                self.ctx.say("Now hold the Up arrow to accelerate. The transmission "
                             "shifts for you.", interrupt=False)
            else:
                self.ctx.say("Now hold Left Shift to press the clutch, then press 1 "
                             "for first gear, and release the clutch.", interrupt=False)

    def on_gear_engaged(self) -> None:
        if self.stage == 1:
            self.stage = 2
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

    def announce_entry(self) -> None:
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
        items.append(MenuItem("Back to the road", self.go_back))
        return items

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
        _advance_rest_clock(d, hos.SLEEP_MIN)
        d.hos.sleep()
        p.fatigue = hos.rest_sleep(p.fatigue)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"You slept 10 hours and woke rested. "
                     f"It is {clock_text(d.trip.current_hour)}. "
                     f"Hours of service reset. {_deadline_text(d)}")

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
                          "a fine for illegal parking."),
        ]

    def go_back(self) -> None:
        self._drive_on()

    def _drive_on(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
        self.ctx.say("Back on the road. The next stop is announced as you "
                     "approach it. Press E to start the engine.", interrupt=True)

    def _shoulder(self) -> None:
        d = self.driving
        p = self.ctx.profile
        _advance_rest_clock(d, hos.SLEEP_MIN)
        d.hos.sleep()
        p.fatigue = hos.rest_shoulder(p.fatigue)
        parts = [f"You sleep poorly on the shoulder, woken again and again by "
                 f"passing trucks. It is {clock_text(d.trip.current_hour)}. "
                 f"Hours of service reset, but you are still tired."]
        if hos.shoulder_fine_due(d.trip_seed, self.stop.at_mi):
            p.money -= hos.SHOULDER_FINE
            self.ctx.audio.play("ui/error")
            parts.append(f"A trooper ticketed you for illegal parking: "
                         f"{hos.SHOULDER_FINE:,.0f} dollars. "
                         f"You have {p.money:,.0f} dollars.")
        parts.append(_deadline_text(d))
        self.ctx.pop_state()
        self.ctx.say(" ".join(parts), interrupt=True)


class PauseMenuState(MenuState):
    title = "Paused"

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def enter(self) -> None:
        self.ctx.audio.play("ui/pause")
        self.ctx.audio.stop_world()
        super().enter()

    def build_items(self) -> list[MenuItem]:
        drive_label = "pickup drive" if self.driving.phase == DRIVE_PHASE_PICKUP else "delivery"
        return [
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
            MenuItem("Save and quit to main menu", self._quit_to_menu,
                     help="Your money, truck, and trip progress are saved. "
                          "This drive resumes from here when you continue."),
        ]

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
                f"{d._pickup_progress_summary()} {hours_used:.1f} hours used.")
            return
        self.ctx.say(
            f"Hauling {d.job.weight_tons:.0f} tons of {d.job.cargo.label} "
            f"to {d.job.destination}. "
            f"{d.trip.progress_summary(self.ctx.settings.imperial_units)} "
            f"{hours_used:.1f} hours used of {d.job.deadline_game_h:.0f}.")

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

        p = self.ctx.profile
        p.truck_fuel_gal = self.driving.truck.fuel_gal
        p.truck_damage_pct = self.driving.truck.damage_pct
        p.active_trip = self.driving.snapshot()
        self.ctx.save_profile()
        drive_label = "pickup drive" if self.driving.phase == DRIVE_PHASE_PICKUP else "delivery"
        self.ctx.say(f"Saved. Your {drive_label} will resume where you left off.",
                     interrupt=True)
        self.ctx.reset_to(MainMenuState(self.ctx))


class FacilityArrivalState(MenuState):
    title = "Destination facility"
    open_sound_key = "facility/dock_gate"
    intro_help = ("Use up and down arrows to navigate, Enter to select. "
                  "Check paperwork reviews the estimate. Dock and deliver "
                  "completes the delivery.")

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    @property
    def facility(self) -> str:
        return self.driving._destination_facility_text()

    def announce_entry(self) -> None:
        self.ctx.audio.set_ambient("ambient/warehouse", volume=0.3)
        self.ctx.say(
            f"Arrived at {self.facility}. You are parked at the gate. "
            f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem("Dock and deliver", self._dock,
                     help="Back into the assigned dock, set the brakes, and "
                          "hand off the paperwork to complete this delivery."),
            MenuItem("Check paperwork", self._paperwork,
                     help="Review estimated pay, deadline, cargo condition, "
                          "and any late or damage considerations without "
                          "settling the delivery."),
            MenuItem("Check arrival status", self._status,
                     help="Hear the destination facility, cargo, speed, and "
                          "delivery instruction again."),
        ]

    def _dock(self) -> None:
        d = self.driving
        if d.truck.speed_mph > DOCKING_MAX_MPH:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Hold the brake and come to a full stop before docking.")
            return
        d.truck.throttle = 0.0
        d.truck.brake = 1.0
        d._set_status("Docked. Delivery paperwork signed.")
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
        net_estimated_pay = estimated_pay - tolls
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
            f"Toll expenses recorded so far are {tolls:,.0f} dollars, "
            f"for an estimated net settlement of {net_estimated_pay:,.0f}. "
            f"{timing}. {cargo_condition} Dock and deliver when ready; "
            "checking paperwork does not settle the load.")

    def _status(self) -> None:
        d = self.driving
        self.ctx.say(
            f"At {self.facility}. Hauling {d.job.weight_tons:.0f} tons of "
            f"{d.job.cargo.label}. Current speed "
            f"{self.ctx.settings.speed_text(d.truck.speed_mph)}. "
            "Select Dock and deliver when stopped to complete the delivery.")

    def go_back(self) -> None:
        self.ctx.say("You are checked in at the destination. Select Dock and "
                     "deliver to complete the job.")

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

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.summary_parts: list[str] = []
        self.terminal = ctx.world.home_terminal(driving.job.destination)
        self._settle()

    def _settle(self) -> None:
        d = self.driving
        p = self.ctx.profile
        job = d.job
        hours = d.trip.game_minutes / 60.0
        trip_damage = max(0.0, d.truck.damage_pct - d.start_damage)
        gross_pay = job.payout(hours, trip_damage)
        pay = gross_pay
        toll_expense = d.trip.toll_expense
        early_bonus = max(0.0, gross_pay - job.payout(job.deadline_game_h, trip_damage))
        if d.speeding_strikes:
            fine = min(400.0, 80.0 * d.speeding_strikes)
            pay = max(0.0, pay - fine)
            self.summary_parts.append(f"Speeding fines cost you {fine:,.0f} dollars.")
        net_pay = pay - toll_expense
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
            f"Toll expenses {toll_expense:,.0f} dollars charged through the "
            f"company transponder settlement. Net settlement {net_pay:,.0f} "
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
        self._announcements = announcements

    def enter(self) -> None:
        self.ctx.audio.stop_world()
        self.ctx.audio.play("ui/job_complete")
        if self._announcements:
            self.ctx.audio.play("ui/level_up")
        self.ctx.audio.play("ui/cash")
        super().enter()

    def announce_entry(self) -> None:
        self.ctx.say(" ".join(self.summary_parts) +
                     " Press Enter to continue.", interrupt=False)

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem("Continue to " + self.terminal.name, self._continue),
            MenuItem("Hear the summary again",
                     lambda: self.ctx.say(" ".join(self.summary_parts))),
        ]

    def go_back(self) -> None:
        self._continue()

    def _continue(self) -> None:
        from .city import CityMenuState

        self.ctx.replace_state(CityMenuState(self.ctx))

    def lines(self) -> list[str]:
        return [self.title, ""] + self.summary_parts + [""] + [
            ("> " if i == self.index else "  ") + item.text
            for i, item in enumerate(self.items)
        ]
