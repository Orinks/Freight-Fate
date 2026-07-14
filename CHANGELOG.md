# Changelog

## Unreleased

### Changed

- **The engine brake now works like a real three-stage jake.** It slows the
  truck through the gears, so it pulls hardest in a low gear with the engine
  turning fast, and does very little in top gear -- set your gear and speed
  before the hill starts. An automatic transmission drops a gear to put the
  jake to work, and shifts up to protect the engine if the hill spins it too
  fast, leaving you a weaker jake in a taller gear. Heavy enough loads can
  outrun the jake entirely, so snub the brakes early or crawl.

- **Brakes now heat and cool like real drums.** Dragging the service brakes
  down a long grade overheats them until they fade badly; short firm
  applications with the jake carrying the load keep them cool. Going faster
  no longer cools hot brakes, and letting a downhill rev the engine past its
  limit now wears the engine -- running at governed speed is safe.

- **Each truck now keeps its own condition.** Tire, brake, and engine wear,
  damage, and fuel stay with the truck they happened to, so swapping tractors
  at the dealer no longer carries your wear -- or your empty tank -- onto the
  next rig, and the garage fixes the truck you actually drove in. A new truck
  off the lot rolls out fresh with a full tank. Careers from earlier versions
  load unchanged: your current wear settles onto every truck you own.

- **Career 1.9 playtests now follow more of a driver's real journey.** Reusable transcript checks cover career stages, driving modes, keyboard-operated controls, speech ordering, and deterministic road events so regressions are caught before they reach players.

- **Relaxed driving now leaves real breathing room without removing the truck.**
  Relaxed pacing keeps weather, traffic, air brakes, fatigue, hazards, and
  consequences understandable, but hazards are spaced farther apart, warnings
  allow more response time, collision damage and fatigue build more gently,
  and routine speech is calmer. Standard keeps the previous balanced pressure,
  while the former Fast pacing is now called Realistic and retains the quickest
  decision cadence. Safety warnings also stay in front of hours and fatigue
  chatter instead of being interrupted.

### Added

- **The alpha ships with a test book.** A new guide in the docs folder
  walks through everything this version changes and how to hear each
  change for yourself: what to set up, what to do, what to listen for,
  and when to call it working. Written for screen-reader playtesting from
  the first line, with the winter driving tests in a companion volume.

- **Cloud restores now get a second integrity check.** Beyond the server's
  signature, a restored profile has to pass the game's own sanity rules --
  wear between zero and one hundred, honest delivery counts, a fuel tank
  that fits in a truck. A file that fails is refused with a plainly spoken
  reason instead of being loaded, and saves from newer versions of the
  game still restore fine.

- **Winter tires are now a real choice at the garage.** A winter-compound set
  bites noticeably harder on snow and ice, and the trade is honest: it wears
  faster and gives up a touch of grip on warm dry pavement. Company tractors
  stay on whatever the carrier specs; owner-operators pick their rubber. The
  rig readout and the garage both say which compound is mounted.

- **Snow chains and chain laws have arrived on the steep grades.** Buy a
  chain set at the garage and it rides in the side box until a flashing sign
  before a snowy or icy pass calls a chain law: Level 1 wants winter tires or
  chains, Level 2 wants chains on the drives. Chaining up happens from the
  pause menu while stopped -- it costs real minutes and real fatigue, and
  doing it in the dark costs more of both. Chained on glare ice the truck
  actually holds: stops shorten dramatically and the engine brake stops
  breaking the drive wheels loose on the descent.

- **Chains are honest equipment, not a magic button.** They want chain speed,
  about thirty miles per hour, and they hate bare pavement: run them fast or
  dry and they grind apart until a chain lets go, whips the fender, and the
  set is scrap. Rolling into an active chain law out of compliance gets a
  spoken warning, and the checkpoint past the sign may write a five hundred
  dollar citation.

- **Freezing rain is now its own weather, and it is the one worth parking
  for.** Rain falling just below freezing glazes the road with ice far
  slicker than snow -- a stop from 40 can take more than twice the room of a
  dry stop from 60. The forecast and weather reports call it out, live
  weather recognizes real freezing rain and sleet, and new road hazards come
  with it. If you drive it, crawl.

- **Hydroplaning now depends on your tires, not just the sky.** Fresh tread
  at highway pressure almost never floats, but the more worn your tires, the
  lower the speed where they start riding the water instead of the road --
  bald tires in a heavy downpour let go near 60. When it happens the truck
  calls it out and steering and braking go soft until you ease off. Deeper
  standing water makes it worse; keeping good rubber on the truck is the fix.

