# Public data sources: what is keyless, what is clean, what is worth adopting

Every verdict below was checked by making the request, not by reading a
description of it. Dates and counts are from **2026-09-19** unless a row says
otherwise; re-check anything older than a release cycle before relying on it.

Two rules from `CLAUDE.md` decide most of these rows. A source has to be
**keyless** -- no signup, no OAuth, a `User-Agent` at most -- because a key is
a secret the open-source build cannot carry. And it has to survive the
provenance rule: a number lands as **read**, **derived**, or **assumed**, never
blurred, so anything that would ship a gap-fill in the same shape as a
measurement is rejected however convenient it is.

**Scope note.** The graph is 624 cities across 48 states and DC -- not the
59 cities an older README described. Anything scoped per state has to be judged
against 49 jurisdictions, which is what sinks several rows below.

## Verdicts

| Source | Keyless | Licence | Format | Freshness | Coverage | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| NTAD Truck Stop Parking (Jason's Law) | yes | US Gov, public domain | GeoJSON / esriJSON | survey, last edited 2025-05-22 | 1,915 sites, 48 states + DC | **Adopt** -- in use, now cached |
| NTAD National Highway System | yes | US Gov, public domain | GeoJSON lines | refreshed 2026-09 | 492,005 segments, all US | **Defer** -- the route graph already exists |
| NTAD Weigh-in-Motion Stations | yes | US Gov, public domain | GeoJSON points | last edited 2025-04-30 | 763 sensor sites | **Adopt as a screen**, not as an inventory |
| FHWA toll facilities | n/a | US Gov, public domain | biennial XLSX / PDF | 2023 edition | national | **Defer** -- superseded by `tools/toll_rates.py` |
| USGS 3DEP elevation | yes | US Gov, public domain | JSON samples | 3DEP rolling | US, 1-10 m | **Adopted** -- 9,484 points read; see ROADMAP |
| NWS `api.weather.gov` | yes | US Gov, public domain | JSON | hourly METAR cycle | US and territories | **Keep** -- pattern still fits |
| WZDx feed registry + member feeds | registry yes; 29 of 43 feeds yes | US Gov registry; feed terms vary | JSON / GeoJSON | 1 min to 72 h | already swept 2026-09-12 | **Nothing new** -- the two keyless rows we lack were benched on purpose |
| Caltrans Lane Closure System | yes | Caltrans public feed | JSON per district | live | California, 12 districts | **Adopt with a district scope** |
| OSM `amenity=weighbridge` | yes | ODbL -- attribution and share-alike | PBF / Overpass | continuous | 2,127 CAT Scales; only 72 enforcement scales | **Adopt for CAT Scales**; useless for scale houses |
| FMCSA hours, endorsements, brake limits | n/a | US Gov, public domain | published rule text | rulemaking | national | **Keep** as cited constants |
| FRED `GASDESW` diesel | yes | Public domain series | CSV | weekly | national average | **Keep** -- already the diesel source |
| EIA fuel prices | **no** | -- | -- | -- | -- | **Needs a key, deferred** |
| Key-gated 511 feeds (CO, IL, MA, MI, OH, OR, PA, VA, CA, TX statewide) | **no** | -- | -- | -- | -- | **Needs a key, deferred** |

## 1. NTAD -- Bureau of Transportation Statistics

The National Transportation Atlas Database is published as plain ArcGIS
feature services on `services.arcgis.com/xOi1kZaI0eWDREZv`. A query string is
the whole protocol. Every layer carries the same licence, quoted from the
service's own item metadata:

> This NTAD dataset is a work of the United States government as defined in 17
> U.S.C. § 101 and as such are not protected by any U.S. copyrights. This work
> is available for unrestricted public use.

Public domain, redistributable inside the baked world. BTS asks for an
acknowledgment rather than requiring one; `tools/ntad.py` carries it in the
snapshot header so it cannot get separated from the data.

**Truck Stop Parking** is the one worth having and is already in the map:
`tools/curate_route_pois.py` has been reading it since 2026-07-17, and
`tools/fill_sparse_legs_jasons_law.py` uses it to give long legs with no
truck-usable stop a real place to pull in. 1,915 records, every contiguous
state plus DC, with counted spaces. As of this change the fetch goes through
`tools/ntad.py`, so a re-run is offline and the licence travels with it.

One thing to know about its provenance: FHWA's acknowledgment names the
commercial **Trucker's Friend** database among the contributing sources. USDOT
still publishes the compiled result as a government work in the public domain,
so redistribution is fine, but the row is not purely a federal survey.

**National Highway System** is keyless and public domain and we should still
not take it. 492,005 line segments covering the whole country, where the route
graph is already built from OSM and Valhalla with truck restrictions applied
and mile-accurate leg geometry. NHS would answer a question nothing asks.

**Toll facilities** are not an NTAD layer. FHWA publishes *Toll Facilities in
the United States* as a biennial report -- the 2023 edition is current -- in
Excel and PDF, and the `data.transportation.gov` mirror is a non-tabular
collection that refuses the resource API outright (HTTP 403, "no row or column
access to non-tabular tables"). It is also the wrong data: it inventories
facilities, not what a five-axle rig pays at them. `tools/toll_rates.py`
already carries the rates, each read off an authority's own adopted schedule.

## 2. USGS 3DEP -- and the wrong door

The Elevation Point Query Service at `epqs.nationalmap.gov` is keyless, public
domain, and answers with a 3DEP value plus its resolution and acquisition date.
It is also one point per request: 12 sequential points took 51.1 s,
4.26 s each. At that rate a single leg's vertices are an afternoon.

The same data has a batch door. The 3DEP ImageServer accepts a multipoint
geometry:

```
POST https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/getSamples
    geometry={"points": [[lon, lat], ...], "spatialReference": {"wkid": 4326}}
    geometryType=esriGeometryMultipoint&returnFirstValueOnly=true&f=json
```

100 points came back in 20.1 s -- 0.20 s per point, twenty times faster --
each with its own `resolution` and `rasterId`, in metres.

Even so, this is a screen, not a replacement bake. Elevations today come
from Open-Meteo over Copernicus DEM GLO-90 (30 m, global) and from ORS; 3DEP is
1-10 m and US-only, which makes it the authoritative instrument for checking
derived grades against the physical limit for their class, exactly as
`CLAUDE.md` requires. Re-baking every vertex at 0.2 s a point is an overnight
job that should be costed against a named benefit first.

**Gotcha worth writing down:** EPQS answers an out-of-coverage point with HTTP
200 and a plain-text body reading `Call failed.` Any loader that trusts the
status code will store that string as an elevation.

## 3. NWS -- confirmed, no change

`crates/ff-core/src/sim/real_weather.rs` already does the right thing and the
pattern still fits career mode: keyless with an identifying `User-Agent`,
station resolved once per city, fetch on a background thread so the game loop
never waits, 5-minute refresh, 30 minutes of stale tolerance, and `None` back
to the caller when nothing has landed -- at which point simulated weather
carries on and the game is identical offline.

The one constraint it already respects is worth restating because it is easy to
re-break: NWS stations file routine METARs once an hour, so the freshest
observation a healthy station has is routinely 30-60 minutes old. The
observation-age ceiling sits at two hours for that reason. Tightening it below
the METAR cycle pushes players onto fallback weather for no reason.

## 4. State incidents and work zones without a key

The useful discovery is that the WZDx feed registry is itself a keyless
dataset, and every row carries a `needapikey` flag:

```
https://datahub.transportation.gov/resource/69qe-yiui.json?$limit=300
```

43 registered feeds, 29 active and keyless. Against the 21 states the game
marks `no_api` in `crates/ff-core/src/sim/real_traffic/state_apis.rs`, that
leaves exactly two -- **and the registry was already swept on 2026-09-12, which
benched both on stated grounds**:

| State | Feed | Today | Why it is benched |
| --- | --- | --- | --- |
| Oklahoma | `oktraffic.org/api/Geojsons/workzones` | 200, 60 zones, WZDx 4.0 | The registry publishes an access token inside the URL. A key in a URL is still a key -- owner's call, not a bug |
| New Mexico | `ai.blyncsy.io/wzdx/nmdot/feed` | 503, same as on 2026-09-12 | Dead, and dead for at least a week -- not a transient outage |

Texas appears in the registry with an Austin-only feed, not a statewide one.
So this source is worked out: re-sweeping the registry finds nothing the
September sweep missed. Re-check New Mexico when a build is due; Oklahoma needs
the owner to revisit the token rule, not new code.

**California** is the largest dark state and has no keyless WZDx feed, but
Caltrans publishes its Lane Closure System per district with no key at
`cwwp2.dot.ca.gov/data/d<N>/lcs/lcsStatusD0<N>.json`. Districts 3, 4, 7, 8, 11
and 12 all answered 200. The catch is size: 1.1 MB for district 11 and
17.6 MB for district 7, against a feed timeout of 8 seconds. It is adoptable
only if the fetch is scoped to the districts a route actually crosses, which needs a
district lookup the map does not have yet.

*Adopted 2026-09-24* (`crates/ff-core/src/sim/real_traffic/caltrans.rs`). The
same rows ship as CSV at `.../lcsStatusD<NN>.csv`, and all twelve districts
answered: District 7 is 2.2 MB and arrived in 4.5 to 5.0 seconds, the rest
38 KB to 780 KB. The county-to-district table is read from the `DISTRICT` field
of Caltrans's `CHboundary/County_Boundaries` layer on caltrans-gis.dot.ca.gov;
county outlines are the Census 2023 1:20,000,000 cartographic boundary file
(public domain), written by `tools/build_ca_county_outlines.py`.

Still needing a key, and so deferred: Colorado, Illinois, Massachusetts,
Michigan, Ohio, Oregon, Pennsylvania, Virginia, California's WZDx feed, and
Texas statewide. Not in the registry at all: Alabama, Arkansas, Montana,
Nebraska, Rhode Island, South Carolina, South Dakota, Tennessee, West Virginia,
Wyoming, DC.

## 5. Weigh and inspection stations

There is no federal inventory of enforcement scales. The nearest NTAD layer,
**Weigh-in-Motion Stations** (763 sites), is a network of *sensors* used for
planning and screening -- a WIM site is not somewhere a driver pulls in, so
using it as the pull-in inventory would ship a derived guess in the shape of a
survey.

OpenStreetMap's `amenity=weighbridge` returns 3,818 US features, which looked
like the answer until the tags were read. Classified by name, operator and
brand:

| What it is | Count |
| --- | --- |
| CAT Scale, at a truck stop, driver pays to weigh | 2,127 |
| No name and no operator -- could be a farm or quarry scale | 1,529 |
| Other private or unclassified | 88 |
| State enforcement scale house | 72 |
| Other truck-stop chain scale | 2 |

So the tag does **not** answer the scale-house question. 72 enforcement scales
nationally is fewer than the 87 the map already carries, which came from
`highway=motorway_junction` exit signs -- every one of them, and only on 78 of
1,283 legs. Both sources are thin for the same reason: nobody maintains a
national list of state scale houses, and the states publish theirs in 50
different shapes. Treat that as unsolved rather than papered over.

What the tag does answer is a different and unclaimed question: 2,127 branded
CAT Scales, where a driver pays to learn their axle weights before a scale
house does it for them. The sim already models mass and axle load
(`crates/ff-core/src/sim/vehicle/mass.rs`), and `docs/roadmap-details.md`
already lists CAT scales among travel-center amenities. That is the layer worth
taking.

Licence is ODbL: attribution required, share-alike on a derived database. The
project already carries that obligation for the rest of the map, so this adds
no new constraint -- but it is the one row in this document that is not public
domain.

## 6. FMCSA static rules

No API exists and none is needed. Hours of service, CDL endorsements and air
brake thresholds are published rule text, public domain, and change by
rulemaking. They belong as constants with the section cited beside them, which
is what `crates/ff-core/src/models/credentials.rs` and the HOS constants
already do. The only upkeep is re-reading the source when a rule moves.

## What to adopt in career 1.9, and what to leave

**Already done.** The truck parking snapshot. It was load-bearing and one BTS
outage away from failing a bake; it is now cached, offline-safe and reading the
full 1,915 records instead of 1,000. No driver hears anything new -- this
survey's one shipped change is maintenance on a layer players already had.

**Worth building, in this order.** CAT Scales as a truck-stop service: 2,127
real branded locations, a driver-elected activity the game does not have, on
top of a mass model that already exists. Then the 3DEP grade screen below,
because a wrong grade is something a driver hears as a wrong advisory. Neither
is a data drop; both are features. The CAT Scale layer is built:
`tools/cat_scales.py` keeps a committed snapshot of the 2,127 points and gives
the `scale` service to the truck stops within 0.25 mi of one; the weigh reads
the axle model in `crates/ff-core/src/sim/vehicle/axles.rs`.

**Adopted as a screen.** 3DEP through the ImageServer, and it has now been
run: `tools/screen_grades_3dep.py` read 9,484 elevations over every grade span
the load screen clamps. It confirmed the clamp on 77 percent of them and found
one thing worth more than the verdicts -- two elevation models agreeing does
not make a slope real, because both read ground and neither reads a bridge
deck. Full findings are in `ROADMAP.md`. Still the wrong instrument for a
wholesale re-bake until that overnight run is costed against a named benefit.

**Leave.** NHS, because the graph already exists. FHWA toll facilities, because
the researched rate table is better data for the question the game asks. The
WZDx registry, because September's sweep already took everything in it.
Caltrans LCS until a route-to-district lookup exists, because a 17 MB fetch
inside an 8-second budget is a stall, not a feature. Every keyed feed, and EIA,
because a key is a secret this build cannot keep.

**Unsolved, and worth saying so.** Where the state scale houses are. 78 of
1,283 legs have one, all found by accident off exit-sign text, and no keyless
national source improves on that. Fixing it means 50 state DOT lists in 50
shapes, which is a project, not a fetch.

## Re-checking this document

```bash
uv run python tools/ntad.py --layer truck_parking --refresh --stats
```

That prints the record count, the snapshot path, the access date and the
licence. Anything else in here is a `curl` away, and the point of writing the
requests down is that the next reader re-runs them instead of trusting a table
that has gone stale.
