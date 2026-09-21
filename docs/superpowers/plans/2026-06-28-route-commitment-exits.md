# Route Commitment Exits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace destination-exit "press X to take the exit" behavior with route-setup-based exit commitment, where speed, lane setup, and signal/intent determine whether the ramp is taken.

**Architecture:** Keep the first implementation slice inside the existing driving state mixins. `DrivingEventMixin` should own the exit-intent state and automatic destination-exit arming; `DrivingControlsMixin` should keep X as the shared pull-over/signal key and update F1 help. Tests evolve the existing focused exit smoke suite before implementation.

**Tech Stack:** Python, pygame event tests, pytest, uv, existing Freight Fate driving state and trip simulation.

---

## File Structure

- Modify `src/freight_fate/states/driving.py`: initialize any new signal/intent fields on `DrivingState`.
- Modify `src/freight_fate/states/driving_events.py`: rename/refine exit arming semantics, auto-arm destination exits, validate signal/intent, and update spoken exit messages.
- Modify `src/freight_fate/states/driving_controls.py`: keep X routing through pull-over first, then signal/intent; update F1 help so it no longer says X takes the exit.
- Modify `tests/test_driving_exits.py`: replace "X takes exit" assumptions with setup-based exit tests; keep ordinary route stop behavior scoped to current implementation.
- Modify `docs/user-manual.md`: update driving controls and road-events text to explain signal/intent and automatic route commitment.
- Optionally modify `ROADMAP.md`: only if implementation changes shipped behavior enough that the roadmap's completed exit item is stale.

Do not split `driving_events.py` in this slice. It is large, but the current plan changes a tightly related existing exit block and should avoid a broad refactor.

## Task 1: Destination Exit Auto-Arms From Route Context

**Files:**
- Modify: `tests/test_driving_exits.py`
- Modify: `src/freight_fate/states/driving_events.py`
- Test: `tests/test_driving_exits.py`

- [ ] **Step 1: Add failing tests for destination exit auto-arming**

Add these tests near the existing exit tests in `tests/test_driving_exits.py`:

```python
@pytest.mark.smoke
def test_destination_exit_auto_arms_and_takes_ramp_with_valid_setup(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.steering_assist = "off"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 15.0

        driving.update(1 / 60)
        assert driving._exit_stop is not None
        assert driving._exit_stop.type == "delivery_destination"

        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)

        assert driving._ramp_mi == pytest.approx(0.5)
        assert driving._destination_exit_taken
        assert any("You take" in line and "destination exit" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_destination_exit_no_longer_requires_x_to_take_ramp(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.steering_assist = "off"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 0.5
        driving.truck.velocity_mps = 12.0

        driving.update(1 / 60)
        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)

        assert driving._ramp_mi == pytest.approx(0.5)
        assert all("Press X to take" not in line for line in spoken)
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_driving_exits.py::test_destination_exit_auto_arms_and_takes_ramp_with_valid_setup tests/test_driving_exits.py::test_destination_exit_no_longer_requires_x_to_take_ramp -q
```

Expected: FAIL because destination exits are not auto-armed unless X calls `_take_exit()`.

- [ ] **Step 3: Auto-arm destination exits in `_check_destination_exit`**

In `src/freight_fate/states/driving_events.py`, update `_check_destination_exit` so it arms destination exits when announced:

```python
    def _check_destination_exit(self) -> None:
        stop = self._destination_exit_stop()
        if stop is None:
            return
        ahead = stop.at_mi - self.trip.position_mi
        if not (0 < ahead <= EXIT_WINDOW_MI):
            return
        key = self._destination_exit_key(stop)
        if key != self._destination_exit_announced_key:
            self._destination_exit_announced_key = key
            message = self._destination_exit_announcement(stop, ahead)
            if self._cruise_mph is not None:
                self._cancel_cruise()
                message += " Adaptive cruise disabled; take manual speed control."
            self.ctx.audio.play("ui/notify", volume=0.7)
            self.ctx.say_event(message, interrupt=False)
        if self._exit_stop is None:
            self._exit_stop = stop
            self._reset_exit_lane_state()
            if self.ctx.settings.steering_assist == "off":
                self._exit_lane_alignment = EXIT_LANE_READY
                self._exit_lane_ready_said = True
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
uv run pytest tests/test_driving_exits.py::test_destination_exit_auto_arms_and_takes_ramp_with_valid_setup tests/test_driving_exits.py::test_destination_exit_no_longer_requires_x_to_take_ramp -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/freight_fate/states/driving_events.py tests/test_driving_exits.py
git commit -m "feat(driving): auto-arm destination exits"
```

