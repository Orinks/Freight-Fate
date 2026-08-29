# Freight Fate

An accessible, audio-first cross-country trucking simulation. Haul freight
between more than 600 American cities, manage fuel, tolls, weather, and
deadlines, and build a driving career entirely by ear.

Freight Fate is designed for blind and low-vision players first: every screen
is fully voiced through your screen reader (NVDA, JAWS, SAPI, VoiceOver,
Speech Dispatcher, and more through the native Prism speech bridge),
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
  with sources documented in the audio credits. The Rust audio engine plays
  them through BASS, with the engine note pitch-tracking RPM in real time. If
  BASS is unavailable, the game continues with a silent audio backend rather
  than failing to start.
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

- **Stable releases** are the finished, numbered versions — pick the latest
  one.
- **Career 1.9 tester builds** (`1.9-tester-YYYYMMDD`, marked pre-release)
  are packaged snapshots of this branch. They are not the public 1.8
  `nightly-YYYYMMDD` snapshots from `dev`. Heads up: a career saved on a
  tester build may not load on an older stable release, so treat tester
  saves as one-way.

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

Career 1.9 is a native Rust game. Python is not part of the gameplay runtime;
it remains in this repository only for build, packaging, data-generation, and
other maintainer tools.

Best path, in this order:

1. Install [Rust](https://www.rust-lang.org/tools/install) through `rustup`.
   The repository's `rust-toolchain.toml` pins the toolchain. Cargo.toml
   sets the minimum supported Rust version at 1.95.
2. Clone Career 1.9 with Git. Git LFS is not required on current
   `feat/career-1.9`.
3. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
   fetch BASS.
4. Run the Rust game with Cargo.
5. For a portable zip, use the release script below.

```bash
git clone --branch feat/career-1.9 https://github.com/Orinks/Freight-Fate.git
cd Freight-Fate
uv sync
uv run python tools/fetch_bass.py
cargo run --release -p freight-fate
```

`src/freight_fate/sounds.pak` is a regular git file, about 7.8 MB. You do
not need Git LFS. If that file is 132 bytes of pointer
text, you are
on an old commit, not current Career 1.9.

`music.pak` is not in git. A silent-audio source run is fine without it.
A release zip needs it, and `tools/build_release.py` fetches it when you
set `FREIGHT_FATE_MUSIC_URL` (see Sound and native libraries below).

The first Cargo build takes longer because it compiles the workspace. Later
runs reuse `target/`. On Windows, SDL2 and Prism are already vendored and are
staged beside the executable automatically. If BASS has not been fetched, the
game still starts but audio is silent.

On Linux, install your distribution's SDL2 and Speech Dispatcher runtime
packages if they are not already present. Platform-native speech and audio
library availability currently varies; Windows is the primary alpha-test
target for Career 1.9.

### Installing uv

On Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

On macOS or Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen the terminal afterwards so the updated PATH takes effect.

## Build a standalone copy

The Career 1.9 release tool uses Python as packaging glue around the Rust
compiler. It builds the native executable, bakes the large JSON world into a
compact data container, stages the runtime libraries and player documents,
checks the packaged payload, and creates the portable archive:

```bash
uv sync --group build
uv run python tools/fetch_bass.py
uv run python tools/build_release.py --rust --smoke
```

The staged folder is `build/FreightFate/`. The finished archive is written as
`dist/FreightFate-<version>-windows-portable.zip` on Windows, with matching
macOS and Linux archive names on those platforms. The package contains
`FreightFate.exe` (renamed from Cargo's `freightfate.exe`), native SDL2, BASS,
and Prism libraries where available, baked world data, sound and music packs,
`build_info.json`, and player documentation.

Useful flags:

- `--smoke` — boot the staged Rust build headlessly and verify that its data
  and audio assets load. This is recommended for a release-ready local build.
- `--skip-smoke` — override `--smoke` when booting the staged build is not
  possible on the current machine.
- `--tag <label>` — override the version label in the archive name. For a
  Career 1.9 tester zip use `1.9-tester-YYYYMMDD`, never `nightly-YYYYMMDD`.
- `--cargo-target-dir <dir>` — use a different Cargo target directory.

### Publish a Career 1.9 tester build

Do not tag 1.9 testers as `nightly-YYYYMMDD`; that family is the public 1.8
snapshot stream from `dev`. Build on `feat/career-1.9`, then create a
GitHub prerelease aimed at this branch:

```bash
uv run python tools/build_release.py --rust --smoke --tag 1.9-tester-YYYYMMDD
gh release create 1.9-tester-YYYYMMDD --repo Orinks/Freight-Fate --target feat/career-1.9 --prerelease --title "Freight Fate 1.9 tester YYYY-MM-DD" dist/FreightFate-1.9-tester-YYYYMMDD-windows-portable.zip
```

The Dropbox tester zip can stay. The in-game updater on a 1.9 packaged
build follows these `1.9-tester-YYYYMMDD` prereleases when the Update
channel is set to snapshot.

`sounds.pak` ships in the clone as a regular git file. `music.pak` is fetched
at package time from `FREIGHT_FATE_MUSIC_URL`, not cloned. Packaging still
refuses a 132-byte LFS pointer; that means the checkout is an old commit.
No build step needs administrator rights; if a build fails, rerun it in a
normal terminal and report the first error rather than retrying elevated.

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

Gameplay code and gameplay tests for Career 1.9 live in the Cargo workspace.
Use the Rust checks for gameplay changes:

```bash
cargo fmt --all --check
cargo clippy --all-targets --locked -- -D warnings
cargo test -p ff-core
cargo test -p freight-fate
```

Python remains supported for repository tooling. When changing packaging,
world-data generation, release notes, or another Python tool, set up its
environment and run focused Python checks for that tool:

```bash
uv sync --group dev --group build
uv run pytest tests/test_build_release.py
uv run ruff check tools tests
```

Do not add Python gameplay implementations or Python gameplay regressions to
Career 1.9. The older Python package remains temporarily as migration
reference material and for tool compatibility, not as the 1.9 runtime.

The pre-push hook runs the release-note gate before publishing commits.
User-facing changes need a player-facing `CHANGELOG.md` entry unless the
entire change set is non-player-facing and uses `changelog: none` or
`[skip changelog]`.

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
of what the game says. The Rust playtest harness drives the real game states
headlessly and is used by the Cargo integration tests. Run a focused transcript
test by name while iterating, then the whole game crate before landing:

```bash
cargo test -p freight-fate --test it transcript_shane_deadline -- --nocapture
cargo test -p freight-fate
```

The maintained Python scripts under `tools/` may still prepare data, launch a
manual test scenario, or watch its log. They are helpers around the Rust game;
they are not a second gameplay implementation or substitute test suite.

### Changelog and snapshots

Player-facing changes should add a short bullet under `## Unreleased` in
`CHANGELOG.md`. Developer snapshots use those curated entries for release
notes; they do not turn git commit subjects into player-facing copy.

Scheduled snapshots build only when new curated Unreleased entries are present,
or when a commit message includes `nightly: build` or `[nightly build]` for an
intentional snapshot refresh. Use `changelog: none` or `[skip changelog]` only
when every commit in the change set is non-user-facing.

### Sound and native libraries for source builds

Career 1.9 stores its approved encrypted sound pack at
`src/freight_fate/sounds.pak` as a regular git blob (about 7.8 MB). Git LFS
is not required. The larger private `music.pak` is a local build asset and
is not stored in Git.

If `sounds.pak` is 132 bytes of Git LFS pointer text, the checkout is an
old commit. Update to current `feat/career-1.9` instead of installing Git
LFS.

The private music pack is downloaded only when a release build needs it.
Ask a maintainer for a temporary private download URL, then set it in the
current session; do not commit the URL.

PowerShell:

```powershell
$env:FREIGHT_FATE_MUSIC_URL = "<temporary private URL>"
$env:FREIGHT_FATE_MUSIC_SHA256 = "50F5440EB478F1E0E630E65081D83E6C308F48A6AA3EA5FE67C7DD1A7F50A8BB"
uv run python tools/build_release.py --rust --skip-smoke
```

bash:

```bash
export FREIGHT_FATE_MUSIC_URL="<temporary private URL>"
export FREIGHT_FATE_MUSIC_SHA256="50F5440EB478F1E0E630E65081D83E6C308F48A6AA3EA5FE67C7DD1A7F50A8BB"
uv run python tools/build_release.py --rust --skip-smoke
```

The release script downloads `music.pak` only when it is absent, verifies the
optional SHA-256 value, and keeps the downloaded pack local.

Loose fallback cues remain under `src/freight_fate/assets/sounds/`. See
[CREDITS.md](src/freight_fate/assets/sounds/CREDITS.md) for provenance and
licensing.

The Rust build also needs BASS for audible output. Because BASS is proprietary,
its binaries are downloaded rather than committed to this public repository:

```bash
uv run python tools/fetch_bass.py
uv run python tools/fetch_bass.py --check
```

The fetcher verifies pinned hashes and stages the libraries where Cargo and the
release packager expect them. SDL2 and Prism libraries for supported targets
are kept in the repository and copied beside Cargo's executable automatically.

## License

Freight Fate is licensed under the
[PolyForm Noncommercial License 1.0.0](LICENSE): the source is public and free
to use, modify, and share for any noncommercial purpose, but only the copyright
holder may sell it or put it to commercial use. This is a source-available
license, not an OSI-approved open-source license. Bundled audio credits and
provenance are tracked in
[CREDITS.md](src/freight_fate/assets/sounds/CREDITS.md).

**BASS license caveat:** audio playback uses the
[BASS](https://www.un4seen.com/) library through Freight Fate's Rust bindings.
BASS is proprietary and **free for non-commercial use only**. If
Freight Fate is ever sold commercially (Steam, itch.io paid downloads, and
so on), a paid license must be purchased from
[un4seen developments](https://www.un4seen.com/bass.html#license) first.
The same terms cover the bundled BASSHLS addon
(`basshls.dll`), which lets the radio play HLS streams; its license text ships
alongside it. When BASS is unavailable, the Rust game uses a silent backend
instead of pygame.
