from freight_fate.models.career_training import (
    TrainingStage,
    company_training_stage,
    training_guidance,
    training_recommendation_score,
)
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.models.start_options import apply_start_option, start_option


def _profile(
    deliveries: int, reputation: float = 75.0, carrier_key: str = "northstar"
) -> Profile:
    profile = Profile(name="Training", current_city="Chicago")
    apply_start_option(profile, start_option(carrier_key))
    profile.career.deliveries = deliveries
    profile.career.reputation = reputation
    return profile


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


def test_company_training_stage_boundaries_do_not_depend_on_perfect_service():
    assert (
        company_training_stage(_profile(0, reputation=35.0))
        is TrainingStage.FIRST_DISPATCH
    )
    assert (
        company_training_stage(_profile(1, reputation=35.0))
        is TrainingStage.TRAINER_REMINDERS
    )
    assert (
        company_training_stage(_profile(2, reputation=35.0))
        is TrainingStage.TRAINER_REMINDERS
    )
    assert (
        company_training_stage(_profile(3, reputation=35.0))
        is TrainingStage.TRUST_OPENING
    )
    assert (
        company_training_stage(_profile(9, reputation=35.0))
        is TrainingStage.TRUST_BUILDING
    )
    assert (
        company_training_stage(_profile(10, reputation=75.0))
        is TrainingStage.NORMAL_GUIDANCE
    )


def test_training_guidance_uses_carrier_flavor_without_probation_wording():
    guidance = training_guidance(_profile(1, carrier_key="great_lakes_training"))

    combined = " ".join(
        (
            guidance.title,
            guidance.terminal_text,
            guidance.dispatch_text,
            guidance.recommendation_label,
        )
    ).lower()
    assert "great lakes training transport" in combined
    assert "trainer" in combined
    assert "probation" not in combined


def test_ten_delivery_guidance_tapers_to_normal_company_driver_voice():
    guidance = training_guidance(_profile(10))

    assert guidance.title == "Trusted company guidance"
    assert "first-week" not in guidance.spoken_summary.lower()
    assert "trainer" not in guidance.spoken_summary.lower()


def test_first_dispatch_recommendation_prefers_short_forgiving_standard_load():
    profile = _profile(0)

    short_standard = _job(70.0, deadline_h=8.0, cargo="general")
    longer_tight = _job(220.0, deadline_h=4.0, cargo="electronics")

    assert training_recommendation_score(
        profile, short_standard
    ) < training_recommendation_score(profile, longer_tight)


def test_trust_building_recommendation_allows_broader_but_still_values_time_margin():
    profile = _profile(5)

    roomy_regional = _job(180.0, deadline_h=10.0, cargo="general")
    tight_short = _job(90.0, deadline_h=2.0, cargo="general")

    assert training_recommendation_score(
        profile, roomy_regional
    ) < training_recommendation_score(profile, tight_short)
