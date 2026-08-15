"""Personal playlist stations and the radio dial's category jump.

The Playlists folder next to the saves turns each dropped playlist file into
a station of the player's own music -- and, since 2026-08-15, of the internet
stations a playlist lists alongside it; Ctrl with a bracket key leaps the dial
a whole category at a time, so the AFN block never again stands between the
player and the terrestrial section.
"""

import logging
from pathlib import Path

import pytest

from freight_fate.radio import (
    DEFAULT_RADIO_CATALOG,
    PERSONAL_PLAYLIST_SOURCE_TYPE,
    RadioPlaybackError,
    RadioState,
    RadioStation,
    _absolute_anywhere,
    _dial_group,
    _parse_m3u,
    _parse_playlist_file,
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
    entries, title = _parse_m3u(m3u)
    assert title == "Norm's Road Mix"
    # Files and streams keep the player's own order: a mixed playlist is a
    # sequence they chose, not two piles.
    assert entries == (
        str(tmp_path / "songs" / "first.mp3"),
        r"C:\music\second.flac",
        "https://example.com/stream.mp3",
        str(tmp_path / "third.opus"),
    )


def test_a_stream_only_m3u_still_builds_a_station(tmp_path):
    """The owner's bug: an internet-radio export is all URLs.

    Every entry was skipped as "internet radio belongs in the catalog", the
    playlist parsed to nothing, and the station silently never existed.
    """
    _write(
        tmp_path / "webmix.m3u",
        "#EXTM3U\n#EXTINF:-1,Some Station\nhttp://example.com/one\nhttps://example.com/two\n",
    )
    (station,) = load_personal_playlists(tmp_path)
    assert station.playlist_entries == ("http://example.com/one", "https://example.com/two")
    assert station.name == "webmix"


def test_parse_pls_reads_numbered_entries_in_order(tmp_path):
    pls = _write(
        tmp_path / "stations.pls",
        "\n".join(
            [
                "[playlist]",
                "NumberOfEntries=3",
                "File2=https://example.com/second",
                "Title2=Second",
                "File1=songs/first.mp3",
                "Title1=First",
                "File3=/music/third.flac",
                "Version=2",
            ]
        ),
    )
    entries, title = _parse_playlist_file(pls)
    assert entries == (
        str(tmp_path / "songs" / "first.mp3"),
        "https://example.com/second",
        str(Path("/music/third.flac")),
    )
    # Several entries means Title1 titles a track, not the playlist.
    assert title == ""


def test_a_one_station_pls_is_named_by_its_title(tmp_path):
    _write(
        tmp_path / "station.pls",
        "[playlist]\nFile1=http://example.com/live\nTitle1=Night Owl Radio\nLength1=-1\n",
    )
    (station,) = load_personal_playlists(tmp_path)
    assert station.name == "Night Owl Radio"
    assert station.playlist_entries == ("http://example.com/live",)


@pytest.mark.parametrize(
    "line, absolute",
    [
        ("songs/first.mp3", False),
        ("third.opus", False),
        ("../next door/track.mp3", False),
        ("/home/driver/music/song.mp3", True),
        (r"C:\music\second.flac", True),
        ("D:/media/third.flac", True),
        (r"\\media-box\share\fourth.mp3", True),
    ],
)
def test_playlist_entries_are_absolute_on_the_machine_that_wrote_them(line, absolute):
    """A Windows playlist read on Linux keeps its drive paths.

    ``Path.is_absolute`` answers for the host, so on Linux a ``C:\\...`` entry
    read as relative and got the playlist's own folder glued in front of it.
    That invented a path the player never had, and buried the real one when the
    track would not play. This has to hold identically on either platform,
    which is why it is asserted here and not through a tmp_path playlist.
    """
    assert _absolute_anywhere(line) is absolute


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
        assert station.playlist_entries
        assert station.display_name.startswith("Playlist, ")
    assert stations[0].id != stations[1].id


def test_an_unusable_playlist_warns_and_builds_no_station(tmp_path, caplog):
    """Silence was the whole diagnosis before: no station, no log, no word."""
    _write(tmp_path / "empty.m3u", "#EXTM3U\n# nothing but comments\n")
    _write(tmp_path / "good.m3u", "one.mp3\nhttps://example.com/live\n")
    with caplog.at_level(logging.INFO, logger="freight_fate.radio"):
        stations = load_personal_playlists(tmp_path)
    assert [s.name for s in stations] == ["good"]
    # getMessage(), not message % args: caplog's records have already been
    # through a handler, so ``message`` is the interpolated text and applying
    # the args a second time raises rather than reporting the real result.
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("empty.m3u" in text for text in warnings)
    info = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert any("good.m3u" in text and "1 files, 1 streams" in text for text in info)


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
        playlist_entries=tuple(files),
    )


