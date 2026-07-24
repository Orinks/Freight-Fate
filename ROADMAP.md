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

## 1.9 in flight (`feat/career-1.9`)

- [x] Add one driving-assistance preset selector with independently adjustable emergency braking, lane, stop-and-go, descent, exit, destination, curve, and route-transition support while preserving player confirmation and control.
- [ ] Add future individual yard-entry guidance and assisted docking; no current preset navigates a yard or completes a delivery.
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
- [ ] Indiana and Wisconsin real-traffic feeds are dead and need new
      clients: 511in.org serves its SPA shell for every REST path
      (checked 2026-07-22; data is behind GraphQL) and 511wi.gov's REST
      API 404s on every path (checked 2026-07-23, warning-spammed two
      live playtests). Both states now run as no_api -- silently
      simulated. A sweep of the other 511 configs for the same rot is
      probably worth an afternoon.
- [x] Cruise vs. curve brake, the deeper fix -- SHIPPED 2026-07-22
      (owner direction, same-day playtest): a pacenote now caps the
      cruise working target to the bend's advisory (like the armed-exit
      ramp cap) and releases silently past the curve footprint, so
      cruise drives the bend instead of fighting the assist brake.
      Manual handoff survives only for advisories under the 20 mph
      cruise floor.
- [x] Add a curated `career_1_9` transcript-backed smoke suite with reusable career-stage presets, structured speech ordering, keyboard reachability, all driving modes, and deterministic event hooks.
- [x] Months-long career arc rebalance: dispatch-assigned fleet tractors by level band (ten new truck models), a per-level unlock audit so every rank names something concrete, rebalanced XP with re-paced level 21-30 thresholds, 19 new achievements, and a deterministic pacing model (`tools/career_pacing.py`) pinned by tests.
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
      outside presets. Remaining slices: the required-slowdown
      consequence tier (hot entries pay physics), the pursuit guide and
      edge textures (audio assets), steering-input feel, cue previews.
- [ ] **Real lane counts from OSM (owner ask 2026-07-16).** OSM tags
      lanes directly (lanes=, lanes:forward=); bake per-mile lane counts
      along every leg from the self-hosted Overpass/PBF harvest, the
      exact pattern of the dense maxspeed sweep. Buys real widths (four
      lanes through Albuquerque on I-40, two-plus-two rural) and REAL
      LANE DROPS: where three lanes become two, that is a genuine merge
      event with a real location, not a scripted taper. Goes in the next
      map re-bake brief.
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
      back out, scaled by how hard you braked. All licensed cuts live
      in the gitignored sounds-licensed/ overlay; a clean clone keeps
      the old synthesized cues everywhere. STILL OPEN from the
      diagnosis: (3) an engagement clunk at shift END (the banks fire
      at shift start), and (4) whether SHIFT_TIME 1.0 s eases to
      ~0.7 s -- that one is PHYSICS and needs the bench re-run. Also
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
      screen; streamer-safe mode is the single radio-content gate for public
      stations and personal playlists.
- [x] **Hosts, regional stations, and real signal behavior.** The Roadhouse
      and Night Line have live hosts; twelve fictional regional stations
      with newly composed songs cover markets across the map, fading to
      static at the fringe of their range and handing back to the Roadhouse
      when the signal drops.
- [x] **Public stations are discovered at runtime (2026-07-23).**
      The checked-in public URL inventory is gone. Radio Browser is now the
      optional runtime directory, discovered through its mirrors with
      failover. A no-key approximate real-world location is the default
      search center; the simulated truck is the automatic fallback and an
      optional mode. Coordinate-backed results are distance-filtered; bounded
      state-matched results without coordinates join as internet-only stations
      with no distance or signal claim. Results are cached for about a day
      outside career saves and added silently to the same dial plain brackets
      already tune. Built-in, fictional regional, satellite fallback, and
      personal playlist stations remain.
- [ ] **AFN 360 Global channels stay unsupported.** StreamTheWorld
      geo-blocks those mounts outside overseas military regions (HTTP 403
      from US IPs on every URL form, HLS included); revisit only if AFN
      opens access.
