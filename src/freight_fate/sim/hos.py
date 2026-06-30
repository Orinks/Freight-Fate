"""Hours of service, ELD duty status, fatigue, and the day/night clock.

Simplified FMCSA-style rules running entirely on the in-game clock (the
trip's ``game_minutes``, never wall time): 11 hours of driving after a
10-hour reset, a 14-hour duty window after coming on duty, and a
30-minute break after 8 cumulative hours of driving. The break may be any
30 consecutive non-driving minutes, including on-duty-not-driving work.

The model includes 7/3 and 8/2 sleeper split credits but intentionally skips
60/70-hour cycle limits for now; the save schema records explicit duty
statuses so those rules can be added without changing how drive, facility,
and POI time is classified.

Everything here is deterministic and pygame-free so the headless tests
can exercise the rules directly.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

HOS_MODES = ("realistic", "relaxed", "debug_off")
HOS_NON_ENFORCED_MODES = {"off", "debug_off"}
DUTY_STATUSES = ("driving", "on_duty_not_driving", "off_duty", "sleeper_berth")
SPLIT_SHORT_MIN = 120.0
SPLIT_SHORT_ALT_MIN = 180.0
SPLIT_LONG_MIN = 420.0
SPLIT_LONG_ALT_MIN = 480.0
HOS_HISTORY_MAX = 96
HOS_SPLIT_REST_HISTORY_MAX = 16

BREAK_MIN = 30.0          # minimum break that resets the 8-hour rule
SLEEP_MIN = 600.0         # a full 10-hour off-duty reset

# (drive limit, duty window, driving allowed before a 30-minute break),
# all in game minutes.
_REALISTIC = (11 * 60.0, 14 * 60.0, 8 * 60.0)
LIMITS = {
    "realistic": _REALISTIC,
    "relaxed": tuple(x * 1.25 for x in _REALISTIC),
}

# Relaxed mode keeps random road hazards rare so the player can focus on
# driver responsibility -- hours of service, fueling, repairs, fatigue --
# instead of constant emergency braking. Realistic and debug modes leave
# hazard frequency untouched.
RELAXED_HAZARD_SCALE = 0.2


def hazard_scale(mode: str) -> float:
    """Random road-hazard frequency multiplier for a difficulty mode."""
    return RELAXED_HAZARD_SCALE if mode == "relaxed" else 1.0


WARNING_THRESHOLDS_MIN = (120.0, 60.0, 30.0)

_THRESHOLD_PHRASES = {120.0: "2 hours", 60.0: "1 hour", 30.0: "30 minutes"}


def warning_is_urgent(message: str) -> bool:
    return message.startswith("Hours of service violation:")


def _positive_minutes(minutes: float) -> float:
    value = float(minutes)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("HOS time increments must be finite positive minutes")
    return value


@dataclass
class HosEvent:
    status: str
    minutes: float
    drive_before: float
    duty_before: float
    since_break_before: float
    source: str = "normal"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "minutes": self.minutes,
            "drive_before": self.drive_before,
            "duty_before": self.duty_before,
            "since_break_before": self.since_break_before,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data) -> HosEvent | None:
        if not isinstance(data, dict):
            return None
        try:
            status = str(data.get("status", "off_duty"))
            if status not in DUTY_STATUSES:
                return None
            return cls(
                status=status,
                minutes=float(data.get("minutes", 0.0)),
                drive_before=float(data.get("drive_before", 0.0)),
                duty_before=float(data.get("duty_before", 0.0)),
                since_break_before=float(data.get("since_break_before", 0.0)),
                source=str(data.get("source", "normal")),
            )
        except (TypeError, ValueError):
            return None


@dataclass
class HosClock:
    """One ELD-style shift ledger, in game minutes.

    ``duty_min`` is the elapsed 14-hour window since the last qualifying
    10-hour reset, not just on-duty labor. FMCSA's 14-hour window is not
    extended by short off-duty breaks, so short breaks keep advancing it.
    """

    driving_min: float = 0.0      # time at the wheel this shift
    duty_min: float = 0.0         # elapsed 14-hour duty window
    since_break_min: float = 0.0  # driving since the last 30-minute break
    status: str = "off_duty"
    non_driving_min: float = 0.0  # consecutive non-driving time
    off_duty_min: float = 0.0     # consecutive off-duty/sleeper time
    warned: list[str] = field(default_factory=list)  # thresholds already spoken
    history: list[HosEvent] = field(default_factory=list)
    split_rest_history: list[HosEvent] = field(default_factory=list)
    split_credit_key: str | None = None

    # -- time accounting ------------------------------------------------------

    def drive(self, minutes: float) -> None:
        minutes = _positive_minutes(minutes)
        self._record_event("driving", minutes)
        self.driving_min += minutes
        self.duty_min += minutes
        self.since_break_min += minutes
        self.status = "driving"
        self.non_driving_min = 0.0
        self.off_duty_min = 0.0

    def on_duty(self, minutes: float) -> None:
        """Work time away from the wheel: fueling, loading, inspections, service."""
        minutes = _positive_minutes(minutes)
        self._record_event("on_duty_not_driving", minutes)
        self.duty_min += minutes
        self.status = "on_duty_not_driving"
        self.off_duty_min = 0.0
        self._record_non_driving(minutes)

    def off_duty(self, minutes: float) -> None:
        """Off-duty time. Short breaks do not extend the 14-hour window."""
        minutes = _positive_minutes(minutes)
        self._record_event("off_duty", minutes)
        self.duty_min += minutes
        self.status = "off_duty"
        self._record_non_driving(minutes)
        self.off_duty_min += minutes
        if self.off_duty_min >= SLEEP_MIN:
            self.sleep(status="off_duty")
            return
        self._apply_split_credit()

    def sleeper(self, minutes: float) -> None:
        """Sleeper-berth time. A full 10 hours resets; shorter rests may split."""
        minutes = _positive_minutes(minutes)
        self._record_event("sleeper_berth", minutes)
        self.duty_min += minutes
        self.status = "sleeper_berth"
        self._record_non_driving(minutes)
        self.off_duty_min += minutes
        if self.off_duty_min >= SLEEP_MIN:
            self.sleep(status="sleeper_berth")
            return
        self._apply_split_credit()

    def take_break(self, minutes: float) -> None:
        """A short off-duty rest. Kept for old callers and explicit break actions."""
        self.off_duty(minutes)

    def sleep(self, status: str = "sleeper_berth") -> None:
        """A full 10-hour off-duty reset: a fresh shift."""
        self._record_event(status, SLEEP_MIN, source="full_reset")
        self.driving_min = 0.0
        self.duty_min = 0.0
        self.since_break_min = 0.0
        self.status = status if status in DUTY_STATUSES else "sleeper_berth"
        self.non_driving_min = SLEEP_MIN
        self.off_duty_min = SLEEP_MIN
        self.split_credit_key = None
        self.warned.clear()

    def _record_non_driving(self, minutes: float) -> None:
        self.non_driving_min += minutes
        if self.non_driving_min >= BREAK_MIN:
            self.since_break_min = 0.0
            self.warned = [w for w in self.warned if not w.startswith("break:")]

    def _record_event(self, status: str, minutes: float, source: str = "normal") -> None:
        event = HosEvent(
            status=status,
            minutes=minutes,
            drive_before=self.driving_min,
            duty_before=self.duty_min,
            since_break_before=self.since_break_min,
            source=source,
        )
        self.history.append(event)
        self.history = self.history[-HOS_HISTORY_MAX:]
        if source == "full_reset":
            self.split_rest_history.clear()
        elif (
            source == "normal"
            and status in {"off_duty", "sleeper_berth"}
            and minutes >= SPLIT_SHORT_MIN
        ):
            self.split_rest_history.append(event)
            self.split_rest_history = self.split_rest_history[-HOS_SPLIT_REST_HISTORY_MAX:]

    def _split_event_key(self, first: HosEvent, second: HosEvent) -> str:
        first_key = (
            first.status, first.source, first.minutes,
            first.drive_before, first.duty_before, first.since_break_before)
        second_key = (
            second.status, second.source, second.minutes,
            second.drive_before, second.duty_before, second.since_break_before)
        return repr((first_key, second_key))

    def _qualifying_split_pair(self) -> tuple[HosEvent, HosEvent] | None:
        rest_events = self._split_rest_events()
        start = 0
        if self.split_credit_key is not None:
            for index, pair in enumerate(self._split_rest_pairs(rest_events)):
                if self.split_credit_key == self._split_event_key(*pair):
                    start = index + 1
                    break
        candidates = self._split_rest_pairs(rest_events[start:])
        for first, second in reversed(list(candidates)):
            if self.split_credit_key == self._split_event_key(first, second):
                continue
            if self._split_pair_qualifies(first, second):
                return first, second
        return None

    def _split_pair_qualifies(self, first: HosEvent, second: HosEvent) -> bool:
        if (
            first.source == "full_reset"
            or second.source == "full_reset"
            or first.minutes >= SLEEP_MIN
            or second.minutes >= SLEEP_MIN
        ):
            return False
        total = first.minutes + second.minutes
        if total < SLEEP_MIN:
            return False
        long_event = first if first.minutes >= second.minutes else second
        short_event = second if long_event is first else first
        if long_event.status != "sleeper_berth":
            return False
        if long_event.minutes >= SPLIT_LONG_ALT_MIN and short_event.minutes >= SPLIT_SHORT_MIN:
            return True
        return long_event.minutes >= SPLIT_LONG_MIN and short_event.minutes >= SPLIT_SHORT_ALT_MIN

    def _apply_split_credit(self) -> None:
        pair = self._qualifying_split_pair()
        if pair is None:
            return
        first, second = pair
        key = self._split_event_key(first, second)
        if self.split_credit_key == key:
            return
        self.driving_min = second.drive_before - self._split_drive_after_rest(first)
        self.duty_min = second.duty_before - self._split_duty_after_rest(first)
        self.since_break_min = 0.0
        self.split_credit_key = key
        self.warned = [w for w in self.warned if not w.startswith(("drive:", "duty:", "break:"))]

    def _split_drive_after_rest(self, event: HosEvent) -> float:
        pair = self._previous_qualifying_split_pair(event)
        if pair is not None:
            first, second = pair
            return second.drive_before - self._split_drive_after_rest(first)
        return event.drive_before

    def _split_duty_after_rest(self, event: HosEvent) -> float:
        pair = self._previous_qualifying_split_pair(event)
        if pair is not None:
            first, second = pair
            return second.duty_before - self._split_duty_after_rest(first)
        return event.duty_before + event.minutes

    def _previous_qualifying_split_pair(
            self, event: HosEvent) -> tuple[HosEvent, HosEvent] | None:
        for first, second in self._split_rest_pairs(self._split_rest_events()):
            if second is event and self._split_pair_qualifies(first, second):
                return first, second
        return None

    def _split_rest_events(self) -> list[HosEvent]:
        return list(self.split_rest_history)

    def _split_rest_pairs(self, rest_events: list[HosEvent]) -> zip[tuple[HosEvent, HosEvent]]:
        return zip(rest_events, rest_events[1:], strict=False)

    def _credited_split_pair(self) -> tuple[HosEvent, HosEvent] | None:
        if self.split_credit_key is None:
            return None
        for pair in self._split_rest_pairs(self._split_rest_events()):
            if self.split_credit_key == self._split_event_key(*pair):
                return pair
        return None

    def sleeper_split_rest(self, minutes: float, source: str = "normal") -> bool:
        minutes = _positive_minutes(minutes)
        self._record_event("sleeper_berth", minutes, source=source)
        self.duty_min += minutes
        self.status = "sleeper_berth"
        self._record_non_driving(minutes)
        self.off_duty_min += minutes
        if self.off_duty_min >= SLEEP_MIN:
            self.sleep(status="sleeper_berth")
            return False
        before_key = self.split_credit_key
        self._apply_split_credit()
        return self.split_credit_key != before_key

    # -- rule queries ----------------------------------------------------------

    def _statuses(self, mode: str) -> list[tuple[str, float, str]]:
        """(kind, minutes remaining, what is due) per enforced limit."""
        if mode not in LIMITS:
            return []
        drive_limit, duty_limit, break_after = LIMITS[mode]
        return [
            ("break", break_after - self.since_break_min,
             "you must take a 30 minute break at a rest stop"),
            ("drive", drive_limit - self.driving_min,
             "your driving time for this shift ends. You need 10 hours of sleep"),
            ("duty", duty_limit - self.duty_min,
             "your duty window closes. You need 10 hours of sleep"),
        ]

    def remaining_min(self, mode: str) -> float | None:
        """Game minutes until the nearest limit, or None when not enforced."""
        statuses = self._statuses(mode)
        if not statuses:
            return None
        return min(rem for _, rem, _ in statuses)

    def next_limit(self, mode: str) -> tuple[str, float, str] | None:
        """Nearest enforced HOS limit as ``(kind, minutes, due_text)``."""
        statuses = self._statuses(mode)
        if not statuses:
            return None
        return min(statuses, key=lambda item: item[1])

    def in_violation(self, mode: str) -> bool:
        return any(rem <= 0 for _, rem, _ in self._statuses(mode))

    def check_warnings(self, mode: str) -> list[str]:
        """Newly crossed warning messages; each threshold fires once.

        Call this every frame while driving. Crossing several thresholds at
        once (a long menu action, say) speaks only the most urgent one, but
        marks them all so nothing fires late.
        """
        candidates: list[tuple[int, float, str]] = []
        violation_priority = {"drive": 0, "duty": 1, "break": 2}
        for kind, rem, due in self._statuses(mode):
            if rem <= 0:
                key = f"{kind}:violation"
                if key not in self.warned:
                    self.warned.append(key)
                    for t in WARNING_THRESHOLDS_MIN:  # swallow the lead-up ones
                        k = f"{kind}:{t:.0f}"
                        if k not in self.warned:
                            self.warned.append(k)
                    candidates.append((
                        violation_priority.get(kind, 9), rem,
                        "Hours of service violation: " + due + ". "
                        "Driving on risks fines at inspections."))
                continue
            crossed = [t for t in WARNING_THRESHOLDS_MIN
                       if rem <= t and f"{kind}:{t:.0f}" not in self.warned]
            if crossed:
                for t in crossed:
                    self.warned.append(f"{kind}:{t:.0f}")
                phrase = _THRESHOLD_PHRASES[min(crossed)]
                candidates.append((10, rem, f"Hours of service: {phrase} until {due}."))
        if not candidates:
            return []
        return [min(candidates, key=lambda item: (item[0], item[1]))[2]]

    def summary(self, mode: str) -> str:
        """Spoken status for the C key and Tab report."""
        if mode in HOS_NON_ENFORCED_MODES:
            return ("Hours of service enforcement is off; "
                    "the ELD clock still records time.")
        drive_limit, duty_limit, break_after = LIMITS[mode]
        drive_left = max(0.0, drive_limit - self.driving_min) / 60.0
        duty_left = max(0.0, duty_limit - self.duty_min) / 60.0
        break_left = max(0.0, break_after - self.since_break_min) / 60.0
        if self.in_violation(mode):
            violations = {kind for kind, rem, _ in self._statuses(mode) if rem <= 0}
            if violations == {"break"}:
                return ("Hours of service: you are past your break limit. "
                        "Take a 30-minute break at a rest stop.")
            return ("Hours of service: you are past your limit. "
                    "Sleep 10 hours at a rest stop to reset.")
        status = self.status.replace("_", " ")
        pending = self.split_pending_summary()
        suffix = f" {pending}" if pending else ""
        if duty_left <= break_left:
            return (f"ELD status {status}. Hours of service: "
                    f"{drive_left:.1f} hours of driving left, "
                    f"{duty_left:.1f} hours of duty window left{suffix}")
        return (f"ELD status {status}. Hours of service: "
                f"{drive_left:.1f} hours of driving left, "
                f"break due in {break_left:.1f} hours, "
                f"duty window closes in {duty_left:.1f} hours{suffix}")

    def split_pending_summary(self) -> str | None:
        credited = self._credited_split_pair()
        if credited is not None and credited[1] is self._split_rest_events()[-1]:
            return None
        pair = self._qualifying_split_pair()
        if pair is not None and self.split_credit_key == self._split_event_key(*pair):
            return None
        rest_events = self._split_rest_events()
        if not rest_events:
            return None
        last = rest_events[-1]
        if last.status == "sleeper_berth" and last.minutes >= SPLIT_LONG_ALT_MIN:
            return (
                "Sleeper split pending: pair this with 2 more hours at "
                "sleep-capable parking."
            )
        if last.status == "sleeper_berth" and last.minutes >= SPLIT_LONG_MIN:
            return (
                "Sleeper split pending: pair this with 3 more hours at "
                "sleep-capable parking."
            )
        if last.minutes >= SPLIT_SHORT_ALT_MIN:
            return "Sleeper split pending: pair this with 7 more hours in the sleeper berth."
        if last.minutes >= SPLIT_SHORT_MIN:
            return "Sleeper split pending: pair this with 8 more hours in the sleeper berth."
        return None

    # -- serialization -----------------------------------------------------------

    def to_dict(self) -> dict:
        return {"driving_min": self.driving_min, "duty_min": self.duty_min,
                "since_break_min": self.since_break_min,
                "status": self.status,
                "non_driving_min": self.non_driving_min,
                "off_duty_min": self.off_duty_min,
                "warned": list(self.warned),
                "history": [event.to_dict() for event in self.history],
                "split_rest_history": [
                    event.to_dict() for event in self.split_rest_history
                ],
                "split_credit_key": self.split_credit_key}

    @classmethod
    def from_dict(cls, data) -> HosClock:
        """Tolerant load: anything unreadable becomes a fresh clock."""
        if not isinstance(data, dict):
            return cls()
        try:
            status = str(data.get("status", "off_duty"))
            if status not in DUTY_STATUSES:
                status = "off_duty"
            history = []
            for raw_event in data.get("history", []):
                event = HosEvent.from_dict(raw_event)
                if event is not None:
                    history.append(event)
            split_rest_history = []
            raw_split_rest_history = data.get("split_rest_history")
            if isinstance(raw_split_rest_history, list):
                for raw_event in raw_split_rest_history:
                    event = HosEvent.from_dict(raw_event)
                    if event is not None:
                        split_rest_history.append(event)
            else:
                split_rest_history = [
                    event for event in history
                    if event.source == "normal"
                    and event.status in {"off_duty", "sleeper_berth"}
                    and event.minutes >= SPLIT_SHORT_MIN
                    and event.minutes < SLEEP_MIN
                ]
            return cls(
                driving_min=float(data.get("driving_min", 0.0)),
                duty_min=float(data.get("duty_min", 0.0)),
                since_break_min=float(data.get("since_break_min", 0.0)),
                status=status,
                non_driving_min=float(data.get("non_driving_min", 0.0)),
                off_duty_min=float(data.get("off_duty_min", 0.0)),
                warned=[str(w) for w in data.get("warned", [])],
                history=history[-HOS_HISTORY_MAX:],
                split_rest_history=split_rest_history[-HOS_SPLIT_REST_HISTORY_MAX:],
                split_credit_key=(
                    str(data["split_credit_key"])
                    if data.get("split_credit_key") is not None else None
                ),
            )
        except (TypeError, ValueError):
            return cls()


# ---------------------------------------------------------------------------
# Fatigue
# ---------------------------------------------------------------------------

FATIGUE_DROWSY = 60.0   # yawns and a spoken warning
FATIGUE_SEVERE = 80.0   # rumble strip drift, urgent warning

# Escalating fines for failed roadside inspections while over hours.
HOS_FINES = (200.0, 500.0, 1000.0, 2000.0)
HOS_REPUTATION_HIT = 3.0
FATIGUE_BREAK_RELIEF = 35.0
FATIGUE_SHOULDER_FLOOR = 30.0
# How long before a sleep/duty limit the shoulder-sleep option opens up, paired
# with a reachability check (no stop you can legally reach before the limit).
# A real driver starts hunting for parking a couple of hours out, not in the
# last half hour -- 30 min left you stranded with no action available.
SHOULDER_SLEEP_LIMIT_BUFFER_MIN = 120.0
SHOULDER_FINE_CHANCE = 0.15
SHOULDER_FINE = 150.0
SHOULDER_DAMAGE_CHANCE = 0.10
SHOULDER_DAMAGE_PCT = 3.0


def fatigue_rate_per_min(night: bool) -> float:
    """Fatigue points per game minute of continuous driving.

    About 8 daytime hours to the drowsy threshold; night driving gets
    there in under 6.
    """
    return 0.17 if night else 0.115


def reaction_window_mult(fatigue: float) -> float:
    """Scale factor for hazard reaction windows: 1.0 fresh, 0.6 exhausted."""
    if fatigue <= FATIGUE_DROWSY:
        return 1.0
    t = min(1.0, (fatigue - FATIGUE_DROWSY) / (100.0 - FATIGUE_DROWSY))
    return 1.0 - 0.4 * t


def rest_break(fatigue: float) -> float:
    """Fatigue after a 30-minute break."""
    return max(0.0, fatigue - FATIGUE_BREAK_RELIEF)


def rest_sleep(fatigue: float) -> float:
    """Fatigue after a proper 10-hour sleep."""
    return 0.0


def rest_shoulder(fatigue: float) -> float:
    """Shoulder parking is poor rest: fatigue never drops below 30."""
    return min(fatigue, FATIGUE_SHOULDER_FLOOR)


def rest_sleeper_split(fatigue: float, minutes: float, *, completed: bool = False) -> float:
    relief = 18.0 if minutes <= 180.0 else 55.0
    floor = 10.0 if completed else 20.0
    return max(floor, max(0.0, fatigue - relief))


# ---------------------------------------------------------------------------
# Day/night clock
# ---------------------------------------------------------------------------

DAWN_START, DAY_START, DUSK_START, NIGHT_START = 5.0, 7.0, 19.0, 21.0


def clock_hour(game_hours: float) -> float:
    return game_hours % 24.0


def time_of_day(game_hours: float) -> str:
    h = clock_hour(game_hours)
    if DAWN_START <= h < DAY_START:
        return "dawn"
    if DAY_START <= h < DUSK_START:
        return "day"
    if DUSK_START <= h < NIGHT_START:
        return "dusk"
    return "night"


def is_night(game_hours: float) -> bool:
    return time_of_day(game_hours) == "night"


def clock_text(game_hours: float) -> str:
    """Spoken 12-hour clock: '6 AM', '11:24 PM'."""
    h = clock_hour(game_hours)
    hour, minute = int(h), int(round((h - int(h)) * 60))
    if minute == 60:
        hour, minute = (hour + 1) % 24, 0
    ampm = "AM" if hour < 12 else "PM"
    h12 = hour % 12 or 12
    if minute == 0:
        return f"{h12} {ampm}"
    return f"{h12}:{minute:02d} {ampm}"


# ---------------------------------------------------------------------------
# Overnight truck parking
# ---------------------------------------------------------------------------

PARKING_CRUNCH_START, PARKING_CRUNCH_END = 20.0, 4.0  # 8 PM .. 4 AM


def parking_full_probability(game_hours: float) -> float:
    """Chance the lot is full, rising through the evening; 0 outside 8 PM-4 AM."""
    h = clock_hour(game_hours)
    if not (h >= PARKING_CRUNCH_START or h < PARKING_CRUNCH_END):
        return 0.0
    hours_past_8pm = (h - PARKING_CRUNCH_START) % 24.0
    return min(0.8, 0.2 + 0.1 * hours_past_8pm)


def parking_is_full(trip_seed: int, stop_mi: float, game_hours: float) -> bool:
    """Deterministic per trip seed and stop, so saves and tests reproduce it."""
    p = parking_full_probability(game_hours)
    if p <= 0.0:
        return False
    rng = random.Random(f"parking:{trip_seed}:{round(stop_mi * 10)}")
    return rng.random() < p


def shoulder_fine_due(trip_seed: int, stop_mi: float) -> bool:
    """Deterministic 15 percent chance of a fine for shoulder parking."""
    rng = random.Random(f"shoulder:{trip_seed}:{round(stop_mi * 10)}")
    return rng.random() < SHOULDER_FINE_CHANCE


def shoulder_damage_due(trip_seed: int, stop_mi: float) -> bool:
    """Deterministic small chance of minor damage while sleeping on the shoulder."""
    rng = random.Random(f"shoulder-damage:{trip_seed}:{round(stop_mi * 10)}")
    return rng.random() < SHOULDER_DAMAGE_CHANCE
