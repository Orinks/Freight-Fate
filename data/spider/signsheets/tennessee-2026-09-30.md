# Tennessee attractions, both directions -- 2026-09-30

Owner-approved 2026-09-30, with three edits from the draft: the Lost Sea line
ends "It still goes by the Lost Sea."; Ruby Falls leaves out the Gadsden and
Huntsville legs, whose Exit 174 mileposts were estimated; and the Museum of
Appalachia has no southbound sign, because the leg's own "Norris Museum
ahead" callout stands just before Exit 122 and now faces southbound only.

Seven real Tennessee roadside attractions, each signed in every direction of
travel where a leg passes it. Every `leg:` is written the way the driver
reads the sign and `at_mi` counts from that end; `tools/bake_billboards.py`
mirrors the milepost onto a leg stored the other way round and records which
way the billboard faces.

Mileposts come from the legs' interchange lists (the attraction's exit and
the one before it) and, where a leg has no interchange list for that road,
from its landmarks and checkpoints. "Next exit" signs stand between the
attraction's exit and the exit before it; "ahead" signs about eight to
fifteen miles out. Each sits at least 2.2 miles from every other callout
heard in the same direction (rivers, museums, villages within a mile and a
half of the road, forward-facing billboards), so the landmark spacing does
not drop it.

## Casey Jones Village, Jackson (I-40 Exit 80)

The famous engineer's home and railroad museum, the Old Country Store, and
shops, at 56 Casey Jones Lane on the US 45 Bypass at I-40 Exit 80A
(caseyjones.com). Exit 80 is not in either leg's interchange list; its
milepost is taken as one mile past Exit 79 (80.9 on the Memphis to
Nashville leg, 79.6 on Memphis to Jackson). Exits 79 and 80 are a mile
apart, too close for a "next exit" sign, so these read "ahead".

### Casey Jones Village (eastbound)
- treatment: billboard
- leg: memphis_tn_us -> nashville_tn_us
- at_mi: 70.6
- spoken: Billboard: Casey Jones Village, ahead in Jackson. The famous train engineer's house and a railroad museum. Trains never have to back into a dock.

### Casey Jones Village (eastbound)
- treatment: billboard
- leg: memphis_tn_us -> jackson_tn_us
- at_mi: 69.3
- spoken: Billboard: Casey Jones Village, ahead in Jackson. The famous train engineer's house and a railroad museum. Trains never have to back into a dock.

### Casey Jones Village (westbound)
- treatment: billboard
- leg: nashville_tn_us -> memphis_tn_us
- at_mi: 120.8
- spoken: Billboard: Casey Jones Village, ahead in Jackson. The famous train engineer's house and a railroad museum. Trains never have to back into a dock.

## The Tina Turner Museum, Brownsville (I-40 Exit 56)

The Tina Turner Museum at Flagg Grove School, on the grounds of the West
Tennessee Delta Heritage Center, 121 Sunny Hill Cove, at I-40 Exit 56. Free
admission. The one-room school she attended in Nutbush was moved to
Brownsville by tractor-trailer in 2012 and opened as the museum in 2014
(haywoodtn.gov; Fox News).

### Tina Turner Museum (eastbound)
- treatment: billboard
- leg: memphis_tn_us -> nashville_tn_us
- at_mi: 55.0
- spoken: Billboard: The Tina Turner Museum, next exit. Her one-room schoolhouse came here from Nutbush on a tractor-trailer. Free admission. Best load that truck ever hauled.

### Tina Turner Museum (westbound)
- treatment: billboard
- leg: nashville_tn_us -> memphis_tn_us
- at_mi: 153.4
- spoken: Billboard: The Tina Turner Museum, next exit. Her one-room schoolhouse came here from Nutbush on a tractor-trailer. Free admission. Best load that truck ever hauled.

