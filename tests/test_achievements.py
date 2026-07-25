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
        artist, _title = achievement.inspiration.split(" - ", 1)
        visible = f"{achievement.name} {achievement.description}".lower()
        assert "\n" not in achievement.description
        assert 80 <= len(achievement.description) <= 220
        assert achievement.description.count(".") >= 2
        assert '"' not in achievement.description
        assert achievement.inspiration
        # Artists stay out of player-facing text. Song titles are allowed to
        # appear (many are just place names, like Jackson or Abilene); the
        # no-lyrics rule lives in the catalog's copy note.
        assert artist.lower() not in visible

    profile = Profile(name="Copy Check")
    message = award(profile, ACHIEVEMENTS[0].id).message
    assert message.startswith("New achievement!")


def test_catalog_tops_one_hundred_with_unique_ids():
    from freight_fate.achievements import ACHIEVEMENTS

    ids = [achievement.id for achievement in ACHIEVEMENTS]
    assert len(ids) == len(set(ids))
    assert len(ids) > 100


def test_increment_stat_counts_and_survives_bad_values():
    from freight_fate.achievements import increment_stat, int_stat
    from freight_fate.models.profile import Profile

    profile = Profile(name="Counter")
    assert increment_stat(profile, "inspections_passed") == 1
    assert increment_stat(profile, "inspections_passed") == 2
    profile.achievement_stats["inspections_passed"] = "corrupt"
    assert int_stat(profile, "inspections_passed") == 0
    assert increment_stat(profile, "inspections_passed") == 1


def test_return_trip_badge_needs_the_reverse_of_the_last_route(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ArrivalState, DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Shuttle Run")
        p = app.ctx.profile
        p.current_city = "Chicago"
        job = next(
            job
            for job in JobBoard(app.ctx.world).offers(
                p.current_city,
                p.career.endorsements,
                level=p.career.level,
                market=p.market,
            )
            if not job.locked_reason(p.career.endorsements, p.career.level)
        )
        route = app.ctx.world.supported_route_options(job.origin, job.destination)[0]
        # The previous delivery ran this exact lane the other way around.
        p.achievement_stats["last_route"] = [job.destination, job.origin]
        driving = DrivingState(app.ctx, job, route)
        driving.trip.game_minutes = job.deadline_game_h * 30.0
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_k: None)

        ArrivalState(app.ctx, driving)

        assert "return_trip" in p.achievements
        # The lane just driven becomes the new benchmark for the next run.
        assert p.achievement_stats["last_route"] == [job.origin, job.destination]
        # A career's home city is pinned by the first delivery's origin.
        assert p.achievement_stats["home_city"] == job.origin
    finally:
        app.shutdown()


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


