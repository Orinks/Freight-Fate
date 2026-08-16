# Speech redesign stage S4: the driving verbosity ladder

**Status:** design, awaiting owner sign-off
**Owner report:** ROADMAP.md, "Drive-time chattiness: even terse is far too
much (owner, 2026-08-15)"
**Predecessors:** `docs/speech-priority-research.md` (R1-R15, all landed in
stages S1-S3 on 2026-08-12)

## The problem, stated exactly

S2 gave every message a normal and a terse rendering, and terse compressed
each one. The owner's report is that the drive is still too chatty, and the
reason is structural: **compression does not reduce the number of things
spoken.** A drive that says thirty short things is still a drive that says
thirty things.

The requirement, in the owner's words: a long drive in the quiet mode should
be mostly engine, road, and radio -- speech should feel like an event.

## Why the current design cannot deliver that

R1 gave informational speech an **urgency** axis: `EventPriority` in
`speech_pacing.py`, three classes, deciding how long a line waits behind
other speech and whether it may be dropped when stale.

There is no **category** axis. Nothing in the code records what a line is
*about*. With no category tag, the only available lever is length -- which
is precisely the lever S2 pulled, and precisely the one that did not work.

So S4 adds one orthogonal tag, threaded exactly the way `priority` already
is through `say_event`, and a named ladder that cuts whole categories.

## Scope boundary: flavor is not governed here

**Owner directive, 2026-08-15:** billboards, place names, landmarks and the
rest of the roadside colour are **not** gated on this ladder. They keep the
switches they already have -- `CHATTER_FIELDS` (parks, rivers, passes,
museums, billboards) and the `place_callouts` ladder -- which the owner set
deliberately that day and does not want changed.

This ladder is for **the information a player needs**, for players who want
less of it. A player may run the loudest flavor settings and the quietest
information rung at the same time; that combination is intentional and must
keep working.

Achievements are flavor for this purpose and stay outside the taxonomy. R9
already reduced them mid-drive to earcon plus name.

## The six informational categories

A new `SpeechCategory` enum. Membership is decided by what the line is
about, never by how urgent it is -- urgency is `EventPriority`'s job and the
two tags are independent.

| Category | Membership |
| --- | --- |
| `SAFETY` | hazard calls, collision, off-pavement, pull-over commands, out-of-service |
| `NAVIGATION` | turns, exits, planned stops, destination, checkpoints, zone entries |
| `MONEY` | tolls charged, fines, citations |
| `COACHING` | technique tails -- "ease down and leave room", load-damage advice |
| `CONFIRMATION` | outcome reports -- cleared it, held the line, backed up, latch caught |
| `STATUS` | speed drift, gaps, weather shifts, non-urgent HOS, redline and low-air bands |

## The ladder

`DRIVING_SPEECH_MODES = ("coaching", "standard", "quiet", "urgent_only")`.

| Rung | safety | money | navigation | coaching | confirmation | status |
| --- | --- | --- | --- | --- | --- | --- |
| `coaching` | full | full | full | full | full | full |
| `standard` | full | full | full | first occurrence | full | transitions |
| `quiet` | terse | terse | terse | earcon | earcon | earcon |
| `urgent_only` | terse | terse | act-now cues only | silent | earcon | silent |

### What the dispositions mean

The table's cells are five defined dispositions, not adjectives:

- **full** -- speaks, normal rendering.
- **terse** -- speaks, terse rendering. Never silence.
- **first occurrence** -- speaks in full the first time the condition arises
  in a leg, silent on later escalations of the same condition. This is R11's
  behavior, generalized from load-damage coaching to the whole category.
- **transitions** -- speaks when the state is entered, when it worsens, and
  when it clears; silent while the state merely persists. This is R12's
  behavior, generalized from off-pavement to the whole category.
- **earcon** -- does not speak; the sound layer carries it and the line goes
  to the message log. Requires a learn-sounds row (invariant 3).
- **silent** -- does not speak and makes no sound; the line goes to the
  message log and stays reachable by the status keys.

`NAVIGATION` at `urgent_only` is **act-now cues only**: the turn, exit, or
stop the player must act on within the current decision window speaks;
everything else in the category (progress, distance-to-go, upcoming-stop
previews) goes silent. The decision window is the same one
`_exit_intent_ready` already computes for exit traffic, so this reuses a
boundary the code has rather than inventing one.

### Invariants the ladder may not violate

1. **`SAFETY` and `MONEY` never fall silent at any rung.** R1's never-dropped
   contract outranks the ladder. A rung may choose the terse rendering; it may
   never choose silence. Pinned by test.
2. **Nothing cut becomes unreachable.** Every category the ladder silences
   still reaches the message log and stays answerable by the existing
   status-query keys. This is what R1's "What NOT to change" section protects
   and what makes cutting legitimate rather than hiding.
