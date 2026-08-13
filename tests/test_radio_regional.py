"""Regional stations, signal falloff, and host breaks on the in-cab radio."""

import math
from importlib import resources

import pytest
from asset_helpers import asset_exists
from speech_capture import speech_stub

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
    EARTH_RADIUS_MI,
    RADIO_REACH_MULT,
    SIGNAL_DEEP_FLOOR,
    SIGNAL_FULL_VOLUME,
    STATIC_SIGNAL_THRESHOLD,
    RadioReception,
    RadioState,
    RadioStation,
    effective_range_miles,
    estimate_signal,
    signal_volume_factor,
)

DALLAS = (32.7767, -96.7970)
CHICAGO = (41.8781, -87.6298)


def _north_of(position, miles):
    """Move due north by `miles` from `position`.

    Exact for a pure meridian offset: the haversine formula collapses to
    the great-circle arc R * dlat when dlon is 0, so this needs no
    small-angle approximation.
    """
    lat, lon = position
    return (lat + math.degrees(miles / EARTH_RADIUS_MI), lon)


REGIONAL = [s for s in DEFAULT_RADIO_CATALOG if s.source_type == "regional"]


def _station(station_id):
    return next(s for s in DEFAULT_RADIO_CATALOG if s.id == station_id)


# Reception-physics fixtures: the fictional catalog stations are always
# available now (every player hears the FF music), so range, fringe, and
# elevation behavior is pinned on stations built here with the old contours.
def _ranged_fixture(
    station_id="kfix-dallas",
    lat=DALLAS[0],
    lon=DALLAS[1],
    range_miles=120.0,
    site_elev_ft=None,
    playlist="",
):
    return RadioStation(
        station_id,
        "Fixture FM",
        "KFIX",
        "country",
        "reception fixture",
        lat=lat,
        lon=lon,
        range_miles=range_miles,
        site_elev_ft=site_elev_ft,
        playlist=playlist,
    )


def test_regional_stations_are_streamer_safe_fiction_available_everywhere():
    assert len(REGIONAL) >= 10
    for station in REGIONAL:
        assert not station.real_stream
        assert station.safe_for_streaming
        assert station.supported
        # Every player hears the FF music: no transmitter bubble, no mode gate.
        assert station.always_available
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
    static = resources.files("freight_fate.assets") / "sounds" / "radio"
    assert asset_exists(static, "static_burst")


def test_builtin_stations_have_hosts_and_playlists():
    roadhouse = _station("route_playlist")
    nightline = _station("ff-night-line")
    assert roadhouse.playlist == "route"
    assert roadhouse.host == "roadhouse"
    assert nightline.playlist == "night"
    assert nightline.host == "nightline"
    assert STATION_HOST_SEGMENTS["roadhouse"]
    assert STATION_HOST_SEGMENTS["nightline"]


def test_new_afn_globals_are_cataloged_with_checked_sources():
    for station_id in ("afn-global-fans", "afn-global-holiday", "afn-mach-5"):
        station = _station(station_id)
        assert station.real_stream
        assert station.stream_url.startswith("http")
        assert "Radio Browser" in station.source
        assert station.always_available


def test_effective_range_doubles_the_published_contour():
    # Compression compensation (owner design 2026-08-13): the truck covers
    # road miles far faster than a real cab, so the published FM contour is
    # doubled before any distance math touches it.
    station = _ranged_fixture(range_miles=40.0)
    assert effective_range_miles(station, None) == 40.0 * RADIO_REACH_MULT == 80.0

    # Range-less (built-in) stations are untouched: 0 * mult is still 0.
    builtin = _ranged_fixture(range_miles=0.0)
    assert effective_range_miles(builtin, None) == 0.0


def test_signal_volume_factor_holds_clean_through_most_of_the_contour():
    # Fixture range_miles=40.0 -> 80 game-miles of reach (RADIO_REACH_MULT).
    station = _ranged_fixture(range_miles=40.0)
    at_tower = estimate_signal(station, DALLAS)
    assert signal_volume_factor(at_tower) == 1.0

    # Clean through 80% of the contour (64 of 80 game-miles).
    clean_position = _north_of(DALLAS, 64.0)
    clean = estimate_signal(station, clean_position)
    assert signal_volume_factor(clean) == 1.0

    # Fading past 85% (70 of 80 game-miles): off full quieting, not yet
    # static.
    fading_position = _north_of(DALLAS, 70.0)
    fading = estimate_signal(station, fading_position)
    assert 0.0 < signal_volume_factor(fading) < 1.0

    # deep fringe (76 of 80 game-miles): the program sinks under the rising
    # static but a trace survives while the station is technically in range
    # (owner's smear rule)
    deep_fringe_position = _north_of(DALLAS, 76.0)
    deep_fringe = estimate_signal(station, deep_fringe_position)
    assert 0.1 < signal_volume_factor(deep_fringe) < 0.6

    gone = estimate_signal(station, CHICAGO)
    assert gone.signal == 0.0
    assert signal_volume_factor(gone) == 0.0

    always = estimate_signal(_station("route_playlist"), None)
    assert signal_volume_factor(always) == 1.0


