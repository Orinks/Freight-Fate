
# South Florida attractions, both directions -- 2026-09-30

DRAFT for owner approval. Tampa Bay and everything south: Lakeland, Sarasota,
Fort Myers, Naples, Lake Okeechobee, the Palm Beaches, the Treasure Coast,
Fort Lauderdale, Miami. No new signs in the Keys or on Alligator Alley (see
the law note at the end).

Every `leg:` is written the way the driver reads the sign and `at_mi` counts
from that end; `tools/bake_billboards.py` mirrors the milepost onto a leg
stored the other way round and records which way the billboard faces.

Mileposts come from each leg's interchange list (the attraction's exit and
the one before it) and, where a leg has none (US 1 to the Keys, State Road
60, US 17, US 27), from its checkpoints and its dense route geometry, which
agrees with the checkpoints to a few tenths of a mile on every leg used here
except Tampa to Miami, where it runs about five miles short in the middle and
was corrected against the Clewiston and South Bay checkpoints. "Next exit"
signs stand between the attraction's exit and the one before it; "ahead"
signs stand roughly five to thirteen miles out. Each sits at least 2.2 miles
from every other callout heard in the same direction, including every other
sign on this sheet.

Ten signs reuse approved copy word for word on legs and directions that had
none: Tampa's Cigar City, Fort Myers' Edison and Ford, Palm Beach's
Grapefruit League, and Solomon's Castle. They are longer than the new lines
because they are the existing text.

## Zoo Miami (Homestead Extension of Florida's Turnpike, Southwest 152nd Street)

Florida's largest zoo and the only tropical zoo in the continental United
States, 12400 Southwest 152nd Street, about a mile off the Miami to Key West
leg's route on the Turnpike's Homestead Extension (Wikipedia, "Zoo Miami").

### Zoo Miami (southbound)
- treatment: billboard
- leg: miami_fl_us -> key_west_fl_us
- at_mi: 9.6
- spoken: Billboard: Zoo Miami, ahead. Florida's biggest zoo, and the only tropical zoo in the continental United States. The animals take the heat better than you.

### Zoo Miami (northbound)
- treatment: billboard
- leg: key_west_fl_us -> miami_fl_us
- at_mi: 139.4
- spoken: Billboard: Zoo Miami, ahead. Florida's biggest zoo, and the only tropical zoo in the continental United States. The animals take the heat better than you.

## Monkey Jungle, Southwest 216th Street

Thirty acres of South Florida forest where the monkeys roam and the visitors
walk through enclosed paths, open to the public since 1935, 14805 Southwest
216th Street, about three and a half miles west of the route
(monkeyjungle.com). Southbound only: northbound, every slot before it is
inside a mile and a half of a village callout or already taken by Coral
Castle.

### Monkey Jungle (southbound)
- treatment: billboard
- leg: miami_fl_us -> key_west_fl_us
- at_mi: 14.6
- spoken: Billboard: Monkey Jungle, ahead. Since nineteen thirty-five, the monkeys have run loose and the visitors have walked through cages. Try to look interesting.

## Coral Castle, Homestead (Turnpike Exit 5, US 1 at Southwest 286th Street)

Edward Leedskalnin's coral-rock castle, 28655 South Dixie Highway, open
daily (coralcastle.com). He built it by himself from about 1,100 tons of
oolite limestone over some twenty-eight years; the nine-ton gate turned on a
truck bearing until it rusted and stuck in 1986 (Wikipedia, "Coral Castle").

### Coral Castle (southbound)
- treatment: billboard
- leg: miami_fl_us -> key_west_fl_us
- at_mi: 17.1
- spoken: Billboard: Coral Castle, ahead in Homestead. One man built it alone from eleven hundred tons of stone, and hung the nine-ton gate on a truck bearing.

### Coral Castle (northbound)
- treatment: billboard
- leg: key_west_fl_us -> miami_fl_us
- at_mi: 127.8
- spoken: Billboard: Coral Castle, ahead in Homestead. One man built it alone from eleven hundred tons of stone, and hung the nine-ton gate on a truck bearing.

## Vizcaya Museum and Gardens, Miami (US 1 and the south end of I-95)

James Deering's Italian Renaissance-style bayfront villa, 3251 South Miami
Avenue, first lived in on Christmas Day 1916; Deering's money was the
Deering McCormick-International Harvester farm-machinery fortune (Wikipedia,
"Vizcaya Museum and Gardens"). Open daily except Tuesday
(vizcaya.org). It stands about two miles south of downtown, where I-95 ends,
so the southbound signs stand on the three legs that come into Miami on I-95,
and the northbound one on the road up from the Keys.

### Vizcaya (northbound)
- treatment: billboard
- leg: key_west_fl_us -> miami_fl_us
- at_mi: 149.4
- spoken: Billboard: Vizcaya, ahead in Miami. A farm-equipment fortune built this Italian-style villa on Biscayne Bay. Somewhere, a combine is very proud.

### Vizcaya (southbound)
- treatment: billboard
- leg: west_palm_beach_fl_us -> miami_fl_us
- at_mi: 66.5
- spoken: Billboard: Vizcaya, ahead in Miami. A farm-equipment fortune built this Italian-style villa on Biscayne Bay. Somewhere, a combine is very proud.

### Vizcaya (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 341.5
- spoken: Billboard: Vizcaya, ahead in Miami. A farm-equipment fortune built this Italian-style villa on Biscayne Bay. Somewhere, a combine is very proud.

### Vizcaya (southbound)
- treatment: billboard
- leg: port_saint_lucie_fl_us -> miami_fl_us
- at_mi: 110.5
- spoken: Billboard: Vizcaya, ahead in Miami. A farm-equipment fortune built this Italian-style villa on Biscayne Bay. Somewhere, a combine is very proud.

## Seminole Hard Rock's Guitar Hotel, Hollywood (Turnpike at Griffin Road; I-95 Exit 22)

