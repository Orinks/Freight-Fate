# Freight Fate Roadmap

## Next up: state troopers and law enforcement

Speeding, HOS/ELD compliance, and route enforcement are now one visible
system instead of unrelated end-of-trip deductions and generic random
inspections. The first shipped slice uses route-backed contexts where the
current corridor data supports them: weigh-station POIs, construction
zones, checkpoints/high-patrol corridors, and seeded patrol windows.
Events carry evidence such as HOS/ELD violations or construction-zone
speeding, and serious HOS violations trigger an out-of-service 10-hour
reset instead of only a fine.

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

- **Patrol presence.** Each route leg gets a patrol intensity from its
  region and highway (urban corridors hot, empty plains cold, construction
  zones always hot), modulated by time of day (speed traps at rush hour,
  DUI patrols at night). The CB radio is the counterplay: chatter like
  "bear at mile marker 12" gives attentive players a spoken heads-up a
  few miles out.
- **Getting pulled over.** Speeding 10+ over inside a patrol's window (or
  blowing past a weigh station while flagged) triggers a siren behind you.
  The player must signal with X (reusing the exit system's muscle memory),
  brake to a stop on the shoulder, and sit through a spoken stop: license
  and logbook check, then a ticket, a warning (reputation and demeanor
  matter), or an order to a nearby weigh station for a full inspection.
- **Consequences.** Immediate fines replace the silent at-delivery
  deduction (escalating like HOS fines: 150 to 1,200 dollars), reputation
  hits, and an "out of service" order for serious HOS violations: 10
  hours parked where you stand. Ignoring the siren is a felony stop:
  spike strips ahead, a huge fine, and possibly losing the load.
- **Settings.** The normal HOS setting now defaults to realistic, keeps
  relaxed for accessibility and pacing, and labels the non-enforced mode
  as a debug bypass rather than ordinary play. A separate law-enforcement
  setting remains open only if enforcement grows beyond HOS and route
  safety evidence.
- **Audio needed.** Siren approach/behind loops, CB radio squelch and
  chatter, an officer voice channel (the SAPI event voice fits), spike
  strip. All synthesizable in `tools/generate_audio.py` first, replaced
  by real recordings later.
- **Open questions.** Should troopers notice damage (a visibly wrecked
  truck invites a stop)? Do warnings expire? Does reputation lower the
  ticket odds, or just the fine?

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

- [x] Optional real-world weather per city via the Open-Meteo API
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
- [ ] Cargo loading/securing minigame
- [x] Hours-of-service fatigue and mandatory rest planning (1.5.0)
- [x] Highway exits: signal with X, slow for the ramp, brake to the stop
- [x] Cruise control (K), with hazard and braking auto-cancel
- [x] Region-flavored road hazards (dust devils, deer, rockfall, ...)
- [x] HOS-aware realistic deadlines (driving + breaks + sleep + slack)
- [ ] State troopers and law enforcement (designed above, next milestone)
- [ ] Special event jobs (oversize loads, urgent medical freight)
- [ ] Trailer types with handling differences

### World
- [x] More cities and regional highways (1.4.0)
- [x] Day/night cycle with audio shifts (1.5.0); seasons still open
- [ ] City-specific ambience and landmarks

### Business
- [ ] Company ownership: hire AI drivers, buy trucks
- [ ] Loans and insurance

### Platforms and community
- [ ] Binary releases (PyInstaller) per platform
- [ ] Steam/itch.io distribution
- [ ] Localization of all speech strings
- [ ] Optional online leaderboards
