# 1.9 Final Slate — track plan (2026-07-27)

The release freeze is amended, not lifted. `feat/career-1.9` takes bug
fixes plus exactly the items below, which Josh (release owner) named.
Everything else stays on `feat/career-2.0`. The driving school stays
gated (`DRIVING_SCHOOL_ENABLED = False` on 1.9 — no school changes).

Working rules for every track:

- Cut a short feature branch **off `feat/career-1.9`** (not 2.0 — 2.0
  carries the un-gated school and must not leak back). Push to `fork`.
- Merge point is the main window (Phil). When your track is done, leave
  a done marker in `logs/` (a small JSON: branch, tip SHA, what shipped,
  tests run) and stop. Phil folds: full-tree conflict-marker grep, full
  suite green (`uv run pytest`, check the exit code, never tail alone),
  then merge to 1.9 and a same-day 1.9 -> 2.0 merge.
- Player-facing work needs a `CHANGELOG.md` bullet under Unreleased in
  player language (entries are read aloud). Move the matching ROADMAP
  bullet in the same change. Test the spoken result and say how.
- Audio assets: synth for sustained/noise beds, real transients only
  from licensed sources (Splice yes, NAS measure-only). Looping beds
  are WAV, never Vorbis (seam clicks) — delete any ogg twin.

## Track A — Ring spectra rebuild (ff-audio window, "Phil 2")

Branch: `sound/ring-rebuild` off `feat/career-1.9`.

The queued engine-voice follow-on: rebuild the ring spectra from 4-6 s
cuts per the recipe in the audio window's own session notes (the
generation scripts are gone; the recipe survives in the engine-voice
handoff). Constraints: keep the shipped voice architecture (formant/air
banks, jake voice, auto-jake, cruise, shift sigh) — this is a spectra
quality pass, not a redesign of the voice. The anti-repetition wobble
and loop-seam fixes are locked; do not regress them. A/B against the
current build and hold the result to the owner's ear before the done
marker.

## Track B — Curve navigation + rumble strips (main window, Phil)

Branch: `feat/curve-nav` off `feat/career-1.9`.

One system, not two. Design authority stays in the main window because
it couples input, trip physics, and audio:

- Lateral position becomes real: a lane/offset state on the trip with
  steering keys, replacing pure speed-management through curves.
- The edge boundary ladder provides the audio: in-lane guidance is the
  panned bed; edges grade by periodicity, with the synthesized rumble
  strip as the outermost shoulder cue (the real sound is absent from
  the sound library; synthesis is also the licensed-clean path).
- Curves consume the baked real-geometry advisories (63,724 curves)
  that already drive the spoken pacenotes; steering demand follows the
  same demand model the decompression logic uses.
- Josh's ask verbatim: "real speeds in for curves as well as panning
  sounds so we can steer through them." The speeds are already real;
  the steering and panning are this track.
- Owner add-on (2026-07-27): once the tone generation exists, the
  turn-signal clicks that mark lane changes become tones too, panned
  to the signaling side -- the soft relay click is hard to hear for
  some players. Not an invented cue: modern cabs play designed
  indicator tones through the speakers; the bare relay click is the
  vintage sound (and can return later as era equipment).

## Track C — NPR translator radio batch (ff-radio window, Oatis)

Branch: `map/radio-npr-translators` — ALREADY RUNNING. Keep going
exactly per the assignment in that worktree's STATUS.md. One change:
the destination is now **1.9**, not 2.0. The branch was cut from 2.0,
so Phil will fold it into 1.9 by cherry-picking the data/changelog
commits (a straight merge would drag 2.0's un-gated school along).
Nothing for the radio window to redo — keep commits data + changelog +
roadmap only, as assigned.

## Track D — Multilane easy slice (ff-map window, Oatis)

Branch: `feat/multilane-speech` off `feat/career-1.9`.

Josh's "multilane if it's easy," honestly scoped. The lane-count data
is already baked into the world (96.3% of legs, from the lane-data
bake); this track wires it into SPEECH ONLY:

- Road status / route briefing speak the lane count in plain words
  ("two lanes your side", "divided, three lanes").
- A spoken callout when the count changes mid-leg ("road widens to
  three lanes", "down to one lane your side").
- Respect verbosity settings; no callout spam on data noise — collapse
  runs shorter than ~2 miles into the neighboring value.
- Explicitly OUT: traffic, passing, lane-position mechanics — lateral
  position belongs to Track B (same axis as steering), and anything
  with other vehicles is 2.0. If a data gap turns up (legs with no
  lane counts speak nothing, never a guess), note it in the done
  marker rather than patching world data ad hoc.

Sequencing note: Tracks B and D both touch trip/driving speech. D is
speech-wiring only and should land FIRST (it is small); B rebases on
top. If D finds itself needing trip-state changes, stop and flag Phil
instead of making them.

### Track D2 — divided-flag bake (ff-map, after D's done marker)

Track B needs a baked `divided` flag per leg so the left road edge can
sound like what it is: a median on a divided highway, the centerline
with oncoming traffic on an undivided one. Only `lanes` is baked today;
Phil infers in the meantime (interstate = divided, one lane per side =
undivided) and the multilane US/state middle needs real OSM data.
Full brief queued in the ff-map window's STATUS.md. Data-only branch
off 1.9, honest-absence rule, done marker as usual.

## Fold order

1. Track D (small, speech only) -> 1.9.
2. Track C cherry-picks (data) -> 1.9, whenever its marker lands.
3. Track A (audio assets + mixer wiring) -> 1.9 after the owner's ear
   signs off.
4. Track B last (largest surface, rebases on D).
5. After each fold: 1.9 -> 2.0 merge, fork CI watched to green.
