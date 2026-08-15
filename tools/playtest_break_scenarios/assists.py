"""Driving assists fighting each other, or fighting the driver.

Cruise, curve-speed assist, and descent control stacked through a mountain;
rapid engine-brake toggling to dodge a town no-jake ordinance; and the new
facility-gate overshoot loop with destination approach assist on and off.
"""

from __future__ import annotations

from playtest_break import DT, MPH_PER_MPS, Rig, _fabricated_curve, _outcome, scenario


@scenario(
    "assists_fight_descent",
    "Cruise + curve assist + descent control on a 6% grade with bends; count cue spam.",
)
def _assists_fight():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        start = 15.0
        d.trip.position_mi = start
        d.trip.curves = [
            _fabricated_curve(start + off, advisory=35, direction="LR"[i % 2])
            for i, off in enumerate((1.5, 3.5, 5.5, 7.5))
        ]
        d.trip.grade_at = lambda mile: -0.06
        rig.prepare(speed_mph=55.0)
        rig.press(rig.pygame.K_k)  # arm automatic speed control at 55
        stage_flips = 0
        last_stage = d.truck.engine_brake_stage
        seconds = 0.0
        frames = 0
        while frames < 5400 and d.trip.position_mi < start + 9.0:
            d.update(DT)
            frames += 1
            seconds += DT
            if d.truck.engine_brake_stage != last_stage:
                stage_flips += 1
                last_stage = d.truck.engine_brake_stage
            if frames % 10 == 0:
                rig.check_invariants()
        rig.check_invariants()
        cue_count = rig.said("Curve speed assistance") + rig.said("Descent")
        if seconds > 0 and cue_count / seconds > 0.2:
            findings.append(
                f"assist cue spam: {cue_count} assist cues in {seconds:.0f}s of descent"
            )
        if seconds > 0 and stage_flips / seconds > 0.5:
            findings.append(
                f"retarder chatter: engine brake stage changed {stage_flips} times "
                f"in {seconds:.0f}s"
            )
        if d.truck.speed_mph > 80.0:
            findings.append(
                f"assists lost the mountain: {d.truck.speed_mph:.0f} mph with cruise, "
                "curve assist, and descent control all engaged"
            )
        return _outcome(
            "assists_fight_descent",
            rig,
            findings,
            f"{cue_count} cues, {stage_flips} stage steps over {seconds:.0f}s; "
            f"held {d.truck.speed_mph:.0f} mph",
        )
    finally:
        rig.close()


@scenario(
    "jake_toggle_fine_dodge",
    "Toggle the jake off at each warning in a ban zone: fines dodged forever, warnings spam.",
)
def _jake_dodge():
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_GRACE_S

    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        t = d.truck
        d.trip.position_mi = 2.0  # inside the Buffalo zone
        t.engine_on = True
        t.transmission.gear = 8
        t.velocity_mps = 55.0 / MPH_PER_MPS
        d.trip.grade_at = lambda mile: 0.0
        cycles = 12
        for _ in range(cycles):
            t.engine_brake = True
            d._update_engine_brake_zone(0.1)  # warning fires
            d._update_engine_brake_zone(JAKE_ZONE_GRACE_S - 1.0)  # bark through the grace
            t.engine_brake = False
            d._update_engine_brake_zone(0.1)  # engagement ends: clean slate
        warnings = rig.said("No engine brake")
        if d.jake_zone_fines == 0 and warnings >= cycles:
            findings.append(
                f"jake toggled off just inside the grace {cycles} times: retarder barking "
                f"~90% of the time in town, {warnings} warnings spoken, zero dollars fined "
                "-- the ordinance is a rhythm game, and the warning repeats forever"
            )
        elif d.jake_zone_fines > 0:
            money_delta = 5000.0 - rig.ctx.profile.money
            if abs(money_delta - d.jake_fines_paid) > 0.01:
                findings.append(
                    f"jake fines paid {d.jake_fines_paid:,.0f} but money moved {money_delta:,.0f}"
                )
        return _outcome(
            "jake_toggle_fine_dodge",
            rig,
            findings,
            f"{d.jake_zone_fines} fines, {warnings} warnings over {cycles} toggle cycles",
        )
    finally:
        rig.close()


