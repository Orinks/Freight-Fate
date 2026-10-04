
# Minnesota and Wisconsin attractions, both directions -- 2026-09-30

Draft for the owner. Thirty-two real roadside attractions, twenty in
Minnesota and twelve in Wisconsin, each signed in every direction of travel
where a leg passes it. Every `leg:`
is written the way the driver reads the sign and `at_mi` counts from that
end; `tools/bake_billboards.py` mirrors the milepost onto a leg stored the
other way round and records which way the billboard faces.

Both states allow commercial billboards along their Interstates and federal
aid highways under a state permit: Minnesota under its Outdoor Advertising
Control Act (Minnesota Statutes chapter 173, annual MnDOT permit,
https://www.dot.state.mn.us/roadsides/billboards/index.html), Wisconsin under
Wisconsin Statutes section 84.30 (WisDOT outdoor advertising permit,
https://docs.legis.wisconsin.gov/statutes/statutes/84/30).

Mileposts come from the legs' interchange lists where the road has one, and
from their checkpoints and landmarks on the US-highway legs, which list no
exits. "Next exit" signs stand between the attraction's exit and the exit
before it; "ahead" signs about eight to fifteen miles out, or closer where
the callouts leave no room. Each sits at least 2.2 miles from every other
callout heard in the same direction.

# Minnesota

## The Runestone Museum, Alexandria (I-94 Exit 103)

The Kensington Runestone, a slab carved in Norse runes and dated 1362 in its
own inscription, found by farmer Olof Ohman in 1898 near Kensington; most
scholars take it for a nineteenth-century carving and the argument has never
stopped. 206 Broadway, Alexandria, three miles north of I-94 Exit 103 on
Minnesota 29, with Big Ole, the twenty-eight-foot Viking statue, outside
(runestonemuseum.org; explorealex.com). Eastbound on the Fargo to
Minneapolis leg, the Chippewa River callout sits at Exit 100, two miles
before Exit 103, so that sign reads "ahead".

### Runestone Museum (westbound)
- treatment: billboard
- leg: st_cloud_mn_us -> fargo_nd_us
- at_mi: 64.5
- spoken: Billboard: The Runestone Museum, next exit in Alexandria. A farmer found the stone in eighteen ninety-eight, and people still argue. The stone is not saying.

### Runestone Museum (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> st_cloud_mn_us
- at_mi: 103.2
- spoken: Billboard: The Runestone Museum, next exit in Alexandria. A farmer found the stone in eighteen ninety-eight, and people still argue. The stone is not saying.

### Runestone Museum (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> minneapolis_mn_us
- at_mi: 95.0
- spoken: Billboard: The Runestone Museum, ahead in Alexandria. A farmer found the stone in eighteen ninety-eight, and people still argue. The stone is not saying.

### Runestone Museum (westbound)
- treatment: billboard
- leg: minneapolis_mn_us -> fargo_nd_us
- at_mi: 128.0
- spoken: Billboard: The Runestone Museum, next exit in Alexandria. A farmer found the stone in eighteen ninety-eight, and people still argue. The stone is not saying.

## Tobies, Hinckley (I-35 Exit 183)

Tobies Restaurant and Bakery, 404 Fire Monument Road at I-35 Exit 183, open
since 1948 and known for its cinnamon rolls; it sits about halfway between
the Twin Cities and Duluth (Minnesota Monthly; Unearth the Voyage). The
Hinckley Fire Museum already has a callout on this leg at the same exit, so
the signs stand 2.2 miles clear of it. Northbound the gap between Exits 180
and 183 holds the museum and the village of Hinckley, so that sign reads
"ahead".

### Tobies (southbound)
- treatment: billboard
- leg: duluth_mn_us -> minneapolis_mn_us
- at_mi: 71.0
- spoken: Billboard: Tobies bakery, next exit in Hinckley. Halfway between the Twin Cities and Duluth since nineteen forty-eight. That is a long time to be halfway.

### Tobies (northbound)
- treatment: billboard
- leg: minneapolis_mn_us -> duluth_mn_us
- at_mi: 68.0
- spoken: Billboard: Tobies bakery, ahead in Hinckley. Halfway between the Twin Cities and Duluth since nineteen forty-eight. That is a long time to be halfway.

## Northfield History Center (I-35 Exit 69, then seven miles east)

The museum at 408 Division Street, Northfield, in the Scriver Building, which
held the First National Bank the James-Younger gang tried to rob on
September 7, 1876; the cashier refused to open the safe and the townspeople
drove the gang out (northfieldhistory.org; KYMN, September 3, 2026).
Northfield is seven miles east of I-35 Exit 69 on Minnesota 19
(carleton.edu directions).

### Northfield History Center (northbound)
- treatment: billboard
- leg: owatonna_mn_us -> minneapolis_mn_us
- at_mi: 27.0
- spoken: Billboard: The Northfield History Center, next exit, seven miles east. The Jesse James gang tried to rob its bank in eighteen seventy-six. The town said no.

### Northfield History Center (southbound)
- treatment: billboard
- leg: minneapolis_mn_us -> owatonna_mn_us
- at_mi: 34.5
- spoken: Billboard: The Northfield History Center, next exit, seven miles east. The Jesse James gang tried to rob its bank in eighteen seventy-six. The town said no.

### Northfield History Center (southbound)
- treatment: billboard
- leg: minneapolis_mn_us -> des_moines_ia_us
- at_mi: 34.6
- spoken: Billboard: The Northfield History Center, next exit, seven miles east. The Jesse James gang tried to rob its bank in eighteen seventy-six. The town said no.

### Northfield History Center (northbound)
- treatment: billboard
- leg: des_moines_ia_us -> minneapolis_mn_us
- at_mi: 207.0
- spoken: Billboard: The Northfield History Center, next exit, seven miles east. The Jesse James gang tried to rob its bank in eighteen seventy-six. The town said no.

## United States Hockey Hall of Fame, Eveleth (US 53)

The national hockey museum, opened 1973, at 801 Hat Trick Avenue, off
northbound US 53 on the edge of Eveleth; open daily (ironrange.org;
Wikipedia, "United States Hockey Hall of Fame"). Its board voted in January
2026 to keep it in Eveleth rather than move to St. Paul (WDIO). The leg has
no exit list; the museum is placed between the leg's Midway and Eveleth
callouts. Southbound the Virginia museum and Midway callouts leave room only
about three miles out.

### Hockey Hall of Fame (southbound)
- treatment: billboard
- leg: hibbing_mn_us -> duluth_mn_us
- at_mi: 25.0
- spoken: Billboard: The United States Hockey Hall of Fame, ahead in Eveleth, on Hat Trick Avenue. Three on-time deliveries in one day is a hat trick too.

### Hockey Hall of Fame (northbound)
- treatment: billboard
- leg: duluth_mn_us -> hibbing_mn_us
- at_mi: 50.0
- spoken: Billboard: The United States Hockey Hall of Fame, ahead in Eveleth, on Hat Trick Avenue. Three on-time deliveries in one day is a hat trick too.

## Judy Garland Museum, Grand Rapids (US 169)

Her restored birthplace home and museum at 2727 South Pokegama Avenue, on US
169 on the south side of Grand Rapids, where she was born in 1922; daily in
summer, weekends off-season (judygarlandmuseum.com; Roadside America). A pair
of ruby slippers from the film was stolen from the museum in August 2005 and
recovered by the FBI in 2018 (CBS News; KQED). Placed from the legs'
Grand Rapids checkpoint and node; these legs list no exits.

### Judy Garland Museum (southbound)
- treatment: billboard
- leg: hibbing_mn_us -> minneapolis_mn_us
- at_mi: 29.5
- spoken: Billboard: The Judy Garland Museum, ahead in Grand Rapids, her birthplace. Ruby slippers were stolen here once. The FBI found them. Clicking heels did not.

### Judy Garland Museum (northbound)
- treatment: billboard
- leg: minneapolis_mn_us -> hibbing_mn_us
- at_mi: 163.0
- spoken: Billboard: The Judy Garland Museum, ahead in Grand Rapids, her birthplace. Ruby slippers were stolen here once. The FBI found them. Clicking heels did not.

### Judy Garland Museum (eastbound)
- treatment: billboard
- leg: bemidji_mn_us -> grand_rapids_mn_us
- at_mi: 60.0
- spoken: Billboard: The Judy Garland Museum, ahead in Grand Rapids, her birthplace. Ruby slippers were stolen here once. The FBI found them. Clicking heels did not.

### Judy Garland Museum (westbound)
- treatment: billboard
- leg: duluth_mn_us -> grand_rapids_mn_us
- at_mi: 77.5
- spoken: Billboard: The Judy Garland Museum, ahead in Grand Rapids, her birthplace. Ruby slippers were stolen here once. The FBI found them. Clicking heels did not.

## The Big Fish, Bena (US 2)

A sixty-five-foot wooden muskie three miles west of Bena on US 2, built in
the late 1950s as a drive-in where diners ate inside the fish, restored and
repainted in 2009; it stands beside the Big Fish Supper Club and appears in
the opening credits of National Lampoon's Vacation (Wikipedia, "The Big Fish
(roadside attraction)"; Grand Forks Herald, September 16, 2009; CBS News
Minnesota, July 5, 2023). It projects onto the Bemidji to Grand Rapids leg
at mile 34.7, beside the leg's Chippewa National Forest callout.

### The Big Fish (eastbound)
- treatment: billboard
- leg: bemidji_mn_us -> grand_rapids_mn_us
- at_mi: 25.0
- spoken: Billboard: The Big Fish, ahead near Bena. A sixty-five-foot muskie, built as a drive-in in the nineteen fifties. Out of water ever since, and looking great.

### The Big Fish (westbound)
- treatment: billboard
- leg: grand_rapids_mn_us -> bemidji_mn_us
- at_mi: 25.0
- spoken: Billboard: The Big Fish, ahead near Bena. A sixty-five-foot muskie, built as a drive-in in the nineteen fifties. Out of water ever since, and looking great.

## The Garrison walleye (US 169, Mille Lacs)

A nineteen-foot fiberglass walleye at the Garrison Concourse wayside on the
shore of Mille Lacs, east side of US 169, on display since 1980 and
repainted in late 2023. Its plaque says Paul Bunyan and Babe caught it after
a three-day fight (Roadside America, "Wally Walleye"; Wikipedia, "Garrison
Concourse"; Brainerd Dispatch). Both signs stand before the town.

### Garrison walleye (southbound)
- treatment: billboard
- leg: hibbing_mn_us -> minneapolis_mn_us
- at_mi: 97.0
- spoken: Billboard: Garrison, ahead on Mille Lacs, where a nineteen-foot fiberglass walleye stands by the lake. The plaque says Paul Bunyan caught it. Sure he did.

### Garrison walleye (northbound)
- treatment: billboard
- leg: minneapolis_mn_us -> hibbing_mn_us
- at_mi: 97.0
- spoken: Billboard: Garrison, ahead on Mille Lacs, where a nineteen-foot fiberglass walleye stands by the lake. The plaque says Paul Bunyan caught it. Sure he did.

## Frank Lloyd Wright's gas station, Cloquet (I-35 Exits 237 and 239)

The R. W. Lindholm Service Station, built in 1958 at Cloquet Avenue and
Fourteenth Street, where Minnesota 33 and 45 meet: the only gas station of
his design built in Wright's lifetime, still a working full-service station
and repair shop (Wikipedia, "R. W. Lindholm Service Station"; Northern News
Now, June 6, 2025; cloquet.com). It is about two miles off I-35 by Exit 237
or 239. Exit 237 is in no leg's interchange list, and the village callouts
at Esko and Scanlon fill the miles before Exit 239, so all four signs read
"ahead in Cloquet". The Duluth to Fargo leg runs I-35 south to Exit 235
before turning west on Minnesota 210, so it passes the same exits.

### Frank Lloyd Wright gas station (southbound)
- treatment: billboard
- leg: duluth_mn_us -> minneapolis_mn_us
- at_mi: 9.8
- spoken: Billboard: Frank Lloyd Wright's gas station, ahead in Cloquet. The only one built in his lifetime, and it still pumps gas. Fill up on architecture.

### Frank Lloyd Wright gas station (southbound)
- treatment: billboard
- leg: duluth_mn_us -> fargo_nd_us
- at_mi: 11.0
- spoken: Billboard: Frank Lloyd Wright's gas station, ahead in Cloquet. The only one built in his lifetime, and it still pumps gas. Fill up on architecture.

### Frank Lloyd Wright gas station (northbound)
- treatment: billboard
- leg: minneapolis_mn_us -> duluth_mn_us
- at_mi: 125.0
- spoken: Billboard: Frank Lloyd Wright's gas station, ahead in Cloquet. The only one built in his lifetime, and it still pumps gas. Fill up on architecture.

### Frank Lloyd Wright gas station (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> duluth_mn_us
- at_mi: 229.0
- spoken: Billboard: Frank Lloyd Wright's gas station, ahead in Cloquet. The only one built in his lifetime, and it still pumps gas. Fill up on architecture.

## Aerial Lift Bridge, Duluth

The 1905 bridge over the Duluth Ship Canal, rebuilt as a vertical lift
bridge in 1929 and 1930; its road deck rises 135 feet in about a minute,
about five thousand times a year, and a ship asks for a lift with long,
short, long, short on its horn (Wikipedia, "Aerial Lift Bridge"). Duluth has
no approach line in the pools. One sign on every leg into the city, about
ten miles out.

### Aerial Lift Bridge (northbound)
- treatment: billboard
- leg: minneapolis_mn_us -> duluth_mn_us
- at_mi: 142.2
- spoken: Billboard: The Aerial Lift Bridge, ahead in Duluth. Ships sound long, short, long, short, and the whole road deck rises. Your horn will not work.

### Aerial Lift Bridge (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> duluth_mn_us
- at_mi: 245.0
- spoken: Billboard: The Aerial Lift Bridge, ahead in Duluth. Ships sound long, short, long, short, and the whole road deck rises. Your horn will not work.

### Aerial Lift Bridge (eastbound)
- treatment: billboard
- leg: grand_rapids_mn_us -> duluth_mn_us
- at_mi: 71.0
- spoken: Billboard: The Aerial Lift Bridge, ahead in Duluth. Ships sound long, short, long, short, and the whole road deck rises. Your horn will not work.

### Aerial Lift Bridge (southbound)
- treatment: billboard
- leg: hibbing_mn_us -> duluth_mn_us
- at_mi: 79.0
- spoken: Billboard: The Aerial Lift Bridge, ahead in Duluth. Ships sound long, short, long, short, and the whole road deck rises. Your horn will not work.

### Aerial Lift Bridge (westbound)
- treatment: billboard
- leg: rice_lake_wi_us -> duluth_mn_us
- at_mi: 88.5
- spoken: Billboard: The Aerial Lift Bridge, ahead in Duluth. Ships sound long, short, long, short, and the whole road deck rises. Your horn will not work.

## The Pine City voyageur (I-35 Exit 169)

A forty-five-foot fur trader carved in 1992 by chainsaw sculptor Dennis
Roghair from one redwood log, brought from California in the 1930s as a
hotel's tourist draw; it stands in Voyageur Park by the Snake River in Pine
City (KSTP, August 8, 2022; Roadside America).

### Pine City voyageur (southbound)
- treatment: billboard
- leg: duluth_mn_us -> minneapolis_mn_us
- at_mi: 84.4
- spoken: Billboard: The Pine City voyageur, next exit. Forty-five feet of redwood, chainsawed into a fur trader. The log came from California and decided to stay.

### Pine City voyageur (northbound)
- treatment: billboard
- leg: minneapolis_mn_us -> duluth_mn_us
- at_mi: 64.2
- spoken: Billboard: The Pine City voyageur, next exit. Forty-five feet of redwood, chainsawed into a fur trader. The log came from California and decided to stay.

## Faribault Woolen Mill (I-35 Exit 59)

A woolen mill on the Cannon River since 1865 that still turns raw wool into
finished blankets, 1500 Second Avenue Northwest, by Exit 59 and Minnesota 21;
store open Monday to Saturday, tours Friday and Saturday
(exploreminnesota.com; familyfuntwincities.com).

### Faribault Woolen Mill (northbound)
- treatment: billboard
- leg: owatonna_mn_us -> minneapolis_mn_us
- at_mi: 16.6
- spoken: Billboard: The Faribault Woolen Mill, next exit. Making wool blankets by the Cannon River since eighteen sixty-five. Minnesota winters have kept it in business.

### Faribault Woolen Mill (southbound)
- treatment: billboard
- leg: minneapolis_mn_us -> owatonna_mn_us
- at_mi: 45.2
- spoken: Billboard: The Faribault Woolen Mill, next exit. Making wool blankets by the Cannon River since eighteen sixty-five. Minnesota winters have kept it in business.

### Faribault Woolen Mill (southbound)
- treatment: billboard
- leg: minneapolis_mn_us -> des_moines_ia_us
- at_mi: 45.4
- spoken: Billboard: The Faribault Woolen Mill, next exit. Making wool blankets by the Cannon River since eighteen sixty-five. Minnesota winters have kept it in business.

### Faribault Woolen Mill (northbound)
- treatment: billboard
- leg: des_moines_ia_us -> minneapolis_mn_us
- at_mi: 196.4
- spoken: Billboard: The Faribault Woolen Mill, next exit. Making wool blankets by the Cannon River since eighteen sixty-five. Minnesota winters have kept it in business.

## Sauk Centre (I-94 Exits 124 and 127)

Sinclair Lewis's hometown and the model for Gopher Prairie in his 1920
novel Main Street, which angered some small-town readers; its downtown is
now the Original Main Street Historic District, and his boyhood home is a
museum (Wikipedia, "Main Street (novel)" and "Original Main Street Historic
District"; MPR News, July 2, 2018). These signs are about the town and stand
before its first exit in each direction.

### Sauk Centre (westbound)
- treatment: billboard
- leg: st_cloud_mn_us -> fargo_nd_us
- at_mi: 40.2
- spoken: Billboard: Sauk Centre, next exit. Sinclair Lewis mocked his hometown in his novel Main Street. Its downtown is now the Original Main Street Historic District.

### Sauk Centre (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> st_cloud_mn_us
- at_mi: 124.6
- spoken: Billboard: Sauk Centre, next exit. Sinclair Lewis mocked his hometown in his novel Main Street. Its downtown is now the Original Main Street Historic District.

### Sauk Centre (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> minneapolis_mn_us
- at_mi: 125.0
- spoken: Billboard: Sauk Centre, next exit. Sinclair Lewis mocked his hometown in his novel Main Street. Its downtown is now the Original Main Street Historic District.

### Sauk Centre (westbound)
- treatment: billboard
- leg: minneapolis_mn_us -> fargo_nd_us
- at_mi: 103.7
- spoken: Billboard: Sauk Centre, next exit. Sinclair Lewis mocked his hometown in his novel Main Street. Its downtown is now the Original Main Street Historic District.

## Otto the Otter, Fergus Falls (I-94 Exit 55)

A forty-foot concrete otter in Adams Park on Grotto Lake, begun as a high
school shop project for the city's 1972 centennial, 1.6 miles from I-94
Exit 55 (Roadside America; ottertaillakescountry.com; Atlas Obscura).
Westbound the signs stand before Fergus Falls, ahead of its first exit, so
they read "ahead".

### Otto the Otter (westbound)
- treatment: billboard
- leg: st_cloud_mn_us -> fargo_nd_us
- at_mi: 104.0
- spoken: Billboard: Otto the Otter, ahead in Fergus Falls. Forty feet of concrete otter since nineteen seventy-two. He has never once gone in the water.

### Otto the Otter (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> st_cloud_mn_us
- at_mi: 56.0
- spoken: Billboard: Otto the Otter, next exit in Fergus Falls. Forty feet of concrete otter since nineteen seventy-two. He has never once gone in the water.

### Otto the Otter (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> minneapolis_mn_us
- at_mi: 56.3
- spoken: Billboard: Otto the Otter, next exit in Fergus Falls. Forty feet of concrete otter since nineteen seventy-two. He has never once gone in the water.

### Otto the Otter (westbound)
- treatment: billboard
- leg: minneapolis_mn_us -> fargo_nd_us
- at_mi: 168.0
- spoken: Billboard: Otto the Otter, ahead in Fergus Falls. Forty feet of concrete otter since nineteen seventy-two. He has never once gone in the water.

## The World's Largest Prairie Chicken, Rothsay (I-94 Exit 38)

A thirteen-foot, nine-thousand-pound greater prairie chicken in the act of
booming, built by Art Fosse for the 1976 Bicentennial, overlooking the
Rothsay exit ramp at the Art Fosse Wayside (Roadside America; Atlas
Obscura). Westbound the Rothsay village and river callouts sit just before
the exit, so those signs stand six miles out and read "ahead".

### Rothsay prairie chicken (westbound)
- treatment: billboard
- leg: st_cloud_mn_us -> fargo_nd_us
- at_mi: 125.5
- spoken: Billboard: The world's largest prairie chicken, ahead in Rothsay. Thirteen feet of bird, puffed up and booming since nineteen seventy-six. Do not boom back.

### Rothsay prairie chicken (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> st_cloud_mn_us
- at_mi: 37.8
- spoken: Billboard: The world's largest prairie chicken, next exit in Rothsay. Thirteen feet of bird, puffed up and booming since nineteen seventy-six. Do not boom back.

### Rothsay prairie chicken (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> minneapolis_mn_us
- at_mi: 38.4
- spoken: Billboard: The world's largest prairie chicken, next exit in Rothsay. Thirteen feet of bird, puffed up and booming since nineteen seventy-six. Do not boom back.

### Rothsay prairie chicken (westbound)
- treatment: billboard
- leg: minneapolis_mn_us -> fargo_nd_us
- at_mi: 188.5
- spoken: Billboard: The world's largest prairie chicken, ahead in Rothsay. Thirteen feet of bird, puffed up and booming since nineteen seventy-six. Do not boom back.

## Hjemkomst Center, Moorhead

Home of the Hjemkomst, a Viking ship replica that Moorhead junior high
school counselor Robert Asp began building in 1974 in a potato warehouse in
Hawley; after his death in 1980 his family and crew sailed it to Norway in
1982. The center also holds a full-scale replica of the Hopperstad stave
church; open daily (Wikipedia, "Hjemkomst Center"; moorheadmn.gov). It sits
a mile short of the Fargo node, so each leg into Fargo from Minnesota gets
one sign about ten miles out. The North Dakota legs into Fargo are left to
that state's sheet.

### Hjemkomst Center (westbound)
- treatment: billboard
- leg: st_cloud_mn_us -> fargo_nd_us
- at_mi: 159.0
- spoken: Billboard: The Hjemkomst Center, ahead in Moorhead. A school counselor built a Viking ship in a potato warehouse. It sailed to Norway. The potatoes stayed home.

### Hjemkomst Center (westbound)
- treatment: billboard
- leg: minneapolis_mn_us -> fargo_nd_us
- at_mi: 224.0
- spoken: Billboard: The Hjemkomst Center, ahead in Moorhead. A school counselor built a Viking ship in a potato warehouse. It sailed to Norway. The potatoes stayed home.

### Hjemkomst Center (westbound)
- treatment: billboard
- leg: duluth_mn_us -> fargo_nd_us
- at_mi: 244.5
- spoken: Billboard: The Hjemkomst Center, ahead in Moorhead. A school counselor built a Viking ship in a potato warehouse. It sailed to Norway. The potatoes stayed home.

## Big Tom, Frazee (US 10)

A twenty-foot, five-thousand-pound fiberglass turkey at Lions Park on a hill
beside US 10 and Minnesota 87, in the self-styled Turkey Capital of the
World. The first Big Tom, from 1986, burned in 1998 when a blowtorch lit its
insulation during a secret touch-up, and this one replaced it that year
(Roadside America; roadtrippers.com).

### Big Tom (westbound)
- treatment: billboard
- leg: duluth_mn_us -> fargo_nd_us
- at_mi: 186.0
- spoken: Billboard: Big Tom, ahead in Frazee, a twenty-foot turkey on a hill. The first one caught fire during a touch-up. This one has been very careful.

### Big Tom (eastbound)
- treatment: billboard
- leg: fargo_nd_us -> duluth_mn_us
- at_mi: 48.0
- spoken: Billboard: Big Tom, ahead in Frazee, a twenty-foot turkey on a hill. The first one caught fire during a touch-up. This one has been very careful.

## Zumbrota Covered Bridge (US 52)

Minnesota's last remaining historic covered bridge, built in 1869 over the
Zumbro River; moved to the fairgrounds in 1932 and to Covered Bridge Park in
downtown Zumbrota in 1997, where it carries people on foot (Wikipedia,
"Zumbrota Covered Bridge"; MnDOT historic bridges, bridge 25580). US 52
lists no exits here, so the signs are placed from the Zumbrota checkpoint.

### Zumbrota Covered Bridge (northbound)
- treatment: billboard
- leg: rochester_mn_us -> minneapolis_mn_us
- at_mi: 14.0
- spoken: Billboard: Zumbrota, ahead, with Minnesota's last historic covered bridge, built in eighteen sixty-nine. It has moved twice, which is unusual for a bridge.

### Zumbrota Covered Bridge (southbound)
- treatment: billboard
- leg: minneapolis_mn_us -> rochester_mn_us
- at_mi: 48.0
- spoken: Billboard: Zumbrota, ahead, with Minnesota's last historic covered bridge, built in eighteen sixty-nine. It has moved twice, which is unusual for a bridge.

## Minneopa State Park bison, Mankato (Minnesota 60 and US 169)

A bison herd on a 331-acre range with a drive-through road, where visitors
must stay in their vehicles; open daily but Wednesdays, shorter winter hours
from November 1 (Minnesota DNR; Mankato Free Press; Southern Minn Scene).
The park lies beside Minnesota 60 just west of Mankato. Leaving Mankato
westbound it is five miles from the start of the leg, so that direction has
no sign on the Mankato to Sioux Falls leg.

### Minneopa bison (eastbound)
- treatment: billboard
- leg: sioux_falls_sd_us -> minneapolis_mn_us
- at_mi: 136.0
- spoken: Billboard: Minneopa State Park, ahead near Mankato. A bison herd roams a range you can drive through. Stay inside and yield. They will not.

### Minneopa bison (eastbound)
- treatment: billboard
- leg: sioux_falls_sd_us -> mankato_mn_us
- at_mi: 137.0
- spoken: Billboard: Minneopa State Park, ahead near Mankato. A bison herd roams a range you can drive through. Stay inside and yield. They will not.

### Minneopa bison (westbound)
- treatment: billboard
- leg: minneapolis_mn_us -> sioux_falls_sd_us
- at_mi: 74.0
- spoken: Billboard: Minneopa State Park, ahead near Mankato. A bison herd roams a range you can drive through. Stay inside and yield. They will not.

## Verne the Patriot, Luverne (I-90 Exit 12)

A sixty-five-foot nutcracker in stars and stripes, finished in June 2026 at
the Those Blasted Things rock shop, 924 South Kniss Avenue (US 75), a block
from I-90; its makers say it is almost twice the height of the current
record holder. Its inspiration, Luverne resident Betty Mann, owns more than
seven thousand nutcrackers, more than the town's population (FOX 9, July 1,
2026; AP via KSL, July 21, 2026; Roadside America). The Sioux Falls to
Mankato and Mankato to Sioux Falls legs list no exits; Exit 12 is placed on
them by the Sioux Falls to Minneapolis leg's distance from the Luverne
checkpoint.

### Verne the Patriot (eastbound)
- treatment: billboard
- leg: sioux_falls_sd_us -> minneapolis_mn_us
- at_mi: 28.3
- spoken: Billboard: Verne the Patriot, a sixty-five-foot nutcracker, next exit in Luverne. One woman here owns more nutcrackers than the town has people.

### Verne the Patriot (westbound)
- treatment: billboard
- leg: minneapolis_mn_us -> sioux_falls_sd_us
- at_mi: 204.3
- spoken: Billboard: Verne the Patriot, a sixty-five-foot nutcracker, next exit in Luverne. One woman here owns more nutcrackers than the town has people.

### Verne the Patriot (eastbound)
- treatment: billboard
- leg: sioux_falls_sd_us -> mankato_mn_us
- at_mi: 27.8
- spoken: Billboard: Verne the Patriot, a sixty-five-foot nutcracker, next exit in Luverne. One woman here owns more nutcrackers than the town has people.

### Verne the Patriot (westbound)
- treatment: billboard
- leg: mankato_mn_us -> sioux_falls_sd_us
- at_mi: 124.3
- spoken: Billboard: Verne the Patriot, a sixty-five-foot nutcracker, next exit in Luverne. One woman here owns more nutcrackers than the town has people.

## Hull Rust Mine View, Hibbing

An overlook at 611 McKinley Street on the north side of Hibbing, open daily
year-round, above an open-pit iron mine eight miles long and three and a
half wide. In 1918 the north part of town, 185 houses and 20 businesses,
was rolled two miles south on wheels so the mine could grow
(hibbingmineview.org). One sign on each leg into Hibbing. From Duluth the
Iron Range village callouts leave no room closer than seventeen miles out.

### Hull Rust Mine View (westbound)
- treatment: billboard
- leg: duluth_mn_us -> hibbing_mn_us
- at_mi: 72.5
- spoken: Billboard: The Hull Rust Mine View, ahead in Hibbing. In nineteen eighteen, part of town rolled two miles south to make room for the mine.

### Hull Rust Mine View (northbound)
- treatment: billboard
- leg: minneapolis_mn_us -> hibbing_mn_us
- at_mi: 202.0
- spoken: Billboard: The Hull Rust Mine View, ahead in Hibbing. In nineteen eighteen, part of town rolled two miles south to make room for the mine.

# Wisconsin

## Wisconsin Dells (I-90/94 Exits 85 to 92)

The waterpark town on the Wisconsin River. The Original Wisconsin Ducks have
run tours since 1946 in World War Two era amphibious vehicles that drive the
trails and splash into the Wisconsin River and Lake Delton, daily mid-March
to mid-November (wisconsinducktours.com; dells.com; travelwisconsin.com).
These signs are about the town, so each stands eight to fourteen miles
before its first Dells exit.

### Wisconsin Dells (eastbound)
- treatment: billboard
- leg: la_crosse_wi_us -> madison_wi_us
- at_mi: 78.0
- spoken: Billboard: Wisconsin Dells, ahead. The duck tours ride in World War Two army trucks that drive into the river. Do not try this with yours.

### Wisconsin Dells (westbound)
- treatment: billboard
- leg: madison_wi_us -> la_crosse_wi_us
- at_mi: 42.0
- spoken: Billboard: Wisconsin Dells, ahead. The duck tours ride in World War Two army trucks that drive into the river. Do not try this with yours.

### Wisconsin Dells (westbound)
- treatment: billboard
- leg: milwaukee_wi_us -> minneapolis_mn_us
- at_mi: 106.0
- spoken: Billboard: Wisconsin Dells, ahead. The duck tours ride in World War Two army trucks that drive into the river. Do not try this with yours.

### Wisconsin Dells (eastbound)
- treatment: billboard
- leg: minneapolis_mn_us -> milwaukee_wi_us
- at_mi: 203.0
- spoken: Billboard: Wisconsin Dells, ahead. The duck tours ride in World War Two army trucks that drive into the river. Do not try this with yours.

## Mars Cheese Castle, Kenosha (I-94 Exit 340)

Opened by Mario Ventura in 1947; the present store, opened in 2011 when I-94
was widened, is built as a castle with turrets, a drawbridge entrance and a
watchtower, at 2800 West Frontage Road, southwest side of Exit 340 (Wisconsin
142); open daily (marscheese.com; Wikipedia, "Mars Cheese Castle"; Roadside
America). Northbound from Chicago, the Des Plaines River callout sits two and
a half miles before Exit 340, so that sign reads "ahead". The Kenosha to
Milwaukee leg joins I-94 at Exit 340 itself, so only its southbound
direction gets a sign; the Kenosha to Chicago leg joins at Exit 342, south of
the castle, and gets none.

### Mars Cheese Castle (southbound)
- treatment: billboard
- leg: green_bay_wi_us -> grand_rapids_mi_us
- at_mi: 141.2
- spoken: Billboard: Mars Cheese Castle, next exit. Turrets, a drawbridge, and cheese since nineteen forty-seven. Storm the castle. Nobody will stop you.

### Mars Cheese Castle (northbound)
- treatment: billboard
- leg: grand_rapids_mi_us -> green_bay_wi_us
- at_mi: 237.5
- spoken: Billboard: Mars Cheese Castle, next exit. Turrets, a drawbridge, and cheese since nineteen forty-seven. Storm the castle. Nobody will stop you.

### Mars Cheese Castle (southbound)
- treatment: billboard
- leg: milwaukee_wi_us -> chicago_il_us
- at_mi: 30.0
- spoken: Billboard: Mars Cheese Castle, next exit. Turrets, a drawbridge, and cheese since nineteen forty-seven. Storm the castle. Nobody will stop you.

### Mars Cheese Castle (northbound)
- treatment: billboard
- leg: chicago_il_us -> milwaukee_wi_us
- at_mi: 51.5
- spoken: Billboard: Mars Cheese Castle, ahead in Kenosha. Turrets, a drawbridge, and cheese since nineteen forty-seven. Storm the castle. Nobody will stop you.

### Mars Cheese Castle (northbound)
- treatment: billboard
- leg: aurora_il_us -> milwaukee_wi_us
- at_mi: 79.5
- spoken: Billboard: Mars Cheese Castle, next exit. Turrets, a drawbridge, and cheese since nineteen forty-seven. Storm the castle. Nobody will stop you.

### Mars Cheese Castle (southbound)
- treatment: billboard
- leg: milwaukee_wi_us -> aurora_il_us
- at_mi: 29.3
- spoken: Billboard: Mars Cheese Castle, next exit. Turrets, a drawbridge, and cheese since nineteen forty-seven. Storm the castle. Nobody will stop you.

### Mars Cheese Castle (southbound)
- treatment: billboard
- leg: milwaukee_wi_us -> kenosha_wi_us
- at_mi: 29.5
- spoken: Billboard: Mars Cheese Castle, next exit. Turrets, a drawbridge, and cheese since nineteen forty-seven. Storm the castle. Nobody will stop you.

## Ehlenbach's Cheese Chalet, DeForest (I-90/94 and I-39 Exit 126)

A family-owned cheese shop at 4879 County Road V, just east of Exit 126,
about ten miles north of Madison, with more than two hundred Wisconsin
cheeses and Sissy the Cow, a fiberglass Holstein, out front; open daily
(ehlenbachscheese.com; visitmadison.com; Roadside America). The village of
Windsor callout sits a mile from the exit on every leg here, so two signs
read "ahead" instead of standing inside that gap.

### Ehlenbach's Cheese Chalet (westbound)
- treatment: billboard
- leg: milwaukee_wi_us -> minneapolis_mn_us
- at_mi: 75.5
- spoken: Billboard: Ehlenbach's Cheese Chalet, ahead in DeForest. Over two hundred Wisconsin cheeses, and a fiberglass cow out front named Sissy. She is not for sale.

### Ehlenbach's Cheese Chalet (eastbound)
- treatment: billboard
- leg: minneapolis_mn_us -> milwaukee_wi_us
- at_mi: 252.3
- spoken: Billboard: Ehlenbach's Cheese Chalet, next exit. Over two hundred Wisconsin cheeses, and a fiberglass cow out front named Sissy. She is not for sale.

### Ehlenbach's Cheese Chalet (southbound)
- treatment: billboard
- leg: la_crosse_wi_us -> madison_wi_us
- at_mi: 128.0
- spoken: Billboard: Ehlenbach's Cheese Chalet, next exit. Over two hundred Wisconsin cheeses, and a fiberglass cow out front named Sissy. She is not for sale.

### Ehlenbach's Cheese Chalet (northbound)
- treatment: billboard
- leg: madison_wi_us -> la_crosse_wi_us
- at_mi: 12.0
- spoken: Billboard: Ehlenbach's Cheese Chalet, next exit. Over two hundred Wisconsin cheeses, and a fiberglass cow out front named Sissy. She is not for sale.

### Ehlenbach's Cheese Chalet (southbound)
- treatment: billboard
- leg: wausau_wi_us -> madison_wi_us
- at_mi: 126.2
- spoken: Billboard: Ehlenbach's Cheese Chalet, next exit. Over two hundred Wisconsin cheeses, and a fiberglass cow out front named Sissy. She is not for sale.

### Ehlenbach's Cheese Chalet (northbound)
- treatment: billboard
- leg: madison_wi_us -> wausau_wi_us
- at_mi: 11.5
- spoken: Billboard: Ehlenbach's Cheese Chalet, ahead in DeForest. Over two hundred Wisconsin cheeses, and a fiberglass cow out front named Sissy. She is not for sale.

## EAA Aviation Museum, Oshkosh (I-41 Exit 116)

About two hundred aircraft at 3000 Poberezny Road; its own directions say
I-41 Exit 116 (Wisconsin 44) east, then Knapp Street and Poberezny Road;
open daily (eaa.org). Each July EAA AirVenture brings more than ten thousand
aircraft into Oshkosh and the airports around it in one week (EAA, via
Aviation Pros, AirVenture 2025). Exit 116 is in no leg's interchange list;
it is placed a mile south of Exit 117 by the I-41 mileposts. Southbound
from Green Bay, Exits 117 and 116 are a mile apart, so that sign reads
"ahead"; so does the Green Bay to Oshkosh one, which ends in the city.

### EAA Aviation Museum (northbound)
- treatment: billboard
- leg: fond_du_lac_wi_us -> oshkosh_wi_us
- at_mi: 19.4
- spoken: Billboard: The EAA Aviation Museum, next exit. Each July about ten thousand airplanes fly into Oshkosh for one week. You thought the truck stop was busy.

### EAA Aviation Museum (northbound)
- treatment: billboard
- leg: madison_wi_us -> green_bay_wi_us
- at_mi: 87.4
- spoken: Billboard: The EAA Aviation Museum, next exit. Each July about ten thousand airplanes fly into Oshkosh for one week. You thought the truck stop was busy.

### EAA Aviation Museum (southbound)
- treatment: billboard
- leg: green_bay_wi_us -> madison_wi_us
- at_mi: 47.0
- spoken: Billboard: The EAA Aviation Museum, ahead in Oshkosh. Each July about ten thousand airplanes fly in for one week. You thought the truck stop was busy.

### EAA Aviation Museum (southbound)
- treatment: billboard
- leg: green_bay_wi_us -> oshkosh_wi_us
- at_mi: 41.0
- spoken: Billboard: The EAA Aviation Museum, ahead in Oshkosh. Each July about ten thousand airplanes fly in for one week. You thought the truck stop was busy.

## Wisconsin Maritime Museum, Manitowoc (I-43 Exit 152)

At 75 Maritime Drive on the lakefront, with the World War Two submarine USS
Cobia; its directions say I-43 Exit 152, then east on Waldo Boulevard to the
lake; open daily, Cobia tours running into October 2026 after a 2025 dry
dock (wisconsinmaritime.org; Roadside America). Manitowoc Shipbuilding built
twenty-eight submarines in the war and sent them to the sea by the Chicago
canal and the Mississippi on floating dry docks (Wisconsin Historical
Society; Naval History magazine, October 2008). Northbound from Sheboygan,
the Manitowoc River and county museum callouts fill the gap between Exits
149 and 152, so that sign reads "ahead".

### Wisconsin Maritime Museum (northbound)
- treatment: billboard
- leg: sheboygan_wi_us -> green_bay_wi_us
- at_mi: 20.0
- spoken: Billboard: The Wisconsin Maritime Museum, ahead in Manitowoc. The town built twenty-eight World War Two submarines and sent them to sea down the Mississippi. Some detour.

### Wisconsin Maritime Museum (southbound)
- treatment: billboard
- leg: green_bay_wi_us -> sheboygan_wi_us
- at_mi: 35.5
- spoken: Billboard: The Wisconsin Maritime Museum, next exit. Manitowoc built twenty-eight World War Two submarines and sent them to sea down the Mississippi. Some detour.

### Wisconsin Maritime Museum (southbound)
- treatment: billboard
- leg: green_bay_wi_us -> grand_rapids_mi_us
- at_mi: 34.8
- spoken: Billboard: The Wisconsin Maritime Museum, next exit. Manitowoc built twenty-eight World War Two submarines and sent them to sea down the Mississippi. Some detour.

### Wisconsin Maritime Museum (northbound)
- treatment: billboard
- leg: grand_rapids_mi_us -> green_bay_wi_us
- at_mi: 344.0
- spoken: Billboard: The Wisconsin Maritime Museum, next exit. Manitowoc built twenty-eight World War Two submarines and sent them to sea down the Mississippi. Some detour.

## Sparta and the Elroy-Sparta State Trail (I-90 Exits 25 and 28)

The Elroy-Sparta State Trail, opened in 1967 and counted as the first
rail trail in the country, starts in Sparta and runs through three railroad
tunnels; the longest, between Norwalk and Sparta, is three-quarters of a
mile (Wikipedia, "Elroy-Sparta State Trail"; travelwisconsin.com). Sparta
also has the Deke Slayton Memorial Space and Bicycle Museum and Ben Bikin',
a thirty-two-foot rider on a high-wheel bicycle (dekeslaytonmuseum.org;
Roadside America). These signs are about the town and stand before its first
exit in each direction.

### Sparta (eastbound)
- treatment: billboard
- leg: la_crosse_wi_us -> madison_wi_us
- at_mi: 24.8
- spoken: Billboard: Sparta, next exit, where America's first rail trail begins. Its longest tunnel runs three-quarters of a mile, and no train is coming.

### Sparta (westbound)
- treatment: billboard
- leg: madison_wi_us -> la_crosse_wi_us
- at_mi: 113.5
- spoken: Billboard: Sparta, next exit, where America's first rail trail begins. Its longest tunnel runs three-quarters of a mile, and no train is coming.

## Norske Nook, Osseo (I-94 Exit 88)

Restaurant and bakery at 13804 Seventh Street, Osseo, at I-94 Exit 88,
open daily since 1973 and known for award-winning pies with hand-rolled
crusts (norskenook.com).

### Norske Nook (westbound)
- treatment: billboard
- leg: milwaukee_wi_us -> minneapolis_mn_us
- at_mi: 221.2
- spoken: Billboard: Norske Nook, next exit in Osseo. Homemade pie since nineteen seventy-three, every crust rolled by hand. Nobody has ever stopped for just one slice.

### Norske Nook (eastbound)
- treatment: billboard
- leg: minneapolis_mn_us -> milwaukee_wi_us
- at_mi: 112.5
- spoken: Billboard: Norske Nook, next exit in Osseo. Homemade pie since nineteen seventy-three, every crust rolled by hand. Nobody has ever stopped for just one slice.

## Kohler Design Center, Kohler (I-43 Exit 126)

The Kohler Company's free showroom of bathtubs, sinks, toilets and its own
history, 101 Upper Road in the village of Kohler, open daily; reached from
I-43 Exit 126 by Wisconsin 23 west and County Y (travelwisconsin.com;
destinationkohler.com). The Milwaukee to Sheboygan leg's exit list ends at
Exit 123, so its sign reads "ahead in Kohler".

### Kohler Design Center (southbound)
- treatment: billboard
- leg: green_bay_wi_us -> grand_rapids_mi_us
- at_mi: 59.6
- spoken: Billboard: The Kohler Design Center, next exit. A showroom of bathtubs, sinks and toilets, free to walk through. Please do not use the exhibits.

### Kohler Design Center (northbound)
- treatment: billboard
- leg: grand_rapids_mi_us -> green_bay_wi_us
- at_mi: 319.0
- spoken: Billboard: The Kohler Design Center, next exit. A showroom of bathtubs, sinks and toilets, free to walk through. Please do not use the exhibits.

### Kohler Design Center (northbound)
- treatment: billboard
- leg: milwaukee_wi_us -> sheboygan_wi_us
- at_mi: 48.5
- spoken: Billboard: The Kohler Design Center, ahead in Kohler. A showroom of bathtubs, sinks and toilets, free to walk through. Please do not use the exhibits.

## National Railroad Museum, Green Bay

In Ashwaubenon on the south side of Green Bay, open daily, with Union
Pacific Big Boy 4017, one of the largest steam locomotives ever built at
about 1.1 million pounds, and Eisenhower's wartime command train
(travelwisconsin.com; nationalrrmuseum.org; whichmuseum.com hours). Green
Bay has one placed sign, Titletown, on the Grand Rapids leg; this one stands
7.6 miles before it. One sign on every leg into the city, about ten miles
out; the legs leaving Green Bay pass the museum in their first three miles
and get none.

### National Railroad Museum (northbound)
- treatment: billboard
- leg: oshkosh_wi_us -> green_bay_wi_us
- at_mi: 36.0
- spoken: Billboard: The National Railroad Museum, ahead in Green Bay. Its Big Boy steam engine weighs over a million pounds. Suddenly your load feels light.

### National Railroad Museum (northbound)
- treatment: billboard
- leg: madison_wi_us -> green_bay_wi_us
- at_mi: 129.0
- spoken: Billboard: The National Railroad Museum, ahead in Green Bay. Its Big Boy steam engine weighs over a million pounds. Suddenly your load feels light.

### National Railroad Museum (northbound)
- treatment: billboard
- leg: sheboygan_wi_us -> green_bay_wi_us
- at_mi: 52.0
- spoken: Billboard: The National Railroad Museum, ahead in Green Bay. Its Big Boy steam engine weighs over a million pounds. Suddenly your load feels light.

### National Railroad Museum (northbound)
- treatment: billboard
- leg: grand_rapids_mi_us -> green_bay_wi_us
- at_mi: 371.4
- spoken: Billboard: The National Railroad Museum, ahead in Green Bay. Its Big Boy steam engine weighs over a million pounds. Suddenly your load feels light.

### National Railroad Museum (eastbound)
- treatment: billboard
- leg: wausau_wi_us -> green_bay_wi_us
- at_mi: 87.0
- spoken: Billboard: The National Railroad Museum, ahead in Green Bay. Its Big Boy steam engine weighs over a million pounds. Suddenly your load feels light.

### National Railroad Museum (southbound)
- treatment: billboard
- leg: escanaba_mi_us -> green_bay_wi_us
- at_mi: 99.5
- spoken: Billboard: The National Railroad Museum, ahead in Green Bay. Its Big Boy steam engine weighs over a million pounds. Suddenly your load feels light.

## The World's Largest Six-Pack, La Crosse

Six storage tanks, fifty-four feet tall, built by the G. Heileman Brewing
Company in 1969 at what is now City Brewery, on Third Street South in
downtown La Crosse, rewrapped as Old Style cans in 2023 (Wikipedia, "World's
Largest Six-Pack"; travelwisconsin.com; KARE 11). One sign on every leg into
the city.

### World's Largest Six-Pack (eastbound)
- treatment: billboard
- leg: rochester_mn_us -> la_crosse_wi_us
- at_mi: 60.8
- spoken: Billboard: The World's Largest Six-Pack, ahead in La Crosse. Six brewery tanks, fifty-four feet tall, dressed as cans. It is a look-only six-pack.

### World's Largest Six-Pack (southbound)
- treatment: billboard
- leg: winona_mn_us -> la_crosse_wi_us
- at_mi: 16.0
- spoken: Billboard: The World's Largest Six-Pack, ahead in La Crosse. Six brewery tanks, fifty-four feet tall, dressed as cans. It is a look-only six-pack.

### World's Largest Six-Pack (southbound)
- treatment: billboard
- leg: eau_claire_wi_us -> la_crosse_wi_us
- at_mi: 72.5
- spoken: Billboard: The World's Largest Six-Pack, ahead in La Crosse. Six brewery tanks, fifty-four feet tall, dressed as cans. It is a look-only six-pack.

### World's Largest Six-Pack (westbound)
- treatment: billboard
- leg: madison_wi_us -> la_crosse_wi_us
- at_mi: 134.5
- spoken: Billboard: The World's Largest Six-Pack, ahead in La Crosse. Six brewery tanks, fifty-four feet tall, dressed as cans. It is a look-only six-pack.

## Bong Veterans Historical Center, Superior

The Richard I. Bong Veterans Historical Center, 305 East Second Street,
Superior, open daily, with a P-38 Lightning at its center; Bong, born in
Superior and raised on a farm in Poplar, was America's top-scoring fighter
ace of World War Two with forty victories (Wikipedia, "Richard Bong";
campendium.com and gottabesuperior.com listings). The Duluth to Rice Lake
direction passes it in its first four miles and gets none.

### Bong Veterans Historical Center (westbound)
- treatment: billboard
- leg: rice_lake_wi_us -> duluth_mn_us
- at_mi: 81.5
- spoken: Billboard: The Bong Veterans Historical Center, ahead in Superior. Richard Bong, America's top fighter ace of World War Two, was a farm kid from nearby Poplar.

## Colby (Wisconsin 29 at Abbotsford)

Where Joseph Steinwand developed Colby cheese at his father's factory in
1885 and named it for the township; a state historical marker downtown
(Wikipedia, "Colby, Wisconsin"; Clark County history). The town lies about
two miles south of Wisconsin 29 at Abbotsford. These legs list no exits, so
the signs are placed from the Abbotsford checkpoint and read "ahead".

### Colby (eastbound)
- treatment: billboard
- leg: eau_claire_wi_us -> wausau_wi_us
- at_mi: 57.0
- spoken: Billboard: Colby, ahead, just south of the highway. Colby cheese was invented here in eighteen eighty-five, and named for the town, not the other way round.

### Colby (westbound)
- treatment: billboard
- leg: wausau_wi_us -> eau_claire_wi_us
- at_mi: 24.0
- spoken: Billboard: Colby, ahead, just south of the highway. Colby cheese was invented here in eighteen eighty-five, and named for the town, not the other way round.

### Colby (westbound)
- treatment: billboard
- leg: wausau_wi_us -> chippewa_falls_wi_us
- at_mi: 24.0
- spoken: Billboard: Colby, ahead, just south of the highway. Colby cheese was invented here in eighteen eighty-five, and named for the town, not the other way round.

### Colby (eastbound)
- treatment: billboard
- leg: chippewa_falls_wi_us -> wausau_wi_us
- at_mi: 46.0
- spoken: Billboard: Colby, ahead, just south of the highway. Colby cheese was invented here in eighteen eighty-five, and named for the town, not the other way round.

## Notes for the owner

Thirty-two attractions, one hundred ten signs: twenty attractions and
sixty-three signs in Minnesota, twelve attractions and forty-seven signs in
Wisconsin. A dry run of `tools/bake_billboards.py` on this sheet resolves
every leg and bakes all one hundred ten (no `--write`). A spacing check
against the current legs found no callout within 2.2 miles of any sign in
its direction, counting village callouts within a mile and a half of the
road and every other sign on this sheet. Every line is spelled out with no
digits and runs twenty-one to twenty-six words. The jokes are original.

Extended 2026-09-30 on the owner's instruction (no cap): the first fourteen
attractions are unchanged except the Hockey Hall of Fame line, which now
ends "Three on-time deliveries in one day is a hat trick too." The rest were
added from a sweep of every leg with miles in either state.

None of these places has a pool line or a placed sign today. Already
covered and left alone: the Spam Museum and Wall Drug (pool lines), the
Darwin twine ball (placed, Willmar to Minneapolis), Paul Bunyan and Babe in
Bemidji (placed landmark), Lambeau Field (the Titletown sign), the
Harley-Davidson Museum (Milwaukee approach line), and the Hinckley Fire
Museum (an existing museum callout, which Tobies stands clear of).

Attractions, sources, and what was checked:

- **Runestone Museum.** https://www.roadsideamerica.com/story/2607,
  https://explorealex.com/stand-tall-with-big-ole/ and the museum listing at
  206 Broadway (open Monday to Saturday). Found 1898 by Olof Ohman,
  inscription dated 1362. Big Ole stands beside it but is not named in the
  copy, to keep it short; add him if you want the statue in.
- **Tobies.** https://www.minnesotamonthly.com/food-drink/caramel-roll-at-tobies-restaurant-bakery/
  and https://unearththevoyage.com/people-never-drive-to-the-north-shore-without-stopping-at-this-minnesota-bakery/
  (since 1948, 404 Fire Monument Road, Exit 183, about halfway between the
  Twin Cities and Duluth). The northbound sign is eleven miles out because
  Exit 180, the museum callout and the Hinckley village callout fill the
  three miles before Exit 183.
- **Northfield History Center.** https://www.northfieldhistory.org/ (name,
  408 Division Street South, open Tuesday to Sunday) and
  https://kymnradio.net/2026/09/03/northfield-history-center-plans-special-events-for-150th-anniversary-of-the-jesse-james-bank-raid/
  (raid on September 7, 1876; the town stopped it). Distance from
  https://www.carleton.edu/visitors/traveling-by-car/ (seven miles east of
  Exit 69 on Minnesota 19). The copy leaves out this month's
  hundred-fiftieth anniversary, which is already past. Unsure: the History
  Center's site says it is raising money to save the Scriver Building, so
  check the bank rooms stay open before baking.
- **United States Hockey Hall of Fame.** https://ironrange.org/listings/us-hockey-hall-of-fame/
  (801 Hat Trick Avenue, off northbound US 53, open daily) and
  https://www.wdio.com/?p=734212 (board voted to stay in Eveleth). The
  museum's own site, https://www.ushockeyhalloffame.com/, shows the 2026
  induction but no hours.
- **Judy Garland Museum.** https://www.judygarlandmuseum.com/ (2727 South
  Pokegama Avenue, 2026 season; says the stolen slippers have not been there
  since 2005) and https://www.kqed.org/pop/105554/judy-garlands-stolen-ruby-slippers-recovered-by-fbi-after-13-years
  (recovered 2018). Hours from https://www.roadsideamerica.com/tip/11052:
  daily in summer, weekends off-season, so a winter weekday stop finds it
  closed. These legs list no exits, so the signs are placed from the
  Grand Rapids checkpoint and node; the museum is on the south side of town,
  so "ahead in Grand Rapids" holds either way.
