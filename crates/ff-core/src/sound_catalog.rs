//! What every road cue means, as data.
//!
//! Freight Fate teaches its cues at seventy miles an hour: the first time a
//! player hears one, something is already happening. That is fine for the engine
//! and useless for the edge ladder, the stop bar and the jake stages, where the
//! sound IS the information. This catalog is what the Learn game sounds screen
//! reads -- one entry per cue that carries a decision, with the recipe for
//! playing it exactly the way the road plays it.
//!
//! Rules this file lives by:
//!
//! * **Pure data.** No audio engine, no states. It is read by the screen and
//!   by tests, and it must stay cheap and headless.
//! * **Canonical nouns.** Every `name` is the word `docs/ontology.md` already
//!   uses. A catalog that invents a second name for the rumble strip is worse
//!   than no catalog.
//! * **Faithful recipes.** Volumes and pans are copied from the call site that
//!   plays the cue in the drive, so what a player learns here is what they hear
//!   out there. Panned cues demo both sides, because the side is the point.
//! * **Every exclusion is on the record.** A cue left out goes in
//!   [`SELF_EXPLANATORY`] with its reason, and the completeness test in
//!   `tests/test_sound_catalog.py` fails on anything in neither list.
//!
//! Port of `freight_fate/sound_catalog.py`. The demo sequencer that plays an
//! entry (`freight_fate/sound_demo.py`) is the [`demo`] submodule.

pub mod demo;

/// The stop bar's continuous tone. It has to be unmistakable -- it is the cue a
/// driver stops the truck by -- but at 0.85 it sat well above every
/// intermittent cue around it and read as jarring (Darren, 2026-08-15). A
/// continuous tone is inherently more present than a tick at the same level, so
/// it stays the loudest continuous cue at a level that no longer dominates the
/// cab. Lives here, with the catalog, so the road and the Learn game sounds
/// screen play it at one level and cannot drift apart.
pub const BAR_SOLID_VOLUME: f64 = 0.62;

/// One sounding inside a demo: what to play, how, and when.
///
/// `hold_s` above zero makes this a held loop rather than a one-shot: the
/// demo re-asserts it for that many seconds and then releases it. `delay_s`
/// is measured from the start of the whole demo, not from the previous cue.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Cue {
    pub key: &'static str,
    pub volume: f64,
    pub pan: f64,
    pub delay_s: f64,
    pub hold_s: f64,
    pub fallback: &'static str,
}

impl Cue {
    /// A centred one-shot at full volume, played at the start of the demo.
    pub const fn new(key: &'static str) -> Self {
        Self {
            key,
            volume: 1.0,
            pan: 0.0,
            delay_s: 0.0,
            hold_s: 0.0,
            fallback: "",
        }
    }

    pub const fn volume(mut self, volume: f64) -> Self {
        self.volume = volume;
        self
    }

    pub const fn pan(mut self, pan: f64) -> Self {
        self.pan = pan;
        self
    }

    pub const fn delay_s(mut self, delay_s: f64) -> Self {
        self.delay_s = delay_s;
        self
    }

    pub const fn hold_s(mut self, hold_s: f64) -> Self {
        self.hold_s = hold_s;
        self
    }

