# Physics playtest checklists (1.9)

Companion to `tools/physics_bench.py`. The bench proves the numbers; these
checklists prove what you actually hear at the wheel. Each scenario says how
to set it up, what to do, what to listen for, and when to call it a pass.
Work them in order or cherry-pick -- every one stands alone.

Written for a screen-reader playtest: everything to verify is spoken, never
visual.

## Forcing the weather

The whole winter suite depends on one dev lever: the
`FREIGHT_FATE_FORCE_WEATHER` environment variable locks the sky for the
entire session. It overrides the seasonal model and the live weather feed,
so glare ice in July works fine.

In PowerShell, from the repo:

    $env:FREIGHT_FATE_FORCE_WEATHER = "ice"
    uv run freight-fate

Accepted values: `clear`, `cloudy`, `rain`, `heavy_rain`, `thunderstorm`,
`snow`, `ice`, `fog`, `wind`. Anything else (or empty) means normal weather.
To go back to normal, close that terminal or run
`Remove-Item Env:FREIGHT_FATE_FORCE_WEATHER` before relaunching. Nothing
else about the game is altered -- money, wear, HOS, and citations all run
stock.

Press V any time while driving to confirm what the sky is doing.

## Good routes for these tests

Mountain terrain gives the game's steepest grades today -- rolling synthetic
climbs and descents up to about 3.5 percent on roughly an 8-mile rhythm.
Short mountain picks:

- Sacramento to Reno on I-80, 132 miles (the shortest mountain leg).
- Flagstaff to Phoenix on I-17, 148 miles.
- Knoxville to Nashville on I-40, 180 miles.

For the straight-line stop tests, terrain does not matter; any flat
heartland leg works.

Equipment purchases need an owner-operator (or leased owner-operator)
profile -- company drivers get carrier rubber and carrier-billed chains,
which is its own checklist below.

## Keys you will lean on

Space speed and gear. V weather and safe speed. S posted limit. J engine
brake. K adaptive cruise, plus and minus to trim it. Down arrow service
brakes, B emergency stop. Tab status menu (brake heat, wear past 50
percent, weather). C clock and hours. Escape pause menu -- where chain-up
lives. F1 repeats the full key help.

---

## 1. The garage sells the ladder (owner-operator)

Set up: owner-operator profile, at a city with a garage, a few thousand
dollars aboard.

Do:

1. Open the garage and arrow through the service list.
2. Find "Switch to winter tires: fresh set for ... dollars" and buy it.
3. Find "Buy snow chains" at 750 dollars and buy a set.
4. Leave the garage and open the city rig readout.

Listen for: the tire line names the compound ("winter compound") and the
chains line says a fresh set is aboard. Buying again should refuse -- "A
fresh set of chains is already in the side box."

Pass when: both purchases speak their price, the money moves, the rig
readout names winter rubber and fresh chains, and double-buying is refused.

## 2. Company drivers get carrier rubber

Set up: company-driver profile, city garage.

Do: try the tire swap, then the chains item.

Listen for: the swap is refused in plain language -- the carrier decides
what rubber the assigned tractor runs -- and no money moves. Chains are
provided carrier-billed: you get the set, your wallet does not shrink.

Pass when: no charge either way, and the refusal explains itself.

## 3. The ice stop ladder

The bench anchors: from 40 miles per hour on glare ice, about 880 feet on
all-season, about 613 on winter compound. Chained and held to chain speed
(30), about 215 feet. You are listening for that ordering, not measuring
tape.

Set up: force `ice`. Flat leg. Run it three times across sessions: once on
all-season, once after the winter swap, once chained (checklist 4 covers
installing).

Do:

1. Get to 40 (chained: 30) on a quiet stretch.
2. Brake hard with the down arrow and hold it to a full stop.
3. Press Space when stopped and note roughly how long the slide felt.

Listen for: on all-season the slide is long and the traction warnings come
easily. Winter compound stops noticeably sooner. Chained from 30 the truck
just stops -- it should feel almost boring.

Pass when: each rung of the ladder stops clearly shorter than the one
below it.

## 4. Chaining up, day and night

Set up: own chains. Any route. Do it once in daylight and once at night --
press C to check the clock; late evening or pre-dawn counts.

Do:

1. Stop completely (under 3 miles per hour) and press Escape.
2. Day: the item reads "Install snow chains: about 25 minutes." Night:
   "Install snow chains in the dark: about 40 minutes."
3. Install, then press C and compare the clock and your hours of service.
4. Later, stop again and take "Remove snow chains: about 10 minutes."

