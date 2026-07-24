"""Transcript-backed keyboard proof for transparent runtime radio discovery."""

from __future__ import annotations

import threading
import time

import pygame
import pytest
from playtest_harness import PlaytestHarness, key_event

from freight_fate.radio import (
    DIRECTORY_INTERNET_ONLY_SOURCE_TYPE,
    DIRECTORY_SOURCE_TYPE,
    PERSONAL_PLAYLIST_SOURCE_TYPE,
    PUBLIC_DIRECTORY_SOURCE_TYPES,
    RadioStation,
    truck_position,
)
from freight_fate.radio_browser import DirectoryStation
from freight_fate.radio_discovery import ApproximateLocation, DiscoveryResult
from freight_fate.radio_url_safety import StreamProbe

UUID_ONE = "12345678-1234-1234-1234-123456789abc"
UUID_TWO = "22345678-1234-1234-1234-123456789abc"


def _station(
    uuid=UUID_ONE,
    name="KTEST Buffalo",
    distance=5.0,
    *,
    internet_only=False,
):
    return DirectoryStation(
        uuid=uuid,
        name=name,
        format="community; MP3, 128 kilobits",
        codec="MP3",
        bitrate=128,
        stream_url=f"https://{uuid[:8]}.example/live.mp3",
        lat=None if internet_only else 42.9,
        lon=None if internet_only else -78.8,
        distance_miles=None if internet_only else distance,
        state="New York",
        city="Buffalo",
        internet_only=internet_only,
    )


def _result(*stations, outcome="updated"):
    return DiscoveryResult(
        generation=1,
        key="real:player-location",
        explicit=False,
        stations=tuple(stations),
        location=ApproximateLocation(42.88, -78.87, "Buffalo", "New York", "NY"),
        outcome=outcome,
    )


class ManualDiscovery:
    def __init__(self):
        self.result = None
        self.requests = []
        self.clicks = []

    @property
    def busy(self):
        return False

    def request(self, **kwargs):
        self.requests.append(kwargs)
        return "started"

    def poll(self):
        result, self.result = self.result, None
        return result

    def cancel(self):
        pass

    def record_click(self, uuid):
        self.clicks.append(uuid)


class PreparedStream:
    def __init__(self, url):
        self.url = url
        self.discarded = False


def _start_radio_harness(
    monkeypatch,
    *,
    streamer_safe=False,
    backend_supported=True,
    origin="Buffalo",
    destination="Rochester",
):
    import freight_fate.states.driving as driving_module
    import freight_fate.states.driving_radio as radio_module

    managers = []

    def manager_factory():
        manager = ManualDiscovery()
        managers.append(manager)
        return manager

    monkeypatch.setattr(driving_module, "RadioDiscoveryManager", manager_factory)
    monkeypatch.setattr(
        radio_module,
        "probe_stream_url",
        lambda url, **kwargs: StreamProbe(url, "audio/mpeg"),
    )
    harness = PlaytestHarness(monkeypatch)
    harness.__enter__()
    harness.app.ctx.settings.online_services = True
    harness.app.ctx.settings.radio_streamer_safe = streamer_safe
    harness.app.ctx.settings.radio_enabled = True
    harness.app.ctx.settings.radio_discovery_location = "real"
    monkeypatch.setattr(
        harness.app.ctx.audio,
        "supports_radio_streams",
        lambda: backend_supported,
    )
    prepared = []
    played = []
    discarded = []

    def prepare(url):
        stream = PreparedStream(url)
        prepared.append(stream)
        return stream

    monkeypatch.setattr(harness.app.ctx.audio, "prepare_radio_stream", prepare)
    monkeypatch.setattr(
        harness.app.ctx.audio,
        "play_prepared_radio_stream",
        lambda stream, url, fade_ms=1500: played.append((stream, url)),
    )

    def discard(stream):
        stream.discarded = True
        discarded.append(stream)

    monkeypatch.setattr(harness.app.ctx.audio, "discard_radio_stream", discard)
    harness.start_route(origin, destination, profile_name="Radio Runtime")
    return harness, managers[-1], prepared, played, discarded


