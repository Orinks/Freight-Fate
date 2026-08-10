"""Career and economy abuse: settlement, advances, endorsements, levels, XP.

Covers whether spoken dollar amounts match the ledger at settlement, whether
an abandon-and-advance cycle can mint money, whether endorsement purchases
are exact-dollar honest, level-up bookkeeping at the settlement boundary, the
owner-operator buy-in gate at exactly level 18, and short-haul streak XP
farming.
"""

from __future__ import annotations

import math
import re

from playtest_break import MPH_PER_MPS, Outcome, Rig, _fresh_data_dir, _outcome, _Shim, scenario


@scenario(
    "settlement_spoken_balance",
    "Full menu-flow delivery with 3 speeding strikes; every spoken dollar must match the ledger.",
)
def _settlement_truth():
    _fresh_data_dir()
    from playtest_harness import PlaytestHarness

    findings: list[str] = []
    with PlaytestHarness(_Shim()) as h:
        h.start_delivery()
        d = h.driving
        # Five strikes: a 400-dollar ledger against a ~200-dollar starter wage,
        # to see which of the two numbers the settlement actually bills.
        d.speeding_strikes = 5
        p = h.app.ctx.profile
        money_before = p.money
        h.settle_current_delivery()
        h.read_settlement_lines()
        text = h.result.transcript_text
        m = re.search(r"you now have (-?[\d,]+)", text)
        if m and abs(float(m.group(1).replace(",", "")) - round(p.money)) > 1.0:
            findings.append(
                f"settlement said 'you now have {m.group(1)}' but the balance is {p.money:,.0f}"
            )
        m = re.search(r"Money after settlement: (-?[\d,]+) dollars", text)
        if m and abs(float(m.group(1).replace(",", "")) - round(p.money)) > 1.0:
            findings.append(
                f"settlement line said {m.group(1)} dollars after settlement, balance is "
                f"{p.money:,.0f}"
            )
        from freight_fate.states.driving_core import _speeding_settlement_fine

        fine = _speeding_settlement_fine(5)
        if f"{fine:,.0f}" not in text:
            findings.append(
                f"5 speeding strikes should cost {fine:,.0f} at settlement but no spoken "
                "line carries that amount"
            )
        delta = p.money - money_before
        if fine > 0 and delta >= 0.0 and "Net driver pay: 0 dollars" in text:
            findings.append(
                f"each strike warned '{fine:,.0f} dollars, due at delivery', and the "
                f"settlement reads 'Driver-responsibility charges: {fine:,.0f} dollars' -- "
                "but net pay is floored at zero, the balance never moved, and everything "
                "beyond the load's small wage was silently forgiven. Fines above the wage "
                "of a cheap load cost nothing, and the spoken ledger claims they were paid"
            )
        if p.career.deliveries != 1:
            findings.append(f"career shows {p.career.deliveries} deliveries after one run")
        verdict = "ODD" if findings else "CLEAN"
        note = (
            findings[0]
            if findings
            else (f"spoken settlement matches the ledger; balance {p.money:,.0f}")
        )
        return Outcome("settlement_spoken_balance", verdict, note, findings, h.result.transcript)


