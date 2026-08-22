# Freight Fate Rust port — design

Date: 2026-08-22. Branch `feat/rust-port`, worktree `C:\Users\joshu\ff-rust`,
forked from `feat/career-1.9` at 44642ade.

## Goal

Port the shipped game — everything under `src/freight_fate/` — to Rust, end to
end, so the release is a native binary plus data instead of a Nuitka-frozen
Python tree. Behaviour is preserved to the spoken word: the existing pytest
suite is ported alongside each module and must pass against the Rust code.

Out of scope (stays Python): `tools/` (bake/enrich/build tooling, the
playtest watcher), CI data sweeps that only exercise tools. The Python
package stays in the repo until the Rust build is the release; it is the
reference implementation during the port.

## Shape

Cargo workspace at the repo root:

```
Cargo.toml                  workspace
crates/prism-sys            raw Prism FFI (from PortkeyDrop), extended
crates/prism                safe Prism wrapper (from PortkeyDrop)
crates/bass-sys             raw BASS FFI via libloading; vendored DLLs
crates/ff-core              pure logic: no SDL, no BASS, no Prism, no network
crates/freight-fate         the game: audio, speech, net, states, app; bin `freightfate`
```

Two game crates, not one, so a change in a state file does not rebuild the
world model; not more, because every further split is a boundary nobody
asked for.

`ff-core` modules mirror the Python packages: `pyrandom`, `pyfmt`, `units`,
`data`, `models`, `sim`, `speech_text`, `speech_pacing`, `message_log`,
`input_hints`, `settings`, `hos`, `timezones`, `engine_audio`, `rumble`,
`sound_catalog`, `music`, `radio_content`, `radio` (physics + catalog),
`audio_fades`, `assets_pack`, `cab_filter`, `achievements`, `profile_*`,
`cloud_save_integrity`, `save_migration`. `freight-fate` holds `audio`
(facade + BASS/null backends), `speech` (Prism backend + capture sink),
`controller`, `net`/`online_*`/`cloud_saves`/`updater`/`discord_presence`,
`states/*`, `app`, and the playtest harness.

## Platform layer decisions

| Concern | Python today | Rust | Why |
|---|---|---|---|
| Window, keyboard, game controller, rumble, clipboard | pygame-ce (SDL2) | `sdl2` crate, dynamic link against vendored prebuilt SDL2 (`vendor/sdl2/<os-arch>/`) | 1:1 GameController API, `SDL_VIDEODRIVER=dummy` headless (the test suite depends on it), rumble off the controller handle, UTF-8 clipboard. Building SDL from source fails on this machine (CMake 3.31 vs VS 18), prebuilt links in 2 s. |
| Audio | sound_lib (BASS) | `bass-sys`: hand-written `libloading` bindings for the ~15 BASS entry points the game uses, plugins `bassopus`, `bassflac`, `bass_aac`, `basshls` loaded if present | Mixtime position sync (horn loop), rate/volume slides, HLS + ICY radio have no pure-Rust equivalent. Same licence position as today. |
| Speech | prismatoid | `prism` + `prism-sys`, extended with `registry_id`/`registry_name`/`registry_priority`/`id_at`, `set_pitch`, voice count/name/set, `backend_speak`, the missing feature bits; `FREIGHT_FATE_PRISM_PATH` | Game's `pick_backend` is priority-driven and uses pitch + voice selection. |
| HTTP/TLS | urllib + certifi | `ureq` 3 (rustls) + `rustls-platform-verifier` | Platform roots (corporate proxies) plus Mozilla roots, as `net.ssl_context()` does now. |
| Crypto | cryptography, hmac | `ed25519-dalek` (verify_strict), `hmac`+`sha2`, hand-written canonical JSON (`js_number`) | Canonical bytes pinned by `test_cloud_saves` fixture. |
| Secret store | keyring | `keyring` 3 with native features on | Same service name `"Freight Fate driver token"`. |
| Discord | pypresence | `discord-rich-presence` | No asyncio leak workaround needed. |
| Archives | zipfile/tarfile/gzip/zlib | `zip`, `tar`, `flate2` | gzip level 9 mtime 0 for cloud content. |
| JSON | json | `serde`/`serde_json` | World data stays JSON; lazy corridors via `OnceCell`. |
| Randomness | `random.Random` | `pyrandom`: bit-exact MT19937 + CPython seeding (int, str via sha512), `random/uniform/randrange/randint/choice/choices/sample/expovariate/getstate/setstate` | 119 transcript tests pin seed-derived lines. |
| Float formatting | f-strings, `round()` | `pyfmt`: `round()` half-even, `round(x, n)`, `{:,.0f}` grouping; Rust `{:.N}` already matches Python on ties | Spoken strings are asserted verbatim. |

