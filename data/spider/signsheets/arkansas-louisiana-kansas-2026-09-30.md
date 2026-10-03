
# Arkansas, Louisiana and Kansas attractions, both directions -- 2026-09-30

DRAFT for owner approval.

Real roadside attractions in three states that carried almost no placed
signs, each signed in every direction a leg passes it. Every `leg:` is
written the way the driver reads the sign and `at_mi` counts from that end;
`tools/bake_billboards.py` mirrors the milepost onto a leg stored the other
way round and records which way the billboard faces.

Mileposts come from the legs' interchange lists (the attraction's exit and
the one before it) and, on US and state highways with no interchange list,
from projecting the place onto the leg's route geometry. "Next exit" signs
stand between the attraction's exit and the exit before it; "ahead" signs
about eight to fifteen miles out. Each sits at least 2.2 miles from every
other callout heard in the same direction (rivers, museums, villages within
a mile and a half of the road, forward-facing billboards), so the landmark
spacing does not drop it.

# Arkansas

## Eureka Springs (US 62)

The Victorian spa town on US 62; the whole 1970 city is on the National
Register as the Eureka Springs Historic District, its streets wind with few
meeting at right angles, and it has no traffic lights (Wikipedia, "Eureka
Springs, Arkansas"; Northwest Arkansas Democrat-Gazette 2022 on the
town's roundabout debate). The leg's own checkpoint puts the town at mile
39.0 from Bentonville.

### Eureka Springs (eastbound)
- treatment: billboard
- leg: bentonville_ar_us -> harrison_ar_us
- at_mi: 25.5
- spoken: Billboard: Eureka Springs, ahead. Streets that wind and hardly ever cross square, and not one traffic light in town. Your trailer has been warned.

### Eureka Springs (westbound)
- treatment: billboard
- leg: harrison_ar_us -> bentonville_ar_us
- at_mi: 30.0
- spoken: Billboard: Eureka Springs, ahead. Streets that wind and hardly ever cross square, and not one traffic light in town. Your trailer has been warned.

## Bathhouse Row, Hot Springs (city node)

Hot Springs National Park. The water reaches the surface at an average of
143 degrees and is more than four thousand years old; the park's jug
fountains give it away free (nps.gov/hosp, "Experience the Water"). The
Buckstaff and Quapaw still offer baths on Bathhouse Row (nps.gov/hosp park
brochure). Hot Springs is the leg endpoint, so each sign stands on an
approach about twelve miles out.

### Bathhouse Row (from Little Rock)
- treatment: billboard
- leg: little_rock_ar_us -> hot_springs_ar_us
- at_mi: 45.0
- spoken: Billboard: Bathhouse Row, ahead in Hot Springs. The water comes up a hundred forty-three degrees and four thousand years old. Fill a jug free.

### Bathhouse Row (from Fort Smith)
- treatment: billboard
- leg: fort_smith_ar_us -> hot_springs_ar_us
- at_mi: 118.0
- spoken: Billboard: Bathhouse Row, ahead in Hot Springs. The water comes up a hundred forty-three degrees and four thousand years old. Fill a jug free.

### Bathhouse Row (from Texarkana)
- treatment: billboard
- leg: texarkana_ar_us -> hot_springs_ar_us
- at_mi: 97.5
- spoken: Billboard: Bathhouse Row, ahead in Hot Springs. The water comes up a hundred forty-three degrees and four thousand years old. Fill a jug free.

## The Walmart Museum, Bentonville (city node)

On the Bentonville square, in Sam Walton's Walton's 5&10; reopened March
14, 2025 after a two-year renovation, with a hologram of Walton that
answers visitors' questions (Talk Business & Politics, March 2025; KNWA).
Open daily. Bentonville is the leg endpoint, so each sign stands on an
approach eleven to fourteen miles out.

### The Walmart Museum (from Fayetteville)
- treatment: billboard
- leg: fayetteville_ar_us -> bentonville_ar_us
- at_mi: 17.5
- spoken: Billboard: The Walmart Museum, ahead in Bentonville. Sam Walton's five-and-dime, and a hologram of him that answers questions. Ask him where to park the truck.

### The Walmart Museum (from Joplin)
- treatment: billboard
- leg: joplin_mo_us -> bentonville_ar_us
- at_mi: 53.0
- spoken: Billboard: The Walmart Museum, ahead in Bentonville. Sam Walton's five-and-dime, and a hologram of him that answers questions. Ask him where to park the truck.

### The Walmart Museum (from Harrison)
- treatment: billboard
- leg: harrison_ar_us -> bentonville_ar_us
- at_mi: 68.5
- spoken: Billboard: The Walmart Museum, ahead in Bentonville. Sam Walton's five-and-dime, and a hologram of him that answers questions. Ask him where to park the truck.

## Alma, the spinach capital (I-40 Exit 13)

Alma has called itself the Spinach Capital of the World since the Allen
Canning Company years; a bronze Popeye holding a can of spinach was
unveiled at the 2007 Spinach Festival, replacing a fiberglass one from 1987
(Roadside America news, April 2007; Encyclopedia of Arkansas, "Popeye
Statue"; KNWA on Popeye Park). Exit 13 is Alma's exit on I-40.
Westbound, Exit 20 comes just before it. Eastbound, Exit 12 (I-49 north)
comes a mile before Exit 13 and is missing from the legs' lists, so the
eastbound signs read "ahead": eleven miles out from Oklahoma; three miles
out on the Fort Smith to Little Rock leg, which joins I-40 in Van Buren;
and on Fort Smith to Russellville, where the Arkansas River and Alma
callouts leave room only before the river, about eleven miles out.

### Alma (westbound)
- treatment: billboard
- leg: little_rock_ar_us -> oklahoma_city_ok_us
- at_mi: 142.6
- spoken: Billboard: Alma, next exit. The town calls itself the spinach capital of the world and keeps a bronze Popeye to prove it. Results may vary.

### Alma (westbound)
- treatment: billboard
- leg: russellville_ar_us -> fort_smith_ar_us
- at_mi: 67.5
- spoken: Billboard: Alma, next exit. The town calls itself the spinach capital of the world and keeps a bronze Popeye to prove it. Results may vary.

### Alma (eastbound)
- treatment: billboard
- leg: oklahoma_city_ok_us -> little_rock_ar_us
- at_mi: 183.5
- spoken: Billboard: Alma, ahead. The town calls itself the spinach capital of the world and keeps a bronze Popeye to prove it. Results may vary.

### Alma (eastbound)
- treatment: billboard
- leg: fort_smith_ar_us -> little_rock_ar_us
- at_mi: 11.0
- spoken: Billboard: Alma, ahead. The town calls itself the spinach capital of the world and keeps a bronze Popeye to prove it. Results may vary.

### Alma (westbound)
- treatment: billboard
- leg: little_rock_ar_us -> fort_smith_ar_us
- at_mi: 143.0
- spoken: Billboard: Alma, next exit. The town calls itself the spinach capital of the world and keeps a bronze Popeye to prove it. Results may vary.

### Alma (eastbound)
- treatment: billboard
- leg: fort_smith_ar_us -> russellville_ar_us
- at_mi: 3.5
- spoken: Billboard: Alma, ahead. The town calls itself the spinach capital of the world and keeps a bronze Popeye to prove it. Results may vary.

## Plum Bayou Mounds Archeological State Park, Scott (US 165)

Formerly Toltec Mounds; renamed in November 2022 after consultation with
tribal nations. The Toltec name came from a nineteenth-century belief that
the Toltecs of Mexico built the mounds, later shown wrong; Mound A, 49.5
feet, is the tallest in Arkansas (Arkansas State Parks; University of
Arkansas Archeological Survey, "Toltec renamed Plum Bayou Mounds";
arkansas.com). Visitor center open Wednesday to Sunday. 490 Toltec Mounds
Road, about four miles from Scott, beside US 165 (leg mile 18.5 from
Little Rock).

### Plum Bayou Mounds (southbound)
- treatment: billboard
- leg: little_rock_ar_us -> stuttgart_ar_us
- at_mi: 9.5
- spoken: Billboard: Plum Bayou Mounds, ahead. The tallest mound in Arkansas. For generations it was named for the Toltecs, who never came near the place.

### Plum Bayou Mounds (northbound)
- treatment: billboard
- leg: stuttgart_ar_us -> little_rock_ar_us
- at_mi: 25.0
- spoken: Billboard: Plum Bayou Mounds, ahead. The tallest mound in Arkansas. For generations it was named for the Toltecs, who never came near the place.

## Stuttgart (city node)

The World's Championship Duck Calling Contest is held in Stuttgart every
Thanksgiving weekend; the first, on Main Street on November 24, 1936, was
won by Thomas E. Walsh, who called with his throat and no duck call
(Encyclopedia of Arkansas, "World's Championship Duck Calling Contest").
Stuttgart is the leg endpoint; both signs are about ten miles out.

### Stuttgart (from Little Rock)
- treatment: billboard
- leg: little_rock_ar_us -> stuttgart_ar_us
- at_mi: 44.0
- spoken: Billboard: Stuttgart, ahead. The world duck calling championship began here in nineteen thirty-six. The first winner used no call, just his throat.

### Stuttgart (from Pine Bluff)
- treatment: billboard
- leg: pine_bluff_ar_us -> stuttgart_ar_us
- at_mi: 27.0
- spoken: Billboard: Stuttgart, ahead. The world duck calling championship began here in nineteen thirty-six. The first winner used no call, just his throat.

## Crystal Bridges Museum of American Art, Bentonville (city node)

A 120-acre site in a natural Ozark ravine around Crystal Spring; free
general admission since it opened in 2011; a 50 percent expansion opened
June 6 and 7, 2026; free parking in the museum garage (Wikipedia, "Crystal
Bridges Museum of American Art"; crystalbridges.org; Talk Business,
September 2025). Each approach already carries the Walmart Museum sign;
these stand at least 2.2 miles from it.

### Crystal Bridges (from Fayetteville)
- treatment: billboard
- leg: fayetteville_ar_us -> bentonville_ar_us
- at_mi: 20.0
- spoken: Billboard: Crystal Bridges, ahead in Bentonville. American art in an Ozark ravine around a spring, and admission is free. Parking is too, for cars.

### Crystal Bridges (from Joplin)
- treatment: billboard
- leg: joplin_mo_us -> bentonville_ar_us
- at_mi: 56.0
- spoken: Billboard: Crystal Bridges, ahead in Bentonville. American art in an Ozark ravine around a spring, and admission is free. Parking is too, for cars.

### Crystal Bridges (from Harrison)
- treatment: billboard
- leg: harrison_ar_us -> bentonville_ar_us
- at_mi: 74.0
- spoken: Billboard: Crystal Bridges, ahead in Bentonville. American art in an Ozark ravine around a spring, and admission is free. Parking is too, for cars.

## The Daisy Airgun Museum, Rogers (I-49 Exit 85; US 62)

202 West Walnut Street in downtown Rogers, open Monday to Saturday; Daisy
makes the Red Ryder BB gun of "A Christmas Story" in northwest Arkansas
(arkansas.com; Axios Northwest Arkansas, November 2023). The I-49 leg's
Exit 85 is Walnut Street; Exit 83 is missing from its list, so the signs
read "ahead". The US 62 legs run through Rogers on the way to Bentonville;
leaving Bentonville eastbound the sign is three miles out.

### Daisy Airgun Museum (from Fayetteville)
- treatment: billboard
- leg: fayetteville_ar_us -> bentonville_ar_us
- at_mi: 15.0
- spoken: Billboard: The Daisy Airgun Museum, ahead in Rogers. Daisy makes the Red Ryder, the BB gun from A Christmas Story. Eye protection recommended.

### Daisy Airgun Museum (westbound)
- treatment: billboard
- leg: harrison_ar_us -> bentonville_ar_us
- at_mi: 66.0
- spoken: Billboard: The Daisy Airgun Museum, ahead in Rogers. Daisy makes the Red Ryder, the BB gun from A Christmas Story. Eye protection recommended.

### Daisy Airgun Museum (eastbound)
- treatment: billboard
- leg: bentonville_ar_us -> harrison_ar_us
- at_mi: 3.0
- spoken: Billboard: The Daisy Airgun Museum, ahead in Rogers. Daisy makes the Red Ryder, the BB gun from A Christmas Story. Eye protection recommended.

## Thorncrown Chapel, Eureka Springs (US 62)

E. Fay Jones's 1980 chapel in the woods just west of Eureka Springs on US
62: 48 feet tall, 425 windows, more than 6,000 square feet of glass; free,
open March through December (Sinclair "Amazing America" via KVAL;
Wikipedia, "Eureka Springs, Arkansas"). Leg mile 36.2 from Bentonville. Westbound the
leg's Holy Land Tour callout sits a mile before the chapel, so that sign
stands six miles out.

### Thorncrown Chapel (eastbound)
- treatment: billboard
- leg: bentonville_ar_us -> harrison_ar_us
- at_mi: 32.5
- spoken: Billboard: Thorncrown Chapel, ahead near Eureka Springs. Four hundred twenty-five windows in the middle of the woods, free to visit. Somebody else washes them.

### Thorncrown Chapel (westbound)
- treatment: billboard
- leg: harrison_ar_us -> bentonville_ar_us
- at_mi: 40.0
- spoken: Billboard: Thorncrown Chapel, ahead near Eureka Springs. Four hundred twenty-five windows in the middle of the woods, free to visit. Somebody else washes them.

## The U.S. Marshals Museum, Fort Smith (city node)

On the Arkansas River in Fort Smith, opened July 1, 2023, in a star-shaped
building designed to recall a marshal's badge; Judge Isaac Parker's court
and deputies like Bass Reeves are why it is here; visitors up 5.3 percent
in 2025 (Encyclopedia of Arkansas, "U.S. Marshals Museum"; Talk Business,
April 2026). Fort Smith ends six legs, and the Little Rock to Oklahoma City
leg runs through it. On Russellville to Fort Smith the Alma, Arkansas River
and Van Buren callouts leave room only 3.5 miles out.

### U.S. Marshals Museum (from Little Rock)
- treatment: billboard
- leg: little_rock_ar_us -> fort_smith_ar_us
- at_mi: 148.0
- spoken: Billboard: The United States Marshals Museum, ahead in Fort Smith. The building is shaped like a marshal's badge. Drive like somebody is watching.

### U.S. Marshals Museum (from Russellville)
- treatment: billboard
- leg: russellville_ar_us -> fort_smith_ar_us
- at_mi: 80.5
- spoken: Billboard: The United States Marshals Museum, ahead in Fort Smith. The building is shaped like a marshal's badge. Drive like somebody is watching.

### U.S. Marshals Museum (westbound)
- treatment: billboard
- leg: little_rock_ar_us -> oklahoma_city_ok_us
- at_mi: 147.0
- spoken: Billboard: The United States Marshals Museum, ahead in Fort Smith. The building is shaped like a marshal's badge. Drive like somebody is watching.

### U.S. Marshals Museum (eastbound)
- treatment: billboard
- leg: oklahoma_city_ok_us -> little_rock_ar_us
- at_mi: 168.0
- spoken: Billboard: The United States Marshals Museum, ahead in Fort Smith. The building is shaped like a marshal's badge. Drive like somebody is watching.

### U.S. Marshals Museum (from Muskogee)
- treatment: billboard
- leg: muskogee_ok_us -> fort_smith_ar_us
- at_mi: 55.7
- spoken: Billboard: The United States Marshals Museum, ahead in Fort Smith. The building is shaped like a marshal's badge. Drive like somebody is watching.

### U.S. Marshals Museum (from Fayetteville)
- treatment: billboard
- leg: fayetteville_ar_us -> fort_smith_ar_us
- at_mi: 47.5
- spoken: Billboard: The United States Marshals Museum, ahead in Fort Smith. The building is shaped like a marshal's badge. Drive like somebody is watching.

### U.S. Marshals Museum (from Texarkana)
- treatment: billboard
- leg: texarkana_ar_us -> fort_smith_ar_us
- at_mi: 170.0
- spoken: Billboard: The United States Marshals Museum, ahead in Fort Smith. The building is shaped like a marshal's badge. Drive like somebody is watching.

### U.S. Marshals Museum (from Hot Springs)
- treatment: billboard
- leg: hot_springs_ar_us -> fort_smith_ar_us
- at_mi: 119.0
- spoken: Billboard: The United States Marshals Museum, ahead in Fort Smith. The building is shaped like a marshal's badge. Drive like somebody is watching.

## The Clinton Presidential Library, Little Rock (city node)

1200 President Clinton Avenue, beside I-30 at the river; the main building
cantilevers over the Arkansas River, echoing "a bridge to the 21st
century", and holds a full-scale Oval Office (Wikipedia, "Clinton
Presidential Center"). Open in 2026: special exhibits in March and on July
4 (American Battlefield Trust; National Archives calendar). Little Rock
ends ten legs; each sign is about ten to twelve miles out.

### Clinton Library (from Conway)
- treatment: billboard
- leg: conway_ar_us -> little_rock_ar_us
- at_mi: 21.0
- spoken: Billboard: The Clinton Library, ahead in Little Rock. It hangs over the river like a bridge, with a full-size Oval Office. No appointment needed.

### Clinton Library (from Fort Smith)
- treatment: billboard
- leg: fort_smith_ar_us -> little_rock_ar_us
- at_mi: 147.0
- spoken: Billboard: The Clinton Library, ahead in Little Rock. It hangs over the river like a bridge, with a full-size Oval Office. No appointment needed.

### Clinton Library (from Oklahoma City)
- treatment: billboard
- leg: oklahoma_city_ok_us -> little_rock_ar_us
- at_mi: 327.0
- spoken: Billboard: The Clinton Library, ahead in Little Rock. It hangs over the river like a bridge, with a full-size Oval Office. No appointment needed.

### Clinton Library (from Memphis)
- treatment: billboard
- leg: memphis_tn_us -> little_rock_ar_us
- at_mi: 127.5
- spoken: Billboard: The Clinton Library, ahead in Little Rock. It hangs over the river like a bridge, with a full-size Oval Office. No appointment needed.

### Clinton Library (from Jonesboro)
- treatment: billboard
- leg: jonesboro_ar_us -> little_rock_ar_us
- at_mi: 130.5
- spoken: Billboard: The Clinton Library, ahead in Little Rock. It hangs over the river like a bridge, with a full-size Oval Office. No appointment needed.

### Clinton Library (from Texarkana)
- treatment: billboard
- leg: texarkana_ar_us -> little_rock_ar_us
- at_mi: 133.5
- spoken: Billboard: The Clinton Library, ahead in Little Rock. It hangs over the river like a bridge, with a full-size Oval Office. No appointment needed.

### Clinton Library (from Hot Springs)
- treatment: billboard
- leg: hot_springs_ar_us -> little_rock_ar_us
- at_mi: 46.0
- spoken: Billboard: The Clinton Library, ahead in Little Rock. It hangs over the river like a bridge, with a full-size Oval Office. No appointment needed.

### Clinton Library (from Pine Bluff)
- treatment: billboard
- leg: pine_bluff_ar_us -> little_rock_ar_us
- at_mi: 33.0
- spoken: Billboard: The Clinton Library, ahead in Little Rock. It hangs over the river like a bridge, with a full-size Oval Office. No appointment needed.

### Clinton Library (from El Dorado)
- treatment: billboard
- leg: el_dorado_ar_us -> little_rock_ar_us
- at_mi: 109.0
- spoken: Billboard: The Clinton Library, ahead in Little Rock. It hangs over the river like a bridge, with a full-size Oval Office. No appointment needed.

### Clinton Library (from Stuttgart)
- treatment: billboard
- leg: stuttgart_ar_us -> little_rock_ar_us
- at_mi: 44.0
- spoken: Billboard: The Clinton Library, ahead in Little Rock. It hangs over the river like a bridge, with a full-size Oval Office. No appointment needed.

## Walnut Ridge and the Beatles (US 412, US 67)

On September 18, 1964, after a Dallas concert, the Beatles landed at
Walnut Ridge just after midnight to change to a small plane for a Missouri
ranch; the town unveiled an Abbey Road monument in 2011 and renamed a
downtown street Abbey Road (Encyclopedia of Arkansas). A town sign before
the town on both roads into it.

### Walnut Ridge (eastbound)
- treatment: billboard
- leg: mountain_home_ar_us -> jonesboro_ar_us
- at_mi: 92.0
- spoken: Billboard: Walnut Ridge, ahead. The Beatles changed planes at its airport in nineteen sixty-four. The town built a monument and named a street Abbey Road.

### Walnut Ridge (westbound)
- treatment: billboard
- leg: jonesboro_ar_us -> mountain_home_ar_us
- at_mi: 11.0
- spoken: Billboard: Walnut Ridge, ahead. The Beatles changed planes at its airport in nineteen sixty-four. The town built a monument and named a street Abbey Road.

### Walnut Ridge (southbound)
- treatment: billboard
- leg: poplar_bluff_mo_us -> jonesboro_ar_us
- at_mi: 63.5
- spoken: Billboard: Walnut Ridge, ahead. The Beatles changed planes at its airport in nineteen sixty-four. The town built a monument and named a street Abbey Road.

### Walnut Ridge (northbound)
- treatment: billboard
- leg: jonesboro_ar_us -> poplar_bluff_mo_us
- at_mi: 15.0
- spoken: Billboard: Walnut Ridge, ahead. The Beatles changed planes at its airport in nineteen sixty-four. The town built a monument and named a street Abbey Road.

## Queen Wilhelmina State Park, Mena (US 71)

The lodge on 2,681-foot Rich Mountain, on the Talimena Scenic Drive west of
Mena by AR 88; the first, opened in 1898 by the Kansas City, Pittsburg and
Gulf Railroad, whose investors were largely Dutch, was named for the young
Queen of the Netherlands; the 40-room lodge is open year-round (Wikipedia,
"Queen Wilhelmina State Park"; arkansas.com). The US 71 leg passes through
Mena; the park is a mountain drive west of town.

### Queen Wilhelmina State Park (southbound)
- treatment: billboard
- leg: fort_smith_ar_us -> texarkana_ar_us
- at_mi: 72.0
- spoken: Billboard: Queen Wilhelmina State Park, ahead, west of Mena. A railroad named its eighteen ninety-eight mountaintop hotel for the young Dutch queen. Arkansas kept the name.

### Queen Wilhelmina State Park (northbound)
- treatment: billboard
- leg: texarkana_ar_us -> fort_smith_ar_us
- at_mi: 90.0
- spoken: Billboard: Queen Wilhelmina State Park, ahead, west of Mena. A railroad named its eighteen ninety-eight mountaintop hotel for the young Dutch queen. Arkansas kept the name.

# Louisiana

## Gator Chateau, Jennings (I-10 Exit 64)

Inside the Louisiana Oil and Gas Park at I-10 Exit 64: hold a baby
alligator, free admission, Monday to Saturday. Hatchlings come each October
from the Rockefeller Wildlife Refuge and go back when they reach about
seven feet (explorelouisiana.com; KPLC, February 2025). Exits 65 and 64 are
two miles apart and the Zigler Art Museum callout sits between them, so
westbound signs read "ahead". The Houston and New Orleans leg lists no Exit
64; its milepost is taken from the leg's Jennings checkpoint, matching the
Lake Charles leg's spacing from Exits 59 and 65. Eastbound on that leg the
Roanoke and Zigler callouts leave no "next exit" slot, so it reads "ahead".

### Gator Chateau (eastbound)
- treatment: billboard
- leg: lake_charles_la_us -> lafayette_la_us
- at_mi: 32.0
- spoken: Billboard: Gator Chateau, next exit in Jennings. Hold a baby alligator, free. At seven feet they go back to the marsh. Visit before then.

### Gator Chateau (eastbound)
- treatment: billboard
- leg: beaumont_tx_us -> lafayette_la_us
- at_mi: 89.3
- spoken: Billboard: Gator Chateau, next exit in Jennings. Hold a baby alligator, free. At seven feet they go back to the marsh. Visit before then.

### Gator Chateau (eastbound)
- treatment: billboard
- leg: houston_tx_us -> new_orleans_la_us
- at_mi: 164.0
- spoken: Billboard: Gator Chateau, ahead in Jennings. Hold a baby alligator, free. At seven feet they go back to the marsh. Visit before then.

### Gator Chateau (westbound)
- treatment: billboard
- leg: lafayette_la_us -> lake_charles_la_us
- at_mi: 30.0
- spoken: Billboard: Gator Chateau, ahead in Jennings. Hold a baby alligator, free. At seven feet they go back to the marsh. Visit before then.

### Gator Chateau (westbound)
- treatment: billboard
- leg: lafayette_la_us -> beaumont_tx_us
- at_mi: 30.0
- spoken: Billboard: Gator Chateau, ahead in Jennings. Hold a baby alligator, free. At seven feet they go back to the marsh. Visit before then.

### Gator Chateau (westbound)
- treatment: billboard
- leg: new_orleans_la_us -> houston_tx_us
- at_mi: 160.5
- spoken: Billboard: Gator Chateau, ahead in Jennings. Hold a baby alligator, free. At seven feet they go back to the marsh. Visit before then.

## Breaux Bridge (I-10 Exit 109)

The Louisiana legislature named Breaux Bridge "la capitale mondiale de
l'ecrevisse", the crawfish capital of the world, for its 1959 centennial;
the Crawfish Festival followed (breauxbridgela.net, "About Breaux Bridge";
cajuncountry.org). Exit 109 is nine miles east of Lafayette.

### Breaux Bridge (eastbound)
- treatment: billboard
- leg: lafayette_la_us -> baton_rouge_la_us
- at_mi: 8.9
- spoken: Billboard: Breaux Bridge, next exit. The state legislature named it the crawfish capital of the world in nineteen fifty-nine. Nobody has filed an appeal.

### Breaux Bridge (eastbound)
- treatment: billboard
- leg: lafayette_la_us -> new_orleans_la_us
- at_mi: 7.5
- spoken: Billboard: Breaux Bridge, next exit. The state legislature named it the crawfish capital of the world in nineteen fifty-nine. Nobody has filed an appeal.

### Breaux Bridge (eastbound)
- treatment: billboard
- leg: houston_tx_us -> new_orleans_la_us
- at_mi: 220.5
- spoken: Billboard: Breaux Bridge, next exit. The state legislature named it the crawfish capital of the world in nineteen fifty-nine. Nobody has filed an appeal.

### Breaux Bridge (westbound)
- treatment: billboard
- leg: baton_rouge_la_us -> lafayette_la_us
- at_mi: 45.0
- spoken: Billboard: Breaux Bridge, next exit. The state legislature named it the crawfish capital of the world in nineteen fifty-nine. Nobody has filed an appeal.

### Breaux Bridge (westbound)
- treatment: billboard
- leg: new_orleans_la_us -> lafayette_la_us
- at_mi: 124.2
- spoken: Billboard: Breaux Bridge, next exit. The state legislature named it the crawfish capital of the world in nineteen fifty-nine. Nobody has filed an appeal.

### Breaux Bridge (westbound)
- treatment: billboard
- leg: new_orleans_la_us -> houston_tx_us
- at_mi: 124.0
- spoken: Billboard: Breaux Bridge, next exit. The state legislature named it the crawfish capital of the world in nineteen fifty-nine. Nobody has filed an appeal.

## The Abita Mystery House, Abita Springs (I-12 Exit 65)

John Preble's UCM Museum, 22275 Highway 36: a vintage gas station is the
entrance to a maze of buildings holding more than fifty thousand found
objects, Buford the Bassigator among them; open daily, cash only
(explorelouisiana.com; abitamysteryhouse.com via KUTV "Amazing America").
About four miles north of I-12 Exit 65 on LA 59. Eastbound, the leg's Black
and Tchefuncte River callouts sit between Exits 63 and 65, so both signs
read "ahead".

### The Abita Mystery House (eastbound)
- treatment: billboard
- leg: baton_rouge_la_us -> gulfport_ms_us
- at_mi: 60.0
- spoken: Billboard: The Abita Mystery House, ahead in Abita Springs. An old gas station leads to fifty thousand odd objects and Buford the Bassigator. No fishing.

### The Abita Mystery House (westbound)
- treatment: billboard
- leg: gulfport_ms_us -> baton_rouge_la_us
- at_mi: 53.0
- spoken: Billboard: The Abita Mystery House, ahead in Abita Springs. An old gas station leads to fifty thousand odd objects and Buford the Bassigator. No fishing.

## Natchitoches (I-49 Exit 138, city node)

Founded by the French in 1714, four years before New Orleans; the oldest
permanent European settlement in the Louisiana Purchase (Wikipedia,
"Natchitoches, Louisiana"; 64 Parishes, "Natchitoches Settlement"). Town
signs, so each stands before the town: on the legs that end there and on
the Baton Rouge to Shreveport leg, which passes Exit 138.

### Natchitoches (northbound)
- treatment: billboard
- leg: alexandria_la_us -> natchitoches_la_us
- at_mi: 41.0
- spoken: Billboard: Natchitoches, ahead, the oldest European settlement in the Louisiana Purchase. It was founded four years before New Orleans, and it brings that up.

### Natchitoches (northbound)
- treatment: billboard
- leg: baton_rouge_la_us -> shreveport_la_us
- at_mi: 150.0
- spoken: Billboard: Natchitoches, ahead, the oldest European settlement in the Louisiana Purchase. It was founded four years before New Orleans, and it brings that up.

### Natchitoches (southbound)
- treatment: billboard
- leg: shreveport_la_us -> natchitoches_la_us
- at_mi: 63.0
- spoken: Billboard: Natchitoches, ahead, the oldest European settlement in the Louisiana Purchase. It was founded four years before New Orleans, and it brings that up.

### Natchitoches (southbound)
- treatment: billboard
- leg: shreveport_la_us -> baton_rouge_la_us
- at_mi: 61.0
- spoken: Billboard: Natchitoches, ahead, the oldest European settlement in the Louisiana Purchase. It was founded four years before New Orleans, and it brings that up.

## Middendorf's, Manchac (I-55 Exit 15)

Opened by Louis and Josie Middendorf on July 4, 1934 at Pass Manchac on
Lake Maurepas, known for thin-cut fried catfish (thick is also served);
operating in 2026 (WWNO "Louisiana Eats", January 2026; 225 Baton Rouge;
iExit, I-55 Exit 15). The Jackson to New Orleans leg lists no Exit 15; its
milepost is placed by the Hammond leg's distances from Exits 23 and 7.

### Middendorf's (southbound)
- treatment: billboard
- leg: hammond_la_us -> new_orleans_la_us
- at_mi: 15.0
- spoken: Billboard: Middendorf's, next exit at Manchac. Thin fried catfish beside Lake Maurepas since nineteen thirty-four. Thick is on the menu too, for the stubborn.

### Middendorf's (southbound)
- treatment: billboard
- leg: jackson_ms_us -> new_orleans_la_us
- at_mi: 143.4
- spoken: Billboard: Middendorf's, next exit at Manchac. Thin fried catfish beside Lake Maurepas since nineteen thirty-four. Thick is on the menu too, for the stubborn.

### Middendorf's (northbound)
- treatment: billboard
- leg: new_orleans_la_us -> hammond_la_us
- at_mi: 39.4
- spoken: Billboard: Middendorf's, next exit at Manchac. Thin fried catfish beside Lake Maurepas since nineteen thirty-four. Thick is on the menu too, for the stubborn.

### Middendorf's (northbound)
- treatment: billboard
- leg: new_orleans_la_us -> jackson_ms_us
- at_mi: 39.0
- spoken: Billboard: Middendorf's, next exit at Manchac. Thin fried catfish beside Lake Maurepas since nineteen thirty-four. Thick is on the menu too, for the stubborn.

## The Creole Nature Trail, Sulphur (I-10 Exit 20)

A 180-mile All-American Road (2002) south through marsh, wildlife refuges
and Gulf beaches, with alligators along the way; its free Adventure Point
welcome center is at 2740 Ruth Street, just south of Exit 20 (sulphurla.gov;
visitlakecharles.org). Eastbound, Exit 20 is the first exit after Vinton,
so those signs read "next exit". Westbound, the Sulphur exits between 23
and 20 are not all in the legs' lists, so those read "ahead". The Sulphur
leg ends at the exit, so its sign is nine miles out.

### Creole Nature Trail (eastbound)
- treatment: billboard
- leg: houston_tx_us -> lake_charles_la_us
- at_mi: 131.0
- spoken: Billboard: The Creole Nature Trail, next exit in Sulphur. A hundred eighty miles of marsh and beach road, alligators included. Admire them from the cab.

### Creole Nature Trail (eastbound)
- treatment: billboard
- leg: beaumont_tx_us -> lafayette_la_us
- at_mi: 44.5
- spoken: Billboard: The Creole Nature Trail, next exit in Sulphur. A hundred eighty miles of marsh and beach road, alligators included. Admire them from the cab.

### Creole Nature Trail (eastbound)
- treatment: billboard
- leg: houston_tx_us -> new_orleans_la_us
- at_mi: 131.0
- spoken: Billboard: The Creole Nature Trail, next exit in Sulphur. A hundred eighty miles of marsh and beach road, alligators included. Admire them from the cab.

### Creole Nature Trail (eastbound)
- treatment: billboard
- leg: orange_tx_us -> sulphur_la_us
- at_mi: 22.5
- spoken: Billboard: The Creole Nature Trail, next exit in Sulphur. A hundred eighty miles of marsh and beach road, alligators included. Admire them from the cab.

### Creole Nature Trail (westbound)
- treatment: billboard
- leg: lake_charles_la_us -> orange_tx_us
- at_mi: 1.8
- spoken: Billboard: The Creole Nature Trail, ahead in Sulphur. A hundred eighty miles of marsh and beach road, alligators included. Admire them from the cab.

### Creole Nature Trail (westbound)
- treatment: billboard
- leg: lake_charles_la_us -> sulphur_la_us
- at_mi: 1.5
- spoken: Billboard: The Creole Nature Trail, ahead in Sulphur. A hundred eighty miles of marsh and beach road, alligators included. Admire them from the cab.

### Creole Nature Trail (westbound)
- treatment: billboard
- leg: lafayette_la_us -> beaumont_tx_us
- at_mi: 74.5
- spoken: Billboard: The Creole Nature Trail, ahead in Sulphur. A hundred eighty miles of marsh and beach road, alligators included. Admire them from the cab.

### Creole Nature Trail (westbound)
- treatment: billboard
- leg: new_orleans_la_us -> houston_tx_us
- at_mi: 204.0
- spoken: Billboard: The Creole Nature Trail, ahead in Sulphur. A hundred eighty miles of marsh and beach road, alligators included. Admire them from the cab.

## Rayne, the frog capital (I-10 Exit 87)

"Frog Capital of the World" since its frog-leg trade of the 1920s, with
more than 130 painted frog statues, frog murals, and Monsieur Jacques, a
giant metal frog tipping his hat at the town's entrance (Wikipedia,
"Rayne, Louisiana"; WorldAtlas 2026; Heart of Louisiana). A town sign, so
each stands before Exit 87 in its direction, clear of the Rayne and Duson
village callouts on either side.

### Rayne (westbound)
- treatment: billboard
- leg: lafayette_la_us -> beaumont_tx_us
- at_mi: 14.8
- spoken: Billboard: Rayne, next exit, frog capital of the world. More than a hundred painted frogs, and a giant metal one tipping his hat. Wave back.

### Rayne (westbound)
- treatment: billboard
- leg: lafayette_la_us -> lake_charles_la_us
- at_mi: 14.5
- spoken: Billboard: Rayne, next exit, frog capital of the world. More than a hundred painted frogs, and a giant metal one tipping his hat. Wave back.

### Rayne (westbound)
- treatment: billboard
- leg: new_orleans_la_us -> houston_tx_us
- at_mi: 145.5
- spoken: Billboard: Rayne, next exit, frog capital of the world. More than a hundred painted frogs, and a giant metal one tipping his hat. Wave back.

### Rayne (eastbound)
- treatment: billboard
- leg: beaumont_tx_us -> lafayette_la_us
- at_mi: 112.0
- spoken: Billboard: Rayne, next exit, frog capital of the world. More than a hundred painted frogs, and a giant metal one tipping his hat. Wave back.

### Rayne (eastbound)
- treatment: billboard
- leg: lake_charles_la_us -> lafayette_la_us
- at_mi: 55.5
- spoken: Billboard: Rayne, next exit, frog capital of the world. More than a hundred painted frogs, and a giant metal one tipping his hat. Wave back.

### Rayne (eastbound)
- treatment: billboard
- leg: houston_tx_us -> new_orleans_la_us
- at_mi: 197.5
- spoken: Billboard: Rayne, next exit, frog capital of the world. More than a hundred painted frogs, and a giant metal one tipping his hat. Wave back.

## Vermilionville, Lafayette (city node)

A living history museum and folklife park on Bayou Vermilion, 300 Fisher
Road: Acadian, Creole and Native American life from 1765 to 1890, seven
restored original homes on 23 acres; open Tuesday to Sunday (Vermilionville
via Group Tour Magazine and Explore Louisiana). Lafayette ends five legs,
and the New Orleans and Houston leg runs through it.

### Vermilionville (from Lake Charles)
- treatment: billboard
- leg: lake_charles_la_us -> lafayette_la_us
- at_mi: 65.8
- spoken: Billboard: Vermilionville, ahead in Lafayette. A bayou village kept between seventeen sixty-five and eighteen ninety, Acadian, Creole and Native. Leave the century in the truck.

### Vermilionville (from Beaumont)
- treatment: billboard
- leg: beaumont_tx_us -> lafayette_la_us
- at_mi: 122.5
- spoken: Billboard: Vermilionville, ahead in Lafayette. A bayou village kept between seventeen sixty-five and eighteen ninety, Acadian, Creole and Native. Leave the century in the truck.

### Vermilionville (from Alexandria)
- treatment: billboard
- leg: alexandria_la_us -> lafayette_la_us
- at_mi: 78.0
- spoken: Billboard: Vermilionville, ahead in Lafayette. A bayou village kept between seventeen sixty-five and eighteen ninety, Acadian, Creole and Native. Leave the century in the truck.

### Vermilionville (from Baton Rouge)
- treatment: billboard
- leg: baton_rouge_la_us -> lafayette_la_us
- at_mi: 42.0
- spoken: Billboard: Vermilionville, ahead in Lafayette. A bayou village kept between seventeen sixty-five and eighteen ninety, Acadian, Creole and Native. Leave the century in the truck.

### Vermilionville (from New Orleans)
- treatment: billboard
- leg: new_orleans_la_us -> lafayette_la_us
- at_mi: 127.0
- spoken: Billboard: Vermilionville, ahead in Lafayette. A bayou village kept between seventeen sixty-five and eighteen ninety, Acadian, Creole and Native. Leave the century in the truck.

### Vermilionville (westbound)
- treatment: billboard
- leg: new_orleans_la_us -> houston_tx_us
- at_mi: 127.0
- spoken: Billboard: Vermilionville, ahead in Lafayette. A bayou village kept between seventeen sixty-five and eighteen ninety, Acadian, Creole and Native. Leave the century in the truck.

### Vermilionville (eastbound)
- treatment: billboard
- leg: houston_tx_us -> new_orleans_la_us
- at_mi: 203.0
- spoken: Billboard: Vermilionville, ahead in Lafayette. A bayou village kept between seventeen sixty-five and eighteen ninety, Acadian, Creole and Native. Leave the century in the truck.

## Duck Commander, West Monroe (I-20)

The Robertson family's duck call company, 117 Kings Lane: store Monday to
Saturday, and a museum of fifteen galleries on the family, Duck Dynasty and
The Blind (duckcommander.com, "Visit us"). The legs list no West Monroe exit
numbers, so the signs read "ahead". Arriving from Vicksburg the leg ends in
Monroe before West Monroe, and leaving Monroe westbound it is four miles
behind the start, so those get none.

### Duck Commander (eastbound)
- treatment: billboard
- leg: ruston_la_us -> monroe_la_us
- at_mi: 21.0
- spoken: Billboard: Duck Commander, ahead in West Monroe. The Robertsons' duck call company, with a museum of fifteen galleries about Duck Dynasty. Beards optional.

### Duck Commander (eastbound)
- treatment: billboard
- leg: dallas_tx_us -> atlanta_ga_us
- at_mi: 272.5
- spoken: Billboard: Duck Commander, ahead in West Monroe. The Robertsons' duck call company, with a museum of fifteen galleries about Duck Dynasty. Beards optional.

### Duck Commander (westbound)
- treatment: billboard
- leg: atlanta_ga_us -> dallas_tx_us
- at_mi: 494.0
- spoken: Billboard: Duck Commander, ahead in West Monroe. The Robertsons' duck call company, with a museum of fifteen galleries about Duck Dynasty. Beards optional.

# Kansas

## The Eisenhower Presidential Library, Abilene (I-70 Exit 275)

Library, museum and boyhood home, 200 SE 4th Street, reached from Exit 275
by K-15, Buckeye Avenue; open Tuesday to Sunday (eisenhowerlibrary.gov).
The Interstate System was renamed the Dwight D. Eisenhower System of
Interstate and Defense Highways on October 15, 1990, Public Law 101-427
(FHWA, highways.dot.gov history).

### Eisenhower Library (westbound)
- treatment: billboard
- leg: junction_city_ks_us -> salina_ks_us
- at_mi: 21.8
- spoken: Billboard: The Eisenhower Presidential Library, next exit in Abilene, where he grew up. The whole interstate system is named for him, this road included.

### Eisenhower Library (westbound)
- treatment: billboard
- leg: kansas_city_mo_us -> denver_co_us
- at_mi: 149.1
- spoken: Billboard: The Eisenhower Presidential Library, next exit in Abilene, where he grew up. The whole interstate system is named for him, this road included.

### Eisenhower Library (eastbound)
- treatment: billboard
- leg: salina_ks_us -> junction_city_ks_us
- at_mi: 24.0
- spoken: Billboard: The Eisenhower Presidential Library, next exit in Abilene, where he grew up. The whole interstate system is named for him, this road included.

### Eisenhower Library (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 450.6
- spoken: Billboard: The Eisenhower Presidential Library, next exit in Abilene, where he grew up. The whole interstate system is named for him, this road included.

## The Sternberg Museum of Natural History, Hays (I-70 Exit 159)

Fort Hays State University's museum, 3000 Sternberg Drive, from Exit 159
south and east on 27th Street (sternberg.fhsu.edu, hours and directions).
Its "Fish-within-a-Fish" is a fourteen-foot Xiphactinus with a six-foot
Gillicus inside, collected by George F. Sternberg in 1952; the big fish
seems to have died soon after swallowing it (Wikipedia, "Xiphactinus").
Westbound, Exits 161 and 159 are 2.3 miles apart and the sign stands
between them. The Colby leg and the three US 183 legs end in Hays and list
no I-70 exits, so those signs read "ahead".

### Sternberg Museum (westbound)
- treatment: billboard
- leg: salina_ks_us -> hays_ks_us
- at_mi: 94.3
- spoken: Billboard: The Sternberg Museum, next exit in Hays. The famous fossil is a fourteen-foot fish with a six-foot fish inside it. Chew your lunch.

### Sternberg Museum (westbound)
- treatment: billboard
- leg: kansas_city_mo_us -> denver_co_us
- at_mi: 263.9
- spoken: Billboard: The Sternberg Museum, next exit in Hays. The famous fossil is a fourteen-foot fish with a six-foot fish inside it. Chew your lunch.

### Sternberg Museum (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 335.8
- spoken: Billboard: The Sternberg Museum, next exit in Hays. The famous fossil is a fourteen-foot fish with a six-foot fish inside it. Chew your lunch.

### Sternberg Museum (eastbound)
- treatment: billboard
- leg: colby_ks_us -> hays_ks_us
- at_mi: 97.0
- spoken: Billboard: The Sternberg Museum, ahead in Hays. The famous fossil is a fourteen-foot fish with a six-foot fish inside it. Chew your lunch.

### Sternberg Museum (from Dodge City)
- treatment: billboard
- leg: dodge_city_ks_us -> hays_ks_us
- at_mi: 106.3
- spoken: Billboard: The Sternberg Museum, ahead in Hays. The famous fossil is a fourteen-foot fish with a six-foot fish inside it. Chew your lunch.

### Sternberg Museum (from Great Bend)
- treatment: billboard
- leg: great_bend_ks_us -> hays_ks_us
- at_mi: 51.3
- spoken: Billboard: The Sternberg Museum, ahead in Hays. The famous fossil is a fourteen-foot fish with a six-foot fish inside it. Chew your lunch.

### Sternberg Museum (from Kearney)
- treatment: billboard
- leg: kearney_ne_us -> hays_ks_us
- at_mi: 133.0
- spoken: Billboard: The Sternberg Museum, ahead in Hays. The famous fossil is a fourteen-foot fish with a six-foot fish inside it. Chew your lunch.

## The Cosmosphere, Hutchinson (city node)

Space museum, 1100 North Plum Street. Its Apollo 13 command module,
Odyssey, was restored by the museum's SpaceWorks and is on display, its
skin still marked from reentry; open daily (cosmo.org; Missouri
Independent, April 2026; collectSPACE). Hutchinson ends three legs, and
the Dodge City to Wichita leg passes South Hutchinson; each sign is nine to
thirteen miles out.

### The Cosmosphere (from Great Bend)
- treatment: billboard
- leg: great_bend_ks_us -> hutchinson_ks_us
- at_mi: 50.5
- spoken: Billboard: The Cosmosphere, ahead in Hutchinson. The real Apollo Thirteen capsule is inside, still marked from the ride home. Your trip has already gone better.

### The Cosmosphere (from Salina)
- treatment: billboard
- leg: salina_ks_us -> hutchinson_ks_us
- at_mi: 52.0
- spoken: Billboard: The Cosmosphere, ahead in Hutchinson. The real Apollo Thirteen capsule is inside, still marked from the ride home. Your trip has already gone better.

### The Cosmosphere (from Wichita)
- treatment: billboard
- leg: wichita_ks_us -> hutchinson_ks_us
- at_mi: 38.0
- spoken: Billboard: The Cosmosphere, ahead in Hutchinson. The real Apollo Thirteen capsule is inside, still marked from the ride home. Your trip has already gone better.

### The Cosmosphere (eastbound)
- treatment: billboard
- leg: dodge_city_ks_us -> wichita_ks_us
- at_mi: 107.0
- spoken: Billboard: The Cosmosphere, ahead in Hutchinson. The real Apollo Thirteen capsule is inside, still marked from the ride home. Your trip has already gone better.

### The Cosmosphere (westbound)
- treatment: billboard
- leg: wichita_ks_us -> dodge_city_ks_us
- at_mi: 37.2
- spoken: Billboard: The Cosmosphere, ahead in Hutchinson. The real Apollo Thirteen capsule is inside, still marked from the ride home. Your trip has already gone better.

## Lindsborg, Little Sweden (I-135 Exit 72)

Founded in 1869 by Swedish immigrants, "Little Sweden, U.S.A.", with the
Wild Dala horses, large painted fiberglass Dala horses, around town since
2000 (Wikipedia, "Lindsborg, Kansas"; Roadside America; visitlindsborg.com).
Exit 72 is the Lindsborg exit (iExit, I-135 Exit 72). The Hutchinson and
Dodge City legs reach Salina on I-135 but list no exits; Exit 72 is placed
on them by the Lindsborg projection and the Salina to Wichita leg's
distances.

### Lindsborg (southbound)
- treatment: billboard
- leg: salina_ks_us -> wichita_ks_us
- at_mi: 20.6
- spoken: Billboard: Lindsborg, next exit. Little Sweden, U.S.A., settled by Swedes in eighteen sixty-nine, with painted Dala horses on the sidewalks. None of them need feeding.

### Lindsborg (northbound)
- treatment: billboard
- leg: wichita_ks_us -> salina_ks_us
- at_mi: 65.8
- spoken: Billboard: Lindsborg, next exit. Little Sweden, U.S.A., settled by Swedes in eighteen sixty-nine, with painted Dala horses on the sidewalks. None of them need feeding.

### Lindsborg (northbound)
- treatment: billboard
- leg: hutchinson_ks_us -> salina_ks_us
- at_mi: 40.0
- spoken: Billboard: Lindsborg, next exit. Little Sweden, U.S.A., settled by Swedes in eighteen sixty-nine, with painted Dala horses on the sidewalks. None of them need feeding.

### Lindsborg (southbound)
- treatment: billboard
- leg: salina_ks_us -> hutchinson_ks_us
- at_mi: 20.3
- spoken: Billboard: Lindsborg, next exit. Little Sweden, U.S.A., settled by Swedes in eighteen sixty-nine, with painted Dala horses on the sidewalks. None of them need feeding.

### Lindsborg (northbound)
- treatment: billboard
- leg: dodge_city_ks_us -> salina_ks_us
- at_mi: 158.0
- spoken: Billboard: Lindsborg, next exit. Little Sweden, U.S.A., settled by Swedes in eighteen sixty-nine, with painted Dala horses on the sidewalks. None of them need feeding.

### Lindsborg (southbound)
- treatment: billboard
- leg: salina_ks_us -> dodge_city_ks_us
- at_mi: 20.3
- spoken: Billboard: Lindsborg, next exit. Little Sweden, U.S.A., settled by Swedes in eighteen sixty-nine, with painted Dala horses on the sidewalks. None of them need feeding.

## Strataca, Hutchinson (city node)

The underground salt museum, 3650 East Avenue G: an elevator ride 650 feet
down into a working salt mine (the Hutchinson Salt Company's), the only
one of fifteen U.S. salt mines open to tourists (Wikipedia, "Strataca";
Kansas Sampler, 8 Wonders of Kansas). Same approaches as the Cosmosphere,
each at least 2.2 miles from that sign; four to nine miles out.

### Strataca (from Great Bend)
- treatment: billboard
- leg: great_bend_ks_us -> hutchinson_ks_us
- at_mi: 54.0
- spoken: Billboard: Strataca, ahead in Hutchinson. An elevator drops six hundred fifty feet into a working salt mine. Lowest point on your whole route.

### Strataca (from Salina)
- treatment: billboard
- leg: salina_ks_us -> hutchinson_ks_us
- at_mi: 59.5
- spoken: Billboard: Strataca, ahead in Hutchinson. An elevator drops six hundred fifty feet into a working salt mine. Lowest point on your whole route.

### Strataca (from Wichita)
- treatment: billboard
- leg: wichita_ks_us -> hutchinson_ks_us
- at_mi: 43.0
- spoken: Billboard: Strataca, ahead in Hutchinson. An elevator drops six hundred fifty feet into a working salt mine. Lowest point on your whole route.

### Strataca (eastbound)
- treatment: billboard
- leg: dodge_city_ks_us -> wichita_ks_us
- at_mi: 112.5
- spoken: Billboard: Strataca, ahead in Hutchinson. An elevator drops six hundred fifty feet into a working salt mine. Lowest point on your whole route.

### Strataca (westbound)
- treatment: billboard
- leg: wichita_ks_us -> dodge_city_ks_us
- at_mi: 43.0
- spoken: Billboard: Strataca, ahead in Hutchinson. An elevator drops six hundred fifty feet into a working salt mine. Lowest point on your whole route.

## Rolling Hills Zoo, Salina (I-70 Exit 244)

Zoo and wildlife museum two miles south of Exit 244, 625 North Hedville
Road, open every day but four holidays; reopened June 2026 after storm
damage (rollinghillszoo.org; KWCH, June 12, 2026). Exit 249 may sit
between Exits 250 and 244 without appearing in the legs' lists, so the
westbound signs stand 1.8 miles before Exit 244, past it.

### Rolling Hills Zoo (westbound)
- treatment: billboard
- leg: salina_ks_us -> hays_ks_us
- at_mi: 9.2
- spoken: Billboard: Rolling Hills Zoo, next exit, two miles south. A zoo and a wildlife museum among the wheat fields. The cows you passed were free.

### Rolling Hills Zoo (westbound)
- treatment: billboard
- leg: kansas_city_mo_us -> denver_co_us
- at_mi: 179.3
- spoken: Billboard: Rolling Hills Zoo, next exit, two miles south. A zoo and a wildlife museum among the wheat fields. The cows you passed were free.

### Rolling Hills Zoo (eastbound)
- treatment: billboard
- leg: hays_ks_us -> salina_ks_us
- at_mi: 85.2
- spoken: Billboard: Rolling Hills Zoo, next exit, two miles south. A zoo and a wildlife museum among the wheat fields. The cows you passed were free.

### Rolling Hills Zoo (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 420.1
- spoken: Billboard: Rolling Hills Zoo, next exit, two miles south. A zoo and a wildlife museum among the wheat fields. The cows you passed were free.

## Kinsley, Midway U.S.A. (US 50 and US 56)

The sign beside a steam locomotive in a park on the west side of Kinsley,
by the US 50 and US 56 junction: New York 1,561 miles, San Francisco
1,561 miles; first put up in February 1940 and still there (KCUR and KMUW,
August 2026). A town sign before the town on both roads.

### Kinsley (eastbound)
- treatment: billboard
- leg: dodge_city_ks_us -> salina_ks_us
- at_mi: 25.0
- spoken: Billboard: Kinsley, ahead, Midway U.S.A. Its sign says fifteen hundred sixty-one miles to New York and the same to San Francisco. Halfway to somewhere.

### Kinsley (eastbound)
- treatment: billboard
- leg: dodge_city_ks_us -> wichita_ks_us
- at_mi: 25.0
- spoken: Billboard: Kinsley, ahead, Midway U.S.A. Its sign says fifteen hundred sixty-one miles to New York and the same to San Francisco. Halfway to somewhere.

### Kinsley (westbound)
- treatment: billboard
- leg: salina_ks_us -> dodge_city_ks_us
- at_mi: 135.0
- spoken: Billboard: Kinsley, ahead, Midway U.S.A. Its sign says fifteen hundred sixty-one miles to New York and the same to San Francisco. Halfway to somewhere.

### Kinsley (westbound)
- treatment: billboard
- leg: wichita_ks_us -> dodge_city_ks_us
- at_mi: 117.0
- spoken: Billboard: Kinsley, ahead, Midway U.S.A. Its sign says fifteen hundred sixty-one miles to New York and the same to San Francisco. Halfway to somewhere.

## The Hays House, Council Grove (K-177)

Hays House 1857 Restaurant and Tavern, 112 West Main, opened by Seth Hays
on the Santa Fe Trail; the oldest continuously operating restaurant west
of the Mississippi; open daily (Kansas Sampler, 8 Wonders of Kansas
Cuisine; National Trust, "Saving Places"). The Emporia to Junction City
leg runs K-177 through town; the leg's own Post Office Oak Museum callout
is in Council Grove too.

### The Hays House (northbound)
- treatment: billboard
- leg: emporia_ks_us -> junction_city_ks_us
- at_mi: 29.0
- spoken: Billboard: The Hays House, ahead in Council Grove. Feeding Santa Fe Trail travelers since eighteen fifty-seven without a break. You qualify.

### The Hays House (southbound)
- treatment: billboard
- leg: junction_city_ks_us -> emporia_ks_us
- at_mi: 35.5
- spoken: Billboard: The Hays House, ahead in Council Grove. Feeding Santa Fe Trail travelers since eighteen fifty-seven without a break. You qualify.

## Little Jerusalem Badlands State Park (US 83)

Kansas's largest Niobrara chalk formation, spires more than 100 feet tall
from a sea 85 million years ago; opened October 2019; day use, sunrise to
sunset, on marked trails. From US 83, 22 miles south of Oakley, west 3.5
miles on Gold Road and north a mile (ksoutdoors.gov; The Nature
Conservancy). The leg's nearest point is about three miles from it.

### Little Jerusalem (northbound)
- treatment: billboard
- leg: garden_city_ks_us -> colby_ks_us
- at_mi: 45.0
- spoken: Billboard: Little Jerusalem Badlands State Park, ahead, a few miles west. Hundred-foot chalk spires left by a sea. Yes, a sea, in Kansas.

### Little Jerusalem (southbound)
- treatment: billboard
- leg: colby_ks_us -> garden_city_ks_us
- at_mi: 38.0
- spoken: Billboard: Little Jerusalem Badlands State Park, ahead, a few miles west. Hundred-foot chalk spires left by a sea. Yes, a sea, in Kansas.

## The Pony Express Barn, Marysville (US 77)

106 South Eighth Street: the only original Pony Express home station still
standing on its original site, from 1859 (Marysville Chamber listing,
2026 hours; nps.gov, "Marysville Pony Express Barn"). The US 77 leg passes
through Marysville.

### Pony Express Barn (southbound)
- treatment: billboard
- leg: lincoln_ne_us -> junction_city_ks_us
- at_mi: 64.0
- spoken: Billboard: The Pony Express Barn, ahead in Marysville, the last home station still on its original ground. The mail goes by truck now.

### Pony Express Barn (northbound)
- treatment: billboard
- leg: junction_city_ks_us -> lincoln_ne_us
- at_mi: 67.0
- spoken: Billboard: The Pony Express Barn, ahead in Marysville, the last home station still on its original ground. The mail goes by truck now.

## The Dalton Defenders Museum, Coffeyville (city node)

On October 5, 1892 the Dalton Gang rode in to rob two banks at once; the
museum, opened 1963 for the townspeople who died stopping them, is now at
814 Walnut across from the bank they tried; open daily (Coffeyville
Historical Society, coffeyvillehistory.com; Humanities Kansas). One leg
ends there.

### Dalton Defenders Museum (from Bartlesville)
- treatment: billboard
- leg: bartlesville_ok_us -> coffeyville_ks_us
- at_mi: 29.5
- spoken: Billboard: The Dalton Defenders Museum, ahead in Coffeyville. The Dalton Gang tried to rob two banks at once here in eighteen ninety-two. The town objected.

## Lee Richardson Zoo, Garden City (city node)

312 East Finnup Drive; walk-in entry free, a drive-through pass sold per
vehicle; open daily (leerichardsonzoo.org, "Hours"). Garden City ends four
legs.

### Lee Richardson Zoo (from Dodge City)
- treatment: billboard
- leg: dodge_city_ks_us -> garden_city_ks_us
- at_mi: 42.0
- spoken: Billboard: Lee Richardson Zoo, ahead in Garden City. Walking in is free; driving through costs extra. Even the zoo has a drive-through.

### Lee Richardson Zoo (from Liberal)
- treatment: billboard
- leg: liberal_ks_us -> garden_city_ks_us
- at_mi: 55.0
- spoken: Billboard: Lee Richardson Zoo, ahead in Garden City. Walking in is free; driving through costs extra. Even the zoo has a drive-through.

### Lee Richardson Zoo (from Colby)
- treatment: billboard
- leg: colby_ks_us -> garden_city_ks_us
- at_mi: 95.0
- spoken: Billboard: Lee Richardson Zoo, ahead in Garden City. Walking in is free; driving through costs extra. Even the zoo has a drive-through.

### Lee Richardson Zoo (from Amarillo)
- treatment: billboard
- leg: amarillo_tx_us -> garden_city_ks_us
- at_mi: 218.0
- spoken: Billboard: Lee Richardson Zoo, ahead in Garden City. Walking in is free; driving through costs extra. Even the zoo has a drive-through.

## Dorothy's House, Liberal (city node)

567 East Cedar Street: an authentic 1907 Kansas farmhouse kept as
Dorothy's house, a walk-through Land of Oz, and a free local history
museum; open Tuesday to Sunday (dorothyshouse.com). Liberal starts two
legs and the Garden City to Amarillo leg runs through it.

### Dorothy's House (from Dodge City)
- treatment: billboard
- leg: dodge_city_ks_us -> liberal_ks_us
- at_mi: 70.5
- spoken: Billboard: Dorothy's House, ahead in Liberal. A real nineteen-oh-seven Kansas farmhouse, and a walk through the Land of Oz. The twister is not included.

### Dorothy's House (from Garden City)
- treatment: billboard
- leg: garden_city_ks_us -> liberal_ks_us
- at_mi: 56.0
- spoken: Billboard: Dorothy's House, ahead in Liberal. A real nineteen-oh-seven Kansas farmhouse, and a walk through the Land of Oz. The twister is not included.

### Dorothy's House (southbound)
- treatment: billboard
- leg: garden_city_ks_us -> amarillo_tx_us
- at_mi: 58.0
- spoken: Billboard: Dorothy's House, ahead in Liberal. A real nineteen-oh-seven Kansas farmhouse, and a walk through the Land of Oz. The twister is not included.

### Dorothy's House (northbound)
- treatment: billboard
- leg: amarillo_tx_us -> garden_city_ks_us
- at_mi: 148.5
- spoken: Billboard: Dorothy's House, ahead in Liberal. A real nineteen-oh-seven Kansas farmhouse, and a walk through the Land of Oz. The twister is not included.

## The Prairie Museum of Art and History, Colby (I-70 Exit 53)

1905 South Franklin Avenue, with the Cooper Barn, the largest barn in
Kansas and one of the 8 Wonders of Kansas Architecture; open daily April
to October, shorter winter hours (prairiemuseum.org). On I-70 the signs
stand between Exits 62 and 53 (westbound, clear of the Monument Rocks
callout) or 45 and 53 (eastbound); the two US 83 legs end in Colby and read
"ahead".

### Prairie Museum (westbound)
- treatment: billboard
- leg: hays_ks_us -> colby_ks_us
- at_mi: 104.8
- spoken: Billboard: The Prairie Museum, next exit in Colby, with the Cooper Barn, the biggest barn in Kansas. The truck stays outside.

### Prairie Museum (westbound)
- treatment: billboard
- leg: kansas_city_mo_us -> denver_co_us
- at_mi: 365.5
- spoken: Billboard: The Prairie Museum, next exit in Colby, with the Cooper Barn, the biggest barn in Kansas. The truck stays outside.

### Prairie Museum (eastbound)
- treatment: billboard
- leg: burlington_co_us -> colby_ks_us
- at_mi: 64.7
- spoken: Billboard: The Prairie Museum, next exit in Colby, with the Cooper Barn, the biggest barn in Kansas. The truck stays outside.

### Prairie Museum (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 230.8
- spoken: Billboard: The Prairie Museum, next exit in Colby, with the Cooper Barn, the biggest barn in Kansas. The truck stays outside.

### Prairie Museum (from Garden City)
- treatment: billboard
- leg: garden_city_ks_us -> colby_ks_us
- at_mi: 95.0
- spoken: Billboard: The Prairie Museum, ahead in Colby, with the Cooper Barn, the biggest barn in Kansas. The truck stays outside.

### Prairie Museum (from North Platte)
- treatment: billboard
- leg: north_platte_ne_us -> colby_ks_us
- at_mi: 135.0
- spoken: Billboard: The Prairie Museum, ahead in Colby, with the Cooper Barn, the biggest barn in Kansas. The truck stays outside.

# Optional block: approved signs in their missing directions

Eight places already have one approved placed sign each: six on the Kansas
City to Denver leg, westbound only; Boot Hill on the Hays to Dodge City
leg, arriving from Hays; and the Tallest Capitol on the Gulfport to Baton
Rouge leg, arriving from the east. A driver eastbound on I-70, on any of
the shorter I-70 legs, or arriving in Dodge City or Baton Rouge by any other
road, hears none of them. These blocks reuse each record's approved copy
unchanged and place it the same distance before its exit or city, in the
directions and on the legs that lack it. Every copy says "ahead" or
describes the town arrived in, so it holds from either side. Delete this
whole part to keep the sheet to new attractions only.

## The Oz Museum, Wamego (I-70 Exit 328)

The westbound record stands 10.2 miles before Exit 328.

### Oz Museum (westbound)
- treatment: billboard
- leg: topeka_ks_us -> junction_city_ks_us
- at_mi: 24.5
- spoken: Billboard: The Oz Museum is ahead in Wamego. Follow the yellow brick road off Interstate seventy, because there is no place like home and apparently no place like Kansas either.

### Oz Museum (eastbound)
- treatment: billboard
- leg: junction_city_ks_us -> topeka_ks_us
- at_mi: 20.0
- spoken: Billboard: The Oz Museum is ahead in Wamego. Follow the yellow brick road off Interstate seventy, because there is no place like home and apparently no place like Kansas either.

### Oz Museum (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 494.0
- spoken: Billboard: The Oz Museum is ahead in Wamego. Follow the yellow brick road off Interstate seventy, because there is no place like home and apparently no place like Kansas either.

## The world's largest Czech egg, Wilson, and the Garden of Eden, Lucas (I-70 Exit 206)

Both are reached from Exit 206; Lucas is sixteen miles north on K-232. The
westbound records stand 9.4 and 5.4 miles before the exit. Eastbound, the
Dorrance village callout sits between those distances, so the Garden of
Eden goes first, about nine miles out, and the egg second, about four.

### World's Largest Czech Egg (westbound)
- treatment: billboard
- leg: salina_ks_us -> hays_ks_us
- at_mi: 40.1
- spoken: Billboard: The world's largest Czech egg is ahead in Wilson, the Czech Capital of Kansas. It stands twenty feet tall and is covered in hand-painted folk art, because every small town deserves one enormous thing.

### The Garden of Eden (westbound)
- treatment: billboard
- leg: salina_ks_us -> hays_ks_us
- at_mi: 44.1
- spoken: Billboard: The Garden of Eden is ahead in Lucas. Its front yard mixes concrete Bible scenes, populist politics, and roadside folk art unlike anything else.

### The Garden of Eden (eastbound)
- treatment: billboard
- leg: hays_ks_us -> salina_ks_us
- at_mi: 39.4
- spoken: Billboard: The Garden of Eden is ahead in Lucas. Its front yard mixes concrete Bible scenes, populist politics, and roadside folk art unlike anything else.

### World's Largest Czech Egg (eastbound)
- treatment: billboard
- leg: hays_ks_us -> salina_ks_us
- at_mi: 44.1
- spoken: Billboard: The world's largest Czech egg is ahead in Wilson, the Czech Capital of Kansas. It stands twenty feet tall and is covered in hand-painted folk art, because every small town deserves one enormous thing.

### The Garden of Eden (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 374.5
- spoken: Billboard: The Garden of Eden is ahead in Lucas. Its front yard mixes concrete Bible scenes, populist politics, and roadside folk art unlike anything else.

### World's Largest Czech Egg (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 379.2
- spoken: Billboard: The world's largest Czech egg is ahead in Wilson, the Czech Capital of Kansas. It stands twenty feet tall and is covered in hand-painted folk art, because every small town deserves one enormous thing.

## The Cathedral of the Plains, Victoria (I-70 Exit 168)

The westbound record stands 9.1 miles before Exit 168. Eastbound, Victoria
is the second exit past Hays, so those signs stand just east of Hays, four
to seven miles out, clear of the Sternberg sign.

### Cathedral of the Plains (westbound)
- treatment: billboard
- leg: salina_ks_us -> hays_ks_us
- at_mi: 77.0
- spoken: Billboard: The Cathedral of the Plains is ahead at Victoria. Twin limestone spires rise over wheat country as though somebody imported Europe and forgot to return it.

### Cathedral of the Plains (eastbound)
- treatment: billboard
- leg: hays_ks_us -> salina_ks_us
- at_mi: 7.0
- spoken: Billboard: The Cathedral of the Plains is ahead at Victoria. Twin limestone spires rise over wheat country as though somebody imported Europe and forgot to return it.

### Cathedral of the Plains (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 339.5
- spoken: Billboard: The Cathedral of the Plains is ahead at Victoria. Twin limestone spires rise over wheat country as though somebody imported Europe and forgot to return it.

## The giant Buffalo Bill, Oakley (I-70 Exit 70)

The westbound record stands 4.2 miles before Exit 70. On Hays to Colby the
Fick Fossil Museum callout sits there, so that sign is 5.0 miles out.

### Giant Buffalo Bill (westbound)
- treatment: billboard
- leg: hays_ks_us -> colby_ks_us
- at_mi: 85.7
- spoken: Billboard: A giant Buffalo Bill is ahead near Oakley, forever charging a bronze buffalo on horseback. He is bigger than life, and life on the plains was already pretty big. Please stop for real buffalo too.

### Giant Buffalo Bill (eastbound)
- treatment: billboard
- leg: colby_ks_us -> hays_ks_us
- at_mi: 14.0
- spoken: Billboard: A giant Buffalo Bill is ahead near Oakley, forever charging a bronze buffalo on horseback. He is bigger than life, and life on the plains was already pretty big. Please stop for real buffalo too.

### Giant Buffalo Bill (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 244.5
- spoken: Billboard: A giant Buffalo Bill is ahead near Oakley, forever charging a bronze buffalo on horseback. He is bigger than life, and life on the plains was already pretty big. Please stop for real buffalo too.

## The world's largest easel, Goodland (I-70 Exits 17 and 19)

The westbound record stands 4.7 miles before Exit 19, Goodland's first
exit from the east; eastbound signs stand the same distance before Exit 17.

### World's Largest Easel (westbound)
- treatment: billboard
- leg: colby_ks_us -> burlington_co_us
- at_mi: 32.3
- spoken: Billboard: The world's largest easel is ahead in Goodland, holding a giant sunflower painting because Kansas found ordinary roadside art too close to the ground.

### World's Largest Easel (eastbound)
- treatment: billboard
- leg: burlington_co_us -> colby_ks_us
- at_mi: 25.3
- spoken: Billboard: The world's largest easel is ahead in Goodland, holding a giant sunflower painting because Kansas found ordinary roadside art too close to the ground.

### World's Largest Easel (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 191.6
- spoken: Billboard: The world's largest easel is ahead in Goodland, holding a giant sunflower painting because Kansas found ordinary roadside art too close to the ground.

## Boot Hill, Dodge City (city node)

The existing record faces drivers arriving from Hays, 3.0 miles out. These
face drivers arriving on the other four roads, three to five miles out.

### Boot Hill (from Liberal)
- treatment: billboard
- leg: liberal_ks_us -> dodge_city_ks_us
- at_mi: 79.0
- spoken: Billboard: Dodge City was once the wickedest little city in the West. Wyatt Earp and Bat Masterson kept the peace badly, while the losers went up to Boot Hill with their boots on. Get out of Dodge, or stay a while.

### Boot Hill (from Garden City)
- treatment: billboard
- leg: garden_city_ks_us -> dodge_city_ks_us
- at_mi: 49.0
- spoken: Billboard: Dodge City was once the wickedest little city in the West. Wyatt Earp and Bat Masterson kept the peace badly, while the losers went up to Boot Hill with their boots on. Get out of Dodge, or stay a while.

### Boot Hill (from Wichita)
- treatment: billboard
- leg: wichita_ks_us -> dodge_city_ks_us
- at_mi: 162.0
- spoken: Billboard: Dodge City was once the wickedest little city in the West. Wyatt Earp and Bat Masterson kept the peace badly, while the losers went up to Boot Hill with their boots on. Get out of Dodge, or stay a while.

### Boot Hill (from Salina)
- treatment: billboard
- leg: salina_ks_us -> dodge_city_ks_us
- at_mi: 177.0
- spoken: Billboard: Dodge City was once the wickedest little city in the West. Wyatt Earp and Bat Masterson kept the peace badly, while the losers went up to Boot Hill with their boots on. Get out of Dodge, or stay a while.

## The Tallest Capitol, Baton Rouge (city node)

The existing record faces drivers arriving from Gulfport, 2.7 miles out.
These face drivers arriving on the other six roads, and both directions of
the two I-10 legs that run through the city, three to five miles out.

### The Tallest Capitol (from Lafayette)
- treatment: billboard
- leg: lafayette_la_us -> baton_rouge_la_us
- at_mi: 53.0
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Tallest Capitol (from New Orleans)
- treatment: billboard
- leg: new_orleans_la_us -> baton_rouge_la_us
- at_mi: 77.0
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Tallest Capitol (from Hammond)
- treatment: billboard
- leg: hammond_la_us -> baton_rouge_la_us
- at_mi: 46.0
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Tallest Capitol (from Jackson)
- treatment: billboard
- leg: jackson_ms_us -> baton_rouge_la_us
- at_mi: 171.0
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Tallest Capitol (from Shreveport)
- treatment: billboard
- leg: shreveport_la_us -> baton_rouge_la_us
- at_mi: 231.0
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Tallest Capitol (from Natchez)
- treatment: billboard
- leg: natchez_ms_us -> baton_rouge_la_us
- at_mi: 88.0
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Tallest Capitol (from Houma)
- treatment: billboard
- leg: houma_la_us -> baton_rouge_la_us
- at_mi: 79.0
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Tallest Capitol (eastbound)
- treatment: billboard
- leg: lafayette_la_us -> new_orleans_la_us
- at_mi: 50.0
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Tallest Capitol (eastbound)
- treatment: billboard
- leg: houston_tx_us -> new_orleans_la_us
- at_mi: 262.0
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Tallest Capitol (westbound)
- treatment: billboard
- leg: new_orleans_la_us -> lafayette_la_us
- at_mi: 77.2
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Tallest Capitol (westbound)
- treatment: billboard
- leg: new_orleans_la_us -> houston_tx_us
- at_mi: 77.0
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

## Notes for the owner

Thirty-six new attractions and 152 new signs: Arkansas thirteen
attractions, fifty signs; Louisiana nine, forty-six; Kansas fourteen,
fifty-six. The optional block adds thirty-three more signs for eight places
that already have one approved sign each, 185 in all. A dry run of
`tools/bake_billboards.py` on this sheet resolves every leg and bakes all
185 (no `--write`). A spacing check against the baked legs found no
callout within 2.2 miles of any sign in its direction, counting the other
signs on this sheet. Every new line is spelled out with no digits and runs
twenty-one to twenty-six words. The jokes are original. All three states
allow commercial billboards; the only four that ban them are Alaska, Hawaii,
Maine and Vermont (Scenic America), which the game already gates.

Many of these legs start or end in a neighboring state (Texas, Oklahoma,
Missouri, Mississippi, Nebraska, Colorado, Georgia). Every sign here stands
in Arkansas, Louisiana or Kansas or on the approach to one of their
attractions, but if another state's sheet lands on the same leg, rerun the
2.2-mile check after merging.

Attractions, sources, and what was checked (all open as of the dates
given):

- **Eureka Springs.** https://en.wikipedia.org/wiki/Eureka_Springs,_Arkansas
  (whole town on the National Register since 1970; streets wind, few at
  right angles; no traffic lights) and the Northwest Arkansas
  Democrat-Gazette, November 2022, on the city weighing a roundabout rather
  than a light. Unsure: "not one traffic light" should be rechecked if the
  town has since added one.
- **Bathhouse Row, Hot Springs.**
  https://www.nps.gov/hosp/planyourvisit/thermal-springs.htm (water over
  four thousand years old, average 143 degrees, free jug fountains) and
  https://www.nps.gov/hosp/planyourvisit/park-brochure-continued.htm. The
  legs already say "Entering Hot Springs National Park" at the city; this
  sign is twelve miles out and says something different.
- **The Walmart Museum, Bentonville.**
  https://talkbusiness.net/2025/03/walmart-museum-to-open-friday-features-sam-walton-hologram/
  (reopened March 14, 2025; Sam Walton hologram answers questions; daily
  hours). Names the company plainly, no slogan.
- **Alma.** https://www.roadsideamerica.com/news/15403 (bronze Popeye
  unveiled April 2007) and https://encyclopediaofarkansas.net/?p=16359 and
  KNWA on Popeye Park. Unsure: whether the spinach-can water tower is still
  painted; the copy leaves it out. Skipped: the Fort Smith to Fayetteville
  leg passes Alma on I-49, which has no Alma exit of its own in the legs'
  lists. The eastbound sign on the Fort Smith leg is only three miles out,
  because that leg reaches I-40 in Van Buren.