def _finish_pending(driving, timeout=2.0):
    deadline = time.monotonic() + timeout
    while driving._radio_pending_station_id and time.monotonic() < deadline:
        driving._poll_radio_tune()
        time.sleep(0.005)
    assert not driving._radio_pending_station_id


def _open_audio_settings_on_streamer_safe(harness):
    from freight_fate.states.main_menu import SettingsCategoryState

    menu = SettingsCategoryState(harness.app.ctx, "audio")
    harness.app.ctx.push_state(menu)
    while not menu.items[menu.index].text.startswith("Radio streamer-safe mode"):
        menu.handle_event(key_event(pygame.K_DOWN))
    return menu


def test_silent_discovery_joins_existing_bracket_dial_and_commits_after_success(
    monkeypatch,
):
    harness, manager, _prepared, played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        transcript_before = list(harness.result.transcript)
        current_before = driving.radio.station_id
        manager.result = _result(_station())
        driving._update_radio_discovery()

        assert harness.result.transcript == transcript_before
        assert driving.radio.station_id == current_before
        assert any(
            station.source_type == DIRECTORY_SOURCE_TYPE
            for station in driving.radio.available_stations()
        )

        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert "Tuned to" in harness.result.transcript[-1]
        playing_before = driving.radio.station_id
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert harness.result.transcript[-1] == "Tuning to KTEST Buffalo."
        assert driving.radio.station_id == playing_before
        harness.press_key(pygame.K_y, "y")
        assert "Tuning to KTEST Buffalo" in harness.result.transcript[-1]
        assert (
            f"{driving.radio.current_station().display_name} remains on"
            in (harness.result.transcript[-1])
        )

        _finish_pending(driving)
        assert driving.radio.station_id == f"radio-browser:{UUID_ONE}"
        assert played and played[-1][1].endswith("/live.mp3")
        assert harness.result.transcript[-1] == "Playing KTEST Buffalo."

        harness.press_key(pygame.K_LEFTBRACKET, "[")
        assert driving.radio.station_id == "ff-night-line"
        assert harness.result.transcript[-1].startswith("Tuned to")
    finally:
        harness.__exit__(None, None, None)


def test_internet_only_station_uses_same_bracket_dial_without_reception_claim(monkeypatch):
    harness, manager, _prepared, _played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        manager.result = _result(_station(name="Statewide Web", internet_only=True))
        driving._update_radio_discovery()
        station = driving.radio.station_by_id(f"radio-browser:{UUID_ONE}")
        assert station is not None
        assert station.source_type == DIRECTORY_INTERNET_ONLY_SOURCE_TYPE
        assert station.always_available is True

        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert harness.result.transcript[-1] == "Tuning to Statewide Web."
        _finish_pending(driving)
        harness.press_key(pygame.K_y, "y")
        status = harness.result.transcript[-1].lower()
        assert "internet-only station" in status
        assert "nearby" not in status
        assert "miles" not in status
        assert "signal" not in status
    finally:
        harness.__exit__(None, None, None)


def test_saved_discovered_station_resumes_through_normal_pending_tune(monkeypatch):
    harness, manager, _prepared, played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        saved_id = f"radio-browser:{UUID_ONE}"
        driving.radio.preferred_station_id = saved_id
        driving.ctx.settings.radio_station_id = saved_id
        current = driving.radio.station_id
        prepare_started = threading.Event()
        release_prepare = threading.Event()

        def delayed_prepare(url):
            prepare_started.set()
            assert release_prepare.wait(2)
            return PreparedStream(url)

        monkeypatch.setattr(
            driving.ctx.audio,
            "prepare_radio_stream",
            delayed_prepare,
        )

        manager.result = _result(_station())
        driving._update_radio_discovery()

        assert prepare_started.wait(1)
        assert driving.radio.station_id == current
        assert driving.radio.preferred_station_id == saved_id
        assert driving._radio_pending_station_id == saved_id
        assert harness.result.transcript[-1] == (
            "Restoring saved station. Tuning to KTEST Buffalo."
        )
        assert harness.result.spoken[-1].interrupt is False
        harness.press_key(pygame.K_y, "y")
        assert "Tuning to KTEST Buffalo" in harness.result.transcript[-1]
        release_prepare.set()
        _finish_pending(driving)
        assert driving.radio.station_id == saved_id
        assert played
        assert harness.result.transcript[-1] == "Playing KTEST Buffalo."
    finally:
        harness.__exit__(None, None, None)


