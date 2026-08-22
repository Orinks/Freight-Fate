//! `GameContext.say` / `say_event` and everything they run: the speech
//! ladder, the anti-backlog pacer, the audio duck, the transcript, and the
//! reviewable message log. The single most intricate piece of logic in the
//! app shell, reproduced line for line from `freight_fate/app.py`.
//!
//! Python defaults -> Rust: `say(text)` is `say_with(text, Say::new())`
//! (`interrupt=True, review=True, category=None`); `say_event(text)` is
//! `say_event_with(text, SayEvent::new())` (`interrupt=True, review=True,
//! priority=None, key=None, force=False, category=None, valid=None`). Both
//! take a plain `&str` or a `SpokenMessage` normal/terse pair through
//! [`IntoSpoken`].

use ff_core::message_log::MessageCategory;
use ff_core::sound_catalog::entry_by_name;
use ff_core::speech_pacing::{
    ladder_earcon, monotonic_seconds, Cut, Disposition, EventPriority, SpeechCategory, Valid,
};
use ff_core::speech_text::SpokenMessage;

use crate::audio::{EARCON_DUCK_S, SPEECH_DUCK_LEVEL};

use super::GameContext;

/// The logger every spoken line lands in too, so a logged playtest reads as
/// a transcript of what the player heard -- the most faithful record for an
/// audio-first game. Same name as the Python logger so the lines grep alike.
pub const TRANSCRIPT_TARGET: &str = "freight_fate.transcript";

macro_rules! transcript {
    ($($arg:tt)*) => {
        log::info!(target: TRANSCRIPT_TARGET, $($arg)*)
    };
}

/// The keyword arguments of `GameContext.say`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Say {
    pub interrupt: bool,
    pub review: bool,
    pub category: Option<SpeechCategory>,
}

impl Default for Say {
    fn default() -> Self {
        Self::new()
    }
}

impl Say {
    /// The Python defaults: `interrupt=True, review=True, category=None`.
    pub const fn new() -> Self {
        Self {
            interrupt: true,
            review: true,
            category: None,
        }
    }

    /// `interrupt=False`.
    pub const fn queued() -> Self {
        Self {
            interrupt: false,
            review: true,
            category: None,
        }
    }

    pub const fn interrupt(mut self, interrupt: bool) -> Self {
        self.interrupt = interrupt;
        self
    }

    pub const fn review(mut self, review: bool) -> Self {
        self.review = review;
        self
    }

    pub const fn category(mut self, category: SpeechCategory) -> Self {
        self.category = Some(category);
        self
    }
}

/// The keyword arguments of `GameContext.say_event`.
#[derive(Default)]
pub struct SayEvent {
    pub interrupt: bool,
    pub review: bool,
    pub priority: Option<EventPriority>,
    pub key: Option<String>,
    pub force: bool,
    pub category: Option<SpeechCategory>,
    /// A zero-argument "is this line still true?" consulted if the line is
    /// cut mid-sentence and offered a rescue.
    pub valid: Option<Valid>,
}

impl SayEvent {
    /// The Python defaults: `interrupt=True, review=True`, nothing else.
    pub fn new() -> Self {
        Self {
            interrupt: true,
            review: true,
            ..Default::default()
        }
    }

    /// `interrupt=False`.
    pub fn queued() -> Self {
        Self::new().interrupt(false)
    }

    pub fn interrupt(mut self, interrupt: bool) -> Self {
        self.interrupt = interrupt;
        self
    }

    pub fn review(mut self, review: bool) -> Self {
        self.review = review;
        self
    }

    pub fn priority(mut self, priority: EventPriority) -> Self {
        self.priority = Some(priority);
        self
    }

    pub fn key(mut self, key: &str) -> Self {
        self.key = Some(key.to_string());
        self
    }

    pub fn force(mut self, force: bool) -> Self {
        self.force = force;
        self
    }

    pub fn category(mut self, category: SpeechCategory) -> Self {
        self.category = Some(category);
        self
    }

    pub fn valid(mut self, valid: impl Fn() -> bool + 'static) -> Self {
        self.valid = Some(Box::new(valid));
        self
    }
}

/// What `say` / `say_event` accept as text: a plain string, or a
/// `SpokenMessage` normal/terse pair resolved in the delivery layer.
pub struct Spoken {
    pub message: SpokenMessage,
    /// Whether this came in as a pair (only a pair is dropped whole when its
    /// chosen rendering is empty).
    pub is_pair: bool,
}

