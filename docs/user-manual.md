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
| New career | Starts name entry and home-terminal selection. |
| Achievements | Reviews earned and locked achievements for a saved career. |
| How to play | Opens the built-in help reader. |
| Settings | Opens gameplay, audio, speech and weather, and update settings. |
| Quit | Exits the game. |

A new driver starts with 5,000 dollars, the standard rig, a full tank, a fresh
career record, and a company terminal or yard in the chosen metro service area.
The home-terminal picker starts with a region list, then opens the cities in
that region. Chicago is the default starting area, but any listed terminal can
be your starting city.

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
| Garage | Refuel, repair, service tires, wash the truck, buy upgrades, buy trucks, or switch owned trucks. |
| Request pay advance | Draw cash against your next load when you are broke. |
| Career stats | Browse level, reputation, deliveries, career totals, rest status, and hours of service line by line. |
| Truck status | Review truck model, fuel, tank size, damage, tire wear, and road grime. |
| Time and weather | Review the clock, career day, and current city weather. |
| Sleep 10 hours | Rest at the terminal and reset hours of service. Warns first if you are already rested, since sleeping then only advances the clock. |
| Save game | Save the current career. |
| Settings | Open settings categories. |
| Quit to main menu | Save and return to the title menu. |

The garage can do partial fuel, repair, or tire work when you cannot afford
the full service. Normal miles add slow tire wear and road grime, even when
you drive cleanly.

If your balance goes negative and you cannot afford fuel, **Request pay
advance** fronts you cash against your next load (also available at in-trip
rest stops, drawn against the load you are hauling). The advance is offered
only while cash is low, is capped, and is repaid automatically out of your
next delivery settlement, so a negative balance is never a dead end.

The garage sells:

| Upgrade Or Truck | Effect |
| --- | --- |
| Engine tune | Adds pulling power. |
| Aerodynamic kit | Improves highway fuel economy. |
| Long-range tank | Adds 50 gallons of capacity. |
| Reinforced brakes | Helps the brakes resist fade longer. |
| Heavy hauler | Adds more torque and a 200-gallon tank, with worse aerodynamics and higher fuel use. |

Upgrades are fleet packages and apply to every truck you own.

## Dispatch And Jobs

The dispatch board lists jobs from local freight facilities. A metro area can
include company yards, ports, intermodal ramps, parcel hubs, warehouses, cold
storage, food processors, farms and grain elevators, manufacturing plants,
construction yards, mines, lumber or paper facilities, cross-docks, and other
freight locations.

Each job lists:

- Cargo and weight.
- Origin facility.
- Destination facility.
- Distance.
- Pay.
- Deadline.
- Equipment type.
- Market note when the cargo market is tight or loose.
- Endorsement requirement when one applies.

Early drivers mostly see shorter regional work. Higher levels widen the
distance cap and unlock more variety.

Deliveries earn money, experience, reputation, and career stats. Leveling up can
unlock longer dispatch distances, better early-career minimum pay, more cargo
variety, refrigerated freight at level 2, heavy-haul freight at level 3, and
high-value freight at level 4.

## Pickup, Loading, And Route Planning

After accepting a dispatch, you drive a local pickup leg from the terminal to
the shipper. At the pickup gate:

1. Stop the truck.
2. Open the pickup facility menu.
3. Check in at the shipping office.
4. Load cargo at the assigned dock.
5. Depart for the destination after the trailer is loaded and sealed.

Check-in takes 15 in-game minutes. Loading takes 60 in-game minutes. Both count
as on-duty time.

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
| Down arrow, hold | Brake. With simple automatic direction changes, keep holding it after stopping to select reverse and back slowly. With deliberate direction changes, release it and press again. |
| B, hold | Emergency brake. |
| E | Start the engine. Stop the engine only below 5 miles per hour. |
| P | Release or set the parking brake. |
| K | Start or cancel automatic speed control. It uses adaptive cruise on open roads and speed keeper in low-speed zones. It pauses through the planned pickup and resumes once the loaded truck is rolling. Braking elsewhere also cancels it. |
| Plus / Minus | Raise or lower the open-road cruise target by 5 mph while automatic speed control is active. The keypad Plus and Minus keys work too. |
| X | Arm or cancel the next exit when it is close enough. |
| T | Open the route point-of-interest menu when stopped at a supported stop. |
| J | Toggle the engine brake. |
| H | Hold to sound the horn; release to stop it. |
| Space | Report speed, gear, RPM, active speed-control mode, open-road target, air pressure, and brake state. |
| S | Report the posted speed limit here, the zone if any, and how far over you are. |
| Tab | Open the driving status menu. |
| F | Report fuel level and estimated range. |
| C | Report clock, deadline, estimated arrival, and hours of service. |
| R | Report route progress and GPS context. |
| Shift+R | Report the next listed highway exit. |
| V | Report weather and forecast. |
| L | Report lane position when lane drift is enabled. |
| A | Repeat the last route announcement, in case you missed it. |
| U | Report what is coming up: imposed speed limits, stops, and exits ahead. |
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
- Engine braking.
- Grades and terrain.
- Brake heat and fade.
- Fuel burn.
- Damage that reduces performance.

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

