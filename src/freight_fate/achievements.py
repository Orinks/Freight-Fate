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
        "Signed, Sealed, Hauled",
        "Your very first load is signed for and gone. No fanfare needed -- the receiver got the freight and the paperwork held up clean.",
        "Deliveries",
        "Dave Dudley - Truck Drivin' Son-of-a-Gun",
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
        "What a Long, Strange Haul",
        "Ten career deliveries in the books. It has been a long, strange stretch of road to get here, and the receipts are piling up faster than the war stories.",
        "Career",
        "Grateful Dead - Truckin'",
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
        "Kept It Between the Lines",
        "You crossed your first state line with freight aboard. One side to the other, you kept the rig between the lines and the load rode clean across the border.",
        "Routes",
        "Johnny Cash - I Walk the Line",
    ),
    Achievement(
        "multi_state",
        "Been Most Everywhere, Man",
        "One route, three states. Still working up to a list of towns long enough to rattle off in one breath, but the map had to stop and clear its throat.",
        "Routes",
        "Hank Snow - I've Been Everywhere",
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
        "A Mile Past the Last Marker",
        "Snow or crosswind, you kept the trailer in line and the wheels turning. The kind of grim stretch that earns roadside markers stayed in your mirror, not the headlines.",
        "Weather",
        "Dick Curless - A Tombstone Every Mile",
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
        "Bumper-to-Bumper Blues",
        "Heavy traffic, and you kept the following distance sane. The road runs long and life moves fast on it, so you let the jam breathe instead of tailgating into a mess.",
        "Road events",
        "Tom Cochrane - Life Is a Highway",
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
        "A Working Man's Receipt",
        "You fixed the rig in a proper garage instead of cobbling it together from borrowed parts. Honest work and an honest bill, and the truck rolled out earning its keep again.",
        "Truck care",
        "Merle Haggard - Workin' Man Blues",
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
    # -- Landmarks: direction, famous corridors, and city-arrival badges ------
    Achievement(
        "eastbound_delivery",
        "Eastbound and Gone",
        "You ran a load net eastbound and put it on the dock. East is east, the hammer was down, and the receiver never had to wait on you.",
        "Landmarks",
        "Jerry Reed - East Bound and Down",
    ),
    Achievement(
        "westbound_delivery",
        "Westbound, Foot Down",
        "A load delivered headed the other way. Westbound and willing, you drank the weak coffee, pushed the sun down ahead of you, and put it on the dock.",
        "Landmarks",
        "Little Feat - Willin'",
    ),
    Achievement(
        "route66_run",
        "The Mother Road",
        "You hauled between two towns strung along the old Mother Road. The neon's faded, but the asphalt still gets its kicks under your tires.",
        "Landmarks",
        "Bobby Troup - (Get Your Kicks on) Route 66",
    ),
    Achievement(
        "amarillo_arrival",
        "Amarillo by Daybreak",
        "Backed into the dock in Amarillo. You weren't quite riding in on a pony, but the Panhandle wind made up the difference.",
        "Landmarks",
        "George Strait - Amarillo by Morning",
    ),
    Achievement(
        "phoenix_arrival",
        "Clear to Phoenix",
        "Freight delivered in Phoenix. By the time you rolled in, the desert had stopped pretending it was ever going to cool off.",
        "Landmarks",
        "Glen Campbell - By the Time I Get to Phoenix",
    ),
    Achievement(
        "wichita_arrival",
        "Wichita on the Line",
        "A load signed for in Wichita. Somewhere out on the plains a lineman waved; you were too busy watching the wind push the trailer.",
        "Landmarks",
        "Glen Campbell - Wichita Lineman",
    ),
    Achievement(
        "lubbock_arrival",
        "Lubbock in the Rearview",
        "Backed into the dock in Lubbock, out on the high plains. They say happiness is a hometown shrinking in the rearview mirror -- but tonight the freight came first.",
        "Landmarks",
        "Mac Davis - Texas in My Rear View Mirror",
    ),
    Achievement(
        "bakersfield_arrival",
        "The Bakersfield Sound",
        "Freight on the dock in Bakersfield. The streets out here have a twang all their own, and your air brakes kept the beat.",
        "Landmarks",
        "Dwight Yoakam & Buck Owens - Streets of Bakersfield",
    ),
    Achievement(
        "tulsa_arrival",
        "Tulsa, Right on Schedule",
        "Pulled into Tulsa with the clock on your side. However long the run took, the dock was glad to see you when you got there.",
        "Landmarks",
        "Don Williams - Tulsa Time",
    ),
    Achievement(
        "vegas_arrival",
        "Long Live Las Vegas",
        "Hauled a load into Las Vegas without leaving a nickel in a machine. The only thing you gambled was the merge, and the house lost.",
        "Landmarks",
        "Elvis Presley - Viva Las Vegas",
    ),
    Achievement(
        "georgia_arrival",
        "Midnight Freight to Georgia",
        "Delivered somewhere in Georgia, maybe well after dark. No first-class ticket -- just a sleeper, a thermos, and a place you'd rather be.",
        "Landmarks",
        "Gladys Knight & the Pips - Midnight Train to Georgia",
    ),
    Achievement(
        "detroit_run",
        "Last Load Out of Detroit",
        "You ran a load into or out of Detroit. The home you left keeps calling, but the freight pays better than the homesickness does.",
        "Landmarks",
        "Bobby Bare - Detroit City",
    ),
    # -- Challenges: the grind, the long ones, and the spotless runs ----------
    Achievement(
        "all_regions",
        "Been Everywhere, For Real",
        "You've now hauled freight in all fourteen regions on the map. The list of towns is finally long enough to leave somebody breathless.",
        "Challenges",
        "Hank Snow - I've Been Everywhere",
    ),
    Achievement(
        "coast_to_coast",
        "Coast-to-Coast Hauler",
        "One run that crossed most of a continent, salt air to salt air. Your seat cushion has seen more states this trip than most folks see in a year.",
        "Challenges",
        "Woody Guthrie - This Land Is Your Land",
    ),
    Achievement(
        "fifty_deliveries",
        "Fifty Loads Down the Road",
        "Fifty career deliveries logged. The board knows your handle now, and the windshield's collected a small nation of bugs.",
        "Challenges",
        "Dave Dudley - Six Days on the Road",
    ),
    Achievement(
        "hundred_deliveries",
        "Just Keep Rollin' On",
        "One hundred deliveries in the book. You never made a fuss about it, just kept the wheels rolling down the road, load after load, until the number turned serious.",
        "Challenges",
        "Lynyrd Skynyrd - Call Me the Breeze",
    ),
    Achievement(
        "ten_thousand_miles",
        "Ten Thousand Down the Line",
        "Ten thousand lifetime miles behind you. The white-line fever stopped being a symptom a long way back -- now it's just the job.",
        "Career",
        "Merle Haggard - White Line Fever",
    ),
    Achievement(
        "fifty_thousand_miles",
        "Highway Lifer",
        "Fifty thousand miles of trailers and two-lane towns behind you. You answer to a long ribbon of road now, and it is not the sort of job a person walks away from.",
        "Challenges",
        "Roger Miller - King of the Road",
    ),
    Achievement(
        "hundred_grand",
        "Hundred-Grand Hood Ornament",
        "You've banked a hundred thousand dollars, one load at a time. Slow as smuggling a Cadillac out a piece at a time -- and a whole lot more legal.",
        "Challenges",
        "Johnny Cash - One Piece at a Time",
    ),
    Achievement(
        "max_level",
        "Veteran of the Long Haul",
        "Career level ten. Same towns, same docks, same diner pie -- but the page turns a little easier when you've read the whole book.",
        "Challenges",
        "Bob Seger - Turn the Page",
    ),
    Achievement(
        "top_reputation",
        "CB Royalty",
        "Your reputation pinned the meter. Trailer for a throne, the whole channel knows the handle, and dispatch finally takes your word for it.",
        "Challenges",
        "Roger Miller - King of the Road",
    ),
    Achievement(
        "perfect_streak",
        "Five Clean, In a Row",
        "Five straight deliveries on time, undamaged, and ticket-free. A streak that quiet doesn't make for a good CB story, but it pays.",
        "Challenges",
        "Red Simpson - I'm a Truck",
    ),
    Achievement(
        "grueling_clean",
        "Long, Hard, and Spotless",
        "Twelve hundred-plus miles, on time, and not a fresh scratch on the rig. They swear no run comes easy; you delivered the exception.",
        "Challenges",
        "Dave Dudley - There Ain't No Easy Run",
    ),
    Achievement(
        "big_payday",
        "Paid Like a Boss Hog",
        "One load cleared four grand gross all by itself. Just this once the big money landed squarely on the right side of the law, and the settlement sheet grinned back.",
        "Career",
        "Waylon Jennings - Good Ol' Boys",
    ),
    Achievement(
        "mountain_clean",
        "Over the Rockies, Spotless",
        "You took a mountain grade and brought the freight down clean. The rocky high country tested the brakes; the brakes politely declined to fail.",
        "Challenges",
        "Joe Walsh - Rocky Mountain Way",
    ),
    Achievement(
        "multi_leg_haul",
        "Four Legs and Rolling",
        "A single dispatch that strung four corridors together. Front to back it was a long line of road, and you ran the whole thing nose to tail.",
        "Career",
        "C.W. McCall - Convoy",
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
