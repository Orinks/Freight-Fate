//! The driving state (port of `freight_fate/states/driving.py`, the
//! "compatibility facade" that composed sixteen mixins onto `State`).
//!
//! # Shape of the port
//!
//! Python's `DrivingState` was one fat object partitioned only by file: every
//! mixin read and wrote `self.<attr>` on state owned by `__init__` or by other
//! mixins. Here it is one struct -- [`DrivingState`], every field listed and
//! grouped by the Python module that initialises or owns it -- and one
//! `impl DrivingState` block per former mixin file (`driving_controls.rs`,
//! `driving_updates.rs`, ...). There is no dynamic dispatch to preserve; the
//! mixins were namespaces.
//!
//! Three things are not fields:
//!
//! * `self.truck` and `self.weather` -- the Rust `Trip` owns its
//!   `TruckState` and `WeatherSystem`, so they are `self.trip.truck` and
//!   `self.trip.weather` ([`DrivingState::truck`] / [`DrivingState::weather`]
//!   are the short forms). Python aliased one object from two places.
//! * `self.hos` -- an alias of `profile.hos`; use
//!   [`crate::states::driving_core::hos_of`] / `hos_mut_of`.
//! * `self._radio_backend` -- built per call by
//!   [`DrivingState::with_radio_backend`].
//!
//! The `State` impl forwards to methods the mixin modules provide; until a
//! mixin lands, [`pending`] carries a temporary stub for each such method so
//! the crate builds. A mixin task deletes its stubs from `pending` as it
//! implements them and touches nothing else here.
//!
//! Submodules: `driving/init.rs` (`new`), `driving/snapshot.rs` (save and
//! resume), `driving/lifecycle.rs` (enter/exit and the facade's own
//! helpers).

mod init;
mod lifecycle;
mod snapshot;

use std::collections::{HashMap, HashSet, VecDeque};

use ff_core::data::curves::RouteCurve;
use ff_core::data::world_models::Route;
use ff_core::models::jobs::Job;
use ff_core::pyrandom::PyRandom;
use ff_core::radio::RadioState;
use ff_core::sim::cross_traffic::CrossTraffic;
use ff_core::sim::enforcement_observe::Observation;
use ff_core::sim::lane::LaneKeeping;
use ff_core::sim::lane_guidance::LaneGuidance;
use ff_core::sim::pedal_latch::PedalLatch;
use ff_core::sim::trip::Trip;
use ff_core::sim::trip_models::RoadStop;
use ff_core::sim::vehicle::TruckState;
use ff_core::sim::weather::WeatherSystem;

use crate::app::GameContext;
use crate::discord_presence::PresenceState;
use crate::states::base::{InputEvent, State};
use crate::states::driving_core::{
    CurveRun, Instructor, PendingAmbient, PendingSound, RigBuffs, SirenLoop,
};

pub use snapshot::ACTIVE_TRIP_DEADLINE_MODEL;

/// `_destination_exit_cache`: the position the scan was computed at, and
/// what it found -- `(miles ahead, exit label, spoken phrase)`, or `None`
/// where there is no destination exit to take.
pub type DestinationExitScan = (f64, Option<(f64, String, String)>);

/// Live truck control with a fully audio HUD.
///
/// Field groups are headed by the Python module that initialises them; a
/// group's fields are listed in the order `__init__` (or the module's own
/// `_reset_*`/`_*_init` helper) assigned them. Leading underscores are
/// dropped (`self._cruise_mph` -> `cruise_mph`).
pub struct DrivingState {
    // ---- driving.py: identity -----------------------------------------------------------
    pub job: Job,
    /// The route the drive was dispatched on. `trip.route` is the active
    /// one and differs on a surface or departure street chain.
    pub route: Route,
    /// `DRIVE_PHASE_PICKUP` / `DRIVE_PHASE_DELIVERY` / `DRIVE_PHASE_SCHOOL`.
    pub phase: &'static str,
    pub trip_seed: i64,
    pub resumed: bool,
    /// The trip, which owns the truck and the weather (`self.trip.truck`,
    /// `self.trip.weather`).
    pub trip: Trip,
    /// Bumped every time `trip` is replaced (surface/departure chain swaps);
    /// the Python `id(self.trip)` the turn latches compared against.
    pub trip_generation: u64,
    pub start_damage: f64,
    // Trip-start wear, for "this run added..." deltas at settlement
    // (mid-trip saves re-sync the profile, so the profile can't provide
    // these once the trip is underway).
    pub start_tire_wear: f64,
    pub start_brake_wear: f64,
    pub start_engine_wear: f64,
    // Rig-care buffs (quick lube, tire rotation) hold for the rest of
    // the trip and die with it -- keyed by buff group, see data/buffs.py.
    pub rig_buffs: RigBuffs,
    pub weather_source_real: bool,
    pub live_weather_controls_calendar: bool,
    pub traffic_source_real: bool,
    pub parking_source_real: bool,
    pub lane: LaneKeeping,

