# Changelog

## Unreleased

### Changed
- **Posted speed limits can now come from real map data.** Where a corridor
  carries an OpenStreetMap `maxspeed` tag, the game uses that real posted limit
  instead of the highway/region approximation -- and falls back to the
  approximation only on stretches OSM has not tagged. Limits are baked at build
  time (truck-specific `maxspeed:hgv` preferred where present); the urban
  reduction near cities and the spoken limit-change cue are unchanged.
- **The lane-drift rumble is now directional.** When you wander toward a lane
  edge, the rumble strip plays from that side -- drift right and you hear it on
  the right -- so the ear it lands in tells you which way to steer back. Uses
  the BASS backend's stereo panning.
- **Safety announcements no longer get buried, and you get more warning.** Zone
  entries, construction and traffic warnings, and checkpoints now preempt
  ambient chatter (weather, tolls, state lines) on the event voice instead of
  queuing behind it -- so a "construction ahead" never arrives after you have
  already entered the zone. Zone warnings also lead by real time now, not a
  flat distance: the heads-up scales with your speed and pacing, so 70 mph at
  high time compression gets a usefully earlier callout instead of a couple of
  seconds.

### Added
- **Consult the controls without leaving a drive.** The pause menu now has a
  "Controls and help" entry that opens the how-to-play reference straight to the
  driving keys -- page through it, read it line by line, then escape back to the
  road. The keys list also now includes S, A, and U.
- **HTML player manual.** Portable builds now ship `USER_MANUAL.html` alongside
  the Markdown one: the same manual rendered as a clean, accessible web page
  (semantic headings and real tables) you can open in any browser.
- **Three new on-demand driving keys.** **S** reads the posted speed limit where
  you are -- the zone if any, and how far over you are -- so you no longer have
  to dig into the status menu. **A** repeats the last route announcement, for
  the one you missed before you could react. **U** reads what is coming up:
  imposed speed limits, stops, and exits ahead, so a zone or gate never blindsides
  you. All three are listed in F1 help and the manual.
- **Drowsiness has real consequences now.** Push past severe fatigue and you
  start to nod off: a rumble-strip jolt and a warning give you a moment to steer
  or brake and stay awake. Catch it and you carry on; miss it and you drift onto
  the shoulder for damage and lost speed. Keep driving exhausted and the nods
  come faster and harder until a third miss forces you off the road. Sleep is no
  longer optional once you are running on empty -- and in relaxed mode, where
  hazards are rare, managing fatigue becomes the heart of the drive.
- **Posted speed limits that change by corridor.** The flat 70 everywhere is
  gone. The limit now comes from the highway and region -- rural Interstates run
  70 in the Midwest and East, 75-80 across the West, US highways and state
  routes slower -- and drops to an urban limit on the city stretches. Crossing
  into a new limit is spoken like a sign ("Speed limit 75"), the limit restores
  correctly when you leave a construction zone, and speeding is judged against
  the corridor you are actually on.
- **Seasons and temperature.** Your career now moves through the year, and the
  weather follows. A regional temperature model (a seasonal swing plus a
  day-night swing, warmer in the desert and Gulf, colder across the northern
  tier) decides whether precipitation falls as rain or snow and whether storms
  can brew, so snow is a cold-season risk, thunderstorms a warm-season one, and
  a Great Lakes January night freezes while a Gulf Coast one does not. Because
  hazards are weather-gated, snow squalls and ice now show up in winter and
  hail in summer, on their own. The terminal time-and-weather readout names the
  season, and weather reports include the temperature in your units. With live
  weather turned on, the season follows the real-world calendar so it matches
  the live conditions you are pulling in; otherwise it follows your career clock.
- **Cargo weight now changes how the truck drives.** Gross weight is the
  tractor-and-trailer tare plus the actual payload, so a heavy load pulls away
  gently, lugs harder on grades, and burns more fuel, while a light load or an
  empty pickup deadhead is noticeably brisker. Heavier freight is now a real
  trade-off, not just a number on the dispatch board. The driving status screen
  shows gross tonnage alongside the cargo weight.
- **Load-sensitive braking.** The foundation brakes have a fixed force ceiling
  sized for the rated gross, so a load heavier than the rated weight is
  brake-capacity limited: it decelerates more gently, takes longer to stop, and
  heats and fades the brakes sooner. Loads at or below the rated gross brake
  exactly as before. Overloading a run now bites on a downgrade or a panic stop.