pub trait IntoSpoken {
    fn into_spoken(self) -> Spoken;
}

impl IntoSpoken for &str {
    fn into_spoken(self) -> Spoken {
        Spoken {
            message: SpokenMessage::new(self),
            is_pair: false,
        }
    }
}

impl IntoSpoken for String {
    fn into_spoken(self) -> Spoken {
        Spoken {
            message: SpokenMessage::new(self),
            is_pair: false,
        }
    }
}

impl IntoSpoken for &String {
    fn into_spoken(self) -> Spoken {
        Spoken {
            message: SpokenMessage::new(self.as_str()),
            is_pair: false,
        }
    }
}

impl IntoSpoken for SpokenMessage {
    fn into_spoken(self) -> Spoken {
        Spoken {
            message: self,
            is_pair: true,
        }
    }
}

impl IntoSpoken for &SpokenMessage {
    fn into_spoken(self) -> Spoken {
        Spoken {
            message: self.clone(),
            is_pair: true,
        }
    }
}

impl GameContext {
    /// Whether the driving speech rung may silence anything yet.
    ///
    /// First-run teaching outranks the rung, exactly as it outranks terse
    /// (research doc R15). A player who picks the quietest setting before
    /// their first drive is the one who most needs to be told the status,
    /// help, and hazard keys exist -- silence them and they can never pull
    /// information nobody told them about. The gate is `tutorial_done`
    /// itself, so finishing the walkthrough and then choosing a quiet rung
    /// resurrects nothing.
    ///
    /// The default with no profile is deliberately `true`: no profile means
    /// nobody is on a first drive, so the rung applies normally.
    pub fn ladder_applies(&self) -> bool {
        self.profile
            .as_ref()
            .is_none_or(|profile| profile.tutorial_done)
    }

    /// Sound the cue standing in for a category the rung just cut.
    ///
    /// Spec invariant 3: what drops out of speech lands on the earcon layer
    /// or the message log, so cutting is legitimate rather than
    /// exclusionary. Only called where `speech_disposition` is already
    /// EARCON -- SILENT never reaches here, which is the entire difference
    /// at the voice between the `quiet` and `urgent_only` rungs.
    /// `LADDER_EARCONS` names the cue by the catalog entry's canonical noun;
    /// the entry itself is the one place its key, volume, and pan are
    /// written down, so this resolves through it rather than keeping a
    /// second copy that could drift.
    ///
    /// A category missing from the table, or a name the catalog does not
    /// carry, is a data bug in that table -- not something to raise
    /// mid-drive over, so it is skipped rather than crashing the game.
    fn play_ladder_earcon(&mut self, category: Option<SpeechCategory>) {
        let Some(category) = category else {
            return;
        };
        let Some(name) = ladder_earcon(category) else {
            return;
        };
        let Some(entry) = entry_by_name(name) else {
            return;
        };
        let Some(cue) = entry.plays.first() else {
            return;
        };
        self.audio.play_with(cue.key, cue.volume, cue.pan);
    }

    /// `say(text)`: interrupt, review, no category.
    pub fn say(&mut self, text: &str) {
        self.say_with(text, Say::new());
    }

