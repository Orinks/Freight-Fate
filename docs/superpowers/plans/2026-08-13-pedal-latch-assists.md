# Pedal Latch Yields to Speed Authorities — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A latched throttle becomes the lowest-priority speed input: cruise, the speed keeper, and curve assist outrank it while engaged, and it resumes when they release — per `docs/superpowers/specs/2026-08-13-pedal-latch-assists-design.md`.

**Architecture:** One split at the input source: `_update_pedal_latches` stops pre-blending the throttle latch into `key_up`, so the frame can compute an effective throttle (latch yields while any speed authority is engaged) and pass hand-only input to the assists' manual-override gates. A small predicate `_speed_authority_engaged()` is the single definition of "someone smarter owns the pedal."

**Tech Stack:** Python 3.12, pygame (headless in tests), pytest. Run everything with `uv run`.

## Global Constraints

- All pytest invocations go through the **test-runner agent** (project rule: it is the only thing that invokes pytest). Commands below are what to hand it. Always serial for these files: `-n 0 -p no:cacheprovider`, env `FREIGHT_FATE_NO_SPEECH=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`.
- Spoken text: player language only, canonical nouns from `docs/ontology.md`. Before writing the catch line in Task 5, read the ontology rows for the cruise and speed-keeper concepts and reuse their exact nouns (the codebase speaks "Adaptive cruise …" and "Speed keeper …"; "automatic speed control" is the umbrella noun).
- A physically held key keeps today's meaning everywhere: live manual override. Only the LATCH yields.
- The existing hard releases (opposite pedal, emergency brake, live hazard/AEB, overspeed) stay releases. Do not convert them to yields.
- Intermediate commits touching `src/` carry `[skip changelog]`; Task 6 adds the real CHANGELOG entry.
- Lint before each commit: `uv run ruff check src tests` (pre-commit runs ruff + format anyway; re-stage if the format hook rewrites files).
- Match surrounding comment density and idiom — this codebase explains *why* in prose comments.

## File Structure

- `src/freight_fate/states/driving_speed_control.py` — add `_speed_authority_engaged()` (owns cruise/keeper lifecycle already).
- `src/freight_fate/states/driving.py` — init `self._latch_yielding = False` beside the latch construction (~line 598).
- `src/freight_fate/states/driving_controls.py` — `_update_pedal_latches` return-shape change (~1393) and catch-line wording (~1432).
- `src/freight_fate/states/driving_updates.py` — input blending in `update()` (~209–245), hand-only `accelerating` for `_update_cruise`/`_update_keeper` (~340), curve-assist jake retry (~847).
- `tests/test_pedal_latch_assists.py` — new file, all behavior tests (patterned on `tests/test_pedal_latch.py`).

Read before starting: `tests/test_pedal_latch.py` (FakeKeys + `_drive_frames` pattern), `tests/driving_feature_helpers.py` (`start_drive`, `quiet_trip`, `release_air_brakes`), and the curve rig at `tests/test_driving_features.py:3520` area.

---

### Task 1: The authority predicate

**Files:**
- Modify: `src/freight_fate/states/driving_speed_control.py` (add method to `SpeedControlStateMixin`)
- Test: `tests/test_pedal_latch_assists.py` (create)

**Interfaces:**
- Produces: `SpeedControlStateMixin._speed_authority_engaged(self) -> bool` — True iff `self._cruise_mph is not None or self._keeper_mph is not None or self._curve_assist_active`. Tasks 2 and 4 call it.

- [ ] **Step 1: Write the failing test**

