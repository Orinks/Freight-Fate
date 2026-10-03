
# Northeast attractions, both directions -- draft 2026-09-30

DRAFT for owner review. Nothing here is approved.

Forty-three real attractions, 212 signs: New Jersey 8 (31 signs), Delaware 2
(10), Maryland 9 including 7 in Ocean City (33), Rhode Island 2 (12),
Connecticut 7 (50), Massachusetts 11 (52), New Hampshire 4 (24), each
signed in every direction of travel where a leg passes it, except where a
note says why not; Ocean City is signed on the roads into Salisbury at the
owner's request. The District of Columbia gets
none: it has banned new billboards since 1931. Maine and Vermont are out
(statewide bans). Every `leg:` is written the way the driver reads the sign
and `at_mi` counts from that end; `tools/bake_billboards.py` mirrors the
milepost onto a leg stored the other way round and records which way the
billboard faces.

Mileposts come from projecting each attraction onto the legs' dense route
geometry (`data/world_data/us/geometry`) and from the legs' interchange
lists. "Next exit" signs stand between the attraction's exit and the exit
before it; "ahead" signs about eight to fifteen miles out unless a note says
otherwise. Each sits at least 2.2 miles from every other callout heard in
the same direction (rivers, museums, villages within a mile and a half of
the road, same-facing billboards, and the other signs on this sheet).

Where state law limits boards, the signs follow it: Maryland bans
off-premise boards on interstates and expressways, so its signs stand only
on the at-grade stretches of US 50 east of Queenstown and on US 13; New
Jersey's signs avoid the Garden State Parkway and the Turnpike south of
Interchange 6; Rhode Island allows no new boards, so its two attractions
are signed on I-95 in Providence, where existing boards stand; nothing
stands in Maine, Vermont or the District.

## Thomas Edison Center at Menlo Park, Edison, New Jersey (Turnpike Exit 11)

