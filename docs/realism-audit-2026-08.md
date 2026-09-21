# Freight Fate realism audit — smart-trucking.com vs. the code

Branch audited: `feat/career-1.9`, main tree only, read-only. No tests run.
Date: 2026-08-11.

## Method

Source mining started from `https://www.smart-trucking.com/sitemap.xml`.
`robots.txt` is `User-agent: * / Disallow:` — the site explicitly permits
automated access, so no crawl-consent problem arose.

Roughly 30 pages were read, selected against systems the game actually
models: hours of service, grades and engine braking, winter traction and
chains, axle weights and scaling, inspections, fuel and idling, truck specs,
trip planning and parking, docks, securement, pay and settlement, owner-
operator cost structure, factoring, and the industry glossary.

Everything from the site is paraphrased. Facts that would drive a
significant rebalance were checked against a second source — FMCSA, eCFR,
CVSA, NHTSA, FHWA, ATRI, Argonne, CDOT — and where the practitioner site
and the regulator disagree, that is called out explicitly below.

Code inventory was taken from `src/freight_fate/` across HOS/fatigue,
driving physics, enforcement, weather, cargo, and career economics.
`ROADMAP.md` (4,011 lines) was read for known-open items; anything already
tracked there is excluded and listed in section G.

Excluded by instruction: the fines rebalance on `feat/fines-rebalance`, and
the curve-assist engine-brake overuse fix.

---

## Top five, one line each

1. **Detention pay, lumper fees, washouts and tolls are calculated, spoken
   to the player, and then never move a single dollar** — including for
   owner-operators, who in reality pay tolls and lumpers out of pocket.
2. **A large fraction of dispatched loads would be illegally overweight**
   (up to ~87,000 lb gross), and no scale in the game ever weighs the truck.
3. **Every open weigh station costs 15 minutes of on-duty time with no
   bypass option**, where a real clean carrier gets a green light 85–90% of
   the time and rolls through in under two minutes.
4. **The repeat-citation fine multiplier is uncapped**, so a late-career
   driver pays several times the statutory maximum for a routine ticket.
5. **Relaxed HOS mode inflates the legal limits themselves** (11 h becomes
   13.75 h, 14 h becomes 17.5 h) and speaks them as hours of service, so the
   mode most likely to be chosen by a new or fatigued player teaches numbers
   that do not exist.

---

# A. Things the game gets wrong

## A1. Accessorial money is spoken but never paid or charged

**What the game does.** `models/settlement.py::carrier_accessorial_charges`
produces detention pay, a $185 delivery lumper and a $45 trailer washout.
`models/trailer_yard.py` computes detention at `DETENTION_FREE_MIN = 120.0`
then `DETENTION_PER_HOUR = 45.0`, and `states/city_pickup.py:237` speaks
"so you are owed {n} dollars in detention." At settlement,
`states/driving_menu_states.py:975` builds
`carrier_charges = toll_expense + charge_total(accessorials)` and that
variable is used in exactly two places — the spoken lines at 1206 and 1311.
It is never passed to `build_business_settlement` and never touches
`profile.money`. Toll events are baked into the world (46 across 14 states)
and accrue into `trip.toll_expense` on the same dead path.

