# Changelog

## Unreleased

### Fixed

- **Controllers are left alone when controller support is off.** With the setting disabled, the game no longer starts up the controller system or grabs a connected pad; turning support on in Settings, Gameplay activates it, and turning it back off releases the controller again.

- **Engine sound now stays present through automatic gear changes.** Shifts still ease the engine tone briefly, without the repeated volume pumping that could sound like the engine was dropping out.

- **Starting the engine no longer dips in volume.** The running engine sound now
  meets the tail of the ignition sound at the same level, then settles smoothly
  down to idle instead of briefly dropping out.

- **Manual and automatic transmissions behave reliably on steep grades.** The
  diesel governor now holds a safe low-gear road speed without quietly damaging
  the engine, and automatic trucks avoid shifts that cannot pull the hill.
- **Transmission changes now apply when you return to an active drive.** The
  game announces the new automatic or manual mode instead of waiting until the
  next trip.
- **Destination signs no longer send you down an early exit.** Navigation now
  favors the interchange nearest the destination over an earlier sign that
  happens to mention the same city.
- **Speeding fines now follow you on bobtail runs.** Empty repositioning trips
  charge accumulated speeding-strike fines and announce the cost in the arrival
  summary instead of silently letting the fines disappear.

### Changed

- **The engine no longer jumps in volume the instant an automatic shift
  finishes.** It now eases back up to full pull over a brief moment, so completed
  shifts sound smooth instead of abruptly snapping back under load.
- **Route alerts no longer repeat at one mile.** Fuel stops, rest stops, and
  other actionable exits now speak once at five miles. State lines speak once
  as you cross them.
- **The soundtrack now uses the finished music throughout the game.** Menu,
  daytime driving, and nighttime driving tracks have been replaced with their
  full-quality versions, normalized to match the existing music. Urban Roll
  also joins the menu rotation as a separate track from its driving version.
- **Automatic shifting now follows real heavy-truck strategy.** Lower gears use
  progressive shift points, the starting gear responds to load and grade,
  light trucks can skip unneeded gears, and braking selects a useful lower gear
  instead of stepping through every ratio. Engine audio now unloads between
  gears instead of sweeping upward as one continuous high-pitched tone.
- **Freight Fate checks for updates again when you leave a terminal.** Returning
  to the main menu from a city terminal or pickup facility now starts a quiet
  background check, so an available update can be installed before you finish
  the session.

### Added

- **The major toll turnpikes now charge realistic tolls.** Running the Kansas
  Turnpike, the Oklahoma turnpikes, the New York Thruway, the Pennsylvania and
  Ohio turnpikes, the Indiana Toll Road, the Illinois Tollway, the Mass Pike, the
  Maine and West Virginia turnpikes now adds an estimated commercial toll to the
  run -- so a toll route is a real cost to weigh against the free way around.

- **Owatonna, Marshalltown, Hinesville, and Spring Hill join the map.** Owatonna
  comes onto Interstate 35 south of Minneapolis, Marshalltown onto US-30 in
  central Iowa, Hinesville ties Fort Stewart into Savannah and Brunswick, and
  Spring Hill opens the US-19 coast north of Tampa.

- **New Jersey and Louisiana fill in.** Toms River and Vineland join the map on
  the Garden State Parkway and in South Jersey, Ruston comes onto Interstate 20
  between Shreveport and Monroe, and Hammond ties Baton Rouge to New Orleans.

- **The Pacific Northwest interior fills in.** Longview comes onto Interstate 5
  between Olympia and Portland, Walla Walla ties into the Tri-Cities and Pendleton
  on US-12, and Port Angeles opens the Olympic Peninsula on US-101.

- **Clarksville now runs straight into Nashville.** The Interstate 24 route from
  Clarksville no longer skips past Nashville, and the drive in from the northwest
  passes Fort Campbell.

- **Northern New England joins the map.** Rutland ties central Vermont to
  Burlington and Albany, Keene links southwest New Hampshire, Lewiston opens
  Maine north of Portland, and Barnstable brings Cape Cod onto the map.

- **The Deep South fills in.** Cullman comes onto Interstate 65 between Huntsville
  and Birmingham, Selma onto US-80 west of Montgomery, Troy onto US-231 toward
  Dothan, and Americus ties into Albany and Columbus in southwest Georgia.

- **Ames, Hickory, Danville, and Yuba City join the map.** Ames comes onto
  Interstate 35 north of Des Moines, Hickory onto Interstate 40 between Asheville
  and Charlotte, Danville onto US-29 between Greensboro and Lynchburg, and Yuba
  City onto California's CA-99 between Sacramento and Chico.

- **Ohio and northwest Pennsylvania fill in.** Zanesville comes onto Interstate 70
  between Columbus and Wheeling, Meadville onto Interstate 79 between Erie and
  Pittsburgh, and Chillicothe and Marion tie into Columbus on US-23.

- **Oxford, Jamestown, Fort Dodge, and Mattoon join the map.** Oxford ties into
  northern Mississippi (Tupelo, Memphis, Clarksdale), Jamestown onto the Southern
  Tier between Erie and Buffalo, Fort Dodge into north-central Iowa, and Mattoon
  onto Interstate 57 between Effingham and Champaign.

- **Wheeling, Columbus, and southwest Florida join the map.** Wheeling comes onto
  Interstate 70 between Columbus and Pittsburgh, Columbus anchors east-central
  Nebraska, and Sarasota and North Port fill the Interstate 75 run down Florida's
  Gulf coast between Tampa and Fort Myers.

- **The West Texas plains fill in.** Plainview comes onto Interstate 27 between
  Lubbock and Amarillo, Big Spring onto Interstate 20 between Midland and Abilene,
  and Hereford ties Amarillo west to Clovis on US-60.

- **Palm Coast, Ridgecrest, and Susanville reach the last corners.** Palm Coast
  comes onto Interstate 95 between Daytona and Jacksonville, and Ridgecrest and
  Susanville open the lonely US-395 desert runs in California -- including the
  mountain climb over the Cascades from Susanville to Redding.

- **The Georgia and South Carolina midlands fill in.** Dublin comes onto
  Interstate 16 between Macon and Savannah, Statesboro ties into Savannah and
  Augusta, and Sumter links Columbia and Florence.

- **Findlay, Dyersburg, and Burlington fill more gaps.** Findlay comes onto
  Interstate 75 between Toledo and Lima, Dyersburg ties northwest Tennessee to
  Memphis and Jackson, and Burlington joins the Mississippi in southeast Iowa
  between Ottumwa and Iowa City.

- **Russellville joins the Arkansas River valley.** Russellville comes onto
  Interstate 40 between Conway and Fort Smith, a real stop on the run west from
  Little Rock.

- **Central Oklahoma fills in.** Stillwater, Ponca City, and Ada join the map,
  linking Oklahoma City, Tulsa, Enid, Bartlesville, Ardmore, and McAlester across
  the middle of the state.

- **Jamestown, Mason City, and Altus fill the last plains gaps.** Jamestown comes
  onto Interstate 94 between Bismarck and Fargo, Mason City onto Interstate 35
  between Albert Lea and Des Moines, and Altus ties into southwestern Oklahoma.

- **Norfolk, Brownwood, and Pampa round out the plains.** Norfolk anchors
  northeast Nebraska (Sioux City, Grand Island, Omaha), Brownwood ties central
  Texas together (Abilene, San Angelo, Lampasas), and Pampa comes onto the map in
  the Texas Panhandle north of Amarillo.

- **Vincennes and Poplar Bluff join the map.** Vincennes seats on the US-41
  corridor between Terre Haute and Evansville, and Poplar Bluff anchors
  southeastern Missouri with runs to Cape Girardeau, Jonesboro, and a US-60 haul
  west into the Ozarks toward Springfield.

- **The Blues Highway fills in at Clarksdale.** Clarksdale joins the map on US-61,
  completing the Delta run from Memphis down through Cleveland to Greenville, with
  an eastern tie to Grenada.

- **The Columbia Gorge opens at The Dalles.** The Dalles comes onto Interstate 84
  between Portland and Pendleton, seating a stop in the Gorge on the run east.

- **East Texas piney woods open at Palestine.** Palestine joins the map hubbing
  Tyler, Lufkin, and College Station on US-69, US-84, and TX-21.

- **Douglas joins southeastern Arizona.** The border town of Douglas ties in over
  the Mule Mountains through Bisbee to Sierra Vista and runs northwest to Tucson.

- **The north country opens at Watertown.** Watertown joins the map on Interstate
  81 north of Syracuse and ties east to Utica over the Tug Hill on NY-12.

- **The southwest Texas border country joins the map.** Uvalde comes onto the
  US-90 run between San Antonio and Del Rio, and the border city of Eagle Pass
  ties in on US-57 and US-277.

- **Central Kansas fills in.** Emporia comes onto the Kansas Turnpike between
  Topeka and Wichita, and Hutchinson and Great Bend open a wheat-country run from
  Wichita and Salina west toward Hays.

- **Hot Springs joins the map in the Ouachitas.** The old resort town links to
  Little Rock and Texarkana on US-70 and runs north to Fort Smith on US-270 --
  a real mountain haul over the Ouachita ridges.

- **The Missouri and Iowa heartland fills in.** Sedalia opens the US-50 run
  between Kansas City and Columbia, and Kirksville and Ottumwa join a US-63
  corridor north from Columbia up into Des Moines.

- **The US-15 route through north-central Pennsylvania opens.** Williamsport joins
  the map on the Susquehanna, linking Harrisburg, State College, and Binghamton --
  including the mountain climb north onto the plateau toward New York.

- **The Grand Strand comes onto the map at Myrtle Beach.** Myrtle Beach seats on
  the coastal US-17 run between Charleston and Wilmington and ties inland to
  Florence and Interstate 95 on US-501.

- **Western Illinois joins along the Mississippi.** The river port of Quincy and
  the rail town of Galesburg come onto the map, opening the Interstate 72 run east
  to Springfield and a proper Interstate 74 stop at Galesburg between Peoria and
  the Quad Cities.

- **The Mississippi Delta opens up at Greenville.** Greenville joins the map with
  US-82 east to Grenada, US-61 south down the Delta to Vicksburg, and a run across
  the river into Arkansas toward Pine Bluff.

- **Southeastern New Mexico's oil country joins the map.** Hobbs anchors the
  Permian Basin with runs to Carlsbad, Lubbock, and Odessa, and Alamogordo opens
  the US-54 and US-70 routes between El Paso, Las Cruces, and Roswell -- including
  the mountain climb over the Sacramentos.

- **Wisconsin's Fox Valley and lakeshore fill in.** Fond du Lac, Oshkosh, and
  Sheboygan join the map, opening the Interstate 41 run up the Fox River Valley
  from Milwaukee to Green Bay and the Interstate 43 lakeshore route past
  Sheboygan.

- **A northern route across the Pennsylvania mountains opens up.** Altoona and
  State College join the map, giving a US-22 and US-322 run from Pittsburgh over
  the Allegheny ridges to Harrisburg -- a real mountain haul alongside the
  Turnpike, with steep grades over the Allegheny Front and the Seven Mountains.

- **Central Indiana fills in around Indianapolis.** Muncie, Anderson, Kokomo,
  Columbus, and Richmond join the map, opening the Interstate 69 run northeast,
  the US-31 haul north to Kokomo, and proper Interstate 65 and 70 stops at
  Columbus and Richmond on the way to Louisville and Dayton.

- **The Colorado River and southern Arizona fill in.** Lake Havasu City and
  Bullhead City open the river run down from Kingman to Yuma, and Nogales and
  Sierra Vista put the Mexican border and Interstate 19 on the map below Tucson.

- **Eastern North Carolina comes onto the map.** Greenville, Jacksonville,
  New Bern, and Rocky Mount join the network, opening the US-17 coastal run
  from Wilmington up past Camp Lejeune, the US-264 haul from Raleigh, and a
  proper Interstate 95 stop at Rocky Mount between Fayetteville and Virginia.

- **US-60 climbs east from Phoenix through copper country.** Globe -- the old
  copper-mining town -- and Show Low, up in the White Mountains, join the map,
  opening the US-60 run past Apache Junction and Superior, down through the Salt
  River Canyon, and on to Interstate 40 at Holbrook.

- **The Interstate 10 corridor around Phoenix fills in.** Casa Grande -- the big
  distribution hub between Phoenix and Tucson -- and Buckeye, out on the western
  farm flats, join the map, breaking the I-10 runs into real stops past Eloy,
  Marana, and Quartzsite.

- **The Verde Valley opens along Interstate 17.** Camp Verde -- the I-17/AZ-260
  junction -- plus Cottonwood and red-rock Sedona join the map, splitting the
  Phoenix-to-Flagstaff run through the valley, with AZ-260 tying east to Payson.

- **The Beeline Highway and Route 66 open central Arizona.** Payson -- the
  junction town below the Mogollon Rim -- plus Winslow and Holbrook join the map:
  the AZ-87 Beeline climb from Phoenix to Payson, the AZ-260 run east to Winslow,
  and Interstate 40 past Holbrook to Gallup.

- **Northern Wisconsin fills in, Wausau up to Duluth.** Chippewa Falls and Rice
  Lake join the map, carrying WI-29 and US-53 north from Green Bay country up
  through Superior to the head of Lake Superior at Duluth.

- **US-89 climbs to Page and Lake Powell.** Page joins the map, opening the run
  north from Flagstaff across the Navajo Nation, past Cameron, to the Glen Canyon
  and Lake Powell country.

- **The Redwood Highway opens, US-101 north to Eureka.** Willits and Fortuna join
  the map, completing the North Coast run from Ukiah up through the redwoods --
  past Garberville and down the Eel River canyon -- to Eureka on Humboldt Bay.

- **The eastern Sierra opens along US-395, Reno to the Antelope Valley.** Carson
  City, Mammoth Lakes, Bishop, Lone Pine, and Mojave join the map, opening the
  long run down the east side of the Sierra Nevada -- over Conway Summit and the
  Sherwin Grade, through the Owens Valley beneath Mount Whitney, down to Mojave
  and Lancaster.