    pub const fn fallback(mut self, fallback: &'static str) -> Self {
        self.fallback = fallback;
        self
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SoundEntry {
    /// the canonical spoken noun, from docs/ontology.md
    pub name: &'static str,
    pub plays: &'static [Cue],
    /// what it tells you, and what to do about it
    pub meaning: &'static str,
    /// the setting or situation that gates it, if any
    pub when: &'static str,
}

impl SoundEntry {
    pub const fn new(name: &'static str, plays: &'static [Cue], meaning: &'static str) -> Self {
        Self {
            name,
            plays,
            meaning,
            when: "",
        }
    }

    pub const fn when(mut self, when: &'static str) -> Self {
        self.when = when;
        self
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SoundCategory {
    pub name: &'static str,
    pub entries: &'static [SoundEntry],
}

// Lane and steering -----------------------------------------------------------
//
// The edge ladder is three structural textures, not one beep getting louder
// (sim/lane_guidance.edge_rung): clipping the strip is intermittent, fully on
// it is periodic, off the pavement is aperiodic gravel. They are catalogued in
// that order so the escalation is learnable as an escalation.

const LANE: SoundCategory = SoundCategory {
    name: "Lane and steering",
    entries: &[
        // The one cue on this screen you steer TOWARD. The guide is a pursuit
        // instrument: its target is `curve_steer - offset`, so drifting right
        // leans the bed left, and following the lean is what recovers the lane
        // (sim/lane_guidance.py, and the "follow the sound" note on
        // states/driving_updates.py::_update_lane_guidance_audio). Every other
        // panned cue here is the opposite -- the rumble strip comes from the
        // side you are drifting toward and you steer away from it. If that
        // inversion ever reads as a mistake and someone "corrects" this text,
        // they will be teaching blind drivers to steer off the road.
        SoundEntry::new(
            "The road lean",
            &[
                Cue::new("vehicle/road").volume(0.6).pan(-0.8).hold_s(2.0),
                Cue::new("vehicle/road")
                    .volume(0.6)
                    .pan(0.8)
                    .delay_s(2.4)
                    .hold_s(2.0),
            ],
            "Not a sound of its own: it is the road noise you are always \
             hearing, leaning to one side. Steer toward the lean. It leans \
             the way the wheel should go, so it points into a bend before \
             you reach it, and away from the edge you are drifting toward. \
             This is the one cue here you follow rather than avoid, and it \
             eases back to the middle once you are straight.",
        )
        .when(
            "Lane keeping partial or off, and lane-departure warning on. \
             With that warning off the road stays centered and the lean never \
             happens; on full lane keeping the truck holds the lane for you.",
        ),
        SoundEntry::new(
            "Rumble strip, clipped",
            &[
                Cue::new("vehicle/edge_clip")
                    .volume(0.5)
                    .pan(-0.7)
                    .hold_s(1.8),
                Cue::new("vehicle/edge_clip")
                    .volume(0.5)
                    .pan(0.7)
                    .delay_s(2.2)
                    .hold_s(1.8),
            ],
            "A tire is just catching the edge line on that side. You are \
             still in the lane. Steer gently away from it.",
        )
        .when("Lane keeping partial or off."),
        SoundEntry::new(
            "Rumble strip",
            &[
                Cue::new("vehicle/edge_strip")
                    .volume(0.7)
                    .pan(-0.7)
                    .hold_s(1.8),
                Cue::new("vehicle/edge_strip")
                    .volume(0.7)
                    .pan(0.7)
                    .delay_s(2.2)
                    .hold_s(1.8),
            ],
            "The whole tire is on the rumble strip on that side. Steer away \
             now: the next rung of this ladder is off the pavement.",
        )
        .when("Lane keeping partial or off."),
        SoundEntry::new(
            "Off the pavement",
            &[
                Cue::new("vehicle/edge_shoulder")
                    .volume(0.88)
                    .pan(-0.7)
                    .hold_s(2.0),
                Cue::new("vehicle/edge_shoulder")
                    .volume(0.88)
                    .pan(0.7)
                    .delay_s(2.4)
                    .hold_s(2.0),
            ],
            "Gravel. The truck has left the road surface on that side. Ease \
             back on: do not yank the wheel, and do not brake hard while a \
             trailer wheel is still in the dirt.",
        )
        .when(
            "Lane keeping partial or off. Past an undivided centerline \
             there is no gravel, so the rumble strip stays the outermost \
             sound and the spoken warning carries the danger.",
        ),
        SoundEntry::new(
            "Back in the lane",
            &[Cue::new("vehicle/lane_centered").volume(0.5)],
            "The soft chime that says you are centered again. It is the \
             all-clear after a drift, and it also marks a bend taken cleanly \
             when speech is set to terse.",
        )
        .when(
            "The all-clear after a drift needs lane keeping partial or \
             off and lane-departure warning on. The short answer to a bend \
             needs curve callouts on and speech set to terse.",
        ),
        SoundEntry::new(
            "Lane line crossed",
            &[
                Cue::new("vehicle/lane_line_cross").volume(0.7).pan(-0.6),
                Cue::new("vehicle/lane_line_cross")
                    .volume(0.7)
                    .pan(0.6)
                    .delay_s(1.2),
            ],
            "The tires rolling over the raised markers of a painted line. \
             You have changed lanes, whether you meant to or not. A quieter \
             version of it means you have crossed the same line again \
             straight away.",
        ),
        SoundEntry::new(
            "Lane locator",
            &[
                Cue::new("vehicle/lane_locator").volume(0.5).pan(-0.9),
                Cue::new("vehicle/lane_locator")
                    .volume(0.5)
                    .pan(-0.3)
                    .delay_s(1.0),
                Cue::new("vehicle/lane_locator")
                    .volume(0.5)
                    .pan(0.3)
                    .delay_s(2.0),
                Cue::new("vehicle/lane_locator")
                    .volume(0.5)
                    .pan(0.9)
                    .delay_s(3.0),
            ],
            "A soft tock, once a beat, panned to where the truck sits inside \
             its lane. You turn it on and off yourself and it keeps ticking \
             until you stop it. It also starts on its own while you are \
             steering across the lane, and while you are lining up for an \
             exit -- and there the beat quickens as you reach the position \
             the exit needs, then stops and the signal cancels. The demo \
             walks it from the left of the lane to the right.",
        )
        .when(
            "Lane keeping partial or off, and above walking pace. The \
             one that starts on its own lasts as long as the move: a steering \
             direction held, or the exit lane being set after you signalled.",
        ),
        SoundEntry::new(
            "Lane guide tone",
            &[
                Cue::new("guide/lane_guide_tone")
                    .volume(0.35)
                    .pan(-0.8)
                    .hold_s(1.6),
                Cue::new("guide/lane_guide_tone")
                    .volume(0.35)
                    .pan(0.8)
                    .delay_s(2.0)
                    .hold_s(1.6),
            ],
            "A soft note that leans toward the side you are drifting to and \
             stops when you are straight again. You only hear this if you \
             have switched the lane guide sound from road noise to tone; the \
             default is the road itself leaning, with nothing added.",
        )
        .when(
            "Lane guide sound set to tone, and lane departure warning \
             on with lane keeping off or partial.",
        ),
        SoundEntry::new(
            "Rumble strip, single hit",
            &[Cue::new("vehicle/rumble_strip").volume(0.8)],
            "A single hit of rumble strip with nothing held after it. A tired \
             driver wandering, or the truck catching the edge for a moment. \
             If you did not steer, it is fatigue, and it is telling you to \
             find somewhere to stop.",
        ),
        SoundEntry::new(
            "Transverse strips",
            // Level rises with road speed at the call site; this is what a
            // hairpin approach sounds like, which is the only place they exist.
            &[Cue::new("vehicle/transverse_strips").volume(0.95)],
            "Grouped bars cut across the whole lane, not along its edge. Real \
             road agencies only cut these ahead of a curve that has killed \
             people. Brake as soon as you hear them; they are placed far \
             enough back that braking still makes the corner.",
        ),
        SoundEntry::new(
            "Curve chime",
            &[
                Cue::new("vehicle/curve_bink").volume(0.9).pan(-0.85),
                Cue::new("vehicle/curve_bink")
                    .volume(0.9)
                    .pan(0.85)
                    .delay_s(1.2),
            ],
            "A demanding bend is coming, and the chime comes from the side it \
             turns toward. Be under the advised speed before you reach it, \
             not while you are in it.",
        )
        .when("Curve callouts on."),
        SoundEntry::new(
            "Signal tone",
            &[
                Cue::new("vehicle/signal_tone").volume(0.8).pan(-0.6),
                Cue::new("vehicle/signal_tone")
                    .volume(0.8)
                    .pan(0.6)
                    .delay_s(1.2),
                // The self-cancel, third: quieter and from straight ahead,
                // exactly as states/driving_updates.py::_update_steering_lane_cue
                // plays it. Same tone, and the treatment is the difference.
                Cue::new("vehicle/signal_tone")
                    .volume(0.45)
                    .pan(0.0)
                    .delay_s(2.4),
            ],
            "Your own turn signal, from the side you signalled. It marks a \
             move you meant to make: a lane change, easing onto the shoulder, \
             coming up a ramp, or taking the exit the route asked for. The \
             quieter one from straight ahead is the same signal cancelling \
             itself, the way it does in a truck when the wheel comes back: \
             the move is finished. After an exit line-up that click is the \
             word that you are far enough over.",
        ),
    ],
};

const AIR: SoundCategory = SoundCategory {
    name: "Air and brakes",
    entries: &[
        SoundEntry::new(
            "Air building",
            &[Cue::new("vehicle/air_pressurize").volume(0.6).hold_s(3.0)],
            "The compressor filling the tanks. The truck cannot move until \
             there is enough air in them, so start the engine, leave the \
             parking brake set, and wait for it to reach a hundred psi.",
        ),
        SoundEntry::new(
            "Air dryer purge",
            &[Cue::new("vehicle/air_dryer_purge").volume(0.65)],
            "A short sharp pop from under the truck when the tanks reach \
             full and the compressor cuts out. Nothing is wrong; it is the \
             sound of the air system being healthy.",
        ),
        SoundEntry::new(
            "Low air buzzer",
            // One sounding, not a loop: the cab plays it once each time the
            // pressure crosses the line, and holding it here would invent a
            // buzzer that never stops.
            &[Cue::new("vehicle/low_air_buzzer").volume(0.7)],
            "Air pressure has fallen too low to brake safely. Stop using the \
             brakes, let the compressor catch up, and keep the parking brake \
             set until it does. Hard repeated braking is what empties the \
             tanks fastest.",
        ),
        SoundEntry::new(
            "Parking brake set",
            &[Cue::new("vehicle/brake_set").volume(0.65)],
            "The parking brake going on: a hard mechanical clunk of air \
             dumping. The truck will not move until you release it.",
        ),
        SoundEntry::new(
            "Parking brake released",
            &[Cue::new("vehicle/brake_release").volume(0.65)],
            "The parking brake coming off. You are free to roll, which also \
             means the truck can roll on a grade before you are ready.",
        ),
        SoundEntry::new(
            "Emergency brake",
            &[Cue::new("vehicle/ebrake")
                .volume(0.9)
                .fallback("vehicle/brake_air")],
            "The hardest stop the truck has. It is for a hazard you cannot \
             otherwise miss, or a stop you would otherwise overshoot, and it \
             is rough on the load.",
        ),
        SoundEntry::new(
            "Tire screech",
            &[Cue::new("vehicle/tire_screech").volume(0.9)],
            "The tires have lost their grip on the road. Ease off whatever \
             you were doing -- brake, throttle or steering -- rather than \
             adding more of it. On a wet or icy road this arrives at speeds \
             that would be fine on dry pavement.",
        ),
    ],
};

// The jake growl is one synthesized loop per rpm band; the retard stage sets
// its level (JAKE_STAGE_GAIN in states/driving_updates.py). The three entries
// below demo the same 1600 rpm band at each stage's gain, so what a player
// learns is the step between stages rather than a change of pitch.
const ENGINE_BRAKE: SoundCategory = SoundCategory {
    name: "Engine brake, speed and shifting",
    entries: &[
        SoundEntry::new(
            "Engine brake, stage one",
            &[Cue::new("engine/jake_1600").volume(0.19).hold_s(2.5)],
            "Two cylinders of retard: the lightest setting. Enough to hold \
             speed on a gentle grade without touching the brakes. Drivers \
             call this the jake.",
        ),
        SoundEntry::new(
            "Engine brake, stage two",
            &[Cue::new("engine/jake_1600").volume(0.49).hold_s(2.5)],
            "Four cylinders of retard. The usual working setting on a long \
             descent. Drivers call this the jake.",
        ),
        SoundEntry::new(
            "Engine brake, stage three",
            &[Cue::new("engine/jake_1600").volume(0.76).hold_s(2.5)],
            "Six cylinders: everything the engine brake has. Loud enough \
             that towns ban it, which is what a no engine brake zone is \
             about. Drivers call this the jake.",
        ),
        SoundEntry::new(
            "Overspeed chime",
            &[Cue::new("vehicle/overspeed_chime").volume(0.65)],
            "You are over the posted limit here. It is not a ticket and \
             nobody has necessarily seen you, but an officer who has will \
             act on it. The faster the chime repeats, the further over you \
             are.",
        )
        .when(
            "More than 7 miles per hour over the posted limit -- past \
             anything adaptive cruise will do on its own, and short of where \
             a trooper can act on your speed.",
        ),
        SoundEntry::new(
            "Gear grind",
            &[Cue::new("vehicle/gear_grind").volume(1.0)],
            "The shift did not take. Clutch in properly and try the gear \
             again; grinding wears the box and leaves you without drive on a \
             grade.",
        )
        .when("Manual transmission only."),
    ],
};

const RAMPS: SoundCategory = SoundCategory {
    name: "Ramps and stop bars",
    entries: &[
        SoundEntry::new(
            "Stop bar tone",
            // Same level the road plays it at, so learning the cue teaches
            // what it will actually sound like out there.
            &[Cue::new("vehicle/bar_solid")
                .volume(BAR_SOLID_VOLUME)
                .hold_s(3.0)],
            "A continuous tone that means the stop bar is close enough that \
             you must already be stopping. It runs until you have stopped or \
             passed it. Treat it as the last warning, not the first.",
        ),
        SoundEntry::new(
            "Green light",
            &[Cue::new("events/ramp_light_green").volume(0.8)],
            "The signal at the bottom of the ramp is green. You may go \
             through without stopping if you are already rolling.",
        ),
        SoundEntry::new(
            "Red light",
            &[Cue::new("events/ramp_light_red").volume(0.7)],
            "The signal has gone red. Stop at the bar and wait for green. \
             Rolling through draws horns; going through at speed means cross \
             traffic hits the trailer.",
        ),
    ],
};

const HAZARDS: SoundCategory = SoundCategory {
    name: "Hazards and the road",
    entries: &[
        SoundEntry::new(
            "Hazard warning",
            &[Cue::new("events/hazard_warning").volume(1.0)],
            "Something in your path needs a real reaction now: brake below \
             twenty five miles per hour quickly, or move to a clear lane if \
             the warning says the object is in your lane.",
        ),
        SoundEntry::new(
            "Hazard clear",
            &[Cue::new("events/hazard_clear").volume(0.75)],
            "You got past the hazard. This is the success half of the \
             dodge outcome pair: in terse speech it is the whole confirmation \
             that you cleared it, and you can go back to normal speed. Its \
             opposite is the collision below -- the two sound nothing alike, \
             so 'did I make it?' is never in doubt.",
        ),
        SoundEntry::new(
            "Collision",
            &[Cue::new("vehicle/collision").volume(0.9)],
            "You hit it. This is the failure half of the dodge outcome pair: \
             where the hazard-clear chime says you got past, this says you did \
             not, and a spoken damage figure follows. In terse speech the \
             sound is the outcome, so it is worth knowing before you need it.",
        ),
        SoundEntry::new(
            "Construction zone",
            &[Cue::new("events/construction_zone")],
            "Roadwork ahead. The posted limit drops, a lane may close, and \
             the taper callout names which side. Move over when told or you \
             will go through the barrels.",
        ),
        SoundEntry::new(
            "Traffic slowing",
            &[Cue::new("events/traffic_slowing")],
            "The traffic in front of you is coming down in speed. Back off \
             the throttle before you need the brakes.",
        ),
        SoundEntry::new(
            "Turn ahead",
            &[Cue::new("events/turn_ahead")],
            "A street maneuver is coming on a local drive. The spoken \
             guidance that follows names the street and the direction.",
        ),
        SoundEntry::new(
            "Turn left",
            &[Cue::new("events/turn_left").pan(-0.6)],
            "The next maneuver is a left. Be under the advised speed before \
             the corner: a loaded trailer off-tracks through a city turn.",
        ),
        SoundEntry::new(
            "Turn right",
            &[Cue::new("events/turn_right").pan(0.6)],
            "The next maneuver is a right. Same rule as a left, and a right \
             in a truck needs more room than it looks like it should.",
        ),
        SoundEntry::new(
            "State line",
            &[Cue::new("events/state_crossing")],
            "You have crossed into another state. Speed limits and rules can \
             change with it, and the spoken callout names the new state.",
        ),
        SoundEntry::new(
            "Toll charged",
            &[Cue::new("events/toll_charged")],
            "A toll gantry or plaza has billed the truck. Tolls are settled \
             at delivery, listed separately from anything you were fined.",
        ),
        SoundEntry::new(
            "Yawn",
            &[Cue::new("driver/yawn").volume(0.9)],
            "You are the one making this sound. Fatigue is building, faster \
             at night, and a tired driver drifts and reacts late. Plan a \
             stop rather than pushing through it.",
        ),
        // The two earcons the S4 driving speech ladder stands in with, once a
        // rung stops speaking a whole category (LADDER_EARCONS in
        // speech_pacing.py, pinned learnable by
        // tests/test_driving_speech_ladder.py, and played by
        // GameContext._play_ladder_earcon in app.py via
        // sound_catalog.entry_by_name). This entry's own recipe -- key and
        // volume -- IS the road level: app.py resolves the cue from here
        // rather than keeping a second copy, so there is nothing to drift.
        // Synthesized rather than shipped (``ladder_earcons.py``), the same
        // way the enforcement signature is -- and, like that one, keyed under
        // a folder name ("ladder/") outside the ones
        // ``tests/test_speech_audio.py::test_all_referenced_assets_exist``
        // scans for a file on disk, since neither cue has one.
        SoundEntry::new(
            "Confirmation note",
            &[Cue::new("ladder/confirmation_note").volume(0.32)],
            "One short, clear high note standing in for a confirmation -- \
             the assist acted, the setting took, the latch caught. The words \
             still reach the message log. Not to be confused with Hazard \
             clear above, which means something quite different and used to \
             be played here.",
        )
        .when("Driving speech set to Quiet or Urgent only."),
        SoundEntry::new(
            "Road ahead note",
            &[Cue::new("ladder/road_ahead_note").volume(0.38)],
            "Two short notes falling, standing in for a heads-up about what \
             the road is about to do -- a bend coming, a merge, how far the \
             next stretch runs. The words still reach the message log, and \
             the route and road keys still answer for it.",
        )
        .when(
            "Driving speech set to Urgent only. At Quiet and below \
             these are spoken. Directions you cannot recover from -- take \
             this exit, turn here, you missed it -- are always spoken, at \
             every setting.",
        ),
        SoundEntry::new(
            "Coaching note",
            &[Cue::new("ladder/coaching_note").volume(0.4)],
            "A soft two-note rising chime standing in for a driving tip. The \
             tip itself still reaches the message log, so pull it up there \
             if you want the words.",
        )
        .when(
            "Driving speech set to Quiet. At Urgent only, tips are \
             dropped instead of getting a sound.",
        ),
        SoundEntry::new(
            "Status note",
            &[Cue::new("ladder/status_note").volume(0.35)],
            "A single short, low tock standing in for a status update -- \
             load condition, the weather turning, and the like. The words \
             still reach the message log and the status keys still answer \
             for it.",
        )
        .when(
            "Driving speech set to Quiet. At Urgent only, status \
             updates are dropped instead of getting a sound.",
        ),
    ],
};

// The siren and the weigh-station bed are both scaled at runtime by how close
// the vehicle is to the cruiser or the scale; each entry below picks a
// representative level rather than the whole range.
//
// The marker and the pass are two entries, not one, because they are two
// different pieces of information. The marker is the warning the whole
// enforcement contract rests on -- it arrives before a post can observe you.
// The pass is the marker with a vehicle behind it, and it arrives AFTER the
// post is behind you (states/driving_enforcement.PASS_TRIGGER_MI), so it
// cannot be a warning about anything.
const ENFORCEMENT: SoundCategory = SoundCategory {
    name: "Enforcement",
    entries: &[
        SoundEntry::new(
            "Enforcement marker",
            // _play_enforcement_marker's own level for the pre-post warning,
            // centered: the marker says "a post is here", never which side.
            &[Cue::new("enforcement/signature").volume(0.75)],
            "A short pair of rising tones, twice over, straight ahead. An \
             enforcement post is about to be close enough to watch you, and \
             this arrives before it can see anything. Be at the limit the \
             moment you hear it: what you do after this tone is all an \
             officer sitting there has to go on.",
        )
        .when(
            "Always -- nothing turns it off. Every post that is allowed \
             to cost you anything sounds this first, at every enforcement \
             presence setting, and the radio is pulled down out of the way \
             so you can hear it.",
        ),
        SoundEntry::new(
            "Police car going by",
            // Marker first at PASS_BASE_VOLUME, vehicle PASS_MARKER_LEAD_S
            // behind it at the same pan; PASS_PAN is positive at a scale and
            // negative at every other post.
            &[
                Cue::new("enforcement/signature").volume(0.7).pan(-0.55),
                Cue::new("traffic/trooper_pass")
                    .volume(0.7)
                    .pan(-0.55)
                    .delay_s(0.2),
                Cue::new("enforcement/signature")
                    .volume(0.7)
                    .pan(0.55)
                    .delay_s(2.6),
                Cue::new("traffic/trooper_pass")
                    .volume(0.7)
                    .pan(0.55)
                    .delay_s(2.8),
            ],
            "The marker again, with a vehicle going past a fifth of a second \
             behind it. You have just passed an enforcement post and a marked \
             car is around it. This one is news, not a warning: it sounds \
             once you are already by, and it does not tell you whether \
             anybody was sitting there. The demo plays it on the left, the \
             side an ordinary post is on, and then on the right, the side a \
             weigh station is on.",
        )
        .when(
            "Past a post with somebody in it, at any enforcement \
             presence setting. Past an empty one, only with presence set to \
             full. Never past a scale that is being worked: there the \
             approach bed carries the warning instead.",
        ),
        SoundEntry::new(
            "Siren",
            &[Cue::new("events/police_siren")
                .volume(0.8)
                .pan(-0.5)
                .hold_s(3.0)],
            "A trooper is pulling you over. Signal, brake, and stop on the \
             shoulder. Ignoring it is logged as evasion and costs far more \
             than the ticket would have. On the road it starts quiet and \
             grows over the first few seconds as the cruiser comes up behind \
             you; the demo holds one steady level, so the rise is the part \
             you will only hear out there.",
        ),
        SoundEntry::new(
            "Inspection warning",
            &[Cue::new("events/inspection_warning").volume(0.7)],
            "You are being looked at for something other than speed: visible \
             damage, no chains inside a chain control, or following far too \
             close.",
        ),
        SoundEntry::new(
            "Scale warning",
            &[Cue::new("events/weigh_station_warning").volume(0.7)],
            "An open weigh station is ahead, and the full spoken notice -- \
             distance, name, the exit key -- follows right behind it. Its \
             own low thump-then-beep, not the inspection cue, so the scale \
             is unmistakable before a word is spoken.",
        ),
        SoundEntry::new(
            "Scale green light",
            &[Cue::new("events/scale_green").volume(0.8)],
            "A weigh-in-motion transponder cleared this truck as it \
             approached an open scale: keep rolling, no exit needed. Follows \
             right behind the open-scale notice, never instead of it.",
        )
        .when(
            "A weigh station transponder only -- the fleet issues one \
             free at career level 4, or an owner-operator can subscribe from \
             Business status. Without one, every open scale still demands \
             every truck pull in.",
        ),
        SoundEntry::new(
            "Scale red light",
            &[Cue::new("events/scale_red").volume(0.7)],
            "A weigh-in-motion transponder called this truck in anyway: \
             signal for the scale exit and pull in, the same as any driver \
             without a transponder. Compliant trucks are still red-lighted \
             sometimes, and an overweight load always is.",
        )
        .when(
            "A weigh station transponder only -- the fleet issues one \
             free at career level 4, or an owner-operator can subscribe from \
             Business status.",
        ),
        SoundEntry::new(
            "Weigh station",
            // Deliberately louder and longer than the road plays it. This bed
            // is the quietest thing in the catalog by a wide margin -- a flat
            // ambience with no attack, sitting around -33 dBFS where the
            // median cue is -21 -- and on the road that is right, because it
            // works by swelling against engine and tyre noise. Demonstrated
            // in a silent menu at the road's own level it reads as nothing
            // happening at all (Shane, 2026-08-15: "I press enter on it and I
            // get silence"). The screen's whole job is to let a player learn
            // the cue before it matters, so here it plays above the road's
            // ceiling and holds long enough to register as a sound rather
            // than a hiss.
            &[Cue::new("poi/weigh_station_lane").volume(1.0).hold_s(5.0)],
            "The bed that swells as you come up on an open scale. An open \
             scale must be pulled into; blowing past one is its own stop. On \
             the road it comes up under the engine rather than over it, so \
             it is quieter there than it is here.",
        ),
        SoundEntry::new(
            "Spike strip",
            &[Cue::new("events/spike_strip").volume(1.0)],
            "The end of a pursuit. If you are hearing this, running from the \
             lights has already gone as badly as it can go.",
        ),
        SoundEntry::new(
            "CB chatter",
            &[Cue::new("events/cb_radio_chatter")],
            "Other drivers passing on what they have seen: enforcement, \
             wrecks, work zones. It says how sure it is, it is sometimes out \
             of date, and it never claims the road is clear.",
        ),
    ],
};

const LOAD: SoundCategory = SoundCategory {
    name: "The load",
    entries: &[
        SoundEntry::new(
            "Surge",
            &[Cue::new("vehicle/liquid_wash").volume(0.55).hold_s(3.0)],
            "Liquid running back and forth inside a tank trailer. It builds \
             while you brake or accelerate and it pushes the truck after you \
             have stopped doing whatever started it.",
        )
        .when("Liquid bulk freight in a tank trailer only."),
        SoundEntry::new(
            "Surge strike",
            &[Cue::new("vehicle/liquid_hit").volume(0.85)],
            "The load hitting the front or back of the tank. It shoves the \
             truck along its length, which is why a smooth bore tank is \
             braked early and gently rather than late and hard.",
        )
        .when("Liquid bulk freight in a tank trailer only."),
        SoundEntry::new(
            "Surge strike, sideways",
            &[Cue::new("vehicle/liquid_hit_lateral").volume(0.85)],
            "The load hitting the side of the tank. It has its own voice, \
             separate from the fore-and-aft strike, because it means \
             something different: this is the one that rolls trucks. It \
             arrives after you have already turned or changed lanes.",
        )
        .when("Liquid bulk freight in a tank trailer only."),
    ],
};

pub const CATALOG: &[SoundCategory] = &[LANE, AIR, ENGINE_BRAKE, RAMPS, HAZARDS, ENFORCEMENT, LOAD];

/// Every entry, in catalog order.
pub fn catalog_entries() -> impl Iterator<Item = &'static SoundEntry> {
    CATALOG.iter().flat_map(|category| category.entries.iter())
}

/// The catalog entry with this canonical spoken noun, or `None`.
///
/// A lookup one caller (the S4 ladder's earcon playback, the app shell)
/// needs at runtime: it knows a cue only by the name it teaches under
/// (`speech_pacing.LADDER_EARCONS`), and the recipe -- key, volume, pan
/// -- lives here so the drive and the Learn game sounds screen can never
/// play the same cue two different ways.
pub fn entry_by_name(name: &str) -> Option<&'static SoundEntry> {
    catalog_entries().find(|entry| entry.name == name)
}

/// Every sound key the catalog plays, fallbacks included.
pub fn catalog_keys() -> std::collections::BTreeSet<&'static str> {
    let mut keys = std::collections::BTreeSet::new();
    for entry in catalog_entries() {
        for cue in entry.plays {
            keys.insert(cue.key);
            if !cue.fallback.is_empty() {
                keys.insert(cue.fallback);
            }
        }
    }
    keys
}

// What is deliberately not taught, and why. An exclusion is a decision on the
// record, not a gap: the completeness test fails on any played cue that is
// neither catalogued above nor listed here. A trailing "/*" excludes a whole
// folder.
//
// vehicle/road is in NEITHER list as a plain bed -- it is catalogued once, as
// the road lean, because what teaches a player something is its pan.
pub const SELF_EXPLANATORY: &[(&str, &str)] = &[
    // Listed one by one rather than as "engine/*": the jake ring lives in the
    // same folder and IS taught, and a folder glob here would mark it excluded
    // and taught at once.
    ("engine/idle", "It is an engine and it sounds like one."),
    (
        "engine_classic/idle",
        "The same engine, in its earlier voice.",
    ),
    (
        "engine/low",
        "As the idle loop: an engine at an engine speed.",
    ),
    ("engine/mid", "As the idle loop."),
    ("engine/midhigh", "As the idle loop."),
    ("engine/high", "As the idle loop."),
    (
        "engine/start",
        "An engine starting, immediately after you started it.",
    ),
    (
        "engine/shutdown",
        "An engine stopping, immediately after you stopped it.",
    ),
    (
        "engine/jake_1600_synth",
        "The classic jake voice: the same three staged entries play it when \
         Settings, Audio has Engine brake voice set to classic, through the \
         same key-resolution routing the drive uses. Not a second cue.",
    ),
    ("weather/*", "Rain, wind, snow and thunder name themselves."),
    ("ambient/*", "Scene, not a cue: no decision attached."),
    ("music/*", "Songs."),
    (
        "ui/*",
        "Menu feedback, learned in the first ten seconds of the main menu.",
    ),
    (
        "radio/fm_hiss_loop",
        "Static means weak signal to anyone who has owned a radio, and the \
         station dropping is spoken aloud when it happens.",
    ),
    (
        "radio/picket",
        "The fringe flutter, same reason as the hiss bed.",
    ),
    (
        "radio/static_burst",
        "Plays under a spoken line that already explains it.",
    ),
    (
        "vehicle/road_joint",
        "Pavement seams: texture, not a decision.",
    ),
    ("vehicle/truck_door", "A door."),
    ("vehicle/fuel_pump", "A fuel pump, at a fuel pump."),
    ("vehicle/reverse", "A backup beeper while backing up."),
    ("vehicle/horn", "The player is holding the horn key."),
    (
        "vehicle/brake_squeal",
        "It means you braked hard, which you know.",
    ),
    (
        "vehicle/brake_hiss_bed",
        "The air letting off after you released the brake pedal.",
    ),
    (
        "vehicle/gear_shift",
        "A gear change in a truck that is changing gear.",
    ),
    ("vehicle/shift_manual", "Banked gear changes, same reason."),
    ("vehicle/shift_auto", "Banked gear changes, same reason."),
    (
        "traffic/car_pass",
        "A vehicle going past sounds like a vehicle going past.",
    ),
    ("traffic/box_truck_pass", "As the car pass."),
    ("traffic/semi_pass", "As the car pass."),
    ("traffic/pickup_pass", "As the car pass."),
    ("traffic/motorcycle_pass", "As the car pass."),
    ("traffic/bus_pass", "As the car pass."),
    ("traffic/tractor_pass", "As the car pass."),
    // Cross traffic at a ramp terminal drives through in front of the
    // stopped truck: same reasoning as the passes, a vehicle crossing
    // sounds like a vehicle crossing, and the terminal callout has
    // already named the intersection it belongs to.
    (
        "traffic/car_cross",
        "A vehicle crossing in front sounds like one.",
    ),
    ("traffic/box_truck_cross", "As the car cross."),
    ("traffic/semi_cross", "As the car cross."),
    ("traffic/pickup_cross", "As the car cross."),
    ("traffic/motorcycle_cross", "As the car cross."),
    ("traffic/bus_cross", "As the car cross."),
    ("traffic/tractor_cross", "As the car cross."),
    (
        "poi/facility_gate",
        "Ambient bed for a place the game has already named.",
    ),
    (
        "poi/rest_stop_night",
        "Ambient bed for a place the game has already named.",
    ),
    (
        "facility/dock_gate",
        "Menu feedback at a facility, not a road cue.",
    ),
    (
        "poi/dock_and_deliver",
        "Menu feedback at a facility, not a road cue.",
    ),
];

/// Whether `key` is deliberately left out of the catalog.
pub fn is_excluded(key: &str) -> bool {
    if SELF_EXPLANATORY.iter().any(|(k, _)| *k == key) {
        return true;
    }
    let folder = key.split_once('/').map(|(f, _)| f).unwrap_or(key);
    let glob = format!("{folder}/*");
    SELF_EXPLANATORY.iter().any(|(k, _)| *k == glob)
}

#[cfg(test)]
mod tests {
    //! The learn-sounds catalog: every entry plays something real and says
    //! what it means.
    //!
    //! The Python file's asset-resolution sweeps (`_resolves`, the `ast`
    //! scan of every string literal in `src/`, the ontology/CHANGELOG/help
    //! text reads) walk the Python source tree and the loose sound tree;
    //! those stay Python until the game crate owns asset lookup. The data
    //! invariants are all pinned here.
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn test_catalog_has_categories_with_entries() {
        assert!(!CATALOG.is_empty(), "the catalog is empty");
        for category in CATALOG {
            assert!(!category.name.is_empty(), "a category has no name");
            assert!(
                !category.entries.is_empty(),
                "{} has no entries",
                category.name
            );
        }
    }

