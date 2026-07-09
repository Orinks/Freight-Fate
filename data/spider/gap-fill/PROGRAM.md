# Gap-fill program (Fable design review, 2026-07-09)

Operational plan for closing the map's connectivity gaps. Inputs: two systematic
scans run 2026-07-09 against 407 cities / 785 legs (the raw catalogs and the
scanner scripts live beside this file). The review below is Fable 5's triage of
those catalogs plus the build sequence; Opus executes it batch by batch on
`map/spider`, re-running the nearest-neighbor scan every 2-3 batches because
each built batch re-bridges dozens of remaining entries.

Progress ledger (update as batches land):

- [x] Pre-program: Deep South 7 (birmingham-chattanooga I-59, mobile-meridian +
  meridian-tupelo US-45, gulfport/jackson-hattiesburg US-49,
  columbia-spartanburg I-26, austin-temple I-35) -- commit 4ac8027
- [ ] Batch 0 -- Interstate spine emergencies (9 legs, all interstates)
- [ ] Batch 1b -- Deep South finish
- [ ] Batch 2 -- Georgia web
- [ ] Batch 3 -- Kentucky parkways & Appalachian corridors
- [ ] Batch 4 -- Carolinas & Virginia
- [ ] (interleave) City-promotion slate: Lynchburg VA, Wytheville VA, Dubuque IA,
      Waterloo IA, Lima/Findlay OH, Bloomington IN, Columbus MS, Ocala FL,
      Longview TX, Walla Walla WA (2nd tier: New London CT, Cumberland MD,
      Natchez MS, Cookeville TN)
- [ ] Batch 5 -- Northeast dense mesh
- [ ] Batch 6 -- Midwest lattice
- [ ] Batch 7 -- Texas & southern plains
- [ ] Batch 8 -- Kansas/Nebraska ladder
- [ ] Batch 9 -- California (real legs)
- [ ] Batch 10 -- Pacific Northwest
- [ ] Batch 11 -- Big Sky & Great Basin sparse net

---

# Design Review: Leg-Gap Triage & Fill Program (Fable 5)

Reviewed both scan files in full (392 corridor gaps, 184 nearest-neighbor gaps).
Verdict up front: the plan is sound -- themed regional batches, legs-before-cities,
sprawl-skipping are all right. The two things I'd change: (1) run a **spine-first
"Batch 0"** across regions before the regional sweeps, because a handful of these
gaps are embarrassing holes in named interstates; (2) formalize a
**pick-one-of-triangle rule**, because both scans generate redundant meshes around
hub cities (Aurora IL, Fort Wayne, Grenada, Killeen) that would triple the leg
count for no player value.

## 1. Triage rules

Apply in order; first failure excludes.

- **R1 -- Same-metro test.** If both endpoints share one continuous urbanized
  area / commuting shed, EXCLUDE. A player should never haul "freight" between
  two nodes of the same city. (LA-Santa Ana, Miami-Coral Springs, Chicago-Aurora,
  Dallas-McKinney.)
- **R2 -- One numbered through-highway.** The leg must be describable in one
  spoken breath: "US-49 south, 70 miles." If the route is a chain of three county
  roads or a straight-line fantasy across a lake or mountain range, EXCLUDE.
- **R3 -- Distinct freight identity.** Both cities must have their own economic
  reason to ship: own MSA, own distribution base, or sole town of its region.
  Suburb nodes fail this even at 40+ miles.
- **R4 -- Non-redundancy / pick-one-of-triangle.** When A-B, B-C, A-C all appear,
  keep the two that follow signed highways and drop the hypotenuse. When two
  parallel highways connect the same pair of areas (US-183 vs US-283 in Kansas),
  pick the bigger one.
- **R5 -- Land the leg on the core.** When a corridor gap touches a metro
  satellite (Aurora, Gary, Kenosha, Fairfield, Valencia), re-anchor the leg on
  the metro core or the satellite that actually sits on the highway -- don't
  build satellite-to-satellite.
- **R6 -- Terrain honesty.** A leg must not imply a truck route where trucks
  don't go: no ferry crossings, no seasonal or 2-lane mountain passes as the
  *only* representation of a pair.

### Specific EXCLUSIONS -- intra-metro / sprawl (R1)