- **Interstate 90's Silver Valley opens across the Idaho panhandle.** Kellogg --
  heart of the old silver-mining country -- and Superior, Montana join the map,
  breaking out the I-90 run from Coeur d'Alene over Lookout Pass into Missoula,
  past historic Wallace.

- **Southwest Colorado connects to the Front Range over Wolf Creek Pass.** Pagosa
  Springs, Alamosa, and Walsenburg join the map, opening the US-160 run from
  Durango across Wolf Creek and La Veta passes down to Pueblo and Interstate 25 --
  Wolf Creek being the pass of runaway-truck fame, a fourteen-percent grade over
  the San Juans.

- **The Million Dollar Highway opens, Durango to Grand Junction.** Montrose and
  Delta join the map, breaking out the US-550 run over Red Mountain Pass -- past
  Silverton and Ouray, the "Switzerland of America" -- a real high-country
  crossing that climbs over four thousand feet with grades past eleven percent,
  the steepest, most dramatic road on the map.

- **Interstate 81 now reaches Richmond the primary way, over Afton Mountain.**
  Staunton joins the map at the Interstate 64 / Interstate 81 junction, so a load
  off I-81 can take I-64 east through the Blue Ridge -- past Waynesboro and
  Charlottesville into Richmond -- the main truck route east, not just the older
  US-460 line through Lynchburg.

- **The Tri-Cities open up along Interstate 81 and US-11W.** Marion and Abingdon
  in southwest Virginia, and Bristol and Kingsport in northeast Tennessee, join
  the map -- linking Wytheville down through the Tennessee valley to Morristown
  and Knoxville, so the whole I-81 Appalachian freight run is drivable.

- **A Black Hills freight run opens, Cheyenne to Rapid City.** Wheatland and Lusk
  out on the Wyoming high plains, and Hot Springs at the southern edge of the
  Black Hills, join the map -- linking Cheyenne up through Lusk and into Rapid
  City and Mount Rushmore country.

- **US-287 completes the Ports-to-Plains, all the way to Denver.** Boise City
  out in the Oklahoma panhandle, and Lamar and Limon on the Colorado high plains,
  join the map -- finishing the US-287 freight spine so a load can run from San
  Antonio up through the Panhandle to the Colorado Front Range on US highways.

- **US-287 climbs the Texas Panhandle north of Amarillo.** Dumas -- cattle and
  meatpacking country -- and Stratford join the map, carrying the Ports-to-Plains
  freight run up toward the Oklahoma line (Colorado and Denver still to come).

- **US-75 reaches north out of Tulsa into Kansas.** Bartlesville -- the old
  Phillips 66 oil town -- and Coffeyville join the map, carrying the US-75
  freight run up across the Oklahoma line into southeast Kansas.

- **US-69 connects southeastern Oklahoma up to Muskogee.** McAlester joins the
  map, completing the US-69 freight run east of US-75 -- from Durant and Atoka
  up through Eufaula and Checotah -- so the Texoma corridor reaches Muskogee and
  Fort Smith.

- **US-287 becomes drivable town by town across the Texas Panhandle.** Vernon,
  Childress, and Clarendon join the map, breaking the long Wichita Falls to
  Amarillo haul into real stops along the Ports-to-Plains freight route --
  through Quanah, Memphis, and Claude.

- **US-75 links Dallas and Tulsa through southern Oklahoma.** Durant, Atoka,
  Henryetta, and Okmulgee join the map, completing the north-south run from the
  Metroplex up across the Red River and through the Choctaw and Muscogee country
  to Tulsa -- a freight route that skips the long swing out to Interstate 44.

- **US-281 opens up central Texas, a north-south run beside Interstate 35.**
  Five towns join the map -- Marble Falls in the Highland Lakes, Lampasas,
  Stephenville, Mineral Wells, and Jacksboro -- linking San Antonio all the way
  up to Wichita Falls on US-281, the freight route that skips the Interstate 35
  crawl through Austin and the Metroplex.

- **Nine long runs now call out real towns instead of vague corridors.** On
  routes like San Antonio to Dallas, Denver to Salt Lake City, Phoenix to Los
  Angeles, Atlanta to Birmingham, and Chicago to Indianapolis, the game names
  the actual towns you pass -- New Braunfels and Waxahachie, Steamboat Springs
  and Vernal, Quartzsite, Baker and Yermo out in the desert -- in place of the
  old generic "corridor" markers.

- **Thirteen more cities finish the flavor map, coast to coast.** Socorro joins
  Interstate 25 down the Rio Grande; Modesto and Merced fill California's Highway 99
  between Stockton and Fresno; New London lands on Interstate 95 between Providence
  and New Haven; plus Clovis, Sherman, Paris, Lufkin, and Victoria across Texas and
  New Mexico, Prescott in the Arizona highlands, Logan and Moab in Utah, and
  Aberdeen up in the Dakotas.

- **Nine more Southern cities join the map.** Gadsden lands on Interstate 59
  between Birmingham and Chattanooga; Brunswick breaks up the Interstate 95 run from
  Jacksonville to Savannah; Natchitoches sits on Interstate 49 between Alexandria and
  Shreveport; plus Florence in the Alabama Shoals, Rome and Columbus, historic
  Natchez on the Mississippi bluffs, Panama City on the Florida panhandle, and Houma
  down in the Louisiana bayou.

- **The central California coast fills in along US-101.** San Luis Obispo and Santa
  Barbara join the map, completing the scenic coast run between the Bay Area and Los
  Angeles -- Salinas down through SLO and Santa Maria, over the coastal grades to
  Santa Barbara and Oxnard.

- **The Florida Gulf coast opens up, across Alligator Alley.** Fort Myers and Naples
  join the map, connecting Tampa down the Gulf coast, and the run from Naples to
  Miami takes Interstate 75's Alligator Alley straight across the Everglades -- no
  services for eighty miles, panther-crossing country, and a truck toll for the
  privilege.

- **Drive the Overseas Highway to Key West.** Key West joins the map at the very
  end of the road, reached from Miami down US-1 through the Florida Keys -- Key
  Largo, Islamorada, Marathon, Big Pine Key -- across the Seven Mile Bridge, all the
  way to the southernmost point in the continental United States.

- **You can now cross the Chesapeake Bay Bridge-Tunnel.** Cape Charles joins the
  map on Virginia's Eastern Shore, and the run north from Norfolk takes you out
  across the seventeen-mile Bridge-Tunnel -- diving into two tunnels beneath the
  shipping channels, past Sea Gull Island, out to where no land is visible in any
  direction, and up the Delmarva peninsula to Salisbury. It carries a hefty truck
  toll, because of course it does.

- **The northern Rockies and the Great Basin connect end to end.** Fifteen final
  runs: Missoula to Helena over MacDonald Pass, Provo to Green River over Soldier
  Summit, and Fort Collins up to Laramie -- real mountain grades -- plus Helena to
  Bozeman, Missoula to Kalispell, Great Falls to Havre along the Hi-Line, Casper to
  Gillette to Miles City, the North Dakota oil country (Dickinson, Williston,
  Glendive, Wolf Point), and the empty heart of Nevada and Utah (Twin Falls to
  Wells, West Wendover to Ely, Winnemucca to Fallon, Cedar City to Richfield).

- **The Pacific Northwest fills in over the Cascade passes.** Fourteen new runs:
  Seattle over Stevens Pass to Wenatchee, Tacoma over White Pass to Yakima, Salem
  over Santiam Pass to Bend -- real mountain grades with brake checks -- plus the
  Willamette Valley (Salem-Corvallis, Newport-Albany), the Columbia Basin
  (Wenatchee, Moses Lake, Tri-Cities, Yakima), the Oregon coast to Olympia, and the
  Idaho panhandle from Lewiston through Coeur d'Alene to Sandpoint.

- **California connects up, coast to desert.** Twelve new runs: San Francisco to
  Santa Rosa and San Jose to Salinas and Stockton; Salinas down the coast to Santa
  Maria; Fresno to Visalia; Oxnard to Valencia; Bakersfield over Tehachapi to
  Barstow; Lancaster to Barstow and Victorville; San Diego up to Riverside; and
  Riverside out to Indio and El Centro across the desert.

- **The Great Plains ladder and the Ozarks connect up.** Fourteen new runs lace
  the plains together -- Dodge City to Hays, Garden City and North Platte to Colby,
  Kearney to Hays, Lincoln to Junction City, Bismarck to Minot, Mitchell to
  Watertown, Sioux Falls to Mankato, Willmar to Watertown -- and down south,
  Columbia to Rolla, Kansas City to Springfield, and three roads into Harrison,
  Arkansas from Springfield, Conway, and Bentonville through the Ozark hills.

- **Twelve more cities open up the western plains and the Rockies.** Lawrence,
  Kansas joins the Interstate 70 run from Topeka to Kansas City; Ardmore breaks up
  Oklahoma City to Dallas over the Arbuckle Mountains; Rawlins lands on Interstate
  80 across Wyoming; Alexandria anchors the middle of Interstate 49 in Louisiana;
  and the long-empty corners fill in -- Roswell and Carlsbad in the New Mexico oil
  country, Farmington and Durango at the Four Corners over the Million Dollar
  Highway, plus Muskogee, Liberal, Scottsbluff, and Pierre.

- **Texas and the southern plains connect up with thirteen new runs.** The
  Interstate 49 line finishes across Arkansas from Fort Smith to Texarkana; Tulsa
  reaches Fayetteville, Enid, and Wichita; Waco runs to Tyler and on to Texarkana;
  Lake Charles crosses into Orange; College Station to Temple; Austin up into the
  Hill Country to Kerrville; and out west, San Angelo connects to Junction, Del Rio,
  and Fort Stockton, with Odessa reaching Fort Stockton across the oil patch.

- **Twelve more cities fill in the eastern and heartland map.** Cumberland,
  Maryland lands on the Interstate 68 climb over the Alleghenies; Saint Joseph joins
  the Interstate 29 run from Kansas City to Omaha; Mansfield breaks up Columbus to
  Cleveland; Youngstown sits between Akron and Pittsburgh; plus Staunton, Paducah,
  Owensboro, Parkersburg, Mount Vernon, Cape Girardeau, Waterloo, and Daytona Beach
  -- each connecting to its neighbors on real highways through towns like Paw Paw,
  Romney, and Appalachian coal country.

- **The Midwest lattice comes together with nineteen new runs.** Cedar Rapids to
  Iowa City; Peoria to Springfield, Decatur, and on to Bloomington and St. Louis;
  Champaign to Lafayette; and across Michigan and the crossroads, Detroit to Ann
  Arbor, Flint, and Toledo; Toledo to Columbus; Fort Wayne to Elkhart, Lansing, and
  Gary; Lansing and Kalamazoo; Milwaukee to Rockford; Indianapolis to South Bend;
  Grand Rapids to Saginaw; and Muskegon up to Traverse City along Lake Michigan.

- **The Northeast fills in from Maine to the Chesapeake.** Fourteen new short-haul
  runs stitch the dense Northeast together: Boston to Manchester, Providence to
  Worcester, Hartford, and New Haven; Philadelphia to Allentown and on to Trenton;
  Baltimore and Washington across the Chesapeake Bay Bridge to Dover and Salisbury;
  Harrisburg to Wilmington; Washington and Pittsburgh to Carlisle; Binghamton to
  Utica; and up through the Green and White Mountains, Albany and Portland, Maine
  to Montpelier.

- **Lynchburg and Longview become real hubs.** Lynchburg, Virginia now anchors
  US-460 between Roanoke and Richmond -- past Bedford, Appomattox, and Midlothian --
  and reaches Charlottesville up US-29. Longview, Texas takes its place on
  Interstate 20 between Tyler and Shreveport, past Marshall, and runs up US-59 to
  Texarkana.

- **Seven cities fill in long blank stretches of Interstate.** Wytheville breaks up
  the Interstate 81 run through the Virginia mountains; Bloomington splits the
  Interstate 69 haul to Evansville; Lima lands on Interstate 75 between Toledo and
  Dayton; Ocala joins the Jacksonville-to-Tampa run; Dubuque anchors the Mississippi
  River crossing on US-20; and Terre Haute and Effingham break the long Indianapolis-
  to-St. Louis drive on Interstate 70 into real stops. Each was a place you drove
  past for a hundred miles with nowhere to stop -- now they're real cities to
  pick up and deliver in.

- **The Carolinas and Virginia knit together with thirteen new runs.** Charlotte
  reaches Winston-Salem and Lumberton; Wilmington connects to Lumberton; Greensboro
  drops to Fayetteville; Charleston runs up to Florence; Asheville crosses the Blue
  Ridge to Spartanburg and Greenville; Roanoke links to Winston-Salem; Raleigh and
  Norfolk both reach Petersburg; and out of Washington, new roads run to Winchester,
  Hagerstown, and Charlottesville through Leesburg, Warrenton, and Frederick.

- **The Kentucky parkways and the Appalachian coalfields open up.** Thirteen new
  runs through some of the most storied hauling country in the East: Pound Gap
  from Johnson City to Pikeville, Corridor G from Charleston, the Cumberland Gap
  on US-25E, the Mountain Parkway to Hazard, Interstate 68 over the Alleghenies to
  Hagerstown, and the New River Gorge road to Beckley -- real mountain grades with
  brake checks, plus the Bluegrass, Western Kentucky, and Cumberland parkways
  through Bardstown, Somerset, and Middlesboro.

- **Georgia fills in from the mountains to the Florida line.** Athens now connects
  to Macon, Augusta, and Greenville, South Carolina; Macon reaches Columbus;
  LaGrange drops to Columbus on Interstate 185; and across the south, Albany links
  to Cordele, Valdosta, and Tallahassee while Valdosta reaches Tallahassee and
  Dothan -- ten new runs through antebellum Madison, Uncle Remus's Eatonton,
  Moultrie, and Cairo.

- **The Deep South knits together with eleven more connections.** Birmingham runs
  down to Opelika and on to Columbus, Georgia; Columbus drops to Dothan past Lake
  Eufaula; Montgomery reaches Meridian on US-80 through Selma; Huntsville joins
  Chattanooga along the Tennessee River past Scottsboro; Mobile connects to
  Hattiesburg, Baton Rouge to Gulfport, and Crestview up to Dothan. In the west,
  Shreveport now reaches Texarkana on Interstate 49, and Little Rock and Texarkana
  both connect down to El Dorado through the south Arkansas timber country.