    /// `say(text, interrupt=..., review=..., category=...)`.
    pub fn say_with(&mut self, text: impl IntoSpoken, say: Say) {
        let spoken = text.into_spoken();
        let Say {
            mut interrupt,
            review,
            category,
        } = say;
        if !self.settings.speaks(category) && self.ladder_applies() && !self.speech_requested {
            // The player's rung silences this category. The line still
            // reaches the review log, so the information is cut from the
            // drive, not from the game -- the review key that exists to
            // answer for it still can. Where the rung's disposition is
            // EARCON rather than SILENT, the sound layer marks the moment
            // instead of the words -- the two rungs that share this branch
            // are otherwise identical at the voice.
            //
            // A line the player ASKED for is exempt (`speech_requested`, set
            // by `player_asked()` around key and button handling) -- the
            // same escape `say_event` has carried as `force` since the
            // ladder shipped, missing here. Without it, pressing the cruise
            // dial at quiet answered with a chime and no number: the rung
            // was silencing an answer to a question the player had just
            // asked, which is not what a rung is for (owner, 2026-08-17).
            // The RENDERING still follows the rung, so quiet answers the
            // dial with "62" rather than a sentence.
            let text = self.render_silenced(&spoken);
            if self.event_pacer.is_silenced_repeat(&text, None, None) {
                // A keyless standing condition (no `key=` reaches this
                // method) re-fires on a timer while the drive is otherwise
                // unchanged. The gate above never used to consult the pacer,
                // so a silenced repeat still hit the earcon on every frame --
                // the quiet rung machine-gunning a sound where coaching says
                // one sentence and falls silent. The plain repeat window is
                // enough here; there is no `key=` to track a condition by.
                // `is_silenced_repeat`/`note_silenced` are a namespace of
                // their own (not `is_repeat`/`note_spoken`): a silenced
                // occurrence must never write into the state the SPEAKING
                // path reads, or raising the rung mid-drive while this same
                // condition is still active would find its own silenced text
                // already on file and go quiet for the sentence the rung now
                // promises.
                return;
            }
            if self.settings.speech_disposition(category) == Disposition::Earcon {
                self.play_ladder_earcon(category);
            }
            self.event_pacer.note_silenced(&text, None);
            transcript!(
                "[ladder] {} silenced: {}",
                self.settings.driving_speech,
                text
            );
            if review {
                self.message_log.add(&text, MessageCategory::General);
            }
            return;
        }
        // A normal/terse pair resolves here, in the delivery layer, so
        // coverage never again depends on a call-site branch (research doc,
        // R5). An empty rendering is a line terse mode drops whole.
        let Some(text) = self.render_spoken(&spoken) else {
            return;
        };
        transcript!("{}", text);
        if interrupt && !self.speech_requested && self.top_paces_main_speech() {
            // At the wheel, the main channel queues instead of cutting: an
            // achievement or assist notice must not stamp on the line the
            // player was mid-way through hearing. Menus and readers keep
            // their default interrupt -- a screen over the drive is the top
            // state, so navigation there still cancels speech the way every
            // screen reader does. A queued line also cannot purge a shared
            // voice, so the rescue below has nothing to hand back.
            //
            // A line the player ASKED for is exempt (`speech_requested`).
            // The rule above was aimed at lines nobody asked for, but it was
            // applied to every main-channel line at the wheel, so pressing a
            // key stopped cutting the speech in progress -- which is what
            // 1.8 does and what every screen reader does (Sarah R. via the
            // owner, 2026-08-16). Answering the key you just pressed is the
            // whole contract of an info key.
            interrupt = false;
        }
        let mut cut = None;
        if interrupt && self.event_voice_shares_main() {
            // In this configuration the main channel is also carrying the
            // road, so an info reply's interrupt can land on a ROUTE or
            // CRITICAL event line mid-sentence (a tester blew a weigh station
            // this way). The reply still answers first; the cut line queues
            // right behind it.
            cut = self.event_pacer.note_channel_purged();
        }
        self.speech.say(&text, interrupt);
        if let Some(cut) = cut {
            self.requeue_cut_event(cut);
        }
        if review {
            self.message_log.add(&text, MessageCategory::General);
        }
    }

    /// The silenced branch's rendering: the rung's rendering, falling back
    /// to the normal text when terse drops the line whole.
    fn render_silenced(&self, spoken: &Spoken) -> String {
        if spoken.is_pair {
            let rendered = spoken.message.render(self.settings.renders_terse());
            if rendered.is_empty() {
                spoken.message.normal.clone()
            } else {
                rendered.to_string()
            }
        } else {
            spoken.message.normal.clone()
        }
    }

    /// The speaking branch's rendering; `None` for a pair terse drops whole.
    fn render_spoken(&self, spoken: &Spoken) -> Option<String> {
        if spoken.is_pair {
            let rendered = spoken.message.render(self.settings.renders_terse());
            if rendered.is_empty() {
                return None;
            }
            Some(rendered.to_string())
        } else {
            Some(spoken.message.normal.clone())
        }
    }

    /// True when driving events speak on the main channel.
    ///
    /// Either the player chose the main voice for events (Settings >
    /// Speech), or the dedicated-voice preference found no separate backend
    /// to bind, so `say_event` falls back to the main channel.
    pub fn event_voice_shares_main(&self) -> bool {
        if !self.settings.sapi_events {
            return true;
        }
        !self.speech.has_separate_event_voice()
    }

