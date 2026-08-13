"""Roadside billboard content -- the spoken flavor you pass on the interstate.

Billboards are ambient roadside color: short, funny, occasionally corridor-
specific signs the event voice reads on the low-priority ambient tier (safety
callouts always preempt them). This is the CONTENT layer -- the sign copy,
authored as data so it stays the map/content author's lane and unit-tests with
no audio. The placement/scheduling that actually speaks them (riding the
navigation-cue and ambient-chatter machinery) is gameplay-layer follow-on.

Two placement modes the content is written for:

* RANDOM en route -- the corridor-agnostic pools (generic Americana, attorney
  ads, church signs, roadside oddities), drawn from a seeded per-trip RNG so a
  drive is deterministic and offline.
* CORRIDOR-KEYED -- ``CORRIDOR_BILLBOARDS`` maps a highway shield to signs for
  the real roadside culture of that route, so a South Dakota Interstate 90 run
  passes the "free ice water, three hundred miles to go" genre and a Mojave
  Interstate 15 run passes alien jerky. Placed signs feel like somewhere, not
  anywhere.

Real roadside attractions are named the way real truck-stop brands already are
(nominative -- a driver really does pass Wall Drug on Interstate 90). The sign
COPY is original parody, not lifted ad text; how closely to echo a real slogan
is an owner call, like the radio-licensing and Big Buck's decisions.

Player-facing speech: no codes, no map tags, and numbers spelled in words so a
screen reader never reads a bare figure ("nine ninety-nine", not "9.99").

The 2026-08-12 owner batch (see the pools tagged with that date) is the one
deliberate exception: those lines are final tester-round copy the owner asked
to ship verbatim, numerals included ("$4.89/gallon", "37 miles", "6 spaces",
"3rd"/"#2", "362 days"). test_billboards.py carries a matching, explicit
allow-list for exactly those lines -- the digit-free rule still applies to
everything else, including any future addition to these same pools.

SONG TRIBUTES (2026-08-12): every achievement in achievements.py credits a
song, and the highway pays some of them back. Tribute signs name the artist
and the song title only -- never a lyric, never a quoted line -- and read as
home-turf pride, not advertising. Tributes whose anchor sits on a mapped
corridor live in ``CORRIDOR_BILLBOARDS`` under that shield; the handful with
no corridor to call home live in ``SONG_TRIBUTE_BILLBOARDS``, which the
random picker reaches for only about one draw in ten
(``TRIBUTE_DRAW_CHANCE``) so the roadside stays attorneys, fireworks, and
pie, with a tribute as an occasional treat rather than a museum wall.
"""

from __future__ import annotations

import random
import re

BILLBOARDS_SOURCE = (
    "Original parody billboard copy evoking real interstate roadside culture; "
    "real attraction names used nominatively, ad text invented."
)

# Corridor-agnostic Americana -- the catch-all random pool.
GENERIC_BILLBOARDS = (
    "Did you eat today? Thank a trucker.",
    "Last real coffee for two hundred miles. This is not a drill.",
    "World's largest pecan. You'll smell it before you see it. Next exit.",
    "Fireworks, fireworks, fireworks. You're already past it.",
    "Prime rib buffet, nine ninety-nine. Cardiologist not included.",
    "Hitchhikers may be escaping inmates. Drive friendly.",
    "Home of the fifty-pound cinnamon roll. Bring a friend. Bring two.",
    "Adult superstore, next exit. Truckers welcome. We won't tell.",
    "Gun show and craft fair this weekend. Something for everyone.",
    "You are now leaving the middle of nowhere. Come back soon.",
    # 2026-08-12 owner batch -- roadfood and attraction signs from the tester
    # round. "3rd-best" and "#2" keep their numerals verbatim (owner sign-off,
    # see the digit-exemption note in test_billboards.py); everything else in
    # this pool stays digit-free by the usual rule.
    "Big Bob's Burgers: burgers so big, the Department of Transportation requires a second trailer.",
    "Mamma's Diner: home cooking! Because apparently your home doesn't have a kitchen.",
    "The Last Chance Cafe: 37 miles back was The First Chance Cafe.",
    "World's 3rd-best pie: we used to be #2. Then Jerry complained.",
    "Uncle Josh's Steakhouse: steaks so tender they're legally considered missing.",
    "Next exit: biggest pancake in the state! Probably. We haven't checked.",
    "Free coffee! With purchase of coffee. Extra refils fifty cents each.",
)