```python
"""A latched throttle yields to the speed authorities.

Owner design 2026-08-13 (spec: docs/superpowers/specs/
2026-08-13-pedal-latch-assists-design.md). Tester Brandon latched the
throttle for the whole trip and expected the assists to manage speed over
it; every assist read the latch as a manual override and stood down. The
latch is now the lowest-priority speed input: cruise, the speed keeper,
and curve assist outrank it while engaged, and it ramps back in when they
release. A hand-held key keeps its manual-override meaning everywhere.
"""

import pygame
from speech_capture import speech_stub

DT = 1 / 60


class FakeKeys:
    def __init__(self, held):
        self.held = held

    def __getitem__(self, key):
        return key in self.held


def _drive_frames(driving, seconds):
    t = 0.0
    while t < seconds:
        driving.update(DT)
        t += DT


def _latch_throttle(driving):
    """Catch the latch directly; the gesture itself is test_pedal_latch.py's job."""
    driving._throttle_latch.latched = True
    driving._throttle_latch._state = "resting"


def test_speed_authority_predicate_reads_all_three():
    from driving_feature_helpers import start_drive

    from freight_fate.app import App

    app = App()
    try:
        d = start_drive(app)
        assert not d._speed_authority_engaged()
        d._cruise_mph = 55.0
        assert d._speed_authority_engaged()
        d._cruise_mph = None
        d._keeper_mph = 25.0
        assert d._speed_authority_engaged()
        d._keeper_mph = None
        d._curve_assist_active = True
        assert d._speed_authority_engaged()
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Hand the test-runner: `uv run pytest tests/test_pedal_latch_assists.py -n 0 -q -p no:cacheprovider` (env as in Global Constraints).
Expected: FAIL with `AttributeError: ... has no attribute '_speed_authority_engaged'`.

- [ ] **Step 3: Write minimal implementation**

In `src/freight_fate/states/driving_speed_control.py`, on `SpeedControlStateMixin` (near `_disarm_speed_control`):

```python
    def _speed_authority_engaged(self) -> bool:
        """Whether an automatic speed system currently owns the pedal.

        This is the latch's whole priority rule: a LATCHED throttle is the
        lowest-priority speed input and contributes nothing while any of
        these is engaged (owner design 2026-08-13, after tester Brandon
        latched for the whole trip expecting the assists to drive). A
        hand-held key is a different thing entirely -- live manual
        override -- and never consults this.
        """
        return (
            self._cruise_mph is not None
            or self._keeper_mph is not None
            or self._curve_assist_active
        )
```

- [ ] **Step 4: Run test to verify it passes** (same command). Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/freight_fate/states/driving_speed_control.py tests/test_pedal_latch_assists.py
git commit -m "feat(driving): speed-authority predicate for the pedal latch [skip changelog]"
```

---

### Task 2: The latch yields; cruise and the keeper run under it

**Files:**
- Modify: `src/freight_fate/states/driving_controls.py:1393-1449` (`_update_pedal_latches`)
- Modify: `src/freight_fate/states/driving_updates.py:209-245` and `:340-341`
- Modify: `src/freight_fate/states/driving.py` (~598, latch init block)
- Test: `tests/test_pedal_latch_assists.py`

**Interfaces:**
- Consumes: `_speed_authority_engaged()` from Task 1.
- Produces: `_update_pedal_latches(...) -> tuple[bool, bool, bool]` returning `(hand_up, key_down_effective, throttle_latched)` — the throttle latch is NO LONGER blended into the first element. `self._latch_yielding: bool` set every frame in `update()`; Task 4 reads it.

- [ ] **Step 1: Write the failing tests** (append to the new file)