### Tina Turner Museum (eastbound)
- treatment: billboard
- leg: memphis_tn_us -> jackson_tn_us
- at_mi: 54.0
- spoken: Billboard: The Tina Turner Museum, next exit. Her one-room schoolhouse came here from Nutbush on a tractor-trailer. Free admission. Best load that truck ever hauled.

### Tina Turner Museum (westbound)
- treatment: billboard
- leg: jackson_tn_us -> memphis_tn_us
- at_mi: 26.1
- spoken: Billboard: The Tina Turner Museum, next exit. Her one-room schoolhouse came here from Nutbush on a tractor-trailer. Free admission. Best load that truck ever hauled.

## Loretta Lynn's Ranch, Hurricane Mills (I-40 Exit 143)

Her home, museum, guided tours and campground, 8000 Highway 13 South,
seven miles north of I-40 Exit 143 (lorettalynn.com; directions from
mxsports.com). The Lynns bought the house in 1966 and the property turned
out to include the whole town, which she said they did not know at the time
(lorettalynn.com, "About the Ranch"; Fox News, quoting her on the Travel
Channel).

### Loretta Lynn's Ranch (eastbound)
- treatment: billboard
- leg: memphis_tn_us -> nashville_tn_us
- at_mi: 142.6
- spoken: Billboard: Loretta Lynn's Ranch, next exit, seven miles north. She bought the house in nineteen sixty-six and found out the whole town came with it.

### Loretta Lynn's Ranch (westbound)
- treatment: billboard
- leg: nashville_tn_us -> memphis_tn_us
- at_mi: 65.8
- spoken: Billboard: Loretta Lynn's Ranch, next exit, seven miles north. She bought the house in nineteen sixty-six and found out the whole town came with it.

### Loretta Lynn's Ranch (eastbound)
- treatment: billboard
- leg: jackson_tn_us -> nashville_tn_us
- at_mi: 62.0
- spoken: Billboard: Loretta Lynn's Ranch, next exit, seven miles north. She bought the house in nineteen sixty-six and found out the whole town came with it.

### Loretta Lynn's Ranch (westbound)
- treatment: billboard
- leg: nashville_tn_us -> jackson_tn_us
- at_mi: 61.4
- spoken: Billboard: Loretta Lynn's Ranch, next exit, seven miles north. She bought the house in nineteen sixty-six and found out the whole town came with it.

## The Lost Sea, Sweetwater (I-75 Exit 60)

Craighead Caverns and America's largest underground lake, with a boat ride
on the tour, 140 Lost Sea Road, seven miles east of I-75 Exit 60 on
Tennessee 68 (thelostsea.com).

### The Lost Sea (northbound)
- treatment: billboard
- leg: chattanooga_tn_us -> knoxville_tn_us
- at_mi: 64.8
- spoken: Billboard: The Lost Sea, next exit, then seven miles. America's largest underground lake. A boy found it in nineteen oh-five. It still goes by the Lost Sea.

### The Lost Sea (southbound)
- treatment: billboard
- leg: knoxville_tn_us -> chattanooga_tn_us
- at_mi: 43.0
- spoken: Billboard: The Lost Sea, next exit, then seven miles. America's largest underground lake. A boy found it in nineteen oh-five. It still goes by the Lost Sea.

### The Lost Sea (southbound)
- treatment: billboard
- leg: knoxville_tn_us -> atlanta_ga_us
- at_mi: 43.4
- spoken: Billboard: The Lost Sea, next exit, then seven miles. America's largest underground lake. A boy found it in nineteen oh-five. It still goes by the Lost Sea.

### The Lost Sea (northbound)
- treatment: billboard
- leg: atlanta_ga_us -> knoxville_tn_us
- at_mi: 180.4
- spoken: Billboard: The Lost Sea, next exit, then seven miles. America's largest underground lake. A boy found it in nineteen oh-five. It still goes by the Lost Sea.

## Museum of Appalachia, Norris (I-75 Exit 122)

