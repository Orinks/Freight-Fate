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
| Save migration | `migrate_save_data`, `SAVE_VERSION` | `models/save_migration.py` |
| Integrity signature | `SIGNATURE_FIELD`, `ProfileIntegrityError` | `models/profile.py` |
| Profile invariants | -- | `profile_invariants.py`, `profile_integrity_invariants.py` |

`Profile` is the root of everything persisted. It *holds* a `Career`, a
`Market`, an `HosClock`, per-truck `TruckCondition` records, the money, the
in-game clock, the achievement list, and an `active_trip` snapshot. It is the
one object whose shape is a compatibility contract in three directions at once:
older saves, the cloud validator, and the integrity signature. Add fields with
defaults; never reorder or repurpose.

`TruckCondition` is per-truck persistent state -- fuel, damage, tire wear,
grime -- keyed by catalog key. It is deliberately *not* portable: condition
belongs to the truck you own in this game, not to the driver.

### The live drive

| Concept | Class | Module |
| --- | --- | --- |
| Trip | `Trip` | `sim/trip.py` |
| Route helpers | -- | `sim/trip_route_helpers.py` |
| Lane keeping | `LaneKeeping` | `sim/lane.py` |
| Time zone | `TimeZone` | `sim/timezones.py` |
| Live weather | `RealWeatherProvider` | `sim/real_weather.py` |
| Radio reception and tuning | `RadioTuner`, `Station` | `sim/radio.py`, `data/radio_catalog.py` |

`Trip` is the binding entity: it joins a driver, a truck, a job and a route
into one moving thing, and it owns the clock. Everything the player hears while
driving is a projection of a `Trip`. Game hours are absolute Eastern; local
time is a view, via `Trip.local_hour`.

### Player-facing systems

| Concept | Class | Module |
| --- | --- | --- |
| Achievement | `Achievement`, `AchievementAward` | `achievements.py` |
| Message | `Message`, `MessageCategory`, `MessageLog` | `message_log.py` |
| Settings | -- | `settings.py` |
| Speech | -- | `speech.py` |
| States | `State` and subclasses | `states/` |

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

- Tools edit `src/freight_fate/data/world.json`.
- The game loads the split `src/freight_fate/data/world_data/` tree.
- `tools/index_world.py` regenerates the split; `--check` verifies the two are
  in sync, and CI and tests expect that.

There is no automatic sync. An edit to `world.json` that is not re-split is a
change the game will never see.

The radio catalog is the same shape one stage shorter:

- `tools/build_radio_catalog.py` joins the source dumps in `data/radio-cache/`
  into `src/freight_fate/data/radio/stations.json`, which is checked in.
- The game reads that file; `tools/bake_radio.py` compiles it into the release
  build, because packaged builds ship no editable data files.
- `--check` verifies the catalog still matches its sources.

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
| A license add-on | endorsement | certification, licence | `ENDORSEMENT_LEVELS` |
| The in-cab receiver | radio | stereo, tuner, head unit | `RadioTuner` |
| One broadcaster | station | channel | `Station` |
| A part of the dial | band | waveband, frequency band | `BANDS` |
| How well it comes in | signal | reception, bars, strength | `signal_strength` |

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

**"Station" is a broadcaster, never a place.** The map already has weigh
stations and fuel stations, so a radio station is only ever called a station
where the sentence is plainly about the radio; elsewhere name it ("the station
you are tuned to", "the weigh station ahead").

**"Band" covers more than FM and AM.** Web radio and satellite are not
wavebands in the real sense, but the player selects them with the same control
and the same word, and inventing a second noun for "the thing Y switches
between" would cost more than the inaccuracy does. FM and AM are spoken as
spaced letters ("F M") so a screen reader says the letters.

**"Stop" is the most overloaded word in the game** -- the POI, the act of
stopping the truck, and the command to do so. Where the sentence could be read
either way, name the thing: "the truck stop ahead", "bring the truck to a
stop".

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

## Working rule

- Adding spoken text for an existing concept: use the word in the table.
- Adding a concept: add a row, in the same change.
- Renaming a concept players hear: that is a player-facing change. It needs a
  changelog entry and a note on what they will hear differently.
