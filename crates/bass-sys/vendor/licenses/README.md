# Vendored BASS redistributables

The files under `vendor/<os>-<arch>/` are the unmodified BASS 2.4 binaries
from Un4seen Developments (<https://www.un4seen.com/>), taken as shipped:

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

Only the Windows x86-64 build is vendored so far. Linux (`libbass.so`) and
macOS (`libbass.dylib`) builds go in sibling directories when they are
added; the loader degrades to no audio rather than failing to start when a
platform directory is absent.