def test_signal_volume_factor_is_continuous_at_the_new_joins():
    # Hand-pin the curve at the exact join points, bypassing lat/lon
    # geometry. The owner's smear ruling: static rises TO program level,
    # never on top of a still-loud one -- these two branches must agree
    # exactly where they meet.
    station = _ranged_fixture()

    def _factor(signal):
        return signal_volume_factor(RadioReception(station, 10.0, signal, "in range"))

    # Full-volume join: right at the threshold is still clean, a hair
    # below starts fading.
    assert _factor(0.20) == 1.0
    assert _factor(0.1999) < 1.0

    # Static join: the fringe formula and the deep-floor formula meet at
    # the same value -- static rises TO program level, never above it.
    edge = _factor(0.12)
    assert edge == pytest.approx(0.72)
    assert _factor(0.1201) > edge  # just inside the fringe: a hair louder
    assert _factor(0.1199) < edge  # just past: sinking, never a jump up

    # Deep floor: keeps sinking, never below the floor, never silent while
    # still technically in range.
    assert _factor(0.005) == pytest.approx(SIGNAL_DEEP_FLOOR)


def test_elevation_extends_fm_range_like_the_rim(  # the owner's ham anchor
):
    # From high ground you receive far past the flat contour: line-of-sight
    # FM, 4/3-earth radio horizon. Desert Rock Phoenix (site 1086 ft, range
    # 125 mi -> 250 game-mi flat reach) at ~300 miles: silent on the flats,
    # clear from ~7000 ft.
    station = _ranged_fixture(
        "kfix-phoenix", lat=33.4484, lon=-112.074, range_miles=125.0, site_elev_ft=1086.0
    )
    far_north = _north_of((station.lat, station.lon), 300.0)

    flat = estimate_signal(station, far_north, elevation_ft=station.site_elev_ft)
    assert flat.signal == 0.0
    assert flat.reason == "out of range"

    rim = estimate_signal(station, far_north, elevation_ft=7000.0)
    assert rim.signal > 0.0

    # no elevation data behaves exactly like the flat model
    unknown = estimate_signal(station, far_north)
    assert unknown.signal == 0.0


def test_below_the_tower_site_is_neutral_never_a_penalty():
    # A mountain-top transmitter looks straight down into its own valley:
    # every in-market listener sits below the site, and that must never
    # shrink the contour (KJZZ on South Mountain serving Phoenix).
    station = _ranged_fixture(
        "kfix-denver", lat=39.7392, lon=-104.9903, range_miles=125.0, site_elev_ft=5280.0
    )
    at_100mi = (station.lat + 1.45, station.lon)

    at_site_level = estimate_signal(station, at_100mi, elevation_ft=station.site_elev_ft)
    below_site = estimate_signal(station, at_100mi, elevation_ft=3800.0)
    assert below_site.signal == pytest.approx(at_site_level.signal)
    assert below_site.signal > 0.0


def test_fringe_factor_is_monotonic_toward_the_range_edge():
    station = _ranged_fixture()
    factors = []
    for east in (0.0, 0.6, 1.2, 1.8):
        reception = estimate_signal(station, (DALLAS[0], DALLAS[1] + east))
        factors.append(signal_volume_factor(reception))
    assert factors == sorted(factors, reverse=True)


def test_ranged_station_receivable_only_near_its_market():
    dallas_fix = _ranged_fixture("kfix-dallas")
    chicago_fix = _ranged_fixture("wfix-chicago", lat=CHICAGO[0], lon=CHICAGO[1])
    radio = RadioState(catalog=DEFAULT_RADIO_CATALOG + (dallas_fix, chicago_fix), position=DALLAS)
    ids_near_dallas = {r.station.id for r in radio.receivable_stations()}
    assert "kfix-dallas" in ids_near_dallas
    assert "wfix-chicago" not in ids_near_dallas

    radio.update_position(CHICAGO)
    ids_near_chicago = {r.station.id for r in radio.receivable_stations()}
    assert "wfix-chicago" in ids_near_chicago
    assert "kfix-dallas" not in ids_near_chicago