More than thirty historic log buildings on a working farm, 2819 Andersonville
Highway, one mile east of I-75 Exit 122 (museumofappalachia.org). Southbound,
the "next exit" slot between Exits 129 and 122 is taken by Rocky Top
(mile 74.0) and the leg's own "Norris Museum ahead" (mile 77.9), so that
direction gets an "ahead" sign before Exit 129.

### Museum of Appalachia (northbound)
- treatment: billboard
- leg: knoxville_tn_us -> london_ky_us
- at_mi: 17.0
- spoken: Billboard: The Museum of Appalachia, next exit. More than thirty log buildings, rescued from across the mountains. Every one of them older than your truck.

## Ruby Falls, Chattanooga (I-24 Exit 174 eastbound, Exit 178 westbound)

An underground waterfall more than a thousand feet inside Lookout Mountain,
found by Leo Lambert in 1928 and named for his wife, Ruby; open daily,
1720 South Scenic Highway (rubyfalls.com; Wikipedia, "Ruby Falls"). Its
own directions send eastbound drivers off at Exit 174 and westbound drivers
off at Exit 178. Eastbound signs read "next exit". Westbound, the exits in
Chattanooga are a mile or two apart, so those signs read "ahead". The
Gadsden and Huntsville legs join I-24 west of the city and list no I-24
exits; Exits 169 and 174 are placed on them by the same distances the
Murfreesboro leg measures from Exit 167 and from downtown.

### Ruby Falls (eastbound)
- treatment: billboard
- leg: murfreesboro_tn_us -> chattanooga_tn_us
- at_mi: 93.3
- spoken: Billboard: Ruby Falls, next exit. A waterfall more than a thousand feet inside Lookout Mountain, named for the finder's wife. Beat that on your anniversary.

### Ruby Falls (eastbound)
- treatment: billboard
- leg: nashville_tn_us -> atlanta_ga_us
- at_mi: 118.3
- spoken: Billboard: Ruby Falls, next exit. A waterfall more than a thousand feet inside Lookout Mountain, named for the finder's wife. Beat that on your anniversary.

### Ruby Falls (eastbound)
- treatment: billboard
- leg: nashville_tn_us -> chattanooga_tn_us
- at_mi: 126.1
- spoken: Billboard: Ruby Falls, next exit. A waterfall more than a thousand feet inside Lookout Mountain, named for the finder's wife. Beat that on your anniversary.

### Ruby Falls (westbound)
- treatment: billboard
- leg: atlanta_ga_us -> nashville_tn_us
- at_mi: 114.6
- spoken: Billboard: Ruby Falls, ahead in Chattanooga. A waterfall more than a thousand feet inside Lookout Mountain, named for the finder's wife. Beat that on your anniversary.

### Ruby Falls (westbound)
- treatment: billboard
- leg: knoxville_tn_us -> chattanooga_tn_us
- at_mi: 97.8
- spoken: Billboard: Ruby Falls, ahead in Chattanooga. A waterfall more than a thousand feet inside Lookout Mountain, named for the finder's wife. Beat that on your anniversary.

### Ruby Falls (westbound)
- treatment: billboard
- leg: dalton_ga_us -> chattanooga_tn_us
- at_mi: 20.5
- spoken: Billboard: Ruby Falls, ahead in Chattanooga. A waterfall more than a thousand feet inside Lookout Mountain, named for the finder's wife. Beat that on your anniversary.

### Ruby Falls (westbound)
- treatment: billboard
- leg: athens_ga_us -> chattanooga_tn_us
- at_mi: 164.5
- spoken: Billboard: Ruby Falls, ahead in Chattanooga. A waterfall more than a thousand feet inside Lookout Mountain, named for the finder's wife. Beat that on your anniversary.

## Bristol Motor Speedway (US 11E, Volunteer Parkway)

