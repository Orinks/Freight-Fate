"""In-game controls reference: reachable from the pause menu, opens to keys."""


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Help", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles,
        1000.0,
        12.0,
        destination_location="Rochester freight market",
    )
    return DrivingState(app.ctx, job, route, phase="delivery")


def test_controls_help_page_points_at_the_driving_keys():
    from freight_fate.states.main_menu import HELP_PAGES, controls_help_page

    idx = controls_help_page()
    title, lines = HELP_PAGES[idx]
    assert title == "Driving information keys"
    # The new keys are documented there.
    joined = " ".join(lines)
    assert "Space speaks your speed" in joined
    assert "active speed-control mode" in joined
    assert "open-road target" in joined
    assert "S speaks the posted speed limit" in joined
    assert "R speaks how far along you are" in joined
    assert "A repeats the last driving announcement" in joined
    # U stopped being a recital of everything ahead (2026-08-15): the exit
    # cue, the traffic-pressure advisory and two of the three bends were
    # already other keys' answers, so the help now promises only the road
    # nothing else covers. Pinned on the promise, not the old phrasing.
    assert "U speaks the road ahead that no other key answers" in joined
    # And U must never advertise police activity again (owner ruling): the
    # check is scoped to U's own line, because a sibling line legitimately
    # explains what the hours-of-service keys do with enforcement off.
    u_line = next(line for line in lines if line.startswith("U speaks"))
    assert not any(word in u_line.lower() for word in ("patrol", "police", "bear"))
    assert any("X" in line and "signal" in line.lower() for line in lines)
    assert all("X takes the next announced exit" not in line for line in lines)
    assert "Left or Right Control stops the driving event voice" in joined


def test_help_pages_explain_t_roadside_sleep_and_poi_priority():
    from freight_fate.states.main_menu import HELP_PAGES

    joined = " ".join(line for _title, lines in HELP_PAGES for line in lines)
    assert "T opens the emergency shoulder-sleep warning" in joined
    assert "nearby route points always take priority" in joined
    assert "T or the pause menu offers emergency shoulder sleep" in joined
    assert "plus D-pad down opens route-stop actions or emergency shoulder sleep" in joined


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


def test_pause_menu_emergency_shoulder_sleep_sits_between_mechanic_and_settings():
    # build_items() inserts this item at a hardcoded index; pin its position
    # so the next inserted item shifts this test instead of silently
    # misplacing the item (it happened once already, index 4 -> 5).
    from freight_fate.app import App
    from freight_fate.states.driving import PauseMenuState

    app = App()
    try:
        d = _driving(app)
        pause = PauseMenuState(app.ctx, d)
        d.emergency_shoulder_sleep_reason = lambda: "stopped away from any route point"
        labels = [item.text for item in pause.build_items()]
        assert "Emergency shoulder sleep" in labels
        idx = labels.index("Emergency shoulder sleep")
        assert labels[idx - 1] == pause._mechanic_label()
        assert labels[idx + 1] == "Settings"
    finally:
        app.shutdown()
