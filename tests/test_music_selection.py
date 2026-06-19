"""Music catalog selection and integration tests."""

from pathlib import Path

from freight_fate.music import (
    ALL_MUSIC_TRACKS,
    DAY_DRIVE_TRACKS,
    GENERATED_MUSIC_TRACKS,
    NIGHT_DRIVE_TRACKS,
    select_drive_music,
    select_drive_music_sequence,
    select_menu_music,
    select_menu_music_sequence,
)

ASSETS = Path(__file__).parents[1] / "src" / "freight_fate" / "assets" / "sounds"


def _denver_to_salt_lake_job():
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    return Job(
        CARGO_CATALOG["food"],
        12,
        "Denver",
        "Denver Warehouse",
        "Salt Lake City",
        521,
        4200,
        16,
    )


def test_menu_music_tracks_career_milestones():
    from freight_fate.models.profile import Profile

    rookie = Profile(name="Rookie")
    assert select_menu_music(rookie) == "menu_theme"

    rookie.career.deliveries = 3
    assert select_menu_music(rookie) == "menu_first_rig"

    regional = Profile(name="Regional")
    regional.career.xp = 2_500
    assert select_menu_music(regional) == "menu_regional_carrier"

    fleet = Profile(name="Fleet")
    fleet.owned_trucks.append("heavy_hauler")
    assert select_menu_music(fleet) == "menu_fleet_owner"

    coast = Profile(name="Coast")
    coast.career.total_miles = 10_000
    assert select_menu_music(coast) == "menu_coast_to_coast"

    legend = Profile(name="Legend")
    legend.career.deliveries = 40
    assert select_menu_music(legend) == "menu_legendary_haul"


def test_menu_music_sequence_is_milestone_pool():
    from freight_fate.models.profile import Profile

    rookie = Profile(name="Rookie")
    rookie_pool = select_menu_music_sequence(rookie)
    assert rookie_pool[0] == "menu_theme"
    assert len(rookie_pool) > 1
    assert "menu_theme" in rookie_pool

    coast = Profile(name="Coast")
    coast.career.total_miles = 10_000
    coast_pool = select_menu_music_sequence(coast)
    assert coast_pool[0] == "menu_coast_to_coast"
    assert len(coast_pool) > len(rookie_pool)
    assert "menu_theme" in coast_pool


def test_drive_music_sequence_is_stable_pool_for_trip_and_separates_day_night(world):
    route = world.route_from_cities(["Denver", "Salt Lake City"])
    day = select_drive_music_sequence(route, 12345, 13.0)
    assert day == select_drive_music_sequence(route, 12345, 13.5)
    assert len(day) == len(DAY_DRIVE_TRACKS)
    assert len(set(day)) > 1
    assert set(day) == {track.key for track in DAY_DRIVE_TRACKS}
    assert select_drive_music(route, 12345, 13.0) == day[0]

    night = select_drive_music_sequence(route, 12345, 23.0)
    assert night == select_drive_music_sequence(route, 12345, 23.5)
    assert len(night) == len(NIGHT_DRIVE_TRACKS)
    assert len(set(night)) > 1
    assert set(night) == {track.key for track in NIGHT_DRIVE_TRACKS}
    assert night != day