- **Two Tennessee cities join the Interstate 40 run across the state.** Jackson
  now breaks up the long Memphis-to-Nashville haul, and Cookeville splits the
  Nashville-to-Knoxville climb over the Cumberland Plateau -- so driving clear
  across Tennessee now stops in real towns the whole way (Jackson, Nashville,
  Cookeville) with Buck Snort and Parker Crossroads still along the road.

- **Nine famous Interstate stretches open up at once.** The New York Thruway from
  the city to Albany up the Hudson Valley; Interstate 5 from Sacramento to Redding;
  the Cajon Pass climb from Riverside to Victorville -- a real mountain grade;
  Interstate 75 from Toledo to Dayton past Neil Armstrong's hometown of Wapakoneta;
  Kansas City to Joplin past Harry Truman's birthplace; plus Chicago to Champaign,
  Indianapolis to Evansville, Colorado Springs to Pueblo, and Tallahassee to Lake
  City across the quiet Big Bend.
- **Optional Profile sharing stays quiet during driving.** With Profile sharing on,
  Freight Fate can queue automatic fictional road-journal posts,
  achievements, and an allowlisted last-saved career snapshot for the public
  driver profile. Offline posting retries in the background and never adds a
  spoken interruption while driving.

- **The Deep South fills in with seven new connections.** Birmingham now runs to
  Chattanooga on Interstate 59; Mobile, Meridian, and Tupelo link up the length of
  US-45; Jackson and Gulfport both reach Hattiesburg on US-49; Columbia connects to
  Spartanburg on Interstate 26; and Austin joins Temple straight up Interstate 35.
  Whole stretches of Alabama, Mississippi, and the Carolinas that could only be
  reached the long way around are now direct.

- **Three more western Interstate gaps close up.** Twin Falls now connects to
  Ogden on Interstate 84, Idaho Falls to Pocatello on Interstate 15 past the Potato
  Capital of Blackfoot, and Casper climbs to Buffalo on Interstate 25 through the
  Powder River country -- filling in the Mountain West so the long-haul routes
  through Idaho, Utah, and Wyoming connect city to city.

- **Interstate 80 across Nebraska is now continuous.** The one missing gap,
  Kearney to North Platte through Cozad and Gothenburg, is filled -- so the great
  transcontinental Interstate 80 run across the Platte River valley connects city
  by city, right past the hundredth-meridian marker.

- **Dallas now connects to the Texas Panhandle up US-287.** Two new runs -- Dallas
  to Wichita Falls, then on to Amarillo through Decatur, Bowie, Vernon, Childress,
  and Memphis -- open the busy Highway 287 truck route across the plains, crossing
  the Red River, and tie Dallas to Amarillo (and onward to Albuquerque).

- **The Interstate 20 run from Birmingham to Tuscaloosa is now drivable.** This
  short but heavily-trucked segment past the Mercedes-Benz plant had no route of
  its own; adding it means the whole Interstate 20 corridor -- Atlanta, Birmingham,
  Tuscaloosa, Meridian, Jackson, Vicksburg, Monroe, Shreveport, Dallas -- can now
  be driven city by city, stopping in every town along the way.

- **Temple, Texas completes the Interstate 35 spine through Central Texas.** The
  new city fills the gap between Killeen and Waco, so the busy run up the middle of
  Texas now stops at every real city along the way -- through Belton and Troy --
  instead of skipping the heart of the corridor.

- **Dothan, Alabama's "Peanut Capital," ties three states together.** The new
  wiregrass city connects Montgomery, Tallahassee, and Albany by real US-highway
  runs through the peanut country of southeast Alabama, the Florida Panhandle, and
  southwest Georgia -- stopping at towns like Troy, Ozark, Blakely, and Cottondale
  and crossing the Chattahoochee and Apalachicola rivers.

- **Stuttgart, the rice and duck capital, anchors Arkansas's farm country.** The
  new city sits in the Grand Prairie rice belt, reached from Little Rock through
  England and looping down to Pine Bluff, crossing the Arkansas River -- flat
  farm-road driving through real Delta towns.

- **South Arkansas's timber and oil country joins the map, connecting into
  Louisiana.** Two cities arrive -- Pine Bluff and El Dorado -- and a new run drops
  south from Little Rock through Pine Bluff and El Dorado to Monroe, Louisiana,
  stopping at real towns along the way: Redfield, Warren, Hermitage, Junction City
  on the state line, Bernice, and Ruston. It opens the first road link between the
  Arkansas and Louisiana networks.

- **The Little Rock to Dallas run now stops at real towns.** Texarkana joins the
  map, right on the Arkansas-Texas line, and the long Interstate 30 haul breaks
  into a real chain of stops -- Benton, Arkadelphia, and Hope in Arkansas, then
  New Boston, Mount Pleasant, Sulphur Springs, and Greenville in Texas -- with
  truck stops, rest areas, and the Red River crossing along the way.

- **The drivable map crosses one hundred thousand miles.** This drop adds about
  twenty-seven thousand four hundred miles of new road and ninety-five new cities,
  bringing the network past one hundred thousand miles you can actually drive --
  126,238 miles across 470 cities and 1,039 routes.

- **Exits now come straight from real-world maps -- with the correct exit names
  and numbers.** On the Interstates, your stops and your destination exit are
  announced with their actual exit number and name and the places they point to --
  "Exit 33, Yemassee," "toward Beaufort and Port Royal," "Durham" -- taken directly
  from real map data, so you always know the right exit to take. This now covers
  the whole Interstate network.

- **Routes now carry the real posted speed limits.** Instead of estimating a
  limit from the road type, most legs now use the actual posted speed limits from
  map data (interstates, US highways, and more), so your truck runs the real
  limit on the road it is driving. Rural roads without published limits still fall
  back to a sensible estimate.

- **Interstate 10 across the Florida Panhandle now stops at real towns.** Two
  cities join the map: Pensacola and Crestview. The long Tallahassee-to-Mobile run
  breaks into stops through Marianna, DeFuniak Springs, and Spanish Fort, with
  truck stops and rest areas along the way.

- **Northern Arkansas's Ozark truck routes join the map.** Harrison and Mountain
  Home connect Northwest Arkansas across the winding US-412 and US-62 to Jonesboro
  -- the real curvy mountain roads a lot of trucks take, with genuine Ozark grades
  and turns through Springdale, Huntsville, Yellville, and beyond.

