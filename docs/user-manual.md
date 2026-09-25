# Freight Fate Player Manual

Freight Fate is an audio-first trucking game. You build a career by accepting
freight, driving to the shipper, loading the trailer, running the route, and
delivering before the deadline.

This manual describes the game as it currently ships with your build. It
focuses on what players can do from the menus and while driving. If you are
returning from an earlier version, read What Changed Recently first.

## Quick start

1. Download the newest stable build from the
   [Freight Fate releases page](https://github.com/Orinks/Freight-Fate/releases).
2. On Windows or Linux, extract the archive into a folder you control, open
   the extracted `FreightFate` folder, and run `FreightFate.exe` on Windows or
   `FreightFate` on Linux.
3. On macOS, the stable archive ends in `-macos.zip`. To test Career 1.9 on
   an Apple Silicon Mac, choose the newest Career 1.9 prerelease and download
   the archive ending in `-macos-arm64.zip`; Career 1.9 does not provide an
   Intel Mac build. Extract the archive and move `FreightFate.app` to
   Applications. Apple has not notarized this build, so macOS may block it the
   first time you open it. Open System Settings, Privacy & Security, scroll to
   the message about Freight Fate, choose Open Anyway, and confirm Open. The
   button appears for about an hour after macOS blocks the launch. VoiceOver
   reads these controls. You only need to do this for the first launch of a
   newly downloaded app.
4. Choose **New career**, enter a driver name, pick a home region, and pick a
   home terminal.
5. Listen to the first-day briefing, open the dispatch board, accept a job,
   and follow the current objective.

In the Windows and Linux archive downloads, saves, settings, save identity
files, and packaged-game logs live in the `saves` folder inside the game
folder. The Linux AppImage keeps them in `~/.local/share/FreightFate`
(or under `XDG_DATA_HOME` if you set it). On macOS the app cannot write beside itself,
so those files live in `~/Library/Application Support/FreightFate` instead.

## What changed recently

If you have driven an earlier version, check these control and settings changes
before starting a new drive.

- **Reverse takes a fresh press, held.** Holding the brake through a stop no
  longer selects reverse, and a quick tap at a stop no longer selects it
  either. Stop fully, release the Down arrow, then press it again and hold it
  for a moment. The reverse beep starts, and keeps going the whole time you
  are in reverse. The same press-and-hold on the Up arrow brings forward gear
  back and says so. This is now true whichever direction change style you
  have set. If you latch the throttle by habit while you are doing it, the
  shift still wins: coming out of reverse always beats the latch.
- **Braking cancels automatic speed control, and Shift+K brings it back.**
  Any service brake or emergency brake press drops it immediately and says so.
  Shift+K resumes the last speed you had set, like the stalk in a car.
- **Comma and Period walk the whole message history.** Comma no longer only
  repeats the last line. A is still the "what did the route just tell me" key.
- **Pulling the parking brake at speed is a violent act.** Above a crawl the
  valve slams the spring brakes on: a screech, a hard stop, and flat spots
  ground into the tires that scale with how fast you were going. Set it when
  you are stopped, like a real hand.
- **The radio dial moved to the Page keys.** Page Down tunes to the next
  station and Page Up to the previous; semicolon and apostrophe still work.
  The bracket keys now switch message review categories instead.
- **Lane keeping replaced Lane drift**, and the old values read backwards.
  Your setting carried over to the value that behaves identically. See
  Settings.
- **Your company tractor is assigned by dispatch.** New hires get the trainer
  rig; better equipment arrives with seniority. Owner-operators still buy
  their own.
- **Each truck keeps its own condition.** Wear, damage, and fuel stay with
  the truck they happened to, so swapping tractors no longer carries your
  wear or your empty tank to the next rig.
- **The hours clock answers one question at a time.** Alt+A, Alt+S, and Alt+D
  each ask a single question; C keeps the clock, the deadline, and whichever
  limit comes first.
- **Traffic lights keep a steady cycle, and every change is spoken.** Each
  ramp-end light keeps its timing while you approach. Reds and greens last
  long enough to stop and pull a loaded truck away; entering on green or
  yellow is legal, and cross traffic clears before green.
- **The dash warns you about your own speed.** A few miles per hour over the
  posted limit chimes softly and names the limit, faster the further over you
  go. It is a courtesy alert with no setting; it starts more than 7 miles per
  hour over the limit.
- **A dropped speed limit gives you braking time.** When the posted limit
  steps down, enforcement gives a loaded truck time to
  comply, as long as you are off the throttle and slowing.
- **An unpaid fine becomes a balance you owe**, collected a quarter at a time
  out of later settlements instead of money vanishing from your cash. See
  When You Owe Money.

- **Settings have moved or changed names.** Speed keeper is under Gameplay,
  Driving assistance. Lane and edge cue volume is under Audio, directly below
  Gameplay cues volume; it was called Lane and edge cue prominence. Weather,
  traffic, and parking sources are under Gameplay, World and traffic.
- **Driving speech was called Speech verbosity.** Saved terse and normal
  choices become Quiet and Standard. The former Coaching choice also becomes
  Standard because those two choices sounded the same.
- **The old Realistic driving mode was retired.** It was the fastest pacing,
  rather than the most true to life. Old saves switch to Standard, and the
  setting explains the change.
- **Latching pedals is now Latching brake.** Any enabled old value keeps the
  brake latch on; the throttle no longer latches.

## Install, updates, and snapshots

Freight Fate ships as portable archives. There is no installer.

Release archives are named by platform when that platform is available:

| Platform | Archive Name |
| --- | --- |
| Windows | `FreightFate-<version>-windows-portable.zip` |
| macOS stable | `FreightFate-<version>-macos.zip` |
| Career 1.9 macOS, Apple Silicon | `FreightFate-<version>-macos-arm64.zip` |
| Linux | `FreightFate-<version>-linux-x64.tar.gz` |
| Linux (AppImage) | `FreightFate-<version>-linux-x86_64.AppImage` |
| Linux ARM64 | `FreightFate-<version>-linux-arm64.tar.gz` |
| Linux ARM64 (AppImage) | `FreightFate-<version>-linux-aarch64.AppImage` |

On Linux you can pick either download. The tarball extracts to a portable
folder, exactly like Windows. The AppImage is a single file: mark it
executable (`chmod +x`) and run it, no extraction needed. Both work on any
current 64-bit distribution: every Career 1.9 snapshot is started on
Ubuntu, Debian, Fedora, Arch, and openSUSE before it is published.

The Linux downloads come in two kinds of processor. The `x64` and `x86_64`
files are for ordinary PCs. The `arm64` and `aarch64` files are for ARM
computers: the Blazie BT Speak and BT Braille notetakers, a Raspberry Pi,
and other ARM64 Linux machines. If you are not sure which you have, run
`uname -m` in a terminal: `x86_64` means the PC files, `aarch64` means the
ARM64 files. The in-game updater only ever offers the kind you are
running. Speech
comes through Speech Dispatcher, which your screen reader already uses, and
sound plays through PulseAudio or PipeWire. An AppImage cannot write into itself,
so its saves live in `~/.local/share/FreightFate` (or under `XDG_DATA_HOME`
if set) instead of a `saves`
folder beside the game. The in-game updater handles the AppImage by
downloading the new version and replacing the `.AppImage` file itself,
then restarting. That needs the folder holding the AppImage to be writable
by your user account; when it is not, the game keeps the downloaded update
in your home folder and tells you where it is so you can finish the
install yourself.

The Career 1.9 Mac archive runs on Apple Silicon Macs. It does not run on
Intel Macs. On an Intel Mac, the in-game updater will not offer the Apple
Silicon archive.

Use the newest stable release for normal play. Stable releases are numbered,
such as `v1.6.0`.

Career 1.9 snapshot builds are tester prereleases named `1.9-tester-YYYYMMDD`.
They let you try newer 1.9 work sooner, but may have rough edges. They are not
the public 1.8 snapshots named `nightly-YYYYMMDD`. A career saved in a
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

## Main menu and career flow

The main menu can include:

| Choice | What It Does |
| --- | --- |
| Continue latest career | Loads the newest readable save. Careers saved before 1.9 stay in their own era and cannot be continued here; the game explains that in full and offers to start a new one. |
| Choose career | Opens a list of saved careers. |
| Manage careers | Opens reset and delete actions with confirmation. |
| New career | Starts name entry, career start choice, and home-terminal selection. |
| Achievements | Reviews earned and locked achievements for a saved career. |
| Online | The public list of drivers on duty, your account-wide achievement collection, your orinks.net account, cloud backup and restore, and sharing choices like Mastodon and Discord, all in one place. |
| Learn game sounds | Plays any cue the road uses, with what it means and what to do about it. Also on the pause menu while you drive. |
| How to play | Opens the built-in help reader. |
| Settings | Opens gameplay, audio, speech and weather, and update settings. |
| Quit | Exits the game. |

A new career asks you to choose a start path after entering a driver name.
Company-driver starts use assigned carrier equipment, carrier-paid fuel and
routine repairs, and different wage and dispatch tradeoffs. The owner-operator
start is the harder way to begin, not a head start: you own your truck and
every operating cost is yours, with higher gross revenue and limited working
capital to absorb a bad week. It changes who pays, not how far along you are.
Both starts begin at level one and climb the same career.

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
with 18,000 dollars working capital, a brand-new truck of your own with a full
tank and nothing worn, and owner-operator costs already active.
The home-terminal picker starts with a region list, then opens the cities in
that region. Each start has a suggested default city, but any listed terminal
can be your starting city.

After the home terminal is chosen, the terminal repeats a first-day briefing
until the first dispatch is accepted. It names the carrier or owner-operator
setup, the current terminal, who pays normal equipment costs, and the first
objective: choose an unlocked dispatch, reach the shipper, and start a clean
record with dispatch. The briefing opens as a screen of lines, so any sentence
can be read again with the arrows.

After that first dispatch, the terminal adds **Career plan**. This opens the
current career objective as a screen of lines, the step first, then how it
should shape dispatch choices. Early
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

## Menu controls

Most menus use the same keyboard pattern:

| Key | Action |
| --- | --- |
| Up arrow or Down arrow | Move through choices. |
| Enter or Space | Activate the selected choice. |
| Escape | Go back, cancel, or repeat a status message when leaving is not useful. |
| Home or End | Jump to the first or last choice. |
| Letter or number | Jump to the next choice starting with that character. |
| F1 | Show help for the current item. |
| Comma | Review earlier speech, except while typing text. |
| Period | Move toward newer speech, except while typing text. |

Menus provide the title, selected item, and item position, such as `2 of 6`.
F1 help explains what the current item does.

### Reviewing what the game said

The review keys work on every screen, whether you are driving, in a menu, or
reading a report. The exception is a box you are typing into, such as entering
a driver name, where the punctuation keys type instead.

| Key | Action |
| --- | --- |
| Comma | Repeat what was just said, then keep stepping back. |
| Period | Move toward newer messages. |
| Ctrl+Comma | Jump to the oldest message kept. |
| Ctrl+Period | Jump back to the newest message. |
| Left bracket or right bracket | Switch between all messages, general messages, and driving events. |
| Ctrl+C | Copy the message you are on to the clipboard. |

Each key press reads the message itself, with nothing added. The game keeps
the last 200 messages. Moving through menus is not kept, so the history holds
what happened rather than where you walked.

While you are reviewing, new announcements do not move your place. Once you
have left the review keys alone for ten seconds the game takes you as done,
so the next press starts fresh from the newest message with all categories
showing again. That way comma always repeats what was just said, rather than
picking up wherever you left off earlier in the run.

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

## Terminal and garage

Your terminal is the safe hub between jobs. Public terminal actions include:

| Choice | What It Does |
| --- | --- |
| Dispatch board | Browse freight offers from local facilities. |
| Truck dealer | Browse tractors at the local dealer. Owner-operators buy and switch here; company drivers can look at what the fleet may assign next. The intro names a local dealer when one is listed for that area. |
| Career plan | Review your next realistic career objective after the first dispatch. |
| Business status | Review company-driver or owner-operator status. |
| Garage | Refuel, repair, service tires, and wash company equipment; owner-operators can also buy upgrades, buy tractors, switch owned tractors, add trailer programs, or buy trailers after own authority. |
| Request pay advance | Draw cash against your next load when you are broke. |
| Career stats | Review level, reputation, deliveries, career totals, the endorsements you hold, your dispatch trust, your safety record and CDL status, and any balance you owe. Its last row, Citations and violations, opens the list newest first: what each was, why, what it cost, when, and where. Citations from before this build are counted but carry no reason. |
| Licenses and training | Book any credential course, from manual transmission training to the LCV certificate. F1 on a row says what the credential unlocks and how you get it: the level the carrier sponsors it at, or the level you can pay for it early. The table under Licenses and training below lists them all. |
| Truck status | Review truck model, fuel, tank size, damage and its band, tire wear, and road grime. |
| Time and weather | A screen of lines: the clock, the date and season, the career day, and the weather in the city, with the live reading's age when there is one. |
| Logbook | Review your Record of Duty Status: what you are doing now, your hours limits, today's totals, and the recent entries. |
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

### Licenses and training

Every license add-on sits in one list at the terminal, in the order the career
reaches them. Certificates are carrier training: the carrier sponsors each one
free at its listed level, and you can pay for it yourself one level earlier.
Endorsements and cards are only ever earned by course, and never before their
level. A course takes game time at the school, and hazmat and the port card
then wait on a background check that clears while you drive. F1 on any row
reads the same facts for that credential.

| Credential | Unlocks | How you get it |
| --- | --- | --- |
| Manual transmission training | A manual-spec pay differential on drives made on a manual gearbox. | Course only, 220 dollars from level 1. |
| Refrigerated certificate | Fresh food and refrigerated goods. | Free from the carrier at level 2, or 900 dollars from level 1. |
| Flatbed securement certificate | Steel products, and lumber and paper products. | Free from the carrier at level 2, or 450 dollars from level 1. |
| Heavy-haul certificate | Heavy machinery. | Free from the carrier at level 3, or 1,600 dollars from level 2. |
| High-value certificate | Electronics and packaged industrial chemicals. | Free from the carrier at level 4, or 1,300 dollars from level 3. |
| Doubles endorsement | Twin-trailer parcel freight. | Course only, 60 dollars from level 8. |
| Hazmat endorsement | Placarded hazardous materials, and bulk fuel once the tank vehicle endorsement joins it. | Course only, 185 dollars from level 10, then a background check of about 30 days. |
| Tank vehicle endorsement | Liquid food products from level 21, and bulk fuel once the hazmat endorsement joins it. | Free from the carrier at level 16, or 2,400 dollars from level 15. |
| TWIC port card | Port containers. | Course only, 125 dollars from level 18, then a background check of about 20 days. |
| LCV certificate | Turnpike doubles freight, between the states whose networks allow them. | Course only, 2,000 dollars from level 20. Needs the doubles endorsement and a clean recent record. |

Holding both the tank vehicle and hazmat endorsements is the X combination,
and bulk fuel opens the day the second one lands.

## Business status

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

You never have to take the buy-in. Once it opens, **Business status** offers
Stay a company driver: the career plan and the business reminders stop
pointing you at the truck, and the buy-in row stays there for later. Your
spoken rank titles and goals also switch to the company career ladder
(senior company and fleet ranks such as Company Fleet Captain and Freight
Fate Company Driver) instead of owner-operator prep or independent titles.
Reopen the owner-operator plan turns the reminders back on. An owner-operator
who wants out chooses Go back to company driving on the same screen. It asks
twice; the carrier takes every tractor and trailer you own, pays you for them
(the buy-in tractor for what you paid, anything bought since at its used
value), and puts you back in a carrier tractor on company wages with company
rank titles again. Nothing goes on your record, and the buy-in stays open if
you change your mind again.

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

**Truck dealer** opens directly from the terminal menu and names a local
dealer when one is listed for that area. The dispatch board
already opens the freight market, and the garage is its own terminal item, so
none of the three needs a separate drive to reach. Fuel, food, a break, sleep,
minor repairs, and paying down what you owe are also available on the road at
supported truck stops.

The garage can do partial fuel, repair, or tire work when an owner-operator
cannot afford the full service. Normal miles add slow tire wear and road
grime, even when you drive cleanly; company drivers bill tire service and
washes to the carrier.

If your balance goes negative and you cannot afford fuel, **Request pay
advance** fronts you cash against your next load (also available at in-trip
rest stops, drawn against the load you are hauling). The advance is offered
only while cash is low, is capped, and is repaid automatically out of your
next delivery settlement, so a negative balance is never a dead end. Once you
are carrying a balance and a share of every settlement is already going to
it, dispatch stops fronting cash and says why: the advance would be borrowed
against money that is already spoken for. See When You Owe Money.

As a company driver, dispatch assigns your tractor, and better equipment
follows seniority: every new hire starts in the same trainer-spec rig, then
the carrier upgrades your assignment at level 4 (a newer regional unit),
level 9 (a long-haul sleeper), level 13 (a premium tractor), and level 17
(first pick of the yard). Each hand-over is announced at settlement and
arrives fueled, serviced, and washed. Which model you get is the carrier's
call -- two drivers at the same level can be handed different iron.

Below level 9 you are a slip-seat driver with no tractor of your own. Each
dispatch, the yard hands you the best fit from a small set of spares -- a day
cab for a short turn, a sleeper when the run is too long to finish in a
shift, a heavy driveline when the load demands it -- and dispatch says which
truck you drew and why. Every spare keeps its own fuel, wear, and damage
between draws, so a fresh truck after a rough turn is the yard handing you a
different unit, not your wear disappearing. A dedicated seat comes with
seniority at level 9.

Seniority is what you have earned; dispatch trust is what the yard is
currently willing to put in your hands, and the assignment is the lower of
the two. Your dispatch trust answers to three things at once: your service
record, whether your CDL is valid, and how much you owe. While any of them is
down, equipment your level has earned can be **held back** and the yard hands
you a lesser truck. When that happens the game says so, names the tractor
your level would have got, names the one thing holding it back, and names
what gives it back. Nothing is lost -- the equipment returns when the hold
clears.

### Dispatch trust

Dispatch trust runs on four rungs, and running clean keeps you on the top one
for a whole career:

| Trust | What dispatch does |
| --- | --- |
| Full | You get the whole board. |
| Guarded | Some freight is held back, and you have fewer refusals. |
| Poor | Assigned loads whatever your level, a board down to two offers, and the good freight goes to other drivers. |
| Last chance | One assigned load at a time, no refusals, and the carrier is deciding whether to keep you. |

Low trust also slows how fast career experience arrives, and a company driver
whose reputation falls to the floor is moved to Great Lakes Training
Transport, the fleet that will still take a driver nobody else wants. Ask for
your dispatch trust from **Career stats** at the terminal, or from **Driver**
in the Tab status menu while driving; both name the rung, the reason, and the
way back.

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

## Dispatch and jobs

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

Freight destinations use mapped facilities where available and representative
local facilities elsewhere. Some mapped destinations include spoken turns on
the public roads leading to the facility. Elsewhere, the GPS gives the
available road guidance without claiming to identify an exact gate or dock.

Each job lists:

- Cargo and weight.
- The margin under or over the 80,000-pound gross-weight limit with the load
  and current fuel.
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

Deadlines are set by a dispatcher who did the arithmetic: driving time from
the route's real speeds, plus the 30-minute break, plus any 10-hour rest your
current shift clock will force before you arrive. A deadline that sounds
generous is usually covering a legal rest, and the job details say so when it
is.

Company drivers use carrier-provided trailers, so trailer program locks do not
block their approved loads. Owner-operators start with a dry van program.
Specialty cargo may say it needs a reefer, flatbed, or bulk trailer program;
add that program from the garage before accepting the load. If a load is
blocked by your trailer setup, the dispatch row starts with `Locked job`.

Own-authority drivers see direct freight on the same board. The listed pay is
direct freight gross, and the row includes a short take-home estimate before
any pay advance. If you own a matching trailer, the job row says so and
settlement uses the owned trailer reserve instead of a trailer-program charge.

Deliveries earn money, experience, reputation, and career stats. Your driving
record counts against reputation too: every citation on the record costs
four points and every serious violation ten for a game year, a major offense
twenty for good, so a bad record shows on the number dispatch, the shippers
and the business gates all read, and the points come back a year of game
time after each one. The carrier's record review and the insurer look back
the same year; only the CDL suspension ladder still counts serious
violations over three years. Every settled
load teaches a base amount of experience on top of its miles, on-time streaks
compound the lesson, delivering the cargo undamaged adds a bonus, and specialty
endorsement freight teaches half again as much per mile. Every level up hands
you something concrete: longer dispatch distances every level, refrigerated
freight at level 2, heavy-haul at 3, high-value and a newer assigned tractor at
4, an extra assigned-load decline at 5, a deeper dispatch board at 6, 10, and
12, load choice at 8, a long-haul sleeper at 9, specialty freight favored on
your board at 11, premium long-haul lanes at 12, a premium tractor at 13, the
owner-operator checklist from 14, the tank vehicle endorsement at 16 (liquid
in a tank surges, and the game says so), first pick of the yard at 17, and
business-path ranks through level 30. The full ladder is a months-long career:
early levels land within your first sessions, and the top rank is a long-haul
project measured in real months of driving.

## Pickup, loading, and route planning

After accepting a dispatch, you drive a local pickup leg from the terminal to
the shipper. At the pickup gate:

1. Stop the truck.
2. Open the pickup facility menu.
3. Check in at the shipping office.
4. Load cargo at the assigned dock.
5. Depart for the destination after the trailer is loaded and sealed.

Check-in takes 15 in-game minutes. A live load at the dock gives a short
spoken wait while the dock crew loads and seals the trailer, then advances
the clock by about 60 in-game minutes. Both count as on-duty time.

### Drop and hook, and the walk-around

Trailers have identifying numbers, and how you pick one up
depends on the shipper. High-volume freight -- cross-docks, parcel hubs,
distribution centers, ports and intermodal ramps -- often stages loaded
trailers in a yard. That is a drop and hook: back under a trailer that was
loaded hours ago, hook, and go in about 25 minutes instead of an hour backed
into a live dock. A farm elevator or a quarry loads you at the dock.

The catch is that nobody has been under a dropped trailer since it was
parked. Before you pull out, **Walk around the trailer** checks the lamps,
the brake adjustment, and the tires yourself. If something is wrong you hear
exactly what it is, and you can refuse the box: the yard takes about half an
hour to bring a sound one, and the defect stays their problem instead of
riding to the first scale house with you. Roll out without looking and it is
yours, including the write-up if an inspector finds it.

A shipper that holds you past two hours of free time owes detention: the
clock and the rate are in the job details, and it is money you earn for
sitting still. The delivery end mirrors the pickup -- a receiver with a drop
yard takes the whole trailer and hands you a clean empty in about 20 minutes
instead of 45 at a dock, which is also how you shed a defect you have been
dragging since the shipper. Owner-operators hauling their own trailer give up
the fast turn: your box comes back with you.

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
enabled, route planning uses live conditions at cities along the route when
available. Once you are driving, live weather follows your current route
position. Otherwise the game uses the simulated forecast.

## Driving controls

Driving controls are active while the road view is focused. The keys and
buttons below are the defaults. Every one of them can be moved to another key
or pad button under Settings, Gameplay, Controls, then Keyboard shortcuts or
Controller buttons. The F1 help, the How to play pages and the spoken prompts
follow the move. With a controller in use, How to play names the pad button
wherever the pad has one.

| Key | Action |
| --- | --- |
| Up arrow, hold | Throttle. |
| Down arrow, hold | Brake. To select reverse: stop fully, release the key, then press and hold it again for a moment. A quick tap, or a brake held through the stop, just brakes. The same press-and-hold on the Up arrow brings forward gear back. |
| Down arrow, tap then press and hold | Latch the brake so it stays applied hands-free. A click and a spoken confirmation mark the catch after about half a second of holding. Press Down arrow once to take it back; the accelerator releases it instantly. The throttle key never latches. Turn the gesture off under Settings, Driving assistance, Latching brake. |
| B, hold | Emergency brake. |
| E | Start the engine. Stop the engine only below 5 miles per hour. |
| P | Release or set the parking brake. Set it above a crawl and the spring brakes slam on: a screech, a hard stop, and permanent flat spots ground into the tires, worse the faster you were going. It is not a brake pedal. |
| K | Start or cancel automatic speed control. It uses adaptive cruise on open roads and speed keeper in low-speed zones. It pauses through the planned pickup and resumes once the loaded truck is rolling. Braking elsewhere also cancels it. Parked with the parking brake set, K latches a high idle instead. |
| Shift+K | Resume automatic speed control at the last speed you had set, after braking cancelled it. |
| Plus / Minus | Raise or lower the open-road cruise target while automatic speed control is active, snapping outward to the next multiple of 5 mph -- from 32 it lands on 35, then 40. The keypad Plus and Minus keys work too. |
| Ctrl+Plus / Ctrl+Minus | Raise or lower the open-road cruise target by exactly 1 mph, no snapping, for setting a precise number. |
| X | Signal for or cancel the next announced route exit. The truck takes the ramp when speed, lane setup, and route intent are valid. |
| T | While rolling, plan the next nearby sleep-capable stop and hear its distance, exit, and stopping-assistance state. T never signals or takes the exit; press X for that. When fully stopped at a supported route stop, T opens its menu; away from route points, it opens the emergency shoulder-sleep confirmation. |
| J | Toggle the engine brake. It engages at the stage you last selected, like a real dash switch. In an automatic, J arms the truck's own retarder management unless you have turned that off. |
| Alt+J | In an automatic, choose whether J arms the automatic retarder or leaves the stage entirely to you. |
| Alt+T | Switch between automatic and manual transmission on the road. This changes your whole control scheme, so it is worth knowing you pressed it. |
| 1 / 2 / 3 | Select the engine brake stage -- two, four, or six cylinders of retard -- while it is on. With the engine brake off these keys do nothing. |
| H | Hold to sound the horn; release to stop it. |
| Space | Report speed, gear, RPM, the active speed-control mode and open-road target when speed control is on, air pressure, and brake state. With the turn signal on for an exit, it ends with that exit and how far away it is. |
| S | Report the posted speed limit here, the zone if any, and how far over you are. In bend country it adds the bend's advisory speed -- the posted limit and the yellow diamond are different numbers on a real road. On a delivery ramp that ends at a traffic light, S answers with the light and the distance to the stop bar instead, since the light is the law there. |
| D | Report one safe-speed number for right now. Weather grip, an armed exit ramp, and the next bend are already baked into the number. |
| G | Report the grade under the wheels: the slope, how far it runs, and whether the truck is holding, pulling, or losing it -- including whether the engine brake has the descent or is about to lose it. G also names the next grade ahead worth planning for, how far off and how long it runs -- including one that steepens without flattening out first, and the gentler pull automatic speed control is building speed for when nothing steep is coming. |
| I | Turn the lane locator on or off: a soft tock, once a beat, panned to where the truck sits inside its lane. It keeps ticking until you turn it off. Needs lane keeping on partial or off. |
| Enter | Arrive: accept a facility arrival once you are fully stopped. |
| Tab | Open the driving status menu. |
| F | Report fuel level and estimated range. |
| C | Report clock, deadline, estimated arrival, and the one hours-of-service limit that comes first. For the first few presses it also names the three keys below, then stops. |
| Alt+A | Report time at the wheel so far this shift, and time on duty. |
| Alt+S | Report when your 30 minute break is due, or that a break will not help. |
| Alt+D | Report what ends this shift -- driving time left and duty window both -- and where you can legally stop before it. |
| R | Report trip progress (the same percent the online drivers list shows) and the distance left, then the road you are on with its direction, the state you are in, and the city you are heading toward. With a planned stop set, the distance counts down to that stop instead of the destination. On city streets -- pulling out of the origin gate, driving a pickup approach, or running the last streets to a facility gate -- it names the street under your wheels and counts down to the on-ramp or the gate instead. Distances close in quarter miles and then in feet, so the answer is never "0 miles" while the gate is still ahead. |
| Alt+1 | Report the state you are in, and nothing else. |
| Alt+2 | Report the road you are on, signed the way you would read it -- "I-90 East". On city streets it names the street instead. |
| Alt+3 | Report the town you are in. When you are not in one, it names the nearest town, how far off the road it sits, and whether it is ahead or behind. On an empty stretch it says there is no town near you rather than going quiet. |
| Alt+4 | Report the direction you are travelling, as the shields sign it -- "Eastbound". A city street has no signed direction and it says so. |
| V | Report weather and forecast. |
| L | Report which lane you are in, whether you are centered, drifting, or at an edge, and whether the lane beside you is open or blocked. |
| Left / Right arrow | With lane keeping on partial or off, steer; steer across the line to change lanes. With lane keeping on full, tap to change one lane in that direction -- the signal clicks and the change is announced. |
| A | Repeat the last route announcement -- the last thing with consequences -- even if other speech came after it. |
| Alt+C | Repeat the last CB chatter, with the distance as it is now. Once you have passed what the CB called, it says so instead. |
| U | Report the road ahead that no other key answers: the exit your signal is on for, first, then the ramp control coming up, the next imposed speed limit, the next stop, and the next bend that will demand slowing, with its advisory speed. Four short clauses at the most. It does not report police activity -- enforcement reaches you on the CB. |
| F1 | Show the driving control list and current objective. |
| Comma | Review earlier speech. The full review keys are listed under "Reviewing what the game said". |
| Period | Move toward newer speech. |
| Escape | Open the pause menu. |

Alt+1 through Alt+4 answer one part of R each, for when you want the single
fact and not the whole sentence. The keypad numbers do the same thing, so a
keyboard without a number row above the letters is not shut out.

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

## Truck behavior

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
- Damage in bands: reduced power, limp mode, and out of service.
- Wear meters for tires, brakes, and engine, driven by how you actually
  drive. Wear talks back: bald tires grip less, worn brakes fade sooner,
  and a tired engine loses power and drinks fuel.

Condition belongs to the truck, not to you. Each truck you own keeps its
own wear, damage, fuel, and traction equipment, so switching tractors
means switching into that truck's actual state.

Fuel adds to gross weight. Burning fuel makes the truck lighter; refueling
adds that weight back. Check the weight margin before accepting a load or
filling the tank. The fuel menu reports the projected weight after refueling.
This is a gross-weight check; the game does not simulate axle-weight limits.

A loaded tractor-trailer pulls away gradually. The automatic transmission holds
the first few gears long enough to feel the weight, then settles into normal
highway acceleration. It shifts like a real automated box: quick, light
shifts down low, deliberate ones up top, and it manages its own engine brake,
staging the retarder against a hill and releasing it when the grade is done.
Alt+J decides whether J hands it that job or leaves the stage to you. Load
changes when the truck shifts and how fast it dares -- an empty or bobtail
truck still pauses between shifts.

The engine brake is a three-stage jake with a cylinder selector: two,
four, or six cylinders, stepped with 1, 2, and 3. It retards through the
gears, so it pulls hardest in a low gear with the engine turning fast and does
very little in top gear. Set your gear and speed before the hill starts. The
full stage can break the drive tires loose on ice, exactly like the warning
stickers say.

Cold starts build air out loud: the compressor charges the tanks before the
brakes will release, and low air has its own buzzer. Parked with the brake
set you can rev freely, and K latches a high idle so you do not have to hold
the throttle.

Repeated hard braking can use air faster than normal driving. If low air is
reported, stop safely, set the parking brake, and let pressure build.

On an open road, automatic speed control requires the engine to be running and
the truck to be moving at least 20 miles per hour. Press K to start adaptive
cruise at your current speed. Plus and Minus raise and lower the open-road target,
snapping outward to the next multiple of 5 miles per hour the way a real cruise
stalk does -- from 32, plus gives 35, then 40. Hold Control with either key to
move the target by exactly 1 mile per hour instead, for setting a precise number.
The keypad Plus and Minus keys work too. Press Space to hear the active mode and
target along with speed, gear, RPM, and air-brake state. Whenever cruise is
holding the truck below that target -- for a ramp you have signalled for, a
bend, a lower posted number, a zone, the grade, the weather, or the vehicle
ahead -- Space and the status screen give the speed it is really holding and
why, with the target after it. The truck accelerates up
to a higher set speed on its own. Cruise looks ahead
for sharp posted-limit drops so it can begin slowing before the lower-limit
stretch. It will not hold more than 5 miles per hour over the posted limit, so
it keeps you legal even if you set it higher. Weather can increase the following
gap, and modeled traffic can make cruise reduce speed. Cruise does not steer,
change lanes, or replace your attention.

## Truck damage and being out of service

Brakes, tires, and the engine also have service limits. At 80 percent wear,
you hear a warning to arrange service. At 100 percent, the worn component
puts the truck out of service even if overall damage is low. These are
maintenance limits in the game. Check truck status to hear what needs repair.
The garage can replace the tires, reline the brakes, or overhaul the engine.
Roadside repair remains available if a component reaches its limit on a trip.

Damage changes how the truck drives at the following thresholds. Each new
band is announced, including when repairs move it back down. Wear can reduce
performance or require service at any damage level.

| Damage | What the truck does |
| --- | --- |
| Under 50 percent | No damage-related power reduction. |
| Past 50 percent | **Reduced power.** The engine holds back and burns more fuel for the same work. |
| Past 75 percent | **Limp mode.** Reduced power, plus a road-speed cap of 45 miles per hour you cannot drive out of. The cap eases in over a few seconds rather than snapping on. |
| Past 85 percent | A spoken last call that names the number ahead, so the wall is never a surprise. |
| Past 90 percent | **Out of service.** The truck may not be driven. It can still crawl clear of a live lane, because leaving a stricken truck stopped in traffic is worse, but the run does not continue under its own power. |

Any readout that gives you a damage figure gives you its band with it, so you
never hear "78 percent" without hearing "limp mode" beside it. The delivery
summary tells you what the run added and what band it left the truck in.

Out of service is not a dead end, and how it resolves depends on who owns the
truck. An owner-operator's tractor is their property: a roadside repair gets
it moving again for real money and several hours, the bill lands whether the
cash is there or not, and the truck is still in reduced power afterwards --
repair it properly at the next stop. A company driver's tractor is not theirs
to gamble with: the carrier takes it out of service, covers the repair, and
sends out a yard spare. What that driver spends is the hours, some dispatch
trust, and a preventable-equipment entry on the record.

A run the carrier rules preventable also costs a deductible and voids the
safety bonus, scaled to the deepest band the run reached rather than the
number at the gate -- so patching the truck on the shoulder does not launder
the trip. Damage taken by reacting correctly to a hazard is not counted
against you.

Driving visibly wrecked equipment past active enforcement is its own problem:
a scale officer can pull you in for a safety stop, and an unsafe-equipment
citation is one of the most expensive in the game.

## Mountain driving

Grades are real: the game samples actual elevation along every route, so
the long climbs and descents you hear are the ones a real driver runs.
Press G at any time for the grade under your wheels and a plain verdict
on whether the truck is holding it, pulling it, or losing it.

The road warns you about the hills that matter. Any climb or descent of three
percent or more that runs at least three quarters of a mile is called out
before it starts, with the steepness, the length, and -- going down -- what to
do about it before it begins. Short dips stay quiet so the real hills stand
out. Quiet and Urgent only skip these; G answers on demand either way, and G
also names the next grade ahead.

Cruise reads the same road when predictive cruise is on. It banks a little
speed before a climb so the truck carries it up the hill, gives up the last
few miles per hour at a crest instead of fighting for them, and stops adding
speed it would only have to brake away before a descent. It says what it is
doing the first time on each hill -- and when it cannot maintain speed on a climb,
it says that too.

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
that already accounts for the conditions; on a steep downgrade that is
the speed your truck can hold the hill at with its current load, and D
says "for the grade". Descent speed control, in the driving assistance
settings, drives a descent the same way for you with adaptive cruise on:
it slows to that speed before the steep part, sets the engine brake,
holds the gear, and snubs the service brakes. When the hill needs a
slower speed than cruise is already holding, descent control says that
speed once, and again only when the hill changes it.

## Taking curves

The engine is your steering guide, and the whole approach comes down to five
habits.

### Carry your speed to the bend

The curve callout is braking distance, not
an order to stop. When you hear "Sharp right, half a mile. Advise 30," you
have real seconds: brake firmly down toward the advisory and arrive within a
few miles per hour of it. Slam to a crawl at the callout and the bend becomes
nothing -- no push, no steering, and time lost.

### Know the vocabulary

Hard double-thuds under the whole truck are
the warning bars real road agencies only cut ahead of a curve that has killed
people: a hairpin is a quarter mile out, so brake hard now, because 25 means
25 with fifteen tons pushing you. A thump-roll from one side is your tires
crossing a lane line's markers.

### Steer toward the lean

The engine leans toward the way to
steer: into a bend as it arrives and through it, and into a street corner as
you reach it. Hold the arrow that way and the engine comes back to the middle
as the truck comes round. This is the one cue you follow rather than avoid --
every other panned cue comes from the side you are drifting toward and you
steer away from it. Small, held corrections. Sawing at the wheel bounces you
across the lane line, and you will hear the marker thump each time; that
rhythm is the sound of overcorrecting.

With lane keeping on partial or off and lane-departure warning on, the engine
also leans back toward lane center when you drift, so the same habit covers
the straight road between the bends.

The road noise underneath answers a different question: it sits where you sit
in your lane. A road bed off to the right means the truck is riding right of
center, not that you should steer right.

Two settings change this. Steering guide flips which way to steer when the
engine leans, for drivers who learned the other habit elsewhere. Lane guide
sound moves the lean off the engine onto a quiet note of its own, and the
engine stays centered.

### Listen to the edge

Drift wide and the boundary answers with real
textures from the side it happens on, in order of how much trouble you are
in: a ragged stutter as your tires clip the rumble strip, a steady buzz fully
on it, and loose gravel once you are off the pavement. Ease back on -- do not
yank the wheel, and do not brake hard while a trailer wheel is still in the
dirt. On an undivided road the left line is different: past the centerline
there is no gravel, only the oncoming lane, and the warning says exactly
that.

### Use the co-driver

U says what bends are coming and exactly how far. D
says the safe speed for the road you are on right now. G reads the grade. I
turns on the lane locator, a soft tock from wherever you sit in the lane,
when you want continuous position. Shift+K resumes cruise on the way out.

Each bend ends with a verdict. "Held your line" means you did it right. "You
caught the edge" means your tires reached the rumble strip. "Through the bend, hot"
means you took the bend too fast.

## Winter driving

Cold seasons bring snow, ice, and the one weather worth parking for:
freezing rain. Ice cuts grip to a small fraction
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
requirement risks a citation of 580 dollars, more if you already have
citations on your record or the checkpoint sits inside a construction zone.
The signs,
the warnings, and the checkpoints all ride real mountain grades from
the map data.

## Road events, weather, and rest stops

The road can report traffic, construction, state lines, city pass-throughs,
checkpoints, toll points, route stops, and weather changes. Morning and
afternoon rush hours can make metro corridors busier and slower. Dense
metro/checkpoint corridors can also produce random road hazards a little more
often than open-country stretches.

Hazards can happen while moving. When a "Brake now" warning appears, slow below
25 miles per hour quickly to avoid a collision. Some hazards are called out as
"Change lanes or brake" -- those are fixed objects in your lane, like road
debris or a stopped vehicle, or a slow vehicle in your lane. The call ends by
naming the lane that is open: "Change lanes or brake! Slow car right ahead.
Left lane open." means one tap of Left (with lane keeping on full) is the
whole move; "Right lane open" means tap Right; "Either lane open" means both
are clear. The lane it names is one the truck has checked -- it exists, it is
not coned off, and nothing is riding alongside in it -- so you never have to
guess. Where there is nowhere to go, on a one-lane road or with traffic
holding both lanes beside you, the call is "Brake!" and ends "No lane open":
brake, and do not reach for a lane change. A lane change dodges the hazard at
full speed, and adaptive cruise stays on through it; braking works too, but
you cannot roll over a ladder at 25 -- an object in the lane takes braking
nearly to a stop, and then you ease around it. Press L any time for which
lane you are in and whether the lanes beside you are open. With automatic
emergency braking on, the truck brakes for you at the last moment -- down to
a crawl for an object in the lane. Fatigue shortens the reaction window.

The road tells you how many lanes you have. Road status names the lanes on
your side -- "divided, three lanes your side" -- and as the road widens or
narrows mid-leg you hear it happen. Where the map has no lane data the game
stays quiet rather than guess. Press L any time for which lane you are in,
and whether the lane beside you is open, blocked, or coned off.

Passing has a second half, and the truck speaks it. When you move over to get
around slower traffic, you hear when the lane you came out of is open again:
"Clear of the box truck. Right lane open." It is said once for each vehicle
you get past, only while it is still true, and never about a lane roadwork has
closed. If you missed it, or want to know before you commit, press L.

Construction and traffic zones lower the speed limit. A construction zone
begins with a mile of reduced speed before the lower limit inside it, the way
a real work zone steps its limit down. The merge or the flagger sits at the
end of that mile. A zone may cone off a lane -- but only where you have
another lane on your side for the whole signed stretch, approach included. On
a road that runs one lane your way,
the work still happens with every lane open. You will never be ordered out of
a lane you cannot leave.

Where a lane is closed, move over when you are told. Ride the coned lane past
one urgent warning and you plow through the barrels: a collision, real truck
damage, a citation of 1,000 dollars, and a serious mark on your safety
record. That citation is charged once per zone however many times the barrels
catch you, and it is deliberately not doubled for being in a construction
zone, because it is already a construction-zone offense. You are never
charged for it when the road left you nowhere to go.

Every callout names the closure by its side of the road, and that side is the
side that is shut, whether the road runs two lanes your way or four. If the
road drops a lane under you and the lane you are moved into is the closed one,
the truck is put back in an open lane and told so -- that one is the road's
doing, not yours, so it costs you nothing.

Speed-limit changes name the town that causes them, and the limits on streets
approaching a facility are the real posted ones, not a blanket guess -- a long
industrial approach might be 45, stepping down as you close on the
gate.

Traffic can also build around exit lanes, highway merges, construction tapers,
and slow lead packs. You may also hear nearby vehicles called out, such as a
merging vehicle, brake lights, or a slow car ahead. Treat those cues like a
heads-up to signal early, leave space, and avoid forcing the merge.

Posted speed limits come from real map data and change along a corridor; a
change is announced as reduced or raised, and named near a city. State troopers
patrol some stretches, hotter on busy interstates, in construction, and at
night. CB chatter may mention a bear ahead or drivers talking about enforcement
near a construction zone. U reports the road ahead, not enforcement chatter. Speed
badly inside a patrol and a trooper may pull you over: signal with X (the same
key as an exit), brake to a stop on the shoulder, and sit through a license and
logbook check that reads your recent duty entries before ending in an
on-the-spot ticket or a warning.
Ignoring the lights starts as a failure-to-stop warning, then a final warning
that says what running costs you. Slow down, brake, or roll on under thirty
and troopers box the truck in and stop it: a failure-to-stop citation and a
serious violation on your record, but not a felony. Hold highway speed or
accelerate for another twelve seconds after that final warning, with no brake,
and you are running from the police. Nobody gets there by accident: a touch of
the brake starts the count over. A pursuit ends in a felony stop that adds
truck damage, a major fine, a reputation hit, several hours of processing
time, and cancels the active loaded run. You are released back to the terminal
so you can repair, rest, and choose what to do next. Speeding is charged only
when a trooper catches it.
What each of those costs, and what it puts on your record, is under
Enforcement, Your Record, And Your CDL.
Open weigh stations also matter: the game warns you before the scale, and if
you blow past at highway speed instead of slowing into the inspection lane, a
scale officer can light you up for a roadside enforcement stop. Slowing into
the lane is enough; the scale's own exit ramp is the sanctioned way in. A
visibly
unsafe truck can also draw a safety stop when you pass active enforcement, so
repair severe damage before pushing through patrol corridors.

Inspections are real. A clean record is waved through an open scale nearly
every time; a record carrying citations or out-of-service orders from the
last game year is pulled into the lane, and older ones no longer count
against you there. The lane is a Level 1 inspection: driver,
paperwork, a walk-around and a look under the truck, about 45 minutes on
duty. Worn tires, brakes near their limit, body damage and whatever the
last driver left on a hooked trailer get written up, with a fine and a
citation on your record. A critical item, a bald tire, brakes out of
adjustment, damage past the safe limit, parks the truck until a roadside
mechanic fixes it. A clean Level 1 earns an inspection decal that gets you
waved past open scales for three months unless your record is targeted.
A trooper can also pull a legal driver in for a routine Level 3, licence
and paperwork only, about 15 minutes; a clean one costs nothing else. The
odds ride your record, and triple during Roadcheck week in May, which the
CB announces. Walk around the truck first: at the terminal and at any
stop, the Walk around the truck row spends 15 minutes on duty and reads
out exactly what an inspector would find, so nothing on the report is a
surprise.
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
calendar. Turn **Live weather controls calendar** off to keep live weather
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

### Time zones

In the accelerated driving modes, the clock you hear is local time where the
truck is, and it carries its zone name with it -- press C for "4 PM Central
Time" rather than a bare number. Real time is the explicit exception: it
starts from your computer's wall clock and calls that value "local game time"
instead of attaching a geographic zone name that may not match your computer.
Cross a zone boundary and the game says so and gives you the new time:
"Crossing into Mountain Time. It is now 3 PM." Your clock going backward an
hour mid-drive is the road, not a fault.

Delivery appointments read in the receiver's local time, with a day
qualifier, the way a driver parked at that dock would say it: "6 PM Eastern
Time tomorrow." That is why a deadline can look out of step with the clock
you just heard from a different zone.

Nothing that measures a duration ever shifts, including when Real time aligns
the displayed calendar and clock. Your hours of service, the
deadline itself, the seasons, and the market all run on one continuous
timeline; only the spoken wall clock changes. Daylight saving is deliberately
not modeled, so a zone's offset never moves under you.

The overspeed warning is your dash, not the police. More than 7 miles per
hour over the limit chimes softly and says the limit; the chime repeats,
faster the further over you go. It quiets while you are braking down and
resets once you settle under. It is a courtesy and it costs nothing: speeding
is charged by the trooper who saw it, on the shoulder, or it is not charged
at all. There is no setting for it: 7 over is past anything adaptive cruise
will do on its own, so it never chimes at a speed the truck chose, and it is
short of the point where a trooper can act on your speed, so it always warns
you while slowing down is still free.

Ramp ends are real intersections. Most ramps end at a traffic light or a stop
sign, called out on the way down. Lights cycle green, yellow, red, and speak
every change. Each light keeps a stable, slower cycle instead of changing its
timing while you wait, and cross traffic clears before green. Enter on green
or yellow; red means brake to a full stop at the bar and hold the brakes until
it says green. Rolling a red draws horns;
blowing one at speed means cross traffic finds your trailer. The stop bar has
a parking-sensor tick that speeds up as you close on it, so you stop at the
bar instead of a quarter mile short and creeping blind.

Once the stop is honored and the way is clear, who pulls ahead depends on
Facility stopping assistance. With it off, the cab says "Clear; pull ahead to
the entrance" (or "Green light. Pull ahead to the entrance") and the last
stretch is yours; where city streets follow the ramp, it says "onto the
streets" instead. With it on, the cab says "Facility stopping assistance is
taking you to the entrance", or "onto the streets", and the truck moves off
on its own: where the ramp
ends at the gate, the assist drives it there and stops; where the facility sits
at the end of city streets, the assist rolls the truck to the streets and the
speed keeper takes them, holding the posted number and easing for each corner,
until the assist takes the pedals again at the gate and holds there, waiting for
Enter. Your own brake, Down or B, cancels it -- "Facility stopping assistance
released; pull ahead to the entrance" -- and the truck is yours again from the
bar, the same rule as every other assist. If the speed keeper is off, a
facility with city streets keeps the manual release, because nothing could
drive the streets for you.

City streets start where your ramp ends: the first street named off the ramp
is the one the ramp meets. Each street keeps its own speed limit, taken from
the map where the map has one and from the state's default for city streets
where it does not. When the street changes, the cab says the new number, "Speed
limit raised to 40". A drop of 10 or more is called ahead of the sign. In
this version the streets themselves have no traffic lights or stop signs;
the ramp's end keeps its own.

The facility's driveway is a turn like any other, called with its advise
speed. Past it you are in the yard, "Into the yard. Yard limit 15", and the
gate where you stop to check in is at the end of the yard. Facilities post
their own yard limits; 15 is the game's number for all of them. Where the map
shows no driveway, the gate stands on the street itself, and the street keeps
its limit right up to it.

A truck stop, travel center or fuel station has its entrance at the end of
its ramp: stop there and the stop's menu opens.

Stops are reported as you approach them. An armed exit counts itself down --
two miles, one mile, half a mile -- so the exit stays anchored while you set
up for it. As an announced exit approaches, use X to signal or cancel your intent.
X commits you to the exit wherever you press it, and the game says "Signal
set"; the blinker itself starts clicking half a mile out, the way a driver
flicks it on near the exit.
Unless lane keeping is on full, move to the right lane and stay centered there;
the game asks for that move only while you are out of the right lane. Just
before the gore the exit lane opens beside the right lane, and the game says
"Exit lane opening. Steer right into it." Steer right across the line and you
are in the exit lane, the start of the ramp. On full, lane keeping takes it for
you. Keep road speed until then: the gore accepts anything up to the speed the
posted limit allows. The exit lane, which road engineers call the deceleration
lane, is where you slow down, and the game says the exit speed as you enter it.
Brake to it before the ramp curve at the end of that lane; a loaded truck
taking that curve too fast shifts its load and can run wide. The signal-on announcement also names how the ramp ends -- a traffic
light or a stop sign -- so the braking plan can start on the mainline, and the
U upcoming readout carries the same warning. Once you are on a ramp that ends
in a light or a sign, the game clock runs in real time until you are through
the intersection, so the warning buys real reaction seconds instead of
compressed ones. If you reach the gore too fast or without signaling, or the
gore goes by without you steering into the exit lane, you stay on the
highway and the game tells you what went wrong. The timing is generous so the
sequence is about preparation, not twitch input. The game can also tell you when
traffic boxes you out of the lane, so you know to recover at the next safe exit
instead of fighting the maneuver. The
game gives a short pull-in moment before the stop menu opens, so holding Down
Arrow to brake does not skip the first menu option.

Destination exits work the same way. When your delivery exit is ahead, the game
announces the signed exit and toward cities, marks it as the destination exit,
and tells you to set up for it. With lane keeping on partial
or off, use X to signal, keep to the right lane, and steer into the exit lane
where it opens. On full, lane keeping
takes the destination exit for you, and the first call of each approach says so. If automatic speed control is
active, it holds road speed and eases at most 10 miles per hour below it just
before the gore. Press X to take the exit; automatic speed control pauses as
you enter the exit lane, then you brake to the exit speed for the ramp
curve and on to the stop. If you miss the destination
exit, continue to the next safe turnaround. Dispatch loops you back onto the
approach so you can hear the exit call again and press X to take it. On full,
the turnaround and the fresh exit call both say lane keeping is taking it, so
you are never told to signal for an exit the truck takes itself.

Ordinary highway exits that do not lead to a current action are not announced
during the drive. The status screen lists the next exit for route
context.

Stop actions depend on that stop's data. A stop may offer:

- Fuel.
- A CAT Scale weigh.
- Meals, drinks, and showers.
- A 30-minute break.
- 10-hour sleep or sleeper-berth splits.
- Repairs and rig care.
- Roadside assistance or towing.
- Inspection check-in.
- Walk around the truck.
- Save point.

Meals, drinks, and showers are purchases with spoken effects and clocks
on them: a hot meal or a coffee helps fatigue for a while and says so
when it wears off, and a sit-down meal's half hour also satisfies the
30-minute break rule. Showers are commonly free with a fuel purchase at
the same visit. Rig care such as lube work and tire checks is truck
work, so the carrier covers it for company drivers; food and showers
are always your own money. Different stop brands are good at what they
are really known for.

A truck stop with a CAT Scale lists it among its services, and its menu
has a Weigh on the CAT Scale row. The weigh takes ten minutes on duty and
reads the ticket: steer axle, drive axles, trailer axles and gross, in
pounds, then either that you are legal on every axle or which ones are over
and by how much. The federal limit is 34,000 pounds on each tandem and
80,000 gross. A weigh costs what CAT Scale charges, 15 dollars and 25
cents, and a reweigh at the same scale within 24 hours costs 5 dollars and
25 cents. Company drivers bill the carrier.

Not every stop offers every action. A public rest area usually does not offer
fuel or repair. A weigh station is for inspection, not food or sleep: slow
below fifteen, signal for the scale exit with X, stop at the scale, then
press T for inspection check-in. T at highway speed plans sleep stops, so
near an open scale it reminds you the scale comes first instead.
Parking labels describe confidence, not a live guarantee that a space is open
right now. Late at night, a sleep-capable stop may be full. A full lot still
sells diesel: the fuel island is open whatever the parking is doing, so a
full stop is never a reason to pass it with the tank low.

When a sleep-capable stop is close enough ahead, press T to plan that exact
stop. The game names it, its exit, and the next action. Press X separately to
signal for the exit; T never chooses to leave the highway by itself. The
default-off Planned rest-stop stopping assistance setting can then brake to a
complete stop at the entrance after you have taken the exit lane and cleared any
ramp light or stop sign. It never selects, signals, takes, or cancels an exit.

## Enforcement, your record, and your CDL

A traffic stop costs money, and it also writes something down. The money is
the smaller half.

### What a citation costs

Every fine in the game is priced from one schedule:

| Citation | Base fine |
| --- | --- |
| Unsafe equipment | 2,300 dollars |
| Running an open scale | 1,800 dollars |
| Failing to pull over promptly | 1,500 dollars |
| Driving through the barrels | 1,000 dollars |
| Following too closely | 600 dollars |
| Chain law | 580 dollars |
| Improper lane use | 500 dollars |
| Running dark after sunset | 350 dollars |

Speeding is charged by how far over you were: 250 dollars up to 10 over, 400
from 10, 1,000 from 15, 1,600 from 20, and 2,500 from 30. Fleeing a stop
altogether is 5,000 dollars.

Two things make a fine bigger, and they multiply rather than add:

- **A construction zone doubles it.** That is the real rule -- several states
  double the penalty for any violation committed inside marked roadwork -- and
  when it happens the game says so out loud, so a doubled number is never a
  mystery. The barrel citation is the one exception: it only exists inside
  roadwork, so it is never doubled again.
- **Every citation already on your record makes the next one dearer**, by half
  the base each time, up to twice the base. The money therefore stops climbing
  after the third citation: a scale bypass runs 1,800, then 2,700, then 3,600,
  and no higher. Past that the deterrent is your record rather than your
  wallet.

The worst single citation the two multipliers can produce is 10,000 dollars,
for 30 or more over the limit in a construction zone as a repeat offender.

### Serious violations and losing the licence

Some violations are categorically different from an expensive ticket.
Speeding 15 miles per hour or more over the limit, reckless driving, improper
lane changes, and following too closely are **serious violations**. This is
why 15 over is not simply a dearer version of 10 over.

- Two serious violations inside three years suspend your CDL for 60 days.
- Three or more suspend it for 120 days.
- Suspensions run consecutively: a new one starts where the last one ends.

Fleeing and eluding is a **major offense**: a full year the first time, and a
lifetime disqualification the second. Running off the road asleep costs
reputation as a preventable safety incident the first time; every time after
that it is a fatigued-driving violation and joins the serious ladder.

While your CDL is suspended, driving work comes off the dispatch board. The
board opens by telling you so and naming the date the work returns, and any
job you try to take says the same. A roadside stop that pulls your licence
ends the run there and releases you to the terminal. Nothing else about your
career is touched: your level, experience, endorsements, and equipment are
all still yours when it clears.

Ask for your record from **Career stats** at the terminal or **Driver** in the
Tab status menu. A clean record says so in one word. Otherwise it counts what
you have, and tells you what one more would cost.

## When you owe money

A fine you cannot pay does not empty your pocket and it does not end your
career. It becomes a **balance owed**: a figure carried forward and collected
out of later settlements.

### What a settlement takes, and what always reaches you

While you owe a balance, one quarter of each settlement goes to paying it
down. Three quarters always reaches you. This leaves money for the next run.

The same quarter also covers any pay advance you are repaying, so the two
together can never push you below your take-home. While a balance is being
collected, dispatch stops fronting new advances and says why.

Your debt is the two things a player feels as one: cash run past zero, and
charges a settlement could not cover. Ask for it from **Career stats** or from
**Driver** in the Tab status menu, and it reads back as what you owe, the
ceiling on it, and what happens at that ceiling.

### The ceiling, and the three warnings before it

Your balance cannot climb forever. There is a ceiling on it, and you get
three spoken warnings on the way there: one when a balance first exists, one
past halfway, and a last one with enough room left for a couple more
settlements at what your runs actually pay. Every warning names the number
you owe, the ceiling, and the consequence. Nothing about this arrives without
notice.

Where the ceiling sits depends on what kind of driver you are:

- **A company driver** is carried up to eight of their own average settlements,
  or 6,000 dollars, whichever is larger -- so a senior driver on long freight
  is not terminated by one bad week, and a new hire has a real floor under
  them.
- **An owner-operator** is carried up to 60 percent of what their tractor
  would bring at sale, or 12,000 dollars, whichever is larger. That is the
  point where the loan stops being covered by the truck behind it.

A company driver who is already at the fleet of last resort has nowhere
further to fall, so the rule changes for them: the balance simply stops at
the ceiling and anything past it is written off. It cannot grow, and a
quarter of every settlement still brings it down.

### What happens at the ceiling

**A company driver's employment ends.** You owed more than the carrier
carries on a driver. That balance is closed -- you do not owe it to anyone
any more, and your cash goes back to zero. Your assigned tractor goes back to
the yard and you go on the payroll at Great Lakes Training Transport: shorter
freight, lower pay, and equipment to match, until you build back up with
them.

**An owner-operator's lender takes the tractor back.** You owed more than the
truck would bring at auction. The sale closes the loan, what you owed is
settled, and your cash goes back to zero. Every truck you own goes, and you
are a company driver again in carrier equipment. The owner-operator path is still
open, and the buy-in gates are the same ones you cleared to get there.

In both cases you keep your career level, your experience, your endorsements,
your driving record, and everything else you own. Nothing is reset and no
save is lost. Both land as a screen you can read at your own pace and read
again later.

## Hours of service and fatigue

Freight Fate tracks an ELD-style hours clock. Realistic and relaxed modes use the same limits:

- You can drive 11 hours after a 10-hour reset.
- The duty window is 14 hours after coming on duty.
- You need a 30-minute break after 8 cumulative hours of driving.
- Sleeping 10 hours resets the shift clock.

Driving to another city to find work counts as commercial repositioning,
even when you are bobtail and chose the trip yourself. It uses driving time
while moving and on-duty time while stopped. Running without a trailer
does not make the trip personal conveyance.

At sleep-capable truck parking, the sleeper berth means the bunk in your cab.
You can choose 2, 3, 7, or 8 hours in the sleeper berth to plan an 8+2 or 7+3
split. Sleep 10 hours remains the simplest full reset. Shoulder sleep and
sleeping 10 hours in the lot are fallback rests, not clean split-rest planning
tools.

A nap in the sleeper berth that does not reset your 14-hour window says so
when you wake, and names the time the window still closes, so a short rest
never reads as a fresh day. The long half of a split, 7 or 8 hours in the
berth, stops the duty window while you sleep, so you wake with the hours you
went to bed with. The short half, 2 or 3 hours, keeps counting until the
pair is complete, and then only the duty between the two rests remains.

The game gives warnings at 2 hours, 1 hour, and 30 minutes before a limit.
Driving past a limit risks inspections, fines, reputation loss, and
out-of-service orders. A log check that finds you over your hours is not a
silent time jump: the officer orders you off the road, the stop names exactly
which clock you broke and by how much, and the ten-hour hold plays out with
the new shift time and what it means for your deadline spoken plainly.

Three keys ask the clock one question each while you drive, so you do not have
to sit through a whole report to hear the number you want. They read left to
right in the shape of a shift:

- **Alt+A** -- at the wheel so far: driving time this shift, and time on duty.
- **Alt+S** -- the break: when your 30 minute break comes due.
- **Alt+D** -- what ends this shift: driving time left and the duty window, the
  one that runs out first named first, plus where you can legally stop before
  it.

Each answer starts with its own words, so a mis-key is obvious before the
number arrives. With hours of service enforcement off, each key says so rather
than going quiet. **C** still gives the clock, the deadline, and whichever
limit comes first, and the **Tab** status menu keeps the full report.

Rest advice estimates which suitable stop you can reach before your next
hours limit, including time to enter the stop. A break-only stop cannot
replace somewhere to sleep when your shift is ending. When rest is needed
before your destination, the game names the last reachable stop and warns
before you pass it. If none is reachable,
the readout says so. Traffic and weather can change the estimate; check
again as your hours run down.

The Logbook is the spoken Record of Duty Status behind that clock. It records a
rolling timeline of driving, on-duty work, off-duty breaks, and sleeper-berth
rest, with the time, location, and a short note such as fuel stop, loading, or
out-of-service order. Open **Logbook** from the terminal, or open **Tab** while
driving and choose **Logbook**. The first line is what you are doing now and
since when. Then come your limits, one per line: driving left, when the break
is due, and when the duty window closes. Today's totals follow on one line,
and after them the recent entries, newest first, each led by what you were
doing.

Fatigue rises while driving, faster at night. Drowsiness adds yawn and rumble
strip cues and makes hazards harder to react to. Once fatigue is severe you
start to nod off: a rumble-strip jolt and a warning give you a brief window to
steer or brake and stay awake. Catch it and you carry on; miss it and you drift
onto the shoulder, taking damage and losing speed, and a third miss in a row
forces you off the road. Running off the road asleep is a preventable safety
incident and costs reputation; do it a second time in a career and it goes on
your record as a fatigued-driving violation, on the same ladder as any other
serious violation. Food and coffee help you stay alert a little longer,
but do not satisfy the 30-minute break rule. A 30-minute break reduces fatigue
more; a proper 10-hour sleep clears it. Plan your rest before you get there.

Emergency shoulder sleep is a fallback, not normal rest. It can appear in the
pause menu when you are stopped away from a route point of interest. The game
also opens the same confirmation when you press T while fully stopped away
from a route point. Pressing T while the truck is still moving tells you to
finish stopping first. The truck is secured before either sleep menu opens.
The game
uses stronger warnings when hours are tight or fatigue is severe. The
confirmation explains that 10 hours pass, the hours clock resets, fatigue only
improves to a poor-rest floor, a parking ticket is possible, minor truck damage
is possible, and the delivery deadline keeps running.

## Status screens

Use these keys when you need status without leaving the road:

| Key | Information |
| --- | --- |
| Space | Speed, gear, RPM, air pressure, and brake state, and with the signal on, how far to the exit. |
| F | Fuel level and estimated range. |
| C | Clock, deadline, estimated arrival, and the nearest hours-of-service limit. |
| Alt+A | Time at the wheel so far this shift, and time on duty. |
| Alt+S | When your 30 minute break is due. |
| Alt+D | What ends this shift, both clocks, plus the next legal stop. |
| R | Route progress and GPS context. |
| V | Weather and forecast. |
| Alt+C | The last CB chatter again, with the distance as it is now. |
| M | Toggle the in-cab radio. |
| Page Down / Page Up | Tune the radio to the next or previous station. |
| ; / ' | The same, on keyboards where the Page keys are awkward: semicolon tunes to the previous station and apostrophe to the next. |
| Ctrl with any tune key | Jump to the previous or next dial category: route playlist, Freight Fate stations, your playlists, favorites, terrestrial, AFN, satellite, international, fallback, web radio, and other stations. |
| Shift with any tune key | Change the in-cab radio volume in 10 percent steps: up on Page Up or Shift+semicolon, down on Page Down or Shift+apostrophe. Works whether the radio is on or off, and speaks the new level. |
| O | Save or unsave the current station as a favorite. Favorites become their own early dial category. |
| Y | Speak radio station, source, signal or fallback state, volume, and streamer-safe status. |
| Shift+Y | Speak what the radio is playing right now. |
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

## Pause, save, and resume

Escape opens the pause menu during a drive. Public pause choices include:

| Choice | What It Does |
| --- | --- |
| Resume driving | Return to the active drive. |
| Trip status | A screen of lines: the load, where it is going, how far along you are, the hours used, and the air. |
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
or loaded delivery.

The main menu can continue the latest career, choose another career, reset a
career, or delete a career. If a saved career fails its integrity check, the
game moves it aside and warns you at startup.

To move a Windows or Linux archive installation to another folder or drive, copy the
whole `FreightFate` folder, including `saves`. On macOS the saves stay in
`~/Library/Application Support/FreightFate` and follow your user account, so
moving the app does not move them. The Linux AppImage also keeps saves separately,
in `~/.local/share/FreightFate` (or under `XDG_DATA_HOME` if set); moving the
AppImage does not move those saves.

## Destination and settlement

At the destination, slow down for the facility gate, stop, and choose **Dock
and deliver**. On highway deliveries, take the announced destination exit
first; in cities with street data, the arrival flows off the ramp onto the
destination's real local streets with spoken turn-by-turn cues, their own
speed limits, and the yard behind the facility's driveway (see the ramp section above), and loaded
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
Late delivery reduces pay.

How the freight rode matters as much as when it arrived. The load's condition
is reported while you drive and judged at the dock: freight in the state it
was tendered is signed for clean and nobody says anything, a load knocked
about gets an exception noted on the bill of lading and a small deduction, a
badly handled one becomes a real freight claim against its value, and a
ruined one is refused outright with no delivery pay at all. Fragile freight
-- electronics, glass, high-value, fresh food, livestock -- reaches those
rungs on far less abuse than lumber or bulk. Hard braking, taking a bend
faster than it is signed for, and hitting things are what move the meter.

If a charge is larger than the settlement can cover, the remainder becomes
a balance you owe and
is collected a quarter at a time out of later settlements, with three
quarters always reaching you. See When You Owe Money.

## Settings

### Driving assistance and speed keeper

Three driving assistance presets are available: Realistic, Balanced, and All assists. Changing an individual assist is shown as Custom. Adaptive cruise always follows traffic, anticipates large posted-limit drops, and increases its following gap in poor weather. Realistic adds modern safety support: automatic emergency braking, lane-departure warning, supported stop-and-go behavior, and realistic descent control. Balanced adds partial lane keeping, lets braking capture a lower descent target, and stops for you at your destination. All assists adds a 55 mile per hour ceiling on every descent and stronger intervention. These presets do not change trip pacing, hours rules, transmission, weather, or hazard frequency.

#### Individual assists

The individual controls are Automatic emergency braking, Lane-departure warning,
Stop-and-go assistance, Descent speed control, Exit speed assistance, Destination
approach assistance, Planned rest-stop stopping assistance, Curve speed
assistance, and Route-transition assistance.

Descent speed control has four levels: Off, Realistic, Balanced, and Interactive.
Interactive is a descent-control level, not a preset. At every level but Off,
adaptive cruise holds a steep downgrade at the speed your truck can take it at
with its load, never faster than your set speed or the posted limit allows.

#### Exit and stopping assistance

Exit speed assistance brakes in the exit lane of an already-selected
exit, so the truck reaches the exit speed by the ramp curve. On the highway it
only slows a truck the gore would refuse. Route-transition, curve, or
facility stopping assistance does the same braking when exit speed assistance
is off. Facility stopping
assistance (the destination approach assistance row) slows and stops at the
selected facility arrival point. About a block out, it says "Facility stopping assistance taking the pedals" and controls the pedals until the gate. From a
cleared stop or green light at the end of the destination ramp, it also pulls
ahead for you and hands city streets to the speed keeper. Realistic leaves it
off; Balanced and All assists turn it on, and changing it by hand reads as
Custom like any other preset row.

The separate default-off planned-stop control stops at a sleep stop only after
T plans it and X signals for it.

#### Curve assistance

Curve assistance slows the truck for mapped curves before you reach them, whatever is holding the speed: adaptive cruise, the speed keeper, or your own pedals. It starts at the curve call. If you are over the bend's advisory when the call comes, the assist takes the service brakes on the approach so the truck is at the advisory by the start of the bend, holds it through the bend (the tightest number when the call names two bends together), and lets go on the far side.

With curve callouts on it says so in the same breath as the call: "Sharp left, half a mile. Advise 35 miles per hour. Curve assistance slowing." Under adaptive cruise the call names cruise instead ("Adaptive cruise easing to 35 miles per hour for the bend"), and a bend too tight for cruise to hold pauses cruise while the assist slows the truck; cruise resumes once you are through and back up to speed.

Your own brake cancels it for that bend, and it says "Curve assistance released." With curve callouts off nothing is said and the slowing is what you hear.

Inside a bend you entered too fast, it brakes and it reaches for the engine brake only when the corner needs about 10 miles per hour or more taken off, or the road under you is a real downgrade. This limits engine braking to bends and descents that need it.

It aims at the advisory itself: a load starts shifting a little over fifteen percent above a bend's posted advisory.

#### Route transitions

Route-transition assistance helps manage speed and lane workload at confirmed route transitions. Lane keeping is the row that decides how much of the lane work is yours; there is no separate lane-centering assist.

Assists never silently choose a route or optional exit, enter a yard, dock, or complete a delivery: you still steer, confirm route choices and exits, initiate lane changes, leave long stops, and handle every precision task.

#### Predictive cruise

Predictive cruise sits outside the presets. It lets cruise read the road about a mile and a half ahead: it banks a little speed before a climb, gives up the last few miles per hour at a crest instead of fighting for them, and stops adding speed it would only brake away before a descent.

#### Lane keeping

Lane keeping controls how much steering you do. Full keeps the truck centered with no lane work, turns Left and Right into tap lane changes, and takes your exits for you, including the destination exit, with no signal and no exit lane. Partial steers the truck through the road's bends and drifts gently, with generous steering help; lane changes and speed are yours. Off drifts like a real wheel, bends included, and every exit needs your turn signal set and a steer into the exit lane where it opens.

On partial or off, with lane-departure warning on, the engine leans back toward lane center when you drift, and you steer the way it leans; a centered-lane chime confirms you are centered again, and the rumble strip is panned to the side you have drifted toward near the lane edge. The road noise underneath leans to where you sit in your lane whichever way you are drifting, so it tells you position, not direction. On full the engine still leans for the bends and corners ahead, and the road noise stays centered because the truck is.

Lane keeping is a preset field: Realistic sets it to off, Balanced to partial, and All assists to full, so the preset row can never describe less automation than you actually have.

#### Speed keeper

Speed keeper sits outside the presets and is never changed by choosing a preset. Where adaptive cruise is unavailable, such as the city streets to a facility, gate queues, and construction zones, pressing K starts automatic speed control in speed-keeper mode. It holds your current speed at or below the zone limit and creeps behind queued traffic, so the accelerator does not need to stay held down. A facility approach is a chain of streets with their own posted numbers, so when the street under you posts a higher one the keeper takes it and says the new number; when it posts a lower one the keeper simply obeys it. It also looks ahead rather than reading only the limit under the wheels: it eases early for the next judged street turn or the next lower posted limit, and the corner call tells you when the keeper has the turn, so you know whether to leave it alone. When the next corner is too close to build back up to the street's number and brake again in time, the keeper holds the corner's own speed until it.

On the open road it automatically changes to adaptive cruise and accelerates toward the posted limit, or restores the cruise target you selected earlier. Entering another restricted zone changes back to the speed keeper. The same handoff covers an open road where a hazard or a stop has left you below 20 miles per hour with the session still armed: the speed keeper builds speed behind whatever slowed you, and adaptive cruise takes over at 20. With the speed keeper off, the cab says once that automatic speed control resumes at 20, and the pedals are yours until then.

If you start it during the deadhead, the planned pickup pauses the session while you check in and load, keeps it through a save, and resumes it after departure once the truck is rolling.

Plus and Minus adjust the remembered open-road cruise target in either mode, snapping outward to the next multiple of 5 the same way, or by exactly 1 mile per hour with Control held.

Any brake input outside that planned pickup, a hazard, or pressing K again cancels the whole session so it cannot restart unexpectedly. Speed keeper is on by default and can be turned off in Settings, Gameplay, Driving assistance.

#### Latching brake

Latching brake is an input accommodation outside the presets, on by default. Tap the brake, then press again and hold for half a second, and a click plus a spoken confirmation latch it so it stays applied hands-free. Press Down arrow once to take it back; the accelerator releases it instantly. See the driving controls table for the full gesture. The throttle key never latches -- holding it is only for moving and for the hold that changes direction, including getting out of reverse. Off turns the brake latch off so a tap or a held key is just a tap or a held key. A key you physically hold down still overrides the assists.

#### Curve callouts

Curve callouts sit outside the presets, on by default. A co-driver
calls the bends that demand slowing before they arrive -- "Sharp left,
half a mile. Advise 35." -- and stays silent for bends you are already
slow enough for. See Mountain Driving for how to drive with the calls.

### Changing settings

Settings are grouped into categories. In a settings category, Up and Down choose
a setting, Right arrow or Enter changes it forward, Left arrow changes it
backward, and Escape returns to the category list. Changes are saved as they
are made.

Gameplay opens four screens, and each setting below is on the screen it is
listed under. Driving assistance is covered in full above.

### Difficulty and hours of service

| Setting | Purpose |
| --- | --- |
| Driving mode | Choose Relaxed, Standard, or Real time pacing and pressure. Relaxed keeps every driving system but gives wider hazard response windows, fewer random hazards, gentler collision damage and fatigue, calmer routine speech, and the most time to respond. Standard keeps balanced timing and consequences and moves distance and time twice as fast, so a driving day takes half the real time and decisions arrive sooner without extra forgiveness. Real time keeps Standard's pressure, lines the date and time up with your computer's clock, and runs the driving clock at the speed of a real clock, so a mile takes as long as it really would; with the weather source set to real world it is the most true to life the game gets. Aligning the clock does not move delivery time remaining, career progress, or hours of service. At low speed the compressed pacings ease toward real time, and deliberate parked waiting runs at double the selected pace; in Real time the clock is real at every speed, parked included. Breaks and sleep at stops pass the clock the same way in every mode. Any of the three can be changed mid-drive from the pause menu; the new pacing starts when the truck next stops. |
| Hours of service | Choose realistic or relaxed legal limits. Both use the same 11-hour driving limit, 14-hour duty window, and break after 8 hours. Relaxed reduces fines, inspections, and random hazards. |

The dash overspeed alert has no setting. It speaks once and then chimes,
faster the further over you go, when you are more than 7 miles per hour over
the posted limit -- above the pace adaptive cruise itself holds, so it never
chimes at a speed the truck chose, and below the point where a trooper can
act on your speed, so it still warns you while slowing down is free. Braking
quiets it, and settling back under the limit disarms it.

### World and traffic

| Setting | Purpose |
| --- | --- |
| Weather source | Switches between simulated weather and live conditions for your current route position while driving. Route planning checks live city conditions along the route when available. |
| Traffic source | Switches between simulated traffic incidents and live reports from state 511 services when available. |
| Parking source | Switches between simulated truck parking and live availability when available. |
| Live weather controls calendar | When on, live weather uses today's real date and season. When off, live conditions continue while the career date advances at midnight and its seasons pass. |

### Controls

| Setting | Purpose |
| --- | --- |
| Units | Switch speed and distance between miles and kilometers. |
| Transmission | Switch between automatic and manual transmission. |
| Automatic direction changes | In an automatic, both styles now change direction the same way: a fresh press held at a standstill. A brake held through a stop just holds the truck. The setting remains for familiarity. |
| Controller | Accept controller input alongside the keyboard. The keyboard always stays active. |
| Haptics | Use controller vibration for hazards, hard braking, rumble strips, and road seams. |
| Keyboard shortcuts | One row per driving control, naming the key it is on. Enter on a row, then press the key you want, with Shift, Control, or Alt held if you want a chord. A key another control already has is refused by name; Escape keeps the current key. The pause key, Enter, F1, the Control keys that stop the voice, plus and minus, the radio dial keys, and the message review keys stay fixed. A last row puts every key back to its default. |
| Controller buttons | The same for the pad. Enter on a row, then press the button you want, with the right bumper held for the second layer. Press the button the row already has to keep it. Start, Back, the bumpers, the triggers, and the sticks stay fixed. |

### Audio settings

| Setting | Purpose |
| --- | --- |
| Master volume | Overall game volume. |
| Gameplay cues volume | Horn, alerts, road, facility, and gameplay cue sounds. |
| Lane and edge cue volume | How loud the road cues are when you leave your line, next to everything else: the rumble-strip and shoulder textures, the lane locator, and the warning bars before a hairpin. It rides on the Gameplay cues volume above rather than replacing it, so this row moves those cues alone. Quieter keeps them under the engine, standard matches it, and louder cuts through. Presets never change it. |
| Weather sounds volume | Rain, wind, thunder, snow, and fog sounds. |
| Engine sounds volume | Engine start, shutdown, and running engine sounds. |
| Engine voice | Real plays the engine recorded from a working truck cab, following the RPM through its range. Classic keeps the original engine sound. Changes apply immediately, even while driving. |
| Music volume | Menu and facility background music volume. |
| Music source | Original, the default, plays the licensed menu and Roadhouse music. Synthesized has menus and the Roadhouse play music the game composes itself, with no voiced breaks, plus the original three tracks from Freight Fate 1.5. Changes take effect at once, even mid-drive. See below for what Synthesized mode does to the radio dial. |
| Music seed | Picks every synthesized piece. Enter opens a field where you type a whole number, such as a seed someone shared with you; Escape leaves the seed as it was. Left or Right rolls a new seed and reads it aloud, so you can share a favorite. Every synthesized piece changes, and the current music restarts at once. |
| In-cab radio volume | Driving radio music volume. It defaults lower than speech and safety cues. |
| Radio streamer-safe mode | Off by default: the full dial plays, including real public streams and personal playlists. Turn it on while streaming or recording to keep the radio on built-in safe stations only. With Music source set to Synthesized, this locks the radio to the synthesized Roadhouse alone; every other station control does nothing, though the radio key, volume, and now playing still work. |
| Shuffle personal playlists | Off by default: each of your playlists plays top to bottom and resumes where it left off. On plays it in a random order, every track once before any repeats, with a new order each time through. |
| Menu and UI sounds volume | Menu movement, selection, warning, and cash sounds. |

### Speech settings

| Setting | Purpose |
| --- | --- |
| Driving speech | Standard gives full confirmations, status updates, and a driving tip once per route leg. Quiet keeps short spoken updates, including lane openings, assist confirmations, costs, and navigation. Urgent only speaks safety warnings and directions requiring action; routine costs, status, and tips are silent, while road heads-ups and confirmations use sounds. Events suppressed by the speech setting stay out of message review. Readout keys always answer on demand. Billboards, place names, and landmarks keep their own switches below. |
| Roadside chatter | The ambient color spoken between navigation cues: entering parks and forests, named river crossings, mountain passes, museums and attractions, and parody billboards. One master switch turns it all on or off, and each kind has its own switch below it. Safety and navigation speech is never affected, and town names have their own Place callouts setting. |
| Place callouts | How much the co-driver says about places along the road. Sparse, the default, speaks only the town names that explain a speed limit change, like Entering Strawberry right before its 35. All adds the towns the route passes through or skirts. Off silences place names entirely. Speed limit announcements themselves are never affected, and no tier ever reads out every place on the map. |
| Menu position announcements | When on, menus say the position, like 3 of 10, after each option. Turn off to hear only the option. |
| Driving event voice | Routes road events through the main voice or a separate software voice when available. |
| Output | Speech and braille, the default, speaks every line and, with NVDA or JAWS, shows it on your braille display as well. Braille only puts every line on the display and speaks nothing, so you can play from the display with speech off: menus, readouts, and road events alike, including the ones the driving event voice would otherwise speak. It needs NVDA or JAWS. With any other voice the game keeps speaking and the row says so, and if your screen reader quits mid-drive, speech comes back until it returns. |
| Speech rate | Appears only when the current voice source supports rate changes. |
| Speech pitch | Appears only when the current voice source supports pitch changes. |
| Speech volume | Appears only when the current voice source supports volume changes. |
| Speech voice | Appears only when selectable voices are available. |

### Online menu

Online features live in their own Online menu on the main menu rather than
inside Settings. Choosing Online inside Settings opens that same menu, so
the old path still works. The Online menu gathers the public drivers list,
your orinks.net account, cloud backup, and every sharing choice in one place:

| Item | Purpose |
| --- | --- |
| Driver directory | Every driver with a public profile, whether they are on duty right now or not. Drivers on duty come first with what they are doing, then everyone else by when they were last on duty, in round figures like three days ago or two weeks ago; a driver the game has never seen on duty says so. The list does not update by itself; Check again asks once more. Press Enter on a driver to read their public profile, the same screen the Drivers on duty list opens. Viewing it shares nothing about you. |
| Drivers on duty | Reads the public list: each driver's name, what they are doing, and how fresh the report is. The list keeps itself up to date about once a minute while it is open, quietly, holding your place, the same way the list on orinks.net does; there is nothing to press. Viewing it shares nothing about you and does not require sharing to be on. Press Enter on a driver to read their public profile: their name and whether they are on duty, their current career, employment and carrier, level and title, truck, a career resume, their achievements across every career, and their latest road journal lines, one fact per row. A driver whose profile is not public says so. |
| Say when drivers go on or off duty | Off by default. When on, the game says when another driver sets off or signs off, like Road Star is on duty, wherever you are in the game, including while driving; the line waits its turn behind anything urgent. It checks the public drivers list about once a minute and never mentions you. Works without an orinks.net account and shares nothing about you. |
| Online services | The master switch for the orinks.net and sharing services. When off, the drivers list, Profile sharing, Cloud backup, Mastodon sharing, and Discord presence all behave as disabled, and each keeps its own setting for when you turn the master switch back on. Real-world weather, traffic, and parking are separate: they follow their own toggles under Settings, Gameplay, World and traffic. |
| Account achievements | Reviews the achievements earned across every career on this installation. Choose one of seven short categories, then review its achievements in catalog order using the same earned and locked style as the career achievement browser. The first item repeats the controls and account-wide scope. This is a read-only account collection; the main-menu Achievements item still shows each career separately. |
| Your profile | Reads your own public driver profile the way any player hears it from the drivers list. It needs your orinks.net account, and if Profile sharing is off it says so and names the setting to turn on. |
| Set up orinks.net account | Connects the game to your orinks.net account. Connecting turns Profile sharing on and starts backing your careers up to that account, so your public driver profile has career statistics on it from the first delivery instead of reading as empty; each of those is a single item on this menu if you want it off. Everything below uses this one sign-in. It takes an activation code and your browser: the game asks orinks.net for a short code, speaks it, and opens your browser at the sign-in page with the code already filled in. Sign in there and the game notices and finishes on its own. The screen keeps two items for as long as the code is live -- one spells the code letter by letter in the NATO alphabet, one puts it on your clipboard -- so you can carry it across to a browser the game could not open for you. You need an orinks.net account before you start; the setup connects one, it does not create one. |
| Open my driver setup page | Opens your driver setup page on orinks.net in a browser, so the address is never something you have to remember or type. That page is where you change your driver name, turn Profile sharing on or off, see every computer signed in to your account -- when each was added and last played -- and sign any of them out, or all of them at once. If the game cannot open a browser for you, it puts the address on your clipboard and says so; if the clipboard refuses too, it reads the address out. |
| Profile sharing | One optional public setting covers the drivers list, eligible profile details, official achievements, automatic road-journal posts, and the updates feed. It does nothing until you connect your orinks.net driver, and connecting turns it on; one item here turns it back off whenever you like. While you drive with the radio on, your line on that list also names the station you are listening to. Money is handled in two deliberate halves: lifetime career earnings, the running total your career has ever earned, is a public career statistic, while the money you currently have is never published. Beyond that, the game never publishes the full save, coordinates, active cargo details, real name, or precise live location. Detailed career statistics appear only after orinks.net accepts a validated private cloud backup; without one, the public profile remains available but omits those statistics. Turning Profile sharing off stops local posting immediately and hides the public profile independently of Cloud backup. |
| Back up saves to your orinks.net account | After each game save, upload that career to your own orinks.net account so you can restore it on another computer or after losing this one. Connecting your orinks.net account turns this on, because the career statistics on your public profile are read from these backups; turning it off leaves the profile without them. Backups are private to your account and never become public downloads. orinks.net validates each revision before accepting and signing it. It uses the same one-time sign-in as your driver profile, so set that up first. The last ten accepted backups of each career are kept. |
| Restore a cloud backup | Lists the careers backed up to your account, newest first, and brings one onto this computer. Freight Fate verifies the server signature before replacing anything. A missing, altered, or unsupported signature leaves the local save untouched. A successful restore keeps the replaced save beside it as a fallback file and signs the restored copy for this computer. If the same career was played on two computers, this menu is also where you choose which accepted copy wins. Each career's screen also has Back up this career now, which sends this computer's save to your account straight away and tells you the result, so a stuck automatic backup is never the only way up. |
| Automatic cloud retention | Your account keeps up to ten cloud careers. When a new active career replaces the least recently played cloud career, Freight Fate names the removed cloud backup and confirms that its local career was not deleted. |
| Share notable deliveries to Mastodon | When on, finishing a delivery that earns an achievement, a level, or a perfect streak posts a short public summary to your own Mastodon account with the FreightFateRuns hashtag. That tag is only used by these automatic posts; the FreightFate tag is where players talk about the game, so you can mute one without losing the other. Routine deliveries are never posted. Off until you link a Mastodon account. |
| Link a Mastodon account | Opens a page on orinks.net where you authorize your own Mastodon server, using the same orinks.net sign-in as driver setup. Unlinking happens on the same page. |
| Discord presence | Show broad activity in Discord (menu, terminal, driving, resting, delivering) with high-level route and cargo. Only general game status is shared, never your saves or personal details. If you pause or leave the game sitting for half an hour, the presence comes down until you play again, so it never claims you are mid-run when you have stepped away. On by default; no effect if Discord is closed. Works without a driver profile. |

### Problem reports

| Setting | Purpose |
| --- | --- |
| Where the game log is saved | Reads out the full path of this session's log file and shows it in the window. Packaged downloads always keep a log; it records the session including everything the game said out loud, so attaching it to a bug report shows exactly what you heard. The session before this one is kept beside it, so restarting the game to check something does not lose it. Both files stay on your computer; the game never sends them anywhere. |

## Audio, speech, and accessibility

Freight Fate is built to be playable by ear. Menus, status screens, update
flows, driving alerts, route information, and settlement summaries are available
through the game's audio and text output. The window mirrors the same
core menu and status information as plain text.

Freight Fate speaks through whichever screen reader you already run: NVDA,
JAWS, ZDSR, PC-Talker, BoYing, SenseReader, System Access, ZoomText, Narrator,
VoiceOver, Orca, or Speech Dispatcher. Where none is running it uses a software
voice instead -- SAPI or the Windows voices on Windows, the system voice
elsewhere. There is no list of approved readers: the game asks each one in turn
whether it can speak right now and takes the first that says yes, so a reader
you start in the middle of a drive is picked up on its own.

To see what your own computer offers, start the game with
`--list-speech-backends`. It names every reader and voice it found, says which
of them can speak, and says which one it would use.

Driving events can use a separate software voice when available, so road alerts
do not fight with a screen reader's own speech.

The truck's own voice is built to stay informative rather than decorative:
the engine never repeats a loop your ear can learn, brakes and gear changes
are the real mechanisms, tire sound rises and falls with speed, and road-seam
thumps give the road texture through both sound and controller vibration.
Every turn signal -- lane change, exit, pull-over -- plays a clear indicator
tone panned to the side you are signaling, the sound a modern cab makes.

Audio is layered by category:

| Category | Examples |
| --- | --- |
| UI | Menu movement, selection, warning, cash, pause, unpause, and notification sounds. |
| Engine | Engine start, shutdown, idle, and RPM-tracking running engine audio. |
| Vehicle | Horn, gear shift, parking brake, brake air, road noise, road seams, collision, rumble strip, and fuel pump sounds. |
| Weather | Rain, snow, wind, thunder, and fog sounds. |
| Route events | Hazards, construction zones, inspections, state crossings, traffic slowing, and toll charges. |
| Facilities and stops | Facility gates, docks, rest stops, and weigh station lanes. |
| Music | Menu, facility, day-driving, and night-driving music pools. |
| In-cab radio | Keyboard-controlled driving music and safe station status. |

Speech, gameplay cues, and warnings are the primary access path. Radio, music,
and ambience sit behind those cues and can be adjusted separately. The radio
draws power from the engine: it falls silent when the engine shuts off and
comes back when the engine starts. Turning it on lands on a station that plays
clean -- if the remembered station has gone fringe or out of range, the radio
retunes to the strongest signal instead. Dial tuning moves through stations
the truck can currently receive from the checked-in catalog, using the route's
approximate position and each station's range; the terrestrial category lists
the strongest signal first. The Radio status screen lists the currently
receivable stations. Saving a station with O keeps it in the Favorites
category, one category jump from anywhere on the dial.

The Freight Fate Roadhouse and the Night Line have their own hosts, who break
in between songs. Fictional regional stations cover markets across the map --
country, classic rock, and blues and soul formats with their own song pools --
and behave like real FM signals: full volume near the market, thinner audio and
static crackle at the fringe of the range, and a fade to static as you drive
past the edge. When a station drops out of range the radio announces it and
tunes to the strongest local station the truck can still hear clearly, and
names it. Only when nothing else is on the air does it fall back to the
Roadhouse, which is receivable everywhere along with the Night Line and the
satellite fallback.

With Settings, Audio, Music source set to Synthesized, the Roadhouse plays
music the game composes itself instead, with no host breaks, station IDs,
or jingles. Freight Fate's own fictional regional stations leave the dial
entirely; the terrestrial, web, and personal-playlist stations are
unaffected. With Music source Original, the dial plays exactly as described
above.

Real public stream stations, including AFN choices, play out of the box; turning
streamer-safe mode on hides them, for anyone streaming or recording their
drive. When the BASS audio backend is available, those stations play from
their public stream URLs. If a selected station cannot play, the radio falls
back safely instead of blocking the drive.

You can put your own music on the dial. Drop M3U, M3U8, or PLS playlist files
into the Playlists folder next to your saves (the game creates it on first run)
and each file becomes a station under Your playlists, named from the playlist.
The entries can point at files anywhere your computer can read, including
network drives, and the usual formats all play: mp3, ogg, opus, flac, aac, and
wma, plus tracker module files such as .it, .xm, .s3m, .mod, and .mo3, the
kind OpenMPT and similar trackers save. Entries can also be internet stations: a playlist exported from an
internet radio app is nothing but stream addresses, and those play too, in the
order the playlist lists them alongside any music files. The station remembers
its place while you tune away during a drive, and an entry that will not open
is skipped rather than stopping the music -- a stream is given time to connect
first, so it is never skipped for being slow. If nothing in a playlist will
play, the radio says so and names the folder rather than going quietly silent.
Opening the Radio status screen re-reads the folder, so a playlist you add or
fix mid-drive appears on the dial without starting a new run. Personal
playlists ride the same streamer-safe gate as real streams -- turning the mode
on hides them, because the game cannot vouch for what your files are licensed
for. Ctrl with any tune key jumps straight to the Your playlists category.
A playlist of your own music files plays in the file's order unless Settings,
Audio, Shuffle personal playlists is on, which plays every track once in a
random order before any repeats.

The dial is grouped into categories -- route playlist, Freight Fate stations,
your playlists, favorites, terrestrial, AFN, satellite, international,
fallback, web radio, and other stations -- and Ctrl with any of the tune keys
jumps between them, so you can skip the AFN stations to reach the local dial. The tune keys are Page Down and Page Up, with semicolon
and apostrophe as a second pair for keyboards where the Page keys are
awkward. Shift with any of those four keys changes the radio volume instead
of tuning, in 10 percent steps, spoken as it moves, and works whether the
radio is on or off. The bracket keys are message review, not the radio.

The real side of the dial is large: hundreds of public stations across the
lower forty-eight, international public broadcasters that are always in
range, and translator fills that light up the loneliest corridors. Real FM
behaves like FM, fading at the fringe with hiss before it drops, and a stream
that will not play at all hands over to another station in the same band and
leaves the dial for the rest of the session rather than blocking you.

Useful accessibility patterns:

- Use F1 when you are unsure what the selected item does.
- Use Space, F, C, R, V, and Tab while driving instead of waiting for automatic
  reminders.
- Turn on the lane locator with I when you want continuous confirmation of
  where the truck sits in its lane, rather than waiting for a drift cue.
- Open Learn game sounds, on the main menu and on the pause menu while you
  drive, to hear any road cue on demand with an explanation of what it means
  and what to do about it. Arrow to a sound, press Enter to hear it, and F1
  for what it is telling you.
- Use the status menu when you want reviewable lines instead of one long status
  message.
- Use the Radio status screen when you want the current station list before
  tuning.
- Lower music or ambience if speech or route cues are hard to follow.
- Check the stop menu for available services. If fuel, repair, or sleep is
  absent, you cannot use that service at this stop.

## Troubleshooting

If the game will not start after extracting a Windows build, check whether your
antivirus quarantined the unsigned `FreightFate.exe`. Restore it or add an
exclusion for the extracted game folder.

If Check for updates says the copy is running from source, download a packaged
release archive from the releases page and play from that folder.

If an update cannot reach the server, check your internet connection and try
again later. The game writes packaged-build logs to `logs/game.log`, which can
help when reporting update or startup problems. That log also records every
line the game spoke, so it is the most useful thing to attach to any bug
report. Settings, Problem reports, Where the game log is saved reads out its
exact location; the previous session is kept beside it as `logs/game.prev.log`.

If the game says at the main menu that it started without sound on Linux,
your sound system's ALSA default device is not reachable. On a desktop with
PulseAudio or PipeWire that means the ALSA plugin for it is not installed:
`libasound2-plugins` on Debian and Ubuntu, `alsa-plugins-pulseaudio` or
`pipewire-alsa` on Fedora, `pipewire-alsa` on Arch. Install it and start the
game again. Speech is separate and keeps working either way.

If your save is missing after extracting or updating a Windows or Linux
archive, look for another nearby
`saves` folder and copy or move the whole `saves` folder into the active
`FreightFate` folder. Keep `profile.key` with the profile files.
AppImage and macOS saves remain in the platform folders listed under
[Quick start](#quick-start), outside the game itself.

If the engine will not start because the tank is empty, the out-of-fuel rescue
can bring enough fuel to continue and charges the career balance.

If you miss a rest stop, continue safely and press T to plan the next
sleep-capable stop. If you are already safely stopped at the missed route point,
T opens its menu when the stop supports one.

## Release notes and more data

Stable and snapshot release notes are on the
[Freight Fate releases page](https://github.com/Orinks/Freight-Fate/releases).
The in-game What's new reader can also review notes for an available update.

For deeper data reference, see:

- [Route, Stop, And Corridor Data](route-stop-data.md).
- [Freight Market And Facility Data](freight-market-facilities.md).
