# STATE_TRUCK_MAX_MPH audit — all 50 states

Audit date: **2026-07-19**. Scope: `STATE_TRUCK_MAX_MPH` in
`src/freight_fate/sim/trip_models.py`.

Proposal only. No code or data was changed.

---

## 1. Summary

The existing 10-entry table has **four entries fully correct, two correct but
scope-limited, four wrong, and one live split missing entirely.**

| Verdict | Count | States |
|---|---|---|
| Correct as written | 4 | California, Indiana, Michigan, Washington |
| Correct number, but scope narrower than the flat cap implies — a *second*, much lower limit applies off that road class | 2 | Arkansas (50 elsewhere), Montana (65 elsewhere) |
| **Wrong — law repealed, entry now stale** | 1 | **Idaho** |
| **Wrong — no truck split exists at all** | 2 | **Nevada, North Dakota** |
| **Wrong — number too permissive** | 1 | **Oregon** (65 → 55) |
| **Missing — real split, silently absent** | 1 | **Arizona** (65) |
| Real split, but structurally unrepresentable | 2 | Illinois, Virginia |

Headline items, in order of how badly they misinform a driver:

1. **Idaho repealed its split 18 days ago.** Idaho Code 49-654(3), as amended by
   H664 (2026 ch. 108), now states affirmatively that 5+ axle heavy vehicles get
   *the same* limits as light vehicles. Signed **2026-03-23**, effective
   **2026-07-01** — 18 days ago. The game currently holds trucks to 70 on Idaho
   interstates posted 75–80 and says "Idaho holds trucks to this." That sentence
   is now false. (The entry was never quite right even before the repeal: the old
   Idaho rule was **posted-minus-10** — 65 on a 75 interstate, 70 on an 80
   segment — not a flat 70.)
2. **Arizona is missing.** A.R.S. 28-709 caps vehicles over 26,000 lb declared
   gross weight at 65 mph statewide, while ADOT posts 75 on rural interstates.
   The game currently serves the car number, telling a driver they may legally
   run 75 on I-10/I-40 where the statutory cap is 65. This is the failure mode
   the brief called the worst one, and it is live on 33 Arizona legs.
3. **Oregon is 55, not 65.** ORS 811.111(1)(b) sets **55 mph on any highway**
   for vehicles over 10,000 lb GVWR as the *default*; 60 and 65 are named-corridor
   exceptions in eastern Oregon. The current 65 is the exception treated as the
   rule, and it over-speeds trucks by 10 mph on I-5 — Oregon's busiest freight
   corridor. See §4 for the complication this creates.
4. **Nevada and North Dakota have no truck split at all.** Both were sourced from
   the aggregator's *general* limit column. Worse, both states' real general
   maximum is **80**, so the entries are wrong twice over: they invent a split
   that does not exist, and they cap 5 mph below a limit that binds nobody.

Method note: **this session's web-search budget (200 calls) was exhausted**
during the sweep. Later verification was done by direct URL fetch. Two states
(Nevada's corridor postings, Arkansas's non-controlled-access provision) carry
residual uncertainty flagged in §4 rather than being filled in.

---

## 2. Per-state findings

### 2a. States with a truck/car split (confirmed)