def test_personal_playlists_ride_the_streamer_safe_gate():
    catalog = DEFAULT_RADIO_CATALOG + (_playlist_station(),)
    safe = RadioState(catalog=catalog, streamer_safe=True)
    assert "playlist-test" not in [s.id for s in safe.available_stations()]
    # Streamer-safe off is enough on its own: it is the one licensing gate.
    open_dial = RadioState(catalog=catalog, streamer_safe=False)
    assert "playlist-test" in [s.id for s in open_dial.available_stations()]


def test_a_refused_playlist_says_its_tracks_would_not_open():
    """ "Off the air" is a broadcast's failure, not a folder's."""

    class _RefusingBackend:
        def play_station(self, station, volume):
            if station.source_type == PERSONAL_PLAYLIST_SOURCE_TYPE:
                raise RadioPlaybackError("no playable entry in this playlist")

        def stop_radio(self):
            pass

    state = RadioState(catalog=DEFAULT_RADIO_CATALOG + (_playlist_station(),))
    action = state.select_station("playlist-test", _RefusingBackend())
    assert "None of the tracks in Playlist, Test Mix would open" in action.message
    assert "off the air" not in action.message
    assert action.fallback_used


def test_reloading_the_folder_puts_a_new_playlist_on_the_dial(tmp_path):
    """A playlist added mid-run used to need a whole new drive to be seen."""
    state = RadioState(catalog=DEFAULT_RADIO_CATALOG)
    state.mark_unplayable("playlist-late-mix")
    _write(tmp_path / "late-mix.m3u", "https://example.com/live\n")
    state.reload_personal_playlists(tmp_path)
    playlists = [s for s in state.catalog if s.source_type == PERSONAL_PLAYLIST_SOURCE_TYPE]
    assert [s.name for s in playlists] == ["late-mix"]
    # An earlier refusal must not keep the repaired playlist off the dial.
    assert "playlist-late-mix" not in state.unplayable_ids
    assert "playlist-late-mix" in [s.id for s in state.available_stations()]
    # Reloading twice does not stack duplicate stations.
    state.reload_personal_playlists(tmp_path)
    assert len([s for s in state.catalog if s.source_type == PERSONAL_PLAYLIST_SOURCE_TYPE]) == 1


def test_playlists_sit_between_built_in_and_terrestrial_on_the_dial():
    catalog = DEFAULT_RADIO_CATALOG + (_playlist_station(),)
    state = RadioState(
        catalog=catalog,
        streamer_safe=False,
        position=(33.45, -112.07),  # Phoenix: terrestrial in range
    )
    groups = [_dial_group(r.station) for r in state.receivable_stations()]
    assert groups == sorted(groups), "dial order is category order"
    assert 2 in groups, "the personal playlist is on the dial"
    assert groups.index(2) > groups.index(1)
    # Terrestrial moved to group 4 when Favorites took 3.
    assert groups.index(2) < groups.index(4)


# -- the category jump -------------------------------------------------------