- **Plum Bayou Mounds.**
  https://www.arkansas.com/state-parks/parks/plum-bayou-mounds-archeological-state-park
  (open Wednesday to Sunday; formerly Toltec Mounds) and
  https://archeology.uark.edu/who-we-are/research-stations/toltec-renamed-plum-bayou-mounds/
  (renamed November 2022 with tribal consultation; the Toltec name came
  from a mistaken belief). Mound A at 49.5 feet as the tallest in Arkansas
  is from arkansas.com. The joke is about the old misnaming, not the
  builders; it is the line most worth your ear.
- **Stuttgart.**
  https://encyclopediaofarkansas.net/entries/Worlds-Championship-Duck-Calling-Contest-3819
  (first contest November 24, 1936 on Main Street; winner Thomas E. Walsh
  called with his throat). The contest is every Thanksgiving weekend; the
  copy says only where and when it began, so it holds all year.
- **Gator Chateau, Jennings.** https://www.explorelouisiana.com/family-fun/gator-chateau
  (Exit 64, free, hold a baby alligator, released at about seven feet) and
  KPLC, February 2025 (Monday to Saturday, 9 to 5).
- **Breaux Bridge.** https://breauxbridgela.net/about/ and cajuncountry.org
  (named crawfish capital of the world by the legislature for the 1959
  centennial). Unsure: on Lafayette to Baton Rouge the sign is only 0.3
  miles before Exit 109, because the leg's Vermilion River callout at mile
  6.7 rules out anything earlier. Pronunciation: a screen reader may not say
  "Breaux" as "Bro"; the game already speaks Natchitoches as written.