| State | Truck max | General | Scope | Source | Conf. |
|---|---|---|---|---|---|
| **Arizona** | **65** | 75 posted (65 statutory, director-raised) | **Statewide, any highway**; >26,000 lb declared GW; ADOT may post higher after engineering study | [A.R.S. 28-709](https://www.azleg.gov/ars/28/00709.htm); general limit [A.R.S. 28-702.04](https://www.azleg.gov/ars/28/00702-04.htm) | HIGH |
| Arkansas | 70 (**50 elsewhere** — see §4b) | 75 | **Rural 4-lane divided controlled-access only**; CMV ≥26,001 lb GVWR in commerce. § 27-51-201(c)(2) separately caps 1.5-ton-capacity trucks at 50 on all other roads | [Ark. Code 27-51-201](https://codes.findlaw.com/ar/title-27-transportation/ar-code-sect-27-51-201.html), validated word-for-word against [Act 784 of 2019](https://www.arkleg.state.ar.us/Home/FTPDocument?path=%2FACTS%2F2019R%2FPublic%2FACT784.pdf) | HIGH |
| California | 55 | 65–70 | **Statewide, all highways**; 3+ axles *or* any vehicle towing | [CVC 22406](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=VEH&sectionNum=22406) | HIGH (primary) |
| **Illinois** | **60 interstate / 55 other** | 70 / 65 / 55 | **Six named counties only**: Cook, DuPage, Kane, Lake, McHenry, Will. ≥8,001 lb second-division. NOT statewide | [625 ILCS 5/11-601(e)](https://www.ilga.gov/documents/legislation/ilcs/documents/062500050K11-601.htm) | HIGH — but see §4 |
| Indiana | 65 | 70 | **Rural interstates + Toll Road only**; declared GVW >26,000 lb; buses excluded | [IC 9-21-5-2(a)(4)](https://codes.findlaw.com/in/title-9-motor-vehicles/in-code-sect-9-21-5-2.html) | HIGH |
| Michigan | 65 | 70 (75 on 614 posted mi) | **Statewide**, limited-access freeway + state trunk line, only where posted >65; GVW ≥10,000 lb or any truck-tractor | [MCL 257.627(4)](https://www.legislature.mi.gov/documents/mcl/pdf/mcl-257-627.pdf); 2016 PA 445 eff. 2017-01-05 | HIGH |
| Montana | **70 interstate / 65 other** | 80 rural interstate; 75 day / 70 night 4-lane; 70 day / 65 night other | >1 ton manufacturer's rated capacity. **No day/night split for trucks** (cars have one) | [MCA 61-8-312](https://mca.legmt.gov/bills/mca/title_0610/chapter_0080/part_0030/section_0120/0610-0080-0030-0120.html); general [MCA 61-8-303](https://mca.legmt.gov/bills/mca/title_0610/chapter_0080/part_0030/section_0030/0610-0080-0030-0030.html) | HIGH |
| **Oregon** | **55 default** (60/65 named corridors) | 65–70 | **Statewide default on any highway**; >10,000 lb GVWR. 65 only on I-84 E of The Dalles, I-82, US-95; 60 on US-20 Bend–Ontario, US-97/197, OR-31, OR-78, US-395, OR-205, US-26 | [ORS 811.111](https://oregon.public.law/statutes/ors_811.111) | HIGH |
| Washington | 60 | 70–75 | **Statewide**; >10,000 lb GVW *or* **any vehicle in combination (no weight floor)**, except auto stages. A statutory ceiling on the secretary's own increase power, not just a posted value | [RCW 46.61.410](https://app.leg.wa.gov/rcw/default.aspx?cite=46.61.410); base [RCW 46.61.400](https://app.leg.wa.gov/rcw/default.aspx?cite=46.61.400) | HIGH (primary) |
| **Virginia** | **45** | 55 | **Secondary/"all other highways" only** — NOT interstates, limited-access, 4+ lane, or state primaries. Trucks match cars at 65/70 on interstates | [Va. Code 46.2-870](https://law.lis.virginia.gov/vacode/title46.2/chapter8/section46.2-870/) | HIGH — but see §4 |
| West Virginia | 40 (dead letter) | 55 / 70 posted | "Open country highway", >8,000 lb GVW. **Unmodernized 1930s text**; WV posts 70 for all on I-64/77/79 | [W.Va. Code 17C-6-4](https://code.wvlegislature.gov/17C-6-4/) | Text HIGH, applicability LOW |

### 2b. States with NO truck split — checked, not assumed

All verified against statutory text unless noted.

| State | General max | Source |
|---|---|---|
| Alabama | 70 | § 32-5A-171. The 55 in (5) is **cargo**-keyed (explosives/flammables/hazwaste), not axle-keyed |
| Alaska | 55 statutory / 65 posted | 13 AAC 02.275 (regulation, not statute) |
| Colorado | 75 | C.R.S. 42-4-1101. (Oddity: 45 mph for single-rear-axle trash haulers >20,000 lb) |
| Connecticut | 65 | C.G.S. 14-219 — thresholds identical by class; "truck" appears only in penalties |
| Delaware | 65 | 21 Del. C. 4169 — no truck language in the subchapter |
| Florida | 70 | Confirmed no truck differential |
| Georgia | 70 | Aggregator-corroborated, MED |
| Hawaii | 60 | HRS ch. 291C — limits set by county/director, no truck class |
| **Idaho** | **75–80, trucks included** | **[Idaho Code 49-654(3)](https://legislature.idaho.gov/statutesrules/idstat/Title49/T49CH6/SECT49-654/) — H664, 2026 ch. 108, eff. 2026-07-01** |
| Iowa | 70 | § 321.285(5)(a) "for all vehicular traffic" |
| Kansas | 75 (posted-corridor) | K.S.A. 8-1558 — only school buses differentiated |
| Kentucky | 65 / 70 parkways | Named-parkway lookup required |
| Louisiana | 70 | R.S. 32:61; truck provision **R.S. 32:62 repealed by Acts 2010 No. 81 §2** |
| Maine | 75 on I-95 Old Town–Houlton | 29-A M.R.S. 2073 — applies to trucks too |
| Maryland | 70 | Transp. 21-801.1, vehicle-neutral |
| Massachusetts | 65 | MGL c.90 §17 — only school buses at 40 |
| Minnesota | 70 | § 169.14 subd. 2(a) |
| Mississippi | 65 / 70 posted | § 63-3-505 truck rule is **weather**-conditional (45 in poor visibility), not a standing limit |
| Missouri | 70 | RSMo 304.010(2), uniform "no vehicle" |
| Nebraska | 75 | § 60-6,186 — words truck/combination/towing do not appear |
| **Nevada** | **80** | **[NRS 484B.600(1)(e)](https://nevada.public.law/statutes/nrs_484b.600); [NRS 484B.613](https://nevada.public.law/statutes/nrs_484b.613) permits NDOT to post truck limits but imposes none** |
| New Hampshire | 70 (I-93 MM45→VT) | RSA 265:66 carve-out is *house* trailers at 45 |
| New Jersey | 65 | N.J.S.A. 39:4-98.1 enabling statute **dormant** — N.J.A.C. 16:28 deleted 1998-12-21 |
| New Mexico | 75 | NMSA 66-7-301. SB 226 (2025) truck-65 bill **DIED** — see §4 |
| New York | 65 | **[VTL 1180-a](https://www.nysenate.gov/legislation/laws/VAT/1180-A) forbids any limit "not uniformly applicable to all types of motor vehicles"** |
| **North Dakota** | **80** (raised 75 → 80 by **HB 1298, 2025**, eff. **2025-08-01**) | **[NDCC 39-09-02](https://ndlegis.gov/cencode/t39c09.pdf) — pure road-class table, every tier reads "the driver of a vehicle"; no truck or weight differential anywhere in ch. 39-09** |
| Ohio | 70 | [ORC 4511.21(B)(14)](https://codes.ohio.gov/ohio-revised-code/section-4511.21) — zero hits for truck/axle/tractor/GVW |
| Oklahoma | 75 / 80 turnpike | 47 O.S. 11-801(D) *authorizes* OTA truck limits; unexercised |
| Pennsylvania | 70 | 75 Pa.C.S. 3362(a)(1.1) "70 miles per hour **for all vehicles**" |
| Rhode Island | 65 | Ch. 31-14 — only motor-driven cycles and solid-tire vehicles |
| South Carolina | 70 | No truck differential (manufactured-home transport is posted-minus-10) |
| South Dakota | 80 | SDCL 32-25-4 — but see §4 |
| Tennessee | 70 | § 55-8-152 — "truck" definition vestigial, same 70 applies |
| **Texas** | **70 statutory / 75–85 posted** | **[Transp. Code 545.352](https://codes.findlaw.com/tx/transportation-code/transp-sect-545-352.html) — truck limit gone; night limit gone (545.352(e), 2011: "same speed limit for daytime and nighttime"); trucks NOT excluded from 75/80/85 corridors** |
| Utah | 75 / 80 | 41-6a-601/602 — no truck cap in Part 6 |
| Vermont | 65 | 23 V.S.A. 1083 — carve-outs are solid-tire/weight-exempt trailers |
| Wisconsin | 70 | § 346.57(4) |
| Wyoming | 75 / 80 | W.S. 31-5-301 — no truck differential |

---

## 3. Proposed replacement dict

Removes 3 entries, corrects 1, adds 1. Illinois and Virginia are deliberately
**not** included — see §4.

```python
# States whose statute holds heavy trucks below the general posted limit.
# Each entry is the statutory maximum, applied as a cap on the baked OSM
# posting; where the state's split is road-class-scoped the comment says so,
# because the flat cap cannot express it (see the audit notes in this file's
# "needs a human decision" section).
# All entries verified against statute text, accessed 2026-07-19.
STATE_TRUCK_MAX_MPH: dict[str, float] = {
    # A.R.S. 28-709: >26,000 lb declared GW, statewide. General limit is 75 on
    # rural interstates (28-702.04, director-raised from a statutory 65).
    "Arizona": 65.0,
    # Ark. Code 27-51-201(b): CMV >=26,001 lb GVWR. Applies only on rural
    # divided controlled-access highways; trucks match cars elsewhere.
    "Arkansas": 70.0,
    # CVC 22406: three or more axles, or any vehicle towing. Statewide, all
    # highways -- the widest split in the country.
    "California": 55.0,
    # IC 9-21-5-2(a)(4): declared GVW >26,000 lb, buses excluded. Rural
    # interstates and the Toll Road only.
    "Indiana": 65.0,
    # MCL 257.627(4): GVW >=10,000 lb or any truck-tractor. Freeways and state
    # trunk lines, engaging only where the posting exceeds 65.
    "Michigan": 65.0,
    # MCA 61-8-312: >1 ton rated capacity. 70 on interstates, 65 on all other
    # public highways -- this entry serves the interstate number.
    "Montana": 70.0,
    # ORS 811.111(1)(b): >10,000 lb GVWR, 55 on ANY highway by default. The 60
    # and 65 figures are named-corridor exceptions in eastern Oregon, not the
    # rule. I-5 is 55.
    "Oregon": 55.0,
    # RCW 46.61.410: >10,000 lb GVW and all combinations, statewide, while the
    # general limit may be raised to 75.
    "Washington": 60.0,
}
```

**Removed, with reason:**

- `"Idaho": 70.0` — **repealed.** Idaho Code 49-654(3) as amended by H664
  (2026 ch. 108) now says 5+ axle heavy vehicles get the same limits as light
  vehicles. Effective 2026-07-01.
- `"Nevada": 75.0` — **no split has ever existed.** NRS 484B.600 caps everyone
  at 80; NRS 484B.613 lets NDOT *post* truck limits but imposes none.
- `"North Dakota": 75.0` — **no split.** NDCC 39-09-02 has no truck or weight
  differential; the interstate maximum is 80 for all.

---

## 4. Needs a human decision

### 4a. Oregon 55 will pull down three corridors that are legally 65

This is the one change that could make the map *worse* somewhere while making
it right nearly everywhere. `_truck_capped_speed_limit` takes
`min(posted, cap)`, so a flat Oregon 55 will cap **I-84 east of The Dalles,
I-82, and US-95 at 55 when the statute gives trucks 65 there** — plus seven
corridors that are legally 60. Oregon has 35 legs.

Three options, no clearly free one:

1. Ship 55 and accept the eastern-Oregon error. Correct on I-5 (the high-traffic
   case), wrong by 10 on I-84 east. Trade a widespread 10-mph *over*-speed for a
   narrow 10-mph *under*-speed.
2. Ship 55 and verify those corridors carry `maxspeed:hgv` in the baked data. If
   OSM tags them, the tagged sample already reads 65 — but the cap would still
   pull it to 55, because the cap is applied as a `min`. **This would need a code
   change: let an explicit `hgv` sample override the statutory cap rather than be
   floored by it.** That is arguably the correct fix generally, and it is the
   same shape as the fix the recipe describes for tagged-vs-statutory.
3. Hold Oregon at 65 until the corridor data exists. Keeps today's known error.

**My recommendation: option 2**, with option 1 as the fallback if the tagging
isn't there. Option 2 is the only one that ends with Oregon actually correct, and
the code change it needs is small and independently justified — an explicitly
tagged truck posting is better evidence than a state default and should win.
This is a genuine design call, not a data entry, which is why it is here.

### 4b. Arkansas is 50 off the controlled-access network — and it is live law

I initially flagged this as probable dead-letter text and was wrong; a second
pass verified it against the primary enacting PDF. **Ark. Code 27-51-201(c)(2)
caps "trucks of one-and-one-half-ton capacity or more in other locations" at
50 mph** — that is every non-controlled-access road in Arkansas. It comes from
**Act 784 of 2019, effective 2020-07-01**, so it is recent law, not 1930s
scaffolding.

That is a **20 mph gap** from the 70 the proposed table would serve on an
Arkansas US or state highway — the single largest numeric error remaining in
the audit, and larger than any error the proposal fixes.

Two complications make this a decision rather than an edit:

- It uses a **different vehicle test** from the 70 provision. The 70 applies to
  a "commercial motor vehicle" (26,001 lb GVWR, in commerce, per subsection
  (h)); the 50 applies to "one-and-one-half-ton capacity", an older
  rated-capacity measure. A rig is inside both, but the two rules are not
  parallel and cannot share one predicate.
- It contradicts observed practice — Arkansas posts 65 for all traffic on many
  US routes. Either enforcement is discretionary or the posted-limit path in
  27-51-201(b)(3) supersedes. **Not resolvable from the code alone.**

Recommend keeping `"Arkansas": 70.0` for now (it is correct on the
controlled-access mileage that carries almost all through-freight) and treating
the 50 as road-class work in the same bucket as Virginia and Montana. Flagging
loudly because if a player drives an Arkansas US highway, the game is currently
20 mph optimistic and says the state's name while doing it.

### 4c. Illinois — a real split the state-keyed dict cannot hold

625 ILCS 5/11-601(e) caps second-division vehicles ≥8,001 lb at **60 on
interstates, 55 elsewhere**, but **only in Cook, DuPage, Kane, Lake, McHenry and
Will counties** — the Chicago metro. Everywhere else in Illinois trucks run 70.

A flat `"Illinois": 60.0` would be wrong across most of the state's 30 legs;
omitting it is wrong across the busiest freight metro in the Midwest. **The dict
cannot express either answer correctly.** Options: a county-scoped override list,
or bake `maxspeed:hgv` onto the affected legs during enrichment and leave the
statutory table out of it.

Note also a widely-repeated error worth not inheriting: secondary sources call
this a **county opt-out covering eight counties**. It is not an opt-out — it is
mandatory by statute — and the truck provision names **six** counties. The
eight-county list (adding Madison and St. Clair) belongs to a *different*
subsection, 11-601(d-1), which is a general ordinance power over all vehicles and
appears unexercised.

### 4d. Virginia — real, but adding it flat would be actively harmful

Va. Code 46.2-870 gives trucks **45 mph where cars get 55**, on secondary roads
only. On interstates Virginia trucks match cars. A flat `"Virginia": 45.0` would
cap trucks at 45 on I-81 — a far larger error than the one it fixes.
Recommend **omit** and record as road-class-conditional work. Flagging because
the brief asked for unrepresentable cases explicitly, and this is the clearest.

### 4e. Sources disagreeing, shown rather than resolved

- **Nevada.** IIHS lists Nevada 80 for cars *and* trucks. Trucking aggregators
  claim a posted 70 truck limit on rural interstates. The statute imposes no
  split (NRS 484B.600/484B.613), which settles the *statutory* question — but
  whether NDOT has posted one under its 484B.613 authority could not be
  confirmed (dot.nv.gov returned 403). **I trust IIHS**: it tracks posted maxima
  with the states directly, and the aggregators cite nothing. Recommend removing
  Nevada; re-check if a player reports a posted truck sign there.
- **Illinois State Police** publishes a traffic-safety page asserting a
  *statewide* 60 mph cap on second-division vehicles and anything towing, with no
  county qualifier. That page also self-contradicts on the rural interstate
  number (says both 70 and 65), so I read it as a stale summary and trust the
  statute. Flagging because it is a `.gov` source contradicting the code.
- **New Mexico.** Several aggregators state a 65 mph truck-tractor limit "took
  effect July 1, 2025." That is the *proposed* effective date in **SB 226
  (2025), which died** — passed the Senate 17-13, then "Action Postponed
  Indefinitely" in House Judiciary. Do not add New Mexico. It passed a chamber
  and may return, so it is worth a re-check next session.
- **Wikipedia's truck columns** (NY 40–65, CT 45–65, MD 40–65, NJ 50–65) are
  road-class ranges misfiled into a truck column, not differentials. They
  contradict IIHS and every primary source. Do not use that table for this field.

### 4f. Low-confidence items I did not act on

- **South Dakota.** SDCL 32-25-6 delegates heavy-vehicle (>10,000 lb) speed
  authority to the Transportation Commission. The negative is well-supported but
  the ARSD administrative-rules sweep was not exhaustive.
- **New England Thruway (I-95, NY).** One uncited site claims a posted "Truck
  Speed Limit 50". It sits oddly against VTL 1180-a's uniformity mandate, which
  would appear to forbid it. LOW CONFIDENCE, corridor-specific at most.
- **Arizona HB 2059 (2026 session, "RAPID Act").** Would raise rural interstates
  to 80 and create daylight-only derestricted zones that **exclude commercial
  vehicles**, without touching 28-709. If enacted the Arizona split *widens* to
  65 vs 80. Introduced, not law. Worth a watch.
- **Hawaii HB 229 (2025).** Would impose 50 mph on 3+ axle / >10,000 lb vehicles
  in counties over 500,000 population (Honolulu only). Passed the House; final
  status unverified (capitol.hawaii.gov 403). County-scoped and axle-conditioned
  if it ever lands.

### 4g. Tests that encode the current errors

Three tests in `tests/test_maxspeed.py` will need to move with this, and two of
them assert the bugs directly:

- **Line 340**: `_split_limit_trip("Arizona", 75.0, hgv=False).truck_limit_at(50.0) == (False, None)`
  — asserts that an Arizona 75 posting is *not* a truck limit. This is precisely
  the missing-split failure, locked in by a test.
- **Line 356**: uses Arizona as the exemplar of "a state with no statutory
  split". Needs a different state once Arizona is added — Nevada or Ohio works.
- **Lines 244–264** (`test_runtime_caps_oregon_and_idaho_truck_limits`): tests
  Idaho 75 → 70, which the repeal invalidates, and Oregon 70 → 65, which becomes
  70 → 55.

### 4h. Data-model findings beyond the numbers

The flat `{state: mph}` shape cannot represent, in rough order of impact:

1. **County scoping** — Illinois (6 counties, truck-only, interstate-vs-other).
2. **Road-class scoping** — Virginia (secondary only), Montana (70 interstate /
   65 other), Arkansas (rural controlled-access only), Indiana (rural interstate
   + Toll Road only), Oregon (named-corridor exceptions).
3. **Conditional engagement** — Michigan's cap engages only where the posting
   exceeds 65; on a 55 county road the truck just follows the sign. The current
   `min()` happens to produce the right answer here, but by luck, not by model.
4. **Eight mutually incompatible vehicle-class tests.** Arizona/Indiana
   >26,000 lb (Indiana's is *declared* gross weight — a registration figure, not
   scale weight); Michigan ≥10,000 lb *or any truck-tractor*; Washington
   >10,000 lb *or any combination*; Oregon >10,000 lb truck / >8,000 lb truck
   tractor; Illinois ≥8,001 lb second-division; Montana >1 ton manufacturer's
   rated capacity; Arkansas 26,001 lb GVWR *and separately* 1.5-ton capacity for
   its own 50 mph rule; California 3+ axles *or towing*. **No single "is this a
   heavy truck" boolean works across states.**
   - **The towing prongs have no weight floor at all.** Washington's "vehicles
     in combination" and California's "drawing any other vehicle" make a pickup
     with a utility trailer legally a 60 and a 55 respectively. These are towing
     rules, not heavy-vehicle rules, and a weight-keyed model gets every light
     combination wrong.
   - **Bus handling is inconsistent**: Indiana excludes buses, Michigan
     explicitly includes school buses, Washington excludes "auto stages",
     California and Oregon include school buses.
5. **Seasonal overrides** — Michigan MCL 257.627(3) drops these same vehicles to
   **35 mph** during declared reduced-loading ("frost law") periods. Given the
   chains and grade work already in 1.9, this one has real gameplay texture.
6. **Weather-conditional truck limits** — Mississippi § 63-3-505 requires trucks
   and combinations to reduce to 45 in poor visibility; PennDOT imposes tiered
   commercial-vehicle restrictions during declared weather events. Both are
   genuinely truck-specific and would model as weather state, not a static limit.
7. **Day/night, and splits that vanish** — Montana's *general* limits are
   day/night split (75/70, 70/65) while its truck limits are flat 70/65. The
   consequence is that **Montana's two-lane truck penalty is 5 mph by day and
   exactly zero at night** (cars drop to 65, trucks stay 65), and the split also
   disappears entirely on urban interstates (65 for everyone). A static cap
   asserts a restriction at 2 a.m. that the law does not impose. Iowa unpaved is
   55 day / 50 night; Rhode Island 50/45 on unposted open roads.
8. **Agency-posted overrides** — Arizona ADOT, Nevada NDOT, Maryland SHA and
   Oklahoma OTA can all post truck-specific limits without a statutory change.
   Nevada and Oklahoma have the authority unexercised today; a future split there
   would appear as posted data, not as a law change.

A shape that would hold all of this: per-state rule objects keyed on road class,
with a vehicle predicate (weight threshold + truck-tractor flag + bus exclusion),
an optional county/corridor override list, and a seasonal/weather override slot.
That is also close to the jurisdiction-keyed generalization the enrichment recipe
already calls for when the map leaves the US.

---

## 5. Live impact

Legs currently in the world data for the states whose entry changes:

| State | Legs | Effect of the proposed change |
|---|---|---|
| Arizona | 33 | Gains a 65 cap that does not exist today — was serving the car number |
| Idaho | 21 | Loses a false 70 cap; trucks now run the posted 75–80 |
| Nevada | 25 | Loses a false 75 cap |
| North Dakota | 13 | Loses a false 75 cap |
| Oregon | 35 | Cap tightens 65 → 55 (see §4a for the corridor complication) |
| Illinois | 30 | Unchanged pending a decision on county scoping |
| California | 97 | Unchanged — verified correct |

---

## Independent verification (Oatis, 2026-07-20)

The audit ran its later checks after exhausting the session web-search
budget, which is exactly where errors hide, so I spot-checked the two
claims most likely to be wrong. **Both verified against primary text.**

**Idaho repeal — CONFIRMED.** Idaho Code 49-654 as published by the Idaho
Legislature now reads, for vehicles of five or more axles over 26,000 lb:
"the maximum lawful speed limits on interstate highways, in nonurban areas,
in urban areas, on state highways, or in other locations shall be the same
as for vehicles with less than five (5) axles". Amendment history on the
page shows 2026, ch. 108, sec. 1, p. 555. Source:
https://legislature.idaho.gov/statutesrules/idstat/Title49/T49CH6/SECT49-654/
(accessed 2026-07-20). The Idaho entry must go.

**North Dakota 80 with no split — CONFIRMED.** I doubted this one and was
wrong. NDCC 39-09-02(1)(i) reads "Eighty miles [128.75 kilometers] an hour
on access-controlled, paved and divided, multilane interstate highways",
with (1)(h) setting 70 on paved divided multilane and (1)(g) 65 on posted
two-lane. Nothing in 39-09-02 distinguishes trucks from cars. Source:
https://ndlegis.gov/cencode/t39c09.pdf (accessed 2026-07-20). The current
75.0 entry invents a cap that binds nobody in law.

Not independently re-checked: Arizona, Oregon, Arkansas, Illinois, Virginia,
and the four entries the audit confirmed correct. Given two for two on the
claims I most doubted, I'd treat the rest as sound but still owner-reviewed
before merge -- the failure mode here is a confidently-spoken false law, and
the game now says the state's name out loud.

**Nothing has been merged. This remains a proposal.**

---

## The three open items — RESOLVED (Oatis, 2026-07-20)

Owner declined to keep arbitrating and asked for them settled. All three were
the same defect in different clothes: **the flat `{state: mph}` dict cannot
express a cap that varies by road class or region.** Resolutions below; the
structure change they imply is the one non-US expansion needs regardless.

### Oregon — set 55, and make hgv tags authoritative over the cap

ORS 811.111(1)(b) makes 55 the statewide default; 60/65 are named
eastern-corridor exceptions. Rather than maintain a per-highway exception
list, let an explicit `maxspeed:hgv` sample **override** the statutory cap
instead of being floored by it (`min`). Justification is in the data:

```
hgv-tagged samples above 55 mph, by state:
  Oregon 144 | Michigan 66 | Montana 61 | Washington 60 | Indiana 52
  Arkansas 27 | Idaho 26 | Utah 8 | Illinois 3 | Texas 3
  California 2 | Ohio 1 | Wisconsin 1 | Wyoming 1
```

Oregon's 144 above-55 truck tags ARE the corridor exceptions, already mapped.
The statutory cap exists to fill gaps where OSM carries only the car number;
it has no business overruling real truck tagging.

**Risk checked before recommending.** The override would be unsafe if a
split-limit state carried stale high hgv tags. California has exactly **two**,
and both are artifacts:

```
sacramento_ca_us:portland_or_us  I-5  mile 286.7 of 578.0  60 mph
san_francisco_ca_us:portland_or_us  I-5  mile 341.3 of 633.0  60 mph
```

Both sit near the Oregon line on ~600-mile legs — state attribution at the
crossing, not mis-tagged California road. **Fix these two separately**; under
the new rule they would serve 60 mph in California. Everything else is clean.

### Arkansas — road-class-scoped cap

Ark. Code 27-51-201(c)(2) (Act 784 of 2019): 70 on controlled-access, **50
elsewhere**. `_highway_class()` in `trip_models.py` already returns
interstate / us_highway / state_route, so this needs no new data — only a cap
keyed by (state, class).

### Illinois — omit, and say why in the comment

The 60/55 split for >=8,001 lb is real but scoped to six Chicago-area
counties, and no county data is baked. Approximating that boundary from city
proximity would be **inventing a legal line** — the same failure mode as
inventing a place, and worse because it would be enforced. Omit until county
polygons exist.

### Implied structure

```python
# jurisdiction -> {road_class_or_default: mph}
# and an explicit maxspeed:hgv sample outranks the statutory cap
```

This is also the shape Canada/Mexico/Europe need (national default with a
regional/class override), so it is not Oregon-and-Arkansas-specific work.

**Still not merged.** Queued after Phil's fold, before the lanes job.
