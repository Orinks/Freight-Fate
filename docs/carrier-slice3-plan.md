# Carrier slice 3 plan — regional, local, and Alaska carriers

Status: **plan only — no carrier data yet.** `data/carriers.json` is not
touched until this list passes a realism cut. Second pass: the review kept
the plan and asked for the fixes recorded in §11 (resolved decisions).

Parent: ROADMAP "Career carriers (slices 2–4)" — the row "The 16 regionals
plus an Alaska regional". Slices 1 and 2 (carrier-owned terminals, the
truthful parked-at line, the carrier-first start picker) are merged into
`feat/career-2.0`.

Branch: `wip/carrier-s3-regionals` off `feat/career-2.0` at `6e852f24`.

---

## 0. Tier rules (approved)

| Tier | Hires | Runs (run band) | Notes |
| --- | --- | --- | --- |
| Local | within ~50 air mi of a terminal, same country | 25-150 mi | Metro cartage and drayage |
| Regional | within 250 air mi of any terminal, same country | 150-600 mi, inside its lane area | `hiring_radius_mi = 250` |
| National | every lower-48 city | 400-3000 mi | Unchanged: Northstar, Great Lakes Training, Summit Value |

The tighter of the run band and the level cap wins (today only the band max
folds into the distance cap; the band minimum stays deferred to slice 4).

Method for every number below: haversine air miles between world city
`lat`/`lon` in `data/world_data/{us,ca}/cities.json` (640 cities: 625
lower 48, 8 AK, 5 BC, 2 YT), same rule as `Carrier::hiring_terminal_city`.
Every terminal key listed here exists as a map city key today.

---

## 1. Proposed carriers at a glance

Prairie Link Regional (`prairie_link`, KC / Omaha / Wichita) stays as it is.
The count is settled: **sixteen new lower-48 regionals plus Prairie Link,
17 lower-48 regionals in all**, one Alaska regional, and three locals
(Chicago, LA, Anchorage). Names below are the post-screen names (§10).

| # | Name | Key | Tier | Terminal city keys | Cities in footprint | Only regional for |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Rockweed Coast Freight | `rockweed_coast` | regional | `boston_ma_us`, `hartford_ct_us`, `portland_me_us`, `albany_ny_us` | 40 | 5 |
| 2 | Kittatinny Crossroads Freight | `kittatinny_crossroads` | regional | `harrisburg_pa_us`, `baltimore_md_us`, `pittsburgh_pa_us`, `newark_nj_us` | 85 | 0 |
| 3 | Catawba Ridge Transport | `catawba_ridge` | regional | `charlotte_nc_us`, `greensboro_nc_us`, `richmond_va_us` | 82 | 7 |
| 4 | Sweetgum Regional | `sweetgum_regional` | regional | `atlanta_ga_us`, `birmingham_al_us`, `savannah_ga_us` | 82 | 0 |
| 5 | Sunpine Freight Lines | `sunpine_freight` | regional | `jacksonville_fl_us`, `orlando_fl_us`, `miami_fl_us` | 38 | 14 |
| 6 | Marsh Hen Carriers | `marsh_hen_carriers` | regional | `new_orleans_la_us`, `baton_rouge_la_us`, `mobile_al_us`, `jackson_ms_us` | 55 | 5 |
| 7 | Lone Mesa Freight | `lone_mesa_freight` | regional | `dallas_tx_us`, `houston_tx_us`, `san_antonio_tx_us`, `mcallen_tx_us` | 64 | 19 |
| 8 | Buttonbush River Lines | `buttonbush_river` | regional | `memphis_tn_us`, `little_rock_ar_us`, `nashville_tn_us` | 94 | 1 |
| 9 | Hellbender Valley Freight | `hellbender_valley` | regional | `columbus_oh_us`, `cincinnati_oh_us`, `louisville_ky_us`, `indianapolis_in_us`, `detroit_mi_us` | 101 | 13 |
| 10 | Loonwater Regional | `loonwater_regional` | regional | `minneapolis_mn_us`, `fargo_nd_us`, `bismarck_nd_us`, `duluth_mn_us`, `green_bay_wi_us` | 73 | 37 |
| 11 | Sandplum Plains Freight | `sandplum_plains` | regional | `oklahoma_city_ok_us`, `tulsa_ok_us`, `amarillo_tx_us`, `lubbock_tx_us` | 85 | 9 |
| 12 | Blue Grama Freight Lines | `blue_grama` | regional | `denver_co_us`, `cheyenne_wy_us`, `billings_mt_us` | 50 | 29 |
| 13 | Pinyon Basin Transport | `pinyon_basin` | regional | `salt_lake_city_ut_us`, `boise_id_us`, `las_vegas_nv_us` | 66 | 22 |
| 14 | Brittlebush Sun Freight | `brittlebush_sun` | regional | `phoenix_az_us`, `tucson_az_us`, `albuquerque_nm_us`, `el_paso_tx_us` | 51 | 17 |
| 15 | Tarweed Valley Freight | `tarweed_valley` | regional | `los_angeles_ca_us`, `fresno_ca_us`, `sacramento_ca_us` | 53 | 20 |
| 16 | Salmonberry Freight Lines | `salmonberry_freight` | regional | `seattle_wa_us`, `portland_or_us`, `spokane_wa_us`, `medford_or_us` | 54 | 36 |
| AK | Spruce Hen Line Freight | `spruce_hen_line` | regional (AK) | `anchorage_ak_us`, `fairbanks_ak_us` | 8 (all AK) | 8 |
| L1 | Bubbly Creek Cartage | `bubbly_creek_cartage` | local | `chicago_il_us`, `gary_in_us`, `aurora_il_us` | 4 | — |
| L2 | Basin Harbor Drayage | `basin_harbor_drayage` | local | `los_angeles_ca_us`, `riverside_ca_us` | 6 | — |
| L3 | Knik Arm Cartage | `knik_arm_cartage` | local (AK) | `anchorage_ak_us` | 3 | — |