- **Arkansas opens up -- Walmart alley and the Delta.** Three new cities join the
  map: Fayetteville and Bentonville (Walmart's home) in the northwest, and
  Jonesboro in the northeast. Interstate 49 now climbs the real Boston Mountains
  from Fort Smith up through Fayetteville and Bentonville toward Joplin, and
  Jonesboro reaches Memphis and Little Rock across the rice-country Delta. You will
  pass Springdale, Rogers, Alma, West Memphis, Brinkley, and more.

- **The Indiana Toll Road and southwest Ohio fill in.** Elkhart, Indiana -- the
  RV manufacturing capital -- joins the map on Interstate 80/90, linking Toledo
  across to South Bend, and Dayton and Cincinnati are now directly connected on
  Interstate 75. You will pass towns like Swanton, Fremont, Monroe, and Sharonville.

- **Mississippi opens up: Tupelo, Hattiesburg, and Grenada join the map.** Three
  new cities knit together the state's Interstates -- Interstate 22 from Birmingham
  through Tupelo to Memphis, Interstate 59 down through Hattiesburg to New Orleans,
  and a new Interstate 55 run from Memphis through Grenada to Jackson. You will
  pass and hear Jasper, New Albany, Holly Springs, Laurel, Picayune, and more,
  with truck stops and real exits along the way.

- **Interstate 75 between Chattanooga and Atlanta now stops at real towns.**
  Two Georgia cities join the map: Dalton, the carpet capital, and Cartersville.
  The run breaks into stops through Ringgold, Calhoun, and Marietta instead of one
  long leg, with truck stops to fuel and rest at. Truck-stop names across the map
  also read more cleanly now (no more bare "T A" or leftover store numbers).

- **Southwest Georgia joins the map: Columbus and Albany.** Columbus, Georgia --
  the state's third-largest city, next to Fort Benning -- and Albany open up the
  wiregrass region, linking west to Montgomery, Alabama and east to the
  Interstate 75 towns at Tifton. You will pass and hear Tuskegee, Cusseta,
  Dawson, and Sylvester along the way.

- **Interstate 85 now runs unbroken from Atlanta down to Montgomery, Alabama.**
  Two more cities join the map: Opelika, Alabama, next to Auburn, and LaGrange,
  Georgia. The Atlanta-to-Montgomery run now stops city to city -- through
  Newnan, Auburn, and Valley -- instead of as one long leg, with truck stops and
  a rest area to break at.

- **Interstate 75 through South Georgia is now a chain of towns, not one long
  haul.** Four cities join the map: Lake City, Florida, and Valdosta, Tifton,
  and Cordele, Georgia. The run from Jacksonville up to Macon and Atlanta now
  stops city to city instead of as a single unbroken three-hundred-mile leg, and
  you will pass and hear the towns between -- Jennings, Adel, Ashburn, Perry --
  with truck stops and rest areas to break at.

- **Interstate 85 now runs unbroken through the Carolina Piedmont into Atlanta.**
  Two more cities join the map: Durham, North Carolina, in the Research Triangle,
  and Spartanburg, South Carolina, on the busy Eighty-Five freight run. The drive
  from Petersburg down through Durham, Greensboro, Charlotte, and Greenville into
  Atlanta finally connects city to city on the real road, and you will pass and
  hear the towns along it -- South Hill and Henderson in the north, Gastonia and
  Gaffney in the Carolinas -- with truck stops to fuel and rest at.

- **The Interstate 95 coast now connects, from Richmond down to Savannah.**
  Three new cities join the map: Florence and Lumberton along the Carolinas'
  stretch of Ninety-Five, and Petersburg, Virginia, where Ninety-Five meets
  Interstate Eighty-Five. That fills a real gap -- the East Coast's busiest
  freight run used to force a detour inland, and now you can drive it city to
  city on the actual road. Along the way you will pass and hear real towns:
  Walterboro, Saint George, and Dillon in South Carolina, Roanoke Rapids and
  Emporia in Virginia, with truck stops and a welcome center to fuel and rest
  at.

- **The biggest map update yet -- 100 new cities to pick up and deliver in.** A
  city is a place a load can start or end, and the map grew from 249 to 349 of
  them, filling in dead zones that used to have nothing drivable for hundreds of
  miles: the mountain West, the northern plains, the Nevada Great Basin, the
  Oregon and California coast, and Appalachia. Whole corridors that simply were
  not there before now connect city to city on the real roads -- Interstate 70
  over the Colorado Rockies, the US-2 Hi-Line across the northern tier, Interstate
  80 across Nevada, and Interstate 75 through the Kentucky mountains among them. Be careful, though -- there are still some challenging
  routes where you had better watch your fuel and get it when you can. Thanks
  to nromey.

- **Every run now names the real towns and country you pass.** Those are
  checkpoints -- the actual places along a route, spoken as you reach them -- and
  the map went from about 550 of them to over 2,500. Instead of empty miles, a
  haul now names the towns you pass and the state lines along the way, all from
  real geography, and real elevation data means the grades are felt and not
  smoothed flat. Thanks to nromey.

- **Over 1,700 truck stops are now named along your routes.** Real travel centers, truck
  stops, and rest areas -- Love's, Pilot, Flying J, TA, Petro, and independents
  -- each pinned to its real location, so every route now has at least one place
  to fuel or park, and even the emptiest rural stretches point you to a real
  diesel pump you can pull a rig into. For now these are just named on the map;
  making them do something -- rest, showers, repairs, and buffs -- comes in a
  later update. Thanks to nromey.

- **The map keeps filling in -- twenty more cities across seven new corridors.**
  Since the big update above, the network grew city by city: Interstate 80 across
  western Nebraska (Kearney, Lexington, Ogallala, and Sidney), Interstate 70 over
  the Kansas high plains into Colorado (Hays, Colby, Junction City, and
  Burlington), Interstate 10 through the West Texas desert (Fort Stockton, Ozona,
  and Junction), Interstate 25 over Raton Pass into New Mexico (Raton and
  Trinidad), Interstate 5 over the Siskiyou Mountains (Mount Shasta and Yreka),
  Interstate 29 up the Dakota plains (Watertown), and the full Willamette Valley
  run from Portland down to Eugene -- Woodburn and Albany on Interstate 5, plus a
  wine-country alternate through Newberg and McMinnville. Each new city is a real
  place to pick up and deliver, wired to its neighbors on truck-routed roads with
  real named stops to fuel and park along the way, and grades that rise and fall
  with the real terrain.

- **Nevada's Great Basin opens up -- six new cities on three high-desert
  corridors.** The empty interior between the interstates fills in: US-93 up the
  eastern Great Basin from Las Vegas through Alamo and Ely to Wells; US-50 -- "the
  Loneliest Road in America" -- across the middle through Eureka, Austin, and
  Fallon; and US-6 tying Ely to Tonopah. These are long, quiet, climbing hauls
  over real mountain grades (the run to Wells tops seven percent over Pequop
  Summit), and every leg points you to a real diesel pump so you never run dry on
  the lonely stretches. Ely, Fallon, and Wells are new places to pick up and
  deliver -- and Wells now splits the old Elko run, so Interstate 80 freight
  passes through the real town instead of leaping it.

- **Some hauls now offer more than one way to drive them.** Where two real truck
  routes reach the same place, the map keeps both, so a run can offer a choice --
  a faster interstate or a shorter back road -- instead of a single fixed path.
  Is it winter, and you'd rather take a southern route than a mountainous
  northern one? We've got you covered. Thanks to nromey.

- **See who else is hauling right now with the new drivers board.** A new
  Drivers online item in the main menu reads the live board from orinks.net:
  each driver's name, what they are doing, their route and cargo, and how
  fresh the report is. If you want to appear there yourself, set up sharing
  under Settings, Online. Drivers are Orinks accounts now: the game opens
  the orinks.net setup page where you sign in, pick your driver name and
  whether the public board lists you at all, and copy a Driver ID and a
  one-time posting token; back in the game you paste each from the
  clipboard and choose Connect and save. Nothing is ever shared before
  that, the game speaks exactly what gets shared, and only broad in-game
  activity goes out, like "Driving: Chicago to Dallas, steel coils", never
  your save files, real name, or location. You leave the board within
  minutes of going off duty or turning sharing off.

- **Your careers can now back up to the cloud.** Turn on Back up saves to
  your Orinks account under Settings, Online, and after each game save your
  career quietly uploads to your own orinks.net account -- so a dead hard
  drive no longer means a dead career, and you can pick up the same driver
  on another computer. It uses the same one-time sign-in as the drivers
  board, nothing extra to set up, and backups are private to your account:
  they never appear on the drivers board or anywhere public. The new
  Restore a cloud backup menu reads your backups aloud, newest first, and
  brings one onto this computer -- keeping the save it replaces beside it
  as a fallback. Played the same career on two computers? The game notices
  and asks which copy should win instead of silently overwriting either.
  Cloud backup is off until you turn it on.

- **The map now has real time zones, and your clock changes as you cross
  them.** Drive west out of Tennessee on I-40 and you will hear "Crossing
  into Central Time. It is now 2:15 PM." With terse speech on, it is just
  "Central Time." Every spoken clock -- rest stops, sleep, city arrivals, the driving
  status screens -- now reads the local time where your truck is, and the
  clock readouts name the zone, like "2:15 PM Central Time". Delivery
  deadlines are also quoted the way a real receiver would say them: in the
  destination's local time, like "deliver by 6 PM Central Time tomorrow", on
  the dispatch job details and in the driving deadline readouts. Hours of
  service, deadlines, and pay are untouched; only what the wall clock says
  changes. Boundaries follow the real lines, including split states like
  Tennessee, Kentucky, Indiana, the Florida panhandle, and far west Texas.

### Changed

- **Pausing now takes you off the live drivers board.** The pause menu used to
  keep you listed as "Paused"; now it counts as going off duty, so the public
  board only shows drivers who are actively hauling. A quick pause and resume
  will not bounce you off the board, and Discord presence still shows
  "Paused" to your friends while the menu is open.

- **Dispatches and route planning now always name the state with each
  city.** A job reads as "to McCall, Idaho" even when no other McCall
  exists, so an unfamiliar town still tells you roughly where you are
  headed. And each route option now says which cities it passes through
  right in the option itself -- "through Boise, Idaho, then McCall" --
  instead of only in the F1 help, so you can weigh routes the same way
  the end-of-trip summary describes them. Thanks to a player suggestion.

- **Automatic direction changes can now be simple or deliberate.** Simple is the
  casual default: keep holding the control after the truck stops to change
  between forward and reverse. Deliberate keeps the safer two-step behavior from
  the previous snapshot: stop, release the control, then press it again. Choose
  the style you prefer under Settings, Gameplay. Manual shifting is unchanged.

- **Online settings are now gathered in one place.** The Discord presence
  toggle moved from Settings, Gameplay to Settings, Online, alongside the
  drivers board and the new cloud backup options. And before you have set
  up your Orinks sign-in, the first Online item now says "Driver profile:
  not set up" -- setting it up is one step that unlocks both the drivers
  board and cloud backup.

- **The horn sounds like a real horn held down.** Instead of restarting the
  same short honk over and over, holding the horn now sustains one steady blast
  for as long as you press it, and when you let go the horn rings out and fades
  the way a real one does rather than cutting off abruptly. Pressing the horn
  again while it is still sounding no longer layers a second horn on top.

- **Abandoning a job now asks you to confirm.** Choosing Abandon job from the
  pause menu opens a Yes or No prompt that starts on No, so you have to arrow
  down to Yes to actually give up the load and pay the penalty. Choosing No
  takes you straight back to the pause menu with the job intact.
- **Cities that share a name now always say their state.** With two Jacksons,
  two Portlands, and three Springfields on the map, dispatch offers, route
  planning, GPS announcements, and delivery summaries now say "Jackson,
  Mississippi" or "Jackson, Michigan" wherever the bare name would be
  ambiguous. Cities with a unique name keep their short spoken form, and a few
  places that used to stutter their state twice, like "toward Jackson,
  Michigan, Michigan", now say it once. Existing careers and saved trips carry
  over unchanged.

- **Job details always tell you the state.** Not sure where Baton Rouge is?
  Open a job's detail view from the dispatch board and the origin and
  destination lines now always include the state, like "in Baton Rouge,
  Louisiana", even for cities with a unique name. Board offers stay short.

### Added

- **The upper Midwest and Great Lakes fill in with twenty-nine new cities
  across five states.** Illinois gains Springfield, Bloomington, Champaign,
  and Decatur. Michigan gains Flint, Saginaw, Kalamazoo, Port Huron, Muskegon,
  Jackson, and Traverse City, plus the Upper Peninsula iron and shipping towns
  of Marquette, Escanaba, Sault Ste. Marie, Iron Mountain, and Houghton.
  Wisconsin gains Kenosha, Eau Claire, Wausau, and La Crosse. Minnesota gains
  St. Cloud, Rochester, Mankato, Winona, Willmar, Albert Lea, and Hibbing on
  the Iron Range. Indiana gains Gary and Lafayette. Every city comes with
  real, named freight facilities -- haul taconite pellets from the Hibbing
  mine, steel out of Gary Works, new Subarus from Lafayette, and turkeys from
  Willmar -- with truck-routed corridors, real truck stops, and labeled
  highway exits along the way. Long slogs like Minneapolis to Fargo and
  Chicago to Indianapolis now have proper stops in between, and Fort Wayne,
  South Bend, and Evansville trade their generic docks for real ones like
  the GM pickup plant and the Mead Johnson formula works.

- **The Great Lakes split into three regions that each feel like
  themselves.** The Upper Midwest covers Minnesota, Wisconsin, and Michigan's
  Upper Peninsula; the Great Lakes keeps the lower-lakes industrial belt from
  Chicago through Detroit to Buffalo; and the new Corn Belt takes interior
  Illinois, Indiana, and southern Ohio. Each has its own weather, fuel
  prices, freight market flavor, and road hazards, so a winter run out of
  Duluth no longer sounds like a summer haul into Cincinnati.

### Fixed

- **A few routes now name the right highway.** On the runs from Denver to Salt
  Lake City, Santa Rosa to Stockton, and Clarksville to Huntsville, the game
  announced a highway the route never actually takes; it now names the road you
  are really driving.
- **The truck now warns you while the engine is over-revving, instead of
  surprising you with damage at delivery.** Holding the engine at redline --
  easiest to do by backing up fast for a long stretch -- quietly ground the
  truck down, and the first you heard of it was a big damage number on the
  end screen. Now a warning sounds and the game tells you the engine is
  taking damage and the current total, repeating while it goes on, so you
  can ease off and slow down before the repair bill grows. Thanks to a
  player report.

- **Online setup now tells you when orinks.net refuses your pasted
  credentials, instead of blaming your connection.** If the server answered
  but did not accept the Driver ID and token, the game said "could not reach
  orinks.net, check your connection," sending you off to troubleshoot a
  network that was fine. It now says the credentials were not accepted and
  asks you to re-copy them from the setup page. The token paste item also
  checks that the pasted text looks like a real driver token -- they always
  start with the letters F F D and an underscore -- and says so when it does
  not, catching a wrong copy before anything is sent. Thanks to a player
  report.

- **Music keeps playing while the game is paused.** If a music track ended
  while you sat on the pause menu -- or in settings, help, or any other menu
  over a drive -- the music went silent until you resumed driving. The next
  track now starts on its own, so a long pause no longer means a quiet cab.

- **Pasting your Driver ID and token now works on Mac.** Setting up the
  online drivers board no longer crashes the game, or silently does
  nothing in the downloadable app, when you paste your Driver ID or
  driver token from the clipboard on a Mac. Thanks to a player report.

- **No more "brake now" ambushes on the way to a pickup.** The short
  facility access road you deadhead down to reach a shipper no longer
  springs road hazards or emergency-braking events; those belong on the
  open road, not on a two-minute crawl at yard speeds. Thanks to a player
  report.

- **Reconnecting a controller no longer crashes the game or leaves it
  half-working.** Unplugging a pad -- or having it change to another device and
  come back over Bluetooth -- could crash the game outright, or bring the
  controller back with the triggers and bumpers dead so you could steer but not
  brake. The game now recovers from the hot-plug instead of crashing, and
  fully re-acquires the controller when it returns -- even when the system hands
  it back under a new identity -- so braking, throttle, and the bumpers work
  again right away.

- **Controller toggle actions no longer fire twice.** On some controllers --
  notably the Xbox Elite -- setting or releasing the parking brake, or starting
  or shutting down the engine, could trigger twice from a single press, so the
  action immediately undid itself. Each button press now counts once, even when
  the controller reports itself to the system more than once.

- **Construction zones no longer stack or chain together.** Slow zones were
  placed independently, so a construction zone could land inside another
  one, or two could start back to back with no open road between. Zones now
  keep at least eight miles apart, so "end of construction" always means
  open road ahead. Thanks to a player report.

- **Metric mode now covers the whole weather report.** With units set to
  kilometers, pressing V mid-drive still read the temperature in Fahrenheit
  and low visibility in miles. Temperatures now speak in Celsius and
  visibility in kilometers everywhere weather is described: the V report,
  weather-change announcements while driving, trip resume summaries, and
  the terminal weather check. Thanks to a player report.

- **The engine sound now stops when you shut down to sleep.** Going to sleep
  at a rest stop, motel, or on the shoulder shuts the engine down, but the
  engine sound kept playing over the night and after you woke, as if the
  truck were still idling with the engine off. The shutdown is now heard
  when it happens, and the idle goes quiet with it. Thanks to Darren Duff
  for the report.

- **Using the accelerator to brake in reverse no longer speeds you up.** In an
  automatic, pressing the accelerator while rolling backward is meant to slow
  and stop the truck, but at higher reverse speeds it could push you faster
  instead. It now brakes reliably all the way to a stop.

- **Adaptive cruise no longer revs the engine when you press the clutch to
  shift.** With a manual gearbox, holding the clutch under cruise control used
  to send the engine screaming toward the redline. Now cruise eases off the
  moment the clutch goes in, the engine settles back toward idle, and the speed
  is picked back up smoothly once you let the clutch out.

- **The engine no longer re-cranks when you pick a trip back up.** Resuming a
  saved haul with the engine already running -- or coming back from a menu
  mid-drive -- used to replay the ignition sound as if you had just turned the
  key. Now the running engine simply fades back in, and the starter is heard
  only when you actually start the engine yourself. When you do start it, the
  crank now blends smoothly into the running engine instead of being drowned
  out the instant it catches.

- **Your truck no longer idles all night while you sleep.** Bedding down for
  the night -- at a rest stop, in the sleeper berth, in a cramped lot, or on
  the shoulder -- now shuts the engine down first, and you will hear "You
  shut down the engine" as you turn in. When you head back to the road,
  start the engine as usual. Thanks to Bartholomue.

- **Updating the game on Mac now works.** Downloading an update used to end
  with "the download failed" and nothing installed, leaving Mac players to
  fetch each new version by hand. The updater now understands the Mac app
  bundle: it swaps in the new app after the game closes and reopens it for
  you, just like on Windows and Linux. Your saves are untouched. Thanks to
  vlad-a-c.

- **Asking for job details on Back to terminal no longer crashes the game.**
  On the dispatch board, pressing F1 while on the Back to terminal entry used
  to crash; it now simply reads the entry back, like any other menu item.
  Thanks to ironcross32.

- **Resuming a trip no longer repeats a stop it already called out.** When you
  continued a saved run, the game could re-announce a truck stop or rest area
  just ahead that it had already told you about before you saved. It now
  remembers what it said and stays quiet. Thanks to nromey.

## 1.8.0 - 2026-07-05

### Added

- **Report a problem straight from the main menu.** A new Report a problem
  option, just above Quit, opens the Freight Fate bug report page on GitHub
  in your web browser and tells you where to find your game log: the file
  game.log in the logs folder next to the game. The game now also keeps the
  previous run's log as game.prev.log, so if the game crashes, the evidence
  survives restarting it to file the report. Crashes inside the game's audio
  and video engines, which used to vanish without a trace, are now written
  into the log as well.

- **Game controllers are now supported, alongside the keyboard.** Plug in an
  Xbox, PlayStation, or other compatible controller and drive by feel: the right
  and left triggers are the gas and brake, the left stick steers, the left bumper
  is the clutch, and the A and X buttons shift up and down. Menus map to the
  D-pad, the A button confirms, the B button goes back, and the Back button reads
  controller help. The first controller is picked up automatically, hot-plugging
  and unplugging are detected mid-game (unplugging pauses the drive), and spoken
  prompts name controller buttons when you are on a pad and keys when you are on
  the keyboard. Turn it off under Settings, Gameplay, Controller. The keyboard
  always stays active. Thanks to ironcross32.

- **Set the parking brake to let time pass while you wait.** Pressing your
  parking brake while stopped now means deliberate waiting: the clock runs at
  double your trip pacing -- weather blows through, daylight comes, and dock
  time passes without the game ever dropping to real time. Pressing it again
  to leave returns to normal pacing instantly. Only your own brake press arms
  the fast-forward; the brake the game sets for you at trip start or after a
  rest stop never does, so pre-trip setup stays cheap. Each pacing setting
  keeps its relative feel while waiting: relaxed 20 times, standard 40,
  fast 80.

- **The Pacific Northwest fills in with eight new cities.** Tacoma, Everett,
  Olympia, Bellingham, and Yakima in Washington and Medford, Roseburg, and
  Pendleton in Oregon join the map with truck-routed corridors, real named
  ports, mills, and freight facilities, and real truck stops along the way.
  The region finally has short local runs -- Seattle to Tacoma is a
  34-mile hop instead of nothing closer than Portland -- and the empty I-84
  corridor gets its first stop at Pendleton. Thanks to liamerven.

- **Appalachia, the Heartland, and the Southern Plains grow by eighteen
  cities.** Appalachia becomes a real Valley-and-Ridge region: Asheville,
  Johnson City, Beckley, Harrisonburg, Winchester, and Hagerstown line the
  I-81, I-77, and I-40 mountain corridors, Roanoke gains its rail yard and
  distribution work, and the western reaches of Virginia, North Carolina, and
  Maryland now count as Appalachian country. The Heartland adds Sioux City,
  Grand Island, North Platte, Columbia, Joplin, and Rolla along I-70, I-29,
  I-80, and I-44; the Southern Plains add Salina, Dodge City, Garden City,
  Enid, Lawton, and San Angelo with their grain, beef, and oilfield freight.
  Every new city carries real named facilities and every corridor has named
  truck stops. Thanks to liamerven.

### Fixed

- **Switching screen readers no longer leaves the game silent.** The game now
  notices within a few seconds when your screen reader closes or changes, for
  example going from NVDA to Narrator and back to NVDA, and reconnects its
  speech to whichever voice is running, telling you which one it picked.
  While Narrator is running, the game keeps its own Windows voice so that
  moving through menus still cuts speech off crisply; Narrator itself only
  carries the game's speech as a last resort when no other voice on the
  machine works. This also
  works if you start the game before your screen reader: speech simply
  begins once the screen reader is up. Your speech rate, voice, and separate
  event voice settings carry over to the reconnected voice automatically.

- **Release archives no longer ship the build machine's log.** The packaging
  smoke check writes a log inside the build folder; it is now stripped
  alongside saves before archiving, so a fresh download starts with an empty
  logs folder instead of a confusing leftover run.
- **Save migration now explains itself.** When the game folds an old save
  folder into the active one on first run, it writes what moved from where
  to the game log and leaves a small saves-moved.txt breadcrumb at the old
  location, so an unexpectedly familiar career is traceable instead of
  haunted.
- **Spoken help now teaches the W and Q gear keys everywhere.** The engine
  start walkthrough, the transmission setting, and the manual-transmission
  page of How to play still told manual drivers to shift with the number
  row; they now describe holding the clutch and pressing W to shift up and
  Q to shift down, matching how the truck actually shifts. The left and
  right arrows also now toggle the Haptics setting like every other
  gameplay setting row, instead of doing nothing there.
- **Getting up to highway speed no longer costs an hour of game time.** Truck
  physics runs in real time so shifting and braking stay playable, but the
  clock billed every real second at full trip pacing -- so the couple of real
  minutes a loaded rig needs to work through the gears cost most of a game
  hour, burning daylight, deadline, and duty clock. Clock compression now
  ramps with road speed: near real time while stopped or maneuvering, your
  full pacing setting once at cruise. Distance, fuel, fatigue, and the hours
  of service ledger all follow the same effective rate, so the simulation
  stays consistent -- acceleration now costs about five game minutes instead
  of forty-five.
- **The dispatch board no longer offers trivially short hauls.** Because each
  city stands for a whole freight area, a job to a neighbor under 25 miles was a
  pointless across-town hop; the board now skips those destinations and fills
  from real routes instead.
- **The dispatch hours warning now respects a fresh clock.** Sleeping off your
  hours before visiting the dispatch board no longer leaves every long haul
  flagged with "may not fit your duty clock." The warning compared your time
  until the next HOS limit against the route's full legal plan -- including the
  overnight sleeps every multi-day run needs anyway -- so it fired even right
  after a reset. It now only warns when hours already spent this shift would
  force an extra rest that fresh hours would avoid, and the board note says
  sleeping first will clear it.
- **Trucks into New York now take the George Washington Bridge, not the Holland
  Tunnel.** New York freight now routes to the Hunts Point market in the Bronx
  over the GWB on I-95 -- the Hudson crossing a full-height rig can legally use
  -- instead of the height-restricted Holland Tunnel that I-78 feeds into. Trips
  from New Jersey and Pennsylvania have realistic mileage and exit cues as a
  result.
- **Truck speed limits are now capped in Oregon and Idaho too.** Posted limits
  on those states' fastest roads are held to the legal truck maximum (65 in
  Oregon, 70 in Idaho), matching the existing handling for California and other
  truck-restricted states.
