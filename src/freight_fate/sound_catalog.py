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


_AIR = SoundCategory(
    "Air and brakes",
    (
        SoundEntry(
            "Air building",
            (Cue("vehicle/air_pressurize", volume=0.6, hold_s=3.0),),
            "The compressor filling the tanks. The truck cannot move until "
            "there is enough air in them, so start the engine, leave the "
            "parking brake set, and wait for it to reach a hundred psi.",
        ),
        SoundEntry(
            "Air dryer purge",
            (Cue("vehicle/air_dryer_purge", volume=0.65),),
            "A short sharp pop from under the truck when the tanks reach "
            "full and the compressor cuts out. Nothing is wrong; it is the "
            "sound of the air system being healthy.",
        ),
        SoundEntry(
            "Low air buzzer",
            (Cue("vehicle/low_air_buzzer", volume=0.7, hold_s=3.0),),
            "Air pressure has fallen too low to brake safely. Stop using the "
            "brakes, let the compressor catch up, and keep the parking brake "
            "set until it does. Hard repeated braking is what empties the "
            "tanks fastest.",
        ),
        SoundEntry(
            "Parking brake set",
            (Cue("vehicle/brake_set", volume=0.65),),
            "The parking brake going on: a hard mechanical clunk of air "
            "dumping. The truck will not move until you release it.",
        ),
        SoundEntry(
            "Parking brake released",
            (Cue("vehicle/brake_release", volume=0.65),),
            "The parking brake coming off. You are free to roll, which also "
            "means the truck can roll on a grade before you are ready.",
        ),
        SoundEntry(
            "Emergency brake",
            (Cue("vehicle/ebrake", volume=0.9, fallback="vehicle/brake_air"),),
            "The hardest stop the truck has. It is for a hazard you cannot "
            "otherwise miss, or a stop you would otherwise overshoot, and it "
            "is rough on the load.",
        ),
        SoundEntry(
            "Tire screech",
            (Cue("vehicle/tire_screech", volume=0.9),),
            "The tires have lost their grip on the road. Ease off whatever "
            "you were doing -- brake, throttle or steering -- rather than "
            "adding more of it. On a wet or icy road this arrives at speeds "
            "that would be fine on dry pavement.",
        ),
    ),
)


# The jake growl is one synthesized loop per rpm band; the retard stage sets
# its level (JAKE_STAGE_GAIN in states/driving_updates.py). The three entries
# below demo the same 1600 rpm band at each stage's gain, so what a player
# learns is the step between stages rather than a change of pitch.
_ENGINE_BRAKE = SoundCategory(
    "Engine brake, speed and shifting",
    (
        SoundEntry(
            "Engine brake, stage one",
            (Cue("engine/jake_1600", volume=0.19, hold_s=2.5),),
            "Two cylinders of retard: the lightest setting. Enough to hold "
            "speed on a gentle grade without touching the brakes.",
        ),
        SoundEntry(
            "Engine brake, stage two",
            (Cue("engine/jake_1600", volume=0.49, hold_s=2.5),),
            "Four cylinders of retard. The usual working setting on a long descent.",
        ),
        SoundEntry(
            "Engine brake, stage three",
            (Cue("engine/jake_1600", volume=0.76, hold_s=2.5),),
            "Six cylinders: everything the engine brake has. Loud enough "
            "that towns ban it, which is what a no engine brake zone is "
            "about.",
        ),
        SoundEntry(
            "Overspeed chime",
            (Cue("vehicle/overspeed_chime", volume=0.65),),
            "You are over the posted limit here. It is not a ticket and "
            "nobody has necessarily seen you, but an officer who has will "
            "act on it.",
        ),
        SoundEntry(
            "Gear grind",
            (Cue("vehicle/gear_grind", volume=1.0),),
            "The shift did not take. Clutch in properly and try the gear "
            "again; grinding wears the box and leaves you without drive on a "
            "grade.",
            when="Manual transmission only.",
        ),
    ),
)


_RAMPS = SoundCategory(
    "Ramps and stop bars",
    (
        SoundEntry(
            "Stop bar tone",
            (Cue("vehicle/bar_solid", volume=0.85, hold_s=3.0),),
            "A continuous tone that means the stop bar is close enough that "
            "you must already be stopping. It runs until you have stopped or "
            "passed it. Treat it as the last warning, not the first.",
        ),
        SoundEntry(
            "Green light",
            (Cue("events/ramp_light_green", volume=0.8),),
            "The signal at the bottom of the ramp is green. You may go "
            "through without stopping if you are already rolling.",
        ),
        SoundEntry(
            "Red light",
            (Cue("events/ramp_light_red", volume=0.7),),
            "The signal has gone red. Stop at the bar and wait for green. "
            "Rolling through draws horns; going through at speed means cross "
            "traffic hits the trailer.",
        ),
    ),
)


