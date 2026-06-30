# Forum Gameplay Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved forum-feedback polish pass: dispatch job detail help, hybrid assist, looping horn, tire/cleaning maintenance, and fairer long-haul pay.

**Architecture:** Keep changes inside existing Freight Fate patterns: Pygame menu states, profile-backed upgrades, driving-state updates, and job-board generation. Each slice adds focused tests first, implements the smallest compatible data/model change, and commits independently.

**Tech Stack:** Python, Pygame, uv, pytest, Ruff, Freight Fate menu/state/model modules.

---

## File Map

- `src/freight_fate/states/city.py`: dispatch board F1 detail state, garage maintenance actions/status, upgrade shop labels.
- `src/freight_fate/models/jobs.py`: pay-per-mile helper and long-haul pay floor.
- `src/freight_fate/models/profile.py`: save-compatible tire wear and dirt fields.
- `src/freight_fate/models/trucks.py`: hybrid assist upgrade definition and fuel-effect constants.
- `src/freight_fate/sim/vehicle.py`: low-speed hybrid fuel-burn effect, tire/dirt wear helpers if best kept on truck state.
- `src/freight_fate/states/driving.py`: initialize/restore maintenance counters as needed.
- `src/freight_fate/states/driving_controls.py`: H keydown/keyup horn loop.
- `src/freight_fate/states/driving_updates.py`: accrue tire wear and dirt during driving.
- `src/freight_fate/audio.py`: reserve one loop channel for the horn and expose `start_horn` / `stop_horn`.
- `tests/test_dispatch_job_detail.py`: new focused dispatch F1 tests.
- `tests/test_trucks.py`: hybrid assist behavior tests.
- `tests/test_driving_features.py`: horn keydown/keyup and driving maintenance accrual tests.
- `tests/test_garage_maintenance.py`: garage tire/wash service tests.
- `tests/test_jobs.py`: long-haul pay floor tests.
- `CHANGELOG.md`: user-facing note for job details, horn loop, maintenance, hybrid upgrade, and long-haul pay.

## Task 1: Dispatch Job Detail View

**Files:**
- Modify: `src/freight_fate/states/city.py`
- Create: `tests/test_dispatch_job_detail.py`

- [ ] **Step 1: Write failing tests for F1 job details**

Create `tests/test_dispatch_job_detail.py`:

```python
import pygame

from driving_feature_helpers import key_event


def _job_board(app):
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    app.ctx.profile = Profile(name="Dispatch Detail", current_city="Buffalo")
    jobs = JobBoard(app.ctx.world, seed=7).offers(
        "Buffalo", {"refrigerated", "heavy_haul", "high_value"}, level=5
    )
    state = JobBoardState(app.ctx, jobs)
    app.push_state(state)
    return state


def test_f1_on_dispatch_job_opens_structured_detail_view():
    from freight_fate.app import App
    from freight_fate.states.city import JobDetailState

    app = App()
    try:
        board = _job_board(app)
        job = board.jobs[board.index]

        board.handle_event(key_event(pygame.K_F1))

        assert isinstance(app.state, JobDetailState)
        lines = app.state.lines()
        joined = " ".join(lines)
        assert lines[0] == "Job details"
        assert f"Cargo: {job.cargo.label}" in joined
        assert "Origin:" in joined
        assert "Destination:" in joined
        assert "Distance:" in joined
        assert "Pay:" in joined
        assert "Dollars per mile:" in joined
        assert "Route details happen after pickup" in joined
    finally:
        app.shutdown()


def test_job_detail_enter_accepts_and_escape_returns():
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState, PickupFacilityState

    app = App()
    try:
        board = _job_board(app)
        board.handle_event(key_event(pygame.K_F1))
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, JobBoardState)

        board.handle_event(key_event(pygame.K_F1))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, PickupFacilityState) or app.state.__class__.__name__ == "DrivingState"
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
uv run pytest tests/test_dispatch_job_detail.py -q
```

Expected: fail because `JobDetailState` does not exist and F1 still speaks generic help.

- [ ] **Step 3: Implement `JobDetailState`**

In `src/freight_fate/states/city.py`, near `JobBoardState`, add:

```python
class JobDetailState(MenuState):
    title = "Job details"

    def __init__(self, ctx, board: "JobBoardState", job: Job) -> None:
        super().__init__(ctx)
        self.board = board
        self.job = job

    def enter(self) -> None:
        self.ctx.say("Job details. " + " ".join(self._detail_lines()))

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem("Accept this job", lambda: self.board._accept(self.job),
                     help="Accept this dispatch and begin the pickup drive."),
            MenuItem("Back to dispatch board", self.ctx.pop_state,
                     help="Return to the dispatch board without accepting this job."),
        ]

    def _detail_lines(self) -> list[str]:
        job = self.job
        dollars_per_mile = job.pay / max(job.distance_mi, 1.0)
        lines = [
            f"Cargo: {job.cargo.label}.",
            f"Origin: {job.origin_facility_text()}.",
            f"Destination: {job.destination_facility_text()} in {job.destination}.",
            f"Distance: {job.distance_mi:.0f} miles.",
            f"Pay: {job.pay:,.0f} dollars.",
            f"Dollars per mile: {dollars_per_mile:.2f}.",
            f"Deadline: {job.deadline_game_h:.0f} hours.",
            f"Equipment: {job.equipment_text()}.",
            "Route details happen after pickup: rest, fuel, tolls, weather, and stops.",
        ]
        if job.cargo.endorsement:
            lines.append(f"Requires {job.cargo.endorsement.replace('_', ' ')} endorsement.")
        return lines

    def lines(self) -> list[str]:
        return [self.title, ""] + self._detail_lines() + ["", self.current_text()]
```

If `Job.equipment_text()` does not exist, add a tiny method to `Job` in `src/freight_fate/models/jobs.py`:

```python
def equipment_text(self) -> str:
    return self.cargo.equipment or "standard dry van"
```

- [ ] **Step 4: Route F1 from dispatch rows to the detail state**

Override `handle_event` in `JobBoardState`:

```python
def handle_event(self, event: pygame.event.Event) -> None:
    if event.type == pygame.KEYDOWN and event.key == pygame.K_F1 and self.jobs:
        self.ctx.push_state(JobDetailState(self.ctx, self, self.jobs[self.index]))
        return
    super().handle_event(event)
```

Keep existing item help text for menu position/help, but F1 now opens review.

- [ ] **Step 5: Verify tests pass**

Run:

```powershell
uv run pytest tests/test_dispatch_job_detail.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/freight_fate/states/city.py src/freight_fate/models/jobs.py tests/test_dispatch_job_detail.py
git commit -m "feat(dispatch): add job detail help view"
```

## Task 2: Long-Haul Pay Floor

**Files:**
- Modify: `src/freight_fate/models/jobs.py`
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Add failing pay-floor tests**

Append to `tests/test_jobs.py`:

```python
def test_long_haul_minimum_pay_keeps_rate_worthwhile():
    from freight_fate.models.jobs import long_haul_pay_floor

    assert long_haul_pay_floor(200.0) == 0.0
    assert long_haul_pay_floor(700.0) >= 700.0 * 5.50
    assert long_haul_pay_floor(1800.0) >= 1800.0 * 5.25


def test_generated_long_haul_jobs_do_not_collapse_to_three_per_mile():
    from freight_fate.models.jobs import CARGO_CATALOG, JobBoard
    from freight_fate.models.market import Market
    from freight_fate.data.world import get_world

    world = get_world()
    board = JobBoard(world, seed=22)
    market = Market(seed=1)
    job = board._make_job(
        cargo=CARGO_CATALOG["general"],
        origin="New York",
        destination="Los Angeles",
        miles=2800.0,
        market=market,
        level=10,
        location=world.freight_locations("New York")[0],
    )

    assert job.pay / job.distance_mi >= 5.25
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest tests/test_jobs.py::test_long_haul_minimum_pay_keeps_rate_worthwhile tests/test_jobs.py::test_generated_long_haul_jobs_do_not_collapse_to_three_per_mile -q
```

Expected: fail because `long_haul_pay_floor` does not exist.

- [ ] **Step 3: Implement the pay floor**

In `src/freight_fate/models/jobs.py`, add near `minimum_pay_for_level`:

```python
LONG_HAUL_PAY_FLOOR_MILES = 600.0
LONG_HAUL_PAY_FLOOR_RATE = 5.25
MEDIUM_HAUL_PAY_FLOOR_RATE = 5.50


def long_haul_pay_floor(miles: float) -> float:
    if miles < LONG_HAUL_PAY_FLOOR_MILES:
        return 0.0
    rate = MEDIUM_HAUL_PAY_FLOOR_RATE if miles < 1200.0 else LONG_HAUL_PAY_FLOOR_RATE
    return miles * rate
```

In `_make_job`, change pay calculation to:

```python
floor = max(minimum_pay_for_level(miles, level), long_haul_pay_floor(miles))
pay = round(max(base_pay, floor) * mult, 2)
```

- [ ] **Step 4: Verify pay tests**

```powershell
uv run pytest tests/test_jobs.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/freight_fate/models/jobs.py tests/test_jobs.py
git commit -m "fix(dispatch): improve long-haul pay floor"
```

## Task 3: Hybrid Assist Upgrade

**Files:**
- Modify: `src/freight_fate/models/trucks.py`
- Modify: `src/freight_fate/sim/vehicle.py`
- Test: `tests/test_trucks.py`

- [ ] **Step 1: Add failing hybrid tests**

Append to `tests/test_trucks.py`:

```python
def test_hybrid_assist_upgrade_is_available():
    from freight_fate.models.trucks import UPGRADE_CATALOG

    upgrade = UPGRADE_CATALOG["hybrid_assist"]
    assert upgrade.label == "Hybrid assist"
    assert "low-speed" in upgrade.description.lower()


def test_hybrid_assist_reduces_low_speed_fuel_burn_more_than_highway():
    from freight_fate.models.trucks import build_truck_specs
    from freight_fate.sim.vehicle import TruckState

    base = TruckState(specs=build_truck_specs("rig", {}))
    hybrid = TruckState(specs=build_truck_specs("rig", {"hybrid_assist": 1}))

    low_base = base.fuel_burn_gph(speed_mph=20.0, throttle=0.5)
    low_hybrid = hybrid.fuel_burn_gph(speed_mph=20.0, throttle=0.5)
    highway_base = base.fuel_burn_gph(speed_mph=65.0, throttle=0.5)
    highway_hybrid = hybrid.fuel_burn_gph(speed_mph=65.0, throttle=0.5)

    assert low_hybrid < low_base * 0.9
    assert highway_hybrid == pytest.approx(highway_base, rel=0.03)
```

If `pytest` is not imported in `tests/test_trucks.py`, add `import pytest`.

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest tests/test_trucks.py -q
```

Expected: fail because upgrade and `fuel_burn_gph` helper do not exist.

- [ ] **Step 3: Add upgrade and spec field**

In `src/freight_fate/models/trucks.py`, add a constant:

```python
HYBRID_LOW_SPEED_FUEL_MULT = 0.82
```

Add to `UPGRADE_CATALOG`:

```python
"hybrid_assist": Upgrade(
    "hybrid_assist", "Hybrid assist",
    (9000,),
    "Adds low-speed electric assist for yards, city streets, and facility approaches. "
    "It lowers fuel costs off the highway; the aerodynamic kit is still the highway "
    "fuel-saver.",
),
```

Add a field to `TruckSpecs` if needed:

```python
hybrid_low_speed_fuel_mult: float = 1.0
```

In `build_truck_specs`, apply:

```python
if upgrades.get("hybrid_assist"):
    specs.hybrid_low_speed_fuel_mult = HYBRID_LOW_SPEED_FUEL_MULT
```

- [ ] **Step 4: Add fuel-burn helper and use it**

In `src/freight_fate/sim/vehicle.py`, add to `TruckState`:

```python
def fuel_burn_gph(self, *, speed_mph: float, throttle: float) -> float:
    base = self.specs.fuel_burn_gph * (0.35 + 0.65 * max(0.0, min(1.0, throttle)))
    if speed_mph < 35.0:
        return base * self.specs.hybrid_low_speed_fuel_mult
    return base
