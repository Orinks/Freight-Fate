# Freight Fate 1.9 alpha test book

The 1.9 line is an opt-in alpha: a version with lots of changes, running
ahead of the calm nightly line. This book is for the people testing it —
it says what is different, how to hear each change for yourself, and when
to call it working. The physics side (jake, brakes, ice, chains) has its
own companion volume, `docs/physics-playtest-checklists.md`; this book
covers everything else and points there for the winter suite.

Written for a screen-reader playtest: everything to verify is spoken,
never visual. Each checklist says how to set it up, what to do, what to
listen for, and when to call it a pass. Work them in order or
cherry-pick — every one stands alone.

When something fails, note three things: what you did, what you heard,
and what you expected to hear. That sentence pair is worth more than any
log file.

## Chapter 1. What the alpha changes, system by system

An exhaustive tour of the gap between the nightly you are used to and
this alpha. Each entry names the chapter or companion checklist that
tests it.

**The truck is a different machine.** The engine brake is now a real
three-stage jake working through the gears — strong in a low gear at high
RPM, nearly useless in overdrive — and automatics pre-select down to put
it to work. Brakes heat like real drums: drag them down a grade and they
fade; jake-and-snub keeps them cool. Letting a downhill spin the engine
past its limit now wears the engine. Companion volume, checklists 5
and 9.

**Winter is real.** Freezing rain is its own weather and the one worth
parking for. Winter tires are a garage choice with honest trade-offs.
Chains ride in the side box, take real minutes and fatigue to hang (more
in the dark), transform ice stops and icy descents, and grind apart on
bare pavement. Chain laws activate over the steep passes with flashing
signs, warnings, and a possible five-hundred-dollar citation. Worn tires
hydroplane at lower speeds; the jake can break the drive wheels loose on
ice. Companion volume, checklists 1 through 8.

**Wear, and the truck it belongs to.** Tires, brakes, and engine each
have their own wear meter, driven by how you actually drive. Wear talks
back: bald tires grip less, worn brakes fade sooner, a tired engine loses
power and drinks fuel. Condition — wear, damage, fuel — now stays with
each truck instead of following your profile between tractors. Chapter 2.

**Truck stops earn their parking lots.** Meals, showers, and rig care are
purchasable at real branded stops, each good at what it is really known
for, and the effects are spoken buffs with clocks on them. Road shops fix
tires and brakes at brand-true prices; Big Buck's, famously, fixes
nothing. Chapter 3.

**The lane is a place.** Discrete lanes with real traffic in them:
dodgeable hazards, sideswipe risk, construction lane closures, keep-right
nags, and exits that gate on being in the right lane. Highway exits take
a real setup — signal with X, get to the exit lane, make ramp speed at
the gore. Signalized ramp terminals run a red/green cycle with dedicated
earcons. Chapter 4.

**Traffic has a clock.** Congestion is grounded in real federal traffic
counts per leg: metro stretches jam at rush hour and flow free at
midnight, and entering a live jam puts slow traffic in both lanes.
Chapter 5.

**Cities are driven, not teleported.** Tier-1 surface streets carry real
turn-by-turn cues with direction-shaped earcons panned to the maneuver
side. Arrivals flow off the ramp onto the destination's streets; loaded
departures drive the streets out to the on-ramp. The terminal's freight
office, garage, and dealer are short local drives. Chapter 6.

**The law is watching more than your speed.** Weigh-station blow-pasts
and severe visible damage draw stops; running from lights escalates to a
felony stop with spike strips; construction zones stage a merge and
flagger before the barrels; CB chatter hints at bears ahead. Traffic
stops read a real logbook — the in-cab Record of Duty Status — and dock
work takes spoken on-duty time. Chapter 7.

**Three driving-pressure modes.** Relaxed keeps every system but spaces
hazards wider, allows more response time, and quiets routine speech;
Standard keeps the old balance; the former Fast is now called Realistic.
Chapter 8.