# The truck-wreck attorney genre -- a real interstate staple, and gently meta in
# a trucking sim. Big Jim is invented.
ATTORNEY_BILLBOARDS = (
    "Injured in a truck wreck? Not this trip, we hope. But remember Big Jim.",
    "One call, that's all. Big Jim Tolliver, attorney at law and bass fisherman.",
    "Hurt on the job? Big Jim gets you paid. Big Jim gets Big Jim paid more.",
    "Eighteen wheels of justice. Big Jim sues trucks. Awkward, we know.",
    "Big Jim's big for a reason, he understands your medical problems cause he's got as many problems as he does pounds. Give him a call if life broke you and he'll sue ... whoever",
)

# Church-sign genre -- earnest, punny, occasionally threatening.
FAITH_BILLBOARDS = (
    "Jesus is watching. So is the weigh station. Slow down.",
    "Where will you spend eternity? Smoking or non-smoking?",
    "Got God? Give him a try, he'll ride shotgun or side saddle with ya any day or night",
    "Honk if you love the Lord. Text and drive if you'd like to meet him.",
    "God answers knee-mail.",
)

# The mystery-spot / two-headed-snake / see-the-thing genre.
ROADSIDE_ODDITIES = (
    "Mystery Spot ahead. Gravity is a suggestion here. Nine ninety-five.",
    "See the two-headed rattlesnake. Alive-ish. Next exit.",
    "Alligator farm and fudge shop. Yes, the same building.",
    "Living through chemistry, get your chemistry fix next four exits.",
    "World's largest ball of twine. Bigger than your problems. Probably.",
    "Zoo! Visit the animals or be one!",
)

# Trucker-services genre -- signs pitched straight at the driver, not the
# tourist: fuel, parking, a bed, a nap, or someone offering to take the truck
# off their hands. 2026-08-12 owner batch. "6 spaces" and "$4.89/gallon" keep
# their numerals verbatim (owner sign-off, see the digit-exemption note in
# test_billboards.py).
TRUCKER_SERVICES_BILLBOARDS = (
    "Tired of driving? Pull over. Take a nap. Your dispatcher will still be mad.",
    "Your truck deserves better. You deserve a raise. Neither is happening here.",
    "We buy used trucks! Even the ones that sound like a washing machine full of rocks.",
    "Truckers welcome! Trucks less welcome. Our parking lot only has 6 spaces.",
    "Need diesel? Of course you do. $4.89/gallon. Please cry inside.",
    "Rest easy at the Budget Palace! Luxury not included.",
)

# Fourth-wall genre -- the billboard knows you're reading it. 2026-08-12 owner
# batch.
META_BILLBOARDS = (
    "Congratulations! You have driven past another billboard.",
    "Don't like this billboard? Keep driving.",
)