- **The Big Fish.** https://en.wikipedia.org/wiki/The_Big_Fish_(roadside_attraction),
  https://www.grandforksherald.com/newsmd/big-fish-resuscitation-endangered-hwy-2-roadside-attraction-gets-rehab-work
  (2009 restoration) and
  https://www.cbsnews.com/amp/minnesota/news/enjoy-a-big-supper-inside-a-big-fish-at-the-big-fish-supper-club
  (supper club beside it, open Wednesday to Saturday, July 2023). Unsure:
  nothing newer than 2023 confirms the supper club, but the fish itself
  stands at the roadside, and the copy is about the fish. Sources disagree
  on 1957 or 1958, so the copy says "the nineteen fifties".
- **Garrison walleye.** https://www.roadsideamerica.com/tip/6737 and
  https://en.wikipedia.org/wiki/Garrison_Concourse (nineteen feet, out since
  1980, the Paul Bunyan plaque) and
  https://www.brainerddispatch.com/news/local/mille-lacs-walleye-sports-a-fresh-look-in-complete-remodel
  (repainted late 2023). The copy names Paul Bunyan only as the plaque's
  claim; it is a different statue from the Bemidji one.
- **Wisconsin Dells.** https://www.wisconsinducktours.com/ (since 1946,
  World War Two era amphibious vehicles, mid-March to mid-November, 2026
  site) and https://www.dells.com/listing/original-wisconsin-ducks. The
  sign is about the town and stays true when the ducks are off for the
  winter. One to weigh: the joke is about trucks driving into a river; it
  says nothing of the 2018 Branson duck boat sinking, but if that
  association bothers you, the backup is "The waterparks are indoors, so it
  is summer here all year."