```python
def test_cruise_holds_its_speed_under_a_latched_throttle(monkeypatch):
    """The Brandon case: latch caught, cruise engaged -- cruise must drive
    the pedal, not fight a throttle ramping to full."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.velocity_mps = 60 / 2.2369362920544
        _latch_throttle(d)
        d._engage_cruise(55.0)

        _drive_frames(d, 3.0)

        assert d._cruise_mph is not None  # cruise never stood down
        assert d._throttle_latch.latched  # and the latch never dropped
        # Cruise is trimming DOWN toward 55: a yielded latch cannot be
        # holding the pedal at full power.
        assert d.truck.throttle < 0.5
    finally:
        app.shutdown()


def test_a_hand_held_key_still_stands_the_assists_down(monkeypatch):
    """Physical hold keeps today's manual-override meaning."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = {pygame.K_UP}
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.velocity_mps = 60 / 2.2369362920544
        d._engage_cruise(55.0)

        _drive_frames(d, 2.0)

        assert d._cruise_mph is not None  # engaged, waiting for the key to lift
        assert d.truck.throttle > 0.9  # but the hand owns the pedal
    finally:
        app.shutdown()


def test_the_latch_ramps_back_in_when_the_authority_releases(monkeypatch):
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.velocity_mps = 60 / 2.2369362920544
        _latch_throttle(d)
        d._engage_cruise(55.0)
        _drive_frames(d, 2.0)
        assert d.truck.throttle < 0.5

        d._cancel_cruise()
        _drive_frames(d, 1.0)

        assert d._throttle_latch.latched
        assert d.truck.throttle > 0.9  # the latch has the pedal again
    finally:
        app.shutdown()


def test_keeper_holds_a_zone_speed_under_a_latched_throttle(monkeypatch):
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App
    from freight_fate.sim.trip_models import Zone

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        # A school zone under the wheels, truck well over its number.
        start = d.trip.position_mi
        d.trip.zones.append(Zone(start - 0.1, start + 3.0, 25.0, "school"))
        d.truck.velocity_mps = 40 / 2.2369362920544
        _latch_throttle(d)
        d._engage_keeper(25.0, "school", target_mph=25.0, announce=False)

        _drive_frames(d, 8.0)

        assert d._keeper_mph is not None  # keeper never stood down
        assert d._throttle_latch.latched
        assert d.truck.speed_mph < 33.0  # shedding toward the zone number
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run to verify the four fail** (same command). Expected: the three latch tests FAIL (throttle pinned near 1.0, keeper/cruise standing down — before the fix `accelerating` is permanently true under a latch); the hand-held test may already PASS (it pins existing behavior — that is its job). If `_engage_keeper`'s real signature differs from `driving_events.py:3013`'s call, match the call site, not this plan.

- [ ] **Step 3: Implement the input split**

In `driving_controls.py`, `_update_pedal_latches` — change ONLY the two return statements and the docstring's last paragraph:

```python
        Returns ``(hand_up, key_down, throttle_latched)``: the throttle
        latch is reported separately rather than blended in, because a
        latched throttle is the lowest-priority speed input -- update()
        lets it drive the pedal only when no speed authority (cruise,
        keeper, curve assist) is engaged, while a hand-held key stays a
        live manual override. The brake latch keeps pre-blending: nothing
        outranks the driver's brake.
```

Early return (setting off): `return key_up, key_down, False`
Final return:

```python
        return (
            key_up,
            key_down or self._brake_latch.latched,
            self._throttle_latch.latched,
        )
```

In `driving.py` beside the `PedalLatch()` construction (~598):

```python
        # True while a caught throttle latch is standing down for a speed
        # authority (see _speed_authority_engaged); the curve block reads
        # it to retry the jake once the yielded throttle drains.
        self._latch_yielding = False
```

In `driving_updates.py`, replace lines 216–219:

```python
        hand_up, key_down, throttle_latched = self._update_pedal_latches(
            key_up, key_down, pad_throttle, pad_brake, keys[pygame.K_b], dt
        )
        # The latch is the LOWEST-priority speed input: while cruise, the
        # keeper, or curve assist is engaged it contributes nothing, and it
        # ramps back in when the last of them releases -- no re-gesture
        # (owner design 2026-08-13). A hand-held key stays a live manual
        # override, which is why the assists are handed hand_accelerating
        # below rather than this blended value.
        self._latch_yielding = throttle_latched and self._speed_authority_engaged()
        key_up = hand_up or (throttle_latched and not self._latch_yielding)
        accelerating = key_up or pad_throttle > 0.05
        hand_accelerating = hand_up or pad_throttle > 0.05
```

At lines 340–341 pass the hand-only signal:

```python
        self._update_cruise(dt, braking, hand_accelerating, clutch_disengaged)
        self._update_keeper(dt, braking, hand_accelerating, clutch_disengaged)
