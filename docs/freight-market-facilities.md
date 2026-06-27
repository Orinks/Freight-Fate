# Freight Market And Facility Data

Freight Fate models cities as metro freight markets. The highway graph remains
the routeable set of supported metro nodes, while each metro expands into
origin and destination facilities: terminals, ports, intermodal ramps,
warehouses, food facilities, plants, yards, and other trucking locations.

This is intentionally representative, not exhaustive. The goal is to make a
59-metro map feel like a national freight network without pretending the game
contains every U.S. town, shipper, receiver, industrial park, or distribution
center.

## Runtime Contract

Runtime data is offline. Job generation must not call BTS, FAF, MARAD, USDA,
OpenStreetMap, routing APIs, or operator sites. External sources guide the
checked-in taxonomy, weights, names, and source notes.

Each facility carries:

- `id`: stable generated or curated facility id.
- `name`: concise player-facing facility name.
- `city`: supported metro route node.
- `locality`: optional suburb or local-market hint.
- `type`: normalized facility category.
- `cargo`: cargo classes associated with the facility.
- `ships` and `receives`: role-specific cargo compatibility.
- `roles`: shipper and/or receiver.
- `lat` and `lon`: curated or representative coordinates when available.
- `traits`: design tags such as `template`, `representative`, or market tags.
- `source_note`: developer-facing note for why the facility exists.
- `spoken_name`: concise screen-reader-friendly label.

Older world data that only has `name`, `type`, and `cargo` is upgraded at load
time. Older saves that only named an origin or destination city display as the
metro freight market instead of failing.

## Facility Taxonomy

The normalized taxonomy covers the common freight surfaces a truck driver
would expect:

- `port_terminal`
- `intermodal_ramp`
- `air_cargo`
- `parcel_hub`
- `grocery_retail_dc`
- `dry_warehouse`
- `cold_storage`
- `food_processor`
- `farm_elevator`
- `manufacturing_plant`
- `steel_industrial`
- `automotive_plant`
- `chemical_petroleum_terminal`
- `construction_materials_yard`
- `mine_quarry`
- `lumber_paper`
- `cross_dock`
- `company_yard`

Legacy data types such as `port`, `warehouse`, `distribution`, `rail`,
`intermodal`, `food_terminal`, `manufacturing`, and `terminal` remain valid so
old data and saves keep loading.

## Source Strategy

Official data sources guide the model:

- [BTS Freight Analysis Framework](https://www.bts.gov/faf) and
  [FHWA FAF overview](https://ops.fhwa.dot.gov/freight/freight_analysis/faf/)
  guide metro/state freight-flow thinking, mode coverage, and commodity
  categories.
- [FAF / ORNL tools](https://faf.ornl.gov/) guide future lane and commodity
  weighting checks.
- [MARAD Ports Data and Statistics](https://www.maritime.dot.gov/data-reports/ports)
  and [BTS Port Performance Freight Statistics](https://www.bts.gov/ports)
  guide port-terminal, container, bulk, and intermodal treatment.
- [USDA Open Ag Transport Data](https://agtransport.usda.gov/) and
  [USDA Grain Truck and Ocean Rate Advisory](https://www.ams.usda.gov/services/transportation-analysis/gtor)
  guide grain, agricultural trucking, refrigerated availability, and food-flow
  context.

Do not paste raw dataset rows, OSM tags, IDs, NAICS codes, or source database
keys into player-facing names. Source notes may name a source family, but the
spoken job board should stay clean.

## Representative Templates

World JSON stays compact by listing curated seed locations. The loader then
adds deterministic representative facilities from market tags. For example:

- a port/gateway metro can receive `port_terminal`, `cross_dock`, and
  `intermodal_ramp` templates;
- an agricultural metro can receive `farm_elevator`, `food_processor`, and
  `cold_storage`;
- an industrial metro can receive `manufacturing_plant`, `steel_industrial`,
  `automotive_plant`, or `construction_materials_yard`;
- an energy metro can receive `chemical_petroleum_terminal`;
- a northwest or forest-products metro can receive `lumber_paper`;
- a logistics hub can receive `parcel_hub`.

Template facilities use stable IDs and polished names such as `Chicago
Cross-Dock` or `Fresno Grain Elevator`. They are representative gameplay
locations, not claims about a specific real-world shipper.

## City Service POIs

City services are separate from freight shippers and receivers. The current
runtime exposes representative service POIs for the freight market office,
terminal garage, and truck dealer, then generates short local approach drives
from the home terminal. They are derived from checked-in terminal and metro
market data, stay offline, and keep the same clean spoken-name rules as freight
facilities.

Future OSM/ORS or operator-data passes can replace the representative approach
distance, road name, and coordinates with source-backed local POIs. Player
speech should still say the service plainly, such as `garage: Chicago Company
Yard Garage`, and should not expose raw OSM tags, IDs, or source keys.

The next data pass should keep service POIs separate from career ownership and
settlement systems. OSM/Overpass and ORS can improve where service drives go;
trailer ownership and cargo-equipment matching belong to a freight-market and
garage/dealer slice, not to the company-driver or owner-operator career arc.

## Job Generation

Job generation now chooses:

1. a compatible origin shipper facility in the current metro;
2. a cargo that the origin ships and the driver can reasonably see at the
   current level;
3. a supported route-node destination within the career distance cap;
4. a compatible receiver facility in that destination metro.

If the destination metro has no receiver for that cargo, the board retries
instead of inventing an implausible receiver. This prevents pairings such as
grain elevator to parcel hub unless the cargo roles explicitly support it.

Metro market tags weight the choices. Ports lean toward containers and bulk,
agricultural markets toward grain and food, industrial markets toward steel,
machinery, automotive, chemicals, lumber, and construction materials, and
border/gateway metros toward cross-dock and container freight.

Higher driver levels and endorsements expose more facility and cargo variety.
The route support gate still applies: new dispatches use metadata-backed
routes, and old saves can still load through the legacy graph.

## Accessibility

Facility names must be concise, pronounceable, and meaningful without a visual
map. Job rows should remain one spoken dispatch, not a wall of source detail.
Use the existing help/status/paperwork paths for deeper explanation.

Recommended spoken shape:

`18 tons of grain from farm elevator Fresno Grain Elevator in Fresno to food
processor Sacramento Food Processing Plant in Sacramento.`

Avoid raw tags, codes, or directional clutter in names. If a locality is useful,
keep it short and optional.

## Update Checklist

1. Add or adjust curated seed facilities in `world.json` only when the name is
   worth being player-facing.
2. Put broad coverage in template rules, not thousands of handwritten entries.
3. Add or update source notes for any new facility type or specialization.
4. Verify every facility has a stable id, clean spoken name, source note, and
   ship/receive cargo roles.
5. Verify generated jobs use compatible shipper and receiver roles.
6. Run focused tests:

```powershell
uv run pytest tests/test_world.py tests/test_job_progression.py tests/test_market.py tests/test_pickup_loading.py tests/test_trip_resume.py
```

