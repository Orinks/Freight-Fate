"""State welcome signs -- the "Welcome to X" flavor spoken at a state crossing.

When you cross a state line the trip already emits a ``state_crossing`` cue
(``sim/trip.py`` ``_build_navigation_cues`` -- "Crossing into Nevada near
Baker."). This module is the CONTENT layer that dresses that moment up the way a
real welcome sign does: the state nickname plus a short, true, roadside-register
fun fact, in the cheerful ninety-nineties-highway voice ("home of a former
president", "famous potatoes"). Authored as data so it stays the map/content
author's lane and unit-tests with no audio.

Keys are the full state names exactly as the crossing data spells them (see
``world_data/us/legs.json`` -- "New Hampshire", "District of Columbia"), so the
lookup can hang straight off the cue's ``into_state``. The placement that
actually speaks these -- appending the welcome line to the state-crossing cue,
gated by a chatter switch like the other roadside callouts -- is gameplay-layer
follow-on. Alaska and Hawaii have no road crossing in the lower-forty-eight map
(Alaska is a future Alcan corridor; Hawaii is not drivable), so they are omitted.

Player-facing speech: no codes, no map tags, and numbers spelled out in words so
a screen reader never reads a bare figure ("Route sixty-six", not "Route 66").
"""

from __future__ import annotations

import random

WELCOME_SIGNS_SOURCE = (
    "Original welcome-sign copy pairing each state's well-known nickname with a "
    "widely-documented fact or landmark; roadside register, facts not invented."
)