@scenario(
    "abandon_and_advance_cycle",
    "Take a pay advance, abandon at 99% complete; the cycle must never mint money.",
)
def _abandon_cycle():
    from freight_fate.models.economy import PAY_ADVANCE_LIMIT, pay_advance_grant

    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        ctx = rig.ctx
        p = ctx.profile
        from freight_fate.states.driving_pause_states import (
            AbandonJobConfirmationState,
            PauseMenuState,
        )

        d.trip.position_mi = d.trip.total_miles - 1.0  # one mile from the gate
        p.money = 5.0
        rep_before = p.career.reputation
        debt = 0.0
        minted = 0.0
        for _ in range(4):
            grant = pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load)
            if grant > 0.0:
                p.money += grant
                p.pay_advance += grant
                p.pay_advance_used_for_load = True
                minted += grant
            money_at_abandon = p.money
            ctx.push_state(d)
            ctx.push_state(PauseMenuState(ctx, d))
            abandon = AbandonJobConfirmationState(ctx, d)
            ctx.push_state(abandon)
            abandon._confirm()
            if abs((money_at_abandon - p.money) - 500.0) > 0.01:
                findings.append(
                    f"abandon penalty took {money_at_abandon - p.money:,.0f}, spoken text "
                    "promises five hundred"
                )
            minted -= 500.0
            debt = p.pay_advance
        if minted > 0.0:
            findings.append(f"advance-abandon cycle minted {minted:,.0f} dollars")
        if debt > PAY_ADVANCE_LIMIT + 0.01:
            findings.append(f"outstanding advance {debt:,.0f} exceeds the {PAY_ADVANCE_LIMIT} cap")
        if pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load) > 0.0 and (
            p.pay_advance >= PAY_ADVANCE_LIMIT
        ):
            findings.append("dispatcher kept advancing past the outstanding-advance cap")
        if p.career.reputation > rep_before - 5.0 + 0.01:
            findings.append("abandoning repeatedly cost no reputation")
        if rig.said("Job abandoned") == 0:
            findings.append("abandon confirmation spoke nothing")
        for line in rig.lines_with("returned to"):
            if "Buffalo" not in line:
                findings.append(f"abandon said '{line}' but the career is in Buffalo")
        return _outcome(
            "abandon_and_advance_cycle",
            rig,
            findings,
            f"4 abandons at 99%: cycle nets {minted:,.0f}, debt capped at {debt:,.0f}, "
            f"rep down {rep_before - p.career.reputation:.0f}",
        )
    finally:
        rig.close()


@scenario(
    "endorsement_wallet_edges",
    "Buy a course broke, then with the exact dollar; refusals and balances must be honest.",
)
def _endorsement_edges():
    rig = Rig()
    findings: list[str] = []
    try:
        from freight_fate.models.career import ENDORSEMENT_COURSE_COSTS
        from freight_fate.states.city_business import EndorsementCourseState

        ctx = rig.ctx
        p = ctx.profile
        state = EndorsementCourseState(ctx)
        key = next(k for k in ENDORSEMENT_COURSE_COSTS if k not in p.career.endorsements)
        cost = ENDORSEMENT_COURSE_COSTS[key]
        p.money = cost - 1.0
        state._buy(key)
        if key in p.career.endorsements:
            findings.append("a course sold itself one dollar short")
        if p.money != cost - 1.0:
            findings.append("a refused course still took money")
        refusal = rig.transcript[-1]
        if f"{cost:,.0f}" not in refusal or f"{cost - 1:,.0f}" not in refusal:
            findings.append(f"refusal does not state both numbers honestly: {refusal}")
        p.money = cost
        lines_before_purchase = len(rig.transcript)
        state._buy(key)
        if key not in p.career.endorsements:
            findings.append("exact-money purchase was refused")
        if p.money != 0.0:
            findings.append(f"exact-money purchase left {p.money}, expected exactly 0")
        # The purchase confirmation is followed by an achievement announcement,
        # so check every line this call actually spoke, not just the last one.
        purchase_lines = rig.transcript[lines_before_purchase:]
        if not any("You have 0 dollars left" in line for line in purchase_lines):
            findings.append(f"purchase did not speak the zero balance: {purchase_lines}")
        state._buy(key)
        if p.money != 0.0:
            findings.append("re-buying an owned endorsement charged money")
        return _outcome(
            "endorsement_wallet_edges",
            rig,
            findings,
            "broke refusal, exact-dollar purchase, and re-buy guard all honest",
        )
    finally:
        rig.close()


