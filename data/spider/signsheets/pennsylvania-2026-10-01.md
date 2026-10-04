# Pennsylvania attractions, both directions -- draft 2026-10-01

DRAFT for owner review. Nothing here is approved.

15 real attractions, 69 signs.

Each is signed in every direction of travel where a leg passes it, except
where a note says why not. Every `leg:` is written the way the driver
reads the sign and `at_mi` counts from that end; `tools/bake_billboards.py`
mirrors the milepost onto a leg stored the other way round and records which
way the billboard faces. One block, Flight 93, is a respectful `landmark`
callout heard both ways, not a billboard.

Billboard law: Pennsylvania's Outdoor Advertising Control Act of 1971 (36
P.S. 2718.101 et seq., administered by PennDOT; 67 Pa. Code chapter 445)
permits off-premise boards beside Interstates and primaries on private land
in commercial and industrial areas, with a PennDOT permit, and bars new
ones within 500 feet of an interchange or rest area. The Turnpike is part
of that system and boards stand along it. US 15 south of Harrisburg is the
Journey Through Hallowed Ground national scenic byway (no new boards under
23 U.S.C. 131(s)) and carries nothing here, as on the northeast sheet.

No leg runs I-80 across Pennsylvania today. The Turnpike (I-76), I-78,
I-81, I-476, I-79 and the legs into Altoona, State College, Williamsport,
Scranton, Carlisle and Erie are what the state's roads hold.

Mileposts come from projecting each attraction's turnoff onto the legs'
dense route geometry and from the legs' interchange lists. "Next exit"
signs stand between the attraction's exit and the exit before it; "ahead"
signs about eight to fifteen miles out; a sign naming a town stands on the
legs arriving there. Each sits at least 2.2 miles from every other callout
heard in the same direction, including the other east-south sheets.

## Valley Forge National Historical Park, King of Prussia (Turnpike Exit 326)

Where the Continental Army spent the winter of 1777 to 1778; the visitor
center at 1000 North Outer Line Drive is open daily, 9 to 5, and the park's
own directions say Turnpike Exit 326 (nps.gov/vafo, Operating Hours; Visitor
Center). The legs list the neighbouring I-76 exit 327 at the same spot.

### Valley Forge National Historical Park (eastbound)
- treatment: billboard
- leg: harrisburg_pa_us -> philadelphia_pa_us
- at_mi: 78.0
- spoken: Billboard: Valley Forge National Historical Park, ahead. Washington's army spent the winter of seventeen seventy-seven here. Your heater works. Be grateful.

### Valley Forge National Historical Park (westbound)
- treatment: billboard
- leg: philadelphia_pa_us -> harrisburg_pa_us
- at_mi: 4.5
- spoken: Billboard: Valley Forge National Historical Park, ahead. Washington's army spent the winter of seventeen seventy-seven here. Your heater works. Be grateful.

### Valley Forge National Historical Park (westbound)
- treatment: billboard
- leg: philadelphia_pa_us -> pittsburgh_pa_us
- at_mi: 8.3
- spoken: Billboard: Valley Forge National Historical Park, ahead. Washington's army spent the winter of seventeen seventy-seven here. Your heater works. Be grateful.

### Valley Forge National Historical Park (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> philadelphia_pa_us
- at_mi: 276.7
- spoken: Billboard: Valley Forge National Historical Park, ahead. Washington's army spent the winter of seventeen seventy-seven here. Your heater works. Be grateful.

## Fallingwater, Mill Run (Turnpike Exit 91, Donegal)

Frank Lloyd Wright's house built over the falls of Bear Run, 1491 Mill Run
Road; its own directions: Turnpike Exit 91 (Donegal), Route 31 east two
miles, Route 381 south about seventeen, nineteen miles in all. Open for its
63rd tour season in 2026 (fallingwater.org, Driving Directions).

### Fallingwater (westbound)
- treatment: billboard
- leg: baltimore_md_us -> pittsburgh_pa_us
- at_mi: 188.5
- spoken: Billboard: Fallingwater, ahead, south of the Donegal exit. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted.