**The career reads like employment.** New careers choose among fictional
starter carriers (assigned equipment, carrier-paid fuel and repairs,
different wage and freight personalities) or a riskier owner-operator
start. A 30-level business arc runs company ranks to the leased-on gate
at 18, own authority at 25, independent ranks to 30. Dispatch freedom is
earned: new hires run what dispatch assigns against a small decline
budget; the full board unlocks at level 8; route choice belongs to
owner-operators. Trailers, carrier accounts, reputation trust bonuses,
endorsement courses, and a first-day briefing that repeats until your
first load. Chapter 9.

**114 achievements.** State, region, and city arrivals, cargo firsts,
close calls, mishaps, and career milestones. Chapter 9 covers the spot
checks.

**The radio follows the map.** M toggles it, brackets tune the stations
you can actually receive, twelve fictional regional stations fade to
static at the edge of their range and hand back to the Roadhouse.
Streamer-safe by default; real public streams behind an explicit opt-in.
Chapter 10.

**The world got big and specific.** More than a hundred new dispatchable
cities fill the dead zones — the mountain West, the northern plains, the
Great Basin, Appalachia — on their real roads with real grades,
checkpoints, and truck stops. Roadside landmarks speak as ambient chatter
with per-kind switches in Settings. The career clock crosses real US time
zones, spoken, with deadlines in destination local time. Chapter 11.

**Cloud restores get a second integrity check.** Beyond the server's
signature, a restored profile must pass the game's own sanity rules, and
a file that fails is refused with a plainly spoken reason. Also shipping
on the nightly line. Chapter 12.

**Old saves keep working.** Careers back through the version-4 schema
load with sensible defaults; your current wear settles onto every truck
you own the first time a pre-alpha save loads. Chapter 12.

## Chapter 2. Wear meters and the truck they belong to

### 2.1 The three meters move for three reasons

Setup: an owner-operator profile with a loaded, longish leg — a few
hundred miles of ordinary interstate.

