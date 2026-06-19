import json

import pygame


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def select(menu, label):
    while not menu.items[menu.index].text.startswith(label):
        menu.handle_event(key_event(pygame.K_DOWN))
    menu.handle_event(key_event(pygame.K_RETURN))


def test_achievement_copy_is_allusive_and_speech_sized():
    from freight_fate.achievements import ACHIEVEMENTS, award
    from freight_fate.models.profile import Profile

    for achievement in ACHIEVEMENTS:
        artist, title = achievement.inspiration.split(" - ", 1)
        visible = f"{achievement.name} {achievement.description}".lower()
        assert "\n" not in achievement.description
        assert 80 <= len(achievement.description) <= 220
        assert achievement.description.count(".") >= 2
        assert '"' not in achievement.description
        assert achievement.inspiration
        assert artist.lower() not in visible
        assert title.lower() not in visible

    profile = Profile(name="Copy Check")
    message = award(profile, ACHIEVEMENTS[0].id).message
    assert message.startswith("New achievement!")


def test_old_save_without_achievements_loads_with_defaults(tmp_path):
    from freight_fate.models.profile import Profile

    path = tmp_path / "old.json"
    path.write_text(json.dumps({"name": "Old Timer", "money": 5000.0}), encoding="utf-8")

    loaded = Profile.load(path)

    assert loaded.achievements == []
    assert loaded.achievement_stats == {}


def test_award_achievement_persists_and_deduplicates_notification(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile

    app = App()
    try:
        app.ctx.profile = Profile(name="Badge Driver")
        spoken = []
        played = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **_kwargs: played.append(key))

        first = app.ctx.award_achievement("first_delivery")
        second = app.ctx.award_achievement("first_delivery")

        assert first is not None
        assert second is None
        assert spoken == [first.message]
        assert first.message.startswith("New achievement!")
        assert played == ["ui/level_up"]
        reloaded = Profile.load(app.ctx.profile.path)
        assert reloaded.achievements == ["first_delivery"]
    finally:
        app.shutdown()


def test_main_menu_achievement_path_is_keyboard_accessible(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.main_menu import (
        AchievementCareerState,
        AchievementsState,
        MainMenuState,
    )

    app = App()
    try:
        profile = Profile(name="Menu Badges")
        profile.achievements.append("first_delivery")
        profile.save()
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))

        app.push_state(MainMenuState(app.ctx))
        select(app.state, "Achievements")
        assert isinstance(app.state, AchievementCareerState)
        assert app.state.items[app.state.index].text.startswith("Menu Badges: 1 of")
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, AchievementsState)
        assert app.state.current_text().startswith("Summary: 1 of")
        assert any(item.text.startswith("Earned: Eastbound") for item in app.state.items)
        assert any(item.text.startswith("Locked: Breaker, Breaker") for item in app.state.items)
        select(app.state, "Earned: Eastbound")
        assert spoken[-1].startswith("Earned: Eastbound")
    finally:
        app.shutdown()


def test_delivery_settlement_awards_core_achievements(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ArrivalState, DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Settlement Badges")
        p = app.ctx.profile
        p.current_city = "Chicago"
        job = next(
            job for job in JobBoard(app.ctx.world).offers(
                p.current_city,
                p.career.endorsements,
                level=p.career.level,
                market=p.market,
            )
            if not job.locked_reason(p.career.endorsements, p.career.level)
        )
        route = app.ctx.world.supported_route_options(job.origin, job.destination)[0]
        driving = DrivingState(app.ctx, job, route)
        driving.trip.game_minutes = job.deadline_game_h * 30.0
        driving.speeding_strikes = 0
        monkeypatch.setattr(app.ctx, "say", lambda *_args, **_kwargs: None)

        arrival = ArrivalState(app.ctx, driving)

        earned = set(p.achievements)
        assert {"first_delivery", "first_on_time", "clean_delivery",
                "speed_limit_saint"}.issubset(earned)
        assert any(part.startswith("New achievement!") for part in arrival.summary_parts)
        reloaded = Profile.load(p.path)
        assert set(reloaded.achievements) == earned
    finally:
        app.shutdown()


def test_suppressed_award_collects_without_chime_or_speech(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile

    app = App()
    try:
        app.ctx.profile = Profile(name="Quiet Badges")
        spoken = []
        played = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **_kwargs: played.append(key))

        result = app.ctx.award_achievement("first_delivery", announce=False)

        assert result is not None
        assert spoken == []
        assert played == []
        assert app.ctx.achievement_notice.startswith("New achievement!")
    finally:
        app.shutdown()


def test_state_crossing_keeps_gameplay_prompt_before_achievement(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.sim.trip import NavigationCue, TripEvent, TripEventKind
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="State Line")
        p = app.ctx.profile
        p.current_city = "Chicago"
        job = next(
            job for job in JobBoard(app.ctx.world).offers(
                p.current_city,
                p.career.endorsements,
                level=p.career.level,
                market=p.market,
            )
            if not job.locked_reason(p.career.endorsements, p.career.level)
        )
        route = app.ctx.world.supported_route_options(job.origin, job.destination)[0]
        driving = DrivingState(app.ctx, job, route)
        spoken = []
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: spoken.append(text))

        cue = NavigationCue(
            "state:test",
            "state_crossing",
            10.0,
            "crossing from Illinois into Missouri",
            "Crossing into Missouri near St. Louis.",
        )
        driving._handle_trip_event(TripEvent(
            TripEventKind.STATE_CROSSING,
            "Crossing into Missouri near St. Louis.",
            {"cue": cue},
        ))

        assert spoken[0] == "Crossing into Missouri near St. Louis."
        assert spoken[1].startswith("New achievement! Two Places, So Far.")
    finally:
        app.shutdown()