- **The engine brake can now break the drive wheels loose on slick roads.**
  The jake slows only the drive axle, and on ice a full-stage jake in a low
  gear is more than that axle can hold -- the truck warns you the wheels are
  sliding, the retard fades, and the right move is a lighter stage or none at
  all. On dry pavement nothing changes; this is a winter discipline.

- **Your rig now wears with how you drive it -- tires, brakes, and engine each
  have their own meter.** Miles and heavy loads slowly eat tire tread, riding
  the service brakes wears the shoes (hot brakes wear them even faster), and
  hours under load wear the engine -- with over-revving and lugging punishing
  it hardest. Wear talks back: bald tires grip less, worn brakes pull weaker
  and overheat sooner, and a tired engine loses power and burns more fuel. The
  engine brake still costs the shoes nothing, so use it on the long downgrades.
  Your delivery summary tells you what each run added, the truck status
  readouts speak all three meters, and the terminal garage now offers brake
  jobs and engine overhauls alongside tires -- each takes shop time and, for
  owner-operators, real money. Company drivers bill the carrier, as always.

- **Truck stops now sell more than fuel: meals, showers, and rig care that
  keep you and the truck going longer.** A hot meal or an energy drink eases
  fatigue right away and makes the next few hours of driving tire you more
  slowly -- Petro's Iron Skillet dinner beats any roadside diner. At a Pilot
  or Flying J, a fuel purchase makes the shower free, just like real life.
  On the truck side, a Speedco or Love's lube bay slows engine wear for the
  rest of the trip, a tire rotation does the same for tread, and a bottle of
  diesel additive helps a little anywhere you fuel. One food buff and one of
  each rig service at a time -- a new one replaces the old -- and none of it
  ever adds legal driving hours. Your status readout tells you what is
  active and how long it has left.

- **The big-name truck stops along your route now fix your rig -- and each
  brand is good at what it is really known for.** Pull into a Love's or a
  Speedco and their tire bay replaces worn tires fast, close to the garage
  price. TravelCenters of America and Petro run full service shops that also
  do brake jobs on the road. Any other major travel center can mount tires,
  at a road markup -- and an engine overhaul still means a trip to your
  terminal garage. Independent stops fix what their listing says, and Big
  Buck's, famously, fixes nothing. Road shops sell the whole job or none of
  it, so if cash is short, plan for the terminal.

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

### Fixed

- **Cloud backup now tells you when this computer needs to reconnect.** If
  orinks.net stops accepting this computer's sign-in, the cloud backup menu
  now says so and explains the fix, instead of wrongly reporting that your
  backups could not be reached.
- **Long deliveries are easier on the game while you drive.** The destination
  exit is now worked out once and remembered instead of being recalculated
  every moment of the drive, removing a heavy background load tied to a
  reported crash on coast-to-coast routes.

### Changed

- **Playing on more than one computer no longer signs the other one out.**
  orinks.net now gives each of your computers its own token: add a computer
  from the driver setup page and your other machines keep working. If the
  game says your sign-in is no longer accepted, it now points you to the
  computer list on the setup page to get a fresh token for that computer.

## 1.8.1 - 2026-07-13

### Fixed

- **The Mountain Grade driving track sounds right again.** The daytime
  mountain music bed has been replaced with a corrected recording, normalized
  to sit at the same volume as the rest of the soundtrack.

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

- **Online sharing now tells orinks.net which game version you are running.**
  When Profile sharing or cloud backup is on, each post carries the release the
  game was built from, such as a stable version or a nightly date. It is used
  only for moderation and troubleshooting, is never shown publicly, and the
  spoken "Hear what gets shared" disclosure now mentions it.

- **The major toll turnpikes now charge realistic tolls.** Running the Kansas
  Turnpike, the Oklahoma turnpikes, the New York Thruway, the Pennsylvania and
  Ohio turnpikes, the Indiana Toll Road, the Illinois Tollway, the Mass Pike, the
  Maine and West Virginia turnpikes now adds an estimated commercial toll to the
  run -- so a toll route is a real cost to weigh against the free way around.