    #[test]
    fn test_every_entry_names_itself_plays_something_and_explains_itself() {
        for entry in catalog_entries() {
            assert!(!entry.name.trim().is_empty(), "an entry has no name");
            assert!(!entry.plays.is_empty(), "{} plays nothing", entry.name);
            assert!(
                !entry.meaning.trim().is_empty(),
                "{} has no meaning text",
                entry.name
            );
        }
    }

    #[test]
    fn test_lane_category_teaches_the_edge_ladder_in_order() {
        let lane = CATALOG
            .iter()
            .find(|c| c.name == "Lane and steering")
            .unwrap();
        let names: Vec<&str> = lane.entries.iter().map(|e| e.name).collect();
        let index = |n: &str| names.iter().position(|x| *x == n).unwrap();
        assert!(index("Rumble strip, clipped") < index("Rumble strip"));
        assert!(index("Rumble strip") < index("Off the pavement"));
    }

    // Entries where the side is a property of the truck's position, not of the
    // event: whichever side of the lane you are on, or whichever side a police
    // vehicle went by on, both are ordinary. Demoing one of them teaches half the
    // cue. Turn left, turn right and the siren are deliberately NOT here -- their
    // side IS the information.
    const BOTH_SIDES_ENTRIES: &[&str] = &[
        "The road lean",
        "Rumble strip, clipped",
        "Rumble strip",
        "Off the pavement",
        "Lane line crossed",
        "Lane locator",
        "Curve chime",
        "Signal tone",
        "Police car going by",
    ];

