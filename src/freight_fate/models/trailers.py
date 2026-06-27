"""Trailer program and cargo compatibility model.

The current business arc models leased-on owner-operators, not full authority.
Company drivers use carrier-provided trailers. Leased-on owner-operators start
with the carrier's dry van program and can add specialty trailer program slots
without buying trailers outright.
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


TRAILER_CATALOG: dict[str, TrailerType] = {
    "dry_van": TrailerType(
        "dry_van",
        "Dry van",
        "dry van trailer",
        "Carrier trailer program for general boxed and pallet freight.",
        0.0,
        0.12,
    ),
    "reefer": TrailerType(
        "reefer",
        "Reefer",
        "refrigerated trailer",
        "Temperature-controlled trailer program for food and refrigerated freight.",
        8_000.0,
        0.18,
    ),
    "flatbed": TrailerType(
        "flatbed",
        "Flatbed",
        "flatbed trailer",
        "Open-deck trailer program for steel, machinery, lumber, and construction freight.",
        7_000.0,
        0.16,
    ),
    "bulk": TrailerType(
        "bulk",
        "Bulk",
        "bulk or hopper trailer",
        "Bulk trailer program for grain, farm inputs, and loose bulk materials.",
        9_000.0,
        0.20,
    ),
}


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
}


def trailer_keys_for_cargo(cargo_key: str) -> tuple[str, ...]:
    return CARGO_TRAILER_COMPATIBILITY.get(cargo_key, DEFAULT_TRAILER_PROGRAMS)


def trailer_labels(keys: Iterable[str]) -> str:
    labels = [
        TRAILER_CATALOG[key].label
        for key in keys
        if key in TRAILER_CATALOG
    ]
    if not labels:
        return "carrier trailer"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f", or {labels[-1]}"


def equipment_text_for_cargo(cargo_key: str) -> str:
    keys = trailer_keys_for_cargo(cargo_key)
    texts = [
        TRAILER_CATALOG[key].equipment_text
        for key in keys
        if key in TRAILER_CATALOG
    ]
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
    charges = [
        TRAILER_CATALOG[key].per_mile_reserve
        for key in keys
        if key in TRAILER_CATALOG
    ]
    return max(charges) if charges else TRAILER_CATALOG["dry_van"].per_mile_reserve
