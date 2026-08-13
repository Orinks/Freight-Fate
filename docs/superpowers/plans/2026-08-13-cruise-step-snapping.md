# Cruise Step Snapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plain +/- snaps the cruise target to the fives grid; Ctrl with +/- steps by exactly 1 mph — per `docs/superpowers/specs/2026-08-13-cruise-step-snapping-design.md`.

**Architecture:** A pure module function `cruise_step_target(target_mph, direction, fine)` in driving_core.py owns the arithmetic; `_adjust_cruise` changes signature from a raw delta to `(direction, *, fine=False)` and calls it; the keyboard handler reads Ctrl the way the radio bindings do, the controller keeps coarse steps.

**Tech Stack:** Python 3.12, pygame (headless tests), pytest via `uv run`.

## Global Constraints

- All pytest invocations go through the **test-runner agent**; commands run with env `FREIGHT_FATE_NO_SPEECH=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` and `-n 0 -q -p no:cacheprovider` (serial) unless a step says otherwise. NEVER bare `uv run pytest` or `-n auto` from an implementer.
- The fine modifier is **Ctrl** (`pygame.KMOD_CTRL`), never Shift — on US layouts the main-row plus IS Shift+equals, so Shift cannot be a modifier for these keys. Shift+K (resume cruise) is untouched.
- Use the existing constants `CRUISE_STEP_MPH`, `CRUISE_MIN_MPH`, `CRUISE_MAX_MPH` — no new literals for bounds or grid.
- Spoken text unchanged except the F1 help clause named in Task 2; player language per `docs/ontology.md`.
- Intermediate commits touching `src/` carry `[skip changelog]`; Task 3 adds the real CHANGELOG entry.
- `uv run ruff check src tests` before each commit; pre-commit may reformat — re-stage and commit again.
- Match surrounding idiom (prose why-comments).

## File Structure

- `src/freight_fate/states/driving_core.py` — add `cruise_step_target` beside `CRUISE_STEP_MPH` (~line 341).
- `src/freight_fate/states/driving_events.py:2473-2506` — `_adjust_cruise` signature and body.
- `src/freight_fate/states/driving_controls.py:83-89` (keyboard), `:546-548` (pad), F1 help text (~:280 and ~:396).
- `tests/test_cruise_steps.py` — new file for the helper + key-path tests.
- `tests/test_driving_cruise_weather.py:256-275`, `tests/test_driving_features.py:2211-2216` — existing callers of the old signature, updated.

---

### Task 1: The pure step function

**Files:**
- Modify: `src/freight_fate/states/driving_core.py` (beside `CRUISE_STEP_MPH`, ~341)
- Test: `tests/test_cruise_steps.py` (create)

**Interfaces:**
- Produces: `cruise_step_target(target_mph: float, direction: int, fine: bool) -> float` — module function in `driving_core.py`, exported via the module's existing star-import surface (driving_core has no `__all__`; the state modules `from .driving_core import *`). Task 2 calls it from `_adjust_cruise`.

- [ ] **Step 1: Write the failing tests**

```python
"""Cruise target stepping: plain steps snap to the fives, Ctrl steps by one.

Tester context (owner-approved design 2026-08-13): K captures the exact
current speed, so a cruise set at 32 used to step 37, 42 -- never landing
on the fives. Jerry latched the throttle and raced K to catch an even 35;
Sarah pointed at her dad's cruise stalk, which snaps. Plain steps now walk
the fives grid from wherever the target sits, and Ctrl with the same keys
moves by exactly one for the players who need a precise number.
"""

import pytest

from freight_fate.states.driving_core import (
    CRUISE_MAX_MPH,
    CRUISE_MIN_MPH,
    cruise_step_target,
)


def test_off_grid_snaps_up_to_the_next_five():
    assert cruise_step_target(32.0, 1, False) == pytest.approx(35.0)


def test_on_grid_steps_a_full_five_up():
    assert cruise_step_target(35.0, 1, False) == pytest.approx(40.0)


def test_off_grid_snaps_down_to_the_previous_five():
    assert cruise_step_target(32.0, -1, False) == pytest.approx(30.0)


def test_on_grid_steps_a_full_five_down():
    assert cruise_step_target(30.0, -1, False) == pytest.approx(25.0)


def test_float_fuzz_on_the_grid_still_moves_a_full_step():
    # A target that is 35 minus one part in a billion must behave as 35:
    # snapping it "up to 35" would be a no-op tap, the old complaint again.
    assert cruise_step_target(35.0 - 1e-9, 1, False) == pytest.approx(40.0)
    assert cruise_step_target(35.0 + 1e-9, -1, False) == pytest.approx(30.0)


def test_fine_steps_move_by_exactly_one():
    assert cruise_step_target(35.0, 1, True) == pytest.approx(36.0)
    assert cruise_step_target(35.0, -1, True) == pytest.approx(34.0)
    assert cruise_step_target(32.0, 1, True) == pytest.approx(33.0)


def test_both_step_kinds_clamp_to_the_bounds():
    assert cruise_step_target(CRUISE_MAX_MPH, 1, False) == pytest.approx(CRUISE_MAX_MPH)
    assert cruise_step_target(CRUISE_MAX_MPH, 1, True) == pytest.approx(CRUISE_MAX_MPH)
    assert cruise_step_target(CRUISE_MIN_MPH, -1, False) == pytest.approx(CRUISE_MIN_MPH)
    assert cruise_step_target(CRUISE_MIN_MPH, -1, True) == pytest.approx(CRUISE_MIN_MPH)
```

