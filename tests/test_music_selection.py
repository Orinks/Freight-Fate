"""Music catalog selection and integration tests."""

from pathlib import Path

from freight_fate.music import (
    ALL_MUSIC_TRACKS,
    DAY_DRIVE_TRACKS,
    NIGHT_DRIVE_TRACKS,
    select_drive_music,
    select_menu_music,
)

ASSETS = Path(__file__).parents[1] / "src" / "freight_fate" / "assets" / "sounds"


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


def test_drive_music_is_stable_for_trip_and_separates_day_night(world):
    route = world.route_from_cities(["Denver", "Salt Lake City"])
    day = select_drive_music(route, 12345, 13.0)
    assert day == select_drive_music(route, 12345, 13.5)
    assert day in {track.key for track in DAY_DRIVE_TRACKS}

    night = select_drive_music(route, 12345, 23.0)
    assert night == select_drive_music(route, 12345, 23.5)
    assert night in {track.key for track in NIGHT_DRIVE_TRACKS}
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


def test_driving_state_uses_selected_drive_music(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    played = []
    monkeypatch.setattr(app.ctx.audio, "play_music",
                        lambda track, fade_ms=1500: played.append(track))
    try:
        app.ctx.profile = Profile(name="Music Test", current_city="Denver")
        job = Job(
            CARGO_CATALOG["food"],
            12,
            "Denver",
            "Denver Warehouse",
            "Salt Lake City",
            521,
            4200,
            16,
        )
        route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
        driving = DrivingState(app.ctx, job, route, trip_seed=12345, start_hour=14.0)
        app.push_state(driving)
        assert played[-1] == driving._day_music_track
        assert played[-1] in {track.key for track in DAY_DRIVE_TRACKS}

        played.clear()
        driving.trip.restore(driving.trip.position_mi, 9.0 * 60.0)
        driving._update_audio()
        assert played[-1] == driving._night_music_track
        assert played[-1] in {track.key for track in NIGHT_DRIVE_TRACKS}
    finally:
        app.shutdown()


def test_all_cataloged_music_tracks_exist():
    missing = [
        track.key for track in ALL_MUSIC_TRACKS
        if not (ASSETS / "music" / f"{track.key}.ogg").exists()
    ]
    assert not missing
