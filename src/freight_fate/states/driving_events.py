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
        self._ambient_event_cooldown_s = tuning_for_time_scale(
            self.trip.time_scale
        ).ambient_spacing_s

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
        if self._should_ignore_destination_exit_gps_cue(event):
            return
        if self._should_ignore_untaken_destination_facility_event(event):
            return
        kind = event.kind
        sound = _route_event_sound(event)
        if kind in (TripEventKind.LANDMARK, TripEventKind.BILLBOARD):
            # Ambient roadside color, filtered by the player's chatter
            # switches at speak time so a mid-trip settings change applies
            # immediately. Terse speech mutes all of it; a muted callout is
            # dropped whole -- it never becomes the A-key replay either.
            category = str(event.data.get("category", ""))
            if self._terse_speech() or not self.ctx.settings.chatter_enabled(category):
                return
        if event.message:
            self._last_event_message = event.message  # replayable with A
        if kind == TripEventKind.HAZARD:
            if self._ramp_mi is not None:
                return  # off the highway: the hazard passes you by
            if self._cruise_mph is not None:
                self._cancel_cruise()  # hands back on the wheel to brake
            if self._keeper_mph is not None:
                self._cancel_keeper()  # same: the hazard call says brake
            self._pending_ambient_event = None
            self.ctx.audio.play(sound or "ui/warning")
            self.ctx.controller.rumble.hazard()  # 750 ms right->left sweep
            # The deadline is braking physics plus reaction slack. The physics
            # part is whatever full service brakes need from the current speed
            # on this surface; the rolled window covers hearing the warning and
            # getting on the pedal, and fatigue eats into that part only --
            # a drowsy driver reacts late, but the truck stops no slower.
            slack = event.data.get("deadline_s", 4.0)
            reaction = tuning_for_time_scale(self.trip.time_scale).reaction_window
            self._hazard_deadline = self._brake_budget_s() + slack * reaction * (
                hos.reaction_window_mult(self.ctx.profile.fatigue)
            )
            # A dodgeable hazard sits in the lane you are in *now*; ending up
            # in any other lane before the deadline clears it, if that lane
            # is actually open. See _finish_lane_change.
            self._hazard_dodgeable = bool(event.data.get("dodgeable", False))
            self._hazard_lane = self.lane.lane
            self._automatic_braking_announced = False
            message = terse_hazard_message(event.message) if self._terse_speech() else event.message
            self.ctx.say_event(message, interrupt=True)
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
        elif kind == TripEventKind.TIMEZONE_CROSSING:
            if sound is not None:
                self.ctx.audio.play(sound)
            self.ctx.say_event(
                timezone_crossing_message(event, self._terse_speech()), interrupt=False
            )
        elif kind in (TripEventKind.LANDMARK, TripEventKind.BILLBOARD):
            self._speak_ambient_event(event.message)
        elif kind == TripEventKind.ARRIVED:
            pass  # handled by _arrive()
        elif self._event_disables_cruise(event):
            self._cancel_cruise_for_restricted_area(event.message)
        else:
            critical = self._is_critical_event(event)
            if critical:
                self._pending_ambient_event = None
                if sound is not None and kind != TripEventKind.ZONE_ENTER:
                    self.ctx.audio.play(sound, pan=_route_event_sound_pan(event))
                self.ctx.say_event(event.message, interrupt=True)
            elif self._should_space_ambient_event(event):
                self._speak_ambient_event(
                    event.message,
                    sound if kind != TripEventKind.ZONE_ENTER else None,
                )
            else:
                if sound is not None and kind != TripEventKind.ZONE_ENTER:
                    self.ctx.audio.play(sound, pan=_route_event_sound_pan(event))
                self.ctx.say_event(event.message, interrupt=False)
        if kind == TripEventKind.ZONE_ENTER:
            self.ctx.audio.play(sound or "ui/notify")
            zone = event.data.get("zone")
            if getattr(zone, "reason", "") == "construction":
                self.construction_seen = True
                self.ctx.award_achievement("construction_zone", event=True)
            elif getattr(zone, "reason", "") == "heavy traffic":
                self.traffic_seen = True
                self.ctx.award_achievement("traffic_slowing", event=True)
        if kind == TripEventKind.GPS_CUE:
            cue = event.data.get("cue")
            if (
                getattr(cue, "kind", "") == "traffic"
                or event.data.get("traffic_pressure") is not None
            ):
                self.traffic_seen = True
                self.ctx.award_achievement("traffic_slowing", event=True)
        if self.construction_seen and self.traffic_seen:
            self.ctx.award_achievement("jam_and_cones", event=True)

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
            _record_inspection(self.ctx, event=True)
            self._place_out_of_service()
            return
        self.ctx.say_event(message, interrupt=True)
        _record_inspection(self.ctx, event=True)

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

            self.ctx.push_state(
                TimedMessageState(
                    self.ctx,
                    title="Pulling into stop",
                    message=(
                        f"Pulling into {stop.spoken_name}. Brakes set; menu opening in a moment."
                    ),
                    status="Pulling into the route stop. Please wait.",
                    seconds=STOP_PULL_IN_WAIT_S,
                    on_complete=complete,
                    sound_key="ui/notify",
                )
            )
            return

        can_sleep = "sleep" in stop.actions
        if can_sleep and hos.parking_is_full(self.trip_seed, stop.at_mi, self.trip.local_hour):
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
                "No route exit to signal for yet. Exits are announced as you approach them."
            )
            return
        self._exit_stop = stop
        self._exit_signal_on = not self._exit_signal_on
        ahead = stop.at_mi - self.trip.position_mi
        if not self._exit_signal_on:
            self._exit_signal_canceled = True
            self.ctx.say("Signal canceled. Keep following the highway.")
            return
        self._exit_signal_canceled = False
        self.ctx.audio.play("vehicle/turn_signal", volume=0.7)
        if stop.type == "delivery_destination":
            labeled = getattr(stop, "exit_phrase", "") or stop.exit_label
            head = (
                # A labeled exit already names itself; don't repeat the
                # facility that the fallback phrase would have baked in.
                f"Signal on for {labeled}, destination exit for {stop.name},"
                if labeled
                else f"Signal on for the destination exit for {stop.name},"
            )
        elif stop.exit_label:
            head = f"Signal on for {stop.exit_label}, {stop.spoken_name},"
        else:
            head = f"Signal on for the {stop.spoken_name} exit,"
        lane_hint = "" if self.lane.lane == 0 else " Get into the right lane."
        if self.ctx.settings.steering_assist == "off":
            self._exit_lane_alignment = EXIT_LANE_READY
            self._exit_lane_ready_said = True
            self.ctx.audio.play("ui/notify", volume=0.6)
            self.ctx.say(
                f"{head} {ahead:.1f} miles ahead. Exit lane set.{lane_hint} "
                f"Slow to {RAMP_MAX_MPH:.0f} or less for the ramp."
            )
            return
        self.ctx.say(
            f"{head} {ahead:.1f} miles ahead.{lane_hint} "
            "Move right for the exit lane, then slow to "
            f"{RAMP_MAX_MPH:.0f} or less for the ramp."
        )

    def _reset_exit_lane_state(self) -> None:
        self._exit_lane_alignment = 0.0
        self._exit_lane_prompt_said = False
        self._exit_lane_ready_said = False
        self._exit_commit_said = False

    def _exit_lane_ready(self) -> bool:
        # Ramps peel off the right lane: no amount of in-lane alignment
        # helps from the left lane, and a change in progress toward the
        # right still counts as making the gore.
        if self.lane.lane != 0 and self._lane_change_target != 0:
            return False
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
        if not self._exit_signal_on:
            return
        ahead = stop.at_mi - self.trip.position_mi
        if self.ctx.settings.exit_speed_assist and 0 < ahead <= 1.5:
            if self._cruise_mph is not None:
                self._cancel_cruise()
            if self.truck.speed_mph > RAMP_MAX_MPH:
                self.truck.brake = max(self.truck.brake, 0.35)
                if not self._assist_exit_slowing_said:
                    self._assist_exit_slowing_said = True
                    self.ctx.say_event(
                        "Exit speed assistance slowing. Confirm the exit when ready.",
                        interrupt=False,
                    )
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
            self._exit_lane_alignment = max(self._exit_lane_alignment, EXIT_LANE_READY)
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
                if pressure is not None and pressure.intensity >= 0.35
                else ""
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
                f"At the exit gore. Hold the exit lane and stay under {RAMP_MAX_MPH:.0f}.",
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

    def _exit_window_mi(self) -> float:
        """Arming and announcement window for exits, scaled like zone warnings.

        At speed under time compression a fixed window shrinks to nothing in
        real terms -- at 74 mph on realistic pacing, 5 miles is about 7 real
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
        if self._departure_chain:
            # Still on the origin's streets: the end of the active trip is
            # the on-ramp merge, not the delivery exit.
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

    def _missed_exit_phrase(self, stop) -> str:
        if stop.type == "delivery_destination":
            # The exit phrase already carries its own label; naming both
            # would speak the same exit twice in one sentence.
            return self._destination_exit_phrase(stop)
        if stop.exit_label:
            return f"{stop.exit_label} for {stop.spoken_name}"
        return f"the exit for {stop.spoken_name}"

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
        lane_text = (
            "Slow down for the ramp."
            if self.ctx.settings.steering_assist == "off"
            else "Move right for the exit lane and slow down."
        )
        return f"{core} {lane_text}"

    def _check_destination_exit(self) -> None:
        stop = self._destination_exit_stop()
        if stop is None:
            return
        ahead = stop.at_mi - self.trip.position_mi
        if not (0 < ahead <= self._exit_window_mi()):
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
            self._exit_signal_canceled = False
            self._reset_exit_lane_state()
            if self.ctx.settings.steering_assist == "off":
                self._exit_lane_alignment = EXIT_LANE_READY
                self._exit_lane_ready_said = True

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

    def _exit_intent_ready(self, stop) -> bool:
        if self._exit_signal_canceled:
            return False
        if self._exit_signal_on:
            return True
        return stop.type == "delivery_destination" and self.ctx.settings.steering_assist == "off"

    def _surface_chain_route(self):
        """The destination facility's tier-1 street chain, or None.

        Only a genuine multi-segment turn-level route makes a chain; a
        single synthetic leg would just be the old teleport with extra
        steps, so those facilities keep the scripted arrival."""
        try:
            route = self.ctx.world.facility_approach_route(
                self.job.destination, self.job.destination_location
            )
        except (KeyError, ValueError):
            return None
        if route is None or len(route.legs) < 2:
            return None
        if not any(leg.local_speed_mph > 0 for leg in route.legs):
            return None
        return route

    def _begin_surface_chain(self, *, announce: bool = True) -> bool:
        """Swap the finished highway trip for the facility's street chain.

        The clock, the day of the week, and the toll ledger carry over, so
        deadlines, rush hour, and settlement are unaffected: only the road
        under the wheels changes."""
        if self._surface_chain:
            return False  # already on the streets
        route = self._surface_chain_route()
        if route is None:
            return False
        old = self.trip
        surface = Trip(
            route,
            self.truck,
            self.weather,
            time_scale=old.time_scale,
            seed=self.trip_seed ^ 0x5AFE,
            start_hour=old.start_hour,
            imperial=old.imperial,
            hazard_scale=0.0,  # no random hazards on the last city miles
            career_hours=old.career_hours,
        )
        surface.game_minutes = old.game_minutes  # deadline and clock continuity
        surface.toll_charges = old.toll_charges  # settlement reads the live trip
        surface.hos_violation = old.hos_violation
        self._highway_trip = old
        self.trip = surface
        self._surface_chain = True
        self._reset_exit_lane_state()
        self._exit_signal_on = False
        if announce:
            first = route.legs[0]
            street = first.local_cue.rstrip(".") if first.local_cue else f"Start on {first.highway}"
            self.ctx.audio.play("ui/notify", volume=0.7)
            self.ctx.say_event(
                f"Off the ramp and onto city streets: {street[:1].lower()}{street[1:]}. "
                f"{self.trip._distance_text(route.miles)} to the facility gate.",
                interrupt=False,
            )
        return True

    def _departure_chain_route(self):
        """The origin facility's street chain driven outbound, or None.

        Same bar as the arrival side: only a genuine multi-segment
        turn-level chain qualifies; other facilities keep the scripted
        departure straight onto the highway."""
        if self.phase != DRIVE_PHASE_DELIVERY:
            return None
        try:
            return self.ctx.world.facility_departure_route(
                self.job.origin, self.job.origin_location
            )
        except (AttributeError, KeyError, ValueError):
            return None

    def _begin_departure_chain(self, *, announce: bool = True) -> bool:
        """Start the loaded run on the origin facility's street chain.

        The full highway trip built at dispatch is parked aside; the truck
        pulls out of the gate onto real streets and the on-ramp merge hands
        the highway trip back with the clock and toll ledger intact."""
        if self._departure_chain or self._surface_chain:
            return False
        route = self._departure_chain_route()
        if route is None:
            return False
        highway = self.trip
        surface = Trip(
            route,
            self.truck,
            self.weather,
            time_scale=highway.time_scale,
            seed=self.trip_seed ^ 0xD00D,
            start_hour=highway.start_hour,
            imperial=highway.imperial,
            hazard_scale=0.0,  # no random hazards on the first city miles
            career_hours=highway.career_hours,
        )
        self._highway_trip = highway
        self.trip = surface
        self._departure_chain = True
        if announce:
            first = route.legs[0]
            street = first.local_cue.rstrip(".") if first.local_cue else f"Start on {first.highway}"
            merge_leg = highway.route.legs[0]
            self.ctx.say_event(
                f"Out of the gate and onto city streets: "
                f"{street[:1].lower()}{street[1:]}. "
                f"{surface._distance_text(route.miles)} to the "
                f"{merge_leg.highway} on-ramp.",
                interrupt=False,
            )
        return True

    def _finish_departure_chain(self) -> None:
        """End of the streets: up the on-ramp and onto the highway trip."""
        surface = self.trip
        highway = self._highway_trip
        highway.game_minutes = surface.game_minutes  # clock continuity
        highway.toll_charges = surface.toll_charges  # settlement reads the live trip
        highway.hos_violation = surface.hos_violation
        self.trip = highway
        self._highway_trip = None
        self._departure_chain = False
        # Coming up the ramp you are in the right lane, merging left.
        self.lane.lane = 0
        self.lane.offset = 0.0
        merge_leg = highway.route.legs[0]
        self.ctx.audio.play("vehicle/turn_signal", volume=0.6, pan=-0.6)
        self.ctx.say_event(
            f"Up the ramp and onto {merge_leg.highway}. Merge left when clear.",
            interrupt=False,
        )

    def _begin_ramp_terminal(self, stop) -> None:
        """Decide what controls the end of the ramp just taken.

        Baked OSM data (a traffic_signals or stop node on the exit's ramp
        links) wins; otherwise a seeded urban/rural heuristic stands in --
        most urban diamond terminals are signalized, rural ones lean to stop
        signs, and a share flow free like a cloverleaf loop."""
        rng = random.Random((self.trip_seed << 16) ^ int(stop.at_mi * 100.0))
        control = self.trip.ramp_control_at(stop.at_mi)
        if not control:
            signal_w, stop_w = (
                RAMP_CONTROL_URBAN_WEIGHTS
                if self.trip._near_city(stop.at_mi)
                else RAMP_CONTROL_RURAL_WEIGHTS
            )
            roll = rng.random()
            control = "signal" if roll < signal_w else "stop" if roll < stop_w else "none"
        self._ramp_control = control
        self._ramp_light_timer = 0.0
        self._ramp_light_offset_s = rng.random() * (RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S)
        self._ramp_light_announced = False
        self._ramp_light_was_red = False
        self._ramp_light_flip_said = False
        self._ramp_terminal_done = control == "none"
        self._ramp_waiting_at_light = False

    def _ramp_light_is_red(self) -> bool:
        cycle = RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S
        return (self._ramp_light_offset_s + self._ramp_light_timer) % cycle < RAMP_LIGHT_RED_S

    def _update_ramp_light(self, dt: float) -> None:
        """Advance the terminal light in real time and speak state changes."""
        if self._ramp_mi is None or self._ramp_control != "signal" or self._ramp_terminal_done:
            return
        self._ramp_light_timer += dt
        red = self._ramp_light_is_red()
        if not self._ramp_light_announced or red == self._ramp_light_was_red:
            return
        self._ramp_light_was_red = red
        if self._ramp_waiting_at_light and not red:
            # The wait at the stop bar ends; the driveway is just ahead.
            self._ramp_waiting_at_light = False
            self._ramp_terminal_done = True
            self.ctx.audio.play("events/ramp_light_green", volume=0.8)
            self.ctx.say_event("Green light. Pull ahead to the entrance.", interrupt=False)
            return
        # Speak at most one flip after the first callout: a slow descent can
        # span several signal cycles in real time, and the stop-bar exchange
        # announces the state that finally matters. One update is
        # information; a play-by-play of every cycle is chatter.
        if not self._ramp_light_flip_said:
            self._ramp_light_flip_said = True
            self.ctx.audio.play(
                "events/ramp_light_red" if red else "events/ramp_light_green",
                volume=0.7,
            )
            self.ctx.say_event(
                "The light ahead turns red. Be ready to stop."
                if red
                else "The light ahead turns green.",
                interrupt=False,
            )

    def _announce_ramp_terminal(self) -> None:
        """Mid-ramp callout naming the control at the terminal."""
        self._ramp_light_announced = True
        if self._ramp_control == "signal":
            red = self._ramp_light_is_red()
            self._ramp_light_was_red = red
            self.ctx.audio.play(
                "events/ramp_light_red" if red else "events/ramp_light_green",
                volume=0.8,
            )
            self.ctx.say_event(
                "Traffic light at the end of the ramp, currently red. Brake to a stop."
                if red
                else "Traffic light at the end of the ramp, currently green.",
                interrupt=False,
            )
        elif self._ramp_control == "stop":
            self.ctx.audio.play("ui/notify", volume=0.7)
            self.ctx.say_event(
                "Stop sign at the end of the ramp. Brake to a full stop there.",
                interrupt=False,
            )

    def _update_ramp_terminal(self) -> None:
        """Crossing the terminal: honor the light or the sign, or pay for it.

        A driver still braking gets the length of the grace distance past the
        bar to finish the stop; carrying speed beyond it commits the run."""
        speed = self.truck.speed_mph
        past_bar = self._ramp_mi is not None and (
            self._ramp_mi <= RAMP_ACCESS_MI - RAMP_TERMINAL_GRACE_MI
        )
        if self._ramp_control == "signal":
            if self._ramp_light_is_red():
                if speed <= RED_STOP_MPH:
                    if not self._ramp_waiting_at_light:
                        self._ramp_waiting_at_light = True
                        self.ctx.say_event(
                            "Stopped at the red light. Hold the brakes for green.",
                            interrupt=False,
                        )
                    return
                if not past_bar:
                    return  # still braking down to the stop bar
                self._ramp_terminal_done = True
                self._ramp_waiting_at_light = False
                if speed > STOP_ROLL_CLIP_MPH:
                    self.ctx.audio.play("traffic/car_pass", volume=1.0, pan=-0.4)
                    self.ctx.audio.play("vehicle/collision")
                    self.ctx.controller.rumble.impact(RED_RUN_DAMAGE)
                    self.truck.apply_collision(RED_RUN_DAMAGE)
                    self.ctx.say_event(
                        "You ran the red light at the ramp end and cross traffic "
                        "clipped the trailer! Total damage "
                        f"{self.truck.damage_pct:.0f} percent.",
                        interrupt=True,
                    )
                else:
                    self.ctx.audio.play("traffic/car_pass", volume=1.0, pan=-0.4)
                    self.ctx.say_event(
                        "You crept through the red light. Cross traffic leans on the horn.",
                        interrupt=True,
                    )
                return
            self._ramp_terminal_done = True
            self._ramp_waiting_at_light = False
            self.ctx.audio.play("events/ramp_light_green", volume=0.7)
            self.ctx.say_event(
                "Green light. Through the intersection; brake for the entrance."
                if speed <= GREEN_ROLL_MPH
                else "Through the green light, but far too fast. Brake hard for the entrance.",
                interrupt=False,
            )
            return
        if self._ramp_control == "stop":
            if speed > RED_STOP_MPH and not past_bar:
                return  # still braking down to the stop bar
            self._ramp_terminal_done = True
            if speed <= RED_STOP_MPH:
                self.ctx.say_event(
                    "Stopped at the sign. Clear; pull ahead to the entrance.",
                    interrupt=False,
                )
            elif speed > STOP_ROLL_CLIP_MPH:
                self.ctx.audio.play("traffic/car_pass", volume=1.0, pan=0.4)
                self.ctx.audio.play("vehicle/collision")
                self.ctx.controller.rumble.impact(STOP_ROLL_DAMAGE)
                self.truck.apply_collision(STOP_ROLL_DAMAGE)
                self.ctx.say_event(
                    "You blew the stop sign at the ramp end and clipped cross "
                    f"traffic! Total damage {self.truck.damage_pct:.0f} percent.",
                    interrupt=True,
                )
            else:
                self.ctx.audio.play("traffic/car_pass", volume=1.0, pan=0.4)
                self.ctx.say_event(
                    "You rolled the stop sign at the ramp end. Cross traffic leans on the horn.",
                    interrupt=True,
                )
            return
        self._ramp_terminal_done = True

    def _update_exit(self, moved_mi: float) -> None:
        """Advance an armed exit or an active ramp; opens the stop menu."""
        if self._ramp_mi is not None:
            self._ramp_mi -= moved_mi
            if not self._ramp_light_announced and self._ramp_mi <= RAMP_CONTROL_ANNOUNCE_MI:
                self._announce_ramp_terminal()
            if not self._ramp_terminal_done and self._ramp_mi <= RAMP_ACCESS_MI:
                self._update_ramp_terminal()
            if self._ramp_mi > 0:
                return
            if self.truck.speed_mph <= DOCKING_MAX_MPH:
                stop = self._ramp_stop
                self._ramp_mi = None
                self._ramp_stop = None
                self._ramp_control = ""
                if stop.type == "delivery_destination":
                    if self._begin_surface_chain():
                        return
                    self.trip.position_mi = self.trip.total_miles
                    self.trip.finished = True
                    self._open_facility_arrival()
                else:
                    self._open_poi_stop(stop, settle=True)
            elif not self._ramp_end_said:
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
        if self._exit_signal_canceled:
            self._reset_exit_lane_state()
            self._exit_signal_canceled = False
            self.ctx.say_event("Exit signal was canceled, so you stayed on the highway.")
            return
        self._exit_signal_canceled = False
        if self.trip.position_mi > stop.at_mi + EXIT_COMMIT_WINDOW_MI:
            self._reset_exit_lane_state()
            self._exit_signal_on = False
            pressure = self._active_exit_pressure(stop)
            if pressure is not None and pressure.intensity >= 0.35:
                self.ctx.say_event(
                    "You missed the exit window in heavy traffic and stayed on the highway."
                )
            else:
                self.ctx.say_event("You missed the exit window and stayed on the highway.")
            return
        if not self._exit_intent_ready(stop):
            self._reset_exit_lane_state()
            self._exit_signal_on = False
            place = self._missed_exit_phrase(stop)
            self.ctx.say_event(
                f"You missed {place}: the turn signal was not set. "
                "Stay on the highway and recover at the next safe exit."
            )
            return
        if not self._exit_lane_ready():
            self._reset_exit_lane_state()
            self._exit_signal_on = False
            missed = self._missed_exit_phrase(stop)
            pressure = self._active_exit_pressure(stop)
            if pressure is not None:
                self.ctx.say_event(
                    "Traffic boxed you out of the exit lane at the gore, so "
                    f"you missed {missed}. Stay on the highway and "
                    "recover at the next safe exit."
                )
            else:
                self.ctx.say_event(
                    f"You missed {missed}: you were not in the "
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
            # The ramp is a single lane peeling off the right side.
            self.lane.lane = 0
            self.lane.offset = 0.0
            self._lane_change_target = None
            self._merge_deadline = None
            self._begin_ramp_terminal(stop)
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
            if self._terse_speech():
                terminal = {
                    "signal": " Traffic light at the end.",
                    "stop": " Stop sign at the end.",
                }.get(self._ramp_control, "")
                message = f"{take} Half a mile of ramp.{terminal}"
            else:
                ending = {
                    "signal": "traffic light at the end, then brake to a stop at the entrance",
                    "stop": "stop sign at the end, then brake to a stop at the entrance",
                }.get(self._ramp_control, "brake to a stop at the end")
                message = f"{take} Half a mile of ramp; {ending}."
            self.ctx.say_event(message, interrupt=True)
        else:
            missed = self._missed_exit_phrase(stop)
            self.ctx.say_event(
                f"You were going too fast for the ramp and missed {missed}.",
                interrupt=True,
            )
            self._exit_signal_on = False
            self._reset_exit_lane_state()

    def _toggle_cruise(self) -> None:
        t = self.truck
        if self._keeper_mph is not None:
            self._cancel_keeper()
            self.ctx.say("Speed keeper off.")
            return
        if self._cruise_mph is not None:
            self._cancel_cruise()
            self.ctx.say("Adaptive cruise off.")
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
        self._cruise_mph = t.speed_mph
        self._cruise_throttle = t.throttle
        self._cruise_applied = t.throttle
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False
        gap = self._acc_gap_seconds()
        self.ctx.audio.play("ui/notify", volume=0.5)
        self.ctx.say(
            "Adaptive cruise set at "
            f"{self.ctx.settings.speed_text(t.speed_mph)}. "
            f"Following gap {gap:.0f} seconds. "
            "K or braking cancels."
        )

    def _adjust_cruise(self, delta_mph: float) -> None:
        """Raise or lower the cruise set point -- the Accel/Coast (+/-) buttons.

        Only while cruise is engaged: the truck then accelerates up to a higher
        set point or eases down to a lower one, still capped at the posted limit
        plus the offset. So you engage once rolling, then dial the target up to
        the speed you want without having to reach it manually first."""
        if self._cruise_mph is None:
            self.ctx.say("Adaptive cruise is off. Press K to set it first.")
            return
        self._cruise_mph = max(CRUISE_MIN_MPH, min(CRUISE_MAX_MPH, self._cruise_mph + delta_mph))
        self.ctx.say(f"Adaptive cruise {self.ctx.settings.speed_text(self._cruise_mph)}.")

    def _cancel_cruise(self) -> None:
        self._cruise_mph = None
        self._cruise_throttle = 0.0
        self._cruise_applied = 0.0
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False
        self._descent_control_active = False

    def _engage_keeper(self, limit_mph: float, zone_reason: str) -> None:
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
        if not t.engine_on or t.speed_mph < KEEPER_MIN_MPH:
            self.ctx.say("The speed keeper needs the engine running and the truck rolling.")
            return
        self._keeper_mph = min(t.speed_mph, limit_mph)
        self._keeper_zone = zone_reason
        self._keeper_throttle = t.throttle
        self.ctx.audio.play("ui/notify", volume=0.5)
        self.ctx.say(
            f"Speed keeper holding {self.ctx.settings.speed_text(self._keeper_mph)} "
            f"through the {zone_reason} zone. K or braking cancels."
        )

    def _cancel_keeper(self) -> None:
        self._keeper_mph = None
        self._keeper_throttle = 0.0
        self._keeper_zone = ""

    def _update_keeper(
        self, dt: float, braking: bool, accelerating: bool, clutch_disengaged: bool
    ) -> None:
        """Hold a gentle low-speed target while the zone lasts."""
        if self._keeper_mph is None:
            return
        t = self.truck
        if braking or t.emergency_brake or t.air_brakes_holding or not t.engine_on or t.stalled:
            self._cancel_keeper()
            self.ctx.say_event("Speed keeper canceled.", interrupt=False)
            return
        if accelerating:
            return  # manual override; the keeper resumes when the key lifts
        if clutch_disengaged:
            t.throttle = 0.0
            return
        limit, zone_reason = self.trip.speed_limit_at(self.trip.position_mi)
        if zone_reason is None:
            # Back on the open road: hand control back rather than creeping
            # along at zone speed, and point at adaptive cruise for the rest.
            self._cancel_keeper()
            self.ctx.say_event(
                "Speed keeper released; open road ahead. Press K at road "
                "speed for adaptive cruise.",
                interrupt=False,
            )
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
        descent_level = self.ctx.settings.descent_speed_control
        descending = t.grade <= -0.025 and descent_level != "off"
        if descending and self._cruise_mph is not None:
            if braking and descent_level in ("balanced", "interactive"):
                self._descent_control_active = True
                new_target = max(CRUISE_MIN_MPH, t.speed_mph)
                should_announce = (
                    not self._descent_capture_active or abs(new_target - self._cruise_mph) >= 2.0
                )
                self._descent_capture_active = True
                self._cruise_mph = new_target
                if should_announce:
                    self.ctx.say_event(
                        f"Descent target changed to {self.ctx.settings.speed_text(self._cruise_mph)}.",
                        interrupt=False,
                    )
                return
            self._descent_capture_active = False
            if not self._descent_control_active:
                self._descent_control_active = True
                self.ctx.say_event(
                    f"Descent control holding {self.ctx.settings.speed_text(self._cruise_mph)}.",
                    interrupt=False,
                )
            if not t.transmission.automatic and t.rpm < 1100:
                limit_state = "gear"
                limit_message = "Descent control needs a lower gear. Downshift now."
            elif t.grip < 0.55:
                limit_state = "traction"
                limit_message = "Low traction limits descent control. Apply brakes carefully."
            else:
                limit_state = ""
                limit_message = ""
                t.engine_brake = True
                if descent_level == "interactive":
                    safe_target = min(self._cruise_mph, 55.0)
                    self._cruise_mph = safe_target
                    if t.speed_mph > safe_target + 8.0:
                        t.brake = max(t.brake, min(0.7, (t.speed_mph - safe_target) / 25.0))
                if t.speed_mph > self._cruise_mph + 10.0:
                    limit_state = "grade"
                    limit_message = "Descent control cannot hold this grade. Apply service brakes."
            if limit_state != self._descent_limit_state:
                self._descent_limit_state = limit_state
                if limit_message:
                    self.ctx.say_event(limit_message, interrupt=True)
        elif self._descent_control_active:
            self._descent_control_active = False
            self._descent_limit_state = ""
            self._descent_capture_active = False
            t.engine_brake = False
        if braking or t.emergency_brake or t.air_brakes_holding or not t.engine_on or t.stalled:
            self._cancel_cruise()
            self.ctx.say_event("Adaptive cruise canceled.", interrupt=False)
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
        # Predictive ACC: never carry the driver past the posted limit. With real
        # OSM limits baked per leg, a held set speed would otherwise sail through
        # urban drops and corridor limit changes straight into speeding strikes,
        # tickets, and trooper stops -- all of which now exist. The "Speed limit X"
        # cue still names the number; this cue says cruise is handling it.
        posted, _ = self._acc_posted_limit_ahead()
        cap_mph = posted + ACC_LIMIT_OFFSET_MPH
        limit_capped = cap_mph < self._cruise_mph
        if limit_capped:
            target_mph = cap_mph
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
                if context.lead.speed_mph <= 5.0 and not self.ctx.settings.stop_and_go_assist:
                    self._cancel_cruise()
                    self.ctx.say_event(
                        "Stopped traffic ahead; adaptive cruise canceled.", interrupt=False
                    )
                    return
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
        if (following or limit_capped) and error < -2.0:
            weather_brake = 0.45 if self.weather.effects.grip < 0.7 else 0.65
            t.brake = max(t.brake, min(weather_brake, abs(error) / 30.0))

    def _handle_out_of_fuel(self) -> None:
        if self._rescue_offered:
            return
        self._rescue_offered = True
        p = self.ctx.profile
        fee = 750.0
        if player_pays_operating_costs(p.business_status):
            p.money -= fee  # can go negative: the rescue is not optional
            billing = f"for {fee:,.0f} dollars"
        else:
            # the carrier pays for company fuel, but a preventable service
            # call goes straight onto the driver's record
            p.career.reputation = max(0.0, p.career.reputation - 2.0)
            billing = "on the carrier account, and dispatch noted the service call"
        self.truck.refuel(30.0)
        self._rescue_offered = False
        self.ctx.audio.play("ui/error")
        self.ctx.say_event(
            f"You ran out of fuel. Roadside rescue brought thirty "
            f"gallons {billing}. Press "
            f"{self.ctx.control_hint('engine')} to restart "
            "the engine, and plan your fuel stops.",
            interrupt=True,
        )

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
        message = (
            f"Pickup ahead: {self._pickup_facility_text()}."
            if self._terse_speech()
            else (
                f"Pickup ahead: {self._pickup_facility_text()}. "
                "Slow down and come to a complete stop at the gate."
            )
        )
        self.ctx.say_event(message, interrupt=True)

    def _handle_pickup_creep(self) -> None:
        if self._arrival_full_stop_said:
            return
        self._arrival_full_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/notify", volume=0.7)
        self._set_status("Pickup gate: stop to check in.")
        self.ctx.say_event(f"At {self._pickup_facility_text()}. Stop to check in.", interrupt=False)

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

        self.ctx.replace_state(
            TimedMessageState(
                self.ctx,
                title="Pulling into pickup",
                message=(
                    f"Pulling into {self._pickup_facility_text()}. "
                    "Setting the brakes and rolling to the check-in lane."
                ),
                status="Pulling into the pickup facility. Please wait.",
                seconds=STOP_PULL_IN_WAIT_S,
                on_complete=complete,
                sound_key="ui/notify",
            )
        )

    def _arrive(self) -> None:
        self.ctx.replace_state(ArrivalState(self.ctx, self))

    def _handle_missed_destination_exit(self) -> None:
        exit_details = self._destination_exit_details(include_past=True)
        self.trip.finished = False
        self._exit_stop = None
        self._exit_signal_on = False
        self._exit_signal_canceled = False
        self._cancel_cruise()
        if self._missed_destination_exit_said:
            return
        self._missed_destination_exit_said = True
        reroute_text = (
            "Continue to the next safe turnaround. Dispatch reroutes you back "
            "onto the approach; take the destination exit when it comes up."
        )
        if exit_details is not None:
            self.trip.game_minutes += 20.0
            self.trip.position_mi = max(0.0, exit_details[0] - 1.0)
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
        if self.ctx.settings.destination_approach_assist:
            self._cancel_cruise()
            self.truck.throttle = 0.0
            self.truck.brake = 1.0
            if self.truck.speed_mph <= 0.5 and not self._arrival_full_stop_said:
                self._arrival_full_stop_said = True
                self.truck.set_parking_brake()
                self.ctx.say_event(
                    "Destination approach stopped and holding. Press Enter, or controller A, to continue into the facility.",
                    interrupt=True,
                )
            return
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
        _advance_rest_clock(self, STOP_PULL_IN_MIN)
        self.hos.on_duty(STOP_PULL_IN_MIN)
        self._set_status("Pulling into destination. Dock menu opening.")

        def complete() -> None:
            self._set_status("Parked at destination. Dock and deliver.")
            self.ctx.replace_state(FacilityArrivalState(self.ctx, self))

        self.ctx.replace_state(
            TimedMessageState(
                self.ctx,
                title="Pulling into destination",
                message=(
                    f"Pulling into {self._destination_facility_text()}. "
                    "Brakes set; dock menu opening in a moment."
                ),
                status="Pulling into the destination facility. Please wait.",
                seconds=STOP_PULL_IN_WAIT_S,
                on_complete=complete,
                sound_key="ui/notify",
            )
        )

    def _destination_facility_text(self) -> str:
        return self.job.destination_facility_text()

    def _pickup_facility_text(self) -> str:
        return self.job.origin_facility_text()

    def _city_service_text(self) -> str:
        try:
            return self.ctx.world.city_service(self.job.origin, self.city_service_key).spoken_name
        except KeyError:
            return self.job.destination_location or "city service"

    def _objective_text(self) -> str:
        if self.phase == DRIVE_PHASE_PICKUP:
            return "pickup at " + self._pickup_facility_text()
        if self.phase == DRIVE_PHASE_CITY_SERVICE:
            return "city service " + self._city_service_text()
        return "deliver to " + self._destination_facility_text()

    def _pickup_progress_summary(self) -> str:
        return (
            f"{self.trip.remaining_miles:.1f} miles remaining of "
            f"{self.trip.total_miles:.1f} to pickup at "
            f"{self._pickup_facility_text()}."
        )

    def _city_service_progress_summary(self) -> str:
        return (
            f"{self.trip.remaining_miles:.1f} miles remaining of "
            f"{self.trip.total_miles:.1f} to {self._city_service_text()}."
        )

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
            f"Speed: {t.speed_mph:.0f} mph (limit {limit:.0f}{', ' + reason if reason else ''})"
            f"   Lane: {self.lane.lane_name}",
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