- [ ] **Step 2: Run to verify failure** — test-runner: `uv run pytest tests/test_cruise_steps.py -n 0 -q -p no:cacheprovider` (env per Global Constraints). Expected: FAIL, `ImportError: cannot import name 'cruise_step_target'`.

- [ ] **Step 3: Implement** in `driving_core.py`, directly under `CRUISE_STEP_MPH`/`CRUISE_MAX_MPH` (`math` is already imported there; if not, add it):

```python
def cruise_step_target(target_mph: float, direction: int, fine: bool) -> float:
    """The next cruise set point from a +/- tap.

    Plain taps walk the fives grid the way a real cruise stalk does: an
    off-grid target (K captures the exact road speed, so 32 happens all
    the time) snaps outward to the next multiple, healing itself in one
    press instead of stepping 37, 42 forever (testers Jerry and Sarah,
    2026-08-13). Ctrl taps move by exactly one for the players who need
    a precise number and cannot feather K onto it. The epsilon keeps a
    float a hair off the grid from turning a tap into a no-op snap.
    """
    if fine:
        stepped = target_mph + direction
    elif direction > 0:
        notches = math.floor(target_mph / CRUISE_STEP_MPH + 1e-9)
        stepped = (notches + 1) * CRUISE_STEP_MPH
    else:
        notches = math.ceil(target_mph / CRUISE_STEP_MPH - 1e-9)
        stepped = (notches - 1) * CRUISE_STEP_MPH
    return max(CRUISE_MIN_MPH, min(CRUISE_MAX_MPH, stepped))
```

- [ ] **Step 4: Run to verify pass** (same command). Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/freight_fate/states/driving_core.py tests/test_cruise_steps.py
git commit -m "feat(driving): cruise step arithmetic snaps to fives, fine steps by one [skip changelog]"
```

---

### Task 2: Wire the keys, the pad, and the help line

**Files:**
- Modify: `src/freight_fate/states/driving_events.py:2473-2506` (`_adjust_cruise`)
- Modify: `src/freight_fate/states/driving_controls.py:83-89` (keyboard), `:546-548` (pad), and the two F1 help sentences (search `driving_controls.py` for `cruise target by five`)
- Modify: `tests/test_driving_cruise_weather.py` (~256-275) and `tests/test_driving_features.py` (~2211-2216) — old-signature callers
- Test: `tests/test_cruise_steps.py`

**Interfaces:**
- Consumes: `cruise_step_target` from Task 1.
- Produces: `_adjust_cruise(self, direction: int, *, fine: bool = False) -> None` — direction is +1/-1, no longer a mph delta. All callers updated in this task; nothing else may keep passing deltas.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_cruise_steps.py`; copy the FakeKeys-free event pattern from `tests/test_lane_return_gap.py::test_the_l_key_speaks_the_lane_readout` for keydown events, and the App scaffolding from the same file's `_driving` or `driving_feature_helpers.start_drive` — read both first and use whichever the cruise tests in `tests/test_driving_cruise_weather.py:256` already use):