def test_tune_category_leaps_and_speaks_the_category():
    state = RadioState(
        catalog=DEFAULT_RADIO_CATALOG,
        streamer_safe=False,
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
    state = RadioState(catalog=DEFAULT_RADIO_CATALOG)  # the out-of-the-box dial
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


def _fake_audio(app, monkeypatch, playing=False):
    """Record what the playlist layer asks the audio stack to play."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        app.ctx.audio,
        "play_music_file",
        lambda path, fade_ms=1200: calls.append(("file", path)),
    )
    monkeypatch.setattr(
        app.ctx.audio,
        "play_radio_stream",
        lambda url, fade_ms=1500: calls.append(("stream", url)),
    )
    monkeypatch.setattr(app.ctx.audio, "music_playing", lambda: playing)
    return calls


def test_a_stream_entry_tunes_a_stream_and_a_file_plays_from_disk(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving_state(app)
        station = _playlist_station(files=("https://example.com/live", "one.mp3"))
        calls = _fake_audio(app, monkeypatch)

        driving._start_playlist_station(station)
        assert calls == [("stream", "https://example.com/live")]
        driving._start_playlist_station(station, advance=True)
        assert calls[-1] == ("file", "one.mp3")
    finally:
        app.shutdown()


def test_a_connecting_stream_is_not_treated_as_a_finished_track(monkeypatch):
    """The whole reason a stream entry needs its own hold.

    play_radio_stream connects on a worker thread, so the music channel is
    silent for as long as the server takes to answer. Advancing on that
    silence would walk the whole playlist in a couple of frames.
    """
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving_state(app)
        station = _playlist_station(files=("https://example.com/live", "one.mp3"))
        calls = _fake_audio(app, monkeypatch)  # music_playing stays False

        driving._start_playlist_station(station)
        for _ in range(8):
            driving._update_playlist_playback(station, dt=1.0)
        assert calls == [("stream", "https://example.com/live")], "held while it connects"
    finally:
        app.shutdown()


def test_a_dead_stream_entry_is_skipped_like_an_unreadable_file(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving_state(app)
        station = _playlist_station(files=("https://example.com/dead", "one.mp3"))
        calls: list[tuple[str, str]] = []

        def fake_stream(url, fade_ms=1500):
            # audio.play_radio_stream reports a failed connect on the NEXT
            # call for the same URL, which is what the re-tune is for.
            if ("stream", url) in calls:
                raise RuntimeError("radio stream unavailable")
            calls.append(("stream", url))

        monkeypatch.setattr(app.ctx.audio, "play_radio_stream", fake_stream)
        monkeypatch.setattr(
            app.ctx.audio,
            "play_music_file",
            lambda path, fade_ms=1200: calls.append(("file", path)),
        )
        monkeypatch.setattr(app.ctx.audio, "music_playing", lambda: False)

        driving._start_playlist_station(station)
        for _ in range(4):
            driving._update_playlist_playback(station, dt=10.0)
        assert calls[-1] == ("file", "one.mp3"), "the dead stream is skipped, not fatal"
    finally:
        app.shutdown()


def test_a_playlist_that_never_plays_says_so_once(monkeypatch):
    """Nothing playing and nothing said was the accessibility bug itself."""
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving_state(app)
        station = _playlist_station(files=("https://example.com/one", "https://example.com/two"))
        _fake_audio(app, monkeypatch)  # every connect "succeeds", none ever plays
        spoken: list[str] = []
        monkeypatch.setattr(
            app.ctx, "say_event", lambda text, **kw: spoken.append(text), raising=False
        )

        driving._start_playlist_station(station)
        for _ in range(60):
            driving._update_playlist_playback(station, dt=10.0)
        assert len(spoken) == 1, "a broken folder explains itself once, not every retry"
        assert "would play" in spoken[0]
        assert "Playlists folder" in spoken[0]
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