The NASCAR short track at 151 Speedway Boulevard, beside US 11E between
Bluff City and Bristol: a 0.533-mile concrete oval banked 24 to 28 degrees
in the turns, with Cup races in spring and September (Wikipedia, "Bristol
Motor Speedway"; bristoltn.gov for tours). The Johnson City to Wytheville
leg takes US 11E north, turns onto Tennessee 394 a mile south of the track
and runs along its south side, then US 421 into downtown Bristol
(checkpoint, mile 27.7) before joining I-81. Its route point at mile 24.5
sits on US 421, matching an OSRM route over the same roads, which puts the
track at about mile 17.5. The northbound sign is about nine and a half miles
out; the southbound one is on I-81 just before Exit 3, about thirteen miles
out.

### Bristol Motor Speedway (northbound)
- treatment: billboard
- leg: johnson_city_tn_us -> wytheville_va_us
- at_mi: 8.0
- spoken: Billboard: Bristol Motor Speedway, ahead. A half-mile of steep concrete, five hundred laps, and every single turn is a left. Your route is kinder.

### Bristol Motor Speedway (southbound)
- treatment: billboard
- leg: wytheville_va_us -> johnson_city_tn_us
- at_mi: 67.0
- spoken: Billboard: Bristol Motor Speedway, ahead. A half-mile of steep concrete, five hundred laps, and every single turn is a left. Your route is kinder.

## Notes for the owner

Seven attractions, twenty-eight signs. A dry run of `tools/bake_billboards.py`
on this sheet resolves every leg and bakes all twenty-eight (no `--write`).
A spacing check against the baked legs found no callout within 2.2 miles of
any sign in its direction. Every line is spelled out with no digits and runs
twenty-four to twenty-six words. The joke in each is original.

Attractions, sources, and what was checked:

- **Casey Jones Village.** https://www.caseyjones.com/ (open; sixtieth
  anniversary ribbon cutting May 2025; 56 Casey Jones Lane, I-40 Exit 80A).
  Roadside America tip https://www.roadsideamerica.com/tip/22245 for the
  home and museum. Unsure: Exit 80 is missing from both legs' interchange
  lists, so its milepost is estimated a mile past Exit 79. The "ahead" signs
  are ten miles out, so a small error doesn't matter. Skipped: westbound on
  the Nashville to Jackson leg, which leaves I-40 at Exit 82, about two miles
  east of the village; and the Dyersburg to Jackson road (US 412), which
  crosses I-40 at Exit 79, a mile from it, but never runs on I-40.
- **Tina Turner Museum, West Tennessee Delta Heritage Center.**
  https://haywoodtn.gov/west-tennessee-delta-heritage-center/ (Exit 56, free
  admission, hours) and
  https://www.foxnews.com/entertainment/one-room-schoolhouse-that-singer-tina-turner-attended-in-west-tennessee-becomes-a-museum
  (the schoolhouse was moved from Nutbush by
  tractor-trailer in 2012 and opened as the museum in 2014). The copy names
  no song. Unsure: on Jackson to Memphis the sign is three miles before the
  exit instead of two, because the leg's Hatchie River crossing sits just
  east of Exit 56.
- **Loretta Lynn's Ranch.** https://lorettalynn.com/ (open; museum and tours
  closed Monday and Tuesday; trail ride dated August 31 to September 4,
  2026) and https://lorettalynn.com/pages/about-the-ranch (bought 1966, the town
  included) and
  https://www.foxnews.com/lifestyle/loretta-lynn-ranch-iconic-sprawling-perhaps-haunted
  (her words: they did not know the town came with it). Directions from I-40 Exit 143,
  seven miles north on Highway 13:
  https://www.mxsports.com/event/amateur-national-motocross-championship/directions.
  Unsure: on Nashville to Jackson the sign is about five miles before Exit
  143, just past Exit 148. That leg's Tennessee, Buffalo and Duck River
  callouts sit 2.6 miles from the exit, which leaves no closer slot. "Next
  exit" is still true there.
