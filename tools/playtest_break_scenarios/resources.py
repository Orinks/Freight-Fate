"""Resource abuse: fuel, hours-of-service, fatigue, and rest.

Running dry for a free rescue, driving a 20+ hour marathon, cheesing HOS with
micro-rests, ignoring a microsleep, and taking a motel room with a minute left
on the delivery deadline.
"""

from __future__ import annotations

import re

from playtest_break import DT, Outcome, Rig, _outcome, scenario


class _AdvancingClock:
    """A wall clock the scenario can fast-forward between rescues.

    ``EventSpeechPacer``'s repeat window (``REPEAT_WINDOW_S``, 2.5 real
    seconds) is keyed off ``time.monotonic()``, and the fuel-farm loop below
    runs three byte-identical rescue lines back to back in a fraction of a
    second of real wall time -- a harness artifact, not something a real
    player can hit, since running a tank dry twice takes minutes of actual
    driving. Swapping the pacer onto this clock and advancing it past the
    window between rescues makes the scenario measure what a real driver
    would hear instead of how fast the test loop happens to run.
    """

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@scenario(
    "fuel_rescue_farming",
    "Run dry three times as a company driver, once as an owner-op; is the rescue farmable?",
)
def _fuel_farm():
    from freight_fate.models.business import LEASED_OWNER_OPERATOR
    from freight_fate.speech_pacing import EventSpeechPacer

    findings: list[str] = []
    rig = Rig()
    try:
        d = rig.d
        p = rig.ctx.profile
        d.trip.position_mi = 12.0
        rig.prepare(speed_mph=0.0)
        # See _AdvancingClock: real minutes separate two run-dry events, so
        # the pacer's repeat window must see real seconds pass too, or three
        # byte-identical rescue lines collapse into one purely because the
        # test loop runs faster than a real drive ever could.
        clock = _AdvancingClock()
        rig.ctx._event_pacer = EventSpeechPacer(clock=clock)
        money_before = p.money
        rep_before = p.career.reputation
        for _ in range(3):
            d.truck.fuel_gal = 0.001
            d.truck.start_engine()
            rig.step(240, until=lambda: not d.truck.engine_on and d.truck.fuel_gal >= 25.0)
            clock.advance(EventSpeechPacer.REPEAT_WINDOW_S + 1.0)
        rescues = rig.said("Roadside rescue")
        if rescues != 3:
            findings.append(f"expected 3 rescues, transcript has {rescues}")
        if p.money != money_before:
            findings.append(
                f"company-driver rescue moved the driver's money ({p.money - money_before:+,.0f})"
            )
        if p.career.reputation == 0.0 and rep_before <= 6.0:
            findings.append(
                "company driver: after reputation bottoms out at 0, roadside rescue is 30 "
                "free gallons with NO remaining cost -- fuel stops are optional forever"
            )
        elif rep_before - p.career.reputation < 5.9:
            findings.append(
                f"reputation only fell {rep_before - p.career.reputation:.1f} for three "
                "preventable service calls"
            )
        company_summary = (
            f"company: 3 rescues, money {p.money - money_before:+,.0f}, "
            f"rep {rep_before:.0f}->{p.career.reputation:.0f}"
        )
        company_problems = list(rig.problems)
    finally:
        rig.close()

    rig2 = Rig(business=LEASED_OWNER_OPERATOR)
    try:
        d = rig2.d
        p = rig2.ctx.profile
        p.money = 100.0
        d.trip.position_mi = 12.0
        rig2.prepare(speed_mph=0.0)
        clock2 = _AdvancingClock()
        rig2.ctx._event_pacer = EventSpeechPacer(clock=clock2)
        for _ in range(2):
            d.truck.fuel_gal = 0.001
            d.truck.start_engine()
            rig2.step(240, until=lambda: not d.truck.engine_on and d.truck.fuel_gal >= 25.0)
            clock2.advance(EventSpeechPacer.REPEAT_WINDOW_S + 1.0)
        if abs(p.money - (100.0 - 1500.0)) > 0.01:
            findings.append(
                f"owner-op rescue billing off: expected -1,500 total, money is {p.money:,.0f}"
            )
        # Money below zero with no floor and no spoken balance is deliberate
        # ("can go negative: the rescue is not optional") -- only flag drift.
        findings.extend(f"invariant: {x}" for x in company_problems + rig2.problems)
        verdict = "ODD" if findings else "CLEAN"
        note = (
            findings[0] if findings else (company_summary + f"; owner-op billed to {p.money:,.0f}")
        )
        return Outcome("fuel_rescue_farming", verdict, note, findings, rig2.transcript)
    finally:
        rig2.close()


