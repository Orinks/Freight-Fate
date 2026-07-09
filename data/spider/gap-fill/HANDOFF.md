# United States coverage handoff (Fable analysis, 2026-07-09)

This is the working program for covering the United States -- highways and
cities -- before any Canada work. It supersedes PROGRAM.md (kept for the full
review text). Owner goal, verbatim: cover as much highway and cities as we can
in the U.S., systematically, not randomized. Opus executes; the owner reads
along; Fable re-analyzes on request only.

The work is generally autonomous per the established rules (node rule,
enrichment recipe, spoken invariants). Everything below is ordered so Opus can
start at the top and keep going.

## PROGRESS (update as batches land)

- [x] Jackson TN + Cookeville TN promoted, I-40 split (2b3ccc1)
- [x] Batch 0 -- 9 Interstate spine emergencies (2758aff)
- [x] Batch 1b -- 11 Deep South legs (452a246)
- [x] Batch 2 -- 10 Georgia legs (a6fa281)
- [x] Batch 3 -- 13 Kentucky/Appalachian legs (a69de00)
- [x] Scanner re-run 2026-07-10: corridor 392->353, nn 184->160; catalogs
      refreshed to *-2026-07-10.txt. Now **409 cities / 830 legs / 107,909 mi**.
- [x] Batch 4 -- 13 Carolinas & Virginia legs (2b5f7a2)
- [x] City Wave 1 -- 7 cities via leg-splits (4569180): Wytheville, Bloomington,
      Lima, Ocala, Dubuque, Terre Haute, Effingham.
- [x] City Wave 1 leftovers -- Lynchburg VA + Longview TX hubs (bbab3d0).
      Wave 1 COMPLETE (9 cities). Placed owner's Midlothian checkpoint.
- [x] Batch 5 -- 14 Northeast legs (7446f43).
- [x] Scanner re-run 2026-07-10b: corridor 353->359 (UP -- City Wave 1's new
      cities create fresh neighbor-gaps), nn 160->157. Catalogs = *-2026-07-10b.txt.
      Now **418 cities / 869 legs / 110,969 mi**.
- [x] Batch 6 -- 19 Midwest lattice legs (696a693). Now 418 cities / 888 legs /
      112,691 mi.
- [ ] City Wave 2  <-- NEXT (analysis done -- see CITY WAVE 2 PLAN below)
- [ ] Batch 7+ per Part 3.

### CITY WAVE 2 PLAN (analyzed 2026-07-10, ready to execute)
None are clean checkpoint-splits. Verified nearest nodes + which sit on a bypass
leg between two neighbors. Build pattern = Longview/Lynchburg (mint city, add spoke
legs to 2-3 nearest nodes; where the city sits on a bypass leg, REPLACE that leg
with two halves through the city -- but FIRST check ORIGINAL_ADJACENT_PAIRS, none
of these four were). Regions from classifier. Highways are best-effort; checkpoints
carry the geography.
- **Cumberland MD** -- CLEAN SPLIT of morgantown->hagerstown I-68 (on-route 0.22mi):
  morgantown->cumberland + cumberland->hagerstown. + cumberland->winchester (US-50).
- **St Joseph MO** -- bypass of kansas_city->omaha I-29 (city ~few mi off): replace
  with kc->st_joseph + st_joseph->omaha (I-29).
- **Mansfield OH** -- bypass of columbus->cleveland I-71 (3mi off): replace with
  columbus->mansfield + mansfield->cleveland (I-71).
- **Youngstown OH** -- bypass of akron->pittsburgh I-76 (6mi off): replace with
  akron->youngstown + youngstown->pittsburgh; + youngstown->cleveland (optional).
- **Staunton VA** -- spokes: staunton->harrisonburg (I-81) + staunton->charlottesville
  (I-64). (harrisonburg->charlottesville US-33 bypasses it -- keep, add spokes.)
- **Paducah KY** -- spokes: paducah->clarksville (I-24) + paducah->evansville (I-69).
  + paducah->cape_girardeau (I-57) once Cape is a node.
- **Owensboro KY** -- spokes: owensboro->evansville (US-60) + owensboro->bowling_green
  (US-231). (no existing bypass leg.)
- **Daytona Beach FL** -- spokes: daytona->orlando (I-4) + daytona->jacksonville (I-95).
- **Waterloo IA** -- spokes: waterloo->cedar_rapids (US-380) + waterloo->dubuque (US-20).
- **Parkersburg WV** -- spokes: parkersburg->charleston (I-77) + parkersburg->morgantown.
- **Mount Vernon IL** -- spokes: mount_vernon->effingham (I-57) + mount_vernon->evansville
  (I-64). (I-57 x I-64 junction.)
