# First-Run orinks.net Offer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Offer the orinks.net connection once, right after a first-time player creates a career, without gating anything behind it.

**Architecture:** A small `OnlineOfferState` built in the mould of `SaveMigrationNoticeState`, gated on a new per-install setting, pushed by career creation in place of `CityMenuState`. Saying yes enters the existing activation flow with setup already started.

**Tech Stack:** Python 3.12, `uv`, pytest, pygame. No new dependencies.

## Global Constraints

- Repo `Freight-fate`, branch `dev`.
- Spec: `docs/superpowers/specs/2026-08-06-onboarding-offer-design.md`. Read it before Task 1.
- **Online stays optional.** Nothing here gates a career behind an account, a sign-in, or a network call. Declining must take one keypress and never be asked again.
- **The copy must not promise cloud backup or the drivers board as things connecting turns on.** Connecting links the computer to an account; both features stay off until enabled separately. A player who connects believing they are backed up, and is not, is worse off than one never offered.
- Spoken text uses the canonical nouns in `docs/ontology.md`. The activation noun is **activation code** — never "pairing code", "device code", or "setup code".
- Tests run headless (`FREIGHT_FATE_NO_SPEECH=1`) and never touch the network or a browser.
- Tests: `uv run pytest`. Lint: `uv run ruff check src tests tools`. Byte-compile: `uv run python -m compileall src tests tools`.
- `src/freight_fate/states/online_states.py` is 908 lines against a 1000-line ceiling, which is why the new state gets its own module.

## File Structure

| File | Responsibility |
| --- | --- |
| `src/freight_fate/settings.py` (modify) | Add the `online_offer_seen` gate. |
| `src/freight_fate/states/online_offer.py` (create) | `OnlineOfferState` — the two-item offer and both exits. |
| `src/freight_fate/states/online_states.py` (modify) | `OnlineSetupState` gains an auto-start flag. |
| `src/freight_fate/states/main_menu.py` (modify) | Career creation pushes the offer when the gate is open. |
| `tests/test_online_offer.py` (create) | Tests for the state and the gate. |
| `tests/test_online_setup.py` (modify) | Test for the auto-start flag. |

---

### Task 1: The gate and the offer state

**Files:**
- Modify: `src/freight_fate/settings.py`
- Create: `src/freight_fate/states/online_offer.py`
- Create: `tests/test_online_offer.py`

**Interfaces:**
- Produces: `Settings.online_offer_seen: bool` (default `False`); `OnlineOfferState(ctx)`; `should_offer_online(ctx) -> bool`.

`should_offer_online` is the single place the two skip conditions live, so career creation does not re-derive them: the gate is unset **and** no identity exists. Reading the identity uses `online_presence.OnlineIdentity.load()`, which returns `None` when the computer has never connected.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_online_offer.py`:

```python
"""Tests for the one-time first-run orinks.net offer.

Nothing here touches the network: the offer itself makes no calls, and the
accept path is asserted by the state it pushes, not by running setup.
"""

from __future__ import annotations

from types import SimpleNamespace

from speech_capture import speech_stub

from freight_fate.settings import Settings
from freight_fate.states import online_offer


def _make_ctx(spoken: list) -> SimpleNamespace:
    return SimpleNamespace(
        settings=Settings(),
        say=speech_stub(spoken),
        audio=SimpleNamespace(play=lambda *a, **k: None),
        push_state=lambda state: spoken.append(("push", type(state).__name__)),
        replace_state=lambda state: spoken.append(("replace", type(state).__name__)),
        pop_state=lambda *a, **k: spoken.append(("pop",)),
    )


def test_offered_when_the_gate_is_open_and_nothing_is_connected(monkeypatch):
    monkeypatch.setattr(online_offer, "_stored_identity", lambda: None)
    ctx = _make_ctx([])
    assert online_offer.should_offer_online(ctx) is True


def test_not_offered_once_seen(monkeypatch):
    monkeypatch.setattr(online_offer, "_stored_identity", lambda: None)
    ctx = _make_ctx([])
    ctx.settings.online_offer_seen = True
    assert online_offer.should_offer_online(ctx) is False