@scenario(
    "hos_marathon_and_rest_cheese",
    "22-hour drive, micro-rest cheese, and the in-cab waiting clock vs the HOS ledger.",
)
def _hos_probe():
    from freight_fate.sim import hos as hos_mod
    from freight_fate.sim.hos import HosClock

    findings: list[str] = []
    # Pure-model probes first: no App needed, fully deterministic.
    clock = HosClock()
    clock.drive(11 * 60 + 5)
    if not clock.in_violation("realistic"):
        findings.append("11h05m of driving is not a violation in realistic mode")
    cheese = HosClock()
    for _ in range(12):
        cheese.drive(48.0)
        cheese.off_duty(29.9)  # 29.9-minute naps: never a qualifying break
    if cheese.since_break_min < 8 * 60:
        findings.append("29.9-minute micro-rests reset the 30-minute-break clock (they must not)")
    if cheese.driving_min < 9 * 60:
        findings.append("micro-rests drained the 11-hour driving clock")
    legit = HosClock()
    legit.drive(60.0)
    for _ in range(20):
        legit.off_duty(30.0)
    if legit.driving_min != 0.0:
        findings.append("10 continuous off-duty hours (in 30-min slices) did not reset the shift")

    # In-cab: deliberate waiting burns the 14-hour window as ON DUTY and can
    # never become rest, while the alpha-book clock lever counts a 10-hour
    # wait as a full break. Two clocks, two answers for the same nap.
    rig = Rig()
    try:
        d = rig.d
        d.trip.position_mi = 12.0
        rig.prepare(speed_mph=0.0)
        d._toggle_parking_brake()  # player-set brake arms deliberate waiting
        if not d.trip.waiting:
            findings.append("player-set parking brake did not arm waiting fast-forward")
        scale = d.trip.effective_time_scale
        if abs(scale - d.trip.time_scale * 2.0) > 1e-6:
            findings.append(f"waiting clock runs {scale:.0f}x, expected double pacing")
        duty_before = d.hos.duty_min
        for _ in range(120):  # ten game-hours of parked waiting, direct-call idiom
            d._update_hours_and_fatigue(5.0)
        waited_min = d.hos.duty_min - duty_before
        if d.hos.status != "on_duty_not_driving":
            findings.append(f"parked waiting logged as {d.hos.status}")
        if d.hos.off_duty_min > 0.0:
            findings.append("parked waiting accrued off-duty rest (it must stay on duty)")
        # No else. Deliberate waiting staying on duty is the DESIGN -- the line
        # above asserts it -- so an else here reported a finding on the healthy
        # path and could never come back clean. That is what it did on the
        # harness's first run, and an always-odd scenario teaches a reader to
        # ignore the column. Waiting must still cost the duty window rather
        # than rest the driver; a driver who wants rest sleeps.
        if waited_min <= 0.0:
            findings.append("ten game-hours of parked waiting burned no duty time at all")
        del hos_mod
        return _outcome(
            "hos_marathon_and_rest_cheese",
            rig,
            findings,
            "HOS ledger held against the marathon and the cheese",
        )
    finally:
        rig.close()


@scenario(
    "microsleep_throttle_through",
    "Fatigue 100, never react, keep the floor down; does the forced stop actually stop you?",
)
def _microsleep():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        p = rig.ctx.profile
        d.trip.position_mi = 12.0
        d.trip.curves = []
        p.fatigue = 100.0
        rig.prepare(speed_mph=65.0)
        rig.held.add(rig.pygame.K_UP)  # throttle is not a microsleep reaction key
        drift_damage: list[float] = []
        forced_stop_frame = None
        frames = 0
        while frames < 14000:
            d.update(DT)
            frames += 1
            if frames % 10 == 0:
                rig.check_invariants()
            if forced_stop_frame is None and rig.said("cannot stay awake") > 0:
                forced_stop_frame = frames
            if forced_stop_frame is not None and frames >= forced_stop_frame + 150:
                break
        drift_lines = rig.lines_with("drifted onto the rumble strip")
        for line in drift_lines:
            m = re.search(r"now (\d+) percent", line)
            if m:
                drift_damage.append(float(m.group(1)))
        if not drift_lines and forced_stop_frame is None:
            findings.append("severe fatigue never produced a microsleep at all")
        if drift_damage and abs(drift_damage[0] - 6.0) > 6.5:
            findings.append(f"first drift damage spoke {drift_damage[0]:.0f}%, model adds 6%")
        if forced_stop_frame is not None and d.truck.speed_mph > 40.0:
            findings.append(
                '"You cannot stay awake ... jolt awake on the brakes. Stop and sleep before '
                'you wreck" -- but the forced stop is a one-frame brake tap: with the '
                f"throttle held the truck is doing {d.truck.speed_mph:.0f} mph five seconds "
                "later and the exhausted driver just keeps going"
            )
        if p.fatigue > 100.0:
            findings.append(f"fatigue exceeded its cap: {p.fatigue}")
        return _outcome(
            "microsleep_throttle_through",
            rig,
            findings,
            f"{len(drift_lines)} drifts, forced stop held the truck",
        )
    finally:
        rig.close()


