# Freight Fate

An accessible, audio-first cross-country trucking simulation. Haul freight
between more than 600 American cities, manage fuel, tolls, weather, and
deadlines, and build a driving career entirely by ear.

Freight Fate is designed for blind and low-vision players first: every screen
is fully voiced through your screen reader (NVDA, JAWS, SAPI, VoiceOver,
Speech Dispatcher, and more via [Prism](https://pypi.org/project/prismatoid/)),
and the road speaks to you through a rich procedural soundscape. A simple
visual display mirrors all speech for sighted players and helpers.

## Features

- **Career mode** — accept jobs inside metro freight markets, deadhead to
  specific origin facilities, deliver to specific receivers, earn money and
  experience, level through a 30-rank trucking career, unlock cargo
  endorsements, then buy into a leased-on owner-operator path when your career
  and working capital are ready.
- **Realistic freight markets** — the 623-city route graph acts as metro
  service areas, while each market expands into representative ports, rail and
  intermodal ramps, air cargo areas, parcel hubs, distribution centers, cold
  storage, food processors, farms/elevators, manufacturing plants, steel and
  automotive sites, chemical terminals, construction yards, mines/quarries,
  lumber/paper facilities, cross-docks, and company yards.
- **Real driving** — a tuned Class 8 truck simulation: 450 horsepower,
  ten gears (manual with clutch, or automatic), air-brake pressure,
  parking brakes, engine braking, grades, stalls, brake fade, and honest
  fuel economy.
- **Business progression** — choose a grounded company-driver carrier with
  assigned equipment plus modest wage and dispatch tradeoffs, or start as a
  higher-risk leased-on owner-operator with owned starter equipment and real
  operating costs. Owner-operators can add specialty trailer programs for
  reefer, flatbed, and bulk freight, then prepare for a limited own-authority
  direct-freight mode with trailer ownership at the end of the career arc.
- **Trucks and upgrades** — owner-operators can earn their way into a heavy
  hauler with more torque and a bigger tank (and worse aerodynamics), and
  outfit any truck with an engine tune, aerodynamic kit, long-range tank, or
  reinforced brakes. Every purchase changes the physics.
- **A living market** — each cargo class has a pay rate that drifts day by
  day, and each metro weights freight by regional specialization. The job
  board tells you when electronics are tight or bulk freight has gone loose;
  chase the tight markets.
- **A living road** — dynamic regional weather that changes grip and safe
  speeds, construction and traffic zones, road hazards that demand quick
  braking, curated rest stops and service plazas with parking certainty,
  carrier-paid toll-road settlement charges, and roadside rescue when you run dry.
- **Real-world weather (optional)** — flip Settings → Speech and weather →
  Weather source to
  "real world" and each city uses its live current conditions from the free
  [National Weather Service](https://www.weather.gov/documentation/services-web-api)
  API. If it is raining in Chicago right now, it is raining in your game. Works
  without an API key and falls back to simulated weather offline. A separate
  calendar setting lets career dates and seasons keep advancing while live
  conditions remain enabled.
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
  F1 help everywhere, on-demand information keys while driving, a message log
  you can walk back through from any screen, and a choice of terse or normal
  speech verbosity.
- **Discord Rich Presence (optional)** — when Discord is running, your profile
  can show what you are up to: in the main menu, at the terminal, driving a
  route, resting, or delivering, with the broad route and cargo. Only general
  game activity is shared — never your save files or personal details — and it
  is on by default but easily switched off under Discord presence on the
  Online menu, on the main menu. The game starts and runs perfectly whether or
  not Discord is open.

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

On Linux there is also a single-file AppImage
(`FreightFate-<version>-linux-x86_64.AppImage`): mark it executable and run
it, no extraction needed, and it works beyond Ubuntu (Fedora, Arch,
openSUSE). Since an AppImage is read-only, its saves live in
`~/.local/share/FreightFate`. The in-game updater works here too — it
downloads the new AppImage, swaps the file in place, and restarts the game.

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

The Rust port packages with the same tool: `uv run python
tools/build_release.py --rust` runs `cargo build --release -p freight-fate`
(add `--cargo-target-dir <dir>` to pick the Cargo target directory), then
stages `build/FreightFate/` in the layout the in-game updater already
expects -- `FreightFate.exe` (renamed from cargo's `freightfate.exe`), the
vendored SDL2, BASS and Prism libraries beside it, the runtime data tree
under `freight_fate/data/`, the sound and music packs, `build_info.json`
and the player docs -- and archives it under `dist/` exactly like the
Python build. The packs come from Git LFS, so a checkout that only has the
pointers is refused with a `git lfs pull` hint. The headless smoke of the
staged binary is opt-in (`--smoke`) until the Rust binary wires `--smoke`.

On Windows the build compiles with Visual Studio's C++ toolchain when
one is installed. Without it, Nuitka downloads a MinGW64 GCC toolchain
on first build, and the script caps compile parallelism to one job per
2 GB of RAM — the parallel compilers otherwise exhaust memory midway
through and the build dies with a GCC error. No build step needs
administrator rights, so if a build fails, re-run it in a normal
prompt and report the first error line rather than retrying elevated.

If the build succeeds but the archive seems to vanish on Windows, check
your antivirus: freshly built unsigned executables are sometimes
quarantined on sight. Add an exclusion for the `dist/` folder or restore
the file from quarantine.

## Controls

Freight Fate plays with the keyboard or a game controller, and both stay active
at all times. Spoken prompts name whichever you last used, so "press X to take
it" on the keyboard becomes "press D-pad down to take it" on a controller.

### Keyboard

#### Menus

| Key | Action |
| --- | --- |
| Up / Down | Navigate |
| Enter | Select |
| Escape | Back |
| Home / End | First / last item |
| Any letter | Jump to the next item starting with it |
| F1 | Contextual help |

#### Messages, on every screen

The message log works the same way everywhere in the game, driving included.
It keeps the last 200 things the game said, in one history shared by menu
speech and driving events.

| Key | Action |
| --- | --- |
| Comma | Repeat the last spoken line; press again quickly to step one line older each time |
| Period | Move toward newer messages |
| Ctrl+Comma | Jump to the oldest message |
| Ctrl+Period | Jump to the newest message |
| Left / Right bracket | Switch between all messages, general messages, and driving events |
| Ctrl+C | Copy the message you are on |

#### Driving

Moving the truck:

| Key | Action |
| --- | --- |
| Up arrow (hold) | Throttle |
| Down arrow (hold) | Brake |
| B (hold) | Emergency brake — the hardest possible stop |
| Left / Right arrow | Steer. With lane keeping on full, a tap changes lanes instead |
| E | Start / stop engine |
| P | Release / set parking brake. Setting it at speed grinds flat spots into the tread and costs real tire wear — it is the emergency backup, not a brake |
| H | Horn |

Gears and the engine brake:

| Key | Action |
| --- | --- |
| Left Shift (hold) | Clutch (manual mode) |
| W | Shift up a gear (manual mode) |
| Q | Shift down a gear (manual mode) |
| N | Neutral (manual mode) |
| Backspace | Reverse (manual mode) |
| Alt+T | Switch between automatic and manual shifting, mid-drive |
| J | Engine brake on / off |
| 1, 2, 3 | Engine brake stage (one, two, three) |
| Alt+J | Whether J arms the automatic engine brake or leaves it to you |

Speed control:

| Key | Action |
| --- | --- |
| K | Automatic speed control on / off. Parked with the brake set, it latches a high idle instead |
| Shift+K | Resume the last speed after braking cancelled it |
| Plus / minus (keypad too) | Raise / lower the remembered open-road target by 5 |

Route actions:

| Key | Action |
| --- | --- |
| X | Signal for the next announced exit, or cancel that signal. Also signals a pull-over when a trooper lights you up |
| T | Plan the next sleep-capable stop while rolling; at a stop, open its menu; fully stopped away from stops, open emergency shoulder sleep |
| Enter | Go inside on a city-service arrival, or open a facility arrival once fully stopped |
| Tab | Driving status menu |
| Escape | Pause menu |

Asking the truck and the road questions:

| Key | Action |
| --- | --- |
| Space | Speed, gear, RPM, the speed-control mode in use, and air pressure |
| S | Posted speed limit. On a ramp with a signal, the light and the distance to the stop bar |
| D | The one safe speed for right here — weather, an armed exit, and the bend ahead already folded in |
| G | The grade under the wheels, whether the truck is holding it, and the next grade ahead |
| R | Route progress, distance left, and where you are |
| Shift+R | Next listed highway exit |
| U | What is coming up: imposed limits, stops, exits, and bends |
| C | Clock, deadline, date and season, and the hours limit that comes first |
| Alt+A | Time at the wheel so far this shift |
| Alt+S | When your 30 minute break is due |
| Alt+D | What ends this shift, and where you can stop before it |
| F | Fuel and range |
| V | Weather and forecast |
| L | Lane position, and whether the lane beside you is open or blocked |
| I | Lane locator on / off — a soft tock once a beat, panned to where you sit inside your lane. Available on lane keeping partial or off |
| A | Repeat the last driving announcement |
| F1 | List all controls |
| Left or Right Ctrl | Stop the driving event voice mid-sentence |

The radio:

| Key | Action |
| --- | --- |
| M | Radio on / off |
| Page Down / Page Up | Tune to the next / previous receivable station (semicolon and apostrophe also work) |
| Ctrl + a tuning key | Jump a whole dial category |
| O | Save or unsave the current station as a favorite |
| Y | Station, volume, and streamer-safe status |

### Controller

Plug in an Xbox, PlayStation, or other compatible controller and the game picks
up the first one automatically. It detects a controller connected or unplugged
mid-game — unplugging pauses the drive — and you can switch back to the keyboard
at any time. Button names below use the Xbox layout; the equivalents map
automatically on other pads. Turn controller support off under Settings →
Gameplay → Controller if you prefer keyboard only.

#### Menus

| Button | Action |
| --- | --- |
| D-pad Up / Down | Navigate |
| D-pad Left / Right | Adjust the selected option (hold to repeat) |
| A | Select (like Enter) |
| B | Back (like Escape) |
| Back / Select | Contextual help (like F1) |

#### Driving

| Button | Action |
| --- | --- |
| Left stick | Steering |
| Right trigger | Throttle |
| Left trigger | Brake (press fully for the hardest stop) |
| Left bumper (LB) | Clutch (manual mode) |
| A | Shift up a gear (manual mode) |
| X | Shift down a gear (manual mode) |
| Y | Automatic speed control on / off |
| B | Speak speed, gear, RPM, speed-control mode, and air pressure |
| D-pad Up | Route progress |
| D-pad Down | Take exit / signal a pull-over |
| D-pad Left | Weather and forecast |
| D-pad Right | Clock, deadline, and the full hours of service report |
| Left stick click (L3) | Horn |
| Right stick click (R3) | Engine brake toggle |
| Start | Pause / resume |
| Back / Select | Controller help |

Hold the right bumper (RB) as a modifier for a second layer of driving bindings:

| Button | Action |
| --- | --- |
| RB + A | Start / stop engine |
| RB + B | Fuel and range |
| RB + Y | Release / set parking brake |
| RB + D-pad Up | Next listed highway exit |
| RB + D-pad Down | Open a route stop, or emergency shoulder sleep away from stops, when fully stopped. |
| RB + D-pad Left / Right | Lower / raise the open-road cruise target |
| RB + Start | Driving status menu |

The left and right triggers are analog: hold them wherever you like for partial
throttle or braking, rather than the ramped hold the arrow keys use. There is no
controller emergency brake — press the left trigger all the way for the hardest
stop.

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
uv run pre-commit install
uv run pre-commit install --hook-type pre-push
uv run pytest          # full test suite, headless
uv run ruff check src tests tools
```

The pre-commit hooks run Ruff lint fixes and formatting before commits. The
pre-push hook runs the release-note gate before publishing commits. It uses
`tools.release_notes check --base auto --head HEAD`, so user-facing changes need
a player-facing `CHANGELOG.md` entry unless the whole change set uses
`changelog: none` or `[skip changelog]`.

### World data

The route tools edit `src/freight_fate/data/world_source/`, but the game loads
the indexed `src/freight_fate/data/world_data/` tree. After changing world data,
regenerate the index so the two stay in sync:

```bash
uv run python tools/index_world.py          # rewrite world_data/ from world_source/
uv run python tools/index_world.py --check  # verify in sync (CI + pre-commit do this)
```

A pre-commit hook and a test both fail if `world_data/` drifts from the source,
so commit the regenerated `world_data/` files alongside your source edits.

Both trees are sharded by the state a leg starts in — `legs/TX.json`,
`legs/CA.json` — because a single file had reached 60 MB, past GitHub's warning
line and heading for its 100 MB limit. Tools never touch the shards directly:
`tools/world_source.py` gives them `load_world()`, which returns the whole world
as one dict, and `save_world(data)`, which writes only the shards that actually
changed. So a one-leg edit is a small reviewable diff, and the code that edits
world data is unchanged from when it was one file.

### Playtesting

Freight Fate is audio-first, so the way to review a playthrough is the transcript
of what the game says. `tools/playtest.py` drives the real game states headless
(no window, no speech) and prints that transcript:

```bash
uv run python tools/playtest.py                       # new-career delivery
uv run python tools/playtest.py --route "Newark->New York"   # one corridor
uv run python tools/playtest.py --route "New York->Boston" --events-only
```

Use `--route` to exercise a specific corridor after editing its route data. The
same harness backs the `@pytest.mark.smoke` delivery tests.

### Changelog and snapshots

Player-facing changes should add a short bullet under `## Unreleased` in
`CHANGELOG.md`. Developer snapshots use those curated entries for release
notes; they do not turn git commit subjects into player-facing copy.

Scheduled snapshots build only when new curated Unreleased entries are present,
or when a commit message includes `nightly: build` or `[nightly build]` for an
intentional snapshot refresh. Use `changelog: none` or `[skip changelog]` only
when every commit in the change set is non-user-facing.

### Sound pack for source builds

Career 1.9 stores its approved encrypted sound and music packs at
`src/freight_fate/sounds.pak` and `src/freight_fate/music.pak` using Git
Large File Storage (Git LFS).

On Windows, install Git LFS from PowerShell with Winget:

```powershell
winget install --id GitHub.GitLFS --exact --source winget
```

Open a new PowerShell window, then initialize Git LFS and update the checkout:

```powershell
git lfs install
git pull
```

On macOS or Linux, follow the
[Git Large File Storage installation instructions](https://git-lfs.com/), then
run `git lfs install` once for your user account before cloning or updating the
project.

A plain `git fetch` updates Git references and the small LFS pointers, but
does not update the working tree or download the packs. With Git LFS
installed, a normal `git pull` or checkout downloads both packs
automatically; a separate `git lfs pull` is not normally needed. If
`sounds.pak` or `music.pak` contains text beginning with
`version https://git-lfs.github.com/spec/v1` instead of binary pack data, run
`git lfs install` followed by `git lfs pull` from the repository root.

GitHub Actions uses an LFS-enabled checkout for jobs that test or package the
project. Loose fallback cues remain under `src/freight_fate/assets/sounds/`. See
[CREDITS.md](src/freight_fate/assets/sounds/CREDITS.md) for provenance and
licensing.

## License

Freight Fate is licensed under the
[PolyForm Noncommercial License 1.0.0](LICENSE): the source is public and free
to use, modify, and share for any noncommercial purpose, but only the copyright
holder may sell it or put it to commercial use. This is a source-available
license, not an OSI-approved open-source license. Bundled audio credits and
provenance are tracked in
[CREDITS.md](src/freight_fate/assets/sounds/CREDITS.md).

**BASS license caveat:** audio playback uses the
[BASS](https://www.un4seen.com/) library (through the `sound_lib` Python
package), which is proprietary and **free for non-commercial use only**. If
Freight Fate is ever sold commercially (Steam, itch.io paid downloads, and
so on), a paid license must be purchased from
[un4seen developments](https://www.un4seen.com/bass.html#license) first.
The same terms cover the bundled BASSHLS addon
(`src/freight_fate/lib/basshls.dll`), which lets the radio play HLS
streams; its license text ships alongside it.
The game falls back to pygame.mixer automatically when BASS is unavailable.
