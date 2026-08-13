"""What the driver is behind by, what a settlement may take back, and when
being behind costs the seat or the tractor.

Debt used to be inert. Every place that took money noted that the balance
"can go negative; never a game over", and nothing downstream ever read it: a
driver could sit fifty-one thousand dollars in the hole, keep gaining levels,
and keep being handed better equipment because the fleet tier was a pure
function of career level. This module is the missing half.

Sources for the numbers here:

* **FLSA, 29 CFR 531.35 and 531.36, with DOL Field Operations Handbook
  30c10(b).** Wages must be paid "free and clear", and a deduction for damage,
  loss, or equipment is unlawful to the extent it cuts the week below the
  minimum wage. That is the operative floor for the money a driver owes here,
  because what this game carries forward is fines, deductibles, and freight
  claims -- exactly the class the law will not let an employer claw back to
  zero. The take-home share below is therefore a legal floor, not a courtesy.
  (Advance *principal* is the one class the FOH does let a carrier recover
  past that floor. This code is deliberately kinder than the law there; see
  ``deductions_from_settlement``.)
* **New Jersey DOL v. STG Logistics, July 2026, 2,775,000 dollars.** The
  carrier deducted fuel, tolls, insurance, and maintenance until "deductions
  were sometimes greater than a driver's entire gross pay, resulting in
  negative net pay during some pay periods". A company driver settling for
  nothing is not hard realism -- it is the conduct a state regulator just
  fined. Company-driver collection is capped here for that reason; the
  open-ended version lives on the owner-operator side, where it belongs.
* **Consumer Credit Protection Act Title III, 15 USC 1673(a).** The standard
  US answer to "how much of one cheque may a creditor reach" is 25 percent of
  disposable earnings. Title III governs third-party garnishment rather than
  an employer recovering its own money, so it is the calibration for
  ``COLLECTION_SHARE`` rather than its authority -- but it is the number every
  other US wage-attachment rule is written against.
* **Company-driver ceiling.** No published figure exists for the balance at
  which a carrier terminates a driver who owes it money; the research is clear
  that it is not a documented industry standard. The nearest well-evidenced
  debt a carrier really does carry against a company driver is CDL-school
  tuition on a 6-to-24-month contract, reported in the 3,000 to 8,000 dollar
  range, with the unamortized balance due on early departure and collections
  after that. ``COMPANY_CEILING_FLOOR`` sits in the middle of that band, and
  the per-driver scaling above it is a design choice, not a cited rate.
* **49 CFR 376.12(k)** (truth in leasing) bounds and accounts for driver
  escrow, and requires the balance back within 45 days of termination. A
  company driver's exposure to a carrier is meant to be small and bounded;
  the carrier's remedy past that is to end the employment, not to run an
  ever-growing tab.
* **UCC Article 9: 9-609, 9-610, 9-615(d), 9-623.** A secured lender may
  repossess on default, must dispose of the collateral in a commercially
  reasonable way, applies the proceeds to the debt, and the obligor is liable
  for any deficiency. Default is whatever the security agreement says -- one
  missed payment technically qualifies -- but lenders in practice escalate to
  a recovery agent around ninety days. The three spoken warning rungs below
  are that escalation window. Once what is owed passes what the tractor would
  bring at sale, the collateral no longer covers the loan: a five-year-old
  sleeper resold around 49,000 to 67,000 dollars in 2025 against six-figure
  new prices, and a realistic post-auction deficiency runs 20,000 to 50,000.
  ``REPOSSESSION_EQUITY_SHARE`` is that resale-to-book ratio, applied to this
  game's catalog values, which are already used-market prices.

The player-facing shape of all of it: money first, then what it cost, then
what you keep, then where you go from here. Nothing here is ever a dead end.
Every rule below leaves a driver able to work their way out, and the take-home
floor is the guarantee that working always helps.
"""

from __future__ import annotations

# -- what a settlement may take ---------------------------------------------