def test_saved_discovered_station_resumes_when_it_first_appears_later(monkeypatch):
    harness, manager, _prepared, played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        saved_id = f"radio-browser:{UUID_ONE}"
        driving.radio.preferred_station_id = saved_id
        driving.ctx.settings.radio_station_id = saved_id

        manager.result = _result(outcome="empty")
        driving._update_radio_discovery()
        assert not driving._radio_pending_station_id

        release_prepare = threading.Event()

        def delayed_prepare(url):
            assert release_prepare.wait(2)
            return PreparedStream(url)

        monkeypatch.setattr(driving.ctx.audio, "prepare_radio_stream", delayed_prepare)
        manager.result = _result(_station())
        driving._update_radio_discovery()
        assert driving._radio_pending_station_id == saved_id
        assert harness.result.transcript[-1] == (
            "Restoring saved station. Tuning to KTEST Buffalo."
        )
        assert harness.result.spoken[-1].interrupt is False

        release_prepare.set()
        _finish_pending(driving)
        assert driving.radio.station_id == saved_id
        assert played

        transcript_count = len(harness.result.transcript)
        manager.result = _result(_station())
        driving._update_radio_discovery()
        assert len(harness.result.transcript) == transcript_count
        assert not driving._radio_pending_station_id
    finally:
        harness.__exit__(None, None, None)


def test_pending_station_survives_silent_geographic_refresh(monkeypatch):
    harness, manager, _prepared, played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        manager.result = _result(_station())
        driving._update_radio_discovery()
        harness.press_key(pygame.K_RIGHTBRACKET, "]")

        prepare_started = threading.Event()
        release_prepare = threading.Event()

        def delayed_prepare(url):
            prepare_started.set()
            assert release_prepare.wait(2)
            return PreparedStream(url)

        monkeypatch.setattr(driving.ctx.audio, "prepare_radio_stream", delayed_prepare)
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert prepare_started.wait(1)
        transcript_count = len(harness.result.transcript)

        manager.result = _result(outcome="empty")
        driving._update_radio_discovery()
        assert driving._radio_pending_station_id == f"radio-browser:{UUID_ONE}"
        assert driving.radio.station_by_id(f"radio-browser:{UUID_ONE}") is not None
        assert len(harness.result.transcript) == transcript_count

        release_prepare.set()
        _finish_pending(driving)
        assert driving.radio.station_id == f"radio-browser:{UUID_ONE}"
        assert played
    finally:
        harness.__exit__(None, None, None)


def test_late_saved_station_never_overrides_pending_bracket_choice(monkeypatch):
    harness, manager, _prepared, played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        saved_id = f"radio-browser:{UUID_ONE}"
        chosen_id = f"radio-browser:{UUID_TWO}"
        driving.radio.preferred_station_id = saved_id
        driving.ctx.settings.radio_station_id = saved_id
        manager.result = _result(_station(UUID_TWO, "Player Choice"))
        driving._update_radio_discovery()
        harness.press_key(pygame.K_RIGHTBRACKET, "]")

        prepare_started = threading.Event()
        release_prepare = threading.Event()

        def delayed_prepare(url):
            prepare_started.set()
            assert release_prepare.wait(2)
            return PreparedStream(url)

        monkeypatch.setattr(driving.ctx.audio, "prepare_radio_stream", delayed_prepare)
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert prepare_started.wait(1)
        assert driving._radio_pending_station_id == chosen_id
        transcript_count = len(harness.result.transcript)

        manager.result = _result(
            _station(UUID_ONE, "Saved Station", 2.0),
            _station(UUID_TWO, "Player Choice", 3.0),
        )
        driving._update_radio_discovery()
        assert driving._radio_pending_station_id == chosen_id
        assert len(harness.result.transcript) == transcript_count

        release_prepare.set()
        _finish_pending(driving)
        assert driving.radio.station_id == chosen_id
        assert driving.radio.preferred_station_id == chosen_id
        assert [url for _stream, url in played] == [f"https://{UUID_TWO[:8]}.example/live.mp3"]
    finally:
        harness.__exit__(None, None, None)


