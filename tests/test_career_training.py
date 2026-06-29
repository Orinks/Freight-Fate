from freight_fate.models.career_training import (
    TrainingStage,
    company_training_stage,
    training_guidance,
)
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
