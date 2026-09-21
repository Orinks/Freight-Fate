# Learn game sounds

A screen a player can open to hear every cue the road will throw at them, with
its name and what it asks them to do, before it matters at seventy miles an
hour.

Freight Fate teaches its sounds the way real driving does: the first time you
hear one, something is already happening. That works for the engine, which
explains itself, and badly for the edge ladder, the stop-bar tone, the curve
chime and the jake stages, where the sound *is* the information and there is
no second chance to study it. Audio games solve this with a "learn sounds"
list -- arrow through entries, each one plays and says what it means. This is
that, sized to Freight Fate's cue vocabulary.

## What ships

A `Learn game sounds` item on the main menu, next to `How to play`, and the
same screen on the driving pause menu after `Controls and help`. Both push one
state; there is one implementation.

Inside: a category list, then a sound list per category. Arrowing speaks the
entry's name and nothing else, exactly like every other menu in the game.
Enter plays the sound. Enter again replays it. F1 speaks what it means, what
to do about it, and -- where a setting can switch the cue off -- when the
player will actually hear it. Escape stops whatever is sounding and steps
back.

Nothing auto-plays on arrow. A cue that fires while its own name is being
spoken teaches the player the collision, not the cue, and holding Down would
machine-gun the audio.

## The catalog

### Module

`src/freight_fate/sound_catalog.py`, a pure data module: no pygame, no audio
engine, no state. It is a list of categories, each holding entries.

```python
@dataclass(frozen=True)
class Cue:
    """One sounding inside a demo: what to play, how, and when."""
    key: str
    volume: float = 1.0
    pan: float = 0.0
    delay_s: float = 0.0      # after the previous cue in the entry starts
    hold_s: float = 0.0       # >0 = a held loop, released after this long
    fallback: str = ""        # key to use when `key` resolves to nothing

@dataclass(frozen=True)
class SoundEntry:
    name: str                 # the canonical spoken noun, from docs/ontology.md
    plays: tuple[Cue, ...]
    meaning: str              # what it tells you and what to do about it
    when: str = ""            # the setting or situation that gates it, if any
```

The state walks `plays` on a timer, so a two-sided demo, a three-rung ladder
and a held tone are all the same code path.

### Rules the entries follow

**Name from the ontology.** Every entry's name is the canonical spoken noun
for that concept in `docs/ontology.md`. A concept that has no row gets one, in
this change. The whole point is a shared vocabulary; a catalog that invents a
second name for the rumble strip is worse than no catalog.

**Meaning is derived from the code that plays the cue, not from memory.** Each
description is written against the call site -- what condition fires it, what
the player is supposed to do. The descriptions are player-facing spoken text:
no key names the current settings do not give this driver, no maintainer
jargon, no visual-only framing.

**Faithful playback.** An entry carries the real key, volume and pan from its
call site. Panned cues demo both sides in turn, left then right, because the
side is the information. Held loops (low air buzzer, stop-bar tone, air
building, the jake growl, the weigh-station bed) play a bounded few seconds
and stop themselves. Ladders play their rungs in escalating order as separate
entries, so the progression is learnable as a progression: clip the strip,
fully on the strip, off the pavement.

**Settings-gated cues stay listed and are annotated.** A driver on full lane
keeping never hears the edge ladder, but hiding it would make the catalog lie
about the game, and settings change. The `when` line says what turns it on.
This is a reference screen, not live driving advice, so the rule against
naming controls a driver does not currently have does not apply -- but the
annotation is what keeps it honest.

### Categories and entries

Seven categories, 46 entries as shipped. That is a little past the 35-40 the
scope was pitched at; the rule held, the count did not. Nothing here is
ambience, flavour or music, and no entry survives that a player could name on
first hearing. The list below is the intended shape; the implementation
confirms each key against its call site and drops any that turns out to be
unreachable.