The museum and the Edison Memorial Tower, 37 Christie Street, Edison, on the
site of Edison's Menlo Park laboratory: a 131-foot Art Deco tower (1938)
topped by a bulb just over fourteen feet high, lit at night (LEDs since the
2015 restoration). Museum open Thursday to Saturday, guided tours
(menloparkmuseum.org; Wikipedia, "Thomas Alva Edison Memorial Tower and
Museum"; theclio.com). The museum's own directions from the Turnpike: Exit 11
to the Garden State Parkway, Parkway Exit 132, Route 27. Southbound there is
no clean slot between Exits 12 and 11 (Carteret, Port Reading, the river
cluster and Woodbridge sit in it), so those signs read "ahead", nine miles
out. Northbound signs stand between Exits 10 and 11.

### Thomas Edison Center (southbound)
- treatment: billboard
- leg: newark_nj_us -> trenton_nj_us
- at_mi: 7.0
- spoken: Billboard: The Thomas Edison Center, ahead in Edison. On the site of his lab, a tower wears a fourteen-foot light bulb. It still works.

### Thomas Edison Center (southbound)
- treatment: billboard
- leg: newark_nj_us -> philadelphia_pa_us
- at_mi: 7.0
- spoken: Billboard: The Thomas Edison Center, ahead in Edison. On the site of his lab, a tower wears a fourteen-foot light bulb. It still works.

### Thomas Edison Center (southbound)
- treatment: billboard
- leg: new_york_ny_us -> philadelphia_pa_us
- at_mi: 28.8
- spoken: Billboard: The Thomas Edison Center, ahead in Edison. On the site of his lab, a tower wears a fourteen-foot light bulb. It still works.

### Thomas Edison Center (northbound)
- treatment: billboard
- leg: trenton_nj_us -> newark_nj_us
- at_mi: 40.0
- spoken: Billboard: The Thomas Edison Center, next exit. On the site of his lab, a tower wears a fourteen-foot light bulb. It still works.

### Thomas Edison Center (northbound)
- treatment: billboard
- leg: philadelphia_pa_us -> newark_nj_us
- at_mi: 67.0
- spoken: Billboard: The Thomas Edison Center, next exit. On the site of his lab, a tower wears a fourteen-foot light bulb. It still works.

### Thomas Edison Center (northbound)
- treatment: billboard
- leg: philadelphia_pa_us -> new_york_ny_us
- at_mi: 67.3
- spoken: Billboard: The Thomas Edison Center, next exit. On the site of his lab, a tower wears a fourteen-foot light bulb. It still works.

## Storybook Land, Egg Harbor Township, New Jersey (AC Expressway Exit 12; US 40 at Cardiff)

A family-run children's park of storybook and nursery-rhyme scenes (Mother
Goose, the Three Little Pigs) and rides, 6415 East Black Horse Pike, opened
1955 by John and Esther Fricano (storybookland.com; Wikipedia, "Storybook
Land"). Open in season; the 2026 fall festival runs September 19 to
October 16 (PhillyVoice). Expressway Exit 12 leads to US 40; the US 40 legs
meet the Black Horse Pike at Cardiff, under a mile from the gate. Expressway
signs read "next exit"; US 40 signs read "ahead", three to four miles out.

### Storybook Land (eastbound)
- treatment: billboard
- leg: philadelphia_pa_us -> atlantic_city_nj_us
- at_mi: 48.0
- spoken: Billboard: Storybook Land, next exit. Nursery rhymes you can walk through, family-run since nineteen fifty-five. The big bad wolf is on his lunch break.

### Storybook Land (westbound)
- treatment: billboard
- leg: atlantic_city_nj_us -> philadelphia_pa_us
- at_mi: 11.0
- spoken: Billboard: Storybook Land, next exit. Nursery rhymes you can walk through, family-run since nineteen fifty-five. The big bad wolf is on his lunch break.

### Storybook Land (eastbound)
- treatment: billboard
- leg: vineland_nj_us -> atlantic_city_nj_us
- at_mi: 21.5
- spoken: Billboard: Storybook Land, ahead. Nursery rhymes you can walk through, family-run since nineteen fifty-five. The big bad wolf is on his lunch break.

### Storybook Land (westbound)
- treatment: billboard
- leg: atlantic_city_nj_us -> vineland_nj_us
- at_mi: 8.6
- spoken: Billboard: Storybook Land, ahead. Nursery rhymes you can walk through, family-run since nineteen fifty-five. The big bad wolf is on his lunch break.

## Dover Motor Speedway, Dover, Delaware (Delaware 1 and US 13)

The Monster Mile, 1131 North Dupont Highway: a one-mile concrete oval banked
24 degrees in the turns, opened 1969; it hosted the 2026 NASCAR All-Star Race
and a Craftsman Truck Series race in May 2026 (Wikipedia, "Dover Motor
Speedway"; nascar.com 2026 Truck Series entry list). The speedway sits
between Delaware 1 Exits 104 and 98; all four signs read "ahead". Leaving
Dover northbound it is five miles up the road, so that sign stands two
miles out.

### Dover Motor Speedway (southbound)
- treatment: billboard
- leg: wilmington_de_us -> dover_de_us
- at_mi: 40.4
- spoken: Billboard: Dover Motor Speedway, ahead. The Monster Mile, one mile of steeply banked concrete, racing since nineteen sixty-nine. Your truck is not entered.

### Dover Motor Speedway (southbound)
- treatment: billboard
- leg: wilmington_de_us -> salisbury_md_us
- at_mi: 41.0
- spoken: Billboard: Dover Motor Speedway, ahead. The Monster Mile, one mile of steeply banked concrete, racing since nineteen sixty-nine. Your truck is not entered.

### Dover Motor Speedway (northbound)
- treatment: billboard
- leg: dover_de_us -> wilmington_de_us
- at_mi: 3.0
- spoken: Billboard: Dover Motor Speedway, ahead. The Monster Mile, one mile of steeply banked concrete, racing since nineteen sixty-nine. Your truck is not entered.

### Dover Motor Speedway (northbound)
- treatment: billboard
- leg: salisbury_md_us -> wilmington_de_us
- at_mi: 55.5
- spoken: Billboard: Dover Motor Speedway, ahead. The Monster Mile, one mile of steeply banked concrete, racing since nineteen sixty-nine. Your truck is not entered.

## Old Wye Mill, Wye Mills, Maryland (US 50 at Maryland 213)

900 Wye Mills Road, just off US 50, calling itself the oldest continuously
operated water-powered grist mill in the United States; grain has been
ground on the site since the 1680s (oldwyemill.org; Wikipedia, "Wye Mill";
Bay Journal). Open May 1 to October 31, Wednesday to Sunday. US 50 meets
Maryland 213 there at a signal, so this stretch is not an expressway under
Maryland's sign law (AARoads, "U.S. 50 East - Eastern Maryland"). Eastbound
the slot past Queenstown is two and a half miles out; westbound eight to
ten.

### Old Wye Mill (eastbound)
- treatment: billboard
- leg: washington_dc_us -> salisbury_md_us
- at_mi: 54.5
- spoken: Billboard: Old Wye Mill, ahead. The oldest water-powered grist mill still grinding in the country, open May through October. The river works for free.

### Old Wye Mill (eastbound)
- treatment: billboard
- leg: baltimore_md_us -> salisbury_md_us
- at_mi: 47.8
- spoken: Billboard: Old Wye Mill, ahead. The oldest water-powered grist mill still grinding in the country, open May through October. The river works for free.

### Old Wye Mill (westbound)
- treatment: billboard
- leg: salisbury_md_us -> washington_dc_us
- at_mi: 50.0
- spoken: Billboard: Old Wye Mill, ahead. The oldest water-powered grist mill still grinding in the country, open May through October. The river works for free.

### Old Wye Mill (westbound)
- treatment: billboard
- leg: salisbury_md_us -> baltimore_md_us
- at_mi: 51.6
- spoken: Billboard: Old Wye Mill, ahead. The oldest water-powered grist mill still grinding in the country, open May through October. The river works for free.

## Salisbury Zoo, Salisbury, Maryland

755 South Park Drive, on a branch of the Wicomico River near downtown; free,
open daily 9 to 4:30 except Thanksgiving and Christmas (salisburyzoo.org;
salisbury.md). It sits at the Salisbury node, so it is signed "ahead" on
each leg arriving there, about ten miles out.

### Salisbury Zoo (eastbound)
- treatment: billboard
- leg: washington_dc_us -> salisbury_md_us
- at_mi: 107.5
- spoken: Billboard: The Salisbury Zoo, ahead in Salisbury. Open all year, and admission is free. The animals are the only ones on the clock.

### Salisbury Zoo (eastbound)
- treatment: billboard
- leg: baltimore_md_us -> salisbury_md_us
- at_mi: 100.5
- spoken: Billboard: The Salisbury Zoo, ahead in Salisbury. Open all year, and admission is free. The animals are the only ones on the clock.

### Salisbury Zoo (southbound)
- treatment: billboard
- leg: dover_de_us -> salisbury_md_us
- at_mi: 46.0
- spoken: Billboard: The Salisbury Zoo, ahead in Salisbury. Open all year, and admission is free. The animals are the only ones on the clock.

### Salisbury Zoo (southbound)
- treatment: billboard
- leg: wilmington_de_us -> salisbury_md_us
- at_mi: 97.0
- spoken: Billboard: The Salisbury Zoo, ahead in Salisbury. Open all year, and admission is free. The animals are the only ones on the clock.

### Salisbury Zoo (northbound)
- treatment: billboard
- leg: cape_charles_va_us -> salisbury_md_us
- at_mi: 85.0
- spoken: Billboard: The Salisbury Zoo, ahead in Salisbury. Open all year, and admission is free. The animals are the only ones on the clock.

## Ocean City, Maryland

Added at the owner's request. No leg reaches Ocean City; it is thirty miles
east of the Salisbury node by US 50 (OSRM, router.project-osrm.org: 48.7 km
from the Salisbury node to downtown Ocean City). Assateague Island's
visitor center is 31 miles from the node by US 50, US 113, Maryland 376 and
Maryland 611 (OSRM, 50.6 km), eight miles south of Ocean City. Every sign
faces the direction heading into Salisbury and says where the place is
from Salisbury, so it is true wherever it stands; none says "next exit".
US 50 eastbound carries all seven (six here, the Life-Saving Station Museum
further down), spread from Queenstown to Hebron; each US 13 leg carries
three or four, the Delaware ones standing in Delaware. Assateague stays off
the Cape Charles leg, because from Virginia the island's southern end is
closer than Salisbury. The boardwalk tram is not signed: Ocean City ended
it permanently in October 2025 (The Daily Record). Jolly Roger at the Pier
and Dumser's Dairyland are not signed: neither site confirmed fall 2026
operation.

- The boardwalk: 2.45 miles from the Inlet to 27th Street, begun in 1902 as
  a few blocks of boards that were rolled up and stored (oceancity.com,
  "The History of the Ocean City Boardwalk"; oceancity.org).
- Thrasher's French Fries: since 1929, salt and cider vinegar, no ketchup;
  open daily April 1 to November 1; voted best boardwalk fries in 2026
  (Maryland Coast Dispatch; oceancity.com).
- Fisher's Popcorn: caramel corn from copper kettles since 1937, Talbot
  Street and the boardwalk; won caramel corn in the 2026 Best of the
  Boardwalk vote (oceancity.com; Baltimore Magazine).
- Dolle's Candyland: salt water taffy since 1910, Wicomico Street and the
  boardwalk; open all year (chamber.oceancity.org; Candy Industry); named
  as Fisher's rival in the 2026 vote.
- Trimper Rides: the boardwalk's south end; its Herschell-Spillman
  carousel has turned in the same building since 1912 (Maryland Coast
  Dispatch; National Carousel Association); 2026 season running
  (trimperrides.com).
- Assateague Island National Seashore: wild horses; the Maryland district is
  open all year; the park asks visitors to stay forty feet, a school bus
  length, from the horses, which bite and kick; feeding them is illegal
  (nps.gov/asis).

### Ocean City boardwalk (eastbound)
- treatment: billboard
- leg: washington_dc_us -> salisbury_md_us
- at_mi: 60.0
- spoken: Billboard: Ocean City, thirty miles east of Salisbury on Route Fifty. Two and a half miles of boardwalk. The first one rolled up for storage.

### Thrasher's French Fries (eastbound)
- treatment: billboard
- leg: washington_dc_us -> salisbury_md_us
- at_mi: 66.0
- spoken: Billboard: Thrasher's French Fries, on the Ocean City boardwalk, thirty miles east of Salisbury. Salt and vinegar since nineteen twenty-nine. Do not ask for ketchup.

### Fisher's Popcorn (eastbound)
- treatment: billboard
- leg: washington_dc_us -> salisbury_md_us
- at_mi: 75.6
- spoken: Billboard: Fisher's Popcorn, Ocean City boardwalk, thirty miles east of Salisbury. Caramel corn from copper kettles since nineteen thirty-seven. Your steering wheel will never recover.

### Dolle's Candyland (eastbound)
- treatment: billboard
- leg: washington_dc_us -> salisbury_md_us
- at_mi: 83.0
- spoken: Billboard: Dolle's Candyland, Ocean City boardwalk, thirty miles east of Salisbury. Salt water taffy since nineteen ten. Your fillings have been warned.

### Trimper Rides (eastbound)
- treatment: billboard
- leg: washington_dc_us -> salisbury_md_us
- at_mi: 89.0
- spoken: Billboard: Trimper Rides, on the Ocean City boardwalk, thirty miles east of Salisbury. The carousel has turned since nineteen twelve. Still going nowhere.

### Assateague Island (eastbound)
- treatment: billboard
- leg: washington_dc_us -> salisbury_md_us
- at_mi: 95.0
- spoken: Billboard: Assateague Island, by Ocean City, thirty miles past Salisbury. Wild horses run the beach. Stay a school bus length back. They bite.

### Ocean City boardwalk (eastbound)
- treatment: billboard
- leg: baltimore_md_us -> salisbury_md_us
- at_mi: 53.0
- spoken: Billboard: Ocean City, thirty miles east of Salisbury on Route Fifty. Two and a half miles of boardwalk. The first one rolled up for storage.

### Thrasher's French Fries (eastbound)
- treatment: billboard
- leg: baltimore_md_us -> salisbury_md_us
- at_mi: 58.3
- spoken: Billboard: Thrasher's French Fries, on the Ocean City boardwalk, thirty miles east of Salisbury. Salt and vinegar since nineteen twenty-nine. Do not ask for ketchup.

### Fisher's Popcorn (eastbound)
- treatment: billboard
- leg: baltimore_md_us -> salisbury_md_us
- at_mi: 68.4
- spoken: Billboard: Fisher's Popcorn, Ocean City boardwalk, thirty miles east of Salisbury. Caramel corn from copper kettles since nineteen thirty-seven. Your steering wheel will never recover.

### Dolle's Candyland (eastbound)
- treatment: billboard
- leg: baltimore_md_us -> salisbury_md_us
- at_mi: 76.0
- spoken: Billboard: Dolle's Candyland, Ocean City boardwalk, thirty miles east of Salisbury. Salt water taffy since nineteen ten. Your fillings have been warned.

### Trimper Rides (eastbound)
- treatment: billboard
- leg: baltimore_md_us -> salisbury_md_us
- at_mi: 82.0
- spoken: Billboard: Trimper Rides, on the Ocean City boardwalk, thirty miles east of Salisbury. The carousel has turned since nineteen twelve. Still going nowhere.

### Assateague Island (eastbound)
- treatment: billboard
- leg: baltimore_md_us -> salisbury_md_us
- at_mi: 88.0
- spoken: Billboard: Assateague Island, by Ocean City, thirty miles past Salisbury. Wild horses run the beach. Stay a school bus length back. They bite.

### Ocean City boardwalk (southbound)
- treatment: billboard
- leg: dover_de_us -> salisbury_md_us
- at_mi: 15.0
- spoken: Billboard: Ocean City, thirty miles east of Salisbury on Route Fifty. Two and a half miles of boardwalk. The first one rolled up for storage.

### Thrasher's French Fries (southbound)
- treatment: billboard
- leg: dover_de_us -> salisbury_md_us
- at_mi: 33.0
- spoken: Billboard: Thrasher's French Fries, on the Ocean City boardwalk, thirty miles east of Salisbury. Salt and vinegar since nineteen twenty-nine. Do not ask for ketchup.

### Assateague Island (southbound)
- treatment: billboard
- leg: dover_de_us -> salisbury_md_us
- at_mi: 39.8
- spoken: Billboard: Assateague Island, by Ocean City, thirty miles past Salisbury. Wild horses run the beach. Stay a school bus length back. They bite.

### Fisher's Popcorn (southbound)
- treatment: billboard
- leg: wilmington_de_us -> salisbury_md_us
- at_mi: 66.0
- spoken: Billboard: Fisher's Popcorn, Ocean City boardwalk, thirty miles east of Salisbury. Caramel corn from copper kettles since nineteen thirty-seven. Your steering wheel will never recover.

### Dolle's Candyland (southbound)
- treatment: billboard
- leg: wilmington_de_us -> salisbury_md_us
- at_mi: 84.0
- spoken: Billboard: Dolle's Candyland, Ocean City boardwalk, thirty miles east of Salisbury. Salt water taffy since nineteen ten. Your fillings have been warned.

### Trimper Rides (southbound)
- treatment: billboard
- leg: wilmington_de_us -> salisbury_md_us
- at_mi: 90.8
- spoken: Billboard: Trimper Rides, on the Ocean City boardwalk, thirty miles east of Salisbury. The carousel has turned since nineteen twelve. Still going nowhere.

### Ocean City boardwalk (northbound)
- treatment: billboard
- leg: cape_charles_va_us -> salisbury_md_us
- at_mi: 69.0
- spoken: Billboard: Ocean City, thirty miles east of Salisbury on Route Fifty. Two and a half miles of boardwalk. The first one rolled up for storage.

### Thrasher's French Fries (northbound)
- treatment: billboard
- leg: cape_charles_va_us -> salisbury_md_us
- at_mi: 74.5
- spoken: Billboard: Thrasher's French Fries, on the Ocean City boardwalk, thirty miles east of Salisbury. Salt and vinegar since nineteen twenty-nine. Do not ask for ketchup.

### Dolle's Candyland (northbound)
- treatment: billboard
- leg: cape_charles_va_us -> salisbury_md_us
- at_mi: 89.0
- spoken: Billboard: Dolle's Candyland, Ocean City boardwalk, thirty miles east of Salisbury. Salt water taffy since nineteen ten. Your fillings have been warned.

## The Big Blue Bug, Providence, Rhode Island (I-95)

Nibbles Woodaway, the fiberglass termite on the roof of Big Blue Bug
Solutions, 161 O'Connell Street, beside I-95: nine feet tall, fifty-eight
feet long, built in 1980, named in 1990 (Wikipedia, "Big Blue Bug";
Roadside America). It stands two miles south of the Providence node, so
southbound signs stand right outside the city, a mile and a half to two
miles before it; northbound ones half a mile to five miles out (two of them
sit close so the Roger Williams Park Zoo sign fits). Signed on I-95 only:
the I-195 and US 6 legs pass half a mile or more from it, across the river.

### The Big Blue Bug (northbound)
- treatment: billboard
- leg: newport_ri_us -> providence_ri_us
- at_mi: 31.4
- spoken: Billboard: The Big Blue Bug, ahead. A fifty-eight-foot termite named Nibbles, on a roof by the highway since nineteen eighty. He prefers houses to trucks.

### The Big Blue Bug (northbound)
- treatment: billboard
- leg: new_london_ct_us -> providence_ri_us
- at_mi: 50.5
- spoken: Billboard: The Big Blue Bug, ahead. A fifty-eight-foot termite named Nibbles, on a roof by the highway since nineteen eighty. He prefers houses to trucks.

### The Big Blue Bug (northbound)
- treatment: billboard
- leg: new_york_ny_us -> providence_ri_us
- at_mi: 168.9
- spoken: Billboard: The Big Blue Bug, ahead. A fifty-eight-foot termite named Nibbles, on a roof by the highway since nineteen eighty. He prefers houses to trucks.

### The Big Blue Bug (southbound)
- treatment: billboard
- leg: providence_ri_us -> newport_ri_us
- at_mi: 0.3
- spoken: Billboard: The Big Blue Bug, ahead. A fifty-eight-foot termite named Nibbles, on a roof by the highway since nineteen eighty. He prefers houses to trucks.

### The Big Blue Bug (southbound)
- treatment: billboard
- leg: providence_ri_us -> new_london_ct_us
- at_mi: 0.5
- spoken: Billboard: The Big Blue Bug, ahead. A fifty-eight-foot termite named Nibbles, on a roof by the highway since nineteen eighty. He prefers houses to trucks.

### The Big Blue Bug (southbound)
- treatment: billboard
- leg: providence_ri_us -> new_york_ny_us
- at_mi: 0.5
- spoken: Billboard: The Big Blue Bug, ahead. A fifty-eight-foot termite named Nibbles, on a roof by the highway since nineteen eighty. He prefers houses to trucks.

## Mystic Seaport Museum, Mystic, Connecticut (I-95 Exit 90)

75 Greenmanville Avenue, a mile south of Exit 90 on Connecticut 27; open
daily, the whaleship Charles W. Morgan aboard Friday to Sunday
(mysticseaport.org). The Morgan is the last wooden whaling ship in the
world; her whaling career ran 1841 to 1921, and she has been at Mystic since
1941 (mysticseaport.org; NPS, New Bedford Whaling NHP). Eastbound out of New
London and from New Haven to Newport, the slot between Exits 87 and 90 is
full (Groton, Mystic and Old Mystic), so those two read "ahead", eight to
nine miles out.

### Mystic Seaport (westbound)
- treatment: billboard
- leg: providence_ri_us -> new_london_ct_us
- at_mi: 46.3
- spoken: Billboard: Mystic Seaport, next exit. Home of the last wooden whaling ship in the world. She quit whaling in nineteen twenty-one and still gets visitors.

### Mystic Seaport (westbound)
- treatment: billboard
- leg: providence_ri_us -> new_york_ny_us
- at_mi: 45.9
- spoken: Billboard: Mystic Seaport, next exit. Home of the last wooden whaling ship in the world. She quit whaling in nineteen twenty-one and still gets visitors.

### Mystic Seaport (westbound)
- treatment: billboard
- leg: newport_ri_us -> new_haven_ct_us
- at_mi: 44.3
- spoken: Billboard: Mystic Seaport, next exit. Home of the last wooden whaling ship in the world. She quit whaling in nineteen twenty-one and still gets visitors.

### Mystic Seaport (eastbound)
- treatment: billboard
- leg: new_york_ny_us -> providence_ri_us
- at_mi: 122.4
- spoken: Billboard: Mystic Seaport, next exit. Home of the last wooden whaling ship in the world. She quit whaling in nineteen twenty-one and still gets visitors.

### Mystic Seaport (eastbound)
- treatment: billboard
- leg: new_london_ct_us -> providence_ri_us
- at_mi: 1.0
- spoken: Billboard: Mystic Seaport, ahead. Home of the last wooden whaling ship in the world. She quit whaling in nineteen twenty-one and still gets visitors.

### Mystic Seaport (eastbound)
- treatment: billboard
- leg: new_haven_ct_us -> newport_ri_us
- at_mi: 48.0
- spoken: Billboard: Mystic Seaport, ahead. Home of the last wooden whaling ship in the world. She quit whaling in nineteen twenty-one and still gets visitors.

## Dinosaur State Park, Rocky Hill, Connecticut (I-91 Exit 23)

400 West Street, about a mile from Exit 23; a geodesic dome (1977) over
hundreds of early Jurassic footprints, about 200 million years old; exhibit
center open Tuesday to Sunday (portal.ct.gov/deep; CT state parks "getting
here" page). Exit 23 is missing from every leg's interchange list; it is
placed between Exits 24 and 22 by projecting the park (0.9 miles off the
road). Southbound "next exit" signs stand just past Exit 24, under two
miles out; northbound just past Exit 22. The New York to Boston leg's
interchange list near Hartford is not usable (it lists Bronx exits there),
so its two signs read "ahead", nine to eleven miles out.

### Dinosaur State Park (southbound)
- treatment: billboard
- leg: hartford_ct_us -> new_york_ny_us
- at_mi: 7.0
- spoken: Billboard: Dinosaur State Park, next exit. Hundreds of real dinosaur footprints under a dome, two hundred million years old. Whoever made them never came back.

### Dinosaur State Park (southbound)
- treatment: billboard
- leg: worcester_ma_us -> new_york_ny_us
- at_mi: 69.6
- spoken: Billboard: Dinosaur State Park, next exit. Hundreds of real dinosaur footprints under a dome, two hundred million years old. Whoever made them never came back.

### Dinosaur State Park (southbound)
- treatment: billboard
- leg: boston_ma_us -> new_york_ny_us
- at_mi: 98.0
- spoken: Billboard: Dinosaur State Park, ahead in Rocky Hill. Hundreds of dinosaur footprints under a dome, two hundred million years old. Whoever made them never came back.

### Dinosaur State Park (northbound)
- treatment: billboard
- leg: new_york_ny_us -> hartford_ct_us
- at_mi: 100.5
- spoken: Billboard: Dinosaur State Park, next exit. Hundreds of real dinosaur footprints under a dome, two hundred million years old. Whoever made them never came back.

### Dinosaur State Park (northbound)
- treatment: billboard
- leg: new_york_ny_us -> worcester_ma_us
- at_mi: 101.9
- spoken: Billboard: Dinosaur State Park, next exit. Hundreds of real dinosaur footprints under a dome, two hundred million years old. Whoever made them never came back.

### Dinosaur State Park (northbound)
- treatment: billboard
- leg: new_york_ny_us -> boston_ma_us
- at_mi: 87.0
- spoken: Billboard: Dinosaur State Park, ahead in Rocky Hill. Hundreds of dinosaur footprints under a dome, two hundred million years old. Whoever made them never came back.

## Lake Compounce, Bristol, Connecticut (I-84 Exit 31)

185 Enterprise Drive, Bristol, reached from I-84 Exit 31 (Connecticut 229)
in Southington; opened to the public as a picnic park in 1846, the oldest
continuously operating amusement park in North America; Herschend has owned
it since March 2025; open May to October, with the 2026 fall festival on
select days September 19 to November 1 (Wikipedia, "Lake Compounce";
connecticuthistory.org; thrillzing.com). Exit 31 is missing from the
Bridgeport to Hartford interchange list; it is placed between Exits 30 and
32. The "next exit" slots both ways are taken (Southington, Plantsville and
the Museum of Fire History), so both signs read "ahead", eight to nine
miles out.

### Lake Compounce (eastbound)
- treatment: billboard
- leg: bridgeport_ct_us -> hartford_ct_us
- at_mi: 31.5
- spoken: Billboard: Lake Compounce, ahead near Bristol. Open since eighteen forty-six, the oldest amusement park in North America still running. The rides have been updated.

### Lake Compounce (westbound)
- treatment: billboard
- leg: hartford_ct_us -> bridgeport_ct_us
- at_mi: 9.5
- spoken: Billboard: Lake Compounce, ahead near Bristol. Open since eighteen forty-six, the oldest amusement park in North America still running. The rides have been updated.

## Plymouth Rock, Plymouth, Massachusetts (MA 3; US 44)

Pilgrim Memorial State Park, Water Street on the harbor; the rock sits
under a granite portico built in 1921 (Wikipedia, "Plymouth Rock";
mass.gov, Pilgrim Memorial State Park, sunrise to sunset, portico season
April to November). The MA 3 and US 44 legs list no interchanges, so
all four signs read "ahead", ten to eleven miles out.

### Plymouth Rock (northbound)
- treatment: billboard
- leg: barnstable_ma_us -> boston_ma_us
- at_mi: 21.0
- spoken: Billboard: Plymouth Rock, ahead in Plymouth. It sits under a granite canopy, and it is smaller than you think. So was the Mayflower.

### Plymouth Rock (northbound)
- treatment: billboard
- leg: barnstable_ma_us -> providence_ri_us
- at_mi: 21.0
- spoken: Billboard: Plymouth Rock, ahead in Plymouth. It sits under a granite canopy, and it is smaller than you think. So was the Mayflower.

### Plymouth Rock (southbound)
- treatment: billboard
- leg: boston_ma_us -> barnstable_ma_us
- at_mi: 28.5
- spoken: Billboard: Plymouth Rock, ahead in Plymouth. It sits under a granite canopy, and it is smaller than you think. So was the Mayflower.

### Plymouth Rock (eastbound)
- treatment: billboard
- leg: providence_ri_us -> barnstable_ma_us
- at_mi: 33.0
- spoken: Billboard: Plymouth Rock, ahead in Plymouth. It sits under a granite canopy, and it is smaller than you think. So was the Mayflower.

## Naismith Memorial Basketball Hall of Fame, Springfield, Massachusetts

1000 Hall of Fame Avenue on the riverfront by I-91 (Exit 6 from the north);
open daily April to November, closed Mondays December to March. James
Naismith invented the game in Springfield in December 1891 with two peach
baskets nailed ten feet up (pioneervalley.org; jr.nba.com; NPR). It sits at
the Springfield node, so every leg arriving there gets an "ahead" sign.
Hartford to Springfield has one clean slot, at mile 4, twenty-one miles
out; the copy still holds there.

### Basketball Hall of Fame (northbound)
- treatment: billboard
- leg: hartford_ct_us -> springfield_ma_us
- at_mi: 4.0
- spoken: Billboard: The Basketball Hall of Fame, ahead in Springfield, where the game began with peach baskets. Somebody had to fetch the ball after every score.

### Basketball Hall of Fame (northbound)
- treatment: billboard
- leg: new_haven_ct_us -> springfield_ma_us
- at_mi: 54.0
- spoken: Billboard: The Basketball Hall of Fame, ahead in Springfield, where the game began with peach baskets. Somebody had to fetch the ball after every score.

### Basketball Hall of Fame (southbound)
- treatment: billboard
- leg: keene_nh_us -> springfield_ma_us
- at_mi: 64.2
- spoken: Billboard: The Basketball Hall of Fame, ahead in Springfield, where the game began with peach baskets. Somebody had to fetch the ball after every score.

### Basketball Hall of Fame (eastbound)
- treatment: billboard
- leg: albany_ny_us -> springfield_ma_us
- at_mi: 73.5
- spoken: Billboard: The Basketball Hall of Fame, ahead in Springfield, where the game began with peach baskets. Somebody had to fetch the ball after every score.

### Basketball Hall of Fame (westbound)
- treatment: billboard
- leg: worcester_ma_us -> springfield_ma_us
- at_mi: 43.0
- spoken: Billboard: The Basketball Hall of Fame, ahead in Springfield, where the game began with peach baskets. Somebody had to fetch the ball after every score.

## America's Stonehenge, Salem, New Hampshire (I-93 Exit 3)

105 Haverhill Road; from Exit 3, Route 111 east four and a half miles, then
a mile on; open daily 9 to 5 all year except Thanksgiving and Christmas
(stonehengeusa.com; gonomad.com). Its age and builders are disputed (Fox
News), which the copy says rather than taking a side. Manchester to Hartford
lists no Exit 3; it is placed where the Manchester to Worcester leg, on the
same road, has it.

### America's Stonehenge (northbound)
- treatment: billboard
- leg: boston_ma_us -> manchester_nh_us
- at_mi: 33.2
- spoken: Billboard: America's Stonehenge, next exit, then about five miles east. Stone chambers in the woods. Nobody agrees who built them. The rocks are not talking.

### America's Stonehenge (northbound)
- treatment: billboard
- leg: hartford_ct_us -> manchester_nh_us
- at_mi: 121.0
- spoken: Billboard: America's Stonehenge, next exit, then about five miles east. Stone chambers in the woods. Nobody agrees who built them. The rocks are not talking.

### America's Stonehenge (northbound)
- treatment: billboard
- leg: worcester_ma_us -> manchester_nh_us
- at_mi: 56.8
- spoken: Billboard: America's Stonehenge, next exit, then about five miles east. Stone chambers in the woods. Nobody agrees who built them. The rocks are not talking.

### America's Stonehenge (southbound)
- treatment: billboard
- leg: manchester_nh_us -> boston_ma_us
- at_mi: 14.1
- spoken: Billboard: America's Stonehenge, next exit, then about five miles east. Stone chambers in the woods. Nobody agrees who built them. The rocks are not talking.

### America's Stonehenge (southbound)
- treatment: billboard
- leg: manchester_nh_us -> hartford_ct_us
- at_mi: 14.4
- spoken: Billboard: America's Stonehenge, next exit, then about five miles east. Stone chambers in the woods. Nobody agrees who built them. The rocks are not talking.

### America's Stonehenge (southbound)
- treatment: billboard
- leg: manchester_nh_us -> worcester_ma_us
- at_mi: 14.6
- spoken: Billboard: America's Stonehenge, next exit, then about five miles east. Stone chambers in the woods. Nobody agrees who built them. The rocks are not talking.

## Robert Frost Farm, Derry, New Hampshire (I-93 Exit 4)

122 Rockingham Road (Route 28); from Exit 4, Route 102 east to the Derry
circle, then Route 28 south; a state historic site open May to October
(robertfrostfarm.org; visitnh.gov). Frost lived and farmed there from 1900
to 1911 (Wikipedia, "Robert Frost Farm (Derry, New Hampshire)"). "Two
roads diverged" is from "The Road Not Taken" (1916, public domain); the
copy echoes it, it does not quote it. Manchester to Hartford lists no Exit
5 or 3; they are placed as on the Manchester to Worcester leg.

### Robert Frost Farm (northbound)
- treatment: billboard
- leg: boston_ma_us -> manchester_nh_us
- at_mi: 38.6
- spoken: Billboard: The Robert Frost Farm, next exit. The poet farmed there eleven years. Two roads diverge at the ramp. Take the one to the farm.

### Robert Frost Farm (northbound)
- treatment: billboard
- leg: hartford_ct_us -> manchester_nh_us
- at_mi: 126.4
- spoken: Billboard: The Robert Frost Farm, next exit. The poet farmed there eleven years. Two roads diverge at the ramp. Take the one to the farm.

### Robert Frost Farm (northbound)
- treatment: billboard
- leg: worcester_ma_us -> manchester_nh_us
- at_mi: 62.2
- spoken: Billboard: The Robert Frost Farm, next exit. The poet farmed there eleven years. Two roads diverge at the ramp. Take the one to the farm.

### Robert Frost Farm (southbound)
- treatment: billboard
- leg: manchester_nh_us -> boston_ma_us
- at_mi: 8.7
- spoken: Billboard: The Robert Frost Farm, next exit. The poet farmed there eleven years. Two roads diverge at the ramp. Take the one to the farm.

### Robert Frost Farm (southbound)
- treatment: billboard
- leg: manchester_nh_us -> hartford_ct_us
- at_mi: 9.0
- spoken: Billboard: The Robert Frost Farm, next exit. The poet farmed there eleven years. Two roads diverge at the ramp. Take the one to the farm.

### Robert Frost Farm (southbound)
- treatment: billboard
- leg: manchester_nh_us -> worcester_ma_us
- at_mi: 9.0
- spoken: Billboard: The Robert Frost Farm, next exit. The poet farmed there eleven years. Two roads diverge at the ramp. Take the one to the farm.

## Atlantic City approach: Steel Pier, Absecon Lighthouse, Lucy the Elephant

Three signs on each leg arriving in Atlantic City off the Expressway, US 40
and US 206 (the Garden State Parkway leg carries none). Steel Pier, 1000
Boardwalk: opened June 18, 1898; rides and a 227-foot observation wheel
(2017); pier season April to October, the wheel March to December
(steelpier.com; Wikipedia, "Steel Pier"). Hoodline reported in September 2026
that the pier is for sale; it is still operating. Absecon Lighthouse,
in Atlantic City's north end: New Jersey's tallest, 228 steps, first lit
1857; open Thursday to Monday September to June, daily in summer (NJ DEP;
abseconlighthouse.org). Lucy the Elephant, 9200 Atlantic Avenue, Margate:
six stories, built 1881, a National Historic Landmark, tours inside
(lucytheelephant.org; Wikipedia); 5.8 road miles from the Atlantic City
node (OSRM, 9.36 km). No leg reaches Margate, so Lucy's copy says where she
is from Atlantic City, the way the Ocean City signs do.

### Steel Pier (eastbound)
- treatment: billboard
- leg: philadelphia_pa_us -> atlantic_city_nj_us
- at_mi: 51.0
- spoken: Billboard: Steel Pier, on the Atlantic City boardwalk. A pier over the ocean since eighteen ninety-eight, with rides and a Ferris wheel. Hold your hat.

### Absecon Lighthouse (eastbound)
- treatment: billboard
- leg: philadelphia_pa_us -> atlantic_city_nj_us
- at_mi: 54.9
- spoken: Billboard: Absecon Lighthouse, ahead in Atlantic City. New Jersey's tallest lighthouse, two hundred twenty-eight steps to the top. The elevator is you.

### Lucy the Elephant (eastbound)
- treatment: billboard
- leg: philadelphia_pa_us -> atlantic_city_nj_us
- at_mi: 59.4
- spoken: Billboard: Lucy the Elephant, in Margate, about six miles south of Atlantic City. Six stories of elephant since eighteen eighty-one. You can walk inside her.

### Steel Pier (eastbound)
- treatment: billboard
- leg: vineland_nj_us -> atlantic_city_nj_us
- at_mi: 24.0
- spoken: Billboard: Steel Pier, on the Atlantic City boardwalk. A pier over the ocean since eighteen ninety-eight, with rides and a Ferris wheel. Hold your hat.

### Absecon Lighthouse (eastbound)
- treatment: billboard
- leg: vineland_nj_us -> atlantic_city_nj_us
- at_mi: 28.0
- spoken: Billboard: Absecon Lighthouse, ahead in Atlantic City. New Jersey's tallest lighthouse, two hundred twenty-eight steps to the top. The elevator is you.

### Lucy the Elephant (eastbound)
- treatment: billboard
- leg: vineland_nj_us -> atlantic_city_nj_us
- at_mi: 34.0
- spoken: Billboard: Lucy the Elephant, in Margate, about six miles south of Atlantic City. Six stories of elephant since eighteen eighty-one. You can walk inside her.

### Steel Pier (southbound)
- treatment: billboard
- leg: trenton_nj_us -> atlantic_city_nj_us
- at_mi: 57.0
- spoken: Billboard: Steel Pier, on the Atlantic City boardwalk. A pier over the ocean since eighteen ninety-eight, with rides and a Ferris wheel. Hold your hat.

### Absecon Lighthouse (southbound)
- treatment: billboard
- leg: trenton_nj_us -> atlantic_city_nj_us
- at_mi: 61.0
- spoken: Billboard: Absecon Lighthouse, ahead in Atlantic City. New Jersey's tallest lighthouse, two hundred twenty-eight steps to the top. The elevator is you.

### Lucy the Elephant (southbound)
- treatment: billboard
- leg: trenton_nj_us -> atlantic_city_nj_us
- at_mi: 66.0
- spoken: Billboard: Lucy the Elephant, in Margate, about six miles south of Atlantic City. Six stories of elephant since eighteen eighty-one. You can walk inside her.

## Battleship New Jersey, Camden, New Jersey

100 Clinton Street on the Camden waterfront, across the Delaware from the
Philadelphia node; open daily 10 to 5; the most decorated battleship in US
Navy history, nineteen battle stars; a $24.25 million renovation starts in
mid-2027, so 2026 operation is unaffected (News12 New Jersey, March 2026;
The Sun Newspapers, August 2026). Signed on the four legs that reach
Philadelphia from the New Jersey side. Vineland to Philadelphia's only clean
slot is 21 miles out; Newark to Philadelphia's is 0.6 miles before the ship,
on the approach to the bridge. The Pennsylvania-side I-95 legs (from
Washington and from Trenton) pass across the river and are left unsigned.

### Battleship New Jersey (westbound)
- treatment: billboard
- leg: atlantic_city_nj_us -> philadelphia_pa_us
- at_mi: 49.0
- spoken: Billboard: Battleship New Jersey, ahead on the Camden waterfront. The most decorated battleship in Navy history, open for tours. It parks better than you do.

### Battleship New Jersey (northbound)
- treatment: billboard
- leg: vineland_nj_us -> philadelphia_pa_us
- at_mi: 19.0
- spoken: Billboard: Battleship New Jersey, ahead on the Camden waterfront. The most decorated battleship in Navy history, open for tours. It parks better than you do.

### Battleship New Jersey (southbound)
- treatment: billboard
- leg: newark_nj_us -> philadelphia_pa_us
- at_mi: 81.8
- spoken: Billboard: Battleship New Jersey, ahead on the Camden waterfront. The most decorated battleship in Navy history, open for tours. It parks better than you do.

### Battleship New Jersey (southbound)
- treatment: billboard
- leg: new_york_ny_us -> philadelphia_pa_us
- at_mi: 97.3
- spoken: Billboard: Battleship New Jersey, ahead on the Camden waterfront. The most decorated battleship in Navy history, open for tours. It parks better than you do.

## Grounds For Sculpture, Hamilton, New Jersey

80 Sculptors Way, Hamilton, two miles from the Trenton node: 42 acres, more
than 300 contemporary works, founded on gifts of the Seward Johnson Atelier,
whose life-size bronze figures sit about the grounds; open daily 10 to 5,
timed tickets (groundsforsculpture.org). Signed on the two New Jersey legs
arriving in Trenton; the legs leaving Trenton start past it.

### Grounds For Sculpture (southbound)
- treatment: billboard
- leg: newark_nj_us -> trenton_nj_us
- at_mi: 51.2
- spoken: Billboard: Grounds For Sculpture, ahead in Hamilton. Forty-two acres of art outdoors, and some of the people on the benches are bronze. Say hello anyway.

### Grounds For Sculpture (northbound)
- treatment: billboard
- leg: atlantic_city_nj_us -> trenton_nj_us
- at_mi: 59.0
- spoken: Billboard: Grounds For Sculpture, ahead in Hamilton. Forty-two acres of art outdoors, and some of the people on the benches are bronze. Say hello anyway.

## Red Mill Museum Village, Clinton, New Jersey (I-78)

56 Main Street, Clinton, beside I-78 between Exits 15 and 17: a wool mill
built around 1810, worked until 1928, now a ten-acre village with a quarry,
schoolhouse, log cabin and blacksmith shop; open Wednesday to Sunday
(theredmill.org). The legs list Exit 17 but not 15, and the slots just
before both are taken (Annandale, Clinton, Lebanon, the Readington Museum),
so all six signs read "ahead", four to twelve miles out.

### Red Mill Museum Village (westbound)
- treatment: billboard
- leg: newark_nj_us -> allentown_pa_us
- at_mi: 30.5
- spoken: Billboard: The Red Mill Museum Village, ahead in Clinton. A wool mill from around eighteen ten, with a quarry and a schoolhouse. Still red, still open.

### Red Mill Museum Village (eastbound)
- treatment: billboard
- leg: allentown_pa_us -> newark_nj_us
- at_mi: 35.0
- spoken: Billboard: The Red Mill Museum Village, ahead in Clinton. A wool mill from around eighteen ten, with a quarry and a schoolhouse. Still red, still open.

### Red Mill Museum Village (eastbound)
- treatment: billboard
- leg: allentown_pa_us -> bridgeport_ct_us
- at_mi: 33.0
- spoken: Billboard: The Red Mill Museum Village, ahead in Clinton. A wool mill from around eighteen ten, with a quarry and a schoolhouse. Still red, still open.

### Red Mill Museum Village (westbound)
- treatment: billboard
- leg: bridgeport_ct_us -> allentown_pa_us
- at_mi: 110.5
- spoken: Billboard: The Red Mill Museum Village, ahead in Clinton. A wool mill from around eighteen ten, with a quarry and a schoolhouse. Still red, still open.

### Red Mill Museum Village (eastbound)
- treatment: billboard
- leg: allentown_pa_us -> new_york_ny_us
- at_mi: 35.0
- spoken: Billboard: The Red Mill Museum Village, ahead in Clinton. A wool mill from around eighteen ten, with a quarry and a schoolhouse. Still red, still open.

### Red Mill Museum Village (westbound)
- treatment: billboard
- leg: new_york_ny_us -> allentown_pa_us
- at_mi: 62.0
- spoken: Billboard: The Red Mill Museum Village, ahead in Clinton. A wool mill from around eighteen ten, with a quarry and a schoolhouse. Still red, still open.

## Hagley Museum, Wilmington, Delaware

200 Hagley Creek Road: 235 acres on the Brandywine, the du Pont company's
black powder yard (early 1800s to the 1920s) with daily demonstrations, and
the first du Pont family home (hagley.org). It is two miles from the
Wilmington node, so it is signed on the legs arriving in Wilmington and on
the I-95 through legs, inside Delaware only (Maryland bans boards on I-95).
The Harrisburg leg passes it from the Pennsylvania side and is unsigned.

### Hagley Museum (northbound)
- treatment: billboard
- leg: baltimore_md_us -> wilmington_de_us
- at_mi: 62.9
- spoken: Billboard: Hagley Museum, ahead in Wilmington. The du Pont black powder works on the Brandywine, with demonstrations. They keep the bangs small.

### Hagley Museum (southbound)
- treatment: billboard
- leg: philadelphia_pa_us -> wilmington_de_us
- at_mi: 26.1
- spoken: Billboard: Hagley Museum, ahead in Wilmington. The du Pont black powder works on the Brandywine, with demonstrations. They keep the bangs small.

### Hagley Museum (northbound)
- treatment: billboard
- leg: dover_de_us -> wilmington_de_us
- at_mi: 41.0
- spoken: Billboard: Hagley Museum, ahead in Wilmington. The du Pont black powder works on the Brandywine, with demonstrations. They keep the bangs small.

### Hagley Museum (northbound)
- treatment: billboard
- leg: salisbury_md_us -> wilmington_de_us
- at_mi: 100.4
- spoken: Billboard: Hagley Museum, ahead in Wilmington. The du Pont black powder works on the Brandywine, with demonstrations. They keep the bangs small.

### Hagley Museum (southbound)
- treatment: billboard
- leg: philadelphia_pa_us -> baltimore_md_us
- at_mi: 25.0
- spoken: Billboard: Hagley Museum, ahead in Wilmington. The du Pont black powder works on the Brandywine, with demonstrations. They keep the bangs small.

### Hagley Museum (northbound)
- treatment: billboard
- leg: baltimore_md_us -> philadelphia_pa_us
- at_mi: 72.0
- spoken: Billboard: Hagley Museum, ahead in Wilmington. The du Pont black powder works on the Brandywine, with demonstrations. They keep the bangs small.

## Ocean City, Maryland (continued): Life-Saving Station Museum

813 South Atlantic Avenue at the inlet, the south end of the boardwalk; the
history of Ocean City and the US Life-Saving Service, whose surfmen rowed
out to wrecks; open in 2026 (ocmuseum.org). Added to both US 50 legs and
the Wilmington leg, which carried only three Ocean City signs.

### Life-Saving Station Museum (eastbound)
- treatment: billboard
- leg: washington_dc_us -> salisbury_md_us
- at_mi: 70.0
- spoken: Billboard: The Life-Saving Station Museum, Ocean City inlet, thirty miles east of Salisbury. The surfmen rowed out into storms. You only have to drive.

### Life-Saving Station Museum (eastbound)
- treatment: billboard
- leg: baltimore_md_us -> salisbury_md_us
- at_mi: 63.0
- spoken: Billboard: The Life-Saving Station Museum, Ocean City inlet, thirty miles east of Salisbury. The surfmen rowed out into storms. You only have to drive.

### Life-Saving Station Museum (southbound)
- treatment: billboard
- leg: wilmington_de_us -> salisbury_md_us
- at_mi: 73.8
- spoken: Billboard: The Life-Saving Station Museum, Ocean City inlet, thirty miles east of Salisbury. The surfmen rowed out into storms. You only have to drive.

## Roger Williams Park Zoo, Providence, Rhode Island (I-95 Exit 34)

1000 Elmwood Avenue; open daily, 9 to 4 in fall; it has served the city
for more than 150 years (rwpzoo.org). The legs'
own exit lists name it at Exit 34 (US 1, Elmwood Avenue). On I-95 it and
the Big Blue Bug share the stretch south of downtown; both fit, with the
Bug's northbound signs moved closer to the Bug on two legs. The Newport
legs list no Exit 34, so those two read "ahead".

### Roger Williams Park Zoo (northbound)
- treatment: billboard
- leg: new_london_ct_us -> providence_ri_us
- at_mi: 52.8
- spoken: Billboard: Roger Williams Park Zoo, next exit. Over a hundred and fifty years old, one of the oldest zoos in the country. The animals have tenure.

### Roger Williams Park Zoo (northbound)
- treatment: billboard
- leg: new_york_ny_us -> providence_ri_us
- at_mi: 166.7
- spoken: Billboard: Roger Williams Park Zoo, next exit. Over a hundred and fifty years old, one of the oldest zoos in the country. The animals have tenure.

### Roger Williams Park Zoo (northbound)
- treatment: billboard
- leg: newport_ri_us -> providence_ri_us
- at_mi: 26.5
- spoken: Billboard: Roger Williams Park Zoo, ahead. Over a hundred and fifty years old, one of the oldest zoos in the country. The animals have tenure.

### Roger Williams Park Zoo (southbound)
- treatment: billboard
- leg: providence_ri_us -> new_london_ct_us
- at_mi: 2.8
- spoken: Billboard: Roger Williams Park Zoo, next exit. Over a hundred and fifty years old, one of the oldest zoos in the country. The animals have tenure.

### Roger Williams Park Zoo (southbound)
- treatment: billboard
- leg: providence_ri_us -> new_york_ny_us
- at_mi: 2.8
- spoken: Billboard: Roger Williams Park Zoo, next exit. Over a hundred and fifty years old, one of the oldest zoos in the country. The animals have tenure.

### Roger Williams Park Zoo (southbound)
- treatment: billboard
- leg: providence_ri_us -> newport_ri_us
- at_mi: 2.5
- spoken: Billboard: Roger Williams Park Zoo, ahead. Over a hundred and fifty years old, one of the oldest zoos in the country. The animals have tenure.

## Mark Twain House and Museum, Hartford, Connecticut

351 Farmington Avenue, 0.4 miles off I-84 west of downtown; open daily 9:30 to 5:30, guided
tours only; the Clemens family lived there 1874 to 1891, and he wrote
Huckleberry Finn and Tom Sawyer there (marktwainhouse.org). It is a mile
and a half from the Hartford node, so every leg arriving in Hartford gets
an "ahead in Hartford" sign, as do the two through legs that cross Hartford
(Worcester to New York, New York to Boston) and I-84 westbound out of
Hartford, which passes it at mile 1.7. Springfield to Hartford's only slot
is four miles out; the others eight to fifteen.

### Mark Twain House (eastbound)
- treatment: billboard
- leg: bridgeport_ct_us -> hartford_ct_us
- at_mi: 47.7
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (northbound)
- treatment: billboard
- leg: new_haven_ct_us -> hartford_ct_us
- at_mi: 28.5
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (southbound)
- treatment: billboard
- leg: springfield_ma_us -> hartford_ct_us
- at_mi: 21.6
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (westbound)
- treatment: billboard
- leg: boston_ma_us -> hartford_ct_us
- at_mi: 92.8
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (westbound)
- treatment: billboard
- leg: worcester_ma_us -> hartford_ct_us
- at_mi: 58.0
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (westbound)
- treatment: billboard
- leg: manchester_nh_us -> hartford_ct_us
- at_mi: 125.2
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (southbound)
- treatment: billboard
- leg: albany_ny_us -> hartford_ct_us
- at_mi: 101.7
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (northbound)
- treatment: billboard
- leg: new_york_ny_us -> hartford_ct_us
- at_mi: 102.7
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (westbound)
- treatment: billboard
- leg: providence_ri_us -> hartford_ct_us
- at_mi: 63.0
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (westbound)
- treatment: billboard
- leg: hartford_ct_us -> bridgeport_ct_us
- at_mi: 0.3
- spoken: Billboard: The Mark Twain House, ahead. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (westbound)
- treatment: billboard
- leg: worcester_ma_us -> new_york_ny_us
- at_mi: 55.9
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (eastbound)
- treatment: billboard
- leg: new_york_ny_us -> worcester_ma_us
- at_mi: 104.2
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (northbound)
- treatment: billboard
- leg: new_york_ny_us -> boston_ma_us
- at_mi: 96.5
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

### Mark Twain House (southbound)
- treatment: billboard
- leg: boston_ma_us -> new_york_ny_us
- at_mi: 92.8
- spoken: Billboard: The Mark Twain House, ahead in Hartford. He wrote Huckleberry Finn and Tom Sawyer there. Tours daily. Do not whitewash the fence.

## The Frog Bridge, Willimantic, Connecticut (US 6)

Thread City Crossing, South Street over the Willimantic River: four copper
frogs on concrete thread spools, for the 1754 night the town took a pond
of croaking bullfrogs for an attack; opened 2000 (Wikipedia, "Thread City
Crossing"). US 6 passes a mile and a half north of it at Willimantic.
Eastbound the only slot is fifteen miles out.

### The Frog Bridge (eastbound)
- treatment: billboard
- leg: hartford_ct_us -> providence_ri_us
- at_mi: 12.4
- spoken: Billboard: The Frog Bridge, ahead in Willimantic. Four copper frogs on giant thread spools. In seventeen fifty-four, the town mistook croaking for an invasion.

### The Frog Bridge (westbound)
- treatment: billboard
- leg: providence_ri_us -> hartford_ct_us
- at_mi: 35.1
- spoken: Billboard: The Frog Bridge, ahead in Willimantic. Four copper frogs on giant thread spools. In seventeen fifty-four, the town mistook croaking for an invasion.

## Yankee Candle Village, South Deerfield, Massachusetts (I-91 Exit 35)

The company's flagship store since 1982, on US 5 and Route 10 at the exit
the leg lists as 35 (Whately, Deerfield), with a Bavarian Christmas village
inside (Wikipedia, "Yankee Candle"; the company site blocked the fetch).

### Yankee Candle Village (southbound)
- treatment: billboard
- leg: keene_nh_us -> springfield_ma_us
- at_mi: 46.5
- spoken: Billboard: Yankee Candle Village, next exit. The flagship candle store, with a Christmas village inside all year. Your cab will smell like pine for a week.

### Yankee Candle Village (northbound)
- treatment: billboard
- leg: springfield_ma_us -> keene_nh_us
- at_mi: 26.8
- spoken: Billboard: Yankee Candle Village, next exit. The flagship candle store, with a Christmas village inside all year. Your cab will smell like pine for a week.

## International Volleyball Hall of Fame, Holyoke, Massachusetts

444 Dwight Street, downtown Holyoke, where William G. Morgan devised the
game at the YMCA in 1895 as a gentler indoor sport than basketball; open in
2026 (volleyhall.org). The Basketball Hall of Fame's southbound sign on the
Keene leg moves back to mile 64.2 to make room.

### Volleyball Hall of Fame (southbound)
- treatment: billboard
- leg: keene_nh_us -> springfield_ma_us
- at_mi: 66.5
- spoken: Billboard: The Volleyball Hall of Fame, ahead in Holyoke, where the game was invented in eighteen ninety-five. Basketball was too rough for some people.

### Volleyball Hall of Fame (northbound)
- treatment: billboard
- leg: springfield_ma_us -> keene_nh_us
- at_mi: 7.0
- spoken: Billboard: The Volleyball Hall of Fame, ahead in Holyoke, where the game was invented in eighteen ninety-five. Basketball was too rough for some people.

## Sandwich Glass Museum, Sandwich, Massachusetts

In Sandwich village, a mile off US 6; the
Boston and Sandwich Glass Company's nineteenth-century glass, live
glassblowing hourly; open daily April to December, Wednesday to Sunday in
February and March (sandwichglassmuseum.org).

### Sandwich Glass Museum (westbound)
- treatment: billboard
- leg: barnstable_ma_us -> boston_ma_us
- at_mi: 6.0
- spoken: Billboard: The Sandwich Glass Museum, ahead in Sandwich. Cape Cod glass from the eighteen hundreds, and live glassblowing on the hour. Do not lean on anything.

### Sandwich Glass Museum (westbound)
- treatment: billboard
- leg: barnstable_ma_us -> providence_ri_us
- at_mi: 6.0
- spoken: Billboard: The Sandwich Glass Museum, ahead in Sandwich. Cape Cod glass from the eighteen hundreds, and live glassblowing on the hour. Do not lean on anything.

### Sandwich Glass Museum (southbound)
- treatment: billboard
- leg: boston_ma_us -> barnstable_ma_us
- at_mi: 46.0
- spoken: Billboard: The Sandwich Glass Museum, ahead in Sandwich. Cape Cod glass from the eighteen hundreds, and live glassblowing on the hour. Do not lean on anything.

### Sandwich Glass Museum (eastbound)
- treatment: billboard
- leg: providence_ri_us -> barnstable_ma_us
- at_mi: 51.0
- spoken: Billboard: The Sandwich Glass Museum, ahead in Sandwich. Cape Cod glass from the eighteen hundreds, and live glassblowing on the hour. Do not lean on anything.

## Norman Rockwell Museum, Stockbridge, Massachusetts (Mass Pike)

In Stockbridge, about a mile south of the Pike as the crow flies (dense
geometry) and several miles by road from the nearest exits; the
world's largest collection of original Rockwell art (574 works) and his
studio, moved to the grounds (Wikipedia, "Norman Rockwell Museum"; the
museum's site blocked the fetch). Eastbound, the stretch before the West
Stockbridge exit is either New York or the West Stockbridge callout, so the
eastbound signs stand past it, before the Lee exit. Albany to Springfield
eastbound has no slot there (the Procter Museum and the two Lee callouts
fill it) and is unsigned.

### Norman Rockwell Museum (westbound)
- treatment: billboard
- leg: springfield_ma_us -> albany_ny_us
- at_mi: 38.0
- spoken: Billboard: The Norman Rockwell Museum, ahead in Stockbridge. The world's largest collection of his original art, and his studio. Everyone in the paintings is still smiling.

### Norman Rockwell Museum (eastbound)
- treatment: billboard
- leg: albany_ny_us -> hartford_ct_us
- at_mi: 39.5
- spoken: Billboard: The Norman Rockwell Museum, ahead in Stockbridge. The world's largest collection of his original art, and his studio. Everyone in the paintings is still smiling.

### Norman Rockwell Museum (eastbound)
- treatment: billboard
- leg: albany_ny_us -> worcester_ma_us
- at_mi: 39.7
- spoken: Billboard: The Norman Rockwell Museum, ahead in Stockbridge. The world's largest collection of his original art, and his studio. Everyone in the paintings is still smiling.

### Norman Rockwell Museum (westbound)
- treatment: billboard
- leg: hartford_ct_us -> albany_ny_us
- at_mi: 61.0
- spoken: Billboard: The Norman Rockwell Museum, ahead in Stockbridge. The world's largest collection of his original art, and his studio. Everyone in the paintings is still smiling.

### Norman Rockwell Museum (westbound)
- treatment: billboard
- leg: worcester_ma_us -> albany_ny_us
- at_mi: 82.0
- spoken: Billboard: The Norman Rockwell Museum, ahead in Stockbridge. The world's largest collection of his original art, and his studio. Everyone in the paintings is still smiling.

## Minute Man National Historical Park, Lexington, Massachusetts (I-95)

The Battle Road between Lexington and Concord, where the fighting of April
19, 1775 began; grounds open daily year-round, sunrise to sunset; two
visitor centers (nps.gov/mima). The Manchester to Providence leg runs
I-95 (Route 128) past Lexington, 0.6 miles from the park.

### Minute Man National Historical Park (southbound)
- treatment: billboard
- leg: manchester_nh_us -> providence_ri_us
- at_mi: 40.7
- spoken: Billboard: Minute Man National Historical Park, ahead in Lexington. The Battle Road, where the Revolution began in seventeen seventy-five. Allow more than a minute.

### Minute Man National Historical Park (northbound)
- treatment: billboard
- leg: providence_ri_us -> manchester_nh_us
- at_mi: 48.2
- spoken: Billboard: Minute Man National Historical Park, ahead in Lexington. The Battle Road, where the Revolution began in seventeen seventy-five. Allow more than a minute.

## Lowell National Historical Park, Lowell, Massachusetts (I-495)

The canal-side mill district; the Boott Cotton Mills Museum's weave room
runs working looms; visitor center and Boott museum open daily 9 to 4 from
September 20 to November 28, 2026, weekends in winter (nps.gov/lowe). I-495
passes two miles from it.

### Lowell National Historical Park (southbound)
- treatment: billboard
- leg: manchester_nh_us -> hartford_ct_us
- at_mi: 25.0
- spoken: Billboard: Lowell National Historical Park, ahead in Lowell. Brick mills on the canals, and a weave room with working looms. Bring your loud voice.

### Lowell National Historical Park (southbound)
- treatment: billboard
- leg: manchester_nh_us -> providence_ri_us
- at_mi: 23.0
- spoken: Billboard: Lowell National Historical Park, ahead in Lowell. Brick mills on the canals, and a weave room with working looms. Bring your loud voice.

### Lowell National Historical Park (southbound)
- treatment: billboard
- leg: manchester_nh_us -> worcester_ma_us
- at_mi: 25.0
- spoken: Billboard: Lowell National Historical Park, ahead in Lowell. Brick mills on the canals, and a weave room with working looms. Bring your loud voice.

### Lowell National Historical Park (northbound)
- treatment: billboard
- leg: hartford_ct_us -> manchester_nh_us
- at_mi: 96.0
- spoken: Billboard: Lowell National Historical Park, ahead in Lowell. Brick mills on the canals, and a weave room with working looms. Bring your loud voice.

### Lowell National Historical Park (northbound)
- treatment: billboard
- leg: providence_ri_us -> manchester_nh_us
- at_mi: 58.0
- spoken: Billboard: Lowell National Historical Park, ahead in Lowell. Brick mills on the canals, and a weave room with working looms. Bring your loud voice.

### Lowell National Historical Park (northbound)
- treatment: billboard
- leg: worcester_ma_us -> manchester_nh_us
- at_mi: 32.0
- spoken: Billboard: Lowell National Historical Park, ahead in Lowell. Brick mills on the canals, and a weave room with working looms. Bring your loud voice.

## The Patriots Hall of Fame, Foxborough, Massachusetts (I-95)

The Hall at Patriot Place, beside the stadium on US 1, two miles from
I-95; open daily 10 to 5; all six of the team's Super Bowl trophies on
display (patriotshalloffame.com).

### Patriots Hall of Fame (southbound)
- treatment: billboard
- leg: boston_ma_us -> providence_ri_us
- at_mi: 17.0
- spoken: Billboard: The Patriots Hall of Fame, ahead in Foxborough. All the team's Super Bowl trophies, under one roof. The parking lot is bigger than some towns.

### Patriots Hall of Fame (northbound)
- treatment: billboard
- leg: providence_ri_us -> boston_ma_us
- at_mi: 15.3
- spoken: Billboard: The Patriots Hall of Fame, ahead in Foxborough. All the team's Super Bowl trophies, under one roof. The parking lot is bigger than some towns.

### Patriots Hall of Fame (southbound)
- treatment: billboard
- leg: manchester_nh_us -> providence_ri_us
- at_mi: 68.0
- spoken: Billboard: The Patriots Hall of Fame, ahead in Foxborough. All the team's Super Bowl trophies, under one roof. The parking lot is bigger than some towns.

### Patriots Hall of Fame (northbound)
- treatment: billboard
- leg: providence_ri_us -> manchester_nh_us
- at_mi: 15.7
- spoken: Billboard: The Patriots Hall of Fame, ahead in Foxborough. All the team's Super Bowl trophies, under one roof. The parking lot is bigger than some towns.

## Canobie Lake Park, Salem, New Hampshire (I-93 Exit 2)

85 North Policy Street; opened August 23, 1902 as a trolley park, owned by
three families since 1958; open May to October, Screeemfest October 2 to
31, 2026 (canobie.com; Wikipedia, "Canobie Lake Park"). Southbound signs
stand between Exits 3 and 2. Northbound the Exit 1 milepost is unknown and
the Stonehenge sign holds the stretch after Exit 2, so those read "ahead".

### Canobie Lake Park (northbound)
- treatment: billboard
- leg: boston_ma_us -> manchester_nh_us
- at_mi: 30.0
- spoken: Billboard: Canobie Lake Park, ahead in Salem. A lakeside amusement park since nineteen oh-two, when the trolley brought the crowds. You drove. Close enough.

### Canobie Lake Park (northbound)
- treatment: billboard
- leg: hartford_ct_us -> manchester_nh_us
- at_mi: 117.0
- spoken: Billboard: Canobie Lake Park, ahead in Salem. A lakeside amusement park since nineteen oh-two, when the trolley brought the crowds. You drove. Close enough.

### Canobie Lake Park (northbound)
- treatment: billboard
- leg: worcester_ma_us -> manchester_nh_us
- at_mi: 53.5
- spoken: Billboard: Canobie Lake Park, ahead in Salem. A lakeside amusement park since nineteen oh-two, when the trolley brought the crowds. You drove. Close enough.

### Canobie Lake Park (southbound)
- treatment: billboard
- leg: manchester_nh_us -> boston_ma_us
- at_mi: 18.8
- spoken: Billboard: Canobie Lake Park, next exit. A lakeside amusement park since nineteen oh-two, when the trolley brought the crowds. You drove. Close enough.

### Canobie Lake Park (southbound)
- treatment: billboard
- leg: manchester_nh_us -> hartford_ct_us
- at_mi: 19.2
- spoken: Billboard: Canobie Lake Park, next exit. A lakeside amusement park since nineteen oh-two, when the trolley brought the crowds. You drove. Close enough.

### Canobie Lake Park (southbound)
- treatment: billboard
- leg: manchester_nh_us -> worcester_ma_us
- at_mi: 19.4
- spoken: Billboard: Canobie Lake Park, next exit. A lakeside amusement park since nineteen oh-two, when the trolley brought the crowds. You drove. Close enough.

## Strawbery Banke Museum, Portsmouth, New Hampshire

By the Portsmouth node, about a mile from I-95: nearly ten acres of houses on
their original sites in the Puddle Dock neighborhood, over 350 years of
history; open year-round, Wednesday to Monday in fall 2026
(strawberybanke.org). Signed on legs reaching Portsmouth from New Hampshire
and Massachusetts. Legs arriving from Maine would need the sign in Maine,
which bans billboards, so those directions are unsigned.

### Strawbery Banke Museum (northbound)
- treatment: billboard
- leg: boston_ma_us -> portsmouth_nh_us
- at_mi: 54.0
- spoken: Billboard: Strawbery Banke Museum, ahead in Portsmouth. Houses on their original sites, spanning over three hundred years. They spell strawberry the old way.

### Strawbery Banke Museum (eastbound)
- treatment: billboard
- leg: manchester_nh_us -> portsmouth_nh_us
- at_mi: 36.5
- spoken: Billboard: Strawbery Banke Museum, ahead in Portsmouth. Houses on their original sites, spanning over three hundred years. They spell strawberry the old way.

### Strawbery Banke Museum (northbound)
- treatment: billboard
- leg: boston_ma_us -> portland_me_us
- at_mi: 49.5
- spoken: Billboard: Strawbery Banke Museum, ahead in Portsmouth. Houses on their original sites, spanning over three hundred years. They spell strawberry the old way.

### Strawbery Banke Museum (eastbound)
- treatment: billboard
- leg: manchester_nh_us -> bangor_me_us
- at_mi: 31.9
- spoken: Billboard: Strawbery Banke Museum, ahead in Portsmouth. Houses on their original sites, spanning over three hundred years. They spell strawberry the old way.

### Strawbery Banke Museum (eastbound)
- treatment: billboard
- leg: manchester_nh_us -> portland_me_us
- at_mi: 31.9
- spoken: Billboard: Strawbery Banke Museum, ahead in Portsmouth. Houses on their original sites, spanning over three hundred years. They spell strawberry the old way.

### Strawbery Banke Museum (eastbound)
- treatment: billboard
- leg: manchester_nh_us -> lewiston_me_us
- at_mi: 36.2
- spoken: Billboard: Strawbery Banke Museum, ahead in Portsmouth. Houses on their original sites, spanning over three hundred years. They spell strawberry the old way.

## Old Sturbridge Village, Sturbridge, Massachusetts (I-84 and the Mass Pike)

1 Old Sturbridge Village Road: a re-created 1830s rural New England town
with costumed interpreters, period trades and heritage animals; open
Wednesday to Sunday, 9:30 to 4, fall 2026 (osv.org). It sits by the
I-84 and Mass Pike interchange, so fourteen leg directions pass it, all
signed "ahead in Sturbridge", four to twelve miles out.

### Old Sturbridge Village (westbound)
- treatment: billboard
- leg: boston_ma_us -> hartford_ct_us
- at_mi: 50.4
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (eastbound)
- treatment: billboard
- leg: hartford_ct_us -> boston_ma_us
- at_mi: 34.9
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (westbound)
- treatment: billboard
- leg: worcester_ma_us -> hartford_ct_us
- at_mi: 18.6
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (eastbound)
- treatment: billboard
- leg: hartford_ct_us -> worcester_ma_us
- at_mi: 34.9
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (westbound)
- treatment: billboard
- leg: worcester_ma_us -> new_york_ny_us
- at_mi: 11.9
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (eastbound)
- treatment: billboard
- leg: new_york_ny_us -> worcester_ma_us
- at_mi: 143.0
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (westbound)
- treatment: billboard
- leg: manchester_nh_us -> hartford_ct_us
- at_mi: 89.7
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (eastbound)
- treatment: billboard
- leg: hartford_ct_us -> manchester_nh_us
- at_mi: 34.7
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (eastbound)
- treatment: billboard
- leg: new_york_ny_us -> boston_ma_us
- at_mi: 135.0
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (westbound)
- treatment: billboard
- leg: boston_ma_us -> new_york_ny_us
- at_mi: 50.0
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (eastbound)
- treatment: billboard
- leg: springfield_ma_us -> worcester_ma_us
- at_mi: 21.0
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (westbound)
- treatment: billboard
- leg: worcester_ma_us -> springfield_ma_us
- at_mi: 11.7
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (eastbound)
- treatment: billboard
- leg: albany_ny_us -> worcester_ma_us
- at_mi: 100.0
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

### Old Sturbridge Village (westbound)
- treatment: billboard
- leg: worcester_ma_us -> albany_ny_us
- at_mi: 11.7
- spoken: Billboard: Old Sturbridge Village, ahead in Sturbridge. An eighteen-thirties New England town, run by people in period dress. The oxen are unimpressed by horsepower.

## The Maritime Aquarium, Norwalk, Connecticut (I-95)

10 North Water Street, South Norwalk, a third of a mile off I-95; open daily
10 to 5; more than 6,800 animals, among them sharks in a 110,000-gallon
habitat, harbor seals and sea turtles (maritimeaquarium.org). Fourteen leg
directions pass it; each sign reads "ahead in Norwalk", seven to eleven
miles out (the I-95 villages leave no closer slots).

### Maritime Aquarium (southbound)
- treatment: billboard
- leg: hartford_ct_us -> new_york_ny_us
- at_mi: 62.5
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (northbound)
- treatment: billboard
- leg: new_york_ny_us -> hartford_ct_us
- at_mi: 30.5
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (southbound)
- treatment: billboard
- leg: new_haven_ct_us -> new_york_ny_us
- at_mi: 24.2
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (northbound)
- treatment: billboard
- leg: new_york_ny_us -> new_haven_ct_us
- at_mi: 30.5
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (southbound)
- treatment: billboard
- leg: worcester_ma_us -> new_york_ny_us
- at_mi: 132.1
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (northbound)
- treatment: billboard
- leg: new_york_ny_us -> worcester_ma_us
- at_mi: 30.5
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (northbound)
- treatment: billboard
- leg: new_york_ny_us -> boston_ma_us
- at_mi: 29.0
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (southbound)
- treatment: billboard
- leg: boston_ma_us -> new_york_ny_us
- at_mi: 157.7
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (northbound)
- treatment: billboard
- leg: new_york_ny_us -> bridgeport_ct_us
- at_mi: 28.6
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (southbound)
- treatment: billboard
- leg: bridgeport_ct_us -> new_york_ny_us
- at_mi: 3.2
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (northbound)
- treatment: billboard
- leg: allentown_pa_us -> bridgeport_ct_us
- at_mi: 135.2
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (southbound)
- treatment: billboard
- leg: bridgeport_ct_us -> allentown_pa_us
- at_mi: 9.4
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (southbound)
- treatment: billboard
- leg: providence_ri_us -> new_york_ny_us
- at_mi: 130.4
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

### Maritime Aquarium (northbound)
- treatment: billboard
- leg: new_york_ny_us -> providence_ri_us
- at_mi: 30.5
- spoken: Billboard: The Maritime Aquarium, ahead in Norwalk. Sharks, harbor seals and sea turtles, open daily. The seals work for fish and seem happy about it.

## New England Air Museum, Windsor Locks, Connecticut

36 Perimeter Road at Bradley International Airport; open every day 9 to 4;
more than 100 aircraft, from early flying machines to supersonic jets
(neam.org). About three and a half miles off I-91, signed "ahead at Bradley
Airport". Springfield to Hartford's slot is sixteen miles out.

### New England Air Museum (southbound)
- treatment: billboard
- leg: springfield_ma_us -> hartford_ct_us
- at_mi: 1.0
- spoken: Billboard: The New England Air Museum, ahead at Bradley Airport. Over a hundred aircraft, from early flying machines to supersonic jets. All safely parked.

### New England Air Museum (northbound)
- treatment: billboard
- leg: hartford_ct_us -> springfield_ma_us
- at_mi: 1.8
- spoken: Billboard: The New England Air Museum, ahead at Bradley Airport. Over a hundred aircraft, from early flying machines to supersonic jets. All safely parked.

### New England Air Museum (southbound)
- treatment: billboard
- leg: springfield_ma_us -> new_haven_ct_us
- at_mi: 8.9
- spoken: Billboard: The New England Air Museum, ahead at Bradley Airport. Over a hundred aircraft, from early flying machines to supersonic jets. All safely parked.

### New England Air Museum (northbound)
- treatment: billboard
- leg: new_haven_ct_us -> springfield_ma_us
- at_mi: 38.1
- spoken: Billboard: The New England Air Museum, ahead at Bradley Airport. Over a hundred aircraft, from early flying machines to supersonic jets. All safely parked.

### New England Air Museum (southbound)
- treatment: billboard
- leg: albany_ny_us -> hartford_ct_us
- at_mi: 88.0
- spoken: Billboard: The New England Air Museum, ahead at Bradley Airport. Over a hundred aircraft, from early flying machines to supersonic jets. All safely parked.

### New England Air Museum (northbound)
- treatment: billboard
- leg: hartford_ct_us -> albany_ny_us
- at_mi: 4.5
- spoken: Billboard: The New England Air Museum, ahead at Bradley Airport. Over a hundred aircraft, from early flying machines to supersonic jets. All safely parked.

## Adams National Historical Park, Quincy, Massachusetts

The birthplaces of John Adams and John Quincy Adams and the family's later
home; visitor center open Wednesday to Sunday through October 31, 2026,
grounds daily (nps.gov/adam). The MA 3 and I-93 legs pass Quincy about a
mile from it.

### Adams National Historical Park (northbound)
- treatment: billboard
- leg: barnstable_ma_us -> boston_ma_us
- at_mi: 52.0
- spoken: Billboard: Adams National Historical Park, ahead in Quincy. Two presidents were born there, in houses side by side. Neither had far to commute.

### Adams National Historical Park (southbound)
- treatment: billboard
- leg: boston_ma_us -> barnstable_ma_us
- at_mi: 3.0
- spoken: Billboard: Adams National Historical Park, ahead in Quincy. Two presidents were born there, in houses side by side. Neither had far to commute.

### Adams National Historical Park (southbound)
- treatment: billboard
- leg: boston_ma_us -> providence_ri_us
- at_mi: 3.0
- spoken: Billboard: Adams National Historical Park, ahead in Quincy. Two presidents were born there, in houses side by side. Neither had far to commute.

### Adams National Historical Park (northbound)
- treatment: billboard
- leg: providence_ri_us -> boston_ma_us
- at_mi: 32.0
- spoken: Billboard: Adams National Historical Park, ahead in Quincy. Two presidents were born there, in houses side by side. Neither had far to commute.

## Notes for the owner

A dry run of `tools/bake_billboards.py` on this sheet resolves every leg and
bakes all 212 signs (no `--write`). A spacing check against the current legs
found nothing within 2.2 miles of any sign in its direction: landmarks
without `directions`, same-facing billboards, villages within 1.5 miles of
the road, and every other sign on this sheet. Every line starts
"Billboard: ", has no digits, and runs 21 to 26 words. The jokes are
original; none quotes real ad copy. The other three sheets being drafted
today were not checked against this one; a combined spacing pass before
baking would catch any shared leg (Philadelphia, Albany, New York and the
Maine legs are the likely ones).

Billboard law, by jurisdiction:

- District of Columbia: Congress banned new billboards in the District in
  1931; only grandfathered ones remain (Scenic America, "A History of
  Billboards in Washington DC"). Effectively a ban, so nothing is signed in
  DC. Its legs reach Maryland within six miles, and the Maryland signs on
  them follow Maryland law.
- Maryland: the State Highway Administration says state law prohibits
  off-premise outdoor advertising along interstates and other expressways
  (roads.maryland.gov, Outdoor Advertising; Transportation Article,
  subtitle 7); other state and US highways need an SHA permit. So no
  Maryland sign stands on I-95, I-70, I-68, I-83, I-270 or the US 50 freeway
  west of Queenstown. US 50 is at-grade with signals at Maryland 213, Wye
  Mills (AARoads), and Ocean City's own boards line it. An old statute
  (Archives of Maryland) bars boards within 500 feet of US 50 from the
  Herring Creek bridge into Ocean City; no sign here is near that stretch.
  US 15 north of Frederick is a national scenic byway (no new boards under
  23 U.S.C. 131(s)), so nothing was placed on it.
- New Jersey: NJDOT permits boards under N.J.A.C. 16:41C. The Turnpike
  Authority allows boards on its own right of way only from the Turnpike's
  north end to Interchange 6, and none on any part of the Garden State
  Parkway's right of way (NJTA Billboard Program Policy; NJDOT's Parkway
  history: the road was built without billboards). No sign stands on the two
  Parkway legs; the Turnpike signs are all north of Exit 6.
- Delaware: 17 Del. C. ch. 11 permits boards in zoned commercial and
  industrial areas along interstates and primaries, with spacing rules.
- Rhode Island: R.I. Gen. Laws 24-10.1 allows no new off-premise boards;
  existing ones may stay and relocate. Existing boards stand along I-95 in
  Providence and Cranston, so the Bug and the Zoo are signed only there.
  The Newport mansions were left out for this reason: their approach roads
  are rural and some are scenic highways.
- Connecticut: about 988 permitted structures on federal-aid highways
  (EWG state summary); allowed.
- Massachusetts: 700 CMR 3.00, about 3,744 permits (MassDOT); allowed.
- New Hampshire: RSA 236:69 to 88 and Tra 600 rules; allowed in commercial
  and industrial areas.
- Maine and Vermont: statewide bans. Signs that would have had to stand in
  either were not placed (see Strawbery Banke, and the Keene to Springfield
  leg, whose Vermont stretch carries nothing).

Unsure, per attraction (sources are in each section above):

- Edison Center: museum open Thursday to Saturday only; the tower and
  grounds are visible every day. Northbound "next exit" is Exit 11, the
  museum's own route via the Parkway.
- Storybook Land: seasonal (spring, fall weekends, the Christmas show); the
  sign stays up year-round, as real ones do.
- Steel Pier: listed for sale in September 2026 (Hoodline). Operating now;
  worth a look before the next release.
- Lucy the Elephant: her website says she is open; an interior restoration
  funded in 2025 and 2026 may close the inside for a time. Not on any leg;
  signed like Ocean City.
- Battleship New Jersey: the Newark to Philadelphia sign is only 0.6 miles
  before the ship; the Vineland one is 21 miles out. The two Pennsylvania-side
  I-95 legs pass it across the river and are unsigned.
- Grounds For Sculpture, Hagley, the Basketball Hall of Fame, Twain, Salisbury
  Zoo and Strawbery Banke sit within two miles of a city node; they are
  signed "ahead in" that city on arriving legs, as Ruby Falls was.
- Hagley: the Harrisburg legs pass it from Pennsylvania and are unsigned.
- Dover Motor Speedway: "racing since 1969" stays true whatever NASCAR's
  schedule does; the Truck Series race and All-Star Race are 2026 facts kept
  out of the copy.
- Old Wye Mill, Plymouth Rock's portico, Canobie, Lake Compounce, the Frost
  Farm, Thrasher's and Trimper Rides are seasonal. Trimper Rides' site calls
  Labor Day the end of its season; its carousel building runs some fall
  weekends. All were operating in 2026.
- Ocean City: every sign says "thirty miles east of Salisbury", true wherever
  it stands (OSRM: 30.2 miles node to downtown). The Delaware US 13 signs
  stand in Delaware, which allows them.
- Big Blue Bug: two northbound signs moved closer to it (0.6 and 1.8 miles
  out) so the Zoo's "next exit" signs fit.
- Dinosaur State Park and Lake Compounce: their exits (23 and 31) are missing
  from the legs' interchange lists and are placed between the exits on
  either side.
- Yankee Candle and the Norman Rockwell Museum: the official sites refused
  the fetch; open status and facts are from Wikipedia, which reports no
  closure.
- Norman Rockwell Museum: Albany to Springfield eastbound is unsigned; the
  only Massachusetts stretch before the Lee exit is filled by the Procter
  Museum and the Lee callouts. The other two eastbound signs stand past
  the West Stockbridge exit, before Lee.
- Mark Twain House, Old Sturbridge Village and the Maritime Aquarium carry
  fourteen signs each, the heaviest sets here. Trimming them to the through
  roads would be reasonable.
- America's Stonehenge: its age and builders are disputed; the copy says
  nobody agrees.
- Volleyball Hall of Fame: "ahead in Holyoke" rather than "next exit",
  because the leg's US 202 exit could not be confirmed as the museum's own.
- Web search ran out partway through (the session's 200-search budget).
  Everything after that was verified on the attraction's own site or the
  NPS, with Wikipedia only where the site refused the fetch.

Dropped:

- American Dream (Meadowlands): southbound, no free slot in New Jersey
  before its exit; the stretch is all villages.
- Hampton Beach: no free slot on either I-95 direction near Hampton
  (Hampton, Hampton Falls, North Hampton, Seabrook, the river cluster).
- Beardsley Zoo, Bridgeport: seven of seventeen leg directions have no slot.
- Six Flags New England: no slot on Springfield to Hartford either way.
- USS Nautilus, Groton: eastbound out of New London its only slot is Mystic
  Seaport's; the better-known Seaport keeps it.
- Mystic Aquarium: same exit as Mystic Seaport.
- Historic Deerfield and Magic Wings: same exit as Yankee Candle.
- Dr. Seuss museum, Springfield; Wadsworth Atheneum, Hartford; USS Albacore,
  Portsmouth: same city stretch as the Basketball Hall of Fame, Twain and
  Strawbery Banke.
- Ward Museum of Wildfowl Art, Salisbury: closed (wardfdn.org).
- Delmarva Discovery Museum, Pocomoke City: closed March 20, 2026.
- Ocean City Boardwalk Tram: ended permanently, October 2025.
- Jolly Roger at the Pier, Dumser's Dairyland, Slater Mill, Essex Steam
  Train, Florence Griswold Museum, Choptank River Lighthouse, American
  Independence Museum, Kowloon (Saugus), Plimoth Patuxet, Mount Kearsarge
  Indian Museum: fall 2026 status or the copy's facts could not be
  confirmed after search ran out.
- Air Mobility Command Museum, Dover: three to four miles off every leg,
  reached only by leaving the route; Fort Delaware (ferry, four miles off);
  Blackwater refuge, Battleship Cove, Liberty State Park, Batsto, Kent
  Falls, Miller State Park, Hancock Shaker Village: no leg within four
  miles.
- Harriet Tubman Underground Railroad sites, Cambridge: a joke billboard
  does not fit; a respectful landmark callout might, if the owner wants one.
- Nothing here duplicates a pool line or placed sign: the Boston (Willis
  Brothers) and New Jersey (Elle King) pool lines, Pizza and Yale, and
  "Boston, Where It Started" are untouched, and the standing exclusions in
  RUTH-CATALOG.md name nothing in these states.

Found along the way (data, not this sheet):

- Several legs carry landmarks, checkpoints or interchanges from a different
  route than their geometry: Providence to New York lists I-395 towns
  (Plainfield, Norwich, Montville) while its exits are coastal I-95;
  Hartford to New York lists I-84 villages (Plainville, Plantsville,
  Milldale) while it runs I-91; New York to Boston lists Bronx exits near
  Hartford; Albany to Hartford lists a New York Route 43 exit in the
  Berkshires.
- Providence to New London's `state_miles` puts the Connecticut line at
  mile 48.4; its own exits are in Connecticut from mile 38.6.
- The corridor pools still read Sheetz and Wawa lines in Maryland, where
  off-premise boards are banned on interstates. A Maryland interstate gate
  like the Maine and Vermont one would fix it.
