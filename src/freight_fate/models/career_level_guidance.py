"""Save-compatible level-band guidance for the 30-level career ladder."""

from __future__ import annotations

from dataclasses import dataclass

from .business import COMPANY_DRIVER, INDEPENDENT_AUTHORITY, is_owner_operator
from .dispatch_policy import SENIOR_LOAD_CHOICE_LEVEL


@dataclass(frozen=True)
class CareerLevelGuidance:
    title: str
    terminal_text: str
    dispatch_text: str
    recommendation: str
    milestone_text: str

    @property
    def spoken_summary(self) -> str:
        return f"{self.title}. {self.terminal_text} {self.dispatch_text}"


def career_level_guidance(profile) -> CareerLevelGuidance:
    level = int(getattr(profile.career, "level", 1))
    status = getattr(profile, "business_status", COMPANY_DRIVER)

    if status == INDEPENDENT_AUTHORITY:
        if level >= 25:
            return CareerLevelGuidance(
                "Grow a freight business",
                "Use direct customer trust, trailer fit, and cash reserves to shape the freight you want.",
                "direct freight is strongest when it protects margin, service reputation, and repeat work.",
                "direct freight with margin",
                "Independent growth depends on profitable repeat freight.",
            )
        return CareerLevelGuidance(
            "Prove independent authority",
            "Use authority carefully while direct-freight reputation and reserves are still forming.",
            "Favor contracts that protect service quality, cash flow, and your authority record.",
            "authority-building freight",
            "Early authority work is about proving reliability as a carrier.",
        )
    if is_owner_operator(status) and level >= 21:
        return CareerLevelGuidance(
            "Build authority readiness",
            "Keep working capital, trailer strategy, and direct-freight readiness in view.",
            "The best loads leave room for fuel, repairs, trailer support, and authority prep.",
            "authority-readiness lane",
            "Authority prep is about reserves and judgment, not just miles.",
        )
    if is_owner_operator(status):
        return CareerLevelGuidance(
            "Protect owner-operator margin",
            "Treat every dispatch as a business decision with fuel, maintenance, and trailer costs.",
            "Favor freight with clear take-home and enough reserve after settlement.",
            "reserve-safe owner-operator freight",
            "Owner-operator progress depends on margin discipline.",
        )
    if level >= 25:
        return CareerLevelGuidance(
            "Plan the next business step",
            "You have senior company experience; use it to compare buy-in, lease, and authority timing.",
            "Choose freight that keeps reputation high while the business decision stays deliberate.",
            "business-decision lane",
            "Top-level company progress is about choosing the right business risk.",
        )
    if level >= 21:
        return CareerLevelGuidance(
            "Build authority readiness",
            "Keep savings, trailer knowledge, and direct-freight readiness in view before authority is real.",
            "Favor freight that teaches business judgment without pretending the authority is active.",
            "authority-readiness lane",
            "Authority prep is about reserves and judgment, not just miles.",
        )
    if level >= 18:
        return CareerLevelGuidance(
            "Protect owner-operator readiness",
            "Treat better freight as practice for fuel, maintenance, and reserve decisions.",
            "Pick freight with clean take-home and enough room to keep savings growing.",
            "reserve-building freight",
            "Owner-operator readiness depends on margin discipline before the truck is yours.",
        )
    if level >= 14:
        return CareerLevelGuidance(
            "Prepare for owner-operator risk",
            "Build reputation, deliveries, and a cash cushion before taking on truck costs.",
            "Choose freight that protects service quality while savings grow.",
            "business-prep load",
            "Business prep starts before the buy-in appears.",
        )
    if level >= 10:
        return CareerLevelGuidance(
            "Run like a senior company driver",
            "Dispatch trusts you with premium lanes, specialized freight, and mentoring-level judgment.",
            "premium freight still needs clean timing, low damage, and steady service.",
            "senior company lane",
            "Senior company status is about consistency under better freight.",
        )
    if level >= SENIOR_LOAD_CHOICE_LEVEL:
        return CareerLevelGuidance(
            "Choose your own freight",
            "Dispatch now trusts you to pick loads from the board; routing "
            "stays assigned until you run your own truck.",
            "Pick freight that protects on-time service while you build toward senior lanes.",
            "self-picked reliable lane",
            "Load choice is new trust: keep the service record clean.",
        )
    if level >= 4:
        return CareerLevelGuidance(
            "Build a regional service record",
            "broader company lanes are opening, and reputation decides how good the board feels. "
            "Dispatch still assigns your loads until level "
            f"{SENIOR_LOAD_CHOICE_LEVEL}.",
            "Run assigned freight cleanly so endorsements and service turn into better dispatch trust.",
            "reputation-building lane",
            "Regional progress comes from clean, repeatable service.",
        )
    return CareerLevelGuidance(
        "Build first-week trust",
        "Use trainer support and safer freight to start a clean service record.",
        "Short, forgiving freight is still the smartest first move.",
        "good first-week run",
        "First-week trust starts with clean service.",
    )