```python
def _cruise_at(driving, mph):
    driving.truck.engine_on = True
    driving.truck.velocity_mps = mph / 2.2369362920544
    driving._engage_cruise(mph)


def test_plus_key_snaps_an_off_grid_cruise_target(monkeypatch):
    import pygame

    from freight_fate.app import App
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive
    from speech_capture import speech_stub

    app = App()
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        _cruise_at(d, 32.0)

        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_EQUALS, mod=0, unicode="="))
        assert d._cruise_mph == pytest.approx(35.0)
        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_EQUALS, mod=0, unicode="="))
        assert d._cruise_mph == pytest.approx(40.0)
    finally:
        app.shutdown()


def test_ctrl_plus_and_minus_step_by_one(monkeypatch):
    import pygame

    from freight_fate.app import App
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive
    from speech_capture import speech_stub

    app = App()
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        _cruise_at(d, 35.0)

        d.handle_event(
            pygame.event.Event(
                pygame.KEYDOWN, key=pygame.K_EQUALS, mod=pygame.KMOD_CTRL, unicode=""
            )
        )
        assert d._cruise_mph == pytest.approx(36.0)
        d.handle_event(
            pygame.event.Event(
                pygame.KEYDOWN, key=pygame.K_MINUS, mod=pygame.KMOD_CTRL, unicode=""
            )
        )
        assert d._cruise_mph == pytest.approx(35.0)
    finally:
        app.shutdown()
```

Also add (same file, same scaffolding — full bodies, not sketches):
- `test_keeper_zone_adjust_snaps_the_resume_target`: engage the keeper the way `tests/test_pedal_latch_assists.py::test_keeper_holds_a_zone_speed_under_a_latched_throttle` does (Zone + `_engage_keeper`), set `d._speed_control_target_mph = 62.0`, send a plain plus keydown, assert `d._speed_control_target_mph == pytest.approx(65.0)` and the keeper's own `_keeper_mph` unchanged.
- `test_high_idle_still_owns_the_keys_when_parked`: follow the existing high-idle test if one exists (grep `high_idle` in tests/); parked with `t.high_idle_rpm` set and allowed, send plus, assert idle RPM stepped and `_cruise_mph`/`_speed_control_target_mph` untouched.

- [ ] **Step 2: Run to verify the new tests fail** (same command; the two existing-caller files are NOT run yet). Expected: FAIL — plus from 32 lands on 37 under the old flat delta.

- [ ] **Step 3: Implement**

