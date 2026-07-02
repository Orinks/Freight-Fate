import pygame
from driving_feature_helpers import key_event


def _job_board(app):
    from freight_fate.models.career import LEVEL_XP
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    app.ctx.profile = Profile(name="Dispatch Detail", current_city="Buffalo")
    app.ctx.profile.career.xp = LEVEL_XP[9]  # senior: browsable board
    jobs = JobBoard(app.ctx.world, seed=7).offers(
        "Buffalo", {"refrigerated", "heavy_haul", "high_value"}, level=5
    )
    state = JobBoardState(app.ctx, jobs)
    app.push_state(state)
    return state


def test_f1_on_dispatch_job_opens_structured_detail_view():
    from freight_fate.app import App
    from freight_fate.states.city import JobDetailState

    app = App()
    try:
        board = _job_board(app)
        job = board.jobs[board.index]

        board.handle_event(key_event(pygame.K_F1))

        assert isinstance(app.state, JobDetailState)
        lines = app.state.lines()
        joined = " ".join(lines)
        assert lines[0] == "Job details"
        assert app.state.items[0].text == f"Cargo: {job.cargo.label}."
        assert f"> Cargo: {job.cargo.label}." in lines
        assert "Origin:" in joined
        assert "Destination:" in joined
        assert "Distance:" in joined
        assert "Carrier gross:" in joined
        assert "Dollars per mile:" in joined
        assert "Route details happen after pickup" in joined
        assert app.state.items[-2].text == "Accept this dispatch"
        assert app.state.items[-1].text == "Back to dispatch board"
    finally:
        app.shutdown()


def test_job_detail_lines_are_reviewable_before_accepting():
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        spoken = []
        app.ctx.say = lambda text, **kwargs: spoken.append(text)
        board = _job_board(app)
        board.handle_event(key_event(pygame.K_F1))
        detail = app.state
        first_line = detail.items[0].text

        detail.handle_event(key_event(pygame.K_RETURN))

        assert app.state is detail
        assert isinstance(app.states[-2], JobBoardState)
        assert spoken[-1] == first_line
    finally:
        app.shutdown()


def test_job_detail_exposes_review_instructions():
    from freight_fate.app import App

    app = App()
    try:
        spoken = []
        app.ctx.say = lambda text, **kwargs: spoken.append(text)
        board = _job_board(app)

        board.handle_event(key_event(pygame.K_F1))
        entry_speech = spoken[-1]
        app.state.handle_event(key_event(pygame.K_F1))

        assert "Use up and down arrows to review each job detail line" in entry_speech
        assert "Home and End jump" in spoken[-1]
        assert "Press Enter to repeat it" in spoken[-1]
    finally:
        app.shutdown()


def test_locked_job_detail_does_not_sound_accept_available():
    from freight_fate.app import App
    from freight_fate.models.business import LEASED_OWNER_OPERATOR
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        spoken = []
        app.ctx.say = lambda text, **kwargs: spoken.append(text)
        app.ctx.profile = Profile(name="Locked Detail", current_city="Buffalo")
        app.ctx.profile.business_status = LEASED_OWNER_OPERATOR
        app.ctx.profile.owned_trucks = ["rig"]
        from freight_fate.models.career import LEVEL_XP

        app.ctx.profile.career.xp = LEVEL_XP[4]  # endorsements owned
        job = Job(
            CARGO_CATALOG["refrigerated"],
            12.0,
            "Buffalo",
            "cold storage",
            "Cleveland",
            180.0,
            1800.0,
            8.0,
        )
        state = JobBoardState(app.ctx, [job])
        app.push_state(state)
        locked_reason = state._locked_reason(job)
        assert "trailer program" in locked_reason

        state.handle_event(key_event(pygame.K_F1))
        locked_action = app.state.items[-2]
        locked_action.action()

        assert locked_action.text == f"Cannot accept this dispatch: {locked_reason}"
        assert spoken[-1] == locked_reason
    finally:
        app.shutdown()


def test_job_detail_accept_command_accepts_and_escape_returns():
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState, PickupFacilityState

    app = App()
    try:
        board = _job_board(app)
        board.handle_event(key_event(pygame.K_F1))
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, JobBoardState)

        board.handle_event(key_event(pygame.K_F1))
        while app.state.items[app.state.index].text != "Accept this dispatch":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert (
            isinstance(app.state, PickupFacilityState)
            or app.state.__class__.__name__ == "DrivingState"
        )
        assert all(state.__class__.__name__ != "JobDetailState" for state in app.states)
    finally:
        app.shutdown()
