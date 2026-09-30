# Billboard audit fixes -- 2026-09-30

Placement fixes from the 2026-09-30 audit of every placed billboard. Every `leg:` is written the way
the driver reads the sign and `at_mi` counts from that end; `tools/bake_billboards.py` mirrors the
milepost onto a leg stored the other way round and records the facing. A billboard block whose name
is already on that leg replaces it, so a move along the same leg or a flip is one block; a move to
another leg is a remove block on the old leg followed by a billboard block on the new one. Copy is
unchanged: every `spoken:` is the current record's text.

Mileposts come from projecting each attraction onto the legs' route geometry (route points and
checkpoints where the geometry disagrees) and from the legs' interchange lists. "Next exit" signs
stand between the attraction's exit and the one before it; "ahead" signs mostly five to fifteen
miles out. Every placement is at least 2.2 miles from any other callout heard in the same direction
on its leg and silences nothing that is heard today.

## Signs on a road that does not pass the attraction

Each is removed from the leg it is on and, where a leg does pass the place, placed there facing the way the copy reads.

### Talladega
Talladega and the Superspeedway are on I-20 (exit 168 Talladega at travel 42.1 from Birmingham); US-280 passes 25 mi south.
- treatment: remove
- leg: birmingham_al_us -> opelika_al_us

### Talladega
Its new place, 9.1 miles before it.
- treatment: billboard
- leg: birmingham_al_us -> atlanta_ga_us
- at_mi: 33.0
- spoken: Billboard: Talladega is ahead, home to the biggest and fastest superspeedway in NASCAR. Cars run flat out in a pack around two and a half miles of high banking, and a movie taught the nation that if you ain't first, you're last.

### Giant Artichoke
Castroville is 8 mi NW of Salinas; this leg heads south away from it.
- treatment: remove
- leg: salinas_ca_us -> san_luis_obispo_ca_us

### Giant Artichoke
Its new place, 4.6 miles before it.
- treatment: billboard
- leg: san_jose_ca_us -> salinas_ca_us
- at_mi: 48.5
- spoken: Billboard: You are entering giant artichoke country. Castroville calls itself the Artichoke Center of the World and has supplied enough thorny vegetables to make dip a regional industry.

### Dinosaur Land
Dinosaur Land, US-522/340 at White Post, 29 mi off this leg's US-29; I-81 exit 307 (To Route 340) at 61.2.
- treatment: remove
- leg: washington_dc_us -> charlottesville_va_us

### Dinosaur Land
Its new place, 8.2 miles before it.
- treatment: billboard
- leg: harrisonburg_va_us -> winchester_va_us
- at_mi: 53.0
- spoken: Billboard: Dinosaur Land is ahead. Fiberglass monsters have ruled this Virginia roadside since your grandparents were children, and extinction has not slowed ticket sales.

### The Smallest Church in America
Christ's Chapel, South Newport GA, I-95 exit 67; that is 37 mi north of Brunswick, past this leg's end.
- treatment: remove
- leg: jacksonville_fl_us -> brunswick_ga_us

### The Smallest Church in America
Its new place, 4.3 miles before it.
- treatment: billboard
- leg: brunswick_ga_us -> savannah_ga_us
- at_mi: 32.6
- spoken: Billboard: The Smallest Church in America is ahead near South Newport. It has six seats, one tiny steeple, and absolutely no room for a megachurch coffee shop.

### Clyde Butcher Gallery
Clyde Butcher's gallery is on US 41, 19 miles south; no leg runs there and Exit 80 is already behind.
- treatment: remove
- leg: naples_fl_us -> miami_fl_us

### Ochopee Post Office
Ochopee's post office is on US 41, 17 miles south; no leg runs there and Exit 80 is already behind.
- treatment: remove
- leg: naples_fl_us -> miami_fl_us

### The Mermaids of Weeki Wachee
Weeki Wachee Springs is on US-19 at Spring Hill, 17.5 mi off I-75; it sits at the spring_hill_fl_us node.
- treatment: remove
- leg: ocala_fl_us -> tampa_fl_us

### The Mermaids of Weeki Wachee
Its new place, 8.0 miles before it.
- treatment: billboard
- leg: ocala_fl_us -> spring_hill_fl_us
- at_mi: 70.0
- spoken: Billboard: Weeki Wachee is the only city of live mermaids. Since nineteen forty-seven, young women in fish tails have performed underwater ballet in a natural spring, breathing from hidden air hoses for the crowd behind the glass. That could only happen in Florida.

### Is This Heaven?
Field of Dreams, 3 mi NE of Dyersville on US-20; this leg's route passes 13 mi south.
- treatment: remove
- leg: cedar_rapids_ia_us -> dubuque_ia_us

### Is This Heaven?
Its new place, 7.9 miles before it.
- treatment: billboard
- leg: waterloo_ia_us -> dubuque_ia_us
- at_mi: 58.9
- spoken: Billboard: The Field of Dreams is ahead at Dyersville. The baseball diamond carved from a cornfield for the movie is still here and still mowed. Is this heaven? No, it is Iowa.

### Kentucky's Giant Fork
The giant fork is at 1430 Uhls Rd north of Franklin KY, near I-65 (exit 6 KY-100 at 20.8), 80+ mi from the Cumberland Pkwy (roadsideamerica, Kentucky Living).
- treatment: remove
- leg: london_ky_us -> bowling_green_ky_us

### Kentucky's Giant Fork
Its new place, 5.8 miles before it.
- treatment: billboard
- leg: bowling_green_ky_us -> nashville_tn_us
- at_mi: 15.0
- spoken: Billboard: A giant fork is ahead. Kentucky already had bourbon barrels and racehorses, so it apparently needed silverware tall enough to threaten low aircraft.

### The Best Fudge Comes From Uranus
Uranus Fudge Factory, I-44 exit 163 (roadsideamerica); 22 mi off US-63.
- treatment: remove
- leg: columbia_mo_us -> rolla_mo_us

### The Best Fudge Comes From Uranus
Its new place, 6.8 miles before it.
- treatment: billboard
- leg: rolla_mo_us -> springfield_mo_us
- at_mi: 16.0
- spoken: Billboard: Uranus, Missouri, is ahead, home to the Uranus Fudge Factory and a motto the whole family will regret reading aloud. The fudge, they swear, is excellent.

### The Throwed Rolls
Lambert's Cafe is in Ozark, 17 mi south of Springfield on US-65 (Ozark checkpoint 17.2 on Springfield->Harrison).
- treatment: remove
- leg: kansas_city_mo_us -> springfield_mo_us

### The Throwed Rolls
Its new place, 5.9 miles before it.
- treatment: billboard
- leg: springfield_mo_us -> harrison_ar_us
- at_mi: 11.3
- spoken: Billboard: Lambert's Cafe is ahead, home of the throwed rolls. Waiters hurl hot dinner rolls across the room, and you are expected to catch them. Raise a hand or wear one.

### Carhenge
Carhenge is at Alliance, 67 miles north of I-80; no leg comes within 60 miles.
- treatment: remove
- leg: omaha_ne_us -> cheyenne_wy_us

### Ben and Jerry's
Waterbury is 11 mi past Montpelier on I-89; I-89 exit 10 is stored 12.5 on Montpelier->Burlington (travel 27.5 from Burlington).
- treatment: remove
- leg: albany_ny_us -> montpelier_vt_us

### Ben and Jerry's
Its new place, 8.8 miles before it.
- treatment: billboard
- leg: burlington_vt_us -> montpelier_vt_us
- at_mi: 18.7
- spoken: Billboard: Waterbury is ahead, home to the Ben and Jerry's factory tour. The ice cream is made here, and retired flavors rest in a real graveyard with little headstones. The samples are free, but the tombstones are emotionally complicated.

