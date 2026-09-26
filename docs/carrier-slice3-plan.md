# Carrier slice 3 plan — regional, local, and Alaska carriers

Status: **plan only — no carrier data yet.** `data/carriers.json` is not
touched until this list passes a realism cut.

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
Sixteen new lower-48 regionals, one Alaska regional, two locals.

| # | Name | Key | Tier | Terminal city keys | Cities in footprint | Only regional for |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Granite Coast Freight | `granite_coast_freight` | regional | `boston_ma_us`, `hartford_ct_us`, `portland_me_us`, `albany_ny_us` | 40 | 5 |
| 2 | Allegheny Crossroads Freight | `allegheny_crossroads` | regional | `harrisburg_pa_us`, `baltimore_md_us`, `pittsburgh_pa_us`, `newark_nj_us` | 85 | 0 |
| 3 | Piedmont Ridge Transport | `piedmont_ridge` | regional | `charlotte_nc_us`, `greensboro_nc_us`, `richmond_va_us` | 82 | 7 |
| 4 | Red Clay Regional | `red_clay_regional` | regional | `atlanta_ga_us`, `birmingham_al_us`, `savannah_ga_us` | 82 | 0 |
| 5 | Sunpine Freight Lines | `sunpine_freight` | regional | `jacksonville_fl_us`, `orlando_fl_us`, `miami_fl_us` | 38 | 14 |
| 6 | Bayou Gulf Carriers | `bayou_gulf` | regional | `new_orleans_la_us`, `baton_rouge_la_us`, `mobile_al_us`, `jackson_ms_us` | 55 | 5 |
| 7 | Lone Mesa Freight | `lone_mesa_freight` | regional | `dallas_tx_us`, `houston_tx_us`, `san_antonio_tx_us`, `mcallen_tx_us` | 64 | 19 |
| 8 | Delta River Lines | `delta_river_lines` | regional | `memphis_tn_us`, `little_rock_ar_us`, `nashville_tn_us` | 94 | 1 |
| 9 | Riverbend Valley Freight | `riverbend_valley` | regional | `columbus_oh_us`, `cincinnati_oh_us`, `louisville_ky_us`, `indianapolis_in_us`, `detroit_mi_us` | 101 | 29 |
| 10 | North Woods Regional | `north_woods_regional` | regional | `minneapolis_mn_us`, `fargo_nd_us`, `bismarck_nd_us`, `duluth_mn_us` | 51 | 31 |
| 11 | Crosstimber Plains Freight | `crosstimber_plains` | regional | `oklahoma_city_ok_us`, `tulsa_ok_us`, `amarillo_tx_us`, `lubbock_tx_us` | 85 | 9 |
| 12 | Pronghorn Freight Lines | `pronghorn_freight` | regional | `denver_co_us`, `cheyenne_wy_us`, `billings_mt_us` | 50 | 29 |
| 13 | Wasatch Basin Transport | `wasatch_basin` | regional | `salt_lake_city_ut_us`, `boise_id_us`, `las_vegas_nv_us` | 66 | 22 |
| 14 | Saguaro Sun Freight | `saguaro_sun` | regional | `phoenix_az_us`, `tucson_az_us`, `albuquerque_nm_us`, `el_paso_tx_us` | 51 | 17 |
| 15 | Tule Valley Freight | `tule_valley` | regional | `los_angeles_ca_us`, `fresno_ca_us`, `sacramento_ca_us` | 53 | 20 |
| 16 | Timberline Cascade Freight | `timberline_cascade` | regional | `seattle_wa_us`, `portland_or_us`, `spokane_wa_us`, `medford_or_us` | 54 | 36 |
| AK | Ptarmigan Line Freight | `ptarmigan_line` | regional (AK) | `anchorage_ak_us`, `fairbanks_ak_us` | 8 (all AK) | 8 |
| L1 | Lakefront Cartage | `lakefront_cartage` | local | `chicago_il_us`, `gary_in_us`, `aurora_il_us` | 4 | — |
| L2 | Basin Harbor Drayage | `basin_harbor_drayage` | local | `los_angeles_ca_us`, `riverside_ca_us` | 6 | — |

Coverage with all sixteen plus Prairie Link: **619 of 625** lower-48 cities
have at least one regional (258 have exactly one, 241 two, 101 three, 19
four). Six are left with nationals only (§5).

