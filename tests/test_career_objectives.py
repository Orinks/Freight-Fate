import pygame

from freight_fate.models.business import (
    LEASED_OWNER_OPERATOR,
    OWNER_OPERATOR_LEVEL,
)
from freight_fate.models.career import LEVEL_XP
from freight_fate.models.career_objectives import career_objective
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def _job(*, miles: float, pay: float = 900.0, cargo: str = "general") -> Job:
    return Job(
        CARGO_CATALOG[cargo],
        12.0,
        "Chicago",
        "Chicago yard",
        "Milwaukee",
        miles,
        pay,
        8.0,
    )


def test_company_driver_objective_tapers_from_first_week_to_trust():
    profile = Profile(name="Career Plan", current_city="Chicago")
    profile.achievements.append("first_dispatch")

    first_load = career_objective(profile)
    assert first_load.title == "First dispatch"
    assert "real freight" in first_load.terminal_text
    assert "short standard load" in first_load.dispatch_text
    assert "probation" not in first_load.spoken_summary.lower()

    profile.career.deliveries = 2
    reminder = career_objective(profile)
    assert reminder.title == "First-week service record"
    assert "steady service, not perfection" in reminder.terminal_text

    profile.career.deliveries = 4
    profile.career.reputation = 62
    trust = career_objective(profile)
    assert trust.title == "Build dispatcher trust"
    assert "on-time service" in trust.terminal_text
    assert "reliable lanes" in trust.dispatch_text


def test_low_reputation_company_driver_keeps_trust_objective_after_training():
    profile = Profile(name="Trust Plan", current_city="Chicago")
    profile.achievements.append("first_dispatch")
    profile.career.deliveries = 12
    profile.career.reputation = 62

    objective = career_objective(profile)

    assert objective.title == "Build dispatcher trust"
    assert "on-time service" in objective.terminal_text
    assert "reliable lanes" in objective.dispatch_text


def test_owner_operator_objective_emphasizes_working_capital():
    profile = Profile(name="Owner Plan", current_city="Chicago")
    profile.business_status = LEASED_OWNER_OPERATOR
    profile.owned_trucks = ["rig"]
    profile.money = 12_000.0
    profile.achievements.append("first_dispatch")

    objective = career_objective(profile)

    assert objective.title == "Protect working capital"
    assert "Fuel, maintenance, insurance" in objective.terminal_text
    assert "take-home" in objective.dispatch_text


def test_terminal_career_plan_is_keyboard_reachable_and_spoken(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Keyboard Plan", current_city="Chicago")
        app.ctx.profile.achievements.append("first_dispatch")

        app.push_state(CityMenuState(app.ctx))

        assert any("Career objective:" in text for text in spoken)
        assert any(item.text == "Career plan" for item in app.state.items)

        app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert spoken[-1].startswith("First dispatch.")
        assert "short standard load" in spoken[-1]
    finally:
        app.shutdown()


def test_dispatch_board_speaks_objective_and_marks_recommended_job(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Board Plan", current_city="Chicago")
        app.ctx.profile.achievements.append("first_dispatch")
        app.ctx.profile.career.deliveries = 2

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=180.0, pay=1200.0),
            _job(miles=70.0, pay=700.0),
        ]))

        assert "Career objective: First-week service record" in spoken[-1]
        assert "short regional freight" in spoken[-1]
        recommended = next(
            item.text for item in app.state.items
            if item.text.startswith("Recommended dispatch")
        )
        assert recommended.startswith(
            "Recommended dispatch, good first-week run: Job 2 of 2:")
        assert not app.state.items[0].text.startswith("Recommended dispatch")
    finally:
        app.shutdown()


def test_late_company_driver_plan_points_to_owner_operator_prep():
    profile = Profile(name="Prep Plan", current_city="Chicago")
    profile.achievements.append("first_dispatch")
    profile.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 4]
    profile.career.deliveries = 25
    profile.career.reputation = 75

    objective = career_objective(profile)

    assert objective.title == "Owner-operator preparation"
    assert "cash cushion" in objective.terminal_text
    assert "protects reputation" in objective.dispatch_text


def test_first_day_terminal_entry_speaks_training_arc_without_tutorial_language(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="First Day", current_city="Chicago")

        app.push_state(CityMenuState(app.ctx))

        entry = spoken[-1]
        assert "First-day objective" in entry
        assert "trainer-recommended" in entry
        assert "probation" not in entry.lower()
    finally:
        app.shutdown()


def test_dispatch_board_recommendation_label_is_spoken_and_visible(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Board Plan", current_city="Chicago")

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=180.0, pay=1200.0),
            _job(miles=70.0, pay=700.0),
        ]))

        assert "First-day objective" in spoken[-1]
        assert "trainer-recommended" in spoken[-1]
        recommended = [
            item.text for item in app.state.items
            if item.text.startswith("Recommended dispatch, trainer-recommended:")
        ]
        assert recommended == [app.state.items[1].text]
        assert app.state.items[1].text.startswith(
            "Recommended dispatch, trainer-recommended: Job 2 of 2:"
        )
    finally:
        app.shutdown()


def test_owner_operator_first_day_terminal_keeps_cash_cushion_guidance(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Owner Day", current_city="Chicago")
        app.ctx.profile.business_status = LEASED_OWNER_OPERATOR
        app.ctx.profile.owned_trucks = ["rig"]
        app.ctx.profile.money = 12_000.0

        app.push_state(CityMenuState(app.ctx))

        entry = spoken[-1]
        assert "First-day objective" in entry
        assert "cash cushion" in entry
        assert "trainer-recommended" not in entry
    finally:
        app.shutdown()


def test_owner_operator_first_day_dispatch_board_keeps_business_cost_guidance(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Owner Board", current_city="Chicago")
        app.ctx.profile.business_status = LEASED_OWNER_OPERATOR
        app.ctx.profile.owned_trucks = ["rig"]
        app.ctx.profile.money = 12_000.0

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=180.0, pay=1200.0),
            _job(miles=70.0, pay=700.0),
        ]))

        entry = spoken[-1]
        assert "owner-operator gross revenue" in entry
        assert "cash cushion" in entry
        assert "trainer-recommended" not in entry
        assert not any(
            item.text.startswith("Recommended dispatch, trainer-recommended:")
            for item in app.state.items
        )
    finally:
        app.shutdown()
