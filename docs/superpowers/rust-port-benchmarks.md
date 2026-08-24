# Rust port -- measured performance

Measured 2026-08-22 on the owner's machine, branch `feat/rust-port`. This
document answers one question and no other: on the numbers, what does the
port buy? Every figure below was produced by the two harnesses named here,
both of which are in the repo and can be re-run.

DRAFT -- Rust column pending. (Placeholder while the freight-fate crate is
mid-write by another task; this file is rewritten with both columns before
the work is reported.)

<!-- Whoever rewrites the sections above: the "Release size" section below is
     finished, measured work from a separate task. Keep it. -->

## Release size

Both builds are `tools/build_release.py --rust` on Windows, staged into
`build/FreightFate/` and archived as a portable zip. The only difference in
the payload rules between them is the baked data container: the earlier build
shipped the JSON tree under `freight_fate/data/`, the later one ships
`freight_fate/data/world.ffdata` instead.

| Component | Before (`nightly-20260822`) | After (`nightly-rustport`) | Change |
|---|---:|---:|---:|
| `FreightFate.exe` | 125,440 | 14,615,040 | +14,489,600 |
| Native libraries (SDL2, BASS + 4 plugins, Prism) | 2,982,560 | 2,982,560 | 0 |
| `freight_fate/data` | 141,937,342 | 7,312,812 | **-134,624,530** |
| `freight_fate/music.pak` | 261,358,688 | 261,358,688 | 0 |
| `freight_fate/sounds.pak` | 7,781,859 | 7,781,859 | 0 |
| `freight_fate/assets/sounds` | 63,747 | 63,747 | 0 |
| `freight_fate/lib` (BASS plugin fallback) | 23,848 | 23,848 | 0 |
| Docs + `build_info.json` | 809,612 | 809,612 | 0 |
| **Staged total** | **415,083,096** (395.9 MiB) | **294,948,166** (281.3 MiB) | **-120,134,930** |
| **Zip** | **281,269,031** (268.2 MiB) | **283,840,482** (270.7 MiB) | **+2,571,451** |

Two things move between those builds, and they move in opposite directions,
so the totals have to be read apart:

- **The bake.** 141,937,342 bytes of JSON become a 7,312,812-byte container.
  Inside the zip, the same content goes from 10,270,471 deflated bytes to
  7,314,108 -- the container is already zstd, so deflate adds nothing.
  So the bake is worth **128.4 MiB on disk and 2.8 MiB on the download**.
  The download barely moves because zip was already compressing that JSON
  roughly 14:1; the win is the installed footprint and the startup parse,
  not the bytes a player downloads.
- **The port itself.** `FreightFate.exe` went from 125,440 bytes to
  14,615,040 (5,604,418 deflated) between the two builds as the game landed.
  That +5.5 MB in the zip is what turns the bake's -2.96 MB into the +2.57 MB
  on the bottom line. It is progress, not regression.

`ff-bake`'s own per-section report on the same tree:

```
cities 205,618 -> 205,719      legs 94,444,986 -> 91,897 (1027.7x)
corridors -> 4,786,690         curves 12,705,282 -> 571,845 (22.2x)
city_services 15.1x            facility_approaches 25.6x
facility_endpoints 20.1x       local_approaches 26.3x
local_geometry 26.9x           street_limits/buffs/radio catalogs 3-10x
total 141,937,342 -> 7,312,780 (19.4x), 1291 legs, all with corridor detail
```

**What still dominates the download.** `music.pak` is 261,358,688 bytes --
89% of the staged folder and 92% of the zip after the bake. Nothing else in
the payload is within two orders of magnitude of it. Any further work on
download size is a decision about that one file (split it out as an optional
download, or leave it), not about anything the bake or the binary can do.

**Smoke.** `FreightFate.exe --smoke` under
`FREIGHT_FATE_NO_SPEECH=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` exits
0 on the staged `nightly-rustport` build, reaching "Choose career. 1 of 9."
in the transcript. It is a real data check, not just a boot: move
`world.ffdata` aside and the same run exits 101 on "the shipped world data
loads". Note that a manual smoke run leaves `saves/` and `logs/` in the
staged folder -- the pipeline strips those before archiving, a run by hand
does not.

## Frame time while the game is being driven

Measured 2026-08-24, same machine, release builds on both sides. Two
harnesses, answering two different questions.

### The simulation step, like for like

`tools/bench_drive.py` and `crates/freight-fate/tests/it/bench_drive.rs`
build the same drive -- Denver to Cheyenne, `trip_seed = 0`, start hour 12,
engine running, accelerator held -- and tick `DrivingState.update` 12 000
times at a fixed 60 Hz step after 600 warm-up frames. Nothing else is in the
timer: speech is silenced and audio is the null backend on both.

| | Python | Rust | Rust is |
|---|---:|---:|---:|
| frame mean | 489.04 us | 25.84 us | **18.9x faster** |
| frame median | 514.80 us | 24.70 us | **20.8x faster** |
| frame p99 | 717.40 us | 46.80 us | **15.3x faster** |
| frame max | 5 033.10 us | 2 223.80 us | 2.3x |
| 12 000 frames | 5 868.5 ms | 310.1 ms | 18.9x |
| peak working set | 1 485.0 MB | not measured by this bench | -- |

