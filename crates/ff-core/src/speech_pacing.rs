//! Pacing, repeat suppression, and priority for the driving event voice.
//!
//! The event channel is a queue the game cannot inspect: it hands lines to a
//! voice that speaks them in submission order, and nothing in Prism will say
//! what is still waiting. Three things go wrong when the road talks straight
//! into it, all three reported from the same tester transcript (2026-08-11):
//!
//! * **The same moment said several times.** A code path that notices
//!   something runs every frame, so one sideswipe arrives as three identical
//!   lines inside half a second.
//! * **A standing condition read out forever.** A damaged load, an engine
//!   held at redline -- the truck is still in that state, so the warning
//!   fires again every few seconds for the rest of the drive. The player
//!   needs it when it starts and again when it gets worse, not on a loop.
//! * **The line that mattered buried.** The stop the player planned waits
//!   behind weather, tolls, and traffic chatter, and is still waiting when
//!   the exit has gone by.
//!
//! [`EventSpeechPacer`] answers all three from one place.
//!
//! Its original job -- and still its core -- is the backlog projection: each
//! submitted line extends a projected clear time by its estimated speaking
//! duration, so the game knows roughly when the voice falls silent. A queued
//! line that would START speaking more than its priority's budget after the
//! moment it described is by definition stale, and the caller delivers it
//! interrupting instead, which purges the dead backlog. Interrupting lines
//! reset the projection to truth, so estimate drift never outlives one
//! backlog.
//!
//! On top of that it remembers what the player has already heard (so a
//! repeat inside `REPEAT_WINDOW_S` never reaches the voice twice), what each
//! standing condition last said (so it speaks again only when it has
//! something new to say), and how long a line of each priority is willing to
//! wait -- a route announcement waits a moment behind chatter and then goes
//! ahead of it.
//!
//! The purge that delivers an interrupting line cuts both ways: it flushes
//! dead chatter, but it also lands on whatever the voice was mid-way through
//! -- and when that was a ROUTE or CRITICAL line (the weigh station notice,
//! the planned stop), the player lost an instruction, not colour (a tester
//! blew a weigh station this way, 2026-08-12). The pacer therefore keeps the
//! newest such line alongside its projected finish time, and an interrupt
//! arriving before that moment hands the line back to the caller to queue
//! right behind the interrupting one: safety line first, then the line it
//! stepped on.
//!
//! Durations are estimated from text length at a conservative default-voice
//! speaking rate. A faster voice just flushes a little less eagerly than it
//! could; a slower one flushes a little late but stays bounded -- either way
//! the player never again waits through a paragraph of expired narration.
//!
//! Port of `freight_fate/speech_pacing.py`.

use std::collections::HashMap;
use std::sync::OnceLock;
use std::time::Instant;

/// Seconds since the first call: the default pacer clock, the equivalent of
/// Python's `time.monotonic`.
pub fn monotonic_seconds() -> f64 {
    static START: OnceLock<Instant> = OnceLock::new();
    START.get_or_init(Instant::now).elapsed().as_secs_f64()
}

/// How long a line is willing to wait behind what is already speaking.
///
/// `Ambient` is the running commentary of the road -- weather, tolls, state
/// lines, roadside colour. Missing one costs the player nothing.
///
/// `Route` is the drive itself: the stop the player planned, the exit they
/// have to take. It gets a much shorter patience than chatter, so it goes
/// ahead of a backlog rather than behind it.
///
/// `Critical` is a warning to act on now. It is always delivered
/// interrupting, so it never consults the budget at all.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum EventPriority {
    Ambient = 0,
    Route = 1,
    Critical = 2,
}

/// What a line of informational speech is ABOUT.
///
/// Orthogonal to [`EventPriority`], which says how long a line waits and
/// whether staleness may drop it. Urgency alone gave the verbosity system
/// only one lever -- length -- which is why compressing every message (stage
/// S2) did not make the drive quieter: it never reduced how many things
/// speak. The rung table below cuts by category instead.
///
/// Flavor -- billboards, place names, landmarks, roadside colour -- is
/// deliberately absent. It answers to the chatter switches and the
/// place-callouts ladder, and the owner set those separately (2026-08-15).
///
/// A recurring miscategorisation the review caught three times (2026-08-16):
/// a line that names a key the player must press to keep moving is never
/// CONFIRMATION. CONFIRMATION is an outcome report -- the assist cleared it,
/// the latch caught, here is what happened. A stalled engine, a grounded
/// tractor, a scrapped chain set are unrequested failures that stop the
/// truck and demand a next action; at quiet and urgent_only CONFIRMATION is
/// an EARCON, so miscategorising one of these turns the instruction that
/// gets the truck moving again into a chime. Route it by what actually
/// changed instead: SAFETY when the truck will not move and the line says
/// what to press, MONEY when it cost money or equipment.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum SpeechCategory {
    Safety,
    Navigation,
    /// Navigation you cannot recover from -- take this exit, turn here, you
    /// missed it -- against navigation that is a heads-up on what the road
    /// is about to do. Both are navigation and both speak at quiet; they
    /// part company at urgent_only, where the heads-up becomes a tone and
    /// the unrecoverable one keeps its words. Splitting them is what makes
    /// the two quietest rungs different settings rather than near-copies
    /// (owner, 2026-08-17: the strict "only if you must act" rule describes
    /// urgent_only, and quiet should be "still very little" above it).
    NavigationAdvisory,
    Money,
    Coaching,
    Confirmation,
    Status,
}

impl SpeechCategory {
    /// Every category, in the Python enum's declaration order.
    pub const ALL: [SpeechCategory; 7] = [
        SpeechCategory::Safety,
        SpeechCategory::Navigation,
        SpeechCategory::NavigationAdvisory,
        SpeechCategory::Money,
        SpeechCategory::Coaching,
        SpeechCategory::Confirmation,
        SpeechCategory::Status,
    ];

    /// The Python `StrEnum` value.
    pub fn value(self) -> &'static str {
        match self {
            SpeechCategory::Safety => "safety",
            SpeechCategory::Navigation => "navigation",
            SpeechCategory::NavigationAdvisory => "navigation_advisory",
            SpeechCategory::Money => "money",
            SpeechCategory::Coaching => "coaching",
            SpeechCategory::Confirmation => "confirmation",
            SpeechCategory::Status => "status",
        }
    }

    /// `SpeechCategory(value)`.
    pub fn from_value(value: &str) -> Option<SpeechCategory> {
        SpeechCategory::ALL
            .into_iter()
            .find(|category| category.value() == value)
    }
}

/// What a rung does with a category.
///
/// `Earcon` and `Silent` both stop the words; they differ in whether the
/// sound layer still marks the moment. Neither loses the line -- both still
/// reach the message log, and the status-query keys still answer, so nothing
/// the ladder cuts becomes unreachable.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Disposition {
    /// speaks, normal rendering
    Full,
    /// speaks, terse rendering -- never silence
    Terse,
    /// speaks the first time per leg, then silent
    FirstOccurrence,
    /// speaks on enter, worsen, and clear only
    Transitions,
    /// the sound layer carries it; no words
    Earcon,
    /// no words, no sound; log and status keys only
    Silent,
}

impl Disposition {
    pub const ALL: [Disposition; 6] = [
        Disposition::Full,
        Disposition::Terse,
        Disposition::FirstOccurrence,
        Disposition::Transitions,
        Disposition::Earcon,
        Disposition::Silent,
    ];

    /// The Python `StrEnum` value.
    pub fn value(self) -> &'static str {
        match self {
            Disposition::Full => "full",
            Disposition::Terse => "terse",
            Disposition::FirstOccurrence => "first",
            Disposition::Transitions => "transitions",
            Disposition::Earcon => "earcon",
            Disposition::Silent => "silent",
        }
    }
}

// "coaching" was a fourth rung above standard, and it was removed on
// 2026-08-17 because it never differed from standard at the voice. Its two
// table cells (COACHING full rather than once-per-leg, STATUS full rather
// than on transitions) only bite where a coaching tip repeats, and exactly
// one line in the game carries SpeechCategory::Coaching -- so cycling to it
// changed nothing a player could hear. In a game read entirely by ear, a
// setting that offers a choice and produces no audible difference is worse
// than one fewer choice: it reads as broken. The CATEGORY stays (that one
// line, and the Coaching note earcon quiet retires it to); it is the RUNG
// that is gone, and re-adding it is one row of a data table once there are
// tips to put in it.
pub const DRIVING_SPEECH_MODES: [&str; 3] = ["standard", "quiet", "urgent_only"];

/// One rung's row of the table: a disposition per category.
pub type DispositionRow = [(SpeechCategory, Disposition); 7];

