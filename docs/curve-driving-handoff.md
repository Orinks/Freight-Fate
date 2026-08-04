# Curve Driving Handoff — for Josh (and Josh's agent)

This is the file to read before testing the new curve navigation. It
covers what shipped, how to turn it on, what every sound means, how to
actually drive a bend, and how to jump straight to good test roads.
Written 2026-07-27, the day the feature folded into `feat/career-1.9`.

## What this is

Your ask, built: "real speeds in for curves as well as panning sounds so
we can steer through them." The advisory speeds were already real (baked
from actual road geometry on all 63,724 curves); this adds the steering.
With lane drift on, curves push the truck toward the outside with honest
physics — tighter bend, heavier load, or more speed over the advisory
all push harder; ice resists less — and you hold the lane with Left and
Right against it. The audio design follows the community ruling from the
audiogames thread: the guide is the EXISTING road sound panned toward
where the wheel should go, never a new tone, and silence-is-centered.

## Turning it on

Curve steering only exists when **lane drift** is on. It's off by
default (Settings, Driving assistance, Lane drift): off means the truck
holds the lane itself, light is gentle drift with centering help,
realistic is the real wheel. For honest testing use realistic, and turn
**Curve speed assistance off** — with it on, the truck brakes for the
bends itself and you'll wonder why nothing is happening. That is not a
bug; it's the assist doing its job. Related settings: "Lane and edge
cue loudness" (subtle / standard / prominent) scales all the new
sounds; "Curve callouts" carries the calls, entry beeps, and exit
verdicts.

## The sound vocabulary

- **Bright beep from one side** — a curve call ("Sharp left, half a
  mile. Advise 35."), or a curve beginning, on that side.
- **Road sound leaning left or right** — the steering guide: it leans
  toward where the wheel should go. Hold the arrow that way, keep the
  sound centered. Centered on a straight = silence; quiet means good.
- **Hard slow double-thuds under the whole truck** — dead-man's bars:
  transverse warning strips a quarter mile before a true hairpin
  (advisory 25 or under). Brake hard immediately. They fire at any
  speed in any assist mode, because they're cut into the road.
- **Thump-roll from one side** — your axles crossing a lane line's
  raised markers, panned to the crossed side, with a signal tone on a
  deliberate change. Rapid re-crossings (fighting the bend) keep only
  the quiet thump — no ding spam.
- **Stutter → steady buzz → gravel, from one side** — the edge ladder:
  clipping the rumble strip, fully on it, off the pavement. Structural
  states, not just louder — they stay tellable-apart under engine
  noise. On an undivided road there's no gravel past the LEFT line;
  instead the warning says the truth: "Across the centerline, in the
  oncoming lane!"
- **Soft tock about once a second** — the lane locator (I key toggle):
  your position in the lane, on demand. L asks once instead.
- **Spoken exit verdict** — "Through the bend, held your line." /
  "You caught the edge." / "Through the bend, hot." Chained bends hold
  the verdict for the last link. Terse speech gets a chime instead.
- **Turn signals are tones now** — panned to the signaling side, at
  every signal site (lane change, exit arm, pull-over).
- **Stop-bar solid tone** — separate feature, same fold: the ramp
  stop-bar beeps (300 ft, quickening) fuse into a continuous tone in
  the last ~60 feet. At the solid tone, be nearly stopped.

## How to drive a bend (the short course)

1. Cruise carries you between bends. The callout is braking DISTANCE,
   not a stop order: brake firmly toward the advisory, arrive within a
   few mph of it. Over-slowing to a crawl deletes the bend.
2. Entry beep marks the start. Hold the arrow toward the lean of the
   road sound; small, held corrections. Sawing = marker thumps = ease
   off.
3. Listen for the verdict on the way out, then K to resume cruise.
4. Dead-man's bars mean a hairpin: brake hard NOW, 25 means 25.

The player-manual chapter "How To Take Curves Like A Boss" (in the 1.9
manual draft) is the long version.

## Jumping straight to test roads

Your own playtest tool is the best harness for this — it grew a couple
of flags in the process:

    # 58 miles of AZ 260 curves, cruise 45, hands-on everything:
    uv run python tools/playtest_road.py --from "Camp Verde" --to "Payson" \
        --at 0 --speed 45 --cruise 45 --steering realistic \
        --curve-assist off --cargo 15

    # Straight to a dead-man's-bars hairpin (bars at mile 37.6,
    # 25-advisory right-hander just past them; three more hairpins
    # clustered at mile 55.5):
    uv run python tools/playtest_road.py --from "Camp Verde" --to "Payson" \
        --at 36.5 --speed 50 --cruise 50 --steering realistic \
        --curve-assist off --cargo 15

    # Find hairpins anywhere:
    uv run python tools/playtest_road.py --find curve --max-advisory 25 --scan

Also fixed in the tool while we were in there: quitting to the main
menu now actually reaches the main menu (it used to respawn the drive),
and a session's `--steering`/`--assists` flags no longer leak into your
real settings on exit.

## Known state / honest notes

- Tuning is one day old and set by one ear (Norm's). Loudness
  balances, bar depth, guide-lean strength, and verdict wording are all
  fair game for feedback — that's why you're getting it.
- The engine driving bands are MID-REVISION: the current licensed cuts
  can read as turbine-ish ("jet engine") under load. Known, diagnosed,
  revision in progress in the audio workstream. Not part of curve nav;
  don't burn time reporting it.
- Curve steering difficulty on realistic is deliberately real. "Light"
  exists for a reason, and default-off is the accessibility position:
  same road, chosen intensity.
- Feedback that helps most: a road name + mile + what you heard vs.
  what you expected. Transcripts land in `logs/playtest.log` from the
  tool, `logs/playtest_log` from normal play.
