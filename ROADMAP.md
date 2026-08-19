# Freight Fate Roadmap


> **RELEASE SCOPE (amended 2026-07-27, owner + Josh):** the 1.9 line
> takes FIXES plus exactly the final slate Josh named -- (1) the easy
> multilane slice (wiring the already-baked lane counts into speech),
> (2) curve navigation with steering, (3) rumble strips (one system
> with curve nav), (4) the engine-ring spectra rebuild, and (5) the
> NPR translator radio batch. Nothing else: every other unchecked
> FEATURE bullet below targets the `feat/career-2.0` line (worktree
> `.claude/worktrees/career-2.0`, created 2026-08-18; the `C:/dev/ff-2.0`
> path this note used to name never existed). The driving school stays
> gated off 1.9 (`DRIVING_SCHOOL_ENABLED`) and reopens on 2.0 to be
> finished.
> Track plan: `docs/plan-1.9-final-slate.md`.

> Current stable: **1.8.8.1** (hotfix shipped 2026-08-08). Next release: **1.9.0**, in
> flight on the `feat/career-1.9` branch -- driving realism between the exits
> (discrete lanes, ramp terminals, congestion, real surface streets) plus the
> highway-spider world expansion, roadside narration, and real time zones.
> `pyproject` is set to 1.9.0 so developer snapshots report it; the stable tag
> follows at release. Keep this file current: when a feature lands on the 1.9
> line, check it off here in the same change.

## 1.10 planned -- the working week and home

Design doc: `docs/eld-home-terminal-design.md`. The ELD grows from a daily
countdown into the system that shapes a driver's week, and the home
terminal becomes the anchor of that week instead of a spawn point.

- [ ] **70-hour/8-day cycle with the 34-hour restart.** A rolling on-duty
      ledger on `HosClock`, spoken through the existing ELD status line;
      restarts at the home terminal are free and full, road restarts cost
      motel money and comfort. The 1.10 centerpiece.
- [ ] **Home terminal persisted and consequential.** `home_terminal_city`
      on the profile (old saves default to the current city with a
      one-time spoken note), ELD readouts in home-terminal time,
      discounted garage work at your terminal, dispatch "gets you home"
      lane notes, and paid domicile relocation for owner-operators.
- [ ] **Local board (short-haul identity).** A second dispatch surface at
      the home terminal: short home-region runs, home every night, no
      cycle pressure, lower pay -- weighted toward new hires in the
      assigned-dispatch levels.

### Personal conveyance and duty-purpose correction

Regulatory baseline: [FMCSA personal-conveyance guidance](https://www.fmcsa.dot.gov/regulations/hours-service/personal-conveyance)
and [FMCSA ELD recording guidance](https://www.fmcsa.dot.gov/hours-service/elds/if-driver-permitted-use-commercial-motor-vehicle-cmv-personal-reasons-how-must).

- [ ] **Correct today's bobtail classification before adding the ELD
      choice.** Separate physical configuration (bobtail means tractor
      without a trailer) from duty purpose. Driving empty to another
      city's dispatch board improves commercial readiness, so it must
      record as driving/on-duty repositioning rather than off-duty
      personal conveyance. Deadhead with an empty trailer remains a
      separate physical configuration.
- [ ] **Personal-conveyance first slice.** Add spoken Start personal
      conveyance and End personal conveyance actions to the ELD menu.
      Ask for a valid purpose and nearby destination: food, shower,
      lodging, or the nearest reasonable safe parking after a shipper or
      receiver releases the driver. Record the movement as off duty with
      a personal-conveyance annotation, reason, start and end locations,
      and distance; preserve it through save/resume.
- [ ] **Keep the clock and truck behavior honest.** Personal conveyance
      still consumes fuel, accumulates fatigue, and keeps all driving
      safety and enforcement active. It does not consume driving or
      on-duty hours, but a short move does not pause or extend an already
      running 14-hour window. Use a carrier policy distance limit rather
      than presenting it as a federal mileage rule; loaded versus empty
      is not the deciding test, though a carrier may set a stricter
      policy.
- [ ] **Reject commercial uses and handle the after-hours exception
      narrowly.** Do not permit personal conveyance to approach the next
      pickup, shop another dispatch board, return to a terminal after a
      dispatched trip, or travel for maintenance. Running out of hours
      alone does not qualify; the exception is leaving a shipper or
      receiver for the first reasonable safe parking location and then
      taking the required rest.
- [ ] **Make misuse reviewable.** The logbook and traffic-stop inspection
      must read the annotation and route evidence. A later enforcement
      slice can question repeated maximum-distance use or other suspicious
      patterns without turning legitimate personal trips into random
      punishment.
- [ ] **Yard moves are separate.** On-property facility movements record
      as on-duty yard time, not personal conveyance or ordinary highway
      driving.
- [ ] **Verify the complete spoken path.** Cover keyboard reachability,
      ELD start/end confirmations, logbook wording, save/resume, eligible
      and rejected destinations, HOS/fatigue behavior, and traffic-stop
      review with transcript-backed playtests. Update in-game help, the
      user manual, and the changelog when the feature lands.
- [ ] **Other ELD character events.** Daily log certification, carrier
      edit approve/reject prompts, a rare ELD-malfunction paper-log day,
      and the adverse-conditions +2-hour exception wired to live weather.

### Signalling a street turn

Deferred out of 1.9 (owner call 2026-08-10) rather than bolting a blinker
onto exit signalling.

- [ ] **A blinker for surface-street maneuvers.** X signals an announced
      highway exit and plays one panned `vehicle/signal_tone`; nothing
      signals a street corner. The map is not the blocker -- baked tier-1
      maneuvers already carry direction and distance, which is what feeds
      the `events/turn_left` and `turn_right` earcons. What is missing is
      the turn as a continuous act: `LaneKeeping` has a lateral offset and
      a lane index and no heading, the same gap that killed the quick-time
      turn in July. Needs a held tick that self-cancels at the corner and a
      rule about signalling before one, alongside whatever turn geometry
      the surface-intersection work (1.9, `docs/surface-roads-plan.md`
      phase 4) leaves behind. The self-cancel half of that now exists:
      `_update_steering_lane_cue` holds a cue on the audio clock's dead
      man's switch and ends it with a centred, quieter `vehicle/signal_tone`.
      Borrow it rather than building a second one.
- [ ] **Decide the two orphan sound assets in the same change.**
      `vehicle/turn_signal` is the repeating tick this feature wants and
      has never been wired to anything. `vehicle/lane_drift` is dead for a
      different reason -- the edge ladder took its job -- so it is a
      deletion, not a wiring job.

## 1.9 in flight (`feat/career-1.9`)

- [ ] **There is no way to back a career up on demand (Brandon, 2026-08-15).**
      A career can only travel upward two ways: the background queue after a
      save, and "Keep this computer's save and back it up" -- which
      `CloudSlotState.build_items` only offers while a conflict is RECORDED.
      No conflict, no upload control anywhere in the game. Brandon fell
      through that hole twice in one evening: first the conflict blocked the
      queue, and then, once he had resolved it by restoring, the button that
      could have sent his own newer career up vanished with the conflict that
      summoned it. He lost level 4 and 3,294 dollars back to the cloud's
      level 3 -- recoverable only because a restore leaves the replaced file
      as `.ffsave.bak`, which nothing tells the player. Wanted: a plain "Back
      up this career now" on the Cloud backup menu, always present, using the
      same upload path, so a stuck queue is never the player's only hope.
      Deliberately not added unattended at 1am -- it is a new control on a
      shipping menu and wants a canonical name in `docs/ontology.md`, a
      decision about whether it appears on the Online menu too, and its own
      spoken result.
- [ ] **A staged limit drop should be taken in stages (Shane, 2026-08-15).**
      Approaching roadwork the truck hears "speed limit 55 miles per hour,
      then construction zone 45" and then sheds straight to 45, never
      pausing at 55. His words: it "should slow to 55 then when before the
      work zone it should slow to 45 instead of diving right down to 45".
      The world model is NOT at fault and needs no change -- `trip.py`
      already lays a `construction merge` zone at
      `CONSTRUCTION_TAPER_LIMIT_MPH` (55) over the taper mile, then the
      `construction` zone at 45, and `speed_limit_at` returns the right
      number for each. The keeper's cap is right too: it comes down with the
      limit under the wheels. The culprit is the ease-ahead,
      `_keeper_ease_target` (`driving_events.py`), which picks the LOWEST
      limit in its lookahead window and sheds toward it, so an intermediate
      posted number inside that window is skipped rather than held. Fix
      shape: ease to the NEXT limit boundary, then re-target, so the truck
      steps down the way the sign sequence and the announcement both
      describe. Deliberately NOT done unattended -- it changes assist
      behaviour on the approach to a work zone, and the spoken promise and
      the enforcement numbers have to be re-checked together against the
      harness, not reasoned about. Owner request 2026-08-15:
      with the lane work yours, taking an exit means holding a position at
      the right of the lane, and that position was the one thing on the road
      a blind driver could not hear. Holding a steering direction now starts
      the lane locator's own panned tock without the I key, for as long as
      the move lasts; an armed exit takes it over from the moment the driver
      moves across, quickens the beat as the position fills, and stops it
      with `vehicle/signal_tone` played centred and quiet -- the signal
      cancelling itself -- the instant the exit lane is set. No new speech,
      silent under full lane keeping and below the locator's speed floor,
      and held on the audio clock's dead man's switch so a menu over the
      drive ends it in silence. See `_update_steering_lane_cue`.
- [x] **Debt payoff from cash -- SHIPPED.** Whenever a driver carries a
      balance and has money in hand, the terminal and every truck stop now
      offer to pay it down: all of it, half, or everything above a 200
      dollar fuel cushion. Clearing the balance stops settlement collection
      on the spot.
- [x] **Truck dealer is a direct terminal menu item -- SHIPPED.** The
      city-service drive is retired; the dealer now opens straight from the
      terminal menu, named for the real local dealership where one is on
      record. Fuel, repairs, rest, and food stay at truck stops and the
      terminal garage. See the amendment on "Local city service drives"
      below.
- [x] **Settings menu reorganized (Variant B) -- SHIPPED.** Gameplay is now a
      category that opens its own submenu of four shorter, spoken screens:
      Driving assistance, Difficulty and hours of service, World and traffic,
      and Controls. The weather/traffic/parking sources and the live-weather
      calendar moved out of Speech and weather (now "Speech") into World and
      traffic; enforcement presence moved to World and traffic too. The dead
      "Lane keeping" pointer stub in old Gameplay is gone, and the duplicate
      speed keeper row is collapsed to exactly one. A one-shot
      `settings_version` migration line tells a returning player where things
      moved the first time they open Gameplay; a fresh install hears nothing.
      A reachability test guards against orphaning any setting in the split.
- [x] **Settings audit -- SHIPPED 2026-08-15.** A field-by-field sweep of all
      73 `Settings` fields for consumers found nothing dead: every field
      either reached the game or was genuine internal migration machinery,
      so the audit itself was a reorganization and an honesty pass rather
      than a deletion (the one field that did come out, below, was removed
      for behaving wrongly, not for being unread). The speed
      keeper moved from Controls into Driving assistance; "Lane and edge cue
      prominence" became "Lane and edge cue volume" and moved to Audio under
      the Gameplay cues volume it scales, with quieter/standard/louder values;
      every saved key stayed identical, so no choice reset. The layout-notice
      flag became a per-version `settings_layout_notice_from`, so future menu
      moves need no new field and a player two layouts behind hears both.
      `test_no_settings_field_is_a_phantom` now fails any field with no
      consumer outside `settings.py` and the settings menu, with commented
      allow-lists separating internal flags from pending features. The one
      real removal came out of the audit rather than into it: the overspeed
      warning armed at 5 over, exactly the pace `ACC_LIMIT_OFFSET_MPH` makes
      predictive cruise hold, so it chimed at drivers for the truck's own
      speed and the setting existed only to silence it. It now arms at 7 --
      above cruise's pace, below `OBSERVE_LEEWAY_MPH`'s 9 -- and the
      `overspeed_warning` setting is gone (owner ruling 2026-08-15).
- [ ] **Lane centering assistance is still a promise, not a feature.**
      `lane_centering_assist` is a real settings row the presets write, and
      nothing in the driving code reads it; the help text now says so plainly
      instead of describing steering help that never arrives. Either
      implement the steering help or retire the row before 1.9 ships.
- [x] **Headless-measured startup: four fixes for ~0.46s off the
      launch-to-main-menu path -- SHIPPED 2026-08-12.** A profiling pass
      pinned headless startup at a 2.166s median and isolated four
      independent costs: the sound engine now kicks the ~225MB sound pack's
      read-and-unmask onto a background thread as early as `App()`
      construction starts, so it overlaps the world load instead of
      stalling the first sound played (measured ~0.32-0.34s off the first
      menu sound at both 0 and 20 saved careers); the main menu's save-scan
      (`_loadable_saves()`) ran three times on every menu entry and now
      runs once and reuses the result (measured ~0.11s saved at 20 saved
      careers, scales with save count); `keyring` and
      `cryptography.hazmat` (pulled in by the online-account and
      cloud-backup modules) are now imported lazily, on first real use,
      instead of on every launch whether or not the player has ever linked
      an account (~0.15s measured import-time saving); and a frozen build
      now bakes its package version into `build_info.json` at build time
      instead of scanning installed-package metadata on every launch (dev
      checkouts are unaffected -- no measurable local win, this only pays
      off in a packaged build). Measured on the same headless phase-timer
      the profiling pass used, 5 runs each: 2.187s to 1.727s median with an
      empty save collection, 1.887s to 1.682s with 20. One thing considered
      and deliberately left alone: skipping `OnlineIdentity.load()`
      entirely when every online setting is off would have shaved a
      further ~0.065s for players with a linked account, but
      `OnlinePresence.set_enabled()`/`CloudSaves` both refuse to turn back
      on without an identity already loaded, and nothing re-loads it when a
      setting is flipped on mid-session outside the account-link flow -- so
      a player who linked an account and then turned every online setting
      off would have lost the ability to turn one back on without
      re-pasting credentials. Left unconditional; the load already costs
      nothing for the common case of no linked account, via the existing
      early return before it ever touches `keyring`. The remaining big
      item, sharding/streaming the world load itself (~1.17s of the
      median, by far the largest single phase), is a separate, larger
      change and out of scope here -- tracked as its own follow-up, owner
      approved, in the bullet immediately below.
- [x] **World load, the largest single startup phase, cut by ~0.82s via
      lazy per-leg corridor loading -- SHIPPED 2026-08-12.** `World.load`
      measured 1.207s median and built every leg's heavy per-mile detail
      (grades, interchanges, landmarks, state crossings, checkpoints, toll
      events, speed limits, traffic volumes, restrictions, lane segments,
      elevation, route points) for all fifty states up front, plus the
      ~31MB of nationwide local-driving data (facility approaches/endpoints,
      surface-street geometry, city services) -- almost none of it touched
      in a session. Legs are now `LazyLeg`: only the fields the route graph
      and dispatch read stay eager, and dispatch-completeness is baked at
      load from raw corridor counts (byte-identical to the old
      `metadata_complete`, since those five fields parse one-for-one) so the
      route graph never triggers a parse. The heavy tuples build once, via a
      non-data descriptor, the first time a leg is driven, then cache on the
      instance for zero per-access cost. The nationwide local data is loaded
      lazily on first facility/city-service query. Measured on the same
      phase-timer, 3 runs: `World.load` 1.207s to 0.390s; route-graph
      dispatch work 0.0014s; first-leg-drive materialization 0.29 ms/leg
      (imperceptible); first facility-approach local-data hit ~85ms, once
      per category. The frozen build benefits equally -- the baked path runs
      the same lazy `World.__init__`. Deferred, not needed: the ~0.30s JSON
      parse itself is untouched; sharding/streaming that is a separate,
      larger change if it ever proves worth it.
- [x] **First round of Dropbox tester findings triaged and fixed --
      SHIPPED 2026-08-11.** Three P0s off the tester living document
      (Shane P). A construction zone could close the only lane on a
      one-lane stretch, pinning the driver in the closed lane and
      re-running the barrel collision until they quit -- placement now
      requires two lanes across the whole footprint including the taper,
      and the merge check stands down when there is no open lane.
      Taking a weigh station's own exit ramp counted as bypassing it,
      because the bypass test ran a frame before the ramp existed and
      judged on speed alone. A paid roadside fine was re-charged on every
      reload, escalating each time, because the armed stop was saved but
      never re-saved on resolution -- this also fixed the same
      double-charge for speeding tickets. Owner-operator careers now
      start with a brand-new truck (owner design call, same date) instead
      of one already damaged and short of fuel, and driving through work
      zone barrels is now a 1,000 dollar serious violation.
- [x] **The two driver assists that manufactured violations -- SHIPPED
      2026-08-11** on `fix/assist-behaviour`. The speed keeper had no
      lookahead at all: it read the limit under the wheels while every
      forward-looking input the game owns is wired only into cruise,
      which refuses to engage on facility streets. The 20 it could not
      reach is not a posted limit either, it is the trailer corner cap on
      any 25 mph street -- so this was a turn advisory, and a
      posted-limit lookahead alone would not have fixed it. Worse than
      speeding: the keeper drove into the missed turn, charged 8 game
      minutes for the loop-back, and then cancelled its own session. The
      curve assist raised the retarder on any curve it handled with no
      test of how much speed the corner needed -- 53 engagements across
      811 miles of real curve data, ten on one route for a 7 mph
      sweeper. Both now measured, not assumed: keeper deceleration
      benched at ~0.4 m/s2 at street speed, and a plain jake threshold
      was caught cooking the drums past fade onset in 4.5 minutes on a 6
      percent grade, so real downgrades are carved out.
- [x] **Automatic emergency braking left no reaction window -- SHIPPED
      2026-08-11** (Munchkinbear, 2026-08-11: "less than half a second
      between being told to brake/change lanes and the truck slamming on
      the emergency brakes"). The hazard deadline was braking budget plus
      a fixed slack, while the assist engaged at 1.2x the budget plus half
      a second -- so the driver's window was a remainder, and every reason
      the truck stops badly (speed, downgrade, brake heat, wear, grip)
      came out of the driver's time rather than the truck's. Measured on
      the traffic warning at 65 mph: 0.52 s fresh, 0.02 s drowsy, negative
      (engaging on the first frame) on hot brakes or in the wet. It got
      worse this build because putting traffic back on the road made that
      warning -- the tightest slack the game emits, and a dodgeable one,
      which budgets the longer stop -- the common case. The deadline is
      now built forward from the moment the assist must act, so the window
      is a guarantee: 3 s minimum to hear the warning and get on the
      pedal, plus 2.5 s more when the call offers a lane change, since
      that is how long the move takes. A tap change already under way
      holds the assist off while it can still beat the hazard.
- [x] **The assist did not always stop in time -- SHIPPED 2026-08-11**
      (owner question the same day: to help a player it should stop in
      time). It applied full SERVICE braking and the budget sizing its
      engage point assumed the same, but the predicted stop gets slower
      while it happens as the drums heat under that application. Benched
      from the moment of engagement across nine conditions, two collided
      after "Emergency braking engaged.": 65 mph on 450 C drums, 40 pct
      wear and grip 0.7 down a six percent grade, and the same downgrade
      at 80. `AEB_BUDGET_MARGIN` was meant to cover this and is not enough
      when every factor compounds. Service braking stays the first answer;
      once the time left no longer covers even that, the assist uses the
      hardest stop the rig has. All nine now clear. Deliberately a last
      resort, with a test each way -- an ordinary hazard on good brakes
      must not become a spring-brake panic stop.
- [x] **Enforcement forgot every look it deferred -- SHIPPED 2026-08-11**
      (Jerry, 2026-08-11: whole routes over the limit with nothing
      happening). One demand on the driver at a time is the right rule, so a
      post whose watch overlapped a hazard, a ramp or a pull-over had its
      look deferred -- into `_deferred_post_ids`, a set written in one place
      and read in none. "Defer, never drop" therefore held only while the
      post still covered the truck's mile, and a hazard window outlasts a
      one-mile radar reach several times over at any pacing. The look is now
      TAKEN when it happens and held until the cab is quiet, with a five-mile
      staleness bound so a trooper who never caught up loses you. The old
      test asserted the id landed in the set, which pinned the bookkeeping
      and not the behaviour; it is replaced by two that drive the truck past
      the post first.
- [x] **Hairpins on ordinary roads, off the mountains -- SHIPPED
      2026-08-11.** The 2026-08-09 screen was gated on flat terrain alone,
      so 385 hairpin-severity curves survived on US and state routes (296 in
      hills, 89 in mountain). Two more discriminators, both measured before
      they were applied: city-departure geometry within 2.5 miles of a leg's
      city node on non-mountain ground (112 curves, including a 43 ft kink a
      mile out of Hazard on KY-80), and a 50 ft radius floor for any road
      class (4 more, the tightest a 41 ft bend on US-50). The floor sits just
      under the tightest genuine switchback in the data, US-550's 54 ft at
      mile 60.5. Across the whole world the three screens together flag
      nothing in mountain terrain -- the property to check first if these
      thresholds are ever moved. KY-80 is the precision case: the hills kink
      at mile 1.06 goes, the mountain switchback at 2.48 stays.
- [x] **The posted limit flickered under time compression -- SHIPPED
      2026-08-11.** OSM splits a way wherever any tag changes, so the baked
      maxspeed profile carried postings a few hundred feet long. Real driving
      hides them; at 20x they go by in under a second, and the player hears
      the limit reduce and normalize with nothing on the road to explain it.
      Measured before the fix: 23 percent of all posted changes on three long
      routes were segments crossed in under three real seconds, including an
      80 to 45 to 80 inside 1.2 seconds on the Sheridan-Merced run. Length
      alone could not be the test -- the median village posting in this world
      runs seven tenths of a mile -- so a short posting survives when a
      village within a mile explains the REDUCTION, and goes when nothing
      does. World-wide: 829 of 1,287 legs changed, posted segments 15,206 to
      11,207, sub-second postings 1,993 to 583, drop-and-restore blips 1,415
      to 309.
- [x] **...and still flickered, because the bar was written in miles --
      SHIPPED 2026-08-12** (owner, on the 2026-08-11 build: "I still see
      speed decreases and increases a few seconds after one another"). Two
      holes. The mile bar is not one experience: a mile at 70 is 2.8 real
      seconds at standard pace and a mile at 30 is over ten, so a 1.0 mi bar
      admitted multi-second flickers by construction (40 of them). Worse, the
      village exception was an unconditional pass -- any reduction within a
      mile of a place survived at any length, which is how a quarter-mile
      80-to-75-to-80 on I-44 lived through the screen. That accounted for 763
      of the 803 postings still crossed in under three real seconds.
      The dwell is real seconds now (`LIMIT_DWELL_REAL_S`), converted to
      miles at each posting's own speed through the same compression ramp
      `effective_time_scale` uses, and the exception is a halved bar for a
      drop to a town speed rather than a free pass. World-wide: posted
      segments 11,207 to 7,401, postings under three real seconds 803 to 0,
      drop-and-restore blips under six seconds 703 to 120 -- and every one of
      those 120 is a town speed beside a village the game speaks aloud, which
      `test_no_leg_in_the_world_flickers_its_posted_limit` now pins as a
      property of the shipped map. Sized on the standard 20x pace: relaxed
      gets a quieter road than it strictly needs, and realistic is the player
      asking for the world to fly by. The data layer carries its own copy of
      the pacing constants (it never imports the sim); `test_maxspeed` pins
      them to `trip_models` so they cannot drift.
      Knock-on, fixed in the same change: Strawberry's 35 was one of the
      slivers, and `_village_explains_drop` only looked FORWARD for the drop
      a village explains, so the rim town stopped being sparse-worthy and
      went unspoken on the default place-callouts tier. A name now also
      explains the town speed already under the wheels when the road opens
      back up just past it.
- [x] **The alpha test book ships with the build -- SHIPPED 2026-08-11**,
      as `ALPHA_TEST_BOOK.md` plus an HTML rendering, verified by
      `verify_packaged_payload` like the manual. Its checklists are written
      against particular builds, so a tester fetching the current copy from
      the repo could easily work an old one. New sections cover the three
      2026-08-11 fixes: the hazard reaction window (4.2a), deferred
      enforcement looks (7.3a), and the curve/limit map fixes (11.1a).
- [x] **Date badges read the clock nobody sees -- SHIPPED 2026-08-11**
      (owner report: April's Fool firing with the real-time calendar on,
      in August). A career carries two clocks: raw `game_hours`, which is
      elapsed career time, and the calendar the player is actually told --
      the real wall-clock date when live weather drives it, otherwise
      career time plus `calendar_offset_days`. Every spoken surface used
      the second; `_award_arrival_achievements` used the first, so
      `april_first` fired on career day 11 whatever the date really was,
      and `christmas_delivery`, `new_year_run`, `friday_thirteenth`,
      `winter_delivery`, `four_seasons` and `desert_summer` were all wrong
      the same way -- a delivery could count as a winter run while the
      live weather said summer. The two-clock choice now lives in one
      accessor, `season.player_calendar_hours`, which the terminal's Time
      and weather readout uses as well; it was the duplicated inline
      expression that let them drift apart. Testers who already earned a
      date badge out of season keep it -- revoking earned badges would be
      the worse call.
- [ ] **New Dropbox tester findings, reported 2026-08-13 -- not yet
      triaged.** (1) Sarah: on a road with more than three lanes the
      lane-change callout says "middle lane" for both the middle and the
      left, and there is no way to tell the far-right lane on a five-lane
      road; she also heard a contradictory "right lane open, left lane
      open" once (Indio to Riverside) -- the baked lane counts feed speech
      but the naming does not distinguish beyond left/middle/right.
      (2) Shane: enforcement and passing-cop sounds cut off the in-cab
      radio -- a game-SFX-over-radio mix issue, distinct from the
      speech-over-engine ducking setting shipped this round. (3) Shane: on
      a one-lane road a cop still tries to pass, which it cannot do -- the
      overtake logic does not check that a passing lane exists. Owner has
      not decided a disposition; recorded so they are not lost.
- [x] **"Lane open" survives time compression -- landed 2026-08-13**
      (Jerry: "it said the right lane was open... I move over and I hit a
      vehicle"). The clearance read behind the lane-open cue and the L
      readout was a static window around the truck, widened by a 0.12-mile
      margin meant to buy the driver reaction time -- but traffic moves on
      compressed game time, so at 20x a cruise at 65 closing on slowed
      traffic at 38 ate that margin in under one real second and half a
      mile of gap before the 2.5-second drift landed. His log shows both
      sideswipes 4.5 real seconds after an honest "Right lane open."
      `vehicle_in_lane` now sweeps each vehicle's relative motion over the
      seconds the driver needs (hear the line, react, drift across),
      converted through `effective_time_scale`, so a lane being closed on
      -- ahead or from behind -- is never called open. The sweep test in
      `test_lane_return_gap.py` now advances the world between the readout
      and the arrival, which is the case the old same-instant test could
      not see.
- [x] **Classic engine voice restored to the original recording --
      2026-08-13.** The Settings engine-voice "classic" option quietly
      became the rebuilt idle cut played the old way when the licensed
      overlay landed 2026-07-27: both voices shared the engine/idle key,
      and the overlay owns that key. The donated 1.8.x idle now ships
      in-repo under its own key (engine_classic/idle, gitignore
      carve-out) that no overlay can shadow, the BASS classic path asks
      for it first and logs an honest fallback, and `*.bak` files no
      longer ride into the pack (the shipped pack carries one beside the
      real 1600 jake).
- [x] **Sounds.pak repacked for the classic voice -- 2026-08-13.** 278
      to 279 entries, rebuilt from the shipped pack's own contents (not
      a builder tree, so every 2026-08 addition survives): adds
      engine_classic/idle.ogg, renames the stray
      jake_1600.synth-original.wav.bak to an honest
      engine/jake_1600_synth.wav so both 1600 jake cuts ship and a
      future synth-versus-recorded jake toggle is a pure code change.
      Length/SHA pins updated. build_release verifies the classic cut
      is in any staged pack.
- [x] **Jake voice A/B -- 2026-08-14.** Settings, Audio now carries an
      Engine brake voice row (recorded/classic) right after Engine voice,
      same live-flip pattern, default recorded. The routing lives at
      key resolution in `audio.py` (`AudioEngine._voice_key`), so both
      the drive and Learn game sounds demo whichever voice is chosen
      without either call site knowing the A/B exists. Provenance on
      the recorded 1600 (f737b416) is still accepted-on-word; OWED: the
      recordist's name from Josh for a CREDITS.md row. If provenance
      sours, the classic option is already wired as the fallback.
- [x] **Sealed-cab transfer on the engine voice -- 2026-08-13.** The
      "engine sounds external" complaint was a missing cabin transfer
      function, not the voice. cab_filter.py applies the owner-approved
      sealed variant (from the sound-test/cab_transfer.py auditions;
      runtime output verified byte-identical to the approved render) to
      the five band cuts at load: -16 dB shelf past 1 kHz, 2.4 kHz
      lowpass, +5 dB body, 63 Hz boom, 1.7/3.3 ms early reflections,
      RMS-matched, circular so loops stay seamless. Classic voice and
      jake deliberately untouched this round.
- [ ] **Cabin-state intensities for the cab transfer.** The moderate
      variant from the same auditions is the natural "window cracked"
      setting; wire intensity selection to the doors/windows mechanic
      when the cabin-audio immersion work lands (2.0 line). Adjust the
      sealed parameters from tester feedback -- they are constants in
      cab_filter.py, not baked assets.
- [ ] **Cab-transfer review follow-ups (merge review, 2026-08-13).** The
      classic fallback on a pre-classic pack now routes the rebuilt idle
      through the seal and then pitches it -- a third voice neither
      setting promises; resolve the classic key once per process instead
      of re-probing and re-warning every ignition. The seal applies only
      to bands that resolve as wav, so an ogg band cut silently skips it
      with no log -- make "sealed" a property of the key, not the file
      extension. Pre-warm the five band seals during the loading screen
      (first ignition currently pays ~160 ms of FFT on the game loop).
      The sealed parameters and biquad math are duplicated between
      cab_filter.py and sound-test/cab_transfer.py -- the audition
      script should import them so tester-feedback tweaks cannot desync
      the lab from the ship. The pygame backend has no classic path, so
      the Settings toggle no-ops there against the changelog's promise.
      Builder trees that still hold jake_1600.synth-original.wav.bak
      must rename it to jake_1600_synth.wav (done on the primary
      builder 2026-08-13) or the next pack_sounds.py run drops the
      synth jake cut.
- [x] **Pedal latch yields to the speed authorities -- landed 2026-08-13**
      (Brandon latched the throttle for the whole trip expecting the
      assists to drive; every assist read the latch as a manual override
      and stood down). A latched throttle is now the lowest-priority
      speed input: cruise, the speed keeper, and curve assist own the
      pedal while engaged and the latch ramps back in when they release,
      with no re-gesture. Hand-held keys keep manual-override meaning;
      releasing the latch never cancels an assist; the catch line names
      the authority holding the speed. Spec:
      `docs/superpowers/specs/2026-08-13-pedal-latch-assists-design.md`.
- [x] **Cruise steps snap to the fives; Ctrl steps by one -- landed
      2026-08-13** (Jerry's latch-and-race-K workaround for catching an
      even 35; Sarah's real-stalk snapping). Plain plus/minus walks the
      fives grid from wherever K captured the target, healing off-grid
      speeds in one tap; Ctrl with the same keys moves by exactly 1 mph
      (Ctrl, not Shift -- the main-row plus IS Shift+equals). Pad cruise
      buttons stay coarse. Spec:
      `docs/superpowers/specs/2026-08-13-cruise-step-snapping-design.md`.
- [x] **Road events breathe; radio contours last -- landed 2026-08-13**
      (owner: back-to-back events in every mode; most of the 5,700-station
      dial living in fringe). Kept the clock -- career pacing is balanced
      on it -- and spaced the three routine talkers (limit arrivals,
      traffic calls, zone colour) with real-seconds gaps at the source,
      self-superseding so only current state ever speaks; big unannounced
      limit drops cut in line. Radio: clean program through ~85% of the
      contour (was ~52%) and a 2x reach multiplier for compression, smear
      ruling intact at the true edge. Spec:
      `docs/superpowers/specs/2026-08-13-event-pacing-radio-reach-design.md`.
- [x] **Station identity content generated and wired in -- landed
      2026-08-14.** All 19 stations now have a real host (8 clips each), 3
      station IDs (2 sung jingles and a spoken legal ID), and a shared pool
      of 18 fictional ads for the road: travel centers, diners, tire shops,
      and more. The Roadhouse got a new host voice, and Night Line's host
      clips were regenerated. Four new stations joined dial group 1: KGOL
      Cruisin' Gold 105.9 Oklahoma City (oldies), WGLR Glory Road 91.5
      Birmingham (gospel), KTJO Puro Tejano 107.1 San Antonio (tejano), and
      KNDR Neon Drive 88.5 Las Vegas (synthwave). The sound pack split: the
      music/ subtree, including all the new host clips, station IDs, and
      ads, moved into its own `music.pak`; `sounds.pak` picked up only the
      six new radio imaging beds. Song pools
      are partial by owner decision (ElevenLabs quota exhausted until
      2026-09-06): oldies is a full 8, gospel and tejano have 3 of 8, and
      synthwave has 1 of 8 -- see the follow-up bullets below.
- [x] **Radiostorm curated onto the web band, and one address per station
      -- landed 2026-08-17.** radiostorm.com's four channels (At Work 104,
      Rock 104 Classic Rock, Oldies 104, Comedy 104) are curated entries
      taken from the station's own `.pls` mounts, with the station's own
      names and formats instead of the directory's contributor-typed ones.
      Three of them were on the band twice: Live365 hands the same station
      out under several CDN edge hosts and several bitrate mounts off one
      station id, and `normalize_stream_url` folded none of that.
      It now canonicalizes a Live365 mount onto its station id, so build-time
      collision dropping and the dial's own identity grouping both see them
      as one stream -- 22 duplicate imported rows went with it (Music City
      Roadhouse, KPISS, Deep Space Radio, Retro Album Rock and more, plus a
      row labelled KTHO 590 South Lake Tahoe that was pointed at Boss Boss
      Radio's mount). `canonical_stream_url` then rewrote the 53 rows stored
      at an ephemeral CDN edge host onto `streaming.live365.com`, which is
      what the station publishes and what redirects to a live edge at play
      time; folding the duplicates had otherwise left six stations with only
      their edge-pinned row. Every surviving merged station was checked live
      (14/14 streaming, 200 audio/mpeg); the two mounts that 404 do so on
      every host and are simply off the air.
- [x] **Every stream on the dial checked, and the dead ones taken off --
      landed 2026-08-18.** `tools/check_radio_streams.py` probes all 6,463
      real streams and writes `radio_stream_health.json`;
      `import_radio_catalog.py` drops the imported casualties at build time
      and curated ones are flagged `supported: false` with a dated note, so
      the hand-written research survives a station coming back. 634 imported
      rows dropped, 131 repointed at their Shoutcast `/;` mount, 8 curated
      flagged, 7 curated repaired by hand (KDFC, WMFO, WRBH, WHYR, KFMG,
      WBWC, KEOS). Two false-negative traps are baked into the tool now:
      Python 3.12's default TLS security level refuses the older ciphers
      most Icecast hosts offer and called KBOO, WBAI, KPFK, KZYX and two
      dozen more dead while curl played every one, and a Shoutcast root
      serves an HTML status page rather than audio. Without both fixes the
      sweep reported 820 dead instead of 649.
- [x] **Terrestrial tier widened from the FCC licence record -- landed
      2026-08-18.** `tools/fetch_fcc_transmitters.py` caches all 26,212
      licensed US call signs with real transmitter coordinates, ERP and
      HAAT from the FCC's own FM and AM queries (public domain);
      `import_radio_catalog.py` reads a Radio Browser US snapshot, resolves
      the call sign out of each station's name against that list, and
      places 648 new stations across all 50 states (2,219 resolved; the
      rest collided with a call sign already on the dial or failed the
      reachability sweep). Coverage now comes from
      licensed power in six bands (8 to 55 miles) instead of the flat 40
      every imported row used to get, which had translators reaching three
      counties. The formats added are the ones the Wikidata join missed:
      classic rock, country, classic hits, top 40, oldies. Roughly 500
      commercial stations moved out of the always-available web band to the
      dial position they actually broadcast on. Two gotchas worth keeping:
      the FCC's front end answers 403 to a user agent containing a URL, and
      its query output carries deleted licences under a "D"-prefixed call
      sign that must be filtered or they shadow live stations. Names are
      cleaned of stream jargon *before* the call sign is read out of them:
      "Ambient Sleeping Pill | 128 kbps mp3" was placed at KBPS Portland's
      transmitter on the strength of the bitrate.
- [ ] **The FCC coverage bands are power buckets, not contours.** ERP and
      HAAT are both cached; the real F(50,50) contour uses terrain and
      antenna pattern, and the buckets ignore HAAT entirely. Good enough
      that a translator no longer outreaches a Class C, not good enough to
      call it modelled.
- [ ] **Only stations naming their call sign got placed.** 2,228 of the
      7,750 US directory rows resolved; the rest brand themselves purely
      ("The Fox", "Magic 106.7") and would need a name-and-market match
      against the licence list to place.
- [x] **Reach capped so the dial is not half fringe -- landed 2026-08-18**
      (owner ruling the same day: "sort by the strongest signal so the
      player isn't searching through a bunch of fringe"). The sort was
      already strongest-first in the terrestrial group; the clutter came
      from `RADIO_REACH_MULT` doubling curated ranges of 90-175 miles into
      200-350 mile monsters, against its own note about no station spanning
      three states. `RADIO_MAX_REACH_MI = 150` caps the doubled figure:
      Dallas went 33 terrestrial (15 fringe, furthest 238 mi) to 22 (4
      fringe, furthest 127 mi), and rural dials keep their stations, which
      a 120-mile cap did not. The elevation lift still stacks on top, so
      the ham anchor holds -- a 7000 ft rim reaches 245 miles where the
      flats reach 150; that test's distance moved from 300 to 220 miles and
      its premise did not.
- [ ] **A station skipped by the dial cannot be reached any other way.**
      `station_list_lines` is a read-out, not a picker, so the dial keys are
      the only route to a station. That ruled out the other fix for the
      fringe complaint (seek stepping over weak stations, as a real car
      radio does) and it is worth a picker in its own right.
- [ ] **Re-run the stream sweep before each release.** The health file is a
      snapshot, not a fact: stations come back, and a 5xx on sweep day is a
      bad afternoon rather than a closure. `--recheck-dead` re-probes only
      the casualties, which is cheap enough to be routine.
- [ ] **Finish the station song batch after the ElevenLabs quota resets
      (2026-09-06).** Gospel +5, tejano +5, synthwave +7, plus top-ups
      (8-10 each) for country, classic rock, blues, and jazz, and 2-3 new
      Night Line ballads. `tools/generate_radio.py --plan-songs` supports
      capped waves via `--limit`.
- [ ] **Ad music beds.** Light instrumental beds mixed under the ad reads,
      with a ducking pass in the imaging chain; the ad scripts only need a
      cheap re-TTS pass to carry them.
- [ ] **Owner listening pass over the generated station content.** Only
      programmatic QC has run so far; ear-check the hosts, IDs, ads, and
      new songs and regenerate any misfires by key.
- [ ] **Cruise destination-lane selection for drift lane changes.** The
      2026-08-14 fix keeps cruise from braking for the lane you are leaving,
      but only for tap changes under automated lane keeping; a held-wheel
      drift still flips the lead at the line-cross instead of the moment the
      change starts.
- [ ] **Off-air stations should not yank the dial.** Tuning past a dead
      stream should carry on around the dial from where you were instead of
      handing over to a distant fallback station (Darren).
- [ ] **Lane names past three lanes.** Left, middle, and right cannot tell
      four or five lanes apart; Sarah already hit ambiguous callouts on a
      three-plus road near Riverside.
- [ ] **Game sounds duck under the in-cab radio.** Enforcement markers and
      pass-bys currently talk over the radio instead of alongside it
      (Shane).
- [ ] **One-lane roads: a cop cannot pass you, so it should not try**
      (Shane).
- [ ] **Merging AI yields to a truck** instead of racing it for the gap
      (Shane, long-standing).
- [ ] **Should the engine start off at trip start?** Design question from
      Darren -- starting it yourself is already how the first-run
      walkthrough begins, so there is a real choice to make.
- [x] **Ramps onto another freeway no longer roll for a control
      (2026-08-18).** The half of the owner's request that was a fact rather
      than a preference. Measured: all 18,011 baked exits carry an empty
      `ramp_control`, so the seeded heuristic decides every terminal in the
      game, and 4,999 of those exits (27.8 percent) lead to an interstate.
      Every one was taking its chances with weights that hand stop signs to
      half the rural ones -- roughly 2,500 stop signs and 1,500 traffic
      lights placed where two freeways meet, which cannot happen. Now read
      off the interchange's own baked `via` (`FREEWAY_VIA_RE`,
      `Trip.interchange_at`) and decided before the dice.

      A literal 0x08 byte got written into `FREEWAY_VIA_RE` on the way in,
      from shell escaping, three times across source and test. It compiled,
      matched every interstate correctly, and silently matched "HAWAII 1" as
      well -- invisible in an editor and in a diff. A test pins the word
      boundary and builds its backslash with `chr(92)` so the check cannot
      fall into the hole it exists to catch.

- [ ] **Testers report sounds are quieter at the quiet speech rung, and
      three measured suspects all went the OTHER way (Shane P, 2026-08-18).**
      He flagged it honestly as "think, not know", then narrowed it to
      troopers. Still unexplained, and worth other ears before more guessing.

      ELIMINATED, so do not re-check these:
      1. The confirmation earcon swap (hazard-clear chime -> its own note).
         Catalog volume fell 0.75 -> 0.32, which looks damning, but MEASURED
         it is -27.5 dBFS RMS before against -23.6 after: **3.9 dB LOUDER**.
         The synthesized note is dense where the ogg chime is sparse.
      2. The trooper pass level, after `enforcement_presence` was removed and
         the scale became road post density. Measured across a real route the
         density runs 1.0 to 1.3, so the pass plays between exactly the old
         flat level and **2.3 dB louder**. It never goes below.
      3. Extra mix ducking at quiet, on the theory that far more earcons fire
         there. It does not: the duck is gated on `duck_audio_for_speech`,
         which is OFF by default, and `_play_ladder_earcon` calls
         `audio.play` directly without touching it.

      THE LESSON THAT KEEPS REPEATING: a catalog volume is a MULTIPLIER, not
      a loudness. Twice this week a suspect looked obvious from the number
      and measured the opposite way (the other was Darren's road lean).
      Measure the rendered RMS, never compare multipliers.

      WHAT WOULD ACTUALLY SPLIT IT, asked of Shane and pending: does a
      trooper sound low in EVERY speech mode, or only quiet? Every mode means
      the sound itself and the speech setting is a red herring. Only quiet
      means something in the speech layer collides with it -- and since level
      and ducking are ruled out, that would point at masking or timing: a cue
      now landing under an earcon it never used to collide with.

- [ ] **No way to route around an active work zone (Brandon, 2026-08-18).**
      "Truckers don't always go through construction work zones when they are
      active; when possible they will detour onto different roads to avoid
      the risks and delays." A fair observation about how the job really
      works, and the game currently gives no choice: the route runs through
      whatever construction the corridor carries.

      The natural home is ROUTE PLANNING, not the wheel. A driver decides
      this before rolling, off the work-zone data we already bake (the WZDx
      feeds behind the construction zones), not by improvising at 60 mph. So
      the shape is an alternate route offered when the planned one crosses an
      active zone, with the trade spoken plainly -- extra miles and time
      against the delay and the risk -- rather than a mid-drive detour.

      Not started, and it is a feature rather than a fix. Wants an owner call
      on scope: it touches dispatch, route choice, and the spoken comparison
      of two routes, which is a bigger piece than it sounds.

- [x] **URGENT, MINE, SHIPPED: the ladder silenced changed content at
      STANDARD (Darren, 2026-08-19). FIXED 2026-08-19.** Reported as
      "certain messages I can read with comma and period are not being
      spoken... the dings play but no messages... very sporadic". From their
      own log, and they are on **standard**, the default rung:

        [ladder] standard already said: 75 miles per hour
        [ladder] standard already said: 69 miles per hour
        [ladder] standard already said: 66 miles per hour
        [ladder] standard already said: 57 miles per hour
        [ladder] standard already said: Clear of the car. Right lane open.

      310 dropped lines in one leg of `game.prev.log`, "62 miles per hour"
      twelve times among them. This is my change from 2026-08-18
      (`feat(speech): standard stops repeating itself`), and it silenced
      real information at the DEFAULT rung.

      I HAD NAMED THE WRONG BRANCH. It was not FIRST_OCCURRENCE. At
      standard, FIRST_OCCURRENCE covers only COACHING, and the one line in
      the game carrying that category is keyless and edge-gated, so it
      behaved correctly. Every dropped line above is **STATUS**, which
      standard delivers on TRANSITIONS -- and TRANSITIONS' fallback for a
      line with no key was `slot = key or text`, using the text as its own
      condition. That turns "enter, worsen, and clear" into "this exact
      sentence once per leg, ever", which is why the damage grew with leg
      length and read as sporadic. Checking the CATEGORY of each line in the
      log is what found it; the roadmap's own guess would have left the bug
      in place.

      THE FIX (`_ladder_repeats`): a keyless line is a discrete moment, not
      a standing condition -- its call site has already decided this
      occurrence is worth saying -- so TRANSITIONS no longer suppresses it
      at all. The pacer's 2.5-second repeat window still stops the same line
      landing twice in a breath, which was the only repetition worth
      blunting. FIRST_OCCURRENCE now keys on `(key, text)` rather than the
      key alone, so a keyed readout whose number moves cannot be swallowed
      the same way; that was latent rather than reported, and is fixed in
      the same change.

      Three tests in `test_driving_speech_ladder.py`, driven from the log's
      own lines.

- [x] **Realistic pacing retired; the row is Relaxed and Standard (owner,
      2026-08-19).** Realistic was 40x game-clock compression -- the FASTEST
      of the three, and therefore the least like real driving, which is 1x.
      It also carried standard's pressure tuning field for field
      (`driving_modes._MODES`), so it was never a difficulty at all: only a
      clock multiplier wearing a difficulty's name. Retiring it costs no
      tuning.

      A save carrying 40.0 migrates to 20.0 in `Settings.load` and arms
      `pace_retired_notice_left`, because the migration halves the rate their
      game clock bills and nothing else would say so -- they would meet it as
      an hours-of-service day that suddenly lasts twice as long. Only the
      exact retired value migrates; a hand-edited custom scale still runs at
      whatever it says, as it always has. 40x is still reachable in play and
      still exercised by tests: `PARKED_TIME_SCALE_MULT` doubles standard
      while parked.

      Found on the way: `SettingsCategoryState.announce_entry` speaks the
      landing row through `ctx.say` rather than `speak_current`, so a
      row-specific notice hung on `speak_current` alone could never reach a
      player whose row is the one they land on -- which is every player for
      Driving mode, the first row of its category. The lane-keeping rename
      notice had the same hole, hidden only because Lane keeping is not first
      in its category. Both now fire from `announce_entry` too.

- [ ] **START HERE: facility approach zones still overlap, and the keeper
      eases for a zone three quarters of a mile away (tester log,
      2026-08-18).** The gate-zone fix in 8608e9fc was real but only NARROWED
      this. Zones still overlap each other and `_active_zone_at` takes the
      LOWEST limit among overlapping zones, so a 15 zone that starts later
      still wins at a position posted 25.

      THE REPRODUCTION IS A REAL LOG, not a bench:
      `C:/ff-tester/FreightFate/logs/game.log`, New Haven, Sargent Drive
      approach, keeper set at 25. Read it with `grep -a` (padded). The
      damning nine milliseconds:

        14:24:57  "Speed limit 25 miles per hour, in a facility access road zone."
        14:25:08   15 mph                                  <- already slowed
        14:25:12  "In three quarters of a mile, facility access road ahead. Speed limit 15."
        14:25:12  quiet silenced: "Entering facility access road zone. Speed limit 15 now."
        14:25:15  quiet silenced: "Posted limit lower; speed keeper easing to 15"
        14:25:27  "Speed limit 25 miles per hour, in a facility access road zone."

      The same instant says the 15 zone is 0.75 mi AHEAD and that it is in
      force NOW. The limit under the wheels was 25 throughout.

      THE FIX: approach zones must not overlap at all. Each leg owns its
      stretch exclusively, and the gate zone takes only what is left after
      the last street's zone ENDS rather than being laid on top of it. Assert
      non-overlap in a test -- do not eyeball the zone list, which is exactly
      how this was missed: the corrected Rochester list `(0.31,0.54,25)` and
      `(0.40,0.54,15)` was printed, read as fixed, and the overlap went
      unnoticed.

      TWO SEPARATE FAULTS RIDE ALONG AND BOTH ARE REAL:
      1. The status readout speaks `_keeper_mph` (the SET speed) rather than
         the target in force, so S says "holding 25" while the truck holds
         15. It should say the live number, e.g. "holding 15, set 25".
      2. "Posted limit lower; speed keeper easing to 15" is CONFIRMATION and
         so is an earcon at quiet. An unrequested 10 mph speed change is
         exactly what the owner's own quiet rule says must be spoken.

      DO NOT bench this with hand-written zones. Four synthetic benches over
      two sessions all came back CLEAN because tidy non-overlapping zones
      were written by hand every time; the bug lives only in the overlap that
      `_facility_speed_zones` actually produces.

- [x] **Bake-time provenance and sanity rules -- the substrate for three
      separate data bugs found on 2026-08-17/18. RULE SHIPPED 2026-08-18.**
      Owner wanted a rule about verifying OSM before baking. The provenance
      audit says the rule has to be wider than that, because only one of the
      three bugs is an OSM problem at all.

      WHERE EVERY LAYER ACTUALLY COMES FROM, counted off the baked `source`
      fields: ORS supplies exactly ONE thing, grade_segments, all 146,496 of
      them, from its route elevation profile. OSM/Overpass supplies the tag
      layers -- interchanges 18,011, lane_segments 20,666, speed_limits
      14,563 of 15,234, restrictions 259, most stops. Neither supplies
      state_crossings (OSRM geometry plus public boundary GeoJSON) nor tolls
      (hand-researched per authority, `tools/toll_rates.py`).

      THREE FAILURE MODES, THREE DIFFERENT RULES.
      1. ORS elevation is noisy and was trusted per segment: 455 grades over
         8 percent, +14.4 on I-5, on 0.2-0.3 mile spans that are bridges.
         This is the only one where "check it against an official source"
         literally applies -- FHWA publishes the interstate grade ceiling.
      2. OSM is THIN, not wrong. `maxspeed` is simply absent outside the
         14,563 segments that carry it; `ramp_control` was absent on all
         18,011 exits; facility approach speeds fall back to "25 named / 15
         unnamed" and the baked data holds exactly two values across 9,588
         legs, which is the fallback doing all the work. OSM never asserted
         anything false. We filled its silence with defaults and baked them
         looking identical to readings. Verification cannot help here; only
         refusing to let a fallback look like a reading can.
      3. OUR OWN ARITHMETIC, with fine inputs: curve radius/deflection
         computed from sparse geometry (the script derives these, OSM does
         not supply them), and the gate zone that was longer than a quarter
         of the roads it sat on. No amount of source verification touches
         these.

      SHIPPED: the rule is in `CLAUDE.md` under "Provenance: read, derived,
      or assumed -- never blurred". Every baked value declares its kind, a
      builder must announce when a layer comes back mostly assumed, a derived
      value is screened against the physical limit for its class before it is
      written, and the official sources that do exist are named there (state
      DOT design manuals, FHWA HPMS, USGS 3DEP, FHWA NBI, 23 CFR 658
      Appendix A). The contributor guide moved from `AGENTS.md` into
      `CLAUDE.md` in the same change, at the owner's request.

- [ ] **The world baked before that rule still does not declare its kinds.**
      Tagging the existing layers is its own sweep, and so is making the
      builders refuse to finish quietly. MEASURED: `ramp_control` empty on
      18,011 of 18,011; `speed_limits` unsourced on 671 of 15,234;
      `landmarks` unsourced on 4,489 of 31,384; `route_points` (7,646),
      `state_miles` (1,750), `legs` (1,290) and `route_via` (27) carry no
      `source` at all. `grade_segments`, `lane_segments`, `interchanges`,
      `stops`, `checkpoints`, `state_crossings`, `restrictions` and
      `toll_events` are fully sourced -- but "sourced" is what the 146,496
      grade segments carrying impossible slopes were too, which is the point.

- [x] **Grade data carried impossible slopes, same shape as the curve
      artifacts (audit 2026-08-18, screened 2026-08-18).** 455 of 146,496
      grade segments were steeper than 8 percent, topping out at **+14.4
      percent on I-5**, and 1,077 interstate segments exceeded the 6 percent
      design ceiling for the class. The tell was self-contradiction, not
      steepness: 336 of the 455 were labelled `flat` or `hills` rather than
      `mountain`, and 335 ran only 0.2 or 0.3 miles -- the signature of
      elevation-profile sampling over a bridge deck, not of road.

      SHIPPED as a load-time screen in `src/freight_fate/data/grades.py`,
      wired into `world_corridor.build_leg_corridor`. It could NOT copy the
      curve screen's mountain exemption: the worst record, the I-5 14.4, is
      itself labelled `mountain`. Road class carries the harder fact instead
      -- no interstate is built past 7 -- so the ceiling is the stricter of
      class (interstate 7, US 10, state 12) and the bake's own terrain label
      (flat 6, hills 8). 926 segments, 0.63 percent, are capped; US-550,
      CA-299 and the Eisenhower approach are untouched.

      It CLAMPS where the curve screen DROPS, because grades tile the leg
      continuously and `Trip.grade_at` falls through to a synthesized terrain
      average for any uncovered mile -- dropping a spike out of a real climb
      would swap a noisy reading for an invented one. The bake is untouched;
      a capped segment records the derivation in its own `source`.

      STILL OPEN, the deeper fix: the noise is bridges and overpasses in a
      30 m SRTM profile. FHWA's National Bridge Inventory gives every US
      bridge's location and length, which is exactly the mask to drop those
      samples against, and USGS 3DEP at 1/3 arc-second is a finer elevation
      surface than the one ORS sampled. A re-bake against those would remove
      the artifacts rather than cap them.

- [ ] **Ramp ends are too often stop signs (owner, 2026-08-17: "fix ramps to
      be more realistic, e.g. no stop signs at the end of ramps"). MOSTLY
      SHIPPED.** The measurement this bullet used to open with -- "all 18,011
      exits carry an empty `ramp_control`, OpenStreetMap tagged a control on
      none of them" -- WAS WRONG, and wrong in the way that mattered. The
      ramp-control bake had only ever been run over Indiana and Ohio; the
      cached index at `~/.cache/freight-fate-osm/regions/freight-fate-rampcontrols.json`
      covers exactly two state extracts and holds 161 nodes. Nobody had asked
      OSM nationally.

      DONE (2026-08-18): the 4,999 exits whose `via` names an interstate are
      decided free-flow before the dice are rolled -- a stop sign where two
      freeways meet does not exist. Then the ramp-control bake was run over
      all 49 state extracts: **8,205 of 18,011 exits (45.6 percent) now carry
      a control read from OSM** -- 5,629 signal, 2,576 stop -- across 712 of
      754 legs.

      WHAT THE REAL DATA SAYS ABOUT THE OLD GUESS: among tagged terminals the
      split is 69 percent signal / 31 percent stop. `RAMP_CONTROL_RURAL_WEIGHTS
      = (0.30, 0.80)` reads as 30 signal / 50 stop / 20 free-flow. The
      heuristic was far more stop-heavy than the road is, which is exactly
      what the owner heard. Treat the 69/31 as suggestive rather than a
      target: OSM tags signals more diligently than stop signs, and tagged
      terminals skew urban.

      STILL OPEN, 9,806 exits: OSM says nothing about them and the dice still
      decide. Two ways to close it -- retune the weights against the measured
      split, or bake the interchange TYPE from OSM junction geometry so the
      control follows the road. The second is the honest one and is the
      chosen direction.

- [ ] **The speed keeper announces a number it then fails to hold -- NOT
      REPRODUCED, mechanism unknown (owner report, 2026-08-17).** "Speed
      keeper holding 25 through the facility access road zone" while the
      truck sits near 14. **This bullet previously asserted a mechanism and
      that assertion was wrong; it is corrected here rather than left to
      mislead.**

      THREE HYPOTHESES WERE TESTED AND ALL THREE DISPROVEN. (1) The throttle
      law: replacing the bare integrator with PI plus anti-windup changed the
      outcome not at all, and was reverted. (2) The box leaving the truck
      lugging in too tall a gear: at the settle point throttle was already at
      the cap, so the loop was demanding everything available. (3)
      `_take_new_posted_limit` announcing the raised number in the present
      tense: on the real loop the truck reaches the new number in about ten
      seconds and holds it.

      EVERY BENCH REPRODUCTION WAS AN ARTIFACT, four of them, each producing
      a confident wrong answer. `_update_keeper` CANNOT be driven in
      isolation: it needs a real `Zone` under the wheels (without one it
      cancels on tick one and hands to cruise), a gear engaged,
      `transmission.automatic`, `truck.auto_shift()` every frame (**the
      driving loop runs the box, `TruckState.update` does not**), and the
      loop's per-frame brake ramp-down (`driving_updates.py` line 349 --
      without it the snub brake latches at 0.20 forever and the truck decays
      to 11 mph, which is what the wrong mechanism above was built on).
      `tests/playtest_harness.py` also hand-rolls its frame and overrides
      throttle; the only faithful driver is `driving.update(dt)` itself.

      WHAT THE REAL LOOP ACTUALLY DOES, measured: press K at 14 mph on a
      15-limit service way and it says "holding 14", honestly. Crossing into
      a 25 zone it raises to 25 and the truck is doing 24.7 within ten
      seconds. Correct behaviour throughout.

      THE ONE LIVE THREAD: when the keeper raised itself from 14 to 25,
      NOTHING was spoken -- though `_take_new_posted_limit` ends in a
      `say_event` and its own comment says an assist that speeds the truck up
      on its own has to say so. If that line fires on the owner's machine and
      not on the bench, the difference is the lead.

      NEXT STEP IS EVIDENCE, NOT ANOTHER HYPOTHESIS: a
      `FREIGHT_FATE_LOG_FILE` capture from a drive where the owner actually
      sees it, giving the spoken line, the real speed, the gear, and the zone
      under the wheels at that moment. Four synthetic guesses at those is
      what produced four wrong answers.

- [ ] **K in a low-speed zone with the speed keeper turned off speaks a
      dead end.** "Adaptive cruise is not available in a facility access
      road zone" never says the keeper exists, is off, or where to turn it
      on (Settings, Gameplay, Controls) -- it cost the owner a settings
      hunt on 2026-08-14. The line should name the setting.
- [x] **Three tester follow-ups from Darren's 2026-08-14 report -- landed.**
      The scale gets its own warning earcon -- a procedural low thump-then-
      beep, `events/weigh_station_warning` -- instead of sharing the
      inspection cue, so the open-scale notice is unmistakable before a
      word is spoken. A highway narrowing to one lane now says so whenever
      the lane-count clamp actually moves you, not only when a construction
      closure does; already in the surviving lane, it stays silent. And the
      roadside tableau -- the siren and shoulder pass for a trooper working
      somebody else -- now reliably says "not you" the moment the siren
      starts, with a seeded pinch of why (speeding, a log check, a light
      out) on some occurrences and the bare fact in terse mode.
- [x] **Second round of Dropbox tester findings -- landed 2026-08-12.**
      Passing now has a way back: a one-shot "Clear of the box truck.
      Right lane open." spoken from the same occupancy check that decides
      a sideswipe, plus an L readout of every neighbouring lane on demand
      (Darren). Driver name entry grew a real caret -- arrows review and
      speak each character, editing happens at the caret (Cary). The
      low-air warning got hysteresis so brake-heavy driving warns once
      per episode, not per dip (Darren). Traffic stops settle the engine
      sound to idle, and motel sleep shuts the engine off before the wake
      prompt asks you to restart it (Jerry, Darren). The speed keeper's
      corner hold no longer hides the next corner of a short city block
      (Shane's "turns coming up really quickly"). Live weather holds
      last-known conditions through a stale station instead of dropping
      to neutral, without traceback spam in the log.
- [x] **Resuming cruise to a high target eases up instead of flooring the
      engine -- landed 2026-08-12** (Shane's redline scream on a 12 percent
      grade). Adaptive/automatic cruise was pure proportional control: a set
      speed far above the current one commanded wide-open throttle at once.
      On the flat the governor capped it; on a downgrade it over-revved past
      redline during the automatic box's between-shift hold and charged
      engine wear. Cruise now chases a working setpoint that ramps toward the
      target at a bounded rate (CRUISE_ACCEL_MPH_PER_S), tapers its throttle
      to nothing as coupled RPM nears the governor (CRUISE_RPM_CEILING_BAND,
      so descent control and the retarder own the grade and cruise never
      feeds an over-rev), and the open-road resume waits for CRUISE_MIN_MPH
      before engaging -- the same bridge the zone-preceded automatic resume
      already gave. tests/test_cruise_resume_ramp.py pins the ramp, the RPM
      ceiling, the engage gate, and the no-redline invariant at road speed.
      Follow-up (not this fix): coasting an unbraked steep grade up from a
      near standstill still over-revs on gravity alone through the gears --
      descent-control territory, tracked separately.
- [x] **The scale announcement and the T key tell the same story --
      landed 2026-08-12** (Jerry's bypass pull-over). The open-scale
      call taught "press T", but T at speed plans a sleep stop, so the
      game planned a travel center past the scale, X armed that exit,
      and following both instructions crossed the scale unarmed into
      the cop. The notice now teaches the exit key first and the rest
      key only once stopped; T near an open scale defers to the scale;
      X prefers the nearer open scale over a planned sleep stop; a
      half-mile reminder fires if the truck is still over fifteen; a
      beginning pull-over stands any armed exit down (one demand at a
      time); and the stop-menu lookup picks the nearest stop, not the
      first listed, so T at the scale opens the scale's menu. Breaker
      scenarios scale_check_in_guidance and
      scale_pull_over_stands_down_exit pin the whole flow.
- [x] **Announcements cut off mid-sentence come back -- landed
      2026-08-12** (the mechanism behind Jerry's blown weigh station).
      An interrupting event line or an info-key reply on a shared voice
      purged whatever the event channel was still speaking; a ROUTE or
      CRITICAL line (scale notice, planned stop, HOS countdown, drowsy
      warning) died silently mid-word. The pacer now hands the cut line
      back and it requeues once, right behind the line that cut it, in
      all three voice configurations; the drowsy warning and non-urgent
      HOS countdowns ride ROUTE so they qualify.
- [x] **Speech-priority redesign, stage S1 -- landed 2026-08-12** (scoped
      by docs/speech-priority-research.md; R1, R2, R13). Delivery
      contracts per priority class: CRITICAL narrows to act-now (the
      hazard call), zone entries, checkpoints, and zone-ahead/traffic
      warnings ride ROUTE's never-dropped queue instead of interrupting
      -- shipped together with the coupled invariant that the
      accelerator-held grace collapse waits out the announcement's
      speech latency. Money lines (toll charged, fines, citations, the
      fuel-rescue bill) ride ROUTE so a busy stretch can never age a
      cost out of the queue; stale AMBIENT chatter drops silently to
      the message log instead of being promoted to an interrupt. The
      main channel queues instead of cutting while the driving state is
      on top (menus keep immediate speech). New Settings > Audio option,
      off by default (owner call, 2026-08-12: the engine is the
      instrument panel): engine, weather, and the radio duck to half
      volume while the event voice speaks, restored on the pacer's own
      clear-time projection. Later stages (naming diet, earcon pairs)
      remain open below.
- [x] **Speech-priority redesign, stage S2 -- landed 2026-08-12** (R4, R5,
      R8, R15). Verbosity moved into the delivery layer: a message is one
      SpokenMessage definition carrying normal and terse renderings side
      by side (`speech_text.py`), and say/say_event pick by the player's
      speech mode -- terse coverage is now a property of the message, not
      of 79 hand-built call-site branches. The terse contract's named
      categories converted under its two bounding rules (compress words,
      never certainty; fixed slot grammar, recorded in docs/ontology.md):
      hazard calls, traffic coaching, the curve-plus-cruise composite,
      stop callouts with all five parking-certainty values distinguishable,
      achievements to earcon-plus-name, tolls (heads-up drops, charged
      line always speaks), the speed-limit nag, and dodge confirmations to
      the hazard-clear earcon alone. The terse hazard synonym is fixed --
      "Brake or change lanes!" in every mode, pinned against the help by
      copy tests (tests/test_terse_contract.py) with a src-wide scan so
      the synonym cannot return. First-run guidance now ignores verbosity
      until the walkthrough completes (gated on tutorial_done itself).
      The long tail of messages that read the same in both modes stays
      normal-only by design.
- [x] **Info keys: R answers with a real distance, U stops reciting the
      other keys (owner report, 2026-08-15).** R rounded to whole miles, so
      the last half mile onto a facility gate answered "0 miles to the
      gate" for over a minute of surface-street driving; it now closes in
      quarter miles and then in feet or metres. The same report's "does not
      reflect the actual state of things" was three more frames: the street
      chain now names the street under the wheels rather than the chain's
      first leg, the departure chain out of the origin gate counts down to
      its on-ramp instead of reading a two-mile chain's percent as the
      run's progress and pointing "toward" the city the truck is standing
      in, and the pickup drive answers as the streets it is instead of a
      highway leg. U dropped the enforcement clause (owner ruling: that
      belongs on the CB), the next listed exit (Shift+R is that key),
      traffic pressure (it restated the taper or the stop beside it), and
      two of its three bends; it is capped at four clauses.
- [x] **Drive-time chattiness: even terse was far too much (owner,
      2026-08-15) -- landed 2026-08-16.** The terse contract only
      compressed each message; a quiet drive still talked constantly
      because compression never reduced the NUMBER of things spoken.
      Shipped from the four accessibility-practice principles the
      original design only half-applied: principle (2), the
      screen-reader verbosity model -- driving speech is now a
      four-rung ladder (coaching / standard / quiet / urgent only,
      `Settings.driving_speech`) that cuts whole categories of
      information rather than shortening all of them alike, tagged
      across all 164 driving speech call sites, with a tutorial
      exemption so a new driver's first-run teaching is never silenced
      by their chosen rung; and principle (4), announce on change --
      standing conditions (load damage, an engine held at redline, the
      parking brake locked out) speak once and then again only when
      what they say actually changes, via `say_event`'s `key=`, instead
      of repeating on a timer. Whole-drive proof:
      `tests/test_driving_speech_ladder.py::
      test_a_drive_gets_quieter_as_the_rung_tightens` drives a real
      scenario through all four rungs and pins the spoken line count
      falling as the rung tightens.
- [x] **The ladder's earcons actually play now -- landed 2026-08-16
      (task 10).** `LADDER_EARCONS` was wired only into the Learn game
      sounds screen's preview; the gate at `app.py` silenced a cut
      category, logged it, and returned, so Quiet and Urgent only were
      audibly identical -- a category the ladder cut was silence, never a
      sound, at every rung that cut it. `GameContext._play_ladder_earcon`
      now plays `LADDER_EARCONS[category]` (resolved through
      `sound_catalog.entry_by_name`, so the recipe lives in one place)
      wherever the rung's disposition is EARCON, in both `say` and
      `say_event`; SILENT still stays silent, which is now the entire
      difference between Quiet and Urgent only at the voice.
- [ ] **Sonification pass (principle 1 of the drive-time chattiness
      redesign above).** Convert spoken state updates (speed drift,
- [x] **One fact per key: Alt 1 to Alt 4 (Tim K., 2026-08-16).** R answers
      state, road, town and direction in one sentence, so hearing the one
      you wanted meant sitting through the other three at speed. Alt 1
      speaks the state, Alt 2 the road signed the way it reads, Alt 3 the
      town the truck is in -- or the nearest one, ranked by true distance
      rather than distance along the road, with how far off it sits -- and
      Alt 4 the direction of travel. Keypad numbers are equivalent. Alt
      with a number used to fall through to the engine-brake stages, so
      asking for the state changed the jake; the stage branch now requires
      Alt to be absent.
- [x] **The pad could not stop the event voice, or ask the limit (Sarah R.,
      2026-08-16).** Two gaps in the controller scheme, one of them a hole
      rather than a rough edge: `stop_event_speech` was bound only to Ctrl,
      so a controller-only driver had no way to silence an announcement and
      every one ran to the end. Every pad button was already bound, so Back
      is now context-sensitive -- it stops the voice while `event_voice_busy`
      (the same projection the audio duck restores on) and reads the
      controller help when nothing is speaking, which also stops it
      answering a driver who wants quiet with a paragraph of help. Right
      bumper plus X reads the posted limit, the pad's answer to S, in the
      slot Sarah proposed.
- [x] **Learn game sounds had no Back row (owner, 2026-08-16).** Escape
      worked and the intro said so, but every other menu in the game also
      offers a Back item -- 16 in the main menu alone -- so this screen was
      the one place a player had to have heard the intro to know the way out.
      Both screens now append it. On the category screen it runs `go_back`,
      which already stops a held demo, so the row cannot leave a cue ringing.
- [ ] **Departing straight into a hazard: work zone or merging traffic at
      mile zero (owner, 2026-08-16).** CONFIRMED, all three claims, and the
      three causes are separate. (1) No departure chain: only a facility with
      a genuine multi-segment turn-level chain gets one
      (`_departure_chain_route`); every other origin keeps the scripted
      departure straight onto the highway, so route mile 0 IS the spawn and
      there are no city miles to absorb anything. (2) Work zone at zero:
      simulated zones draw from `uniform(15, ...)` so their taper cannot
      start before mile 14, but REAL 511 zones have no such floor --
      `start_mi = max(0.0, best_leg_mile - zone_length / 2)` clamps to zero,
      so a real event near the corridor start can already cover the truck
      before it moves, with the taper behind it and nothing to announce.
      (3) Merging traffic ahead: `spawn_initial_traffic` keeps slot 0 at
      least 8 miles into a leg, but the rolling bubble's floor is
      `NO_SPAWN_AHEAD_MI = 1.1`, and a cell drawn there can roll the
      "merging" intent, so the first thing a driver hears on pulling out is
      a merge cue about a vehicle barely a mile off.
      CORRECTION to the first write-up of this bullet: the departure chain
      is NOT a fix for (2) or (3), and treating it as the honest complete
      answer was wrong. `_finish_departure_chain` hands the parked highway
      trip back unchanged and never advances its position, so the truck
      rejoins at highway mile 0 either way. A real zone clamped to zero
      still covers the merge, and the bubble still seeds around the truck at
      its 1.1-mile floor -- the chain buys a minute of streets and then
      delivers the driver into the same hazard at ramp speed.
      Measured coverage, since it sizes the data option: 3,639 of 5,054
      facilities (72 percent) depart straight onto the highway, and all 624
      cities have at least one. That is a rebuild of most approach data, not
      a gap-fill.
      SPLIT, (a) and (b) LANDED 2026-08-16 on owner go-ahead:
      (a) DONE. A real zone whose `start_mi` is inside `CONSTRUCTION_TAPER_MI`
      of the route start is dropped rather than having its taper clipped to
      nothing. Not "no hazards in the first miles" -- a zone at mile 5 signed
      from mile 4 is untouched. The game declines to place a hazard it cannot
      sign, rather than hiding work that is really there.
      (b) DONE. `MERGE_FREE_START_MI = 3.0` withholds the "merging" intent
      from the bubble inside the opening miles, keyed off the route mile so
      it also covers the on-ramp handback. Harness evidence:
      `floor_it_through_town` used to open "Merging box truck 1.5 miles
      ahead" and now opens "Slow box truck 1.5 miles ahead", with merging
      traffic still appearing later in the same run.
      (c) OPEN -- departure chains for the remaining 72 percent of
      facilities. Real and wanted, a data project to scope on its own. It is
      the realism fix, not the safety fix, and does not gate anything now
      that (a) and (b) have landed.
- [x] **The dial is inert with the radio switched off (Darren, 2026-08-16;
      owner ruling the same day).** Tuning while off used to pick a station
      silently and hold it for power-on -- deliberate, and it worked, but it
      is not how a radio behaves and it read as a station that had failed to
      play. First pass only lengthened the sentence to explain itself; the
      owner ruled for the expectation instead, which is the better call
      because matching what a driver already knows beats teaching them a
      quirk. `tune` and `tune_category` now return `_dial_is_off()` before
      touching `station_id`, and `_radio_switched_off()` in the driving layer
      ticks and speaks, deliberately the same shape as `_radio_no_power` so
      the two "not right now" answers feel like one response. It says "Radio
      off" rather than going silent -- nothing happening with no explanation
      is the one outcome a screen reader user cannot tell from a broken key.
      `select_station` is untouched: that is the game retuning off a station
      the player lost (streamer-safe, signal gone), not a dial key, and it
      has to work regardless of the switch.
- [x] **R2 caught the info keys as well as the notices (Sarah R. via the
      owner, 2026-08-16).** A 1.9 regression against 1.8, found only because
      the owner knew 1.8 muted speech on any button. On dev/main `ctx.say` is
      `speech.say(text, interrupt)` with no pacer, so every readout cut the
      line in progress. `e0230c85` (R2) added `paces_main_speech` to stop
      unasked-for lines stamping on one mid-air -- right for achievements and
      assist notices, but applied to every main-channel line at the wheel, so
      pressing a key stopped cutting too. That is the whole contract of an
      info key, and the thing a tester coming from 1.8 reaches for first.
      Fixed centrally, matching how R2 itself was done rather than tagging
      twenty call sites that gain siblings every week: `GameContext.
      player_asked()` wraps the driving state's key and pad handlers, and
      `say` exempts anything spoken inside it. Anything arriving from
      `update` still queues. The existing `_requeue_cut_event` rescue means a
      road line cut by an answer is re-delivered behind it rather than lost --
      confirmed in the probe, not assumed.
      NOTE for the record: my first reply to Sarah told her the keyboard
      never interrupted either and called the behaviour deliberate. That was
      true of 1.9's code and wrong as an answer, because she was reporting a
      CHANGE. Corrected in the living document.
- [x] **Emergency braking, pass one: two controls the pad was promised and
      never had (owner, 2026-08-16).** `emergency = keys[pygame.K_b]` was the
      only source of the emergency application, while the controller help,
      `input_hints` and the manual all said "press the left trigger fully for
      the hardest stop". A pad driver got a full service application and none
      of what the emergency one carries -- the air cue, the rumble, and every
      check keyed off `emergency_brake`. `PAD_EMERGENCY_BRAKE = 0.97` now
      arms it, gated on `not backing` because holding that same trigger from
      a stop is the reverse gesture. Worse in the same area: the microsleep
      reaction check was four keys, so a controller-only driver could not
      react to "steer or brake now" and drifted off the road every time; the
      stick and the trigger now count, at keyboard parity (a held Down arrow
      already counted).
- [ ] **PARKED BRANCH `fix/honest-brake-decel` (b2a5a43a, pushed, owner
      parked it 2026-08-16 rather than land it the night before a build).**
      Gap (a) below is DONE on that branch and measured: `max_brake_decel_g`
      0.35 -> 0.55 and `EMERGENCY_BRAKE_MULT` 1.6 -> 1.0 put a loaded rig at
      215 ft from 60 mph, and make `full_service_decel_mps2` describe the
      truck the brakes actually are. `CARGO_HARD_BRAKE_G` 0.45 -> 0.8 came
      with it (0.45 was unsourced, chosen to sit in the gap between the old
      full-service and emergency figures; 0.8 g forward is 49 CFR 393.102,
      already cited in the comment beside it). Three tests rewritten to the
      new model, not loosened.
      WHAT BLOCKS THE MERGE, and it is a decision rather than a bug: two
      assist tests fail, one of which encodes the owner ruling of 2026-08-11
      that the automatic braking assist must actually stop in time. The 1.6x
      boost was what delivered that. With the emergency application no longer
      stronger than a full pedal, a hot, worn, wet, 6-percent-downgrade stop
      at 65 loaded genuinely cannot be made in 2.5 s, and escalating buys the
      assist nothing. RECOMMENDED RESOLUTION: keep the ruling by engaging the
      assist EARLIER -- a fade margin on its budget, since in-stop fade is
      what the boost was quietly covering -- rather than letting the truck
      brake harder than physics allows. Do not rebase this onto a moved
      `feat/career-1.9` without re-running the full suite: the change moves
      every stopping distance in the game.
- [ ] **Emergency braking, realism gaps still open (measured 2026-08-16).**
      Two found while doing the above, neither a quick win, both wanted:
      (a) THE BUDGET DISAGREES WITH THE STOP. `EMERGENCY_BRAKE_MULT = 1.6`
      makes the emergency application 5.49 m/s^2 against a full service
      application's 3.43 -- 211 ft versus 334 ft from 60 mph. But
      `full_service_decel_mps2`, whose own docstring says it is "what an
      emergency-braking budget must use", returns the UNBOOSTED figure, so
      every stopping-distance cue is computed on a truck 1.6x weaker than the
      one B actually delivers. Note before changing it: 211 ft is close to
      real modern tractor-trailer performance and the FMVSS 121 reduced-
      stopping-distance ceiling of 250 ft, while 334 ft is a pre-2011 truck.
      That points at `max_brake_decel_g` being low and the boost quietly
      compensating, so the fix is probably to raise the base and drop the
      multiplier rather than to nerf the emergency stop. Needs an owner call
      on feel, since it moves every stop in the game.
      (b) NOTHING EVER LOCKS UP. The jake has a traction cap and
      `jake_slipping` to start a trolley jackknife; the foundation brakes
      have no equivalent. Grip does scale the force correctly (measured: 5.49
      dry, 3.85 wet, 0.99 on glare ice, all under the tire limit), so the
      truck is never superhuman -- it simply always makes a clean stop, with
      no lockup, no lost steering and no jackknife however hard it is slammed
      on ice. There is no ABS modelled either, so this is idealised rather
      than either era of real truck. The bigger of the two jobs.
- [ ] **PARKED BRANCH `worktree-speech-endorsements-1.9` (e780ab21, pushed).
      The drive-time speech ladder, held until the endorsement slice starts
      (owner, 2026-08-16).** 28 commits of speech work despite the branch
      name -- there is NO endorsement code on it yet, which is what it is
      waiting for. Ready otherwise, and verified rather than assumed:
      `feat/career-1.9` is merged INTO it as of 623a0bc6 (two conflicts, both
      from the same day -- the settings import still carried the removed
      `ENFORCEMENT_PRESENCE_LEVELS`, and both sides had appended a roadmap
      bullet in one spot), full suite 4011 passed, adversarial 34 passed with
      one xfail matching this branch, ruff and compileall clean, four harness
      scenarios CLEAN.
      WHAT THE MERGE EXPOSED, now fixed on that branch at e780ab21: the
      branch had documented a KNOWN_OPEN on `settings_flips_mid_drive` where
      a CONFIRMATION takes the pacer's protected hand-back slot, so the next
      interrupting main-channel line resurfaces a finished confirmation over
      the line the player just asked for. Rare until this branch met
      `fix/asked-for-speech-cuts`, which made every info key an interrupting
      main-channel line -- probed on the merged tree, S spoke the limit and
      the stale "Transmission changed to manual." came straight back behind
      it. `_track` now refuses the slot to a CONFIRMATION whatever priority
      it carries, the KNOWN_OPEN entry is deleted in the same change as the
      strict XPASS asks, and two pacer tests pin both halves.
      KEEP MERGING career-1.9 INTO IT while it waits; the overlap with the
      speech work is where the surprises are.
- [ ] **Drive-time chattiness: even terse is far too much (owner,
      2026-08-15) -- next speech-redesign target, grounded in
      accessibility practice.** The terse contract compressed each
      message; the drive is still too chatty because compression does
      not reduce the NUMBER of things spoken. The grounding from
      accessibility practice points at four principles the current
      design only half-applies:
      (1) Sound before speech (Game Accessibility Guidelines: key
      information carried by audio cues; audio-game convention:
      continuous state belongs in continuous sound -- engine pitch,
      surface texture, panning -- events in earcons, speech ONLY for
      what sound cannot carry, like numbers and instructions). Candidate:
      a systematic pass converting spoken state updates (speed drift,
      gaps opening, weather shifts) to the earcon/sonification layer,
      speech kept only for the first occurrence as a teaching pair. The
      ladder's three earcons (Coaching note, Status note, the reused
      Hazard clear chime) now play for real (see above) -- what remains
      is everything past those three categories: speed drift, gaps
      opening, and weather shifts have no sonified substitute at all yet
      and still speak in full every time regardless of rung.
- [ ] **Per-minute cruise speech budget (principle 3 of the drive-time
      chattiness redesign above).** The live-region politeness model's
      missing half: the S1 pacer already drops stale AMBIENT lines, but
      nothing yet caps how many polite messages a busy stretch of road
      can queue in a minute at cruise. Add the budget so a jammed
      stretch coalesces or defers to the message log instead of
      speaking a backlog late.
- [x] **`Disposition.FIRST_OCCURRENCE` and `Disposition.TRANSITIONS`
      are implemented.** Shipped 2026-08-17. Both behaved exactly like
      FULL because `Settings.speaks()` branches on EARCON/SILENT alone,
      so standard's own table was a promise nothing kept. The
      bookkeeping cannot live in `Settings` (it needs per-line memory),
      so it sits in `GameContext` beside the pacer: `_ladder_said` is
      leg-scoped for FIRST_OCCURRENCE, reset from
      `DrivingUpdateMixin.update` on a leg change, and `_ladder_last`
      holds the last text per key for TRANSITIONS -- identical text is
      the condition re-asserting itself, changed text is the transition.

      `reset_event_condition` clears the last-text memory too. Without
      that, a condition that genuinely cleared and came back word for
      word never spoke again; the air-brake lockout test caught it,
      which is the "swallows a genuine re-warning" failure the original
      review of this area forbade.

- [x] **Curve records that contradict their own geometry are screened at
      load (2026-08-17).** Found in an owner playtest: a 160 ft "hairpin"
      on US-285 turning 79.9 degrees over 53 feet of road, where that
      geometry needs 223. Both existing screens passed it correctly -- it is
      in real mountain terrain, which they deliberately leave alone. The new
      screen asks only whether a record agrees with itself, which terrain
      cannot excuse: span against the arc its own radius and deflection
      require, plus zero-tangent opposite-direction pairs (the digitized-kink
      signature, and what caught this one). Drops 1,190 of 51,231 surviving
      mainline rows, 2.3%. Connectors exempt, matching the screens above.

- [ ] **Advisory speeds above 80 mph in the baked curve data.** 298 of 804
      curves on four sampled mountain routes carry an advisory over 80,
      including 85 -- no US advisory plaque reads that. Harmless today only
      because an advisory above the posted limit never fires a pacenote, so
      nothing is spoken and nothing is wrong on the road; it is the bake's
      0.3 g formula running unclamped on gentle curves. Worth clamping at
      the bake so the data means what it says, and so a future consumer
      cannot read one as a real number.

- [x] **The coaching rung is removed (2026-08-17).** Measured on two
      scenarios after the dispositions went in: byte-identical transcripts
      against standard, 6 and 8 lines each. The rung's two cells only bite
      where a coaching tip repeats, and exactly one line in the game carries
      `SpeechCategory.COACHING`. An inaudible setting is worse than one
      fewer setting here -- a player cycling it hears nothing change and
      reasonably concludes it is broken. `DRIVING_SPEECH_MODES` is now
      three; a saved "coaching" migrates to standard through the existing
      unknown-rung fallback. The CATEGORY and its earcon stay.

- [ ] **Coaching's technique tips, and the rung to hold them.** The reason
      the rung was removed rather than kept: there is nothing to say in it.
      Writing the tips means adding COACHING-category lines (there is one
      today, chains hammering above the safe speed) and re-adding the rung
      as one row of `DRIVING_SPEECH_DISPOSITIONS` plus its menu copy. The
      FIRST_OCCURRENCE machinery standard uses to blunt them is already
      built and tested, so the rung would be audibly different from standard
      the day the first tip lands.

      Worth knowing before writing them: the status readouts that repeat
      mostly carry a changed number, which is a genuine worsening and
      correctly still speaks at standard. So a tip only earns the rung its
      difference if it is the kind of thing that would otherwise be said
      more than once per leg.
- [x] **Urgent only's NAVIGATION row is a genuine act-now filter (final
      review of this branch, finding 5).** Shipped 2026-08-17 as the
      option the bullet asked for: a real filter inside NAVIGATION rather
      than a declaration that the taxonomy split was already enough.
      NAVIGATION_ADVISORY carries the lookahead half -- the lead
      announcement ("in a mile, take exit 42"), the bend coming, the place
      still miles off -- and retires to the Road ahead note earcon at
      urgent only while NAVIGATION keeps the turn itself, the exit, and the
      stop. Measured on a headless I-65 run: quiet 29 lines, urgent only
      26, against 0 apart before. Player-facing copy went back to a real
      promise in the same change (settings row, its help text, the user
      manual, docs/ontology.md).

      Found while doing it: STOP_AHEAD looks like a lookahead and is not --
      "Road Ranger at exit 292 in one mile. Press X to signal" names the key
      that takes the stop, so a tone in its place removes the only way to
      pull in rather than making the drive quieter. It stays act-now, the
      same rule the pacing module already gives for CONFIRMATION.

      The bullet's real cause was structural and is worth keeping written
      down: before this, quiet and urgent only differed in COACHING and
      STATUS alone, and both were already inaudible at quiet -- so the two
      quietest rungs were the same setting with different names. A test now
      fails if any future table lands back in that shape.
- [ ] **A stale CONFIRMATION line can resurface and bury what the player
      just asked for (found by task 10, adversarial scenario
      `settings_flips_mid_drive`).** A `CONFIRMATION` line (e.g.
      "Transmission changed to manual.") is usually spoken with
      `interrupt=True` and no explicit `priority=`, so `say_event`
      defaults it to `EventPriority.CRITICAL` -- and the pacer's
      protected-hand-back slot, built to rescue a ROUTE or CRITICAL line
      an interrupt plausibly cut off mid-sentence, holds onto it on the
      same terms. The next interrupting line on the main channel (an S
      query, another settings flip) purges the channel and hands the
      confirmation back to be requeued, even though it already finished
      speaking and what it reported may already be contradicted -- and it
      resurfaces after, sometimes burying, the line the player actually
      just asked for. Recorded as a strict xfail in
      `tests/adversarial/test_break_scenarios.py::KNOWN_OPEN`. Needs a
      pacer design change so CONFIRMATION does not occupy the
      ROUTE/CRITICAL hand-back slot; out of scope for task 10.
- [x] **Speech-priority redesign, stage S3 -- landed 2026-08-12** (R6, R7,
      R9, R10, R11, R12, R14). The naming diet and the noise cuts: facility
      names speak in full on first mention per leg and short after, with the
      type prefix dropped when the proper name already carries it (R6);
      demonstrated instructions retire -- engine start, the controls-help
      pointer, the exit-signal prompt stop repeating once the player has done
      them, gated on a persisted counter keyed to control binding and
      transmission so a remap or a manual gearbox re-teaches (R7); achievement
      flavor leaves the drive entirely, mid-drive announce is earcon plus name
      in both modes and the settlement collapses a run's badges to one named
      row, flavor kept in the log and the achievements menu (R9); the
      settlement drops the rows that report the unremarkable default -- no new
      damage, a full tank, an undamaged truck, the empty career-messages
      placeholder, the standing carrier-charges note (R10); the load-damage
      coaching tail speaks once per episode, escalations carry only the new
      number (R11); off-pavement becomes a standing condition -- speech at
      transitions only (entry, worse, back on), the pre-existing panned
      edge-rumble ladder carrying position in between (R12); and the dodge
      outcome pair (hazard-clear and collision) is learnable on both sides in
      the sounds screen (R14).
- [x] **The chatter switches work in terse -- landed 2026-08-15** (owner:
      "Roadside chatter is pinned to the normal or terse setting. When
      terse, the individual settings don't mean anything"). Terse returned
      before the five switches were consulted, so a terse player had five
      switches on by default that did nothing. The switch decides what is
      spoken and verbosity decides how much is said about it: an enabled
      category now speaks in terse as its short form -- the name and the
      fact, framing dropped -- built as a SpokenMessage pair
      (`speech_text.roadside_chatter`) like the rest of the S2 work.
      Villages are untouched; they answer to the place-callouts ladder.
      Principle (2) above, in miniature: the switch is the ladder, and
      verbosity stops overriding it.
- [x] **Exit traffic speaks only for the exit you are taking -- landed
      2026-08-15** (owner, the same day as the chattiness note above: "when
      exits come up, the game announces traffic info for that exit. Suppress
      all of those types of announcements unless the player signals for the
      exit"). Every route stop grows an exit-traffic pressure a couple of
      miles ahead of itself, so a corridor thick with truck stops narrated
      exit after exit the driver had no intention of using. The advisory is
      now gated in the driving layer on the exit being signalled -- or on
      lane keeping taking it for the driver -- and the trip marks the
      pressure announced either way, so arming late cannot dump a stale
      call. Merge, construction-taper and traffic-pack pressures are
      untouched: they warn about the road the truck is already on. A first
      concrete cut under principle (4) above, announce on change not on
      state.
- [ ] R12 follow-up: redline and low-air are still discrete re-speaks rather
      than the transition-plus-continuous-cue model off-pavement now uses. The
      transition speech is straightforward; the continuous half wants an
      engine-strain tone for redline that the pack does not yet carry, so it
      rides the sound-hunt list with the cruise earcon below.
- [ ] A dedicated cruise-adjust earcon for terse mode's curve composite
      (the easing clause currently folds into the pacenote; the curve
      chime plus audible deceleration carry it), auditioned alongside the
      other sound-hunt needs and added to the learn-sounds screen.
- [ ] **Remaining tester findings from the same document.** Merging
      traffic does not yield to a loaded truck. At least one unexplained
      sound (a whoosh on the left). Landed 2026-08-12: work-zone closures
      keep one authoritative side so the announced lane always matches
      the coned lane, and spoken-event dedup stops standing warnings
      re-reading themselves and stale speech replaying after a pause.
- [x] **Owner manual playtest round -- landed 2026-08-12.** Five real
      playtest_road sessions over the tester-fix build verified the
      work-zone side authority, the lane-return cue, the speech dedup
      across a 25-minute pause, the once-per-episode air warning, and
      the name-entry caret by ear -- and surfaced five more bugs, all
      fixed the same day: a blown stop at a no-chain destination ramp
      terminal stranded the drive silently while cruise auto-resumed
      into it (now the fourth loop-back, with cruise held off the whole
      ramp); hazard warnings offered lane changes on roads with no lane
      to change into; the posted-limit drop spoke three times and too
      late to act on; the hazard assist pumped the service brakes (an
      air cost per re-press, which is what kept draining the tanks) and
      its emergency escalation never reached the wheels; and a dead NWS
      station pinned its route cell to simulated fallback forever (the
      fetch now walks to the next-nearest live station).
- [x] **Speed keeper holds street speed on access roads -- landed
      2026-08-12** (Armstrong's report, secondhand). Three defects: the
      keeper's number could only fall, so a session begun on a 15 mph
      service way crawled the whole facility approach while the zones
      announced 25; the ease window priced the whole shed at entry
      speed (40 percent early on a 25-to-15 drop, crawled rather than
      re-planned since the eased number became a held floor); and a
      slower lead anywhere in the traffic bubble's 2.5-mile reach was
      matched outright with no distance test. All three fixed with the
      spoken hand-back-up line; queue creep and hand-set speeds
      unchanged.
- [x] **Traffic drove at fixed speeds while the map got faster.** The
      intent bands were absolute mph (cruising 52-64, merging 38-52,
      braking 35-48) chosen before real OSM speed limits were baked per
      leg, and they never moved when the map did. On a 75 mph Texas
      corridor the whole population ran 20-40 mph under the road, which
      the driver met as a lead-vehicle cue telling them to leave room for
      30 for a semi on an interstate (owner playtest, 2026-08-15). Speeds
      are now drawn as offsets from the posting at the spawn mile, with
      the floor a share of that limit rather than one absolute number, so
      the same bands suit a 75 corridor and a 30 mph street. NPCs read the
      car limit, not the truck cap, so in a split-limit state the traffic
      going by a rig held to 55 is doing a legal 65.
- [ ] **Adaptive cruise's own limit lookahead ignores time compression.**
      `_acc_limit_lookahead_mi` sizes cruise's slow-down trigger with the
      same uncompressed braking physics the limit pacenote just moved off
      of, so at high pacing cruise can start easing later than a spoken
      warning would like. Same real-seconds conversion, cruise's turn.
- [x] **Adversarial battery findings, 2026-08-12 run (31 scenarios: 28
      clean, 3 odd) -- all three SHIPPED.** A gate-overshoot loop-back
      repositioned the truck on 20 minutes of free time with the HOS
      driving clock never moving; it now charges real hours-of-service and
      fatigue and burns idle-rate fuel for the loop, so the spoken "the
      clock is still running" line is true. A settlement that jumps
      several career levels announced only the last one; every rank
      passed now gets its own "Level up" line with its own unlock. The
      streak-compounded short-hop XP edge is addressed by the streak-cap
      fix below.
- [x] Short-hop XP farming reined in: the on-time streak bonus is capped
      at the mileage XP (25-mile-hop efficiency 4.9x to 4.6x versus a
      500-mile haul, honest pacing to level 30 unchanged at 335 hours).
      The remaining gap is the flat completion XP, kept by design.
- [x] **Five small bug fixes, 2026-08-12.** A trooper's out-of-service
      order now shuts the engine down like every other overnight stop
      instead of leaving it running while the wake-up line told the
      driver to start it. Docking and pickup check-in gates, and a
      settling POI stop, now snap engine audio to idle instead of
      freezing at the approach's revs -- the same fix already shipped for
      roadside stops, now shared through one `_settle_engine_to_idle`
      helper. Running off the road asleep a third or later time now
      speaks the real count instead of freezing at "twice now".
- [x] **Billboards, round two, 2026-08-12.** Seventeen new owner-written
      roadside boards in the rotation (roadfood, trucker-commerce, and
      fourth-wall genres), plus song tribute boards for the achievement
      catalog: forty-plus signs on the corridors that raised the music,
      corridor-keyed (nineteen new shield keys) or riding a low-weight
      tribute pool that draws about one sign in ten. Titles and artist
      names only, never lyric quotes.
- [ ] Billboard tribute copy could use one more polish pass with the
      owner's own eye -- shipped at "good enough for now" after three
      revision rounds; the closer style rules are in the module docstring.
- [ ] Split the first-drive tutorial across multiple runs (owner call,
      future session). Interacts with the speech redesign's R15 rule:
      first-run guidance is exempt from verbosity until the walkthrough
      completes, so a multi-run tutorial changes what "complete" means.
- [ ] The playtest rig records speech submissions, not deliveries -- it
      bypasses the real pacer, so transcripts cannot show dropped or
      cut-off lines. Route the rig through the pacer (or add a
      pacer-aware mode) so the adversarial battery can catch speech
      regressions.
- [ ] The blown ramp terminal and missed street turn loop-backs still
      charge only clock time -- same free-time defect fixed for the
      facility gate and destination exit; apply `_charge_scripted_loop`
      to both.
- [ ] **The no-engine-brake ban only knows route cities.** It rides
      `URBAN_RADIUS_MI` (6.0) around route nodes, so small towns a leg
      merely passes through are not modelled at all -- in a survey only
      17 of 70 assisted curves fell inside any ban zone, and 4 of 26 on
      one mountain route. An assist-raised retarder can never be fined
      (`driver_owns_jake` excludes it), so this is realism rather than a
      money bug, but it is why the retarder barks through bends an
      experienced driver reads as a ticket waiting to happen. Widening
      the radius is an owner call.
- [x] **Fines rebalanced against real trucking penalties -- SHIPPED
      2026-08-11** on `feat/fines-rebalance`, merged after the driver-assist
      fixes so the penalties land on player error. Unsafe equipment to 2,300,
      weigh station bypass to 1,800, chain law to 580, following too
      close to 600, lane misuse to 500, shoulder to 400, lights to 350,
      failure to stop to 1,500. A 2x multiplier inside a construction
      zone (taper included) and repeat-offender escalation extended from
      speeding to every fine, compounding rather than adding. All amounts
      and both multipliers now live in `models/enforcement.py` behind one
      `citation_fine` helper; `CHAIN_LAW_FINE` had two live definitions
      on different paths, one shadowing the other, now collapsed.
- [ ] **Detention, lumper fees, washouts and tolls are spoken but never
      paid.** `carrier_charges` (`driving_menu_states.py:975`) computes
      them and feeds two spoken strings; nothing moves money. The game
      tells an owner-operator "you are owed 90 dollars in detention" and
      then does not pay it, and bills them for nothing. Wrong in both
      directions, and the owner-operator start is the mode that feels it.
      Found by the 2026-08-11 realism audit; full report in
      `docs/realism-audit-2026-08.md`.
- [ ] **Nothing ever weighs the truck.** Loads routinely gross to about
      87,000 lb against the 80,000 lb federal limit, and "overweight"
      appears nowhere in `src/`. Meanwhile every open scale costs a
      mandatory 15 minutes of duty-window time with no bypass concept,
      where a clean real carrier is waved through 85-90 percent of the
      time. So the game charges for scales but never enforces the thing
      scales exist for -- punishing and unrealistic in the same feature.
- [ ] **Relaxed hours-of-service mode misreports the law.** It multiplies
      the legal limits by 1.25 and then speaks 13.75 hours as "the
      11-hour driving limit". Whatever the mode does to the numbers, the
      spoken text must not name a real regulation it is not enforcing.
- [ ] **Two roadmap claims are already false.** Split sleeper berth (8/2
      and 7/3) is fully implemented despite lines further down this file
      saying twice that it is not. Also worth knowing: the 30-minute
      break rule is implemented to the current 2020 regulation, and at
      least one practitioner source still describes the pre-2020 version
      -- following that source would break working code.
- [x] **The barrel citation is no longer doubled for the zone -- SHIPPED
      2026-08-11.** It was the one citation that can only happen inside a
      construction zone, so the multiplier always applied and it was
      always charged 2,000. Its base is Missouri RSMo 304.585, already
      the work-zone-specific penalty, which caps a first offense at
      1,000 -- doubling charged twice for the same aggravating fact. The
      zone multiplier now applies only to offenses whose base is not
      already zone-specific. Priors still escalate it.
- [ ] **Spoken "work zone" contradicts the ontology.** `sim/trip.py`
      lines 2229 and 2234 speak "Work zone active" where
      `docs/ontology.md` makes "construction zone" canonical. Pre-existing
      drift, found while fixing the lane trap.
- [ ] **A resolved enforcement stop re-speaks its fine amount.**
      Re-entering a settled stop replays the whole line including the
      dollar figure without charging anything, because `_resolve()` runs
      in `__init__` and `announce_entry` has no once-guard. The money is
      safe, but the repeat is word-for-word identical to a fresh charge,
      so there is no way to tell one from the other. Lead a re-entry with
      past tense instead; do not silence it, since re-reading the stop is
      the only way back to the detail.

- [x] **Break-harness findings now assert what they claim, and the one
      real one is fixed -- SHIPPED 2026-08-10.** Triaging the harness's
      2026-08-09 findings against transcripts, four of nine were
      artifacts rather than game bugs, and acting on them would have
      meant "fixing" working code: `slam_reverse_at_speed` called
      `Transmission.request_gear` beneath the road-speed guard the gear
      keys actually reach; `hazard_ignored_to_100_damage` compared a
      mid-run spoken line against post-rescue damage;
      `neutral_coast_mountain` hardcoded "no mechanical failure" while
      its own transcript walked the truck to out of service; and
      `hos_marathon_and_rest_cheese` appended a finding in the `else` of
      a check whose `if` asserts the opposite, so it could never come
      back clean. All four now check the consequence instead of
      asserting its absence. 26 clean, 5 odd, down from 9.
      `reverse_down_the_route` was the real one: a mile backed down an
      interstate with no wrong-way feedback of any kind, an
      accessibility gap before a realism one, since the only spoken line
      was a merge instruction for the exit being reversed away from. New
      `states/driving_wrong_way.py` ladders remind -> illegal -> traffic
      on distance backed, exempting the yard, stops and the receiver's
      gate zone.
- [x] Break-harness findings, all now shipped: the facility-gate loop-back
      now charges HOS driving time, fatigue, and idle fuel alongside the
      20 game minutes; a multi-level settlement now speaks one line per
      rank passed; short-hop streak XP is addressed by the streak-cap fix
      earlier in this section. (The save/reload hazard finding was closed
      2026-08-11 as not reachable -- see the bullet below on why serializing
      it would be
      worse.)
- [x] **A full lot no longer closes the fuel island -- SHIPPED
      2026-08-10.** Owner-reported from a live run. `_open_poi_stop`
      diverted to `ParkingFullState` whenever a stop carried `sleep` and
      the overnight crunch rolled full (20:00-04:00), and that `return`
      swallowed the whole stop -- so the biggest truck stops, the ones
      most likely to carry `sleep`, were exactly the ones that turned a
      driver away from their pumps overnight, with running dry the
      likely outcome. The fuel purchase moved to a `_FuelPumpMixin`
      shared by `RestStopState` and `ParkingFullState`, and the full-lot
      menu now leads with the pumps when the stop has them. Note for
      later: the game models no opening hours at all (the scraped
      `opening_hours` OSM tags in `data/spider/vehicle-access-cache.json`
      are dead data), so nothing else is time-gated -- if stop hours are
      ever wanted, fuel islands should stay 24-hour.
- [x] **Load-shift realism retune -- SHIPPED 2026-08-10.** Benched
      through `tools/playtest_road.py` (which now reports cargo
      condition, peak deceleration and worst bend overspeed in its
      headless trace) and found two faults. Braking: the threshold sat
      at 0.25 g against a truck whose service brakes top out at 0.35 g,
      so one full application from 65 mph cost general freight 13.3 pct
      -- past the exception line -- and food 31.9 pct. Securement is
      rated to 0.8 g forward under 49 CFR 393.102, which no Class 8 rig
      can reach, so the threshold moved to 0.45 g: full service stops
      are free, the emergency application (0.58 g measured) costs about
      3 pct, and a grade adding its own g still bites. Cornering: the
      model read raw mph over the advisory, which ranked bends backwards
      -- a 472 ft sweeper at +15 cost 7.1 pct while a 198 ft hairpin at
      the same +15, pulling 0.68 g against the sweeper's 0.51, cost only
      2.8 pct. Rebuilt on geometric lateral g from the curve's own
      `min_radius_ft` (new `TruckState.corner_lateral_g`, fed by
      `driving_damage`, with an advisory-derived fallback for legs whose
      data carries no radius), threshold 0.40 g -- above every shipped
      advisory, below the 0.5 g lateral securement rating. Every bend in
      the game is now free at its posted advisory.
- [x] **Test-suite streamlining, first pass -- SHIPPED 2026-08-10.**
      The count was never the problem. 6,614 of the 9,720 tests lived in
      `tests/test_radio.py`, and 6,599 of those were one parametrised
      function doing field-presence checks on static catalog rows: 89 s
      of near-pure pytest overhead at ~13 ms an assertion. Collapsed to
      a single sweep that reports every bad entry at once (89.21s ->
      2.00s), plus the tuning test that walked all 5,092 receivable
      stations to prove a set membership (33.5s -> 0.32s). Suite is
      9,720 -> 3,122 with no coverage lost. Separately, `-n auto` on the
      28-core developer machine was not merely pinning the CPU, it was
      dying with an INTERNALERROR in the reporter -- almost certainly the
      same "node down" the CI xdist notes describe. Worker curve on 140
      driving tests is flat past eight (n=4 48s, n=8 31s, n=16 31s), so
      `tests/conftest.py` now implements xdist's
      `pytest_xdist_auto_num_workers` hook and caps auto at 8; CI runners
      are below the ceiling and unaffected.
- [x] **Adversarial battery reports through pytest -- SHIPPED
      2026-08-10.** `tests/adversarial/test_break_scenarios.py` runs the
      same registry `tools/playtest_break.py` does, so the scenarios stay
      one source of truth and the CLI (`--scenario NAME --transcript`,
      still the way to read spoken output) is untouched. The ODD-vs-FAIL
      ambiguity that let four bogus findings sit untriaged is gone: a NEW
      odd finding fails, the four known-open ones are strict xfails
      carrying their explanation in `KNOWN_OPEN`, and fixing one turns it
      into XPASS, which fails and says to delete the entry. Marked
      `adversarial` and deselected in addopts; `tests/conftest.py` also
      skips collecting the directory unless the marker is asked for,
      since deselection happens after collection and collecting it pulls
      in pygame and the whole scenario package for nothing. 28 passed,
      4 xfailed in 7 s under the worker cap -- faster than the tool's
      serial run, so the "it is fast because it is outside pytest"
      worry did not survive contact. Watch for: a second conftest under
      `tests/` claims the bare module name `conftest`, which broke
      `test_online_presence.py`'s `from conftest import FakeKeyring`.
      The loader lives in the test module for that reason.
- [ ] **Three adversarial scenarios need triage after the playtest_break
      transcript-capture fix (task 9 of the driving-verbosity-ladder
      plan, 2026-08-16).** `tools/playtest_break.py` and
      `tools/playtest_road.py` used to stub `ctx.say`/`ctx.say_event`
      themselves, which sits outside `GameContext.say`/`say_event` and
      so skipped the event pacer entirely -- every transcript either
      tool ever produced showed every line a scenario's code path
      attempted, not what a player actually hears once repeat
      suppression runs. Fixed to stub the voice layer
      (`ctx.speech.say`/`say_event`) instead. With the real pacer now
      running, three scenarios turned ODD that were CLEAN before:
      `fuel_rescue_farming` (expects 3 identical roadside-rescue
      announcements, gets 1 -- may be a genuine silent-second-rescue
      accessibility gap, or just the scenario's own timing landing
      inside the repeat window), `scale_check_in_guidance` ("T mid
      scale warning" response goes missing), and
      `settings_flips_mid_drive` (a direct call to `_speak_speed_limit`
      lands inside the repeat window of an earlier routine
      announcement and is correctly dropped, so the assertion reads a
      stale `transcript[-1]`). None investigated further -- out of
      scope for a proof-and-paperwork task. Each needs a human to judge
      real bug vs. stale scenario-script assumption, then either a
      small scenario-script fix (advance past `EventSpeechPacer.
      REPEAT_WINDOW_S` before asserting, or read `rig.said(...)`/
      `lines_with(...)` deltas instead of `transcript[-1]`) or a
      `KNOWN_OPEN` entry in `tests/adversarial/test_break_scenarios.py`.
- [x] **Passing traffic you can actually hear -- SHIPPED 2026-08-10**
      (player-requested). Five bugs in the existing bubble, no redesign:
      traffic was stepped on the raw `time_scale` while everything else
      ran on `effective_time_scale`, against that property's own
      docstring, so NPCs slid relative to the truck whenever pacing eased;
      `spawn_initial_traffic` drew one candidate per 85 miles, once, and
      never replaced what the cull retired, so the bubble drained as a run
      went on; everything was seeded ahead, so the `passing` intent could
      never pass; `_leg_density` was multiplied by `hazard_scale` (the
      relaxed-mode hazard knob times the time-scale tuning's hazard
      frequency, landing at 0.11), which is the rule enforcement already
      settled -- presence is not difficulty; and no pass earcon existed
      for bubble vehicles at all. Now: a rolling window that spawns ahead
      and behind with deterministic per-cell draws, clear air around the
      cab so nothing materialises alongside, a drawn exit mile so a slow
      vehicle cannot pin the truck for the rest of the route, density
      tracking the live local hour rather than the departure hour, and
      `states/driving_traffic_pass.py` firing a class-matched whoosh
      panned to the side, rate-limited in REAL seconds because ten times
      pacing turned a populated road into a cue every 2.2 seconds.
      Measured: bubble 0-3 -> 10-19 vehicles, pass-bys 0 -> 4-7 per 6 mi,
      cues across every class. `TrafficManager.rolling_bubble` turns the
      top-up off for tests that hand-place their own road.
- [ ] Traffic follow-ups the above surfaced: the player cannot overtake a
      slow vehicle under automatic lane keeping, so being held up is
      currently resolved only by that vehicle's exit mile -- an actual
      pass manoeuvre is the real answer. Also worth a look: the
      `traffic_slowing` achievement ("Bumper-to-Bumper Blues") was
      unreachable on the old empty road and now fires, so its wording and
      rarity have never been reviewed against real play.
- [x] Superseded detail from the original report, kept for the record:
      (1) **Nothing plays when a vehicle passes.** The cues hang off
      `TrafficManager.next_situation`, which returns a situation only for
      `merging`, `braking` or `following` -- a hazard needing driver
      action -- and only once per vehicle ever
      (`announced_vehicle_keys`). A vehicle simply overtaking is silent.
      This is the same wiring the trooper-cue note in `traffic_manager`
      already describes, and it is wider than the trooper.
      (2) **There is almost nothing out there to pass.** Peak bubble was
      0-3 vehicles at hours 7, 8, 9, 17 and 22, and actual pass-bys --
      an NPC changing which side of the truck it is on -- were ZERO at
      every hour except one trooper at 09:00. Vehicles are culled only
      at 2.0 mi behind, so they are not being lost before crossing;
      `spawn_initial_traffic` seeds them ahead along the leg and nothing
      ever comes up from behind, so the bubble is a set of lead vehicles
      you slowly close on rather than a living road.
      Fixing this needs an overtake event keyed on relative position
      (pan by side, level by closing speed), separate from the hazard
      announcement path, plus enough density for it to fire. The audio
      is not the blocker: `traffic/semi_pass` was replaced 2026-08-10
      with a real Blastwave FX roadside take (peak/median 43x, 1948 rpm
      under load) and it changes nothing until the above lands.
- [ ] Shared App() fixtures, if ever worth it. Measured 2026-08-10 and
      NOT the bottleneck: a boot is 149 ms warm across 83 files, while
      the full suite is 3,114 tests in 3:54. What is left is a handful of
      legitimate broad sweeps -- the network-wide deadline check (58 s),
      the whole-board route check (53 s), and 113 s of full deliveries in
      `test_mapped_state_lines_are_authoritative_in_delivery_transcripts`,
      three params of which are strict xfails re-confirming the ambient
      message-queue bug documented in that file. Fixing that queue
      deletes those xfails and about 90 s with them, which is the real
      lever; trimming the sweeps would trade coverage for seconds.
- [x] **Adversarial "break the game" harness -- SHIPPED 2026-08-09.**
      `tools/playtest_break.py` (plus `tools/playtest_break_scenarios/`,
      split by system family to stay under the practical-file-size
      guideline) drives DrivingState and the menu-flow harness through 31
      deliberately unreasonable scenarios across every system -- physics
      (floor it through town, reverse down the interstate, coast a
      mountain in neutral, dynamite the parking brake at 60), assists
      fighting each other (cruise/curve/descent stacked, the jake-zone
      toggle dodge, the new facility-gate overshoot with the approach
      assist on and off), resources (fuel-rescue farming, a 22-hour HOS
      marathon, micro-rest cheese, a motel room one minute from a
      deadline), career/economy (settlement honesty, the advance-abandon
      cycle, endorsement wallet edges, the level-up boundary, the
      owner-operator buy-in gate at exactly level 18, short-hop streak
      XP farming), dispatch board-reroll farming, save-scum during a
      traffic stop or a live hazard, chain-law and glare-ice physics, and
      radio-dial abuse. Each scenario checks its own invariants (money
      finite, position monotonic, spoken numbers matching real state) so
      a rerun after any change flags regressions without a transcript
      read. `--list` / `--scenario NAME` / `--transcript`; the whole
      battery runs in well under a minute, single process, no window.
      First run: 17 clean, 14 odd findings (see PR/session notes for the
      ranked list) -- none fixed here by design, this lands the harness
      and the findings for the enforcement-overhaul and damage-band work
      already in flight to triage against.
- [x] **Bake the remaining curated billboard sheets -- SHIPPED
      2026-08-09.** All 23 sheets baked with zero copy changes; blockers
      finished the same day at the owner's direction: the sixteen
      stale-leg blocks re-pointed onto today's split corridors (approved
      copy untouched, exit-verified Route 66 placements), and the five
      do-not-bake blocks replaced with new in-style signs (Navasota
      blues capital, Tallahassee canopy roads, Little America, Terre
      Haute's Coca-Cola bottle, Leavenworth's Bavarian village). Final
      tally: `billboard_sign` 42 -> 233 across all sixteen regions,
      `highway_marker` 59; index regenerated and verified. Still open,
      non-blocking: Ape Cave stays held for a future Mount St. Helens
      route per its note, and twenty-odd baked blocks carry soft
      "verify" fact-notes in their sheets for an eventual fact pass.
- [x] **Achievement categories, on Saltwake's model -- SHIPPED
      2026-08-09.** The catalog (172 badges, grown past the planned 145)
      now carries seven categories with per-category earned counts, and
      the Achievements screen browses in two levels exactly on the
      Saltwake shape: category menu first ("title, earned of total"),
      then that category's badges -- earned ones tell their story,
      locked ones keep to their title (the existing no-spoiler idiom),
      and five hidden calendar/number badges stay "a secret the manifest
      is keeping" until earned. Copy tests cover category titles and
      descriptions; the category noun joined docs/ontology.md. Owner
      voice pass over the seven titles/descriptions still worth a
      listen before release.
- [x] **Screen artifact curves out of the highway bake -- SHIPPED
      2026-08-09.** Loader-side screen in `data/curves.py`: interstate
      mainline records under 300 ft radius or over 150 degrees of
      deflection are sweep artifacts (city-anchor departure geometry and
      interchange vertices baked as mainline) and are dropped on load --
      3,113 records, taking interstate mainline hairpins from 1,604 to
      zero. The raw bake keeps every row; ramps/connectors and all
      US/state-route records are untouched (US-550's 36 switchbacks and
      Glenwood Canyon survive verbatim, verified). RESIDUE CLOSED
      2026-08-09: the US/state pass found its discriminator -- local
      terrain at the hairpin's apex (a real hairpin cannot sit on flat
      ground). tools/screen_curve_artifacts.py classifies every
      non-interstate hairpin-severity curve against the archived
      elevation profile and writes curve_artifacts.jsonl (963 flat-
      terrain artifacts across 372 legs, skipped by the loader like the
      interstate screen); all 385 hill/mountain hairpins kept, US-550
      and Salt River Canyon verified untouched, tests pin both sides.
- [x] **No career transfer from 1.8 and earlier -- SHIPPED 2026-08-09
      (owner ruling 2026-08-08).** `created_line` marker on every new
      save; pre-marker 1.9 tester careers pass via the save-version
      discriminator (versions 6+ exist only on the 1.9 line; dev/main
      stopped at 5) and get stamped on first load. The load gate raises
      before migration or resave so old files stay byte-for-byte intact
      and 1.8-playable; legacy careers stay listed with a clear label
      and open a kind notice offering a fresh start; a same-named new
      career refuses to overwrite a legacy save. Cloud restores refuse
      pre-1.9 snapshots three layers deep without deleting anything, and
      orinks-net (branch feat/legacy-restore-gate) pre-clears the marker
      in the validator allow-list. KNOWN IRREDUCIBLE: a 1.8 career a
      tester already continued on an early 1.9 dev build was rewritten
      as v6+ back then and passes the gate -- that history is gone.
      CUTOVER REMINDERS: Convex deploys before any build with the marker
      ships, and the full invariants-export regen (version ceiling to
      11) is still the existing cutover checklist item -- today's dev
      validator still rejects 1.9 uploads as unsupported_version.
- [x] **1.9 data on online profiles -- SHIPPED 2026-08-09** (game merge
      plus orinks-net branch `feat/profile-1-9-fields`). The drivers-board
      line names the tuned station while driving with the radio on
      (detail-string append, board only, display name never a stream
      URL). Durable profile career statistics add lifetime career
      earnings (`Career.total_earnings`, rounded), badges earned out of
      the catalog, endorsements in unlock order, and -- company drivers
      only -- the carrier fleet tier; the server derives all display from
      the invariants export (`endorsements` + `fleetTiers` tables now in
      it), and no new field entered the signed payload. The disclosure,
      Online-hub help, and manual all say it plainly: lifetime earnings
      is public, the current money balance is never published. Pre-1.9
      snapshots render exactly as before (test-pinned). Leaderboards
      deliberately NOT here: they get their own pass (and the per-driver
      vs per-career identity decision) once the 1.9 baseline has real
      data -- they inherit the stats-pinned-to-first-career guard.
      The cutover invariants regen landed on the same preview branch
      (ceiling 5 to 11, stable saves keep validating), so a real 1.9
      build pointed at the preview validates end to end; at dev cutover,
      re-regen if fields drifted and replay stored prod blobs before the
      prod deploy.
- [ ] **Public career should follow the career you open (Shane,
      2026-08-14) -- design decision needed.** The public-career chooser
      (orinks-net dev b2b8a5c, publicSaveName) makes fronting a career a
      manual step, and Shane asks for the active career to become the
      public one automatically. The sharp edge: testers keep throwaway
      fiddle careers, and blind auto-follow would publish an experiment
      the moment it is opened. Leading candidate (Shane's own follow-up):
      ask once per career, spoken -- "do you want this career public on
      the boards?" -- yes is public, no is private but still backed up;
      backups never depend on the answer. Paired suggestion: the drivers
      board names the career in play ("munchkinbear, playing on career
      littlebear"), which would also surface the known presence-vs-stats
      career mismatch honestly instead of hiding it. Owner call before
      any build ships it.
- [x] **Staging validator repaired end to end for honest saves
      (2026-08-14 night).** Three refusal classes fixed in one evening:
      unknown fields from another build line are tolerated (issue #97
      doctrine), the money ceiling credits the richest career start (the
      owner-operator's 18,000 rejected as impossible_money until then --
      the exporter now ships startingMoneyMax), and money may run
      negative because 1.9 debt IS an overdraft. Every rejected upload
      is now retained as evidence, not just the arithmetic families --
      four honest-save bugs in a row had to be diagnosed blind because
      schema-family refusals vanished on arrival. Root operational
      lesson: the branch's Vercel builds never deployed Convex (the
      deploy key was dev-scoped), so fixes "deployed" all evening
      without reaching testers; feat/profile-1-9-fields now carries its
      own production deploy key and auto-deploys to
      scrupulous-ferret-428 on every push, proven in build logs. All
      stuck testers (trssharp, munchkinbear x3 careers, jessie, sarah)
      confirmed backing up the same night.
- [x] **The computer cap's refusal names a control the page has
      (armstrong445, 2026-08-15).** He could not connect the latest build:
      orinks.net refused the activation at the ten-computer cap, and the
      refusal told him to "remove one on the setup page" -- a page whose
      buttons say Sign out and have never said Remove. The site's message
      now names signing out, says why the list fills with the same PC, and
      links to the page (orinks-net dev, 5f5df49).
- [x] **The computer cap counted activations, not computers -- FIXED on
      staging 2026-08-15.** Every freshly unzipped build that connected
      minted another row, so a tester who takes a build a week filled the
      list of ten with one PC and was locked out. A client-side fix
      (remembering the sign-in in the platform secret store) was written
      and REVERTED on owner ruling: a copy extracted to a clean folder must
      be a clean game, and may consult only that folder and the game's
      appdata. The counting is the server's, so the fix is the server's --
      the game names the computer with an opaque hash when the player
      deliberately activates (never a hostname; equality is all it is used
      for), and redeeming replaces that computer's row instead of adding
      one. The cap skips a computer already on the list, so a full account
      can still reconnect the PC it is signed in on, and a build that sends
      no key behaves exactly as before. orinks-net dev 542bb69, deployed to
      staging and verified against dev.orinks.net. An account that already
      collected ghost rows still needs one pass of Sign out all computers.
- [x] **The Online menu opens the driver setup page (owner, 2026-08-15).**
      Follow-up from the above: the recovery for a full computer list, a
      driver rename, or a sharing change all live on a page whose path
      (/freight-fate/online/setup) nobody should have to remember, and the
      game had no way to reach it. New hub row "Open my driver setup page"
      opens `online_presence.setup_page_url()` -- staged host included --
      with the Mastodon opener's clipboard-then-spoken-address fallback for
      remote and streamed sessions. Deliberately its OWN row rather than a
      job the account row takes over once connected: that row is also the
      way back in when orinks.net stops accepting this computer, which is
      the moment a player needs to re-activate rather than browse, and it
      is what AUTH_HELP names.
- [ ] **PRE-RELEASE MUST-DO: point the game back at production.** The
      1.9 test line defaults its online services to the staged
      deployment (dev.orinks.net, the orinks-net dev branch on its own
      Convex backend). Before the 1.9 release: flip DEFAULT_BASE_URL in
      online_presence.py back to PRODUCTION_BASE_URL and drop the
      2026-08-staging entry from PUBLIC_KEYS in cloud_save_integrity.py.
      Staged accounts and backups are test data and do not migrate.
- [x] **Staging restored after Convex collected its backend (2026-08-11).**
      Convex deletes preview deployments five days after they are created
      on the free and starter plans, and it collected the one behind
      dev.orinks.net. Every online surface failed at once -- the drivers
      board, the updates feed, and every driver profile -- and the tester
      accounts, careers, cloud backups, and the staging signing key went
      with it. Staging is running again on a fresh preview deployment
      (charming-terrier-46) with a regenerated signing key, since the old
      private half existed only inside the deleted deployment. Testers
      need a build carrying the new public key before cloud restores
      verify. Staging data does not survive this kind of loss, so treat
      it as throwaway.
- [x] **Staging now runs on a deployment that cannot expire
      (2026-08-11).** dev.orinks.net is served by
      scrupulous-ferret-428, the production deployment of its own Convex
      project (orinks-net-staging2). Production deployments have no
      lifetime, so the five-day preview clock no longer applies to
      staging. The dev branch reaches it through a Vercel
      CONVEX_DEPLOY_KEY scoped to Preview (dev), plus CONVEX_DEPLOY_FLAGS
      carrying `--check-build-environment disable` -- Convex otherwise
      refuses a production key from a preview build. Both are
      branch-scoped, so every other branch still gets throwaway previews.
- [ ] **Dead Convex deployment left behind: industrious-parrot-713**
      (project orinks-net-staging), the first attempt. It never accepted
      a push -- three tries, each hanging 300s before a 408 on
      evaluate_push -- while an identically configured deployment
      created minutes later took its first push in 21 seconds. Reported
      to Convex on Discord 2026-08-11. Delete it once they answer, but
      copy the signing key out first: `convex env get` still works on
      it, and it is one of the few places that private half exists.
- [ ] **A first push can fail spuriously.** charming-terrier-46 rejected
      its first push with `InvalidModules: Cannot read properties of
      undefined (reading 'error')`, naming no module, then accepted the
      identical code seconds later. Not universal -- scrupulous-ferret-428
      was fine first time. If a push fails that way, retry before
      believing the commit is broken.
- [x] **Staging cloud backups fixed for 1.9 careers (2026-08-09).** Day
      one of staged testing surfaced it: every company-driver backup was
      silently refused as `invalid_possession`, because the validator's
      possession rule still demanded the career own the trainer rig and
      its active truck -- the 1.8 model that 1.9's dispatch-assigned
      fleet ended (fresh careers own nothing until the level-18 buy-in,
      and the buy-in keeps the assigned tractor, not the rig). Fixed on
      orinks-net dev (4616cf5): possession now checks only that truck
      keys are real and listed once, the forensics-first stance the money
      rule already took. Rides to prod with the normal dev-to-main merge
      at cutover. The game's Cloud backup menu also stops claiming
      "ready" while the setting is off and offers the opt-in in place.
      LESSON FOR THE CUTOVER AUDIT: the invariants-export regen was
      byte-identical and still missed this, because the stale half was
      rule LOGIC, not data -- and replaying stored prod blobs cannot
      catch it either, since every stored blob predates the new model.
      At the dev cutover, replay freshly played 1.9 careers (company new
      hire, slip-seat level 4+, post-buy-in owner-operator) against the
      validator, not just the stored-blob corpus.
- [ ] **THE BACK HALF OF THE ARC IS FLAVOUR TEXT (direction set
      2026-08-09).** An audit of all thirty ranks found every real
      mechanical unlock lives in levels 1-13 (endorsements, regional
      fleet, extra decline, board growth to 6/7/8 offers, choosing your
      own loads at 8, a dedicated tractor at 9, premium fleet at 13).
      Levels 14-16 only make text visible ("Working-capital target
      becomes visible"), and 19-30 are twelve levels of flavour
      ("Specialty trailer programs matter more", "Top career rank").
      That is why the owner-operator start was placed at 18 -- it sat
      exactly where the ladder stopped paying out.
      OWNER RULING: do NOT build a fleet-management layer -- it would
      duplicate the separate dispatch game and drag a blind player out
      of the cab into menus. The first half is EARNING TRUST; the second
      half is CARRYING RISK. Same cab, same road, higher stakes. Every
      addition must pass one test: you can hear and feel the difference
      from the driver's seat. Planned spine: harder freight classes
      (tanker surge first, then oversize/overweight with permits and
      route restrictions, hazmat with route bans and inspection
      scrutiny), dedicated contract lanes you can fail, owned trailers
      with their own upkeep, and authority turning the board into a
      market you price rather than a list you pick from. If the second
      act cannot be filled with real mechanics, the honest fix is fewer
      levels rather than more flavour -- validate the ~335h curve
      against whatever actually ships.
- [x] **Owner-operator start begins at level 1 (2026-08-09).** It used
      to grant LEVEL_XP[17] (level 18) plus 35 deliveries, 42,000 miles
      and 70,000 dollars of lifetime earnings -- all published to the
      public profile as career history that never happened. The option
      now grants only what it is about: the tractor, 18,000 dollars of
      working capital, and every operating cost. Freight access was
      never the reason for the high level -- all three endorsements
      unlock by level 4.
- [x] **Invariants regen for the tank endorsement and safety record --
      DEPLOYED TO STAGING 2026-08-10** (orinks-net dev `74370b9`). The
      diff was BIGGER than the implementing agents believed: five new
      top-level profile fields, not three. `selection_score` and
      `out_of_service_events` were reported as nested on `DrivingRecord`
      and are not -- they reach `profileFields`, so without this every
      1.9 backup would have failed `invalid_schema` again. Verified both
      directions before deploying (current payloads rejected by the live
      export, accepted by the regen) and confirmed live afterwards by
      uploading a real backup. LESSON: never take "no regeneration
      needed" on trust; diff the export.
      STILL OWED AT THE DEV CUTOVER: the same regen against production.
- [x] **Sound pack repacked for liquid surge -- 2026-08-10.** 274 to 277
      entries; `tests/test_sound_pack.py` pins the length and SHA-256 and
      both were updated. Pushing it needs `git lfs push origin <branch>`
      by absolute path first (git-lfs is not on PATH here), then the
      normal `git push`.
- [ ] **A real endorsement path (owner, 2026-08-15) -- design from
      actual CDL structure.** Four endorsements (refrigerated,
      heavy_haul, high_value, tank -- three of them done by level 4) is
      not meaningful progression. The real credential ladder has far
      more rungs, and each maps naturally onto freight, lanes, and pay
      the game already models. Proposed two-track path, grounded in
      FMCSA structure:
      RESTRICTION REMOVALS (early game): a fresh CDL can carry
      restrictions that are lifted by training, not levels -- the E
      restriction (automatic transmission only) is the natural first
      rung and ties straight into the game's existing transmission
      setting: train out the restriction, drive manual boxes, better
      settlements on manual-spec tractors.
      CARRIER CERTIFICATIONS (early-mid, sponsored): today's
      refrigerated / high-value stay here, joined by flatbed load
      securement (steel, lumber, machinery classes) -- these are
      company training, not CDL law, and dispatch trust is the gate.
      CDL ENDORSEMENTS (mid-late, real names, knowledge tests +
      course fees + time): T doubles/triples (unlocks double-trailer
      freight), N tank (the existing tank endorsement, renamed to its
      real letter), H hazmat -- the standout game beat: ELDT theory
      course PLUS a TSA background check with a real waiting period of
      in-game days and a fee before chemicals-class freight opens --
      and X (tank + hazmat combined) for fuel-tanker work.
      SPECIALIST CREDENTIALS (late game): LCV certification (49 CFR
      380: requires the T endorsement plus six months of Class A
      experience -- a real prerequisite chain worth copying) unlocking
      turnpike doubles/triples ONLY on the specific corridors that
      allow them, which fits the real-map corridor data; TWIC port
      card for container freight out of port cities; oversize/
      overweight permits per state with pilot-car escorts, curfews,
      and route surveys deepening heavy_haul from one unlock into a
      permit economy.
      Pacing intent: restriction removal in act one, first CDL letters
      in act two, LCV/TWIC/superload in act three -- so the back half
      of the 30-level arc earns credentials instead of only numbers.
      Each rung is a course (money + dwell time, motel-style), some
      with prerequisites and waiting periods, all spoken in plain
      language with the real-world name given once. Validator note:
      endorsement keys ride the invariants export, so every new key is
      an exporter regen + staging deploy in the same change.
- [ ] **Jail for a pursuit, not a three-hour "processing" fee.** Owner
      question 2026-08-10, roadmapped rather than built. Speeding is a
      citation even at the extreme end, so no change there -- but fleeing
      police is a genuine arrestable felony, and the game currently
      charges 5,000 dollars, 12 percent damage and 180 minutes of
      "processing" before releasing the driver to the terminal. Three
      hours is booking, not custody. The realistic version holds the
      driver for days of game time, which the "wait out the CDL
      suspension" flow at states/city.py already knows how to advance --
      except automatic rather than chosen. It would also make the
      one-year major-offense disqualification land properly, since the
      driver would come out of custody into a licence they cannot use.
      Must not become a dead end: the notice has to state the release
      date and what still works, per the save_notice cadence.
- [ ] **Give the horn gameplay.** Owner idea 2026-08-10, roadmapped.
      Today it is a sound with no consequence. Real horn use is
      functional and situational: warning a vehicle drifting into your
      lane, alerting someone reversing across your path, the blast at a
      blind corner or an uncontrolled crossing, and the pull-the-cord
      wave to a kid. Mechanically it should be able to PREVENT an
      incident -- a drifting car warned off in time is a collision that
      does not happen, which turns a hazard from a reaction test into a
      decision. It should also cost something when misused: leaning on
      it inside a town is the same municipal noise ordinance the engine
      brake already answers to. The hazard and traffic systems it needs
      both already exist, so this is cheap for how much it adds, and it
      fits the "carrying risk" spine for the back half of the arc.
- [x] **"A live hazard does not survive save and reload" -- CLOSED
      2026-08-11 as not reachable, not fixed.** `_hazard_deadline` is
      genuinely absent from the snapshot, but no save can be written while
      one is running, so there is nothing to save-scum. Every
      player-reachable save needs a parked truck or an open menu (the
      rest-stop save, the motel, a city service with the parking brake
      set), and the one save taken mid-roll is the traffic stop, which
      cannot begin during a hazard: `_begin_pull_over` has a single
      caller, `_begin_observed_stop`, reachable only when
      `_enforcement_busy()` is false, and a live hazard is one of the
      things that makes it true. The scenario reached it by calling
      `snapshot()` directly. Serializing the deadline would be the worse
      bug -- the player would resume on a braking clock they never heard
      the warning for -- so `save_scum_enforcement` now asserts the gate
      instead of the round-trip, and its `KNOWN_OPEN` entry is deleted.
- [ ] **Wear ceilings need their own wall.** The damage bands shipped
      2026-08-09 with a 90 percent out-of-service cutoff, but brake,
      engine, and tire wear at 100 percent still only fade physics --
      no band ladder, no spoken ceiling warning, no "your brakes are
      gone" wall. Verified they are not duplicated by the damage bands;
      this is the natural follow-up.
- [ ] **Senior-driver reassignment on a grounded tractor.** A company
      driver at level 9+ has a dedicated seat and cannot be moved into a
      yard spare without a new persistent Profile field, so they get a
      road-crew patch instead. Given the cloud-validator profile-shape
      history, that field wants its own change.
- [ ] **Cornering damage to the tractor, not just the freight.** A bend
      taken far too fast now costs the load; body damage from cornering
      needs a roll/lateral-load model that does not exist yet.
- [ ] **Reefer spoilage.** Temperature-controlled loads cannot fail
      because no temperature simulation exists to fail; deliberately not
      faked when cargo damage shipped.
- [ ] **A tow, distinct from roadside repair.** The out-of-service
      recovery is a single roadside-repair contract mirroring the fuel
      rescue. A real tow -- where the truck ends up somewhere else and
      the load is affected -- was flagged rather than half-built.
- [ ] **Rename `steering_assist` to `lane_keeping_assist`.** The name is
      inverted: `"off"` means the truck holds the lane FOR you, and
      `"realistic"` is the manual task. Two studies independently flagged
      it as the reason "turns are already manual" reads false. Deferred
      from the turn-commitment pass only because it touches ~40 test call
      sites and would have collided with concurrent work; values map
      `off -> full`, `light -> partial`, `realistic -> off`, and existing
      saves must migrate to today's behaviour, not to a harder game.
- [ ] **Police phases 2-5** (`docs`-less design captured 2026-08-09):
      typed enforcement posts replacing `PatrolWindow` with an observation
      model (geometry, line of sight, weather, traffic cover, severity);
      the full inspection ladder (Levels I/II/V, vehicle out-of-service,
      roadside repair, scale weighing and overweight); staged pursuit with
      a surrender branch and telegraphed spike deployment; urban units
      giving the engine-brake citation a body; ports of entry. Phase 0
      (data + RNG split + pull-over persistence + control hints) and the
      scale data landed 2026-08-09.
- [ ] **Enforcement catch rate is still the weak link.** Fines and the
      violation ladder are tuned per citation, but patrols cover only
      ~4.6% of a 600-mile route in realistic mode, 0% under 120 miles,
      and a 5.5-mile window is 3.8-7.6 REAL seconds at high pacing --
      shorter than `SPEEDING_HOLD_S` (6.0), so at the fastest pacing a
      speeder can be structurally unable to accrue a strike inside a
      patrol. The presence model above is the fix.
- [ ] **Extend the missed-gate overshoot to the pickup and city-service
      gates.** The delivery gate now loops you back when you carry past
      it too fast (2026-08-09, third instance of the scripted loop-back
      pattern); the pickup gate and city-service arrivals still pin the
      odometer at the end regardless of speed — same treadmill, same fix
      pattern, deliberately left out of the first pass.
- [x] **Speak refused backups where the player can hear it.** The manual
      half shipped 2026-08-14 (Shane's report): Save game at the terminal
      now runs the backup immediately (`CloudSaves.backup_now`, no
      debounce or backoff) and speaks the outcome -- accepted, already
      backed up, rejected with the career named, conflict, paused
      sign-in, or still retrying. The background half shipped 2026-08-15
      (owner decision): a background upload's terminal refusal --
      rejected, conflict, or paused sign-in -- now queues one spoken
      line (`CloudSaves.take_announcements`, drained by the app's main
      loop like the controller-disconnect notice), once per cause per
      career until the cause changes or the slot uploads again, with a
      career-named all-clear when backups resume. Transient network
      failures still retry silently; the manual Save game item still
      owns its own attempt's result.
- [ ] **Report client sync status server-side so stalls are diagnosable
      from the dashboard.** The client now logs its per-career sync state
      at startup (2026-08-13), but that only helps for testers who share
      logs; a player whose backups silently stop (Trssharp, Jessie) is
      still a black box. Have the client include a small per-career
      status report with its existing traffic — last upload result,
      recorded conflict and its cloud revision, reason for the last skip
      — stored per driver on orinks-net for the dashboard. Metadata
      only, no save content, riding the existing cloud-backup consent.
      Two-repo change that touches the server, so it waits for the
      validator cutover to settle rather than shipping mid-window.
- [x] **Country-originals music batch (2026-08-08).** Thirty-one tracks
      from the owner's originals zip: five day beds, eight night beds, ten
      country-station songs, the seven-track Nashville After Hours jazz
      station, and a seventh menu milestone bed at level 21. At the time the
      repo shipped `sounds.pak` only (LFS); the loose `assets/sounds` tree
      stayed builder-local and tests fell back to the pack on clean clones.
      The music/ subtree later split into its own `music.pak` with the
      2026-08-14 station-identity batch.
- [x] **Freight Fate stations play everywhere (2026-08-08).** The twelve
      fictional stations plus Nashville After Hours are always available --
      no transmitter bubbles, every mode -- grouped with Roadhouse and
      Night Line on the dial. Reception physics stays covered by fixtures.
- [x] **Live weather immediate and never simulated mid-run (2026-08-08).**
      Station-shared observation cache, city-menu warm-up, first fetch at
      trip construction, and failures hold last-known conditions; simulated
      fallback survives only for a session that was never online.
- [x] **Dead streams hand over instead of going silent (2026-08-08).** A
      stream that refuses to play announces itself off the air, hands over
      within its dial category, and leaves the dial for the session.
- [x] **Dev sync 2026-08-08 (through the 1.8.8 release).** Merged from `dev`:
      activation-code online setup replacing clipboard paste, the one-time
      first-run orinks.net offer (spoken after 1.9's first-day briefing, with
      the city menu's announcement queued so nothing is cut off), corykad's
      transmission and clutch-damage fixes, Day Garwood's save-restore fixes
      (date/season, deadline, and quit-mid-drive saves), live weather that
      follows the truck and reports its freshness honestly, and the pause
      states' move into `driving_pause_states.py` -- carrying 1.9's snow
      chains and carrier repair billing along.
- [x] **Standalone builds no longer die midway on machines without Visual
      Studio (tester report, 2026-08-08).** Nuitka falls back to a downloaded
      MinGW64 GCC there and ran one compiler per CPU core; the parallel
      compilers exhausted memory partway through the ~360-module compile and
      the build failed with a GCC error (elevation never helps -- no build
      step needs admin). `tools/build_release.py` now caps compile jobs to
      one per 2 GB of RAM on such machines and says so; MSVC machines and CI
      keep Nuitka's defaults. Ported to `dev` via PR #151.
- [x] **Rest-stop sleep selection and stopping recovery.** T now plans and
      names the exact nearby sleep stop without silently taking its exit, and
      an independent default-off assist can finish the entrance stop only
      after the player signals and takes that selected exit.
- [x] Add one driving-assistance preset selector with independently adjustable emergency braking, lane, stop-and-go, descent, exit, destination, curve, and route-transition support while preserving player confirmation and control.
- [ ] Add future individual yard-entry guidance and assisted docking; no current preset navigates a yard or completes a delivery.
- [x] **Spoken-message review from the cab (PR #122, Day Garwood).**
      Comma and period walk the message log, Ctrl with either jumps to the
      first or latest, the brackets switch category, and Ctrl+C copies the
      current line. Merged from `dev`; the radio dial moved to semicolon
      and apostrophe to make room, and the app-wide speech repeat now
      stands aside for any state that reviews its own log.
- [ ] Decide whether the app-wide speech repeat and the categorised message
      log should stay two features. They answer the same need with the same
      keys, and only the state flag keeps them apart today.
- [x] **Stop-sign terminals got the bar instruments (playtest
      2026-07-22, third session) -- FIXED same day.** Every bar-position
      instrument (countdown, closing tick, S query, stopped-short
      guidance) was gated to signal terminals; a stop-sign ramp was one
      announce line and then the damage message. All four now answer
      for the sign, with sign-specific wording.
- [x] **Ramp-terminal light folded into route-transition assistance
      (owner direction, 2026-07-22 playtest).** Positioning on the stop
      bar blind under a live light cycle was damage-or-nothing (the
      second playtest ended with cross traffic clipping the trailer on
      a red the driver was still braking for). The assist now brakes
      for red/dying-yellow, holds the stop at the bar until green, and
      caps green crossings under the clean-roll speed; phase speech and
      the pull-ahead stay the driver's. Assist off keeps the fully
      manual bar for the realistic tier.
- [x] **Facility-arrival overshoot trap (playtest 2026-07-22, Gary to
      Chicago) -- FIXED same day.** The gate warnings latched after one
      announcement, so rolling past a pickup, delivery, or city-service
      entrance at speed meant silence for the rest of the drive (six
      minutes and the on-time bonus lost; recovery only found by reading
      the session log). All three gates now re-speak their stop
      instruction every ten seconds while the truck is still moving,
      cancel any re-armed cruise on each repeat, and the S key answers
      with the gate instead of the ended route's posted limit.
- [x] **Route status goes stale after the destination exit (same
      playtest) -- FIXED same day.** R now answers by phase: on the
      street chain it names the current street and the distance to the
      gate; on a scripted approach it drops the highway framing; at
      the gate it says "You have arrived" plus the gate instruction,
      agreeing with the S key. The surface trip also learned the
      facility's name for its fallback cue.
- [x] **Curve speed assistance thrash (same playtest) -- FIXED same
      day.** Engage/release now has hysteresis (engage over advisory +
      5, hold until within 2) and the spoken cues carry a 15-second
      cooldown, so a cruise-vs-curve-brake fight can no longer chant
      slowing/released seven times a second.
- [x] **Indiana and Wisconsin real-traffic feeds rebuilt -- SHIPPED
      2026-08-09**, with the full-registry sweep. Indiana, Minnesota,
      and Colorado now ride the CARS GraphQL platform
      (`POST /api/graphql`, `MapFeatures` query, incidents +
      construction); Wisconsin and nine more states (AZ, CT, FL, GA,
      ID, NV, NY, NC, PA, UT) read WZDx v4 work-zone feeds at
      `/api/wzdx` -- the old camelCase WZDx parser could not read v4,
      so this fixed every live WZDx state at once. TPIMS truck parking
      rebuilt on Wisconsin's 13 live sites (Ohio's keyless endpoint is
      gone), and the rest-stop parking consumer no longer hardcodes
      Ohio at a fixed coordinate -- the feature is reachable anywhere a
      feed exists. Eleven states stay no_api with dated notes: OH, TX,
      OR, WA (key walls -- could return if the project ever ships API
      keys), CA and TN (dead DNS), MD, MI, MO, NJ, VA (404/403/SPA).
- [ ] **Incidents for the WZDx-only states.** The platform-wide death
      of the old `/api/events` endpoints means the ten WZDx states get
      construction only; live incidents work on the three CARS states.
      Find per-state incident feeds (or CARS siblings) for the big
      WZDx states, FL and NY first.
- [x] Cruise vs. curve brake, the deeper fix -- SHIPPED 2026-07-22
      (owner direction, same-day playtest): a pacenote now caps the
      cruise working target to the bend's advisory (like the armed-exit
      ramp cap) and releases silently past the curve footprint, so
      cruise drives the bend instead of fighting the assist brake.
      Manual handoff survives only for advisories under the 20 mph
      cruise floor.
- [x] **Air buzzer once after a shoulder rest -- RULED OUT 2026-08-09.**
      Owner ruling: not worth chasing; the one-off buzzer read as
      unrealistic and the item is closed without a fix. The honest
      low-pressure warnings and the cold-start buzzer-defer stay as
      they are.
- [x] **Cruise sags on a loaded pull instead of revving out (owner
      playtest, night of 2026-07-22) -- FIXED 2026-07-25.** Two causes,
      both confirmed on the bench. The controller was integral-only at
      0.08 per mph-second, so it needed over ten seconds just to reach
      full throttle while the hill was already taking a mile an hour a
      second; it now feed-forwards from `Truck.hold_throttle()`, the
      throttle the truck's own physics says balances the grade under the
      wheels, and only trims from there with P and I (anti-windup, so a
      grade the engine cannot pull does not bury the integrator). And
      the automatic never downshifted, because the revs were not lugging
      yet: `auto_shift` now takes a pull downshift when the pedal is on
      the floor, the road is going up, and the truck is still losing
      ground -- gated on the lower gear genuinely making more wheel
      force, so the box walks down the pull and stops. A loaded 18-tonne
      run at 62 set: a 2 percent climb held 55.7 and never recovered,
      now holds 61; a 4 percent climb bottomed at 33.5, now 43.
- [x] **A climb cruise cannot hold now says so (2026-07-25).** Once the
      pedal is genuinely on the floor and the truck is still more than the
      droop band under its number, cruise says it is flat out and names the
      speed it is holding. Once a hill (a re-arm at half droop plus a two
      minute floor), and terse speech keeps it -- the engine note and the
      downshifts already say the truck is working.
- [x] **Climb cue no longer fires when cruise is winning (dev guards
      ported 2026-07-27, same day as the flag).** `_say_cruise_out_of_truck`
      now carries dev's three guards (f23a97ec): a `CRUISE_GRADE_BEATEN_PCT`
      floor so it never fires on road the G key calls level, a mid-shift
      hold (an open driveline is no evidence either way -- the debounce
      pauses rather than resets, so a shift-heavy climb still gets its cue),
      and a `CRUISE_GRADE_BEATEN_S` debounce so one frame is never enough.
      Cooldown and terse suppression unchanged. Pinned by
      `test_climb_cue_stays_quiet_when_cruise_is_winning` (target jumped
      well above speed on near-level road: silence while accelerating);
      the original repro (`tools/playtest_road.py --find limit-drop
      --cruise 80 --verbosity 2 --headless 6`) runs clean.
- [x] **Predictive cruise (2026-07-25).** Cruise reads `Trip.grade_at` a
      mile and a half ahead -- the baked grade segments resolve to a median
      half a mile, so this is a real road profile, not a smoothed guess --
      and plans against it the way Volvo I-See and Detroit Intelligent
      Powertrain Management do. Banks up to 3 mph before a pull, holds
      rather than reaches in the last 0.4 mile before a crest, and shaves
      up to 2 mph before a downgrade it would only brake away. Read through
      a 0.3-mile window rather than a preview average: averaging buried a
      half-mile 4 percent hill at 1.3 percent and skipped exactly the hills
      banked momentum helps most. Bench, 18 t at 62 set: a 1-mile 4 percent
      pull crests 45.5 instead of 44.3 and takes 4 s less; a half-mile
      6 percent pull averages 49.0 instead of 48.2. Clamped against the
      posted cap, so momentum is never a licence to speed. Setting is
      `predictive_cruise`, on by default, preset-independent like the speed
      keeper.
- [ ] **Eco-coast / neutral roll.** Real AMTs drop the driveline on a
      gentle downgrade (Detroit eCoast, Volvo I-Roll) and let the truck
      roll. Deferred from the 2026-07-25 pass: the fuel model here is pure
      wheel power, so the saving would be real but small, and it lands in
      the engine-audio path that nromey's arc owns. Worth doing when that
      area is next open.
- [ ] **Driver-selectable following gap.** Real ACC offers three gaps
      (roughly 2.5, 3.0, 3.5 seconds). Freight Fate derives the gap from
      weather only. A setting would suit the players who want a longer
      cushion without pretending it is raining.
- [ ] **I-5 speed limit changes for a few miles (owner observation,
      night of 2026-07-22, verify only).** A short stretch of I-5 spoke
      a different limit. Probably CORRECT -- the dense maxspeed sweep
      baked real posted limits and short zones are exactly what it
      added -- but confirm against the owner's session log which
      stretch it was and check the baked segment against the real
      posted limit there. Verify through a Trip readout, never the raw
      data files.
- [x] **Speeding fine with cruise engaged (Josh report, 2026-07-22) --
      FIXED 2026-07-25; the owner's grade guess was exactly right.**
      Cruise could only cut fuel, and it only ever touched the service
      brake while a lead or a lower posted limit was already pulling the
      target down -- so on a plain downgrade nothing held the truck at
      all. On the bench at 62 set, a 2 percent grade settled nine mph
      over and a 6 percent grade accelerated past 100 with no ceiling;
      on top of the +5 posted offset that is well past the 9 mph strike
      leeway, which is the fine Josh paid. Cruise now stages the
      retarder against the overspeed itself (release, one, two, three,
      on a cooldown so it does not chatter in the player's ears) and
      snubs the service brakes when the jake is not enough. Snubs, not
      the old proportional trim: that settled into a permanent light
      application that drained the tanks 125 psi to 74 in twenty-two
      seconds until the spring brakes set and stopped the truck on a
      downhill. Held speed is now inside about three mph of the set
      speed on grades up to 6 percent, with full air and cool drums.
      Cruise deliberately leaves the retarder alone when it is closing
      on traffic or easing to a lower limit -- the drums do that quietly
      and the jake is loud.
- [x] Add a curated `career_1_9` transcript-backed smoke suite with reusable career-stage presets, structured speech ordering, keyboard reachability, all driving modes, and deterministic event hooks.
- [x] Months-long career arc rebalance: dispatch-assigned fleet tractors by level band (ten new truck models; the roster grew to 35 on 2026-07-25 and dispatch now matches the tractor to the load -- see the slip-seat entry below), a per-level unlock audit so every rank names something concrete, rebalanced XP with re-paced level 21-30 thresholds, 19 new achievements, and a deterministic pacing model (`tools/career_pacing.py`) pinned by tests.
- [x] **Slip-seat dispatch and a 35-tractor roster (2026-07-25).** The
      catalog grew from twelve to thirty-five, spread across day cabs and
      sleepers and light, standard, and heavy driveline specs so there is
      something real for dispatch to choose between. Junior company drivers
      now slip-seat -- what actually happens to a new hire at a big carrier
      -- drawing a tractor per load from a small stable set of yard spares,
      matched to the work: a bunk for anything past 500 miles (eleven hours
      of driving does not cover it), a heavy spec past 20 tons, a day cab
      for a turn inside 250. The pool is deliberately small and stable so
      each spare keeps its own fuel, wear, and damage and the player learns
      which of them pulls; it is also coverage-checked, because the rotation
      alone once left a driver holding nothing but day cabs and sent them
      out on a nine hundred mile run. Levels 1 to 3 stay on the trainer rig
      (onboarding wants one answer), and level 9 ends slip-seating for good
      -- seniority is a truck of your own.
- [x] **Trailer yards and drop-and-hook (2026-07-25).** Trailers are things
      in yards now, not just a type derived from the cargo. High-volume
      facility types stage loaded trailers; a farm elevator or a quarry does
      not, and the middle types are a weighted, facility-stable coin. A
      drop-and-hook pickup is 25 minutes against a live load's 60, and the
      trailer you hook carries its own number and condition -- a rough one
      hands the next roadside inspection a write-up your own walk-around
      would have caught, which is drop-and-hook's real cost. Live loads that
      run past two hours earn detention pay, on the settlement ledger as a
      negative charge (money the other way). Owner-operators pulling their
      own box always live-load, because nobody swaps your trailer for one out
      of the yard. Yards are derived from facility identity and the plan is
      recomputed from the job, so the whole feature persists nothing and
      touches no save schema. Three badges came with it.
- [x] **Drop-and-hook on the delivery end (2026-07-25).** A receiver with a
      drop yard takes the whole trailer: 20 minutes against a live unload's
      45, and it is how a driver sheds a box they have been dragging a defect
      around on. Every dock-worded instruction on the arrival screen now says
      the right thing for the ending it is offering.
- [x] **Pre-trip walk-around (2026-07-25).** Walking the hooked trailer is a
      menu action at the pickup, so the defect is something the driver goes
      and finds rather than something an inspector springs on them at a
      scale -- the accessibility point, since a blind driver had no other way
      to look. Finding one unlocks refusing it: the yard swaps the box for
      `TRAILER_SWAP_MIN`, and the refusal is threaded through the pickup
      snapshot, `start_loaded_drive`, `RouteSelectState`, and the driving
      snapshot so the scale house finds the trailer actually under the truck.
- [x] **Playtest harness reaches the equipment layer (2026-07-25).** The
      harness pressed Enter a fixed number of times at the pickup and arrival
      menus, so every new menu item silently pushed it onto a different
      button; it now selects by label (`select_menu_item`) and handles either
      pickup mode and either delivery ending by name. `PlaytestResult` gained
      the facts a transcript cannot carry -- assigned tractor, the yard spares
      it was drawn from, live load versus drop-and-hook, trailer number,
      condition and defect, detention earned, delivery mode -- and
      `tools/playtest.py` prints them as an equipment block, with
      `--equipment-only` and `--walk-around` for driving the pre-trip.
- [ ] **Harness still cannot reach rest, fuel, the garage, or enforcement.**
      Sleeping, fuelling, repairs, endorsement courses, and roadside
      inspections are all driven by hand in their own tests rather than
      through the harness, so a whole-session playtest cannot cover them.
      Worth a second pass with the same select-by-label approach.
- [ ] **Trailer wear should accumulate, not just be drawn.** A trailer's
      condition is derived from the yard, so nothing the driver does to it
      sticks. Real per-trailer wear wants somewhere to live -- probably the
      same per-truck condition record, keyed by trailer number.
- [ ] Wire Big Buck's content into a playable roadside stop; current 1.9 data and spoken refusal content are shipped, but no honest drive-and-enter gameplay path exists yet.
- [x] **Physics test bench** (`tools/physics_bench.py`): deterministic scripted-driver scenarios over the real truck model -- descents, runaway coasts, stop tests -- printing plain-text, screen-reader-friendly, diffable reports (peak brake temp, fade onset, wear added, the cues the game would have played). The tuning loop for every physics change; `tests/test_physics_bench.py` keeps its orderings honest. Now also a tuning instrument: `--sweep` re-runs a scenario across one knob (speed, cargo, grade, wear) one line per value, and `--solve` bisects for an edge ("the fastest drag speed that stays under fade"), both plain-text and deterministic.
- [x] **Per-truck condition.** Wear, damage, and fuel moved off the profile into `truck_conditions`, keyed by truck, so each owned tractor keeps its own state and swapping trucks no longer teleports condition. Legacy saves migrate (all owned trucks inherit current wear; no pristine spare), per-truck wear is under the save signature, and the field is scoped by truck *model* key -- true per-instance trucks are still the rental feature's job.
- [ ] Truck selling / trade-in at the dealer: no sell path exists today, so `truck_conditions` never needs to drop a record. When selling lands, drop the sold truck's condition record (and decide salvage value from its wear).
- [ ] Transmission as a per-truck purchase spec (rides the dealer/sell path above): a gearbox is bought with the truck, never swapped in later. Carrier-spec company tractors run automatics like real fleets; owner-operators choose at the dealer, and the cheap old rigs of the lease-to-start onramp skew manual -- cheap entry costs shifting skill. Gear count (10/13/18-speed) can join as a spec later. The global Transmission setting survives as the player's accessibility override, and dispatch respects it.
- [ ] **ATS-style in-city facility fronts (community ask via Josh, 2026-07-21).** A player asked for "city services like in American Truck Simulator" -- the drivable in-city facility buildings: truck dealer, service shop, purchasable home garage, recruitment agency, truck wash. Nearly all of it maps onto features already planned here (dealer/sell path and transmission spec above; player truck marketplace; multi-truck logistics with a per-truck home city; the AI driver fleet IS the recruitment agency; truck-stop repair bays shipped). Recommended shape, relayed to the owner for Josh: do NOT hard-gate the district to owner-operators -- facilities answer honestly by role instead. A company driver browses the dealer (window-shopping is the aspiration loop, and the lease-to-start onramp is the dealer's answer to a broke driver), repairs stay carrier-billed at terminals, and only the recruitment agency waits naturally on owner-operator status plus a second truck. Physical access rides the facility-approach machinery: each facility is an endpoint on a baked surface-street chain, the same way docks and errand destinations connect today -- also the answer to "how do we connect parking to the surface streets": mint the spot as an endpoint in the same bake. Note the naming collision: Freight Fate's existing "city services" are the in-town errand drives, a different feature.
- [x] **Jake brake realism.** The jake is now retarding torque through the gearing -- three stages, scaling with RPM and gear ratio -- so gear discipline decides descents: stage 3 in 7th holds a loaded rig on a 6 percent grade with zero service brake, stage 1 makes the shoes work, and overdrive gives almost nothing. Automatics pre-select down into the retard band with the jake on and upshift past the RPM ceiling to protect the engine (the realistic runaway spiral). Bench-solved anchors: jake-only holds up to ~26 tonnes of payload on the 6 percent; past that you snub or run away. The on/off key still works; a staged in-cab control is open follow-up below.
- [x] **Brake thermal realism.** Drum heat is now real energy accounting: dissipated brake power soaks a drum thermal mass, cooling is convective (square root of speed -- outrunning your brakes no longer air-conditions them), and faded shoes grip less so they also heat less. The six-mile 6 percent drag now peaks at 466 C with miles ridden past fade, while jake-and-snub finishes cool -- the drag-vs-snub lesson finally has teeth. Overspeed realism came with it: the road can drive the engine past the governor (that wears it; governed running is safe), and brake wear is now charged per megajoule actually dissipated in the shoes.
- [x] Staged jake in-cab control (landed 2026-07-21, owner control scheme): J is the dash enable switch and re-engages at the last-selected stage; 1/2/3 select two/four/six cylinders while the jake is on (spoken), and do nothing while it is off so the number keys stay free for other contexts. Controller: modifier + jake button cycles stages. Automatic descent control still manages the full jake itself.
- [x] **Traction deep-dive: freezing rain, hydroplaning, jake grip cap.** `WeatherKind.ICE` (grip 0.15, a third of snow) forms physically -- rain sampled in the 1 to -4 C band glazes, and the live NWS feed maps freezing rain/sleet/ice to it instead of snow -- with its own hazards, spoken "ice on the road" status, and a bench `stop-ice` anchor (880 ft from 40 mph vs 329 dry from 60). Hydroplaning follows the Horne relation: onset ~106 mph on fresh tread (trucks at highway pressure basically never plane), pulled down by tread wear and standing-water depth (`WeatherEffects.water_mm` -> `truck.water_mm`) -- 80 percent worn rubber planes at ~59 in heavy rain, grip collapsing toward a 0.3 floor over a 12 mph band, with a spoken onset warning and hydro-aware conditions incidents. The jake is now capped by drive-axle grip (42.5 percent of gross, half usable before lockup): dry never binds, glare ice breaks stage 3 loose in a low gear while stage 1 stays hooked up, `jake_slipping` speaks a warning, and the bench `grade-jake-ice` run shows the capped jake losing ground on a 4 percent it would hold dry.
- [ ] Jake-slip and hydroplane consequences beyond the warning: sustained sliding should be able to escalate into a real incident (trolley jackknife / spin) through the event system, which needs a "release the jake / ease off" resolution verb rather than the brake-to-answer hazard contract.
- [ ] **Curve management as a difficulty tier (owner idea 2026-07-15;
      sound grammar designed 2026-07-16).** The data half is DONE: 63,725
      discrete curve records (at-mile, direction, radius, physics
      advisory speed) are baked and shipped under world_data/us/gameplay.
      The feature: at the manage-curves difficulty tier speak the
      approach ("sharp right, quarter mile, advisory 25" -- plain
      language pacenotes from the real records, warned in REAL reaction
      seconds like ramp endings), guide the bend, require the slowdown,
      and let hot entries pay physics consequences (drift off-lane, load
      and ice against the lateral-traction bullet above). SOUND GRAMMAR
      (owner + Fable design session 2026-07-16, Forza Motorsport's Blind
      Driving Assists as validated prior art): silence-is-centered on
      straights -- the lane speaks only when you drift (fatigue beats
      information density over a ten-hour haul); when the road bends,
      the PURSUIT guide takes over -- pan the existing road/engine bed
      along the arc (Forza's steering guide panned engine+tires toward
      the needed steer; pursuit tracking beats error-nulling in the
      human-factors literature -- the owner independently reinvented it
      from bed); drift cues stay underneath as the error backstop; lane
      EDGES get per-side textures (rumble strip inside vs gravel
      shoulder outside) so single-sided hearing still knows which way it
      wandered; and every cue gets a preview-in-Settings audition, Forza
      style -- a natural driving-school lesson. Steering input, presets
      (Josh's DRIVING_ASSIST_FIELDS entry, keyboard first-class, analog
      pad.steering as the smoother option), and the exact guide sound
      NARROWING: Josh passed on the audio-design lead (2026-07-16), the
      owner posted the open questions to the audiogames.net forum
      (posted 2026-07-17 in the Freight Fate thread, replies same day),
      and the community RESOLVED two of them our way: NO steering
      tones (JaceK: continuous tones overwhelm the soundscape and hurt
      players with sensory/hearing issues; rumble strips and real-world
      edge sounds instead -- exactly the silence-is-centered +
      per-side-textures design, owner concurs and had already resolved
      on rumble strips), and the guide stays the panned existing bed,
      never a new tone. JaceK also ruled: BRAKE BEFORE THE BEND, never
      in it (locked wheels lose steering) -- pacenotes must front-load
      the slow-down call, and mid-curve braking should cost grip in the
      physics. Still open: steering-input feel (his "thinking ahead,
      not jerking the wheel" leans hold-to-sweep).
      PACENOTE LAYER SHIPPED (2026-07-18): data/curves.py reads the
      shard (143 ms once, cached), Trip carries route-mapped
      direction-mirrored curves, and DrivingPacenoteMixin speaks the
      calls -- severity from the baked advisory (hairpin <=25 / sharp
      <=35 / curve <=50 / gentle bend), front-loaded lead (5 s reaction
      + comfortable-braking distance, floor a third of a mile), silent
      when already slow enough, linked "then right" tails, U lists the
      next bends, D folds the bend into its number, Settings toggle
      outside presets. PURSUIT GUIDE + EDGE LADDER SHIPPED (2026-07-27,
      Track B): the road bed pans along the arc toward the needed steer
      (community ruling honored -- the existing bed, never a new tone;
      silence-is-centered with drift/curve wake-sleep hysteresis), and
      the lane edges answer with structural textures synthesized from
      the edge_nav audition machinery -- intermittent clip / periodic
      strip / aperiodic gravel, panned to the side, with boundary truth
      from the baked lane data (no gravel past an undivided centerline;
      the spoken warning names the oncoming lane; graded haptics
      unchanged). Turn signals now speak as panned tones (owner call
      2026-07-27); the relay click stays for a future vintage-equipment
      option. Remaining slices: the required-slowdown consequence tier
      (hot entries pay physics), steering-input feel, cue previews.
- [x] **Real lane counts from OSM (owner ask 2026-07-16) -- DATA LAYER
      BAKED 2026-07-23.** `corridor.lane_segments` now carries real OSM
      lane counts (`lanes`, `lanes:forward`/`backward`, `oneway`) for every
      leg OSM tags, matched to the archived route geometry against the
      self-hosted Overpass -- the exact way-matching pattern of the dense
      maxspeed sweep (`tools/bake_lane_segments.py`, reusing the Job 2
      matcher). Honest absence where OSM has no tag (no guessed defaults);
      the runtime can default by road class later. All 1,287 legs swept,
      20,666 segments, 96.3% of route-miles covered (per-state 92-99%,
      reported in `logs/oatis-lane-bake-done.json`); acceptance verified --
      I-40 widens to 3+ lanes through Albuquerque and holds 2 rural.
      Guarded by `tests/test_lane_data.py`. No mechanic reads it yet: the
      wiring job below carries the player-facing changelog.
- [x] **Lane counts spoken (Track D multilane slice) -- SHIPPED
      2026-07-27.** The baked `corridor.lane_segments` now reach the player
      as speech: the road-status readout and the route briefing say the
      lanes in the travel direction ("divided, three lanes your side"),
      and a callout fires when the count changes mid-leg ("road widens to
      three lanes", "down to two lanes your side"). Direction-aware (your
      side flips with travel direction), verbosity-aware (change callouts
      hush in terse; status readout keeps them), and honest-absence (legs
      with no baked lane data say nothing). Runs shorter than two miles
      collapse so a passing-lane blip is not announced. Speech only -- no
      traffic, no lane-position mechanic. `tests/test_multilane_speech.py`.
- [x] **Divided-highway flag baked (Track D2, for curve nav) -- SHIPPED
      2026-07-27.** Each leg carries `divided: true/false` from real OSM
      carriageway geometry (`tools/bake_divided.py`, PBF cache, oneway
      pairing), so curve nav's LEFT edge can sound like a median on a
      divided highway vs the centerline with oncoming traffic on an
      undivided one -- instead of inferring it from road class. 1005
      divided, 196 undivided, 86 genuinely-mixed legs omitted (honest
      absence, inference stays the fallback). Data only; curve nav reads
      it. `tests/test_divided_data.py`.
- [ ] **Lane data as a mechanic (Track B / 2.0, follows the speech
      above).** REAL LANE DROPS as genuine merge events tied to lateral
      position, real widths enforced, exit-lane guidance, and keep-right
      pressure that knows how many lanes exist. Reads the same
      `corridor.lane_segments`; advisory guidance may run on partial data,
      punitive consequences only where lane data is real (see
      `docs/lanes-harvest-brief.md`). Lateral position belongs to the
      curve-navigation track.
- [ ] **Assistance-mode assessment: accessibility features that drive the
      truck right (Josh's ask to the owner, 2026-07-22).** The automatic
      driving aids -- adaptive cruise, the speed keeper, curve speed
      assist, route-transition assist, descent control, automatic
      emergency braking, lane keeping -- are ACCESSIBILITY features, not
      truck-spec upgrades: they exist for players who need them and stay
      available on every truck regardless of the era/spec ladder (the
      same override rule as the transmission setting). Their duty is to
      operate the real truck the way a skilled driver would: engine
      brake before service brakes, traction-linked, honest air and wear
      costs, audible through the proper voices (jake growl versus brake
      clunk) so a blind driver can hear WHICH system is acting. Curve
      speed assist got jake-first on 2026-07-22; the keeper, transition
      assist, descent-control interactive mode, and AEB still go
      straight to the pedal. Owner to assess each mode in play and call
      the fixes; auto jake and the traction-linked retarder gate are the
      building blocks.
- [ ] **Hand throttle, parked high-idle, and equipment by model era
      (owner idea 2026-07-22, sparked by the 896 take's rev-and-hold).**
      Two features on the per-truck-spec pattern. (1) PARKED HIGH-IDLE
      -- SHIPPED 2026-07-22 (sound/engine-integration): K latches it
      while the parking brake holds (controller: Y), plus/minus step
      the setpoint 800-1500, air genuinely builds faster, parked
      revving burns real fuel, and releasing the brake cancels it like
      a real ECM. (2) EQUIPMENT BY ERA:
      cruise control only exists on electronic engines (~1990-on), so a
      genuinely vintage mechanical rig -- marketplace/classic material,
      the 896 Mack's era -- gets NO cruise, a HAND THROTTLE that also
      holds rolling (throttle, not speed: rpm sags audibly on grades),
      manual box only, and NO ABS (pre-1997), which couples straight
      into the traction physics. Lease-fleet "old" trucks (2000s-2010s)
      keep cruise and ABS but not adaptive extras. Same accessibility
      rule as the gearbox spec: realism default per truck, Settings
      override stays. On-road hand throttle must cancel instantly on
      brake, like cruise. AUTO JAKE SHIPPED 2026-07-22 for automatic
      boxes (J = auto retarder management, Volvo off/auto/1/2/3 stalk;
      Alt+J for hand-stagers, Alt+T flips shift modes on the road) --
      when the era ladder lands, vintage rigs simply lack the auto
      position. Follow-up worth doing: true AMT manual-hold mode (pin a
      gear without the clutch, like a real AMT's arrows) -- pairs with
      driving-school descent lessons.
- [ ] **A turn signal you actually operate (owner idea 2026-07-16).**
      Today lane-change taps click the signal for you; give the player
      the stalk: signal before a lane change, and unsignaled changes
      become a discipline the CB and troopers can notice at the
      higher-realism tiers. Pairs with a LANE-LINE CROSSING sound --
      a soft paint-and-dots tick when crossing a dashed line, the
      clearly-quieter kin of the edge rumble strip, so every lane change
      has a physical moment (owner idea, same night).
- [ ] **Signal-and-steer turns on surface streets (owner idea
      2026-07-15).** Turn-by-turn today is automatic: the truck follows
      the baked chain, the player hears the cue and panned chime and only
      manages speed and stops. At the higher-realism tier a turn should
      be driven: signal (indicator stalk sound already shipped), brake to
      turn speed, steer through with the same guidance-tone grammar as
      curves, with missed or unsignaled turns costing a reroute or
      strike. Natural interaction layer for per-turn trailer
      off-tracking.
- [x] **Map sharding: split the two 60 MB JSON files before GitHub's
      100 MB wall (Josh's ask, 2026-07-18; SHIPPED 2026-07-19).** Both
      trees are now per-state shards keyed on the state a leg starts in:
      the source moved from world.json to world_source/ (meta.json,
      cities.json, legs/TX.json ...) and world_data/us/legs.json became
      world_data/us/legs/. Largest shard is Texas at 5.4 MB, down from
      60 MB. tools/world_source.py hands every build tool the same merged
      dict it always got (load_world / save_world), so ~25 tools migrated
      mechanically and none changed behavior; save_world rewrites only
      the shards that actually changed, so a one-leg edit is a one-file
      diff. index_world.py emits the runtime shards and its --check now
      also catches a stale shard left behind after its last leg moved
      states. No git-lfs (breaks plain clones, costs Josh quotas), no
      history rewrite (Josh's call, someday) -- the 341 MB pack stays.
- [x] **Truck-accessibility sweep: vehicle_access classification
      (Josh's spec via Codex, owner + Phil concur, 2026-07-18).** Full
      brief: docs/truck-access-sweep-brief.md. Three tiers on every
      stop, separate from parking: tractor_trailer (announced, usable),
      bobtail_only (on the map, hidden from semi announcements and HOS
      planning; usable in 1.9 while GENUINELY bobtailing -- an empty
      trailer is not a bobtail), none (landmark only). Never filter by
      brand (some Exxons and the Wawa Travel Center are truck-oriented;
      1,082 generic fuel_station records need real classification, not
      a brand purge); generic fuel stations default bobtail_only unless
      truck access is verified via OSM/Overpass. Route gaps left by the
      sweep get filled with REAL truck stops, plazas, and rest areas --
      never disguised gas stations. The parking buff may affect
      fullness at legal stops, never admit semis to impossible lots.
      Policy bans (Big Buck's GOLDEN ANTLER waiver) stay a separate
      future flag; the pass never overrides physics. OATIS runs the
      sweep in his own window AFTER sharding lands; the
      announcement/HOS filter is game-side. SHIPPED 2026-07-19: rails
      game-side (b91d476, every stop defaults tractor_trailer), sweep
      merged from map/truck-access-sweep -- all 3,745 stops classified
      (2,720 tractor_trailer / 1,021 bobtail_only / 4 owner-adjudicated
      none), 527 real gap-fill facilities on 248 legs, 100-mile-plus
      service gaps roughly halved (sleep 271 -> 136). Follow-ups live
      as their own bullets below (locators, warn-at-dispatch, sampling
      density, classify-at-creation); 81 legs remain UNVERIFIED where
      OSM is likely under-tagged rather than the corridor truly empty.
- [ ] **Terrain audit: relief-aware reclassification (player-found by
      Josh, 2026-07-19).** The grade-segment classifier calls any
      segment over 3% "mountain" with no relief context, so East Texas
      creek dips read "terrain mountain" and can roll mountain-only
      hazards (runaway truck) outside Lufkin; meanwhile 186 legs with
      mountain-scale relief are labeled flat at leg level (the
      Grapevine!). Physics is untouched (it reads numeric grades).
      Full brief with rules, ground-truth checks (all 96 runaway ramps
      must sit on mountain segments), and the handshake:
      docs/terrain-audit-brief.md. Oatis's next map job after the
      access sweep merges.
- [x] **Name the villages a leg passes through (landed 2026-07-20).**
      Swept and spoken: "Entering Strawberry" arrives just before the
      35 it explains, on every leg that has such a town. Governed by
      the Place callouts ladder (see the map workstream section for
      the bake details and the ladder design).
- [ ] **Guard the real world source during tests.** save_world()
      defaults to the checked-in source, so a stray call from a test or
      ad-hoc script silently rewrites the map (same class as the
      FREIGHT_FATE_DATA_DIR rule for saves). Add a loud failure when
      tests write the real source without explicitly opting in.
- [ ] **Toll sweep: every leg, real published rates, and a transponder to
      buy (owner, 2026-07-19).** The map prices 46 toll events across 16
      authorities -- broad coverage of the tolled interstates, since those
      are the only toll roads the router uses (I-4, I-35, I-10, I-25 and
      friends are free; SH-130, Florida's Turnpike and E-470 are
      alternatives we never route onto). Two gaps, both real:
      every amount is `estimated: true` -- plausible, never sourced to a
      published tariff -- and some tolled legs carry nothing at all
      (New Hampshire's I-95 Hampton plaza, and the Portsmouth->Portland leg
      that crosses the Maine Turnpike's York barrier we toll elsewhere).
      `tools/toll_scan.py` finds the rest by evidence: it walks each leg's
      geometry and asks OpenStreetMap what carries `toll=yes`, classifying
      a sighting as ON-ROUTE only when the tolled way's own `ref` names the
      leg's highway. Proximity is not use -- I-30 runs within two miles of
      the George Bush Turnpike and a truck on I-30 pays neither, so a
      parallel tollway is reported for review and never billed.
      Then price the confirmed set against each authority's published
      5-axle commercial tariff, storing BOTH the transponder and the
      pay-by-plate amount per event.
      **The transponder mechanic that pays for:** company drivers get one
      from the carrier (the toll model already assumes settlement
      accounting, so nothing changes for them); an owner-operator buys a
      generic "toll transponder" ONCE, or pays plate rates at every gantry
      until they do. A single device rather than E-ZPass plus K-TAG plus
      PikePass plus SunPass: real national drivers carry several, but
      modelling five networks is buying the same decision five times --
      tedium, not depth. The trade-off survives the compression, since
      skipping it still costs real money every mile of turnpike.
      Note for the pricing pass: `$0.00` events are NOT bugs. They are the
      documented ticket-system entry markers (see `docs/route-stop-data.md`)
      that settle at the exit gantry.
      **State 2026-07-21: groundwork landed, data NOT yet baked.** The old
      46 estimated events are gone; the world currently carries ZERO toll
      events, only per-leg `tollway_detected` scan flags. `tools/toll_scan.py`
      (evidence scanner), `tools/toll_rates.py` (the researched 5-axle
      tariff table), and `tools/toll_review_sheet.py` all shipped in
      fcd846a; the remaining work is reviewing the sheet and running the
      bake. Until then the game bills no tolls at all -- upstream's
      "prices seem off" report (Josh, 2026-07-21) is right on both lines.
- [ ] **Interactive toll plazas: stop, window down, pay cash (Josh ask,
      owner approved, 2026-07-21).** Real toll points split two ways and
      the bake should record which is which per event: all-electronic
      gantries have nothing to stop at -- no transponder there means
      pay-by-plate at the higher stored rate, spoken honestly as you pass
      -- while conventional plazas with cash lanes get the mechanic: an
      approach call ("Toll plaza ahead, cash lanes right"), X to take the
      cash lane (the same verb as exits and pull-overs), then the ramp
      stop-bar machinery runs the booth -- rolling countdown, the
      parking-sensor tick to the window, stop, window down, the spoken
      amount, pay, barrier, go. Costs real clock time versus the
      transponder lane. Rides the stoppable-stop spine with chain-up
      areas and Big Buck's; per-operator cash acceptance is researchable
      in the same pass that bakes the tariffs. Josh's in-progress traffic
      and API work could someday feed cash-lane queue lengths as an
      optional live layer (determinism boundary applies).
- [ ] **More first-party truck-stop locators, and public parking feeds
      (owner approved, 2026-07-19).** `curate_route_pois.py` queries only
      Love's and Pilot/Flying J today (730 + 877 locations). Pointed at the
      21 legs with no truck-accessible stop, those two closed exactly one
      (Pilot Dealer Perris, I-15 mile 88) -- useful, and evidence the
      corridors really are thin rather than merely untagged. Add the chains
      we never ask: **TA/Petro** (the big omission), Sapp Bros, Bosselman,
      Road Ranger, Maverik, plus the **AmBest** and **NATSO** member
      directories, which is where the rural independents live. Same code
      path, same `Candidate` shape, same citable source notes.
      **TA/Petro specifically is LOW PRIORITY, and here is why so nobody
      re-derives it:** Love's + Pilot gave 1,607 real first-party locations
      and produced exactly ONE hit across the 20 legs. TA is ~360 locations
      with the same Interstate-heavy profile, so expected yield is ~0-1. The
      structural reason is that national chains build where freight density
      is -- on Interstates -- and every remaining gap leg is a US or state
      route. No chain locator can close them, by definition. Checked
      2026-07-19: TA's sitemap lists 361 location pages and robots.txt
      permits crawling them, but the JSON-LD is EMPTY (lat/lon/address
      render client-side) and the official API needs a partner token, so it
      costs a JS renderer or a business relationship for near-zero return.
      Also investigate **Park My Truck** (NATSO/ATRI) for a DOCUMENTED public
      feed -- real-time space counts, publicly funded origins.
      DO NOT scrape Trucker Path, AllStays, or similar apps: the data is
      their product, their terms forbid it, it is not licensed for
      redistribution, and user-reported availability cannot go in a
      deterministic offline game that must answer every player identically
      forever.
- [ ] **"Where am I": an on-demand orientation key (owner, 2026-07-19).**
      A sighted driver answers this with a glance at a sign. A blind driver
      cannot, and no amount of automatic chatter answers it at the moment
      somebody actually wonders. It joins the existing on-demand family (S
      speed, D details, U upcoming, X exit), so the pattern is already
      familiar. Speaks what the map already knows and currently keeps to
      itself: nearest town and its distance and direction ("Pine, one mile
      ahead; Strawberry, four back"), the road and state, the nearest baked
      landmark, the next route city.
      **Nearest truck service belongs here too, and MUST honour
      `vehicle_access`** -- naming a bobtail-only stop as "nearest service"
      to a driver pulling a trailer is exactly the false promise the
      truck-access sweep just removed from announcements.
      This also reframes the village sweep: the bake becomes the DATA LAYER
      this key reads, and the automatic half stops being a separate callout
      at all. The town name RIDES the limit announcement the game already
      makes -- "Entering Strawberry. Speed limit drops to 35." -- so it adds
      no new event, only the context that stops the drop reading as
      arbitrary. That is why it belongs ON by default (owner's call, and the
      right one): defaulting it off would suppress the explanation for
      something the game announces regardless. The toggle stays for anyone
      who wants the bare limit call.
      Push and pull answer different questions and neither substitutes for
      the other: the ride-along answers "why is this happening", the key
      answers "where am I on I-40 at three in the morning", which never
      arrives on a schedule.
      **Bake WIDE, display TIGHT.** The 0.5 mi rule is what makes "entering"
      true, but the key's honest answer is whatever is nearest at whatever
      distance -- on I-40 that may be "Winslow, eleven miles ahead", and
      refusing to say it would make the key useless exactly where it is
      wanted. So collect a 10-15 mi catchment, store each place's offset and
      whether it is on-route, and let the tight radius govern the callout
      only. Two or three places at most, along-the-road direction rather
      than compass.
      **Low priority and interruptible (owner, safety).** Speak it with
      `interrupt=False` so it never purges anything; the existing safety
      path then preempts it for free, since an interrupting line already
      purges the channel. Keep it short -- a long recital holds the channel
      long enough that even correct preemption feels laggy.
      **Big Buck's stays hidden.** A readout that gives its distance hands
      away the discovery. Let the key speak it only after the player has
      found one, or surface it as CB rumour -- the button reports what the
      driver would plausibly KNOW, not what the database contains. That
      rule keeps it an orientation aid rather than an oracle.
- [ ] **Warn the driver before an under-served route, instead of faking a
      stop on it (owner, 2026-07-19).** After the access sweep, 21 legs over
      100 miles carry no stop a combination vehicle can enter. Designating an
      invented truck stop would falsify real geography -- a 158-mile US-2
      Hi-Line stretch with nowhere to pull in is TRUE, and US-50 across Nevada
      is meant to be empty. So surface the constraint rather than paper over
      it: at dispatch and route selection, warn when (a) the calculated fuel
      range will not clear the route's longest stretch with no truck-accessible
      fuel, or (b) HOS says a sleep falls due inside a stretch with no
      truck-accessible sleep stop. Turns a data gap into the planning tension
      the game is about -- and it is honest where an invented stop is not.
      The gap maths already exists in tools/truck_access_gap_report.py
      (longest serviceless stretch per leg per capability) and wants moving
      into the sim beside the HOS planner. Note the evidence limit: on I-15
      San Diego-Riverside and I-69 Bloomington-Evansville a dense 5-mile probe
      found 53 and 19 named stations with ZERO truck tags of any kind, so
      "no verified stop" cannot be read as "no stop exists" -- another reason
      to warn rather than assert.
- [ ] **Densify corridor POI sampling in the mapping utility (found
      during the access sweep, 2026-07-19).** `_overpass_named_candidates`
      queries a fixed 7 boxes per leg -- five mid-corridor samples plus the
      two endpoint cities -- each about 7.5 miles of road. That is ~52 miles
      inspected regardless of leg length: a third of a 162-mile leg, a
      seventh of a 345-mile one, so coverage is thinnest exactly where a
      serviceless stretch strands somebody. The five mid-points are indices
      into `route_points`, not evenly spaced miles, so they cluster wherever
      geometry vertices fall; the Love's at Williams and the truck stops at
      Corning sit in the blind spots on I-5, both `hgv=yes` in the extract we
      already query. Generic car fuel (the `rural_fallback` relaxation) hid
      this by making thin corridors look served until the access sweep
      demoted them. Fix belongs in the enrichment tool: sample by mileage and
      scale the probe count to leg length.
      `tools/fill_truck_access_gaps.py` densifies only INSIDE qualifying
      gaps, so corridors that are merely thin are still under-sampled and a
      map-wide re-sweep is still owed.
- [ ] **Emit `vehicle_access` when the mapping utility creates a stop
      (owner, 2026-07-19).** Every POI-adding path should classify at
      creation instead of waiting for a re-sweep, or each map expansion
      reintroduces unclassified stops. When judging an unfamiliar operator,
      read the OSM `website` tag -- it often carries the operator's own
      location page, which settles format and amenities better than a brand
      name (it identified Love's #120 as a Vian country store). That matters
      most for Hawaii, Alaska, and Canada, where the chains are unfamiliar.
- [ ] **Real construction zones from state 511 APIs.** When real-time
      traffic is enabled, construction zones should be generated from actual
      state DOT work zone data instead of simulated zones. Requires:
      parsing construction events from 511 APIs, mapping real construction
      locations to route mile markers, converting real data into Zone objects
      with appropriate speed limits, and fallback to simulated zones when
      real data is unavailable. The current implementation only announces
      construction as traffic alerts; this would make the zones themselves
      match real-world work zones.
- [x] **No-key realism enhancements -- SHIPPED 2026-07-16.** Four foundational
      realism systems added without API keys: enhanced truck stop amenities
      (CAT scales, laundry, game rooms, barber shops, premium wifi, check
      cashing, DEF lanes, ATM services), truck stop loyalty programs (points
      per gallon, shower credits, reward redemption), real-time traffic data
      via state 511 APIs (Ohio OHGO as reference), and truck parking
      availability via TPIMS APIs (Ohio OHGO as reference). All three
      real-data systems are optional settings with graceful fallback to
      simulated data. Amenities are data-only; loyalty is fully playable;
      traffic and parking are integrated as announcements and availability
      checks. (2026-07-22: the incident-alert path had never actually run --
      it crashed on a missing Trip helper and queried a hardcoded Ohio
      point; fixed on the 1.9 line to use the truck's real state and
      position, checked once per mile.)
- [ ] **Route terrain browser (owner idea 2026-07-15).** A reviewable,
      navigable summary of what the route will demand: big climbs and
      descents with grade and length, sharp-curve clusters, chain-law
      areas, by milepost -- readable at dispatch and route selection,
      from the pause menu, and on demand while driving alongside the U
      upcoming key. Feeds off corridor.grade_segments and the future
      curve records; kin to the map-stats explorer idea.
- [x] **On-demand safe-speed key -- SHIPPED 2026-07-15.** D (next to S's
      posted limit, a deliberate spatial pair) speaks one number: the
      minimum of the posted limit, the weather-grip safe speed, and the
      ramp speed once an exit is armed within two miles or the truck is on
      the ramp. Weather and context are baked into the math, never the
      sentence ("Safe speed 45 miles per hour for the ramp."), repeatable
      free. Curve advisories join the same key when the Job 2 curve
      records land (the curve-tier bullet above).
- [x] **Speech history review -- SHIPPED 2026-07-15.** Comma now walks
      back through a ring of the last 20 spoken lines across both
      channels: first press repeats the newest (unchanged), further
      presses within ten seconds each step one line older, spoken with a
      "2 back:" position prefix, clamped at the oldest -- the
      speech-history pattern NVDA users already know. A fresh
      announcement (or a pause past the window) resets the walk to
      newest; consecutive duplicate lines collapse to one entry. A keeps
      its route-announcement meaning unchanged. The event pacer also
      logs a `[pacer]` transcript marker whenever it flushes a stale
      backlog, so playtest logs show the flushes.
- [x] **Stale event-speech backlog -- FIXED 2026-07-15.** The event voice
      queued utterances faster than it spoke them, so arriving at the yard
      played the whole approach script late ("slow down to dock, at dock,
      delivering" after the load was dropped) and the backlog talked over
      light dings. `EventSpeechPacer` (speech.py) now projects when the
      channel falls silent from utterance length and a conservative
      speaking rate; a queued line that would start more than three
      seconds after the moment it described flushes the dead backlog and
      speaks immediately, and interrupting lines reset the projection to
      truth. Follow-up if the estimate ever misbehaves: scale the
      chars-per-second to the configured event voice rate.
- [x] **Dispatch lane variety -- SHIPPED 2026-07-15.** The profile
      remembers the last six delivered from:to lanes
      (`Profile.recent_lanes`, saved), and the assignment queue
      stable-partitions fresh candidates so an unseen lane goes first --
      score order still rules within each group, an all-recent board
      changes nothing, so the nudge delays a repeat but never blocks
      dispatch. Higher levels widening the distance cap stacks on top.
- [ ] **Billboards on short routes (playtest 2026-07-15).** Nothing was
      deleted -- the pools, corridor signs, and wiring are all intact -- but
      the spacing math (15-mile lead-in plus a 35-to-65-mile gap roll)
      means a run under about 30 miles usually rolls zero billboards, which
      reads as "the billboards are gone" on short-lane days. Scale the
      lead-in and gap down on short routes so even an errand run can pass
      one sign.
- [ ] **Brake-heat sensory ladder (owner ask 2026-07-15).** The physics
      already tracks brake temperature continuously (heating, cooling,
      fade onset, effectiveness collapse) but the player only hears three
      coarse buckets buried in the detailed status readout, plus a squeal
      that fires once it is already too late. Real trucks have no brake
      temperature gauge -- drivers judge by smell, pedal feel, and smoke
      -- so the honest interface is a five-rung spoken sensory ladder
      (cool, warm, hot, fading, smoking) with each transition announced
      once as the sensation ("You smell hot brakes", "The pedal is going
      soft"), a one-word trend on the hot rungs (still heating vs
      cooling -- the whole question on a long descent), and the heat word
      added to the quick status key, not just the long readout. Prime
      driving-school lesson: a long practice grade, snub braking versus
      dragging, when to grab a lower gear, what each rung means -- pairs
      with the latching-controls lesson (latch the brake, hear the
      ladder climb).
- [ ] **Ambience honesty: season, temperature, and region gate the
      wildlife (owner playtest 2026-07-16).** The night ambience sang
      cicadas over a 52-degree March windstorm in Holbrook -- wrong
      season (cicadas are a summer chorus), wrong temperature (they go
      quiet below about 60 degrees), wrong feel for a high-plateau
      desert night (wind, a distant coyote, honest silence). Ambience
      beds should key on the same season/temperature/region state the
      weather system already tracks: insect layers gated by season AND
      warmth, regional voices where they belong (cicadas in a Georgia
      summer, absolutely; Holbrook in March, never). And the gate swings
      both ways (owner, same night): a per-season palette, not just
      evictions -- spring peepers near Midwest water at dusk, the full
      summer chorus in the South, fall geese overhead, and winter's
      snow-muffled hush. A rest stop should sound like a date on a
      calendar somewhere real. Audit the existing loops against this
      rule; the owner's NAS library sources both the evictions'
      replacements and the new seasonal beds.
- [ ] **Cab and rig sonification pass (owner 2026-07-15).** The state the
      truck is in should be hearable before it is spoken. First candidates:
      a chain-clatter loop whenever chains are mounted, pitched and paced
      with speed -- on snow it is texture, on bare pavement it is the
      warning that saves the set (the physics snaps a cross chain after
      about two dry miles at highway speed; today the snap is the first
      thing you hear); a wear-based brake squeak (worn pads chirp at every
      stop -- the real wear-indicator sound, distinct from the existing
      too-hot squeal); the latch catch click (shipped 2026-07-15 with a
      ui/tick placeholder -- swap for a proper cab sound in this pass).
      Also: a true shift sound (driveline clunk + air/turbo breath --
      the click is UI, not a truck), auditioned only AFTER the engine
      voices revs honestly across shifts (the low-gear bullet below).
      Community votes 2026-07-17 (antonio luigi): the JAKE needs its
      sound most of all (the slowing works, silently -- and the jake
      sample is the known library gap), and the service-brake RELEASE
      should breathe its little air sigh, not just the apply.
      vehicle/brake_release.ogg already ships -- check the wiring.
      Sourcing ladder (owner, REVISED 2026-07-22): Splice first (both
      maintainers hold licenses), then freesound CC0/CC-BY, then
      ElevenLabs generation (character sounds only, never
      timing-critical transients), then field recording (a community
      call for truck recordings is an option), then CC-licensed YouTube
      only, with attribution -- never ordinary YouTube rips. The NAS
      library has NO KNOWN PROVENANCE and is reference/measurement
      material only -- nothing cut from it may ship. CREDITS.md tracks
      provenance for every asset.
      NAS SWEEP DONE 2026-07-18: `docs/sound-shortlist.md` lists
      unauditioned candidates for all seven needs plus ready-to-run
      ElevenLabs prompts. Three findings change the plan. (a) The
      RUMBLE STRIP DOES NOT EXIST in the 62,280-file library -- no
      washboard, no corrugation, no shoulder-drift take; it has to be
      synthesized as a speed-tracking pulse train over a gravel noise
      floor (Sound Ideas 6009 "Auto Road Surfaces" supplies the floor),
      which is the better answer anyway since the buzz rate should
      follow wheel speed. (b) The CURVE TONE LADDER has its material:
      Sony Vol. 4 Vintage Cartoon holds thirteen chromatic `Xylophone
      Single Note` one-shots from one session -- one timbre, three
      pitches, exactly the RFC 1b grammar. (c) TURBO AND DRIVELINE are
      thin (no wastegate, no blow-off, no diesel turbo anywhere), so
      the shift sound gets built from a GMC 6000 gear clunk plus a
      pitched-down transmission clunk plus an air release.
- [ ] **Provenance audit of shipped sound assets (owner, 2026-07-22).**
      The Duff-shared cues cannot ship -- he holds no license for the
      material he passed along (owner ruling, 2026-07-22), so every
      Duff row is a replacement, not a check. Audit ran 2026-07-22
      (git history of every unlabeled row): the 2026-06-18 batch
      (weather, event cues, POI/ambience loops) is all project-clean
      ElevenLabs/procedural work, never swapped since -- weather
      re-sourcing from Splice is now a quality upgrade, not a
      compliance fix. One mislabel found and corrected:
      `ambient/night.ogg` was credited "original" but came from
      Darren's sound pack. Replacements owed: vehicle/horn.ogg,
      driver/yawn.ogg, ambient/night.ogg (Splice); the engine-voice
      rebuild retires idle/start/shutdown, gear_shift, and both
      parking-brake cues.
- [x] **Bobtail means no trailer at all (forum report, SRD625
      2026-07-17).** Shipped 2026-07-22: `trailer_attached` on the truck
      drops the dry van's 6.4 t from the tare on reposition and
      city-service drives, and the air gauge stops waiting on the
      disconnected trailer line. Deadhead-with-empty-trailer keeps the
      old number. Shipped alongside the load-aware shift scheduling the
      same investigation exposed: the lug guard now scales with load
      (empty rigs pull up from 800 rpm instead of bouncing every
      skip-shift), and the stopped-gear reset honors the light start
      gear. Bench anchors, 45 mph from rest: bobtail 15.7 s, deadhead
      20.3 s, loaded 38.7 s.
- [ ] **Dispatch board first-visit hitch (forum lead, Draq via Claude
      2026-07-17).** JobBoard._candidates() walks all 623 cities with
      supported_route() on the first board build in each city --
      measured ~350 ms per new city on a fast machine (then 0: the
      session cache already fixed the old multi-second lag, as SRD625
      reported). Polish: warm the cache off-thread on city arrival so
      even the first board opens instantly on slow hardware.
- [x] **Engine and shift audio tells the truth at low speed -- SHIPPED
      2026-07-22 (sound/engine-integration), owner's ear audition
      owed.** The diagnosed fix option 1 landed, upgraded: BASS now
      voices the engine as a multisample ring of four REAL 896 cab
      cuts at their recorded rpms (680/1000/1150/1800), crossfaded
      equal-power with per-band playback-rate slides of rpm/native
      (clamped 0.85-1.30), so pitch tracks RPM proportionally through
      every launch pull. Shifts play real recorded cuts from the same
      cab (manual and automatic round-robin banks; the gear click is
      retired in overlay builds). Cold starts fast-idle at 900 while
      the compressor builds air (physics change, vehicle.py), with the
      fill hiss and the settle as the drive-ready flip. Brake press
      plays the clunk bank leveled by force; release breathes the air
      back out, scaled by how hard you braked. Career 1.9 now carries
      the approved encrypted sound pack through Git LFS, so source and
      release builds use the same audio without distributing the raw
      library recordings. (3) SHIPPED 2026-07-24: the
      engagement clunk at shift END, together with the shift SIGH --
      the voice now follows the physics rpm falling toward the new
      gear through the interrupt (ducked, unloaded) instead of the
      frozen pre-shift hang; kachunk -- sigh -- kachunk per the
      owner's ear. (4) OBSOLETE: Phil's modern-AMT power upshifts
      (155f05ad, 0.25-0.5 s) already went past the 0.7 s idea. Also
      open: launch/load rev one-shots (engine/rev_launch, rev_load are
      encoded and staged but not yet wired -- mixing them over the
      ring needs the owner's ear) and per-trigger pitch jitter on the
      banks (needs a playback-rate parameter on one-shots).
- [ ] **Audible traffic -- hear the vehicle you overtake (owner idea
      2026-07-16).** Traffic already exists as modeled vehicles with
      lanes and speeds; give the near ones voices: continuous positional
      emitters (engine/tire loops) panned by relative lane and faded by
      gap, so closing on a slow truck is heard before any speech, an
      overtake tracks past the window, and a vehicle sitting in the
      passing lane is audible before a lane change -- the ear-level
      groundwork that makes real overtaking decisions possible. Speech
      stays the fallback (L and the traffic status already report
      lanes); sounds from the NAS library. Infrastructure work on our
      side of the fence -- independent of the steering-grammar design
      offered to Josh.
- [ ] Runaway truck ramps as regular highway furniture on steep descents: the
      real ramps are now baked (96 tagged escape ramps with side and milepost
      in `world_data/us/gameplay/ramps.jsonl`, read offline from the local
      Geofabrik PBFs), so approach announcements and the escape move are
      wiring work now, not a data gap -- announced on approach, takeable as
      the escape move when the brakes are gone (the physics already runs away
      honestly -- bench `grade-runaway` tops 149 mph and grenades the engine
      past redline). Curated DOT gap-fill welcome later; never synthesized
      where the real road has none (owner call 2026-07-15).
- [ ] **Runaway ramp aftermath (owner design 2026-07-15).** An arrester
      bed buries the rig to the axles; you do not drive out. The sequence:
      gravel roar and grind-down, cab contents going forward, air hiss,
      then ticking silence -- and the truck is stuck with the engine fine
      and the brakes cooked. Mandatory roadside call for a heavy-wrecker
      winch-out: expensive, hours lost, carrier-billed for company
      drivers, the GOLDEN FLARE membership's flagship moment. NO citation
      ever -- taking the ramp is the right move and must never score worse
      than the alternative; the lesson costs money and time, not blame.
- [ ] **Crash consequence tiers (owner design 2026-07-15).** Today every
      collision scrubs speed, adds at most 18 percent damage, and you keep
      rolling -- there is no catastrophic outcome. Add a severity
      threshold: below it, today's fender-bender behavior stands; above
      it the truck is DISABLED where it sits -- tow to the nearest city,
      trip over, load salvaged or claimed, a heavy invoice, and a safety
      record strike a carrier cares about. Head-ons and rollovers are the
      tier's ceiling (truck effectively totaled, load gone). The player
      always walks away -- "You walked away. The truck didn't." -- the
      wallet, the clock, and the record take the damage, never the
      driver.
- [x] **Ramp endings announced early, and in real time -- SHIPPED
      2026-07-15.** Both prongs, exactly as designed off the log receipt
      (exit 17:00:13, sign blown 17:00:18): (1) the signal-on
      announcement names the ending ("The ramp ends at a stop sign.")
      with a mile-plus of mainline to plan on, and the U upcoming key
      carries the same phrase -- the terminal-control decision was made
      previewable (`_ramp_control_for`, pure function of trip seed +
      baked OSM data) so the early call and the ramp always agree; (2)
      `trip.controlled_ramp` pins the clock to REAL time from the gore
      until the truck is through a light/sign terminal, instead of
      easing compression only with speed. Free-flow ramps compress as
      before.
- [ ] **Signal running: dice and tickets, not a guaranteed clip (owner
      playtest 2026-07-15).** Blowing the ramp-end red or stop sign today
      ALWAYS clips cross traffic and never draws a citation -- backwards
      on both counts. Make the clip a seeded traffic roll (sometimes the
      horn and a near miss, sometimes a T-bone that belongs in the
      catastrophic tier), and make running the light risk a citation on
      the existing trooper/citation rails (chain-law checkpoint pattern).
      Rides the back-road stoplights feature where the signal mechanic
      lives.
- [x] **Dense maxspeed and curve-geometry sweep (2026-07-15).** Every leg in
      the country re-sampled along its real routed geometry with a
      curvature-adaptive sampler (dense through curves, collapsed on tangents):
      posted speed limits now step through the real canyon and mountain zones a
      driver hears, instead of one heuristic guess -- all 1,287 legs carry a
      profile and the anchor linter reports zero on the fresh data. The same
      pass banked the fine data the driving model needs next: 63,724 per-curve
      records (radius, direction, and a physics advisory speed v = sqrt(a_lat
      R)) and 96 real runaway-truck ramps, stored as delta-encoded, sharded,
      regenerable text under `world_data/us/geometry` and
      `world_data/us/gameplay`. Tools: `bake_curve_geometry.py` (the sweep) and
      `harvest_escape_ramps.py` (escape ramps read offline from the local
      Geofabrik PBFs, since the self-hosted Overpass extract omits them).
- [x] **Coverage-gap markers end the town-limit smear (2026-07-19).** The
      sweep always knew where OSM tagging ran out (`mph: null` rows in the
      derived shard) but the world schema dropped them, so a village 30 could
      rule miles of untagged highway (player-found live: NY-12 out of Norwich
      held 30 for nine miles). The schema, runtime, anchor repair, and bake
      now carry the markers end to end -- inside a gap the road reverts to the
      highway/region heuristic. 670 markers migrated onto 391 legs from the
      existing sweep shard; 8 never-swept legs heal when the sweep reaches
      them. Paired with co-driver speech: a warn-worthy posted drop is called
      ahead with pacenote timing, and a short town zone has its length spoken
      on entry.
- [ ] Lateral traction on curves and ramps: the curve geometry now exists (the
      2026-07-15 sweep above bakes per-curve radius, direction, and an advisory
      speed per leg), but the 1-D truck model does not yet consume it -- so
      cornering grip, curve-speed advisories keyed to load and ice, and
      rollover/off-tracking stay future, now unblocked on the data side and
      gated on surface streets for off-tracking.
- [x] **Chain laws and the tire-type ladder.** Traction equipment is now a three-rung ladder on the per-truck condition record: all-season (today's physics), winter compound (x1.3 grip on snow, x1.5 on ice, honestly paid for with x1.5 tread wear and a 3 percent dry-grip loss -- owner-operator garage purchase at a 25 percent set premium; company tractors run carrier rubber), and chains (x1.5 snow / x2.5 ice, steel replaces the contact patch so tread wear and hydroplaning stop mattering, $750 a set, carrier-billed for company drivers). Chain-law areas sit over sustained steep grade (5 percent for a mile-plus) and activate from live weather -- snow = Level 1 (winter tires or chains), freezing rain = Level 2 (chains) -- with a flashing-sign GPS callout on approach, escalation re-announced. Chaining up is a pause-menu act while stopped: 25 minutes and 6 fatigue by day, 40 minutes and 10 fatigue by headlamp at night (the lonely-snowy-night-out-of-Denver penalty, delivered); removal 10 minutes. Chains are consumable: ~500 miles used right, ~2 miles on bare pavement at highway speed before a cross chain snaps into the fender (4 percent damage, set scrapped, spoken cue). Non-compliance in an active law speaks a warning, then a seeded checkpoint past the area midpoint writes a $500 citation (0.6 staffed chance, one roll per area -- reloads do not re-roll). Bench anchors: ice stop 880 ft stock / 613 winter / 215 chained from 30; the chained jake holds the icy 4 percent it lost unchained (2:14 slip vs 15:06).
- [ ] Chain-up areas as physical pullouts: today chaining works anywhere stopped and the pullout is spoken flavor; a real chain-up area stop (safe, lit, maybe a helper service that installs for money) rides the stoppable-stop spine with Big Buck's.
- [ ] Road-stop tire service sells wear repair only; swapping compound (and pricing winter rubber) stays a terminal-garage act. Revisit if field tire swaps earn their menu weight.
- [ ] Chain controls by state personality: CO/CA tier wording shipped as the generic shape; later, region-flavored signs and the CA R1/R2/R3 phrasing on the California legs. Pure sign-wording work -- the corridors already carry curated ORS grades, and chain-law areas place today on 158 legs (I-70 Denver-Silverthorne, Siskiyou, the Grapevine).
- [x] **Profile integrity, client half.** `profile_invariants.py` enforces the hard, version-stable invariants (ranges, counter relations, closed enums, per-truck condition bounds) as defense-in-depth behind the Ed25519 signature check on every cloud restore, with a plain spoken refusal; unknown content keys from newer builds deliberately pass. `docs/profile-invariants.md` is the maintained validation list for the server gate -- hard rules mirrored in code, plausibility heuristics (money-vs-earnings, XP-vs-miles, achievements-vs-stats, possession-implies-acquisition with the Golden Antler as the flagship) specified for the server with exact game constants. Follow-up: the append-only event ledger that upgrades server validation from plausibility to recomputation.
- [x] Release-archive verification: after a player report of a Linux snapshot with no game file (2026-07-14 sweep found all published archives intact), `tools/build_release.py` now re-opens each finished archive and proves the executable (with its permission bits) and key payload survived archiving, and `build.yml` fails instead of publishing a release with a missing platform download.

Four threads: make the drive *between* the exits real, give every maneuver
and working hour weight, make the career read like real employment, and
make the world big and specific enough that every run feels like a place.
(Also releasing with 1.9: everything built for 1.8 that missed the 1.8.0
cut -- the exit setup, expanded enforcement, logbook, timed dock work, and
city service drives below.)

### Lanes and maneuvering

- [x] **Exit-flow speech honesty (playtest transcript, 2026-07-16).** The
      drift-on exit slowdown said "confirm the exit" though no confirm
      action exists -- obeying it toggled the signal OFF and cost the exit.
      Fixed four ways: the prompt now says "hold Right for the exit lane";
      inside the last mile a stray X keeps the signal (deliberate second
      press cancels); two quick Left/Right taps with drift on explain that
      taps only nudge the wheel (taps are the assist-off lane change, so the
      silence read as broken keys); and the terse missed-exit turnaround now
      says to re-signal. Same session: the All assists preset now drops lane
      drift to off (owner call) -- the easiest preset must not leave a
      manual steering task running; other presets still never touch it.
      Second finding, same transcript: the missed-destination-exit recovery
      only worked ONCE (the say-once latch also swallowed the reposition), so
      a second miss soft-locked the trip at 0 miles remaining with cruise
      dying every frame; and the turnaround dropped the player 1 mile out --
      a few real seconds under compression. Now every miss reroutes, and the
      turnaround uses the full _exit_window_mi() lead like a first approach.
      Third finding (turnaround fix verified live in the same session): a
      cautious stop on "brake to a stop" landed ~0.2 mi short of the ramp
      light's stop bar, outside RAMP_ACCESS_MI, where the waiting handshake
      never engages and one 15-second green cannot be crossed from a
      standstill -- an endless red/green loop with zero position feedback.
      Speech is now stop-bar-aware: a stopped-short creep prompt, at-the-bar
      vs short-of-it yellow/green wording, and the callout says to stop AT
      the light. Round 2 (verified live, same day): the prompt now NAMES the
      gap in feet/meters and says "drive up" past ~200 ft -- "creep" over
      600 ft spans several cycles and still read as broken. Open follow-up:
      consider a queue-position readout (S-style key) for distance to the
      bar while on a controlled ramp.
- [x] **Stop-or-swerve for fixed-object hazards (owner call, 2026-07-16).**
      "Brake to 25 clears debris" never made physical sense. Dodgeable
      (fixed-in-lane) hazards now resolve by lane change at speed OR by
      braking to HAZARD_CREEP_MPH (8) and easing around; the deadline
      budgets the longer stop via _brake_budget_s(target), a once-per-hazard
      hint fires if the player settles at the old 25 ("still in your
      lane"), and AEB brakes to the creep speed for these. Moving/surface
      hazards keep the 25-mph contract. Manual + in-game help updated.
- [x] **AEB budget honesty (playtest, 2026-07-16).** `_brake_budget_s` used
      the spec-sheet decel (rated g x weather grip) while the real brake
      model applies fade (to 20 percent when cooked), shoe wear, tread, and
      the overweight capacity cap -- so on hot brakes the assist engaged
      with zero margin and the collision landed 2 s after "Emergency
      braking engaged." Now `TruckState.full_service_decel_mps2()` feeds
      the budget (hazard warning lead times inherit the honesty), and the
      assist leads by AEB_BUDGET_MARGIN + AEB_LEAD_S for the heat the stop
      itself adds.
- [x] **Discrete lanes on the drift model.** `LaneKeeping` carries a discrete
      lane index under its continuous offset: with steering assist on,
      steering across the line is the lane change; with assist off, a
      Left/Right tap runs a timed change with signal clicks. Dodgeable
      hazards ("Brake or change lanes!"), sideswipe risk against real
      absolute-lane traffic, construction lane closures with barrel crashes,
      keep-right-except-to-pass CB nags, and right-lane exit gating.
- [x] **Signalized ramp terminals grounded in OSM.** Baked
      `traffic_signals`/`stop` nodes on 6,295 of 13,504 exit ramp links
      (heuristic elsewhere): a red/green cycle at the stop bar, grace
      distance, cross-traffic clips for running it -- now with dedicated
      red and green light earcons alongside the spoken callouts.
      Reworked 2026-07-14 after a log-proven playtest crash: lights now
      run a real green-yellow-red cycle (15 s green crossable from a
      stop, 4 s yellow, entering on yellow legal like the law), and
      every phase change on the approach is spoken -- the old one-flip
      announce cap could say green, silently flip red, and punish the
      driver for obeying the last thing they heard.
- [x] **Congestion grounded in FHWA HPMS volume.** Real AADT baked per leg
      drives clock-gated jams on a commuter curve: metro stretches jam at
      rush hour and flow free at midnight; entering a live jam injects slow
      traffic into both lanes.
- [ ] **Live traffic volume -- deferred to 2.0.** The split `world_data`
      tree carries no `traffic_aadt`, so congestion placement falls back to
      the metro heuristic and no jam lands on any route: a sweep of 12 seeds
      across 8 metro pairs found none. Sourcing live volume needs data work
      beyond the 1.9 scope, so it waits for 2.0. Until then nothing that
      depends on a live jam can be played or tested on this line, including
      the end-to-end speed-control case for heavy traffic, which is xfail in
      `tests/test_playtest_harness.py` for exactly this reason.
- [x] **Surface streets driven for real.** Tier-1 street chains carry baked
      per-segment cues and speed zones; boundary cues speak the maneuver
      with block-aware distances; city-passage and highway-pressure language
      is suppressed on streets.
- [x] **Steering audio cues.** The geometry builders bake turn *directions*
      from the signed bearing change at each road-name boundary ("Turn right
      onto", with near-straight name changes as "Continue onto"), and the
      runtime plays a direction-shaped earcon panned from the maneuver side:
      falling chime left, rising chime right, steady tone ahead.
- [x] **Surface chaining, arrival side.** The destination exit ramp flows
      onto the facility's tier-1 street chain and ends at the standard gate
      arrival, with clock/toll/weekday continuity and a `surface_chain` save
      marker; facilities without turn-level data keep the scripted arrival.
- [x] **Surface chaining, departure side.** A loaded run out of a
      chain-capable origin facility starts at the gate and drives the same
      street chain outbound -- leg order reversed and every junction's turn
      direction flipped -- then merges up the on-ramp onto the highway trip
      with clock and toll continuity and a `departure_chain` save marker.
      Facilities without turn-level data keep the scripted highway start.
- [x] **Tier-1 surface coverage expansion.** The "Data Expansion" pass of
      `docs/surface-roads-plan.md` shipped: the endpoint, local-approach,
      city-service-geometry, and facility-approach sweeps re-ran over the
      full 623-city map (5,486 facilities, 3,636 source-backed endpoints,
      6,223 of 6,233 approaches on named roads, 1,541 turn-level facility
      chains; 372 of 623 home-terminal yards start loads with turn-by-turn
      streets). The builders survived the slug migration and now print
      per-state progress. Still open below: widening the high-confidence
      facility-type set for turn geometry (grain elevators, cold storage).
- [ ] **Turn geometry for more facility types.** The turn-level route pass
      still limits itself to the original high-confidence type set (yards,
      cross-docks, warehouses, plants, ramps, parcel hubs). Grain
      elevators, cold storage, and food processors now have source-backed
      endpoints at scale -- extend `HIGH_CONFIDENCE_TYPES` in
      `tools/build_facility_approaches.py` after judging spoken-name
      quality on a sample.
- [x] **Street cue pacing and clean spoken names.** Street cues pace one
      maneuver at a time with a block-scale lookahead (a departure used to
      read the whole itinerary in one burst), and spoken street names trim
      raw OSM ref lists at load ("(SR 933;BUS US 31)" speaks as "(SR 933)").
- [ ] **Interactive street turns ride nromey's turn-by-turn work.** A
      steer-each-turn prototype (arrow key inside a reaction window, missed
      turns stop and turn around, realistic-preset default) was built and
      then withdrawn on 2026-07-15 in favor of the fork's richer
      turn-by-turn solution on the PR #75 line. When that lands, fold the
      one-maneuver pacing above into it and revisit whether manual steering
      still needs a preset hook here.
- [ ] **Normalize street refs in the builder sweep.** The runtime trims
      multi-ref lists to the first ref, but the baked data still carries
      them (1,185 in facility_approaches.json), and abbreviations like
      "BUS US 31" or "Hist" would read better expanded ("Business US 31",
      "Historic"). Fold proper ref selection and expansion into the next
      facility-approach/city-service geometry sweep.
- [ ] **Street chains for single-segment approaches.** A 2026-07-15 logged
      playtest out of Gary Intermodal Ramp had no spoken street guidance in
      either direction: its facility approach is source-backed but a single
      non-turn-level segment (2.1 miles on Richard G. Hatcher Boulevard), and
      the chain gates require a multi-segment turn-level chain, so both the
      arrival and the loaded departure kept the scripted highway start.
      Either let genuine source-backed single-road approaches drive as
      (turnless) chains -- "out of the gate onto Richard G. Hatcher
      Boulevard, 2.1 miles to the I-90 on-ramp" is real guidance -- or make
      the next facility-approach sweep try harder for turn-level geometry at
      intermodal ramps like Gary's before falling back to one segment.
- [x] **Template facility realism pass.** Template port terminals are now
      gated on a MARAD/USACE-derived allowlist of real deep-water, Great
      Lakes, and navigable-river port cities (282 -> 78), and template
      intermodal ramps are suppressed in ~250 towns with no rail intermodal
      service in dray reach (402 -> 157). Curated facilities are never
      gated, and accepting a stale cached board offer for a retired
      facility pulls the offer instead of crashing.
- [x] **Grant ports to the Great Lakes cities missing one.** Toledo,
      Detroit, Chicago, and Green Bay carry the port market tag as city
      tags and joined the template-port allowlist, so each now hosts a
      port terminal (82 template ports total). Their endpoint/approach
      records ride the next data sweep like any map growth. Dedupe
      decision: the 40 cities with both a curated port and a template
      port terminal keep both -- real ports run many terminals, and the
      extra facility is freight variety, not a realism error.
- [ ] **Surface intersections.** Phase 4 of `docs/surface-roads-plan.md`:
      stop signs and traffic signals at surface-street junctions, junction
      decision prompts, and traffic pressure at intersections -- extending
      the ramp-terminal signal mechanics (red/green cycle, grace distance,
      cross-traffic consequences) onto the tier-1 street chains. Deferred
      until local-drive pacing was proven in playtests; the per-system
      harness sweep now passes clean across all 38 corridors.

### Maneuvers, enforcement, and the working day

Mechanics finished after the 1.8.0 cut, so they release with 1.9 (the
detailed design notes live in the sections further down, whose "Shipped
for 1.8" framing predates the release split):

- [x] **Enforcement presence is the road's, not a setting (owner ruling,
      2026-08-16).** The `enforcement_presence` field, its levels, its
      settings row and its ambience table are gone. It never touched odds --
      `announced` is set for every staffed post at any level, so the "quiet"
      player was never safer -- but at `full` it played the marked-unit pass
      for EMPTY crossovers, and by ear that is identical to a staffed one. So
      the road sounded saturated with police, a third of whom demonstrably
      ignored a speeder going by, because nobody was in the car. An unstaffed
      post is now silent at all times: a marked unit you can hear is one that
      can act. Loudness comes from `Trip._post_density_at` -- deliberately the
      same number the placement walk uses, not a parallel formula -- which
      measured 0.47 to 1.49 across region, road class and clock, bracketing
      the slider's old 0.45/1.0/1.35. Old settings files carrying the key load
      unchanged: `Settings.load` only applies keys that still exist.
- [x] **Roving patrols could never clock anyone on a highway -- FIXED
      2026-08-16 after an owner-ordered harness playtest.** There were TWO
      blockers, and the first hid the second. (1) `PACING_MIN_REAL_S = 20`
      real seconds, unsatisfiable at any compression the game offers. (2)
      Even with that made distance-based, a pacing unit only banks road AFTER
      the truck passes it, while `end_mi` stopped asking it to look 0.3 of a
      mile past itself and the tracker ran to a literal 1.0 -- so the most
      pace it could hold at a moment it was allowed to observe was 0.3, short
      of any gate. Both windows now read one constant, `PACING_WINDOW_MI`.
      MEASURED, same roads and seeds either side: at a sustained 12 over,
      roving patrols went from 315 looks and ZERO catches to 350 looks and 7
      catches; total stops over 2,007 miles went 17 -> 24, one per 118 miles
      -> one per 84. Harness clean on five enforcement scenarios. Three tests
      added, including one that pins the gate inside the window, since
      nothing in 3,940 tests caught either bug.
- [x] **An opt-in guide tone ships alongside the bed (2026-08-17).** Does
      not close the bullet below -- the bed is still too quiet and still
      needs regenerating, which is the fix that helps everyone. This is the
      escape hatch for drivers the bed already fails.
      THE RULING WAS CHECKED FIRST, not worked around: the community ruled
      against steering tones (JaceK on the audiogames.net thread the owner
      posted 2026-07-17 -- continuous tones overwhelm the soundscape and
      hurt players with sensory or hearing conditions), and the owner
      concurred at the time. What the ruling objects to is a tone nobody
      asked for, so `Settings.lane_guide_tone` is False by default, an
      unreadable value falls to the bed, and silence-is-centered still holds
      -- the loop starts on the guide's wake and stops on its settle, so a
      straight road is as quiet as it ever was. Owner decision 2026-08-17:
      "we make it optional, the alternative is an unusable sound."
      Darren's candidate is the SPEC, not the bytes: 291.6 Hz at -16 dBFS
      RMS, both his. His file is a 1.45 s one-shot whose seam could not be
      trimmed into a loop (three attempts, best -35 dBFS), and the harmonics
      sit 40 dB down, so it is a pure sine and nothing else. Synthesized in
      `lane_guide_tone.py` like the ladder earcons: the sample count is
      chosen so a whole number of cycles fits exactly, which makes the wrap
      error zero rather than small. Credit him in the release notes.
      Auditioned against the real cab before wiring -- `engine/mid` and
      `vehicle/road` pulled from the pak, road at the 0.97 gain
      `set_road_noise` runs at highway speed, panned by GUIDE_PAN_MAX and
      PAN_SLEW_PER_S. Measured engine -18.7 and road -33.3, matching the
      numbers below.
      MEASURED 2026-08-17, and the worry was right: 291.6 Hz is the WORST
      of eight pitches tested against the real engine loops. Narrow-band
      energy around it peaks at 130.4 dB on `engine/midhigh` -- ordinary
      cruising -- against 121.8 at 1320 Hz and 122.8 at 880. That is 8.5 dB
      more engine sitting directly on Darren's pitch than on the quietest
      candidate, which is the difference between a cue that cuts through and
      one that smears into the engine exactly when the driver is holding
      speed. Higher pitches also localise better, which is the other half of
      what this cue has to do.
      NOT CHANGED WITHOUT AN EAR: the pitch is Darren's contribution and the
      owner approved it by listening, so a table is not enough to overrule
      it. An A/B of 291.6 against 880 over `engine/midhigh` is built and
      ready to play. If the ear agrees with the measurement it is one
      constant, `TONE_HZ` in `lane_guide_tone.py`, and the loop length
      follows automatically.

- [ ] **The road lean is inaudible under the engine, and the fix is the ASSET
      (Darren and the owner, 2026-08-17).** Measured: `vehicle/road` is
      -33.6 dBFS RMS against the engine loops' -18.7, and `set_road_noise`
      already runs the road channel at full gain by highway speed, so there
      is no headroom. The lean carries its meaning in the PAN of that bed, so
      15 dB down it carries nothing.
      TRIED AND REVERTED THE SAME MORNING: ducking the engine while the guide
      is awake (`GUIDE_DUCK_LEVEL`, measured 6.9 dB of room, road from -15.2
      to -8.2 relative). Darren rejected it before it shipped -- "the engine
      sound is nice and smooth and does not need to be tampered with at all"
      -- and he is right for a reason the measurement could not see: the
      engine is how a blind driver reads speed, load and gear, and a bend is
      when that matters most, not least. Reverted from the build.
      THE FIX: re-record or regenerate `vehicle/road` louder so the bed sits
      near the engine on its own. Fixes every use at once, touches nothing
      else, needs a repack (`tools/pack_sounds.py`) since the loose tree is
      builder-local and only the pak ships. Darren should judge the new
      recording before it lands.
      THE NUMBER TO HIT, and this is the useful thing that came out of
      Darren's candidate file (`sounds/lane beep.mp3` in the tester Dropbox,
      2026-08-17): **-16 dBFS RMS**, which is where his file sits and which
      puts it 2.6 dB ABOVE the engine loops. That is the level the bed needs.
      "Louder" was the instruction before; this is a target.
      OWNER DECISION 2026-08-17: wait for the ElevenLabs quota (resets
      2026-09-06, see the radio-station note) and generate the bed there
      rather than adapting Darren's file. His file cannot do this job -- it
      is a single 1.45 s sustained 290 Hz tone with 0.01 s of trailing
      silence, so it cannot loop without clicking, and the lean is a
      continuously panned BED rather than a one-shot.
      AND IT IS NOT AN EDGE CUE EITHER, which is where I nearly sent it: the
      edge boundary already has a three-rung ladder chosen to stay separable
      under engine noise (`edge_clip` intermittent, `edge_strip` periodic,
      `edge_shoulder` aperiodic), plus a single-hit rumble strip and the
      transverse strips. A discrete "you crossed the edge" beep would be a
      fourth cue saying what those three already say. The gap is the
      PRE-edge lean, and only the lean.
- [ ] **Learn game sounds demos cues the player's settings make impossible
      (Darren, 2026-08-17).** He reported the road lean as "very very quiet
      and you can hardly even hear it". Measured: it is not quiet. On the
      road the bed runs at 0.97 gain at 65 mph against the demo's 0.60, and
      the pan is `GUIDE_PAN_MAX = 0.8` in both -- the drive is LOUDER than
      the lesson. What is actually true is that the lean cannot happen for
      him: it needs lane departure warning ON and lane keeping off or
      partial, so on full lane keeping there is no lean at any volume, only a
      centred bed. The catalog's `when=` field says exactly this, but it
      lives behind F1 while pressing Enter just plays the cue -- so the
      screen teaches a sound the player will never hear and says nothing
      about it. Same principle as the empty-crossover earcon removed
      2026-08-16: a cue that cannot fire must not present as one that can.
      FIX SHAPE: give `SoundEntry` an optional availability check against
      live settings, and have `play_entry` say "your settings mean you will
      not hear this on the road, because ..." before or instead of the demo.
      Not done on build morning because it is a new mechanism across a
      catalog rather than a one-line fix, and the entries that need
      annotating have to be identified rather than guessed.
- [ ] **Things an officer never notices that the game already models
      (2026-08-16).** `_candidates` covers speeding, unsafe equipment, no
      chains, no lights, following too close and left-lane misuse. Missing,
      each already simulated elsewhere: an hours-of-service violation
      (`hos.in_violation`, and a roadside inspection is exactly where it is
      caught -- the most realistic omission for a truck); the engine brake in
      a no-engine-brake town (`Trip.engine_brake_ban_at`, which has its own
      ontology row); and wrong-way driving (`WrongWayMixin`). All three want
      a `WHAT_` reason, a fine in `models/enforcement`, and a visual-method
      post to see them.
- [ ] **The deadline planner is blind to curves (measured 2026-08-16, owner
      question).** `route_drive_hours` walks the route on posted limits
      alone -- there are zero references to curves anywhere in
      `models/jobs.py` -- so every bend the driver actually has to slow for
      is time the plan never budgeted. Measured across eight routes, the
      advisories cost 2.8 percent of drive time on average: 0.5 percent on
      flat corridors (Chicago-Indianapolis, Buffalo-Rochester,
      Phoenix-Flagstaff), 3.3 to 3.4 on Atlanta-Nashville and
      Seattle-Portland, and 5.6 on Denver-Salt Lake City, whose worst bend is
      signed 20.
      NOT URGENT, and deliberately not done before the 2026-08-17 build:
      `DEADLINE_PLANNING_SPEED_FACTOR = 0.88` already discounts the plan by
      12 percent, which covers even the mountain case. The reason to fix it
      anyway is that the cover is luck rather than design -- the bends
      already eat half that margin in the mountains, and every further round
      of curve enrichment erodes it with no signal, until one day a corridor
      goes undeliverable and nothing in the code will say why. Making the
      planner cap each sampled segment at the curve advisory is small and
      contained, but it moves every deadline in the game, so it wants its
      own change and a full gate.
      CHECKED AT THE SAME TIME AND SOUND, so nobody re-investigates it: the
      hours-of-service model does NOT conflate the duty window with the
      driving limit. `driving_min` and `duty_min` are separate, `drive()`
      advances both, `on_duty`/`off_duty` advance only the window, short
      breaks do not extend it, the 30-minute break lands after 8 hours of
      driving, and split sleeper berth is implemented. It only FEELS
      conflated because of where the arithmetic lands: simulated shifts end
      at 12.6 h duty for drop-and-hook and 13.2 h for a live load against an
      11-hour driving limit, so an ordinary day is bound by driving and never
      meets the window -- while a slow shipper (14.7 h) or a breakdown
      (14.1 h) does hit it. That is the same shape the window has in real
      life, so it is tuning to leave alone.

- [x] **Highway exits take a real setup.** X signals the announced exit,
      the GPS asks for the right-side exit lane, checks ramp speed at the
      gore, and explains missed exits; destination ramps follow the same
      speed/lane/intent contract, and merge traffic puts spoken pressure on
      the maneuver. Since 2026-08-15 the approach is graduated rather than
      stepped: automatic control holds road speed and sheds along the
      distance still left, the arrival zones are sized from the destination
      facility's own approach record and never cap below ramp speed, and
      exit-traffic advisories speak only for an exit the driver is taking.
      Two more of Shane's reports closed on `fix/ramp-speed-control-resume`
      (2026-08-15): the ramp now PAUSES an armed speed-control session
      instead of disarming it -- in all three places that used to end it
      outright -- and lifts that pause by itself once the bar is honored and
      the truck is rolling again, so nobody has to press resume past a stop
      bar; a destination exit still holds until departure. And the approach
      glide is measured in real miles, with `Trip._armed_exit_decompression`
      putting the trip on the real clock for the shed window the way a
      controlled ramp and a severe curve already do, so signalling nine miles
      out no longer starts the shed the moment the signal goes on, at any
      pacing. Battery scenario: `ramp_speed_control_handback`.
- [x] **Enforcement beyond the speeding stop.** Weigh-station blow-pasts
      and severe visible damage draw roadside stops; running from lights
      escalates through warnings to a felony stop with spike strips and
      loaded-run cancellation; construction zones stage a merge/flagger
      taper before the barrels; CB chatter hints at bears and work-zone
      enforcement a few miles out.
- [x] **The working day has weight.** An in-cab logbook records a real
      Record of Duty Status that traffic stops actually read; loading,
      unloading, and pull-ins take spoken on-duty time; loaded launches ramp
      in like a heavy truck; rush hour and corridor busyness shape traffic
      and hazard pacing.
- [x] **Three distinct driving-pressure modes.** Relaxed retains the 1.9 truck,
      traffic, weather, fatigue, and hazard systems with calmer spacing, wider
      reactions, gentler recovery, and quieter routine speech. Standard keeps
      balanced pressure; Realistic keeps the quickest decision cadence.
- [x] **Drive to city services.** The terminal's freight office, garage,
      and truck dealer are short local drives with sourced names, road
      context, and (where the data supports it) real street-by-street
      turns.

### Career, dispatch, and business

The other half of the 1.9 line: the career now reads like employment at a
real starter carrier, not a menu of freight. Detail lives in the Business
section below and the Unreleased changelog; the release-line view:

- [x] **Grounded start choices.** New careers pick among fictional
      company-driver starter carriers (assigned equipment, carrier-paid
      fuel and routine repairs, different wage/dispatch/freight tradeoffs,
      carrier-shaped dispatch boards) or a higher-risk owner-operator start
      with operating costs active from day one.
- [x] **A 30-level business arc.** Company-driver ranks lead to the
      level-18 leased-on owner-operator gate, level-21 authority prep,
      level-25 own authority, and independent ranks through 30 -- with
      distinct guidance voices per level band and haul-length caps that
      grow through the whole arc instead of maxing out by level 12.
- [x] **A months-long grind where every level pays out.** Rebalanced XP
      (flat completion lesson, deeper on-time streaks, clean-cargo bonus,
      stronger specialty multipliers) and re-paced level 21-30 thresholds
      put level 30 at roughly 300+ real hours with no single-level walls,
      verified by a deterministic pacing model (`tools/career_pacing.py` +
      `tests/test_career_pacing.py`). Every rank now names a concrete
      unlock: extra decline at 5, board depth at 6/10/12, specialized
      freight weighting at 11, premium long-haul lanes at 12, the
      owner-operator checklist read from 14, and fleet tractors below.
- [x] **Dispatch-assigned company tractors.** A carrier fleet
      (`models/carrier_fleet.py`) assigns every company driver a tractor by
      level band -- yard standard, regional at 4, long-haul at 9, premium at
      13, first pick of the yard at 17 -- deterministically per driver and
      carrier. Tier promotions hand over a fresh unit at settlement with
      spoken hand-over text. Ten new tractor models fill the fleet and the
      owner-operator dealer catalog.
- [x] **Dispatch freedom is earned.** New hires run the load and lane
      dispatch assigns -- accept or decline against a small budget that
      refills on promotion, no route menu -- with load choice from the full
      board unlocking at level 8 and route choice reserved for
      owner-operators and own authority. Declined loads stay declined.
- [x] **The economy pays like a real one.** Carrier accounts cover a
      company driver's road fuel and repairs; specialty cargo and on-time
      streaks compound experience; reputation pays a continuous dispatch
      trust bonus; personal money buys endorsement courses and motel rest.
- [x] **Trailers matter.** Trailer programs for leased-on owner-operators,
      owned trailers under own authority, and dispatch rows that preview
      trailer fit and estimated take-home before you accept.
- [x] **A first day that lands.** A repeating first-day briefing until the
      first dispatch is accepted, a Career plan terminal item naming the
      next practical step, and a rewritten How to play that teaches earned
      dispatch freedom.
- [x] **166 achievements.** The badge wall nearly doubles and keeps
      growing: state, region, and city arrivals, cargo firsts, close calls,
      mishaps, and career milestones, each nodding to a country or trucking
      song. The 1.9 arc adds level milestones through 30, business-gate
      badges (buy-in, own authority, self-paid courses), fleet-tractor
      badges, map-coverage milestones (cities, states, the Dakotas,
      Montana, northern New England) sized for the 623-city map, and twelve
      song-city arrivals (Muskogee, Memphis, Kansas City, Saginaw, Fort
      Worth, San Antonio, New Orleans, Houston, Winslow, Chattanooga,
      Abilene, and Jackson -- Tennessee or Mississippi both count) via the
      shared `SIMPLE_ARRIVAL_BADGES` mapping. The copy rule now allows a
      song title in badge text when it is simply a place name; artist names
      and lyrics stay out.
      The 2026-07-25 pass adds twenty-one more over ground the wall had
      never touched: the radio (a station ridden until the hiss takes it,
      a fringe catch from far outside its contour, one signal held across
      three state lines, twenty-five stations found), driving craft (two
      miles of downgrade on the engine alone, drums cooked past fade,
      predictive cruise reading a real hill, a run better than eight miles
      to the gallon), the slip-seat yard (five tractors, every fleet band),
      calendar dates (Christmas, Friday the thirteenth, New Year's
      midnight), clean-record streaks, and a short row of deliberate jokes
      -- eighty-eight miles an hour, sixteen tons in one load, and a solid
      mile held at exactly sixty-nine.
- [x] **Rookie-arc achievement rework (owner-approved).** A first career run
      used to fire four unavoidable badges (`first_dispatch`, `air_ready`,
      `first_pickup`, `first_delivery`) plus up to three likely ones
      (`first_on_time`, `clean_delivery`, `speed_limit_saint`) before the
      player had done anything skillful. `first_dispatch`, `air_ready`, and
      `first_pickup` now fold into one new "First Day" badge awarded on
      pickup completion; their old ids and catalog entries stay so the cloud
      validator's allow-list never sees a removed id, they simply no longer
      trigger. `first_on_time`/`clean_delivery`/`speed_limit_saint` in
      `_award_arrival_achievements` now gain delivery-count floors
      (`>= 2`/`>= 3`/`>= 4`) so they spread across the first several runs
      instead of all landing on run one, just ahead of `five_deliveries`.
- [x] **Save compatibility.** Careers back through the version-4 schema
      load with sensible defaults, and newer-snapshot saves no longer crash
      older-schema loads.

### Radio

- [x] **The in-cab radio follows the map.** M toggles, semicolon and
      apostrophe tune the currently receivable stations, Y speaks status,
      Tab has a Radio screen. (The dial moved off the brackets when
      message review took them for its categories.)
- [x] **The full dial out of the box; one streamer-safe switch
      (2026-08-12, owner ruling).** The former pair -- streamer-safe on
      by default plus a separate real-streams opt-in (an earlier fold in
      the discovery line was reverted with it in `5e3e66a4`) -- is one
      setting again: streamer-safe mode, off by default, hiding real
      streams and personal playlists when on. Terrestrial now sorts
      strongest signal first; power-on retunes a fringe or out-of-range
      memory to the strongest signal; and the radio draws power from the
      engine -- silent in a dead cab, back on its own at ignition, with
      a spoken no-power line on the radio keys. Pre-fold settings files
      keep a deliberately-enabled streamer-safe; only the default
      changed. The manual playtest round
      (`tests/manual_playtest_radio.py`) then caught and fixed three
      more: the dead station's fringe static survived the fade-out
      handover for a reception tick; the Skip on the Far End badge fired
      on any deep-fringe listening instead of a genuine past-the-contour
      catch; and flipping streamer-safe on mid-drive never stopped the
      playing stream (it now hands over to the Roadhouse audibly, via
      the restored `apply_active_radio_settings` plumbing).
- [x] **Hosts, regional stations, and real signal behavior.** The Roadhouse
      and Night Line have live hosts; twelve fictional regional stations
      with newly composed songs cover markets across the map, fading to
      static at the fringe of their range and handing back to the Roadhouse
      when the signal drops.
- [x] **Real local stations across the whole map.** The catalog now carries
      57 real public and community streams (up from 14), filling Portland,
      Boise, Spokane, Salt Lake City, Las Vegas, Reno, Minneapolis,
      Milwaukee, Detroit, St. Louis, Houston, the Ohio Valley, the Northeast
      corridor, the South, Florida, and the southern plains, plus wide
      public-radio networks over the 623-city map's empty country (Prairie
      Public, SDPB, Montana Public Radio, Yellowstone Public Radio, High
      Plains Public Radio, Jefferson Public Radio, Interlochen, Maine
      Public, Vermont Public, WV Public Broadcasting). Each is geo-ranged
      like FM and verified with a live BASS smoke test; a coverage script
      shows 162 of 623 cities still outside every contour, mostly realistic
      radio darkness. The game now bundles and loads the BASSHLS addon
      (`src/freight_fate/lib/`), so HLS-only streams play too (first user:
      KMHD Portland).
- [ ] **AFN 360 Global channels stay unsupported.** StreamTheWorld
      geo-blocks those mounts outside overseas military regions (HTTP 403
      from US IPs on every URL form, HLS included); revisit only if AFN
      opens access. Re-checked 2026-08-04 against a fresh station list from
      a player in Europe: the fourteen Global channels they can play (Hall
      of Fame, Freedom Rock, The Groove, Mach 5, Jazz+, Country, Fans, The
      Blend, Joe, Legacy, Holiday and the Pacific variants) all 403 with
      `x-stw-error: 430 Invalid Mount` from here, on the same edge hosts
      that serve them audio, and the provisioning API reports the station
      keys as 404 from a US connection. Six more (Gravity, PowerTalk,
      Voice, and the Blend/Joe/Legacy Pacific feeds) 404 at the redirect
      endpoint from both continents, so those mounts are simply gone. The
      talk and news channels are all in those two groups -- there is no
      AFN talk station we can carry.
- [x] **Five more AFN Pacific bases (2026-08-04).** Iwakuni, Kunsan,
      Misawa, Okinawa, and Sasebo joined the AFN section from a
      player-supplied station list, each verified streaming from a US
      connection. All twenty-three regional AFN stations moved to the
      canonical StreamTheWorld redirect form, which is the numbered-edge
      auto-repair the 2026-07-27 refresh-tool findings called for, applied
      by hand to the AFN block.
- [x] **Imported broadcast and web tiers from PR #150 (2026-08-07).** 829
      real commercial and independent stations joined the dial under the
      curated catalog, plus a Web radio band of 5,023 internet streams in
      listener-vote order, all converted by `tools/import_radio_catalog.py`
      from the Radio Browser x Wikidata call-sign join CatalystForChaos
      built in PR #150. Curated call signs and stream URLs always win;
      every imported station is a real stream (hidden in streamer-safe
      mode). Terrestrial imports use the source catalog's default per-band
      radius (FM 40 mi, AM 90 mi) with no site elevation, so the terrain
      model's lift term simply stays off for them; the web band sits last
      on the dial, one category jump to skip. The BASS connect also moved
      off the game thread with real timeouts (their pattern), so a dead
      station no longer freezes a frame.
- [x] **Radio favorites (2026-08-07).** O saves or unsaves the current
      station; favorites are dial category 3 ("Favorites"), pulled forward
      from wherever they normally live, receivable rules unchanged. Stored
      on the profile as `radio_favorites` (additive, no migration; PR #150's
      approach). The imported/web tiers made this necessary: the dial is
      six and a half thousand stations now.
- [ ] **Imported-tier follow-ups.** Re-sweep the 371 HLS streams PR #150's
      build dropped (we bundle BASSHLS, so they play here); consider real
      FCC contour radii or curated `range_miles`/`site_elev_ft` overlays
      for high-listener imported stations. `radio_favorites` joins the
      profile shape: regenerate the cloud invariants export at the 1.9
      cutover (already on the cutover checklist). Dead-station manners
      SHIPPED 2026-08-08: a stream that refuses to play hands over to the
      next station on its band and leaves the dial for the session.
- [x] **Community/college/NPR coverage sweep (2026-07-22).** Fifty-one
      real stations joined the dial, each gated on the BASS live check,
      lifting real-station reach from 78% to 93% of the 623 dispatchable
      cities. KPFT (Houston) came back with its Pacifica mount; the Rio
      Grande Valley (UTRGV), Savannah (GPB WSVH), and Amarillo (KACV) are
      on the air; WFMU and KABF joined by name; and public-radio networks
      filled the Iowa corridor, the Plains, the Rockies, the Southeast
      coast, and the Florida panhandle. jpr-redding was repointed to JPR's
      new Zeno mount. Honest remaining gaps at the time: WABE Atlanta (later
      revived in the 2026-07-23 cleanup pass -- see below),
      KDHX St. Louis (defunct on air; 88.1 sold, no successor
      stream yet; market covered by KWMU), WFSU Tallahassee (mount refuses
      BASS), the far Montana Hi-Line, the Texas border west of the Valley,
      and interior US-50 Nevada -- genuinely thin country, left dark rather
      than faked. (Interior Nevada and the Texas border were later lit by the
      2026-07-27 NPR translator dark-corridor sweep -- see below; the truly
      stationless spots, Wells/Austin NV and Malta MT, stay dark.)
- [x] **Montana Hi-Line via translators (owner lead, 2026-07-22) --
      resolved 2026-07-27.** The Hi-Line east of Havre was already lit by
      Yellowstone Public Radio in the catalog (Havre, Glasgow, Wolf Point,
      Glendive, Miles City). The 2026-07-27 sweep confirmed the remaining
      gap honestly: Malta, Chinook, and Saco have no reliable public-radio
      signal (Malta's only in-town FMs are religious and commercial), so
      they stay dark rather than faked. The one real find is KGVA 88.1
      (Aaniiih Nakoda College, Fort Belknap), a full-power tribal NPR
      station that covers the Harlem/Dodson stretch -- carried forward as
      the follow-up in the dark-corridor bullet above (its stream needs a
      Chrome network-sniff to extract).
- [x] **Deadlines respect the hours you already burned -- SHIPPED
      same day (owner question, 2026-07-24).** Dispatch deadlines model HOS honestly for
      a FRESH clock (route-aware driving + breaks + a 10-hour sleep per
      11-hour shift, times 1.2-1.5 slack) -- but never look at the
      driver's CURRENT shift state at acceptance. Accept a one-shift
      load with six hours already used and a mandatory mid-trip sleep
      makes the deadline impossible. Real dispatch asks how many hours
      you have. Fix shape: feed hours-already-used into the deadline
      (or at minimum speak it in the briefing: "with your hours, this
      run includes your 10-hour break"), reusing the fair_active_deadline
      machinery that already does this for resumed saves.
- [x] **Log-check stops stop the truck and burn clock -- SHIPPED same
      day (owner playtest, 2026-07-24).** Root cause found in the log:
      the out-of-service order applied its 10 hours and ledger reset
      instantly while the wheels rolled (3 AM became 1:57 PM between
      two spoken lines). Serious HOS violations now run the real
      pull-over: lights and siren, signal and brake to the shoulder,
      and the ten hours pass parked with the officer's order spoken.
      Original bullet: An enforcement log check
      played its tone and said the driver was stopped -- while the
      truck rolled on unbothered. The stop should be real: truck
      braked to the shoulder, a realistic inspection duration off the
      clock (and off the 14-hour window), then released. Same shape as
      the pull-over flow the speeding rework wants, so build them on
      one mechanism.
- [x] **A non-qualifying sleep says loudly what it did NOT do -- SHIPPED
      same day (owner confusion, 2026-07-24).** Wake message leads with
      "did NOT reset" plus the window-close time; countdown warnings
      re-arm after any non-resetting sleep; the out-of-service stop
      names the blown limits in plain words. Original: A 7-hour berth sleep left the split
      pending and the 14-hour window RUNNING -- but the wake-up message
      buried that in one clause, and the owner drove into a window
      violation believing he had hours left (the "six hours" he heard
      was the deadline clock). Wake from any non-resetting sleep should
      lead with the consequence: "This did not reset your clock. Your
      duty window closes at X; pair 3 more sleeper hours by then or
      stop." And the window-close countdown deserves spoken warnings at
      60 and 30 minutes, like the break countdown already gets.
- [ ] **Violation class decides the roadside outcome (owner ruling,
      2026-07-24).** Caught DRIVING over hours right now: out of
      service on the spot, ten hours -- that is real FMCSA and stays.
      But a logbook ERROR or a past-trip violation found in the record
      (an unpaired shoulder rest from yesterday, form-and-manner)
      should mean the fine and a marked record that raises your
      likelihood of future inspections -- never an instant ten-hour
      hold when you are legal to drive TODAY. Wire the scrutiny
      escalation into the same patrol-frequency machinery the speeding
      rebalance will use.
- [x] **Assigned-dispatch drivers can HEAR the board they cannot pick
      from yet -- SHIPPED same day (owner design, 2026-07-24): an
      on-demand "Review the rest of today's board" option, owner's
      refinement over automatic flavor. Original:** Below level 8 the board shows exactly one assigned
      load, by design -- but the offer pool behind it grows with level
      (5 wide at 1, 6 at 6, more later) and that growth is inaudible.
      Proposal: the assignment board previews the rest of the day's
      pool as locked flavor entries ("Dispatch also posted: ...;
      assigned loads only until level 8"), so each level audibly widens
      the world and level 8 lands as a real payoff instead of a number.
- [ ] **Facility placement audit: 776 approach pins land too far out
      (Josh's Kenosha 35-mile deadhead, 2026-07-24).** The approach bake
      caps at 35 miles and 776 records sit past 8 -- geocoded pins that
      landed counties from their city (worst offenders pinned at exactly
      the cap). Runtime now clamps synthetic approaches to Josh's 1-9
      band as mitigation; the real fix is an agent sweep re-geocoding
      each flagged facility within its city's bounds (OSM name+type
      match, mark unresolvable ones estimated-near-city), then re-bake
      approaches and lift the clamp for genuinely-remote facilities
      that carry evidence. Flag list reproducible: audit script walks
      facility_approach_route for miles > 8.
- [ ] **Real speed limits for facility approach streets (owner ask,
      2026-07-24).** Street-chain legs carry defaults today -- 25 for
      named streets, 15 for unnamed service ways -- but a real arterial
      approach can be posted 35 or 45, and a blanket 25 for miles of it
      is not cool. Bake OSM maxspeed over every facility approach
      route's street legs (same sweep pattern as the corridor and lane
      bakes, self-hosted Overpass, honest absence: keep the current
      defaults only where OSM is untagged). A short 25 or 15 right at
      the gate stays exactly as it is -- that part is true.

- [x] **Real speed limits for facility approach streets (owner ask,
      2026-07-24) -- SHIPPED 2026-07-24.** Every facility approach
      street chain now carries its real OSM `maxspeed` where the road is
      tagged; the 25 (named) / 15 (unnamed) defaults stay only where OSM
      is untagged (honest absence). Read from the local per-state PBF
      cache the facility builder already uses, NOT the self-hosted
      Overpass -- that extract is the corridor extract (motorway..
      tertiary) and carries none of the residential/service streets
      these approaches run on. `tools/build_local_geometry.py` gained a
      maxspeed read threaded through its own osmium graph, so the limit
      comes from the exact way that defines each segment. Labels only: a
      full rebuild changed nothing but `speed_mph` (0 structural diffs
      across all 6,910 targets). 1,457 of 12,820 segments moved off the
      blanket default to a real limit -- 593 to 30, 404 to 35, 245 to
      40/45 -- the mis-blanketed arterials the owner flagged. The short
      25/15 and the 15 mph gate zone right at the dock are untouched.
- [ ] **Reefer rules for the reefer feature (owner spec, 2026-07-24).**
      Two rulings to build into the queued reefer-temp feature: (1) a
      refrigerated load means the engine NEVER shuts down at rests --
      resting keeps it idling and burns idle fuel for the whole stop
      (the game simplifies the separate reefer unit onto the truck
      engine, so engine-on is the cold chain). (2) If the driver shuts
      the engine off with cold cargo aboard: an immediate spoken
      warning, then spoilage as a percentage scaling with how long the
      engine stayed off -- tied into the degree-hours spoilage model
      and its claim path. A driver should never do it; the game should
      let them find out why.
- [ ] **Rebalance speeding toward police encounters (owner design
      question, 2026-07-23).** Today sustained speeding rolls against
      patrol intensity: caught means a real pull-over and ticket;
      NOT caught means a silent "strike" fine at delivery (the
      insurance/safety framing). The owner questions the uncaught
      branch: real life mostly punishes speeding through getting
      caught. Options to weigh: drop or soften the silent fine (shift
      it to a carrier safety score that affects job quality instead of
      cash), raise patrol-encounter frequency to compensate so speeding
      still carries real risk, and keep CB bear reports as the
      counterplay. Ties into Josh's cruise-speeding ding finding --
      whatever survives must never fire while assists hold the limit.
- [ ] **Fine speed adjust: step cruise by 1, not just 5 (owner ask,
      2026-07-23).** Plus and minus move the cruise set speed in 5 mph
      jumps; there is no way to nudge by 1. Add a fine step -- e.g.
      Shift+plus / Shift+minus for 1 mph (and the metric equivalent) --
      for dialing exactly to a posted limit or a curve advisory.
- [ ] **Food and coffee stops are free (owner catch, 2026-07-23, night
      drive).** The short food-and-coffee break at a travel plaza speaks
      its alertness effect but charges nothing -- a real stop costs real
      money. Belongs to the truck-stop economy and buffs pass: price the
      quick stops (coffee, meal, shower outside loyalty credits), charge
      at the register, and let the tiered buffs ride the same purchase.
      The new loyalty program (owner likes it) gives the natural hook:
      paid purchases should earn points too, not just fuel gallons.
- [ ] **Long repeating hiss at highway cruise (owner report 2026-07-23,
      CLAIMED: ff-audio session).** OWNER CORRECTION: not machinery
      engaging -- a GENUINE LONG HISS that repeats at steady cruise.
      Evidence gathered: the sim is innocent (log shows psi pinned at
      125, compressor idle, no brake applications on that stretch) and
      the ring bands measure hiss-flat (no in-loop fill hiss -- the old
      bug is NOT back). Prime suspect: cruise rpm 1695-1767 sits inside
      the narrow midhigh(1425)<->high(1900) crossfade window, so ACC's
      small rpm wobble slides the mix across the seam cyclically.
      A long hiss fading in/out fits the seam IF one band carries a
      hissier steady character than its neighbor (the swing scan only
      rules out WITHIN-loop hiss spikes, not a uniformly hissy band --
      measured means: idle .131, high .144, midhigh .149, mid .155,
      low .159, all in 3-8 kHz ratio). Also re-check the long-hiss
      assets themselves: brake_hiss_bed and air_pressurize triggering
      at cruise despite the gates. Candidate fixes: de-hiss the guilty
      band, widen/recenter the window, damp mix against rpm wobble.
      ALSO for the same session: the brake-release pssht goes missing at
      the final dock stop -- "Brakes set; dock menu opening" fires in the
      same beat and likely cuts the release sound before it plays (owner,
      Merced delivery). The arrival pssht deserves to finish; it is the
      punctuation on the whole drive.
- [x] **Shift transient lands AFTER the band crossfade (owner ear,
      2026-07-24) -- SUPERSEDED by the shift sigh (shipped same day).**
      The gap-then-re-entry hold this bullet defends was replaced at
      the owner's direction: the voice now follows the physics rpm
      falling through the interrupt (ducked -- the real between-gears
      sigh), the start clunk fires the same frame the interrupt begins,
      and engagement got its own soft end clunk. The voice moving
      during the interrupt is now intentional; re-open only if the
      owner still hears the start clunk arriving late.
- [ ] **Quitting at speed should confirm before discarding the leg
      (owner loss, 2026-07-27).** Save-at-stops is the right design,
      but the "this delivery will resume from your last stop" warning
      speaks WHILE the quit executes -- too late to matter. The owner
      quit at 76 mph on I-80 (relaunching for an audio test) and lost
      67 miles back to the trip start. Quit-to-menu while moving should
      ask first, and say the cost in miles: "You will lose 67 miles
      since your last stop. Quit anyway?" Parked quits stay instant.
      Same session, related surprise worth a product look with Josh:
      resuming always starts you parked with the brake set even when
      the save context was mid-corridor -- honest, but it should
      narrate itself ("pulled to the shoulder at your last checkpoint")
      so the stopped truck makes story sense.
- [x] **Randomize sound loop edges (owner + ChatGPT ideas, 2026-07-27,
      SHIPPED same day as the engine-ring wobble).** The suggestions were
      reviewed in the audio session: seam/phase advice was already done
      (WAV + circular splice), and micro-variation won as the cure for
      the fixed-period signature. Each engine band's rate and gain now
      takes a slow bounded random walk (~5 cents / ~0.5 dB, sqrt(dt)
      diffusion in the BASS backend) so the loop period never lands
      where the ear predicted. STILL OPEN if the ear still catches it:
      spectral loop EXTENSION -- regenerate the formant-model cuts at
      4-6 s with continuous harmonics over a fresh-random noise floor,
      shrinking the fingerprint itself; and the dual-loop LCM overlap
      idea stays deferred (doubles the stream count).
- [x] **Ring rebuild: longer spectrally-extended cuts -- SHIPPED
      2026-07-27 (final-slate Track A, owner ear sign-off: "chef's
      kiss").** tools/engine_ring_extend.py resynthesizes each driving
      band FROM its own approved cut at ~5 s: partials detected at
      revolution-rate harmonics (firing lines AND lope sidebands),
      rebuilt as exact circular sinusoids with slow per-octave wander,
      over a fresh-random-phase noise floor shaped by the residual PSD.
      No splice, no seam, no repeating envelope. Measured: envelope
      self-similarity 0.30-0.52 -> 0.10-0.15, chug modulation
      preserved, transients clean. Idle stays the real recording;
      jakes untouched. Rumble-strip synthesis rides Track B.
- [ ] **Lay on the horn (owner ask, 2026-07-23).** H plays one shortish
      horn sample today. Holding H should hold the horn -- attack, a
      seamless sustain loop for as long as the key is down, then the
      release -- like a real air horn lever. Pairs perfectly with the
      horn replacement already owed (the current horn is Duff material):
      when the new Splice/synth horn is cut, cut it AS attack/sustain/
      release pieces so the hold behavior falls out of the asset design.
      NOTE (owner, same night): the horn already sounds SHORTER than it
      used to, but the shipped file is untouched since June -- so the
      audio rework's playback path is probably cutting it early. Check
      the play site before blaming the sample.
- [ ] **Refresh tool: periodic live-check of the whole radio catalog
      (owner, 2026-07-23).** The station search had a first-match-wins
      bug -- one hit per area and it moved on (one station in New York,
      NPR forgotten) -- and the full re-search now running will grow the
      catalog far past what a one-time BASS gate covered. Teach
      tools/refresh_map_data.py's --radio pass to re-test every stream
      on a cadence (streams die: KDHX did), report dead mounts for
      re-pointing, and keep honest-coverage rules: a dead stream goes
      dark or gets a verified replacement, never a fake.
      Two findings from the first full 741-station run (2026-07-27):
      (1) the single-threaded `--radio` pass FALSE-DEATHS on StreamTheWorld
      -- rapid sequential probes get rate-limited, so it must host-partition
      or space same-host hits the way the sweep gate does, else it cries
      wolf; verify any dead list with a serial clean-session re-gate before
      acting. (2) The most common REAL rot is stored StreamTheWorld
      *numbered-edge* URLs (`NNNNN.live.streamtheworld.com/<MOUNT>`) that
      expire; auto-repair could rewrite those to the stable canonical
      `playerservices.streamtheworld.com/api/livestream-redirect/<MOUNT>`
      form and re-gate, healing most deaths without a hand pass. First heal
      pass done by hand (3a81da73): 13 restored, 6 unsupported honestly.
- [ ] **NPR translator/repeater hunt for the remaining dark zones
      (owner leads, 2026-07-27 -- next radio pass, 2.0 line).** The
      Hi-Line pattern generalizes: query the FCC facility database for
      service class FX (FM translator) along each dark corridor; every
      translator record names its PRIMARY station -- resolve to the
      parent network, BASS-verify the parent stream, seat it at the
      translator's dial position. Owner's concrete leads: KQEI-FM 89.3
      Sacramento (KQED repeater -- NPR flagship programming for the
      Sacramento dial) and Winnemucca, likely a KUNR Reno translator --
      which would start lighting the interior I-80 Nevada dark zone.
      Full-power repeaters (like KQEI) surface in the ordinary FM query;
      the FX class search is what catches the low-power translators
      Wikipedia and the first sweeps missed.
- [ ] **Fringe reception should burst, not fade (owner spec, 2026-07-23,
      ham-ear ruling).** Today the edge of a station's range plays static
      at a volume scaled by signal -- a knob, not a radio. Real analog
      fringe is BURSTY: random static bursts of differing lengths at
      differing intervals, each slightly ducking the music (duck window
      0 to a quarter second), with bursts getting louder and the quiet
      gaps between them shorter as the truck drives further out, until
      static wins. Randomize burst length and spacing (seeded, per trip)
      so no two fades sound alike. If a digital/HD station ever joins the
      dial its fringe is different and simpler -- it just drops out --
      but analog static done right is the foundation.
- [x] **Fictional call signs de-squatted (2026-07-22, Josh-approved).** An
      FCC license audit found eleven of the twelve invented regional call
      signs collide with real licensed stations; each was renamed to an
      FCC-unassigned sign with the brand and dial position unchanged. A
      second overnight pass against the FCC LPFM/translator databases (the
      records Wikipedia misses) caught two more squats: the twelfth sign,
      KRWL, is a real LPFM in Coquille, Oregon, and one replacement, KHRM,
      collides with a Nevada station -- both swapped to verified-free signs
      (KRWZ, KHRZ). Josh approved the full list.
- [x] **Full music rotations for the fictional stations.** A 52-track
      Suno-composed batch (via the Zero CLI) grows the format pools to
      radio-scale: country 15 songs, classic rock 17 (including a Saltwake
      tribute, "Greywater Quay"), blues and soul 12,
      ten new Roadhouse daytime instrumentals, four new night beds, and
      two Night Line-only vocal ballads. Second takes of the 24 vocal
      songs are kept outside the repo as auditionable spares.
- [x] **Menu rotation borrows radio instrumentals.** Six curated radio
      instrumentals joined the menu music pools: Steel String Sunday,
      Dobro Dusk, and Glass Highway rotate behind the daytime milestone
      bed; Freight Yard Moon, Midnight Siding, and Low Beams behind the
      night piano theme. Menus stay instrumental (no vocals or host
      breaks) so music never competes with menu speech.
- [x] **Map-refresh utility shipped (v1, report-only) --
      tools/refresh_map_data.py, 2026-07-14.** The owner-run drift
      checker: --radio plays every supported real stream through the
      game's BASS stack and reports the dead; --limits-lint runs the
      anchor-repair judgment rules as a linter (fresh bakes must report
      zero); --stops re-queries OSM per leg (honors OVERPASS_URL) and
      diffs live named truck POIs against baked stops, with a direct
      existence check around each baked stop's own corridor point so a
      sampled miss never reads as a closure. Never writes; exit code 1
      when anything needs attention, so a scheduled run can alert.
      Curation stays with the recipes. Future: fold in landmark and
      interchange drift.
- [x] **Personal playlist stations from M3U files (landed 2026-07-20).**
      Drop `.m3u`/`.m3u8` files into the Playlists folder next to the
      saves (created on first run) and each becomes a dial station under
      Your playlists, named from the `#PLAYLIST` tag or filename.
      Entries resolve relative to the M3U and may point anywhere the OS
      reads, NAS included; playback rides the music channel, so ducking,
      radio volume, and pause-menu continuity all apply, and the bundled
      BASS stack decodes mp3/ogg/opus/flac/aac/alac/wma with no new
      codec work. Unreadable files skip at play time (a sleeping NAS
      must not erase the station); each station remembers its place for
      the drive. A drop-in folder, never a file picker -- screen-reader
      users manage folders in Explorer. Personal media rides the
      streamer-safe gate like real streams. Owner report 2026-08-15:
      stream URLs inside a playlist were dropped, so a playlist exported
      from an internet radio app parsed to nothing and its station never
      reached the dial, silently -- fixed on
      `fix/personal-playlist-streams`. Entries are now file paths or
      stream URLs in the player's own order (a stream plays through the
      same async connect the curated real streams use, with a connect
      hold so it is never skipped for being slow); `.pls` files are read
      alongside `.m3u`/`.m3u8`; loading logs one INFO line per playlist
      and a WARNING for any file that yields nothing; a playlist with
      nothing playable says so instead of falling silent; and opening
      the Radio status screen re-reads the folder mid-drive. Follow-up:
      consider shuffle and a cross-session resume position if playtests
      want them.
- [x] **Radio dial categories with a jump key (landed 2026-07-20).**
      Ctrl+bracket (the owner's binding -- plain brackets already tune)
      leaps to the first station of the previous/next dial category and
      leads with the category name: route playlist, Freight Fate
      stations, your playlists, terrestrial, AFN, satellite. AFN got its
      own category so its 25-station block never buries the local dial
      again; the dial sort and the jump share one grouping.
- [x] **Fictional call signs must not squat real stations (owner catch
      2026-07-20).** Shipped 2026-07-22 -- see "Fictional call signs
      de-squatted" above. KDRT and every other invented sign was audited
      against the FCC database (including the LPFM/translator records) and
      renamed to a verified-free sign; brands and dial positions unchanged.
- [x] **Community and college radio sweep, and an NPR coverage audit
      (owner ask 2026-07-20).** Shipped 2026-07-22 -- see "Community/
      college/NPR coverage sweep" above. WFMU, KABF, college stations, and
      public-radio networks joined via direct station stream URLs with
      source notes, each gated on the BASS live check; real-station reach
      went 78% -> 93% of the 623 cities. Radio Browser was the finding aid
      only; TuneIn stayed out.
- [x] **Streams reconnect themselves; a silent radio never crackles
      (owner catch 2026-07-23).** The Merced ghost hiss: a live stream
      killed by a dock-menu bed (or a network stall) stayed dead --
      nothing restarted real streams, the same-URL guard blocked
      re-tuning the same station, and fringe static bursts fired off
      reception math alone every 6 seconds over a radio making no sound.
      Now the reception tick quietly re-tunes a dead stream (spoken
      fallback if it is truly unreachable), and static only plays under
      an audible program.
- [x] **Terrain-aware FM propagation with honest fringe audio (owner
      approved AND SHIPPED same day, 2026-07-23).** What shipped:
      elevation-aware contours (truck elevation from the leg's samples
      vs station site_elev_ft through the 4/3-earth radio horizon; the
      Rim case is a regression test; below the site is NEUTRAL -- a
      mountain-top transmitter looks down into its valley, so canyon
      shadowing waits for real path profiles, owner-test catch
      2026-07-24), the hiss-bed loop + sharp picket
      splashes replacing the 6-second burst timer entirely, exponential
      inter-arrival around 2v/lambda, program duck to 0.12 per splash,
      frequency_mhz + site_elev_ft on all 12 regional stations, and NO
      fringe over a dead stream. Original design notes kept below;
      follow-ups split into the next bullet. Was: replace the flat
      distance-falloff with
      line-of-sight over the elevation data we already carry: terrain
      profile between truck and tower decides the signal, so a river
      valley drops a station and a ridge crest brings it in.
      Acceptance test from the owner's ham experience: from the
      Mogollon Rim you receive Phoenix AND Flagstaff clearly at
      distances the current radius model would refuse. Fringe audio is
      synthesized, not sampled (FM has no static crashes -- the limiter
      rejects impulse noise): a shaped white-noise hiss bed rising as
      signal thins, blended UNDER the program instead of the current
      6-second burst timer, plus picket-fence flutter RANDOMIZED around
      the physical 2v/lambda rate (owner's ear ruling 2026-07-23: a
      metronomic 18 Hz tremolo sounds fake -- real flutter is a Rayleigh
      fading envelope, irregular nulls whose average rate rides truck
      speed and the station's dial frequency; synthesize as low-passed
      complex noise at the Doppler cutoff, magnitude out). It slows as
      you slow and stops when you park. Stations need a real frequency
      field for that; tune the noise shaping by the owner's ear.
      PICKETS ARE SHARP, not crossfades (owner ear ruling 2026-07-23):
      FM capture is a threshold, so render flutter as the Rayleigh
      envelope GATING program vs hiss with abrupt edges -- brief hiss
      splashes punching through clean audio, never a smooth linear
      fade. Picket density and depth grow as signal thins with
      distance (occasional single pickets at the strong edge,
      machine-gun picketing deep in the fringe, then mostly noise).
      RUNTIME, not baked (owner call 2026-07-23): the flutter depends on
      live speed so the bed must be synthesized in play -- hybrid shape:
      a seamless committed hiss LOOP as the texture with fade depth and
      the Rayleigh envelope computed per-frame as channel gain (the
      engine ring's machinery); fast flutter near 18 Hz gets steppy at
      frame-rate volume updates, so the BASS path likely wants a
      push-stream or DSP callback, degrading to slow wander on pygame.
      The 2026-07-23 static_burst regen (FM demod curve + de-emphasis in
      tools/generate_radio.py) is the interim burst asset AND the
      reference recipe for that loop.
- [ ] **FM propagation follow-ups.** Backfill frequency_mhz and
      site_elev_ft for the ~63 real terrestrial streams (real dial
      facts -- fold into the community-radio sweep; unknown fields
      degrade honestly to the flat model and a mid-band default).
      Later: true path-profile occlusion if off-route terrain data
      ever lands, and a BASS push-stream Rayleigh envelope if the
      one-shot pickets feel too sparse at deep fringe (perceptual cap
      9 per second now).
- [ ] **Tell "still buffering" from "stalled for good" on stream
      startup.** The reconnect loop recreates a silent stream every 9
      seconds; a slow HLS join that needed 10 could get interrupted.
      Poll the BASS stalled/buffering channel state before tearing one
      down.

- [x] **Whole-market completeness sweep (owner ask 2026-07-23).** Shipped
      2026-07-23. The dial no longer carries one station per town but the
      market's full non-commercial roster: public news plus separate
      classical/jazz sisters, community and college stations, and HD2/HD3
      sub-channels (the HD3s are how BBC World Service reaches the dial --
      WUKY, KWGS, KUT, KCND, Vermont Public). 396 real stations added
      (167 -> 563), every one BASS-gated 3x, across all 48 continental
      states + DC. Twelve parallel research agents sourced station-owned
      "listen live" mounts only (no TuneIn/iHeart), with FCC call-sign
      rigor and honest transmitter ranges; darkness stays honest where a
      market has no streamable non-commercial station. Each new entry also
      carries a `state` tag for the future main-menu Radio Player.
- [x] **Always-available international public broadcasters (owner ask
      2026-07-23).** Shipped 2026-07-23 (Phase 0, commit 61e79cbb). New
      "International" dial category carrying 12 English-language public
      streams verified from a US machine: ABC AU (triple j, Jazz, Classic,
      Double J), RTE IE (Radio 1, 2FM, lyric fm), RNZ NZ (National,
      Concert), RFI English, CBC (Radio One, Music). BBC World Service was
      excluded direct (its CDN 403s US IPs) and reaches the dial via US HD3
      sub-channels instead.
- [x] **Radio reading services for blind listeners (owner ask
      2026-07-23).** Shipped 2026-07-23. Twelve reading services (that read
      newspapers/books aloud for blind and print-disabled listeners) now
      ride the dial as real local stations -- WYPL Memphis, WRBH New
      Orleans, Sun Sounds of Arizona, CRIS Chicago, Triangle and Down East
      NC, Sight Into Sound Houston, GPB Reading Radio, WQCS FL, Vision
      Resources PA -- each tagged `reading_service: true`. Most of the
      category (per the IAAIS directory) is SCA-subcarrier only with no
      public stream, so those stay out honestly.
- [x] **Holdout cleanup pass (2026-07-23).** A fresh-session pass that
      cracked JS-locked / no-mount stations the big sweeps had to defer.
      New finding aid: `onlineradiobox.com/json/us/<call>/play` 302-redirects
      to a station's true upstream mount, so Brightspot and other JS players
      give up their stream without a browser. Un-darked WABE Atlanta (its
      StreamTheWorld HD1 mount plays cleanly once STW is not being hammered)
      and added two net-new public markets, KWBU-FM Waco (NPR/Baylor) and
      WLRH Huntsville; corrected VPM Richmond's call sign to WCVE-FM. Four
      more reading services joined the dial -- Iowa (IRIS, Des Moines),
      VOICEcorps (Columbus OH), the Nashville Talking Library, and the WUFT
      Radio Reading Service (Gainesville) -- lifting the category from 12 to
      16. Every stream BASS-gated 3/3 spaced from a clean session; Mississippi
      RRS, Omaha RTBS, and Detroit DRIS stay out honestly (closed-circuit /
      subcarrier / part-time only).
- [x] **NPR translator dark-corridor sweep (2026-07-27).** The map's
      genuinely dark stretches got their first public-radio signal, each
      seated at the real FCC translator or repeater serving the town and
      carrying its parent network's BASS-verified live stream. Interior
      Nevada now catches NPR along Interstate 80 (Winnemucca K217AX, Battle
      Mountain K263AB, Elko KNCC) and US-50 (Eureka K215CM via KUNR; Ely
      KWPR via Nevada Public Radio); the Big Bend of far West Texas picks up
      Marfa Public Radio (Marfa KRTS, Alpine KRTP, Marathon KDKY, Presidio
      KOJP) and Texas Public Radio at Del Rio (KTPD). Translator ranges are
      honestly short, so the signals fade in and out between the mountain
      ranges the way low-power translators really do. Every parent stream was
      re-checked on the BASS live gate three times from a clean session.
      Honestly still dark, no real signal, not faked: Wells and Austin,
      Nevada (US-50's loneliest stretch -- a test asserts Austin stays dark),
      Malta on the Montana Hi-Line (only a religious and a commercial FM in
      town), and Eagle Pass and Van Horn on the Texas border. Follow-up:
      KGVA 88.1, the Aaniiih Nakoda College tribal NPR station, reliably
      covers the dark Harlem/Dodson stretch of the Hi-Line, but its stream
      hides behind a JavaScript player -- a Chrome network-sniff pass could
      add it, and it pairs naturally with the planned tribal-nation crossing
      callouts.
- [x] **Community-radio second sweep (2026-07-27).** The dial skewed heavily
      to NPR and public-radio news (306 public locals vs 129 community), so
      this pass added the volunteer-run and student side. 162 community,
      college, freeform, Pacifica, and tribal stations joined the catalog
      (579 -> 741 stations), each FCC-call-checked and verified on the BASS
      live gate (parallel-gate false deaths re-confirmed serially from a
      clean session before anything was dropped). Twelve states that had
      public radio but no community station are now covered -- New York
      (WBAI, WNYU, WHCR), Wisconsin (WORT, WSUM), Virginia (WTJU, WUVT,
      WDCE), Kentucky (WRFL, WLXU), Vermont (WRUV, WGDR), Indiana (WFHB),
      South Carolina (WUSC), and more -- and the Pacifica flagships (KPFK,
      WBAI, WPFW) and the marquee college freeforms (KALX Berkeley, KDVS
      Davis, KZSU Stanford, WREK Georgia Tech, WXYC Chapel Hill, KVRX
      Austin) are on the air. Honest omissions, not faked: stations that
      stream only through phone apps (Live365, Mixlr, Zeno), internet-only
      outfits with no FCC license, and simulcasts of stations already
      carried were left out (77 such cases logged by the research pass).
      KDHX St. Louis was confirmed defunct (88.1 license reissued) and
      dropped. Follow-up: a handful of real stations whose stream the game's
      audio engine cannot open -- WRAS Atlanta (Georgia State), KNON Dallas,
      KUCI Irvine, WEGL Auburn, KRUI Iowa, plus WRIR Richmond and WVUA
      Tuscaloosa whose mounts would not resolve -- want a Chrome
      network-sniff pass, same as the KGVA follow-up.
- [ ] **Reading Services dial category with a "nearest" jump.** The data +
      tag are in; the feature is a new dial category whose bracket-jump
      tunes the geographically NEAREST reading service (not first-by-call),
      so the most useful content for blind players is always one jump away
      from anywhere on the map.
- [ ] **Main-menu Radio Player (browse-all utility).** A parked-only menu
      to browse and play any catalog station free of range gating, states
      as categories, reading services nested per state, International/AFN
      their own groups. Needs `state` on the RadioStation dataclass +
      backfill on pre-sweep locals. Accessibility-critical spoken menu.
      A `station_type` tag (public / community / college / tribal /
      reading_service / international / afn / regional / built_in / satellite)
      is now baked on every catalog record (data-only, loader ignores it for
      now) -- pre-wiring a browse filter that separates NPR/public from
      community and college. Whether the Radio Player exposes those as
      categories/tabs is a product call raised by the owner (2026-07-27) and
      forwarded to Josh; the in-cab driving dial deliberately stays a single
      scan-what's-in-range band (no genre tabs, matching a real car radio).
- [ ] **Radio cleanup pass: JS-locked holdouts + a real trucking station.**
      Chase the stations the sweep flagged but could not extract a mount
      for -- WABE Atlanta, KWBU Waco, the Richmond/Huntsville public and
      reading stations, ~37 IAAIS "no-mount" services -- via the StreamGuys
      sgplayer3 config.json trick and Chrome network inspection (proved on
      GPB Radio Atlanta 2026-07-23). Also hunt a real free trucking-format
      webcaster to put a genuine trucker station on the dial (SiriusXM Road
      Dog is pay-only/DRM and cannot be tuned).
- [ ] **AM news/talk sweep (next session -- needs fresh web budget).**
      iHeart is tunable via its public revma HLS mounts; Audacy is app-
      locked. Real-first so players lean less on the fictional fallback
      stations. Overnight trucker talk (Red Eye Radio, Coast to Coast AM)
      already rides free AM affiliates in the catalog.
- [ ] **Spotify and Apple Music: research only, parked (owner idea
      2026-07-20).** In-game playback of either is off the table --
      both wrap streams in DRM their licenses forbid unwrapping, official
      playback SDKs are browser or Apple-framework only, and storing a
      login to fetch audio directly would break their terms and put the
      project at legal risk. The honest middle path if ever wanted:
      Spotify Connect remote control (game OAuths, starts the player's
      chosen playlist on their own Premium client, mutes in-game radio) --
      audio would bypass the game mixer, so speech ducking degrades to
      crude API volume nudges. The M3U playlist feature above covers the
      underlying need -- your own library on the dial -- without any of
      this. Rides the online-enhancement determinism boundary if built.
- [ ] **Stream URLs rot fast -- fold a dial health check into the
      map-refresh tool.** One day after the 57-station sweep, seven
      streams were already dead (KJZZ, KCRW, KUNM, KUTX, KERA, KCUR,
      WBUR -- all repointed 2026-07-14 after a full BASS live sweep of
      the catalog). The owner-run map-refresh tool should re-test every
      real stream the same way and report movers, so the dial stays
      honest between releases.
- [x] **The desert Southwest sweep landed: six stations, ten total.** KTNN
      660 AM (Window Rock, the Voice of the Navajo Nation, 175-mile AM
      groundwave contour -- widest in the catalog, honestly), KNAU
      (Flagstaff), KXCI (Tucson), KRWG (Las Cruces), KANW (Albuquerque
      beside KUNM, like the real dial), and KAWC (Yuma), each BASS
      smoke-verified 2026-07-14. StreamTheWorld stations use the stable
      livestream-redirect URLs -- the numbered edge hosts Radio Browser
      caches rotate and die (that is what killed the first KNAU/KRWG/KANW
      attempts). Still dark: Santa Fe and KUAZ Tucson (skipped, KXCI
      covers the market); KTNN pairs naturally with the future
      tribal-nation crossing callouts.

### World and narration

- [x] **Elberton, Georgia added as a granite node (player request, 2026-08-16).**
      A contact-form request from William asked for the "granite capital of
      the world", left off the map. Researched and confirmed: Elberton cuts
      over a third of US monumental granite, ~90 percent of its output being
      cemetery memorials, with named granite carriers based in town. Added as
      a small specialty-origin node (population 4,640, no interstate) with
      seven real curated facilities from the Elberton Granite Association
      directory and the county development authority, plus three legs --
      Athens on GA 72, Augusta on GA 17 through Washington and Thomson, and
      Greenville, South Carolina on GA 17 to I-85 at Lavonia. Ten real
      checkpoints placed, ORS driving-hgv geometry and curve/maxspeed bake
      run. The one claim in the request that does NOT hold: Elberton is not
      why the country has granite at all -- countertop and dimension stone is
      overwhelmingly imported, and Barre Vermont, Texas, Missouri and
      Minnesota all cut monuments independently.
- [ ] **The new Elberton facilities have no baked surface-street approaches.**
      The city-services / facility-endpoint / local-approach / facility-approach
      sweeps predate the node, so its docks fall back to synthetic approaches
      until the next data expansion pass. Same standing gap as every other
      city added since the 2026-07-14 resweep; folded into that job.
- [ ] **Ninety auto-discovered stops are named by bare brand initialisms.**
      36 "TA", 32 "BP", 15 "76", plus CGX, CFN, TXB and a lowercase "bp".
      `AGENTS.md` calls this out by name ("TA" must be "TA Travel Center").
      The spoken form carries the type label in front ("travel center: TA"),
      so it is intelligible today rather than broken -- but the stop schema
      has no spoken override, so fixing it means renaming the stops
      themselves in one sweep across the network.
- [x] **Village and small-town callouts (landed 2026-07-19).** The route now
      names the small places it runs through -- "Entering Strawberry",
      "Passing Kennebunk" -- so a speed limit dropping to 35 in the middle of
      a mountain highway has a town attached to it instead of arriving from
      nowhere. 26,894 real OSM `place=village|town` points across 1,280 legs
      (`tools/bake_villages.py`), each projected onto the leg's real
      OpenRouteService route with its distance off the road recorded. Baked
      wide (12-mile catchment) and displayed tight: the ride-along speaks only
      places within 1.5 miles of the road, 390 of them positioned just ahead
      of the speed zone they explain; the wider set waits for the planned
      "where am I" key, which needs to answer "Winslow, eleven miles ahead".
      No hamlets. Spoken through the Place callouts ladder (below).
      Follow-ups below.
- [x] **Place callouts ladder: one setting for every place name (owner
      design session, 2026-07-20).** The one-day-old village chatter bool and
      the never-built checkpoint sparse mode (2026-07-09 design) collapsed
      into a single three-tier setting, because the split between "curated
      place markers" and "swept villages" is data provenance, not anything a
      player can hear. "Place callouts: off / sparse / all", sparse the
      default: sparse speaks only names that explain a speed limit change
      (probed from the baked corridor limits at trip build, deterministic,
      never from random work zones); all adds the pass-through towns and, on
      worlds that carry them, the curated route markers; the two-mile advance
      cue for places is dead at every tier -- a town is not actionable the way
      an exit is. Limit-explaining villages are seated before spacing thins
      the rest, so Strawberry and Pine both survive their shared window. The
      1.9 world carries zero legacy checkpoint markers (discovered in this
      pass -- the checkpoint speech only ever fires on dev's world), so the
      same code governs both lines with no version awareness.
- [ ] ~~Extract the place-callouts ladder to dev as a small PR.~~
      Investigated 2026-07-22 and deferred: dev's monolith world carries no
      positioned corridor limits, so the sparse tier's limit probe would find
      nothing and the default tier would speak nothing. A faithful port drags
      the dense-limits sweep along -- bulk, not a small PR. Dev gets the
      ladder with the 1.9 world at the release merge.
- [ ] **Village bake: per-leg cap and the wide catchment.** 569 of 1,280 legs
      hit the 30-places-per-leg cap, so their far field (5 to 12 miles off the
      road) is truncated. Harmless for the ride-along, which never reaches
      past 1.5 miles, but the "where am I" key will want the cap raised or
      replaced with a distance-ranked store before it ships.
- [ ] **Villages should carry their own state.** The bake reports counts by
      the state the LEG starts in, not the state the village is in, so a place
      in Washington on a Portland to Seattle leg counts as Oregon. Store the
      real state per record when the orientation readout needs to speak it.
- [ ] **Township and neighbourhood names in the OSM place layer.** OSM tags
      some townships ("Deptford Township") and a few neighbourhoods ("Journal
      Square") as `place=village|town`. They are real names and they read
      aloud correctly, but they are not places a driver arrives at. Worth a
      curated exclusion pass if they grate in play.
- [ ] **Places across a river read as passing.** On the Columbia the route is
      on the Oregon bank and a Washington town can sit under a mile away, so
      it speaks as "Passing Wishram". True, but worth a look in play.
- [x] **Official truck-parking capacity on rest stops (landed 2026-07-17).**
      The FHWA Jason's Law survey (USDOT BTS NTAD Truck Stop Parking, the
      dataset behind the national truck-parking inventory) now annotates
      checked-in stops: 68 stops on 57 legs carry a surveyed
      `parking_spaces` count, spoken with the parking certainty ("confirmed
      truck parking, 45 spaces"), and the overnight parking crunch is
      capacity-aware -- a surveyed 8-spot turnout fills earlier than a
      100-spot travel plaza. Annotation runs offline from a downloaded
      snapshot (`tools/curate_route_pois.py --annotate-parking`), matches
      conservatively (distinctive-name overlap, or same-class public
      facility at the same spot; a branded travel center never inherits a
      nearby public lot's count), and records the source on each stop.
- [x] **Unmatched Jason's Law records offered as fill POIs (landed
      2026-07-17).** `curate_route_pois.py --jasons-law-only` annotates
      first, then offers only the records that matched no checked-in stop
      as new public rest-area POIs on legs under the stop-density
      thresholds (3-mile corridor radius, offline from the local
      snapshot). Netted 2 new surveyed lots (I-90 near Presho SD, I-25
      Mile 129 turnout); 9 under-threshold legs have no surveyed lot
      within reach and keep their coverage gap visible. Survey names are
      whitespace-sanitized and mile-marker jargon is spoken as "Mile";
      one previously committed survey name with an embedded newline
      (Hancock County Welcome Center) was cleaned in the same pass.
- [x] **Posted low-clearance and weight-limit advisories (landed
      2026-07-17).** OSM `maxheight`/`maxweight` tags on mainline corridor
      ways now bake into `corridor.restrictions`
      (`tools/build_interchanges.py --restrictions`, offline from the cached
      per-state extracts), and the GPS speaks them ahead like toll points:
      "In 2 miles, low clearance ahead: posted 13 feet 6 inches." Routing
      already avoids impassable bridges, so these are the advisory signs a
      legal truck really passes; a bearing gate keeps restricted streets
      that cross *over* the highway from baking onto it. An empty baked
      list records a clean sweep, so silent legs are surveyed, not unknown.
- [x] **Destination exit offered a state early on rural-highway finishes --
      FIXED 2026-07-16 (player transcripts).** The destination-exit scan
      accepted the last labeled interchange anywhere on the route, so
      routes whose final legs are unbaked rural highways (US-281 into
      Lampasas, US-2 across the plains to Havre) crowned an exit hundreds
      of miles out -- worst case 1,158 miles, I-39 in Wisconsin for a
      Havre, Montana receiver -- and taking it settled the delivery from
      there. The scan now only accepts exits within the final 25 miles of
      the route and otherwise falls back to the synthetic end-of-route
      exit. Regression test pinned on both transcript routes.
- [ ] Bake labeled exits or junction cues for rural US-highway final
      approaches so arrivals there can name a real exit instead of the
      generic end-of-route fallback (follow-up to the 2026-07-16
      destination-exit fix; needs an OSM junction sweep over non-motorway
      trunk corridors). Scale, measured 2026-07-16 on this branch's data:
      533 of 1,287 legs carry no labeled interchange, and 192 of 623
      cities have none on any approach leg, so every arrival there uses
      the generic fallback. A seeded 2,489-route sample of supported
      routes found 44 percent previously misfired the destination exit
      by more than 25 miles (worst sampled: Payson, Arizona to Newport,
      Oregon, 1,152 miles early on a 1,420-mile route); all of those now
      take the fallback this sweep would upgrade. Regen should run
      offline from the cached PBFs like the overlay pipeline, targeting
      trunk/primary junction nodes on the 533 unlabeled legs.
- [x] **State truck speed limits audited against statute -- FIXED
      2026-07-20 (traced from a player report of "wrong" limits in
      California).** The reported limits were correct -- CVC 22406 caps
      three-axle rigs at 55 statewide -- but the table behind them came
      from a single aggregator and proved wrong on 4 of its 10 rows.
      All 50 states rechecked against statute text
      (`docs/truck-speed-limit-audit.md`): Arizona added at 65 (A.R.S.
      28-709) where it had been MISSING and 33 legs served the 75 car
      number; Oregon corrected 65 -> 55 (ORS 811.111(1)(b)); Idaho
      removed (repealed by H664, effective 2026-07-01); Nevada and North
      Dakota removed (never had a split -- their numbers had been lifted
      from the aggregator's *general* limit column).
      The table is now keyed by **road class** with a `default`, because
      Montana's 70-interstate/65-elsewhere split cannot be written as one
      number, and an explicit `maxspeed:hgv` tag outranks the statewide
      default but is trusted only as far as the statute permits -- that
      is how Oregon's tagged eastern corridors keep their real 65 while
      I-5 stays 55, without a stray 60 mph tag eleven miles inside
      California licensing an illegal speed.
      Deliberately NOT encoded, each for a stated reason: Illinois
      (real, but scoped to six Chicago-area counties and no county data
      is baked), Virginia (real, but secondary-roads-only -- a flat entry
      would cap I-81 at 45), and Arkansas's 50 mph off the
      controlled-access network (live law, but it uses a different
      vehicle test than the 70 provision and contradicts observed posting
      practice; needs ground truth from a driver who runs it).
- [ ] **Arkansas non-freeway truck limit: resolve the 50 mph question.**
      Ark. Code 27-51-201(c)(2) (Act 784 of 2019) reads 50 for trucks
      "in other locations", a 20 mph gap from what the game serves on
      Arkansas US routes. Not encodable from the statute alone -- ask a
      driver who runs Arkansas whether it is enforced.
- [x] **Interstate speed limits polluted by city-street samples at leg
      endpoints -- FIXED 2026-07-14 (found live by the owner on I-10).**
      The maxspeed bake's shield-match guard cannot fire when the
      interstate is outside the 400 m sample box at the mile-0/end city
      anchors, so a city arterial's 25-40 was baked onto the corridor
      and the step function held it for miles (I-10 out of Buckeye
      enforced 30 for ten miles; worst case 25 mph for 73 miles on
      I-84). Repaired offline, no Overpass needed:
      tools/repair_interstate_anchor_limits.py dropped every leading and
      trailing sub-45 sample on interstate legs (430 legs repaired, the
      step function heals back to mile 0), and the bake tool now skips
      shield-less sub-45 readings on interstate corridors so a re-sweep
      cannot reintroduce them. No re-bake needed unless we want denser
      urban 55/65 sampling later. Extended same day to surface highways:
      227 more legs dropped a city-street mile-0 anchor sample owning a
      fast corridor (US-60 out of Phoenix: 25 mph baked for 22 miles of
      the Superstition Freeway), honest small-town limits kept, and
      speeding enforcement gained a braking-grace window after any
      posted-limit drop.
- [x] **Cruise control now cancels on the player's own service brake
      (owner report, FIXED 2026-07-14).** Any service or emergency brake
      input drops cruise immediately and announces "Cruise off" -- the
      first tap of the pedal, like a real truck.
- [x] **Comma repeats the last spoken line, anywhere (owner ask,
      2026-07-14).** One global key re-speaks whatever said last -- menu
      item, readout, or road event -- complementing the driving-only A
      key. Text entry keeps its commas.
- [x] **G speaks the grade and the force verdict (owner ask,
      2026-07-14).** Slope, how far it runs, and whether the truck is
      holding it -- straight from the sim's net-force balance, including
      jake-holding and jake-slipping states.
- [x] **Overspeed dash warning (forum ask via JaceK's I-70 story, owner
      go 2026-07-14).** A few mph over the posted limit arms a spoken
      heads-up and a soft repeating dash chime -- carrier-style, exactly
      what a real company truck does -- quiet while actively braking
      down, disarmed by compliance, Gameplay settings toggle (default
      on). Chime is a deterministic procedurally-synthesized bell strike
      (vehicle/overspeed_chime.ogg, recipe in CREDITS.md). Answers "no
      clue I was speeding until I hit space."
- [ ] **Physics bench: add climb scenarios.** The bench covers descents
      and stops but nothing uphill; the 2026-07-14 climb audit (0-60
      loaded 66-69 s, 6 percent balance 29.8 mph, 3 percent balance
      44.9 -- all inside real envelopes) lived in a scratch script and
      deserves scenario status so regressions get caught.
- [ ] **Phoenix-metro interchange density is thin.** The interchange
      bake took (12 baked on the 40-mile Buckeye-Phoenix leg, speaking
      under the exits verbosity setting) but real I-10 there has 25-plus
      exits; metro legs deserve a densifying pass when the interchange
      bake next runs.
- [ ] **Overlong city-service routes from a bad geometry bake (proven
      in-engine 2026-07-14).** local_geometry.json carries 91 city-service
      chains over 10 miles (max 35.0), all single-segment with
      turn_level=false -- and the local_approaches fallback bakes the same
      broken distance, so the game really builds a 35-mile route at a
      blanket 25 mph to, e.g., the Tyler TX freight market, the Beckley WV
      freight market, and the Mankato MN garage (~80 game-minutes to run
      an errand). Yard/facility approaches are healthy (max 4.0 mi). Root
      cause is the dev-side build_local_geometry.py POI match picking a
      distant candidate and collapsing the failed turn-level route into
      one giant segment. ROOT-CAUSED 2026-07-14: two radii never
      reconciled -- build_city_services matches POIs within 28 crow-flies
      miles while build_local_geometry only routes within 18, so every
      sourced service in the 18-28 band is guaranteed to bake its full
      distance as one 25-mph fallback segment. Full execution spec for
      the re-bake (offline, local PBFs, no Overpass needed) lives in
      docs/rebake-briefs-2026-07-14.md alongside the dense maxspeed
      sweep brief; Opus executes both in a worktree.
      dozens of spider batches grow the map to 375 cities and 626 enriched
      legs -- real corridors across the Great Basin, the Hi-Line, the
      Dakotas, Appalachia, West Texas, and more, each with real roads,
      checkpoints, grades, and truck stops.
- [x] **Stable slug city keys.** Cities key by slug (`abilene_tx_us`) with a
      composed spoken layer, ending display-name collisions as the map grows.
- [x] **Truck-stop POI sweep and rural-diesel fallback.** Every leg now has
      a real or fallback fuel stop.
- [x] **Roadside landmarks and billboards.** 2,835 baked OSM landmarks speak
      as ambient chatter (national forests, named rivers, passes, museums),
      plus corridor-keyed parody billboards; a Settings group adds a master
      Roadside chatter switch with per-kind toggles, and terse verbosity
      mutes it all.
- [x] **Brand amenities at service stops.** Travel-center brands describe
      their real amenity sets in POI offers and rest-stop menus (the
      spoken layer of the amenities/Big Buck's modules).
- [x] **Real US time zones.** The compressed career clock now crosses real
      zone boundaries with spoken zone changes; deadlines read in the
      destination's local time.
- [x] **Service-stop buffs shipped.** Truck stops sell meals, showers, and
      rig care as spoken, clocked buffs: food eases fatigue and slows its
      build, lube bays and tire rotations slow engine and tread wear for
      the trip, brands behave by their real reputations (free shower with
      fuel at Pilot/Flying J, the Iron Skillet at Petro, tire bays at
      Love's/Speedco, road brake jobs at TA/Petro, Big Buck's fixes
      nothing), one buff per group with replacement, and none of it ever
      adds legal driving hours. The Big Buck's purchase-catalog gameplay
      still rides the drive-and-enter stop above.
- [x] **The 1.9 alpha test book.** `docs/alpha-test-book.md`: an
      exhaustive spoken-first delta chapter (everything the alpha changes
      versus the nightly line, system by system) plus setup / do / listen
      for / pass checklists for every non-physics 1.9 system -- wear and
      per-truck condition, truck-stop buffs and brand repairs, lanes and
      exits and ramp lights, congestion, surface streets and city
      services, enforcement and the logbook, pressure modes, the career
      arc, radio, world narration switches, saves and the integrity gate.
      The winter/physics suite stays in
      `docs/physics-playtest-checklists.md` as the companion volume.
- [x] **Scenario playtest levers.** Three environment variables put a
      parked career in position for a scenario without setup driving:
      `FREIGHT_FATE_FORCE_CITY` relocates on career load,
      `FREIGHT_FATE_FORCE_CLOCK` rolls the clock forward to a local hour
      (logged as off duty; a ten-plus-hour wait rests the driver), and
      `FREIGHT_FATE_FORCE_DEST` guarantees the dispatch board offers a
      load to a destination and puts it first in assigned dispatch. All
      spoken plainly, no miles or money moved, refused mid-load;
      documented in the test book Appendix A. The shared-profile event
      ledger must record forced moves when it lands (Josh's server side).
      SANDBOX BY DEFAULT (owner design 2026-07-15, after a lever run
      cost a real career $500): a lever session plays entirely in memory
      -- `save_profile` no-ops for the run, spoken as "Playtest sandbox:
      nothing this session is saved" -- and the career file resumes
      untouched; `FREIGHT_FATE_FORCE_PERSIST=1` opts one run back into
      permanence. Follow-up (shared with the driving school): gate
      online presence and the achievement journal during sandbox
      sessions so a sandboxed run never publishes real-looking events.
- [x] **Overlay re-sweep on the slug world.** The local-approach and
      turn-level geometry builders emit canonical world-key ids, and the
      city-service sweep now covers all 623 cities (1,869 services, 1,076
      turn-level routes) instead of the old 249-city batch. A 10-road-mile
      match cap keeps each city's freight market, garage, and truck dealer a
      real in-town errand rather than a ten-to-thirty-five-mile haul to a
      look-alike business in the next town. Fresh per-state OSM extracts are
      pulled by `tools/fetch_state_extracts.py`; the whole periodic re-bake
      is documented in `docs/refresh-city-service-data.md`.

- [ ] **Periodic macOS boot test (owner ask 2026-07-15).** The speech
      layer already plans for it (AVSpeech is the baked-in macOS event
      voice hint, Speech Dispatcher for Linux), but nobody has proven
      pygame + BASS + Prism boot on a Mac. Owner has a Mac Mini; run the
      smoke suite and a spoken menu walk there occasionally so the
      cross-platform seams stay honest.
- [ ] **Earcon audition pass.** The five 1.9 steering sounds (turn
      left/right/ahead, ramp light red/green) shipped verified by
      measurement, not by ear; regenerate any that sound off via
      `tools/generate_sounds.py` (+ `tools/mirror_turn_chime.py` for the
      right-turn mirror).
- [x] **Learn game sounds.** A catalog screen on the main menu and the pause
      menu: seven categories of road cue, each entry played on demand with
      the canonical name, what it means, and the setting that gates it.
      Ambience, music and self-explanatory sounds are excluded on the record,
      and a completeness test fails any new cue that ships uncatalogued --
      including the ones the game synthesizes at runtime rather than shipping
      as a file.
- [ ] **Sweep the catalog for cues that demo too quietly to hear.** The weigh
      station bed was fixed on its own report (Shane, 2026-08-15): it plays at
      the level the road plays it, which is deliberately low because it works
      by swelling under engine noise, so in a silent menu it read as nothing
      at all. Measuring every catalogued cue over the span the demo actually
      sounds put it at -33 dBFS against a catalog median of -21 -- and it is
      not even the quietest. "The road lean" (-38.5) and "Yawn" (-38.3) are
      lower still and nobody has reported them, so they were deliberately
      left alone rather than tuned blind. Worth listening through the whole
      catalog on headphones and deciding a floor, instead of waiting for each
      one to be reported.

## Shipped in 1.6.0

- [x] Realistic freight markets and facilities: metro route nodes now expand
      into hundreds of representative shippers and receivers, with stable
      facility IDs, ship/receive cargo roles, regional specialization, curated
      source notes, deterministic offline templates, and save-compatible
      facility-aware job generation.
- [x] Playable air-brake pressure mechanics: cold starts need a short air
      build before the parking brake can release, service-brake applications
      consume air, parked engine-off time bleeds reservoir pressure (issue
      #79), low-air and spring-brake thresholds are spoken, and active trip
      saves preserve the air-brake state.
- [x] Dedicated air-system audio assets: the compressor-ready cue now plays a
      real air-dryer purge (`vehicle/air_dryer_purge.ogg`) and the low-air /
      spring-brake warnings a low-air buzzer (`vehicle/low_air_buzzer.ogg`),
      both ElevenLabs-generated; the spoken cues are kept for accessibility.

## Realism and polish pass (1.7.0 shipped, 1.8.0 in flight)

A consolidation pass focused on closing realism gaps and removing rough
edges rather than adding new systems. Much of it shipped in **1.7.0**
(player-feedback UX, dispatcher pay advances, relaxed mode, grounded
hazards, drowsiness, truck-legal HGV routing); the 1.7.0 CHANGELOG is the
source of truth for that release's exact contents. The **1.8.0** batch --
shipped 2026-07-05 -- added the trooper pull-overs,
real OSM `maxspeed` baked per leg, corridor/real speed limits, seasons and a
temperature model, cargo-weight physics, immediate speeding-cost cues, the
S/A/U info keys, the HTML manual, and limit-aware (predictive) adaptive
cruise. Checkboxes below mark what is implemented; which release each lands
in is 1.7.0 or 1.8.0 per the split above. Several items overlap the trooper
milestone below (speeding consequences especially).

### Player feedback round (accessibility/UX)

From a batch of player reports:

- [x] **Map screen read raw data keys for the route -- FIXED 2026-07-21
  (NVDA player report).** Its first line joined the world's city slugs, so an
  east-coast run opened with "new underscore york underscore n y underscore u
  s" for all thirteen cities; every other screen already composed spoken names.
  Same pass singularized spoken measurements ("1 mile", not "1 miles") on one
  shared helper. The reporter's snapshot also predated 36a7f8e, which is why
  the map listed the same shared-city facility twice and pushed real stops off
  the five-item list.
- [ ] Unresolved half of that report: stop lines on the Map screen "make the
  sound but not letting me fully read" under NVDA. Not reproducible from the
  code -- the list is built once, nothing under the menu updates, and no path
  interrupts or drops an utterance. Needs the reporter's `logs/game.log` from a
  snapshot newer than 2026-07-21 to tell "the game never spoke it" from "NVDA
  never spoke it"; packaged builds have always written that transcript, and
  Settings, Problem reports now tells a player where to find it.
- [x] **Destination exit offered a state early on rural-highway finishes --
  FIXED 2026-07-16 (player transcripts).** The destination-exit scan accepted
  the last labeled interchange anywhere on the route, so routes whose final
  legs are unbaked rural highways (US-281 into Lampasas, US-2 across the
  plains to Havre) crowned an exit hundreds of miles out -- worst case 1,158
  miles, I-39 in Wisconsin for a Havre, Montana receiver -- and taking it
  settled the delivery from there. The scan now only accepts exits within the
  final 25 miles of the route and otherwise falls back to the synthetic
  end-of-route exit. Regression test pinned on both transcript routes.
- [ ] Bake labeled exits or junction cues for rural US-highway final
  approaches so arrivals there can name a real exit instead of the generic
  end-of-route fallback (follow-up to the 2026-07-16 destination-exit fix;
  needs an OSM junction sweep over non-motorway trunk corridors). Scale,
  measured 2026-07-16: 533 of 1,287 legs carry no labeled interchange, and
  192 of 623 cities have none on any approach leg, so every arrival there
  uses the generic fallback. A seeded 2,489-route sample of supported routes
  found 44 percent previously misfired the destination exit by more than 25
  miles (worst sampled: Payson, Arizona to Newport, Oregon, 1,152 miles
  early on a 1,420-mile route); all of those now take the fallback this
  sweep would upgrade. Regen should run offline from the cached PBFs like
  the overlay pipeline, targeting trunk/primary junction nodes on the 533
  unlabeled legs.
- [x] **Loading a career cut off its own welcome -- FIXED 2026-08-05.**
  Continue latest career and Choose career spoke "Welcome back" and then
  pushed the city menu, whose own "Parked at..." announcement interrupted and
  cancelled it before a player heard where they were or how much money they
  had. Same defect as the 2026-08-05 orinks.net-offer fix (`8baae687`),
  applied to the load path via `CityMenuState`'s existing one-shot
  `queue_entry_announcement`.
- [ ] Same welcome-truncation defect remains open on two rarer hand-offs out
  of Continue/Choose career: resuming an in-progress pickup (`PickupFacilityState`,
  which still announces with `interrupt=True`) and a pending save notice
  (`SaveMigrationNoticeState` / `SaveModifiedNoticeState`, same default).
  Both would need their own one-shot queue flag, mirroring `CityMenuState`'s;
  left out of the 2026-08-05 fix as lower-value (the lost line is just the
  short "Welcome back, name" greeting, not new information) and higher-risk
  to thread through `_world_entry_state`'s snapshot-resume branches untested.
- [x] **State lines repeated at intermediate cities -- FIXED 2026-07-19
  (player transcript).** Mapped state-boundary cues are now authoritative, so
  passing the next major city no longer claims that the truck crossed the same
  state line again. City narration retains the old crossing wording only as a
  fallback for legacy legs without mapped boundaries. Full harness regressions
  cover Tennessee and Texas routes, reverse travel, and an all-Texas route.
- [x] **Terrain labels read real relief -- LANDED 2026-07-22 (nromey,
  PR #107).** Grade segments were labeled mountain from point steepness alone,
  so a single creek-crossing roller in flat country read as mountains in the
  status readout. Labels are now reclassified from the relief-aware sweep
  computed on the 1.9 line (18,638 false-mountain segments corrected
  network-wide, 166 leg summaries promoted, no curated corridor downgraded).
  Labels only; `avg_grade_pct` and everything physics reads is untouched.
- [ ] Reconcile checkpoint positions with state-boundary positions on seven
  corridor legs. A 24-route forward/reverse harness sweep found 13 places
  spoken on the wrong side of a state line: Fort Oglethorpe on
  Nashville--Atlanta; Peekskill, Newburgh, Kingston, Ravena, Rotterdam, and
  Amsterdam on New York--Buffalo; North East and Conneaut on
  Buffalo--Cleveland; Mesquite on Las Vegas--Salt Lake City; the Longview--
  Portland corridor checkpoint; Ashland on Portland--San Francisco; and
  Vernal on Denver--Salt Lake City. This is a route-data ordering issue, not
  another city-narration composition bug.
- [x] **Quick info keys.** S reads the posted speed limit (was buried in the
  Tab menu); A repeats the last route announcement; U reads what is coming
  up (imposed limits, stops, exits ahead); R answers "where am I" in two
  short sentences -- progress and distance left (to a planned stop when one
  is set), then the road, the state, and the city it is taking you toward.
- [x] **Stop details and planned stops (1.8.x nightly).** Enter on a Map-screen
  stop opens a job-details-style view (exit, distance, offers, parking, and an
  ELD-rule ETA with an arrive-before-your-next-HOS-limit note), with plan /
  cancel / supersede buttons. The planned stop is announced with a "Planned
  stop" prefix at every surface that names stops (5-mile exit announcement,
  U key, C-key next-legal-stop, Map screen), persists in the active-trip
  snapshot, and clears itself when taken or passed.
- [x] **Announcement priority and lead time.** Safety cues (zone entry,
  construction/traffic warnings, checkpoints) preempt ambient chatter on the
  event voice instead of queuing behind it; zone warnings lead by real time
  (scaled by speed and `time_scale`) instead of a flat 2 miles that compressed
  to a few seconds at highway speed.
- [x] **Construction-zone reaction window.** Shipped: construction-zone
  warnings now lead with "Brake now!" and arrive early enough at highway speed
  for normal service braking to reach the work-zone limit. Troopers also wait
  a little farther into the zone before clocking construction speeding, so the
  emergency brake can still save a late reaction.
- [x] **Directional lane-drift rumble.** Shipped: `AudioEngine.play` takes a
  `pan` argument (BASS `BASS_ATTRIB_PAN`, with a stereo-volume fallback for the
  pygame backend), and the lane rumble sets it from `lane.offset` so the strip
  sounds from the side you drifted toward. Follow-up if wanted: pan other
  lateral cues (e.g. a lead vehicle to one side) the same way.
- [x] **Consultable keys reference.** Shipped: the pause menu's "Controls and
  help" opens the navigable how-to-play reference straight to the driving-keys
  page (`controls_help_page()` + `HelpState(start_page=...)`), so the key list
  is reachable mid-drive instead of only the F1 firehose; the keys page now
  lists S/A/U. The manual is also exported to `USER_MANUAL.html` (a small
  dependency-free Markdown->HTML converter, `tools/manual_html.py`) and shipped
  in portable builds beside `USER_MANUAL.md`.
- [x] **Drivers board reachable from the pause menu.** The "Drivers board"
  item now sits in the pause menu (between Settings and Abandon job), so a
  player can see who is hauling mid-drive without quitting to the main menu.
  Viewing shares nothing about the paused driver.
- [x] **Metric units applied consistently.** The units setting converted the
  driving cues but not the dispatch board, job details, pay rate, departure and
  deadhead summaries, exit and hazard callouts, pickup distance, delivery
  summary, career stats, or the on-screen HUD, so a metric player heard
  kilometers on the road and miles everywhere else. All of those now go through
  the shared `units` helpers, and `sim.trip` delegates to them too rather than
  keeping its own copy of the conversion (one of which used a rounded factor)
  (PR #142).
- [ ] **Remaining imperial-only readouts.** Fuel is always gallons and a price
  per gallon, air pressure is always psi, and `weather.describe` omits the
  "Fahrenheit" that `season.py` says, so its temperature reads bare "degrees".
  Adding litres, bar/kPa, and a consistent temperature phrase is a feature
  rather than a units-setting bug, so it wants its own pass on the 1.9 line.
- [x] **Ambient-cue spacing (anti-stacking).** Shipped: priority handling fixes
  the critical case, and low-priority route chatter now has a short spacing
  window with one pending newest cue. Hazards, construction, checkpoints, pull-
  overs, and other safety events still speak immediately, while weather, tolls,
  state lines, CB chatter, and similar ambient lines no longer pile up in one
  burst; actionable GPS distances stay immediate.
- Confirmed-good: routing announcements through the SAPI event voice avoids
  contention with the player's primary screen reader; keep it the recommended
  default and documented.

### Driver economics

- [x] **Negative-balance recovery (softlock fix).** Shipped as a
  **dispatcher pay advance**: from the terminal hub or any in-trip rest
  stop, a broke driver (cash under $400) can draw $500 against the next
  load, capped at $1,500 outstanding, repaid automatically out of the next
  delivery settlement (never below zero, remainder carried). Tracked on
  `Profile.pay_advance`; deterministic and save-compatible. Money still
  goes negative freely for fines/tows by design, but broke-and-empty is no
  longer a dead end.
- [x] **Advances count toward lifetime earnings.** Settlement was crediting
  `total_earnings` with the post-repayment remainder, so advanced dollars
  were cash the career could not account for and cloud upload screening
  refused the save and stamped a sticky integrity flag. Lifetime earnings
  now book the whole settlement.
- [x] **Review integrity flags stamped before that fix.** All five production
  flags were cleared by hand on 2026-07-20. One (a level 2 career, four
  deliveries) was a false positive with no sign of an edit; the other four
  had been confirmed separately by offline forensics and were cleared as a
  deliberate amnesty.
- [x] **Stop screening from branding accounts on arithmetic alone.** A failed
  money or XP check now rejects the upload and keeps the payload for review
  instead of stamping a sticky flag that hid the driver until a human
  cleared it. Flags are still available by hand, from evidence. Both rules
  were wrong in the accusing direction: the XP ceiling was a copied 1.2 per
  mile sitting exactly on what a spotless career earns, and the money check
  priced owned equipment as if it had all been bought.
- [x] **Cloud screening reads the economy from the game.** Starting cash, the
  advance cap, and the XP rates ship in the exported invariants rather than
  being kept by hand on the server, so a balance pass cannot silently turn
  the rules against honest drivers.
- [ ] **Carry the same fixes onto the 1.9 line.** The career arc changes the
  XP model (flat per-delivery XP plus class, streak, and condition
  multipliers) and adds the owner-operator buy-in, where a driver takes
  title to a carrier tractor worth far more than the buy-in. Regenerate the
  exported invariants for save version 11 before 1.9 ships — the server
  gate matches on exact save version, so an un-regenerated export rejects
  every 1.9 backup.

### Fatigue and driver responsibility

- [x] **Drowsiness consequences.** Shipped: at severe fatigue
  (`FATIGUE_SEVERE`, 80+) the driver involuntarily nods off on a shrinking
  interval. Each microsleep plays a rumble-strip jolt with a short reaction
  window; steering or braking catches it (works with steering-assist off),
  but missing it drifts off the road for damage and scrubbed speed, and a
  third consecutive miss forces a stop. Independent of HOS mode (fatigue is
  physiological), so in relaxed mode -- where hazards are rare -- managing
  fatigue, fuel, and rest becomes the core of the drive. Possible follow-up:
  a dedicated microsleep/yawn audio asset instead of reusing the rumble strip.

- [x] **Coffee-break alertness tuning.** Shipped: food-and-coffee stops now
  ease fatigue enough to help you stay alert a little longer, while still
  staying much weaker than a 30-minute break and never satisfying the HOS
  break rule. Remaining balance follow-up: watch playtest feedback around
  night fatigue pacing and the gap between a quick coffee stop, a real break,
  and proper sleep.

- [x] **Relaxed mode should feel relaxed.** Shipped: `Trip` now takes a
  `hazard_scale` and relaxed mode passes `hos.hazard_scale("relaxed")`
  (0.2), so random road hazards are ~5x rarer while weather and night
  still modulate the ones that occur. Driver-responsibility systems
  (hours of service, fueling, repairs, fatigue) carry the relaxed loop;
  `realistic` mode is unchanged. Patrol windows already scale by
  `hazard_scale`; ambient traffic density (`_leg_traffic_density`) and the
  random roadside log-check odds (`_random_inspection_odds`) now do too, so a
  relaxed run is genuinely quieter on the road. Fixed weigh-station and
  construction-zone enforcement stay put -- a real violation still catches you.

- [x] **Grounded, context-aware hazards.** Shipped: the flat per-region
  string pool (which could announce farm equipment merging onto a freeway
  or a dust devil on a clear day) is replaced by a tagged `HAZARDS`
  catalog and `eligible_hazards(region, weather, terrain, hour)`. A hazard
  is only drawn when region, weather, terrain, *and* time of day all allow
  it: standing water/hydroplaning need wet weather; snow squalls, bridge
  ice, and shaded-grade black ice need snow; fog brake-lights need fog;
  crosswind and dust storms need high wind in open regions; rockfall and
  runaway-truck need mountain terrain; deer/elk are dawn/dusk/night-biased
  with regional species. Follow-up ideas: tie hazard *frequency* to
  corridor traffic density and proximity to metros; seasonal weather so
  snow is winter-only; condition animal strikes on rural vs urban miles.

### Driving feel

- [x] **Windows event-voice interruption crash (issue #85).** Urgent road
  alerts now use the speech backend's atomic interrupt-and-speak operation
  instead of issuing a separate SAPI stop immediately beforehand.
- [x] **Fair enforcement after lower speed signs (issues #80 and #87).** A
  driver who releases the accelerator now gets the braking time a loaded truck
  needs before a lower posted limit can produce a speeding strike. Continuing
  on the throttle forfeits the grace.
- [x] **Repeat destination-exit recovery (issues #84 and #90).** Every missed
  destination exit now reroutes the delivery back through a full approach
  window; the second miss can no longer leave the trip pinned at zero miles.
- [x] **Over-rev damage is now audible while it happens.** Sustained redline
  (easiest by backing up fast for a long stretch: the road-coupled RPM pins at
  `max_rpm`) silently ground the truck down 0.8%/s and only surfaced on the
  end screen (issue #62). The driving loop now plays the warning cue and
  speaks the rising damage total, repeating while it persists, with a short
  grace so shift flares stay quiet. Follow-up if wanted: a governor that cuts
  throttle at redline, and a reverse-speed cap, so sustained redline damage
  is hard to reach at all.
- [x] **Don't bind a controller when the controller setting is off.**
  `ControllerManager.__init__` opens the first pad unconditionally; with the
  setting disabled the game still enumerates and binds (issue #61: a fight
  stick got picked up despite controller-off). Gate `_open_first()` and the
  device-added hot-plug path on `enabled`, and open on `set_enabled(True)`.
- [x] **Verify the controller off/on toggle does not double button events.**
  Disabling now quits the SDL controller subsystem and re-enabling calls
  `init()` again mid-session, which the `_reopen()` docstring warns
  re-registers SDL's controller event watch so every event arrives twice
  (PR #67 review). Play-verified with a real pad (2026-07-12): several
  off/on toggle cycles in Settings, then button presses in menus -- no
  doubled events on current pygame, so no follow-up needed. If duplicates
  ever appear after a pygame upgrade, the fix is to make disable only close
  the pad and keep the initialized subsystem alive, reserving `_sdl.quit()`
  for `shutdown()`.
- [x] **Speed-dependent tire pitch and road-seam thumps.** Tire hum pitches
  up and down dynamically with speed on supported audio systems, with a
  distinct sound and controller pulse for road seams (PR #114).
- [x] **Gear / launch realism.** Shipped: gross mass is now
  cargo-weight-aware (tare + payload), so a heavy load accelerates slower,
  lugs on grades, and burns more fuel, and an empty deadhead is light and
  brisk -- the truck mass is no longer a flat 36 t. The low-speed launch now
  ramps into full drive-wheel traction instead of using the full rolling cap at
  a dead stop, and the automatic uses a slightly higher low-gear upshift point
  so a loaded tractor does not rush through the first gears before it is really
  moving. Tests pin the 0-20 mph and highway-speed envelopes so the truck feels
  heavier without turning sluggish.

### Speed limits and speeding

- [x] **Corridor highway speed limits.** Shipped: `speed_limit_at` now
  derives the open-road limit from `corridor_speed_limit(highway, region)`
  -- Interstate vs US highway vs state route, with rural Interstates faster
  out West (e.g. great_basin 80, southern_plains/rockies 75) -- and drops to
  an urban limit within `URBAN_RADIUS_MI` of a city. Changes are spoken as a
  GPS cue, zone-exit restores the corridor limit (not a flat 70), and the
  speeding check is judged against it.

- [x] **Real OSM `maxspeed`.** Shipped and baked: every one of the 438 legs now
  carries a `speed_limits` profile -- a step function of real posted limits from
  OpenStreetMap `maxspeed` (mph, normalized at build time) -- and
  `_corridor_limit_at` prefers it, falling back to `corridor_speed_limit(highway,
  region)` only where a leg has no baked profile. The urban-near-city reduction
  and the spoken limit-change cue are unchanged. The full bake produced 3,113
  samples (227 truck-specific `maxspeed:hgv`), correctly capturing Western 80 mph
  Great Basin stretches, California/Oregon truck-55/60, and Texas 85 mph.
  - Pipeline (local PBF, primary): `tools/build_interchanges.py --maxspeed`
    reuses the interchange reader to stream `maxspeed`/`maxspeed:hgv` off the
    corridor highway ways in local per-state Geofabrik extracts
    (`~/.cache/freight-fate-osm/regions/<state>-latest.osm.pbf`, auto-selected
    from the states each leg touches), snaps them to the checked-in OSRM
    geometry, and bakes a median-smoothed step profile. Its own index cache
    (`*.maxspeed.json`) keeps the interchange cache untouched.
  - Pipeline (Overpass, fallback): `tools/enrich_routes.py --add-maxspeed` does
    the same from the public Overpass API per route point when no local extract
    is available. Both are additive and idempotent.
  - `parse_osm_maxspeed` handles `"55 mph"`, bare `"55"` (assumed mph on the
    US-only map; OSM's km/h default is available via `default_kmh`), metric
    `"90 km/h"`, `"none"`/`"signals"`, and `;`/`,` lists (first general token
    wins). Unparseable -> `None`, so the heuristic stays the backstop.

  **Re-baking:** to refresh after a map change, run `uv run --group tooling
  python tools/build_interchanges.py --maxspeed --force --write` (per-state
  extracts auto-selected; `--only 'From->To'` for one leg). The bake is
  network-free (cached OSRM geometry or local route-point interpolation) and
  idempotent. The heuristic stays the backstop for any future leg OSM has no
  `maxspeed` on.

- [x] **Speeding leeway and consequences.** Shipped: when a strike is recorded
  (`_update_speeding`), the cab now speaks the running speeding-fine total
  immediately ("Speeding strike. The limit is 65. Speeding fines now total 160
  dollars, due at delivery."), and says when the fine has hit its cap, instead
  of the cost only surfacing as a silent settlement deduction. The leeway and
  hold window are now named constants (`SPEEDING_LEEWAY_MPH = 9`,
  `SPEEDING_HOLD_S = 6`) and judged against the leg's real OSM limit. The
  trooper milestone (below) remains the home for *visible, immediate*
  enforcement: getting pulled over and on-the-spot fines.

- [x] **Driving assistance presets and descent control.** Shipped for the current snapshot: Realistic, Balanced, All assists, and Custom coordinate optional lane, emergency-braking, stop-and-go, and interactive descent support without changing inherent adaptive-cruise behavior or simulation settings. Automatic exits, destination stops, yard entry, and docking remain deferred to Career 1.9 or later. On the 1.9 line, lane drift itself lives in the Driving assistance category but stays preset-independent like the speed keeper: presets tune warnings and support, never whether the lane task runs, so fresh careers keep the centered-lane accessible default.
- [ ] **De-duplicate assist chatter on fast ramps.** A 2026-07-15 logged playtest of the four 1.9 assists showed curve speed assistance and route-transition assistance both firing on the same too-fast exit ramp (the ramp adds curve weight, and both brake and announce back-to-back). With the realistic preset both are on by default, so every hot ramp speaks two assist lines; the ramp case should speak one. Same playtest confirmed the destination approach assist deliberately does not cover the ramp-end stop sign -- players can still roll it with the assist on, which may deserve a clearer spoken hint.
- [x] **Speed keeper for low-speed zones.** Shipped: K starts a job-scoped speed-control session that uses the speed keeper on facility roads, in gate queues, work zones, and congestion -- where adaptive cruise is deliberately unavailable -- then automatically hands off to adaptive cruise on the open road, so players who cannot keep the accelerator held (or whose fingers tire) are not locked out of those stretches. It pauses through the planned pickup, persists through pickup saves, and resumes once the loaded truck is rolling. It restores the chosen cruise target across zones, follows queued traffic, and eases to ramp speed when the destination exit is announced before releasing control on the ramp. It fully disarms on other braking or hazards so it cannot restart unexpectedly. Preset-independent and on by default, toggleable in Settings, Gameplay.
- [ ] **Driving assistance presets and descent control.** Built and then withdrawn from the 1.8 nightly line after playtesting (the underlying assists need the 1.9 driving arc around them); the work lives on feat/career-1.9 and ships with 1.9. Release-merge note: the withdrawal was a git revert of merge 9b406fe (plus 9f2dbff and b971684) on dev, so merging feat/career-1.9 back will NOT re-apply this content on its own -- the release merge must first revert the revert commit on dev, then merge.
- [x] **Limit-aware adaptive cruise.** Shipped: once real OSM limits, zones,
  and trooper enforcement landed, plain "hold the set speed" cruise would carry
  the driver straight through an urban drop into strikes and pull-overs. Cruise
  now caps its target at the posted limit plus a small offset
  (`ACC_LIMIT_OFFSET_MPH = 5`, a with-traffic pace under the 9 mph strike
  threshold), brakes gently down to a lower limit, and announces once when it
  eases off. Still follows slower traffic and widens its gap in bad weather.
  Plus and Minus adjust the set point by `CRUISE_STEP_MPH` (the real
  Accel/Coast buttons), so you engage once rolling and dial the target up to the
  speed you want; the truck accelerates up to it, capped by the limit offset.
- [x] **Grade-aware adaptive cruise, and grades you can hear coming.** Shipped
  on the 1.8.x nightly line from a player report: cruise could only add
  throttle, so a downgrade carried the truck fifteen-plus mph past the set
  speed in silence and into a fine. `Truck.hold_throttle` now feed-forwards the
  grade under the wheels and P/I only trims from there; over the target cruise
  takes the engine brake and snubs the drums when that is not enough, holding
  the set speed on grades to eight percent with full air and cool shoes. It
  hands back only the engine brake it switched on itself. Alongside it, a
  spoken advisory for any grade of 3 percent or more lasting at least three
  quarters of a mile (short dips filtered out -- unfiltered, Knoxville to
  Asheville spoke 76 advisories in 116 miles), a once-per-grade line when
  cruise concedes the hill, and the G key for the slope under the wheels, its
  run, the truck's verdict, and the next grade ahead worth planning for --
  including a grade that steepens without flattening first, and the gentler
  pull the speed preview is banking momentum for, which the steep bar alone
  never mentioned.
- [x] **`tools/playtest_road.py`: drop into a chosen piece of road.** Built
  alongside the grade work, because walking the menus to a specific hill takes
  minutes and lands somewhere slightly different every time. Finds a road
  feature by evidence (`--find downgrade|upgrade|zone|limit-drop|stop`, with
  `--scan` to list candidates), then starts the real game already rolling at
  it with the truck, cargo, weather, hour, and cruise set as asked -- or
  `--headless N` for a speed/gear/jake/air trace instead of a window. Searching
  reads the world data alone, so `--scan` never opens a window. Its sibling
  `tools/playtest.py` still drives a whole delivery headlessly for transcripts.
- [ ] Follow-ups the dev line does not have: staged retarder control (dev's
  engine brake is one switch, so cruise holds by cycling it against the
  throttle rather than picking a stage), the predictive read of the grade
  ahead, and a pull downshift for climbs the automatic currently rides out in
  top gear. All three exist on `feat/career-1.9`; the merge takes 1.9's side.

- [x] **Window-model on-time bonus.** Shipped on the 1.8.x nightly line:
  `Job.payout` used to scale its on-time bonus by unused deadline (max 15%
  only for a near-instant delivery, a few percent in practice), which
  rewarded racing the clock and paid almost nothing for normal on-time runs.
  It now pays a flat 10% for any delivery inside the window, the way real
  shipper scorecards (OTIF-style) pay for service; late/damage penalties are
  unchanged. Compared against feat/career-1.9 before landing: 1.9's carrier
  pay plans add their own flat on-time share (2-6% of gross) plus reputation
  trust pay (max 6%) *on top of* gross, and its `Job.payout` is identical to
  dev's, so this reshapes the shared gross curve and merges cleanly; watch
  the combined stack (10% gross + carrier share + trust) when rebalancing
  the 1.9 economy.

- [x] **Tapered dispatch minimums.** The flat $700-1050 pay floors (clamped at
  the level-3 values forever) paid a 50-mile hop ~$23 a mile — four to five
  times any long haul — so grinding short hops was strictly optimal once load
  choice unlocked. `minimum_pay_for_level` now guarantees a short-haul rate
  premium ($4.70-5.50/mi by level, holding to 100 mi) that tapers linearly to
  $3.20-3.50/mi at 600 mi, where the untouched long-haul minimums (levels 4+)
  take over, plus a small $300-350 "worth rolling the truck" floor. Mid/long
  totals stay within a few percent of the old floors; only sub-~200-mi pay
  came down. Landed on dev and feat/career-1.9 together (1.9's
  direct-freight multiplier stacks on top, unchanged). Watch early-career
  cash pacing (rookie sub-150-mi jobs pay ~30-60% less; truck purchase
  timing may shift) when tuning the 1.9 arc.

### Realism north star (ongoing)

The guiding goal for 1.8 and beyond: make every system as true to real
trucking as the 2-D, audio-first design allows, short of a 3-D driving
model. New realism ideas land here, then graduate into a concrete slice
above when picked up. Existing items already serving this goal: grounded
hazards (done), corridor speed limits, gear/launch realism, drowsiness
consequences, and the trooper/enforcement milestone below.

Net-new realism candidates, roughly by area:

- [x] **Weather and seasons.** Shipped: the career clock now yields a day of
  the year and season, and `sim/season.py` models a regional temperature
  (seasonal + daily swing). Temperature reconciles the simulated draw --
  precipitation falls as snow when freezing, snow thaws to rain when warm,
  storms need warmth -- so snow is a cold-season risk and thunderstorms a
  warm-season one, and the weather-gated hazards inherit that automatically
  (winter ice/squalls, summer hail). Seasons are opt-in via `WeatherSystem`'s
  `game_hours` so seed-based tests stay deterministic; real-weather mode keeps
  driving conditions (and thus hazard context) from live data, and with live
  weather on the season follows the real-world calendar by default so it
  matches those conditions. Players can now turn off **Live weather controls
  calendar** to keep live conditions while the career date and seasons
  advance; established careers anchor that independent calendar to today's
  date at the handoff while new careers retain the March 21 start. A seasonal reconciliation guard prevents summer snow and
  cold-season thunderstorms in that mode. Real observation temperature is now extracted too (`_temp_to_c`
  -> `RealWeatherProvider.get_temperature` -> `WeatherSystem._temperature`), so
  live mode reports the station's real degrees and falls back to the climate
  model only when a reading is missing. Weather also bites mechanically now,
  not just as flavor: the per-condition aero `drag_mult` is applied to the
  physics (storms/wind cost top speed and fuel), driving well over the
  conditions-safe speed on a slick road risks a traction-loss incident
  (`_check_conditions_speed`), and low visibility shortens hazard reaction time
  (`_visibility_reaction_factor`). Freezing rain is now its own condition (see
  the 1.9 traction deep-dive above), so glaze ice no longer rides on active
  snow. Live-weather fog is now gated on the station's measured visibility
  (NWS "Fog/Mist"/"Haze" at 6+ miles played as pea-soup fog before).
  Remaining follow-ups: black-ice risk on clear cold mornings after wet
  roads (refreeze after the rain has stopped is still not modeled); steady
  crosswind nudging the trailer; and seasonal daylight length.
  (`_visibility_reaction_factor`). Remaining follow-ups: black-ice risk on clear
  cold mornings after wet roads (currently ice rides on active snow); steady
  crosswind nudging the trailer; and seasonal daylight length. Live-weather fog
  is now gated on the station's measured visibility (NWS "Fog/Mist"/"Haze" at
  6+ miles played as pea-soup fog before).
- [ ] **Live-weather staleness fallback.** If the network drops mid-trip,
  `RealWeatherProvider.unavailable()` still reports a city as available while
  its cache entry is stale (>30 min), so `WeatherSystem.update()` holds the
  last live condition indefinitely instead of falling back to simulated
  weather. Treat a stale-only cache as offline (and consider a spoken note
  when live weather falls back) so conditions can't silently freeze.
- [x] **Per-truck condition tracking.** Every owned truck now keeps its own
  fuel, damage, tire wear, and road grime (save version 5); newly bought
  trucks arrive fueled and fresh, and switching trucks no longer carries or
  loses fuel. Older saves are migrated automatically on load, with a one-time
  spoken notice that the save is no longer readable by older versions.
- [ ] **Teach the server-side validation gate and cloud-save consumers the
  `truck_conditions` shape.** The client invariants and docs are updated for
  save version 5, but the server plausibility rules still describe the flat
  pre-v5 condition fields.
- [x] **Mid-drive quit writes a self-consistent save.** Quit to main menu now
  rolls hours of service and fatigue back to the active-trip checkpoint the
  player will actually resume from, instead of persisting the shift accrued
  since the last stop (PR #146).
- [ ] **Close the same gap on the window-close path.** `App.shutdown()` saves
  the profile unconditionally, so closing the window mid-drive still writes the
  drifted hours of service and fatigue. Resuming re-restores both from the
  active-trip snapshot, so gameplay is unaffected, but the on-disk save and its
  cloud backup disagree with their own checkpoint until then.
- [ ] **Decide whether mid-drive money should roll back too.** Speeding fines
  and roadside fees deduct from the profile as they happen, so a mid-drive quit
  keeps money lost after the last stop while the position, hours, and fatigue
  all rewind to it. Either commit the charge deliberately or restore it with
  the rest of the checkpoint.
- **Physics and the truck.** Cargo-weight-aware gross mass is done for
  acceleration, grade lugging, fuel burn, and now braking: the foundation
  brakes have a fixed force ceiling sized for the rated gross, so loads over
  the rated weight are brake-capacity limited -- they stop longer and heat
  the brakes faster -- while loads at or below the rated gross are unchanged.
  Tire, brake, and engine wear over a truck's life shipped with the 1.9 rig
  wear system (wear accrues from how the truck is driven and feeds grip,
  brake force, fade onset, power, and fuel burn). Remaining: finer
  grade-based fuel burn.
- **Traffic and corridors.** Three slices shipped: rush-hour departure windows
  (morning and afternoon commute) raise modeled traffic density, especially on
  checkpoint/metro corridors, and can slow lead traffic packs with
  commuter/merge callouts. Random road-hazard check spacing now also follows
  corridor busyness: dense metro/checkpoint interstates check sooner, while
  sparse open-country corridors breathe more. Merge/exit pressure now marks
  exit lanes, route merges, construction tapers, and traffic packs with spoken
  gap cues and traffic-specific missed-exit recovery. Remaining: richer
  surrounding-vehicle behavior and multi-lane traffic choices.
- **Hours of service.** Split-sleeper provision and the 60/70-hour cycle
  with 34-hour restart (the HOS model intentionally skips these today).
- **Local delivery realism.** The checked-in map-data foundation now includes
  source-backed city-service POIs for every supported city, nearest-public-road
  local approach context for 2,395 of 2,401 service/facility targets, turn-level
  local street geometry for 412 city-service drives, and source-backed freight
  facility endpoints for 1,462 of 1,819 facilities. A bounded Midwest facility
  approach pass now road-snaps 71 high-confidence source-backed facility
  endpoints from Illinois, Indiana, and Ohio, with 6 long enough to use as
  turn-level playable facility approaches. These layers were built
  offline from the local Geofabrik PBF cache at
  `C:\Users\joshu\.cache\freight-fate-osm\regions\`; runtime remains offline
  and reads checked-in compact JSON only. Remaining: broader facility routing,
  true gate/yard/dock/driveway hints, private-entry validation, and first-drive
  city orientation routes. Player-facing text must continue to hide raw OSM
  IDs, tags, and source keys.
- **Business realism.** The grounded 30-level company-driver to independent
  owner-operator arc is shipped; true-authority depth, trailer polish,
  operating-cost tuning, and market pricing are tracked under Business.
- **Local delivery realism.** The destination-local approach legs already
  sketched under World: surface-street miles, gate speeds, and dock
  approaches after the highway portion.
- **Business realism.** The company-driver→owner-operator arc, loans, and
  insurance already sketched under Business.
- [x] **One message-review system, working on every screen.** The two
  overlapping histories (the app-level speech ring and the driving state's
  message log) are now a single bounded log; every review key -- step, jump to
  oldest/newest, filter by category, copy to clipboard -- is offered to each
  state by the app rather than wired into individual screens (issue #134).
  Remaining: an in-game review screen that lists the history rather than
  stepping through it one message at a time, and a player setting for how many
  messages to keep.
- [x] **National hub network fill (407 → 623 cities).** Audit-driven map
  expansion on the 1.8.x nightly line (community PR #68): every >10,000-pop
  independent city without a bigger neighbor within ~30 miles was built with
  the full enrichment recipe -- 1,287 legs, ~139,000 network miles, real toll
  events on the major turnpikes, and posted speed limits on every leg.

## Local city service drives (built for 1.8, releases with 1.9)

**Amended 2026-08-13:** the drive-to-location flow described below is
retired before 1.9 ships. The truck dealer now opens directly from the
terminal menu (see the 1.9 in-flight bullet above), reusing the same
source-backed `city_services.json` data for its name. Fuel, repairs, rest,
and food stay at truck stops and the terminal garage, as they always did.
The POI/approach/geometry data foundation below is retained for that
naming lookup even though the drivable route itself is gone.

The first ATS-style city-layout foundation is in: from the terminal, **Drive to
city services** lets the player pick the freight market office, terminal
garage, or truck dealer, drive a short local service route, stop at the
destination, and press Enter to go inside. This keeps the current terminal menu
available while moving city services toward a drive-to-location model.

- [x] **Source-backed city service POI foundation.** Every supported city now
  has three checked-in service roles in `city_services.json`: freight/logistics
  office, garage/repair, and truck dealer. The full-map bake used local
  Geofabrik-style state extracts from
  `C:\Users\joshu\.cache\freight-fate-osm\regions\` through
  `tools/build_city_services.py --all-supported`; runtime remains offline. The
  current data covers 194 cities and 582 service roles: 494 roles are
  source-backed from OSM and 88 truck-dealer roles are explicit fallback records
  with machine-readable fallback reasons. Source-backed roles carry coordinates,
  approach mileage, and road/context; fallback roles are not described as real
  POIs.
- [x] **Full-map local approach road context.** `local_approaches.json` is a
  checked-in build-time bake from the same local PBF cache plus world/facility
  data. It covers 2,401 approach targets: all 582 city-service roles have a
  nearest OSM public-road context, and 1,813 of 1,819 freight facility legs have
  nearest OSM public-road context. Six representative facility legs keep
  explicit fallback records because no usable road segment was found within the
  bounded search radius. Facility coordinates are still usually representative,
  so these are local-road approach contexts, not claims about real driveways,
  gates, docks, or companies.
- [x] **Turn-level local geometry subset.** `local_geometry.json` adds a
  source-backed local street sequence where confidence is high. The current
  bake covers all 2,401 service/facility targets with honest metadata: 412 of
  582 city-service drives have turn-level local street geometry from the local
  OSM PBF road graph, 170 city-service drives fall back to nearest-road context,
  and all 1,819 freight-facility records remain estimated fallback geometry
  because their endpoints are still representative metro-market facilities.
  This layer is not ORS `driving-hgv`; ORS HGV already powers corridor/highway
  route metadata where checked in, while this local batch stays rebuildable from
  local OSM extracts without hundreds of live directions calls.
- [x] **Local service driving phase.** City service drives use the existing
  truck physics, GPS/status surfaces, save/resume path, and spoken driving help.
  Arrival does not auto-open the menu: the truck must be fully stopped, then the
  player presses Enter to go inside.
- [x] **Accessible PDA/status wording.** The Tab status screens describe these
  as no-cargo local service drives, not `0 tons` freight loads, and F1/arrival
  prompts name the Enter-to-enter contract.
- [x] **Player/data docs.** The manual and freight-market data notes describe
  source-backed service coverage, explicit fallback behavior, and the rule that
  raw OSM tags, IDs, and source keys stay out of player-facing speech.

Follow-up hooks for the roadmap worker:

- **First-drive orientation route.** A new career can start with a short guided
  city tour that visits the garage, truck dealer, freight market office, and
  terminal services before the first dispatch. Keep it skippable/replayable and
  spoken as GPS guidance, not as a forced tutorial wall.
- **Turn-level local geometry.** Add ORS HGV or OSRM local geometry for
  the remaining sourced approaches so GPS can cue actual turns, lane changes,
  and final pull-ins instead of only source coordinates plus approach
  mileage/context. Runtime should still read checked-in compact data. The next
  routing-quality decision is whether to run a credential-gated ORS HGV local
  batch for selected service endpoints, self-host an HGV router, or keep
  extending the local PBF graph extractor with truck-access tags.
- **Facility-leg realism.** Replace representative freight-facility coordinates
  with sourced shipper/receiver, gate, yard, or driveway points where reliable
  local data supports them. Keep fallback reasons machine-readable and keep raw
  OSM tags, IDs, and source keys out of spoken/menu text.
- **Fallback reduction and data quality.** Keep extending the build-time
  classifier and optional operator-source inputs for the 88 fallback truck
  dealer roles, but do not invent dealers where OSM/operator data is missing.
  Keep bounded local extracts first, and only download the smallest missing
  state extract after reporting the absent path.
- **Enter-to-enter polish.** Add pull-in/park sounds and brief exterior/office
  transition cues when entering and leaving services. Keep the keyboard contract
  simple: stop, Enter to enter, menu action, Back/Escape returns to the truck or
  terminal stack with clear speech.
- **Freight market and trailers.** Trailer ownership/equipment matching belongs
  with a freight-market overhaul, not with the company-to-owner-operator career
  arc. A later slice can let the garage/dealer sell trailers, filter cargo by
  owned trailer capability, and show market sell prices at freight-market
  offices, while the business arc remains focused on driver/company vs
  owner-operator settlement and operating costs.

## Timed facility work and stop-menu settling (built for 1.8, releases with 1.9)

Pickup, loading, destination docking, unloading, and route-stop pull-ins now
feel like short in-game actions instead of instant teleports. Loading and
unloading speak what is happening, advance the career/HOS clocks as on-duty
work, and keep the player in a status screen for a brief real-time wait. Pulling
into pickup gates, destination gates, and route stops adds a short settling
buffer before the menu accepts navigation, so holding Down Arrow to brake does
not skip the first spoken option.

Follow-ups for a later facility/keyboard polish pass:

- [x] Let T open emergency shoulder sleep away from route stops, with one
  complete-stop threshold and an atomic brake-set handoff before menus freeze
  driving physics.

- [x] Offer the engine kill switch inside the pickup and delivery facility
  menus, and charge facility waits idle fuel at the road's rate so shutting
  down is a decision rather than decoration. Departing with the engine off
  names the start-up keys instead of announcing a departure.

- Let the driver set and release the parking brake themselves at a facility.
  Arrival currently parks the truck for them, which is what prompted the
  request (Jake, 2026-08-17); a menu row alone would be inert, so this wants
  the arrival gate to stop handing over an already-parked truck.
- Drive to the terminal after a delivery instead of being narrated there.
  `ArrivalState` settles the load and reports the driver parked at the home
  terminal; the empty-reposition trip type (`_settle_bobtail`) is most of the
  machinery a real post-delivery leg would need.
- Keep the future cargo loading/securing minigame optional and audio-first,
  with a simple timed loading path preserved for players who do not want an
  extra ritual at every dock.
- Give local facility approaches more distinct dock/gate identity: yard road
  names, gate lanes, backing distance, and receiver-specific arrival language.
- If key repeat is ever enabled globally, add an explicit post-transition input
  guard so held braking/navigation keys cannot leak into newly opened menus.

## In-cab logbook, Record of Duty Status (built for 1.8, releases with 1.9)

The game talks about an ELD and the shipped `TrafficStopState` already runs a
spoken "license/logbook check." That now has a real logbook behind it:
`DutyLog` records a rolling Record of Duty Status (RODS) as chronological
driving, on-duty, off-duty, and sleeper-berth segments with timestamps,
locations, and notes. The terminal and driving Tab status menu expose a spoken
Logbook screen, and traffic stops read the recent logbook summary before
resolving the warning or ticket. (The 60/70-hour cycle and 34-hour restart that
a RODS window would unlock are deferred to a later milestone.)

### Design sketch

- [x] **Data model.** A `DutyLog` of ordered `DutySegment`s: status (the existing
  `DUTY_STATUSES` -- driving / on_duty_not_driving / off_duty / sleeper_berth),
  start and end hour on the career clock (`profile.game_hours`), a short location
  string ("I-90 near Toledo", "Chicago terminal"), and an optional note ("fuel
  stop", "out-of-service order").
- [x] **Recording with coalescing.** `drive()` runs every frame, so the log must not
  append a row per tick. `DutyLog.record(status, start_hour, end_hour, location)`
  extends the current segment when status, location, and note match, and only
  opens a new one on an actual transition. A continuous driving stint becomes
  one row, on-ramp to rest stop.
- [x] **Architecture.** Keep `HosClock` pure and pygame-free (the headless tests
  drive it directly). The `DutyLog` lives on the `Profile` alongside `hos`, and
  is recorded from the layer that already knows the absolute clock and place --
  the driving/city/rest code that calls `_advance_rest_clock` and
  `hos.drive/on_duty/off_duty`. `DutyLog` stays unit-testable standalone. Prune
  to a rolling ~8-day window (192 game-hours) to bound save size.
- [x] **Persistence.** Additive `duty_log` field in `Profile.to_dict`/`from_dict`
  with a tolerant load like `HosClock.from_dict`; absent in old saves means an
  empty log. Fully backward compatible.
- [x] **Player surface.** A fully spoken Logbook screen (first-letter nav, consistent
  with the rest of the UI), reachable from the city menu and the driving Tab
  status menu. Shows current status, today's hours-in-each-status grid, the
  running limits the clock already computes, and a chronological list of recent
  segments ("7:00 AM-11:30 AM, driving, 4.5 hrs, I-90 from Chicago"). No new
  global hotkey needed -- C and Tab already cover live HOS.
- [x] **Real enforcement (first slice).** `TrafficStopState`'s logbook check
  reads the recorded RODS instead of only saying it performed a generic
  "license/logbook check." Future enforcement can cite deeper violations such
  as "11.5 hours driving since your last 10-hour reset."

## State troopers and law enforcement

Speeding, HOS/ELD compliance, and route enforcement are now one visible
system instead of unrelated end-of-trip deductions and generic random
inspections. The first shipped slice uses route-backed contexts where the
current corridor data supports them: weigh-station POIs, construction
zones, checkpoints/high-enforcement corridors, and seeded enforcement windows.
Events carry evidence such as HOS/ELD violations or construction-zone
speeding, and serious HOS violations trigger an out-of-service 10-hour
reset instead of only a fine.

- [x] **Speeding pull-overs and CB chatter.** Shipped: routes seed
  `PatrolWindow`s by highway class, region, and time of day (`Trip._place_patrols`
  / `active_patrol_at`), construction zones always hot, scaled down by relaxed
  mode's `hazard_scale`. A sustained speeding strike inside a window rolls
  against patrol intensity (`DrivingState._trooper_catches_speeder`); a hit lights
  you up (`events/police_siren`), you signal with X and brake to a stop, and
  `TrafficStopState` runs a spoken license/logbook check ending in an immediate
  on-the-spot ticket (`SPEEDING_TICKET_FINES`, paid now) or a warning; a prompt,
  fully-compliant stop has a small chance a ticket is waived to a warning. A
  behavior-based compliance tracker (seeded at `PULL_OVER_START_COMPLIANCE`,
  raised by braking, lowered by accelerating/coasting/failing to signal) judges
  the stop -- refusing to comply zeroes it out and is logged as an evasion/felony
  rather than the old distance rule. Disabled in the
  debug HOS bypass. Uncaught speeding still accrues the silent settlement strike.
  CB chatter now warns a few miles before drivers are talking about a bear or
  work-zone enforcement, plays `events/cb_radio_chatter.ogg`, remains
  non-critical so hazards and construction warnings can preempt it, and is
  reviewable with the U upcoming key. Real ElevenLabs audio is in:
  `events/police_siren.ogg` (pull-over),
  `events/spike_strip.ogg` (felony-stop sound on evasion), and
  `events/cb_radio_chatter.ogg` (CB chatter). Regenerate via
  `tools/generate_sounds.py`.
- [x] **Weigh-station bypass and unsafe-equipment stops.** Shipped:
  `DrivingState._check_weigh_station_enforcement` now gives a scale warning
  before open weigh stations, treats highway-speed blow-pasts as a roadside
  enforcement stop, and keeps the developer `debug_off` bypass. Severe visible
  truck damage now draws a safety stop when the truck passes an active patrol
  window. Both use `EnforcementStopState` for spoken reason, prompt-with-X
  pull-over flow, on-the-spot fine, and reputation hit without counting as a
  speeding ticket.
- [x] **Felony failure-to-stop escalation.** Shipped:
  `DrivingState._update_pull_over` now gives a failure-to-stop warning and a
  final warning before spike strips. If the player still keeps driving,
  `FelonyStopState` forces the stop, applies a larger fine, major reputation
  hit, spike-strip truck damage, three hours of enforcement processing time,
  and cancels the active loaded run before returning the player to the city
  terminal. Empty/bobtail runs do not claim a load was lost, and `debug_off`
  remains the internal enforcement bypass.
- [x] **Richer construction enforcement.** Shipped: construction zones now add a
  staged merge/flagger taper before the main work zone. The first cue remains
  action-first ("Brake now!") and tells the player to merge left for the flagger
  taper, slow to the taper limit, then hold the lower work-zone limit. The taper
  is a real speed zone for S/U/status surfaces, while ticket enforcement still
  waits for the main construction zone and its fair braking grace distance.

The ELD/HOS model is grounded in FMCSA's property-carrier summary:
11 hours of driving after 10 consecutive hours off duty, a 14-hour
driving window after coming on duty, a 30-minute break after 8 cumulative
driving hours that may be any non-driving period, and 60/70-hour cycle
rules with 34-hour restart as a future expansion. Primary references:
https://www.fmcsa.dot.gov/regulations/hours-service/summary-hours-service-regulations
and https://www.fmcsa.dot.gov/regulations/hours-of-service. ELD save data
records duty status, time, and route evidence in the spirit of FMCSA's ELD
function guidance: https://www.fmcsa.dot.gov/hours-service/elds/eld-functions-faqs.

### Design sketch

- **Enforcement presence.** Each route leg gets an enforcement intensity from its
  region and highway (urban corridors hot, empty plains cold, construction
  zones always hot), modulated by time of day. The CB radio is the flavor:
  chatter about a bear ahead or enforcement near a work zone gives attentive
  players a vague spoken heads-up a few miles out.
- **Getting pulled over.** Speeding 10+ over inside a patrol's window (or
  blowing past an open weigh station at highway speed) triggers a siren behind you.
  The player must signal with X (reusing the exit system's muscle memory),
  brake to a stop on the shoulder, and sit through a spoken stop: license
  and logbook check, then a ticket, a warning (reputation and demeanor
  matter), or an order to a nearby weigh station for a full inspection.
- **Consequences.** Immediate fines replace the silent at-delivery
  deduction (escalating like HOS fines: 150 to 1,200 dollars), reputation
  hits, and an "out of service" order for serious HOS violations: 10
  hours parked where you stand. Ignoring the siren now escalates through
  spoken failure-to-stop warnings before a felony stop: spike strips, a huge
  fine, truck damage, processing time, and active loaded-run cancellation.
- **Settings.** HOS defaults to realistic and keeps relaxed for
  accessibility and pacing. There is no player-facing non-enforced mode:
  enforcement-off survives only as an internal developer bypass
  (`debug_off`), and legacy 1.5.0 "off" saves now load as realistic. A
  separate law-enforcement setting remains open only if enforcement grows
  beyond HOS and route safety evidence.
- **Audio needed.** Siren approach/behind loops, CB radio squelch and
  chatter, an officer voice channel (the SAPI event voice fits), spike
  strip. Added as Ogg Vorbis assets under
  `src/freight_fate/assets/sounds/`.
- **Open questions.** Do warnings expire after a clean stretch? Does reputation
  lower the ticket odds, or just the fine? Should repeat felony stops affect
  future dispatch availability?

## Shipped in 1.5.0

- [x] Hours-of-service fatigue and mandatory rest planning: 11-hour
      driving and 14-hour duty limits on the in-game clock, a 30-minute
      break rule, spoken countdown warnings, inspections with escalating
      fines, and a realistic / relaxed / off setting
- [x] Rest stop menu (T): refuel, take a 30-minute break, or sleep
      10 hours while the delivery deadline keeps counting
- [x] Fatigue 0-100 with drowsiness audio cues (yawns, rumble strip
      drift) and slower hazard reactions; resets with sleep
- [x] Day/night cycle from the career clock: night ambience and music,
      sparser traffic, higher hazard risk, spoken clock time
- [x] Overnight truck parking that can fill up late in the evening:
      drive on or risk shoulder parking (poor rest, possible fine)

## Shipped in 1.4.0

- [x] Denser, real-corridor map: 59 cities and 106 legs along real US
      interstates, regional freight identity per city, no dead ends,
      full backward compatibility with old saves
- [x] Home terminal picker at career start (fully spoken, grouped by
      region, defaults to Chicago)
- [x] Regional early-career job generation: single-leg neighbor hops at
      low levels, proximity-weighted destinations, cross-country hauls
      unlocking around level 4-5

## Shipped in 1.2.0

- [x] Truck upgrades (engine tune, aerodynamic kit, long-range tank,
      reinforced brakes) and a second purchasable truck (heavy hauler)
- [x] Market fluctuations in cargo rates: per-class multipliers drifting
      daily on a seeded random walk, spoken on the job board
- [x] BASS audio backend (sound_lib) with real-time RPM-tracking engine
      pitch; pygame.mixer kept as an automatic fallback

## Shipped in 1.1.0

- [x] Optional real-world weather per city via the National Weather Service API
      (Settings -> Weather source), with seamless offline fallback

## Shipped in 1.0.0

The core loop from the original roadmap is complete:

```
Browse jobs -> Plan route -> Drive (events, weather, fuel) ->
Deliver -> Earn and level up -> Repeat
```

### Driving mechanics (done)
- [x] Realistic truck physics (torque curve, grades, traction, mass)
- [x] Ten-speed gear shifting: manual with clutch, and automatic
- [x] Fuel consumption with honest mpg and regional diesel prices
- [x] Brake temperature and fade
- [x] Engine damage and wear affecting power
- [x] Stalling, engine braking, traction limits

### Weather system (done)
- [x] Dynamic regional weather with gradual transitions
- [x] Grip, drag, and visibility effects on driving
- [x] Weather forecasting along routes
- [x] Audio ambience per condition, thunder events

### Route planning (done)
- [x] Multiple route options per job (distance, highways, terrain)
- [x] Construction and traffic zones
- [x] Rest stop and fuel stop planning
- [x] ETA and deadline tracking

### Economy and progression (done)
- [x] Pay by distance, cargo class, weight, timeliness, and condition
- [x] Speeding fines, abandonment penalties, roadside rescue costs
- [x] Experience levels and reputation
- [x] License endorsements gating special cargo
- [x] Garage repairs and refueling

### Accessibility (done)
- [x] Screen reader output via Prism (NVDA, JAWS, SAPI, VoiceOver, ...)
- [x] Fully spoken menus with first-letter navigation and F1 help
- [x] On-demand driving information keys
- [x] Speech verbosity settings, imperial/metric units
- [x] Visible text mirror of all speech
- [x] Tutorial and in-game manual

### Technical (done)
- [x] Save/load with atomic writes and multiple profiles
- [x] uv packaging, cross-platform CI, headless test suite
- [x] Fully procedural CC0 sound and music library

## Future ideas (post-1.0)

### Gameplay depth
- [x] Timed loading, unloading, and pull-in settling before facility/stop menus
- [ ] Optional cargo loading/securing minigame
- [x] Hours-of-service fatigue and mandatory rest planning (1.5.0)
- [x] Highway exits: signal with X, move right into the exit lane, slow for the
      ramp, brake to the stop, and get spoken missed-exit recovery when the
      signal, lane, speed, or gore-window setup is wrong
- [x] Cruise control (K), with hazard and braking auto-cancel
- [x] Region-flavored road hazards (dust devils, deer, rockfall, ...)
- [x] HOS-aware realistic deadlines (driving + breaks + sleep + slack)
- [x] In-cab logbook / Record of Duty Status, with the trooper logbook
      check reading real entries
- [ ] State troopers and law enforcement (speeding pull-overs, CB heads-up,
      scale bypass stops, damage-triggered stops, and felony failure-to-stop
      load cancellation shipped; future repeat-offender dispatch hooks remain)
- [ ] Special event jobs (oversize loads, urgent medical freight)
- [ ] Trailer types with handling differences
- [ ] **In-game driving school (owner-approved 2026-07-14; skeleton
      SHIPPED 2026-07-15).** Landed: the Driving school terminal item, the
      sandbox architecture (lessons run the real driving engine on a
      throwaway profile copy -- wear, money, and hours die with the
      lesson; one save_profile guard keeps it off disk; every exit path
      restores the career), the 25-mile flat practice road, and Lesson 1
      "Rolling basics" (engine, air, parking brake, roll to thirty,
      smooth stop) as an instructor riding the first-run tutorial's
      hooks. Remaining below. A CDL-style
      spoken tutorial mode: guided lessons for air brakes, shifting and the
      jake, exits and lanes, chain-up, and hours of service, each teaching
      by doing in a consequence-free practice drive. Solves cold-start
      onboarding for alpha and new players -- today the game teaches via
      How to play, F1 key help, and the test book; every system learned by
      book there is a candidate lesson here. Curriculum effectively drafted
      by the 2026-07-14 learn-by-test-book session (test book Chapter 4
      leads). Pairs naturally with the lease-to-start onramp: school first,
      then the working career. Owner-expanded 2026-07-15: lessons run on a
      simulated practice road (spoken instruction, no career consequences)
      with weather sim and, when the curve tier lands, curve lessons;
      school is enterable from anywhere, any time; buying a truck with new
      equipment (jake stages, assists, a manual box) offers a
      return-to-school refresher on the new bits. Build it as a complete
      presentation for Josh -- done, tested, preset-integrated -- and he
      decides if it ships.
- [ ] **Assists as equipment and skill at the realism tier (owner idea
      2026-07-15, the transmission pattern applied).** At the realistic
      preset, driving assists become what they are in a real cab: truck
      equipment by model year and spec (a new tractor carries AEB and
      lane centering; a lease-starter rig carries nothing) plus trained
      skill from driving school. The Settings presets stay exactly as
      built -- the permanent, free accessibility override that always
      wins, same as the Transmission setting over per-truck gearboxes
      (owner-approved precedent 2026-07-13). Realism players feel the
      equipment; accessibility players keep every accommodation; Josh's
      framework becomes the front door to both layers.
- [x] **Latching controls -- SHIPPED 2026-07-15.** Double-tap-and-hold
      on the pedal keys (tap, press again, hold half a second) latches
      the accelerator or brake hands-free, exactly the owner's gesture
      design: a catch click (ui/tick placeholder until the NAS sound
      pass, distinct from the gear click) plus "Throttle latched.",
      release by a single press of the same key or instantly by the
      opposite pedal, all spoken both ways. Safety semantics as
      designed: hazards (including AEB), the emergency brake, and the
      overspeed alarm outrank a latched accelerator and drop it
      audibly; microsleeps deliberately read the RAW keys, so a latched
      brake never answers a nod-off for you; a latched brake reads as
      held everywhere else (reverse gesture, cruise cancel). Lives in
      Settings, Driving assistance, as "Latching pedals", on by
      default, outside the presets like the speed keeper. Follow-ups:
      swap the catch click for a proper cab sound from the NAS library,
      and the driving-school lesson that teaches latch + jake + brake
      heat together (school-curriculum bullet).
- [ ] **Endorsements earned by coursework, not just cash (owner idea
      2026-07-15).** Today an endorsement is a level threshold or a paid
      course with no learning in it; both should route through the
      driving school as a spoken written-test module -- study material
      read aloud, then a short question set to pass. Hazmat is the
      flagship and does not exist yet: placarding, tunnel restrictions
      (the map already bakes them), segregation rules, plus the real
      TSA-style background wait modeled as game days before it
      activates. Company drivers get courses on the carrier account;
      owner-operators pay their own way.
- [ ] **Endorsement grants must be heard, not missed.** The level-up
      announcement is spoken once inside the delivery-summary chatter
      and is gone; the owner declined a reefer load he was already
      cleared for. The Career stats endorsements line (shipped
      2026-07-15) is the reviewable record; still worth doing: repeat
      the grant on the next terminal entry, and let unlocked
      endorsement jobs on the board name the clearance ("you hold the
      refrigerated endorsement") the first few times.

### World
- [x] More cities and regional highways (1.4.0)
- [x] Day/night cycle with audio shifts (1.5.0); seasons and a regional
      temperature model now shipped too
- [ ] City-specific ambience and landmarks
- [ ] Destination-local facility legs: after the highway trip reaches the
      destination city, hand the player onto a short local approach to the
      receiver gate. Route display and GPS cues should clearly separate
      highway miles from local gate approach, saves should resume on the
      correct leg, and facility data should carry enough road name, distance,
      gate speed, and dock-approach detail to make warehouses, terminals,
      ports, and industrial yards feel distinct.
- [ ] International expansion, beginning with research into Canada and the
      United Kingdom: country profiles need driving side, units, currency,
      local trucking terms, hours-of-service rules, weather fallbacks, legal
      routing, and border-crossing behavior before routes can ship.

### In-cab radio (1.8 / 1.9 candidate)

A truck radio you can tune as you drive: pull in the local FM stations for
wherever you are on the map, with a satellite-style network as the
always-available fallback when you are out of range of anything local. A
community suggestion; the right kind of immersion for long hauls and a natural
fit for an audio-first game.

- [x] **Practical in-cab radio.** Shipped: driving now has keyboard radio
  controls (M toggles, brackets tune, Y speaks status), persistent radio
  enabled/station/volume settings, a dedicated lower radio volume, streamer-safe
  mode on by default, real public streams gated behind explicit opt-in, and
  graceful fallback when a selected station/backend cannot play. The checked-in
  JSON catalog includes safe built-in stations, AFN Pacific, multiple AFN Go
  choices (Freedom, Gravity, Country, The Voice, and Okinawa Eagle), and a curated
  regional public-station subset across the current map. The truck estimates its
  lat/lon from checked-in route geometry and city coordinates, bracket tuning
  walks only the currently receivable stations, and the Tab status menu has a
  Radio screen with signal/fallback/source/volume details. External live streams
  are still metadata-only until a non-blocking stream backend is added; opt-in
  stations fall back safely instead of hanging or crashing. Remaining: FCC-derived
  contour/range refresh, station favorites/presets beyond the review list,
  audible static/signal fades, and actual external stream playback once the
  backend can do it without stealing priority from speech and safety cues.

- **Direction (decided):** use real stations via their public internet stream
  URLs (a friend has a curated list). The game is free and non-commercial, and
  it acts as a *tuner* -- it points the player's own client at a stream the
  station already broadcasts publicly, not hosting or rebroadcasting audio
  (the TuneIn / car-head-unit model). Free and non-commercial is not a blanket
  copyright exemption, but the tuner-to-public-stream posture plus no money
  changing hands keeps practical risk low for a small game.

- **Streamer-safe toggle still required.** Independent of the game's own
  posture: a player who streams a session to YouTube/Twitch with copyrighted
  station audio can still get the VOD struck. So real-stream radio stays an
  explicit toggle (and a "mute radio for streaming" switch), with an owned
  royalty-free station and the satellite fallback as the always-safe default
  audio, so streamers are protected unless they opt in.

- **Geography-gated reception.** Stations are data, not magic: a JSON catalog
  per station with call sign, format/genre, public stream URL and its audio
  format (so the loader can skip unsupported transports), transmitter
  latitude/longitude, ERP (effective radiated power), and antenna HAAT, plus a
  derived `range_miles`. Range is estimated from public FCC license data (FM Query /
  LMS) using the F(50,50) protected-contour idea -- power and antenna height,
  refined by terrain -- so you can only pull in stations whose coverage
  actually reaches you. The truck's geo-position is interpolated in
  latitude/longitude along the current route leg (cities already carry
  lat/lon), signal strength falls off toward the edge of a station's contour,
  and reception fades into static and drops out as you leave range -- then the
  next town's stations fade in.

- **Satellite fallback: AFN.** An always-available station for when no local
  FM is in range -- AFN (American Forces Network), which has exactly the right
  always-on, ad-free, slightly-institutional vibe. AFN's *overseas over-the-air
  and decoder-box* broadcasts are encrypted, but its internet radio (AFN 360)
  is publicly streamable to anyone, so it can be used directly. Public stream
  URL (Triton/StreamTheWorld, AFN Pacific):
  `https://playerservices.streamtheworld.com/api/livestream-redirect/AFNP_OKN_SC`.
  AFN is ad-free and U.S. government-produced, but the music it airs is still
  commercially licensed, so the streamer-safe toggle still applies to it. This
  is the one station that is always in range, so it doubles as the graceful
  fallback when a local stream rots or drops out.

- **Audio sourcing: real streams, with the real work being technical not
  legal.** The friend's stream-URL list is the primary source. The gotchas to
  build around: (1) streams rot -- URLs change and stations go dark, so
  reception must fail gracefully and fall back to the satellite/owned station,
  never dead air or a crash; (2) codec/transport -- the BASS/sound_lib backend
  handles Icecast/Shoutcast MP3/AAC easily, but HLS (`.m3u8`) needs more work,
  so the catalog should record stream format and the loader should skip
  unsupported ones; (3) some stations geo-block or require their own app, so a
  few URLs won't work for a third-party player and the catalog needs a
  reachable/working flag. Keep an owned royalty-free station and the satellite
  fallback for offline play and the streamer-safe default.

- **Accessibility is the feature, not a checkbox.** Tuning must be fully
  spoken and keyboard-driven: seek/scan up and down the dial, announce call
  sign + format + signal strength, audibly fade as you move in and out of
  range, a station list and favorites, and a dedicated radio volume in
  Settings. This is core UX for the game's audience, designed in from the
  start.

- **Ties to existing systems.** Reuses regions and city lat/lon, the music
  backend, and the day/night + seasons clock (programming could shift by time
  of day or season). Open questions: ship the full FCC-derived dataset or a
  curated subset; how granular the range/terrain model needs to be; and
  per-genre licensing for any owned music library.

### Business
- [x] Company-driver to owner-operator career arc. Full first arc: choose among
      grounded fictional company-driver starter carriers with
      carrier-assigned equipment, carrier-paid fuel/repairs, and different
      wage, dispatch, route-mix, and freight tradeoffs; progress through 30
      ranks; then unlock a
      level-18 leased-on owner-operator path with a buy-in,
      working-capital gate, owned-tractor garage access, higher gross revenue,
      and operating-cost deductions. A higher-risk owner-operator start is also
      available for experienced-driver fantasy play. Level-21
      owner-operators can now set aside an authority prep reserve, then unlock
      a limited level-25 own-authority direct-freight mode once the final gates
      are met. Levels 26-30 add established independent owner-operator ranks.
      Loans, full paperwork simulation, and fleet ownership remain future work.
- [x] Trailer program and cargo compatibility slice. Cargo now maps to dry van,
      reefer, flatbed, or bulk trailer programs. Company drivers keep
      carrier-provided trailers. Leased-on owner-operators start with dry van
      access and can add specialty trailer programs from the garage; missing
      programs lock matching loads with clear dispatch-board text.
- [x] Own-authority trailer ownership slice. Own-authority drivers can buy dry
      van, reefer, flatbed, and bulk trailers from the garage. Matching direct
      freight rows say when an owned trailer fits, and settlement uses a smaller
      owned-trailer reserve instead of the trailer-program charge.
- [x] Trailer-fit dispatch preview slice. Dispatch rows now mark trailer-setup
      locks before the player accepts a load and show an estimated driver pay
      or take-home preview based on the current carrier, business status, and
      owned/program trailer setup. This is a readable offer preview, not a full
      spot-market or resale model.
- [x] True authority and direct freight first slice. Prepared owner-operators
      can activate own authority from Business status after delivery,
      reputation, cash, trailer-program, and advance-clearance gates. Dispatch
      then marks loads as direct freight with higher gross revenue, and
      settlement adds insurance, compliance, trailer, truck, and factoring
      overhead. This is not a full DOT/MC paperwork or broker contract sim.
- [ ] Advanced authority realism. Build on the current own-authority state with
      richer insurance filings, DOT/MC application timing, broker/load-board
      access tiers, factoring or delayed settlement choices, and clearer
      compliance overhead.
- [ ] Advanced trailer ownership and leasing. Build on the current owned
      trailer model with condition, financing, resale, tanker cargo, washout,
      and richer authority-specific cargo-fit choices.
- [ ] Operating-cost polish. Continue tuning owner-operator deductions against
      real cost categories such as fuel, maintenance reserve, insurance, truck
      payment, trailer program, and settlement/factoring fees, while keeping
      settlement speech short and understandable.
- [ ] Freight-market pricing realism. Continue separating company-driver wages,
      leased-on gross revenue, and own-authority spot or broker rates; expand
      direct freight board comparisons with better lane-rate inputs, fuel
      estimates, and trailer condition once those systems exist.
- [ ] Business realism caveats. Keep lease-purchase risk visible as caution,
      not the golden path. Avoid payday-loan-like traps, and keep fleet hiring
      separate from the driving-career loop.
- [ ] Equipment model polish. Legacy profile fields still preserve `truck` and
      `owned_trucks` for save compatibility, but company-driver UI hides them
      behind assigned-equipment helpers. A future schema pass can rename those
      internals once older saves have a migration path.
- [ ] Company ownership: hire AI drivers, buy trucks
- [ ] Loans and insurance

### Platforms and community
- [x] Binary releases (Nuitka) per platform
- [ ] Steam/itch.io distribution
- [ ] Localization of all speech strings
- [ ] Optional online leaderboards
- [x] Opt-in Profile sharing for fictional road journals, achievements, and last-saved profile summaries
- [x] Online posts carry the game's build identity (release tag or source checkout) so moderation can tell which version a driver runs
- [x] Validated and server-signed private cloud revisions with verified public profile summaries
- [ ] Richer verified driver profiles: identity headline (level title, business
      status, carrier, rig), a rates-first resume (lifetime deliveries and
      miles, on-time and damage-free percentages with a minimum-deliveries
      floor, clean-inspections-vs-citations safety record), traveler stats
      (states and cities visited, longest haul), the two or three most recent
      badges, and net worth (cash plus equipment) labeled by business status.
      One fact per spoken line, identity first; keep XP, fatigue, HOS state,
      and dispatcher standing private.
- [x] Profile integrity, client half: `profile_invariants.py` runs the hard, version-stable sanity rules (ranges, counter relations, upgrade tiers) as defense in depth behind the Ed25519 signature on every cloud restore, refusing with a plain spoken reason; `docs/profile-invariants.md` is the maintained validation list for the server gate. Follow-up: the append-only event ledger that upgrades server validation from plausibility to recomputation
- [x] Packed save container: careers live in signed `.ffsave` files (magic header + deflated JSON) that text editors cannot open; legacy plain-JSON saves convert on load with a `.json.bak` rollback copy. A failed local signature now marks the profile `integrity_modified` (sticky, signed-in, spoken once) instead of quarantining — local play continues, shared features read the mark. `tools/dump_save.py` prints the JSON inside a save for bug reports.
- [ ] Retire legacy plain-JSON save loading (and its unsigned amnesty) once converted installs are the norm — one or two releases after the container ships; the amnesty is the last casual editing door
- [ ] Ship a stable release carrying the packed save container, so players are not split across two save formats. Until one exists, a career backed up from a developer snapshot cannot be restored onto 1.8.3: the snapshot writes the newer format, and the stable build drops the fields it does not recognise. Moving forward (stable career onto a snapshot) is fine. Fixing the backwards direction in the client was considered and deliberately declined — too many edge cases for the value; the stable release is the fix. Told players so on issue #97, without naming a date.
- [x] Cloud backup accepts every shipped save shape, not just the newest build's: the orinks.net validator matches uploads against a superset allow-list and a supported version range, and only requires the fields it actually reads. It had demanded an exact match with whichever build the invariants export was last generated from, which refused newer and older saves in turn — most recently every save from 1.8.3, the stable release, leaving those players unable to back up at all (issue #97)
- [ ] Server absolution for `integrity_modified`: a profile that passes full server validation may have the client mark cleared on the next verified restore, so honest cross-machine movers are not marked forever (`docs/server-integrity-handoff.md`)
- [x] Driver token in the platform secret store: the secret half of the online credentials goes to Windows Credential Manager, the macOS Keychain, or Secret Service/KWallet on Linux via `keyring`, leaving only the public Driver ID in `online.json`. Tokens written by earlier builds migrate on the next load, with no re-paste. A machine with no working store (headless Linux) falls back to an owner-only `online.token` opened at 0600 (community PR #133, reworked cross-platform)
- [ ] Sign out from inside the game: there is no way to unlink a computer from the game side, so the stored token outlives an uninstall. Needs a Cloud/Online menu action that clears `online.json`, the secret-store entry, and any fallback token file, plus the corresponding revoke on the orinks.net computer list
- [x] Per-computer driver tokens on orinks.net: each computer gets its own token from a named, revocable computer list on the driver setup page, so connecting a second computer no longer retires the first one's sign-in (issue #64; game-side reconnect guidance points at the computer list)
- [x] Copy the delivery summary to the clipboard from the delivery complete screen (verified by read-back before the game says "copied")
- [x] Delete a career's cloud backups from the Cloud backup menu: a confirmed, safe-default-first delete removes every kept revision from the account (server DELETE route + existing `deleteSaveSlot` mutation); local saves untouched, sync state forgotten so a still-local career starts a fresh slot on its next save
- [x] Choose the public career from the Cloud backup menu: one designated career fronts the public profile (`publicSaveName` on the driver row, spoken "your public career" in the backup list, confirmed switch per career), and every other career stays a private cloud backup -- ending mixed public stats when several careers back up. Accounts that never choose keep the old first-uploaded-owns rule; the empty-cloud sticky conflict that silently stopped backups after a server-side wipe or remote delete heals itself on the next save
- [x] Opt-in Mastodon sharing of notable deliveries: the player links their own Mastodon account on orinks.net (any instance, dynamic app registration, `read:accounts write:statuses` scope), and the game offers deliveries that earned an achievement, level, or streak milestone; the server composes the public post from allowlisted facts and adds the #FreightFateRuns hashtag (deliberately not the bare #FreightFate, which players use for their own posts -- muting the bot must not mute the conversation). Off by default, separate consent from Profile sharing, durable outbox client-side
- [ ] Mastodon sharing follow-ups: unlink from inside the game (today the orinks.net page is the only unlink), and consider per-post visibility choice (public vs unlisted) if players ask
- [x] Activation-code setup replaces clipboard-paste credentials: connecting
      a computer to orinks.net now shows a short activation code (spoken,
      spellable phonetically, and copyable to the clipboard) instead of
      requiring a Driver ID and token to be copied from the website and
      pasted into the game; the game polls and finishes connecting on its
      own once the code is confirmed in the browser (`online_activation.py`,
      device-code exchange already live on orinks.net)
- [x] First-career onboarding offer: creating a first career now offers,
      once, to connect the computer to an orinks.net account -- right after
      "Welcome aboard" and before the dispatch board (`states/online_offer.py`,
      gated by the per-install `Settings.online_offer_seen`, never asked again
      once seen or once a computer is already connected). Declining (or
      Escape, which behaves the same) and accepting both continue straight
      into the city menu either way. The offer says exactly what connecting
      does, which since the change below is turn Profile sharing and cloud
      backup on.
- [x] Connecting an orinks.net account turns Profile sharing and cloud backup
      on, instead of leaving both off behind their own separate yes: the
      public career statistics are derived from the latest accepted backup,
      so a connected account with neither switched on left every new driver
      staring at a profile that read "no career statistics yet". Cloud backup
      needs no handshake and starts immediately; Profile sharing waits on the
      server confirming it, exactly as the standalone toggle does, and a
      refusal keeps the connection and names the retry rather than sending
      the player back for a fresh activation code. Setup disclosure, the
      first-run offer, the Online menu help, and the manual all say so up
      front. Players already connected are untouched -- nothing they left off
      turns itself on at upgrade.
- [x] Idle drivers age off the live board: a truck parked with the game left running (not paused) signs off after 30 minutes without a snapshot change and stops heartbeating (`online_presence.py` IDLE_SIGNOFF_S); the server hides still-beating idle rows on the same clock for older builds (orinks-net `PRESENCE_IDLE_MS` + per-row `changedAt`), and deadhead presence now carries progress so a long empty run never reads as idle
- [x] Online hub: the drivers board, orinks.net account, cloud backup and restore, and all sharing toggles moved from Settings into one Online menu on the main menu (`states/online_hub.py`); Settings keeps an Online pointer that opens the same menu for a release or two
- [ ] Remove the Settings Online pointer once players have had a release or two to relearn the location
- [ ] 1.9.0 release-notes credit sweep: nromey's Unreleased bullets (engine audio arc, physics realism, playlists, place callouts, speed-limit audits, signature v3) carry no "Thanks to" attribution yet -- credit them with the PR link when the 1.9.0 notes are cut, per the contributor-credit rule in AGENTS.md
- [x] The drivers-board progress percent is readable in-game: the R route report leads with "N percent there" (`Trip.progress_percent`, same position/total figure presence posts) and the Tab status menu carries a Progress line; deadhead drives included
- [x] Braille-friendly driving readouts: the on-demand C, R, V, and F reports front-load the answer so the first line of a one-line braille display carries it (displays are 14 to 80 cells, commonly 40, and screen readers flash game speech one line at a time); terse speech additionally trims the C report to time, verdict, and hours of service
- [ ] Braille pass over the remaining spoken surfaces (event announcements, menus, arrival and settlement summaries): same front-loading rule, and check flash-message length against a 40-cell display
