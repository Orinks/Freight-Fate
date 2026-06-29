# Traffic Bubble Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an experimental `TrafficManager` that owns nearby NPC traffic around the truck while preserving the current player-facing traffic APIs.

**Architecture:** Add a focused traffic manager module under `src/freight_fate/sim/` and migrate `Trip` to delegate NPC spawn, update, lead-vehicle lookup, status, and cue generation through it. Keep compatibility methods/properties during the first pass so driving, adaptive cruise, status menus, and harness tests keep working while internals move behind the manager.

**Tech Stack:** Python dataclasses, existing Freight Fate trip simulation, pytest, Hypothesis-backed harness tests, Ruff.

---

## File Structure

- Create `src/freight_fate/sim/traffic_manager.py`
  - Owns `TrafficVehicle`, `TrafficSituation`, and `TrafficManager`.
  - Contains deterministic spawning, bubble pruning, per-frame update, lead selection, status text, warning text, and cue dedupe helpers.
- Modify `src/freight_fate/sim/trip.py`
  - Create `TrafficManager` during `Trip.__init__`.
  - Delegate NPC updates and cue checks to manager methods.
  - Keep `npc_vehicles` compatibility property while tests migrate.
- Modify `src/freight_fate/sim/trip_traffic.py`
  - Re-route existing public traffic methods to `self.traffic_manager`.
  - Remove old NPC spawn/update internals after manager integration.
- Modify `src/freight_fate/sim/trip_models.py`
  - Keep `TrafficContext` and `TrafficPressure`.
  - Keep the existing `NPCVehicle` dataclass as a compatibility type for this slice.
- Modify `src/freight_fate/states/driving_menu_states.py`
  - Read nearby traffic from `trip.traffic_manager.vehicles` for the driver app's traffic page.
- Modify `tests/test_weather_trip.py`, `tests/test_trip_cues.py`, `tests/test_driving_cruise_weather.py`
  - Add manager unit/integration coverage and migrate direct `trip.npc_vehicles` assignments where practical.
- Modify `tests/playtest_harness.py` and `tests/test_playtest_harness.py`
  - Add manager scenario helpers and keep headless transcript coverage.
- Create `tests/test_traffic_manager.py`
  - Low-cost manager tests that do not construct `App`.

## Task 1: Add Traffic Manager Types

**Files:**
- Create: `src/freight_fate/sim/traffic_manager.py`
- Test: `tests/test_traffic_manager.py`

- [ ] **Step 1: Write failing tests for traffic vehicle compatibility and lead selection**

Create `tests/test_traffic_manager.py`:

```python
"""Traffic bubble manager tests."""

from freight_fate.data.world import get_world
from freight_fate.sim.traffic_manager import TrafficManager, TrafficVehicle
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherSystem


def _manager(seed: int = 1) -> TrafficManager:
    world = get_world()
    route = world.route_from_cities(["Chicago", "Indianapolis"])
    truck = TruckState()
    weather = WeatherSystem("great_lakes", seed=1)
    return TrafficManager(
        route=route,
        truck=truck,
        weather=weather,
        leg_starts=[0.0],
        seed=seed,
        start_hour=8.0,
        hazard_scale=1.0,
        imperial=True,
    )


def test_traffic_vehicle_keeps_npc_compatibility_properties():
    vehicle = TrafficVehicle(
        key="traffic:test",
        position_mi=12.5,
        speed_mph=44.0,
        target_speed_mph=40.0,
        relative_lane=1,
        intent="merging",
        vehicle_class="car",
    )

    assert vehicle.at_mi == 12.5
    assert vehicle.end_mi > vehicle.at_mi
    assert vehicle.lane_text == "right lane"
    assert vehicle.reason == "merging traffic"


def test_lead_vehicle_selects_nearest_vehicle_in_player_lane():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("left", 5.1, 55.0, 55.0, -1, "passing", "car"),
        TrafficVehicle("far", 6.0, 45.0, 45.0, 0, "following", "semi"),
        TrafficVehicle("near", 5.3, 42.0, 42.0, 0, "braking", "car"),
    ]

    context = manager.lead_vehicle(position_mi=5.0, truck_speed_mph=60.0)

    assert context is not None
    assert context.lead.key == "near"
    assert context.closing_mph == 18.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_traffic_manager.py -q
```