- **Control now stops speech in menus too, not just while driving.** Left or
  Right Control already silenced the driving event voice; it now also stops the
  current speech in every menu and in the how-to-play reader, so a long readout
  -- job details, cargo loading, a full help page -- can be cut short with the
  same key everywhere.
- **Dispatch, garage, and driving tools feel clearer.** F1 on a dispatch job now opens a
  reviewable job-detail view with line-by-line facts, long-haul pay has a stronger
  floor, drive-start speech is shorter in terse mode, the horn loops while held,
  truck and upgrade wording is clearer, and the garage can service tire wear and
  wash road grime.
- **Reverse now has its own backing cue.** Shifting into reverse with the engine
  running now starts a backing loop through the main audio backend, and automatic
  reverse selection still gets a spoken confirmation. Thanks to ashleygrobler04
  for the original reverse-loop PR.
- **Lane drift now cues direction before the rumble strip.** When lane drift is
  enabled, a short beep now plays from the side you drift toward, and a dedicated
  centered-lane chime confirms when you are back in the lane.
- **Hazard clears are easier to hear, and speech backs off faster.** Passing a
  road hazard now plays a short achievement-like confirmation sound, and urgent
  events plus driving warnings clear stale spoken messages so old alerts do not
  keep piling up. The brake-now hazard warning cue was also remade as a short,
  louder alert.
- **First-rig menu music refreshed.** The first-owned-truck menu bed now uses
  a cleaner, longer copy and plays for its full length before the menu rotation
  advances.
- **Driving realism polish.** Metric speed warnings,
  speeding strikes, trooper stops, cruise messages, and the speed-limit key now
  use the selected units consistently. Missed destination exits reroute you via
  a safe turnaround instead of telling you to reverse down the highway, and
  recovery no longer loops gate-speed tickets. Dispatch warns when your current
  hours are too short for a load, including when every listed job is risky.
  Bobtail repositioning now counts as off-duty personal conveyance, dispatch
  board facility names are less repetitive, impossible short delivery summaries
  are floored to a practical road time, and automatic shift audio no longer
  flares at full throttle during gear changes.
- **Engine brake and throttle no longer fight each other.** The engine brake now
  refuses to switch on while you are accelerating, and pressing the accelerator
  turns it back off so the truck can make power normally.
- **Destination exits keep the route status honest.** Taking a delivery exit now
  clears the remaining route miles before the dock menu opens, and the GPS no
  longer repeats the destination exit with a second generic interchange cue.
- **Real posted speed limits win near cities.** City approaches still use a
  slower fallback when the route has no posted speed-limit sample, but real
  baked `maxspeed` data is no longer capped just because the route is near a
  city.
- **Truck speed limits now respect state caps.** Baked route speed-limit data
  now applies lower truck maximums in states that cap commercial trucks below
  the general posted limit, and reversed routes read the correct limit profile.
- **Stops no longer announce speculative truck parking.** If a stop's parking
  is confirmed, that still gets spoken; otherwise speculative parking wording
  is dropped from route cues so the game just announces the stop.
- **Adaptive cruise starts slowing before big speed-limit drops.** When the
  posted limit ahead falls sharply, adaptive cruise now looks far enough ahead
  to begin braking before the lower-limit point instead of waiting until the
  truck is already in the slower stretch. Pressing Space while cruise is on now
  also includes the cruise set speed in the speed readout.
- **Adaptive cruise no longer gets you fined while braking for a lower limit.**
  When the posted limit drops sharply, cruise now gets a clean chance to slow
  the truck instead of letting the speeding timer fire while it is already
  braking down.
- **Route status explains road grade clearly.** Pressing R now reports the
  current grade as a percent and uphill, downhill, or level instead of saying
  the vague phrase "Grade level."
- **Delivery windows match the slower, real route model.** New dispatch
  deadlines now use the route's posted-limit profile, city approaches, facility
  gates, HOS breaks, sleep, and practical slack instead of a flat mileage
  average. Older active trips that were saved under the faster estimate get a
  one-time fair deadline floor when they resume, so a source update does not
  make an in-progress load suddenly late.
- **Metric weather readouts use metric safe speed.** Pressing V with metric
  units enabled now reports the weather safe speed in kilometers per hour.
- **No more "dot dot" at the end of menu items.** A menu or list item that was
  already a full sentence (like a settlement summary line) got a second period
  appended before its "N of M" position, which a screen reader voiced as "dot
  dot". The readout now adds a period only when the text does not already end
  in one.
- **You can always find somewhere to sleep.** A sleep option is now reachable
  at any time, so the hours-of-service clock can never strand you with nowhere
  legal to stop. Stopped on the open road with no route stop nearby, you can
  pull over and sleep on the shoulder (poor rest, possible parking ticket);
  the wording escalates when an HOS limit is closing in with no reachable stop.
  Any break/fuel stop you reach -- even one with no sleeper facility -- now
  offers an emergency sleep in the lot: a legal 10-hour reset with poor, cramped
  rest. The "no stop visible" warning also names the shoulder-sleep out, so it
  is a plan rather than a panic. (Proper sleeper stops still give the best,
  fully-rested 10-hour sleep.)
- **The automatic no longer gears up while you brake.** Braking from speed could
  trigger an upshift because the box only watched engine RPM; it now holds the
  gear for engine braking and downshifts cleanly as you slow to a stop.
- **"Air pressure ready" no longer repeats back to back.** The parking-brake
  release threshold sat exactly at the compressor cut-in pressure, so the ready
  state flickered every 100-125 psi cycle and re-announced. The cue now fires
  once, only while the parking brake is actually set (its whole purpose is
  "you can release it now"), and only re-arms after a genuine low-air depletion.
- **Snapshot players move to stable when it catches up.** On the preview
  snapshot channel, the game now offers the stable release whenever it is as
  new as -- or newer than -- the latest nightly, so once those changes ship in
  a stable build you converge back onto stable instead of being left on an
  equivalent nightly.
- **The low-air alarm now sounds on a cold start.** Starting the engine for
  the first time with the air tanks low used to stay silent; the warning now
  plays as soon as the engine is running with pressure below the threshold,
  so you know to wait for the compressor before releasing the brakes. Thanks
  to hannes16.
- **Erie and Evansville moved to their right regions.** Erie sits on the Lake
  Erie shore between Buffalo and Cleveland, so it is now Great Lakes country
  rather than Appalachia; Evansville, down on Indiana's Ohio River border, is
  now the Mid-South rather than the Great Lakes. Spoken region names, weather
  flavor, and regional hazards on runs through both cities now match the
  geography. Thanks to liamerven.

### Fixed
- **Exit warnings now arrive early enough to act on.** At highway speed on
  standard or fast pacing, the destination exit callout used to fire so close
  that by the time it finished speaking the ramp was gone. The warning
  distance now grows with your speed and pacing, so you always get roughly
  the same amount of real listening and braking time, and the exit can be
  armed as soon as you hear the callout.
- **Exit announcements no longer say the same name twice.** Messages like
  "missed exit 5B for exit 5B" and "Signaling for the exit for the warehouse,
  destination exit for the warehouse" now speak each exit and facility name
  exactly once. Distances also read naturally: "in 1 mile" instead of
  "in 1 miles".

### Changed
- **Career stats at the terminal is now a browsable list.** Instead of one
  long spoken paragraph, arrow through your level, reputation, deliveries,
  lifetime miles, and earnings one line at a time; Enter repeats a line. The
  screen also gains your rest status: whether you are fully rested or how
  tired you are, plus your hours of service at a glance.
- **Sleeping at the terminal no longer swallows 10 hours by accident.** If
  your hours of service are fresh and you are not tired, choosing Sleep 10
  hours now warns that sleeping would only move the clock forward, and asks
  you to press Enter again to sleep anyway. So an extra press on the sleep
  option can never quietly cost you a rested clock.
- **New installs now start at relaxed trip pacing.** Fresh installs default to
  the relaxed pace, which gives you the most real time to hear and react to
  spoken warnings like exits and hazards. Existing players keep whatever
  pacing they already chose, and standard and fast are still one setting away
  under Settings, Gameplay, Trip pacing.
- **All music now plays at the same volume.** Six tracks, including the main
  menu themes, Open Road, Night Haul, and Small Hours, were much louder than
  the rest of the soundtrack. They have been brought down to match, so the
  music volume slider now behaves the same no matter which track is playing,
  and the menu no longer greets you louder than the drive that follows.
- **Real-world weather now refreshes three times as often.** With the real
  weather source turned on, the game checks the live conditions for your
  destination every five minutes instead of every fifteen, so fog rolling in,
  a storm firing up, or skies clearing reach your drive much sooner. If your
  connection drops, the game holds the last known weather for the same half
  hour as before switching to simulated conditions.
- **Downloaded builds no longer expose the game's world data files.** The
  world now ships built into the game program itself, so there is no data
  folder to browse or accidentally edit next to the game. Nothing changes
  about how the game plays, and source checkouts keep their editable data
  files.
- **Downloaded builds now ship their sounds as a single packed file.** The
  browsable sounds folder is gone from the download; all sound effects and
  music travel in one pack file the game reads directly. Every sound plays
  exactly as before, the sound and music credits ship as a readable file
  next to the game, and source checkouts keep their editable sound files.
- **During a manual drive.** hold down the clutch (shift) then press W to shift up gears, and q to shift down gears .
- **Hours-of-service rules are more realistic.** Realistic mode now tracks the
  11-hour driving limit, 14-hour duty window, 30-minute break requirement,
  60/70-hour weekly limits, roadside inspections, and legal sleeper-berth split
  rest. Rest menus now make the choice explicit: short breaks, poor emergency
  sleep, full sleeper sleep, or sleeper split planning where the stop supports
  it.
- **Menus can read just the option, not its place.** A new Speech setting,
  "Menu position announcements," turns off the "N of 10" position spoken after
  each menu option, so menus read only the option itself. On by default.
- **In-game help and manual now cover the new systems.** The how-to-play pages,
  the F1 driving help, and the user manual were brought in line: the calendar
  and seasons, weather that bites (traction loss, drag, visibility), the
  always-available shoulder and lot sleep, cruise that declines low-speed local
  roads, and -- newly documented anywhere -- state-trooper speeding pull-overs
  (signal with X) and real changing posted limits.
