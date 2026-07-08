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
    "Try our forty-eight ounce steak. Seasoned and purely American, if you eat this thing in an hour, you eat it for free!",
    "Fireworks, fireworks, fireworks. You're already past it.",
    "Prime rib buffet, nine ninety-nine. Cardiologist not included.",
    "Hitchhikers may be escaping inmates. Drive friendly.",
    "Home of the fifty-pound cinnamon roll. Bring a friend. Bring two.",
    "Adult superstore, next exit. Truckers welcome. We won't tell.",
    "Gun show and craft fair this weekend. Something for everyone.",
    "You are now leaving the middle of nowhere. Come back soon.",
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

# Corridor-keyed signs, mapped by highway shield. The lookup normalizes to the
# route number, so "I-90", "I 90", and "Interstate 90" all match.
CORRIDOR_BILLBOARDS: dict[str, tuple[str, ...]] = {
    "I-90": (
        "Free ice water at Wall Drug. Only three hundred miles. You're basically there.",
        "Wall Drug. Five-cent coffee since your grandfather was your age.",
    ),
    "I-95": (
        "The big sombrero tower ahead. Fireworks, tacos, and a lookout. You never sausage a place.",
        "South of the Border, coming up. Or is it? Keep driving to find out.",
    ),
    "I-10": (
        "The Thing? Mystery of the desert. Two hundred miles of suspense building.",
        "Dinosaurs, next exit. Concrete, enormous, unbothered by extinction.",
    ),
    "I-15": (
        "Alien jerky, next exit. They won't say who the jerky's made from.",
        "The Mad Greek. Gyros in the middle of the Mojave. Trust the desert.",
    ),
    "I-40": (
        "Historic Route sixty-six. Get your kicks, then get back on schedule.",
        "Meramec-style caverns ahead. Outlaws hid here. So can you, for nine ninety-five.",
    ),
    "I-80": (
        "World's largest porch swing. Seats twenty-five. Zero of them truckers.",
        "Little America, ahead. Ice cream, cheap gas, and a very large sign about it.",
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

# Every corridor-agnostic sign, for the random picker.
_ROADSIDE = GENERIC_BILLBOARDS + ATTORNEY_BILLBOARDS + FAITH_BILLBOARDS + ROADSIDE_ODDITIES


def random_billboard(rng: random.Random) -> str:
    """Pick a corridor-agnostic billboard, deterministically for a seeded RNG."""
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
    "CORRIDOR_BILLBOARDS",
    "BIG_BUCKS_BILLBOARDS",
    "random_billboard",
    "corridor_billboards",
    "big_bucks_billboards",
]