# Corridor-keyed signs, mapped by highway shield. The lookup normalizes to the
# route number, so "I-90", "I 90", and "Interstate 90" all match.
CORRIDOR_BILLBOARDS: dict[str, tuple[str, ...]] = {
    "I-90": (
        "Free ice water at Wall Drug. Only three hundred miles. You're basically there.",
        "Wall Drug. Five-cent coffee since your grandfather was your age.",
        # Song tributes -- Boston (The Willis Brothers), Moorcroft, Wyoming
        # (Chancey Williams), and the Idaho panhandle (Colby Acuff).
        "Boston ahead. The Willis Brothers needed forty acres to turn a rig around in this town. It hasn't gotten any wider.",
        "Wyoming, Land of the Buffalo. Chancey Williams sings it from right up the road. Buffalo cross wherever they please.",
        "Idaho panhandle country. Colby Acuff and the Western White Pines both grew up here.",
    ),
    "I-95": (
        "The big sombrero tower ahead. Fireworks, tacos, and a lookout. You never sausage a place.",
        "South of the Border, coming up. Or is it? Keep driving to find out.",
        # 2026-08-12 owner batch -- Carolinas fireworks-stand country, the
        # genre South of the Border already trades on. "362 days" keeps its
        # numerals verbatim (owner sign-off, see test_billboards.py).
        "Bubba's Fireworks: open 362 days a year! Closed on the other three because we're usually in the hospital.",
        # Song tributes -- the Haynesville Woods in Maine (Dick Curless), the
        # Jersey Turnpike (Elle King), and Jacksonville (Lynyrd Skynyrd).
        "The Haynesville Woods are up north of here. Dick Curless counted A Tombstone Every Mile. Watch for moose.",
        "New Jersey: more state than it gets credit for. Elle King sings one called Jersey Giant.",
        "Jacksonville ahead, hometown of Lynyrd Skynyrd. Down here even the breeze plays guitar -- they named a song for it, Call Me the Breeze.",
    ),
    "I-10": (
        "The Thing? Mystery of the desert. Two hundred miles of suspense building.",
        "Dinosaurs, next exit. Concrete, enormous, unbothered by extinction.",
        # Song tributes -- the southern transcontinental collects song towns:
        # Phoenix, Houston, Baton Rouge, Biloxi, El Paso, and the Big Thicket.
        "Phoenix ahead, eventually. The desert gives you time to think. Glen Campbell got By the Time I Get to Phoenix out of it.",
        "Houston ahead. Larry Gatlin measured this trip in days and just called the song Houston.",
        "Baton Rouge ahead. Kris Kristofferson set Me and Bobby McGee hitchhiking out of here. Pick up the song, not the hitchhikers.",
        "Biloxi by two? Only if you keep it moving. Ellis Bullard makes it sound easy.",
        "El Paso, out past the haze. Marty Robbins sang El Paso City and the Streets of Laredo. West Texas gave him the material.",
        "The Big Thicket, off to the north -- deep pines and deeper voices. George Jones grew up in there. Welcome to Possum country.",
    ),
    "I-15": (
        "Alien jerky, next exit. They won't say who the jerky's made from.",
        "The Mad Greek. Gyros in the middle of the Mojave. Trust the desert.",
        # Song tribute -- Las Vegas (Elvis Presley).
        "Las Vegas ahead. Elvis said Viva. The lights are on all night.",
    ),
    "I-40": (
        "Historic Route sixty-six. Get your kicks, then get back on schedule.",
        "Meramec-style caverns ahead. Outlaws hid here. So can you, for nine ninety-five.",
        # Song tributes -- the old Route Sixty-Six corridor is wall-to-wall
        # song country: Winslow, Memphis, Muskogee, Okemah, the Smokies, and
        # the mother road itself.
        "Historic Route Sixty-Six, right under your wheels. Bobby Troup gave it a song and half the country followed. The old road still takes visitors.",
        "Winslow, Arizona, home of the world-famous corner. The Eagles sang Take It Easy about it, so the town built a park. Statue included.",
        "Memphis, on down the road. Every highway in Tennessee gets there eventually. Tom T. Hall named his route That's How I Got to Memphis.",
        "Muskogee, Oklahoma, up the road. Merle Haggard put it on the map. The proudest Okies you'll ever wave at.",
        "Okemah, Oklahoma. Home of Woody Guthrie. This Land Is Your Land. This billboard is somebody else's.",
        "East Tennessee, home of Dolly Parton. The Smokies raised her. Nobody's worked a longer shift with a bigger smile.",
    ),
    "I-80": (
        "World's largest porch swing. Seats twenty-five. Zero of them truckers.",
        "Little America, ahead. Ice cream, cheap gas, and a very large sign about it.",
        # Song tribute -- San Francisco Bay at the far western end (Otis
        # Redding).
        "The Dock of the Bay is at the far end of this road. Otis Redding held the best seat. No parking for trailers.",
    ),
    # 2026-08-12 owner batch -- the Rockies climb, where the scenery genuinely
    # earns the joke.
    "I-70": (
        "Have you seen the scenery? Neither has your driver!",
        # Song tributes -- the San Juans (C.W. McCall), the Front Range (Joe
        # Walsh), and Kansas City (Roger Miller).
        "Black Bear Road, way south of here: one lane, hairpins, no guardrails off the Rockies. C.W. McCall sang his way down it. Keep the convoy on the pavement.",
        "The Rockies, straight ahead and getting bigger. Joe Walsh saw this view and wrote Rocky Mountain Way.",
        "Kansas City ahead. Roger Miller made it famous twice -- Kansas City Star, then King of the Road.",
    ),
    # Song tributes -- the Missouri and Oklahoma road. Franklin County,
    # Missouri (Union, Pacific, Saint Clair, Sullivan) is the Franklin County
    # Trucking Company's home turf, by owner order; Tulsa belongs to Don
    # Williams.
    "I-44": (
        "Franklin County, Missouri -- Union, Pacific, Saint Clair, and Sullivan. Home turf of the Franklin County Trucking Company. If you're a trucker, they already wrote your song.",
        "Tulsa ahead. Set your watch to Tulsa Time. Don Williams says it runs a little easier.",
    ),
    # Song tributes -- the Texas-to-Minnesota main street of country music:
    # San Antonio, Austin, Waco, Abbott, Fort Worth, and Wichita.
    "I-35": (
        "You're deep in George Strait country now. All his exes live around here somewhere. Amarillo can wait till morning.",
        "Abbott, Texas -- Willie Nelson's hometown. He's on the road again.",
        "Waco ahead. Croy and the Boys wrote Don't Let Me Die in Waco. The city would like everyone to relax.",
        "Austin ahead. Dale Watson territory -- honky-tonk for people who read weigh station signs.",
        "San Antonio, down the road. Western swing was born in Texas and Bob Wills drove it. New San Antonio Rose still blooms.",
        "Flattest stretch in Kansas: wheat, sky, and telephone poles. Glen Campbell got Wichita Lineman out of one of those poles. Plenty left.",
    ),
    # Song tributes -- the Central Valley grade and the Bakersfield Sound.
    "I-5": (
        "Bakersfield Sound country. Buck Owens and Merle Haggard tuned it, Red Simpson trucked it, Dwight Yoakam kept it running. Turn it up.",
        "The Grapevine, dead ahead. Commander Cody raced a Hot Rod Lincoln up this grade. Trucks use low gear.",
    ),
    # Song tributes -- the Delta highway: Dyess, Arkansas (Johnny Cash) and
    # the old rail line to New Orleans (Willie Nelson's version).
    "I-55": (
        "Arkansas Delta bottomland. Johnny Cash grew up picking cotton out here in Dyess. Hold your lane and walk the line.",
        "The old rail line to New Orleans runs this same stretch. Willie Nelson sang the City of New Orleans down it.",
    ),
    # Song tributes -- Alabama into Tennessee: Hank Williams's home state,
    # Birmingham (Andrea and Mud), and Nashville (Curtis Grimes).
    "I-65": (
        "Alabama, Hank Williams's home state. Move It On Over -- he meant the dog, but the left lane applies.",
        "Birmingham by eight thirty in the morning? It's been done. Andrea and Mud wrote a song about it.",
        "Nashville ahead, where a songwriter waits ten years for one hit. Curtis Grimes wrote Ten Year Town about the wait.",
    ),
    # Song tribute -- Fort Payne, Alabama, hometown of the band Alabama.
    "I-59": (
        "Fort Payne, Alabama -- hometown of the band Alabama. They wrote Roll On for every eighteen wheeler on this road.",
    ),
    # Song tributes -- the long north-south haul: Saginaw and Detroit at the
    # top, Macon, Georgia at the bottom.
    "I-75": (
        "Detroit City ahead. Bobby Bare sang it for every homesick southerner on the assembly lines up here.",
        "Saginaw, Michigan, up the interstate. Lefty Frizzell made a fishing town famous. The bay is cold.",
        "Macon, Georgia -- the Allman Brothers' town. Southbound never sounded better than it does on this stretch.",
    ),
    # Song tributes -- Atlanta owns this corridor: Jerry Reed, Alan Jackson,
    # and Gladys Knight all call it home.
    "I-85": (
        "Atlanta ahead, Jerry Reed's town. He made hauling freight in a hurry flat-out famous -- East Bound and Down.",
        "Newnan, Georgia raised Alan Jackson. He learned to drive on the back roads out here and wrote Drive about it.",
        "Atlanta ahead. Gladys Knight caught the Midnight Train home to it.",
    ),
    # Song tribute -- Chattanooga (Glenn Miller).
    "I-24": (
        "Chattanooga ahead. The Choo Choo is real -- an actual train, parked downtown since Glenn Miller made it swing. No ticket required.",
    ),
    # Song tributes -- Wisconsin gave trucking Dave Dudley; Detroit gave
    # everyone Motown and Bob Seger.
    "I-94": (
        "Wisconsin made Dave Dudley, and Dave Dudley made Six Days on the Road. Every truck stop jukebox since owes him a quarter.",
        "Detroit, the Motown assembly line. Marvin Gaye, Stevie Wonder, and no mountain high enough to slow the freight.",
        "Detroit builds engines, and it built Bob Seger. Night Moves and Turn the Page came off these roads.",
    ),
    # Song tribute -- Ionia County, Michigan (Billy Strings).
    "I-96": (
        "Ionia County, Michigan -- Billy Strings picked his way out of here. Long Journey Home, played fast.",
    ),
    # Song tribute -- Cincinnati (Arlo McKinley).
    "I-71": (
        "Cincinnati ahead, Arlo McKinley's hometown -- the one he wrote Back Home about. The hills sing sad and the chili is a controversy.",
    ),
    # Song tributes -- Charleston, West Virginia raised Red Sovine and Kathy
    # Mattea both.
    "I-77": (
        "Charleston, West Virginia raised Red Sovine, the voice of every ghost rig and truck stop prayer. Give the Phantom the right of way.",
        "Kathy Mattea grew up just down the river. Her big one, Eighteen Wheels and a Dozen Roses, is about the last run before retirement.",
    ),
    # Song tributes -- the Appalachian valley: Russell County, Virginia
    # (Forty-Nine Winchester) and Smoky Mountain fog (Flatt and Scruggs).
    "I-81": (
        "Russell County line, a valley over. Forty-Nine Winchester put it on every honky-tonk jukebox in Virginia. Wave as you pass.",
        "Mountain fog ahead is a local specialty. Flatt and Scruggs turned it into the fastest banjo tune ever cut, Foggy Mountain Breakdown. Use low beams in fog.",
    ),
    # Song tributes -- Kentucky: the bluegrass east (Brit Taylor) and the
    # coalfields (Tennessee Ernie Ford).
    "I-64": (
        "Eastern Kentucky, where the grass really does look blue. Brit Taylor wrote Kentucky Blue about home.",
        "Coal country. Tennessee Ernie Ford counted Sixteen Tons of it and famously came up broke.",
    ),
    # Song tribute -- Hope, Arkansas (Brennen Leigh).
    "I-30": (
        "Hope, Arkansas, next exit. Brennen Leigh wrote a song about running out of it. Fuel up before you do.",
    ),
    # Song tribute -- border-blaster radio country (Wall of Voodoo).
    "I-8": (
        "Border radio country. The old megawatt stations down south out-shouted every dial in America -- Wall of Voodoo caught one and cut Mexican Radio. Scan the dial.",
    ),
    # Song tribute -- Nazareth, Pennsylvania (The Band).
    "I-78": (
        "Nazareth, Pennsylvania, a few exits north. The Weight is about a stranger rolling in looking for a bed. Book ahead.",
    ),
    # Song tribute -- Abilene, Texas (George Hamilton the Fourth).
    "I-20": (
        "Abilene ahead. George Hamilton the Fourth made the town sound gentle as a Sunday. Watch for crosswinds.",
    ),
}