### Fallingwater (westbound)
- treatment: billboard
- leg: carlisle_pa_us -> pittsburgh_pa_us
- at_mi: 138.0
- spoken: Billboard: Fallingwater, next exit, nineteen miles south. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted.

### Fallingwater (westbound)
- treatment: billboard
- leg: hagerstown_md_us -> pittsburgh_pa_us
- at_mi: 125.9
- spoken: Billboard: Fallingwater, next exit, nineteen miles south. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted.

### Fallingwater (westbound)
- treatment: billboard
- leg: harrisburg_pa_us -> pittsburgh_pa_us
- at_mi: 146.0
- spoken: Billboard: Fallingwater, ahead, south of the Donegal exit. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted.

### Fallingwater (westbound)
- treatment: billboard
- leg: philadelphia_pa_us -> pittsburgh_pa_us
- at_mi: 246.4
- spoken: Billboard: Fallingwater, ahead, south of the Donegal exit. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted.

### Fallingwater (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> baltimore_md_us
- at_mi: 46.4
- spoken: Billboard: Fallingwater, next exit, nineteen miles south. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted.

### Fallingwater (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> carlisle_pa_us
- at_mi: 46.6
- spoken: Billboard: Fallingwater, next exit, nineteen miles south. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted.

### Fallingwater (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> hagerstown_md_us
- at_mi: 46.7
- spoken: Billboard: Fallingwater, next exit, nineteen miles south. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted.

### Fallingwater (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> harrisburg_pa_us
- at_mi: 39.0
- spoken: Billboard: Fallingwater, ahead, south of the Donegal exit. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted.

### Fallingwater (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> philadelphia_pa_us
- at_mi: 46.5
- spoken: Billboard: Fallingwater, next exit, nineteen miles south. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted.

## Flight 93 National Memorial, Stoystown (Turnpike Exit 110, Somerset)

The national memorial to the forty passengers and crew of United Flight 93,
September 11, 2001, at 6424 Lincoln Highway; from Turnpike Exit 110, Route
281 and US 219 north, then US 30 east, about twenty miles (nps.gov/flni,
Directions). No joke belongs here, so this is a `landmark` callout in the
register of the existing Appomattox and Edmund Pettus Bridge callouts,
heard both ways near Exit 110. The owner may prefer to leave it out.

### Flight Ninety-Three National Memorial
- treatment: landmark
- leg: baltimore_md_us -> pittsburgh_pa_us
- at_mi: 178.8
- facing: both
- spoken: You are passing near Shanksville, where the Flight Ninety-Three National Memorial honors the forty passengers and crew of September eleventh, two thousand one.

### Flight Ninety-Three National Memorial
- treatment: landmark
- leg: harrisburg_pa_us -> pittsburgh_pa_us
- at_mi: 138.2
- facing: both
- spoken: You are passing near Shanksville, where the Flight Ninety-Three National Memorial honors the forty passengers and crew of September eleventh, two thousand one.

### Flight Ninety-Three National Memorial
- treatment: landmark
- leg: philadelphia_pa_us -> pittsburgh_pa_us
- at_mi: 237.5
- facing: both
- spoken: You are passing near Shanksville, where the Flight Ninety-Three National Memorial honors the forty passengers and crew of September eleventh, two thousand one.

### Flight Ninety-Three National Memorial
- treatment: landmark
- leg: pittsburgh_pa_us -> carlisle_pa_us
- at_mi: 68.8
- facing: both
- spoken: You are passing near Shanksville, where the Flight Ninety-Three National Memorial honors the forty passengers and crew of September eleventh, two thousand one.

### Flight Ninety-Three National Memorial
- treatment: landmark
- leg: pittsburgh_pa_us -> hagerstown_md_us
- at_mi: 67.4
- facing: both
- spoken: You are passing near Shanksville, where the Flight Ninety-Three National Memorial honors the forty passengers and crew of September eleventh, two thousand one.