## Architecture of the game crate

- `trait Audio` with the `AudioEngine` facade surface (`play`, `start_loop`,
  `set_engine_rpm`, `hold_alert`, ... exactly the table in the audio map),
  implemented by `BassAudio` and `NullAudio`. Dead-man switches for held
  alerts/cues stay in the facade.
- `trait SpeechSink` with `Speech` (Prism, main + SAPI event channel, 3 s
  refresh poll, Narrator/UIA gating, retry-once) and `CaptureSpeech` (tests,
  transcripts). `GameContext::say`/`say_event` with the ladder, pacer,
  ducking, transcript logger and message log are ported first and tested
  without a window.
- `Ctx` is passed `&mut` into every state method; states are
  `Vec<Box<dyn State>>`. `DrivingState` is one struct with `impl` blocks per
  former mixin file.
- Background I/O: `std::thread` + `Arc<Mutex<Vec<T>>>`/`mpsc`, drained once per
  frame on the main thread — the same `take_*()` shape as today. No async
  runtime.
- Event pump: SDL `KeyDown` paired with the following `TextInput` so menus'
  first-letter jump, text entry and the `+`/`-` fallbacks keep working.
- Data: loaded from `src/freight_fate/data/` relative to the executable
  (frozen) or the repo (dev) through one `data_root()`; the Python package's
  data tree is the shipped data tree. `sounds.pak`/`music.pak` unchanged.

## Tests

- Each Python test file becomes a Rust test module next to the code it
  covers (`ff-core` unit tests) or an integration test in
  `crates/freight-fate/tests/` (app-shell, network-mock, audio-stub
  buckets). Test names keep the Python name so a diff of the two suites is
  greppable.
- `PlaytestHarness` is ported: headless `App`, `CaptureSpeech`, key
  injection, `start_route`, `drive_frames`, transcript metrics and the
  `assert_*` helpers. The 119 transcript tests run against it at
  `trip_seed = 0`.
- `tools/playtest_break.py` scenarios become a `freightfate --break-scenario`
  mode so the adversarial battery survives.
- Tool tests (`test_build_*`, `test_index_world`, ...) stay Python.

## Build and release

- `cargo build --release` produces `target/release/freightfate.exe` plus the
  vendored DLLs copied by build scripts. `tools/build_release.py` grows a
  Rust mode later (layout: exe, DLLs, `freight_fate/data/`, packs,
  `build_info.json`); not part of this port's first milestone.
- Linux/macOS: SDL2 and BASS libraries for those targets are vendored when
  available; the loader degrades (no audio / no speech) rather than failing to
  start, like Prism does today.

## Order of work

Foundation (serial): workspace, `pyrandom`, `pyfmt`, `units`, Prism
extension, `bass-sys`, SDL vendoring, `Speech`/`Audio` traits and their
test doubles. Then waves of parallel module ports following the dependency
layers from the core map (leaf modules → `data` → `sim` → `models.profile` →
audio/speech/controller/app shell → states → transcript tests). Each wave
compiles and its ported tests pass before the next starts.
