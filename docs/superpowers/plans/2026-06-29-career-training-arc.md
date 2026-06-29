# Career Training Arc Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the first company-driver hours feel like earning dispatch trust through spoken guidance, practical recommendations, and simple progression gates.

**Architecture:** Keep this as a save-compatible derived layer. Add a small career-training model that reads existing profile fields, then have terminal guidance and the dispatch board consume that model. Do not add tutorial locks or new save fields for this slice.

**Tech Stack:** Python 3.12, pygame menu states, pytest, Freight Fate `PlaytestHarness`, existing profile/career/business models.

---

## File Structure

- Create `src/freight_fate/models/career_training.py` for company-driver training stages, carrier-flavored guidance, recommendation labels, and dispatch scoring helpers.
- Modify `src/freight_fate/models/career_objectives.py` so early company-driver objectives use the training stage instead of "probation" wording.
- Modify `src/freight_fate/states/city.py` so first-day briefing, terminal entry, Career plan, dispatch-board intro, and recommended job labels speak the training guidance.
- Modify `tests/test_career_objectives.py` for objective wording, tapering, and spoken dispatch recommendations.
- Create `tests/test_career_training.py` for pure model coverage of stages, carrier flavor, and recommendation scoring.
- Optionally modify `tests/test_playtest_harness.py` only if a new end-to-end transcript test belongs there better than in the career objective tests.
- Update `docs/superpowers/specs/2026-06-28-career-training-arc-design.md` only if implementation discovers a design correction; otherwise leave the spec unchanged.

## Implementation Tasks

### Task 1: Add Training-Stage Model

**Files:**
- Create: `src/freight_fate/models/career_training.py`
- Test: `tests/test_career_training.py`

- [x] **Step 1: Write failing tests for stage boundaries and carrier flavor**

Create `tests/test_career_training.py`:

```python
from freight_fate.models.career_training import (
    TrainingStage,
    company_training_stage,
    training_guidance,
)
from freight_fate.models.profile import Profile
from freight_fate.models.start_options import apply_start_option, start_option


def _profile(deliveries: int, reputation: float = 75.0, carrier_key: str = "northstar") -> Profile:
    profile = Profile(name="Training", current_city="Chicago")
    apply_start_option(profile, start_option(carrier_key))
    profile.career.deliveries = deliveries
    profile.career.reputation = reputation
    return profile


def test_company_training_stage_boundaries_do_not_depend_on_perfect_service():
    assert company_training_stage(_profile(0, reputation=35.0)) is TrainingStage.FIRST_DISPATCH
    assert company_training_stage(_profile(1, reputation=35.0)) is TrainingStage.TRAINER_REMINDERS
    assert company_training_stage(_profile(2, reputation=35.0)) is TrainingStage.TRAINER_REMINDERS
    assert company_training_stage(_profile(3, reputation=35.0)) is TrainingStage.TRUST_OPENING
    assert company_training_stage(_profile(9, reputation=35.0)) is TrainingStage.TRUST_BUILDING
    assert company_training_stage(_profile(10, reputation=75.0)) is TrainingStage.NORMAL_GUIDANCE


def test_training_guidance_uses_carrier_flavor_without_probation_wording():
    guidance = training_guidance(_profile(1, carrier_key="great_lakes_training"))

    combined = " ".join((
        guidance.title,
        guidance.terminal_text,
        guidance.dispatch_text,
        guidance.recommendation_label,
    )).lower()
    assert "great lakes training transport" in combined
    assert "trainer" in combined
    assert "probation" not in combined


def test_ten_delivery_guidance_tapers_to_normal_company_driver_voice():
    guidance = training_guidance(_profile(10))

    assert guidance.title == "Trusted company guidance"
    assert "first-week" not in guidance.spoken_summary.lower()
    assert "trainer" not in guidance.spoken_summary.lower()
```

- [x] **Step 2: Run tests to confirm they fail**

Run:

```powershell
uv run pytest tests/test_career_training.py -q
```

Expected: failure because `freight_fate.models.career_training` does not exist.

- [x] **Step 3: Implement the training model**

Create `src/freight_fate/models/career_training.py`:

```python
"""Save-compatible company-driver training guidance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .business import COMPANY_DRIVER, carrier_name
from .start_options import start_option


class TrainingStage(Enum):
    FIRST_DISPATCH = "first_dispatch"
    TRAINER_REMINDERS = "trainer_reminders"
    TRUST_OPENING = "trust_opening"
    TRUST_BUILDING = "trust_building"
    NORMAL_GUIDANCE = "normal_guidance"


@dataclass(frozen=True)
class TrainingGuidance:
    stage: TrainingStage
    title: str
    terminal_text: str
    dispatch_text: str
    recommendation_label: str

    @property
    def spoken_summary(self) -> str:
        return f"{self.title}. {self.terminal_text} {self.dispatch_text}"


def is_company_training_profile(profile) -> bool:
    return getattr(profile, "business_status", COMPANY_DRIVER) == COMPANY_DRIVER


def company_training_stage(profile) -> TrainingStage:
    deliveries = int(getattr(profile.career, "deliveries", 0))
    if deliveries <= 0:
        return TrainingStage.FIRST_DISPATCH
    if deliveries < 3:
        return TrainingStage.TRAINER_REMINDERS
    if deliveries == 3:
        return TrainingStage.TRUST_OPENING
    if deliveries < 10:
        return TrainingStage.TRUST_BUILDING
    return TrainingStage.NORMAL_GUIDANCE


def training_guidance(profile) -> TrainingGuidance:
    stage = company_training_stage(profile)
    carrier = carrier_name(profile)
    option = start_option(getattr(profile, "carrier_key", ""))
    flavor = _carrier_flavor(option.key, carrier)
    if stage is TrainingStage.FIRST_DISPATCH:
        return TrainingGuidance(
            stage,
            "First dispatch",
            f"{carrier} has you on real freight with trainer support close by.",
            f"{flavor} Start with a short standard load that leaves room on the appointment.",
            "trainer-recommended",
        )
    if stage is TrainingStage.TRAINER_REMINDERS:
        return TrainingGuidance(
            stage,
            "First-week service record",
            f"{carrier} is looking for steady service, not perfection.",
            f"{flavor} Favor short regional freight with clean timing.",
            "good first-week run",
        )
    if stage is TrainingStage.TRUST_OPENING:
        return TrainingGuidance(
            stage,
            "Dispatch trust opening",
            f"{carrier} has enough first-week history to widen the board.",
            "A reliable lane still helps your record more than chasing a difficult load.",
            "good lane to build your record",
        )
    if stage is TrainingStage.TRUST_BUILDING:
        return TrainingGuidance(
            stage,
            "Build dispatcher trust",
            f"{carrier} is watching on-time service, damage, and steady miles.",
            "Pick reliable lanes before chasing specialty freight.",
            "good service-record load",
        )
    return TrainingGuidance(
        stage,
        "Trusted company guidance",
        "Keep building seniority, clean service, endorsements, and better carrier lanes.",
        "Unlocked freight with good time margins is the strongest career move.",
        "trusted carrier lane",
    )


def _carrier_flavor(key: str, carrier: str) -> str:
    if key == "great_lakes_training":
        return f"{carrier} usually gives new hires extra appointment room."
    if key == "prairie_link":
        return f"{carrier} likes practical regional mileage."
    if key == "summit_value":
        return f"{carrier} rewards appointment discipline."
    return f"{carrier} keeps the first week balanced."
```

- [x] **Step 4: Run model tests**

Run:

```powershell
uv run pytest tests/test_career_training.py -q
```

Expected: all tests in `tests/test_career_training.py` pass.

- [x] **Step 5: Commit**

Run:

```powershell
git add src/freight_fate/models/career_training.py tests/test_career_training.py
git commit -m "feat(career): model company-driver training stages"
```

### Task 2: Replace Early Objective Wording

**Files:**
- Modify: `src/freight_fate/models/career_objectives.py`
- Modify: `tests/test_career_objectives.py`

- [x] **Step 1: Update failing objective tests**

In `tests/test_career_objectives.py`, replace `test_company_driver_objective_moves_from_probation_to_dispatcher_trust` with:

