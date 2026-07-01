# Dispatch Autonomy As Progression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make *freedom to choose your freight and route* something the player earns across the 30-level career, instead of having it from minute one. A brand-new company driver should be **assigned** a load and a route by dispatch; load choice is earned with seniority; full load-and-route choice is the reward for going owner-operator. This closes the biggest realism gap in the career arc and turns an existing no-op menu into a progression payoff.

## Why (design rationale)

`docs/business-arc.md` already states the intent: *"The carrier controls the dispatch relationship, assigns and maintains the tractor/trailer combination."* The implementation has not caught up — today the player browses a 5-load board **and** picks their own route from level 1 as a "Yard Trainee."

Two facts from playtesting this branch:

- **Route choice is offered almost always but is unrealistic for a company driver.** Of 60 random city pairs, 52 offered 2–3 route options; the route menu appears from level 1. Real company drivers run the lane dispatch gives them.
- **The menu is often a no-op anyway.** Short/adjacent hauls frequently have a single supported route, so the player just presses Enter through "Route 1 of 2" (the 2nd item is "Back"). Friction without meaning.

Grounding the mechanic in real trucking:

- **Company driver:** dispatch assigns the load and the lane. The driver's real agency is *accept or decline*, and declining is remembered (service record). Refusing loads hurts your standing with dispatch.
- **Seniority:** trusted company drivers get more say in *which* load, but still run assigned routing.
- **Owner-operator / authority:** you choose your freight and your lanes — that is the whole point of the independence you bought into.

This makes the 30 levels feel like earning autonomy. It also gives the mid-late company levels (which currently reuse the same guidance text) a concrete, felt unlock.

## Autonomy bands

Gate on **business status first, then company level band** (both already exist: `business.py` statuses, `career.level`).

| Band | Status / level | Load | Route |
|------|----------------|------|-------|
| New hire | `company_driver`, level < `SENIOR_LOAD_CHOICE_LEVEL` (8) | **Assigned** (single offered load, accept/decline) | **Assigned** |
| Senior company | `company_driver`, level ≥ 8 | Choose from board (current) | **Assigned** |
| Owner-operator / authority | `leased_owner_operator` or `independent_authority` | Choose from board | **Choose** (current `RouteSelectState`) |

Route choice keys purely off `is_owner_operator(status)` / authority (i.e., *not* `company_driver`) — clean and matches the business arc. Load choice adds the senior-company level gate on top.

**Decline mechanic (company driver only):** a small per-cycle budget of assigned-load refusals. Declining draws the next offered load and costs reputation; running out means you take what you are given until the budget refills. Owner-operators/authority always choose, so declining is just "look at another load."

## Architecture

Add one small, pure policy model — `dispatch_policy(profile) -> DispatchPolicy` — mirroring the existing `career_level_guidance` / `career_objective` pattern. State code (`JobBoardState`, `_depart_for_destination`) consults the policy to decide whether to present a menu or auto-assign. No economy or route-geometry changes; assignment reuses the existing `_recommended_job_index()` (loads) and `supported_route_options()[0]` (route — already sorted best-first). Save-compatible: new `Profile` fields default cleanly; existing saves keep working and simply gain the assigned-dispatch flow at their current band.

**Tech Stack:** Python 3.12, Freight Fate model/state modules, pytest, ruff, existing `PlaytestHarness` (with the `--route`-style transcript proofs).

---

## File Structure

- Create `src/freight_fate/models/dispatch_policy.py`: `DispatchPolicy` dataclass (`assigns_load`, `assigns_route`, `decline_budget`) plus `dispatch_policy(profile)`.
- Modify `src/freight_fate/models/profile.py`: add save-compatible decline-tracking fields (`dispatch_declines_used: int = 0`, cycle marker) with defaults.
- Modify `src/freight_fate/states/city.py` (`JobBoardState`): when `policy.assigns_load`, present the single assigned load with an accept/decline flow instead of a browsable board; otherwise unchanged.
- Modify `src/freight_fate/states/city_pickup.py` (`_depart_for_destination`): when `not policy.assigns_route`, keep the menu; when it assigns, auto-select `routes[0]`, skip `RouteSelectState`, and narrate the assigned routing.
- Modify `src/freight_fate/models/career.py`: refill the decline budget on level-up (in `record_delivery`) and add `SENIOR_LOAD_CHOICE_LEVEL`.
- Create `tests/test_dispatch_policy.py`: pure band coverage.
- Modify `tests/test_playtest_harness.py`: transcript proof that a new-hire run is *assigned* a load+route (no route menu) and an owner-operator run still gets to choose.
- Modify `docs/business-arc.md`: add a short "Dispatch autonomy" section pointing at this arc.
- Modify this plan doc: check off steps as work progresses.

## Implementation Tasks

### Task 1: Dispatch policy model

**Files:** create `src/freight_fate/models/dispatch_policy.py`; test `tests/test_dispatch_policy.py`.