Names are fictional and follow the existing style (place or landscape word
plus Freight / Lines / Regional / Transport). They were chosen to avoid
known carrier names (for example no "Old Dominion", "Southeastern",
"Central", "Estes", "Saia", "Averitt", "Keystone"); a trademark search is
still an open question (§8).

---

## 2. Regional carriers

### 1. Granite Coast Freight (`granite_coast_freight`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `boston_ma_us`, `hartford_ct_us`, `portland_me_us`, `albany_ny_us` (widest terminal pair 190 air mi).
- **Lane area:** New England and the upper Hudson: Boston, Hartford, Portland ME, and Albany terminals; lanes Maine to the NYC metro and west to the Hudson.
- **Hiring footprint:** 40 map cities; states NY 7, PA 7, NJ 5, MA 4, CT 4, NH 3, VT 3, ME 3, RI 2, DE 2.
- **Only regional for:** Bangor ME, Lewiston ME, Portland ME, Burlington VT, Montpelier VT.

### 2. Allegheny Crossroads Freight (`allegheny_crossroads`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `harrisburg_pa_us`, `baltimore_md_us`, `pittsburgh_pa_us`, `newark_nj_us` (widest terminal pair 306 air mi).
- **Lane area:** Mid-Atlantic: Harrisburg, Baltimore, Pittsburgh, and Newark terminals; lanes along I-76/I-78/I-81/I-95 between the NJ ports, the PA distribution belt, and the Chesapeake.
- **Hiring footprint:** 85 map cities; states VA 13, OH 12, PA 11, NY 9, WV 6, NJ 5, MA 4, CT 4, MD 4, KY 4, MI 3, NH 3, RI 2, DE 2, DC 1, NC 1, VT 1.
- **Only regional for:** none (every city here is also reached by another regional).

### 3. Piedmont Ridge Transport (`piedmont_ridge`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `charlotte_nc_us`, `greensboro_nc_us`, `richmond_va_us` (widest terminal pair 248 air mi).
- **Lane area:** Carolinas and Virginia: Charlotte, Greensboro, and Richmond terminals; lanes along I-85/I-40/I-95 from Richmond to upstate SC.
- **Hiring footprint:** 82 map cities; states VA 15, NC 14, GA 11, PA 7, SC 7, WV 6, KY 6, TN 5, MD 4, NJ 4, DE 2, DC 1.
- **Only regional for:** Durham NC, Greensboro NC, Greenville NC, Jacksonville NC, New Bern NC, Raleigh NC, Winston-Salem NC.

### 4. Red Clay Regional (`red_clay_regional`)

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

### 6. Bayou Gulf Carriers (`bayou_gulf`)

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

### 8. Delta River Lines (`delta_river_lines`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `memphis_tn_us`, `little_rock_ar_us`, `nashville_tn_us` (widest terminal pair 325 air mi).
- **Lane area:** Mid-South: Memphis, Little Rock, and Nashville terminals; lanes along I-40/I-55/I-24 around the Memphis rail and river hub.
- **Hiring footprint:** 94 map cities; states AR 14, TN 12, KY 12, MS 10, OK 9, MO 6, GA 6, AL 6, LA 5, IN 5, TX 3, IL 3, OH 1, NC 1, KS 1.
- **Only regional for:** Poplar Bluff MO.

### 9. Riverbend Valley Freight (`riverbend_valley`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `columbus_oh_us`, `cincinnati_oh_us`, `louisville_ky_us`, `indianapolis_in_us`, `detroit_mi_us` (widest terminal pair 316 air mi).
- **Lane area:** Ohio Valley and lower Great Lakes: Columbus, Cincinnati, Louisville, Indianapolis, and Detroit terminals; lanes along I-70/I-71/I-65/I-75 and into Chicagoland and lower Michigan.
- **Hiring footprint:** 101 map cities; states IN 15, KY 14, OH 13, IL 12, TN 11, MI 11, VA 6, WV 6, PA 4, MO 2, NY 2, WI 2, AL 1, GA 1, MD 1.
- **Only regional for:** Aurora IL, Bloomington IL, Champaign IL, Chicago IL, Decatur IL, Galesburg IL, Peoria IL, Rockford IL, Springfield IL, Anderson IN, Elkhart IN, Fort Wayne IN, Gary IN, Indianapolis IN, Kokomo IN, Lafayette IN, Muncie IN, Richmond IN, South Bend IN, Flint MI, Grand Rapids MI, Jackson MI, Kalamazoo MI, Lansing MI, Muskegon MI, Saginaw MI, Traverse City MI, Kenosha WI, Milwaukee WI.

