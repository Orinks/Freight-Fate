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
from ..models.jobs import CARGO_CATALOG, Job, facility_label
from ..sim import hos
from ..sim.hos import HosClock, clock_text, is_night, time_of_day
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

# Highway exits: signal inside the window, slow enough to make the ramp.
EXIT_WINDOW_MI = 5.0              # how far out X can arm the upcoming exit
RAMP_MAX_MPH = 45.0               # any faster and you blow past the exit
RAMP_LENGTH_MI = 0.5              # deceleration lane plus ramp to the stop

CRUISE_MIN_MPH = 20.0             # cruise control needs road speed to hold
ENGINE_SHUTDOWN_SAFE_MPH = 5.0    # prevent accidental kill-switch use at speed
DELIVERY_PARK_MPH = 3.0           # destination settlement requires parking speed
DOCKING_MAX_MPH = 1.0             # final dock/park action needs a full stop


class DrivingState(State):
    def __init__(self, ctx, job: Job, route: Route, trip_seed: int | None = None) -> None:
        super().__init__(ctx)
        self.job = job
        self.route = route
        self.trip_seed = trip_seed if trip_seed is not None else random.randrange(2**31)
        self.resumed = False
        profile = ctx.profile
        self.truck = TruckState(specs=profile.truck_specs())
        self.truck.transmission.automatic = ctx.settings.automatic_transmission
        self.truck.fuel_gal = min(profile.truck_fuel_gal, self.truck.specs.fuel_tank_gal)
        self.truck.damage_pct = profile.truck_damage_pct
        self.start_damage = profile.truck_damage_pct
        region = ctx.world.cities[job.origin].region
        self.weather = WeatherSystem(region, provider=ctx.real_weather_provider())
        self._weather_source_real = ctx.settings.real_weather
        self.trip = Trip(route, self.truck, self.weather,
                         time_scale=ctx.settings.time_scale, seed=self.trip_seed,
                         start_hour=profile.game_hours % 24.0)
        self.tutorial = Tutorial(ctx) if not profile.tutorial_done else None

        self.hos = profile.hos          # shift clock lives on the profile
        self.hos_fine_count = 0         # escalates with each failed inspection
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
        self._arrival_stop_said = False
        self._arrival_menu_open = False
        self._status_text = "Press E to start the engine."

    # -- save and resume -----------------------------------------------------------

    def snapshot(self) -> dict:
        """Everything needed to resume this delivery from a save."""
        job = self.job
        return {
            "kind": "delivery",
            "job": {
                "cargo": job.cargo.key,
                "weight_tons": job.weight_tons,
                "origin": job.origin,
                "origin_location": job.origin_location,
                "destination": job.destination,
                "distance_mi": job.distance_mi,
                "pay": job.pay,
                "deadline_game_h": job.deadline_game_h,
                "market_mult": job.market_mult,
                "origin_type": job.origin_type,
                "destination_location": job.destination_location,
                "destination_type": job.destination_type,
            },
            "route_cities": list(self.route.cities),
            "trip_seed": self.trip_seed,
            "position_mi": self.trip.position_mi,
            "game_minutes": self.trip.game_minutes,
            "start_damage": self.start_damage,
            "speeding_strikes": self.speeding_strikes,
            "hos": self.hos.to_dict(),
            "fatigue": self.ctx.profile.fatigue,
            "hos_fine_count": self.hos_fine_count,
        }

    @classmethod
    def from_snapshot(cls, ctx, data: dict) -> DrivingState | None:
        """Rebuild a saved delivery; None if the snapshot is unreadable."""
        try:
            j = data["job"]
            cargo = CARGO_CATALOG[j["cargo"]]
            route = ctx.world.route_from_cities(data["route_cities"])
            if route is None:
                return None
            job = Job(cargo, float(j["weight_tons"]), j["origin"],
                      j["origin_location"], j["destination"],
                      float(j["distance_mi"]), float(j["pay"]),
                      float(j["deadline_game_h"]),
                      market_mult=float(j.get("market_mult", 1.0)),
                      origin_type=str(j.get("origin_type", "terminal")),
                      destination_location=str(j.get("destination_location", "")),
                      destination_type=str(j.get("destination_type", "terminal")))
            state = cls(ctx, job, route, trip_seed=int(data["trip_seed"]))
            state.resumed = True
            state.start_damage = float(data["start_damage"])
            state.speeding_strikes = int(data["speeding_strikes"])
            state.trip.restore(float(data["position_mi"]), float(data["game_minutes"]))
            # HOS and fatigue: absent in pre-1.5 snapshots, defaulting to a
            # fresh clock and a rested driver.
            if "hos" in data:
                ctx.profile.hos = HosClock.from_dict(data["hos"])
                state.hos = ctx.profile.hos
            ctx.profile.fatigue = max(0.0, min(100.0, float(
                data.get("fatigue", ctx.profile.fatigue))))
            state.hos_fine_count = int(data.get("hos_fine_count", 0))
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
            self.ctx.say(
                f"Resuming your loaded delivery: {self.job.weight_tons:.0f} tons of "
                f"{self.job.cargo.label} to {self.job.destination}. "
                f"{self.trip.progress_summary(self.ctx.settings.imperial_units)} "
                f"{hours_used:.1f} hours used of {self.job.deadline_game_h:.0f}. "
                f"It is {now}. Transmission is {mode}. "
                f"Weather: {self.weather.describe()}. "
                "You are parked. Press E to start the engine.",
                interrupt=False)
        else:
            self.ctx.say(f"You are at the wheel. It is {now}. "
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
            self.ctx.say(
                "Hold Up arrow to accelerate, Down arrow to brake. "
                "Hold B for the emergency brake, the hardest possible stop. "
                "K sets cruise control at your current speed; braking cancels. "
                "X takes the next announced exit: slow to 45 for the ramp, "
                "then brake to a stop for the rest stop menu. "
                "E starts the engine, and stops it only below 5 miles per hour. "
                "Pickup and loading are complete. At your destination, come to a "
                "full stop, then dock and deliver from the facility menu. "
                "Space speed. Tab full status. F fuel. "
                "C clock, deadline, and hours of service. "
                "R route. V weather. T rest stop menu when already stopped "
                "at one: refuel, take a break, or sleep. H horn. "
                "J engine brake. Escape pause menu. "
                + ("" if self.truck.transmission.automatic else
                   "Hold Left Shift for clutch, then 1 through 0 for gears, N for neutral."))

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
        gear = "neutral" if t.transmission.in_neutral else f"gear {t.transmission.gear}"
        self.ctx.say(f"{self.ctx.settings.speed_text(t.speed_mph)}, {gear}, "
                     f"{t.rpm:.0f} RPM.")

    def _speak_full_status(self) -> None:
        t = self.truck
        limit, reason = self.trip.speed_limit_at(self.trip.position_mi)
        parts = [
            self.ctx.settings.speed_text(t.speed_mph),
            f"speed limit {limit:.0f}" + (f" in a {reason} zone" if reason else ""),
            self.trip.progress_summary(self.ctx.settings.imperial_units),
            f"fuel {t.fuel_fraction * 100:.0f} percent",
            f"it is {time_of_day(self.trip.current_hour)}",
        ]
        if self._cruise_mph is not None:
            parts.insert(1, "cruise control set at "
                            f"{self.ctx.settings.speed_text(self._cruise_mph)}")
        if t.damage_pct - self.start_damage > 1:
            parts.append(f"new damage {t.damage_pct - self.start_damage:.0f} percent")
        if self.ctx.settings.speech_verbosity >= 1:
            fatigue = self.ctx.profile.fatigue
            if fatigue >= hos.FATIGUE_DROWSY:
                parts.append(f"fatigue {fatigue:.0f} percent")
            parts.append(self.hos.summary(self.ctx.settings.hos_mode).rstrip("."))
        self.ctx.say(". ".join(parts) + ".")

    def _speak_fuel(self) -> None:
        t = self.truck
        mpg = 6.0
        range_mi = t.fuel_gal * mpg
        self.ctx.say(f"Fuel {t.fuel_fraction * 100:.0f} percent, {t.fuel_gal:.0f} gallons. "
                     f"Estimated range {self.ctx.settings.distance_text(range_mi)}.")

    def _speak_clock(self) -> None:
        hours_used = self.trip.game_minutes / 60.0
        remaining = self.job.deadline_game_h - hours_used
        eta = self.trip.eta_game_hours()
        basis = ("at your current speed"
                 if self.truck.speed_mph >= self.trip.ETA_MIN_MPH
                 else "at a typical highway pace")
        now = f"It is {clock_text(self.trip.current_hour)}."
        hos_part = self.hos.summary(self.ctx.settings.hos_mode)
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
        if keys[pygame.K_UP]:
            t.throttle = min(1.0, t.throttle + ramp)
        else:
            t.throttle = max(0.0, t.throttle - ramp * 2)
        braking = keys[pygame.K_DOWN]
        if braking:
            new_brake = min(1.0, t.brake + ramp * 1.5)
            if t.brake < 0.05 and new_brake >= 0.05 and t.velocity_mps > 1:
                self.ctx.audio.play("vehicle/brake_air", volume=0.6)
            t.brake = new_brake
        else:
            t.brake = max(0.0, t.brake - ramp * 3)
        emergency = keys[pygame.K_b]
        if emergency:
            # no ramp: slams to full application instantly, plus spring brakes
            if not t.emergency_brake and t.velocity_mps > 1:
                self.ctx.audio.play("vehicle/brake_air", volume=1.0)
            t.throttle = 0.0
            t.brake = 1.0
        t.emergency_brake = emergency
        t.transmission.clutch = 1.0 if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] else 0.0
        self._update_cruise(dt, braking, keys[pygame.K_UP])

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
            self._handle_arrival_gate()

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
        if mode != "off":
            for message in self.hos.check_warnings(mode):
                self.ctx.audio.play("ui/warning")
                self.ctx.say_event(message, interrupt=False)
        self.trip.hos_violation = mode != "off" and self.hos.in_violation(mode)

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
        elif kind == TripEventKind.ARRIVED:
            pass  # handled by _arrive()
        else:
            self.ctx.say_event(event.message, interrupt=False)
        if kind == TripEventKind.ZONE_ENTER:
            self.ctx.audio.play("ui/notify", volume=0.7)

    def _handle_inspection(self, event) -> None:
        """Caught driving past an HOS limit: escalating fine, reputation hit."""
        p = self.ctx.profile
        fine = hos.HOS_FINES[min(self.hos_fine_count, len(hos.HOS_FINES) - 1)]
        self.hos_fine_count += 1
        p.money -= fine   # can go negative; never a game over
        p.career.reputation = max(0.0, p.career.reputation - hos.HOS_REPUTATION_HIT)
        self.ctx.audio.play("ui/error")
        self.ctx.say_event(f"{event.message} You are over your hours of service. "
                           f"Fined {fine:,.0f} dollars, and your reputation took "
                           "a hit. Sleep 10 hours at a rest stop to reset your "
                           "clock.", interrupt=True)

    def _try_rest_stop(self) -> None:
        stop = self.trip.nearest_stop_within()
        if stop is None:
            self.ctx.say("There is no rest stop here. Stops are announced as you "
                         "approach them.")
            return
        if self.truck.speed_mph > 3:
            self.ctx.say("Come to a complete stop first.")
            return
        if hos.parking_is_full(self.trip_seed, stop.at_mi, self.trip.current_hour):
            self.ctx.push_state(ParkingFullState(self.ctx, self, stop))
        else:
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
                if hos.parking_is_full(self.trip_seed, stop.at_mi,
                                       self.trip.current_hour):
                    self.ctx.push_state(ParkingFullState(self.ctx, self, stop))
                else:
                    self.ctx.push_state(RestStopState(self.ctx, self, stop))
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
            self.ctx.say("Cruise control off.")
            return
        if not t.engine_on or t.speed_mph < CRUISE_MIN_MPH:
            self.ctx.say("Cruise control needs the engine running and at "
                         f"least {CRUISE_MIN_MPH:.0f} miles per hour.")
            return
        self._cruise_mph = t.speed_mph
        self._cruise_throttle = t.throttle
        self.ctx.audio.play("ui/notify", volume=0.5)
        self.ctx.say("Cruise control set at "
                     f"{self.ctx.settings.speed_text(t.speed_mph)}. "
                     "K or braking cancels.")

    def _cancel_cruise(self) -> None:
        self._cruise_mph = None
        self._cruise_throttle = 0.0

    def _update_cruise(self, dt: float, braking: bool,
                       accelerating: bool) -> None:
        """Hold the set speed with a slow integrating throttle."""
        if self._cruise_mph is None:
            return
        t = self.truck
        if braking or t.emergency_brake or not t.engine_on or t.stalled:
            self._cancel_cruise()
            self.ctx.say_event("Cruise control off.", interrupt=False)
            return
        if accelerating:
            return   # manual override; cruise resumes when the key lifts
        error = self._cruise_mph - t.speed_mph
        self._cruise_throttle = max(0.0, min(
            1.0, self._cruise_throttle + error * 0.08 * dt))
        t.throttle = self._cruise_throttle

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

    def _arrive(self) -> None:
        self.ctx.replace_state(ArrivalState(self.ctx, self))

    def _handle_arrival_gate(self) -> None:
        if self.truck.speed_mph <= DOCKING_MAX_MPH:
            self._open_facility_arrival()
            return
        if self._arrival_stop_said:
            return
        self._arrival_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/warning")
        if self.truck.speed_mph <= DELIVERY_PARK_MPH:
            instruction = "Hold the brake to a full stop before the facility menu opens."
            self._set_status("Destination gate reached: full stop required for docking.")
        else:
            instruction = (f"Slow below {DELIVERY_PARK_MPH:.0f} miles per hour, "
                           "then hold the brake to a full stop.")
            self._set_status("Destination reached: slow down and park to deliver.")
        self.ctx.say_event(
            f"Destination facility ahead: {self._destination_facility_text()}. "
            f"{instruction} Docking completes the delivery.",
            interrupt=True)

    def _open_facility_arrival(self) -> None:
        if self._arrival_menu_open:
            return
        self._arrival_menu_open = True
        self._cancel_cruise()
        self.truck.throttle = 0.0
        self._set_status("Parked at destination. Dock and deliver from the facility menu.")
        self.ctx.replace_state(FacilityArrivalState(self.ctx, self))

    def _destination_facility_text(self) -> str:
        if self.job.destination_location:
            return (f"{facility_label(self.job.destination_type)} "
                    f"{self.job.destination_location} in {self.job.destination}")
        return self.job.destination

    def _set_status(self, text: str) -> None:
        self._status_text = text

    def lines(self) -> list[str]:
        t = self.truck
        limit, reason = self.trip.speed_limit_at(self.trip.position_mi)
        gear = "N" if t.transmission.in_neutral else str(t.transmission.gear)
        return [
            f"Driving loaded to {self.job.destination}",
            "",
            f"Speed: {t.speed_mph:.0f} mph (limit {limit:.0f}{', ' + reason if reason else ''})",
            f"Gear: {gear}   RPM: {t.rpm:.0f}   {'ENGINE ON' if t.engine_on else 'engine off'}"
            + (f"   CRUISE {self._cruise_mph:.0f}" if self._cruise_mph is not None else ""),
            f"Fuel: {t.fuel_fraction * 100:.0f}%   Damage: {t.damage_pct:.0f}%",
            f"Remaining: {self.trip.remaining_miles:.0f} of {self.trip.total_miles:.0f} miles",
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
    """Spoken rest stop menu: refuel, take a break, or sleep the night."""

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
                     f"It is {clock_text(self.driving.trip.current_hour)}. "
                     f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(self._fuel_label, self._refuel,
                     help="Fill the tank at this region's diesel price, "
                          "plus a 35 dollar service fee. If cash is short, buy "
                          "as many gallons as you can afford."),
            MenuItem("Take a 30-minute break", self._take_break,
                     help="Satisfies the 30-minute break rule and eases fatigue. "
                          "The clock and your deadline advance half an hour."),
            MenuItem("Sleep 10 hours", self._sleep,
                     help="A full reset: fresh hours of service and zero fatigue. "
                          "The clock and your deadline advance 10 hours."),
            MenuItem("Back to the road", self.go_back),
        ]

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
        self.ctx.audio.play("vehicle/fuel_pump")
        self.ctx.say(f"Refueled {need:.0f} gallons for {cost:,.0f} dollars. "
                     f"You have {p.money:,.0f} dollars.")
        self.refresh()

    def _take_break(self) -> None:
        d = self.driving
        p = self.ctx.profile
        _advance_rest_clock(d, 30.0)
        d.hos.take_break(30.0)
        p.fatigue = hos.rest_break(p.fatigue)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"You took a 30-minute break. "
                     f"It is {clock_text(d.trip.current_hour)}. "
                     f"Your break requirement is reset and you feel a little "
                     f"fresher. {_deadline_text(d)}")

    def _sleep(self) -> None:
        d = self.driving
        p = self.ctx.profile
        _advance_rest_clock(d, hos.SLEEP_MIN)
        d.hos.sleep()
        p.fatigue = hos.rest_sleep(p.fatigue)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"You slept 10 hours and woke rested. "
                     f"It is {clock_text(d.trip.current_hour)}. "
                     f"Hours of service reset. {_deadline_text(d)}")

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
        return [
            MenuItem("Resume driving", self._resume,
                     help="Return to the active delivery."),
            MenuItem("Trip status", self._status,
                     help="Hear cargo, destination, route progress, and time used."),
            MenuItem(self._mechanic_label, self._mechanic,
                     help="A mobile mechanic patches the truck up enough to "
                          "drive on. Costs much more than a garage repair, "
                          "takes an hour and a half, and the bill is due even "
                          "if it puts you in debt."),
            MenuItem("Settings", self._settings,
                     help="Change units, transmission, volumes, weather, "
                          "voices, update channel, and trip pacing."),
            MenuItem("Abandon job", self._abandon,
                     help="Give up this delivery. Costs five hundred dollars and "
                          "reputation, and returns you to the origin city."),
            MenuItem("Save and quit to main menu", self._quit_to_menu,
                     help="Your money, truck, and trip progress are saved. "
                          "The delivery resumes from here when you continue."),
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
        self.ctx.say("Saved. Your delivery will resume where you left off.",
                     interrupt=True)
        self.ctx.reset_to(MainMenuState(self.ctx))


class FacilityArrivalState(MenuState):
    title = "Destination facility"
    intro_help = ("Use up and down arrows to navigate, Enter to select. "
                  "Dock and deliver completes the delivery.")

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
        self._settle()

    def _settle(self) -> None:
        d = self.driving
        p = self.ctx.profile
        job = d.job
        hours = d.trip.game_minutes / 60.0
        trip_damage = max(0.0, d.truck.damage_pct - d.start_damage)
        pay = job.payout(hours, trip_damage)
        early_bonus = max(0.0, pay - job.payout(job.deadline_game_h, trip_damage))
        if d.speeding_strikes:
            fine = min(400.0, 80.0 * d.speeding_strikes)
            pay = max(0.0, pay - fine)
            self.summary_parts.append(f"Speeding fines cost you {fine:,.0f} dollars.")
        on_time = hours <= job.deadline_game_h
        p.money += pay
        p.current_city = job.destination
        p.truck_fuel_gal = d.truck.fuel_gal
        p.truck_damage_pct = d.truck.damage_pct
        announcements = p.career.record_delivery(job.distance_mi, pay, on_time, trip_damage)
        p.game_hours += hours
        p.market.advance_to(p.market_day())
        p.active_trip = None
        self.ctx.save_profile()

        self.summary_parts.insert(0, (
            f"Delivered {job.weight_tons:.0f} tons of {job.cargo.label} to "
            f"{job.destination} in {hours:.1f} hours, "
            f"{'on time' if on_time else 'late'}. "
            f"It is {clock_text(p.game_hours)}. "
            f"You earned {pay:,.0f} dollars and now have {p.money:,.0f}."))
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
            MenuItem("Continue to " + self.driving.job.destination, self._continue),
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
