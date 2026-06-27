# Company Driver To Owner-Operator Arc

This design keeps Freight Fate's owner-operator fantasy, but grounds the path
in a real trucking progression instead of making a risky lease-purchase deal
the main dream.

## Grounding

The realistic first step is not instant independence. A new company-path driver
starts with one of several fictional starter carriers. The carrier controls the
dispatch relationship, assigns and maintains the tractor/trailer combination,
and carries the normal carrier costs. The driver earns wages and bonuses from
each settlement, while fines and damaged-load consequences still matter.

The first owner-operator step is modeled as a leased-on owner-operator, not full
motor-carrier authority. That keeps the game focused on driving and load choice:
the player buys into a tractor position and pays operating costs, but the
carrier still anchors dispatch, trailers, authority support, settlement, and
reimbursed accessorials. Full independent authority, direct load-board play, and
fleet ownership remain later roadmap work.

The progression intentionally avoids making lease-purchase the happy path. The
FMCSA Truck Leasing Task Force exists because lease and lease-purchase
arrangements can create serious risk for drivers, and those risks are the wrong
tone for the first playable business arc. The game therefore uses a clear
buy-in and working-capital gate instead of a confusing weekly deduction trap.

Freight Fate also offers an alternate owner-operator start for players who want
that fantasy immediately. It is framed as an experienced-driver start: the
player begins leased on with an owned starter tractor, higher gross revenue,
limited working capital, partial fuel, light equipment wear, and operating
costs active from day one.

## Gameplay Model

- Company driver: listed board pay is carrier gross; settlement pays a driver
  wage/bonus. Fuel, routine repairs, roadside fuel, and carrier shop repair are
  billed to the carrier. The driver may have a regular assigned tractor, but
  does not own, switch, or upgrade tractors yet.
- Starter carrier differences: company carriers adjust realistic wage and
  dispatch factors: pay share, per-mile wage floor, stop pay, on-time bonus,
  route-length mix, deadline slack, regional tendency, and modest freight
  emphasis. They do not grant magic perks or personal truck ownership.
- Leased-on owner-operator: listed board pay is gross revenue; settlement adds
  a higher revenue multiplier, then deducts business costs: maintenance reserve,
  insurance reserve, trailer program, truck payment reserve, and settlement
  service fee. Fuel and repairs also come out of the player's cash.
  Truck purchases, switching, and upgrades unlock here because the player now
  has owned tractor responsibility.
- Trailer compatibility: cargo now maps to trailer programs. Company drivers
  use carrier-provided trailers. Leased-on owner-operators start with a dry van
  trailer program and can add reefer, flatbed, or bulk programs from the garage.
  Missing specialty programs lock matching cargo until the player adds them.
- Progression: level 5 starts owner-operator preparation, but the leased-on
  buy-in does not unlock until level 15 with 35 deliveries, reputation 80, no
  pay advance, and enough cash for a 35,000 dollar buy-in while keeping 10,000
  dollars of working capital.
- The design remains a driving career, not a fleet-management sim. It adds one
  terminal menu and settlement math; it does not add driver hiring, tax filing,
  direct broker negotiation, or full authority management.
- Level-20 owner-operators can set aside an authority prep reserve when
  their reputation, delivery count, and working capital are ready. This is a
  playable savings milestone for a future motor-carrier authority feature, not
  current independent authority.

## Career Start Choices

| Start | Mode | Practical Tradeoff |
| --- | --- | --- |
| Northstar Freight Lines | Company driver | Balanced wage plan and broad dispatch. |
| Great Lakes Training Transport | Company driver | Better short-load stop pay, more short-haul training work, and slightly more forgiving deadlines. |
| Prairie Link Regional | Company driver | Better per-mile wage floor, lower stop pay, more same-region work, and grain/bulk emphasis. |
| Summit Value Logistics | Company driver | Better percentage and on-time bonus, smaller guarantee, and more long-haul/high-value lanes. |
| Owner-operator start | Leased-on owner-operator | Starts at level 15 with owned starter equipment, 18,000 dollars working capital, partial fuel, light wear, higher gross revenue, and operating costs active. |

## 20-Level Arc

