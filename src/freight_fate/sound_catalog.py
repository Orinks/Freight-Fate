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

# The stop bar's continuous tone. It has to be unmistakable -- it is the cue a
# driver stops the truck by -- but at 0.85 it sat well above every
# intermittent cue around it and read as jarring (Darren, 2026-08-15). A
# continuous tone is inherently more present than a tick at the same level, so
# it stays the loudest continuous cue at a level that no longer dominates the
# cab. Lives here, with the catalog, so the road and the Learn game sounds
# screen play it at one level and cannot drift apart.
BAR_SOLID_VOLUME = 0.62


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
        # The one cue on this screen you steer TOWARD. The guide is a pursuit
        # instrument: its target is `curve_steer - offset`, so drifting right
        # leans the bed left, and following the lean is what recovers the lane
        # (sim/lane_guidance.py, and the "follow the sound" note on
        # states/driving_updates.py::_update_lane_guidance_audio). Every other
        # panned cue here is the opposite -- the rumble strip comes from the
        # side you are drifting toward and you steer away from it. If that
        # inversion ever reads as a mistake and someone "corrects" this text,
        # they will be teaching blind drivers to steer off the road.
        SoundEntry(
            "The road lean",
            (
                Cue("vehicle/road", volume=0.6, pan=-0.8, hold_s=2.0),
                Cue("vehicle/road", volume=0.6, pan=0.8, delay_s=2.4, hold_s=2.0),
            ),
            "Not a sound of its own: it is the road noise you are always "
            "hearing, leaning to one side. Steer toward the lean. It leans "
            "the way the wheel should go, so it points into a bend before "
            "you reach it, and away from the edge you are drifting toward. "
            "This is the one cue here you follow rather than avoid, and it "
            "eases back to the middle once you are straight.",
            when="Lane keeping partial or off, and lane-departure warning on. "
            "With that warning off the road stays centered and the lean never "
            "happens; on full lane keeping the truck holds the lane for you.",
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
            (
                Cue("vehicle/edge_shoulder", volume=0.88, pan=-0.7, hold_s=2.0),
                Cue("vehicle/edge_shoulder", volume=0.88, pan=0.7, delay_s=2.4, hold_s=2.0),
            ),
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
            when="The all-clear after a drift needs lane keeping partial or "
            "off and lane-departure warning on. The short answer to a bend "
            "needs curve callouts on and speech set to terse.",
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
            "until you stop it. It also starts on its own while you are "
            "steering across the lane, and while you are lining up for an "
            "exit -- and there the beat quickens as you reach the position "
            "the exit needs, then stops and the signal cancels. The demo "
            "walks it from the left of the lane to the right.",
            when="Lane keeping partial or off, and above walking pace. The "
            "one that starts on its own lasts as long as the move: a steering "
            "direction held, or the exit lane being set after you signalled.",
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
            # Level rises with road speed at the call site; this is what a
            # hairpin approach sounds like, which is the only place they exist.
            (Cue("vehicle/transverse_strips", volume=0.95),),
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
            "Signal tone",
            (
                Cue("vehicle/signal_tone", volume=0.8, pan=-0.6),
                Cue("vehicle/signal_tone", volume=0.8, pan=0.6, delay_s=1.2),
                # The self-cancel, third: quieter and from straight ahead,
                # exactly as states/driving_updates.py::_update_steering_lane_cue
                # plays it. Same tone, and the treatment is the difference.
                Cue("vehicle/signal_tone", volume=0.45, pan=0.0, delay_s=2.4),
            ),
            "Your own turn signal, from the side you signalled. It marks a "
            "move you meant to make: a lane change, easing onto the shoulder, "
            "coming up a ramp, or taking the exit the route asked for. The "
            "quieter one from straight ahead is the same signal cancelling "
            "itself, the way it does in a truck when the wheel comes back: "
            "the move is finished. After an exit line-up that click is the "
            "word that you are far enough over.",
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
            # One sounding, not a loop: the cab plays it once each time the
            # pressure crosses the line, and holding it here would invent a
            # buzzer that never stops.
            (Cue("vehicle/low_air_buzzer", volume=0.7),),
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
            "speed on a gentle grade without touching the brakes. Drivers "
            "call this the jake.",
        ),
        SoundEntry(
            "Engine brake, stage two",
            (Cue("engine/jake_1600", volume=0.49, hold_s=2.5),),
            "Four cylinders of retard. The usual working setting on a long "
            "descent. Drivers call this the jake.",
        ),
        SoundEntry(
            "Engine brake, stage three",
            (Cue("engine/jake_1600", volume=0.76, hold_s=2.5),),
            "Six cylinders: everything the engine brake has. Loud enough "
            "that towns ban it, which is what a no engine brake zone is "
            "about. Drivers call this the jake.",
        ),
        SoundEntry(
            "Overspeed chime",
            (Cue("vehicle/overspeed_chime", volume=0.65),),
            "You are over the posted limit here. It is not a ticket and "
            "nobody has necessarily seen you, but an officer who has will "
            "act on it. The faster the chime repeats, the further over you "
            "are.",
            when="More than 7 miles per hour over the posted limit -- past "
            "anything adaptive cruise will do on its own, and short of where "
            "a trooper can act on your speed.",
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
            # Same level the road plays it at, so learning the cue teaches
            # what it will actually sound like out there.
            (Cue("vehicle/bar_solid", volume=BAR_SOLID_VOLUME, hold_s=3.0),),
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
            "You got past the hazard. This is the success half of the "
            "dodge outcome pair: in terse speech it is the whole confirmation "
            "that you cleared it, and you can go back to normal speed. Its "
            "opposite is the collision below -- the two sound nothing alike, "
            "so 'did I make it?' is never in doubt.",
        ),
        SoundEntry(
            "Collision",
            (Cue("vehicle/collision", volume=0.9),),
            "You hit it. This is the failure half of the dodge outcome pair: "
            "where the hazard-clear chime says you got past, this says you did "
            "not, and a spoken damage figure follows. In terse speech the "
            "sound is the outcome, so it is worth knowing before you need it.",
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
        # The two earcons the S4 driving speech ladder stands in with, once a
        # rung stops speaking a whole category (LADDER_EARCONS in
        # speech_pacing.py, pinned learnable by
        # tests/test_driving_speech_ladder.py). Neither has a real call site
        # yet -- the ladder logs and answers status keys for what it cuts,
        # it does not yet sound anything in its place -- so there is no road
        # level to be faithful to; the levels below are this cue's own.
        # Synthesized rather than shipped (``ladder_earcons.py``), the same
        # way the enforcement signature is -- and, like that one, keyed under
        # a folder name ("ladder/") outside the ones
        # ``tests/test_speech_audio.py::test_all_referenced_assets_exist``
        # scans for a file on disk, since neither cue has one.
        SoundEntry(
            "Coaching note",
            (Cue("ladder/coaching_note", volume=0.4),),
            "A soft two-note rising chime standing in for a driving tip. The "
            "tip itself still reaches the message log, so pull it up there "
            "if you want the words.",
            when="Driving speech set to Quiet. At Urgent only, tips are "
            "dropped instead of getting a sound.",
        ),
        SoundEntry(
            "Status note",
            (Cue("ladder/status_note", volume=0.35),),
            "A single short, low tock standing in for a status update -- "
            "load condition, the weather turning, and the like. The words "
            "still reach the message log and the status keys still answer "
            "for it.",
            when="Driving speech set to Quiet. At Urgent only, status "
            "updates are dropped instead of getting a sound.",
        ),
    ),
)


