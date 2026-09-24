# ALCAN Phase B plan — Anchorage on the continuous AK truck graph

Status: **PLAN ONLY** (this tip). No `world_data` / city / leg JSON. Phase A continuous Lower-48 → Fairbanks remains **KEEP**. Ruth cuts this plan before any Phase B data lands; owner GO after Ruth.

Parent scaffold: [`docs/alcan-corridor-scaffold-plan.md`](./alcan-corridor-scaffold-plan.md) (sequence A corridor → **B Alaska map** → C rest of Canada → D Europe).

Branch: `feat/career-2.0` only. Daytime public APIs first (Overpass, public Valhalla/OSRM, Geofabrik regional). **No overnight PBF / Valhalla bake** for this plan tip.

---

## 0. Phase A attach (KEEP — do not re-mint)

| Key / leg | Miles | Notes |
| --- | --- | --- |
| `tok_ak_us` | — | Tok; Young's Chevron stand-in (Alaska Hwy) |
| `fairbanks_ak_us` | — | Phase A terminus; Sourdough Fuel 1688 Airport Way stand-in |
| `whitehorse_yt_ca` ↔ `tok_ak_us` | **387** | Border `poker_creek_beaver_creek`, through_freight, cabotage forbidden (both ways) |
| `tok_ak_us` ↔ `fairbanks_ak_us` | **202** | Alaska Hwy / Richardson AK-2 |

Phase B hangs Anchorage off this AK tip. It does **not** reopen Canada cabotage, ferry shortcuts, or Phase C/D scope.

---

## 1. Route choice (with rationale)

### Options

| Corridor | Highways | From | To | Public Valhalla **truck** (2026-09-24, estimate) | MILEPOST / published |
| --- | --- | --- | --- | --- | --- |
| **Tok Cutoff + Glenn** | AK-1 Tok Cutoff → short Richardson link → AK-1 Glenn | `tok_ak_us` | Anchorage | **~318 mi** direct; segmented ~139 + ~138 + ~43 | ~328 mi (Tok→ANC principal route) |
| **Parks** | AK-3 Parks (shared Glenn south of Glenn–Parks interchange) | `fairbanks_ak_us` | Anchorage | **~361 mi** direct; segmented ~57 + ~58 + ~43 + ~169 + ~44 | ~358–362 mi Fairbanks↔Anchorage |

Passes / grades of note:

- **Glenn / Tok Cutoff:** Mentasta Summit (~2,434 ft) on Tok Cutoff; **Eureka Summit (~3,322 ft, Glenn MP ~129.5)** — highest point on Glenn; winter ice/glaze reported; not a seasonal closure by default (paved all-weather), but check Alaska 511.
- **Parks:** **Broad Pass (~2,409 ft)** south of Cantwell; generally milder summit than Eureka; Parks is the Denali / Interior tourist + rail-parallel freight spine between Fairbanks and Mat-Su.

### Recommendation — **both**, land **Tok Cutoff + Glenn first**

**Primary (lands first):** Tok Cutoff (AK-1) + Glenn Highway (AK-1) from `tok_ak_us` → `glennallen_ak_us` → `palmer_ak_us` → `anchorage_ak_us`.

**Secondary (lands second, after primary CI green):** Parks Highway (AK-3) from `fairbanks_ak_us` → pass-through fuel towns → `wasilla_ak_us` → `anchorage_ak_us` (shared Glenn south of the Glenn–Parks interchange).

**Rationale (one paragraph):** Anchorage-bound overland freight that already entered Alaska on the ALCAN at Tok does **not** detour to Fairbanks then south on Parks; The MILEPOST and Interior freight planning treat the **Glenn Highway / Tok Cutoff as the principal paved Tok→Anchorage connection (~328 mi)**. Fairbanks remains the ALCAN / Richardson terminus for Interior and North Slope staging; Fairbanks↔Anchorage freight uses Parks (and/or rail from Port of Alaska). Most Anchorage consumer freight arrives by **sea via Port of Alaska**, not by ALCAN tractor — Phase B still needs the continuous road filament so through-freight and AK domestic legs are honest, but Anchorage must not be sold as “the ALCAN destination.” Parks is required for a real AK highway graph (Fairbanks–Mat-Su–Anchorage) and should follow once the Tok→Anchorage filament is green. Eureka Summit is steeper/higher than Broad Pass and deserves HGV winter notes; it does not justify skipping the primary freight path.

Order locked unless Ruth flips it: **B1 Tok Cutoff/Glenn → B2 Parks**.

---

## 2. Proposed city keys

Key shape: `{name}_{region}_{country}` (e.g. `tok_ak_us`).