    /// Finish delivering a ROUTE or CRITICAL line an interrupt cut short.
    ///
    /// Straight to the voice, queued: the line already passed the pacer,
    /// the transcript, and the message log when it was first submitted, so
    /// this is the same delivery completing rather than a new event. The
    /// pacer tracks it again, so a further genuine interrupt can hand it
    /// back a second time; it cannot ping-pong forever, because a requeue
    /// is never interrupting and an identical interrupting line is never
    /// handed back behind itself.
    fn requeue_cut_event(&mut self, cut: Cut) {
        let (text, priority) = cut;
        // Name the line. A bare "cut line requeued" says a hand-back
        // happened and not what came back, which is the one thing an audit
        // needs: four separate lines have now been found coming back after
        // their moment had passed (the scale exit, the destination exit,
        // the hazard dodge call, the dock hold prompt), each by a tester
        // hearing it rather than by anyone reading a bench transcript. With
        // the text here, a playtest log answers the question by itself --
        // grep the requeues, read each one, ask whether it was still true.
        transcript!("[pacer] cut line requeued: {}", text);
        self.event_pacer.note_queued(&text, priority, None, None);
        if self.settings.sapi_events {
            self.speech.say_event(&text, false);
        } else {
            self.speech.say(&text, false);
        }
    }

    /// Forget what has been said once, at a leg boundary.
    ///
    /// FIRST_OCCURRENCE is "speaks the first time per leg", so a new leg is
    /// a fresh road and the tip is worth one more telling.
    pub fn reset_ladder_leg_memory(&mut self) {
        self.ladder_said.clear();
    }

    /// Whether this rung's disposition drops this line as already-said.
    ///
    /// FIRST_OCCURRENCE: this LINE said once per leg, then nothing. Keyed on
    /// the key and the text together, not the key alone: the disposition
    /// exists for a coaching tip that repeats word for word, and keying on
    /// the condition instead meant a keyed readout whose number moves was
    /// said once and swallowed for the rest of the leg.
    ///
    /// TRANSITIONS: "enter, worsen, and clear only". A `key` names a standing
    /// condition, and status lines carry the state they are reporting in
    /// their own text -- so a line identical to the last one under this key
    /// is the condition re-asserting itself and a changed one is the
    /// transition.
    ///
    /// A line with NO key is not a standing condition; it is a discrete
    /// moment, and its call site has already decided this occurrence is
    /// worth saying. The rung has nothing to compare it against, so it does
    /// not suppress it. This fallback used to key on the text itself, which
    /// turned "enter, worsen, and clear" into "this exact sentence once per
    /// leg, ever" -- 310 lines dropped in one leg of a tester's log on
    /// STANDARD, the default rung (Darren, 2026-08-19). The pacer's own
    /// repeat window still stops the same line landing twice in a breath.
    fn ladder_repeats(
        &mut self,
        text: &str,
        category: Option<SpeechCategory>,
        key: Option<&str>,
    ) -> bool {
        match self.settings.speech_disposition(category) {
            Disposition::FirstOccurrence => {
                let slot = (key.unwrap_or("").to_string(), text.to_string());
                if self.ladder_said.contains(&slot) {
                    return true;
                }
                self.ladder_said.insert(slot);
                false
            }
            Disposition::Transitions => {
                let Some(key) = key else {
                    return false;
                };
                if self.ladder_last.get(key).is_some_and(|last| last == text) {
                    return true;
                }
                self.ladder_last.insert(key.to_string(), text.to_string());
                false
            }
            _ => false,
        }
    }

    /// `say_event(text)`: interrupt, review, no pacing arguments.
    pub fn say_event(&mut self, text: &str) {
        self.say_event_with(text, SayEvent::new());
    }