# The most one settlement can put toward a carried balance. Title III's
# garnishment ceiling, used here for the same reason the law sets it: a
# collection that takes the whole cheque stops the driver being able to work.
COLLECTION_SHARE = 0.25
# The other side of the same number, named so the spoken text can promise it.
TAKE_HOME_SHARE = 1.0 - COLLECTION_SHARE

# -- ceilings ---------------------------------------------------------------

# A company driver's exposure to the carrier is bounded by what the carrier
# will carry before it ends the employment. Scaled to the driver's own
# settlements so a senior driver on long freight is not terminated by a single
# bad week, with a floor for a new hire whose average is still tiny.
COMPANY_CEILING_SETTLEMENTS = 8.0
COMPANY_CEILING_FLOOR = 6_000.0
# What one settlement is assumed to be worth before a career has any history.
NOMINAL_SETTLEMENT = 750.0

# An owner-operator's lender repossesses when what is owed passes what the
# tractor would bring at sale. Used sleeper tractors resell well under book,
# so the collateral stops covering the loan around here.
REPOSSESSION_EQUITY_SHARE = 0.6
# A tractor with no catalog price (the starter rig) still stands behind a
# loan; this is the floor under the same rule.
REPOSSESSION_FLOOR = 12_000.0

# Warning rungs, as a share of the ceiling. The last one also has to leave
# real room -- see ``final_rung_debt``.
RUNG_HALFWAY_SHARE = 0.5
RUNG_FINAL_SHARE = 0.8
# The final warning has to leave at least this many of *this driver's own*
# settlements of headroom. A fixed dollar gap is worthless to a driver whose
# average run is bigger than the gap.
RUNG_FINAL_SETTLEMENTS = 2.0


def debt_owed(profile) -> float:
    """Everything the driver is behind by, in one number.

    Two things put a driver behind and a player experiences them as one: cash
    run past zero, and charges a settlement could not cover and carried
    forward. Anything that reads the driver's solvency reads this.
    """
    overdraft = max(0.0, -float(getattr(profile, "money", 0.0) or 0.0))
    balance = max(0.0, float(getattr(profile, "fines_owed", 0.0) or 0.0))
    return round(overdraft + balance, 2)


def in_debt(profile) -> bool:
    return debt_owed(profile) >= 1.0


def average_settlement(profile) -> float:
    """What one settlement is worth to this driver, from their own history."""
    career = getattr(profile, "career", None)
    deliveries = int(getattr(career, "deliveries", 0) or 0)
    if deliveries <= 0:
        return NOMINAL_SETTLEMENT
    earned = float(getattr(career, "total_earnings", 0.0) or 0.0)
    return max(NOMINAL_SETTLEMENT, earned / deliveries)


def tractor_value(profile) -> float:
    """Book value of the tractor standing behind an owner-operator's loan."""
    from .trucks import TRUCK_CATALOG

    key = str(getattr(profile, "truck", "") or "")
    model = TRUCK_CATALOG.get(key)
    return float(getattr(model, "price", 0.0) or 0.0)


def repossession_threshold(profile) -> float:
    """What an owner-operator may owe before the tractor no longer covers it."""
    return round(max(REPOSSESSION_FLOOR, tractor_value(profile) * REPOSSESSION_EQUITY_SHARE), 2)


def company_debt_ceiling(profile) -> float:
    """What the carrier will carry before it ends a company driver's employment."""
    return round(
        max(COMPANY_CEILING_FLOOR, average_settlement(profile) * COMPANY_CEILING_SETTLEMENTS), 2
    )


def debt_ceiling(profile) -> float:
    """The number that matters to this driver, whichever kind of driver they are."""
    from .business import is_owner_operator

    if is_owner_operator(getattr(profile, "business_status", "")):
        return repossession_threshold(profile)
    return company_debt_ceiling(profile)


def debt_share(profile) -> float:
    """How far toward the ceiling this driver is, 0 to 1."""
    ceiling = debt_ceiling(profile)
    if ceiling <= 0.0:
        return 0.0
    return max(0.0, min(1.0, debt_owed(profile) / ceiling))