```python
def test_company_driver_objective_tapers_from_first_week_to_trust():
    profile = Profile(name="Career Plan", current_city="Chicago")
    profile.achievements.append("first_dispatch")

    first_load = career_objective(profile)
    assert first_load.title == "First dispatch"
    assert "real freight" in first_load.terminal_text
    assert "short standard load" in first_load.dispatch_text
    assert "probation" not in first_load.spoken_summary.lower()

    profile.career.deliveries = 2
    reminder = career_objective(profile)
    assert reminder.title == "First-week service record"
    assert "steady service, not perfection" in reminder.terminal_text

    profile.career.deliveries = 4
    profile.career.reputation = 62
    trust = career_objective(profile)
    assert trust.title == "Build dispatcher trust"
    assert "on-time service" in trust.terminal_text
    assert "reliable lanes" in trust.dispatch_text
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_career_objectives.py::test_company_driver_objective_tapers_from_first_week_to_trust -q
```

Expected: failure because current code still says "Finish the probation load" and "Probation board".

- [x] **Step 3: Route early company-driver objectives through `training_guidance`**

Modify `src/freight_fate/models/career_objectives.py`:

```python
from .career_training import TrainingStage, training_guidance
```

Then replace the first three early-company branches in `_company_driver_objective` with:

```python
    guidance = training_guidance(profile)
    if guidance.stage is not TrainingStage.NORMAL_GUIDANCE:
        return CareerObjective(
            guidance.title,
            guidance.terminal_text,
            guidance.dispatch_text,
            guidance.recommendation_label,
        )
```

Keep the existing owner-operator prep, buy-in, and normal company-driver logic below this new block.

- [x] **Step 4: Run objective tests**

Run:

```powershell
uv run pytest tests/test_career_objectives.py tests/test_career_training.py -q
```

Expected: all selected tests pass.

- [x] **Step 5: Commit**

Run:

```powershell
git add src/freight_fate/models/career_objectives.py tests/test_career_objectives.py
git commit -m "fix(career): remove probation wording from early guidance"
```

### Task 3: Speak Training Guidance On Terminal And Dispatch Board

**Files:**
- Modify: `src/freight_fate/states/city.py`
- Modify: `tests/test_career_objectives.py`

- [ ] **Step 1: Add failing spoken-feedback tests**

Append to `tests/test_career_objectives.py`:

```python
def test_first_day_terminal_entry_speaks_training_arc_without_tutorial_language(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="First Day", current_city="Chicago")

        app.push_state(CityMenuState(app.ctx))

        entry = spoken[-1]
        assert "First-day objective" in entry
        assert "trainer-recommended" in entry
        assert "probation" not in entry.lower()
    finally:
        app.shutdown()


def test_dispatch_board_recommendation_label_is_spoken_and_visible(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Board Plan", current_city="Chicago")
        app.ctx.profile.career.deliveries = 1
        app.ctx.profile.achievements.append("first_dispatch")

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=180.0, pay=1200.0),
            _job(miles=70.0, pay=700.0),
        ]))

        assert "Career objective: First-week service record" in spoken[-1]
        assert "Recommended dispatch: good first-week run" in spoken[-1]
        assert app.state.items[1].text.startswith(
            "Recommended dispatch, good first-week run: Job 2 of 2:"
        )
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run the new tests to verify failure**

Run:

```powershell
uv run pytest tests/test_career_objectives.py::test_first_day_terminal_entry_speaks_training_arc_without_tutorial_language tests/test_career_objectives.py::test_dispatch_board_recommendation_label_is_spoken_and_visible -q
```

Expected: failure because first-day entry lacks the recommendation label and the visible label still uses `Recommended dispatch for ...`.

- [ ] **Step 3: Update terminal and dispatch-board speech**

In `src/freight_fate/states/city.py`, import:

```python
from ..models.career_training import training_guidance
```

Change first-day terminal entry in `CityMenuState.announce_entry`:

```python
        if not first_dispatch_done(p):
            guidance = training_guidance(p)
            first_day = (
                " First-day objective: open the dispatch board and take a "
                f"{guidance.recommendation_label} load."
            )
```

Change first-day dispatch-board intro in `JobBoardState.announce_entry`:

```python
            if not first_dispatch_done(self.ctx.profile):
                guidance = training_guidance(self.ctx.profile)
                first_day = (
                    f"First-day objective: pick a {guidance.recommendation_label} "
                    f"load. {guidance.dispatch_text} "
                )
```

Change normal career-objective dispatch-board intro in the same method:

```python
            else:
                objective = career_objective(self.ctx.profile)
                first_day = (
                    f"Career objective: {objective.title}. "
                    f"{objective.dispatch_text} "
                    f"Recommended dispatch: {objective.recommendation}. "
                )
