"""Tests for OnlineSetupState, the activation-code setup menu.

The menu is static at five items; only the first item's label carries
progress (see the class docstring). ``online_activation.start_activation``
and ``.poll_activation`` are monkeypatched wholesale here -- the same style
already used for ``online_presence.verify_identity`` elsewhere in this
package -- so nothing in this file touches the network or a real browser.
"""

from __future__ import annotations

import threading
import time
import urllib.error
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


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://orinks.net", code, "err", None, None)


def _run_real_poll_loop(monkeypatch, state, activation, transport, stop_event=None):
    """Wire a fake transport through the *real* poll_activation dispatch
    logic and drive it through the *real* _poll_loop -- not a hand-built
    PollResult -- so a regression in either function's status mapping (the
    exact kind of bug that let 5xx and 400 collapse to the same outcome)
    would fail these tests instead of only the ones that bypass the mapping
    by setting state._outcome directly.

    The real function is captured *before* patching: online_states.online_
    activation and this module's own online_activation name are the same
    module object, so setting the attribute on one overwrites it for both --
    a lambda that referenced online_activation.poll_activation at call time,
    instead of a captured reference, would end up calling itself.
    """
    real_poll_activation = online_activation.poll_activation
    monkeypatch.setattr(
        online_states.online_activation,
        "poll_activation",
        lambda act: real_poll_activation(act, transport=transport),
    )
    state._poll_loop(activation, stop_event or threading.Event())


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


# -- polling dispatch, driven through the real poll_activation --------------
#
# These inject a fake *transport* and let the real online_activation.poll_
# activation turn it into a PollResult, then feed that through the real
# _poll_loop -- covering the status-to-outcome mapping end to end, which the
# mailbox-driven tests below (by design) do not.


def test_poll_loop_reaches_ready_with_the_result_intact(monkeypatch):
    activation = _an_activation()

    def transport(url, payload, headers, method=None):
        return {
            "status": "ready",
            "driver_id": "rig-hauler",
            "token": "ffd_" + "b" * 64,
            "display_name": "Rig Hauler",
        }

    ctx = _make_ctx([])
    state = online_states.OnlineSetupState(ctx)
    state.enter()

    _run_real_poll_loop(monkeypatch, state, activation, transport)

    kind, result = state._outcome
    assert kind == "ready"
    assert result.driver_id == "rig-hauler"
    assert result.display_name == "Rig Hauler"


def test_poll_loop_stops_on_expired_from_a_410(monkeypatch):
    activation = _an_activation()

    def transport(url, payload, headers, method=None):
        raise _http_error(410)

    ctx = _make_ctx([])
    state = online_states.OnlineSetupState(ctx)
    state.enter()

    _run_real_poll_loop(monkeypatch, state, activation, transport)

    assert state._outcome == ("expired", None)


def test_poll_loop_stops_on_expired_from_the_deadline_without_polling(monkeypatch):
    """The code's own expires_at passing is checked before the network call --
    an activation that arrived already past its deadline never has to ask
    the server at all."""
    activation = _an_activation(expires_at=time.time() - 1.0)
    poll_calls = []

    def transport(url, payload, headers, method=None):
        poll_calls.append(1)
        return {"status": "pending"}

    ctx = _make_ctx([])
    state = online_states.OnlineSetupState(ctx)
    state.enter()

    _run_real_poll_loop(monkeypatch, state, activation, transport)

    assert state._outcome == ("expired", None)
    assert poll_calls == []


def test_poll_loop_stops_on_a_400_corrupt_code(monkeypatch):
    activation = _an_activation()

    def transport(url, payload, headers, method=None):
        raise _http_error(400)

    ctx = _make_ctx([])
    state = online_states.OnlineSetupState(ctx)
    state.enter()

    _run_real_poll_loop(monkeypatch, state, activation, transport)

    assert state._outcome == ("error", None)


