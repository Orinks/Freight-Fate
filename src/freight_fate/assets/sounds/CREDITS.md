# Sound and Music Credits

Every sound effect and music track in this directory was procedurally
synthesized for Freight Fate by `tools/generate_audio.py` in this repository.
No third-party recordings or samples were used.

All audio assets are original work and are dedicated to the public domain
under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). You may
copy, modify, and redistribute them for any purpose without attribution.

## Music

| Track | File | Description |
| --- | --- | --- |
| Headlights West | `music/menu_theme.ogg` | Warm Americana for the main menu |
| Open Road | `music/open_road.ogg` | Easy mid-tempo groove for long hauls |
| Night Haul | `music/night_haul.ogg` | Slow ambient pads for night driving |

To regenerate everything from source (reproducible, seeded):

```
uv run python tools/generate_audio.py
```