def final_rung_debt(profile) -> float:
    """The debt at which the last warning is owed.

    Whichever comes first: four fifths of the ceiling, or the point that still
    leaves two of this driver's own settlements of room. A driver whose runs
    settle for more than the gap would otherwise get the warning and the
    consequence in the same breath.
    """
    ceiling = debt_ceiling(profile)
    headroom_point = ceiling - RUNG_FINAL_SETTLEMENTS * average_settlement(profile)
    return round(max(0.0, min(ceiling * RUNG_FINAL_SHARE, headroom_point)), 2)


def debt_rung(profile) -> int:
    """Which warning this driver is owed: 0 none, 1 exists, 2 halfway, 3 final."""
    owed = debt_owed(profile)
    if owed < 1.0:
        return 0
    if owed >= final_rung_debt(profile):
        return 3
    if owed >= debt_ceiling(profile) * RUNG_HALFWAY_SHARE:
        return 2
    return 1


# -- collection -------------------------------------------------------------


def collection_from_settlement(balance: float, net_pay: float) -> float:
    """What this settlement puts toward a carried balance.

    Never the whole of it. A settlement that pays nothing leaves the driver
    with a truck, a board, and no reachable state where working helps, which
    is not a hard career -- it is a soft lock with a menu.
    """
    owed = max(0.0, float(balance))
    pay = max(0.0, float(net_pay))
    return round(min(owed, pay * COLLECTION_SHARE), 2)


def take_home_floor(net_pay: float) -> float:
    """What always reaches the driver, whatever they owe."""
    return round(max(0.0, float(net_pay)) * TAKE_HOME_SHARE, 2)


def deductions_from_settlement(
    balance: float, advance: float, net_pay: float
) -> tuple[float, float]:
    """Split one settlement into (collected toward the balance, advance repaid).

    With nothing owed this is exactly what the game has always done: the
    advance comes back out of the settlement in full. That path is untouched,
    so a solvent driver's money is arithmetically identical.

    With a balance owed, the two together stay inside the take-home floor. The
    FOH would let a carrier take advance principal past that floor, but a
    driver whose settlement is being collected against and whose advance is
    also being recovered ends every run with nothing -- and a driver with
    nothing cannot buy the fuel that earns the next settlement. The floor wins.
    """
    owed = max(0.0, float(balance))
    outstanding = max(0.0, float(advance))
    pay = max(0.0, float(net_pay))
    if owed < 0.01:
        return 0.0, round(min(outstanding, pay), 2)
    budget = round(pay * COLLECTION_SHARE, 2)
    collected = round(min(owed, budget), 2)
    repaid = round(min(outstanding, max(0.0, budget - collected)), 2)
    return collected, repaid


def collection_active(profile) -> bool:
    """Whether a share of every settlement is currently going to a balance."""
    return max(0.0, float(getattr(profile, "fines_owed", 0.0) or 0.0)) >= 1.0


def advance_refused_reason(profile) -> str:
    """Why a dispatcher will not front cash right now. Empty when they will.

    A real trip advance is a hundred dollars against next week's settlement,
    not a line of credit. Once a balance is already being collected, drawing
    more is borrowing against money that is already spoken for -- and because
    the advance is only ever offered below ten dollars of cash, a driver in
    debt would be offered it after every single run, forever.
    """
    if not collection_active(profile):
        return ""
    return (
        "Dispatch will not front you cash while a share of every settlement is "
        f"already going to what you owe. You have {money_text(debt_owed(profile))} "
        "outstanding, and three quarters of every settlement still reaches you. "
        "Run a load and it comes down."
    )


# -- paying it down from cash ------------------------------------------------

PAYOFF_CASH_CUSHION = 200.0
PAYOFF_MIN_CASH = 10.0