Do: before departing, open the truck status readout (Tab while driving,
or the garage's condition readout in town) and note tire, brake, and
engine wear. Drive the leg with some deliberate sins: ride the service
brakes on one descent, hold a low gear past the shift point for a minute,
run loaded the whole way. Deliver, and listen to the delivery summary.

Listen for: the delivery summary telling you what the run added to each
meter, separately. The status readout speaking all three meters any time
you ask.

Pass when: each meter moved and the summary attributed wear where you
earned it — brake wear from the dragged descent, engine wear from the
lugging and the loaded hours, tire wear from the miles.

### 2.2 Wear talks back

Setup: force a worn truck honestly (many legs) or use an established
high-mileage profile.

Do: compare a hard stop and a fuel readout against a fresh truck's.

Listen for: worn brakes pulling weaker and overheating sooner (the fade
warning arrives earlier than the companion volume's fresh-truck
anchors); a tired engine burning noticeably more fuel on the F readout
over the same leg.

Pass when: the worn truck is audibly worse in the way each meter
promises, and the garage quotes a repair for exactly the worn item.

### 2.3 Condition follows the truck, not you

Setup: an owner-operator with enough money for a second tractor.

Do: run your current truck until it carries obvious wear and a
half-empty tank; note the readouts. Buy a second truck at the dealer and
drive it. Then swap back.

Listen for: the new truck rolling out fresh with a full tank — none of
your first truck's wear or fuel state carried over. On the swap back,
the first truck exactly as you left it: same wear, same tank.

Pass when: nothing teleported between tractors, and the garage in town
fixes the truck you actually drove in, not the one parked.

### 2.4 The garage sells more than tires

Setup: an owner-operator in town with worn brakes and a worn engine.

Do: open the terminal garage and walk the service list.

Listen for: brake jobs and engine overhauls offered alongside tire
replacement, each quoting shop time and a real price. On a company
driver profile, the same services billing the carrier instead.

Pass when: each service restores its meter, costs an owner-operator real
money, and takes spoken shop time.

## Chapter 3. Truck stops: meals, showers, and rig care

### 3.1 One food buff at a time, and it never adds hours

Setup: any loaded run past branded truck stops; note your fatigue on the
clock readout (C).

Do: pull into a stop (T at an announced stop) and buy a hot meal. Drive
an hour, then buy an energy drink somewhere else.

Listen for: the meal easing fatigue immediately and the status readout
(Tab) naming the active food buff and how long it has left; the energy
drink replacing the meal buff rather than stacking on it. Petro's Iron
Skillet dinner beating a no-name diner's effect.

Pass when: one food buff exists at a time, the readout tracks it, and
your legal driving hours never grew — buffs touch fatigue, never the
clock.

### 3.2 The shower deal is real

Setup: a run past a Pilot or Flying J with fuel below full.

Do: buy fuel there, then check the shower price. Compare with a stop
where you bought nothing.

Pass when: the fuel purchase made the shower free, like real life, and
without fuel it costs money.

### 3.3 Rig care buffs, one per system

Setup: an owner-operator mid-trip near a Speedco or Love's.

Do: buy the lube-bay service, then a tire rotation, then a bottle of
diesel additive at any fuel stop.

Listen for: each purchase spoken with what it slows (engine wear for the
lube bay, tread for the rotation, a little of both for the additive) and
the status readout carrying one buff per rig system — a new lube
purchase replaces the old one instead of stacking.

Pass when: the delivery summary's wear lines come in lower than an
unbuffed run of the same leg, and no purchase ever added driving hours.

### 3.4 Road repairs are brand-true

Setup: a worn truck and a route with a spread of branded stops (the
interstate picks in the companion volume all qualify).

Do: at a Love's or Speedco, ask for tires. At a TA or Petro, ask for a
brake job. At some other major travel center, ask for tires. At Big
Buck's, ask for anything.

Listen for: Love's and Speedco replacing tires fast at close to the
garage price; TA and Petro running full service shops that also do
brakes on the road; other majors mounting tires at a spoken road markup;
an engine overhaul always deferred to your terminal garage; Big Buck's
fixing nothing, famously. Road shops selling the whole job or none of
it — no partial repairs when cash is short.

Pass when: every brand behaved by its real-world reputation and the
prices said so out loud.

## Chapter 4. Lanes, exits, and ramp lights

### 4.1 The lane is discrete and the taps are real

Setup: Settings with steering assist off; any multi-lane interstate leg.

Do: press L to hear your lane. Tap Left and Right arrows to change
lanes; try one while on an exit ramp.

Listen for: signal clicks with each timed change, L describing the new
lane, and the ramp refusing: "You are on the exit ramp. No lanes to
change."

Pass when: every change is announced, lands in the adjacent lane, and
the lane readout always agrees with what you last did.

### 4.2 Brake or change lanes

Setup: a busy leg, Standard or Realistic pressure.

Do: when a dodgeable hazard calls "Brake or change lanes!", dodge with a
lane change instead of braking — but press L first to know where the
traffic is.

Listen for: a clean dodge when the adjacent lane is clear; sideswipe
risk spoken when it is not; the CB nagging you to keep right if you camp
the hammer lane afterward.

Pass when: the lane change genuinely resolves the hazard and sideswiping
real traffic carries real consequences.

### 4.3 Construction closes a real lane

Setup: any leg that announces a work zone.

Do: obey the merge — flagger and taper first, then the barrels. On a
second pass, stay in the closing lane too long on purpose.

Listen for: the staged approach in order (merge warning, flagger,
taper), then barrel strikes and damage if you ignored it, and work-zone
enforcement pressure hinted on the CB a few miles out.

Pass when: complying is calm and ignoring it is expensive.

### 4.4 Exits take a setup

Setup: any leg with announced exits; know your destination exit (R for
progress, Shift+R for what the next exit offers).

Do: when your exit is announced, press X to commit to it. Follow the
GPS: right-side exit lane, then ramp speed by the gore. Once, miss the
exit on purpose.

Listen for: the GPS asking for the exit lane, checking your speed at the
gore point, and explaining plainly what happens now that you missed —
and merge/exit traffic pressuring the maneuver while you do it.

Pass when: a set-up exit flows clean, a missed exit costs real miles and
is explained, and X while a pull-over is pending signals that instead.

### 4.5 The ramp light is an instrument

Setup: exits whose ramps end at a signal (thousands do — they are baked
from real intersection data).

Do: take a ramp to its stop bar on a red; wait for the cycle. On another
ramp, run the red deliberately.

Listen for: the dedicated red-light earcon and spoken callout at the
bar, the distinct green earcon on release, and cross-traffic punishing a
run red with more than words.

Pass when: red means stop, green frees you, and running it hurt.

### 4.6 The ramp's ending is announced before the ramp

Setup: any leg with announced exits.

Do: signal for an exit with X and listen to the whole announcement.
Press U on the mainline before the exit. Then take the ramp and watch
the clock: press C once on the open highway and again while braking
down a ramp that ends in a light or sign.

Listen for: the signal-on announcement naming the ending -- "The ramp
ends at a stop sign." -- with a mile-plus still to drive, U carrying
the same phrase, and time slowing to real seconds from the gore of a
controlled ramp: the half mile down to the sign takes as long as it
would take a real truck, not a compressed blink.

Pass when: you always know how the ramp ends before you are on it, and
you always have real time to brake for it. A free-flow ramp still
passes in compressed time.

### 4.7 Latching pedals

Setup: Settings, Driving assistance, Latching pedals on (the default).

Do: on open highway, tap the accelerator, then press it again and hold
for half a second. Let go. Later, press it once to take it back. Latch
it again and tap the brake. Latch the brake on a long downgrade and
listen to the drums.

Listen for: a catch click clearly different from the gear click, then
"Throttle latched."; the truck holding power with your hands off;
"Throttle released." on the single press or instantly on the opposite
pedal; hazards, emergency braking, and the overspeed alarm dropping a
latched throttle on their own, spoken. A latched brake on a grade
heats and fades exactly like a held one -- the latch never edits
physics.

Pass when: the gesture never fires from ordinary pumping taps, every
latch and release is spoken, and no alarm ever has to shout over a
latched pedal that refuses to let go.

## Chapter 5. Traffic with a clock

### 5.1 Rush hour is a place and a time

Setup: a metro leg (into or out of Denver, Portland, or any big-city
corridor). Two runs: one arriving in the commute window, one near
midnight — the C key tells you the local clock.

Do: drive the same stretch at both hours.

Listen for: the rush-hour run jamming — spoken congestion, slow traffic
injected in both lanes, your following distance doing real work — and
the midnight run flowing free on the same asphalt.

Pass when: the difference between the two runs is unmistakable by ear
alone, and rural stretches never fake a jam.

## Chapter 6. Streets, city services, and both ends of the trip

### 6.1 Turn-by-turn on real streets

Setup: a delivery to a facility in a city with street-level data (big
terminals usually qualify; the arrival announces itself street by
street).

Do: follow the spoken maneuvers off the ramp to the gate.

Listen for: each junction spoken with block-aware distance ("Turn right
onto..."), a direction-shaped earcon panned to the maneuver side —
falling chime left, rising chime right, steady tone ahead — and highway
pressure language gone quiet on the streets.

Pass when: you can drive gate-to-gate by ear, and near-straight name
changes say "Continue onto" instead of inventing a turn.

### 6.2 Departures drive out, too

Setup: a loaded run out of a facility that announced street-level
arrival (chain-capable both ways).

Do: accept the load and start driving from the gate.

Listen for: the same streets outbound with every turn direction
correctly flipped, then the on-ramp merge onto the highway with your
clock and tolls continuous — no teleport to the interstate.

Pass when: the outbound chain mirrors the inbound one and the trip
odometer never jumps.

### 6.3 City services are drives

Setup: any terminal city; a reason to visit the freight office, garage,
or truck dealer.

Do: pick a service from the city menu and take the drive; press Enter
when the arrival is offered.

Listen for: a short local drive with sourced street names and road
context — real turns where the data supports them — instead of a menu
teleport.

Pass when: each service arrives by road and the drive matches the city
it claims to be.

## Chapter 7. Enforcement and the working day

### 7.1 The logbook is real and the law reads it

Setup: a career a few deliveries old.

Do: in town, open the city menu's Logbook item and arrow through the
entries. Then get pulled over on the road (speeding works) and listen.

Listen for: Record of Duty Status lines that match what you actually did
— drive blocks, on-duty dock time, rests — and the officer's stop
referencing your logbook rather than ignoring it.

Pass when: the book matches your day and the stop reads it.

### 7.2 Weigh stations and visible damage

Setup: a leg with an announced weigh station; separately, a truck
carrying severe damage.

Do: blow past the open scale once. Drive the damaged truck past patrol
presence.

Listen for: the blow-past drawing a roadside stop with consequences;
severe visible damage attracting a stop all by itself.

Pass when: both stop types trigger from their true causes and resolve
with spoken outcomes (fines, orders, or a clean release).

### 7.3 Running is a felony

Setup: courage, and a save you do not love. Get lit up, then do not
stop.

Listen for: escalating warnings, then the felony stop — spike strips,
the arrest, and a loaded run cancelled out from under you.

Pass when: the escalation is staged and spoken all the way down, and
the consequences land on your career, not just your ears.

### 7.4 Docks take time

Setup: any pickup and delivery.

Do: listen through the loading and unloading at both ends; check the
clock (C) before and after.

Listen for: spoken on-duty time passing at the dock, pull-ins taking
real minutes, and loaded launches ramping in heavy instead of leaping
off the line.

Pass when: dock time shows up in the logbook as on-duty and your
delivery windows price it in.

## Chapter 8. Three pressures, one truck

### 8.1 Relaxed is calmer, not smaller

Setup: the same leg, same load, driven twice: once in Relaxed, once in
Realistic (Settings, driving mode).

Do: drive both honestly.

Listen for: Relaxed keeping every system — weather, traffic, air brakes,
fatigue, hazards, consequences — but spacing hazards farther apart,
allowing more response time, building damage and fatigue more gently,
and speaking routine matters more quietly. Realistic keeping the
quickest decision cadence. Safety warnings staying ahead of hours and
fatigue chatter in both.

Pass when: the difference is pacing and breathing room, never missing
systems — nothing in Relaxed feels like a feature was removed.

## Chapter 9. The career is a job

### 9.1 The first day lands

Setup: a brand-new career.

Do: walk the start: pick among the starter carriers (or the
owner-operator start), listen to the first-day briefing, then stall —
visit menus without accepting a load.

Listen for: each carrier pitched with its real trade-offs (wage,
dispatch personality, freight mix, assigned equipment); the briefing
repeating until your first dispatch is accepted; the Career plan
terminal item naming your next practical step in plain words.

Pass when: a brand-new player who only listens knows exactly what to do
next.

### 9.2 Dispatch freedom is earned

Setup: a new company-driver career.

Do: try to refuse work. Decline dispatched loads until the budget runs
dry; note what the board offers before level 8 and after.

Listen for: declines drawing down a spoken budget that refills on
promotion; declined loads staying declined; the full freight board
unlocking at level 8; route choice refused until you are an
owner-operator or run your own authority.

Pass when: the freedom ladder matches your level and the game says why
each rung is locked.

### 9.3 The money is a carrier's money

Setup: a company-driver career and an owner-operator career,
side by side if you keep two profiles.

Do: fuel and repair on both. Deliver specialty cargo on time and watch
the streaks.

Listen for: the carrier covering a company driver's road fuel and
routine repairs; the owner-operator paying real operating costs from day
one; on-time streaks and specialty cargo compounding experience;
reputation paying a continuous dispatch trust bonus you can hear in the
offers.

Pass when: the same purchase sounds different in the two careers, and
personal money still buys endorsement courses and motel rest in both.

### 9.4 Trailers and the long arc

Setup: a career at or past the level-18 leased-on gate (an established
profile is fine).

Do: walk the leased-on trailer program, then dispatch rows with trailer
previews.

Listen for: dispatch rows previewing trailer fit and estimated take-home
before you accept; owned trailers arriving with own authority at 25;
guidance voices changing with the level band; haul-length caps growing
through the arc instead of maxing early.

Pass when: the trailer economics are spoken before commitment and the
arc still has somewhere to go at level 25.

### 9.5 Achievement spot checks

Do: earn any three obvious ones — a first delivery, a state arrival, a
close call — and check the badge wall.

Pass when: each lands once, speaks its line, and nothing awards twice.

## Chapter 10. Radio

### 10.1 The dial follows the map

Setup: a long leg crossing regions; radio on (M).

Do: tune with the brackets, ask for status with Y, open the Radio screen
from Tab. Drive a regional station to the edge of its market.

Listen for: only receivable stations in the bracket rotation; the
regional station fading to static at the fringe and the Roadhouse taking
back over when the signal drops; hosts on the Roadhouse and Night Line
at their hours.

Pass when: what you can tune matches where you are, and the handoff at
signal loss is automatic and spoken.

### 10.2 Streamer-safe by default

Setup: a fresh install or reset settings.

Do: check what the radio plays before touching any opt-in; then find
the explicit opt-in for real public streams.

Pass when: nothing externally licensed plays until you opted in, in so
many words.

## Chapter 11. The world speaks

### 11.1 New country

Setup: dispatch into the new territory — the Great Basin on I-80, the
Hi-Line on US-2, I-70 over the Rockies, I-75 through the Kentucky
mountains.

Do: drive a leg that did not exist on the nightly line.

Listen for: real roads with real checkpoints, grades that match the
terrain out the window, truck stops (or a spoken rural-diesel fallback)
on every leg, and fuel planning that actually matters on the empty
stretches.

Pass when: the new corridor plays as fully as an old one — no silent
miles, no missing fuel plan.

### 11.2 The chatter switches work

Setup: Settings, the Roadside chatter group.

Do: drive a landmark-rich leg (national forests, named rivers, passes)
with chatter on; flip the master switch off; then re-enable just one
kind; then set verbosity to terse.

Listen for: ambient callouts for landmarks and parody billboards when
on; total silence from the whole group when the master switch is off;
only the chosen kind returning; terse verbosity muting it all
regardless.

Pass when: every switch does exactly what its label says, spoken
settings round-trip included.

### 11.3 Time is local

Setup: a leg crossing a zone boundary (Denver westbound works).

Do: check the clock before and after the crossing; take a load whose
deadline lies across a boundary.

Listen for: the zone change spoken at the line, C reporting the new
local time, and deadlines always read in the destination's local time.

Pass when: you can never be surprised by an hour you were not told
about.

### 11.4 The comma walks back through what you heard

Setup: any busy drive -- callouts, status keys, a warning or two.

Do: press comma once and you get the newest line, as always. Now press
it again quickly, and again: each press steps one line older, spoken as
"2 back:", "3 back:". Wait ten seconds and press once more. Then press
Space (a fresh status line) and comma again.

Listen for: the walk stepping through both voices' recent lines --
menu speech and driving events share one history -- the position
prefix on every older line, the pause snapping the key back to the
newest line, and any fresh announcement doing the same.

Pass when: a warning you missed two announcements ago is reachable in
three presses, and a comma pressed cold always answers "what did it
just say?".

## Chapter 12. Saves, restores, and the integrity gate

### 12.1 Old careers migrate honestly

Setup: a save from the nightly line (version-4 schema or later).

Do: load it in the alpha; check the truck status readout and the garage.

Listen for: the career loading with sensible defaults for everything
new, and your old wear settled onto every truck you own — no pristine
spare appearing from nowhere.

Pass when: nothing was lost, nothing was invented, and the profile
plays.

### 12.2 Cloud restores still restore

Setup: a cloud backup made normally.

Do: restore it.

Listen for: a clean, ordinary restore. The new integrity layer runs
behind the server's signature on every restore; an honest save should
never hear it. If a restore is ever refused, the spoken line names the
first problem in plain words — that sentence is the bug report.

Pass when: honest saves restore silently and any refusal you can
provoke says exactly why.

## Appendix A. Levers and keys

Weather forcing (`FREIGHT_FATE_FORCE_WEATHER`), the winter route picks,
and the physics key list live in the companion volume,
`docs/physics-playtest-checklists.md`. The keys this book leans on
beyond those: X commit to the exit (or signal a pull-over), L lane
readout, Left/Right lane change with assist off, R progress, Shift+R
next exit, U upcoming, A repeat last announcement, comma repeat the
last spoken line (press again quickly to walk back through the last
twenty), M radio with
brackets to tune and Y for status, T stop at an announced service, F
fuel, Enter accept a city-service arrival, F1 the full key help.

### Scenario levers

Three more environment variables move a career into position for a
scenario without hours of setup driving. All three speak what they did
in plain words, move no miles and no money, and only touch a career
that is parked with no load in progress.

**A lever session is a sandbox by default.** The whole run — the
relocation, any loads you take, money won or lost, damage, abandoned
jobs — plays out in memory and is never saved. You hear "Playtest
sandbox: nothing this session is saved" as the career loads, and your
real save resumes untouched the next time you play normally. For the
rare run whose changes should stick (moving your career home, say), set
`FREIGHT_FATE_FORCE_PERSIST = "1"` alongside the levers and the session
saves like normal play.

Set the levers before launching the game, load your career from the
main menu, and unset them when the scenario is done. In PowerShell:

    $env:FREIGHT_FATE_FORCE_CITY = "denver_co_us"
    $env:FREIGHT_FATE_FORCE_CLOCK = "21"
    $env:FREIGHT_FATE_FORCE_DEST = "silverthorne_co_us"

- `FREIGHT_FATE_FORCE_CITY` — relocate the parked career to a city
  (slug or plain name) as the career loads. You hear "Playtest lever:
  relocated to..." after the terminal announcement.
- `FREIGHT_FATE_FORCE_CLOCK` — roll the career clock forward to the
  next time the local wall clock reads that hour (0 to 23). The wait is
  logged as off duty; ten or more hours counts as a full break and
  resets hours of service, exactly like sleeping at the terminal.
- `FREIGHT_FATE_FORCE_DEST` — the next freshly built dispatch board is
  guaranteed to offer a load to that city when a supported corridor
  reaches it, and assigned dispatch hands you that load first. If the
  board was cached before you set the lever, sleep once or deliver a
  load to refresh it.

Unset with `Remove-Item Env:FREIGHT_FATE_FORCE_CITY` (and the same for
the other two) before normal play. When shared profiles arrive, the
event ledger must record forced relocations and clock moves so a
shared save carries an honest history (see docs/profile-invariants.md).

## Appendix B. Reporting a run

One line of setup, what you heard, what you expected. Say which chapter
and checklist, your driving mode, and whether weather was forced. If a
spoken line was wrong, quote it as closely as you can — the exact
wording is often the whole bug.