_HAZARDS = SoundCategory(
    "Hazards and the road",
    (
        SoundEntry(
            "Hazard warning",
            (Cue("events/hazard_warning", volume=1.0),),
            "Something in your path needs a real reaction now: brake below "
            "twenty five miles per hour quickly, or move to a clear lane if "
            "the warning says the object is in your lane.",
        ),
        SoundEntry(
            "Hazard clear",
            (Cue("events/hazard_clear", volume=0.75),),
            "The hazard is behind you. You can go back to normal speed.",
        ),
        SoundEntry(
            "Construction zone",
            (Cue("events/construction_zone"),),
            "Roadwork ahead. The posted limit drops, a lane may close, and "
            "the taper callout names which side. Move over when told or you "
            "will go through the barrels.",
        ),
        SoundEntry(
            "Traffic slowing",
            (Cue("events/traffic_slowing"),),
            "The traffic in front of you is coming down in speed. Back off "
            "the throttle before you need the brakes.",
        ),
        SoundEntry(
            "Turn ahead",
            (Cue("events/turn_ahead"),),
            "A street maneuver is coming on a local drive. The spoken "
            "guidance that follows names the street and the direction.",
        ),
        SoundEntry(
            "Turn left",
            (Cue("events/turn_left", pan=-0.6),),
            "The next maneuver is a left. Be under the advised speed before "
            "the corner: a loaded trailer off-tracks through a city turn.",
        ),
        SoundEntry(
            "Turn right",
            (Cue("events/turn_right", pan=0.6),),
            "The next maneuver is a right. Same rule as a left, and a right "
            "in a truck needs more room than it looks like it should.",
        ),
        SoundEntry(
            "State line",
            (Cue("events/state_crossing"),),
            "You have crossed into another state. Speed limits and rules can "
            "change with it, and the spoken callout names the new state.",
        ),
        SoundEntry(
            "Toll charged",
            (Cue("events/toll_charged"),),
            "A toll gantry or plaza has billed the truck. Tolls are settled "
            "at delivery, listed separately from anything you were fined.",
        ),
        SoundEntry(
            "Yawn",
            (Cue("driver/yawn", volume=0.9),),
            "You are the one making this sound. Fatigue is building, faster "
            "at night, and a tired driver drifts and reacts late. Plan a "
            "stop rather than pushing through it.",
        ),
    ),
)


# The enforcement post, the siren and the weigh-station bed are all scaled
# at runtime by how close the vehicle is to the cruiser or the scale; each
# entry below picks a representative level rather than the whole range.
_ENFORCEMENT = SoundCategory(
    "Enforcement",
    (
        SoundEntry(
            "Enforcement post",
            (
                Cue("traffic/trooper_pass", volume=0.8, pan=-0.6),
                Cue("traffic/trooper_pass", volume=0.8, pan=0.6, delay_s=1.6),
            ),
            "A patrol car sitting off the road on that side, heard before it "
            "can see you. Most posts are empty and cost you nothing; this "
            "sound means this one is not, so be at the limit before you "
            "reach it.",
        ),
        SoundEntry(
            "Siren",
            (Cue("events/police_siren", volume=0.8, pan=-0.5, hold_s=3.0),),
            "A trooper is pulling you over. Signal, brake, and stop on the "
            "shoulder. Ignoring it is logged as evasion and costs far more "
            "than the ticket would have.",
        ),
        SoundEntry(
            "Inspection warning",
            (Cue("events/inspection_warning", volume=0.7),),
            "You are being looked at for something other than speed: visible "
            "damage, no chains inside a chain control, or following far too "
            "close.",
        ),
        SoundEntry(
            "Weigh station",
            (Cue("poi/weigh_station_lane", volume=0.6, hold_s=3.0),),
            "The bed that swells as you come up on an open scale. An open "
            "scale must be pulled into; blowing past one is its own stop.",
        ),
        SoundEntry(
            "Spike strip",
            (Cue("events/spike_strip", volume=1.0),),
            "The end of a pursuit. If you are hearing this, running from the "
            "lights has already gone as badly as it can go.",
        ),
        SoundEntry(
            "CB chatter",
            (Cue("events/cb_radio_chatter"),),
            "Other drivers passing on what they have seen: enforcement, "
            "wrecks, work zones. It says how sure it is, it is sometimes out "
            "of date, and it never claims the road is clear.",
        ),
    ),
)


_LOAD = SoundCategory(
    "The load",
    (
        SoundEntry(
            "Surge",
            (Cue("vehicle/liquid_wash", volume=0.55, hold_s=3.0),),
            "Liquid running back and forth inside a tank trailer. It builds "
            "while you brake or accelerate and it pushes the truck after you "
            "have stopped doing whatever started it.",
            when="Liquid bulk freight in a tank trailer only.",
        ),
        SoundEntry(
            "Surge strike",
            (Cue("vehicle/liquid_hit", volume=0.85),),
            "The load hitting the front or back of the tank. It shoves the "
            "truck along its length, which is why a smooth bore tank is "
            "braked early and gently rather than late and hard.",
            when="Liquid bulk freight in a tank trailer only.",
        ),
        SoundEntry(
            "Surge strike, sideways",
            (Cue("vehicle/liquid_hit_lateral", volume=0.85),),
            "The load hitting the side of the tank. It has its own voice, "
            "separate from the fore-and-aft strike, because it means "
            "something different: this is the one that rolls trucks. It "
            "arrives after you have already turned or changed lanes.",
            when="Liquid bulk freight in a tank trailer only.",
        ),
    ),
)


CATALOG: tuple[SoundCategory, ...] = (
    _LANE,
    _AIR,
    _ENGINE_BRAKE,
    _RAMPS,
    _HAZARDS,
    _ENFORCEMENT,
    _LOAD,
)


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