```

Change recommended label in `_job_label`:

```python
        if self._recommended_job_index() == index - 1:
            recommendation = career_objective(p).recommendation
            label = f"Recommended dispatch, {recommendation}: {label}"
```

- [ ] **Step 4: Run spoken-feedback tests**

Run:

```powershell
uv run pytest tests/test_career_objectives.py -q
```

Expected: all career objective tests pass, and no spoken or visible text includes "probation".

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/freight_fate/states/city.py tests/test_career_objectives.py
git commit -m "feat(career): speak first-week dispatch guidance"
```

### Task 4: Make Recommendations Prefer Safe Early Freight

**Files:**
- Modify: `src/freight_fate/models/career_training.py`
- Modify: `src/freight_fate/states/city.py`
- Modify: `tests/test_career_training.py`
- Modify: `tests/test_career_objectives.py`

- [ ] **Step 1: Add failing recommendation-scoring tests**

Append to `tests/test_career_training.py`:

```python
from freight_fate.models.career_training import training_recommendation_score
from freight_fate.models.jobs import CARGO_CATALOG, Job


def _job(miles: float, deadline_h: float = 8.0, cargo: str = "general") -> Job:
    return Job(
        CARGO_CATALOG[cargo],
        12.0,
        "Chicago",
        "Chicago yard",
        "Milwaukee",
        miles,
        900.0,
        deadline_h,
    )


def test_first_dispatch_recommendation_prefers_short_forgiving_standard_load():
    profile = _profile(0)

    short_standard = _job(70.0, deadline_h=8.0, cargo="general")
    longer_tight = _job(220.0, deadline_h=4.0, cargo="electronics")

    assert training_recommendation_score(profile, short_standard) < training_recommendation_score(
        profile, longer_tight
    )


def test_trust_building_recommendation_allows_broader_but_still_values_time_margin():
    profile = _profile(5)

    roomy_regional = _job(180.0, deadline_h=10.0, cargo="general")
    tight_short = _job(90.0, deadline_h=2.0, cargo="general")

    assert training_recommendation_score(profile, roomy_regional) < training_recommendation_score(
        profile, tight_short
    )
```

- [ ] **Step 2: Run scoring tests to verify failure**

Run:

```powershell
uv run pytest tests/test_career_training.py::test_first_dispatch_recommendation_prefers_short_forgiving_standard_load tests/test_career_training.py::test_trust_building_recommendation_allows_broader_but_still_values_time_margin -q
```

Expected: failure because `training_recommendation_score` is missing.

- [ ] **Step 3: Implement recommendation scoring**

Add to `src/freight_fate/models/career_training.py`:

```python
def training_recommendation_score(profile, job) -> float:
    stage = company_training_stage(profile)
    miles = float(getattr(job, "distance_mi", 0.0))
    deadline = float(getattr(job, "deadline_h", 0.0))
    margin = max(0.0, deadline - miles / 55.0)
    cargo = getattr(getattr(job, "cargo", None), "key", "")
    specialty_penalty = 60.0 if cargo in {"electronics", "machinery", "hazmat"} else 0.0

    if stage is TrainingStage.FIRST_DISPATCH:
        return miles + specialty_penalty - margin * 18.0
    if stage is TrainingStage.TRAINER_REMINDERS:
        return miles * 0.85 + specialty_penalty * 0.5 - margin * 14.0
    if stage in {TrainingStage.TRUST_OPENING, TrainingStage.TRUST_BUILDING}:
        return miles * 0.65 - margin * 20.0 + specialty_penalty * 0.25
    return miles
```

- [ ] **Step 4: Use scoring in the dispatch board for company-driver training stages**

In `src/freight_fate/states/city.py`, import:

```python
from ..models.career_training import (
    TrainingStage,
    training_guidance,
    training_recommendation_score,
)
```

In `_recommended_job_index`, replace the company-driver `candidates.append((job.distance_mi, index))` branch with:

```python
            else:
                if training_guidance(p).stage is not TrainingStage.NORMAL_GUIDANCE:
                    candidates.append((training_recommendation_score(p, job), index))
                else:
                    candidates.append((job.distance_mi, index))
```

- [ ] **Step 5: Add a dispatch-board integration assertion**

