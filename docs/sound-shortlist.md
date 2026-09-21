# Sound shortlist: candidates by need

Curated 2026-07-18 from `\\romeyserv\share\sounds\manifest.txt` (62,280
audio files). Answers the sweep in `docs/sound-hunt-brief.md`.

**Everything here is UNAUDITIONED.** Selection was filename matching
only -- no playback was possible. Norm auditions by ear in Reaper and
makes the calls. Candidates are listed best-guess first. Paths are
library-relative to `\\romeyserv\share\sounds\`.

Anything that ships gets its provenance recorded in `CREDITS.md`.

## Read this first: four of these are replacements, not gaps

The game already ships placeholders at `vehicle/rumble_strip.ogg`,
`vehicle/turn_signal.ogg`, `vehicle/brake_release.ogg` and
`vehicle/gear_shift.ogg` (plus `brake_air`, `air_dryer_purge`,
`low_air_buzzer`). Needs 2 through 5 are upgrade-and-compare jobs --
audition candidates against what is in the tree today, not into an
empty slot. Need 1 is the only genuinely new sound family.

## Summary of what the library does and does not have

| Need | Verdict |
| --- | --- |
| 1. Curve cue tones | Adequate, and one standout: a real pitched set |
| 2. Rumble strip | **Absent.** Gravel shoulder is well served |
| 3. Turn-signal relay | Well covered |
| 4. Driveline clunk + turbo | Thin. Build it from parts |
| 5. Brake-release air sigh | Well covered, four collections deep |
| 6. Repair / rig-wear foley | Rich, but truck-specific tire work is thin |
| 7. Mini-game / UI stingers | Mixed. Bells and buzzers yes, game-show no |

---

## 1. Curve cue tones (highest priority)

Short one-shots for the panned pacenote cue and the RFC 1b tone ladder
(curve entry, back to center). Must stay pleasant at high repetition.

**The find: a genuine pitched set.** Sony Volume 4's Vintage Cartoon /
Musical Elements folder holds thirteen chromatic `Xylophone Single
Note` files (A through G#, plus a C octave), recorded in one session --
so they share timbre, level and decay and differ only in pitch. That is
exactly what the tone ladder wants: one instrument speaking three
times, not three unrelated blips. Nothing else in 62,280 files matches
that shape. A parallel `Xylophone Chord` set and a 6-hit Temple Block
set sit in the same folder.

- `./high quality/Sony/Volume 4/Vintage Cartoon/Musical Elements/Xylophone Single Note C.flac` -- anchor of the chromatic set; xylophone one-shots are inherently 200-300ms, dry, transient-clean.
- `./high quality/Sony/Volume 4/Vintage Cartoon/Musical Elements/Xylophone Single Note E.flac` -- third rung for a C-E-G ladder; same-session consistency.
- `./high quality/Sony/Volume 4/Vintage Cartoon/Musical Elements/Xylophone Single Note G.flac` -- a fifth above C; identical timbre keeps the ladder reading as one voice.
- `./high quality/Sony/Volume 5/Vehicles/Watercraft/Submarine Sonar Ping Classic.flac` -- archetypal pure-tone ping; "Classic" implies the clean isolated single, and it pitch-shifts trivially into a set.
- `./high quality/Sony/Volume 4/Vintage Cartoon/Drums & Percussion/Temple Block Hit 01.flac` -- dry woodblock from a 6-hit set; temple blocks are natively pitched by size and non-fatiguing.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6027 Music_ Percussion/06 Chimes Single Note.flac` -- explicitly a single isolated chime note; best pure chime in the library.
- `./high quality/sound_ideas/2000 Series/Sound Ideas 2000 Series - 2017 - Track47 - Marimbasingle Hit In G, Music, Percussion.mp3` -- explicit pitch label; warm round mallet, friendliest family for constant repetition.
- `./high quality/sound_ideas/Megasonics Sound Design SFX/MegaSonics CD1 - Hits, Risers, Fallers, Sweepers, Flybys, Wooshes, Transitions/Chime Hit A.flac` -- three-variant set (A/B/C); "Hit" signals a tight transient, not a swell.
- `./high quality/sound_ideas/2000 Series/Sound Ideas 2000 Series - 2017 - Track61 - Trianglesingle Hit, Music, Percussion, Idea.mp3` -- isolated triangle; shimmer cuts through road noise without reading as a UI notify.
- `./high quality/best service Blue Box/percussive_fx/woodblock_reverb.flac` -- single woodblock with a short tail; the tail gives the panned cue spatial depth.
- `./high quality/Sony/Volume 4/Vintage Cartoon/Musical Elements/Xylophone Chord C.flac` -- chord variant of the same set; a distinct curve-entry accent that stays in-family.
- `./high quality/Sony/Volume 3/Home & Office/Glass Clink Single.flac` -- naturally recorded short bell-like ting, distinct from anything synthetic.
- `./high quality/digital juice/Noise/Pings/10842_SFX.mp3` -- head of a 49-file Pings category; see caveat below.
- `./high quality/digital juice/Noise/Chimes/08846_SFX.mp3` -- head of a 99-file Chimes category, the largest clean-chime pool here.
- `./high quality/digital juice/Noise/Crystal/09106_SFX.mp3` -- 9-file Crystal category; glassy high-register, least likely to mask engine or voice.

