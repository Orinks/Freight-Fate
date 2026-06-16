# Route, Stop, And Corridor Data

Freight Fate keeps route amenities and corridor metadata in static JSON so the
game remains playable offline. Runtime driving does not call OpenStreetMap,
OSRM, Overpass, paid truck routing APIs, Census services, or operator sites.
External sources are build-time inputs only.

## Schema

Route stops and corridor details live on a leg in
`src/freight_fate/data/world.json`:

```json
{
  "from": "Chicago",
  "to": "Indianapolis",
  "miles": 184,
  "highway": "I-65",
  "corridor": {
    "route_points": [
      {"at_mi": 0.0, "lat": 41.8781, "lon": -87.6298}
    ],
    "state_crossings": [
      {
        "at_mi": 33.0,
        "from_state": "Illinois",
        "state": "Indiana",
        "place": "the I-65 state line south of Hammond"
      }
    ],
    "checkpoints": [
      {
        "name": "Gary and Hammond industrial corridor",
        "type": "place",
        "state": "Indiana",
        "highway": "I-65 south",
        "at_mi": 36.0
      }
    ],
    "state_miles": [
      {"state": "Illinois", "miles": 33.0},
      {"state": "Indiana", "miles": 151.0}
    ]
  },
  "stops": [
    {
      "name": "Loves Travel Stop Lafayette",
      "type": "travel_center",
      "at_mi": 122.0
    }
  ]
}
```

`at_mi` is route miles from the leg's `from` city toward its `to` city. The trip
simulator mirrors stops, state crossings, and checkpoints when the player drives
the same leg in the opposite direction.

Name-only stops are intentionally rejected by the loader. They used to be
spread evenly across each leg, which made route amenities feel synthetic. New
data must provide a named, typed stop with an explicit position inside the leg
mileage.

Corridor metadata is optional for old data and saves. When present, it drives
GPS cues, state-line announcements, intermediate place calls, and progress
summaries. This is the first step away from treating each route as a plain
0-to-N mile bar between city nodes.

## Navigation And Traffic Runtime

Loaded trips are destination/load-first. The player accepts freight, drives to
the origin facility, loads, and dispatch starts the itinerary. Manual route
selection is no longer the main fiction of the trip.

The GPS layer reads the itinerary and announces concise audio-first cues:

- continue cues for long highway stretches;
- advance and near cues for maneuvers;
- state crossings and intermediate corridor places;
- one-mile rest-stop exit cues;
- modeled traffic slowdowns when a lead vehicle or queue is ahead.

Basic traffic is deterministic for a trip seed. The first slice models lead
traffic packs with a speed, gap, and reason such as slow lead traffic, merging
traffic, lane restriction, or queue. Adaptive cruise control uses that context:
it holds the set speed when clear, follows slower traffic at a three-second gap,
and cancels when the driver brakes. It does not steer, change lanes, or replace
the GPS.

## Source Strategy

The current seed is small on purpose. It covers representative corridors and
test-critical routes using public DOT rest-area pages, operator location pages,
development-time map review, and small no-key API smoke checks. Examples
include:

- OSRM public demo route API over OpenStreetMap for tiny build-time geometry
  checks. Keep requests cached or one-off; do not use it at runtime.
- Nominatim, only if necessary for sparse build-time lookup. Use a custom
  User-Agent, at most one request per second, and keep attribution visible.
- Overpass API for development-time discovery of rest areas, truck stops,
  service plazas, truck parking, and weigh stations. Do not call it at runtime.
- Census/TIGER or Census-derived public state boundary GeoJSON for computing
  state crossings from route geometry.
- WisDOT Kenosha Safety Rest Area, with truck parking:
  https://wisconsindot.gov/Pages/travel/road/rest-areas/26-kenosha.aspx
- INDOT rest-area/truck-parking overview:
  https://www.in.gov/indot/restareas.htm
