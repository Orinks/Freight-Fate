
# North and Central Florida attractions, both directions -- 2026-09-30

Draft for the owner. Real roadside attractions from Pensacola to Tallahassee,
Jacksonville, Saint Augustine, Gainesville, Ocala, Daytona, Orlando and the
Space Coast as far south as Melbourne, each signed in every direction of
travel where a leg passes it. Every `leg:` is written the way the driver reads
the sign and `at_mi` counts from that end; `tools/bake_billboards.py` mirrors
the milepost onto a leg stored the other way round and records which way the
billboard faces.

Florida allows commercial billboards along its Interstates and federal-aid
primary highways in commercial and industrial areas under an FDOT permit
(Florida Statutes chapter 479, sections 479.07 and 479.111), at least 1,500
feet apart on an Interstate. New billboards are barred on the scenic portions
of state-designated scenic highways (the federal rule, 23 U.S.C. 131(s)). No
sign here stands on one of Florida's scenic highways; see the notes.

Mileposts come from the legs' interchange lists where the road has one. On
the US-route legs that share Interstate 10 or Interstate 75 and list no
exits, the exit positions were carried over from the Interstate leg's own
interchange list along the dense road geometry. "Next exit" signs stand
between the attraction's exit and the exit before it; "ahead" signs about
three to fifteen miles out, or where the callouts leave room. Each sits at
least 2.2 miles from every other callout heard in the same direction.

Four existing town lines are reused verbatim on legs and directions that had none:
the Oldest City (Saint Augustine), the World Center of Racing (Daytona
Beach), Glass-Bottom Boats (Ocala and Silver Springs) and Gator Country
(Gainesville). Their headings carry a direction so the bake does not replace
the original record of the same name.

# The Panhandle

## Florida Caverns State Park, Marianna (I-10 Exit 142)

The only cave tours in Florida, through limestone caverns the Civilian
Conservation Corps opened up in the 1930s; a constant 65 degrees; 3345
Caverns Road, three miles north of Marianna. Tours daily. The park's own
directions use I-10 Exit 142 (floridastateparks.org; florida-backroads-travel.com).
The Dothan and Panama City legs to Tallahassee run I-10 east of Cottondale,
so they pass Exit 142 too.

### Florida Caverns (westbound)
- treatment: billboard
- leg: tallahassee_fl_us -> crestview_fl_us
- at_mi: 60.0
- spoken: Billboard: Florida Caverns State Park, next exit, north of Marianna. The only cave tours in Florida, sixty-five degrees all year. The state's oldest air conditioning.

### Florida Caverns (eastbound)
- treatment: billboard
- leg: crestview_fl_us -> tallahassee_fl_us
- at_mi: 86.3
- spoken: Billboard: Florida Caverns State Park, next exit, north of Marianna. The only cave tours in Florida, sixty-five degrees all year. The state's oldest air conditioning.

### Florida Caverns (eastbound)
- treatment: billboard
- leg: dothan_al_us -> tallahassee_fl_us
- at_mi: 45.1
- spoken: Billboard: Florida Caverns State Park, next exit, north of Marianna. The only cave tours in Florida, sixty-five degrees all year. The state's oldest air conditioning.

### Florida Caverns (westbound)
- treatment: billboard
- leg: tallahassee_fl_us -> dothan_al_us
- at_mi: 60.3
- spoken: Billboard: Florida Caverns State Park, next exit, north of Marianna. The only cave tours in Florida, sixty-five degrees all year. The state's oldest air conditioning.

### Florida Caverns (eastbound)
- treatment: billboard
- leg: panama_city_fl_us -> tallahassee_fl_us
- at_mi: 58.5
- spoken: Billboard: Florida Caverns State Park, next exit, north of Marianna. The only cave tours in Florida, sixty-five degrees all year. The state's oldest air conditioning.

### Florida Caverns (westbound)
- treatment: billboard
- leg: tallahassee_fl_us -> panama_city_fl_us
- at_mi: 57.5
- spoken: Billboard: Florida Caverns State Park, next exit, north of Marianna. The only cave tours in Florida, sixty-five degrees all year. The state's oldest air conditioning.

## Falling Waters State Park, Chipley (I-10 Exit 120)

Florida's highest waterfall, 73 feet into a cylindrical sinkhole 100 feet
deep; 1130 State Park Road, three miles south of I-10 Exit 120 on SR 77;
open daily 8 to sundown (Wikipedia, "Falling Waters State Park";
floridastateparks.org). The Crestview to Dothan leg runs I-10 east to
Exit 130, so it passes Exit 120 both ways.

### Falling Waters (westbound)
- treatment: billboard
- leg: tallahassee_fl_us -> crestview_fl_us
- at_mi: 82.5
- spoken: Billboard: Falling Waters State Park, next exit, south of Chipley. Florida's tallest waterfall drops seventy-three feet straight into a sinkhole. Even the waterfalls here go underground.

### Falling Waters (eastbound)
- treatment: billboard
- leg: crestview_fl_us -> tallahassee_fl_us
- at_mi: 64.0
- spoken: Billboard: Falling Waters State Park, next exit, south of Chipley. Florida's tallest waterfall drops seventy-three feet straight into a sinkhole. Even the waterfalls here go underground.

### Falling Waters (eastbound)
- treatment: billboard
- leg: crestview_fl_us -> dothan_al_us
- at_mi: 64.2
- spoken: Billboard: Falling Waters State Park, next exit, south of Chipley. Florida's tallest waterfall drops seventy-three feet straight into a sinkhole. Even the waterfalls here go underground.

### Falling Waters (westbound)
- treatment: billboard
- leg: dothan_al_us -> crestview_fl_us
- at_mi: 43.2
- spoken: Billboard: Falling Waters State Park, next exit, south of Chipley. Florida's tallest waterfall drops seventy-three feet straight into a sinkhole. Even the waterfalls here go underground.

## Ponce de Leon Springs State Park (I-10 Exit 96)

A spring pool that holds 68 degrees year round and puts out 14 million
gallons a day, half a mile south of US 90 on CR 181A, just off I-10 Exit 96
(floridastateparks.org; florida-backroads-travel.com). The joke is about the
water temperature, not the explorer, so it never contradicts the Oldest City
line's Fountain of Youth.

### Ponce de Leon Springs (westbound)
- treatment: billboard
- leg: tallahassee_fl_us -> crestview_fl_us
- at_mi: 106.0
- spoken: Billboard: Ponce de Leon Springs State Park, next exit. Sixty-eight degrees all year round. Swimmers call it refreshing. Swimmers are lying.

### Ponce de Leon Springs (eastbound)
- treatment: billboard
- leg: crestview_fl_us -> tallahassee_fl_us
- at_mi: 40.4
- spoken: Billboard: Ponce de Leon Springs State Park, next exit. Sixty-eight degrees all year round. Swimmers call it refreshing. Swimmers are lying.

### Ponce de Leon Springs (eastbound)
- treatment: billboard
- leg: crestview_fl_us -> dothan_al_us
- at_mi: 39.5
- spoken: Billboard: Ponce de Leon Springs State Park, next exit. Sixty-eight degrees all year round. Swimmers call it refreshing. Swimmers are lying.

### Ponce de Leon Springs (westbound)
- treatment: billboard
- leg: dothan_al_us -> crestview_fl_us
- at_mi: 66.6
- spoken: Billboard: Ponce de Leon Springs State Park, next exit. Sixty-eight degrees all year round. Swimmers call it refreshing. Swimmers are lying.

## Lake DeFuniak, DeFuniak Springs (I-10 Exit 85)

A spring-fed lake almost perfectly round, about a mile around, at the center
of the historic district, two miles north of I-10 Exit 85 on US 331
(Wikipedia, "Lake DeFuniak"). The Panama City to Crestview leg comes up US
331 from the coast and turns west onto I-10 at Exit 85, so that sign reads
"ahead"; the town is just north of the junction.

### Lake DeFuniak (westbound)
- treatment: billboard
- leg: tallahassee_fl_us -> crestview_fl_us
- at_mi: 117.4
- spoken: Billboard: Lake DeFuniak, next exit in DeFuniak Springs. A spring-fed lake almost perfectly round, a mile around. The one roundabout in Florida nobody complains about.

### Lake DeFuniak (eastbound)
- treatment: billboard
- leg: crestview_fl_us -> tallahassee_fl_us
- at_mi: 29.0
- spoken: Billboard: Lake DeFuniak, next exit in DeFuniak Springs. A spring-fed lake almost perfectly round, a mile around. The one roundabout in Florida nobody complains about.

