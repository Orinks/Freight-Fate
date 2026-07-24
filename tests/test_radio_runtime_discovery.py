"""Transcript-backed keyboard proof for transparent runtime radio discovery."""

from __future__ import annotations

import threading
import time

import pygame
import pytest
from playtest_harness import PlaytestHarness, key_event

from freight_fate.radio import (
    DIRECTORY_SOURCE_TYPE,
    PERSONAL_PLAYLIST_SOURCE_TYPE,
    RadioStation,
    truck_position,
)
from freight_fate.radio_browser import DirectoryStation
from freight_fate.radio_discovery import ApproximateLocation, DiscoveryResult
from freight_fate.radio_url_safety import StreamProbe

UUID_ONE = "12345678-1234-1234-1234-123456789abc"
UUID_TWO = "22345678-1234-1234-1234-123456789abc"


def _station(uuid=UUID_ONE, name="KTEST Buffalo", distance=5.0):
    return DirectoryStation(
        uuid=uuid,
        name=name,
        format="community; MP3, 128 kilobits",
        codec="MP3",
        bitrate=128,
        stream_url=f"https://{uuid[:8]}.example/live.mp3",
        lat=42.9,
        lon=-78.8,
        distance_miles=distance,
        state="New York",
        city="Buffalo",
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
    harness.app.ctx.settings.radio_real_streams = True
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
            station.source_type == DIRECTORY_SOURCE_TYPE
            for station in driving.radio.available_stations()
        )
        assert manager.requests == []
    finally:
        harness.__exit__(None, None, None)

    harness, _manager, _prepared, _played, _discarded = _start_radio_harness(
        monkeypatch,
        backend_supported=False,
    )
    try:
        harness.press_key(pygame.K_y, "y")
        assert "audio system cannot play them" in harness.result.transcript[-1]
        assert "Built-ins remain" in harness.result.transcript[-1]
    finally:
        harness.__exit__(None, None, None)


def test_online_off_status_is_truthful_on_y_and_radio_screen(monkeypatch):
    harness, _manager, _prepared, _played, _discarded = _start_radio_harness(monkeypatch)
    try:
        driving = harness.driving
        driving.ctx.settings.online_services = False

        harness.press_key(pygame.K_y, "y")
        assert "Public streams allowed; Online services off" in harness.result.transcript[-1]
        assert "Built-ins remain" in harness.result.transcript[-1]

        driving.handle_event(key_event(pygame.K_TAB))
        for _ in range(3):
            harness.app.state.handle_event(key_event(pygame.K_DOWN))
        harness.app.state.handle_event(key_event(pygame.K_RETURN))
        harness.app.state.handle_event(key_event(pygame.K_DOWN))
        assert harness.result.transcript[-1].startswith(
            "Public streams allowed; Online services off"
        )
        assert "Built-ins remain" in harness.result.transcript[-1]
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
        harness.press_key(pygame.K_m, "m")
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert driving.radio.station_id == "playlist-test"
        assert "Road Trip Mix" in harness.result.transcript[-1]
        assert harness.result.transcript[-1].startswith("Radio off. Selected")
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
        for _ in range(3):
            harness.app.state.handle_event(key_event(pygame.K_DOWN))

        assert "Using saved nearby stations" in harness.result.transcript[-1]
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
