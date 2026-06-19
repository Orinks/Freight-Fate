"""Persistent player achievements and notification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models.profile import Profile


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    description: str
    category: str
    inspiration: str


@dataclass(frozen=True)
class AchievementAward:
    achievement: Achievement
    message: str


# Copy note: each badge has a specific inspiration, but player-facing text uses
# song-title-level allusions and broad themes only. Do not quote lyrics or
# recognizable lines, never reuse the exact artist or song title in the name or
# description, and do not show the source field in the in-game menu.
ACHIEVEMENTS: tuple[Achievement, ...] = (
    Achievement(
        "first_dispatch",
        "Breaker, Breaker",
        "You grabbed your first load off the board. No long line of trucks stacked up behind you yet, good buddy -- just a handle, a load number, and somewhere to be.",
        "Getting started",
        "C.W. McCall - Convoy",
    ),
    Achievement(
        "first_pickup",
        "Loaded and Rolling",
        "Cargo's aboard and the seal is set. Eighteen wheels don't roll on by themselves -- somebody had to back it into the dock and sign for it first.",
        "Getting started",
        "Alabama - Roll On (Eighteen Wheeler)",
    ),
    Achievement(
        "first_delivery",
        "Eastbound and Delivered",
        "Your first load is signed for and gone. Bandit-run theatrics optional -- the receiver got the freight and the paperwork held up clean.",
        "Deliveries",
        "Jerry Reed - East Bound and Down",
    ),
    Achievement(
        "first_on_time",
        "Beat the Clock, Fewer Days",
        "You hit the dock before the deadline. Didn't take most of a week behind the wheel to manage it, and dispatch only ever reads the timestamp anyway.",
        "Deliveries",
        "Dave Dudley - Six Days on the Road",
    ),
    Achievement(
        "clean_delivery",
        "Pretty as a Billboard",
        "You delivered with barely a scratch on the rig. The truck's still pretty enough to smile down from a billboard -- not one new dent stealing the look.",
        "Deliveries",
        "Del Reeves - Girl on the Billboard",
    ),
    Achievement(
        "speed_limit_saint",
        "Slow Rod Lincoln",
        "A whole run and not one speeding strike. The souped-up itch tapped the throttle once, then you sat it down to think hard about the insurance.",
        "Deliveries",
        "Commander Cody and His Lost Planet Airmen - Hot Rod Lincoln",
    ),
    Achievement(
        "five_deliveries",
        "Just Can't Wait to Roll",
        "Five career deliveries logged. That itch to get rolling down the highway again finally has a stat line that agrees with you.",
        "Career",
        "Willie Nelson - On the Road Again",
    ),
    Achievement(
        "ten_deliveries",
        "Ten Loads, Good Buddy",
        "Ten career deliveries in the books. That's a whole line of receipts now, ten-four, not just big talk crackling over the CB.",
        "Career",
        "C.W. McCall - Convoy",
    ),
    Achievement(
        "level_three",
        "Another Page, Another Town",
        "You reached career level 3. Here you are again, on stage in some new town -- except this chapter happens to pay better rates.",
        "Career",
        "Bob Seger - Turn the Page",
    ),
    Achievement(
        "twenty_five_grand",
        "Built It a Piece at a Time",
        "You've banked 25,000 dollars, stacked up load by load. Slower than sneaking a Cadillac out of the plant in your lunchbox, but a whole lot more legal.",
        "Career",
        "Johnny Cash - One Piece at a Time",
    ),
    Achievement(
        "thousand_miles",
        "Caught the White-Line Bug",
        "A thousand lifetime miles behind you. That white line gets in the blood like a fever, and the windshield's got the bug count to prove you've caught it.",
        "Career",
        "Merle Haggard - White Line Fever",
    ),
    Achievement(
        "long_haul",
        "Where the Ribbon Don't End",
        "One loaded haul over 900 miles. The blacktop unspooled ahead like a ribbon with no end in sight, long enough for the seat cushion to earn seniority.",
        "Routes",
        "Tiny Harris - Endless Black Ribbon",
    ),
    Achievement(
        "state_crossing",
        "Two Places, So Far",
        "You crossed your first state line with freight aboard. A long way from having been most everywhere, man, but the list officially has two names on it now.",
        "Routes",
        "Johnny Cash - I've Been Everywhere",
    ),
    Achievement(
        "multi_state",
        "Been Most Everywhere, Man",
        "One route, three states. Still working up to a list of towns long enough to rattle off in one breath, but the map had to stop and clear its throat.",
        "Routes",
        "Hank Snow / Johnny Cash - I've Been Everywhere",
    ),
    Achievement(
        "three_regions",
        "Three Regions and Ramblin'",
        "You've worked three freight regions now. Can't wait to get rolling out to the next one -- though dispatch still mispronounces wherever it turns out to be.",
        "Routes",
        "Willie Nelson - On the Road Again",
    ),
    Achievement(
        "toll_paid",
        "Bandit Pays the Toll",
        "You hit a toll and let the carrier eat it. Eastbound, westbound, loaded down -- one little beep at the booth, then accounting took the wheel.",
        "Routes",
        "Jerry Reed - East Bound and Down",
    ),
    Achievement(
        "no_toll_long",
        "Turns Out, an Easy Run",
        "Three hundred-plus loaded miles and not a single toll. They always swear no run comes easy -- this one clearly never got that memo.",
        "Routes",
        "Dave Dudley - There Ain't No Easy Run",
    ),
    Achievement(
        "rain_driver",
        "World Through a Wet Windshield",
        "You drove through the rain and kept it civil. The whole world goes by through that glass, with the wipers keeping time and your following distance keeping order.",
        "Weather",
        "Del Reeves - Looking at the World Through a Windshield",
    ),
    Achievement(
        "winter_or_wind",
        "Roll On Through the Snow",
        "Snow or crosswind, you kept the trailer in line and the wheels turning. Traction won the argument it always picks a fight over.",
        "Weather",
        "Alabama - Roll On (Eighteen Wheeler)",
    ),
    Achievement(
        "low_visibility",
        "Foggy Mountain Haul",
        "You ran through fog thick enough to bend a banjo string and never lost the road. Headlights, GPS, and brake distance picked up the tune.",
        "Weather",
        "Flatt & Scruggs - Foggy Mountain Breakdown",
    ),
    Achievement(
        "hazard_avoided",
        "Highway to Maybe Not",
        "You slowed in time to dodge a road hazard. Could've been a one-way ramp to somewhere awful -- your brake pedal had other plans.",
        "Road events",
        "AC/DC - Highway to Hell",
    ),
    Achievement(
        "construction_zone",
        "Honky-Tonk of Cones",
        "You crept through a construction zone like every cone had a lawyer on retainer. The swagger shrank down to posted speed, orange vests, and patient merging.",
        "Road events",
        "John Anderson - Honky Tonk Crowd",
    ),
    Achievement(
        "traffic_slowing",
        "Mind the Bumper Gap",
        "Heavy traffic, and you kept the bumper gap sane. No tangled-up mess for the whole CB channel to retell about you later, good buddy.",
        "Road events",
        "C.W. McCall - Convoy",
    ),
    Achievement(
        "inspection",
        "Smokey at the Scale",
        "You rolled through an inspection with the paperwork in order. All that radio mischief stayed outside while your axle weights behaved themselves indoors.",
        "Road events",
        "Rod Hart - C.B. Savage",
    ),
    Achievement(
        "first_rest_stop",
        "Sweetheart of the Truck Stop",
        "You pulled into a rest stop for the very first time. The romance lasted exactly as long as the vending machine took to size you up and judge.",
        "Rest and service",
        "The Willis Brothers - Truck Stop Cutie",
    ),
    Achievement(
        "route_refuel",
        "Filler-Up and Keep Truckin'",
        "You topped off the tank before it got dramatic. Filled 'er up at the old roadside cafe and kept right on truckin' down the line.",
        "Rest and service",
        "C.W. McCall - Old Home Filler-Up an' Keep On-a-Truckin' Cafe",
    ),
    Achievement(
        "break_taken",
        "Coffee Break, Driver",
        "You took your 30-minute break and let the clock breathe. One more cup of truck-stop coffee, and your knees filed a note of gratitude.",
        "Rest and service",
        "Buck Owens - Truck Drivin' Man",
    ),
    Achievement(
        "slept_on_route",
        "Five-by-Two and Out",
        "Ten hours in the bunk and you woke up legal. Unglamorous sleeper math -- and somehow the most heroic move on the whole board.",
        "Rest and service",
        "Red Simpson - Sleeper, Five-By-Two",
    ),
    Achievement(
        "sleep_before_exhaustion",
        "Mama Warned You About This",
        "You bunked down before the fatigue started steering. Somebody once warned you about staring down that centerline too long -- this time you listened.",
        "Rest and service",
        "Merle Haggard - Mama Tried",
    ),
    Achievement(
        "garage_repair",
        "Fixed It Piece by Piece",
        "You fixed the rig in a proper garage instead of cobbling it together from borrowed parts hauled out one at a time. Every receipt left with a clean conscience.",
        "Truck care",
        "Johnny Cash - One Piece at a Time",
    ),
    Achievement(
        "first_upgrade",
        "Soup It Up a Little",
        "Your first upgrade -- a small taste of souped-up confidence. The ghost in that old hopped-up Lincoln approved, then asked why the invoice was so reasonable.",
        "Truck care",
        "Commander Cody and His Lost Planet Airmen - Hot Rod Lincoln",
    ),
    Achievement(
        "heavy_hauler",
        "Eighteen Wheels and Then Some",
        "You bought the heavy hauler. The hills got a politely worded threat, and the fuel bill immediately demanded a speaking part of its own.",
        "Truck care",
        "Alabama - Roll On (Eighteen Wheeler)",
    ),
    Achievement(
        "air_ready",
        "Star of the Interstate",
        "You built up enough air to kick the brakes loose like a pro. The glory goes to the compressor today -- even the fastest thing on the interstate needs its PSI.",
        "Truck care",
        "Deep Purple - Highway Star",
    ),
    Achievement(
        "manual_driver",
        "Stick-Shift Solo",
        "You ran in manual and made the gearbox part of the band. Every clean shift sounds cool, right up until the grade changes key on you.",
        "Truck care",
        "Pete Drake - Gear Shiftin'",
    ),
)

ACHIEVEMENT_BY_ID = {achievement.id: achievement for achievement in ACHIEVEMENTS}


def earned_ids(profile: Profile) -> set[str]:
    return {str(value) for value in getattr(profile, "achievements", [])}


def award(profile: Profile, achievement_id: str) -> AchievementAward | None:
    achievement = ACHIEVEMENT_BY_ID[achievement_id]
    if achievement.id in earned_ids(profile):
        return None
    profile.achievements.append(achievement.id)
    message = f"New achievement! {achievement.name}. {achievement.description}"
    return AchievementAward(achievement, message)


def list_stat(profile: Profile, key: str) -> list[str]:
    stats = _stats(profile)
    raw = stats.get(key, [])
    if not isinstance(raw, list):
        raw = []
    values = [str(value) for value in raw]
    stats[key] = values
    return values


def add_unique_stat(profile: Profile, key: str, value: str) -> int:
    values = list_stat(profile, key)
    if value not in values:
        values.append(value)
    return len(values)


def bool_stat(profile: Profile, key: str) -> bool:
    return bool(_stats(profile).get(key, False))


def set_bool_stat(profile: Profile, key: str) -> None:
    _stats(profile)[key] = True


def _stats(profile: Profile) -> dict:
    stats = getattr(profile, "achievement_stats", None)
    if not isinstance(stats, dict):
        profile.achievement_stats = {}
        stats = profile.achievement_stats
    return stats