    // ---- driving.py: music and radio (read by driving_updates) ------------------------
    pub day_music_sequence: Vec<String>,
    pub night_music_sequence: Vec<String>,
    pub music_night: bool,
    pub radio: RadioState,
    // Station rotation: per-station shuffled song order, with break slots
    // (host/id/ad) every few songs on the stations that have a live host.
    pub radio_station_id: String,
    pub radio_playlist: Vec<String>,
    pub radio_track_index: usize,
    pub radio_elapsed_s: f64,
    pub radio_break_queue: Vec<String>,
    pub radio_break_pos: usize,
    pub radio_break_count: usize,
    pub radio_tracks_since_break: usize,
    // Personal playlist stations: where each playlist left off this drive,
    // and a hold between entries so neither a fade-in nor a stream still
    // connecting ever reads as a finished track.
    pub playlist_positions: HashMap<String, usize>,
    pub playlist_wait_s: f64,
    pub playlist_stream_tries: u32,
    pub playlist_stream_skips: u32,
    // Which playlists have already said they have nothing that will play,
    // so a broken folder explains itself once instead of every 30 seconds.
    pub playlist_silence_spoken: HashSet<String>,
    // Reception: signal re-checked on a slow cadence while driving so
    // ranged stations fade with distance and drop past their contour.
    pub radio_signal_timer: f64,
    // Re-tune cadence for a real stream that went silent (a dock bed
    // borrowed the music channel, or the connection stalled mid-drive).
    pub radio_reconnect_timer: f64,
    // The song the tuned stream last reported (ICY StreamTitle), polled on
    // the reception tick; None when nothing is streaming or the station
    // sends no song information. Shift+Y speaks it, the Tab radio screen
    // and the drivers board line carry it.
    pub radio_now_playing: Option<String>,
    // The radio draws power from the engine: last power state, so the
    // per-frame sync starts or stops playback only on the transition.
    pub radio_powered: bool,
    pub radio_signal_factor: f64,
    // FM fringe renderer state: cached signal/dial from the reception
    // tick, the hiss-bed flag, and the picket scheduler (its own seeded
    // rng -- flutter is cosmetic but must replay deterministically).
    pub radio_fringe_signal: Option<f64>,
    pub radio_fringe_freq: f64,
    pub fringe_bed_active: bool,
    pub radio_picket_duck: f64,
    pub picket_duck_s: f64,
    pub picket_wait_s: f64,
    pub fringe_rng: PyRandom,
    /// The first-run walkthrough, or a driving-school lesson; `None` once
    /// `tutorial_done`.
    pub tutorial: Option<Box<dyn Instructor>>,

    // ---- driving.py: hours, fatigue, hazards (driving_updates / driving_events) -------
    pub hos_fine_count: i64, // escalates with each failed inspection
    pub enforcement_events: HashSet<String>,
    pub out_of_service_count: i64,
    pub drowsy_said: bool,
    pub severe_said: bool,
    pub fatigue_cue_gm: f64, // game minutes since the last drowsy cue
    pub microsleep_deadline: Option<f64>, // reaction window, real seconds
    pub microsleep_gm: f64,  // game minutes since the last nod
    pub microsleep_cooldown_gm: f64,
    pub microsleep_misses: i64, // consecutive nods drifted off the road
    pub hazard_deadline: Option<f64>,
    // What is actually pending, in the order it armed. A second hazard
    // arming while one is still live folds its name in here instead of
    // clobbering the first (see _handle_trip_event's HAZARD branch), so
    // the resolution line can name everything that just cleared.
    pub hazard_names: Vec<String>,
    pub horn_scare_tried: bool,
    pub hazard_slow_hint_said: bool,
    pub automatic_braking_announced: bool,
    pub automatic_braking_escalated: bool,
    // The service application the hazard assist is holding (0.0 = off the
    // pedal), whether it has earned the emergency application on top, and
    // the measurements that decide it. Held rather than re-decided every
    // frame: the air system charges a whole brake application every time
    // the pedal rises, and the assist's own braking retreats the very
    // threshold that engaged it.
    pub aeb_brake: f64,
    pub aeb_emergency: bool,
    pub aeb_hold_s: f64,
    pub aeb_losing_s: f64,
    pub aeb_decel_mps2: f64,
    pub aeb_last_speed_mps: Option<f64>,
    pub last_event_message: String, // last spoken route announcement, for replay
    pub speed_announce_timer: f64,
    pub last_announced_mph: f64,
    // Compliance grace after a posted-limit drop: braking time before
    // strikes accrue, earned only while actually slowing.
    pub enforced_limit_prev: Option<f64>,
    pub limit_drop_grace_s: f64,
    // The demoted (ROUTE-queued) zone-entry line may lag its boundary;
    // the throttle-held grace collapse must not arm until it has had
    // time to actually be spoken (research doc, R1's coupled invariant).
    pub limit_drop_throttle_exempt_s: f64,
    // Dash overspeed alert: armed while over the limit, chiming on an
    // interval until the truck settles back under.
    pub overspeed_active: bool,
    pub overspeed_chime_timer: f64,
    // Congestion badges: both kinds of slow inside one trip earns a nod.
    pub construction_seen: bool,
    pub traffic_seen: bool,
    pub brake_squeal_cooldown_s: f64, // hot-brake squeal cue spacing
    pub hydro_active: bool,           // spoken hydroplane warning edge tracking
    pub jake_slip_active: bool,       // spoken jake-slip warning edge tracking
    // The cylinder selector's position, like the real dash switch: J
    // engages at whatever stage was last chosen. Full retard by default
    // -- the setting every driver leaves it on until ice says otherwise.
    pub jake_selected_stage: i32,
    pub chains_fast_active: bool, // spoken chains-over-speed warning edge tracking
    pub chain_law_warned: HashSet<(i64, i64)>, // (area, level) spoken warnings
    pub chain_law_cited: HashSet<(i64, i64)>, // checkpoint rolls already taken
    // Curve management: whether a hot-entry slip warning has been spoken
    // for the current curve.
    pub curve_slip_active: bool,