### B1 — Tok Cutoff + Glenn (required)

| Role | Proposed key | Approx pin | Role detail |
| --- | --- | --- | --- |
| Exists (KEEP) | `tok_ak_us` | 63.3367, −142.9856 | Phase A entry; do not re-mint |
| Junction / full node | `glennallen_ak_us` | ~62.11, −145.55 | Glenn × Richardson junction; Copper River region service hub |
| Mat-Su / pass-through→full | `palmer_ak_us` | ~61.60, −149.11 | Glenn corridor agricultural / staging node before Anchorage |
| Phase B destination / full node | `anchorage_ak_us` | ~61.22, −149.90 | Port-fed market; continuous-drive end of B1 |

Optional B1 pass-through (Ruth may cut): none required. **Do not** mint `gakona_ak_us` unless Glennallen pin honesty fails (Gakona is the Tok Cutoff / Richardson junction hamlet a few miles north of Glennallen services).

### B2 — Parks (after B1)

| Role | Proposed key | Approx pin | Role detail |
| --- | --- | --- | --- |
| Exists (KEEP) | `fairbanks_ak_us` | 64.8378, −147.7167 | Phase A terminus |
| Pass-through fuel | `nenana_ak_us` | ~64.56, −149.09 | Parks fuel / Yukon River town |
| Pass-through fuel | `healy_ak_us` | ~63.87, −148.97 | Parks / Denali gateway; small truck lot |
| Pass-through fuel | `cantwell_ak_us` | ~63.39, −148.95 | Parks × Denali Hwy; Broad Pass approach |
| Mat-Su / full or strong pass-through | `wasilla_ak_us` | ~61.58, −149.44 | Parks corridor; near Glenn–Parks interchange |
| Exists after B1 | `anchorage_ak_us` | — | Shared destination |

`healy_ak_us` may stay a thin fuel pin (Fisher Fuel ~3 truck spaces) rather than a career skyline — Ruth decides full vs pass-through.

### Explicitly not Phase B cities

- Haines / Skagway / any ferry POE as drive nodes
- Kenai / Soldotna / Homer / Seward / Whittier (peninsula / tunnel) unless Ruth expands scope
- Prudhoe Bay / Deadhorse / Dalton Hwy
- Valdez (Richardson south) — separate filament, not required to join Anchorage from ALCAN
- Tourism lodges as cities (Eureka Lodge, Sheep Mountain Lodge, etc.)

---

## 3. Ordered leg list (estimates)

Direction shown Anchorage-bound; expect matching reverse edges when data lands. Miles are **estimates** from public Valhalla truck costing (`valhalla1.openstreetmap.de`, loaded-semi options, 2026-09-24) unless noted. Round to whole miles at data tip (±5 mi band, Phase A practice). Auto profile matched truck mileage on these corridors in the same probe (no Blaine-style truck detour observed).

### B1 — Tok Cutoff + Glenn (lands first)

| # | Leg | Est. mi | Highway | Source |
| --- | --- | --- | --- | --- |
| 1 | `tok_ak_us` → `glennallen_ak_us` | **~139** | Tok Cutoff AK-1 (+ short Richardson to Glennallen services) | Public Valhalla truck 2026-09-24 |
| 2 | `glennallen_ak_us` → `palmer_ak_us` | **~138** | Glenn Hwy AK-1 via Eureka Summit | Public Valhalla truck 2026-09-24 |
| 3 | `palmer_ak_us` → `anchorage_ak_us` | **~43** | Glenn Hwy AK-1 | Public Valhalla truck 2026-09-24 |
| — | `tok_ak_us` → `anchorage_ak_us` (checksum) | **~318** | Combined | Public Valhalla truck; MILEPOST ~328 |

No Tok→Anchorage skip that omits Glennallen. No Fairbanks detour on B1.

### B2 — Parks (lands second)

| # | Leg | Est. mi | Highway | Source |
| --- | --- | --- | --- | --- |
| 1 | `fairbanks_ak_us` → `nenana_ak_us` | **~57** | Parks AK-3 | Public Valhalla truck 2026-09-24 |
| 2 | `nenana_ak_us` → `healy_ak_us` | **~58** | Parks AK-3 | Public Valhalla truck 2026-09-24 |
| 3 | `healy_ak_us` → `cantwell_ak_us` | **~43** | Parks AK-3 | Public Valhalla truck 2026-09-24 |
| 4 | `cantwell_ak_us` → `wasilla_ak_us` | **~169** | Parks AK-3 via Broad Pass | Public Valhalla truck 2026-09-24 |
| 5 | `wasilla_ak_us` → `anchorage_ak_us` | **~44** | Parks → Glenn–Parks interchange → Glenn AK-1 | Public Valhalla truck 2026-09-24 |
| — | `fairbanks_ak_us` → `anchorage_ak_us` (checksum) | **~361** | Combined | Public Valhalla truck |

