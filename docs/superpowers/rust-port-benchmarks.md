# Rust port -- measured performance

Measured 2026-08-22 on the owner's machine, branch `feat/rust-port`. This
document answers one question and no other: on the numbers, what does the
port buy? Every figure below was produced by the two harnesses named here,
both of which are in the repo and can be re-run.

DRAFT -- Rust column pending. (Placeholder while the freight-fate crate is
mid-write by another task; this file is rewritten with both columns before
the work is reported.)

<!-- Whoever rewrites the sections above: the "Release size" section below is
     finished, measured work from a separate task. Keep it. -->

## Release size

Both builds are `tools/build_release.py --rust` on Windows, staged into
`build/FreightFate/` and archived as a portable zip. The only difference in
the payload rules between them is the baked data container: the earlier build
shipped the JSON tree under `freight_fate/data/`, the later one ships
`freight_fate/data/world.ffdata` instead.

| Component | Before (`nightly-20260822`) | After (`nightly-rustport`) | Change |
|---|---:|---:|---:|
| `FreightFate.exe` | 125,440 | 14,615,040 | +14,489,600 |
| Native libraries (SDL2, BASS + 4 plugins, Prism) | 2,982,560 | 2,982,560 | 0 |
| `freight_fate/data` | 141,937,342 | 7,312,812 | **-134,624,530** |
| `freight_fate/music.pak` | 261,358,688 | 261,358,688 | 0 |
| `freight_fate/sounds.pak` | 7,781,859 | 7,781,859 | 0 |
| `freight_fate/assets/sounds` | 63,747 | 63,747 | 0 |
| `freight_fate/lib` (BASS plugin fallback) | 23,848 | 23,848 | 0 |
| Docs + `build_info.json` | 809,612 | 809,612 | 0 |
| **Staged total** | **415,083,096** (395.9 MiB) | **294,948,166** (281.3 MiB) | **-120,134,930** |
| **Zip** | **281,269,031** (268.2 MiB) | **283,840,482** (270.7 MiB) | **+2,571,451** |

Two things move between those builds, and they move in opposite directions,
so the totals have to be read apart:

- **The bake.** 141,937,342 bytes of JSON become a 7,312,812-byte container.
  Inside the zip, the same content goes from 10,270,471 deflated bytes to
  7,314,108 -- the container is already zstd, so deflate adds nothing.
  So the bake is worth **128.4 MiB on disk and 2.8 MiB on the download**.
  The download barely moves because zip was already compressing that JSON
  roughly 14:1; the win is the installed footprint and the startup parse,
  not the bytes a player downloads.
- **The port itself.** `FreightFate.exe` went from 125,440 bytes to
  14,615,040 (5,604,418 deflated) between the two builds as the game landed.
  That +5.5 MB in the zip is what turns the bake's -2.96 MB into the +2.57 MB
  on the bottom line. It is progress, not regression.

`ff-bake`'s own per-section report on the same tree:

```
cities 205,618 -> 205,719      legs 94,444,986 -> 91,897 (1027.7x)
corridors -> 4,786,690         curves 12,705,282 -> 571,845 (22.2x)
city_services 15.1x            facility_approaches 25.6x
facility_endpoints 20.1x       local_approaches 26.3x
local_geometry 26.9x           street_limits/buffs/radio catalogs 3-10x
total 141,937,342 -> 7,312,780 (19.4x), 1291 legs, all with corridor detail
```

**What still dominates the download.** `music.pak` is 261,358,688 bytes --
89% of the staged folder and 92% of the zip after the bake. Nothing else in
the payload is within two orders of magnitude of it. Any further work on
download size is a decision about that one file (split it out as an optional
download, or leave it), not about anything the bake or the binary can do.

**Smoke.** `FreightFate.exe --smoke` under
`FREIGHT_FATE_NO_SPEECH=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` exits
0 on the staged `nightly-rustport` build, reaching "Choose career. 1 of 9."
in the transcript. It is a real data check, not just a boot: move
`world.ffdata` aside and the same run exits 101 on "the shipped world data
loads". Note that a manual smoke run leaves `saves/` and `logs/` in the
staged folder -- the pipeline strips those before archiving, a run by hand
does not.
