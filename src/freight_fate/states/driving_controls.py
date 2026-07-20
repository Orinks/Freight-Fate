# ruff: noqa: F403,F405
from __future__ import annotations

from .driving_core import *
from .driving_menu_states import DrivingStatusState, PauseMenuState

# Wear meters join the status readout once they're worth planning around.
WEAR_STATUS_PCT = 50.0

# An armed exit owns the D safe-speed answer once it is this close: past
# here the ramp speed is the number that matters, not the mainline's.
SAFE_SPEED_EXIT_MI = 2.0
# D looks this far ahead for a bend: about the pacenote call distance, so
# the one number never contradicts the call you just heard.
SAFE_SPEED_CURVE_MI = 0.5


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
            self._note_critical_speech_stopped()
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
        elif (
            key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS)
            or getattr(event, "unicode", "") == "+"
        ):
            self._adjust_cruise(CRUISE_STEP_MPH)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS) or getattr(event, "unicode", "") == "-":
            self._adjust_cruise(-CRUISE_STEP_MPH)
        elif key == pygame.K_LEFT and self.ctx.settings.steering_assist == "off":
            self._tap_lane_change(1)
        elif key == pygame.K_RIGHT and self.ctx.settings.steering_assist == "off":
            self._tap_lane_change(-1)
        elif key == pygame.K_SPACE:
            self._speak_speed()
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.phase == DRIVE_PHASE_CITY_SERVICE:
                self._enter_city_service()
            elif self._arrival_full_stop_said and self.truck.speed_mph <= 0.5:
                self._open_facility_arrival()
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
                self._speak_route_status()
        elif key == pygame.K_v:
            self._speak_weather()
        elif key == pygame.K_l:
            self.ctx.say(self.lane.describe())
        elif key == pygame.K_s:
            self._speak_speed_limit()
        elif key == pygame.K_d:
            self._speak_safe_speed()
        elif key == pygame.K_a:
            self._speak_last_announcement()
        elif key == pygame.K_g:
            self._speak_grade()
        elif key == pygame.K_u:
            self._speak_upcoming()
        elif key == pygame.K_m:
            self._toggle_radio()
        elif key == pygame.K_LEFTBRACKET:
            # Brackets walk the dial; Ctrl+brackets leap a whole category
            # (25 AFN stations in a row buried terrestrial for a linear tune).
            if event.mod & pygame.KMOD_CTRL:
                self._jump_radio_category(-1)
            else:
                self._tune_radio(-1)
        elif key == pygame.K_RIGHTBRACKET:
            if event.mod & pygame.KMOD_CTRL:
                self._jump_radio_category(1)
            else:
                self._tune_radio(1)
        elif key == pygame.K_y:
            self._speak_radio_status()
        elif key == pygame.K_F1:
            self._speak_driving_help()

    def _tap_lane_change(self, direction: int) -> None:
        """Assist-off lane change: a timed drift across the line, +1 moves
        left, -1 moves right. With steering assist on, the held wheel does
        this instead, so the tap handler never runs there."""
        if self._microsleep_deadline is not None:
            return  # the held-key wake-up check owns the arrows right now
        t = self.truck
        lane = self.lane
        if self._ramp_mi is not None:
            self.ctx.say("You are on the exit ramp. No lanes to change.")
            return
        if self._lane_change_target is not None:
            self.ctx.say("Still changing lanes.")
            return
        if not t.engine_on or t.speed_mph < LANE_MIN_MPH:
            self.ctx.say(
                "Lane changes need the engine running and at least "
                f"{self.ctx.settings.speed_text(LANE_MIN_MPH)}."
            )
            return
        target = lane.lane + direction
        if not 0 <= target < lane.lane_count:
            self.ctx.say(f"You are already in the {lane.lane_name} lane.")
            return
        zone = self.trip.active_zone
        if zone is not None and zone.reason == "construction" and zone.closed_lane == target:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"The {lane_label(target, lane.lane_count)} lane is closed here.")
            return
        self._lane_change_target = target
        self._lane_change_timer = LANE_TAP_CHANGE_S
        self._lane_signal_timer = 0.0
        pan = -0.6 if direction > 0 else 0.6
        self.ctx.audio.play("vehicle/turn_signal", volume=0.8, pan=pan)
        self.ctx.say(f"Changing to the {lane_label(target, lane.lane_count)} lane.")

    def _objective_help(self) -> str:
        if self.phase == DRIVE_PHASE_PICKUP:
            return (
                f"Your current objective is pickup: drive to "
                f"{self._pickup_facility_text()}, stop at the gate, then "
                "check in and load. "
            )
        if self.phase == DRIVE_PHASE_CITY_SERVICE:
            return (
                f"Your current objective is {self._city_service_text()}: "
                "drive there, stop, then press Enter to go inside. "
            )
        return "Pickup and loading are complete. At your destination, stop, then dock and deliver. "

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
                "then release the Down arrow and press and hold it again to shift "
                "into reverse and back slowly. While reversing, hold the Up arrow "
                "to brake to a stop, then release it and press and hold again to "
                "shift back into forward. A quick tap just brakes. "
            )
        else:
            automatic_help = (
                "In automatic with simple direction changes, brake to a stop, "
                "release the Down arrow, then press and hold it again to shift into "
                "reverse and back slowly. While reversing, brake with the Up arrow, "
                "and once stopped, release and hold it again to shift back into "
                "forward. Holding a brake through a stop just holds the truck. "
            )
        latch_help = (
            "Tap the accelerator or brake, then press again and hold half a "
            "second, to latch the pedal so it stays applied hands-free: a "
            "click and a spoken confirmation mark the catch. Press the same "
            "key once to take the pedal back; the opposite pedal or any "
            "safety alert releases it instantly. "
            if self.ctx.settings.pedal_latch
            else ""
        )
        self.ctx.say(
            "Hold Up arrow to accelerate, Down arrow to brake. "
            + latch_help
            + automatic_help
            + "Hold B for the emergency brake, the hardest possible stop. "
            "K starts automatic speed control. Adaptive cruise handles open "
            "roads and the speed keeper handles low-speed zones, switching "
            "automatically between them. Bad weather increases the following "
            "gap, sharp posted-limit drops make it slow early, and braking "
            "cancels the whole session. At the planned pickup, it pauses while "
            "you check in and load, then resumes once you depart and get rolling. "
            "Plus and minus, including the keypad keys, raise and lower the "
            "remembered open-road target by five, so you can dial it up to the "
            "speed you want; it will not hold above the posted limit. "
            "X signals for the next announced route exit, called out by its "
            "number when known, or cancels that signal. Prepare early: slow "
            "to 45 for the ramp, hold the exit "
            "lane when lane drift is enabled, and the truck takes the ramp "
            "when your setup is valid. Ramps usually end at a traffic light "
            "or stop sign, called out on the way down; stop for red or the "
            "sign, then pull ahead. X also signals a pull-over if a "
            "trooper lights you up for speeding, scale bypass, or unsafe "
            "equipment: signal, then brake to a stop. Ignoring the lights "
            "gives staged failure-to-stop warnings, then a felony stop "
            "that can cancel the active load. "
            "C also speaks the date and season. "
            "M toggles the in-cab radio, left and right brackets tune it, "
            "and Y speaks radio station, volume, and streamer-safe status. "
            "The Tab status menu includes a radio screen with the currently "
            "receivable stations. "
            "E starts the engine, and stops it only below 5 miles per hour. "
            "Air pressure must build before the truck can move. "
            "Press P to release or set the parking brake; if pressure is "
            "below 100 psi, wait with the engine running. "
            f"{objective_help}"
            "Space speed, active speed-control mode, and target. "
            "S posted speed limit. G the grade under the wheels and whether "
            "the truck is holding it. Tab status menu. F fuel. "
            "C clock, deadline, and hours of service. "
            "R route and current location. Shift R next listed highway exit. "
            "V weather. L lane position. "
            "A repeats the last announcement. Comma re-reads the last spoken "
            "line of any kind, here and in every menu; press it again quickly "
            "to step back through earlier lines. U reads what is "
            "coming up: imposed limits, stops, exits, and bends ahead. "
            "Curves that demand slowing are called before they arrive, "
            "like Sharp left, half a mile, advise 35; D folds the bend "
            "into its one safe-speed number. "
            "The Tab status menu includes a Driver apps tablet menu for "
            "navigation, weather, traffic, truck stops, road chatter, and ELD. "
            "Left or Right Control stops the driving event voice. "
            "Left and Right arrows steer when lane drift is enabled; steer "
            "across the lane line to change lanes. With lane drift off, tap "
            "Left or Right to change lanes instead. Exits leave from the "
            "right lane. Hazards called out as brake or change lanes are "
            "fixed objects in your lane: dodge with a clear lane beside "
            "you, or brake nearly to a stop and ease around. "
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
                "then let the left trigger return to neutral and press and hold it "
                "again to shift into reverse and back slowly. While reversing, hold "
                "the right trigger to brake to a stop, then let it return to "
                "neutral and press and hold again to shift back into forward. A "
                "quick tap just brakes. "
            )
        else:
            gears = (
                "In automatic with simple direction changes, brake to a stop, let "
                "the left trigger return to neutral, then press and hold it again to "
                "shift into reverse and back slowly. While reversing, brake with the "
                "right trigger, and once stopped, release and press it again to "
                "shift back into forward. Holding a brake through a stop just holds "
                "the truck. "
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
            "D-pad down signals for the next announced exit, or signals a "
            "pull-over when a trooper lights you up. "
            "D-pad up reads your route and current location, D-pad left the "
            "weather, D-pad right the clock. The B button speaks your speed. "
            "Click the left stick to honk, "
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
            if self._arrival_full_stop_said and self.truck.speed_mph <= 0.5:
                self._open_facility_arrival()
            else:
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
            self._speak_route_status()
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
        """S: the posted limit here, the zone if any, and how far over you are.

        On a signal-controlled ramp the light IS the law here, so S answers
        with the light and the distance to the stop bar instead -- the
        driver could never ask "where is the bar" before this (owner
        playtest, 2026-07-19: five stop-and-listen hops over 1300 feet)."""
        light = self._ramp_light_query_text()
        if light is not None:
            self.ctx.say(light)
            return
        limit, reason = self.trip.speed_limit_at(self.trip.position_mi)
        zone = f", in a {reason} zone" if reason else ""
        over = self.truck.speed_mph - limit
        comparison = (
            f" You are about {self.ctx.settings.speed_text(over)} over." if over >= 1 else ""
        )
        # Split-limit states post one number for cars and a lower one for
        # rigs, so S saying only the truck figure reads as a wrong map to
        # anyone who remembers the shield (player report, 2026-07-19).
        # Name the state once and the 55 under a 65 sign explains itself.
        is_truck_limit, cap_state = self.trip.truck_limit_at(self.trip.position_mi)
        split = f" {cap_state} holds trucks to this." if cap_state else ""
        # A posted 55 through hairpin country is honest -- the yellow
        # diamond is advisory, not the limit -- but S saying only "55"
        # mid-canyon reads as nonsense, so name the bend's number too.
        curve = self.trip.curve_at(self.trip.position_mi)
        if curve is None:
            upcoming = self.trip.curves_within(SAFE_SPEED_CURVE_MI)
            curve = upcoming[0] if upcoming else None
        advisory = ""
        if curve is not None and curve.advisory_mph < limit:
            advisory = (
                f" The bend here advises {self.ctx.settings.speed_text(curve.advisory_mph)}."
            )
        lead = "Truck limit" if is_truck_limit else "Speed limit"
        self.ctx.say(
            f"{lead} {self.ctx.settings.speed_text(limit)}{zone}."
            f"{split}{comparison}{advisory}"
        )

    def _speak_safe_speed(self) -> None:
        """D: one number -- the speed that is safe right here, right now.

        Sits next to S on purpose: S answers "what is posted", D answers
        "what should I actually be doing". Weather grip, an armed exit, and
        an approaching curve are baked into the math, never into the
        sentence, so the answer survives being heard exactly once at speed.
        Repeatable free.
        """
        limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
        safe = min(limit, self.weather.effects.safe_speed_mph)
        context = ""
        # The bend under the wheels, or the next one close ahead: whichever
        # binds, its advisory is the number that keeps the truck on the
        # road. Connector arcs count when the truck is inside one.
        curve = self.trip.curve_at(self.trip.position_mi)
        if curve is None:
            upcoming = self.trip.curves_within(SAFE_SPEED_CURVE_MI)
            curve = upcoming[0] if upcoming else None
        if curve is not None and curve.advisory_mph < safe:
            safe = curve.advisory_mph
            context = " for the bend"
        stop = getattr(self, "_exit_stop", None)
        ahead = (stop.at_mi - self.trip.position_mi) if stop is not None else None
        exit_armed = (
            getattr(self, "_exit_signal_on", False)
            and ahead is not None
            and 0 < ahead <= SAFE_SPEED_EXIT_MI
        )
        if getattr(self, "_ramp_mi", None) is not None or exit_armed:
            safe = min(safe, RAMP_MAX_MPH)
            context = " for the ramp"
        self.ctx.say(f"Safe speed {self.ctx.settings.speed_text(safe)}{context}.")

    def _speak_last_announcement(self) -> None:
        """A: replay the last route announcement, for one you missed."""
        if self._last_event_message:
            self.ctx.say(self._last_event_message)
        else:
            self.ctx.say("No recent announcement to repeat.")

    def _speak_grade(self) -> None:
        """G: the grade under the wheels and what it is doing to the truck.

        The verdict comes from the sim's own net-force balance, so the spoken
        answer to "why am I slowing down" is the same physics the wheels feel
        -- including whether the jake has the descent or is about to lose it.
        """
        t = self.truck
        grade = t.grade
        if abs(grade) < 0.005:
            parts = ["Level road."]
        else:
            direction = "uphill" if grade > 0 else "downhill"
            lead = f"Grade {abs(grade) * 100:.1f} percent {direction}"
            # How far the slope keeps its character, sampled the way the
            # chain-law scan does; flat or reversed counts as the end.
            sign = 1.0 if grade > 0 else -1.0
            run_mi = None
            probe = 0.25
            while probe <= 15.0:
                at = self.trip.position_mi + probe
                if at >= self.trip.total_miles:
                    break
                if self.trip.grade_at(at) * sign <= 0.002:
                    run_mi = probe
                    break
                probe += 0.25
            if run_mi is not None and run_mi >= 1.0:
                lead += f" for another {self.trip._distance_text(run_mi)}"
            parts = [lead + "."]
        moving = t.velocity_mps > 0.5
        if moving:
            net = t.drive_force() - t.resistance_force() - t.brake_force()
            accel_mph_s = net / t.gross_mass_kg * 2.23694
            stage = t.engine_brake_stage
            if grade > 0.005:
                if accel_mph_s < -0.2:
                    parts.append("The hill has the load; expect to lose speed.")
                elif accel_mph_s > 0.2:
                    parts.append("Pulling it with speed to spare.")
                else:
                    parts.append("Holding speed.")
            elif grade < -0.005:
                if t.jake_slipping:
                    parts.append("The jake is sliding the drive wheels; back it off a stage.")
                elif accel_mph_s > 0.2:
                    if stage > 0:
                        parts.append(
                            f"Jake stage {stage} is not holding it; gear down or snub the brakes."
                        )
                    elif t.throttle <= 0.05:
                        parts.append("Speed is building; set the jake before it runs.")
                elif stage > 0:
                    parts.append(f"Jake stage {stage} has it.")
                else:
                    parts.append("Speed in hand.")
        self.ctx.say(" ".join(parts))

    def _speak_upcoming(self, within_mi: float = 15.0) -> None:
        """U: what is coming up -- imposed limits, stops, and exits ahead.

        On a signal-controlled ramp the nearest upcoming thing is always
        the stop bar, so it leads the readout with the light's phase."""
        s = self.ctx.settings
        pos = self.trip.position_mi
        parts: list[str] = []
        light = self._ramp_light_query_text()
        if light is not None:
            parts.append(light.rstrip(".").lower())
        zone = self.trip.next_zone_within(within_mi)
        if zone is not None:
            paired = None
            if zone.reason == "construction merge":
                paired = next(
                    (
                        z
                        for z in self.trip.zones
                        if z.reason == "construction" and abs(z.start_mi - zone.end_mi) < 0.01
                    ),
                    None,
                )
            if paired is not None:
                parts.append(
                    f"construction taper in {s.distance_text(zone.start_mi - pos)}, "
                    f"merge left, speed limit {s.speed_text(zone.limit_mph)}, "
                    f"then work zone {s.speed_text(paired.limit_mph)}"
                )
            else:
                parts.append(
                    f"{zone.reason} in {s.distance_text(zone.start_mi - pos)}, "
                    f"speed limit {s.speed_text(zone.limit_mph)}"
                )
        stop = self.trip.upcoming_stop(within_mi)
        if stop is not None:
            # The ramp's ending is part of the plan: a stop sign first heard
            # mid-ramp is too late to brake for.
            ending = {
                "signal": ", where the ramp ends at a traffic light",
                "stop": ", where the ramp ends at a stop sign",
            }.get(self._ramp_control_for(stop), "")
            parts.append(
                f"{self.trip.planned_prefix(stop)}{stop.spoken_name} "
                f"in {s.distance_text(stop.at_mi - pos)}{ending}"
            )
        pressure = self.trip.next_traffic_pressure_within(within_mi)
        if pressure is not None:
            parts.append(
                f"{pressure.reason} in {s.distance_text(pressure.start_mi - pos)}, "
                f"move {pressure.direction} and target "
                f"{s.speed_text(pressure.target_speed_mph)}"
            )
        if self.ctx.settings.hos_mode not in hos.HOS_NON_ENFORCED_MODES:
            patrol = self.trip.next_patrol_within(within_mi)
            if patrol is not None:
                ahead = patrol.start_mi - pos
                parts.append(self.trip.cb_patrol_status(patrol, ahead))
        cue = self.trip.next_exit_cue()
        if cue is not None and 0 < cue.at_mi - pos <= within_mi:
            parts.append(f"in {s.distance_text(cue.at_mi - pos)}, {cue.text}")
        # The next few bends that would demand slowing from the posted
        # limit; gentle sweeps stay out of the readout like they stay out
        # of the pacenotes.
        limit, _ = self.trip.speed_limit_at(pos)
        bends = [
            c
            for c in self.trip.curves_within(within_mi)
            if c.advisory_mph < limit and c.severity != "gentle"
        ][:3]
        for c in bends:
            parts.append(
                f"{self._pacenote_phrase(c).lower()} in "
                f"{s.distance_text(c.start_mi - pos, precise=True)}, "
                f"advise {s.speed_text(c.advisory_mph)}"
            )
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
            self.trip.npc_traffic_status(),
            f"Route: {progress}",
            f"Fuel: {t.fuel_fraction * 100:.0f} percent",
            f"Air brakes: {self._air_status_text(detailed=True)}",
            f"Weather: {self.weather.describe(self.ctx.settings.imperial_units)}",
            f"Radio: {self.radio.status_text()}",
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
        for worn, label in (
            (t.tire_wear_pct, "Tires"),
            (t.brake_wear_pct, "Brakes"),
            (t.engine_wear_pct, "Engine"),
        ):
            if worn >= WEAR_STATUS_PCT:
                lines.append(f"{label}: {worn:.0f} percent worn")
        now_h = self._absolute_game_hour()
        for entry in self.ctx.profile.active_buffs:
            left_h = float(entry.get("expires_h", 0.0)) - now_h
            if left_h <= 0.0:
                continue
            if left_h >= 1.05:
                left = f"about {left_h:.0f} hours left"
            else:
                left = f"about {left_h * 60.0:.0f} minutes left"
            lines.append(f"{entry.get('label', 'Buff')}: {left}")
        for info in self.rig_buffs.values():
            lines.append(f"{info.get('label', 'Rig service')}: good for the rest of the trip")
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
            f"Next legal stop: {self.trip.planned_prefix(next_stop)}{next_stop.spoken_name} "
            f"in {self.ctx.settings.distance_text(ahead)}"
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

    def _update_pedal_latches(
        self,
        key_up: bool,
        key_down: bool,
        pad_throttle: float,
        pad_brake: float,
        emergency: bool,
        dt: float,
    ) -> tuple[bool, bool]:
        """Advance both pedal latches and blend them into the pedal state.

        Called once per frame from update() with the raw pedal inputs;
        returns the effective (key_up, key_down) the rest of the frame
        drives on. The catch clicks (its own sound, not the gear click)
        and both directions speak. The opposite pedal always releases a
        latch instantly, and safety systems outrank a latched accelerator:
        a live hazard (including automatic emergency braking), the
        emergency brake, and the overspeed alarm all drop it audibly.
        """
        if not self.ctx.settings.pedal_latch:
            if self._throttle_latch.release():
                self.ctx.say_event("Throttle released.", interrupt=False)
            if self._brake_latch.release():
                self.ctx.say_event("Brake released.", interrupt=False)
            return key_up, key_down
        for latch, held, name in (
            (self._throttle_latch, key_up, "Throttle"),
            (self._brake_latch, key_down, "Brake"),
        ):
            event = latch.update(bool(held), dt)
            if event == "latched":
                # The latch gesture's second press is also a press-and-hold
                # at whatever speed the truck has -- at a standstill that
                # would arm a direction change and grab reverse a tenth of
                # a second after the catch. The catch wins: latching a
                # pedal means "hold this", never "change direction".
                self._direction_armed = ""
                self._direction_hold_s = 0.0
                self.ctx.audio.play("ui/tick", volume=1.0)
                self.ctx.say_event(f"{name} latched.", interrupt=False)
            elif event == "released":
                self.ctx.say_event(f"{name} released.", interrupt=False)
        throttle_overridden = (
            key_down
            or pad_brake > 0.05
            or emergency
            or self._hazard_deadline is not None
            or self._overspeed_active
        )
        if throttle_overridden and self._throttle_latch.release():
            self.ctx.say_event("Throttle released.", interrupt=False)
        if (key_up or pad_throttle > 0.05) and self._brake_latch.release():
            self.ctx.say_event("Brake released.", interrupt=False)
        return (
            key_up or self._throttle_latch.latched,
            key_down or self._brake_latch.latched,
        )
