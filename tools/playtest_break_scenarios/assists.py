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