@scenario(
    "money_exact_zero_and_below",
    "Fines that land the balance on exactly $0, then below; escalation and ledger must agree.",
)
def _money_zero():
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_FINES, JAKE_ZONE_GRACE_S

    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        t = d.truck
        p = rig.ctx.profile
        p.money = float(JAKE_ZONE_FINES[0] + JAKE_ZONE_FINES[1])  # 450: two fines to zero
        d.trip.position_mi = 2.0
        t.engine_on = True
        t.transmission.gear = 8
        t.velocity_mps = 55.0 / MPH_PER_MPS
        d.trip.grade_at = lambda mile: 0.0
        for _ in range(3):
            t.engine_brake = True
            d._update_engine_brake_zone(0.1)
            d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 1.0)
            t.engine_brake = False
            d._update_engine_brake_zone(0.1)
        if d.jake_zone_fines != 3:
            findings.append(f"expected 3 citations, ledger has {d.jake_zone_fines}")
        expected_money = 450.0 - sum(JAKE_ZONE_FINES)
        if abs(p.money - expected_money) > 0.001:
            findings.append(f"balance {p.money} after 3 fines, expected {expected_money}")
        for fine, amount in zip(rig.lines_with("dollar fine"), JAKE_ZONE_FINES, strict=False):
            if f"{amount:,.0f}" not in fine:
                findings.append(f"citation spoke the wrong amount: {fine}")
        if not math.isfinite(p.money):
            findings.append("negative balance went non-finite")
        return _outcome(
            "money_exact_zero_and_below",
            rig,
            findings,
            f"450 -> 0 -> {p.money:,.0f}: escalation spoken right, negative balance survives",
        )
    finally:
        rig.close()


@scenario(
    "level_up_at_settlement_boundary",
    "XP one point under a level threshold, settle a delivery; the level-up must land exactly.",
)
def _level_up_boundary():
    """Level-ups only announce at delivery settlement (ArrivalState._settle),
    never mid-drive -- so the adversarial move is landing XP exactly on a
    threshold and checking the announcement, the audio cue, and the level
    count are all honest, including a delivery big enough to jump two
    thresholds at once.
    """
    from freight_fate.models.career import LEVEL_XP
    from freight_fate.states.driving_menu_states import ArrivalState

    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        p = rig.ctx.profile
        target_level = 5
        p.career.xp = LEVEL_XP[target_level - 1] - 1.0  # one XP short of the threshold
        p.career.deliveries = 0
        d.trip.position_mi = d.trip.total_miles
        d.trip.game_minutes = 0.0  # comfortably on time
        played: list[str] = []
        rig.ctx.audio.play = lambda name, *a, **k: played.append(name)
        arrival = ArrivalState(rig.ctx, d)  # settles synchronously in __init__
        if p.career.level != target_level:
            findings.append(
                f"one XP over the level-{target_level} threshold, career.level reads "
                f"{p.career.level}"
            )
        level_up_lines = [a for a in arrival._announcements if "Level up" in a]
        if not level_up_lines:
            findings.append("crossing a level threshold at settlement announced nothing")
        elif f"level {target_level}" not in level_up_lines[0]:
            findings.append(
                f"level-up line does not name level {target_level}: {level_up_lines[0]}"
            )
        # The audio cue and the spoken arrival screen only fire on enter(),
        # which is what push_state does for a real player landing here.
        rig.app.push_state(arrival)
        if "ui/level_up" not in played:
            findings.append("level-up audio cue (ui/level_up) did not play on arrival")

        # Now a delivery huge enough to skip levels entirely, the way
        # record_delivery itself computes the jump: no App or DrivingState
        # needed, this is the exact model call ArrivalState._settle makes.
        from freight_fate.models.career import Career

        skip_career = Career(xp=LEVEL_XP[2] - 1.0)  # level 2, one short of level 3
        level_before_skip = skip_career.level
        skip_messages = skip_career.record_delivery(3000.0, 5000.0, on_time=True, damage_pct=0.0)
        levels_crossed = skip_career.level - level_before_skip
        level_up_count = sum(1 for m in skip_messages if "Level up" in m)
        if levels_crossed >= 2 and level_up_count < levels_crossed:
            findings.append(
                f"one delivery pushed career level {level_before_skip} -> "
                f"{skip_career.level} ({levels_crossed} levels in one settlement) but only "
                f"{level_up_count} 'Level up!' line(s) were announced -- record_delivery's "
                "level-up message only ever reports the level it lands on, so every "
                "intermediate rank (and that rank's own unlock text) goes completely unspoken"
            )

        return _outcome(
            "level_up_at_settlement_boundary",
            rig,
            findings,
            f"exact-threshold level-up announced level {target_level} with its audio cue",
        )
    finally:
        rig.close()