Expected: FAIL because `freight_fate.sim.traffic_manager` does not exist.

- [ ] **Step 3: Implement minimal traffic manager types and lead selection**

Create `src/freight_fate/sim/traffic_manager.py`:

```python
"""Small NPC traffic bubble around the player's truck."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from ..data.world import Leg, Route
from .hos import is_night
from .trip_models import RUSH_HOUR_WINDOWS, TRAFFIC_LOOKAHEAD_MI, TrafficContext


@dataclass
class TrafficVehicle:
    key: str
    position_mi: float
    speed_mph: float
    target_speed_mph: float
    relative_lane: int
    intent: str
    vehicle_class: str
    length_mi: float = 0.25

    @property
    def at_mi(self) -> float:
        return self.position_mi

    @property
    def end_mi(self) -> float:
        return self.position_mi + self.length_mi

    @property
    def lane_text(self) -> str:
        if self.relative_lane < 0:
            return "left lane"
        if self.relative_lane > 0:
            return "right lane"
        return "your lane"

    @property
    def behavior(self) -> str:
        return {
            "cruising": "steady_truck",
            "following": "slow_car",
            "merging": "merging_vehicle",
            "braking": "braking_traffic",
            "passing": "passing_vehicle",
            "yielding": "slow_car",
        }.get(self.intent, "steady_truck")

    @property
    def reason(self) -> str:
        return {
            "cruising": "steady truck traffic",
            "following": "slow car ahead",
            "merging": "merging traffic",
            "braking": "brake lights ahead",
            "passing": "passing traffic",
            "yielding": "yielding traffic",
        }.get(self.intent, "traffic ahead")


@dataclass(frozen=True)
class TrafficSituation:
    kind: str
    vehicle: TrafficVehicle
    message: str
    interrupt: bool = False


class TrafficManager:
    def __init__(
        self,
        *,
        route: Route,
        truck,
        weather,
        leg_starts: list[float],
        seed: int | None,
        start_hour: float,
        hazard_scale: float,
        imperial: bool,
    ) -> None:
        self.route = route
        self.truck = truck
        self.weather = weather
        self.leg_starts = list(leg_starts)
        self.seed = seed
        self.start_hour = start_hour
        self.hazard_scale = hazard_scale
        self.imperial = imperial
        self.vehicles: list[TrafficVehicle] = []
        self.announced_vehicle_keys: set[str] = set()

    def lead_vehicle(
        self, *, position_mi: float, truck_speed_mph: float
    ) -> TrafficContext | None:
        best: TrafficContext | None = None
        for vehicle in self.vehicles:
            if vehicle.relative_lane != 0:
                continue
            gap = vehicle.position_mi - position_mi
            if gap < -vehicle.length_mi or gap > TRAFFIC_LOOKAHEAD_MI:
                continue
            closing = max(0.0, truck_speed_mph - vehicle.speed_mph)
            context = TrafficContext(vehicle, max(0.0, gap), closing)
            if best is None or context.gap_mi < best.gap_mi:
                best = context
        return best
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
uv run pytest tests/test_traffic_manager.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/freight_fate/sim/traffic_manager.py tests/test_traffic_manager.py
git commit -m "feat: add traffic bubble manager types"
```

## Task 2: Move Deterministic Spawn Into TrafficManager

**Files:**
- Modify: `src/freight_fate/sim/traffic_manager.py`
- Test: `tests/test_traffic_manager.py`

- [ ] **Step 1: Add failing deterministic spawn tests**

Append to `tests/test_traffic_manager.py`:

```python
from freight_fate.sim.weather import WeatherKind


def _signature(manager: TrafficManager) -> list[tuple[float, float, int, str, str]]:
    return [
        (
            round(vehicle.position_mi, 2),
            round(vehicle.speed_mph, 1),
            vehicle.relative_lane,
            vehicle.intent,
            vehicle.vehicle_class,
        )
        for vehicle in manager.vehicles
    ]


def test_spawn_is_deterministic_for_same_route_and_seed():
    first = _manager(seed=1)
    second = _manager(seed=1)

    first.spawn_initial_traffic()
    second.spawn_initial_traffic()

    assert _signature(first)
    assert _signature(first) == _signature(second)


def test_bad_weather_slows_spawned_traffic_without_moving_it():
    clear = _manager(seed=1)
    rain = _manager(seed=1)
    rain.weather.current = WeatherKind.HEAVY_RAIN

    clear.spawn_initial_traffic()
    rain.spawn_initial_traffic()

    assert _signature(clear)
    assert [v.position_mi for v in rain.vehicles] == [v.position_mi for v in clear.vehicles]
    assert min(v.speed_mph for v in rain.vehicles) < min(v.speed_mph for v in clear.vehicles)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_traffic_manager.py -q
```

Expected: FAIL because `spawn_initial_traffic` does not exist.

- [ ] **Step 3: Implement deterministic spawn**

Add these methods and constants to `src/freight_fate/sim/traffic_manager.py`:

```python
    def _seed_key(self) -> str:
        route_key = "|".join(
            f"{city}:{leg.highway}:{leg.miles:.1f}"
            for city, leg in zip(self.route.cities, self.route.legs, strict=False)
        )
        return f"traffic-manager:{self.seed}:{route_key}"

    def _rng(self) -> random.Random:
        digest = hashlib.sha256(self._seed_key().encode("utf-8")).hexdigest()
        return random.Random(int(digest[:16], 16))

    def _rush_hour_traffic_bias(self, leg: Leg) -> float:
        if not any(start <= self.start_hour < end for start, end in RUSH_HOUR_WINDOWS):
            return 0.0
        return 0.14 if leg.checkpoints else 0.06

    def _leg_density(self, leg: Leg, weather_slowdown: float, night: bool) -> float:
        metro_bias = 0.18 if leg.checkpoints else 0.0
        night_bias = -0.08 if night else 0.0
        rush_bias = self._rush_hour_traffic_bias(leg)
        density = min(
            0.86,
            max(
                0.05,
                0.22 + leg.miles / 900.0 + metro_bias
                + weather_slowdown / 100.0 + night_bias + rush_bias,
            ),
        )
        return density * self.hazard_scale

    def _weather_slowdown(self) -> float:
        effects = self.weather.effects
        return max(
            0.0,
            min(
                14.0,
                (1.0 - effects.grip) * 20.0
                + max(0.0, 3.0 - effects.visibility_mi) * 1.4,
            ),
        )

    def spawn_initial_traffic(self) -> None:
        rng = self._rng()
        vehicles: list[TrafficVehicle] = []
        weather_slowdown = self._weather_slowdown()
        night = is_night(self.start_hour)
        for leg_index, (start, leg) in enumerate(
            zip(self.leg_starts, self.route.legs, strict=True)
        ):
            if leg.miles < 35.0:
                continue
            density = self._leg_density(leg, weather_slowdown, night)
            slots = max(1, int(leg.miles / 85.0))
            for slot in range(slots):
                if rng.random() > min(0.92, density + 0.18):
                    continue
                span = leg.miles / slots
                low = max(4.0, slot * span + 8.0)
                high = min(leg.miles - 6.0, (slot + 1) * span + 4.0)
                if high <= low:
                    continue
                intent = rng.choices(
                    ("cruising", "following", "merging", "braking", "passing"),
                    weights=(3.0, 1.5, 1.2, 1.0, 1.1),
                )[0]
                vehicle_class = rng.choices(
                    ("car", "box truck", "semi", "service vehicle"),
                    weights=(5.0, 1.4, 2.0, 0.3),
                )[0]
                base_speed = {
                    "cruising": rng.uniform(52.0, 64.0),
                    "following": rng.uniform(42.0, 55.0),
                    "merging": rng.uniform(38.0, 52.0),
                    "braking": rng.uniform(35.0, 48.0),
                    "passing": rng.uniform(62.0, 75.0),
                }[intent]
                rush_slowdown = (
                    rng.uniform(4.0, 10.0) if self._rush_hour_traffic_bias(leg) else 0.0
                )
                speed = max(25.0, base_speed - weather_slowdown - rush_slowdown)
                lane = -1 if intent == "passing" else 0
                if intent == "merging":
                    lane = 1
                vehicles.append(TrafficVehicle(
                    key=f"traffic:{leg_index}:{slot}:{intent}",
                    position_mi=start + rng.uniform(low, high),
                    speed_mph=speed,
                    target_speed_mph=speed,
                    relative_lane=lane,
                    intent=intent,
                    vehicle_class=vehicle_class,
                ))
        self.vehicles = sorted(vehicles, key=lambda vehicle: vehicle.position_mi)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
uv run pytest tests/test_traffic_manager.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/freight_fate/sim/traffic_manager.py tests/test_traffic_manager.py
git commit -m "feat: spawn deterministic traffic bubbles"
```