Coverage with all sixteen plus Prairie Link, including the Green Bay
terminal on Loonwater Regional: **625 of 625** lower-48 cities have at least
one regional (248 have exactly one, 257 two, 101 three, 19 four). No city is
left with nationals only (§6).

Names are fictional and follow the existing style (place or landscape word
plus Freight / Lines / Regional / Transport / Carriers / Cartage). Every
name passed the screen in §10; sixteen first-pass names were replaced there.

---

## 2. Regional carriers

### 1. Rockweed Coast Freight (`rockweed_coast`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `boston_ma_us`, `hartford_ct_us`, `portland_me_us`, `albany_ny_us` (widest terminal pair 190 air mi).
- **Lane area:** New England and the upper Hudson: Boston, Hartford, Portland ME, and Albany terminals; lanes Maine to the NYC metro and west to the Hudson.
- **Hiring footprint:** 40 map cities; states NY 7, PA 7, NJ 5, MA 4, CT 4, NH 3, VT 3, ME 3, RI 2, DE 2.
- **Only regional for:** Bangor ME, Lewiston ME, Portland ME, Burlington VT, Montpelier VT.

### 2. Kittatinny Crossroads Freight (`kittatinny_crossroads`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `harrisburg_pa_us`, `baltimore_md_us`, `pittsburgh_pa_us`, `newark_nj_us` (widest terminal pair 306 air mi).
- **Lane area:** Mid-Atlantic: Harrisburg, Baltimore, Pittsburgh, and Newark terminals; lanes along I-76/I-78/I-81/I-95 between the NJ ports, the PA distribution belt, and the Chesapeake.
- **Hiring footprint:** 85 map cities; states VA 13, OH 12, PA 11, NY 9, WV 6, NJ 5, MA 4, CT 4, MD 4, KY 4, MI 3, NH 3, RI 2, DE 2, DC 1, NC 1, VT 1.
- **Only regional for:** none (every city here is also reached by another regional).

### 3. Catawba Ridge Transport (`catawba_ridge`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `charlotte_nc_us`, `greensboro_nc_us`, `richmond_va_us` (widest terminal pair 248 air mi).
- **Lane area:** Carolinas and Virginia: Charlotte, Greensboro, and Richmond terminals; lanes along I-85/I-40/I-95 from Richmond to upstate SC.
- **Hiring footprint:** 82 map cities; states VA 15, NC 14, GA 11, PA 7, SC 7, WV 6, KY 6, TN 5, MD 4, NJ 4, DE 2, DC 1.
- **Only regional for:** Durham NC, Greensboro NC, Greenville NC, Jacksonville NC, New Bern NC, Raleigh NC, Winston-Salem NC.

### 4. Sweetgum Regional (`sweetgum_regional`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `atlanta_ga_us`, `birmingham_al_us`, `savannah_ga_us` (widest terminal pair 347 air mi).
- **Lane area:** Deep South hub: Atlanta, Birmingham, and Savannah terminals; lanes between the Port of Savannah, metro Atlanta DCs, and Birmingham.
- **Hiring footprint:** 82 map cities; states GA 20, TN 13, AL 12, FL 11, MS 10, SC 7, NC 6, KY 2, VA 1.
- **Only regional for:** none (every city here is also reached by another regional).

### 5. Sunpine Freight Lines (`sunpine_freight`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `jacksonville_fl_us`, `orlando_fl_us`, `miami_fl_us` (widest terminal pair 328 air mi).
- **Lane area:** Florida: Jacksonville, Orlando, and Miami terminals; lanes along I-95/I-75/I-4 inside the peninsula and up to south Georgia.
- **Hiring footprint:** 38 map cities; states FL 23, GA 13, SC 1, AL 1.
- **Only regional for:** Cape Coral FL, Coral Springs FL, Fort Myers FL, Key West FL, Lakeland FL, Miami FL, Naples FL, North Port FL, Palm Bay FL, Port Saint Lucie FL, Sarasota FL, Spring Hill FL, Tampa FL, West Palm Beach FL.

### 6. Marsh Hen Carriers (`marsh_hen_carriers`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `new_orleans_la_us`, `baton_rouge_la_us`, `mobile_al_us`, `jackson_ms_us` (widest terminal pair 188 air mi).
- **Lane area:** Central Gulf Coast: New Orleans, Baton Rouge, Mobile, and Jackson MS terminals; lanes along I-10/I-12/I-55/I-65 between the river ports and chemical belt.
- **Hiring footprint:** 55 map cities; states LA 12, MS 12, AL 10, AR 8, FL 4, GA 4, TX 3, TN 2.
- **Only regional for:** Baton Rouge LA, Hammond LA, Houma LA, New Orleans LA, Gulfport MS.