def test_gate_change_cancels_pending_tune_with_terminal_truth(monkeypatch):
    harness, manager, _prepared, played, discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        manager.result = _result(_station())
        driving._update_radio_discovery()
        harness.press_key(pygame.K_RIGHTBRACKET, "]")

        prepare_started = threading.Event()
        release_prepare = threading.Event()

        def delayed_prepare(url):
            prepare_started.set()
            assert release_prepare.wait(2)
            return PreparedStream(url)

        monkeypatch.setattr(driving.ctx.audio, "prepare_radio_stream", delayed_prepare)
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert prepare_started.wait(1)

        driving.ctx.settings.radio_streamer_safe = True
        current_name = driving.radio.current_station().display_name
        driving._update_radio_discovery()
        assert not driving._radio_pending_station_id
        assert harness.result.transcript[-1] == (
            f"Public station tuning canceled. {current_name} remains playing."
        )
        assert harness.result.spoken[-1].interrupt is False

        release_prepare.set()
        time.sleep(0.03)
        driving._poll_radio_tune()
        assert played == []
        assert all(stream.discarded for stream in discarded)
    finally:
        harness.__exit__(None, None, None)


def test_gate_change_falls_back_once_when_public_station_is_playing(monkeypatch):
    harness, manager, _prepared, played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        manager.result = _result(
            _station(UUID_ONE, "Playing Station", 2.0),
            _station(UUID_TWO, "Pending Station", 3.0),
        )
        driving._update_radio_discovery()
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        _finish_pending(driving)
        assert driving.radio.station_id == f"radio-browser:{UUID_ONE}"

        prepare_started = threading.Event()
        release_prepare = threading.Event()

        def delayed_prepare(url):
            prepare_started.set()
            assert release_prepare.wait(2)
            return PreparedStream(url)

        monkeypatch.setattr(driving.ctx.audio, "prepare_radio_stream", delayed_prepare)
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert prepare_started.wait(1)
        menu = _open_audio_settings_on_streamer_safe(harness)
        transcript_count = len(harness.result.transcript)

        menu.handle_event(key_event(pygame.K_RETURN))
        release_prepare.set()
        new_lines = harness.result.transcript[transcript_count:]
        assert len(new_lines) == 2
        assert new_lines[0].startswith("Radio streamer-safe mode: on.")
        assert new_lines[1].startswith("Streamer-safe mode on. Public station tuning canceled. ")
        assert new_lines[1].endswith(" instead.")
        assert harness.result.spoken[-1].interrupt is False
        assert harness.app.state is menu
        assert not driving._radio_pending_station_id
        assert driving.radio.station_id == "ff-safety-satellite"

        time.sleep(0.03)
        driving._poll_radio_tune()
        assert len(played) == 1

        transcript_count = len(harness.result.transcript)
        menu.handle_event(key_event(pygame.K_RETURN))
        assert len(harness.result.transcript) == transcript_count + 1
        assert harness.result.transcript[-1].startswith("Radio streamer-safe mode: off.")
        safe_station_id = driving.radio.station_id
        manager.result = _result(
            _station(UUID_ONE, "Playing Station", 2.0),
            _station(UUID_TWO, "Pending Station", 3.0),
        )
        driving._update_radio_discovery()
        assert len(harness.result.transcript) == transcript_count + 1
        assert not driving._radio_pending_station_id
        assert driving.radio.station_id == safe_station_id
    finally:
        harness.__exit__(None, None, None)