## Road Events, Weather, And Rest Stops

The road can report traffic, construction, state lines, city pass-throughs,
checkpoints, toll points, route stops, and weather changes.

Hazards can happen while moving. When a "Brake now" warning appears, slow below
25 miles per hour quickly to avoid a collision. Fatigue shortens the reaction
window.

Construction and traffic zones lower the speed limit. Speeding in a
construction zone can trigger enforcement.

Posted speed limits come from real map data where available and change along a
corridor; a change is announced as reduced or raised, and named near a city when
the game is using a city-approach fallback. State troopers patrol some
stretches, hotter on busy interstates, in construction, and at night. Speed
badly inside a patrol and a trooper may pull you over: signal with X (the same
key as an exit), brake to a stop on the shoulder, and sit through a license and
logbook check that ends in an on-the-spot ticket or a warning.
Ignoring the lights is logged as evasion and costs far more. Speeding the
patrols do not catch still adds a quieter charge at delivery settlement.
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
an exit. Press X to signal for the exit, slow to 45 miles per hour or less, and
brake to a stop at the end of the ramp.

Destination exits work the same way. When your delivery exit is ahead, the game
announces the signed exit and toward cities, marks it as the destination exit,
and tells you to press X. If automatic speed control is active, the destination-exit
callout cancels the whole session so you can take manual speed control. If you miss the destination
exit, the delivery does not complete; back up until the exit is ahead again,
then press X to take it.

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
fuel or repair. A weigh station is for inspection, not food or sleep. Parking
labels describe confidence, not a live guarantee that a space is open right
now. Late at night, a sleep-capable stop may be full.

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

Fatigue rises while driving, faster at night. Drowsiness adds yawn and rumble
strip cues and makes hazards harder to react to. Once fatigue is severe you
start to nod off: a rumble-strip jolt and a warning give you a brief window to
steer or brake and stay awake. Catch it and you carry on; miss it and you drift
onto the shoulder, taking damage and losing speed, and a third miss in a row
forces you off the road. A 30-minute break reduces fatigue; a proper 10-hour
sleep clears it. Plan your rest before you get there.

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
| Tab | Grouped driving status screens. |

Tab opens the Driving status menu. It has three review screens:

| Screen | Information |
| --- | --- |
| Route | Current route status lines from the active drive. |
| Driver | Driver name, money, load, objective, truck fuel and damage, transmission, fatigue, hours, and deadline. |
| Map | Route cities, highways, progress, next guidance, upcoming stops, map points, and toll exposure. |

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
| Emergency shoulder sleep | Rest on the shoulder when stopped away from route points; warnings get stronger when hours or fatigue are urgent. |
| Settings | Open settings during the drive. |
| Abandon job | Pay a penalty and return to the origin city. |
| Save and quit to main menu | Save the active drive and resume it later. |

Freight Fate saves at terminals, at supported route save points, when quitting
to the main menu, and during important trip state changes. Continue latest
career can resume a saved pickup objective, pickup drive, pickup facility visit,
or loaded delivery.

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
| Dock and deliver | Complete the delivery and open settlement. |
| Check paperwork | Review facility, cargo, payout, deadline, damage, tolls, approved charges, driver charges, and net pay before settlement. |
| Check arrival status | Review facility, cargo, speed, and next step. |

Settlement reports cargo delivered, trip time, on-time status, gross pay,
carrier-paid or reimbursed charges, driver-responsibility charges, net driver
pay, money after settlement, fuel, truck damage, career messages, and
achievements.

Tolls and approved accessorial charges are carrier settlement items. They are
reported for transparency but do not reduce driver pay. Driver-caused charges,
such as speeding fines, can reduce driver pay. Hitting the delivery window
earns a flat ten percent on-time bonus, the way real shipper scorecards pay
for service: arriving hours early pays no more than making the appointment.
Late delivery and cargo damage reduce pay.

## Settings

### Speed keeper

In low-speed zones where adaptive cruise is unavailable, such as facility access roads, gate queues, and work zones, pressing K starts automatic speed control in speed-keeper mode. It holds your current speed at or below the zone limit and creeps behind queued traffic, so the accelerator does not need to stay held down. On the open road it automatically changes to adaptive cruise and accelerates toward the posted limit, or restores the cruise target you selected earlier. Entering another restricted zone changes back to the speed keeper. If you start it during the deadhead, the planned pickup pauses the session while you check in and load, keeps it through a save, and resumes it after departure once the truck is rolling. Plus and Minus adjust the remembered open-road cruise target in either mode. Any brake input outside that planned pickup, a hazard, or pressing K again cancels the whole session so it cannot restart unexpectedly. Speed keeper is on by default and can be turned off in Settings, Gameplay.

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
| Music volume | Background music volume. |
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

Speech, gameplay cues, and warnings are the primary access path. Music and
ambience sit behind those cues and can be adjusted separately.

Useful accessibility patterns:

- Use F1 when you are unsure what the selected item does.
- Use Space, F, C, R, V, and Tab while driving instead of waiting for automatic
  reminders.
- Use the status menu when you want reviewable lines instead of one long status
  message.
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