### 7. Lone Mesa Freight (`lone_mesa_freight`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `dallas_tx_us`, `houston_tx_us`, `san_antonio_tx_us`, `mcallen_tx_us` (widest terminal pair 462 air mi).
- **Lane area:** Texas Triangle and the border: Dallas, Houston, San Antonio, and McAllen terminals; lanes inside the I-35/I-45/I-10 triangle and down to the Rio Grande Valley crossings.
- **Hiring footprint:** 64 map cities; states TX 40, OK 13, LA 7, AR 4.
- **Only regional for:** Austin TX, Brownsville TX, College Station TX, Corpus Christi TX, Del Rio TX, Eagle Pass TX, Houston TX, Kerrville TX, Killeen TX, Lampasas TX, Laredo TX, Marble Falls TX, McAllen TX, Palestine TX, San Antonio TX, Temple TX, Uvalde TX, Victoria TX, Waco TX.

### 8. Buttonbush River Lines (`buttonbush_river`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `memphis_tn_us`, `little_rock_ar_us`, `nashville_tn_us` (widest terminal pair 325 air mi).
- **Lane area:** Mid-South: Memphis, Little Rock, and Nashville terminals; lanes along I-40/I-55/I-24 around the Memphis rail and river hub.
- **Hiring footprint:** 94 map cities; states AR 14, TN 12, KY 12, MS 10, OK 9, MO 6, GA 6, AL 6, LA 5, IN 5, TX 3, IL 3, OH 1, NC 1, KS 1.
- **Only regional for:** Poplar Bluff MO.

### 9. Hellbender Valley Freight (`hellbender_valley`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `columbus_oh_us`, `cincinnati_oh_us`, `louisville_ky_us`, `indianapolis_in_us`, `detroit_mi_us` (widest terminal pair 316 air mi).
- **Lane area:** Ohio Valley and lower Great Lakes: Columbus, Cincinnati, Louisville, Indianapolis, and Detroit terminals; lanes along I-70/I-71/I-65/I-75 and into Chicagoland and lower Michigan.
- **Hiring footprint:** 101 map cities; states IN 15, KY 14, OH 13, IL 12, TN 11, MI 11, VA 6, WV 6, PA 4, MO 2, NY 2, WI 2, AL 1, GA 1, MD 1.
- **Only regional for:** Bloomington IL, Champaign IL, Decatur IL, Galesburg IL, Peoria IL, Springfield IL, Anderson IN, Fort Wayne IN, Indianapolis IN, Kokomo IN, Lafayette IN, Muncie IN, Richmond IN.

### 10. Loonwater Regional (`loonwater_regional`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `minneapolis_mn_us`, `fargo_nd_us`, `bismarck_nd_us`, `duluth_mn_us`, `green_bay_wi_us` (widest terminal pair 636 air mi).
- **Lane area:** Upper Midwest and the western Great Lakes: Minneapolis, Fargo, Bismarck, Duluth, and Green Bay terminals; lanes along I-94/I-35/I-29/I-41/I-43 across MN, the Dakotas, Wisconsin, and the Upper Peninsula, and down the Mississippi to the Quad Cities.
- **Span note:** the Green Bay terminal makes Bismarck-Green Bay the widest pair of any regional (636 air mi, past the 600 mi run band max). No single run spans both ends; the terminals share one lane area the way the four approved wide spans do. Flagged for the cut, not blocking.
- **Hiring footprint:** 73 map cities; states MI 13, WI 12, MN 12, IA 11, SD 8, ND 8, IL 3, IN 3, MT 3.
- **Only regional for:** Davenport IA, Dubuque IA, Escanaba MI, Houghton MI, Iron Mountain MI, Marquette MI, Sault Ste. Marie MI, Bemidji MN, Duluth MN, Grand Rapids MN, Hibbing MN, Minneapolis MN, Rochester MN, St. Cloud MN, Willmar MN, Winona MN, Bismarck ND, Devils Lake ND, Dickinson ND, Fargo ND, Grand Forks ND, Jamestown ND, Minot ND, Williston ND, Aberdeen SD, Pierre SD, Watertown SD, Chippewa Falls WI, Eau Claire WI, Fond du Lac WI, Green Bay WI, La Crosse WI, Madison WI, Oshkosh WI, Rice Lake WI, Sheboygan WI, Wausau WI.

### 11. Sandplum Plains Freight (`sandplum_plains`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `oklahoma_city_ok_us`, `tulsa_ok_us`, `amarillo_tx_us`, `lubbock_tx_us` (widest terminal pair 377 air mi).
- **Lane area:** Southern Plains: Oklahoma City, Tulsa, Amarillo, and Lubbock terminals; lanes along I-40/I-44/I-35/I-27 and into the Permian edge.
- **Hiring footprint:** 85 map cities; states TX 30, OK 17, KS 12, AR 10, NM 9, MO 4, CO 3.
- **Only regional for:** Amarillo TX, Big Spring TX, Clarendon TX, Dumas TX, Lubbock TX, Midland TX, Pampa TX, Plainview TX, Stratford TX.

