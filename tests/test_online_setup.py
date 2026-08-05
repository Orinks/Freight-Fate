"""Tests for OnlineSetupState, the activation-code setup menu.

The menu is static at five items; only the first item's label carries
progress (see the class docstring). ``online_activation.start_activation``
and ``.poll_activation`` are monkeypatched wholesale here -- the same style
already used for ``online_presence.verify_identity`` elsewhere in this
package -- so nothing in this file touches the network or a real browser.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

from speech_capture import speech_stub

from freight_fate import online_activation
from freight_fate.settings import Settings
from freight_fate.states import online_states


def _an_activation(**overrides) -> online_activation.Activation:
    defaults = dict(
        device_code="a" * 64,
        user_code="WKQR-3468",
        verification_uri="https://orinks.net/activate",
        verification_uri_complete="https://orinks.net/activate?code=WKQR-3468",
        expires_at=time.time() + 600,
        interval=3.0,
    )
    defaults.update(overrides)
    return online_activation.Activation(**defaults)


def _make_ctx(spoken: list[str] | None = None, **overrides):
    sink = spoken if spoken is not None else []
    ctx = SimpleNamespace(
        settings=Settings(),
        audio=SimpleNamespace(play=lambda _sound: None),
        say=speech_stub(sink),
        pop_state=lambda: sink.append(("pop",)),
        adopt_online_identity=lambda identity: sink.append(("identity", identity.driver_id)),
        apply_online_presence=lambda: sink.append(("profile",)),
        apply_cloud_saves=lambda: sink.append(("cloud",)),
    )
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx


def _no_real_browser(monkeypatch):
    """Every test that drains an "activation" outcome calls _announce_activation,
    which calls webbrowser.open -- never let that reach a real browser."""
    monkeypatch.setattr(online_states.webbrowser, "open", lambda _url: True)


class ImmediateThread:
    """Runs its target synchronously, matching the pattern already used for
    online-verify threads elsewhere in this package."""

    def __init__(self, *, target, **_kwargs):
        self.target = target

    def start(self):
        self.target()


# -- starting ---------------------------------------------------------------


def test_starting_speaks_the_activation_code(monkeypatch):
    _no_real_browser(monkeypatch)
    activation = _an_activation()
    monkeypatch.setattr(online_states.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(online_states.online_activation, "start_activation", lambda: activation)

    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    # The worker's own poll loop is exercised in its own tests; here only the
    # "starting" -> "code announced" transition matters.
    monkeypatch.setattr(state, "_poll_loop", lambda *_a, **_k: None)

    state._start_setup()
    state.update(0.0)  # drains the "activation" outcome, which is what speaks the code

    assert any("WKQR-3468" in line for line in spoken if isinstance(line, str))
    assert state.activation is activation
    assert state._phase == "waiting"


def test_start_failure_is_spoken_and_recoverable(monkeypatch):
    monkeypatch.setattr(online_states.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(online_states.online_activation, "start_activation", lambda: None)

    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()

    state._start_setup()
    state.update(0.0)  # drains the "start_failed" outcome, which is what speaks the failure

    assert any("Could not reach orinks.net" in line for line in spoken if isinstance(line, str))
    assert state.activation is None
    assert state._phase == "idle"


def test_browser_that_would_not_open_speaks_address_and_code_and_keeps_polling(monkeypatch):
    activation = _an_activation()

    def raise_on_open(_url):
        raise OSError("no browser handler registered")

    monkeypatch.setattr(online_states.webbrowser, "open", raise_on_open)
    monkeypatch.setattr(online_states.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(online_states.online_activation, "start_activation", lambda: activation)

    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    monkeypatch.setattr(state, "_poll_loop", lambda *_a, **_k: None)

    state._start_setup()
    state.update(0.0)  # drains the "activation" outcome, which is what announces the failure

    last = [line for line in spoken if isinstance(line, str)][-1]
    assert activation.verification_uri in last
    assert activation.user_code in last
    assert "Say my activation code again" in last
    assert "Copy my activation code" in last
    # The worker still reaches _poll_loop (stubbed above) -- opening the
    # browser failing must not cancel polling.
    assert state._phase == "waiting"


# -- review affordances: item 2 and item 3 -----------------------------------


def test_repeat_item_spells_the_code_phonetically():
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state.activation = _an_activation(user_code="WKQR-3468")

    state._repeat_code()

    assert any(online_activation.spell_code("WKQR-3468") in line for line in spoken)


def test_repeat_item_without_a_code_points_back_at_setup():
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()

    state._repeat_code()

    assert any("Set up this computer with orinks.net" in line for line in spoken)


def test_copy_item_reports_success(monkeypatch):
    monkeypatch.setattr(online_states, "write_clipboard_text", lambda _text: True)
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state.activation = _an_activation()

    state._copy_code()

    assert any("copied" in line.lower() for line in spoken)
    assert not any("could not copy" in line.lower() for line in spoken)


def test_copy_item_never_claims_a_failed_copy(monkeypatch):
    monkeypatch.setattr(online_states, "write_clipboard_text", lambda _text: False)
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state.activation = _an_activation()

    state._copy_code()

    assert not any("copied" in line.lower() and "could not" not in line.lower() for line in spoken)
    assert any("could not copy" in line.lower() for line in spoken)


# -- polling outcomes, driven directly through the update() mailbox ---------


def test_pending_poll_keeps_waiting_and_speaks_nothing_new(monkeypatch):
    """A pending poll posts no outcome; only the elapsed-time check in
    update() ever speaks "Still waiting." -- separately from this test."""

    class StopAfterTwoWaits:
        def __init__(self):
            self.waits = 0

        def is_set(self):
            return self.waits >= 2

        def wait(self, _timeout):
            self.waits += 1
            return self.waits >= 2

    poll_calls = []

    def fake_poll(_activation):
        poll_calls.append(1)
        return online_activation.PollResult(status="pending")

    monkeypatch.setattr(online_states.online_activation, "poll_activation", fake_poll)
    ctx = _make_ctx([])
    state = online_states.OnlineSetupState(ctx)
    state.enter()

    state._poll_loop(_an_activation(), StopAfterTwoWaits())

    assert len(poll_calls) == 2
    assert state._outcome is None


def test_still_waiting_is_spoken_once_after_five_seconds():
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state.activation = _an_activation()
    state._phase = "waiting"
    state._poll_started = time.monotonic() - 6.0

    state.update(0.0)
    state.update(0.0)  # a second frame must not repeat the line

    waits = [line for line in spoken if line == "Still waiting."]
    assert len(waits) == 1


def test_ready_poll_adopts_identity_and_speaks_the_display_name(monkeypatch):
    monkeypatch.setattr(online_states.OnlineIdentity, "save", lambda self: None)
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    ctx.settings.online_presence = True
    ctx.settings.cloud_saves = True
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state.activation = _an_activation()
    state._phase = "waiting"

    result = online_activation.PollResult(
        status="ready",
        driver_id="rig-hauler",
        token="ffd_" + "b" * 64,
        display_name="Rig Hauler",
    )
    state._outcome = ("ready", result)
    state.update(0.0)

    assert any("Connected to orinks.net as Rig Hauler." in line for line in spoken)
    assert state.activation is None
    assert ctx.settings.online_presence is False
    assert ctx.settings.cloud_saves is False
    assert ("identity", "rig-hauler") in spoken
    assert ("pop",) in spoken


def test_token_save_failure_reuses_the_keyring_failure_wording(monkeypatch):
    def raise_oserror(_self):
        raise OSError("no usable secret store")

    monkeypatch.setattr(online_states.OnlineIdentity, "save", raise_oserror)
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state.activation = _an_activation()
    state._phase = "waiting"

    result = online_activation.PollResult(
        status="ready", driver_id="rig-hauler", token="ffd_" + "b" * 64, display_name="Rig Hauler"
    )
    state._outcome = ("ready", result)
    state.update(0.0)

    assert any(
        "could not save the driver token securely" in line
        for line in spoken
        if isinstance(line, str)
    )
    assert not any(t == ("pop",) for t in spoken)


def test_expiry_speaks_the_recovery():
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state.activation = _an_activation()
    state._phase = "waiting"

    state._outcome = ("expired", None)
    state.update(0.0)

    last = [line for line in spoken if isinstance(line, str)][-1]
    assert "expired" in last.lower()
    assert "Set up this computer with orinks.net" in last
    assert state.activation is None
    assert state._phase == "expired"


def test_corrupt_code_error_does_not_suggest_waiting():
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state.activation = _an_activation()
    state._phase = "waiting"

    state._outcome = ("error", None)
    state.update(0.0)

    last = [line for line in spoken if isinstance(line, str)][-1]
    assert "wait" not in last.lower()
    assert "Set up this computer with orinks.net" in last
    assert state.activation is None
    assert state._phase == "error"


# -- leaving the menu ---------------------------------------------------------


def test_leaving_the_menu_stops_the_worker(monkeypatch):
    # Shrink the real polling schedule so this test, which uses a real
    # background thread and real time, finishes in well under a second.
    monkeypatch.setattr(online_states, "_ACTIVATION_POLL_INTERVAL_FIRST", 0.01)
    monkeypatch.setattr(online_states, "_ACTIVATION_POLL_INTERVAL_LATER", 0.01)
    monkeypatch.setattr(online_states, "_ACTIVATION_POLL_FIRST_PHASE_SECONDS", 0.01)
    _no_real_browser(monkeypatch)

    real_thread_cls = online_states.threading.Thread
    threads: list = []

    class RecordingThread(real_thread_cls):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            threads.append(self)

    monkeypatch.setattr(online_states.threading, "Thread", RecordingThread)

    activation = _an_activation()
    monkeypatch.setattr(online_states.online_activation, "start_activation", lambda: activation)
    monkeypatch.setattr(
        online_states.online_activation,
        "poll_activation",
        lambda _activation: online_activation.PollResult(status="pending"),
    )

    ctx = _make_ctx([])
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state._start_setup()

    time.sleep(0.05)  # let the worker actually reach the poll loop
    assert len(threads) == 1
    worker = threads[0]
    assert worker.is_alive()

    state.exit()  # what pop_state() calls when the player backs out

    worker.join(timeout=2.0)
    assert not worker.is_alive()


def test_cancel_while_waiting_says_canceled_and_still_goes_back():
    spoken: list[str] = []
    popped: list[str] = []
    ctx = _make_ctx(spoken, pop_state=lambda: popped.append("pop"))
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state.activation = _an_activation()
    state._phase = "waiting"

    state.go_back()

    assert any("canceled" in line.lower() for line in spoken if isinstance(line, str))
    assert popped == ["pop"]