### 10. North Woods Regional (`north_woods_regional`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `minneapolis_mn_us`, `fargo_nd_us`, `bismarck_nd_us`, `duluth_mn_us` (widest terminal pair 410 air mi).
- **Lane area:** Upper Midwest: Minneapolis, Fargo, Bismarck, and Duluth terminals; lanes along I-94/I-35/I-29 across MN, the Dakotas, and western WI.
- **Hiring footprint:** 51 map cities; states MN 12, IA 10, SD 8, ND 8, WI 7, MI 3, MT 3.
- **Only regional for:** Dubuque IA, Houghton MI, Iron Mountain MI, Marquette MI, Bemidji MN, Duluth MN, Grand Rapids MN, Hibbing MN, Minneapolis MN, Rochester MN, St. Cloud MN, Willmar MN, Winona MN, Bismarck ND, Devils Lake ND, Dickinson ND, Fargo ND, Grand Forks ND, Jamestown ND, Minot ND, Williston ND, Aberdeen SD, Pierre SD, Watertown SD, Chippewa Falls WI, Eau Claire WI, La Crosse WI, Madison WI, Oshkosh WI, Rice Lake WI, Wausau WI.

### 11. Crosstimber Plains Freight (`crosstimber_plains`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `oklahoma_city_ok_us`, `tulsa_ok_us`, `amarillo_tx_us`, `lubbock_tx_us` (widest terminal pair 377 air mi).
- **Lane area:** Southern Plains: Oklahoma City, Tulsa, Amarillo, and Lubbock terminals; lanes along I-40/I-44/I-35/I-27 and into the Permian edge.
- **Hiring footprint:** 85 map cities; states TX 30, OK 17, KS 12, AR 10, NM 9, MO 4, CO 3.
- **Only regional for:** Amarillo TX, Big Spring TX, Clarendon TX, Dumas TX, Lubbock TX, Midland TX, Pampa TX, Plainview TX, Stratford TX.

### 12. Pronghorn Freight Lines (`pronghorn_freight`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `denver_co_us`, `cheyenne_wy_us`, `billings_mt_us` (widest terminal pair 454 air mi).
- **Lane area:** Front Range and high plains: Denver, Cheyenne, and Billings terminals; lanes along I-25/I-80/I-90 from Colorado Springs to Montana.
- **Hiring footprint:** 50 map cities; states CO 18, MT 11, WY 10, NE 4, SD 3, ID 1, KS 1, NM 1, OK 1.
- **Only regional for:** Burlington CO, Colorado Springs CO, Denver CO, Edwards CO, Fort Collins CO, Glenwood Springs CO, Limon CO, Silverthorne CO, Billings MT, Bozeman MT, Glasgow MT, Great Falls MT, Havre MT, Helena MT, Shelby MT, North Platte NE, Ogallala NE, Scottsbluff NE, Sidney NE, Hot Springs SD, Buffalo WY, Casper WY, Cheyenne WY, Gillette WY, Laramie WY, Lusk WY, Rawlins WY, Sheridan WY, Wheatland WY.

### 13. Wasatch Basin Transport (`wasatch_basin`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `salt_lake_city_ut_us`, `boise_id_us`, `las_vegas_nv_us` (widest terminal pair 517 air mi).
- **Lane area:** Great Basin: Salt Lake City, Boise, and Las Vegas terminals; lanes along I-15/I-80/I-84 between the Wasatch Front, southern Idaho, and Las Vegas.
- **Hiring footprint:** 66 map cities; states CA 18, AZ 11, UT 10, NV 10, ID 6, OR 4, WA 2, MT 2, CO 2, WY 1.
- **Only regional for:** Boise ID, Pocatello ID, Twin Falls ID, Alamo NV, Battle Mountain NV, Elko NV, Ely NV, Eureka NV, Wells NV, West Wendover NV, Winnemucca NV, Ontario OR, Cedar City UT, Green River UT, Logan UT, Moab UT, Nephi UT, Ogden UT, Provo UT, Richfield UT, Saint George UT, Salt Lake City UT.

