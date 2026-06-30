# HOS Regulations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement sleeper-berth split rest for both player HOS modes while shaping the HOS ledger for later cycle-limit, restart, adverse-condition, and short-haul work.

**Architecture:** Extend `HosClock` with compact duty/rest history entries and split-rest evaluation, keeping the current counters as the public enforcement surface. Add sleeper-berth menu choices at sleep-capable stops and reuse existing spoken summaries so players understand pending and completed split credit.

**Tech Stack:** Python dataclasses, pygame menu states, existing pytest suite, Freight Fate playtest harness.

---

## File Structure

- Modify `src/freight_fate/sim/hos.py`: add history entries, split-rest constants, split evaluation, serialization, summary text, and fatigue helper.
- Modify `src/freight_fate/states/driving_rest_states.py`: add 2/3/7/8-hour sleeper-berth choices at stops with `sleep`, wire rest actions to `HosClock.sleeper_split_rest`, and speak clear outcomes.
- Modify `src/freight_fate/states/driving_controls.py`: keep HOS status readable when a split is pending or completed through `HosClock.summary`.
- Modify `src/freight_fate/states/main_menu_help.py` and `docs/user-manual.md`: explain sleeper berth, split choices, and the fact that sleep-capable parking is enough because the berth is in the cab.
- Modify `tests/test_hos.py`: add unit and smoke coverage for split-rest rules, menu choices, serialization, and player-facing summaries.

## Task 1: HOS History And Split Rules

**Files:**
- Modify: `src/freight_fate/sim/hos.py`
- Test: `tests/test_hos.py`

- [ ] **Step 1: Write failing tests for valid split pairs**

Add these tests near the HOS clock tests in `tests/test_hos.py`:

```python
def test_eight_two_sleeper_split_restores_time_without_full_reset():
    c = HosClock()
    c.drive(300)
    c.sleeper_split_rest(480)
    c.drive(300)
    c.sleeper_split_rest(120)

    assert c.driving_min == pytest.approx(300)
    assert c.duty_min == pytest.approx(300)
    assert c.since_break_min == 0
    assert c.status == "sleeper_berth"
    assert c.split_pending_summary() is None


def test_seven_three_sleeper_split_restores_time_without_full_reset():
    c = HosClock()
    c.drive(240)
    c.sleeper_split_rest(420)
    c.on_duty(60)
    c.drive(180)
    c.sleeper_split_rest(180)

    assert c.driving_min == pytest.approx(240)
    assert c.duty_min == pytest.approx(300)
    assert c.since_break_min == 0
    assert c.split_pending_summary() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hos.py::test_eight_two_sleeper_split_restores_time_without_full_reset tests/test_hos.py::test_seven_three_sleeper_split_restores_time_without_full_reset -q`

Expected: FAIL because `HosClock` has no `sleeper_split_rest` or `split_pending_summary`.

- [ ] **Step 3: Implement history entries and split evaluation**

In `src/freight_fate/sim/hos.py`, add constants and a dataclass after `DUTY_STATUSES`:

```python
SPLIT_SHORT_MIN = 120.0
SPLIT_SHORT_ALT_MIN = 180.0
SPLIT_LONG_MIN = 420.0
SPLIT_LONG_ALT_MIN = 480.0
HOS_HISTORY_MAX = 96


@dataclass
class HosEvent:
    status: str
    minutes: float
    drive_before: float
    duty_before: float
    since_break_before: float
    source: str = "normal"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "minutes": self.minutes,
            "drive_before": self.drive_before,
            "duty_before": self.duty_before,
            "since_break_before": self.since_break_before,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data) -> "HosEvent | None":
        if not isinstance(data, dict):
            return None
        try:
            status = str(data.get("status", "off_duty"))
            if status not in DUTY_STATUSES:
                return None
            return cls(
                status=status,
                minutes=float(data.get("minutes", 0.0)),
                drive_before=float(data.get("drive_before", 0.0)),
                duty_before=float(data.get("duty_before", 0.0)),
                since_break_before=float(data.get("since_break_before", 0.0)),
                source=str(data.get("source", "normal")),
            )
        except (TypeError, ValueError):
            return None
```

Add fields to `HosClock`:

```python
    history: list[HosEvent] = field(default_factory=list)
    split_credit_key: str | None = None
```

Add helpers inside `HosClock`:

```python
    def _record_event(self, status: str, minutes: float, source: str = "normal") -> None:
        self.history.append(HosEvent(
            status=status,
            minutes=minutes,
            drive_before=self.driving_min,
            duty_before=self.duty_min,
            since_break_before=self.since_break_min,
            source=source,
        ))
        self.history = self.history[-HOS_HISTORY_MAX:]

    def _split_event_key(self, first: HosEvent, second: HosEvent) -> str:
        return f"{id(first)}:{id(second)}:{first.minutes:.0f}:{second.minutes:.0f}"

    def _qualifying_split_pair(self) -> tuple[HosEvent, HosEvent] | None:
        rest_events = [
            e for e in self.history
            if e.source == "normal"
            and e.status in {"off_duty", "sleeper_berth"}
            and e.minutes >= SPLIT_SHORT_MIN
        ]
        for first, second in zip(rest_events, rest_events[1:]):
            total = first.minutes + second.minutes
            if total < SLEEP_MIN:
                continue
            long_event = first if first.minutes >= second.minutes else second
            short_event = second if long_event is first else first
            if long_event.status != "sleeper_berth":
                continue
            if long_event.minutes >= SPLIT_LONG_ALT_MIN and short_event.minutes >= SPLIT_SHORT_MIN:
                return first, second
            if long_event.minutes >= SPLIT_LONG_MIN and short_event.minutes >= SPLIT_SHORT_ALT_MIN:
                return first, second
        return None

    def _apply_split_credit(self) -> None:
        pair = self._qualifying_split_pair()
        if pair is None:
            return
        first, second = pair
        key = self._split_event_key(first, second)
        if self.split_credit_key == key:
            return
        self.driving_min = max(0.0, self.driving_min - first.drive_before)
        self.duty_min = max(0.0, self.duty_min - first.duty_before - first.minutes - second.minutes)
        self.since_break_min = 0.0
        self.split_credit_key = key
        self.warned = [w for w in self.warned if not w.startswith(("drive:", "duty:", "break:"))]

    def sleeper_split_rest(self, minutes: float, source: str = "normal") -> bool:
        minutes = _positive_minutes(minutes)
        self._record_event("sleeper_berth", minutes, source=source)
        self.duty_min += minutes
        self.status = "sleeper_berth"
        self._record_non_driving(minutes)
        self.off_duty_min += minutes
        if self.off_duty_min >= SLEEP_MIN:
            self.sleep(status="sleeper_berth")
            return False
        before_key = self.split_credit_key
        self._apply_split_credit()
        return self.split_credit_key != before_key
```

Update existing `drive`, `on_duty`, `off_duty`, `sleeper`, and `sleep` methods to call `_record_event` before mutating counters. Use `source="full_reset"` for `sleep()` and clear `split_credit_key` during a full reset.

- [ ] **Step 4: Run tests to verify valid pairs pass**

Run: `uv run pytest tests/test_hos.py::test_eight_two_sleeper_split_restores_time_without_full_reset tests/test_hos.py::test_seven_three_sleeper_split_restores_time_without_full_reset -q`

Expected: PASS.

- [ ] **Step 5: Write failing tests for invalid split and pending summary**

Add:

```python
def test_split_long_period_must_be_sleeper_berth():
    c = HosClock()
    c.drive(300)
    c.off_duty(480)
    c.drive(60)
    completed = c.sleeper_split_rest(120)

    assert completed is False
    assert c.driving_min == pytest.approx(360)
    assert c.duty_min == pytest.approx(960)


def test_split_pending_summary_names_needed_pair():
    c = HosClock()
    c.drive(300)
    c.sleeper_split_rest(480)

    assert c.split_pending_summary() == (
        "Sleeper split pending: pair this with 2 more hours off duty or sleeper berth."
    )
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/test_hos.py::test_split_long_period_must_be_sleeper_berth tests/test_hos.py::test_split_pending_summary_names_needed_pair -q`

Expected: first test may fail on counter behavior, second fails because `split_pending_summary` does not exist.

- [ ] **Step 7: Implement pending summary**

Add to `HosClock`:

```python
    def split_pending_summary(self) -> str | None:
        rest_events = [
            e for e in self.history
            if e.source == "normal"
            and e.status in {"off_duty", "sleeper_berth"}
            and e.minutes >= SPLIT_SHORT_MIN
        ]
        if not rest_events:
            return None
        last = rest_events[-1]
        if last.status == "sleeper_berth" and last.minutes >= SPLIT_LONG_ALT_MIN:
            return "Sleeper split pending: pair this with 2 more hours off duty or sleeper berth."
        if last.status == "sleeper_berth" and last.minutes >= SPLIT_LONG_MIN:
            return "Sleeper split pending: pair this with 3 more hours off duty or sleeper berth."
        if last.minutes >= SPLIT_SHORT_ALT_MIN:
            return "Sleeper split pending: pair this with 7 more hours in the sleeper berth."
        if last.minutes >= SPLIT_SHORT_MIN:
            return "Sleeper split pending: pair this with 8 more hours in the sleeper berth."
        return None
```