**What really happens.** Detention past a two-hour free window is a real,
billed accessorial; industry reporting puts it at roughly $50–100/hour, and
ATRI's 2024 study found drivers detained at 39.3% of all stops in 2023, at a
cost of $15.1 billion to the industry
(https://www.abltrucking.com/post/the-real-cost-of-driver-detention-what-the-data-tells-us,
https://landline.media/study-shines-a-spotlight-on-costly-cascading-effects-of-detention-time/).
Carriers publish concrete schedules — Smart Trucking cites KLLM at $10/hour
after 3 hours capped at $100/day, and Bison at $100 per 24-hour layover
(https://www.smart-trucking.com/truck-driver-salary/,
https://www.smart-trucking.com/bison-transport/). Lumper fees are paid by
the driver at the dock and reimbursed by the carrier; Smart Trucking's own
position is that it is illegal for the driver to eat an unreimbursed lumper
charge (https://www.smart-trucking.com/lumpers/). Tolls are a real
owner-operator line item — ATRI's 2025 cost study logged tolls as the
fastest-rising category, up 13.2%
(https://www.ttnews.com/articles/atri-truck-costs-2025).

**Why it matters.** The game tells the player, out loud, that they are owed
money, and then does not pay it. That is worse than not modelling detention
at all — it reads as a bug to any player who checks their balance. For
company drivers the carrier-pays framing is defensible; for owner-operators
and own-authority drivers it is simply wrong in both directions, and it
removes the entire economic reason to care about a slow dock, which is the
main thing that makes dock choice interesting.

**Size.** Small for the fix that matters most: route `carrier_charges`
through the settlement for owner-operator and independent-authority statuses
(credit detention, debit tolls and lumpers), and reword the company-driver
line so it does not promise money that is not coming.

**Confidence.** High. Verified in the code directly, not via a subagent.
Corroborated by ATRI, Land Line and two carrier pay schedules.

## A2. Loads routinely exceed the federal gross weight limit, and nothing checks

**What the game does.** `sim/vehicle.py` sets `REFERENCE_CARGO_KG =
21_500.0` and a default `TruckSpecs.mass_kg = 36_000.0`, giving
`tare_kg = 14,500 kg` (~31,970 lb) and
`gross_mass_kg = tare_kg + cargo_kg`. `models/jobs.py::CARGO_CATALOG`
draws payload from per-cargo ranges that top out at 25 tonnes for `bulk`,
`grain`, `construction`, `steel`, `machinery` and `fuel_bulk`. A 25-tonne
load therefore grosses 39,500 kg ≈ **87,080 lb**. There is no gross limit,
no axle group, no bridge formula, and the string "overweight" does not
appear anywhere in `src/`. The only mention of 80,000 lb in the codebase is
a comment explaining `DRIVE_AXLE_LOAD_FRACTION = 0.425`.

**What really happens.** Federal interstate limits are 80,000 lb gross,
34,000 lb per tandem group, with the Federal Bridge Gross Weight Formula
capping any consecutive axle group
(https://en.wikipedia.org/wiki/Federal_Bridge_Gross_Weight_Formula). Smart
Trucking's practical target for a legal 80,000 lb rig is 12,000 steer /
34,000 drives / 34,000 trailer (https://www.smart-trucking.com/axle-weights/,
https://www.smart-trucking.com/18-wheeler/). With a ~32,000 lb tare the
legal payload ceiling is about 48,000 lb ≈ 21.8 tonnes — so the game's
22–25 tonne loads are 1,000–7,000 lb over. Fines are state-assessed on a
per-pound sliding scale; New Jersey charges $500 for the first 1,000 lb over
gross plus $100 per additional 1,000 lb, and federal civil penalties for
size-and-weight violations reach $16,000
(https://www.njticketatty.com/overweight-truck-ticket-39-3-20/,
https://blog.thetruckercodex.com/overweight-violations-permit-requirements-fines-and-carrier/).

**Why it matters.** It teaches something false about the single number every
real driver watches, and it makes the weigh station a pure tax — the player
stops, waits 15 minutes, and is never actually weighed. Weight is otherwise
one of the best-modelled things in the game (it drives acceleration, grade
lugging, braking capacity, tire wear and fuel burn), so the omission is
conspicuous.

**Size.** Two options. Cheap: clamp `weight_tons` ranges so no generated
load can gross over 80,000 lb, and speak the gross on the dispatch board.
Expensive but high value for an audio game: a real scale mechanic — a
spoken CAT-scale ticket with steer/drive/trailer numbers, sliding the
tandems N holes at ~400 lb per hole to shift weight, and an overweight
citation if you cross a scale heavy. Smart Trucking documents the whole
procedure and the 400 lb/hole figure
(https://www.smart-trucking.com/tandem-axle-trailer/); a CAT scale weigh is
$13.50 with a $4.00 reweigh
(https://landline.media/cat-scale-prices-up-slightly/). Note it needs an
axle-split model, which the physics does not currently have.

**Confidence.** High on the discrepancy (arithmetic from the code
constants). Medium on how much of the scale mechanic is worth building.

## A3. Relaxed HOS mode changes the law rather than the enforcement

**What the game does.** `sim/hos.py`:
```
_REALISTIC = (11 * 60.0, 14 * 60.0, 8 * 60.0)
LIMITS = {"realistic": _REALISTIC,
          "relaxed": tuple(x * 1.25 for x in _REALISTIC)}
```
Relaxed mode therefore runs 13.75 h driving, a 17.5 h window, and 10 h
before the break. `HosClock.summary()` speaks these as "Hours of service",
and `violation_causes()` speaks phrases like "you had driven past the
11-hour driving limit" — which in relaxed mode is spoken against a 13.75 h
clock.

**What really happens.** 11 hours driving inside a 14-hour window, 30
minutes after 8 cumulative hours of driving, is 49 CFR 395.3 and there is no
"easier" version of it (https://www.fmcsa.dot.gov/regulations/hours-of-service).

**Why it matters.** Relaxed mode exists for accessibility and for players
who want a calmer drive — exactly the players least likely to already know
the real numbers. Speaking a fabricated limit as "the 11-hour driving limit"
is the one category of error an educational-adjacent sim should not make.

**Size.** Small, and there is a clean fix that keeps the design intent:
leave the real limits in place and relax the *consequences* in relaxed mode
(inspection odds, fine severity, out-of-service duration) rather than the
clock. The game already has that lever — `RELAXED_HAZARD_SCALE = 0.2`
scales hazards this way.

**Confidence.** High.

## A4. Fatigue only accrues while the truck is moving

**What the game does.** `states/driving_updates.py::_update_hours_and_fatigue`
adds fatigue only inside the `moving` branch (`speed_mph > 5.0`). The
14-hour duty window correctly keeps running while parked, but a driver held
four hours at a dock, or spending 90 minutes waiting on a mechanic, gets
zero fatigue. Loading, fuelling, inspections and chain-up all cost time and
HOS but no tiredness.

**What really happens.** Detention is one of the most-cited fatigue drivers
in the industry precisely because it burns the driver's day without rest —
the ATRI and FMCSA detention work frames the cost as lost driving time and
degraded scheduling, not as rest
(https://landline.media/magazine/detention-time-new-study-outlines-true-costs-consequences/).
Chain installation in particular is heavy physical work in bad weather; the
game already models that as a fatigue cost (`CHAIN_INSTALL_FATIGUE = 6.0`),
which shows the model can express it.

**Why it matters.** It quietly makes a slow dock the *safe* choice, which
inverts the real trade-off. It also means a player can burn most of a
14-hour window on duty-not-driving and still start driving fresh.

**Size.** Small — an on-duty-not-driving fatigue rate, lower than the
driving rate, applied in `_advance_rest_clock` where duty status is already
recorded.

**Confidence.** High on the code behaviour; medium-high on the magnitude of
a suitable on-duty rate (no single authoritative number — pick something
around a third of the driving rate and playtest).

## A5. A missed 30-minute break costs a flat 10 hours out of service

**What the game does.** `states/driving_events.py::_handle_inspection`
routes any HOS violation to `_place_out_of_service()`, which advances the
clock by `OUT_OF_SERVICE_MIN = hos.SLEEP_MIN` — 600 minutes — regardless of
which of the three limits was broken. `hos.violation_causes()` already
distinguishes the drive limit, the duty window, and the break rule.

**What really happens.** The out-of-service order lasts until the violation
is corrected. A driver over the 11-hour or 14-hour limit needs a full
10-hour reset. A driver who missed the 30-minute break needs 30 consecutive
minutes off duty. CVSA describes out-of-service as lasting "until the
condition(s) or defect(s) can be corrected"
(https://cvsa.org/inspections/out-of-service-criteria/); the 10-hour figure
is specific to certain violations such as operating without a required ELD
(https://cvsa.org/news/april-1-2018-eld-oos-full-enforcement/).

**Why it matters.** It is the single harshest disproportion in the
enforcement model — a 30-minute administrative slip and an 11-hour driving
violation are punished identically, and the 10-hour version can strand a
delivery. This is the kind of thing that shows up in tester frustration.

**Size.** Small — branch `_place_out_of_service` on the violation cause the
model already computes: 30 minutes for a break violation, 600 for the two
clock violations.

**Confidence.** High on the game behaviour and on the general CVSA
principle. I could not find a public, quotable line in the CVSA criteria
stating the break-violation duration explicitly — the criteria document is
paywalled — so treat the exact 30-minute figure as the logical reading of
"until corrected" rather than a cited constant.

---

# B. Things missing entirely

Ordered by player impact, not by realism interest.

## B1. Pre-trip inspection / DVIR

**Missing.** No pre-trip, walk-around, or Driver Vehicle Inspection Report
exists anywhere in `src/`. Trailer defects are generated
(`TrailerUnit.defect`) and surface only as evidence at a roadside
inspection — the player has no way to find them first.

**Real practice.** A daily DVIR is required by FMCSR 396.11; Smart Trucking
puts a thorough pre-trip at 10–15 minutes and lists the specific checks:
slack adjuster travel over one inch means the brake needs adjustment, drive
tires 100–110 psi with 2/32" minimum tread, steer tires 110–120 psi with
4/32" minimum (https://www.smart-trucking.com/pre-trip-inspection/). Smart
Trucking's inspection piece also notes a missing spare is an automatic
out-of-service item and that fifth-wheel and tandem-slider security
violations are unusually common
(https://www.smart-trucking.com/csa-inspection/).

**Why it matters.** This is close to an ideal audio-first mechanic: a
sequence of named checks with spoken results, real numbers, and a genuine
risk/time trade-off against the delivery clock. It also gives the existing
trailer-defect system a purpose — right now the player is punished for a
defect they had no opportunity to find. Of everything in this report, this
is the biggest gameplay-per-unit-of-work item.

**Size.** A system, but a contained one: a menu-driven inspection at
departure that reveals existing `TrailerUnit.defect` and truck wear state,
costs on-duty time, and reduces the citation risk at the next inspection.

**Confidence.** High.

## B2. Diesel exhaust fluid

**Missing.** No DEF, aftertreatment, or urea model. Confirmed by grep.

**Real practice.** Roughly one gallon of DEF per 50 gallons of diesel (~2%),
one gallon lasting 300–500 miles; running the tank dry triggers an engine
derate to about 5 mph, and many trucks will not restart
(https://otrsolutions.com/blog/what-is-diesel-exhaust-fluid,
https://www.hotshotsecret.com/what-is-diesel-limp-mode/). Note the EPA moved
in 2026 to relax the low-DEF limp-mode requirement
(https://tfltruck.com/2026/02/epa-def-systems-guidance-update-diesel-trucks-news/),
so the derate is regulation-dependent, not physics.

**Why it matters.** It is a second consumable with a different refill
cadence from fuel, and it produces the game's most dramatic failure state.
The game already has a derate/limp/creep ladder (`DAMAGE_LIMP_CAP_MPH =
45.0`, `DAMAGE_CREEP_CAP_MPH = 10.0`) to hang it on.

**Size.** Small: a second tank level, a burn rate tied to fuel burn, a
spoken warning ladder, and a reuse of the existing speed cap.

**Confidence.** High on the mechanic; medium on whether to model the derate
given the 2026 EPA change — worth a design call rather than a straight copy.

## B3. Fuel weight in the gross

**Missing.** `gross_mass_kg = tare_kg + cargo_kg`. `fuel_gal` exists
(150–250 gallons across the catalog) but contributes no mass, so the truck
does not get lighter as it burns fuel and a full tank costs nothing at a
scale.

**Real practice.** Diesel runs about 7 lb per gallon, so 300 gallons is
~2,100 lb; drivers running heavy leave a fuel buffer — Smart Trucking
describes allowing about 3,000 lb on a 77,000 lb unit, and deliberately not
fuelling immediately before a scale
(https://www.smart-trucking.com/weight-of-diesel-fuel/). Smart Trucking's
fuel-economy piece gives 7.2 lb/gal
(https://www.smart-trucking.com/diesel-fuel-economy/); the two pages
disagree slightly, and 7.0–7.1 lb/gal at typical temperatures is the
standard figure.

**Why it matters.** On its own, almost nothing — nobody would notice. It
only becomes meaningful if B2 in section A2 (weights) is built, at which
point it is the mechanic that makes fuel stop planning interesting. **Do not
build this alone.**

**Size.** A constant, gated on the weight system existing.

**Confidence.** High.

## B4. Hazmat

**Missing.** `chemicals` and `fuel_bulk` cargo exist with no hazmat class,
placards, routing restriction, or tunnel/bridge ban. `ENDORSEMENT_LEVELS`
has no hazmat entry.

**Real practice.** Hazmat endorsement requires a TSA security threat
assessment and fingerprinting, and hazardous materials carry route
restrictions under 49 CFR 397 — tunnel bans, designated routes, and
attendance/parking rules.

**Why it matters.** Medium. It is a natural late-career freight class and
the roadmap already names it as the intended spine for levels 14–30.
Flagged here only to note the *endorsement* side (background check, expiry,
renewal) is absent as well as the routing side.

**Size.** A system. Partly covered by roadmap L488; see section G.

## B5. Weigh-station bypass service

Covered under C1 below, since the player-facing problem is the punishment,
not the absence.

## B6. Tire blowout

**Missing.** No blowout event. Tire wear degrades grip
(`TIRE_WEAR_GRIP_LOSS = 0.25`) and nothing else, and wear at 100% still only
fades the physics.

**Real practice.** A steer-tire blowout is one of the defining emergencies
of the job, and it is the reason steer tires carry a higher minimum tread
(4/32" vs 2/32") and higher pressure
(https://www.smart-trucking.com/pre-trip-inspection/).

**Why it matters.** Medium. It gives worn tires a consequence with a sound
and a reaction window, and the hazard/reaction machinery already exists.
Note the roadmap already tracks "wear ceilings need their own wall"
(L569) and roadside tire service, so this is an extension of tracked work
rather than a fresh gap.

**Size.** A rule plus one hazard definition.

## B7. Fuel surcharge

**Missing.** No fuel surcharge anywhere. Every load pays a single all-in
rate.

**Real practice.** A fuel surcharge separate from linehaul is on essentially
every real rate confirmation. The roadmap's freight-market realism item
(L3946) already names it.

**Why it matters.** Low-medium on its own; it matters because the game's
regional fuel prices vary from $3.40 (gulf_coast) to $5.10 (california) and
the player currently absorbs all of that with no offset — which is the
opposite of how real lanes price. Listed here for completeness; see G.

---

# C. More punishing than reality

**This is the section most likely to be behind tester frustration.**

## C1. Every open scale costs 15 minutes, with no way to be waved through

**What the game does.** `WEIGH_STATION_NOTICE_MI = 2.0`,
`WEIGH_STATION_BYPASS_MPH = 15.0`, `INSPECTION_MIN = 15.0`. A scale is open
45% of weekdays (`SCALE_OPEN_WEEKDAY = 0.45`, weekend 0.12). If it is open,
the player must slow below 15 mph and check in for 15 minutes of on-duty
time — every time, regardless of safety record. `inspection_selection_chance`
(0.08 clean / 0.45 watched / 1.00 targeted) then decides whether anything
further happens. There is no PrePass, Drivewyze, or transponder concept
anywhere in the codebase.

**What really happens.** A truck crosses a modern scale on a weigh-in-motion
ramp without stopping unless it is pulled in. Bypass services cover 700+
(PrePass) and 900+ (Drivewyze) sites across 45–47 states, and a carrier with
a clean record sees bypass rates of 85–90%
(https://rockytransportinc.com/blog/weigh-station-guide-truckers/,
https://otrucking.com/resources/guides/prepass-vs-drivewyze/). Smart
Trucking's glossary describes scales as facilities that *randomly* check
weights and sometimes inspect (https://www.smart-trucking.com/trucking-terms/).

**Cost to the player.** With scales spaced along a corridor, a long run can
lose the better part of an hour of the 14-hour window to nothing but
check-ins. Because that time lands in the duty window, it directly reduces
achievable miles — this is a compounding punishment, not a flat one.

**Recommended shape.** Keep the stop as the default. Make the 15 minutes the
*selected* case rather than the universal one: a clean safety record should
usually produce a spoken green light and a 1–2 minute roll-through, and the
existing `inspection_selection_chance` bands are already the right lever.
A purchasable transponder for owner-operators is the natural
progression unlock and mirrors the roadmap's planned toll transponder.

**Size.** Small to medium — mostly re-using the safety-record bands that
already exist.

**Confidence.** High.

## C2. The repeat-citation multiplier has no ceiling

**What the game does.** `models/enforcement.py`:
`CITATION_REPEAT_STEP = 0.5`, applied as `1 + 0.5 * priors` over every prior
citation in the career. `repeat_fine` accepts an optional ceiling and **no
call site passes one**. A driver with ten prior citations pays 6× — a $250
first speeding ticket becomes $1,500, and the top band ($2,500 at 30+ over)
becomes $15,000.

**What really happens.** Repeat-offender escalation is real, but statutory
maximums are fixed. FMCSA's schedule caps an HOS violation at $4,812 for a
driver ($19,246 for a carrier)
(https://aguiarinjurylawyers.com/dot-fines-for-hours-of-service-violations/),
and state speeding fines have hard ceilings. Real escalation for a repeat
offender goes to *licence status* — 49 CFR 383.51's serious-violation ladder
(60 days for a second, 120 for a third), which the game already models
correctly via `SERIOUS_SECOND_SUSPENSION_DAYS` / `SERIOUS_THIRD_*`.

**Why it matters.** The game already has the realistic escalation channel
(suspension) and then adds an unbounded monetary one on top. Late-career
players accumulate citations naturally, so this makes the economy get
harsher the longer you play, for reasons that never appear on a real ticket.

**Important interaction with in-flight work.** The fines rebalance
(ROADMAP L142) extends repeat-offender escalation from speeding to *every*
fine and makes it compound rather than add. Applied on top of an uncapped
multiplier, that will multiply the problem rather than fix it. **This is
worth raising with whoever owns that branch before it lands**: a per-fine
ceiling (a multiple of the base, or an absolute cap near the statutory
maximum) should go in as part of the same change.

**Size.** A constant plus one argument at the call sites.

**Confidence.** High.

## C3. Chain law activates on physics, not on a posted control

**What the game does.** `Trip.chain_law_level()` returns level 2 (chains
required) whenever the surface is ice and level 1 whenever it is snow,
anywhere a chain-law area exists (`CHAIN_LAW_MIN_GRADE = 0.05` over
`CHAIN_LAW_MIN_RUN_MI = 1.0`). Chaining costs 25 minutes (×1.6 at night)
plus 6–10 fatigue, and a checkpoint fires with `CHAIN_LAW_CHECKPOINT_CHANCE
= 0.6`.

**What really happens.** Chain laws are *activated by the state*, corridor
by corridor, not automatically by local conditions. Colorado's commercial
chain law on I-70 runs mile 163 to 259, September 1 to May 31, and is
imposed by CDOT; carrying chains is the year-round requirement, chaining up
is the activated one. Statewide the fine for not chaining when the law is in
effect is $500 plus a $157 surcharge, rising to $1,000 plus $313 if you
block the highway
(https://www.codot.gov/news/2025/november/new-traction-law-requirements,
https://www.truckinginfo.com/news/colorado-trucking-group-urges-drivers-to-obey-new-chain-laws).

**Why it matters.** Moderate, and this one is close to right — the game's
level 1 / level 2 split is explicitly modelled on Colorado's and matches it.
The over-punishment is that a brief icy patch on any 5% grade produces a
mandatory 25-minute chain-up at full fatigue cost with no advance
declaration, where a real driver hears the law go into effect on the radio
or sees the signs lit well before the corridor. The roadmap already tracks
chain-up areas as physical pullouts (L1596) and CA R1/R2/R3 wording (L1598),
so the remaining gap is specifically **advance notice and hysteresis** — the
level should be declared for a corridor and stay declared, not flicker with
the weather sample.

**Size.** Small — latch the level per area with an announcement.

**Confidence.** Medium-high. The game's fine ($500) matches Colorado's base
exactly, which suggests this was researched already; the rebalance branch
moves it to $580/$1,150, which also matches Colorado's two tiers well.

## C4. Deadhead is unpaid and unmodelled as a planning cost

**What the game does.** Pickup approach legs are capped at
`SYNTHETIC_APPROACH_CAP_MI = 9.0` and unpaid; long repositioning is a
`bobtail` job with "No load and no pay."

**What really happens.** Real deadhead is unpaid too — this part is
correct. But real drivers *choose* loads partly on deadhead, and the pay
floors in the game (`SHORT_HAUL_RATE_BY_LEVEL` up to $5.50/mi, long-haul
floors of $4.75–5.25/mi) are generous enough that the deadhead never bites.

**Why it matters.** Low. Noted only because it is adjacent to the facility
placement audit already on the roadmap (L2040, "776 approach pins land too
far out" — Josh's 35-mile Kenosha deadhead). That known bug is what makes
deadhead punishing today, not the design. **Not a new finding**; do not fix
the design when the data is the problem.

---

# D. More lenient than reality

## D1. Company driver pay floors are well above real rookie wages

The pay floor is `stop_pay + miles * min_per_mile`, with `min_per_mile`
between $0.74 and $0.95 and `stop_pay` between $130 and $225 per load.
Real entry-level company CPM in 2026 runs roughly $0.45–0.52, reaching
$0.65–0.80 only for senior drivers with clean records
(https://otrucking.com/resources/guides/otr-driver-salary-guide/); Smart
Trucking's own salary guide cites a US average of $45,570
(https://www.smart-trucking.com/truck-driver-salary/). A level-1 Freight
Fate rookie is paid better than a real senior driver.

Combined with `minimum_pay_for_level` floors of $4.75–5.25/mi at 600+ miles,
most of the `CARGO_CATALOG` `rate_per_mile` table is dead above level 4 —
the floor dominates. This overlaps the roadmap's freight-market pricing item
(L3946), so treat it as a data point for that work rather than a separate
task. Size: constants. Confidence: high on the arithmetic, medium on the
right target given the game is not trying to simulate poverty.

## D2. Owner-operator cost structure is thin but the total is close

The five owner-operator per-mile reserves come to $0.61/mi (maintenance
0.18, insurance 0.09, trailer 0.12, truck payment 0.22, plus a 2%
settlement fee). Add fuel at the calibrated ~6.5 mpg and a ~$3.80 average
price and you get roughly $1.19/mi. ATRI's 2025 figure is $2.336/mi
all-in, of which $1.028 is driver wages and benefits, leaving $1.308/mi
of non-driver cost (https://www.ttnews.com/articles/atri-truck-costs-2025).
**The total is within about 10% of reality**, which is a good result.

What is missing is the *shape*: no IFTA, no apportioned plates, no permits,
no escrow, no dispatch fee, no cargo insurance. Smart Trucking's cost-per-
mile worksheet lists licensing at $2,200/yr and permits at $650/yr as
separate lines (https://www.smart-trucking.com/trucking-cost-per-mile/), and
its factoring piece puts factoring fees at 1.5–4% of invoice with 75–90%
advanced in 24–72 hours (https://www.smart-trucking.com/factoring-brokers/)
— the game's `AUTHORITY_FACTORING_FEE_SHARE = 0.035` sits correctly inside
that band.

**Recommendation: do not chase the missing line items for accuracy's sake.**
The total is right and every added line is another spoken settlement row for
a screen reader to read. Add them only if a specific one becomes a
gameplay decision. This overlaps roadmap L3942.

## D3. Maintenance reserve is decoupled from simulated wear

`OWNER_MAINTENANCE_PER_MILE = 0.18` is charged per mile regardless of how
the truck is driven, while the actual wear model prices out around $0.014/mi
at shop rates (0.003%/mi tire wear × $45/pct). The player is charged a
reserve that has no relationship to the wear they cause, and the wear they
cause is far cheaper than the reserve. ATRI puts real repair and maintenance
at $0.202/mi rising 8.6% — so the *reserve* is right and the *wear pricing*
is roughly an order of magnitude too cheap. Size: constants. Confidence:
high on the arithmetic.

---

# E. Where the game is right — a plausible "fix" would make it worse

This section exists because several of these look like bugs.

## E1. The 30-minute break rule is implemented to the current regulation, and the source site is out of date

`sim/hos.py` triggers the break after **8 hours of driving** and accepts
**any 30 consecutive non-driving minutes**, including on-duty-not-driving.
That is 49 CFR 395.3(a)(3)(ii) as revised in 2020.

Smart Trucking's HOS page describes it as a 30-minute break "for every 8
hours of ON-duty time" (https://www.smart-trucking.com/dot-hours-of-service/)
— that is the **pre-2020 rule**. Implementing what the practitioner site
says would break a correct system. FMCSA's current guidance and the
implementing FAQs confirm the driving-time trigger and the on-duty-not-
driving qualification
(https://www.fmcsa.dot.gov/regulations/hours-of-service).

The same page also states the adverse-conditions exception as extending
driving to 13 hours; the actual rule extends **both** the driving limit and
the 14-hour window by up to two hours. That matters because the roadmap
already plans this exception (L92) — build it against the regulation, not
the article.

## E2. Split sleeper berth is implemented, and the roadmap says it is not

`hos.py` has `SPLIT_SHORT_MIN = 120.0`, `SPLIT_SHORT_ALT_MIN = 180.0`,
`SPLIT_LONG_MIN = 420.0`, `SPLIT_LONG_ALT_MIN = 480.0`, and
`_split_pair_qualifies()` correctly requires the longer period to be in the
sleeper berth and the pair to total 10 hours — i.e. both the 8/2 and 7/3
pairings of 395.1(g). ROADMAP lines 3328–3329 and 3480 still say
"the HOS model intentionally skips these today." **The roadmap is stale on
this point**; only the 60/70-hour cycle and 34-hour restart are genuinely
absent. Worth correcting so nobody builds it twice.

## E3. The jake brake does not heat the service brakes

`_update_temps` and `_update_wear` use `service_brake_force()` only, and
there is an explicit comment saying so. This is correct and it is the entire
point of an engine brake — Smart Trucking's position is that proper jake use
in the mountains "can add years to the life of the brake shoes"
(https://www.smart-trucking.com/jake-brake/). Do not "fix" this by adding
jake heat to the drums; it would destroy the descent lesson the game is
teaching.

Relatedly, the jake's RPM shaping (`0.3 + 0.7 * rpm/max_rpm`) and the
three-stage control match practitioner description of a 3-position jake
worked in the shifting range around 1100–1400 rpm, with stage 3 strongest
and lower stages for poor conditions (same source).

## E4. A full service brake application cannot damage freight

`max_brake_decel_g = 0.35` is deliberately below `CARGO_HARD_BRAKE_G = 0.45`,
so only emergency application, grade, or a collision can shift a load. This
is consistent with 49 CFR 393.102, which sizes securement for 0.8 g forward
and 0.5 g lateral — a properly secured load does not move under normal
braking. Do not lower the cargo threshold to "add tension."

## E5. Idle burn and cruise fuel economy are both right

The comment target of ~0.8 gal/h at idle matches Argonne's ~0.85 gal/h for a
long-haul sleeper (https://www.anl.gov/esia/idle-reduction-research), and
the ~6.5 mpg cruise calibration sits in the real range of 6.5–7.5 mpg for a
loaded tractor-trailer. Smart Trucking's fuel-economy page recommends 55–60
mph as the economy sweet spot and 50–55 into a headwind
(https://www.smart-trucking.com/diesel-fuel-economy/), which the drag model
reproduces naturally. No change needed.

## E6. Hydroplaning onset near 106 mph is not a bug

`HYDRO_ONSET_BASE_MPH = 106.0` derives from the Horne relation at ~105 psi,
and the water-depth and tread terms bring the effective onset down. Truck
tires at highway pressure genuinely do not plane at 55 mph on thin water —
that is why the failure mode on wet roads is loss of traction under braking
and cornering, not hydroplaning. Do not "fix" this by making trucks plane at
highway speed.

## E7. Braking capacity is ceilinged at rated gross

`service_brake_force()` caps friction at `specs.mass_kg * effort`, so an
overloaded truck stops longer. That is correct physics and it is the right
groundwork for A2 — if weights get built, this constant already carries the
consequence. NHTSA's FMVSS 121 reduced stopping distance standard reflects
the same principle, allowing 310 ft instead of 250 ft at 60 mph for the
heaviest configurations
(https://www.nhtsa.gov/sites/nhtsa.gov/files/121_stopping_distance_fr.pdf).

## E8. If axle weights get built, 12,000 lb is not the legal steer limit

Smart Trucking, correctly for practice, gives 12,000 lb steer / 34,000 lb
drives / 34,000 lb trailer as the target
(https://www.smart-trucking.com/axle-weights/). But the **federal single-axle
limit is 20,000 lb**; the 12,000 lb figure is a tire and manufacturer rating
in common practice, and some states permit more. Coding 12,000 as a legal
maximum would produce citations that do not exist. Use 20,000 lb as the law,
12,000 lb as the practical target the spoken advice recommends.

## E9. Detention terms are already right

`DETENTION_FREE_MIN = 120.0` and `DETENTION_PER_HOUR = 45.0` match the real
convention of a two-hour free window followed by hourly billing, and $45/hr
sits just under the $50–100/hr industry band. The 30% chance of a slow live
load also lines up with ATRI's finding that drivers were detained at 39.3%
of stops. The problem with detention is A1 (it never pays), not the numbers.

## E10. Floating gears being refused is a defensible design call

`Transmission.request_gear` grinds and refuses when `clutch < 0.8`. Real
drivers float constantly and Smart Trucking treats it as a normal skill
(https://www.smart-trucking.com/floating-gears/). But the same page
recommends new drivers double-clutch first, and the game's accessibility
brief argues against a technique that needs precise timing without visual
feedback. Listed as "right for this game" rather than "realistic" — flag it
as a deliberate divergence rather than a gap, and do not let a realism pass
quietly add it.

---

# F. Corroboration notes and what I could not verify

- **The site is thinner on numbers than its reputation suggests.** Several
  pages selected for specific figures — CSA inspection levels, commercial
  insurance premiums, semi truck repair costs, cornering and rollover
  thresholds, tailgating stopping distances, big rig specs, idling — turned
  out to be qualitative advice with no quantitative content. Where I needed
  numbers in those areas I went to the regulator or the research body
  instead, and said so above.
- **Where the site is wrong.** Its HOS page carries the pre-2020 30-minute
  break rule and an incomplete adverse-conditions exception (E1). Treat it
  as a good source for *practice and judgement* — descent technique, scaling
  procedure, what an inspector actually looks at, dock behaviour — and a
  poor one for current regulation.
- **Could not corroborate:** the exact out-of-service duration for a
  30-minute break violation (A5) — the CVSA out-of-service criteria document
  is not publicly readable, and the public summaries state only the general
  "until corrected" principle plus the specific 10-hour ELD case.
- **Regionalism to watch:** Smart Trucking is Canadian-authored and several
  of its pay examples (the owner-operator settlements, the diesel weight
  slightly over 7 lb/gal) are Canadian. I have used US figures throughout
  and flagged the one place the site's own numbers disagree with themselves
  (7.0 vs 7.2 lb/gal, B3).
- **Note for the fines branch:** the federal speed-limiter mandate was
  formally withdrawn in July 2025
  (https://www.federalregister.gov/documents/2025/07/24/2025-13928/),
  so there is no regulatory basis for a governed-speed requirement — the
  game's absence of a road-speed governor is currently *more* accurate than
  it would have been two years ago.

---

# G. Excluded — already tracked, in flight, or out of scope

Not re-reported. Verified present in `ROADMAP.md` or named in the brief:

- Fines rebalance (L142) and the curve-assist jake overuse (L136) — in flight.
- 70-hour/8-day cycle and 34-hour restart (L29, L3328).
- Adverse driving conditions +2-hour exception (L90, L92).
- Personal conveyance, the six-part slice (L48–L85); yard moves (L82).
- ELD character events: log certification, carrier edits, malfunction
  paper-log day (L90). Home terminal (L33). Local/short-haul board (L38).
- Reefer temperature and spoilage (L583, L2077).
- Runaway ramps as highway furniture and their aftermath (L1515, L1524).
- Lateral traction on curves and ramps (L1589); cornering damage to the
  tractor (L580); jake-slip and hydroplane consequences (L904).
- Chain-up areas as physical pullouts (L1596); CA R1/R2/R3 wording (L1598).
- Black-ice refreeze on clear cold mornings, steady crosswind nudging the
  trailer, seasonal daylight (all under the weather item, L3247).
- Toll sweep with real published rates and a transponder (L1125);
  interactive toll plazas (L1164).
- Trailer wear accumulation (L890); wear ceilings (L569); tow distinct from
  roadside repair (L586); crash consequence tiers (L1533).
- Truck selling/trade-in and salvage value (L897); transmission as a
  per-truck spec (L898); loans and insurance (L3958).
- Operating-cost polish (L3942), freight-market pricing and fuel surcharge
  (L3946), advanced authority realism (L3935), trailer ownership (L3939).
- "The back half of the arc is flavour text" (L488) — including the planned
  oversize/overweight-with-permits and hazmat-with-route-bans spine.
- Enforcement catch rate (L607); violation class decides the outcome
  (L2020); police phases 2–5 (L598).
- Facility placement audit / long deadheads (L2040).
- Parking availability: **not a gap.** `hos.parking_is_full` /
  `parking_full_probability` are live and consumed at
  `driving_events.py:637`. A subagent reported this as missing; it is not.
