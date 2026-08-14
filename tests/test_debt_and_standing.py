"""Debt that actually costs something, and equipment that answers to standing.

The bug behind all of it: a tester sat 51,000 dollars in the hole, kept
gaining levels, and kept being handed better trucks, because the fleet tier
was a pure function of career level and every place that took money noted
that the balance "can go negative; never a game over".

The invariant that binds the whole change is the first test here: a clean,
solvent driver's game is not touched by any of it.
"""

from speech_capture import speech_stub

DAY = 24.0


def _profile(name="Dale", **kwargs):
    from freight_fate.models.profile import Profile

    p = Profile(name=name, current_city="Buffalo")
    for key, value in kwargs.items():
        setattr(p, key, value)
    return p


def _quiet(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    return spoken


# --- the invariant ----------------------------------------------------------


def test_a_clean_solvent_driver_is_untouched_by_any_of_this():
    """Every gate in this change is off for a driver running clean and square.

    Same experience to the float, same tractor, same trust line, no debt
    surface anywhere. If this ever fails, the 1.9 arc has moved for everyone.
    """
    from freight_fate.models import enforcement, solvency
    from freight_fate.models.career import Career, standing_xp_rate
    from freight_fate.models.carrier_fleet import (
        assigned_fleet_tier,
        eligible_fleet_tier,
        equipment_held_back,
        equipment_hold_text,
    )

    p = _profile()
    for level_xp in (0, 25_000, 152_000, 387_000):
        p.career.xp = level_xp
        assert enforcement.standing_band(p) == enforcement.TRUST_FULL
        assert standing_xp_rate(enforcement.standing_band(p)) == 1.0
        # Eligibility and assignment agree, so no truck is held back.
        assert assigned_fleet_tier(p).key == eligible_fleet_tier(p).key
        assert not equipment_held_back(p)
        assert equipment_hold_text(p) == ""
        # Nothing owed, nothing to warn about, nothing to say.
        assert solvency.debt_owed(p) == 0.0
        assert solvency.debt_rung(p) == 0
        assert solvency.debt_line(p) == ""
        assert solvency.debt_warning_line(p) == ""
        assert not solvency.company_termination_due(p)
        assert not solvency.repossession_due(p)
        # The trust line a clean driver hears is the one they always heard.
        assert enforcement.dispatch_trust_line(p) == enforcement.trust_text(p.career.reputation)

    # And the experience arithmetic is bit-for-bit what it was.
    plain, rated = Career(), Career()
    for _ in range(8):
        plain.record_delivery(420.0, pay=900.0, on_time=True, damage_pct=0.0)
        rated.record_delivery(420.0, pay=900.0, on_time=True, damage_pct=0.0, standing_rate=1.0)
    assert plain.xp == rated.xp


# --- standing gates equipment ----------------------------------------------


def test_the_yard_hands_over_the_lower_of_level_and_standing():
    from freight_fate.models import enforcement
    from freight_fate.models.carrier_fleet import (
        FLEET_TIERS,
        assigned_fleet_tier,
        eligible_fleet_tier,
    )

    p = _profile()
    p.career.xp = 387_000  # top of the ladder: eligible for the best iron
    assert eligible_fleet_tier(p).key == "first_pick"

    # Each band caps the assignment further down, and never above eligibility.
    seen = {}
    for reputation, expected in (
        (100.0, "first_pick"),
        (30.0, "long_haul"),  # guarded
        (20.0, "regional"),  # poor
        (10.0, "yard_standard"),  # last chance
    ):
        p.career.reputation = reputation
        seen[enforcement.standing_band(p)] = assigned_fleet_tier(p).key
        assert assigned_fleet_tier(p).key == expected
    assert len(seen) == 4  # all four bands exercised

    # A junior driver is never given *more* than their level earns by standing.
    p.career.xp = 0
    p.career.reputation = 100.0
    assert assigned_fleet_tier(p).key == FLEET_TIERS[0].key


def test_debt_alone_holds_the_iron_back_even_with_a_spotless_record():
    from freight_fate.models import enforcement
    from freight_fate.models.carrier_fleet import assigned_fleet_tier, equipment_held_back

    p = _profile()
    p.career.xp = 387_000
    p.career.reputation = 100.0
    assert not equipment_held_back(p)
    p.money = -5_000.0  # square on service, deep on money
    assert enforcement.trust_band(p.career.reputation) == enforcement.TRUST_FULL
    assert enforcement.standing_band(p) != enforcement.TRUST_FULL
    assert enforcement.standing_cause(p) == enforcement.CAUSE_DEBT
    assert equipment_held_back(p)
    assert assigned_fleet_tier(p).key != "first_pick"


def test_a_held_back_truck_names_the_earned_tier_the_cause_and_the_way_out():
    """The most frequent moment in the change, and the easiest to read as a bug."""
    from freight_fate.models.carrier_fleet import equipment_hold_text

    p = _profile()
    p.career.xp = 387_000
    p.money = -5_000.0
    verbose = equipment_hold_text(p)
    terse = equipment_hold_text(p, terse=True)
    for text in (verbose, terse):
        assert "first pick of the yard" in text  # what the level earns
        assert "5,000 dollars" in text  # the cause, in money
    assert "Clear it" in verbose  # and exactly what gives it back
    assert len(terse) < len(verbose)


def test_a_suspended_licence_holds_the_seat_but_an_old_violation_does_not():
    """Violations reach the band through reputation; only a suspension pins it.

    A hold no amount of good driving could clear for three game years would be
    a trap, so the serious-violation ladder is deliberately not a second gate.
    """
    from freight_fate.models import enforcement

    p = _profile()
    p.career.xp = 387_000
    p.driving_record.record_serious_violation(p.game_hours)
    assert not p.driving_record.suspended(p.game_hours)
    assert enforcement.licence_band(p) == enforcement.TRUST_FULL
    assert enforcement.standing_band(p) == enforcement.TRUST_FULL

    p.driving_record.record_serious_violation(p.game_hours)  # second: suspended
    assert p.driving_record.suspended(p.game_hours)
    assert enforcement.standing_band(p) == enforcement.TRUST_LAST_CHANCE
    assert enforcement.standing_cause(p) == enforcement.CAUSE_LICENCE
    assert "clears" in enforcement.standing_way_back(p)


def test_the_way_back_names_the_cause_rather_than_promising_clean_runs():
    """ "Clean on-time runs rebuild it" is a lie to a driver whose debt is the problem."""
    from freight_fate.models import enforcement

    p = _profile()
    p.money = -5_000.0
    way_back = enforcement.standing_way_back(p)
    assert "owe" in way_back and "Paying it down" in way_back
    assert way_back != "Clean on-time runs rebuild it."

    q = _profile()
    q.career.reputation = 20.0
    assert enforcement.standing_way_back(q) == "Clean on-time runs rebuild it."


# --- collection never takes the whole cheque (the zero-pay trap) ------------


def test_a_settlement_never_puts_more_than_a_quarter_toward_a_balance():
    """The trap: floor net at zero, collect everything, and working stops helping."""
    from freight_fate.models.solvency import collection_from_settlement, deductions_from_settlement

    assert collection_from_settlement(50_000.0, 1_000.0) == 250.0
    # Both deductions share one quarter, so three quarters always lands.
    collected, repaid = deductions_from_settlement(50_000.0, 1_500.0, 1_000.0)
    assert collected + repaid <= 250.0 + 0.01
    assert round(1_000.0 - collected - repaid, 2) == 750.0
    # A small balance is simply cleared, not stretched out.
    assert collection_from_settlement(40.0, 1_000.0) == 40.0


def test_with_nothing_owed_the_advance_repays_exactly_as_it_always_did():
    from freight_fate.models.solvency import deductions_from_settlement

    collected, repaid = deductions_from_settlement(0.0, 400.0, 1_000.0)
    assert (collected, repaid) == (0.0, 400.0)
    collected, repaid = deductions_from_settlement(0.0, 4_000.0, 1_000.0)
    assert (collected, repaid) == (0.0, 1_000.0)


def test_working_always_digs_a_driver_out_however_deep_they_are():
    """Fifty settlements at the cap must reduce the balance, not tread water."""
    from freight_fate.models.solvency import deductions_from_settlement

    balance = 51_000.0
    take_home_total = 0.0
    for _ in range(50):
        collected, _ = deductions_from_settlement(balance, 0.0, 1_200.0)
        assert collected > 0.0
        take_home_total += 1_200.0 - collected
        balance = round(balance - collected, 2)
    assert balance < 51_000.0
    assert take_home_total > 0.0  # and the driver ate every one of those weeks


def _run_a_settlement(app, *, money=1_000.0, fines_owed=0.0, pay_advance=0.0):
    """Drive one real delivery to settlement and hand back what it said and paid."""
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ArrivalState, DrivingState

    route = app.ctx.world.route_from_cities(["New York", "Philadelphia"])
    job = Job(
        CARGO_CATALOG["general"],
        18.0,
        "New York",
        "air cargo terminal",
        "Philadelphia",
        route.miles,
        1_400.0,
        14.0,
        destination_location="Philadelphia receiver",
    )
    app.ctx.profile = Profile(name="Settlement Audit", current_city="New York")
    p = app.ctx.profile
    p.money = money
    p.fines_owed = fines_owed
    p.pay_advance = pay_advance
    before = p.money
    driving = DrivingState(app.ctx, job, route, phase="delivery")
    driving.trip.position_mi = driving.trip.total_miles
    driving.trip.update(0.0)
    app.ctx.push_state(ArrivalState(app.ctx, driving))
    return p, round(p.money - before, 2), " ".join(app.state.summary_parts)


def test_a_settlement_under_collection_still_pays_the_driver(monkeypatch):
    """End to end, in the real settlement, against the trap that shipped.

    The old path added the whole carried balance to this load's charges, net
    pay floored at zero, and the shortfall carried again -- so every run after
    the first shortfall paid exactly nothing, forever.
    """
    from freight_fate.app import App

    app = App()
    try:
        _quiet(app, monkeypatch)
        clean_profile, clean_pay, clean_summary = _run_a_settlement(app)
        assert clean_pay > 0.0
        assert clean_profile.fines_owed == 0.0
        # A clean run says nothing about balances at all.
        assert "Balance owed" not in clean_summary

        indebted, paid, summary = _run_a_settlement(app, fines_owed=51_000.0)
        assert paid > 0.0, "a driver under collection must still be paid"
        assert paid >= clean_pay * 0.7  # three quarters of it, less rounding
        assert "Balance owed" in summary
        assert "three quarters always reaches you" in summary
        # The balance came down by what was collected, and no more.
        assert indebted.fines_owed < 51_000.0
        assert round(51_000.0 - indebted.fines_owed, 2) == round(clean_pay - paid, 2)
    finally:
        app.shutdown()


def test_collection_and_an_advance_together_still_leave_the_driver_paid(monkeypatch):
    """One capped budget covers both, so carrying both cannot zero a settlement.

    A big balance uses the whole of it and the advance simply waits, which is
    the right order: the advance cannot be drawn again while collection runs,
    so repaying it early would buy the driver nothing, and taking both would
    be exactly the spiral this change exists to close.
    """
    from freight_fate.app import App

    app = App()
    try:
        _quiet(app, monkeypatch)
        _clean, clean_pay, _ = _run_a_settlement(app)
        p, paid, summary = _run_a_settlement(app, fines_owed=20_000.0, pay_advance=1_500.0)
        assert paid > 0.0
        assert paid >= clean_pay * 0.7
        assert "Balance owed" in summary
        assert p.pay_advance == 1_500.0  # untouched: it waits its turn

        # A small balance clears inside the budget, and the advance gets the rest.
        q, q_paid, q_summary = _run_a_settlement(app, fines_owed=30.0, pay_advance=1_500.0)
        assert q.fines_owed == 0.0
        assert q.pay_advance < 1_500.0
        assert "Pay advance repaid" in q_summary
        assert q_paid >= clean_pay * 0.7
    finally:
        app.shutdown()


# --- warnings ---------------------------------------------------------------


def test_the_last_warning_leaves_two_of_this_driver_s_own_settlements():
    """A fixed dollar gap is worthless to a driver whose runs pay more than it."""
    from freight_fate.models.solvency import (
        average_settlement,
        debt_ceiling,
        final_rung_debt,
    )

    p = _profile()
    p.career.deliveries = 60
    p.career.total_earnings = 60 * 2_400.0  # a senior driver on long freight
    assert average_settlement(p) == 2_400.0
    gap = debt_ceiling(p) - final_rung_debt(p)
    assert gap >= 2 * average_settlement(p) - 0.01


def test_every_rung_is_reachable_and_each_names_the_ceiling_and_what_happens():
    from freight_fate.models.solvency import debt_ceiling, debt_rung, debt_warning_line

    p = _profile()
    ceiling = debt_ceiling(p)
    assert debt_rung(p) == 0
    seen = set()
    for owed in (200.0, ceiling * 0.55, ceiling * 0.95):
        p.money = -owed
        rung = debt_rung(p)
        seen.add(rung)
        verbose = debt_warning_line(p)
        terse = debt_warning_line(p, terse=True)
        assert verbose and terse
        # Terse may drop the "what brings it down" clause; it never drops the
        # ceiling number or the consequence.
        for text in (verbose, terse):
            assert f"{ceiling:,.0f}" in text
    assert seen == {1, 2, 3}
    assert "ends your employment" in debt_warning_line(p)


def test_a_rung_is_spoken_once_and_only_when_it_moves(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.solvency import debt_rung

    app = App()
    try:
        app.ctx.profile = _profile()
        p = app.ctx.profile
        record = p.driving_record
        assert record.debt_rung_heard == 0
        p.money = -200.0
        assert debt_rung(p) == 1
        # The record is what makes it speak once; the same rung twice is silent.
        record.debt_rung_heard = debt_rung(p)
        assert debt_rung(p) == record.debt_rung_heard
    finally:
        app.shutdown()


# --- company drivers: the ceiling is an ending of employment ---------------


def test_crossing_the_ceiling_ends_a_company_driver_s_employment():
    from freight_fate.models import solvency
    from freight_fate.models.enforcement import LAST_CHANCE_CARRIER_KEY

    p = _profile()
    p.career.xp = 152_000
    former = p.carrier_name
    p.money = -solvency.company_debt_ceiling(p) - 1.0
    assert solvency.company_termination_due(p)

    lines = solvency.apply_company_termination(p)
    joined = " ".join(lines)
    assert p.carrier_key == LAST_CHANCE_CARRIER_KEY
    assert p.driving_record.carrier_terminations == 1
    # The balance is settled: arriving at the next fleet still carrying the
    # debt that cost the last seat is a career on rails to lose this one too.
    assert solvency.debt_owed(p) == 0.0
    assert p.money >= 0.0
    assert former in joined
    assert "ended your employment" in joined
    assert "keep your career level" in joined
    # Never a dead end, and never these words.
    assert "dispatch board" in joined.lower()
    for banned in ("game over", "career over", "you failed", "start over", "bankrupt"):
        assert banned not in joined.lower()


def test_a_terminated_driver_can_still_get_a_load_and_still_earn():
    """The loop must not close: a board offer and take-home pay always exist."""
    from freight_fate.models import solvency
    from freight_fate.models.enforcement import board_offers_for_reputation

    p = _profile()
    p.career.xp = 152_000
    p.career.reputation = 0.0
    p.money = -solvency.company_debt_ceiling(p) - 1.0
    solvency.apply_company_termination(p)
    assert board_offers_for_reputation(8, p.career.reputation) >= 1
    collected, repaid = solvency.deductions_from_settlement(p.fines_owed, p.pay_advance, 900.0)
    assert 900.0 - collected - repaid > 0.0


def test_debt_stops_growing_at_the_fleet_that_hires_anyone():
    """Nowhere further down, so the ceiling holds rather than dangling."""
    from freight_fate.models import solvency
    from freight_fate.models.enforcement import (
        LAST_CHANCE_CARRIER_KEY,
        LAST_CHANCE_CARRIER_NAME,
    )

    p = _profile()
    p.carrier_key = LAST_CHANCE_CARRIER_KEY
    p.carrier_name = LAST_CHANCE_CARRIER_NAME
    p.money = -3_000.0
    p.fines_owed = 40_000.0
    assert solvency.hard_capped(p)
    assert not solvency.company_termination_due(p)  # never fires here

    written_off = solvency.apply_hard_cap(p)
    assert written_off > 0.0
    assert solvency.debt_owed(p) <= solvency.debt_ceiling(p) + 0.01
    assert "holds it there" in solvency.debt_line(p)


# --- owner-operators: the lender takes the truck ---------------------------


def _owner_operator(truck="highline_sleeper"):
    from freight_fate.models.business import LEASED_OWNER_OPERATOR

    p = _profile()
    p.career.xp = 202_000
    p.career.reputation = 85.0
    p.business_status = LEASED_OWNER_OPERATOR
    p.truck = truck
    p.owned_trucks = [truck]
    return p


def test_the_threshold_is_what_the_tractor_would_bring_at_sale():
    from freight_fate.models.solvency import (
        REPOSSESSION_EQUITY_SHARE,
        repossession_threshold,
        tractor_value,
    )
    from freight_fate.models.trucks import TRUCK_CATALOG

    cheap = _owner_operator("hand_me_down_sleeper")
    dear = _owner_operator("presidential_sleeper")
    assert tractor_value(dear) > tractor_value(cheap)
    # A better truck stands behind a bigger loan, so it carries further.
    assert repossession_threshold(dear) > repossession_threshold(cheap)
    expected = TRUCK_CATALOG["presidential_sleeper"].price * REPOSSESSION_EQUITY_SHARE
    assert repossession_threshold(dear) == round(expected, 2)


def test_negative_equity_costs_the_truck_and_lands_on_a_payroll():
    from freight_fate.models import solvency
    from freight_fate.models.business import COMPANY_DRIVER

    p = _owner_operator()
    assert not solvency.repossession_due(p)
    p.money = -solvency.repossession_threshold(p) - 1.0
    assert solvency.repossession_due(p)

    lines = solvency.apply_repossession(p)
    joined = " ".join(lines)
    assert p.business_status == COMPANY_DRIVER
    assert p.owned_trucks == []
    assert p.driving_record.repossessions == 1
    assert solvency.debt_owed(p) == 0.0
    assert "taken it back" in joined
    assert "keep your career level" in joined
    assert "owner-operator path is still open" in joined
    for banned in ("game over", "career over", "you failed", "start over", "bankrupt"):
        assert banned not in joined.lower()


def test_repossession_always_lands_at_a_carrier_that_will_hire():
    """Losing the truck and the seat in the same breath would leave nowhere to drive."""
    from freight_fate.models import solvency
    from freight_fate.models.enforcement import (
        LAST_CHANCE_CARRIER_KEY,
        REPUTATION_TERMINATION,
    )

    p = _owner_operator()
    p.career.reputation = REPUTATION_TERMINATION - 1.0
    p.money = -solvency.repossession_threshold(p) - 1.0
    solvency.apply_repossession(p)
    assert p.carrier_key == LAST_CHANCE_CARRIER_KEY
    # And the driver is in a real tractor, not an empty key.
    from freight_fate.models.trucks import TRUCK_CATALOG

    assert p.active_truck_key() in TRUCK_CATALOG


def test_an_owner_operator_in_good_standing_keeps_their_own_carrier():
    from freight_fate.models import solvency
    from freight_fate.models.enforcement import LAST_CHANCE_CARRIER_KEY

    p = _owner_operator()
    p.carrier_name = "Great Plains Freight"
    p.carrier_key = "great_plains"
    p.money = -solvency.repossession_threshold(p) - 1.0
    solvency.apply_repossession(p)
    assert p.carrier_key != LAST_CHANCE_CARRIER_KEY
    assert p.carrier_key == "great_plains"


# --- experience slows, but never stops -------------------------------------


def test_experience_slows_by_band_and_never_reaches_zero():
    from freight_fate.models import enforcement
    from freight_fate.models.career import STANDING_XP_RATE, standing_xp_rate

    bands = (
        enforcement.TRUST_FULL,
        enforcement.TRUST_GUARDED,
        enforcement.TRUST_POOR,
        enforcement.TRUST_LAST_CHANCE,
    )
    # The bands the code keys on are exactly the bands enforcement defines.
    assert set(STANDING_XP_RATE) == set(bands)
    rates = [standing_xp_rate(band) for band in bands]
    assert rates[0] == 1.0  # a clean driver's arc does not move
    assert rates == sorted(rates, reverse=True)
    assert all(0.0 < rate <= 1.0 for rate in rates)
    assert rates[-1] >= 0.5  # a driver digging out still makes real progress


def test_a_slowed_career_still_levels_up():
    from freight_fate.models.career import Career, standing_xp_rate

    slowed = Career()
    rate = standing_xp_rate("last chance")
    for _ in range(30):
        slowed.record_delivery(500.0, pay=800.0, on_time=True, damage_pct=0.0, standing_rate=rate)
    assert slowed.level > 1


def test_the_slowdown_is_said_in_words_and_never_as_a_number():
    from freight_fate.models.career import xp_rate_clause, xp_rate_settlement_clause

    assert xp_rate_clause("full") == ""
    assert xp_rate_settlement_clause("full") == ""
    for band in ("guarded", "poor", "last chance"):
        sentence = xp_rate_clause(band)
        clause = xp_rate_settlement_clause(band)
        assert band in sentence and "more slowly" in sentence
        assert band in clause and "slower rate" in clause
        for text in (sentence, clause):
            for banned in ("percent", "multiplier", "penalty", "x", "0."):
                assert banned not in text.replace("experience", "e")


def test_slowed_experience_stays_under_the_exported_cloud_ceiling():
    from freight_fate.models.career import Career, standing_xp_rate
    from freight_fate.profile_integrity_invariants import invariant_data

    data = invariant_data()
    career = Career()
    for _ in range(25):
        career.record_delivery(
            700.0,
            pay=0.0,
            on_time=True,
            damage_pct=0.0,
            cargo_class_mult=1.5,
            standing_rate=standing_xp_rate("guarded"),
        )
    ceiling = (
        career.deliveries * data["xpFlatPerDelivery"] + career.total_miles * (data["xpPerMileMax"])
    )
    assert career.xp <= ceiling


# --- the pay advance cannot become the debt spiral -------------------------


def test_no_advance_while_a_balance_is_already_being_collected():
    """It is only ever offered under ten dollars of cash, so it would be offered forever."""
    from freight_fate.models.solvency import advance_refused_reason, collection_active

    p = _profile()
    p.money = 2.0
    assert advance_refused_reason(p) == ""
    assert not collection_active(p)

    p.fines_owed = 3_000.0
    reason = advance_refused_reason(p)
    assert collection_active(p)
    assert "will not front you cash" in reason
    assert "3,000 dollars" in reason
    assert "three quarters" in reason  # and what they do still get


def test_the_terminal_stops_offering_an_advance_under_collection(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        app.ctx.profile = _profile()
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        p.money = 2.0
        menu = CityMenuState(app.ctx)
        assert menu._pay_advance_available()
        p.fines_owed = 3_000.0
        assert not menu._pay_advance_available()
        assert not any("pay advance" in item.text.lower() for item in menu.build_items())
    finally:
        app.shutdown()


# --- the two big moments are reviewable, not one-shot ----------------------


def test_the_setback_lands_as_a_re_readable_screen_that_escape_acknowledges(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models import solvency
    from freight_fate.states.career_setback import CareerSetbackNoticeState

    app = App()
    try:
        app.ctx.profile = _profile()
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        p.career.xp = 152_000
        p.money = -solvency.company_debt_ceiling(p) - 1.0
        lines = solvency.apply_company_termination(p)
        assert solvency.setback_pending(p)

        notice = CareerSetbackNoticeState(app.ctx)
        items = notice.build_items()
        # Every line is its own arrowable item, plus a way out.
        assert [item.text for item in items[:-1]] == lines
        assert items[-1].text == "Continue"
        notice.announce_entry()
        assert any("ended your employment" in line for line in spoken)

        app.ctx.push_state(notice)
        notice.go_back()  # Escape acknowledges; nobody is ever stuck here
        assert not solvency.setback_pending(p)
    finally:
        app.shutdown()


def test_the_notice_survives_a_save_and_reload():
    from freight_fate.models import solvency
    from freight_fate.models.profile import Profile

    p = _profile()
    p.career.xp = 152_000
    p.money = -solvency.company_debt_ceiling(p) - 1.0
    solvency.apply_company_termination(p)
    reloaded = Profile.from_dict(p.to_dict())
    assert reloaded.driving_record.setback_notice_kind == "termination"
    assert reloaded.driving_record.setback_notice_lines == p.driving_record.setback_notice_lines
    assert solvency.setback_pending(reloaded)


def test_a_setback_only_ever_fires_at_the_terminal(monkeypatch):
    """Both of these take the tractor the driver is sitting in."""
    from freight_fate.app import App
    from freight_fate.models import solvency
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        app.ctx.profile = _profile()
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        p.career.xp = 152_000
        p.money = -solvency.company_debt_ceiling(p) - 1.0
        # Walking into the terminal is what fires it, and the notice takes the
        # screen ahead of everything else the terminal had to say.
        app.ctx.push_state(CityMenuState(app.ctx))
        assert type(app.state).__name__ == "CareerSetbackNoticeState"
        assert p.carrier_key == "great_lakes_training"

        app.state.go_back()  # Escape: back to the terminal, and it stays gone
        assert type(app.state).__name__ == "CityMenuState"
        assert not solvency.setback_pending(p)

        # Nothing on the driving side takes the seat: the check lives here.
        import freight_fate.states.driving_menu_states as dms

        assert not hasattr(dms.ArrivalState, "_check_career_setback")
    finally:
        app.shutdown()


# --- a level-up must not promise a truck the yard is withholding -----------


def test_a_level_up_does_not_promise_iron_the_yard_is_holding_back(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.carrier_fleet import WITHHELD_UNLOCK_TAIL
    from freight_fate.states.driving_menu_states import ArrivalState

    app = App()
    try:
        app.ctx.profile = _profile()
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        p.career.xp = 40_000  # level 11
        p.money = -5_000.0
        rank_unlock = p.career.rank.unlock
        announcements = [f"Level up! You are now level 11: X. Unlock: {rank_unlock}"]
        ArrivalState._rewrite_unlock_promise(type("S", (), {"ctx": app.ctx})(), announcements)
        assert WITHHELD_UNLOCK_TAIL in announcements[0]
        assert rank_unlock in announcements[0]  # the true half still stands
    finally:
        app.shutdown()


def test_a_withheld_promotion_does_not_hand_over_a_freshly_serviced_truck():
    """No fuel, no reset wear, no wash: nothing changed hands."""
    from freight_fate.models.carrier_fleet import withheld_promotion_text

    p = _profile()
    p.career.xp = 152_000
    p.money = -5_000.0
    text = withheld_promotion_text(p)
    assert "exactly as it stands" in text
    assert "fueled" not in text and "washed" not in text


# --- out-of-pocket payoff helpers -------------------------------------------


def _payer(money, owed):
    p = _profile()
    p.money = money
    p.fines_owed = owed
    return p


def test_payoff_options_full_coverage():
    from freight_fate.models.solvency import out_of_pocket_options

    opts = dict(out_of_pocket_options(_payer(money=5_000.0, owed=1_000.0)))
    assert opts["all"] == 1_000.0
    assert opts["half"] == 500.0
    # cushion amount (4800) exceeds the balance, so it clamps to it and
    # duplicates "all" -- deduplicated away.
    assert "cushion" not in opts


def test_payoff_options_partial_coverage():
    from freight_fate.models.solvency import out_of_pocket_options

    opts = dict(out_of_pocket_options(_payer(money=800.0, owed=2_000.0)))
    assert "all" not in opts
    assert opts["half"] == 800.0  # half the balance is 1000, capped at cash
    assert opts["cushion"] == 600.0  # cash minus the 200 cushion


def test_payoff_options_hidden_when_broke_or_clear():
    from freight_fate.models.solvency import out_of_pocket_options

    assert out_of_pocket_options(_payer(money=9.0, owed=500.0)) == []
    assert out_of_pocket_options(_payer(money=500.0, owed=0.5)) == []
    assert out_of_pocket_options(_payer(money=-50.0, owed=500.0)) == []


def test_pay_out_of_pocket_clamps_and_clears():
    from freight_fate.models.solvency import pay_out_of_pocket

    p = _payer(money=800.0, owed=600.0)
    assert pay_out_of_pocket(p, 600.0) == 600.0
    assert p.fines_owed == 0.0
    assert p.money == 200.0

    p = _payer(money=100.0, owed=600.0)
    assert pay_out_of_pocket(p, 999.0) == 100.0  # never below zero cash
    assert p.money == 0.0
    assert p.fines_owed == 500.0

    p = _payer(money=100.0, owed=600.0)
    assert pay_out_of_pocket(p, 0.0) == 0.0  # no-op stays a no-op


# --- debt lines point at cash payoff -------------------------------------------


def test_debt_lines_point_at_out_of_pocket_payoff():
    from freight_fate.models import solvency

    POINTER = "You can also pay it down from cash at any terminal or truck stop."

    p = _payer(money=500.0, owed=1_000.0)  # rung 1 for a fresh company driver
    assert POINTER in solvency.debt_warning_line(p)
    assert POINTER not in solvency.debt_warning_line(p, terse=True)
    assert POINTER in solvency.debt_line(p)


def test_debt_lines_point_at_out_of_pocket_payoff_when_hard_capped():
    """A hard-capped driver has nowhere further down to fall, but the cash
    payoff pointer is still true for them and must still be spoken."""
    from freight_fate.models import enforcement, solvency

    POINTER = "You can also pay it down from cash at any terminal or truck stop."

    p = _payer(money=500.0, owed=40_000.0)
    p.carrier_key = enforcement.LAST_CHANCE_CARRIER_KEY
    assert solvency.hard_capped(p)

    assert POINTER in solvency.debt_warning_line(p)
    assert POINTER not in solvency.debt_warning_line(p, terse=True)
    assert POINTER in solvency.debt_line(p)


# --- the terminal menu item and PayDebtState --------------------------------


def test_the_terminal_only_offers_payoff_when_something_is_owed(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        app.ctx.profile = _payer(money=5_000.0, owed=1_000.0)
        _quiet(app, monkeypatch)
        menu = CityMenuState(app.ctx)
        assert any(
            item.text == "Pay down what you owe: 1,000 dollars owed" for item in menu.build_items()
        )

        app.ctx.profile.fines_owed = 0.0
        assert not any(item.text.startswith("Pay down what you owe") for item in menu.build_items())
    finally:
        app.shutdown()


def test_paying_it_all_off_clears_the_balance_and_says_so(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models import solvency
    from freight_fate.states.city import PayDebtState

    app = App()
    try:
        app.ctx.profile = _payer(money=5_000.0, owed=1_000.0)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        state = PayDebtState(app.ctx)
        items = state.build_items()
        pay_it_all = next(item for item in items if item.text.startswith("Pay it all"))
        pay_it_all.action()

        assert p.fines_owed == 0.0
        assert solvency.debt_owed(p) == 0.0
        assert p.money == 4_000.0
        assert any("your account is clear" in line for line in spoken)
    finally:
        app.shutdown()


def test_paying_it_all_off_speaks_the_clear_confirmation_last(monkeypatch):
    """Popping back to the terminal fires the parent menu's own interrupt=True
    entry announcement. The clear confirmation must be spoken after that pop,
    so it survives as the last thing heard instead of being cut off by it."""
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState, PayDebtState

    app = App()
    try:
        app.ctx.profile = _payer(money=5_000.0, owed=1_000.0)
        events: list[tuple[str, bool]] = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(events, with_interrupt=True))
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events, with_interrupt=True))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)

        app.push_state(CityMenuState(app.ctx))
        state = PayDebtState(app.ctx)
        app.push_state(state)
        events.clear()  # only the pay-it-all action's own speech matters here
        items = state.build_items()
        pay_it_all = next(item for item in items if item.text.startswith("Pay it all"))
        pay_it_all.action()

        assert events, "expected the clear confirmation to be spoken"
        last_text, last_interrupt = events[-1]
        assert "your account is clear" in last_text
        assert last_interrupt is True
    finally:
        app.shutdown()


def test_paying_half_leaves_the_rest_owed_and_says_the_remainder(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models import solvency
    from freight_fate.states.city import PayDebtState

    app = App()
    try:
        app.ctx.profile = _payer(money=5_000.0, owed=1_000.0)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        state = PayDebtState(app.ctx)
        items = state.build_items()
        pay_half = next(item for item in items if item.text.startswith("Pay half"))
        pay_half.action()

        assert p.fines_owed == 500.0
        assert solvency.debt_owed(p) == 500.0
        assert p.money == 4_500.0
        assert any("500" in line and "still owed" in line for line in spoken)
    finally:
        app.shutdown()


# --- the same payoff item at truck stops -------------------------------------


def _rest_driving(app, money, owed):
    from freight_fate.models.business import LEASED_OWNER_OPERATOR
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = _payer(money=money, owed=owed)
    app.ctx.profile.current_city = "Denver"
    app.ctx.profile.business_status = LEASED_OWNER_OPERATOR
    app.ctx.profile.owned_trucks = ["rig"]
    job = Job(
        CARGO_CATALOG["general"], 12.0, "Denver", "yard", "Salt Lake City", 200.0, 900.0, 12.0
    )
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, job, route, trip_seed=99, start_hour=10.0)
    app.push_state(driving)
    return driving


def _rest_stop(driving, name="Pilot Travel Center"):
    from types import SimpleNamespace

    return SimpleNamespace(
        name=name,
        at_mi=driving.trip.position_mi,
        type="travel_center",
        actions=("fuel", "break"),
        services=(),
        parking="limited",
        exit_label="",
        spoken_name=name,
        parking_text="limited truck parking",
    )


def test_the_rest_stop_only_offers_payoff_when_something_is_owed(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        _quiet(app, monkeypatch)
        driving = _rest_driving(app, money=5_000.0, owed=1_000.0)
        state = RestStopState(app.ctx, driving, _rest_stop(driving))
        assert any(
            item.text == "Pay down what you owe: 1,000 dollars owed" for item in state.build_items()
        )

        app.ctx.profile.fines_owed = 0.0
        assert not any(
            item.text.startswith("Pay down what you owe") for item in state.build_items()
        )
    finally:
        app.shutdown()


def test_the_rest_stop_payoff_item_pushes_pay_debt_state(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import PayDebtState
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        _quiet(app, monkeypatch)
        driving = _rest_driving(app, money=5_000.0, owed=1_000.0)
        state = RestStopState(app.ctx, driving, _rest_stop(driving))
        item = next(i for i in state.build_items() if i.text.startswith("Pay down what you owe"))
        item.action()

        assert type(app.state).__name__ == "PayDebtState"
        assert isinstance(app.state, PayDebtState)
    finally:
        app.shutdown()
