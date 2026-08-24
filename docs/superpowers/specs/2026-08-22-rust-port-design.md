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
crates/bass-sys             raw BASS FFI via libloading; DLLs fetched, not committed
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
| Audio | sound_lib (BASS) | `bass-sys`: hand-written `libloading` bindings for the ~15 BASS entry points the game uses, plugins `bassopus`, `bassflac`, `bass_aac`, `basshls` loaded if present. BASS is un4seen's and proprietary, so it is fetched by `tools/fetch_bass.py` (sha256-pinned) rather than committed to this public repo | Mixtime position sync (horn loop), rate/volume slides, HLS + ICY radio have no pure-Rust equivalent. Same licence position as today. |
| Speech | prismatoid | `prism` + `prism-sys`, extended with `registry_id`/`registry_name`/`registry_priority`/`id_at`, `set_pitch`, voice count/name/set, `backend_speak`, the missing feature bits; `FREIGHT_FATE_PRISM_PATH` | Game's `pick_backend` is priority-driven and uses pitch + voice selection. |
| HTTP/TLS | urllib + certifi | `ureq` 3 (rustls) + `rustls-platform-verifier` | Platform roots (corporate proxies) plus Mozilla roots, as `net.ssl_context()` does now. |
| Crypto | cryptography, hmac | `ed25519-dalek` (verify_strict), `hmac`+`sha2`, hand-written canonical JSON (`js_number`) | Canonical bytes pinned by `test_cloud_saves` fixture. |
| Secret store | keyring | `keyring` 3 with native features on | Same service name `"Freight Fate driver token"`. |
| Discord | pypresence | `discord-rich-presence` | No asyncio leak workaround needed. |
| Archives | zipfile/tarfile/gzip/zlib | `zip`, `tar`, `flate2` | gzip level 9 mtime 0 for cloud content. |
| JSON | json | `serde`/`serde_json` | The data tree is authored and reviewed as JSON; the release ships it baked (see Baked data). Lazy corridors via `OnceCell` on both paths. |
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
  data tree is the source of truth. A release ships it baked into one
  `world.ffdata` beside the loose files (see Baked data below);
  `sounds.pak`/`music.pak` unchanged.

## Baked data

The shipped data folder is ~142 MB of JSON, 94 MB of it the fifty state leg
shards. The heavy per-mile corridor is already lazy, but the *parse* is not:
serde_json walks every byte of those shards at startup to hand each lazy leg
its raw `Value`, which is ~0.25 s before the menu in release and several
hundred MB of retained `Value` trees. `ff_core::data::baked` replaces that
with one memory-mapped binary container, `freight_fate/data/world.ffdata`.

**Format.** A 32-byte header (magic `FFDATA\0\0`, u32 format version, flags,
then the directory's offset and length), the section payloads, then the
directory itself as a bincode `Vec<Section>` of `{name, offset, stored, raw,
codec}`. A section is stored raw, as one zstd frame, or -- for the corridors
-- as a *region* of independent zstd frames that each leg addresses by its
own offset, so driving one leg decompresses one leg. A container whose
version does not match the build is refused by name, with the re-bake command
in the message; it is never half-read.

**What is eager.** The city table (already parsed, market-expanded and
validated) and every leg's endpoint fields plus its corridor offset. That is
two small sections. Everything else -- each leg's corridor, the five
nationwide side maps, the screened curve table -- is decoded on first touch,
exactly where the JSON path decoded it on first touch. `street_limits.json`,
`buffs.json` and the two radio catalogs ride along as their compressed JSON
*text* and are parsed by the same parsers, because they are small and hold
free-form JSON the model keeps as `Value`.

**Measured** (owner's machine, 2026-08-22, release profile): 142 MB of JSON
becomes a 7.3 MB container; `World::load()` goes from 248 ms to 24 ms cold;
one leg's corridor decompresses and decodes in 0.09 ms. Baking takes ~3 s.

**Both paths stay alive.** The JSON tree always wins where it exists, so a
source checkout and the whole test suite behave exactly as before; the
container is consulted only where the loose file is absent. The baker runs
the shipped loaders (`World::load_from_json`, `curves::build_from_sources`,
`world_local_data::load_*`) rather than parsing anything itself, so the two
cannot describe different worlds. `crates/ff-core/tests/data_baked.rs` bakes
the real tree and compares the two worlds field by field.

**Re-baking.** The bake is deterministic -- same tree, byte-identical file --
so a rebuild diffs as unchanged and `--check` is a byte comparison:

```
cargo run --release -p ff-core --bin ff-bake -- \
    --data-dir src/freight_fate/data --out <dir>/world.ffdata
cargo run --release -p ff-core --bin ff-bake -- \
    --data-dir src/freight_fate/data --out <dir>/world.ffdata --check
```

`tools/build_release.py --rust` runs the baker itself and ships the container
*instead of* the JSON tree, refusing a payload that carries both.

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
  vendored DLLs copied by build scripts. `tools/build_release.py --rust`
  stages exe, DLLs, `freight_fate/data/world.ffdata` (baked by `ff-bake`),
  packs and `build_info.json`.
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