```

Then replace the existing per-frame fuel drain formula with this helper. Preserve current fuel behavior aside from the hybrid multiplier.

- [ ] **Step 5: Verify tests**

```powershell
uv run pytest tests/test_trucks.py tests/test_vehicle.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/freight_fate/models/trucks.py src/freight_fate/sim/vehicle.py tests/test_trucks.py
git commit -m "feat(garage): add hybrid assist upgrade"
```

## Task 4: Looping Horn

**Files:**
- Modify: `src/freight_fate/audio.py`
- Modify: `src/freight_fate/states/driving_controls.py`
- Modify: `src/freight_fate/states/driving.py`
- Test: `tests/test_driving_features.py`

- [ ] **Step 1: Add failing horn tests**

Append to `tests/test_driving_features.py`:

```python
def test_horn_loops_while_held_and_stops_on_release(monkeypatch):
    from freight_fate.app import App

    app = App()
    calls = []
    monkeypatch.setattr(app.ctx.audio, "start_horn", lambda: calls.append("start"))
    monkeypatch.setattr(app.ctx.audio, "stop_horn", lambda: calls.append("stop"))
    try:
        driving = start_drive(app)
        quiet_trip(driving)

        driving.handle_event(key_event(pygame.K_h))
        driving.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_h))

        assert calls == ["start", "stop"]
    finally:
        app.shutdown()


def test_horn_stops_when_driving_state_exits(monkeypatch):
    from freight_fate.app import App

    app = App()
    calls = []
    monkeypatch.setattr(app.ctx.audio, "start_horn", lambda: calls.append("start"))
    monkeypatch.setattr(app.ctx.audio, "stop_horn", lambda: calls.append("stop"))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.handle_event(key_event(pygame.K_h))

        driving.exit()

        assert calls == ["start", "stop"]
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest tests/test_driving_features.py::test_horn_loops_while_held_and_stops_on_release tests/test_driving_features.py::test_horn_stops_when_driving_state_exits -q
```

Expected: fail because `start_horn` and `stop_horn` do not exist and `KEYUP` is ignored.

- [ ] **Step 3: Add audio API**

In `src/freight_fate/audio.py`, reserve a horn loop channel after ambience:

```python
CH_AMBIENT = 7
CH_HORN = 8
RESERVED = 9
NUM_CHANNELS = 32
```

Add methods to the `_AudioBackend` protocol:

```python
def start_loop(self, channel: int, key: str, volume: float = 1.0,
               fade_ms: int = 300) -> None: ...
def stop_loop(self, channel: int, fade_ms: int = 300) -> None: ...
```

The loop methods already exist; keep this protocol section aligned if the file has it.

Add methods to the `AudioEngine` facade:

```python
def start_horn(self) -> None:
    self.start_loop(CH_HORN, "vehicle/horn", volume=1.0, fade_ms=0)

def stop_horn(self) -> None:
    self.stop_loop(CH_HORN, fade_ms=80)
```

- [ ] **Step 4: Handle H keydown and keyup**

In `src/freight_fate/states/driving_controls.py`, change `handle_event`:

```python
if event.type == pygame.KEYUP:
    if event.key == pygame.K_h:
        self.ctx.audio.stop_horn()
    return
if event.type != pygame.KEYDOWN:
    return
```

Change H press:

```python
elif key == pygame.K_h:
    self.ctx.audio.start_horn()
```

In `src/freight_fate/states/driving.py`, change `exit`:

```python
def exit(self) -> None:
    self.ctx.audio.stop_horn()
    self.ctx.audio.stop_world()
    self.ctx.audio.stop_music(600)
```

- [ ] **Step 5: Verify horn tests**

```powershell
uv run pytest tests/test_driving_features.py::test_horn_loops_while_held_and_stops_on_release tests/test_driving_features.py::test_horn_stops_when_driving_state_exits -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/freight_fate/audio.py src/freight_fate/states/driving_controls.py src/freight_fate/states/driving.py tests/test_driving_features.py
git commit -m "feat(driving): loop horn while held"
```

## Task 5: Tire Wear And Cleaning Maintenance

**Files:**
- Modify: `src/freight_fate/models/profile.py`
- Modify: `src/freight_fate/states/driving_updates.py`
- Modify: `src/freight_fate/states/driving_events.py`
- Modify: `src/freight_fate/states/city.py`
- Create: `tests/test_garage_maintenance.py`
- Modify: `tests/test_driving_features.py`

- [ ] **Step 1: Add failing profile/default tests**

Create `tests/test_garage_maintenance.py`:

```python
from driving_feature_helpers import key_event


