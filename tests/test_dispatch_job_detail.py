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
        assert f"Cargo: {job.cargo.label}" in joined
        assert "Origin:" in joined
        assert "Destination:" in joined
        assert "Distance:" in joined
        assert "Pay:" in joined
        assert "Dollars per mile:" in joined
        assert "Route details happen after pickup" in joined
    finally:
        app.shutdown()


def test_job_detail_enter_accepts_and_escape_returns():
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState, PickupFacilityState

    app = App()
    try:
        board = _job_board(app)
        board.handle_event(key_event(pygame.K_F1))
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, JobBoardState)

        board.handle_event(key_event(pygame.K_F1))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert (
            isinstance(app.state, PickupFacilityState)
            or app.state.__class__.__name__ == "DrivingState"
        )
        assert all(state.__class__.__name__ != "JobDetailState" for state in app.states)
    finally:
        app.shutdown()