    #[test]
    fn test_directional_entries_demo_both_sides() {
        for name in BOTH_SIDES_ENTRIES {
            let entry = entry_by_name(name).unwrap();
            let mut pans: Vec<f64> = entry.plays.iter().map(|c| c.pan).collect();
            pans.sort_by(|a, b| a.partial_cmp(b).unwrap());
            assert!(
                pans[0] < 0.0 && 0.0 < pans[pans.len() - 1],
                "{name} must demo left and right"
            );
        }
    }

    const EXPECTED_CATEGORIES: &[&str] = &[
        "Lane and steering",
        "Air and brakes",
        "Engine brake, speed and shifting",
        "Ramps and stop bars",
        "Hazards and the road",
        "Enforcement",
        "The load",
    ];

    #[test]
    fn test_all_seven_categories_are_present_in_order() {
        let names: Vec<&str> = CATALOG.iter().map(|c| c.name).collect();
        assert_eq!(names, EXPECTED_CATEGORIES);
    }

    #[test]
    fn test_the_dodge_outcome_ships_as_a_learnable_success_fail_pair() {
        // R14: an earcon that reports an outcome ships as a distinct success/fail
        // pair, both learnable. Terse mode leans on the hazard-clear chime as the
        // whole 'you cleared it' confirmation, so its opposite -- the collision --
        // must be catalogued alongside it, not left as an implicit sound.
        let keys = catalog_keys();
        assert!(keys.contains("events/hazard_clear"));
        assert!(keys.contains("vehicle/collision"));
        // Neither half may quietly fall back to the "self-explanatory" exclusion.
        assert!(!is_excluded("vehicle/collision"));
        assert!(!is_excluded("events/hazard_clear"));
    }