## Task 2: Change X From Exit Action To Signal Or Intent

**Files:**
- Modify: `tests/test_driving_exits.py`
- Modify: `src/freight_fate/states/driving.py`
- Modify: `src/freight_fate/states/driving_events.py`
- Test: `tests/test_driving_exits.py`

- [ ] **Step 1: Add failing tests for X signal semantics**

Replace `test_exit_key_is_a_toggle_and_needs_an_exit_nearby` with:

```python
@pytest.mark.smoke
def test_x_signals_for_upcoming_route_exit_without_taking_it(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.steering_assist = "light"
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.5

        driving.handle_event(key_event(pygame.K_x))

        assert driving._exit_stop is not None
        assert driving._exit_stop.type == "delivery_destination"
        assert driving._exit_signal_on
        assert any("Signal on" in line for line in spoken)

        driving.handle_event(key_event(pygame.K_x))

        assert driving._exit_stop is not None
        assert not driving._exit_signal_on
        assert any("Signal canceled" in line for line in spoken)
    finally:
        app.shutdown()
```

Add this test after it:

```python
@pytest.mark.smoke
def test_x_without_route_exit_reports_no_signal_target(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.position_mi = 0.0
        if driving._destination_exit_stop() is not None:
            pytest.skip("route starts close to a destination exit")

        driving.handle_event(key_event(pygame.K_x))

        assert not driving._exit_signal_on
        assert any("No route exit to signal for yet" in line for line in spoken)
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_driving_exits.py::test_x_signals_for_upcoming_route_exit_without_taking_it tests/test_driving_exits.py::test_x_without_route_exit_reports_no_signal_target -q
```

Expected: FAIL because `_exit_signal_on` does not exist and X currently toggles `_exit_stop`.

- [ ] **Step 3: Initialize signal state**

In `src/freight_fate/states/driving.py`, add this field next to the existing exit fields:

```python
        self._exit_signal_on = False
```

- [ ] **Step 4: Replace `_take_exit` with signal intent behavior**

In `src/freight_fate/states/driving_events.py`, replace `_take_exit` with:

```python
    def _take_exit(self) -> None:
        self._toggle_exit_signal()

    def _toggle_exit_signal(self) -> None:
        if self._ramp_mi is not None:
            self.ctx.say("You are already on the exit ramp. Brake to a stop.")
            return
        stop = self._exit_stop or self._upcoming_exit_stop()
        if stop is None:
            self.ctx.say("No route exit to signal for yet. Exits are announced as you approach them.")
            return
        self._exit_stop = stop
        self._exit_signal_on = not self._exit_signal_on
        ahead = stop.at_mi - self.trip.position_mi
        if not self._exit_signal_on:
            self.ctx.say("Signal canceled. Keep following the highway.")
            return
        self.ctx.audio.play("ui/notify", volume=0.5)
        if stop.type == "delivery_destination":
            head = f"Signal on for {self._destination_exit_phrase(stop)}, destination exit for {stop.name},"
        elif stop.exit_label:
            head = f"Signal on for {stop.exit_label}, {stop.spoken_name},"
        else:
            head = f"Signal on for the {stop.spoken_name} exit,"
        if self.ctx.settings.steering_assist == "off":
            self._exit_lane_alignment = EXIT_LANE_READY
            self._exit_lane_ready_said = True
            self.ctx.audio.play("ui/notify", volume=0.6)
            self.ctx.say(
                f"{head} {ahead:.1f} miles ahead. Exit lane set. "
                f"Slow to {RAMP_MAX_MPH:.0f} or less for the ramp."
            )
            return
        self.ctx.say(
            f"{head} {ahead:.1f} miles ahead. Move right for the exit lane, "
            f"then slow to {RAMP_MAX_MPH:.0f} or less for the ramp."
        )
```

Update `_reset_exit_lane_state` so it does not cancel `_exit_signal_on`; lane reset and signal cancellation are separate concepts. In `_update_exit`, after any miss or successful ramp entry, set:

```python
            self._exit_signal_on = False
```