def _terrestrial_at(station_id, call_sign, degrees_east, range_miles=120.0):
    return RadioStation(
        station_id,
        f"{call_sign} FM",
        call_sign,
        "country",
        "reception fixture",
        lat=DALLAS[0],
        lon=DALLAS[1] + degrees_east,
        range_miles=range_miles,
    )


def test_terrestrial_category_sorts_strongest_signal_first():
    # Call signs deliberately disagree with signal order: the old call-sign
    # sort opened the band on the fringe station at the start of every run.
    near = _terrestrial_at("fix-near", "WZZZ", 0.0)
    mid = _terrestrial_at("fix-mid", "KMMM", 0.9)
    far = _terrestrial_at("fix-far", "KAAA", 1.8)
    radio = RadioState(catalog=(far, mid, near), position=DALLAS)

    ids = [r.station.id for r in radio.receivable_stations()]

    assert ids == ["fix-near", "fix-mid", "fix-far"]


def test_power_on_retunes_a_fringe_memory_to_the_strongest_signal():
    strong = _terrestrial_at("fix-strong", "WZZZ", 0.0)
    # ~232 mi east: past the doubled 240 mi reach's clean threshold, still
    # technically in range.
    fringe = _terrestrial_at("fix-fringe", "KAAA", 4.0)
    radio = RadioState(catalog=(strong, fringe), station_id="fix-fringe", position=DALLAS)

    radio.toggle()  # off
    action = radio.toggle()  # back on: the fringe memory does not play clean

    assert action.enabled is True
    assert action.station.id == "fix-strong"


def test_power_on_keeps_a_station_that_still_plays_clean():
    from freight_fate.radio import SAFE_ROUTE_PLAYLIST

    # A full-volume terrestrial memory holds the dial even against a
    # stronger neighbor; so does any always-available choice.
    strongest = _terrestrial_at("fix-strongest", "KAAA", 0.0)
    clean = _terrestrial_at("fix-clean", "WZZZ", 0.35)  # ~20 mi: full volume
    radio = RadioState(catalog=(strongest, clean), station_id="fix-clean", position=DALLAS)
    radio.toggle()
    assert radio.toggle().station.id == "fix-clean"

    playlist = RadioState(station_id=SAFE_ROUTE_PLAYLIST, position=DALLAS)
    playlist.toggle()
    assert playlist.toggle().station.id == SAFE_ROUTE_PLAYLIST


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
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
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
    ranged = _ranged_fixture("kfix-denver", lat=39.7392, lon=-104.9903, playlist="classic_rock")
    driving.radio.catalog = driving.radio.catalog + (ranged,)
    driving.radio.update_position((39.7392, -104.9903))
    driving.radio.select_station("kfix-denver", driving._radio_backend)

    # drive far beyond The Ridge's contour: reception check retunes safely
    def far_from_denver(route, position_mi, world):
        return (40.7608, -111.8910)  # Salt Lake City

    import freight_fate.states.driving_updates as driving_updates

    # The drive to the contour edge left the fringe renderer live: hiss bed
    # up, pickets ducking the program. All of it belongs to the dying station.
    driving._radio_fringe_signal = 0.15
    driving._fringe_bed_active = True
    driving._radio_picket_duck = 0.5

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
    # The dead station's fringe dies with it: no hiss or picket duck may
    # survive the handover to sit over the always-available fallback.
    assert driving._radio_fringe_signal is None
    assert driving._fringe_bed_active is False
    assert driving._radio_picket_duck == 1.0


def test_streamer_safe_flip_mid_drive_hands_over_audibly(denver_driving, monkeypatch):
    # Turning streamer-safe on from the pause settings while a licensed
    # stream plays: the stream leaves the air immediately, the cab says so,
    # and the radio lands on the Roadhouse -- never the silent fallback.
    # Flipping back off restores the dial without moving the radio again.
    app, driving, played_music, _effects, events = denver_driving
    streams = []
    monkeypatch.setattr(
        driving.ctx.audio, "play_radio_stream", lambda url, fade_ms=1500: streams.append(url)
    )
    driving.truck.start_engine()
    station = RadioStation(
        "kfix-live",
        "Denver Live",
        "KLIV",
        "news",
        "fixture",
        lat=39.7392,
        lon=-104.9903,
        range_miles=120.0,
        real_stream=True,
        stream_url="https://example.test/live.mp3",
        safe_for_streaming=False,
    )
    driving.radio.catalog = driving.radio.catalog + (station,)
    driving.radio.update_position((39.7392, -104.9903))
    driving.radio.select_station("kfix-live", driving._radio_backend)
    assert streams == [station.stream_url]
    played_music.clear()

    app.ctx.settings.radio_streamer_safe = True
    app.ctx.apply_active_radio_settings()

    assert driving.radio.current_station().id == "route_playlist"
    assert any("left the dial" in text for text in events)
    assert played_music, "the Roadhouse takes the channel from the stream"

    events.clear()
    app.ctx.settings.radio_streamer_safe = False
    app.ctx.apply_active_radio_settings()

    assert driving.radio.current_station().id == "route_playlist"
    assert not events, "nothing to say: the dial just fills back in"
    assert "kfix-live" in {s.id for s in driving.radio.available_stations()}


