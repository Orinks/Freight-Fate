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
# recognizable lines, and do not show the source field in the in-game menu.
ACHIEVEMENTS: tuple[Achievement, ...] = (
    Achievement(
        "first_dispatch",
        "Load Duck",
        "You accepted your first dispatch from the board. The radio-myth crowd can keep the nicknames; you got a load number and somewhere to be.",
        "Getting started",
        "C.W. McCall - Convoy",
    ),
    Achievement(
        "first_pickup",
        "Seal The Deal",
        "You loaded cargo at the pickup dock and left with the seal doing its job. That is less glamorous than a big-rig anthem, but much harder to fake at the gate.",
        "Getting started",
        "Alabama - Roll On (Eighteen Wheeler)",
    ),
    Achievement(
        "first_delivery",
        "Dockward And Done",
        "You settled your first delivery after choosing Dock and deliver. The receiver got freight, the paperwork got signatures, and the dock plate survived its cameo.",
        "Deliveries",
        "Jerry Reed - East Bound and Down",
    ),
    Achievement(
        "first_on_time",
        "Beat The Clock, Keep The Diesel",
        "You finished inside the deadline instead of turning punctuality into a stunt. The road-grind legend can brag later; dispatch mostly likes the timestamp.",
        "Deliveries",
        "Dave Dudley - Six Days on the Road",
    ),
    Achievement(
        "clean_delivery",
        "Billboard Without A Dent",
        "You settled a load with no more than one percent new truck damage. The roadside glamour can have the smile; you kept the repair clipboard bored.",
        "Deliveries",
        "Del Reeves - Girl on the Billboard",
    ),
    Achievement(
        "speed_limit_saint",
        "No Hot-Rod Paper Trail",
        "You settled a run with zero speeding strikes. The souped-up impulse tapped the throttle, then you made it sit quietly and think about insurance.",
        "Deliveries",
        "Commander Cody and His Lost Planet Airmen - Hot Rod Lincoln",
    ),
    Achievement(
        "five_deliveries",
        "Back Where The Asphalt Knows You",
        "You settled your fifth career delivery. The asphalt may remember you fondly, but the career screen is the one keeping score without getting sentimental.",
        "Career",
        "Willie Nelson - On the Road Again",
    ),
    Achievement(
        "ten_deliveries",
        "Ten-Four, Ten Loads",
        "You settled your tenth career delivery. The radio-handle fantasy now has enough receipts to stop sounding like something you made up in a fuel line.",
        "Career",
        "C.W. McCall - Convoy",
    ),
    Achievement(
        "level_three",
        "Another Page In The Logbook",
        "You reached career level 3. The lonely-stage mood can wait; the freight board just found better rates and slightly sharper teeth.",
        "Career",
        "Bob Seger - Turn the Page",
    ),
    Achievement(
        "twenty_five_grand",
        "Monarch Of The Ledger",
        "You banked at least 25,000 dollars. The budget-road royalty joke came true backward: you have money, receipts, and a garage catalog trying to look casual.",
        "Career",
        "Johnny Cash - One Piece at a Time",
    ),
    Achievement(
        "thousand_miles",
        "Bug-Spattered Worldview",
        "You logged 1,000 lifetime miles. The windshield has seen enough country to offer opinions, though most of them are shaped like insects.",
        "Career",
        "Merle Haggard - White Line Fever",
    ),
    Achievement(
        "long_haul",
        "Half-Dozen Sunrises, Condensed",
        "You completed a loaded haul of at least 900 miles. It was not a literal week of road mythology, just long enough for the seat cushion to develop seniority.",
        "Routes",
        "Tiny Harris - Endless Black Ribbon",
    ),
    Achievement(
        "state_crossing",
        "One Border, Many Boasts",
        "You crossed your first state line with freight still aboard. The grand travel brag began modestly: one sign, one state name, and one GPS pronunciation attempt.",
        "Routes",
        "Johnny Cash - I've Been Everywhere",
    ),
    Achievement(
        "multi_state",
        "Gazetteer With Gaps",
        "You finished a route through at least three states. You did not visit every town, but the map still had to clear its throat.",
        "Routes",
        "Hank Snow / Johnny Cash - I've Been Everywhere",
    ),
    Achievement(
        "three_regions",
        "Back On Familiar Pavement",
        "You visited three freight regions. That is not every road in the songbook, but it is enough for dispatch to mispronounce your location with confidence.",
        "Routes",
        "Willie Nelson - On the Road Again",
    ),
    Achievement(
        "toll_paid",
        "Toll Booth Serenade",
        "You triggered a carrier-billed toll and kept your personal wallet out of it. The fast-delivery grin got one tiny beep, then accounting took over.",
        "Routes",
        "Jerry Reed - East Bound and Down",
    ),
    Achievement(
        "no_toll_long",
        "Easy-Run Wallet Trick",
        "You settled a loaded route of at least 300 miles with no toll expense. The allegedly hard run looked at the cash drawer and decided to behave.",
        "Routes",
        "Dave Dudley - There Ain't No Easy Run",
    ),
    Achievement(
        "rain_driver",
        "Metronome On The Glass",
        "You drove through rain or heavy rain and kept the truck civilized. The wipers handled percussion, while your following distance did the adult supervision.",
        "Weather",
        "Del Reeves - Looking at the World Through a Windshield",
    ),
    Achievement(
        "winter_or_wind",
        "Eighteen-Wheel Snow Verse",
        "You drove through snow or wind and gave the trailer fewer opinions than it wanted. The big-rig family kept moving because traction won the argument.",
        "Weather",
        "Alabama - Roll On (Eighteen Wheeler)",
    ),
    Achievement(
        "low_visibility",
        "Banjo Fog Freight",
        "You drove through fog or thunderstorm gloom while the horizon acted unavailable. The nimble-picking joke stayed light; you trusted headlights, GPS, and brake distance.",
        "Weather",
        "Flatt & Scruggs - Foggy Mountain Breakdown",
    ),
    Achievement(
        "hazard_avoided",
        "Highway To Not Today",
        "You slowed enough to avoid a road hazard. The dramatic-ramp anthem can keep its smoke machine; your brake pedal solved the problem quietly.",
        "Road events",
        "AC/DC - Highway to Hell",
    ),
    Achievement(
        "construction_zone",
        "Hard-Hat Honky-Tonk",
        "You entered a construction zone and treated every cone like it had a lawyer. The dance-floor swagger shrank to posted speed, vests, and patient merging.",
        "Road events",
        "John Anderson - Honky Tonk Crowd",
    ),
    Achievement(
        "traffic_slowing",
        "CB Etiquette Champion",
        "You handled heavy traffic without turning the bumper gap into folklore. The radio-club fantasy appreciates restraint when nobody has to describe your mistake.",
        "Road events",
        "C.W. McCall - Convoy",
    ),
    Achievement(
        "inspection",
        "Scale-House, No Sweat",
        "You met an inspection or weigh-station check and had the paperwork survive. The mischievous-radio energy stayed outside while your axle numbers behaved indoors.",
        "Road events",
        "Rod Hart - C.B. Savage",
    ),
    Achievement(
        "first_rest_stop",
        "Booth Vinyl Charm",
        "You opened a route facility or rest-stop menu for the first time. The truck-stop romance lasted exactly as long as the vending machine took to judge you.",
        "Rest and service",
        "The Willis Brothers - Truck Stop Cutie",
    ),
    Achievement(
        "route_refuel",
        "Home-Stop Fuel Receipt",
        "You refueled at a terminal or route stop before the tank got theatrical. The roadside-cafe nod is there, but the pump receipt did the useful singing.",
        "Rest and service",
        "C.W. McCall - Old Home Filler-Up an' Keep On-a-Truckin' Cafe",
    ),
    Achievement(
        "break_taken",
        "Road-Hand Intermission",
        "You took a 30-minute break at a route stop and let the clock breathe. The road-hand swagger sat down, and your knees entered that into evidence.",
        "Rest and service",
        "Buck Owens - Truck Drivin' Man",
    ),
    Achievement(
        "slept_on_route",
        "Sleeper Math Checks Out",
        "You slept 10 hours on the road and woke up legally useful. The bunk arithmetic was unglamorous, precise, and somehow the most heroic thing available.",
        "Rest and service",
        "Red Simpson - Sleeper, Five-By-Two",
    ),
    Achievement(
        "sleep_before_exhaustion",
        "Centerline Fixation, Avoided",
        "You slept before fatigue got severe enough to start lobbying the steering wheel. The centerline stayed a line, not a personal philosophy.",
        "Rest and service",
        "Merle Haggard - Mama Tried",
    ),
    Achievement(
        "garage_repair",
        "Piece-By-Piece Revival",
        "You repaired the truck in a proper garage instead of building a legend from loose parts. The socket set behaved, and every receipt had a clean conscience.",
        "Truck care",
        "Johnny Cash - One Piece at a Time",
    ),
    Achievement(
        "first_upgrade",
        "Chrome-Shop Receipt",
        "You bought your first upgrade, giving the truck a tiny taste of parking-lot confidence. The fast-car ghost approved, then asked why the invoice was so sensible.",
        "Truck care",
        "Commander Cody and His Lost Planet Airmen - Hot Rod Lincoln",
    ),
    Achievement(
        "heavy_hauler",
        "Eighteen And Counting",
        "You bought the heavy hauler truck. Hills received a professionally worded threat, and the fuel bill immediately requested a speaking part.",
        "Truck care",
        "Alabama - Roll On (Eighteen Wheeler)",
    ),
    Achievement(
        "air_ready",
        "Interstate Astronomer",
        "You built enough air pressure to release the brakes like a professional. The star-power belongs to the compressor today, because swagger still needs PSI.",
        "Truck care",
        "Deep Purple - Highway Star",
    ),
    Achievement(
        "manual_driver",
        "Clutch-Hand Guitar Solo",
        "You started a run in manual mode and made the clutch part of the rhythm section. Every clean shift sounds cool until the grade changes key.",
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
