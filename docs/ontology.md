# Freight Fate ontology

What kinds of things exist in Freight Fate, what the code calls them, and --
the part that reaches players -- what the game *says* out loud for each one.

Two audiences. A contributor adding a feature should be able to find out
whether the concept already exists under another name. A contributor writing
spoken text should be able to find out which word the game already uses, so a
screen reader user does not hear three nouns for one thing.

This is a contributor document. Nothing here is player-facing, so changes to it
alone take `[skip changelog]`.

## Two tiers

Freight Fate's entities divide into a portable model layer and a game layer.

**The portable layer** -- `models/` and most of `sim/` -- describes the world,
the freight, the driver and the equipment. None of it should know that
Freight Fate is a Pygame program: no pygame import, no audio backend, no
speech. That rule is not stylistic. It is what keeps the model layer testable
headless and reusable, and it is enforced by convention today, so watch for it
in review.

**The game layer** -- `states/`, the audio and speech stack, saves, online
services -- is Freight Fate specific and always will be.

The portable layer's vocabulary is documented alongside the code that owns it.
This file catalogues the game layer, and then the spoken vocabulary for both.

## Game-layer entities

### The save

| Concept | Class | Module |
| --- | --- | --- |
| Profile | `Profile` | `models/profile.py` |
| Truck condition | `TruckCondition` | `models/trucks.py` |
| Duty log | `DutyLog` | `sim/hos.py` |
| Loyalty account | `LoyaltyAccount` | `models/loyalty.py` |
| Radio favorite (spoken "favorites", a saved station) | `RadioState.favorite_ids` | `radio.py` |
| Save migration | `migrate_save_data`, `SAVE_VERSION` | `models/save_migration.py` |
| Career from an earlier version (the 1.9 cutover gate; never "legacy" in spoken text) | `created_line`, `LegacyCareerError` | `models/profile.py` |
| Integrity signature | `SIGNATURE_FIELD`, `ProfileIntegrityError` | `models/profile.py` |
| Profile invariants | -- | `profile_invariants.py`, `profile_integrity_invariants.py` |

`Profile` is the root of everything persisted. It *holds* a `Career`, a
`Market`, an `HosClock`, a `DutyLog`, a `LoyaltyAccount`, per-truck
`TruckCondition` records, the business standing (status, carrier, start mode,
authority readiness), owned and programme trailers, active buffs, the money,
the in-game clock, the achievement list, and an `active_trip` snapshot. It is
the one object whose shape is a compatibility contract in three directions at
once: older saves, the cloud validator, and the integrity signature. Add fields
with defaults; never reorder or repurpose.

The business fields are the ones to be most careful with, because they are read
by the cloud validator as well as by the game. The allow-list there is a
superset and the required set is only what the checks actually read -- exact
field matching rejects both older and newer builds.

### Carrier and equipment

| Concept | Class | Module |
| --- | --- | --- |
| Fleet tier | `FleetTier` | `models/carrier_fleet.py` |
| Trailer unit | `TrailerUnit` | `models/trailer_yard.py` |
| Pickup plan | `PickupPlan` | `models/trailer_yard.py` |
| Delivery plan | `DeliveryPlan` | `models/trailer_yard.py` |

A `FleetTier` is what a carrier *assigns* at a level band: a company driver
does not choose a tractor, they are given one. An owner-operator owns theirs.
The same `truck` field on the profile means "assigned tractor" or "active owned
tractor" depending on business status, which is worth remembering before
writing any sentence about "your truck".

`TruckCondition` is per-truck persistent state -- fuel, damage, tire wear,
grime -- keyed by catalog key. It is deliberately *not* portable: condition
belongs to the truck you own in this game, not to the driver.

### The live drive

| Concept | Class | Module |
| --- | --- | --- |
| Trip | `Trip` | `sim/trip.py` |
| Route helpers | -- | `sim/trip_route_helpers.py` |
| Road events | `TripRoadEventMixin` | `sim/trip_road_events.py` |
| Traffic on the trip | `TripTrafficMixin` | `sim/trip_traffic.py` |
| Lane keeping | `LaneKeeping` | `sim/lane.py` |
| Driving mode tuning | `DrivingModeTuning` | `sim/driving_modes.py` |
| Pedal latch | `PedalLatch` | `sim/pedal_latch.py` |
| Planned rest-stop stopping assistance | `selected_stop_assist` | `settings.py`, `states/driving_events.py` |
| Traffic vehicle | `TrafficVehicle`, `TrafficSituation`, `TrafficManager` | `sim/traffic_manager.py` |
| Live traffic | `TrafficEvent`, `TrafficData`, `RealTrafficProvider` | `sim/real_traffic.py` |
| Truck parking | `TruckParkingLocation`, `ParkingData`, `TruckParkingProvider` | `sim/truck_parking.py` |
| Time zone | `TimeZone` | `sim/timezones.py` |
| Live weather | `RealWeatherProvider` | `sim/real_weather.py` |

