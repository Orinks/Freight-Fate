# ALCAN corridor scaffold plan (through-freight only)

Status: **Phase A first city/leg tip landed** on `feat/career-2.0` (Bellingham → Blaine → Surrey). Ruth geometry cut next.
Still no Anchorage, no full Canada board, no Dawson→Tok short-hop.

Owner sequence (locked): **(1) this ALCAN corridor → (2) map Alaska → (3) rest of Canada → (4) Europe (#195).**
Do not jump ahead. Ruth verifies every step.

**Locked Phase A routing decisions:** the primary POE is **Blaine Pacific Highway**; **Sumas is an alternate only if the POE decision flips**. With Blaine, the BC entry is `surrey_bc_ca` or another **verified tractor-parking node on Hwy 99**. `abbotsford_bc_ca` is allowed only when the POE is Sumas. The first legs must retain **real routed ALCAN highway mileage**, not compressed short-hop proxies.

Deferred mentions already in-tree:
- `docs/highway-spider-methodology.md` §1 Phase 3 — Canadian corridors deferred; points here.
- `data/spider/gap-fill/HANDOFF.md` — U.S. coverage first; Canada (Alcan program) unblocks after, “gated anyway on the 96 GB RAM arrival for the world extract.”
- `docs/gap-analyzer-brief.md` — do not rank Canada/Mexico off-graph dreams.
- `docs/map-enrichment-recipe.md` — “Taking this off the US grid” (jurisdiction caps / canonical units).
- `docs/roadmap-details.md` — International expansion bullet (research Canada/UK); sequence below supersedes any “full Canada next” reading.

---

## 0. Phased sequence (do not reorder)

| Phase | Scope | This tip? |
| --- | --- | --- |
| **A** | Minimal Canada ALCAN corridor that puts Alaska on the continuous truck graph (through-freight only; no Canada domestic cabotage) | **Yes — scaffold/plan only** |
| **B** | Map Alaska itself (beyond Tok/Fairbanks as mere endpoints — real AK highway graph / cities). Anchorage only when the AK highway graph reaches it continuously. Haines/Skagway = ferry later, never continuous drive. | Named next after A lands |
| **C** | Rest of Canada (full board) | After B |
| **D** | Europe (#195) | After C |

Phase A attaches to the existing Lower-48 graph at **Bellingham / I-5**. It does **not** open a Canada domestic career board.

---

## 1. Inventory (feat/career-2.0 tip at plan time)

Verified on branch against `data/world_data/` (tip used for this plan):

- **Graph:** US-only. `data/world_data/index.json` lists a single country (`US`). **624** cities in `data/world_data/us/cities.json`. **1283** legs across `data/world_data/us/legs/*.json` (no `AK.json`; research brief rounded ≈1290).
- **Northern I-5 tip:** `bellingham_wa_us` exists (also `seattle_wa_us`, `everett_wa_us`, etc.). WA legs already include Bellingham↔Everett on I-5.
- **Missing (all corridor targets):** no Blaine/Sumas nodes; no Dawson Creek / Fort Nelson / Watson Lake / Whitehorse / Tok / Fairbanks / Anchorage keys; no BC/YT/AK cities; no Canada country pack.
- **`data/world_data/geo.json`:** US state table includes `AK` as a name only — no cities/legs behind it.
- **Attach point:** corridor must hang off **existing Bellingham / I-5**, not a teleport from Seattle or a new Lower-48 stub that skips the graph.

---

## 2. Proposed city keys (Phase A)

Key shape matches current slug rule: `{name}_{region}_{country}` (e.g. `bellingham_wa_us`).

### Required stops (must be real cities on the continuous drive)

| Role | Proposed key | Notes |
| --- | --- | --- |
| US attach (exists) | `bellingham_wa_us` | Do not re-mint |
| BC entry service node | `surrey_bc_ca` (Blaine primary) | With Blaine Pacific Highway, use Surrey or another **verified tractor-parking node on Hwy 99**; not a tourism lodge. `abbotsford_bc_ca` is allowed only if the POE flips to Sumas. **Ruth locks key with POE.** |
| Mile 0 ALCAN | `dawson_creek_bc_ca` | Required |
| ALCAN BC | `fort_nelson_bc_ca` | Required |
| ALCAN YT | `watson_lake_yt_ca` | Required |
| ALCAN YT | `whitehorse_yt_ca` | Required |
| AK entry | `tok_ak_us` | Required |
| Main AK node (Phase A end) | `fairbanks_ak_us` | Required; Phase A terminus |

### Locked primary POE

- **Primary:** Pacific Highway **Blaine**.
- **Alternate only:** **Sumas**; use it only if the POE decision explicitly flips. Only then is `abbotsford_bc_ca` an acceptable BC entry service node.
- Model the crossing as **border data on the cross-border leg(s)**, not as a fake “teleport city.” Optional US-side service pin only if needed for fuel/parking honesty; do not invent a career city just to name the booth.

### Allowed pass-through fuel/parking towns (no full careers)

Honesty on Blaine→Dawson Creek may add checkpoints / service pins without dispatch careers, e.g.:

- `prince_george_bc_ca`
- `fort_st_john_bc_ca`

(and other on-route fuel/parking towns Ruth accepts). Pass-through ≠ cabotage board.

### Explicitly not Phase A cities

- **Anchorage** — Phase B only, if/when continuous AK highway graph reaches it.
- Haines / Skagway — ferry later; never a continuous-drive substitute for ALCAN.
- Interior BC/Prairie/Ontario cities, Mexico, Europe — out of scope.

---

## 3. Proposed ordered leg list (corridor)

Direction shown northbound; expect matching southbound edges when the graph lands.

1. `bellingham_wa_us` → **(Blaine Pacific Hwy POE)** → `surrey_bc_ca` (or a verified Hwy 99 tractor-parking node; `abbotsford_bc_ca` only if POE flips to Sumas)
2. BC entry → …optional pass-throughs (Prince George, Fort St. John, …)… → `dawson_creek_bc_ca` using the real routed highway mileage
3. `dawson_creek_bc_ca` → `fort_nelson_bc_ca` (Alaska Hwy)
4. `fort_nelson_bc_ca` → `watson_lake_yt_ca`
5. `watson_lake_yt_ca` → `whitehorse_yt_ca`
6. `whitehorse_yt_ca` → **(Poker Creek AK / Beaver Creek YT border)** → `tok_ak_us`
7. `tok_ak_us` → `fairbanks_ak_us`

No Seattle→Fairbanks skip. No short-hop “ALCAN” that omits Mile 0 / Whitehorse / the Poker Creek–Beaver Creek crossing, and no compressed `dawson_creek_bc_ca` → `tok_ak_us` proxy. The first legs must preserve verified, routed ALCAN road mileage through each corridor segment; do not substitute straight-line, guessed, or short-hop distances.

---

## 4. Border-crossing data shape (proposal)

Goal: model Blaine/Sumas and Poker Creek/Beaver Creek **without** Canada domestic cabotage.

Suggested leg (or leg-segment) metadata — names indicative, not schema freeze:

```json
"border_crossing": {
  "id": "blaine_pacific_highway",
  "from_country": "US",
  "to_country": "CA",
  "ports": ["blaine_pacific_highway"],
  "mode": "through_freight",
  "cabotage": "forbidden"
}
```

Rules of thumb for the cut:

- Crossing is **on the continuous path** (delay / inspection beat later); it is not a menu teleport.
- **Through-freight only** in Phase A: loads that enter Canada must be international through movements (Lower 48 ↔ Alaska via the corridor), not CA domestic pickup/delivery for a US carrier fantasy board.
- Second crossing on the same corridor: `poker_creek_beaver_creek` with `from_country: CA`, `to_country: US`.
- Do not mint full career economies on Canadian pass-through towns in Phase A.

Exact schema lands with the first city/leg PR **after** Ruth cuts this plan — not in this tip.

---

## 5. Multi-country profile blockers (exists vs missing)

| Area | Exists today | Missing for Phase A honesty |
| --- | --- | --- |
| Country packs | `index.json` → US only | CA pack path; AK cities under US (or explicit AK handling); geo names for BC/YT |
| Units | Player `imperial_units` toggle; sim stores miles | Jurisdiction truck caps beyond US state mph table; `docs/map-enrichment-recipe.md` already says non-US needs jurisdiction keys + canonical km/h defaults |
| Currency | USD-centric money / speech | CAD purse (and FX or dual purse) is deferred; it is not required to *drive* the corridor, but pay/fuel speech will lie if ignored — flag for follow-up |
| HOS | FMCSA-style clock | Canadian HOS / south-of-60 vs north rules not modeled; Phase A may use the US through-freight clock only as a **named HOS honesty debt** accepted for this tip. Never silently label it Canadian law or imply Canadian compliance. |
| Borders | State-line cues | International border mechanic still **deferred**; need at least data hooks (above) before pretending clearance gameplay |
| Map extracts | US Geofabrik / self-hosted ORS-Overpass for US | **Need BC / YT / AK extracts** — US extract alone cannot bake honest ALCAN geometry |
| HANDOFF / extract gate | `data/spider/gap-fill/HANDOFF.md` cites **96 GB RAM world extract** as a Canada unblock | **Soft for Phase A** if public Overpass / routing / Geofabrik *regional* downloads already cover the ALCAN filament honestly. Escalate to a full PBF / Valhalla-class bake only when APIs fail honesty — see §5.1 |


### 5.1 Extract / bake ops policy (owner)

For ALCAN / CA / AK world-data work **after Ruth cuts this plan**:

1. **Prefer public APIs first.** Overpass, public routing, and Geofabrik *regional* downloads as needed. Slow is fine; stay honest. Corridor-scale Overpass / API work can run on Chelsea’s Linux box.
2. **Full PBF bake or Valhalla-class jobs** (only when APIs cannot keep the filament honest): run on **Josh (Windows)**, with large OSM on **E: (SanDisk SSD)** — not C: or D:. **Ask Chelsea before starting anything that needs Josh left awake overnight** (that machine often sleeps).
3. **Do not assume Chelsea’s Linux box can hold Valhalla tiles.** It has 16 GB RAM and no swap; Valhalla-class tile builds OOM there.

**96 GB HANDOFF gate:** soft if APIs cover the ALCAN filament. Only escalate to Josh for bulk extract when APIs fail honesty. Still: **plan tip → Ruth cut → then data.** No `world_data` bulk in this tip.

---

## 6. Out of scope / dishonest traps (Ruth will reject)

- Teleport / skip-Canada Lower 48 → Alaska.
- Short-hop “ALCAN” missing Dawson Creek, Whitehorse, or Poker Creek/Beaver Creek.
- Full Canada dispatch board in Phase A.
- US cabotage fantasy inside Canada (domestic CA loads for the US through-freight slice).
- Tourism lodges as tractor stops without truck parking.
- Alaska cities with no continuous highway path (including Anchorage before Phase B graph reaches it).
- Ferry-as-drive via Haines/Skagway.
- Europe (#195) or rest-of-Canada bulk before Alaska map phase.
- Silent use of car-speed limits / mph-only tables on CA/YT statutory truck caps.
- CAD purse / FX work, deep border gameplay, and other full Canada or Alaska economy work are deferred from this plan tip.

---

## 7. GO gates (before first city/leg PR)

1. Ruth cuts this plan (Blaine Pacific Highway primary; Sumas only if the POE flips; Surrey/Hwy 99 BC entry key; pass-through list).
2. Confirm extract path: BC/YT/AK coverage via public APIs / regional Geofabrik first (see §5.1); treat 96 GB HANDOFF gate as soft unless APIs fail honesty.
3. Name the temporary HOS honesty debt (US through-freight clock only) and keep CAD purse, deep border gameplay, and full-country expansion deferred.
4. Only then: first PR adds country/geo hooks + corridor cities/legs — **still no rest-of-Canada bulk.**

After Phase A lands continuously to Fairbanks: **Phase B = Alaska expansion** (named next), then Phase C rest of Canada, then Phase D Europe.


---

## 8. First tip landed (Bellingham → Blaine → Surrey)

Landed on `feat/career-2.0` after Chelsea GO (plan locks kept: Blaine primary, Surrey BC entry, no Abbotsford).

| Key / leg | Miles | Notes |
| --- | --- | --- |
| `bellingham_wa_us` | (exists) | US attach; unchanged |
| `blaine_wa_us` | — | New US stand-in service pin near Pacific Highway POE |
| `surrey_bc_ca` | — | New CA stand-in; pin at City of Surrey truck parking **17768 96 Avenue** (Hwy 15 / Pacific Highway corridor) |
| `bellingham_wa_us` → `blaine_wa_us` | **22** | I-5; public OSRM driving geometry 2026-09-22 |
| `blaine_wa_us` → `surrey_bc_ca` | **16** | Hwy 15 / Pacific Highway via Blaine POE; `border_crossing` stub (`through_freight`, cabotage forbidden) |

### Mileage / geometry source

- Route distance + `route_points`: public OSRM (`router.project-osrm.org`) over OSM, development-time 2026-09-22.
- Elevation: Open-Meteo elevation API.
- **Not** a truck-class Valhalla/ORS HGV bake. Named debt for Ruth cut.

### Named honesty debts (this tip)

1. **HOS:** US through-freight clock only — never labeled as Canadian HOS / south-of-60 compliance.
2. **Units / speed:** CA statutory truck caps not researched; tip speed_limits are coarse placeholders.
3. **Currency:** no CAD purse / FX.
4. **Border gameplay:** data stub only (`border_crossing` on the Blaine→Surrey leg); no inspection beat / clearance sim.
5. **HGV geometry:** car-profile OSRM + coarse grades until Ruth cuts truck geometry / regional extract bake.
6. **Stand-in markets:** Blaine and Surrey are stand-in yards (no surveyed CA career board / cabotage).

### Blockers for next slice (toward Dawson Creek)

- Extend BC pass-throughs (`prince_george_bc_ca`, `fort_st_john_bc_ca`) + `dawson_creek_bc_ca` with **real** routed miles (no short-hop).
- City lat test currently asserts `lat < 50.0` (`data_world.rs`) — blocks northern BC / YT / AK keys until raised.
- Prefer public Overpass / regional Geofabrik before Josh overnight PBF/Valhalla (ask Chelsea).
- Still no Anchorage (Phase B).
