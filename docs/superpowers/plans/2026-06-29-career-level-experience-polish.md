# Career Level Experience Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing 30-level career ladder feel distinct through spoken level-band guidance, Career plan text, dispatch framing, and transcript proof without changing economy or save data.

**Architecture:** Add a save-compatible derived guidance model for level bands, then let `career_objective()` delegate to it only after urgent practical states are handled. Existing terminal and dispatch-board speech already consume `career_objective()`, so the main integration path stays small and audio-first.

**Tech Stack:** Python 3.12, Freight Fate model/state modules, pytest, ruff, existing `PlaytestHarness`.

---

## File Structure

- Create `src/freight_fate/models/career_level_guidance.py`: immutable level-band guidance object plus `career_level_guidance(profile)`.
- Modify `src/freight_fate/models/career_objectives.py`: delegate generic company/owner/authority guidance to the new model while preserving urgent gates.
- Create `tests/test_career_level_guidance.py`: pure representative level-band coverage.
- Modify `tests/test_career_objectives.py`: integration coverage proving urgent states still override level-band guidance.
- Modify `tests/test_playtest_harness.py`: add one transcript proof for mid/late-career guidance.
- Modify `docs/superpowers/plans/2026-06-29-career-level-experience-polish.md`: mark steps complete as work progresses.

## Implementation Tasks

### Task 1: Add Level-Band Guidance Model

**Files:**
- Create: `src/freight_fate/models/career_level_guidance.py`
- Test: `tests/test_career_level_guidance.py`

- [x] **Step 1: Write failing representative guidance tests**

Create `tests/test_career_level_guidance.py`:

```python
from freight_fate.models.business import INDEPENDENT_AUTHORITY, LEASED_OWNER_OPERATOR
from freight_fate.models.career import LEVEL_XP
from freight_fate.models.career_level_guidance import career_level_guidance
from freight_fate.models.profile import Profile


def _profile(level: int, *, status: str = "company_driver") -> Profile:
    profile = Profile(name="Level Guide", current_city="Chicago")
    profile.career.xp = LEVEL_XP[level - 1]
    profile.career.deliveries = 12
    profile.career.reputation = 82
    profile.business_status = status
    if status != "company_driver":
        profile.owned_trucks = ["rig"]
        profile.money = 80_000.0
    return profile


def test_company_level_guidance_moves_from_regional_to_senior_to_business_prep():
    regional = career_level_guidance(_profile(4))
    assert regional.title == "Build a regional service record"
    assert "broader company lanes" in regional.terminal_text
    assert regional.recommendation == "reputation-building lane"

    senior = career_level_guidance(_profile(10))
    assert senior.title == "Run like a senior company driver"
    assert "premium" in senior.dispatch_text
    assert senior.recommendation == "senior company lane"

    prep = career_level_guidance(_profile(14))
    assert prep.title == "Prepare for owner-operator risk"
    assert "cash cushion" in prep.terminal_text
    assert prep.recommendation == "business-prep load"


def test_owner_operator_guidance_tracks_margin_authority_and_independence():
    leased = career_level_guidance(_profile(18, status=LEASED_OWNER_OPERATOR))
    assert leased.title == "Protect owner-operator margin"
    assert "reserve" in leased.dispatch_text
    assert leased.recommendation == "reserve-safe owner-operator freight"

    authority_prep = career_level_guidance(_profile(22, status=LEASED_OWNER_OPERATOR))
    assert authority_prep.title == "Build authority readiness"
    assert "trailer strategy" in authority_prep.terminal_text
    assert authority_prep.recommendation == "authority-readiness lane"

    independent = career_level_guidance(_profile(27, status=INDEPENDENT_AUTHORITY))
    assert independent.title == "Grow independent freight reputation"
    assert "direct freight" in independent.dispatch_text
    assert independent.recommendation == "direct freight with margin"
```

- [x] **Step 2: Run tests to confirm failure**

Run:

```powershell
uv run pytest tests/test_career_level_guidance.py -q
```

Expected: failure because `freight_fate.models.career_level_guidance` does not exist.

- [x] **Step 3: Implement the derived guidance model**

Create `src/freight_fate/models/career_level_guidance.py`:

