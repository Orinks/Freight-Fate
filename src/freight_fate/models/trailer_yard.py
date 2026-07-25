"""Trailer yards, drop-and-hook, and the trailer you are actually pulling.

Freight Fate already knew what *kind* of trailer a load needs (see
``trailers.CARGO_TRAILER_COMPATIBILITY``), but not that trailers are physical
things sitting in yards. That gap swallowed the single biggest difference
between one pickup and another: whether the driver waits at a dock while the
freight goes on, or drops the box they came in with and hooks one that was
loaded hours ago.

Both are real and the trade is real:

- **Live load.** Back into a dock and wait. An hour if the shipper is sharp,
  considerably longer if not -- and past the free time the carrier bills
  detention, which is money the driver earns for sitting still.
- **Drop and hook.** Twenty-odd minutes: drop, hook, crank the gear, do the
  paperwork, gone. It is why big carriers chase it. The catch is that you get
  the trailer you get, and nobody in that yard has looked at it since it was
  parked.

Which one a load is depends on the facility. High-volume freight -- a
distribution centre, a parcel hub, an intermodal ramp -- stages preloaded
trailers as a matter of course. A farm elevator or a quarry does not.

Nothing here is saved. Yards are derived from the facility's own identity, so
the same dock always holds the same iron without a byte of profile schema; the
one trailer that has to persist is the one currently hooked, and that rides in
the trip snapshot with the rest of the run.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .trailers import TRAILER_CATALOG, trailer_keys_for_cargo

# Facilities that move enough freight to keep loaded trailers standing ready.
DROP_YARD_FACILITY_TYPES = frozenset(
    {
        "cross_dock",
        "grocery_retail_dc",
        "retail_distribution",
        "distribution",
        "parcel_hub",
        "port_terminal",
        "intermodal_ramp",
        "automotive_plant",
        "company_yard",
        "terminal",
    }
)
# Facilities that sometimes have a drop yard and sometimes do not; the coin is
# weighted by how much freight the type moves.
SOMETIMES_DROP_YARD = {
    "dry_warehouse": 0.45,
    "food_processor": 0.40,
    "cold_storage": 0.40,
    "steel_industrial": 0.30,
    "lumber_paper": 0.30,
    "chemical_petroleum_terminal": 0.25,
}

DROP_HOOK_MIN = 25.0  # drop, hook, crank the gear, sign, gone
LIVE_LOAD_MIN = 60.0  # the shipper's own hour at the dock
# Real detention terms: two hours free, then the carrier bills by the hour and
# the driver is paid for the wait. Under two hours nobody owes anybody anything.
DETENTION_FREE_MIN = 120.0
DETENTION_PER_HOUR = 45.0
# How long a slow shipper can hold a truck past the scheduled hour.
LIVE_LOAD_SLOW_EXTRA_MIN = 165.0

MODE_DROP_HOOK = "drop_and_hook"
MODE_LIVE = "live_load"


@dataclass(frozen=True)
class TrailerUnit:
    """One physical trailer, with a number on the side and a history behind it."""

    number: str
    trailer_key: str
    condition_pct: float  # 0 is a new box, 100 is a candidate for the bone yard

    @property
    def label(self) -> str:
        return TRAILER_CATALOG[self.trailer_key].label

    @property
    def spoken_name(self) -> str:
        return f"{self.label.lower()} {self.number}"

    @property
    def condition_text(self) -> str:
        if self.condition_pct < 20.0:
            return "in good shape"
        if self.condition_pct < 45.0:
            return "well used but sound"
        if self.condition_pct < 70.0:
            return "rough around the edges"
        return "in poor shape"

    @property
    def defect(self) -> str | None:
        """What an inspector would write up, or None if it would pass clean.

        Drop-and-hook's real risk in one property: the trailer was parked by
        somebody else and nobody has been under it since.
        """
        if self.condition_pct < 55.0:
            return None
        if self.condition_pct < 70.0:
            return "trailer marker lamp out"
        if self.condition_pct < 85.0:
            return "trailer brake out of adjustment"
        return "worn trailer tire below tread depth"

    def describe(self) -> str:
        text = f"You are hooked to {self.spoken_name}, {self.condition_text}."
        if self.defect:
            text += f" Walking around it you find a {self.defect}."
        return text


def _seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    return int.from_bytes(digest[:6], "big")


def facility_has_drop_yard(facility_type: str, facility_id: str) -> bool:
    """Whether this facility stages loaded trailers instead of loading at a dock."""
    if facility_type in DROP_YARD_FACILITY_TYPES:
        return True
    chance = SOMETIMES_DROP_YARD.get(facility_type)
    if chance is None:
        return False
    return (_seed("dropyard", facility_type, facility_id) % 1000) / 1000.0 < chance


def yard_trailers(facility_type: str, facility_id: str, cargo_key: str) -> tuple[TrailerUnit, ...]:
    """The trailers standing in this yard that could take this freight.

    Derived from the facility itself, so the same dock always holds the same
    boxes across sessions and machines without persisting a thing.
    """
    if not facility_has_drop_yard(facility_type, facility_id):
        return ()
    keys = trailer_keys_for_cargo(cargo_key)
    units: list[TrailerUnit] = []
    for slot in range(3):
        seed = _seed("trailer", facility_id, cargo_key, slot)
        key = keys[seed % len(keys)]
        # A fleet keeps its trailers serviceable, so the spread leans good and
        # tails off into the tired ones: squaring a flat roll puts roughly two
        # in three under half worn and leaves the write-ups rare enough to be
        # worth noticing. Flat, nearly half the yard failed a walk-around.
        roll = (seed // 7) % 100
        condition = roll * roll / 100.0
        number = str(1000 + (seed // 13) % 8999)
        units.append(TrailerUnit(number, key, float(condition)))
    return tuple(units)


def preloaded_trailer(job) -> TrailerUnit | None:
    """The loaded trailer waiting for this dispatch, or None for a live load."""
    units = yard_trailers(
        str(getattr(job, "origin_type", "") or ""),
        str(getattr(job, "origin_facility_id", "") or getattr(job, "origin_location", "")),
        str(getattr(getattr(job, "cargo", None), "key", "") or ""),
    )
    if not units:
        return None
    # The yard hands over whichever box the shipper loaded for this run, which
    # from the driver's side is simply the one with the paperwork on it.
    return units[
        _seed("assigned", getattr(job, "origin_facility_id", ""), job.distance_mi) % len(units)
    ]


def owns_the_trailer(profile, job) -> bool:
    """Whether the player is pulling a trailer that belongs to them.

    Nobody swaps an owner-operator's own trailer for one out of the yard, so
    owning your box costs you drop-and-hook. That is a real trade and it is
    the honest reason leased carriers move freight faster.
    """
    from .trailers import owned_trailer_for_cargo

    if not getattr(profile, "owns_equipment", lambda: False)():
        return False
    owned = getattr(profile, "visible_owned_trailers", lambda: ())()
    return owned_trailer_for_cargo(job.cargo.key, owned) is not None


@dataclass(frozen=True)
class PickupPlan:
    """How this load gets onto the truck, and what it costs in time."""

    mode: str
    minutes: float
    trailer: TrailerUnit | None
    detention_minutes: float
    reason: str

    @property
    def is_drop_hook(self) -> bool:
        return self.mode == MODE_DROP_HOOK

    @property
    def detention_pay(self) -> float:
        return round(self.detention_minutes / 60.0 * DETENTION_PER_HOUR, 2)


def pickup_plan(job, profile) -> PickupPlan:
    """Decide live load or drop-and-hook for this dispatch, and time it."""
    if owns_the_trailer(profile, job):
        return PickupPlan(
            MODE_LIVE,
            LIVE_LOAD_MIN,
            None,
            0.0,
            "it is your own trailer, so this one loads at the dock",
        )
    trailer = preloaded_trailer(job)
    if trailer is not None:
        return PickupPlan(
            MODE_DROP_HOOK,
            DROP_HOOK_MIN,
            trailer,
            0.0,
            "the yard has your load already on a trailer",
        )
    # Live load: the shipper's own hour, and sometimes a good deal more.
    seed = _seed("detention", getattr(job, "origin_facility_id", ""), job.distance_mi)
    slow = (seed % 100) < 30
    extra = round(LIVE_LOAD_SLOW_EXTRA_MIN * ((seed // 100) % 100) / 100.0, 0) if slow else 0.0
    minutes = LIVE_LOAD_MIN + extra
    detention = max(0.0, minutes - DETENTION_FREE_MIN)
    reason = "the shipper is loading you at the dock"
    if detention > 0.0:
        reason = "the shipper is loading you at the dock, and they are running behind"
    return PickupPlan(MODE_LIVE, minutes, None, detention, reason)


TRAILER_SWAP_MIN = 30.0  # the yard finds another box and brings it round


def replacement_trailer(job, refused: TrailerUnit | None) -> TrailerUnit | None:
    """The box the yard brings out after a driver refuses one.

    A yard asked to swap a trailer does not hand over another bad one -- the
    point of refusing is that somebody goes and finds a serviceable trailer.
    Drawn from the same yard so the number is real, then guaranteed sound.
    """
    if refused is None:
        return None
    units = yard_trailers(
        str(getattr(job, "origin_type", "") or ""),
        str(getattr(job, "origin_facility_id", "") or getattr(job, "origin_location", "")),
        str(getattr(getattr(job, "cargo", None), "key", "") or ""),
    )
    clean = [unit for unit in units if not unit.defect and unit.number != refused.number]
    if clean:
        return clean[0]
    # Every box in this yard has something on it, so the swap is a trailer
    # somebody actually went and fixed before handing it over.
    seed = _seed("swap", refused.number, getattr(job, "origin_facility_id", ""))
    return TrailerUnit(str(1000 + seed % 8999), refused.trailer_key, 12.0)


DROP_EMPTY_MIN = 20.0  # back it in, drop, hook an empty, sign, gone
LIVE_UNLOAD_MIN = 45.0  # the receiver's own dock time


@dataclass(frozen=True)
class DeliveryPlan:
    """How the freight comes off: dropped in the yard, or unloaded at a dock."""

    mode: str
    minutes: float
    keeps_trailer: bool  # False when the loaded box stays and you leave with an empty
    reason: str

    @property
    def is_drop_hook(self) -> bool:
        return self.mode == MODE_DROP_HOOK


def delivery_plan(job, profile) -> DeliveryPlan:
    """Decide live unload or drop-and-hook at the receiver.

    Same trade as the pickup end and the same rules decide it, with one
    addition that only exists here: dropping the loaded box is also how a
    driver gets rid of a trailer they have been dragging a defect around on
    since the shipper. You hand the write-up to the receiver's yard along
    with the freight, and hook a clean empty.
    """
    if owns_the_trailer(profile, job):
        return DeliveryPlan(
            MODE_LIVE,
            LIVE_UNLOAD_MIN,
            True,
            "it is your own trailer, so they unload you at the dock",
        )
    facility_type = str(getattr(job, "destination_type", "") or "")
    facility_id = str(
        getattr(job, "destination_facility_id", "") or getattr(job, "destination_location", "")
    )
    if facility_has_drop_yard(facility_type, facility_id):
        return DeliveryPlan(
            MODE_DROP_HOOK,
            DROP_EMPTY_MIN,
            False,
            "the receiver takes the whole trailer and you leave with an empty",
        )
    return DeliveryPlan(
        MODE_LIVE,
        LIVE_UNLOAD_MIN,
        True,
        "the receiver is unloading you at the dock",
    )


def detention_charge(plan: PickupPlan):
    """Detention as a settlement line, or None when nobody owes anybody.

    Detention is money *to* the driver, so it rides the ledger as a negative
    charge -- the same way the settlement already nets carrier-paid lines.
    """
    if plan.detention_minutes <= 0.0:
        return None
    from .settlement import CARRIER_PAID, SettlementCharge

    hours = plan.detention_minutes / 60.0
    return SettlementCharge(
        "detention_pay",
        "detention pay",
        -plan.detention_pay,
        CARRIER_PAID,
        f"{hours:.1f} hours held past the free time at the shipper",
    )