### 14. Saguaro Sun Freight (`saguaro_sun`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `phoenix_az_us`, `tucson_az_us`, `albuquerque_nm_us`, `el_paso_tx_us` (widest terminal pair 345 air mi).
- **Lane area:** Desert Southwest: Phoenix, Tucson, Albuquerque, and El Paso terminals; lanes along I-10/I-17/I-25/I-40 and the Nogales crossing.
- **Hiring footprint:** 51 map cities; states AZ 22, NM 14, CO 7, TX 5, CA 3.
- **Only regional for:** Casa Grande AZ, Douglas AZ, Globe AZ, Holbrook AZ, Nogales AZ, Payson AZ, Phoenix AZ, Show Low AZ, Sierra Vista AZ, Tucson AZ, Winslow AZ, Albuquerque NM, Farmington NM, Gallup NM, Las Cruces NM, Socorro NM, El Paso TX.

### 15. Tule Valley Freight (`tule_valley`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `los_angeles_ca_us`, `fresno_ca_us`, `sacramento_ca_us` (widest terminal pair 361 air mi).
- **Lane area:** California and Reno: Los Angeles, Fresno, and Sacramento terminals; lanes along I-5/CA-99/I-80 from the LA basin through the Central Valley to Reno.
- **Hiring footprint:** 53 map cities; states CA 43, NV 7, AZ 3.
- **Only regional for:** Fairfield CA, Fresno CA, Merced CA, Modesto CA, Oxnard CA, Sacramento CA, Salinas CA, San Diego CA, San Francisco CA, San Jose CA, San Luis Obispo CA, Santa Barbara CA, Santa Maria CA, Santa Rosa CA, Stockton CA, Austin NV, Carson City NV, Fallon NV, Fernley NV, Reno NV.

### 16. Timberline Cascade Freight (`timberline_cascade`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `seattle_wa_us`, `portland_or_us`, `spokane_wa_us`, `medford_or_us` (widest terminal pair 454 air mi).
- **Lane area:** Pacific Northwest: Seattle, Portland, Spokane, and Medford terminals; lanes along I-5/I-84/I-90 from the Canadian line to southern Oregon and the Idaho panhandle.
- **Hiring footprint:** 54 map cities; states OR 20, WA 14, CA 11, ID 5, MT 4.
- **Only regional for:** Crescent City CA, Coeur d'Alene ID, Kellogg ID, Sandpoint ID, Kalispell MT, Libby MT, Superior MT, Albany OR, Astoria OR, Bend OR, Coos Bay OR, Corvallis OR, Eugene OR, Grants Pass OR, Klamath Falls OR, McMinnville OR, Medford OR, Newberg OR, Newport OR, Portland OR, Roseburg OR, Salem OR, The Dalles OR, Woodburn OR, Bellingham WA, Blaine WA, Everett WA, Longview WA, Moses Lake WA, Olympia WA, Port Angeles WA, Seattle WA, Spokane WA, Tacoma WA, Wenatchee WA, Yakima WA.

---

## 3. Local carriers

### L1. Lakefront Cartage (`lakefront_cartage`)

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
- **Lane area:** LA/Long Beach port drayage to the Inland Empire DCs and
  out to 150 mi — 17 map cities in band, including San Diego, Bakersfield,
  Barstow, Oxnard, and Indio.

Other metros checked and not proposed: NYC/Newark (4 hire cities, 20 in
band), Dallas-Fort Worth (4 and 24), Houston (1 and 10). Either NYC or DFW
could replace one of the two if the cut prefers.

---

## 4. Alaska regional and the picker rule

### Ptarmigan Line Freight (`ptarmigan_line`)

- **Tier:** regional; `hiring_radius_mi = 250`, same country.
- **Terminals:** `anchorage_ak_us`, `fairbanks_ak_us`.
- **Hiring footprint:** all 8 AK map cities — Anchorage 0, Fairbanks 0,
  Wasilla 29, Palmer 37, Nenana 45, Healy 77, Glennallen 157, Tok 176 air
  mi from the nearer terminal.
