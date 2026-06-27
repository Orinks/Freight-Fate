"""Career business status and settlement economics.

Freight Fate keeps the business arc playable rather than fully accounting-like:
the player starts as a company driver, then can buy into a leased-on
owner-operator track once the career has enough reputation, cash, and miles.
"""

from __future__ import annotations

from dataclasses import dataclass

from .jobs import Job

COMPANY_DRIVER = "company_driver"
LEASED_OWNER_OPERATOR = "leased_owner_operator"

OWNER_OPERATOR_LEVEL = 5
OWNER_OPERATOR_REPUTATION = 65.0
OWNER_OPERATOR_DELIVERIES = 10
OWNER_OPERATOR_BUY_IN = 20_000.0
OWNER_OPERATOR_WORKING_CAPITAL = 3_000.0
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


def owner_operator_eligibility(profile) -> tuple[bool, tuple[str, ...]]:
    """Whether the profile can buy into owner-operator status now."""
    if is_owner_operator(getattr(profile, "business_status", COMPANY_DRIVER)):
        return False, ("You are already running as an owner-operator.",)

    reasons: list[str] = []
    if profile.career.level < OWNER_OPERATOR_LEVEL:
        reasons.append(f"Reach level {OWNER_OPERATOR_LEVEL}.")
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


def business_status_summary(profile) -> str:
    status = getattr(profile, "business_status", COMPANY_DRIVER)
    if is_owner_operator(status):
        return (
            "You are a leased-on owner-operator. Load revenue is higher, but "
            "fuel, repairs, maintenance reserve, insurance, trailer program, "
            "truck payment reserve, and settlement fees come out of your money."
        )
    ok, reasons = owner_operator_eligibility(profile)
    if ok:
        return (
            "You are a company driver and qualify to buy your first tractor. "
            f"Owner-operator buy-in costs {OWNER_OPERATOR_BUY_IN:,.0f} dollars "
            f"and keeps {OWNER_OPERATOR_WORKING_CAPITAL:,.0f} dollars of "
            "working capital in the bank."
        )
    return (
        "You are a company driver. The carrier supplies the tractor, fuel, "
        "repairs, trailer, authority, and insurance; your settlements are "
        "driver wages and bonuses. Owner-operator path locked: "
        + " ".join(reasons)
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
