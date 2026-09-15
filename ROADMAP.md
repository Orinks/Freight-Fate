# Freight Fate Roadmap

> **RELEASE SCOPE (amended 2026-07-27, owner + Josh):** the 1.9 line
> takes FIXES plus exactly the final slate Josh named -- (1) the easy
> multilane slice (wiring the already-baked lane counts into speech),
> (2) curve navigation with steering, (3) rumble strips (one system
> with curve nav), (4) the engine-ring spectra rebuild, and (5) the
> NPR translator radio batch. Nothing else: every other unchecked
> FEATURE bullet below targets the `feat/career-2.0` line, except the
> explicitly scoped 1.10 work below (2.0 worktree
> `.claude/worktrees/career-2.0`, created 2026-08-18; the `C:/dev/ff-2.0`
> path this note used to name never existed). The driving school stays
> gated off 1.9 (`DRIVING_SCHOOL_ENABLED`) and reopens on 2.0 to be
> finished.
> Track plan: `docs/plan-1.9-final-slate.md`.

> On September 11, the owner approved five corrections to existing 1.9 systems:
> commercial bobtail duty, braking estimates, component service limits, fuel
> weight, and reachable HOS rest stops. The weekly HOS cycle and full personal
> conveyance controls remain in the 1.10 plan.

> Current stable: **1.8.8.1** (hotfix shipped 2026-08-08). Next release: **1.9.0**, in
> flight on the `feat/career-1.9` branch -- driving realism between the exits
> (discrete lanes, ramp terminals, congestion, real surface streets) plus the
> highway-spider world expansion, roadside narration, and real time zones.
> `pyproject` is set to 1.9.0 so developer snapshots report it; the stable tag
> follows at release. Keep this file current: when a feature lands on the 1.9
> line, check it off here in the same change.

## Reading this roadmap