def out_of_pocket_options(profile) -> list[tuple[str, float]]:
    """What a driver holding cash may put toward the balance, right now.

    Kinds: "all" when cash covers the whole balance, "half" for half of it
    capped at cash, "cushion" for everything above a fuel cushion. Amounts
    under a dollar or duplicating an earlier option are dropped.
    """
    balance = max(0.0, float(getattr(profile, "fines_owed", 0.0) or 0.0))
    cash = float(getattr(profile, "money", 0.0) or 0.0)
    if balance < 1.0 or cash < PAYOFF_MIN_CASH:
        return []
    options: list[tuple[str, float]] = []

    def _offer(kind: str, amount: float) -> None:
        amount = round(amount, 2)
        if amount >= 1.0 and all(abs(amount - a) >= 0.01 for _, a in options):
            options.append((kind, amount))

    if cash >= balance:
        _offer("all", balance)
    _offer("half", min(balance / 2.0, cash))
    _offer("cushion", min(balance, cash - PAYOFF_CASH_CUSHION))
    return options


def pay_out_of_pocket(profile, amount: float) -> float:
    """Move cash onto the balance; returns what was actually paid.

    Clamped so cash never goes below zero and the balance never below it.
    """
    balance = max(0.0, float(getattr(profile, "fines_owed", 0.0) or 0.0))
    cash = float(getattr(profile, "money", 0.0) or 0.0)
    paid = round(min(max(0.0, float(amount)), balance, max(0.0, cash)), 2)
    if paid < 0.01:
        return 0.0
    profile.fines_owed = round(balance - paid, 2)
    profile.money = round(cash - paid, 2)
    return paid


# -- the fleet of last resort cannot let debt run away ----------------------


def hard_capped(profile) -> bool:
    """A company driver already at the fleet that hires anyone.

    There is nowhere further down, so ending their employment is not a move
    the game can make. Their debt therefore stops at the ceiling instead of
    climbing toward a consequence that can never arrive.
    """
    from .business import is_owner_operator
    from .enforcement import LAST_CHANCE_CARRIER_KEY

    if is_owner_operator(getattr(profile, "business_status", "")):
        return False
    return str(getattr(profile, "carrier_key", "")) == LAST_CHANCE_CARRIER_KEY


def apply_hard_cap(profile) -> float:
    """Write off anything past the ceiling for a driver with nowhere to fall.

    Returns what was written off, so the terminal can say it happened.
    """
    if not hard_capped(profile):
        return 0.0
    excess = debt_owed(profile) - debt_ceiling(profile)
    if excess < 1.0:
        return 0.0
    written_off = round(excess, 2)
    balance = max(0.0, float(getattr(profile, "fines_owed", 0.0) or 0.0))
    from_balance = min(balance, written_off)
    profile.fines_owed = round(balance - from_balance, 2)
    remainder = round(written_off - from_balance, 2)
    if remainder >= 0.01:
        profile.money = round(float(profile.money) + remainder, 2)
    return written_off


# -- consequences -----------------------------------------------------------


def company_termination_due(profile) -> bool:
    """A company driver whose balance has passed what the carrier will carry."""
    from .business import is_owner_operator

    if is_owner_operator(getattr(profile, "business_status", "")):
        return False
    if hard_capped(profile):
        return False  # nowhere further down; the cap above holds the line
    return debt_owed(profile) >= company_debt_ceiling(profile)


def repossession_due(profile) -> bool:
    """An owner-operator who owes more than the tractor would bring at sale."""
    from .business import is_owner_operator

    if not is_owner_operator(getattr(profile, "business_status", "")):
        return False
    return debt_owed(profile) >= repossession_threshold(profile)


def sale_proceeds(profile) -> float:
    """What the tractor brings at auction, applied to what is owed."""
    return round(tractor_value(profile) * REPOSSESSION_EQUITY_SHARE, 2)


def settle_account(profile) -> float:
    """Clear what the driver owes, and return the figure that was settled.

    Both endings settle the account, for the same reason and with the same
    honesty: the carrier writes off what it could not collect from a driver it
    no longer employs, and the lender's sale closes out the loan it wrote. A
    deficiency after that is a civil matter between the driver and a finance
    company, not something that follows them into the next cab -- carriers
    hire drivers with one every day. Carrying it forward would only guarantee
    the next seat ended the same way, which is a trap wearing a consequence's
    clothes.
    """
    settled = debt_owed(profile)
    profile.fines_owed = 0.0
    if float(profile.money) < 0.0:
        profile.money = 0.0
    return round(settled, 2)


