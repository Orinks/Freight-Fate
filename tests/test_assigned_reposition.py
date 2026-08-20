"""Carrier-ASSIGNED repositions (ROADMAP: "Company drivers get ASSIGNED
repositions"): occasional empty deadhead dispatch sends a company driver on,
distinct from the owner-operator self-serve "Bobtail to a nearby city" menu.
"""

import pygame
import pytest

from freight_fate.models.business import LEASED_OWNER_OPERATOR


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def _find_reposition(app, *, owner_operator=False, trials=600):
    """Walk seeded profiles/cities until the board's own deterministic roll
    turns up a reposition, mirroring how tests elsewhere search seeds for a
    property instead of hand-picking one fragile value."""
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import assigned_reposition_for_board, dispatch_cache_key

    board = JobBoard(app.ctx.world)
    cities = list(app.ctx.world.cities.keys())
    for i in range(trials):
        p = Profile(name=f"Seed{i}", current_city=cities[i % len(cities)])
        p.market.seed = i
        if owner_operator:
            p.business_status = LEASED_OWNER_OPERATOR
        app.ctx.profile = p
        key = dispatch_cache_key(p)
        job = assigned_reposition_for_board(app.ctx, board, key)
        if job is not None:
            return p, job
    return None, None


def test_assigned_reposition_shows_for_company_driver_never_for_owner_operator():
    from freight_fate.app import App
    from freight_fate.models.start_options import pay_plan_for_key

    app = App()
    try:
        p, job = _find_reposition(app)
        assert p is not None, "no seeded board produced a reposition in the trial budget"
        assert job.bobtail and job.assigned
        assert job.destination != job.origin
        assert app.ctx.world.supported_route(job.origin, job.destination) is not None
        # Pays something, but strictly less than the loaded per-mile floor.
        plan = pay_plan_for_key(p.carrier_key)
        assert 0.0 < job.pay < job.distance_mi * plan.min_per_mile

        # The same search never turns one up for an owner-operator: the
        # gate is unconditional, not just an unlucky roll.
        oo_p, oo_job = _find_reposition(app, owner_operator=True)
        assert oo_p is None and oo_job is None
    finally:
        app.shutdown()


def test_assigned_reposition_replaces_a_board_slot_for_company_driver():
    """The reposition takes an ordinary offer's place rather than adding a
    ninth entry, so the board still shows exactly as many jobs as the
    player's level and trust earn -- the same invariant a stale board
    rebuild relies on (see test_stale_dispatch_board.py)."""
    from freight_fate.app import App
    from freight_fate.models import enforcement
    from freight_fate.models.jobs import board_offer_count
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        p, _job = _find_reposition(app)
        assert p is not None
        app.ctx.profile = p
        city_state = CityMenuState(app.ctx)
        city_state._job_board()
        board = app.state

        assert any(j.bobtail and j.assigned for j in board.jobs)
        expected_count = enforcement.board_offers_for_reputation(
            board_offer_count(p.career.level), p.career.reputation
        )
        assert len(board.jobs) == expected_count
    finally:
        app.shutdown()


def test_assigned_reposition_pays_reduced_rate_and_awards_mileage_xp():
    """Completing an assigned reposition pays the reduced empty-mile rate
    already baked into job.pay and earns mileage XP like any other
    completed drive -- unlike a self-serve bobtail, which pays and earns
    nothing (test_bobtail_relocates_to_a_nearby_city_without_pay)."""
    from freight_fate.app import App
    from freight_fate.models.jobs import ASSIGNED_REPOSITION_PAY_FRACTION, make_reposition_job
    from freight_fate.models.profile import Profile
    from freight_fate.models.start_options import pay_plan_for_key
    from freight_fate.states.driving import ArrivalState, DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Assigned Reposition")
        p = app.ctx.profile
        p.current_city = "Denver"
        job = make_reposition_job(
            app.ctx.world, "Denver", "Cheyenne", assigned=True, carrier_key=p.carrier_key
        )
        assert job is not None and job.bobtail and job.assigned

        plan = pay_plan_for_key(p.carrier_key)
        expected_pay = round(
            job.distance_mi * plan.min_per_mile * ASSIGNED_REPOSITION_PAY_FRACTION, 2
        )
        assert job.pay == expected_pay

        money_before = p.money
        xp_before = p.career.xp
        deliveries_before = p.career.deliveries
        route = app.ctx.world.supported_route("Denver", "Cheyenne")
        driving = DrivingState(app.ctx, job, route)

        app.ctx.push_state(ArrivalState(app.ctx, driving))
        arrival = app.state

        assert p.current_city == "cheyenne_wy_us"
        assert p.money == pytest.approx(money_before + job.pay)
        assert p.career.xp > xp_before  # mileage XP, same as any other drive
        assert p.career.deliveries == deliveries_before + 1  # a real completed assignment
        assert any(f"{job.pay:,.0f} dollars" in line for line in arrival.summary_lines)
    finally:
        app.shutdown()


def test_abandoning_assigned_reposition_costs_reputation_only():
    """Walking away from an ASSIGNED reposition is walking away from a
    dispatch assignment: reputation drops, no dollar penalty -- unlike a
    real load (five hundred dollars and reputation) and unlike a self-serve
    bobtail (nothing at all, test_abandoning_a_bobtail_costs_nothing)."""
    from freight_fate.app import App
    from freight_fate.models.jobs import make_reposition_job
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.driving import (
        AbandonJobConfirmationState,
        DrivingState,
        PauseMenuState,
    )

    app = App()
    try:
        app.ctx.profile = Profile(name="Assigned Reposition Abandon", current_city="Denver")
        p = app.ctx.profile
        job = make_reposition_job(
            app.ctx.world, "Denver", "Cheyenne", assigned=True, carrier_key=p.carrier_key
        )
        assert job is not None
        route = app.ctx.world.supported_route("Denver", "Cheyenne")
        driving = DrivingState(app.ctx, job, route)
        money_before = p.money
        reputation_before = p.career.reputation

        app.push_state(driving)
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, PauseMenuState)
        pause = app.state
        while pause.items[pause.index].text != "Abandon job":
            pause.handle_event(key_event(pygame.K_DOWN))
        pause.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, AbandonJobConfirmationState)
        confirm = app.state
        assert confirm._is_bobtail()
        assert confirm._is_assigned_reposition()

        confirm.handle_event(key_event(pygame.K_DOWN))  # arrow to Yes
        confirm.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, CityMenuState)
        assert p.money == money_before  # no dollar penalty
        assert p.career.reputation == pytest.approx(
            reputation_before - confirm.ASSIGNED_REPOSITION_ABANDON_REPUTATION_PENALTY
        )
    finally:
        app.shutdown()