### Dinosaur Bar-B-Que
Dinosaur Bar-B-Que's central New York restaurant is in Syracuse, 46 mi off NY-12.
- treatment: remove
- leg: binghamton_ny_us -> utica_ny_us

### Dinosaur Bar-B-Que
Its new place, 9.0 miles before it.
- treatment: billboard
- leg: binghamton_ny_us -> syracuse_ny_us
- at_mi: 64.0
- spoken: Billboard: Central New York barbecue is ahead. Dinosaurs are extinct, but apparently they left enough sauce behind to open several restaurants.

### The Longest Beach
The Long Beach Peninsula is west on US 101; this leg turns up WA 401 at the bridge and never reaches it.
- treatment: remove
- leg: astoria_or_us -> olympia_wa_us

### Crater Lake
Crater Lake is 34 mi north of OR-140; the way in from this area is OR-62 off US-97 near Chiloquin (checkpoint 26.9).
- treatment: remove
- leg: medford_or_us -> klamath_falls_or_us

### Crater Lake
Its new place, 8.0 miles before it.
- treatment: billboard
- leg: klamath_falls_or_us -> eugene_or_us
- at_mi: 20.0
- spoken: Billboard: Crater Lake is ahead and uphill. The deepest lake in the country fills the blasted crater of a fallen volcano and glows an impossible blue. There is nothing else like it.

### The Shoe House
Haines Shoe House is on US-30 at Hellam, east of York, 14.5 mi off the Turnpike; Allentown->Baltimore passes it at 85.4.
- treatment: remove
- leg: harrisburg_pa_us -> philadelphia_pa_us

### The Shoe House
Its new place, 9.8 miles before it.
- treatment: billboard
- leg: allentown_pa_us -> baltimore_md_us
- at_mi: 75.6
- spoken: Billboard: The Haines Shoe House is ahead. This five-story house is shaped like a work boot and was built by a shoe salesman who understood that subtlety does not sell footwear.

### World's Largest Ball of Twine
No ball of twine in South Dakota; Darwin MN (US-12) is on Willmar->Minneapolis at 33.5; the other is Cawker City KS on US-24, no leg.
- treatment: remove
- leg: mitchell_sd_us -> watertown_sd_us

### World's Largest Ball of Twine
Its new place, 8.5 miles before it.
- treatment: billboard
- leg: willmar_mn_us -> minneapolis_mn_us
- at_mi: 25.0
- spoken: Billboard: A giant ball of twine is ahead. Thousands of pounds of string were wound together so future generations could ask the correct question: why?

### Lambert's Cafe
Lambert's Cafe, Ozark MO, 15 mi south of I-44; Ozark at travel 60.8 from Harrison.
- treatment: remove
- leg: dallas_tx_us -> st_louis_mo_us

### Lambert's Cafe
Its new place, 8.8 miles before it.
- treatment: billboard
- leg: harrison_ar_us -> springfield_mo_us
- at_mi: 52.0
- spoken: Billboard: Lambert's Cafe is ahead near Springfield, home of the throwed rolls. Raise a hand and a waiter will throw a hot dinner roll clear across the room at you. Catch it; those are the rules.

### Hole N' the Rock
Hole N' the Rock is 15 mi SOUTH of Moab on US-191; this leg heads north.
- treatment: remove
- leg: moab_ut_us -> grand_junction_co_us

### Hole N' the Rock
Its new place, 8.3 miles before it.
- treatment: billboard
- leg: moab_ut_us -> durango_co_us
- at_mi: 8.0
- spoken: Billboard: Hole N' the Rock is ahead. It is a five-thousand-square-foot home blasted into sandstone, with souvenirs, animals, and punctuation that has survived every editor.

### Mayberry
Mount Airy is on US 52 northwest of Winston-Salem; no leg comes within 30 miles.
- treatment: remove
- leg: roanoke_va_us -> winston_salem_nc_us

## Late, too close, too far out, or short of its own count

Same copy, new milepost (and, for a few, a new leg or facing).

### Grand Canyon Caverns
Late: sign at 95.0, attraction at 76.6. Grand Canyon Caverns is 25 mi up Route 66 from the Seligman exits (123 at 76.6, 121 at 78.9); 18 mi off I-40, no leg on Route 66. It now stands 7.6 miles before it.
- treatment: billboard
- leg: flagstaff_az_us -> kingman_az_us
- at_mi: 69.0
- spoken: Billboard: Grand Canyon Caverns is ahead near Peach Springs. The country's largest dry cavern lies two hundred feet down, with one motel room at the very bottom for the very brave.

### Two Guns
Too close: sign at 35.0, attraction at 34.3. Two Guns, I-40 exit 230 at 34.3. It now stands 6.3 miles before it.
- treatment: billboard
- leg: flagstaff_az_us -> winslow_az_us
- at_mi: 28.0
- spoken: Billboard: The ghost town of Two Guns is ahead. It has stone ruins, an old zoo, a canyon, and enough Route sixty-six legends to make every abandoned wall suspicious.

### Meteor Crater
Too close: sign at 38.0, attraction at 37.8. Meteor Crater Rd, I-40 exit 233 at 37.8 (crater 5 mi south). It now stands 6.3 miles before it.
- treatment: billboard
- leg: flagstaff_az_us -> winslow_az_us
- at_mi: 31.5
- spoken: Billboard: Meteor Crater is ahead, a hole in the desert nearly a mile wide that was punched out by a rock from space. It is bigger than it sounds. Much bigger.

### Wigwam Motel
Too close: sign at 2.0, attraction at 0.1. Wigwam Motel, W Hopi Dr on the west side of Holbrook; the sign is 1.9 mi east of it heading away.
- treatment: remove
- leg: holbrook_az_us -> gallup_nm_us

### Wigwam Motel
Its new place, 6.9 miles before it.
- treatment: billboard
- leg: winslow_az_us -> holbrook_az_us
- at_mi: 26.0
- spoken: Billboard: Sleep in a wigwam tonight in Holbrook. The motel has concrete teepees, a classic car at every door, and the old question on the sign: have you slept in a wigwam lately?

### Standin' on the Corner
Late: sign at 5.0, attraction at 0.1. Standin' on the Corner Park, downtown Winslow (leg start).
- treatment: remove
- leg: winslow_az_us -> holbrook_az_us

### Standin' on the Corner
Its new place, 8.0 miles before it.
- treatment: billboard
- leg: flagstaff_az_us -> winslow_az_us
- at_mi: 50.0
- spoken: Billboard: Winslow, Arizona, is ahead. Stand on the corner, and a girl in a flatbed Ford may slow down to look. You know the song.

### Jack Rabbit Trading Post
Too close: sign at 17.0, attraction at 16.1. Jack Rabbit Trading Post, I-40 exit 269 (Jackrabbit Rd) at 16.1. It now stands 6.1 miles before it.
- treatment: billboard
- leg: winslow_az_us -> holbrook_az_us
- at_mi: 10.0
- spoken: Billboard: The Jack Rabbit Trading Post is ahead. A giant rabbit waits out front beneath a sign that says, simply, Here It Is.

### San Gorgonio Windmills
Too far out: sign at 65.0, attraction at 97.9. San Gorgonio Pass wind farm, Whitewater exit 114 at 97.9; copy says the wind is shoving you now, but the sign is in Yucaipa. It now stands 4.9 miles before it.
- treatment: billboard
- leg: los_angeles_ca_us -> indio_ca_us
- at_mi: 93.0
- spoken: Billboard: A forest of windmills ahead in the San Gorgonio Pass, turning in the same wind that is currently shoving your trailer around. They will not kill your birds, or your fuzzy dice, but they will spin.