## Task 3: Add Bubble Update, Pruning, And Situations

**Files:**
- Modify: `src/freight_fate/sim/traffic_manager.py`
- Test: `tests/test_traffic_manager.py`

- [ ] **Step 1: Add failing update and situation tests**

Append to `tests/test_traffic_manager.py`:

```python
def test_update_moves_and_prunes_vehicles_outside_bubble():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("behind", -3.0, 55.0, 55.0, 0, "cruising", "semi"),
        TrafficVehicle("ahead", 2.0, 55.0, 55.0, 0, "cruising", "semi"),
    ]

    manager.update(dt=1.0, position_mi=0.0, time_scale=20.0)

    assert [vehicle.key for vehicle in manager.vehicles] == ["ahead"]
    assert manager.vehicles[0].position_mi > 2.2


def test_merging_vehicle_moves_into_player_lane_and_creates_situation():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("merge", 0.8, 42.0, 42.0, 1, "merging", "car")
    ]

    manager.update(dt=0.0, position_mi=0.0, time_scale=20.0)
    situation = manager.next_situation(position_mi=0.0, truck_speed_mph=55.0)

    assert manager.vehicles[0].relative_lane == 0
    assert situation is not None
    assert situation.kind == "merging"
    assert "Merging" in situation.message


def test_braking_vehicle_slows_and_creates_lead_situation():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("brake", 0.7, 45.0, 45.0, 0, "braking", "car")
    ]

    manager.update(dt=1.0, position_mi=0.0, time_scale=20.0)
    situation = manager.next_situation(position_mi=0.0, truck_speed_mph=60.0)

    assert manager.vehicles[0].target_speed_mph < 45.0
    assert situation is not None
    assert situation.kind == "braking"
    assert "Brake lights" in situation.message
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_traffic_manager.py -q
```

Expected: FAIL because `update` and `next_situation` do not exist or do not handle these cases.

- [ ] **Step 3: Implement update, pruning, and situations**

Add to `TrafficManager`:

```python
    def _gap_text(self, miles: float) -> str:
        if self.imperial:
            return f"{miles:.1f} miles"
        return f"{miles * 1.609344:.1f} kilometers"

    def _speed_value(self, mph: float) -> str:
        if self.imperial:
            return f"{mph:.0f}"
        return f"{mph * 1.609344:.0f}"

    def update(self, *, dt: float, position_mi: float, time_scale: float) -> None:
        game_hours = dt * time_scale / 3600.0
        kept: list[TrafficVehicle] = []
        for vehicle in self.vehicles:
            gap = vehicle.position_mi - position_mi
            if vehicle.intent == "merging" and 0.0 <= gap <= 1.4:
                vehicle.relative_lane = 0
            if vehicle.intent == "braking" and 0.0 <= gap <= 1.8:
                vehicle.target_speed_mph = max(30.0, vehicle.target_speed_mph - 8.0 * dt)
            delta = vehicle.target_speed_mph - vehicle.speed_mph
            vehicle.speed_mph += max(-6.0 * dt, min(4.0 * dt, delta))
            vehicle.position_mi += max(0.0, vehicle.speed_mph) * game_hours
            if -2.0 <= vehicle.position_mi - position_mi <= 10.0:
                kept.append(vehicle)
        self.vehicles = sorted(kept, key=lambda vehicle: vehicle.position_mi)

    def next_situation(
        self, *, position_mi: float, truck_speed_mph: float
    ) -> TrafficSituation | None:
        context = self.lead_vehicle(
            position_mi=position_mi,
            truck_speed_mph=truck_speed_mph,
        )
        if context is None or context.gap_mi > 2.2:
            return None
        vehicle = context.lead
        if vehicle.key in self.announced_vehicle_keys:
            return None
        gap = self._gap_text(context.gap_mi)
        speed = self._speed_value(vehicle.speed_mph)
        if vehicle.intent == "merging":
            message = (
                f"Merging {vehicle.vehicle_class} {gap} ahead. Hold your lane, "
                f"leave a gap, and be ready for {speed}."
            )
            kind = "merging"
        elif vehicle.intent == "braking":
            message = f"Brake lights {gap} ahead. Ease down and leave room for {speed}."
            kind = "braking"
        elif vehicle.intent == "following":
            message = f"Slow {vehicle.vehicle_class} {gap} ahead. Be ready near {speed}."
            kind = "lead"
        else:
            return None
        self.announced_vehicle_keys.add(vehicle.key)
        return TrafficSituation(kind, vehicle, message, interrupt=True)
```

Keep `time_scale` as an explicit argument so the manager follows the active trip pacing without owning the trip clock.

- [ ] **Step 4: Run tests**

Run:

```powershell
uv run pytest tests/test_traffic_manager.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/freight_fate/sim/traffic_manager.py tests/test_traffic_manager.py
git commit -m "feat: update traffic bubble behavior"
```

## Task 4: Integrate TrafficManager With Trip

**Files:**
- Modify: `src/freight_fate/sim/trip.py`
- Modify: `src/freight_fate/sim/trip_traffic.py`
- Modify: `src/freight_fate/sim/trip_models.py`
- Test: `tests/test_weather_trip.py`
- Test: `tests/test_trip_cues.py`

- [ ] **Step 1: Add failing Trip integration assertions**

Update `tests/test_weather_trip.py::test_npc_traffic_seeding_is_deterministic`:

```python
    assert hasattr(trip_a, "traffic_manager")
    assert trip_a.npc_vehicles is trip_a.traffic_manager.vehicles
```

Update `tests/test_trip_cues.py::test_traffic_context_and_warning_are_grounded_in_lead_vehicle` to use the manager:

```python
    trip.traffic_manager.vehicles = [
        NPCVehicle("npc:queue", 10.0, 45.0, 45.0, 0, "braking_traffic")
    ]
```

Expected current failure: `traffic_manager` does not exist.

- [ ] **Step 2: Run failing tests**

Run:

```powershell
uv run pytest tests/test_weather_trip.py::test_npc_traffic_seeding_is_deterministic tests/test_trip_cues.py::test_traffic_context_and_warning_are_grounded_in_lead_vehicle -q
```

Expected: FAIL because `Trip.traffic_manager` is missing.

- [ ] **Step 3: Wire Trip to TrafficManager**