- **The Abita Mystery House.** https://www.explorelouisiana.com/shopping/abita-mystery-house-ucm-museum
  (gas-station entrance, more than fifty thousand objects, Buford the
  Bassigator) and https://www.roadsideamerica.com/tip/3667 (daily, 10 to 5).
- **Natchitoches.** https://en.wikipedia.org/wiki/Natchitoches,_Louisiana
  and https://64parishes.org/entry/natchitoches-settlement (1714, four years
  before New Orleans; oldest permanent European settlement in the Louisiana
  Purchase). The copy says "European settlement", not "town", on purpose.
- **Middendorf's, Manchac.**
  https://www.wwno.org/show/louisiana-eats/2026-01-17/louisiana-eats
  (operating, thin-cut catfish since 1934) and 225 Baton Rouge (thick or
  thin; Exit 15).
- **The Eisenhower Presidential Library.** https://www.eisenhowerlibrary.gov/visit/visit-us
  (200 SE 4th Street, parking off K-15 Buckeye Avenue at Exit 275; Tuesday
  to Sunday) and https://highways.dot.gov/history/interstate-system/dwight-d-eisenhower-highway
  (system renamed for him October 15, 1990).
- **The Sternberg Museum.** https://sternberg.fhsu.edu/plan-a-visit/hours-and-admission/index.html
  (Exit 159, then 27th Street) and https://en.wikipedia.org/wiki/Xiphactinus
  (the fourteen-foot fish with a six-foot fish inside, 1952). Skipped: the
  legs leaving Hays, where the museum is behind the driver within three
  miles of the start.
