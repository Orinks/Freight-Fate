# ruff: noqa: F403,F405
from __future__ import annotations

from .base import TimedMessageState
from .driving_core import *
from .driving_menu_states import ArrivalState, FacilityArrivalState
from .driving_rest_states import ParkingFullState, RestStopState


class DrivingEventMixin:
    def _speak_ambient_event(self, message: str, sound: str | None = None) -> None:
        if self._hazard_deadline is not None or self._ambient_event_cooldown_s > 0.0:
            self._pending_ambient_event = (message, sound)
            return
        if sound is not None:
            self.ctx.audio.play(sound)
        self.ctx.say_event(message, interrupt=False)
        self._ambient_event_cooldown_s = AMBIENT_EVENT_SPACING_S

    def _update_ambient_events(self, dt: float) -> None:
        if self._ambient_event_cooldown_s > 0.0:
            self._ambient_event_cooldown_s = max(0.0, self._ambient_event_cooldown_s - dt)
        if self._hazard_deadline is not None:
            return
        if self._ambient_event_cooldown_s > 0.0 or self._pending_ambient_event is None:
            return
        message, sound = self._pending_ambient_event
        self._pending_ambient_event = None
        self._speak_ambient_event(message, sound)

    def _should_space_ambient_event(self, event) -> bool:
        if event.kind == TripEventKind.WEATHER_CHANGE:
            return True
        if event.kind == TripEventKind.GPS_CUE:
            cue = event.data.get("cue")
            return (
                event.data.get("cb_patrol") is not None
                or event.data.get("traffic_pressure") is not None
                or getattr(cue, "kind", "") == "toll"
            )
        return False

    def _handle_trip_event(self, event) -> None:
        if self._should_ignore_untaken_destination_facility_event(event):
            return
        kind = event.kind
        sound = _route_event_sound(event)
        if event.message:
            self._last_event_message = event.message   # replayable with A
        if kind == TripEventKind.HAZARD:
            if self._ramp_mi is not None:
                return   # off the highway: the hazard passes you by
            if self._cruise_mph is not None:
                self._cancel_cruise()   # hands back on the wheel to brake
            self._pending_ambient_event = None
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
            self._speak_ambient_event(event.message)
            self._record_weather_achievement()
        elif kind == TripEventKind.TOLL_CHARGED:
            self._speak_ambient_event(event.message, sound or "ui/notify")
            self.ctx.award_achievement("toll_paid", event=True)
        elif kind == TripEventKind.STATE_CROSSING:
            cue = event.data.get("cue")
            state = getattr(cue, "near_text", event.message)
            add_unique_stat(self.ctx.profile, "states_crossed", str(state))
            self._speak_ambient_event(event.message, sound)
            self.ctx.award_achievement("state_crossing", event=True)
        elif kind == TripEventKind.ARRIVED:
            pass  # handled by _arrive()
        elif self._event_disables_cruise(event):
            self._cancel_cruise_for_restricted_area(event.message)
        else:
            critical = self._is_critical_event(event)
            if critical:
                self._pending_ambient_event = None
                if sound is not None and kind != TripEventKind.ZONE_ENTER:
                    self.ctx.audio.play(sound)
                self.ctx.say_event(event.message, interrupt=True)
            elif self._should_space_ambient_event(event):
                self._speak_ambient_event(
                    event.message,
                    sound if kind != TripEventKind.ZONE_ENTER else None,
                )
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
            if (
                getattr(cue, "kind", "") == "traffic"
                or event.data.get("traffic_pressure") is not None
            ):
                self.ctx.award_achievement("traffic_slowing", event=True)

    def _is_critical_event(self, event) -> bool:
        """Safety announcements that must preempt ambient chatter on the event
        voice -- zone entries, checkpoints, and zone-ahead/traffic warnings --
        versus informational cues (weather, tolls, state lines, stops) that
        should queue and yield rather than bury a warning you need to act on."""
        if event.kind in (TripEventKind.HAZARD, TripEventKind.ZONE_ENTER,
                          TripEventKind.CHECKPOINT):
            return True
        if event.kind == TripEventKind.GPS_CUE:
            if event.data.get("zone") is not None:
                return True
            cue = event.data.get("cue")
            if getattr(cue, "kind", "") == "traffic":
                return True
        return False

    def _should_ignore_untaken_destination_facility_event(self, event) -> bool:
        if self.phase != DRIVE_PHASE_DELIVERY or self._destination_exit_taken:
            return False
        zone = event.data.get("zone")
        if zone is None:
            return False
        return zone.reason in {
            "destination approach",
            "facility access road",
            "facility gate",
        }

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
        # A restricted area (construction, heavy traffic) is a safety cue: it
        # preempts ambient chatter rather than queuing behind it.
        self.ctx.say_event(
            f"{message} Adaptive cruise disabled; take manual speed control.",
            interrupt=True,
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

    def _open_poi_stop(self, stop, *, settle: bool = False) -> None:
        # Secure the truck before handing off to the stop menu: zero the
        # throttle, apply the service brake, and set the parking brake. A truck
        # that rolled in just under the docking threshold (or idled in gear)
        # would otherwise keep creeping while the driver rests -- napping while
        # the rig drifts down the freeway. Mirrors the pickup/delivery arrivals.
        self.truck.throttle = 0.0
        self.truck.brake = 1.0
        self.truck.set_parking_brake()

        if settle:
            _advance_rest_clock(self, STOP_PULL_IN_MIN)
            self.hos.on_duty(STOP_PULL_IN_MIN)
            self.ctx.profile.active_trip = self.snapshot()
            self.ctx.save_profile()

            def complete() -> None:
                self.ctx.pop_state()
                self._open_poi_stop(stop, settle=False)

            self.ctx.push_state(TimedMessageState(
                self.ctx,
                title="Pulling into stop",
                message=(
                    f"Pulling into {stop.spoken_name}. "
                    "Brakes set; menu opening in a moment."
                ),
                status="Pulling into the route stop. Please wait.",
                seconds=STOP_PULL_IN_WAIT_S,
                on_complete=complete,
                sound_key="ui/notify"))
            return

        can_sleep = "sleep" in stop.actions
        if can_sleep and hos.parking_is_full(self.trip_seed, stop.at_mi,
                                             self.trip.current_hour):
            self.ctx.push_state(ParkingFullState(self.ctx, self, stop))
            return
        self.ctx.push_state(RestStopState(self.ctx, self, stop))
        self.ctx.award_achievement("first_rest_stop")

    def _take_exit(self) -> None:
        self._toggle_exit_signal()

    def _toggle_exit_signal(self) -> None:
        if self._ramp_mi is not None:
            self.ctx.say("You are already on the exit ramp. Brake to a stop.")
            return
        stop = self._exit_stop or self._upcoming_exit_stop()
        if stop is None:
            self.ctx.say(
                "No route exit to signal for yet. Exits are announced as you "
                "approach them."
            )
            return
        self._exit_stop = stop
        self._exit_signal_on = not self._exit_signal_on
        ahead = stop.at_mi - self.trip.position_mi
        if not self._exit_signal_on:
            self.ctx.say("Signal canceled. Keep following the highway.")
            return
        self.ctx.audio.play("ui/notify", volume=0.5)
        if stop.type == "delivery_destination":
            head = (
                f"Signal on for {self._destination_exit_phrase(stop)}, "
                f"destination exit for {stop.name},"
            )
        elif stop.exit_label:
            head = f"Signal on for {stop.exit_label}, {stop.spoken_name},"
        else:
            head = f"Signal on for the {stop.spoken_name} exit,"
        if self.ctx.settings.steering_assist == "off":
            self._exit_lane_alignment = EXIT_LANE_READY
            self._exit_lane_ready_said = True
            self.ctx.audio.play("ui/notify", volume=0.6)
            self.ctx.say(
                f"{head} {ahead:.1f} miles ahead. Exit lane set. "
                f"Slow to {RAMP_MAX_MPH:.0f} or less for the ramp."
            )
            return
        self.ctx.say(f"{head} {ahead:.1f} miles ahead. "
                     "Move right for the exit lane, then slow to "
                     f"{RAMP_MAX_MPH:.0f} or less for the ramp.")

    def _reset_exit_lane_state(self) -> None:
        self._exit_lane_alignment = 0.0
        self._exit_lane_prompt_said = False
        self._exit_lane_ready_said = False
        self._exit_commit_said = False

    def _exit_lane_ready(self) -> bool:
        return (
            self._exit_lane_alignment >= EXIT_LANE_READY
            or self.lane.offset >= EXIT_LANE_OFFSET_READY
        )

    def _update_exit_preparation(self, keys, dt: float) -> None:
        stop = self._exit_stop
        if stop is None or self._ramp_mi is not None:
            self._reset_exit_lane_state()
            return
        if self.ctx.settings.steering_assist == "off":
            return
        ahead = stop.at_mi - self.trip.position_mi
        if ahead < -EXIT_COMMIT_WINDOW_MI:
            return

        right = keys[pygame.K_RIGHT]
        left = keys[pygame.K_LEFT]
        if right:
            self._exit_lane_alignment += dt / 1.2
        elif left:
            self._exit_lane_alignment -= dt / 0.8
        elif (
            self._exit_lane_ready_said
            and self._exit_lane_alignment >= EXIT_LANE_READY
            and self.lane.offset >= -0.25
        ):
            self._exit_lane_alignment = max(
                self._exit_lane_alignment, EXIT_LANE_READY)
        elif self.lane.offset >= EXIT_LANE_OFFSET_READY:
            self._exit_lane_alignment += dt / 2.0
        elif self.lane.offset < -0.25:
            self._exit_lane_alignment -= dt / 0.8
        else:
            self._exit_lane_alignment -= dt / 4.0
        self._exit_lane_alignment = max(0.0, min(1.0, self._exit_lane_alignment))

        if 0 < ahead <= EXIT_LANE_PREP_MI and not self._exit_lane_prompt_said:
            self._exit_lane_prompt_said = True
            pressure = self._active_exit_pressure(stop)
            pressure_text = (
                " Traffic is tight, so hold the lane and let the gap open."
                if pressure is not None and pressure.intensity >= 0.35 else ""
            )
            self.ctx.say_event(
                f"Exit lane in {ahead:.1f} miles. Signal is on; steer right "
                f"for the exit lane and slow to {RAMP_MAX_MPH:.0f}.{pressure_text}",
                interrupt=False,
            )
        if (
            0 < ahead <= EXIT_LANE_PREP_MI
            and self._exit_lane_ready()
            and not self._exit_lane_ready_said
        ):
            self._exit_lane_ready_said = True
            self.ctx.audio.play("ui/notify", volume=0.6)
            self.ctx.say("Exit lane set. Hold this lane and keep slowing.")
        if 0 <= ahead <= EXIT_COMMIT_WINDOW_MI and not self._exit_commit_said:
            self._exit_commit_said = True
            self.ctx.say_event(
                "At the exit gore. Hold the exit lane and stay under "
                f"{RAMP_MAX_MPH:.0f}.",
                interrupt=False,
            )

    def _active_exit_pressure(self, stop) -> object | None:
        sample_mi = min(self.trip.position_mi, stop.at_mi)
        pressure = self.trip.traffic_pressure_at(sample_mi)
        if pressure is None or pressure.kind != "exit":
            return None
        if pressure.start_mi <= stop.at_mi <= pressure.end_mi + 0.2:
            return pressure
        return None

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
        lane_text = (
            "Slow down for the ramp."
            if self.ctx.settings.steering_assist == "off"
            else "Move right for the exit lane and slow down."
        )
        return (f"In {ahead:.0f} miles, {phrase}, destination exit. "
                f"{lane_text}")

    def _check_destination_exit(self) -> None:
        stop = self._destination_exit_stop()
        if stop is None:
            return
        ahead = stop.at_mi - self.trip.position_mi
        if not (0 < ahead <= EXIT_WINDOW_MI):
            return
        key = self._destination_exit_key(stop)
        if key != self._destination_exit_announced_key:
            self._destination_exit_announced_key = key
            message = self._destination_exit_announcement(stop, ahead)
            if self._cruise_mph is not None:
                self._cancel_cruise()
                message += " Adaptive cruise disabled; take manual speed control."
            self.ctx.audio.play("ui/notify", volume=0.7)
            self.ctx.say_event(message, interrupt=False)
        if self._exit_stop is None:
            self._exit_stop = stop
            self._reset_exit_lane_state()
            if self.ctx.settings.steering_assist == "off":
                self._exit_lane_alignment = EXIT_LANE_READY
                self._exit_lane_ready_said = True

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
                    self._open_poi_stop(stop, settle=True)
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
        self._exit_signal_on = False
        if self.trip.position_mi > stop.at_mi + EXIT_COMMIT_WINDOW_MI:
            self._reset_exit_lane_state()
            pressure = self._active_exit_pressure(stop)
            if pressure is not None and pressure.intensity >= 0.35:
                self.ctx.say_event(
                    "You missed the exit window in heavy traffic and stayed on "
                    "the highway."
                )
            else:
                self.ctx.say_event(
                    "You missed the exit window and stayed on the highway."
                )
            return
        if not self._exit_lane_ready():
            self._reset_exit_lane_state()
            place = (self._destination_exit_phrase(stop)
                     if stop.type == "delivery_destination" else stop.spoken_name)
            pressure = self._active_exit_pressure(stop)
            missed = stop.exit_label if stop.exit_label else "the exit"
            if pressure is not None:
                self.ctx.say_event(
                    "Traffic boxed you out of the exit lane at the gore, so "
                    f"you missed {missed} for {place}. Stay on the highway and "
                    "recover at the next safe exit."
                )
            else:
                self.ctx.say_event(
                    f"You missed {missed} for {place}: you were not in the "
                    "exit lane. Stay on the highway and recover at the next safe exit."
                )
            return
        if self.truck.speed_mph <= RAMP_MAX_MPH:
            self._reset_exit_lane_state()
            self._exit_signal_on = False
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
            self._exit_signal_on = False
            self._reset_exit_lane_state()

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
        _, zone_reason = self.trip.speed_limit_at(self.trip.position_mi)
        if zone_reason is not None:
            # No cruise on facility access roads, gates, work zones, or heavy
            # traffic -- low-speed local stretches a real driver takes manually.
            self.ctx.say(f"Adaptive cruise is not available in a {zone_reason} zone.")
            return
        self._cruise_mph = t.speed_mph
        self._cruise_throttle = t.throttle
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False
        gap = self._acc_gap_seconds()
        self.ctx.audio.play("ui/notify", volume=0.5)
        self.ctx.say("Adaptive cruise set at "
                      f"{self.ctx.settings.speed_text(t.speed_mph)}. "
                      f"Following gap {gap:.0f} seconds. "
                      "K or braking cancels.")

    def _adjust_cruise(self, delta_mph: float) -> None:
        """Raise or lower the cruise set point -- the Accel/Coast (+/-) buttons.

        Only while cruise is engaged: the truck then accelerates up to a higher
        set point or eases down to a lower one, still capped at the posted limit
        plus the offset. So you engage once rolling, then dial the target up to
        the speed you want without having to reach it manually first."""
        if self._cruise_mph is None:
            self.ctx.say("Adaptive cruise is off. Press K to set it first.")
            return
        self._cruise_mph = max(CRUISE_MIN_MPH,
                               min(CRUISE_MAX_MPH, self._cruise_mph + delta_mph))
        self.ctx.say(
            f"Adaptive cruise {self.ctx.settings.speed_text(self._cruise_mph)}.")

    def _cancel_cruise(self) -> None:
        self._cruise_mph = None
        self._cruise_throttle = 0.0
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False

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
        # Predictive ACC: never carry the driver past the posted limit. With real
        # OSM limits baked per leg, a held set speed would otherwise sail through
        # urban drops and corridor limit changes straight into speeding strikes,
        # tickets, and trooper stops -- all of which now exist. The "Speed limit X"
        # cue still names the number; this cue says cruise is handling it.
        posted, _ = self.trip.speed_limit_at(self.trip.position_mi)
        cap_mph = posted + ACC_LIMIT_OFFSET_MPH
        limit_capped = cap_mph < self._cruise_mph
        if limit_capped:
            target_mph = cap_mph
            if not self._acc_limit_capped:
                self.ctx.say_event(
                    "Posted limit lower; adaptive cruise easing to "
                    f"{self.ctx.settings.speed_text(cap_mph)}.", interrupt=False)
        self._acc_limit_capped = limit_capped
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
        if (following or limit_capped) and error < -2.0:
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
        p.game_hours += (self.trip.game_minutes + STOP_PULL_IN_MIN) / 60.0
        p.hos.on_duty(STOP_PULL_IN_MIN)
        p.market.advance_to(p.market_day())
        p.active_trip = pickup_snapshot(self.job, air_brake=self.truck.air_brake_snapshot())
        self.ctx.save_profile()
        self._set_status("Pulling into pickup. Check-in menu opening.")

        def complete() -> None:
            self._set_status("Parked at pickup. Check in and load.")
            self.ctx.replace_state(PickupFacilityState(self.ctx, self.job, driving=self))

        self.ctx.replace_state(TimedMessageState(
            self.ctx,
            title="Pulling into pickup",
            message=(
                f"Pulling into {self._pickup_facility_text()}. "
                "Setting the brakes and rolling to the check-in lane."
            ),
            status="Pulling into the pickup facility. Please wait.",
            seconds=STOP_PULL_IN_WAIT_S,
            on_complete=complete,
            sound_key="ui/notify"))

    def _arrive(self) -> None:
        self.ctx.replace_state(ArrivalState(self.ctx, self))

    def _handle_missed_destination_exit(self) -> None:
        self.trip.finished = False
        self._exit_stop = None
        self._exit_signal_on = False
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
        _advance_rest_clock(self, STOP_PULL_IN_MIN)
        self.hos.on_duty(STOP_PULL_IN_MIN)
        self._set_status("Pulling into destination. Dock menu opening.")

        def complete() -> None:
            self._set_status("Parked at destination. Dock and deliver.")
            self.ctx.replace_state(FacilityArrivalState(self.ctx, self))

        self.ctx.replace_state(TimedMessageState(
            self.ctx,
            title="Pulling into destination",
            message=(
                f"Pulling into {self._destination_facility_text()}. "
                "Brakes set; dock menu opening in a moment."
            ),
            status="Pulling into the destination facility. Please wait.",
            seconds=STOP_PULL_IN_WAIT_S,
            on_complete=complete,
            sound_key="ui/notify"))

    def _destination_facility_text(self) -> str:
        return self.job.destination_facility_text()

    def _pickup_facility_text(self) -> str:
        return self.job.origin_facility_text()

    def _city_service_text(self) -> str:
        try:
            return self.ctx.world.city_service(
                self.job.origin, self.city_service_key).spoken_name
        except KeyError:
            return self.job.destination_location or "city service"

    def _objective_text(self) -> str:
        if self.phase == DRIVE_PHASE_PICKUP:
            return "pickup at " + self._pickup_facility_text()
        if self.phase == DRIVE_PHASE_CITY_SERVICE:
            return "city service " + self._city_service_text()
        return "deliver to " + self._destination_facility_text()

    def _pickup_progress_summary(self) -> str:
        return (f"{self.trip.remaining_miles:.1f} miles remaining of "
                f"{self.trip.total_miles:.1f} to pickup at "
                f"{self._pickup_facility_text()}.")

    def _city_service_progress_summary(self) -> str:
        return (f"{self.trip.remaining_miles:.1f} miles remaining of "
                f"{self.trip.total_miles:.1f} to {self._city_service_text()}.")

    def _handle_city_service_gate(self) -> None:
        if self.truck.speed_mph <= DOCKING_MAX_MPH:
            first_ready = not self._city_service_enter_ready
            self._city_service_enter_ready = True
            if first_ready:
                p = self.ctx.profile
                self._cancel_cruise()
                self.truck.throttle = 0.0
                self.truck.brake = 1.0
                self.truck.set_parking_brake()
                p.truck_fuel_gal = self.truck.fuel_gal
                p.truck_damage_pct = self.truck.damage_pct
                p.active_trip = self.snapshot()
                self.ctx.save_profile()
                self._set_status("Parked at city service. Press Enter to go inside.")
                self.ctx.audio.play("ui/notify", volume=0.7)
                self.ctx.say_event(
                    f"Parked at {self._city_service_text()}. Press Enter to go inside.",
                    interrupt=False,
                )
            return
        if self.truck.speed_mph <= DELIVERY_PARK_MPH:
            if self._arrival_full_stop_said:
                return
            self._arrival_full_stop_said = True
            self._cancel_cruise()
            self.ctx.audio.play("ui/notify", volume=0.7)
            self._set_status("City service ahead: stop, then press Enter.")
            self.ctx.say_event(
                f"At {self._city_service_text()}. Stop, then press Enter to go inside.",
                interrupt=False,
            )
            return
        if self._arrival_stop_said:
            return
        self._arrival_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/warning")
        self._set_status("City service ahead: slow down and stop.")
        self.ctx.say_event(
            f"City service ahead: {self._city_service_text()}. "
            "Slow down and come to a complete stop.",
            interrupt=True,
        )

    def _enter_city_service(self) -> None:
        if self.phase != DRIVE_PHASE_CITY_SERVICE:
            return
        if not self.trip.finished:
            self.ctx.say(f"Keep following the GPS to {self._city_service_text()}.")
            return
        if self.truck.speed_mph > DOCKING_MAX_MPH:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Stop before going inside.")
            return
        self._open_city_service()

    def _open_city_service(self) -> None:
        if self._arrival_menu_open:
            return
        from .city import CityMenuState, GarageState, TruckShopState, open_freight_market

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
        p.active_trip = None
        self.ctx.save_profile()
        service = self.ctx.world.city_service(p.current_city, self.city_service_key)
        self._set_status(f"Inside {service.name}.")
        self.ctx.audio.play("vehicle/truck_door")
        self.ctx.reset_to(CityMenuState(self.ctx))
        if service.key == "freight_market":
            open_freight_market(self.ctx)
        elif service.key == "garage":
            self.ctx.push_state(GarageState(self.ctx))
        elif service.key == "truck_dealer":
            self.ctx.push_state(GarageState(self.ctx))
            self.ctx.push_state(TruckShopState(self.ctx))
        else:
            self.ctx.say(f"Inside {service.spoken_name}.", interrupt=True)

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
            f"Date: {self._calendar_phrase() or 'unknown'}",
            f"Clock: {clock_text(self.trip.current_hour)} "
            f"({time_of_day(self.trip.current_hour)})   "
            f"Fatigue: {self.ctx.profile.fatigue:.0f}%",
            "",
            self._status_text,
        ]

