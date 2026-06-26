"""Dispatcher pay-advance recovery line: grant rules and limits."""

from freight_fate.models.economy import (
    PAY_ADVANCE_ELIGIBLE_BELOW,
    PAY_ADVANCE_GRANT,
    PAY_ADVANCE_LIMIT,
    pay_advance_grant,
    pay_advance_unavailable_reason,
)


def _menu_texts(items):
    return [item.text for item in items]


def test_no_advance_when_cash_is_healthy():
    assert pay_advance_grant(PAY_ADVANCE_ELIGIBLE_BELOW, 0.0) == 0.0
    assert pay_advance_grant(5000.0, 0.0) == 0.0


def test_advance_available_when_broke():
    assert pay_advance_grant(-300.0, 0.0) == PAY_ADVANCE_GRANT
    assert pay_advance_grant(0.0, 0.0) == PAY_ADVANCE_GRANT


def test_advance_is_capped_by_the_outstanding_limit():
    # Almost at the ceiling: only the remaining headroom is offered.
    near_limit = PAY_ADVANCE_LIMIT - 100.0
    assert pay_advance_grant(-50.0, near_limit) == 100.0
    # At the ceiling: nothing more until a delivery pays it down.
    assert pay_advance_grant(-50.0, PAY_ADVANCE_LIMIT) == 0.0


def test_unavailable_reason_distinguishes_healthy_cash_from_the_limit():
    assert "cash is low" in pay_advance_unavailable_reason(5000.0, 0.0)
    assert "limit" in pay_advance_unavailable_reason(-50.0, PAY_ADVANCE_LIMIT)


def test_terminal_pay_advance_option_only_appears_when_available():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        app.ctx.profile = Profile(name="Advance Test", current_city="New York")
        state = CityMenuState(app.ctx)

        app.ctx.profile.money = PAY_ADVANCE_ELIGIBLE_BELOW
        assert not any(
            text.startswith("Request pay advance")
            for text in _menu_texts(state.build_items())
        )

        app.ctx.profile.money = PAY_ADVANCE_ELIGIBLE_BELOW - 1.0
        assert any(
            text.startswith("Request pay advance")
            for text in _menu_texts(state.build_items())
        )

        app.ctx.profile.pay_advance = PAY_ADVANCE_LIMIT
        assert not any(
            text.startswith("Request pay advance")
            for text in _menu_texts(state.build_items())
        )
    finally:
        app.shutdown()


def test_rest_stop_pay_advance_option_only_appears_when_available():
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.sim.trip import RoadStop
    from freight_fate.states.driving import DrivingState, RestStopState

    app = App()
    try:
        app.ctx.profile = Profile(name="Advance Test", current_city="New York")
        job = Job(
            CARGO_CATALOG["electronics"],
            18,
            "New York",
            "JFK Air Cargo",
            "Philadelphia",
            78,
            2500,
            12,
            origin_type="air_cargo",
            destination_location="Philadelphia Distribution Center",
            destination_type="retail_distribution",
        )
        route = app.ctx.world.route_from_cities(["New York", "Philadelphia"])
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        stop = RoadStop(
            "Example Service Plaza",
            10.0,
            "service_plaza",
            ("park", "save"),
            ("parking",),
        )
        state = RestStopState(app.ctx, driving, stop)

        app.ctx.profile.money = PAY_ADVANCE_ELIGIBLE_BELOW
        assert not any(
            text.startswith("Request pay advance")
            for text in _menu_texts(state.build_items())
        )

        app.ctx.profile.money = PAY_ADVANCE_ELIGIBLE_BELOW - 1.0
        assert any(
            text.startswith("Request pay advance")
            for text in _menu_texts(state.build_items())
        )

        app.ctx.profile.pay_advance = PAY_ADVANCE_LIMIT
        assert not any(
            text.startswith("Request pay advance")
            for text in _menu_texts(state.build_items())
        )
    finally:
        app.shutdown()