/// The rung table. Read a row as "at this rung, a line of this category is
/// delivered this way". Safety and money are FULL or TERSE in every row and
/// a test pins that: R1's never-dropped contract outranks any rung.
pub const DRIVING_SPEECH_DISPOSITIONS: [(&str, DispositionRow); 3] = [
    (
        "standard",
        [
            (SpeechCategory::Safety, Disposition::Full),
            (SpeechCategory::Money, Disposition::Full),
            (SpeechCategory::Navigation, Disposition::Full),
            (SpeechCategory::NavigationAdvisory, Disposition::Full),
            (SpeechCategory::Coaching, Disposition::FirstOccurrence),
            (SpeechCategory::Confirmation, Disposition::Full),
            (SpeechCategory::Status, Disposition::Transitions),
        ],
    ),
    (
        "quiet",
        [
            (SpeechCategory::Safety, Disposition::Terse),
            (SpeechCategory::Money, Disposition::Terse),
            (SpeechCategory::Navigation, Disposition::Terse),
            (SpeechCategory::NavigationAdvisory, Disposition::Terse),
            (SpeechCategory::Coaching, Disposition::Earcon),
            (SpeechCategory::Confirmation, Disposition::Earcon),
            (SpeechCategory::Status, Disposition::Earcon),
        ],
    ),
    (
        "urgent_only",
        [
            (SpeechCategory::Safety, Disposition::Terse),
            (SpeechCategory::Money, Disposition::Terse),
            (SpeechCategory::Navigation, Disposition::Terse),
            (SpeechCategory::NavigationAdvisory, Disposition::Earcon),
            (SpeechCategory::Coaching, Disposition::Silent),
            (SpeechCategory::Confirmation, Disposition::Earcon),
            (SpeechCategory::Status, Disposition::Silent),
        ],
    ),
];

pub const DEFAULT_DRIVING_SPEECH: &str = "standard";

/// `DRIVING_SPEECH_DISPOSITIONS[mode]`, or None for a rung not in the table.
pub fn disposition_row(mode: &str) -> Option<&'static DispositionRow> {
    DRIVING_SPEECH_DISPOSITIONS
        .iter()
        .find(|(name, _)| *name == mode)
        .map(|(_, row)| row)
}

/// One cell of a row.
pub fn row_disposition(row: &DispositionRow, category: SpeechCategory) -> Option<Disposition> {
    row.iter()
        .find(|(candidate, _)| *candidate == category)
        .map(|(_, disposition)| *disposition)
}

/// The sound that carries a category once a rung stops speaking it. Every
/// value is a real `SoundEntry.name` in the Learn game sounds catalog
/// (`sound_catalog::CATALOG`) -- pinned by
/// `test_every_earcon_category_is_learnable` -- because a sound the player
/// cannot look up is information removed rather than information moved
/// (R14). CONFIRMATION had reused the hazard-clear chime that shipped in S3
/// rather than getting a cue of its own. That was a mistake and is fixed:
/// the chime already means "you got past the hazard", so at quiet it fired
/// for every silenced confirmation -- including "Automatic braking.", which
/// happens while the hazard is still there (owner playtest, 2026-08-17).
/// COACHING, CONFIRMATION, NAVIGATION_ADVISORY and STATUS have no existing
/// sound that means what an earcon here needs to mean, so each gets its own
/// synthesized entry (`ladder_earcons`).
pub const LADDER_EARCONS: [(SpeechCategory, &str); 4] = [
    (SpeechCategory::NavigationAdvisory, "Road ahead note"),
    (SpeechCategory::Coaching, "Coaching note"),
    (SpeechCategory::Confirmation, "Confirmation note"),
    (SpeechCategory::Status, "Status note"),
];

/// `LADDER_EARCONS.get(category)`.
pub fn ladder_earcon(category: SpeechCategory) -> Option<&'static str> {
    LADDER_EARCONS
        .iter()
        .find(|(candidate, _)| *candidate == category)
        .map(|(_, name)| *name)
}

/// How this rung delivers this category.
///
/// An unknown rung reads as the default rather than raising: a settings
/// file edited by hand must not be able to crash the drive. A `None`
/// category is an unclassified call site and always speaks -- the rendering
/// still follows the rung, so it gets shorter but never disappears.
pub fn disposition_for(mode: &str, category: Option<SpeechCategory>) -> Disposition {
    let row = disposition_row(mode)
        .or_else(|| disposition_row(DEFAULT_DRIVING_SPEECH))
        .expect("the default rung is in the table");
    match category {
        None => row_disposition(row, SpeechCategory::Safety).expect("every row rules on safety"),
        Some(category) => row_disposition(row, category).unwrap_or(Disposition::Full),
    }
}

/// A source of monotonic seconds; injectable so tests can drive the
/// projection without sleeping.
pub type Clock = Box<dyn FnMut() -> f64>;

/// "Is the moment this line described still live?" -- consulted before a
/// cut line is handed back.
pub type Valid = Box<dyn Fn() -> bool>;

/// A cut ROUTE or CRITICAL line handed back for requeueing.
pub type Cut = (String, EventPriority);

// The newest ROUTE or CRITICAL line submitted, with the projection's
// estimate of when it finishes speaking. (The Python kept this as a 4-tuple
// of text, priority, done_at, valid.)
struct Protected {
    text: String,
    priority: EventPriority,
    done_at: f64,
    valid: Option<Valid>,
}

/// Keeps the dedicated event voice from performing the past.
///
/// See the module docs for the whole picture. The caller's contract:
///
/// * `is_repeat` decides whether the player has already heard this; a true
///   means say nothing at all.
/// * `note_spoken` records a line that did reach the voice.
/// * `is_silenced_repeat`/`note_silenced` are the same pair for a line the
///   driving speech rung cut to an earcon or to nothing -- a private
///   namespace so a silenced occurrence can dedupe its own earcon without
///   ever registering as something `is_repeat` would recognise as heard.
/// * `note_interrupt` for an interrupting line (it purges the channel), or
///   `should_flush` for a queued one -- true there means the backlog has
///   gone stale and this line must be submitted interrupting instead.
/// * `note_interrupt` may hand back the ROUTE or CRITICAL line the purge cut
///   off mid-sentence; the caller resubmits it queued (`note_queued`) so the
///   player still hears it, right behind the line that cut it.
/// * `note_channel_purged` when speech outside the pacer's view (an info
///   reply on a shared voice) purges the channel -- same hand-back.
/// * `pause`/`resume` around a screen that takes the player off the road.
pub struct EventSpeechPacer {
    clock: Clock,
    clear_at: f64,
    /// text -> when the player last heard it.
    recent: HashMap<String, f64>,
    /// condition key -> the last thing said about it.
    conditions: HashMap<String, String>,
    // The same two maps, but for occurrences the driving speech rung
    // silenced (an earcon or nothing, never the words). Kept separate from
    // `recent`/`conditions` on purpose: those two belong to what the player
    // actually heard, and `is_repeat` consults them to decide whether a
    // genuinely spoken line would be news. If a silenced occurrence wrote
    // into that same state, raising the rung mid-drive while a standing
    // condition was still active (still locked out, still at redline) would
    // find the SILENCED text sitting in `conditions`, read the now-audible
    // occurrence as an unchanged repeat, and skip it -- exactly the rung
    // promising full sentences going quiet for the condition the player
    // raised it to hear about.
    silenced_recent: HashMap<String, f64>,
    silenced_conditions: HashMap<String, String>,
    /// Set by pause(): the next line purges the channel, so anything the
    /// voice was still holding when the player stepped away cannot surface
    /// behind it.
    purge_next: bool,
    /// The newest ROUTE or CRITICAL line submitted, with the projection's
    /// estimate of when it finishes speaking. An interrupt landing before
    /// that moment plausibly cut it off mid-sentence; it is handed back to
    /// the caller so the player still hears it.
    protected: Option<Protected>,
    /// Set by should_flush when its purge cut a line still speaking;
    /// collected once by take_flush_cut. See that method.
    flush_cut: Option<Cut>,
    /// text -> until when further rescues of it are refused. See
    /// `take_protected`: one rescue per line per window.
    rescued_until: HashMap<String, f64>,
}

impl Default for EventSpeechPacer {
    fn default() -> Self {
        Self::new()
    }
}

impl EventSpeechPacer {
    /// a queued line may start at most this far in the past
    pub const STALE_WAIT_S: f64 = 3.0;
    /// per-utterance pause before the voice gets going
    pub const BASE_UTTERANCE_S: f64 = 0.4;
    /// the default Windows voice at its default rate
    pub const CHARS_PER_S: f64 = 13.0;

    /// Two identical lines this close together are one thing happening, not
    /// two, whichever code path noticed it. Deliberately short: it collapses
    /// a burst of frames without ever swallowing the second press of a key
    /// the player pushed on purpose.
    pub const REPEAT_WINDOW_S: f64 = 2.5;

    /// Bound on the remembered-lines map, so a long career cannot grow it
    /// without limit.
    pub const RECENT_LIMIT: usize = 256;
    pub const RECENT_MEMORY_S: f64 = 300.0;

    /// After a line is rescued once, further cuts within this window drop it
    /// instead of replaying it -- long enough to cover any burst of stacked
    /// urgent lines (the trooper escalation runs well under this), short
    /// enough that the same words minutes later are a new moment that earns
    /// its own rescue.
    pub const RESCUE_ONCE_WINDOW_S: f64 = 30.0;

