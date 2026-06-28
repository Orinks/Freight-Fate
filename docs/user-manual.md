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
6. Open the dispatch board, accept a job, and follow the current objective.

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

The normal career loop is:

1. Start or continue a career.
2. Pick a dispatch from your terminal's dispatch board.
3. Drive from the terminal to the pickup facility.
4. Check in, load the cargo, and choose a destination route.
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
| Business status | Review company-driver or owner-operator status. |
| Garage | Refuel and repair company equipment; owner-operators can also buy upgrades, buy tractors, switch owned tractors, add trailer programs, or buy trailers after own authority. |
| Request pay advance | Draw cash against your next load when you are broke. |
| Career stats | Review level, reputation, deliveries, and career totals. |
| Truck status | Review truck model, fuel, tank size, and damage condition. |
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

If your balance goes negative and you cannot afford fuel, **Request pay
advance** fronts you cash against your next load (also available at in-trip
rest stops, drawn against the load you are hauling). The advance is offered
only while cash is low, is capped, and is repaid automatically out of your
next delivery settlement, so a negative balance is never a dead end.

After the owner-operator buy-in, the garage sells:

| Upgrade, Truck, Program, Or Trailer | Effect |
| --- | --- |
| Engine tune | Adds pulling power. |
| Aerodynamic kit | Improves highway fuel economy. |
| Long-range tank | Adds 50 gallons of capacity. |
| Reinforced brakes | Helps the brakes resist fade longer. |
| Heavy hauler | Adds more torque and a 200-gallon tank, with worse aerodynamics and higher fuel use. |
| Reefer trailer program | Opens refrigerated and fresh food cargo for owner-operators. |
| Flatbed trailer program | Opens steel, machinery, construction, lumber, and paper cargo for owner-operators. |
| Bulk trailer program | Opens grain, farm inputs, and loose bulk cargo for owner-operators. |
| Owned trailer | Own-authority drivers can buy dry van, reefer, flatbed, or bulk trailers. Matching direct freight uses an owned-trailer reserve at settlement. |

## Dispatch And Jobs

The dispatch board lists jobs from local freight facilities. A metro area can
include company yards, ports, intermodal ramps, parcel hubs, warehouses, cold
storage, food processors, farms and grain elevators, manufacturing plants,
construction yards, mines, lumber or paper facilities, cross-docks, and other
freight locations.

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

Deliveries earn money, experience, reputation, and career stats. Leveling up can
unlock longer dispatch distances, better early-career minimum pay, more cargo
variety, refrigerated freight at level 2, heavy-haul freight at level 3,
high-value freight at level 4, and business-path ranks through level 30.

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

Route planning appears after pickup and loading. Each route option lists:

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
| Down arrow, hold | Brake. In automatic mode, holding it while stopped reverses slowly. |
| B, hold | Emergency brake. |
| E | Start the engine. Stop the engine only below 5 miles per hour. |
| P | Release or set the parking brake. |
| K | Set or cancel adaptive cruise control. Braking also cancels it. |
| Plus / Minus | Raise or lower the set cruise speed by 5 mph while cruise is engaged. |
| X | Signal for or cancel the next exit when it is close enough. |
| T | Open the route point-of-interest menu when stopped at a supported stop. |
| J | Toggle the engine brake. |
| H | Sound the horn. |
| Space | Report speed, gear, RPM, air pressure, and brake state. |
| S | Report the posted speed limit here, the zone if any, and how far over you are. |
| Tab | Open the driving status menu. |
| F | Report fuel level and estimated range. |
| C | Report clock, deadline, estimated arrival, and hours of service. |
| R | Report route progress and GPS context. |
| Shift+R | Report the next listed highway exit. |
| V | Report weather and forecast. |
| L | Report lane position when lane drift is enabled. |
| A | Repeat the last route announcement, in case you missed it. |
| U | Report what is coming up: imposed speed limits, patrols, stops, and exits ahead. |
| F1 | Show the driving control list and current objective. |
| Escape | Open the pause menu. |

Manual transmission adds:

| Key | Action |
| --- | --- |
| Left Shift or Right Shift, hold | Clutch. |
| 1 through 9, then 0 | Gears 1 through 10. |
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
- Engine braking.
- Grades and terrain.
- Brake heat and fade.
- Fuel burn.
- Damage that reduces performance.

A loaded tractor-trailer pulls away gradually. The automatic transmission holds
the first few gears long enough to feel the weight, then settles into normal
highway acceleration.

Repeated hard braking can use air faster than normal driving. If low air is
reported, stop safely, set the parking brake, and let pressure build.

Adaptive cruise requires the engine to be running and the truck to be moving at
least 20 miles per hour. Press K to set cruise at your current speed. Once it is
engaged, Plus and Minus raise and lower the set speed by 5 miles per hour, just
like the accelerate and coast buttons on a real truck, so you can dial the
target up to the speed you want without having to reach it manually first. The
truck then accelerates up to a higher set speed on its own. Cruise will not hold
more than 5 miles per hour over the posted limit, so it keeps you legal even if
you set it higher. Weather can increase the following gap. Simulated nearby
vehicles can make cruise reduce speed when a slower vehicle is in your lane.
Cruise does not steer, change lanes, or replace your attention.

## Road Events, Weather, And Rest Stops

The road can report traffic, construction, state lines, city pass-throughs,
checkpoints, toll points, route stops, and weather changes. Morning and
afternoon rush hours can make metro corridors busier and slower. Dense
metro/checkpoint corridors can also produce random road hazards a little more
often than open-country stretches.

