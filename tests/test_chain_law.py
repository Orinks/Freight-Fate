"""Chain laws: areas over sustained steep grade, levels from the live
weather, the spoken sign, and the deterministic checkpoint.

The physics (grip multipliers, chain wear, the snap) is pinned in
test_vehicle.py and test_physics_bench.py; these tests cover the law layer
that sits on top of it.
"""

from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from freight_fate.sim.trip import Trip
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherKind, WeatherSystem


def _trip(world, monkeypatch=None, grade=None, **kwargs) -> Trip:
    """A Chicago-Indianapolis trip; optionally with a synthetic grade profile
    patched in before construction so chain-law placement sees it."""
    if monkeypatch is not None and grade is not None:
        monkeypatch.setattr(Trip, "grade_at", lambda self, mile: grade(mile))
    route = world.route_options("Chicago", "Indianapolis")[0]
    truck = TruckState()
    truck.transmission.automatic = True
    return Trip(route, truck, WeatherSystem("great_lakes", seed=1), seed=2, **kwargs)


def _mountain_grade(mile: float) -> float:
    """Flat, except a sustained 6 percent between miles 10 and 14."""
    return 0.06 if 10.0 <= mile <= 14.0 else 0.0


def test_chain_law_areas_sit_over_sustained_steep_grade(world, monkeypatch):
    trip = _trip(world, monkeypatch, _mountain_grade)
    assert len(trip.chain_law_areas) == 1
    start, end = trip.chain_law_areas[0]
    # The area leads the grade by the chain-up pullout and covers the run.
    assert start == pytest.approx(9.5, abs=0.3)
    assert end >= 14.0
    assert trip.chain_law_area_at(12.0) == 0
    assert trip.chain_law_area_at(5.0) is None


def test_short_pitches_do_not_make_a_chain_law(world, monkeypatch):
    # A half-mile 6 percent pitch is a hill, not a chain-control pass.
    trip = _trip(world, monkeypatch, lambda m: 0.06 if 10.0 <= m <= 10.5 else 0.0)
    assert trip.chain_law_areas == []


def test_chain_law_level_follows_the_surface(world):
    trip = _trip(world)
    trip.weather.current = WeatherKind.CLEAR
    assert trip.chain_law_level() == 0
    trip.weather.current = WeatherKind.RAIN
    assert trip.chain_law_level() == 0
    trip.weather.current = WeatherKind.SNOW
    assert trip.chain_law_level() == 1
    trip.weather.current = WeatherKind.ICE
    assert trip.chain_law_level() == 2


def test_chain_law_sign_speaks_on_approach_and_escalates(world, monkeypatch):
    trip = _trip(world, monkeypatch, _mountain_grade)
    trip.weather.current = WeatherKind.SNOW
    trip.position_mi = 9.0  # inside the lookahead of the area at 9.5
    trip._check_chain_law()
    signs = [e for e in trip._events if "chain law in effect" in e.message]
    assert len(signs) == 1
    assert "Level 1" in signs[0].message
    assert "Chain-up area" in signs[0].message
    # The same sign does not repeat, but an escalation to ice speaks again.
    trip._check_chain_law()
    trip.weather.current = WeatherKind.ICE
    trip._check_chain_law()
    signs = [e for e in trip._events if "chain law in effect" in e.message]
    assert len(signs) == 2
    assert "Level 2" in signs[1].message
    # No law, no sign: the areas are silent infrastructure in clear weather.
    trip2 = _trip(world, grade=None)
    trip2.weather.current = WeatherKind.CLEAR
    trip2._check_chain_law()
    assert not [e for e in trip2._events if "chain law" in e.message]


def _law_stub(seed: int, *, level: int, position: float, chains_on: bool, tire_type: str):
    truck = TruckState()
    truck.chains_on = chains_on
    truck.tire_type = tire_type
    truck.velocity_mps = 20.0  # rolling, not stopped at the pullout
    spoken: list[str] = []
    trip = SimpleNamespace(
        chain_law_level=lambda: level,
        chain_law_area_at=lambda mile: 0,
        chain_law_areas=[(0.0, 10.0)],
        position_mi=position,
    )
    ctx = SimpleNamespace(
        profile=SimpleNamespace(money=1000.0),
        say_event=lambda text, interrupt=True: spoken.append(text),
        audio=SimpleNamespace(play=lambda *a, **k: None),
    )
    return SimpleNamespace(
        truck=truck,
        trip=trip,
        ctx=ctx,
        trip_seed=seed,
        ticket_fines_paid=0.0,
        _chain_law_warned=set(),
        _chain_law_cited=set(),
        _spoken=spoken,
    )


def test_chain_checkpoint_is_seeded_and_fines_past_the_midpoint():
    from freight_fate.states.driving_core import (
        CHAIN_LAW_CHECKPOINT_CHANCE,
        CHAIN_LAW_FINE,
    )
    from freight_fate.states.driving_updates import DrivingUpdateMixin

    caught = missed = None
    for seed in range(40):
        roll = random.Random(f"{seed}:chain-law:0:2").random()
        if roll < CHAIN_LAW_CHECKPOINT_CHANCE and caught is None:
            caught = seed
        elif roll >= CHAIN_LAW_CHECKPOINT_CHANCE and missed is None:
            missed = seed
    assert caught is not None and missed is not None

    # Staffed checkpoint: warned once, cited once, fine off the wallet.
    stub = _law_stub(caught, level=2, position=6.0, chains_on=False, tire_type="all_season")
    DrivingUpdateMixin._update_chain_law(stub)
    assert any("without chains" in s for s in stub._spoken)
    assert stub.ctx.profile.money == pytest.approx(1000.0 - CHAIN_LAW_FINE)
    assert stub.ticket_fines_paid == pytest.approx(CHAIN_LAW_FINE)
    # A second tick neither re-warns nor double-fines.
    DrivingUpdateMixin._update_chain_law(stub)
    assert stub.ctx.profile.money == pytest.approx(1000.0 - CHAIN_LAW_FINE)

    # Unstaffed day: the gamble comes off, warning only.
    stub = _law_stub(missed, level=2, position=6.0, chains_on=False, tire_type="all_season")
    DrivingUpdateMixin._update_chain_law(stub)
    assert any("without chains" in s for s in stub._spoken)
    assert stub.ctx.profile.money == pytest.approx(1000.0)

    # Before the midpoint there is warning but no citation roll yet.
    stub = _law_stub(caught, level=2, position=2.0, chains_on=False, tire_type="all_season")
    DrivingUpdateMixin._update_chain_law(stub)
    assert stub.ctx.profile.money == pytest.approx(1000.0)
    assert stub._chain_law_cited == set()


def test_compliance_ends_the_matter():
    from freight_fate.states.driving_updates import DrivingUpdateMixin

    # Chained up: Level 2 has nothing to say.
    stub = _law_stub(1, level=2, position=6.0, chains_on=True, tire_type="all_season")
    DrivingUpdateMixin._update_chain_law(stub)
    assert stub._spoken == []
    assert stub.ctx.profile.money == pytest.approx(1000.0)

    # Winter tires satisfy Level 1 but not Level 2.
    stub = _law_stub(1, level=1, position=6.0, chains_on=False, tire_type="winter")
    DrivingUpdateMixin._update_chain_law(stub)
    assert stub._spoken == []
    stub = _law_stub(1, level=2, position=2.0, chains_on=False, tire_type="winter")
    DrivingUpdateMixin._update_chain_law(stub)
    assert any("without chains" in s for s in stub._spoken)