- TxDOT safety rest-area list and Hill County details:
  https://www.txdot.gov/discover/rest-areas-travel-information-centers/safety-rest-area-list.html
  https://www.txdot.gov/discover/rest-areas-travel-information-centers/safety-rest-area-list/hill.html
- ARDOT welcome centers/rest areas PDF:
  https://media.ark.org/ardot/Welcome-Centers-and-Rest-Areas-and-Accessibility-Barriers.pdf
- Caltrans Safety Roadside Rest Areas program:
  https://dot.ca.gov/programs/design/lap-landscape-architecture-and-community-livability/lap-liv-h-safety-roadside-rest-areas
- Iowa 80 Truckstop official site:
  https://iowa80truckstop.com/
- Road Ranger Waco official location page:
  https://www.roadrangerusa.com/node/251
- Loves Lafayette official location page:
  https://www.loves.com/locations/in/lafayette/loves-travel-stop-lafayette-874
- Pilot Travel Center Lincoln official location page:
  https://locations.pilotflyingj.com/us/al/lincoln/75750-al-77
- IDOT truck parking page for I-55 rest areas:
  https://idot.illinois.gov/programs-and-projects/rail-and-freight/truck-parking.html
- Pilot Battle Creek and TA Sawyer official location pages:
  https://locations.pilotflyingj.com/us/mi/battle-creek/15901-11-mile-rd
  https://www.ta-petro.com/location/mi/ta-sawyer/

OpenStreetMap and Overpass are good development-time candidates for expanding
coverage because they expose open highway amenity data. If OSM-derived data is
committed, keep attribution and ODbL obligations visible in release materials
and source notes:

- OpenStreetMap copyright and license:
  https://www.openstreetmap.org/copyright
- OpenStreetMap Foundation attribution guidelines:
  https://osmfoundation.org/wiki/Licence/Attribution_Guidelines
- Overpass API documentation:
  https://wiki.openstreetmap.org/wiki/Overpass_API

## Build-Time Tooling

Inspect the checked-in corridor metadata:

```powershell
uv run python tools/enrich_routes.py --from-city Chicago --to-city Indianapolis
```

Run the tiny live OSRM smoke check:

```powershell
uv run python tools/enrich_routes.py --from-city Chicago --to-city Indianapolis --live-smoke
```

The live smoke prints OSRM route mileage and simplified geometry point count.
It is deliberately separate from deterministic unit tests and should remain a
small, credential-free sanity check.

## Update Process

1. Choose a corridor and confirm the route leg mileage already represents the
   intended highway path.
2. Run or review build-time route geometry and state-boundary data to place
   route points, state crossings, checkpoints, and state mileage.
3. Find truck-relevant public rest areas, travel centers, service plazas, or
   truck parking from public agency pages, official operator pages, or
   OSM/Overpass development-time queries.
4. Estimate `at_mi` from the leg's `from` city using route mileage, exit/mile
   marker data, or a map distance check. Do not place stops at regular
   intervals just to fill the route.
5. Add `source` notes that are specific enough for another developer to verify
   the stop later.
6. Run `uv run pytest tests/test_world.py tests/test_weather_trip.py
   tests/test_job_progression.py` and focused driving/rest-stop tests.

## Future Freight Data

FAF/BTS freight datasets can improve market realism, lane demand, and commodity
flows later. That is separate from corridor realism: the current goal is to make
the driven itinerary feel grounded. A future market pass should map FAF/BTS
flows into job generation weights while keeping the offline runtime model.

## Accessibility Impact

Stop type labels remain spoken before the stop name, such as `public rest area:
Kenosha Safety Rest Area` or `travel center: Road Ranger Waco`. The keyboard
flow remains audio-first: stops are announced ahead, `X` arms the exit, and `T`
opens the stop menu when parked at a stop. `R` speaks route progress plus GPS
context. `K` sets adaptive cruise, and the spoken cue includes the following
gap and cancellation behavior. GPS and traffic cues supplement the keyboard
status keys; they never require a visual map.