# Big Buck's approach signs -- the parody Texas mega-stop runs its own billboard
# campaign, the one every driver passes for a couple hundred miles before the
# exit. Real Buc-ee's hypes its spotless restrooms across half a state ("only
# two hundred sixty-two miles, you can hold it") and puns off its beaver mascot;
# this is original copy in that register. These fire as you NEAR a Big Buck's
# landmark, not from the corridor-agnostic pool, so the beaver only turns up
# where the beaver actually is. Pairs with the big_bucks brand and gate content.
BIG_BUCKS_BILLBOARDS = (
    # The "you can hold it" bladder-buster core -- the whole genre in one line.
    "Big Buck's. Two hundred sixty-two miles. You can hold it.",
    "Potty like a rockstar. One hundred ninety miles to go, superstar.",
    "Restrooms so clean your mother would approve. She'd also ask why you never call.",
    "Hold it. Just hold it. We believe in you. Ninety more miles.",
    "The cleanest restrooms in America, and you'll spend the next four hundred miles thinking about them.",
    # Home of the Bladder Buster -- the bucket of soda that undoes all of the above.
    "Home of the Bladder Buster. Sixty-four ounces. You come out a changed driver.",
    # Beaver-mascot puns -- their bread and butter.
    "Hello. Is it the beaver you're looking for?",
    "That billboard was printed upside down on purpose. Made you look. Big Buck's, next exit.",
    "A beaver the size of a refrigerator is waving at you. Ninety miles. Wave back.",
    # The food wall.
    "Fresh brisket, a wall of jerky, and Beaver Bites. Ninety miles. Try to think about anything else.",
    "Fudge made fresh this morning. Beaver Bites made fresh this morning. Your diet, made yesterday.",
    # The trucker irony -- sparing, because this is a trucking sim and it stings.
    "Big Buck's ahead. Acres of gleaming fuel islands, and not one of them for you. Drop the trailer and dream.",
)