@scenario(
    "gate_overshoot_with_assists",
    "Carry past the facility gate at 70 with the approach assist off, then on; verify both.",
)
def _gate_overshoot_with_assists():
    """The new missed-facility-gate loop-back (states/driving_facility_gate.py),
    stressed under two assist configurations: none (the miss should latch and
    charge time) and destination_approach_assist (which should brake for the
    player and prevent the miss outright). Also checks that HOS/fuel keep
    ticking honestly through a loop, since the clock is the only consequence.
    """
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        rig.ctx.settings.destination_approach_assist = False
        d._destination_exit_taken = True
        d.trip.position_mi = d.trip.total_miles
        d.trip.finished = True
        d.truck.engine_on = True
        d.truck.velocity_mps = 70.0 / MPH_PER_MPS
        d._gate_speed_warned = True
        d._gate_grace_s = 0.0
        minutes_before = d.trip.game_minutes
        driving_min_before = d.hos.driving_min
        fuel_before = d.truck.fuel_gal
        d._handle_arrival_gate()
        if d.trip.finished:
            findings.append("70 mph across the gate with no assist did not miss it at all")
        if d._gate_miss_count != 1:
            findings.append(f"expected exactly one miss recorded, got {d._gate_miss_count}")
        from freight_fate.states.driving_facility_gate import GATE_MISS_LOOP_MIN

        if abs(d.trip.game_minutes - minutes_before - GATE_MISS_LOOP_MIN) > 1e-6:
            findings.append(
                f"gate miss charged {d.trip.game_minutes - minutes_before:.1f} min, "
                f"expected {GATE_MISS_LOOP_MIN}"
            )
        if d.hos.driving_min == driving_min_before:
            findings.append(
                "the 20 lost minutes of the loop-back never touched the HOS driving clock: "
                "a scripted reposition is free of hours-of-service cost"
            )
        if d.truck.fuel_gal >= fuel_before:
            findings.append(
                "looping back through the safe turnaround burned zero fuel -- a scripted "
                "reposition with no fuel cost while the player's odometer clearly moved"
            )
        if "slow to" not in rig.transcript[-1].lower():
            findings.append(f"miss message does not restate a target speed: {rig.transcript[-1]}")

        # Now the assist should own it and never miss.
        rig.ctx.settings.destination_approach_assist = True
        d._destination_exit_taken = True
        d.trip.position_mi = d.trip.total_miles
        d.trip.finished = True
        d.truck.velocity_mps = 70.0 / MPH_PER_MPS
        d._gate_speed_warned = True
        d._gate_grace_s = 0.0
        miss_count_before = d._gate_miss_count
        d._handle_arrival_gate()
        if not d.trip.finished:
            findings.append(
                "destination_approach_assist enabled did not prevent a 70 mph gate miss"
            )
        if d._gate_miss_count != miss_count_before:
            findings.append("assist-owned approach still incremented the gate-miss counter")
        if d.truck.brake != 1.0:
            findings.append(
                f"assist claims to be braking the truck but truck.brake is {d.truck.brake}"
            )

        return _outcome(
            "gate_overshoot_with_assists",
            rig,
            findings,
            "unassisted miss looped back honestly; the assist then owned the approach",
        )
    finally:
        rig.close()


