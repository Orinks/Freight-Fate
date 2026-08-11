"""The driver's enforcement record: citations, serious violations, CDL standing.

This models real US commercial-driver enforcement rather than a softened
version of it, because the softened version taught players nothing: a driver
could run from troopers twice, take spike strips twice, and keep every load on
the board.

Sources for every number here:

* 49 CFR 383.51 Table 2 (serious traffic violations). Speeding 15 mph or more
  over the limit, reckless driving, improper lane changes, and following too
  closely are serious violations. A **second** conviction inside three years
  disqualifies the CDL for 60 days; a **third or subsequent** for 120 days.
* 49 CFR 383.51 Table 1 (major offenses). Using a commercial vehicle in the
  commission of a felony -- which is what fleeing and eluding a police officer
  is in most states -- disqualifies the CDL for one year on the first offense
  and for **life** on the second. Leaving the scene carries the same pair.
* CDL speeding fines. The top-of-range fine for a first offense of 15 mph or
  more over the limit is 2,500 dollars (Illinois; Arizona matches it), so that
  is the ceiling a single speeding citation can reach here.
* 49 CFR 386 Appendix B. Violating an out-of-service order carries a civil
  penalty of not less than 3,961 dollars for a first conviction and not less
  than 7,924 dollars for a second.
* Work zone penalty doubling. Nevada, Texas and Pennsylvania are among the
  states that double the fine for a violation committed inside a marked work
  zone, whatever the violation was. Every citation here doubles the same way
  inside a construction zone, and the driver is told that is why.
* FMCSA CSA Unsafe Driving BASIC. Every roadside citation is weighted and
  follows the *carrier*, which is why a company driver's citations cost the
  carrier's standing and eventually the job, while an owner-operator simply
  pays and watches their own authority.

Nothing here is harsher than the real rule. Where the real rule gives a range,
this takes the severe end of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

HOURS_PER_DAY = 24.0

# -- serious traffic violations (49 CFR 383.51 Table 2) ----------------------

# Speeding this far over the posted limit is a serious traffic violation, not
# an expensive inconvenience.
SERIOUS_SPEED_MPH_OVER = 15.0
# Convictions count against each other for three years.
SERIOUS_WINDOW_DAYS = 3 * 365
SERIOUS_SECOND_SUSPENSION_DAYS = 60
SERIOUS_THIRD_SUSPENSION_DAYS = 120

# -- major offenses (49 CFR 383.51 Table 1) ---------------------------------

MAJOR_FIRST_DISQUALIFICATION_DAYS = 365
# The second major offense is a lifetime disqualification. Represented by the
# flag rather than a duration, because there is no date it clears.

SUSPENSION_SERIOUS = "serious"
SUSPENSION_MAJOR = "major"
SUSPENSION_LIFETIME = "lifetime"

# -- money ------------------------------------------------------------------

# Speeding citation by how far over the limit, taking the severe end of the
# published state schedules. The 15-mph step is where a citation also becomes
# a serious traffic violation, which is why the money jumps there too.
SPEEDING_FINE_STEPS: tuple[tuple[float, float], ...] = (
    (0.0, 250.0),
    (10.0, 400.0),
    (15.0, 1_000.0),
    (20.0, 1_600.0),
    (30.0, 2_500.0),
)
# Prior citations anywhere in the career make the next one cost more. The step
# schedule above is the severe end of real first-offense CDL law, but a first
# offense is the cheapest a violation ever is: repeat and aggravated speeding
# is charged as a misdemeanor in several states, habitual-offender statutes
# stack penalties further, and court costs and surcharges ride on top of every
# count.
#
# The same step now scales every flat fine below, not just speeding. There is
# deliberately one knob: a second repeat ladder would be a second thing to
# tune, a second thing to explain, and a second thing to drift.
CITATION_REPEAT_STEP = 0.5

# ...but the step is capped, which it was not when it applied to speeding
# alone. Two reasons, and the second is the binding one.
#
# Real repeat offenders are charged "double, even triple" a standard fine, so
# the shape is right but the runaway is not. Uncapped, a career driver's scale
# bypass reached 19,800 dollars by twenty priors, and 39,600 inside roadwork,
# against a federal ceiling of 10,000 for the real offense.
#
# The binding constraint is solvency, not statute. An owner-operator who owes
# more than ``solvency.REPOSSESSION_FLOOR`` (12,000) loses the tractor. A
# single citation must never be able to reach that on its own, or one traffic
# stop repossesses a truck -- which no player would read as a rule, only as
# the game breaking. Capping the step at 2.0 leaves the construction-zone
# doubling to ride on top for a worst case of 4x base: unsafe equipment tops
# out at 9,200 and the very worst case in the game, 30-plus over in a work
# zone as a repeat offender, at 10,000. Punishing, survivable, and clear of
# the floor.
#
# Deliberately capping the STEP and not the total: the zone doubling stays
# whole so the spoken "it is doubled because you were in a construction zone"
# is always true. A total cap would silently swallow it for repeat offenders
# and make that line a lie.
#
# The money therefore stops climbing after the third citation -- 1,800 then
# 2,700 then 3,600 for a bypass -- and that is the intended shape rather than
# a gap. Past that the deterrent is the record, not the wallet: the serious
# violation ladder and the suspension tiers above keep escalating for the
# whole career, and losing the licence costs far more than any fine.
CITATION_REPEAT_MAX_MULTIPLIER = 2.0
# A fine earned inside an active construction zone is doubled. That is the
# real rule, not a game rule -- Nevada, Texas and Pennsylvania all double the
# penalty for a violation committed inside a marked work zone, and the sign at
# the taper that says so is a sign real drivers read. It multiplies the
# repeat-offender figure rather than adding to it, because a state that does
# both doubles whatever the driver already owed.
CONSTRUCTION_ZONE_FINE_MULTIPLIER = 2.0

# -- what each citation costs before those multipliers ----------------------
#
# Every fine amount in the game lives here, beside the schedule and the
# multipliers that scale it. They used to be scattered through the driving
# layer, where the chain-law citation had drifted into two separate constants
# that each claimed to be the Colorado number.

# FMCSA driver-level penalty for operating a commercial vehicle with unsafe
# conditions: 2,304 dollars.
UNSAFE_DAMAGE_FINE = 2300.0
# Running an open scale. State fines run from 250 dollars into four figures,
# and California and New York both pass 1,000 on a first offense; the federal
# exposure standing behind them reaches 10,000.
WEIGH_STATION_BYPASS_FINE = 1800.0
# Colorado's chain-law citation: 500 dollars plus a 79-dollar surcharge.
CHAIN_LAW_FINE = 580.0
# Following too closely is a serious traffic violation under 49 CFR 383.51
# Table 2 -- two inside three years disqualify the CDL for 60 days -- so it is
# priced as one, not as the fender-bender it looks like from the cab.
FOLLOWING_TOO_CLOSE_FINE = 600.0
# Improper lane use is a serious traffic violation on the same table. Virginia
# charges 250 dollars for it, or 500 in a designated highway safety corridor;
# this takes the corridor figure.
LANE_MISUSE_FINE = 500.0
# Running dark after sunset: an equipment violation everywhere, written as a
# fix-it-plus-fine in most states.
LIGHTS_FINE = 350.0
# Driving through the barrels instead of merging out of a coned-off lane.
# Missouri RSMo 304.585 (endangerment of a highway worker) lists striking or
# moving barrels, barriers and signs as an offense in its own right -- the one
# category in that statute that does not need workers to be present -- at up
# to 1,000 dollars. This takes the top of that range: it sits above the
# equipment fines because what it risks is the crew, not the truck.
WORK_ZONE_BARRELS_FINE = 1000.0
# Failing to pull over promptly -- and then stopping -- is not fleeing. It is
# charged as failing to obey a lawful order, which rides in with reckless
# driving as a serious traffic violation under 49 CFR 383.51 Table 2, above
# the ordinary commercial citation range.
FAILURE_TO_STOP_CITATION_FINE = 1500.0
# Fleeing and eluding a police officer in a commercial vehicle is a felony in
# most states -- a third-degree felony in Florida, for one, carrying a fine of
# up to 5,000 dollars. This takes that top of range, and the conviction is a
# major offense under 49 CFR 383.51 Table 1 on top of the money.
FAILURE_TO_STOP_FINE = 5000.0

# -- fatigue (49 CFR 392.3 / 392.5) -----------------------------------------

# 49 CFR 392.3 forbids operating a commercial vehicle while ability or
# alertness is impaired by fatigue, and 392.5 lets an officer put a fatigued
# driver out of service on the spot. Running off the road asleep is also a
# preventable safety incident: carriers discipline it and repeat it is a
# termination, and it feeds the CSA fatigued-driving BASIC.
FATIGUE_EVENT_REPUTATION_HIT = 6.0
# Do it more than once in a career and it stops being an accident. The second
# and every later run-off-road fatigue event is a 392.3 violation on the
# record, joining the serious-violation ladder.
FATIGUE_EVENTS_BEFORE_SERIOUS = 2
# The standard fatigue out-of-service order is ten consecutive hours off duty.
FATIGUE_OUT_OF_SERVICE_HOURS = 10.0

# -- dispatch trust ---------------------------------------------------------

# Reputation has always paid a trust bonus. It now also decides what dispatch
# will put in front of you and how much choice you get, and it slides the
# whole way down instead of tripping one gate at the bottom.
#
# New careers start at 50 and every on-time delivery adds 2, so a driver who
# runs clean never leaves the top band and never sees any of this. The full
# band reaches down to 40 on purpose: refusing an assigned load costs 2 and
# is a sanctioned move with its own budget, so spending that budget must not
# by itself read as losing dispatch's confidence.
TRUST_FULL = "full"
TRUST_GUARDED = "guarded"
TRUST_POOR = "poor"
TRUST_LAST_CHANCE = "last chance"

REPUTATION_FULL_BOARD = 40.0
REPUTATION_GUARDED = 28.0
REPUTATION_POOR = 16.0
# A company driver below this has run out of carrier patience.
REPUTATION_TERMINATION = 8.0
# The fleet a terminated driver can still get hired by.
LAST_CHANCE_CARRIER_KEY = "great_lakes_training"
LAST_CHANCE_CARRIER_NAME = "Great Lakes Training Transport"


def citation_fine(
    base_fine: float,
    prior_citations: int = 0,
    *,
    construction_zone: bool = False,
    ceiling: float | None = None,
) -> float:
    """What a citation actually costs: the base, the priors, and where it happened.

    The one place a fine is priced. Every charge in the game comes through
    here so that neither multiplier can be applied twice, skipped, or applied
    in a different order somewhere else.

    They compound rather than add. The repeat-offender step decides what this
    driver owes for this violation; the construction zone then doubles that
    whole figure, which is what a state that does both actually does to a
    repeat offender. A second bypass inside roadwork is 1,800 x 1.5 x 2.

    The repeat step is capped at ``CITATION_REPEAT_MAX_MULTIPLIER``. Repeat
    offenders really are charged "double, even triple" a standard fine, and
    that is the shape this models -- but the step alone is unbounded, and
    left to run it priced a career driver's scale bypass at 19,800 dollars
    by twenty priors and 39,600 inside roadwork, against a federal ceiling
    of 10,000 for the real offense. An owner-operator starts with 18,000, so
    a single stop could exceed a whole career's capital. Past a point the
    arithmetic stops reading as severity and starts reading as a bug.

    The construction-zone doubling is applied AFTER the cap, not folded into
    it: the cap governs how much being a repeat offender can cost you, and
    where the violation happened is a separate fact about this one citation.

    ``ceiling`` is optional and names a statutory maximum for a specific
    citation; it is the last word, applied after everything else.
    """
    step = 1.0 + CITATION_REPEAT_STEP * max(0, int(prior_citations))
    multiplier = min(step, CITATION_REPEAT_MAX_MULTIPLIER)
    if construction_zone:
        multiplier *= CONSTRUCTION_ZONE_FINE_MULTIPLIER
    fine = float(base_fine) * multiplier
    return round(fine if ceiling is None else min(ceiling, fine), 2)


def speeding_citation_fine(
    mph_over: float, prior_citations: int = 0, *, construction_zone: bool = False
) -> float:
    """What a speeding citation costs, by how far over, how many priors, and where."""
    fine = SPEEDING_FINE_STEPS[0][1]
    for threshold, amount in SPEEDING_FINE_STEPS:
        if mph_over >= threshold:
            fine = amount
    return citation_fine(fine, prior_citations, construction_zone=construction_zone)


def career_citations(profile) -> int:
    """How many citations this career already carries, for the repeat scaling.

    Tolerates a profile with no record at all: a career that predates the
    licence file is a first offender, not a crash.
    """
    record = getattr(profile, "driving_record", None)
    return int(getattr(record, "citations", 0) or 0)


def construction_zone_fine_clause(construction_zone: bool) -> str:
    """Why the figure is twice what it would be anywhere else.

    Spoken after the amount, never instead of it. A driver who hears a doubled
    number with no explanation hears a bug. Empty when nothing was doubled, so
    every caller can append it unconditionally.
    """
    return " It is doubled because you were in a construction zone." if construction_zone else ""


def is_serious_speed(mph_over: float) -> bool:
    """Whether this overage is an FMCSA serious traffic violation."""
    return float(mph_over) >= SERIOUS_SPEED_MPH_OVER


@dataclass
class DrivingRecord:
    """What the licence file remembers about this driver, for the whole career.

    Times are career game hours -- the same clock ``Profile.game_hours`` runs
    on -- so a suspension is served in game time and survives save and load.
    """

    # Career game hours at which each serious violation was recorded.
    serious_violations: list[float] = field(default_factory=list)
    # Career game hours at which each major offense was recorded.
    major_offenses: list[float] = field(default_factory=list)
    citations: int = 0  # every spoken roadside citation, lifetime
    fines_paid: float = 0.0  # lifetime enforcement money, all sources
    fatigue_events: int = 0  # times this driver ran off the road asleep
    # The trust band the driver has already been told about, so a change is
    # spoken once when it happens and never repeated on a timer.
    trust_band_heard: str = ""
    # The debt warning the driver has already been given, on the same
    # discipline: rungs are spoken when they move, never on a timer.
    debt_rung_heard: int = 0
    # Times a lender has taken an owner-operator's tractor back.
    repossessions: int = 0
    # A career-changing setback that has happened but not yet been read: the
    # lines are composed when it lands and kept until the driver acknowledges
    # them, so the longest and most consequential text in the game survives a
    # keypress, a save, and a reload.
    setback_notice_kind: str = ""  # "" | "termination" | "repossession"
    setback_notice_lines: list[str] = field(default_factory=list)
    suspended_until_h: float = 0.0  # career game hours the CDL comes back
    suspension_reason: str = ""  # SUSPENSION_SERIOUS / SUSPENSION_MAJOR
    lifetime_disqualified: bool = False
    carrier_terminations: int = 0
    # A career that predates the record loaded with offenses already on it and
    # has not yet heard the one-time explanation of where it now stands.
    notice_pending: bool = False

    # -- reads --------------------------------------------------------------

    def serious_in_window(self, game_hours: float) -> int:
        """Serious violations still inside the three-year counting window."""
        cutoff = float(game_hours) - SERIOUS_WINDOW_DAYS * HOURS_PER_DAY
        return sum(1 for at in self.serious_violations if at >= cutoff)

    @property
    def major_count(self) -> int:
        return len(self.major_offenses)

    def suspended(self, game_hours: float) -> bool:
        return self.lifetime_disqualified or float(game_hours) < self.suspended_until_h

    def hours_left(self, game_hours: float) -> float:
        if self.lifetime_disqualified:
            return float("inf")
        return max(0.0, self.suspended_until_h - float(game_hours))

    def days_left(self, game_hours: float) -> float:
        left = self.hours_left(game_hours)
        return left if left == float("inf") else left / HOURS_PER_DAY

    def clean(self, game_hours: float) -> bool:
        """No standing a player would want explained to them."""
        return (
            not self.lifetime_disqualified
            and not self.suspended(game_hours)
            and self.serious_in_window(game_hours) == 0
            and not self.major_offenses
        )

    # -- writes -------------------------------------------------------------

    def record_citation(self, fine: float) -> None:
        self.citations += 1
        self.fines_paid += max(0.0, float(fine))

    def record_serious_violation(self, game_hours: float) -> int:
        """Log a serious traffic violation; returns the count in the window.

        Applies the 383.51 Table 2 ladder: the second conviction inside three
        years suspends the CDL for 60 days, the third and every one after for
        120 days.
        """
        self.serious_violations.append(float(game_hours))
        count = self.serious_in_window(game_hours)
        if count == 2:
            self._suspend(game_hours, SERIOUS_SECOND_SUSPENSION_DAYS, SUSPENSION_SERIOUS)
        elif count >= 3:
            self._suspend(game_hours, SERIOUS_THIRD_SUSPENSION_DAYS, SUSPENSION_SERIOUS)
        return count

    def record_fatigue_event(self, game_hours: float) -> tuple[int, int]:
        """Log running off the road asleep. Returns (fatigue events, serious).

        The first one is a preventable safety incident: it costs standing but
        not the licence. From the second on it is a 49 CFR 392.3 violation --
        operating a commercial vehicle impaired by fatigue -- and it joins the
        serious-violation ladder like any other.
        """
        self.fatigue_events += 1
        serious = 0
        if self.fatigue_events >= FATIGUE_EVENTS_BEFORE_SERIOUS:
            serious = self.record_serious_violation(game_hours)
        return self.fatigue_events, serious

    def record_major_offense(self, game_hours: float) -> str:
        """Log a major offense; returns SUSPENSION_MAJOR or SUSPENSION_LIFETIME.

        Table 1: one year for the first, life for the second.
        """
        self.major_offenses.append(float(game_hours))
        if len(self.major_offenses) >= 2:
            self.lifetime_disqualified = True
            self.suspension_reason = SUSPENSION_LIFETIME
            return SUSPENSION_LIFETIME
        self._suspend(game_hours, MAJOR_FIRST_DISQUALIFICATION_DAYS, SUSPENSION_MAJOR)
        return SUSPENSION_MAJOR

    def _suspend(self, game_hours: float, days: int, reason: str) -> None:
        # Suspensions run consecutively: a new one starts where the last one
        # ends, exactly as a state licensing agency stacks them.
        start = max(float(game_hours), self.suspended_until_h)
        self.suspended_until_h = start + days * HOURS_PER_DAY
        self.suspension_reason = reason

    def serve_until(self, game_hours: float) -> None:
        """Called when the career clock has been advanced past a suspension."""
        if not self.lifetime_disqualified and float(game_hours) >= self.suspended_until_h:
            self.suspended_until_h = 0.0
            self.suspension_reason = ""


# -- dispatch access --------------------------------------------------------


def trust_band(reputation: float) -> str:
    """How far dispatch trusts this driver right now."""
    rep = float(reputation)
    if rep >= REPUTATION_FULL_BOARD:
        return TRUST_FULL
    if rep >= REPUTATION_GUARDED:
        return TRUST_GUARDED
    if rep >= REPUTATION_POOR:
        return TRUST_POOR
    return TRUST_LAST_CHANCE


def board_offers_for_reputation(base: int, reputation: float) -> int:
    """How many loads dispatch will still put in front of this driver."""
    band = trust_band(reputation)
    if band == TRUST_FULL:
        return base
    if band == TRUST_GUARDED:
        return max(3, base - 2)
    if band == TRUST_POOR:
        return 2
    return 1


def trust_revokes_load_choice(reputation: float) -> bool:
    """Below guarded, a senior driver goes back to taking what dispatch gives.

    The career already earns the right to pick loads at level 8. Losing
    dispatch's trust takes that privilege back -- the game's own language for
    "we do not let you choose any more".
    """
    return trust_band(reputation) in (TRUST_POOR, TRUST_LAST_CHANCE)


def trust_decline_penalty(reputation: float) -> int:
    """Refusals dispatch takes off the budget as trust falls."""
    band = trust_band(reputation)
    if band == TRUST_GUARDED:
        return 1
    if band == TRUST_POOR:
        return 2
    if band == TRUST_LAST_CHANCE:
        return 99  # no refusals at all: take it or leave the job
    return 0


def trust_band_text(band: str) -> str:
    """What a trust band means, without saying what brings it back.

    Split out because "clean on-time runs rebuild it" stopped being true once
    money and the licence fed the same band: a driver whose service is fine
    and whose debt is the problem can run clean forever and watch nothing
    move. The way back has to name the thing that is actually holding it.
    """
    if band == TRUST_FULL:
        return "Dispatch trust: full. You get the whole board."
    if band == TRUST_GUARDED:
        return (
            "Dispatch trust: guarded. Dispatch is holding back some of the "
            "freight and fewer refusals."
        )
    if band == TRUST_POOR:
        return (
            "Dispatch trust: poor. You are back to assigned loads whatever your "
            "level, the board is down to two, and the good freight is going to "
            "other drivers."
        )
    return (
        "Dispatch trust: last chance. One assigned load at a time, no refusals, "
        "and the carrier is deciding whether to keep you."
    )


def trust_text(reputation: float) -> str:
    """Where the driver stands with dispatch on service alone, in one line."""
    band = trust_band(reputation)
    if band == TRUST_FULL:
        return trust_band_text(band)
    return f"{trust_band_text(band)} Clean on-time runs rebuild it."


# -- the whole picture: service, licence, and money -------------------------

# Dispatch trust is one ladder with three inputs, not three ladders. Service
# has always fed it. The licence and what the driver owes now feed the same
# rungs, because a yard that will not give a driver its good freight is the
# same yard that will not give them its good iron, for the same reasons.
#
# It stays one ladder on purpose: a second parallel status would cost a screen
# reader user a whole extra concept to hold, and there is only one question
# behind all of it -- how much is this carrier willing to put in your hands.

# Worst first, so the binding input is simply the minimum.
_BAND_ORDER = (TRUST_LAST_CHANCE, TRUST_POOR, TRUST_GUARDED, TRUST_FULL)

CAUSE_SERVICE = "service"
CAUSE_LICENCE = "licence"
CAUSE_DEBT = "debt"


def worst_band(*bands: str) -> str:
    return min(bands, key=lambda band: _BAND_ORDER.index(band))


def licence_band(profile) -> str:
    """A licence that is not valid takes the seat, whatever the service record.

    Only a suspension counts, never a serious violation on its own. A
    suspension is a fact with a date on it that the driver can already hear
    and wait out; violations age off over three game years, and gating the
    equipment on those would be a hold no amount of good driving could clear.
    Those already reach dispatch trust the honest way, through reputation.
    """
    record = getattr(profile, "driving_record", None)
    if record is None:
        return TRUST_FULL
    hours = float(getattr(profile, "game_hours", 0.0) or 0.0)
    return TRUST_LAST_CHANCE if record.suspended(hours) else TRUST_FULL


def solvency_band(profile) -> str:
    """How far what the driver owes has eaten into the carrier's patience."""
    from .solvency import debt_rung

    return (TRUST_FULL, TRUST_GUARDED, TRUST_POOR, TRUST_LAST_CHANCE)[debt_rung(profile)]


