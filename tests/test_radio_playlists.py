"""Personal M3U playlist stations and the radio dial's category jump.

The Playlists folder next to the saves turns each dropped M3U file into a
station of the player's own music; Ctrl with a bracket key leaps the dial a
whole category at a time, so the AFN block never again stands between the
player and the terrestrial section.
"""

from pathlib import Path

from freight_fate.radio import (
    DEFAULT_RADIO_CATALOG,
    PERSONAL_PLAYLIST_SOURCE_TYPE,
    RadioPlaybackError,
    RadioState,
    RadioStation,
    _dial_group,
    _parse_m3u,
    load_personal_playlists,
)

# -- the M3U parser ----------------------------------------------------------


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_m3u_resolves_paths_and_reads_title(tmp_path):
    m3u = _write(
        tmp_path / "road.m3u",
        "\n".join(
            [
                "#EXTM3U",
                "#PLAYLIST: Norm's Road Mix",
                "#EXTINF:245,Artist - Song",
                "songs/first.mp3",
                "",
                r"C:\music\second.flac",
                "https://example.com/stream.mp3",
                "# a comment",
                "third.opus",
            ]
        ),
    )
    files, title = _parse_m3u(m3u)
    assert title == "Norm's Road Mix"
    assert files == (
        str(tmp_path / "songs" / "first.mp3"),
        r"C:\music\second.flac",
        str(tmp_path / "third.opus"),
    )


def test_parse_m3u_survives_a_missing_file(tmp_path):
    assert _parse_m3u(tmp_path / "gone.m3u") == ((), "")


# -- the folder loader -------------------------------------------------------


def test_load_personal_playlists_builds_stations(tmp_path):
    _write(tmp_path / "b-mix.m3u", "#PLAYLIST:Night Drive\none.mp3\n")
    _write(tmp_path / "a-mix.m3u", "two.mp3\nthree.mp3\n")
    _write(tmp_path / "empty.m3u", "#EXTM3U\n")
    stations = load_personal_playlists(tmp_path)
    assert [s.name for s in stations] == ["a-mix", "Night Drive"]
    for station in stations:
        assert station.source_type == PERSONAL_PLAYLIST_SOURCE_TYPE
        assert station.always_available
        assert not station.safe_for_streaming
        assert station.playlist_files
        assert station.display_name.startswith("Playlist, ")
    assert stations[0].id != stations[1].id


def test_load_personal_playlists_creates_the_folder(tmp_path):
    target = tmp_path / "Playlists"
    assert not target.exists()
    assert load_personal_playlists(target) == ()
    assert target.is_dir(), "an empty folder invites dropping files in"


def test_same_titles_get_distinct_station_ids(tmp_path):
    _write(tmp_path / "one.m3u", "#PLAYLIST:Mix\na.mp3\n")
    _write(tmp_path / "two.m3u", "#PLAYLIST:Mix\nb.mp3\n")
    ids = [s.id for s in load_personal_playlists(tmp_path)]
    assert len(ids) == len(set(ids)) == 2


# -- the streamer-safe gate --------------------------------------------------


def _playlist_station(files=("a.mp3",)) -> RadioStation:
    return RadioStation(
        id="playlist-test",
        name="Test Mix",
        call_sign="Playlist",
        format="personal playlist",
        source="your playlist file test.m3u",
        source_type=PERSONAL_PLAYLIST_SOURCE_TYPE,
        safe_for_streaming=False,
        always_available=True,
        playlist_files=tuple(files),
    )


def test_personal_playlists_ride_the_streamer_safe_gate():
    catalog = DEFAULT_RADIO_CATALOG + (_playlist_station(),)
    safe = RadioState(catalog=catalog, streamer_safe=True)
    assert "playlist-test" not in [s.id for s in safe.available_stations()]
    # Streamer-safe off is enough on its own: personal files need no internet,
    # so the real-streams switch does not gate them.
    open_dial = RadioState(catalog=catalog, streamer_safe=False, real_streams_enabled=False)
    assert "playlist-test" in [s.id for s in open_dial.available_stations()]