| Level | Rank | Business Meaning |
| --- | --- | --- |
| 1 | Yard Trainee | Start with a company carrier and an assigned company tractor. |
| 2 | New Hire Company Driver | Refrigerated freight unlocks. |
| 3 | Solo Company Driver | Heavy-haul freight unlocks. |
| 4 | Regional Company Driver | High-value freight unlocks. |
| 5 | Owner-Operator Apprentice | Business status starts tracking the preparation path. |
| 6 | Regional Fleet Driver | Wider regional work while still company-paid. |
| 7 | Long-Haul Company Driver | Long-haul dispatch becomes routine. |
| 8 | Trusted Freight Driver | Better specialized freight opportunities. |
| 9 | High-Value Driver | Higher-consequence freight trust. |
| 10 | Lead Company Driver | Senior company-driver status. |
| 11 | Owner-Operator Candidate | Full owner-operator checklist appears. |
| 12 | Working Capital Builder | Saving cash becomes the main milestone. |
| 13 | Tractor Buy-In Candidate | Tractor buy-in target is active. |
| 14 | Leased-On Applicant | Final reputation, delivery, and cash gate. |
| 15 | Leased-On Owner-Operator | Buy-in can unlock leased-on owner-operator economics. |
| 16 | Settled Owner-Operator | Owner-operator settlements become normal. |
| 17 | Established Owner-Operator | Higher-trust leased-on business status. |
| 18 | Equipment Planner | Trailer/equipment planning is a future hook. |
| 19 | Authority Candidate | Independent authority readiness appears. |
| 20 | Independent Operator | Current owner-operator arc is complete. |

Full independent motor-carrier authority is not implemented in this slice.
Level 20 means the player has completed the owner-operator career arc and is
ready for a later authority system, not that Freight Fate has become a fleet or
brokerage simulator.

## Authority Prep Reserve

Authority readiness is the first concrete hook toward true authority without
turning Freight Fate into a compliance sim. A leased-on owner-operator at level
20 can set aside a 12,500 dollar reserve after 60 deliveries, reputation 90, and
25,000 dollars of working capital. The reserve marks the profile as ready for a
future authority system and keeps the current game grounded: dispatch, trailers,
insurance support, and settlement still run through the leased-on carrier.

## Trailer Programs

This slice implements trailer compatibility without jumping all the way to
player-owned trailer fleets. The current trailer programs are:

| Program | Cargo Fit |
| --- | --- |
| Dry van | General, retail, parcel, automotive, electronics, packaged chemicals, and some container, farm, construction, lumber, and paper freight. |
| Reefer | Fresh food and refrigerated cargo. |
| Flatbed | Steel, machinery, construction, lumber, paper, and some container freight. |
| Bulk | Grain, farm inputs, and loose bulk materials. |

The dry van program is included for leased-on owner-operators. Reefer, flatbed,
and bulk programs are leased from the garage. They are not lease-purchase deals
and do not create weekly debt traps. Tanker freight is not implemented yet
because current chemical cargo is packaged industrial freight, not liquid bulk
tanker work.

## Follow-Up Realism Hooks

- True authority should be a later, optional step. It should cover
  motor-carrier authority, insurance filings, broker/load-board access,
  settlement or factoring timing, and more compliance overhead.
- Authority prep now has a reserve gate and save flag; the future work is
  turning that prepared state into a real authority application, insurance, and
  direct-freight gameplay loop.
- Trailer ownership should be a later authority or dealer slice. Current
  gameplay has leased-on trailer program slots and cargo fit; future work can
  add owned trailer condition, financing, tanker cargo, and trailer resale.
- Operating-cost polish should keep using recognizable owner-operator cost
  categories, but player-facing settlement text should stay concise and avoid
  dense finance jargon.
- Freight-market pricing should keep company-driver wages, leased-on gross
  revenue, and future true-authority spot or broker rates distinct.
- Lease-purchase remains a realism caveat and caution, not the default success
  path. Fleet hiring and company ownership stay separate from this driving arc.
- A future save-schema cleanup can rename internal `truck` and `owned_trucks`
  fields so legacy saves keep loading without those fields sounding like
  company-driver ownership in code.

## Sources Consulted

- FMCSA operating authority overview:
  https://www.fmcsa.dot.gov/registration/get-mc-number-authority-operate
- FMCSA insurance filing requirements:
  https://www.fmcsa.dot.gov/registration/insurance-filing-requirements
- FMCSA hours-of-service summary:
  https://www.fmcsa.dot.gov/regulations/hours-service/summary-hours-service-regulations
- FMCSA Truck Leasing Task Force:
  https://www.fmcsa.dot.gov/tltf
- ATRI operational cost research:
  https://truckingresearch.org/about-atri/atri-research/operational-costs-of-trucking/
- Bureau of Labor Statistics heavy and tractor-trailer truck driver overview:
  https://www.bls.gov/ooh/transportation-and-material-moving/heavy-and-tractor-trailer-truck-drivers.htm
- Schneider company-driver equipment overview:
  https://schneiderjobs.com/truck-driving-jobs/benefits/equipment-technology
- Schneider power-only carrier equipment split:
  https://schneider.com/carriers/power-only
- FMCSA cargo tank registration and resources:
  https://www.fmcsa.dot.gov/carrier-safety/hazardous-materials-safety/cargo-tank-registration-and-resources
- NMFTA trucking type overview:
  https://nmfta.org/resource/different-types-of-trucking-in-the-shipping-industry/
- NMFTA reefer overview:
  https://nmfta.org/resource/what-is-reefer-trucking/
- NMFTA flatbed overview:
  https://nmfta.org/resource/types-of-flatbed-trailers-how-are-they-different/
