# Freight Fate Roadmap

> Current stable: **1.8.0** (shipped 2026-07-05). Next release: **1.9.0**, in
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
- [x] **Physics test bench** (`tools/physics_bench.py`): deterministic scripted-driver scenarios over the real truck model -- descents, runaway coasts, stop tests -- printing plain-text, screen-reader-friendly, diffable reports (peak brake temp, fade onset, wear added, the cues the game would have played). The tuning loop for every physics change; `tests/test_physics_bench.py` keeps its orderings honest. Now also a tuning instrument: `--sweep` re-runs a scenario across one knob (speed, cargo, grade, wear) one line per value, and `--solve` bisects for an edge ("the fastest drag speed that stays under fade"), both plain-text and deterministic.
- [x] **Per-truck condition.** Wear, damage, and fuel moved off the profile into `truck_conditions`, keyed by truck, so each owned tractor keeps its own state and swapping trucks no longer teleports condition. Legacy saves migrate (all owned trucks inherit current wear; no pristine spare), per-truck wear is under the save signature, and the field is scoped by truck *model* key -- true per-instance trucks are still the rental feature's job.
- [ ] Truck selling / trade-in at the dealer: no sell path exists today, so `truck_conditions` never needs to drop a record. When selling lands, drop the sold truck's condition record (and decide salvage value from its wear).
- [ ] Transmission as a per-truck purchase spec (rides the dealer/sell path above): a gearbox is bought with the truck, never swapped in later. Carrier-spec company tractors run automatics like real fleets; owner-operators choose at the dealer, and the cheap old rigs of the lease-to-start onramp skew manual -- cheap entry costs shifting skill. Gear count (10/13/18-speed) can join as a spec later. The global Transmission setting survives as the player's accessibility override, and dispatch respects it.
- [x] **Jake brake realism.** The jake is now retarding torque through the gearing -- three stages, scaling with RPM and gear ratio -- so gear discipline decides descents: stage 3 in 7th holds a loaded rig on a 6 percent grade with zero service brake, stage 1 makes the shoes work, and overdrive gives almost nothing. Automatics pre-select down into the retard band with the jake on and upshift past the RPM ceiling to protect the engine (the realistic runaway spiral). Bench-solved anchors: jake-only holds up to ~26 tonnes of payload on the 6 percent; past that you snub or run away. The on/off key still works; a staged in-cab control is open follow-up below.
- [x] **Brake thermal realism.** Drum heat is now real energy accounting: dissipated brake power soaks a drum thermal mass, cooling is convective (square root of speed -- outrunning your brakes no longer air-conditions them), and faded shoes grip less so they also heat less. The six-mile 6 percent drag now peaks at 466 C with miles ridden past fade, while jake-and-snub finishes cool -- the drag-vs-snub lesson finally has teeth. Overspeed realism came with it: the road can drive the engine past the governor (that wears it; governed running is safe), and brake wear is now charged per megajoule actually dissipated in the shoes.
- [ ] Staged jake in-cab control: the physics supports stages 1-3 but the J key still toggles off/full. Add a spoken stage cycle (and gamepad binding) so drivers can pick partial retard on purpose.
- [x] **Traction deep-dive: freezing rain, hydroplaning, jake grip cap.** `WeatherKind.ICE` (grip 0.15, a third of snow) forms physically -- rain sampled in the 1 to -4 C band glazes, and the live NWS feed maps freezing rain/sleet/ice to it instead of snow -- with its own hazards, spoken "ice on the road" status, and a bench `stop-ice` anchor (880 ft from 40 mph vs 329 dry from 60). Hydroplaning follows the Horne relation: onset ~106 mph on fresh tread (trucks at highway pressure basically never plane), pulled down by tread wear and standing-water depth (`WeatherEffects.water_mm` -> `truck.water_mm`) -- 80 percent worn rubber planes at ~59 in heavy rain, grip collapsing toward a 0.3 floor over a 12 mph band, with a spoken onset warning and hydro-aware conditions incidents. The jake is now capped by drive-axle grip (42.5 percent of gross, half usable before lockup): dry never binds, glare ice breaks stage 3 loose in a low gear while stage 1 stays hooked up, `jake_slipping` speaks a warning, and the bench `grade-jake-ice` run shows the capped jake losing ground on a 4 percent it would hold dry.
- [ ] Jake-slip and hydroplane consequences beyond the warning: sustained sliding should be able to escalate into a real incident (trolley jackknife / spin) through the event system, which needs a "release the jake / ease off" resolution verb rather than the brake-to-answer hazard contract.
<<<<<<< HEAD
- [ ] Lateral traction on curves and ramps: no curve geometry exists in the 1-D model, so cornering grip, curve-speed advisories keyed to load and ice, and rollover/off-tracking stay future -- rides the interchange/ramp data and the off-tracking phase gated on surface streets.
- [ ] **Curve management as a difficulty tier (owner idea 2026-07-15).**
      Today "curves" are only per-leg terrain wander (hills 0.25 /
      mountain 0.55 fed to lane drift) -- no bend has a place, direction,
      or severity, and the curve speed assist auto-brakes on that same
      blunt terrain number (above ~39 mph on every mountain leg, even
      65-mph interstates; even the realistic preset ships it on). The
      real feature: bake discrete curve records from OSM route geometry
      (at-mile, direction, severity, advisory speed -- the same canyon
      data as the dense maxspeed sweep), then at the manage-curves
      difficulty tier speak the approach ("sharp right, quarter mile,
      advisory 25"), guide the bend with a panned tone tracking the road
      center (the lane-guidance audio grammar), require the slowdown, and
      let hot entries pay physics consequences (drift off-lane, load and
      ice against the lateral-traction bullet above). Owner-shaped design
      points (2026-07-15): opt-in as a new DRIVING_ASSIST_FIELDS entry so
      Josh's presets own it (All assists = today's auto-curves, Realistic
      = drive them yourself); keyboard stays first-class
      (tap-to-nudge/hold-to-sweep with the guidance tone closing the
      loop) with analog pad.steering as the smoother option -- the lane
      code reads it already; and a terse safe-speed key speaking one
      grip-adjusted number ("Safe speed 18" -- weather baked into the
      math, never into the speech), same verdict grammar as the G grade
      key.
