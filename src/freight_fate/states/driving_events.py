# ruff: noqa: F403,F405
from __future__ import annotations

from .driving_core import *
from .driving_menu_states import ArrivalState, FacilityArrivalState
from .driving_rest_states import ParkingFullState, RestStopState


class DrivingEventMixin:
    def _handle_trip_event(self, event) -> None:
        if self._should_ignore_destination_exit_gps_cue(event):
            return
        kind = event.kind
        sound = _route_event_sound(event)
        if event.message:
            self._last_event_message = event.message  # replayable with A
        if kind == TripEventKind.HAZARD:
            if self._ramp_mi is not None:
                return  # off the highway: the hazard passes you by
            speed_control_was_active = (
                self._speed_control_armed
                or self._cruise_mph is not None
                or self._keeper_mph is not None
            )
            if speed_control_was_active:
                self._disarm_speed_control()  # hands back on the wheel to brake
            self.ctx.audio.play(sound or "ui/warning")
            self.ctx.controller.rumble.hazard()  # 750 ms right->left sweep
            # The deadline is braking physics plus reaction slack. The physics
            # part is whatever full service brakes need from the current speed
            # on this surface; the rolled window covers hearing the warning and
            # getting on the pedal, and fatigue eats into that part only --
            # a drowsy driver reacts late, but the truck stops no slower.
            slack = event.data.get("deadline_s", 4.0)
            self._hazard_deadline = self._brake_budget_s() + slack * hos.reaction_window_mult(
                self.ctx.profile.fatigue
            )
            message = terse_hazard_message(event.message) if self._terse_speech() else event.message
            if speed_control_was_active:
                message = f"{message} Automatic speed control canceled."
            self.ctx.say_event(message, interrupt=True)
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
        elif kind == TripEventKind.TIMEZONE_CROSSING:
            if sound is not None:
                self.ctx.audio.play(sound)
            self.ctx.say_event(
                timezone_crossing_message(event, self._terse_speech()), interrupt=False
            )
        elif kind == TripEventKind.ARRIVED:
            pass  # handled by _arrive()
        elif self._event_disables_cruise(event):
            self._cancel_cruise_for_restricted_area(event)
        else:
            if sound is not None and kind != TripEventKind.ZONE_ENTER:
                self.ctx.audio.play(sound)
            self.ctx.say_event(event.message, interrupt=self._is_critical_event(event))
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

    def _should_ignore_destination_exit_gps_cue(self, event) -> bool:
        if self.phase != DRIVE_PHASE_DELIVERY or event.kind != TripEventKind.GPS_CUE:
            return False
        cue = event.data.get("cue")
        if getattr(cue, "kind", "") != "interchange":
            return False
        stop = self._destination_exit_stop()
        if stop is None:
            return False
        return abs(float(getattr(cue, "at_mi", -9999.0)) - stop.at_mi) <= 0.15

    def _is_critical_event(self, event) -> bool:
        """Safety announcements that must preempt ambient chatter on the event
        voice -- zone entries, checkpoints, and zone-ahead/traffic warnings --
        versus informational cues (weather, tolls, state lines, stops) that
        should queue and yield rather than bury a warning you need to act on."""
        if event.kind in (TripEventKind.HAZARD, TripEventKind.ZONE_ENTER, TripEventKind.CHECKPOINT):
            return True
        if event.kind == TripEventKind.GPS_CUE:
            if event.data.get("zone") is not None:
                return True
            cue = event.data.get("cue")
            if getattr(cue, "kind", "") == "traffic":
                return True
        return False

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
        # An armed speed-control session stays on for the advance warning so
        # cruise can slow for the lower limit, then hands off at zone entry.
        if self._speed_control_armed and self.ctx.settings.speed_keeper:
            return False
        return zone.reason in {"construction", "heavy traffic"}

    def _cancel_cruise_for_restricted_area(self, event) -> None:
        message = event.message
        zone = event.data.get("zone")
        if self._speed_control_armed and self.ctx.settings.speed_keeper and zone is not None:
            self._cancel_cruise(preserve_session=True)
            self._engage_keeper(
                zone.limit_mph,
                zone.reason,
                target_mph=zone.limit_mph,
                announce=False,
            )
            self.ctx.audio.play("ui/notify")
            message = (
                f"{message} Speed keeper holding {self.ctx.settings.speed_text(self._keeper_mph)}."
            )
            self.ctx.say_event(message, interrupt=True)
            return
        self._cancel_cruise()
        self.ctx.audio.play("ui/notify")
        # A restricted area (construction, heavy traffic) is a safety cue: it
        # preempts ambient chatter rather than queuing behind it.
        if not self._terse_speech():
            message = f"{message} Adaptive cruise disabled; take manual speed control."
        self.ctx.say_event(message, interrupt=True)

    def _handle_inspection(self, event) -> None:
        """Route-backed enforcement with stable evidence and no duplicate fines."""
        event_key = str(
            event.data.get(
                "key",
                f"{event.message}:{round(self.trip.position_mi, 1)}:{self.hos_fine_count}",
            )
        )
        if event_key in self.enforcement_events:
            return
        self.enforcement_events.add(event_key)
        p = self.ctx.profile
        fine = hos.HOS_FINES[min(self.hos_fine_count, len(hos.HOS_FINES) - 1)]
        self.hos_fine_count += 1
        p.money -= fine  # can go negative; never a game over
        p.career.reputation = max(0.0, p.career.reputation - hos.HOS_REPUTATION_HIT)
        evidence = list(event.data.get("evidence", ()))
        if not evidence:
            evidence = ["HOS/ELD violation"]
        evidence_text = ", ".join(evidence)
        self.ctx.audio.play("ui/error")
        self.ctx.controller.rumble.alert()
        serious_hos = (
            self.ctx.settings.hos_mode not in hos.HOS_NON_ENFORCED_MODES
            and self.hos.in_violation(self.ctx.settings.hos_mode)
        )
        message = (
            f"{event.message} Evidence: {evidence_text}. "
            f"Fined {fine:,.0f} dollars, and your reputation took a hit."
        )
        if serious_hos:
            self.ctx.say_event(
                message + " Out of service order: parked for 10 hours to reset your ELD clock.",
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
            self.ctx.say("There is no route POI here. Stops are announced as you approach them.")
            return
        if self.truck.speed_mph > DOCKING_MAX_MPH:
            self.ctx.say("Come to a complete stop first.")
            return
        self._open_poi_stop(stop)

    def _open_poi_stop(self, stop) -> None:
        # Secure the truck before handing off to the stop menu: zero the
        # throttle, apply the service brake, and set the parking brake. A truck
        # that rolled in just under the docking threshold (or idled in gear)
        # would otherwise keep creeping while the driver rests -- napping while
        # the rig drifts down the freeway. Mirrors the pickup/delivery arrivals.
        self.truck.throttle = 0.0
        self.truck.brake = 1.0
        self.truck.set_parking_brake()
        if self.trip.is_planned(stop):
            # Plan fulfilled; the stop menu announces itself.
            self.trip.planned_stop_name = None
        can_sleep = "sleep" in stop.actions
        if can_sleep and hos.parking_is_full(self.trip_seed, stop.at_mi, self.trip.local_hour):
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
            self._cruise_exit_mph = None
            self.ctx.say("Exit canceled. Staying on the highway.")
            return
        stop = self._upcoming_exit_stop()
        if stop is None:
            self.ctx.say("No exit coming up. Exits are announced as you approach them.")
            return
        self._exit_stop = stop
        self.ctx.audio.play("ui/notify", volume=0.5)
        ahead = stop.at_mi - self.trip.position_mi
        if stop.type == "delivery_destination":
            labeled = getattr(stop, "exit_phrase", "") or stop.exit_label
            head = (
                # A labeled exit already names itself; don't repeat the
                # facility that the fallback phrase would have baked in.
                f"Signaling for {labeled}, destination exit for {stop.name},"
                if labeled
                else f"Signaling for the destination exit for {stop.name},"
            )
        elif stop.exit_label:
            head = f"Signaling for {stop.exit_label}, {stop.spoken_name},"
        else:
            head = f"Signaling for the {stop.spoken_name} exit,"
        self.ctx.say(
            f"{head} {ahead:.1f} miles ahead. Slow to "
            f"{self.ctx.settings.speed_text(RAMP_MAX_MPH)} or less for the ramp."
            + self._cap_cruise_for_ramp()
        )

    def _cap_cruise_for_ramp(self) -> str:
        """Bring automatic speed control down to ramp speed for an armed exit.

        Arming an exit commits the truck to leaving the highway, so the cruise
        target has to come down with it. Otherwise automatic control holds
        highway speed straight through the gore point and the driver loses the
        exit without ever touching a control. Returns the spoken addition, or
        an empty string when there is nothing to say.
        """
        if self._cruise_mph is None:
            # Paused mid-session -- a zone keeper, or a planned-stop pause.
            # Remember the cap so cruise resumes at ramp speed, but say
            # nothing: the keeper is already holding a low zone speed.
            if self._speed_control_armed and self._speed_control_target_mph is not None:
                self._cruise_exit_mph = min(self._speed_control_target_mph, RAMP_MAX_MPH)
            return ""
        self._cruise_exit_mph = min(self._cruise_mph, RAMP_MAX_MPH)
        action = "easing to" if self.truck.speed_mph > self._cruise_exit_mph + 1.0 else "holding"
        return (
            f" Adaptive cruise {action} "
            f"{self.ctx.settings.speed_text(self._cruise_exit_mph)} for the ramp."
        )

    def _exit_window_mi(self) -> float:
        """Arming and announcement window for exits, scaled like zone warnings.

        At speed under time compression a fixed window shrinks to nothing in
        real terms -- at 74 mph on fast pacing, 5 miles is about 7 real
        seconds, not enough to hear the callout, arm the exit, and brake to
        ramp speed. Scale the window so it covers roughly
        ``EXIT_WARNING_REAL_S`` of real time at the current pace.
        """
        speed = max(self.truck.speed_mph, 30.0)
        miles = EXIT_WARNING_REAL_S * speed * self.trip.effective_time_scale / 3600.0
        return max(EXIT_WINDOW_MI, min(miles, EXIT_WINDOW_MAX_MI))

    def _upcoming_exit_stop(self):
        window = self._exit_window_mi()
        stop = self.trip.upcoming_stop(window)
        destination = self._destination_exit_stop()
        if destination is None:
            return stop
        ahead = destination.at_mi - self.trip.position_mi
        if not (0 <= ahead <= window):
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
        labeled = getattr(stop, "exit_phrase", "") or stop.exit_label
        distance = f"{ahead:.0f} miles" if round(ahead) != 1 else "1 mile"
        core = (
            f"In {distance}, {labeled}, destination exit."
            if labeled
            else f"In {distance}, the destination exit for {stop.name}."
        )
        if self._terse_speech():
            return core
        return f"{core} Press {self.ctx.control_hint('take_exit')} to take it."

    def _check_destination_exit(self) -> None:
        stop = self._destination_exit_stop()
        if stop is None:
            return
        ahead = stop.at_mi - self.trip.position_mi
        if not (0 < ahead <= self._exit_window_mi()):
            return
        key = self._destination_exit_key(stop)
        if key == self._destination_exit_announced_key:
            return
        self._destination_exit_announced_key = key
        message = self._destination_exit_announcement(stop, ahead) + self._cap_cruise_for_ramp()
        self.ctx.audio.play("ui/notify", volume=0.7)
        self.ctx.say_event(message, interrupt=True)

    def _destination_exit_details(
        self, *, include_past: bool = False
    ) -> tuple[float, str, str] | None:
        if include_past:
            return self._scan_destination_exit_details(include_past=True)
        # This runs every frame from _check_destination_exit, and the scan
        # walks every interchange on the route building spoken phrases -- far
        # too much churn to redo per tick on a coast-to-coast route. The
        # winning exit only changes when the truck passes it, so reuse the
        # last answer until then. A backward position move (missed-exit
        # rewind, rescue) invalidates the cache wholesale, because exits
        # behind the compute position come back into play.
        pos = self.trip.position_mi
        cache = self._destination_exit_cache
        if cache is None or pos < cache[0] or (cache[1] is not None and cache[1][0] <= pos + 0.05):
            cache = (pos, self._scan_destination_exit_details())
            self._destination_exit_cache = cache
        return cache[1]

    def _scan_destination_exit_details(
        self, *, include_past: bool = False
    ) -> tuple[float, str, str] | None:
        if not self.route.legs:
            return None
        # Matched against real interchange sign text, so compare the spoken
        # city name ("Nashville"), never the slug key.
        destination = self.ctx.world.spoken_city(self.route.cities[-1], qualified=False).casefold()
        scan_floor = self.trip.total_miles - DESTINATION_EXIT_SCAN_WINDOW_MI
        candidates = []
        for i in range(len(self.route.legs) - 1, -1, -1):
            leg = self.route.legs[i]
            if self.trip._leg_starts[i] + leg.miles < scan_floor:
                # This leg ends before the final approach; every earlier leg
                # is farther out still.
                break
            forward = self.route.cities[i] == leg.a
            target = leg.miles if forward else 0.0
            for ix in leg.interchanges:
                if not ix.exit_label:
                    continue
                offset = ix.at_mi if forward else leg.miles - ix.at_mi
                route_mile = self.trip._leg_starts[i] + offset
                if route_mile < scan_floor:
                    continue
                if not include_past and route_mile <= self.trip.position_mi + 0.05:
                    continue
                dist_from_destination = abs(ix.at_mi - target)
                matches_destination = any(
                    destination in part.casefold() for part in ix.destinations
                )
                candidates.append(
                    (
                        len(self.route.legs) - 1 - i,
                        dist_from_destination,
                        not matches_destination,
                        route_mile,
                        ix.exit_label,
                        ix.spoken_phrase,
                    )
                )
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
                    self.trip.position_mi = self.trip.total_miles
                    self.trip.finished = True
                    self._open_facility_arrival()
                else:
                    self._open_poi_stop(stop)
                return
            stop = self._ramp_stop
            # Rolled clear past the end of the ramp without ever stopping. A
            # destination exit keeps waiting (missing it drives its own reroute);
            # a route POI is blown, so give the highway back instead of leaving a
            # stuck, unpatrolled ramp lingering for miles.
            if stop.type != "delivery_destination" and self._ramp_mi <= -RAMP_OVERSHOOT_MI:
                self._ramp_mi = None
                self._ramp_stop = None
                self._ramp_end_said = False
                planned = self.trip.is_planned(stop)
                if planned:
                    self.trip.planned_stop_name = None
                exit_ref = (
                    f"{stop.exit_label} for {stop.spoken_name}"
                    if stop.exit_label
                    else f"the exit for {stop.spoken_name}"
                )
                line = (
                    f"Drove past {stop.spoken_name}; you never stopped."
                    if self._terse_speech()
                    else f"You never stopped and drove past {exit_ref}."
                )
                if planned:
                    line += " Plan cancelled."
                self.ctx.say_event(line, interrupt=True)
                return
            if not self._ramp_end_said:
                self._ramp_end_said = True
                place = (
                    self._ramp_stop.name
                    if self._ramp_stop.type == "delivery_destination"
                    else self._ramp_stop.spoken_name
                )
                message = (
                    f"At {place}."
                    if self._terse_speech()
                    else f"You are at {place}. Come to a complete stop."
                )
                self.ctx.say_event(message, interrupt=True)
            return
        stop = self._exit_stop
        if stop is None or self.trip.position_mi < stop.at_mi:
            return
        self._exit_stop = None
        # The exit is settled either way now, so the ramp cap comes off: taking
        # it cancels cruise outright, and missing it must not leave automatic
        # control crawling at ramp speed down the open highway.
        self._cruise_exit_mph = None
        if self.truck.speed_mph <= RAMP_MAX_MPH:
            self._ramp_mi = RAMP_LENGTH_MI
            self._ramp_stop = stop
            self._ramp_end_said = False
            self._destination_exit_taken = stop.type == "delivery_destination"
            self._cancel_cruise()
            self._cancel_keeper()
            self.ctx.audio.play("ui/notify", volume=0.7)
            if stop.type == "delivery_destination":
                labeled = getattr(stop, "exit_phrase", "") or stop.exit_label
                take = (
                    f"You take {labeled}, destination exit for {stop.name}."
                    if labeled
                    else f"You take the destination exit for {stop.name}."
                )
            else:
                take = (
                    f"You take {stop.exit_label} for {stop.spoken_name}."
                    if stop.exit_label
                    else f"You take the exit for {stop.spoken_name}."
                )
            message = (
                f"{take} Half a mile of ramp."
                if self._terse_speech()
                else f"{take} Half a mile of ramp; brake to a stop at the end."
            )
            self.ctx.say_event(message, interrupt=True)
        else:
            if stop.type == "delivery_destination":
                # The exit phrase already carries its own label; naming both
                # would speak the same exit twice in one sentence.
                missed = self._destination_exit_phrase(stop)
            elif stop.exit_label:
                missed = f"{stop.exit_label} for {stop.spoken_name}"
            else:
                missed = f"the exit for {stop.spoken_name}"
            line = f"You were going too fast for the ramp and missed {missed}."
            if self.trip.is_planned(stop):
                # Fold the plan cancellation into this one line so the driver
                # hears a single cue, and clear it here so _check_stops doesn't
                # also emit a "drove past your planned stop" warning next tick.
                self.trip.planned_stop_name = None
                line += " Plan cancelled."
            self.ctx.say_event(line, interrupt=True)

    def _toggle_cruise(self) -> None:
        t = self.truck
        if (
            self._speed_control_armed
            or self._keeper_mph is not None
            or self._cruise_mph is not None
        ):
            self._disarm_speed_control()
            self.ctx.say("Automatic speed control off.")
            return
        limit, zone_reason = self.trip.speed_limit_at(self.trip.position_mi)
        if zone_reason is not None:
            # Adaptive cruise never runs on facility access roads, gates, work
            # zones, or heavy traffic. The speed keeper covers those low-speed
            # stretches instead, so nobody has to hold the accelerator down.
            self._engage_keeper(limit, zone_reason)
            return
        if not t.engine_on or t.speed_mph < CRUISE_MIN_MPH:
            self.ctx.say(
                "Adaptive cruise needs the engine running and at "
                f"least {self.ctx.settings.speed_text(CRUISE_MIN_MPH)}."
            )
            return
        self._engage_cruise(t.speed_mph)

    def _engage_cruise(self, target_mph: float, *, transition: bool = False) -> None:
        """Start adaptive cruise as part of the armed speed-control session."""
        t = self.truck
        self._speed_control_armed = True
        self._cruise_mph = max(CRUISE_MIN_MPH, min(CRUISE_MAX_MPH, target_mph))
        self._speed_control_target_mph = self._cruise_mph
        self._cruise_throttle = t.throttle
        self._cruise_applied = t.throttle
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False
        gap = self._acc_gap_seconds()
        effective_mph = (
            min(self._cruise_mph, self._cruise_exit_mph)
            if self._cruise_exit_mph is not None
            else self._cruise_mph
        )
        exit_note = " for the ramp" if self._cruise_exit_mph is not None else ""
        self.ctx.audio.play("ui/notify", volume=0.5)
        message = (
            f"Adaptive cruise {'resuming' if transition else 'set'} at "
            f"{self.ctx.settings.speed_text(effective_mph)}{exit_note}. "
            f"Following gap {gap:.0f} seconds. K or braking cancels."
        )
        if transition:
            self.ctx.say_event(f"Open road. {message}", interrupt=False)
        else:
            self.ctx.say(message)

    def _adjust_cruise(self, delta_mph: float) -> None:
        """Raise or lower the cruise set point -- the Accel/Coast (+/-) buttons.

        While the speed keeper is handling a restricted zone, the same buttons
        adjust the open-road target that adaptive cruise will resume."""
        if self._cruise_mph is None and self._keeper_mph is None:
            self.ctx.say("Adaptive cruise is off. Press K to set it first.")
            return
        base = self._speed_control_target_mph
        if base is None:
            limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
            base = max(CRUISE_MIN_MPH, limit)
        target = max(CRUISE_MIN_MPH, min(CRUISE_MAX_MPH, base + delta_mph))
        self._speed_control_target_mph = target
        if self._cruise_mph is not None:
            self._cruise_mph = target
            if self._cruise_exit_mph is not None:
                ramp_target = min(target, self._cruise_exit_mph)
                self.ctx.say(
                    f"Open-road cruise target {self.ctx.settings.speed_text(target)}. "
                    "Ramp approach target "
                    f"{self.ctx.settings.speed_text(ramp_target)}."
                )
            else:
                self.ctx.say(f"Adaptive cruise {self.ctx.settings.speed_text(target)}.")
        else:
            self.ctx.say(f"Open-road cruise target {self.ctx.settings.speed_text(target)}.")

    def _engage_keeper(
        self,
        limit_mph: float,
        zone_reason: str,
        *,
        target_mph: float | None = None,
        announce: bool = True,
    ) -> None:
        """Hold the current speed through a low-speed zone (K in a zone).

        An input-accessibility aid: facility access roads, gate queues, work
        zones, and congestion otherwise demand a continuously held accelerator,
        which some players cannot sustain. The keeper caps at the zone's limit,
        follows queued traffic, and hands back on any brake input.
        """
        t = self.truck
        if not self.ctx.settings.speed_keeper:
            self.ctx.say(f"Adaptive cruise is not available in a {zone_reason} zone.")
            return
        if not t.engine_on or (target_mph is None and t.speed_mph < KEEPER_MIN_MPH):
            self.ctx.say("The speed keeper needs the engine running and the truck rolling.")
            return
        self._speed_control_armed = True
        self._keeper_mph = min(t.speed_mph if target_mph is None else target_mph, limit_mph)
        self._keeper_zone = zone_reason
        self._keeper_throttle = t.throttle
        if announce:
            self.ctx.audio.play("ui/notify", volume=0.5)
            self.ctx.say(
                f"Automatic speed control on. Speed keeper holding "
                f"{self.ctx.settings.speed_text(self._keeper_mph)} through the "
                f"{zone_reason} zone. K or braking cancels."
            )

    def _update_keeper(
        self, dt: float, braking: bool, accelerating: bool, clutch_disengaged: bool
    ) -> None:
        """Hold a gentle low-speed target while the zone lasts."""
        if self._keeper_mph is None:
            return
        t = self.truck
        if braking or t.emergency_brake or t.air_brakes_holding or not t.engine_on or t.stalled:
            self._cancel_keeper()
            self.ctx.say_event(
                "Speed keeper canceled; automatic speed control off.", interrupt=False
            )
            return
        if accelerating:
            return  # manual override; the keeper resumes when the key lifts
        if clutch_disengaged:
            t.throttle = 0.0
            return
        limit, zone_reason = self.trip.speed_limit_at(self.trip.position_mi)
        if zone_reason is None:
            target_mph = self._speed_control_target_mph or limit
            self._cancel_keeper(preserve_session=True)
            self._engage_cruise(target_mph, transition=True)
            return
        self._keeper_zone = zone_reason
        target_mph = min(self._keeper_mph, limit)
        context = self.trip.traffic_context()
        if context is not None and (
            context.gap_seconds <= KEEPER_GAP_SECONDS or context.lead.speed_mph < target_mph
        ):
            # Creep along with the queue, all the way down to a stop, and roll
            # again when it moves -- gates and work zones are queue country.
            target_mph = min(target_mph, context.lead.speed_mph)
        error = target_mph - t.speed_mph
        self._keeper_throttle = max(
            0.0, min(KEEPER_MAX_THROTTLE, self._keeper_throttle + error * 0.1 * dt)
        )
        t.throttle = self._keeper_throttle
        if error < -1.5:
            t.brake = max(t.brake, min(0.4, abs(error) / 15.0))

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

    def _acc_limit_lookahead_mi(self, speed_mph: float, target_mph: float) -> float:
        """Distance ACC needs to ease down to a specific lower limit."""
        speed_mps = max(0.0, speed_mph * 0.44704)
        target_mps = max(0.0, target_mph * 0.44704)
        if target_mps >= speed_mps:
            return ACC_LIMIT_LOOKAHEAD_MIN_MI
        braking_m = (speed_mps * speed_mps - target_mps * target_mps) / (
            2.0 * ACC_LIMIT_COMFORT_DECEL_MPS2
        )
        braking_mi = max(0.0, braking_m / 1609.344)
        return max(ACC_LIMIT_LOOKAHEAD_MIN_MI, min(ACC_LIMIT_LOOKAHEAD_MAX_MI, braking_mi + 0.25))

    def _acc_posted_limit_ahead(self) -> tuple[float, str | None]:
        """Lowest posted limit close enough that ACC should start slowing now."""
        start = self.trip.position_mi
        end = min(self.trip.total_miles, start + ACC_LIMIT_LOOKAHEAD_MAX_MI)
        lowest_limit, lowest_reason = self.trip.speed_limit_at(start)
        probe = start + ACC_LIMIT_LOOKAHEAD_STEP_MI
        while probe <= end + 1e-6:
            limit, reason = self.trip.speed_limit_at(probe)
            cap_mph = limit + ACC_LIMIT_OFFSET_MPH
            braking_mi = self._acc_limit_lookahead_mi(self.truck.speed_mph, cap_mph)
            if limit < lowest_limit and probe - start <= braking_mi:
                lowest_limit, lowest_reason = limit, reason
            probe += ACC_LIMIT_LOOKAHEAD_STEP_MI
        return lowest_limit, lowest_reason

    def _update_cruise(
        self, dt: float, braking: bool, accelerating: bool, clutch_disengaged: bool
    ) -> None:
        """Hold speed when clear, and follow slower modeled traffic when present."""
        if self._cruise_mph is None:
            return
        t = self.truck
        if braking or t.emergency_brake or t.air_brakes_holding or not t.engine_on or t.stalled:
            self._cancel_cruise()
            self.ctx.say_event(
                "Adaptive cruise canceled; automatic speed control off.", interrupt=False
            )
            return
        limit, zone_reason = self.trip.speed_limit_at(self.trip.position_mi)
        if zone_reason is not None and self._speed_control_armed and self.ctx.settings.speed_keeper:
            self._cancel_cruise(preserve_session=True)
            self._engage_keeper(limit, zone_reason, target_mph=limit, announce=False)
            self.ctx.say_event(
                f"{zone_reason.title()} zone. Speed keeper holding "
                f"{self.ctx.settings.speed_text(self._keeper_mph)}.",
                interrupt=False,
            )
            return
        if accelerating:
            return  # manual override; cruise resumes when the key lifts
        if clutch_disengaged:
            # Clutch in / mid-shift: driveline is open, so any applied throttle
            # only free-revs the engine. Cut throttle to idle and hold the
            # integrator; the applied throttle ramps back up from zero once the
            # clutch engages again.
            t.throttle = 0.0
            self._cruise_applied = 0.0
            return
        target_mph = self._cruise_mph
        exit_capped = self._cruise_exit_mph is not None and self._cruise_exit_mph < target_mph
        if exit_capped:
            target_mph = self._cruise_exit_mph
        # Predictive ACC: never carry the driver past the posted limit. With real
        # OSM limits baked per leg, a held set speed would otherwise sail through
        # urban drops and corridor limit changes straight into speeding strikes,
        # tickets, and trooper stops -- all of which now exist. The "Speed limit X"
        # cue still names the number; this cue says cruise is handling it.
        posted, _ = self._acc_posted_limit_ahead()
        cap_mph = posted + ACC_LIMIT_OFFSET_MPH
        limit_capped = cap_mph < self._cruise_mph
        if limit_capped:
            # Take the lower of the two caps. A posted limit above ramp speed
            # must not undo an armed exit's cap and send the truck past its
            # ramp at the corridor limit.
            target_mph = min(target_mph, cap_mph)
            if not self._acc_limit_capped:
                self.ctx.say_event(
                    "Posted limit lower; adaptive cruise easing to "
                    f"{self.ctx.settings.speed_text(cap_mph)}.",
                    interrupt=False,
                )
        self._acc_limit_capped = limit_capped
        context = self.trip.traffic_context()
        following = False
        if context is not None:
            desired_gap = self._acc_gap_seconds()
            reason = self._acc_weather_gap_text()
            if (
                reason
                and not self._acc_weather_gap_said
                and context.gap_seconds <= desired_gap + 1.5
            ):
                self._acc_weather_gap_said = True
                self.ctx.say_event(reason, interrupt=False)
            if context.gap_seconds <= desired_gap + 1.0 or context.lead.speed_mph < target_mph:
                target_mph = min(target_mph, context.lead.speed_mph)
                following = True
        if following and not self._acc_following:
            self.ctx.audio.play("ui/notify", volume=0.55)
            self.ctx.say_event("Traffic ahead, adaptive cruise reducing speed.", interrupt=False)
        self._acc_following = following
        error = target_mph - t.speed_mph
        self._cruise_throttle = max(0.0, min(1.0, self._cruise_throttle + error * 0.08 * dt))
        # Ramp the applied throttle up to the held integrator value rather than
        # snapping, so cruise eases back in after a clutch release; drops (traffic
        # or a lower limit) still apply immediately. On a steady frame the applied
        # throttle already equals _cruise_throttle, so this holds as before.
        if self._cruise_throttle > self._cruise_applied:
            load_fraction = min(1.0, max(0.0, t.cargo_kg / REFERENCE_CARGO_KG))
            recovery_rate = 0.7 + 0.8 * (1.0 - load_fraction)
            recovery_rate += min(0.6, max(0.0, error) / 15.0)
            self._cruise_applied = min(
                self._cruise_throttle,
                self._cruise_applied + dt * recovery_rate,
            )
        else:
            self._cruise_applied = self._cruise_throttle
        t.throttle = self._cruise_applied
        if (following or limit_capped or exit_capped) and error < -2.0:
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
        self.ctx.say_event(
            f"You ran out of fuel. Roadside rescue brought thirty "
            f"gallons for {fee:,.0f} dollars. Press "
            f"{self.ctx.control_hint('engine')} to restart "
            "the engine, and plan your fuel stops.",
            interrupt=True,
        )

    def _arrive(self) -> None:
        self.ctx.replace_state(ArrivalState(self.ctx, self))

    def _handle_missed_destination_exit(self) -> None:
        exit_details = self._destination_exit_details(include_past=True)
        self.trip.finished = False
        self._exit_stop = None
        self._cancel_cruise()
        if exit_details is None:
            # With no exit to loop back to, say the recovery instruction once
            # instead of repeating it every frame.
            if self._missed_destination_exit_said:
                return
            self._missed_destination_exit_said = True
        reroute_text = (
            "Continue to the next safe turnaround. Dispatch reroutes you back "
            "onto the approach; take the destination exit when it comes up."
        )
        if exit_details is not None:
            # Every miss must reposition the trip. The old say-once guard
            # swallowed a second miss and left the truck stuck at zero miles.
            self._missed_destination_exit_said = True
            self.trip.game_minutes += 20.0
            self.trip.position_mi = max(0.0, exit_details[0] - self._exit_window_mi())
            self._destination_exit_announced_key = None
            if self._terse_speech():
                reroute_text = "Safe turnaround. Destination exit ahead again."
            else:
                reroute_text = (
                    "You continue to the next safe turnaround and loop back onto "
                    "the approach. The destination exit is ahead again; press "
                    f"{self.ctx.control_hint('take_exit')} "
                    "when you are close enough to take it."
                )
        self.ctx.audio.play("ui/warning")
        self._set_status("Destination exit missed. Use the next safe turnaround.")
        self.ctx.say_event(
            f"You missed the destination exit for {self._destination_facility_text()}. "
            f"{reroute_text}",
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
        message = (
            f"Destination ahead: {self._destination_facility_text()}."
            if self._terse_speech()
            else (
                f"Destination ahead: {self._destination_facility_text()}. "
                "Slow down and come to a complete stop at the gate."
            )
        )
        self.ctx.say_event(message, interrupt=True)

    def _handle_arrival_creep(self) -> None:
        if self._arrival_full_stop_said:
            return
        self._arrival_full_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/notify", volume=0.7)
        self._set_status("Destination gate: stop to dock.")
        self.ctx.say_event(
            f"At {self._destination_facility_text()}. Stop to dock.", interrupt=False
        )

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
            origin=self.job.spoken_origin,
            destination=self.job.spoken_destination,
            cargo=self.job.cargo.label,
            fraction=fraction,
            moving=moving,
            truck_label=truck.label if truck else "",
        )

    def online_presence(self):
        return self.presence()

    def lines(self) -> list[str]:
        t = self.truck
        limit, reason = self.trip.speed_limit_at(self.trip.position_mi)
        gear = "N" if t.transmission.in_neutral else str(t.transmission.gear)
        title = (
            f"Deadheading to pickup at {self._pickup_facility_text()}"
            if self.phase == DRIVE_PHASE_PICKUP
            else f"Driving loaded to {self.job.spoken_destination}"
        )
        remaining = (
            f"{self.trip.remaining_miles:.1f} of {self.trip.total_miles:.1f} miles"
            if self.phase == DRIVE_PHASE_PICKUP
            else f"{self.trip.remaining_miles:.0f} of {self.trip.total_miles:.0f} miles"
        )
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
            f"Clock: {clock_text(self.trip.local_hour)} "
            f"{self.trip.current_timezone.name} "
            f"({time_of_day(self.trip.local_hour)})   "
            f"Fatigue: {self.ctx.profile.fatigue:.0f}%",
            "",
            self._status_text,
        ]