    #[test]
    fn test_no_entry_name_repeats_across_the_catalog() {
        let names: Vec<&str> = catalog_entries().map(|e| e.name).collect();
        let unique: HashSet<&str> = names.iter().cloned().collect();
        assert_eq!(names.len(), unique.len(), "two entries share a name");
    }

    #[test]
    fn test_held_cues_declare_a_duration_and_one_shots_do_not_linger() {
        for entry in catalog_entries() {
            for cue in entry.plays {
                assert!(cue.hold_s >= 0.0);
                assert!(
                    cue.hold_s <= 6.0,
                    "{} holds {} too long",
                    entry.name,
                    cue.key
                );
            }
        }
    }

    #[test]
    fn test_the_emergency_brake_entry_declares_a_fallback() {
        // vehicle/ebrake ships only in the licensed overlay; a clean clone must
        // still hear something rather than learning that the cue is silent.
        let entry = entry_by_name("Emergency brake").unwrap();
        let cue = entry.plays[0];
        assert_eq!(cue.key, "vehicle/ebrake");
        assert_eq!(cue.fallback, "vehicle/brake_air");
    }

    #[test]
    fn test_every_exclusion_carries_a_reason() {
        for (key, reason) in SELF_EXPLANATORY {
            assert!(
                !reason.trim().is_empty(),
                "{key} is excluded with no reason given"
            );
        }
    }

