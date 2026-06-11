# Changelog

## Unreleased

### Added
- **Highway exits.** Rest stops now sit at proper exits. They are
  announced a few miles out ("Press X to take the exit for it"); X
  signals for the exit (and X again cancels), you slow to 45 or less for
  the ramp — any faster and you blow past it — then half a mile of ramp
  and brake to a stop, and the rest stop menu opens by itself. The ramp
  is off the highway: hazards and speeding checks pause while you are on
  it. Pressing T while stopped on the highway at a stop still works.
- **Cruise control.** K sets cruise at your current speed, like every
  real semi, and holds it with a slow throttle governor through grades.
  K again, any braking, the emergency brake, a stall, or taking an exit
  cancels it — and a hazard warning hands control straight back to you.
  Tab reports the set speed.
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

### Changed
- **Realistic deadlines.** Dispatch can no longer ask for the
  impossible. Deadlines are now built from the hours a law-abiding
  trucker actually needs — driving at an achievable 55 mph average, plus
  the 30-minute break every 8 driving hours and a 10-hour sleep for
  every 11-hour shift the distance demands — with 20 to 50 percent
  shipper slack and a flat hour for fuel on top. San Antonio to Dallas
  now quotes a workable 7-to-8-hour window instead of a sprint.
- The state trooper / law enforcement system is designed and documented
  at the top of ROADMAP.md as the next milestone (patrol intensity per
  corridor, CB chatter warnings, pull-overs reusing the X signal flow,
  immediate fines, and an enforcement setting).
- **Portable saves.** Profiles and settings now live in a `saves` folder
  inside the game's own directory (next to the executable in release
  builds, the project root from source) instead of the per-user data
  directory. Existing saves are migrated over automatically on first
  launch; the originals are left in place. `FREIGHT_FATE_DATA_DIR`
  still overrides the location.

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
  profile. Job descriptions call out hot, strong, soft, and cold markets,
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