def test_not_offered_when_already_connected(monkeypatch):
    """A second career on a connected computer must not ask again -- the
    connection is per computer, not per career."""
    monkeypatch.setattr(online_offer, "_stored_identity", lambda: object())
    ctx = _make_ctx([])
    assert ctx.settings.online_offer_seen is False
    assert online_offer.should_offer_online(ctx) is False


def test_declining_sets_the_gate_and_enters_the_world():
    spoken: list = []
    ctx = _make_ctx(spoken)
    state = online_offer.OnlineOfferState(ctx)
    state.enter()
    state._decline()

    assert ctx.settings.online_offer_seen is True
    assert ("replace", "CityMenuState") in spoken


def test_escape_behaves_exactly_like_not_now():
    """The player must never be stuck here, and backing out must still spend
    the one offer -- otherwise it reappears on the next career."""
    spoken: list = []
    ctx = _make_ctx(spoken)
    state = online_offer.OnlineOfferState(ctx)
    state.enter()
    state.go_back()

    assert ctx.settings.online_offer_seen is True
    assert ("replace", "CityMenuState") in spoken


def test_the_offer_names_where_to_find_it_later():
    spoken: list = []
    ctx = _make_ctx(spoken)
    online_offer.OnlineOfferState(ctx).enter()
    said = " ".join(line for line in spoken if isinstance(line, str))
    assert "Online" in said


def test_the_offer_does_not_promise_backup_or_the_board():
    """Connecting does not switch either on. Promising them would leave a
    player believing their career is backed up when nothing is."""
    spoken: list = []
    ctx = _make_ctx(spoken)
    online_offer.OnlineOfferState(ctx).enter()
    said = " ".join(line for line in spoken if isinstance(line, str)).lower()
    assert "backed up" not in said
    assert "backing up" not in said


def test_not_now_is_the_starting_item():
    """The low-effort answer on a one-shot consent prompt should be the one
    that changes nothing."""
    spoken: list = []
    state = online_offer.OnlineOfferState(_make_ctx(spoken))
    state.enter()
    assert "Not now" in state.current_text()
```

**Before you run anything:** `_spend_the_offer` calls `ctx.settings.save()`, which writes to the real settings file. `tests/conftest.py` already isolates settings for the suite — confirm that before running, because a test that writes the developer's own settings would silently switch off their first-run offer and be near-impossible to trace later. If the isolation is not there, stub `save` in the test context rather than adding global fixtures.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_online_offer.py -v`
Expected: FAIL — no module named `freight_fate.states.online_offer`.

- [ ] **Step 3: Add the setting**

In `src/freight_fate/settings.py`, alongside the other online fields (`online_presence`, `cloud_saves`):

```python
    # Whether the one-time first-run offer to connect this computer to
    # orinks.net has been made. Per install, not per career: the connection
    # belongs to the computer, so a second career must not ask again. Set on
    # either answer, so declining is respected and the prompt cannot reappear
    # after a mid-prompt quit.
    online_offer_seen: bool = False
```

- [ ] **Step 4: Write the state**

Create `src/freight_fate/states/online_offer.py`. Read `src/freight_fate/states/save_notice.py` first and follow its shape — announce, act, `replace_state` onward, and `go_back` that never leaves the player stuck.