Hazards can happen while moving. When a "Brake now" warning appears, slow below
25 miles per hour quickly to avoid a collision. Fatigue shortens the reaction
window.

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
night. CB radio chatter can warn you a few miles before a patrol window; press
U to check upcoming patrols along with other route guidance. Speed
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
Adaptive cruise will not engage on low-speed local roads such as facility
access roads, construction, or heavy traffic; drive those manually.

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
date, season, and temperature follow the real-world calendar instead.

Stops are reported as you approach them. A one-mile cue tells you when to take
an exit. Press X to signal for the exit. With lane drift off, that also sets the
exit lane; with lane drift on, steer right when prompted. Slow to 45 miles per
hour or less, and brake to a stop at the end of the ramp. If you reach the gore
too fast, without signaling, or without the exit lane set, you stay on the
highway and the game tells you what went wrong. The timing is generous so the
sequence is about preparation, not twitch input. The game can also tell you when
traffic boxes you out of the lane, so you know to recover at the next safe exit
instead of fighting the maneuver. The
game gives a short pull-in moment before the stop menu opens, so holding Down
Arrow to brake does not skip the first menu option.

Destination exits work the same way. When your delivery exit is ahead, the game
announces the signed exit and toward cities, marks it as the destination exit,
and tells you to press X and slow down. If lane drift is on, it also tells you
when to move right for the exit lane. If
adaptive cruise is set, the destination-exit callout cancels cruise so you can
take manual speed control. If you miss the destination exit, the delivery does
not complete; back up until the exit is ahead again, then signal and take the
exit correctly.

Ordinary highway exits that do not lead to a current action are not announced
during the drive. Press Shift+R if you want the next listed exit for route
context.

Stop actions depend on that stop's data. A stop may offer:

- Fuel.
- Food and coffee.
- A 30-minute break.
- 10-hour sleep.
- Repairs.
- Roadside assistance or towing.
- Inspection check-in.
- Save point.

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
pause menu only when you are stopped away from a route point of interest and
the game sees a real hours or fatigue problem without a suitable stop visible.
The confirmation explains that 10 hours pass, the hours clock resets, fatigue
only improves to a poor-rest floor, a parking ticket is possible, minor truck
damage is possible, and the delivery deadline keeps running.

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
| Y | Speak radio station, source, signal or fallback state, volume, and streamer-safe status. |
| Tab | Grouped driving status screens. |

Tab opens the Driving status menu. It has five review screens:

| Screen | Information |
| --- | --- |
| Route | Current route status lines from the active drive. |
| Driver | Driver name, money, load, objective, truck fuel and damage, transmission, fatigue, hours, and deadline. |
| Map | Route cities, highways, progress, next guidance, upcoming stops, map points, and toll exposure. |
| Radio | Current station, stream-safety state, approximate reception position, and currently receivable stations. |
| Logbook | Today's duty totals and recent Record of Duty Status entries. |

Inside a status screen, Up and Down move line by line, Enter repeats the current
line, and Escape returns to the status screen list.

## Pause, Save, And Resume

Escape opens the pause menu during a drive. Public pause choices include:

| Choice | What It Does |
| --- | --- |
| Resume driving | Return to the active drive. |
| Trip status | Review cargo, objective, route progress, time used, and air status. |
| Controls and help | Open the how-to-play reference at the driving keys, page by page, without leaving the drive. |
| Call a roadside mechanic | Patch severe truck damage enough to continue, at a high cost. |
| Emergency shoulder sleep | Appears only when the game detects a true hours or fatigue emergency. |
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
and deliver**. On highway deliveries, take the announced destination exit first.
You can also review paperwork before settling.

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
such as speeding fines, can reduce driver pay. Early delivery can increase pay.
Late delivery and cargo damage reduce pay.

## Settings

Settings are grouped into categories. In a settings category, Up and Down choose
a setting, Right arrow or Enter changes it forward, Left arrow changes it
backward, and Escape returns to the category list. Changes are saved as they
are made.

Gameplay settings include:

| Setting | Purpose |
| --- | --- |
| Units | Switch speed and distance between miles and kilometers. |
| Transmission | Switch between automatic and manual transmission. |
| Trip pacing | Choose relaxed, standard, or fast pacing. |
| Hours of service | Choose realistic or relaxed hours rules. |
| Lane drift | Choose whether lane drift is off, light, or realistic. When on, the rumble strip is panned to the side you have drifted toward, so the side you hear it on is the side to steer away from. |
| Discord presence | Show broad activity in Discord (menu, terminal, driving, resting, delivering) with high-level route and cargo. Only general game status is shared, never your saves or personal details. On by default; no effect if Discord is closed. |

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
| Menu position announcements | When on, menus say the position, like 3 of 10, after each option. Turn off to hear only the option. |
| Driving event voice | Routes road events through the main voice or a separate software voice when available. |
| Speech rate | Appears only when the current voice source supports rate changes. |
| Speech pitch | Appears only when the current voice source supports pitch changes. |
| Speech volume | Appears only when the current voice source supports volume changes. |
| Speech voice | Appears only when selectable voices are available. |
| Weather source | Switches between simulated weather and live city conditions when available. |

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

Real public stream stations, including AFN choices, are hidden unless you turn on
real streams and turn off streamer-safe mode. When the BASS audio backend is
available, those stations play from their public stream URLs. If a selected
station cannot play, the radio falls back safely instead of blocking the drive.

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