```

No changes inside `_update_cruise`/`_update_keeper` — their `if accelerating: return` gates now honestly mean "the hand is on the pedal."

- [ ] **Step 4: Run the file** (same command). Expected: all Task 1–2 tests PASS.

- [ ] **Step 5: Regression check** — hand the test-runner: `uv run pytest tests/test_pedal_latch.py tests/test_driving_features.py -n 0 -q -p no:cacheprovider`. Expected: all pass (`test_latched_throttle_drives_the_truck_hands_free` exercises the new return shape with no authority engaged).

- [ ] **Step 6: Commit**

```bash
git add src/freight_fate/states/driving_controls.py src/freight_fate/states/driving_updates.py src/freight_fate/states/driving.py tests/test_pedal_latch_assists.py
git commit -m "feat(driving): latched throttle yields to cruise and the speed keeper [skip changelog]"
```

---

### Task 3: Releasing the latch never cancels an assist

**Files:**
- Test: `tests/test_pedal_latch_assists.py` (test-only task — pins the owner's rule; expected to pass already, and must be red-teamed by reading it)

**Interfaces:**
- Consumes: `_latch_throttle`, FakeKeys scaffold from earlier tasks.

- [ ] **Step 1: Write the test**

```python
def test_releasing_the_latch_leaves_cruise_holding(monkeypatch):
    """Owner rule 2026-08-13: unlatching hands the pedal back to the hand;
    it is not a cruise cancel. The brake stays the cancel, unchanged."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    spoken = []
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.velocity_mps = 60 / 2.2369362920544
        _latch_throttle(d)
        d._engage_cruise(55.0)
        _drive_frames(d, 1.0)

        # A fresh press of the throttle key returns the pedal to the hand...
        held.add(pygame.K_UP)
        _drive_frames(d, 0.3)
        held.discard(pygame.K_UP)
        _drive_frames(d, 1.0)

        assert not d._throttle_latch.latched
        assert "Throttle released." in spoken
        assert d._cruise_mph is not None  # ...and cruise never blinked
        assert not any("cruise canceled" in s.lower() for s in spoken)
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run it** (same command). Expected: PASS — cruise cancel keys off `braking_key`/emergency only (`driving_updates.py:260`). If it FAILS, something couples throttle input to a cancel: investigate with superpowers:systematic-debugging before touching anything.

- [ ] **Step 3: Commit**

```bash
git add tests/test_pedal_latch_assists.py
git commit -m "test(driving): unlatching the throttle is not a cruise cancel [skip changelog]"
```

---

### Task 4: Curve assist gets the pedal, and its jake, under a latch

**Files:**
- Modify: `src/freight_fate/states/driving_updates.py:847` (jake engage condition in the curve block)
- Test: `tests/test_pedal_latch_assists.py`

**Interfaces:**
- Consumes: `self._latch_yielding` from Task 2; the fake-curve rig pattern from `tests/test_driving_features.py:3424-3560` (read it first — reuse `RouteCurve` from `freight_fate.data.curves` exactly as `_CurveRig` does).

- [ ] **Step 1: Write the failing tests**

```python
def _fake_curve(monkeypatch, driving, advisory=35.0):
    from freight_fate.data.curves import RouteCurve

    curve = RouteCurve(
        start_mi=driving.trip.position_mi - 0.05,
        end_mi=driving.trip.position_mi + 2.0,
        direction="R",
        angle_deg=60.0,
        advisory_mph=advisory,
        connector=False,
    )
    monkeypatch.setattr(driving.trip, "curve_at", lambda _mile: curve)
    return curve


def test_curve_assist_drains_a_latched_throttle(monkeypatch):
    """The 0.35 service trim must not fight a pedal ramping to full."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.ctx.settings.curve_speed_assist = True
        _fake_curve(monkeypatch, d, advisory=35.0)
        d.truck.velocity_mps = 50 / 2.2369362920544
        _latch_throttle(d)

        _drive_frames(d, 3.0)

        assert d._curve_assist_active
        assert d._throttle_latch.latched
        assert d.truck.throttle < 0.05  # yielded and drained
        assert d.truck.speed_mph < 48.0  # the trim is actually winning now
    finally:
        app.shutdown()