# -- spoken numbers ---------------------------------------------------------


def money_text(amount: float) -> str:
    return f"{amount:,.0f} dollars"


def ceiling_consequence_text(profile) -> str:
    """What happens at the ceiling, in one plain clause. Never a threat."""
    from .business import is_owner_operator

    if is_owner_operator(getattr(profile, "business_status", "")):
        return "the tractor is worth less than the loan on it and the lender takes it back"
    return "the carrier ends your employment and you move to another fleet"


# -- the two endings --------------------------------------------------------
#
# Both are written to the same shape: the money first, then what it cost, then
# what the driver keeps, then where they go from here. Neither is an ending in
# the sense the words usually mean -- the save is intact, the career is intact,
# and there is freight on the board in the morning. Nothing here says failed,
# over, bankrupt, or terminated out loud, and nothing here blames the driver.

KEPT_LINE = (
    "You keep your career level, your experience, your endorsements, your "
    "driving record, and everything else you own. Nothing about your career "
    "was reset and no save was lost."
)
BACK_TO_WORK_LINE = "There is freight waiting. Open the dispatch board whenever you are ready."


def apply_company_termination(profile) -> list[str]:
    """End a company driver's employment over an unpayable balance.

    The carrier writes off what it could not collect -- which is what really
    happens, and what has to happen here, because a driver who arrives at the
    next fleet still carrying the debt that cost them the last one is on rails
    to lose that seat too.
    """
    from .enforcement import LAST_CHANCE_CARRIER_KEY, LAST_CHANCE_CARRIER_NAME

    former = str(getattr(profile, "carrier_name", "") or "your carrier")
    settled = settle_account(profile)
    record = profile.driving_record
    record.carrier_terminations += 1
    profile.carrier_key = LAST_CHANCE_CARRIER_KEY
    profile.carrier_name = LAST_CHANCE_CARRIER_NAME
    profile.pay_advance = 0.0
    profile.pay_advance_used_for_load = False
    profile.dispatch_board_cache = None
    lines = [
        f"You owed {money_text(settled)}, which is more than {former} carries "
        "on a driver, and they have ended your employment.",
        "That balance is closed. You do not owe it to anyone any more, and "
        "your cash is back to zero.",
        KEPT_LINE,
        f"What changes is the seat. Your assigned tractor goes back to the "
        f"{former} yard, and you go on the payroll at "
        f"{LAST_CHANCE_CARRIER_NAME}: shorter freight, lower pay, and "
        "equipment to match, until you build back up with them.",
        BACK_TO_WORK_LINE,
    ]
    record.setback_notice_kind = "termination"
    record.setback_notice_lines = list(lines)
    return lines