In `src/freight_fate/sim/trip.py`, import:

```python
from .traffic_manager import TrafficManager
```

Replace:

```python
self.npc_vehicles = self._place_npc_traffic()
```

with:

```python
self.traffic_manager = TrafficManager(
    route=self.route,
    truck=self.truck,
    weather=self.weather,
    leg_starts=self._leg_starts,
    seed=self._seed,
    start_hour=self.start_hour,
    hazard_scale=self.hazard_scale,
    imperial=self.imperial,
)
self.traffic_manager.spawn_initial_traffic()
```

Add compatibility property to `Trip`:

```python
    @property
    def npc_vehicles(self):
        return self.traffic_manager.vehicles

    @npc_vehicles.setter
    def npc_vehicles(self, vehicles) -> None:
        self.traffic_manager.vehicles = vehicles
```

Replace in `Trip.update`:

```python
self._update_npc_traffic(dt)
```

with:

```python
self.traffic_manager.update(
    dt=dt,
    position_mi=self.position_mi,
    time_scale=self.time_scale,
)
```

- [ ] **Step 4: Delegate public traffic methods**

In `src/freight_fate/sim/trip_traffic.py`, replace `_npc_context`, `traffic_context`, `traffic_target_speed`, `npc_traffic_status`, `_npc_warning_message`, and `_check_npc_traffic_cues` with manager-backed methods:

```python
    def traffic_context(self) -> TrafficContext | None:
        return self.traffic_manager.lead_vehicle(
            position_mi=self.position_mi,
            truck_speed_mph=self.truck.speed_mph,
        )

    def traffic_target_speed(self) -> float | None:
        context = self.traffic_context()
        if context is None:
            return None
        return context.lead.speed_mph

    def npc_traffic_status(self) -> str:
        context = self.traffic_context()
        if context is None:
            return "Traffic: no close traffic ahead."
        lead = context.lead
        return (
            f"Traffic: {lead.reason} {self._gap_text(context.gap_mi)} ahead "
            f"in {lead.lane_text}, moving {self._speed_value(lead.speed_mph)}."
        )

    def _check_npc_traffic_cues(self) -> None:
        situation = self.traffic_manager.next_situation(
            position_mi=self.position_mi,
            truck_speed_mph=self.truck.speed_mph,
        )
        if situation is None:
            return
        cue = NavigationCue(
            f"traffic:{situation.vehicle.key}",
            "traffic",
            situation.vehicle.position_mi,
            situation.vehicle.reason,
            speed_mph=situation.vehicle.speed_mph,
        )
        self._emit(
            TripEventKind.GPS_CUE,
            situation.message,
            cue=cue,
            npc_vehicle=situation.vehicle,
        )
```

Keep imports for `NavigationCue`, `TrafficContext`, and `TripEventKind`. Remove the `NPCVehicle` import from `trip_traffic.py` after this replacement because cue generation no longer needs an `isinstance` check there.

- [ ] **Step 5: Keep `NPCVehicle` import compatibility without circular imports**

Keep the existing `NPCVehicle` dataclass in `src/freight_fate/sim/trip_models.py` for this experimental slice. Update `TrafficManager` methods to work with any vehicle object that has `key`, `position_mi`, `speed_mph`, `target_speed_mph`, `relative_lane`, `behavior`, `reason`, `lane_text`, and `length_mi`. Do not import `TrafficVehicle` into `trip_models.py`; that would create a circular dependency because `traffic_manager.py` imports `TrafficContext` from `trip_models.py`.

Where `TrafficManager` checks intent, use:

```python
intent = getattr(vehicle, "intent", None)
behavior = getattr(vehicle, "behavior", "")
is_merging = intent == "merging" or behavior == "merging_vehicle"
is_braking = intent == "braking" or behavior == "braking_traffic"
is_following = intent == "following" or behavior == "slow_car"
```

The minimum rule: existing tests that import `NPCVehicle` from `freight_fate.sim.trip` must still pass.