Use that assignment in each branch that clears the active exit: missed gore window, missed lane, successful ramp entry, and too-fast miss.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
uv run pytest tests/test_driving_exits.py::test_x_signals_for_upcoming_route_exit_without_taking_it tests/test_driving_exits.py::test_x_without_route_exit_reports_no_signal_target -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/freight_fate/states/driving.py src/freight_fate/states/driving_events.py tests/test_driving_exits.py
git commit -m "feat(driving): make exit key a signal"
```

## Task 3: Require Signal Or Inferred Intent In Realistic Mode

**Files:**
- Modify: `tests/test_driving_exits.py`
- Modify: `src/freight_fate/states/driving_events.py`
- Test: `tests/test_driving_exits.py`

- [ ] **Step 1: Add failing tests for signal requirement and relaxed inference**

Add:

```python
@pytest.mark.smoke
def test_realistic_lane_drift_requires_signal_for_destination_exit(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.steering_assist = "light"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 12.0
        driving._exit_lane_alignment = 1.0
        driving.update(1 / 60)

        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)

        assert driving._ramp_mi is None
        assert any("signal was not set" in line for line in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_relaxed_lane_drift_infers_destination_exit_intent(monkeypatch):
    from freight_fate.app import App

    spoken = []
    app = App()
    app.ctx.settings.steering_assist = "off"
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving._destination_exit_stop()
        assert stop is not None
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 12.0
        driving.update(1 / 60)

        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)

        assert driving._ramp_mi == pytest.approx(0.5)
        assert any("You take" in line for line in spoken)
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_driving_exits.py::test_realistic_lane_drift_requires_signal_for_destination_exit tests/test_driving_exits.py::test_relaxed_lane_drift_infers_destination_exit_intent -q
```

Expected: first test FAILS because lane readiness is enough today; second test may already pass after Task 1, but keep it as regression coverage.

- [ ] **Step 3: Add route-commitment helper**

In `src/freight_fate/states/driving_events.py`, add this helper above `_update_exit`:

```python
    def _exit_intent_ready(self, stop) -> bool:
        if self._exit_signal_on:
            return True
        if stop.type == "delivery_destination" and self.ctx.settings.steering_assist == "off":
            return True
        return False
```

In `_update_exit`, before the lane-ready check, add:

```python
        if not self._exit_intent_ready(stop):
            self._reset_exit_lane_state()
            self._exit_signal_on = False
            place = (
                self._destination_exit_phrase(stop)
                if stop.type == "delivery_destination"
                else stop.spoken_name
            )
            self.ctx.say_event(
                f"You missed {place}: the turn signal was not set. "
                "Stay on the highway and recover at the next safe exit."
            )
            return
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
uv run pytest tests/test_driving_exits.py::test_realistic_lane_drift_requires_signal_for_destination_exit tests/test_driving_exits.py::test_relaxed_lane_drift_infers_destination_exit_intent -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/freight_fate/states/driving_events.py tests/test_driving_exits.py
git commit -m "feat(driving): require exit intent in realistic lane mode"
```

## Task 4: Update Spoken Help And Player Documentation

**Files:**
- Modify: `tests/test_info_keys.py`
- Modify: `tests/test_controls_reference.py`
- Modify: `src/freight_fate/states/driving_controls.py`
- Modify: `src/freight_fate/states/main_menu_help.py`
- Modify: `docs/user-manual.md`
- Test: `tests/test_info_keys.py`, `tests/test_controls_reference.py`, `tests/test_manual_html.py`

- [ ] **Step 1: Add failing text-regression tests**

In `tests/test_info_keys.py`, add:

```python
def test_driving_help_describes_x_as_signal_not_take_exit(monkeypatch):
    from freight_fate.app import App
    from driving_feature_helpers import key_event, quiet_trip, start_drive

    spoken = []
    app = App()
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.handle_event(key_event(pygame.K_F1))

        help_text = spoken[-1]
        assert "X signals for the next announced route exit" in help_text
        assert "X takes the next announced exit" not in help_text
    finally:
        app.shutdown()
```

In `tests/test_controls_reference.py`, update the existing driving-controls expectations so the X row expects signal wording:

```python
assert any("X" in line and "signal" in line.lower() for line in lines)
assert all("X takes the next announced exit" not in line for line in lines)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_info_keys.py::test_driving_help_describes_x_as_signal_not_take_exit tests/test_controls_reference.py -q
```

Expected: FAIL because F1 and help still say X takes the exit.

- [ ] **Step 3: Update F1 help**

In `src/freight_fate/states/driving_controls.py`, replace the X help sentence with:

```python
                "X signals for the next announced route exit or cancels that "
                "signal. Prepare early: slow to 45 for the ramp, hold the exit "
                "lane when lane drift is enabled, and the truck takes the ramp "
                "when your setup is valid. "
                "X also signals a pull-over if a trooper "