### 12. Blue Grama Freight Lines (`blue_grama`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `denver_co_us`, `cheyenne_wy_us`, `billings_mt_us` (widest terminal pair 454 air mi).
- **Lane area:** Front Range and high plains: Denver, Cheyenne, and Billings terminals; lanes along I-25/I-80/I-90 from Colorado Springs to Montana.
- **Hiring footprint:** 50 map cities; states CO 18, MT 11, WY 10, NE 4, SD 3, ID 1, KS 1, NM 1, OK 1.
- **Only regional for:** Burlington CO, Colorado Springs CO, Denver CO, Edwards CO, Fort Collins CO, Glenwood Springs CO, Limon CO, Silverthorne CO, Billings MT, Bozeman MT, Glasgow MT, Great Falls MT, Havre MT, Helena MT, Shelby MT, North Platte NE, Ogallala NE, Scottsbluff NE, Sidney NE, Hot Springs SD, Buffalo WY, Casper WY, Cheyenne WY, Gillette WY, Laramie WY, Lusk WY, Rawlins WY, Sheridan WY, Wheatland WY.

### 13. Pinyon Basin Transport (`pinyon_basin`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `salt_lake_city_ut_us`, `boise_id_us`, `las_vegas_nv_us` (widest terminal pair 517 air mi).
- **Lane area:** Great Basin: Salt Lake City, Boise, and Las Vegas terminals; lanes along I-15/I-80/I-84 between the Wasatch Front, southern Idaho, and Las Vegas.
- **Hiring footprint:** 66 map cities; states CA 18, AZ 11, UT 10, NV 10, ID 6, OR 4, WA 2, MT 2, CO 2, WY 1.
- **Only regional for:** Boise ID, Pocatello ID, Twin Falls ID, Alamo NV, Battle Mountain NV, Elko NV, Ely NV, Eureka NV, Wells NV, West Wendover NV, Winnemucca NV, Ontario OR, Cedar City UT, Green River UT, Logan UT, Moab UT, Nephi UT, Ogden UT, Provo UT, Richfield UT, Saint George UT, Salt Lake City UT.

### 14. Brittlebush Sun Freight (`brittlebush_sun`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `phoenix_az_us`, `tucson_az_us`, `albuquerque_nm_us`, `el_paso_tx_us` (widest terminal pair 345 air mi).
- **Lane area:** Desert Southwest: Phoenix, Tucson, Albuquerque, and El Paso terminals; lanes along I-10/I-17/I-25/I-40 and the Nogales crossing.
- **Hiring footprint:** 51 map cities; states AZ 22, NM 14, CO 7, TX 5, CA 3.
- **Only regional for:** Casa Grande AZ, Douglas AZ, Globe AZ, Holbrook AZ, Nogales AZ, Payson AZ, Phoenix AZ, Show Low AZ, Sierra Vista AZ, Tucson AZ, Winslow AZ, Albuquerque NM, Farmington NM, Gallup NM, Las Cruces NM, Socorro NM, El Paso TX.

### 15. Tarweed Valley Freight (`tarweed_valley`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `los_angeles_ca_us`, `fresno_ca_us`, `sacramento_ca_us` (widest terminal pair 361 air mi).
- **Lane area:** California and Reno: Los Angeles, Fresno, and Sacramento terminals; lanes along I-5/CA-99/I-80 from the LA basin through the Central Valley to Reno.
- **Hiring footprint:** 53 map cities; states CA 43, NV 7, AZ 3.
- **Only regional for:** Fairfield CA, Fresno CA, Merced CA, Modesto CA, Oxnard CA, Sacramento CA, Salinas CA, San Diego CA, San Francisco CA, San Jose CA, San Luis Obispo CA, Santa Barbara CA, Santa Maria CA, Santa Rosa CA, Stockton CA, Austin NV, Carson City NV, Fallon NV, Fernley NV, Reno NV.

### 16. Salmonberry Freight Lines (`salmonberry_freight`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `seattle_wa_us`, `portland_or_us`, `spokane_wa_us`, `medford_or_us` (widest terminal pair 454 air mi).
- **Lane area:** Pacific Northwest: Seattle, Portland, Spokane, and Medford terminals; lanes along I-5/I-84/I-90 from the Canadian line to southern Oregon and the Idaho panhandle.
- **Hiring footprint:** 54 map cities; states OR 20, WA 14, CA 11, ID 5, MT 4.
- **Only regional for:** Crescent City CA, Coeur d'Alene ID, Kellogg ID, Sandpoint ID, Kalispell MT, Libby MT, Superior MT, Albany OR, Astoria OR, Bend OR, Coos Bay OR, Corvallis OR, Eugene OR, Grants Pass OR, Klamath Falls OR, McMinnville OR, Medford OR, Newberg OR, Newport OR, Portland OR, Roseburg OR, Salem OR, The Dalles OR, Woodburn OR, Bellingham WA, Blaine WA, Everett WA, Longview WA, Moses Lake WA, Olympia WA, Port Angeles WA, Seattle WA, Spokane WA, Tacoma WA, Wenatchee WA, Yakima WA.

---

## 3. Local carriers

Chicago and LA are KEEP (resolved). The Anchorage local is new in this pass
(§4).

### L1. Bubbly Creek Cartage (`bubbly_creek_cartage`)