- [x] **Community/college/NPR coverage sweep (2026-07-22).** Fifty-one
      real stations joined the dial, each gated on the BASS live check,
      lifting real-station reach from 78% to 93% of the 623 dispatchable
      cities. KPFT (Houston) came back with its Pacifica mount; the Rio
      Grande Valley (UTRGV), Savannah (GPB WSVH), and Amarillo (KACV) are
      on the air; WFMU and KABF joined by name; and public-radio networks
      filled the Iowa corridor, the Plains, the Rockies, the Southeast
      coast, and the Florida panhandle. jpr-redding was repointed to JPR's
      new Zeno mount. Honest remaining gaps: WABE Atlanta (every mount,
      including its Zeno relay, still refuses BASS -- supported:false with
      notes), KDHX St. Louis (defunct on air; 88.1 sold, no successor
      stream yet; market covered by KWMU), WFSU Tallahassee (mount refuses
      BASS), the far Montana Hi-Line, the Texas border west of the Valley,
      and interior US-50 Nevada -- genuinely thin country, left dark rather
      than faked.
- [ ] **Montana Hi-Line via translators (owner lead, 2026-07-22).** The
      Hi-Line gap may not be as dark as the license map suggests: Montana
      Public Radio and Yellowstone Public Radio blanket the state through
      low-power FM translators, and the parent streams are real, licensed,
      and likely BASS-friendly. Next radio pass: map which translator
      (parent network) actually covers each Hi-Line dispatch city and seat
      the parent stream there under the local translator's dial position,
      the same honest-coverage rule as everywhere else.
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
- [x] **Fictional call signs de-squatted (2026-07-22).** An FCC license
      audit found eleven of the twelve invented regional call signs
      collide with real licensed stations (only KRWL was clear). Each was
      renamed to an FCC-unassigned sign with the brand and dial position
      unchanged; Josh accepted the old->new list 2026-07-23, closing the
      audit -- nothing further owed before the release cut.
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
      checker: --limits-lint runs the
      anchor-repair judgment rules as a linter (fresh bakes must report
      zero); --stops re-queries OSM per leg (honors OVERPASS_URL) and
      diffs live named truck POIs against baked stops, with a direct
      existence check around each baked stop's own corridor point so a
      sampled miss never reads as a closure. Never writes; exit code 1
      when anything needs attention, so a scheduled run can alert.
      Curation stays with the recipes. Future: fold in landmark and
      interchange drift. Its old checked-in radio URL sweep was retired
      when public stations moved to runtime discovery on 2026-07-23.
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
      streamer-safe gate like public station audio; stream URLs inside an M3U
      are ignored. Follow-up: consider shuffle
      and a cross-session resume position if playtests want them.