```

If the `RouteCurve` constructor differs, copy the exact construction from `_CurveRig` in `tests/test_driving_features.py` — that rig is the source of truth, not this plan.

- [ ] **Step 2: Run to verify it fails** (same command). Expected: FAIL — before the fix the latch is not yielding to curve assist... but note Task 2 already added `_curve_assist_active` to the predicate, so this may PASS outright. If it passes, keep it as pinning coverage and continue; the genuinely new behavior is the jake test below.

- [ ] **Step 3: Write the failing jake test**

The jake only engages on the frame curve assist first becomes active (`curve_assisting and not self._curve_assist_active`), and on that frame a just-yielded latch still has the throttle above the `t.throttle < 0.05` capability check — so without a retry the corner never gets its grade jake under a latch:

```python
def test_curve_assist_jake_arrives_once_the_latched_throttle_drains(monkeypatch):
    """On a real downgrade the assist raises the retarder -- but on the
    engage frame a yielded latch is still draining, so the capability
    check must retry while the latch is yielding."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.ctx.settings.curve_speed_assist = True
        _fake_curve(monkeypatch, d, advisory=30.0)
        monkeypatch.setattr(d, "_on_downgrade", lambda: True)
        d.truck.velocity_mps = 50 / 2.2369362920544
        _latch_throttle(d)

        _drive_frames(d, 3.0)

        assert d._curve_assist_active
        assert d._curve_assist_jake  # engaged after the drain, not never
    finally:
        app.shutdown()
```

Check how the existing downgrade jake tests fake the grade (`tests/test_driving_features.py::test_curve_assist_jakes_a_bend_on_a_real_downgrade`) and copy that mechanism if it is not a monkeypatched `_on_downgrade`.

- [ ] **Step 4: Run to verify the jake test fails.** Expected: FAIL on `assert d._curve_assist_jake`.

- [ ] **Step 5: Implement the retry**

In `driving_updates.py:847`, widen the engage condition — strictly scoped to the yielding latch so hand-throttle behavior is untouched:

```python
        if curve_assisting and (
            not self._curve_assist_active
            # A yielded latch is still draining on the engage frame, so the
            # jake_capable check below sees throttle above its threshold and
            # the corner would never get its grade retarder. Retry while the
            # latch is the reason -- a HAND on the throttle still means the
            # driver is overriding, and for them this engages on the
            # transition frame only, exactly as before.
            or (self._latch_yielding and not self._curve_assist_jake)
        ):
```

The body already guards with `jake_capable`, `worth_the_bark`, and `not t.engine_brake`, so re-running it is idempotent until the throttle drains.

- [ ] **Step 6: Run the file** (same command). Expected: all PASS.

- [ ] **Step 7: Regression** — test-runner: `uv run pytest tests/test_driving_features.py -n 0 -q -p no:cacheprovider` (the curve/jake suites live there). Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/freight_fate/states/driving_updates.py tests/test_pedal_latch_assists.py
git commit -m "feat(driving): curve assist owns the pedal and retries its jake under a latch [skip changelog]"
```

---

### Task 7: The three-way Latching pedals setting (owner revision 2026-08-13 — runs BETWEEN Tasks 4 and 5)

**Files:**
- Modify: `src/freight_fate/settings.py:253-258` (field) and the legacy-coercion block near `:517` (bool migration)
- Modify: `src/freight_fate/states/driving_controls.py` (`_update_pedal_latches` off-check, ~1412) 
- Modify: `src/freight_fate/states/driving_updates.py` (the yield/blend block from Task 2)
- Modify: `src/freight_fate/states/main_menu.py` (~1626/1704: the settings entry becomes a mode cycler like `_toggle_overspeed_warning`, ~1774)
- Test: `tests/test_pedal_latch_assists.py`, plus fix any test that sets `pedal_latch = False`/`True` (`tests/test_pedal_latch.py:181`, settings-menu test at `tests/test_pedal_latch.py:201`)

**Interfaces:**
- Consumes: Task 2's blend block and `_latch_yielding`.
- Produces: `Settings.pedal_latch: str = "assists first"` with values `"assists first" | "latch first" | "off"`; legacy `True → "assists first"`, `False → "off"` in the load-time coercion block (copy the `overspeed_warning` pattern at `settings.py:517-520`). Task 5 reads the mode for its speech gate.

- [ ] **Step 1: Write the failing tests**

```python
def test_latch_first_mode_keeps_the_old_override_meaning(monkeypatch):
    """Owner revision: "latch first" is the pre-change behavior -- a latched
    throttle is a manual override and cruise stands down (stays engaged,
    waiting, while the latch drives the pedal)."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        app.ctx.settings.pedal_latch = "latch first"
        app.ctx.settings.overspeed_warning = "off"
        d.truck.engine_on = True
        d.truck.velocity_mps = 60 / 2.2369362920544
        _latch_throttle(d)
        d._engage_cruise(55.0)

        _drive_frames(d, 2.0)

        assert d._cruise_mph is not None  # engaged, standing down
        assert d._throttle_latch.latched
        assert d.truck.throttle > 0.9  # the latch owns the pedal, old style
        assert not d._latch_yielding
    finally:
        app.shutdown()