    // ---- driving.py: enforcement counters and the live stop (driving_updates) ----------
    // Trooper pull-overs: a strike inside a patrol window may get you stopped
    // for an immediate ticket, separate from the silent at-delivery strikes.
    pub speeding_tickets: i64,
    pub ticket_fines_paid: f64,
    // No-engine-brake zones: town noise ordinances around route cities
    // (driving_engine_brake).
    pub jake_zone_fines: i64, // citations this trip; escalates the fine
    pub jake_fines_paid: f64,
    pub jake_violation_deadline_s: Option<f64>, // grace after the warning
    pub jake_citation_latched: bool,            // one citation per continuous engagement
    // Zones whose one warning has already been spent this trip; a second
    // engagement in the same town is cited without a fresh grace window.
    pub jake_zone_grace_used: HashSet<String>,
    pub jake_zone_warned_key: Option<String>, // approach callout latch
    pub assist_zone_cue_key: Option<String>,  // once-per-zone assist-release cue
    /// `None` | `PULL_OVER_LIGHTS` | `PULL_OVER_STOPPING`.
    pub pull_over: Option<String>,
    pub pull_over_start_mi: f64,
    pub pull_over_signaled: bool,
    pub pull_over_over: f64,  // mph over the limit when clocked
    pub pull_over_limit: f64, // posted limit when clocked
    pub pull_over_kind: String,
    pub pull_over_title: String,
    pub pull_over_summary: String,
    pub pull_over_fine: f64,
    pub pull_over_reputation_hit: f64,
    pub pull_over_return: String,
    // Whether the violation happened inside roadwork, which doubles the fine.
    pub pull_over_construction_zone: bool,
    pub pull_over_warning_level: i64,
    pub failure_to_stop_count: i64,
    // Real seconds owed to the player before the stop is judged at all:
    // the spoken instruction plus reaction time. Nothing drains until it
    // has run out.
    pub pull_over_grace_s: f64,
    // How long the stop has stayed unresolved past the final warning.
    pub pull_over_forced_s: f64,
    // How long the deliberate run key has been held down.
    pub pursuit_hold_s: f64,
    // Ladder movement spoken during this trip, restated once at the
    // delivery summary so nothing about your standing is heard only
    // on a road the player has already left.
    pub record_events: Vec<String>,
    pub fatigue_events: i64, // run-off-road microsleeps this trip
    pub weigh_station_notice_key: String,
    // The half-mile "slow for the scale" nudge, latched separately so it
    // speaks once per announced scale and never re-fires on a re-approach.
    pub weigh_station_reminder_key: String,
    // A scale crossed with its own exit armed: judged after the exit watch
    // runs, later in the same frame, never on ramp speed alone.
    pub weigh_station_pending: Option<RoadStop>,
    // Weigh-in-motion verdicts for a transponder-equipped truck, keyed by
    // _weigh_station_key(stop): "green" or "red", rolled once at the
    // notice point in EnforcementWatchMixin._resolve_transponder_verdict
    // and read both by the bypass judgment and by the half-mile reminder.
    pub weigh_station_transponder_verdict: HashMap<String, String>,
    // Last retarder stage written to the transcript, so _trace_engine_brake
    // logs a CHANGE rather than a frame. -1 rather than 0: the first
    // observation is worth a line even if the jake starts down.
    pub traced_jake_stage: i32,
    pub unsafe_damage_stop_key: String,
    // Compliance tracker for the active stop: 0..1, judged from behavior
    // (signaling and slowing), not distance. Reset on every stop-ending path.
    pub pull_over_compliance: f64,    // seeded on begin
    pub pull_over_elapsed: f64,       // s since the lights came on (signal grace)
    pub pull_over_prev_mph: f64,      // last-tick speed, to classify accel vs decel
    pub pull_over_coast_s: f64,       // consecutive s with no braking and no accel
    pub pull_over_signal_boost: bool, // the one-time signal bump has fired
    pub pull_over_nosignal_hit: bool, // the one-time no-signal 1/4 hit has fired
    // The road-joint spacer used to draw from the shared patrol stream
    // about a hundred times a mile, so whether a trooper caught you came
    // down to how many joints had played -- frame timing, effectively, and
    // a reload re-rolled it. Ambience keeps its own stream, and there is
    // no longer a shared enforcement stream at all: every police decision
    // is a named, position-quantised seed (see sim/enforcement_posts.
    // post_seed), so nothing the audio layer does can consume it.
    pub road_texture_rng: PyRandom,

