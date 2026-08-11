"""What every road cue means, as data.

Freight Fate teaches its cues at seventy miles an hour: the first time a
player hears one, something is already happening. That is fine for the engine
and useless for the edge ladder, the stop bar and the jake stages, where the
sound IS the information. This catalog is what the Learn game sounds screen
reads -- one entry per cue that carries a decision, with the recipe for
playing it exactly the way the road plays it.

Rules this file lives by:

* **Pure data.** No pygame, no audio engine, no states. It is imported by the
  screen and by tests, and it must stay cheap and headless.
* **Canonical nouns.** Every ``name`` is the word ``docs/ontology.md`` already
  uses. A catalog that invents a second name for the rumble strip is worse
  than no catalog.
* **Faithful recipes.** Volumes and pans are copied from the call site that
  plays the cue in the drive, so what a player learns here is what they hear
  out there. Panned cues demo both sides, because the side is the point.
* **Every exclusion is on the record.** A cue left out goes in
  ``SELF_EXPLANATORY`` with its reason, and the completeness test in
  ``tests/test_sound_catalog.py`` fails on anything in neither list.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cue:
    """One sounding inside a demo: what to play, how, and when.

    ``hold_s`` above zero makes this a held loop rather than a one-shot: the
    demo re-asserts it for that many seconds and then releases it. ``delay_s``
    is measured from the start of the whole demo, not from the previous cue.
    """

    key: str
    volume: float = 1.0
    pan: float = 0.0
    delay_s: float = 0.0
    hold_s: float = 0.0
    fallback: str = ""


@dataclass(frozen=True)
class SoundEntry:
    name: str  # the canonical spoken noun, from docs/ontology.md
    plays: tuple[Cue, ...]
    meaning: str  # what it tells you, and what to do about it
    when: str = ""  # the setting or situation that gates it, if any


@dataclass(frozen=True)
class SoundCategory:
    name: str
    entries: tuple[SoundEntry, ...]


# Lane and steering -----------------------------------------------------------
#
# The edge ladder is three structural textures, not one beep getting louder
# (sim/lane_guidance.edge_rung): clipping the strip is intermittent, fully on
# it is periodic, off the pavement is aperiodic gravel. They are catalogued in
# that order so the escalation is learnable as an escalation.

_LANE = SoundCategory(
    "Lane and steering",
    (
        SoundEntry(
            "The road lean",
            (
                Cue("vehicle/road", volume=0.6, pan=-0.8, hold_s=2.0),
                Cue("vehicle/road", volume=0.6, pan=0.8, delay_s=2.4, hold_s=2.0),
            ),
            "Road noise leans toward the side of the lane you are on, and "
            "toward a bend before you reach it. It is the quietest thing in "
            "the cab that tells you where you are; steer back toward the "
            "middle and it settles.",
            when="Lane keeping partial or off. On full, the truck holds the "
            "lane and the road stays centered.",
        ),
        SoundEntry(
            "Rumble strip, clipped",
            (
                Cue("vehicle/edge_clip", volume=0.5, pan=-0.7, hold_s=1.8),
                Cue("vehicle/edge_clip", volume=0.5, pan=0.7, delay_s=2.2, hold_s=1.8),
            ),
            "A tire is just catching the edge line on that side. You are "
            "still in the lane. Steer gently away from it.",
            when="Lane keeping partial or off.",
        ),
        SoundEntry(
            "Rumble strip",
            (
                Cue("vehicle/edge_strip", volume=0.7, pan=-0.7, hold_s=1.8),
                Cue("vehicle/edge_strip", volume=0.7, pan=0.7, delay_s=2.2, hold_s=1.8),
            ),
            "The whole tire is on the rumble strip on that side. Steer away "
            "now: the next rung of this ladder is off the pavement.",
            when="Lane keeping partial or off.",
        ),
        SoundEntry(
            "Off the pavement",
            (Cue("vehicle/edge_shoulder", volume=0.88, pan=-0.7, hold_s=2.0),),
            "Gravel. The truck has left the road surface on that side. Ease "
            "back on: do not yank the wheel, and do not brake hard while a "
            "trailer wheel is still in the dirt.",
            when="Lane keeping partial or off. Past an undivided centerline "
            "there is no gravel, so the rumble strip stays the outermost "
            "sound and the spoken warning carries the danger.",
        ),
        SoundEntry(
            "Back in the lane",
            (Cue("vehicle/lane_centered", volume=0.5),),
            "The soft chime that says you are centered again. It is the "
            "all-clear after a drift, and it also marks a bend taken cleanly "
            "when speech is set to terse.",
        ),
        SoundEntry(
            "Lane line crossed",
            (
                Cue("vehicle/lane_line_cross", volume=0.7, pan=-0.6),
                Cue("vehicle/lane_line_cross", volume=0.7, pan=0.6, delay_s=1.2),
            ),
            "The tires rolling over the raised markers of a painted line. "
            "You have changed lanes, whether you meant to or not. A quieter "
            "version of it means you have crossed the same line again "
            "straight away.",
        ),
        SoundEntry(
            "Lane locator",
            (
                Cue("vehicle/lane_locator", volume=0.5, pan=-0.9),
                Cue("vehicle/lane_locator", volume=0.5, pan=-0.3, delay_s=1.0),
                Cue("vehicle/lane_locator", volume=0.5, pan=0.3, delay_s=2.0),
                Cue("vehicle/lane_locator", volume=0.5, pan=0.9, delay_s=3.0),
            ),
            "A soft tock, once a beat, panned to where the truck sits inside "
            "its lane. You turn it on and off yourself and it keeps ticking "
            "until you stop it. The demo walks it from the left of the lane "
            "to the right.",
            when="Lane keeping partial or off, and above walking pace.",
        ),
        SoundEntry(
            "Rumble strip, single hit",
            (Cue("vehicle/rumble_strip", volume=0.8),),
            "A single hit of rumble strip with nothing held after it. A tired "
            "driver wandering, or the truck catching the edge for a moment. "
            "If you did not steer, it is fatigue, and it is telling you to "
            "find somewhere to stop.",
        ),
        SoundEntry(
            "Transverse strips",
            (Cue("vehicle/transverse_strips", volume=0.8),),
            "Grouped bars cut across the whole lane, not along its edge. Real "
            "road agencies only cut these ahead of a curve that has killed "
            "people. Brake as soon as you hear them; they are placed far "
            "enough back that braking still makes the corner.",
        ),
        SoundEntry(
            "Curve chime",
            (
                Cue("vehicle/curve_bink", volume=0.9, pan=-0.85),
                Cue("vehicle/curve_bink", volume=0.9, pan=0.85, delay_s=1.2),
            ),
            "A demanding bend is coming, and the chime comes from the side it "
            "turns toward. Be under the advised speed before you reach it, "
            "not while you are in it.",
            when="Curve callouts on.",
        ),
        SoundEntry(
            "Exit signal tone",
            (
                Cue("vehicle/signal_tone", volume=0.8, pan=-0.6),
                Cue("vehicle/signal_tone", volume=0.8, pan=0.6, delay_s=1.2),
            ),
            "Your signal, from the side you signalled. It marks a deliberate "
            "move: an exit you asked for, or a lane change you meant.",
        ),
    ),
)


CATALOG: tuple[SoundCategory, ...] = (_LANE,)


def catalog_entries() -> tuple[SoundEntry, ...]:
    """Every entry, in catalog order."""
    return tuple(entry for category in CATALOG for entry in category.entries)


def catalog_keys() -> set[str]:
    """Every sound key the catalog plays, fallbacks included."""
    keys: set[str] = set()
    for entry in catalog_entries():
        for cue in entry.plays:
            keys.add(cue.key)
            if cue.fallback:
                keys.add(cue.fallback)
    return keys