def test_rapid_bracket_tuning_never_plays_stale_worker(monkeypatch):
    harness, manager, _prepared, played, discarded = _start_radio_harness(monkeypatch)
    try:
        import freight_fate.states.driving_radio as radio_module

        driving = harness.driving
        manager.result = _result(
            _station(UUID_ONE, "First Station", 2.0),
            _station(UUID_TWO, "Second Station", 3.0),
        )
        driving._update_radio_discovery()
        harness.press_key(pygame.K_RIGHTBRACKET, "]")  # Night Line

        first_started = threading.Event()
        release_first = threading.Event()

        def controlled_probe(url, **kwargs):
            if UUID_ONE[:8] in url:
                first_started.set()
                assert release_first.wait(2)
            return StreamProbe(url, "audio/mpeg")

        monkeypatch.setattr(radio_module, "probe_stream_url", controlled_probe)
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert first_started.wait(1)
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        _finish_pending(driving)
        release_first.set()
        time.sleep(0.03)
        driving._poll_radio_tune()

        assert driving.radio.station_id == f"radio-browser:{UUID_TWO}"
        assert [url for _stream, url in played] == [f"https://{UUID_TWO[:8]}.example/live.mp3"]
        assert all(stream.discarded for stream in discarded)
        assert harness.result.transcript[-1] == "Playing Second Station."
    finally:
        harness.__exit__(None, None, None)


def test_failed_tune_speaks_safe_fallback_and_radio_off_stays_off(monkeypatch):
    harness, manager, _prepared, played, _discarded = _start_radio_harness(monkeypatch)
    try:
        import freight_fate.states.driving_radio as radio_module

        driving = harness.driving
        manager.result = _result(_station())
        driving._update_radio_discovery()
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        monkeypatch.setattr(
            radio_module,
            "probe_stream_url",
            lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("offline")),
        )
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        _finish_pending(driving)

        assert driving.radio.station_id == "route_playlist"
        assert played == []
        assert "KTEST Buffalo is unavailable" in harness.result.transcript[-1]
        assert "Freight Fate Roadhouse" in harness.result.transcript[-1]

        harness.press_key(pygame.K_m, "m")
        assert driving.radio.enabled is False
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert driving.radio.enabled is False
        assert harness.result.transcript[-1].startswith("Radio off. Selected")
    finally:
        harness.__exit__(None, None, None)


def test_streamer_safe_and_backend_unavailable_keep_public_dial_hidden(monkeypatch):
    harness, manager, _prepared, _played, _discarded = _start_radio_harness(
        monkeypatch,
        streamer_safe=True,
    )
    try:
        driving = harness.driving
        manager.result = _result(_station())
        driving._update_radio_discovery()
        assert not any(
            station.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES
            for station in driving.radio.available_stations()
        )
        assert manager.requests == []
        harness.press_key(pygame.K_y, "y")
        assert (
            "Streamer-safe on: public radio and personal playlists hidden"
            in (harness.result.transcript[-1])
        )
    finally:
        harness.__exit__(None, None, None)

    harness, _manager, _prepared, _played, _discarded = _start_radio_harness(
        monkeypatch,
        backend_supported=False,
    )
    try:
        harness.press_key(pygame.K_y, "y")
        assert "unavailable with this audio system" in harness.result.transcript[-1]
        assert "Local radio remains" in harness.result.transcript[-1]
    finally:
        harness.__exit__(None, None, None)