def test_event_achievement_speaks_through_screen_reader(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile

    app = App()
    try:
        app.ctx.profile = Profile(name="Screen Reader Badges")
        screen_reader = []
        events = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: screen_reader.append(text))
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))

        result = app.ctx.award_achievement("first_delivery", event=True)

        assert result is not None
        assert screen_reader == [result.message]
        assert events == []
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
        assert any(item.text.startswith("Earned: Signed") for item in app.state.items)
        assert any(item.text.startswith("Locked: Breaker, Breaker") for item in app.state.items)
        select(app.state, "Earned: Signed")
        assert spoken[-1].startswith("Earned: Signed")
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
            job
            for job in JobBoard(app.ctx.world).offers(
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
        assert {"first_delivery", "first_on_time", "clean_delivery", "speed_limit_saint"}.issubset(
            earned
        )
        assert any(part.startswith("New achievement!") for part in arrival.summary_parts)
        reloaded = Profile.load(p.path)
        assert set(reloaded.achievements) == earned
    finally:
        app.shutdown()


def test_eastbound_badge_fires_only_on_an_eastbound_delivery(monkeypatch):
    from freight_fate.achievements import ACHIEVEMENT_BY_ID
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ArrivalState, DrivingState

    # The first-delivery badge is direction-neutral now; "eastbound" is its own.
    assert "eastbound" not in ACHIEVEMENT_BY_ID["first_delivery"].name.lower()

    app = App()
    try:
        app.ctx.profile = Profile(name="Eastbound Run")
        p = app.ctx.profile
        p.current_city = "chicago_il_us"
        world = app.ctx.world
        origin_lon = world.city("Chicago").lon
        # Find any unlocked, net-eastbound job Chicago offers. Which seed yields
        # one shifts as the map grows (more western destinations dilute a single
        # seed's draw), so search seeds instead of pinning one -- the test only
        # needs a genuine eastbound delivery, not a specific one.
        job = next(
            (
                candidate
                for seed in range(200)
                for candidate in JobBoard(world, seed=seed).offers(
                    "Chicago", p.career.endorsements, level=5, market=p.market
                )
                if not candidate.locked_reason(p.career.endorsements, p.career.level)
                and world.cities[candidate.destination].lon > origin_lon + 1.0  # net eastbound
            ),
            None,
        )
        assert job is not None, "expected Chicago to offer a net-eastbound job under some seed"
        route = world.supported_route_options(job.origin, job.destination)[0]
        driving = DrivingState(app.ctx, job, route)
        driving.trip.game_minutes = job.deadline_game_h * 30.0
        driving.speeding_strikes = 0
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_k: None)

        ArrivalState(app.ctx, driving)

        assert "eastbound_delivery" in p.achievements
        assert "westbound_delivery" not in p.achievements
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
            job
            for job in JobBoard(app.ctx.world).offers(
                p.current_city,
                p.career.endorsements,
                level=p.career.level,
                market=p.market,
            )
            if not job.locked_reason(p.career.endorsements, p.career.level)
        )
        route = app.ctx.world.supported_route_options(job.origin, job.destination)[0]
        driving = DrivingState(app.ctx, job, route)
        events = []
        screen_reader = []
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: screen_reader.append(text))

        cue = NavigationCue(
            "state:test",
            "state_crossing",
            10.0,
            "crossing from Illinois into Missouri",
            "Crossing into Missouri near St. Louis.",
        )
        driving._handle_trip_event(
            TripEvent(
                TripEventKind.STATE_CROSSING,
                "Crossing into Missouri near St. Louis.",
                {"cue": cue},
            )
        )

        assert events == ["Crossing into Missouri near St. Louis."]
        assert screen_reader[0].startswith("New achievement! Kept It Between the Lines.")
    finally:
        app.shutdown()


# -- the 2026-07-25 additions: radio, craft, and a few bad ideas -------------------


def _driving_for_badges():
    """A drive with the physics quiet, for exercising badge triggers only."""
    import sys

    sys.path.insert(0, "tests")
    from driving_feature_helpers import open_limits, quiet_trip, start_drive

    from freight_fate.app import App

    app = App()
    app.ctx.say = lambda *a, **k: None
    app.ctx.say_event = lambda *a, **k: None
    awarded: list[str] = []
    original = app.ctx.award_achievement

    def spy(achievement_id, **kwargs):
        awarded.append(achievement_id)
        return original(achievement_id, **kwargs)

    app.ctx.award_achievement = spy
    driving = start_drive(app)
    quiet_trip(driving)
    open_limits(driving)
    driving.trip.traffic_context = lambda: None
    driving.trip.grade_at = lambda mile: 0.0
    t = driving.truck
    t.start_engine()
    t.set_air_ready(parking_brake=False)
    t.transmission.gear = t.transmission.num_gears
    t.grade = 0.0
    return app, driving, awarded


def test_the_number_that_means_nothing_takes_a_whole_mile():
    """Sixty-nine has to be held, not merely passed through."""
    app, driving, awarded = _driving_for_badges()
    try:
        t = driving.truck
        # Passing through the number on the way somewhere else is not holding it.
        for speed in (60.0, 69.0, 75.0, 69.0):
            t.velocity_mps = speed / 2.23694
            driving._track_driving_badges(1 / 60)
        assert "sixty_nine_mph" not in awarded

        for _ in range(70 * 60):  # a mile at sixty-nine takes about fifty seconds
            t.velocity_mps = 69.0 / 2.23694
            driving._track_driving_badges(1 / 60)
        assert "sixty_nine_mph" in awarded
    finally:
        app.shutdown()