- **Grounded, context-aware road hazards.** Hazards now only happen where and
  when they plausibly would. Standing water and hydroplaning need wet weather;
  snow squalls, bridge-deck ice, and black ice on shaded grades need snow;
  dense-fog brake-lights need fog; crosswind shoves and dust storms need high
  wind in open country; rockfall and runaway-truck hazards need mountain
  terrain. Deer and elk are biased to dawn, dusk, and night, with regional
  species. The implausible ones are gone -- no more farm equipment merging
  onto the interstate or a dust devil on a clear, calm day.
- **Relaxed mode now actually relaxes the road.** In relaxed hours-of-service
  mode, random road hazards are much rarer, so the drive centers on driver
  responsibility -- hours, fueling, repairs, and fatigue -- instead of constant
  emergency braking. Realistic mode is unchanged. The Settings help for Hours
  of service spells out the difference.
- **Dispatcher pay advances (no more soft lock).** A broke driver who can no
  longer afford fuel can now draw a cash advance against the next load -- from
  the terminal hub or any in-trip rest stop -- and it is repaid automatically
  out of the next delivery settlement. The advance is offered only while cash
  is low and is capped, so it stays a recovery line rather than free money. A
  negative balance is no longer a dead end.
- **Discord Rich Presence (optional).** When Discord is running, your profile
  can show broad game activity -- the main menu, the terminal, driving a route,
  resting, or delivering -- with high-level route and cargo context. Only
  general game status is shared, never save files or personal details. It is on
  by default and can be switched off in Settings → Gameplay → Discord presence,
  and the game starts, plays, and exits cleanly whether or not Discord is open.
- **Bigger freight map.** The playable network grows to 194 cities and
  438 routed legs, adding many more regional hubs, shorter connector lanes,
  and route-backed freight choices across the country.
- **Highway exit callouts.** Interstate drives now announce upcoming
  interchanges the way a real sign reads them -- "In 2 miles, exit 7 for
  US-1 North toward Trenton and New York" -- with the exit number, the route
  you would take, and its control cities. Exit data is sourced from
  OpenStreetMap and snapped onto each corridor.
