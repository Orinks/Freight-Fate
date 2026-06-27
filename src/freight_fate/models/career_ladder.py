"""Structured 20-level company-driver to owner-operator career ladder."""

from __future__ import annotations

from dataclasses import dataclass

STARTER_CARRIER_NAME = "Northstar Freight Lines"
MAX_CAREER_LEVEL = 20


@dataclass(frozen=True)
class CareerRank:
    level: int
    title: str
    stage: str
    unlock: str
    status: str


CAREER_RANKS: tuple[CareerRank, ...] = (
    CareerRank(
        1,
        "Yard Trainee",
        "Company driver",
        "Starter company tractor and short regional dispatches.",
        "Learning company procedures with carrier-paid equipment.",
    ),
    CareerRank(
        2,
        "New Hire Company Driver",
        "Company driver",
        "Refrigerated freight endorsement.",
        "Running short freight with company dispatch and company equipment.",
    ),
    CareerRank(
        3,
        "Solo Company Driver",
        "Company driver",
        "Heavy-haul freight endorsement.",
        "Trusted for solo regional work and heavier freight.",
    ),
    CareerRank(
        4,
        "Regional Company Driver",
        "Company driver",
        "High-value freight endorsement.",
        "Working broader lanes while the carrier still owns the business risk.",
    ),
    CareerRank(
        5,
        "Owner-Operator Apprentice",
        "Company driver",
        "Business status starts tracking the owner-operator preparation path.",
        "Still a company driver, now learning the money side before any buy-in.",
    ),
    CareerRank(
        6,
        "Regional Fleet Driver",
        "Company driver",
        "Wider regional dispatch access.",
        "Building miles, reputation, and savings on carrier equipment.",
    ),
    CareerRank(
        7,
        "Long-Haul Company Driver",
        "Company driver",
        "Long-haul dispatch becomes routine.",
        "Trusted for longer routes with company tractor and trailer support.",
    ),
    CareerRank(
        8,
        "Trusted Freight Driver",
        "Company driver",
        "More frequent specialized freight opportunities.",
        "A reliable company driver with better freight options.",
    ),
    CareerRank(
        9,
        "High-Value Driver",
        "Company driver",
        "Priority access to fragile and high-value lanes.",
        "Dispatch trusts the driver with higher-consequence freight.",
    ),
    CareerRank(
        10,
        "Lead Company Driver",
        "Company driver",
        "Senior company-driver status.",
        "A veteran company driver, still protected from tractor operating costs.",
    ),
    CareerRank(
        11,
        "Owner-Operator Candidate",
        "Business preparation",
        "Owner-operator qualification checklist appears in full.",
        "Preparing for a leased-on business path without a lease-purchase trap.",
    ),
    CareerRank(
        12,
        "Working Capital Builder",
        "Business preparation",
        "Working-capital target becomes the main business milestone.",
        "Saving cash for repairs, fuel, and slow settlements before the switch.",
    ),
    CareerRank(
        13,
        "Tractor Buy-In Candidate",
        "Business preparation",
        "Tractor buy-in target is active.",
        "Close to a leased-on tractor position, but still on company settlement.",
    ),
    CareerRank(
        14,
        "Leased-On Applicant",
        "Business preparation",
        "Final reputation, delivery, and cash gate before owner-operator.",
        "Dispatch is ready to sponsor the move if the finances are ready.",
    ),
    CareerRank(
        15,
        "Leased-On Owner-Operator",
        "Owner-operator",
        "Leased-on owner-operator buy-in unlocks when other gates are met.",
        "Eligible to buy into a tractor position and pay operating costs.",
    ),
    CareerRank(
        16,
        "Settled Owner-Operator",
        "Owner-operator",
        "Owner-operator settlements become the normal business rhythm.",
        "Learning fuel, maintenance, insurance, trailer, and settlement reserves.",
    ),
    CareerRank(
        17,
        "Established Owner-Operator",
        "Owner-operator",
        "Higher-trust owner-operator status.",
        "Running as a steady leased-on business with clearer upside and costs.",
    ),
    CareerRank(
        18,
        "Equipment Planner",
        "Owner-operator",
        "Trailer and equipment planning becomes the next roadmap hook.",
        "Ready for future trailer ownership or leasing decisions.",
    ),
    CareerRank(
        19,
        "Authority Candidate",
        "Authority preparation",
        "Independent authority readiness appears as an endgame goal.",
        "Learning what full authority would add without turning this into a fleet sim.",
    ),
    CareerRank(
        20,
        "Independent Operator",
        "Authority preparation",
        "Endgame owner-operator status; full authority remains future work.",
        "A completed owner-operator arc, authority-ready but still driving-focused.",
    ),
)


def rank_for_level(level: int) -> CareerRank:
    clamped = max(1, min(MAX_CAREER_LEVEL, int(level)))
    return CAREER_RANKS[clamped - 1]


def next_rank_for_level(level: int) -> CareerRank | None:
    if level >= MAX_CAREER_LEVEL:
        return None
    return rank_for_level(level + 1)