- **Mars Cheese Castle.** https://www.marscheese.com/ (2800 West Frontage
  Road, open daily) and https://en.wikipedia.org/wiki/Mars_Cheese_Castle
  (1947; the 2011 castle with turrets, a drawbridge entrance and a
  watchtower) and https://www.roadsideamerica.com/tip/8445 (Exit 340,
  southwest side). Seven signs, because three through legs and the Kenosha
  leg all pass it. The Chicago to Milwaukee sign is seven miles out ("ahead
  in Kenosha"), because that leg's Des Plaines River callout sits two and a
  half miles before Exit 340.
- **Ehlenbach's Cheese Chalet.** https://ehlenbachscheese.com/ (4879 County
  Road V, open daily, over two hundred thirty cheeses, "Sissy The Cow") and
  https://www.visitmadison.com/listings/ehlenbachs-cheese-chalet/178660/
  (Exit 126, ten miles north of Madison). Roadside America spells the cow
  both Sissie and Sissy; the store says Sissy. Six signs over three legs.
  On Madison to La Crosse the sign is three miles before the exit, because
  the Windsor callout sits a mile before it. The westbound Milwaukee to
  Minneapolis sign and the northbound Madison to Wausau sign read "ahead in
  DeForest" for the same reason.
- **EAA Aviation Museum.** https://eaa.org/eaa-museum/visitor-information/directions-to-the-museum
  (Exit 116, Wisconsin 44) and https://www2.eaa.org/eaa-museum/visitor-information/hours-of-operation
  (open daily) and
  https://www.aviationpros.com/airport-business/airside-operations-area/press-release/55306274/eaa-airventure-oshkosh-2025-sets-records
  (more than ten thousand aircraft into the area for AirVenture 2025).
  Unsure: Exit 116 is in no leg's interchange list, so its milepost is
  estimated a mile south of Exit 117. The northbound "next exit" signs are
  about a mile before that estimate. "EAA" is spoken as a name; screen
  readers should spell it out as letters, but it is worth one listen.