Two kinds of traffic exist and they are not the same concept. `TrafficManager`
simulates the vehicles around the truck right now -- the ones a player hears
and reacts to. `RealTrafficProvider` fetches real-world incident data for the
route ahead. A sentence about "traffic" should make clear which one it means.

Three providers -- weather, traffic and parking -- reach the network. All of
them must degrade to the baked data silently; nothing in the drive may block on
one.

`Trip` is the binding entity: it joins a driver, a truck, a job and a route
into one moving thing, and it owns the clock. Everything the player hears while
driving is a projection of a `Trip`. Game hours are absolute Eastern; local
time is a view, via `Trip.local_hour`.

### Player-facing systems

| Concept | Class | Module |
| --- | --- | --- |
| Achievement | `Achievement`, `AchievementAward` | `achievements.py` |
| Achievement category | `AchievementCategory` | `achievements.py` |
| Message | `Message`, `MessageCategory`, `MessageLog` | `message_log.py` |
| Engine voice | `EngineVoice`, `EngineReading` | `engine_audio.py` |
| Settings | -- | `settings.py` |
| Speech | -- | `speech.py` |
| States | `State` and subclasses | `states/` |
| Playtest levers | -- | `playtest_levers.py` |

### Roadside colour

Curated flavour data. It has no mechanical effect except where noted, but it is
player-facing text and therefore bound by the vocabulary rules below.

| Concept | Class or catalogue | Module |
| --- | --- | --- |
| Buff | `Buff`, `BUFF_CATALOG` | `data/buffs.py` |
| Brand | `Brand`, `BRANDS` | `data/amenities.py` |
| Billboard | `CORRIDOR_BILLBOARDS` and the roadside sets | `data/billboards.py` |
| Curve | `CurveRecord`, `RouteCurve` | `data/curves.py` |
| Welcome sign | `WELCOME_SIGNS` | `data/state_welcome.py` |

A **buff** is a purchasable consumable -- a shower, a meal, an oil service --
that changes a fatigue, engine or tire accrual rate for a time or for a trip.
Curves are the exception to "no mechanical effect": a `RouteCurve` carries an
advisory speed, and hairpins, sharp and moderate bands have real limits.

### Online

| Concept | Class | Module |
| --- | --- | --- |
| Online identity | `OnlineIdentity`, `OnlinePresence` | `online_presence.py` |
| Journal outbox | `JournalOutbox`, `OutboxItem` | `online_journal.py` |
| Cloud saves | `CloudSaves`, `SyncState` | `cloud_saves.py`, `cloud_save_integrity.py` |

None of these are part of the world model. They project a career or a live trip
outward; nothing in the simulation may depend on them, and every one of them
has to degrade silently when offline.

### The data pipeline

Not classes, but part of the ontology, because the shape is load-bearing:

- Tools edit `src/freight_fate/data/world_source/`, never directly: go through
  `tools/world_source.py`, where `load_world()` returns the whole world as one
  dict and `save_world(data)` writes it back as per-state shards.
- The game loads the indexed `src/freight_fate/data/world_data/` tree.
- `tools/index_world.py` regenerates the index; `--check` verifies the two are
  in sync, and CI and tests expect that.

Both trees shard by the state a leg starts in (`legs/TX.json`), so a one-leg
edit is a small reviewable diff rather than a sixty-megabyte blob. There is no
automatic sync: a source edit that is not re-indexed is a change the game will
never see.

## Spoken vocabulary

The canonical player-facing noun for each concept. This is an accessibility
contract, not a style preference: a screen reader user builds a mental model
from the words, and synonyms cost them a re-read.