    /// How long a line of each priority will wait behind a backlog before it
    /// is better to purge the channel and speak now. Route announcements
    /// have almost no patience: a planned stop that arrives after its exit
    /// is worse than a piece of chatter cut off mid-word.
    pub fn wait_budget_s(priority: EventPriority) -> f64 {
        match priority {
            EventPriority::Ambient => Self::STALE_WAIT_S,
            EventPriority::Route => 0.8,
            EventPriority::Critical => Self::STALE_WAIT_S,
        }
    }

    /// A pacer on the monotonic clock.
    pub fn new() -> Self {
        Self::with_clock(Box::new(monotonic_seconds))
    }

    pub fn with_clock(clock: Clock) -> Self {
        Self {
            clock,
            clear_at: 0.0,
            recent: HashMap::new(),
            conditions: HashMap::new(),
            silenced_recent: HashMap::new(),
            silenced_conditions: HashMap::new(),
            purge_next: false,
            protected: None,
            flush_cut: None,
            rescued_until: HashMap::new(),
        }
    }

    /// Swap the clock under a live pacer (the Python tests poked
    /// `pacer._clock`; the app's ladder tests need the same).
    pub fn set_clock(&mut self, clock: Clock) {
        self.clock = clock;
    }

    fn now(&mut self) -> f64 {
        (self.clock)()
    }

    fn duration_s(text: &str) -> f64 {
        Self::BASE_UTTERANCE_S + text.chars().count() as f64 / Self::CHARS_PER_S
    }

    // -- what the player has already heard ---------------------------------

    /// True when saying this again would tell the player nothing new.
    ///
    /// `key` names a standing condition -- a state of the world rather than
    /// a moment in it. A condition speaks when it starts and again only when
    /// what there is to say about it has changed, so a worsening number is
    /// news and the same number is not.
    ///
    /// `force` is for a line the player asked for: a status key, a
    /// deliberate replay. It is always heard.
    pub fn is_repeat(
        &mut self,
        text: &str,
        key: Option<&str>,
        force: bool,
        window: Option<f64>,
    ) -> bool {
        if force || text.is_empty() {
            return false;
        }
        if let Some(key) = key {
            if self.conditions.get(key).is_some_and(|said| said == text) {
                return true;
            }
        }
        let budget = window.unwrap_or(Self::REPEAT_WINDOW_S);
        if budget <= 0.0 {
            return false;
        }
        match self.recent.get(text).copied() {
            Some(last) => self.now() - last < budget,
            None => false,
        }
    }

    /// Record a line that reached the voice.
    pub fn note_spoken(&mut self, text: &str, key: Option<&str>) {
        if text.is_empty() {
            return;
        }
        let now = self.now();
        self.recent.insert(text.to_string(), now);
        if let Some(key) = key {
            self.conditions.insert(key.to_string(), text.to_string());
        }
        if self.recent.len() > Self::RECENT_LIMIT {
            self.recent
                .retain(|_, said| now - *said < Self::RECENT_MEMORY_S);
        }
    }

    /// A standing condition has cleared; let it announce itself afresh.
    pub fn forget_condition(&mut self, key: &str) {
        self.conditions.remove(key);
        self.silenced_conditions.remove(key);
    }

    // -- what the rung silenced (earcon-only or fully quiet) ----------------

    /// True when this silenced occurrence was already marked (earcon or not).
    ///
    /// The silenced branches' own dedup: mirrors [`Self::is_repeat`]'s rules
    /// exactly, but reads a namespace private to occurrences the rung cut,
    /// never `conditions`/`recent`. A silenced repeat must not go unmarked
    /// (that is the earcon machine-gun this exists to stop), but it must
    /// equally never be mistaken for a genuinely spoken occurrence by
    /// [`Self::is_repeat`] once the rung changes and the condition is still
    /// active -- that would silence the very line the player raised the rung
    /// to hear.
    pub fn is_silenced_repeat(
        &mut self,
        text: &str,
        key: Option<&str>,
        window: Option<f64>,
    ) -> bool {
        if text.is_empty() {
            return false;
        }
        if let Some(key) = key {
            if self
                .silenced_conditions
                .get(key)
                .is_some_and(|said| said == text)
            {
                return true;
            }
        }
        let budget = window.unwrap_or(Self::REPEAT_WINDOW_S);
        if budget <= 0.0 {
            return false;
        }
        match self.silenced_recent.get(text).copied() {
            Some(last) => self.now() - last < budget,
            None => false,
        }
    }

    /// Record a silenced occurrence (earcon played, or fully quiet).
    pub fn note_silenced(&mut self, text: &str, key: Option<&str>) {
        if text.is_empty() {
            return;
        }
        let now = self.now();
        self.silenced_recent.insert(text.to_string(), now);
        if let Some(key) = key {
            self.silenced_conditions
                .insert(key.to_string(), text.to_string());
        }
        if self.silenced_recent.len() > Self::RECENT_LIMIT {
            self.silenced_recent
                .retain(|_, said| now - *said < Self::RECENT_MEMORY_S);
        }
    }

    // -- the backlog projection ---------------------------------------------

    /// Remember the newest line worth rescuing if an interrupt lands on it.
    ///
    /// A CONFIRMATION never takes the slot, whatever priority it was spoken
    /// at. Confirmations default to CRITICAL because they answer something
    /// the player just did, so they used to qualify -- and then the next
    /// interrupting line on the main channel handed the finished
    /// confirmation back to be requeued, where it resurfaced AFTER, and
    /// could bury, the line the player had actually just asked for. The slot
    /// exists to rescue a warning cut off mid-sentence; an outcome report
    /// that already finished, and whose outcome may since have been
    /// contradicted (the transmission flipped back, the units changed
    /// again), is not that. Found by the adversarial harness on
    /// settings_flips_mid_drive, and made routine rather than rare once
    /// pressed keys began interrupting again (2026-08-16).
    ///
    /// Public because the driving layer (and the Python tests) re-arm the
    /// slot with a liveness check after a plain submission.
    pub fn track(
        &mut self,
        text: &str,
        priority: EventPriority,
        category: Option<SpeechCategory>,
        valid: Option<Valid>,
    ) {
        if category == Some(SpeechCategory::Confirmation) {
            self.protected = None;
            return;
        }
        if priority >= EventPriority::Route {
            self.protected = Some(Protected {
                text: text.to_string(),
                priority,
                done_at: self.clear_at,
                valid,
            });
        }
    }

    /// The line a stale flush cut off mid-sentence, once, for requeueing.
    ///
    /// `note_interrupt` returns its cut directly; `should_flush` cannot,
    /// because its return value is the flush verdict. Same contract either
    /// way: a ROUTE or CRITICAL line still plausibly speaking is handed back.
    pub fn take_flush_cut(&mut self) -> Option<Cut> {
        self.flush_cut.take()
    }

    /// Hand over the protected line if it was plausibly cut mid-speech.
    ///
    /// The slot empties either way: a line is given back at most once per
    /// cut, and a line whose projected finish had already passed was heard
    /// in full, not destroyed. A line cutting itself is one line, not two,
    /// so it is never handed back behind its own delivery.
    ///
    /// And at most ONE rescue per line per window. A rescued line is
    /// re-queued and re-protected, so without this a CHAIN of urgent lines
    /// replays it after every one of them -- the 21 August build note has
    /// "Signal for the scale exit" speaking five times through a trooper
    /// escalation, and the transponder's green light three times. One
    /// rescue is the whole contract (the cut line gets to finish once); a
    /// line cut a second time in a moment that busy has been overtaken by
    /// events, and message review holds the words.
    fn take_protected(&mut self, cutting_text: Option<&str>) -> Option<Cut> {
        let held = self.protected.take()?;
        let Protected {
            text,
            priority,
            done_at,
            valid,
        } = held;
        if self.now() >= done_at || Some(text.as_str()) == cutting_text {
            return None;
        }
        if let Some(valid) = valid {
            if !valid() {
                // The moment the line described has passed -- the scale is
                // behind the truck, the damage total has moved on. Replaying
                // the words verbatim would state something that is no longer
                // true, which is worse than the silence (the adversarial
                // battery's "44% total damage while the truck was at 51%",
                // and the scale-exit instruction offered after the scale).
                // Message review holds it.
                return None;
            }
        }
        let now = self.now();
        if now < self.rescued_until.get(&text).copied().unwrap_or(0.0) {
            return None;
        }
        let until = self.now() + Self::RESCUE_ONCE_WINDOW_S;
        self.rescued_until.insert(text.clone(), until);
        Some((text, priority))
    }

    /// An interrupting line purges the channel: the projection restarts.
    ///
    /// Returns the ROUTE or CRITICAL line the purge plausibly cut off
    /// mid-sentence -- its projected finish had not yet passed -- so the
    /// caller can queue it right back behind the interrupting line. Chatter,
    /// lines already heard in full, and a line interrupting itself return
    /// None: nothing worth giving back was destroyed.
    pub fn note_interrupt(
        &mut self,
        text: &str,
        priority: EventPriority,
        category: Option<SpeechCategory>,
        valid: Option<Valid>,
    ) -> Option<Cut> {
        let cut = self.take_protected(Some(text));
        self.purge_next = false;
        self.clear_at = self.now() + Self::duration_s(text);
        self.track(text, priority, category, valid);
        cut
    }