def test_eighty_eight_miles_an_hour_is_noticed():
    app, driving, awarded = _driving_for_badges()
    try:
        driving.truck.velocity_mps = 80.0 / 2.23694
        driving._track_driving_badges(1 / 60)
        assert "eighty_eight_mph" not in awarded
        driving.truck.velocity_mps = 89.0 / 2.23694
        driving._track_driving_badges(1 / 60)
        assert "eighty_eight_mph" in awarded
    finally:
        app.shutdown()


def test_a_jake_only_descent_is_ruined_by_one_touch_of_the_brake():
    """The badge is for the gear discipline, so the service brake resets it."""
    app, driving, awarded = _driving_for_badges()
    try:
        t = driving.truck
        t.grade = -0.05
        t.engine_brake_stage = 2

        def roll(seconds, brake=0.0):
            for _ in range(int(seconds * 60)):
                t.velocity_mps = 55.0 / 2.23694
                t.brake = brake
                driving._track_driving_badges(1 / 60)

        roll(100)  # most of the way there
        roll(1, brake=0.4)  # one touch, and it starts over
        assert "jake_only_descent" not in awarded
        roll(200)
        assert "jake_only_descent" in awarded
    finally:
        app.shutdown()


def test_cooking_the_drums_is_its_own_badge():
    app, driving, awarded = _driving_for_badges()
    try:
        t = driving.truck
        t.brake_temp_c = t.brake_fade_onset_c - 50.0
        driving._track_driving_badges(1 / 60)
        assert "brake_smoke" not in awarded
        t.brake_temp_c = t.brake_fade_onset_c + 10.0
        driving._track_driving_badges(1 / 60)
        assert "brake_smoke" in awarded
    finally:
        app.shutdown()


def test_the_radio_badges_follow_the_signal():
    """Holding a station across three states, and catching one at the fringe."""
    from types import SimpleNamespace

    app, driving, awarded = _driving_for_badges()
    try:
        station = SimpleNamespace(id="ff:test", display_name="Test Radio")
        reception = SimpleNamespace(station=station)
        driving._radio_signal_factor = 1.0
        for state in ("Illinois", "Indiana"):
            driving.trip.state_at = lambda _mile=None, s=state: s
            driving._track_radio_badges(reception)
        assert "radio_three_states" not in awarded
        driving.trip.state_at = lambda _mile=None: "Ohio"
        driving._track_radio_badges(reception)
        assert "radio_three_states" in awarded

        # A signal down in the hiss is a fringe catch.
        awarded.clear()
        driving._radio_signal_factor = 0.01
        driving._track_radio_badges(reception)
        assert "radio_fringe_catch" in awarded
    finally:
        app.shutdown()


def test_a_new_station_restarts_the_three_state_tally():
    from types import SimpleNamespace

    app, driving, awarded = _driving_for_badges()
    try:
        driving._radio_signal_factor = 1.0
        for index, state in enumerate(("Illinois", "Indiana", "Ohio")):
            driving.trip.state_at = lambda _mile=None, s=state: s
            # A different station every state: no single signal held three.
            driving._track_radio_badges(SimpleNamespace(station=SimpleNamespace(id=f"ff:{index}")))
        assert "radio_three_states" not in awarded
    finally:
        app.shutdown()


def test_the_funny_ones_are_actually_in_the_catalog():
    """They are jokes, but they are shipped jokes and they follow the copy rules."""
    from freight_fate.achievements import ACHIEVEMENTS

    by_id = {a.id: a for a in ACHIEVEMENTS}
    for badge_id in (
        "sixty_nine_mph",
        "eighty_eight_mph",
        "sixteen_tons",
        "brake_smoke",
        "one_for_the_road",
    ):
        badge = by_id[badge_id]
        assert badge.inspiration.count(" - ") >= 1  # artist and title, both named
        assert badge.description.strip()


def test_every_badge_cites_a_song():
    """The catalog's whole voice rests on this; a new one must not break it."""
    from freight_fate.achievements import ACHIEVEMENTS

    for badge in ACHIEVEMENTS:
        artist, title = badge.inspiration.split(" - ", 1)
        assert artist.strip() and title.strip(), badge.id