def standing_band(profile) -> str:
    """The band the carrier actually acts on: the worst of the three inputs.

    Internal name only. Spoken text calls this dispatch trust, because that is
    the noun the game already uses and ``docs/ontology.md`` already rules
    "standing" out as a synonym for it.
    """
    return worst_band(
        trust_band(float(getattr(getattr(profile, "career", None), "reputation", 50.0))),
        licence_band(profile),
        solvency_band(profile),
    )


def standing_cause(profile) -> str:
    """Which input is holding the band down. Empty when nothing is."""
    band = standing_band(profile)
    if band == TRUST_FULL:
        return ""
    if licence_band(profile) == band:
        return CAUSE_LICENCE
    if solvency_band(profile) == band:
        return CAUSE_DEBT
    return CAUSE_SERVICE


def standing_way_back(profile) -> str:
    """What actually brings the band up, naming the thing that is holding it."""
    from .solvency import debt_owed, money_text

    cause = standing_cause(profile)
    if cause == CAUSE_LICENCE:
        clears = clears_text(profile)
        if not clears:
            return "Your CDL is disqualified for life, so the seat is not coming back."
        return f"Your CDL is suspended, so the yard holds your seat until it clears {clears}."
    if cause == CAUSE_DEBT:
        line = f"You owe {money_text(debt_owed(profile))}, and that is what is holding it."
        if trust_band(float(profile.career.reputation)) != TRUST_FULL:
            return f"{line} Paying it down brings it back, and clean on-time runs help too."
        return f"{line} Paying it down brings it back."
    if cause == CAUSE_SERVICE:
        return "Clean on-time runs rebuild it."
    return ""