    /// Extend the projection for a line delivered queued, no verdict asked.
    ///
    /// For the deliveries that must never flush: a rescued cut-off line (it
    /// has to fall in BEHIND the line that cut it, never purge it) and event
    /// lines riding the main channel, where the backlog belongs to the main
    /// voice rather than the pacer.
    pub fn note_queued(
        &mut self,
        text: &str,
        priority: EventPriority,
        category: Option<SpeechCategory>,
        valid: Option<Valid>,
    ) {
        let start = self.now().max(self.clear_at);
        self.clear_at = start + Self::duration_s(text);
        self.track(text, priority, category, valid);
    }

    /// Speech outside the pacer's view purged the channel events ride on.
    ///
    /// Only meaningful when the event voice is collapsed onto the main
    /// channel: an info reply's interrupt there lands on whatever event line
    /// was mid-sentence. Returns the cut ROUTE or CRITICAL line exactly as
    /// [`Self::note_interrupt`] would; the projection falls with the purge
    /// (the interrupting speech itself is not the pacer's to time).
    pub fn note_channel_purged(&mut self) -> Option<Cut> {
        let cut = self.take_protected(None);
        self.clear_at = 0.0;
        cut
    }

    /// Whether the projection says the event voice is still speaking.
    ///
    /// The channel cannot be asked directly (nothing in Prism reports queue
    /// state), so this is the same estimate the staleness budget runs on. It
    /// is what audio ducking restores on: the mix steps back while this is
    /// true and comes back the frame it goes false. Purges, pauses, and
    /// resets zero the projection, so a silenced channel reads not-busy at
    /// once instead of waiting out a stale estimate.
    pub fn busy(&mut self) -> bool {
        self.now() < self.clear_at
    }

    /// Whether this queued line would start past its priority's budget.
    ///
    /// A pure reading -- the projection is not touched, nothing is tracked.
    /// The caller uses it to decide a line's fate BEFORE committing it to
    /// the channel: chatter that would start stale is dropped silently (UIA
    /// MostRecent semantics -- superseded telemetry is discarded, not read
    /// late), where [`Self::should_flush`] would instead deliver it
    /// interrupting. A purge armed by pause() is not staleness; that path
    /// stays with should_flush, whose first line back purges the backlog.
    pub fn would_start_stale(&mut self, _text: &str, priority: EventPriority) -> bool {
        if self.purge_next {
            return false;
        }
        let now = self.now();
        let start = now.max(self.clear_at);
        let budget = Self::wait_budget_s(priority);
        start - now > budget
    }

    /// Decide a queued line's fate and update the projection either way.
    ///
    /// Returns true when the line would otherwise start stale -- the caller
    /// must then submit it interrupting (which purges the dead backlog).
    /// `priority` sets how long this line is willing to wait: a route
    /// announcement gives a backlog of chatter under a second before it goes
    /// in front of it.
    ///
    /// (As in the Python, the slot is re-armed here WITHOUT a category: a
    /// confirmation delivered queued still takes it.)
    pub fn should_flush(
        &mut self,
        text: &str,
        priority: EventPriority,
        valid: Option<Valid>,
    ) -> bool {
        let now = self.now();
        self.flush_cut = None;
        if self.purge_next {
            // Coming back from a pause. Whatever the voice was still holding
            // when the player stepped away is about a mile they have already
            // been told about, so the first line back purges it -- and that
            // one really is stale, so it is dropped rather than rescued.
            self.purge_next = false;
            self.clear_at = now + Self::duration_s(text);
            self.protected = None;
            self.track(text, priority, None, valid);
            return true;
        }
        let start = now.max(self.clear_at);
        let budget = Self::wait_budget_s(priority);
        if start - now > budget {
            // A stale flush takes the backlog -- everything in it described
            // miles already driven -- but NOT a protected line that is still
            // speaking. The incoming line starting stale says nothing about
            // the outgoing one: a CRITICAL warning that began this very tick
            // is not stale, and dropping it here broke the class's own
            // never-dropped contract silently, with no requeue.
            //
            // An engine stall was stepped on exactly this way by the
            // route-start merge cue (owner playtest, 2026-08-19). It was
            // latent until that cue stopped being AMBIENT -- as chatter it
            // was dropped by would_start_stale before ever reaching here.
            //
            // An AGED backlog of ROUTE announcements really does describe
            // road already driven and is right to go -- rescuing those
            // turned one flush into a recital of everything it had just
            // purged. A safety call is the standing exception: it is the one
            // line whose worth does not decay while it waits.
            //
            // But "aged" was read off the INCOMING line only, and the two
            // come apart the moment the road speaks twice in one frame.
            // Measured on the owner's 23 August session: of 59 lines a flush
            // destroyed, 34 were cut inside `BASE_UTTERANCE_S` of their own
            // start -- the pause before the voice gets going -- so by this
            // pacer's own duration model the player had not heard one
            // character of them. Three route lines arriving inside 37 ms
            // took the ramp-exit briefing with them: "Off the ramp and onto
            // city streets: start on unnamed public road. Then turn right
            // now onto Halleck Street" was purged 22 ms in, and that turn
            // was never spoken. A line that young is not a backlog; it is
            // this same instant of road, and destroying it costs the whole
            // line rather than its tail.
            //
            // So the rescue asks how much of the outgoing line the player
            // actually got. Past the pre-utterance window it has said
            // something and its tail is expendable; inside it, nothing was
            // heard and the words are still current, so they are handed back
            // to be queued behind the line that cut them -- the same
            // contract a CRITICAL cut has always had. `RESCUE_ONCE_WINDOW_S`
            // still caps it at one hand-back per line, so a run of urgent
            // lines cannot replay it.
            let held_rescuable = self.protected.as_ref().is_some_and(|held| {
                held.priority == EventPriority::Critical
                    || now - (held.done_at - Self::duration_s(&held.text)) < Self::BASE_UTTERANCE_S
            });
            if held_rescuable {
                self.flush_cut = self.take_protected(Some(text));
            } else {
                self.protected = None;
            }
            self.clear_at = now + Self::duration_s(text);
            self.track(text, priority, None, valid);
            return true;
        }
        self.clear_at = start + Self::duration_s(text);
        self.track(text, priority, None, valid);
        false
    }

    /// The channel was silenced outside the pacer's view (Ctrl, menus).
    pub fn reset(&mut self) {
        self.clear_at = 0.0;
        self.purge_next = false;
        self.protected = None;
    }

    // -- leaving and returning to the road ----------------------------------

    /// The player has stepped off the road (pause menu, a stop, settings).
    ///
    /// The caller silences the event channel; this drops the projection with
    /// it and arms the purge, so the first line spoken back on the road
    /// cannot arrive behind a backlog describing where the truck used to be.
    pub fn pause(&mut self) {
        self.clear_at = 0.0;
        self.purge_next = true;
        self.protected = None;
    }

    /// Back at the wheel. Nothing from before the pause is news.
    pub fn resume(&mut self) {
        self.clear_at = 0.0;
        self.purge_next = true;
        self.protected = None;
    }
}

#[cfg(test)]
mod tests {
    //! Ported from the pure (no `App()`) tests of
    //! `tests/test_event_speech_pacer.py` and `tests/test_driving_speech_ladder.py`.
    use super::*;
    use std::cell::Cell;
    use std::rc::Rc;

    /// A controllable clock: `clock.now.set(...)` to advance.
    struct FakeClock {
        now: Rc<Cell<f64>>,
    }

    impl FakeClock {
        fn at(start: f64) -> Self {
            Self {
                now: Rc::new(Cell::new(start)),
            }
        }

        fn clock(&self) -> Clock {
            let now = Rc::clone(&self.now);
            Box::new(move || now.get())
        }

        fn advance(&self, seconds: f64) {
            self.now.set(self.now.get() + seconds);
        }
    }

    fn make_pacer() -> (EventSpeechPacer, FakeClock) {
        let clock = FakeClock::at(100.0);
        (EventSpeechPacer::with_clock(clock.clock()), clock)
    }

    fn flush(pacer: &mut EventSpeechPacer, text: &str) -> bool {
        pacer.should_flush(text, EventPriority::Ambient, None)
    }

    fn flush_at(pacer: &mut EventSpeechPacer, text: &str, priority: EventPriority) -> bool {
        pacer.should_flush(text, priority, None)
    }

    fn interrupt(pacer: &mut EventSpeechPacer, text: &str) -> Option<Cut> {
        pacer.note_interrupt(text, EventPriority::Critical, None, None)
    }

    fn cut(text: &str, priority: EventPriority) -> Option<Cut> {
        Some((text.to_string(), priority))
    }

    fn always(value: Rc<Cell<bool>>) -> Option<Valid> {
        Some(Box::new(move || value.get()))
    }

    // ~10 seconds at the default 13 chars per second
    const LONG_LINE: &str = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx";

    #[test]
    fn test_long_line_is_130_chars() {
        assert_eq!(LONG_LINE.len(), 130);
    }

    #[test]
    fn test_quiet_channel_queues_normally() {
        let (mut pacer, _) = make_pacer();
        assert!(!flush(&mut pacer, "Slow down for the dock."));
    }