- **The map explodes from 249 cities to 623, coast to coast.** Since the last
  stable release the drivable network has more than doubled: 623 cities to
  pick up and deliver in, joined by about 139,000 miles of real truck routes.
  Dead zones that used to have nothing drivable for hundreds of miles -- the
  mountain West, the northern plains, the Nevada Great Basin, Appalachia, the
  Gulf coast -- now connect city to city on the real roads, town by town.
  The entries below tour the new country region by region; each nightly
  snapshot's notes carried the town-by-town detail. Special thanks to nromey
  for the mapping work behind it. And watch your fuel out there -- some of
  the new country is a long way between diesel pumps.

- **New England and the Northeast fill in.** Rutland, Keene, Lewiston, and
  Barnstable bring Vermont, New Hampshire, Maine, and Cape Cod onto the map;
  Watertown and Jamestown open New York's north country and Southern Tier;
  Williamsport, Altoona, State College, and Meadville put the Pennsylvania
  mountains on real routes; and fourteen short-haul runs stitch the corridor
  from Boston and Manchester down through Providence, Hartford, and
  Philadelphia to the Chesapeake, including the Bay Bridge run to Dover and
  Salisbury and the New York Thruway up the Hudson Valley.

- **The Mid-Atlantic and Appalachia connect through the mountains.** The whole
  Interstate 81 freight run is drivable -- Staunton, Wytheville, Marion,
  Abingdon, Bristol, and Kingsport -- with Interstate 64 east over Afton
  Mountain into Richmond. The Kentucky parkways and the coalfields open
  thirteen storied mountain runs, from Pound Gap and the Cumberland Gap to the
  New River Gorge road to Beckley, with Paducah and Owensboro on the western
  parkways; Cumberland lands on the Interstate 68 climb over the Alleghenies;
  Lynchburg anchors US-460; and Jackson and Cookeville break the long
  Interstate 40 haul clear across Tennessee into real stops.

- **The Carolinas and the Southeast coast come together.** Durham and
  Spartanburg finish Interstate 85 through the Piedmont; Petersburg, Florence,
  and Lumberton close the Interstate 95 gap, so the East Coast's busiest
  freight run finally drives city to city; eastern North Carolina adds
  Greenville, Jacksonville, New Bern, and Rocky Mount; and Myrtle Beach brings
  the Grand Strand onto coastal US-17.

- **Georgia, Alabama, and Mississippi fill in from the mountains to the
  Gulf.** Interstates 75 and 85 stop in real towns the whole way -- Dalton,
  Cartersville, Valdosta, Tifton, Cordele, Opelika, and LaGrange -- Columbus
  and Albany open the wiregrass, and Dothan, the Peanut Capital, ties three
  states together. The Delta and the Blues Highway open at Greenville,
  Clarksdale, Oxford, Tupelo, Grenada, and Hattiesburg, while Gadsden,
  Cullman, Selma, Natchez, and Panama City round out the Deep South. Louisiana
  fills in too, from Ruston and Natchitoches to Hammond and bayou-country
  Houma, with Alexandria anchoring the middle of Interstate 49.

- **Florida runs border to border.** Pensacola and Crestview break up the
  Panhandle, Ocala and Palm Coast fill the peninsula's spine, and Daytona
  Beach, Sarasota, North Port, Fort Myers, and Naples line both coasts -- with
  the run from Naples to Miami crossing the Everglades on Interstate 75's
  Alligator Alley, no services for eighty miles.

- **Arkansas and the Ozarks open up.** Fayetteville and Bentonville climb the
  real Boston Mountains, Jonesboro reaches the rice-country Delta, Harrison
  and Mountain Home carry the winding Ozark truck routes, Hot Springs crosses
  the Ouachita ridges, the Interstate 49 line finishes across the state from
  Fort Smith to Texarkana, and Pine Bluff, El Dorado, Stuttgart, and
  Russellville tie the farm and timber country into Texas, Louisiana, and
  Tennessee.

- **Texas and Oklahoma become town-by-town country.** The US-287
  Ports-to-Plains spine runs from San Antonio clear to Denver through Vernon,
  Childress, Dumas, and the Oklahoma panhandle; US-281 and US-75 open
  north-south routes beside the crowded interstates; Temple completes the
  Interstate 35 spine; Uvalde and Eagle Pass open the border country; the
  plains add Plainview, Big Spring, Brownwood, and Pampa; Longview takes its
  place on Interstate 20 toward Shreveport; and Oklahoma links up through
  Stillwater, McAlester, Muskogee, Durant, Ardmore, Bartlesville, and Ada.