def dispatch_trust_line(profile) -> str:
    """Everything dispatch trust is doing to this driver, on demand, in one go.

    Spoken when the band changes and whenever the player asks for it. Never on
    a timer, and never for a driver in full trust beyond the one plain line
    they already heard.
    """
    from .career import xp_rate_clause
    from .carrier_fleet import equipment_hold_clause

    band = standing_band(profile)
    parts = [trust_band_text(band)]
    way_back = standing_way_back(profile)
    if way_back:
        parts.append(way_back)
    hold = equipment_hold_clause(profile)
    if hold:
        parts.append(hold)
    rate = xp_rate_clause(band)
    if rate:
        parts.append(rate)
    return " ".join(parts)


def board_reputation_note(reputation: float) -> str:
    """Why the board is short, said plainly. Empty when it is not short."""
    return "" if trust_band(reputation) == TRUST_FULL else trust_text(reputation)


def carrier_termination_due(profile) -> bool:
    """A company driver the carrier will not keep on the insurance any longer."""
    from .business import is_owner_operator

    if is_owner_operator(getattr(profile, "business_status", "")):
        return False
    if getattr(profile, "carrier_key", "") == LAST_CHANCE_CARRIER_KEY:
        return False  # already at the fleet of last resort; nowhere further down
    return float(getattr(profile.career, "reputation", 50.0)) < REPUTATION_TERMINATION


