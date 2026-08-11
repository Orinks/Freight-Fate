# Player Manual 1.9 Draft — for the owner's voice pass

DRAFT ONLY. Nothing in this file ships. Each block below names the manual
section it belongs to; rewrite in your own voice and move it into
docs/user-manual.md, then delete it here. Changed habits are the priority —
each one gets its own line, up front, because surprising a returning player
is worse than surprising a new one.

STALENESS PASS 2026-07-27 (Phil): everything below the line "== SECOND
SWEEP ==" is new in this pass, drafted from the shipped changelog for
your voice. Two rows ABOVE that line were corrected in place (Comma and
A — the message review changed what they do). The curve-navigation
section at the very bottom describes a build that folds after your ear
pass; verify it in-game before moving it to the manual.

## New section, near the top: "New In 1.9 — Changed Habits First"

If you played 1.8, these are the habits that changed. Read these before
anything else.

- **Reverse changed.** Holding the brake through a stop no longer selects
  reverse, and a quick tap at a stop no longer selects reverse. To back up:
  stop fully, release the Down arrow, then press it again and HOLD it for a
  moment. You will hear "Reverse selected." The same press-and-hold on the
  Up arrow brings forward gear back. A quick tap just brakes, always.
- **Braking turns cruise control off.** Any press of the service brake or
  emergency brake drops cruise immediately and says so. Cruise no longer
  quietly pulls the truck back up to speed after you slowed on purpose.
- **Traffic lights have a yellow now, and every change is spoken.** Ramp-end
  lights cycle green, yellow, red, and each change announces itself.
  Entering on green or yellow is legal. Yellow means stop if you are not
  already at the light.
- **The dash warns you about your own speed.** A few miles per hour over the
  posted limit sounds a soft chime and says the limit; the chime repeats,
  faster the further over you go. It is a Gameplay setting with three
  positions: on, urgent only, and off.
- **A dropped speed limit gives you braking time.** When the posted limit
  steps down, enforcement waits the seconds a loaded truck honestly needs to
  comply -- as long as you are off the throttle and slowing.
- **Your company tractor is assigned by dispatch now.** New hires get the
  trainer rig; better equipment arrives with seniority at levels 4, 9, 13,
  and 17. Owner-operators still buy their own.
- **Each truck keeps its own condition.** Wear, damage, and fuel stay with
  the truck they happened to. Swapping tractors no longer carries your wear
  or your empty tank to the next rig.

## Driving Controls section: table rows to add or update

Update the Down arrow row:

| Down arrow, hold | Brake. To select reverse: stop fully, release, then press and hold again for a moment. A quick tap just brakes. |

Add these rows:

| G | Report the grade under the wheels: the slope, how far it runs, and whether the truck is holding it -- including whether the jake has the descent or is about to lose it. G also names the next steep grade ahead: how far off and how long it runs. |
| Comma and Period | Walk back and forward through recent spoken messages -- a line lost under an overlapping announcement is no longer gone. Ctrl with either jumps to the oldest or newest; the brackets switch between all messages, general ones, and driving events; Ctrl+C copies the message you are on. |
| M | Toggle the in-cab radio. |
| Page Down and Page Up | Tune the radio to the next and previous station. Ctrl with either leaps a whole category. The semicolon and apostrophe keys still work. |
| Y | Report the radio station, volume, and streamer-safe status. |
| R | Report how far along the route you are. |
| Alt+A | Report time at the wheel so far this shift, and time on duty. |
| Alt+S | Report when your 30 minute break is due, or that a break will not help. |
| Alt+D | Report what ends this shift -- driving time left and duty window both -- and where you can legally stop before it. |

Update the C row: it now reports the clock, the deadline, the estimated
arrival, and the one hours-of-service limit that comes first, rather than the
whole hours report. The first few presses also name the three Alt keys above.

Update the A row so the repeat keys read as a family:

| A | Repeat the last route announcement -- the last thing with consequences -- even if other speech came after it. Comma and Period walk the whole message history. |

## Truck Behavior section: additions

The truck wears with how you drive it. Tires, brakes, and the engine each
keep their own meter. Miles and heavy loads eat tire tread; riding the
service brakes wears the shoes, and hot brakes wear them faster; hours under
load wear the engine, and over-revving or lugging punishes it hardest. Wear
talks back: bald tires grip less, worn brakes pull weaker and fade sooner, a
tired engine loses power and burns more fuel. The truck status readouts speak
all three meters, and the delivery summary tells you what each run added.

