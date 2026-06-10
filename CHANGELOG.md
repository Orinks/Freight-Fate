# Changelog

## 1.3.0 — 2026-06-10

### Added
- **Cargo weight drives the physics.** The truck's mass is now split into
  the tractor (plus empty trailer) and the cargo actually on board, set
  from the active job's listed weight. A 25-ton haul pulls away slower,
  climbs grades slower, needs noticeably more road to stop (brakes deliver
  a fixed maximum force sized for the rated gross weight, capped by tire
  grip), and burns more fuel per mile; an 8-ton load feels distinctly
  livelier. A max-weight load still climbs a 6% mountain grade in low
  gears. The Tab status report now includes the load
  ("hauling 25 tons of machinery").
- **Audio lane keeping** (Settings → Steering assist and lane drift:
  off / light / realistic, default off so existing saves drive exactly as
  before). The truck slowly drifts in its lane from gentle random wander,
  road curvature derived from each leg's terrain (flat legs are mostly
  straight, mountain legs wind continuously), and crosswind gusts scaled
  by the weather. Hold Left/Right arrows to steer back — analog-feel, like
  the throttle — with heavier loads responding more sluggishly. Every cue
  is audio: engine and road noise pan toward the side you are drifting, a
  rumble strip sounds in the matching ear at the lane edge, and staying
  fully off the lane for a couple of seconds scrubs speed, ticks cargo
  damage, and speaks a warning. Tuned gentle: a calm flat leg needs a
  correction roughly every half minute; mountain curves in a storm demand
  real attention. L speaks your lane position on demand, Tab includes it,
  F1 and the in-game manual document the new controls, and the tutorial
  teaches them when assist is on. Lane position and load survive mid-trip
  save and resume.
- Stereo panning support in both audio backends (BASS pan slides;
  pygame.mixer per-channel stereo volumes).

### Changed
- `TruckSpecs.mass_kg` is replaced by `tractor_mass_kg` +
  `TruckState.cargo_mass_kg`; brake strength is now rated against
  `brake_rated_mass_kg` instead of scaling with whatever is on board.

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
