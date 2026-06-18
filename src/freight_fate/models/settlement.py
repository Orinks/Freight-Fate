"""Settlement accounting for carrier-paid and driver-responsibility charges."""

from __future__ import annotations

from dataclasses import dataclass

from .jobs import Job

CARRIER_PAID = "carrier_paid"
DRIVER_RESPONSIBILITY = "driver_responsibility"

LUMPER_DESTINATION_TYPES = {
    "cold_storage",
    "distribution",
    "food_terminal",
    "grocery_retail_dc",
    "retail_distribution",
}

WASHOUT_CARGO = {"food", "refrigerated", "grain"}


@dataclass(frozen=True)
class SettlementCharge:
    """A charge shown on the settlement ledger."""

    key: str
    label: str
    amount: float
    responsibility: str
    note: str = ""


def carrier_accessorial_charges(job: Job) -> tuple[SettlementCharge, ...]:
    """Approved load-related charges that do not reduce driver pay."""
    charges: list[SettlementCharge] = []
    if job.destination_type in LUMPER_DESTINATION_TYPES:
        charges.append(SettlementCharge(
            "delivery_lumper",
            "carrier-authorized unloading service",
            185.0,
            CARRIER_PAID,
            "receipt required; billed to the carrier/customer settlement",
        ))
    if job.cargo.key in WASHOUT_CARGO:
        charges.append(SettlementCharge(
            "trailer_washout",
            "required trailer washout",
            45.0,
            CARRIER_PAID,
            "approved sanitation charge after food or refrigerated freight",
        ))
    return tuple(charges)


def charge_total(charges: tuple[SettlementCharge, ...] | list[SettlementCharge]) -> float:
    return sum(charge.amount for charge in charges)


def charge_summary(charges: tuple[SettlementCharge, ...] | list[SettlementCharge]) -> str:
    if not charges:
        return "none"
    return ", ".join(f"{charge.label} {charge.amount:,.0f} dollars" for charge in charges)