def apply_repossession(profile) -> list[str]:
    """Take an owner-operator's tractor back and put them on a payroll again.

    Every owned tractor goes, not just the one being driven. Leaving a spare
    behind would settle the loan and leave the driver still an owner-operator,
    which is a loophole rather than an ending.
    """
    from .business import COMPANY_DRIVER
    from .enforcement import (
        LAST_CHANCE_CARRIER_KEY,
        LAST_CHANCE_CARRIER_NAME,
        REPUTATION_TERMINATION,
    )
    from .trucks import TRUCK_CATALOG

    label = TRUCK_CATALOG[profile.active_truck_key()].label
    proceeds = sale_proceeds(profile)
    settled = settle_account(profile)
    record = profile.driving_record
    record.repossessions += 1
    profile.owned_trucks = []
    profile.owned_trailers = []
    profile.business_status = COMPANY_DRIVER
    profile.authority_readiness = False
    profile.pay_advance = 0.0
    profile.pay_advance_used_for_load = False
    # A driver whose reputation is already at the floor cannot be handed to a
    # carrier that would not have them: they would lose the truck and the seat
    # in the same breath, with nowhere to drive. The fleet that hires anyone
    # catches that case.
    if float(profile.career.reputation) < REPUTATION_TERMINATION:
        profile.carrier_key = LAST_CHANCE_CARRIER_KEY
        profile.carrier_name = LAST_CHANCE_CARRIER_NAME
    hiring = str(getattr(profile, "carrier_name", "") or LAST_CHANCE_CARRIER_NAME)
    from .carrier_fleet import assigned_truck_key

    profile.truck = assigned_truck_key(profile)
    profile.dispatch_board_cache = None
    lines = [
        f"You owed {money_text(settled)} against a {label} that would bring "
        f"about {money_text(proceeds)} at sale, so the loan is no longer "
        "covered by the truck behind it, and the lender has taken it back.",
        "The sale closes the loan. What you owed is settled and your cash is back to zero.",
        KEPT_LINE,
        f"You are a company driver again, on the payroll at {hiring} and in a "
        "carrier tractor. The owner-operator path is still open to you, and "
        "the buy-in gates are the same ones you cleared to get here.",
        BACK_TO_WORK_LINE,
    ]
    record.setback_notice_kind = "repossession"
    record.setback_notice_lines = list(lines)
    return lines


def setback_pending(profile) -> bool:
    record = getattr(profile, "driving_record", None)
    return bool(getattr(record, "setback_notice_lines", None))


def clear_setback_notice(profile) -> None:
    record = profile.driving_record
    record.setback_notice_kind = ""
    record.setback_notice_lines = []


# -- warnings ---------------------------------------------------------------


def debt_warning_line(profile, terse: bool = False) -> str:
    """The warning this rung is owed, or empty when none is.

    Terse keeps every rung and never drops the ceiling or the consequence --
    they are money with a career attached, which is exactly what terse is for.
    What terse drops is the sentence about what brings it down.
    """
    rung = debt_rung(profile)
    if rung == 0:
        return ""
    owed = money_text(debt_owed(profile))
    if hard_capped(profile):
        if terse:
            return f"Owed {owed}. Held there; a quarter of each settlement pays it down."
        return (
            f"You owe {owed}. Your carrier holds it there and writes off anything "
            "past it, so it cannot grow. A quarter of each settlement goes to it "
            "and three quarters always reaches you."
        )
    ceiling = money_text(debt_ceiling(profile))
    consequence = ceiling_consequence_text(profile)
    if rung == 1:
        if terse:
            return f"Owed {owed}. Ceiling {ceiling}."
        return (
            f"You owe {owed}. A quarter of every settlement now goes to it, and "
            "three quarters always reaches you, so you will never finish a run "
            f"with nothing. The ceiling on this is {ceiling}."
        )
    if rung == 2:
        if terse:
            return f"Owed {owed}, over halfway to a ceiling of {ceiling}."
        return (
            f"You owe {owed}, which is over halfway to a ceiling of {ceiling}. "
            "A quarter of every settlement is paying it down; running clean and "
            "on time keeps new charges off it."
        )
    if terse:
        return f"Owed {owed}. At {ceiling}, {consequence}."
    return (
        f"You owe {owed}, against a ceiling of {ceiling}. This is the last "
        f"warning before it: at {ceiling}, {consequence}. You have room for a "
        "couple more settlements at what your runs pay, and a quarter of each "
        "one is paying it down."
    )


def debt_line(profile) -> str:
    """The reviewable debt line: what you owe, the ceiling, and what happens.

    Empty when there is nothing owed, so a solvent driver never hears it.
    """
    owed = debt_owed(profile)
    if owed < 1.0:
        return ""
    if hard_capped(profile):
        return (
            f"Owed: {money_text(owed)}. Your carrier holds it there and writes "
            "off anything past it. Part of every settlement pays it down."
        )
    ceiling = debt_ceiling(profile)
    return (
        f"Owed: {money_text(owed)} of {money_text(ceiling)}. Past that, "
        f"{ceiling_consequence_text(profile)}."
    )