The 450-foot hotel tower built to look like a guitar, opened October 2019,
1 Seminole Way, beside Florida's Turnpike and visible from it (Wikipedia,
"Seminole Hard Rock Hotel & Casino Hollywood"). The casino's own directions
use the Turnpike's Griffin Road exit and I-95's Stirling Road exit. On I-95
it is three miles west of the road, so those signs read "ahead".

### Guitar Hotel (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 313.5
- spoken: Billboard: Seminole Hard Rock's Guitar Hotel, ahead in Hollywood. Four hundred fifty feet tall, shaped like a guitar, and never once out of tune.

### Guitar Hotel (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 11.7
- spoken: Billboard: Seminole Hard Rock's Guitar Hotel, ahead in Hollywood. Four hundred fifty feet tall, shaped like a guitar, and never once out of tune.

### Guitar Hotel (southbound)
- treatment: billboard
- leg: port_saint_lucie_fl_us -> miami_fl_us
- at_mi: 82.5
- spoken: Billboard: Seminole Hard Rock's Guitar Hotel, ahead in Hollywood. Four hundred fifty feet tall, shaped like a guitar, and never once out of tune.

### Guitar Hotel (northbound)
- treatment: billboard
- leg: miami_fl_us -> port_saint_lucie_fl_us
- at_mi: 11.7
- spoken: Billboard: Seminole Hard Rock's Guitar Hotel, ahead in Hollywood. Four hundred fifty feet tall, shaped like a guitar, and never once out of tune.

### Guitar Hotel (southbound)
- treatment: billboard
- leg: west_palm_beach_fl_us -> miami_fl_us
- at_mi: 37.0
- spoken: Billboard: Seminole Hard Rock's Guitar Hotel, ahead in Hollywood. Four hundred fifty feet tall, shaped like a guitar, and never once out of tune.

### Guitar Hotel (northbound)
- treatment: billboard
- leg: miami_fl_us -> west_palm_beach_fl_us
- at_mi: 13.0
- spoken: Billboard: Seminole Hard Rock's Guitar Hotel, ahead in Hollywood. Four hundred fifty feet tall, shaped like a guitar, and never once out of tune.

## Butterfly World, Coconut Creek (Turnpike Exit 69, Sample Road)

Butterfly World in Tradewinds Park, 3600 West Sample Road, a quarter mile
from the Turnpike's Sample Road exit; twenty thousand butterflies and birds
in open-air aviaries (butterflyworld.com; directions from the park). Open
daily. Northbound, the slot between Exits 66 and 69 is inside the Coconut
Creek callout, so those signs stand before Exit 66 and read "ahead".

### Butterfly World (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 306.5
- spoken: Billboard: Butterfly World, next exit. Twenty thousand butterflies and birds in open-air aviaries. Please leave the air horn in the truck.

### Butterfly World (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 32.8
- spoken: Billboard: Butterfly World, ahead in Coconut Creek. Twenty thousand butterflies and birds in open-air aviaries. Please leave the air horn in the truck.

### Butterfly World (southbound)
- treatment: billboard
- leg: port_saint_lucie_fl_us -> miami_fl_us
- at_mi: 75.7
- spoken: Billboard: Butterfly World, next exit. Twenty thousand butterflies and birds in open-air aviaries. Please leave the air horn in the truck.

### Butterfly World (northbound)
- treatment: billboard
- leg: miami_fl_us -> port_saint_lucie_fl_us
- at_mi: 32.7
- spoken: Billboard: Butterfly World, ahead in Coconut Creek. Twenty thousand butterflies and birds in open-air aviaries. Please leave the air horn in the truck.

## Morikami Museum and Japanese Gardens, Delray Beach (Turnpike, between Exits 75 and 81)