- **Tier:** local; hires within 50 air mi of a terminal; runs 25-150 mi.
- **Terminals:** `chicago_il_us`, `gary_in_us`, `aurora_il_us`.
- **Hiring footprint:** Chicago, Aurora, Gary, Kenosha.
- **Lane area:** Chicagoland rail ramps and DCs out to 150 mi — 28 map
  cities in band, including Milwaukee, Rockford, Peoria, South Bend, Fort
  Wayne, Indianapolis edge, Madison, and Grand Rapids.

### L2. Basin Harbor Drayage (`basin_harbor_drayage`)

- **Tier:** local; hires within 50 air mi of a terminal; runs 25-150 mi.
- **Terminals:** `los_angeles_ca_us`, `riverside_ca_us`.
- **Hiring footprint:** Los Angeles, Riverside, Santa Ana, Valencia,
  Lancaster, Victorville.
- **Lane area:** Inland Empire DCs and metro cartage out to 150 mi — 17 map
  cities in band, including San Diego, Bakersfield, Barstow, Oxnard, and
  Indio. Port drayage into the LA/Long Beach marine terminals needs a TWIC
  card; that waits for real drayage loads (ROADMAP row, §9).

---

## 4. Alaska carriers and the picker rule

### Spruce Hen Line Freight (`spruce_hen_line`)

- **Tier:** regional; `hiring_radius_mi = 250`, same country.
- **Terminals:** `anchorage_ak_us`, `fairbanks_ak_us`.
- **Hiring footprint:** all 8 AK map cities — Anchorage 0, Fairbanks 0,
  Wasilla 29, Palmer 37, Nenana 45, Healy 77, Glennallen 157, Tok 176 air
  mi from the nearer terminal.
- **Lane area: inside Alaska only.** The Parks, Glenn, Tok Cutoff, and
  Richardson corridors between Anchorage, Mat-Su, Fairbanks, and Tok. No
  loads leave AK. ALCAN through-freight is future work (§9).

### L3. Knik Arm Cartage (`knik_arm_cartage`)

- **Tier:** local; hires within 50 air mi of its terminal, same country;
  runs 25-150 mi.
- **Terminal:** `anchorage_ak_us`.
- **Hiring footprint:** Anchorage (0 air mi), Wasilla (29), Palmer (37).
  The next AK city, Glennallen, is 157 mi out.
- **Run footprint (25-150 mi):** Wasilla 29 and Palmer 37 are the only map
  cities in band. Anchorage itself is under 25 mi, and every other AK city
  is past 150 (Glennallen 157, Healy 186, Nenana 233, Fairbanks 259, Tok
  266). So the board has two destination cities until the map grows (Kenai,
  Seward, and Whittier would all sit in band) or slice 4 adds in-metro
  stops. Flagged for the cut; it does not block the carrier's main job,
  which is to be the Anchorage-area employer that is not Spruce Hen.
- **Lane area:** Port of Alaska and Ted Stevens cargo to Anchorage and
  Mat-Su distribution.

### How AK homes interact with the picker

- A home base is offerable when some carrier hires there
  (`is_offerable_home_city`). Nationals hire only in the lower 48, so today
  no AK city qualifies. With Spruce Hen Line in `data/carriers.json`, all
  eight AK cities become offerable. Anchorage, Wasilla, and Palmer list
  Spruce Hen Line and Knik Arm Cartage; the other five list Spruce Hen Line
  only.
- **BC and YT stay blocked with no code change:** regionals and locals hire
  in the same country only, and the nearest AK terminal is 490 air mi from
  Whitehorse and 688+ from every other BC/YT city. No other carrier hires
  there.
- No lower-48 carrier reaches AK (nationals stop at the lower 48, and no
  lower-48 terminal is within 250 mi), and neither AK carrier reaches a
  lower-48 city, so the two carrier lists never mix.
- Tests that pin Healy and Anchorage as not offerable flip to offerable;
  Whitehorse and Surrey stay excluded.

---

## 5. Termination and solvency fallback (rule change)

**Today:** `check_carrier_termination` (`states/city/terminal.rs`) and the
two solvency paths (`solvency.rs`, `set_carrier` with
`LAST_CHANCE_CARRIER_KEY`) always move the driver to Great Lakes Training
(`enforcement::LAST_CHANCE_CARRIER_KEY`). `change_carrier` then makes a
Great Lakes Training terminal the driver's home terminal. For an Alaska
driver that means Milwaukee, which is wrong: **a fired driver never moves to
Milwaukee.**

**New rule.** The fallback carrier is picked from the driver's home city
(`home_city`, else `home_terminal_city`):

1. Candidates are carriers that hire in the home city (the same test as
   `is_offerable_home_city`), **never the carrier that just fired the
   driver.**
2. Prefer a regional or local that hires there, nearest hiring terminal
   first (ties by carrier key, so the pick is stable).
3. Otherwise, in the lower 48, Great Lakes Training, which hires in every
   lower-48 city and stays the designated last-chance carrier (it never
   fires; `carrier_termination_due` already skips it). Other nationals do
   not take a driver another carrier just fired.
4. Otherwise (no non-firing carrier hires there), the driver stays home and
   unassigned: no carrier and no assigned truck, at the home city, until
   they apply somewhere.

The same pick serves the solvency path (an owner-operator who loses the
business), minus the "not the firing carrier" filter.

**Alaska outcomes:**

