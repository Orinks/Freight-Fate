"""Whether the officer at a post actually notices you, and what they noticed.

The old rule was one line: roll a number, compare it to the window's
intensity. That is a dice game, not a police force. It could only ever see
speed, it could not tell a crest from a straightaway or fog from a clear
night, and there was nothing a driver could *do* about it.

Observation here is a scored decision with five inputs a player can feel:

geometry      how close you are to the post relative to its method's reach
line of sight a crest or a hard bend between you and a lidar post blocks it;
              radar hardly cares
weather       fog and heavy rain gut lidar and eyesight; radar barely notices
traffic cover running in a pack at the pack's speed materially lowers the odds
              you are the one picked -- which is how real speed enforcement
              works, and is a genuine tactic
severity      five over is noticed and ignored; twenty over is a certainty at
              any post that can see you at all

And the thing observed is no longer only speed. A post using its eyes sees
visible damage, a truck with no chains inside an active control, an unlit
truck at night, a following distance nobody would defend, and lane misuse.
That is what makes the police feel like they are watching the road rather
than rolling dice on a speedometer.

Nothing here rolls a number. ``observe`` returns a confidence; the caller
makes the named, seeded, position-quantised draw against it, so the same
driving through the same road always produces the same outcome.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enforcement_posts import (
    METHOD_LIDAR,
    METHOD_PACING,
    METHOD_RADAR,
    METHOD_SCALE_SCREEN,
    METHOD_VISUAL,
    PACING_MIN_MI,
    EnforcementPost,
)

# Tolerance before a speed is a speed at all. Mirrors the ticketing leeway the
# driving layer has always used; ``driving_core.SPEEDING_LEEWAY_MPH`` is this
# constant, so the number lives in one place.
OBSERVE_LEEWAY_MPH = 9.0

# At or past this far over the limit, any post that can see you at all has
# you. No roll, no luck, no pack to hide in.
CERTAIN_OVER_MPH = 20.0

# Overage that reads as full severity short of the certainty line.
SEVERE_OVER_MPH = 18.0

# A confidence under this is a shrug: the officer clocked you and went back to
# their coffee. Returning None rather than a tiny number keeps "noticed and
# ignored" a real, testable state instead of a rare bad-luck ticket.
IGNORE_FLOOR = 0.06

# How far the truck must have travelled while over the limit before a post
# will read it as a speed rather than a blip. DISTANCE, not real seconds:
# a radar clocks you over a stretch of road, and a stretch of road is the same
# stretch at every pacing and every frame rate. Roughly four hundred feet.
OBSERVE_HOLD_MI = 0.08

# Traffic cover. Neighbours inside this distance, holding within this many mph
# of the truck, are a pack you are hiding in.
COVER_RADIUS_MI = 0.30
COVER_SPEED_TOLERANCE_MPH = 4.0
COVER_FACTOR = {0: 1.0, 1: 0.70}
COVER_FACTOR_PACK = 0.45  # two or more neighbours

# Line of sight. A crest or a hard bend between you and the post.
LOS_BLOCKED_FACTOR = {
    METHOD_LIDAR: 0.15,
    METHOD_VISUAL: 0.25,
    METHOD_RADAR: 0.85,
    METHOD_PACING: 0.9,
    METHOD_SCALE_SCREEN: 1.0,
}

# Visibility below this is genuinely obscuring; above it, clear enough.
CLEAR_VISIBILITY_MI = 3.0

# Damage the eye can see from the shoulder, and the point at which it is the
# only thing an officer is looking at.
DAMAGE_NOTICE_PCT = 45.0
DAMAGE_SEVERE_PCT = 80.0

# A following distance no officer would let pass, in seconds of gap.
TAILGATE_GAP_S = 1.2

WHAT_SPEEDING = "speeding"
WHAT_DAMAGE = "unsafe equipment"
WHAT_CHAINS = "no chains"
WHAT_LIGHTS = "no lights"
WHAT_FOLLOWING = "following too close"
WHAT_LANE = "lane misuse"


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class RoadSample:
    """Everything a post could possibly notice about the truck right now.

    Assembled by the driving layer from data that already exists. Optional
    fields default to the innocent reading, so a caller that cannot answer a
    question never accidentally accuses the driver.
    """

    position_mi: float
    speed_mph: float
    limit_mph: float
    damage_pct: float = 0.0
    visibility_mi: float = 10.0
    night: bool = False
    lights_on: bool = True
    chains_required: bool = False
    chains_on: bool = True
    following_gap_s: float | None = None
    left_lane_restricted: bool = False
    in_left_lane: bool = False
    # Neighbours inside COVER_RADIUS_MI holding within COVER_SPEED_TOLERANCE_MPH.
    pack_neighbours: int = 0
    # A crest or hard bend sits between the truck and the post.
    crest_between: bool = False
    # Road this post has been sitting behind the truck over (pacing only).
    # Miles rather than real seconds, for the same reason the over-limit hold
    # is: a stretch of road is the same stretch at every time compression, at
    # every frame rate, and after a reload.
    paced_mi: float = 0.0
    # How far the truck has run continuously over the limit.
    over_limit_mi: float = 0.0

    @property
    def mph_over(self) -> float:
        return max(0.0, self.speed_mph - self.limit_mph)


@dataclass(frozen=True)
class Observation:
    """One thing one post noticed, and how sure they are."""

    post: EnforcementPost
    confidence: float
    method: str
    what: str
    detail: str = ""

    @property
    def certain(self) -> bool:
        return self.confidence >= 1.0


def speeding_severity(mph_over: float) -> float:
    """0 where the overage is inside the leeway, 1 at a flagrant speed."""
    over = float(mph_over)
    if over <= OBSERVE_LEEWAY_MPH:
        return 0.0
    if over >= CERTAIN_OVER_MPH:
        return 1.0
    span = max(1e-6, SEVERE_OVER_MPH - OBSERVE_LEEWAY_MPH)
    return _clamp((over - OBSERVE_LEEWAY_MPH) / span)


def _candidates(post: EnforcementPost, sample: RoadSample) -> list[tuple[str, float, str]]:
    """(what, severity, detail) for everything this post could notice."""
    found: list[tuple[str, float, str]] = []
    speed_sev = speeding_severity(sample.mph_over)
    if speed_sev > 0.0 and sample.over_limit_mi >= OBSERVE_HOLD_MI:
        found.append((WHAT_SPEEDING, speed_sev, f"{sample.mph_over:.0f} over"))
    if post.method not in (METHOD_VISUAL, METHOD_SCALE_SCREEN):
        # Radar, lidar, and a pacing unit are looking at speed. Everything
        # below needs eyes on the truck.
        return found
    damage = float(sample.damage_pct)
    if damage >= DAMAGE_NOTICE_PCT:
        span = max(1e-6, DAMAGE_SEVERE_PCT - DAMAGE_NOTICE_PCT)
        found.append(
            (WHAT_DAMAGE, _clamp((damage - DAMAGE_NOTICE_PCT) / span), f"{damage:.0f} percent")
        )
    if sample.chains_required and not sample.chains_on:
        found.append((WHAT_CHAINS, 1.0, "chain control in force"))
    if sample.night and not sample.lights_on:
        found.append((WHAT_LIGHTS, 0.9, "running dark"))
    gap = sample.following_gap_s
    if gap is not None and 0.0 < gap < TAILGATE_GAP_S:
        found.append((WHAT_FOLLOWING, _clamp((TAILGATE_GAP_S - gap) / TAILGATE_GAP_S), "closed up"))
    if sample.left_lane_restricted and sample.in_left_lane:
        found.append((WHAT_LANE, 0.4, "left lane"))
    return found


def geometry_factor(post: EnforcementPost, sample: RoadSample) -> float:
    """How well the post's method reaches this piece of road.

    Full strength at the post, tailing off to half at the edge of its reach.
    Zero once the truck is past the post: an officer facing oncoming traffic
    does not clock the taillights going away, and a with-traffic post has
    already had its look.
    """
    ahead = post.at_mi - sample.position_mi
    if post.method == METHOD_PACING:
        # A pacing unit is behind you, so it works the other way round: it
        # needs to have been there long enough to hold a speed.
        if sample.paced_mi < PACING_MIN_MI:
            return 0.0
        return _clamp(0.5 + 0.5 * min(1.0, sample.paced_mi / (2.0 * PACING_MIN_MI)))
    if ahead < -0.3 or ahead > post.reach_mi:
        return 0.0
    closeness = 1.0 - _clamp(max(0.0, ahead) / max(1e-6, post.reach_mi))
    return 0.5 + 0.5 * closeness


def line_of_sight_factor(post: EnforcementPost, sample: RoadSample) -> float:
    if not sample.crest_between:
        return 1.0
    return LOS_BLOCKED_FACTOR.get(post.method, 0.5)


def weather_factor(post: EnforcementPost, sample: RoadSample) -> float:
    """Fog and heavy rain gut the optical methods and barely touch radar."""
    vis = max(0.0, float(sample.visibility_mi))
    clarity = _clamp(vis / CLEAR_VISIBILITY_MI)
    if post.method in (METHOD_LIDAR, METHOD_VISUAL):
        return _clamp(0.15 + 0.85 * clarity, 0.15, 1.0)
    if post.method == METHOD_SCALE_SCREEN:
        return 1.0  # the truck drives onto the scale; nobody is squinting
    return _clamp(0.9 + 0.1 * clarity, 0.9, 1.0)


def cover_factor(sample: RoadSample) -> float:
    """Running in a pack at the pack's speed is real cover, and a real tactic."""
    n = max(0, int(sample.pack_neighbours))
    return COVER_FACTOR.get(n, COVER_FACTOR_PACK)