- **Wisconsin Maritime Museum.** https://www.wisconsinmaritime.org/ (open
  daily; Cobia tours listed for October 2026; 2025 dry dock) and
  https://www.roadsideamerica.com/tip/10092 (Exit 152, then Waldo Boulevard
  east). Twenty-eight submarines and the river route:
  https://www.wisconsinhistory.org/Records/Article/CS10193 and
  https://www.usni.org/magazines/naval-history-magazine/2008/october/those-stout-manitowoc-boats.
  The museum is about four miles off I-43.
- **Sparta.** https://en.wikipedia.org/wiki/Elroy-Sparta_State_Trail and
  https://TravelWisconsin.com/article/linear-bike-trails/the-elroy-sparta-state-trail-americas-first-rails-to-trails-project
  (opened 1967, first rail trail, the long tunnel is about three-quarters of
  a mile, 3,810 feet); https://dekeslaytonmuseum.org/visit-us/ (open
  Tuesday to Saturday). The trail's tunnels close November 1 to April 30
  (Wisconsin DNR, via the trail's Wikipedia article), so the
  copy says only where the trail begins and how long the tunnel is, not
  that you can ride it today.
- **Norske Nook.** https://www.norskenook.com/ (13804 Seventh Street, Osseo,
  open daily, since 1973, hand-rolled crusts, award-winning pies).

