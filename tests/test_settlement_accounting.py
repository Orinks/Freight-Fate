"""Settlement accounting regression tests for neutral carrier charges."""

import pytest

from freight_fate.models.business import (
    COMPANY_DRIVER,
    LEASED_OWNER_OPERATOR,
    build_business_settlement,
)


def _job(
    cargo_key="electronics",
    *,
    origin="New York",
    destination="Philadelphia",
    destination_type="dry_warehouse",
    pay=2500.0,
    deadline=12.0,
    distance=78.0,
):
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    return Job(
        CARGO_CATALOG[cargo_key],
        18.0,
        origin,
        f"{origin} pickup",
        destination,
        distance,
        pay,
        deadline,
        origin_type="air_cargo",
        destination_location=f"{destination} receiver",
        destination_type=destination_type,
    )


def _settle(
    app,
    job,
    route_cities,
    *,
    money=1000.0,
    speeding_strikes=0,
    pay_advance=0.0,
    pay_advance_used_for_load=False,
    business_status=COMPANY_DRIVER,
):
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ArrivalState, DrivingState
    from freight_fate.states.driving_menu_states import _settlement_hours

    app.ctx.profile = Profile(name="Settlement Audit", current_city=job.origin)
    app.ctx.profile.money = money
    app.ctx.profile.business_status = business_status
    app.ctx.profile.pay_advance = pay_advance
    app.ctx.profile.pay_advance_used_for_load = pay_advance_used_for_load
    route = app.ctx.world.route_from_cities(route_cities)
    driving = DrivingState(app.ctx, job, route, phase="delivery")
    driving.speeding_strikes = speeding_strikes
    driving.trip.position_mi = driving.trip.total_miles
    driving.trip.update(0.0)
    gross = job.payout(_settlement_hours(driving), 0.0)
    app.ctx.push_state(ArrivalState(app.ctx, driving))
    return gross, " ".join(app.state.summary_parts)


def test_carrier_paid_charges_do_not_increase_player_progression():
    from freight_fate.app import App

    app = App()
    try:
        job = _job(destination_type="retail_distribution")
        gross, summary = _settle(app, job, ["New York", "Philadelphia"], money=1000.0)
        carrier_charges = 30.0 + 185.0
        expected = build_business_settlement(
            COMPANY_DRIVER, job, gross, on_time=True, driver_charges=0.0
        )

        assert f"Carrier-paid or reimbursed charges {carrier_charges:,.0f} dollars" in summary
        assert app.ctx.profile.money == pytest.approx(1000.0 + expected.net_before_advance)
        assert app.ctx.profile.career.total_earnings == pytest.approx(expected.net_before_advance)
        from freight_fate.models.career import xp_class_multiplier

        assert app.ctx.profile.career.xp == pytest.approx(
            job.distance_mi * 1.2 * xp_class_multiplier(job.cargo)
        )
        assert app.ctx.profile.career.reputation == pytest.approx(52.0)
    finally:
        app.shutdown()


def test_delivery_adds_tire_wear_and_road_grime():
    from freight_fate.app import App

    app = App()
    try:
        job = _job(destination_type="retail_distribution")
        _gross, summary = _settle(app, job, ["New York", "Philadelphia"], money=1000.0)

        assert app.ctx.profile.tire_wear_pct > 0.0
        assert app.ctx.profile.road_grime_pct > 0.0
        assert "tire wear" in summary
        assert "road grime" in summary
    finally:
        app.shutdown()


def test_driver_responsibility_charges_reduce_driver_pay_but_not_carrier_charges():
    from freight_fate.app import App

    app = App()
    try:
        job = _job(destination_type="retail_distribution")
        gross, summary = _settle(
            app,
            job,
            ["New York", "Philadelphia"],
            money=1000.0,
            speeding_strikes=2,
        )
        expected = build_business_settlement(
            COMPANY_DRIVER, job, gross, on_time=True, driver_charges=160.0
        )

        assert "Carrier-paid or reimbursed charges 215 dollars" in summary
        assert "Driver-responsibility charges 160 dollars" in summary
        assert app.ctx.profile.money == pytest.approx(1000.0 + expected.net_before_advance)
        assert app.ctx.profile.career.total_earnings == pytest.approx(expected.net_before_advance)
    finally:
        app.shutdown()


def test_owner_operator_settlement_deducts_business_costs():
    from freight_fate.app import App

    app = App()
    try:
        job = _job(destination_type="retail_distribution")
        gross, summary = _settle(
            app,
            job,
            ["New York", "Philadelphia"],
            money=1000.0,
            business_status=LEASED_OWNER_OPERATOR,
        )
        expected = build_business_settlement(
            LEASED_OWNER_OPERATOR, job, gross, on_time=True, driver_charges=0.0
        )

        assert "Business status: leased-on owner-operator" in summary
        assert "Owner-operator business costs" in summary
        assert expected.business_charge_total > 0
        assert app.ctx.profile.money == pytest.approx(1000.0 + expected.net_before_advance)
        assert app.ctx.profile.career.total_earnings == pytest.approx(expected.net_before_advance)
    finally:
        app.shutdown()


def test_pay_advance_is_repaid_from_settlement():
    from freight_fate.app import App

    app = App()
    try:
        job = _job(destination_type="retail_distribution")
        gross, summary = _settle(
            app,
            job,
            ["New York", "Philadelphia"],
            money=-200.0,
            pay_advance=500.0,
        )
        expected = build_business_settlement(
            COMPANY_DRIVER, job, gross, on_time=True, driver_charges=0.0
        )

        assert "Pay advance repaid from this settlement: 500 dollars" in summary
        assert app.ctx.profile.pay_advance == pytest.approx(0.0)
        assert app.ctx.profile.pay_advance_used_for_load is False
        # Net pay is reduced by the repaid advance; the bank reflects it.
        assert app.ctx.profile.money == pytest.approx(-200.0 + expected.net_before_advance - 500.0)
        assert app.ctx.profile.career.total_earnings == pytest.approx(
            expected.net_before_advance - 500.0
        )
    finally:
        app.shutdown()