# -- spoken standing --------------------------------------------------------

_COUNT_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_ORDINAL_WORDS = ("", "first", "second", "third", "fourth", "fifth", "sixth", "seventh")


def count_word(n: int) -> str:
    n = int(n)
    return _COUNT_WORDS[n] if 0 <= n < len(_COUNT_WORDS) else f"{n}"


def ordinal_word(n: int) -> str:
    n = int(n)
    return _ORDINAL_WORDS[n] if 0 < n < len(_ORDINAL_WORDS) else f"{n}th"


def days_text(days: float) -> str:
    """A suspension length in game days, never raw hours."""
    whole = max(1, int(round(days)))
    return "1 day" if whole == 1 else f"{whole} days"


def clears_text(profile) -> str:
    """When the suspension clears, as a spoken game-calendar date."""
    from ..sim.season import date_text, weekday_name

    record = profile.driving_record
    if record.lifetime_disqualified:
        return ""
    offset = float(getattr(profile, "calendar_offset_days", 0) or 0) * HOURS_PER_DAY
    at = record.suspended_until_h + offset
    return f"{weekday_name(at)}, {date_text(at)}"


def status_verb(record: DrivingRecord) -> str:
    """A serious-violation ladder suspends; a major offense disqualifies."""
    return "disqualified" if record.suspension_reason == SUSPENSION_MAJOR else "suspended"


