# Channel 3000 clips (assets only; never merge)

The audio for Channel 3000, the in-game radio station at 87.7, staged for
`tools/build_channel3000.py` on the feature branch, which packs `clips/`
into `channel3000.pak` and copies `clips.json` to `data/channel3000.json`.
The plan is `docs/superpowers/plans/2026-10-06-channel-3000.md` on
`feat/channel-3000-radio`.

- `clips/*.opus`: Ogg Opus, 48 kbps stereo, 48 kHz, one static gain each to
  -18 LUFS (-1 dBTP ceiling), like music.pak.
- `clips.json`: kind, dayparts, opener, title and measured duration per clip.
- `stage_clips.py`: how they were made from the owner's local masters.
- `STATION.md`, `DAYTIME.md`, `NIGHT.md`: the station's briefs ("What plays
  when" is the schedule's spec).