- **The Cosmosphere.**
  https://missouriindependent.com/2026/04/20/repub/return-to-earth-at-this-kansas-space-museum-i-came-in-search-of-what-we-had-nearly-lost/
  (Odyssey on display, its skin still marked; 2026) and cosmo.org.
- **Lindsborg.** https://en.wikipedia.org/wiki/Lindsborg,_Kansas (1869,
  Swedish settlers, "Little Sweden"), https://www.roadsideamerica.com/tip/4511
  (the Wild Dala horses) and iExit for Exit 72. Unsure: the Hutchinson and
  Dodge City legs list no I-135 exits, so Exit 72 is estimated on them from
  the Lindsborg projection; a tenth or two either way does not change the
  copy.
- **Crystal Bridges.** https://en.wikipedia.org/wiki/Crystal_Bridges_Museum_of_American_Art
  (ravine, Crystal Spring, free general admission since 2011) and
  https://crystalbridges.org/news/crystal-bridges-to-open-highly-anticipated-expansion-june-6-and-7
  (expansion opened June 2026). Each Bentonville approach now carries
  three signs (Daisy, Walmart Museum, Crystal Bridges) within about eight
  miles; cut one if that reads as too many.
- **The Daisy Airgun Museum.** https://www.arkansas.com/rogers/landmarks/daisy-airgun-museum
  (202 West Walnut, Monday to Saturday) and Axios Northwest Arkansas,
  November 27, 2023 (Red Ryder made in northwest Arkansas). The closer
  nods at the film's famous warning without quoting it.