# One welcome line per state today; kept as tuples so the picker and tests match
# the billboard pools and a state can grow a small pool later without a reshape.
WELCOME_SIGNS: dict[str, tuple[str, ...]] = {
    "Alabama": (
        "Welcome to Alabama, the Yellowhammer State. Home of the rockets that "
        "carried the first men to the moon, built right here in Huntsville.",
    ),
    "Arizona": (
        "Welcome to Arizona, the Grand Canyon State, where the canyon turns out "
        "to be even bigger than the billboards promised.",
    ),
    "Arkansas": (
        "Welcome to Arkansas, the Natural State. Home of a former president, and "
        "the one place in America you can dig your own diamonds and keep them.",
    ),
    "California": (
        "Welcome to California, the Golden State. More people, more traffic, and "
        "more of that burger stand with the palm trees than you can shake a stick at.",
    ),
    "Colorado": (
        "Welcome to Colorado, the Centennial State, where the plains finally quit "
        "and the Rocky Mountains take over all at once.",
    ),
    "Connecticut": (
        "Welcome to Connecticut, the Constitution State, birthplace of the "
        "hamburger, the Frisbee, and a great many very old stone walls.",
    ),
    "Delaware": (
        "Welcome to Delaware, the First State, first to ratify the Constitution "
        "and proud enough to say so right on the sign.",
    ),
    "District of Columbia": (
        "Welcome to the District of Columbia, the nation's capital. Monuments, "
        "museums, and traffic circles laid out to confuse an invading army. And you.",
    ),
    "Florida": (
        "Welcome to Florida, the Sunshine State. Oranges, alligators, and a theme "
        "park about the size of a small country.",
    ),
    "Georgia": (
        "Welcome to Georgia, the Peach State. Home of peaches, pecans, and the "
        "fizzy brown drink that went and conquered the world.",
    ),
    "Idaho": (
        "Welcome to Idaho, the Gem State. Famous potatoes. It says so right on "
        "the license plate, so it must be true.",
    ),
    "Illinois": (
        "Welcome to Illinois, the Prairie State. Land of Lincoln, deep-dish "
        "pizza, and the start of the mother road, Route sixty-six.",
    ),
    "Indiana": (
        "Welcome to Indiana, the Hoosier State, home of the greatest spectacle in "
        "racing and more rows of corn than a driver can count.",
    ),
    "Iowa": (
        "Welcome to Iowa, the Hawkeye State, where the corn is high, the ground "
        "is flat, and somebody carved a baseball diamond into a cornfield.",
    ),
    "Kansas": (
        "Welcome to Kansas, the Sunflower State. Flat as a tabletop, and yes, "
        "Dorothy really was from here.",
    ),
    "Kentucky": (
        "Welcome to Kentucky, the Bluegrass State. Bourbon, horse races, and "
        "fried chicken worth crossing a state line for.",
    ),
    "Louisiana": (
        "Welcome to Louisiana, the Pelican State, where the food is spicy, the "
        "music never quite stops, and the swamp starts at the shoulder.",
    ),
    "Maine": (
        "Welcome to Maine, the Pine Tree State. Lobster, lighthouses, and the "
        "very first sunrise in the nation.",
    ),
    "Maryland": (
        "Welcome to Maryland, the Old Line State. Crab cakes, and the harbor that "
        "gave us the rockets' red glare.",
    ),
    "Massachusetts": (
        "Welcome to Massachusetts, the Bay State, where the Revolution kicked off "
        "and everybody still drives like it.",
    ),
    "Michigan": (
        "Welcome to Michigan, the Great Lakes State. Hold up your right hand: "
        "that is your map. Home of the automobile.",
    ),
    "Minnesota": (
        "Welcome to Minnesota, the North Star State. Ten thousand lakes, give or "
        "take, and winters that absolutely mean it.",
    ),
    "Mississippi": (
        "Welcome to Mississippi, the Magnolia State, birthplace of the blues and "
        "namesake of the mighty river on your left.",
    ),
    "Missouri": (
        "Welcome to Missouri, the Show-Me State, the gateway to the West, with a "
        "giant steel arch to prove it.",
    ),
    "Montana": (
        "Welcome to Montana, Big Sky Country. More cattle than people, and a sky "
        "that earns the nickname every single evening.",
    ),
    "Nebraska": (
        "Welcome to Nebraska, the Cornhusker State. Corn, corn-fed beef, and the "
        "original Cabela's waiting for you out on Interstate eighty.",
    ),
    "Nevada": (
        "Welcome to Nevada, the Silver State, where the desert glitters after "
        "dark and the odds are never quite in your favor.",
    ),
    "New Hampshire": (
        "Welcome to New Hampshire, the Granite State. Live free or die, and no "
        "sales tax. They are not kidding about either one.",
    ),
    "New Jersey": (
        "Welcome to New Jersey, the Garden State. It really is a garden once "
        "you are past the turnpike, and somebody else will pump your gas.",
    ),
    "New Mexico": (
        "Welcome to New Mexico, the Land of Enchantment. Red or green chile on "
        "everything, and night skies the flying-saucer crowd swears by.",
    ),
    "New York": (
        "Welcome to New York, the Empire State. One very large city, and an even "
        "larger amount of state that nobody ever tells you about.",
    ),
    "North Carolina": (
        "Welcome to North Carolina, the Tar Heel State, first in flight and home "
        "of the original pulled-pork argument.",
    ),
    "North Dakota": (
        "Welcome to North Dakota, the Peace Garden State, home of the world's "
        "largest buffalo and a whole highway lined with giant metal sculptures.",
    ),
    "Ohio": (
        "Welcome to Ohio, the Buckeye State, birthplace of aviation and more "
        "astronauts and presidents than really seems fair to the other states.",
    ),
    "Oklahoma": (
        "Welcome to Oklahoma, the Sooner State, where the wind comes sweeping "
        "down the plain, exactly like the song promised.",
    ),
    "Oregon": (
        "Welcome to Oregon, the Beaver State. Waterfalls, giant trees, and a "
        "coastline that fights the Pacific to a draw.",
    ),
    "Pennsylvania": (
        "Welcome to Pennsylvania, the Keystone State, where the country was "
        "founded and the sandwiches come smothered in cheese.",
    ),
    "Rhode Island": (
        "Welcome to Rhode Island, the Ocean State. Small enough to cross on your "
        "lunch break, and serious about coffee milk and hot wieners.",
    ),
    "South Carolina": (
        "Welcome to South Carolina, the Palmetto State, home of the giant "
        "sombrero tower you have been reading about for three hundred miles.",
    ),
    "South Dakota": (
        "Welcome to South Dakota, the Mount Rushmore State. Four presidents "
        "carved into a mountain, and free ice water down the road at Wall Drug.",
    ),
    "Tennessee": (
        "Welcome to Tennessee, the Volunteer State. Music City, Graceland, and "
        "hot chicken that fights back.",
    ),
    "Texas": (
        "Welcome to Texas, the Lone Star State, where everything really is "
        "bigger, including the drive to get across it.",
    ),
    "Utah": (
        "Welcome to Utah, the Beehive State. Red-rock arches, blinding salt "
        "flats, and a lake you can float in like a cork.",
    ),
    "Vermont": (
        "Welcome to Vermont, the Green Mountain State. Maple syrup, covered "
        "bridges, and ice cream with a conscience.",
    ),
    "Virginia": (
        "Welcome to Virginia, the Old Dominion, birthplace of a whole shelf of "
        "presidents, and, so the sign insists, for lovers.",
    ),
    "Washington": (
        "Welcome to Washington, the Evergreen State. Coffee, rain, apples, and a "
        "volcano keeping a quiet eye on things.",
    ),
    "West Virginia": (
        "Welcome to West Virginia, the Mountain State. Almost heaven, they say, "
        "and the roads do wind exactly like the song.",
    ),
    "Wisconsin": (
        "Welcome to Wisconsin, the Badger State. Cheese, more cheese, and a giant "
        "waterpark town they simply call the Dells.",
    ),
    "Wyoming": (
        "Welcome to Wyoming, the Equality State, first to let women vote, home of "
        "Old Faithful and a great deal of wide-open nobody.",
    ),
}

# Case-normalized view so a stray-cased ``into_state`` still resolves.
_BY_LOWER = {name.lower(): lines for name, lines in WELCOME_SIGNS.items()}


def welcome_signs(state: str) -> tuple[str, ...]:
    """Welcome lines for a state, or ``()`` if it has none (e.g. Alaska/Hawaii)."""
    return _BY_LOWER.get(str(state).strip().lower(), ())


def welcome_sign(state: str, rng: random.Random) -> str:
    """One welcome line for a state, deterministically for a seeded RNG.

    Returns the empty string for a state with no sign, so a caller can fall back
    to the plain crossing cue without a lookup of its own.
    """
    lines = welcome_signs(state)
    return rng.choice(lines) if lines else ""


__all__ = [
    "WELCOME_SIGNS_SOURCE",
    "WELCOME_SIGNS",
    "welcome_signs",
    "welcome_sign",
]
