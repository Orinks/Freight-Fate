"""Save-compatible company-driver training guidance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .business import COMPANY_DRIVER, carrier_name
from .start_options import start_option


class TrainingStage(Enum):
    FIRST_DISPATCH = "first_dispatch"
    TRAINER_REMINDERS = "trainer_reminders"
    TRUST_OPENING = "trust_opening"
    TRUST_BUILDING = "trust_building"
    NORMAL_GUIDANCE = "normal_guidance"


@dataclass(frozen=True)
class TrainingGuidance:
    stage: TrainingStage
    title: str
    terminal_text: str
    dispatch_text: str
    recommendation_label: str

    @property
    def spoken_summary(self) -> str:
        return f"{self.title}. {self.terminal_text} {self.dispatch_text}"


def is_company_training_profile(profile) -> bool:
    return getattr(profile, "business_status", COMPANY_DRIVER) == COMPANY_DRIVER


def company_training_stage(profile) -> TrainingStage:
    deliveries = int(getattr(profile.career, "deliveries", 0))
    if deliveries <= 0:
        return TrainingStage.FIRST_DISPATCH
    if deliveries < 3:
        return TrainingStage.TRAINER_REMINDERS
    if deliveries == 3:
        return TrainingStage.TRUST_OPENING
    if deliveries < 10:
        return TrainingStage.TRUST_BUILDING
    return TrainingStage.NORMAL_GUIDANCE


def training_guidance(profile) -> TrainingGuidance:
    stage = company_training_stage(profile)
    carrier = carrier_name(profile)
    option = start_option(getattr(profile, "carrier_key", ""))
    flavor = _carrier_flavor(option.key, carrier)
    if stage is TrainingStage.FIRST_DISPATCH:
        return TrainingGuidance(
            stage,
            "First dispatch",
            f"{carrier} has you on real freight with trainer support close by.",
            f"{flavor} Start with a short standard load that leaves room on the appointment.",
            "trainer-recommended",
        )
    if stage is TrainingStage.TRAINER_REMINDERS:
        return TrainingGuidance(
            stage,
            "First-week service record",
            f"{carrier} is looking for steady service, not perfection, with trainer notes still close by.",
            f"{flavor} Favor short regional freight with clean timing.",
            "good first-week run",
        )
    if stage is TrainingStage.TRUST_OPENING:
        return TrainingGuidance(
            stage,
            "Dispatch trust opening",
            f"{carrier} has enough first-week history to widen the board.",
            "A reliable lane still helps your record more than chasing a difficult load.",
            "good lane to build your record",
        )
    if stage is TrainingStage.TRUST_BUILDING:
        return TrainingGuidance(
            stage,
            "Build dispatcher trust",
            f"{carrier} is watching on-time service, damage, and steady miles.",
            "Pick reliable lanes before chasing specialty freight.",
            "good service-record load",
        )
    return TrainingGuidance(
        stage,
        "Trusted company guidance",
        "Keep building seniority, clean service, endorsements, and better carrier lanes.",
        "Unlocked freight with good time margins is the strongest career move.",
        "trusted carrier lane",
    )


def training_recommendation_score(profile, job) -> float:
    stage = company_training_stage(profile)
    miles = float(getattr(job, "distance_mi", 0.0))
    deadline = float(getattr(job, "deadline_game_h", getattr(job, "deadline_h", 0.0)))
    margin = max(0.0, deadline - miles / 55.0)
    cargo = getattr(getattr(job, "cargo", None), "key", "")
    specialty_penalty = 60.0 if cargo in {"electronics", "machinery", "hazmat"} else 0.0

    if stage is TrainingStage.FIRST_DISPATCH:
        return miles + specialty_penalty - margin * 18.0
    if stage is TrainingStage.TRAINER_REMINDERS:
        return miles * 0.85 + specialty_penalty * 0.5 - margin * 14.0
    if stage in {TrainingStage.TRUST_OPENING, TrainingStage.TRUST_BUILDING}:
        return miles * 0.65 - margin * 20.0 + specialty_penalty * 0.25
    return miles


def _carrier_flavor(key: str, carrier: str) -> str:
    if key == "great_lakes_training":
        return f"{carrier} usually gives new hires extra appointment room."
    if key == "prairie_link":
        return f"{carrier} likes practical regional mileage."
    if key == "summit_value":
        return f"{carrier} rewards appointment discipline."
    return f"{carrier} keeps the first week balanced."
