"""Driving/physics abuse: floor it, reverse it, coast it, dynamite it.

Every scenario here puts the truck in a position no sane driver would choose
and checks whether the physics, the ledgers, and the spoken cues stay honest
about the consequences.
"""

from __future__ import annotations

import re

from playtest_break import DT, Rig, _fabricated_curve, _outcome, scenario


@scenario(
    "floor_it_through_town",
    "Hold the floor through urban speed zones; every dollar it costs must come "
    "from an officer who was audibly there.",
)
def _floor_it():
    """Flooring it must produce a real pull-over or nothing at all.

    This scenario used to check a "speeding strike" ledger: hold nine over for
    six seconds anywhere on the route and the drive banked a charge, billed at
    the dock. That was a fine from an officer who was never there, and it is
    gone. What replaces it is the harder question -- when the road DOES charge
    you, was there a trooper, and did the player hear them?
    """
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        money_before = rig.ctx.profile.money
        rig.prepare(speed_mph=30.0)
        rig.held.add(rig.pygame.K_UP)
        rig.step(9000, until=lambda: d.trip.position_mi >= min(25.0, d.trip.total_miles - 8.0))

        # Nothing may bank a charge behind the player's back any more.
        for ghost in ("Speeding strike", "due at delivery", "dollar maximum"):
            if rig.lines_with(ghost):
                findings.append(f"the removed silent speeding charge still speaks: {ghost!r}")
        money_delta = rig.ctx.profile.money - money_before
        if money_delta < 0.0 and d.speeding_tickets == 0:
            findings.append(
                f"money fell {-money_delta:,.0f} with no traffic stop on the record: "
                "speeding nobody saw is supposed to cost nothing"
            )
        # A ticket is real money, so it has to have had a real officer behind
        # it -- and the player has to have heard them coming.
        if d.speeding_tickets:
            if not rig.lines_with("Lights and siren behind you"):
                findings.append(
                    f"{d.speeding_tickets} ticket(s) written with no lights-and-siren "
                    "call: the player was charged by an officer they never heard"
                )
            if abs(money_delta + d.ticket_fines_paid) > 0.01:
                findings.append(
                    f"ticket ledger mismatch: money moved {money_delta:+,.0f} but "
                    f"tickets total {d.ticket_fines_paid:,.0f}"
                )
        every_post_heard = all(
            post.announced for post in d.trip.posts if post.declined or not post.staffed
        )
        if not every_post_heard:
            findings.append("a post acted on the driver before it had made a sound")
        return _outcome(
            "floor_it_through_town",
            rig,
            findings,
            f"{d.speeding_tickets} traffic stop(s), {d.ticket_fines_paid:,.0f} dollars, "
            "every one of them audible first",
        )
    finally:
        rig.close()


@scenario(
    "hairpin_at_70_no_assists",
    "Take a 25-mph hairpin at 70 with every assist off; does anything push back?",
)
def _hairpin():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        rig.ctx.settings.curve_speed_assist = False
        rig.ctx.settings.route_transition_assist = False
        start = 12.0
        d.trip.position_mi = start
        d.trip.curves = [_fabricated_curve(start + 1.0)]
        rig.prepare(speed_mph=70.0)
        damage_before = d.truck.damage_pct
        rig.held.add(rig.pygame.K_UP)
        rig.step(6000, until=lambda: d.trip.position_mi >= start + 2.0)
        if rig.said("too fast, drifting to the outside") == 0:
            findings.append("no drifting-outside warning through a hairpin taken 45 over")
        min_speed = d.truck.speed_mph
        damage_delta = d.truck.damage_pct - damage_before
        if damage_delta == 0.0:
            findings.append(
                "blew a 25-advisory hairpin at 70 (assists and lane drift off): zero damage, "
                "no crash, no spoken consequence beyond the warning -- the bend cannot "
                "hurt you"
            )
        return _outcome(
            "hairpin_at_70_no_assists",
            rig,
            findings,
            f"hairpin punished the overspeed (damage +{damage_delta:.0f}, min {min_speed:.0f} mph)",
        )
    finally:
        rig.close()


