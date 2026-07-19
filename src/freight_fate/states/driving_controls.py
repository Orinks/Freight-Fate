# ruff: noqa: F403,F405
from __future__ import annotations

from .driving_core import *
from .driving_menu_states import DrivingStatusState, PauseMenuState


class DrivingControlsMixin:
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP and event.key == pygame.K_h:
            self.ctx.audio.horn_stop()
            return
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        tr = self.truck.transmission
        if key in (pygame.K_LCTRL, pygame.K_RCTRL):
            self.ctx.stop_event_speech()
            self._set_status("Event voice stopped.")
        elif key == pygame.K_ESCAPE:
            self.ctx.audio.horn_stop()
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
        elif key == pygame.K_w and not tr.automatic:
            if tr.in_reverse or tr.in_neutral:
                self._manual_shift(1)
            elif tr.gear < 10:
                self._manual_shift(tr.gear + 1)
        elif key == pygame.K_q and not tr.automatic and not tr.in_neutral and tr.gear > 1:
            self._manual_shift(tr.gear - 1)
        elif key == pygame.K_j:
            self._toggle_engine_brake()
        elif key == pygame.K_p:
            self._toggle_parking_brake()
        elif key == pygame.K_h:
            self.ctx.audio.horn_start()
        elif key == pygame.K_t:
            self._try_rest_stop()
        elif key == pygame.K_x:
            if self._pull_over is not None:
                self._signal_pull_over()
            else:
                self._take_exit()
        elif key == pygame.K_k:
            self._toggle_cruise()
        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS) or event.unicode == "+":
            self._adjust_cruise(CRUISE_STEP_MPH)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS) or event.unicode == "-":
            self._adjust_cruise(-CRUISE_STEP_MPH)
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
        elif key == pygame.K_s:
            self._speak_speed_limit()
        elif key == pygame.K_a:
            self._speak_last_announcement()
        elif key == pygame.K_u:
            self._speak_upcoming()
        elif key == pygame.K_F1:
            self._speak_driving_help()

    def _objective_help(self) -> str:
        return (
            f"Your current objective is pickup: drive to {self._pickup_facility_text()}, "
            "stop at the gate, then check in and load. "
            if self.phase == DRIVE_PHASE_PICKUP
            else "Pickup and loading are complete. At your destination, stop, "
            "then dock and deliver. "
        )

    def _speak_driving_help(self) -> None:
        """F1 help: keyboard or controller layout, following the device in use."""
        if self.ctx.controller.device == "controller":
            self._speak_controller_help()
        else:
            self._speak_keyboard_help()

    def _speak_keyboard_help(self) -> None:
        objective_help = self._objective_help()
        if self.ctx.settings.automatic_direction_changes == "deliberate":
            automatic_help = (
                "In automatic with deliberate direction changes, brake to a stop, "
                "then release the Down arrow and press it again to shift into reverse "
                "and back slowly. While reversing, hold the Up arrow to brake to a "
                "stop, then release it and press again to shift back into forward. "
            )
        else:
            automatic_help = (
                "In automatic with simple direction changes, keep holding the Down "
                "arrow after you stop to shift into reverse and back slowly. While "
                "reversing, keep holding the Up arrow after you stop to shift back "
                "into forward. "
            )
        self.ctx.say(
            "Hold Up arrow to accelerate, Down arrow to brake. "
            + automatic_help
            + "Hold B for the emergency brake, the hardest possible stop. "
            "K starts automatic speed control. Adaptive cruise handles open "
            "roads and the speed keeper handles low-speed zones, switching "
            "automatically between them. Bad weather increases the following "
            "gap, sharp posted-limit drops make it slow early, and braking "
            "cancels the whole session. At the planned pickup, it pauses while "
            "you check in and load, then resumes once you depart and get rolling. "
            "Plus and minus, including the keypad "
            "keys, change the remembered open-road target by five; it will not "
            "hold above the posted limit. "
            "X takes the next announced exit, called out by its number "
            "when known: slow to 45 for the ramp, then brake to a stop for "
            "the rest stop menu. X also signals a pull-over if a trooper "
            "lights you up for speeding: signal, then brake to a stop. "
            "C also speaks the date and season. "
            "E starts the engine, and stops it only below 5 miles per hour. "
            "Air pressure must build before the truck can move. "
            "Press P to release or set the parking brake; if pressure is "
            "below 100 psi, wait with the engine running. "
            f"{objective_help}"
            "Space speed, active speed-control mode, and target. "
            "S posted speed limit. Tab status menu. F fuel. "
            "C clock, deadline, and hours of service. "
            "R route. Shift R next listed highway exit. V weather. L lane position. "
            "A repeats the last announcement. U reads what is coming up: "
            "imposed limits, stops, and exits ahead. "
            "Left or Right Control stops the driving event voice. "
            "Left and Right arrows steer when lane drift is enabled. "
            "T route POI menu when already stopped "
            "at one: available actions may include fuel, break, sleep, "
            "inspect, roadside assistance, or save when source-backed. H horn. "
            "J engine brake. Escape pause menu. "
            + (
                ""
                if self.truck.transmission.automatic
                else "Hold Left Shift for clutch, then W to shift up or Q to shift down, "
                "Backspace for reverse, N for neutral."
            )
        )

    def _speak_controller_help(self) -> None:
        """Controller layout help, spoken from the Back button or F1 on a pad."""
        manual = not self.truck.transmission.automatic
        if manual:
            gears = (
                "The A button shifts up a gear and the X button shifts down, while "
                "you hold the left bumper for the clutch. "
            )
        elif self.ctx.settings.automatic_direction_changes == "deliberate":
            gears = (
                "In automatic with deliberate direction changes, brake to a stop, "
                "then let the left trigger return to neutral and press it again to "
                "shift into reverse and back slowly. While reversing, hold the right "
                "trigger to brake to a stop, then let it return to neutral and press "
                "again to shift back into forward. "
            )
        else:
            gears = (
                "In automatic with simple direction changes, keep holding the left "
                "trigger after you stop to shift into reverse and back slowly. While "
                "reversing, keep holding the right trigger after you stop to shift "
                "back into forward. "
            )
        self.ctx.say(
            "Right trigger is the gas, left trigger the brake; press the left "
            "trigger fully for the hardest stop. The left stick steers when lane "
            "drift is on. "
            f"{gears}"
            "The Y button starts automatic speed control, switching between "
            "adaptive cruise and the low-speed keeper as needed. Hold the right "
            "bumper and press D-pad left or right to lower or raise the open-road "
            "cruise target by five. It pauses through the planned pickup and "
            "resumes once the loaded truck is rolling. "
            "D-pad down takes the next announced exit, or signals a pull-over. "
            "D-pad up reads your route, D-pad left the weather, D-pad right the "
            "clock. The B button speaks your speed. Click the left stick to honk, "
            "the right stick to toggle the engine brake. "
            "Hold the right bumper for the second layer: plus A starts or stops "
            "the engine, plus B reads fuel, plus Y sets or releases the parking "
            "brake, plus D-pad up reads the next listed exit, plus D-pad down "
            "opens rest-stop actions, and plus Start opens the status menu. "
            "Start pauses and unpauses. The Back button repeats this help. "
            f"{self._objective_help()}"
        )

    def _toggle_engine_brake(self) -> None:
        if self.truck.throttle > 0.05 and not self.truck.engine_brake:
            self.ctx.say("Release the accelerator before turning the engine brake on.")
            return
        self.truck.engine_brake = not self.truck.engine_brake
        self.ctx.say("Engine brake on." if self.truck.engine_brake else "Engine brake off.")

    def _shift_relative(self, delta: int) -> None:
        """Controller next/previous gear: step one gear from the current one."""
        tr = self.truck.transmission
        if tr.automatic:
            return
        target = max(REVERSE, min(tr.num_gears, tr.gear + delta))
        if target != tr.gear:
            self._manual_shift(target)

    def handle_controller(self, event: pygame.event.Event, manager) -> None:
        button = event.button
        if event.type == pygame.CONTROLLERBUTTONUP:
            if button == pygame.CONTROLLER_BUTTON_LEFTSTICK:
                self.ctx.audio.horn_stop()  # release L3 to stop the horn
            return
        if event.type != pygame.CONTROLLERBUTTONDOWN:
            return
        if manager.modifier:
            self._handle_controller_modified(button)
            return
        if button == pygame.CONTROLLER_BUTTON_A:
            self._shift_relative(1)
        elif button == pygame.CONTROLLER_BUTTON_X:
            self._shift_relative(-1)
        elif button == pygame.CONTROLLER_BUTTON_B:
            self._speak_speed()
        elif button == pygame.CONTROLLER_BUTTON_Y:
            self._toggle_cruise()
        elif button == pygame.CONTROLLER_BUTTON_START:
            self.ctx.audio.horn_stop()
            self.ctx.push_state(PauseMenuState(self.ctx, self))
        elif button == pygame.CONTROLLER_BUTTON_LEFTSTICK:
            self.ctx.audio.horn_start()
        elif button == pygame.CONTROLLER_BUTTON_RIGHTSTICK:
            self._toggle_engine_brake()
        elif button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            self.ctx.say(self.trip.progress_summary(self.ctx.settings.imperial_units))
        elif button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            if self._pull_over is not None:
                self._signal_pull_over()
            else:
                self._take_exit()
        elif button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            self._speak_weather()
        elif button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            self._speak_clock()
        elif button == pygame.CONTROLLER_BUTTON_BACK:
            self._speak_controller_help()

    def _handle_controller_modified(self, button: int) -> None:
        """Secondary bindings while the right bumper (modifier) is held."""
        if button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            self.ctx.say(self.trip.next_exit_context())
        elif button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            self._try_rest_stop()
        elif button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            self._adjust_cruise(-CRUISE_STEP_MPH)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            self._adjust_cruise(CRUISE_STEP_MPH)
        elif button == pygame.CONTROLLER_BUTTON_A:
            self._toggle_engine()
        elif button == pygame.CONTROLLER_BUTTON_B:
            self._speak_fuel()
        elif button == pygame.CONTROLLER_BUTTON_Y:
            self._toggle_parking_brake()
        elif button == pygame.CONTROLLER_BUTTON_START:
            self.ctx.push_state(DrivingStatusState(self.ctx, self))

    def on_controller_disconnect(self) -> None:
        # Pause so an unplugged pad mid-drive does not leave the truck rolling.
        self.ctx.audio.horn_stop()
        self.ctx.push_state(PauseMenuState(self.ctx, self))

    def _toggle_engine(self) -> None:
        if self.ctx.audio.engine_starting:
            # Ignition still in progress; ignore mashed presses so the crank,
            # shutdown, and loop sounds cannot stack on top of each other.
            return
        t = self.truck
        if t.engine_on:
            if t.speed_mph > ENGINE_SHUTDOWN_SAFE_MPH:
                self.ctx.audio.play("ui/error")
                text = (
                    f"Unsafe to shut the engine off at "
                    f"{self.ctx.settings.speed_text(t.speed_mph)}. "
                    "Brake below 5 miles per hour first."
                )
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
                if t.air_low_warning:
                    # Starting from a parked low-air state should always give an
                    # immediate audible warning, independent of frame timing.
                    self.ctx.audio.play("vehicle/low_air_buzzer", volume=0.7)
                    self.ctx.controller.rumble.alert()
                    self._low_air_said = True
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
        if self._terse_speech():
            return f"Air pressure {t.air_pressure_psi:.0f} psi."
        brake_hint = self.ctx.control_hint("parking_brake")
        if t.parking_brake:
            if t.air_ready:
                return f"Air pressure ready. Press {brake_hint} to release the parking brake."
            return (
                f"Air pressure {t.air_pressure_psi:.0f} psi. "
                f"Wait for 100 psi, then press {brake_hint} to release the parking brake."
            )
        return f"Air pressure ready. Hold {self.ctx.control_hint('accelerate')} to drive."

    def _toggle_parking_brake(self) -> None:
        t = self.truck
        if t.parking_brake:
            # Trying to leave, even if low air keeps the brake locked: stop
            # fast-forwarding so build-up time is not billed at waiting pace.
            self.trip.waiting = False
            if t.release_parking_brake():
                self.ctx.audio.play("vehicle/brake_release", volume=0.65)
                self._set_status("Parking brake released.")
                self.ctx.say(f"Parking brake released. Air pressure {t.air_pressure_psi:.0f} psi.")
                if self.tutorial:
                    self.tutorial.on_parking_brake_released()
            else:
                self.ctx.audio.play("ui/error")
                self._set_status("Parking brake locked: build air pressure first.")
                if self._terse_speech():
                    self.ctx.say(f"Parking brake set. Air pressure {t.air_pressure_psi:.0f} psi.")
                else:
                    self.ctx.say(
                        f"Parking brake stays set. Air pressure {t.air_pressure_psi:.0f} psi; "
                        "wait for 100 psi with the engine running."
                    )
            return
        t.set_parking_brake()
        t.throttle = 0.0
        self._cancel_cruise()
        # The player's own brake press means deliberate waiting; auto-sets at
        # trip start, rest stops, and arrivals never arm the fast-forward.
        self.trip.waiting = True
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
            self.ctx.say(
                f"Grinding gears! Hold {self.ctx.control_hint('clutch')} to press the clutch first."
            )
        else:
            self.ctx.say(result.message)

    # -- info keys ---------------------------------------------------------------------

    def _speak_speed(self) -> None:
        t = self.truck
        gear = self._gear_text()
        keeper_target = (
            f", open-road target {self.ctx.settings.speed_text(self._speed_control_target_mph)}"
            if self._speed_control_target_mph is not None
            else ", open-road target will use the posted limit"
        )
        cruise = (
            ", automatic speed control, adaptive cruise set at "
            f"{self.ctx.settings.speed_text(self._cruise_mph)}"
            if self._cruise_mph is not None
            else (
                ", automatic speed control, speed keeper holding "
                f"{self.ctx.settings.speed_text(self._keeper_mph)}{keeper_target}"
                if self._keeper_mph is not None
                else (
                    f", automatic speed control paused{keeper_target}"
                    if self._speed_control_armed
                    else ""
                )
            )
        )
        self.ctx.say(
            f"{self.ctx.settings.speed_text(t.speed_mph)}, {gear}, "
            f"{t.rpm:.0f} RPM{cruise}, {self._air_status_text()}."
        )

    def _speak_speed_limit(self) -> None:
        """S: the posted limit here, the zone if any, and how far over you are."""
        limit, reason = self.trip.speed_limit_at(self.trip.position_mi)
        zone = f", in a {reason} zone" if reason else ""
        over = self.truck.speed_mph - limit
        comparison = (
            f" You are about {self.ctx.settings.speed_text(over)} over." if over >= 1 else ""
        )
        self.ctx.say(f"Speed limit {self.ctx.settings.speed_text(limit)}{zone}.{comparison}")

    def _speak_last_announcement(self) -> None:
        """A: replay the last route announcement, for one you missed."""
        if self._last_event_message:
            self.ctx.say(self._last_event_message)
        else:
            self.ctx.say("No recent announcement to repeat.")

    def _speak_upcoming(self, within_mi: float = 15.0) -> None:
        """U: what is coming up -- imposed limits, stops, and exits ahead."""
        s = self.ctx.settings
        pos = self.trip.position_mi
        parts: list[str] = []
        zone = self.trip.next_zone_within(within_mi)
        if zone is not None:
            parts.append(
                f"{zone.reason} in {s.distance_text(zone.start_mi - pos)}, "
                f"speed limit {s.speed_text(zone.limit_mph)}"
            )
        stop = self.trip.upcoming_stop(within_mi)
        if stop is not None:
            parts.append(f"{stop.spoken_name} in {s.distance_text(stop.at_mi - pos)}")
        cue = self.trip.next_exit_cue()
        if cue is not None and 0 < cue.at_mi - pos <= within_mi:
            parts.append(f"in {s.distance_text(cue.at_mi - pos)}, {cue.text}")
        if not parts:
            self.ctx.say(f"Nothing notable in the next {s.distance_text(within_mi)}.")
            return
        self.ctx.say("Coming up: " + ". ".join(parts) + ".")

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
            f"Calendar: {self._calendar_phrase() or 'unknown'}",
            f"Clock: {clock_text(self.trip.local_hour)} {self.trip.current_timezone.name} "
            f"({time_of_day(self.trip.local_hour)})",
        ]
        if self._cruise_mph is not None:
            lines.insert(
                1,
                f"Cruise: adaptive cruise set at {self.ctx.settings.speed_text(self._cruise_mph)}",
            )
            context = self.trip.traffic_context()
            if context is not None:
                lines.insert(
                    2,
                    "Traffic: lead vehicle "
                    f"{self.ctx.settings.distance_text(context.gap_mi)} ahead, "
                    f"{self.ctx.settings.speed_text(context.lead.speed_mph)}",
                )
        elif self._keeper_mph is not None:
            lines.insert(
                1,
                f"Speed control: speed keeper holding "
                f"{self.ctx.settings.speed_text(self._keeper_mph)}",
            )
            target = (
                self.ctx.settings.speed_text(self._speed_control_target_mph)
                if self._speed_control_target_mph is not None
                else "posted limit when the open road begins"
            )
            lines.insert(2, f"Open-road target: {target}")
        elif self._speed_control_armed:
            lines.insert(1, "Speed control: paused; resumes when the truck is rolling")
            target = (
                self.ctx.settings.speed_text(self._speed_control_target_mph)
                if self._speed_control_target_mph is not None
                else "posted limit when the open road begins"
            )
            lines.insert(2, f"Open-road target: {target}")
        if t.damage_pct - self.start_damage > 1:
            lines.append(f"Damage: new damage {t.damage_pct - self.start_damage:.0f} percent")
        if self.ctx.settings.speech_verbosity >= 1:
            fatigue = self.ctx.profile.fatigue
            if fatigue >= hos.FATIGUE_DROWSY:
                lines.append(f"Fatigue: {fatigue:.0f} percent")
            lines.append(f"HOS: {self.hos.summary(self.ctx.settings.hos_mode).rstrip('.')}")
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
            "brakes hot"
            if t.brake_temp_c >= t.specs.brake_fade_temp_c
            else "brakes warm"
            if t.brake_temp_c >= 180.0
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
        self.ctx.say(
            f"Fuel {t.fuel_fraction * 100:.0f} percent, {t.fuel_gal:.0f} gallons. "
            f"Estimated range {self.ctx.settings.distance_text(range_mi)}."
        )

    def _calendar_phrase(self) -> str:
        """Calendar date and season for the spoken readouts; '' when unknown."""
        date = self.weather.date_text
        if date is None:
            return ""
        season = self.weather.season
        return f"{date}, {season}" if season else date

    def _clock_phrase(self) -> str:
        """'It is 5:33 AM, March 21, spring.' -- the time plus the calendar."""
        cal = self._calendar_phrase()
        base = f"It is {clock_text(self.trip.local_hour)} {self.trip.current_timezone.name}"
        return f"{base}, {cal}." if cal else f"{base}."

    def _speak_clock(self) -> None:
        hours_used = self.trip.game_minutes / 60.0
        now = self._clock_phrase()
        if self.phase == DRIVE_PHASE_PICKUP:
            self.ctx.say(
                f"{now} Pickup drive to {self._pickup_facility_text()}. "
                f"{self.ctx.settings.distance_text(self.trip.remaining_miles)} remain. "
                f"{hours_used:.1f} hours used before loading. "
                f"{self.hos.summary(self.ctx.settings.hos_mode)} "
                f"{self._hos_route_context()}"
            )
            return
        remaining = self.job.deadline_game_h - hours_used
        eta = self.trip.eta_game_hours()
        basis = (
            "at your current speed"
            if self.truck.speed_mph >= self.trip.ETA_MIN_MPH
            else "at a typical highway pace"
        )
        hos_part = self.hos.summary(self.ctx.settings.hos_mode)
        hos_route = self._hos_route_context()
        if hos_route:
            hos_part = f"{hos_part} {hos_route}"
        if remaining > 0:
            verdict = (
                "You are on schedule."
                if eta < remaining
                else "You are running behind. Keep your speed up."
            )
            appointment = _deadline_appointment(self)
            self.ctx.say(
                f"{now} {hours_used:.1f} hours on the road. "
                f"{remaining:.1f} hours until the deadline; "
                f"delivery is due by {appointment}. "
                f"Estimated time to arrival {eta:.1f} hours {basis}. "
                f"{verdict} {hos_part}"
            )
        else:
            self.ctx.say(
                f"{now} You are {-remaining:.1f} hours past the deadline. "
                f"The pay is shrinking, but finish the delivery. {hos_part}"
            )

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
            return (
                f"No route stop is currently visible before the next {action} "
                f"limit, due in {remaining_min / 60.0:.1f} hours. If you "
                "cannot reach a stop, come to a stop and you can sleep on the "
                "shoulder: poor rest, and a possible parking ticket."
            )
        ahead = max(0.0, next_stop.at_mi - self.trip.position_mi)
        verdict = "before" if ahead <= legal_miles else "after"
        stop_text = (
            f"Next legal stop: {next_stop.spoken_name} in {self.ctx.settings.distance_text(ahead)}"
        )
        if next_stop.parking_text:
            stop_text += f", {next_stop.parking_text}"
        return f"{stop_text}, {verdict} the next {action} limit."

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
        """Why shoulder sleep is offered now, or None when it is not.

        Available whenever the truck is stopped with no route POI to pull into --
        a driver can always choose to pull over and rest, urgently or not. The
        wording escalates with urgency (severe fatigue, or an HOS limit closing
        in with no reachable stop) but the option itself is always there."""
        if self.truck.speed_mph > 3:
            return None
        if self.trip.nearest_stop_within() is not None:
            return None  # a POI is right here; use its rest menu instead
        if self.ctx.profile.fatigue >= hos.FATIGUE_SEVERE:
            return "Fatigue is severe, and no route stop is nearby."
        mode = self.ctx.settings.hos_mode
        if mode not in hos.HOS_NON_ENFORCED_MODES:
            if self.hos.in_violation(mode):
                return "You are past your hours-of-service limit, and there is no route POI here."
            next_limit = self.hos.next_limit(mode)
            if next_limit is not None:
                kind, remaining_min, _due = next_limit
                action = "break" if kind == "break" else "sleep"
                legal_miles = self._legal_miles_for_hos(remaining_min)
                if (
                    remaining_min <= hos.SHOULDER_SLEEP_LIMIT_BUFFER_MIN
                    and self._upcoming_stop_with_action(action, max(legal_miles + 5.0, 5.0)) is None
                ):
                    return (
                        f"Your next {action} limit is due in "
                        f"{remaining_min / 60.0:.1f} hours, and no suitable "
                        "route stop is visible before it."
                    )
        return "No route stop is nearby. You can pull over and rest on the shoulder."

    def _speak_weather(self) -> None:
        source = "Live conditions" if self.weather.live else "Currently"
        safe_speed = self.ctx.settings.speed_text(self.weather.effects.safe_speed_mph)
        parts = [
            f"It is {time_of_day(self.trip.local_hour)}.",
            f"{source} {self.weather.describe(self.ctx.settings.imperial_units)}.",
            f"Safe speed about {safe_speed}.",
        ]
        if not self.weather.live:
            ahead = ", then ".join(k.value for k in self.weather.forecast(2))
            parts.append(f"Ahead: {ahead}.")
        self.ctx.say(" ".join(parts))

    # -- per-frame update -----------------------------------------------------------------