Sixteen acres of Japanese gardens and a bonsai collection on land George
Morikami, the last farmer of the Yamato Colony, gave to Palm Beach County;
open since 1977, 4000 Morikami Park Road, about a mile east of the Turnpike
(morikami.org; Frommer's; The Cultural Landscape Foundation). The copy
names the place and the gardens and keeps the joke on trees and trucks.

### Morikami Gardens (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 293.0
- spoken: Billboard: The Morikami Japanese Gardens, ahead in Delray Beach. Sixteen acres of gardens, with bonsai older than your truck and shorter than your tires.

### Morikami Gardens (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 41.0
- spoken: Billboard: The Morikami Japanese Gardens, ahead in Delray Beach. Sixteen acres of gardens, with bonsai older than your truck and shorter than your tires.

### Morikami Gardens (southbound)
- treatment: billboard
- leg: port_saint_lucie_fl_us -> miami_fl_us
- at_mi: 62.2
- spoken: Billboard: The Morikami Japanese Gardens, ahead in Delray Beach. Sixteen acres of gardens, with bonsai older than your truck and shorter than your tires.

### Morikami Gardens (northbound)
- treatment: billboard
- leg: miami_fl_us -> port_saint_lucie_fl_us
- at_mi: 41.0
- spoken: Billboard: The Morikami Japanese Gardens, ahead in Delray Beach. Sixteen acres of gardens, with bonsai older than your truck and shorter than your tires.

### Morikami Gardens (southbound)
- treatment: billboard
- leg: port_saint_lucie_fl_us -> coral_springs_fl_us
- at_mi: 60.0
- spoken: Billboard: The Morikami Japanese Gardens, ahead in Delray Beach. Sixteen acres of gardens, with bonsai older than your truck and shorter than your tires.

### Morikami Gardens (northbound)
- treatment: billboard
- leg: coral_springs_fl_us -> port_saint_lucie_fl_us
- at_mi: 10.0
- spoken: Billboard: The Morikami Japanese Gardens, ahead in Delray Beach. Sixteen acres of gardens, with bonsai older than your truck and shorter than your tires.

### Morikami Gardens (northbound)
- treatment: billboard
- leg: coral_springs_fl_us -> palm_bay_fl_us
- at_mi: 11.5
- spoken: Billboard: The Morikami Japanese Gardens, ahead in Delray Beach. Sixteen acres of gardens, with bonsai older than your truck and shorter than your tires.

## Loggerhead Marinelife Center, Juno Beach (I-95 Exit 83, Donald Ross Road)

A sea turtle hospital and marine center, free to visit, open daily, 14200
US Highway 1, about four miles east of I-95 Exit 83 (marinelife.org; front
entrance under renovation from September 21, north entrance open).

### Loggerhead Marinelife Center (northbound)
- treatment: billboard
- leg: west_palm_beach_fl_us -> palm_bay_fl_us
- at_mi: 13.6
- spoken: Billboard: Loggerhead Marinelife Center, next exit, then four miles east. Free to visit, with a hospital for sea turtles. Nobody honks at the patients.

### Loggerhead Marinelife Center (southbound)
- treatment: billboard
- leg: palm_bay_fl_us -> west_palm_beach_fl_us
- at_mi: 92.9
- spoken: Billboard: Loggerhead Marinelife Center, next exit, then four miles east. Free to visit, with a hospital for sea turtles. Nobody honks at the patients.

### Loggerhead Marinelife Center (southbound)
- treatment: billboard
- leg: port_saint_lucie_fl_us -> coral_springs_fl_us
- at_mi: 32.0
- spoken: Billboard: Loggerhead Marinelife Center, next exit, then four miles east. Free to visit, with a hospital for sea turtles. Nobody honks at the patients.

### Loggerhead Marinelife Center (northbound)
- treatment: billboard
- leg: coral_springs_fl_us -> port_saint_lucie_fl_us
- at_mi: 47.6
- spoken: Billboard: Loggerhead Marinelife Center, next exit, then four miles east. Free to visit, with a hospital for sea turtles. Nobody honks at the patients.

## Palm Beach (approved copy, reused)

The Grapefruit League sign stands only northbound on I-95 from Miami. These
two stand before West Palm Beach on the other two roads into it.

### The Grapefruit League (southbound)
- treatment: billboard
- leg: palm_bay_fl_us -> west_palm_beach_fl_us
- at_mi: 107.0
- spoken: Billboard: Palm Beach is where mansions face the ocean and old money spends the winter. Come February, baseball teams arrive for spring training in the Grapefruit League, while the lighthouse at Jupiter keeps guarding the coast as it has since before the Civil War.

### The Grapefruit League (eastbound)
- treatment: billboard
- leg: cape_coral_fl_us -> west_palm_beach_fl_us
- at_mi: 135.0
- spoken: Billboard: Palm Beach is where mansions face the ocean and old money spends the winter. Come February, baseball teams arrive for spring training in the Grapefruit League, while the lighthouse at Jupiter keeps guarding the coast as it has since before the Civil War.

## Lion Country Safari, Loxahatchee (State Road 80, Southern Boulevard)

America's first drive-through safari park, opened in 1967, 2003 Lion
Country Safari Road, two miles north of Southern Boulevard; open daily, no
convertibles or soft tops in the preserve (lioncountrysafari.com; Wikipedia,
"Lion Country Safari"). The Turnpike passes fifteen miles east of it, too far
for a sign.

### Lion Country Safari (westbound)
- treatment: billboard
- leg: west_palm_beach_fl_us -> cape_coral_fl_us
- at_mi: 11.0
- spoken: Billboard: Lion Country Safari, ahead. America's first drive-through safari park, open since nineteen sixty-seven. Windows up, and the rhinos have the right of way.

### Lion Country Safari (eastbound)
- treatment: billboard
- leg: cape_coral_fl_us -> west_palm_beach_fl_us
- at_mi: 108.0
- spoken: Billboard: Lion Country Safari, ahead. America's first drive-through safari park, open since nineteen sixty-seven. Windows up, and the rhinos have the right of way.

## Lake Okeechobee (US 27 between Moore Haven and South Bay)

Florida's largest freshwater lake, about 730 square miles, average depth
about eight feet ten inches, ringed by the Herbert Hoover Dike, which hides
it from the road (Wikipedia, "Lake Okeechobee"; South Florida Water
Management District). Tampa to Miami runs the south shore from Moore Haven
to South Bay; West Palm Beach to Cape Coral from South Bay to Clewiston.
A natural feature, not a business: the owner's call whether it belongs on a
billboard.

### Lake Okeechobee (southbound)
- treatment: billboard
- leg: tampa_fl_us -> miami_fl_us
- at_mi: 155.0
- spoken: Billboard: Lake Okeechobee, ahead, behind the dike. Florida's biggest lake, and on average only about nine feet deep. Wading across is still not recommended.

### Lake Okeechobee (northbound)
- treatment: billboard
- leg: miami_fl_us -> tampa_fl_us
- at_mi: 72.0
- spoken: Billboard: Lake Okeechobee, ahead, behind the dike. Florida's biggest lake, and on average only about nine feet deep. Wading across is still not recommended.

### Lake Okeechobee (westbound)
- treatment: billboard
- leg: west_palm_beach_fl_us -> cape_coral_fl_us
- at_mi: 41.0
- spoken: Billboard: Lake Okeechobee, ahead, behind the dike. Florida's biggest lake, and on average only about nine feet deep. Wading across is still not recommended.

### Lake Okeechobee (eastbound)
- treatment: billboard
- leg: cape_coral_fl_us -> west_palm_beach_fl_us
- at_mi: 66.0
- spoken: Billboard: Lake Okeechobee, ahead, behind the dike. Florida's biggest lake, and on average only about nine feet deep. Wading across is still not recommended.

## Everglades Holiday Park (US 27 at Griffin Road)

Airboat tours and an alligator show, 21940 Griffin Road, at the west end of
Griffin Road just off US 27, open daily; the Animal Planet series "Gator
Boys" was filmed here (evergladesholidaypark.com). Both the Naples and
Tampa legs into Miami come down US 27 past it. The Naples leg's signs stand
on US 27, south of the Alligator Alley toll plaza, outside the parkway's
sign ban.

### Everglades Holiday Park (southbound)
- treatment: billboard
- leg: naples_fl_us -> miami_fl_us
- at_mi: 88.5
- spoken: Billboard: Everglades Holiday Park, ahead. Airboat rides through the sawgrass, and the park where television's Gator Boys was filmed. The gators were not paid.

### Everglades Holiday Park (northbound)
- treatment: billboard
- leg: miami_fl_us -> naples_fl_us
- at_mi: 23.0
- spoken: Billboard: Everglades Holiday Park, ahead. Airboat rides through the sawgrass, and the park where television's Gator Boys was filmed. The gators were not paid.

### Everglades Holiday Park (southbound)
- treatment: billboard
- leg: tampa_fl_us -> miami_fl_us
- at_mi: 230.5
- spoken: Billboard: Everglades Holiday Park, ahead. Airboat rides through the sawgrass, and the park where television's Gator Boys was filmed. The gators were not paid.

### Everglades Holiday Park (northbound)
- treatment: billboard
- leg: miami_fl_us -> tampa_fl_us
- at_mi: 22.0
- spoken: Billboard: Everglades Holiday Park, ahead. Airboat rides through the sawgrass, and the park where television's Gator Boys was filmed. The gators were not paid.

## Naples Zoo at Caribbean Gardens (I-75 Exits 107 and 105)

1590 Goodlette-Frank Road; its primates live on islands in a lake and are
seen from the boat on the Primate Expedition Cruise, included with
admission (napleszoo.org directions; Wikipedia, "Naples Zoo"; USA Today
10Best 2026). Its directions use Exit 107 from the north and Exit 105 from
the east. Not signed leaving Naples, where it is the first thing on the road.

### Naples Zoo (southbound)
- treatment: billboard
- leg: fort_myers_fl_us -> naples_fl_us
- at_mi: 33.0
- spoken: Billboard: Naples Zoo, next exit. The primates live on islands in a lake, and a boat ride takes you past. They do not wave back.

### Naples Zoo (southbound)
- treatment: billboard
- leg: cape_coral_fl_us -> coral_springs_fl_us
- at_mi: 32.5
- spoken: Billboard: Naples Zoo, next exit. The primates live on islands in a lake, and a boat ride takes you past. They do not wave back.

### Naples Zoo (northbound)
- treatment: billboard
- leg: coral_springs_fl_us -> cape_coral_fl_us
- at_mi: 99.0
- spoken: Billboard: Naples Zoo, next exit. The primates live on islands in a lake, and a boat ride takes you past. They do not wave back.

## Everglades Wonder Gardens, Bonita Springs (I-75 Exit 116)

Opened in 1936 by Bill and Lester Piper, two retired bootleggers, as the
Everglades Reptile Gardens behind their house; now a nonprofit garden with
flamingos, alligators and rescued birds, ninety years old in 2026, 27180 Old
41 Road (Roadside America; Florida Rambler; WGCU, January 2026).

### Everglades Wonder Gardens (southbound)
- treatment: billboard
- leg: fort_myers_fl_us -> naples_fl_us
- at_mi: 24.0
- spoken: Billboard: Everglades Wonder Gardens, next exit in Bonita Springs. Two retired bootleggers opened it in nineteen thirty-six with backyard alligators. A wholesome second career.

### Everglades Wonder Gardens (northbound)
- treatment: billboard
- leg: naples_fl_us -> fort_myers_fl_us
- at_mi: 11.0
- spoken: Billboard: Everglades Wonder Gardens, ahead in Bonita Springs. Two retired bootleggers opened it in nineteen thirty-six with backyard alligators. A wholesome second career.

### Everglades Wonder Gardens (southbound)
- treatment: billboard
- leg: cape_coral_fl_us -> coral_springs_fl_us
- at_mi: 17.7
- spoken: Billboard: Everglades Wonder Gardens, ahead in Bonita Springs. Two retired bootleggers opened it in nineteen thirty-six with backyard alligators. A wholesome second career.

### Everglades Wonder Gardens (northbound)
- treatment: billboard
- leg: coral_springs_fl_us -> cape_coral_fl_us
- at_mi: 106.0
- spoken: Billboard: Everglades Wonder Gardens, ahead in Bonita Springs. Two retired bootleggers opened it in nineteen thirty-six with backyard alligators. A wholesome second career.

## Koreshan State Park, Estero (I-75 Exit 123, Corkscrew Road)

The settlement Cyrus Teed's Koreshan Unity built from 1894; they held that
people live on the inside of a hollow Earth. Their last members gave it to
the state in 1961. Two miles west of Exit 123 on Corkscrew Road (Florida
State Parks; Florida Rambler). Every "next exit" slot here is crowded by the
San Carlos Park, Miromar Lakes and Shadow Wood callouts, so these read
"ahead".

### Koreshan State Park (southbound)
- treatment: billboard
- leg: fort_myers_fl_us -> naples_fl_us
- at_mi: 12.0
- spoken: Billboard: Koreshan State Park, ahead in Estero. Its founders believed we all live inside a hollow Earth. Wave to the folks overhead.

### Koreshan State Park (northbound)
- treatment: billboard
- leg: naples_fl_us -> fort_myers_fl_us
- at_mi: 19.0
- spoken: Billboard: Koreshan State Park, ahead in Estero. Its founders believed we all live inside a hollow Earth. Wave to the folks overhead.

### Koreshan State Park (southbound)
- treatment: billboard
- leg: cape_coral_fl_us -> coral_springs_fl_us
- at_mi: 10.0
- spoken: Billboard: Koreshan State Park, ahead in Estero. Its founders believed we all live inside a hollow Earth. Wave to the folks overhead.

### Koreshan State Park (northbound)
- treatment: billboard
- leg: coral_springs_fl_us -> cape_coral_fl_us
- at_mi: 110.0
- spoken: Billboard: Koreshan State Park, ahead in Estero. Its founders believed we all live inside a hollow Earth. Wave to the folks overhead.

## Fort Myers: Edison and Ford Winter Estates (approved copy, reused)

The Edison and Ford sign stands only northbound on I-75 from Naples. These
two stand before Fort Myers on I-75 from the north and on State Road 80 from
the east.

### Edison and Ford Wintered Here (southbound)
- treatment: billboard
- leg: north_port_fl_us -> fort_myers_fl_us
- at_mi: 44.5
- spoken: Billboard: Fort Myers is where Thomas Edison and Henry Ford kept winter homes side by side on the river. Edison planted a banyan tree that now shades an acre, and his laboratory remains much as he left it.

### Edison and Ford Wintered Here (westbound)
- treatment: billboard
- leg: west_palm_beach_fl_us -> cape_coral_fl_us
- at_mi: 119.0
- spoken: Billboard: Fort Myers is where Thomas Edison and Henry Ford kept winter homes side by side on the river. Edison planted a banyan tree that now shades an acre, and his laboratory remains much as he left it.

## Solomon's Castle, Ona (approved copy, reused)

Howard Solomon's castle of discarded aluminum printing plates, 4533 Solomon
Road, reached from US 17 at Wauchula by State Road 64 west and County Road
665 south; open October 1 to August 1, closed August and September
(Roadside America; Solomon's Castle by phone listing). The existing sign
faces northbound only; this one stands ten miles before Wauchula
southbound.

### Solomon's Castle (southbound)
- treatment: billboard
- leg: lakeland_fl_us -> cape_coral_fl_us
- at_mi: 28.0
- spoken: Billboard: Solomon's Castle is ahead in the Florida woods. It is a handmade silver palace built from printing plates, imagination, and a complete refusal to ask whether zoning approved.

## Bok Tower Gardens, Lake Wales (State Road 60 and US 27)

The 205-foot Singing Tower with a sixty-bell carillon, dedicated by
President Coolidge in 1929, on Iron Mountain, about 295 feet above sea
level and one of the highest points in peninsular Florida; a National
Historic Landmark, about three miles north of State Road 60 (Wikipedia, "Bok
Tower Gardens"; boktowergardens.org).

### Bok Tower Gardens (eastbound)
- treatment: billboard
- leg: lakeland_fl_us -> port_saint_lucie_fl_us
- at_mi: 16.0
- spoken: Billboard: Bok Tower Gardens, ahead in Lake Wales. A sixty-bell singing tower on one of the highest hills in peninsular Florida. The competition is flat.

### Bok Tower Gardens (westbound)
- treatment: billboard
- leg: port_saint_lucie_fl_us -> lakeland_fl_us
- at_mi: 87.0
- spoken: Billboard: Bok Tower Gardens, ahead in Lake Wales. A sixty-bell singing tower on one of the highest hills in peninsular Florida. The competition is flat.

## Spook Hill, Lake Wales (North Wales Drive)

A gravity hill: on a marked stretch of North Wales Drive a car in neutral
appears to roll uphill. City-signed, on the National Register since April
2019, about a mile north of State Road 60 (Wikipedia, "Spook Hill"; WUSF,
2019; Roadside America). The copy leaves out the city sign's legend.

### Spook Hill (eastbound)
- treatment: billboard
- leg: lakeland_fl_us -> port_saint_lucie_fl_us
- at_mi: 21.0
- spoken: Billboard: Spook Hill, ahead in Lake Wales. A car in neutral seems to roll uphill. Do not try it with forty tons behind you.

### Spook Hill (westbound)
- treatment: billboard
- leg: port_saint_lucie_fl_us -> lakeland_fl_us
- at_mi: 92.0
- spoken: Billboard: Spook Hill, ahead in Lake Wales. A car in neutral seems to roll uphill. Do not try it with forty tons behind you.

## Westgate River Ranch, River Ranch (State Road 60)

A dude ranch resort at 3200 River Ranch Boulevard, just south of State Road
60 by the Kissimmee River, with a rodeo open to the public every Saturday
night at 7:30, tickets at the gate (visitcentralflorida.org; Palm Beach
Illustrated; orlandoattractions.com).

### Westgate River Ranch (eastbound)
- treatment: billboard
- leg: lakeland_fl_us -> port_saint_lucie_fl_us
- at_mi: 44.0
- spoken: Billboard: Westgate River Ranch, ahead. A dude ranch with a rodeo every Saturday night. Eight seconds on a bull is longer than it sounds.

### Westgate River Ranch (westbound)
- treatment: billboard
- leg: port_saint_lucie_fl_us -> lakeland_fl_us
- at_mi: 64.0
- spoken: Billboard: Westgate River Ranch, ahead. A dude ranch with a rodeo every Saturday night. Eight seconds on a bull is longer than it sounds.

## Dinosaur World, Plant City (I-4 Exit 17, Branch Forbes Road)

Hundreds of life-size dinosaur models in a twenty-two-acre outdoor park,
5145 Harvey Tew Road, at Exit 17; open daily (dinosaurworld.com/florida).
Westbound, Exit 19 sits between Exits 21 and 17 but is not in the leg's
list; the sign stands past it.

### Dinosaur World (westbound)
- treatment: billboard
- leg: orlando_fl_us -> tampa_fl_us
- at_mi: 64.5
- spoken: Billboard: Dinosaur World, next exit in Plant City. Hundreds of life-size dinosaurs out in the woods. Older than the rest areas, but only just.

### Dinosaur World (eastbound)
- treatment: billboard
- leg: tampa_fl_us -> orlando_fl_us
- at_mi: 17.0
- spoken: Billboard: Dinosaur World, next exit in Plant City. Hundreds of life-size dinosaurs out in the woods. Older than the rest areas, but only just.

## Tampa (approved copy, reused)

The Cigar City sign stands only on Sarasota to Tampa. These stand two and a
half to three miles before downtown Tampa on every other road into it.

### The Cigar City (northbound)
- treatment: billboard
- leg: cape_coral_fl_us -> tampa_fl_us
- at_mi: 131.5
- spoken: Billboard: Tampa is the Cigar City, where Ybor City once rolled the world's cigars by hand. A pirate ship invades the bay each winter for Gasparilla, while beer, roller coasters, and giraffes coexist at Busch Gardens.

### The Cigar City (northbound)
- treatment: billboard
- leg: miami_fl_us -> tampa_fl_us
- at_mi: 268.5
- spoken: Billboard: Tampa is the Cigar City, where Ybor City once rolled the world's cigars by hand. A pirate ship invades the bay each winter for Gasparilla, while beer, roller coasters, and giraffes coexist at Busch Gardens.

### The Cigar City (westbound)
- treatment: billboard
- leg: orlando_fl_us -> tampa_fl_us
- at_mi: 81.5
- spoken: Billboard: Tampa is the Cigar City, where Ybor City once rolled the world's cigars by hand. A pirate ship invades the bay each winter for Gasparilla, while beer, roller coasters, and giraffes coexist at Busch Gardens.

### The Cigar City (southbound)
- treatment: billboard
- leg: ocala_fl_us -> tampa_fl_us
- at_mi: 97.5
- spoken: Billboard: Tampa is the Cigar City, where Ybor City once rolled the world's cigars by hand. A pirate ship invades the bay each winter for Gasparilla, while beer, roller coasters, and giraffes coexist at Busch Gardens.

### The Cigar City (southbound)
- treatment: billboard
- leg: spring_hill_fl_us -> tampa_fl_us
- at_mi: 47.5
- spoken: Billboard: Tampa is the Cigar City, where Ybor City once rolled the world's cigars by hand. A pirate ship invades the bay each winter for Gasparilla, while beer, roller coasters, and giraffes coexist at Busch Gardens.

## The Ringling, Sarasota (I-75 Exit 213, University Parkway)

The John and Mable Ringling Museum of Art (the state art museum of
Florida), Ca' d'Zan, the Ringlings' 1926 bayfront mansion, and the Circus
Museum with Howard Tibbals' Howard Bros. Circus model, 3,800 square feet at
three-quarters of an inch to the foot (a median new American house is about
2,200 square feet); 5401 Bay Shore Road, about seven miles west of Exit 213;
open daily (ringling.org; Wikipedia, "The Howard Bros. Circus"). Not signed northbound out of Sarasota: the
only slot before Exit 213 is inside the Braden River callout.

### The Ringling (southbound)
- treatment: billboard
- leg: tampa_fl_us -> sarasota_fl_us
- at_mi: 49.6
- spoken: Billboard: The Ringling, next exit, then seven miles west. A circus king's art museum, his bayfront mansion, and a miniature circus bigger than most houses.

### The Ringling (southbound)
- treatment: billboard
- leg: tampa_fl_us -> cape_coral_fl_us
- at_mi: 49.2
- spoken: Billboard: The Ringling, next exit, then seven miles west. A circus king's art museum, his bayfront mansion, and a miniature circus bigger than most houses.

### The Ringling (northbound)
- treatment: billboard
- leg: cape_coral_fl_us -> tampa_fl_us
- at_mi: 81.2
- spoken: Billboard: The Ringling, next exit, then seven miles west. A circus king's art museum, his bayfront mansion, and a miniature circus bigger than most houses.

## Siesta Key (I-75 Exit 205, Clark Road)

Siesta Beach, whose sand is about ninety-nine percent quartz and stays cool
underfoot on hot days; Dr. Beach's top beach in the country in 2011
(Smarter Travel; Luxury Travel Advisor). The legs mark
Exit 205 for Siesta Key.

### Siesta Key (southbound)
- treatment: billboard
- leg: sarasota_fl_us -> north_port_fl_us
- at_mi: 8.9
- spoken: Billboard: Siesta Key, next exit. Its beach sand is almost pure quartz and stays cool underfoot, even in August. Your boots are not invited.

### Siesta Key (southbound)
- treatment: billboard
- leg: tampa_fl_us -> cape_coral_fl_us
- at_mi: 58.3
- spoken: Billboard: Siesta Key, next exit. Its beach sand is almost pure quartz and stays cool underfoot, even in August. Your boots are not invited.

### Siesta Key (northbound)
- treatment: billboard
- leg: north_port_fl_us -> sarasota_fl_us
- at_mi: 22.5
- spoken: Billboard: Siesta Key, next exit. Its beach sand is almost pure quartz and stays cool underfoot, even in August. Your boots are not invited.

### Siesta Key (northbound)
- treatment: billboard
- leg: cape_coral_fl_us -> tampa_fl_us
- at_mi: 72.8
- spoken: Billboard: Siesta Key, next exit. Its beach sand is almost pure quartz and stays cool underfoot, even in August. Your boots are not invited.

## Venice, the Shark Tooth Capital of the World (I-75 Exit 193)

Fossil shark teeth wash up on Venice's beaches, Caspersen Beach above all,
and the city calls itself the Shark Tooth Capital of the World (Sarasota
Magazine, April 2026; Islands; Roadside America). The legs mark Exit 193 for
Venice.

### Venice (southbound)
- treatment: billboard
- leg: sarasota_fl_us -> north_port_fl_us
- at_mi: 20.6
- spoken: Billboard: Venice, next exit, the Shark Tooth Capital of the World. Fossil shark teeth wash up on its beaches. The sharks are done with them.

### Venice (southbound)
- treatment: billboard
- leg: tampa_fl_us -> cape_coral_fl_us
- at_mi: 70.5
- spoken: Billboard: Venice, next exit, the Shark Tooth Capital of the World. Fossil shark teeth wash up on its beaches. The sharks are done with them.

### Venice (northbound)
- treatment: billboard
- leg: north_port_fl_us -> sarasota_fl_us
- at_mi: 10.5
- spoken: Billboard: Venice, next exit, the Shark Tooth Capital of the World. Fossil shark teeth wash up on its beaches. The sharks are done with them.

### Venice (northbound)
- treatment: billboard
- leg: cape_coral_fl_us -> tampa_fl_us
- at_mi: 61.4
- spoken: Billboard: Venice, next exit, the Shark Tooth Capital of the World. Fossil shark teeth wash up on its beaches. The sharks are done with them.

## Notes for the owner

Twenty-five attractions and eighty signs: twenty-one new attractions on
seventy signs, plus four already-signed places (Tampa, Fort Myers, Palm
Beach, Solomon's Castle) reused word for word on ten legs and directions
that had none. A dry run of `tools/bake_billboards.py` on this sheet
resolves every leg and bakes all eighty (no `--write`). A spacing check
against the current legs found no callout heard in the same direction
within 2.2 miles of any sign, counting villages within a mile and a half,
every billboard facing the same way, and the other signs on this sheet.
Three signs sit exactly 2.2 miles from a callout on each side (Coral Castle
northbound, the Guitar Hotel northbound on Miami to Jacksonville, Wonder
Gardens on Cape Coral to Coral Springs); the game's own spacing is 2.0, so
they hold. Every new line is spelled out with no digits and runs twenty to
twenty-six words; the joke in each is original.

**Billboard law, and what it changed.**

- Florida Statutes 335.092 makes Alligator Alley (the Everglades Parkway,
  I-75 between its tollgates) an official scenic highway and bans any
  advertising sign within 500 feet of it, official road signs and small
  for-sale signs excepted
  (https://flsenate.gov/Laws/Statutes/2025/0335.092). No sign on this sheet
  stands between the tollgates. The four existing eastbound billboards on
  Naples to Miami (Skunk Ape at 24, Everglades City at 27, Airboat at 40,
  You Are Outnumbered at 60) all stand inside that ban. Recommendation:
  move the Everglades City and Skunk Ape signs west of the Golden Gate toll
  plaza (before mile 10, Exit 101) and drop the other two, since the real
  road carries no billboards there. Your call; nothing here touches them.
- US 1 from Key Largo to Key West is the Florida Keys Scenic Highway, an
  All-American Road since 2009
  (https://floridascenichighways.com/our-byways/southern-region/florida-keys-scenic-highway/).
  Federal law, 23 USC 131(s), bars new billboards along a designated scenic
  byway on the primary system, and Monroe County's land development code,
  section 142-4(1), prohibits off-premises signs; pre-1986 signs survive
  only as nonconforming
  (https://www.zoneomics.com/code/monroe-county-unincorporated-FL/chapter_18).
  So this sheet adds nothing in the Keys: no Dolphin Research Center, Turtle
  Hospital or Pennekamp sign, and no northbound copies of the existing Keys
  signs, though the brief welcomed those. The existing southbound Keys signs
  can stand for the old boards that are still up.
- The 18-Mile Stretch of US 1 from Florida City to Key Largo runs through
  conservation land with no commercial zoning, where Chapter 479 permits no
  billboard. No sign here stands on it, which is why Robert Is Here gets no
  northbound sign.
- Elsewhere Chapter 479 permits billboards along interstates and US routes
  in commercial and industrial areas, which covers every other sign here.
  Not checked: zoning at each milepost, notably US 27 through western
  Broward County, where the west side of the road is water conservation
  land.

**Attractions, sources, and what was checked** (each checked open in
September 2026, on its own site unless noted):

- **Zoo Miami.** https://en.wikipedia.org/wiki/Zoo_Miami (largest zoo in
  Florida, "the only tropical zoo in the continental United States"). The
  Miami to Key West leg runs the Turnpike's Homestead Extension past it,
  about a mile off, though the leg is labeled US 1.
- **Monkey Jungle.** https://www.monkeyjungle.com/ (open; 30 acres; open to
  the public since 1935; visitors walk caged paths). Its slogan is not used.
  Reviewers in 2025 reported fewer monkeys and half the grounds under
  renovation.
- **Coral Castle.** https://coralcastle.com/visit/ (open daily 9 to 8) and
  https://en.wikipedia.org/wiki/Coral_Castle (1,100 tons, built alone, gate
  on a truck bearing). Its Turnpike exit is Exit 5; the leg has no
  interchange list, so the signs read "ahead".
- **Vizcaya.** https://vizcaya.org/ (open daily except Tuesday) and
  https://en.wikipedia.org/wiki/Vizcaya_Museum_and_Gardens. Unsure: the
  southbound signs stand on legs that end downtown, about two miles short
  of it; they are true for anyone continuing down I-95.
- **Seminole Hard Rock's Guitar Hotel.**
  https://en.wikipedia.org/wiki/Seminole_Hard_Rock_Hotel_%26_Casino_Hollywood
  (450 feet, opened October 2019, visible from the Turnpike) and the
  casino's directions (Turnpike at Griffin Road; I-95 at Stirling Road).
  Casinos are on the Ruth keep list.
- **Butterfly World.** https://www.butterflyworld.com/ (open daily; 20,000
  butterflies and birds) and Visit Lauderdale for Turnpike Exit 69.
- **Morikami Museum and Japanese Gardens.**
  https://www.frommers.com/destinations/boca-raton/attractions/morikami-museum-and-japanese-gardens/
  and https://tclf.org/landscapes/morikami-museum-and-japanese-gardens
  (Yamato Colony, George Morikami's gift, opened 1977, sixteen acres of
  gardens, bonsai) and https://morikami.org/ (open Tuesday to Sunday, 10
  to 5; the museum galleries are closed for an air-conditioning repair this
  week, the gardens open). Seven signs, because four legs share the
  Turnpike past it; trimming to the two Jacksonville to Miami signs would
  be reasonable.
- **Loggerhead Marinelife Center.** https://marinelife.org/ (open daily 10
  to 5, free; front entrance under renovation from September 21).
- **Lion Country Safari.** https://www.lioncountrysafari.com/ (open daily
  10 to 5) and https://en.wikipedia.org/wiki/Lion_Country_Safari (1967,
  billed as the country's first drive-through safari; windows stay shut).