**Coverage note.** Adequate, with the value concentrated in two places.
Sony Vol. 4 supplies the pitched set and is the real prize. Digital
Juice carries volume via purpose-built categories (Pings 49, Chimes 99,
Beeps 97, Clicks 76, Crystal 9) but every filename is an opaque numeric
ID -- treat those folders as audition pools to scrub through, not
curated picks, and note they lean toward the generic UI shapes the
brief said to avoid. Sound Ideas adds a few well-labeled isolated
percussion hits. BBC, Hollywood Edge, AKAI and Blue Box are
wrong-shaped: their tonal material is rolls, cascades, scales and clock
chimes, not sub-half-second one-shots.

**Open design question.** The shipped panned warning cue is currently
`ui/tick`. Either it also becomes a xylophone note (one co-driver,
three pitches -- recommended) or it stays deliberately a different
timbre so "road shape ahead" and "you are in it now" cannot blur. This
decision determines what actually gets cut.

### ElevenLabs prompts

1. "A single clean marimba note, soft mallet on a wooden bar, pitched
   around G4, 250 milliseconds total including its natural decay. Dry,
   close-mic'd, no reverb tail, no room. One hit only, no repeat."
2. "A short sonar-style sine ping, pitched around 900 hertz, 180
   milliseconds, fast attack and a smooth exponential fade. Pure tone,
   no harmonics, no echo, no underwater ambience. Single ping only."
3. "A small glass bell struck once, bright but not piercing, 300
   milliseconds, recorded dry with no reverb. Gentle enough to hear a
   hundred times in a row without fatigue. One strike, silence after."

Ladder note: run ONE prompt three times asking for three pitches (low /
mid / high) rather than writing three different prompts. Same timbre
across the ladder is the entire point.

---

## 2. Rumble strip + gravel shoulder

**Lead with synthesis. The library has no rumble strip.** Not thin --
absent. Across 62,280 files, "rumble" is entirely thunder, earthquake,
sci-fi drones and subway. No washboard, no corrugation, no
shoulder-drift recording. The nearest real thing is a cattle-guard
pass, and that is a one-shot event, not a bed.

This is probably the better outcome anyway. A rumble strip's defining
feature is a *periodic* buzz at tire-crossing rate, which should track
truck speed -- so a pulse train over a broadband noise floor beats any
fixed-rate recording. The gravel takes below supply the floor.

The gravel shoulder itself is well served, chiefly by Sound Ideas
General Series **6009 "Auto Road Surfaces"**, a purpose-built
dirt/rock/gravel matrix with interior, side and rear perspectives.