def test_settlement_time_cannot_be_faster_than_practical_road_average():
    from freight_fate.app import App

    app = App()
    try:
        job = _job(
            origin="Austin",
            destination="San Antonio",
            destination_type="retail_distribution",
            pay=1800.0,
            deadline=4.0,
            distance=79.0,
        )
        _gross, summary = _settle(
            app,
            job,
            ["Austin", "San Antonio"],
            money=1000.0,
        )

        assert "to San Antonio in 1.4 hours" in summary
        assert "in 0.0 hours" not in summary
        assert app.ctx.profile.career.total_miles == pytest.approx(79.0)
    finally:
        app.shutdown()


def test_pay_advance_repayment_never_drives_net_pay_negative():
    from freight_fate.app import App

    app = App()
    try:
        # A small payout against a larger outstanding advance: repay only what
        # the settlement can cover, carry the rest, and never claw the bank
        # below the settlement itself.
        job = _job(destination_type="retail_distribution", pay=300.0)
        gross, summary = _settle(
            app,
            job,
            ["New York", "Philadelphia"],
            money=0.0,
            pay_advance=1500.0,
        )

        expected = build_business_settlement(
            COMPANY_DRIVER, job, gross, on_time=True, driver_charges=0.0
        )
        repaid = min(1500.0, expected.net_before_advance)
        assert app.ctx.profile.pay_advance == pytest.approx(1500.0 - repaid)
        assert app.ctx.profile.money == pytest.approx(expected.net_before_advance - repaid)
        assert app.ctx.profile.money >= 0.0
        assert "still outstanding" in summary
    finally:
        app.shutdown()


def test_pay_advance_load_cooldown_resets_at_settlement():
    from freight_fate.app import App

    app = App()
    try:
        job = _job(destination_type="retail_distribution")
        _settle(
            app,
            job,
            ["New York", "Philadelphia"],
            money=-200.0,
            pay_advance=500.0,
            pay_advance_used_for_load=True,
        )

        assert app.ctx.profile.pay_advance_used_for_load is False
    finally:
        app.shutdown()


def test_restored_toll_charges_do_not_duplicate_or_pay_out():
    from freight_fate.app import App
    from freight_fate.models.jobs import job_payload
    from freight_fate.models.profile import Profile
    from freight_fate.sim.trip import TripEventKind
    from freight_fate.states.driving import ArrivalState, DrivingState

    app = App()
    try:
        job = _job()
        app.ctx.profile = Profile(name="Old Toll Save", current_city="New York")
        app.ctx.profile.money = 1000.0
        snapshot = {
            "kind": "delivery",
            "job": job_payload(job),
            "route_cities": ["New York", "Philadelphia"],
            "trip_seed": 1234,
            "start_hour": 8.0,
            "position_mi": 79.0,
            "game_minutes": 45.0,
            "toll_charges": [
                {"name": "New Jersey Turnpike ticket entry", "amount": 18.0},
                {"name": "Delaware River Turnpike Toll Bridge settlement point", "amount": 12.0},
            ],
            "start_damage": 0.0,
            "speeding_strikes": 0,
        }

        resumed = DrivingState.from_snapshot(app.ctx, snapshot)
        assert resumed is not None
        assert resumed.trip.toll_expense == pytest.approx(30.0)
        events = resumed.trip.update(0.0)
        assert resumed.trip.toll_expense == pytest.approx(30.0)
        assert not [event for event in events if event.kind == TripEventKind.TOLL_CHARGED]

        from freight_fate.states.driving_menu_states import _settlement_hours

        gross = job.payout(_settlement_hours(resumed), 0.0)
        expected = build_business_settlement(
            COMPANY_DRIVER, job, gross, on_time=True, driver_charges=0.0
        )
        app.ctx.push_state(ArrivalState(app.ctx, resumed))
        assert app.ctx.profile.money == pytest.approx(1000.0 + expected.net_before_advance)
        assert app.ctx.profile.career.total_earnings == pytest.approx(expected.net_before_advance)
    finally:
        app.shutdown()


def test_toll_route_does_not_pay_more_than_equal_non_toll_route():
    from freight_fate.app import App

    app = App()
    try:
        toll_job = _job(origin="New York", destination="Philadelphia")
        non_toll_job = _job(origin="Chicago", destination="Indianapolis")

        toll_gross, toll_summary = _settle(
            app,
            toll_job,
            ["New York", "Philadelphia"],
            money=1000.0,
            business_status=LEASED_OWNER_OPERATOR,
        )
        toll_money = app.ctx.profile.money
        toll_earnings = app.ctx.profile.career.total_earnings
        non_toll_gross, non_toll_summary = _settle(
            app,
            non_toll_job,
            ["Chicago", "Indianapolis"],
            money=1000.0,
            business_status=LEASED_OWNER_OPERATOR,
        )

        assert toll_gross == pytest.approx(non_toll_gross)
        assert "Carrier-paid or reimbursed charges 30 dollars" in toll_summary
        assert "Carrier-paid or reimbursed charges 0 dollars" in non_toll_summary
        assert toll_money == pytest.approx(app.ctx.profile.money)
        assert toll_earnings == pytest.approx(app.ctx.profile.career.total_earnings)
    finally:
        app.shutdown()