def _highway_key(highway: str) -> str:
    """The route number from a shield/ref, e.g. 'Interstate 90' or 'I 90' -> '90'."""
    digits = re.findall(r"\d+", str(highway))
    return digits[0] if digits else ""


# Precomputed number-normalized view of the corridor map for robust lookups.
_CORRIDOR_BY_NUMBER = {_highway_key(k): v for k, v in CORRIDOR_BILLBOARDS.items()}

# Song tributes with no mapped corridor to call home -- either the anchor
# sits off the interstate grid (Lubbock, the hollers, redwood country) or the
# song's whole point is being from everywhere at once. Same rules as every
# tribute: artist names and song titles only, never a lyric.
SONG_TRIBUTE_BILLBOARDS = (
    "Hank Snow claimed he'd been everywhere. This mile marker confirms it.",
    "The girl on the billboard? Wrong billboard. Del Reeves saw her a few hundred miles back. Eyes on the road.",
    "West Texas cotton flats made Waylon Jennings. One question -- Are You Sure Hank Done It This Way -- and outlaw country was born.",
    "Somewhere out there is Lubbock, Texas. Mac Davis kept it in his rear view mirror until he missed it.",
    "Redwood country, far off this road: trees taller than your rig is long. Andrew Gabbard wrote one called Redwood.",
    "Up any of these hollers: a porch, a banjo, somebody picking. Dirty Grass Soul calls it Back to the Holler. No trailers past the cattle gate.",
)