    #[test]
    fn test_nothing_is_both_taught_and_excluded() {
        let both: Vec<&str> = catalog_keys()
            .into_iter()
            .filter(|k| is_excluded(k))
            .collect();
        assert!(both.is_empty(), "catalogued and excluded at once: {both:?}");
    }

    #[test]
    fn test_a_folder_glob_excludes_the_whole_folder() {
        assert!(is_excluded("weather/rain_loop"));
        assert!(is_excluded("music/open_road"));
        assert!(!is_excluded("engine/jake_1600"));
        assert!(is_excluded("engine/idle"));
    }

    // Entries whose cue a setting can silence, delay or change the meaning of.
    // Nothing in the data says so -- the gating lives at the call site -- so this
    // list is kept by hand: catalogue a cue that a setting governs, and add its
    // name here in the same change.
    const SETTINGS_GATED_ENTRIES: &[&str] = &[
        "The road lean",
        "Rumble strip, clipped",
        "Rumble strip",
        "Off the pavement",
        "Back in the lane",
        "Lane locator",
        "Curve chime",
        "Overspeed chime",
        "Gear grind",
        "Police car going by",
    ];

    #[test]
    fn test_every_settings_gated_entry_says_when_it_sounds() {
        for name in SETTINGS_GATED_ENTRIES {
            let entry = entry_by_name(name)
                .unwrap_or_else(|| panic!("{name} is no longer in the catalog; fix this list"));
            assert!(
                !entry.when.trim().is_empty(),
                "{name} only sounds under some settings, so it must say which. \
                 A player told a cue means one thing, whose settings mean it means \
                 another, has been taught something false."
            );
        }
    }