- **Lake Okeechobee.** https://en.wikipedia.org/wiki/Lake_Okeechobee (734
  square miles, average depth 8 feet 10 inches) and
  https://www.sfwmd.gov/our-work/lake-okeechobee. A natural feature, not a
  business; drop these four if billboards should stay commercial.
- **Everglades Holiday Park.** https://www.evergladesholidaypark.com/about
  (airboats daily from 9; the Gator Boys filming location).
- **Naples Zoo.** https://www.napleszoo.org/directions and
  https://en.wikipedia.org/wiki/Naples_Zoo (Primate Expedition Cruise;
  USA Today 10Best 2026).
- **Everglades Wonder Gardens.** https://roadsideamerica.com/story/13422
  (opened February 22, 1936 by Bill and Lester Piper, "retired
  bootleggers") and
  https://www.floridarambler.com/florida-gardens/everglades-wonder-gardens/
  (open, now a nonprofit garden); WGCU, January 2026, on its ninetieth
  year.
- **Koreshan State Park.** Florida State Parks history pages and
  https://www.floridarambler.com/historic-florida-getaways/koreshan-state-park/
  (hollow-Earth belief; Exit 123, two miles west). Open; its boat ramp and
  parking lot closed for renovation from May 11, 2026.
- **Edison and Ford, Palm Beach, Tampa, Solomon's Castle.** Existing copy,
  unchanged. Solomon's Castle is closed August and September and reopens
  October 1 (https://www.roadsideamerica.com/story/2059). The Palm Beach
  copy's "Come February" is seasonal by design.
- **Bok Tower Gardens.** https://en.wikipedia.org/wiki/Bok_Tower_Gardens
  (205 feet, sixty bells, Iron Mountain about 295 feet, one of the highest
  points in peninsular Florida).
- **Spook Hill.** https://en.wikipedia.org/wiki/Spook_Hill (gravity hill,
  National Register 2019). The city sign's legend involves a chief and an
  alligator; the copy leaves it out.
- **Westgate River Ranch.**
  https://visitcentralflorida.org/events/saturday-night-rodeo/ (Saturday
  7:30 rodeo, tickets at the gate). A resort brand, so the most commercial
  line here; its "largest dude ranch east of the Mississippi" claim is not
  used.