- `./high quality/Sony/Volume 5/Vehicles/Cars & Trucks/Tires On Gravel Steady.flac` -- the only filename promising a steady, engine-agnostic tire-on-gravel bed; "Steady" reads as loop-cuttable.
- `./high quality/sound_ideas/larger than life/2/2-32 Auto, Gravel Car Tire Stopping On Gravel And Brush, No Engine 0_06 Ltl2 32-2 Auto, Gravel Car Tire Hitting And Rolling On Wet Gravel, No Engine.flac` -- "No Engine" is rare and valuable: isolated tire crunch to layer over the game's own engine loop.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6009 Auto Road Surfaces/45 Auto,'90 Grand Am Ext_Start,Drive Med On Gravel,Stop,Shut Off,Rear.flac` -- rear mic puts the contact patch closer than the engine; sustained mid-section to crop.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6009 Auto Road Surfaces/42 Auto,'90 Grand Am Ext_Start,Drive Med On Gravel,Stop,Shut Off,Side.flac` -- same take, side perspective; crop between the start and the stop.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6009 Auto Road Surfaces/34 Auto,'90 Grand Am Ext_Start,Drive Med On Rocks,Stop,Shut Off,Side.flac` -- coarsest surface in the set, closest to a chunky shoulder crunch.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6009 Auto Road Surfaces/29 Auto,'90 Grand Am Int_Start,Idle,Drive On Dirt,Med,Stop,Shut Off.flac` -- interior POV, which matches a driver-seat game.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6009 Auto Road Surfaces/39 Auto,'90 Grand Am Int_Start,Drive Slow On Rocks,Stop,Idle,Shut Off.flac` -- slow-speed rocks give a low-rate irregular clatter; the nearest stand-in for washboard.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6009 Auto Road Surfaces/21 Auto,'90 Grand Am Ext_Start,Drive Med On Dirt,Stop,Shut Off,Side.flac` -- softer dirt bed; the quieter inner-shoulder texture before full gravel.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6009 Auto Road Surfaces/43 Auto,'90 Grand Am Ext_Spin Tires,Drive Fast On Gravel,Skid Stop,Side.flac` -- denser high-speed bed for a hard drift-out, with a skid tail.
- `./high quality/hollywood edge/BustedFX/03/83 - Car Tires Over Cattle Guard 2X.flac` -- the library's only true corrugated-metal-under-tires event; a 2x one-shot pass, not a bed, but the closest timbre to a rumble strip.
- `./high quality/sound_ideas/larger than life/2/2-25 Auto, Truck, Ram Ext_ Onboard_ Driving Through Gears, Skid To Stop 0_25 Ltl2 25-2 Auto, Truck, Ram Ext_ Onboard_ High Revs, Various Starts And Stops On Gravel.flac` -- onboard *truck* on gravel, right vehicle class; engine-dominant but has usable stretches.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6043/56 Auto, Gravel Ext_ Onboar.flac` -- truncated title, reads as a continuous onboard gravel bed.
- `./high quality/sound_ideas/de wolfe/12 - Cars/36 - Approach and pass on gravel.flac` -- exterior pass-by; short, but clean surface texture worth stretching.
- `./high quality/hollywood edge/ambience crowds and battle sounds/Rocks_Gravel.mp3` -- not vehicle-tied, but an ambience-collection granular bed usable as a sweetener.

**Coverage note.** Thin for the exact need, rich for the adjacent one.
6009 is the workhorse; Sony Vol. 5 supplies the one clean steady bed.
Nearly everything else labeled gravel in this library is footsteps,
horses or shovels. Missing shape: any isolated, engine-free,
long-duration rhythmic buzz.

### ElevenLabs prompts

1. "Continuous heavy truck tires running over a milled highway rumble
   strip at 60 miles per hour, 12 seconds, steady unchanging buzz-drone
   with a sharp repeating flutter. Recorded from inside the cab, no
   engine, no music, no variation in speed."
2. "Loose gravel and small stones crunching continuously under heavy
   truck tires on a road shoulder at low speed, 12 seconds, dense and
   steady, no engine, no gear changes, no fade in or out."
3. "Corrugated washboard dirt road under truck tires, 10 seconds, rapid
   even rattling texture, constant speed, dry outdoor recording, no
   engine noise."

Loop note: ask for 10-12 seconds and constant speed explicitly.
Anything that ramps or fades cannot be loop-cut cleanly.

### CC-licensed leads

Search YouTube with the Creative Commons filter (Filters > Features >
Creative Commons) for `rumble strip onboard`, `truck rumble strip
interior`, `washboard road driving`. Verify the CC-BY license on the
video page itself before using anything, and record it in `CREDITS.md`.
Never rip an ordinary video.

---

## 3. Turn-signal relay

