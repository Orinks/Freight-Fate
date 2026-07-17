# Steering by ear: design notes (ours to build)

Phil's brainstorm, parked 2026-07-16 while Josh was offered the audio
design lead. Josh passed the same day ("you handle this"), so this
file is the working design again. Norm posted the open questions to
the audiogames.net forum 2026-07-16; community answers get folded in
as they arrive, and if the thread stays quiet, we build from these
notes with Phil's recommendations as the defaults.

## The problem in one sentence

The road data is done -- 63,725 real curves nationwide, each with
direction, radius, and a physics advisory speed -- so steering is now
purely a perception problem: how a blind driver feels the lane, hears
the bend coming, and steers through it for a ten-hour haul rather than
a three-minute race.

## What the game already has to build on

- Curve records (direction, radius, advisory speed, at-mile) shipped
  under world_data/us/gameplay; grade data per leg; real posted-limit
  zones.
- A lane model with continuous offset, discrete lanes, drift, wind and
  curve inputs already plumbed (lane.update takes curve= and wind=).
- Two speech channels plus a positional audio engine with panning,
  and controller rumble.
- The honesty rule shipped for ramps: warnings timed in REAL reaction
  seconds, never compressed ones. Curves inherit it.

## Prior art: Forza Motorsport's Blind Driving Assists (2023)

Co-developed with blind consultant Brandon Cole; he won races with it.
The pieces, per Xbox Wire and Kotaku's coverage:

- Spoken co-driver guidance (rally-style, turns described ahead).
- Sonar-style tones for track edges and progress through a turn.
- A deceleration cue that conveys HOW MUCH braking is needed, and a
  shift cue for manual gearboxes.
- The steering guide: pans the ENGINE AND TIRE sounds you already
  hear toward the direction you should steer. No new tone added; the
  car's own voice leans and you chase it back to center.
- Every cue individually toggleable, pitch- and volume-adjustable,
  and PREVIEWABLE from the accessibility menu before driving.

Sources:
- https://news.xbox.com/en-us/2023/04/27/forza-motorsport-accessibility-features-blind-driving/
- https://kotaku.com/forza-motorsport-xbox-blind-accessibility-options-race-1850829331
- https://blindgamingclub.com/forza-motorsport/

## The design so far: five layers

1. PACENOTES (the co-driver). Spoken curve calls from the real
   records: "Sharp left, quarter mile, advise forty-five." Severity
   from radius (gentle / moderate / sharp / hairpin). Advisory speed
   spoken only when it is below current speed. U reads the next few;
   the D safe-speed key folds curve advisories into its one number.

2. SILENCE IS CENTERED. On a straight, a centered truck is quiet.
   Drift raises a soft textured cue on the drift side, growing with
   offset. Reasoning: a continuous centering tone maximizes
   information per second but turns a long haul into ear fatigue; the
   lane should only speak when it has something to say. (Norm and
   Phil agreed 2026-07-16; still worth stress-testing with the
   community -- see question two.)

3. THE ROAD LEANS WHEN IT BENDS (the pursuit guide). Through a curve
   the existing road/engine bed pans along the arc; the driver steers
   to bring it back overhead. Straights silent, bends sing. Why
   pursuit: human-factors research distinguishes compensatory
   tracking (null an error signal -- layer 2) from pursuit tracking
   (chase a moving target); pursuit is reliably more accurate because
   the target shows where things are GOING. Norm proposed the
   follow-the-tone idea independently; Forza's panned-bed steering
   guide is the fatigue-friendly version of it, and physics does the
   demand honestly underneath: lateral acceleration v^2/R biases
   drift toward the outside of the bend, scaled by the same grip
   model as traction (ice, worn tires, chains all change the shove).

4. EDGES THAT NAME THEIR SIDE. The two lane edges get DIFFERENT
   TEXTURES, not just different pan: rumble strip on one side, gravel
   shoulder on the other, so a driver with single-sided hearing still
   knows which way they wandered. Crossing a dashed lane line gets a
   soft paint-and-dots tick, the clearly-quieter kin of the edge
   rumble (Norm's idea, same night, roadmapped).

5. EVERY CUE AUDITIONED FIRST. Forza-style preview of each sound
   from Settings, plus a driving-school lesson that teaches the whole
   grammar on the flat practice road before it matters at speed.

## Open questions (ask the community and Josh)

1. STEERING FEEL ON A KEYBOARD. Hold-to-sweep (holding the arrow
   banks the wheel further; release self-centers like real caster) vs
   tap-to-nudge (each tap steps sideways a fixed amount; nothing
   moves unasked) vs something from a game that got it right. Phil
   recommends hold-to-sweep with self-centering -- holding against
   the curve's pull for the length of the bend is the actual work of
   driving, and self-centering makes letting go safe on a straight --
   but this is the most open of all the questions. Analog
   pad.steering stays the smoother option either way.

2. IS SILENCE-IS-CENTERED RIGHT? Or should a quiet continuous
   center reference exist as an option? Ask specifically: people who
   drove games with a constant centering tone -- did you grow to rely
   on it or to hate it after an hour?

3. WHAT IS THE CURVE GUIDE? The panned road/engine bed, a dedicated
   tone tracing the bend, or both as separate options? Phil leans
   panned bed as default (no new sound source to fatigue) with a
   dedicated tone as an opt-in training wheel.

4. WHICH GAMES TO STUDY? What did each get right that nobody else
   did, and what mistake must not be repeated? (War stories beat
   votes: "what wore you out after an hour" is the gold answer.)

5. CURVE CALL LANGUAGE. Plain "sharp left" vs rally "left three,
   tightens" vs a setting for each. Phil recommends plain language as
   the only mode at first -- this is a truck and a career, thousands
   of calls, and jargon is a separate skill to teach. Rally mode can
   arrive later as a setting if asked for.

## Settled, not up for consultation

Real-reaction-seconds warnings; per-side edge textures; previewable
cues; the curve DATA (already shipped); plain-language default for
everything the game speaks.

## For Josh specifically

- Which preset owns the curve tier? Proposal: a new
  DRIVING_ASSIST_FIELDS entry so his presets govern it -- All assists
  keeps today's auto-curve behavior unchanged, Realistic means you
  drive the bends yourself.
- Does he know a driving game whose steering-by-sound we should copy
  outright? He has played far more of them.
- If he wants to build any of it himself, the curve records, the lane
  model, and this grammar are the interfaces to agree on first.

## Adjacent ideas from the same session (already roadmapped)

- Real lane counts baked from OSM (lanes= tags via our own
  Overpass/PBF pipeline) -- four lanes through Albuquerque, real lane
  drops as genuine merge events. Next map brief.
- A player-operated turn signal, with unsignaled lane changes as a
  discipline the CB and troopers can notice at higher realism tiers.