### Lake DeFuniak (eastbound)
- treatment: billboard
- leg: crestview_fl_us -> dothan_al_us
- at_mi: 29.2
- spoken: Billboard: Lake DeFuniak, next exit in DeFuniak Springs. A spring-fed lake almost perfectly round, a mile around. The one roundabout in Florida nobody complains about.

### Lake DeFuniak (westbound)
- treatment: billboard
- leg: dothan_al_us -> crestview_fl_us
- at_mi: 78.2
- spoken: Billboard: Lake DeFuniak, next exit in DeFuniak Springs. A spring-fed lake almost perfectly round, a mile around. The one roundabout in Florida nobody complains about.

### Lake DeFuniak (eastbound)
- treatment: billboard
- leg: crestview_fl_us -> panama_city_fl_us
- at_mi: 29.0
- spoken: Billboard: Lake DeFuniak, next exit in DeFuniak Springs. A spring-fed lake almost perfectly round, a mile around. The one roundabout in Florida nobody complains about.

### Lake DeFuniak (northbound)
- treatment: billboard
- leg: panama_city_fl_us -> crestview_fl_us
- at_mi: 52.0
- spoken: Billboard: Lake DeFuniak, ahead in DeFuniak Springs. A spring-fed lake almost perfectly round, a mile around. The one roundabout in Florida nobody complains about.

## Seaside (US 98, Walton County)