- **Dinosaur World.** https://www.dinosaurworld.com/florida/ (open daily 10
  to 5; "hundreds of life-sized dinosaurs"; Exit 17).
- **The Ringling.** https://www.ringling.org/visit/ (open daily),
  https://en.wikipedia.org/wiki/John_and_Mable_Ringling_Museum_of_Art and
  https://en.wikipedia.org/wiki/The_Howard_Bros._Circus (3,800 square
  feet). Median new house, 2,183 square feet in late 2025 (Census Bureau
  via NAHB).
- **Siesta Key.** https://smartertravel.com/daily-daydream-siesta-beach-florida
  (99 percent quartz, cool underfoot) and Dr. Beach's 2011 list.
- **Venice.** https://www.sarasotamagazine.com/travel-and-outdoors/2026/04/venice-is-the-shark-tooth-capital-of-the-world
  and https://www.roadsideamerica.com/tip/81403. "Shark Tooth Capital of
  the World" is the city's nickname, not ad copy.

**Dropped:**

- **Keys attractions (Dolphin Research Center, the Turtle Hospital, John
  Pennekamp, Pigeon Key) and northbound copies of the Keys signs.** Law,
  above.
- **Alligator Alley attractions (Billie Swamp Safari, the Ah-Tah-Thi-Ki
  Museum) and westbound copies of the Alley signs.** Law, above.
