# Speech priority and verbosity research

Research notes, 2026-08-12. Not shipped documentation: this is the evidence
base for deciding how the spoken interface should prioritize, interrupt, and
shorten. Read part 1 for what the game does today (with transcript numbers),
part 2 for what mature screen readers and accessible games do, part 3 for the
numbered recommendations.

Three complaints drove this research:

1. Important messages can be lost when newer speech interrupts them; the
   message log and replay key recover them, but recovery is not prevention.
2. Some messages are too verbose in every speech mode.
3. Terse mode still announces far too much for the advanced players it is for.

Method: read of the whole speech stack (`app.py` say/say_event,
`speech.py`, `speech_pacing.py`, `states/driving_events.py`,
`settings.py`); deterministic headless transcripts generated with the
playtest battery (`tools/playtest_break.py`) run per scenario in both
speech modes; parallel web research with citations. No pytest, no game
window, no source edits.

A scope note on the transcripts: the battery rig records every line the game
*submits* to speech (it replaces `ctx.say`/`ctx.say_event` with recorders),
so counts are pre-pacer — repeat suppression and stale-flush would trim a few
of these lines in real play. That bias is small and works against the
complaint, so the verbosity numbers below are conservative.

Known in-flight work this report deliberately does NOT restate (a fix is
already being implemented): requeue of cut-off ROUTE/CRITICAL lines, an
interrupt guard on the info keys, and ROUTE priority on the weigh-station
notice. Every recommendation here layers on top of those.

---

## Part 1 — the current system

### 1.1 Two channels, and only one of them has discipline

- **Main channel** — `ctx.say` (`src/freight_fate/app.py`), Prism to the
  player's screen reader. **535 call sites**, and the signature default is
  `interrupt: bool = True`. No pacer, no priority, no repeat suppression.
  Menus, tutorial, achievements, arrival/settlement text all speak here.
- **Event channel** — `ctx.say_event`, a dedicated second voice (SAPI by
  default, `settings.sapi_events`). **176 call sites.** Every line passes
  `EventSpeechPacer` (`src/freight_fate/speech_pacing.py`, commit
  `d6d79b45`): repeat window 2.5 s, standing-condition keys (speak on start,
  again only on change), backlog projection with per-priority wait budgets,
  purge on pause/resume.
- **Review**: every spoken line lands in the categorized message log
  (comma/period walk it, brackets switch category, Ctrl+C copies —
  `states/base.py`), and A replays the last route announcement
  (`driving_controls.py:819`). This is a solid recovery layer.

The asymmetry is the structural cause of complaint 1: the event channel now
has real pacing, but a main-channel line (achievement, assist notice, menu
speech) still lands with `interrupt=True` by default and can stamp on
anything — including the screen-reader reading the player asked for.

### 1.2 The priority taxonomy as it stands

`EventPriority` (AMBIENT / ROUTE / CRITICAL) with wait budgets 3.0 s / 0.8 s /
always-interrupt. The mapping (`driving_events.py::_event_priority` and
`_is_critical_event`):

| Today's class | Members | Delivery |
| --- | --- | --- |
| CRITICAL | HAZARD, ZONE_ENTER, CHECKPOINT, zone GPS cues, traffic cues | always interrupts |
| ROUTE | STOP_AHEAD, planned-stop events | queues, 0.8 s patience, stale → interrupt |
| AMBIENT | everything else (weather, tolls, state lines, chatter) | queues, 3.0 s patience, stale → interrupt |

Two observations:

- **CRITICAL is broad.** A zone entry or checkpoint notice interrupts exactly
  like a collision warning. Since an interrupt purges the channel, each new
  CRITICAL erases whatever CRITICAL was mid-word — this is the loss mechanism
  the in-flight requeue addresses, but the class membership itself makes the
  collision more frequent than it needs to be.
- **Nothing may be dropped.** AMBIENT lines that go stale get *promoted to an
  interrupt* rather than discarded — the flush "purges the dead backlog" by
  speaking the stale line on top of everything. For chatter whose loss "costs
  the player nothing" (the enum's own words), external practice (part 2)
  says drop, not promote.

### 1.3 The verbosity system, quantified

One binary setting: `speech_verbosity` (0 terse / 1 normal; the chatty tier
was retired — `settings.py:270,496`). Orthogonal switches that already exist:
five roadside-chatter category toggles, the `place_callouts` ladder
(off/sparse/all), `announce_menu_position`, and the routine speed-callout
interval. (`overspeed_warning` was on this list until 2026-08-15, when the
setting was removed: the alert had armed at the same 5-over pace adaptive
cruise holds, and raising the threshold to 7 left nothing to switch off.)