    /// Driving event announcements (hazards, warnings, weather, ...).
    ///
    /// `valid`, when given, answers "is this line still true?" -- consulted
    /// if the line is cut mid-sentence and offered a rescue. A line whose
    /// moment has passed (the scale is behind the truck, the damage total
    /// has moved on) is dropped instead of replayed verbatim; message review
    /// holds the words either way.
    ///
    /// With the dedicated SAPI event voice enabled, events speak on their
    /// own channel, where `interrupt` only cuts off a previous event -- so
    /// an urgent cue can still jump ahead of a stale one without touching
    /// the screen reader. With it disabled the player has chosen to hear
    /// events through their screen reader. Urgent events first flush stale
    /// game speech, then speak as a fresh queued utterance so old messages
    /// do not bury the warning.
    ///
    /// Every line first passes the pacer, which knows what the player has
    /// already heard. A line identical to one spoken a moment ago is dropped
    /// outright -- one moment noticed on several frames is still one moment.
    /// `key` marks a standing condition (a damaged load, an engine at
    /// redline) rather than an event: it speaks when it starts and again
    /// only when what it says has changed. `force` is for a line the player
    /// asked for and must hear whether or not it repeats.
    ///
    /// Queued events then ride an anti-backlog projection either way: a
    /// line that would start speaking well after the moment it described
    /// flushes the expired backlog and speaks now instead of joining the
    /// recital. `priority` sets how long it is willing to wait first --
    /// route announcements give ambient chatter well under a second before
    /// going in front of it.
    ///
    /// An interrupting line's purge also lands on whatever the voice was
    /// mid-way through. When that was a ROUTE or CRITICAL line still
    /// plausibly speaking, the pacer hands it back and it is resubmitted
    /// queued, right behind the interrupting line -- safety line first,
    /// then the line it stepped on, never dropped.
    ///
    /// `review` keeps a line out of the reviewable message log. An assist
    /// that interrupts to say it is acting would otherwise land exactly
    /// where the warning it cut off should be, so the review keys that
    /// exist to rescue an interrupted line would hand back the interruption
    /// instead.
    ///
    /// `text` may be a `SpokenMessage` normal/terse pair; the player's
    /// speech mode picks the rendering here, so terse coverage is a property
    /// of the message definition rather than of the call site. A pair whose
    /// terse rendering is empty is dropped whole in terse mode: not spoken,
    /// not logged, exactly like a muted chatter line.
    pub fn say_event_with(&mut self, text: impl IntoSpoken, opts: SayEvent) {
        let spoken = text.into_spoken();
        let SayEvent {
            mut interrupt,
            review,
            priority,
            key,
            force,
            category,
            valid,
        } = opts;
        let key = key.as_deref();
        if !self.settings.speaks(category) && !force && self.ladder_applies() {
            // The player's rung silences this category. The line still
            // reaches the review log and the status keys, so the
            // information is cut from the drive, not from the game. `force`
            // is a line the player asked for and must hear. Where the rung's
            // disposition is EARCON rather than SILENT, the sound layer marks
            // the moment instead of the words.
            let text = self.render_silenced(&spoken);
            if self.event_pacer.is_silenced_repeat(&text, key, None) {
                // A keyed standing condition (an engine held at redline, a
                // locked-out air brake) re-fires on a timer by design while
                // the condition holds -- that is what keeps it audible when
                // the rung speaks it. But this gate used to return before
                // ever reaching the pacer, so a silenced repeat still played
                // the earcon and logged the line on every re-fire: the quiet
                // rung machine-gunning a sound where coaching says one
                // sentence and falls silent for the rest of the drive.
                // `is_silenced_repeat`/`note_silenced` deliberately do NOT
                // share `is_repeat`/`conditions` with the speaking path
                // below: if a silenced occurrence wrote `conditions[key]`,
                // raising the rung mid-drive while this same condition was
                // still active would have the speaking path's own `is_repeat`
                // see its silenced text already on file, read the now-audible
                // occurrence as an unchanged repeat, and skip it -- the rung
                // the player raised specifically to hear this condition going
                // quiet instead.
                return;
            }
            if self.settings.speech_disposition(category) == Disposition::Earcon {
                self.play_ladder_earcon(category);
                // The cue is standing in for the words, so it gets the room
                // the words would have had (see engage_earcon_duck).
                self.engage_earcon_duck();
            }
            self.event_pacer.note_silenced(&text, key);
            transcript!(
                "[ladder] {} silenced: {}",
                self.settings.driving_speech,
                text
            );
            if review {
                self.message_log.add(&text, MessageCategory::Event);
            }
            return;
        }
        let Some(text) = self.render_spoken(&spoken) else {
            return;
        };
        if !force && self.ladder_applies() && self.ladder_repeats(&text, category, key) {
            // Said once already, and this rung only promised once. Logged,
            // so the review keys still answer for it.
            transcript!(
                "[ladder] {} already said: {}",
                self.settings.driving_speech,
                text
            );
            if review {
                self.message_log.add(&text, MessageCategory::Event);
            }
            return;
        }
        if self.event_pacer.is_repeat(&text, key, force, None) {
            // Already in the player's ear. Not spoken, not logged, not
            // reviewable: as far as the drive is concerned it never happened
            // a second time.
            return;
        }
        let priority = priority.unwrap_or(if interrupt {
            EventPriority::Critical
        } else {
            EventPriority::Ambient
        });
        if !interrupt
            && priority == EventPriority::Ambient
            && self.settings.sapi_events
            && self.event_pacer.would_start_stale(&text, priority)
        {
            // Chatter that would start speaking after the moment it
            // described is dropped, not promoted to an interrupt: losing it
            // costs the player nothing (the enum's own words), and the old
            // stale-flush made the least important class the only one
            // guaranteed to preempt. The review log still keeps the line --
            // recovery is exactly what the log is for. Not marked heard: the
            // player never heard it, so an identical later moment speaks
            // fresh.
            transcript!("[pacer] stale ambient dropped: {}", text);
            if review {
                self.message_log.add(&text, MessageCategory::Event);
            }
            return;
        }
        transcript!("[event] {}", text);
        self.event_pacer.note_spoken(&text, key);
        let mut cut = None;
        if self.settings.sapi_events {
            if interrupt {
                cut = self
                    .event_pacer
                    .note_interrupt(&text, priority, category, valid);
            } else if self.event_pacer.should_flush(&text, priority, valid) {
                // The channel is backed up past the point of truth: purging
                // and speaking fresh IS the queued line's honest delivery.
                // The purge can still have cut a line that was genuinely
                // mid-sentence, so it is handed back and requeued behind this
                // one exactly as an interrupt's would be -- never dropped.
                transcript!("[pacer] stale event backlog flushed");
                cut = self.event_pacer.take_flush_cut();
                interrupt = true;
            }
            self.speech.say_event(&text, interrupt);
        } else {
            if interrupt {
                cut = self
                    .event_pacer
                    .note_interrupt(&text, priority, category, valid);
                self.speech.stop_main();
            } else {
                self.event_pacer
                    .note_queued(&text, priority, category, valid);
            }
            self.speech.say(&text, false);
        }
        self.engage_speech_duck();
        if let Some(cut) = cut {
            self.requeue_cut_event(cut);
        }
        if review {
            self.message_log.add(&text, MessageCategory::Event);
        }
    }

