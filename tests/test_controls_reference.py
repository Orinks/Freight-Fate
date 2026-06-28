"""In-game controls reference: reachable from the pause menu, opens to keys."""


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Help", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(CARGO_CATALOG["general"], 12.0, "Buffalo", "company yard",
              "Rochester", route.miles, 1000.0, 12.0,
              destination_location="Rochester freight market")
    return DrivingState(app.ctx, job, route, phase="delivery")


def test_controls_help_page_points_at_the_driving_keys():
    from freight_fate.states.main_menu import HELP_PAGES, controls_help_page

    idx = controls_help_page()
    title, lines = HELP_PAGES[idx]
    assert title == "Driving information keys"
    # The new keys are documented there.
    joined = " ".join(lines)
    assert "Space speaks your speed" in joined
    assert "cruise set speed when cruise is on" in joined
    assert "S speaks the posted speed limit" in joined
    assert "A repeats the last route announcement" in joined
    assert "U speaks what is coming up" in joined


def test_help_state_opens_to_a_chosen_page():
    from freight_fate.app import App
    from freight_fate.states.main_menu import HelpState, controls_help_page

    app = App()
    try:
        page = controls_help_page()
        state = HelpState(app.ctx, start_page=page)
        assert state.page == page
        # Out-of-range requests clamp instead of crashing.
        assert HelpState(app.ctx, start_page=9999).page >= 0
    finally:
        app.shutdown()


def test_pause_menu_offers_controls_and_help():
    from freight_fate.app import App
    from freight_fate.states.driving import PauseMenuState

    app = App()
    try:
        d = _driving(app)
        pause = PauseMenuState(app.ctx, d)
        labels = [item.text for item in pause.build_items()]
        assert "Controls and help" in labels
    finally:
        app.shutdown()