Added in the extension, Minnesota:

- **Frank Lloyd Wright gas station, Cloquet.** https://en.wikipedia.org/wiki/R._W._Lindholm_Service_Station
  and https://www.northernnewsnow.com/2025/06/06/historic-frank-lloyd-wright-gas-station-still-serves-community/
  (built 1958, the only Wright gas station built in his lifetime, still a
  full-service station and repair shop). Wright designed one more that
  was built in Buffalo in 2014, after his death, which is why the copy says
  "in his lifetime".
- **Aerial Lift Bridge, Duluth.** https://en.wikipedia.org/wiki/Aerial_Lift_Bridge
  (1905, lift span 1929 and 1930, 135 feet in about a minute, about five
  thousand lifts a year, long-short-long-short asks for a lift). Five signs,
  one per leg into Duluth.
- **Pine City voyageur.** https://kstp.com/?p=2826267 (August 8, 2022: 45
  feet, redwood log from California in the 1930s, carved by Dennis Roghair)
  and https://www.roadsideamerica.com/tip/736. Unsure: nothing newer than
  2022 shows it, though a 2026 historical marker stands in the same park
  (hmdb.org). Barnum's Big Louis, a twenty-five-foot voyageur at I-35 Exit
  220, was left out as the smaller of two voyageurs on the same road.