- **Grounded exits and onramps.** When a rest stop sits at a real interchange,
  the exit prompt and ramp now name its number ("Signaling for exit 113, the
  Petro Stopping Centers"; "You take exit 113"). Each run also opens with an
  onramp callout -- "Merge onto I-65 South toward Indianapolis" -- and highway
  changes name the new road and direction.
- **Optional lane drift.** Gameplay settings now include off, light, and
  realistic drift so players can add a gentle steering task, rumble-strip
  warnings, and off-road consequences without making the default drive harder.
- **Packaged changelog and manual.** Portable builds now include
  `CHANGELOG.md` and `USER_MANUAL.md` in the game folder so release notes and
  the player manual are available offline.
- **Player manual.** A new public manual now gathers install, career,
  dispatch, driving, saves, settings, accessibility, and troubleshooting
  guidance in one linkable place.
- **Music remakes.** The main menu theme, Open Road, and Night Haul now use
  new Suno remakes while keeping their familiar Freight Fate music slots.
- **Music rotation.** All menu and driving music beds now play once and rotate
  through their active pool instead of looping.
- **Quieter music by default.** New settings now start background music at half
  volume so speech and driving cues stay comfortably in front.
- **Expanded music beds.** Freight Fate now includes longer menu, facility,
  daytime driving, and nighttime driving music. Menus and freight facility
  screens use a career-aware pool, and active drives use stable day/night
  pools that rotate without reshuffling abruptly while you are on the road.
- **Truck cab sound refresh.** Engine start, idle, shutdown, horn, gear shift,
  parking-brake set and release, and highway road ambience now use the updated
  in-cab vehicle sound set, with donated truck recordings from
  [Darren Duff](https://darrenduff.com/). The start cue is trimmed so the idle
  loop takes over cleanly.
- **Night driving ambience.** Night drives now play a new recorded in-cab
  night ambience loop.
- **New achievement system.** Careers now track achievements across a range
  of categories, with a spoken main-menu viewer and a chime when you unlock
  one. Existing careers carry over. Note: a career saved on a developer
  snapshot may not load on an older stable release.

### Changed
- **Real weather now uses the National Weather Service.** Optional live weather
  switched from Open-Meteo to the U.S. National Weather Service API
  (api.weather.gov). It is still free and needs no API key, reads each city's
  nearest official station for current conditions, and keeps the same seamless
  fallback to simulated weather when offline.

### Fixed
- **Real weather warm-up.** With real weather enabled, a drive now starts in
  neutral clear conditions and waits for live data, instead of briefly showing a
  simulated condition that the live data immediately replaced. That warm-up
  flicker could also wrongly unlock a weather achievement (for example, a rain
  achievement for weather you never drove in). Simulated weather still runs as
  the offline fallback when live data cannot be reached.
- **macOS save location.** Saves now live in
  `~/Library/Application Support/FreightFate` instead of beside the app in
  Applications, matching macOS conventions. Existing saves found next to or
  inside the app bundle are moved into the new location on first launch.
- **Empty reposition arrivals.** Finishing a bobtail (empty reposition) run no
  longer crashes on arrival. The "Repositioned" summary screen now opens and
  reads its relocation summary instead of failing as you reach the new city.
- **Speech setting previews.** Adjusting speech rate, pitch, volume, or voice
  now previews with the voice being changed, so a selected SAPI or OneCore
  voice speaks its own new setting.
- **Truck idling.** The diesel now stays running through pickup check-in,
  loading, route planning, loaded departure, and active-drive resume instead
  of forcing a fresh engine start.
- **Destination exits.** Delivery routes now require taking the real signed
  exit for the destination when one is listed, instead of completing just by
  driving to the end of the highway corridor.
- **Destination exit callouts.** Destination exits now announce the signed exit
  and toward cities before the ramp, then tell you to press X; adaptive cruise
  cancellation includes that exit guidance.
- **OneCore pitch.** Windows OneCore speech now keeps its native default pitch
  unless the player changes the pitch setting.
- **Metric driving status.** Metric mode now reports driving status,
  speed limits, traffic, pickup distance, and legal-stop distance in metric
  units instead of mixing in mph or miles.
- **Metric traffic speed.** The traffic-queue speed shown in the route line now
  reads in kilometers per hour in metric mode, instead of staying in miles per
  hour next to the already-metric distance.
- **Metric navigation cues.** Spoken GPS guidance -- onramp, continue, stop,
  exit, traffic, and construction-zone callouts -- and the Map status screen now
  give distances in kilometers in metric mode instead of miles, matching the
  rest of the metric driving readouts.
- **Metric speed limits.** Construction and traffic zone callouts now speak the
  posted speed limit as a metric value in metric mode instead of the mph number.
- **Live unit switching.** Switching between miles and kilometers mid-drive now
  updates spoken navigation guidance right away, including the distances already
  laid out along the current route.
- **Packaged update checks.** The updater now recognizes standalone packaged
  folders more reliably, so switching to developer snapshots does not leave
  the update screen thinking the game is running from source.
- **Quieter exit guidance.** Ordinary highway exits now stay available in the
  route screen without being announced during the drive unless they lead to a
  stop you can actually take.
- **Route key priority.** Pressing R now keeps the next actionable route detail
  first, while Shift+R reports the next listed highway exit.
- **State-line timing.** State crossing previews now speak about 10 miles out
  instead of 2 miles out, giving the preview and crossing announcements more
  room at highway speed.
- **Upper gear spacing.** Automatic shifting now holds 9th gear longer before
  entering overdrive 10th, so the truck no longer reaches top gear around
  city-road speeds.
- **Portable save folders.** Snapshot builds now move nearby duplicate
  portable save folders into the active `FreightFate\saves` folder instead of
  leaving players with two likely save locations after extraction or updates.
- **Clearer help.** F1 help now focuses on what the selected item does for the
  player instead of repeating menu controls, and garage upgrade help explains
  how each upgrade changes the truck.
- **Updater works in packaged builds again.** Nuitka builds do not set the
  PyInstaller-era ``sys.frozen`` flag, so the game mistook every packaged copy
  for a source checkout: "Check for updates" reported running from source, the
  startup update check never ran, and ``saves/game.log`` was never written.
  Packaged builds are now detected correctly, restoring update checks, install,
  and crash logging.
- **Facility approach speed cues.** Pickup deadheads now use lower-speed
  facility access roads, deliveries slow through a final receiver approach,
  and the last gate prompts are shorter so stopping instructions land faster.
- **Facility gate ambience.** Pickup and destination facility screens now use a
  quieter loading-dock ambience that stays away from truck-idle rumble.
- **Preview sound volume.** The refreshed truck, road, weather, route, and
  facility sounds now play at full source strength before the player's volume
  settings are applied, so lowering and raising sound effects behaves more
  predictably.
- **Achievement speech routing.** Achievement unlocks now speak through the
  screen reader voice instead of the separate driving-event voice, so players
  who miss or interrupt an unlock can still review it later from the
  Achievements menu.
- **Facility and settings audio fixes.** Terminal and yard screens now use
  the new facility-gate ambience, delivery completion no longer buries the
  dock and settlement cues under a generic menu sound, and volume settings
  persist into the next game session.
- **Status and settings navigation.** The driving status panel now opens into
  clear route, driver, truck, and map-style status screens, and Settings uses
  category menus for gameplay, audio, speech, weather, and updates.
- **Menu navigation polish.** Delivery completion now presents settlement,
  route, truck, and career details in one continuous list, while Settings keeps
  its category menus for easier browsing.

## 1.6.0 - 2026-06-19

### Added
- **Contextual route and weather audio.** Driving now uses in-cab rain, snow,
  wind, fog horn, and thunder cues plus short route-event sounds for hazards,
  construction zones, inspections, tolls, state crossings, rest stops, weigh
  stations, facility gates, and docking. The road bed is back in the mix so
  the cab does not feel dry while moving. The experimental vehicle engine sound
  redesign is still being tuned and is not part of this release.
- **Route rest, toll, and settlement realism.** Route planning now uses richer
  truck-stop data, handles shoulder-sleep edge cases more cleanly, and accounts
  for toll and settlement details more explicitly.
- **Air-brake startup and reservoir behavior.** Trucks now build air
  pressure before departure, keep spring brakes engaged until the system is
  ready, and model service and emergency reservoir pressure while driving so
  braking feels more like a heavy truck without stranding new careers.
- **Driving status menu.** Pressing Tab while driving now opens a spoken status
  menu with load, trip, truck, route, and route-stop details from the road.
- **Better route stops.** Dispatch-supported freight now
  relies on curated truck-relevant route stops only: placeholder midpoint
  POIs no longer count as real route support, long-haul lanes must include
  explicit fuel-capable stops, and route summaries/GPS stop details
  now give clearer parking certainty.
- **Auto-updater.** The packaged game now checks GitHub for new releases
  when you reach the main menu. When one is found, a fully spoken prompt
  offers "Download and restart" (downloads the update, swaps it in, and
  relaunches the game for you), "What's new" (reads the update's changelog
  line by line), "Remind me later", and "Skip this version". A new
  Settings entry, "Update channel", picks between stable releases and preview
  builds, and "Check for updates" checks immediately.
- **Real pickup and loading flow.** Job offers now name the origin
  facility as an actual stop on the trip instead of flavor text. After
  accepting a load, you check in at the listed facility, load only while
  stopped, then plan the loaded trip to the destination.
- **Company terminal dispatch flow.** New careers and continued drives now
  frame the service-area hub as a company terminal or yard instead of a
  generic city spawn. Dispatches start with a local deadhead move from the
  terminal to the shipper, and delivery settlement parks the truck at the
  destination area's terminal or yard for the next assignment.
- **Destination facility docking.** Deliveries no longer settle just
  because the truck reached the destination city. The game now warns at
  speed, keeps you in control until a full stop, opens a facility menu
  with a dock/yard cue, and requires "Dock and deliver" before payment.
  "Check paperwork" previews facility, cargo, payout, deadline, and damage
  details without completing the load.
- **Real freight facilities on job boards.** Cities now offer freight from
  classified locations such as terminals, warehouses, ports, intermodal
  yards, air cargo areas, manufacturing plants, food terminals, industrial
  parks, retail distribution hubs, and bulk facilities. Cargo is filtered
  by plausible facility type.
- **Highway exits.** Rest stops now sit at proper exits. They are
  announced a few miles out ("Press X to take the exit for it"); X
  signals for the exit (and X again cancels), you slow to 45 or less for
  the ramp — any faster and you blow past it — then half a mile of ramp
  and brake to a stop, and the rest stop menu opens by itself. The ramp
  is off the highway: hazards and speeding checks pause while you are on
  it. Pressing T while stopped on the highway at a stop still works.
- **Explicit highway stop positions.** Route data now stores named highway
  amenities with explicit mile positions instead of spreading rest stops
  evenly across a leg. The first curated offline stop set uses sourced rest
  areas and travel centers, keeping the game playable without live map lookups.
- **Reverse gear and missed-stop recovery.** Trucks can now back up.
  Automatic players can hold Down while stopped to reverse slowly, then
  touch Up to brake and return to forward drive; manual players can press
  the clutch and Backspace for reverse. If you miss a rest stop, slow
  down, back up carefully, stop, and press T.
- **Cruise control.** K sets cruise at your current speed, matching common
  highway driving expectations, and holds it with a slow throttle governor
  through grades.
  K again, any braking, the emergency brake, a stall, or taking an exit
  cancels it — and a hazard warning hands control straight back to you.
  Space reports speed.
- **Region-flavored road hazards.** The hazard pool now mixes nationwide
  staples with local flavor for the region you are driving through: dust
  devils and tumbleweeds in the Southwest, deer and farm equipment in
  the Midwest, rockfall in the Rockies, elk and standing water in the
  Pacific Northwest, and more.
- **Separate voice for driving events.** Road events — hazard warnings,
  collisions, weather changes, rest stop and city announcements, HOS and
  fatigue warnings, speeding, inspections, speed callouts — now speak
  through a dedicated Windows SAPI voice, so a screen reader reading menus
  or echoing keystrokes can no longer cut off a "Brake now!" mid-sentence.
  A new Settings entry, "Driving event voice" (default: separate SAPI
  voice), switches events back to the screen reader. When SAPI is
  unavailable, or is already the main voice, events fall back to the main
  channel automatically.
- **Emergency brake.** Hold B while driving for the hardest possible stop:
  instant full application plus the spring brakes (about 1.6 times the
  service brakes, still subject to weather grip and brake fade), with a
  loud air-dump cue. Use it for hazards and for rest stops you would
  otherwise overshoot. Mentioned in the tutorial, F1 controls, and the
  manual.
- **Roadside mechanic.** The pause menu while driving now offers "Call a
  roadside mechanic" once damage is past 25 percent: a field patch back
  down to 25 percent damage for a 500-dollar callout plus 110 dollars per
  percent repaired (a steep premium over the garage). The repair takes 90
  in-game minutes against your deadline and duty window, and the bill is
  due even if it puts you in debt — never a dead end.
- **Time and weather in the city.** A new city menu entry speaks the
  clock, the time of day, the day of your career, and current conditions
  in town (live Open-Meteo data when real weather is enabled).
- **Sleep in any city.** A new city menu entry, "Sleep 10 hours", gives a
  full night at your terminal: fresh hours of service, zero fatigue, and
  the clock advances 10 hours. Previously a spent duty window followed
  you into the city with no remedy except driving — illegally — to the
  first rest stop of the next run.

### Fixed
- **Pickup facility sounds.** Pickup gates and loading now use the new facility
  ambience and dock cues instead of the older generic menu notification sounds.
- **Preview builds stay in sync with release notes.** Preview builds now pick up
  player-facing changes that have already been prepared for the next stable
  release, so their "What's new" text no longer falls behind.
- **Save resume keeps traffic zones stable.** Continuing a saved drive now
  seeds trip weather from the saved trip seed too, so traffic and
  construction-zone layouts regenerate consistently across operating
  systems.
- **Updater connections on macOS and Linux.** The packaged game's Python
  runtime looks for certificate authorities at paths that only exist on
  the build machine, so on macOS and Linux every secure connection — the
  update check, the download, and the real-weather fetch (which silently
  fell back to simulated weather) — could fail certificate verification.
  The game now ships its own certificate bundle (certifi) and uses it
  alongside the system store on every connection.
- **Update errors now say what went wrong.** "Could not reach the update
  server" covered everything from a dropped connection to a blocked DNS
  lookup. The check and download now speak the actual reason — "The
  secure connection could not be verified", "The server answered with
  error 403", "The server address could not be found", and so on. The
  packaged game also writes a session log to saves/game.log, so a
  player can share the full error when reporting a problem.
- **Hazard warnings were unbeatable at highway speed.** The reaction
  window was a fixed 3 to 4.5 seconds, but a full-service stop from 65
  to the safe 25 miles per hour takes about 5 — even the emergency brake
  could not make it once you add the time to hear the warning. The
  deadline is now the braking time the truck actually needs from its
  current speed (on the current surface and grade) plus the rolled
  reaction window, so hitting the brakes promptly always succeeds — in
  rain or snow you get the longer stop those surfaces really take.
  Drowsiness now eats into the reaction part only instead of the whole
  window, since a tired driver reacts late but the truck stops no
  slower. Warnings also lead with "Brake now!" instead of ending with
  it, so you can be on the brakes before the sentence finishes.
- **Collision stall soft-lock.** A hard collision could stop the truck
  while the automatic transmission was still in a high gear; the engine
  then stalled the instant it was restarted, every time, stranding the
  player (it read as "too damaged to start", since the same crashes also
  max out damage). The automatic now returns to first gear whenever the
  truck is stopped in a higher gear, and restarting after a stall recovers
  cleanly.
- Pressing E with a bone-dry tank no longer dead-ends on "the engine will
  not start": the out-of-fuel roadside rescue now triggers from there too.
- **The C key's arrival estimate was a constant.** It always assumed
  55 miles per hour, so it never responded to how fast you were actually
  driving. It now tracks your current speed once you are meaningfully
  rolling (and says so), falling back to a typical highway pace while
  parked, and names the basis either way.
- **Abandoning a job lost the hours you drove.** The world clock snapped
  back to the departure time while hours of service and fatigue kept the
  accrued wear, and the freight market did not advance. The time spent on
  the failed run now counts.
- **Trip pacing now applies mid-trip.** Changing "Trip pacing" from the
  pause menu's settings was silently ignored until the next delivery; the
  active trip now picks it up immediately.
- **Unsafe engine shutdown blocked.** Pressing E at road speed no longer
  shuts off the engine. The game now gives spoken feedback and requires a
  safe low-speed stop before shutdown.
- **Delivery at speed blocked.** Arriving at the destination at highway
  speed no longer completes the job. Settlement now requires the full
  stopped facility docking flow.
- **Tampered saves are quarantined.** Career saves now carry an integrity
  signature. Old unsigned saves migrate forward, but edited or corrupted
  saves are moved aside instead of being loaded as valid career data.
- **Implausible route detours filtered.** Route options now reject obvious
  short-haul detours that send drivers far out of the way, while still
  allowing meaningful alternate long-haul routes.
- **State progress announcements improved.** Trips now announce state
  crossings and nearby cities along the route, not only the destination
  state.
- **Construction-zone warnings are actionable again.** Construction zones
  now give a spoken GPS warning about 2 miles before the slowdown begins,
  and troopers will not clock construction-zone speeding until you have
  had about a mile inside the zone to react. Speech-first players can
  slow down in time again instead of being fined on the same update that
  first announces the zone.

### Changed
- **How-to-play driving guidance.** The main-menu guidance for driving controls
  is shorter and more direct.
- **Early career progression and pay.** Low-level jobs now pay enough to
  make early progress feel worthwhile after operating costs, and higher
  levels unlock clearer differences in range, cargo, endorsements, and
  long-haul opportunities.
- **Truck acceleration and shifting.** Loaded trucks reach safe highway
  speeds more plausibly, top gear behaves more like mild overdrive, and
  automatic shift cues are easier to hear without adding air-brake sounds
  to gear changes.
- **Freight market terminology.** Player-facing market wording now uses
  trucking language: tight, loose, and steady, replacing the old generic
  market labels.
- **Real terrain on real highways.** A geography audit corrected 20 of
  the 106 legs. The famous grades are now mountains: Monteagle on I-24
  (Nashville-Atlanta), the Cumberland Plateau on I-40
  (Knoxville-Nashville), the Pennsylvania Turnpike's Allegheny crossings
  (Philadelphia-Pittsburgh and Baltimore-Pittsburgh), and US-95's Idaho
  canyon country (Spokane-Boise). Rolling country stopped pretending to
  be flat: I-70's Missouri River hills, the Flint Hills and Arbuckles on
  I-35, Tennessee's Highland Rim on I-40, Wisconsin's driftless coulees
  on I-94, the Carolinas' piedmont, Connecticut on I-95, and the desert
  passes on I-10 (San Gorgonio, Texas Canyon) among others. Genuinely
  flat country — the high plains, the Gulf coast, Florida, and the Illinois
  prairie — stays flat.
- **Realistic deadlines.** Dispatch can no longer ask for the
  impossible. Deadlines are now built from the hours a law-abiding
  trucker actually needs — driving at an achievable 55 mph average, plus
  the 30-minute break every 8 driving hours and a 10-hour sleep for
  every 11-hour shift the distance demands — with 20 to 50 percent
  shipper slack and a flat hour for fuel on top. San Antonio to Dallas
  now quotes a workable 7-to-8-hour window instead of a sprint.
- **State trooper groundwork.** The next law-enforcement milestone is outlined:
  patrol intensity by corridor, CB chatter warnings, pull-overs, immediate
  fines, and an enforcement setting.
- **Portable saves.** Profiles and settings now live in a `saves` folder
  inside the game's own directory (next to the executable in release
  builds) instead of the per-user data directory. Existing saves are migrated
  over automatically on first launch; the originals are left in place.

## 1.5.0 — 2026-06-10

"On the Clock": hours of service, fatigue, day and night, and overnight
parking. Everything runs on the in-game clock (`settings.time_scale`
compresses it as usual), never wall time.

### Added
- **Hours of service.** Simplified FMCSA rules per shift: 11 hours of
  driving inside a 14-hour duty window, a 30-minute break required after
  8 hours at the wheel, and a 10-hour sleep to reset. Spoken warnings at
  2 hours, 1 hour, and 30 minutes before each limit (each fires once),
  and at the violation itself. The C key now reports the clock time and
  HOS status alongside the deadline; Tab includes it at normal and chatty
  verbosity. Driving past a limit risks roadside inspections with
  escalating fines (200 to 2,000 dollars) and reputation hits — never a
  game over. A new Settings entry, "Hours of service", picks realistic,
  relaxed (every limit 25 percent longer), or off.
- **Rest stop menu.** Pressing T at a rest stop now opens a fully spoken
  menu: refuel (as before), take a 30-minute break, or sleep 10 hours.
  Resting advances the in-game clock, so the delivery deadline keeps
  counting — that is the tension.
- **Fatigue.** Builds with continuous driving (faster at night), eases
  with breaks, and clears with sleep. A drowsy driver yawns, drifts onto
  the rumble strip, hears spoken drowsiness warnings, and reacts late to
  hazards (the reaction window shrinks up to 40 percent). Deterministic
  under the trip seed.
- **Day/night cycle.** Dawn, day, dusk, and night derived from the career
  clock (new careers still start at 6 AM). Nights bring sparser traffic
  zones, a higher hazard chance, a cricket-and-air night ambience layer,
  and the previously unused "Night Haul" track while driving. V, Tab, and
  C mention the time of day, and arrivals speak the clock ("It is 11 PM").
- **Overnight truck parking.** Arriving at a rest stop between 8 PM and
  4 AM, the lot may be full — more likely as the evening wears on,
  deterministic per trip seed. A spoken menu offers driving on to the next
  stop or shoulder parking: a full HOS reset but poor rest (fatigue floor
  of 30) and a 15 percent chance of a 150-dollar ticket.
- New manual page "Hours and rest"; F1 help on all new menus.
- New procedural sounds: `ambient/night` and `driver/yawn`
  (regenerate with `tools/generate_audio.py`).

### Fixed
- **Speech backend selection.** Prism's registry ranks NVDA above every
  other backend whether or not NVDA is running, so on machines without it
  the game bound to a dead NVDA connection and stayed silent. The backend
  choice is now validated against actual runtime support and falls down
  the priority list (JAWS, One Core, SAPI, Speech Dispatcher, ...) to the
  best backend that can really speak. A new
  `FREIGHT_FATE_SPEECH_BACKEND=<name>` environment variable forces a
  specific backend for troubleshooting.

### Compatibility
- Save format version is now 3. Old v2 profiles and pre-1.5 mid-trip
  snapshots load cleanly, defaulting to a fresh HOS clock and a rested
  driver.

## 1.4.0 — 2026-06-10

### Added
- **Home terminal picker.** A new career now asks where it should begin:
  after name entry, a fully spoken menu lists every city labeled by region
  ("Atlanta, the South"), with the usual arrow, Home/End, and first-letter
  navigation plus F1 help. Defaults to Chicago; Escape returns to name
  entry with the typed name intact. Existing profiles are untouched.
- **A real interstate network.** The map grows from 21 cities and 27 legs
  to 59 cities and 106 legs along real corridors (I-95, I-90, I-80, I-75,
  I-70, I-65, I-40, I-35, I-10, I-5, and more), so neighboring cities sit
  roughly 100-250 miles apart. Every new city has real coordinates for the
  live-weather feature, a weather region, and freight locations with
  regional identity: produce out of the Central Valley, autos around
  Detroit, electronics at the container ports, grain and livestock across
  the plains, machinery in the rust belt. Boston and Seattle are no longer
  dead ends; no city has fewer than two highways.
- **Career-arc job generation.** Rookie boards (levels 1-2) offer short
  regional work: mostly single-leg hops to neighboring cities, capped
  around 280-340 miles, with destinations weighted toward nearby cities so
  freight follows plausible lanes. The distance cap grows with level and
  cross-country hauls (600+ miles) unlock around level 4-5 as a dedicated
  long-haul slot on the board. A flat hookup fee keeps short early runs
  profitable after fuel.

### Compatibility
- All 21 original cities and all 27 original direct legs are preserved
  verbatim, so old profiles and mid-trip snapshots (`route_cities`) load
  and resume unchanged. A regression test pins every original adjacency.

## 1.2.1 — 2026-06-09

### Added
- **Mid-trip save and resume.** "Save and quit to main menu" while driving
  now snapshots the delivery — job, route, position on the route, clock,
  speeding strikes, and trip damage baseline — into the profile. Continue
  (and Load driver) resume the drive right where you left off, parked with
  the engine off, with a spoken recap of cargo, destination, remaining
  miles, and hours used. Construction and traffic zones reappear in the
  same places thanks to a persisted trip seed, and stops or cities already
  passed are not re-announced. The Load driver list shows mid-delivery
  profiles as "on the road to <city>".

### Fixed
- "Save and quit to main menu" no longer silently discards the delivery
  (previously Continue always returned to the city with the job gone).

## 1.2.0 — 2026-06-09

### Added
- **BASS audio backend** via [sound_lib](https://pypi.org/project/sound_lib/)
  (pinned `==0.8.8`; PyPI's version ordering for this package is broken and an
  unpinned install resolves to a stale 2022 build). The truck engine is now a
  single loop whose playback frequency tracks RPM in real time, smoothed with
  BASS attribute slides — no more four-band crossfade seams. pygame.mixer
  remains as an automatic fallback when sound_lib/BASS cannot initialize
  (`FREIGHT_FATE_AUDIO_BACKEND=pygame` forces it), and headless environments
  use BASS's "no sound" device so CI runs the full audio pipeline silently.
- **Garage upgrades** (Garage → Upgrades), money-gated and saved on the
  profile: engine tune (+10% torque per tier, two tiers), aerodynamic kit
  (−12% drag), long-range tank (+50 gallons), and reinforced brakes (fade
  onset pushed 150 degrees hotter). Upgrades feed straight into the driving
  physics.
- **A second truck**: the heavy hauler (Garage → Trucks) — a quarter more
  torque and a 200-gallon tank, but blunter aerodynamics and a thirstier
  engine. Buy it once, then switch between owned trucks at any garage.
- **Freight market**: every cargo class carries a pay multiplier (0.8–1.3)
  that drifts each in-game day on a seeded random walk persisted in the
  profile. Job descriptions call out tight and loose markets,
  and the job board opens with a spoken market watch headline.

### Changed
- Truck status and garage refueling respect the active truck's actual tank
  size instead of assuming 150 gallons.
- Save format version is now 2 (older saves load fine; new fields get
  defaults).

### Notes
- BASS is proprietary software, free for non-commercial use. If Freight Fate
  is ever sold commercially, a paid license from
  [un4seen developments](https://www.un4seen.com/bass.html#license) is
  required. See the README's license section.

## 1.1.0 — 2026-06-09

### Added
- **Real-world weather** (Settings → Weather source): live current
  conditions for each city from the free
  [Open-Meteo](https://open-meteo.com) API (no key required). WMO weather
  codes map onto the game's conditions, including strong-wind promotion.
  Fetches run in background threads with a 15-minute cache; offline or on
  any failure the simulated weather takes over seamlessly.
- City coordinates in the world data.
- With real weather enabled, route planning's W key speaks live conditions
  for the cities along the route, and the V key while driving reports
  "live conditions" for the city you are heading toward.

## 1.0.0 — 2026-06-09

First release. Complete rewrite of the prototype.

### Added
- Career mode: jobs, route planning, deliveries, money, experience levels,
  reputation, and cargo endorsements (refrigerated at level 2, high-value at
  level 4).
- Tuned Class 8 truck physics: ten-speed transmission (manual with clutch or
  automatic), torque curve, grades, traction limits, stalling, brake fade,
  engine braking, and realistic fuel economy (~6 mpg loaded).
- 21-city, 27-leg interstate network with Dijkstra route finding and multiple
  route options per job.
- Dynamic regional weather (eight conditions) affecting grip, drag, and safe
  speed, with forecasts and thunder.
- Trip events: construction and traffic zones, road hazards with reaction
  windows, rest stop refueling, out-of-fuel roadside rescue, speeding fines.
- Screen reader output through Prism (`prismatoid`): NVDA, JAWS, SAPI,
  VoiceOver, Speech Dispatcher, and more, with silent fallback.
- Fully synthesized CC0 sound library (43 effects) and three original music
  tracks, all reproducible from `tools/generate_audio.py`.
- RPM-crossfaded engine audio, speed-tracking road noise, weather ambience.
- Accessible UI: spoken menus with wrap-around and first-letter navigation,
  contextual F1 help, accessible text entry, three speech verbosity levels,
  imperial/metric units, and a visible text mirror of all speech.
- First-drive tutorial, six-page in-game manual.
- Atomic JSON saves with multiple driver profiles.
- uv-based packaging, cross-platform CI (Windows + Linux), 67-test suite.

### Removed
- SRAL DLL dependency (replaced by the Prism Python package).
- Legacy prototype source tree, duplicate data files, and debug artifacts.