```

- [ ] **Step 4: Update built-in help and manual**

In `src/freight_fate/states/main_menu_help.py`, update any driving-controls line that says X takes an exit so it says:

```python
"X signals for the next announced route exit or cancels that signal."
```

In `docs/user-manual.md`, update:

```markdown
| X | Signal for or cancel the next announced route exit. The truck takes the ramp when speed, lane setup, and route intent are valid. |
```

Also update the Road Events exit paragraph so it no longer says "Press X to signal for the exit" as a required take-exit action. Use:

```markdown
As an announced exit approaches, use X to signal or cancel your intent, slow to 45 miles per hour or less, and set up the exit lane when lane drift is enabled. If your speed, lane setup, and route intent are valid at the marker, the truck takes the ramp automatically.
```

- [ ] **Step 5: Run focused docs/help tests**

Run:

```powershell
uv run pytest tests/test_info_keys.py::test_driving_help_describes_x_as_signal_not_take_exit tests/test_controls_reference.py tests/test_manual_html.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/freight_fate/states/driving_controls.py src/freight_fate/states/main_menu_help.py docs/user-manual.md tests/test_info_keys.py tests/test_controls_reference.py
git commit -m "docs: explain route-based exit commitment"
```

## Task 5: Verification And Accessibility Pass

**Files:**
- Modify only if verification finds a real defect.
- Test: focused exit/help tests plus full suite.

- [ ] **Step 1: Run focused exit and speech tests**

Run:

```powershell
uv run pytest tests/test_driving_exits.py tests/test_info_keys.py tests/test_controls_reference.py tests/test_manual_html.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full suite with tooling dependencies**

Run:

```powershell
uv sync --group dev --group tooling
uv run pytest -q
```

Expected: PASS. If existing unrelated failures appear, document exact tests and root cause before deciding whether they belong to this slice.

- [ ] **Step 3: Run desktop accessibility review**

Review changed speech and keyboard behavior against the desktop accessibility checklist:

```text
Scope:
- X remains keyboard reachable.
- Pull-over X behavior remains prioritized when a trooper stop is active.
- Destination-exit guidance is spoken through GPS/event speech.
- Missed-exit reasons are spoken: missing signal, bad lane, too fast, or missed window.
- F1 and built-in help describe the new behavior.
- Relaxed mode remains more forgiving and does not create a silent dead-end.
```

Expected: no critical or major accessibility findings.

- [ ] **Step 4: Manual smoke scenario**

Run a short destination-exit smoke in the app or with the existing smoke harness:

```powershell
uv run pytest tests/test_driving_exits.py::test_destination_exit_auto_arms_and_takes_ramp_with_valid_setup -q
```

Expected: PASS, with spoken event text confirming the destination exit is taken after valid setup.

- [ ] **Step 5: Final commit if verification required fixes**

If Step 2 or Step 3 required any changes, commit them:

```powershell
git add src/freight_fate/states/driving.py src/freight_fate/states/driving_events.py src/freight_fate/states/driving_controls.py src/freight_fate/states/main_menu_help.py docs/user-manual.md tests/test_driving_exits.py tests/test_info_keys.py tests/test_controls_reference.py
git commit -m "fix(driving): polish route exit commitment"
```

If no changes were needed, do not create an empty commit.

## Self-Review

Spec coverage:

- Speed planning and route context are covered by requiring valid speed/lane/intent at the destination exit.
- Route commitment and X-as-signal are covered directly in Tasks 1-4.
- Realistic vs relaxed mode is covered by Task 3.
- Accessibility and spoken feedback are covered by Tasks 4-5.
- Powertrain, broader routing, trailer awareness, ordinary route stops, weigh stations, local turns, and facility gates are intentionally out of scope for this first slice.

Placeholder scan:

- No TBD/TODO placeholders.
- Each task has exact files, commands, expected outcomes, and code snippets for the relevant changes.

Type consistency:

- New state field is `_exit_signal_on`.
- New helper is `_exit_intent_ready(self, stop)`.
- Existing `_take_exit()` remains the control entry point for X and delegates to `_toggle_exit_signal()`.