### Hadley's Date Shakes
Late: sign at 96.0, attraction at 88.8. Hadley Fruit Orchards, 48980 Seminole Dr, exit 104 (between 103 at 87.3 and 106 at 90.3). It now stands 2.3 miles before it.
- treatment: billboard
- leg: los_angeles_ca_us -> indio_ca_us
- at_mi: 86.5
- spoken: Billboard: Date shakes ahead at Hadley's. Yes, a milkshake made of dates. Trust the desert. It knows what it is doing.

### The Underground Gardens
Late: sign at 52.0, attraction at 47.9. Forestiere Underground Gardens, 5021 W Shaw Ave at CA-99. It now stands 5.9 miles before it.
- treatment: billboard
- leg: merced_ca_us -> fresno_ca_us
- at_mi: 42.0
- spoken: Billboard: Fresno has a villa hidden beneath the valley heat. A Sicilian immigrant spent forty years digging its courtyards, cool rooms, and citrus groves out of hardpan by hand.

### Tree of Utah
Late: sign at 705.0, attraction at 641.6. Tree of Utah, north side of I-80 at Utah MP 26 (utah.com); exit 49 at 664.6. It now stands 9.6 miles before it.
- treatment: billboard
- leg: san_francisco_ca_us -> salt_lake_city_ut_us
- at_mi: 632.0
- spoken: Billboard: The Tree of Utah stands ahead on the salt flats, an eighty-foot concrete tree sprouting from the middle of nowhere. How do you suppose this happened?

### Solvang
Too close: sign at 32.0, attraction at 32.2. Solvang is 3 mi east of 101 via the Buellton/CA-246 exit at about 32.2. It now stands 7.7 miles before it.
- treatment: billboard
- leg: santa_maria_ca_us -> santa_barbara_ca_us
- at_mi: 24.5
- spoken: Billboard: Solvang is ahead. A whole Danish village appears in the California hills, complete with windmills, half-timbered houses, warm aebleskiver, and Hans Christian Andersen watching over it all.

### African Queen
Too far out: sign at 20.0, attraction at 60.4. African Queen, Holiday Inn Key Largo MM 100 (projects 60.4; Key Largo checkpoint 61.9). It now stands 3.2 miles before it.
- treatment: billboard
- leg: miami_fl_us -> key_west_fl_us
- at_mi: 57.2
- spoken: Billboard: Key Largo is ahead, where the actual African Queen from the movie still runs canal tours. Bogart is not included.

### Theater of the Sea
Too far out: sign at 40.0, attraction at 74.9. Theater of the Sea, Islamorada MM 84.5. It now stands 8.9 miles before it.
- treatment: billboard
- leg: miami_fl_us -> key_west_fl_us
- at_mi: 66.0
- spoken: Billboard: Theater of the Sea is ahead in Islamorada. Visitors have swum with dolphins in this old coral quarry since the nineteen forties.

### Robbie's of Islamorada
Too far out: sign at 42.0, attraction at 81.2. Robbie's, Lower Matecumbe MM 77.5. It now stands 9.2 miles before it.
- treatment: billboard
- leg: miami_fl_us -> key_west_fl_us
- at_mi: 72.0
- spoken: Billboard: Robbie's is ahead. You can feed giant tarpon by hand from the dock, but mind your fingers and the pelicans, who cheat.

### Seven Mile Bridge
Late: sign at 118.0, attraction at 113.0. Seven Mile Bridge starts at Marathon MM 47 (projects 113); the sign is on the bridge. It now stands 7.0 miles before it.
- treatment: billboard
- leg: miami_fl_us -> key_west_fl_us
- at_mi: 106.0
- spoken: Billboard: Seven Mile Bridge is ahead. For seven miles, you get nothing but water on both sides, while the old bridge runs alongside and goes nowhere beautifully.

### Skunk Ape Research Headquarters
Too close: sign at 30.0, attraction at 30.4. Skunk Ape HQ is on US-41 at Ochopee; from I-75 the way there is exit 80 (SR-29) at 30.4, 0.4 mi past the sign. It now stands 6.4 miles before it.
- treatment: billboard
- leg: naples_fl_us -> miami_fl_us
- at_mi: 24.0
- spoken: Billboard: Skunk Ape Research Headquarters is ahead. Florida's swamp cousin of Bigfoot smells like rotten eggs, and he is definitely out there. Probably.

### The Giant Orange
Too close: sign at 20.0, attraction at 18.8. Eli's Orange World, 5395 W Irlo Bronson Hwy, 3 mi east of I-4 exit 64 (US-192) at 18.8 (roadsideamerica). It now stands 6.8 miles before it.
- treatment: billboard
- leg: orlando_fl_us -> tampa_fl_us
- at_mi: 12.0
- spoken: Billboard: A giant orange is ahead. Florida once advertised citrus by building fruit large enough to contain a gift shop, because normal oranges were apparently not persuasive enough.

### The Town Sherman Spared
Too close: sign at 29.0, attraction at 29.0. Madison GA (checkpoint 29.0). It now stands 5.0 miles before it.
- treatment: billboard
- leg: athens_ga_us -> macon_ga_us
- at_mi: 24.0
- spoken: Billboard: Madison is ahead, the town said to have been too pretty to burn. Sherman marched past and left the mansions standing, and they stand yet.

### Peach World
Too close: sign at 58.0, attraction at 28.0. Georgia Peach World: main store I-95 exit 58 Townsend (28.0), second store Richmond Hill exit 87 (56.5, 1.5 mi behind the sign) (WTOC, exploregeorgia). It now stands 6.0 miles before it.
- treatment: billboard
- leg: brunswick_ga_us -> savannah_ga_us
- at_mi: 22.0
- spoken: Billboard: Peach World is ahead. It sells peaches, pecans, preserves, boiled peanuts, and enough peach-flavored merchandise to prove Georgia takes branding personally.

### Berry College
Late: sign at 5.0, attraction at 2.9. Berry College main gate on US-27 north of Rome (projects 2.9). It now stands 8.1 miles before it.
- treatment: billboard
- leg: chattanooga_tn_us -> rome_ga_us
- at_mi: 57.0
- spoken: Billboard: Berry College is ahead near Rome. Its twenty-seven thousand acres of forest and fields make it the largest college campus on Earth, and its stone mill wheel is taller than a house.

### Big Things in a Small Town
Too close: sign at 37.0, attraction at 35.4. Casey, I-70 exit 129 at 35.4. It now stands 8.3 miles before it.
- treatment: billboard
- leg: terre_haute_in_us -> effingham_il_us
- at_mi: 27.1
- spoken: Billboard: Casey is ahead, a tiny town that decided to build the world's largest things. Its main street holds the largest wind chime, rocking chair, mailbox, golf tee, and wooden shoes, because one record was not enough.

### World's Largest Czech Egg
Late: sign at 225.0, attraction at 219.4. Czech egg, Wilson, I-70 exit 206 (KS-232) at 219.4. It now stands 9.4 miles before it.
- treatment: billboard
- leg: kansas_city_mo_us -> denver_co_us
- at_mi: 210.0
- spoken: Billboard: The world's largest Czech egg is ahead in Wilson, the Czech Capital of Kansas. It stands twenty feet tall and is covered in hand-painted folk art, because every small town deserves one enormous thing.