- **The Lost Sea.** https://thelostsea.com/ (open every day but Thanksgiving
  and Christmas; boat ride; Exit 60, then seven miles) and
  https://en.wikipedia.org/wiki/Lost_Sea (found in 1905 by a thirteen-year-old,
  Ben Sands; largest underground lake in the United States).
- **Museum of Appalachia.** https://museumofappalachia.org/directions/ (Exit
  122, one mile east; hours) and
  https://en.wikipedia.org/wiki/Museum_of_Appalachia (more than thirty
  historic buildings). Unsure: the London to Knoxville leg already carries a
  museum landmark named "Norris Museum ahead" at mile 77.9, with no source
  field. It may be this museum under another name, or the Lenoir Museum at
  Norris Dam. Either way, a southbound driver hears the Appalachia sign
  first and "Norris Museum ahead" nine miles later. Worth a look at that
  record before baking.
- **Ruby Falls.** https://www.rubyfalls.com/ and Roadside America
  https://www.roadsideamerica.com/tip/1210 (open daily; eastbound Exit 174,
  westbound Exit 178) and https://en.wikipedia.org/wiki/Ruby_Falls (1,120
  feet below the summit; found by Leo Lambert in 1928, named for his wife).
  Ruby Falls is on the methodology seed list as its own entry beside Rock
  City. The copy doesn't mention Rock City, but the two are Lookout Mountain
  neighbors, so confirm it is in. Unsure: the Gadsden and Huntsville legs
  list no I-24 exits, so their Exit 174 mileposts are estimated. The
  estimates come from the Murfreesboro leg's distances and agree within a
  tenth of a mile both ways. Nine signs is the heaviest set here, because
  every road into Chattanooga passes it. Trimming to the three I-24 through
  signs would be reasonable.
- **Bristol Motor Speedway.** https://en.wikipedia.org/wiki/Bristol_Motor_Speedway
  (0.533-mile concrete, 24 to 28 degree banking, Cup races in spring and
  the September night race, each five hundred laps) and
  https://www.bristoltn.gov/Archive.aspx?ADID=516 (tours, US 11E). An OSRM
  route over the same roads, https://router.project-osrm.org/, confirms the
  leg's route runs along Tennessee 394 on the track's south side. This is a
  different attraction from the Birthplace of Country Music Museum line in
  the I-81 pool. That pool line can still be read anywhere on this leg,
  though, so a driver may hear both Bristol signs on one run.

Dropped:

- **Jack Daniel's Distillery, Lynchburg.** No leg comes within eight miles.
  The US 231 legs pass about eight to ten miles west, and I-24 at Exit 111
  is about twenty miles away, so neither "next exit" nor "ahead" is honest.
- **Cumberland Caverns, McMinnville.** More than twelve miles from every leg.
- **Tennessee Aquarium.** It sits at the Chattanooga city node, so every leg
  starts or ends on it and no sign can stand before it. Chattanooga already
  has the Choo Choo approach line, and Ruby Falls covers the city.
- **Rock City.** Standing owner exclusion.
- **Dollywood and Pigeon Forge, Graceland, Beale Street, the Opry, the
  Ryman, the Hermitage.** Memphis, Nashville and Knoxville already carry
  signs.
- **Buc-ee's at Crossville, the first Cracker Barrel at Lebanon.** Chains the
  pools already cover.

Found along the way (data, not this sheet): the Hatchie River callout on
I-40 is at mile 56.6 on Memphis to Jackson but 67.4 on Memphis to
Nashville, over the same road. On Memphis to Nashville the Tennessee,
Buffalo and Duck River crossings are stacked together at mile 148.7. The
real I-40 bridge over the Tennessee (Jimmy Mann Evans Memorial Bridge,
Wikipedia) is near mile 134, just past Exit 133, about fourteen miles west
of that callout. None of
this moves a sign here, but at least one callout of each pair is heard in the wrong
place.