Coverage: verbosity is consulted at **~79 sites** total (65 of them the
`_terse_speech()` helper in driving states), against **176 `say_event` + 535
`say` call sites**. Most spoken text never consults the mode. In particular
`ctx.say`/`say_event` themselves are verbosity-blind — every terse variant is
a hand-built branch at the call site.

Transcript counts, same deterministic drive in each mode
(`tools/playtest_break.py` scenarios; lines are submissions, see scope note):

| Scenario | Normal | Terse | Terse kept |
| --- | --- | --- | --- |
| assists_fight_descent (~12 game-min) | 24 | 8 | 33% |
| floor_it_through_town (~24 game-min) | 20 | 13 | 65% |
| neutral_coast_mountain (~27 game-min) | 31 | 20 | 65% |

What terse successfully drops: periodic speed callouts, roadside chatter,
"Through the bend, held your line" confirmations, descent/climb/cruise
coaching. What terse still speaks **in full**:

- Achievements with 2–3 sentences of flavor, mid-drive, even between hazard
  lines ("New achievement! Bumper-to-Bumper Blues. Heavy traffic, and you
  kept the following distance sane. The road runs long and life moves fast on
  it, so you let the jam breathe instead of tailgating into a mess.").
- The composite curve line, four times in one descent, near-identical:
  "Sharp left, half a mile. Advise 35 miles per hour. Adaptive cruise easing
  to 35 miles per hour for the bend."
- The full facility line with type prefix and instruction: "travel center:
  Flying J Travel Center Corfu at exit 48A in 5 miles. confirmed truck
  parking. Press X to signal for the exit."
- Toll accounting, twice per toll (ahead + charged): "E-ZPass toll charged at
  New York State Thruway settlement: Estimated 15 dollars, billed to carrier
  settlement."
- Hazard coaching tails and pats on the back: "Ease down and leave room for
  38 miles per hour." / "You slow nearly to a stop and ease around it. Well
  done."

So terse mode's product today is "normal minus the easy 35–65%", not "the
minimum an expert needs" — which matches complaint 3 exactly.

Two defects found while diffing modes. First: **terse suppresses the
first-drive walkthrough itself** (`driving_core.py::Tutorial` — at
verbosity 0, `begin()` and every reminder return early, and the stage
confirmations shrink to "Parking brake released." / "In gear." /
"Rolling."). A brand-new player who flips to terse before their first drive
— exactly the player who hates chatty games — never hears that the status
key, the help key, or hazard warnings exist, and cannot pull information
they were never told about. Verbosity is a filter on running commentary;
first-run teaching is not commentary (see R15).

Second: terse rewrites the dodgeable hazard
call to **"Brake or swerve!"** (`driving_core.py::terse_hazard_message`)
while normal mode and the help teach **"Brake or change lanes"**
(`main_menu_help.py:309`). That is a synonym for the single most
safety-critical cue in the game, delivered only to the players who turned
explanations off — the exact drift `docs/ontology.md` exists to prevent.

### 1.4 The worst verbose offenders, all modes

From the full-battery transcripts (settlement, hazard, microsleep, dispatch
scenarios), the patterns that dominate spoken time:

1. **Facility type prefix + proper name + city, every mention.**
   "cross-dock Chicago Cross-Dock in Chicago, Illinois" is spoken six times
   during one pickup; "port Port of Indiana-Burns Harbor in Gary, Indiana"
   five times during one delivery. The type prefix duplicates a word already
   inside most proper names ("cross-dock … Cross-Dock", "port Port of …").
2. **Double scaffolding in the wheel-entry line.** "Weather: Simulated
   weather: rain, 30 degrees." — two labels for one fact.
3. **Instructions the player has demonstrably outgrown.** "Press E to start
   the engine and build air pressure. F1 lists the controls." is appended to
   every "You are at the wheel" line forever, tutorial done or not; "Press X
   to signal for the exit" rides every stop callout forever.
4. **Achievement flavor at the wrong moment.** 2–3 sentences of (good) comedy
   delivered mid-drive on the main channel, including six read back-to-back
   inside the settlement menu.
5. **Toll bookkeeping twice per toll**, both lines carrying "billed to
   carrier settlement".
6. **Coaching tails repeated on every escalation.** Each worsening
   load-damage report re-ends with "Brake and corner gently from here."; each
   collision is followed by the full "Total damage N percent" sentence.
7. **Standing conditions restated verbatim.** "Off the pavement, into the
   median on the left! Steer back toward the lane center." seven times in a
   row (the pacer's condition keys can suppress identical text, but the road
   position line is regenerated each time and identical anyway — in the real
   game the 2.5 s repeat window thins this; the condition still deserves a
   key plus escalation instead of a loop).
8. **Zero-information settlement rows.** The 25-item settlement readout
   includes "Carrier charges are not deducted from driver pay", "No new
   damage recorded", "Fuel remaining: 100 percent", "Truck damage now: 0
   percent" — rows that say nothing happened.
9. **The dispatch board reads the full job composite twice back-to-back**
   (board intro repeats item 1's entire text: cargo, origin, destination,
   miles, gross, deadline, equipment, pay, lane note).
10. **Speed-limit nag with fixed phrasing.** "Watch your speed. The limit is
    65 miles per hour." recurs at full length (its own toggle exists, but the
    phrase never shortens on repetition).

