# Synthesized music: a no-AI music source

Date: 2026-09-21. Status: approved 2026-09-21.

## Why

Some players do not want AI-made music in the game. The menu beds, the
Roadhouse drive beds and the Roadhouse host breaks are mostly Suno, Eleven
Music and ElevenLabs output. This adds a second music source the game
composes itself, plus the three 1.5-era synth tracks restored. It does not
replace the radio: the other stations stay as they are, and tuning to them
is the player's choice.

## What the player gets

### Settings

Settings, Audio gains two rows:

- **Music source: Original / Synthesized.** Default Original. Spoken with
  its effect: "Music source: Synthesized. Menu music and the Roadhouse
  station play music made by the game itself, with no AI-made songs or
  voices." Changing it restarts the current rotation at once.
- **Music seed.** Reads "Music seed: 48213" (five digits). Enter rolls a
  new one and says it: "New music seed, 71904. Every synthesized piece is
  new." The current rotation restarts at once. Settings is reachable from
  the pause menu, so this works mid-drive. Typing a seed in is out of scope
  until players ask for it.

Both are global settings, not per career, so a seed sounds the same on any
career and can be shared.

### Menus, Synthesized

Every place that plays menu music today (title, city terminal, pickup
facility, facility arrival) plays synthesized pieces instead. The borrowed
radio instrumentals drop out of the menu rotation.

The milestone ladder follows the career path:

| Rung | Everyone | Company driver | Leased or independent |
|---|---|---|---|
| 0 | New hire | | |
| 1 | First run | | |
| 2 | Regional | | |
| 3 | | Senior company driver | Fleet owner |
| 4 | | Top hand | Coast to coast |
| 5 | | Trainer | Legendary haul |
| 6 | | Million-mile driver | Road legend |

Rung thresholds are exactly the existing ones in `menu_milestone_index`
(`crates/ff-core/src/music.rs`), rung for rung, with one change for the
synth ladder only: rung 1 unlocks on level 2 or 3 deliveries, not on a
truck other than `rig`. A company driver's carrier tractor is not a
milestone. (Rung 3's "two trucks owned" clause stays; a company driver
reaches rung 3 on level 5 as today.)

The branch is read from `business_status` every time music is chosen:
going back to company driving moves the career to the company branch, and
buying in moves it to the owner branch. The Original ladder is unchanged.

A brand-new career opens on the restored 1.5 "Headlights West"
(`classic_menu_theme`), as it did in 1.5. After dark the synth night-menu
style leads, as the night theme does today.

The company branch is steady and warm; the owner branch is broader with
more drive. Each rung has its own key, tempo and instrumentation so a rung
change is audible.

### Driving, Synthesized

The Roadhouse keeps its name and dial position and plays synthesized day and
night beds, with `classic_open_road` (day) and `classic_night_haul` (night)
in the rotation. It schedules no host breaks, station IDs or jingles, since
those are AI-voiced. Every other station is unchanged. Volumes, the radio
key and radio off are unchanged.

Now playing names a synth piece by a generated title: "Synthesized: First
Rig, number 3." A classic reads "Headlights West, from Freight Fate 1.5",
and likewise "Open Road" and "Night Haul".

### The radio dial

Owner rulings, 2026-09-21:

- **Music source Original:** the radio is exactly as today, with
  streamer-safe on or off.
- **Synthesized, streamer-safe off:** Freight Fate's own fictional stations
  leave the dial. The dial and the category key cycle the synthesized
  Roadhouse, terrestrial stations, web streams and personal playlists.
- **Synthesized, streamer-safe on:** the synthesized Roadhouse is the only
  station. Station commands (tuning, seek, categories, favorites, the
  station browser, playlists) do nothing and say nothing. The radio key
  still turns the radio on and off; volume and now playing still work.
- Menus play synthesized music whenever Music source is Synthesized.

### Tracker modules

Dropped as a separate feature (owner, 2026-09-21): personal radio playlists
already carry a player's own music. The game learns to play tracker modules
(`.it`, `.xm`, `.s3m`, `.mod`, `.mo3`, as OpenMPT saves them) through
`BASS_MusicLoad`, so a playlist entry can be one.

### Vocabulary

"Synthesized music" is a new canonical noun; add its row to
`docs/ontology.md` in the same change.

## How it works

### `ff-core::music_synth` (headless)

No audio device, no threads; testable with `cargo test -p ff-core`.

