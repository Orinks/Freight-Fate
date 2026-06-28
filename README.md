# Freight Fate

An accessible, audio-first cross-country trucking simulation. Haul freight
between more than 45 American cities, manage fuel, tolls, weather, and
deadlines, and build a driving career entirely by ear.

Freight Fate is designed for blind and low-vision players first: every screen
is fully voiced through your screen reader (NVDA, JAWS, SAPI, VoiceOver,
Speech Dispatcher, and more via [Prism](https://pypi.org/project/prismatoid/)),
and the road speaks to you through a rich procedural soundscape. A simple
visual display mirrors all speech for sighted players and helpers.

## Features

- **Career mode** — accept jobs inside metro freight markets, deadhead to
  specific origin facilities, deliver to specific receivers, earn money and
  experience, level up, and unlock cargo endorsements (refrigerated,
  heavy-haul, high-value).
- **Realistic freight markets** — the 59-city route graph acts as metro
  service areas, while each market expands into representative ports, rail and
  intermodal ramps, air cargo areas, parcel hubs, distribution centers, cold
  storage, food processors, farms/elevators, manufacturing plants, steel and
  automotive sites, chemical terminals, construction yards, mines/quarries,
  lumber/paper facilities, cross-docks, and company yards.
- **Real driving** — a tuned Class 8 truck simulation: 450 horsepower,
  ten gears (manual with clutch, or automatic), air-brake pressure,
  parking brakes, engine braking, grades, stalls, brake fade, and honest
  fuel economy.
- **Trucks and upgrades** — earn your way into a heavy hauler with more
  torque and a bigger tank (and worse aerodynamics), and outfit any truck
  with an engine tune, aerodynamic kit, long-range tank, or reinforced
  brakes. Every purchase changes the physics.
- **A living market** — each cargo class has a pay rate that drifts day by
  day, and each metro weights freight by regional specialization. The job
  board tells you when electronics are tight or bulk freight has gone loose;
  chase the tight markets.
- **A living road** — dynamic regional weather that changes grip and safe
  speeds, construction and traffic zones, road hazards that demand quick
  braking, curated rest stops and service plazas with parking certainty,
  carrier-paid toll-road settlement charges, and roadside rescue when you run dry.
- **Real-world weather (optional)** — flip Settings → Weather source to
  "real world" and each city uses its live current conditions from the free
  [National Weather Service](https://www.weather.gov/documentation/services-web-api)
  API. If it is raining in Chicago right now, it is raining in your game. Works
  without an API key and falls back to simulated weather offline.
- **Route planning** — route options per job with distance, highways, state
  context, grade/terrain, toll events, curated POIs, and weather forecasts.
  Geometry coverage is broad, while generated placeholder POIs are reported as
  data gaps instead of dispatch-ready truck stops. Facilities add local pickup
  and delivery realism without pretending that every suburb or shipper needs a
  separate highway node.
- **Original audio** — sound effects and music are original project assets,
  with sources documented in the audio credits. Audio
  plays through BASS (via [sound_lib](https://pypi.org/project/sound_lib/)),
  with the engine note pitch-tracking RPM in real time; pygame.mixer takes
  over automatically if BASS cannot initialize.
- **Screen reader native** — menus with first-letter navigation, contextual
  F1 help everywhere, on-demand information keys while driving, and three
  speech verbosity levels.
- **Discord Rich Presence (optional)** — when Discord is running, your profile
  can show what you are up to: in the main menu, at the terminal, driving a
  route, resting, or delivering, with the broad route and cargo. Only general
  game activity is shared — never your save files or personal details — and it
  is on by default but easily switched off in Settings → Gameplay → Discord
  presence. The game starts and runs perfectly whether or not Discord is open.

## Download and play

The easiest way to play is a prebuilt portable build from the
[releases page](https://github.com/Orinks/Freight-fate/releases):

- **Stable releases** (`v1.6.0` and so on) are the finished, numbered
  versions — pick the latest one.
- **Developer snapshots** (`nightly-...`, marked pre-release) are automatic
  nightly builds of work in progress: new features sooner, rough edges
  included. Heads up: a career saved on a developer snapshot may not load
  on an older stable release, so treat nightly saves as one-way.

Download the archive for your platform, extract it anywhere, and run the
game from the extracted `FreightFate` folder — `FreightFate.exe` on
Windows, `FreightFate` on macOS and Linux. There is nothing to install,
and the game is truly portable: your saves and settings live in a `saves`
folder inside the game folder, so you can move or copy the whole folder
(USB stick included) and your career travels with it. The game checks for
newer releases at the main menu and can download, install, and restart
itself — updates replace only the game's own files and never touch the
`saves` folder. Switch between stable and snapshot updates in Settings
under "Update channel".

For a complete player-facing guide to installing, careers, dispatch, driving,
route stops, saves, settings, audio, speech, and troubleshooting, see the
[Freight Fate Player Manual](docs/user-manual.md).

Want to help with code, docs, or world data? Start with
[CONTRIBUTING.md](CONTRIBUTING.md).

## Run from source

You need two tools installed and on your PATH:

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — manages
  Python and all dependencies for you (it downloads a suitable Python
  automatically, so a system Python is not required). The official
  installer puts uv on your PATH for you; close and reopen the terminal
  afterwards so the change takes effect.

  On Windows (PowerShell):

  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

  On macOS or Linux:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- [git](https://git-scm.com/downloads) — required even after cloning,
  because one dependency (`sound_lib`) installs straight from a git
  repository. If `uv sync` fails resolving `sound_lib`, a missing git is
  almost always why.

```bash
git clone https://github.com/Orinks/Freight-fate.git
cd Freight-fate
uv sync
uv run freight-fate
```

On Linux you also need SDL and Speech Dispatcher packages from your
distribution (for example `libsdl2-2.0-0` and `speech-dispatcher` on
Debian/Ubuntu).

## Build a standalone copy

`tools/build_release.py` produces the same portable build that the
releases page ships, using Nuitka. macOS uses Nuitka's app mode with
ad-hoc signing so Gatekeeper does not block the unsigned bundle on
downloaded builds:

```bash
uv sync --group build
uv run python tools/build_release.py
```

This freezes the game into `dist/FreightFate/`, boots it once as a smoke
check, and archives it as `dist/FreightFate-<version>-windows-portable.zip`
(or `-macos.zip` / `-linux-x64.tar.gz`). Useful flags:

- `--skip-smoke` — skip booting the frozen build (for cross-checking on
  headless machines).
- `--tag <label>` — override the version label in the archive name, as the
  nightly workflow does.

If the build succeeds but the archive seems to vanish on Windows, check
your antivirus: freshly built unsigned executables are sometimes
quarantined on sight. Add an exclusion for the `dist/` folder or restore
the file from quarantine.

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
| P | Release / set parking brake |
| Left Shift (hold) | Clutch (manual mode) |
| 1–0 | Gears 1–10 (manual mode) |
| N | Neutral (manual mode) |
| J | Engine brake toggle |
| H | Horn |
| X | Arm / cancel the next actionable exit |
| T | Refuel and rest (stopped at a rest stop) |
| Space | Speak speed, gear, RPM |
| Tab | Driving status menu |
| F | Fuel and range |
| C | Clock, deadline, ETA |
| R | Route progress |
| Shift+R | Next listed highway exit |
| L | Lane position |
| V | Weather and forecast |
| F1 | List all controls |
| Escape | Pause menu |

### Air-brake model

Freight Fate models air pressure without asking players to run a full CDL
inspection before every dispatch. A cold trip starts with low pressure and
the parking brake set. Start the engine, wait for the compressor to build
air to 100 psi, then press `P` to release the parking brake. Repeated brake
applications draw from separate truck and trailer air tanks, low air warns
around 60 psi, and spring brakes apply around 40 psi. Normal driving should
feel familiar; the extra detail mostly gives clearer warnings if you pump the
brakes hard, ignore low air, or drive damaged equipment. Press `Tab` while
driving to review primary, secondary, and trailer air, compressor state,
parking or spring brake state, and brake heat.

The thresholds are grounded in official CDL and air-brake references:
[FMCSA](https://www.fmcsa.dot.gov/sites/fmcsa.dot.gov/files/docs/brake_safety_systems_02-14.pdf)
describes typical 110-130 psi compressor cut-out, cut-in about 20 psi lower,
and an 85-to-100 psi build-up check; the
[California DMV](https://www.dmv.ca.gov/portal/handbook/commercial-driver-handbook/section-5-air-brakes/)
places low-air warnings between 55 and 75 psi; the
[Georgia DDS](https://dds.georgia.gov/section-52-53) describes spring-brake
and governor checks; and
[SGI](https://sgi.sk.ca/air-brake/-/knowledge_base/air-brake/air-governor)
lists 120-145 psi cut-out and 100 psi minimum cut-in. Build-up time is
compressed for playability so startup is a short, understandable pause
rather than minutes of waiting.

## Development

```bash
uv sync --group dev
uv run pre-commit install --hook-type pre-push
uv run pytest          # full test suite, headless
uv run ruff check src tests tools
```

The pre-push hook runs the release-note gate before publishing commits. It
uses `tools.release_notes check --base auto --head HEAD`, so user-facing
changes need a player-facing `CHANGELOG.md` entry unless the whole change set
uses `changelog: none` or `[skip changelog]`.

### Changelog and snapshots

Player-facing changes should add a short bullet under `## Unreleased` in
`CHANGELOG.md`. Developer snapshots use those curated entries for release
notes; they do not turn git commit subjects into player-facing copy.

Scheduled snapshots build only when new curated Unreleased entries are present,
or when a commit message includes `nightly: build` or `[nightly build]` for an
intentional snapshot refresh. Use `changelog: none` or `[skip changelog]` only
when every commit in the change set is non-user-facing.

Bundled audio assets ship as Ogg Vorbis files under
`src/freight_fate/assets/sounds/` — see
[CREDITS.md](src/freight_fate/assets/sounds/CREDITS.md) for provenance and
licensing.

## License

Code is [MIT](LICENSE). Bundled audio credits and licensing notes are tracked in
[CREDITS.md](src/freight_fate/assets/sounds/CREDITS.md).

**BASS license caveat:** audio playback uses the
[BASS](https://www.un4seen.com/) library (through the `sound_lib` Python
package), which is proprietary and **free for non-commercial use only**. If
Freight Fate is ever sold commercially (Steam, itch.io paid downloads, and
so on), a paid license must be purchased from
[un4seen developments](https://www.un4seen.com/bass.html#license) first.
The game falls back to pygame.mixer automatically when BASS is unavailable.