## The Bedford Coffee Pot, Bedford (Turnpike Exit 146)

The Koontz Coffee Pot, eighteen feet tall, built in 1927 by gas station
owner David Koontz on the Lincoln Highway; it served as a restaurant, then a
bar and a bus stop, never a coffee shop; saved and moved to the Bedford
County Fairgrounds entrance, 108 Telegraph Road, in 2004
(uncoveringpa.com; Sinclair's Amazing America, 2026; roadsideamerica.com).
About two miles from Turnpike Exit 146.

### The Bedford Coffee Pot (westbound)
- treatment: billboard
- leg: baltimore_md_us -> pittsburgh_pa_us
- at_mi: 131.3
- spoken: Billboard: The Bedford Coffee Pot, ahead. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop.

### The Bedford Coffee Pot (westbound)
- treatment: billboard
- leg: carlisle_pa_us -> pittsburgh_pa_us
- at_mi: 73.1
- spoken: Billboard: The Bedford Coffee Pot, ahead. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop.

### The Bedford Coffee Pot (westbound)
- treatment: billboard
- leg: hagerstown_md_us -> pittsburgh_pa_us
- at_mi: 60.9
- spoken: Billboard: The Bedford Coffee Pot, ahead. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop.

### The Bedford Coffee Pot (westbound)
- treatment: billboard
- leg: harrisburg_pa_us -> pittsburgh_pa_us
- at_mi: 94.1
- spoken: Billboard: The Bedford Coffee Pot, ahead. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop.

### The Bedford Coffee Pot (westbound)
- treatment: billboard
- leg: philadelphia_pa_us -> pittsburgh_pa_us
- at_mi: 199.5
- spoken: Billboard: The Bedford Coffee Pot, next exit. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop.

### The Bedford Coffee Pot (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> baltimore_md_us
- at_mi: 93.9
- spoken: Billboard: The Bedford Coffee Pot, ahead. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop.

### The Bedford Coffee Pot (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> carlisle_pa_us
- at_mi: 92.3
- spoken: Billboard: The Bedford Coffee Pot, ahead. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop.

### The Bedford Coffee Pot (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> hagerstown_md_us
- at_mi: 94.4
- spoken: Billboard: The Bedford Coffee Pot, ahead. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop.

### The Bedford Coffee Pot (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> harrisburg_pa_us
- at_mi: 90.9
- spoken: Billboard: The Bedford Coffee Pot, ahead. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop.

### The Bedford Coffee Pot (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> philadelphia_pa_us
- at_mi: 94.0
- spoken: Billboard: The Bedford Coffee Pot, ahead. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop.

## The U.S. Army Heritage and Education Center, Carlisle

950 Soldiers Drive, Carlisle, beside I-81 Exit 52: free admission, open
daily, with the outdoor Army Heritage Trail of vehicles, tanks and
reconstructed trenches open dawn to dusk (ahec.armywarcollege.edu, Visitor
Guide 2026; uncoveringpa.com). Signed "ahead in Carlisle" on I-81 and the
Turnpike; the US 15 leg from Washington is a scenic byway and unsigned.

### The Army Heritage and Education Center (northbound)
- treatment: billboard
- leg: hagerstown_md_us -> carlisle_pa_us
- at_mi: 46.8
- spoken: Billboard: The Army Heritage and Education Center, ahead in Carlisle. Free admission, and an outdoor trail of real tanks and trenches. Those tanks are parked for good.

### The Army Heritage and Education Center (northbound)
- treatment: billboard
- leg: hagerstown_md_us -> harrisburg_pa_us
- at_mi: 46.8
- spoken: Billboard: The Army Heritage and Education Center, ahead in Carlisle. Free admission, and an outdoor trail of real tanks and trenches. Those tanks are parked for good.

### The Army Heritage and Education Center (westbound)
- treatment: billboard
- leg: harrisburg_pa_us -> carlisle_pa_us
- at_mi: 10.2
- spoken: Billboard: The Army Heritage and Education Center, ahead in Carlisle. Free admission, and an outdoor trail of real tanks and trenches. Those tanks are parked for good.

### The Army Heritage and Education Center (westbound)
- treatment: billboard
- leg: harrisburg_pa_us -> hagerstown_md_us
- at_mi: 10.2
- spoken: Billboard: The Army Heritage and Education Center, ahead in Carlisle. Free admission, and an outdoor trail of real tanks and trenches. Those tanks are parked for good.

### The Army Heritage and Education Center (westbound)
- treatment: billboard
- leg: harrisburg_pa_us -> pittsburgh_pa_us
- at_mi: 9.7
- spoken: Billboard: The Army Heritage and Education Center, ahead in Carlisle. Free admission, and an outdoor trail of real tanks and trenches. Those tanks are parked for good.

### The Army Heritage and Education Center (westbound)
- treatment: billboard
- leg: philadelphia_pa_us -> pittsburgh_pa_us
- at_mi: 107.7
- spoken: Billboard: The Army Heritage and Education Center, ahead in Carlisle. Free admission, and an outdoor trail of real tanks and trenches. Those tanks are parked for good.

### The Army Heritage and Education Center (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> carlisle_pa_us
- at_mi: 175.9
- spoken: Billboard: The Army Heritage and Education Center, ahead in Carlisle. Free admission, and an outdoor trail of real tanks and trenches. Those tanks are parked for good.

### The Army Heritage and Education Center (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> harrisburg_pa_us
- at_mi: 175.3
- spoken: Billboard: The Army Heritage and Education Center, ahead in Carlisle. Free admission, and an outdoor trail of real tanks and trenches. Those tanks are parked for good.

### The Army Heritage and Education Center (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> philadelphia_pa_us
- at_mi: 176.0
- spoken: Billboard: The Army Heritage and Education Center, ahead in Carlisle. Free admission, and an outdoor trail of real tanks and trenches. Those tanks are parked for good.

## Hawk Mountain Sanctuary, Kempton (I-78 Exit 29, Hamburg)

The world's first refuge for birds of prey, founded in 1934 on the
Kittatinny Ridge; about 18,000 raptors pass its lookout between mid-August
and mid-December. From I-78 at Hamburg: Route 61 north 4.5 miles, Route 895
east to Drehersville, then two miles up Hawk Mountain Road
(worldatlas.com; advcollective.com; Pennsylvania Game Commission).

### Hawk Mountain Sanctuary (westbound)
- treatment: billboard
- leg: allentown_pa_us -> harrisburg_pa_us
- at_mi: 17.8
- spoken: Billboard: Hawk Mountain Sanctuary, ahead, north of Hamburg. Each fall about eighteen thousand hawks pass its lookout. Not one of them stops for fuel.

### Hawk Mountain Sanctuary (eastbound)
- treatment: billboard
- leg: harrisburg_pa_us -> allentown_pa_us
- at_mi: 44.3
- spoken: Billboard: Hawk Mountain Sanctuary, ahead, north of Hamburg. Each fall about eighteen thousand hawks pass its lookout. Not one of them stops for fuel.

## The Crayola Experience, Easton (I-78 Exit 75)

30 Centre Square, downtown Easton, open daily: more than twenty-five
attractions, among them Melt and Mold, where a crayon is melted into a new
shape (crayolaexperience.com/easton). Easton is the first Pennsylvania town
on I-78 from New Jersey, Exit 75 by Route 611.

### The Crayola Experience (eastbound)
- treatment: billboard
- leg: allentown_pa_us -> bridgeport_ct_us
- at_mi: 8.9
- spoken: Billboard: The Crayola Experience, ahead in Easton. Twenty-five rooms of crayons, and you can melt one into a new shape. Coloring outside the lines is encouraged.

### The Crayola Experience (eastbound)
- treatment: billboard
- leg: allentown_pa_us -> new_york_ny_us
- at_mi: 9.9
- spoken: Billboard: The Crayola Experience, ahead in Easton. Twenty-five rooms of crayons, and you can melt one into a new shape. Coloring outside the lines is encouraged.

### The Crayola Experience (eastbound)
- treatment: billboard
- leg: allentown_pa_us -> newark_nj_us
- at_mi: 11.7
- spoken: Billboard: The Crayola Experience, ahead in Easton. Twenty-five rooms of crayons, and you can melt one into a new shape. Coloring outside the lines is encouraged.

### The Crayola Experience (westbound)
- treatment: billboard
- leg: bridgeport_ct_us -> allentown_pa_us
- at_mi: 124.6
- spoken: Billboard: The Crayola Experience, ahead in Easton. Twenty-five rooms of crayons, and you can melt one into a new shape. Coloring outside the lines is encouraged.

### The Crayola Experience (westbound)
- treatment: billboard
- leg: new_york_ny_us -> allentown_pa_us
- at_mi: 77.3
- spoken: Billboard: The Crayola Experience, ahead in Easton. Twenty-five rooms of crayons, and you can melt one into a new shape. Coloring outside the lines is encouraged.

### The Crayola Experience (westbound)
- treatment: billboard
- leg: newark_nj_us -> allentown_pa_us
- at_mi: 50.1
- spoken: Billboard: The Crayola Experience, ahead in Easton. Twenty-five rooms of crayons, and you can melt one into a new shape. Coloring outside the lines is encouraged.

## Jim Thorpe (I-476 Exit 74, Mahoning Valley)

The old coal town of Mauch Chunk, which took the Olympic champion's name in
1954 when his widow offered his remains to a town that would honor him; he
had never set foot there, and he is buried in a mausoleum at the edge of
town (nps.gov, Mauch Chunk Historic District; Philadelphia Inquirer, 2009;
Britannica). About six miles from the Northeast Extension's Mahoning Valley
exit.

### Jim Thorpe (southbound)
- treatment: billboard
- leg: scranton_pa_us -> allentown_pa_us
- at_mi: 48.5
- spoken: Billboard: Jim Thorpe, next exit. The Olympic champion never set foot in this town. It took his name in nineteen fifty-four, and he rests there now.

## Steamtown National Historic Site, Scranton

The National Park Service's railroad museum in the old Lackawanna yards,
with a working roundhouse and its own Big Boy, No. 4012; admission is free
(scrantonpa.gov and WVIA, on the June 2026 Big Boy reunion). Scranton is
also the setting of the television comedy The Office, whose paper company is
fictional. Signed on the legs arriving in Scranton.

### Steamtown National Historic Site (eastbound)
- treatment: billboard
- leg: allentown_pa_us -> scranton_pa_us
- at_mi: 61.8
- spoken: Billboard: Steamtown National Historic Site, ahead in Scranton. Real steam locomotives in a working roundhouse, and admission is free. The paper company is a different show.

### Steamtown National Historic Site (southbound)
- treatment: billboard
- leg: binghamton_ny_us -> scranton_pa_us
- at_mi: 50.0
- spoken: Billboard: Steamtown National Historic Site, ahead in Scranton. Real steam locomotives in a working roundhouse, and admission is free. The paper company is a different show.

### Steamtown National Historic Site (northbound)
- treatment: billboard
- leg: harrisburg_pa_us -> scranton_pa_us
- at_mi: 116.7
- spoken: Billboard: Steamtown National Historic Site, ahead in Scranton. Real steam locomotives in a working roundhouse, and admission is free. The paper company is a different show.

## Pioneer Tunnel Coal Mine, Ashland (I-81 at Frackville)

An open mine car rides 1,800 feet into Mahanoy Mountain through a real
anthracite mine on a 35-minute tour, April through October, with a steam
lokie ride outside (discovernepa.com; uncoveringpa.com). Ashland is about
six miles north of I-81 at Frackville by Route 61, so the copy reads
"ahead in Ashland".

### Pioneer Tunnel Coal Mine (northbound)
- treatment: billboard
- leg: harrisburg_pa_us -> scranton_pa_us
- at_mi: 48.8
- spoken: Billboard: Pioneer Tunnel Coal Mine, ahead in Ashland. Ride an open mine car eighteen hundred feet into a real coal mine. Your cab has more legroom.

### Pioneer Tunnel Coal Mine (southbound)
- treatment: billboard
- leg: scranton_pa_us -> harrisburg_pa_us
- at_mi: 49.9
- spoken: Billboard: Pioneer Tunnel Coal Mine, ahead in Ashland. Ride an open mine car eighteen hundred feet into a real coal mine. Your cab has more legroom.

## The Pennsylvania Trolley Museum, Washington (I-79 Exit 41)

1 Electric Way, Washington: almost fifty restored trolleys, and admission
includes a four-mile ride; I-79 Exit 41 (Race Track Road), then three miles
on signs. Open Thursday to Sunday in the fall, Tuesday to Sunday in summer
(pa-trolley.org 2026 calendar; visitpittsburgh.com).

### The Pennsylvania Trolley Museum (northbound)
- treatment: billboard
- leg: charleston_wv_us -> pittsburgh_pa_us
- at_mi: 193.9
- spoken: Billboard: The Pennsylvania Trolley Museum, ahead near Washington. Almost fifty trolleys, and admission includes a four-mile ride. The motorman never once has to steer.

### The Pennsylvania Trolley Museum (northbound)
- treatment: billboard
- leg: morgantown_wv_us -> pittsburgh_pa_us
- at_mi: 40.9
- spoken: Billboard: The Pennsylvania Trolley Museum, ahead near Washington. Almost fifty trolleys, and admission includes a four-mile ride. The motorman never once has to steer.

### The Pennsylvania Trolley Museum (southbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> charleston_wv_us
- at_mi: 14.7
- spoken: Billboard: The Pennsylvania Trolley Museum, ahead near Washington. Almost fifty trolleys, and admission includes a four-mile ride. The motorman never once has to steer.

### The Pennsylvania Trolley Museum (southbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> morgantown_wv_us
- at_mi: 14.7
- spoken: Billboard: The Pennsylvania Trolley Museum, ahead near Washington. Almost fifty trolleys, and admission includes a four-mile ride. The motorman never once has to steer.

### The Pennsylvania Trolley Museum (southbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> wheeling_wv_us
- at_mi: 14.6
- spoken: Billboard: The Pennsylvania Trolley Museum, ahead near Washington. Almost fifty trolleys, and admission includes a four-mile ride. The motorman never once has to steer.

### The Pennsylvania Trolley Museum (eastbound)
- treatment: billboard
- leg: wheeling_wv_us -> pittsburgh_pa_us
- at_mi: 24.0
- spoken: Billboard: The Pennsylvania Trolley Museum, ahead near Washington. Almost fifty trolleys, and admission includes a four-mile ride. The motorman never once has to steer.

## Horseshoe Curve National Historic Landmark, Altoona

Where the old Pennsylvania Railroad main line climbs the Alleghenies by
bending back on itself, west of Altoona; the visitor center, run by the
Railroaders Memorial Museum, is open April 1 to December 20, Wednesday to
Sunday (Wikipedia; pabucketlist.com; railroadcity.org). Signed on the legs
arriving in Altoona.

### Horseshoe Curve (eastbound)
- treatment: billboard
- leg: pittsburgh_pa_us -> altoona_pa_us
- at_mi: 87.6
- spoken: Billboard: Horseshoe Curve, ahead outside Altoona. The main line climbs the Alleghenies by bending back on itself. The trains do the hard part. You watch.

### Horseshoe Curve (southbound)
- treatment: billboard
- leg: state_college_pa_us -> altoona_pa_us
- at_mi: 30.2
- spoken: Billboard: Horseshoe Curve, ahead outside Altoona. The main line climbs the Alleghenies by bending back on itself. The trains do the hard part. You watch.

## Penn State Berkey Creamery, State College

Penn State's dairy store on campus. Ben Cohen and Jerry Greenfield learned
ice cream making in 1978 from the university's five-dollar correspondence
course, which they split, the forerunner of today's Ice Cream Short Course
(CNBC, 2019; Wikipedia; foodscience.psu.edu). Signed on the legs arriving
in State College; the US 322 leg from Harrisburg is unsigned because its
route points and geometry disagree near State College.

### The Berkey Creamery (eastbound)
- treatment: billboard
- leg: altoona_pa_us -> state_college_pa_us
- at_mi: 31.0
- spoken: Billboard: Penn State's Berkey Creamery, ahead in State College. Ben and Jerry learned ice cream here by mail, in a course they split for five dollars.

### The Berkey Creamery (southbound)
- treatment: billboard
- leg: williamsport_pa_us -> state_college_pa_us
- at_mi: 50.9
- spoken: Billboard: Penn State's Berkey Creamery, ahead in State College. Ben and Jerry learned ice cream here by mail, in a course they split for five dollars.

## The World of Little League Museum, South Williamsport

525 Montgomery Pike (US 15), South Williamsport, beside the stadiums of the
Little League World Series, played every August by players twelve and
under; open daily in summer, with fall and winter hours
(littleleague.org/museum). Signed on the legs arriving in Williamsport.

### The World of Little League Museum (westbound)
- treatment: billboard
- leg: binghamton_ny_us -> williamsport_pa_us
- at_mi: 114.0
- spoken: Billboard: The World of Little League Museum, ahead in South Williamsport. Every August the world watches twelve-year-olds play baseball here. Some throw harder than you.

### The World of Little League Museum (westbound)
- treatment: billboard
- leg: harrisburg_pa_us -> williamsport_pa_us
- at_mi: 86.8
- spoken: Billboard: The World of Little League Museum, ahead in South Williamsport. Every August the world watches twelve-year-olds play baseball here. Some throw harder than you.

### The World of Little League Museum (eastbound)
- treatment: billboard
- leg: state_college_pa_us -> williamsport_pa_us
- at_mi: 52.5
- spoken: Billboard: The World of Little League Museum, ahead in South Williamsport. Every August the world watches twelve-year-olds play baseball here. Some throw harder than you.

## Presque Isle State Park, Erie

A sandy peninsula on Lake Erie four miles west of the city, with seven miles
of beach, the most visited state park in Pennsylvania and billed as its
only seashore; open every day (Wikipedia; islands.com). Signed on the legs
arriving in Erie.

### Presque Isle State Park (westbound)
- treatment: billboard
- leg: buffalo_ny_us -> erie_pa_us
- at_mi: 84.0
- spoken: Billboard: Presque Isle State Park, ahead in Erie. Seven miles of sand beach on Lake Erie. Pennsylvania has a seashore, and this is the whole of it.

### Presque Isle State Park (eastbound)
- treatment: billboard
- leg: cleveland_oh_us -> erie_pa_us
- at_mi: 92.0
- spoken: Billboard: Presque Isle State Park, ahead in Erie. Seven miles of sand beach on Lake Erie. Pennsylvania has a seashore, and this is the whole of it.

### Presque Isle State Park (westbound)
- treatment: billboard
- leg: jamestown_ny_us -> erie_pa_us
- at_mi: 38.0
- spoken: Billboard: Presque Isle State Park, ahead in Erie. Seven miles of sand beach on Lake Erie. Pennsylvania has a seashore, and this is the whole of it.

### Presque Isle State Park (northbound)
- treatment: billboard
- leg: meadville_pa_us -> erie_pa_us
- at_mi: 32.9
- spoken: Billboard: Presque Isle State Park, ahead in Erie. Seven miles of sand beach on Lake Erie. Pennsylvania has a seashore, and this is the whole of it.

## Notes for the owner

See `REVIEW-east-south-2026-10-01.md` for the decisions, the law findings
and the list of new lines.
