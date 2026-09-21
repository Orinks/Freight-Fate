"""Settings-flip and cross-cutting abuse: units, transmission, waiting, hazards.

Flipping transmission mode and units mid-drive, deliberate parked waiting's
double-speed clock, and ignoring hazards all the way to a totaled truck.
"""

from __future__ import annotations

import re

from playtest_break import DT, Rig, _outcome, scenario


@scenario(
    "settings_flips_mid_drive",
    "Flip transmission and units at 55 mph; the cab must announce and switch everywhere.",
)
def _settings_flips():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        d.trip.position_mi = 12.0
        rig.prepare(speed_mph=55.0)
        rig.step(30)
        gear_before = d.truck.transmission.gear
        speed_before = d.truck.speed_mph
        rig.ctx.settings.automatic_transmission = False
        rig.step(2)
        if rig.said("Transmission changed to manual") != 1:
            findings.append("mid-drive flip to manual was not announced exactly once")
        if d.truck.transmission.automatic:
            findings.append("settings flip did not reach the transmission")
        if abs(d.truck.transmission.gear - gear_before) > 1:
            findings.append(
                f"flipping to manual jumped the gear {gear_before} -> {d.truck.transmission.gear}"
            )
        if abs(d.truck.speed_mph - speed_before) > 5.0:
            findings.append("flipping the transmission changed the truck's speed")
        rig.ctx.settings.automatic_transmission = True
        rig.step(2)

        d._speak_speed_limit()
        imperial_line = rig.transcript[-1]
        if "miles per hour" not in imperial_line and "mile" not in imperial_line:
            findings.append(f"imperial limit readout has no imperial units: {imperial_line}")
        rig.ctx.settings.imperial_units = False
        rig.step(2)
        d._speak_speed_limit()
        metric_line = rig.transcript[-1]
        if "kilometers per hour" not in metric_line:
            findings.append(f"metric limit readout is not metric: {metric_line}")
        if "miles per hour" in metric_line:
            findings.append(f"metric readout still speaks miles: {metric_line}")
        d._last_announced_mph = 0.0
        d._speed_announce_timer = 1e9
        rig.step(2)
        recent = rig.transcript[-3:]
        if not any("kilometers per hour" in line for line in recent):
            findings.append("routine speed announcements did not switch to metric")
        return _outcome(
            "settings_flips_mid_drive",
            rig,
            findings,
            "transmission and unit flips announced and applied everywhere checked",
        )
    finally:
        rig.close()


@scenario(
    "waiting_time_warp",
    "Deliberate parked waiting: the double-speed clock must bill time honestly.",
)
def _time_warp():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        d.trip.position_mi = 12.0
        rig.prepare(speed_mph=0.0)
        d._toggle_parking_brake()
        if not d.trip.waiting:
            findings.append("player-set parking brake did not arm waiting")
        gm_before = d.trip.game_minutes
        duty_before = d.hos.duty_min
        rig.step(300)  # 10 real seconds
        gm = d.trip.game_minutes - gm_before
        expected = 300 * DT * d.trip.time_scale * 2.0 / 60.0
        if abs(gm - expected) > expected * 0.05:
            findings.append(
                f"waiting advanced {gm:.2f} game-min in 10s; double pacing predicts {expected:.2f}"
            )
        duty_gained = d.hos.duty_min - duty_before
        if abs(duty_gained - gm) > max(0.2, gm * 0.05):
            findings.append(
                f"trip clock moved {gm:.2f} game-min while the HOS ledger logged "
                f"{duty_gained:.2f} -- the two clocks disagree while waiting"
            )
        d._toggle_parking_brake()  # release
        if d.trip.waiting:
            findings.append("releasing the parking brake left waiting armed")
        return _outcome(
            "waiting_time_warp",
            rig,
            findings,
            f"waiting billed {gm:.1f} game-min in 10s, HOS ledger matched",
        )
    finally:
        rig.close()


@scenario(
    "hazard_ignored_to_100_damage",
    "No AEB, never brake for hazards; collision math, spoken damage, and what 100% allows.",
)
def _hazard_ignore():
    from freight_fate.sim.trip_models import TripEvent, TripEventKind

    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        t = d.truck
        rig.ctx.settings.automatic_emergency_braking = False
        d.trip.position_mi = 12.0
        d.trip.curves = []
        rig.prepare(speed_mph=70.0)
        rig.held.add(rig.pygame.K_UP)
        collisions = 0
        # Each spoken number is checked against the damage the truck carried at
        # the moment it was said. Comparing the LAST line to the truck's state
        # at the END of the run is what made the harness's first pass report a
        # lie that was not one: this scenario drives the truck to out of
        # service, and the automatic roadside rescue then patches it down to
        # BREAKDOWN_REPAIR_DAMAGE_PCT, long after the line was honest.
        spoken_vs_actual: list[tuple[float, float]] = []
        for _ in range(16):
            if t.damage_pct >= 100.0:
                break
            d._handle_trip_event(
                TripEvent(TripEventKind.HAZARD, "Debris on the road ahead. Brake!", {})
            )
            before = collisions
            seen_lines = len(rig.lines_with("Total damage"))
            rig.step(1200, until=lambda n=before: rig.said("Collision!") > n)
            collisions = rig.said("Collision!")
            if collisions == before:
                break
            fresh = rig.lines_with("Total damage")[seen_lines:]
            for line in fresh:
                m = re.search(r"Total damage (\d+) percent", line)
                if m:
                    spoken_vs_actual.append((float(m.group(1)), t.damage_pct))
            rig.step(600, until=lambda: t.speed_mph >= 55.0)  # power back up
        for said_pct, actual_pct in spoken_vs_actual:
            if abs(said_pct - round(actual_pct)) > 1.0:
                findings.append(
                    f"a collision spoke {said_pct:.0f}% total damage while the truck was at "
                    f"{actual_pct:.0f}%"
                )
                break
        if collisions == 0:
            findings.append("ignored hazards never produced a collision")
        if t.damage_pct > 100.0:
            findings.append(f"damage exceeded its cap: {t.damage_pct}")
        if t.damage_pct >= 100.0:
            rig.step(300)
            if t.speed_mph > 30.0 and d._pull_over is None:
                findings.append(
                    "at 100% damage the wreck still cruises at highway speed; the unsafe-"
                    "equipment stop only exists inside patrol windows, so on an empty road "
                    "a totaled truck is street-legal forever"
                )
        return _outcome(
            "hazard_ignored_to_100_damage",
            rig,
            findings,
            f"{collisions} collisions to {t.damage_pct:.0f}% damage, all spoken honestly",
        )
    finally:
        rig.close()