- **Thorncrown Chapel.** https://www.kval.com/amazing-america/thorncrown-chapel-is-one-of-arkansas-crown-jewels
  (425 windows, 6,000 square feet of glass, free, March through December).
- **The U.S. Marshals Museum.** https://encyclopediaofarkansas.net/entries/us-marshals-museum-8151/
  (opened July 1, 2023; star-shaped design) and
  https://talkbusiness.net/2026/04/marshals-museum-visitor-numbers-up-more-than-5-in-2025/.
  Unsure: on Russellville to Fort Smith the sign is only 3.5 miles out, the
  one slot the Alma, river and Van Buren callouts leave.
- **The Clinton Library.** https://en.wikipedia.org/wiki/Clinton_Presidential_Center
  (cantilevered over the river; full-scale Oval Office) and the National
  Archives July 4, 2026 calendar entry (open, special exhibit). An
  expansion is planned; the museum is open meanwhile. Ten signs, one per
  road into Little Rock.
- **Walnut Ridge.** https://encyclopediaofarkansas.net/?p=4073 (September
  18, 1964 plane change; 2011 Abbey Road monument; street renamed).
- **Queen Wilhelmina State Park.** https://en.wikipedia.org/wiki/Queen_Wilhelmina_State_Park
  and https://www.arkansas.com/state-parks/parks/queen-wilhelmina-state-park
  (lodge open year-round). Unsure: the park is a mountain drive west of
  Mena, roughly ten miles off the leg; neither source gives the mileage,
  so the copy says only "west of Mena". Drop it if that detour is too long
  for a billboard.