- `Style`: key, tempo range, progression pool, voices, drum pattern pool,
  mood. One per place: the three shared rungs, four company rungs, four
  owner rungs, night menu, day drive, night drive (14 styles).
- `compose(style, seed) -> Score`: sections (intro, A, B, A, outro), a
  chord per bar from the style's progressions, a bass line, a melody drawn
  from the scale over the chords, and drums where the style has them. Its
  own seeded RNG, independent of `pyrandom`, so a piece never changes once
  shipped. Length varies piece to piece, 90 seconds to 5 minutes;
  the classics keep their own lengths.
- `render(&Score, sample_rate) -> Vec<i16>`: the 1.5 voice set (soft pad,
  plucked lead, sine bass, brushed-noise percussion), a light reverb, fade
  in and out, peak-normalised with headroom. 22,050 Hz stereo, about 8 to 26 MB
  per piece.
- Piece seed = hash(style id, music seed, track index).

### `ff-core::music_synth::worker` (worker)

- One worker thread, a bounded request channel (capacity 2), results back on
  a channel the loop polls. The loop never waits on a render.
- The menu rotation and the Roadhouse request the next piece one track
  ahead. The worker composes, renders, wraps a WAV header and calls
  `register_generated_sound("music/synth_<style>_<seed>", ...)`. The
  rotation times the track from the composed score's length, which needs
  no render.
- If a piece is not ready when a track ends, the classic for that place
  plays instead (menu: `classic_menu_theme`; day drive: `classic_open_road`;
  night drive and night menu: `classic_night_haul`).
- Four rendered pieces are kept registered; older ones are released, except
  that a piece among the last four requests (each rotation's current and
  next piece, for the menu and the Roadhouse at once) is never released.
- A render checks the cancel flag as it goes, so a quit mid-render stops it
  and publishes nothing.
- Shutdown: signal cancel, stop accepting requests, join within a measured
  bound, log each step. Nothing in `Drop` beyond signalling.
- A full request queue drops the new request; the rotation falls back to
  the classic and asks again on the next track.

### Hooks into existing code

- `select_menu_music_sequence` and the Roadhouse playlist builder check
  `music_source` and return synth keys (and classics) instead of pack
  tracks.
- The Roadhouse break planner (`radio_content::plan_break` path) plans no
  break when the source is Synthesized.
- Changing either setting restarts the active rotation (menu or radio).
- No BASS changes: generated sounds already play through
  `stream_create_mem`, as the siren and ladder earcons do.

### Classics

`menu_theme.ogg`, `open_road.ogg` and `night_haul.ogg` are restored byte for
byte from `v1.5.0` (`src/freight_fate/assets/sounds/music/`) as
`classic_menu_theme`, `classic_open_road` and `classic_night_haul`, packed in
`sounds.pak`, not `music.pak`, so Synthesized mode never needs the music
pack download. `CREDITS.md` records them as procedurally generated by
`tools/generate_audio.py` (removed in `e751db73`).

## Tests

- Same style and seed give an identical score and identical PCM (hash
  pinned).
- Every style renders within its length bounds, peaks under full scale, and
  is not silent.
- Different music seeds give different pieces for the same place.
- Rung selection: company, leased and independent careers land on the right
  branch and rung; switching business status switches branch; rung 1 no
  longer fires on the tractor alone.
- Menu rotation with Synthesized on contains only synth keys and classics.
- The Roadhouse with Synthesized on plans no host break.
- A slow or dead worker falls back to the place's classic, and the rotation
  keeps going.
- Rolling a new seed restarts the rotation and speaks the new seed.
- The settings rows speak as specified.
- A module in a place folder joins that place's rotation and is named by
  title and composer; a broken player file is skipped, not fatal.
- Agent-server listen pass: the menu and a Roadhouse drive with Synthesized
  on, then an owner listening pass for how it actually sounds.

## Out of scope

- Changing stations other than the ones the dial rules above take off or
  lock (the owner's 2026-09-21 rulings brought that filtering into scope).
- AI-made sound effects and speech outside music.
- Typing in a seed.
- Exporting generated pieces as `.xm` sketches for OpenMPT.
- Event stingers (delivery, level up): none exist today.
- Changing the Original ladder's rung-1 rule.

## Changelog and roadmap

One Added bullet for the Music source setting, one for the Music seed, one
for the restored 1.5 tracks. A ROADMAP bullet under the 1.9 line; follow-ups
(typed seeds, more voices) as unchecked bullets.
