# Freight Fate

An accessible, audio-first cross-country trucking simulation. Haul freight
between 21 American cities, manage fuel, weather, and deadlines, and build a
driving career — entirely by ear.

Freight Fate is designed for blind and low-vision players first: every screen
is fully voiced through your screen reader (NVDA, JAWS, SAPI, VoiceOver,
Speech Dispatcher, and more via [Prism](https://pypi.org/project/prismatoid/)),
and the road speaks to you through a rich procedural soundscape. A simple
visual display mirrors all speech for sighted players and helpers.

## Features

- **Career mode** — accept jobs at city freight locations, deliver on time,
  earn money and experience, level up, and unlock cargo endorsements
  (refrigerated, high-value).
- **Real driving** — a tuned Class 8 truck simulation: 450 horsepower,
  ten gears (manual with clutch, or automatic), engine braking, grades,
  stalls, brake fade, and honest fuel economy.
- **Trucks and upgrades** — earn your way into a heavy hauler with more
  torque and a bigger tank (and worse aerodynamics), and outfit any truck
  with an engine tune, aerodynamic kit, long-range tank, or reinforced
  brakes. Every purchase changes the physics.
- **A living market** — each cargo class has a pay rate that drifts day by
  day. The job board tells you when electronics are hot or bulk freight has
  gone cold; chase the strong markets.
- **A living road** — dynamic regional weather that changes grip and safe
  speeds, construction and traffic zones, road hazards that demand quick
  braking, rest stops for refueling, and roadside rescue when you run dry.
- **Real-world weather (optional)** — flip Settings → Weather source to
  "real world" and each city uses its live current conditions from the free
  [Open-Meteo](https://open-meteo.com) API. If it is raining in Chicago right
  now, it is raining in your game. Works without an API key and falls back to
  simulated weather offline.
- **Route planning** — multiple route options per job with distance, highways,
  terrain, and weather forecasts.
- **Original audio** — every sound effect and all three music tracks are
  procedurally synthesized and dedicated to the public domain (CC0). Audio
  plays through BASS (via [sound_lib](https://pypi.org/project/sound_lib/)),
  with the engine note pitch-tracking RPM in real time; pygame.mixer takes
  over automatically if BASS cannot initialize.
- **Screen reader native** — menus with first-letter navigation, contextual
  F1 help everywhere, on-demand information keys while driving, and three
  speech verbosity levels.

## Installation

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Orinks/Freight-fate.git
cd Freight-fate
uv sync
uv run freight-fate
```

On Linux you may need SDL and Speech Dispatcher development packages
(`libsdl2`, `speech-dispatcher`).

## Controls

### Menus

| Key | Action |
| --- | --- |
| Up / Down | Navigate |
| Enter | Select |
| Escape | Back |
| Home / End | First / last item |
| Any letter | Jump to the next item starting with it |
| F1 | Contextual help |

### Driving

| Key | Action |
| --- | --- |
| Up arrow (hold) | Throttle |
| Down arrow (hold) | Brake |
| E | Start / stop engine |
| Left Shift (hold) | Clutch (manual mode) |
| 1–0 | Gears 1–10 (manual mode) |
| N | Neutral (manual mode) |
| J | Engine brake toggle |
| H | Horn |
| T | Refuel and rest (stopped at a rest stop) |
| Space | Speak speed, gear, RPM |
| Tab | Full status report |
| F | Fuel and range |
| C | Clock, deadline, ETA |
| R | Route progress |
| V | Weather and forecast |
| F1 | List all controls |
| Escape | Pause menu |

## Development

```bash
uv sync --dev
uv run pytest          # full test suite, headless
uv run ruff check src tests tools
uv run python tools/generate_audio.py   # regenerate all audio from source
```

The entire sound library is produced by `tools/generate_audio.py` with seeded
randomness — see [CREDITS.md](src/freight_fate/assets/sounds/CREDITS.md).

## License

Code is [MIT](LICENSE). All bundled audio is
[CC0](https://creativecommons.org/publicdomain/zero/1.0/).

**BASS license caveat:** audio playback uses the
[BASS](https://www.un4seen.com/) library (through the `sound_lib` Python
package), which is proprietary and **free for non-commercial use only**. If
Freight Fate is ever sold commercially (Steam, itch.io paid downloads, and
so on), a paid license must be purchased from
[un4seen developments](https://www.un4seen.com/bass.html#license) first.
The game falls back to pygame.mixer automatically when BASS is unavailable.