    #[test]
    fn test_backlog_past_the_threshold_flushes() {
        let (mut pacer, _) = make_pacer();
        // First long line starts immediately; the second waits ~10s behind
        // it -- far past the 3-second staleness budget.
        assert!(!flush(&mut pacer, LONG_LINE));
        assert!(flush(&mut pacer, "At the dock."));
    }

    #[test]
    fn test_flush_restarts_the_projection() {
        let (mut pacer, _) = make_pacer();
        flush(&mut pacer, LONG_LINE);
        assert!(flush(&mut pacer, "At the dock."));
        // The flush purged the channel: the very next line queues normally.
        assert!(!flush(&mut pacer, "Delivering."));
    }

    #[test]
    fn test_interrupt_resets_to_truth() {
        let (mut pacer, _) = make_pacer();
        flush(&mut pacer, LONG_LINE);
        interrupt(&mut pacer, "Collision!");
        // The interrupting line purged the backlog; a short queued follow-up
        // starts right behind it, inside the staleness budget.
        assert!(!flush(&mut pacer, "Total damage 12 percent."));
    }

    #[test]
    fn test_projection_expires_with_real_time() {
        let (mut pacer, clock) = make_pacer();
        flush(&mut pacer, LONG_LINE);
        clock.advance(30.0); // the voice long since finished speaking
        assert!(!flush(&mut pacer, "Exit ahead."));
    }

    #[test]
    fn test_reset_clears_the_projection() {
        let (mut pacer, _) = make_pacer();
        flush(&mut pacer, LONG_LINE);
        pacer.reset();
        assert!(!flush(&mut pacer, "At the dock."));
    }

    const CHATTER: &str = "Rain easing off, roads still wet."; // ~2.4s estimated

    #[test]
    fn test_would_start_stale_is_a_pure_reading() {
        let (mut pacer, _) = make_pacer();
        flush(&mut pacer, LONG_LINE);
        assert!(pacer.would_start_stale(CHATTER, EventPriority::Ambient));
        // Pure: asking did not extend the projection or consume anything.
        assert!(pacer.would_start_stale(CHATTER, EventPriority::Ambient));
        let (mut quiet, _) = make_pacer();
        assert!(!quiet.would_start_stale(CHATTER, EventPriority::Ambient));
    }

    /// The first line back from a pause must purge and speak, never drop.
    #[test]
    fn test_the_post_pause_purge_is_not_read_as_staleness() {
        let (mut pacer, clock) = make_pacer();
        flush(&mut pacer, LONG_LINE);
        pacer.pause();
        clock.advance(45.0);
        assert!(!pacer.would_start_stale(CHATTER, EventPriority::Ambient));
        assert!(flush(&mut pacer, CHATTER));
    }

    #[test]
    fn test_many_short_lines_stay_within_budget_then_flush() {
        let (mut pacer, _) = make_pacer();
        let line = "Passing the fuel island."; // ~2.3s estimated
        let verdicts: Vec<bool> = (0..4).map(|_| flush(&mut pacer, line)).collect();
        // The first few fit inside the budget; the backlog eventually crosses it.
        assert!(!verdicts[0]);
        assert!(verdicts[1..].contains(&true));
    }

    // -- one moment, said once (tester transcript, 2026-08-11) --------------
    //
    // A sideswipe arrived as three identical lines inside six tenths of a
    // second, and a load's condition was read out unchanged every few
    // seconds for the rest of the drive. The pacer now knows what the player
    // has already heard.

    const SIDESWIPE: &str = "You sideswiped a box truck in the right lane! The truck took damage, now 13 percent. Check your mirrors before moving over.";

    #[test]
    fn test_identical_line_inside_the_window_is_a_repeat() {
        let (mut pacer, clock) = make_pacer();
        assert!(!pacer.is_repeat(SIDESWIPE, None, false, None));
        pacer.note_spoken(SIDESWIPE, None);
        clock.advance(0.6); // the burst the tester heard
        assert!(pacer.is_repeat(SIDESWIPE, None, false, None));
    }

    #[test]
    fn test_the_same_line_is_news_again_once_the_window_passes() {
        let (mut pacer, clock) = make_pacer();
        pacer.note_spoken(SIDESWIPE, None);
        clock.advance(EventSpeechPacer::REPEAT_WINDOW_S + 0.1);
        assert!(!pacer.is_repeat(SIDESWIPE, None, false, None));
    }

    #[test]
    fn test_a_line_the_player_asked_for_is_never_a_repeat() {
        let (mut pacer, _) = make_pacer();
        pacer.note_spoken(SIDESWIPE, None);
        assert!(!pacer.is_repeat(SIDESWIPE, None, true, None));
    }

    /// A state of the world speaks when it starts and when it worsens.
    #[test]
    fn test_standing_condition_repeats_only_when_it_changes() {
        let (mut pacer, clock) = make_pacer();
        let at_45 = "The load has shifted hard and is badly damaged, 45 percent.";
        let at_60 = "The load has shifted hard and is badly damaged, 60 percent.";

        assert!(!pacer.is_repeat(at_45, Some("cargo_condition"), false, None));
        pacer.note_spoken(at_45, Some("cargo_condition"));

        // Minutes later, still the same load in the same state: nothing new to say.
        clock.advance(300.0);
        assert!(pacer.is_repeat(at_45, Some("cargo_condition"), false, None));

        // The damage has moved. That is news, and it speaks.
        assert!(!pacer.is_repeat(at_60, Some("cargo_condition"), false, None));
        pacer.note_spoken(at_60, Some("cargo_condition"));
        clock.advance(300.0);
        assert!(pacer.is_repeat(at_60, Some("cargo_condition"), false, None));
    }

    #[test]
    fn test_a_cleared_condition_announces_itself_afresh() {
        let (mut pacer, clock) = make_pacer();
        let redline = "Redline. Engine wear 4 percent.";
        pacer.note_spoken(redline, Some("engine_redline"));
        clock.advance(300.0);
        assert!(pacer.is_repeat(redline, Some("engine_redline"), false, None));
        // The engine came off the limiter and went back on: a fresh event.
        pacer.forget_condition("engine_redline");
        assert!(!pacer.is_repeat(redline, Some("engine_redline"), false, None));
    }

    /// The pacer half of `test_raising_the_rung_still_speaks_an_active_silenced_condition`
    /// (an `App()` test in the ladder file): a silenced occurrence marks its
    /// own namespace and never the one `is_repeat` reads.
    #[test]
    fn test_a_silenced_occurrence_never_reads_as_heard() {
        let (mut pacer, clock) = make_pacer();
        let lockout = "Parking brake set. Press P to release it.";
        assert!(!pacer.is_silenced_repeat(lockout, Some("air_brake_lockout"), None));
        pacer.note_silenced(lockout, Some("air_brake_lockout"));
        clock.advance(60.0);
        // The earcon is deduped for the silenced branch...
        assert!(pacer.is_silenced_repeat(lockout, Some("air_brake_lockout"), None));
        // ...and the speaking path still finds the line unheard.
        assert!(!pacer.is_repeat(lockout, Some("air_brake_lockout"), false, None));
        // Clearing the condition clears both namespaces.
        pacer.forget_condition("air_brake_lockout");
        assert!(!pacer.is_silenced_repeat(lockout, Some("air_brake_lockout"), None));
    }

    // -- stepping off the road ----------------------------------------------

    #[test]
    fn test_pause_arms_a_purge_so_the_backlog_is_not_replayed() {
        let (mut pacer, clock) = make_pacer();
        flush(&mut pacer, LONG_LINE); // a line still speaking when the player pauses
        pacer.pause();
        clock.advance(45.0); // a while in the pause menu
                             // Back on the road: the first line purges the channel rather than
                             // falling in behind whatever the voice was still holding.
        assert!(flush(
            &mut pacer,
            "Speed limit reduced to 55 miles per hour."
        ));
    }

    #[test]
    fn test_resume_purges_once_then_paces_normally() {
        let (mut pacer, _) = make_pacer();
        pacer.pause();
        pacer.resume();
        assert!(flush(&mut pacer, "Rest area in two miles."));
        // The purge is spent; the channel is trusted again from here.
        assert!(!flush(&mut pacer, "Weigh station ahead."));
    }

    // -- the stop the player planned ----------------------------------------

    /// Tester Darren: planned stops get lost in the traffic chatter.
    ///
    /// Two pacers in identical states, so the only thing under test is the
    /// priority the line was submitted with.
    #[test]
    fn test_route_priority_will_not_wait_out_a_backlog_of_chatter() {
        let stop_line = "Planned stop, Iowa 80 Truckstop at Exit 284 in five miles.";

        let (mut ambient, _) = make_pacer();
        flush(&mut ambient, CHATTER);
        // Behind one piece of chatter, another informational line is content
        // to wait its turn -- nothing is lost by hearing it a few seconds later.
        assert!(!flush_at(&mut ambient, stop_line, EventPriority::Ambient));

        let (mut route, _) = make_pacer();
        flush(&mut route, CHATTER);
        // The same line as a planned stop has an exit to make, so it goes in
        // front of the chatter instead of behind it.
        assert!(flush_at(&mut route, stop_line, EventPriority::Route));
    }