@scenario(
    "hos_rest_minute_cheese",
    "In violation, rest one minute thirty times; split-sleeper credit must not double-dip.",
)
def _hos_edges():
    from freight_fate.sim.hos import HosClock

    findings: list[str] = []
    clock = HosClock()
    clock.drive(11 * 60 + 5)
    for _ in range(29):
        clock.off_duty(1.0)
    if not clock.in_violation("realistic"):
        findings.append("29 one-minute naps talked the ledger out of an 11-hour violation")
    if clock.driving_min < 11 * 60:
        findings.append("one-minute rests drained the driving clock")
    clock.off_duty(1.0)  # the 30th consecutive minute is a legitimate break
    if clock.since_break_min != 0.0:
        findings.append("30 consecutive off-duty minutes did not clear the break clock")
    if not clock.in_violation("realistic"):
        findings.append("a 30-minute break cleared an 11-hour DRIVING violation (it cannot)")

    split = HosClock()
    split.drive(5 * 60)
    split.sleeper(7 * 60)
    split.drive(2 * 60)
    drive_before_credit = split.driving_min
    split.off_duty(3 * 60)  # completes a 7/3 split pair
    after_first = split.driving_min
    split.off_duty(3 * 60)  # the same long rest must not pair twice
    after_second = split.driving_min
    if after_second < after_first:
        findings.append(
            f"split-sleeper credit double-dipped: driving {drive_before_credit:.0f} -> "
            f"{after_first:.0f} -> {after_second:.0f} minutes"
        )
    for label, value in (
        ("driving_min", split.driving_min),
        ("duty_min", split.duty_min),
        ("since_break_min", split.since_break_min),
    ):
        if value < 0.0:
            findings.append(f"split credit drove {label} negative: {value}")
    verdict = "ODD" if findings else "CLEAN"
    note = findings[0] if findings else "minute-rest cheese and split double-dip both held"
    return Outcome("hos_rest_minute_cheese", verdict, note, findings, [])


@scenario(
    "motel_rest_deadline_crunch",
    "Take a 10-hour motel room with 1 minute left to deliver; the game must not paper over it.",
)
def _motel_deadline_crunch():
    """A player one minute from a deadline who takes a full 10-hour motel rest
    should be told, honestly, that the load is now hours overdue -- never a
    stretched deadline, never silence. Uses the RestStopState idiom straight
    from tests/test_career_economy.py's motel tests.
    """
    from freight_fate.models.economy import MOTEL_COST
    from freight_fate.states.driving import RestStopState
    from freight_fate.states.driving_core import _deadline_text

    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        p = rig.ctx.profile
        p.money = 500.0
        p.fatigue = 90.0
        d.trip.position_mi = 12.0
        rig.prepare(speed_mph=0.0)
        # One minute of game-time left before the deadline.
        d.trip.game_minutes = d.job.deadline_game_h * 60.0 - 1.0
        remaining_before = d.job.deadline_game_h - d.trip.game_minutes / 60.0
        if not (0.0 < remaining_before <= 1.0 / 60.0 + 1e-6):
            findings.append(f"setup did not land ~1 minute out: {remaining_before * 60:.2f} min")

        import types

        stop = types.SimpleNamespace(
            name="Test Travel Center",
            at_mi=d.trip.position_mi,
            type="travel_center",
            actions=("break", "fuel"),
            services=(),
            parking="limited",
            exit_label="",
            spoken_name="Test Travel Center",
            parking_text="limited truck parking",
        )
        state = RestStopState(rig.ctx, d, stop)
        rig.app.push_state(state)
        deadline_before_h = d.job.deadline_game_h
        lines_before_sleep = len(rig.transcript)
        state._motel_sleep()

        if p.money != 500.0 - MOTEL_COST:
            findings.append(f"motel did not charge {MOTEL_COST:,.0f} exactly: money is {p.money}")
        if d.job.deadline_game_h != deadline_before_h:
            findings.append(
                f"deadline moved during a rest ({deadline_before_h} -> {d.job.deadline_game_h}); "
                "a motel room must never buy back deadline time"
            )
        remaining_after = _deadline_text(d)
        if "past the deadline" not in remaining_after:
            findings.append(
                f"took a 10-hour rest 1 minute from the deadline and the honesty line reads "
                f"{remaining_after!r} instead of admitting the load is now overdue"
            )
        # The motel confirmation is followed by an achievement announcement
        # (slept_on_route), so check every line this call actually spoke, not
        # just the last one in the transcript.
        sleep_lines = rig.transcript[lines_before_sleep:]
        confirmation = next((ln for ln in sleep_lines if "You took a motel room" in ln), "")
        if remaining_after not in confirmation:
            findings.append(
                f"the motel confirmation line does not carry the blown-deadline warning "
                f"({remaining_after!r} missing): {sleep_lines!r}"
            )
        if "wake fresh" not in confirmation:
            findings.append("motel confirmation line dropped the usual rested-and-woke phrasing")
        return _outcome(
            "motel_rest_deadline_crunch",
            rig,
            findings,
            "motel charged honestly and admitted the blown deadline",
        )
    finally:
        rig.close()