```python
"""The one-time offer to connect this computer to an orinks.net account.

Shown once, straight after a first career is created, because nothing else
tells a new player the feature exists. Online is optional and stays optional:
declining takes one keypress, sets the gate, and is never asked again.

What the copy deliberately does NOT say: that connecting turns on cloud
backup or the drivers board. It does not -- both stay off until the player
enables each separately -- and a player who connects believing their career is
backed up, and is not, is worse off than one who was never offered.
"""

from __future__ import annotations

from ..online_presence import OnlineIdentity
from .base import MenuItem, MenuState


def _stored_identity():
    """The saved account credentials, or None. Split out so tests can pin it
    without touching the platform secret store."""
    return OnlineIdentity.load()


def should_offer_online(ctx) -> bool:
    """Whether a first-run player should hear the offer at all."""
    if ctx.settings.online_offer_seen:
        return False
    return _stored_identity() is None


class OnlineOfferState(MenuState):
    title = "Connect to orinks.net"
    intro_help = "Choose Set up now to connect this computer, or Not now to start driving."

    def announce_entry(self) -> None:
        self.ctx.say(
            "Before you set off. You can connect this computer to an "
            "orinks.net account. That is what lets you turn on cloud backup "
            "for your career and appear on the drivers board later, from "
            "Online on the main menu. It takes a code and your browser, and "
            "you can do it any time instead. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        # Not now first, so the cursor starts on the answer that changes
        # nothing. Escape takes the same path.
        return [
            MenuItem("Not now", self._decline, help="Start driving. You can connect later from Online."),
            MenuItem("Set up now", self._accept, help="Connect this computer to an orinks.net account."),
        ]

    def _spend_the_offer(self) -> None:
        self.ctx.settings.online_offer_seen = True
        self.ctx.settings.save()

    def _enter_world(self) -> None:
        from .city import CityMenuState

        self.ctx.replace_state(CityMenuState(self.ctx))

    def _decline(self) -> None:
        self._spend_the_offer()
        self.ctx.say(
            "No problem. You can connect any time from Online on the main menu.",
            interrupt=True,
        )
        self._enter_world()

    def _accept(self) -> None:
        self._spend_the_offer()
        self._enter_world()

    def go_back(self) -> None:
        # Escape means Not now. The player must never be stuck here, and
        # backing out still spends the offer so it cannot reappear.
        self._decline()
```

Note `_accept` currently only enters the world — Task 2 wires it to setup. Leave it that way so this task's tests pass on their own terms.

- [ ] **Step 5: Run to verify they pass**

Run: `uv run pytest tests/test_online_offer.py -v` — all pass.

- [ ] **Step 6: Commit**

```bash
git add src/freight_fate/settings.py src/freight_fate/states/online_offer.py tests/test_online_offer.py
git commit -m "feat(online): the one-time first-run offer to connect an account"
```

---

### Task 2: Saying yes goes straight into activation

**Files:**
- Modify: `src/freight_fate/states/online_states.py`
- Modify: `src/freight_fate/states/online_offer.py`
- Modify: `tests/test_online_setup.py`, `tests/test_online_offer.py`

**Interfaces:**
- Consumes: `OnlineOfferState._accept` from Task 1.
- Produces: `OnlineSetupState(ctx, *, autostart: bool = False)`.

A player who just answered "Set up now" must not then be asked to choose "Set up this computer with orinks.net" from a five-item menu. `autostart` starts the same `_start_setup` the menu item calls, on entry.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_online_setup.py`:

```python
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
```

Append to `tests/test_online_offer.py`:

```python
def test_accepting_pushes_setup_with_activation_already_started():
    spoken: list = []
    ctx = _make_ctx(spoken)
    pushed: list = []
    ctx.replace_state = lambda state: pushed.append(state)

    state = online_offer.OnlineOfferState(ctx)
    state.enter()
    state._accept()

    assert ctx.settings.online_offer_seen is True
    names = [type(s).__name__ for s in pushed]
    assert "OnlineSetupState" in names
    setup = next(s for s in pushed if type(s).__name__ == "OnlineSetupState")
    # The flag, not just the state: pushing setup without autostart would
    # leave the player confirming a decision they already made.
    assert setup.autostart is True
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_online_setup.py tests/test_online_offer.py -v`
Expected: FAIL — `OnlineSetupState` takes no `autostart` argument.

- [ ] **Step 3: Add the flag**

In `OnlineSetupState.__init__`, accept and store `autostart`, and in `enter()` call `self._start_setup()` when it is set — after the existing entry work, so the announcement order is unchanged. Comment why it exists.

- [ ] **Step 4: Wire the accept path**

In `online_offer.py`, replace `_accept`'s body so it pushes setup with the flag, keeping the city menu underneath so backing out of setup lands in the world rather than back on the offer:

```python
    def _accept(self) -> None:
        from .city import CityMenuState
        from .online_states import OnlineSetupState

        self._spend_the_offer()
        self.ctx.replace_state(CityMenuState(self.ctx))
        self.ctx.push_state(OnlineSetupState(self.ctx, autostart=True))