def standing_text(profile) -> str:
    """One spoken line of where this driver stands. Asked for, never on a timer."""
    record = profile.driving_record
    game_hours = float(getattr(profile, "game_hours", 0.0) or 0.0)
    if record.lifetime_disqualified:
        return "Record: your CDL is disqualified for life. You cannot take driving work."
    if record.suspended(game_hours):
        left = days_text(record.days_left(game_hours))
        verb = status_verb(record)
        return f"Record: CDL {verb}, {left} remaining. It clears {clears_text(profile)}."
    serious = record.serious_in_window(game_hours)
    majors = record.major_count
    if serious == 0 and majors == 0:
        return "Record: clean."
    parts = []
    if serious:
        noun = "serious violation" if serious == 1 else "serious violations"
        parts.append(f"{count_word(serious)} {noun}")
    if majors:
        noun = "major offense" if majors == 1 else "major offenses"
        parts.append(f"{count_word(majors)} {noun}")
    tail = ""
    if majors >= 1:
        tail = " One more major offense disqualifies your CDL for life."
    elif serious == 1:
        tail = " One more before your CDL is suspended for 60 days."
    return f"Record: {', '.join(parts)}.{tail}"


def suspension_board_line(profile) -> str:
    """The first thing the dispatch board says while the CDL is not valid."""
    record = profile.driving_record
    if record.lifetime_disqualified:
        return (
            "Dispatch board. Your CDL is disqualified for life, so there is no "
            "driving work here. The board is listed for reference only."
        )
    return (
        f"Dispatch board. Your CDL is {status_verb(record)}; driving jobs "
        f"return {clears_text(profile)}."
    )