- **The Great Plains ladder is complete.** Interstate 80 across Nebraska is
  now continuous past the hundredth-meridian marker, Kansas adds Lawrence,
  Emporia, Hutchinson, Great Bend, and Liberal, the Dakotas add Jamestown,
  Pierre, and Aberdeen, a Black Hills freight run links Cheyenne through
  Scottsbluff country to Rapid City, and the Missouri and Iowa heartland
  fills in from Sedalia and Saint Joseph up through Ames, Fort Dodge, and
  Mason City, with Cape Girardeau and Poplar Bluff anchoring southeast
  Missouri.

- **The Midwest and Great Lakes lattice comes together.** Twenty-nine new
  cities across five states -- from Springfield, Flint, and Kalamazoo to the
  Upper Peninsula's Marquette and Sault Ste. Marie and the Iron Range's
  Hibbing -- plus central Indiana around Indianapolis, Ohio's Zanesville,
  Mansfield, and Youngstown, Wisconsin's Fox Valley, and nineteen short runs
  lacing Detroit, Toledo, Fort Wayne, and Milwaukee together. Terre Haute and
  Effingham break the long Indianapolis-to-St. Louis drive, Dubuque anchors
  the US-20 Mississippi crossing, and every city comes with real, named
  freight facilities: haul taconite pellets from the Hibbing mine, steel out
  of Gary Works, and new Subarus from Lafayette.

- **The Rockies and the Great Basin connect end to end.** Wolf Creek Pass and
  the Million Dollar Highway open Colorado's steepest crossings, with grades
  past eleven percent over the San Juans; Durango and Farmington meet at the
  Four Corners; fifteen runs link the northern Rockies from Missoula to Miles
  City; the Silver Valley opens Interstate 90 over Lookout Pass; Rawlins
  lands on Interstate 80 across Wyoming, with Logan and Moab opening Utah;
  New Mexico adds Hobbs, Alamogordo, Roswell, Carlsbad, and Socorro; and
  Nevada's US-93 and US-50 -- the Loneliest Road in America -- cross the
  Great Basin through Ely, Austin, and Fallon.

- **Arizona and the desert Southwest fill in.** The Verde Valley, the Beeline
  Highway, and Route 66 country open Camp Verde, Sedona, Payson, Winslow, and
  Holbrook, with Prescott in the highlands; copper country climbs US-60
  through Globe and the Salt River Canyon to Show Low; the border adds
  Nogales, Sierra Vista, and Douglas; the Colorado River runs from Lake
  Havasu City down to Yuma; and US-89 reaches Page and Lake Powell across
  the Navajo Nation.

- **California and the Pacific Northwest round out the coast.** San Luis
  Obispo and Santa Barbara complete the US-101 coast run, Modesto and Merced
  fill Highway 99 through the Central Valley, the Redwood Highway reaches
  Eureka, the eastern Sierra opens the long US-395 run beneath Mount
  Whitney, the Cajon Pass climb connects Riverside to Victorville, and
  fourteen Cascade-pass runs -- Stevens, White, and Santiam, real grades with
  brake checks -- tie Seattle, Tacoma, and Salem to the Columbia Basin, with
  The Dalles seating the Columbia Gorge.

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
- **Cloud backups now prove they were accepted by orinks.net before restore.**
  orinks.net validates and signs each private revision, and Freight Fate verifies
  that signature before touching a local career. Public Profile sharing stays
  separate: detailed career statistics come only from an accepted backup and
  are omitted when no verified revision exists.

- **Optional Profile sharing stays quiet during driving.** With Profile sharing on,
  Freight Fate can queue automatic road-journal posts,
  achievements, and updates for the public driver profile. Detailed career
  statistics come only from the latest private Cloud Backup accepted by
  orinks.net. Offline posting retries in the background and never adds a spoken
  interruption while driving.

- **Exits now come straight from real-world maps -- with the correct exit names
  and numbers.** On the Interstates, your stops and your destination exit are
  announced with their actual exit number and name and the places they point to --
  "Exit 33, Yemassee," "toward Beaufort and Port Royal," "Durham" -- taken directly
  from real map data, so you always know the right exit to take. This now covers
  the whole Interstate network.

- **Routes now carry the real posted speed limits.** Instead of estimating a
  limit from the road type, every leg on the map now carries the actual posted
  speed limits from map data (interstates, US highways, and more), so your truck
  runs the real limit on the road it is driving. Rural roads without published
  limits still fall back to a sensible estimate.

- **Truck-stop names read cleanly now.** Spoken stop names across the map no
  longer include bare initials like "T A" or leftover store numbers.

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

