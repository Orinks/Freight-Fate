"""Dispatch autonomy bands: assigned freight is earned away with seniority."""

from freight_fate.models.business import (
    INDEPENDENT_AUTHORITY,
    LEASED_OWNER_OPERATOR,
)
from freight_fate.models.career import LEVEL_XP, Career
from freight_fate.models.dispatch_policy import (
    NEW_HIRE_DECLINE_BUDGET,
    SENIOR_LOAD_CHOICE_LEVEL,
    declines_remaining,
    dispatch_policy,
)
from freight_fate.models.profile import Profile


def _company_profile(level: int = 1) -> Profile:
    profile = Profile(name="Policy Band", current_city="Chicago")
    profile.career.xp = LEVEL_XP[level - 1]
    assert profile.career.level == level
    return profile


def test_new_hire_company_driver_is_assigned_load_and_route():
    policy = dispatch_policy(_company_profile(level=1))

    assert policy.assigns_load
    assert policy.assigns_route
    assert policy.decline_budget > 0


def test_last_new_hire_level_is_still_assigned_loads():
    policy = dispatch_policy(_company_profile(level=SENIOR_LOAD_CHOICE_LEVEL - 1))

    assert policy.assigns_load
    assert policy.assigns_route


def test_senior_company_driver_chooses_load_but_runs_assigned_route():
    policy = dispatch_policy(_company_profile(level=SENIOR_LOAD_CHOICE_LEVEL))

    assert not policy.assigns_load
    assert policy.assigns_route


def test_leased_owner_operator_chooses_load_and_route():
    profile = _company_profile(level=18)
    profile.business_status = LEASED_OWNER_OPERATOR

    policy = dispatch_policy(profile)

    assert not policy.assigns_load
    assert not policy.assigns_route
    assert policy.decline_budget == 0


def test_independent_authority_chooses_load_and_route():
    profile = _company_profile(level=25)
    profile.business_status = INDEPENDENT_AUTHORITY

    policy = dispatch_policy(profile)

    assert not policy.assigns_load
    assert not policy.assigns_route
    assert policy.decline_budget == 0


def test_decline_budget_counts_down_and_clamps_at_zero():
    profile = _company_profile(level=1)
    assert declines_remaining(profile) == NEW_HIRE_DECLINE_BUDGET

    profile.career.dispatch_declines_used = 2
    assert declines_remaining(profile) == NEW_HIRE_DECLINE_BUDGET - 2

    profile.career.dispatch_declines_used = NEW_HIRE_DECLINE_BUDGET + 5
    assert declines_remaining(profile) == 0


def test_level_up_refills_the_decline_budget():
    career = Career(xp=LEVEL_XP[1] - 100.0)
    career.dispatch_declines_used = NEW_HIRE_DECLINE_BUDGET

    messages = career.record_delivery(200.0, 900.0, on_time=True, damage_pct=0.0)

    assert any("Level up" in message for message in messages)
    assert career.dispatch_declines_used == 0


def test_delivery_without_level_up_keeps_declines_spent():
    career = Career()
    career.dispatch_declines_used = 2

    career.record_delivery(10.0, 100.0, on_time=True, damage_pct=0.0)

    assert career.dispatch_declines_used == 2


def test_old_save_without_decline_field_round_trips():
    profile = Profile(name="Old Save", current_city="Chicago")
    data = profile.to_dict()
    data["career"].pop("dispatch_declines_used", None)

    loaded = Profile.from_dict(data)

    assert loaded.career.dispatch_declines_used == 0

    loaded.career.dispatch_declines_used = 2
    reloaded = Profile.from_dict(loaded.to_dict())
    assert reloaded.career.dispatch_declines_used == 2