The engine brake is a real three-stage jake. It retards through the gears,
so it pulls hardest in a low gear with the engine turning fast and does very
little in top gear. Set your gear and speed before the hill starts. The
automatic drops a gear to put the jake to work and shifts up to protect the
engine if the hill spins it too fast -- which leaves you a weaker jake in a
taller gear, exactly the spiral a mismanaged descent earns. Heavy loads can
outrun the jake entirely: snub the brakes early or crawl.

A loaded rig eases into its power and its grip. An empty deadhead launches
briskly; a grossed-out trailer creeps away from the line. On a steep climb
the truck uses everything it has, and if the hill has the load, no gear will
hide it -- press G to hear the honest verdict.

## Road Events, Weather, And Rest Stops section: additions

Ramp ends are real intersections. Most ramps end at a traffic light or a
stop sign, called out on the way down. Lights cycle green, yellow, red, and
speak every change. Enter on green or yellow; red means brake to a full stop
at the bar and hold the brakes until it says green. Rolling a red draws
horns; blowing one at speed means cross traffic finds your trailer.

Winter has teeth now. Snow and ice cut grip hard, and freezing rain is the
one worth parking for -- rain glazing the road just below freezing is far
slicker than snow. Winter-compound tires are a real choice at the garage,
and snow chains ride in the side box until a flashing sign before a snowy
pass calls a chain law: Level 1 wants winter tires or chains, Level 2 wants
chains on the drives. Chaining up happens from the pause menu while stopped.
It costs real minutes and real fatigue, more in the dark -- and chained on
glare ice, the truck actually holds.

The overspeed warning is your dash, not the police. A few over the limit
chimes softly and says the limit; the chime repeats, faster the further
over. It quiets while you are braking down and resets when you settle under.
It is a courtesy and it costs nothing: speeding is charged by the trooper who
saw it, on the shoulder, or it is not charged at all.

## The In-Cab Radio: new section

The radio carries two kinds of stations. The Freight Fate stations -- the
Roadhouse, the Night Line, and the regional stations -- play original music
composed for the game, with hosts, and they are always safe to stream on
Twitch or YouTube. Real public radio stations join them when you allow real
streams in Settings: live jazz from Portland, news in the cities, community
radio in Tucson, the Voice of the Navajo Nation across the Four Corners.
Real stations fade in and out by distance like FM, and the wide rural
networks carry the empty country. Real streams are not streamer-safe --
station-side music licensing does not cover a re-broadcast -- which is why
they sit behind both the real-streams setting and the streamer-safe switch.

M toggles the radio. Page Down tunes to the next station and Page Up to
the previous; the semicolon and apostrophe keys still work. Y speaks what is
playing, and the
Tab status menu has a Radio screen listing every receivable station with
signal strength, distance, and source.

## Settings section: new entries

- Overspeed warning: on, urgent only, or off. Urgent only stays quiet until
  you are far past the limit -- for drivers who speed on purpose but still
  want the runaway alarm.
- Radio real public streams: allow live stations on the dial. Streamer-safe
  mode must also be off before they play.
- Automatic direction changes: both styles now use the same gesture -- a
  fresh press held at a standstill. The setting remains for familiarity.

## Truck stops section: additions

Truck stops sell more than fuel. A hot meal or an energy drink eases fatigue
and slows how fast the next hours tire you; at a Pilot or Flying J, fueling
makes the shower free. On the truck side, a lube bay slows engine wear for
the rest of the trip, a tire rotation does the same for tread, and the
big-name stops fix what they are really known for -- Love's does tires fast,
TA and Petro run full service shops. Big Buck's, famously, fixes nothing.
One food buff and one of each rig service at a time, and none of it ever
adds legal driving hours.

== SECOND SWEEP == (2026-07-27 -- everything below is new; draft for your voice)

## "New In 1.9 -- Changed Habits First": MORE rows to add

- **Comma changed.** It no longer just repeats the last line -- Comma and
  Period now walk backward and forward through everything recently spoken,
  and the bracket keys pick which kind of message you are walking. A is
  still the "what did the route just tell me" key.
- **Pulling the parking brake at speed is now the violent move it really
  is.** Above a crawl, the valve slams the spring brakes on: a screech, a
  hard stop, and flat spots ground into your tires that scale with how fast
  you were going. Set it when stopped, like a real hand.
- **Turn signals are tones now, not clicks.** [PENDING CURVE-NAV FOLD]
  Every signal -- lane change, exit, pull-over -- plays a clear indicator
  tone panned to the side you are signaling, the sound a modern cab makes.
- **Cruise has a resume button.** Braking still cancels cruise; resume
  brings back the last set speed like a car's stalk.

## Dispatch And Jobs section: additions

