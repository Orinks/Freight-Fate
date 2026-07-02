"""Structured 30-level company-driver to owner-operator career ladder."""

from __future__ import annotations

from dataclasses import dataclass

STARTER_CARRIER_NAME = "Northstar Freight Lines"
MAX_CAREER_LEVEL = 30


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
        "Regional Regular",
        "Company driver",
        "Broader regional lane variety.",
        "A dependable company driver, still on assigned carrier equipment.",
    ),
    CareerRank(
        6,
        "Experienced Company Driver",
        "Company driver",
        "Better company-driver lane quality.",
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
        "Heavy Freight Driver",
        "Company driver",
        "Dispatch now lets you choose your own loads from the board, "
        "with more machinery, construction, and bulk opportunities.",
        "Trusted with heavier freight while the carrier covers operating costs.",
    ),
    CareerRank(
        9,
        "High-Value Company Driver",
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
        "Specialized Company Driver",
        "Senior company driver",
        "Specialized company freight appears more often.",
        "Endorsements and careful service matter more to dispatch.",
    ),
    CareerRank(
        12,
        "Premium Lane Driver",
        "Senior company driver",
        "Better carrier lane quality.",
        "Trusted for premium company freight without personal equipment risk.",
    ),
    CareerRank(
        13,
        "Carrier Mentor Driver",
        "Senior company driver",
        "Stronger reputation weight with dispatch.",
        "A senior company driver with reliable service history.",
    ),
    CareerRank(
        14,
        "Business Prep Driver",
        "Senior company driver",
        "Owner-operator checklist starts to matter.",
        "Learning reserves and settlement risk while still on company wages.",
    ),
    CareerRank(
        15,
        "Owner-Operator Candidate",
        "Business preparation",
        "Working-capital target becomes visible.",
        "Preparing for a leased-on path without a lease-purchase trap.",
    ),
    CareerRank(
        16,
        "Leased-On Applicant",
        "Owner-operator preparation",
        "Leased-on requirements appear in full.",
        "Finalizing delivery, reputation, and cash readiness.",
    ),
    CareerRank(
        17,
        "Tractor Buy-In Candidate",
        "Owner-operator preparation",
        "Tractor buy-in target is active.",
        "Close to a leased-on tractor position, but still on company settlement.",
    ),
    CareerRank(
        18,
        "Leased-On Owner-Operator",
        "Owner-operator",
        "Leased-on owner-operator buy-in unlocks when other gates are met.",
        "Eligible to buy into a tractor position and pay operating costs.",
    ),
    CareerRank(
        19,
        "Settled Owner-Operator",
        "Owner-operator",
        "Owner-operator settlements become the normal business rhythm.",
        "Learning fuel, maintenance, insurance, trailer, and settlement reserves.",
    ),
    CareerRank(
        20,
        "Established Owner-Operator",
        "Owner-operator",
        "Specialty trailer programs matter more.",
        "Running as a steady leased-on business with clearer upside and costs.",
    ),
    CareerRank(
        21,
        "Authority Prep Candidate",
        "Authority preparation",
        "Authority prep reserve can unlock when other gates are met.",
        "Studying full authority while staying focused on one-truck operations.",
    ),
    CareerRank(
        22,
        "Direct Freight Prep",
        "Authority preparation",
        "Direct freight readiness gates become clearer.",
        "Building reputation and working capital before direct broker freight.",
    ),
    CareerRank(
        23,
        "Trailer Strategy Owner",
        "Authority preparation",
        "Trailer ownership planning matters for direct freight.",
        "Choosing when a trailer program is enough and when ownership helps.",
    ),
    CareerRank(
        24,
        "Authority-Ready Operator",
        "Authority preparation",
        "Final authority activation checklist.",
        "Prepared for own authority without simulating a full compliance office.",
    ),
    CareerRank(
        25,
        "Independent Authority Operator",
        "Own authority",
        "Own authority and direct freight unlock when other gates are met.",
        "Direct freight is available with insurance, compliance, and factoring costs.",
    ),
    CareerRank(
        26,
        "Contract Freight Builder",
        "Established owner-operator",
        "Premium direct freight reputation matters more.",
        "Building a stronger one-truck book of repeat freight.",
    ),
    CareerRank(
        27,
        "Specialized Trailer Operator",
        "Established owner-operator",
        "Specialized trailer opportunities stand out.",
        "Matching owned or leased equipment to better freight.",
    ),
    CareerRank(
        28,
        "Premium Lane Operator",
        "Established owner-operator",
        "Premium lanes favor high reputation and the right trailer.",
        "An established owner-operator with strong freight-market choice.",
    ),
    CareerRank(
        29,
        "Veteran Independent Operator",
        "Established owner-operator",
        "Prestige freight and best dispatch quality.",
        "A proven independent driver, not a fleet manager.",
    ),
    CareerRank(
        30,
        "Freight Fate Independent",
        "Established owner-operator",
        "Top career rank.",
        "A complete company-driver to independent owner-operator career.",
    ),
)


def rank_for_level(level: int) -> CareerRank:
    clamped = max(1, min(MAX_CAREER_LEVEL, int(level)))
    return CAREER_RANKS[clamped - 1]


def next_rank_for_level(level: int) -> CareerRank | None:
    if level >= MAX_CAREER_LEVEL:
        return None
    return rank_for_level(level + 1)
