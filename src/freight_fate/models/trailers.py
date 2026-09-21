"""Trailer program, ownership, and cargo compatibility model.

Company drivers use carrier-provided trailers. Leased-on owner-operators use
carrier trailer programs. Own-authority players can buy trailers outright while
still keeping earlier support programs for save compatibility.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

DEFAULT_TRAILER_PROGRAMS = ("dry_van",)


@dataclass(frozen=True)
class TrailerType:
    key: str
    label: str
    equipment_text: str
    description: str
    lease_deposit: float
    per_mile_reserve: float
    purchase_price: float
    owned_per_mile_reserve: float


TRAILER_CATALOG: dict[str, TrailerType] = {
    "dry_van": TrailerType(
        "dry_van",
        "Dry van",
        "dry van trailer",
        "Carrier trailer program for general boxed and pallet freight.",
        0.0,
        0.12,
        42_000.0,
        0.05,
    ),
    "reefer": TrailerType(
        "reefer",
        "Reefer",
        "refrigerated trailer",
        "Temperature-controlled trailer program for food and refrigerated freight.",
        8_000.0,
        0.18,
        82_000.0,
        0.10,
    ),
    "flatbed": TrailerType(
        "flatbed",
        "Flatbed",
        "flatbed trailer",
        "Open-deck trailer program for steel, machinery, lumber, and construction freight.",
        7_000.0,
        0.16,
        48_000.0,
        0.07,
    ),
    "bulk": TrailerType(
        "bulk",
        "Bulk",
        "bulk or hopper trailer",
        "Bulk trailer program for grain, farm inputs, and loose bulk materials.",
        9_000.0,
        0.20,
        58_000.0,
        0.09,
    ),
    # A tank is the most expensive box a driver can pull and the one the
    # carrier is fussiest about: pressure tests, internal wash-outs between
    # products, and a shell that is scrap the first time it is rolled. The
    # reserves reflect equipment that is inspected far more than a dry van.
    "tank": TrailerType(
        "tank",
        "Tank",
        "tank trailer",
        "Tank trailer program for liquid bulk: fuel, chemicals, and liquid food products.",
        14_000.0,
        0.26,
        96_000.0,
        0.13,
    ),
}

# How much liquid a road tank holds, in the same tonnes the job weights use.
# A load's weight against this is how full the tank is -- which is the single
# number that decides how hard it will surge.
TANK_CAPACITY_TONS = 26.0


CARGO_TRAILER_COMPATIBILITY: dict[str, tuple[str, ...]] = {
    "general": ("dry_van",),
    "retail": ("dry_van",),
    "parcel": ("dry_van",),
    "container": ("dry_van", "flatbed"),
    "bulk": ("bulk",),
    "grain": ("bulk",),
    "farm_inputs": ("dry_van", "bulk"),
    "construction": ("flatbed", "dry_van"),
    "lumber_paper": ("flatbed", "dry_van"),
    "automotive": ("dry_van",),
    "machinery": ("flatbed",),
    "steel": ("flatbed",),
    "food": ("reefer",),
    "refrigerated": ("reefer",),
    "chemicals": ("dry_van",),
    "electronics": ("dry_van",),
    "fuel_bulk": ("tank",),
    "liquid_food": ("tank",),
}


def trailer_keys_for_cargo(cargo_key: str) -> tuple[str, ...]:
    return CARGO_TRAILER_COMPATIBILITY.get(cargo_key, DEFAULT_TRAILER_PROGRAMS)


def trailer_labels(keys: Iterable[str]) -> str:
    labels = [TRAILER_CATALOG[key].label for key in keys if key in TRAILER_CATALOG]
    if not labels:
        return "carrier trailer"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f", or {labels[-1]}"


def equipment_text_for_cargo(cargo_key: str) -> str:
    keys = trailer_keys_for_cargo(cargo_key)
    texts = [TRAILER_CATALOG[key].equipment_text for key in keys if key in TRAILER_CATALOG]
    if not texts:
        return "carrier trailer"
    if len(texts) == 1:
        return texts[0]
    return ", ".join(texts[:-1]) + f", or {texts[-1]}"


def normalized_trailer_programs(programs: Iterable[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for key in programs:
        if key in TRAILER_CATALOG and key not in seen:
            seen.append(key)
    return tuple(seen)


def compatible_with_programs(cargo_key: str, programs: Iterable[str]) -> bool:
    owned = set(normalized_trailer_programs(programs))
    return bool(owned & set(trailer_keys_for_cargo(cargo_key)))


def required_program_text(cargo_key: str) -> str:
    return trailer_labels(trailer_keys_for_cargo(cargo_key))


def trailer_program_charge_per_mile(cargo_key: str) -> float:
    keys = trailer_keys_for_cargo(cargo_key)
    charges = [TRAILER_CATALOG[key].per_mile_reserve for key in keys if key in TRAILER_CATALOG]
    return max(charges) if charges else TRAILER_CATALOG["dry_van"].per_mile_reserve


def owned_trailer_for_cargo(
    cargo_key: str,
    owned_trailers: Iterable[str],
) -> TrailerType | None:
    owned = set(normalized_trailer_programs(owned_trailers))
    for key in trailer_keys_for_cargo(cargo_key):
        if key in owned and key in TRAILER_CATALOG:
            return TRAILER_CATALOG[key]
    return None


def owned_trailer_charge_per_mile(cargo_key: str, owned_trailers: Iterable[str]) -> float | None:
    trailer = owned_trailer_for_cargo(cargo_key, owned_trailers)
    if trailer is None:
        return None
    return trailer.owned_per_mile_reserve
