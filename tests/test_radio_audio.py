"""Radio streaming through the audio facade.

Nothing here reaches the internet. Where a real connect is exercised it goes
to a closed port on this machine, which is refused immediately -- that is the
failure path the game has to survive anyway, because public stream URLs rot.
"""

import threading
import time

import pytest

from freight_fate import audio
from freight_fate.audio import AudioEngine

# A closed port on this machine. The connect is refused without leaving the
# machine, but not instantly -- it takes about two seconds on Windows, which is
# precisely why every test that uses it settles before shutting the engine
# down: freeing BASS from under a live connect crashes the process.
DEAD_URL = "http://127.0.0.1:1/nothing"
# Rejected by BASS before any socket is opened.
BAD_URL = "notaurl://nothing/here"


@pytest.fixture(autouse=True)
def _free_leaked_bass():
    """Free any BASS device a failing test leaves initialized (see
    tests/test_audio_backends.py for why this matters)."""
    yield
    try:
        from sound_lib.external.pybass import BASS_Free, BASS_SetDevice

        BASS_SetDevice(0)
        BASS_Free()
    except Exception:
        pass


def _settle(engine: AudioEngine, timeout: float = 15.0) -> str:
    """Wait for the background connect to reach a final state.

    Every test that starts a real connect must call this before shutdown, so
    no worker thread is still inside BASS when the device goes away.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if engine.radio_state != "connecting":
            break
        time.sleep(0.02)
    return engine.radio_state


def test_the_facade_reports_whether_radio_is_possible(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    engine = AudioEngine()
    try:
        # BASS can stream a URL; the pygame fallback cannot.
        if engine.backend_name == "bass":
            assert engine.radio_supported is True
            assert engine.radio_state == "idle"
        else:
            assert engine.radio_supported is False
            assert engine.radio_state == "unsupported"
    finally:
        engine.shutdown()


def test_pygame_backend_never_pretends_to_tune(monkeypatch):
    monkeypatch.setenv("FREIGHT_FATE_AUDIO_BACKEND", "pygame")
    engine = AudioEngine()
    try:
        assert engine.radio_supported is False
        # Every radio call is a safe no-op, so game code never has to check.
        engine.play_radio(BAD_URL)
        engine.set_radio_gain(0.5)
        engine.stop_radio()
        assert engine.radio_state == "unsupported"
    finally:
        engine.shutdown()


def test_a_dead_stream_fails_without_taking_the_game_with_it(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    engine = AudioEngine()
    try:
        if engine.backend_name != "bass":
            pytest.skip("URL streaming is a BASS-only path")
        engine.play_radio(DEAD_URL)
        # The connect happens off the game thread, so play_radio returns at once.
        assert engine.radio_state in ("connecting", "failed")
        assert _settle(engine) == "failed"
        # A failed station leaves the radio usable, not wedged.
        engine.stop_radio()
        assert engine.radio_state == "idle"
    finally:
        _settle(engine)
        engine.shutdown()


def test_an_empty_url_is_ignored(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    engine = AudioEngine()
    try:
        engine.play_radio("")
        engine.play_radio("   ")
        assert engine.radio_state in ("idle", "unsupported")
    finally:
        engine.shutdown()


def test_seeking_past_a_slow_station_does_not_get_overtaken(monkeypatch):
    """A stale connect must never override the station the driver just chose."""
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    engine = AudioEngine()
    try:
        if engine.backend_name != "bass":
            pytest.skip("URL streaming is a BASS-only path")
        for i in range(4):  # seek, seek, seek, seek
            engine.play_radio(f"{BAD_URL}/{i}")
        engine.stop_radio()
        # stop_radio orphans anything still connecting, so the state stays idle
        # however the in-flight workers finish.
        time.sleep(0.5)
        assert engine.radio_state == "idle"
    finally:
        engine.shutdown()


def test_quitting_mid_connect_leaves_the_device_alone_instead_of_crashing(monkeypatch):
    """Freeing BASS from under a live connect kills the process.

    A station that has gone dark can hold the connect thread for seconds --
    longer than anyone quitting the game should wait -- so shutdown gives it a
    short grace period and then leaves the device to the operating system.
    """
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    engine = AudioEngine()
    try:
        if engine.backend_name != "bass":
            pytest.skip("URL streaming is a BASS-only path")
        impl = engine._impl

        never_finishes = threading.Event()
        impl._radio_threads = [
            threading.Thread(target=never_finishes.wait, daemon=True, name="stuck-connect")
        ]
        impl._radio_threads[0].start()

        freed = []
        monkeypatch.setattr(impl._output, "free", lambda: freed.append(True))
        started = time.monotonic()
        assert impl._radio_connects_finished() is False
        # It waited, but not for long.
        assert time.monotonic() - started < audio.RADIO_SHUTDOWN_JOIN_S + 1.0
        never_finishes.set()
        # And with the connect finished, the device is freed normally.
        assert impl._radio_connects_finished() is True
    finally:
        engine.shutdown()


def test_radio_volume_and_gain_are_clamped():
    backend = audio._NullBackend()
    backend.set_volumes(radio=2.0)
    assert backend.radio_volume == 1.0
    backend.set_volumes(radio=-1.0)
    assert backend.radio_volume == 0.0


def test_signal_gain_scales_the_radio_level(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    engine = AudioEngine()
    try:
        if engine.backend_name != "bass":
            pytest.skip("the level model is a BASS-only path")
        impl = engine._impl
        impl.set_volumes(master=1.0, radio=0.5)
        impl.set_radio_gain(1.0)
        assert impl._radio_level() == pytest.approx(0.5)
        impl.set_radio_gain(0.5)  # half signal, half as loud
        assert impl._radio_level() == pytest.approx(0.25)
        impl.set_radio_gain(0.0)
        assert impl._radio_level() == 0.0
    finally:
        engine.shutdown()


def test_stopping_the_world_stops_the_radio(monkeypatch):
    """Pausing must not leave a station talking under the menu."""
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    engine = AudioEngine()
    try:
        if engine.backend_name != "bass":
            pytest.skip("URL streaming is a BASS-only path")
        engine.play_radio(DEAD_URL)
        engine.stop_world()
        assert engine.radio_state == "idle"
        _settle(engine)  # never free BASS with a connect still inside it
    finally:
        engine.shutdown()