- [ ] **Step 1: Failing band tests.** Assert: level-1 `company_driver` → `assigns_load and assigns_route`; level-8 `company_driver` → `assigns_route and not assigns_load`; `leased_owner_operator` → neither assigned; `independent_authority` → neither assigned. Assert `decline_budget > 0` only for `company_driver`.
- [ ] **Step 2: Implement `DispatchPolicy` + `dispatch_policy(profile)`.** Pure function of `business_status` and `career.level`. Constants: `SENIOR_LOAD_CHOICE_LEVEL = 8`, `NEW_HIRE_DECLINE_BUDGET = 3`.
- [ ] **Step 3: `ruff format` / `ruff check`; tests green.**

### Task 2: Save-compatible decline tracking

**Files:** modify `src/freight_fate/models/profile.py`, `src/freight_fate/models/career.py`.

- [ ] **Step 1: Failing tests** for a fresh `Profile` defaulting `dispatch_declines_used = 0` and old-save round-trip still loading.
- [ ] **Step 2:** add `dispatch_declines_used: int = 0` (+ any cycle marker) with defaults; refill (reset to 0) on level-up inside `Career.record_delivery` so a promotion clears refusals. Remaining budget = `NEW_HIRE_DECLINE_BUDGET - dispatch_declines_used`.
- [ ] **Step 3:** ruff + tests green, including existing profile-integrity/signature tests.

### Task 3: Assigned-load flow on the dispatch board

**Files:** modify `src/freight_fate/states/city.py` (`JobBoardState`).

- [ ] **Step 1: Failing state test.** With a `company_driver` level-1 profile, opening the board yields a single *assigned* load (the `_recommended_job_index()` load) with accept + decline actions, not a 5-item browsable list. Declining draws the next candidate and increments `dispatch_declines_used`; a decline applies the reputation penalty; budget exhaustion locks to accept-only.
- [ ] **Step 2: Implement.** Branch on `dispatch_policy(profile).assigns_load`: reuse `_recommended_job_index()`/`_candidates` to pick the assigned load; speak it as an assignment ("Dispatch assigned you…"); wire decline → next candidate + `career.reputation` hit + budget decrement. Leave the browsable board untouched when `not assigns_load`.
- [ ] **Step 3:** ruff + tests green.

### Task 4: Assigned-route flow at departure

**Files:** modify `src/freight_fate/states/city_pickup.py` (`_depart_for_destination`).

- [ ] **Step 1: Failing test.** `company_driver` departure auto-selects `routes[0]` and transitions straight to `DrivingState` (no `RouteSelectState`), narrating the assigned routing ("Dispatch routed you via …"). Owner-operator/authority still pushes `RouteSelectState`.
- [ ] **Step 2: Implement.** When `not dispatch_policy(profile).assigns_route`, keep pushing `RouteSelectState`. Otherwise build the trip from `routes[0]` with the state RouteSelectState already constructs (reuse its trip-setup so air-brake/engine snapshots carry over), speak the assigned route summary, and push `DrivingState` directly.
- [ ] **Step 3:** ruff + tests green.

### Task 5: Guidance + transcript proof

**Files:** modify `src/freight_fate/states/city.py` terminal/first-day guidance, `tests/test_playtest_harness.py`, `docs/business-arc.md`.

- [ ] **Step 1:** Update first-day / terminal objective text so new hires are told the load and route are assigned ("run dispatch's load and lane, build your record"), and senior/owner bands are told what they now choose.
- [ ] **Step 2: Harness proof.** Extend `PlaytestHarness` so a new-hire run asserts the transcript contains an assigned-load and assigned-route line and **no** route-selection prompt; add an owner-operator variant (set `business_status` + XP) that asserts the route menu still appears.
- [ ] **Step 3:** Add a "Dispatch autonomy" section to `docs/business-arc.md`; ruff + full `uv run pytest` green.

## Out of scope (follow-ups noted from the same playtest)

- **Distance-cap recompression:** `JobBoard.distance_cap(level)` grows to 4,700 mi by L12 and 13,700 by L30 — larger than any U.S. route, so haul length stops progressing after ~L8. Recompress separately (e.g., L1≈250 → L30≈2,800).
- **Guidance de-duplication:** L1/L6 and L25/L30 currently share guidance text; give each rank a distinct concrete objective.
- Detention/appointment windows, persistent 70-hour HOS clock, and owner-operator fuel/deadhead cash pressure — each its own plan.

## Testing strategy

- Pure model tests for `dispatch_policy` bands and decline budget.
- State tests for the assigned-load board and assigned-route departure, plus the owner-operator "still chooses" path.
- Two `PlaytestHarness` transcript proofs (new-hire assigned run; owner-operator choice run) so the audio-first behavior is locked.
- `ruff check` + full `pytest` before completion; save-compatibility covered by profile round-trip tests.