---

## Part 2 — external practice

### 2.1 Screen reader and platform conventions

**NVDA: the highest priority is cut-then-RESUME, by design.** NVDA's speech
subsystem has exactly three priorities (`Spri.NORMAL` / `NEXT` / `NOW`).
`NOW` "should be spoken right now, interrupting low priority speech. After
it is spoken, interrupted speech will resume"; `NEXT` barges in at the next
utterance boundary without cutting anything. Losslessness was a stated
design requirement of the speech refactor ("without losing lower priority
utterances already sent"), not an accident.
- https://github.com/nvaccess/nvda/blob/master/source/speech/priorities.py
- https://github.com/nvaccess/nvda/issues/4877
- Open proposal for an "idle" tier (speak low-priority lines only after N ms
  of silence): https://github.com/nvaccess/nvda/issues/13915

This is the strongest external validation of the in-flight requeue work: the
reference screen reader treats interrupted speech as something to resume,
not something the player should have to dig out of a log.

**User input always wins.** NVDA and JAWS both cut current speech on
keystrokes (configurable "speech interrupt for typed characters" / "Typing
Interrupt"). The player's own action is a universal, sanctioned interrupt
source — which is what the in-flight info-key guard formalizes in reverse
(the player's *query* should not destroy a pending warning).
- https://download.nvaccess.org/releases/2026.1/documentation/userGuide.html
- https://supportcenter.lexisnexis.com/app/answers/answer_view/a_id/1124308

**JAWS: interruption is accepted as lossy, and the recovery is a log.**
Speech History (Insert+Space, H) keeps the last 500 spoken announcements in
a reviewable viewer — the same shape as Freight Fate's message log.
- https://support.freedomscientific.com/teachers/lessons/5.5.1_SpeechHistory.htm

**ARIA live regions: two politeness levels, and "assertive" is feared.**
The spec defines `polite` as "presented at the next graceful opportunity"
and `assertive` as highest priority, presented immediately; `role="alert"`
is assertive + atomic. The spec deliberately does not define what happens to
pending speech; in practice assertive often *clears the queue*
(cut-and-discard), and MDN warns "don't use the assertive value unless the
interruption is imperative." Real-world live-region delivery is inconsistent
enough that a successor API (`ariaNotify`) is being designed.
- https://www.w3.org/TR/wai-aria-1.2/#aria-live
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live
- https://www.sarasoueidan.com/blog/accessible-notifications-with-aria-live-regions-part-1/

**Windows UIA NotificationProcessing: the most explicit interrupt/queue/
coalesce taxonomy in any mainstream API.** Two orthogonal axes — urgency
(Important vs not) and coalescing (All / MostRecent / CurrentThenMostRecent).
`ImportantAll` carries a documented flooding warning; `MostRecent` exists so
stale, superseded updates are dropped rather than read late; and Windows
build 26100 *added* `ImportantCurrentThenMostRecent` ("don't interrupt the
current notification, as it is considered important and must be allowed to
finish") — the OS-level acknowledgment that hard cuts destroy information.
- https://learn.microsoft.com/en-us/windows/win32/api/uiautomationcore/ne-uiautomationcore-notificationprocessing

**SAPI is all-or-nothing.** Speak calls queue by default;
`SPF_PURGEBEFORESPEAK` purges *everything* pending. No priority, no partial
purge, no resume — any nuanced policy must be built above the synthesizer,
which is exactly what `EventSpeechPacer` is.
- https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms717252(v=vs.85)
- https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms719820(v=vs.85)

### 2.2 Audiogames and accessible mainstream games

**Forza Motorsport's Blind Driving Assists — the closest cousin to Freight
Fate.** A spoken co-driver announces discrete route facts (turn number,
direction, severity 1–6), while *continuous* state — track-edge position,
apex, braking point — is carried by stereo-panned tones, never speech. Each
cue set is individually toggleable with per-cue pitch/volume, and every cue
has an in-menu preview. Tester Steve Saylor initially heard "a cacophony of
sound" until he tuned per-cue volumes — the strongest evidence that
per-cue mixers, not global presets, are what make a dense cue stack usable.
- https://news.xbox.com/en-us/2023/04/27/forza-motorsport-accessibility-features-blind-driving/
- https://kotaku.com/forza-motorsport-xbox-blind-accessibility-options-race-1850829331

**The Last of Us Part II.** Fixed earcon vocabulary (traversal cues, combat
cues) catalogued in a browsable Audio Cue Glossary; sonification (pitch =
height) instead of speech for scanning; a frequency dial (Off / Sometimes /
Frequent) for prompts; and repeat-on-demand status via Touch Pad Swipe Up.
- https://www.naughtydog.com/blog/the_last_of_us_part_ii_accessibility_features_detailed

**Sequence Storm.** Gameplay is deliberately not spoken: per-lane earcons
taught in an explicit trainer, with TTS reserved for menus and cutscene
descriptions. The community's version of "speech gets quieter as skill
grows" is exactly this — learn the cues in a trainer, then play speech-free.
- https://www.familygamingdatabase.com/en-us/accessibility/Sequence+Storm

**Swamp / A Hero's Call — the audiogame baseline.** Earcons carry the world
(loot is "a fly sound"; beacons and audio radar carry navigation), TTS is
reserved for menus and *pulled* status (`/where`, `/time`, `/stats` query
commands); A Hero's Call splits three ways: earcons for space, TTS for
UI/inventory, recorded voice for narrative.
- http://www.blackscreengaming.com/swamp/commands/index.php
- https://afb.org/aw/19/3/15113
- (Caveat: audiogames.net blocks automated fetches, so forum thread
  contents are characterized from search excerpts, not full reads; Swamp's
  exact verbosity toggles could not be pinned to a citable source.)

**Hearthstone Access — pull-model speech under time pressure.** Nearly
everything is an on-demand hotkey layered from summary to detail (read
hand, read next valid play, reread current option, more info on focused
card), so the player decides how much of the rope timer to spend on speech.
- https://hearthstoneaccess.github.io/

**Xbox Accessibility Guidelines — the citable industry anchor.**
XAG 106 (Screen narration): moving focus "should immediately stop" current
narration; "players should be able to quickly cancel/repeat narration";
"don't overdo narration... too much narration can easily get repetitive and
distracting"; an option to disable enumeration narration; recurring timed
notifications "every 7-10 seconds so as not to interfere with other
narration." XAG 105 (Audio): per-category volume sliders, and "an option to
automatically lower or mute game audio when audio output from assistive
technologies such as a screen reader is detected" — ducking as an explicit
guideline. XAG 103: audio cues "can provide a better experience than
in-game narration."
- https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/106
- https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/105
(Note: CTA-2087, floated as a possible source, turned out to be an XR
accessories standard with nothing on speech priority; XAG is the right
citation.)

**Game Accessibility Guidelines** (gameaccessibilityguidelines.com/full-list/):
"Provide separate volume controls or mutes for effects, speech and
background / music"; "Keep background noise to minimum during speech";
"Ensure sound / music choices for each key objects / events are distinct
from each other"; "Ensure screen reader support, including menus &
installers"; and — directly on point for a trucking sim — "Provide a voiced
GPS" (http://gameaccessibilityguidelines.com/provide-a-voiced-gps/).

**Community conventions** (AFB AccessWorld deep dive,
https://www.afb.org/aw/fall2023/Blindness-Accessibility-in-Video-Games-A-Deep-Dive):
threshold announcements instead of continuous speech (health at 75/50/25/
15/10%), dedicated keys to speak information on demand, and artificial
sounds (beeps, chimes) for object/proximity state vs natural sounds for
context.

### 2.3 Auditory display and warning research

- **Urgency mapping** (Edworthy, Loxley & Dennis 1991; Hellier & Edworthy
  1999): the perceived urgency of a warning sound should match the
  situational urgency, and it can be engineered quantitatively (speed,
  frequency, repetition, inharmonicity). For *spoken* warnings, wording and
  delivery style carry urgency independently (Hellier et al. 2002).
  https://journals.sagepub.com/doi/10.1177/001872089103300206 ·
  https://journals.sagepub.com/doi/10.1518/0018720024494810
- **Earcons** (Blattner et al. 1989; Brewster et al. 1995): structured audio
  motives in families of related messages; concurrent same-family earcons
  interfere with each other (McGookin & Brewster), so serialize rather than
  overlap. https://sonification.de/handbook/download/TheSonificationHandbook-chapter14.pdf
- **Alarm standards**: IEC 60601-1-8 encodes priority in the signal itself
  (distinct burst patterns for high vs medium), and its 2020 amendment added
  category "auditory icons" to fight alarm fatigue; ISO 7731 defines three
  urgency tiers. Small, acoustically distinct tier counts are the norm.
  https://array.aami.org/content/news/updated-iec-60601-1-8-breaks-new-ground-development-alarm-sounds ·
  https://www.iso.org/obp/ui/en/#!iso:std:33590:en

### 2.4 Synthesis

When a high-priority message arrives mid-utterance, mature systems do all
four things — **tiered by urgency, as documented convention**:

1. **Queue (lossless) is the default** for ordinary messages (SAPI default,
   NVDA NORMAL, ARIA polite, UIA `All`).
2. **Coalesce/drop is a first-class policy for superseding or stale
   messages** (UIA `MostRecent`; XAG's 7–10 s cadence for recurring state;
   audiogame threshold announcements). Stale telemetry is dropped, not read
   late.
3. **Cut is reserved for genuine urgency and treated warily** (ARIA
   assertive warnings; UIA `ImportantAll` flooding warning) — except when
   the *player* initiates it, which always wins.
4. **Cut-then-resume is the state of the art** (NVDA `Spri.NOW`; Windows'
   new `ImportantCurrentThenMostRecent`): what an urgent message cut should
   come back, automatically.
5. **Ducking belongs to the game-audio-vs-speech layer** (XAG 105), not the
   speech-vs-speech layer; screen readers do not duck speech under speech.
6. **Every mature system pairs interruption with a recovery path** (JAWS
   Speech History, TLOU2 status swipe, Hearthstone reread keys) — a log plus
   repeat-on-demand, which Freight Fate already has.
7. **Verbosity control converges on per-category toggles + pull-model query
   keys**, with earcons replacing speech for continuous/high-frequency
   state once players learn them in a trainer/glossary (Forza, TLOU2,
   Sequence Storm).

---

## Part 3 — recommendations

Numbered; each carries an effort estimate (small / medium / large) and its
evidence type (external practice, transcript data, or both).

### 3.1 The priority taxonomy (keep the enum at three, tighten the contract)

**R1. Give each EventPriority class an explicit delivery contract, and
narrow CRITICAL.** (medium; both)

| Class | Membership rule | Delivery contract | Verbosity may suppress? |
| --- | --- | --- | --- |
| CRITICAL | act *now* or lose something: hazard calls, collision, off-pavement, pull-over commands, out-of-service | interrupt; requeue whatever it cut (in-flight); never suppressed, never dropped | never |
| ROUTE | act *soon*, or a consequence that must be heard: planned stop, destination exit, turn cues, weigh-station notice (in-flight), zone entries, checkpoints, **money lines** (toll charged, fine, citation) | queue with short patience; stale → interrupt; requeue if cut; **never dropped** | terse may shorten, never drop |
| AMBIENT | costs nothing to miss: weather, toll *pre-announcements*, state lines, chatter, confirmations, achievements | queue with long patience; **stale → drop silently** (still logged for review) | terse drops most of it |

Money is a consequence, not chatter: a charged toll or a fine that a busy
stretch could silently age out would make normal mode *lossier* than terse
mode's "what it cost" guarantee. So money lines ride ROUTE's never-drop
contract (the toll-ahead heads-up stays AMBIENT — losing the preview costs
nothing once the charge itself is guaranteed).

**Coupled invariant — the zone-entry demotion must not ship without this.**
A dropped speed limit earns braking-grace seconds, but the grace *collapses
to zero if the accelerator is held* during the window
(`driving_updates.py::_limit_drop_grace_s` — "staying on the throttle
through the drop is disregard"). A player whose zone-entry line is waiting
out the 0.8 s ROUTE budget is necessarily still on the throttle — nobody
has told them anything yet — so demoting the line alone would let speech
latency masquerade as disregard and burn the whole grace window from the
zone boundary. Therefore: the accelerator-held collapse must not arm until
the zone-entry line has actually been spoken (equivalently, the first
`WAIT_BUDGET_S[ROUTE]` seconds of the grace window are exempt from the
throttle check). An implementer who cannot take the coupling takes the
fallback instead: speed-zone ZONE_ENTER stays CRITICAL and only checkpoints
demote.

The two changes from today: zone entries and checkpoints move from CRITICAL
to ROUTE (they are act-soon, not act-now, and each interrupt is a chance to
erase a real warning), and stale AMBIENT is dropped instead of being promoted
to an interrupt — the current stale-flush turns the *least* important class
into the only one guaranteed to preempt. The review log keeps the dropped
line, which is exactly what the log is for.

External backing: three tiers matches NVDA's entire priority model and ISO
7731's tier count (2.1, 2.3); stale-drop is UIA `MostRecent` semantics and
the audiogame threshold convention (2.1, 2.2); interrupt-plus-requeue is
NVDA `Spri.NOW`'s documented cut-then-resume and Windows'
`ImportantCurrentThenMostRecent` (2.1) — the in-flight requeue work is
implementing the state of the art, and this table just keeps the classes
honest around it.

**R2. Bring the main channel under the same discipline during a drive.**
(medium; transcript data) `ctx.say` defaults to `interrupt=True` with no
pacer. Any driving-time main-channel line (achievements, assist notices,
buff expiry) should either move to `say_event` with a priority, or at
minimum default to `interrupt=False` while the driving state is active.
Menu/screen reading keeps its interrupt default — that mirrors how screen
readers cancel on navigation.

**R3. Pair every genuine interrupt with a class-distinct earcon,
*concurrent* with speech onset.** (small–medium; external practice) The
game already pairs many events with sounds. The earcon plays on the
game-audio mixer, which is a different output path from the SAPI voice —
nothing forces serialization, and a serial "tone, then words" prefix would
add its full duration to the latency of the actionable verb on the one
channel where 0.8 s already counts as too long (at 70 mph, 200 ms is 6 m).
So: fire the class earcon at speech onset, concurrently; if any serial
prefix is ever wanted, cap it near 150 ms and count it inside the CRITICAL
delivery budget. The long-term win is explicit: experienced players come to
react to the *tone* and treat the words as confirmation — the Forza /
Sequence Storm endpoint (2.2) — which is why the tone must be per-class
distinct, not decorative. Urgency encoded in the signal itself per the
alarm-design standards and Edworthy/Hellier urgency mapping (2.3); keep the
class-to-sound mapping small and acoustically distinct (ISO 7731), and
never overlap two cues from the same family (McGookin & Brewster, 2.3).

### 3.2 The terse-mode contract

**R4. State and enforce a terse contract.** (medium–large; both) Proposed
contract, one paragraph:

> Terse mode promises: the truck will tell you what to *do* and what it
> *cost*, and nothing else. Every safety call, route instruction, and money
> consequence still speaks — in the shortest form the ontology allows —
> and everything that is color, confirmation, coaching, or congratulation
> is an earcon or silence. If the road is quiet, terse mode is silent.
> Terse never applies before the first-drive walkthrough completes.

Two rules that bound every terse rewrite:

- **Compress words, never certainty.** A qualifier that changes a decision
  survives terse. Parking certainty is the worked example: the vocabulary
  is five-valued (`data/world_constants.py::PARKING_CERTAINTY_LABELS` —
  confirmed / likely / limited / unknown / none), it is Jason's Law data a
  driver planning a 10-hour rest is deciding on at 70 mph, and every value
  must stay distinguishable in terse: "Parking confirmed." / "Parking
  limited." / "No truck parking." / "Parking not verified." (the normal
  labels compressed, no new words — "unverified" would be a synonym).
  "Likely" is already spoken as silence in normal mode (its label is the
  empty string, a pre-existing design choice); terse mirrors normal
  exactly, so silence keeps meaning "likely" and nothing else — but note
  for the owner that this silent value predates terse and deserves its own
  look. Every row below gets this review: which qualifiers are
  load-bearing?
- **A fixed terse grammar, recorded in `docs/ontology.md`.** Slot order is
  part of the contract — hazards as [thing, distance, target speed]
  ("Brake lights, 2 miles, 38."), stops as [name, exit, distance,
  qualifier]. A bare trailing number is only parseable because the frame
  never shuffles; document the frame where the nouns live so future terse
  lines cannot reorder the slots.

Concrete category dispositions, with transcript lines:

| Category | Today in terse | Should be |
| --- | --- | --- |
| Hazard calls | full ("Brake or swerve! Slow car right ahead.") | keep, but fix the synonym: "Brake or change lanes! Slow car ahead." (R8) |
| Hazard coaching tails ("Ease down and leave room for 38 miles per hour.") | spoken | shorten to the number that matters: "Brake lights, 2 miles, 38." |
| Dodge confirmations ("You slow nearly to a stop and ease around it. Well done.") | spoken | outcome earcon only — a distinct success/fail *pair*, both in the learn-sounds screen (R14): "did I clear it?" may never be ambiguous |
| Curve + cruise composite (×4 identical) | full | "Sharp left, half a mile, advise 35." — the cruise clause becomes the cruise's own earcon |
| Facility/stop callouts | full incl. "Press X…" | "Flying J Travel Center Corfu, exit 48A, 5 miles. Parking confirmed." No key instruction (R7); the parking qualifier survives (rule above) |
| Achievements | full flavor | earcon + name only: "Bumper-to-Bumper Blues." Flavor waits in the log/menu (R9) |
| Tolls | both lines, full accounting | pre-announce drops (AMBIENT); charged line always speaks (ROUTE, R1): "Toll, 15 dollars, carrier." |
| First-drive walkthrough | suppressed entirely | exempt from verbosity until `tutorial_done` (R15) |
| Speed-limit nag | full sentence | "Limit 65." (the overspeed alert is separate and no longer has a toggle; it arms at 7 over) |
| Speed callouts, tutorial, chatter, bend confirmations | already silent | keep silent |

**R5. Make `say_event` verbosity-aware instead of hand-branching 65 call
sites.** (medium; transcript data) Accept a normal/terse text pair, so
coverage stops depending on every author remembering `_terse_speech()`.
The 79-of-711 coverage number in part 1 is the argument. Two guards, or
this mechanism *generates* the drift R8 just caught (the swerve bug
happened precisely because the terse variant lived in a separate function
nobody diffed against the help text):

- The pair is **co-located in one message definition** — one place where a
  reviewer sees both forms side by side — never a bare second string typed
  at a distant call site.
- Safety-critical pairs are **pinned by copy tests** (the repo already has
  copy-test conventions): a test fails when one side of a hazard/route
  message changes without the other being looked at.

**R15. First-run guidance ignores verbosity.** (small; transcript data)
The walkthrough, its reminders, and the "here are your keys" lines speak in
full until `tutorial_done`, regardless of `speech_verbosity` — terse's
contract begins where teaching ends. Today terse silences the tutorial
outright (part 1.3), which orphans exactly the new player most likely to
pick terse on day one, and quietly breaks the pull-model premise that every
push-line the game retires stays reachable by a key the player knows about.
The gate is `tutorial_done` itself, not verbosity history: a player who
finishes the walkthrough and then flips terse on gets no resurrected
tutorial lines — the exemption is over because the teaching is over.

### 3.3 Verbosity in every mode

**R6. Adopt a first-mention-full, then-short naming rule.** (medium;
transcript data) "cross-dock Chicago Cross-Dock in Chicago, Illinois" six
times in one pickup is the single worst offender. First mention per stop
speaks the full form; after that, the proper name alone ("Chicago
Cross-Dock"), and the type prefix is dropped whenever the proper name
already contains it ("port Port of Indiana-Burns Harbor" → "Port of
Indiana-Burns Harbor"). Canonical nouns are untouched — this removes
repetition, not vocabulary. Reset triggers for "first mention": a new leg,
and resuming after a pause or save — anywhere the player may have lost the
thread, the full form comes back once.

**R7. Retire instructions the player has demonstrated.** (medium; both)
"Press E to start the engine… F1 lists the controls" on every wheel entry,
and "Press X to signal for the exit" on every stop callout, forever. Gate
each on a small profile counter (spoken until the player has performed the
action N times), the same way `tutorial_done` already gates the walkthrough.
Retirement must **re-arm when the hint would change**: counters are keyed
to the control binding and transmission mode they were earned under, so a
mid-career settings flip or a differently-equipped assigned tractor speaks
the new hint afresh — the standing rule that spoken advice never names a
key the current settings don't give this driver cuts both ways (never name
a wrong key; never go silent where the key is now different).

**R8. Fix the terse hazard synonym.** (small; transcript data) Terse mode
says "Brake or swerve!" where normal mode and the help teach "Brake or
change lanes" — one canonical phrase for the highest-stakes cue, per
`docs/ontology.md`. *(Also record the decision in the ontology's hazard row.)*

**R9. Move achievement flavor out of the drive.** (small–medium; transcript
data) Mid-drive: earcon + "New achievement: <name>." Full flavor text speaks
where the player is stationary (settlement, pause menu, log review). In the
settlement readout, collapse the six full achievement rows into "6 new
achievements" with the names, details on demand.

**R10. Strip zero-information rows from composite readouts.** (small;
transcript data) Settlement: drop "Carrier charges are not deducted from
driver pay", "No new damage recorded", "Fuel remaining: 100 percent",
"Truck damage now: 0 percent" when they report the unremarkable default —
speak them only when non-zero/abnormal. Dispatch board: stop reading the
full job composite twice back-to-back (intro + item 1).

**R11. Coaching tails speak once per condition, not per escalation.**
(small; transcript data) "Brake and corner gently from here." belongs on the
first load-damage report only; later escalations speak the new number
("Load damage 43 percent, claim territory."). The pacer's condition keys
already support exactly this — the tails just need to move out of the
re-generated text.

### 3.4 Supporting moves from external practice

**R12. Standing conditions: speech on transitions, a continuous cue in
between.** (medium; both) The seven verbatim "Off the pavement, into the
median on the left!" lines in part 1.4 are speech carrying a *continuous*
quantity — and part 2.2's own lesson (Forza) is that continuous state
belongs in panned tones, never in repeated sentences. Split it:

- **Speech only at state transitions**: left the pavement, back on it,
  getting worse (deeper off, speed rising). Same for redline and low air —
  entered the band, left the band, band worsened. The pacer's condition
  keys already store the last thing said, so "say something new or stay
  quiet" is one comparison away.
- **A continuous panned cue carries the state between transitions** — a
  surface-rumble loop panned to the side the truck went off, an engine
  strain tone for redline — so "where am I right now" never needs a
  sentence at all.
- XAG 106's 7–10 s cadence ("so as not to interfere with other narration")
  is the *fallback* for a genuinely discrete recurring notification with no
  continuous cue (a timer, an objective) — not the model for road position.

**R13. Duck game audio under speech, as a setting.** (medium; external
practice) XAG 105's explicit guideline: lower game audio while assistive
speech is playing. The game has per-channel volume settings already
(master/weather/engine/ui); a "duck engine and weather while the event voice
speaks" option is the missing piece, and it directly helps warnings survive
loud moments without raising speech volume. The 1.9 radio joins the ducked
set — a streaming station is the loudest thing in the cab. (GAG: "Keep
background noise to minimum during speech.")

**R14. Every earcon that replaces words joins the learn-sounds screen.**
(small, ongoing rule; external practice) The game already has a sound-
learning screen (`states/learn_sounds.py`) — the same pattern as TLOU2's
Audio Cue Glossary, Forza's cue previews, and Sequence Storm's trainer.
Make it a standing rule of R3/R4: no earcon may carry meaning that is not
learnable there, and any earcon that reports an *outcome* ships as a
distinct success/fail pair (the dodge confirmation in R4's table is the
first case). That is what makes "terse mode replaces words with sounds"
legitimate rather than exclusionary.

### 3.5 What NOT to change

- **The two-voice design** (screen reader for UI, dedicated voice for the
  road) — separation of narration and world is the pattern mature titles
  converge on.
- **The pacer's core**: backlog projection, repeat window, standing-condition
  keys, pause/resume purge. This is genuinely ahead of most of the field.
- **The review log + replay key.** JAWS ships a 500-entry Speech History for
  exactly this reason, and XAG 106 requires cancel/repeat on demand; keep A
  and the comma/period walker exactly as they are.
- **The status-query keys** (speed key, status menu, HOS summaries, F1).
  Pull-model speech is *the* audiogame convention (Hearthstone Access,
  Swamp's query commands, AFB's 'H'-for-health pattern) — and it is what
  makes R7's instruction-retirement safe: the information never becomes
  unreachable, it just stops being pushed.
- **Per-category chatter toggles and the place_callouts ladder** — per-category
  opt-outs on top of a global mode is the convention, not a redundancy.
- **The three-member priority enum.** More classes is how these systems rot;
  the fix is membership and contracts, not new tiers.
- **Deadline-relative staleness** (WAIT_BUDGET_S) — dropping/flushing by
  "would this start too late to be true" is better than fixed queue caps.