def suspension_refusal_line(profile) -> str:
    """Why a job cannot be taken, said once, with the way back."""
    record = profile.driving_record
    if record.lifetime_disqualified:
        return (
            "You cannot take driving work with a lifetime CDL disqualification. "
            "Escape goes back to the terminal."
        )
    return (
        f"You cannot take this job while your CDL is {status_verb(record)}. It "
        f"clears {clears_text(profile)}. Escape goes back to the board."
    )


def career_menu_status(profile) -> str:
    """The CDL line on the career screens: short, factual, always available."""
    record = profile.driving_record
    game_hours = float(getattr(profile, "game_hours", 0.0) or 0.0)
    if record.lifetime_disqualified:
        return "CDL: disqualified for life"
    if record.suspended(game_hours):
        left = days_text(record.days_left(game_hours))
        return f"CDL: {status_verb(record)}, {left} remaining"
    return "CDL: clear"


# -- legacy careers ---------------------------------------------------------


def seed_record_from_save(data: dict) -> DrivingRecord:
    """Build a record for a career saved before the record existed.

    No amnesty: every offense the save actually still holds is counted, and
    the driver hears about it once. Offenses are read out of the mid-delivery
    trip snapshot, which is the only place the old build kept them.
    """
    record = DrivingRecord()
    trip = data.get("active_trip")
    game_hours = float(data.get("game_hours", 0.0) or 0.0)
    if isinstance(trip, dict):
        for _ in range(int(trip.get("failure_to_stop_count", 0) or 0)):
            record.record_major_offense(game_hours)
        for _ in range(int(trip.get("speeding_tickets", 0) or 0)):
            record.record_citation(float(trip.get("ticket_fines_paid", 0.0) or 0.0))
    reputation = float((data.get("career") or {}).get("reputation", 50.0) or 50.0)
    if not record.clean(game_hours) or reputation < REPUTATION_FULL_BOARD:
        record.notice_pending = True
    return record
