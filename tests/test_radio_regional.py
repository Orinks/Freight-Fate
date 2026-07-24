"""Regional stations, signal falloff, and host breaks on the in-cab radio."""

from importlib import resources

import pytest
from asset_helpers import asset_exists

from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.music import (
    ALL_HOST_SEGMENTS,
    STATION_HOST_SEGMENTS,
    STATION_PLAYLISTS,
    music_track_duration_s,
    select_host_segments,
    select_station_playlist,
)
from freight_fate.radio import (
    DEFAULT_RADIO_CATALOG,
    RadioState,
    estimate_signal,
    signal_volume_factor,
)

DALLAS = (32.7767, -96.7970)
CHICAGO = (41.8781, -87.6298)

REGIONAL = [s for s in DEFAULT_RADIO_CATALOG if s.source_type == "regional"]


def _station(station_id):
    return next(s for s in DEFAULT_RADIO_CATALOG if s.id == station_id)


def test_regional_stations_are_streamer_safe_fiction_with_real_ranges():
    assert len(REGIONAL) >= 10
    for station in REGIONAL:
        assert not station.real_stream
        assert station.safe_for_streaming
        assert station.supported
        assert station.lat is not None and station.lon is not None
        # realistic FM contours: strong regional stations, not continent-wide
        assert 80 <= station.range_miles <= 150
        assert station.playlist in STATION_PLAYLISTS
        # US call-sign convention: K west of the Mississippi, W east
        assert station.call_sign[0] in {"K", "W"}


def test_regional_playlists_have_generated_music_on_disk():
    sounds = resources.files("freight_fate.assets") / "sounds" / "music"
    for playlist, tracks in STATION_PLAYLISTS.items():
        assert tracks, playlist
        for track in tracks:
            assert asset_exists(sounds, track.key), track.key


def test_host_segments_have_generated_voice_clips_on_disk():
    sounds = resources.files("freight_fate.assets") / "sounds" / "music"
    assert len(ALL_HOST_SEGMENTS) == 12
    for segment in ALL_HOST_SEGMENTS:
        assert asset_exists(sounds, segment.key), segment.key
    static = resources.files("freight_fate.assets") / "sounds" / "radio" / "static_burst.ogg"
    assert static.is_file()


def test_builtin_stations_have_hosts_and_playlists():
    roadhouse = _station("route_playlist")
    nightline = _station("ff-night-line")
    assert roadhouse.playlist == "route"
    assert roadhouse.host == "roadhouse"
    assert nightline.playlist == "night"
    assert nightline.host == "nightline"
    assert STATION_HOST_SEGMENTS["roadhouse"]
    assert STATION_HOST_SEGMENTS["nightline"]


def test_checked_catalog_has_no_maintenance_heavy_public_stream_urls():
    assert not any(station.real_stream for station in DEFAULT_RADIO_CATALOG)
    assert not any(station.stream_url for station in DEFAULT_RADIO_CATALOG)


def test_signal_volume_factor_fades_with_distance():
    station = _station("krwl-dallas")
    at_tower = estimate_signal(station, DALLAS)
    assert signal_volume_factor(at_tower) == 1.0

    fringe_position = (DALLAS[0], DALLAS[1] + 1.9)  # ~110 mi east of Dallas
    fringe = estimate_signal(station, fringe_position)
    assert 0.0 < fringe.signal < 0.6
    assert 0.3 <= signal_volume_factor(fringe) < 1.0

    gone = estimate_signal(station, CHICAGO)
    assert gone.signal == 0.0
    assert signal_volume_factor(gone) == 0.0

    always = estimate_signal(_station("route_playlist"), None)
    assert signal_volume_factor(always) == 1.0


def test_fringe_factor_is_monotonic_toward_the_range_edge():
    station = _station("krwl-dallas")
    factors = []
    for east in (0.0, 0.6, 1.2, 1.8):
        reception = estimate_signal(station, (DALLAS[0], DALLAS[1] + east))
        factors.append(signal_volume_factor(reception))
    assert factors == sorted(factors, reverse=True)


def test_regional_station_receivable_only_near_its_market():
    radio = RadioState(position=DALLAS)
    ids_near_dallas = {r.station.id for r in radio.receivable_stations()}
    assert "krwl-dallas" in ids_near_dallas
    assert "wgrx-chicago" not in ids_near_dallas

    radio.update_position(CHICAGO)
    ids_near_chicago = {r.station.id for r in radio.receivable_stations()}
    assert "wgrx-chicago" in ids_near_chicago
    assert "krwl-dallas" not in ids_near_chicago


