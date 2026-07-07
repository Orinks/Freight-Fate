"""Big Buck's -- roadside-landmark mini-game content (spoken line pools).

Big Buck's is an original parody of the famous Texas travel-center chain that
bans big rigs. This is the CONTENT layer: the spoken lines the landmark
interaction draws from, authored as data so it stays the map/content author's
lane and unit-tests with no audio. The interaction STATE that consumes these
pools -- the gate turn-away menu, the one-time hint flag, the menace/ban
escalation, the crowd cooldown -- is gameplay-layer follow-on. It pairs with the
amenities brand layer's ``Brand(key="big_bucks", bans_big_rigs=True)``.

Two refusal flavors, kept mechanically distinct:

* STRUCTURAL -- your fault. You showed up trailered (loaded or deadhead, still
  an eighteen-wheeler): no-big-rigs signage, then a one-time teaching hint, then
  escalating menace lines, then a temporary ban plus a reputation ding. Comes
  from the truck's configuration, so it is deterministic.
* SITUATIONAL -- not your fault. Even bobtail and welcome, the lot can be mobbed.
  A soft "come back later" with NO penalty, mirroring the full-lot rest stop.

Every string here is player-facing speech: no codes, no map tags, and numbers
spelled in words where a bare figure would read oddly through a screen reader.
"""

from __future__ import annotations

import random

BIG_BUCKS_SOURCE = (
    "Original parody of a well-known Texas travel-center chain that bans big "
    "rigs; names and products are invented to keep the joke and drop the mark."
)

# Forced trailered attempts *after* the first-offense hint before Big Buck's
# bans you. The hint itself is attempt zero; the beaver's patience runs out on
# the attempt that reaches this count.
BAN_THRESHOLD = 3

# STRUCTURAL refusal -- spoken at the gate whenever you roll up trailered.
NO_BIG_RIGS_SIGNAGE = (
    "The sign over the entrance is not subtle: no eighteen-wheelers. Big Buck's "
    "turns away anything pulling a trailer.",
    "A grinning beaver on a billboard waves you off. No eighteen-wheelers, "
    "partner. Not today, not ever.",
)

# STRUCTURAL -- said exactly once, the first time you are turned away, so a new
# player learns the rule (and the bobtail-versus-deadhead distinction).
FIRST_OFFENSE_HINT = (
    "You will never fit a trailer in that car lot. Drop your trailer somewhere "
    "and roll back in bobtail -- just the tractor, no trailer -- and the beaver "
    "will let you slip in."
)

# STRUCTURAL -- escalating flavor for repeat trailered attempts after the hint.
# Indexed by how many times you have already been turned away since the hint;
# the last line is the final warning before the ban.
MENACE_LINES = (
    "Still hauling a trailer. The greeter's smile is getting thin. You know the "
    "rule by now.",
    "That is three strikes' worth of trailer. A manager in a beaver cap is "
    "watching you idle at the entrance.",
    "Last warning: keep blocking the entrance with that rig and Big Buck's will "
    "ask you not to come back for a while.",
)

# STRUCTURAL -- the ban lands, with a reputation ding handled by the interaction.
BAN_NOTICE = (
    "That does it. The beaver has had enough. You are banned from Big Buck's for "
    "a while, and word gets around -- your reputation takes a hit."
)

# STRUCTURAL -- arriving while the ban is still in effect.
STILL_BANNED = (
    "The greeter recognizes your rig from the entrance camera and shakes his "
    "head. Still banned. Come back when things have cooled off."
)

# SITUATIONAL refusal -- you are bobtail and welcome, but the place is a zoo.
# No penalty, no rep hit; just try again later. Riff pool -- add freely.
CROWD_REFUSALS = (
    "Five buses of middle-school thrill-seekers are raiding the fudge counter. "
    "Maybe give it a pass for now.",
    "A tour bus just unloaded forty road-trippers into the brisket line. Give "
    "it an hour.",
    "It is a summer Saturday and the lot is packed to the beaver's whiskers. "
    "Come back when it is calmer.",
    "Three motor homes, a car club, and a wedding party in the parking lot. No "
    "room even for a bobtail today.",
    "They are restocking the jerky wall and half the pumps are coned off. Swing "
    "back later.",
    "The famous restrooms have a line out the door. Trust us -- come back.",
)

# The reward: you dropped your trailer and slipped in bobtail. Welcome flavor.
ARRIVAL_GREETING = (
    "Welcome to Big Buck's. Acres of gleaming fuel islands you are not allowed "
    "to use, the cleanest restrooms in three counties, and a wall of brisket "
    "that can be smelled from the interstate.",
    "You ease the bobtail tractor between two minivans and a beaver the size of "
    "a refrigerator waves hello. You made it in.",
)

# Browsable catalog once you are inside -- a money sink and, later, the buff
# menu. Content only here; the buff effects are gameplay-layer.
MENU = (
    "a brisket sandwich the size of a hubcap",
    "Beaver Bites -- glazed corn-nut things that are dangerously good",
    "a slab of homemade fudge from the fudge counter",
    "a foot of house-smoked jerky off the jerky wall",
    "a soda cup you could bathe a puppy in",
    "a souvenir tee that says I Survived Big Buck's",
)


def crowd_refusal(rng: random.Random) -> str:
    """Pick a situational (not-your-fault) refusal line, deterministically."""
    return rng.choice(CROWD_REFUSALS)


def signage(rng: random.Random) -> str:
    """Pick a no-big-rigs gate line for a trailered arrival, deterministically."""
    return rng.choice(NO_BIG_RIGS_SIGNAGE)


def arrival_greeting(rng: random.Random) -> str:
    """Pick a welcome line for a successful bobtail arrival, deterministically."""
    return rng.choice(ARRIVAL_GREETING)


def menace_line(prior_offenses: int) -> str:
    """Escalating line for a repeat trailered attempt after the first hint.

    ``prior_offenses`` is how many times you have already been turned away since
    the hint (so the first menace line is ``prior_offenses == 1``). Clamped to
    the final warning past the end of the ladder.
    """
    index = min(max(prior_offenses, 1) - 1, len(MENACE_LINES) - 1)
    return MENACE_LINES[index]


def is_ban_earned(prior_offenses: int) -> bool:
    """Whether a trailered attempt should now trigger the temporary ban."""
    return prior_offenses >= BAN_THRESHOLD


__all__ = [
    "BIG_BUCKS_SOURCE",
    "BAN_THRESHOLD",
    "NO_BIG_RIGS_SIGNAGE",
    "FIRST_OFFENSE_HINT",
    "MENACE_LINES",
    "BAN_NOTICE",
    "STILL_BANNED",
    "CROWD_REFUSALS",
    "ARRIVAL_GREETING",
    "MENU",
    "crowd_refusal",
    "signage",
    "arrival_greeting",
    "menace_line",
    "is_ban_earned",
]