@scenario(
    "ramp_speed_control_handback",
    "Signal early at 20x, honor the ramp's stop bar, drive on: no early shed, "
    "and speed control returns unaided.",
)
def _ramp_speed_control_handback():
    """Both of Shane's 2026-08-15 reports, driven end to end in real frames.

    Signalling nine miles out used to start the shed immediately under time
    compression, and taking the ramp used to kill adaptive cruise and the speed
    keeper for the rest of the run -- only the resume key brought them back.
    Neither survived a full gate before, because no scenario drove a ramp
    terminal and then asked whether automatic speed control had come back.
    """
    from freight_fate.states.driving import RAMP_MAX_MPH

    name = "ramp_speed_control_handback"
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        pygame = rig.pygame
        # High pacing is the case the early shed showed up in; full lane
        # keeping pins the exit-lane mechanics that are not under test here.
        rig.ctx.settings.time_scale = 20.0
        d.trip.time_scale = 20.0
        rig.ctx.settings.route_transition_assist = True
        rig.ctx.settings.speed_keeper = True
        rig.ctx.settings.lane_keeping = "full"
        d.trip.curves = []
        d.trip.grade_at = lambda mile: 0.0
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        rig.prepare(speed_mph=limit - 1.0)
        rig.press(pygame.K_k)  # automatic speed control on, at corridor speed
        cruise = d._cruise_mph
        if cruise is None:
            findings.append("cruise never armed at corridor speed")
            return _outcome(name, rig, findings, "")

        # Signal as early as the game lets a driver signal, the way the report
        # did: X every half second until an exit takes it.
        armed_mi = None
        # This scenario never touches the pedals, so anything that stops the
        # truck on the way -- automatic braking for a merging vehicle, say --
        # leaves it parked for the rest of the frame budget and the run reports
        # that no exit ever arrived. The subject is the ramp handback, not
        # surviving traffic, so a stall gets the truck rolling again.
        stalls = 0
        for frame in range(20000):
            if d._exit_stop is not None:
                armed_mi = d._exit_stop.at_mi - d.trip.position_mi
                break
            if frame % 15 == 0:
                rig.press(pygame.K_x)
            d.update(DT)
            if d.truck.speed_mph < 3.0 and stalls < 20:
                stalls += 1
                rig.prepare(speed_mph=limit - 1.0)
                rig.press(pygame.K_k)
            if frame % 10 == 0:
                rig.check_invariants()
        if armed_mi is None:
            findings.append("no exit ever came within signalling range")
            return _outcome(name, rig, findings, "")
        exit_stop = d._exit_stop

        # 1. Far from the gore the signal itself must not slow the truck: the
        #    approach cap has to stay clear of the set speed.
        early_shed_mi = None
        stopped_short_mi = None
        entry_mph = None
        for _ in range(60000):
            ahead = exit_stop.at_mi - d.trip.position_mi
            cap = d._ramp_approach_cap_mph()
            if early_shed_mi is None and ahead > 1.0 and cap is not None and cap < cruise - 0.01:
                early_shed_mi = ahead
            if stopped_short_mi is None and ahead > 0.0 and d.truck.speed_mph <= 0.05:
                stopped_short_mi = ahead
            if d._ramp_mi is not None:
                entry_mph = d.truck.speed_mph
                break
            if ahead < -0.5:
                break
            d.update(DT)
            rig.check_invariants()
        if stopped_short_mi is not None:
            findings.append(
                f"came to a dead stop {stopped_short_mi:.2f} miles short of the gore, in the "
                "through lane: the approach slowed the truck and then nothing drove it"
            )
        if early_shed_mi is not None:
            findings.append(
                f"the exit cap fell under the {cruise:.0f} mph set speed "
                f"{early_shed_mi:.1f} miles from the gore: signalling early is itself "
                "what slows the truck"
            )
        if entry_mph is None:
            findings.append("the signalled exit was never taken at all")
            return _outcome(name, rig, findings, "")
        if entry_mph > RAMP_MAX_MPH:
            findings.append(f"entered the gore at {entry_mph:.1f} mph, over the ramp's limit")

        # 2. The ramp takes the pedals, never the session.
        if not d._speed_control_armed:
            findings.append(
                "taking the exit disarmed automatic speed control outright, so nothing "
                "can bring it back but the resume key"
            )
        # 3. Route-transition assistance brings the truck to the bar. Nothing
        #    may re-engage on the creep toward it.
        rig.step(60000, until=lambda: d._ramp_terminal_done and d.truck.speed_mph < 1.0)
        if not d._ramp_terminal_done:
            findings.append("the ramp terminal never resolved")
        if d._cruise_mph is not None or d._keeper_mph is not None:
            findings.append("automatic speed control re-engaged while still on the ramp")

        # 4. Drive on from the bar -- past the plaza rather than into it, which
        #    is the "honor the bar and drive on" the report is about. No key
        #    but the throttle: speed control has to be live again once the ramp
        #    is behind the truck.
        rig.held.add(pygame.K_UP)
        rig.step(60000, until=lambda: d._ramp_mi is None and d.truck.speed_mph > 25.0)
        rig.step(120)  # a couple of seconds of open road to hand it back on
        rig.held.discard(pygame.K_UP)
        live = d._cruise_mph is not None or d._keeper_mph is not None
        if not live:
            findings.append(
                "past the stop bar and back up to road speed with automatic speed "
                "control still dead: the driver has to switch it on by hand"
            )

        # 5. And the drive stayed sane by ear: no resume announced on the ramp,
        #    and the pause never announced itself twice.
        if rig.said("Automatic speed control paused") > 1:
            findings.append("the ramp pause announced itself more than once")
        if rig.said("resuming") > 1:
            findings.append("automatic speed control announced its return more than once")

        return _outcome(
            name,
            rig,
            findings,
            f"signalled {armed_mi:.1f} mi out with no early shed, entered the gore at "
            f"{entry_mph:.0f} mph, and speed control came back past the bar unaided",
        )
    finally:
        rig.close()