- **Lane area:** the Parks, Glenn, Tok Cutoff, and Richardson corridors
  between Anchorage, Mat-Su, Fairbanks, and Tok.

### How AK homes interact with the picker

- A home base is offerable when some carrier hires there
  (`is_offerable_home_city`). Nationals hire only in the lower 48, so today
  no AK city qualifies. With Ptarmigan Line in `data/carriers.json`, all
  eight AK cities become offerable, listing Ptarmigan Line only.
- **BC and YT stay blocked with no code change:** regionals hire in the
  same country only, and the nearest AK terminal is 490 air mi from
  Whitehorse and 688+ from every other BC/YT city. No other carrier hires
  there.
- No lower-48 carrier reaches AK (nationals stop at the lower 48, and no
  lower-48 regional terminal is within 250 mi), and Ptarmigan Line reaches
  no lower-48 city, so the two carrier lists never mix.
- Tests that pin Healy and Anchorage as not offerable flip to offerable;
  Whitehorse and Surrey stay excluded.

---

## 5. Cities left with nationals only

| City | Nearest regional terminal (air mi) |
| --- | --- |
| Davenport, IA | Indianapolis (Riverbend) 261, Kansas City (Prairie Link) 269 |
| Green Bay, WI | Duluth (North Woods) 252 |
| Fond du Lac, WI | Minneapolis (North Woods) 252 |
| Sheboygan, WI | Detroit (Riverbend) 255 |
| Escanaba, MI | Duluth (North Woods) 251 |
| Sault Ste. Marie, MI | Detroit (Riverbend) 295 |

Five of the six miss by under 12 mi. Eastern Wisconsin sits under Great
Lakes Training's Milwaukee terminal, so nationals-only there is defensible.
Adding a Green Bay terminal to North Woods would close all six (Davenport
244, Sault Ste. Marie 224, the rest under 100 mi) — open question.

---

## 6. Bayou Gulf Carriers (`bayou_gulf`)

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

### 8. Delta River Lines (`delta_river_lines`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `memphis_tn_us`, `little_rock_ar_us`, `nashville_tn_us` (widest terminal pair 325 air mi).
- **Lane area:** Mid-South: Memphis, Little Rock, and Nashville terminals; lanes along I-40/I-55/I-24 around the Memphis rail and river hub.
- **Hiring footprint:** 94 map cities; states AR 14, TN 12, KY 12, MS 10, OK 9, MO 6, GA 6, AL 6, LA 5, IN 5, TX 3, IL 3, OH 1, NC 1, KS 1.
- **Only regional for:** Poplar Bluff MO.

### 9. Riverbend Valley Freight (`riverbend_valley`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `columbus_oh_us`, `cincinnati_oh_us`, `louisville_ky_us`, `indianapolis_in_us`, `detroit_mi_us` (widest terminal pair 316 air mi).
- **Lane area:** Ohio Valley and lower Great Lakes: Columbus, Cincinnati, Louisville, Indianapolis, and Detroit terminals; lanes along I-70/I-71/I-65/I-75 and into Chicagoland and lower Michigan.
- **Hiring footprint:** 101 map cities; states IN 15, KY 14, OH 13, IL 12, TN 11, MI 11, VA 6, WV 6, PA 4, MO 2, NY 2, WI 2, AL 1, GA 1, MD 1.
- **Only regional for:** Aurora IL, Bloomington IL, Champaign IL, Chicago IL, Decatur IL, Galesburg IL, Peoria IL, Rockford IL, Springfield IL, Anderson IN, Elkhart IN, Fort Wayne IN, Gary IN, Indianapolis IN, Kokomo IN, Lafayette IN, Muncie IN, Richmond IN, South Bend IN, Flint MI, Grand Rapids MI, Jackson MI, Kalamazoo MI, Lansing MI, Muskegon MI, Saginaw MI, Traverse City MI, Kenosha WI, Milwaukee WI.