Append pending summary in `summary()` before the final period:

```python
        pending = self.split_pending_summary()
        suffix = f" {pending}" if pending else ""
        return (f"ELD status {status}. Hours of service: "
                f"{drive_left:.1f} hours of driving left, "
                f"break due in {break_left:.1f}, "
                f"duty window closes in {duty_left:.1f}.{suffix}")
```

- [ ] **Step 8: Run focused HOS tests**

Run: `uv run pytest tests/test_hos.py::test_split_long_period_must_be_sleeper_berth tests/test_hos.py::test_split_pending_summary_names_needed_pair -q`

Expected: PASS.

- [ ] **Step 9: Commit Task 1**

Run:

```powershell
git add src\freight_fate\sim\hos.py tests\test_hos.py
git commit -m "feat(hos): add sleeper split ledger"
```

Expected: commit succeeds.

## Task 2: Save Compatibility And Full Reset Boundaries

**Files:**
- Modify: `src/freight_fate/sim/hos.py`
- Test: `tests/test_hos.py`

- [ ] **Step 1: Write failing serialization tests**

Add:

```python
def test_split_history_roundtrips_through_dict():
    c = HosClock()
    c.drive(300)
    c.sleeper_split_rest(480)
    c.drive(120)

    again = HosClock.from_dict(c.to_dict())

    assert again.history == c.history
    assert again.split_pending_summary() == c.split_pending_summary()


def test_emergency_sleep_sources_do_not_create_split_credit():
    c = HosClock()
    c.drive(300)
    c.sleeper_split_rest(480, source="emergency_lot")
    c.drive(120)
    completed = c.sleeper_split_rest(120)

    assert completed is False
    assert c.driving_min == pytest.approx(420)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hos.py::test_split_history_roundtrips_through_dict tests/test_hos.py::test_emergency_sleep_sources_do_not_create_split_credit -q`

Expected: FAIL because serialization does not include history/source handling yet.

- [ ] **Step 3: Update serialization**

Update `to_dict()` to include:

```python
                "history": [event.to_dict() for event in self.history],
                "split_credit_key": self.split_credit_key,
```

Update `from_dict()` to parse history:

```python
            history = []
            for raw_event in data.get("history", []):
                event = HosEvent.from_dict(raw_event)
                if event is not None:
                    history.append(event)
            return cls(
                driving_min=float(data.get("driving_min", 0.0)),
                duty_min=float(data.get("duty_min", 0.0)),
                since_break_min=float(data.get("since_break_min", 0.0)),
                status=status,
                non_driving_min=float(data.get("non_driving_min", 0.0)),
                off_duty_min=float(data.get("off_duty_min", 0.0)),
                warned=[str(w) for w in data.get("warned", [])],
                history=history[-HOS_HISTORY_MAX:],
                split_credit_key=(
                    str(data["split_credit_key"])
                    if data.get("split_credit_key") is not None else None
                ),
            )
```

- [ ] **Step 4: Run serialization tests**

Run: `uv run pytest tests/test_hos.py::test_split_history_roundtrips_through_dict tests/test_hos.py::test_emergency_sleep_sources_do_not_create_split_credit -q`

Expected: PASS.

- [ ] **Step 5: Run existing compatibility tests**

Run: `uv run pytest tests/test_hos.py::test_clock_roundtrips_through_dict tests/test_hos.py::test_legacy_clock_data_migrates_to_eld_fields tests/test_hos.py::test_clock_from_garbage_is_fresh -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add src\freight_fate\sim\hos.py tests\test_hos.py
git commit -m "feat(hos): persist sleeper split history"
```

Expected: commit succeeds.

## Task 3: Rest Menu Sleeper Choices

**Files:**
- Modify: `src/freight_fate/states/driving_rest_states.py`
- Test: `tests/test_hos.py`

- [ ] **Step 1: Write failing menu and smoke tests**

Add:

```python
@pytest.mark.smoke
def test_sleep_capable_stop_offers_sleeper_split_choices():
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        driving = start_drive(app)
        sleeper = SimpleNamespace(
            name="Big Truck Stop", at_mi=driving.trip.position_mi, type="truck_stop",
            actions=("break", "fuel", "sleep"), services=(), parking="confirmed",
            exit_label="", spoken_name="Big Truck Stop", parking_text="confirmed truck parking")
        labels = [i.text for i in RestStopState(app.ctx, driving, sleeper).build_items()]

        assert "Sleep 2 hours in sleeper berth" in labels
        assert "Sleep 3 hours in sleeper berth" in labels
        assert "Sleep 7 hours in sleeper berth" in labels
        assert "Sleep 8 hours in sleeper berth" in labels
        assert "Sleep 10 hours" in labels
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_split_sleeper_rest_action_advances_clock_and_speaks_status(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        sleeper = SimpleNamespace(
            name="Big Truck Stop", at_mi=driving.trip.position_mi, type="truck_stop",
            actions=("break", "fuel", "sleep"), services=(), parking="confirmed",
            exit_label="", spoken_name="Big Truck Stop", parking_text="confirmed truck parking")
        app.push_state(RestStopState(app.ctx, driving, sleeper))
        before = driving.trip.game_minutes

        select(app.state, "Sleep 8 hours in sleeper berth")

        assert driving.trip.game_minutes == pytest.approx(before + 480.0)
        assert driving.hos.status == "sleeper_berth"
        assert "Sleeper split pending" in spoken[-1]
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hos.py::test_sleep_capable_stop_offers_sleeper_split_choices tests/test_hos.py::test_split_sleeper_rest_action_advances_clock_and_speaks_status -q`

Expected: FAIL because menu items do not exist.

- [ ] **Step 3: Add menu items and handler**

In `RestStopState.build_items`, before the existing `Sleep 10 hours` item, add:

```python
            for hours in (2, 3, 7, 8):
                items.append(MenuItem(
                    f"Sleep {hours} hours in sleeper berth",
                    lambda h=hours: self._sleeper_split_rest(h),
                    help=self._sleeper_split_help(hours)))
```

Add methods to `RestStopState`:

```python
    def _sleeper_split_help(self, hours: int) -> str:
        if hours == 2:
            pair = "Can pair with 8 hours in the sleeper berth."
        elif hours == 3:
            pair = "Can pair with 7 hours in the sleeper berth."
        elif hours == 7:
            pair = "Can pair with 3 hours off duty or sleeper berth."
        else:
            pair = "Can pair with 2 hours off duty or sleeper berth."
        return f"{pair} The clock and your deadline advance {hours} hours."

    def _sleeper_split_rest(self, hours: int) -> None:
        d = self.driving
        p = self.ctx.profile
        minutes = float(hours * 60)
        _advance_rest_clock(d, minutes)
        completed = d.hos.sleeper_split_rest(minutes)
        p.fatigue = hos.rest_sleeper_split(p.fatigue, minutes, completed=completed)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        status = (
            "Sleeper split credited. "
            if completed else (d.hos.split_pending_summary() or "Sleeper berth rest recorded.")
        )
        self.ctx.say(
            f"You slept {hours} hours in the sleeper berth. "
            f"It is {clock_text(d.trip.current_hour)}. {status} {_deadline_text(d)}"
        )
        self.ctx.award_achievement("slept_on_route")
        self.refresh()
```

Add fatigue helper in `hos.py`:

```python
def rest_sleeper_split(fatigue: float, minutes: float, *, completed: bool = False) -> float:
    relief = 18.0 if minutes <= 180.0 else 55.0
    floor = 10.0 if completed else 20.0
    return max(floor, max(0.0, fatigue - relief))
```

- [ ] **Step 4: Run menu tests**

Run: `uv run pytest tests/test_hos.py::test_sleep_capable_stop_offers_sleeper_split_choices tests/test_hos.py::test_split_sleeper_rest_action_advances_clock_and_speaks_status -q`

Expected: PASS.

- [ ] **Step 5: Verify non-sleep stops do not offer split choices**

Extend `test_break_only_stop_always_offers_emergency_lot_sleep` with:

```python
        assert not any("sleeper berth" in label for label in labels)
```

Run: `uv run pytest tests/test_hos.py::test_break_only_stop_always_offers_emergency_lot_sleep -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add src\freight_fate\sim\hos.py src\freight_fate\states\driving_rest_states.py tests\test_hos.py
git commit -m "feat(hos): offer sleeper berth rest choices"
```

Expected: commit succeeds.

## Task 4: Player Guidance And Accessibility Text

**Files:**
- Modify: `src/freight_fate/states/main_menu_help.py`
- Modify: `docs/user-manual.md`
- Test: `tests/test_controls_reference.py`, `tests/test_manual_html.py`, `tests/test_hos.py`