- **The calendar reads as a real date, in more places.** The career clock now
  speaks an actual date that advances as time passes -- "March 21," then "April
  1," and so on (a new career starts March 21) -- instead of only a day number.
  It is announced on the C clock readout, the Tab status menu, and the on-screen
  status, not just at the terminal, with the season alongside it. With live
  weather on, the date and season follow the real-world calendar.
- **Weather you have to drive to, not just hear.** Three conditions that used to
  be flavor now bite. High wind and storms add real aerodynamic drag, so they
  cost top speed and fuel. Driving well over the conditions-safe speed on a
  slick road risks a traction-loss incident -- hydroplaning in rain, sliding on
  snow -- so the safe-speed readout finally has teeth. And low visibility (fog,
  heavy rain) shortens how much warning you get before a hazard, so you have to
  actually slow down to see and react in time.
- **Speed-limit changes now say why.** A changing posted limit is announced as
  "Speed limit reduced to X" or "raised to X" instead of a bare number, and an
  urban drop names the city ("reduced to 55 approaching Boston"), so a mid-drive
  change is no longer a mystery.
- **No cruise on low-speed local roads.** Adaptive cruise will not engage on a
  facility access road, gate, construction zone, or heavy-traffic stretch -- the
  low-speed local roads a real driver takes manually -- and says so if you try.
- **Relaxed mode now feels emptier on the road.** Relaxed hours-of-service mode
  already made random hazards and trooper patrols rarer; it now also thins
  ambient traffic and the odds of a random roadside log check, so a relaxed run
  centers on driver responsibility -- hours, fuel, fatigue -- with fewer
  interruptions. Fixed checkpoints (weigh stations) and construction-zone
  enforcement are unchanged: a real violation still catches you. Realistic mode
  is untouched.
- **Live weather now reports the real temperature.** With live weather on, the
  cab speaks the actual temperature from the nearest National Weather Service
  station instead of the modeled seasonal estimate, so the degrees match the
  conditions it is already pulling in. The seasonal climate model stays the
  fallback whenever live data is unavailable or a station omits its reading.
- **Dial your cruise speed with Plus and Minus.** Once adaptive cruise is set,
  Plus and Minus raise and lower the target by 5 -- the accelerate and coast
  buttons on a real truck -- so you can engage as soon as you are rolling and
  dial the speed up to where you want it instead of having to reach it manually
  first. The truck accelerates up to a higher target on its own, and the posted
  limit cap still applies, so a higher set speed never makes it speed.
- **Adaptive cruise now respects the posted limit.** Cruise eases off to hold a
  with-traffic pace (about 5 over the posted limit) instead of carrying your set
  speed straight through an urban drop or a lower-limit stretch -- so it keeps
  you moving naturally without driving you into speeding strikes, tickets, and
  trooper stops. It still follows slower traffic and widens its gap in bad
  weather, and a short cue says when it eases off for a lower limit (the
  "Speed limit X" sign cue still names the number).
- **The air-brake system has real sounds now.** When pressure builds, you hear
  an air-dryer purge as the compressor cuts out instead of a generic beep, and
  low-air and spring-brake warnings sound a proper low-air buzzer. The spoken
  cues are unchanged, so nothing is lost if you rely on them.
