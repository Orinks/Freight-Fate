"""Assigned dispatch for new hires; load and route choice earned with rank."""

import pygame

from freight_fate.models.business import LEASED_OWNER_OPERATOR
from freight_fate.models.career import LEVEL_XP
from freight_fate.models.dispatch_policy import (
    NEW_HIRE_DECLINE_BUDGET,
    SENIOR_LOAD_CHOICE_LEVEL,
)
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def _job(*, miles: float, pay: float = 900.0, deadline: float = 8.0) -> Job:
    return Job(
        CARGO_CATALOG["general"],
        12.0,
        "Chicago",
        "Chicago yard",
        "Milwaukee",
        miles,
        pay,
        deadline,
    )


def _new_hire(name: str = "New Hire") -> Profile:
    profile = Profile(name=name, current_city="Chicago")
    profile.achievements.append("first_dispatch")
    return profile


def test_new_hire_board_offers_single_assignment_with_decline(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = _new_hire()
        app.ctx.profile.career.deliveries = 12  # past training stages

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=180.0),
            _job(miles=70.0),
        ]))

        board = app.state
        assert board.assigned_mode
        labels = [item.text for item in board.items]
        assert labels[0].startswith("Accept assigned dispatch:")
        assert "70 miles" in labels[0]  # the recommended (shortest) load
        assert labels[1].startswith("Decline and request another load:")
        assert f"{NEW_HIRE_DECLINE_BUDGET} declines left" in labels[1]
        assert labels[-1] == "Back to terminal"
        assert "Dispatch assigns your load and route" in spoken[-1]
        assert f"level {SENIOR_LOAD_CHOICE_LEVEL}" in spoken[-1]
    finally:
        app.shutdown()


def test_declining_assignment_costs_reputation_and_draws_next_load(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = _new_hire("Decliner")
        app.ctx.profile.career.deliveries = 12
        reputation_before = app.ctx.profile.career.reputation

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=180.0),
            _job(miles=70.0),
        ]))
        board = app.state
        while not board.items[board.index].text.startswith("Decline"):
            board.handle_event(key_event(pygame.K_DOWN))
        board.handle_event(key_event(pygame.K_RETURN))

        assert app.ctx.profile.career.dispatch_declines_used == 1
        assert app.ctx.profile.career.reputation < reputation_before
        assert "Load declined" in spoken[-1]
        assert "service record" in spoken[-1]
        assert "180 miles" in spoken[-1]  # the next candidate was drawn
        assert board.items[0].text.startswith("Accept assigned dispatch:")
        assert "180 miles" in board.items[0].text
    finally:
        app.shutdown()


def test_exhausted_decline_budget_locks_board_to_accept_only(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        app.ctx.profile = _new_hire("Out Of Declines")
        app.ctx.profile.career.deliveries = 12
        app.ctx.profile.career.dispatch_declines_used = NEW_HIRE_DECLINE_BUDGET

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=180.0),
            _job(miles=70.0),
        ]))

        labels = [item.text for item in app.state.items]
        assert labels[0].startswith("Accept assigned dispatch:")
        assert not any(label.startswith("Decline") for label in labels)
    finally:
        app.shutdown()


def test_single_candidate_assignment_offers_no_decline(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        app.ctx.profile = _new_hire("One Load Town")

        app.push_state(JobBoardState(app.ctx, [_job(miles=70.0)]))

        labels = [item.text for item in app.state.items]
        assert labels[0].startswith("Accept assigned dispatch:")
        assert not any(label.startswith("Decline") for label in labels)
    finally:
        app.shutdown()


def test_accepting_assignment_starts_pickup_drive(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.states.city import JobBoardState
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        app.ctx.profile = _new_hire("Assigned Acceptor")
        jobs = JobBoard(app.ctx.world, seed=7).offers("Chicago", set(), level=1)

        app.push_state(JobBoardState(app.ctx, jobs))
        assert app.state.assigned_mode
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, DrivingState)
        assert app.state.phase == "pickup"
    finally:
        app.shutdown()


def test_senior_company_driver_gets_browsable_board(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        app.ctx.profile = _new_hire("Senior Driver")
        app.ctx.profile.career.xp = LEVEL_XP[SENIOR_LOAD_CHOICE_LEVEL - 1]
        app.ctx.profile.career.deliveries = 20
        app.ctx.profile.career.reputation = 80

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=180.0),
            _job(miles=70.0),
        ]))

        assert not app.state.assigned_mode
        assert any("Job 1 of 2" in item.text for item in app.state.items)
    finally:
        app.shutdown()


def test_owner_operator_board_stays_browsable(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        app.ctx.profile = _new_hire("Owner Browser")
        app.ctx.profile.business_status = LEASED_OWNER_OPERATOR
        app.ctx.profile.owned_trucks = ["rig"]

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=180.0),
            _job(miles=70.0),
        ]))

        assert not app.state.assigned_mode
    finally:
        app.shutdown()


def test_company_departure_runs_dispatch_assigned_route(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import PickupFacilityState
    from freight_fate.states.driving import DrivingState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = _new_hire("Routed Driver")
        expected = app.ctx.world.supported_route_options("Chicago", "Milwaukee")[0]

        app.push_state(PickupFacilityState(
            app.ctx, _job(miles=92.0), checked_in=True, loaded=True))
        app.state.handle_event(key_event(pygame.K_RETURN))  # depart

        assert isinstance(app.state, DrivingState)
        assert app.state.phase == "delivery"
        assert app.state.route.cities == expected.cities
        departure = next(text for text in spoken if "Dispatch routed you to" in text)
        assert "Departing now" in departure
        assert not any("Route planning to" in text for text in spoken)
    finally:
        app.shutdown()


def test_senior_company_departure_is_still_dispatch_routed(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import PickupFacilityState
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        app.ctx.profile = _new_hire("Senior Routed")
        app.ctx.profile.career.xp = LEVEL_XP[SENIOR_LOAD_CHOICE_LEVEL - 1]

        app.push_state(PickupFacilityState(
            app.ctx, _job(miles=92.0), checked_in=True, loaded=True))
        app.state.handle_event(key_event(pygame.K_RETURN))  # depart

        assert isinstance(app.state, DrivingState)
        assert app.state.phase == "delivery"
    finally:
        app.shutdown()


def test_owner_operator_departure_keeps_route_choice(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import PickupFacilityState, RouteSelectState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = _new_hire("Owner Router")
        app.ctx.profile.business_status = LEASED_OWNER_OPERATOR
        app.ctx.profile.owned_trucks = ["rig"]

        app.push_state(PickupFacilityState(
            app.ctx, _job(miles=92.0), checked_in=True, loaded=True))
        app.state.handle_event(key_event(pygame.K_RETURN))  # depart

        assert isinstance(app.state, RouteSelectState)
        assert any("Route planning to" in text for text in spoken)
    finally:
        app.shutdown()