def test_profile_defaults_include_tire_wear_and_dirt():
    from freight_fate.models.profile import Profile

    p = Profile(name="Maintenance", current_city="Buffalo")
    assert p.truck_tire_wear_pct == 0.0
    assert p.truck_dirt_pct == 0.0
```

- [ ] **Step 2: Add failing garage service tests**

Append:

```python
def test_garage_services_tires_and_washes_truck(monkeypatch):
    import pygame
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import GarageState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        app.ctx.profile = Profile(name="Maintenance", current_city="Buffalo", money=5000.0)
        app.ctx.profile.truck_tire_wear_pct = 42.0
        app.ctx.profile.truck_dirt_pct = 75.0
        app.push_state(GarageState(app.ctx))

        labels = [item.text for item in app.state.items]
        assert "Service tires" in labels
        assert "Wash truck" in labels

        while app.state.items[app.state.index].text != "Service tires":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.profile.truck_tire_wear_pct == 0.0

        while app.state.items[app.state.index].text != "Wash truck":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.profile.truck_dirt_pct == 0.0
        assert any("washed" in text.lower() for text in spoken)
    finally:
        app.shutdown()
```

- [ ] **Step 3: Run failing tests**

```powershell
uv run pytest tests/test_garage_maintenance.py -q
```

Expected: fail because profile fields and garage items do not exist.

- [ ] **Step 4: Add profile fields**

In `src/freight_fate/models/profile.py`, add to `Profile`:

```python
truck_tire_wear_pct: float = 0.0
truck_dirt_pct: float = 0.0
```

Make sure save/load already preserves dataclass fields. If profile loading filters keys, add these fields to that mapping.

- [ ] **Step 5: Add garage actions**

In `src/freight_fate/states/city.py`, update `GarageState.build_items` to include:

```python
MenuItem("Service tires", self._service_tires,
         help="Replace worn tires and reset tire wear to zero."),
MenuItem("Wash truck", self._wash_truck,
         help="Clean road grime, salt, and mud from the truck."),
```

Add methods:

```python
def _service_tires(self) -> None:
    p = self.ctx.profile
    wear = p.truck_tire_wear_pct
    cost = max(250.0, wear * 18.0)
    if p.money < cost:
        self.ctx.say(f"Not enough money. Tire service costs {cost:,.0f} dollars.")
        return
    p.money -= cost
    p.truck_tire_wear_pct = 0.0
    p.save()
    self.ctx.say(f"Tires serviced for {cost:,.0f} dollars.")

def _wash_truck(self) -> None:
    p = self.ctx.profile
    cost = 75.0
    if p.money < cost:
        self.ctx.say("Not enough money. Truck wash costs 75 dollars.")
        return
    p.money -= cost
    p.truck_dirt_pct = 0.0
    p.save()
    self.ctx.say("Truck washed for 75 dollars.")
```

- [ ] **Step 6: Add accrual test**

Append to `tests/test_driving_features.py`:

```python
def test_driving_adds_tire_wear_and_dirt():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        app.ctx.profile.truck_tire_wear_pct = 0.0
        app.ctx.profile.truck_dirt_pct = 0.0
        driving.truck.velocity_mps = 55.0 / 2.23694

        driving.update(60.0)

        assert app.ctx.profile.truck_tire_wear_pct > 0.0
        assert app.ctx.profile.truck_dirt_pct > 0.0
    finally:
        app.shutdown()
```

- [ ] **Step 7: Implement accrual**

In `src/freight_fate/states/driving_updates.py`, after trip movement updates:

```python
def _update_maintenance_wear(self, moved_mi: float) -> None:
    p = self.ctx.profile
    if p is None or moved_mi <= 0:
        return
    tire_gain = moved_mi * 0.002
    if self.truck.brake > 0.7:
        tire_gain += moved_mi * 0.003
    p.truck_tire_wear_pct = min(100.0, p.truck_tire_wear_pct + tire_gain)
    dirt_mult = 2.0 if self.weather.current.name in {"RAIN", "HEAVY_RAIN", "SNOW"} else 1.0
    p.truck_dirt_pct = min(100.0, p.truck_dirt_pct + moved_mi * 0.01 * dirt_mult)