def test_streamer_safe_off_starts_silent_discovery_from_audio_settings(monkeypatch):
    harness, manager, _prepared, _played, _discarded = _start_radio_harness(
        monkeypatch,
        streamer_safe=True,
    )
    try:
        driving = harness.driving
        assert manager.requests == []
        menu = _open_audio_settings_on_streamer_safe(harness)
        transcript_count = len(harness.result.transcript)

        menu.handle_event(key_event(pygame.K_RETURN))
        assert driving.ctx.settings.radio_streamer_safe is False
        assert len(manager.requests) == 1
        assert len(harness.result.transcript) == transcript_count + 1
        assert "Radio streamer-safe mode: off" in harness.result.transcript[-1]
        assert menu.items[menu.index].text == "Radio streamer-safe mode: off"

        manager.result = _result(_station())
        before_result = len(harness.result.transcript)
        driving._update_radio_discovery()
        assert len(harness.result.transcript) == before_result
        assert driving.radio.station_by_id(f"radio-browser:{UUID_ONE}") is not None
        assert harness.app.state is menu
    finally:
        harness.__exit__(None, None, None)


def test_online_off_status_is_truthful_on_y_and_radio_screen(monkeypatch):
    harness, _manager, _prepared, _played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        driving.ctx.settings.online_services = False

        harness.press_key(pygame.K_y, "y")
        assert "Public stations unavailable: Online services off" in (harness.result.transcript[-1])
        assert "Local radio remains" in harness.result.transcript[-1]

        driving.handle_event(key_event(pygame.K_TAB))
        for _ in range(3):
            harness.app.state.handle_event(key_event(pygame.K_DOWN))
        harness.app.state.handle_event(key_event(pygame.K_RETURN))
        harness.app.state.handle_event(key_event(pygame.K_DOWN))
        assert harness.result.transcript[-1].startswith(
            "Public stations unavailable: Online services off"
        )
        assert "Local radio remains" in harness.result.transcript[-1]
    finally:
        harness.__exit__(None, None, None)


def test_online_services_keyboard_toggle_immediately_falls_back_public_audio(monkeypatch):
    from freight_fate.states.online_hub import OnlineHubState

    harness, manager, _prepared, _played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        manager.result = _result(_station())
        driving._update_radio_discovery()
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        _finish_pending(driving)
        assert driving.radio.station_id == f"radio-browser:{UUID_ONE}"

        menu = OnlineHubState(harness.app.ctx)
        harness.app.ctx.push_state(menu)
        menu.handle_event(key_event(pygame.K_DOWN))
        transcript_count = len(harness.result.transcript)
        menu.handle_event(key_event(pygame.K_RETURN))

        new_lines = harness.result.transcript[transcript_count:]
        assert len(new_lines) == 2
        assert new_lines[0].startswith("Online services: off.")
        assert new_lines[1].startswith("Online services off. Playing ")
        assert new_lines[1].endswith(" instead.")
        assert harness.result.spoken[-1].interrupt is False
        assert driving.ctx.settings.online_services is False
        assert driving.radio.current_station().source_type not in PUBLIC_DIRECTORY_SOURCE_TYPES
        assert not any(
            station.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES
            for station in driving.radio.catalog
        )
        assert harness.app.state is menu
    finally:
        harness.__exit__(None, None, None)


def test_personal_station_remains_in_simple_radio_off_bracket_path(monkeypatch):
    harness, _manager, _prepared, _played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        personal = RadioStation(
            id="playlist-test",
            name="Road Trip Mix",
            call_sign="Playlist",
            format="personal playlist",
            source="your playlist file road-trip.m3u",
            source_type=PERSONAL_PLAYLIST_SOURCE_TYPE,
            safe_for_streaming=False,
            always_available=True,
            playlist_files=("not-played-while-radio-off.mp3",),
        )
        driving.radio.catalog += (personal,)
        driving.ctx.settings.online_services = False
        driving._sync_radio_settings()
        assert "playlist-test" in {station.id for station in driving.radio.available_stations()}
        harness.press_key(pygame.K_m, "m")
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert driving.radio.station_id == "playlist-test"
        assert "Road Trip Mix" in harness.result.transcript[-1]
        assert harness.result.transcript[-1].startswith("Radio off. Selected")
    finally:
        harness.__exit__(None, None, None)