The two runs did the same work, and say so rather than asking to be
believed: both end at **42.988 mi**, at **85.51 mph**, at **34.465 game
minutes**, with **0** states pushed. A drift in any of those four would mean
the drives had diverged and the numbers were not comparable.

Against the 60 Hz frame budget (16 667 us), the Python sim step was **2.9%**
of a frame at the mean and 4.3% at p99; the Rust one is **0.16%** and 0.28%.
Neither was ever going to drop a frame on this machine on that route. The
port's win here is headroom, not a rescue.

### The whole frame, on a hard route

`crates/freight-fate/tests/it/frame_time.rs` is the missing measurement: not
the sim alone but everything `App::frame` does with the window taken away --
`App::tick` (controller, the speech poll, cloud notices, audio fades, the
speech duck, the state update, presence) plus the line build `App::render`
hands the shell. It drives I-70 west out of Denver, seeded and
weather-pinned, with traffic and hazards left ON, and stops when the truck
does.

Release, 35 618 timed frames, 63.5 miles, 89 game minutes:

| | us |
|---|---:|
| mean | 62.81 |
| median | 55.70 |
| p95 | 105.60 |
| p99 | 123.50 |
| max | 2 530.40 |

**0 frames of 35 618 went over the 16 667 us budget.** At the mean the game
uses **0.38%** of its frame; at p99, 0.74%. Sustained, that is about 15 900
frames a second if nothing else ran. The game is not frame-bound.

Where it goes, per frame:

| phase | us | share |
|---|---:|---:|
| the sim step (`DrivingState::update_frame`) | 53.39 | 85.0% |
| the rest of `App::tick` | 7.00 | 11.2% |
| the line build (18 rows) | 2.42 | 3.8% |

and inside the tick, nothing else reaches a microsecond: controller 0.05,
speech poll 0.03, cloud notices 0.03, audio 0.04, the speech duck 0.02,
Discord presence 0.57, the drivers-board line 1.60. Frames that spoke cost
107 us against 63 for frames that did not. No phase gets more expensive as
the drive goes on.

### What measuring it found

The first run of that bench read **2 150 us mean, of which 2 097 -- 97.5% --
was one phase outside the simulation**: 13% of the whole frame budget, on a
frame nobody had ever looked at. Splitting that phase (a second run of the
same drive, so its absolute numbers are its own) put **2 395 us a frame in
the drivers-board line against 84 us for the sim.**

`DrivingState::online_presence_state` was resolving the tuned station on
`self.radio.clone()`: a deep copy of the whole dial, 757 baked stations plus
the identity map built over them, sixty times a second, to read one
station's display name and throw the copy away. The clone existed only
because `RadioState::current_station` takes `&mut self` -- it persists a
sibling handover or a fallback -- while `presence()` is `&self`.

`RadioState::tuned_station` is that same resolve without the write-back.
Same station, same string, no copy. The drivers-board line now builds in
**1.60 us**, and the driven frame went from 2 150 us to 62.81.

Two things are worth keeping from it. First, **it was a port artifact**: the
Python this was ported from calls `self.radio.current_station()` directly,
because nothing in Python makes `&mut` cost a copy. A whole-frame Python
comparison run before the fix would have been measuring the port's bug.
Second, **the absolute gate would not have caught it** -- 2.4 ms still fits
in a 60 Hz frame. What catches it is the ratio gate below.

### The gates

Both live in `frame_time.rs` and run in the ordinary suite.

* `a_driven_frame_stays_well_inside_the_sixty_hertz_budget` -- p99 of the
  driven frame under **4 167 us**. Derived: the loop targets `app::FPS` = 60,
  so the frame is 16 667 us; this bench measures the headless part, and the
  SDL pump, the window render, BASS and Prism must still fit beside it; the
  quarter is the four-to-one single-thread spread between a current desktop
  part and a low-end mobile one (PassMark, same generation), so a quarter
  here is the whole budget on the slowest machine supported. Deliberately
  loose, so a busy CI box cannot fail it.
* `a_frames_bookkeeping_never_out_costs_its_simulation` -- each presence
  string must build in less time than the sim step, both measured in the
  same frames of the same process, so machine speed and CI load cancel. The
  rule is a design one: a string handed to services that throttle to seconds
  must not out-cost simulating the truck. Today it is 0.012x and 0.033x; the
  radio clone was 28x and would have failed on the first frame.

### What the bench does not cover, and why

* **The route runs out before the drive does.** The synthetic driver is a
  throttle and a brake. Off the Continental Divide it works the service
  brakes down to the low-air warning and the spring brakes park the truck at
  mile 63.5 of 246 -- the air system behaving correctly, a driver behaving
  badly. So the timed frames are all on leg one: no leg change, no city
  arrival, no pushed screens. Teaching the driver the retarder is the next
  thing anyone extending this should do.
* **No SDL, no BASS, no Prism.** The window render, the real audio mixer and
  the screen-reader hand-off are outside every number here. That is the
  headroom the gate's quarter-budget is reserving, not a measurement.
* **Memory is measured on the Python side only.** `bench_drive.py` reads its
  own peak working set; the Rust bench does not, and the 1 485 MB above has
  no counterpart here.