**Lane and steering** (11) -- the edge ladder (`vehicle/edge_clip`,
`vehicle/edge_strip`, `vehicle/edge_shoulder`) as three rungs; the road lean
(`vehicle/road` held and panned, the lane guide bed -- the pan is the cue, not
the road noise); back in the lane (`vehicle/lane_centered`); lane line crossed
(`vehicle/lane_line_cross`); the lane locator tock (`vehicle/lane_locator`);
rumble strip (`vehicle/rumble_strip`); dead-man's-curve transverse strips
(`vehicle/transverse_strips`); the curve chime (`vehicle/curve_bink`); the
exit signal tone (`vehicle/signal_tone`).

**Air and brakes** (7) -- air building (`vehicle/air_pressurize`, held); air
dryer purge (`vehicle/air_dryer_purge`); low air buzzer
(`vehicle/low_air_buzzer`); parking brake set and released
(`vehicle/brake_set`, `vehicle/brake_release`); emergency brake
(`vehicle/ebrake`, falling back to `vehicle/brake_air`); tire screech
(`vehicle/tire_screech`).

**Engine brake, speed and shifting** (5) -- the jake growl at two, four and
six cylinders of retard (`engine/jake_*`), demoed at a representative rpm;
overspeed chime (`vehicle/overspeed_chime`); gear grind
(`vehicle/gear_grind`).

**Ramps and stop bars** (3) -- the stop bar's solid tone (`vehicle/bar_solid`,
held); ramp light green and red (`events/ramp_light_green`,
`events/ramp_light_red`).

**Hazards and the road** (10) -- hazard warning (`events/hazard_warning`);
hazard clear (`events/hazard_clear`); construction zone
(`events/construction_zone`); traffic slowing (`events/traffic_slowing`); turn
ahead, left and right (`events/turn_*`); state line
(`events/state_crossing`); toll charged (`events/toll_charged`); the driver's
yawn (`driver/yawn`).

**Enforcement** (7) -- the enforcement marker (`enforcement/signature`), the
cue that arrives before a post can observe you; the police car going by (that
same marker plus `traffic/trooper_pass` 0.2s behind it), which fires *after*
the post and does not mean it was staffed; the siren
(`events/police_siren`); inspection warning (`events/inspection_warning`);
the weigh station approach bed (`poi/weigh_station_lane`, held); spike strip
(`events/spike_strip`); CB chatter (`events/cb_radio_chatter`).

The marker and the pass are two entries, not one, because conflating them is
the mistake this catalog made first: the pass whoosh is deliberately hard to
tell from a civilian one and arrives too late to act on, while the marker is
the game's own guarantee that nothing tickets a driver it never spoke to.
`enforcement/signature` is synthesized at runtime rather than shipped as a
file, so the completeness scan has to union the generated keys or it cannot
see the most important cue on this list.

**The load** (3) -- liquid surge in a tank trailer: the wash
(`vehicle/liquid_wash`, held), the fore-aft strike (`vehicle/liquid_hit`) and
the lateral strike (`vehicle/liquid_hit_lateral`).

### What is deliberately left out

`SELF_EXPLANATORY` in the same module: key, plus the reason, one line each.
An exclusion is a decision on the record, not a gap.

- `engine/*` (idle, low, mid, midhigh, high, start, shutdown) -- it is an
  engine and it sounds like one.
- `radio/fm_hiss_loop`, `radio/picket_*`, `radio/static_burst` -- static means
  weak signal to anyone who has owned a radio, and the one thing the hiss
  predicts (the station drops and the radio falls back to the Roadhouse) is
  spoken aloud when it happens.
- `weather/*` -- rain, wind, snow and thunder name themselves.
- `ambient/*`, `vehicle/road_joint`, `vehicle/truck_door`,
  `vehicle/fuel_pump`, `vehicle/reverse`, `vehicle/horn`,
  `vehicle/brake_squeal`, `vehicle/collision` -- scene and mechanism, no
  decision attached. A collision announces itself by having happened.
- `traffic/car_pass`, `traffic/box_truck_pass`, `traffic/semi_pass` -- a
  vehicle going past sounds like a vehicle going past. `traffic/trooper_pass`
  is catalogued because it marks an enforcement post, which is not audible
  from the sound alone.
- `vehicle/gear_shift` and the `vehicle/shift_manual` / `vehicle/shift_auto`
  banks -- a gear change in a truck that is changing gear.
- `poi/facility_gate`, `poi/rest_stop_night` -- ambient beds for a place the
  game has already named out loud.
