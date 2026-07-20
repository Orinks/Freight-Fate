# Freight Fate Player Manual

Freight Fate is an audio-first trucking game. You build a career by accepting
freight, driving to the shipper, loading the trailer, running the route, and
delivering before the deadline.

This manual describes the current public game on the stable and development
snapshot channels. It focuses on what players can do from the menus and while
driving.

## Quick Start

1. Download the newest stable build from the
   [Freight Fate releases page](https://github.com/Orinks/Freight-Fate/releases).
2. Extract the archive into a folder you control.
3. Open the extracted `FreightFate` folder.
4. Run `FreightFate.exe` on Windows, or `FreightFate` on macOS or Linux.
5. Choose **New career**, enter a driver name, pick a home region, and pick a
   home terminal.
6. Listen to the first-day briefing, open the dispatch board, accept a job,
   and follow the current objective.

On Windows and Linux the game is portable: saves, settings, save identity
files, and packaged-game logs live in the `saves` folder inside the game
folder. On macOS the app lives in Applications and cannot write beside itself,
so those files live in `~/Library/Application Support/FreightFate` instead.

## Install, Updates, And Snapshots

Freight Fate ships as portable archives. There is no installer.

Release archives are named by platform when that platform is available:

| Platform | Archive Name |
| --- | --- |
| Windows | `FreightFate-<version>-windows-portable.zip` |
| macOS | `FreightFate-<version>-macos.zip` |
| Linux | `FreightFate-<version>-linux-x64.tar.gz` |

Use the newest stable release for normal play. Stable releases are numbered,
such as `v1.6.0`.

Snapshot builds are public pre-release builds named `nightly-YYYYMMDD`. They
let you try newer work sooner, but may have rough edges. A career saved in a
snapshot build may not load in an older stable release, so treat snapshot saves
as moving forward.

Packaged builds can check GitHub Releases for updates. Open Settings, then
Updates, to choose an update channel:

| Setting | What It Does |
| --- | --- |
| Update channel | Switches between stable releases and snapshot builds. |
| Check for updates | Looks for a newer packaged build immediately. |

When an update is available, the prompt offers:

| Choice | What It Does |
| --- | --- |
| Download and restart | Downloads the build, replaces game files, and relaunches. |
| What's new | Reads the release notes line by line. |
| Remind me later | Skips the update for now. |
| Skip this version | Stops asking about that exact release. |

Updates replace the game files only. They preserve the `saves` folder.

## Main Menu And Career Flow

The main menu can include:

| Choice | What It Does |
| --- | --- |
| Continue latest career | Loads the newest readable save. |
| Choose career | Opens a list of saved careers. |
| Manage careers | Opens reset and delete actions with confirmation. |
| New career | Starts name entry, career start choice, and home-terminal selection. |
| Achievements | Reviews earned and locked achievements for a saved career. |
| How to play | Opens the built-in help reader. |
| Settings | Opens gameplay, audio, speech and weather, and update settings. |
| Quit | Exits the game. |

A new career asks you to choose a start path after entering a driver name.
Company-driver starts use assigned carrier equipment, carrier-paid fuel and
routine repairs, and different wage and dispatch tradeoffs. The owner-operator
start is an experienced-driver shortcut with owned starter equipment, higher
gross revenue, limited working capital, and player-paid operating costs from
day one.

Company-driver carrier choices are:

| Start | Tradeoff |
| --- | --- |
| Northstar Freight Lines | Balanced company-driver wages and broad dispatch. |
| Great Lakes Training Transport | Better short-load stop pay, more short-haul training work, and slightly more forgiving deadlines. |
| Prairie Link Regional | Better per-mile floor, lower stop pay, more same-region work, and grain/bulk emphasis. |
| Summit Value Logistics | Better percentage and on-time bonus, smaller guarantee, and more long-haul/high-value lanes. |

Company starts begin with 5,000 dollars, an assigned company tractor, a full
tank, a fresh career record, and a company terminal or yard in the chosen metro
service area. The owner-operator start begins as a leased-on owner-operator
with 18,000 dollars working capital, an owned starter tractor, partial fuel,
light wear, and owner-operator costs already active.
The home-terminal picker starts with a region list, then opens the cities in
that region. Each start has a suggested default city, but any listed terminal
can be your starting city.

After the home terminal is chosen, the terminal repeats a first-day briefing
until the first dispatch is accepted. It names the carrier or owner-operator
setup, the current terminal, who pays normal equipment costs, and the first
objective: choose an unlocked dispatch, reach the shipper, and start a clean
record with dispatch.

After that first dispatch, the terminal adds **Career plan**. This speaks the
current career objective and how it should shape dispatch choices. Early
company drivers work through probation loads, dispatcher trust, safe service,
and better carrier lanes. Owner-operators hear reminders about working capital,
fuel, repairs, trailer costs, and cash reserves before moving toward stronger
contracts or own authority.

The normal career loop is:

1. Start or continue a career.
2. Open your terminal's dispatch board. New company hires accept the load
   dispatch assigns; senior drivers and owner-operators pick their own.
3. Drive from the terminal to the pickup facility.
4. Check in and load the cargo. Owner-operators then choose a destination
   route; company drivers run the route dispatch assigns.
5. Drive the loaded trip.
6. Use route stops for fuel, breaks, sleep, saves, inspections, or repairs when
   the stop supports those actions.
7. Take the signed destination exit when it is announced.
8. Stop at the destination facility, dock, deliver, and review settlement.
9. Continue from the destination terminal.

## Menu Controls

Most menus use the same keyboard pattern:

| Key | Action |
| --- | --- |
| Up arrow or Down arrow | Move through choices. |
| Enter or Space | Activate the selected choice. |
| Escape | Go back, cancel, or repeat a status message when leaving is not useful. |
| Home or End | Jump to the first or last choice. |
| Letter or number | Jump to the next choice starting with that character. |
| F1 | Show help for the current item. |

Menus provide the title, selected item, and item position, such as `2 of 6`.
F1 help explains what the current item does.

New career name entry supports Backspace to delete, F2 to review the current
name, Enter to confirm, and Escape to cancel.

The built-in How to play reader uses:

| Key | Action |
| --- | --- |
| Left arrow or Page Up | Previous help page. |
| Right arrow or Page Down | Next help page. |
| Up arrow or Down arrow | Read line by line. |
| Enter or Space | Read the whole current page. |
| Escape | Return to the previous menu. |

## Terminal And Garage

Your terminal is the safe hub between jobs. Public terminal actions include:

| Choice | What It Does |
| --- | --- |
| Dispatch board | Browse freight offers from local facilities. |
| Drive to city services | Drive a short local route to the freight market office, garage, or truck dealer. Service names use sourced local data where available, and GPS prefers checked-in local turns or road context when they exist. |
| Career plan | Review your next realistic career objective after the first dispatch. |
| Business status | Review company-driver or owner-operator status. |
| Garage | Refuel, repair, service tires, and wash company equipment; owner-operators can also buy upgrades, buy tractors, switch owned tractors, add trailer programs, or buy trailers after own authority. |
| Request pay advance | Draw cash against your next load when you are broke. |
| Career stats | Review level, reputation, deliveries, career totals, and the endorsements you currently hold. |
| Endorsement courses | Pay for refrigerated, heavy-haul, or high-value training early; the carrier sponsors each course for free at its unlock level. |
| Driving school | Spoken lessons on a flat, empty practice road where nothing counts: no money, no wear, no fuel, no hours. An instructor walks you through each step and waits for you to do it. Use it to learn the controls or practice without risking the career. |
| Truck status | Review truck model, fuel, tank size, damage, tire wear, and road grime. |
| Time and weather | Review the clock, career day, and current city weather. |
| Logbook | Review your recent Record of Duty Status entries. |
| Sleep 10 hours | Rest at the terminal and reset hours of service. |
| Save game | Save the current career. |
| Settings | Open settings categories. |
| Quit to main menu | Save and return to the title menu. |

Company drivers use an assigned carrier tractor. Fuel and routine repairs are
billed to the carrier, and truck purchases or performance upgrades stay locked.
After you become an owner-operator, fuel and repairs come out of your cash; the
garage can do partial fuel or repair work when you cannot afford a full tank or
full repair. Owner-operators also start with a dry van trailer program and can
add reefer, flatbed, or bulk programs. Company drivers do not lease trailers;
the carrier supplies the right trailer for approved loads.

## Business Status

Freight Fate can start you as a company driver for one of several fictional
starter carriers. The dispatch board lists carrier gross, but your settlement
pays driver wages and bonuses. The selected carrier changes wage floor, stop
pay, pay share, on-time bonus, route-length mix, deadline slack, and in some
cases regional or freight emphasis. The carrier assigns the tractor and supplies
the trailer, authority, insurance, fuel, and routine repairs.

The career ladder has 30 levels. Levels 1 through 15 are company-driver and
senior company-driver ranks. Levels 16 and 17 are owner-operator preparation,
but they are not a lease-purchase shortcut. The **Business status** menu tells
you your carrier, rank, next business unlock, and what still blocks the next
step.

The leased-on owner-operator buy-in unlocks later, at level 18, when the rest
of the business gate is also ready: 35 deliveries, reputation 80, no outstanding
pay advance, and enough cash for a 35,000 dollar truck buy-in while keeping
10,000 dollars working capital.

Owner-operators see higher gross revenue, but the business pays fuel, repairs,
maintenance reserve, insurance reserve, trailer program, truck payment reserve,
and settlement fees. You can reach that through the level-18 company-driver
buy-in, or choose the owner-operator start for a higher-risk career from day
one. The carrier still handles dispatch and reimbursed accessorials so the game
stays focused on driving.

At level 21, established owner-operators can set aside an authority prep reserve
from **Business status** after enough deliveries, reputation, and working
capital. At level 25, the final own-authority gate can open with 75 deliveries,
reputation 92, at least one specialty trailer program, no pay advance, and
enough cash to pay the startup cost while keeping working capital. Levels 26
through 30 are established independent owner-operator ranks with better direct
freight positioning, not fleet management. Direct freight has higher gross
revenue, but settlement also deducts insurance, compliance, trailer, truck, and
factoring costs. Buying a matching trailer lowers the direct-freight trailer
charge to an owned-trailer reserve. It is a playable business step, not a full
paperwork or broker-contract simulation.

City service drives are a first step toward more local city driving. Pick a
service, follow the spoken GPS, stop at the destination, and press Enter to go
inside. The truck does not enter the service automatically. Current service
locations are representative city POIs derived from the checked-in freight
market and terminal data; future map-data passes can make those approaches more
specific without changing the controls.

The garage can do partial fuel, repair, or tire work when an owner-operator
cannot afford the full service. Normal miles add slow tire wear and road
grime, even when you drive cleanly; company drivers bill tire service and
washes to the carrier.

If your balance goes negative and you cannot afford fuel, **Request pay
advance** fronts you cash against your next load (also available at in-trip
rest stops, drawn against the load you are hauling). The advance is offered
only while cash is low, is capped, and is repaid automatically out of your
next delivery settlement, so a negative balance is never a dead end.

As a company driver, dispatch assigns your tractor, and better equipment
follows seniority: every new hire starts in the same trainer-spec rig, then
the carrier upgrades your assignment at level 4 (a newer regional unit),
level 9 (a long-haul sleeper), level 13 (a premium tractor), and level 17
(first pick of the yard). Each hand-over is announced at settlement and
arrives fueled, serviced, and washed. Which model you get is the carrier's
call -- two drivers at the same level can be handed different iron.

After the owner-operator buy-in you take over the tractor you were assigned,
and the garage sells the rest of the catalog: day cabs, regional and
long-haul sleepers, long-nose classics, big-bunk conventionals, aero
flagships, and the heavy hauler. Each entry speaks its practical tradeoff --
pulling power, tank size, aerodynamics, and fuel appetite. The garage also
sells:

| Upgrade, Program, Or Trailer | Effect |
| --- | --- |
| Engine tune | Adds pulling power. |
| Aerodynamic kit | Improves highway fuel economy. |
| Long-range tank | Adds 50 gallons of capacity. |
| Reinforced brakes | Helps the brakes resist fade longer. |
| Reefer trailer program | Opens refrigerated and fresh food cargo for owner-operators. |
| Flatbed trailer program | Opens steel, machinery, construction, lumber, and paper cargo for owner-operators. |
| Bulk trailer program | Opens grain, farm inputs, and loose bulk cargo for owner-operators. |
| Owned trailer | Own-authority drivers can buy dry van, reefer, flatbed, or bulk trailers. Matching direct freight uses an owned-trailer reserve at settlement. |

Upgrades are fleet packages and apply to every truck you own. The garage
also sells winter equipment -- winter tires and snow chains -- covered in
the Winter Driving section.

## Dispatch And Jobs

The dispatch board lists jobs from local freight facilities. A metro area can
include company yards, ports, intermodal ramps, parcel hubs, warehouses, cold
storage, food processors, farms and grain elevators, manufacturing plants,
construction yards, mines, lumber or paper facilities, cross-docks, and other
freight locations.

How much say you have is earned with seniority. New company hires do not
browse the board: dispatch assigns one load, and you accept it or decline it.
You can decline a few assignments before your next promotion to have dispatch
draw another, but each refusal costs reputation, and when the declines run
out you take what you are given until you level up. Load choice from the full
board opens at level 8; choosing your own routes is an owner-operator
freedom.

Many freight destinations now use real map-sourced endpoint matches when the
offline data supports them. When the map data cannot prove a specific freight
place, the game keeps using a representative local facility and treats it as a
fallback instead of pretending it found a real gate or dock.
Some sourced freight destinations also have local public-road turn guidance;
where that is not available, the GPS keeps using the best checked fallback road
context.

Each job lists:

- Cargo and weight.
- Origin facility.
- Destination facility.
- Distance.
- Pay.
- Deadline.
- Equipment type.
- Trailer program note for owner-operators.
- Estimated driver pay or take-home before any pay advance.
- Market note when the cargo market is tight or loose.
- Endorsement requirement when one applies.

Early drivers mostly see shorter regional work. Higher levels widen the
distance cap and unlock more variety.

Company drivers use carrier-provided trailers, so trailer program locks do not
block their approved loads. Owner-operators start with a dry van program.
Specialty cargo may say it needs a reefer, flatbed, or bulk trailer program;
add that program from the garage before accepting the load. If a load is
blocked by your trailer setup, the dispatch row starts with `Locked job`.

Own-authority drivers see direct freight on the same board. The listed pay is
direct freight gross, and the row includes a short take-home estimate before
any pay advance. If you own a matching trailer, the job row says so and
settlement uses the owned trailer reserve instead of a trailer-program charge.

Deliveries earn money, experience, reputation, and career stats. Every settled
load teaches a base amount of experience on top of its miles, on-time streaks
compound the lesson, delivering the cargo undamaged adds a bonus, and specialty
endorsement freight teaches half again as much per mile. Every level up hands
you something concrete: longer dispatch distances every level, refrigerated
freight at level 2, heavy-haul at 3, high-value and a newer assigned tractor at
4, an extra assigned-load decline at 5, a deeper dispatch board at 6, 10, and
12, load choice at 8, a long-haul sleeper at 9, specialty freight favored on
your board at 11, premium long-haul lanes at 12, a premium tractor at 13, the
owner-operator checklist from 14, first pick of the yard at 17, and
business-path ranks through level 30. The full ladder is a months-long career:
early levels land within your first sessions, and the top rank is a long-haul
project measured in real months of driving.

## Pickup, Loading, And Route Planning

After accepting a dispatch, you drive a local pickup leg from the terminal to
the shipper. At the pickup gate:

1. Stop the truck.
2. Open the pickup facility menu.
3. Check in at the shipping office.
4. Load cargo at the assigned dock.
5. Depart for the destination after the trailer is loaded and sealed.

Check-in takes 15 in-game minutes. Loading gives a short spoken wait while the
dock crew loads and seals the trailer, then advances the clock by 60 in-game
minutes. Both count as on-duty time.

Departure depends on your business status. Company drivers run the lane
dispatch gives them: departing announces the assigned routing and starts the
loaded trip directly. Owner-operators and own-authority drivers plan their
own routing, and route planning appears after pickup and loading. Each route
option lists:

- Distance and highways.
- Legal hours plan.
- Fuel-capable and sleep-capable stop counts.
- Estimated carrier-paid toll exposure, if any.
- Terrain summary.
- Parking confidence notes.

Press W on a route option to check weather along it. With real-world weather
enabled, the game uses live city conditions when available. Otherwise it uses
the simulated forecast.

## Driving Controls

Driving controls are active while the road view is focused:

| Key | Action |
| --- | --- |
| Up arrow, hold | Throttle. |
| Down arrow, hold | Brake. With simple automatic direction changes, keep holding it after stopping to select reverse and back slowly. With deliberate direction changes, release it and press again. |
| Up or Down arrow, tap then press and hold | Latch that pedal so it stays applied hands-free, like the old hand-throttle knob. A click and a spoken confirmation mark the catch after about half a second of holding. Press the same key once to take the pedal back; the opposite pedal, the emergency brake, a hazard, or the overspeed alarm releases it instantly, spoken. Turn the gesture off under Settings, Driving assistance, Latching pedals. |
| B, hold | Emergency brake. |
| E | Start the engine. Stop the engine only below 5 miles per hour. |
| P | Release or set the parking brake. |
| K | Start or cancel automatic speed control. It uses adaptive cruise on open roads and speed keeper in low-speed zones. It pauses through the planned pickup and resumes once the loaded truck is rolling. Braking elsewhere also cancels it. |
| Plus / Minus | Raise or lower the open-road cruise target by 5 mph while automatic speed control is active. The keypad Plus and Minus keys work too. |
| X | Signal for or cancel the next announced route exit. The truck takes the ramp when speed, lane setup, and route intent are valid. |
| T | Open the route point-of-interest menu when stopped at a supported stop. |
| J | Toggle the engine brake. |
| H | Hold to sound the horn; release to stop it. |
| Space | Report speed, gear, RPM, the active speed-control mode and open-road target when speed control is on, air pressure, and brake state. |
| S | Report the posted speed limit here, the zone if any, and how far over you are. In bend country it adds the bend's advisory speed -- the posted limit and the yellow diamond are different numbers on a real road. On a delivery ramp that ends at a traffic light, S answers with the light and the distance to the stop bar instead, since the light is the law there. |
| D | Report one safe-speed number for right now. Weather grip, an armed exit ramp, and the next bend are already baked into the number. |
| G | Report the grade under the wheels and whether the truck is holding, pulling, or losing it. |
| Tab | Open the driving status menu. |
| F | Report fuel level and estimated range. |
| C | Report clock, deadline, estimated arrival, and hours of service. |
| R | Report the current road and direction, state, nearest named place, route progress, grade, and GPS context. |
| Shift+R | Report the next listed highway exit. |
| V | Report weather and forecast. |
| L | Report which lane you are in and whether you are centered, drifting, or at an edge. |
| Left / Right arrow | With lane drift on, steer; steer across the line to change lanes. With lane drift off, tap to change one lane in that direction -- the signal clicks and the change is announced. |
| A | Repeat the last route announcement, in case you missed it. |
| Comma | Re-read the last spoken line of any kind, here and in every menu. Press it again within a few seconds to step back through the last 20 lines; each older line is prefaced with how far back it is, and any new announcement returns the key to the newest line. |
| U | Report what is coming up: imposed speed limits, patrols, stops, exits, and the next few bends ahead with their advisory speeds. |
| F1 | Show the driving control list and current objective. |
| Escape | Open the pause menu. |

Manual transmission adds:

| Key | Action |
| --- | --- |
| Left Shift or Right Shift, hold | Clutch. |
| W | Shift up a gear. From neutral or reverse, selects first gear. |
| Q | Shift down a gear. |
| N | Neutral. |
| Backspace | Reverse. |

If you shift manually without the clutch, the game gives a gear-grinding
warning.

## Truck Behavior

Start the engine with E. A cold trip starts with the parking brake set and air
pressure low. Let the compressor build air to 100 psi, then press P to release
the parking brake.

The truck simulation includes:

- Automatic or manual shifting.
- Ten forward gears in manual mode.
- Air pressure, low-air warnings, parking brakes, and spring brakes.
- Separate primary, secondary, and trailer air tanks in detailed status.
- A three-stage engine brake worked through the gears.
- Grades and terrain from real elevation data.
- Brake heat, fade, and wear from real energy accounting.
- Fuel burn.
- Damage that reduces performance.
- Wear meters for tires, brakes, and engine, driven by how you actually
  drive. Wear talks back: bald tires grip less, worn brakes fade sooner,
  and a tired engine loses power and drinks fuel.

Condition belongs to the truck, not to you. Each truck you own keeps its
own wear, damage, fuel, and traction equipment, so switching tractors
means switching into that truck's actual state.

A loaded tractor-trailer pulls away gradually. The automatic transmission holds
the first few gears long enough to feel the weight, then settles into normal
highway acceleration.

Repeated hard braking can use air faster than normal driving. If low air is
reported, stop safely, set the parking brake, and let pressure build.

On an open road, automatic speed control requires the engine to be running and
the truck to be moving at least 20 miles per hour. Press K to start adaptive
cruise at your current speed. Plus and Minus raise and lower the open-road target
by 5 miles per hour, just like the accelerate and coast buttons on a real truck.
The keypad Plus and Minus keys work too. Press Space to hear the active mode and
target along with speed, gear, RPM, and air-brake state. The truck accelerates up
to a higher set speed on its own. Cruise looks ahead
for sharp posted-limit drops so it can begin slowing before the lower-limit
stretch. It will not hold more than 5 miles per hour over the posted limit, so
it keeps you legal even if you set it higher. Weather can increase the following
gap, and modeled traffic can make cruise reduce speed. Cruise does not steer,
change lanes, or replace your attention.

## Mountain Driving

Grades are real: the game samples actual elevation along every route, so
the long climbs and descents you hear are the ones a real driver runs.
Press G at any time for the grade under your wheels and a plain verdict
on whether the truck is holding it, pulling it, or losing it.

Curves are real too, and a co-driver reads them to you. When a bend
ahead demands slowing at your current speed, a short tone sounds on the
curve's side -- left tone for a left bend -- and the call follows:
"Sharp left, half a mile. Advise 35." The tone marks the words as a
description of the road, never a steering instruction, and the call
lands with enough road left to brake before the bend, never in it. The severity ladder runs gentle bend,
curve, sharp, and hairpin, and tight pairs link into one call: "Sharp
left, a quarter mile. Advise 30. Then right." Bends you are already slow
enough for stay silent, so a straight interstate stays quiet. Press U
any time to hear the next few bends with their advisory speeds, and D to
get one safe-speed number with the bend already baked in. Turn the calls
off under Settings, Driving assistance, Curve callouts; U and D keep
reporting bends either way.

Going down is the discipline. The service brakes turn speed into heat,
and heat is the enemy: drag the brakes down a long grade and they fade,
which means the same pedal gives you less and less stopping power right
when you need it most. The way down a mountain is the engine brake.
Press J to toggle it. It is strongest in a low gear at high RPM and
nearly useless in overdrive, so gear down before the descent, let the
engine hold the truck back, and save the service brakes for short, firm
corrections -- brake down a few miles per hour, release, and let the
brakes cool while the engine does the steady work. The automatic
transmission helps by pre-selecting a lower gear when the engine brake
needs one.

If you cook the brakes anyway, you will hear it: hot brakes squeal, and
a spoken warning names the trend. Press D for the one safe-speed number
that already accounts for the conditions. Descent speed control, in the
driving assistance settings, can manage engine braking for you at the
level you choose.

## Winter Driving

Cold seasons bring snow, ice, and the one weather worth parking for:
freezing rain. Traction is honest -- ice cuts grip to a small fraction
of dry pavement, worn tires make everything worse, and the engine brake
can break the drive wheels loose on a slick surface.

The garage sells the winter answers:

| Equipment | What It Does |
| --- | --- |
| Winter tires | A fresh set in a winter compound. Better grip on snow and ice all season, no speed penalty, normal wear. Company drivers ride on whatever the carrier specs. |
| Snow chains | A set kept in the truck's side box until you hang them. Chains rule ice and packed snow, but demand chain speed -- around 30 miles per hour -- and they grind apart fast on bare pavement. Snapped chains are replaced at the garage. |

Chain up from the pause menu while stopped. Hanging chains takes real
minutes and real effort, more in the dark, and the time is logged as
on-duty work. Removing them is quicker. Listen to the road: chains on
bare pavement complain before they snap, so take them off when the
surface clears.

Mountain passes carry chain laws. When a chain law is active, flashing
signs announce it ahead of the restricted stretch, and the requirement
is spoken plainly: Level 1 wants winter tires or chains, Level 2 wants
chains on the drive axles. Running a checkpoint without meeting the
requirement risks a citation of around five hundred dollars. The signs,
the warnings, and the checkpoints all ride real mountain grades from
the map data.

## Road Events, Weather, And Rest Stops

The road can report traffic, construction, state lines, city pass-throughs,
checkpoints, toll points, route stops, and weather changes. Morning and
afternoon rush hours can make metro corridors busier and slower. Dense
metro/checkpoint corridors can also produce random road hazards a little more
often than open-country stretches.

Hazards can happen while moving. When a "Brake now" warning appears, slow below
25 miles per hour quickly to avoid a collision. Some hazards are called out as
"Brake or change lanes" -- those are fixed objects in your lane, like road
debris or a stopped vehicle. A lane change dodges them at full speed if the
lane beside you is clear; braking works too, but you cannot roll over a ladder
at 25 -- an object in the lane takes braking nearly to a stop, and then you
ease around it. Press L first if you are not sure which lane you are in, and
listen for the nearby-vehicle callouts; changing lanes into a real vehicle
risks a sideswipe. With automatic emergency braking on, the truck brakes for
you at the last moment -- down to a crawl for an object in the lane.
Fatigue shortens the reaction window.

Construction and traffic zones lower the speed limit. Construction zones may
begin with a merge/flagger taper before the lower work-zone limit. Speeding in
the main construction zone can trigger enforcement.

Traffic can also build around exit lanes, highway merges, construction tapers,
and slow lead packs. You may also hear nearby vehicles called out, such as a
merging vehicle, brake lights, or a slow car ahead. Treat those cues like a
heads-up to signal early, leave space, and avoid forcing the merge.

Posted speed limits come from real map data and change along a corridor; a
change is announced as reduced or raised, and named near a city. State troopers
patrol some stretches, hotter on busy interstates, in construction, and at
night. CB chatter may mention a bear ahead or drivers talking about enforcement
near a work zone; press U to review that chatter with other route guidance. Speed
badly inside a patrol and a trooper may pull you over: signal with X (the same
key as an exit), brake to a stop on the shoulder, and sit through a license and
logbook check that reads your recent duty entries before ending in an
on-the-spot ticket or a warning.
Ignoring the lights starts as a failure-to-stop warning, then a final warning.
Keep driving past that and troopers end the stop with spike strips. A felony
stop adds truck damage, a major fine, a reputation hit, several hours of
processing time, and cancels the active loaded run. You are released back to the
terminal so you can repair, rest, and choose what to do next. Speeding the
patrols do not catch still adds a quieter charge at delivery settlement.
Open weigh stations also matter: the game warns you before the scale, and if
you blow past at highway speed instead of slowing into the inspection lane, a
scale officer can light you up for a roadside enforcement stop. A visibly
unsafe truck can also draw a safety stop when you pass active enforcement, so
repair severe damage before pushing through patrol corridors.
In low-speed local roads such as facility access, construction, or heavy
traffic, automatic speed control uses the speed keeper instead. It switches
back to adaptive cruise when the open road begins. If you start it during the
deadhead, the planned pickup pauses the session while you check in and load.
After departure, get the loaded truck rolling and speed control resumes on its
own. The paused state is kept if you save at the pickup.

Weather affects safe speed, traction, braking, visibility, traffic pressure,
adaptive cruise following distance, and audio layers such as rain, wind,
thunder, snow, and fog. Press V while driving for current conditions. In
simulated weather, V also gives the upcoming forecast. Driving well over the
safe speed for the conditions on a slick road risks losing traction --
hydroplaning in rain, sliding on snow -- and high winds and storms add real
drag that costs you speed and fuel.

Your career runs on a calendar. A new career begins on **March 21**, in early
spring, and the date advances as you drive, rest, and sleep -- through summer,
autumn, and into winter, then around again. The season sets the weather:
snow and ice are cold-season risks, thunderstorms a warm-season one, and the
regional temperature follows the time of year and time of day. The current
date and season are announced with the clock (press C while driving), in the
Tab status menu, and at the city terminal. With live weather turned on, the
default is for the date, season, and temperature to follow the real-world
calendar. Turn **Live weather controls calendar** off to keep live city
conditions while the career date advances at midnight and its seasons pass.
For an established career, turning it off begins the independent calendar on
today's date so the date does not jump backward. A newly created career still
begins on March 21.
Conditions remain seasonally plausible, so live snow is changed to rain or
cloud when the career calendar is in warm weather, and thunderstorms are
changed to heavy rain when the career season is too cold for them.
The Time and weather item at a terminal always uses the live station
temperature when it is available, regardless of which calendar controls the
season. On the first request it may say live weather is still loading; try the
item again after a moment rather than treating a modeled temperature as live.

Stops are reported as you approach them. A one-mile cue tells you when to take
an exit. As an announced exit approaches, use X to signal or cancel your intent,
slow to 45 miles per hour or less, and set up the exit lane when lane drift is
enabled. The signal-on announcement also names how the ramp ends -- a traffic
light or a stop sign -- so the braking plan can start on the mainline, and the
U upcoming readout carries the same warning. Once you are on a ramp that ends
in a light or a sign, the game clock runs in real time until you are through
the intersection, so the warning buys real reaction seconds instead of
compressed ones. If your speed, lane setup, and route intent are valid at the marker,
the truck takes the ramp automatically. If you reach the gore too fast, without
signaling, or without the exit lane set, you stay on the
highway and the game tells you what went wrong. The timing is generous so the
sequence is about preparation, not twitch input. The game can also tell you when
traffic boxes you out of the lane, so you know to recover at the next safe exit
instead of fighting the maneuver. The
game gives a short pull-in moment before the stop menu opens, so holding Down
Arrow to brake does not skip the first menu option.

Destination exits work the same way. When your delivery exit is ahead, the game
announces the signed exit and toward cities, marks it as the destination exit,
and tells you to slow down and set up for the ramp. If lane drift is on, use X
to signal and move right for the exit lane. With lane drift off, the GPS infers
your destination-exit intent from the route. If automatic speed control is
active, it eases the truck to 45 miles per hour or your lower cruise target so
you can reach ramp speed without an abrupt handoff. Press X to take the exit;
automatic speed control releases as you enter the ramp, then you brake to the
stop. If you miss the destination exit, continue to the next safe turnaround.
Dispatch loops you back onto the approach so you can hear the exit call again
and press X to take it.

Ordinary highway exits that do not lead to a current action are not announced
during the drive. Press Shift+R if you want the next listed exit for route
context.

Stop actions depend on that stop's data. A stop may offer:

- Fuel.
- Meals, drinks, and showers.
- A 30-minute break.
- 10-hour sleep or sleeper-berth splits.
- Repairs and rig care.
- Roadside assistance or towing.
- Inspection check-in.
- Save point.

Meals, drinks, and showers are purchases with spoken effects and clocks
on them: a hot meal or a coffee helps fatigue for a while and says so
when it wears off, and a sit-down meal's half hour also satisfies the
30-minute break rule. Showers are commonly free with a fuel purchase at
the same visit. Rig care such as lube work and tire checks is truck
work, so the carrier covers it for company drivers; food and showers
are always your own money. Different stop brands are good at what they
are really known for.

Not every stop offers every action. A public rest area usually does not offer
fuel or repair. A weigh station is for inspection, not food or sleep: slow
down, pull into the scale lane, stop, then press T for inspection check-in.
Parking labels describe confidence, not a live guarantee that a space is open
right now. Late at night, a sleep-capable stop may be full.

## Hours Of Service And Fatigue

Freight Fate tracks an ELD-style hours clock. In realistic mode:

- You can drive 11 hours after a 10-hour reset.
- The duty window is 14 hours after coming on duty.
- You need a 30-minute break after 8 cumulative hours of driving.
- Sleeping 10 hours resets the shift clock.

At sleep-capable truck parking, the sleeper berth means the bunk in your cab.
You can choose 2, 3, 7, or 8 hours in the sleeper berth to plan an 8+2 or 7+3
split. Sleep 10 hours remains the simplest full reset. Shoulder sleep and
sleeping 10 hours in the lot are fallback rests, not clean split-rest planning
tools.

The game gives warnings at 2 hours, 1 hour, and 30 minutes before a limit.
Driving past a limit risks inspections, fines, reputation loss, and
out-of-service orders.

The Logbook is the spoken Record of Duty Status behind that clock. It records a
rolling timeline of driving, on-duty work, off-duty breaks, and sleeper-berth
rest, with the time, location, and a short note such as fuel stop, loading, or
out-of-service order. Open **Logbook** from the terminal, or open **Tab** while
driving and choose **Logbook**, to review today's totals and recent entries.

Fatigue rises while driving, faster at night. Drowsiness adds yawn and rumble
strip cues and makes hazards harder to react to. Once fatigue is severe you
start to nod off: a rumble-strip jolt and a warning give you a brief window to
steer or brake and stay awake. Catch it and you carry on; miss it and you drift
onto the shoulder, taking damage and losing speed, and a third miss in a row
forces you off the road. Food and coffee help you stay alert a little longer,
but do not satisfy the 30-minute break rule. A 30-minute break reduces fatigue
more; a proper 10-hour sleep clears it. Plan your rest before you get there.

Emergency shoulder sleep is a fallback, not normal rest. It can appear in the
pause menu when you are stopped away from a route point of interest. The game
uses stronger warnings when hours are tight or fatigue is severe. The
confirmation explains that 10 hours pass, the hours clock resets, fatigue only
improves to a poor-rest floor, a parking ticket is possible, minor truck damage
is possible, and the delivery deadline keeps running.

## Status Screens

Use these keys when you need status without leaving the road:

| Key | Information |
| --- | --- |
| Space | Speed, gear, RPM, air pressure, and brake state. |
| F | Fuel level and estimated range. |
| C | Clock, deadline, estimated arrival, and hours of service. |
| R | Route progress and GPS context. |
| Shift+R | Next listed highway exit. |
| V | Weather and forecast. |
| M | Toggle the in-cab radio. |
| [ / ] | Tune the radio down or up. |
| Ctrl+[ / Ctrl+] | Jump to the previous or next radio category: route playlist, Freight Fate stations, your playlists, terrestrial, AFN, satellite. |
| Y | Speak radio station, source, signal or fallback state, volume, and streamer-safe status. |
| Tab | Grouped driving status screens. |

Tab opens the Driving status menu. It has four review screens and a Driver apps menu:

| Screen | Information |
| --- | --- |
| Route | Current route status lines from the active drive. |
| Driver | Driver name, money, load, objective, truck fuel and damage, transmission, fatigue, hours, and deadline. |
| Map | Route cities, highways, progress, next guidance, upcoming stops, map points, and toll exposure. |
| Radio | Current station, stream-safety state, approximate reception position, and currently receivable stations. |
| Driver apps | A tablet-style app menu for Navigation, Weather, Traffic, Truck stops, Road chatter, and ELD. |

Inside a status screen, Up and Down move line by line, Enter repeats the current
line, and Escape returns to the status screen list.

Inside Driver apps, choose an app first. Each app opens as its own reviewable
list: Up and Down move line by line, Enter repeats the current line, and Escape
returns to the Driver apps menu.

## Pause, Save, And Resume

Escape opens the pause menu during a drive. Public pause choices include:

| Choice | What It Does |
| --- | --- |
| Resume driving | Return to the active drive. |
| Trip status | Review cargo, objective, route progress, time used, and air status. |
| Controls and help | Open the how-to-play reference at the driving keys, page by page, without leaving the drive. |
| Call a roadside mechanic | Patch severe truck damage enough to continue, at a high cost. |
| Install snow chains | While stopped with chains in the side box: hang the chains. Takes real minutes, more in the dark, logged as on-duty work. |
| Remove snow chains | While stopped with chains mounted: take them off before bare pavement grinds them apart. |
| Emergency shoulder sleep | Rest on the shoulder when stopped away from route points; warnings get stronger when hours or fatigue are urgent. |
| Settings | Open settings during the drive. |
| Abandon job | Pay a penalty and return to the origin city. |
| Save and quit to main menu | Save the active drive and resume it later. |

Freight Fate saves at terminals, at supported route save points, when quitting
to the main menu, and during important trip state changes. Continue latest
career can resume a saved pickup objective, pickup drive, pickup facility visit,
city service drive, or loaded delivery.

The main menu can continue the latest career, choose another career, reset a
career, or delete a career. If a saved career fails its integrity check, the
game moves it aside and warns you at startup.

To move Freight Fate to another folder or drive on Windows or Linux, copy the
whole `FreightFate` folder, including `saves`. On macOS the saves stay in
`~/Library/Application Support/FreightFate` and follow your user account, so
moving the app does not move them.

## Destination And Settlement

At the destination, slow down for the facility gate, stop, and choose **Dock
and deliver**. On highway deliveries, take the announced destination exit
first; in cities with street data, the arrival flows off the ramp onto the
destination's real local streets with spoken turn-by-turn cues, and loaded
departures drive the streets back out to the on-ramp the same way. You can
also review paperwork before settling.

The destination menu includes:

| Choice | What It Does |
| --- | --- |
| Dock and deliver | Unload the trailer, sign the paperwork, and open settlement. |
| Check paperwork | Review facility, cargo, payout, deadline, damage, tolls, approved charges, driver charges, and net pay before settlement. |
| Check arrival status | Review facility, cargo, speed, and next step. |

Unloading gives a short spoken wait and advances the clock as on-duty work
before settlement. Settlement reports cargo delivered, trip time, on-time
status, gross pay, carrier-paid or reimbursed charges, driver-responsibility
charges, net driver pay, money after settlement, fuel, truck damage, career
messages, and achievements.

Tolls and approved accessorial charges are carrier settlement items. They are
reported for transparency but do not reduce driver pay. Driver-caused charges,
such as speeding fines, can reduce driver pay. Hitting the delivery window
earns a flat ten percent on-time bonus, the way real shipper scorecards pay
for service: arriving hours early pays no more than making the appointment.
Late delivery and cargo damage reduce pay.

## Settings

### Driving assistance and speed keeper

Three driving assistance presets are available: Realistic, Balanced, and All assists. Changing an individual assist is shown as Custom. Adaptive cruise always follows traffic, anticipates large posted-limit drops, and increases its following gap in poor weather. Realistic adds modern safety support: automatic emergency braking, lane-departure warning, supported stop-and-go behavior, and realistic descent control. Balanced adds light lane centering and lets braking capture a lower descent target. All assists adds automatic safe descent targets and stronger intervention. These presets do not change trip pacing, hours rules, transmission, weather, or hazard frequency.

The individual controls are Automatic emergency braking, Lane-departure warning, Stop-and-go assistance, Lane centering assistance, Descent speed control, Exit speed assistance, Destination approach assistance, Curve speed assistance, and Route-transition assistance. Descent speed control has four levels: Off, Realistic, Balanced, and Interactive. Interactive is a descent-control level, not a preset. Exit speed assistance slows for an already-selected exit, destination approach assistance slows and stops at the selected facility arrival point, curve speed assistance reduces speed workload for mapped curves, and route-transition assistance helps manage speed and lane workload at confirmed route transitions. Assists never choose a route, take an exit, enter a yard, dock, or complete a delivery: you still steer, confirm route choices and exits, initiate lane changes, leave long stops, and handle every precision task.

Lane drift also lives in this category and, like the speed keeper, sits outside the presets. It chooses whether the lane-position task runs at all: Off keeps the truck centered with no lane work, Light drifts gently with centering help, and Realistic drifts like a real wheel. When lane drift is on, a short beep comes from the side you drift toward, so steer away from the beep; a centered-lane chime confirms you are centered again, and the rumble strip is panned to the side you have drifted toward near the lane edge. With lane drift on, taking an exit needs your turn signal set and the exit lane held. Choosing Light or Realistic turns the matching lane support on. The All assists preset switches lane drift off, so lanes are kept for you and a tap changes lanes; other presets never change it.

One more control, Speed keeper, sits outside the presets and is never changed by choosing a preset. In low-speed zones where adaptive cruise is unavailable, such as facility access roads, gate queues, and work zones, pressing K starts automatic speed control in speed-keeper mode. It holds your current speed at or below the zone limit and creeps behind queued traffic, so the accelerator does not need to stay held down. On the open road it automatically changes to adaptive cruise and accelerates toward the posted limit, or restores the cruise target you selected earlier. Entering another restricted zone changes back to the speed keeper. If you start it during the deadhead, the planned pickup pauses the session while you check in and load, keeps it through a save, and resumes it after departure once the truck is rolling. Plus and Minus adjust the remembered open-road cruise target in either mode. Any brake input outside that planned pickup, a hazard, or pressing K again cancels the whole session so it cannot restart unexpectedly. Speed keeper is on by default and can be turned off in Settings, Gameplay.

Latching pedals is the same kind of control: an input accommodation that sits outside the presets, on by default. Tap the accelerator or brake, then press again and hold for half a second, and a click plus a spoken confirmation latch that pedal so it stays applied hands-free. Press the same key once to take it back; the opposite pedal or any safety alert releases it instantly, spoken. See the driving controls table for the full gesture.

Curve callouts also sit outside the presets, on by default. A co-driver
calls the bends that demand slowing before they arrive -- "Sharp left,
half a mile. Advise 35." -- and stays silent for bends you are already
slow enough for. See Mountain Driving for how to drive with the calls.

Settings are grouped into categories. In a settings category, Up and Down choose
a setting, Right arrow or Enter changes it forward, Left arrow changes it
backward, and Escape returns to the category list. Changes are saved as they
are made.

Gameplay settings include:

| Setting | Purpose |
| --- | --- |
| Units | Switch speed and distance between miles and kilometers. |
| Transmission | Switch between automatic and manual transmission. |
| Automatic direction changes | In an automatic, Simple changes between forward and reverse when you keep holding the control after stopping. Deliberate requires releasing and pressing it again. |
| Overspeed warning | The dash alert for running over the posted limit: On speaks once and then chimes faster the further over you are, Urgent only keeps just the runaway alarm for deliberate fast cruising, and Off silences it. |
| Driving mode | Choose Relaxed, Standard, or Realistic pacing and pressure. Relaxed keeps every driving system but gives wider hazard response windows, fewer random hazards, gentler collision damage and fatigue, calmer routine speech, and the most real time to respond. Standard keeps balanced timing and consequences. Realistic moves distance and time fastest, so decisions arrive sooner without extra forgiveness. At low speed the clock still eases toward real time, and deliberate parked waiting runs at double the selected pace. |
| Hours of service | Choose realistic or relaxed legal limits. Relaxed hours rules lengthen the limits and further reduce random hazard frequency; real violations keep their normal consequences. |
| Driving assistance | Open Settings, Driving assistance for lane drift, lane warning, lane centering, emergency braking, stop-and-go, descent, and speed keeper controls. |
| Trip pacing | Choose relaxed, standard, or fast pacing. Pacing applies at highway speed; the clock eases toward real time while you accelerate, brake, or maneuver, so working up through the gears does not cost most of a game hour. Setting the parking brake while stopped means deliberate waiting: time then passes at double your pacing, letting weather and daylight move along. |
| Hours of service | Choose realistic or relaxed hours rules. |
| Lane drift | Choose whether lane drift is off, light, or realistic. When on, a short beep comes from the side you drift toward, so steer away from the beep. A dedicated centered-lane chime confirms you are centered again, and the rumble strip is panned to the side you have drifted toward near the lane edge. |
| Speed keeper | Allow automatic speed control to use the speed keeper in low-speed zones and switch back to adaptive cruise on open roads. |

Audio settings include:

| Setting | Purpose |
| --- | --- |
| Master volume | Overall game volume. |
| Gameplay cues volume | Horn, alerts, road, facility, and gameplay cue sounds. |
| Weather sounds volume | Rain, wind, thunder, snow, and fog sounds. |
| Engine sounds volume | Engine start, shutdown, and running engine sounds. |
| Music volume | Menu and facility background music volume. |
| In-cab radio volume | Driving radio music volume. It defaults lower than speech and safety cues. |
| Radio streamer-safe mode | Keeps radio on built-in safe stations and hides real public streams. |
| Radio real public streams | Opt-in catalog access for real public stations, including AFN choices. Streamer-safe mode must also be off before they appear. |
| Menu and UI sounds volume | Menu movement, selection, warning, and cash sounds. |

Speech and weather settings include:

| Setting | Purpose |
| --- | --- |
| Speech verbosity | Controls how often driving status reminders run. |
| Roadside chatter | The ambient color spoken between navigation cues: entering parks and forests, named river crossings, mountain passes, museums and attractions, and parody billboards. One master switch turns it all on or off, and each kind has its own switch below it. Safety and navigation speech is never affected, and town names have their own Place callouts setting. |
| Place callouts | How much the co-driver says about places along the road. Sparse, the default, speaks only the town names that explain a speed limit change, like Entering Strawberry right before its 35. All adds the towns the route passes through or skirts. Off silences place names entirely. Speed limit announcements themselves are never affected, and no tier ever reads out every place on the map. |
| Menu position announcements | When on, menus say the position, like 3 of 10, after each option. Turn off to hear only the option. |
| Driving event voice | Routes road events through the main voice or a separate software voice when available. |
| Speech rate | Appears only when the current voice source supports rate changes. |
| Speech pitch | Appears only when the current voice source supports pitch changes. |
| Speech volume | Appears only when the current voice source supports volume changes. |
| Speech voice | Appears only when selectable voices are available. |
| Weather source | Switches between simulated weather and live city conditions when available. |
| Live weather controls calendar | When on, live weather uses today's real date and season. When off, live conditions continue while the career date advances at midnight and its seasons pass. |

Online settings include:

| Setting | Purpose |
| --- | --- |
| Profile sharing | One optional public setting covers the drivers board, eligible profile details, official achievements, automatic road-journal posts, and the updates feed. It is off until you connect your orinks.net driver and turn it on. The game never publishes the full save, money, coordinates, active cargo details, real name, or precise live location. Detailed career statistics appear only after orinks.net accepts a validated private cloud backup; without one, the public profile remains available but omits those statistics. Turning Profile sharing off stops local posting immediately and hides the public profile independently of Cloud backup. |
| Back up saves to your orinks.net account | After each game save, upload that career to your own orinks.net account so you can restore it on another computer or after losing this one. Off until you turn it on, and separate from Profile sharing: backups are private to your account and never become public downloads. orinks.net validates each revision before accepting and signing it. It uses the same one-time sign-in as your driver profile, so set that up first. The last ten accepted backups of each career are kept. |
| Restore a cloud backup | Lists the careers backed up to your account, newest first, and brings one onto this computer. Freight Fate verifies the server signature before replacing anything. A missing, altered, or unsupported signature leaves the local save untouched. A successful restore keeps the replaced save beside it as a fallback file and signs the restored copy for this computer. If the same career was played on two computers, this menu is also where you choose which accepted copy wins. |
| Discord presence | Show broad activity in Discord (menu, terminal, driving, resting, delivering) with high-level route and cargo. Only general game status is shared, never your saves or personal details. On by default; no effect if Discord is closed. Works without a driver profile. |

The main menu also has a Drivers online item that reads the same public board:
each driver's name, what they are doing, and how fresh the report is. Viewing
the board shares nothing about you and does not require sharing to be on.

## Audio, Speech, And Accessibility

Freight Fate is built to be playable by ear. Menus, status screens, update
flows, driving alerts, route information, and settlement summaries are available
through the game's audio and text output. The window mirrors the same
core menu and status information as plain text.

Freight Fate can use NVDA, JAWS, SAPI, VoiceOver, Speech Dispatcher, and other
available voices. It chooses a voice that is usable on the current machine. If
the preferred screen reader is not running, the game can fall back to another
available voice.

Driving events can use a separate software voice when available, so road alerts
do not fight with a screen reader's own speech.

Audio is layered by category:

| Category | Examples |
| --- | --- |
| UI | Menu movement, selection, warning, cash, pause, unpause, and notification sounds. |
| Engine | Engine start, shutdown, idle, and RPM-tracking running engine audio. |
| Vehicle | Horn, gear shift, parking brake, brake air, road noise, collision, rumble strip, and fuel pump sounds. |
| Weather | Rain, snow, wind, thunder, and fog sounds. |
| Route events | Hazards, construction zones, inspections, state crossings, traffic slowing, and toll charges. |
| Facilities and stops | Facility gates, docks, rest stops, and weigh station lanes. |
| Music | Menu, facility, day-driving, and night-driving music pools. |
| In-cab radio | Keyboard-controlled driving music and safe station status. |

Speech, gameplay cues, and warnings are the primary access path. Radio, music,
and ambience sit behind those cues and can be adjusted separately. The in-cab
radio defaults to built-in Freight Fate music and streamer-safe mode. Bracket
tuning moves through stations the truck can currently receive from the checked-in
catalog, using the route's approximate position and each station's range. The
Radio status screen lists the currently receivable stations.

The Freight Fate Roadhouse and the Night Line have their own hosts, who break
in between songs. Fictional regional stations cover markets across the map --
country, classic rock, and blues and soul formats with their own song pools --
and behave like real FM signals: full volume near the market, thinner audio and
static crackle at the fringe of the range, and a fade to static as you drive
past the edge. When a station drops out of range the radio announces it and
falls back to the Roadhouse, which is receivable everywhere along with the
Night Line and the satellite fallback.

Real public stream stations, including AFN choices, are hidden unless you turn on
real streams and turn off streamer-safe mode. When the BASS audio backend is
available, those stations play from their public stream URLs. If a selected
station cannot play, the radio falls back safely instead of blocking the drive.

You can put your own music on the dial. Drop M3U or M3U8 playlist files into
the Playlists folder next to your saves (the game creates it on first run) and
each file becomes a station under Your playlists, named from the playlist. The
entries can point at files anywhere your computer can read, including network
drives, and the usual formats all play: mp3, ogg, opus, flac, aac, and wma.
The station remembers its place while you tune away during a drive, and a file
that will not open is skipped rather than stopping the music. Personal
playlists play only when streamer-safe mode is off, because the game cannot
vouch for what your files are licensed for. Ctrl+Right bracket jumps straight
to the category.

The dial is grouped into categories -- route playlist, Freight Fate stations,
your playlists, terrestrial, AFN, and satellite -- and Ctrl with a bracket key
jumps between them, so twenty-five AFN stations never again stand between you
and the local dial.

Useful accessibility patterns:

- Use F1 when you are unsure what the selected item does.
- Use Space, F, C, R, V, and Tab while driving instead of waiting for automatic
  reminders.
- Use the status menu when you want reviewable lines instead of one long status
  message.
- Use the Radio status screen when you want the current station list before
  tuning.
- Lower music or ambience if speech or route cues are hard to follow.
- Treat route stop menus as data-backed: if a stop does not list fuel, repair,
  or sleep, that stop is not currently documented as supporting that action.

## Troubleshooting

If the game will not start after extracting a Windows build, check whether your
antivirus quarantined the unsigned `FreightFate.exe`. Restore it or add an
exclusion for the extracted game folder.

If Check for updates says the copy is running from source, download a packaged
release archive from the releases page and play from that folder.

If an update cannot reach the server, check your internet connection and try
again later. The game writes packaged-build logs to `logs/game.log`, which can
help when reporting update or startup problems.

If your save is missing after extracting or updating, look for another nearby
`saves` folder and copy or move the whole `saves` folder into the active
`FreightFate` folder. Keep `profile.key` with the profile files.

If the engine will not start because the tank is empty, the out-of-fuel rescue
can bring enough fuel to continue and charges the career balance.

If you miss a rest stop, slow down, back up carefully, stop at the route point
of interest, and press T when the stop supports a menu.

## Release Notes And More Data

Stable and snapshot release notes are on the
[Freight Fate releases page](https://github.com/Orinks/Freight-Fate/releases).
The in-game What's new reader can also review notes for an available update.

For deeper data reference, see:

- [Route, Stop, And Corridor Data](route-stop-data.md).
- [Freight Market And Facility Data](freight-market-facilities.md).