    // ---- driving_enforcement.py: `_enforcement_init` ---------------------------------
    pub siren: SirenLoop,
    // Continuous distance over the limit. This -- not a real-time hold --
    // is what a post reads as a speed. See _update_enforcement_watch.
    pub over_limit_mi: f64,
    // Continuous distance closed up on the vehicle ahead; same idea, and
    // read by the same kind of hold. See _accrue_following_gap.
    pub closed_up_mi: f64,
    pub enforcement_prev_mi: f64,
    pub passed_post_ids: HashSet<String>,
    pub marked_post_ids: HashSet<String>,
    // A tableau's two cues, each fired once: the siren some seconds
    // before the spot, and the stopped pair as you go by it.
    pub tableau_siren_ids: HashSet<String>,
    pub tableau_pass_ids: HashSet<String>,
    pub scale_bed_key: String,
    pub scale_bed_volume: f64,
    pub radio_cue_duck: f64,
    pub radio_cue_duck_s: f64,
    pub radio_cut_for_stop: bool,
    pub pending_sounds: Vec<PendingSound>,
    // Posts whose look was deferred because the cab was busy. They keep
    // their turn; nothing is silently dropped.
    pub deferred_post_ids: HashSet<String>,
    // The look itself, and the mile it was taken at: what makes the
    // deferral a postponement rather than a discard.
    pub held_observation: Option<(Observation, f64)>,
    // Miles each pacing unit has held station behind the truck.
    pub pacing_mi: HashMap<String, f64>,
    pub rescue_offered: bool,

    // ---- driving_damage.py --------------------------------------------------------------
    // Damage bands. The band itself is derived from damage_pct every
    // frame; what is trip-scoped is the last band ANNOUNCED (so an edge
    // speaks once) and the limp cap mid-wind-down. Both round-trip through
    // the snapshot -- a resume that re-announced limp mode, or snapped the
    // cap back to full speed, would be lying about the truck.
    pub damage_band: i32,
    // The deepest band this run reached, for settlement to grade against.
    pub worst_damage_band: i32,
    pub limp_cap_mph: Option<f64>,
    pub limp_cruise_said: bool,
    pub out_of_service_creep_s: f64,
    pub recovering: bool,
    // The highest cargo-condition rung already spoken, so each one warns
    // once. Trip-scoped and snapshotted like the damage band.
    pub cargo_cue_at: f64,
    // The coaching tail ("brake and corner gently from here") is teaching,
    // not news: it belongs on the first load-damage report of the episode,
    // and every escalation after it speaks only the new number and the
    // consequence (research doc R11). Snapshotted so a resume mid-episode
    // does not re-teach it.
    pub cargo_coaching_said: bool,

