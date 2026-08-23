import pytest
from asset_helpers import needs_audio_assets

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


STATION = "brk-fixture"
HOST_COUNT = 8
ID_COUNT = 3
AD_COUNT = 4


def _patched_pools(monkeypatch):
    hosts = tuple(MusicTrack(f"host_x_{i:02d}", f"h{i}", "", 5.0) for i in range(1, HOST_COUNT + 1))
    ids = tuple(MusicTrack(f"id_x_{i:02d}", f"i{i}", "", 10.0) for i in range(1, ID_COUNT + 1))
    ads = tuple(MusicTrack(f"ad_y_{i:02d}", f"a{i}", "", 25.0) for i in range(1, AD_COUNT + 1))
    monkeypatch.setattr("freight_fate.music.STATION_HOST_SEGMENTS", {"x": hosts}, raising=False)
    monkeypatch.setattr(radio_content, "STATION_IDS", {STATION: ids})
    monkeypatch.setattr(radio_content, "AD_SPOTS", ads)
    monkeypatch.setattr(radio_content, "AD_FORMAT_TAGS", {t.key: ("country",) for t in ads})


def _breaks(count, station=STATION, host="x"):
    return [radio_content.plan_break(station, host, "country", "seed", i) for i in range(count)]


def test_break_pattern_cycles_and_is_deterministic(monkeypatch):
    _patched_pools(monkeypatch)
    kinds = _breaks(8)
    for i, planned in enumerate(kinds):
        assert planned == radio_content.plan_break(STATION, "x", "country", "seed", i)
    # pattern: host, id, host, ad_id, repeated
    for pos in (0, 2, 4, 6):
        assert kinds[pos][0].startswith("host_"), pos
    for pos in (1, 5):
        assert kinds[pos][0].startswith("id_"), pos
    for pos in (3, 7):
        assert kinds[pos][0].startswith("ad_") and kinds[pos][1].startswith("id_"), pos


def test_every_pool_entry_is_reachable_across_breaks(monkeypatch):
    """No segment is stranded: each pool advances on its own count.

    Host slots land twice per four-break cycle, ID slots up to twice (own
    slot plus the tag chasing an ad), ads once -- so four cycles is enough
    for the 8/3/4 fixture pools to be heard out in full.
    """
    _patched_pools(monkeypatch)
    planned = _breaks(4 * len(radio_content.BREAK_PATTERN))
    keys = [key for elems in planned for key in elems]
    assert len({k for k in keys if k.startswith("host_")}) == HOST_COUNT
    assert len({k for k in keys if k.startswith("id_")}) == ID_COUNT
    assert len({k for k in keys if k.startswith("ad_")}) == AD_COUNT


def test_break_slots_degrade_when_pools_missing(monkeypatch):
    _patched_pools(monkeypatch)
    monkeypatch.setattr(radio_content, "STATION_IDS", {})
    monkeypatch.setattr(radio_content, "AD_SPOTS", ())
    # id and ad slots fall back to a host break; still never empty for a
    # station that has a host
    planned = _breaks(4 * len(radio_content.BREAK_PATTERN))
    assert all(len(elems) == 1 and elems[0].startswith("host_") for elems in planned)
    # a degraded station still cycles its whole host pool
    assert len({elems[0] for elems in planned}) == HOST_COUNT
    # and a station with no host at all gets no break
    assert radio_content.plan_break(STATION, "", "country", "seed", 0) == ()