- **Cape Girardeau MO** -- spokes: cape->st_louis (I-55) + cape->paducah (I-57).
- **Kingsport TN** -- DEFER/DROP: the Tri-Cities is already served by Johnson City +
  the Bristol checkpoint; only add if the owner wants it as a freight destination.
Cadence: re-run BOTH scanners after Wave 2 (it adds ~12 cities -> reshapes gaps).
- Cadence reminder: re-run BOTH scanners every 2-3 batches (done above); the
  flaky --add-maxspeed dispatcher needs a per-leg retry loop after each batch.

## Part 0 -- housekeeping (DONE -- Batch 0 committed as 2758aff)

The worktree held Batch 0, fully built and TEST-GREEN but uncommitted:
nine interstate legs (New York-Albany I-87, Colorado Springs-Pueblo I-25,
Chicago-Champaign I-57, Sacramento-Redding I-5, Indianapolis-Evansville I-69,
Kansas City-Joplin I-49, Toledo-Dayton I-75, Riverside-Victorville I-15 Cajon
Pass as terrain mountain, Tallahassee-Lake City I-10). Checkpoints, POIs,
landmarks, interchanges, grades, speed, enrich-all: all done. Test leg count
already bumped to 794. POI names already cleaned (dropped two mis-tags,
renamed bare TA and two initialism rest areas).

To land it:
1. Add this bullet under Unreleased / Added in CHANGELOG.md:

   - **Nine famous Interstate stretches open up at once.** The New York
     Thruway from the city to Albany up the Hudson Valley; Interstate 5 from
     Sacramento to Redding; the Cajon Pass climb from Riverside to
     Victorville -- a real mountain grade; Interstate 75 from Toledo to
     Dayton past Neil Armstrong's hometown of Wapakoneta; Kansas City to
     Joplin past Harry Truman's birthplace; plus Chicago to Champaign,
     Indianapolis to Evansville, Colorado Springs to Pueblo, and Tallahassee
     to Lake City across the quiet Big Bend.

2. Update the milestone bullet's totals (run
   `tools/map_stats.py --since origin/dev`; at build time it read 104,473
   miles / 407 cities / 794 legs).
3. Commit (feat(map), describe as gap Batch 0), push to fork, confirm PR #58
   CI goes green.

## Part 1 -- the dataset

- `gap-corridor-2026-07-09.txt` -- 392 city PAIRS with no leg, where the real
  truck route passes no other map city. Candidate direct legs.
- `gap-nearest-neighbor-2026-07-09.txt` -- 184 city PAIRS where a city is not
  connected to one of its three nearest neighbors. Mostly overlaps the first
  list; treat as a checklist, not a queue.
- Both scanners are committed beside this file (gap_scan_corridor.py,
  gap_scan_nn.py). RE-RUN BOTH after every two or three batches -- each built
  batch re-bridges dozens of remaining entries, so the survivor list shrinks
  fast. Never work from a stale snapshot.
