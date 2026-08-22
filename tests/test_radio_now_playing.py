"""What the station says it is playing: read off the stream, spoken on a key,
shown on the Tab radio screen, and carried on the drivers board line.

Owner, 2026-08-22: "add stream metadata, e.g. artist and title currently
playing, to a key in-game to get it and add it to the station line in the
online profile." Icecast and Shoutcast streams publish that as ICY metadata
(``StreamTitle='Artist - Title';``); BASS exposes the latest block as a tag
on the channel, and that is the only source -- nothing here fetches anything.
"""

import pytest
from speech_capture import speech_stub

from freight_fate.audio import AudioEngine, parse_icy_stream_title
from freight_fate.models.jobs import CARGO_CATALOG, Job


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"StreamTitle='Usher - U Remind Me';StreamUrl='';", "Usher - U Remind Me"),
        ("StreamTitle='Darren Duff radio';", "Darren Duff radio"),
        # UTF-8 from a modern Icecast mount.
        ("StreamTitle='Beyoncé - Halo';".encode(), "Beyoncé - Halo"),
        # Latin-1 from an older Shoutcast one: not valid UTF-8, still a title.
        (b"StreamTitle='Caf\xe9 del Mar';", "Café del Mar"),
        # Whitespace runs inside a title collapse; surrounding space goes.
        (b"StreamTitle='  Artist   -   Title  ';", "Artist - Title"),
        # An empty block between songs is "no information", not "".
        (b"StreamTitle='';StreamUrl='';", None),
        (b"StreamUrl='http://x';", None),
        (b"", None),
        (None, None),
    ],
)
def test_icy_stream_title_parsing(raw, expected):
    assert parse_icy_stream_title(raw) == expected


def test_the_audio_facade_answers_none_when_the_backend_cannot_know():
    engine = AudioEngine.__new__(AudioEngine)

    class Impl:
        pass

    engine._impl = Impl()
    assert engine.radio_now_playing() is None


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
def streaming_driving(monkeypatch):
    """A Denver drive with the engine on, tuned to a real web stream, and
    the audio layer reporting whatever the test puts in ``title``."""
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    spoken = []
    title = {"value": "Usher - U Remind Me", "playing": True}
    monkeypatch.setattr(app.ctx.audio, "play_music", lambda track, fade_ms=1500: None)
    monkeypatch.setattr(app.ctx.audio, "stop_music", lambda fade_ms=0: None)
    monkeypatch.setattr(app.ctx.audio, "play_radio_stream", lambda url, fade_ms=1500: None)
    monkeypatch.setattr(app.ctx.audio, "music_playing", lambda: title["playing"])
    monkeypatch.setattr(app.ctx.audio, "radio_now_playing", lambda: title["value"])
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    app.ctx.profile = Profile(name="Now Playing", current_city="Denver")
    app.ctx.settings.radio_streamer_safe = False
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, _drive_job(), route, trip_seed=777, start_hour=13.0)
    app.push_state(driving)
    driving.truck.start_engine()
    driving.radio.enabled = True
    action = driving.radio.select_station("darren-duff-radio", driving._radio_backend)
    assert action.station.id == "darren-duff-radio", action.message
    try:
        yield app, driving, spoken, title
    finally:
        app.shutdown()


def test_shift_y_speaks_the_song_the_station_reports(streaming_driving):
    import pygame
    from driving_feature_helpers import key_event

    _app, driving, spoken, _title = streaming_driving
    event = key_event(pygame.K_y)
    event.mod = pygame.KMOD_SHIFT
    driving.handle_event(event)
    assert spoken[-1] == "Now playing on Darren Duff radio: Usher - U Remind Me."


def test_plain_y_still_speaks_the_radio_status(streaming_driving):
    import pygame
    from driving_feature_helpers import key_event

    _app, driving, spoken, _title = streaming_driving
    event = key_event(pygame.K_y)
    event.mod = 0
    driving.handle_event(event)
    assert spoken[-1] == driving.radio.status_text()


def test_a_station_without_song_information_says_so(streaming_driving):
    _app, driving, _spoken, title = streaming_driving
    title["value"] = None
    assert (
        driving._radio_now_playing_text()
        == "Darren Duff radio is not sending song information right now."
    )


def test_a_connecting_stream_says_nothing_is_playing_yet(streaming_driving):
    _app, driving, _spoken, title = streaming_driving
    title["playing"] = False
    assert (
        driving._radio_now_playing_text()
        == "Darren Duff radio is still connecting; nothing is playing yet."
    )


def test_a_freight_fate_station_does_not_pretend_to_have_song_information(streaming_driving):
    from freight_fate.radio import SAFE_ROUTE_PLAYLIST

    _app, driving, _spoken, _title = streaming_driving
    driving.radio.select_station(SAFE_ROUTE_PLAYLIST, driving._radio_backend)
    text = driving._radio_now_playing_text()
    assert text.endswith("does not send song information.")


def test_the_drivers_board_line_carries_the_song(streaming_driving):
    _app, driving, _spoken, title = streaming_driving
    # The board reads the reception tick's copy, so tick once.
    driving._radio_signal_timer = 0.0
    driving._update_radio_reception(0.0)
    detail = driving.online_presence().detail
    assert "listening to Darren Duff radio: Usher - U Remind Me" in detail
    # And drops it the moment the station stops saying.
    title["value"] = None
    driving._radio_signal_timer = 0.0
    driving._update_radio_reception(0.0)
    detail = driving.online_presence().detail
    assert detail.endswith("listening to Darren Duff radio")


def test_the_tab_radio_screen_has_a_now_playing_line(streaming_driving):
    from freight_fate.states.driving_menu_states import DrivingStatusScreenState

    app, driving, _spoken, _title = streaming_driving
    screen = DrivingStatusScreenState(app.ctx, driving, "radio")
    lines = screen._radio_lines()
    assert "Now playing on Darren Duff radio: Usher - U Remind Me." in lines


def test_a_slow_station_gets_a_second_connect_before_it_is_written_off():
    """Owner, 2026-08-22: Darren Duff radio was being written off as a dead
    stream while it was still coming. One refusal now buys a fresh connect
    and a spoken "trying again"; the second refusal is the handover."""
    from freight_fate.radio import RadioPlaybackError, RadioState

    class SlowBackend:
        def __init__(self):
            self.calls = 0

        def play_station(self, station, volume):
            self.calls += 1
            if self.calls == 1:
                raise RadioPlaybackError("slow")

        def stop_radio(self):
            pass

    radio = RadioState(enabled=True, station_id="darren-duff-radio", streamer_safe=False)
    backend = SlowBackend()
    action = radio.play(backend)
    assert action.retried is True
    assert action.fallback_used is False
    assert action.station.id == "darren-duff-radio"
    assert action.message == "Darren Duff radio is slow to answer. Trying again."
    assert backend.calls == 2
    assert "darren-duff-radio" not in radio.unplayable_ids
    # Still on the dial, still the tuned station.
    assert radio.station_id == "darren-duff-radio"

    # A second refusal on a later tick is the end of it for this session.
    class DeadBackend(SlowBackend):
        def play_station(self, station, volume):
            self.calls += 1
            if station.id == "darren-duff-radio":
                raise RadioPlaybackError("dead")

    action = radio.play(DeadBackend())
    assert action.fallback_used is True
    assert "darren-duff-radio" in radio.unplayable_ids