### The Garden of Eden
Late: sign at 235.0, attraction at 219.4. Garden of Eden, Lucas: 16 mi north via the same exit 206 (KS-232) at 219.4. It now stands 5.4 miles before it.
- treatment: billboard
- leg: kansas_city_mo_us -> denver_co_us
- at_mi: 214.0
- spoken: Billboard: The Garden of Eden is ahead in Lucas. Its front yard mixes concrete Bible scenes, populist politics, and roadside folk art unlike anything else.

### Cathedral of the Plains
Late: sign at 270.0, attraction at 256.3. St. It now stands 9.1 miles before it.
- treatment: billboard
- leg: kansas_city_mo_us -> denver_co_us
- at_mi: 247.2
- spoken: Billboard: The Cathedral of the Plains is ahead at Victoria. Twin limestone spires rise over wheat country as though somebody imported Europe and forgot to return it.

### The Beach and the Lighthouse
Late: sign at 2.0, attraction at 1.9. "Welcome to the Mississippi Coast" faces north, heard 2 mi after leaving the coast. It now stands 5.0 miles before it.
- treatment: billboard
- leg: hattiesburg_ms_us -> gulfport_ms_us
- at_mi: 65.0
- spoken: Billboard: Welcome to the Mississippi Coast. It has twenty-six miles of white man-made beach, the tall iron Biloxi Lighthouse standing in the highway median, casinos on the water, and shrimp fresh off the boats.

### The Shed Barbecue
Late: sign at 38.0, attraction at 27.8. The Shed, Ocean Springs, I-10 exit 57 at 27.8. It now stands 6.8 miles before it.
- treatment: billboard
- leg: gulfport_ms_us -> mobile_al_us
- at_mi: 21.0
- spoken: Billboard: The Shed Barbecue is ahead. It offers smoke, sauce, blues, and a building assembled from whatever did not run away fast enough.

### Great Platte River Road Archway
Too close: sign at 180.0, attraction at 178.9. Great Platte River Road Archway spans I-80 east of Kearney (projects 178.9). It now stands 7.9 miles before it.
- treatment: billboard
- leg: omaha_ne_us -> cheyenne_wy_us
- at_mi: 171.0
- spoken: Billboard: The Great Platte River Road Archway is ahead near Kearney. This entire museum stretches over Interstate eighty, so you drive directly beneath it and genuinely cannot miss it.

### Pony Express Station
Late: sign at 250.0, attraction at 243.4. Pony Express Station, Gothenburg, I-80 exit 211 at 243.4. It now stands 7.4 miles before it.
- treatment: billboard
- leg: omaha_ne_us -> cheyenne_wy_us
- at_mi: 236.0
- spoken: Billboard: An original Pony Express station is ahead in Gothenburg. Teenage riders once swapped horses here at a gallop while carrying the mail west.

### Golden Spike Tower
Too close: sign at 280.0, attraction at 278.1. Golden Spike Tower, North Platte, I-80 exit 177 at 278.1. It now stands 7.1 miles before it.
- treatment: billboard
- leg: omaha_ne_us -> cheyenne_wy_us
- at_mi: 271.0
- spoken: Billboard: The Golden Spike Tower is ahead in North Platte, overlooking Bailey Yard, the largest railroad yard on Earth. From above, you can watch ten thousand rail cars a day being sorted like a giant toy set.

### The Original Cabela's
Late: sign at 410.0, attraction at 394.8. original Cabela's, Sidney, I-80 exit 59 at 394.8. It now stands 7.8 miles before it.
- treatment: billboard
- leg: omaha_ne_us -> cheyenne_wy_us
- at_mi: 387.0
- spoken: Billboard: The original Cabela's is ahead in Sidney, where the outdoor empire began. Inside waits a mountain of gear and an ark's worth of taxidermy, all watching you shop.

### The Thing (countdown, sign one)
Short of its own count: sign at 60.0, attraction at 210.1. The Thing, I-10 exit 322 at 210.1 (Wikipedia); copy says two hundred miles, it is 150. It now stands 200.0 miles before it.
- treatment: billboard
- leg: las_cruces_nm_us -> tucson_az_us
- at_mi: 10.1
- spoken: Billboard: What is it? The Thing? Mystery of the desert ahead. Two hundred miles to guess, and whatever you do, do not stop moving.

### World's Tallest Thermometer
Too far out: sign at 50.0, attraction at 91.5. Baker thermometer, I-15 exit 248 (Baker) at 91.5. It now stands 11.5 miles before it.
- treatment: billboard
- leg: las_vegas_nv_us -> los_angeles_ca_us
- at_mi: 80.0
- spoken: Billboard: The world's tallest thermometer is ahead in Baker. More than a hundred feet of neon will tell you exactly how hot the Mojave is, and the answer is always too hot.

### Alien Fresh Jerky
Too far out: sign at 70.0, attraction at 91.5. Alien Fresh Jerky, Baker exit 248 at 91.5; exits 265 and 259 come first. It now stands 1.3 miles before it.
- treatment: billboard
- leg: las_vegas_nv_us -> los_angeles_ca_us
- at_mi: 90.2
- spoken: Billboard: Alien Fresh Jerky is at the next exit in Baker. They will not say who the jerky is made from, and the little green fellow on the sign is not talking.

### Zzyzx Road
Too close: sign at 100.0, attraction at 100.1. Zzyzx Road exit 239 at 100.1. It now stands 1.5 miles before it.
- treatment: billboard
- leg: las_vegas_nv_us -> los_angeles_ca_us
- at_mi: 98.6
- spoken: Billboard: The exit for Zzyzx Road is coming up, with the last word in the dictionary sitting out here in the sand. A strange story and a lake you would never expect wait behind that name.

### Peggy Sue's Fifties Diner
Late: sign at 155.0, attraction at 148.2. Peggy Sue's, Ghost Town Rd exit 191 at 148.2. It now stands 6.2 miles before it.
- treatment: billboard
- leg: las_vegas_nv_us -> los_angeles_ca_us
- at_mi: 142.0
- spoken: Billboard: Peggy Sue's Fifties Diner is ahead near Yermo. It has chrome, a jukebox, a diner cat, and a pond full of concrete dinosaurs out back. Rock and roll never checked out.

### Calico Ghost Town
Late: sign at 165.0, attraction at 148.2. Calico Ghost Town, 4 mi north of Ghost Town Rd exit 191 at 148.2. It now stands 8.5 miles before it.
- treatment: billboard
- leg: las_vegas_nv_us -> los_angeles_ca_us
- at_mi: 139.7
- spoken: Billboard: Calico Ghost Town is ahead near Barstow. It is a real silver boomtown, half restored and half falling down, and, they will tell you, thoroughly haunted.

### Cooperstown
Too close: sign at 60.0, attraction at 59.9. Cooperstown is 18 mi east of NY-12; the sign sits on the Sherburne village callout. It now stands 6.1 miles before it.
- treatment: billboard
- leg: binghamton_ny_us -> utica_ny_us
- at_mi: 53.8
- spoken: Billboard: Turn off for Cooperstown and the Baseball Hall of Fame. This lakeside village is where the game was supposedly born and where its immortals are enshrined in bronze.

### Grandpa's Cheesebarn
Late: sign at 55.0, attraction at 46.6. Grandpa's Cheesebarn, I-71 exit 186 (Ashland) at 46.6. It now stands 7.6 miles before it.
- treatment: billboard
- leg: akron_oh_us -> columbus_oh_us
- at_mi: 39.0
- spoken: Billboard: Grandpa's Cheesebarn is ahead. It offers cheese, fudge, smoked meat, and free samples arranged to defeat every promise you made at breakfast.