    #[test]
    fn test_the_enforcement_entries_match_what_the_road_plays() {
        // The warning and the pass are different cues and must stay so.
        //
        // The catalog once taught the pass as the thing "heard before it can see
        // you". It is not: it fires a twentieth of a mile PAST the post. The cue
        // that arrives first is the marker, and these two entries are only worth
        // having if each keeps the recipe of the thing it names.
        //
        // The road's own constants (driving_siren.SIGNATURE_KEY /
        // PASS_MARKER_LEAD_S, driving_enforcement.PASS_BASE_VOLUME / PASS_PAN)
        // are pinned by value here until the states port lands.
        const SIGNATURE_KEY: &str = "enforcement/signature";
        const PASS_MARKER_LEAD_S: f64 = 0.2;
        const PASS_BASE_VOLUME: f64 = 0.7;
        const PASS_PAN: f64 = 0.55;

        let enforcement = CATALOG.iter().find(|c| c.name == "Enforcement").unwrap();
        let by_name = |n: &str| enforcement.entries.iter().find(|e| e.name == n).unwrap();

        let marker = by_name("Enforcement marker");
        let keys: Vec<&str> = marker.plays.iter().map(|c| c.key).collect();
        assert_eq!(keys, vec![SIGNATURE_KEY]);
        assert_eq!(
            marker.plays[0].volume, 0.75,
            "the marker's own level in _play_enforcement_marker"
        );
        assert_eq!(marker.plays[0].pan, 0.0, "the pre-post marker is centered");

        let passing = by_name("Police car going by");
        assert_eq!(
            passing.plays.len() % 2,
            0,
            "the pass is marker-then-vehicle pairs"
        );
        for pair in passing.plays.chunks(2) {
            let (lead, behind) = (pair[0], pair[1]);
            assert_eq!(
                lead.key, SIGNATURE_KEY,
                "the marker leads the whoosh, never the other way"
            );
            assert_eq!(behind.key, "traffic/trooper_pass");
            assert!(((behind.delay_s - lead.delay_s) - PASS_MARKER_LEAD_S).abs() < 1e-3);
            assert_eq!(
                lead.pan, behind.pan,
                "both halves of one pass come from one side"
            );
            assert_eq!(lead.pan.abs(), PASS_PAN);
            assert_eq!(lead.volume, PASS_BASE_VOLUME);
            assert_eq!(behind.volume, PASS_BASE_VOLUME);
        }
    }