    // ---- driving_events.py: exits, ramps, the destination ---------------------------------
    pub signal_timer: f64,
    pub exit_stop: Option<RoadStop>, // active route exit
    // Stable proof that the player explicitly selected an optional sleep
    // stop with T. _exit_stop is not enough: destination approaches infer
    // it automatically, and a canceled signal can leave it populated.
    pub selected_stop_key: Option<String>,
    pub selected_stop_assist_armed: bool,
    pub selected_stop_assist_said: bool,
    pub selected_stop_assist_brake: f64,
    pub exit_signal_on: bool,
    pub exit_signal_canceled: bool,
    pub exit_lane_alignment: f64,
    pub exit_lane_prompt_said: bool,
    pub exit_lane_ready_said: bool,
    pub exit_commit_said: bool,
    pub exit_cancel_armed: bool,
    pub exit_right_hold_s: f64,
    pub exit_right_taps: i64,
    pub exit_tap_hint_said: bool,
    /// `set[float]` of the `EXIT_COUNTDOWN_MILESTONES_MI` already spoken.
    pub exit_countdown_said: Vec<f64>,
    pub ramp_mi: Option<f64>, // ramp distance left, once taken
    pub ramp_stop: Option<RoadStop>,
    pub ramp_end_said: bool,
    pub ramp_arrival_grace_s: f64,
    // How many times this drive has been carried past the destination
    // terminal at speed; a repeat miss earns the braking hint.
    pub ramp_terminal_miss_count: i64,
    // Ramp terminal control for the active ramp: what meets you where the
    // ramp joins the surface road, and the light's cycle state if a signal.
    // "signal" | "stop" | "yield" | "roundabout" | "none" | "" (no ramp)
    pub ramp_control: String,
    pub ramp_light_offset_s: f64, // seeded phase into the light cycle
    pub ramp_light_timer: f64,    // real seconds since the ramp was taken
    pub ramp_light_announced: bool,
    pub ramp_light_last_phase: String, // "red" | "yellow" | "green", once announced
    pub ramp_terminal_done: bool,
    pub ramp_waiting_at_light: bool,
    // Stopped at the sign with cross traffic rolling: the clear call is
    // waiting on the bubble's gap.
    pub ramp_waiting_at_sign: bool,
    // The living crossroad at a controlled terminal (sim.cross_traffic);
    // built per ramp by _begin_ramp_terminal, None between ramps.
    pub cross_bubble: Option<CrossTraffic>,
    pub ramp_creep_prompt_said: bool,
    pub ramp_gap_milestones_said: HashSet<i64>,
    pub ramp_bar_tick_timer: f64,
    pub bar_solid_on: bool, // the bar's continuous final-zone tone
    pub ramp_assist_said: bool,
    // The pedal route-transition assistance is currently holding for the
    // terminal, so it can follow the demand up without letting go and
    // re-making the application every few frames.
    pub ramp_assist_brake: f64,
    // Safety-call re-arm window (curve calls vs the Ctrl reflex).
    pub critical_curve: Option<RouteCurve>,
    pub critical_call_age_s: f64,
    pub critical_respeak_at: Option<f64>,
    pub destination_exit_taken: bool,
    // True only while the destination approach assist is actually shedding
    // for the arrival point. The zone keeper refuses to re-engage into it,
    // the way it already refuses on a ramp -- without that the keeper held
    // a street limit straight through the market gate.
    pub destination_arrival_active: bool,
    pub destination_assist_brake: f64,
    pub destination_chain_ahead: Option<bool>, // memo, see _destination_street_chain_ahead
    pub missed_destination_exit_said: bool,
    pub destination_exit_announced_key: String,
    pub destination_exit_response_s: f64,
    // Surface chain: after the destination ramp, the drive continues on
    // the facility's real street chain to the gate instead of a scripted
    // arrival. The highway trip is kept for records; the active trip
    // becomes the surface route.
    pub surface_chain: bool,
    pub highway_trip: Option<Trip>,
    // Departure chain: the mirror. A loaded run out of a chain-capable
    // origin facility starts on its streets and merges onto the highway.
    // Checked lazily on the first drive tick so restored mid-highway
    // saves are never pulled back onto the streets.
    pub departure_chain: bool,
    pub departure_checked: bool,
    // -1 so the first tick always resets, whatever leg a resumed
    // run starts on.
    pub ladder_leg_index: i64,
    // (position when computed, scan result) -- see _destination_exit_details
    pub destination_exit_cache: Option<DestinationExitScan>,

