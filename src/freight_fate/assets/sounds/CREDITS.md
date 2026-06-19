# Sound and Music Credits

Most sound effects and music tracks in this directory were procedurally
synthesized for Freight Fate by `tools/generate_audio.py` in this repository.
No third-party recordings or samples were used for those generated assets.

The default sound_lib weather loops were generated for Freight Fate with
ElevenLabs sound effects tooling, then reviewed and selected for the in-cab
weather mix.

Procedurally generated assets are dedicated to the public domain under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). ElevenLabs
generated assets are original project assets subject to the applicable
ElevenLabs terms for the generating account.

## Weather

| Sound | File | Description |
| --- | --- | --- |
| Light rain | `weather/rain_light.ogg` | Isolated in-cab light rain layer |
| Heavy rain | `weather/rain_heavy.ogg` | Isolated in-cab heavy rain layer |
| Snow and wind | `weather/snow_wind.ogg` | Dry snow against the truck cab |
| Fog horn | `weather/fog_horn.ogg` | Distant fog-horn ambience without engine bed |
| Wind | `weather/wind.ogg` | Isolated wind around the truck cab shell |
| Thunder | `weather/thunder.ogg` | Filtered in-cab thunder one-shot |

## Route Events And POIs

| Sound | File | Description |
| --- | --- | --- |
| Hazard warning | `events/hazard_warning.ogg` | Short in-drive hazard cue |
| Construction zone | `events/construction_zone.ogg` | Short construction-zone cue |
| Traffic slowing | `events/traffic_slowing.ogg` | Short traffic-slowing cue |
| Toll charged | `events/toll_charged.ogg` | Short toll/transponder cue |
| State crossing | `events/state_crossing.ogg` | Short route milestone cue |
| Inspection warning | `events/inspection_warning.ogg` | Short inspection/weigh-station cue |
| Rest stop at night | `poi/rest_stop_night.ogg` | Parked rest-stop ambience loop |
| Weigh station lane | `poi/weigh_station_lane.ogg` | Parked weigh-station lane ambience loop |
| Facility gate | `poi/facility_gate.ogg` | Parked pickup and destination gate ambience loop |
| Dock and deliver | `poi/dock_and_deliver.ogg` | Destination docking action cue |

## Music

| Track | File | Description |
| --- | --- | --- |
| Headlights West | `music/menu_theme.ogg` | Warm Americana for the main menu |
| Keys To The Rig | `music/menu_first_rig.ogg` | First-owned-truck career menu bed |
| Regional Lines | `music/menu_regional_carrier.ogg` | Regional carrier career menu bed |
| Yard Lights | `music/menu_fleet_owner.ogg` | Fleet-owner career menu bed |
| Coast To Coast Ledger | `music/menu_coast_to_coast.ogg` | Coast-to-coast career menu bed |
| Million Mile Morning | `music/menu_legendary_haul.ogg` | Late-career menu bed |
| Open Road | `music/open_road.ogg` | Easy mid-tempo groove for long hauls |
| Desert Two-Lane | `music/drive_desert_two_lane.ogg` | Spacious daytime desert drive bed |
| Mountain Grade | `music/drive_mountain_grade.ogg` | Measured daytime mountain drive bed |
| Rain-Day Cruise | `music/drive_rain_day_cruise.ogg` | Gentle rainy daytime drive bed |
| Urban Roll | `music/drive_urban_roll.ogg` | Light heavy-traffic daytime drive bed |
| Dawn Push | `music/drive_dawn_push.ogg` | Soft early-morning daytime drive bed |
| Night Haul | `music/night_haul.ogg` | Slow ambient pads for night driving |
| Midnight Interstate | `music/night_midnight_interstate.ogg` | Quiet nighttime highway bed |
| Neon Truck Stop | `music/night_neon_truck_stop.ogg` | Soft night truck-stop approach bed |
| Rainy Night Miles | `music/night_rainy_miles.ogg` | Sparse rainy night drive bed |
| Lonely Plains | `music/night_lonely_plains.ogg` | Open nighttime plains drive bed |
| Mountain Night Pass | `music/night_mountain_pass.ogg` | Quiet mountain night drive bed |

To regenerate the procedural assets from source (reproducible, seeded):

```
uv run python tools/generate_audio.py
```
