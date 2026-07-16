# Freight Fate Roadmap

> Current stable: **1.8.1** (shipped 2026-07-13). Next release: **1.9.0**, in
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
- [ ] **ELD character events.** Daily log certification, carrier edit
      approve/reject prompts, personal conveyance and yard-move duty
      statuses, a rare ELD-malfunction paper-log day, and the
      adverse-conditions +2-hour exception wired to live weather.

## 1.9 in flight (`feat/career-1.9`)

- [x] Add one driving-assistance preset selector with independently adjustable emergency braking, lane, stop-and-go, descent, exit, destination, curve, and route-transition support while preserving player confirmation and control.
- [ ] Add future individual yard-entry guidance and assisted docking; no current preset navigates a yard or completes a delivery.
- [x] Add a curated `career_1_9` transcript-backed smoke suite with reusable career-stage presets, structured speech ordering, keyboard reachability, all driving modes, and deterministic event hooks.
- [x] Months-long career arc rebalance: dispatch-assigned fleet tractors by level band (ten new truck models), a per-level unlock audit so every rank names something concrete, rebalanced XP with re-paced level 21-30 thresholds, 19 new achievements, and a deterministic pacing model (`tools/career_pacing.py`) pinned by tests.
- [ ] Wire Big Buck's content into a playable roadside stop; current 1.9 data and spoken refusal content are shipped, but no honest drive-and-enter gameplay path exists yet.
- [x] Release-archive verification: after a player report of a Linux snapshot with no game file (2026-07-14 sweep found all published archives intact), `tools/build_release.py` now re-opens each finished archive and proves the executable (with its permission bits) and key payload survived archiving, and `build.yml` fails instead of publishing a release with a missing platform download.

Four threads: make the drive *between* the exits real, give every maneuver
and working hour weight, make the career read like real employment, and
make the world big and specific enough that every run feels like a place.
(Also releasing with 1.9: everything built for 1.8 that missed the 1.8.0
cut -- the exit setup, expanded enforcement, logbook, timed dock work, and
city service drives below.)

### Lanes and maneuvering

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
- [x] **Congestion grounded in FHWA HPMS volume.** Real AADT baked per leg
      drives clock-gated jams on a commuter curve: metro stretches jam at
      rush hour and flow free at midnight; entering a live jam injects slow
      traffic into both lanes.
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

- [x] **Highway exits take a real setup.** X signals the announced exit,
      the GPS asks for the right-side exit lane, checks ramp speed at the
      gore, and explains missed exits; destination ramps follow the same
      speed/lane/intent contract, and merge/exit traffic puts spoken
      pressure on the maneuver.
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
- [x] **145 achievements.** The badge wall nearly doubles and keeps
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
- [x] **Save compatibility.** Careers back through the version-4 schema
      load with sensible defaults, and newer-snapshot saves no longer crash
      older-schema loads.

### Radio

- [x] **The in-cab radio follows the map.** M toggles, brackets tune the
      currently receivable stations, Y speaks status, Tab has a Radio
      screen; streamer-safe by default with real public streams behind an
      explicit opt-in.
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
      opens access.
- [ ] **Regional stream gaps to re-sweep.** Community stations KDHX
      (St. Louis) and KPFT (Houston) had no working stream endpoint (the
      markets are covered by KWMU and KUHF instead); the Rio Grande Valley
      (Brownsville, McAllen, Laredo), Savannah (GPB not listed on Radio
      Browser), and Amarillo still have no receivable real station -- try
      again in a later sweep.
- [x] **Full music rotations for the fictional stations.** A 52-track
      Suno-composed batch (via the Zero CLI) grows the format pools to
      radio-scale: country 15 songs, classic rock 17 (including a Saltwake
      tribute, "Greywater Quay"), blues and soul 12,
      ten new Roadhouse daytime instrumentals, four new night beds, and
      two Night Line-only vocal ballads. Second takes of the 24 vocal
      songs are kept outside the repo as auditionable spares.

### World and narration

- [x] **Highway-spider map expansion.** Corridor-inventory tooling plus
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
- [ ] **Service-stop buffs and the Big Buck's catalog.** The amenities and
      `big_bucks` modules ship content and tiers; the gameplay layer --
      purchase menus and buff effects on rest quality, fatigue, or morale --
      is not wired yet.
- [ ] **Overlay re-sweep on the slug world.** The local-approach /
      city-service / turn-level geometry sweeps predate the slug migration
      and the newest cities; the runtime canonicalizes old ids and new
      targets simply fall back until the five-builder overlay pipeline is
      updated for slug keys and re-run over the 375-city map.