- [ ] **Step 1: Write failing text coverage**

Add a test to `tests/test_hos.py`:

```python
def test_hos_summary_mentions_pending_sleeper_split():
    c = HosClock()
    c.drive(300)
    c.sleeper_split_rest(480)

    summary = c.summary("realistic")

    assert "Sleeper split pending" in summary
    assert "2 more hours" in summary
```

- [ ] **Step 2: Run summary test**

Run: `uv run pytest tests/test_hos.py::test_hos_summary_mentions_pending_sleeper_split -q`

Expected: PASS if Task 1 summary wiring is complete; otherwise FAIL and fix `HosClock.summary`.

- [ ] **Step 3: Update help and manual wording**

In `src/freight_fate/states/main_menu_help.py`, update the "Hours and rest" page to include:

```python
        "At sleep-capable truck parking, the sleeper berth is your cab bunk.",
        "You can choose 2, 3, 7, or 8 hours in the sleeper berth to build a",
        "legal split, or sleep 10 hours for the simple full reset.",
```

In `docs/user-manual.md`, update the hours/rest section with:

```markdown
At sleep-capable truck parking, the sleeper berth means the bunk in your cab.
You can choose 2, 3, 7, or 8 hours in the sleeper berth to plan an 8+2 or 7+3
split. Sleep 10 hours remains the simplest full reset. Shoulder sleep and
emergency lot sleep are fallback rests, not clean split-rest planning tools.
```

- [ ] **Step 4: Run docs/help tests**

Run: `uv run pytest tests/test_controls_reference.py tests/test_manual_html.py tests/test_hos.py::test_hos_summary_mentions_pending_sleeper_split -q`

Expected: PASS.

- [ ] **Step 5: Accessibility-agent verification**

Use the relevant accessibility specialist/lead to review the changed spoken
menu labels and help wording. Ask it to check that the rest choices are
distinguishable by screen-reader users, avoid internal implementation terms, and
explain pending split status clearly.

Expected: no blocking accessibility findings, or fixes applied before commit.

- [ ] **Step 6: Commit Task 4**

Run:

```powershell
git add src\freight_fate\states\main_menu_help.py docs\user-manual.md tests\test_hos.py
git commit -m "docs(hos): explain sleeper berth rest"
```

Expected: commit succeeds.

## Task 5: Final Verification

**Files:**
- Verify only unless failures require fixes.

- [ ] **Step 1: Run focused HOS suite**

Run: `uv run pytest tests/test_hos.py -q`

Expected: PASS.

- [ ] **Step 2: Run broader regression checks**

Run: `uv run pytest -q`

Expected: PASS.

- [ ] **Step 3: Run playtest harness smoke for rest menu**

Run an existing playtest-harness route that reaches a sleep-capable stop and opens the rest menu. If no direct transcript exists, add the narrowest harness transcript that enters a drive, parks at a sleep-capable test stop, opens the menu, and asserts spoken labels include "Sleep 8 hours in sleeper berth."

Expected: transcript confirms the new menu labels and HOS pending status are spoken.

- [ ] **Step 4: Review file sizes**

Run:

```powershell
(Get-Content src\freight_fate\sim\hos.py).Count
(Get-Content src\freight_fate\states\driving_rest_states.py).Count
```

Expected: both practical code files remain at or below 1000 lines. If either exceeds 1000, split cohesive helpers into a nearby module before finalizing.

- [ ] **Step 5: Final commit if verification fixes were needed**

If Task 5 required fixes, commit them:

```powershell
git status --short
git add src\freight_fate\sim\hos.py src\freight_fate\states\driving_rest_states.py src\freight_fate\states\main_menu_help.py docs\user-manual.md tests\test_hos.py
git commit -m "test(hos): verify sleeper berth split rest"
```

Expected: no uncommitted implementation changes remain except intentionally untracked local artifacts.

## Self-Review

- Spec coverage: Task 1 implements split pairs and pending summaries; Task 2 preserves save compatibility and keeps history suitable for future cycle limits; Task 3 adds player choice at sleep-capable stops and excludes emergency rests; Task 4 covers player wording and accessibility; Task 5 covers automated, smoke, and file-size verification.
- Deferred regulations: 60/70-hour cycle limits, 34-hour restart, adverse-condition extension, and short-haul exception are intentionally not implemented in this plan, matching the spec's first-slice scope.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: planned APIs are `HosEvent`, `HosClock.sleeper_split_rest`, `HosClock.split_pending_summary`, and `hos.rest_sleeper_split`.