| Home | Fired by | Fallback |
| --- | --- | --- |
| Anchorage, Wasilla, Palmer | Spruce Hen Line | Knik Arm Cartage |
| Anchorage, Wasilla, Palmer | Knik Arm Cartage | Spruce Hen Line |
| Fairbanks, Nenana, Healy, Glennallen, Tok | Spruce Hen Line | none: home and unassigned |

**Lower 48:** the rule covers lower-48 fallbacks too. Every lower-48 city
has at least one regional (§6), so a driver fired by a national gets a
regional in the home city. The 248 cities with exactly one regional drop to
Great Lakes Training only when that regional is the one that fired them;
Chicago and LA homes also have a local to try first.

**If the rule does not land in this slice,** an AK termination keeps the
driver home and unassigned; it never moves them to Milwaukee. That minimum
guard (a same-country check before the Great Lakes Training fallback) is
small enough to land with the AK carriers either way.

Code touch points: `enforcement::LAST_CHANCE_CARRIER_KEY` (stays, as the
lower-48 last resort), `check_carrier_termination` in
`states/city/terminal.rs` (pick instead of hard-coding, and a new spoken
line naming the carrier that takes the driver on or saying they are home
without a seat), the two `set_carrier` calls in `solvency.rs`, and the
tests that pin Great Lakes Training (`states_city.rs`, `solvency/tests.rs`,
`carriers.rs`). An unassigned driver needs a save and hub state the menus
read clearly, which is the biggest part of the change.

---

## 6. Cities left with nationals only — resolved, none left

The Green Bay terminal on Loonwater Regional closes all six cities the
first pass left with nationals only:

| City | Air mi from Green Bay | Regional after the fix |
| --- | --- | --- |
| Davenport, IA | 244 | Loonwater Regional |
| Green Bay, WI | 0 | Loonwater Regional |
| Fond du Lac, WI | 56 | Loonwater Regional |
| Sheboygan, WI | 55 | Loonwater Regional |
| Escanaba, MI | 97 | Loonwater Regional |
| Sault Ste. Marie, MI | 224 | Loonwater Regional |

Davenport closes, but only by 6 mi, and only Loonwater reaches it. If a
later map or radius change drops it, the smallest real fix is a Quad Cities
(`davenport_ia_us`) terminal on Prairie Link or Loonwater, or a Des Moines
terminal on Prairie Link. The coverage test (§7) would catch the drop.

---

## 7. Coverage test (lands with the data)

`crates/ff-core/tests/it/data_world.rs` (or `models/carriers.rs` tests):

1. **National floor:** every lower-48 map city is hired into by at least
   one national (`tier == "national"`), and no national hires in AK, BC, or
   YT.
2. **Regional coverage:** every lower-48 city is hired into by at least one
   regional. The nationals-only list is empty, and the test pins it empty,
   so a map or carrier change that opens a gap fails loudly.
3. **Same country and radius:** every regional or local hire is within its
   `hiring_radius_mi` of a terminal in the same country.
4. **Alaska:** every AK city is offerable through Spruce Hen Line (and
   Anchorage, Wasilla, and Palmer through Knik Arm Cartage too); every
   BC/YT city is not offerable.
5. **Terminals:** every `terminal_city_key` is a world city (already
   validated) and no two carriers share a display name.
6. **Picker agreement:** every offerable city has at least one start option
   (already covered by the slice 2 app test; extended to the new carriers).
7. **Fallback:** for every offerable home city and every carrier hiring
   there, the fallback pick is never that carrier and never a carrier in
   another country; for AK homes it is never Great Lakes Training.

---

## 8. Implementation outline (after the cut)

1. `data/carriers.json`: the 20 new entries (16 regionals, Spruce Hen Line,
   3 locals). Pay and dispatch numbers per tier, reusing Prairie Link's
   regional shape and a local shape (higher `stop_pay`, strong
   `short_haul_bias`), tuned in review.
2. Tier `local` in `models/carriers.rs` (a non-national with
   `hiring_radius_mi = 50`; the regional code path already handles it).
3. One company start option per new carrier in
   `models/start_options.rs`, so the carrier-first picker lists them.
4. The fallback rule (§5), or at least the AK guard.
5. Flip the AK picker tests; keep BC/YT tests.
6. The §7 coverage test.
7. CHANGELOG bullet; ROADMAP rows checked off.

---

## 9. Future work (not this slice)

- **ALCAN through-freight** is a later long-haul lane program, not part of
  Spruce Hen Line: through moves only between AK and the lower 48, no
  domestic BC/YT moves (Canadian cabotage), and ACE/ACI eManifest filed at
  each border crossing.
- **TWIC for port drayage:** drayage into the LA/Long Beach marine
  terminals needs a TWIC card. Tracked as a ROADMAP row for when drayage
  loads are real.

---

## 10. Trademark screen

This is a **screen, not legal clearance.** It looks for names that match or
are confusingly close to a real motor carrier or a registered
transportation mark. A name is flagged when its distinctive word is shared
with a carrier whose name signals freight, trucking, transport, or
logistics, or with a carrier working the same lane area.

Sources, run 2026-09-26:

- **FMCSA SAFER company-name search**
  (`safer.fmcsa.dot.gov/keywordx.asp?searchstring=*TERM*`): wildcard search
  on the distinctive word or phrase, then a check of each match's name and
  location.