def test_poll_loop_survives_transient_failures_and_still_reaches_ready(monkeypatch):
    """The regression finding 1 fixes: a 503 and a dropped connection must
    not be terminal the way a 400 is -- the loop keeps polling the same code
    and still reaches "ready" once the network recovers."""
    monkeypatch.setattr(online_states, "_ACTIVATION_POLL_INTERVAL_FIRST", 0.001)
    monkeypatch.setattr(online_states, "_ACTIVATION_POLL_INTERVAL_LATER", 0.001)
    activation = _an_activation()
    calls = {"n": 0}

    def transport(url, payload, headers, method=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(503)
        if calls["n"] == 2:
            raise OSError("connection reset")
        return {
            "status": "ready",
            "driver_id": "rig-hauler",
            "token": "ffd_" + "b" * 64,
            "display_name": "Rig Hauler",
        }

    ctx = _make_ctx([])
    state = online_states.OnlineSetupState(ctx)
    state.enter()

    _run_real_poll_loop(monkeypatch, state, activation, transport)

    assert calls["n"] == 3
    kind, result = state._outcome
    assert kind == "ready"
    assert result.driver_id == "rig-hauler"


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


def test_still_waiting_never_interrupts_the_code_announcement():
    """The line fires five seconds after the announcement *starts*, and the
    browser-failed announcement (code, address, and both fallback menu items)
    takes far longer than that to speak. Interrupting would cut the player off
    mid-address on the one path -- a remote session where no browser opens --
    where hearing the address is the only way to finish setup."""
    spoken: list[tuple[str, bool]] = []
    ctx = _make_ctx(spoken, say=speech_stub(spoken, with_interrupt=True))
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state.activation = _an_activation()
    state._phase = "waiting"
    state._poll_started = time.monotonic() - 6.0

    state.update(0.0)

    assert ("Still waiting.", False) in spoken


def test_still_waiting_clock_starts_after_the_announcement(monkeypatch):
    """The interval has to measure five seconds of actual waiting, not five
    seconds of the announcement still being spoken -- so the clock starts
    once the code has been announced, not before."""
    _no_real_browser(monkeypatch)
    activation = _an_activation()
    monkeypatch.setattr(online_states.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(online_states.online_activation, "start_activation", lambda: activation)

    ctx = _make_ctx([])
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    monkeypatch.setattr(state, "_poll_loop", lambda *_a, **_k: None)

    started_when_spoken: list[float] = []
    ctx.say = lambda _text, interrupt=True, review=True: started_when_spoken.append(
        state._poll_started
    )

    state._start_setup()
    state.update(0.0)  # drains the "activation" outcome: announce, then start the clock

    assert started_when_spoken[-1] == 0.0  # clock not yet running while the code is spoken
    assert state._poll_started > 0.0


def test_ready_poll_adopts_identity_and_speaks_the_display_name(monkeypatch):
    # The save stub records the identity it was called on rather than
    # discarding it: driver_id reaching adopt_online_identity is not enough
    # to prove the right token was saved -- a bug that adopted the correct
    # driver with a wrong, truncated, or empty token would still pass every
    # other assertion here, and would only surface later, silently, at the
    # next presence heartbeat.
    saved: list[online_states.OnlineIdentity] = []
    monkeypatch.setattr(online_states.OnlineIdentity, "save", lambda self: saved.append(self))
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
    assert len(saved) == 1
    assert saved[0].driver_id == "rig-hauler"
    assert saved[0].driver_token == result.token


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
    # ...and the two halves have to agree: telling the player retrying will
    # not help, then naming a menu item to choose again, is a contradiction
    # heard aloud with no way to scroll back and re-read it.
    assert "not fix" not in last.lower()
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


def test_cancel_while_starting_also_says_canceled():
    """A player who backs out before the activation code even arrives (still
    contacting orinks.net) gets the same confirmation as one who backs out
    mid-poll -- not just the generic menu-back sound and no word on it."""
    spoken: list[str] = []
    popped: list[str] = []
    ctx = _make_ctx(spoken, pop_state=lambda: popped.append("pop"))
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state._phase = "starting"

    state.go_back()

    assert any("canceled" in line.lower() for line in spoken if isinstance(line, str))
    assert popped == ["pop"]


def test_cancel_while_idle_stays_silent_about_canceling():
    """No request is in flight yet, so there is nothing to confirm canceling
    -- only "starting" and "waiting" get the extra line."""
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    assert state._phase == "idle"

    state.go_back()

    assert not any("canceled" in line.lower() for line in spoken if isinstance(line, str))


# -- only one worker at a time -------------------------------------------------


def test_choosing_setup_twice_starts_only_one_worker_thread(monkeypatch):
    """The guard in _start_setup, not real threading, is what is under test
    here: a second press while a request is already under way must not spin
    up a second background worker."""
    started_targets: list = []

    class CountingThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            started_targets.append(self.target)
            # Deliberately never runs the target -- this test only cares
            # whether a second Thread gets constructed while phase is
            # "starting" or "waiting", not what the worker would do.

    monkeypatch.setattr(online_states.threading, "Thread", CountingThread)
    ctx = _make_ctx([])
    state = online_states.OnlineSetupState(ctx)
    state.enter()

    state._start_setup()  # phase -> "starting"; thread #1 recorded
    state._start_setup()  # still "starting": guard must skip a new thread
    assert len(started_targets) == 1

    # Simulate the activation having already arrived (phase "waiting").
    state._phase = "waiting"
    state.activation = _an_activation()
    state._start_setup()  # a status repeat, not a fresh request
    assert len(started_targets) == 1


def test_pressing_setup_again_before_the_code_arrives_is_never_silent(monkeypatch):
    """Phase "starting" with no activation yet: there is no code to repeat,
    but returning in silence reads as "did that keypress register" in a game
    with no visual fallback to check against."""

    class NeverRunsThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            pass

    monkeypatch.setattr(online_states.threading, "Thread", NeverRunsThread)
    spoken: list[str] = []
    ctx = _make_ctx(spoken)
    state = online_states.OnlineSetupState(ctx)
    state.enter()

    state._start_setup()  # phase -> "starting", no activation yet
    spoken.clear()
    state._start_setup()  # the second press

    assert state.activation is None
    assert [line for line in spoken if isinstance(line, str)] == [
        "Still contacting orinks.net for an activation code."
    ]


# -- autostart from the offer's accept path ------------------------------------


def test_autostart_begins_setup_on_entry(monkeypatch):
    """A player who just said yes must not be asked to confirm again."""
    started: list = []
    monkeypatch.setattr(
        online_states.OnlineSetupState, "_start_setup", lambda self: started.append(True)
    )
    ctx = _make_ctx([])
    online_states.OnlineSetupState(ctx, autostart=True).enter()
    assert started == [True]


def test_without_autostart_entry_starts_nothing(monkeypatch):
    """Reaching setup from the Online menu must still wait for the player."""
    started: list = []
    monkeypatch.setattr(
        online_states.OnlineSetupState, "_start_setup", lambda self: started.append(True)
    )
    ctx = _make_ctx([])
    online_states.OnlineSetupState(ctx).enter()
    assert started == []


def test_autostart_skips_the_menu_intro_and_speaks_setup_starting(monkeypatch):
    """A player who just said "Set up now" already knows what this state is
    for. Announcing the five-item menu and then talking over it a moment
    later with "Contacting orinks.net..." (from the real _start_setup) would
    read as the game losing its place mid-sentence -- so autostart must go
    straight to that line instead of announcing the menu first."""

    class NeverRunsThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            pass  # the network request itself is not what this test checks

    monkeypatch.setattr(online_states.threading, "Thread", NeverRunsThread)
    spoken: list[str] = []
    ctx = _make_ctx(spoken)

    online_states.OnlineSetupState(ctx, autostart=True).enter()

    said = [line for line in spoken if isinstance(line, str)]
    assert said == ["Contacting orinks.net for an activation code."]
    assert not any("orinks.net account setup" in line for line in said)


def test_without_autostart_entry_still_speaks_the_menu_intro():
    """The Online-menu path is unchanged: a player choosing setup from a
    menu has not already committed, so the five-item menu is announced as
    before."""
    spoken: list[str] = []
    ctx = _make_ctx(spoken)

    online_states.OnlineSetupState(ctx).enter()

    said = [line for line in spoken if isinstance(line, str)]
    assert any("orinks.net account setup" in line for line in said)
    assert "Contacting orinks.net for an activation code." not in said