- **The Creole Nature Trail.** https://www.sulphurla.gov/640/Creole-Nature-Trail
  and https://www.visitlakecharles.org/blog/post/top-9-questions-about-the-creole-nature-trail/
  (180 miles, All-American Road since 2002, Adventure Point at Exit 20).
  Adventure Point's hours vary by source; the copy names the road, which is
  always open. The westbound Lake Charles signs stand under two miles from
  the city, the only room before the Calcasieu River callout.
- **Rayne.** https://en.wikipedia.org/wiki/Rayne,_Louisiana and Heart of
  Louisiana, "Frogs Everywhere" (130 painted frogs; Monsieur Jacques).
- **Vermilionville.** Group Tour Magazine and Explore Louisiana (1765 to
  1890; 23 acres; Tuesday to Sunday).
- **Duck Commander.** https://duckcommander.com/pages/visit-us (museum of
  fifteen galleries, store Monday to Saturday). "Beards optional" is about
  the show's family, not a group; your call.
- **Strataca.** https://en.wikipedia.org/wiki/Strataca (650 feet; the only
  tourist salt mine of fifteen). Hours there date from an older listing.
- **Rolling Hills Zoo.** https://www.rollinghillszoo.org/info (2026 season
  dates, daily) and KWCH, June 12, 2026 (reopened after storm damage).