@scenario(
    "reverse_down_the_route",
    "Engage reverse and back down the interstate; position must clamp, someone should object.",
)
def _reverse_route():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        d.trip.position_mi = 1.0
        rig.prepare(speed_mph=0.0)
        # The deliberate direction gesture: a FRESH brake press at a standstill,
        # held through the confirmation beat.
        rig.step(5)  # settle with no keys so the press below is a rising edge
        rig.held.add(rig.pygame.K_DOWN)
        rig.step(60)  # > DIRECTION_CHANGE_HOLD_S at DT
        if not d.truck.transmission.in_reverse:
            findings.append("standstill reverse gesture never engaged reverse")
            return _outcome("reverse_down_the_route", rig, findings, "")
        max_reverse_mph = 0.0
        backed_mi = 0.0
        for _ in range(7200):
            d.update(DT)
            max_reverse_mph = max(max_reverse_mph, d.truck.speed_mph)
            backed_mi = 1.0 - d.trip.position_mi
            rig.check_invariants()
            if d.trip.position_mi <= 0.0:
                break
        rig.step(300)  # keep backing against the route origin
        if max_reverse_mph > 11.0:
            findings.append(f"reverse reached {max_reverse_mph:.1f} mph (cap should be ~10)")
        if d.trip.position_mi < 0.0:
            findings.append("backed to a negative route position")
        wrongway = [
            line
            for line in rig.transcript
            if "wrong" in line.lower()
            or "backward" in line.lower()
            or "back the way" in line.lower()
        ]
        if backed_mi >= 0.5 and not wrongway:
            findings.append(
                f"backed {backed_mi:.1f} miles down the interstate (to route mile "
                f"{d.trip.position_mi:.2f}) with no wrong-way or off-route feedback of any "
                "kind after the initial 'Reverse selected' -- a blind player has no way to "
                "know the trip is unwinding"
            )
        if d.hos.driving_min <= 0.0:
            findings.append("reversing at 9 mph never counted as HOS driving time")
        return _outcome(
            "reverse_down_the_route",
            rig,
            findings,
            f"clamped at mile {d.trip.position_mi:.2f}, reverse capped {max_reverse_mph:.1f} mph",
        )
    finally:
        rig.close()


@scenario(
    "slam_reverse_at_speed",
    "Manual box: grab reverse at 60 mph; a real driveline would grenade.",
)
def _slam_reverse():
    from freight_fate.sim.transmission import REVERSE

    rig = Rig(automatic=False)
    findings: list[str] = []
    try:
        d = rig.d
        d.trip.position_mi = 12.0
        rig.prepare(speed_mph=60.0, gear=10)
        rig.held.add(rig.pygame.K_LSHIFT)  # clutch in
        rig.step(8)
        # Through TruckState, which is the path the gear keys take
        # (states/driving_controls.py). Calling Transmission.request_gear
        # directly reaches past the road-speed guard that lives one layer up,
        # and reported a bug no player can reach for the harness's first run.
        damage_before = d.truck.damage_pct
        result = d.truck.request_gear(REVERSE)
        rig.held.discard(rig.pygame.K_LSHIFT)
        if result.ok:
            findings.append(
                "reverse engaged at 60 mph forward with only the clutch pressed: no speed "
                "guard, no grind, no driveline damage model"
            )
        elif d.truck.damage_pct <= damage_before:
            findings.append(
                "reverse at 60 mph was refused but cost the driveline nothing: a real box "
                "would be short some teeth for the attempt"
            )
        rig.step(900)
        if d.truck.transmission.in_reverse and d.truck.velocity_mps > 1.0:
            findings.append(
                f"rolling forward at {d.truck.speed_mph:.0f} mph in reverse gear; over-rev "
                f"wear is the only consequence (engine wear {d.truck.engine_wear_pct:.1f}%)"
            )
        redline = rig.lines_with("Redline") + rig.lines_with("taking damage")
        if redline and d.truck.damage_pct == 0.0:
            findings.append(
                f"redline warning says 'taking damage, now {d.truck.damage_pct:.0f} percent' "
                "but over-rev only raises engine WEAR -- the spoken damage number never moves"
            )
        return _outcome(
            "slam_reverse_at_speed",
            rig,
            findings,
            "reverse at speed was refused or punished",
        )
    finally:
        rig.close()


@scenario(
    "neutral_coast_mountain",
    "Slam neutral on a 6% descent and ride it; how fast does it get, and does anything object?",
)
def _neutral_coast():
    rig = Rig(automatic=False)
    findings: list[str] = []
    try:
        d = rig.d
        d.trip.position_mi = 12.0
        d.trip.curves = []
        d.trip.grade_at = lambda mile: -0.06
        rig.prepare(speed_mph=55.0, gear=10)
        result = d.truck.transmission.request_gear(0)  # neutral needs no clutch
        if not result.ok:
            findings.append(f"could not select neutral while rolling: {result.message}")
        # Reaching three figures in neutral down a long grade is not the bug --
        # that IS a runaway, and the sim is right to allow it. What would be a
        # bug is a truck that survives one. The first run of this harness
        # reported "no mechanical failure, no runaway-truck event" as a
        # finding, which was an editorial claim the scenario never checked and
        # its own transcript disproves: the run walks reduced power, limp
        # mode, the last call, and out of service. So check for the
        # consequence rather than asserting its absence.
        from freight_fate.sim.vehicle import RUNAWAY_SPEED_MPH

        max_mph = 0.0
        damage_before = d.truck.damage_pct
        for _ in range(5400):
            d.update(DT)
            max_mph = max(max_mph, d.truck.speed_mph)
            rig.check_invariants()
            if d.trip.position_mi >= d.trip.total_miles - 8.0:
                break
        runaway = max_mph > RUNAWAY_SPEED_MPH
        took_damage = d.truck.damage_pct > damage_before or bool(
            rig.lines_with("Out of service") or rig.lines_with("Limp mode")
        )
        if runaway and not took_damage:
            findings.append(
                f"neutral coast reached {max_mph:.0f} mph, past the {RUNAWAY_SPEED_MPH:.0f} mph "
                "runaway threshold, and the truck took no damage at all: tires past their "
                "rated speed and an unloaded driveline cost nothing"
            )
        strike_count = rig.said("Speeding strike")
        # Try to stop it on the service brakes alone from whatever speed remains.
        rig.held.add(rig.pygame.K_DOWN)
        stopped = rig.step(2700, until=lambda: d.truck.speed_mph < 5.0)
        if d.truck.speed_mph >= 5.0:
            findings.append(
                f"service brakes could not stop the neutral runaway ({d.truck.speed_mph:.0f} "
                f"mph after {stopped * DT:.0f}s of full brake, drums {d.truck.brake_temp_c:.0f}C)"
            )
        return _outcome(
            "neutral_coast_mountain",
            rig,
            findings,
            f"peaked {max_mph:.0f} mph, {strike_count} strikes, brakes recovered it",
        )
    finally:
        rig.close()