def test_playlists_sit_between_built_in_and_terrestrial_on_the_dial():
    catalog = DEFAULT_RADIO_CATALOG + (_playlist_station(),)
    state = RadioState(
        catalog=catalog,
        streamer_safe=False,
        real_streams_enabled=True,
        position=(33.45, -112.07),  # Phoenix: terrestrial in range
    )
    groups = [_dial_group(r.station) for r in state.receivable_stations()]
    assert groups == sorted(groups), "dial order is category order"
    assert 2 in groups, "the personal playlist is on the dial"
    assert groups.index(2) > groups.index(1)
    assert groups.index(2) < groups.index(3)


# -- the category jump -------------------------------------------------------


def test_tune_category_leaps_and_speaks_the_category():
    state = RadioState(
        catalog=DEFAULT_RADIO_CATALOG,
        streamer_safe=False,
        real_streams_enabled=True,
        position=(33.45, -112.07),
    )
    action = state.tune_category(1)
    assert action.message.startswith("Freight Fate stations. Tuned to ")
    action = state.tune_category(1)
    assert action.message.startswith("Terrestrial. Tuned to ")
    # And back down the same rung.
    action = state.tune_category(-1)
    assert action.message.startswith("Freight Fate stations. Tuned to ")


def test_tune_category_wraps_and_never_lands_mid_category():
    state = RadioState(catalog=DEFAULT_RADIO_CATALOG)  # streamer-safe defaults
    receptions = state.receivable_stations()
    first_by_group = {}
    for reception in receptions:
        first_by_group.setdefault(_dial_group(reception.station), reception.station.id)
    seen = []
    for _ in range(len(first_by_group)):
        action = state.tune_category(1)
        seen.append(action.station.id)
    # One full lap visits each category's first station exactly once.
    assert sorted(seen) == sorted(first_by_group.values())


# -- playback: skip the unreadable, remember the place -----------------------


def _driving_state(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Playlists", current_city="Buffalo")
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


def test_playlist_playback_skips_dead_files_and_advances(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving_state(app)
        station = _playlist_station(files=("dead.mp3", "one.mp3", "two.mp3"))
        played = []

        def fake_play(path, fade_ms=1200):
            if "dead" in path:
                raise RuntimeError("unreadable")
            played.append(path)

        monkeypatch.setattr(app.ctx.audio, "play_music_file", fake_play)

        driving._start_playlist_station(station)
        assert played == ["one.mp3"], "the dead file is skipped, not fatal"
        assert driving._playlist_positions[station.id] == 1

        driving._start_playlist_station(station, advance=True)
        assert played[-1] == "two.mp3"
        # Advancing past the end wraps and skips the dead file again.
        driving._start_playlist_station(station, advance=True)
        assert played[-1] == "one.mp3"
    finally:
        app.shutdown()


def test_playlist_with_nothing_playable_raises_for_fallback(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving_state(app)
        station = _playlist_station(files=("dead1.mp3", "dead2.mp3"))

        def fake_play(path, fade_ms=1200):
            raise RuntimeError("unreadable")

        monkeypatch.setattr(app.ctx.audio, "play_music_file", fake_play)
        try:
            driving._start_playlist_station(station)
            raise AssertionError("expected RadioPlaybackError")
        except RadioPlaybackError:
            pass
    finally:
        app.shutdown()


def test_update_advances_when_the_file_ends(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving_state(app)
        station = _playlist_station(files=("one.mp3", "two.mp3"))
        played = []
        monkeypatch.setattr(
            app.ctx.audio, "play_music_file", lambda path, fade_ms=1200: played.append(path)
        )
        monkeypatch.setattr(app.ctx.audio, "music_playing", lambda: False)

        driving._start_playlist_station(station)
        assert played == ["one.mp3"]
        # Inside the grace window nothing advances even though the channel
        # reads idle -- a fade-in must not be mistaken for a finished song.
        driving._update_playlist_playback(station, dt=0.5)
        assert played == ["one.mp3"]
        driving._update_playlist_playback(station, dt=2.0)
        driving._update_playlist_playback(station, dt=0.1)
        assert played[-1] == "two.mp3"
    finally:
        app.shutdown()
