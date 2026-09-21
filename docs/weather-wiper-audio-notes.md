# Weather + wiper audio — design notes (brainstorm, 2026-07-09)

Owner's spec for a 1.9-line physics + sound feature. Status: idea capture,
not scheduled. Reference feel: MSFS rain-on-windshield, made *legible* for
audio-first play.

## The core mechanic

The windshield is a blind driver's view: the lane-guidance sound lives
there. Rain degrades windshield clarity (faster at speed); running the
wipers restores it at their sweep rate. As clarity drops, the lane-keeping
bed blurs — masked, smeared, harder to center on. One keypress of wipers
brings your "vision" back.

Guardrail: degrade lane/road cues only. Spoken GPS, warnings, and any
safety speech stay fully intelligible at all times.

## Weather model

- Upgrade rain from a per-trip scalar to a continuous rate at positions
  along the leg. Legs now carry real `route_points` geometry, so weather
  can be cellular: you drive into a storm around a mile marker, through
  its peak, and out the far side.
- Deterministic and offline first, then a live ladder on top (owner,
  2026-07-09 — wants moving systems you "follow across the country"):
  1. **Baked climate** (default): region-by-month distributions, seeded
     per trip. Offline, deterministic, always works.
  2. **Forecast-locked live** (recommended live default): lock the FIELD,
     not the frame — fetch Open-Meteo's hourly forecast timeline (~48 h)
     along the route corridor once at dispatch and freeze it. The game
     clock samples the forecast at the game-time instant, so cells MOVE
     during the trip while replays stay deterministic and no mid-trip
     connection is needed. Also sidesteps FSX-style time-compression
     weirdness.
  3. **True live re-poll** for long real-time sessions: refresh the field
     mid-trip; log every sample into the trip record so saves stay
     coherent; fall back to the frozen field if the connection drops.
  4. **Bring-your-own-key premium** provider slot for weather nuts
     (radar-grade granularity). US bonus: the NWS API (api.weather.gov)
     is free, keyless, and carries live severe-weather ALERTS — a tornado
     warning over the CB is real data.
  5. **Actual-conditions mode** (observations/radar, not forecasts):
     - Free US: NWS station observations; NOAA MRMS radar (~1 km grid,
       ~2-minute updates, free on AWS Open Data — self-hostable as an
       ff-radar service beside the ORS/Overpass containers; sample the
       grid at the truck's coordinates for measured rain intensity);
       Synoptic Data mesonet stations.
     - Premium keys: Xweather/Vaisala (source-level obs, own lightning
       network, road-conditions endpoints — unusually trucking-shaped),
       Tomorrow.io minute nowcasts, IBM/Weather Underground PWS network,
       RainViewer radar tiles, OpenWeatherMap/Weatherbit/Visual Crossing.
     - Nowcasts (radar extrapolated 0-2 h) are the natural data source
       for the premium radar upgrade's "cell hits you in twenty minutes"
       line.
     - Tradeoff to expose honestly: actual-conditions follows the WALL
       clock (real noon storm during sim midnight — the FSX quirk);
       forecast-locked mode follows game time.

## Hosting and cost architecture

- Default live weather is serverless: each player's game calls
  Open-Meteo / NWS directly (keyless; a two-hour drive is ~60 calls —
  trivially light per player).
- A shared community weather relay earns its keep only for MRMS radar:
  ingest the raw GRIB2 feed once (a few GB/day), serve tiny
  rain-at-coordinates JSON to every player. The weather field is shared,
  so a thousand players cost barely more than one. NOAA data is public
  domain — redistribution is legally clean — and the relay gives the
  game one stable schema plus coordinate privacy.
- Premium feeds can never be relayed (commercial ToS forbid
  redistribution) — premium stays bring-your-own-key. Xweather's free
  tier (15,000 calls/month) comfortably covers an individual player;
  its paid tiers (~EUR 300/month per million calls) are business-scale
  and irrelevant here.
- Pilot on the MS-02 (ff-radar container behind a tunnel, beside
  ff-ors/ff-overpass) to prove real costs; graduate to a small VPS as
  project infrastructure if adopted. The relay is always optional —
  baked and forecast-locked modes never depend on it.

## Sound layers

- **Rain bed:** two or three intensity loops crossfaded by local rain
  rate, modulated by vehicle speed. Moving: patter smeared on glass plus
  tire wash. Parked: slower, fatter drumming on the cab roof. Stopping at
  a rest area in a storm should sound like it.
- **Snow:** nearly silent by design. Low-pass the world, muffle traffic
  and tires, add wind. The quiet itself is the ice warning; pairs with
  winter grip physics and future chain laws.
- **Thunder:** a seeded generative scheduler over a pool of samples —
  near cracks vs. distant rumbles, randomized spacing and distance so it
  never audibly loops.
- **Wipers:** real swipe-thunk per pass. Off / intermittent / low / high
  on one key; intermittent interval can track vehicle speed like real
  trucks. Mismatch is audible skill feedback: squeak-drag when the glass
  is too dry for the setting, swipes drowned by patter when a setting too
  slow.

## Weather radar (truck upgrade)

Spoken weather-ahead feedback as purchasable equipment — cheap to build,
because the forecast-locked field already holds the route's weather; the
radar just speaks data the base rig keeps secret. You are buying
information (the assists-are-equipment principle again).

- **CB chatter (free):** vague, social — "drivers say it's a mess past
  Amarillo." Same emitter pattern as the planned bear reports.
- **Basic radar (upgrade):** distance and type — "rain ahead, about
  thirty miles."
- **Premium radar (upgrade):** intensity, movement, clearing time —
  "heavy cell at mile one-forty, moving east; wait forty-five minutes and
  you miss the worst of it." Relays live NWS severe-weather alerts when
  live weather is on.
- Both an on-demand query key ("weather ahead?") and proactive callouts,
  matching the planned exit-readout interaction shape.
- The decision it unlocks: wait it out (costs deadline clock — perhaps at
  a truck stop, or the brisket wall) vs. drive through (costs grip, lane
  clarity, hydroplaning risk). Only meaningful because cells move.

## Cross-links

- Hydroplaning: rain rate x speed x tire wear (existing tire/weather plan).
- Wiper blades as a truck-stop consumable: worn blades streak and squeak;
  buy replacements at truck stops (rides the rig-wear + truck-stop
  economy plans).
- Sound sourcing: NAS library first, ElevenLabs for clean-license gaps
  (same plan as the jake brake).

## Decided

No-wipers degrades ONLY the lane-keeping bed (owner, 2026-07-09). GPS and
all speech stay clear — real-world logic: rain never garbled a GPS
speaker.

## Headlights (owner extension, same session — "this is all connected")

Darkness is the one condition a blind player cannot perceive, so the game
must telegraph it before it may penalize it.

- **Unified visibility-clarity model:** rain x wipers AND darkness x
  headlights feed the same clarity state that blurs the lane bed. One
  system, one DSP path, one mental model. Night without lights sounds
  like rain without wipers.
- **Wipers-on-lights-on:** real law in most US states — rain chains
  naturally into the lights habit.
- **Telegraph ladder (diegetic first):**
  1. Dusk soundscape — crickets/night insects in, traffic thins; dawn
     birds on the other end. The world audibly gets dark.
  2. Cab chime + one spoken "Getting dark — lights?" (modern trucks
     really do this; realism, not a crutch).
  3. Oncoming honks/flashes when running dark.
  4. Trooper pull-over — a stop that costs clock time (slots into the
     unified clock-stops family with tolls and stoplights).
- **Assist ladder:** reminder chime is a setting (default on); AUTOMATIC
  HEADLIGHTS as a purchasable truck upgrade (real trucks have them) —
  accessibility ladder disguised as a garage option. RAIN-SENSING WIPERS
  complete the same pattern: assists are never a "disable realism"
  checkbox, they are equipment you buy. The rookie rig is full manual —
  driving a truck is supposed to be hard (owner, 2026-07-09); the premium
  truck does wipers and lights for you because premium trucks really do.
- Lights state joins the status-readout keys so "are my lights on?" is
  always one keypress away.