`driving_events.py` — signature and target line (docstring's first line gains the grid sentence; speech below stays byte-identical):

```python
    def _adjust_cruise(self, direction: int, *, fine: bool = False) -> None:
        """Raise or lower the cruise set point -- the Accel/Coast (+/-) buttons.

        Plain taps walk the fives grid (an off-grid captured speed heals on
        the first press); Ctrl taps move by exactly one mile per hour. While
        the speed keeper is handling a restricted zone, the same buttons
        adjust the open-road target that adaptive cruise will resume. Parked
        with high idle latched, they step the idle setpoint instead."""
        t = self.truck
        if t.high_idle_rpm is not None and t.high_idle_allowed:
            step = HIGH_IDLE_STEP_RPM if direction > 0 else -HIGH_IDLE_STEP_RPM
            t.high_idle_rpm = max(HIGH_IDLE_MIN_RPM, min(HIGH_IDLE_MAX_RPM, t.high_idle_rpm + step))
            self.ctx.say(f"High idle {t.high_idle_rpm:.0f} RPM.")
            return
        if self._cruise_mph is None and self._keeper_mph is None:
            self.ctx.say("Adaptive cruise is off. Press K to set it first.")
            return
        base = self._speed_control_target_mph
        if base is None:
            limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
            base = max(CRUISE_MIN_MPH, limit)
        target = cruise_step_target(base, direction, fine)
        self._speed_control_target_mph = target
```

(The rest of the method from `if self._cruise_mph is not None:` onward is unchanged.)

`driving_controls.py:83-89` keyboard handler:

```python
        elif (
            key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS)
            or getattr(event, "unicode", "") == "+"
        ):
            self._adjust_cruise(1, fine=bool(getattr(event, "mod", 0) & pygame.KMOD_CTRL))
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS) or getattr(event, "unicode", "") == "-":
            self._adjust_cruise(-1, fine=bool(getattr(event, "mod", 0) & pygame.KMOD_CTRL))
```

Pad handler at `:546-548`: `self._adjust_cruise(-1)` / `self._adjust_cruise(1)` (coarse — a pad has no Ctrl).

F1 help: find the sentence containing `cruise target by five` (two spots, keyboard ~:280 region and controller ~:396) and extend the KEYBOARD one with: `Control with plus or minus moves it by one mile per hour.` The controller sentence stays as it is.

Update the two old-signature callers: `tests/test_driving_features.py:2211,2216` `driving._adjust_cruise(-5.0)` → `driving._adjust_cruise(-1)`. In `tests/test_driving_cruise_weather.py` (~256-275) the assertions use `base + CRUISE_STEP_MPH` — read the test; if `base` there is a multiple of 5 the assertions still hold with snapping and only the call sites' arguments change (`_adjust_cruise(1)` style, or keydown events if that is what it sends); if base is off-grid, update the expected values to the snapped ones and say so in your report.

- [ ] **Step 4: Run** — test-runner: `uv run pytest tests/test_cruise_steps.py tests/test_driving_cruise_weather.py tests/test_driving_features.py -n 0 -q -p no:cacheprovider`. Expected: all pass.

- [ ] **Step 5: Grep guard** — `grep -rn "_adjust_cruise(" src tests` must show only `direction`-style calls (`1`, `-1`, with optional `fine=`); any remaining mph-delta call is a missed site — fix it.

- [ ] **Step 6: Commit**

```bash
git add src/freight_fate/states/driving_events.py src/freight_fate/states/driving_controls.py tests/test_cruise_steps.py tests/test_driving_cruise_weather.py tests/test_driving_features.py
git commit -m "feat(driving): plus and minus snap cruise to the fives, Ctrl steps by one [skip changelog]"
```

---

### Task 3: Changelog, roadmap, full verification

**Files:**
- Modify: `CHANGELOG.md` (`## Unreleased` → `### Changed`, first bullet)
- Modify: `ROADMAP.md` (beside the other `landed 2026-08-13` entries)

**Interfaces:** none — paperwork and the wide net.

- [ ] **Step 1: CHANGELOG bullet** (screen-reader audience, verbatim):

```markdown
- **Cruise speed now steps onto the fives, with a fine step when you need
  an exact number.** Setting cruise captures your exact speed, so a
  target like 32 used to step to 37, then 42 -- never landing on the
  fives. Plus and minus now snap to the next five first, the way a real
  cruise stalk does: from 32, plus gives you 35, then 40. And holding
  Control with plus or minus changes the target by exactly one mile per
  hour, for picking a precise number without having to catch it on the
  speedometer. The controller's cruise buttons step by fives the same
  way.
```

- [ ] **Step 2: ROADMAP bullet**, beside the 2026-08-13 entries:

```markdown
- [x] **Cruise steps snap to the fives; Ctrl steps by one -- landed
      2026-08-13** (Jerry's latch-and-race-K workaround for catching an
      even 35; Sarah's real-stalk snapping). Plain plus/minus walks the
      fives grid from wherever K captured the target, healing off-grid
      speeds in one tap; Ctrl with the same keys moves by exactly 1 mph
      (Ctrl, not Shift -- the main-row plus IS Shift+equals). Pad cruise
      buttons stay coarse. Spec:
      `docs/superpowers/specs/2026-08-13-cruise-step-snapping-design.md`.
```

- [ ] **Step 3: Foreign-edit guard** — before staging, `git diff CHANGELOG.md ROADMAP.md` must show only your edits; other people commit to this branch. If there are foreign modifications, report BLOCKED.

- [ ] **Step 4: Full verification** — test-runner, in order: `uv run pytest tests/test_cruise_steps.py tests/test_driving_cruise_weather.py tests/test_driving_features.py tests/test_pedal_latch_assists.py -n 0 -q -p no:cacheprovider`; then `uv run pytest -q` (full suite, exactly once, default config); then `uv run ruff check src tests tools` and `uv run python -m compileall -q src tests tools`. Unrelated pre-existing failures get reported, not fixed.

- [ ] **Step 5: Commit** (no `[skip changelog]` — this commit carries the entry)

```bash
git add CHANGELOG.md ROADMAP.md
git commit -m "feat(driving): cruise steps snap to fives, Ctrl steps by one"
```

---

## Self-Review (done at authoring)

- Spec coverage: snapping → Tasks 1-2; Ctrl fine step → Tasks 1-2; clamping → Task 1; keeper resume target → Task 2 test; high idle untouched → Task 2 test; pad coarse → Task 2; help copy → Task 2; mph grid → constants only; changelog/roadmap → Task 3.
- Placeholders: the two named-but-sketched tests in Task 2 Step 1 carry exact setup pointers (which test to copy, which values to assert) — acceptable as they pin repo-discovered scaffolding the plan cannot know verbatim; everything else is complete code.
- Type consistency: `cruise_step_target(target_mph, direction, fine)` matches between Task 1's implementation, Task 2's `_adjust_cruise` body, and every test; `_adjust_cruise(direction, *, fine=False)` consistent across handler edits and test updates.