```python
"""Save-compatible level-band guidance for the 30-level career ladder."""

from __future__ import annotations

from dataclasses import dataclass

from .business import COMPANY_DRIVER, INDEPENDENT_AUTHORITY, is_owner_operator


@dataclass(frozen=True)
class CareerLevelGuidance:
    title: str
    terminal_text: str
    dispatch_text: str
    recommendation: str
    milestone_text: str

    @property
    def spoken_summary(self) -> str:
        return f"{self.title}. {self.terminal_text} {self.dispatch_text}"


def career_level_guidance(profile) -> CareerLevelGuidance:
    level = int(getattr(profile.career, "level", 1))
    status = getattr(profile, "business_status", COMPANY_DRIVER)

    if status == INDEPENDENT_AUTHORITY or level >= 25:
        return CareerLevelGuidance(
            "Grow independent freight reputation",
            "Use authority, trailer fit, and cash reserves to choose better contracts.",
            "Direct freight is strongest when it protects margin and service reputation.",
            "direct freight with margin",
            "Independent freight reputation matters more than raw gross pay.",
        )
    if is_owner_operator(status) and level >= 21:
        return CareerLevelGuidance(
            "Build authority readiness",
            "Keep working capital, trailer strategy, and direct-freight readiness in view.",
            "The best loads leave room for fuel, repairs, trailer support, and authority prep.",
            "authority-readiness lane",
            "Authority prep is about reserves and judgment, not just miles.",
        )
    if is_owner_operator(status) or level >= 18:
        return CareerLevelGuidance(
            "Protect owner-operator margin",
            "Treat every dispatch as a business decision with fuel, maintenance, and trailer costs.",
            "Favor freight with clear take-home and enough reserve after settlement.",
            "reserve-safe owner-operator freight",
            "Owner-operator progress depends on margin discipline.",
        )
    if level >= 14:
        return CareerLevelGuidance(
            "Prepare for owner-operator risk",
            "Build reputation, deliveries, and a cash cushion before taking on truck costs.",
            "Choose freight that protects service quality while savings grow.",
            "business-prep load",
            "Business prep starts before the buy-in appears.",
        )
    if level >= 10:
        return CareerLevelGuidance(
            "Run like a senior company driver",
            "Dispatch trusts you with premium lanes, specialized freight, and mentoring-level judgment.",
            "Premium freight still needs clean timing, low damage, and steady service.",
            "senior company lane",
            "Senior company status is about consistency under better freight.",
        )
    if level >= 4:
        return CareerLevelGuidance(
            "Build a regional service record",
            "Broader company lanes are opening, and reputation decides how good the board feels.",
            "Pick reliable freight that turns endorsements and clean service into better dispatch trust.",
            "reputation-building lane",
            "Regional progress comes from clean, repeatable service.",
        )
    return CareerLevelGuidance(
        "Build first-week trust",
        "Use trainer support and safer freight to start a clean service record.",
        "Short, forgiving freight is still the smartest first move.",
        "good first-week run",
        "First-week trust starts with clean service.",
    )
```

- [x] **Step 4: Run model tests**

Run:

```powershell
uv run pytest tests/test_career_level_guidance.py -q
```

Expected: all tests pass.

- [x] **Step 5: Commit**

Run:

```powershell
git add src/freight_fate/models/career_level_guidance.py tests/test_career_level_guidance.py
git commit -m "feat(career): add level-band guidance"
```

### Task 2: Integrate Guidance Into Career Objectives

**Files:**
- Modify: `src/freight_fate/models/career_objectives.py`
- Modify: `tests/test_career_objectives.py`

- [x] **Step 1: Add failing objective integration tests**

Append to `tests/test_career_objectives.py`:

```python
def test_company_driver_objective_uses_level_band_guidance_after_training():
    profile = Profile(name="Regional Plan", current_city="Chicago")
    profile.achievements.append("first_dispatch")
    profile.career.xp = LEVEL_XP[3]
    profile.career.deliveries = 12
    profile.career.reputation = 82

    objective = career_objective(profile)

    assert objective.title == "Build a regional service record"
    assert "Broader company lanes" in objective.terminal_text
    assert objective.recommendation == "reputation-building lane"


def test_ready_unlock_states_override_level_band_guidance():
    profile = Profile(name="Buy In", current_city="Chicago")
    profile.achievements.append("first_dispatch")
    profile.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 1]
    profile.career.deliveries = 35
    profile.career.reputation = 82
    profile.money = 60_000.0

    objective = career_objective(profile)

    assert objective.title == "Owner-operator buy-in ready"
    assert objective.recommendation == "clean company load"
```