| Concept | Say | Avoid | Internal name |
| --- | --- | --- | --- |
| The haul contract | job | gig, run, assignment | `Job` |
| The freight itself | cargo, the load | payload, goods | `CargoType`, `Job.cargo` |
| The board of offers | dispatch board | job list, load board | `JobBoard` |
| The vehicle | truck | rig (except as noted) | `TruckModel` |
| One city-to-city stretch | leg | segment, hop | `Leg` |
| The real highway a leg follows | corridor | -- | -- |
| One drive, start to finish | run | trip, haul | `Trip` |
| A truck stop or service POI | stop | POI, waypoint | `Stop`, `RoadStop` |
| The level band | rank | tier, grade | `CareerRank` |
| A group of related achievements | category | group, section, tab | `AchievementCategory` |
| A license add-on | endorsement | certification, licence | `ENDORSEMENT_LEVELS` |
| A purchasable consumable | its own name: "shower", "energy drink" | buff, item, power-up | `Buff` |
| The tractor a carrier gave you | your assigned truck | your truck (when leased) | `FleetTier` |
| Vehicles around you now | traffic | NPCs, cars | `TrafficManager` |
| Incidents reported ahead | delays, road reports | traffic (unqualified) | `RealTrafficProvider` |
| A parking space at a stop | parking | slot, spot | `TruckParkingLocation` |
| The short code a player reads and types into a browser to connect a computer | activation code | user code, device code, pairing code | `Activation.user_code` |
| The retarder | engine brake; "jake" in short control feedback ("Jake on, stage two") | retarder | `TruckState.engine_brake_stage` |
| A stretch of road where a town bans the engine brake | no engine brake zone | jake brake zone, engine brake restriction, quiet zone | `Trip.engine_brake_ban_at` |
| The facility entrance where a drive ends | facility gate; "gate" in short cues | entrance (as the noun for the thing), dock gate | `_handle_arrival_gate` |
| The highway exit for the delivery | destination exit | final exit, last exit, your exit | `_destination_exit_stop` |
| The loop-back after missing the destination exit or the facility gate | safe turnaround | U-turn, turnaround point, loop | `_handle_missed_destination_exit`, `_handle_missed_facility_gate` |
| The fine for engine braking in one | engine brake citation | jake ticket, noise fine | `EngineBrakeZoneMixin._fine_engine_braking` |
| The first damage band: the engine holds power back | reduced power | derate, band two, power loss | `DAMAGE_BAND_REDUCED` |
| The deep damage band: reduced power plus a road-speed cap | limp mode | limp-home, speed governor, safe mode | `DAMAGE_BAND_LIMP` |
| Damage past the point where the truck may be driven | out of service | broken down, totaled, disabled, dead truck | `TruckState.out_of_service` |
| The carrier taking a company tractor off the road | dispatch grounds it, grounded | benched, red-tagged, impounded | `_carrier_grounds_the_tractor` |
| The tractor a grounded company driver is moved into | yard spare | loaner, replacement truck, backup rig | `_draw_yard_spare` |
| The emergency call-out that gets an out-of-service truck moving | roadside repair | roadside rescue (that is the fuel one), tow | `_roadside_repair_out_of_pocket` |
| The emergency call-out for an empty tank | roadside rescue | roadside repair (that is the damage one) | `_handle_out_of_fuel` |
| Losing the truck to speed, usually out of gear on a grade | runaway | overspeed (that is the posted-limit one) | `RUNAWAY_SPEED_MPH` |
| What state the freight is in | the load; "freight" where "load" would be ambiguous | cargo condition, product, goods | `TruckState.cargo_damage_pct` |
| The receiver's note about damaged freight | exception on the bill of lading | OS and D, discrepancy, ding | `CARGO_OUTCOME_EXCEPTION` |
| What the carrier owes for freight it damaged | freight claim | damages, cargo insurance, write-off | `CargoSettlement.claim_value` |
| The receiver refusing a load outright | the receiver refused the load | bounced, returned, kicked back | `CARGO_OUTCOME_REJECTED` |
| Damage a safety committee rules the driver's fault | preventable damage | at-fault, chargeable, negligence | `TruckState.preventable_damage_pct` |
| The polling secret bound to this device | never spoken -- internal only | activation code | `Activation.device_code` |

Notes on the entries that are not simple:

**Job and load are two concepts, not two names.** The job is the contract; the
load is the freight on the trailer. "Use Abandon job to drop the load" is
correct and should stay that way. What is wrong is using "load" for the
contract -- "no load, no pay" means the job.

