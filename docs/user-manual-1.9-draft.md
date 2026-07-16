# Player Manual 1.9 Draft — for the owner's voice pass

DRAFT ONLY. Nothing in this file ships. Each block below names the manual
section it belongs to; rewrite in your own voice and move it into
docs/user-manual.md, then delete it here. Changed habits are the priority —
each one gets its own line, up front, because surprising a returning player
is worse than surprising a new one.

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

| G | Report the grade under the wheels: the slope, how far it runs, and whether the truck is holding it -- including whether the jake has the descent or is about to lose it. |
| Comma | Say the last spoken line again, whatever it was. Works everywhere, including menus. |
| M | Toggle the in-cab radio. |
| Left and Right brackets | Tune the radio down and up the dial. |
| Y | Report the radio station, volume, and streamer-safe status. |

Update the A row so the two repeat keys read as a pair:

| A | Repeat the last route announcement -- the last thing with consequences -- even if other speech came after it. Comma repeats the very last line of any kind. |

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
Speeding strikes are separate and silent -- the warning exists so a strike
never surprises you.

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

M toggles the radio, the brackets tune it, Y speaks what is playing, and the
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