def test_fringe_signal_thins_radio_volume(denver_driving):
    app, driving, _music, played_effects, _events = denver_driving
    applied = []
    driving.ctx.audio.set_volumes = lambda **kw: applied.append(kw)
    ranged = _ranged_fixture("kfix-denver", lat=39.7392, lon=-104.9903, playlist="classic_rock")
    driving.radio.catalog = driving.radio.catalog + (ranged,)
    driving.radio.select_station("kfix-denver", driving._radio_backend)

    # ~228 miles east of the Denver tower: past the doubled 240 mi reach's
    # clean threshold, still technically in range.
    fringe = (39.7392, -104.9903 + 4.3)

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


def _fringe_stream_station():
    return RadioStation(
        "kfog-test",
        "Test FM",
        "KFOG",
        "music",
        "fixture",
        stream_url="https://example.test/live.aac",
        real_stream=True,
    )


def test_dead_stream_reconnects_quietly_and_never_crackles(denver_driving, monkeypatch):
    # A real stream the dock bed (or a network stall) killed: the reception
    # tick re-tunes it silently and plays NO fringe static -- a silent radio
    # has no program for static to sit under (the Merced ghost-hiss bug).
    app, driving, _music, played_effects, _events = denver_driving
    station = _fringe_stream_station()
    reception = RadioReception(station, 90.0, 0.2, "in range")
    driving.radio.enabled = True
    monkeypatch.setattr(driving.radio, "current_station", lambda: station)
    monkeypatch.setattr(driving.radio, "current_reception", lambda: reception)
    monkeypatch.setattr(driving.ctx.audio, "music_playing", lambda: False)
    streams = []
    monkeypatch.setattr(
        driving.ctx.audio, "play_radio_stream", lambda url, fade_ms=1500: streams.append(url)
    )

    driving._radio_signal_timer = 0.0
    driving._update_radio_reception(1.0)

    assert streams == [station.stream_url]
    assert not any(key == "radio/static_burst" for key, _v in played_effects)

    # retries back off instead of hammering the stream every tick
    driving._radio_signal_timer = 0.0
    driving._update_radio_reception(1.0)
    assert streams == [station.stream_url]


def test_live_fringe_stream_gets_hiss_bed_and_pickets(denver_driving, monkeypatch):
    # A thinning but audible station: the reception tick caches the fringe,
    # the per-frame renderer brings in the hiss bed and fires a sharp picket
    # that ducks the program hard, then releases it. FRINGE_BED_SIGNAL and
    # PICKET_SIGNAL now reference radio.SIGNAL_FULL_VOLUME (0.20) and
    # radio.STATIC_SIGNAL_THRESHOLD (0.12) directly, so a signal has to sit
    # below the lower of the two (STATIC_SIGNAL_THRESHOLD) to prove both
    # the bed and the pickets in one pass.
    app, driving, _music, played_effects, _events = denver_driving
    station = _fringe_stream_station()
    deep_fringe_signal = STATIC_SIGNAL_THRESHOLD - 0.04
    reception = RadioReception(station, 90.0, deep_fringe_signal, "in range")
    driving.radio.enabled = True
    monkeypatch.setattr(driving.radio, "current_station", lambda: station)
    monkeypatch.setattr(driving.radio, "current_reception", lambda: reception)
    monkeypatch.setattr(driving.ctx.audio, "music_playing", lambda: True)
    streams = []
    monkeypatch.setattr(
        driving.ctx.audio, "play_radio_stream", lambda url, fade_ms=1500: streams.append(url)
    )
    loops = []
    monkeypatch.setattr(
        driving.ctx.audio,
        "start_loop",
        lambda ch, key, volume=1.0, fade_ms=300: loops.append((ch, key, volume)),
    )
    applied = []
    monkeypatch.setattr(driving.ctx.audio, "set_volumes", lambda **kw: applied.append(kw))

    driving._radio_signal_timer = 0.0
    driving._update_radio_reception(1.0)
    assert streams == []  # audible stream is left alone
    assert driving._radio_fringe_signal == pytest.approx(deep_fringe_signal)

    driving.truck.velocity_mps = 25.0
    driving._picket_wait_s = 0.0
    driving._update_radio_fringe(0.016)

    assert loops and loops[-1][1] == "radio/fm_hiss_loop" and loops[-1][2] > 0.0
    assert any(key.startswith("radio/picket") for key, _v in played_effects)
    assert driving._radio_picket_duck < 1.0  # capture lost: program near-silent
    assert driving._picket_wait_s > 0.0  # next picket is scheduled, never metronomic

    # the splash releases sharply once its window passes
    driving._picket_wait_s = 10.0
    driving._update_radio_fringe(0.5)
    assert driving._radio_picket_duck == 1.0