- **Speeding now costs you out loud, the moment it happens.** When a speeding
  strike is recorded, the cab calls out the running fine ("Speeding strike. The
  limit is 65. Speeding fines now total 160 dollars, due at delivery.") instead
  of the cost landing silently on your settlement. Judged against the corridor's
  real posted limit, with the usual ~10 mph leeway before a strike lands.
- **Posted speed limits can now come from real map data.** Where a corridor
  carries an OpenStreetMap `maxspeed` tag, the game uses that real posted limit
  instead of the highway/region approximation -- and falls back to the
  approximation only on stretches OSM has not tagged. Limits are baked at build
  time (truck-specific `maxspeed:hgv` preferred where present); the spoken
  limit-change cue still calls out posted-limit changes as you drive.
- **The lane-drift rumble is now directional.** When you wander toward a lane
  edge, the rumble strip plays from that side -- drift right and you hear it on
  the right -- so the ear it lands in tells you which way to steer back.
- **Safety announcements no longer get buried, and you get more warning.** Zone
  entries, construction and traffic warnings, and checkpoints now preempt
  ambient chatter (weather, tolls, state lines) on the event voice instead of
  queuing behind it -- so a "construction ahead" never arrives after you have
  already entered the zone. Zone warnings also lead by real time now, not a
  flat distance: the heads-up scales with your speed and pacing, so 70 mph at
  high time compression gets a usefully earlier callout instead of a couple of
  seconds.

### Added
- **Repeat the market watch on the dispatch board.** The board speaks which
  freight is tight or loose when you open it; pressing Tab now repeats just that
  market watch, so you can re-check it without leaving and reopening the board.
- **State troopers can pull you over for speeding.** Routes now have patrol
  windows -- hotter on busy interstates, in construction, and in dense regions,
  cooler out on the plains, with a night DUI bump. Speed badly inside one and a
  trooper lights you up: signal with X, brake to a stop on the shoulder, and sit
  through a license and logbook check that ends in an on-the-spot ticket (paid
  immediately, escalating with each stop) or a warning if it's a first, marginal
  stop or your reputation is strong. Run from the stop and it's logged as
  evasion -- a heavier fine and a serious reputation hit. Speeding the patrols
  don't catch still accrues the quieter safety-record cost at settlement.
  Relaxed mode keeps patrols light.
- **Consult the controls without leaving a drive.** The pause menu now has a
  "Controls and help" entry that opens the how-to-play reference straight to the
  driving keys -- page through it, read it line by line, then escape back to the
  road. The keys list also now includes S, A, and U.
- **HTML player manual.** Portable builds now ship `USER_MANUAL.html` alongside
  the Markdown one: the same manual rendered as a clean, accessible web page
  (semantic headings and real tables) you can open in any browser.
- **Three new on-demand driving keys.** **S** reads the posted speed limit where
  you are -- the zone if any, and how far over you are -- so you no longer have
  to dig into the status menu. **A** repeats the last route announcement, for
  the one you missed before you could react. **U** reads what is coming up:
  imposed speed limits, stops, and exits ahead, so a zone or gate never blindsides
  you. All three are listed in F1 help and the manual.
- **Drowsiness has real consequences now.** Push past severe fatigue and you
  start to nod off: a rumble-strip jolt and a warning give you a moment to steer
  or brake and stay awake. Catch it and you carry on; miss it and you drift onto
  the shoulder for damage and lost speed. Keep driving exhausted and the nods
  come faster and harder until a third miss forces you off the road. Sleep is no
  longer optional once you are running on empty -- and in relaxed mode, where
  hazards are rare, managing fatigue becomes the heart of the drive.
- **Posted speed limits that change by corridor.** The flat 70 everywhere is
  gone. The limit now comes from the highway and region -- rural Interstates run
  70 in the Midwest and East, 75-80 across the West, US highways and state
  routes slower -- and drops to an urban limit on the city stretches. Crossing
  into a new limit is spoken like a sign ("Speed limit 75"), the limit restores
  correctly when you leave a construction zone, and speeding is judged against
  the corridor you are actually on.
- **Seasons and temperature.** Your career now moves through the year, and the
  weather follows. A regional temperature model (a seasonal swing plus a
  day-night swing, warmer in the desert and Gulf, colder across the northern
  tier) decides whether precipitation falls as rain or snow and whether storms
  can brew, so snow is a cold-season risk, thunderstorms a warm-season one, and
  a Great Lakes January night freezes while a Gulf Coast one does not. Because
  hazards are weather-gated, snow squalls and ice now show up in winter and
  hail in summer, on their own. The terminal time-and-weather readout names the
  season, and weather reports include the temperature in your units. With live
  weather turned on, the season follows the real-world calendar so it matches
  the live conditions you are pulling in; otherwise it follows your career clock.
- **Cargo weight now changes how the truck drives.** Gross weight is the
  tractor-and-trailer tare plus the actual payload, so a heavy load pulls away
  gently, lugs harder on grades, and burns more fuel, while a light load or an
  empty pickup deadhead is noticeably brisker. Heavier freight is now a real
  trade-off, not just a number on the dispatch board. The driving status screen
  shows gross tonnage alongside the cargo weight.
- **Load-sensitive braking.** The foundation brakes have a fixed force ceiling
  sized for the rated gross, so a load heavier than the rated weight is
  brake-capacity limited: it decelerates more gently, takes longer to stop, and
  heats and fades the brakes sooner. Loads at or below the rated gross brake
  exactly as before. Overloading a run now bites on a downgrade or a panic stop.
- **Grounded, context-aware road hazards.** Hazards now only happen where and
  when they plausibly would. Standing water and hydroplaning need wet weather;
  snow squalls, bridge-deck ice, and black ice on shaded grades need snow;
  dense-fog brake-lights need fog; crosswind shoves and dust storms need high
  wind in open country; rockfall and runaway-truck hazards need mountain
  terrain. Deer and elk are biased to dawn, dusk, and night, with regional
  species. The implausible ones are gone -- no more farm equipment merging
  onto the interstate or a dust devil on a clear, calm day.

## 1.7.0 - 2026-06-26

### Added

- **Relaxed mode now actually relaxes the road.** In relaxed hours-of-service
  mode, random road hazards are much rarer, so the drive centers on driver
  responsibility -- hours, fueling, repairs, and fatigue -- instead of constant
  emergency braking. Realistic mode is unchanged. The Settings help for Hours
  of service spells out the difference.
- **Dispatcher pay advances (no more soft lock).** A broke driver who can no
  longer afford fuel can now draw a cash advance against the next load -- from
  the terminal hub or any in-trip rest stop -- and it is repaid automatically
  out of the next delivery settlement. The advance is offered only while cash
  is low and is capped, so it stays a recovery line rather than free money. A
  negative balance is no longer a dead end.
- **Discord Rich Presence (optional).** When Discord is running, your profile
  can show broad game activity -- the main menu, the terminal, driving a route,
  resting, or delivering -- with high-level route and cargo context. Only
  general game status is shared, never save files or personal details. It is on
  by default and can be switched off in Settings → Gameplay → Discord presence,
  and the game starts, plays, and exits cleanly whether or not Discord is open.
- **Bigger freight map.** The playable network grows to 194 cities and
  437 routed legs, adding many more regional hubs, shorter connector lanes,
  and route-backed freight choices across the country.
- **Highway exit callouts.** Interstate drives now announce upcoming
  interchanges the way a real sign reads them -- "In 2 miles, exit 7 for
  US-1 North toward Trenton and New York" -- with the exit number, the route
  you would take, and its control cities. Exit data is sourced from
  OpenStreetMap and snapped onto each corridor.
- **Grounded exits and onramps.** When a rest stop sits at a real interchange,
  the exit prompt and ramp now name its number ("Signaling for exit 113, the
  Petro Stopping Centers"; "You take exit 113"). Each run also opens with an
  onramp callout -- "Merge onto I-65 South toward Indianapolis" -- and highway
  changes name the new road and direction.
- **Optional lane drift.** Gameplay settings now include off, light, and
  realistic drift so players can add a gentle steering task, rumble-strip
  warnings, and off-road consequences without making the default drive harder.
- **Packaged changelog and manual.** Portable builds now include
  `CHANGELOG.md` and `USER_MANUAL.md` in the game folder so release notes and
  the player manual are available offline.
- **Player manual.** A new public manual now gathers install, career,
  dispatch, driving, saves, settings, accessibility, and troubleshooting
  guidance in one linkable place.
- **Music remakes.** The main menu theme, Open Road, and Night Haul now use
  new Suno remakes while keeping their familiar Freight Fate music slots.
- **Music rotation.** All menu and driving music beds now play once and rotate
  through their active pool instead of looping.
- **Quieter music by default.** New settings now start background music at half
  volume so speech and driving cues stay comfortably in front.
- **Expanded music beds.** Freight Fate now includes longer menu, facility,
  daytime driving, and nighttime driving music. Menus and freight facility
  screens use a career-aware pool, and active drives use stable day/night
  pools that rotate without reshuffling abruptly while you are on the road.
- **Truck cab sound refresh.** Engine start, idle, shutdown, horn, gear shift,
  parking-brake set and release, and highway road ambience now use an updated
  in-cab vehicle sound set, thanks to [Darren Duff](https://darrenduff.com/).
  The start cue is trimmed so the idle loop takes over cleanly.
- **Night driving ambience.** Night drives now play a new recorded in-cab
  night ambience loop.
- **More music.** New night beds: a menu theme for careers loaded after dark,
  and a late-night driving piece.
- **New drowsiness yawn.** The fatigue yawn cue uses a fresh sound, thanks to
  [Darren Duff](https://darrenduff.com/).
- **New achievement system.** Careers now track achievements across a range
  of categories, with a spoken main-menu viewer and a chime when you unlock
  one. Existing careers carry over. Note: a career saved on a preview snapshot
  may not load on an older stable release.

### Changed

- **Safety announcements no longer get buried, and you get more warning.** Zone
  entries, construction and traffic warnings, and checkpoints now preempt
  ambient chatter (weather, tolls, state lines) on the event voice instead of
  queuing behind it -- so a "construction ahead" never arrives after you have
  already entered the zone. Zone warnings also lead by real time now, not a
  flat distance: the heads-up scales with your speed and pacing, so 70 mph at
  high time compression gets a usefully earlier callout instead of a couple of
  seconds.
- **Truck-legal routing everywhere.** Every corridor's geometry, elevation, and
  grades are now derived from OpenRouteService's heavy-goods (driving-hgv)
  profile. The original cross-country legs (NY-Boston, the I-70/I-80 spine, and
  about a hundred others) were still on the car-routing engine; they now match
  the rest of the network with truck-legal paths and real truck elevation. Their
  grade profiles are finer too -- the old car-engine legs had a single grade per
  corridor, where the truck engine breaks each into the real run of climbs and
  descents -- though no leg's overall terrain rating changed. Distances were
  already accurate, so pay and deadlines are unchanged. The refreshed route
  data is included in the game, so driving still works fully offline.
- **Real weather now uses the National Weather Service.** Optional live weather
  switched from Open-Meteo to the U.S. National Weather Service API
  (api.weather.gov). It is still free and needs no API key, reads each city's
  nearest official station for current conditions, and keeps the same seamless
  fallback to simulated weather when offline.

### Fixed

- **The truck can no longer roll away while you rest.** Opening a truck
  stop or rest-stop menu now sets the parking brake and cuts the throttle, the
  same way pulling into a pickup or delivery does. Before, a rig that crept in
  just under the stop threshold (or idled in gear) could keep drifting down the
  road while the driver slept. Returning to the road now reminds you to release
  the parking brake with P.
- **No more implausible interstate hazards.** The random road-hazard pool no
  longer surfaces things that can't happen on a limited-access interstate, or
  that are really weather rather than a brake-now event: farm equipment merging
  onto the highway, sudden downpours and thunderstorm downpours, and hail. Real
  weather still arrives through the weather system, and genuine road hazards --
  standing water, whiteout squalls, debris, stopped traffic, crosswinds,
  wildlife, rockfall -- stay.
- **Phantom state-line crossings.** Highways that run alongside a river border
  -- I-84 down the Columbia Gorge most of all -- no longer announce a flurry of
  back-and-forth state crossings the driver never makes. I-84 hugs the Oregon
  bank of the Columbia (the Oregon/Washington line) for about 100 miles without
  ever crossing it, but corridor sampling against a simplified boundary used to
  flicker across the line and fabricate the crossings; a Portland run could call
  the Oregon/Washington line four times before the real Oregon/Idaho border. The
  baked route data is now scrubbed of these round trips (71 across 20 legs,
  including I-5, I-24, I-29, I-79, and I-90 corridors), and the enrichment
  pipeline guards against re-introducing them.
- **Salem connected to Portland.** Salem now has a direct I-5 leg to Portland
  (about 46 miles). Before, Salem was wired to Seattle and Tri-Cities but not to
  Portland right next door, so a Salem-to-Portland run routed 176 miles the
  wrong way -- south to Eugene and back north through Salem -- and long hauls out
  of Salem were labeled I-84 from the start even though they leave on I-5. The
  redundant direct Salem-Seattle and Salem-Tri-Cities legs are gone; those trips
  now compose through Portland with correct per-highway signage (I-5 out of
  Salem, I-84 only once you reach the Columbia).
- **Real weather warm-up.** With real weather enabled, a drive now starts in
  neutral clear conditions and waits for live data, instead of briefly showing a
  simulated condition that the live data immediately replaced. That warm-up
  flicker could also wrongly unlock a weather achievement (for example, a rain
  achievement for weather you never drove in). Simulated weather still runs as
  the offline fallback when live data cannot be reached.
- **macOS save location.** Saves now live in
  `~/Library/Application Support/FreightFate` instead of beside the app in
  Applications, matching macOS conventions. Existing saves found next to or
  inside the app bundle are moved into the new location on first launch.
- **Empty reposition arrivals.** Finishing a bobtail (empty reposition) run no
  longer crashes on arrival. The "Repositioned" summary screen now opens and
  reads its relocation summary instead of failing as you reach the new city.
- **Speech setting previews.** Adjusting speech rate, pitch, volume, or voice
  now previews with the voice being changed, so a selected SAPI or OneCore
  voice speaks its own new setting.
- **Truck idling.** The diesel now stays running through pickup check-in,
  loading, route planning, loaded departure, and active-drive resume instead
  of forcing a fresh engine start.
- **Destination exits.** Delivery routes now require taking the real signed
  exit for the destination when one is listed, instead of completing just by
  driving to the end of the highway corridor.
- **Destination exit callouts.** Destination exits now announce the signed exit
  and toward cities before the ramp, then tell you to press X; adaptive cruise
  cancellation includes that exit guidance.
- **OneCore pitch.** Windows OneCore speech now keeps its native default pitch
  unless the player changes the pitch setting.
- **Metric driving status.** Metric mode now reports driving status,
  speed limits, traffic, pickup distance, and legal-stop distance in metric
  units instead of mixing in mph or miles.
- **Metric traffic speed.** The traffic-queue speed shown in the route line now
  reads in kilometers per hour in metric mode, instead of staying in miles per
  hour next to the already-metric distance.
- **Metric navigation cues.** Spoken GPS guidance -- onramp, continue, stop,
  exit, traffic, and construction-zone callouts -- and the Map status screen now
  give distances in kilometers in metric mode instead of miles, matching the
  rest of the metric driving readouts.
- **Metric speed limits.** Construction and traffic zone callouts now speak the
  posted speed limit as a metric value in metric mode instead of the mph number.
- **Live unit switching.** Switching between miles and kilometers mid-drive now
  updates spoken navigation guidance right away, including the distances already
  laid out along the current route.
- **Packaged update checks.** The updater now recognizes standalone packaged
  folders more reliably, so switching to preview snapshots does not leave the
  update screen confused about how the game was installed.
- **Quieter exit guidance.** Ordinary highway exits now stay available in the
  route screen without being announced during the drive unless they lead to a
  stop you can actually take.
- **Route key priority.** Pressing R now keeps the next actionable route detail
  first, while Shift+R reports the next listed highway exit.
- **State-line timing.** State crossing previews now speak about 10 miles out
  instead of 2 miles out, giving the preview and crossing announcements more
  room at highway speed.
- **Upper gear spacing.** Automatic shifting now holds 9th gear longer before
  entering overdrive 10th, so the truck no longer reaches top gear around
  city-road speeds.
- **Portable save folders.** Snapshot builds now move nearby duplicate
  portable save folders into the active `FreightFate\saves` folder instead of
  leaving players with two likely save locations after extraction or updates.
- **Clearer help.** F1 help now focuses on what the selected item does for the
  player instead of repeating menu controls, and garage upgrade help explains
  how each upgrade changes the truck.
- **Updater works in packaged builds again.** Packaged copies are now detected
  correctly, restoring update checks, install, and crash logging.
- **Facility approach speed cues.** Pickup deadheads now use lower-speed
  facility access roads, deliveries slow through a final receiver approach,
  and the last gate prompts are shorter so stopping instructions land faster.
- **Facility gate ambience.** Pickup and destination facility screens now use a
  quieter loading-dock ambience that stays away from truck-idle rumble.
- **Preview sound volume.** The refreshed truck, road, weather, route, and
  facility sounds now play at full source strength before the player's volume
  settings are applied, so lowering and raising sound effects behaves more
  predictably.
- **Achievement speech routing.** Achievement unlocks now speak through the
  screen reader voice instead of the separate driving-event voice, so players
  who miss or interrupt an unlock can still review it later from the
  Achievements menu.
- **Facility and settings audio fixes.** Terminal and yard screens now use
  the new facility-gate ambience, delivery completion no longer buries the
  dock and settlement cues under a generic menu sound, and volume settings
  persist into the next game session.
- **Status and settings navigation.** The driving status panel now opens into
  clear route, driver, truck, and map-style status screens, and Settings uses
  category menus for gameplay, audio, speech, weather, and updates.
- **Menu navigation polish.** Delivery completion now presents settlement,
  route, truck, and career details in one continuous list, while Settings keeps
  its category menus for easier browsing.

## 1.6.0 - 2026-06-19

### Added
- **Contextual route and weather audio.** Driving now uses in-cab rain, snow,
  wind, fog horn, and thunder cues plus short route-event sounds for hazards,
  construction zones, inspections, tolls, state crossings, rest stops, weigh
  stations, facility gates, and docking. The road bed is back in the mix so
  the cab does not feel dry while moving. The experimental vehicle engine sound
  redesign is still being tuned and is not part of this release.
- **Route rest, toll, and settlement realism.** Route planning now uses richer
  truck-stop data, handles shoulder-sleep edge cases more cleanly, and accounts
  for toll and settlement details more explicitly.
- **Air-brake startup and reservoir behavior.** Trucks now build air
  pressure before departure, keep spring brakes engaged until the system is
  ready, and model service and emergency reservoir pressure while driving so
  braking feels more like a heavy truck without stranding new careers.
- **Driving status menu.** Pressing Tab while driving now opens a spoken status
  menu with load, trip, truck, route, and route-stop details from the road.
- **Better route stops.** Dispatch-supported freight now
  relies on curated truck-relevant route stops only: placeholder midpoint
  POIs no longer count as real route support, long-haul lanes must include
  explicit fuel-capable stops, and route summaries/GPS stop details
  now give clearer parking certainty.
- **Auto-updater.** The packaged game now checks GitHub for new releases
  when you reach the main menu. When one is found, a fully spoken prompt
  offers "Download and restart" (downloads the update, swaps it in, and
  relaunches the game for you), "What's new" (reads the update's changelog
  line by line), "Remind me later", and "Skip this version". A new
  Settings entry, "Update channel", picks between stable releases and preview
  builds, and "Check for updates" checks immediately.
- **Real pickup and loading flow.** Job offers now name the origin
  facility as an actual stop on the trip instead of flavor text. After
  accepting a load, you check in at the listed facility, load only while
  stopped, then plan the loaded trip to the destination.
- **Company terminal dispatch flow.** New careers and continued drives now
  frame the service-area hub as a company terminal or yard instead of a
  generic city spawn. Dispatches start with a local deadhead move from the
  terminal to the shipper, and delivery settlement parks the truck at the
  destination area's terminal or yard for the next assignment.
- **Destination facility docking.** Deliveries no longer settle just
  because the truck reached the destination city. The game now warns at
  speed, keeps you in control until a full stop, opens a facility menu
  with a dock/yard cue, and requires "Dock and deliver" before payment.
  "Check paperwork" previews facility, cargo, payout, deadline, and damage
  details without completing the load.
- **Real freight facilities on job boards.** Cities now offer freight from
  classified locations such as terminals, warehouses, ports, intermodal
  yards, air cargo areas, manufacturing plants, food terminals, industrial
  parks, retail distribution hubs, and bulk facilities. Cargo is filtered
  by plausible facility type.
- **Highway exits.** Rest stops now sit at proper exits. They are
  announced a few miles out ("Press X to take the exit for it"); X
  signals for the exit (and X again cancels), you slow to 45 or less for
  the ramp — any faster and you blow past it — then half a mile of ramp
  and brake to a stop, and the rest stop menu opens by itself. The ramp
  is off the highway: hazards and speeding checks pause while you are on
  it. Pressing T while stopped on the highway at a stop still works.
- **Explicit highway stop positions.** Route data now stores named highway
  amenities with explicit mile positions instead of spreading rest stops
  evenly across a leg. The first curated offline stop set uses sourced rest
  areas and travel centers, keeping the game playable without live map lookups.
- **Reverse gear and missed-stop recovery.** Trucks can now back up.
  Automatic players can hold Down while stopped to reverse slowly, then
  touch Up to brake and return to forward drive; manual players can press
  the clutch and Backspace for reverse. If you miss a rest stop, slow
  down, back up carefully, stop, and press T.
- **Cruise control.** K sets cruise at your current speed, matching common
  highway driving expectations, and holds it with a slow throttle governor
  through grades.
  K again, any braking, the emergency brake, a stall, or taking an exit
  cancels it — and a hazard warning hands control straight back to you.
  Space reports speed.
- **Region-flavored road hazards.** The hazard pool now mixes nationwide
  staples with local flavor for the region you are driving through: dust
  devils and tumbleweeds in the Southwest, deer and farm equipment in
  the Midwest, rockfall in the Rockies, elk and standing water in the
  Pacific Northwest, and more.
- **Separate voice for driving events.** Road events — hazard warnings,
  collisions, weather changes, rest stop and city announcements, HOS and
  fatigue warnings, speeding, inspections, speed callouts — now speak
  through a dedicated Windows SAPI voice, so a screen reader reading menus
  or echoing keystrokes can no longer cut off a "Brake now!" mid-sentence.
  A new Settings entry, "Driving event voice" (default: separate SAPI
  voice), switches events back to the screen reader. When SAPI is
  unavailable, or is already the main voice, events fall back to the main
  channel automatically.
- **Emergency brake.** Hold B while driving for the hardest possible stop:
  instant full application plus the spring brakes (about 1.6 times the
  service brakes, still subject to weather grip and brake fade), with a
  loud air-dump cue. Use it for hazards and for rest stops you would
  otherwise overshoot. Mentioned in the tutorial, F1 controls, and the
  manual.
- **Roadside mechanic.** The pause menu while driving now offers "Call a
  roadside mechanic" once damage is past 25 percent: a field patch back
  down to 25 percent damage for a 500-dollar callout plus 110 dollars per
  percent repaired (a steep premium over the garage). The repair takes 90
  in-game minutes against your deadline and duty window, and the bill is
  due even if it puts you in debt — never a dead end.
- **Time and weather in the city.** A new city menu entry speaks the
  clock, the time of day, the day of your career, and current conditions
  in town (live Open-Meteo data when real weather is enabled).
- **Sleep in any city.** A new city menu entry, "Sleep 10 hours", gives a
  full night at your terminal: fresh hours of service, zero fatigue, and
  the clock advances 10 hours. Previously a spent duty window followed
  you into the city with no remedy except driving — illegally — to the
  first rest stop of the next run.

### Fixed
- **Pickup facility sounds.** Pickup gates and loading now use the new facility
  ambience and dock cues instead of the older generic menu notification sounds.
- **Preview builds stay in sync with release notes.** Preview builds now pick up
  player-facing changes that have already been prepared for the next stable
  release, so their "What's new" text no longer falls behind.
- **Save resume keeps traffic zones stable.** Continuing a saved drive now
  seeds trip weather from the saved trip seed too, so traffic and
  construction-zone layouts regenerate consistently across operating
  systems.
- **Updater connections on macOS and Linux.** The packaged game's Python
  runtime looks for certificate authorities at paths that only exist on
  the build machine, so on macOS and Linux every secure connection — the
  update check, the download, and the real-weather fetch (which silently
  fell back to simulated weather) — could fail certificate verification.
  The game now ships its own certificate bundle (certifi) and uses it
  alongside the system store on every connection.
- **Update errors now say what went wrong.** "Could not reach the update
  server" covered everything from a dropped connection to a blocked DNS
  lookup. The check and download now speak the actual reason — "The
  secure connection could not be verified", "The server answered with
  error 403", "The server address could not be found", and so on. The
  packaged game also writes a session log to logs/game.log, so a
  player can share the full error when reporting a problem.
- **Hazard warnings were unbeatable at highway speed.** The reaction
  window was a fixed 3 to 4.5 seconds, but a full-service stop from 65
  to the safe 25 miles per hour takes about 5 — even the emergency brake
  could not make it once you add the time to hear the warning. The
  deadline is now the braking time the truck actually needs from its
  current speed (on the current surface and grade) plus the rolled
  reaction window, so hitting the brakes promptly always succeeds — in
  rain or snow you get the longer stop those surfaces really take.
  Drowsiness now eats into the reaction part only instead of the whole
  window, since a tired driver reacts late but the truck stops no
  slower. Warnings also lead with "Brake now!" instead of ending with
  it, so you can be on the brakes before the sentence finishes.
- **Collision stall soft-lock.** A hard collision could stop the truck
  while the automatic transmission was still in a high gear; the engine
  then stalled the instant it was restarted, every time, stranding the
  player (it read as "too damaged to start", since the same crashes also
  max out damage). The automatic now returns to first gear whenever the
  truck is stopped in a higher gear, and restarting after a stall recovers
  cleanly.
- Pressing E with a bone-dry tank no longer dead-ends on "the engine will
  not start": the out-of-fuel roadside rescue now triggers from there too.
- **The C key's arrival estimate was a constant.** It always assumed
  55 miles per hour, so it never responded to how fast you were actually
  driving. It now tracks your current speed once you are meaningfully
  rolling (and says so), falling back to a typical highway pace while
  parked, and names the basis either way.
- **Abandoning a job lost the hours you drove.** The world clock snapped
  back to the departure time while hours of service and fatigue kept the
  accrued wear, and the freight market did not advance. The time spent on
  the failed run now counts.
- **Trip pacing now applies mid-trip.** Changing "Trip pacing" from the
  pause menu's settings was silently ignored until the next delivery; the
  active trip now picks it up immediately.
- **Unsafe engine shutdown blocked.** Pressing E at road speed no longer
  shuts off the engine. The game now gives spoken feedback and requires a
  safe low-speed stop before shutdown.
- **Delivery at speed blocked.** Arriving at the destination at highway
  speed no longer completes the job. Settlement now requires the full
  stopped facility docking flow.
- **Tampered saves are quarantined.** Career saves now carry an integrity
  signature. Old unsigned saves migrate forward, but edited or corrupted
  saves are moved aside instead of being loaded as valid career data.
- **Implausible route detours filtered.** Route options now reject obvious
  short-haul detours that send drivers far out of the way, while still
  allowing meaningful alternate long-haul routes.
- **State progress announcements improved.** Trips now announce state
  crossings and nearby cities along the route, not only the destination
  state.
- **Construction-zone warnings are actionable again.** Construction zones
  now give a spoken GPS warning about 2 miles before the slowdown begins,
  and troopers will not clock construction-zone speeding until you have
  had about a mile inside the zone to react. Speech-first players can
  slow down in time again instead of being fined on the same update that
  first announces the zone.

### Changed
- **How-to-play driving guidance.** The main-menu guidance for driving controls
  is shorter and more direct.
- **Early career progression and pay.** Low-level jobs now pay enough to
  make early progress feel worthwhile after operating costs, and higher
  levels unlock clearer differences in range, cargo, endorsements, and
  long-haul opportunities.
- **Truck acceleration and shifting.** Loaded trucks reach safe highway
  speeds more plausibly, top gear behaves more like mild overdrive, and
  automatic shift cues are easier to hear without adding air-brake sounds
  to gear changes.
- **Freight market terminology.** Player-facing market wording now uses
  trucking language: tight, loose, and steady, replacing the old generic
  market labels.
- **Real terrain on real highways.** A geography audit corrected 20 of
  the 106 legs. The famous grades are now mountains: Monteagle on I-24
  (Nashville-Atlanta), the Cumberland Plateau on I-40
  (Knoxville-Nashville), the Pennsylvania Turnpike's Allegheny crossings
  (Philadelphia-Pittsburgh and Baltimore-Pittsburgh), and US-95's Idaho
  canyon country (Spokane-Boise). Rolling country stopped pretending to
  be flat: I-70's Missouri River hills, the Flint Hills and Arbuckles on
  I-35, Tennessee's Highland Rim on I-40, Wisconsin's driftless coulees
  on I-94, the Carolinas' piedmont, Connecticut on I-95, and the desert
  passes on I-10 (San Gorgonio, Texas Canyon) among others. Genuinely
  flat country — the high plains, the Gulf coast, Florida, and the Illinois
  prairie — stays flat.
- **Realistic deadlines.** Dispatch can no longer ask for the
  impossible. Deadlines are now built from the hours a law-abiding
  trucker actually needs — driving at an achievable 55 mph average, plus
  the 30-minute break every 8 driving hours and a 10-hour sleep for
  every 11-hour shift the distance demands — with 20 to 50 percent
  shipper slack and a flat hour for fuel on top. San Antonio to Dallas
  now quotes a workable 7-to-8-hour window instead of a sprint.
- **State trooper groundwork.** The next law-enforcement milestone is outlined:
  patrol intensity by corridor, CB chatter warnings, pull-overs, immediate
  fines, and an enforcement setting.
- **Portable saves.** Profiles and settings now live in a `saves` folder
  inside the game's own directory (next to the executable in release
  builds) instead of the per-user data directory. Existing saves are migrated
  over automatically on first launch; the originals are left in place.

## 1.5.0 — 2026-06-10

"On the Clock": hours of service, fatigue, day and night, and overnight
parking. Everything runs on the in-game clock (`settings.time_scale`
compresses it as usual), never wall time.

### Added
- **Hours of service.** Simplified FMCSA rules per shift: 11 hours of
  driving inside a 14-hour duty window, a 30-minute break required after
  8 hours at the wheel, and a 10-hour sleep to reset. Spoken warnings at
  2 hours, 1 hour, and 30 minutes before each limit (each fires once),
  and at the violation itself. The C key now reports the clock time and
  HOS status alongside the deadline; Tab includes it at normal and chatty
  verbosity. Driving past a limit risks roadside inspections with
  escalating fines (200 to 2,000 dollars) and reputation hits — never a
  game over. A new Settings entry, "Hours of service", picks realistic,
  relaxed (every limit 25 percent longer), or off.
- **Rest stop menu.** Pressing T at a rest stop now opens a fully spoken
  menu: refuel (as before), take a 30-minute break, or sleep 10 hours.
  Resting advances the in-game clock, so the delivery deadline keeps
  counting — that is the tension.
- **Fatigue.** Builds with continuous driving (faster at night), eases
  with breaks, and clears with sleep. A drowsy driver yawns, drifts onto
  the rumble strip, hears spoken drowsiness warnings, and reacts late to
  hazards (the reaction window shrinks up to 40 percent). Deterministic
  under the trip seed.
- **Day/night cycle.** Dawn, day, dusk, and night derived from the career
  clock (new careers still start at 6 AM). Nights bring sparser traffic
  zones, a higher hazard chance, a cricket-and-air night ambience layer,
  and the previously unused "Night Haul" track while driving. V, Tab, and
  C mention the time of day, and arrivals speak the clock ("It is 11 PM").
- **Overnight truck parking.** Arriving at a rest stop between 8 PM and
  4 AM, the lot may be full — more likely as the evening wears on,
  deterministic per trip seed. A spoken menu offers driving on to the next
  stop or shoulder parking: a full HOS reset but poor rest (fatigue floor
  of 30) and a 15 percent chance of a 150-dollar ticket.
- New manual page "Hours and rest"; F1 help on all new menus.
- New procedural sounds: `ambient/night` and `driver/yawn`
  (regenerate with `tools/generate_audio.py`).

### Fixed
- **Speech backend selection.** Prism's registry ranks NVDA above every
  other backend whether or not NVDA is running, so on machines without it
  the game bound to a dead NVDA connection and stayed silent. The backend
  choice is now validated against actual runtime support and falls down
  the priority list (JAWS, One Core, SAPI, Speech Dispatcher, ...) to the
  best backend that can really speak. A new
  `FREIGHT_FATE_SPEECH_BACKEND=<name>` environment variable forces a
  specific backend for troubleshooting.

### Compatibility
- Save format version is now 3. Old v2 profiles and pre-1.5 mid-trip
  snapshots load cleanly, defaulting to a fresh HOS clock and a rested
  driver.

## 1.4.0 — 2026-06-10

### Added
- **Home terminal picker.** A new career now asks where it should begin:
  after name entry, a fully spoken menu lists every city labeled by region
  ("Atlanta, the South"), with the usual arrow, Home/End, and first-letter
  navigation plus F1 help. Defaults to Chicago; Escape returns to name
  entry with the typed name intact. Existing profiles are untouched.
- **A real interstate network.** The map grows from 21 cities and 27 legs
  to 59 cities and 106 legs along real corridors (I-95, I-90, I-80, I-75,
  I-70, I-65, I-40, I-35, I-10, I-5, and more), so neighboring cities sit
  roughly 100-250 miles apart. Every new city has real coordinates for the
  live-weather feature, a weather region, and freight locations with
  regional identity: produce out of the Central Valley, autos around
  Detroit, electronics at the container ports, grain and livestock across
  the plains, machinery in the rust belt. Boston and Seattle are no longer
  dead ends; no city has fewer than two highways.
- **Career-arc job generation.** Rookie boards (levels 1-2) offer short
  regional work: mostly single-leg hops to neighboring cities, capped
  around 280-340 miles, with destinations weighted toward nearby cities so
  freight follows plausible lanes. The distance cap grows with level and
  cross-country hauls (600+ miles) unlock around level 4-5 as a dedicated
  long-haul slot on the board. A flat hookup fee keeps short early runs
  profitable after fuel.

### Compatibility
- All 21 original cities and all 27 original direct legs are preserved
  verbatim, so old profiles and mid-trip snapshots load and resume unchanged.

## 1.2.1 — 2026-06-09

### Added
- **Mid-trip save and resume.** "Save and quit to main menu" while driving
  now snapshots the delivery — job, route, position on the route, clock,
  speeding strikes, and trip damage baseline — into the profile. Continue
  (and Load driver) resume the drive right where you left off, parked with
  the engine off, with a spoken recap of cargo, destination, remaining
  miles, and hours used. Construction and traffic zones reappear in the
  same places thanks to a persisted trip seed, and stops or cities already
  passed are not re-announced. The Load driver list shows mid-delivery
  profiles as "on the road to <city>".

### Fixed
- "Save and quit to main menu" no longer silently discards the delivery
  (previously Continue always returned to the city with the job gone).

## 1.2.0 — 2026-06-09

### Added
- **Smoother truck engine audio.** Engine sound now follows RPM more naturally,
  with smoother transitions as you accelerate, shift, and settle into highway
  speed.
- **Garage upgrades** (Garage → Upgrades), money-gated and saved on the
  profile: engine tune (+10% torque per tier, two tiers), aerodynamic kit
  (−12% drag), long-range tank (+50 gallons), and reinforced brakes (fade
  onset pushed 150 degrees hotter). Upgrades feed straight into the driving
  physics.
- **A second truck**: the heavy hauler (Garage → Trucks) — a quarter more
  torque and a 200-gallon tank, but blunter aerodynamics and a thirstier
  engine. Buy it once, then switch between owned trucks at any garage.
- **Freight market**: every cargo class carries a pay multiplier (0.8–1.3)
  that drifts each in-game day on a seeded random walk persisted in the
  profile. Job descriptions call out tight and loose markets,
  and the job board opens with a spoken market watch headline.

### Changed
- Truck status and garage refueling respect the active truck's actual tank
  size instead of assuming 150 gallons.
- Save format version is now 2 (older saves load fine; new fields get
  defaults).

### Notes
- BASS is proprietary software, free for non-commercial use. If Freight Fate
  is ever sold commercially, a paid license from
  [un4seen developments](https://www.un4seen.com/bass.html#license) is
  required. See the README's license section.

## 1.1.0 — 2026-06-09

### Added
- **Real-world weather** (Settings → Weather source): live current
  conditions for each city from the free
  [Open-Meteo](https://open-meteo.com) API (no key required). WMO weather
  codes map onto the game's conditions, including strong-wind promotion.
  Fetches run in background threads with a 15-minute cache; offline or on
  any failure the simulated weather takes over seamlessly.
- City coordinates in the world data.
- With real weather enabled, route planning's W key speaks live conditions
  for the cities along the route, and the V key while driving reports
  "live conditions" for the city you are heading toward.

## 1.0.0 — 2026-06-09

First release. Complete rewrite of the prototype.

### Added
- Career mode: jobs, route planning, deliveries, money, experience levels,
  reputation, and cargo endorsements (refrigerated at level 2, high-value at
  level 4).
- Tuned Class 8 truck physics: ten-speed transmission (manual with clutch or
  automatic), torque curve, grades, traction limits, stalling, brake fade,
  engine braking, and realistic fuel economy (~6 mpg loaded).
- 21-city, 27-leg interstate network with Dijkstra route finding and multiple
  route options per job.
- Dynamic regional weather (eight conditions) affecting grip, drag, and safe
  speed, with forecasts and thunder.
- Trip events: construction and traffic zones, road hazards with reaction
  windows, rest stop refueling, out-of-fuel roadside rescue, speeding fines.
- Screen reader output through Prism (`prismatoid`): NVDA, JAWS, SAPI,
  VoiceOver, Speech Dispatcher, and more, with silent fallback.
- Fully synthesized CC0 sound library (43 effects) and three original music
  tracks, all reproducible from `tools/generate_audio.py`.
- RPM-crossfaded engine audio, speed-tracking road noise, weather ambience.
- Accessible UI: spoken menus with wrap-around and first-letter navigation,
  contextual F1 help, accessible text entry, three speech verbosity levels,
  imperial/metric units, and a visible text mirror of all speech.
- First-drive tutorial, six-page in-game manual.
- Atomic JSON saves with multiple driver profiles.
- Packaged builds for Windows and Linux.

### Removed
- SRAL DLL dependency (replaced by the Prism Python package).
- Legacy prototype files and duplicate data files.