### First on the Moon
Too close: sign at 15.0, attraction at 14.9. Armstrong Air and Space Museum, I-75 exit 111 at 14.9. It now stands 3.6 miles before it.
- treatment: billboard
- leg: lima_oh_us -> dayton_oh_us
- at_mi: 11.3
- spoken: Billboard: Wapakoneta is ahead, birthplace of Neil Armstrong, the first human to set foot on the moon. A museum shaped like a moon base waits out here among the Ohio corn.

### Chocolate Town
Late: sign at 20.0, attraction at 16.5. Hershey, 5 mi off the route; nearest approach at 16.5. It now stands 6.3 miles before it.
- treatment: billboard
- leg: harrisburg_pa_us -> wilmington_de_us
- at_mi: 10.2
- spoken: Billboard: Hershey is ahead, the sweetest place on Earth. The chocolate bar built this town, where the streetlights are shaped like Kisses and the air itself can smell like cocoa.

### Wall Drug (countdown, sign three)
Too close: sign at 222.0, attraction at 222.1. Wall Drug, exit 110 at 222.1; exit 116 at 216.1 before it. It now stands 1.5 miles before it.
- treatment: billboard
- leg: mitchell_sd_us -> rapid_city_sd_us
- at_mi: 220.6
- spoken: Billboard: Wall Drug, next exit. You have read the signs for two hundred miles. You know you are stopping.

### Porter Sculpture Park
Late: sign at 32.0, attraction at 29.4. Porter Sculpture Park, half a mile south of I-90 exit 374 (Montrose) at 29.4 (roadsideamerica). It now stands 8.5 miles before it.
- treatment: billboard
- leg: sioux_falls_sd_us -> mitchell_sd_us
- at_mi: 20.9
- spoken: Billboard: A sixty-foot bull's head is staring at you from the prairie. That is Porter Sculpture Park. Pull over. It wants to be looked at.

### Corn Palace
Too far out: sign at 63.0, attraction at 71.1. Corn Palace, Mitchell exit 332 at 71.1; exit 335 at 68.0 comes first, so not the next exit. It now stands 1.5 miles before it.
- treatment: billboard
- leg: sioux_falls_sd_us -> mitchell_sd_us
- at_mi: 69.6
- spoken: Billboard: The Corn Palace, next exit. A building decorated entirely in corn. Redecorated every year. In corn. We cannot stress the corn enough.

### The Blues Capital of Texas
Late: sign at 147.0, attraction at 140.0. Navasota checkpoint 140.0. It now stands 7.0 miles before it.
- treatment: billboard
- leg: beaumont_tx_us -> college_station_tx_us
- at_mi: 133.0
- spoken: Billboard: Navasota is ahead, the Blues Capital of Texas. Mance Lipscomb played these porches for sixty years before anybody thought to bring a tape recorder, and the town has been making up for lost time ever since.

### Blue Whale of Catoosa
Too far out: sign at 266.9, attraction at 320.3. Blue Whale, Catoosa, NE of Tulsa (projects 320.3 on route_points; Claremore checkpoint 332.4). It now stands 8.3 miles before it.
- treatment: billboard
- leg: dallas_tx_us -> st_louis_mo_us
- at_mi: 312.0
- spoken: Billboard: The Blue Whale is ahead at Catoosa. A man built this giant smiling whale in a swimming hole for his wife, who loved whales. It may be Route sixty-six's gentlest giant.

### World's Largest Totem Pole
Too far out: sign at 303.5, attraction at 343.7. Ed Galloway's Totem Pole Park, east of Foyil (projects 343.7). It now stands 8.7 miles before it.
- treatment: billboard
- leg: dallas_tx_us -> st_louis_mo_us
- at_mi: 335.0
- spoken: Billboard: The world's largest totem pole is ahead at Foyil. One man spent eleven years hand-pouring and carving ninety feet of concrete, although nobody asked him to. You will be glad he did.

### Galena
Too far out: sign at 366.3, attraction at 408.5. Galena KS, west of Joplin (projects 408.5; Miami OK checkpoint 391.0). It now stands 8.5 miles before it.
- treatment: billboard
- leg: dallas_tx_us -> st_louis_mo_us
- at_mi: 400.0
- spoken: Billboard: Galena is ahead, an old Route sixty-six mining town where three states meet within a few miles. That rusty tow truck out front may look familiar if you have seen a certain cartoon.

### Gay Parita
Too far out: sign at 418.7, attraction at 463.7. Gay Parita, Paris Springs Junction, Route 66 west of Springfield (projects 463.7). It now stands 7.7 miles before it.
- treatment: billboard
- leg: dallas_tx_us -> st_louis_mo_us
- at_mi: 456.0
- spoken: Billboard: Gay Parita is ahead near Paris Springs. This lovingly rebuilt nineteen-thirties filling station, green dinosaur and all, survives because some folks simply refuse to let the old road die.

### Route Sixty-Six Car Museum
Too far out: sign at 450.1, attraction at 484.7. Route 66 Car Museum, W College St, Springfield (projects 484.7). It now stands 7.7 miles before it.
- treatment: billboard
- leg: dallas_tx_us -> st_louis_mo_us
- at_mi: 477.0
- spoken: Billboard: The Route Sixty-Six Car Museum is ahead near Springfield. It has chrome, fins, muscle, and enough polished paint to make your truck feel underdressed.

### Munger Moss Motel
Too far out: sign at 465.8, attraction at 536.7. Munger Moss Motel, Lebanon (Lebanon checkpoint 536.0). It now stands 7.7 miles before it.
- treatment: billboard
- leg: dallas_tx_us -> st_louis_mo_us
- at_mi: 529.0
- spoken: Billboard: The Munger Moss Motel is ahead in Lebanon, with a Route sixty-six neon sign the size of a house. It still glows every night for travelers who prefer the old way.

### Uranus Fudge Factory
Too far out: sign at 502.4, attraction at 571.0. Uranus Fudge Factory, I-44 exit 163, 7 mi east of Waynesville (checkpoint 564.2). It now stands 1.2 miles before it.
- treatment: billboard
- leg: dallas_tx_us -> st_louis_mo_us
- at_mi: 569.8
- spoken: Billboard: The best fudge in the world comes from Uranus. We did not name the town. Bring the kids, bring the jokes, and take the next exit.

### Meramec Caverns
Too far out: sign at 586.1, attraction at 633.6. Meramec Caverns, Stanton, I-44 exit 230 (Sullivan checkpoint 629.4; projects 633.6). It now stands 7.6 miles before it.
- treatment: billboard
- leg: dallas_tx_us -> st_louis_mo_us
- at_mi: 626.0
- spoken: Billboard: Meramec Caverns is ahead, with five stories of underground rooms where Jesse James is said to have hidden. It has a gift shop now, because of course it does.