- [x] **Step 2: Run tests to confirm failure**

Run:

```powershell
uv run pytest tests/test_career_objectives.py::test_company_driver_objective_uses_level_band_guidance_after_training tests/test_career_objectives.py::test_ready_unlock_states_override_level_band_guidance -q
```

Expected: first test fails because generic company-driver text still returns `Trusted company driver`; ready-unlock test should continue to pass or fail only if the test setup needs existing gate cash adjusted.

- [x] **Step 3: Delegate generic objective text to level guidance**

In `src/freight_fate/models/career_objectives.py`, import:

```python
from .career_level_guidance import career_level_guidance
```

Replace the final generic company-driver return with:

```python
    guidance = career_level_guidance(profile)
    return CareerObjective(
        guidance.title,
        guidance.terminal_text,
        guidance.dispatch_text,
        guidance.recommendation,
    )
```

Replace the final generic owner-operator return in `_owner_operator_objective()` with:

```python
    guidance = career_level_guidance(profile)
    return CareerObjective(
        guidance.title,
        guidance.terminal_text,
        guidance.dispatch_text,
        guidance.recommendation,
    )
```

Replace the final generic independent authority return in `_independent_authority_objective()` with:

```python
    guidance = career_level_guidance(profile)
    return CareerObjective(
        guidance.title,
        guidance.terminal_text,
        guidance.dispatch_text,
        guidance.recommendation,
    )
```

Keep low-reputation, buy-in-ready, working-capital, authority-ready, and authority-activation branches above the delegated generic returns.

- [x] **Step 4: Run objective and level-guidance tests**

Run:

```powershell
uv run pytest tests/test_career_objectives.py tests/test_career_level_guidance.py -q
```

Expected: all tests pass.

- [x] **Step 5: Commit**

Run:

```powershell
git add src/freight_fate/models/career_objectives.py tests/test_career_objectives.py
git commit -m "feat(career): use level-band objectives"
```

### Task 3: Add Speech And Dispatch Integration Coverage

**Files:**
- Modify: `tests/test_career_objectives.py`

- [x] **Step 1: Add failing terminal and dispatch-board speech tests**

Append to `tests/test_career_objectives.py`:

```python
def test_terminal_career_plan_speaks_senior_company_level_guidance(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Senior Driver", current_city="Chicago")
        app.ctx.profile.achievements.append("first_dispatch")
        app.ctx.profile.career.xp = LEVEL_XP[9]
        app.ctx.profile.career.deliveries = 20
        app.ctx.profile.career.reputation = 86

        app.push_state(CityMenuState(app.ctx))
        career_item = next(i for i, item in enumerate(app.state.items) if item.text == "Career plan")
        app.state.index = career_item
        app.state.items[career_item].action()

        assert spoken[-1].startswith("Run like a senior company driver.")
        assert "premium lanes" in spoken[-1]
        assert "Premium freight" in spoken[-1]
    finally:
        app.shutdown()


def test_dispatch_board_speaks_authority_level_recommendation(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.business import INDEPENDENT_AUTHORITY
    from freight_fate.states.city import JobBoardState

    spoken: list[str] = []
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Independent", current_city="Chicago")
        app.ctx.profile.achievements.append("first_dispatch")
        app.ctx.profile.business_status = INDEPENDENT_AUTHORITY
        app.ctx.profile.owned_trucks = ["rig"]
        app.ctx.profile.money = 90_000.0
        app.ctx.profile.career.xp = LEVEL_XP[24]
        app.ctx.profile.career.deliveries = 80
        app.ctx.profile.career.reputation = 94

        app.push_state(JobBoardState(app.ctx, [
            _job(miles=120.0, pay=1800.0),
        ]))

        assert "Career objective: Grow independent freight reputation" in spoken[-1]
        assert "direct freight" in spoken[-1]
        assert "direct freight with margin" in spoken[-1]
    finally:
        app.shutdown()
```

- [x] **Step 2: Run tests to confirm failure or current gaps**

Run:

```powershell
uv run pytest tests/test_career_objectives.py::test_terminal_career_plan_speaks_senior_company_level_guidance tests/test_career_objectives.py::test_dispatch_board_speaks_authority_level_recommendation -q
```

Expected: pass after Task 2; if it fails, the failure should identify missing speech propagation through existing terminal or dispatch-board paths.

- [x] **Step 3: Fix only if propagation is missing**