@scenario(
    "owner_op_buyin_at_level_18_boundary",
    "Buy into owner-operator at exactly level 18 with exact capital; refuse it at level 17.",
)
def _owner_op_boundary():
    from freight_fate.models.business import (
        LEASED_OWNER_OPERATOR,
        OWNER_OPERATOR_BUY_IN,
        OWNER_OPERATOR_DELIVERIES,
        OWNER_OPERATOR_LEVEL,
        OWNER_OPERATOR_REPUTATION,
        OWNER_OPERATOR_WORKING_CAPITAL,
    )
    from freight_fate.models.career import LEVEL_XP
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import BusinessStatusState

    _fresh_data_dir()
    import pygame
    from speech_capture import speech_stub

    from freight_fate.app import App

    findings: list[str] = []
    app = App()
    try:
        app.ctx.profile = Profile(name="Owner Boundary", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 1]  # exactly level 18
        if p.career.level != OWNER_OPERATOR_LEVEL:
            findings.append(f"LEVEL_XP boundary did not land level {OWNER_OPERATOR_LEVEL} exactly")
        p.career.deliveries = OWNER_OPERATOR_DELIVERIES
        p.career.reputation = OWNER_OPERATOR_REPUTATION
        p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL  # exact dollar

        app.push_state(BusinessStatusState(app.ctx))
        menu = app.state
        target = next(
            (i for i, item in enumerate(menu.items) if "Buy into leased-on" in item.text), None
        )
        if target is None:
            findings.append("level 18 with exact capital: no buy-in menu item offered")
        else:
            while menu.index != target:
                menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, unicode=""))
            menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=""))
            if p.business_status != LEASED_OWNER_OPERATOR:
                findings.append("exact-level, exact-capital buy-in was refused")
            if abs(p.money - OWNER_OPERATOR_WORKING_CAPITAL) > 0.01:
                findings.append(
                    f"buy-in left {p.money:,.0f}, expected exactly the "
                    f"{OWNER_OPERATOR_WORKING_CAPITAL:,.0f} working capital"
                )
    finally:
        app.shutdown()

    # One level short, plenty of money: must be refused and name level 18.
    app2 = App()
    try:
        app2.ctx.profile = Profile(name="One Short", current_city="Chicago")
        p2 = app2.ctx.profile
        p2.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 2]  # level 17
        if p2.career.level != OWNER_OPERATOR_LEVEL - 1:
            findings.append("LEVEL_XP boundary did not land level 17 for the refusal case")
        p2.career.deliveries = OWNER_OPERATOR_DELIVERIES
        p2.career.reputation = OWNER_OPERATOR_REPUTATION
        p2.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL + 50_000.0
        money_before = p2.money
        spoken: list[str] = []
        app2.ctx.say = speech_stub(spoken)
        app2.push_state(BusinessStatusState(app2.ctx))
        menu2 = app2.state
        target2 = next(
            (i for i, item in enumerate(menu2.items) if "Buy into leased-on" in item.text), None
        )
        if target2 is not None:
            findings.append(
                "level 17 (one short) still offered the owner-operator buy-in menu item"
            )
        else:
            # Try the purchase method directly to confirm the refusal path.
            if hasattr(menu2, "_become_owner_operator"):
                menu2._become_owner_operator()
                if p2.business_status == LEASED_OWNER_OPERATOR:
                    findings.append("level 17 buy-in succeeded despite the level-18 gate")
                if p2.money != money_before:
                    findings.append("a refused buy-in at level 17 still took money")
                if spoken and f"level {OWNER_OPERATOR_LEVEL}" not in spoken[-1]:
                    findings.append(
                        f"refusal does not name level {OWNER_OPERATOR_LEVEL}: {spoken[-1]}"
                    )
    finally:
        app2.shutdown()

    verdict = "ODD" if findings else "CLEAN"
    note = (
        findings[0]
        if findings
        else (
            "level 18 with exact capital bought in for exactly the working capital left over; "
            "level 17 was refused and named the gate"
        )
    )
    return Outcome("owner_op_buyin_at_level_18_boundary", verdict, note, findings, [])


