# Route Stop Data

Freight Fate keeps route amenities in static JSON so the game remains playable
offline. Runtime driving does not call OpenStreetMap, Overpass, paid truck
routing APIs, or operator sites.

## Schema

Route stops live on a leg in `src/freight_fate/data/world.json`:

```json
{
  "name": "Road Ranger Waco",
  "type": "travel_center",
  "at_mi": 185.0,
  "source": "Road Ranger Waco, 6615 N Interstate Highway 35, I-35 Exit 342B: https://www.roadrangerusa.com/node/251"
}
```

`at_mi` is route miles from the leg's `from` city toward its `to` city. The
trip simulator mirrors that offset when the player drives the same leg in the
opposite direction.

Name-only stops are intentionally rejected by the loader. They used to be
spread evenly across each leg, which made route amenities feel synthetic. New
data must provide a named, typed stop with an explicit position inside the leg
mileage.

## Source Strategy

The current seed is small on purpose. It covers representative corridors and
test-critical routes using public DOT rest-area pages, operator location pages,
and development-time map review. Examples include:

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

## Update Process

1. Choose a corridor and confirm the route leg mileage already represents the
   intended highway path.
2. Find truck-relevant public rest areas, travel centers, service plazas, or
   truck parking from public agency pages, official operator pages, or
   OSM/Overpass development-time queries.
3. Estimate `at_mi` from the leg's `from` city using route mileage, exit/mile
   marker data, or a map distance check. Do not place stops at regular
   intervals just to fill the route.
4. Add `source` notes that are specific enough for another developer to verify
   the stop later.
5. Run `uv run pytest tests/test_world.py tests/test_weather_trip.py
   tests/test_job_progression.py` and focused driving/rest-stop tests.

## Accessibility Impact

Stop type labels remain spoken before the stop name, such as `public rest area:
Kenosha Safety Rest Area` or `travel center: Road Ranger Waco`. The keyboard
flow is unchanged: stops are announced ahead, `X` arms the exit, and `T` opens
the stop menu when parked at a stop.