    // ---- driving_events.py / driving_speed_control.py: cruise and the keeper -----------
    pub cruise_mph: Option<f64>,
    // The rate-limited speed cruise is actually chasing this frame; it eases
    // from the engage speed up to _cruise_mph so a big resume error never
    // lands on the pedal at once. None whenever cruise is off.
    pub cruise_working_mph: Option<f64>,
    // What cruise ACTUALLY held this frame, after every cap, and the phrase
    // for why -- published by the loop so the status keys can answer with the
    // number the truck is on rather than the number the dial is set to. The
    // reason is empty when nothing named it (the weather cap, or nothing
    // capping at all). None whenever cruise is off, and until the loop has
    // run once in a fresh session.
    pub cruise_held_mph: Option<f64>,
    pub cruise_held_reason: String,
    pub cruise_throttle: f64,
    pub cruise_applied: f64,
    pub cruise_trim: f64,       // integral trim on top of the grade feed-forward
    pub cruise_jake_stage: i32, // retarder stages cruise itself commanded
    pub cruise_jake_cooldown_s: f64, // quiet time between those stage steps
    pub cruise_snubbing: bool,  // a service-brake snub is in progress
    pub pcc_phase: String,      // what the grade preview is doing, for the cue
    pub pcc_cue_s: f64,         // quiet time between preview cues
    pub climb_cue_said: bool,   // cruise has already owned up to this pull
    pub climb_cue_s: f64,       // quiet time between hand-back cues
    pub climb_beaten_s: f64,    // how long the grade has genuinely been winning
    pub descent_cue_s: f64,     // quiet time between descent-control cues
    // A trailer refused at the shipper: the yard swapped it, so the box
    // under the truck is sound and no scale house should say otherwise.
    pub trailer_refused: bool,
    pub nice_speed_mi: f64,   // distance held at a very particular speed
    pub jake_descent_mi: f64, // downgrade held on the engine alone
    pub radio_states_station: String, // station the state tally belongs to
    pub radio_states_held: HashSet<String>,
    pub cruise_descent_mph: Option<f64>, // interactive descent ceiling, while it lasts
    pub cruise_exit_mph: Option<f64>,
    pub cruise_curve_mph: Option<f64>,
    pub cruise_curve_end_mi: Option<f64>,
    // Sign of the steep grade already announced, so each hill is called out
    // once rather than every frame, and where the road profile was last read.
    pub grade_warned_sign: i32,
    pub grade_scan_mi: f64,
    // K arms one continuous speed-control session. The active controller
    // changes between adaptive cruise on open roads and the speed keeper in
    // restricted zones, while this target remembers what cruise should
    // resume at after the zone ends.
    pub speed_control_armed: bool,
    // Set while an armed session is held at a planned stop. An ARRIVAL --
    // a pickup or delivery gate, a planned rest stop -- is remembered but
    // must not re-engage on its own: it resumes when the player departs,
    // or when they arm it again by hand. A TRANSIT stop -- the light or
    // sign at the end of a ramp -- has no departure to wait for, so its
    // pause lifts itself once the stop has been honored and the truck is
    // rolling again.
    pub speed_control_paused_at_stop: bool,
    pub speed_control_transit_pause: bool,
    pub speed_control_stop_honored: bool,
    pub speed_control_target_mph: Option<f64>,
    pub acc_following: bool,
    pub acc_weather_gap_said: bool,
    pub acc_limit_capped: bool,
    pub acc_limit_cap_said: Option<f64>,
    pub acc_weather_cap_said: Option<f64>,
    // (end mile, limit, reason) of a restricted zone cruise has begun
    // slowing for -- a work zone or heavy traffic.
    pub construction_slowdown: Option<(f64, f64, String)>,
    pub acc_follow_cue_s: f64, // quiet window between "Traffic ahead" cues
    pub descent_control_active: bool,
    pub descent_limit_state: String,
    pub descent_capture_active: bool,
    pub assist_exit_slowing_said: bool,
    // Lane keeping on full grants the exit lane and takes the destination
    // exit without the driver touching anything. That is coherent, but
    // unattributed it reads as the exit taking itself -- which is exactly
    // what got reported. Name the automation at the point of confusion,
    // once each per run, then go back to the plain wording.
    pub lane_keeping_grant_said: bool,
    pub lane_keeping_takes_exit_said: bool,
    pub curve_assist_active: bool,
    pub curve_assist_cue_s: f64,
    // Whether the SLOWING cue was actually spoken for the run in progress.
    // The release line is paired to it, so an engagement that stayed quiet
    // (see the ramp case in driving_updates) never leaves a lone
    // "released" hanging with nothing before it.
    pub curve_assist_spoke: bool,
    pub transition_assist_active: bool,
    pub keeper_mph: Option<f64>,
    pub keeper_throttle: f64,
    pub keeper_zone: String,
    // The posted number the keeper last took its target from, so a street
    // that posts a HIGHER one can hand the keeper back up to street speed.
    pub keeper_zone_limit: Option<f64>,
    // The lower number ahead the keeper is easing for, and the say-once
    // latch for the posted-limit version of that cue.
    pub keeper_ease_said: Option<f64>,
    pub keeper_ease_target: Option<(f64, f64, String)>,
    // The service-brake snub the keeper is holding (0.0 = off the pedal),
    // and how long it has been out of authority with the truck still over
    // the number -- past which it owns up rather than riding it out.
    pub keeper_snub: f64,
    // And the mirror of that on the other side of the number: how long the
    // keeper has been flat out and still losing the grade, plus the
    // say-once latch and the per-hill cooldown for owning up to it.
    pub keeper_droop_s: f64,
    pub keeper_droop_said: bool,
    pub keeper_droop_cue_s: f64,
    pub keeper_overrun_s: f64,
    pub keeper_overrun_said: bool,

    // ---- driving_events.py / driving_pickup.py / driving_facility_gate.py: arrival ----
    pub arrival_stop_said: bool,
    pub arrival_full_stop_said: bool,
    pub arrival_menu_open: bool,
    pub gate_reminder_s: f64,
    // Facility gate misses (driving_facility_gate.py): the pre-gate speed
    // warning latch, the real-time reaction window it opens, and how many
    // loop-backs this trip has cost -- the count escalates the spoken help.
    pub gate_speed_warned: bool,
    pub gate_grace_s: f64,
    pub gate_miss_count: i64,

    // ---- driving_wrong_way.py ----------------------------------------------------------
    // Backing down a live road: route miles given up since reverse was
    // engaged somewhere it has no business being, and the distance the
    // last warning was spoken at. Per-stint, not saved -- a reloaded trip
    // is not still reversing.
    pub wrong_way_mi: f64,
    pub wrong_way_said_at: f64,

    // ---- driving_traffic_pass.py: `_reset_traffic_passes` ------------------------------
    // Which end of the truck each bubble vehicle was on last frame (the
    // relative mile), and which have already been given their whoosh.
    // Per-stint, not saved.
    pub traffic_pass_side: HashMap<String, f64>,
    pub traffic_passed_keys: HashSet<String>,
    pub traffic_pass_cooldown_s: f64,

    // ---- driving_lane_gap.py: `_reset_lane_gap` ----------------------------------------
    // The lane a completed change moved out of, and the vehicle that was
    // holding it. Per-stint, not saved: a reloaded trip is not mid-pass.
    pub lane_gap_watch: Option<i64>,
    pub lane_gap_prev_lane: Option<i64>,
    pub lane_gap_blocker_key: Option<String>,
    pub lane_gap_blocker_class: String,
    pub lane_gap_said_keys: HashSet<String>,
    pub lane_gap_cue_s: f64,

