import pygame
from driving_feature_helpers import key_event


def _job_board(app):
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    app.ctx.profile = Profile(name="Dispatch Detail", current_city="Buffalo")
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
        # The detail view always names the state, even for a unique city name,
        # so a player who does not know the geography can ask for it here.
        assert "in Buffalo, New York" in joined
        assert "Distance:" in joined
        assert "Pay:" in joined
        assert "Dollars per mile:" in joined
        assert "Route details happen after pickup" in joined
        assert app.state.items[-2].text == "Accept this dispatch"
        assert app.state.items[-1].text == "Back to dispatch board"
    finally:
        app.shutdown()


def test_tab_repeats_only_the_market_watch(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        board = _job_board(app)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))

        board.handle_event(key_event(pygame.K_TAB))

        # Exactly the market summary is spoken -- no job line, no HOS note.
        assert spoken == [app.ctx.profile.market.summary()]
        assert board.index == 0  # Tab does not move the selection
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
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        spoken = []
        app.ctx.say = lambda text, **kwargs: spoken.append(text)
        app.ctx.profile = Profile(name="Locked Detail", current_city="Buffalo")
        jobs = JobBoard(app.ctx.world, seed=7).offers("Buffalo", set(), level=2)
        state = JobBoardState(app.ctx, jobs)
        app.push_state(state)
        while not state.jobs[state.index].locked_reason(
            app.ctx.profile.career.endorsements, app.ctx.profile.career.level
        ):
            state.handle_event(key_event(pygame.K_DOWN))

        state.handle_event(key_event(pygame.K_F1))
        locked_action = app.state.items[-2]
        locked_reason = state.jobs[state.index].locked_reason(
            app.ctx.profile.career.endorsements, app.ctx.profile.career.level
        )
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