def observe(post: EnforcementPost, sample: RoadSample) -> Observation | None:
    """What this post notices about the truck right now, and how sure it is.

    Returns ``None`` when there is nothing worth noticing, when the post is
    empty, when it cannot see this piece of road, when it has already had its
    look and let it go, or when the player was never told it was there. That
    last gate is an accessibility rule, not a balance one: a post the player
    had no cue for is not allowed to cost them anything.
    """
    if not post.staffed or post.declined or not post.announced:
        return None
    geometry = geometry_factor(post, sample)
    if geometry <= 0.0:
        return None
    candidates = _candidates(post, sample)
    if not candidates:
        return None
    los = line_of_sight_factor(post, sample)
    weather = weather_factor(post, sample)
    visibility_product = geometry * los * weather
    best: Observation | None = None
    for what, severity, detail in candidates:
        # Speed is the one thing a pack hides. Damage, chains, and lights are
        # visible on your truck whoever else is around.
        cover = cover_factor(sample) if what == WHAT_SPEEDING else 1.0
        confidence = severity * visibility_product * cover * post.notice
        if (
            what == WHAT_SPEEDING
            and sample.mph_over >= CERTAIN_OVER_MPH
            and visibility_product >= 0.2
        ):
            # Flagrant speed at a post that can see the road at all is not a
            # question. No pack, no weather, no luck.
            confidence = 1.0
        confidence = _clamp(confidence)
        if confidence < IGNORE_FLOOR:
            continue
        if best is None or confidence > best.confidence:
            best = Observation(post, confidence, post.method, what, detail)
    return best


__all__ = [
    "CERTAIN_OVER_MPH",
    "COVER_RADIUS_MI",
    "COVER_SPEED_TOLERANCE_MPH",
    "DAMAGE_NOTICE_PCT",
    "IGNORE_FLOOR",
    "OBSERVE_HOLD_MI",
    "OBSERVE_LEEWAY_MPH",
    "Observation",
    "RoadSample",
    "TAILGATE_GAP_S",
    "WHAT_CHAINS",
    "WHAT_DAMAGE",
    "WHAT_FOLLOWING",
    "WHAT_LANE",
    "WHAT_LIGHTS",
    "WHAT_SPEEDING",
    "cover_factor",
    "geometry_factor",
    "line_of_sight_factor",
    "observe",
    "speeding_severity",
    "weather_factor",
]