- **New: real roadside landmarks as you drive.** Routes now call out the world
  going by -- entering a national forest, crossing a named river, approaching a
  mountain pass, a roadside museum ahead -- over 2,800 of them, drawn from real
  map data so a long haul has a sense of place instead of silence. The callouts
  ride the quiet background voice: they wait their turn behind navigation and
  never talk over a safety warning. Thanks to nromey.

- **Billboards line the highway now, and they have opinions.** Every long run
  passes the occasional billboard, read aloud as you go by: earnest church
  signs, truck-wreck attorneys, mystery spots, and the world's largest
  several things. Some routes get their own real roadside culture -- free ice
  water on Interstate 90, alien jerky on Interstate 15 -- and no sign repeats
  itself on the same trip.

- **You choose the roadside chatter you want to hear.** A new Roadside
  chatter group in Settings, Speech and weather, has one master switch and
  separate switches for parks and forests, river crossings, mountain passes,
  museums and attractions, and billboards -- so you can keep the geography
  and lose the jokes, or the other way around. Terse speech verbosity mutes
  all of it, and safety and navigation announcements are never affected.

- **Name-brand truck stops now tell you what they are good at.** Pulling up
  the details on a branded stop adds its specialty -- tire care and a quick
  lube at a Love's, the sit-down restaurant at a Petro -- to the spoken
  rundown at the stop and in the en-route stop listings.

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

- **The Great Lakes split into three regions that each feel like
  themselves.** The Upper Midwest covers Minnesota, Wisconsin, and Michigan's
  Upper Peninsula; the Great Lakes keeps the lower-lakes industrial belt from
  Chicago through Detroit to Buffalo; and the new Corn Belt takes interior
  Illinois, Indiana, and southern Ohio. Each has its own weather, fuel
  prices, freight market flavor, and road hazards, so a winter run out of
  Duluth no longer sounds like a summer haul into Cincinnati.


- **The world got five new sounds, and every shipped sound now earns its
  keep.** Rest stops sound different by daylight: a new daytime truck-stop
  lot ambience (idling diesels, air brakes, a highway pass-by) plays at
  stops before dusk, with the familiar night loop after dark. Warehouse,
  cold-storage, and distribution docks now wrap you in a big reverberant
  warehouse interior instead of the generic gate loop. Signaling for an
  exit or a pull-over clicks like a real indicator stalk, overworked
  brakes squeal once they pass their fade temperature, and a microsleep
  forced stop ends in a proper tire screech. All five are ElevenLabs
  generations added to the `tools/generate_sounds.py` catalog (which now
  supports seamless-loop requests), and the last orphaned synthesizer-era
  asset is gone.
- **54 new achievements -- the badge wall passes one hundred.** The catalog
  grows from 60 to 114 badges: new state, region, and city arrivals (Virginia
  ridges, bluegrass country, the Jersey Turnpike, Waco, the Mississippi coast,
  Nashville, El Paso, Laredo, Baton Rouge, and more), compass runs north and
  south, cargo firsts (refrigerated, heavy-haul, high-value, farm freight, and
  max-gross loads), career milestones out to 200 deliveries and 100,000 miles,
  season and calendar badges (including one for a certain day in early April),
  close-call deliveries (deadline squeakers, empty fuel tanks, midnight and
  pre-dawn docks), citation mishaps, congestion, inspections, deep repairs,
  roadside rescues, bobtail repositions, and a fully optioned rig. As always,
  every badge quietly tips its hat to a country or trucking song -- this round
  adds nods to a heap of underground country artists alongside the classics.
- **The career economy now pays like a real one.** Company drivers fuel and
  repair on the carrier account on the road, not just at terminals -- an
  out-of-fuel rescue dings the service record instead of the wallet, while
  owner-operators keep paying their own way. Demanding freight teaches more:
  specialty and premium cargo earn bonus experience and on-time streaks
  compound it, so the mid-career grind rewards exactly the freight dispatch
  recommends. Reputation now pays continuously through a dispatch trust
  bonus on company settlements. And personal money has real uses: pay for
  endorsement courses to unlock specialty freight before the carrier
  sponsors the training, or take a motel room for full-quality rest where
  truck parking is poor or full.
- **How to play now teaches the current game.** The in-game help reader
  gained a dedicated radio page (stations, hosts, signal ranges, and the
  streamer-safe rules), The goal and Deliveries pages explain earned dispatch
  freedom -- assigned loads and routes for new hires, declines, the level-8
  board unlock, F1 job details, and hours warnings -- and terminal, board,
  and early-career guidance text no longer tells assigned new hires to
  browse and pick freight.