If either test fails because `CityMenuState` or `JobBoardState` does not speak the delegated objective, update `src/freight_fate/states/city.py` to use `career_objective(profile).spoken_summary`, `.dispatch_text`, and `.recommendation` exactly as existing first-week paths do. Do not add new menu items or save fields.

- [x] **Step 4: Run speech integration tests**

Run:

```powershell
uv run pytest tests/test_career_objectives.py tests/test_career_level_guidance.py -q
```

Expected: all tests pass.

- [x] **Step 5: Commit**

If tests required code or test changes:

```powershell
git add src/freight_fate/states/city.py tests/test_career_objectives.py
git commit -m "test(career): cover spoken level guidance"
```

If Task 2 already made these tests pass and no code changed, commit only the tests:

```powershell
git add tests/test_career_objectives.py
git commit -m "test(career): cover spoken level guidance"
```

### Task 4: Add Transcript Proof

**Files:**
- Modify: `tests/test_playtest_harness.py`

- [x] **Step 1: Add failing transcript test for mid-career guidance**

Add to `tests/test_playtest_harness.py`:

```python
def test_mid_career_transcript_speaks_level_band_guidance(monkeypatch):
    from freight_fate.models.career import LEVEL_XP

    with PlaytestHarness(monkeypatch) as harness:
        harness.app.ctx.profile.career.xp = LEVEL_XP[9]
        harness.app.ctx.profile.career.deliveries = 20
        harness.app.ctx.profile.career.reputation = 86
        result = harness.start_delivery(
            profile_name="Harness Senior Career",
            job_rank=0,
            route_rank=0,
        )

    text = result.transcript_text
    assert "Run like a senior company driver" in text
    assert "senior company lane" in text
    assert "probation" not in text.lower()
```

- [x] **Step 2: Run transcript test**

Run:

```powershell
uv run pytest tests/test_playtest_harness.py::test_mid_career_transcript_speaks_level_band_guidance -q
```

Expected: pass if the harness captures terminal/dispatch-board guidance. If it fails because `start_delivery()` resets profile state after the assignments, inspect `tests/playtest_harness.py` and set the profile fields after harness initialization but before opening the dispatch board using the harness’s existing helper flow.

- [x] **Step 3: Run harness baseline**

Run:

```powershell
uv run pytest tests/test_playtest_harness.py -q
```

Expected: all harness tests pass.

- [x] **Step 4: Commit**

Run:

```powershell
git add tests/test_playtest_harness.py
git commit -m "test(career): cover mid-career guidance transcript"
```

### Task 5: Final Verification And Accessibility Review

**Files:**
- No code changes unless verification exposes defects.

- [x] **Step 1: Run focused career checks**

Run:

```powershell
uv run pytest tests/test_career_level_guidance.py tests/test_career_objectives.py tests/test_career_start_options.py tests/test_business_arc.py tests/test_job_progression.py -q
```

Expected: all selected tests pass.

- [x] **Step 2: Run playtest proof**

Run:

```powershell
uv run pytest tests/test_playtest_harness.py -q
```

Expected: all harness tests pass.

- [x] **Step 3: Run accessibility review**

Use the available accessibility-agent or desktop accessibility review path for:

```text
Freight Fate level-band career guidance. Verify that level-band milestones,
terminal Career plan guidance, and dispatch recommendations are spoken,
keyboard reachable, not visual-label-only, and do not mislead owner-operator
or own-authority profiles.
```

Expected: no blocking findings. Fix any concrete spoken/focus findings before finalizing.

- [x] **Step 4: Run full suite**

Run:

```powershell
uv sync --group dev --group tooling
uv run pytest -q
```

Expected: full pytest passes.

- [x] **Step 5: Commit final fixes if needed**

If verification required changes:

```powershell
git add <changed-files>
git commit -m "fix(career): polish level guidance accessibility"
```

If no changes were needed, do not create an empty commit.

## Self-Review

- Spec coverage: The plan adds a derived level-guidance layer, integrates it through `career_objective()`, covers representative level bands, preserves urgent gates, adds spoken terminal/dispatch coverage, and adds transcript proof.
- Scope control: The plan does not alter XP thresholds, rank titles, save schema, settlement math, freight economics, or authority systems.
- Accessibility: The plan keeps all new guidance flowing through spoken terminal and dispatch paths and requires a final accessibility review.
- Completeness scan: No task uses vague work, delayed implementation language, or unspecified tests.