### 10. North Woods Regional (`north_woods_regional`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `minneapolis_mn_us`, `fargo_nd_us`, `bismarck_nd_us`, `duluth_mn_us` (widest terminal pair 410 air mi).
- **Lane area:** Upper Midwest: Minneapolis, Fargo, Bismarck, and Duluth terminals; lanes along I-94/I-35/I-29 across MN, the Dakotas, and western WI.
- **Hiring footprint:** 51 map cities; states MN 12, IA 10, SD 8, ND 8, WI 7, MI 3, MT 3.
- **Only regional for:** Dubuque IA, Houghton MI, Iron Mountain MI, Marquette MI, Bemidji MN, Duluth MN, Grand Rapids MN, Hibbing MN, Minneapolis MN, Rochester MN, St. Cloud MN, Willmar MN, Winona MN, Bismarck ND, Devils Lake ND, Dickinson ND, Fargo ND, Grand Forks ND, Jamestown ND, Minot ND, Williston ND, Aberdeen SD, Pierre SD, Watertown SD, Chippewa Falls WI, Eau Claire WI, La Crosse WI, Madison WI, Oshkosh WI, Rice Lake WI, Wausau WI.

### 11. Crosstimber Plains Freight (`crosstimber_plains`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `oklahoma_city_ok_us`, `tulsa_ok_us`, `amarillo_tx_us`, `lubbock_tx_us` (widest terminal pair 377 air mi).
- **Lane area:** Southern Plains: Oklahoma City, Tulsa, Amarillo, and Lubbock terminals; lanes along I-40/I-44/I-35/I-27 and into the Permian edge.
- **Hiring footprint:** 85 map cities; states TX 30, OK 17, KS 12, AR 10, NM 9, MO 4, CO 3.
- **Only regional for:** Amarillo TX, Big Spring TX, Clarendon TX, Dumas TX, Lubbock TX, Midland TX, Pampa TX, Plainview TX, Stratford TX.

### 12. Pronghorn Freight Lines (`pronghorn_freight`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `denver_co_us`, `cheyenne_wy_us`, `billings_mt_us` (widest terminal pair 454 air mi).
- **Lane area:** Front Range and high plains: Denver, Cheyenne, and Billings terminals; lanes along I-25/I-80/I-90 from Colorado Springs to Montana.
- **Hiring footprint:** 50 map cities; states CO 18, MT 11, WY 10, NE 4, SD 3, ID 1, KS 1, NM 1, OK 1.
- **Only regional for:** Burlington CO, Colorado Springs CO, Denver CO, Edwards CO, Fort Collins CO, Glenwood Springs CO, Limon CO, Silverthorne CO, Billings MT, Bozeman MT, Glasgow MT, Great Falls MT, Havre MT, Helena MT, Shelby MT, North Platte NE, Ogallala NE, Scottsbluff NE, Sidney NE, Hot Springs SD, Buffalo WY, Casper WY, Cheyenne WY, Gillette WY, Laramie WY, Lusk WY, Rawlins WY, Sheridan WY, Wheatland WY.

### 13. Wasatch Basin Transport (`wasatch_basin`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `salt_lake_city_ut_us`, `boise_id_us`, `las_vegas_nv_us` (widest terminal pair 517 air mi).
- **Lane area:** Great Basin: Salt Lake City, Boise, and Las Vegas terminals; lanes along I-15/I-80/I-84 between the Wasatch Front, southern Idaho, and Las Vegas.
- **Hiring footprint:** 66 map cities; states CA 18, AZ 11, UT 10, NV 10, ID 6, OR 4, WA 2, MT 2, CO 2, WY 1.
- **Only regional for:** Boise ID, Pocatello ID, Twin Falls ID, Alamo NV, Battle Mountain NV, Elko NV, Ely NV, Eureka NV, Wells NV, West Wendover NV, Winnemucca NV, Ontario OR, Cedar City UT, Green River UT, Logan UT, Moab UT, Nephi UT, Ogden UT, Provo UT, Richfield UT, Saint George UT, Salt Lake City UT.

### 14. Saguaro Sun Freight (`saguaro_sun`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `phoenix_az_us`, `tucson_az_us`, `albuquerque_nm_us`, `el_paso_tx_us` (widest terminal pair 345 air mi).
- **Lane area:** Desert Southwest: Phoenix, Tucson, Albuquerque, and El Paso terminals; lanes along I-10/I-17/I-25/I-40 and the Nogales crossing.
- **Hiring footprint:** 51 map cities; states AZ 22, NM 14, CO 7, TX 5, CA 3.
- **Only regional for:** Casa Grande AZ, Douglas AZ, Globe AZ, Holbrook AZ, Nogales AZ, Payson AZ, Phoenix AZ, Show Low AZ, Sierra Vista AZ, Tucson AZ, Winslow AZ, Albuquerque NM, Farmington NM, Gallup NM, Las Cruces NM, Socorro NM, El Paso TX.