    // ---- driving_turns.py: `_reset_turn_state_for_trip` -------------------------------
    // Street corners: how many corners this run has cost, which escalates
    // the spoken help. The per-corner latches are rebuilt whenever the
    // trip's route changes (`turn_trip_id` vs `trip_generation`).
    pub turn_miss_count: i64,
    pub turn_trip_id: u64,
    pub turn_advised: HashSet<String>,
    pub turn_missed: HashSet<String>,
    pub turn_resolved: HashSet<String>,
    pub turn_grace_s: f64,

    // ---- driving.py: air, brakes, engine (driving_updates / driving_controls) ----------
    pub air_ready_said: bool,
    pub low_air_said: bool,
    pub spring_brake_said: bool,
    pub brake_lockout_cue_timer: f64,
    pub brake_air_hissed: bool, // rising-edge guard for the brake-apply hiss
    pub pending_low_air_buzzer: bool, // cold-start buzzer, held past the crank
    pub brake_peak_application: f64, // hardest press this application, shapes the release
    pub overrev_s: f64,         // continuous seconds at damaging RPM
    pub overrev_warn_due: f64,  // repeats push it out further

    // ---- driving.py: lanes, merges, hazards, ambient queue (driving_updates / events) ---
    // Discrete lanes: tap-change progress (assist off), closed-lane
    // policing, hazard-dodge context, and keep-right pressure.
    pub lane_change_target: Option<i64>,
    pub lane_change_timer: f64,
    pub lane_signal_timer: f64,
    pub merge_deadline: Option<f64>,
    // Miles of acceleration lane still ahead after pulling out of a
    // facility. None once the lane is behind the truck (or when the run
    // never started at a facility at all).
    pub departure_ramp_mi: Option<f64>,
    // Lanes on our side last tick, so a road that narrows under the truck
    // can be told apart from a driver who steered into the cones.
    pub lane_count_seen: Option<i64>,
    // The truck's own lane index the instant before this frame's
    // set_lane_count clamp ran, so a narrowing road that actually moved
    // the truck can be told apart from one that merely renumbered a lane
    // the truck was never in.
    pub lane_before_narrow: Option<i64>,
    pub merge_taper_warned: Option<String>,
    pub hazard_dodgeable: bool,
    // The speed of the VEHICLE this hazard is about, when it is a vehicle.
    // None for debris, animals and anything else that is not going
    // anywhere. See hazard_target_mph.
    pub hazard_lead_mph: Option<f64>,
    pub hazard_lane: i64,
    pub left_lane_s: f64,
    pub keep_right_nags: i64,
    pub ambient_event_cooldown_s: f64,
    // Ambient lines waiting for the road to go quiet. A FIFO, not the
    // one slot it used to be: see _speak_ambient_event.
    pub pending_ambient_events: VecDeque<PendingAmbient>,
    pub road_joint_accumulator_m: f64,
    pub next_joint_distance_m: f64,
    pub lane_guidance: LaneGuidance,
    pub edge_loop_key: Option<String>, // active edge-ladder rung loop
    pub road_pan_applied: f64,         // last pursuit-guide pan set on the road bed
    // The opt-in guide tone: whether its loop is running, and where it
    // is panned. Separate from the bed's tracker so switching the
    // setting mid-drive cannot leave either one stuck off center.
    pub lane_guide_tone_on: bool,
    pub lane_guide_pan_applied: f64,
    // Dead-man's-curve strips: fixed road furniture ahead of each hairpin.
    pub transverse_strip_miles: Vec<f64>,
    /// `set[float]` of the strips already played.
    pub transverse_fired: Vec<f64>,
    pub lane_locator_on: bool, // I toggles the panned position tock
    pub lane_locator_timer: f64,
    // The same tock, summoned by the steering itself rather than by I:
    // while a lane move is underway it runs on its own and ends with the
    // signal cancelling. See _update_steering_lane_cue.
    pub steer_cue_active: bool,
    pub steer_cue_timer: f64,
    pub steer_cue_hold_s: f64, // how long the wheel has been held this way
    pub curve_run: Option<CurveRun>, // the bend underway, and how it is going
    pub cross_repeat_s: f64,   // rapid re-crossings keep only the quiet thump
    pub sideswipe_cooldown_s: f64, // one contact, however many crossings
    // Off-pavement is a standing condition: the panned edge-rumble loop
    // carries "where am I right now", and speech fires only at transitions
    // -- left the pavement, worse, back on it (research doc R12). None means
    // on the pavement; otherwise the last-spoken severity band.
    pub road_position_band: Option<i32>,
    pub reverse_cue_active: bool,
    pub air_cue_active: bool, // compressor fill loop below governor release
    pub jake_cue_key: Option<String>, // jake growl loop currently playing
    pub curve_assist_jake: bool, // jake engaged BY the assist (not the player)
    pub auto_jake: bool,      // automatic-box retarder management (J on an AMT)
    pub auto_jake_enabled: bool, // Alt+J: whether J arms auto mode on an AMT
    pub resume_target_mph: Option<f64>, // Shift+K brings this speed back
    pub auto_jake_hold_mph: Option<f64>, // speed auto mode holds
    pub auto_jake_cooldown_s: f64, // rate limit between stage steps
    pub shift_recover_t: f64, // 0->1 recovery progress after an automatic shift ends
    pub shift_hold_rpm: Option<f64>, // engine voice held here through a shift
    // Smooth only the audible engine load. Physics keeps the raw throttle,
    // while small controller and cruise changes blend into the engine bed.
    pub engine_audio_throttle: f64,
    // Prev-frame accel/brake state, so a forward<->reverse shift needs a
    // fresh press (release then press) rather than a held control.
    pub reverse_brake_held: bool,
    pub reverse_accel_held: bool,
    // Direction-change gesture state: which change a fresh standstill
    // press has armed, and how long the control has been held since.
    // The gear engages only past DIRECTION_CHANGE_HOLD_S.
    pub direction_armed: String,
    pub direction_hold_s: f64,
    // Latching pedals (double-tap-and-hold, see sim/pedal_latch.py):
    // a latched pedal reads as held everywhere downstream.
    pub throttle_latch: PedalLatch,
    pub brake_latch: PedalLatch,
    // True while a caught throttle latch is standing down for a speed
    // authority (see _speed_authority_engaged); the curve block reads
    // it to retry the jake once the yielded throttle drains.
    pub latch_yielding: bool,
    // Curve calls already made this trip (keys are curve entry miles).
    pub pacenote_spoken: HashSet<i64>,
    pub status_text: String,

