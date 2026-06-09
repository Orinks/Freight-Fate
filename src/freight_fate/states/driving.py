"""The driving state: live truck control with a fully audio HUD.

Continuous controls (throttle, brake, clutch) are sampled from held keys
each frame. Everything the player needs to know is available on demand from
information keys, and important changes announce themselves.
"""

from __future__ import annotations

import pygame

from ..data.world import Route
from ..models.jobs import Job
from ..sim.trip import Trip, TripEventKind
from ..sim.vehicle import TruckState
from ..sim.weather import WeatherSystem
from .base import MenuItem, MenuState, State

GEAR_KEYS = {
    pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3, pygame.K_4: 4, pygame.K_5: 5,
    pygame.K_6: 6, pygame.K_7: 7, pygame.K_8: 8, pygame.K_9: 9, pygame.K_0: 10,
}

HAZARD_SAFE_MPH = 25.0


class DrivingState(State):
    def __init__(self, ctx, job: Job, route: Route) -> None:
        super().__init__(ctx)
        self.job = job
        self.route = route
        profile = ctx.profile
        self.truck = TruckState()
        self.truck.transmission.automatic = ctx.settings.automatic_transmission
        self.truck.fuel_gal = profile.truck_fuel_gal
        self.truck.damage_pct = profile.truck_damage_pct
        self.start_damage = profile.truck_damage_pct
        region = ctx.world.cities[job.origin].region
        self.weather = WeatherSystem(region, provider=ctx.real_weather_provider())
        self.trip = Trip(route, self.truck, self.weather,
                         time_scale=ctx.settings.time_scale)
        self.tutorial = Tutorial(ctx) if not profile.tutorial_done else None

        self._hazard_deadline: float | None = None
        self._speed_announce_timer = 0.0
        self._last_announced_mph = 0.0
        self._speeding_timer = 0.0
        self.speeding_strikes = 0
        self._rescue_offered = False
        self._signal_timer = 0.0
        self._status_text = "Press E to start the engine."

    # -- lifecycle ---------------------------------------------------------------

    def enter(self) -> None:
        self.ctx.audio.stop_music(800)
        self.ctx.audio.play_music("open_road", fade_ms=2500)
        self.ctx.audio.set_weather(self.weather.effects.sound)
        self.ctx.audio.set_wind(self.weather.effects.wind)
        mode = "automatic" if self.truck.transmission.automatic else "manual"
        self.ctx.say(f"You are at the wheel. Transmission is {mode}. "
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
                "Hold Up arrow to accelerate, Down arrow to brake. E engine. "
                "Space speed. Tab full status. F fuel. C clock and deadline. "
                "R route. V weather. T rest stop when stopped at one. H horn. "
                "J engine brake. Escape pause menu. "
                + ("" if self.truck.transmission.automatic else
                   "Hold Left Shift for clutch, then 1 through 0 for gears, N for neutral."))

    def _toggle_engine(self) -> None:
        t = self.truck
        if t.engine_on:
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
                self.ctx.say("The engine will not start. The fuel tank is empty.")

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
        ]
        if t.damage_pct - self.start_damage > 1:
            parts.append(f"new damage {t.damage_pct - self.start_damage:.0f} percent")
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
        if remaining > 0:
            verdict = ("You are on schedule." if eta < remaining
                       else "You are running behind. Keep your speed up.")
            self.ctx.say(f"{hours_used:.1f} hours on the road. "
                         f"{remaining:.1f} hours until the deadline. "
                         f"Estimated time to arrival {eta:.1f} hours. {verdict}")
        else:
            self.ctx.say(f"You are {-remaining:.1f} hours past the deadline. "
                         "The pay is shrinking, but finish the delivery.")

    def _speak_weather(self) -> None:
        source = "Live conditions" if self.weather.live else "Currently"
        parts = [f"{source} {self.weather.describe()}.",
                 f"Safe speed about {self.weather.effects.safe_speed_mph:.0f}."]
        if not self.weather.live:
            ahead = ", then ".join(k.value for k in self.weather.forecast(2))
            parts.append(f"Ahead: {ahead}.")
        self.ctx.say(" ".join(parts))

    # -- per-frame update -----------------------------------------------------------------

    def update(self, dt: float) -> None:
        t = self.truck
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
        t.transmission.clutch = 1.0 if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] else 0.0

        if t.transmission.automatic and t.engine_on:
            new_gear = t.auto_shift()
            if new_gear is not None:
                self.ctx.audio.play("vehicle/gear_shift", volume=0.5)

        was_on = t.engine_on
        t.update(dt)
        if was_on and not t.engine_on:
            self.ctx.audio.engine_stop()
            if t.stalled:
                self.ctx.say("The engine stalled. Press E to restart, and use a "
                             "lower gear at low speed.")
            elif t.fuel_gal <= 0:
                self._handle_out_of_fuel()

        for event in self.trip.update(dt):
            self._handle_trip_event(event)

        self._update_audio()
        self._update_announcements(dt)
        self._update_hazard(dt)
        self._update_speeding(dt)
        if self.tutorial:
            self.tutorial.update(dt, t)
        if self.trip.finished:
            self._arrive()

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
        if self.weather.should_thunder():
            audio.play("weather/thunder", volume=0.9)

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
                self.ctx.say(self.ctx.settings.speed_text(mph), interrupt=False)

    def _update_hazard(self, dt: float) -> None:
        if self._hazard_deadline is None:
            return
        if self.truck.speed_mph <= HAZARD_SAFE_MPH:
            self._hazard_deadline = None
            self.ctx.say("Hazard avoided. Well done.", interrupt=False)
            return
        self._hazard_deadline -= dt
        if self._hazard_deadline <= 0:
            self._hazard_deadline = None
            self.ctx.audio.play("vehicle/collision")
            severity = min(1.0, self.truck.speed_mph / 70.0)
            self.truck.apply_collision(severity)
            self.ctx.say(f"Collision! The truck took damage. "
                         f"Total damage {self.truck.damage_pct:.0f} percent.")

    def _update_speeding(self, dt: float) -> None:
        limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
        if self.truck.speed_mph > limit + 9:
            self._speeding_timer += dt
            if self._speeding_timer > 6.0:
                self._speeding_timer = 0.0
                self.speeding_strikes += 1
                self.ctx.audio.play("ui/warning")
                self.ctx.say(f"You are speeding. The limit is {limit:.0f}.",
                             interrupt=False)
        else:
            self._speeding_timer = 0.0

    def _handle_trip_event(self, event) -> None:
        kind = event.kind
        if kind == TripEventKind.HAZARD:
            self.ctx.audio.play("ui/warning")
            self._hazard_deadline = event.data.get("deadline_s", 4.0)
            self.ctx.say(event.message, interrupt=True)
        elif kind == TripEventKind.WEATHER_CHANGE:
            self.ctx.say(event.message, interrupt=False)
        elif kind == TripEventKind.ARRIVED:
            pass  # handled by _arrive()
        else:
            self.ctx.say(event.message, interrupt=False)
        if kind == TripEventKind.ZONE_ENTER:
            self.ctx.audio.play("ui/notify", volume=0.7)

    def _try_rest_stop(self) -> None:
        stop = self.trip.nearest_stop_within()
        if stop is None:
            self.ctx.say("There is no rest stop here. Stops are announced as you "
                         "approach them.")
            return
        if self.truck.speed_mph > 3:
            self.ctx.say("Come to a complete stop first.")
            return
        p = self.ctx.profile
        region = self.trip.current_region
        need = self.truck.specs.fuel_tank_gal - self.truck.fuel_gal
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
        self.truck.refuel(need)
        self.ctx.audio.play("vehicle/fuel_pump")
        self.ctx.say(f"Rested and refueled {need:.0f} gallons at {stop.name} "
                     f"for {cost:,.0f} dollars. You have {p.money:,.0f} dollars.")

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
        self.ctx.say(f"You ran out of fuel. Roadside rescue brought thirty gallons "
                     f"for {fee:,.0f} dollars. Press E to restart the engine, and "
                     "plan your fuel stops.")

    def _arrive(self) -> None:
        self.ctx.replace_state(ArrivalState(self.ctx, self))

    def _set_status(self, text: str) -> None:
        self._status_text = text

    def lines(self) -> list[str]:
        t = self.truck
        limit, reason = self.trip.speed_limit_at(self.trip.position_mi)
        gear = "N" if t.transmission.in_neutral else str(t.transmission.gear)
        return [
            f"Driving to {self.job.destination}",
            "",
            f"Speed: {t.speed_mph:.0f} mph (limit {limit:.0f}{', ' + reason if reason else ''})",
            f"Gear: {gear}   RPM: {t.rpm:.0f}   {'ENGINE ON' if t.engine_on else 'engine off'}",
            f"Fuel: {t.fuel_fraction * 100:.0f}%   Damage: {t.damage_pct:.0f}%",
            f"Remaining: {self.trip.remaining_miles:.0f} of {self.trip.total_miles:.0f} miles",
            f"Weather: {self.weather.current.value}",
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
                "warnings, and brake hard when you hear them. Safe travels.",
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
            MenuItem("Resume driving", self._resume),
            MenuItem("Trip status", self._status),
            MenuItem("Settings", self._settings),
            MenuItem("Abandon job", self._abandon,
                     help="Give up this delivery. Costs five hundred dollars and "
                          "reputation, and returns you to the origin city."),
            MenuItem("Save and quit to main menu", self._quit_to_menu,
                     help="The job is abandoned, but your money and progress are saved."),
        ]

    def go_back(self) -> None:
        self._resume()

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
        self.ctx.save_profile()
        self.ctx.say("Saved. The delivery was left behind.", interrupt=True)
        self.ctx.reset_to(MainMenuState(self.ctx))


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
        self.ctx.save_profile()

        self.summary_parts.insert(0, (
            f"Delivered {job.weight_tons:.0f} tons of {job.cargo.label} to "
            f"{job.destination} in {hours:.1f} hours, "
            f"{'on time' if on_time else 'late'}. "
            f"You earned {pay:,.0f} dollars and now have {p.money:,.0f}."))
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