def test_ids_are_keyed_by_station_not_host(monkeypatch):
    """Two stations sharing a host still speak their own call signs."""
    _patched_pools(monkeypatch)
    other = (MusicTrack("id_other_01", "o1", "", 10.0),)
    monkeypatch.setattr(
        radio_content,
        "STATION_IDS",
        dict(radio_content.STATION_IDS) | {"brk-other": other},
    )
    assert radio_content.plan_break("brk-other", "x", "country", "seed", 1) == ("id_other_01",)
    assert radio_content.plan_break("nope", "x", "country", "seed", 1)[0].startswith("host_")


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
        app.ctx.audio,
        "play_music",
        lambda track, fade_ms=1500: played.append((track, fade_ms)),
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
    dt = radio_content.content_duration_s(played[-1][0]) + 0.1
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
    assert played[-1][0].startswith("radio_country_")

    _play_next(driving, played)  # song 2
    assert played[-1][0].startswith("radio_country_")
    _play_next(driving, played)  # after 2 songs: a host break
    assert played[-1][0].startswith("host_x_")
    assert played[-1][1] == 600  # fade into a break

    _play_next(driving, played)  # break ends, music resumes (song 3)
    assert played[-1][0].startswith("radio_country_")
    assert played[-1][1] == 1200  # fade back to music
    _play_next(driving, played)  # song 4
    assert played[-1][0].startswith("radio_country_")
    _play_next(driving, played)  # after 4 songs: an id break
    assert played[-1][0].startswith("id_x_")
    assert played[-1][1] == 600  # fade into a break

    _play_next(driving, played)  # resumes (song 5)
    assert played[-1][1] == 1200  # fade back to music
    _play_next(driving, played)  # song 6
    _play_next(driving, played)  # after 6 songs: host again (pattern cycles)
    assert played[-1][0].startswith("host_x_")
    assert played[-1][1] == 600  # fade into a break

    _play_next(driving, played)  # resumes (song 7)
    assert played[-1][1] == 1200  # fade back to music
    _play_next(driving, played)  # song 8
    _play_next(driving, played)  # after 8 songs: an ad plays
    assert played[-1][0].startswith("ad_y_")
    assert played[-1][1] == 600  # fade into a break
    _play_next(driving, played)  # ...followed by an id
    assert played[-1][0].startswith("id_x_")
    assert played[-1][1] == 300  # fade between break elements
    _play_next(driving, played)  # then music resumes
    assert played[-1][0].startswith("radio_country_")
    assert played[-1][1] == 1200  # fade back to music


def test_no_host_station_chains_songs_without_break(break_driving):
    app, driving, played = break_driving
    station = RadioStation(
        "brk-nohost", "Fixture", "KFX", "country", "test fixture", playlist="country"
    )
    driving.radio.catalog = driving.radio.catalog + (station,)
    driving.radio.select_station("brk-nohost", driving._radio_backend)
    assert played[-1][0].startswith("radio_country_")

    for _ in range(6):
        _play_next(driving, played)
        assert played[-1][0].startswith("radio_country_")
    assert driving._radio_break_queue == ()


@needs_audio_assets
def test_station_content_tables_resolve():
    import json
    from importlib import resources
    from pathlib import Path

    from asset_helpers import asset_exists

    from freight_fate import radio_content
    from freight_fate.music import STATION_HOST_SEGMENTS, STATION_PLAYLISTS

    catalog = json.loads(
        Path("src/freight_fate/data/radio_catalog.json").read_text(encoding="utf-8")
    )
    for row in catalog["stations"]:
        if row.get("playlist"):
            assert row["playlist"] in ("route",) or row["playlist"] in STATION_PLAYLISTS
        if row.get("host"):
            assert row["host"] in STATION_HOST_SEGMENTS, row["id"]
    keys = [t.key for pool in radio_content.STATION_IDS.values() for t in pool]
    keys += [t.key for t in radio_content.AD_SPOTS]
    assert len(keys) == len(set(keys))
    assert all(radio_content.content_duration_s(k) > 0 for k in keys)
    assert set(radio_content.AD_FORMAT_TAGS) <= {t.key for t in radio_content.AD_SPOTS}
    for tags in radio_content.AD_FORMAT_TAGS.values():
        assert all(tag in STATION_PLAYLISTS for tag in tags)

    # IDs are keyed by catalog station id, and every clip has to be on disk
    # (or in the shipped pack) or the break plays silence.
    station_ids = {row["id"] for row in catalog["stations"]}
    assert set(radio_content.STATION_IDS) <= station_ids
    sounds = resources.files("freight_fate.assets") / "sounds" / "music"
    for key in keys:
        assert asset_exists(sounds, key), key

    # An ad only ever runs with an ID chasing it back into music, so a
    # station whose playlist has tagged ads needs IDs of its own -- without
    # them the ad slot silently degrades to a host break and the ad never
    # plays anywhere.
    for row in catalog["stations"]:
        if not row.get("host") or not row.get("playlist"):
            continue
        if radio_content.station_ads(row["playlist"]):
            assert radio_content.STATION_IDS.get(row["id"]), row["id"]

    # Every registered host segment must resolve to its own duration; a pool
    # listed in STATION_HOST_SEGMENTS but missing from ALL_HOST_SEGMENTS
    # would fall through to the 60-second unknown-key guess, which the
    # playback loop hears as dead air.
    for pool in STATION_HOST_SEGMENTS.values():
        for segment in pool:
            assert radio_content.content_duration_s(segment.key) == segment.duration_s, segment.key
