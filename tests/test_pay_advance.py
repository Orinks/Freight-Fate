"""Dispatcher pay-advance recovery line: grant rules and limits."""

from freight_fate.models.economy import (
    PAY_ADVANCE_ELIGIBLE_BELOW,
    PAY_ADVANCE_GRANT,
    PAY_ADVANCE_LIMIT,
    pay_advance_grant,
    pay_advance_unavailable_reason,
)


def test_no_advance_when_cash_is_healthy():
    assert pay_advance_grant(PAY_ADVANCE_ELIGIBLE_BELOW, 0.0) == 0.0
    assert pay_advance_grant(10.0, 0.0) == 0.0
    assert pay_advance_grant(400.0, 0.0) == 0.0
    assert pay_advance_grant(5000.0, 0.0) == 0.0


def test_advance_available_when_broke():
    assert pay_advance_grant(-300.0, 0.0) == PAY_ADVANCE_GRANT
    assert pay_advance_grant(0.0, 0.0) == PAY_ADVANCE_GRANT
    assert pay_advance_grant(9.99, 0.0) == PAY_ADVANCE_GRANT


def test_advance_is_capped_by_the_outstanding_limit():
    # Almost at the ceiling: only the remaining headroom is offered.
    near_limit = PAY_ADVANCE_LIMIT - 100.0
    assert pay_advance_grant(-50.0, near_limit) == 100.0
    # At the ceiling: nothing more until a delivery pays it down.
    assert pay_advance_grant(-50.0, PAY_ADVANCE_LIMIT) == 0.0


def test_unavailable_reason_distinguishes_healthy_cash_from_the_limit():
    assert "cash is low" in pay_advance_unavailable_reason(5000.0, 0.0)
    assert "limit" in pay_advance_unavailable_reason(-50.0, PAY_ADVANCE_LIMIT)