Ruth may collapse Nenana/Healy/Cantwell into fewer pins if fuel honesty still holds; do **not** invent short-hop miles.

Cross-link (optional later, not required for B1 GO): `palmer_ak_us` ↔ `wasilla_ak_us` short Mat-Su connector — only if both cities exist and a real highway path is densified; not a teleport.

---

## 4. Truck stops / parking (real diesel + truck parking only)

Prefer `parking` / `travel_center`-class location types for public lots — **not** `company_yard` (carry soft type debt from Phase A; fix on new pins). Tourism lodges are on the kill list even when AllStays lists “truck parking.”

### B1 corridor candidates

| Area | Candidate | Notes (capacity from public directories; verify at data tip) | Verdict |
| --- | --- | --- | --- |
| Tok (exists) | Young's Chevron (Alaska Hwy & E 4th) | ~25 truck spaces; diesel; Phase A pin KEEP | **KEEP** |
| Glennallen | **Hub of Alaska** (Glenn @ Richardson / ~MP 189 Glenn) | ~20–25 truck spaces; diesel; 24h listings | **Primary Glennallen pin** |
| Glennallen | Glennallen Fuel & Service (~187 Glenn Hwy) | ~10 truck spaces; diesel | Alternate / second lot OK |
| Tok Cutoff mid | Mentasta Lodge | Lodging / tourism first; do not treat as tractor stop | **REJECT** |
| Glenn mid | Eureka Lodge / Sheep Mountain Lodge / Grand View | Tourism / RV | **REJECT** |
| Palmer | Chevron on Glenn (~MP 42 class listings) | ~18 truck spaces claimed in secondary directories — **verify via Overpass/OSM + site honesty before pin** | Candidate |
| Anchorage | **Essential One** (9250 King St) — Petro 49 / Shoreside | High-flow diesel, cardlock, DEF; AllStays ~**3** truck spaces in dirt lot | **Candidate with capacity honesty debt** |
| Anchorage | Many Holiday / in-town pumps | Often **no** tractor parking | Do not pin as truck stops |

Anchorage honest parking is thin in public truck-stop directories. Data tip must re-verify (Overpass `amenity=parking`+`hgv`, operator sites, daytime street imagery). Do not invent a 40-space Tesoro lot without a primary source.

### B2 corridor candidates

| Area | Candidate | Notes | Verdict |
| --- | --- | --- | --- |
| Nenana | A-Frame SVC / Parks Hwy fuel | Diesel claimed; **truck parking capacity unverified** | Fuel pin only if parking/diesel confirmed |
| Healy | Fisher Fuel (Parks MM ~249.5) | Diesel; AllStays ~**3** truck spaces | Thin pass-through OK |
| Cantwell | Vitus / Cantwell Food Mart (Parks MM ~210) | Diesel + on-site parking; capacity TBD | Candidate fuel pin |
| Wasilla / Big Lake | Holiday / Three Bears Travel Center / Fishers Fuel (Big Lake) | Secondary directories claim ~25 spaces at Holiday Parks Hwy and Fishers Big Lake — **verify before pin** | Prefer verified travel_center |
| Wasilla | Tourism / RV-only parks | — | **REJECT** |

---

## 5. HGV notes (Alaska)

- **Default CMV speed (13 AAC 03.275):** commercial motor vehicles default to **55 mph** on roadways unless a different limit is posted under 13 AAC 03.280. Rural NHS segments of Parks / Glenn / Richardson / Alaska Hwy may post **65 mph** where signed — use **posted**, not assumed 65, in speed contexts. Prefer `hgv:true` contexts on AK NHS legs when densifying.
- **Size/weight (17 AAC 25):** typical legal envelope includes 53 ft cargo unit / combination rules per MSCVC; overweight/oversize by permit. Overweight permits may impose lower max speeds (e.g. 45→25 mph bands by overload %).
- **Spring breakup:** seasonal axle-load restrictions (often 85% / 75% / 50% of legal) on Northern and Central Region routes including Tok Cutoff, Glenn (selected MPs), Parks approaches, and local Glennallen/Tok roads — see DOT&PF MSCVC weight-restriction bulletins (e.g. Northern Region notices into 2026). Model as named honesty / seasonal modifier later; do not silently ignore in career copy.
- **Chains / traction:** follow posted / 511 / trooper direction; Eureka Summit and Mentasta Summit ice glaze are real winter hazards (not automatic seasonal closures).
- **Steep / summit grades:** Eureka Summit (Glenn) primary concern for B1; Mentasta Summit on Tok Cutoff; Broad Pass (Parks) milder for B2. Atigun Pass (Dalton) is **out of scope**.
- **Public Valhalla truck vs auto (2026-09-24 probe):** Tok→ANC and Fairbanks→ANC truck and auto profiles returned **matching** mileages on these corridors (unlike Blaine POE Phase A debt). Still densify with **truck** costing at data tip; re-check if OSM truck restrictions appear.
- **Routing APIs:** prefer public Valhalla truck; OSRM car as cross-check only. Overpass for fuel/parking tags. AKDOT&PF 511 + MSCVC for restrictions — not as geometry source.