- **Faribault Woolen Mill.** https://www.exploreminnesota.com/profile/faribault-woolen-mill-co/5087
  and https://www.familyfuntwincities.com/directory/faribault-woolen-mill
  (1865, Exit 59 and Minnesota 21, store Monday to Saturday). The mill
  closed in 2009 and reopened in 2011 under new owners
  (fibre2fashion.com), so "since eighteen sixty-five" is the mill's age,
  not an unbroken run.
- **Sauk Centre.** https://en.wikipedia.org/wiki/Main_Street_(novel) and
  https://en.wikipedia.org/wiki/Original_Main_Street_Historic_District
  (National Register, 1994) and
  https://www.mprnews.org/story/2018/07/02/sauk-centre-minn-sinclair-lewis-legacy.
  The boyhood home keeps short hours and opens by appointment off-season
  (whichmuseum.com), so the copy is about the town.
- **Otto the Otter.** https://www.roadsideamerica.com/story/2713 and
  https://ottertaillakescountry.com/blog/snap-a-selfie-with-otto-the-otter/
  (forty feet, concrete over metal, 1972 centennial, 1.6 miles from Exit 55).
- **World's Largest Prairie Chicken.** https://www.roadsideamerica.com/tip/2712
  (thirteen feet, nine thousand pounds, Art Fosse, 1976, over the Rothsay
  exit ramp). "World's largest" is the statue's own name.