### Smithfield Ham
Too close: sign at 28.0, attraction at 27.6. Smithfield (on this leg's route; projects 27.6). It now stands 9.4 miles before it.
- treatment: billboard
- leg: norfolk_va_us -> petersburg_va_us
- at_mi: 18.2
- spoken: Billboard: Smithfield is ahead, and it calls itself the Ham Capital. A salt-cured Virginia ham must age in this town by law to earn the name. The whole place smells, wonderfully, of hog.

### The New River Gorge Bridge
Late: sign at 150.0, attraction at 145.7. New River Gorge Bridge on US-19 at Fayetteville (projects 145.7). It now stands 4.7 miles before it.
- treatment: billboard
- leg: morgantown_wv_us -> beckley_wv_us
- at_mi: 141.0
- spoken: Billboard: New River Gorge is ahead. Its great steel arch was the longest in the Western Hemisphere when it opened, and once a year they let people leap off it with parachutes.

### The Thing (countdown, sign one)
Exit 322 is at 252.3; the copy says two hundred miles, so it stands at about 52, not 102.2.
- treatment: billboard
- leg: el_paso_tx_us -> tucson_az_us
- at_mi: 52.3
- spoken: Billboard: What is it? The Thing? Mystery of the desert ahead. Two hundred miles to guess, and whatever you do, do not stop moving.

## Duplicate

### Bavarian Leavenworth
A second "Leavenworth is ahead" on the same leg and direction, 26 miles before the other.
- treatment: remove
- leg: seattle_wa_us -> wenatchee_wa_us

## Descriptions of the city just left

These sat two to five miles out of the city they describe, facing away from it. Each now faces drivers arriving.

### Mobile's Mardi Gras
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: hattiesburg_ms_us -> mobile_al_us
- at_mi: 95.0
- spoken: Billboard: Mobile is the birthplace of American Mardi Gras. It started here, not in New Orleans, back in the early seventeen hundreds. Mobile brought the floats, the moon pies thrown from them, and the whole raucous carnival to America first.

### USS Alabama
A description of the city just left, heard 4.0 miles after leaving it; it now faces drivers arriving, 9.0 miles out.
- treatment: billboard
- leg: meridian_ms_us -> mobile_al_us
- at_mi: 124.0
- spoken: Billboard: Mobile Bay is home to the battleship U S S Alabama, a steel giant of the Second World War. You can walk it from bow to gun turret.

### The Bakersfield Sound
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: barstow_ca_us -> bakersfield_ca_us
- at_mi: 126.0
- spoken: Billboard: Bakersfield is home to the Bakersfield Sound. Buck Owens and Merle Haggard built a twangier, harder kind of country music here, a world away from Nashville. The Crystal Palace still swings.

### Bubblegum Alley
A description of the city just left, heard 2.0 miles after leaving it; it now faces drivers arriving, 2.2 miles out.
- treatment: billboard
- leg: santa_maria_ca_us -> san_luis_obispo_ca_us
- at_mi: 29.8
- spoken: Billboard: San Luis Obispo has an entire downtown alley walled from floor to ceiling in decades of chewed bubblegum. It is a landmark you can smell. Bring a piece, or make the healthier choice and do not.

### Edison and Ford Wintered Here
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: naples_fl_us -> fort_myers_fl_us
- at_mi: 40.0
- spoken: Billboard: Fort Myers is where Thomas Edison and Henry Ford kept winter homes side by side on the river. Edison planted a banyan tree that now shades an acre, and his laboratory remains much as he left it.

### Gator Country
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: orlando_fl_us -> gainesville_fl_us
- at_mi: 112.0
- spoken: Billboard: Gainesville is home to the Florida Gators and the Swamp. A scientist mixed the first batch of Gatorade here to keep the football team from wilting in the heat, and Tom Petty grew up here too.

### The Theme Park Capital
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: tampa_fl_us -> orlando_fl_us
- at_mi: 81.0
- spoken: Billboard: Orlando is where a mouse built a kingdom out of the swamp. Disney World, Universal, and roller coasters stretch as far as the eye can see, and more people visit here than almost anywhere on Earth.

### The Cigar City
A description of the city just left, heard 3.3 miles after leaving it; it now faces drivers arriving, 2.5 miles out.
- treatment: billboard
- leg: sarasota_fl_us -> tampa_fl_us
- at_mi: 57.5
- spoken: Billboard: Tampa is the Cigar City, where Ybor City once rolled the world's cigars by hand. A pirate ship invades the bay each winter for Gasparilla, while beer, roller coasters, and giraffes coexist at Busch Gardens.

### The Grapefruit League
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: miami_fl_us -> west_palm_beach_fl_us
- at_mi: 68.0
- spoken: Billboard: Palm Beach is where mansions face the ocean and old money spends the winter. Come February, baseball teams arrive for spring training in the Grapefruit League, while the lighthouse at Jupiter keeps guarding the coast as it has since before the Civil War.

### Athens Sound
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: augusta_ga_us -> athens_ga_us
- at_mi: 96.0
- spoken: Billboard: Athens is the birthplace of R E M and the B-Fifty-Twos. This college town produced more good bands than it had any right to.

### The Tree That Owns Itself
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: macon_ga_us -> athens_ga_us
- at_mi: 91.0
- spoken: Billboard: Athens is home to the Tree That Owns Itself, a white oak said to hold the deed to the ground where it grows. That tree owns more property than most people.

### A Tradition Unlike Any Other
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: columbia_sc_us -> augusta_ga_us
- at_mi: 68.0
- spoken: Billboard: Augusta is home to the Masters. Every April, the golf world comes to Augusta National for the green jacket, the azaleas, Amen Corner, and a pimento cheese sandwich that somehow still costs almost nothing.

### Watermelon Capital, Georgia's Claim
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: albany_ga_us -> cordele_ga_us
- at_mi: 36.0
- spoken: Billboard: Cordele calls itself the Watermelon Capital of the world. Arkansas may argue, but the melons here do not care who wins.

### Macon Music
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 2.8 miles out.
- treatment: billboard
- leg: columbus_ga_us -> macon_ga_us
- at_mi: 96.2
- spoken: Billboard: Macon is home to Little Richard, Otis Redding, and the Allman Brothers. This red-clay town wrote a shocking share of American music.

### Cherry Blossom Capital
A description of the city just left, heard 5.0 miles after leaving it; it now faces drivers arriving, 5.0 miles out.
- treatment: billboard
- leg: columbus_ga_us -> macon_ga_us
- at_mi: 94.0
- spoken: Billboard: Macon is the Cherry Blossom Capital of the world. About three hundred fifty thousand Yoshino cherry trees bloom pink every March, which is more than Washington and Tokyo have to spare.

### The Capitoline Wolf
A description of the city just left, heard 2.0 miles after leaving it; it now faces drivers arriving, 5.5 miles out.
- treatment: billboard
- leg: cartersville_ga_us -> rome_ga_us
- at_mi: 21.5
- spoken: Billboard: Rome, Georgia, was built on seven hills and has a bronze she-wolf suckling Romulus and Remus. It was a gift from Rome, Italy. Yes, that Rome.

### The Floating Green
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: sandpoint_id_us -> coeur_d_alene_id_us
- at_mi: 43.0
- spoken: Billboard: Coeur d'Alene has a golf green that floats on the lake, and a boat ferries you out to your ball. Miss the island and you feed the fish.

### Evel Knievel's Canyon
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 2.8 miles out.
- treatment: billboard
- leg: wells_nv_us -> twin_falls_id_us
- at_mi: 113.2
- spoken: Billboard: Twin Falls is where Evel Knievel tried to rocket across the Snake River Canyon on a steam-powered cycle. He came up short but alive, while today's base jumpers leap from the bridge for fun.

### Boot Hill
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: hays_ks_us -> dodge_city_ks_us
- at_mi: 113.0
- spoken: Billboard: Dodge City was once the wickedest little city in the West. Wyatt Earp and Bat Masterson kept the peace badly, while the losers went up to Boot Hill with their boots on. Get out of Dodge, or stay a while.

### The Tallest Capitol
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 2.7 miles out.
- treatment: billboard
- leg: gulfport_ms_us -> baton_rouge_la_us
- at_mi: 133.3
- spoken: Billboard: Baton Rouge has the tallest state capitol in the nation, a thirty-four-story tower built by Huey Long. The Kingfish himself was shot dead in the marble halls he raised.

### The Motor City and Motown
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: toledo_oh_us -> detroit_mi_us
- at_mi: 56.0
- spoken: Billboard: Detroit is the Motor City that put the world on wheels and gave it Motown. From a little house called Hitsville came the Supremes, the Temptations, Stevie Wonder, and the sound of young America.

### Tennessee Williams' Columbus
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: tupelo_ms_us -> columbus_ms_us
- at_mi: 63.0
- spoken: Billboard: Columbus is the birthplace of Tennessee Williams. The rectory where the playwright of A Streetcar Named Desire was born still stands. Stella is not included.

### Jimmie Rodgers, the Singing Brakeman
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: tupelo_ms_us -> meridian_ms_us
- at_mi: 139.0
- spoken: Billboard: Meridian is home to Jimmie Rodgers, the father of country music. He was a railroad man who yodeled the blues and helped start it all.

### NASCAR's Capital
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: winston_salem_nc_us -> charlotte_nc_us
- at_mi: 75.0
- spoken: Billboard: Charlotte is the capital of NASCAR. Nearly every race team is based within an hour, and the Hall of Fame downtown lets you sit in the cars and feel the noise.

### The Battleship
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: lumberton_nc_us -> wilmington_nc_us
- at_mi: 76.0
- spoken: Billboard: Wilmington is where the battleship North Carolina rides at anchor on the Cape Fear. So many movies are filmed here that the city also calls itself Hollywood East.

### The Great Platte River Road Archway
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: hays_ks_us -> kearney_ne_us
- at_mi: 144.0
- spoken: Billboard: Kearney has a museum built as a giant arch over the entire interstate. It tells the story of wagon trains, the Pony Express, and the railroad, all of which followed this river valley west.

### The Very Large Array
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: las_cruces_nm_us -> socorro_nm_us
- at_mi: 143.0
- spoken: Billboard: West of Socorro, twenty-seven giant white dish antennas listen to the universe together across the Plains of San Agustin. You have seen them in the movies, aimed at the stars.

### Rubber City
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: cleveland_oh_us -> akron_oh_us
- at_mi: 36.0
- spoken: Billboard: Akron is the Rubber City, where the world's tires were born and the Goodyear blimp still lives. It is also home to the Soap Box Derby and a kid named LeBron.

### The Rock and Roll Hall of Fame
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: toledo_oh_us -> cleveland_oh_us
- at_mi: 111.0
- spoken: Billboard: Cleveland rocks. The Rock and Roll Hall of Fame stands in a glass pyramid on the lake, in the city where a disc jockey first shouted the words rock and roll.

### The Horseshoe
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: cincinnati_oh_us -> columbus_oh_us
- at_mi: 103.0
- spoken: Billboard: Columbus is home to Ohio State and the Horseshoe. More than a hundred thousand people spell out O H I O while the band marches Script Ohio and a sousaphone player dots the i.

### Toledo, Glass and Klinger
A description of the city just left, heard 3.1 miles after leaving it; it now faces drivers arriving, 3.1 miles out.
- treatment: billboard
- leg: findlay_oh_us -> toledo_oh_us
- at_mi: 42.9
- spoken: Billboard: Toledo is the Glass City, where they build Jeeps and blow glass. Do not leave without a Hungarian hot dog from Tony Packo's, the place Corporal Klinger would not shut up about.

### The Goonies
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: olympia_wa_us -> astoria_or_us
- at_mi: 119.0
- spoken: Billboard: Astoria is where they filmed The Goonies and Kindergarten Cop. The oldest American town west of the Rockies climbs a hill toward a tall column you can climb from the inside.

### Free Willy Lived Here
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: albany_or_us -> newport_or_us
- at_mi: 57.0
- spoken: Billboard: Newport is home to the Oregon Coast Aquarium, where Keiko, the orca from Free Willy, once lived before they set him free for real.

### Home of the Aggies
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: temple_tx_us -> college_station_tx_us
- at_mi: 88.0
- spoken: Billboard: College Station is home to Texas A and M and the Twelfth Man. The Aggies stand for the entire game, bury their mascots near the stadium, and once built bonfires that touched the sky.

### Magnolia
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 2.8 miles out.
- treatment: billboard
- leg: tyler_tx_us -> waco_tx_us
- at_mi: 127.2
- spoken: Billboard: Waco is home to Magnolia Market at the Silos. Chip and Joanna turned an old cotton mill into shiplap heaven, and the buses of shoppers have not stopped since.

### The Home of Dr Pepper
A description of the city just left, heard 5.0 miles after leaving it; it now faces drivers arriving, 5.0 miles out.
- treatment: billboard
- leg: tyler_tx_us -> waco_tx_us
- at_mi: 125.0
- spoken: Billboard: Waco is the birthplace of Dr Pepper, the oldest major soft drink in America. It was mixed at a drugstore soda fountain here before Coke was even a gleam, and the museum occupies the old bottling plant.

### Utah's Shakespeare
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: richfield_ut_us -> cedar_city_ut_us
- at_mi: 111.0
- spoken: Billboard: Cedar City hosts a Tony-winning Shakespeare festival in the red-rock desert. It is also the gateway to Zion, Bryce, and the pink cliffs of Cedar Breaks.

### The World's Largest Pencil
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: roanoke_va_us -> wytheville_va_us
- at_mi: 75.0
- spoken: Billboard: Wytheville is home to a pencil the size of a telephone pole, leaning against an office building. Outside town, an old lead-shot tower marks where molten metal was dropped until gravity made it round.

### Titletown
A description of the city just left, heard 3.0 miles after leaving it; it now faces drivers arriving, 3.0 miles out.
- treatment: billboard
- leg: grand_rapids_mi_us -> green_bay_wi_us
- at_mi: 379.0
- spoken: Billboard: Green Bay is Titletown, home of the Packers and the only team owned by its fans. Lambeau Field is the frozen tundra, filled with grown adults wearing foam cheese on their heads.

## Signs the landmark spacing never lets speak

Each sat within two miles of a village or an earlier landmark, so Trip::place_landmarks dropped it. Each is nudged clear.

### Noccalula Falls
Never heard: within two miles of Attalla at 57.7, so the landmark spacing drops it. Moved to 54.5.
- treatment: billboard
- leg: birmingham_al_us -> gadsden_al_us
- at_mi: 54.5
- spoken: Billboard: Gadsden is home to Noccalula Falls, a ninety-foot waterfall in a city park. A bronze Cherokee maiden stands at the brink, recalling an old and sorrowful legend.

### Troy
Never heard: within two miles of Conecuh River at 45.5, so the landmark spacing drops it. Moved to 43.0.
- treatment: billboard
- leg: montgomery_al_us -> troy_al_us
- at_mi: 43.0
- spoken: Billboard: Troy University is ahead, home of the Trojans and a surprisingly world-class art collection out among the pines.

### The Boll Weevil Monument
Never heard: within two miles of Ozark at 33.7, so the landmark spacing drops it. Moved to 28.5.
- treatment: billboard
- leg: troy_al_us -> dothan_al_us
- at_mi: 28.5
- spoken: Billboard: Enterprise, west of here, built a monument to the boll weevil, the bug that ate its cotton. The disaster forced farmers to plant peanuts, peanuts made them rich, and gratitude to a pest became a statue.

### Peanut Capital of the World
Never heard: within two miles of Little Choctawatchee River at 49.0, so the landmark spacing drops it. Moved to 44.5.
- treatment: billboard
- leg: troy_al_us -> dothan_al_us
- at_mi: 44.5
- spoken: Billboard: Dothan is the Peanut Capital of the World. A quarter of the nation's peanuts pass through here, and downtown is decorated with giant painted peanuts wearing hats.

### The Madonna Inn
Never heard: within two miles of Cuesta Pass at 122.3, so the landmark spacing drops it. Moved to 124.5.
- treatment: billboard
- leg: salinas_ca_us -> san_luis_obispo_ca_us
- at_mi: 124.5
- spoken: Billboard: San Luis Obispo is home to the Madonna Inn, a pink palace where every room is a different fever dream. Even the men's room waterfall is a tourist attraction in its own right.

### The Oldest City
Never heard: within two miles of Vermont Heights at 40.8, so the landmark spacing drops it. Moved to 30.0.
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 30.0
- spoken: Billboard: Saint Augustine is the oldest city in America. The Spanish founded it in fifteen sixty-five, more than forty years before Jamestown. It has a stone fort that never fell, a college inside a palace, and a spring Ponce de Leon called the Fountain of Youth.

### Robert Is Here
Never heard: within two miles of Coral Gables at 4.9, so the landmark spacing drops it. Moved to 19.5.
- treatment: billboard
- leg: miami_fl_us -> key_west_fl_us
- at_mi: 19.5
- spoken: Billboard: Robert Is Here is the famous fruit stand at the edge of the Everglades. It sells key limes and milkshakes beneath a boy's name that outgrew him.

### Bahia Honda
Never heard: within two miles of Crane Point Museum at 108.9, so the landmark spacing drops it. Moved to 111.5.
- treatment: billboard
- leg: miami_fl_us -> key_west_fl_us
- at_mi: 111.5
- spoken: Billboard: Bahia Honda is ahead, with one of the best beaches in the Keys beneath the broken back of Flagler's old railroad bridge.

### Southernmost Point
Never heard: within two miles of Reaching Key West, the southernmost point in the continental United States at 155.0, so the landmark spacing drops it. Moved to 152.5.
- treatment: billboard
- leg: miami_fl_us -> key_west_fl_us
- at_mi: 152.5
- spoken: Billboard: Key West has the Southernmost Point in the continental United States, ninety miles from Cuba and one long line of people waiting to be photographed with it.

### Everglades City Stone Crab
Never heard: within two miles of Skunk Ape Research Headquarters at 30.0, so the landmark spacing drops it. Moved to 27.0.
- treatment: billboard
- leg: naples_fl_us -> miami_fl_us
- at_mi: 27.0
- spoken: Billboard: Everglades City is the stone crab capital. The claws are harvested, the crabs go back to sea, and the mustard sauce has no intention of being optional.

### Uncle Remus Country
Never heard: within two miles of Bledsoe-Green House Museum at 51.8, so the landmark spacing drops it. Moved to 49.5.
- treatment: billboard
- leg: athens_ga_us -> macon_ga_us
- at_mi: 49.5
- spoken: Billboard: Eatonton is home to Br'er Rabbit. The old Uncle Remus tales were set down here, and a statue of the rabbit himself stands watch at the courthouse.

### The Corvette Sinkhole
Never heard: within two miles of Plum Springs at 138.4, so the landmark spacing drops it. Moved to 136.0.
- treatment: billboard
- leg: london_ky_us -> bowling_green_ky_us
- at_mi: 136.0
- spoken: Billboard: Bowling Green is home to the Corvette. A sinkhole once opened under the museum floor and swallowed eight of them whole, so naturally they saved the hole.

### Hell, Michigan
Never heard: within two miles of Genoa Charter Township at 23.7, so the landmark spacing drops it. Moved to 26.3.
- treatment: billboard
- leg: ann_arbor_mi_us -> grand_rapids_mi_us
- at_mi: 26.3
- spoken: Billboard: Turn off for Hell, Michigan. You can get married, mail a postcard, buy a souvenir, and announce that Hell froze over when you visit in winter.

### The Big House
Never heard: within two miles of Huron River at 39.1, so the landmark spacing drops it. Moved to 41.5.
- treatment: billboard
- leg: detroit_mi_us -> ann_arbor_mi_us
- at_mi: 41.5
- spoken: Billboard: Ann Arbor is home to Michigan and the Big House, the largest stadium in the country. More than a hundred thousand fans wear maize and blue and sing The Victors.

### Bronner's CHRISTmas Wonderland
Never heard: within two miles of Birch Run at 21.4, so the landmark spacing drops it. Moved to 18.5.
- treatment: billboard
- leg: flint_mi_us -> saginaw_mi_us
- at_mi: 18.5
- spoken: Billboard: Frankenmuth is ahead, Michigan's Little Bavaria and home to Bronner's, the world's largest Christmas store. It stays open all year, covers several football fields, and glows like the North Pole in July.

### Oz Museum
Never heard: within two miles of Paxico at 91.7, so the landmark spacing drops it. Moved to 88.5.
- treatment: billboard
- leg: kansas_city_mo_us -> denver_co_us
- at_mi: 88.5
- spoken: Billboard: The Oz Museum is ahead in Wamego. Follow the yellow brick road off Interstate seventy, because there is no place like home and apparently no place like Kansas either.

### Branson
Never heard: within two miles of Bull Creek at 39.0, so the landmark spacing drops it. Moved to 36.5.
- treatment: billboard
- leg: springfield_mo_us -> harrison_ar_us
- at_mi: 36.5
- spoken: Billboard: Branson is ahead, a little Ozark town with more theater seats than Broadway. Country music shows line the strip, and a theme park waits up on the mountain. Bring the grandparents.

### Elvis, again
Never heard: within two miles of Verona at 60.9, so the landmark spacing drops it. Moved to 58.5.
- treatment: billboard
- leg: columbus_ms_us -> tupelo_ms_us
- at_mi: 58.5
- spoken: Billboard: Tupelo is the home of Elvis. He got his first guitar here instead of the bicycle his family could not afford. The rest you know.

### The Birthplace of the Blues Marker
Never heard: within two miles of Crawford at 73.4, so the landmark spacing drops it. Moved to 71.0.
- treatment: billboard
- leg: meridian_ms_us -> tupelo_ms_us
- at_mi: 71.0
- spoken: Billboard: You are in Mississippi music country, where blues, gospel, country, and rock and roll traded notes along roads like this before anyone argued over who invented what.

### Elvis Presley Birthplace
Never heard: within two miles of Verona at 136.9, so the landmark spacing drops it. Moved to 134.5.
- treatment: billboard
- leg: meridian_ms_us -> tupelo_ms_us
- at_mi: 134.5
- spoken: Billboard: Tupelo is ahead, home to the two-room shotgun shack where Elvis Presley was born. The King started here, poor as dirt, with a guitar from the hardware store.

## Covered by the pool-move signs

### World's Largest Rocking Chair
Casey is east of Effingham; the new eastbound rocking-chair sign on Terre Haute to Effingham already covers it.
- treatment: remove
- leg: effingham_il_us -> st_louis_mo_us

### Little America
Little America is 36 miles past this leg's end; the new Rock Springs to Salt Lake City sign already covers it.
- treatment: remove
- leg: rawlins_wy_us -> rock_springs_wy_us

## Closed attractions

### Split Pea Soup
Pea Soup Andersen's in Buellton closed on 1 January 2024 and is cleared for demolition.
- treatment: remove
- leg: santa_maria_ca_us -> santa_barbara_ca_us

### Goats on the Roof
Goats on the Roof in Tiger, Georgia, closed in April 2024; it is also 60 miles off this road.
- treatment: remove
- leg: athens_ga_us -> chattanooga_tn_us

### World's Largest Prairie Dog
Prairie Dog Town at Oakley closed for good in 2014.
- treatment: remove
- leg: kansas_city_mo_us -> denver_co_us
