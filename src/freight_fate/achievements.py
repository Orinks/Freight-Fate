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
        "Rolled into Amarillo in the early light, the load on the dock by daybreak. You weren't quite riding in on a pony, but the Panhandle dawn made up the difference.",
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
        "Rolled out of Lubbock with a load, the high plains opening up ahead. They say happiness is a hometown shrinking in the rearview mirror, and tonight the freight led the way.",
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
        "Pulled into Tulsa with the clock on your side and the load in on time. You ran it tight, and the dock was glad to see you right when they expected you.",
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
        "Delivered somewhere in Georgia with the freight rolling in well after dark. No first-class ticket -- just a sleeper, a thermos, and a place you'd rather be.",
        "Landmarks",
        "Gladys Knight & the Pips - Midnight Train to Georgia",
    ),
    Achievement(
        "detroit_run",
        "Last Load Out of Detroit",
        "You hauled a load out of Detroit and pointed it down the road. The home you left keeps calling, but the freight pays better than the homesickness does.",
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
        "Career level twenty. Same towns, same docks, same diner pie -- but the page turns a little easier when you've read the whole book.",
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
    # -- Landmarks, second verse: states, regions, and more city badges -------
    Achievement(
        "virginia_line",
        "Runnin' the County Line",
        "You put freight on a dock in Virginia, out where the ridgelines run the show. Some county lines out here are worth singing about; you crossed yours with the trailer full.",
        "Landmarks",
        "49 Winchester - Russell County Line",
    ),
    Achievement(
        "birmingham_morning",
        "Birmingham Before the Coffee Kicks In",
        "Freight delivered in Birmingham while the morning was still finding its feet. Eight-thirty in Alabama hits different when you have been rolling since before the birds.",
        "Landmarks",
        "Andrea and Mud - Birmingham, AL 8:30AM",
    ),
    Achievement(
        "kentucky_delivery",
        "Bluegrass on the Bill of Lading",
        "A load signed for in Kentucky, where the pastures look painted and the fences run forever. The grass gets called blue; the money you made on it was plain green.",
        "Landmarks",
        "Brit Taylor - Kentucky Blue",
    ),
    Achievement(
        "jersey_delivery",
        "Giant of the Turnpike",
        "You delivered in New Jersey and lived to merge again. Between the toll plazas and the jughandles, walking tall through Jersey takes a certain kind of nerve.",
        "Landmarks",
        "Elle King - Jersey Giant",
    ),
    Achievement(
        "waco_survivor",
        "Made It to Waco Just Fine",
        "Freight delivered in Waco without a scratch worth mentioning. Whatever the songs say about this town, you rolled in, got the signature, and kept your health intact.",
        "Landmarks",
        "Croy and the Boys - Don't Let Me Die in Waco",
    ),
    Achievement(
        "gulf_coast_by_two",
        "Coast Freight by Two O'Clock",
        "Delivered on the Mississippi Gulf coast with the clock still shy of two. Shrimp boats, salt air, and a bill of lading signed before the afternoon heat got serious.",
        "Landmarks",
        "Ellis Bullard - Biloxi By Two",
    ),
    Achievement(
        "nashville_delivery",
        "An Overnight Success, Eventually",
        "You put a load on a dock in Nashville, where every songwriter is ten years into being discovered any day now. Your freight got its big break on the first try.",
        "Landmarks",
        "Curtis Grimes - Ten Year Town",
    ),
    Achievement(
        "appalachia_delivery",
        "Freight Up the Holler",
        "You delivered into Appalachian coal-and-ridge country, where the roads bend like fiddle tunes. The hills watched you come in, and the dock was glad you did.",
        "Landmarks",
        "Dirty Grass Soul - Back to the Holler",
    ),
    Achievement(
        "wyoming_delivery",
        "Where the Herds Still Graze",
        "A delivery completed in Wyoming, high plains rolling out in every direction. Not much traffic to fight out here -- mostly wind, antelope, and the occasional legend.",
        "Landmarks",
        "Chancey Williams - Land of the Buffalo",
    ),
    Achievement(
        "norcal_giants",
        "Shadow of the Giants",
        "You delivered up in far Northern California, where the biggest living things on Earth watch the trucks go by. The trailer felt small the whole way in.",
        "Landmarks",
        "Andrew Gabbard - Redwood",
    ),
    Achievement(
        "pnw_delivery",
        "Pines to the Pacific",
        "Freight delivered in the Pacific Northwest, where the evergreens crowd the shoulders and the rain keeps its own schedule. The air alone was worth the trip.",
        "Landmarks",
        "Colby Acuff - Western White Pines",
    ),
    Achievement(
        "el_paso_arrival",
        "A Ballad Out West",
        "You brought freight into El Paso, the far west end of Texas. The old ballads about this town end in heartbreak; yours ended with a signed delivery receipt.",
        "Landmarks",
        "Marty Robbins - El Paso City",
    ),
    Achievement(
        "laredo_arrival",
        "Down the Old Cowboy Road",
        "Freight delivered in Laredo, right up against the border. The old song about this town is a slow goodbye; your visit was strictly business, and everybody stayed cheerful.",
        "Landmarks",
        "Marty Robbins - Streets of Laredo",
    ),
    Achievement(
        "baton_rouge_arrival",
        "Better Off Than Busted Flat",
        "You rolled into Baton Rouge with a load and a paycheck coming, which beats thumbing it with a harmonica. Freedom is nice; a settlement sheet is nicer.",
        "Landmarks",
        "Kris Kristofferson - Me and Bobby McGee",
    ),
    Achievement(
        "sacramento_arrival",
        "A Whistle Outside Folsom",
        "Freight delivered in Sacramento, just down the road from a famously well-sung prison. You heard a train whistle on the way in and kept rolling, free as you please.",
        "Landmarks",
        "Johnny Cash - Folsom Prison Blues",
    ),
    Achievement(
        "texas_triangle",
        "All Your Loads Live in Texas",
        "Origin and destination both inside the Texas triangle, one more load bouncing between the big towns. Some drivers spread out; this week the whole map was one state.",
        "Landmarks",
        "George Strait - All My Ex's Live in Texas",
    ),
    # -- Routes, second verse: compass runs and marathon dispatches -----------
    Achievement(
        "true_north_run",
        "The Compass Said Keep Going",
        "A delivery that ran hard north, latitude stacking up the whole way. When the wandering gets aimless, some folks find a bearing and follow it; yours had a dock at the end.",
        "Routes",
        "Caroline Spence - True North",
    ),
    Achievement(
        "southbound_run",
        "Down the Map with a Load",
        "A delivery that ran hard south, shedding latitude with every fuel stop. Warmer air, looser shoulders, and somebody at the bottom of the map waiting on freight.",
        "Routes",
        "The Allman Brothers Band - Southbound",
    ),
    Achievement(
        "return_trip",
        "Right Back Where You Started",
        "You delivered a load, then hauled the very next one straight back where you came from. Some drivers chase new horizons; this week the horizon ran a shuttle.",
        "Routes",
        "Aaron McDonnell - You Drive Back",
    ),
    Achievement(
        "all_terrain_route",
        "Flats, Foothills, and the Big Climb",
        "One route that served flat land, rolling hills, and a real mountain grade before the dock. Your stomach rode the whole ride; the freight never noticed a thing.",
        "Routes",
        "Ellis Bullard - Roller Coaster",
    ),
    Achievement(
        "long_day_run",
        "The Long Way to the Dock",
        "One dispatch that stretched past a full day on the trip clock, sleep and all. The kind of run where the last hundred miles feel personally aimed at you.",
        "Routes",
        "Billy Strings - Long Journey Home",
    ),
    # -- Cargo: what's in the box matters -------------------------------------
    Achievement(
        "reefer_load",
        "Cold Freight, Warm Heart",
        "Your first refrigerated load delivered with the temperature holding steady. The trailer ran cold the whole way there; no reason your mood had to.",
        "Cargo",
        "Hank Williams - Cold, Cold Heart",
    ),
    Achievement(
        "heavy_haul_load",
        "Big John on the Drive Axles",
        "Your first heavy-haul load, the kind of tonnage that makes a trailer groan and a grade think twice. Every gear change felt like moving a legend.",
        "Cargo",
        "Jimmy Dean - Big Bad John",
    ),
    Achievement(
        "high_value_load",
        "Sparkle in the Dry Van",
        "Your first high-value load delivered with the seals intact. Cargo worth more than the truck rides quiet, stays locked up tight, and never stops for souvenirs.",
        "Cargo",
        "Amanda Fields - Diamonds",
    ),
    Achievement(
        "farm_load",
        "Feed, Seed, and Freight",
        "You hauled farm freight where it was needed -- feed, seed, or the season's grain. Somewhere down a gravel drive, a rancher checked the sky and said much obliged.",
        "Cargo",
        "Emily Nenni - On The Ranch",
    ),
    Achievement(
        "max_gross_load",
        "Grossed Out at the Scale House",
        "You delivered a load pushing the legal weight limit, every axle earning its keep. The big mama of manifests, and the scale house waved it through anyway.",
        "Cargo",
        "Joe Stampley - Roll On Big Mama",
    ),
    # -- Career, second verse: the numbers keep climbing ----------------------
    Achievement(
        "twenty_five_deliveries",
        "Twenty-Five and Rolling Steady",
        "Twenty-five career deliveries logged. Not a rookie number anymore, not a veteran number yet -- just a little more road behind you than most folks ever get.",
        "Career",
        "Ellie Turner - A Little Farther Down The Line",
    ),
    Achievement(
        "two_hundred_deliveries",
        "Two Hundred and Playing for Keeps",
        "Two hundred career deliveries in the book. This stopped being a phase somewhere around load fifty; now it is a body of work with its own gravity.",
        "Career",
        "Emily Nenni - Long Game",
    ),
    Achievement(
        "quarter_million_bank",
        "A Vault with Mud Flaps",
        "You banked 250,000 dollars, hauled in one settlement at a time. The teller stopped counting out loud somewhere around the third deposit. The bank is fine, by the way.",
        "Career",
        "Alex Miller - Breaking the Bank",
    ),
    Achievement(
        "half_million_earned",
        "Half a Million in Lifetime Freight",
        "Five hundred thousand dollars in career earnings, gross of everything the road took back along the way. Nobody would call it easy money, but it spends just the same.",
        "Career",
        "Brit Taylor - Rich Little Girls",
    ),
    Achievement(
        "hundred_k_miles",
        "Leave Me on the Interstate",
        "One hundred thousand lifetime miles. At this point the road owns a controlling share of you, and someday it can have the rest -- but not today, driver.",
        "Career",
        "Bob Wayne - Spread My Ashes on the Highway",
    ),
    Achievement(
        "rep_ninety",
        "Strut Past the Fuel Island",
        "Reputation at ninety or better. Walk through any truck stop like you own the coffee machine, because at this point dispatch practically curtsies.",
        "Career",
        "Elvin Bishop - Struttin' My Stuff",
    ),
    Achievement(
        "month_on_road",
        "Thirty Days of Diesel",
        "A full month on the career clock. Thirty days of docks, diners, and dawn departures -- and tomorrow you will get up and ask the road for another one.",
        "Career",
        "Ellie Turner - One More Day",
    ),
    Achievement(
        "home_return",
        "The Porch Light Was Still On",
        "Ten deliveries or more into your career, you brought a load into your old home terminal city. The streets got smaller while you were gone; the welcome did not.",
        "Career",
        "Arlo McKinley - Back Home",
    ),
    Achievement(
        "bobtail_done",
        "Room Enough to Turn Around",
        "You ran a bobtail reposition -- no trailer, no load, no pay, just a tractor finding its next job. Turning a rig around takes a lot less acreage without the box.",
        "Career",
        "The Willis Brothers - Give Me 40 Acres",
    ),
    # -- Seasons: the calendar rides shotgun -----------------------------------
    Achievement(
        "april_first",
        "Nobody's Fool on the First",
        "A delivery settled on the first day of April. Dispatch swore the load was real, and for once the joke was on nobody -- paperwork clean, payment posted.",
        "Seasons",
        "Bo Hazard - April's Fool",
    ),
    Achievement(
        "winter_delivery",
        "December Never Stood a Chance",
        "A load delivered in the dead of winter, heater roaring and shoulders tight. The cold months lean hard on a trucking family; you leaned back and kept rolling.",
        "Seasons",
        "Merle Haggard - If We Make It Through December",
    ),
    Achievement(
        "four_seasons",
        "All Four Pages of the Calendar",
        "You have settled deliveries in spring, summer, fall, and winter. The road changes clothes four times a year, and you have now seen the whole wardrobe.",
        "Seasons",
        "George Jones - Seasons of My Heart",
    ),
    Achievement(
        "desert_summer",
        "Through the Furnace Door",
        "A summer delivery into the desert Southwest, where the asphalt shimmers and the door handle can bite. Whatever is on the other side of hot, you drove through it.",
        "Seasons",
        "Emily Nenni - Gates Of Hell",
    ),
    Achievement(
        "weather_collector",
        "Every Sky in the Logbook",
        "You have driven under every kind of sky the forecast can throw: sun, cloud, rain, downpour, thunder, snow, fog, and wind. None of it lasted; you did.",
        "Weather",
        "Waylon Jennings & Jessi Colter - Storms Never Last",
    ),
    Achievement(
        "storm_driving",
        "Dark Line on the Radar",
        "You drove through a genuine thunderstorm and kept the trailer behind you where it belongs. You could feel the weather coming on long before the first drop hit.",
        "Weather",
        "Channing Wilson - Blues Comin' On",
    ),
    # -- Deliveries, second verse: clocks, gauges, and close calls ------------
    Achievement(
        "deadline_squeaker",
        "Hot Brakes, Warm Handshake",
        "On time with almost nothing to spare -- the kind of arrival where the dock crew was already drafting the late note. They tore it up, and you never saw it.",
        "Deliveries",
        "Brennen Leigh & Asleep At The Wheel - Comin' In Hot",
    ),
    Achievement(
        "first_late",
        "Keep the Bonus, Boss",
        "Your first late delivery is on the books. The bonus walked, the receiver sighed, and you learned exactly how much of a deadline is actually cushion.",
        "Deliveries",
        "Johnny Paycheck - Take This Job and Shove It",
    ),
    Achievement(
        "midnight_delivery",
        "The Small Hours Ride Along",
        "Freight delivered in the smallest hours, between midnight and the first hint of gray. Whatever kept you company out there signed nothing and vanished at the dock.",
        "Deliveries",
        "Dolly Parton & Ben Haggard - Demons",
    ),
    Achievement(
        "dawn_run",
        "Rolling Before the Roosters",
        "You pulled out before the world got loud, first light still rehearsing on the horizon. The early start echoes all day -- mostly in yawns, occasionally in bonuses.",
        "Deliveries",
        "American Aquarium - Waking Up the Echoes",
    ),
    Achievement(
        "fuel_fumes",
        "Hope Is Not a Fuel Plan",
        "You made the dock with the fuel gauge past pleading and into prayer. Somewhere back down the road you passed the last cheap diesel and said, probably fine.",
        "Deliveries",
        "Brennen Leigh - Running Out Of Hope, Arkansas",
    ),
    Achievement(
        "spotless_long",
        "Vanished Like a Professional",
        "Three hundred-plus miles delivered on time with no damage, no strikes, and no tickets. In and out so smooth the paperwork is the only proof you were there.",
        "Deliveries",
        "Caroline Spence - Clean Getaway",
    ),
    # -- Road events, second verse: citations and congestion ------------------
    Achievement(
        "first_ticket",
        "Yeah, Officer, That Was Me",
        "Your first on-the-spot speeding ticket, signed and paid at the roadside. When dispatch heard, they did not even sound surprised -- which stings worse than the fine.",
        "Road events",
        "Drake Milligan - Sounds Like Something I'd Do",
    ),
    Achievement(
        "second_ticket",
        "Twice in One Trip, Really",
        "Two speeding tickets inside a single run. The first one was a lesson; the second one was a decision. The trooper recognized the truck, which is never a good sign.",
        "Road events",
        "Erin Viancourt - Should've Known Better",
    ),
    Achievement(
        "jam_and_cones",
        "Stuck in Every Flavor of Slow",
        "Construction cones and a genuine traffic jam, both inside one trip. For a while there the truck was less a vehicle and more a waiting room with mud flaps.",
        "Road events",
        "Christian Parker - You Ain't Going Nowhere",
    ),
    Achievement(
        "scale_regular",
        "On a First-Name Basis at the Scale",
        "Five inspections weathered across your career. The scale house is a wall every driver has to get over sooner or later; by now you could climb it in your sleep.",
        "Road events",
        "Caroline Spence - Scale These Walls",
    ),
    # -- Truck care, second verse: the shop knows you by name -----------------
    Achievement(
        "all_upgrades",
        "Every Box on the Order Sheet",
        "Every upgrade in the catalog installed on your rig. They quit building cars like they used to, but a fully optioned tractor still turns heads at the fuel island.",
        "Truck care",
        "Dale Watson - Whatever Happened To The Cadillac",
    ),
    Achievement(
        "deep_repair",
        "Back from the Bottom of the Ledger",
        "You brought the truck in at seventy-five percent damage or worse and paid to make it whole. There is only one direction to go from down there, and you took it.",
        "Truck care",
        "Alex Williams - Rock Bottom",
    ),
    Achievement(
        "roadside_fix",
        "The Show Rolls On",
        "Broke down bad enough to call for roadside help, waited out the mechanic, and finished the run anyway. Every touring act has a night like this; yours had freight.",
        "Truck care",
        "Dale Watson & Ray Benson - Bus' Breakdown",
    ),
    # -- Career ladder milestones: the 30-level arc pays out --------------------
    Achievement(
        "level_five",
        "Regular on the Regional Board",
        "Career level five. Dispatch stopped double-checking your paperwork, the lanes run a little wider, and you can even turn a load down without getting a lecture.",
        "Career",
        "Merle Haggard - Workin' Man Blues",
    ),
    Achievement(
        "level_ten",
        "Lead Driver, Says So on the Vest",
        "Career level ten and senior status at the carrier. Premium freight, a deeper board, and new hires who assume you know where every dock in the country hides.",
        "Career",
        "Alabama - Forty Hour Week (For a Livin')",
    ),
    Achievement(
        "level_fifteen",
        "Halfway Up the Ladder",
        "Career level fifteen. The working-capital target is taped to the sun visor now, and the owner-operator checklist reads less like a dream and more like a plan.",
        "Career",
        "Dolly Parton - 9 to 5",
    ),
    Achievement(
        "level_twenty_five",
        "Qualified for Your Own Numbers",
        "Career level twenty-five. Whether or not you ever file the paperwork, this career now qualifies for its own operating authority. In freight, that counts as arriving.",
        "Career",
        "Waylon Jennings - Are You Sure Hank Done It This Way",
    ),
    Achievement(
        "level_thirty",
        "All the Way to the Top Rung",
        "Career level thirty, the top of the ladder. Every rank, every gate, every unlock -- the whole climb is behind you, and the road ahead is simply yours to choose.",
        "Career",
        "Roger Miller - King of the Road",
    ),
    # -- The company fleet: better iron follows seniority ----------------------
    Achievement(
        "fleet_upgrade",
        "Newer Iron from the Yard",
        "Dispatch swapped your assigned tractor for a newer fleet unit, handed over fueled, serviced, and washed. Seniority has a smell, and it is fresh upholstery.",
        "Truck care",
        "Dale Watson - Truckin' Man",
    ),
    Achievement(
        "fleet_flagship",
        "First Pick of the Yard",
        "You reached the top of the company fleet: the flagship tractor with the big bunk and the long legs. The yard hands you the keys before anyone else gets asked.",
        "Truck care",
        "Red Sovine - Phantom 309",
    ),
    Achievement(
        "three_trucks",
        "A Yard of Your Own",
        "Three tractors with your name on the titles. Call it a fleet if you like; the insurance folder certainly does. Somebody still has to drive them all, though.",
        "Truck care",
        "Kathy Mattea - Eighteen Wheels and a Dozen Roses",
    ),
    # -- Business milestones: the arc's biggest doors ---------------------------
    Achievement(
        "owner_operator_buyin",
        "Your Name on the Title",
        "You bought into your first tractor position as a leased-on owner-operator. The revenue is bigger, the bills are yours, and so is every decision from here on.",
        "Career",
        "Red Simpson - I'm a Truck",
    ),
    Achievement(
        "authority_active",
        "Running Under Your Own Numbers",
        "Own authority is active: your freight, your rates, your compliance folder. Nobody left to lease the risk to, and nobody to hand the upside to either.",
        "Career",
        "Hank Williams Jr. - A Country Boy Can Survive",
    ),
    Achievement(
        "self_paid_course",
        "Paid for the Classroom Yourself",
        "You bought an endorsement course with your own money instead of waiting on carrier sponsorship. Ambition has tuition, and you covered it in cash at the counter.",
        "Career",
        "Aaron Tippin - Working Man's Ph.D.",
    ),
    # -- The 623-city map: pins, plates, and far corners ------------------------
    Achievement(
        "twenty_five_cities",
        "Twenty-Five Pins in the Map",
        "Deliveries settled in twenty-five different cities. The atlas in the door pocket is starting to fall open to the right page all on its own.",
        "Landmarks",
        "Hank Snow - I've Been Everywhere",
    ),
    Achievement(
        "seventy_five_cities",
        "Seventy-Five Docks Deep",
        "Seventy-five different cities have signed for your freight. Receivers you have never met already know the truck, and somehow the coffee is bad in every one.",
        "Landmarks",
        "Willie Nelson - Still Is Still Moving to Me",
    ),
    Achievement(
        "hundred_fifty_cities",
        "Half the Map, Signed For",
        "One hundred fifty cities delivered. On a map of six hundred some towns that is a serious dent, and the far side of the country is starting to feel left out.",
        "Landmarks",
        "Alan Jackson - Drive (For Daddy Gene)",
    ),
    Achievement(
        "fifteen_states",
        "Fifteen State Lines Behind You",
        "You have delivered freight in fifteen different states. The trailer plate is a conversation starter now, and the glovebox is mostly toll receipts.",
        "Landmarks",
        "Bobby Bare - 500 Miles Away from Home",
    ),
    Achievement(
        "thirty_states",
        "Thirty States and Counting",
        "Thirty states have taken freight off your trailer. Most folks need a lifetime and a camper to see that much country; you did it hauling other people's furniture.",
        "Landmarks",
        "Johnny Cash - Ride This Train",
    ),
    Achievement(
        "dakota_delivery",
        "Freight for the High Plains",
        "A load delivered into the Dakotas, where the horizon does most of the talking and the wind files a counterclaim. Somebody has to keep the prairie stocked.",
        "Landmarks",
        "Corb Lund - Long Gone to Saskatchewan",
    ),
    Achievement(
        "montana_delivery",
        "Under the Biggest Sky",
        "Freight settled in Montana, where the interstate runs long, the radio runs out, and the sky goes on far past the windshield. Worth the mileage every single time.",
        "Landmarks",
        "Merle Haggard - Big City",
    ),
    Achievement(
        "new_england_delivery",
        "Down East with a Dry Van",
        "A delivery into northern New England: narrow bridges, frost heaves, and town names that pick fights with the GPS. The chowder alone justifies the deadhead home.",
        "Landmarks",
        "Dick Curless - A Tombstone Every Mile",
    ),
    # -- Song cities: places the jukebox got to first ---------------------------
    Achievement(
        "muskogee_arrival",
        "Still Proud in Muskogee",
        "A load delivered into Muskogee, Oklahoma, where folks still take pride in living right and shaking your hand. Clean paperwork counts as manners out here.",
        "Landmarks",
        "Merle Haggard - Okie From Muskogee",
    ),
    Achievement(
        "kansas_city_arrival",
        "Brighter Than the Local TV Star",
        "Freight delivered into Kansas City, home of burnt ends, wide boulevards, and local celebrities who will not help you back into a dock. You managed anyway.",
        "Landmarks",
        "Roger Miller - Kansas City Star",
    ),
    Achievement(
        "memphis_arrival",
        "However You Got to Memphis",
        "Freight put down in Memphis, at the top of the Delta where the river hauls nearly as much as the highway. Whatever brought you here, the dock only asked for the bills.",
        "Landmarks",
        "Tom T. Hall - That's How I Got to Memphis",
    ),
    Achievement(
        "saginaw_arrival",
        "Cold Bay, Warm Welcome",
        "A delivery into Saginaw, up where the bay wind finds every gap in the cab insulation. Half the town works the water; the freight still comes in by road.",
        "Landmarks",
        "Lefty Frizzell - Saginaw, Michigan",
    ),
    Achievement(
        "fort_worth_arrival",
        "Cowtown Crossed Your Mind",
        "A load delivered into Fort Worth, where the stockyards went showbiz but the freight stayed honest. Dallas sits close enough to wave at and far enough to ignore.",
        "Landmarks",
        "George Strait - Does Fort Worth Ever Cross Your Mind",
    ),
    Achievement(
        "san_antonio_arrival",
        "Backing Down to San Antone",
        "Freight settled in San Antonio, down where the missions keep their bells and the breakfast tacos outrank the barbecue. The river walks; your trailer rolled.",
        "Landmarks",
        "Bob Wills & His Texas Playboys - New San Antonio Rose",
    ),
    Achievement(
        "new_orleans_arrival",
        "Good Morning, Crescent City",
        "A load brought into New Orleans, past the wards and the water, where even the freight moves a little behind the beat. Nobody minded, and the coffee fixed it.",
        "Landmarks",
        "Willie Nelson - City of New Orleans",
    ),
    Achievement(
        "houston_arrival",
        "One Day Closer, Says the Odometer",
        "Freight delivered into Houston, a city sprawling far enough to have its own weather and at least four rush hours. Every mile of it counted toward somewhere that matters.",
        "Landmarks",
        "Larry Gatlin & The Gatlin Brothers - Houston (Means I'm One Day Closer to You)",
    ),
    Achievement(
        "winslow_arrival",
        "A Corner Worth Standing On",
        "A load delivered into Winslow, a small Arizona town with one world-famous corner. Park the rig, stretch your legs, and enjoy being the second-most photographed thing downtown.",
        "Landmarks",
        "Eagles - Take It Easy",
    ),
    Achievement(
        "chattanooga_arrival",
        "Quicker Than the Old Express",
        "Freight rolled into Chattanooga ahead of anything on rails, through the ridge cuts where the river bends twice to look around. The old trains would have needed a schedule.",
        "Landmarks",
        "Glenn Miller - Chattanooga Choo Choo",
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


def int_stat(profile: Profile, key: str) -> int:
    try:
        return int(_stats(profile).get(key, 0))
    except (TypeError, ValueError):
        return 0


def increment_stat(profile: Profile, key: str) -> int:
    value = int_stat(profile, key) + 1
    _stats(profile)[key] = value
    return value


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
