# BASS is fetched, not stored here

**The BASS binaries are not committed to this repository.** It is public
source, and un4seen's licence lets the game bundle BASS in a release for
free non-commercial use — but hosting someone else's proprietary binaries in
a source tree is a different thing from shipping them in a build, and the
owner's decision (2026-08-23) is not to.

Get them with:

```
uv run python tools/fetch_bass.py
```

That writes them into `vendor/windows-x86_64/`, where `build.rs` finds them
and stages them beside the test and game binaries. Every file is pinned by
sha256, so a silent change upstream is refused rather than absorbed — the
audio backend is where a quiet substitution would be hardest to notice.
`--check` verifies without writing, and `FREIGHT_FATE_BASS_PATH` overrides
the search entirely.

The pins name the builds the game has actually been played against: the ones
`sound_lib` ships and the Python release has always bundled. Checked against
un4seen on 2026-08-23, `bass.dll` and `basshls.dll` are byte-identical to the
current downloads; `bassflac.dll` and `bassopus.dll` are not, because upstream
has moved on, and the AAC add-on no longer sits at a guessable URL. So the
fetch prefers the local `sound_lib` copy and reaches the network only where
the pin still matches. Re-pinning is a deliberate job, not a bump: fetch,
listen to the engine ring and a live radio stream, then update the hashes.

What the fetch provides, and where each pinned build came from:

| File | Origin |
|---|---|
| `bass.dll` | BASS 2.4 core, as packaged in the `sound_lib` 0.8.8 Python wheel (`sound_lib/lib/`) |
| `bassopus.dll` | BASSOPUS add-on, same wheel |
| `bassflac.dll` | BASSFLAC add-on, same wheel |
| `bass_aac.dll` | BASS_AAC add-on, same wheel |
| `basshls.dll` | BASSHLS 2.4 add-on, from the Freight Fate Python tree (`src/freight_fate/lib/`), with its `basshls.txt` release note |

BASS and its add-ons are copyright Un4seen Developments Ltd. They are not
open source. The `sound_lib` wrapper around them is MIT-licensed (Christopher
Toth) but that licence covers the Python code only, not the DLLs.

## Licence position

BASS is free for non-commercial use. Distribution in a commercial product
requires a licence purchased from Un4seen (the BASS shareware/commercial
licence; see <https://www.un4seen.com/bass.html#license>). The add-ons
(BASSOPUS, BASSFLAC, BASS_AAC, BASSHLS) are "free to use with BASS", i.e.
they inherit the BASS licence terms. The Rust port takes exactly the same
licence position as the Python game it replaces, which ships these same
files through `sound_lib` and `src/freight_fate/lib/` today.

The BASSHLS release note reproduced in `windows-x86_64/basshls.txt` carries
Un4seen's own warranty disclaimer:

> TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, BASSHLS IS PROVIDED
> "AS IS", WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESSED OR IMPLIED ...
> YOU USE BASSHLS ENTIRELY AT YOUR OWN RISK.

The same disclaimer applies to `bass.dll` and the other add-ons per their
respective `bass.txt` / `bassopus.txt` / `bassflac.txt` / `bass_aac.txt`
release notes, which the `sound_lib` wheel does not include.

Only the Windows x86-64 build is pinned so far. Linux (`libbass.so`) and
macOS (`libbass.dylib`) builds go in sibling directories when they are
added; the loader degrades to no audio rather than failing to start when a
platform directory is absent.

SDL2 (zlib) and Prism (MPL-2.0) stay vendored, under `vendor/sdl2/` and
`crates/prism-sys/vendor/` — their licences permit redistribution without
question.