# The siren and the weigh-station bed are both scaled at runtime by how close
# the vehicle is to the cruiser or the scale; each entry below picks a
# representative level rather than the whole range.
#
# The marker and the pass are two entries, not one, because they are two
# different pieces of information. The marker is the warning the whole
# enforcement contract rests on -- it arrives before a post can observe you.
# The pass is the marker with a vehicle behind it, and it arrives AFTER the
# post is behind you (states/driving_enforcement.PASS_TRIGGER_MI), so it
# cannot be a warning about anything.
_ENFORCEMENT = SoundCategory(
    "Enforcement",
    (
        SoundEntry(
            "Enforcement marker",
            # _play_enforcement_marker's own level for the pre-post warning,
            # centered: the marker says "a post is here", never which side.
            (Cue("enforcement/signature", volume=0.75),),
            "A short pair of rising tones, twice over, straight ahead. An "
            "enforcement post is about to be close enough to watch you, and "
            "this arrives before it can see anything. Be at the limit the "
            "moment you hear it: what you do after this tone is all an "
            "officer sitting there has to go on.",
            when="Always -- nothing turns it off. Every post that is allowed "
            "to cost you anything sounds this first, at every enforcement "
            "presence setting, and the radio is pulled down out of the way "
            "so you can hear it.",
        ),
        SoundEntry(
            "Police car going by",
            # Marker first at PASS_BASE_VOLUME, vehicle PASS_MARKER_LEAD_S
            # behind it at the same pan; PASS_PAN is positive at a scale and
            # negative at every other post.
            (
                Cue("enforcement/signature", volume=0.7, pan=-0.55),
                Cue("traffic/trooper_pass", volume=0.7, pan=-0.55, delay_s=0.2),
                Cue("enforcement/signature", volume=0.7, pan=0.55, delay_s=2.6),
                Cue("traffic/trooper_pass", volume=0.7, pan=0.55, delay_s=2.8),
            ),
            "The marker again, with a vehicle going past a fifth of a second "
            "behind it. You have just passed an enforcement post and a marked "
            "car is around it. This one is news, not a warning: it sounds "
            "once you are already by, and it does not tell you whether "
            "anybody was sitting there. The demo plays it on the left, the "
            "side an ordinary post is on, and then on the right, the side a "
            "weigh station is on.",
            when="Past a post with somebody in it, at any enforcement "
            "presence setting. Past an empty one, only with presence set to "
            "full. Never past a scale that is being worked: there the "
            "approach bed carries the warning instead.",
        ),
        SoundEntry(
            "Siren",
            (Cue("events/police_siren", volume=0.8, pan=-0.5, hold_s=3.0),),
            "A trooper is pulling you over. Signal, brake, and stop on the "
            "shoulder. Ignoring it is logged as evasion and costs far more "
            "than the ticket would have. On the road it starts quiet and "
            "grows over the first few seconds as the cruiser comes up behind "
            "you; the demo holds one steady level, so the rise is the part "
            "you will only hear out there.",
        ),
        SoundEntry(
            "Inspection warning",
            (Cue("events/inspection_warning", volume=0.7),),
            "You are being looked at for something other than speed: visible "
            "damage, no chains inside a chain control, or following far too "
            "close.",
        ),
        SoundEntry(
            "Scale warning",
            (Cue("events/weigh_station_warning", volume=0.7),),
            "An open weigh station is ahead, and the full spoken notice -- "
            "distance, name, the exit key -- follows right behind it. Its "
            "own low thump-then-beep, not the inspection cue, so the scale "
            "is unmistakable before a word is spoken.",
        ),
        SoundEntry(
            "Weigh station",
            # Deliberately louder and longer than the road plays it. This bed
            # is the quietest thing in the catalog by a wide margin -- a flat
            # ambience with no attack, sitting around -33 dBFS where the
            # median cue is -21 -- and on the road that is right, because it
            # works by swelling against engine and tyre noise. Demonstrated
            # in a silent menu at the road's own level it reads as nothing
            # happening at all (Shane, 2026-08-15: "I press enter on it and I
            # get silence"). The screen's whole job is to let a player learn
            # the cue before it matters, so here it plays above the road's
            # ceiling and holds long enough to register as a sound rather
            # than a hiss.
            (Cue("poi/weigh_station_lane", volume=1.0, hold_s=5.0),),
            "The bed that swells as you come up on an open scale. An open "
            "scale must be pulled into; blowing past one is its own stop. On "
            "the road it comes up under the engine rather than over it, so "
            "it is quieter there than it is here.",
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


# What is deliberately not taught, and why. An exclusion is a decision on the
# record, not a gap: the completeness test fails on any played cue that is
# neither catalogued above nor listed here. A trailing "/*" excludes a whole
# folder.
#
# vehicle/road is in NEITHER list as a plain bed -- it is catalogued once, as
# the road lean, because what teaches a player something is its pan.
SELF_EXPLANATORY: dict[str, str] = {
    # Listed one by one rather than as "engine/*": the jake ring lives in the
    # same folder and IS taught, and a folder glob here would mark it excluded
    # and taught at once.
    "engine/idle": "It is an engine and it sounds like one.",
    "engine_classic/idle": "The same engine, in its earlier voice.",
    "engine/low": "As the idle loop: an engine at an engine speed.",
    "engine/mid": "As the idle loop.",
    "engine/midhigh": "As the idle loop.",
    "engine/high": "As the idle loop.",
    "engine/start": "An engine starting, immediately after you started it.",
    "engine/shutdown": "An engine stopping, immediately after you stopped it.",
    "engine/jake_1600_synth": (
        "The classic jake voice: the same three staged entries play it when "
        "Settings, Audio has Engine brake voice set to classic, through the "
        "same key-resolution routing the drive uses. Not a second cue."
    ),
    "weather/*": "Rain, wind, snow and thunder name themselves.",
    "ambient/*": "Scene, not a cue: no decision attached.",
    "music/*": "Songs.",
    "ui/*": "Menu feedback, learned in the first ten seconds of the main menu.",
    "radio/fm_hiss_loop": (
        "Static means weak signal to anyone who has owned a radio, and the "
        "station dropping is spoken aloud when it happens."
    ),
    "radio/picket": "The fringe flutter, same reason as the hiss bed.",
    "radio/static_burst": "Plays under a spoken line that already explains it.",
    "vehicle/road_joint": "Pavement seams: texture, not a decision.",
    "vehicle/truck_door": "A door.",
    "vehicle/fuel_pump": "A fuel pump, at a fuel pump.",
    "vehicle/reverse": "A backup beeper while backing up.",
    "vehicle/horn": "The player is holding the horn key.",
    "vehicle/brake_squeal": "It means you braked hard, which you know.",
    "vehicle/brake_hiss_bed": "The air letting off after you released the brake pedal.",
    "vehicle/gear_shift": "A gear change in a truck that is changing gear.",
    "vehicle/shift_manual": "Banked gear changes, same reason.",
    "vehicle/shift_auto": "Banked gear changes, same reason.",
    "traffic/car_pass": "A vehicle going past sounds like a vehicle going past.",
    "traffic/box_truck_pass": "As the car pass.",
    "traffic/semi_pass": "As the car pass.",
    "poi/facility_gate": "Ambient bed for a place the game has already named.",
    "poi/rest_stop_night": "Ambient bed for a place the game has already named.",
    "facility/dock_gate": "Menu feedback at a facility, not a road cue.",
    "poi/dock_and_deliver": "Menu feedback at a facility, not a road cue.",
}


def is_excluded(key: str) -> bool:
    """Whether ``key`` is deliberately left out of the catalog."""
    if key in SELF_EXPLANATORY:
        return True
    folder = key.split("/", 1)[0]
    return f"{folder}/*" in SELF_EXPLANATORY
