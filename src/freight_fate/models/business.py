"""Career business status and settlement economics.

Freight Fate keeps the business arc playable rather than fully accounting-like:
the player starts as a company driver, then can buy into a leased-on
owner-operator track once the 20-level career ladder has enough reputation,
cash, and miles behind it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .career_ladder import STARTER_CARRIER_NAME, next_rank_for_level, rank_for_level
from .jobs import Job
from .start_options import (
    START_MODE_OWNER_OPERATOR,
    option_for_profile,
    pay_plan_for_key,
)
from .trailers import owned_trailer_charge_per_mile, trailer_program_charge_per_mile

COMPANY_DRIVER = "company_driver"
LEASED_OWNER_OPERATOR = "leased_owner_operator"
INDEPENDENT_AUTHORITY = "independent_authority"

OWNER_OPERATOR_PREP_LEVEL = 5
OWNER_OPERATOR_CANDIDATE_LEVEL = 11
OWNER_OPERATOR_LEVEL = 15
OWNER_OPERATOR_REPUTATION = 80.0
OWNER_OPERATOR_DELIVERIES = 35
OWNER_OPERATOR_BUY_IN = 35_000.0
OWNER_OPERATOR_WORKING_CAPITAL = 10_000.0
OWNER_OPERATOR_REVENUE_MULT = 1.12
AUTHORITY_READY_LEVEL = 20
AUTHORITY_READY_DELIVERIES = 60
AUTHORITY_READY_REPUTATION = 90.0
AUTHORITY_READY_RESERVE = 12_500.0
AUTHORITY_READY_WORKING_CAPITAL = 25_000.0
AUTHORITY_ACTIVATION_DELIVERIES = 75
AUTHORITY_ACTIVATION_REPUTATION = 92.0
AUTHORITY_ACTIVATION_COST = 15_000.0
AUTHORITY_ACTIVATION_WORKING_CAPITAL = 35_000.0

OWNER_MAINTENANCE_PER_MILE = 0.18
OWNER_INSURANCE_PER_MILE = 0.09
OWNER_TRAILER_PROGRAM_PER_MILE = 0.12
OWNER_TRUCK_PAYMENT_PER_MILE = 0.22
OWNER_SETTLEMENT_FEE_SHARE = 0.02
AUTHORITY_INSURANCE_PER_MILE = 0.14
AUTHORITY_COMPLIANCE_PER_MILE = 0.06
AUTHORITY_FACTORING_FEE_SHARE = 0.035


@dataclass(frozen=True)
class BusinessCharge:
    label: str
    amount: float


@dataclass(frozen=True)
class BusinessSettlement:
    status: str
    status_label: str
    gross_pay: float
    driver_charges: float
    business_charges: tuple[BusinessCharge, ...]
    net_before_advance: float

    @property
    def business_charge_total(self) -> float:
        return round(sum(charge.amount for charge in self.business_charges), 2)

    @property
    def business_charge_summary(self) -> str:
        if not self.business_charges:
            return "none"
        return ", ".join(
            f"{charge.label} {charge.amount:,.0f} dollars"
            for charge in self.business_charges
        )


def is_owner_operator(status: str) -> bool:
    return status in {LEASED_OWNER_OPERATOR, INDEPENDENT_AUTHORITY}


def has_independent_authority(profile) -> bool:
    return getattr(profile, "business_status", COMPANY_DRIVER) == INDEPENDENT_AUTHORITY


def status_label(status: str) -> str:
    if status == INDEPENDENT_AUTHORITY:
        return "own authority"
    if is_owner_operator(status):
        return "leased-on owner-operator"
    return "company driver"


def pay_label(status: str) -> str:
    if status == INDEPENDENT_AUTHORITY:
        return "Direct gross"
    if status == LEASED_OWNER_OPERATOR:
        return "Gross revenue"
    return "Carrier gross"


def player_pays_operating_costs(status: str) -> bool:
    return is_owner_operator(status)


def carrier_name(profile) -> str:
    return str(getattr(profile, "carrier_name", STARTER_CARRIER_NAME) or STARTER_CARRIER_NAME)


def carrier_key(profile) -> str:
    return str(getattr(profile, "carrier_key", "") or "")


def has_authority_readiness(profile) -> bool:
    return bool(getattr(profile, "authority_readiness", False))


def authority_readiness_eligibility(profile) -> tuple[bool, tuple[str, ...]]:
    """Whether an owner-operator can set aside an authority-readiness reserve."""
    if has_authority_readiness(profile):
        return False, ("Authority readiness reserve is already set.",)
    if not is_owner_operator(getattr(profile, "business_status", COMPANY_DRIVER)):
        return False, ("Become a leased-on owner-operator first.",)

    reasons: list[str] = []
    if profile.career.level < AUTHORITY_READY_LEVEL:
        rank = rank_for_level(AUTHORITY_READY_LEVEL)
        reasons.append(f"Reach level {AUTHORITY_READY_LEVEL}: {rank.title}.")
    if profile.career.deliveries < AUTHORITY_READY_DELIVERIES:
        reasons.append(f"Complete {AUTHORITY_READY_DELIVERIES} deliveries.")
    if profile.career.reputation < AUTHORITY_READY_REPUTATION:
        reasons.append(f"Build reputation to {AUTHORITY_READY_REPUTATION:.0f}.")
    needed_cash = AUTHORITY_READY_RESERVE + AUTHORITY_READY_WORKING_CAPITAL
    if profile.money < needed_cash:
        reasons.append(
            f"Have {needed_cash:,.0f} dollars first: "
            f"{AUTHORITY_READY_RESERVE:,.0f} for the reserve plus "
            f"{AUTHORITY_READY_WORKING_CAPITAL:,.0f} working capital."
        )
    if profile.pay_advance >= 1.0:
        reasons.append("Pay off your dispatcher advance.")
    return not reasons, tuple(reasons)


def authority_activation_eligibility(profile) -> tuple[bool, tuple[str, ...]]:
    """Whether a prepared owner-operator can activate own authority."""
    if has_independent_authority(profile):
        return False, ("Own authority is already active.",)
    if not is_owner_operator(getattr(profile, "business_status", COMPANY_DRIVER)):
        return False, ("Become a leased-on owner-operator first.",)

    reasons: list[str] = []
    if not has_authority_readiness(profile):
        reasons.append("Set the authority prep reserve first.")
    if profile.career.deliveries < AUTHORITY_ACTIVATION_DELIVERIES:
        reasons.append(f"Complete {AUTHORITY_ACTIVATION_DELIVERIES} deliveries.")
    if profile.career.reputation < AUTHORITY_ACTIVATION_REPUTATION:
        reasons.append(f"Build reputation to {AUTHORITY_ACTIVATION_REPUTATION:.0f}.")
    trailer_programs = set(profile.active_trailer_programs())
    if not (trailer_programs - {"dry_van"}):
        reasons.append("Add at least one specialty trailer program.")
    needed_cash = AUTHORITY_ACTIVATION_COST + AUTHORITY_ACTIVATION_WORKING_CAPITAL
    if profile.money < needed_cash:
        reasons.append(
            f"Have {needed_cash:,.0f} dollars first: "
            f"{AUTHORITY_ACTIVATION_COST:,.0f} for authority startup plus "
            f"{AUTHORITY_ACTIVATION_WORKING_CAPITAL:,.0f} working capital."
        )
    if profile.pay_advance >= 1.0:
        reasons.append("Pay off your dispatcher advance.")
    return not reasons, tuple(reasons)


def owner_operator_eligibility(profile) -> tuple[bool, tuple[str, ...]]:
    """Whether the profile can buy into owner-operator status now."""
    if is_owner_operator(getattr(profile, "business_status", COMPANY_DRIVER)):
        return False, ("You are already running as an owner-operator.",)

    reasons: list[str] = []
    if profile.career.level < OWNER_OPERATOR_LEVEL:
        rank = rank_for_level(OWNER_OPERATOR_LEVEL)
        reasons.append(f"Reach level {OWNER_OPERATOR_LEVEL}: {rank.title}.")
    if profile.career.deliveries < OWNER_OPERATOR_DELIVERIES:
        reasons.append(f"Complete {OWNER_OPERATOR_DELIVERIES} deliveries.")
    if profile.career.reputation < OWNER_OPERATOR_REPUTATION:
        reasons.append(f"Build reputation to {OWNER_OPERATOR_REPUTATION:.0f}.")
    needed_cash = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL
    if profile.money < needed_cash:
        reasons.append(
            f"Save {needed_cash:,.0f} dollars: {OWNER_OPERATOR_BUY_IN:,.0f} "
            f"for the truck buy-in and {OWNER_OPERATOR_WORKING_CAPITAL:,.0f} "
            "for working capital."
        )
    if profile.pay_advance >= 1.0:
        reasons.append("Pay off your dispatcher advance.")
    return not reasons, tuple(reasons)


def business_path_label(profile) -> str:
    rank = rank_for_level(profile.career.level)
    option = option_for_profile(profile)
    return (
        f"{carrier_name(profile)}. Level {rank.level}: {rank.title}. "
        f"{rank.stage}. {option.menu_summary}"
    )


def next_business_unlock(profile) -> str:
    status = getattr(profile, "business_status", COMPANY_DRIVER)
    if status == INDEPENDENT_AUTHORITY:
        return (
            "Own authority active. Direct freight is available on the dispatch "
            "board, with insurance, compliance, and factoring costs in settlement."
        )
    if is_owner_operator(status):
        if has_authority_readiness(profile):
            ok, reasons = authority_activation_eligibility(profile)
            if ok:
                return "Next: activate own authority from Business status."
            return (
                "Own authority locked: " + " ".join(reasons)
            )
        ok, reasons = authority_readiness_eligibility(profile)
        if ok:
            return (
                "Next: set aside an authority prep reserve from Business "
                "status."
            )
        if profile.career.level >= 20:
            return (
                "Authority prep locked: " + " ".join(reasons)
            )
        next_rank = next_rank_for_level(profile.career.level)
        if next_rank is None:
            return "You are at the top career rank."
        return f"Next: level {next_rank.level}, {next_rank.title}. {next_rank.unlock}"

    ok, reasons = owner_operator_eligibility(profile)
    if ok:
        return (
            "Next: buy into a leased-on owner-operator tractor position from "
            "Business status."
        )
    if profile.career.level < OWNER_OPERATOR_LEVEL - 1:
        next_rank = next_rank_for_level(profile.career.level)
        if next_rank is None:
            return "You are at the top career rank."
        return f"Next: level {next_rank.level}, {next_rank.title}. {next_rank.unlock}"
    return "Owner-operator gate locked: " + " ".join(reasons)


def business_status_summary(profile) -> str:
    status = getattr(profile, "business_status", COMPANY_DRIVER)
    rank = rank_for_level(profile.career.level)
    if is_owner_operator(status):
        if status == INDEPENDENT_AUTHORITY:
            return (
                f"You run under your own authority as a level {rank.level} "
                f"{rank.title}. Direct freight pays higher gross, but your "
                "business carries fuel, repairs, insurance, trailer program "
                "or owned-trailer reserve, truck reserve, compliance reserve, "
                "and factoring costs. "
                + next_business_unlock(profile)
            )
        start_mode = getattr(profile, "start_mode", "")
        lead = (
            "You chose the owner-operator start. "
            if start_mode == START_MODE_OWNER_OPERATOR else
            ""
        )
        return (
            f"{lead}You are leased to {carrier_name(profile)} as a level "
            f"{rank.level} {rank.title}. Load revenue is higher, but fuel, "
            "repairs, maintenance reserve, insurance, trailer program, truck "
            "payment reserve, and settlement fees come out of your money. "
            + (
                "Authority prep reserve is set. "
                if has_authority_readiness(profile) else
                ""
            )
            + next_business_unlock(profile)
        )
    ok, reasons = owner_operator_eligibility(profile)
    if ok:
        return (
            f"You are a company driver for {carrier_name(profile)}, level "
            f"{rank.level} {rank.title}. You qualify to buy your first "
            f"leased-on tractor position. Owner-operator buy-in costs "
            f"{OWNER_OPERATOR_BUY_IN:,.0f} dollars "
            f"and keeps {OWNER_OPERATOR_WORKING_CAPITAL:,.0f} dollars of "
            "working capital in the bank."
        )
    return (
        f"You are a company driver for {carrier_name(profile)}, level "
        f"{rank.level} {rank.title}. {option_for_profile(profile).menu_summary} "
        "The carrier supplies the tractor, fuel, repairs, trailer, authority, "
        "and insurance; your settlements are driver wages and bonuses. "
        + next_business_unlock(profile)
    )


def company_driver_pay(
    job: Job,
    gross_pay: float,
    on_time: bool,
    carrier_key_value: str | None = None,
) -> float:
    plan = pay_plan_for_key(carrier_key_value)
    wage_floor = plan.stop_pay + job.distance_mi * plan.min_per_mile
    wage_share = gross_pay * plan.pay_share
    bonus = gross_pay * plan.on_time_bonus_share if on_time else 0.0
    return round(max(wage_floor, wage_share) + bonus, 2)


def owner_operator_gross(gross_pay: float) -> float:
    return round(gross_pay * OWNER_OPERATOR_REVENUE_MULT, 2)


def direct_freight_gross(gross_pay: float) -> float:
    return round(gross_pay, 2)


def owner_operator_charges(job: Job, gross_pay: float) -> tuple[BusinessCharge, ...]:
    return (
        BusinessCharge("maintenance reserve", round(job.distance_mi * OWNER_MAINTENANCE_PER_MILE, 2)),
        BusinessCharge("insurance reserve", round(job.distance_mi * OWNER_INSURANCE_PER_MILE, 2)),
        BusinessCharge("trailer program", round(
            job.distance_mi * trailer_program_charge_per_mile(job.cargo.key), 2)),
        BusinessCharge("truck payment reserve", round(job.distance_mi * OWNER_TRUCK_PAYMENT_PER_MILE, 2)),
        BusinessCharge("settlement service fee", round(gross_pay * OWNER_SETTLEMENT_FEE_SHARE, 2)),
    )


def independent_authority_charges(job: Job, gross_pay: float) -> tuple[BusinessCharge, ...]:
    owned_trailers: tuple[str, ...] = ()
    return independent_authority_charges_for_trailers(job, gross_pay, owned_trailers)


def independent_authority_charges_for_trailers(
    job: Job,
    gross_pay: float,
    owned_trailers: tuple[str, ...] | list[str] = (),
) -> tuple[BusinessCharge, ...]:
    owned_trailer_charge = owned_trailer_charge_per_mile(job.cargo.key, owned_trailers)
    if owned_trailer_charge is None:
        trailer_charge = BusinessCharge(
            "trailer program",
            round(job.distance_mi * trailer_program_charge_per_mile(job.cargo.key), 2),
        )
    else:
        trailer_charge = BusinessCharge(
            "owned trailer reserve",
            round(job.distance_mi * owned_trailer_charge, 2),
        )
    return (
        BusinessCharge("maintenance reserve", round(job.distance_mi * OWNER_MAINTENANCE_PER_MILE, 2)),
        BusinessCharge("insurance reserve", round(job.distance_mi * AUTHORITY_INSURANCE_PER_MILE, 2)),
        trailer_charge,
        BusinessCharge("truck payment reserve", round(job.distance_mi * OWNER_TRUCK_PAYMENT_PER_MILE, 2)),
        BusinessCharge("authority compliance reserve", round(
            job.distance_mi * AUTHORITY_COMPLIANCE_PER_MILE, 2)),
        BusinessCharge("factoring fee", round(gross_pay * AUTHORITY_FACTORING_FEE_SHARE, 2)),
    )


def build_business_settlement(
    status: str,
    job: Job,
    gross_pay: float,
    *,
    on_time: bool,
    driver_charges: float,
    carrier_key: str | None = None,
    owned_trailers: tuple[str, ...] | list[str] = (),
) -> BusinessSettlement:
    if status == INDEPENDENT_AUTHORITY:
        gross_pay = direct_freight_gross(gross_pay)
        charges = independent_authority_charges_for_trailers(job, gross_pay, owned_trailers)
        net = max(0.0, gross_pay - driver_charges - sum(charge.amount for charge in charges))
        return BusinessSettlement(
            status,
            status_label(status),
            round(gross_pay, 2),
            driver_charges,
            charges,
            round(net, 2),
        )
    if is_owner_operator(status):
        gross_pay = owner_operator_gross(gross_pay)
        charges = owner_operator_charges(job, gross_pay)
        net = max(0.0, gross_pay - driver_charges - sum(charge.amount for charge in charges))
        return BusinessSettlement(
            status,
            status_label(status),
            round(gross_pay, 2),
            driver_charges,
            charges,
            round(net, 2),
        )

    net = max(
        0.0,
        company_driver_pay(job, gross_pay, on_time, carrier_key) - driver_charges,
    )
    return BusinessSettlement(
        COMPANY_DRIVER,
        status_label(COMPANY_DRIVER),
        round(gross_pay, 2),
        driver_charges,
        (),
        round(net, 2),
    )