- [ ] **Earcon audition pass.** The five 1.9 steering sounds (turn
      left/right/ahead, ramp light red/green) shipped verified by
      measurement, not by ear; regenerate any that sound off via
      `tools/generate_sounds.py` (+ `tools/mirror_turn_chime.py` for the
      right-turn mirror).

## Shipped in 1.6.0

- [x] Realistic freight markets and facilities: metro route nodes now expand
      into hundreds of representative shippers and receivers, with stable
      facility IDs, ship/receive cargo roles, regional specialization, curated
      source notes, deterministic offline templates, and save-compatible
      facility-aware job generation.
- [x] Playable air-brake pressure mechanics: cold starts need a short air
      build before the parking brake can release, service-brake applications
      consume air, low-air and spring-brake thresholds are spoken, and active
      trip saves preserve the air-brake state.
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

- [x] **Quick info keys.** S reads the posted speed limit (was buried in the
  Tab menu); A repeats the last route announcement; U reads what is coming
  up (imposed limits, stops, exits ahead).
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

- [x] **Speed keeper for low-speed zones.** Shipped alongside the presets: in facility access roads, gate queues, work zones, and congestion -- where adaptive cruise is deliberately unavailable -- K holds the current speed at or below the zone limit and follows queued traffic, so players who cannot keep the accelerator held (or whose fingers tire) are not locked out of those stretches. Preset-independent and on by default.
- [x] **Driving assistance presets and descent control.** Shipped for the current snapshot: Realistic, Balanced, All assists, and Custom coordinate optional lane, emergency-braking, stop-and-go, and interactive descent support without changing inherent adaptive-cruise behavior or simulation settings. Automatic exits, destination stops, yard entry, and docking remain deferred to Career 1.9 or later. On the 1.9 line, lane drift itself lives in the Driving assistance category but stays preset-independent like the speed keeper: presets tune warnings and support, never whether the lane task runs, so fresh careers keep the centered-lane accessible default.
- [ ] **De-duplicate assist chatter on fast ramps.** A 2026-07-15 logged playtest of the four 1.9 assists showed curve speed assistance and route-transition assistance both firing on the same too-fast exit ramp (the ramp adds curve weight, and both brake and announce back-to-back). With the realistic preset both are on by default, so every hot ramp speaks two assist lines; the ramp case should speak one. Same playtest confirmed the destination approach assist deliberately does not cover the ramp-end stop sign -- players can still roll it with the assist on, which may deserve a clearer spoken hint.
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
  weather on the season follows the real-world calendar so it matches those
  conditions. Real observation temperature is now extracted too (`_temp_to_c`
  -> `RealWeatherProvider.get_temperature` -> `WeatherSystem._temperature`), so
  live mode reports the station's real degrees and falls back to the climate
  model only when a reading is missing. Weather also bites mechanically now,
  not just as flavor: the per-condition aero `drag_mult` is applied to the
  physics (storms/wind cost top speed and fuel), driving well over the
  conditions-safe speed on a slick road risks a traction-loss incident
  (`_check_conditions_speed`), and low visibility shortens hazard reaction time
  (`_visibility_reaction_factor`). Remaining follow-ups: black-ice risk on clear
  cold mornings after wet roads (currently ice rides on active snow); steady
  crosswind nudging the trailer; and seasonal daylight length.
- **Physics and the truck.** Cargo-weight-aware gross mass is done for
  acceleration, grade lugging, fuel burn, and now braking: the foundation
  brakes have a fixed force ceiling sized for the rated gross, so loads over
  the rated weight are brake-capacity limited -- they stop longer and heat
  the brakes faster -- while loads at or below the rated gross are unchanged.
  Remaining: tire and brake wear over a truck's life, and finer grade-based
  fuel burn.
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
- [x] **National hub network fill (407 → 623 cities).** Audit-driven map
  expansion on the 1.8.x nightly line (community PR #68): every >10,000-pop
  independent city without a bigger neighbor within ~30 miles was built with
  the full enrichment recipe -- 1,287 legs, ~139,000 network miles, real toll
  events on the major turnpikes, and posted speed limits on every leg.
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

## Local city service drives (built for 1.8, releases with 1.9)

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
  on-the-spot ticket (`SPEEDING_TICKET_FINES`, paid now) or a warning. Ignoring
  the lights past `PULL_OVER_IGNORE_MI` is logged as evasion. Disabled in the
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
- [x] Per-computer driver tokens on orinks.net: each computer gets its own token from a named, revocable computer list on the driver setup page, so connecting a second computer no longer retires the first one's sign-in (issue #64; game-side reconnect guidance points at the computer list)