    /// Step the mix back for an earcon, the way it steps back for words.
    ///
    /// Tester Shane, 2026-08-17: "some of the sounds when you put speech in
    /// quiet mode have been significantly lowered." Measured absolutely they
    /// were not -- the confirmation note came out about 4 dB LOUDER than the
    /// chime it replaced, and a trooper pass never drops below its old
    /// level. Both measurements missed the point, because a listener hears
    /// a level RELATIVE to what is under it.
    ///
    /// A spoken line ducks engine, weather and radio to SPEECH_DUCK_LEVEL
    /// while it talks. A silenced line returns from `say_event` before
    /// reaching that duck, so its earcon played against the full road bed --
    /// roughly 6 dB worse off than the words it stands in for, and quiet is
    /// precisely the rung where confirmation, status and coaching ALL become
    /// earcons. So the sound that carries the information was the one
    /// competing hardest to be heard.
    ///
    /// The window is real seconds and short, because the cues are short: the
    /// longest (the two-note coaching chime) runs 0.18 s. It is not the
    /// pacer's projection, which describes a voice that in this case is
    /// never going to speak.
    fn engage_earcon_duck(&mut self) {
        if !self.settings.duck_audio_for_speech {
            return;
        }
        self.speech_ducked = true;
        self.earcon_duck_until = monotonic_seconds() + EARCON_DUCK_S;
        self.audio.set_speech_duck(SPEECH_DUCK_LEVEL);
    }

    /// Step the game mix back while the event voice speaks (R13).
    ///
    /// XAG 105's guideline made a setting: engine, weather, and the radio
    /// drop to half volume so a warning survives a loud cab without the
    /// voice itself getting louder. Restoration is edge-driven, not polled:
    /// `update_speech_duck` runs once per frame from the main loop and
    /// restores the mix when the pacer's projection -- the same estimate the
    /// staleness budget runs on -- says the voice is done.
    fn engage_speech_duck(&mut self) {
        if !self.settings.duck_audio_for_speech {
            return;
        }
        self.speech_ducked = true;
        self.audio.set_speech_duck(SPEECH_DUCK_LEVEL);
    }