def test_city_menu_uses_milestone_music(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState

    app = App()
    played = []
    monkeypatch.setattr(app.ctx.audio, "play_music",
                        lambda track, fade_ms=1500: played.append(track))
    try:
        app.ctx.profile = Profile(name="Fleet", current_city="Chicago")
        app.ctx.profile.owned_trucks.append("heavy_hauler")
        app.push_state(CityMenuState(app.ctx))
        assert played[-1] == "menu_fleet_owner"
    finally:
        app.shutdown()


def test_main_menu_uses_latest_save_milestone_music(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.main_menu import MainMenuState

    profile = Profile(name="Coast Runner", current_city="Denver")
    profile.career.total_miles = 10_000
    profile.save()

    app = App()
    played = []
    monkeypatch.setattr(app.ctx.audio, "play_music",
                        lambda track, fade_ms=1500: played.append(track))
    try:
        app.push_state(MainMenuState(app.ctx))
        assert played[-1] == "menu_coast_to_coast"
    finally:
        app.shutdown()


def test_menu_music_pool_advances_without_immediate_repeat(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState

    app = App()
    played = []
    monkeypatch.setattr(app.ctx.audio, "play_music",
                        lambda track, fade_ms=1500: played.append(track))
    try:
        app.ctx.profile = Profile(name="Menu Pool", current_city="Chicago")
        app.ctx.profile.career.total_miles = 10_000
        state = CityMenuState(app.ctx)
        for _ in range(4):
            state.enter()
            state.exit()
        assert len(set(played)) > 1
        assert all(a != b for a, b in zip(played, played[1:], strict=False))
    finally:
        app.shutdown()


def test_pickup_facility_uses_music_pool_and_keeps_facility_ambience(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import PickupFacilityState

    app = App()
    played = []
    ambient = []
    monkeypatch.setattr(app.ctx.audio, "play_music",
                        lambda track, fade_ms=1500: played.append(track))
    monkeypatch.setattr(app.ctx.audio, "set_ambient",
                        lambda key, volume=0.7: ambient.append((key, volume)))
    try:
        app.ctx.profile = Profile(name="Pickup Pool", current_city="Denver")
        app.ctx.profile.career.total_miles = 10_000
        state = PickupFacilityState(app.ctx, _denver_to_salt_lake_job())
        for _ in range(3):
            state.enter()
            state.exit()

        assert len(set(played)) > 1
        assert all(a != b for a, b in zip(played, played[1:], strict=False))
        assert ("poi/facility_gate", 0.35) in ambient
        assert (None, 0.7) in ambient
    finally:
        app.shutdown()


def test_destination_facility_uses_music_pool_and_keeps_facility_ambience(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState, FacilityArrivalState

    app = App()
    played = []
    ambient = []
    monkeypatch.setattr(app.ctx.audio, "play_music",
                        lambda track, fade_ms=1500: played.append(track))
    monkeypatch.setattr(app.ctx.audio, "set_ambient",
                        lambda key, volume=0.7: ambient.append((key, volume)))
    try:
        app.ctx.profile = Profile(name="Destination Pool", current_city="Denver")
        app.ctx.profile.career.total_miles = 10_000
        job = _denver_to_salt_lake_job()
        route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
        driving = DrivingState(app.ctx, job, route, trip_seed=12345, start_hour=14.0)
        state = FacilityArrivalState(app.ctx, driving)
        for _ in range(3):
            state.enter()

        assert len(set(played)) > 1
        assert all(a != b for a, b in zip(played, played[1:], strict=False))
        assert ("poi/facility_gate", 0.35) in ambient
    finally:
        app.shutdown()


def test_delivery_complete_uses_music_pool(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ArrivalState, DrivingState

    app = App()
    played = []
    monkeypatch.setattr(app.ctx.audio, "play_music",
                        lambda track, fade_ms=1500: played.append(track))
    try:
        app.ctx.profile = Profile(name="Arrival Pool", current_city="Denver")
        app.ctx.profile.career.total_miles = 10_000
        job = _denver_to_salt_lake_job()
        route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
        first = DrivingState(app.ctx, job, route, trip_seed=12345, start_hour=14.0)
        second = DrivingState(app.ctx, job, route, trip_seed=12346, start_hour=14.0)
        ArrivalState(app.ctx, first).enter()
        ArrivalState(app.ctx, second).enter()

        assert len(set(played)) > 1
        assert played[0] != played[1]
    finally:
        app.shutdown()


def test_driving_state_uses_selected_drive_music(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    played = []
    monkeypatch.setattr(app.ctx.audio, "play_music",
                        lambda track, fade_ms=1500: played.append(track))
    try:
        app.ctx.profile = Profile(name="Music Test", current_city="Denver")
        job = _denver_to_salt_lake_job()
        route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
        driving = DrivingState(app.ctx, job, route, trip_seed=12345, start_hour=14.0)
        app.push_state(driving)
        assert played[-1] == driving._day_music_sequence[0]
        assert played[-1] in {track.key for track in DAY_DRIVE_TRACKS}

        played.clear()
        driving.trip.restore(driving.trip.position_mi, 9.0 * 60.0)
        driving._update_audio()
        assert played[-1] == driving._night_music_sequence[0]
        assert played[-1] in {track.key for track in NIGHT_DRIVE_TRACKS}
    finally:
        app.shutdown()


def test_night_driving_advances_through_music_pool(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.music import music_track_duration_s
    from freight_fate.states.driving import DrivingState

    app = App()
    played = []
    monkeypatch.setattr(app.ctx.audio, "play_music",
                        lambda track, fade_ms=1500: played.append(track))
    try:
        app.ctx.profile = Profile(name="Night Music", current_city="Denver")
        job = _denver_to_salt_lake_job()
        route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
        driving = DrivingState(app.ctx, job, route, trip_seed=54321, start_hour=23.0)
        app.push_state(driving)
        first = played[-1]
        duration = music_track_duration_s(first)

        driving._update_audio(duration + 0.1)
        second = played[-1]
        driving._update_audio(music_track_duration_s(second) + 0.1)
        third = played[-1]

        assert first in {track.key for track in NIGHT_DRIVE_TRACKS}
        assert second in {track.key for track in NIGHT_DRIVE_TRACKS}
        assert third in {track.key for track in NIGHT_DRIVE_TRACKS}
        assert len({first, second, third}) >= 3
    finally:
        app.shutdown()


def test_all_cataloged_music_tracks_exist():
    missing = [
        track.key for track in ALL_MUSIC_TRACKS
        if not (ASSETS / "music" / f"{track.key}.ogg").exists()
    ]
    assert not missing


def test_new_generated_music_tracks_are_at_least_one_minute():
    import soundfile as sf

    too_short = []
    for track in GENERATED_MUSIC_TRACKS:
        info = sf.info(str(ASSETS / "music" / f"{track.key}.ogg"))
        duration = info.frames / info.samplerate
        if duration < 60.0:
            too_short.append((track.key, duration))
    assert not too_short