- [ ] **Signal-and-steer turns on surface streets (owner idea
      2026-07-15).** Turn-by-turn today is automatic: the truck follows
      the baked chain, the player hears the cue and panned chime and only
      manages speed and stops. At the higher-realism tier a turn should
      be driven: signal (indicator stalk sound already shipped), brake to
      turn speed, steer through with the same guidance-tone grammar as
      curves, with missed or unsignaled turns costing a reroute or
      strike. Natural interaction layer for per-turn trailer
      off-tracking.
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
- [ ] **Speech history review -- walk back through what you heard (owner
      playtest 2026-07-15 night).** The repeat keys hold one line each
      (comma = last spoken anywhere, A = last route announcement), but on
      a busy road the line you missed is several announcements back: the
      owner pressed comma hunting the flashing chain-law sign and got
      "25 miles per hour, gear 7, 1427 RPM" -- the status readout that
      happened to speak last (log receipt, Denver night run). Keep a
      ring of the last ~20 spoken lines across both channels; the first
      comma press repeats the newest (today's behavior), and further
      presses within a few seconds each step ONE LINE OLDER -- press,
      press, press walks back in time, exactly the speech-history
      pattern NVDA users already know. A fresh announcement resets the
      walk to newest. A keeps its route-announcement meaning unchanged.
      While in the file: log a transcript marker when the event pacer
      flushes a stale backlog, so playtest logs show the flushes.
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
- [ ] **Cab and rig sonification pass (owner 2026-07-15).** The state the
      truck is in should be hearable before it is spoken. First candidates:
      a chain-clatter loop whenever chains are mounted, pitched and paced
      with speed -- on snow it is texture, on bare pavement it is the
      warning that saves the set (the physics snaps a cross chain after
      about two dry miles at highway speed; today the snap is the first
      thing you hear); a wear-based brake squeak (worn pads chirp at every
      stop -- the real wear-indicator sound, distinct from the existing
      too-hot squeal); the latch catch click (distinct from the gear
      click). Source from the owner's NAS sound library (film/broadcast
      quality) first, generate only what it lacks.
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
      again in a later sweep. WABE Atlanta joined the dark list
      2026-07-14 (every known mount refused; supported:false with notes).
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
  (`_visibility_reaction_factor`). Freezing rain is now its own condition (see
  the 1.9 traction deep-dive above), so glaze ice no longer rides on active
  snow. Remaining follow-ups: black-ice risk on clear cold mornings after wet
  roads (refreeze after the rain has stopped is still not modeled); steady
  crosswind nudging the trailer; and seasonal daylight length.
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
- [x] **National hub network fill (407 → 623 cities).** Audit-driven map
  expansion on the 1.8.x nightly line (community PR #68): every >10,000-pop
  independent city without a bigger neighbor within ~30 miles was built with
  the full enrichment recipe -- 1,287 legs, ~139,000 network miles, real toll
  events on the major turnpikes, and posted speed limits on every leg.

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
- [ ] **Latching controls -- sticky keys for the cab (owner idea
      2026-07-15).** Press to latch the brake or accelerator, press
      again to release, spoken both ways ("Brake latched. Brake
      released."). Generalizes the speed keeper's motor-accessibility
      case to every sustained hold: descent snubs, long pulls, backing.
      Free settings-layer accommodation, never gated. Safety semantics:
      AEB, the hazard brake-to-answer verb, and the overspeed alarm all
      outrank a latched accelerator and release it audibly; the reverse
      press-and-hold gesture must read a latched brake as held or
      reverse becomes unreachable for exactly the players the latch
      serves. Gesture design (owner, playtest 2026-07-15): the latch
      should live on the pedal keys themselves, no chord to learn --
      but a bare double-tap false-triggers on feathering (players pump
      the throttle in taps), so the gesture is DOUBLE-TAP-AND-HOLD:
      tap, then press again and keep holding about half a second; a
      click marks the catch, then "Throttle latched" -- and the catch
      click must be its own sound, clearly distinct from the gear click
      and easy to hear over the engine (owner note 2026-07-15). Release is any
      single press of the same key (returning to manual), and the
      opposite pedal always releases instantly -- a brake press kills a
      latched throttle as it brakes, spoken. Realism cover: the latched
      accelerator is the old hand-throttle knob, a real cab control --
      and a latched service brake on a long grade cooks the drums
      exactly like the brake-fire physics says it should, which is the
      jake-brake lesson teaching itself. Cruise covers hold-a-speed;
      the latch covers hold-a-pedal (full-torque pulls, steady snubs)
      -- different tools, both spoken. Natural driving-school lesson
      once both land.
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