    // ---- driving_liquid.py (lazily initialised in Python via getattr) -------------------
    pub liquid_audio_ok: Option<bool>,
    pub liquid_wash_on: bool,
    pub liquid_lateral_cooldown_s: f64,
    pub liquid_surge_said: bool,
    pub liquid_settled_said: bool,
    pub liquid_settle_timer_s: f64,

    // ---- driving.py: lifecycle -----------------------------------------------------------
    pub entered_once: bool,
}

impl DrivingState {
    /// `self.truck`: the truck rides on the trip.
    #[inline]
    pub fn truck(&self) -> &TruckState {
        &self.trip.truck
    }

    #[inline]
    pub fn truck_mut(&mut self) -> &mut TruckState {
        &mut self.trip.truck
    }

    /// `self.weather`: the weather system rides on the trip.
    #[inline]
    pub fn weather(&self) -> &WeatherSystem {
        &self.trip.weather
    }

    #[inline]
    pub fn weather_mut(&mut self) -> &mut WeatherSystem {
        &mut self.trip.weather
    }

    /// Replace the active trip (surface or departure chain) and bump the
    /// generation the turn latches compare against (`id(self.trip)`).
    pub fn replace_trip(&mut self, trip: Trip) -> Trip {
        self.trip_generation += 1;
        std::mem::replace(&mut self.trip, trip)
    }
}

// -- the State facade ---------------------------------------------------------------------
//
// Forwards to the mixin modules' methods:
//   driving_controls.rs : handle_key_event, handle_controller_event,
//                         handle_controller_disconnect
//   driving_updates.rs  : update_frame, tick_drive_music, apply_radio_settings_to_drive
//   driving_events.rs   : visible_lines, presence_state, online_presence_state

impl State for DrivingState {
    // At the wheel, main-channel lines (achievements, assist notices, info
    // replies) queue instead of cutting whatever is mid-air -- the event
    // channel's discipline, extended to the other voice (research doc, R2).
    fn paces_main_speech(&self) -> bool {
        true
    }

    fn enter(&mut self, ctx: &mut GameContext) {
        self.enter_drive(ctx);
    }

    fn exit(&mut self, ctx: &mut GameContext) {
        self.exit_drive(ctx);
    }

    fn handle_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        self.handle_key_event(ctx, event);
    }

    fn handle_controller(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        self.handle_controller_event(ctx, event);
    }

    fn on_controller_disconnect(&mut self, ctx: &mut GameContext) {
        self.handle_controller_disconnect(ctx);
    }

    fn update(&mut self, ctx: &mut GameContext, dt: f64) {
        self.update_frame(ctx, dt);
    }

    fn lines(&self, ctx: &GameContext) -> Vec<String> {
        self.visible_lines(ctx)
    }

    fn presence(&self, ctx: &GameContext) -> Option<PresenceState> {
        self.presence_state(ctx)
    }

    fn online_presence(&self, ctx: &GameContext) -> Option<PresenceState> {
        self.online_presence_state(ctx)
    }

    fn ticks_covered_music(&self) -> bool {
        true
    }

    fn tick_covered_music(&mut self, ctx: &mut GameContext, dt: f64) {
        self.tick_drive_music(ctx, dt);
    }

    fn applies_radio_settings(&self) -> bool {
        true
    }

    fn apply_radio_settings_now(&mut self, ctx: &mut GameContext) {
        self.apply_radio_settings_to_drive(ctx);
    }

    fn radio(&self) -> Option<&RadioState> {
        Some(&self.radio)
    }
}

// The TEMPORARY stub module that stood here while the mixins landed is gone:
// every block in it has been deleted by the module that took it over, this
// task's (`driving_updates.rs`) last of all.