- **Web search:** "<word>" plus trucking, freight, transport, or carriers.
- **USPTO trademark search** (tmsearch.uspto.gov): not reachable from the
  screening machine (the search API answered HTTP 405), so no USPTO results
  are recorded. Run it before the data ships.

| Proposed name | Searched | Result | Outcome |
| --- | --- | --- | --- |
| Granite Coast Freight | SAFER "GRANITE"; web | GRANITE STATE HAULING (Rochester NH), same region | Flagged |
| Bayberry Coast Freight (candidate) | SAFER "BAYBERRY"; web | "The Bayberry," a registered carrier in Amagansett NY, in the lane area | Flagged |
| **Rockweed Coast Freight** | SAFER "ROCKWEED"; web | No SAFER records; web hits are seaweed harvesters | Clean — **replaces Granite Coast** |
| Allegheny Crossroads Freight | SAFER "ALLEGHENY"; web | ALLEGHENY LOGISTICS, ALLEGHENY HAULING (PA) | Flagged |
| **Kittatinny Crossroads Freight** | SAFER "KITTATINNY"; web | Only a canoe and campground outfit (Milford PA) | Clean — **replaces Allegheny** |
| Piedmont Ridge Transport | SAFER "PIEDMONT"; web | PIEDMONT CARRIERS LLC (Charlotte NC) | Flagged |
| **Catawba Ridge Transport** | SAFER "CATAWBA RIDGE"; web | No records | Clean — **replaces Piedmont Ridge** |
| Red Clay Regional | SAFER "RED CLAY"; web | RED CLAY FREIGHT, RED CLAY LOGISTICS GROUP (Macon GA), RED CLAY SHIPPING (GA) | Flagged |
| **Sweetgum Regional** | SAFER "SWEETGUM"; web | A contractor (NC) and a farm (AL); no freight names | Clean — **replaces Red Clay** |
| **Sunpine Freight Lines** | SAFER "SUNPINE"; web | No carriers; a lumber maker and a Swedish biofuel firm | Clean — kept |
| Bayou Gulf Carriers | SAFER "BAYOU"; web | Many BAYOU trucking firms in LA | Flagged |
| Cypress Knee Carriers (candidate) | SAFER "CYPRESS KNEE"; web | Cypress Knee Transport Inc (Dunnellon FL) | Flagged |
| Pirogue Gulf Carriers (candidate) | SAFER "PIROGUE" | PIROGUE LOGISTICS LLC (Shreveport LA) | Flagged |
| Spanish Moss / Canebrake (candidates) | SAFER | SPANISH MOSS TRANSPORTATION LLC (FL); CANEBRAKE FORESTRY (AL) | Flagged |
| **Marsh Hen Carriers** | SAFER "MARSH HEN"; web | No SAFER records; weak web hit: Marsh Hen Mill, a SC grits maker with one delivery van | Clean (weak hit noted) — **replaces Bayou Gulf** |
| **Lone Mesa Freight** | SAFER "LONE MESA"; web | No carriers; a publisher and a state park | Clean — kept |
| Delta River Lines | web | Confusable with Delta Air Lines, a registered transportation mark | Flagged |
| Muscadine River Lines (candidate) | SAFER "MUSCADINE"; web | Muscadine Timber LLC, a timber hauler in AL | Flagged |
| Loblolly / Pawpaw / Persimmon / Chinkapin (candidates) | SAFER; web | LOBLOLLY TRUCKING (AL); PAWPAW TRUCKING (TX); PERSIMMON CREEK TRANSPORT (GA); Chinkapin Trucking Inc (Klamath Falls OR) | Flagged |
| **Buttonbush River Lines** | SAFER "BUTTONBUSH"; web | No SAFER records; web hits are street addresses only | Clean — **replaces Delta River** |
| Riverbend Valley Freight | SAFER "RIVERBEND"; web | RIVERBEND TRANSPORT, RIVERBEND LOGISTICS (Hebron OH and others) | Flagged |
| **Hellbender Valley Freight** | SAFER "HELLBENDER"; web | Only a vinyl installer (Pittsburgh PA) | Clean — **replaces Riverbend** |
| North Woods Regional | SAFER "NORTH WOODS"; web | NORTH WOODS TRANSPORT LLC, NORTH WOODS TRUCKING LLC | Flagged |
| **Loonwater Regional** | SAFER "LOONWATER"; web | No records | Clean — **replaces North Woods** |
| Crosstimber Plains Freight | SAFER "CROSSTIMBER"; web | CROSSTIMBERS HAULING, CROSSTIMBERS HOT SHOT, others | Flagged |
| Scissortail / Caprock (candidates) | SAFER | Freight-named carriers under both | Flagged |
| **Sandplum Plains Freight** | SAFER "SANDPLUM"; web | No SAFER records; web hits are street names | Clean — **replaces Crosstimber** |
| Pronghorn Freight Lines | SAFER "PRONGHORN"; web | PRONGHORN FREIGHT BROKERS INC | Flagged |
| Yarrow / Larkspur / Rimrock (candidates) | SAFER | Freight-named carriers under each | Flagged |
| **Blue Grama Freight Lines** | SAFER "BLUE GRAMA"; web | No records | Clean — **replaces Pronghorn** |
| Wasatch Basin Transport | SAFER "WASATCH"; web | Many WASATCH freight firms in UT | Flagged |
| **Pinyon Basin Transport** | SAFER "PINYON"; web | Environmental and oilfield service firms (CO); no freight names | Clean — **replaces Wasatch** |
| Saguaro Sun Freight | SAFER "SAGUARO"; web | SAGUARO TRUCKING CO (Tucson), SAGUARO TRANSPORTATION | Flagged |
| Cholla Sun / Ocotillo (candidates) | SAFER; web | Cholla Managing Group and Cholla Ready Mix, registered carriers in AZ; OCOTILLO freight names | Flagged |
| **Brittlebush Sun Freight** | SAFER "BRITTLEBUSH"; web | No SAFER records; web hits are street addresses only | Clean — **replaces Saguaro Sun** |
| Tule Valley Freight | SAFER "TULE"; web | TULE RIVER TRANSPORT (Tulare CA) | Flagged |
| Manzanita (candidate) | SAFER | Freight-named carriers | Flagged |
| **Tarweed Valley Freight** | SAFER "TARWEED"; web | No records | Clean — **replaces Tule Valley** |
| Timberline Cascade Freight | SAFER "TIMBERLINE", "CASCADE"; web | TIMBERLINE FREIGHT SERVICES LLC (Springfield OR); several Cascade trucking firms in WA/OR | Flagged |
| **Salmonberry Freight Lines** | SAFER "SALMONBERRY"; web | No records ("Cascade" dropped) | Clean — **replaces Timberline Cascade** |
| Ptarmigan Line Freight | SAFER "PTARMIGAN"; web | PTARMIGAN TRANSPORT SERVICES LLC (Palmer AK), PTARMIGAN TRANSPORTATION LLC (North Pole AK) | Flagged |
| Fireweed Line Freight (candidate) | SAFER "FIREWEED"; web | Fireweed Fence (Kenai AK, registered carrier) plus fuel and services firms in AK | Weak hit in the same state; dropped |
| **Spruce Hen Line Freight** | SAFER "SPRUCE HEN"; web | No SAFER records; web hits are a tungsten prospect and an airstrip | Clean — **replaces Ptarmigan Line** |
| Lakefront Cartage | SAFER "LAKEFRONT"; web | LAKEFRONT TRUCK LINES (West Bend WI), several LAKEFRONT TRANSPORT | Flagged |
| **Bubbly Creek Cartage** | SAFER "BUBBLY CREEK"; web | No records | Clean — **replaces Lakefront** |
| **Basin Harbor Drayage** | SAFER "BASIN HARBOR"; web | No SAFER records; a Vermont resort, and an unrelated hauler on Basin Harbor Rd listed as not authorized | Clean — kept |
| **Knik Arm Cartage** | SAFER "KNIK ARM"; web | No SAFER records; web hits are geography and port context | Clean — kept |

