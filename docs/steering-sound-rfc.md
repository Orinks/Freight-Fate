# Steering by ear: a design consultation

Draft for the audiogames.net forum and for Josh. Plain language, ready
to paste; trim or reword freely. The questions at the end are the
point -- everything above them is just enough context to answer well.

---

Hi all,

We're building real steering into Freight Fate, our audio-first
trucking simulation, and before we commit to a sound language we want
to hear from people who have actually driven games by ear -- what
worked for you, what wore you out, and what you wish someone had built.

A little context. The game already knows the real shape of every road:
we've mapped over sixty thousand actual curves across the US highway
network, each with its direction, its tightness, and the speed a real
truck could take it. So the road data is not the problem. The problem
is the honest one: how does a blind driver feel the lane, hear the
bend coming, and steer through it -- for a ten-hour haul, not a
three-minute race.

Here's the design we have so far, in five layers:

1. A co-driver. Spoken curve calls built from the real road: "Sharp
   left, quarter mile, advise forty-five." Plain language, not rally
   code. Warnings are timed in real seconds of reaction, not
   compressed game time.

2. Silence means centered. On a straight road, a centered truck is a
   quiet truck. Drift toward a line and a soft textured cue fades in
   on that side and grows with the drift. No constant centering tone
   -- we think that turns a long haul into ear fatigue. This is one of
   the things we want challenged.

3. The road leans when it bends. Through a curve, the sounds you
   already hear -- tires and engine -- pan along the arc, and you
   steer to bring them back overhead. Forza Motorsport's Blind Driving
   Assists proved this idea: follow the sound, rather than react to an
   error beep. Straights stay silent; bends sing.

4. Edges that name their side. The two lane edges sound different,
   not just panned differently: rumble strip on one side, gravel
   shoulder on the other. If you have hearing in only one ear, you
   still know which way you've wandered. Crossing a dashed lane line
   gets its own soft paint-and-dots tick, much quieter than an edge.

5. Every sound auditioned before you drive. Each cue can be previewed
   from the settings menu and practiced in the in-game driving school
   before it ever matters at speed.

And now the questions. Any one answer helps; war stories help more.

Question one: steering feel on a keyboard. Hold-to-sweep, where
holding the arrow banks the wheel further the longer you hold and
releasing lets it self-center, like a real wheel's caster? Or
tap-to-nudge, where each tap steps you sideways a fixed amount and
nothing moves unless you ask? Something else from a game that got it
right?

Question two: is silence-is-centered correct, or do you want the
option of a quiet continuous reference at the lane center? If you've
driven games with a constant centering tone, did you grow to rely on
it or grow to hate it?

Question three: what should the curve guide actually be -- the panned
road-and-engine bed described above, a dedicated tone that traces the
bend, or both as separate options?

Question four: which audio driving games should we study before we
build this? What did they get right that nobody else did, and what
mistake should we absolutely not repeat?

Question five: curve calls -- plain language ("sharp left"), rally
style ("left three, tightens"), or a setting for each? Remember this
is a truck: you'll hear thousands of these over a career.

We'd rather change the design now than after you've learned it. Thanks
-- and if you want to hear where the game already is, the current
build speaks everything from lane position to brake temperature.

---

## Notes for us (not part of the post)

- Decided 2026-07-16 and not up for consultation: real reaction
  seconds for warnings, per-side edge textures, previewable cues,
  plain-language default. The consultation may still overturn
  silence-is-centered (question two) and the guide sound (question
  three); steering feel (question one) is genuinely open -- owner
  leans neither way yet, Fable recommends hold-to-sweep with
  self-centering.
- Forza Motorsport Blind Driving Assists, for reference: spoken
  co-driver guidance, sonar tones for edges and turn progress, a
  deceleration-amount cue, shift cues, a steering guide that pans
  engine and tire audio toward the needed steer, all individually
  toggleable with pitch and volume control and in-menu previews.
  Co-developed with blind consultant Brandon Cole.
- Josh gets the same questions plus one more: which of his presets
  should own the curve tier, and does All assists keep today's
  auto-curve behavior byte-for-byte?
