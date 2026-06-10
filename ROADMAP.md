# Freight Fate Roadmap

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