3. **Every earcon that replaces words is learnable** in
   `states/learn_sounds.py`. This is R14's standing rule and it binds S4's new
   substitutions. No new meaning-bearing earcon ships without its row.
4. **The ladder never applies before `tutorial_done`.** R15's exemption is
   unchanged and now covers the rung as well as the rendering.

### Rendering

The rung selects the rendering, so `SpokenMessage` is untouched:
`coaching` and `standard` render normal, `quiet` and `urgent_only` render
terse. `SpokenMessage.render(terse: bool)` keeps its present signature.

## Principle (4): announce on change, not on state

The pacer's `key=` parameter already implements this -- a keyed line "speaks
when it starts and again only when what it says has changed"
(`app.py::say_event`). The mechanism is complete; the coverage is not.

S4's second deliverable is an audit pass giving a `key=` to every `STATUS`
and `CONFIRMATION` line that currently re-reads a state the player has not
changed. This is finite and testable: the transcript harness
(`tools/playtest_break.py --transcript`) shows repeated state lines directly,
and each one fixed is a regression test asserting the second identical read
never reaches the voice.

## Implementation shape

**`settings.py`**
- Add `driving_speech: str = "standard"` and `DRIVING_SPEECH_MODES`.
- Remove `speech_verbosity`. Only 11 references exist across 7 src files --
  the S2 pair mechanism already centralized it -- so a compatibility shim
  would cost more than it saves.
- Migrate under a `SETTINGS_VERSION` bump to 3: saved `speech_verbosity` 0
  becomes `quiet`, 1 becomes `standard`, anything else becomes `standard`.
  Same shape as the `chatter_villages` -> `place_callouts` migration at
  `settings.py:552`.
- `speaks(category) -> bool` and `renders_terse() -> bool` on `Settings`, so
  the rung table lives in exactly one place.

**`speech_pacing.py`**
- Add `SpeechCategory`. It lives beside `EventPriority` because the two tags
  travel together, but nothing in the pacer's projection reads it -- the
  pacer's core is R1's "do not change" list.

**`app.py`**
- `say_event(..., category: SpeechCategory | None = None)`. The ladder gate
  runs *before* the `SpokenMessage` render, so a silenced category never
  renders and never reaches the voice, the log gate, or the duck.
- `say()` takes the same parameter for driving-time main-channel lines.
- A `None` category is treated as `SAFETY` -- speaks at every rung. An
  untagged line is a call site nobody has classified yet, and the failure
  mode must be "too loud", never "silently dropped a warning".

**Call-site tagging** is the bulk of the work: every `say_event` site gets
its category. `driving_events.py` (31 priority sites) and
`driving_updates.py` (6) are the concentrations.

**`states/main_menu.py`**
- `_cycle_verbosity` becomes `_cycle_driving_speech`, cycling the four rungs
  the way `_cycle_place_callouts` cycles its three.
- The row label becomes `Driving speech: <rung>`. The existing help text
  ("Controls how often driving status reminders speak") finally describes
  what the control does; it currently describes length, which is what it
  actually controlled.

## Player-facing copy

Rung names spoken as: "coaching", "standard", "quiet", "urgent only". Each
gets a row in `docs/ontology.md` alongside the existing verbosity vocabulary,
per the standing rule that a new concept means a new ontology row in the same
change. The four names are the canonical spoken nouns; "terse" survives only
as the internal rendering flag and is retired from player-facing text, since
the player now picks a rung rather than a length.

`CHANGELOG.md` gets an entry under `## Unreleased` / `Changed`: the setting a
player already knows changes shape, which is exactly the kind of thing the
changelog gate exists for.

## Testing

- **Rung table**, pinned as data: for each rung and category, the expected
  disposition. One table test, so a future edit to the table is a visible
  diff rather than a behavior surprise.
- **Invariant tests**: safety and money speak at every rung; no rung silences
  them; `None` category speaks at every rung.
- **Migration tests**: `speech_verbosity` 0 and 1 land on the right rungs; an
  out-of-range value lands on `standard`; a settings file already carrying
  `driving_speech` is untouched.
- **Flavor independence**: the loudest chatter settings with `urgent_only`
  still speak billboards, and `coaching` with all chatter off still speaks no
  billboards. This is the owner's directive as an executable assertion.
- **Announce-on-change**: per keyed line, a second identical read never
  reaches the voice.
- **Transcript comparison**: the same scenario under
  `tools/playtest_break.py --transcript` at each rung, asserting the spoken
  line count falls monotonically as the rung tightens. This is the closest
  thing to the owner's actual complaint that a test can express.

## Deliberately out of scope

Principles (1) and (3) from the roadmap entry -- the systematic sonification
pass converting spoken state updates to the earcon layer, and the per-minute
spoken-event budget at cruise -- are the deeper half of the owner's report
and get their own stage. S4 builds the ladder they will both need: (1) needs
a category tag to know what to convert, and (3) needs one to know what to
coalesce first.