- [x] **Radio dial categories with a jump key (landed 2026-07-20).**
      Ctrl+bracket (the owner's binding -- plain brackets already tune)
      leaps to the first station of the previous/next dial category and
      leads with the category name: route playlist, Freight Fate
      stations, your playlists, terrestrial, nearby internet, internet-only, and
      satellite. The dial sort and the jump share one grouping.
- [ ] **Fictional call signs must not squat real stations (owner catch
      2026-07-20).** Our fictional Phoenix classic-rock station is
      "KDRT Desert Rock 101.5" -- but KDRT-LP is a real community station
      in Davis, California. Rename it, and audit all 15 fictional call
      signs against the FCC database (WDLT and WSOL look suspect too);
      fictional stations should hold call signs no real broadcaster owns.
- [x] **Community and college coverage moved to runtime discovery
      (2026-07-23).** Radio Browser is now the optional runtime dependency
      for public stations, rather than only a finding aid for checked-in
      URLs. Its live state directory covers public, community, and college
      stations without a manual URL sweep. TuneIn remains out.
- [ ] **Custom internet station entry.** Add a simple accessible settings
      path for a player-supplied HTTP or HTTPS stream. Reuse the runtime
      URL-safety and non-blocking tune path; do not turn the Radio status
      screen into a station manager. Personal M3U files remain file-only.
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
- [x] **Retire the public-stream catalog health chore (2026-07-23).**
      Runtime directory health, bounded stream checks, and cached stale
      fallback replace the manual checked-in URL sweep.
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
- [x] **State lines repeated at intermediate cities -- FIXED 2026-07-19
  (player transcript).** Mapped state-boundary cues are now authoritative, so
  passing the next major city no longer claims that the truck crossed the same
  state line again. City narration retains the old crossing wording only as a
  fallback for legacy legs without mapped boundaries. Full harness regressions
  cover Tennessee and Texas routes, reverse travel, and an all-Texas route.
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
  up (imposed limits, stops, exits ahead); R includes the current road, state,
  direction, nearest named place, and trip progress in its route report.
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

### In-cab radio (1.8 / 1.9 candidate)

A truck radio you can tune as you drive: built-in and fictional stations are
always ready, while public stations for the player's detected region join the
same dial at runtime. Coordinate-backed entries are distance-filtered and
coordinate-less entries are explicitly internet-only. A satellite-style safe
station remains the always-available fallback.

- [x] **Practical in-cab radio.** Shipped: driving now has keyboard radio
  controls (M toggles, brackets tune, Y speaks status), persistent radio
  enabled/station/volume settings, a dedicated lower radio volume, streamer-safe
  mode on by default as the sole radio-content gate for public streams, and
  graceful fallback when a selected station/backend cannot play. The checked-in
  JSON catalog now contains only safe built-in, fictional regional, and
  satellite-fallback stations. Radio Browser supplies bounded nearby and
  state-matched internet-only stations at runtime through a cached,
  non-blocking, mirror-failing-over path. Plain
  brackets walk every receivable entry. Stream probing and opening stay off the
  driving loop, and the latest generation alone may take over playback.

- **Direction (decided):** discover public station streams from Radio Browser
  at runtime instead of maintaining a checked-in URL list. The directory is
  optional, requires no shared key, and never replaces the built-in/offline
  dial.

- **Streamer-safe is the single radio-content gate.** Independent of the game's own
  posture: a player who streams a session to YouTube/Twitch with copyrighted
  station audio can still get the VOD struck. With streamer-safe on, public
  stations and personal playlists are hidden; turning it off silently permits
  automatic public discovery when Online services and the audio system allow it.

- **Nearby and internet-only, without false precision.** A no-key approximate network location is
  the default center. If it fails, discovery follows the simulated truck; that
  is also an optional setting. Queries send a state/region, and distance is
  calculated locally from directory coordinates. Those coordinates are not FCC
  contours, so coordinate-backed entries are described only as nearby internet
  stations. State-matched entries without coordinates are a bounded
  internet-only category: always receivable while cached, with no distance,
  signal, or terrestrial claim. The fictional regional stations keep their
  existing authored range behavior.

- **Satellite fallback: owned and offline.** The Safe Satellite Fallback remains
  always available without a public network stream. It covers directory
  outages, unsupported audio systems, and streamer-safe play.

- **Audio sourcing: bounded and defensive.** Runtime results must be currently
  working, use a supported ordinary HTTP audio codec/transport, and pass public
  destination checks before entering the dial. A selected stream is checked and
  prepared asynchronously, including redirect validation; failures return to a
  safe built-in station without blocking controls or speech.

- **Accessibility is the feature, not a checkbox.** Tuning must be fully
  spoken and keyboard-driven: plain brackets move through the dial, pending
  and playing states are truthful, failures are concise, discovery never
  steals focus or floods speech, and radio volume remains separate in
  Settings. The status screen stays current-only; it is not a second tuning
  interface.

- **Ties to existing systems.** Reuses the music backend, settings gates,
  state names, simulated truck position as fallback, and the normal dial.
  Directory results never enter signed career saves.

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
- [x] Per-computer driver tokens on orinks.net: each computer gets its own token from a named, revocable computer list on the driver setup page, so connecting a second computer no longer retires the first one's sign-in (issue #64; game-side reconnect guidance points at the computer list)
- [x] Copy the delivery summary to the clipboard from the delivery complete screen (verified by read-back before the game says "copied")
- [x] Opt-in Mastodon sharing of notable deliveries: the player links their own Mastodon account on orinks.net (any instance, dynamic app registration, `read:accounts write:statuses` scope), and the game offers deliveries that earned an achievement, level, or streak milestone; the server composes the public post from allowlisted facts and adds the #FreightFate hashtag. Off by default, separate consent from Profile sharing, durable outbox client-side
- [ ] Mastodon sharing follow-ups: unlink from inside the game (today the orinks.net page is the only unlink), and consider per-post visibility choice (public vs unlisted) if players ask
- [x] Online hub: the drivers board, orinks.net account, cloud backup and restore, and all sharing toggles moved from Settings into one Online menu on the main menu (`states/online_hub.py`); Settings keeps an Online pointer that opens the same menu for a release or two
- [ ] Remove the Settings Online pointer once players have had a release or two to relearn the location
- [ ] 1.9.0 release-notes credit sweep: nromey's Unreleased bullets (engine audio arc, physics realism, playlists, place callouts, speed-limit audits, signature v3) carry no "Thanks to" attribution yet -- credit them with the PR link when the 1.9.0 notes are cut, per the contributor-credit rule in AGENTS.md