def test_legacy_bool_settings_migrate_to_modes():
    from freight_fate.settings import Settings

    s = Settings()
    s.pedal_latch = True
    s.__class__.__dict__  # no-op; keep ruff quiet if unused
    # Run the same load-time coercion path the overspeed migration uses;
    # find the classmethod/function that applies it (settings.py ~517) and
    # call it the way the loader does.
    ...
```

For the migration test, read `settings.py` around line 517 first: write the test the way the existing overspeed bool-migration is tested (grep `tests/` for `overspeed_warning is True` or the loader test) — same mechanism, same test shape, asserting `True → "assists first"` and `False → "off"`. If no such loader test exists, test via the public load path (`Settings.load`/`from_dict`, whatever the loader is named).

- [ ] **Step 2: Run to verify the mode test fails** (env FREIGHT_FATE_NO_SPEECH=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy, `uv run pytest tests/test_pedal_latch_assists.py -n 0 -q -p no:cacheprovider`). Expected: FAIL — with a string value the current `if not self.ctx.settings.pedal_latch` check treats every non-empty mode as latch-enabled, but nothing implements "latch first", so `_latch_yielding` goes True and throttle drains.

- [ ] **Step 3: Implement**

`settings.py` field (keep the existing comment, extend it):

```python
    # Double-tap-and-hold latches the accelerator or brake key so a long
    # pull or a steady snub needs no sustained hold; a fresh press of the
    # same key, the opposite pedal, or any safety override releases it.
    # The same input-accessibility layer as the keeper: presets never
    # touch it. Realism cover: the hand-throttle knob is a real cab control.
    # Modes (owner revision 2026-08-13): "assists first" lets cruise, the
    # speed keeper, and curve assist outrank a latched throttle; "latch
    # first" is the original meaning, the latch as a manual override the
    # assists stand down for; "off" is the plain pedals.
    pedal_latch: str = "assists first"
```

Legacy coercion beside the overspeed one (settings.py ~517):

```python
        if s.pedal_latch is True:
            s.pedal_latch = "assists first"
        elif s.pedal_latch is False:
            s.pedal_latch = "off"
```

`driving_controls.py` off-check: `if not self.ctx.settings.pedal_latch:` becomes `if self.ctx.settings.pedal_latch == "off":`.

`driving_updates.py` blend block — the yield gates on the mode; in "latch first" the latch counts as a hand for the assists:

```python
        latch_mode = self.ctx.settings.pedal_latch
        self._latch_yielding = (
            throttle_latched
            and latch_mode == "assists first"
            and self._speed_authority_engaged()
        )
        key_up = hand_up or (throttle_latched and not self._latch_yielding)
        accelerating = key_up or pad_throttle > 0.05
        # In "latch first" the latch IS the driver insisting on speed, so the
        # assists see it as a hand and stand down -- the original meaning.
        assist_up = hand_up or (throttle_latched and latch_mode == "latch first")
        hand_accelerating = assist_up or pad_throttle > 0.05
