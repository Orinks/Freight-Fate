"""Trailer yards, drop-and-hook, live loads, and detention."""

from types import SimpleNamespace

import pytest

from freight_fate.models.jobs import CARGO_CATALOG
from freight_fate.models.trailer_yard import (
    DETENTION_FREE_MIN,
    DROP_HOOK_MIN,
    LIVE_LOAD_MIN,
    MODE_DROP_HOOK,
    MODE_LIVE,
    TrailerUnit,
    detention_charge,
    facility_has_drop_yard,
    pickup_plan,
    yard_trailers,
)


def _job(facility_type="cross_dock", facility_id="fac-1", cargo="general", distance=400.0):
    return SimpleNamespace(
        origin_type=facility_type,
        origin_facility_id=facility_id,
        origin_location="Origin Dock",
        cargo=CARGO_CATALOG[cargo],
        distance_mi=distance,
        weight_tons=14.0,
    )


def _company_driver():
    return SimpleNamespace(owns_equipment=lambda: False, visible_owned_trailers=lambda: ())


def _owner_operator(trailers=("dry_van",)):
    return SimpleNamespace(owns_equipment=lambda: True, visible_owned_trailers=lambda: trailers)


def test_high_volume_freight_stages_trailers_and_a_quarry_does_not():
    """Who keeps a drop yard is a fact about the business, not a dice roll."""
    for facility_type in ("cross_dock", "parcel_hub", "intermodal_ramp", "port_terminal"):
        assert facility_has_drop_yard(facility_type, "any-id"), facility_type
    for facility_type in ("farm_elevator", "mine_quarry"):
        assert not facility_has_drop_yard(facility_type, "any-id"), facility_type


def test_a_maybe_facility_is_the_same_answer_every_time():
    """Derived from the facility, so the yard does not shuffle between visits."""
    answers = {facility_has_drop_yard("dry_warehouse", "warehouse-9") for _ in range(5)}
    assert len(answers) == 1
    # And different warehouses genuinely differ.
    spread = {facility_has_drop_yard("dry_warehouse", f"warehouse-{n}") for n in range(30)}
    assert spread == {True, False}


def test_a_drop_yard_holds_trailers_the_freight_can_actually_go_in():
    from freight_fate.models.trailers import trailer_keys_for_cargo

    units = yard_trailers("cold_storage", "cold-1", "food") or yard_trailers(
        "grocery_retail_dc", "dc-1", "food"
    )
    assert units
    allowed = set(trailer_keys_for_cargo("food"))
    for unit in units:
        assert unit.trailer_key in allowed
        assert unit.number.isdigit()


def test_drop_and_hook_is_far_quicker_than_a_dock():
    plan = pickup_plan(_job(), _company_driver())
    assert plan.mode == MODE_DROP_HOOK
    assert plan.minutes == DROP_HOOK_MIN
    assert plan.minutes < LIVE_LOAD_MIN
    assert plan.trailer is not None
    assert plan.detention_minutes == 0.0


def test_a_live_load_is_the_shippers_hour_and_sometimes_a_lot_more():
    plans = [
        pickup_plan(_job("farm_elevator", f"elev-{n}", "grain", 300.0 + n), _company_driver())
        for n in range(60)
    ]
    assert all(plan.mode == MODE_LIVE for plan in plans)
    assert all(plan.trailer is None for plan in plans)
    assert all(plan.minutes >= LIVE_LOAD_MIN for plan in plans)
    # Most shippers are fine; a real minority are not.
    slow = [plan for plan in plans if plan.minutes > LIVE_LOAD_MIN]
    assert 5 <= len(slow) <= 40, len(slow)


def test_detention_only_starts_after_the_free_time():
    """Two hours free is the real term, and under it nobody owes anybody."""
    plans = [
        pickup_plan(_job("farm_elevator", f"elev-{n}", "grain", 300.0 + n), _company_driver())
        for n in range(120)
    ]
    for plan in plans:
        if plan.minutes <= DETENTION_FREE_MIN:
            assert plan.detention_minutes == 0.0
            assert detention_charge(plan) is None
        else:
            assert plan.detention_minutes == pytest.approx(plan.minutes - DETENTION_FREE_MIN)
            charge = detention_charge(plan)
            assert charge is not None
            # Detention is money coming the other way.
            assert charge.amount < 0.0
            assert "detention" in charge.label


def test_owning_your_trailer_costs_you_drop_and_hook():
    """Nobody swaps an owner-operator's own box for one out of the yard."""
    job = _job()  # a facility that definitely has a drop yard
    assert pickup_plan(job, _company_driver()).is_drop_hook
    plan = pickup_plan(job, _owner_operator())
    assert plan.mode == MODE_LIVE
    assert plan.trailer is None
    assert "your own trailer" in plan.reason
    # An owner-operator without a matching trailer is back on carrier equipment.
    assert pickup_plan(job, _owner_operator(("reefer",))).is_drop_hook


def test_the_same_dispatch_always_comes_with_the_same_trailer():
    """No save state backs this, so it has to be derivable and stable."""
    first = pickup_plan(_job(), _company_driver()).trailer
    again = pickup_plan(_job(), _company_driver()).trailer
    assert first == again


def test_most_of_a_yard_is_serviceable_and_a_few_are_not():
    """A fleet keeps its trailers up; the write-ups have to stay worth noticing."""
    units = [unit for n in range(120) for unit in yard_trailers("cross_dock", f"dc-{n}", "general")]
    assert units
    defective = [unit for unit in units if unit.defect]
    share = len(defective) / len(units)
    assert 0.05 <= share <= 0.30, share


def test_a_trailer_describes_itself_in_driver_words():
    clean = TrailerUnit("4417", "dry_van", 10.0)
    assert clean.defect is None
    text = clean.describe()
    assert "dry van 4417" in text
    assert "good shape" in text

    rough = TrailerUnit("9002", "dry_van", 90.0)
    assert rough.defect
    lowered = rough.describe().lower()
    assert "9002" in lowered
    for marker in ("_", "condition_pct", "none", "key="):
        assert marker not in lowered