---

## 6. Honesty debts

### Carried from Phase A

1. US HOS through-freight clock (not Canadian law).
2. CA truck caps unresearched on Hwy 15 / ALCAN CA segments.
3. Blaine cross-border HGV refine still open.
4. No CAD purse / FX.
5. Border gameplay stub only (`border_crossing` data).
6. Stand-in markets on corridor pass-throughs.
7. Soft location-type debt (`company_yard` where `parking` / `travel_center` fits).

### New Phase B debts

1. **Anchorage is sea-fed:** Port of Alaska dominates inbound consumer freight; ALCAN through-freight is secondary. Career copy / market sizing must not imply Anchorage “is” the ALCAN destination.
2. **Anchorage tractor parking scarcity:** public directories show few high-capacity truck stops inside Anchorage; Essential One ~3 spaces. Pin honesty may need port-adjacent / industrial lots researched at data tip.
3. **Ferry later:** Haines / Skagway remain ferry — never continuous-drive substitutes for ALCAN or Phase B.
4. **Kenai / Seward / Whittier out of scope** unless Ruth expands (Whittier tunnel / ferry adjacency is a footgun).
5. **Dalton / Prudhoe out of scope** for this phase.
6. **Spring breakup not simulated** yet — name it; do not fake year-round legal GVW on restricted weeks.
7. **Parks mid-corridor thin lots:** Healy/Cantwell/Nenana parking capacity poorly documented — fuel pins may be thinner than Lower-48 travel centers.
8. **Valdez / Richardson south** not required for Anchorage join — do not sneak Valdez in as “almost Anchorage.”

---

## 7. Out of scope / kill list

- Ferry-as-drive (Haines, Skagway, any AMHS hop labeled as highway miles)
- Teleport Lower 48 → Anchorage or Tok → Anchorage skip of Glennallen
- Short-hop / straight-line / guessed miles
- Cabotage fantasy inside Canada (unchanged)
- Tourism lodges as tractor stops (Mentasta Lodge, Eureka Lodge, Sheep Mountain, etc.)
- Full Canada board (Phase C)
- Europe (#195) (Phase D)
- Dalton Hwy / Deadhorse / Prudhoe
- Kenai Peninsula / Seward / Whittier unless separately argued and Ruth-cut
- Overnight PBF / Valhalla tile bake for this plan tip
- Any `world_data` / `world_source` city or leg edits in the plan tip

---

## 8. GO gates

1. **Ruth cuts this plan** (route order B1 then B2; city keys; kill list; parking honesty).
2. **Owner GO** after Ruth.
3. **First data tip = B1 only:** `glennallen_ak_us`, `palmer_ak_us`, `anchorage_ak_us` + three legs both directions; public Valhalla truck densify; parking/travel_center types; CI green.
4. **Second data tip = B2 Parks** only after B1 KEEP — Nenana/Healy/Cantwell/Wasilla + Parks legs.
5. Still **no** rest-of-Canada bulk, no ferry nodes, no Dalton.

Ops: daytime public Overpass / Valhalla / regional Geofabrik only. Escalate to overnight bake only if APIs fail honesty — and ask before any overnight machine leave-on.

---

## 9. Suggested verification checklist (data tip, not this tip)

- [ ] Re-run Valhalla truck per leg; store paid miles + shape
- [ ] Overpass confirm diesel + HGV parking tags (or operator primary source) for each pin
- [ ] Reject any lodge-only amenity
- [ ] AK `hgv` speed contexts from posted/statutory defaults
- [ ] Lat ceiling / lon floor already raised for Fairbanks; confirm Anchorage (~61.2°N, ~−149.9°) inside integrity bounds
- [ ] Both directions authored; no CA cabotage unlock
- [ ] Changelog / `[skip changelog]` policy followed for docs vs data tips