    #[test]
    fn test_the_jake_ring_is_catalogued_by_hand() {
        // Built by f-string at the call site, so the Python scanner cannot see it.
        // Catalogued explicitly, which is why this asserts rather than trusts.
        assert!(catalog_keys().iter().any(|k| k.starts_with("engine/jake_")));
    }

    #[test]
    fn test_descriptions_stay_player_facing() {
        let banned = [
            "src/",
            ".py",
            "CH_",
            "audio.play",
            "TODO",
            "FIXME",
            "changelog",
            "pytest",
        ];
        for entry in catalog_entries() {
            let text = format!("{} {}", entry.meaning, entry.when);
            for word in banned {
                assert!(
                    !text.contains(word),
                    "{} says {word:?} to the player",
                    entry.name
                );
            }
        }
    }

    fn entry(name: &str) -> &'static SoundEntry {
        entry_by_name(name).unwrap()
    }

    #[test]
    fn test_the_road_lean_is_taught_as_a_cue_you_steer_toward() {
        // The lane guide is a pursuit instrument and the rumble strip is not.
        //
        // Its target is `curve_steer - offset` (sim/lane_guidance), so drifting
        // right leans the bed left and following the lean is what recovers the
        // lane -- the opposite of the rumble strip, which sounds from the side
        // being drifted toward and is steered away from. Prose is the only place
        // that difference can live, and getting it backwards would teach a blind
        // driver to steer off the road, so it is pinned here rather than trusted.
        let lean = entry("The road lean");
        assert!(lean.meaning.contains("Steer toward the lean"));
        for rung in ["Rumble strip, clipped", "Rumble strip"] {
            assert!(
                entry(rung).meaning.to_lowercase().contains("away"),
                "{rung} must keep telling the player to steer away from it, \
                 or the two opposite conventions blur together"
            );
        }
    }

    #[test]
    fn test_the_weigh_station_bed_demos_louder_than_the_road_plays_it() {
        // The one cue whose road level makes it undemonstrable.
        //
        // Mixed to sit *under* engine and tyre noise, it works on the road by
        // swelling against them. Played in a silent menu at that same level it is a
        // featureless hiss and reads as nothing happening (Shane, 2026-08-15: "I
        // press enter on it and I get silence"). The Learn game sounds screen has to
        // play it above its road ceiling to demonstrate it at all, so that is
        // pinned here rather than left to drift back down.
        //
        // driving_enforcement.SCALE_BED_OPEN_MAX_VOLUME, pinned by value until
        // the states port lands.
        const SCALE_BED_OPEN_MAX_VOLUME: f64 = 0.55;

        let entry = catalog_entries()
            .find(|e| e.plays.iter().any(|c| c.key == "poi/weigh_station_lane"))
            .unwrap();
        let cue = entry
            .plays
            .iter()
            .find(|c| c.key == "poi/weigh_station_lane")
            .unwrap();

        assert!(
            cue.volume > SCALE_BED_OPEN_MAX_VOLUME,
            "the weigh station bed must demo above the loudest the road ever \
             plays it ({SCALE_BED_OPEN_MAX_VOLUME}), or the screen teaches the \
             player that a real cue is silent"
        );
        // Long enough to register as a sound rather than a blip of hiss.
        assert!(cue.hold_s >= 5.0);
    }

    #[test]
    fn test_the_lane_guide_tone_is_learnable_like_every_other_cue() {
        // R14: a sound a player cannot look up is information removed.
        let matched = catalog_entries()
            .find(|e| e.plays.iter().any(|c| c.key == "guide/lane_guide_tone"))
            .expect("the guide tone is not in Learn game sounds");
        // And it says it is the non-default, so a player auditioning sounds is
        // not left wondering why they have never heard it.
        assert!(matched.meaning.to_lowercase().contains("default"));
    }
}
