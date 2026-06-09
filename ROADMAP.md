# Freight Fate Roadmap

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
- [ ] Truck upgrades (engine, tank, aerodynamics) and new trucks
- [ ] Hours-of-service fatigue and mandatory rest planning
- [ ] Special event jobs (oversize loads, urgent medical freight)
- [ ] Trailer types with handling differences

### World
- [ ] More cities and regional highways
- [ ] Seasons and day/night cycle with audio shifts
- [ ] City-specific ambience and landmarks

### Business
- [ ] Company ownership: hire AI drivers, buy trucks
- [ ] Loans and insurance
- [ ] Market fluctuations in cargo rates

### Platforms and community
- [ ] Binary releases (PyInstaller) per platform
- [ ] Steam/itch.io distribution
- [ ] Localization of all speech strings
- [ ] Optional online leaderboards