### 15. Tule Valley Freight (`tule_valley`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `los_angeles_ca_us`, `fresno_ca_us`, `sacramento_ca_us` (widest terminal pair 361 air mi).
- **Lane area:** California and Reno: Los Angeles, Fresno, and Sacramento terminals; lanes along I-5/CA-99/I-80 from the LA basin through the Central Valley to Reno.
- **Hiring footprint:** 53 map cities; states CA 43, NV 7, AZ 3.
- **Only regional for:** Fairfield CA, Fresno CA, Merced CA, Modesto CA, Oxnard CA, Sacramento CA, Salinas CA, San Diego CA, San Francisco CA, San Jose CA, San Luis Obispo CA, Santa Barbara CA, Santa Maria CA, Santa Rosa CA, Stockton CA, Austin NV, Carson City NV, Fallon NV, Fernley NV, Reno NV.

### 16. Timberline Cascade Freight (`timberline_cascade`)

- **Tier:** regional; hires within 250 air mi of any terminal, same country; runs 150-600 mi.
- **Terminals:** `seattle_wa_us`, `portland_or_us`, `spokane_wa_us`, `medford_or_us` (widest terminal pair 454 air mi).
- **Lane area:** Pacific Northwest: Seattle, Portland, Spokane, and Medford terminals; lanes along I-5/I-84/I-90 from the Canadian line to southern Oregon and the Idaho panhandle.
- **Hiring footprint:** 54 map cities; states OR 20, WA 14, CA 11, ID 5, MT 4.
- **Only regional for:** Crescent City CA, Coeur d'Alene ID, Kellogg ID, Sandpoint ID, Kalispell MT, Libby MT, Superior MT, Albany OR, Astoria OR, Bend OR, Coos Bay OR, Corvallis OR, Eugene OR, Grants Pass OR, Klamath Falls OR, McMinnville OR, Medford OR, Newberg OR, Newport OR, Portland OR, Roseburg OR, Salem OR, The Dalles OR, Woodburn OR, Bellingham WA, Blaine WA, Everett WA, Longview WA, Moses Lake WA, Olympia WA, Port Angeles WA, Seattle WA, Spokane WA, Tacoma WA, Wenatchee WA, Yakima WA.

---

## 3. Local carriers

### L1. Lakefront Cartage (`lakefront_cartage`)

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
- **Lane area:** LA/Long Beach port drayage to the Inland Empire DCs and
  out to 150 mi — 17 map cities in band, including San Diego, Bakersfield,
  Barstow, Oxnard, and Indio.

Other metros checked and not proposed: NYC/Newark (4 hire cities, 20 in
band), Dallas-Fort Worth (4 and 24), Houston (1 and 10). Either NYC or DFW
could replace one of the two if the cut prefers.

---

## 4. Alaska regional and the picker rule

### Ptarmigan Line Freight (`ptarmigan_line`)

- **Tier:** regional; `hiring_radius_mi = 250`, same country.
- **Terminals:** `anchorage_ak_us`, `fairbanks_ak_us`.
- **Hiring footprint:** all 8 AK map cities — Anchorage 0, Fairbanks 0,
  Wasilla 29, Palmer 37, Nenana 45, Healy 77, Glennallen 157, Tok 176 air
  mi from the nearer terminal.
- **Lane area:** the Parks, Glenn, Tok Cutoff, and Richardson corridors
  between Anchorage, Mat-Su, Fairbanks, and Tok.

### How AK homes interact with the picker

- A home base is offerable when some carrier hires there
  (`is_offerable_home_city`). Nationals hire only in the lower 48, so today
  no AK city qualifies. With Ptarmigan Line in `data/carriers.json`, all
  eight AK cities become offerable, listing Ptarmigan Line only.
- **BC and YT stay blocked with no code change:** regionals hire in the
  same country only, and the nearest AK terminal is 490 air mi from
  Whitehorse and 688+ from every other BC/YT city. No other carrier hires
  there.