In `tests/test_career_objectives.py`, add a shorter tight-deadline job and a roomier regional job to `test_dispatch_board_recommendation_label_is_spoken_and_visible`:

```python
        app.push_state(JobBoardState(app.ctx, [
            Job(CARGO_CATALOG["general"], 12.0, "Chicago", "Chicago yard", "Milwaukee", 45.0, 900.0, 1.0),
            Job(CARGO_CATALOG["general"], 12.0, "Chicago", "Chicago yard", "Milwaukee", 120.0, 900.0, 12.0),
        ]))
```

Then assert the recommended item is the roomier job:

```python
        assert app.state.items[1].text.startswith(
            "Recommended dispatch, good first-week run: Job 2 of 2:"
        )
```

- [ ] **Step 6: Run recommendation tests**

Run:

```powershell
uv run pytest tests/test_career_training.py tests/test_career_objectives.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/freight_fate/models/career_training.py src/freight_fate/states/city.py tests/test_career_training.py tests/test_career_objectives.py
git commit -m "feat(career): prefer safer first-week freight"
```

### Task 5: Add Scenario Playtest Proof

**Files:**
- Modify: `tests/test_playtest_harness.py`

- [ ] **Step 1: Add failing transcript test**

Add to `tests/test_playtest_harness.py`:

```python
def test_company_driver_first_delivery_transcript_builds_dispatch_trust(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(job_rank=0, route_rank=0)

    text = result.transcript_text.lower()
    assert "dispatch" in text
    assert "trainer" in text or "first-week" in text
    assert "probation" not in text
```

- [ ] **Step 2: Run the playtest harness test**

Run:

```powershell
uv run pytest tests/test_playtest_harness.py::test_company_driver_first_delivery_transcript_builds_dispatch_trust -q
```

Expected: the test should pass after Tasks 1-4. If it fails because the harness starts after the first-dispatch achievement is awarded, adjust the assertion to inspect the dispatch-board transcript before acceptance rather than weakening the "no probation wording" requirement.

- [ ] **Step 3: Run focused harness baseline**

Run:

```powershell
uv run pytest tests/test_playtest_harness.py -q
```

Expected: all playtest harness tests pass.

- [ ] **Step 4: Commit**

Run:

```powershell
git add tests/test_playtest_harness.py
git commit -m "test(career): cover first-week dispatch transcript"
```

### Task 6: Final Verification And Accessibility Review

**Files:**
- No required code changes unless verification exposes a defect.

- [ ] **Step 1: Run focused career checks**

Run:

```powershell
uv run pytest tests/test_career_training.py tests/test_career_objectives.py tests/test_career_start_options.py tests/test_business_arc.py tests/test_job_progression.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run playtest smoke proof**

Run:

```powershell
uv run pytest tests/test_playtest_harness.py -q
```

Expected: all harness tests pass with transcript coverage for spoken guidance.

- [ ] **Step 3: Run accessibility-agent review for the spoken UI surface**

Use the available accessibility-agent tool for game/audio UI review. Ask it to review the diff for:

```text
Freight Fate company-driver career training arc. Verify that dispatch recommendations, training-stage changes, and gate reasons are spoken, keyboard reachable, and not visual-label-only.
```

Expected: no blocking findings. If it reports findings, fix them before continuing.

- [ ] **Step 4: Run full focused regression if time allows**

Run:

```powershell
uv run pytest -q
```

Expected: full suite passes. If this is too slow for the worker budget, report that focused career, business, job progression, and playtest harness checks passed and name the skipped full-suite command.

- [ ] **Step 5: Commit final fixes if needed**

If verification required changes:

```powershell
git add <changed-files>
git commit -m "fix(career): polish training arc accessibility"
```

If no changes were needed, do not create an empty commit.

## Self-Review

- Spec coverage: The plan covers company-driver training stages, carrier flavor, recommendation wording, spoken feedback, simple gates at 3 and 10 deliveries, no perfect-service trap, owner-operator prep staying later, and scenario playtest proof.
- Scope control: This plan intentionally does not add save fields, new menus, hard job locks, reputation rebuild lectures, or a new owner-operator economy.
- Accessibility: Spoken output is part of each implementation task, and final verification requires an accessibility-agent pass because this is an audio-first interactive surface.
- Placeholder scan: No task uses placeholder work, delayed implementation language, or unspecified tests; each task includes exact files, commands, and expected outcomes.
