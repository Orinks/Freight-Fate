# Debt Payoff + Direct Truck Dealer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let drivers pay their carried balance from cash at terminals and truck stops, and replace the drive-to-city-services flow with a direct Truck dealer menu item.

**Architecture:** Pure money helpers in `models/solvency.py`; a small `PayDebtState` menu reused from the terminal and rest-stop menus; deletion of the `city_service` driving phase with a save-compat drop; source-backed dealer names read from the kept `city_services.json` data.

**Tech Stack:** Python 3.12, pytest, existing MenuState framework.

Spec: `docs/superpowers/specs/2026-08-13-debt-dealer-radio-design.md` sections A and B.

## Global Constraints

- Branch: `feat/debt-dealer-radio` (off `feat/career-1.9`). Push direct, no PR (owner directive for the 1.9 line).
- Run tests through the test-runner agent, never a second parallel pytest.
- Spoken text: plain player language, amounts as "1,234 dollars" via `solvency.money_text`. Canonical nouns per `docs/ontology.md`.
- Files stay at or below 1000 lines (`city.py` is 1786 — do not grow it beyond the new state and item; if it crosses further, note it, don't restructure here).
- Every commit: `[skip changelog]` EXCEPT the final changelog/roadmap commit.
- Headless: set `FREIGHT_FATE_NO_SPEECH=1` when running anything game-adjacent.

---

### Task 1: Solvency payoff helpers

**Files:**
- Modify: `src/freight_fate/models/solvency.py` (append after `advance_refused_reason`)
- Test: `tests/test_debt_and_standing.py` (append)

**Interfaces:**
- Produces: `PAYOFF_CASH_CUSHION = 200.0`, `PAYOFF_MIN_CASH = 10.0`,
  `out_of_pocket_options(profile) -> list[tuple[str, float]]` (kinds `"all"`, `"half"`, `"cushion"`),
  `pay_out_of_pocket(profile, amount: float) -> float` (returns what was actually paid).

- [ ] **Step 1: Write the failing tests** (follow the existing profile-fixture style already in `tests/test_debt_and_standing.py` — it builds profiles with `fines_owed`/`money` directly):

```python
def _payer(money, owed):
    p = _profile()  # reuse this file's existing profile helper
    p.money = money
    p.fines_owed = owed
    return p


def test_payoff_options_full_coverage():
    from freight_fate.models.solvency import out_of_pocket_options

    opts = dict(out_of_pocket_options(_payer(money=5_000.0, owed=1_000.0)))
    assert opts["all"] == 1_000.0
    assert opts["half"] == 500.0
    # cushion amount (4800) exceeds the balance, so it clamps to it and
    # duplicates "all" -- deduplicated away.
    assert "cushion" not in opts


def test_payoff_options_partial_coverage():
    from freight_fate.models.solvency import out_of_pocket_options

    opts = dict(out_of_pocket_options(_payer(money=800.0, owed=2_000.0)))
    assert "all" not in opts
    assert opts["half"] == 800.0  # half the balance is 1000, capped at cash
    assert opts["cushion"] == 600.0  # cash minus the 200 cushion


def test_payoff_options_hidden_when_broke_or_clear():
    from freight_fate.models.solvency import out_of_pocket_options

    assert out_of_pocket_options(_payer(money=9.0, owed=500.0)) == []
    assert out_of_pocket_options(_payer(money=500.0, owed=0.5)) == []
    assert out_of_pocket_options(_payer(money=-50.0, owed=500.0)) == []


def test_pay_out_of_pocket_clamps_and_clears():
    from freight_fate.models.solvency import pay_out_of_pocket

    p = _payer(money=800.0, owed=600.0)
    assert pay_out_of_pocket(p, 600.0) == 600.0
    assert p.fines_owed == 0.0
    assert p.money == 200.0

    p = _payer(money=100.0, owed=600.0)
    assert pay_out_of_pocket(p, 999.0) == 100.0  # never below zero cash
    assert p.money == 0.0
    assert p.fines_owed == 500.0

    p = _payer(money=100.0, owed=600.0)
    assert pay_out_of_pocket(p, 0.0) == 0.0  # no-op stays a no-op
```

- [ ] **Step 2: Run tests, verify the new ones fail** with ImportError on `out_of_pocket_options`.

Run (test-runner agent): `uv run pytest tests/test_debt_and_standing.py -p no:xdist -q`

- [ ] **Step 3: Implement in `solvency.py`** under a new section comment `# -- paying it down from cash ------------`:

```python
PAYOFF_CASH_CUSHION = 200.0
PAYOFF_MIN_CASH = 10.0


def out_of_pocket_options(profile) -> list[tuple[str, float]]:
    """What a driver holding cash may put toward the balance, right now.

    Kinds: "all" when cash covers the whole balance, "half" for half of it
    capped at cash, "cushion" for everything above a fuel cushion. Amounts
    under a dollar or duplicating an earlier option are dropped.
    """
    balance = max(0.0, float(getattr(profile, "fines_owed", 0.0) or 0.0))
    cash = float(getattr(profile, "money", 0.0) or 0.0)
    if balance < 1.0 or cash < PAYOFF_MIN_CASH:
        return []
    options: list[tuple[str, float]] = []

    def _offer(kind: str, amount: float) -> None:
        amount = round(amount, 2)
        if amount >= 1.0 and all(abs(amount - a) >= 0.01 for _, a in options):
            options.append((kind, amount))

    if cash >= balance:
        _offer("all", balance)
    _offer("half", min(balance / 2.0, cash))
    _offer("cushion", min(balance, cash - PAYOFF_CASH_CUSHION))
    return options


def pay_out_of_pocket(profile, amount: float) -> float:
    """Move cash onto the balance; returns what was actually paid.

    Clamped so cash never goes below zero and the balance never below it.
    """
    balance = max(0.0, float(getattr(profile, "fines_owed", 0.0) or 0.0))
    cash = float(getattr(profile, "money", 0.0) or 0.0)
    paid = round(min(max(0.0, float(amount)), balance, max(0.0, cash)), 2)
    if paid < 0.01:
        return 0.0
    profile.fines_owed = round(balance - paid, 2)
    profile.money = round(cash - paid, 2)
    return paid
```

- [ ] **Step 4: Run the file's tests, verify all pass** (same command).
- [ ] **Step 5: Commit** `feat(solvency): out-of-pocket payoff helpers [skip changelog]`

---

### Task 2: Spoken pointers in the debt lines

**Files:**
- Modify: `src/freight_fate/models/solvency.py` (`debt_warning_line` rungs 1-2 full form, `debt_line`)
- Test: `tests/test_debt_and_standing.py`

**Interfaces:**
- Consumes: nothing new. Produces: unchanged signatures, new sentence in three strings.

- [ ] **Step 1: Failing tests** — assert the exact sentence appears in the non-terse rung 1 and rung 2 warnings and in `debt_line`, and does NOT appear in the terse forms or the hard-capped line:

```python
POINTER = "You can also pay it down from cash at any terminal or truck stop."


def test_debt_lines_point_at_out_of_pocket_payoff():
    from freight_fate.models import solvency

    p = _payer(money=500.0, owed=1_000.0)  # rung 1 for a fresh company driver
    assert POINTER in solvency.debt_warning_line(p)
    assert POINTER not in solvency.debt_warning_line(p, terse=True)
    assert POINTER in solvency.debt_line(p)
```

- [ ] **Step 2: Run, verify fails.**
- [ ] **Step 3: Implement** — append the sentence to the rung 1 and rung 2 full-form return strings and to the non-hard-capped `debt_line` string. Do not touch rung 3, terse forms, or the hard-capped branches.
- [ ] **Step 4: Run, verify passes.** Also rerun the whole file: earlier string-equality tests may need the sentence added.
- [ ] **Step 5: Commit** `feat(solvency): debt lines point at cash payoff [skip changelog]`

---

### Task 3: PayDebtState and the terminal menu item

**Files:**
- Modify: `src/freight_fate/states/city.py` (`CityMenuState.build_items`, new `PayDebtState` beside `BobtailDestState`)
- Test: `tests/test_debt_and_standing.py` (or the harness file where `CityMenuState(` tests live, e.g. `tests/test_business_arc.py` style — follow whichever pattern builds a ctx + CityMenuState)

**Interfaces:**
- Consumes: `solvency.out_of_pocket_options`, `solvency.pay_out_of_pocket`, `solvency.money_text`, `solvency.debt_owed`.
- Produces: `PayDebtState(ctx)` MenuState importable from `.city` (Task 4 reuses it).

- [ ] **Step 1: Failing test** — with a profile owing 1,000 with 5,000 cash, `CityMenuState.build_items()` labels include `"Pay down what you owe: 1,000 dollars owed"`; with `fines_owed=0` the label is absent. Then drive `PayDebtState`: invoking the "all" option leaves `fines_owed == 0`, money reduced, and the spoken text (capture via the test harness's say recorder, same as neighboring menu tests) contains "your account is clear".
- [ ] **Step 2: Run, verify fails.**
- [ ] **Step 3: Implement.** In `CityMenuState.build_items`, insert after the Garage item:

```python
if solvency.out_of_pocket_options(self.ctx.profile):
    items.insert(  # right behind the garage: the money cluster
        items.index(next(i for i in items if i.action == self._business_status)),
        MenuItem(
            self._pay_debt_label,
            self._pay_debt,
            help="Put your own cash toward the balance you owe, instead "
            "of waiting for settlement collection. You choose how much; "
            "cash never goes below zero.",
        ),
    )
```

(If `MenuItem` comparison by action is awkward in this file, append next to the garage item positionally — match how `_pay_advance_available` inserts at a fixed index.) Label + handler:

```python
def _pay_debt_label(self) -> str:
    owed = solvency.money_text(solvency.debt_owed(self.ctx.profile))
    return f"Pay down what you owe: {owed} owed"

def _pay_debt(self) -> None:
    self.ctx.push_state(PayDebtState(self.ctx))
```

New state, modeled on `BobtailDestState`:

```python
class PayDebtState(MenuState):
    title = "Pay down what you owe"
    intro_help = (
        "Choose how much of your own cash to put toward the balance. "
        "Escape backs out without paying."
    )

    _LABELS = {
        "all": "Pay it all: {amount}",
        "half": "Pay half: {amount}",
        "cushion": "Pay what you can, keeping a 200 dollar cushion: {amount}",
    }

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(
            f"You owe {solvency.money_text(solvency.debt_owed(p))} and have "
            f"{solvency.money_text(p.money)}. {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                self._LABELS[kind].format(amount=solvency.money_text(amount)),
                lambda a=amount: self._pay(a),
                help="A quarter of every settlement also keeps paying it down.",
            )
            for kind, amount in solvency.out_of_pocket_options(self.ctx.profile)
        ]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _pay(self, amount: float) -> None:
        p = self.ctx.profile
        paid = solvency.pay_out_of_pocket(p, amount)
        if paid < 0.01:
            self.ctx.audio.play("ui/error")
            self.ctx.say("That amount is no longer payable. Check the options again.")
            self.refresh()
            return
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        if solvency.debt_owed(p) < 1.0:
            self.ctx.say(
                f"Paid {solvency.money_text(paid)} and your account is clear. "
                "Every settlement reaches you in full again. You have "
                f"{solvency.money_text(p.money)}.",
                interrupt=True,
            )
            self.ctx.pop_state()
            return
        self.ctx.say(
            f"Paid {solvency.money_text(paid)} toward what you owed. You have "
            f"{solvency.money_text(p.money)}, and "
            f"{solvency.money_text(solvency.debt_owed(p))} still owed.",
            interrupt=True,
        )
        self.refresh()
```

- [ ] **Step 4: Run, verify passes.**
- [ ] **Step 5: Commit** `feat(city): pay down debt from cash at the terminal [skip changelog]`

---

### Task 4: Same item at truck stops

**Files:**
- Modify: `src/freight_fate/states/driving_rest_states.py` (`RestStopState.build_items`, after the repair item block)
- Test: same file as Task 3's tests

**Interfaces:**
- Consumes: `PayDebtState` from `.city`, `solvency` helpers.

- [ ] **Step 1: Failing test** — `RestStopState.build_items()` for an indebted, cash-holding profile contains the payoff label; absent when clear.
- [ ] **Step 2: Run, verify fails.**
- [ ] **Step 3: Implement** — in `RestStopState.build_items`, after the `"repair" in actions` block:

```python
from ..models import solvency  # module-top import, matching the file's style

if solvency.out_of_pocket_options(self.ctx.profile):
    owed = solvency.money_text(solvency.debt_owed(self.ctx.profile))
    items.append(
        MenuItem(
            f"Pay down what you owe: {owed} owed",
            self._pay_debt,
            help="Put your own cash toward the balance you owe, "
            "right from this stop.",
        )
    )
```

with `def _pay_debt(self): from .city import PayDebtState; self.ctx.push_state(PayDebtState(self.ctx))` (local import mirrors how this file already imports city states lazily).

- [ ] **Step 4: Run, verify passes.**
- [ ] **Step 5: Commit** `feat(rest): pay down debt from cash at truck stops [skip changelog]`

---

### Task 5: Direct Truck dealer menu item

**Files:**
- Modify: `src/freight_fate/states/city.py` (`build_items` at line ~270: replace the "Drive to city services" item; `_city_services` handler replaced by `_truck_dealer`)
- Modify: `src/freight_fate/states/city_business.py` (`TruckShopState.announce_entry`, `intro_help`)
- Test: Task 3's test file

**Interfaces:**
- Consumes: `TruckShopState` (already imported into `city.py`), `world.city_service(city, "truck_dealer").name`.

- [ ] **Step 1: Failing tests** — terminal menu labels include `"Truck dealer"` and no longer include `"Drive to city services"`; entering it lands on `TruckShopState`; its spoken entry for a city with source-backed data (Indianapolis, per `tests/test_city_services.py`) contains that dealer's real `name`.
- [ ] **Step 2: Run, verify fails.**
- [ ] **Step 3: Implement.** Menu item:

```python
MenuItem(
    "Truck dealer",
    self._truck_dealer,
    help="Browse tractors at the local dealer. Owner-operators buy "
    "and switch here; company drivers can look at what the fleet "
    "may assign next.",
),
```

`def _truck_dealer(self): self.ctx.push_state(TruckShopState(self.ctx))` (import from `.city_business` alongside the file's existing imports). In `TruckShopState.announce_entry`:

```python
def announce_entry(self) -> None:
    p = self.ctx.profile
    dealer = ""
    try:
        service = self.ctx.world.city_service(p.current_city, "truck_dealer")
        if not service.fallback:
            dealer = f"Inside {service.name}. "
    except KeyError:
        pass
    self.ctx.say(f"{dealer}Trucks. You have {p.money:,.0f} dollars. {self.current_text()}")
```

and drop the trailing "Escape returns to the garage." sentence from `intro_help` (it now also opens from the terminal): end at "Company drivers use carrier-assigned equipment."

- [ ] **Step 4: Run, verify passes.**
- [ ] **Step 5: Commit** `feat(city): direct truck dealer menu item [skip changelog]`

---

### Task 6: Remove the city-service drive machinery

**Files:**
- Modify: `src/freight_fate/states/city.py` (delete `CityServiceSelectState` and the now-unused `Job`/route plumbing it owned)
- Modify: `src/freight_fate/states/driving.py`, `driving_core.py`, `driving_controls.py`, `driving_menu_states.py`, `driving_events.py`, `driving_updates.py` (every `DRIVE_PHASE_CITY_SERVICE` branch and `city_service_key` parameter)
- Modify: `src/freight_fate/states/main_menu.py` (`_world_entry_state`)
- Modify: `src/freight_fate/data/world_services.py` (delete `city_service_route`, `city_service_approach`, `city_service_geometry`; KEEP `city_services`, `city_service`, `_fallback_city_service`)
- Test: `tests/test_city_services.py` (data tests stay; route/approach tests deleted), plus a new save-compat test

**Interfaces:**
- Consumes: nothing new. Produces: `DRIVE_PHASE_CITY_SERVICE` no longer exists anywhere.

- [ ] **Step 1: Write the save-compat failing test** (in `tests/test_city_services.py`):

```python
def test_city_service_snapshot_drops_to_terminal(app_ctx):  # use this repo's
    # standard headless app fixture; mirror how main-menu resume tests build it
    p = app_ctx.profile
    p.active_trip = {"kind": "city_service_drive", "job": {}, "trip_seed": 1}
    from freight_fate.states.main_menu import _world_entry_state
    state = _world_entry_state(app_ctx)
    from freight_fate.states.city import CityMenuState
    assert isinstance(state, CityMenuState)
    assert p.active_trip is None
    assert any("retired" in line for line in app_ctx.spoken_lines())
```

(Adapt fixture/recorder names to what neighboring resume tests actually use — read one first.)

- [ ] **Step 2: Run, verify fails** (currently it builds a DrivingState).
- [ ] **Step 3: Implement, in this order:**
  1. `main_menu._world_entry_state`: before the `from_snapshot` dispatch add

```python
if p.active_trip.get("kind") == "city_service_drive":
    p.active_trip = None
    ctx.say(
        "Local service drives were retired in this update; "
        "you are parked at the terminal."
    )
    return CityMenuState(ctx, queue_entry_announcement=True)
```

  2. Delete `CityServiceSelectState` from `city.py` and the `_city_services` remnants.
  3. Delete `DRIVE_PHASE_CITY_SERVICE` from `driving_core.py`, then chase every compile error: `driving.py` (constructor arg `city_service_key`, snapshot kind `city_service_drive` writer, `from_snapshot` branch), `driving_controls.py`, `driving_menu_states.py` (the two phase filters), `driving_events.py` (`_enter_city_service`, `_open_city_service`, `_city_service_text`, the ahead-announcement branch), `driving_updates.py:475` branch.
  4. `world_services.py`: remove the three route/approach/geometry methods and the module constants only they used (`CITY_SERVICE_APPROACH_MILES`, `CITY_SERVICE_APPROACH_ROADS`). Keep `city_services`/`city_service` and the fallback.
  5. `tests/test_city_services.py`: delete route/approach/geometry assertions (lines ~30-32 and friends); keep source-backed data tests.
- [ ] **Step 4: Byte-compile + targeted tests:** `uv run python -m compileall src tests tools`, then (test-runner agent) `uv run pytest tests/test_city_services.py tests/test_world.py -p no:xdist -q`, then a sweep: `grep -rn "city_service" src/` must show only the kept data accessors (`world_services.py`, `world_local_data.py`, `data_resources.py`) and `city_services.json` mentions.
- [ ] **Step 5: Commit** `feat(city)!: retire the drive to city services [skip changelog]`

---

### Task 7: Spoken/help text sweep

**Files:**
- Modify: `src/freight_fate/states/driving_rest_states.py:92` and `:120` ("rest, repairs, and city services" → "rest, repairs, the garage, and the truck dealer")
- Modify: any `main_menu_help.py` / `city.py` help strings naming city services (sweep `grep -rn "city services" src/ docs/`)
- Modify: `docs/ontology.md` — remove/replace the "city services" row if present; add a "truck dealer" row (canonical noun: "truck dealer") if absent
- Test: `tests/test_debt_and_standing.py` or wherever `_suspension_text` is asserted (`grep -rn "city services" tests/`)

- [ ] **Step 1: Sweep and list** every remaining player-facing "city services" string.
- [ ] **Step 2: Reword each**, run the affected test files, fix string assertions.
- [ ] **Step 3: Commit** `fix(speech): suspension and help copy name the real services [skip changelog]`

---

### Task 8: Changelog, roadmap, full suite

**Files:**
- Modify: `CHANGELOG.md` (`## Unreleased`), `ROADMAP.md` (1.9 section)

- [ ] **Step 1: Changelog** (player language, bold lead):

```markdown
### Added
- **You can now pay down what you owe from your own cash.** Whenever you
  carry a balance and have money in hand, the terminal and every truck stop
  offer to pay it all, half, or everything above a 200 dollar fuel cushion.
  Clearing the balance stops settlement collection on the spot.

### Changed
- **The truck dealer is now one menu choice away.** The drive to city
  services is retired: the dealer opens straight from the terminal menu,
  named for the real local dealership where we have one on record. Fuel,
  repairs, rest, and food stay at truck stops and the terminal garage.
```

- [ ] **Step 2: ROADMAP** — add/check bullets under the 1.9 line for both features.
- [ ] **Step 3: Full suite via the test-runner agent:** `uv run pytest` and `uv run ruff check src tests tools`. Fix fallout (grep-visible candidates: transcripts or adversarial tests that drove to city services).
- [ ] **Step 4: Commit** `feat(career): debt payoff and direct truck dealer` (no skip marker — this is the changelog commit).
