import pytest

from freight_fate import radio_content
from freight_fate.music import MusicTrack
from freight_fate.radio import RadioStation


def test_content_duration_falls_back_to_music_catalog():
    # host_roadhouse_01 lives in music.py's host tables today
    assert radio_content.content_duration_s("host_roadhouse_01") > 0
    assert radio_content.content_duration_s("no_such_key") == 60.0


def test_station_ads_filters_by_format_tag(monkeypatch):
    spots = (
        MusicTrack("ad_test_tires", "Tire ad", "test", 22.0),
        MusicTrack("ad_test_diner", "Diner ad", "test", 25.0),
    )
    monkeypatch.setattr(radio_content, "AD_SPOTS", spots)
    monkeypatch.setattr(
        radio_content,
        "AD_FORMAT_TAGS",
        {"ad_test_tires": ("country",), "ad_test_diner": ("country", "blues")},
    )
    assert [t.key for t in radio_content.station_ads("blues")] == ["ad_test_diner"]
    assert len(radio_content.station_ads("country")) == 2
    assert radio_content.station_ads("jazz") == ()


def _patched_pools(monkeypatch):
    hosts = tuple(MusicTrack(f"host_x_{i:02d}", f"h{i}", "", 5.0) for i in range(1, 9))
    ids = tuple(MusicTrack(f"id_x_{i:02d}", f"i{i}", "", 10.0) for i in range(1, 4))
    ads = tuple(MusicTrack(f"ad_y_{i:02d}", f"a{i}", "", 25.0) for i in range(1, 5))
    monkeypatch.setattr("freight_fate.music.STATION_HOST_SEGMENTS", {"x": hosts}, raising=False)
    monkeypatch.setattr(radio_content, "STATION_IDS", {"x": ids})
    monkeypatch.setattr(radio_content, "AD_SPOTS", ads)
    monkeypatch.setattr(radio_content, "AD_FORMAT_TAGS", {t.key: ("country",) for t in ads})


def test_break_pattern_cycles_and_is_deterministic(monkeypatch):
    _patched_pools(monkeypatch)
    kinds = []
    for i in range(8):
        first = radio_content.plan_break("x", "country", "seed", i)
        assert first == radio_content.plan_break("x", "country", "seed", i)
        kinds.append(first)
    # pattern: host, id, host, ad_id, repeated
    assert kinds[0][0].startswith("host_")
    assert kinds[1][0].startswith("id_")
    assert kinds[3][0].startswith("ad_") and kinds[3][1].startswith("id_")
    assert kinds[4] == kinds[0] or kinds[4][0].startswith("host_")


def test_break_slots_degrade_when_pools_missing(monkeypatch):
    _patched_pools(monkeypatch)
    monkeypatch.setattr(radio_content, "STATION_IDS", {})
    monkeypatch.setattr(radio_content, "AD_SPOTS", ())
    # id and ad slots fall back to a host break; still never empty for a
    # station that has a host
    for i in range(4):
        elems = radio_content.plan_break("x", "country", "seed", i)
        assert elems and elems[0].startswith("host_")
    # and a station with no host at all gets no break
    assert radio_content.plan_break("", "country", "seed", 0) == ()


def _drive_job():
    from freight_fate.models.jobs import CARGO_CATALOG, Job

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
def break_driving(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    played = []
    monkeypatch.setattr(
        app.ctx.audio, "play_music", lambda track, fade_ms=1500: played.append(track)
    )
    app.ctx.profile = Profile(name="Break Slots", current_city="Denver")
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, _drive_job(), route, trip_seed=42, start_hour=13.0)
    app.push_state(driving)
    try:
        yield app, driving, played
    finally:
        app.shutdown()


def _play_next(driving, played):
    dt = radio_content.content_duration_s(played[-1]) + 0.1
    driving._update_radio_playback(False, dt)


def test_break_queue_delivers_host_id_ad_slots_in_order(break_driving, monkeypatch):
    _patched_pools(monkeypatch)
    app, driving, played = break_driving
    station = RadioStation(
        "brk-fixture",
        "Fixture",
        "KFX",
        "country",
        "test fixture",
        playlist="country",
        host="x",
    )
    driving.radio.catalog = driving.radio.catalog + (station,)
    driving.radio.select_station("brk-fixture", driving._radio_backend)
    assert played[-1].startswith("radio_country_")

    _play_next(driving, played)  # song 2
    assert played[-1].startswith("radio_country_")
    _play_next(driving, played)  # after 2 songs: a host break
    assert played[-1].startswith("host_x_")

    _play_next(driving, played)  # break ends, music resumes (song 3)
    assert played[-1].startswith("radio_country_")
    _play_next(driving, played)  # song 4
    assert played[-1].startswith("radio_country_")
    _play_next(driving, played)  # after 4 songs: an id break
    assert played[-1].startswith("id_x_")

    _play_next(driving, played)  # resumes (song 5)
    _play_next(driving, played)  # song 6
    _play_next(driving, played)  # after 6 songs: host again (pattern cycles)
    assert played[-1].startswith("host_x_")

    _play_next(driving, played)  # resumes (song 7)
    _play_next(driving, played)  # song 8
    _play_next(driving, played)  # after 8 songs: an ad plays
    assert played[-1].startswith("ad_y_")
    _play_next(driving, played)  # ...followed by an id
    assert played[-1].startswith("id_x_")
    _play_next(driving, played)  # then music resumes
    assert played[-1].startswith("radio_country_")


def test_no_host_station_chains_songs_without_break(break_driving):
    app, driving, played = break_driving
    station = RadioStation(
        "brk-nohost", "Fixture", "KFX", "country", "test fixture", playlist="country"
    )
    driving.radio.catalog = driving.radio.catalog + (station,)
    driving.radio.select_station("brk-nohost", driving._radio_backend)
    assert played[-1].startswith("radio_country_")

    for _ in range(6):
        _play_next(driving, played)
        assert played[-1].startswith("radio_country_")
    assert driving._radio_break_queue == ()