def test_clean_program_at_the_new_full_volume_join_has_no_fringe(denver_driving, monkeypatch):
    # The smear ruling (2026-07-24): static never sits on top of a still-
    # loud program. signal_volume_factor plays clean program at full
    # volume from SIGNAL_FULL_VOLUME (0.20) up; the fringe renderer must
    # agree exactly, or the game would lay hiss and pickets over a clean
    # signal -- audible proof that FRINGE_BED_SIGNAL/PICKET_SIGNAL track
    # radio.SIGNAL_FULL_VOLUME/STATIC_SIGNAL_THRESHOLD instead of a stale
    # hardcoded copy.
    app, driving, _music, played_effects, _events = denver_driving
    station = _fringe_stream_station()
    reception = RadioReception(station, 20.0, SIGNAL_FULL_VOLUME, "in range")
    driving.radio.enabled = True
    monkeypatch.setattr(driving.radio, "current_station", lambda: station)
    monkeypatch.setattr(driving.radio, "current_reception", lambda: reception)
    monkeypatch.setattr(driving.ctx.audio, "music_playing", lambda: True)
    loops = []
    monkeypatch.setattr(
        driving.ctx.audio,
        "start_loop",
        lambda ch, key, volume=1.0, fade_ms=300: loops.append((ch, key, volume)),
    )

    driving._radio_signal_timer = 0.0
    driving._update_radio_reception(1.0)
    assert driving._radio_fringe_signal == pytest.approx(SIGNAL_FULL_VOLUME)

    driving.truck.velocity_mps = 25.0
    driving._picket_wait_s = 0.0
    driving._update_radio_fringe(0.016)

    assert loops == []  # no hiss bed at full quieting
    assert not any(key.startswith("radio/picket") for key, _v in played_effects)
    assert driving._radio_picket_duck == 1.0  # never ducked: nothing to duck for


def test_strong_signal_and_dead_stream_render_no_fringe(denver_driving, monkeypatch):
    app, driving, _music, played_effects, _events = denver_driving
    station = _fringe_stream_station()
    driving.radio.enabled = True
    monkeypatch.setattr(driving.radio, "current_station", lambda: station)
    loops = []
    monkeypatch.setattr(
        driving.ctx.audio,
        "start_loop",
        lambda ch, key, volume=1.0, fade_ms=300: loops.append((ch, key, volume)),
    )
    # strong signal: no bed, no pickets
    monkeypatch.setattr(
        driving.radio, "current_reception", lambda: RadioReception(station, 5.0, 0.95, "in range")
    )
    monkeypatch.setattr(driving.ctx.audio, "music_playing", lambda: True)
    driving._radio_signal_timer = 0.0
    driving._update_radio_reception(1.0)
    driving._update_radio_fringe(0.016)
    assert loops == []
    # dead stream: fringe stays silent too (no ghost hiss over a dead radio)
    monkeypatch.setattr(driving.ctx.audio, "music_playing", lambda: False)
    driving._radio_fringe_signal = 0.2
    driving._update_radio_fringe(0.016)
    assert loops == []
    assert not any(key.startswith("radio/picket") for key, _v in played_effects)


def test_how_to_play_documents_the_radio_page():
    from freight_fate.states.main_menu import HELP_PAGES

    titles = [title for title, _lines in HELP_PAGES]
    assert "The in-cab radio" in titles
    help_text = " ".join(line for _title, lines in HELP_PAGES for line in lines).lower()
    assert "receivable stations" in help_text
    assert "streamer-safe status" in help_text
    assert "host breaks in between songs" in help_text
    assert "regional stations cover markets across the map" in help_text
    assert "static crackle at the fringe" in help_text
    assert "falls" in help_text and "back to the roadhouse" in help_text