def test_station_playlist_selection_is_deterministic_and_complete():
    first = select_station_playlist("classic_rock", "seed|wgrx-chicago")
    second = select_station_playlist("classic_rock", "seed|wgrx-chicago")
    assert first == second
    assert set(first) == {t.key for t in STATION_PLAYLISTS["classic_rock"]}
    other = select_station_playlist("classic_rock", "seed|kdrt-phoenix")
    assert set(other) == set(first)

    hosts = select_host_segments("roadhouse", "seed|route_playlist")
    assert set(hosts) == {t.key for t in STATION_HOST_SEGMENTS["roadhouse"]}
    assert select_host_segments("", "seed|none") == ()


def _drive_job() -> Job:
    return Job(
        CARGO_CATALOG["general"],
        12.0,
        "Denver",
        "Denver Dry Warehouse",
        "Salt Lake City",
        520.0,
        2400.0,
        14.0,
    )


@pytest.fixture
def denver_driving(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    played_music = []
    played_effects = []
    events = []
    monkeypatch.setattr(
        app.ctx.audio, "play_music", lambda track, fade_ms=1500: played_music.append(track)
    )
    monkeypatch.setattr(
        app.ctx.audio,
        "play",
        lambda key, volume=1.0, pan=0.0: played_effects.append((key, volume)),
    )
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
    from freight_fate.models.profile import Profile

    app.ctx.profile = Profile(name="Radio Range", current_city="Denver")
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, _drive_job(), route, trip_seed=777, start_hour=13.0)
    app.push_state(driving)
    try:
        yield app, driving, played_music, played_effects, events
    finally:
        app.shutdown()


def test_regional_station_plays_its_format_pool_while_in_range(denver_driving):
    app, driving, played_music, _effects, _events = denver_driving
    driving.radio.update_position((39.7392, -104.9903))  # at the Denver anchor

    action = driving.radio.select_station("krdg-denver", driving._radio_backend)

    assert action.station.id == "krdg-denver"
    rock = {t.key for t in STATION_PLAYLISTS["classic_rock"]}
    assert played_music[-1] in rock

    first = played_music[-1]
    driving._update_radio_playback(False, music_track_duration_s(first) + 0.1)
    assert played_music[-1] in rock
    assert played_music[-1] != first


def test_station_fades_out_of_range_and_falls_back_to_roadhouse(denver_driving):
    app, driving, played_music, played_effects, events = denver_driving
    driving.radio.update_position((39.7392, -104.9903))
    driving.radio.select_station("krdg-denver", driving._radio_backend)

    # drive far beyond The Ridge's contour: reception check retunes safely
    def far_from_denver(route, position_mi, world):
        return (40.7608, -111.8910)  # Salt Lake City

    import freight_fate.states.driving_updates as driving_updates

    driving._radio_signal_timer = 0.0
    orig = driving_updates.truck_position
    driving_updates.truck_position = far_from_denver
    try:
        driving._update_radio_reception(1.0)
    finally:
        driving_updates.truck_position = orig

    assert driving.radio.current_station().id == "route_playlist"
    assert any("faded out of range" in text for text in events)
    assert any(key == "radio/static_burst" for key, _v in played_effects)


def test_fringe_signal_thins_radio_volume(denver_driving):
    app, driving, _music, played_effects, _events = denver_driving
    applied = []
    driving.ctx.audio.set_volumes = lambda **kw: applied.append(kw)
    driving.radio.select_station("krdg-denver", driving._radio_backend)

    fringe = (39.7392, -104.9903 + 2.1)  # ~110 miles east of the Denver tower

    import freight_fate.states.driving_updates as driving_updates

    orig = driving_updates.truck_position
    driving_updates.truck_position = lambda route, position_mi, world: fringe
    driving._radio_signal_timer = 0.0
    try:
        driving._update_radio_reception(1.0)
    finally:
        driving_updates.truck_position = orig

    assert applied, "reception update should re-apply the radio volume"
    volume = applied[-1]["music"]
    assert 0.0 < volume < driving.ctx.settings.radio_volume
    # fringe reception crackles
    assert any(key == "radio/static_burst" for key, _v in played_effects)


def test_how_to_play_documents_the_radio_page():
    from freight_fate.states.main_menu import HELP_PAGES

    titles = [title for title, _lines in HELP_PAGES]
    assert "The in-cab radio" in titles
    help_text = " ".join(line for _title, lines in HELP_PAGES for line in lines).lower()
    assert "join that same dial quietly" in help_text
    assert "left and right bracket tune every station" in help_text
    assert "streamer-safe status" in help_text
    assert "online services are on" in help_text
    assert "active audio system can play public streams" in help_text
    assert "personal playlists play only when streamer-safe mode is off" in help_text
    assert "host breaks in between songs" in help_text
    assert "regional stations cover markets across the map" in help_text
    assert "static crackle at the fringe" in help_text
    assert "falls" in help_text and "back to the roadhouse" in help_text
