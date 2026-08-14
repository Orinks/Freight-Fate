"""Enforcement posts: the places on a corridor where an officer may be sitting.

The old model was a *window* -- a few miles of road with a probability
attached, and a coin flip the moment you sped inside it. It produced a country
with no police in it: five windows on a six-hundred-mile run covered under five
percent of the route, a run shorter than a hundred and twenty miles carried
none at all, and a driver who never sped never once heard a trooper.

A post is a PLACE WITH A BODY. It sits at a milepost, not across a span. It
observes up-corridor as far as its method reaches. Whether anyone is sitting
there today is settled once, when the trip is built, from the trip seed -- most
posts are empty most of the time, which is what makes the staffed ones matter.
Whether that body notices *you* is a separate, graded decision made in
``enforcement_observe``: geometry, line of sight, weather, traffic cover, and
how badly you are actually driving.

Every kind is anchored to data the world already carries. Nothing here invents
a new world-data field:

``median_post``      interstate median crossovers, spaced off ``leg.interchanges``
``roving_patrol``    a unit moving with traffic; the trooper NPC is its body
``work_zone_post``   a ``Zone(reason="construction")``
``scale_apron_post`` a ``weigh_station`` stop that is closed today
``fixed_scale``      the same ``weigh_station`` stop when it is open
``urban_unit``       the urban radius that already lowers the limit near a city
``cmv_unit``         commercial-vehicle enforcement; scales and truck corridors
``chain_control``    an entry in ``chain_law_areas``

Presence is not difficulty. Placement and staffing read nothing from the
enforcement-presence setting and nothing from ``hazard_scale``: the road has
the police it has. The presence setting governs how much ambient enforcement
audio the player hears, and never how likely they are to be pulled over
(see ``settings.enforcement_presence``).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .season import day_of_week
from .trip_models import (
    _COLD_PATROL_REGIONS,
    _HOT_PATROL_REGIONS,
    URBAN_RADIUS_MI,
    _highway_class,
)

# -- methods ----------------------------------------------------------------

# How a post observes. Each answers distance, line of sight, and weather
# differently, which is the whole reason the player can have tactics.
METHOD_RADAR = "radar"  # long reach, weather-tolerant, geometry-tolerant
METHOD_LIDAR = "lidar"  # short, needs a clear line, dies in fog
METHOD_PACING = "pacing"  # a unit that falls in behind you and clocks you
METHOD_VISUAL = "visual"  # eyes: damage, chains, lights, following distance
METHOD_SCALE_SCREEN = "scale_screen"  # the scale's own screening lane

# Reach up-corridor, in miles, by method. Radar down an interstate really does
# read a mile out; a lidar operator needs about half that and a clear line; an
# officer using their eyes has a couple of tenths.
METHOD_REACH_MI = {
    METHOD_RADAR: 1.0,
    METHOD_LIDAR: 0.5,
    METHOD_PACING: 0.6,
    METHOD_VISUAL: 0.2,
    METHOD_SCALE_SCREEN: 0.5,
}

# A unit that paces you has to be behind you long enough to hold a speed. Real
# seconds, not compressed ones: the officer's stopwatch runs on the same clock
# the player's does.
PACING_MIN_REAL_S = 20.0

# -- kinds ------------------------------------------------------------------

KIND_MEDIAN = "median_post"
KIND_ROVING = "roving_patrol"
KIND_WORK_ZONE = "work_zone_post"
KIND_SCALE_APRON = "scale_apron_post"
KIND_FIXED_SCALE = "fixed_scale"
KIND_URBAN = "urban_unit"
KIND_CMV = "cmv_unit"
KIND_CHAIN = "chain_control"

POST_KINDS = (
    KIND_MEDIAN,
    KIND_ROVING,
    KIND_WORK_ZONE,
    KIND_SCALE_APRON,
    KIND_FIXED_SCALE,
    KIND_URBAN,
    KIND_CMV,
    KIND_CHAIN,
)

# Only a commercial-vehicle unit and an open scale run a full equipment
# inspection. A trooper on a median crossover writes tickets.
INSPECTING_KINDS = frozenset({KIND_CMV, KIND_FIXED_SCALE})

# -- tableau: a post already working somebody else ---------------------------

# Only a patrol kind ever runs a tableau: a trooper on a crossover, a roving
# unit, or a city unit can be caught with a customer already pulled over. A
# work zone detail, a scale, a CMV unit and a chain checkpoint work from a
# fixed spot with no roving "somebody else" to be caught with.
TABLEAU_KINDS = frozenset({KIND_MEDIAN, KIND_ROVING, KIND_URBAN})

# Chance a staffed patrol-kind post is already working a stop, independent of
# whether the driver ever speeds near it. Loosely calibrated against how many
# patrol-kind posts a route already carries (BASE_STAFFED x the spacing
# tables): converting roughly half of them keeps a tableau to about one every
# hour or so of driving on a patrol-covered interstate -- rare enough to stay
# an event, not wallpaper.
TABLEAU_CHANCE = 0.55

# How far before the post the siren becomes audible, and how far this post's
# own catches start being suppressed. The same distance on purpose: the
# player is told the trooper is occupied at exactly the point it stops being
# able to catch them.
TABLEAU_SIREN_LEAD_MI = 1.5
# How far past the post the trooper stays occupied with their stop. A real
# traffic stop runs several minutes, which is more road than it looks like at
# highway speed.
TABLEAU_BUSY_PAST_MI = 2.0

METHOD_BY_KIND = {
    KIND_MEDIAN: METHOD_RADAR,
    KIND_ROVING: METHOD_PACING,
    KIND_WORK_ZONE: METHOD_VISUAL,
    KIND_SCALE_APRON: METHOD_RADAR,
    KIND_FIXED_SCALE: METHOD_SCALE_SCREEN,
    KIND_URBAN: METHOD_LIDAR,
    KIND_CMV: METHOD_VISUAL,
    KIND_CHAIN: METHOD_VISUAL,
}

# Which way the post looks. "oncoming" is the median crossover watching the
# other roadway; "both" is a crossover working either direction. Only a post
# that can look at your side of the road can ever observe you, and only a post
# that faces oncoming produces the marked-unit pass earcon.
FACING_BY_KIND = {
    KIND_MEDIAN: "both",
    KIND_ROVING: "with_traffic",
    KIND_WORK_ZONE: "with_traffic",
    KIND_SCALE_APRON: "both",
    KIND_FIXED_SCALE: "with_traffic",
    KIND_URBAN: "with_traffic",
    KIND_CMV: "with_traffic",
    KIND_CHAIN: "with_traffic",
}

AGENCY_BY_KIND = {
    KIND_MEDIAN: "state police",
    KIND_ROVING: "state police",
    KIND_WORK_ZONE: "state police",
    KIND_SCALE_APRON: "state police",
    KIND_FIXED_SCALE: "commercial vehicle enforcement",
    KIND_URBAN: "city police",
    KIND_CMV: "commercial vehicle enforcement",
    KIND_CHAIN: "state police",
}

# The internal context label the existing spoken lines interpolate as
# "a trooper on this {reason}". Kept short and non-jargon.
REASON_BY_KIND = {
    KIND_MEDIAN: "highway enforcement",
    KIND_ROVING: "highway enforcement",
    KIND_WORK_ZONE: "work zone enforcement",
    KIND_SCALE_APRON: "scale apron",
    KIND_FIXED_SCALE: "weigh station",
    KIND_URBAN: "city enforcement",
    KIND_CMV: "commercial vehicle enforcement",
    KIND_CHAIN: "chain control",
}

# Base chance a post has a body in it today, before region, road class, hour,
# and day of week. Most posts are empty most of the time; a work zone with an
# officer detail is the near-certainty it has always been, and an open scale is
# staffed by definition.
BASE_STAFFED = {
    KIND_MEDIAN: 0.24,
    KIND_ROVING: 0.34,
    KIND_WORK_ZONE: 0.90,
    KIND_SCALE_APRON: 0.35,
    KIND_FIXED_SCALE: 1.0,
    KIND_URBAN: 0.22,
    KIND_CMV: 0.22,
    KIND_CHAIN: 0.50,
}

# How willing this kind of post is to act at all, before severity. A scale
# screening lane looks at every truck; a city unit on a call has other things
# to do.
BASE_NOTICE = {
    KIND_MEDIAN: 0.9,
    KIND_ROVING: 0.85,
    KIND_WORK_ZONE: 0.95,
    KIND_SCALE_APRON: 0.9,
    KIND_FIXED_SCALE: 1.0,
    KIND_URBAN: 0.7,
    KIND_CMV: 0.95,
    KIND_CHAIN: 0.9,
}

# -- spacing ----------------------------------------------------------------

# Target miles between posts of each spaced kind, on an interstate at the
# neutral regional baseline. Region, road class, and the clock stretch or
# compress these.
#
# Region and road class reach SPACING ONLY, never staffing. Applying them to
# both squared the effect: a hot-region interstate came out with 3.4 times the
# police contacts of a cold-region one, not the 1.9 the tables describe, and a
# five-hundred-mile California run overshot the presence target by half.
SPACING_MI = {
    KIND_MEDIAN: 40.0,
    KIND_ROVING: 80.0,
    KIND_CMV: 170.0,
}

# Road class scales spacing: an interstate carries the most enforcement per
# mile, a two-lane state route the least.
CLASS_SPACING_MULT = {"interstate": 1.0, "us_highway": 1.5, "state_route": 2.4}

# Region density, reusing the tables the old model already used.
HOT_REGION_MULT = 1.3
COLD_REGION_MULT = 0.7

# Thin between 2 and 5 in the morning, thick through both commuter peaks.
QUIET_HOURS = (2.0, 5.0)
BUSY_HOURS = ((6.0, 9.0), (15.0, 18.0))
QUIET_HOUR_MULT = 0.55
BUSY_HOUR_MULT = 1.15

# Fixed scales are largely closed at the weekend. This is the openness roll,
# not a staffing roll: a closed scale can still carry an apron post.
SCALE_OPEN_WEEKDAY = 0.45
SCALE_OPEN_WEEKEND = 0.12

# A post the player can never reach in time to react to is not fair, so no
# post is placed inside the first or last stretch of the run.
EDGE_MARGIN_MI = 3.0

# The route mile a post's body actually sits at, relative to the feature that
# anchors it: a work-zone detail parks just inside the cones, a scale apron
# post sits at the scale.
WORK_ZONE_POST_OFFSET_MI = 0.4


def region_multiplier(region: str) -> float:
    if region in _HOT_PATROL_REGIONS:
        return HOT_REGION_MULT
    if region in _COLD_PATROL_REGIONS:
        return COLD_REGION_MULT
    return 1.0


def hour_multiplier(hour: float) -> float:
    """Time-of-day density. Thin in the small hours, thick at the peaks."""
    h = float(hour) % 24.0
    if QUIET_HOURS[0] <= h < QUIET_HOURS[1]:
        return QUIET_HOUR_MULT
    for start, end in BUSY_HOURS:
        if start <= h < end:
            return BUSY_HOUR_MULT
    return 1.0


def scale_open_chance(career_hours: float | None) -> float:
    """Odds a fixed scale is open. Weekends are mostly dark."""
    if career_hours is None:
        return SCALE_OPEN_WEEKDAY  # unknown day reads as a weekday, the busier case
    return SCALE_OPEN_WEEKEND if day_of_week(career_hours) >= 5 else SCALE_OPEN_WEEKDAY


def post_seed(trip_seed: int | None, post_id: str, purpose: str) -> str:
    """The named, seeded draw key for one police decision.

    Every police decision in the game is one of these. Never time-quantised:
    a reload, a frame-rate change, or a different pacing must reproduce the
    same road.
    """
    return f"{trip_seed}:police:{post_id}:{purpose}"


@dataclass
class EnforcementPost:
    """One place on the corridor where an officer may be sitting.

    ``at_mi`` is a point, not a span. ``reach_mi`` is how far up-corridor the
    post's method can observe -- so the stretch of road it covers is
    ``[at_mi - reach_mi, at_mi]`` for traffic coming toward it.
    """

    at_mi: float
    kind: str
    leg_index: int = 0
    method: str = METHOD_RADAR
    reach_mi: float = 1.0
    facing: str = "with_traffic"
    staffed: bool = False
    agency: str = "state police"
    # Slug of the anchoring world feature, when there is one: the scale's
    # stop key, the zone's reason, the city name. Never spoken; it exists so
    # a post can be traced back to the data that put it there.
    anchor: str = ""
    # Region/class/hour density that produced this post, kept for the status
    # readout and for tests that assert hot regions run hotter than cold ones.
    density: float = 1.0
    notice: float = 0.9
    # Set by the trip once the player has heard this post announced. A post
    # cannot observe a driver who was never told it was there.
    announced: bool = field(default=False, compare=False)
    # A post that has already looked at you and let it go does not re-decide.
    declined: bool = field(default=False, compare=False)
    # Whether this staffed patrol post already has somebody stopped. Settled
    # once at trip build, from the trip seed, the same way ``staffed`` is.
    tableau: bool = field(default=False, compare=False)

    @property
    def id(self) -> str:
        return f"post:{self.leg_index}:{self.at_mi:.1f}:{self.kind}"

    @property
    def reason(self) -> str:
        """Short internal context label, interpolated into spoken lines."""
        return REASON_BY_KIND.get(self.kind, "highway enforcement")

    @property
    def is_scale(self) -> bool:
        return self.kind in (KIND_FIXED_SCALE, KIND_SCALE_APRON)

    @property
    def inspects(self) -> bool:
        """Whether this post runs a full equipment inspection, not just a ticket."""
        return self.kind in INSPECTING_KINDS

    @property
    def watch_start_mi(self) -> float:
        """First mile at which this post can see traffic coming toward it."""
        return max(0.0, self.at_mi - self.reach_mi)

    # -- legacy read surface -------------------------------------------------
    # The info key, the traffic bubble, and the road-ahead readout all still
    # ask a post where it starts and ends. A point post answers with the
    # stretch it watches rather than pretending to be a window again.

    @property
    def start_mi(self) -> float:
        return self.watch_start_mi

    @property
    def end_mi(self) -> float:
        return self.at_mi + 0.3

    def covers(self, mile: float) -> bool:
        return self.watch_start_mi <= mile <= self.end_mi

    def distance_from(self, mile: float) -> float:
        """Miles from ``mile`` up to the post; negative once it is behind you."""
        return self.at_mi - mile

    def tableau_busy_at(self, mile: float) -> bool:
        """Whether this post's trooper is occupied with somebody else here.

        From the siren lead to a couple of miles past the stop: a bear with a
        customer is off the hunt, real CB wisdom, now mechanically true. Only
        this post's own catches are affected -- every other post on the
        route keeps watching normally.
        """
        if not self.tableau:
            return False
        return self.at_mi - TABLEAU_SIREN_LEAD_MI <= mile <= self.at_mi + TABLEAU_BUSY_PAST_MI


def build_post(
    *,
    at_mi: float,
    kind: str,
    leg_index: int,
    trip_seed: int | None,
    density: float,
    anchor: str = "",
    staffed: bool | None = None,
    staffing: float = 1.0,
) -> EnforcementPost:
    """One post, with its staffing settled from the trip seed.

    ``staffed=None`` rolls it; an explicit value is for the kinds whose
    staffing is a fact rather than a chance (an open scale is staffed).
    ``staffing`` carries only the clock: how busy a shift is, not how dense
    the region is -- density is already spent on where the posts are.
    """
    method = METHOD_BY_KIND[kind]
    post = EnforcementPost(
        at_mi=round(float(at_mi), 3),
        kind=kind,
        leg_index=leg_index,
        method=method,
        reach_mi=METHOD_REACH_MI[method],
        facing=FACING_BY_KIND[kind],
        agency=AGENCY_BY_KIND[kind],
        anchor=anchor,
        density=density,
        notice=BASE_NOTICE[kind],
    )
    if staffed is None:
        chance = min(0.97, BASE_STAFFED[kind] * max(0.1, staffing))
        rolled = random.Random(post_seed(trip_seed, post.id, "staffed")).random()
        post.staffed = rolled < chance
    else:
        post.staffed = bool(staffed)
    return post


def assign_tableau(post: EnforcementPost, trip_seed: int | None) -> bool:
    """Whether ``post`` already has somebody stopped, on this trip's seed.

    Only a staffed patrol-kind post is ever eligible: a post nobody is
    sitting in has nothing to be busy with, and a fixed spot (a scale, a work
    zone, a CMV unit, a chain control) has no roving "somebody else" to catch.
    """
    if post.kind not in TABLEAU_KINDS or not post.staffed:
        return False
    roll = random.Random(post_seed(trip_seed, post.id, "tableau")).random()
    return roll < TABLEAU_CHANCE


class EnforcementPostMixin:
    """Trip-side placement and lookup for enforcement posts.

    Mixed into :class:`~freight_fate.sim.trip.Trip`, which supplies
    ``route``, ``_leg_starts``, ``_region_at``, ``_leg_at_mile``, ``zones``,
    ``stops``, ``chain_law_areas``, ``_city_mileposts`` and the trip seed.
    """

    # -- placement -----------------------------------------------------------

    def _post_density_at(self, mile: float) -> float:
        leg_i, _ = self._leg_at_mile(mile)
        cls = _highway_class(self.route.legs[leg_i].highway)
        density = 1.0 / CLASS_SPACING_MULT.get(cls, CLASS_SPACING_MULT["state_route"])
        density *= region_multiplier(self._region_at(mile))
        density *= hour_multiplier(self.local_start_hour)
        return density

    def _spaced_posts(self, kind: str) -> list[EnforcementPost]:
        """Posts of a spaced kind laid down along the whole route.

        The step is the kind's target spacing divided by the local density, so
        an interstate through a hot region carries them close together and a
        two-lane out on the plains carries them far apart -- from the same
        walk, with no extra random draw.
        """
        total = self.route.miles
        posts: list[EnforcementPost] = []
        mile = EDGE_MARGIN_MI
        guard = 0
        while mile <= total - EDGE_MARGIN_MI and guard < 4000:
            guard += 1
            density = self._post_density_at(mile)
            step = SPACING_MI[kind] / max(0.2, density)
            leg_i, _ = self._leg_at_mile(mile)
            at = mile
            anchor = ""
            if kind == KIND_MEDIAN:
                # A crossover is a piece of interstate infrastructure, so the
                # post lands on the nearest interchange rather than a bare
                # milepost. Falls back to the walk position where the leg
                # carries no interchange bake.
                snapped = self._nearest_interchange_mile(mile, within_mi=step * 0.5)
                if snapped is not None:
                    at, anchor = snapped
            posts.append(
                build_post(
                    at_mi=at,
                    kind=kind,
                    leg_index=leg_i,
                    trip_seed=self._seed,
                    density=density,
                    staffing=hour_multiplier(self.local_start_hour),
                    anchor=anchor,
                )
            )
            mile += step
        return posts

    def _nearest_interchange_mile(
        self, mile: float, *, within_mi: float
    ) -> tuple[float, str] | None:
        """Route mile and exit label of the interchange nearest ``mile``."""
        from .trip_route_helpers import _stop_offset_for_direction

        best: tuple[float, str] | None = None
        best_d = within_mi
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            forward = self.route.cities[i] == leg.a
            for ix in leg.interchanges:
                offset = _stop_offset_for_direction(ix.at_mi, leg.miles, forward)
                route_mi = start + offset
                d = abs(route_mi - mile)
                if d <= best_d:
                    best_d = d
                    best = (route_mi, str(getattr(ix, "exit_ref", "") or ""))
        return best

    def _place_enforcement_posts(self) -> list[EnforcementPost]:
        """Every post on this route, sorted up-corridor.

        Deliberately reads neither ``hazard_scale`` nor the enforcement
        presence setting. The world has the police it has; the presence
        setting decides how much of it the player hears, and the difficulty
        mode decides what a citation costs.
        """
        if (
            getattr(self, "_is_facility_approach_route", None)
            and self._is_facility_approach_route()
        ):
            return []
        posts: list[EnforcementPost] = []
        for kind in (KIND_MEDIAN, KIND_ROVING, KIND_CMV):
            posts.extend(self._spaced_posts(kind))
        posts.extend(self._work_zone_posts())
        posts.extend(self._scale_posts())
        posts.extend(self._urban_posts())
        posts.extend(self._chain_posts())
        posts.sort(key=lambda p: p.at_mi)
        for post in posts:
            post.tableau = assign_tableau(post, self._seed)
        return posts

    def _work_zone_posts(self) -> list[EnforcementPost]:
        posts: list[EnforcementPost] = []
        for zone in self.zones:
            if zone.reason != "construction":
                continue
            at = min(zone.end_mi, zone.start_mi + WORK_ZONE_POST_OFFSET_MI)
            leg_i, _ = self._leg_at_mile(at)
            post = build_post(
                at_mi=at,
                kind=KIND_WORK_ZONE,
                leg_index=leg_i,
                trip_seed=self._seed,
                density=self._post_density_at(at),
                staffing=hour_multiplier(self.local_start_hour),
                anchor=f"zone:{zone.start_mi:.1f}",
            )
            # A detail watches the whole coned stretch, not two tenths of it.
            post.reach_mi = max(post.reach_mi, min(3.0, zone.end_mi - zone.start_mi))
            posts.append(post)
        return posts

    def _scale_posts(self) -> list[EnforcementPost]:
        """Open scales and the closed scales that still carry an apron post.

        The world just gained eighty-seven surveyed scales across thirty-two
        states. A trooper parked on a dark scale apron is one of the most
        common real sightings there is, so a closed scale is not an empty
        milepost -- it is a coin flip the driver cannot call.
        """
        posts: list[EnforcementPost] = []
        open_chance = scale_open_chance(self.career_hours)
        for stop in self.stops:
            if stop.type != "weigh_station":
                continue
            leg_i, _ = self._leg_at_mile(stop.at_mi)
            density = self._post_density_at(stop.at_mi)
            scale_id = f"post:{leg_i}:{stop.at_mi:.1f}:{KIND_FIXED_SCALE}"
            is_open = (
                random.Random(post_seed(self._seed, scale_id, f"scale:{stop.key}:open")).random()
                < open_chance
            )
            if is_open:
                posts.append(
                    build_post(
                        at_mi=stop.at_mi,
                        kind=KIND_FIXED_SCALE,
                        leg_index=leg_i,
                        trip_seed=self._seed,
                        density=density,
                        anchor=stop.key,
                        staffed=True,
                    )
                )
            else:
                posts.append(
                    build_post(
                        at_mi=stop.at_mi,
                        kind=KIND_SCALE_APRON,
                        leg_index=leg_i,
                        trip_seed=self._seed,
                        density=density,
                        anchor=stop.key,
                    )
                )
        return posts

    def _urban_posts(self) -> list[EnforcementPost]:
        """One unit per route city, on the urban radius that already exists."""
        posts: list[EnforcementPost] = []
        total = self.route.miles
        for i, milepost in enumerate(self._city_mileposts):
            at = milepost - URBAN_RADIUS_MI * 0.5
            if not (EDGE_MARGIN_MI <= at <= total - EDGE_MARGIN_MI):
                continue
            leg_i, _ = self._leg_at_mile(at)
            city = self.route.cities[min(i, len(self.route.cities) - 1)]
            posts.append(
                build_post(
                    at_mi=at,
                    kind=KIND_URBAN,
                    leg_index=leg_i,
                    trip_seed=self._seed,
                    density=self._post_density_at(at),
                    staffing=hour_multiplier(self.local_start_hour),
                    anchor=city,
                )
            )
        return posts

    def _chain_posts(self) -> list[EnforcementPost]:
        posts: list[EnforcementPost] = []
        for start, _end in self.chain_law_areas:
            leg_i, _ = self._leg_at_mile(start)
            posts.append(
                build_post(
                    at_mi=start,
                    kind=KIND_CHAIN,
                    leg_index=leg_i,
                    trip_seed=self._seed,
                    density=self._post_density_at(start),
                    staffing=hour_multiplier(self.local_start_hour),
                    anchor=f"chain:{start:.1f}",
                )
            )
        return posts

    # -- lookup --------------------------------------------------------------

    def active_post_at(self, mile: float) -> EnforcementPost | None:
        """The staffed post watching this mile, most attentive first."""
        watching = [p for p in self.posts if p.staffed and p.covers(mile)]
        if not watching:
            return None
        return max(watching, key=lambda p: (p.notice * p.density, BASE_NOTICE.get(p.kind, 0.0)))

    def posts_watching(self, mile: float) -> list[EnforcementPost]:
        """Staffed posts that could still catch a driver at this mile.

        A post running a tableau is dropped for the duration of its busy
        window -- its trooper is occupied with somebody else, so it makes no
        catch contribution here. Every other post is unaffected.
        """
        return [
            p for p in self.posts if p.staffed and p.covers(mile) and not p.tableau_busy_at(mile)
        ]

    def next_post_within(self, within_mi: float) -> EnforcementPost | None:
        """Nearest post at or ahead of the truck inside the lookahead."""
        candidates = [
            p
            for p in self.posts
            if p.end_mi >= self.position_mi and p.at_mi - self.position_mi <= within_mi
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda p: max(0.0, p.at_mi - self.position_mi))

    def audible_enforcement_contacts(self) -> list[EnforcementPost]:
        """Posts on this route the player will hear something from.

        Every staffed post announces itself, and every scale -- open or closed
        -- swells its approach ambience. An empty median crossover makes no
        sound, because there is nothing there to make one. This is the list
        the presence targets are calibrated against.
        """
        return [p for p in self.posts if p.staffed or p.is_scale]


__all__ = [
    "AGENCY_BY_KIND",
    "BASE_NOTICE",
    "BASE_STAFFED",
    "EDGE_MARGIN_MI",
    "EnforcementPost",
    "EnforcementPostMixin",
    "FACING_BY_KIND",
    "INSPECTING_KINDS",
    "KIND_CHAIN",
    "KIND_CMV",
    "KIND_FIXED_SCALE",
    "KIND_MEDIAN",
    "KIND_ROVING",
    "KIND_SCALE_APRON",
    "KIND_URBAN",
    "KIND_WORK_ZONE",
    "METHOD_BY_KIND",
    "METHOD_LIDAR",
    "METHOD_PACING",
    "METHOD_RADAR",
    "METHOD_REACH_MI",
    "METHOD_SCALE_SCREEN",
    "METHOD_VISUAL",
    "PACING_MIN_REAL_S",
    "POST_KINDS",
    "REASON_BY_KIND",
    "SPACING_MI",
    "TABLEAU_BUSY_PAST_MI",
    "TABLEAU_CHANCE",
    "TABLEAU_KINDS",
    "TABLEAU_SIREN_LEAD_MI",
    "assign_tableau",
    "build_post",
    "hour_multiplier",
    "post_seed",
    "region_multiplier",
    "scale_open_chance",
]