- [ ] **Step 6: Run focused integration tests**

Run:

```powershell
uv run pytest tests/test_traffic_manager.py tests/test_weather_trip.py::test_npc_traffic_seeding_is_deterministic tests/test_weather_trip.py::test_npc_traffic_moves_each_trip_tick tests/test_weather_trip.py::test_npc_traffic_cue_and_status_are_reviewable tests/test_trip_cues.py::test_traffic_context_and_warning_are_grounded_in_lead_vehicle -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/freight_fate/sim/trip.py src/freight_fate/sim/trip_traffic.py src/freight_fate/sim/trip_models.py tests/test_weather_trip.py tests/test_trip_cues.py
git commit -m "feat: route trip traffic through manager"
```

## Task 5: Migrate Cruise, Status, And Harness Helpers

**Files:**
- Modify: `tests/test_driving_cruise_weather.py`
- Modify: `tests/playtest_harness.py`
- Modify: `tests/test_playtest_harness.py`
- Modify: `src/freight_fate/states/driving_menu_states.py`

- [ ] **Step 1: Update harness helper to set manager vehicles**

In `tests/playtest_harness.py`, change `add_npc_traffic_ahead` from:

```python
self.driving.trip.npc_vehicles = [vehicle]
```

to:

```python
self.driving.trip.traffic_manager.vehicles = [vehicle]
```

Also change neutralization:

```python
self.driving.trip.traffic_manager.vehicles = []
```

Keep `self.driving.trip.npc_vehicles == []` assertions only if the compatibility property remains.

- [ ] **Step 2: Update cruise tests to use manager**

In `tests/test_driving_cruise_weather.py`, replace direct assignments:

```python
driving.trip.npc_vehicles = [
    NPCVehicle("npc:acc", driving.trip.position_mi + 0.08,
               44.0, 44.0, 0, "braking_traffic")
]
```

with:

```python
driving.trip.traffic_manager.vehicles = [
    NPCVehicle("npc:acc", driving.trip.position_mi + 0.08,
               44.0, 44.0, 0, "braking_traffic")
]
```

Apply the same pattern to the weather-gap cruise test.

- [ ] **Step 3: Run harness and cruise tests**

Run:

```powershell
uv run pytest tests/test_playtest_harness.py tests/test_driving_cruise_weather.py -q
```

Expected: PASS.

- [ ] **Step 4: Update driver-app traffic status lines**

In `src/freight_fate/states/driving_menu_states.py`, keep the public Trip API and update only the internal iteration in `_next_traffic_line`:

```python
for lead in getattr(d.trip.traffic_manager, "vehicles", []):
    ahead = lead.position_mi - pos
```

Run:

```powershell
uv run pytest tests/test_driving_features.py::test_status_menu_reports_traffic -q
```

```powershell
uv run pytest tests/test_driving_features.py tests/test_info_keys.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add tests/playtest_harness.py tests/test_playtest_harness.py tests/test_driving_cruise_weather.py src/freight_fate/states/driving_menu_states.py
git commit -m "test: migrate traffic harness to manager"
```

## Task 6: Remove Direct NPC List Assumptions From Core Tests

**Files:**
- Modify: `tests/test_weather_trip.py`
- Modify: `tests/test_trip_cues.py`
- Modify: `tests/test_smoke.py`
- Modify: `tests/driving_feature_helpers.py`

- [ ] **Step 1: Replace direct list mutation with helper**

Add to `tests/driving_feature_helpers.py`:

```python
def set_trip_traffic(driving, vehicles):
    driving.trip.traffic_manager.vehicles = list(vehicles)
```

Change `quiet_trip` from:

```python
driving.trip.npc_vehicles = []
```

to:

```python
driving.trip.traffic_manager.vehicles = []
```

- [ ] **Step 2: Update smoke and trip tests**

In `tests/test_smoke.py`, replace:

```python
driving.trip.npc_vehicles = []
```

