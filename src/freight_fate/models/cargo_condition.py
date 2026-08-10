"""What the freight arrives in, and what the receiver does about it.

Truck damage is the driver's problem. Cargo damage is the customer's, and
that is a different and much larger kind of money. Under the Carmack
Amendment (49 U.S.C. 14706) a motor carrier is liable for the actual loss or
injury to the property it carries: accept a clean bill of lading at origin,
deliver short or damaged, and the carrier owes the value of the freight
unless it can prove one of a short list of defences. At the dock the receiver
inspects, notes any exception on the bill of lading -- the OS&D notation,
Over, Short and Damaged -- and, if the load is bad enough, refuses it
outright. The carrier is then holding freight nobody will pay for and a claim
besides, and the driver delivered nothing.

So the ladder here is the real one, and it is deliberately harsher at the top
than any truck-damage consequence: clean, an exception noted, a claim paid,
and the load rejected.

The meter is condition, not value: 0 is freight in the state it was tendered,
100 is a trailer of scrap. What moves it is what already moves in the sim --
hard braking, taking a bend faster than it is signed for, hitting something --
scaled by how well the freight in question survives being thrown about.
Nothing here knows about Pygame; the driving layer feeds it and speaks it.
"""

from __future__ import annotations

from dataclasses import dataclass

# Condition thresholds at the dock. Below the first, the receiver signs a
# clean bill and nobody says anything -- which is where a careful driver
# lives, and the whole point of the shallow end being free.
CARGO_EXCEPTION_PCT = 12.0  # noted on the bill of lading; a small deduction
CARGO_CLAIM_PCT = 35.0  # a real claim against the load's value
CARGO_REJECT_PCT = 60.0  # the receiver refuses it: no delivery pay at all

# What each outcome costs, as a share of the load's gross pay. The claim
# figure is the freight's value, not a fee, which is why it dwarfs every
# fine in the game; rejection takes the pay as well as owing the claim.
CARGO_EXCEPTION_PAY_LOSS = 0.10
CARGO_CLAIM_PAY_LOSS = 0.45
CARGO_REJECT_PAY_LOSS = 1.0
# Standing lost at each rung. A rejected load is the worst thing a driver can
# hand a carrier short of hurting somebody.
CARGO_EXCEPTION_REPUTATION = 2.0
CARGO_CLAIM_REPUTATION = 6.0
CARGO_REJECT_REPUTATION = 15.0

# How much of the load's gross the carrier is out when a claim is filed.
# Rejected freight is a total loss on top of the unpaid haul.
CARGO_CLAIM_VALUE_MULT = 1.5
CARGO_REJECT_VALUE_MULT = 3.0

# How freight answers being thrown around. 1.0 is a pallet of general
# freight; the delicate classes bruise, shatter, or spoil at a multiple of
# it, and the classes that are already rubble travel nearly indifferent.
CARGO_FRAGILITY: dict[str, float] = {
    "electronics": 3.0,
    "high_value": 3.0,
    "glass": 3.0,
    "food": 2.4,
    "refrigerated": 2.4,
    "livestock": 2.6,
    "automotive": 1.8,
    "machinery": 1.6,
    "retail": 1.4,
    "parcel": 1.4,
    "lumber_paper": 0.8,
    "construction": 0.6,
    "grain": 0.5,
    "bulk": 0.4,
    # Liquid cannot be broken. What a tank load loses is quality: product
    # whipped into foam and out through the vents, temperature spec gone,
    # a food-grade load no longer fit to sell. That takes a great deal of
    # abuse, so the meter climbs slowly -- the danger of a tanker was never
    # to the cargo, it is to the truck and the driver, and that is priced in
    # the physics rather than here.
    "fuel_bulk": 0.30,
    "liquid_food": 0.40,
}
CARGO_FRAGILITY_DEFAULT = 1.0
CARGO_FRAGILE_FLAG_MULT = 1.5  # applied when the class is flagged fragile

# The rates that MOVE the meter live with the physics that produce them,
# in sim/vehicle (CARGO_HARD_BRAKE_G and friends). This module owns only
# what the dock does with the number they arrive at.

CARGO_OUTCOME_CLEAN = "clean"
CARGO_OUTCOME_EXCEPTION = "exception"
CARGO_OUTCOME_CLAIM = "claim"
CARGO_OUTCOME_REJECTED = "rejected"


