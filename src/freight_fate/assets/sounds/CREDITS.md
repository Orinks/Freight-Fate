# Sound and Music Credits

Sound effects in this directory come from a few sources, documented per file in
the tables below: original effects created for Freight Fate (no third-party
recordings or samples), weather and road loops produced with ElevenLabs sound
effects tooling, and -- in release builds only -- driving sounds cut from
commercially licensed sample libraries (see "Licensed Driving Sounds" below).
A number of in-cab cues were shared by Darren Duff early in the project; he
holds no license for that material (owner ruling 2026-07-22), so every Duff
row below is scheduled for replacement, not attribution -- most are already
superseded in release builds by the licensed overlay. The main menu, Open
Road, and Night Haul themes are Suno remakes created by the project owner. The July 2026 radio-station batch
(fifty-two tracks marked "2026-07 Zero batch" below) was composed with Suno V5
through the
Zero capability marketplace, with original lyrics written for Freight Fate;
those tracks are subject to the applicable Suno terms for the generating
account.

The default sound_lib weather loops were generated for Freight Fate with
ElevenLabs sound effects tooling, then reviewed and selected for the in-cab
weather mix.

The original project sound effects, and the ElevenLabs-generated assets
(original project assets subject to the applicable ElevenLabs terms for the
generating account), are part of Freight Fate and covered by the project's
PolyForm Noncommercial License (see `LICENSE` at the repository root): free to
use and share for noncommercial purposes, all other rights reserved by the
project owner. They are not dedicated to the public domain.