- **Kinsley.** https://www.kcur.org/history/2026-08-11/kinsley-kansas-midway-usa-halfway-road-sign
  (the sign, its mileages, still standing August 2026).
- **The Hays House.** Kansas Sampler, 8 Wonders of Kansas Cuisine, and the
  National Trust (1857; oldest continuously operating restaurant west of
  the Mississippi). The leg also has a Post Office Oak Museum callout in
  Council Grove; the sign stands ten miles before either.
- **Little Jerusalem Badlands.** https://ksoutdoors.gov/State-Parks/Locations/Little-Jerusalem-Badlands
  and https://www.nature.org/en-us/get-involved/how-to-help/places-we-protect/little-jerusalem-badlands-state-park/
  (100-foot Niobrara chalk, 85 million years, Gold Road directions).
- **The Pony Express Barn.** nps.gov, "Marysville Pony Express Barn", and
  the Marysville chamber's 2026 hours (only original home station on its
  original site). Unsure: its hours may shorten after October.
- **The Dalton Defenders Museum.** https://www.coffeyvillehistory.com/dalton-defenders-museum
  (October 5, 1892; open daily). Townspeople died stopping the raid, and
  the museum is dedicated to them; "The town objected" is the dry register
  the Boot Hill sign uses, but it is the line to weigh.