@scenario(
    "dynamite_parking_brake_at_60",
    "Pull the parking brake valve at 60: flat-spots, no waiting fast-forward, honest speech.",
)
def _dynamite():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        d.trip.position_mi = 12.0
        rig.prepare(speed_mph=60.0)
        rig.step(30)
        wear_before = d.truck.tire_wear_pct
        speed = d.truck.speed_mph
        d._toggle_parking_brake()
        if rig.said("dynamited") == 0:
            findings.append("no spoken dynamiting consequence for a parking brake pull at 60")
        from freight_fate.states.driving_core import FLAT_SPOT_WEAR_PCT_PER_MPH

        expected = speed * FLAT_SPOT_WEAR_PCT_PER_MPH
        delta = d.truck.tire_wear_pct - wear_before
        if abs(delta - expected) > 0.3:
            findings.append(
                f"flat-spot wear {delta:.2f}% does not match the model ({expected:.2f}%)"
            )
        if d.trip.waiting:
            findings.append("waiting fast-forward armed by a parking brake pulled at speed")
        rig.step(1200, until=lambda: d.truck.speed_mph < 0.5)
        if d.truck.speed_mph >= 0.5:
            findings.append("spring brakes never brought the truck to a stop")
        if d.trip.waiting:
            findings.append("waiting fast-forward armed itself after the dynamited stop")
        scale = d.trip.effective_time_scale
        if scale > d.trip.time_scale:
            findings.append(f"parked clock is running at {scale:.0f}x without deliberate waiting")
        rig.held.add(rig.pygame.K_UP)
        rig.step(90)
        rig.held.discard(rig.pygame.K_UP)
        if rig.said("Parking brake set") == 0:
            findings.append("throttle against the set parking brake drew no spoken lockout cue")
        return _outcome(
            "dynamite_parking_brake_at_60",
            rig,
            findings,
            f"flat-spotted {delta:.1f}% tread, stopped, no fast-forward, lockout cue spoken",
        )
    finally:
        rig.close()


@scenario(
    "redline_damage_readout",
    "Force a road-driven over-rev; the warning quotes a damage number that must be honest.",
)
def _redline():
    rig = Rig(automatic=False)
    findings: list[str] = []
    try:
        d = rig.d
        t = d.truck
        d.trip.position_mi = 12.0
        d.trip.curves = []
        d.trip.grade_at = lambda mile: -0.10
        rig.prepare(speed_mph=50.0)
        # Pick the tallest gear that is already past damaging revs at this speed.
        gear = next((g for g in range(10, 0, -1) if t.coupled_rpm(g) > t.specs.max_rpm * 1.06), 3)
        t.transmission.gear = gear
        wear_before = t.engine_wear_pct
        rig.step(600, until=lambda: rig.said("Redline") + rig.said("redline") > 0)
        redline_lines = rig.lines_with("redline") + rig.lines_with("Redline")
        if not redline_lines:
            findings.append("sustained over-rev never drew a spoken redline warning")
            return _outcome("redline_damage_readout", rig, findings, "")
        m = re.search(r"damage, now (\d+) percent|Damage (\d+) percent", redline_lines[0])
        spoken_damage = float(m.group(1) or m.group(2)) if m else None
        wear_gained = t.engine_wear_pct - wear_before
        if spoken_damage is not None and abs(spoken_damage - t.damage_pct) > 1.0:
            findings.append(
                f"redline warning spoke {spoken_damage:.0f}% damage but damage is "
                f"{t.damage_pct:.0f}%"
            )
        if wear_gained > 0.1 and t.damage_pct == 0.0 and "damage" in redline_lines[0].lower():
            findings.append(
                'redline warning says the engine is "taking damage, now 0 percent" while the '
                f"harm actually lands on engine WEAR (+{wear_gained:.1f}%) -- the spoken "
                "number will read 0 forever, telling a blind player the abuse is free"
            )
        return _outcome(
            "redline_damage_readout",
            rig,
            findings,
            "redline warning quotes a number that tracks the real harm",
        )
    finally:
        rig.close()