The in-cab truck sounds used for selected vehicle cues are authorized sounds
that [Darren Duff](https://darrenduff.com/) found, liked, and sent along for the
project. Darren also shared the louder/doubled-volume versions used for the
current idle, start, and shutdown cues.

## Vehicle Sounds

| Sound | File | Description |
| --- | --- | --- |
| Truck idle, interior | `engine/idle.ogg` | In-cab idle loop, shared by Darren Duff |
| Truck start, interior | `engine/start.ogg` | In-cab engine-start cue, shared by Darren Duff |
| Truck shutdown, interior | `engine/shutdown.ogg` | In-cab shutdown cue, shared by Darren Duff |
| Truck horn, interior | `vehicle/horn.ogg` | In-cab horn cue (trimmed from Take 2), shared by Darren Duff |
| Gear shift, interior | `vehicle/gear_shift.ogg` | In-cab gear-shift cue (split from a two-shift source), shared by Darren Duff |
| Parking brake release, interior | `vehicle/brake_release.ogg` | In-cab air-brake cue, shared by Darren Duff |
| Parking brake set, interior | `vehicle/brake_set.ogg` | In-cab brake-set cue, shared by Darren Duff |
| Driver yawn | `driver/yawn.ogg` | Drowsiness yawn cue, shared by Darren Duff |
| Air dryer purge | `vehicle/air_dryer_purge.ogg` | ElevenLabs-generated compressor cut-out purge, played when air pressure is ready |
| Low air buzzer | `vehicle/low_air_buzzer.ogg` | ElevenLabs-generated low-air-pressure / spring-brake warning buzzer |
| Highway road bed | `vehicle/road.ogg` | ElevenLabs-generated in-cab road ambience |
| Car pass-by | `traffic/car_pass.ogg` | ElevenLabs-generated nearby passenger-car pass-by cue |
| Box truck pass-by | `traffic/box_truck_pass.ogg` | ElevenLabs-generated nearby medium-truck pass-by cue |
| Semi pass-by | `traffic/semi_pass.ogg` | ElevenLabs-generated nearby tractor-trailer pass-by cue |
| State trooper pass-by | `traffic/trooper_pass.ogg` | ElevenLabs-generated patrol-car pass-by cue without siren |
| Lane drift | `vehicle/lane_drift.ogg` | ElevenLabs-generated directional lane drift beep |
| Lane centered | `vehicle/lane_centered.ogg` | ElevenLabs-generated centered-lane confirmation chime |
| Turn signal | `vehicle/turn_signal.ogg` | ElevenLabs-generated in-cab indicator clicks for exit and pull-over signaling |
| Tire screech | `vehicle/tire_screech.ogg` | ElevenLabs-generated emergency-braking skid for microsleep forced stops |
| Brake squeal | `vehicle/brake_squeal.ogg` | ElevenLabs-generated overheated-brake squeal past the fade temperature |
| Air pressurization fill | `vehicle/air_pressurize.ogg` | Original parametric DSP loop (seeded frequency-domain synthesis, `sound-test/air_fallback.py`); superseded in release builds by the licensed overlay version |

## Licensed Driving Sounds (release builds only)

These assets ship inside release builds via the local `sounds-licensed/`
overlay and are never committed to the repository: they are cut from
commercially licensed sample-library recordings (Splice subscriptions held by
the project maintainers) whose license covers synchronized use in the finished
game but is per-seat and non-transferable, so the source samples cannot be
redistributed. A source checkout falls back to the committed cues above.

| Game file(s) | Built from | Source pack |
| --- | --- | --- |
| `engine/idle`, `engine/mid`, `engine/high`, `engine/rev_launch`, `engine/rev_load` | Steady holds and real acceleration pulls cut from the `SemiTruckMac_S08IN.896` interior driving take | Splice -- Large Vehicles |
| `engine/low` | The 896 mid cut pitched 1150 to 950 rpm by resampling (`sound-test/engine_low_950.py`) | Splice -- Large Vehicles |
| `vehicle/shift_manual_01`..`15`, `vehicle/shift_auto_01`..`15` | Real gear changes (manual: clutch squeaks; automatic: shorter disengage) cut from `SemiTruck_S08IN.854/.855/.859` and `SemiTruckMac_S08IN.896` | Splice -- Large Vehicles |
| `vehicle/brake_clunk_01`..`14` | Percussive valve/actuation onsets from `SemiTruckBrake_S08IN.913`-`.917` and `BantamBrakeMach_S08IN.62` (`sound-test/brake_banks.py`) | Splice -- Large Vehicles / Industry Vol. 1 |
| `vehicle/ebrake` | The full sustained Bantam air event, `BantamBrakeMach_S08IN.62` | Splice -- Industry Vol. 1 |
| `vehicle/brake_hiss_bed` | Resynthesized (frequency-domain, seeded phase) from the de-whistled averaged spectra of `SemiTruckBrake_S08IN.917`, `SemiTruckAirBrake_BWU.95`, `AirBrake_BW.20321` (`sound-test/brake_hiss_synth.py`) | Splice -- Large Vehicles / Industry Vol. 1 |
| `vehicle/air_pressurize` | Resynthesized air-fill hiss from a licensed air-release spectrum with a compressor-pump whisper (`sound-test/pressurize.py`) | Splice -- Large Vehicles / Industry Vol. 1 |

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
| Local turn left | `events/turn_left.ogg` | ElevenLabs-generated falling two-note turn chime, panned left at playback |
| Local turn right | `events/turn_right.ogg` | Rising mirror of the left-turn chime (note order swapped via `tools/mirror_turn_chime.py`), panned right at playback |
| Local turn ahead | `events/turn_ahead.ogg` | ElevenLabs-generated single-tone straight-ahead cue, loudness-normalized |
| Ramp light red | `events/ramp_light_red.ogg` | ElevenLabs-generated low two-tone stop cue for a red ramp-terminal light |
| Ramp light green | `events/ramp_light_green.ogg` | ElevenLabs-generated go cue for a green ramp-terminal light, loudness-normalized |
| Police siren | `events/police_siren.ogg` | ElevenLabs-generated trooper pull-over siren wail |
| CB radio chatter | `events/cb_radio_chatter.ogg` | ElevenLabs-generated CB squelch and chatter for bear and enforcement heads-up cues |
| Spike strip | `events/spike_strip.ogg` | ElevenLabs-generated spike-strip puncture/air-hiss for felony stops |
| Hazard clear | `events/hazard_clear.ogg` | ElevenLabs-generated confirmation cue when a hazard has been safely passed |
| Rest stop at night | `poi/rest_stop_night.ogg` | Parked rest-stop ambience loop |
| Weigh station lane | `poi/weigh_station_lane.ogg` | Parked weigh-station lane ambience loop |
| Facility gate | `poi/facility_gate.ogg` | ElevenLabs-generated loading-dock gate ambience loop |
| Dock and deliver | `poi/dock_and_deliver.ogg` | Destination docking action cue |
| Truck stop by day | `ambient/truck_stop.ogg` | ElevenLabs-generated daytime truck-stop lot ambience loop |
| Warehouse interior | `ambient/warehouse.ogg` | ElevenLabs-generated warehouse dock interior ambience loop |
| Night driving | `ambient/night.ogg` | In-cab night ambience loop, shared by Darren Duff |

## Music

| Track | File | Description |
| --- | --- | --- |
| Headlights West | `music/menu_theme.ogg` | Suno remake for the main menu |
| Keys To The Rig | `music/menu_first_rig.ogg` | First-owned-truck career menu bed |
| Regional Lines | `music/menu_regional_carrier.ogg` | Regional carrier career menu bed |
| Yard Lights | `music/menu_fleet_owner.ogg` | Fleet-owner career menu bed |
| Coast To Coast Ledger | `music/menu_coast_to_coast.ogg` | Coast-to-coast career menu bed |
| Million Mile Morning | `music/menu_legendary_haul.ogg` | Late-career menu bed |
| Midnight Keys | `music/menu_theme_night.ogg` | Night piano ballad menu bed (career loaded after dark) |
| Open Road | `music/open_road.ogg` | Suno remake for daytime driving |
| Desert Two-Lane | `music/drive_desert_two_lane.ogg` | Spacious daytime desert drive bed |
| Mountain Grade | `music/drive_mountain_grade.ogg` | Measured daytime mountain drive bed |
| Rain-Day Cruise | `music/drive_rain_day_cruise.ogg` | Gentle rainy daytime drive bed |
| Urban Roll | `music/drive_urban_roll.ogg` | Light heavy-traffic daytime drive bed |
| Dawn Push | `music/drive_dawn_push.ogg` | Soft early-morning daytime drive bed |
| Night Haul | `music/night_haul.ogg` | Suno remake for night driving |
| Midnight Interstate | `music/night_midnight_interstate.ogg` | Quiet nighttime highway bed |
| Neon Truck Stop | `music/night_neon_truck_stop.ogg` | Soft night truck-stop approach bed |
| Rainy Night Miles | `music/night_rainy_miles.ogg` | Sparse rainy night drive bed |
| Lonely Plains | `music/night_lonely_plains.ogg` | Open nighttime plains drive bed |
| Mountain Night Pass | `music/night_mountain_pass.ogg` | Quiet mountain night drive bed |
| Small Hours | `music/night_small_hours.ogg` | Late-night piano ballad drive bed |
| Backroads Sunrise | `music/radio_country_backroads.ogg` | ElevenLabs-composed country song for regional radio |
| Two-Lane Towns | `music/radio_country_two_lane.ogg` | ElevenLabs-composed classic country song for regional radio |
| Diesel Heart | `music/radio_country_diesel_heart.ogg` | ElevenLabs-composed country rock song for regional radio |
| Open Throttle | `music/radio_rock_open_throttle.ogg` | ElevenLabs-composed highway rock anthem for regional radio |
| Night Shift | `music/radio_rock_night_shift.ogg` | ElevenLabs-composed organ-driven rock song for regional radio |
| Chrome Horizon | `music/radio_rock_chrome_horizon.ogg` | ElevenLabs-composed heartland rock song for regional radio |
| Delta Mile | `music/radio_blues_delta_mile.ogg` | ElevenLabs-composed delta blues song for regional radio |
| Crossroad Coffee | `music/radio_blues_crossroad_coffee.ogg` | ElevenLabs-composed soul blues song for regional radio |
| Low Beams | `music/radio_night_low_beams.ogg` | ElevenLabs-composed late-night jazz instrumental for the Night Line and the night menu rotation |
| High Plains Wind | `music/drive_high_plains_wind.ogg` | Suno-composed warm high-plains Americana bed for the in-game radio (2026-07 Zero batch) |
| Open Sky Run | `music/drive_open_sky_run.ogg` | Suno-composed breezy open-sky Americana bed for the in-game radio (2026-07 Zero batch) |
| Golden Hour Freeway | `music/drive_golden_hour_freeway.ogg` | Suno-composed golden-hour heartland drive bed for the in-game radio (2026-07 Zero batch) |
| Amber Lanes | `music/drive_amber_lanes.ogg` | Suno-composed warm sunset freeway drive bed for the in-game radio (2026-07 Zero batch) |
| River Valley Roll | `music/drive_river_valley_roll.ogg` | Suno-composed rolling folk-rock valley bed for the in-game radio (2026-07 Zero batch) |
| Green Mile Bend | `music/drive_green_mile_bend.ogg` | Suno-composed easy fingerpicked river-road bed for the in-game radio (2026-07 Zero batch) |
| County Line Cruise | `music/drive_county_line_cruise.ogg` | Suno-composed laid-back twangy cruising bed for the in-game radio (2026-07 Zero batch) |
| Two-Lane Daydream | `music/drive_two_lane_daydream.ogg` | Suno-composed relaxed two-lane country-rock bed for the in-game radio (2026-07 Zero batch) |
| Chrome Creek | `music/drive_chrome_creek.ogg` | Suno-composed breezy slide-guitar roots bed for the in-game radio (2026-07 Zero batch) |
| Silver Current | `music/drive_silver_current.ogg` | Suno-composed sparkling slide-guitar morning bed for the in-game radio (2026-07 Zero batch) |
| Quiet Mile | `music/night_quiet_mile.ogg` | Suno-composed calm electric-piano night bed for the in-game radio (2026-07 Zero batch) |
| Soft Shoulder | `music/night_soft_shoulder.ogg` | Suno-composed soft ambient night-highway bed for the in-game radio (2026-07 Zero batch) |
| Starlight Grade | `music/night_starlight_grade.ogg` | Suno-composed gentle piano mountain-night bed for the in-game radio (2026-07 Zero batch) |
| High Beam Hush | `music/night_high_beam_hush.ogg` | Suno-composed hushed strings-and-piano night bed for the in-game radio (2026-07 Zero batch) |
| Last Diner Open | `music/radio_night_last_diner.ogg` | Suno-composed quiet late-night diner ballad for the in-game radio (2026-07 Zero batch) |
| Third Shift Waltz | `music/radio_night_third_shift_waltz.ogg` | Suno-composed gentle waltz for night workers for the in-game radio (2026-07 Zero batch) |
| County Fair | `music/radio_country_county_fair.ogg` | Suno-composed upbeat county-fair country song for the in-game radio (2026-07 Zero batch) |
| Porch Light | `music/radio_country_porch_light.ogg` | Suno-composed warm homecoming country song for the in-game radio (2026-07 Zero batch) |
| Wildflower Mile | `music/radio_country_wildflower_mile.ogg` | Suno-composed hopeful springtime country song for the in-game radio (2026-07 Zero batch) |
| Dust and Daylight | `music/radio_country_dust_and_daylight.ogg` | Suno-composed gritty outlaw country song for the in-game radio (2026-07 Zero batch) |
| Blue Ridge Morning | `music/radio_country_blue_ridge_morning.ogg` | Suno-composed upbeat bluegrass instrumental for the in-game radio (2026-07 Zero batch) |
| Appalachian Sunrise | `music/radio_country_appalachian_sunrise.ogg` | Suno-composed bright mountain bluegrass instrumental for the in-game radio (2026-07 Zero batch) |
| Steel String Sunday | `music/radio_country_steel_string_sunday.ogg` | Suno-composed lazy pedal-steel instrumental for the in-game radio and the day menu rotation (2026-07 Zero batch) |
| Dobro Dusk | `music/radio_country_dobro_dusk.ogg` | Suno-composed mellow dobro country instrumental for the in-game radio and the day menu rotation (2026-07 Zero batch) |
| Mile Marker Moon | `music/radio_country_mile_marker_moon.ogg` | Suno-composed moonlit homesick country waltz for the in-game radio (2026-07 Zero batch) |
| Paper Town | `music/radio_country_paper_town.ogg` | Suno-composed wistful small-town country song for the in-game radio (2026-07 Zero batch) |
| Tailgate Summer | `music/radio_country_tailgate_summer.ogg` | Suno-composed rowdy lakeside party country song for the in-game radio (2026-07 Zero batch) |
| Grandpa's Radio | `music/radio_country_grandpas_radio.ogg` | Suno-composed tender heirloom-radio country ballad for the in-game radio (2026-07 Zero batch) |
| Thunder County | `music/radio_rock_thunder_county.ogg` | Suno-composed storm-charged seventies rock anthem for the in-game radio (2026-07 Zero batch) |
| Midnight Arcade | `music/radio_rock_midnight_arcade.ogg` | Suno-composed neon eighties arena rock song for the in-game radio (2026-07 Zero batch) |
| Neon Avenue | `music/radio_rock_neon_avenue.ogg` | Suno-composed late-night organ-driven rock groove for the in-game radio (2026-07 Zero batch) |
| Ember Sky | `music/radio_rock_ember_sky.ogg` | Suno-composed hopeful heartland rock song for the in-game radio (2026-07 Zero batch) |
| Glass Highway | `music/radio_rock_glass_highway.ogg` | Suno-composed melodic highway rock instrumental for the in-game radio and the day menu rotation (2026-07 Zero batch) |
| Mercury Miles | `music/radio_rock_mercury_miles.ogg` | Suno-composed soaring lead-guitar rock instrumental for the in-game radio (2026-07 Zero batch) |
| Switchback | `music/radio_rock_switchback.ogg` | Suno-composed funky seventies rock instrumental for the in-game radio (2026-07 Zero batch) |
| Hairpin | `music/radio_rock_hairpin.ogg` | Suno-composed wah-driven mountain rock instrumental for the in-game radio (2026-07 Zero batch) |
| Wildfire Line | `music/radio_rock_wildfire_line.ogg` | Suno-composed driving fire-crew hard rock anthem for the in-game radio (2026-07 Zero batch) |
| Silver Falcon | `music/radio_rock_silver_falcon.ogg` | Suno-composed female-fronted muscle-car rocker for the in-game radio (2026-07 Zero batch) |
| Last Ferry Home | `music/radio_rock_last_ferry_home.ogg` | Suno-composed warm harbor-dusk rock song for the in-game radio (2026-07 Zero batch) |
| Static and Stars | `music/radio_rock_static_and_stars.ogg` | Suno-composed wide-open night-sky heartland rock for the in-game radio (2026-07 Zero batch) |
| Greywater Quay | `music/radio_rock_greywater_quay.ogg` | Suno-composed folk-rock tribute to Saltwake's Greywater Quay for the in-game radio (2026-07 Zero batch) |
| Inland Sea | `music/radio_rock_inland_sea.ogg` | Suno-composed heartland rock song about the Great Salt Lake for the in-game radio (2026-07 Zero batch) |
| Raincheck | `music/radio_blues_raincheck.ogg` | Suno-composed slow rained-out electric blues for the in-game radio (2026-07 Zero batch) |
| Magnolia Porch | `music/radio_blues_magnolia_porch.ogg` | Suno-composed warm porch-evening southern soul for the in-game radio (2026-07 Zero batch) |
| Neon and Bourbon | `music/radio_blues_neon_bourbon.ogg` | Suno-composed smoky Chicago bar-band blues for the in-game radio (2026-07 Zero batch) |
| Freight Yard Moon | `music/radio_blues_freight_yard_moon.ogg` | Suno-composed midnight rail-yard blues instrumental for the in-game radio and the night menu rotation (2026-07 Zero batch) |
| Midnight Siding | `music/radio_blues_midnight_siding.ogg` | Suno-composed slow-burning night blues instrumental for the in-game radio and the night menu rotation (2026-07 Zero batch) |
| Slow Train Shuffle | `music/radio_blues_slow_train_shuffle.ogg` | Suno-composed rolling harmonica blues instrumental for the in-game radio (2026-07 Zero batch) |
| Boxcar Stroll | `music/radio_blues_boxcar_stroll.ogg` | Suno-composed easy boxcar harmonica instrumental for the in-game radio (2026-07 Zero batch) |
| Grits and Gasoline | `music/radio_blues_grits_and_gasoline.ogg` | Suno-composed greasy roadside blues rocker for the in-game radio (2026-07 Zero batch) |
| Paycheck Friday | `music/radio_blues_paycheck_friday.ogg` | Suno-composed swinging horn-section jump blues for the in-game radio (2026-07 Zero batch) |
| Levee Moon | `music/radio_blues_levee_moon.ogg` | Suno-composed smoky riverside delta soul for the in-game radio (2026-07 Zero batch) |

## Radio Hosts And Static

| Sound | File | Source |
| --- | --- | --- |
| Roadhouse host breaks | `music/host_roadhouse_01.ogg` … `music/host_roadhouse_06.ogg` | ElevenLabs TTS host segments for the Freight Fate Roadhouse |
| Night Line host breaks | `music/host_nightline_01.ogg` … `music/host_nightline_06.ogg` | ElevenLabs TTS host segments for the Freight Fate Night Line |
| Radio static burst | `radio/static_burst.ogg` | Procedurally generated band-limited noise (tools/generate_radio.py) |
| Overspeed dash chime | `vehicle/overspeed_chime.ogg` | Procedurally synthesized two-partial bell strike (deterministic numpy/soundfile recipe, 2026-07-14) |