- **The in-cab radio now has hosts, regional stations, and real signal
  ranges.** The Freight Fate Roadhouse and the Night Line each have a live
  host who breaks in between songs, and twelve fictional regional stations --
  country, classic rock, and blues and soul, each with newly composed songs --
  cover markets from Seattle to New Orleans. Stations behave like real FM
  signals: full and clear near their market, thinner with static crackle at
  the fringe, and gone past their range, with a spoken fallback to the
  Roadhouse when the signal drops. Three more Radio Browser-checked AFN 360
  channels (Global Fans, Global Holiday, and Mach 5) join the catalog for the
  real-streams opt-in.
- **Every career level band now has its own voice.** Levels 8 and 9 celebrate
  the load-choice unlock, and level 30 gets distinct top-of-the-ladder
  guidance for company drivers, leased-on owner-operators, and independent
  authority instead of repeating the level-25 text.
- **Haul length now progresses through the whole company arc.** Dispatch
  distance caps used to grow 500 miles per level and blow past every real
  U.S. route by level 12; they now grow gradually and top out at a real
  coast-to-coast run, so longer freight keeps unlocking into the late teens.
- **Old saves load cleanly on snapshot builds.** Careers saved by earlier
  stable and nightly builds (back through the version 4 schema) load with
  sensible defaults for everything added since -- business status, hours
  clock, duty log, tire wear -- and a save touched by a newer snapshot no
  longer crashes an older-schema load with unknown fields.
- **Freight and route freedom is now earned, not given.** Reaching level 8 is
  announced as the load-choice unlock, career guidance for levels 8 and 9
  celebrates picking your own freight, and a declined load stays declined:
  leaving the dispatch board and coming back re-offers it only after the
  fresh candidates run out. New company hires
  run the load and lane dispatch assigns: the dispatch board offers a single
  assignment with accept or decline, declining draws another load but costs
  reputation and comes from a small budget that refills at your next
  promotion, and departure runs dispatch's routing with no route menu. Load
  choice from the full board opens at level 8, and choosing your own routes
  is the owner-operator and own-authority reward, matching how forced
  dispatch works at real starter carriers.
- **New-career first day has a stronger handoff.** After choosing a start and
  home terminal, the terminal repeats a first-day briefing until the first
  dispatch is accepted. It names the carrier or owner-operator setup, the
  terminal, who pays equipment costs, and why the first dispatch matters.
- **Career terminals now name the next practical step.** After the first
  dispatch, the terminal adds a Career plan item and the dispatch board frames
  realistic next moves such as probation loads, dispatcher trust, cash
  reserves, owner-operator preparation, and direct-freight margins.
- **CB chatter sounds more like drivers talking.** Road radio warnings now use
  vague bear and work-zone enforcement chatter instead of pinpoint enforcement
  language.
- **Career progression now stretches to 30 levels.** The company-driver path
  grows through senior company ranks before a level-18 leased-on
  owner-operator gate, level-21 authority prep, level-25 own authority, and
  established independent owner-operator ranks through level 30.
- **Local turns now say and sound which way to steer.** Turn-by-turn cues on
  local streets say "Turn left onto" or "Turn right onto" instead of just
  "Turn onto", and each turn plays a soft chime from the side you are about
  to steer toward: a falling chime on the left, a rising chime on the right,
  and a single steady tone for continuing straight. Gentle bends where the
  street just changes name are spoken as "Continue onto" so a turn cue always
  means a real turn. Spoken GPS instructions with road names remain the main
  guidance.
- **The traffic light at the end of an exit ramp has its own sound.** A firm
  low two-tone cue means the light is red and you should brake; a bright go
  chime means green. You hear them when the light is first called out, when
  it changes ahead of you, and when a wait at the stop bar ends, alongside
  the spoken callouts.
- **Loaded runs now pull out of the gate onto real streets.** Leaving a
  shipper that has turn-level street data, the drive starts at the facility
  gate and follows the same named streets you arrived by, with every turn
  mirrored for the outbound direction, then merges up the on-ramp onto the
  highway. A save made on the outbound streets resumes there, and facilities
  without street data keep the usual highway start.
- **Dispatch rows now preview trailer fit and take-home.** Company drivers keep
  carrier-provided trailer support, while owner-operators and own-authority
  drivers hear when a load needs a missing trailer program or owned trailer.
  Rows also include a short estimated driver-pay or take-home preview before
  pay advances, using the current business status and trailer setup.
