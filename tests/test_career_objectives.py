import pygame

from freight_fate.models.business import (
    LEASED_OWNER_OPERATOR,
    OWNER_OPERATOR_LEVEL,
)
from freight_fate.models.career import LEVEL_XP
from freight_fate.models.career_objectives import career_objective
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.models.start_options import (
    OWNER_OPERATOR_START_KEY,
    apply_start_option,
    start_option,
)


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


def test_company_driver_objective_uses_level_band_guidance_after_training():
    profile = Profile(name="Regional Plan", current_city="Chicago")
    profile.achievements.append("first_dispatch")
    profile.career.xp = LEVEL_XP[3]
    profile.career.deliveries = 12
    profile.career.reputation = 82

    objective = career_objective(profile)

    assert objective.title == "Build a regional service record"
    assert "broader company lanes" in objective.terminal_text
    assert objective.recommendation == "reputation-building lane"


def test_ready_unlock_states_override_level_band_guidance():
    profile = Profile(name="Buy In", current_city="Chicago")
    profile.achievements.append("first_dispatch")
    profile.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 1]
    profile.career.deliveries = 35
    profile.career.reputation = 82
    profile.money = 60_000.0

    objective = career_objective(profile)

    assert objective.title == "Owner-operator buy-in ready"
    assert objective.recommendation == "clean company load"


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


def test_terminal_career_plan_speaks_senior_company_level_guidance(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Senior Driver", current_city="Chicago")
        app.ctx.profile.achievements.append("first_dispatch")
        app.ctx.profile.career.xp = LEVEL_XP[9]
        app.ctx.profile.career.deliveries = 20
        app.ctx.profile.career.reputation = 86

        app.push_state(CityMenuState(app.ctx))
        career_item = next(i for i, item in enumerate(app.state.items) if item.text == "Career plan")
        app.state.index = career_item
        app.state.items[career_item].action()

        assert spoken[-1].startswith("Run like a senior company driver.")
        assert "premium lanes" in spoken[-1]
        assert "premium freight" in spoken[-1]
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


def test_dispatch_board_speaks_authority_level_recommendation(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.business import INDEPENDENT_AUTHORITY
    from freight_fate.states.city import JobBoardState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Independent", current_city="Chicago")
        app.ctx.profile.achievements.append("first_dispatch")
        app.ctx.profile.business_status = INDEPENDENT_AUTHORITY
        app.ctx.profile.owned_trucks = ["rig"]
        app.ctx.profile.money = 90_000.0
        app.ctx.profile.career.xp = LEVEL_XP[24]
        app.ctx.profile.career.deliveries = 80
        app.ctx.profile.career.reputation = 94

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=120.0, pay=1800.0),
        ]))

        assert "Career objective: Grow a freight business" in spoken[-1]
        assert "direct freight" in spoken[-1]
        assert "direct freight with margin" in spoken[-1]
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


def test_out_of_sync_company_terminal_entry_uses_first_week_guidance(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(
            app.ctx, "say", lambda text, interrupt=True: spoken.append(text)
        )
        app.ctx.profile = Profile(name="First Week", current_city="Chicago")
        app.ctx.profile.career.deliveries = 1

        app.push_state(CityMenuState(app.ctx))

        entry = spoken[-1]
        assert "First-day objective" not in entry
        assert "Career objective:" in entry
        assert "steady service, not perfection" in entry
        assert "good first-week run" in entry
        assert "trainer notes still close by" in entry
        labels = [item.text for item in app.state.items]
        assert "First-day briefing" not in labels
        assert "Career plan" in labels
    finally:
        app.shutdown()


def test_dispatch_board_recommendation_label_is_spoken_and_visible(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(
            app.ctx, "say", lambda text, interrupt=True: spoken.append(text)
        )
        app.ctx.profile = Profile(name="Board Plan", current_city="Chicago")
        app.ctx.profile.career.deliveries = 1

        app.push_state(
            JobBoardState(
                app.ctx,
                [
                    Job(
                        CARGO_CATALOG["general"],
                        12.0,
                        "Chicago",
                        "Chicago yard",
                        "Milwaukee",
                        45.0,
                        900.0,
                        1.0,
                    ),
                    Job(
                        CARGO_CATALOG["general"],
                        12.0,
                        "Chicago",
                        "Chicago yard",
                        "Milwaukee",
                        120.0,
                        900.0,
                        12.0,
                    ),
                ],
            )
        )

        assert "Career objective: First-week service record" in spoken[-1]
        assert "First-day objective" not in spoken[-1]
        assert "good first-week run" in spoken[-1]
        assert "Recommended dispatch: good first-week run" not in spoken[-1]
        assert (
            "Recommended dispatch, good first-week run: Job 2 of 2:"
            in spoken[-1]
        )
        assert (
            "Recommended dispatch is Recommended dispatch"
            not in spoken[-1]
        )
        assert app.state.index == 1
        assert app.state.current_text().startswith(
            "Recommended dispatch, good first-week run: Job 2 of 2:"
        )
        recommended = [
            item.text for item in app.state.items
            if item.text.startswith("Recommended dispatch, trainer-recommended:")
            or item.text.startswith("Recommended dispatch, good first-week run:")
        ]
        assert recommended == [app.state.items[1].text]
        assert app.state.items[1].text.startswith(
            "Recommended dispatch, good first-week run: Job 2 of 2:"
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


def test_out_of_sync_owner_operator_uses_career_guidance(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState, JobBoardState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(
            app.ctx, "say", lambda text, interrupt=True: spoken.append(text)
        )
        app.ctx.profile = Profile(name="Owner Week", current_city="Chicago")
        apply_start_option(app.ctx.profile, start_option(OWNER_OPERATOR_START_KEY))

        app.push_state(CityMenuState(app.ctx))

        terminal_entry = spoken[-1]
        labels = [item.text for item in app.state.items]
        assert "First-day objective" not in terminal_entry
        assert "Career objective:" in terminal_entry
        assert "Fuel, maintenance, insurance" in terminal_entry
        assert "First-day briefing" not in labels
        assert "Career plan" in labels

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=180.0, pay=1200.0),
            _job(miles=70.0, pay=1800.0),
        ]))

        board_entry = spoken[-1]
        assert "First-day objective" not in board_entry
        assert "Career objective:" in board_entry
        assert "cash-positive load" in board_entry
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
            _job(miles=70.0, pay=1800.0),
        ]))

        entry = spoken[-1]
        assert "owner-operator gross revenue" in entry
        assert "cash cushion" in entry
        assert "trainer-recommended" not in entry
        assert app.state.index == 0
        assert app.state.current_text().startswith("Job 1 of 2:")
        assert not any(
            item.text.startswith("Recommended dispatch, trainer-recommended:")
            for item in app.state.items
        )
    finally:
        app.shutdown()