**"Rig" is flavour, not function.** It never appears in a menu item, prompt,
status readout or warning. It appears in achievement prose, where a second word
for the truck reads as writing rather than as a new concept, and it is the
label of one truck model ("standard rig"). Keep it out of functional text.

**"Corridor" is an explanatory word.** It belongs in help and manual text
describing where the map comes from ("routes made from real highway
corridors"). Per-drive navigation says leg.

**"Device code" is never spoken.** It is the polling secret bound to this
device, not something a player ever reads back or types anywhere -- only the
activation code crosses to the player. Keep it out of every spoken and
transcript-bound string; if a screen reads it out loud, that is a bug.

**The damage bands are three nouns, not three ways of saying "damaged".**
Reduced power is the engine holding back; limp mode is that plus a road-speed
cap the driver cannot drive out of; out of service is the truck no longer being
legal or able to drive at all. Each one means something different is true about
what the truck will do next, so they are never used loosely or
interchangeably. Every readout that gives a damage number gives the band beside
it -- the number alone tells a player nothing about what they have lost.

**"Out of service" is the real-world term and carries its real meaning.** It is
not a colourful way of saying "very damaged": it is the state in which a truck
may not be driven, borrowed from the out-of-service criteria an inspector
applies at the roadside. The same words already name the hours-of-service
version (`_place_out_of_service`), which is correct -- both mean "this truck
does not move until something is put right" -- so never introduce a second
noun for either.

**Grounding is what the carrier does; out of service is what the truck is.** A
company driver hears both, in that order, because they are different facts: the
truck is unfit, and the carrier has taken it off the road as a result.

**Truck damage and load damage are never the same sentence.** The truck's
number is the driver's problem and prices at a garage; the load's is the
customer's and prices at the freight's value, which is far larger. A readout
that gives one must not let the player assume it covers the other, so the Tab
screen names the freight separately from the truck.

**The load's condition is spoken in words first, the number second.**
"Eighteen percent" tells a player nothing about whether the receiver will sign
for it; "damaged, eighteen percent" tells them both. The words are fixed --
secure, shifted but sound, damaged, badly damaged, ruined -- and each one maps
to exactly one thing the dock will do.

**"Roadside rescue" and "roadside repair" are two different call-outs.** The
rescue brings fuel; the repair gets an out-of-service truck moving. They cost
different money and different hours, so they keep different names.

**"Stop" is the most overloaded word in the game** -- the POI, the act of
stopping the truck, and the command to do so. Where the sentence could be read
either way, name the thing: "the truck stop ahead", "bring the truck to a
stop".

**"Buff" is an internal word and must never be spoken.** The catalogue calls
them buffs; the player buys a shower, an energy drink, an Iron Skillet dinner.
Every spoken string goes through `Buff.label`, which is what makes that work.
Game-shop jargon in a trucking sim breaks the fiction and, more practically,
tells a screen reader user nothing about what they just bought.

**"Traffic" needs a qualifier.** Simulated vehicles around the truck and
reported incidents on the road ahead are different systems the player can act
on differently. "Traffic is heavy" and "there is a wreck reported ahead" are
not interchangeable.

## Open naming decisions

Recorded rather than silently resolved, because changing any of them changes
what players hear.

- **run against trip.** Delivery summaries say "this run"; the class is `Trip`;
  help text uses both. The table above picks "run" for spoken text and leaves
  `Trip` as the internal name, which is the current majority behaviour rather
  than a decision anyone made.
- **job against load in older strings.** "job" leads roughly four to one across
  `states/`, but some surviving uses of "load" mean the contract, not the
  freight. Those are the ones worth fixing, and only where a player would
  actually hear the ambiguity.
- **`TruckCondition` lives in `models/trucks.py`**, a portable-layer module,
  despite being game-owned save state. It should probably move next to
  `Profile`. Cheap to do, and it removes a boundary exception.
- **One spoken "buff" leak exists.** `states/driving_updates.py` falls back to
  the literal word when a worn-off record has no label:
  `worn.get("label", "buff")`. Every catalogued buff has a label, so it should
  not fire, but if it ever does the player hears "The buff has worn off." A
  better fallback is the group name -- "the coffee", "the tire service" -- or
  saying nothing at all.

## Working rule

- Adding spoken text for an existing concept: use the word in the table.
- Adding a concept: add a row, in the same change.
- Renaming a concept players hear: that is a player-facing change. It needs a
  changelog entry and a note on what they will hear differently.