The planned beach town where The Truman Show was filmed, on County Road 30A
about two and a half miles south of US 98, which the Panama City to Crestview
leg follows west to US 331 (Wikipedia, "Seaside, Florida"; "The Truman
Show"). The sign stands on US 98, not on Scenic Highway 30A.

### Seaside (westbound)
- treatment: billboard
- leg: panama_city_fl_us -> crestview_fl_us
- at_mi: 30.0
- spoken: Billboard: Seaside, ahead, just south of this road. The town where they filmed The Truman Show. Wave at the sky on your way past, just in case.

### Seaside (eastbound)
- treatment: billboard
- leg: crestview_fl_us -> panama_city_fl_us
- at_mi: 53.0
- spoken: Billboard: Seaside, ahead, just south of this road. The town where they filmed The Truman Show. Wave at the sky on your way past, just in case.

## Milton, the Canoe Capital of Florida (I-10 Exits 26 to 31)

Named the Canoe Capital of Florida by act of the state legislature; the
Blackwater River, a tea-colored sand-bottom river, runs through town
(visitflorida.com; Wikipedia, "Blackwater River (Florida)"). A town sign,
standing before Milton in each direction.

### Milton (westbound)
- treatment: billboard
- leg: crestview_fl_us -> pensacola_fl_us
- at_mi: 24.0
- spoken: Billboard: Milton, ahead, the official Canoe Capital of Florida. The Blackwater River runs dark as tea over white sand. Your truck does not count as a canoe.

### Milton (eastbound)
- treatment: billboard
- leg: pensacola_fl_us -> crestview_fl_us
- at_mi: 12.0
- spoken: Billboard: Milton, ahead, the official Canoe Capital of Florida. The Blackwater River runs dark as tea over white sand. Your truck does not count as a canoe.

## National Naval Aviation Museum, Pensacola (Naval Air Station Pensacola)

Free, open daily 9 to 4, with some 150 historic aircraft, at 1750 Radford
Boulevard on the air station (navalaviationmuseum.org; Naval History and
Heritage Command). Daily public access resumed on May 1, 2026, through the
West Gate on Blue Angel Parkway with a REAL ID or passport (Fox 10, May 2,
2026). From I-10 the way in is Exit 7, Pine Forest Road, then south on Blue
Angel Parkway, about fifteen miles, so both signs read "ahead".

### Naval Aviation Museum (westbound)
- treatment: billboard
- leg: crestview_fl_us -> pensacola_fl_us
- at_mi: 40.0
- spoken: Billboard: The National Naval Aviation Museum, ahead on the Navy base in Pensacola. About a hundred and fifty airplanes, free to see, all parked better than you.

### Naval Aviation Museum (eastbound)
- treatment: billboard
- leg: mobile_al_us -> pensacola_fl_us
- at_mi: 45.8
- spoken: Billboard: The National Naval Aviation Museum, ahead on the Navy base in Pensacola. About a hundred and fifty airplanes, free to see, all parked better than you.

## Florida's Historic Capitol, Tallahassee (I-10 Exit 199)

The 1845 capitol, restored to its 1902 look with red and white striped
awnings, free and open 363 days a year. The plan for the 22-story new
Capitol, finished in 1977, called for tearing it down; public outcry saved
it (flhistoriccapitol.gov; Bay News 9, March 7, 2024; Tallahassee Magazine).
Signed on every approach to Tallahassee except Dothan's, which already
carries the Canopy Roads town sign four miles out.

### Historic Capitol (eastbound)
- treatment: billboard
- leg: crestview_fl_us -> tallahassee_fl_us
- at_mi: 140.5
- spoken: Billboard: Florida's Historic Capitol, ahead in Tallahassee. The plan was to tear it down for the twenty-two story tower. People said no, and the striped awnings stayed.

### Historic Capitol (eastbound)
- treatment: billboard
- leg: panama_city_fl_us -> tallahassee_fl_us
- at_mi: 113.4
- spoken: Billboard: Florida's Historic Capitol, ahead in Tallahassee. The plan was to tear it down for the twenty-two story tower. People said no, and the striped awnings stayed.

### Historic Capitol (westbound)
- treatment: billboard
- leg: lake_city_fl_us -> tallahassee_fl_us
- at_mi: 101.6
- spoken: Billboard: Florida's Historic Capitol, ahead in Tallahassee. The plan was to tear it down for the twenty-two story tower. People said no, and the striped awnings stayed.

### Historic Capitol (westbound)
- treatment: billboard
- leg: jacksonville_fl_us -> tallahassee_fl_us
- at_mi: 160.8
- spoken: Billboard: Florida's Historic Capitol, ahead in Tallahassee. The plan was to tear it down for the twenty-two story tower. People said no, and the striped awnings stayed.

### Historic Capitol (southbound)
- treatment: billboard
- leg: albany_ga_us -> tallahassee_fl_us
- at_mi: 78.0
- spoken: Billboard: Florida's Historic Capitol, ahead in Tallahassee. The plan was to tear it down for the twenty-two story tower. People said no, and the striped awnings stayed.

### Historic Capitol (westbound)
- treatment: billboard
- leg: valdosta_ga_us -> tallahassee_fl_us
- at_mi: 75.0
- spoken: Billboard: Florida's Historic Capitol, ahead in Tallahassee. The plan was to tear it down for the twenty-two story tower. People said no, and the striped awnings stayed.

# The Big Bend and North Florida

## Greenville, Ray Charles's hometown (I-10 Exit 241)

Ray Charles grew up in Greenville; a life-size bronze of him at the piano,
by local sculptors Bradley Cooley and Brad Cooley Jr., stands in Ray Charles
Plaza in Haffye Hays Park, and his restored childhood home on Ray Charles
Avenue opened in 2009 (florida-backroads-travel.com; WCTV, September 24,
2025; Greene Publishing). A town sign: I-10 signs read "next exit"; the
Valdosta leg comes down US 221 through the middle of town, so its southbound
sign reads "ahead".

### Greenville (eastbound)
- treatment: billboard
- leg: tallahassee_fl_us -> jacksonville_fl_us
- at_mi: 45.0
- spoken: Billboard: Greenville, next exit, where Ray Charles grew up. A life-size bronze Ray plays piano in the town park. He has not missed a show since.

### Greenville (eastbound)
- treatment: billboard
- leg: tallahassee_fl_us -> lake_city_fl_us
- at_mi: 44.9
- spoken: Billboard: Greenville, next exit, where Ray Charles grew up. A life-size bronze Ray plays piano in the town park. He has not missed a show since.

### Greenville (westbound)
- treatment: billboard
- leg: jacksonville_fl_us -> tallahassee_fl_us
- at_mi: 121.5
- spoken: Billboard: Greenville, next exit, where Ray Charles grew up. A life-size bronze Ray plays piano in the town park. He has not missed a show since.

### Greenville (westbound)
- treatment: billboard
- leg: lake_city_fl_us -> tallahassee_fl_us
- at_mi: 62.6
- spoken: Billboard: Greenville, next exit, where Ray Charles grew up. A life-size bronze Ray plays piano in the town park. He has not missed a show since.

### Greenville (eastbound)
- treatment: billboard
- leg: tallahassee_fl_us -> valdosta_ga_us
- at_mi: 41.4
- spoken: Billboard: Greenville, next exit, where Ray Charles grew up. A life-size bronze Ray plays piano in the town park. He has not missed a show since.

### Greenville (southbound)
- treatment: billboard
- leg: valdosta_ga_us -> tallahassee_fl_us
- at_mi: 36.5
- spoken: Billboard: Greenville, ahead, where Ray Charles grew up. A life-size bronze Ray plays piano in the town park. He has not missed a show since.

## Stephen Foster Folk Culture Center State Park, White Springs (I-75 Exit 439)

A museum and a 97-bell carillon on the Suwannee River honoring the composer
of "Old Folks at Home," Florida's state song, who never visited Florida;
three miles east of I-75 Exit 439, which the leg's own exit list names
"Stephen Foster State Park" (Wikipedia; floridastateparks.org). The copy
names no lyric.

### Stephen Foster State Park (northbound)
- treatment: billboard
- leg: lake_city_fl_us -> valdosta_ga_us
- at_mi: 12.5
- spoken: Billboard: Stephen Foster State Park, next exit in White Springs. He wrote Florida's state song about the Suwannee River without ever visiting. Some dispatchers work that way.

### Stephen Foster State Park (southbound)
- treatment: billboard
- leg: valdosta_ga_us -> lake_city_fl_us
- at_mi: 46.0
- spoken: Billboard: Stephen Foster State Park, next exit in White Springs. He wrote Florida's state song about the Suwannee River without ever visiting. Some dispatchers work that way.

## Paynes Prairie Preserve State Park, Micanopy (I-75 Exit 374)

Florida's first state preserve and a National Natural Landmark, 21,000 acres
of prairie where wild bison and Spanish-descended wild horses roam; I-75
crosses it. Main entrance on US 441 one mile east of I-75 Exit 374
(floridastateparks.org; Wikipedia; Spectrum News, February 28, 2025).
Southbound legs join I-75 inside Gainesville and list no exit before 374, so
the southbound signs read "ahead".

### Paynes Prairie (southbound)
- treatment: billboard
- leg: gainesville_fl_us -> orlando_fl_us
- at_mi: 5.5
- spoken: Billboard: Paynes Prairie Preserve, ahead. Wild bison and wild horses roam it, and this highway runs straight across. The bison ask that you keep moving.

### Paynes Prairie (southbound)
- treatment: billboard
- leg: gainesville_fl_us -> lakeland_fl_us
- at_mi: 5.5
- spoken: Billboard: Paynes Prairie Preserve, ahead. Wild bison and wild horses roam it, and this highway runs straight across. The bison ask that you keep moving.

### Paynes Prairie (northbound)
- treatment: billboard
- leg: orlando_fl_us -> gainesville_fl_us
- at_mi: 100.2
- spoken: Billboard: Paynes Prairie Preserve, ahead. Wild bison and wild horses roam it, and this highway runs straight across. The bison ask that you keep moving.

### Paynes Prairie (northbound)
- treatment: billboard
- leg: lakeland_fl_us -> gainesville_fl_us
- at_mi: 129.2
- spoken: Billboard: Paynes Prairie Preserve, ahead. Wild bison and wild horses roam it, and this highway runs straight across. The bison ask that you keep moving.

## Gainesville (existing Gator Country copy, verbatim)

The Gator Country town sign stands northbound on the Orlando leg only. These
add it to the other two approaches, three and six miles out.

### Gator Country (northbound)
- treatment: billboard
- leg: lakeland_fl_us -> gainesville_fl_us
- at_mi: 141.0
- spoken: Billboard: Gainesville is home to the Florida Gators and the Swamp. A scientist mixed the first batch of Gatorade here to keep the football team from wilting in the heat, and Tom Petty grew up here too.

### Gator Country (westbound)
- treatment: billboard
- leg: jacksonville_fl_us -> gainesville_fl_us
- at_mi: 66.0
- spoken: Billboard: Gainesville is home to the Florida Gators and the Swamp. A scientist mixed the first batch of Gatorade here to keep the football team from wilting in the heat, and Tom Petty grew up here too.

## Ocala and Silver Springs (existing Glass-Bottom Boats copy, verbatim)

Silver Springs State Park, where the glass-bottom boat was first put on the
water, is the place behind this town sign. It stands southbound on US 301
only; these add it to the Interstate 75 approaches to Ocala.

### Glass-Bottom Boats (southbound)
- treatment: billboard
- leg: gainesville_fl_us -> orlando_fl_us
- at_mi: 31.0
- spoken: Billboard: Ocala sits in horse country, where the springs run so clear that Floridians invented the glass-bottom boat to look into them. Marion County also raises thoroughbreds by the thousand on rolling green pastures nobody expects to find in Florida.

### Glass-Bottom Boats (southbound)
- treatment: billboard
- leg: gainesville_fl_us -> lakeland_fl_us
- at_mi: 31.0
- spoken: Billboard: Ocala sits in horse country, where the springs run so clear that Floridians invented the glass-bottom boat to look into them. Marion County also raises thoroughbreds by the thousand on rolling green pastures nobody expects to find in Florida.

### Glass-Bottom Boats (northbound)
- treatment: billboard
- leg: orlando_fl_us -> gainesville_fl_us
- at_mi: 71.0
- spoken: Billboard: Ocala sits in horse country, where the springs run so clear that Floridians invented the glass-bottom boat to look into them. Marion County also raises thoroughbreds by the thousand on rolling green pastures nobody expects to find in Florida.

### Glass-Bottom Boats (northbound)
- treatment: billboard
- leg: lakeland_fl_us -> gainesville_fl_us
- at_mi: 100.0
- spoken: Billboard: Ocala sits in horse country, where the springs run so clear that Floridians invented the glass-bottom boat to look into them. Marion County also raises thoroughbreds by the thousand on rolling green pastures nobody expects to find in Florida.

### Glass-Bottom Boats (northbound)
- treatment: billboard
- leg: tampa_fl_us -> ocala_fl_us
- at_mi: 88.0
- spoken: Billboard: Ocala sits in horse country, where the springs run so clear that Floridians invented the glass-bottom boat to look into them. Marion County also raises thoroughbreds by the thousand on rolling green pastures nobody expects to find in Florida.

### Glass-Bottom Boats (northbound)
- treatment: billboard
- leg: spring_hill_fl_us -> ocala_fl_us
- at_mi: 68.0
- spoken: Billboard: Ocala sits in horse country, where the springs run so clear that Floridians invented the glass-bottom boat to look into them. Marion County also raises thoroughbreds by the thousand on rolling green pastures nobody expects to find in Florida.

## Don Garlits Museum of Drag Racing, Ocala (I-75 Exit 341)

Dragsters, funny cars and several Swamp Rats, about 270 cars in three
buildings, open daily 9 to 5, at 13700 SW 16th Avenue just east of I-75 Exit
341 (garlits.com; Spectrum News, May 22, 2026, which has Garlits, 94, still
greeting visitors). Garlits was the first drag racer to officially pass 200
miles an hour, at 201.34 in August 1964 (Wikipedia; Sports Illustrated
vault, August 31, 1964). The Spring Hill leg rides I-75 north from Exit 314.

### Garlits Museum (southbound)
- treatment: billboard
- leg: gainesville_fl_us -> orlando_fl_us
- at_mi: 46.3
- spoken: Billboard: The Don Garlits Museum of Drag Racing, next exit. Big Daddy was the first drag racer past two hundred miles an hour. Not in this lane.

### Garlits Museum (southbound)
- treatment: billboard
- leg: gainesville_fl_us -> lakeland_fl_us
- at_mi: 46.4
- spoken: Billboard: The Don Garlits Museum of Drag Racing, next exit. Big Daddy was the first drag racer past two hundred miles an hour. Not in this lane.

### Garlits Museum (southbound)
- treatment: billboard
- leg: ocala_fl_us -> tampa_fl_us
- at_mi: 14.8
- spoken: Billboard: The Don Garlits Museum of Drag Racing, next exit. Big Daddy was the first drag racer past two hundred miles an hour. Not in this lane.

### Garlits Museum (southbound)
- treatment: billboard
- leg: ocala_fl_us -> spring_hill_fl_us
- at_mi: 14.4
- spoken: Billboard: The Don Garlits Museum of Drag Racing, next exit. Big Daddy was the first drag racer past two hundred miles an hour. Not in this lane.

### Garlits Museum (northbound)
- treatment: billboard
- leg: orlando_fl_us -> gainesville_fl_us
- at_mi: 65.1
- spoken: Billboard: The Don Garlits Museum of Drag Racing, next exit. Big Daddy was the first drag racer past two hundred miles an hour. Not in this lane.

### Garlits Museum (northbound)
- treatment: billboard
- leg: lakeland_fl_us -> gainesville_fl_us
- at_mi: 94.0
- spoken: Billboard: The Don Garlits Museum of Drag Racing, next exit. Big Daddy was the first drag racer past two hundred miles an hour. Not in this lane.

### Garlits Museum (northbound)
- treatment: billboard
- leg: tampa_fl_us -> ocala_fl_us
- at_mi: 81.6
- spoken: Billboard: The Don Garlits Museum of Drag Racing, next exit. Big Daddy was the first drag racer past two hundred miles an hour. Not in this lane.

### Garlits Museum (northbound)
- treatment: billboard
- leg: spring_hill_fl_us -> ocala_fl_us
- at_mi: 60.0
- spoken: Billboard: The Don Garlits Museum of Drag Racing, next exit. Big Daddy was the first drag racer past two hundred miles an hour. Not in this lane.

## Florida Citrus Tower, Clermont (US 27)

A 226-foot observation tower built in 1956 over the citrus groves, with an
elevator to a glass-enclosed deck 22 stories up; it marked 70 years in June
2026. On US 27 just north of SR 50 (florida-backroads-travel.com; Lake and
Sumter Style, June 12, 2026; The History Center). The freezes of the 1980s
ended most of the Lake County groves (The History Center). The Gainesville to
Lakeland leg runs US 27 right past it. The leg's existing Presidents Hall of
Fame callout, a mile south and still open, sets how close the signs can come.

### Citrus Tower (southbound)
- treatment: billboard
- leg: gainesville_fl_us -> lakeland_fl_us
- at_mi: 89.5
- spoken: Billboard: The Florida Citrus Tower, ahead in Clermont. Built in nineteen fifty-six to look out over the orange groves. The groves moved on. The tower stayed.

### Citrus Tower (northbound)
- treatment: billboard
- leg: lakeland_fl_us -> gainesville_fl_us
- at_mi: 46.5
- spoken: Billboard: The Florida Citrus Tower, ahead in Clermont. Built in nineteen fifty-six to look out over the orange groves. The groves moved on. The tower stayed.

# The First Coast

## Jacksonville Zoo and Gardens (I-95 Exit 358A)

Opened May 12, 1914, with a single red deer fawn; 370 Zoo Parkway, a quarter
mile off I-95 Exit 358A (Wikipedia; the zoo's directions). Exit 358 is not in
the leg's exit list; its milepost comes from the dense road geometry, between
Exits 356 and 360. Southbound, the Trout River callout leaves only a short
slot, about a mile before the exit.

### Jacksonville Zoo (northbound)
- treatment: billboard
- leg: jacksonville_fl_us -> brunswick_ga_us
- at_mi: 5.1
- spoken: Billboard: The Jacksonville Zoo and Gardens, next exit. It opened in nineteen fourteen with exactly one deer. Everything since has been an add-on.

### Jacksonville Zoo (southbound)
- treatment: billboard
- leg: brunswick_ga_us -> jacksonville_fl_us
- at_mi: 61.8
- spoken: Billboard: The Jacksonville Zoo and Gardens, next exit. It opened in nineteen fourteen with exactly one deer. Everything since has been an add-on.

## Fort Clinch State Park, Amelia Island (I-95 Exit 373)

An 1847 brick fort at the north tip of Amelia Island; it changed hands in the
Civil War without a battle, and on the first weekend of each month
interpreters staff it as the Union garrison of 1864. From I-95 Exit 373, A1A
east through Fernandina Beach, about fifteen miles (floridastateparks.org;
Wikipedia, "Fort Clinch").

### Fort Clinch (northbound)
- treatment: billboard
- leg: jacksonville_fl_us -> brunswick_ga_us
- at_mi: 19.3
- spoken: Billboard: Fort Clinch, next exit, out on Amelia Island. The first weekend of every month, its garrison reports for duty dressed for eighteen sixty-four. Always on time.

### Fort Clinch (southbound)
- treatment: billboard
- leg: brunswick_ga_us -> jacksonville_fl_us
- at_mi: 46.1
- spoken: Billboard: Fort Clinch, next exit, out on Amelia Island. The first weekend of every month, its garrison reports for duty dressed for eighteen sixty-four. Always on time.

## Saint Augustine (existing Oldest City copy, verbatim)

The town sign stands southbound on the Jacksonville to Miami leg only. These
add it to the other five legs and directions that pass Saint Augustine on
I-95, each before the city's exits. Its copy already names the Castillo, the
college and the Fountain of Youth, so those three get no signs of their own.

### The Oldest City (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 296.0
- spoken: Billboard: Saint Augustine is the oldest city in America. The Spanish founded it in fifteen sixty-five, more than forty years before Jamestown. It has a stone fort that never fell, a college inside a palace, and a spring Ponce de Leon called the Fountain of Youth.

### The Oldest City (northbound)
- treatment: billboard
- leg: palm_coast_fl_us -> jacksonville_fl_us
- at_mi: 9.0
- spoken: Billboard: Saint Augustine is the oldest city in America. The Spanish founded it in fifteen sixty-five, more than forty years before Jamestown. It has a stone fort that never fell, a college inside a palace, and a spring Ponce de Leon called the Fountain of Youth.

### The Oldest City (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> palm_coast_fl_us
- at_mi: 29.0
- spoken: Billboard: Saint Augustine is the oldest city in America. The Spanish founded it in fifteen sixty-five, more than forty years before Jamestown. It has a stone fort that never fell, a college inside a palace, and a spring Ponce de Leon called the Fountain of Youth.

### The Oldest City (northbound)
- treatment: billboard
- leg: orlando_fl_us -> jacksonville_fl_us
- at_mi: 92.5
- spoken: Billboard: Saint Augustine is the oldest city in America. The Spanish founded it in fifteen sixty-five, more than forty years before Jamestown. It has a stone fort that never fell, a college inside a palace, and a spring Ponce de Leon called the Fountain of Youth.

### The Oldest City (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> orlando_fl_us
- at_mi: 27.0
- spoken: Billboard: Saint Augustine is the oldest city in America. The Spanish founded it in fifteen sixty-five, more than forty years before Jamestown. It has a stone fort that never fell, a college inside a palace, and a spring Ponce de Leon called the Fountain of Youth.

## Saint Augustine Alligator Farm Zoological Park (I-95 Exit 311)

Open since May 20, 1893, at 999 Anastasia Boulevard; since 1993 it has kept
all 24 living species of crocodilian, the only place that does
(alligatorfarm.com history; Wikipedia). From I-95 Exit 311, SR 207 to SR 312
east, then A1A north on Anastasia Island. Northbound on the Palm Coast leg,
a car museum and a village sit between Exits 305 and 311, so that sign reads
"ahead".

### Alligator Farm (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 38.4
- spoken: Billboard: Saint Augustine Alligator Farm, next exit. Open since eighteen ninety-three, home to every living kind of crocodilian. They all smile. None of them mean it.

### Alligator Farm (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 302.8
- spoken: Billboard: Saint Augustine Alligator Farm, next exit. Open since eighteen ninety-three, home to every living kind of crocodilian. They all smile. None of them mean it.

### Alligator Farm (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> palm_coast_fl_us
- at_mi: 38.5
- spoken: Billboard: Saint Augustine Alligator Farm, next exit. Open since eighteen ninety-three, home to every living kind of crocodilian. They all smile. None of them mean it.

### Alligator Farm (northbound)
- treatment: billboard
- leg: palm_coast_fl_us -> jacksonville_fl_us
- at_mi: 13.5
- spoken: Billboard: Saint Augustine Alligator Farm, ahead. Open since eighteen ninety-three, home to every living kind of crocodilian. They all smile. None of them mean it.

### Alligator Farm (northbound)
- treatment: billboard
- leg: orlando_fl_us -> jacksonville_fl_us
- at_mi: 97.2
- spoken: Billboard: Saint Augustine Alligator Farm, next exit. Open since eighteen ninety-three, home to every living kind of crocodilian. They all smile. None of them mean it.

### Alligator Farm (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> orlando_fl_us
- at_mi: 38.5
- spoken: Billboard: Saint Augustine Alligator Farm, next exit. Open since eighteen ninety-three, home to every living kind of crocodilian. They all smile. None of them mean it.

## Ripley's Believe It or Not, Saint Augustine (I-95 Exit 318)

The first permanent Ripley's museum, opened December 25, 1950, in Castle
Warden, an 1887 winter home that Robert Ripley repeatedly tried and failed to
buy before he died in 1949; 19 San Marco Avenue, open daily
(ripleys.com; Legends of America). SR 16 from Exit 318 leads to San Marco
Avenue. The Oldest City sign sits so close to Exit 318 that "next exit" has
no room on some legs, so every Ripley's sign reads "ahead". The copy names
the museum, not the slogan.

### Ripley's (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 27.5
- spoken: Billboard: The first Ripley's museum, ahead in Saint Augustine. Robert Ripley kept trying to buy the castle. His collection moved in the year after he died.

### Ripley's (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 308.5
- spoken: Billboard: The first Ripley's museum, ahead in Saint Augustine. Robert Ripley kept trying to buy the castle. His collection moved in the year after he died.

### Ripley's (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> palm_coast_fl_us
- at_mi: 32.0
- spoken: Billboard: The first Ripley's museum, ahead in Saint Augustine. Robert Ripley kept trying to buy the castle. His collection moved in the year after he died.

### Ripley's (northbound)
- treatment: billboard
- leg: palm_coast_fl_us -> jacksonville_fl_us
- at_mi: 24.5
- spoken: Billboard: The first Ripley's museum, ahead in Saint Augustine. Robert Ripley kept trying to buy the castle. His collection moved in the year after he died.

### Ripley's (northbound)
- treatment: billboard
- leg: orlando_fl_us -> jacksonville_fl_us
- at_mi: 103.0
- spoken: Billboard: The first Ripley's museum, ahead in Saint Augustine. Robert Ripley kept trying to buy the castle. His collection moved in the year after he died.

### Ripley's (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> orlando_fl_us
- at_mi: 31.0
- spoken: Billboard: The first Ripley's museum, ahead in Saint Augustine. Robert Ripley kept trying to buy the castle. His collection moved in the year after he died.

## Marineland, A1A north of Palm Coast (I-95 Exit 289)

The world's first oceanarium, opened in 1938 as an underwater filming studio,
on the National Register; 9600 Oceanshore Boulevard (A1A), about ten miles
from I-95 by Palm Coast Parkway (visitflagler.com). It stayed open through
its owner's bankruptcy and a court-ordered sale, and is under new owners and
management in 2026 (AskFlagler, October 30, 2025; Spectrum News, January 21,
2026; Jax Today, May 20, 2026). The signs read "ahead" because the turn is
by way of the coast road.

### Marineland (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 55.0
- spoken: Billboard: Marineland, ahead on the beach road. The world's first oceanarium opened here in nineteen thirty-eight as an underwater movie studio. The dolphins still expect top billing.

### Marineland (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 282.3
- spoken: Billboard: Marineland, ahead on the beach road. The world's first oceanarium opened here in nineteen thirty-eight as an underwater movie studio. The dolphins still expect top billing.

### Marineland (northbound)
- treatment: billboard
- leg: orlando_fl_us -> jacksonville_fl_us
- at_mi: 77.3
- spoken: Billboard: Marineland, ahead on the beach road. The world's first oceanarium opened here in nineteen thirty-eight as an underwater movie studio. The dolphins still expect top billing.

### Marineland (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> orlando_fl_us
- at_mi: 55.0
- spoken: Billboard: Marineland, ahead on the beach road. The world's first oceanarium opened here in nineteen thirty-eight as an underwater movie studio. The dolphins still expect top billing.

### Marineland (northbound)
- treatment: billboard
- leg: daytona_beach_fl_us -> palm_coast_fl_us
- at_mi: 30.0
- spoken: Billboard: Marineland, ahead on the beach road. The world's first oceanarium opened here in nineteen thirty-eight as an underwater movie studio. The dolphins still expect top billing.

### Marineland (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> palm_coast_fl_us
- at_mi: 47.0
- spoken: Billboard: Marineland, ahead on the beach road. The world's first oceanarium opened here in nineteen thirty-eight as an underwater movie studio. The dolphins still expect top billing.

# Daytona, Orlando and the Space Coast

## Daytona Beach (existing World Center of Racing copy, verbatim)

The town sign stands only northbound on the Daytona to Palm Coast leg, three
miles after leaving the city. These put it before Daytona Beach on the six
legs and directions that arrive or pass without one.

### The World Center of Racing (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 78.0
- spoken: Billboard: Daytona Beach is the World Center of Racing and home of the Daytona Five Hundred. The beach is so hard and flat that you can drive a car right onto the sand, which is how the racing started.

### The World Center of Racing (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 247.0
- spoken: Billboard: Daytona Beach is the World Center of Racing and home of the Daytona Five Hundred. The beach is so hard and flat that you can drive a car right onto the sand, which is how the racing started.

### The World Center of Racing (eastbound)
- treatment: billboard
- leg: orlando_fl_us -> daytona_beach_fl_us
- at_mi: 44.0
- spoken: Billboard: Daytona Beach is the World Center of Racing and home of the Daytona Five Hundred. The beach is so hard and flat that you can drive a car right onto the sand, which is how the racing started.

### The World Center of Racing (eastbound)
- treatment: billboard
- leg: orlando_fl_us -> jacksonville_fl_us
- at_mi: 42.0
- spoken: Billboard: Daytona Beach is the World Center of Racing and home of the Daytona Five Hundred. The beach is so hard and flat that you can drive a car right onto the sand, which is how the racing started.

### The World Center of Racing (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> orlando_fl_us
- at_mi: 76.0
- spoken: Billboard: Daytona Beach is the World Center of Racing and home of the Daytona Five Hundred. The beach is so hard and flat that you can drive a car right onto the sand, which is how the racing started.

### The World Center of Racing (southbound)
- treatment: billboard
- leg: palm_coast_fl_us -> daytona_beach_fl_us
- at_mi: 24.5
- spoken: Billboard: Daytona Beach is the World Center of Racing and home of the Daytona Five Hundred. The beach is so hard and flat that you can drive a car right onto the sand, which is how the racing started.

## Blue Spring State Park, Orange City (I-4 Exit 114)

The winter refuge where hundreds of manatees gather in the 72-degree spring
run from about mid-November to mid-March, watched from a half-mile
boardwalk; I-4 Exit 114, SR 472 to US 17-92 south, then French Avenue two
miles west (floridastateparks.org brochure; Spectrum News, December 27,
2024). Open all year; the copy says winter. Lake Helen and the Postal Museum
callouts sit near Exit 114, so all four signs read "ahead".

### Blue Spring (westbound)
- treatment: billboard
- leg: daytona_beach_fl_us -> orlando_fl_us
- at_mi: 19.0
- spoken: Billboard: Blue Spring State Park, ahead in Orange City. Every winter, hundreds of manatees crowd into the warm spring to wait out the cold. Snowbirds, only heavier.

### Blue Spring (eastbound)
- treatment: billboard
- leg: orlando_fl_us -> daytona_beach_fl_us
- at_mi: 27.6
- spoken: Billboard: Blue Spring State Park, ahead in Orange City. Every winter, hundreds of manatees crowd into the warm spring to wait out the cold. Snowbirds, only heavier.

### Blue Spring (eastbound)
- treatment: billboard
- leg: orlando_fl_us -> jacksonville_fl_us
- at_mi: 27.0
- spoken: Billboard: Blue Spring State Park, ahead in Orange City. Every winter, hundreds of manatees crowd into the warm spring to wait out the cold. Snowbirds, only heavier.

### Blue Spring (westbound)
- treatment: billboard
- leg: jacksonville_fl_us -> orlando_fl_us
- at_mi: 104.5
- spoken: Billboard: Blue Spring State Park, ahead in Orange City. Every winter, hundreds of manatees crowd into the warm spring to wait out the cold. Snowbirds, only heavier.

## Central Florida Zoo and Botanical Gardens, Sanford (I-4 Exit 104)

Started in 1923 when a traveling circus gave a rhesus monkey to the Sanford
Elks Club and the fire department took it in; at 3755 West Seminole
Boulevard on Lake Monroe since 1975, at I-4 Exit 104, open daily 9 to 5
(centralfloridazoo.org history; Wikipedia). Eastbound the Heathrow village
and the Saint Johns River callouts bracket Exit 104, so every sign reads
"ahead".

### Central Florida Zoo (westbound)
- treatment: billboard
- leg: daytona_beach_fl_us -> orlando_fl_us
- at_mi: 32.5
- spoken: Billboard: The Central Florida Zoo, ahead in Sanford. It began in nineteen twenty-three, when a passing circus left a monkey with the Elks Club. Things escalated.

### Central Florida Zoo (eastbound)
- treatment: billboard
- leg: orlando_fl_us -> daytona_beach_fl_us
- at_mi: 14.5
- spoken: Billboard: The Central Florida Zoo, ahead in Sanford. It began in nineteen twenty-three, when a passing circus left a monkey with the Elks Club. Things escalated.

### Central Florida Zoo (eastbound)
- treatment: billboard
- leg: orlando_fl_us -> jacksonville_fl_us
- at_mi: 19.6
- spoken: Billboard: The Central Florida Zoo, ahead in Sanford. It began in nineteen twenty-three, when a passing circus left a monkey with the Elks Club. Things escalated.

### Central Florida Zoo (westbound)
- treatment: billboard
- leg: jacksonville_fl_us -> orlando_fl_us
- at_mi: 117.5
- spoken: Billboard: The Central Florida Zoo, ahead in Sanford. It began in nineteen twenty-three, when a passing circus left a monkey with the Elks Club. Things escalated.

## Morse Museum, Winter Park (I-4 Exit 87, Fairbanks Avenue)

The Charles Hosmer Morse Museum of American Art, with the world's most
comprehensive collection of Louis Comfort Tiffany's work, including the
chapel he built for the 1893 Chicago World's Fair; 445 North Park Avenue,
1.8 miles east of I-4 on Fairbanks Avenue (morsemuseum.org). Eastbound
only: westbound, the Eatonville, Maitland and Wekiwa Springs callouts leave
no slot on either leg.

### Morse Museum (eastbound)
- treatment: billboard
- leg: orlando_fl_us -> jacksonville_fl_us
- at_mi: 2.5
- spoken: Billboard: The Morse Museum, ahead in Winter Park. The most complete collection of Tiffany glass in the world, a whole chapel included. Every bit is breakable.

### Morse Museum (eastbound)
- treatment: billboard
- leg: orlando_fl_us -> daytona_beach_fl_us
- at_mi: 2.5
- spoken: Billboard: The Morse Museum, ahead in Winter Park. The most complete collection of Tiffany glass in the world, a whole chapel included. Every bit is breakable.

## WonderWorks, International Drive, Orlando (I-4 Exit 74A)

A science attraction in a building made to look like a mansion dropped
upside down, open since 1998; 9067 International Drive, off I-4 Exit 74A by
Sand Lake Road (Roadside America; ClickOrlando, March 6, 2023;
wonderworksonline.com, with 2026 events posted). Westbound the Tangelo Park
and Doctor Phillips callouts sit by the exit, so the signs read "ahead".

### WonderWorks (westbound)
- treatment: billboard
- leg: orlando_fl_us -> tampa_fl_us
- at_mi: 5.0
- spoken: Billboard: WonderWorks, ahead on International Drive. The whole building stands upside down, roof on the ground. Do not try that with a trailer.

### WonderWorks (eastbound)
- treatment: billboard
- leg: tampa_fl_us -> orlando_fl_us
- at_mi: 72.5
- spoken: Billboard: WonderWorks, ahead on International Drive. The whole building stands upside down, roof on the ground. Do not try that with a trailer.

## Gatorland, Orlando (Florida's Turnpike Exit 249, State Road 417 Exit 11)

Founded in 1949 by Owen Godwin on old cattle land and still family owned,
110 acres with thousands of alligators and crocodiles; in the Gator
Jumparoo show the big ones leap out of the water for their food. 14501 South
Orange Blossom Trail, a mile from Turnpike Exit 249 or SR 417 Exit 11, both
on the Palm Bay to Lakeland leg (gatorland.com; Wikipedia). Villages crowd
both exits, so the signs read "ahead".

### Gatorland (westbound)
- treatment: billboard
- leg: palm_bay_fl_us -> lakeland_fl_us
- at_mi: 52.0
- spoken: Billboard: Gatorland, ahead, open since nineteen forty-nine. Thousands of alligators, and the big ones jump for chicken at feeding time. Lunch is all that gets them moving.

### Gatorland (eastbound)
- treatment: billboard
- leg: lakeland_fl_us -> palm_bay_fl_us
- at_mi: 39.5
- spoken: Billboard: Gatorland, ahead, open since nineteen forty-nine. Thousands of alligators, and the big ones jump for chicken at feeding time. Lunch is all that gets them moving.

## Kennedy Space Center Visitor Complex (I-95 Exit 212; SR 528 Exit 37)

The Apollo/Saturn V Center, included with admission, displays a real
363-foot Saturn V laid out on its side (kennedyspacecenter.com). KSC's own
directions: from I-95 Exit 212 north on SR 407 to SR 405 east; from Orlando,
SR 528 east to the SR 407 exit, Exit 37 (NASA, "Driving Directions";
Wikipedia, "Florida State Road 407"). The Palm Bay to Orlando leg passes
SR 528 Exit 37 both ways.

### Kennedy Space Center (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 137.6
- spoken: Billboard: Kennedy Space Center, next exit. A real Saturn Five rocket lies inside, three hundred sixty-three feet of it. And you thought your trailer was long.

### Kennedy Space Center (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 204.8
- spoken: Billboard: Kennedy Space Center, next exit. A real Saturn Five rocket lies inside, three hundred sixty-three feet of it. And you thought your trailer was long.

### Kennedy Space Center (eastbound)
- treatment: billboard
- leg: orlando_fl_us -> palm_bay_fl_us
- at_mi: 33.5
- spoken: Billboard: Kennedy Space Center, next exit. A real Saturn Five rocket lies inside, three hundred sixty-three feet of it. And you thought your trailer was long.

### Kennedy Space Center (westbound)
- treatment: billboard
- leg: palm_bay_fl_us -> orlando_fl_us
- at_mi: 36.8
- spoken: Billboard: Kennedy Space Center, next exit. A real Saturn Five rocket lies inside, three hundred sixty-three feet of it. And you thought your trailer was long.

## Ron Jon Surf Shop, Cocoa Beach (I-95 Exit 201, SR 520 east)

The flagship, a two-acre store with more than 52,000 square feet, often
called the world's largest surf shop, at A1A and SR 520 in Cocoa Beach,
about eleven miles east of I-95 (surfertoday.com; travelingwithmj.com). The
copy names the shop and avoids its slogan. The leg lists the SR 520
interchange as Exit 202 on one leg and 201 on the other; Exits 201 and 202
are a mile apart, so the signs read "ahead".

### Ron Jon (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 147.4
- spoken: Billboard: Ron Jon Surf Shop, ahead in Cocoa Beach. Two acres of surf shop, and not one board long enough for your trailer. They checked.

### Ron Jon (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 195.0
- spoken: Billboard: Ron Jon Surf Shop, ahead in Cocoa Beach. Two acres of surf shop, and not one board long enough for your trailer. They checked.

### Ron Jon (northbound)
- treatment: billboard
- leg: palm_bay_fl_us -> orlando_fl_us
- at_mi: 27.5
- spoken: Billboard: Ron Jon Surf Shop, ahead in Cocoa Beach. Two acres of surf shop, and not one board long enough for your trailer. They checked.

### Ron Jon (southbound)
- treatment: billboard
- leg: orlando_fl_us -> palm_bay_fl_us
- at_mi: 43.0
- spoken: Billboard: Ron Jon Surf Shop, ahead in Cocoa Beach. Two acres of surf shop, and not one board long enough for your trailer. They checked.

## Brevard Zoo, Melbourne (I-95 Exit 191, Wickham Road)

Opened March 26, 1994, built by more than 16,000 community volunteers,
billed as the world's largest volunteer community build; 8225 North Wickham
Road, just east of I-95 Exit 191 (Wikipedia; brevardzoo.org). The Viera
village callout sits by Exit 191, so the signs read "ahead".

### Brevard Zoo (southbound)
- treatment: billboard
- leg: jacksonville_fl_us -> miami_fl_us
- at_mi: 157.4
- spoken: Billboard: The Brevard Zoo, ahead in Melbourne. Sixteen thousand neighbors built it by hand in the early nineties. Try getting that many to help you move.

### Brevard Zoo (northbound)
- treatment: billboard
- leg: miami_fl_us -> jacksonville_fl_us
- at_mi: 183.8
- spoken: Billboard: The Brevard Zoo, ahead in Melbourne. Sixteen thousand neighbors built it by hand in the early nineties. Try getting that many to help you move.

### Brevard Zoo (northbound)
- treatment: billboard
- leg: palm_bay_fl_us -> orlando_fl_us
- at_mi: 17.0
- spoken: Billboard: The Brevard Zoo, ahead in Melbourne. Sixteen thousand neighbors built it by hand in the early nineties. Try getting that many to help you move.

### Brevard Zoo (southbound)
- treatment: billboard
- leg: orlando_fl_us -> palm_bay_fl_us
- at_mi: 51.5
- spoken: Billboard: The Brevard Zoo, ahead in Melbourne. Sixteen thousand neighbors built it by hand in the early nineties. Try getting that many to help you move.

## Notes for the owner

Thirty attractions, 121 signs: 26 new attractions with 102 new-copy signs,
plus 19 signs that reuse four existing Florida town lines verbatim on legs
and directions that had none. A dry run of `tools/bake_billboards.py` on
this sheet resolves every leg and bakes all 121 (no `--write`). A spacing
check against the baked legs found no callout within 2.2 miles of any sign
in its direction, counting every other sign here. Every new line is spelled
out with no digits and runs 21 to 27 words; the four reused lines run 37 to
46 words because they are copied verbatim. Every joke is original.

Billboard law. Florida permits commercial billboards along Interstates and
federal-aid primary highways in commercial and industrial areas, by FDOT
permit, at least 1,500 feet apart on an Interstate (Florida Statutes
479.07(9)(a), 479.111(2);
https://flsenate.gov/Laws/Statutes/2025/Chapter479/All). Chapter 479 says
nothing about scenic highways. The federal Highway Beautification Act
barrier applies instead: no new billboards on the scenic segments of
state-designated scenic byways on the Interstate and primary system (23
U.S.C. 131(s); FDOT's 1972 agreement with the federal government; Florida
Outdoor Advertising Association, https://foaa.org/federal_laws). Florida has
27 designated scenic highways (floridascenichighways.com). Those nearest
these legs are Scenic Highway 30A, the A1A Scenic and Historic Coastal
Byway, the Old Florida Heritage Highway (US 441 and county roads around
Paynes Prairie), the Indian River Lagoon National Scenic Byway (US 1, A1A
and the lagoon causeways) and the Green Mountain Scenic Byway (Oakland
Avenue, CR 455 and CR 561 around Lake Apopka). Every sign here stands on an
Interstate, the Turnpike, SR 528 west of I-95, SR 417, or US 27, 98, 221,
231, 301, 319 and 331 away from those byways. The Seaside signs are on US
98, not 30A. The Clermont signs are on US 27, which the Green Mountain
byway does not use.

Attractions, sources, and what was checked:

- **Florida Caverns State Park.** Cave tours daily, first come first served,
  Exit 142, then SR 71 north and US 90 west
  (https://www.floridastateparks.org/park/Florida-Caverns). The only cave
  tours in Florida, 65 degrees, CCC-built, opened 1942
  (https://www.florida-backroads-travel.com/florida-caverns-state-park.html,
  April 2025). The park sits five to six miles from I-10, so "north of
  Marianna" stands in for a mileage.
- **Falling Waters State Park.** 73-foot waterfall into a 100-foot sinkhole,
  Exit 120 and SR 77 south (https://en.wikipedia.org/wiki/Falling_Waters_State_Park).
  Seasonal: in a dry spell the fall slows to a trickle. The copy still holds.
- **Ponce de Leon Springs State Park.** 68 degrees, 14 million gallons a day,
  half a mile south of US 90
  (https://www.florida-backroads-travel.com/ponce-de-leon-springs-state-park.html).
- **Lake DeFuniak.** Almost perfectly round, about a mile around
  (https://en.wikipedia.org/wiki/Lake_DeFuniak). "Roundabout" is the joke,
  not a claim about traffic.
- **Seaside.** Filming town for The Truman Show
  (https://en.wikipedia.org/wiki/Seaside,_Florida). The sign names a town,
  not a ticketed attraction. Drop it if the sheet should stay
  attraction-only.
- **Milton.** Canoe Capital of Florida by act of the legislature
  (https://floridians.visitflorida.com/en-us/cities/milton.html), the
  Blackwater a sand-bottom river
  (https://en.wikipedia.org/wiki/Blackwater_River_(Florida)).
- **National Naval Aviation Museum.** Free, daily 9 to 4
  (https://www.navalaviationmuseum.org/), some 150 aircraft
  (https://history.navy.mil/content/history/museums/nnam/about-us/about-the-museum.html).
  Daily public access through the West Gate resumed May 1, 2026, with a
  REAL ID or passport required
  (https://www.fox10tv.com/2026/05/02/daily-public-access-resumes-naval-air-station-pensacola/).
  Unsure: base access has changed three times since 2019. The copy leaves
  the rules out so it does not go stale. If the base closes to the public
  again, the sign is false.
- **Florida's Historic Capitol.** Free, open 363 days a year
  (https://baynews9.com/fl/tampa/news/2024/03/07/the-florida-historic-capitol-museum-is-free--open-363-days-a-year-and-in-the-shadow-of-modern-government-in-tallahassee).
  The 22-story Capitol, finished in 1977, was first planned with the old
  building demolished. Public outcry saved it
  (https://www.tallahasseemagazine.com/?p=1061; skyscraperpage.com).
- **Greenville and Ray Charles.** The statue at the piano and the childhood
  home (https://florida-backroads-travel.com/greenville-florida.html;
  https://www.wctv.tv/2025/09/24/greenville-celebrates-ray-charles-95th-birthday-lasting-impact/).
  The copy is warm, and the joke is about the statue, never his
  blindness. Unsure: whether the childhood home keeps regular hours; the
  copy names only the statue in the public park.
- **Stephen Foster Folk Culture Center State Park.** Carillon of 97 bells,
  Foster never visited Florida
  (https://en.wikipedia.org/wiki/Stephen_Foster_Folk_Culture_Center_State_Park).
  "Old Folks at Home" is still the state song; the copy names neither the
  title nor any lyric.
- **Paynes Prairie Preserve State Park.** Bison and wild horses; open 8 to
  sundown every day; Exit 374 then CR 234 and US 441
  (https://mynews13.com/fl/orlando/news/2025/02/28/visit-florida-s-paynes-prairie-preserve-and-see-wild-horses---bison-roaming-freely;
  https://en.wikipedia.org/wiki/Paynes_Prairie_Preserve_State_Park).
- **Don Garlits Museum of Drag Racing.** Open daily 9 to 5, Exit 341
  (https://garlits.com/venue/don-garlits-museum-of-drag-racing/;
  https://mynews13.com/fl/orlando/florida-on-a-tankful/2026/05/22/big-daddy-s-legacy-lives-on-at-ocala-drag-racing-museum).
  First official 200 mph quarter mile, 201.34, August 1, 1964
  (https://en.wikipedia.org/wiki/Don_Garlits;
  https://vault.si.com/vault/1964/08/31/fame-and-terror-at-200-mph). The
  May 2026 article calls him the first past 300. That is wrong (Kenny
  Bernstein, 1992), and the copy does not use it.
- **Florida Citrus Tower.** 226 feet, 1956, 70th anniversary June 2026
  (https://lakeandsumterstyle.com/iconic-citrus-tower-marks-70-years-with-huge-celebration-sunday/;
  https://florida-backroads-travel.com/citrus-tower.html). The Presidents
  Hall of Fame next door is still open (Spectrum News, January 2025), so
  the leg's existing museum callout stays true.
- **Jacksonville Zoo and Gardens.** Opened 1914 with one red deer fawn; Exit
  358A to Zoo Parkway (https://en.wikipedia.org/wiki/Jacksonville_Zoo_and_Gardens;
  https://www.florida-backroads-travel.com/jacksonville-zoo.html).
- **Fort Clinch State Park.** No battles fought there; living history on the
  first weekend of each month; Exit 373 and A1A
  (https://en.wikipedia.org/wiki/Fort_Clinch;
  https://www.floridastateparks.org/parks-and-trails/fort-clinch-state-park).
- **Saint Augustine Alligator Farm.** Opened May 20, 1893; all 24
  crocodilian species since 1993; open daily 9 to 5
  (https://alligatorfarm.com/tickets-info/our-history). The copy says "open
  since" and "home to", which keeps the two dates apart. Unsure: Exit 311
  by SR 207 and SR 312 is the usual route, but drivers also reach it by
  SR 16 and the Bridge of Lions.
- **Ripley's, Saint Augustine.** First permanent museum, December 25, 1950,
  in Castle Warden; open daily; 19 San Marco Avenue
  (https://www.ripleys.com/attractions/ripleys-believe-it-or-not-st-augustine;
  https://www.legendsofamerica.com/fl-ripleysodditorium/). The copy names
  Ripley's plainly and keeps clear of the "believe it or not" slogan.
  Owner's call on trademark closeness.
- **Marineland.** World's first oceanarium, 1938
  (https://www.visitflagler.com/listing/marineland-dolphin-adventure/270614/).
  The Dolphin Company bankruptcy sale went to a local group, and the park
  never closed (https://askflagler.com/7-1m-marineland-sale-halted-for-now-by-judge/;
  https://mynews13.com/fl/orlando/news/2026/01/21/marineland-dolphin-adventure-under-new-ownership;
  https://jaxtoday.org/2026/05/20/marineland-new-management/). Unsure:
  under the new owners it may drop "Dolphin Adventure" from its name; the
  copy says only "Marineland".
- **Blue Spring State Park.** Manatees from about mid-November to mid-March
  in 72-degree water; Exit 114
  (https://mynews13.com/fl/orlando/news/2024/12/27/hundreds-of-manatees-have-moved-into-blue-spring-in-volusia-county-for-the-winter-months;
  https://floridawildlifeviewing.com/florida_manatees/BlueSpring.htm).
  Seasonal: the sign is heard all year but says "every winter", so it
  stays true in July.
- **Central Florida Zoo.** The circus monkey and the Elks Club
  (https://centralfloridazoo.org/history); open daily 9 to 5, Exit 104
  (https://en.wikipedia.org/wiki/Central_Florida_Zoo_and_Botanical_Gardens).
- **Morse Museum.** The Tiffany collection and chapel; Fairbanks Avenue east
  1.8 miles (https://www.morsemuseum.org/plan-your-visit).
- **WonderWorks Orlando.** Upside-down building at 9067 International Drive,
  Exit 74A (https://www.roadsideamerica.com/tip/281). The site lists 2026
  events (https://www.wonderworksonline.com/orlando/).
- **Gatorland.** Founded 1949, 110 acres, thousands of alligators, the
  Jumparoo show (https://en.wikipedia.org/wiki/Gatorland;
  https://www.blogs.gatorland.com/map-and-directions.shtml). The copy avoids
  the park's own "Alligator Capital of the World" slogan.
- **Kennedy Space Center Visitor Complex.** The Saturn V in the Apollo/Saturn
  V Center, included with admission
  (https://www.kennedyspacecenter.com/explore-attractions/race-to-the-moon/featured-attraction/saturn-v-rocket);
  the official routes by I-95 Exit 212 and SR 528 Exit 37
  (https://public.ksc.nasa.gov/partnerships/about-us/driving-directions/;
  https://en.wikipedia.org/wiki/Florida_State_Road_407).
- **Ron Jon Surf Shop.** Two-acre flagship, 52,000 square feet
  (https://www.surfertoday.com/surfing/the-story-of-ron-jon-surf-shop). The
  existing Space Coast sign mentions "a surf shop the size of a mall".
  That sign is heard only northbound on the West Palm Beach to Palm Bay
  leg, south of this region, so a driver going on north may hear both.
  Unsure: older sources say the store is open around the clock. Current
  hours could not be confirmed, so the copy leaves them out.
- **Brevard Zoo.** Opened March 26, 1994, after 16,000 people built it
  (https://en.wikipedia.org/wiki/Brevard_Zoo).
- **Reused town lines.** The Oldest City, the World Center of Racing,
  Glass-Bottom Boats and Gator Country are copied character for character
  from the baked records. Each heading carries a direction so the bake
  does not replace the original record of the same name on the same leg.

Dropped:

- **Walt Disney World, Universal, SeaWorld, LEGOLAND.** The Orlando pool
  line and the Theme Park Capital sign already name the parks, and the
  instruction was plain or not at all.
- **Castillo de San Marcos, the Fountain of Youth, Flagler College.** The
  Oldest City copy already names all three.
- **Saint Augustine Lighthouse.** Same exit as the Alligator Farm, so it was
  dropped for spacing. The Alligator Farm is the better-known.
- **Olustee Battlefield (I-10), Dade Battlefield (I-75 Exit 314), Kingsley
  Plantation (I-95 Exit 358).** A battlefield and a plantation where people
  were enslaved take no joke. They could be respectful landmark callouts
  if wanted.
- **Wakulla Springs, the John Gorrie Museum in Apalachicola, the phone-booth
  police station in Carrabelle, the Cape San Blas and Saint Marks
  lighthouses.** No leg runs coastal US 98: the Panama City to Tallahassee
  leg goes north on US 231 to I-10.
- **Panama City Beach strip (Gulf World, the second WonderWorks, Ripley's).**
  The leg runs the back highway. WonderWorks and Ripley's are signed
  elsewhere, and Seaside covers that coast.
- **Air Force Armament Museum, Eglin.** No leg runs SR 85 south of
  Crestview.
- **Torreya State Park, Ichetucknee Springs, Rainbow Springs.** More than
  ten miles from every leg. Crystal River and Homosassa Springs are also
  far off, and on the Tampa Bay side.
- **Ponce de Leon Inlet Lighthouse.** About ten miles off I-95 through Port
  Orange, on a stretch the Daytona line already covers.
- **Valiant Air Command Warbird Museum, American Space Museum (Titusville).**
  Same exits as Kennedy Space Center, which is kept.
- **Micanopy.** Same exit as Paynes Prairie.
- **Florida Museum of Natural History.** At the Gainesville city node, where
  Gator Country covers the town.
- **Morse Museum westbound, and the Citrus Tower from the Turnpike.** No
  slot clears the Eatonville, Maitland and Wekiwa Springs callouts
  westbound. The Turnpike passes the tower 2.7 miles away, through
  Clermont streets.
- **Stephen Foster from I-10.** Exit 301, then about ten miles north. The
  I-75 signs, three miles out, are kept.
- **Chautauqua Winery, DeFuniak Exit 85.** A tasting room for drivers, on
  the same exit as Lake DeFuniak.
- **Canopy Roads and Theme Park Capital reuse.** The Tallahassee approaches
  get the Historic Capitol instead. The Orlando approaches already have
  the pool line. The Dothan approach gets no Capitol sign because Canopy
  Roads stands four miles out.
- **Polk County (Florida Southern College's Frank Lloyd Wright buildings in
  Lakeland, Bok Tower, Fantasy of Flight).** Left to the Tampa Bay sheet,
  since Lakeland and Lake Wales sit at Tampa's latitude. If that sheet
  skips them, Florida Southern on I-4 is the one worth adding. Fantasy of
  Flight is not open to the public daily.

Found along the way (data, not this sheet):

- **Highway labels that do not match the routes.** Several Panhandle legs
  are labeled for a road they barely use. "Dothan to Tallahassee, US-84"
  and "Panama City to Tallahassee, US-98" both run US 231 to Cottondale
  and then I-10. "Crestview to Dothan, FL-85" runs I-10 east to Exit 130
  and then US 231. "Panama City to Crestview, SR-79" runs US 98 west and
  US 331 north. The mileposts here follow the real geometry, not the
  labels.
- **Saint Johns River callouts on I-4.** The bridge is between Exits 104 and
  108. On the Daytona to Orlando leg the callout sits at mile 35.0, just
  past Exit 104 westbound. On the Orlando to Jacksonville leg it sits at
  mile 13.9, near Longwood, about eight miles off.
- **Mismatched I-4 exit mileposts.** The Orlando to Jacksonville leg puts
  the SR 46 interchange (101D) at mile 20.7. The Daytona to Orlando leg
  puts it (101C) two miles earlier, eastbound.
- **The existing World Center of Racing sign.** It faces northbound three
  miles after leaving Daytona Beach. With this sheet's southbound sign on
  the same leg, that one could move or go.
- **Exit 358A (Jacksonville Zoo) and Exit 104 (on the Orlando to
  Jacksonville leg) are missing** from those legs' exit lists.