- **Lee Richardson Zoo.** https://www.leerichardsonzoo.org/hours (walk-in
  free, per-vehicle drive-through pass, open now).
- **Dorothy's House.** https://www.dorothyshouse.com/ (1907 farmhouse,
  Land of Oz walk-through, Tuesday to Sunday). This is a second Oz sign in
  Kansas, on different roads from Wamego's.
- **The Prairie Museum.** https://www.prairiemuseum.org/ (Cooper Barn,
  largest barn in Kansas; hours April to October and winter).

The optional block reuses the copy already on the Kansas City to Denver,
Hays to Dodge City and Gulfport to Baton Rouge legs, unchanged, so it needs
no new approval of wording, only of placement. Those lines run thirty to
forty-one words, longer than the new ones. The Oz Museum also has a
statewide I-70 pool line, so a driver may hear both on one run.

Dropped:

- **Crater of Diamonds State Park, Murfreesboro.** Twenty-one miles from the
  nearest leg (I-30 and the Hot Springs to Texarkana leg).
- **Tabasco and Jungle Gardens, Avery Island.** Twenty-two miles from
  Lafayette; no leg runs US 90 south.
- **Poverty Point World Heritage Site.** Eighteen miles from I-20 Exit 153
  by three state highways, and an ancient earthwork site where a joke
  billboard fits poorly.
- **Wegner Crystal Mines, Mount Ida.** The US 270 leg already calls it out
  by name.
- **Tallgrass Prairie National Preserve.** The US 50 leg already says
  "Entering Tallgrass Prairie National Preserve"; a sign ahead of it would
  repeat it.
- **Big Well, Greensburg; Little House on the Prairie Museum,
  Independence.** No leg passes within five miles.
- **Fort Larned National Historic Site.** Five miles off US 56 on K-156,
  and a frontier-war fort where a joke billboard fits poorly. Pea Ridge
  National Military Park, on the US 62 leg, dropped for the same reason.
- **Kansas Barbed Wire Museum, La Crosse.** Closes in September and opens
  by appointment the rest of the year.
- **Arkansas Railroad Museum, Pine Bluff.** Three days a week, four hours a
  day, and no current confirmation.
- **Chicken Annie's and Chicken Mary's, Pittsburg.** Both open (KCUR, July
  2026), but see the Tulsa to Kansas City leg below: its spoken towns are in
  Missouri, so a sign about Pittsburg would land in the wrong state.
- **Honey Island Swamp tours, Slidell.** Operating, but the legs' Slidell
  interchange lists skip Exit 266 and mislabel others, so no placement
  could be made true.
- **Bonnie and Clyde Ambush Museum, Gibsland.** Current opening could not
  be confirmed.
- **Henderson swamp tours; LaPlace andouille; Scott boudin; Gonzales
  jambalaya; Crowley rice.** Same stretches as Breaux Bridge, Rayne and the
  Cajun country pool line; Breaux Bridge and Rayne kept as the better
  known, and the Cajun line already covers boudin.
- **Clinton Birthplace, Hope.** Exit 30 already carries the Hope sign both
  ways.
- **Coronado Heights, Lindsborg; the Greyhound Hall of Fame, Abilene; the
  High Plains Museum, Goodland; the Lucas Bowl Plaza.** Same exits as a
  kept sign; the better-known one kept.
- **Monroe's Biedenharn museum.** The first bottled Coca-Cola was in
  Vicksburg, not Monroe.
- **Johnny Cash's Dyess, the twine ball, the Oz Museum, Boot Hill, Hope,
  Cajun boudin.** Already in the pools or placed.

Found along the way (data, not this sheet):

- The Tulsa to Kansas City leg (US 69) has dense geometry running up US 69
  in Kansas (Pittsburg, Fort Scott, longitude 94.70 west), but its route
  points, checkpoints and village callouts follow I-49 in Missouri
  (Carthage at 129.4, Lamar at 153.3, Nevada at 178.9). A driver hears
  Missouri towns while the leg's road is in Kansas. Its state miles also say
  174 in Kansas.
- On the Hutchinson to Salina leg (K-61, joining I-135) the Smoky Hill River
  callout is at mile 42.3, about twenty-three miles from Salina; on the
  Salina to Wichita and Dodge City to Salina legs, over the same crossing,
  it is eleven to thirteen miles from Salina.
- The Dallas to St. Louis leg (labeled I-44) has the same split: its
  geometry and interchanges run I-30 and US 67 through Arkansas (Bryant,
  Mabelvale, Little Rock's airport exit, Walnut Ridge), while its
  checkpoints and callouts are Oklahoma I-44 (Claremore, the Blue Whale of
  Catoosa at 312.0, the World's Largest Totem Pole at 335.0). No sign here
  goes on it; the Clinton Library and Walnut Ridge would otherwise belong
  on it both ways.