Below level 9 you are a slip-seat driver: no tractor of your own. Each
dispatch, the yard hands you the best fit from a small set of spares --
a day cab for a short turn, a sleeper when the run is too long to finish
in a shift, a heavy driveline when the load demands it -- and dispatch
says which truck you drew and why. Every spare keeps its own fuel, wear,
and damage between draws, so a fresh truck after a turn is the yard
handing you a different unit, not your wear disappearing. A dedicated
seat comes with seniority at level 9. The roster behind this grew from
twelve tractors to thirty-five.

New hires can review the rest of the day's board before accepting the
assigned load: the option reads out what else the market posted today.
Declining your assignment draws the first of those instead; choosing
freely unlocks at level 8.

Deadlines are set by a dispatcher who did the math: driving time from
real route speeds plus the breaks and, on multi-day runs, the ten-hour
resets the law will force. A tight-sounding deadline covers legal rest;
the job details say when a deadline banks on it.

## Pickup, Loading, And Route Planning section: additions (trailers)

Trailers are real objects now, with their own paperwork and their own
problems.

At a busy shipper -- cross-docks, parcel hubs, big distribution centers --
pickup can be drop and hook: back under a loaded trailer standing in the
yard, hook, and go in about twenty-five minutes instead of an hour backed
into a live dock. Before you pull out, a walkaround option lets you check
the lamps, the brake adjustment, and the tires yourself. If something is
wrong you hear exactly what, and you can refuse the box -- the yard takes
about half an hour to bring a sound one, and the defect stays their
problem instead of riding to the first scale house with you. Roll out
without looking and it is yours.

The delivery end mirrors it: a receiver with a drop yard takes the whole
trailer -- back it in, hook a clean empty, gone in twenty minutes instead
of forty-five at a dock. It is also how you shed a trailer with a defect
you have been dragging since the shipper.

Live docks that hold you past the free time now pay detention -- the
clock and the rate are in the job details. Owner-operators hauling their
own trailer give up the fast drop-and-hook turn: your box has to come
back with you, and the trade-off is priced into the freight.

## Driving Controls / Truck Behavior: additions (the drivetrain grew up)

The automatic shifts like a real automated box now: quick, light shifts
in the low gears, deliberate ones up top, and it manages its own jake --
stages the engine brake against the hill, releases it when the grade is
done. The engine brake has a real cylinder selector: two, four, or six
cylinders, stepped with the same key, and the full stage can break the
drive tires loose on ice, exactly like the warning stickers say. An
empty or bobtail truck no longer machine-guns through the gears; load
changes when the truck shifts and how fast it dares.

Cold starts build air out loud: the compressor charges the tanks before
the brakes will release, and low air has its own buzzer. Parked with the
brake set you can rev freely, and the cruise button doubles as a parked
high idle -- rev it like a boss, hands off.

## Mountain Driving section: additions

The road warns you about the hills that matter. Any climb or descent of
three percent or more running at least three quarters of a mile is
called out before it starts, with the steepness, the length, and --
going down -- what to do about it before it begins. Short dips stay
quiet so the real hills stand out. Terse speech skips these; G answers
on demand either way, and G also names the next grade ahead.

Cruise reads the same road: it banks a little speed before a climb,
gives up the last few miles per hour at a crest instead of fighting,
and stops adding speed it would only brake away before a descent. It
says what it is doing the first time on each hill -- and when a climb
has genuinely beaten it, it says that too, so the quiet sinking of the
old cruise is gone.

## Road Events section: additions

The road tells you how many lanes you have. Road status says the lanes
on your side -- "divided, three lanes your side" -- and as the road
widens or narrows mid-leg you hear it happen. Where the map has no lane
data it stays quiet rather than guess.

Speed-limit changes name the town that causes them, and the limits on
the streets that approach a facility are the real posted ones now, not
a blanket guess -- a long industrial approach might honestly be 45,
stepping down as you close in on the gate.

An armed exit counts itself down -- two miles, one mile, half a mile --
and the stop bar at a ramp's end has a parking-sensor tick that speeds
up as you close on it, so you stop AT the bar instead of a quarter mile
short and creeping blind.

## Hours Of Service section: additions (enforcement grew teeth and honesty)

The clock answers one question at a time now. Alt A gives time at the wheel so
far this shift, Alt S when the 30 minute break comes due, and Alt D what ends
the shift -- driving time and duty window both, the one that runs out first
named first, then the nearest place you can legally stop. Each answer opens
with its own words, so a slipped key is obvious by ear, and with enforcement
off each key says so instead of going quiet. C keeps the clock, the deadline,
and whichever limit comes first, and for the first few presses it points at
the new keys. On a controller, D-pad right still reads the whole hours report
in one press.