    #[test]
    fn test_route_priority_still_queues_behind_a_quiet_channel() {
        let (mut pacer, _) = make_pacer();
        // Nothing is speaking: a route line has no reason to cut anything off.
        assert!(!flush_at(
            &mut pacer,
            "Rest area in two miles.",
            EventPriority::Route
        ));
    }

    // -- the line the interrupt stepped on (tester report, 2026-08-12) -------
    //
    // A hazard, a curve call, or an info key landing while the voice was
    // mid-way through "Open weigh station ahead" destroyed the announcement
    // outright: the purge that delivers an interrupting line took the queue
    // with it, and nothing gave the cut line back. A tester blew a weigh
    // station that way. The pacer now hands the cut ROUTE or CRITICAL line
    // back so it queues right behind the line that cut it -- safety line
    // first, then the line it stepped on.

    const STOP_LINE: &str = "Planned stop, Iowa 80 Truckstop at Exit 284 in five miles.";
    const HAZARD: &str = "Hazard! Stopped traffic ahead.";

    #[test]
    fn test_interrupt_hands_back_a_cut_route_line() {
        let (mut pacer, _) = make_pacer();
        flush_at(&mut pacer, STOP_LINE, EventPriority::Route);
        assert_eq!(
            interrupt(&mut pacer, HAZARD),
            cut(STOP_LINE, EventPriority::Route)
        );
    }

    #[test]
    fn test_a_route_line_that_finished_is_not_handed_back() {
        let (mut pacer, clock) = make_pacer();
        flush_at(&mut pacer, STOP_LINE, EventPriority::Route);
        clock.advance(30.0); // the voice long since read it out in full
        assert_eq!(interrupt(&mut pacer, HAZARD), None);
    }

    #[test]
    fn test_ambient_chatter_is_never_handed_back() {
        let (mut pacer, _) = make_pacer();
        flush(&mut pacer, CHATTER); // AMBIENT: missing it costs the player nothing
        assert_eq!(interrupt(&mut pacer, HAZARD), None);
    }

    #[test]
    fn test_a_critical_line_cut_by_another_critical_is_handed_back() {
        let (mut pacer, _) = make_pacer();
        let first = "Emergency vehicle approaching from behind. Move right.";
        assert_eq!(interrupt(&mut pacer, first), None); // quiet channel: nothing was cut
        assert_eq!(
            interrupt(&mut pacer, HAZARD),
            cut(first, EventPriority::Critical)
        );
    }

    /// The one-line ping-pong: A cutting A must not requeue A behind A.
    #[test]
    fn test_a_line_interrupting_itself_is_not_handed_back() {
        let (mut pacer, _) = make_pacer();
        flush_at(&mut pacer, STOP_LINE, EventPriority::Route);
        assert_eq!(interrupt(&mut pacer, STOP_LINE), None);
    }

    #[test]
    fn test_the_hand_back_happens_at_most_once_per_cut() {
        let (mut pacer, _) = make_pacer();
        flush_at(&mut pacer, STOP_LINE, EventPriority::Route);
        assert_eq!(
            interrupt(&mut pacer, HAZARD),
            cut(STOP_LINE, EventPriority::Route)
        );
        // The slot emptied with the hand-back and now holds the hazard: a
        // further interrupt rescues the line it lands on, never the stop line
        // twice.
        assert_eq!(
            interrupt(&mut pacer, "Sharp curve ahead."),
            cut(HAZARD, EventPriority::Critical)
        );
    }

    /// The trooper-escalation loop from the 21 August build note: a rescued
    /// line is requeued and re-protected, so a CHAIN of urgent lines used to
    /// replay it after every one -- "Signal for the scale exit" spoke five
    /// times. One rescue per line per window; the second cut drops it.
    #[test]
    fn test_a_rescued_line_is_not_rescued_again_by_the_next_cut() {
        let (mut pacer, _) = make_pacer();
        let escalations: Vec<String> = (1..6)
            .map(|n| format!("Failure to stop, warning {n}."))
            .collect();
        flush_at(&mut pacer, STOP_LINE, EventPriority::Route);
        let mut rescues = 0;
        for warning in &escalations {
            if let Some((text, priority)) = interrupt(&mut pacer, warning) {
                if text == STOP_LINE {
                    rescues += 1;
                    // the app requeues the rescue behind the warning,
                    // re-protecting it
                    pacer.note_queued(&text, priority, None, None);
                }
            }
        }
        assert_eq!(rescues, 1, "the stop line was replayed {rescues} times");
    }

    /// The cap is a window, not a life sentence: a genuinely new moment that
    /// happens to use the same words is cut and rescued like any other.
    #[test]
    fn test_the_same_words_minutes_later_earn_a_fresh_rescue() {
        let (mut pacer, clock) = make_pacer();
        flush_at(&mut pacer, STOP_LINE, EventPriority::Route);
        let rescued = interrupt(&mut pacer, HAZARD);
        assert_eq!(rescued, cut(STOP_LINE, EventPriority::Route));
        let (text, priority) = rescued.unwrap();
        pacer.note_queued(&text, priority, None, None);
        clock.advance(EventSpeechPacer::RESCUE_ONCE_WINDOW_S + 1.0);
        flush_at(&mut pacer, STOP_LINE, EventPriority::Route);
        assert_eq!(
            interrupt(&mut pacer, HAZARD),
            cut(STOP_LINE, EventPriority::Route)
        );
    }

    /// It answers something the player did; it is not a warning to rescue.
    ///
    /// Confirmations default to CRITICAL, so they used to qualify -- and then
    /// the next interrupting line on the main channel handed the FINISHED
    /// confirmation back to be requeued, where it resurfaced after, and could
    /// bury, the line the player had actually just asked for. The adversarial
    /// harness found it on settings_flips_mid_drive; pressed keys
    /// interrupting again (2026-08-16) turned it from rare into every info
    /// key.
    #[test]
    fn test_a_confirmation_never_takes_the_hand_back_slot() {
        let (mut pacer, _) = make_pacer();
        let confirmation = "Transmission changed to manual.";
        assert_eq!(
            pacer.note_interrupt(
                confirmation,
                EventPriority::Critical,
                Some(SpeechCategory::Confirmation),
                None
            ),
            None
        );
        // The S query that follows gets the channel to itself.
        assert_eq!(interrupt(&mut pacer, HAZARD), None);
    }

    /// The slot still does its job for the lines it was built for.
    #[test]
    fn test_a_warning_is_still_handed_back_after_the_confirmation_rule() {
        let (mut pacer, _) = make_pacer();
        flush_at(&mut pacer, STOP_LINE, EventPriority::Route);
        assert_eq!(
            interrupt(&mut pacer, HAZARD),
            cut(STOP_LINE, EventPriority::Route)
        );
    }

    /// The class promises a ROUTE or CRITICAL line still speaking is handed
    /// back, never dropped. `note_interrupt` honoured that; `should_flush`
    /// did not -- its purge cleared the protected slot outright.
    ///
    /// An engine stall was stepped on exactly that way by the route-start
    /// merge cue on the owner's Denver playtest: the stall spoke CRITICAL,
    /// the merge cue flushed a moment later, and the stall was gone with no
    /// requeue. It was latent until that cue stopped being AMBIENT, because
    /// as chatter it had been dropped before ever reaching the flush.
    ///
    /// Narrowly CRITICAL: a backlog of stale ROUTE announcements really does
    /// describe road already driven, and rescuing those turned one flush
    /// into a recital of everything it had purged.
    #[test]
    fn test_a_stale_flush_never_steps_on_a_safety_call() {
        let clock = FakeClock::at(0.0);
        let mut pacer = EventSpeechPacer::with_clock(clock.clock());

        // A safety call starts speaking.
        pacer.note_interrupt(
            "Brake now! Stopped traffic ahead.",
            EventPriority::Critical,
            None,
            None,
        );
        // A route line arrives while it is still mid-sentence, far enough
        // behind the projection to flush.
        clock.advance(0.05);
        assert!(flush_at(
            &mut pacer,
            "Merge onto US-40 west toward Salt Lake City.",
            EventPriority::Route
        ));
        let cut = pacer.take_flush_cut();
        let cut = cut.expect("the safety call was purged with no requeue");
        assert_eq!(cut.0, "Brake now! Stopped traffic ahead.");
        // Collected once only.
        assert_eq!(pacer.take_flush_cut(), None);
    }

    /// The other half, and why the rescue is narrow. A route announcement
    /// the player has been listening to for a while has said its piece and
    /// describes road already driven; handing its tail back would perform
    /// the very backlog the flush purged.
    #[test]
    fn test_a_stale_flush_still_discards_an_aged_route_backlog() {
        let clock = FakeClock::at(0.0);
        let mut pacer = EventSpeechPacer::with_clock(clock.clock());

        let stop = "Next stop in 5 miles: service plaza."; // ~3.2 s spoken
        pacer.note_queued(stop, EventPriority::Route, None, None);
        // Well past the pre-utterance pause: the voice has been reading this
        // line aloud, and it is still mid-sentence when the flush lands.
        clock.advance(2.0);
        assert!(
            flush_at(
                &mut pacer,
                "Zone ahead; speed limit 45.",
                EventPriority::Route
            ),
            "the backlog was not deep enough to flush"
        );
        assert_eq!(
            pacer.take_flush_cut(),
            None,
            "an aged route backlog was resurrected"
        );
    }