with:

```python
driving.trip.traffic_manager.vehicles = []
```

In `tests/test_weather_trip.py` and `tests/test_trip_cues.py`, replace test setup assignments with:

```python
trip.traffic_manager.vehicles = [
    NPCVehicle("npc:queue", 10.0, 45.0, 45.0, 0, "braking_traffic")
]
```

- [ ] **Step 3: Keep compatibility assertions**

Add one compatibility test to `tests/test_weather_trip.py`:

```python
def test_npc_vehicles_property_tracks_traffic_manager(world):
    trip, _truck = make_trip(world)
    vehicle = NPCVehicle("npc:compat", 5.0, 55.0, 55.0, 0, "steady_truck")

    trip.npc_vehicles = [vehicle]

    assert trip.traffic_manager.vehicles == [vehicle]
    assert trip.npc_vehicles == [vehicle]
```

- [ ] **Step 4: Run migrated tests**

Run:

```powershell
uv run pytest tests/test_weather_trip.py tests/test_trip_cues.py tests/test_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_weather_trip.py tests/test_trip_cues.py tests/test_smoke.py tests/driving_feature_helpers.py
git commit -m "test: use traffic manager in trip tests"
```

## Task 7: Full Focused Verification And Cleanup

**Files:**
- Modify only files required by Ruff or failing tests.

- [ ] **Step 1: Search for stale direct internals**

Run:

```powershell
rg -n "trip\\.npc_vehicles|self\\.npc_vehicles|_place_npc_traffic|_update_npc_traffic|_npc_context|_npc_warning_message" src tests
```

Expected:

- No production references to `_place_npc_traffic`, `_update_npc_traffic`, `_npc_context`, or `_npc_warning_message`.
- `trip.npc_vehicles` references only in the compatibility test, or none if compatibility is removed.

- [ ] **Step 2: Run focused traffic verification**

Run:

```powershell
uv run pytest tests/test_traffic_manager.py tests/test_weather_trip.py tests/test_trip_cues.py tests/test_driving_cruise_weather.py tests/test_playtest_harness.py -q
```

Expected: PASS.

- [ ] **Step 3: Run broader relevant gameplay verification**

Run:

```powershell
uv run pytest tests/test_driving_features.py tests/test_driving_exits.py tests/test_info_keys.py tests/test_smoke.py -q
```

Expected: PASS.

- [ ] **Step 4: Run Ruff**

Run:

```powershell
uv run ruff check src/freight_fate/sim src/freight_fate/states tests/test_traffic_manager.py tests/test_weather_trip.py tests/test_trip_cues.py tests/test_driving_cruise_weather.py tests/test_playtest_harness.py tests/playtest_harness.py
```

Expected: PASS.

- [ ] **Step 5: Commit cleanup when files changed**

If Step 1-4 changed any files:

```powershell
git add src tests
git commit -m "refactor: clean up traffic manager migration"
```

If Step 1-4 produced no file changes, record that in the handoff summary and skip this commit.

## Task 8: Experimental Branch Summary

**Files:**
- Modify: `docs/superpowers/specs/2026-06-29-traffic-bubble-manager-design.md` only if implementation materially differs from the spec.

- [ ] **Step 1: Confirm spec still matches implementation**

Run:

```powershell
git diff origin/codex/player-experience-integration...HEAD --stat
```

Read:

```powershell
Get-Content docs/superpowers/specs/2026-06-29-traffic-bubble-manager-design.md
```

Expected: implementation matches the spec's Traffic Bubble Manager approach.

- [ ] **Step 2: Run final status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree on `codex/traffic-manager-player`.

- [ ] **Step 3: Prepare handoff summary**

Summarize:

- new files and architecture;
- preserved public APIs;
- tests passed;
- known experimental limits;
- explicit note that this is based on `codex/player-experience-integration`, not `dev`.

Do not merge into `dev` from this branch without explicit approval.