Listen for: the completion line -- chains hung, keep it near 30 miles per
hour -- and the night version costing 40 minutes with a wearier read.
Installing on bare pavement warns you the road is bare. The time lands on
your duty clock, and fatigue rises more at night (10 points against 6).

Pass when: the label, the minutes, the clock, and the fatigue all move
together, and night is plainly the worse deal.

## 5. The chained jake holds the icy grade

The bench anchor: on an icy 4 percent descent, the unchained jake slips for
15 minutes; chained, it holds with about 2 minutes of low-gear protest.
In-game grades top out near 3.5 percent, so expect the same lesson, gentler.

Set up: force `ice`. Mountain leg (Sacramento to Reno is ideal). Chains
aboard. Run the descent once unchained, once chained.

Do:

1. On a descent, jake on with J, target about 20 to 25 miles per hour, stay
   off the service brakes as much as you dare.
2. Unchained: listen for the jake-slip warning as the drives break loose
   and the speed creeping despite the jake.
3. Stop, chain up, and ride the next descent the same way.

Listen for: unchained, the slip warning and rising speed; chained, the jake
simply holds and the slip warning stays rare or absent.

Pass when: the chained descent is controlled where the unchained one was
losing ground.

## 6. Chains grind apart on bare pavement

Set up: normal or forced `clear` weather. Chains aboard. A flat leg and a
tolerance for repair bills -- this one deliberately destroys a 750 dollar
set and adds 4 percent damage.

Do:

1. Stop and install chains. Accept the bare-road warning.
2. Accelerate past about 32 miles per hour.
3. Hold 55 and keep rolling.

Listen for: first the hammering cue as you pass chain speed -- steel
slapping the fenders. Then, around two miles in, the snap: a chain lets go,
hammers the fender, and the game tells you the set is gone. The Tab status
picks up the new damage. At the next garage the item reads "Replace snapped
snow chains."

Pass when: hammering cue, then snap, damage, and the garage offering a
replacement -- in that order.

## 7. Hydroplaning still respects the tread (and the chains)

Set up: force `heavy_rain`. Best on a profile whose tires are well worn --
check the city rig readout; past 60 or 70 percent worn is the danger zone.
Fresh rubber basically never planes at legal speed, which is itself the
realism.

Do:

1. On worn tires, work up past 60 and listen for the hydroplane onset
   warning; ease off and feel it hook back up.
2. If you have chains aboard, chain up (yes, in rain) and try again: steel
   is the contact patch, so hydroplaning stops being a thing -- but the
   bare-pavement grind of checklist 6 is running the whole time.

Listen for: the onset warning keyed to speed on worn tires, and its
complete absence while chained.

Pass when: worn tires warn and recover; chains never warn but chew
themselves up doing it.

## 8. Chain-law signs and citations -- bench only, for now

Not reachable in-game yet, on purpose honest: chain-law areas require a
real sustained 5 percent grade and the shipped map's synthetic terrain
grades top out near 3.5 percent. No route today places an area, so the
flashing sign, the compliance warning, and the 500 dollar checkpoint
citation cannot be heard at the wheel until a mountain corridor carries
curated grade data (Donner and Eisenhower are the natural firsts -- see
ROADMAP).

Verify it at the bench instead:

    uv run python tools/physics_bench.py --list
    uv run python tools/physics_bench.py stop-ice stop-ice-winter stop-ice-chains
    uv run python tools/physics_bench.py grade-jake-ice grade-jake-ice-chains chains-bare

The law logic itself is covered by `tests/test_chain_law.py` (placement,
levels, sign escalation, seeded citation).

## 9. Grade and brake-heat regression sweep

Ten minutes to confirm the earlier tasks still sound right after the chain
work.

Do, on a mountain leg in clear weather:

1. Descend once dragging the service brakes; watch for the brakes-hot
   status on Tab and the fade making the pedal feel longer.
2. Descend once on jake and snubs; Tab should stay at brakes warm or cool.
3. On a climb, listen for the speed bleeding on the grade and the
   downshift.

Pass when: dragging heats, jake-and-snub stays cool, and nothing about the
chain work changed the dry-weather feel.

---

## After the run

What matters most: anything that sounded wrong, un-truck-like, or spoken
awkwardly by the screen reader -- exact wording notes are gold. Second:
any ordering that felt off (winter rubber not obviously better on snow,
chains not obviously king on ice). The bench holds the numbers steady;
your ears hold the game honest.