- `./high quality/hollywood edge/PE collection/PE7 Cars/83 Volkswagen GTI Turn Signal On_Off.mp3` -- best by a wide margin: an actual turn signal captured as an explicit on/off pair, exactly the requested event.
- `./high quality/sound_ideas/Digiffects/D15 Transport/74 - Bus - transport lorry - big - blinker - direction light - 3 versions  - car.flac` -- a large commercial truck's blinker, the correct vehicle class for a tractor; three versions give alternates.
- `./high quality/sound_ideas/Digiffects/D15 Transport/47 - Mazda 626 - 1988 - blinkers - direction light  - car.flac` -- 1988 means a genuine electromechanical thermal flasher, the loudest and driest click type.
- `./high quality/sound_ideas/Digiffects/D19 Transport/50 - Car - Lexus IS200 2000 - Directionlights - blinkers - ticks.flac` -- "ticks" signals dry mechanical clicking rather than a chime.
- `./high quality/sound_ideas/de wolfe/12 - Cars/12 - Indicators.flac` -- cleanly isolated with no other event in the title; almost certainly a running loop of relay clicks.
- `./high quality/BBC Sound Effects Library/016 - Cars/13-Interior_ Indicators Operating.flac` -- interior perspective, which is the game's POV.
- `./high quality/sound_ideas/Digiffects/D19 Transport/78 - Honda CRV 2.0 03 automatic - suv - Directionslight - blinkers - 2 versions.flac` -- modern-era, likely a softer tick; useful as the quiet variant.
- `./high quality/sound_ideas/de wolfe/12 - Cars/11 - Start up and switch on indicator.flac` -- includes the stalk-throw transient that precedes the relay.
- `./high quality/sound_ideas/de wolfe/12 - Cars/21 - Hazard warning lights.flac` -- same relay hardware under double load; directly reusable for the game's hazard state.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6026 Motorcycles/56 Motorcycle,Suz.1100 Turn Signal_Switch On,Run,Switch Off.flac` -- full three-part structure, so it yields both a pair and a loop; brighter and faster than a truck's.
- `./high quality/Sound Effects 7/34. Relay switch.mp3` -- non-automotive but a real relay: a dry electromechanical snap to layer or pitch.
- `./high quality/sound_ideas/Power Surge 2/02/49 - SWITCH, ELECTRONIC - POWER RELAY FOR MONITOR_ SWITCH ON.flac` -- isolated energize click.
- `./high quality/sound_ideas/Power Surge 2/02/50 - SWITCH, ELECTRONIC - POWER RELAY FOR MONITOR_ SWITCH OFF.flac` -- the de-energize half; together with 49 a literal click pair, just not automotive in origin.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6038 Sound Designer Frank Serafine/54 Switchbox Traffic Switchbox_Timer And Switching Relays.flac` -- traffic-control switchbox, road-adjacent rhythmic clicking; fallback loop.

**Coverage note.** Genuinely well covered -- the pleasant surprise of
this sweep. Digiffects is the standout with four vehicles' blinkers
recorded in isolation and unambiguously labeled; Hollywood Edge PE7 is
the closest single match because it names the on/off pair outright. De
Wolfe and BBC each add an interior take. Missing: a heavy diesel
tractor's flasher specifically (the Digiffects lorry is the only
commercial-vehicle option), and any take isolating one clean click with
silence on both sides -- expect to slice the pair out of a running loop.

### ElevenLabs prompts

1. "A single vintage automotive flasher relay click, dry mechanical
   snap of a bimetallic contact, 60 milliseconds, close-mic'd on the
   relay itself, no cabin ambience, no engine. One click only."
2. "An old truck turn signal relay ticking steadily, 8 seconds, roughly
   85 clicks per minute, alternating harder on-click and softer
   off-click, dry and mechanical, nothing else in the recording."

---

## 4. Driveline clunk + air/turbo for shifts

**Lead with the prompts.** This need is thin and will have to be built
from parts. There is no file anywhere in the manifest containing
"driveline", "drive shaft", "wastegate" or "blow off", and only two
turbo hits that are not turboprop aircraft -- a Supra and a submarine.

- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6069 - Toboggam-Water/23 - Gmc 6000_ Ext_ Approach At Medium Speed, Pull Up, Idle, Shut Off, Heavy Gear Clunk.flac` -- the only filename in the library pairing "heavy gear clunk" with a truck; TRUCK.
- `./high quality/Sony/Volume 5/Vehicles/Cars & Trucks/18 Wheeler Away Shift Slow.flac` -- a genuine tractor-trailer pulling away through a shift, closest thing to a real semi upshift; TRUCK.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6069 - Toboggam-Water/25 - Gmc 6000_ Ext_ Approach, Pass By At Medium Speed, Shifting Gear Past Microphone.flac` -- same GMC 6000, audible gear shift in motion; TRUCK, exterior.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6025 Military/75 Truck,Military Weapons Carrier_Int_Drive Fast,Gear Down To Stop.flac` -- interior downshift of a heavy truck, right weight class and cab mic position; TRUCK.
- `./high quality/hollywood edge/PE collection/PE7 Cars/64 Old Truck Idles With Gear Grinds.mp3` -- isolated truck gear grinds against idle; close to a missed-gear crunch; TRUCK.
- `./high quality/sound_ideas/larger than life/2/2-25 Auto, Truck, Ram Ext_ Onboard_ Driving Through Gears, Skid To Stop 0_25 Ltl2 25-2 Auto, Truck, Ram Ext_ Onboard_ High Revs, Various Starts And Stops On Gravel.flac` -- onboard "driving through gears"; TRUCK, light-duty Ram not heavy.
- `./high quality/sound_ideas/Twentieth Century Fox Sound Effects Library/10/42 - TRUCK, MILITARY          ARMY TRUCK INTERIOR_  START,  DRIVE IN LOW GEAR,  HIGH ENGINE REVS,  STOP.flac` -- heavy army truck cab; donor for engine-load layers around a shift; TRUCK.
- `./high quality/hollywood edge/BustedFX/03/44 - Car Transmission Start Idle with Bad Transmission Clunks Off.flac` -- isolated transmission clunks with no road noise; CAR, pitch down for truck mass.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6073 - Air-Battle/01 - Air, Release Air Hose_ Disconnecting Air Burst, Fast.flac` -- cleanest short pneumatic burst to layer between shifts; UNKNOWN source.
- `./high quality/sound_ideas/platinum sounds/03 - Industrial 1/01 - AIR, RELEASE          SHORT, SOFT AIR PRESSURE RELEASE.flac` -- subtle air-line accent under each gear change; INDUSTRIAL.
- `./high quality/sound_ideas/platinum sounds/03 - Industrial 1/13 - AIR, RELEASE          AIR PRESSURE RELEASE VALVE OPEN.flac` -- valve-opening character rather than plain hiss; closer to a shift-assist valve; INDUSTRIAL.
- `./high quality/hollywood edge/Lon Bender's Wacky World Of Robots, Widgets & Gizmos/01/10-Hydraulic_Gear_Air_Hiss_And_Whoosh_Down_-_OdX.flac` -- a designed gear + air hiss + whoosh hybrid; essentially a pre-built mechanical-shift gesture; DESIGNED.
- `./high quality/sound_ideas/platinum sounds/03 - Industrial 1/87 - SERVO          ROBOT SERVO MOTOR_ TWO HEAVY, CLUNKING FOOTSTEPS.flac` -- two heavy metallic clunks in isolation; raw engagement-clunk transients; FOLEY.
- `./high quality/misc/Car Sounds - Supra Turbo.mp3` -- the only actual automotive turbo in the manifest; CAR, race/sport turbo not diesel, poorly labeled.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6038 Sound Designer Frank Serafine/60 Motor,Submarine Submarine Turbo Start Motor,Wind Up.flac` -- slow heavy wind-up that could stand in for diesel spool; SUBMARINE, designed.

**Coverage note.** Thin. General Series 6000 carries essentially all
the truck-shift material via the GMC 6000 and military-truck entries;
Hollywood Edge supplies clunk and grind material but in car context.
Missing entirely: a clean isolated heavy-truck turbo spool, a
wastegate/blow-off, and a dry driveline-clunk one-shot. Expect to build
the shift layer by combining the GMC 6000 clunk, a pitched-down
BustedFX transmission clunk, and a Platinum Sounds air release.

### ElevenLabs prompts

1. "A heavy truck driveline clunk as the gear engages, one dull
   metallic thud with a short low-end thump, 350 milliseconds,
   mechanical and weighty, no engine tone, no reverb."
2. "Diesel turbo blow-off between gearshifts, a quick rising whistle
   then a sharp pressurized release, 700 milliseconds total, big-rig
   scale not sports car, no engine note underneath."
3. "Short pneumatic air line release on a heavy truck, crisp hiss, 400
   milliseconds, decaying naturally, dry close recording, no ambience."

### CC-licensed leads

CC-filtered YouTube searches: `diesel turbo spool truck`, `jake brake
turbo whistle onboard`, `semi truck shift interior`. License-verify on
the video page; log in `CREDITS.md`.

---

## 5. Brake-release air sigh

The forum-requested pshhh. Well covered -- it exists in at least four
independent collections, nearly all genuine road vehicles rather than
rail.

- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6074 - Bayonet-Crowd/46 - Brakes, Air Truck Or Bus Air Brakes_ Short Release, Hydraulic.flac` -- best match: explicitly a truck/bus air brake SHORT RELEASE, isolated, Sound Ideas-labeled; TRUCK/BUS.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6074 - Bayonet-Crowd/47 - Brakes, Air Truck Or Bus Air Brakes_ Short Release, Hydraulic.flac` -- alternate take, so the release does not repeat identically; TRUCK/BUS.
- `./high quality/hollywood edge/PE collection/PE7 Cars/92 Air Brake Hiss #1_ Logging Truck.mp3` -- dedicated isolated hiss from a logging truck, exactly the road-tractor source wanted; TRUCK.
- `./high quality/hollywood edge/PE collection/PE7 Cars/93 Air Brake Hiss #2_ Large Truck.mp3` -- second in a four-file series built for this purpose; TRUCK.
- `./high quality/hollywood edge/PE collection/PE7 Cars/94 Air Brake Hiss #3_ Large Truck.mp3` -- third variation, good for randomizing set/release; TRUCK.
- `./high quality/hollywood edge/PE collection/PE7 Cars/95 Air Brake Hiss #4_ Large Truck.mp3` -- fourth variation; TRUCK.
- `./high quality/Sony/Volume 5/Vehicles/Cars & Trucks/18 Wheeler Air Brakes 01.flac` -- correct 18-wheeler class; TRUCK.
- `./high quality/Sony/Volume 5/Vehicles/Cars & Trucks/18 Wheeler Air Brakes 02.flac` -- second take for variation; TRUCK.
- `./high quality/sound_ideas/Digiffects/D15 Transport/79 - Bus - transport lorry - big - hydraulic brakes - air pressure - interior- car.flac` -- recorded INTERIOR, matching in-cab listener perspective; TRUCK/BUS.
- `./high quality/sound_ideas/Digiffects/D15 Transport/80 - Bus - transport lorry - big - hydraulic brakes - air pressure - close - version 1  - car.flac` -- same lorry, close mic, dry and isolated; TRUCK/BUS.
- `./high quality/hollywood edge/BustedFX/03/59 - Truck Semi Air Brakes Stop 2X.flac` -- semi air brakes, two passes, release tail sliceable; TRUCK.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6011 Construction #1/44 Constr. , Cement Truck Backing Up, Brake Air Release, Construction.flac` -- heavy diesel with a labeled brake air release; TRUCK, has a backup beeper to edit around.
- `./high quality/planes, trains, and automobiles/Truck air brakes.mp3` -- plainly labeled, though the collection is poorly documented; TRUCK.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6033 Transportation/05 Bus,City,Transit Pull Up To Side,Air Release.flac` -- transit bus, same pneumatic system as a tractor; BUS.
- `./high quality/Point Productions - Sound Effects 3/62. Bus with air brakes.mp3` -- backup; BUS, thin labeling.

**Coverage note.** Well covered. Hollywood Edge PE7 (four dedicated
isolated hisses) and General Series 6074 (two short-release takes) are
strongest; Sony Vol. 5 and Digiffects D15 are clean backups. **Avoid
the rail-sourced hits** -- `Premier Edition 4/05 - Airport Travel/09`
(subway) and `6069 - Toboggam-Water/04` and `/05` (diesel locomotive)
read as rail and are wrong for a road tractor, though usable for a long
sustained bleed-down. Missing: a labeled parking-brake /
tractor-protection-valve pop specifically, and any in-cab interior
perspective other than the single Digiffects lorry file.

### ElevenLabs prompts

1. "Air brake release on a parked semi truck, the long pneumatic sigh
   as pressure drops, 1.5 seconds, deep and airy with a soft tail,
   recorded close outside the tractor, no engine, no traffic."
2. "Parking brake knob popping out on a heavy truck followed by a sharp
   pressurized pshhh, 1 second total, dry mechanical then airy, nothing
   else in the recording."
3. "Short service brake air release, quick punchy psshh, 600
   milliseconds, truck scale not train scale, dry, no reverb tail."

Scale note: say "truck, not train" in every prompt here -- the model
otherwise defaults to a much bigger, longer rail-yard release.

---

## 6. Repair / rig-wear foley

- `./high quality/sound_ideas/platinum sounds/03 - Industrial 1/14 - IMPACT WRENCH          COMPRESSED AIR IMPACT WRENCH_ SINGLE BURST.flac` -- isolated single-burst air impact wrench; the canonical one-shot for a lug-nut hit.
- `./high quality/sound_ideas/platinum sounds/03 - Industrial 1/16 - IMPACT WRENCH          COMPRESSED AIR IMPACT WRENCH_ QUICK, HIGH REV BURST.flac` -- short high-rev burst, ideal as a repeatable per-nut tick in a repair mini-game.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6012 Construction #2/25 Ratchet Hand_ Loosen Nut, Construction, Wrench _23 6012 25-2 Ratchet Hand_ Tighten Nut, Construction, Wrench.flac` -- explicit hand-ratchet loosen AND tighten pair; exactly the manual lug-nut action.
- `./high quality/hollywood edge/industrial motor and electrical/44_FACTORY_MACHINERY_TIRE_CHANGE_CLANGING_HISSING_INDUSTRY_AUTO.mp3` -- named tire change with clanging and air hiss; a whole repair-bay beat in one file.
- `./high quality/Sound Effects 8/32. Hydraulic auto lift.mp3` -- literal hydraulic auto lift, best single match for raising the rig.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6052/29 Hydraulic Lift Operating.flac` -- clean lift-operation loop; pairs with the above for up/down states.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6052/17 Hub Turner Pneumatic Tir.flac` -- pneumatic tire/hub tool; strong tire-service candidate.
- `./high quality/hollywood edge/BustedFX/02/01 - Machines Air Compressor 1 On Steady Chugging Motor Off with Air Release.flac` -- full compressor cycle with on/steady/off plus air release; covers bay ambience and stingers.
- `./high quality/sound_ideas/Digiffects/E1 Industry/71 - Compressor - including emptying of air in tank.flac` -- compressor with tank blow-down for the air-drain hiss.
- `./high quality/Sound Effects 7/53. Tire repair shop.mp3` -- whole tire-shop ambience bed to sit discrete foley on top of.
- `./high quality/Sony Music Special Products - The Complete Sound Effects Library/67. Tire pump at gas station.mp3` -- tire inflation at a service station; the inflate action itself.
- `./high quality/sound_ideas/platinum sounds/03 - Industrial 1/13 - AIR, RELEASE          AIR PRESSURE RELEASE VALVE OPEN.flac` -- valve-open release, usable as the tire-deflate / chuck-off punctuation.
- `./high quality/BBC Sound Effects Library/043 - CONSTRUCTION/07-Wrench removed from toolbox.flac` -- tool-select foley; a natural UI cue for choosing a tool.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6054 - Industry-Motor/71 - Metal, Drop Drop Metal Wrench To Concrete Floor.flac` -- dropped wrench on concrete; the classic "you fumbled it" failure sting.
- `./high quality/sound_ideas/Digiffects/E3 Industry/19 - Hammering on solid metal - tools.flac` -- hammer on solid metal; the persuasion-by-hammer repair step.

**Coverage note.** Rich but uneven. Impact wrench, ratchet,
hammer-on-metal and air compressor are all well served; genuinely
truck-specific tire service is thin (essentially the Hollywood Edge
tire-change cue, the 6052 hub turner, and two tire-pump tracks).
sound_ideas carried the bulk (platinum sounds Industrial 1, General
Series discs 6012/6052/6054, Digiffects E-series), BBC disc 043 supplied
clean isolated hand-tool foley, Hollywood Edge BustedFX the compressors.
Missing entirely: air-ratchet on wheel studs, torque-wrench click, lug
nuts dropping in a pan, bottle/floor jack pumping, hydraulic lift
lock-pin engage. **Watch out:** most "lug" and "jack" hits in the
manifest are jackhammers, not vehicle jacks -- build the lug sequence
from single wrench bursts plus metal drops.

### ElevenLabs prompts

1. "Pneumatic impact wrench spinning a lug nut off a truck wheel, one
   burst, 1.5 seconds, hammering rattle then the nut spinning free, dry
   garage recording, no voices."
2. "Hydraulic shop lift raising, low motor hum with a rising pneumatic
   groan, 6 seconds steady, no clanking, no voices."
3. "Air compressor in a repair bay kicking on and running, 10 seconds
   steady, mechanical drone with a pulsing motor, no voices, no tools."

---

## 7. Mini-game / UI stingers

- `./high quality/sound_ideas/Power Surge 2/01/04 - bell, small high bell ding.flac` -- small high bell ding, isolated and short: the default correct-answer cue.
- `./high quality/hollywood edge/the edge edition/1/86 - Desk Bell.flac` -- crisp desk bell; reads as truck-stop counter service and doubles as a positive confirm.
- `./high quality/fun with sound effects/02/Door_buzzer.mp3` -- blunt flat buzzer, the most stereotypically "WRONG" tone in the manifest.
- `./high quality/hollywood edge/BustedFX/01/18 - Alarm Oven Timer Old 3 On Quick Buzzer Type Runs Ratty Off.flac` -- short ratty buzzer run: wrong-answer / time-expired.
- `./high quality/sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6010 - Misc Various Subjects/Bell, Desk Desk Bell_ Singl.flac` -- single desk-bell hit; alternate ding voice for menu confirms.
- `./high quality/hollywood edge/BustedFX/01/16 - Alarm Oven Timer Old 1 On Surge Buzzer Type Runs Ratty Off Close Perspective.flac` -- longer timer-alarm variant for countdown expiry.
- `./high quality/Keith Holzman - Authentic Sound Effects Vol.1/06. Kitchen timer.mp3` -- mechanical timer; source for both the ticking countdown and its ring-off.
- `./high quality/sound_ideas/Sports Sound Effects Library/02/69 - BOXING = ELECTRIC RING BELL_ SINGLE RING = _02.flac` -- single electric ring bell: round-start / round-end for timed mini-games.
- `./high quality/best service Blue Box/applause/applause_small.flac` -- small short applause, the right scale for a modest win, not a stadium.
- `./high quality/AKAI Sound Effects/HCLP+CHEER 1.flac` -- compact clap-plus-cheer one-shot, already stinger-length.
- `./high quality/Sony/Volume 4/Vocals & Wallas/Bite Chew Crunch Gulp.flac` -- one file covering bite, chew, crunch and gulp: the whole eating mini-game in one asset.
- `./high quality/hollywood edge/the edge edition/3/33 - Gum Wrapper, Open & Chew Gum.flac` -- unwrap plus chew; good for a snack/coffee stop with a lead-in.
- `./high quality/Sony/Volume 4/Vintage Cartoon/Comedy Vocals/Human Swallow 01.flac` -- isolated swallow, the natural terminator for an eating sequence.
- `./high quality/Sony/Volume 4/Vintage Cartoon/Comedy Vocals/Bronx Cheer 01.flac` -- cartoon raspberry; a comedic wrong-answer alternative to a buzzer.
- `./high quality/sound_ideas/Power Surge 2/01/64 - money, cash register with bell & drawer opens.flac` -- register bell plus drawer: the payout / ka-ching reward sting.
- `./high quality/AKAI Sound Effects/WEIGHTSCAL-S.flac` -- named weight-scale hit; see the caveat below.

**Coverage note.** Mixed. Bells, buzzers, applause and eating are
abundant; true game-show stingers are absent. Sony Vol. 4 Vintage
Cartoon carried the comedic vocals and eating material, AKAI supplied
short pre-trimmed cheer/clap one-shots, Hollywood Edge supplied buzzers
and desk bells, and Blue Box has a deep dedicated `applause/` folder
(~30 files, small through large). Missing: any purpose-built
correct/incorrect UI ding, a countdown tick-per-second, and a
scale-house beep. **The scale caveat:** the only weight-scale hits are a
bathroom/exercise scale (`AKAI Sound Effects/WEIGHTSCAL-S.flac`,
`Sports Sound Effects Library/03/16`) -- wrong object entirely. A weigh
beep will need a generic electronic tone or a register bell instead.

### ElevenLabs prompts

1. "A bright two-note correct-answer ding, ascending perfect fifth on a
   glass bell, 400 milliseconds, cheerful and clean, no reverb, no
   music."
2. "A short wrong-answer buzzer, low square-wave buzz, 500
   milliseconds, flat and blunt, not harsh or distorted, one buzz only."
3. "A small warm crowd applause, 3 seconds, twenty or thirty people
   clapping in a diner-sized room, starting immediately and fading
   naturally, no cheering, no whistles."

---

## Out of scope

Jake brake is **not** in this library (confirmed 2026-07-09, and this
sweep did not re-search it). The plan remains one clean exhaust pop
retriggered at RPM/20 for an inline-six, sourced via ElevenLabs first.