- **Robert Is Here, northbound.** Its only slot is on the 18-Mile Stretch.
- **Monkey Jungle, northbound.** No slot clear of the Homestead village
  callouts that Coral Castle does not take.
- **Shell Factory, North Fort Myers.** Closed for good September 29, 2024
  (WINK News; WGCU).
- **The Desert Inn, Yeehaw Junction.** Demolished September 2024 (Florida
  Rambler).
- **Fantasy of Flight, Polk City.** Main museum closed for long-term
  renovation; a small hangar opens on seasonal weekends only.
- **Warm Mineral Springs, North Port.** Under a sixteen-month rebuild from
  July 2026, and it sits at the North Port city node.
- **Manatee Viewing Center, Apollo Beach.** Open November to mid-April
  only.
- **National Navy UDT-SEAL Museum, Fort Pierce.** About thirteen road miles
  from I-95 by its own directions; neither "next exit" nor "ahead" is
  honest.
- **Busch Gardens and ZooTampa.** Busch Gardens is named in the Tampa
  sign, which this sheet puts on every road into Tampa; ZooTampa would
  compete with it on I-275.
- **Seminole Hard Rock Tampa.** Same stretch as the Tampa sign, and a
  second Hard Rock line.
- **Homestead-Miami Speedway, the Everglades Alligator Farm, Fruit and
  Spice Park, Venetian Pool, Fairchild Garden.** Same South Dade stretch as
  Coral Castle, Monkey Jungle and Zoo Miami, with no free slot.