- SIXTEEN pairs from these catalogs are ALREADY BUILT this session (the Deep
  South seven, plus Batch 0's nine). Tick them off mentally when reading the
  raw files; the batch lists below already exclude them.

These pairs are LEGS between existing cities. The separate CITY program is
Part 4.

## Part 2 -- triage rules and standing exclusions

Apply in order; first failure excludes a pair.

- Rule 1, same metro: never connect two nodes of one urban area.
- Rule 2, one numbered highway: the leg must be speakable in one breath
  ("US-49 south, 70 miles"); no county-road chains, no water/mountain
  fantasies.
- Rule 3, distinct freight identity: both endpoints need their own economic
  reason to ship.
- Rule 4, pick one of triangle: when A-B, B-C, A-C all appear, build the two
  that follow signed highways, drop the hypotenuse.
- Rule 5, land on the core: re-anchor satellite-city pairs onto the metro
  core or the town actually on the highway.
- Rule 6, terrain honesty: no ferries; no 2-lane seasonal passes as a pair's
  only representation.
- Plus the established build rules: check ALL intermediate nodes before
  minting a "missing" link (an existing node may already bridge it); new-leg
  order of operations (geometry first, enrich-all last); terrain =
  length-weighted dominant cross-checked against a neighboring leg; every
  spoken name real and initialism-free.

NEVER BUILD (intra-metro): Los Angeles-Santa Ana, Riverside-Santa Ana,
Los Angeles-Valencia, Santa Ana-Oceanside, San Diego-Oceanside, San
Francisco-Fairfield, Sacramento-Fairfield, Santa Rosa-Fairfield,
Stockton-Fairfield, Miami-Coral Springs, Coral Springs-West Palm Beach,
Dallas-McKinney, Chicago-Aurora, Aurora-Gary, Nashville-Murfreesboro,
Lafayette LA-Sulphur, Lancaster-Los Angeles, San Diego-Santa Ana,
Everett-Olympia, Bellingham-Tacoma, Nephi-Ogden, Trenton-Scranton.

NEVER BUILD (no real through-road): Milwaukee-Muskegon (ferry), Green
Bay-Traverse City, Escanaba-Traverse City, Baker City-McCall, Green
River-Nephi, Eureka CA-Yreka, La Grande-Lewiston, Laramie-Silverthorne,
Harrisonburg-Morgantown, Roanoke-Pikeville, Glasgow-Miles City, Coeur
d'Alene-Libby (build Sandpoint-Libby instead).

REDUNDANT MESH (drop; full reasoning in PROGRAM.md): the Aurora, Gary,
Fort Wayne, Grenada, and Killeen hub meshes; the Kentucky, DC/Chesapeake, and
long-shot redundancy lists. When in doubt apply Rule 4.

OWNER-JUDGMENT FLAVOR (park until asked): Missoula-Lewiston (Lolo Pass),
Colorado Springs-Edwards (Tennessee Pass), Cape Coral-Port Saint Lucie,
Tonopah-Alamo (Extraterrestrial Highway -- billboard gold when wanted).

## Part 3 -- leg batches, in build order

Roughly 110 clearly-worth-building pairs survive triage. Full pair lists per
batch are in PROGRAM.md sections; headline sequence:

- Batch 1b, Deep South finish: Mobile-Hattiesburg US-98, Baton Rouge-Gulfport
  I-12, Shreveport-Texarkana, Texarkana-El Dorado, Little Rock-El Dorado,
  Huntsville-Chattanooga US-72, Opelika-Columbus GA, Columbus GA-Dothan,
  Crestview-Dothan, Birmingham-Opelika US-280, Montgomery-Meridian US-80.
- Batch 2, Georgia web: Athens-Macon, Athens-Augusta, Athens-Greenville SC,
  Macon-Columbus, Cordele-Albany, Albany-Valdosta, Albany-Tallahassee US-19,
  Valdosta-Tallahassee, Valdosta-Dothan US-84, LaGrange-Columbus.
- Batch 3, Kentucky parkways and Appalachia: Lexington-Elizabethtown,
  Elizabethtown-Evansville, London-Bowling Green, Mount Sterling-Richmond,
  Mount Sterling-Hazard, Huntington-Paintsville, Paintsville-Hazard, Johnson
  City-Pikeville, Charleston-Pikeville, Morristown-London, Morgantown-Beckley,
  Morgantown-Hagerstown I-68, Pittsburgh-Hagerstown. (Beckley-Winston-Salem
  waits for the Wytheville city, Part 4.)
- Batch 4, Carolinas and Virginia: Charlotte-Winston-Salem,
  Greensboro-Fayetteville, Wilmington-Lumberton, Charlotte-Lumberton,
  Charleston-Florence US-52, Norfolk-Petersburg US-460, Raleigh-Petersburg,
  Roanoke-Winston-Salem US-220, Asheville-Spartanburg, Asheville-Greenville,
  DC-Winchester I-66, DC-Hagerstown, DC-Charlottesville US-29,
  Petersburg-Virginia Beach.
- CITY WAVE 1 goes here -- see Part 4.
- Batch 5, Northeast mesh: Providence-Worcester, Boston-Manchester I-93,
  Hartford-Providence, Providence-New Haven, Philadelphia-Allentown,
  Allentown-Trenton, Baltimore-Dover, DC-Salisbury US-50, Atlantic City-Dover,
  Harrisburg-Wilmington, Washington-Carlisle US-15, Pittsburgh-Carlisle,
  Binghamton-Utica, Albany-Montpelier, Portland ME-Montpelier.
- Batch 6, Midwest lattice: Cedar Rapids-Iowa City I-380 (the single most
  obvious gap in either file), Peoria-Springfield, Peoria-Decatur,
  Decatur-Bloomington, Champaign-Lafayette I-74, St. Louis-Decatur,
  Detroit-Ann Arbor, Ann Arbor-Toledo, Ann Arbor-Flint, Toledo-Columbus US-23,
  Kalamazoo-Elkhart, Fort Wayne-Elkhart, Fort Wayne-Lansing I-69, Fort
  Wayne-Gary US-30, Lansing-Kalamazoo, Milwaukee-Rockford, Indianapolis-South
  Bend US-31, Muskegon-Traverse City US-31, Grand Rapids-Saginaw.
- CITY WAVE 2 goes here.
- Batch 7, Texas and southern plains: Lake Charles-Orange I-10, College
  Station-Temple, Waco-Tyler, Tyler-Texarkana, Fort Smith-Texarkana US-71
  (with KC-Joplin done this completes the future I-49 line),
  Tulsa-Fayetteville US-412, Tulsa-Enid, Wichita-Tulsa, San Angelo-Junction,
  San Angelo-Del Rio US-277, San Angelo-Fort Stockton US-67, Odessa-Fort
  Stockton, Fort Stockton-Midland, Austin-Kerrville US-290.
- Batch 8, Kansas/Nebraska ladder: Dodge City-Hays US-183, Garden City-Colby
  US-83, North Platte-Colby US-83, Kearney-Hays, Lincoln-Junction City US-77,
  Bismarck-Minot, Mitchell-Watertown, Sioux Falls-Mankato, Willmar-Watertown,
  Columbia-Rolla US-63, KC-Springfield MO-13, Springfield-Harrison,
  Conway-Harrison, Bentonville-Harrison (Ozark grade flavor).
- CITY WAVE 3 goes here.
- Batch 9, California real legs: Fresno-Visalia CA-99, San Jose-Salinas
  US-101, Salinas-Santa Maria US-101, SF-Santa Rosa US-101, San Jose-Stockton,
  Bakersfield-Barstow SR-58 Tehachapi (grade), Lancaster-Barstow,
  Lancaster-Victorville, San Diego-Riverside I-15, Riverside-Indio I-10,
  Indio-El Centro, Indio-Yuma (verify road), Oxnard-Valencia SR-126, Klamath
  Falls-Mount Shasta US-97, Crescent City-Coos Bay US-101.
- Batch 10, Pacific Northwest: Salem-Corvallis, Newport-Albany US-20,
  Salem-Bend US-20 Santiam Pass (grade), Medford-Klamath Falls,
  Astoria-Olympia US-101, Seattle-Wenatchee US-2 Stevens Pass (grade), Moses
  Lake-Wenatchee, Tri-Cities WASHINGTON-Moses Lake (the existing
  tri_cities_wa_us node -- not the Tennessee Tri-Cities of Wave 2),
  Wenatchee-Yakima US-97, Yakima-Moses
  Lake, Tacoma-Yakima US-12, Newberg-Woodburn, McMinnville-Woodburn,
  Lewiston-Coeur d'Alene US-95, Coeur d'Alene-Sandpoint, McCall-Ontario,
  Sandpoint-Libby.
- Batch 11, Big Sky and Great Basin: Helena-Bozeman, Missoula-Helena US-12,
  Missoula-Kalispell US-93, Great Falls-Havre US-87, Casper-Gillette,
  Gillette-Miles City, Fort Collins-Laramie US-287, Dickinson-Williston,
  Williston-Glendive, Wolf Point-Glendive, Battle Mountain-Austin NV,
  Tonopah-Austin, Elko-Eureka NV, Twin Falls-Wells US-93, West Wendover-Ely,
  Tonopah-Fallon US-95, Winnemucca-Fallon, Cedar City-Richfield, Provo-Green
  River US-6 Soldier Summit (the best grade-physics leg in the file), Cedar
  City-Alamo.

## Part 4 -- the city program (NEW, from tonight's missing-metro sweep)

A sweep of about 165 significant US metros and interstate junction towns
against the current 407-city map, cross-checked against the promotion slate
the leg data implied. Slug variants verified (Saint George UT and Sault Ste
Marie MI exist; they are NOT missing). The old July-7 "35 approved nodes" are
all built -- ignore that list.

Each city below still gets the standard node checks at build time (dedupe
against slug variants, region FROM THE CLASSIFIER, split-don't-duplicate when
it lands on an existing leg -- e.g. Lima splits the new Toledo-Dayton leg,
Bloomington splits Indianapolis-Evansville).

CITY WAVE 1 -- corridor-critical, build after Batch 4 (~11 cities). These
unlock or split legs the batch plan needs:
- [DONE 2026-07-09, commit 2b3ccc1] Jackson, Tennessee AND Cookeville,
  Tennessee -- both promoted and the I-40 legs split
  (memphis->jackson->nashville, knoxville->cookeville->nashville); Buck Snort
  and the other curated checkpoints preserved; Cumberland Plateau "mountain"
  and Highland Rim "hills" pins held. These two are OFF the build list.
- Wytheville, Virginia -- I-77 x I-81 junction; unlocks Beckley-Winston-Salem
  as two real legs.
- Lynchburg, Virginia -- US-29/US-460 hub; fixes the Roanoke-Charlottesville
  detour.
- Bloomington, Indiana -- splits the new I-69 Indy-Evansville leg.
- Lima, Ohio -- splits the new I-75 Toledo-Dayton leg (prefer over Findlay:
  bigger, I-75 x US-30).
- Terre Haute, Indiana -- I-70 Indianapolis-St. Louis midpoint, genuine void.
- Effingham, Illinois -- I-57 x I-70 junction, famous trucking crossroads.
- Ocala, Florida -- I-75 Tampa-Gainesville, real distribution hub.
- Longview, Texas -- I-20 east-Texas void; enables Tyler-Texarkana chain.
- Dubuque, Iowa -- tri-state US-151/US-61 hub.

CITY WAVE 2 -- eastern/central voids, build after Batch 6 (~12 cities):
- Paducah, Kentucky (I-24 x Ohio River) and Owensboro, Kentucky (US-60).
- Tri-Cities Tennessee/Virginia, DOWNGRADED after verification (NOT the
  existing Washington tri_cities_wa_us node): the corridor was worked
  recently -- Morristown and Johnson City are nodes, and the 176mi
  johnson_city-roanoke I-81 leg already SPEAKS Bristol, Abingdon, Marion,
  Wytheville, Dublin, Christiansburg, and Salem as checkpoints. Promoting
  Wytheville (Wave 1) splits that leg and anchors I-81; after that,
  Kingsport/Bristol move to Wave 4 owner-picks unless the owner wants the
  Tri-Cities as a freight destination in its own right. Kingsport sits on
  US-11W/US-23 off the built path -- it would also ride the future Batch 3
  johnson_city-pikeville leg as a checkpoint.
- Staunton, Virginia -- I-81 x I-64 junction.
- Cumberland, Maryland -- I-68 mid-void (with the Morgantown-Hagerstown leg).
- Parkersburg, West Virginia -- I-77 Ohio River void.
- Youngstown, Ohio -- I-76/I-80 between Akron and Pittsburgh.
- Mansfield, Ohio -- I-71 Columbus-Cleveland midpoint.
- Waterloo, Iowa -- Avenue of the Saints void.
- Saint Joseph, Missouri -- I-29 KC-Omaha void (slug: saint_joseph_mo_us).
- Cape Girardeau, Missouri -- I-55 St. Louis-Memphis void.
- Mount Vernon, Illinois -- I-57 x I-64 junction (alternative: Carbondale).
- Daytona Beach, Florida -- I-95 x I-4 junction, closes the Florida loop.

CITY WAVE 3 -- plains/western voids, build after Batch 8 (~12 cities):
- Ardmore, Oklahoma -- I-35 OKC-Dallas void.
- Muskogee or McAlester, Oklahoma -- the I-40/US-69 Texoma freight diagonal;
  pick per the node rule when wiring.
- Lawrence, Kansas -- I-70 (the owner's old un-ticked item; now approved as
  part of this wave unless he objects).
- Hutchinson or Salina-adjacent void is COVERED; skip Manhattan/Emporia unless
  a leg needs them (Rule 3 borderline).
- Liberal, Kansas -- US-54/US-83 corner void.
- Scottsbluff, Nebraska -- Panhandle void, US-26.
- Pierre, South Dakota -- US-83/US-14; a state capital with no node.
- Rawlins, Wyoming -- splits the long I-80 Laramie-Rock Springs stretch.
- Roswell + Carlsbad or Hobbs, New Mexico -- the southeast New Mexico oil
  patch is the largest all-void region in the lower 48 on this map; two
  cities minimum (US-285/US-62).
- Farmington, New Mexico -- Four Corners void (US-550/US-64).
- Durango, Colorado -- pairs with Farmington on US-550.
- Alexandria, Louisiana -- I-49 midpoint between Shreveport and Lafayette;
  finishes the in-state I-49 chain.

CITY WAVE 4 -- coastal/flavor, owner picks (park until asked): Naples FL
(Alligator Alley), Key West FL (US-1 Overseas Highway -- superb audio flavor),
Panama City FL, Brunswick GA (I-95 Savannah-Jacksonville), San Luis Obispo +
Santa Barbara CA (completes coastal US-101 with existing Santa Maria/Oxnard),
Modesto + Merced CA (completes CA-99 chain), Walla Walla WA (US-12), Port
Angeles WA, Victoria TX, Lufkin TX, Paris/Sherman TX, Natchez MS, Columbus MS
(Golden Triangle), Florence AL (the Shoals), Rome GA, Gadsden AL, Cookeville
TN, New London CT, Houma LA, Natchitoches LA, Clovis NM, Socorro NM (now a
checkpoint; only if a US-60 leg wants it), Moab UT, Vernal UT, Logan UT,
Prescott AZ, Winslow/Holbrook AZ (keep as Route 66 checkpoints unless
promoted for flavor), Aberdeen SD, Alpena MI.

DO NOT PROMOTE (metro-covered or better as checkpoints): Vancouver WA
(Portland), Stamford CT (New York), Council Bluffs IA (Omaha), Superior WI
(Duluth), Auburn AL (Opelika), Bryan TX (College Station), Denton TX
(DFW), Palm Springs CA (Indio), Casa Grande AZ (checkpoint between
Phoenix-Tucson), Kokomo/Muncie IN, Marion/Zanesville/Marietta OH, Ames IA,
Selma AL, Big Spring/Pecos TX (checkpoints on I-20), Deming NM (checkpoint),
Hastings/Norfolk NE, Ottumwa/Mason City/Kirksville/Quincy (Rule 3 borderline
-- revisit only if a scan pair demands them), Danville IL, Pontiac IL,
Woodward/Ponca City OK (revisit with a US-412/US-64 corridor), Wheeling WV
(covered by Pittsburgh-Columbus I-70 checkpoints), Clarksburg WV, Danville VA
(checkpoint on a future US-29 leg), Ellensburg WA (checkpoint on I-90),
Aberdeen WA, Sierra Vista AZ, Show Low/Globe AZ, Alamogordo NM, Uvalde/Eagle
Pass TX (Del Rio covers the border unless a US-90/US-277 pass wants them),
Eureka CA area additions.

## Part 5 -- cadence, scale, and done

- Cadence: two or three leg batches, then a city wave, then RE-RUN BOTH
  SCANNERS and re-triage. Cities change the scan results (they bridge pairs
  and create new near-neighbor entries), so never build more than three
  batches on a stale scan.
- Scale estimate: ~110 clear legs + ~35-45 cities across the waves. That is
  roughly 10-15 build sessions at the current pace, landing the map somewhere
  north of 115,000 drivable miles with every two-digit interstate continuous.
- Done (from the review, unchanged): every city reaches its three nearest
  distinct neighbors directly or via one on-route intermediate; every claimed
  interstate/US spine traversable end to end; no same-metro, no-road, or
  duplicate legs; a fresh scan returns only pairs with a nameable reason to
  reject. Then the U.S. is covered, and Canada (Alcan program) unblocks --
  gated anyway on the 96 GB RAM arrival for the world extract.

## Part 6 -- operational notes for Opus (compressed; details in the runbook)

- Services: ORS localhost:8080 (ORS_API_KEY=selfhosted), Overpass
  localhost:12347 -- ALWAYS export OVERPASS_URL or tools crawl the public API.
- New LEG order: checkpoints, then refresh-geometry (ors), THEN
  POIs/landmarks/interchanges(Interstate only)/maxspeed, enrich-all LAST
  (fills state_miles + crossings; without it the leg is unplayable).
- New CITY: region = classify_region(state, lat, lon), never neighbor-matched;
  locations []; when the city sits on an existing leg, SPLIT that leg (keep
  curated content; the old direct stays only if genuinely shorter); check all
  intermediate nodes before adding any leg.
- Every batch: bump the leg count in tests/test_route_coverage_tool.py, run
  test_regions + test_world + test_world_overlay + test_route_coverage_tool +
  test_place_checkpoints, ruff, index_world --check; terrain =
  length-weighted dominant matched to a neighbor leg; scan new POI names for
  initialisms/store numbers/non-freight mis-tags; changelog bullet per batch
  (player language); commit per batch; push and watch PR #58 CI.
- Redundant-atomic questions for the owner stay in CHANGES.md open-questions.
