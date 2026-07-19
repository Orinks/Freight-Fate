"""Consumable buffs sold at route stops.

A buff is a purchase that slows how fast fatigue or rig wear accrues for a
while -- endurance bought before a hard leg, stacking naturally with rest
instead of replacing it. Food and drink also give a small instant fatigue
lift so a meal feels like a meal. Two hard rules from the design
(docs/1.9-buff-system-design.md): buffs never touch the hours-of-service
duty clock, and one buff is active per group -- the newest replaces its
predecessor, so three coffees do not stack.

The catalog lives in buffs.json next to this module so balance passes are
data edits, and future systems (mini-games, passes) can grant buffs by id
without a parallel reward system. Availability is brand-keyed through
``amenities.classify_brand`` -- the Iron Skillet dinner is a Petro thing,
showers are the Pilot/Flying J thing (free with fuel, like real life) --
or keyed to a stop's listed actions for generic items like the energy
drink. All ``label``/``help``/``purchased``/``worn_off`` strings are
player-facing speech: plain language, no jargon.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .amenities import classify_brand
from .data_resources import read_data_text

# "fatigue" buffs are timed (fixed game hours); "engine" and "tire" buffs
# are rig services that last the rest of the trip and die with it.
BUFF_GROUPS = ("fatigue", "engine", "tire")


@dataclass(frozen=True)
class Buff:
    id: str
    label: str
    group: str
    price: float
    stop_minutes: float
    rate: float  # accrual multiplier for the group's axis (0..1]
    fatigue_instant: float = 0.0  # one-time fatigue relief on purchase
    duration_game_h: float = 0.0  # timed buffs: how long the rate holds
    trip_scoped: bool = False  # rig buffs: holds until the trip ends
    brands: tuple[str, ...] = ()  # amenities brand keys that sell it
    actions: tuple[str, ...] = ()  # stop actions that sell it (e.g. fuel)
    free_with_fuel: bool = False  # free after fueling this visit (showers)
    help: str = ""
    purchased: str = ""
    worn_off: str = ""


def _load_catalog() -> dict[str, Buff]:
    text = read_data_text("buffs.json")
    if text is None:
        raise FileNotFoundError("buffs.json is missing from this build")
    raw = json.loads(text)
    catalog: dict[str, Buff] = {}
    for buff_id, entry in raw.items():
        buff = Buff(
            id=buff_id,
            label=str(entry["label"]),
            group=str(entry["group"]),
            price=float(entry["price"]),
            stop_minutes=float(entry["stop_minutes"]),
            rate=float(entry["rate"]),
            fatigue_instant=float(entry.get("fatigue_instant", 0.0)),
            duration_game_h=float(entry.get("duration_game_h", 0.0)),
            trip_scoped=bool(entry.get("trip_scoped", False)),
            brands=tuple(entry.get("brands", ())),
            actions=tuple(entry.get("actions", ())),
            free_with_fuel=bool(entry.get("free_with_fuel", False)),
            help=str(entry.get("help", "")),
            purchased=str(entry.get("purchased", "")),
            worn_off=str(entry.get("worn_off", "")),
        )
        if buff.group not in BUFF_GROUPS:
            raise ValueError(f"buff {buff_id}: unknown group {buff.group!r}")
        if not 0.0 < buff.rate <= 1.0:
            raise ValueError(f"buff {buff_id}: rate must be in (0, 1], got {buff.rate}")
        if buff.group == "fatigue" and buff.duration_game_h <= 0.0:
            raise ValueError(f"buff {buff_id}: fatigue buffs need duration_game_h")
        if buff.group != "fatigue" and not buff.trip_scoped:
            raise ValueError(f"buff {buff_id}: rig buffs must be trip_scoped")
        if not buff.brands and not buff.actions:
            raise ValueError(f"buff {buff_id}: no availability (brands or actions)")
        if not buff.help or not buff.purchased:
            raise ValueError(f"buff {buff_id}: help and purchased speech are required")
        catalog[buff_id] = buff
    return catalog


BUFF_CATALOG: dict[str, Buff] = _load_catalog()


def buffs_for_stop(name: str, actions: tuple[str, ...]) -> tuple[Buff, ...]:
    """The buffs a stop sells, from its brand and its listed actions.

    Catalog order is menu order. Generic stops sell only action-keyed
    items; brand signatures (Iron Skillet, showers, lube bays) appear
    only under their brand.
    """
    brand = classify_brand(name)
    action_set = set(actions)
    offered: list[Buff] = []
    for buff in BUFF_CATALOG.values():
        by_brand = brand is not None and brand.key in buff.brands
        by_action = bool(action_set.intersection(buff.actions))
        if by_brand or by_action:
            offered.append(buff)
    return tuple(offered)


__all__ = ["BUFF_CATALOG", "BUFF_GROUPS", "Buff", "buffs_for_stop"]