- **Everglades National Park.** Already signed as the Everglades.
- **Legoland Florida.** Named in the existing Winter Haven sign.
- **Florida Southern College's Wright buildings.** Already a Lakeland
  callout.
- **Jupiter Inlet Lighthouse.** Named in the Palm Beach sign.
- **Flagler Museum, Palm Beach Zoo, Florida Aquarium, Wynwood Walls,
  Jungle Island.** At a city node, following the Tennessee Aquarium
  precedent.
- **Myakka River State Park.** Shares Exit 205 with Siesta Key.
- **Sawgrass Recreation Park.** Same stretch of US 27 as Everglades Holiday
  Park.
- **The Ringling, northbound out of Sarasota.** The only slot before Exit
  213 is inside the Braden River callout; Cape Coral to Tampa carries it.
- **St. Petersburg and Clearwater (the Dali Museum, the Sunshine Skyway,
  Clearwater Marine Aquarium, Tarpon Springs).** No leg goes there.
- **Sanibel, Corkscrew Swamp, McKee Botanical Garden, Lake Kissimmee State
  Park, Seminole Casino Immokalee.** Fifteen miles or more off any leg.

Found along the way (data, not this sheet): on Tampa to Miami the dense
route geometry runs four to five miles short of the checkpoints in the
middle (Clewiston 172.9 against 176.7, South Bay 188.6 against 192.8), so
geometry-projected mileposts on that leg need correcting. On Cape Coral to
Tampa the Braden and Little Manatee River crossings are stacked at mile
96.3, though the Little Manatee is about thirteen miles north. On the
Turnpike legs into Miami a "Miami River" crossing sits at Miami Gardens,
about ten miles north of the river. Checked together with the finished
north and central Florida sheet (signs-fl-north.md, 121 signs): no two
signs on a shared leg stand within 2.2 miles in the same direction, no
names collide, and no attraction is on both sheets.
