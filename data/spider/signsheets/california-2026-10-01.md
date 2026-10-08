# California attractions, both directions -- 2026-10-01

Draft for the owner's review, not yet approved.

Thirty-four real roadside attractions in California, each signed in every
direction a leg passes it, 170 signs in all. Every `leg:` is written the way
the driver reads the sign and `at_mi` counts from that end;
`tools/bake_billboards.py` mirrors the milepost onto a leg stored the other
way round and records which way the billboard faces.

California allows commercial billboards beside its Interstates and the
National Highway System under a Caltrans outdoor advertising permit (Outdoor
Advertising Act, Business and Professions Code 5200 and following;
dot.ca.gov/programs/traffic-operations/oda). Section 5440 bars displays aimed
at a classified landscaped freeway, and section 5440.1 bars any display along
an officially designated state scenic highway or scenic byway. The designated
segments on the game's roads (Caltrans list of eligible and officially
designated State Scenic Highways, October 2025): I-5 from Route 152 north to
I-580; Highway 152 from the Santa Clara County line east to I-5; Highway 156
from Castroville to US 101; US 101 through Del Norte Coast Redwoods and on the
Gaviota Coast; US 395 in Mono County and from Fort Independence north to Fish
Springs Road; I-580 from I-5 over the Altamont; I-680 from Fremont to Walnut
Creek; I-280; Highway 12 by Sonoma. US 97 from Weed to Oregon is the Volcanic
Legacy Scenic Byway, where 23 USC 131(s) bars new billboards. No sign on this
sheet stands on any of them. Landscaped-freeway classification is not in the
game's data.

Mileposts come from projecting each attraction onto the legs' dense geometry,
read against each leg's interchange list. "Next exit" signs stand between the
attraction's exit and the exit before it, one to two miles out, and only where
the interchange list has no gap in its exit numbers there; otherwise the sign
reads "ahead". "Ahead" signs stand about eight to twelve miles out, closer
where village callouts or the scenic segments leave no other room. A sign
about a city stands on the legs into it, never on the ones leaving. Each sign
sits at least 2.2 miles from every other callout heard in the same direction
(rivers, museums, passes, villages within a mile and a half of the road,
billboards facing the same way, and every other sign on the west-coast
sheets).

## Harris Ranch, Coalinga (I-5 Exit 334)

The Inn at Harris Ranch, with its steakhouse, bakery and country store, 24505 West Dorris Avenue at I-5 Exit 334 and State Highway 198, midway between Los Angeles and San Francisco, with its own private landing strip (aaa.com; i5exitguide.com).

### Harris Ranch (northbound)
- treatment: billboard
- leg: los_angeles_ca_us -> san_francisco_ca_us
- at_mi: 189.2
- spoken: Billboard: Harris Ranch, ahead at Coalinga. A steakhouse and inn halfway between Los Angeles and San Francisco, with its own airstrip. Please arrive by road.

### Harris Ranch (southbound)
- treatment: billboard
- leg: san_francisco_ca_us -> los_angeles_ca_us
- at_mi: 183.3
- spoken: Billboard: Harris Ranch, next exit. A steakhouse and inn halfway between Los Angeles and San Francisco, with its own airstrip. Please arrive by road.

## The Olive Pit, Corning (I-5 Exit 631)

Olive tasting bar, cafe and shop in Corning, the Olive City, since 1967, at I-5 Exit 631 (californiagrown.org; activenorcal.com).

### The Olive Pit (northbound)
- treatment: billboard
- leg: sacramento_ca_us -> portland_or_us
- at_mi: 102.5
- spoken: Billboard: The Olive Pit, ahead in Corning. Free olive tasting since nineteen sixty-seven. Try the garlic ones, then roll the windows down.

### The Olive Pit (southbound)
- treatment: billboard
- leg: portland_or_us -> sacramento_ca_us
- at_mi: 463.8
- spoken: Billboard: The Olive Pit, next exit in Corning. Free olive tasting since nineteen sixty-seven. Try the garlic ones, then roll the windows down.

### The Olive Pit (northbound)
- treatment: billboard
- leg: sacramento_ca_us -> redding_ca_us
- at_mi: 111.3
- spoken: Billboard: The Olive Pit, next exit in Corning. Free olive tasting since nineteen sixty-seven. Try the garlic ones, then roll the windows down.

### The Olive Pit (southbound)
- treatment: billboard
- leg: redding_ca_us -> sacramento_ca_us
- at_mi: 47.7
- spoken: Billboard: The Olive Pit, next exit in Corning. Free olive tasting since nineteen sixty-seven. Try the garlic ones, then roll the windows down.

### The Olive Pit (northbound)
- treatment: billboard
- leg: san_francisco_ca_us -> portland_or_us
- at_mi: 165.9
- spoken: Billboard: The Olive Pit, next exit in Corning. Free olive tasting since nineteen sixty-seven. Try the garlic ones, then roll the windows down.

### The Olive Pit (southbound)
- treatment: billboard
- leg: portland_or_us -> san_francisco_ca_us
- at_mi: 464.1
- spoken: Billboard: The Olive Pit, next exit in Corning. Free olive tasting since nineteen sixty-seven. Try the garlic ones, then roll the windows down.

## Granzella's, Williams (I-5 Exit 578)

