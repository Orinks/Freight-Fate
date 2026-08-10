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
# Prior citations anywhere in the career make the next one cost more, and
# nothing caps it. The step schedule above is the severe end of real
# first-offense CDL law, but a first offense is the cheapest a violation ever
# is: repeat and aggravated speeding is charged as a misdemeanor in several
# states, habitual-offender statutes stack penalties further, and court costs
# and surcharges ride on top of every count. A driver who keeps collecting
# citations keeps paying more, without limit -- which is the honest shape of
# the real thing and the point of the schedule.
CITATION_REPEAT_STEP = 0.5

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


def speeding_citation_fine(mph_over: float, prior_citations: int = 0) -> float:
    """What a speeding citation costs, by how far over and how many priors."""
    fine = SPEEDING_FINE_STEPS[0][1]
    for threshold, amount in SPEEDING_FINE_STEPS:
        if mph_over >= threshold:
            fine = amount
    multiplier = 1.0 + CITATION_REPEAT_STEP * max(0, int(prior_citations))
    return round(fine * multiplier, 2)


def is_serious_speed(mph_over: float) -> bool:
    """Whether this overage is an FMCSA serious traffic violation."""
    return float(mph_over) >= SERIOUS_SPEED_MPH_OVER


def repeat_fine(base_fine: float, prior_citations: int, ceiling: float | None = None) -> float:
    """The same repeat-offender scaling for non-speeding citations.

    ``ceiling`` is optional and exists only for a citation whose statute
    genuinely names a maximum; left None, the fine compounds with priors
    without limit, like the speeding schedule.
    """
    multiplier = 1.0 + CITATION_REPEAT_STEP * max(0, int(prior_citations))
    fine = base_fine * multiplier
    return round(fine if ceiling is None else min(ceiling, fine), 2)


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


def trust_text(reputation: float) -> str:
    """Where the driver stands with dispatch, in one spoken line."""
    band = trust_band(reputation)
    if band == TRUST_FULL:
        return "Dispatch trust: full. You get the whole board."
    if band == TRUST_GUARDED:
        return (
            "Dispatch trust: guarded. Dispatch is holding back some of the "
            "freight and fewer refusals. Clean on-time runs rebuild it."
        )
    if band == TRUST_POOR:
        return (
            "Dispatch trust: poor. You are back to assigned loads whatever your "
            "level, the board is down to two, and the good freight is going to "
            "other drivers. Clean on-time runs rebuild it."
        )
    return (
        "Dispatch trust: last chance. One assigned load at a time, no refusals, "
        "and the carrier is deciding whether to keep you. Clean on-time runs "
        "rebuild it."
    )


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
