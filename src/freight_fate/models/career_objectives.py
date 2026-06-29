"""Derived career objectives for terminal and dispatch-board guidance."""

from __future__ import annotations

from dataclasses import dataclass

from .business import (
    AUTHORITY_ACTIVATION_LEVEL,
    AUTHORITY_READY_LEVEL,
    AUTHORITY_READY_WORKING_CAPITAL,
    COMPANY_DRIVER,
    INDEPENDENT_AUTHORITY,
    OWNER_OPERATOR_DELIVERIES,
    OWNER_OPERATOR_LEVEL,
    OWNER_OPERATOR_REPUTATION,
    OWNER_OPERATOR_WORKING_CAPITAL,
    authority_activation_eligibility,
    authority_readiness_eligibility,
    carrier_name,
    is_owner_operator,
    owner_operator_eligibility,
)
from .career_training import TrainingStage, training_guidance


@dataclass(frozen=True)
class CareerObjective:
    title: str
    terminal_text: str
    dispatch_text: str
    recommendation: str

    @property
    def spoken_summary(self) -> str:
        return f"{self.title}. {self.terminal_text} {self.dispatch_text}"


def career_objective(profile) -> CareerObjective:
    """Return the current practical career objective without changing saves."""
    status = getattr(profile, "business_status", COMPANY_DRIVER)
    if status == INDEPENDENT_AUTHORITY:
        return _independent_authority_objective(profile)
    if is_owner_operator(status):
        return _owner_operator_objective(profile)
    return _company_driver_objective(profile)


def _company_driver_objective(profile) -> CareerObjective:
    guidance = training_guidance(profile)
    if guidance.stage is not TrainingStage.NORMAL_GUIDANCE:
        return CareerObjective(
            guidance.title,
            guidance.terminal_text,
            guidance.dispatch_text,
            guidance.recommendation_label,
        )
    if profile.career.reputation < 70:
        return CareerObjective(
            "Build dispatcher trust",
            f"{carrier_name(profile)} is watching on-time service, damage, and steady miles.",
            "Pick reliable lanes before chasing specialty freight.",
            "reliable unlocked lane",
        )
    eligible, _ = owner_operator_eligibility(profile)
    if eligible:
        return CareerObjective(
            "Owner-operator buy-in ready",
            "Business status has the truck buy-in available if you want more responsibility.",
            "Company loads still pay safely while you decide whether to buy in.",
            "clean company load",
        )
    if profile.career.level >= OWNER_OPERATOR_LEVEL - 3:
        return CareerObjective(
            "Owner-operator preparation",
            (
                f"Work toward level {OWNER_OPERATOR_LEVEL}, "
                f"{OWNER_OPERATOR_DELIVERIES} deliveries, "
                f"{OWNER_OPERATOR_REPUTATION:.0f} reputation, and a cash cushion."
            ),
            "Choose freight that protects reputation and builds savings.",
            "steady earning lane",
        )
    return CareerObjective(
        "Trusted company driver",
        "Keep building seniority, clean service, endorsements, and better carrier lanes.",
        "Unlocked freight with good time margins is the strongest career move.",
        "trusted carrier lane",
    )


def _owner_operator_objective(profile) -> CareerObjective:
    if profile.money < OWNER_OPERATOR_WORKING_CAPITAL * 2:
        return CareerObjective(
            "Protect working capital",
            "Fuel, maintenance, insurance, trailer programs, and truck wear come out of your cash.",
            "Favor unlocked loads with clear take-home and avoid stretching the reserve.",
            "cash-positive load",
        )
    eligible, _ = authority_readiness_eligibility(profile)
    if eligible:
        return CareerObjective(
            "Authority prep ready",
            "Business status can set aside the reserve for your own-authority plan.",
            "Keep taking freight that protects the reserve until you make that move.",
            "reserve-safe load",
        )
    if profile.career.level >= AUTHORITY_READY_LEVEL - 2:
        return CareerObjective(
            "Authority preparation",
            (
                f"Build reputation, deliveries, and at least "
                f"{AUTHORITY_READY_WORKING_CAPITAL:,.0f} dollars in working capital."
            ),
            "The strongest loads are the ones that leave room for fuel, repairs, and trailer costs.",
            "owner-operator margin load",
        )
    return CareerObjective(
        "Prove the truck",
        "Run clean leased-on freight while your reputation and cash reserve grow.",
        "Compare take-home estimates and trailer needs before accepting.",
        "clean leased-on load",
    )


def _independent_authority_objective(profile) -> CareerObjective:
    eligible, _ = authority_activation_eligibility(profile)
    if eligible:
        return CareerObjective(
            "Authority activation ready",
            "Business status can activate your own authority when you are ready.",
            "Direct freight is available, but keep enough cash for compliance and trailer costs.",
            "direct freight with margin",
        )
    if profile.career.level < AUTHORITY_ACTIVATION_LEVEL:
        return CareerObjective(
            "Grow direct freight reputation",
            "Protect service quality while you build toward stronger direct contracts.",
            "Compare gross pay against authority costs before taking a lane.",
            "direct freight with margin",
        )
    return CareerObjective(
        "Independent contract growth",
        "Use reputation, trailer fit, and cash reserves to choose better direct freight.",
        "The best contract is the one you can deliver cleanly and settle profitably.",
        "profitable direct freight",
    )