@scenario(
    "short_hop_streak_xp_farming",
    "Chain trivial-distance on-time deliveries; XP-per-real-minute dwarfs an honest long haul.",
)
def _short_hop_streak():
    """DELIVERY_COMPLETION_XP is a flat 150 regardless of distance, and the
    on-time streak bonus multiplies the WHOLE gained XP -- completion plus
    per-mile. A player who chains the shortest board-legal hauls (near
    MIN_JOB_DISTANCE_MI) racks up nearly as much XP per delivery as a long
    haul, for a fraction of the real playtime, and the streak bonus keeps
    compounding regardless of how trivial each hop was.
    """
    from freight_fate.models.career import Career
    from freight_fate.models.jobs import MIN_JOB_DISTANCE_MI

    findings: list[str] = []
    short_miles = MIN_JOB_DISTANCE_MI  # the shortest a real dispatch board offers
    long_miles = 500.0

    short_career = Career()
    for _ in range(10):
        short_career.record_delivery(short_miles, 300.0, on_time=True, damage_pct=0.0)
    short_xp = short_career.xp
    short_real_miles = short_miles * 10

    long_career = Career()
    long_career.record_delivery(long_miles, 1800.0, on_time=True, damage_pct=0.0)
    long_xp = long_career.xp

    # Ten legal short hops still cover fewer real miles than one long haul,
    # but a short haul plays out in a small fraction of the time a 500-mile
    # haul takes at the wheel -- the real-world axis that matters to a player
    # is playtime, not miles, and this harness cannot clock wall time, so
    # miles is used as the visible proxy for "how much less trip" the short
    # hops represent.
    xp_per_mile_short = short_xp / short_real_miles
    xp_per_mile_long = long_xp / long_miles
    ratio = xp_per_mile_short / xp_per_mile_long if xp_per_mile_long else float("inf")
    if ratio > 2.0:
        findings.append(
            f"10 legal {short_miles:.0f}-mile hops (streak-compounded) earn "
            f"{short_xp:,.0f} XP over {short_real_miles:.0f} real miles "
            f"({xp_per_mile_short:.2f} XP/mi) versus one {long_miles:.0f}-mile haul's "
            f"{long_xp:,.0f} XP ({xp_per_mile_long:.2f} XP/mi) -- {ratio:.1f}x the XP "
            "efficiency for the shortest, fastest-to-drive loads on the board, and the "
            "streak bonus keeps growing with each trivial hop"
        )
    if short_career.on_time_streak != 10:
        findings.append(
            f"streak should read 10 after 10 clean on-time hops, reads "
            f"{short_career.on_time_streak}"
        )

    verdict = "ODD" if findings else "CLEAN"
    note = (
        findings[0]
        if findings
        else (
            f"short-hop XP/mile ({xp_per_mile_short:.2f}) stayed within 2x of long-haul "
            f"XP/mile ({xp_per_mile_long:.2f})"
        )
    )
    return Outcome("short_hop_streak_xp_farming", verdict, note, findings, [])