- **In-cab radio now follows the map.** Press M to toggle the radio, bracket
  keys to tune receivable stations, Y for spoken station status, and Tab for a
  Radio status screen. The checked-in catalog now includes regional public
  stations across the game map plus multiple AFN choices. Streamer-safe mode
  stays on by default, real public streams stay hidden unless explicitly opted
  in, and external streams fall back safely until live stream playback is added.
- **Highway exits now require a real setup.** X signals for the next announced
  exit instead of magically taking it. The GPS now stages the maneuver, asks for
  the right-side exit lane, checks that you are slowed to ramp speed at the
  gore, and explains missed exits when you are too fast or in the wrong lane.
- **Destination exits now follow the route setup.** The delivery ramp is taken
  when speed, lane setup, and route intent are valid. Lane-drift modes require
  a signal; with lane drift off, the GPS infers destination intent from the
  route unless you explicitly cancel the signal.
- **Merge and exit traffic now puts pressure on the maneuver.** The route can
  call out traffic building near exits, highway merges, construction tapers,
  and lead-traffic packs. Relaxed mode keeps those cues calmer, and missed
  exits now distinguish being boxed out by traffic from simply missing the lane.
- **Law enforcement now watches scales and unsafe trucks.** Open weigh stations
  warn you before the scale; blow past one at highway speed and a scale officer
  can light you up for a roadside enforcement stop. Severe visible truck damage
  can also trigger a safety stop when you pass active enforcement. Both
  stops use spoken warnings, X to signal, a full stop on the shoulder, an
  on-the-spot fine, and a reputation hit.
- **Running from a stop now escalates before it ends badly.** If you keep
  driving with lights behind you, the game gives a failure-to-stop warning and
  a final warning before spike strips. A felony stop now means a major fine,
  reputation damage, truck damage, processing time, and cancellation of the
  active loaded run, with a clear return to the terminal afterward.
- **Local approaches now name real streets almost everywhere.** The road
  snap used to let a nameless service way beat a named street a few meters
  farther, so 39 percent of deadheads and facility approaches said "unnamed
  public road." The snap now prefers the nearest named road inside the same
  search radius, and the regenerated data names a real street for every
  road-snapped target -- "Deadhead 2.1 miles on North Meridian Street"
  instead of an unnamed mystery road.
- **Tuning the radio no longer says the station name twice.** "Tuned to"
  announcements already name the station, so the station line that follows
  now skips the repeat, and the doubled period between them is gone.
- **Route cues no longer say "In 0 miles."** When you are already on top of
  a cue, the redundant advance warning is skipped; the arrival announcement
  that follows carries the news. State-line and hours-of-service readouts
  also gained a missing sentence break, so the duty window no longer runs
  into the rest-stop advice.
- **Construction-zone warnings give you room to react.** The warning now comes
  earlier at highway speed and starts with "Brake now!", and troopers wait a
  little longer inside the zone before clocking you, so normal braking from the
  warning is fair and the emergency brake can still save a late reaction.
- **Route chatter no longer stacks into a wall of speech.** Low-priority road
  chatter now has a short spacing window and keeps only the newest pending cue,
  so weather, toll, state-line, CB, and similar ambient lines do not all pile up
  in one burst. Safety cues and actionable GPS distances still speak immediately.
- **More freight destinations use real map-backed endpoints.** The offline map
  data now includes source-backed freight facility endpoints where local OSM
  data supports them, while facilities without a confident match stay clearly
  marked as representative fallbacks. The game does not claim gates, yards,
  docks, or truck-legal turn-by-turn facility routing from this layer yet.
- **Some freight facility approaches now use real local road turns.** A bounded
  Midwest map pass snaps 71 high-confidence source-backed freight facilities to
  public-road context, with 6 long enough to use checked-in turn-level approach
  geometry. Other facilities keep explicit fallback road context.
- **Own-authority drivers can now buy trailers.** The garage sells dry van,
  reefer, flatbed, and bulk trailers after own authority is active. Direct
  freight rows say when an owned trailer fits, and settlement uses an
  owned-trailer reserve instead of the trailer-program charge.
- **Authority prep now leads to a first own-authority mode.** Qualified
  owner-operators can pay the startup cost from Business status, unlock direct
  freight on the dispatch board, and see insurance, compliance, trailer, truck,
  and factoring costs in settlement without turning the game into a compliance
  simulator.