```

`main_menu.py`: turn the pedal-latch entry into a three-mode cycler exactly like `_toggle_overspeed_warning` (`modes = ["assists first", "latch first", "off"]`), spoken as `Latching pedals: {mode}`. Match whatever label text the entry uses today.

Fix the two existing tests that assign bools: `tests/test_pedal_latch.py:181` `pedal_latch = False` → `"off"`. (Direct assignment of `True` elsewhere: change to `"assists first"` if any exists.)

- [ ] **Step 4: Run** `uv run pytest tests/test_pedal_latch_assists.py tests/test_pedal_latch.py tests/test_settings_menu.py -n 0 -q -p no:cacheprovider`. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/freight_fate/settings.py src/freight_fate/states/driving_controls.py src/freight_fate/states/driving_updates.py src/freight_fate/states/main_menu.py tests/test_pedal_latch_assists.py tests/test_pedal_latch.py
git commit -m "feat(driving): Latching pedals grows assists-first / latch-first / off modes [skip changelog]"
```

---

### Task 5: The catch line names the authority holding the speed (runs AFTER Task 7)

**Files:**
- Modify: `src/freight_fate/states/driving_controls.py:1423-1432` (the `event == "latched"` branch)
- Modify: `src/freight_fate/states/main_menu.py` (~1626/1704 area) ONLY IF the pedal-latch setting's spoken description claims assists stand down — read it first; if it says nothing contradictory, leave it alone.
- Test: `tests/test_pedal_latch_assists.py`

**Interfaces:**
- Consumes: `self._cruise_mph` / `self._keeper_mph` (already in scope in the mixin).

- [ ] **Step 1: Read `docs/ontology.md`** for the canonical spoken nouns of cruise and the speed keeper. The strings below assume "Adaptive cruise" and "Speed keeper" (matching "Adaptive cruise canceled…" / "Speed keeper canceled…" in `driving_events.py`); if ontology says otherwise, ontology wins and the test strings change with it.

- [ ] **Step 2: Write the failing test**

```python
def test_the_catch_line_names_the_authority_holding_the_speed(monkeypatch):
    """Latching while cruise or the keeper drives must not sound dead."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    spoken = []
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.velocity_mps = 60 / 2.2369362920544
        d._engage_cruise(55.0)

        # The real gesture, so the spoken confirmation path is the one
        # players hear: tap, release, press and hold through the catch.
        held.add(pygame.K_UP)
        _drive_frames(d, 0.2)
        held.discard(pygame.K_UP)
        _drive_frames(d, 0.2)
        held.add(pygame.K_UP)
        _drive_frames(d, 0.8)
        held.discard(pygame.K_UP)

        assert "Throttle latched. Adaptive cruise holds the speed." in spoken
        assert "Throttle latched." not in spoken  # replaced, not doubled
    finally:
        app.shutdown()


def test_a_plain_catch_keeps_its_plain_line(monkeypatch):
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    spoken = []
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        held.add(pygame.K_UP)
        _drive_frames(d, 0.2)
        held.discard(pygame.K_UP)
        _drive_frames(d, 0.2)
        held.add(pygame.K_UP)
        _drive_frames(d, 0.8)
        held.discard(pygame.K_UP)

        assert "Throttle latched." in spoken
    finally:
        app.shutdown()
```

- [ ] **Step 3: Run to verify the first fails** (same command). Expected: FAIL — the line is currently always `"Throttle latched."`.

- [ ] **Step 4: Implement**

In `_update_pedal_latches`, replace the catch confirmation:

```python
            if event == "latched":
                # (existing direction-armed reset and click stay as they are)
                self._direction_armed = ""
                self._direction_hold_s = 0.0
                self.ctx.audio.play("ui/tick", volume=1.0)
                line = f"{name} latched."
                if (
                    latch is self._throttle_latch
                    and self.ctx.settings.pedal_latch == "assists first"
                ):
                    # A latch caught while something smarter is holding the
                    # speed must say who has the pedal, or the gesture feels
                    # dead -- the latch takes over only when they release.
                    # In "latch first" mode the plain line is the truth: the
                    # latch has the pedal and nothing outranks it.
                    if self._cruise_mph is not None:
                        line = "Throttle latched. Adaptive cruise holds the speed."
                    elif self._keeper_mph is not None:
                        line = "Throttle latched. Speed keeper holds the speed."
                self.ctx.say_event(line, interrupt=False)
```