```

Call it after `pos_before` movement is computed:

```python
moved_mi = max(0.0, self.trip.position_mi - pos_before)
self._update_maintenance_wear(moved_mi)
```

If collision or rumble-strip damage occurs in `driving_updates.py`, add small tire wear there:

```python
self.ctx.profile.truck_tire_wear_pct = min(100.0, self.ctx.profile.truck_tire_wear_pct + 1.0)
```

- [ ] **Step 8: Verify tests**

```powershell
uv run pytest tests/test_garage_maintenance.py tests/test_driving_features.py::test_driving_adds_tire_wear_and_dirt -q
```

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add src/freight_fate/models/profile.py src/freight_fate/states/city.py src/freight_fate/states/driving_updates.py tests/test_garage_maintenance.py tests/test_driving_features.py
git commit -m "feat(garage): add tire and wash maintenance"
```

## Task 6: Changelog, Docs, And Full Verification

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `src/freight_fate/states/main_menu_help.py`
- Possibly modify: `README.md` or `docs/user-manual.md` if current project release docs mention controls/upgrades.

- [ ] **Step 1: Update player-facing help text**

In `src/freight_fate/states/main_menu_help.py`, add concise notes:

```python
"Hold H to sound the horn; release H to stop it.",
"The garage can service tires and wash the truck as maintenance builds up.",
"Hybrid assist lowers fuel use in low-speed city and facility driving.",
"Dispatch job details include dollars per mile so long-haul value is easier to compare.",
```

Put the horn line in Driving basics/information keys, garage lines in The garage, and dispatch value line in Deliveries and money.

- [ ] **Step 2: Update changelog**

Under `## Unreleased`, add one bullet:

```markdown
- **Dispatch, garage, and horn polish.** F1 on a dispatch job now opens a structured job-detail view, long-haul pay has a stronger floor, the horn loops while held, hybrid assist lowers low-speed fuel burn, and the garage can service tire wear and wash road grime.
```

- [ ] **Step 3: Run focused suites**

```powershell
uv run pytest tests/test_dispatch_job_detail.py tests/test_jobs.py tests/test_trucks.py tests/test_garage_maintenance.py tests/test_driving_features.py -q
```

Expected: pass.

- [ ] **Step 4: Run full verification**

```powershell
uv run pytest -q
uv run ruff check src tests tools
```

Expected: both pass.

- [ ] **Step 5: Manual desktop smoke**

Start a source run:

```powershell
Start-Process -FilePath "uv" -ArgumentList @("run", "freight-fate") -WorkingDirectory "C:\Users\joshu\gh-projects\Freight-Fate"
```

Manual checks:

- Open dispatch board, press F1 on a job, verify job details are digestible.
- Press Escape to return to board.
- Hold H while driving and release it; horn should start and stop.
- Open garage and verify tire/wash/hybrid wording is reachable.

- [ ] **Step 6: Commit final docs/help**

```powershell
git add CHANGELOG.md src/freight_fate/states/main_menu_help.py README.md docs/user-manual.md
git commit -m "docs: update gameplay polish notes"
```

If `README.md` or `docs/user-manual.md` are unchanged, omit them from `git add`.

## Self-Review

Spec coverage:

- Dispatch F1 detail view: Task 1.
- Hybrid assist: Task 3.
- Looping horn: Task 4.
- Tire wear and cleaning: Task 5.
- Long-haul pay: Task 2.
- Help/changelog/full verification: Task 6.

No horn-required hazards are included. That is intentional and matches the approved correction.

Completeness scan: no unfinished markers or unspecified implementation notes remain. Any conditional notes name the exact fallback behavior.

Type consistency: public names used across tasks are `JobDetailState`, `equipment_text`, `long_haul_pay_floor`, `hybrid_assist`, `start_horn`, `stop_horn`, `truck_tire_wear_pct`, and `truck_dirt_pct`.