- **Hjemkomst Center.** https://en.wikipedia.org/wiki/Hjemkomst_Center
  (Robert Asp, guidance counselor at Moorhead Junior High; built from 1974
  in the Leslie Welter Potato Warehouse in Hawley; sailed to Norway in 1982)
  and https://www.moorheadmn.gov/parks-rec/hjemkomst-center (open daily).
- **Big Tom.** https://www.roadsideamerica.com/tip/2130 and
  https://www.roadsideamerica.com/news/5322 (twenty feet, the 1986 turkey
  burned in 1998 during a secret renovation, replaced that year). This leg
  has no exit list and its dense geometry is off (see below), so both signs
  are placed from the Frazee village callout.
- **Zumbrota Covered Bridge.** https://en.wikipedia.org/wiki/Zumbrota_Covered_Bridge
  and https://www.dot.state.mn.us/historicbridges/25580.html (1869, moved
  1932 and 1997). The leg's North Fork Zumbro River callout is seven miles
  from its Zumbrota checkpoint, though the river runs through town; the
  signs keep clear of both.
- **Minneopa State Park bison.** https://www-dev.dnr.state.mn.us/state_parks/minneopa/bison.html
  and the Southern Minn Scene and Mankato Free Press pieces (331-acre range,
  stay in your vehicle, closed Wednesdays, winter hours from November 1).
