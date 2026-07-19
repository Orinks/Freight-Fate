# Sound-hunt brief: rebuild the library index, curate by need

For Oatis (or any agent running on a machine with NAS access). The
previous sweep's outputs (2026-07-09) were saved to a session scratchpad
and are gone; this run recreates them in permanent homes. `[skip
changelog]` on every commit — maintainer tooling, nothing player-facing
until sounds actually ship.

## The library

`\\romeyserv\share\sounds\high quality\` — 63,849 pro SFX files (BBC,
Sony, Hollywood Edge, Sound Ideas, AKAI, and more; Sound Ideas is the
best-labeled). Filenames are descriptive; search the manifest, never
browse the tree.

## Deliverables (permanent locations, not scratchpads)

1. `\\romeyserv\share\sounds\manifest.txt` — one-time filename manifest:
   `find . -type f \( -iname "*.wav" -o -iname "*.mp3" -o -iname
   "*.flac" -o -iname "*.aif*" \) > manifest.txt` from the share root.
2. `docs/sound-shortlist.md` in THIS repo, committed — per need below:
   8-15 candidate files each (full library-relative paths), one line on
   why each looks right, flagged best-guess first. Filename matching
   only; Norm auditions by ear in Reaper and makes the calls.
3. Per need, ALSO include an **ElevenLabs section**: 2-3 ready-to-paste
   text-to-SFX prompts Norm can run himself (he has ElevenLabs with a
   clean commercial license), written concretely — duration, character,
   what to avoid ("a single dry woodblock tick, 200 milliseconds, no
   reverb tail" beats "a click"). Where the library candidates look
   thin for a need, say so plainly and lead with the prompts. YouTube
   goes in only as CC-licensed leads (search terms plus the license
   filter to use), never ordinary videos — per the sourcing ladder.

## Needs, priority order

1. **Curve cue tones (NEW, highest).** Short one-shot blips, chimes,
   indicator ticks, sonar-style pings, marimba/woodblock notes — clean,
   under half a second, pleasant at high repetition, distinct from the
   game's existing ui/notify and ui/tick. This seeds the pacenote cue
   (panned warning tone, shipped with a placeholder) plus the planned
   curve-entry and back-to-center tones (owner's discrete tone ladder,
   docs/steering-sound-rfc.md section 1b). Grep seeds: `blip, chime,
   ping, sonar, indicator, marimba, woodblock, xylophone, bell.?tree,
   click.?tone, beep`.
2. **Rumble strip + gravel shoulder (edge textures).** Loopable or
   loop-cuttable road textures: `rumble, gravel, shoulder, washboard,
   corrugat, dirt.?road, cattle.?guard`.
3. **Turn-signal relay.** A real flasher-relay click pair: `turn
   signal, indicator, relay, flasher, blinker`. Owner's field spec
   (rode with his dad, 2026-07-18): very staccato, very sharp, TWO
   tones alternating -- close to but not exactly an octave apart --
   the relay closing (higher tick) and releasing (lower tock) at
   roughly 80-90 per minute. ElevenLabs prompt seed: "a car turn
   signal relay: alternating two-tone mechanical tick-tock, sharp
   staccato clicks about 50 milliseconds each, the second click lower
   in pitch, dry, no reverb, no engine noise." DESIGN NOTE: the same
   high/low pair is the intended grammar for the curve tone ladder
   (high tick = curve entry, low tock = back to center), so shortlist
   candidates whose two tones would also work solo as one-shots.
4. **Driveline clunk + air/turbo for shifts.** The shift-sound gap:
   `clunk, driveline, gear.?engage, air.?release, turbo, wastegate,
   hiss`.
5. **Brake-release air sigh** (forum request): `air.?brake, brake
   release, air release, psshh, pneumatic`.
6. **Repair / rig-wear foley (recreate lost list).** Impact wrench,
   tire work, hydraulic lift, compressor, hand tools. Best
   sub-libraries: Sound Ideas "platinum sounds / Industrial 1", General
   Series 6000, BBC Construction (043).
7. **Mini-game / UI stingers (recreate lost list).** Trivia ding,
   buzzer, timer, applause, eating, scale-house. Sony Vol.4 Vintage
   Cartoon, cartoon/, AKAI.

## Known non-answers

- **Jake brake is NOT in this library** (confirmed 2026-07-09; not on
  freesound either). Do not burn time re-searching. The plan is one
  clean exhaust pop retriggered at RPM/20 (inline-6), sourced via
  ElevenLabs SFX first. Out of scope for this sweep.
- Never rip ordinary YouTube audio. Provenance for anything that ships
  goes in CREDITS.md.

## Method

Manifest grep + parallel Explore agents for the fan-out (keep file
dumps out of context, return curated lists only). No audio playback is
expected or possible — filename curation only, explicitly labeled as
unauditioned.