    /// The owner's 23 August drive, three route lines inside 37 ms: the
    /// ramp-exit briefing was purged 22 ms into its own delivery -- by this
    /// pacer's own duration model, before the voice had uttered a character
    /// -- and the turn it named was never spoken at all. A line that young
    /// is not a stale backlog; it is the same instant of road as the line
    /// cutting it, so it comes back behind that line instead of dying.
    #[test]
    fn test_a_flush_hands_back_a_route_line_that_never_got_a_word_out() {
        let clock = FakeClock::at(0.0);
        let mut pacer = EventSpeechPacer::with_clock(clock.clock());

        let briefing = "Off the ramp and onto city streets: start on unnamed \
                        public road. Then turn right now onto Halleck Street. \
                        1 mile to the facility gate.";
        pacer.note_queued(briefing, EventPriority::Route, None, None);
        // The next route line lands in the same frame.
        clock.advance(0.022);
        assert!(
            flush_at(
                &mut pacer,
                "Start on unnamed public road.",
                EventPriority::Route
            ),
            "the burst did not flush"
        );
        assert_eq!(
            pacer.take_flush_cut(),
            cut(briefing, EventPriority::Route),
            "the turn instruction was destroyed before it said anything"
        );
        // Collected once only, exactly as a safety call's hand-back is.
        assert_eq!(pacer.take_flush_cut(), None);
    }

    /// And it is a hand-back, not a licence to replay: the cap that stops a
    /// run of urgent lines reciting the same words still applies.
    #[test]
    fn test_a_handed_back_route_line_is_not_handed_back_twice() {
        let clock = FakeClock::at(0.0);
        let mut pacer = EventSpeechPacer::with_clock(clock.clock());

        let briefing = "Off the ramp and onto city streets: start on unnamed \
                        public road. Then turn right now onto Halleck Street.";
        pacer.note_queued(briefing, EventPriority::Route, None, None);
        clock.advance(0.02);
        flush_at(
            &mut pacer,
            "Start on unnamed public road.",
            EventPriority::Route,
        );
        let (text, priority) = pacer.take_flush_cut().expect("the first hand-back");
        pacer.note_queued(&text, priority, None, None); // the app requeues it
        clock.advance(0.015);
        flush_at(
            &mut pacer,
            "In half a mile, facility gate ahead. Speed limit 15.",
            EventPriority::Route,
        );
        assert_eq!(
            pacer.take_flush_cut(),
            None,
            "the same line was handed back a second time"
        );
    }

    /// Darren and Jerry, 2026-08-21: the repeat the build note describes at
    /// a scale happens in a work zone too.
    ///
    /// The cap is keyed on the line's own words, so it was always going to
    /// cover this -- but "was always going to" is not a test, and the report
    /// named a place the suite had never driven. These are the real
    /// work-zone lines, behind the run of urgent lines a busy taper produces.
    #[test]
    fn test_a_construction_zone_line_is_rescued_once_like_any_other() {
        let work_zone = "Work zone active. The right lane is closed; keep left and watch the barrels. Speed limit 45.";
        let urgent = [
            "Brake lights ahead!",
            "Cones in your lane!",
            "Flagger stopping traffic!",
            "Truck merging left!",
            "Barrels in the shoulder!",
        ];
        let (mut pacer, _) = make_pacer();
        flush_at(&mut pacer, work_zone, EventPriority::Route);
        let mut rescues = 0;
        for warning in urgent {
            if let Some((text, priority)) = interrupt(&mut pacer, warning) {
                if text == work_zone {
                    rescues += 1;
                    pacer.note_queued(&text, priority, None, None);
                }
            }
        }
        assert_eq!(
            rescues, 1,
            "the work zone line was replayed {rescues} times"
        );
    }

    /// The other half of a work zone: the taper's own merge instruction,
    /// which is the line a driver can least afford to hear four times while
    /// deciding which way to go.
    #[test]
    fn test_the_merge_taper_line_is_rescued_once_too() {
        let taper =
            "Construction merge taper. The right lane closes ahead; merge left now. Speed limit 55.";
        let (mut pacer, _) = make_pacer();
        flush_at(&mut pacer, taper, EventPriority::Route);
        let mut rescues = 0;
        for n in 1..5 {
            if let Some((text, priority)) = interrupt(&mut pacer, &format!("Hazard {n}!")) {
                if text == taper {
                    rescues += 1;
                    pacer.note_queued(&text, priority, None, None);
                }
            }
        }
        assert_eq!(rescues, 1, "the taper line was replayed {rescues} times");
    }

    /// A cut line comes back so it can finish -- but only while it is still
    /// true. "Move right for the exit lane" handed back after the gore is
    /// behind the truck instructs a maneuver that no longer exists, which is
    /// the build note's own complaint about being told to signal for an exit
    /// when there is no exit left to take.
    #[test]
    fn test_a_rescued_line_dies_when_its_moment_has_passed() {
        let exit_line = "Exit 14A, half a mile ahead. Move right for the exit lane.";
        let still_ahead = Rc::new(Cell::new(true));
        let (mut pacer, _) = make_pacer();
        flush_at(&mut pacer, exit_line, EventPriority::Route);
        pacer.track(
            exit_line,
            EventPriority::Route,
            None,
            always(Rc::clone(&still_ahead)),
        );
        // Cut while the exit is still ahead: handed back, as it should be.
        assert_eq!(
            interrupt(&mut pacer, "Brake lights ahead!"),
            cut(exit_line, EventPriority::Route)
        );

        // Now the truck is past it. The same cut must NOT bring it back.
        still_ahead.set(false);
        let (mut pacer2, _) = make_pacer();
        flush_at(&mut pacer2, exit_line, EventPriority::Route);
        pacer2.track(
            exit_line,
            EventPriority::Route,
            None,
            always(Rc::clone(&still_ahead)),
        );
        assert_eq!(interrupt(&mut pacer2, "Brake lights ahead!"), None);
    }

    /// Shane, 2026-08-21, on "Change lanes or brake! Retread debris from a
    /// blown tire.": the line repeated two or three times.
    ///
    /// A cut line is handed back so it finishes -- that is what rescued the
    /// missing "you swerve around the brake lights". But a dodge call handed
    /// back after the truck is clear tells the driver to swerve around
    /// something that is no longer there. Same rule the scale and the
    /// destination exit already carry: a rescued line has to still be true.
    #[test]
    fn test_a_hazard_call_does_not_come_back_once_the_hazard_is_clear() {
        let hazard_line = "Change lanes or brake! Retread debris from a blown tire.";
        let live = Rc::new(Cell::new(true));
        let (mut pacer, _) = make_pacer();
        flush_at(&mut pacer, hazard_line, EventPriority::Critical);
        pacer.track(
            hazard_line,
            EventPriority::Critical,
            None,
            always(Rc::clone(&live)),
        );
        // Still live: cut by something louder, handed back to finish.
        assert_eq!(
            interrupt(&mut pacer, "Deer in the road!"),
            cut(hazard_line, EventPriority::Critical)
        );

        // Cleared: the same cut must not bring the dodge call back.
        live.set(false);
        let (mut pacer2, _) = make_pacer();
        flush_at(&mut pacer2, hazard_line, EventPriority::Critical);
        pacer2.track(
            hazard_line,
            EventPriority::Critical,
            None,
            always(Rc::clone(&live)),
        );
        assert_eq!(interrupt(&mut pacer2, "Deer in the road!"), None);
    }

    /// Found by driving it, not by a report: `playtest_road --find scale`
    /// requeued both of these.
    ///
    /// "Signal and brake to a stop on the shoulder" handed back after the
    /// truck IS stopped demands a pull-over that already happened, and its
    /// escalation threatens spike strips and felony charges over a stop the
    /// driver made. These carry the heaviest consequence of any line in the
    /// game, so they are the last ones that should be able to speak out of
    /// their moment.
    #[test]
    fn test_an_enforcement_stop_instruction_dies_once_the_truck_has_stopped() {
        let stop_call = "Scale bypass enforcement. Lights and siren behind you: signal with X and brake to a stop on the shoulder.";
        let final_call = "Final failure-to-stop warning. Brake to a full stop now or troopers will end the stop with spike strips and felony charges.";

        fn rescued(line: &str, stop_live: bool) -> Option<Cut> {
            let (mut pacer, _) = make_pacer();
            flush_at(&mut pacer, line, EventPriority::Critical);
            pacer.track(
                line,
                EventPriority::Critical,
                None,
                Some(Box::new(move || stop_live)),
            );
            interrupt(&mut pacer, "Deer in the road!")
        }

        for line in [stop_call, final_call] {
            // Stop still running: handed back so it finishes, which is the point.
            assert_eq!(rescued(line, true), cut(line, EventPriority::Critical));
            // Stop over: it must not come back and demand it again.
            assert_eq!(rescued(line, false), None, "{line}");
        }
    }