- **Trailer fit now matters for owner-operators.** Company drivers still use
  carrier-provided trailers, while leased-on owner-operators start with dry van
  access and can add reefer, flatbed, or bulk trailer programs from the garage.
  Dispatch now tells you when specialty cargo needs a trailer program.
- **Carrier choice now shapes the dispatch board.** Starter carriers still stay
  grounded, but they now change how often you see short, regional, long-haul,
  grain or bulk, and high-value jobs. Some training loads also have more
  forgiving deadlines.
- **Owner-operators now have an authority prep milestone.** Qualified
  level-21 owner-operators can set aside a reserve from Business status before
  taking the later own-authority step.
- **New careers now offer grounded start choices.** Pick from several
  fictional company-driver carriers with assigned equipment and modest wage or
  freight tradeoffs, or choose a higher-risk owner-operator start with owned
  starter equipment and operating costs active from day one.
- **Busy corridors now feel busier beyond rush hour.** Random road-hazard checks
  now use corridor busyness: dense metro/checkpoint interstates check sooner,
  while sparse open-country corridors leave more breathing room. Relaxed mode
  still keeps random hazards rare overall.
- **Construction zones now stage the slowdown.** Work zones add a merge/flagger
  taper before the barrels, with spoken guidance to slow first for the taper and
  then for the lower work-zone limit. The taper shows up in speed-limit and
  upcoming-road readouts, while ticket enforcement still waits until the main
  work zone after the fair braking window.
- **Loaded trucks pull away more like loaded trucks.** Low-speed drive force now
  ramps in from a stop instead of hitting the full rolling traction cap
  immediately, and the automatic holds the first few gears a little longer, so a
  heavy tractor-trailer launch has weight without losing highway acceleration.
- **Career progression now has a 30-level business arc.** New drivers start
  with fictional carrier Northstar Freight Lines, move through company-driver
  and owner-operator preparation ranks, and unlock the leased-on
  owner-operator buy-in later in the ladder instead of jumping there at level 5.
- **Company-driver equipment now reads like company equipment.** New drivers
  use an assigned carrier tractor with carrier-paid fuel and routine repairs;
  buying, switching, and upgrading owned tractors waits until the leased-on
  owner-operator path.
- **City service drives use sourced local service names across the map.** The
  garage, freight/logistics office, and truck dealer drives now prefer
  checked-in source-backed local service data for every supported city, with
  representative fallbacks only where no suitable sourced role is available.
- **Local service and facility drives use checked-in road context.** GPS and
  route summaries now prefer source-backed nearby road names for city-service
  drives and pickup/delivery facility approaches, while simplified fallbacks
  remain clearly marked in the data.
- **Some city service drives now have real local turns.** Where local OSM data
  supports it, service drives can use checked-in street-by-street approach
  geometry with spoken local turn cues. Other services and representative
  facility approaches still fall back to simpler road context.
- **Rush hour makes traffic feel busier.** Starting a trip during morning or
  afternoon commute windows now raises modeled traffic density, especially near
  metro/checkpoint corridors, and can slow lead traffic with commuter or merge
  callouts.
- **Loading, unloading, and pulling in now take a beat.** Pickup loading and
  destination unloading now give a short spoken wait and advance the in-game
  clock as on-duty work. Pulling into pickup gates, destination gates, and route
  stops also gives the first menu option a moment to speak, so holding Down
  Arrow to brake no longer skips past it.
- **Coffee helps alertness a little longer.** Food-and-coffee stops now ease
  fatigue more than before, but they still do not satisfy the 30-minute break
  rule and remain much weaker than a full break or proper sleep.
- **In-cab logbook.** The game now records a rolling Record of Duty Status as
  you drive, fuel, repair, load, take breaks, sleep, or get placed out of
  service. You can review it from the terminal or the driving status menu, and
  traffic stops now read the recent logbook entries instead of only pretending
  to check them.
- **CB radio enforcement chatter.** CB chatter can now warn you a few miles
  before drivers are talking about a bear ahead or enforcement near a work
  zone, with a radio squelch cue and a clear "check your speed" line. The cue
  stays secondary to hazards and construction warnings, and the U upcoming key
  can review that chatter alongside stops, speed zones, and exits.

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
  out of the next delivery settlement. The advance is offered only when cash is
  nearly gone and is capped, so it stays a recovery line rather than free
  money. A negative balance is no longer a dead end.
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
