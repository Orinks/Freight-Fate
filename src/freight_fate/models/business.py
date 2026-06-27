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

COMPANY_DRIVER = "company_driver"
LEASED_OWNER_OPERATOR = "leased_owner_operator"

OWNER_OPERATOR_PREP_LEVEL = 5
OWNER_OPERATOR_CANDIDATE_LEVEL = 11
OWNER_OPERATOR_LEVEL = 15
OWNER_OPERATOR_REPUTATION = 80.0
OWNER_OPERATOR_DELIVERIES = 35
OWNER_OPERATOR_BUY_IN = 35_000.0
OWNER_OPERATOR_WORKING_CAPITAL = 10_000.0
OWNER_OPERATOR_REVENUE_MULT = 1.12

COMPANY_PAY_SHARE = 0.36
COMPANY_MIN_PER_MILE = 0.82
COMPANY_STOP_PAY = 175.0
COMPANY_ON_TIME_BONUS_SHARE = 0.04

OWNER_MAINTENANCE_PER_MILE = 0.18
OWNER_INSURANCE_PER_MILE = 0.09
OWNER_TRAILER_PROGRAM_PER_MILE = 0.12
OWNER_TRUCK_PAYMENT_PER_MILE = 0.22
OWNER_SETTLEMENT_FEE_SHARE = 0.02


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
    return status == LEASED_OWNER_OPERATOR


def status_label(status: str) -> str:
    if is_owner_operator(status):
        return "leased-on owner-operator"
    return "company driver"


def pay_label(status: str) -> str:
    if is_owner_operator(status):
        return "Gross revenue"
    return "Carrier gross"


def player_pays_operating_costs(status: str) -> bool:
    return is_owner_operator(status)


def carrier_name(profile) -> str:
    return str(getattr(profile, "carrier_name", STARTER_CARRIER_NAME) or STARTER_CARRIER_NAME)


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
    return (
        f"{carrier_name(profile)}. Level {rank.level}: {rank.title}. "
        f"{rank.stage}."
    )


def next_business_unlock(profile) -> str:
    status = getattr(profile, "business_status", COMPANY_DRIVER)
    if is_owner_operator(status):
        if profile.career.level >= 20:
            return (
                "Endgame owner-operator status reached. Full independent "
                "authority is a future optional system."
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
        return (
            f"You are leased to {carrier_name(profile)} as a level "
            f"{rank.level} {rank.title}. Load revenue is higher, but fuel, "
            "repairs, maintenance reserve, insurance, trailer program, truck "
            "payment reserve, and settlement fees come out of your money. "
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
        f"{rank.level} {rank.title}. The carrier supplies the tractor, fuel, "
        "repairs, trailer, authority, and insurance; your settlements are "
        "driver wages and bonuses. "
        + next_business_unlock(profile)
    )


def company_driver_pay(job: Job, gross_pay: float, on_time: bool) -> float:
    wage_floor = COMPANY_STOP_PAY + job.distance_mi * COMPANY_MIN_PER_MILE
    wage_share = gross_pay * COMPANY_PAY_SHARE
    bonus = gross_pay * COMPANY_ON_TIME_BONUS_SHARE if on_time else 0.0
    return round(max(wage_floor, wage_share) + bonus, 2)


def owner_operator_gross(gross_pay: float) -> float:
    return round(gross_pay * OWNER_OPERATOR_REVENUE_MULT, 2)


def owner_operator_charges(job: Job, gross_pay: float) -> tuple[BusinessCharge, ...]:
    return (
        BusinessCharge("maintenance reserve", round(job.distance_mi * OWNER_MAINTENANCE_PER_MILE, 2)),
        BusinessCharge("insurance reserve", round(job.distance_mi * OWNER_INSURANCE_PER_MILE, 2)),
        BusinessCharge("trailer program", round(job.distance_mi * OWNER_TRAILER_PROGRAM_PER_MILE, 2)),
        BusinessCharge("truck payment reserve", round(job.distance_mi * OWNER_TRUCK_PAYMENT_PER_MILE, 2)),
        BusinessCharge("settlement service fee", round(gross_pay * OWNER_SETTLEMENT_FEE_SHARE, 2)),
    )


def build_business_settlement(
    status: str,
    job: Job,
    gross_pay: float,
    *,
    on_time: bool,
    driver_charges: float,
) -> BusinessSettlement:
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

    net = max(0.0, company_driver_pay(job, gross_pay, on_time) - driver_charges)
    return BusinessSettlement(
        COMPANY_DRIVER,
        status_label(COMPANY_DRIVER),
        round(gross_pay, 2),
        driver_charges,
        (),
        round(net, 2),
    )