Renames: Granite Coast → Rockweed Coast, Allegheny Crossroads → Kittatinny
Crossroads, Piedmont Ridge → Catawba Ridge, Red Clay → Sweetgum, Bayou Gulf
→ Marsh Hen, Delta River → Buttonbush River, Riverbend Valley → Hellbender
Valley, North Woods → Loonwater, Crosstimber Plains → Sandplum Plains,
Pronghorn → Blue Grama, Wasatch Basin → Pinyon Basin, Saguaro Sun →
Brittlebush Sun, Tule Valley → Tarweed Valley, Timberline Cascade →
Salmonberry, Ptarmigan Line → Spruce Hen Line, Lakefront → Bubbly Creek.

---

## 11. Resolved decisions

1. **Count:** sixteen new regionals plus Prairie Link, 17 lower-48
   regionals in all. No regional is cut.
2. **Wide terminal spans:** Pinyon Basin (SLC-Boise-Las Vegas, 517 mi),
   Lone Mesa (Dallas-McAllen 462), Blue Grama (Denver-Billings 454), and
   Salmonberry (Seattle-Medford 454) are all KEEP.
3. **Eastern Wisconsin, the UP, and the Quad Cities:** Loonwater Regional
   gets a Green Bay terminal; all six nationals-only cities close (§6).
4. **Termination fallback:** a fired driver never moves to Milwaukee. The
   fallback is a carrier hiring in the home city, never the firing carrier;
   Knik Arm Cartage is the second AK carrier; without the rule, an AK
   termination leaves the driver home and unassigned (§5).
5. **AK lane area:** inside AK only. ALCAN through-freight is future work
   (§9).
6. **Locals:** Chicago and LA are KEEP; TWIC for LA/Long Beach port drayage
   is a ROADMAP row.
7. **Regionals overlapping a national's home city** (Hellbender Valley
   reaching Chicago and Milwaukee): KEEP.
8. **Trademark screen:** done (§10); sixteen names replaced.

---

## 12. Open questions

1. **Loonwater span:** Bismarck-Green Bay is 636 air mi, the widest pair of
   any regional. Keep, or accept it like the four approved spans?
2. **Knik Arm Cartage run footprint:** only Wasilla and Palmer sit in its
   25-150 mi band on today's map. Accept as-is, or add Kenai, Seward, or
   Whittier to the AK map with the data?
3. **Unassigned driver state (§5):** how the hub reads a driver with no
   carrier (menu wording, what the dispatch board says) needs a design
   before the fallback rule lands.
4. **USPTO:** the federal trademark search was unreachable during the
   screen; run it on the final names before `data/carriers.json` lands.