    /// Per-frame: bring the mix back once the event voice falls silent.
    ///
    /// An earcon duck holds for its own short window instead, since the
    /// pacer has nothing to project for a line that was never spoken.
    pub fn update_speech_duck(&mut self) {
        if !self.speech_ducked {
            return;
        }
        if self.earcon_duck_until != 0.0 && monotonic_seconds() < self.earcon_duck_until {
            return;
        }
        if self.event_pacer.busy() {
            return;
        }
        self.speech_ducked = false;
        self.earcon_duck_until = 0.0;
        self.audio.set_speech_duck(1.0);
    }

    /// Whether the mix is currently stepped back under speech.
    pub fn speech_ducked(&self) -> bool {
        self.speech_ducked
    }

    /// Test seam: move the earcon duck's deadline (real seconds).
    pub fn set_earcon_duck_until(&mut self, until: f64) {
        self.earcon_duck_until = until;
    }

    /// A standing condition has cleared; let it announce itself afresh.
    pub fn reset_event_condition(&mut self, key: &str) {
        self.event_pacer.forget_condition(key);
        // TRANSITIONS means enter, worsen and clear. A condition that
        // genuinely cleared and comes back is an ENTER, even though its text
        // is word-for-word what was said last time -- so the last-text
        // memory has to be dropped here too, or standard swallows the second
        // real warning.
        self.ladder_last.remove(key);
    }

    /// The player stepped off the road: silence the road and drop its
    /// backlog.
    ///
    /// Stopping the channel is what actually purges the voice's own queue --
    /// without it, everything the road had submitted before the pause is
    /// still in there and gets performed the moment the player comes back
    /// (tester transcript, 2026-08-11).
    pub fn pause_event_speech(&mut self) {
        self.event_pacer.pause();
        self.speech.stop_event();
    }

    /// Back at the wheel; nothing from before the pause is news.
    pub fn resume_event_speech(&mut self) {
        self.event_pacer.resume();
        self.speech.stop_event();
    }

    /// Mark everything spoken inside `f` as an answer to a control press.
    ///
    /// Wrapped around the driving state's input handlers rather than added
    /// to each readout, for the same reason the pacing rule itself is
    /// central: there are twenty-odd info keys and they gain new siblings
    /// every week, and a rule that has to be remembered per call site is
    /// one that will be missed. Anything spoken from a key press is by
    /// definition something the player asked for.
    ///
    /// Re-entrant and restoring, so a handler that opens a menu which
    /// speaks does not leave the flag stuck on for the ambient lines that
    /// follow.
    pub fn player_asked<R>(&mut self, f: impl FnOnce(&mut GameContext) -> R) -> R {
        let previous = self.player_asked_begin();
        let result = f(self);
        self.player_asked_end(previous);
        result
    }

    /// The two halves of `player_asked` for a handler that cannot take a
    /// closure (a state method that needs `self` and `ctx` both): call
    /// `begin`, keep the token, call `end` with it on every return path.
    pub fn player_asked_begin(&mut self) -> bool {
        let previous = self.speech_requested;
        self.speech_requested = true;
        previous
    }

    pub fn player_asked_end(&mut self, previous: bool) {
        self.speech_requested = previous;
    }

    /// Whether a control press is being handled right now.
    pub fn speech_requested(&self) -> bool {
        self.speech_requested
    }

    /// The leg-scoped FIRST_OCCURRENCE memory: `(key, text)` pairs.
    pub fn ladder_said(&self) -> &std::collections::HashSet<(String, String)> {
        &self.ladder_said
    }

    /// The TRANSITIONS memory: last text per condition key.
    pub fn ladder_last(&self) -> &std::collections::HashMap<String, String> {
        &self.ladder_last
    }

    /// Whether the event voice is mid-delivery right now.
    ///
    /// The same projection the audio duck restores on, so a control that
    /// has to decide "is there anything to shut up" is trusting the estimate
    /// the mix already trusts rather than inventing a second one.
    pub fn event_voice_busy(&mut self) -> bool {
        self.event_pacer.busy()
    }

    pub fn stop_event_speech(&mut self) {
        self.event_pacer.reset();
        self.speech.stop_event();
    }

    /// Silence all in-progress speech on both channels (main and event).
    ///
    /// Menus and readers speak through the main channel, so the
    /// driving-only `stop_event_speech` does not quiet them. This silences
    /// everything so a single key works as a "stop talking" everywhere in
    /// the game.
    pub fn stop_speech(&mut self) {
        self.event_pacer.reset();
        self.speech.stop_main();
        self.speech.stop_event();
    }
}