From gap-corridor: LA-Santa Ana, Riverside-Santa Ana, LA-Valencia,
Santa Ana-Oceanside, San Diego-Oceanside, SF-Fairfield, Sacramento-Fairfield,
Santa Rosa-Fairfield, Stockton-Fairfield, Miami-Coral Springs,
Coral Springs-West Palm Beach, Dallas-McKinney, Chicago-Aurora, Aurora-Gary,
Nashville-Murfreesboro (Murfreesboro is Nashville's McKinney -- it should live
*on* the Nashville-Chattanooga I-24 leg, not as a spoke hub), Lafayette LA-Sulphur
(Sulphur is effectively Lake Charles -- flag Sulphur as a near-duplicate node).

From gap-nn, additionally: Lancaster-LA, San Diego-Santa Ana, Fairfield-Ukiah,
Everett-Olympia and Bellingham-Tacoma (both are "I-5 through Seattle" artifacts),
Nephi-Ogden (I-15 through Provo/SLC -- the scan's 1-hop check missed Provo).
Allentown-Philadelphia is a KEEP (distinct city, PA turnpike NE extension) but
Trenton-Scranton is an exclude.

### Specific EXCLUSIONS -- redundant hub-mesh (R4, R5)

- **Aurora IL as a hub:** Aurora-Kenosha, Aurora-Bloomington, Aurora-Champaign;
  re-anchor Aurora-Davenport as **Chicago-Davenport (I-88)** if that spine leg
  doesn't exist.
- **Gary mesh:** Champaign-Gary, Bloomington-Gary, Peoria-Gary, Rockford-Gary,
  Muskegon-Gary, Kalamazoo-Gary. Keep only Fort Wayne-Gary (US-30).
- **Fort Wayne mesh:** drop FW-Jackson MI, FW-Kalamazoo, FW-Lafayette,
  Columbus-FW, Cincinnati-FW. Keep FW-Lansing (I-69 spine), FW-Elkhart, FW-Gary.
- **Grenada MS mesh:** drop Meridian-Grenada, Vicksburg-Grenada, Tupelo-Grenada,
  Grenada-Stuttgart, Tuscaloosa-Grenada, Grenada-Pine Bluff. Grenada is an I-55
  waypoint, not a hub.
- **Killeen/hill-country mesh:** drop Killeen-Kerrville, Killeen-Junction,
  Killeen-Abilene, Austin-Junction, Del Rio-Junction. Keep Austin-Kerrville
  (US-290) and one Del Rio connector (San Angelo-Del Rio via US-277 preferred).
- **Kentucky redundancies:** Morehead-Hazard, Louisville-London, Richmond-BG,
  Clarksville-E'town, Murfreesboro-E'town, Knoxville-Murfreesboro.
- **DC/Chesapeake:** keep DC-Salisbury (US-50 Bay Bridge) and Baltimore-Dover;
  drop DC-Dover, DC-Harrisonburg, Baltimore-Winchester, Richmond-Winchester.
- **Long-shot redundancies:** Florence-Durham, Greensboro-Florence,
  Florence-Spartanburg, Greensboro-Lumberton, Charlottesville-Durham,
  Roanoke-Durham, Augusta-Spartanburg, Toledo-Akron (Ohio Turnpike past
  Cleveland), Saginaw-Traverse City, Evansville-Decatur, Mountain Home-Stuttgart,
  Wichita-Hays, Lincoln-Salina, Kearney-Colby, Lexington NE-Colby/Hays,
  Denver-Sidney, Sidney/Ogallala-Burlington, Tacoma-Moses Lake,
  Tri-Cities-Wenatchee, Moses Lake-Lewiston, Salem-Newport (use Albany-Newport),
  Worcester/Springfield-Montpelier (keep one Montpelier feeder),
  Cedar Rapids-Rochester/Albert Lea/La Crosse, Madison-Davenport, Fargo-Willmar,
  Atlanta-Huntsville, Birmingham-Dalton, Birmingham-LaGrange,
  Huntsville-LaGrange, Macon-LaGrange, Tallahassee-Tifton,
  Tallahassee-Columbus GA, Savannah-Tifton.

### Rough survival counts

- **gap-corridor (392):** ~25 intra-metro, ~85 redundant mesh/hypotenuse, ~20
  terrain-dubious (section 4) -> **roughly 260 survive**, of which **~110 clearly
  worth building** and the rest opportunistic density.
- **gap-nn (184):** ~40 sprawl/artifact, ~25 redundant -> **roughly 120 survive,
  but ~80% duplicate scan 1.** Its unique value is the dense-region short legs
  (New England, Willamette, Columbia Basin) and lake-crossing artifacts to
  *reject*. Treat gap-nn as a checklist, not a work queue, and re-run it after
  each batch -- 1-hop bridging changes as legs get built.

## 2. Prioritized fill program (12 batches)

**Batch 0 -- Interstate spine emergencies (cross-region, gap-corridor).** Holes
in named interstates a player would notice immediately: New York-Albany (I-87
Thruway!), Colorado Springs-Pueblo (I-25), Chicago-Champaign (I-57),
Sacramento-Redding (I-5), Indianapolis-Evansville (I-69), Kansas City-Joplin
(I-49), Toledo-Dayton (I-75), Riverside-Victorville (I-15 Cajon Pass -- grade
physics showcase), Tallahassee-Lake City (I-10). One batch, nine legs,
disproportionate credibility payoff.

**Batch 1b -- Deep South finish (gap-corridor; extends the pre-program batch).**
Mobile-Hattiesburg (US-98), Baton Rouge-Gulfport (I-12), Shreveport-Texarkana
(US-71/I-49), Texarkana-El Dorado + Little Rock-El Dorado (US-82/US-167),
Huntsville-Chattanooga (US-72), Opelika-Columbus GA, Columbus GA-Dothan
(US-431), Crestview-Dothan, Birmingham-Opelika (US-280), Montgomery-Meridian
(US-80). Closes the region just worked while it's warm.

**Batch 2 -- Georgia web (gap-corridor).** Athens-Macon, Athens-Augusta,
Athens-Greenville SC, Macon-Columbus, Cordele-Albany, Albany-Valdosta,
Albany-Tallahassee (US-19), Valdosta-Tallahassee, Valdosta-Dothan (US-84),
LaGrange-Columbus. Georgia is the densest surviving cluster in the file.

**Batch 3 -- Kentucky parkways & Appalachian corridors (gap-corridor).**
Lexington-Elizabethtown (Bluegrass Pkwy), Elizabethtown-Evansville (WK Pkwy),
London-Bowling Green (Cumberland Pkwy), Mount Sterling-Richmond,
Mount Sterling-Hazard (Mountain Pkwy -- the spoken names are great),
Huntington-Paintsville + Paintsville-Hazard (US-23/KY corridors),
Johnson City-Pikeville (US-23 Pound Gap), Charleston-Pikeville (US-119 Corridor
G), Morristown-London (US-25E Cumberland Gap), Morgantown-Beckley (US-19 New
River Gorge), Morgantown-Hagerstown (I-68), Pittsburgh-Hagerstown (I-70/76),
Beckley-Winston-Salem (the I-77 Fancy Gap spine -- see Wytheville in the
missing-city slate). The batch with the most real-road romance per mile.

**Batch 4 -- Carolinas & Virginia (both scans).** Charlotte-Winston-Salem,
Greensboro-Fayetteville (US-421), Wilmington-Lumberton (US-74),
Charlotte-Lumberton, Charleston-Florence (US-52), Norfolk-Petersburg (US-460),
Raleigh-Petersburg, Roanoke-Winston-Salem (US-220), Asheville-Spartanburg +
Asheville-Greenville (I-26/US-25 -- Saluda Grade country), DC-Winchester (I-66),
DC-Hagerstown, DC-Charlottesville (US-29), Petersburg-Virginia Beach (nn).

**Batch 5 -- Northeast dense mesh (mostly gap-nn).** Providence-Worcester,
Boston-Manchester (I-93), Hartford-Providence, Providence-New Haven (I-95
shoreline), Philadelphia-Allentown, Allentown-Trenton, Baltimore-Dover,
DC-Salisbury, Atlantic City-Dover, Harrisburg-Wilmington, Washington-Carlisle
(US-15), Pittsburgh-Carlisle (PA Turnpike), Binghamton-Utica, Albany-Montpelier,
Portland ME-Montpelier (US-302 Crawford Notch -- flavor). Short legs, fast wins,
fixes the region the corridor scan structurally under-serves.

**Batch 6 -- Midwest lattice (both scans).** Cedar Rapids-Iowa City (I-380 --
31 mi, the single most obvious gap in either file), Peoria-Springfield (I-155),
Peoria-Decatur, Decatur-Bloomington, Champaign-Lafayette (I-74),
St. Louis-Decatur, Detroit-Ann Arbor, Ann Arbor-Toledo, Ann Arbor-Flint,
Toledo-Columbus (US-23), Kalamazoo-Elkhart, Fort Wayne-Elkhart,
Fort Wayne-Lansing (I-69), Fort Wayne-Gary (US-30), Lansing-Kalamazoo,
Milwaukee-Rockford, Indianapolis-South Bend (US-31), Muskegon-Traverse City
(US-31), Grand Rapids-Saginaw.

**Batch 7 -- Texas & southern plains (gap-corridor).** Lake Charles-Orange
(I-10), College Station-Temple, Waco-Tyler (TX-31), Tyler-Texarkana,
Fort Smith-Texarkana (US-71 -- completes the future I-49 line KC-to-Shreveport
with Batch 0's KC-Joplin), Tulsa-Fayetteville (US-412; preferred over
Tulsa-Bentonville), Tulsa-Enid (US-412), Wichita-Tulsa, San Angelo-Junction +
San Angelo-Del Rio (US-277), San Angelo-Fort Stockton (US-67),
Odessa-Fort Stockton, Fort Stockton-Midland (nn).

**Batch 8 -- Kansas/Nebraska ladder (gap-corridor).** Dodge City-Hays (US-183),
Garden City-Colby (US-83), North Platte-Colby (US-83), Kearney-Hays (US-183),
Lincoln-Junction City (US-77), Bismarck-Minot, Mitchell-Watertown,
Sioux Falls-Mankato, Willmar-Watertown (US-212), Columbia-Rolla (US-63),
KC-Springfield (MO-13), Springfield-Harrison + Conway-Harrison +
Bentonville-Harrison (US-65/62 Ozarks -- grade flavor).

**Batch 9 -- California, the real legs (both scans).** Fresno-Visalia (CA-99),
San Jose-Salinas (US-101), Salinas-Santa Maria (US-101), SF-Santa Rosa (US-101),
San Jose-Stockton (Altamont), Bakersfield-Barstow (SR-58 Tehachapi -- grade
physics), Lancaster-Barstow, Lancaster-Victorville, San Diego-Riverside (I-15),
Riverside-Indio (I-10), Indio-El Centro, Indio-Yuma (verify actual road -- I-10
to I-8 feeder), Oxnard-Valencia (SR-126), Klamath Falls-Mount Shasta (US-97),
Crescent City-Coos Bay (US-101).

**Batch 10 -- Pacific Northwest (both scans).** Salem-Corvallis, Newport-Albany
(US-20), Salem-Bend (US-20 Santiam Pass -- grade), Medford-Klamath Falls
(OR-140), Astoria-Olympia (US-101), Seattle-Wenatchee (US-2 Stevens Pass --
grade), Moses Lake-Wenatchee, Tri-Cities-Moses Lake, Wenatchee-Yakima (US-97),
Yakima-Moses Lake, Tacoma-Yakima (US-12 White Pass -- flavor), Newberg-Woodburn
+ McMinnville-Woodburn (Willamette trickle towns need their short legs),
Lewiston-Coeur d'Alene (US-95), Coeur d'Alene-Sandpoint, McCall-Ontario.

**Batch 11 -- Big Sky & Great Basin sparse net (gap-corridor).** Helena-Bozeman,
Missoula-Helena (US-12 MacDonald Pass), Missoula-Kalispell (US-93),
Great Falls-Havre (US-87), Casper-Gillette, Gillette-Miles City,
Fort Collins-Laramie (US-287), Dickinson-Williston + Williston-Glendive + one
Hi-Line connector (Wolf Point-Glendive), Battle Mountain-Austin NV (NV-305),
Tonopah-Austin, Elko-Eureka NV, Twin Falls-Wells (US-93), West Wendover-Ely,
Tonopah-Fallon (US-95), Winnemucca-Fallon, Cedar City-Richfield,
Provo-Green River (US-6 Soldier Summit -- the best grade-physics leg in the
whole file), Cedar City-Alamo (pick this over Saint George-Alamo). Optional
flavor: Tonopah-Alamo, the NV-375 Extraterrestrial Highway -- billboard gold.

**Highest-value corridor completions overall:** I-87 (NYC-Albany), I-49 line
(KC-Joplin + Fort Smith-Texarkana + Shreveport-Texarkana), I-57
(Chicago-Champaign), I-5 (Sacramento-Redding), I-69 (Indy-Evansville), I-25
(Springs-Pueblo), I-68 (Morgantown-Hagerstown), US-101 coast (Crescent
City-Coos Bay + Astoria-Olympia + Salinas-Santa Maria), US-95 (Tonopah-Fallon),
US-6 (Provo-Green River).

## 3. Legs vs new cities

**Legs-first is correct** -- roughly 9 in 10 surviving gaps are pure edges. But
the scans betray about a dozen genuine voids where repeated long, awkward gaps
all route through the same nodeless town. These are where a *city* is the real
fix:

- **Lynchburg, VA** -- Roanoke-Charlottesville (119) and Charlottesville-Durham
  both detour around it; US-29/US-460 junction.
- **Wytheville, VA** -- the I-77/I-81 junction; the 155-mi Beckley-Winston-Salem
  gap is really two legs through Wytheville.
- **Dubuque, IA** -- Madison-Cedar Rapids (162) is the symptom; tri-state
  US-151/US-61 hub.
- **Waterloo/Cedar Falls, IA** -- the Avenue of the Saints void behind
  Cedar Rapids-Albert Lea/Rochester weirdness.
- **Lima or Findlay, OH** -- 149 nodeless miles of I-75 between Toledo and
  Dayton.
- **Bloomington, IN** -- splits the 173-mi Indy-Evansville I-69 leg.
- **Columbus, MS (Golden Triangle)** -- Tupelo-Tuscaloosa routes through it.
- **Ocala, FL** -- Tampa-Gainesville I-75; real distribution hub.
- **Longview, TX** -- the I-20 east-Texas void behind Tyler-Texarkana.
- **Walla Walla, WA** -- Pendleton-Lewiston and Tri-Cities-Lewiston both want
  US-12 through it.
- **Wichita Falls, TX** -- WAS flagged "check if node"; it IS one (built
  2026-07-09 with the US-287 legs), so no action.
- Second tier: New London CT (I-95), Cumberland MD (I-68), Natchez MS (US-61,
  flavor), Cookeville TN (verify the Nashville-Knoxville I-40 leg has a mid
  node).

Interleave this ~10-city promotion slate after Batches 3-4 rather than after all
eleven; it dovetails with the already-approved ~35-node handoff.

## 4. Dubious pairs -- do NOT connect (or owner-judgment)

**Hard no (no real through-road; would misrepresent geography):**
- Milwaukee-Muskegon, Green Bay-Traverse City, Escanaba-Traverse City -- Lake
  Michigan straight-line artifacts (the first is literally a ferry).
- Baker City-McCall -- Hells Canyon/Wallowas; no road exists.
- Green River-Nephi -- San Rafael Swell; no road.
- Eureka CA-Yreka -- Trinity Alps.
- La Grande-Lewiston -- Wallowas; the drive is a huge detour.
- Laramie-Silverthorne -- remote 2-lane through North Park; not a truck route.
- Harrisonburg-Morgantown -- Allegheny ridges; US-33 is a 2-lane mountain crawl.
- Roanoke-Pikeville -- no through-road across the coalfields.
- Glasgow-Miles City -- Fort Peck country; MT-24 is not freight.
- Coeur d'Alene-Libby -- the real link is **Sandpoint-Libby (US-2/MT-200)**;
  build that instead.

**Owner judgment (real road, questionable as a truck leg):**
- Missoula-Lewiston -- US-12 over Lolo Pass: real, historic, and 200 winding
  miles trucks mostly avoid. Could be a deliberate hard-mode flavor leg; not a
  connectivity leg.
- Colorado Springs-Edwards -- US-24 over Tennessee Pass via Leadville: legal,
  brutal, gorgeous. Same category.
- Cape Coral-Port Saint Lucie -- SR-70 across Okeechobee country is real but
  lonely two-lane.
- Worcester-Portsmouth, Hartford-Newport RI -- no natural through-highway; skip.
- Nashville-Murfreesboro -- fold Murfreesboro into the I-24 leg rather than
  spoke it.

## 5. Definition of done

Map connectivity is DONE when: every city reaches each of its three nearest
distinct-city neighbors (under ~120 straight-line miles) either directly or
through one intermediate city that actually sits on the driving route; every
two-digit interstate and every named US-highway spine the map claims to model is
traversable end-to-end as a chain of legs with no segment longer than about 200
driving miles lacking a node; no leg exists between two nodes of the same metro,
across a water or mountain barrier without a real signed truck route, or
duplicating a two-hop path along the same highway; and a fresh run of both scans
returns only pairs with a nameable reason to reject. At that point new *legs*
stop adding player value, and all remaining growth comes from promoting cities
into voids -- which is a different program with its own economics.

Process note: re-run the nearest-neighbor scan after every two or three batches
rather than working from the 2026-07-09 snapshot -- each batch re-bridges dozens
of its remaining entries.