- `facility/dock_gate`, `poi/dock_and_deliver` -- menu feedback at a facility,
  not road cues.
- `ui/*` -- menu feedback, learned in the first ten seconds of the main menu.
- `music/*` -- songs.

`vehicle/road` appears in neither list as a plain bed: it is catalogued once,
as the road lean, because what teaches the player something is its pan.

## The state

`src/freight_fate/states/learn_sounds.py`, two `MenuState` subclasses:

- `LearnSoundsState` -- the category list. Each item pushes the sound list for
  its category. Its own help explains Enter plays, F1 explains, Escape stops.
- `LearnSoundCategoryState` -- the entries in one category. `MenuItem` label is
  the entry name, `help` is `meaning` plus `when`, and the action starts the
  demo.

Demo playback lives in the category state:

- A small scheduler advances `plays` in `update(dt)`: fire each `Cue` at its
  `delay_s`, and for a cue with `hold_s > 0` re-assert `audio.hold_alert` (or
  hold the loop channel) each frame until it expires, then release.
- Starting a new demo cancels the running one first, so mashing Enter or
  arrowing away never layers two demos or strands a loop.
- `exit()` cancels and releases unconditionally. A held tone must not be able
  to outlive the screen -- the same dead man's switch rule `hold_alert`
  already enforces for the stop bar.

Opening from the pause menu is safe without extra work: `PauseMenuState.enter`
already calls `stop_world()`, so the engine, road, weather and any held alert
are down before the catalog is reachable, and demos play against silence. The
drive resumes untouched.

`lines()` mirrors the spoken content for the window, as every state does.

## Tests

`tests/test_sound_catalog.py`:

1. **Every catalogued key resolves.** Each `Cue.key` exists in the committed
   sound tree or the pack, or declares a `fallback` that does. Guards against
   an entry that silently plays nothing -- the worst failure this screen can
   have, because it teaches the player that a real cue is silent.
2. **Completeness.** Scan `src/` for cue keys passed to `audio.play`,
   `play_bank`, `hold_alert` and `start_loop`. Every key found is either in
   the catalog or in `SELF_EXPLANATORY`. A new cue added without a catalog
   entry fails the suite, which is what keeps this from rotting.
3. **Names are ontology nouns.** Every entry name appears in
   `docs/ontology.md`.
4. **Copy rules.** No entry name or description is empty; descriptions carry
   no maintainer jargon or file keys; `when` is present on every entry whose
   cue is gated by a setting.

`tests/test_learn_sounds_state.py`, driving a fake audio engine:

5. Arrowing speaks the name and plays nothing.
6. Enter plays the entry's cues with the catalogued key, volume and pan; a
   two-sided entry plays left then right.
7. A held cue is released when its `hold_s` expires, when a new demo starts,
   and when the state exits.
8. F1 speaks the meaning and the `when` note.
9. The item exists on both the main menu and the pause menu, and pushes the
   same state.

## Player-facing changes

A `## Unreleased` / `Added` changelog entry: a new Learn game sounds screen on
the main menu and the pause menu, where every cue the road uses can be played
on demand with what it means and what to do about it.

`ROADMAP.md` gains the feature under the 1.9 line.

`docs/user-manual-1.9-draft.md` and the `How to play` reader get a short
pointer -- one line each, saying the screen exists and where. The catalog
itself is not duplicated into prose; it would go stale immediately and the
screen is the better place to learn a sound anyway.

`docs/ontology.md` gains rows for any cue concept that does not have one, and
for the screen itself.

## Out of scope

- **A side drill.** Play a random side, press Left or Right to name it. A good
  idea and a separate feature; it needs scoring, repetition and its own tests,
  and the catalog has to exist first.
- **Volume mixing inside the screen.** Demos honour the player's existing
  audio settings. Adjusting them belongs in Settings, Audio.
- **The two dead assets found while scoping this.** `vehicle/lane_drift` and
  `vehicle/turn_signal` exist in the sound tree and nothing in `src/` plays
  them; the drift cue is the edge ladder now. Recorded here and on the
  roadmap; removing them or wiring them back up is its own change, and the
  completeness test is what surfaced them.