A log check that finds you over your hours is no longer a silent time
jump: the officer orders you off the road, the stop explains exactly
which clock you broke and by how much, and the ten-hour out-of-service
hold plays out with the new shift time and what it means for your
deadline spoken plainly. And the sleeper berth tells the truth: a nap
that does NOT reset your fourteen-hour window says so when you wake,
with the time the window still closes -- the old wording could read
like a fresh day when it was not.

## The In-Cab Radio section: replace the station counts / coverage claims

The dial is much bigger than the first draft said: hundreds of real
public stations across all lower forty-eight states, reading services
for blind listeners as their own category, international public
broadcasters that are always in range, and translator fills that light
up the loneliest corridors -- interior Nevada on I-80 and US-50, far
West Texas. Real FM behaves like FM: stations fade at the fringe with
hiss and picket-fencing before they drop. The dial jumps by category
with Ctrl, and your own music can join it -- point the game at a folder
playlist and it becomes a personal station.

## Settings section: additions

- Lane keeping is the steering setting -- it was called Lane drift, and
  its old values read backwards. Now they explain themselves: full means
  the truck holds the lane and takes your exits, partial is gentle drift
  with steering help, off means you hold the lane and take your own
  exits. Your old setting carried over to the value that behaves
  identically, and the row says so the first few times you visit it.
  [PENDING CURVE-NAV FOLD for the exact spoken wording.]
- Overspeed warning, real radio streams, and automatic direction changes
  are as the first draft described.

## Audio, Speech, And Accessibility section: additions

The truck's voice was rebuilt this cycle: the engine never repeats a
loop your ear can learn, brakes and gear changes are the real
mechanisms, tire sounds rise and fall with speed, and road-seam thumps
give the road texture through sound and controller vibration.

## Driving section: NEW -- "How To Take Curves Like A Boss" [PENDING CURVE-NAV FOLD]

(The owner's title, earned the honest way -- every rule below is a mistake
somebody made on Camp Verde to Payson first.)

**Rule one: carry your speed to the fight.** Cruise holds your pace between
bends; the curve callout is braking DISTANCE, not an order to stop. When
you hear "sharp right, half a mile, advise 30," you have real seconds --
brake firmly down TOWARD the advisory and arrive within a few of it. Slam
to a crawl at the callout and the bend becomes nothing: no push, no
steering, no fun, and time lost. The exit verdict tells on you either way.

**Rule two: know the vocabulary.** A bright bink on one side is a curve
call or a curve beginning on that side. Hard double-thuds under the whole
truck are the dead-man's bars: a true hairpin is a quarter mile out --
brake hard NOW, because 25 means 25 with fifteen tons pushing you. A
thump-roll from one side is your tires crossing a lane line's markers.
The stutter-buzz-gravel ladder on one side is the road edge, in order of
how much trouble you are in.

**Rule three: steer toward the sound, gently.** In the bend the road
sound leans toward where the wheel should go -- hold the arrow that way
and keep the sound centered. Small, held corrections. Sawing at it
bounces you across the lane line -- you will hear the marker thump each
time you cross, and that rhythm is the sound of overcorrecting. Ease off.

**Rule four: use the co-driver.** U says what bends are coming and
exactly how far. D says the safe speed for the road you are on right
now. G reads the grade. I toggles the lane locator -- a soft tock from
wherever you sit in the lane -- when you want continuous position. K
resumes cruise on the way out.

**Rule five: listen for the verdict.** "Held your line" means you did it
right. "You caught the edge" means the strip has notes. "Through the
bend, hot" means you gambled and won -- this time. String together clean
verdicts on a mountain road and you have earned the title.

## Main Menu And Career Flow section: additions

- **Learn game sounds** plays any cue the road uses, with what it means and
  what to do about it. It is on the main menu and on the pause menu while you
  drive. Arrow to a sound, press Enter to hear it, and press F1 for what it
  is telling you.

## Driving section: NEW -- steering through curves (the sound design) [PENDING CURVE-NAV FOLD]

With lane keeping on partial or off, the road sound becomes your steering guide. It
leans toward where the wheel should go: into a bend as the bend
arrives, through it, and back toward lane center when you drift --
follow the sound home. Centered on a straight, nothing new plays.
Drift to the road edge and the boundary answers with real textures
from the side it happens on: a ragged stutter as your tires clip the
rumble strip, a steady buzz fully on it, loose gravel once you are off
the pavement. On an undivided road the left line is different: past
the centerline there is no gravel, only the oncoming lane, and the
warning says exactly that.
