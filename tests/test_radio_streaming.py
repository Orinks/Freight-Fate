"""Radio streams connect off the game thread and fail without freezing it."""

import threading
import time

import pytest

from freight_fate.audio import AudioEngine

URL = "http://example.invalid/stream"
OTHER = "http://example.invalid/other"


class FakeStream:
    def __init__(self, gate: threading.Event | None = None, fail: bool = False):
        if gate is not None:
            gate.wait(timeout=5.0)
        if fail:
            raise RuntimeError("no route to station")
        self.handle = 1
        self.volume = None
        self.played = False
        self.freed = False

    def set_volume(self, volume):
        self.volume = volume

    def play(self):
        self.played = True

    @property
    def is_playing(self):
        return self.played and not self.freed

    def free(self):
        self.freed = True


@pytest.fixture
def bass(monkeypatch):
    engine = AudioEngine()
    impl = engine._impl
    if getattr(impl, "name", "") != "bass":
        engine.shutdown()
        pytest.skip("BASS backend unavailable")
    # The fade slide is a real BASS call; fakes have no real handle.
    monkeypatch.setattr(impl, "_bass_call", lambda *a, **k: None)
    monkeypatch.setattr(impl, "_fade_out", lambda stream, ms: stream.free())
    yield engine, impl
    engine.shutdown()


def wait_for_workers(impl, timeout=5.0):
    deadline = time.monotonic() + timeout
    for thread in list(impl._radio_threads):
        thread.join(max(0.0, deadline - time.monotonic()))


def test_stream_opens_off_thread_and_update_wires_it(bass, monkeypatch):
    engine, impl = bass
    monkeypatch.setattr(impl, "_URLStream", lambda url, autofree: FakeStream())
    engine.play_radio_stream(URL)  # returns immediately, nothing wired yet
    assert not engine.music_playing()
    wait_for_workers(impl)
    engine.update(0.016)
    assert engine.music_playing()
    assert impl._music_track == URL


def test_failed_connect_raises_on_the_retry_not_the_tune(bass, monkeypatch):
    engine, impl = bass
    monkeypatch.setattr(impl, "_URLStream", lambda url, autofree: FakeStream(fail=True))
    engine.play_radio_stream(URL)  # the tune itself never blocks or raises
    wait_for_workers(impl)
    engine.update(0.016)
    assert not engine.music_playing()
    with pytest.raises(RuntimeError):
        engine.play_radio_stream(URL)  # the reconnect loop's retry hears it
    # The failure was consumed: tuning back later starts a fresh attempt.
    monkeypatch.setattr(impl, "_URLStream", lambda url, autofree: FakeStream())
    engine.play_radio_stream(URL)
    wait_for_workers(impl)
    engine.update(0.016)
    assert engine.music_playing()


def test_slow_connect_loses_to_a_newer_tune(bass, monkeypatch):
    engine, impl = bass
    gate = threading.Event()
    streams = {}

    def make(url, autofree):
        streams[url] = FakeStream(gate=gate if url == URL else None)
        return streams[url]

    monkeypatch.setattr(impl, "_URLStream", make)
    engine.play_radio_stream(URL)  # stalls on the gate
    engine.play_radio_stream(OTHER)  # driver seeks on
    wait_for_workers(impl, timeout=0.2)  # OTHER finishes; URL still gated
    engine.update(0.016)
    gate.set()
    wait_for_workers(impl)
    engine.update(0.016)
    assert impl._music_track == OTHER
    assert streams[URL].freed  # the late arrival was dropped, not wired


def test_radio_off_while_connecting_orphans_the_stream(bass, monkeypatch):
    engine, impl = bass
    gate = threading.Event()
    streams = []

    def make(url, autofree):
        stream = FakeStream(gate=gate)
        streams.append(stream)
        return stream

    monkeypatch.setattr(impl, "_URLStream", make)
    engine.play_radio_stream(URL)
    engine.stop_music()  # radio switched off mid-connect
    gate.set()
    wait_for_workers(impl)
    engine.update(0.016)
    assert not engine.music_playing()
    assert impl._music_track is None
    assert streams and streams[0].freed