def cargo_fragility(cargo) -> float:
    """How fast this freight takes damage relative to general freight."""
    if cargo is None:
        return CARGO_FRAGILITY_DEFAULT
    key = str(getattr(cargo, "key", "") or "")
    mult = CARGO_FRAGILITY.get(key, CARGO_FRAGILITY_DEFAULT)
    if key not in CARGO_FRAGILITY and getattr(cargo, "fragile", False):
        # A class the table has not been given a number for, but which the
        # catalogue already flags fragile, must not read as general freight.
        mult *= CARGO_FRAGILE_FLAG_MULT
    return mult


def cargo_outcome(condition_pct: float) -> str:
    """What the receiver does with freight in this condition."""
    if condition_pct >= CARGO_REJECT_PCT:
        return CARGO_OUTCOME_REJECTED
    if condition_pct >= CARGO_CLAIM_PCT:
        return CARGO_OUTCOME_CLAIM
    if condition_pct >= CARGO_EXCEPTION_PCT:
        return CARGO_OUTCOME_EXCEPTION
    return CARGO_OUTCOME_CLEAN


@dataclass(frozen=True)
class CargoSettlement:
    """The dock's ruling on a load, in the numbers settlement needs."""

    outcome: str
    condition_pct: float
    pay_loss: float  # dollars withheld from the driver's gross
    claim_value: float  # dollars the claim is worth against the carrier
    reputation_hit: float

    @property
    def rejected(self) -> bool:
        return self.outcome == CARGO_OUTCOME_REJECTED

    @property
    def clean(self) -> bool:
        return self.outcome == CARGO_OUTCOME_CLEAN


def settle_cargo(condition_pct: float, gross_pay: float) -> CargoSettlement:
    """Rule on a delivered load. Gross pay is the haul before deductions."""
    outcome = cargo_outcome(condition_pct)
    gross = max(0.0, float(gross_pay))
    if outcome == CARGO_OUTCOME_REJECTED:
        return CargoSettlement(
            outcome,
            condition_pct,
            gross * CARGO_REJECT_PAY_LOSS,
            gross * CARGO_REJECT_VALUE_MULT,
            CARGO_REJECT_REPUTATION,
        )
    if outcome == CARGO_OUTCOME_CLAIM:
        return CargoSettlement(
            outcome,
            condition_pct,
            gross * CARGO_CLAIM_PAY_LOSS,
            gross * CARGO_CLAIM_VALUE_MULT,
            CARGO_CLAIM_REPUTATION,
        )
    if outcome == CARGO_OUTCOME_EXCEPTION:
        return CargoSettlement(
            outcome,
            condition_pct,
            gross * CARGO_EXCEPTION_PAY_LOSS,
            0.0,
            CARGO_EXCEPTION_REPUTATION,
        )
    return CargoSettlement(outcome, condition_pct, 0.0, 0.0, 0.0)


# The same four rungs said in the words that fit a tank. Diesel does not
# "shift but sound" and milk does not "break": a liquid load is worked, then
# off spec, then contaminated, then lost. Same thresholds, same money -- only
# the nouns change, because a driver who hears "the load is damaged" about a
# tank of fuel has been told nothing they can act on.
LIQUID_CONDITION_TEXT = {
    CARGO_OUTCOME_REJECTED: "lost",
    CARGO_OUTCOME_CLAIM: "contaminated",
    CARGO_OUTCOME_EXCEPTION: "off spec",
}


def cargo_condition_text(condition_pct: float, *, liquid: bool = False) -> str:
    """The spoken state of the load, for status readouts and cues.

    Plain words, not a number alone: "eighteen percent" tells a player
    nothing about whether the receiver will sign for it. ``liquid`` swaps in
    the tank vocabulary; the thresholds and the consequences are identical.
    """
    outcome = cargo_outcome(condition_pct)
    if liquid:
        if outcome in LIQUID_CONDITION_TEXT:
            return LIQUID_CONDITION_TEXT[outcome]
        return "worked" if condition_pct >= 1.0 else "settled"
    if outcome == CARGO_OUTCOME_REJECTED:
        return "ruined"
    if outcome == CARGO_OUTCOME_CLAIM:
        return "badly damaged"
    if outcome == CARGO_OUTCOME_EXCEPTION:
        return "damaged"
    if condition_pct >= 1.0:
        return "shifted but sound"
    return "secure"