Start with the [1.9 release gate](#release-gate----what-stands-between-here-and-a-public-190),
including its cutover checklist, remaining bugs, and owner decisions.
The [1.10 plan](#110-planned----the-working-week-and-home) follows it.
The [detailed roadmap](docs/roadmap-details.md) preserves the implementation
record and full pending backlog. Section links below keep existing roadmap
bookmarks usable.

## 1.9 in flight (`feat/career-1.9`)

- [x] Keep traffic light approaches and changes brief: Light red, Light yellow,
      Light green; retain the distance countdown without "to the bar."

- [x] Start the route readout directly with the location or arrival information
      on facility approaches, city streets, and at the gate.

- [x] Keep the exit blinker repeating on the right until ramp entry, cancellation,
      or a missed exit; stop canceled-exit guidance until the driver signals again.

- [ ] Validate the Windows portable snapshot on a clean Windows installation
      without a separately installed Visual C++ redistributable; the build
      runner's smoke test alone cannot establish this.

### Release gate -- what stands between here and a public 1.9.0

The checklist below retains the recorded open release gates. Verification here
covers the September 11 corrections; other items have not been revalidated. The
[detailed backlog](docs/roadmap-details.md) retains the supporting notes and
[completed gate work](docs/roadmap-details.md#completed-19-release-gate-work).

#### Release cutover checklist

These steps remain open even where a related implementation bullet is checked:

- [ ] Revert-the-revert on dev for the driving-assists withdrawal
      BEFORE the release merge (merging career-1.9 alone will NOT
      restore the assists; the bullet in the Realism and polish pass
      section spells out the exact commits). Public career selection
      re-lands the same way.
- [ ] The invariants-export regen against PRODUCTION, now including the
      credential ladder's rows ("STILL OWED AT THE DEV CUTOVER").
- [ ] The cutover replay: freshly played 1.9 careers (company new hire,
      slip-seat 4+, post-buy-in owner-operator) against the prod
      validator, not just stored blobs.
- [ ] Flip `DEFAULT_BASE_URL` back to production and drop the
      2026-08-staging key (PRE-RELEASE MUST-DO bullet).
- [ ] Convex deploys before any build with the no-transfer marker
      ships; the radio stream sweep (`--recheck-dead`) runs before the
      release; the place-callouts ladder rides the release merge to dev.
- [ ] The physical-Mac VoiceOver listening pass on the Mac release
      staging, and the owner voice pass over seven achievement titles.
- [ ] Cut the stable notes from the rewritten Unreleased block
      (2026-09-14: 718 bullets at a median of 85 words became 774 at 27,
      one heading per section). Before cutting: drop the tester-line
      bullets that are false at release (the staging orinks.net copy, the
      1.9 tester snapshots, the Update channel developer-snapshots row,
      the "1.9 updates look for tester builds" fix), and settle the pairs
      the rewrite could not from the code: fuel counting toward the
      truck's weight against the 80,000-pound dispatch cap; curve speed
      assistance "engine brake first" (Added) against "the engine brake
      is for hills, not corners" (Fixed); the Learn game sounds collision
      entry, which still explains itself by the retired terse mode.

#### Player-impacting release blockers

These items are part of the release-gate sweep:

- [ ] Lane centering assist is a settings promise with no feature:
      implement or retire before 1.9 ships (owner decision).
- [x] Signal running is dice and tickets (2026-09-12): the crossroad's
      seeded traffic decides whether a blown red or stop sign meets nothing,
      a horn, a clip or a heavy broadside, and a flat seeded roll draws the
      red-light or stop-sign citation on the chain-law checkpoint rails.
- [ ] The 2026-08-13 Dropbox tester findings are still untriaged.
- [x] Cruise switches its traffic focus on the actual held-wheel lane
      crossing, keeping the origin lane until then and protecting traffic in
      the lane entered.
- [x] Braking estimates share the live brake-force calculation. Generic
      hazard warnings retain service-braking and reaction time; emergency
      braking has its own stopping estimate.

- [x] Testers hear sounds quieter at the quiet speech rung -- the Aug 19
      earcon duck covered say_event; the main say path (cruise/stop
      confirmations) now ducks the bed the same way when game sounds step
      back for speech is on. Absolute levels were never low; relative
      masking under the unducked road bed was.
- [ ] Departing straight into a hazard at route mile zero -- MOSTLY DONE:
      the real-zone floor and the merge-free opening miles landed
      2026-08-16; what remains is departure chains for the other 72
      percent of facilities, a data project.

#### World data and sound licensing blockers

- [ ] ~250 legs' curves/limits/ramps still describe pre-repair
      geometry (re-bake over the 210 repaired legs; finish the 250).
- [ ] 33 legs a truck router would refuse.
- [ ] 776 facility approach pins land too far out (the 35-mile
      deadhead); blanket 25-mph approach streets for miles.
- [ ] The Duff-shared sound cues flagged unlicensed by the provenance
      audit -- cannot ship in a public build (separate from the
      resolved Splice matter; owner may already know better).
- [ ] Colorado's live traffic and construction are dead (CARS GraphQL
      retired; COtrip's WZDx feed wants a registered key, as do Ohio,
      Oregon, Texas, Virginia, Michigan and Illinois). The 2026-09-12 FHWA
      registry sweep put every keyless statewide feed in: 29 states carry
      live construction now, 15 of them new that day.

#### Owner decisions

These decisions remain with the owner: engine off at trip start;
the per-aid assistance-mode assessment; the two CONFIRMATION lines
silenced at quiet (2026-08-22 build); the two parked branches
(honest-brake-decel; the speech-ladder branch predates the Rust cutover
and needs triage before revival); public career following the opened
career (Shane's design ask).

The detailed backlog retains the remaining work and its recorded release scope.
Update each item where it is recorded; this reorganization does not change
its status or release decision.

### September 11 trucking corrections

- [x] Commercial bobtail repositioning records driving time while moving and
      on-duty time while stopped, including terminal turnaround.
- [x] Tires, brakes, and engine warn at the 80-percent game maintenance
      threshold and require service at 100 percent. Garage and roadside
      recovery remain available to company drivers and owner-operators.
- [x] Remaining diesel contributes to gross weight. Dispatch previews use
      the assigned tractor, and fuel menus report full-tank weight margin.
- [x] HOS advice selects a compatible reachable rest stop and warns before
      the last usable exit. Interrupted warnings retry after pause or resume;
      completed warnings stay suppressed until the relevant reset.
- [x] Skip speech voices that fail to initialize and retain spoken agent
      readouts when sound output is busy. Native SAPI and OneCore checks pass.
      A live session with normal Windows access used NVDA and SAPI, completed
      a short drive and stop, and returned status and HOS readouts without
      speech errors. The earlier initialization failure reproduced in the
      restricted shell without the agent server.
- [x] The long half of a sleeper split (7 or more berth hours) pauses the
      14-hour window while it runs, as 49 CFR 395.1(g)(1)(iii)(B) excludes
      qualifying rest from the window; the short half counts until the pair
      is credited. Tester report 2026-09-11: 7 duty hours plus an 8-hour
      berth rest woke to a closed window.
- [x] `--agent-server --operator-keys` keeps the window up and lets the
      owner's keyboard reach the game, to drive alongside the agent; the
      repo's `.mcp.json` passes it. Without the switch the keys are still
      dropped at the door.
- [ ] Complete the owner's listening pass and longer gameplay verification
      of wear thresholds and interrupted warnings. Captured live readouts and
      successful native calls do not establish what the owner heard.
- [x] Stabilized the curve-assistance test's empty-road fixture. It clears
      current vehicles and disables random traffic replenishment before the
      bend cases run. One full run reported cargo damage; focused and full
      reruns passed.
- [x] The clock key's arrival estimate on the departure streets adds the
      parked highway run at its route pace, and the speed readout names a
      lead vehicle that is setting the speed keeper's number (agent drive,
      Dallas to Sherman with every assist on, 2026-09-11).
- [x] Facility stopping assistance is a preset field again (owner ruling
      2026-09-11): Realistic off, Balanced and All assists on, hand changes
      read as Custom. The 2026-08-31 rest-stop merge had left it outside the
      presets while the manual promised Balanced stops at the destination.
- [x] The S key names mainline bends only (2026-09-12). It used to add a
      connector arc's advisory ("The bend here advises 40") at a
      highway-to-highway interchange, though connector arcs are excluded
      from the curve call, the curve servo and the cargo model by design,
      so the driver was told about a bend no assist acts on (I-30 to I-35
      at Fort Worth). D still answers with the connector's safe speed.

### September 12 live data and dispatch

- [x] Dispatch reads the state 511 construction reports onto each route
      option at the pickup departure, takes the next route when the road is
      closed or the delay outweighs the extra miles, and says why. Fifteen
      more states' feeds came in from the FHWA WZDx registry, all keyless;
      29 states carry live construction.
- [x] National Weather Service warnings ride the real weather toggle:
      dispatch plans around a blizzard, ice storm, hurricane or tornado
      warning, prices a winter storm, high wind, flash flood or dense fog
      warning into the route, and only mentions a thunderstorm; the cab reads
      a warning out as the truck drives into it, and a winter warning posts
      the chain law before the first flake. Driven live out of Pittsburgh.
- [x] Convenience stations the map had typed as travel centers with only
      assumed truck parking read as bobtail-only at load: no announcement,
      no exit signal, no rest stop with a trailer on. 242 stops, nine in ten
      kept; the sleep-gap corridors held.
- [x] The pumps charge this week's federal survey diesel price with each
      region's usual spread on top, on by default; Settings, World, Fuel
      prices switches back to simulated.
- [x] Company drivers get a load RELAYED from a nearby freight town when the
      board here is thin (few loads, poor pay, or half the freight of a market
      in range), deadhead paid and timed as part of the assignment, driven as
      one pickup drive that resumes from a save. The one-in-nine empty
      reposition is gone. Home-time relays wait for the 1.10 home terminal.
- [x] The agent server's `scenario` tool stages the sandbox career in any
      situation; the sandbox turns every live feed on. Driven live: Tonopah,
      relayed Las Vegas load assigned and accepted.

### September 12 profiles and the safety record

- [x] The public profile explains each badge: the invariants export carries
      every badge's description and category (hidden ones included, since a
      badge on a profile is earned) and orinks.net dev renders them under
      the title; the in-game driver profile speaks the description too. The
      song behind each badge stays out of the export.
- [x] Two safety-record gaps closed: the chain-law checkpoint citation was
      charged but never booked on the licence file, and an out-of-service
      order only ever counted on the trip, never on the career field the
      scale screening scores. Both reach the record now.
- [ ] The public safety record lists citations, serious violations, major
      offenses, claims, terminations and repossessions; out-of-service
      orders and fatigue events are scored but not shown, by the same rule
      that keeps fatigue private. Decide whether orders belong on the page.
- [x] The driving record bites through the carrier and the insurer, and is
      spoken (owner ask, 2026-09-12). Endorsements stay untied to the record
      (hazmat is a TSA threat assessment, 49 CFR 1572, criminal and
      immigration disqualifiers only; tank and doubles are knowledge tests,
      383.93). Citations now carry career times; the carrier's annual record
      review (391.25) is a fourth dispatch-trust input for company drivers
      (guarded over three citations or one serious violation in three years,
      termination at six or two, floors ASSUMED from common insurer hiring
      standards) with the age-out date spoken; the owner-operator insurance
      reserve carries a surcharge (a tenth per citation, a third per serious,
      capped at double, ASSUMED); the record line and the terminal greeting
      read the live consequence.
- [x] A career that is over stays readable (owner ruling 2026-09-12, over
      automatic deletion): the second major offense lands as a terminal
      notice, the greeting says the career is over, the buy-in waits for a
      clear CDL, the public profile carries a Career ended row with the last
      verified career behind it, and Close out this career (terminal menu,
      last row, confirmed) is the only thing that removes the save and its
      cloud backups. Real-life basis: 49 CFR 383.51 Table 1 lifetime
      disqualification, 49 CFR 384.225 55-year record retention.
- [ ] Two record gaps from the same research: the scale-house safety
      record scores lifetime counts where the real carrier score is a
      time-weighted 24 months, and driving under an out-of-service order is
      a disqualifying offense (383.51 Table 4) the game does not model.

### September 14 reputation reads the record

- [x] Reputation is the delivery ledger less the driving record inside a
      ONE-GAME-YEAR window (4 per citation, 10 per serious violation, 20 per
      major offense for life, capped at 60), read by every gate, the trust
      band, the pay bonus, the stats screen and the public profile (the save
      now carries `career.standing`; invariants regenerated on both sides).
      The raw ledger is untouched, so an aged-out record gives the points
      back. Owner ruling 2026-09-14 after Jess read 98 beside three serious
      violations. Cargo claims already hit the ledger directly and were left
      out of the penalty. The window is a year, not the review's three,
      because the clock only moves on the road: staging shows about a game
      day per delivery, so three years outlasts every career played.
- [x] Audit of every wait keyed to game time (2026-09-14): the hazmat (30
      days) and TWIC (20 days) background checks and the 60/120 day
      suspensions are reachable, and a suspension can be waited out at the
      terminal. The 391.25 carrier review and the insurer surcharge moved to
      the same one-game-year window as reputation (REVIEW_WINDOW_DAYS), so
      the equipment hold's age-out date is one a driver can reach; the 383.51
      licence ladder keeps its three years because it is the law, not the
      carrier. Lifetime counts (claims, terminations, repossessions, fatigue,
      out-of-service) stay lifetime by design.

### September 14 screens of lines

- [x] Four screens that answered with one long sentence are lists of lines
      on the shared readout screen (`SimpleMenuState::readout`): Time and
      weather, Trip status, Career plan, and the first-day briefing. The
      logbook drops its duplicated status and its heading row, splits the
      hours limits one per line, and reads entries newest first, led by the
      status. Business status rows, action results, and the driving readout
      keys stay single answers on purpose.
- [x] Every citation and violation booked at the wheel keeps its reason,
      fine, game hour and place as a record entry (the last 60), and Career
      stats opens them newest first. Counts from before this build read as
      "recorded before reasons were kept". The entries ride inside the
      record, which the cloud validator already knows as one top-level
      field, so no validator change was needed.
- [x] Whole hours are spoken whole ("3 hours", "1 hour") by the one helper
      every hours answer shares; the hours summary and the logbook read
      through it too.

### September 14 work zone approach

- [x] Automatic speed control follows the warning's two numbers: cruise
      eases to the taper's 55 first, then to the zone's 45 once the barrels
      are inside the larger of its braking window and the keeper's ease
      distance; the keeper, which takes the taper over at its start, sheds
      for the barrels from that moment instead of holding the taper's
      number until its 0.75-mile window opened. Measured at standard
      pacing: entry 47.2 before, 45.7 after (owner report).
- [x] The mile ahead of a work zone is spoken as the reduced-speed approach
      ("speed limit 55 from one mile out, then 45 through the work zone";
      entry "Reduced speed for construction"), matching how a real
      interstate work zone steps its limit down through its advance warning
      area. "Taper" now names only the short merge at its end, as in MUTCD
      Part 6, where the traffic-squeeze advisory still uses it.

### September 14 keyboard shortcuts and controller buttons

- [x] Every discrete driving control resolves through one table
      (`crates/freight-fate/src/bindings.rs`) the player edits from
      Settings, Gameplay, Controls: Keyboard shortcuts and Controller
      buttons, one row per control, Enter then a press to move it, refusals
      by name for a taken or fixed key, a reset row. Saved as two text fields
      in the settings file. The F1 help, the spoken "press X to" prompts, and
      the mastery counter that retires them all follow the moved key. Fixed
      by design: Escape, Enter, F1, the Control keys, Shift and the left
      bumper as the clutch, plus and minus, the radio dial keys, message
      review, Start and Back on the pad, and every menu key.
- [x] The How to play pages render every control name from the live table
      (`{{id}}` placeholders in `main_menu_help.rs`), following the device
      in use: the pad button when a controller is active and the control
      has one, else the keyboard key. The Controller page pins pad names.
- [x] The agent server's `press`, `hold`, `release` and `pedal` tools take a
      control's shortcut id as well as a key name, resolved against the
      sandbox player's own table, chord included.

### September 14 pause stays on duty

- [x] Pausing keeps the driver on the drivers list, shown as paused, instead
      of signing them off after twenty seconds and back on at resume (which
      read "went off duty" and "is on duty" to everyone's duty watch for a
      bathroom break). The game posts the pause once and sends no
      heartbeats while paused; the server holds a paused row for the
      thirty-minute idle window instead of the six-minute heartbeat one,
      so a pause left for good ages off like a parked truck, dated at the
      pause. Server side deployed first; builds before it keep the old
      behaviour.

### September 16 radio range and the cruise floor

- [x] Driving out of a station's range is announced and retuned again. The
      per-frame settings sync re-pointed the dial at the new position before
      the reception tick compared, so the tick saw the fallback on both sides:
      no line, no static, the dead stream left running at full volume, and
      the drivers board naming the Eagle while the cab played KVSC (owner,
      Willmar to Owatonna, 2026-09-16; inherited from the Python frame order).
      The tick and the board now go by the station the playback seam
      recorded.
- [x] A hazard that leaves the truck below cruise's holding speed no longer
      parks the armed session silently. The keeper bridges the crawl on open
      road, as it does the acceleration lane, and hands to adaptive cruise at
      20; with the keeper off the cab says once what the session waits for
      (owner, US-12 near Litchfield, 2026-09-16: "Well done" at 17 mph, then
      nothing).

### September 13 driver directory

- [x] A driver directory beside Drivers on duty, in the game and on
      orinks.net: every driver with a public profile, on duty first, then by
      when they were last on duty in round figures. The server stamps a
      driver's last-on-duty time once per session end (the sweep that ages
      a silent game off the board, or the game's own sign-off), never per
      heartbeat, so the live board stays as cheap as it was. Same audience
      as the board: public, consented, unflagged. Drivers whose last session
      ended before the stamp existed read as not seen on duty yet until
      their next one ends.

- [x] Two owner-supplied instrumentals in the music pack: D-Major Medley
      in the menu rotation, From Bossa to Blues in the day drive pool (so
      the Roadhouse plays it). Pack re-pinned at 380 entries and
      republished.

### September 12 long sessions and speech

- [x] The three-second voice health probe re-published the whole speech
      snapshot each time, and the snapshot's event-voice options are built by
      acquiring every Prism backend. Prism 0.18.2's OneCore acquire leaks one
      USER object, two handles and about 30 KiB per call (measured with
      `cargo run -p prism --example handle_leak_probe`; NVDA, SAPI and the
      rest are clean after first use), so the game gained 1,200 USER objects
      and 2,400 handles an hour: the 10,000-object process limit and the
      desktop heap, which is the tester's low-memory warning and NVDA failing
      to restart beside the game. The probe now enumerates only when a voice
      changed, and the game's registry holds each Prism backend it acquires
      for the session instead of re-acquiring per request, which also covers
      a session with no screen reader running, where OneCore is the automatic
      main voice and the probe re-acquired it on every pass. 1.8 never
      enumerated outside the settings menu.
- [ ] Owner verifies the OneCore leak with Prism's author before anything
      goes upstream; no issue or PR from this side (owner rule 2026-09-12).
      Hand-off is the probe. Pinned 2026-09-12: the leak is in FREEING an
      acquired (registry-cached) OneCore instance, not in acquiring it
      (acquire-and-never-free is flat); prismatoid 0.16.7, which 1.8 runs,
      frees the same way and is clean, while 0.17.3 and 0.18.2 both leak
      (`FREIGHT_FATE_PRISM_PATH` points the probe at any build). The Rust
      game enumerates exactly as 1.8 does; the library under it changed.
      Holding each instance for the session sidesteps it on every version.

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

- [x] **Commercial bobtail duty corrected in 1.9.** Driving empty to another
      city's dispatch board records driving/on-duty repositioning. Bobtail
      still means a tractor without a trailer; deadhead with an empty trailer
      remains a separate physical configuration.
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


### Lanes and maneuvering

[Read this section in the detailed roadmap](docs/roadmap-details.md#lanes-and-maneuvering).

### Maneuvers, enforcement, and the working day

[Read this section in the detailed roadmap](docs/roadmap-details.md#maneuvers-enforcement-and-the-working-day).

### Career, dispatch, and business

[Read this section in the detailed roadmap](docs/roadmap-details.md#career-dispatch-and-business).

### Radio

[Read this section in the detailed roadmap](docs/roadmap-details.md#radio).

### World and narration

[Read this section in the detailed roadmap](docs/roadmap-details.md#world-and-narration).

## Shipped in 1.6.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-160).

## Realism and polish pass (1.7.0 shipped, 1.8.0 in flight)

[Read this section in the detailed roadmap](docs/roadmap-details.md#realism-and-polish-pass-170-shipped-180-in-flight).

### Player feedback round (accessibility/UX)

[Read this section in the detailed roadmap](docs/roadmap-details.md#player-feedback-round-accessibilityux).

### Driver economics

[Read this section in the detailed roadmap](docs/roadmap-details.md#driver-economics).

### Fatigue and driver responsibility

[Read this section in the detailed roadmap](docs/roadmap-details.md#fatigue-and-driver-responsibility).

### Driving feel

[Read this section in the detailed roadmap](docs/roadmap-details.md#driving-feel).

### Speed limits and speeding

[Read this section in the detailed roadmap](docs/roadmap-details.md#speed-limits-and-speeding).

### Realism north star (ongoing)

[Read this section in the detailed roadmap](docs/roadmap-details.md#realism-north-star-ongoing).

## Local city service drives (built for 1.8, releases with 1.9)

[Read this section in the detailed roadmap](docs/roadmap-details.md#local-city-service-drives-built-for-18-releases-with-19).

## Timed facility work and stop-menu settling (built for 1.8, releases with 1.9)

[Read this section in the detailed roadmap](docs/roadmap-details.md#timed-facility-work-and-stop-menu-settling-built-for-18-releases-with-19).

## In-cab logbook, Record of Duty Status (built for 1.8, releases with 1.9)

[Read this section in the detailed roadmap](docs/roadmap-details.md#in-cab-logbook-record-of-duty-status-built-for-18-releases-with-19).

### Design sketch

[Read this section in the detailed roadmap](docs/roadmap-details.md#design-sketch).

## State troopers and law enforcement

[Read this section in the detailed roadmap](docs/roadmap-details.md#state-troopers-and-law-enforcement).

### Design sketch

[Read this section in the detailed roadmap](docs/roadmap-details.md#design-sketch-1).

## Shipped in 1.5.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-150).

## Shipped in 1.4.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-140).

## Shipped in 1.2.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-120).

## Shipped in 1.1.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-110).

## Shipped in 1.0.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-100).

### Driving mechanics (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#driving-mechanics-done).

### Weather system (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#weather-system-done).

### Route planning (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#route-planning-done).

### Economy and progression (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#economy-and-progression-done).

### Accessibility (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#accessibility-done).

### Technical (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#technical-done).

## Future ideas (post-1.0)

[Read this section in the detailed roadmap](docs/roadmap-details.md#future-ideas-post-10).

### Gameplay depth

[Read this section in the detailed roadmap](docs/roadmap-details.md#gameplay-depth).

### World

[Read this section in the detailed roadmap](docs/roadmap-details.md#world).

### In-cab radio (1.8 / 1.9 candidate)

[Read this section in the detailed roadmap](docs/roadmap-details.md#in-cab-radio-18--19-candidate).

### Business

[Read this section in the detailed roadmap](docs/roadmap-details.md#business).

### Platforms and community

[Read this section in the detailed roadmap](docs/roadmap-details.md#platforms-and-community).
