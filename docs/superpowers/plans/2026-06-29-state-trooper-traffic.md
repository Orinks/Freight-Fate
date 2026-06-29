# State Trooper Traffic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make state troopers real NPC traffic vehicles tied to existing patrol windows.

**Architecture:** Keep normal traffic classes as `car`, `box truck`, `semi`, and `service vehicle`. Add patrol-backed `state trooper` vehicles to `TrafficManager` after `Trip` creates patrol windows, preserving current enforcement behavior and public traffic APIs.

**Tech Stack:** Python dataclasses, existing Freight Fate trip simulation, pytest, Ruff.

---

### Task 1: Add Patrol-Backed Trooper Vehicles

**Files:**
- Modify: `src/freight_fate/sim/traffic_manager.py`
- Modify: `src/freight_fate/sim/trip.py`
- Test: `tests/test_traffic_manager.py`
- Test: `tests/test_troopers.py`

- [ ] **Step 1: Write failing tests**

Add manager coverage that `add_patrol_traffic()` creates `state trooper` vehicles for patrol windows and preserves sorted traffic.

Add trip coverage that a trip with a patrol window also has a `state trooper` traffic vehicle.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_traffic_manager.py::test_patrol_windows_add_state_trooper_traffic tests/test_troopers.py::test_patrol_windows_create_state_trooper_npcs -q
```

Expected: FAIL because `add_patrol_traffic()` does not exist.

- [ ] **Step 3: Implement minimal trooper traffic**

Add `TrafficManager.add_patrol_traffic(patrols)` that deterministically appends one `TrafficVehicle` with `vehicle_class="state trooper"` near each patrol window when no matching trooper key exists.

Call it from `Trip.__init__` after `self.patrols = self._place_patrols()`.

- [ ] **Step 4: Run focused verification**

Run:

```powershell
uv run pytest tests/test_traffic_manager.py tests/test_troopers.py -q
uv run ruff check src/freight_fate/sim/traffic_manager.py src/freight_fate/sim/trip.py tests/test_traffic_manager.py tests/test_troopers.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add docs/superpowers/plans/2026-06-29-state-trooper-traffic.md src/freight_fate/sim/traffic_manager.py src/freight_fate/sim/trip.py tests/test_traffic_manager.py tests/test_troopers.py
git commit -m "feat: add state trooper traffic npcs"
```