Add a third test beside the two above: same gesture-under-cruise setup as
`test_the_catch_line_names_the_authority_holding_the_speed` but with
`app.ctx.settings.pedal_latch = "latch first"`, asserting `"Throttle
latched."` IS in spoken and the authority line is NOT.

(Curve assist is deliberately omitted: a corner is seconds long and its own cues are already speaking.)

- [ ] **Step 5: Run the file, then the two neighbour suites** — test-runner: `uv run pytest tests/test_pedal_latch_assists.py tests/test_pedal_latch.py tests/test_settings_menu.py -n 0 -q -p no:cacheprovider`. Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/freight_fate/states/driving_controls.py tests/test_pedal_latch_assists.py
git commit -m "feat(speech): latch catch names the authority holding the speed [skip changelog]"
```

(Include `src/freight_fate/states/main_menu.py` in the add if Step 1's read showed the setting description needed the one-line amendment.)

---

### Task 6: Changelog, roadmap, full verification

**Files:**
- Modify: `CHANGELOG.md` (`## Unreleased` → `### Changed`)
- Modify: `ROADMAP.md` (1.9 tester-findings area, near the 2026-08-13 entries)

**Interfaces:** none — paperwork and the wide net.

- [ ] **Step 1: CHANGELOG entry** (spoken by screen readers — player language, no jargon), first bullet under `### Changed`:

```markdown
- **A latched throttle now gets out of the way of the speed assists, and
  the Latching pedals setting lets you choose.** A latched accelerator
  used to read as your hand insisting on speed, so cruise, the speed
  keeper, and curve assistance all stood down and the truck just kept
  accelerating. Latching pedals now has three settings. Assists first,
  the new standard, makes the latch the quietest voice in the cab: any
  speed assist that is holding or shedding speed drives the pedal, and
  the latch takes over again the moment it lets go -- no need to redo
  the latch gesture -- and latching while cruise or the speed keeper is
  active says who is holding the speed. Latch first keeps the old
  meaning, where the latch overrides the assists until a safety system
  steps in. Off keeps the plain pedals for fully manual driving. A key
  you physically hold down still overrides the assists in every mode,
  exactly as before.
```

- [ ] **Step 2: ROADMAP bullet**, beside the other 2026-08-13 entries:

```markdown
- [x] **Pedal latch yields to the speed authorities -- landed 2026-08-13**
      (Brandon latched the throttle for the whole trip expecting the
      assists to drive; every assist read the latch as a manual override
      and stood down). A latched throttle is now the lowest-priority
      speed input: cruise, the speed keeper, and curve assist own the
      pedal while engaged and the latch ramps back in when they release,
      with no re-gesture. Hand-held keys keep manual-override meaning;
      releasing the latch never cancels an assist; the catch line names
      the authority holding the speed. Spec:
      `docs/superpowers/specs/2026-08-13-pedal-latch-assists-design.md`.
```

- [ ] **Step 3: Full verification** — test-runner, three commands: `uv run pytest tests/test_pedal_latch_assists.py tests/test_pedal_latch.py tests/test_driving_features.py -n 0 -q -p no:cacheprovider`, then `uv run pytest -q` (full suite, default xdist), then `uv run ruff check src tests tools` plus `uv run python -m compileall -q src tests tools`. Expected: all green.

- [ ] **Step 4: Commit** (no `[skip changelog]` — this commit carries the entry)

```bash
git add CHANGELOG.md ROADMAP.md
git commit -m "feat(driving): pedal latch yields to speed authorities"
```

---

## Self-Review (done at authoring)

- Spec coverage: meaning change → Tasks 2/4; hard releases untouched → no task edits them, Task 3 pins the brake path; release-never-cancels → Task 3; speech → Task 5; realistic-mode note → CHANGELOG text (Task 6); tests list in spec → every bullet has a named test above.
- Placeholders: none; every step has runnable code or an exact command.
- Type consistency: `_update_pedal_latches` triple `(hand_up, key_down, throttle_latched)` matches between Task 2's implementation and every test that drives `update()`; `_speed_authority_engaged` and `_latch_yielding` names consistent across Tasks 1/2/4.