# The whole weighting mechanism for the tribute pool: the corridor-agnostic
# picker rolls once per sign and takes a tribute at this rate, otherwise
# drawing from the everyday pools. At one draw in ten, with signs every
# thirty-five to sixty-five miles, a coast-to-coast run passes a small
# handful of tributes -- the roadside stays attorneys, fireworks, and pie.
TRIBUTE_DRAW_CHANCE = 0.1

# Every corridor-agnostic sign, for the random picker.
_ROADSIDE = (
    GENERIC_BILLBOARDS
    + ATTORNEY_BILLBOARDS
    + FAITH_BILLBOARDS
    + ROADSIDE_ODDITIES
    + TRUCKER_SERVICES_BILLBOARDS
    + META_BILLBOARDS
)


def random_billboard(rng: random.Random) -> str:
    """Pick a corridor-agnostic billboard, deterministically for a seeded RNG.

    Rarely (``TRIBUTE_DRAW_CHANCE``) the pick comes from the low-weight song
    tribute pool instead of the everyday pools."""
    if rng.random() < TRIBUTE_DRAW_CHANCE:
        return rng.choice(SONG_TRIBUTE_BILLBOARDS)
    return rng.choice(_ROADSIDE)


def corridor_billboards(highway: str) -> tuple[str, ...]:
    """Signs specific to a highway's real roadside culture, or ``()`` if none."""
    return _CORRIDOR_BY_NUMBER.get(_highway_key(highway), ())


def big_bucks_billboards() -> tuple[str, ...]:
    """Every Big Buck's approach sign, for the near-a-Big-Buck's picker."""
    return BIG_BUCKS_BILLBOARDS


__all__ = [
    "BILLBOARDS_SOURCE",
    "GENERIC_BILLBOARDS",
    "ATTORNEY_BILLBOARDS",
    "FAITH_BILLBOARDS",
    "ROADSIDE_ODDITIES",
    "TRUCKER_SERVICES_BILLBOARDS",
    "META_BILLBOARDS",
    "SONG_TRIBUTE_BILLBOARDS",
    "TRIBUTE_DRAW_CHANCE",
    "CORRIDOR_BILLBOARDS",
    "BIG_BUCKS_BILLBOARDS",
    "random_billboard",
    "corridor_billboards",
    "big_bucks_billboards",
]