    /// `playtest_road --find limit-drop` requeued "Limit 35."
    ///
    /// Terse renders the overspeed warning as the bare limit, and a cut line
    /// is handed back to finish -- so a driver who lifted off in the meantime
    /// was told off for a speed they were no longer doing, quoting a limit
    /// that by then might belong to road behind them.
    #[test]
    fn test_the_overspeed_nag_dies_once_the_driver_has_slowed() {
        let nag = "Limit 35.";
        let over = Rc::new(Cell::new(false));
        let (mut pacer, _) = make_pacer();
        flush_at(&mut pacer, nag, EventPriority::Route);
        pacer.track(nag, EventPriority::Route, None, always(over));
        assert_eq!(interrupt(&mut pacer, "Brake now!"), None);
    }

    #[test]
    fn test_busy_follows_the_projection() {
        let (mut pacer, clock) = make_pacer();
        assert!(!pacer.busy());
        flush(&mut pacer, CHATTER);
        assert!(pacer.busy());
        clock.advance(10.0);
        assert!(!pacer.busy());
        flush(&mut pacer, CHATTER);
        pacer.reset();
        assert!(!pacer.busy());
    }

    // -- the S4 driving verbosity ladder (tests/test_driving_speech_ladder.py)

    /// "coaching" was a fourth rung and is gone (2026-08-17).
    ///
    /// It never differed from standard at the voice -- measured on two
    /// scenarios, byte-identical transcripts -- because its two table cells
    /// only bite where a coaching tip repeats and the game has exactly one
    /// line in that category. A setting that offers a choice and changes
    /// nothing audible is worse than one fewer choice in a game played by
    /// ear. The CATEGORY survives; the rung does not.
    #[test]
    fn test_the_ladder_has_three_named_rungs() {
        assert_eq!(DRIVING_SPEECH_MODES, ["standard", "quiet", "urgent_only"]);
        assert!(disposition_row("coaching").is_none());
    }

    #[test]
    fn test_every_rung_rules_on_every_category() {
        for mode in DRIVING_SPEECH_MODES {
            for category in SpeechCategory::ALL {
                assert!(Disposition::ALL.contains(&disposition_for(mode, Some(category))));
            }
        }
    }

    #[test]
    fn test_safety_and_money_speak_at_every_rung() {
        // R1's never-dropped contract outranks the ladder. A rung may
        // shorten these; it may never silence them.
        for mode in DRIVING_SPEECH_MODES {
            for category in [SpeechCategory::Safety, SpeechCategory::Money] {
                assert!(matches!(
                    disposition_for(mode, Some(category)),
                    Disposition::Full | Disposition::Terse
                ));
            }
        }
    }

    #[test]
    fn test_an_untagged_line_speaks_at_every_rung() {
        // A call site nobody has classified yet must be too loud, never silent.
        for mode in DRIVING_SPEECH_MODES {
            assert!(matches!(
                disposition_for(mode, None),
                Disposition::Full | Disposition::Terse
            ));
        }
    }

    #[test]
    fn test_the_table_reads_exactly_as_the_spec_says() {
        assert_eq!(
            *disposition_row("standard").unwrap(),
            [
                (SpeechCategory::Safety, Disposition::Full),
                (SpeechCategory::Money, Disposition::Full),
                (SpeechCategory::Navigation, Disposition::Full),
                (SpeechCategory::NavigationAdvisory, Disposition::Full),
                (SpeechCategory::Coaching, Disposition::FirstOccurrence),
                (SpeechCategory::Confirmation, Disposition::Full),
                (SpeechCategory::Status, Disposition::Transitions),
            ]
        );
        assert_eq!(
            *disposition_row("quiet").unwrap(),
            [
                (SpeechCategory::Safety, Disposition::Terse),
                (SpeechCategory::Money, Disposition::Terse),
                (SpeechCategory::Navigation, Disposition::Terse),
                (SpeechCategory::NavigationAdvisory, Disposition::Terse),
                (SpeechCategory::Coaching, Disposition::Earcon),
                (SpeechCategory::Confirmation, Disposition::Earcon),
                (SpeechCategory::Status, Disposition::Earcon),
            ]
        );
        assert_eq!(
            *disposition_row("urgent_only").unwrap(),
            [
                (SpeechCategory::Safety, Disposition::Terse),
                (SpeechCategory::Money, Disposition::Terse),
                (SpeechCategory::Navigation, Disposition::Terse),
                (SpeechCategory::NavigationAdvisory, Disposition::Earcon),
                (SpeechCategory::Coaching, Disposition::Silent),
                (SpeechCategory::Confirmation, Disposition::Earcon),
                (SpeechCategory::Status, Disposition::Silent),
            ]
        );
    }

    #[test]
    fn test_an_unknown_rung_falls_back_to_standard() {
        assert_eq!(
            disposition_for("nonsense", Some(SpeechCategory::Status)),
            Disposition::Transitions
        );
    }

    /// A guard against the shape of the bug, not just this instance of it.
    ///
    /// If a later change makes every category quiet and urgent_only disagree
    /// on inaudible at quiet, the two settings become indistinguishable again
    /// however different the table looks.
    #[test]
    fn test_the_two_quietest_rungs_are_not_the_same_setting() {
        let quiet = disposition_row("quiet").unwrap();
        let urgent = disposition_row("urgent_only").unwrap();
        let audible = [
            Disposition::Full,
            Disposition::Terse,
            Disposition::FirstOccurrence,
            Disposition::Transitions,
        ];
        let differ: Vec<SpeechCategory> = quiet
            .iter()
            .filter(|(category, disposition)| {
                row_disposition(urgent, *category) != Some(*disposition)
            })
            .map(|(category, _)| *category)
            .collect();
        assert!(!differ.is_empty(), "the rungs are identical");
        assert!(
            differ
                .iter()
                .any(|c| audible.contains(&row_disposition(quiet, *c).unwrap())),
            "quiet and urgent_only differ only in categories quiet already \
             silences, so a player switching between them hears no change"
        );
    }

    /// Owner playtest, 2026-08-17: "the hazard earcon is being used double
    /// in some places."
    ///
    /// CONFIRMATION borrowed the shipped "Hazard clear" chime instead of
    /// having a cue of its own, so at quiet every silenced confirmation
    /// played "you got past the hazard" -- including "Automatic braking.",
    /// which fires while the hazard is still there and the truck is braking
    /// for it. That is the exact failure `ladder_earcons`' own docstring
    /// forbids: one sound teaching a player two things.
    ///
    /// Pinned as a rule rather than as one mapping, so the next category
    /// added to the ladder cannot quietly borrow a different loaded sound.
    #[test]
    fn test_no_ladder_earcon_borrows_a_sound_that_already_means_something() {
        // Sounds that already carry a meaning of their own on the road.
        let spoken_for = [
            "Hazard clear",
            "Hazard warning",
            "Collision",
            "Overspeed",
            "Low air",
        ];
        let borrowed: Vec<_> = LADDER_EARCONS
            .iter()
            .filter(|(_, name)| spoken_for.contains(name))
            .collect();
        assert!(
            borrowed.is_empty(),
            "ladder earcon borrows a loaded sound: {borrowed:?}"
        );

        // And every ladder earcon is its own sound, not shared between two
        // categories -- which would be the same bug wearing a different hat.
        let mut names: Vec<&str> = LADDER_EARCONS.iter().map(|(_, name)| *name).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), LADDER_EARCONS.len());
        assert_eq!(ladder_earcon(SpeechCategory::Status), Some("Status note"));
        assert_eq!(ladder_earcon(SpeechCategory::Safety), None);
    }

    /// Quiet and urgent_only must not be able to drop a line as already-said.
    ///
    /// Both quieter rungs deliver every category TERSE, EARCON, or SILENT --
    /// the earcon/silent gate returns before `_ladder_repeats` is reached,
    /// and a TERSE line is never dropped -- so the suppression that swallowed
    /// 310 lines on standard could not touch them. That is a property of the
    /// TABLE, not of the code, and it is exactly the kind of thing a later
    /// table edit changes without anyone noticing: moving one quiet cell to
    /// TRANSITIONS would silently hand quiet a leg-scoped memory it has never
    /// had. Pinned so that edit has to be deliberate.
    #[test]
    fn test_only_standard_can_reach_the_already_said_gate() {
        let reaches_the_gate = [Disposition::FirstOccurrence, Disposition::Transitions];
        for rung in ["quiet", "urgent_only"] {
            let offenders: Vec<_> = disposition_row(rung)
                .unwrap()
                .iter()
                .filter(|(_, disposition)| reaches_the_gate.contains(disposition))
                .collect();
            assert!(
                offenders.is_empty(),
                "{rung} now reaches the already-said gate for {offenders:?}; \
                 that gate is standard's alone (Darren, 2026-08-19)"
            );
        }
    }

    #[test]
    fn test_enum_values_round_trip() {
        for category in SpeechCategory::ALL {
            assert_eq!(SpeechCategory::from_value(category.value()), Some(category));
        }
        assert_eq!(SpeechCategory::from_value("flavor"), None);
        assert_eq!(Disposition::FirstOccurrence.value(), "first");
        assert!(EventPriority::Critical > EventPriority::Route);
        assert!(EventPriority::Route > EventPriority::Ambient);
    }
}