Italian deli and restaurant in Williams since 1976, known for its house muffuletta, at I-5 Exit 578 (ABC10 Bartell's Backroads; flavortownusa.com).

### Granzella's (northbound)
- treatment: billboard
- leg: sacramento_ca_us -> portland_or_us
- at_mi: 57.6
- spoken: Billboard: Granzella's, next exit in Williams. An Italian deli since nineteen seventy-six, famous for its muffuletta. The napkins are free. Take several.

### Granzella's (southbound)
- treatment: billboard
- leg: portland_or_us -> sacramento_ca_us
- at_mi: 508.7
- spoken: Billboard: Granzella's, ahead in Williams. An Italian deli since nineteen seventy-six, famous for its muffuletta. The napkins are free. Take several.

### Granzella's (northbound)
- treatment: billboard
- leg: sacramento_ca_us -> redding_ca_us
- at_mi: 57.9
- spoken: Billboard: Granzella's, next exit in Williams. An Italian deli since nineteen seventy-six, famous for its muffuletta. The napkins are free. Take several.

### Granzella's (southbound)
- treatment: billboard
- leg: redding_ca_us -> sacramento_ca_us
- at_mi: 92.2
- spoken: Billboard: Granzella's, ahead in Williams. An Italian deli since nineteen seventy-six, famous for its muffuletta. The napkins are free. Take several.

### Granzella's (northbound)
- treatment: billboard
- leg: san_francisco_ca_us -> portland_or_us
- at_mi: 112.5
- spoken: Billboard: Granzella's, next exit in Williams. An Italian deli since nineteen seventy-six, famous for its muffuletta. The napkins are free. Take several.

### Granzella's (southbound)
- treatment: billboard
- leg: portland_or_us -> san_francisco_ca_us
- at_mi: 509.0
- spoken: Billboard: Granzella's, ahead in Williams. An Italian deli since nineteen seventy-six, famous for its muffuletta. The napkins are free. Take several.

## Lake Shasta Caverns, O'Brien (I-5 Exit 695)

Tours cross the McCloud Arm of Shasta Lake by catamaran, ride a bus up the cliff, and climb more than six hundred steps through the caverns; I-5 Exit 695, Shasta Caverns Road; open all year, fewer tours in winter (Moon California; Roadside America).

### Lake Shasta Caverns (northbound)
- treatment: billboard
- leg: redding_ca_us -> klamath_falls_or_us
- at_mi: 7.9
- spoken: Billboard: Lake Shasta Caverns, ahead at O'Brien. A boat across the lake, a bus up the cliff, then six hundred steps underground. The truck waits on shore.

### Lake Shasta Caverns (southbound)
- treatment: billboard
- leg: klamath_falls_or_us -> redding_ca_us
- at_mi: 113.1
- spoken: Billboard: Lake Shasta Caverns, ahead at O'Brien. A boat across the lake, a bus up the cliff, then six hundred steps underground. The truck waits on shore.

### Lake Shasta Caverns (northbound)
- treatment: billboard
- leg: redding_ca_us -> mount_shasta_ca_us
- at_mi: 5.6
- spoken: Billboard: Lake Shasta Caverns, ahead at O'Brien. A boat across the lake, a bus up the cliff, then six hundred steps underground. The truck waits on shore.

### Lake Shasta Caverns (southbound)
- treatment: billboard
- leg: mount_shasta_ca_us -> redding_ca_us
- at_mi: 33.3
- spoken: Billboard: Lake Shasta Caverns, ahead at O'Brien. A boat across the lake, a bus up the cliff, then six hundred steps underground. The truck waits on shore.

### Lake Shasta Caverns (northbound)
- treatment: billboard
- leg: sacramento_ca_us -> portland_or_us
- at_mi: 174.5
- spoken: Billboard: Lake Shasta Caverns, next exit. A boat across the lake, a bus up the cliff, then six hundred steps underground. The truck waits on shore.

### Lake Shasta Caverns (southbound)
- treatment: billboard
- leg: portland_or_us -> sacramento_ca_us
- at_mi: 400.5
- spoken: Billboard: Lake Shasta Caverns, next exit. A boat across the lake, a bus up the cliff, then six hundred steps underground. The truck waits on shore.

### Lake Shasta Caverns (northbound)
- treatment: billboard
- leg: san_francisco_ca_us -> portland_or_us
- at_mi: 229.4
- spoken: Billboard: Lake Shasta Caverns, next exit. A boat across the lake, a bus up the cliff, then six hundred steps underground. The truck waits on shore.

### Lake Shasta Caverns (southbound)
- treatment: billboard
- leg: portland_or_us -> san_francisco_ca_us
- at_mi: 400.6
- spoken: Billboard: Lake Shasta Caverns, next exit. A boat across the lake, a bus up the cliff, then six hundred steps underground. The truck waits on shore.

## The Sundial Bridge, Redding (city node)

Santiago Calatrava's glass-decked footbridge over the Sacramento River at Turtle Bay Exploration Park, opened 2004; it works as a sundial whose shadow is marked from eleven to three (turtlebay.org; Wikipedia). Signed on the legs into Redding.

### The Sundial Bridge (northbound)
- treatment: billboard
- leg: chico_ca_us -> redding_ca_us
- at_mi: 61.6
- spoken: Billboard: Redding's Sundial Bridge is ahead, a glass footbridge built as a giant sundial. It tells time from eleven to three, then takes the afternoon off.

### The Sundial Bridge (eastbound)
- treatment: billboard
- leg: eureka_ca_us -> redding_ca_us
- at_mi: 136.0
- spoken: Billboard: Redding's Sundial Bridge is ahead, a glass footbridge built as a giant sundial. It tells time from eleven to three, then takes the afternoon off.

### The Sundial Bridge (southbound)
- treatment: billboard
- leg: klamath_falls_or_us -> redding_ca_us
- at_mi: 127.3
- spoken: Billboard: Redding's Sundial Bridge is ahead, a glass footbridge built as a giant sundial. It tells time from eleven to three, then takes the afternoon off.

### The Sundial Bridge (southbound)
- treatment: billboard
- leg: mount_shasta_ca_us -> redding_ca_us
- at_mi: 49.1
- spoken: Billboard: Redding's Sundial Bridge is ahead, a glass footbridge built as a giant sundial. It tells time from eleven to three, then takes the afternoon off.

### The Sundial Bridge (northbound)
- treatment: billboard
- leg: sacramento_ca_us -> portland_or_us
- at_mi: 150.8
- spoken: Billboard: Redding's Sundial Bridge is ahead, a glass footbridge built as a giant sundial. It tells time from eleven to three, then takes the afternoon off.

### The Sundial Bridge (southbound)
- treatment: billboard
- leg: portland_or_us -> sacramento_ca_us
- at_mi: 408.3
- spoken: Billboard: Redding's Sundial Bridge is ahead, a glass footbridge built as a giant sundial. It tells time from eleven to three, then takes the afternoon off.

### The Sundial Bridge (northbound)
- treatment: billboard
- leg: sacramento_ca_us -> redding_ca_us
- at_mi: 147.5
- spoken: Billboard: Redding's Sundial Bridge is ahead, a glass footbridge built as a giant sundial. It tells time from eleven to three, then takes the afternoon off.

### The Sundial Bridge (northbound)
- treatment: billboard
- leg: san_francisco_ca_us -> portland_or_us
- at_mi: 205.3
- spoken: Billboard: Redding's Sundial Bridge is ahead, a glass footbridge built as a giant sundial. It tells time from eleven to three, then takes the afternoon off.

### The Sundial Bridge (southbound)
- treatment: billboard
- leg: portland_or_us -> san_francisco_ca_us
- at_mi: 408.1
- spoken: Billboard: Redding's Sundial Bridge is ahead, a glass footbridge built as a giant sundial. It tells time from eleven to three, then takes the afternoon off.

### The Sundial Bridge (westbound)
- treatment: billboard
- leg: susanville_ca_us -> redding_ca_us
- at_mi: 105.7
- spoken: Billboard: Redding's Sundial Bridge is ahead, a glass footbridge built as a giant sundial. It tells time from eleven to three, then takes the afternoon off.

## California State Railroad Museum, Old Sacramento (city node)

111 I Street in Old Sacramento State Historic Park: more than twenty restored locomotives and cars, some from 1862 (Wikipedia; parks.ca.gov). Signed on the legs into Sacramento.

### California State Railroad Museum (westbound)
- treatment: billboard
- leg: chico_ca_us -> fairfield_ca_us
- at_mi: 75.2
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (eastbound)
- treatment: billboard
- leg: fairfield_ca_us -> chico_ca_us
- at_mi: 30.8
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (northbound)
- treatment: billboard
- leg: fresno_ca_us -> sacramento_ca_us
- at_mi: 159.0
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (southbound)
- treatment: billboard
- leg: portland_or_us -> sacramento_ca_us
- at_mi: 567.0
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (southbound)
- treatment: billboard
- leg: redding_ca_us -> sacramento_ca_us
- at_mi: 152.1
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (westbound)
- treatment: billboard
- leg: reno_nv_us -> sacramento_ca_us
- at_mi: 121.0
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (eastbound)
- treatment: billboard
- leg: san_francisco_ca_us -> sacramento_ca_us
- at_mi: 78.8
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (southbound)
- treatment: billboard
- leg: yuba_city_ca_us -> sacramento_ca_us
- at_mi: 32.0
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (eastbound)
- treatment: billboard
- leg: san_francisco_ca_us -> salt_lake_city_ut_us
- at_mi: 72.9
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (westbound)
- treatment: billboard
- leg: salt_lake_city_ut_us -> san_francisco_ca_us
- at_mi: 642.0
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (eastbound)
- treatment: billboard
- leg: san_jose_ca_us -> sacramento_ca_us
- at_mi: 106.6
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (eastbound)
- treatment: billboard
- leg: santa_rosa_ca_us -> sacramento_ca_us
- at_mi: 84.6
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

### California State Railroad Museum (northbound)
- treatment: billboard
- leg: stockton_ca_us -> sacramento_ca_us
- at_mi: 38.5
- spoken: Billboard: The California State Railroad Museum, ahead in Old Sacramento. More than twenty restored locomotives, some from the eighteen sixties. Retirement suits them.

## Jelly Belly Visitor Center, Fairfield (I-80 Exit 44A)

One Jelly Belly Lane, half a mile from I-80 Exit 44A; open daily, with a self-guided quarter-mile walkway over the factory floor and a cafe serving burgers and pizza in the jelly-bean shape (visitfairfield.com; daytrippen.com; iexitapp.com).

### Jelly Belly (westbound)
- treatment: billboard
- leg: chico_ca_us -> fairfield_ca_us
- at_mi: 114.1
- spoken: Billboard: The Jelly Belly factory, ahead in Fairfield. Watch the beans get made from a catwalk, then order a burger shaped like one. It tastes like a burger.

### Jelly Belly (westbound)
- treatment: billboard
- leg: sacramento_ca_us -> san_francisco_ca_us
- at_mi: 32.6
- spoken: Billboard: The Jelly Belly factory, ahead in Fairfield. Watch the beans get made from a catwalk, then order a burger shaped like one. It tastes like a burger.

### Jelly Belly (eastbound)
- treatment: billboard
- leg: san_francisco_ca_us -> sacramento_ca_us
- at_mi: 35.4
- spoken: Billboard: The Jelly Belly factory, ahead in Fairfield. Watch the beans get made from a catwalk, then order a burger shaped like one. It tastes like a burger.

### Jelly Belly (eastbound)
- treatment: billboard
- leg: san_francisco_ca_us -> salt_lake_city_ut_us
- at_mi: 33.7
- spoken: Billboard: The Jelly Belly factory, ahead in Fairfield. Watch the beans get made from a catwalk, then order a burger shaped like one. It tastes like a burger.

### Jelly Belly (westbound)
- treatment: billboard
- leg: salt_lake_city_ut_us -> san_francisco_ca_us
- at_mi: 691.8
- spoken: Billboard: The Jelly Belly factory, next exit. Watch the beans get made from a catwalk, then order a burger shaped like one. It tastes like a burger.

### Jelly Belly (eastbound)
- treatment: billboard
- leg: santa_rosa_ca_us -> sacramento_ca_us
- at_mi: 51.5
- spoken: Billboard: The Jelly Belly factory, next exit. Watch the beans get made from a catwalk, then order a burger shaped like one. It tastes like a burger.

### Jelly Belly (westbound)
- treatment: billboard
- leg: sacramento_ca_us -> santa_rosa_ca_us
- at_mi: 32.0
- spoken: Billboard: The Jelly Belly factory, ahead in Fairfield. Watch the beans get made from a catwalk, then order a burger shaped like one. It tastes like a burger.

### Jelly Belly (eastbound)
- treatment: billboard
- leg: santa_rosa_ca_us -> stockton_ca_us
- at_mi: 40.8
- spoken: Billboard: The Jelly Belly factory, ahead in Fairfield. Watch the beans get made from a catwalk, then order a burger shaped like one. It tastes like a burger.

### Jelly Belly (westbound)
- treatment: billboard
- leg: stockton_ca_us -> santa_rosa_ca_us
- at_mi: 45.2
- spoken: Billboard: The Jelly Belly factory, ahead in Fairfield. Watch the beans get made from a catwalk, then order a burger shaped like one. It tastes like a burger.

## Charles M. Schulz Museum, Santa Rosa (city node)

2301 Hardies Lane, Santa Rosa, founded in 2002, the largest collection of original Peanuts artwork in the world (schulzmuseum.org fact sheet, 2025). Signed on US 101 into Santa Rosa from both sides.

### Charles M. Schulz Museum (northbound)
- treatment: billboard
- leg: san_francisco_ca_us -> santa_rosa_ca_us
- at_mi: 41.0
- spoken: Billboard: The Charles M. Schulz Museum, ahead in Santa Rosa. The largest collection of original Peanuts art anywhere. The kite-eating tree is not on display.

### Charles M. Schulz Museum (southbound)
- treatment: billboard
- leg: ukiah_ca_us -> santa_rosa_ca_us
- at_mi: 50.0
- spoken: Billboard: The Charles M. Schulz Museum, ahead in Santa Rosa. The largest collection of original Peanuts art anywhere. The kite-eating tree is not on display.

## The Skunk Train, Willits (city node)

The redwood logging line out of Willits; the name dates from 1925, when gasoline motorcars with oil stoves gave off fumes the locals said you could smell before you could see (skunktrain.com; 2026 Willits season press release).

### The Skunk Train (northbound)
- treatment: billboard
- leg: ukiah_ca_us -> eureka_ca_us
- at_mi: 13.6
- spoken: Billboard: The Skunk Train runs out of Willits, ahead, into the redwoods. Its early motorcars smelled so bad the name stuck. The smell did not.

### The Skunk Train (southbound)
- treatment: billboard
- leg: eureka_ca_us -> ukiah_ca_us
- at_mi: 126.4
- spoken: Billboard: The Skunk Train runs out of Willits, ahead, into the redwoods. Its early motorcars smelled so bad the name stuck. The smell did not.

### The Skunk Train (northbound)
- treatment: billboard
- leg: ukiah_ca_us -> willits_ca_us
- at_mi: 17.0
- spoken: Billboard: The Skunk Train runs out of Willits, ahead, into the redwoods. Its early motorcars smelled so bad the name stuck. The smell did not.

### The Skunk Train (southbound)
- treatment: billboard
- leg: fortuna_ca_us -> willits_ca_us
- at_mi: 109.0
- spoken: Billboard: The Skunk Train runs out of Willits, ahead, into the redwoods. Its early motorcars smelled so bad the name stuck. The smell did not.

## Chandelier Drive-Thru Tree, Leggett (US 101 at Highway 1)

A living coast redwood with a passage six feet wide by six feet nine inches cut in the 1930s, in Underwood Park at the junction of US 101 and Highway 1 in Leggett; open daily, per-car admission (drivethrutree.com; Roadside America).

### Chandelier Drive-Thru Tree (northbound)
- treatment: billboard
- leg: ukiah_ca_us -> eureka_ca_us
- at_mi: 60.2
- spoken: Billboard: The Chandelier Drive-Thru Tree, ahead in Leggett. A living redwood with a tunnel six feet wide. Cars fit. Your truck can wave from the road.

### Chandelier Drive-Thru Tree (southbound)
- treatment: billboard
- leg: eureka_ca_us -> ukiah_ca_us
- at_mi: 81.6
- spoken: Billboard: The Chandelier Drive-Thru Tree, ahead in Leggett. A living redwood with a tunnel six feet wide. Cars fit. Your truck can wave from the road.

### Chandelier Drive-Thru Tree (northbound)
- treatment: billboard
- leg: willits_ca_us -> fortuna_ca_us
- at_mi: 37.1
- spoken: Billboard: The Chandelier Drive-Thru Tree, ahead in Leggett. A living redwood with a tunnel six feet wide. Cars fit. Your truck can wave from the road.

### Chandelier Drive-Thru Tree (southbound)
- treatment: billboard
- leg: fortuna_ca_us -> willits_ca_us
- at_mi: 64.8
- spoken: Billboard: The Chandelier Drive-Thru Tree, ahead in Leggett. A living redwood with a tunnel six feet wide. Cars fit. Your truck can wave from the road.

## Confusion Hill, Piercy (US 101)

A gravity house and mystery spot on the old Redwood Highway since 1949, 75001 North Highway 101, now just off the 2009 bypass bridges; open all year (Roadside America).

### Confusion Hill (northbound)
- treatment: billboard
- leg: ukiah_ca_us -> eureka_ca_us
- at_mi: 71.4
- spoken: Billboard: Confusion Hill, ahead near Piercy. Since nineteen forty-nine its gravity house has made visitors lean the wrong way. Your load is not invited.

### Confusion Hill (southbound)
- treatment: billboard
- leg: eureka_ca_us -> ukiah_ca_us
- at_mi: 73.1
- spoken: Billboard: Confusion Hill, ahead near Piercy. Since nineteen forty-nine its gravity house has made visitors lean the wrong way. Your load is not invited.

### Confusion Hill (northbound)
- treatment: billboard
- leg: willits_ca_us -> fortuna_ca_us
- at_mi: 46.8
- spoken: Billboard: Confusion Hill, ahead near Piercy. Since nineteen forty-nine its gravity house has made visitors lean the wrong way. Your load is not invited.

### Confusion Hill (southbound)
- treatment: billboard
- leg: fortuna_ca_us -> willits_ca_us
- at_mi: 56.4
- spoken: Billboard: Confusion Hill, ahead near Piercy. Since nineteen forty-nine its gravity house has made visitors lean the wrong way. Your load is not invited.

## Avenue of the Giants (State Route 254)

Thirty-one and a half miles of the former US 101 through Humboldt Redwoods State Park, leaving US 101 near Phillipsville at the south end and Pepperwood at the north end (Wikipedia; gribblenation.org). Northbound signs stand before the south end, southbound before the north end.

### Avenue of the Giants (northbound)
- treatment: billboard
- leg: ukiah_ca_us -> eureka_ca_us
- at_mi: 88.5
- spoken: Billboard: The Avenue of the Giants, ahead. Thirty-one miles of the old highway under some of the tallest trees on earth. Look up later.

### Avenue of the Giants (northbound)
- treatment: billboard
- leg: willits_ca_us -> fortuna_ca_us
- at_mi: 67.0
- spoken: Billboard: The Avenue of the Giants, ahead. Thirty-one miles of the old highway under some of the tallest trees on earth. Look up later.

### Avenue of the Giants (southbound)
- treatment: billboard
- leg: eureka_ca_us -> ukiah_ca_us
- at_mi: 23.6
- spoken: Billboard: The Avenue of the Giants, ahead. Thirty-one miles of the old highway under some of the tallest trees on earth. Look up later.

### Avenue of the Giants (southbound)
- treatment: billboard
- leg: fortuna_ca_us -> willits_ca_us
- at_mi: 8.2
- spoken: Billboard: The Avenue of the Giants, ahead. Thirty-one miles of the old highway under some of the tallest trees on earth. Look up later.

## Trees of Mystery, Klamath (US 101)

A redwood park on US 101 at Klamath, with a forty-nine-foot Paul Bunyan (1961) and a thirty-five-foot Babe the Blue Ox out front and the SkyTrail gondola; a hidden staff member talks to visitors through Paul's speaker (Wikipedia; Only In Your State). US 101 north of the park, through Del Norte Coast Redwoods, is a designated state scenic highway, so the southbound sign stands just south of it.

### Trees of Mystery (northbound)
- treatment: billboard
- leg: eureka_ca_us -> crescent_city_ca_us
- at_mi: 58.3
- spoken: Billboard: Trees of Mystery, ahead in Klamath. A forty-nine-foot Paul Bunyan stands out front with his blue ox. He talks, too. Say hello.

### Trees of Mystery (southbound)
- treatment: billboard
- leg: crescent_city_ca_us -> eureka_ca_us
- at_mi: 16.7
- spoken: Billboard: Trees of Mystery, ahead in Klamath. A forty-nine-foot Paul Bunyan stands out front with his blue ox. He talks, too. Say hello.

## The coffeepot water tower, Kingsburg (Highway 99)

Kingsburg, Little Sweden, remodeled its 1911 water tower in 1985 to look like a Swedish coffee pot; it stands 122 feet and holds sixty thousand gallons, beside Highway 99 (Roadside America; PBS SoCal).

### Kingsburg Coffeepot (northbound)
- treatment: billboard
- leg: bakersfield_ca_us -> fresno_ca_us
- at_mi: 79.2
- spoken: Billboard: Kingsburg is ahead, where the Swedish town turned its water tower into a giant coffeepot. Sixty thousand gallons, and nobody has offered cream.

### Kingsburg Coffeepot (southbound)
- treatment: billboard
- leg: fresno_ca_us -> bakersfield_ca_us
- at_mi: 7.9
- spoken: Billboard: Kingsburg is ahead, where the Swedish town turned its water tower into a giant coffeepot. Sixty thousand gallons, and nobody has offered cream.

### Kingsburg Coffeepot (southbound)
- treatment: billboard
- leg: fresno_ca_us -> visalia_ca_us
- at_mi: 7.9
- spoken: Billboard: Kingsburg is ahead, where the Swedish town turned its water tower into a giant coffeepot. Sixty thousand gallons, and nobody has offered cream.

### Kingsburg Coffeepot (northbound)
- treatment: billboard
- leg: visalia_ca_us -> fresno_ca_us
- at_mi: 12.3
- spoken: Billboard: Kingsburg is ahead, where the Swedish town turned its water tower into a giant coffeepot. Sixty thousand gallons, and nobody has offered cream.

### Kingsburg Coffeepot (northbound)
- treatment: billboard
- leg: los_angeles_ca_us -> fresno_ca_us
- at_mi: 190.4
- spoken: Billboard: Kingsburg is ahead, where the Swedish town turned its water tower into a giant coffeepot. Sixty thousand gallons, and nobody has offered cream.

### Kingsburg Coffeepot (southbound)
- treatment: billboard
- leg: fresno_ca_us -> los_angeles_ca_us
- at_mi: 7.9
- spoken: Billboard: Kingsburg is ahead, where the Swedish town turned its water tower into a giant coffeepot. Sixty thousand gallons, and nobody has offered cream.

## Castle Air Museum, Atwater (Highway 99)

Military aircraft at the former Castle Air Force Base north of Atwater, among them an SR-71A Blackbird and an Avro Vulcan; open daily (Wikipedia; sr-71.org).

### Castle Air Museum (northbound)
- treatment: billboard
- leg: fresno_ca_us -> sacramento_ca_us
- at_mi: 52.0
- spoken: Billboard: Castle Air Museum, ahead near Atwater. Bombers, fighters, and a Blackbird that flew three times the speed of sound. The limit here is lower.

### Castle Air Museum (southbound)
- treatment: billboard
- leg: sacramento_ca_us -> fresno_ca_us
- at_mi: 100.7
- spoken: Billboard: Castle Air Museum, ahead near Atwater. Bombers, fighters, and a Blackbird that flew three times the speed of sound. The limit here is lower.

### Castle Air Museum (southbound)
- treatment: billboard
- leg: modesto_ca_us -> merced_ca_us
- at_mi: 26.7
- spoken: Billboard: Castle Air Museum, ahead near Atwater. Bombers, fighters, and a Blackbird that flew three times the speed of sound. The limit here is lower.

### Castle Air Museum (northbound)
- treatment: billboard
- leg: merced_ca_us -> modesto_ca_us
- at_mi: 1.0
- spoken: Billboard: Castle Air Museum, ahead near Atwater. Bombers, fighters, and a Blackbird that flew three times the speed of sound. The limit here is lower.

## Casa de Fruta, Pacheco Pass (Highway 152)

A roadside fruit stand on the west side of Pacheco Pass that grew into a restaurant, bakery, deli, carousel and train ride, in business more than 115 years (Wikipedia, State Route 152; California Grown). Highway 152 east of the Santa Clara County line is an officially designated state scenic highway, so the westbound signs stand between the summit and the stand.

### Casa de Fruta (eastbound)
- treatment: billboard
- leg: salinas_ca_us -> fresno_ca_us
- at_mi: 28.1
- spoken: Billboard: Casa de Fruta, ahead on Pacheco Pass. A fruit stand that kept growing until it had a restaurant, a carousel, and its own little train.

### Casa de Fruta (westbound)
- treatment: billboard
- leg: fresno_ca_us -> salinas_ca_us
- at_mi: 102.8
- spoken: Billboard: Casa de Fruta, ahead on Pacheco Pass. A fruit stand that kept growing until it had a restaurant, a carousel, and its own little train.

### Casa de Fruta (northbound)
- treatment: billboard
- leg: salinas_ca_us -> stockton_ca_us
- at_mi: 28.2
- spoken: Billboard: Casa de Fruta, ahead on Pacheco Pass. A fruit stand that kept growing until it had a restaurant, a carousel, and its own little train.

### Casa de Fruta (southbound)
- treatment: billboard
- leg: stockton_ca_us -> salinas_ca_us
- at_mi: 90.4
- spoken: Billboard: Casa de Fruta, ahead on Pacheco Pass. A fruit stand that kept growing until it had a restaurant, a carousel, and its own little train.

### Casa de Fruta (eastbound)
- treatment: billboard
- leg: san_jose_ca_us -> fresno_ca_us
- at_mi: 36.9
- spoken: Billboard: Casa de Fruta, ahead on Pacheco Pass. A fruit stand that kept growing until it had a restaurant, a carousel, and its own little train.

### Casa de Fruta (westbound)
- treatment: billboard
- leg: fresno_ca_us -> san_jose_ca_us
- at_mi: 102.2
- spoken: Billboard: Casa de Fruta, ahead on Pacheco Pass. A fruit stand that kept growing until it had a restaurant, a carousel, and its own little train.

## Mission San Juan Bautista (Highway 156)

The mission has had no bell tower since 1949; for Vertigo, Hitchcock painted one in on glass and built the inside on a set (Wikipedia, Vertigo; hitchcock.zone).

### Mission San Juan Bautista (eastbound)
- treatment: billboard
- leg: salinas_ca_us -> fresno_ca_us
- at_mi: 8.9
- spoken: Billboard: Mission San Juan Bautista, ahead. Hitchcock filmed Vertigo here and painted in a bell tower the mission does not have. Visitors still look up for it.

### Mission San Juan Bautista (westbound)
- treatment: billboard
- leg: fresno_ca_us -> salinas_ca_us
- at_mi: 113.0
- spoken: Billboard: Mission San Juan Bautista, ahead. Hitchcock filmed Vertigo here and painted in a bell tower the mission does not have. Visitors still look up for it.

### Mission San Juan Bautista (northbound)
- treatment: billboard
- leg: salinas_ca_us -> stockton_ca_us
- at_mi: 13.3
- spoken: Billboard: Mission San Juan Bautista, ahead. Hitchcock filmed Vertigo here and painted in a bell tower the mission does not have. Visitors still look up for it.

### Mission San Juan Bautista (southbound)
- treatment: billboard
- leg: stockton_ca_us -> salinas_ca_us
- at_mi: 103.0
- spoken: Billboard: Mission San Juan Bautista, ahead. Hitchcock filmed Vertigo here and painted in a bell tower the mission does not have. Visitors still look up for it.

## National Steinbeck Center, Salinas (city node)

One Main Street, Salinas, John Steinbeck's hometown; East of Eden is set in the Salinas Valley (steinbeck.org; Charity Navigator).

### National Steinbeck Center (eastbound)
- treatment: billboard
- leg: fairfield_ca_us -> salinas_ca_us
- at_mi: 125.0
- spoken: Billboard: The National Steinbeck Center, ahead in Salinas. His hometown, and the valley where East of Eden is set. The book takes longer than the valley.

### National Steinbeck Center (eastbound)
- treatment: billboard
- leg: fresno_ca_us -> salinas_ca_us
- at_mi: 132.1
- spoken: Billboard: The National Steinbeck Center, ahead in Salinas. His hometown, and the valley where East of Eden is set. The book takes longer than the valley.

### National Steinbeck Center (southbound)
- treatment: billboard
- leg: san_francisco_ca_us -> salinas_ca_us
- at_mi: 101.0
- spoken: Billboard: The National Steinbeck Center, ahead in Salinas. His hometown, and the valley where East of Eden is set. The book takes longer than the valley.

### National Steinbeck Center (northbound)
- treatment: billboard
- leg: san_luis_obispo_ca_us -> salinas_ca_us
- at_mi: 118.0
- spoken: Billboard: The National Steinbeck Center, ahead in Salinas. His hometown, and the valley where East of Eden is set. The book takes longer than the valley.

### National Steinbeck Center (southbound)
- treatment: billboard
- leg: stockton_ca_us -> salinas_ca_us
- at_mi: 122.3
- spoken: Billboard: The National Steinbeck Center, ahead in Salinas. His hometown, and the valley where East of Eden is set. The book takes longer than the valley.

### National Steinbeck Center (southbound)
- treatment: billboard
- leg: san_jose_ca_us -> salinas_ca_us
- at_mi: 51.0
- spoken: Billboard: The National Steinbeck Center, ahead in Salinas. His hometown, and the valley where East of Eden is set. The book takes longer than the valley.

## Pismo Beach (US 101)

The city has called itself the Clam Capital of the World since the 1940s and dresses its giant clam statues for the holidays; the Clam Island statue stands just off US 101 at Price Street (Roadside America; experiencepismobeach.com).

### Pismo Beach (southbound)
- treatment: billboard
- leg: san_luis_obispo_ca_us -> santa_maria_ca_us
- at_mi: 5.1
- spoken: Billboard: Pismo Beach, ahead. The self-declared clam capital of the world dresses its giant clam statue for every holiday. The clams have no say in it.

### Pismo Beach (northbound)
- treatment: billboard
- leg: santa_maria_ca_us -> san_luis_obispo_ca_us
- at_mi: 10.9
- spoken: Billboard: Pismo Beach, ahead. The self-declared clam capital of the world dresses its giant clam statue for every holiday. The clams have no say in it.

### Pismo Beach (southbound)
- treatment: billboard
- leg: visalia_ca_us -> santa_maria_ca_us
- at_mi: 140.2
- spoken: Billboard: Pismo Beach, ahead. The self-declared clam capital of the world dresses its giant clam statue for every holiday. The clams have no say in it.

### Pismo Beach (northbound)
- treatment: billboard
- leg: santa_maria_ca_us -> visalia_ca_us
- at_mi: 10.8
- spoken: Billboard: Pismo Beach, ahead. The self-declared clam capital of the world dresses its giant clam statue for every holiday. The clams have no say in it.

## Museum of Western Film History, Lone Pine (US 395)

701 South Main Street, Lone Pine; open daily. More than four hundred movies have been shot in the Alabama Hills and around Lone Pine, from Hopalong Cassidy to Iron Man (museumofwesternfilmhistory.org; Lonely Planet). Southbound signs stand south of Fort Independence, clear of the designated scenic stretch of 395.

### Museum of Western Film History (southbound)
- treatment: billboard
- leg: bishop_ca_us -> lone_pine_ca_us
- at_mi: 49.0
- spoken: Billboard: The Museum of Western Film History, ahead in Lone Pine. Four hundred movies were shot in these hills. The scenery has more credits than most actors.

### Museum of Western Film History (northbound)
- treatment: billboard
- leg: mojave_ca_us -> lone_pine_ca_us
- at_mi: 105.8
- spoken: Billboard: The Museum of Western Film History, ahead in Lone Pine. Four hundred movies were shot in these hills. The scenery has more credits than most actors.

### Museum of Western Film History (northbound)
- treatment: billboard
- leg: ridgecrest_ca_us -> bishop_ca_us
- at_mi: 70.4
- spoken: Billboard: The Museum of Western Film History, ahead in Lone Pine. Four hundred movies were shot in these hills. The scenery has more credits than most actors.

### Museum of Western Film History (southbound)
- treatment: billboard
- leg: bishop_ca_us -> ridgecrest_ca_us
- at_mi: 48.6
- spoken: Billboard: The Museum of Western Film History, ahead in Lone Pine. Four hundred movies were shot in these hills. The scenery has more credits than most actors.

## Erick Schat's Bakkery, Bishop (US 395)

763 North Main Street, Bishop, open daily; its Original Sheepherder Bread is still shaped by hand, from a loaf made for the sheepherders of the Owens Valley (bishopvisitor.com; RV.com). Signs into Bishop from the north stand south of the Mono County line, where 395 becomes a designated scenic highway; from the south, north of Fish Springs Road.

### Erick Schat's Bakkery (northbound)
- treatment: billboard
- leg: lone_pine_ca_us -> bishop_ca_us
- at_mi: 48.9
- spoken: Billboard: Erick Schat's Bakkery is ahead in Bishop, baking sheepherder bread by hand. The line goes out the door. The sheep are not in it.

### Erick Schat's Bakkery (southbound)
- treatment: billboard
- leg: mammoth_lakes_ca_us -> bishop_ca_us
- at_mi: 33.0
- spoken: Billboard: Erick Schat's Bakkery is ahead in Bishop, baking sheepherder bread by hand. The line goes out the door. The sheep are not in it.

### Erick Schat's Bakkery (northbound)
- treatment: billboard
- leg: ridgecrest_ca_us -> bishop_ca_us
- at_mi: 128.0
- spoken: Billboard: Erick Schat's Bakkery is ahead in Bishop, baking sheepherder bread by hand. The line goes out the door. The sheep are not in it.

## Borax Visitor Center, Boron (Highway 58)

Rio Tinto's free visitor center above the Boron mine, California's largest open-pit mine and the world's largest borax mine, with a twenty-mule-team replica out front (borax.com; Wikipedia; Atlas Obscura).

### Borax Visitor Center (eastbound)
- treatment: billboard
- leg: bakersfield_ca_us -> barstow_ca_us
- at_mi: 79.7
- spoken: Billboard: The Borax Visitor Center, ahead in Boron, looks into California's largest open-pit mine. Borax used to leave the desert behind twenty mules. Now it takes trucks.

### Borax Visitor Center (westbound)
- treatment: billboard
- leg: barstow_ca_us -> bakersfield_ca_us
- at_mi: 31.3
- spoken: Billboard: The Borax Visitor Center, ahead in Boron, looks into California's largest open-pit mine. Borax used to leave the desert behind twenty mules. Now it takes trucks.

### Borax Visitor Center (eastbound)
- treatment: billboard
- leg: lancaster_ca_us -> barstow_ca_us
- at_mi: 45.8
- spoken: Billboard: The Borax Visitor Center, ahead in Boron, looks into California's largest open-pit mine. Borax used to leave the desert behind twenty mules. Now it takes trucks.

### Borax Visitor Center (westbound)
- treatment: billboard
- leg: barstow_ca_us -> lancaster_ca_us
- at_mi: 31.2
- spoken: Billboard: The Borax Visitor Center, ahead in Boron, looks into California's largest open-pit mine. Borax used to leave the desert behind twenty mules. Now it takes trucks.

## Red Rock Canyon State Park (Highway 14)

Striped sandstone cliffs on both sides of Highway 14, twenty-five miles northeast of Mojave; the Jurassic Park dig-site scene was filmed here (parks.ca.gov brochure; Tehachapi News, 2022).

### Red Rock Canyon State Park (southbound)
- treatment: billboard
- leg: lone_pine_ca_us -> mojave_ca_us
- at_mi: 80.0
- spoken: Billboard: Red Rock Canyon State Park, ahead. The striped cliffs played the fossil dig in Jurassic Park. The dinosaurs were added later.

### Red Rock Canyon State Park (northbound)
- treatment: billboard
- leg: mojave_ca_us -> lone_pine_ca_us
- at_mi: 17.0
- spoken: Billboard: Red Rock Canyon State Park, ahead. The striped cliffs played the fossil dig in Jurassic Park. The dinosaurs were added later.

### Red Rock Canyon State Park (southbound)
- treatment: billboard
- leg: ridgecrest_ca_us -> mojave_ca_us
- at_mi: 25.0
- spoken: Billboard: Red Rock Canyon State Park, ahead. The striped cliffs played the fossil dig in Jurassic Park. The dinosaurs were added later.

### Red Rock Canyon State Park (northbound)
- treatment: billboard
- leg: mojave_ca_us -> ridgecrest_ca_us
- at_mi: 17.0
- spoken: Billboard: Red Rock Canyon State Park, ahead. The striped cliffs played the fossil dig in Jurassic Park. The dinosaurs were added later.

## Vasquez Rocks, Agua Dulce (Highway 14, Agua Dulce Canyon Road)

Tilted sandstone slabs in a free Los Angeles County park beside the Antelope Valley Freeway, a Star Trek location since the original series (Wikipedia; Roadside America); exit at Agua Dulce Canyon Road.

### Vasquez Rocks (northbound)
- treatment: billboard
- leg: oxnard_ca_us -> lancaster_ca_us
- at_mi: 61.1
- spoken: Billboard: Vasquez Rocks, ahead at Agua Dulce. These tilted slabs have played a dozen alien planets on Star Trek. They have never once left Los Angeles County.

### Vasquez Rocks (southbound)
- treatment: billboard
- leg: lancaster_ca_us -> oxnard_ca_us
- at_mi: 21.9
- spoken: Billboard: Vasquez Rocks, ahead at Agua Dulce. These tilted slabs have played a dozen alien planets on Star Trek. They have never once left Los Angeles County.

### Vasquez Rocks (northbound)
- treatment: billboard
- leg: santa_ana_ca_us -> lancaster_ca_us
- at_mi: 66.2
- spoken: Billboard: Vasquez Rocks, ahead at Agua Dulce. These tilted slabs have played a dozen alien planets on Star Trek. They have never once left Los Angeles County.

### Vasquez Rocks (southbound)
- treatment: billboard
- leg: lancaster_ca_us -> santa_ana_ca_us
- at_mi: 29.3
- spoken: Billboard: Vasquez Rocks, next exit. These tilted slabs have played a dozen alien planets on Star Trek. They have never once left Los Angeles County.

### Vasquez Rocks (northbound)
- treatment: billboard
- leg: valencia_ca_us -> victorville_ca_us
- at_mi: 23.7
- spoken: Billboard: Vasquez Rocks, next exit. These tilted slabs have played a dozen alien planets on Star Trek. They have never once left Los Angeles County.

### Vasquez Rocks (southbound)
- treatment: billboard
- leg: victorville_ca_us -> valencia_ca_us
- at_mi: 64.3
- spoken: Billboard: Vasquez Rocks, next exit. These tilted slabs have played a dozen alien planets on Star Trek. They have never once left Los Angeles County.

## Desert View Tower, In-Ko-Pah (I-8)

A five-story stone lookout built from 1922 by Bert Vaughn, with a museum inside and Boulder Park beside it, where Merle Ratcliff carved the rocks into a turtle, a bison, a skull and more in the 1930s; open daily, at the In-Ko-Pah Park Road exit (Wikipedia; hiddensandiego.com).

### Desert View Tower (eastbound)
- treatment: billboard
- leg: san_diego_ca_us -> el_centro_ca_us
- at_mi: 73.1
- spoken: Billboard: Desert View Tower, next exit. A stone lookout from the nineteen twenties, and boulders carved into a turtle, a bison and a skull. Pick a favorite.

### Desert View Tower (westbound)
- treatment: billboard
- leg: el_centro_ca_us -> san_diego_ca_us
- at_mi: 36.9
- spoken: Billboard: Desert View Tower, next exit. A stone lookout from the nineteen twenties, and boulders carved into a turtle, a bison and a skull. Pick a favorite.

### Desert View Tower (eastbound)
- treatment: billboard
- leg: san_diego_ca_us -> phoenix_az_us
- at_mi: 64.0
- spoken: Billboard: Desert View Tower, ahead. A stone lookout from the nineteen twenties, and boulders carved into a turtle, a bison and a skull. Pick a favorite.

### Desert View Tower (westbound)
- treatment: billboard
- leg: phoenix_az_us -> san_diego_ca_us
- at_mi: 271.0
- spoken: Billboard: Desert View Tower, ahead. A stone lookout from the nineteen twenties, and boulders carved into a turtle, a bison and a skull. Pick a favorite.

## The Official Center of the World, Felicity (I-8 Exit 164)

A twenty-one-foot pink granite pyramid in Felicity holds what the town declared the Official Center of the World, beside the Museum of History in Granite; Exit 164, Sidewinder Road (historyingranite.org; Islands).

### Center of the World (eastbound)
- treatment: billboard
- leg: el_centro_ca_us -> yuma_az_us
- at_mi: 49.2
- spoken: Billboard: The official Center of the World, next exit in Felicity. A pink granite pyramid marks the spot. The town said so, and nobody has proved otherwise.

### Center of the World (westbound)
- treatment: billboard
- leg: yuma_az_us -> el_centro_ca_us
- at_mi: 1.0
- spoken: Billboard: The official Center of the World, ahead in Felicity. A pink granite pyramid marks the spot. The town said so, and nobody has proved otherwise.

### Center of the World (eastbound)
- treatment: billboard
- leg: san_diego_ca_us -> phoenix_az_us
- at_mi: 151.3
- spoken: Billboard: The official Center of the World, ahead in Felicity. A pink granite pyramid marks the spot. The town said so, and nobody has proved otherwise.

### Center of the World (westbound)
- treatment: billboard
- leg: phoenix_az_us -> san_diego_ca_us
- at_mi: 192.2
- spoken: Billboard: The official Center of the World, next exit in Felicity. A pink granite pyramid marks the spot. The town said so, and nobody has proved otherwise.

## Imperial Sand Dunes (I-8)

The Algodones Dunes, California's largest mass of sand dunes, more than forty miles long, crossed by I-8 between Gordons Well Road and the Ogilby exit; Return of the Jedi's Sarlacc pit and sail barge scenes were filmed here (DesertUSA).

### Imperial Sand Dunes (eastbound)
- treatment: billboard
- leg: el_centro_ca_us -> yuma_az_us
- at_mi: 29.5
- spoken: Billboard: The Imperial Sand Dunes, ahead. Forty miles of sand, where Return of the Jedi filmed its desert battle. Stay on the pavement. The sand is hungry.

### Imperial Sand Dunes (eastbound)
- treatment: billboard
- leg: san_diego_ca_us -> phoenix_az_us
- at_mi: 139.2
- spoken: Billboard: The Imperial Sand Dunes, ahead. Forty miles of sand, where Return of the Jedi filmed its desert battle. Stay on the pavement. The sand is hungry.

### Imperial Sand Dunes (westbound)
- treatment: billboard
- leg: yuma_az_us -> el_centro_ca_us
- at_mi: 4.9
- spoken: Billboard: The Imperial Sand Dunes, ahead. Forty miles of sand, where Return of the Jedi filmed its desert battle. Stay on the pavement. The sand is hungry.

### Imperial Sand Dunes (westbound)
- treatment: billboard
- leg: phoenix_az_us -> san_diego_ca_us
- at_mi: 194.5
- spoken: Billboard: The Imperial Sand Dunes, ahead. Forty miles of sand, where Return of the Jedi filmed its desert battle. Stay on the pavement. The sand is hungry.

## Mount Shasta, birthplace of the Black Bear Diner (city node)

The first Black Bear Diner opened in Mount Shasta in 1995, on the old Berryvale strawberry fields; the chain had 166 locations in 14 states by August 2025 (Wikipedia; Black Bear Diner). Signed on the legs into Mount Shasta and the I-5 legs past it.

### Mount Shasta (southbound)
- treatment: billboard
- leg: yreka_ca_us -> mount_shasta_ca_us
- at_mi: 30.6
- spoken: Billboard: Mount Shasta is ahead, where the first Black Bear Diner opened in nineteen ninety-five. The mountain got there a little earlier.

### Mount Shasta (northbound)
- treatment: billboard
- leg: redding_ca_us -> klamath_falls_or_us
- at_mi: 50.3
- spoken: Billboard: Mount Shasta is ahead, where the first Black Bear Diner opened in nineteen ninety-five. The mountain got there a little earlier.

### Mount Shasta (southbound)
- treatment: billboard
- leg: klamath_falls_or_us -> redding_ca_us
- at_mi: 68.6
- spoken: Billboard: Mount Shasta is ahead, where the first Black Bear Diner opened in nineteen ninety-five. The mountain got there a little earlier.

### Mount Shasta (northbound)
- treatment: billboard
- leg: redding_ca_us -> mount_shasta_ca_us
- at_mi: 52.0
- spoken: Billboard: Mount Shasta is ahead, where the first Black Bear Diner opened in nineteen ninety-five. The mountain got there a little earlier.

### Mount Shasta (northbound)
- treatment: billboard
- leg: sacramento_ca_us -> portland_or_us
- at_mi: 211.9
- spoken: Billboard: Mount Shasta is ahead, where the first Black Bear Diner opened in nineteen ninety-five. The mountain got there a little earlier.

### Mount Shasta (southbound)
- treatment: billboard
- leg: portland_or_us -> sacramento_ca_us
- at_mi: 347.4
- spoken: Billboard: Mount Shasta is ahead, where the first Black Bear Diner opened in nineteen ninety-five. The mountain got there a little earlier.

### Mount Shasta (northbound)
- treatment: billboard
- leg: san_francisco_ca_us -> portland_or_us
- at_mi: 266.5
- spoken: Billboard: Mount Shasta is ahead, where the first Black Bear Diner opened in nineteen ninety-five. The mountain got there a little earlier.

### Mount Shasta (southbound)
- treatment: billboard
- leg: portland_or_us -> san_francisco_ca_us
- at_mi: 348.9
- spoken: Billboard: Mount Shasta is ahead, where the first Black Bear Diner opened in nineteen ninety-five. The mountain got there a little earlier.

## General Patton Memorial Museum, Chiriaco Summit (I-10 Exit 173)

Opened 1988 at the entrance to Camp Young, headquarters of the Desert Training Center, where more than a million soldiers trained between 1942 and 1944; tanks on display outside; open daily (desertusa.com; NBC Palm Springs, March 2026).

### General Patton Memorial Museum (westbound)
- treatment: billboard
- leg: phoenix_az_us -> los_angeles_ca_us
- at_mi: 206.0
- spoken: Billboard: The General Patton Memorial Museum, ahead at Chiriaco Summit. A million soldiers trained in this desert for the Second World War. The tanks out front are not going anywhere.

### General Patton Memorial Museum (eastbound)
- treatment: billboard
- leg: los_angeles_ca_us -> phoenix_az_us
- at_mi: 146.0
- spoken: Billboard: The General Patton Memorial Museum, ahead at Chiriaco Summit. A million soldiers trained in this desert for the Second World War. The tanks out front are not going anywhere.

### General Patton Memorial Museum (eastbound)
- treatment: billboard
- leg: indio_ca_us -> blythe_ca_us
- at_mi: 28.5
- spoken: Billboard: The General Patton Memorial Museum, next exit. A million soldiers trained in this desert for the Second World War. The tanks out front are not going anywhere.

### General Patton Memorial Museum (westbound)
- treatment: billboard
- leg: blythe_ca_us -> indio_ca_us
- at_mi: 66.5
- spoken: Billboard: The General Patton Memorial Museum, next exit. A million soldiers trained in this desert for the Second World War. The tanks out front are not going anywhere.

## Joshua Tree National Park, south entrance (I-10 Exit 168)

The Cottonwood Visitor Center, the park's south entrance, seven miles north of I-10 Exit 168 on Cottonwood Spring Road (nps.gov). Joshua trees are a yucca, Yucca brevifolia.

### Joshua Tree National Park (westbound)
- treatment: billboard
- leg: phoenix_az_us -> los_angeles_ca_us
- at_mi: 208.8
- spoken: Billboard: Joshua Tree National Park, ahead at Cottonwood Spring Road. The trees are really yuccas. Nobody has told them, and nobody should.

### Joshua Tree National Park (eastbound)
- treatment: billboard
- leg: los_angeles_ca_us -> phoenix_az_us
- at_mi: 151.7
- spoken: Billboard: Joshua Tree National Park, next exit, seven miles north. The trees are really yuccas. Nobody has told them, and nobody should.

### Joshua Tree National Park (eastbound)
- treatment: billboard
- leg: indio_ca_us -> blythe_ca_us
- at_mi: 15.5
- spoken: Billboard: Joshua Tree National Park, ahead at Cottonwood Spring Road. The trees are really yuccas. Nobody has told them, and nobody should.

### Joshua Tree National Park (westbound)
- treatment: billboard
- leg: blythe_ca_us -> indio_ca_us
- at_mi: 71.0
- spoken: Billboard: Joshua Tree National Park, next exit, seven miles north. The trees are really yuccas. Nobody has told them, and nobody should.

## Palm Springs Aerial Tramway (I-10)

The world's largest rotating tram cars, opened 1963, climbing Chino Canyon from 2,643 to 8,516 feet in about ten minutes; operating normally in 2026 (pstramway.com). Reached by Highway 111 from I-10 eastbound and by Indian Canyon Drive westbound.

### Palm Springs Aerial Tramway (eastbound)
- treatment: billboard
- leg: los_angeles_ca_us -> phoenix_az_us
- at_mi: 81.9
- spoken: Billboard: The Palm Springs Aerial Tramway, ahead. Its cars rotate all the way up the cliffs, almost six thousand feet. The view comes around to you.

### Palm Springs Aerial Tramway (eastbound)
- treatment: billboard
- leg: los_angeles_ca_us -> indio_ca_us
- at_mi: 79.7
- spoken: Billboard: The Palm Springs Aerial Tramway, ahead. Its cars rotate all the way up the cliffs, almost six thousand feet. The view comes around to you.

### Palm Springs Aerial Tramway (eastbound)
- treatment: billboard
- leg: riverside_ca_us -> indio_ca_us
- at_mi: 36.3
- spoken: Billboard: The Palm Springs Aerial Tramway, ahead. Its cars rotate all the way up the cliffs, almost six thousand feet. The view comes around to you.

### Palm Springs Aerial Tramway (westbound)
- treatment: billboard
- leg: phoenix_az_us -> los_angeles_ca_us
- at_mi: 260.1
- spoken: Billboard: The Palm Springs Aerial Tramway, ahead. Its cars rotate all the way up the cliffs, almost six thousand feet. The view comes around to you.

### Palm Springs Aerial Tramway (westbound)
- treatment: billboard
- leg: indio_ca_us -> los_angeles_ca_us
- at_mi: 14.1
- spoken: Billboard: The Palm Springs Aerial Tramway, ahead. Its cars rotate all the way up the cliffs, almost six thousand feet. The view comes around to you.

### Palm Springs Aerial Tramway (westbound)
- treatment: billboard
- leg: indio_ca_us -> riverside_ca_us
- at_mi: 16.0
- spoken: Billboard: The Palm Springs Aerial Tramway, ahead. Its cars rotate all the way up the cliffs, almost six thousand feet. The view comes around to you.

## Temecula wine country (I-15)

The Temecula Valley wineries line Rancho California Road east of I-15, beginning about four miles from the interstate (Expedia, Temecula Uncorked; Sunset).

### Temecula Wine Country (northbound)
- treatment: billboard
- leg: oceanside_ca_us -> victorville_ca_us
- at_mi: 21.3
- spoken: Billboard: Temecula wine country, ahead. Dozens of wineries line Rancho California Road. The driver gets the grape juice.

### Temecula Wine Country (southbound)
- treatment: billboard
- leg: victorville_ca_us -> oceanside_ca_us
- at_mi: 77.7
- spoken: Billboard: Temecula wine country, ahead. Dozens of wineries line Rancho California Road. The driver gets the grape juice.

### Temecula Wine Country (southbound)
- treatment: billboard
- leg: riverside_ca_us -> oceanside_ca_us
- at_mi: 30.4
- spoken: Billboard: Temecula wine country, ahead. Dozens of wineries line Rancho California Road. The driver gets the grape juice.

### Temecula Wine Country (northbound)
- treatment: billboard
- leg: oceanside_ca_us -> riverside_ca_us
- at_mi: 21.6
- spoken: Billboard: Temecula wine country, ahead. Dozens of wineries line Rancho California Road. The driver gets the grape juice.

### Temecula Wine Country (northbound)
- treatment: billboard
- leg: san_diego_ca_us -> riverside_ca_us
- at_mi: 51.6
- spoken: Billboard: Temecula wine country, ahead. Dozens of wineries line Rancho California Road. The driver gets the grape juice.

### Temecula Wine Country (southbound)
- treatment: billboard
- leg: riverside_ca_us -> san_diego_ca_us
- at_mi: 33.2
- spoken: Billboard: Temecula wine country, ahead. Dozens of wineries line Rancho California Road. The driver gets the grape juice.

## Elmer's Bottle Tree Ranch, Oro Grande (old Route 66)

Two acres of more than two hundred metal trees hung with more than a thousand bottles, on the National Trails Highway in Oro Grande between Victorville and Barstow; free, sunrise to sunset, kept up by Elmer Long's son since 2019 (Gray TV Route 66, June 2026; Roadside America). Northbound out of Victorville the turn is already behind the driver, so that leg carries none.

### Elmer's Bottle Tree Ranch (southbound)
- treatment: billboard
- leg: barstow_ca_us -> victorville_ca_us
- at_mi: 17.0
- spoken: Billboard: Elmer's Bottle Tree Ranch, ahead on old Route Sixty-Six in Oro Grande. Two hundred trees grown from pipe and bottles. Free, and no watering needed.

### Elmer's Bottle Tree Ranch (southbound)
- treatment: billboard
- leg: las_vegas_nv_us -> los_angeles_ca_us
- at_mi: 172.8
- spoken: Billboard: Elmer's Bottle Tree Ranch, ahead on old Route Sixty-Six in Oro Grande. Two hundred trees grown from pipe and bottles. Free, and no watering needed.

### Elmer's Bottle Tree Ranch (northbound)
- treatment: billboard
- leg: los_angeles_ca_us -> las_vegas_nv_us
- at_mi: 77.2
- spoken: Billboard: Elmer's Bottle Tree Ranch, ahead on old Route Sixty-Six in Oro Grande. Two hundred trees grown from pipe and bottles. Free, and no watering needed.

## Lassen Volcanic National Park, Manzanita Lake entrance (Highway 44)

The north entrance at Manzanita Lake, where Highways 44 and 89 meet; Lassen Peak erupted in 1914 and 1915, the big blasts on May 19 and 22, 1915 (nps.gov; National Geographic). Highway 89, including its run with 44 from Old Station, is the Volcanic Legacy Scenic Byway, so the westbound sign stands before Old Station.

### Lassen Volcanic National Park (westbound)
- treatment: billboard
- leg: susanville_ca_us -> redding_ca_us
- at_mi: 46.7
- spoken: Billboard: Lassen Volcanic National Park, ahead. Lassen Peak blew its top in nineteen fifteen and still steams in places. Consider it napping.

### Lassen Volcanic National Park (eastbound)
- treatment: billboard
- leg: redding_ca_us -> susanville_ca_us
- at_mi: 37.9
- spoken: Billboard: Lassen Volcanic National Park, ahead. Lassen Peak blew its top in nineteen fifteen and still steams in places. Consider it napping.

## Notes for the owner

Considered and left out:

- **Bagdad Cafe, Newberry Springs.** Its owner, Andrea Pruett, died in
  January 2026 after a fire took her home; whether the cafe stays open is not
  settled.
- **Route 66 Mother Road Museum, Barstow.** Reopened after flood damage but
  open Friday to Sunday only.
- **Winchester Mystery House, San Jose.** No leg passes within two and a half
  miles.
- **Six Flags Discovery Kingdom, Vallejo.** Operating, but Six Flags is
  closing parks; Jelly Belly covers that stretch of I-80.
- **The Tehachapi Loop.** Already a landmark callout on the Bakersfield to
  Barstow leg.
- **Donner Memorial State Park and Manzanar.** No light line fits either.
- **Shasta Dam.** The caverns sign covers the same stretch.
- **Pea Soup Andersen's, Buellton.** Shares its exit with the Solvang sign.
- **Bravo Farms, Kettleman City.** Could not confirm it is open.
- Mono County's 395, I-5 from Route 152 to I-580, Highway 152 east of the
  Santa Clara County line, US 97 north of Weed, and the Del Norte redwoods
  stretch of 101 carry no new sign; see the law note at the top.