def test_streamer_safe_immediately_replaces_active_personal_station(monkeypatch):
    harness, _manager, _prepared, _played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        personal = RadioStation(
            id="playlist-test",
            name="Road Trip Mix",
            call_sign="Playlist",
            format="personal playlist",
            source="your playlist file road-trip.m3u",
            source_type=PERSONAL_PLAYLIST_SOURCE_TYPE,
            safe_for_streaming=False,
            always_available=True,
            playlist_files=("test.mp3",),
        )
        driving.radio.catalog += (personal,)
        driving.radio.station_id = personal.id
        driving.radio.preferred_station_id = personal.id
        menu = _open_audio_settings_on_streamer_safe(harness)
        transcript_count = len(harness.result.transcript)

        menu.handle_event(key_event(pygame.K_RETURN))
        new_lines = harness.result.transcript[transcript_count:]
        assert len(new_lines) == 2
        assert new_lines[0].startswith("Radio streamer-safe mode: on.")
        assert new_lines[1].startswith("Streamer-safe mode on. Playing ")
        assert new_lines[1].endswith(" instead.")
        assert harness.result.spoken[-1].interrupt is False
        assert driving.radio.station_id != personal.id
        assert personal.id not in {station.id for station in driving.radio.available_stations()}
    finally:
        harness.__exit__(None, None, None)


def test_stale_cache_status_is_reviewable_through_existing_keyboard_screen(monkeypatch):
    harness, manager, _prepared, _played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        manager.result = _result(_station(), outcome="stale")
        transcript_count = len(harness.result.transcript)
        driving._update_radio_discovery()
        assert len(harness.result.transcript) == transcript_count

        driving.handle_event(key_event(pygame.K_TAB))
        for _ in range(3):
            harness.app.state.handle_event(key_event(pygame.K_DOWN))
        harness.app.state.handle_event(key_event(pygame.K_RETURN))
        for _ in range(4):
            harness.app.state.handle_event(key_event(pygame.K_DOWN))

        assert "Using saved public radio" in harness.result.transcript[-1]
        harness.app.state.handle_event(key_event(pygame.K_DOWN))
        assert "could not be reached" in harness.result.transcript[-1]
    finally:
        harness.__exit__(None, None, None)


def test_truck_fallback_keeps_intermediate_state_coordinates_and_rekeys(monkeypatch):
    harness, manager, _prepared, _played, _discarded = _start_radio_harness(
        monkeypatch,
        origin="Atlanta",
        destination="Dallas",
    )
    try:
        driving = harness.driving
        alabama_mile = next(
            mile
            for mile in (driving.trip.total_miles * step / 200 for step in range(201))
            if _state_at(driving, mile) == "Alabama"
        )
        driving.trip.position_mi = alabama_mile
        expected = truck_position(
            driving.route,
            driving.trip.position_mi,
            driving.ctx.world,
        )
        location = driving._truck_radio_location()
        assert location.state == "Alabama"
        assert location.state_code == "AL"
        assert location.position == pytest.approx(expected)

        manager.result = DiscoveryResult(
            generation=1,
            key="real:player-location",
            explicit=False,
            stations=(),
            location=location,
            outcome="empty",
            used_truck_fallback=True,
        )
        driving._update_radio_discovery()
        assert driving._radio_discovery_key == "player-location-fallback:AL"

        texas_mile = next(
            mile
            for mile in (driving.trip.total_miles * step / 200 for step in range(201))
            if _state_at(driving, mile) == "Texas"
        )
        driving.trip.position_mi = texas_mile
        before = len(manager.requests)
        driving._update_radio_discovery()
        assert len(manager.requests) == before + 1
        assert manager.requests[-1]["market_key"] == "player-location-fallback:TX"
    finally:
        harness.__exit__(None, None, None)


def _state_at(driving, mile):
    driving.trip.position_mi = mile
    return driving.trip.current_state