- **Verne the Patriot, Luverne.** https://www.fox9.com/news/luverne-minnesotas-65-foot-nutcracker-july-1-2026
  (65 feet, finished mid-June 2026, a block from I-90, Betty Mann's 7,000
  nutcrackers outnumber the town) and https://www.ksl.com/article/51600201/a-minnesota-town-now-boasts-the-worlds-tallest-nutcracker-its-pieces-were-crafted-in-utah
  (named Verne the Patriot) and https://www.roadsideamerica.com/tip/92731
  (924 South Kniss Avenue). Guinness has not certified it, so the copy
  claims no record. On the two Mankato legs, which list no exits, Exit 12
  is placed by the Sioux Falls to Minneapolis leg's spacing.
- **Hull Rust Mine View.** https://hibbingmineview.org/hull-rust-mine-view/
  (open daily year-round; 1918 move of 185 houses and 20 businesses two
  miles south).

Added in the extension, Wisconsin:

- **Kohler Design Center.** https://www.travelwisconsin.com/tours/kohler-design-center-203510
  (open daily, free) and https://origin-www.destinationkohler.com/getting-here
  (Exit 126, Wisconsin 23 west, County Y).
- **National Railroad Museum.** https://www.travelwisconsin.com/things-to-do/culture-arts/museums-history/national-railroad-museum
  and https://nationalrrmuseum.org/ (open daily April to December, closed
  Mondays January to March; Big Boy 4017, about 1.1 million pounds;
  Eisenhower's command train). Six signs, one per leg into Green Bay.
- **World's Largest Six-Pack.** https://en.wikipedia.org/wiki/World%27s_Largest_Six-Pack
  and https://kare11.com/article/news/local/land-of-10000-stories/la-crosses-worlds-largest-six-pack-back-as-old-style-brewing-returns-to-gods-country/89-60ab55a6-c8aa-4c3c-ac6b-62ce86d6ffb2
  (1969, fifty-four feet, rewrapped as Old Style cans in 2023). It is a
  brewery landmark; the copy calls it "look-only" and names no beer. Cut
  it if beer is out of bounds.
- **Bong Veterans Historical Center.** https://en.wikipedia.org/wiki/Richard_Bong
  and https://maps.campendium.com/us/superior-wi/attractions/richard-i-bong-veterans-historical-center
  (305 East Second Street, open daily, P-38 inside). The copy shortens the
  name to "The Bong Veterans Historical Center", so a screen reader does
  not read "Richard I." as "Richard the first". No joke, by choice.
- **Colby.** https://en.wikipedia.org/wiki/Colby,_Wisconsin and
  https://www.wiclarkcountyhistory.org/0data/3/3779.htm (1885, Joseph
  Steinwand, named for the township; marker downtown). Colby is about two
  miles south of Wisconsin 29 by the dense geometry.

Dropped:

- **Minnesota's Largest Candy Store, Jordan (US 169).** Open now, but it
  closes November 1, 2026 to move across the highway into a new building
  twice the size, reopening in May 2027 if construction keeps to plan
  (Star Tribune via AOL; minnesotaslargestcandystore.com). A sign baked this
  week would describe a store that is shut for half a year and then
  replaced. Worth signing next spring, on the Mankato to Minneapolis and
  Sioux Falls to Minneapolis legs.
- **Jolly Green Giant, Blue Earth.** No leg passes it: the Sioux Falls to
  Minneapolis leg leaves I-90 at Worthington for Minnesota 60.
- **House on the Rock, Circus World, the National Mustard Museum.** More
  than five miles from every leg (Spring Green, Baraboo, Middleton).
- **Paul Bunyan and Babe, Lambeau Field, the Spam Museum, the Darwin twine
  ball, the Hinckley Fire Museum, the Harley-Davidson Museum.** Already
  signed or called out.
- **Greyhound Bus Museum, Hibbing.** Season mid-May through September
  (ironrange.org), so it is closed from tomorrow. The Hull Rust Mine View
  covers Hibbing.
- **Jelly Belly, Pleasant Prairie.** Its warehouse tour and store closed in
  August 2020 (FOX6; Roadside America).
- **Wisconsin Cranberry Discovery Center, Warrens.** Closed permanently,
  April 2026 (Roadside America).
- **Peshtigo Fire Museum (US 41).** Its season ends October 8 (Peshtigo
  Historical Society), a week from now.
- **Snake River Fur Post, Pine City.** Minnesota Historical Society site,
  open Memorial Day to Labor Day and Saturdays in September only.
- **Paul Bunyan Land, Brainerd; International Crane Foundation, Baraboo;
  Valleyfair, Shakopee; Little Chute Windmill.** Summer or fall seasons
  that end within weeks, and Brainerd's Bunyan would sit beside the Bemidji
  one.
- **History Museum at the Castle (Houdini), Appleton.** The Oshkosh to Green
  Bay leg already calls it out as "Appleton History Museum ahead".
- **Pink Elephant, DeForest; Grand Casino Hinckley.** Same exits as
  Ehlenbach's and Tobies, too close for a second sign; the better-known
  stop kept each slot.
- **Big Orange Moose, Black River Falls (I-94 Exit 116).** Last confirmed by
  a visitor in April 2022, on private motel grounds, and that leg's exit
  list near Black River Falls is mislabeled (see below), so its milepost
  cannot be placed honestly.
- **Seymour, Home of the Hamburger.** More than six miles from Wisconsin 29.
- **Mabel Tainter theater, Menomonie.** Tours Friday and Saturday afternoons
  only; a smaller draw than anything kept.
- **Hormel chili can, Beloit.** A tank you look at from I-90; nothing to say
  that does not need a picture.
- **Leinenkugel's, Chippewa Falls; Stevens Point Brewery.** Brewery tours;
  left out.

Found along the way (data, not this sheet): the dense route geometry
(`data/world_data/us/geometry`) for Hibbing to Minneapolis runs east to I-35
through Hinckley, while the leg's own route points, checkpoints and
landmarks follow US 169 through Grand Rapids and Garrison. The Duluth to
Fargo geometry likewise passes the Big Fish on US 2 while its landmarks run
through Brainerd. These signs follow the route points and landmarks. On I-94
near Alexandria the Chippewa River callout is at Exit 100 on Fargo to
Minneapolis but three and a half miles west of it on St. Cloud to Fargo. On
Milwaukee to Minneapolis, the interchanges at miles 190.5 and 196.1, by
Black River Falls, carry Madison exit numbers and names (250 Radio Drive,
244 Sun Prairie). I-35 Exit 237 (Minnesota 33, Cloquet) and I-41 Exit 116
(Wisconsin 44, Oshkosh) are missing from every leg's interchange list.