```

- [ ] **Step 5: Run to verify they pass**

Run: `uv run pytest tests/test_online_setup.py tests/test_online_offer.py -v`

- [ ] **Step 6: Commit**

```bash
git add src/freight_fate/states/online_states.py src/freight_fate/states/online_offer.py tests/test_online_setup.py tests/test_online_offer.py
git commit -m "feat(online): saying yes to the offer starts activation immediately"
```

---

### Task 3: Career creation, and the player-facing docs

**Files:**
- Modify: `src/freight_fate/states/main_menu.py`
- Modify: `tests/test_online_offer.py`
- Modify: `CHANGELOG.md`, `ROADMAP.md`, `docs/ontology.md`

**Interfaces:**
- Consumes: `should_offer_online(ctx)` and `OnlineOfferState` from Task 1.

The confirm path is `_pick` in the city picker (`main_menu.py`, around line 746). It pops its three pickers, pushes `CityMenuState`, then speaks "Welcome aboard…". Push the offer **instead of** `CityMenuState` when the gate is open; the offer's own exits put `CityMenuState` on the stack, so the destination is identical either way. Leave the "Welcome aboard" line exactly where it is — the player hears where they are before being asked anything.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_online_offer.py`:

```python
def test_creating_a_first_career_reaches_the_offer(monkeypatch):
    """The offer replaces the city menu at career creation; its own exits put
    the city menu back, so a player lands in the same place either way."""
    from freight_fate.states import main_menu

    monkeypatch.setattr(online_offer, "_stored_identity", lambda: None)
    ctx = _make_ctx([])
    assert main_menu._first_state_after_career_creation(ctx).__class__.__name__ == "OnlineOfferState"


def test_creating_a_later_career_goes_straight_to_the_city_menu(monkeypatch):
    from freight_fate.states import main_menu

    monkeypatch.setattr(online_offer, "_stored_identity", lambda: None)
    ctx = _make_ctx([])
    ctx.settings.online_offer_seen = True
    assert main_menu._first_state_after_career_creation(ctx).__class__.__name__ == "CityMenuState"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_online_offer.py -v`
Expected: FAIL — `_first_state_after_career_creation` does not exist.

- [ ] **Step 3: Add the helper and use it**

Add to `main_menu.py`, beside `pending_notice_state`, which it deliberately resembles:

```python
def _first_state_after_career_creation(ctx) -> State:
    """The city menu, or the one-time orinks.net offer ahead of it."""
    from .city import CityMenuState
    from .online_offer import OnlineOfferState, should_offer_online

    if should_offer_online(ctx):
        return OnlineOfferState(ctx)
    return CityMenuState(ctx)
```

Then in `_pick`, replace `self.ctx.push_state(CityMenuState(self.ctx))` with `self.ctx.push_state(_first_state_after_career_creation(self.ctx))`.

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest && uv run ruff check src tests tools && uv run python -m compileall src tests tools`

- [ ] **Step 5: Write the player-facing docs**

`CHANGELOG.md`, under `## Unreleased` — CI-gated because `src/` changed. Bold lead sentence, then plain player language. Say that the game now offers to connect an account when you create your first career, that it asks once, and that Not now is fine and it stays available from Online. Do not describe it as enabling backup or the board.

`ROADMAP.md` — a bullet in the current release-line section.

`docs/ontology.md` — check whether this introduces a spoken concept needing a row. It reuses **activation code**; if the offer itself needs a canonical noun, add it.

- [ ] **Step 6: Commit**

```bash
git add src/freight_fate/states/main_menu.py tests/test_online_offer.py CHANGELOG.md ROADMAP.md docs/ontology.md
git commit -m "feat(online): offer the account connection after a first career"
```

---

## Manual verification

Delete or rename your settings file and your saved identity, create a career, and listen: the offer should arrive after "Welcome aboard" and before the dispatch board, with the cursor on "Not now". Check Escape behaves as Not now, that creating a second career asks nothing, and that "Set up now" reads out an activation code without a second confirmation.