- No lower-48 carrier reaches AK (nationals stop at the lower 48, and no
  lower-48 regional terminal is within 250 mi), and Ptarmigan Line reaches
  no lower-48 city, so the two carrier lists never mix.
- Tests that pin Healy and Anchorage as not offerable flip to offerable;
  Whitehorse and Surrey stay excluded.

---

## 5. Cities left with nationals only

| City | Nearest regional terminal |
| --- | --- |
| Davenport, IA | Omaha (Prairie Link) / Indianapolis (Riverbend), just over 250 mi |
| Green Bay, WI | Duluth (North Woods) / Detroit (Riverbend), over 250 mi |
| Fond du Lac, WI | as Green Bay |
| Sheboygan, WI | as Green Bay |
| Escanaba, MI | Duluth, over 250 mi |
| Sault Ste. Marie, MI | Detroit / Duluth, over 250 mi |

Eastern Wisconsin sits under Great Lakes Training's Milwaukee terminal, so
nationals-only there is defensible. Adding a Green Bay terminal to North
Woods would close five of the six (open question).

---

## 6. Coverage test (lands with the data)

`crates/ff-core/tests/it/data_world.rs` (or `models/carriers.rs` tests):

1. **National floor:** every lower-48 map city is hired into by at least
   one national (`tier == "national"`), and no national hires in AK, BC, or
   YT.
2. **Regional coverage:** every lower-48 city not on a pinned
   nationals-only list (§5) is hired into by at least one regional. The
   pinned list is exact, so a map or carrier change that grows or shrinks
   it fails loudly.
3. **Same country and radius:** every regional/local hire is within its
   `hiring_radius_mi` of a terminal in the same country.
4. **Alaska:** every AK city is offerable through the AK regional only;
   every BC/YT city is not offerable.
5. **Terminals:** every `terminal_city_key` is a world city (already
   validated) and no two carriers share a display name.
6. **Picker agreement:** every offerable city has at least one start option
   (already covered by the slice 2 app test; extended to the new carriers).

---

## 7. Implementation outline (after the cut)

1. `data/carriers.json`: the 19 new entries. Pay and dispatch numbers per
   tier, reusing Prairie Link's regional shape and a local shape (higher
   `stop_pay`, strong `short_haul_bias`), tuned in review.
2. Tier `local` in `models/carriers.rs` (a non-national with
   `hiring_radius_mi = 50`; the regional code path already handles it).
3. One company start option per new carrier in
   `models/start_options.rs`, so the carrier-first picker lists them.
4. Flip the AK picker tests; keep BC/YT tests.
5. The §6 coverage test.
6. CHANGELOG bullet; ROADMAP rows checked off.

---

## 8. Open questions

1. **Count:** "16 regionals" read as sixteen new ones plus Prairie Link
   (17 lower-48 regionals). If Prairie Link is one of the sixteen, cut one:
   Allegheny Crossroads and Red Clay Regional are the only two with no
   city unique to them; merging Allegheny's Harrisburg and Baltimore
   terminals into Granite Coast or Piedmont is the least disruptive cut.
2. **Terminal spread:** Wasatch Basin (SLC-Boise-Las Vegas, widest pair
   517 mi), Lone Mesa (Dallas-McAllen 462), Pronghorn (Denver-Billings 454),
   and Timberline (Seattle-Medford 454) span more than a typical regional.
   Keep, or split and drop another?
3. **Eastern Wisconsin / UP / Quad Cities:** add a Green Bay terminal to
   North Woods (closes all six), or leave the six nationals-only cities (§5)?
4. **AK solvency fallback:** a terminated AK driver moves to Great Lakes
   Training, whose nearest terminal is Milwaukee. Should AK get its own
   fallback, or should termination keep an AK driver on Ptarmigan Line with
   a penalty?
5. **AK lane area:** does Ptarmigan Line haul only inside AK, or also the
   ALCAN through-freight lanes to the lower 48 (Canada cabotage forbids
   domestic moves inside BC/YT)?
6. **Locals:** Chicago and LA, or swap one for NYC/Newark or DFW?
7. **Trademarks:** the names were checked against well-known carriers only;
   run a trademark search before the data lands.
8. **Overlap with nationals' home cities:** Riverbend reaches Chicago and
   Milwaukee (Northstar and Great Lakes Training home terminals). Fine for
   realism, or keep regional footprints off national home cities?
