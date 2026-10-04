
# Colorado, Washington and North Dakota attractions, both directions -- 2026-09-30

DRAFT for the owner's approval. Thirty-four real roadside attractions across
the three states, each signed in every direction a leg passes it where the
state's billboard law allows a sign there. Every `leg:` is written the way the
driver reads the sign and `at_mi` counts from that end;
`tools/bake_billboards.py` mirrors the milepost onto a leg stored the other
way round and records which way the billboard faces.

Mileposts come from the legs' interchange lists (the attraction's exit and
the one before it) and, where a leg has no interchange list, from its
villages and checkpoints and from projecting the attraction onto the leg's
dense route geometry. "Next exit" signs stand between the attraction's exit
and the exit before it; "ahead" signs about seven to fifteen miles out, or
closer where the next exit is not the attraction's. Each sits at least 2.2
miles from every other callout heard in the same direction (rivers, passes,
museums, forests, villages within a mile and a half of the road, and the
other signs on this sheet), so the landmark spacing does not drop it.

Billboard law, checked per state. North Dakota (NDCC 24-17, NDDOT permits)
and Colorado (C.R.S. 43-1-401 and CDOT's rules) permit commercial off-premise
boards along interstates and primary routes in commercial and industrial
areas. Both bar new boards on designated scenic byways: North Dakota by NDDOT
rule, Colorado since 2021 (SB21-263). Nothing here stands on a byway. Washington (RCW 47.42) permits them except
where visible from the scenic system (RCW 47.39.020), which takes in I-90
from Issaquah to Thorp Road, all of US 195 and US 101 from Queets around to
Olympia; nothing here stands on those.

## North Dakota

## Salem Sue, New Salem (I-94 Exit 127)

The world's largest Holstein cow: fiberglass, 38 feet high and 50 feet long,
built in 1974 by the New Salem Lions Club, on School Hill south of I-94 Exit
127 (Wikipedia, "Salem Sue"; Roadside America).

### Salem Sue (westbound)
- treatment: billboard
- leg: bismarck_nd_us -> dickinson_nd_us
- at_mi: 29.5
- spoken: Billboard: Salem Sue, the world's largest Holstein cow, next exit at New Salem. Thirty-eight feet of fiberglass on a hill. Nobody has tried to milk her.

### Salem Sue (eastbound)
- treatment: billboard
- leg: dickinson_nd_us -> bismarck_nd_us
- at_mi: 65.5
- spoken: Billboard: Salem Sue, the world's largest Holstein cow, next exit at New Salem. Thirty-eight feet of fiberglass on a hill. Nobody has tried to milk her.

## The Enchanted Highway, Gladstone (I-94 Exit 72)

Seven giant scrap-metal sculptures by Gary Greff along the 32 miles from I-94
Exit 72 to Regent; "Geese in Flight", at the exit and visible from the
interstate, was listed by Guinness in 2002 as the world's largest scrap-metal
sculpture (ndtourism.com; Roadside America).

### Enchanted Highway (westbound)
- treatment: billboard
- leg: bismarck_nd_us -> dickinson_nd_us
- at_mi: 84.0
- spoken: Billboard: The Enchanted Highway, next exit. Thirty-two miles of giant scrap-metal sculptures. The geese at the exit set a world record and never flew south.

### Enchanted Highway (eastbound)
- treatment: billboard
- leg: dickinson_nd_us -> bismarck_nd_us
- at_mi: 9.5
- spoken: Billboard: The Enchanted Highway, next exit. Thirty-two miles of giant scrap-metal sculptures. The geese at the exit set a world record and never flew south.

## Theodore Roosevelt Presidential Library, Medora (I-94 Exit 24 from the west, Exit 27 from the east)

Opened July 4, 2026, open year-round, at 3410 Chateau Road on the edge of the
national park; a living roof planted with native prairie (trlibrary.com
directions; nd.gov; Cowboy State Daily, August 2026; Deseret News).

### Theodore Roosevelt Presidential Library (eastbound)
- treatment: billboard
- leg: glendive_mt_us -> dickinson_nd_us
- at_mi: 58.5
- spoken: Billboard: The Theodore Roosevelt Presidential Library, next exit in Medora. The roof is planted with native prairie. Please do not graze the library.

### Theodore Roosevelt Presidential Library (westbound)
- treatment: billboard
- leg: dickinson_nd_us -> glendive_mt_us
- at_mi: 33.0
- spoken: Billboard: The Theodore Roosevelt Presidential Library, next exit in Medora. The roof is planted with native prairie. Please do not graze the library.

## Theodore Roosevelt National Park, Painted Canyon (I-94 Exit 32)

The South Unit's overlook and visitor center, six miles east of Medora right
off I-94 Exit 32 (nps.gov/thro). The overlook is open all year; the visitor
center is seasonal, generally May to October.

### Painted Canyon (eastbound)
- treatment: billboard
- leg: glendive_mt_us -> dickinson_nd_us
- at_mi: 67.5
- spoken: Billboard: Theodore Roosevelt National Park, Painted Canyon, next exit. The badlands open up right off the interstate. The bison have the right of way.

### Painted Canyon (westbound)
- treatment: billboard
- leg: dickinson_nd_us -> glendive_mt_us
- at_mi: 27.6
- spoken: Billboard: Theodore Roosevelt National Park, Painted Canyon, next exit. The badlands open up right off the interstate. The bison have the right of way.

## Theodore Roosevelt National Park, North Unit (US 85)

The North Unit entrance is on US 85 about fourteen miles south of Watford City;
bison, mule deer and bighorn sheep, and the park calls it the less-visited
unit (nps.gov/thro, "North Unit").

### Theodore Roosevelt National Park North Unit (northbound)
- treatment: billboard
- leg: dickinson_nd_us -> williston_nd_us
- at_mi: 60.5
- spoken: Billboard: Theodore Roosevelt National Park, North Unit, ahead on this highway. Badlands, bison, and bighorn sheep, and hardly anybody else. The bison prefer it that way.

### Theodore Roosevelt National Park North Unit (southbound)
- treatment: billboard
- leg: williston_nd_us -> dickinson_nd_us
- at_mi: 50.0
- spoken: Billboard: Theodore Roosevelt National Park, North Unit, ahead on this highway. Badlands, bison, and bighorn sheep, and hardly anybody else. The bison prefer it that way.

## Sandy, the World's Largest Sandhill Crane, Steele (I-94 Exit 200)

A 40-foot rolled sheet-metal crane built in 1998 and 1999 by ironworker James
Miller, just south of Exit 200 behind the Cobblestone Inn, kept up by a local
foundation (Roadside America tip 1834).

### Sandy the Sandhill Crane (eastbound)
- treatment: billboard
- leg: bismarck_nd_us -> jamestown_nd_us
- at_mi: 40.8
- spoken: Billboard: Sandy, the world's largest sandhill crane, next exit at Steele. Forty feet of sheet metal. The real cranes only pass through.

### Sandy the Sandhill Crane (westbound)
- treatment: billboard
- leg: jamestown_nd_us -> bismarck_nd_us
- at_mi: 56.5
- spoken: Billboard: Sandy, the world's largest sandhill crane, next exit at Steele. Forty feet of sheet metal. The real cranes only pass through.

## The World's Largest Buffalo, Jamestown (I-94 Exit 258)

"Dakota Thunder", 26 feet tall and 60 tons of concrete over steel, on the
hill since 1959, beside the National Buffalo Museum's live herd and Frontier
Village (ndtourism.com). It stands at the Jamestown city node, so the signs
are "ahead" ones before the city; nothing stands before it on legs that
start in Jamestown.

### World's Largest Buffalo (eastbound)
- treatment: billboard
- leg: bismarck_nd_us -> jamestown_nd_us
- at_mi: 91.9
- spoken: Billboard: The world's largest buffalo, ahead in Jamestown. Sixty tons of concrete, on the hill since nineteen fifty-nine. The live herd next door gets around more.

### World's Largest Buffalo (westbound)
- treatment: billboard
- leg: fargo_nd_us -> jamestown_nd_us
- at_mi: 82.0
- spoken: Billboard: The world's largest buffalo, ahead in Jamestown. Sixty tons of concrete, on the hill since nineteen fifty-nine. The live herd next door gets around more.

## The Woodchipper from Fargo, Fargo-Moorhead Visitors Center (I-94 Exit 348)

The original prop from the 1996 film, on display at 2001 44th Street South,
off I-94 Exit 348; open daily (fargomoorhead.org; Roadside America). Eastbound
only: the westbound leg starts at the Fargo node three miles east of it, and
the legs from Minnesota and on I-29 end before they reach it.

### Fargo Woodchipper (eastbound)
- treatment: billboard
- leg: jamestown_nd_us -> fargo_nd_us
- at_mi: 78.5
- spoken: Billboard: The woodchipper from the movie Fargo, ahead at the Fargo visitors center. The actual prop. It has retired from show business, and from yard work.

## Bonanzaville, West Fargo (I-94 Exit 343)

The Cass County Historical Society's pioneer village, 34 historic buildings,
1351 Main Avenue West; open daily through October 12, 2026 (bonanzaville.org).
Eastbound only: westbound, Exit 343 is under eight miles from the Fargo node
with West Fargo's own callout in between.

### Bonanzaville (eastbound)
- treatment: billboard
- leg: jamestown_nd_us -> fargo_nd_us
- at_mi: 85.0
- spoken: Billboard: Bonanzaville, next exit in West Fargo. A pioneer village of thirty-four old buildings. The settlers had no air conditioning and no complaints department.

## Geographical Center of North America marker, Rugby (US 2 and ND 3)

A stone obelisk raised in 1931 and moved a short way in 1971 when US 2 was
widened, at the southeast corner of US 2 and ND 3. The USGS puts the true
point about fifteen miles away (Wikipedia, "Rugby, North Dakota").

### Rugby Center of North America (eastbound)
- treatment: billboard
- leg: minot_nd_us -> devils_lake_nd_us
- at_mi: 54.0
- spoken: Billboard: Rugby, ahead, and its stone marker for the center of North America. The true spot is about fifteen miles off. Close enough for a monument.

### Rugby Center of North America (westbound)
- treatment: billboard
- leg: devils_lake_nd_us -> minot_nd_us
- at_mi: 47.0
- spoken: Billboard: Rugby, ahead, and its stone marker for the center of North America. The true spot is about fifteen miles off. Close enough for a monument.

## Lewis & Clark Interpretive Center, Washburn (US 83 and ND 200A)

State Historical Society site at 2576 8th Street SW, Washburn; admission
includes Fort Mandan, the replica of the fort where the expedition wintered
in 1804 and 1805, two miles west. Open daily in summer, Tuesday to Saturday
October to April (history.nd.gov).

### Lewis and Clark Interpretive Center (northbound)
- treatment: billboard
- leg: bismarck_nd_us -> minot_nd_us
- at_mi: 30.0
- spoken: Billboard: The Lewis and Clark Interpretive Center, ahead at Washburn. The expedition spent the winter of eighteen oh-four nearby, with no heater at all.

### Lewis and Clark Interpretive Center (southbound)
- treatment: billboard
- leg: minot_nd_us -> bismarck_nd_us
- at_mi: 61.0
- spoken: Billboard: The Lewis and Clark Interpretive Center, ahead at Washburn. The expedition spent the winter of eighteen oh-four nearby, with no heater at all.

## Colorado

## Red Rocks Park and Amphitheatre, Morrison (I-70 Exit 259)

A stage between two 300-foot sandstone monoliths, Ship Rock and Creation
Rock; the park is free by day and open from an hour before sunrise to an
hour after sunset; the visitor center is closed for construction
(redrocksonline.com). Westbound the next exit after each sign is C-470, so
those read "ahead".

### Red Rocks (westbound)
- treatment: billboard
- leg: denver_co_us -> silverthorne_co_us
- at_mi: 11.0
- spoken: Billboard: Red Rocks Amphitheatre, ahead at Morrison. The stage sits between two sandstone rocks three hundred feet tall. The rocks have heard everybody.

### Red Rocks (westbound)
- treatment: billboard
- leg: denver_co_us -> salt_lake_city_ut_us
- at_mi: 8.5
- spoken: Billboard: Red Rocks Amphitheatre, ahead at Morrison. The stage sits between two sandstone rocks three hundred feet tall. The rocks have heard everybody.

### Red Rocks (eastbound)
- treatment: billboard
- leg: silverthorne_co_us -> denver_co_us
- at_mi: 51.5
- spoken: Billboard: Red Rocks Amphitheatre, next exit at Morrison. The stage sits between two sandstone rocks three hundred feet tall. The rocks have heard everybody.

### Red Rocks (eastbound)
- treatment: billboard
- leg: salt_lake_city_ut_us -> denver_co_us
- at_mi: 475.0
- spoken: Billboard: Red Rocks Amphitheatre, next exit at Morrison. The stage sits between two sandstone rocks three hundred feet tall. The rocks have heard everybody.

## Buffalo Bill Museum and Grave, Lookout Mountain (I-70 Exit 256 westbound, Exit 254 eastbound)

987 1/2 Lookout Mountain Road, Golden; the museum is open daily May to
October and Tuesday to Sunday in winter, the grave daily (buffalobill.org,
whose directions send westbound drivers off at Exit 256 and eastbound drivers
off at Exit 254). In 1948 Cody, Wyoming's American Legion post offered a
reward to anyone who would bring the body to Cody, and Denver's post mounted
a guard over the grave (Wikipedia, "Buffalo Bill"; 5280 magazine says the
National Guard, so the copy says only "a guard").

### Buffalo Bill's Grave (westbound)
- treatment: billboard
- leg: denver_co_us -> silverthorne_co_us
- at_mi: 14.5
- spoken: Billboard: Buffalo Bill's grave, next exit on Lookout Mountain. A group in Cody, Wyoming once offered a reward to steal him back. Denver posted a guard.

### Buffalo Bill's Grave (westbound)
- treatment: billboard
- leg: denver_co_us -> salt_lake_city_ut_us
- at_mi: 14.3
- spoken: Billboard: Buffalo Bill's grave, next exit on Lookout Mountain. A group in Cody, Wyoming once offered a reward to steal him back. Denver posted a guard.

### Buffalo Bill's Grave (eastbound)
- treatment: billboard
- leg: silverthorne_co_us -> denver_co_us
- at_mi: 46.5
- spoken: Billboard: Buffalo Bill's grave, next exit on Lookout Mountain. A group in Cody, Wyoming once offered a reward to steal him back. Denver posted a guard.

### Buffalo Bill's Grave (eastbound)
- treatment: billboard
- leg: salt_lake_city_ut_us -> denver_co_us
- at_mi: 469.8
- spoken: Billboard: Buffalo Bill's grave, next exit on Lookout Mountain. A group in Cody, Wyoming once offered a reward to steal him back. Denver posted a guard.

## Georgetown Loop Railroad (I-70 Exits 228 and 226)

The 1884 narrow-gauge line climbs between Georgetown and Silver Plume, two
miles apart, on four and a half miles of track over the Devil's Gate High
Bridge (Wikipedia); depots at Devil's Gate (Exit 228) and Silver Plume (Exit
226); running in 2026 with holiday trains on sale (georgetownlooprr.com).
Signs read "ahead" because Empire, Silver Plume and the passes leave no clear
slot before either exit.

### Georgetown Loop Railroad (westbound)
- treatment: billboard
- leg: denver_co_us -> silverthorne_co_us
- at_mi: 35.5
- spoken: Billboard: The Georgetown Loop Railroad, ahead. Georgetown and Silver Plume are two miles apart. The train takes four and a half, and nobody aboard minds.

### Georgetown Loop Railroad (westbound)
- treatment: billboard
- leg: denver_co_us -> salt_lake_city_ut_us
- at_mi: 33.5
- spoken: Billboard: The Georgetown Loop Railroad, ahead. Georgetown and Silver Plume are two miles apart. The train takes four and a half, and nobody aboard minds.

### Georgetown Loop Railroad (eastbound)
- treatment: billboard
- leg: silverthorne_co_us -> denver_co_us
- at_mi: 14.5
- spoken: Billboard: The Georgetown Loop Railroad, ahead. Georgetown and Silver Plume are two miles apart. The train takes four and a half, and nobody aboard minds.

### Georgetown Loop Railroad (eastbound)
- treatment: billboard
- leg: salt_lake_city_ut_us -> denver_co_us
- at_mi: 437.5
- spoken: Billboard: The Georgetown Loop Railroad, ahead. Georgetown and Silver Plume are two miles apart. The train takes four and a half, and nobody aboard minds.

## Old Town Hot Springs, Steamboat Springs (US 40)

136 Lincoln Avenue, open every day but Thanksgiving and Christmas
(oldtownhotsprings.org). Trappers named the place for a spring whose chugging
they took for a steamboat coming down the river (Wikipedia, "Steamboat
Springs, Colorado").

### Old Town Hot Springs (westbound)
- treatment: billboard
- leg: denver_co_us -> salt_lake_city_ut_us
- at_mi: 145.0
- spoken: Billboard: Old Town Hot Springs, ahead in Steamboat Springs. The name comes from a spring that chugged like a steamboat. Trappers went looking for the boat.

### Old Town Hot Springs (eastbound)
- treatment: billboard
- leg: salt_lake_city_ut_us -> denver_co_us
- at_mi: 324.0
- spoken: Billboard: Old Town Hot Springs, ahead in Steamboat Springs. The name comes from a spring that chugged like a steamboat. Trappers went looking for the boat.

## Glenwood Hot Springs, Glenwood Springs (I-70 Exit 116)

The world's largest hot springs pool, opened 1888, 405 feet long, about a
million gallons kept near ninety degrees; open 365 days (hotspringspool.com
fact sheet). It is at the Glenwood Springs node, so the signs stand before
the city on the legs that end there.

### Glenwood Hot Springs (westbound)
- treatment: billboard
- leg: edwards_co_us -> glenwood_springs_co_us
- at_mi: 38.0
- spoken: Billboard: Glenwood Hot Springs, ahead. The world's largest hot springs pool, since eighteen eighty-eight. A million gallons, and not one of them cold.

### Glenwood Hot Springs (eastbound)
- treatment: billboard
- leg: grand_junction_co_us -> glenwood_springs_co_us
- at_mi: 78.5
- spoken: Billboard: Glenwood Hot Springs, ahead. The world's largest hot springs pool, since eighteen eighty-eight. A million gallons, and not one of them cold.

## Colorado National Monument, Grand Junction (US 50 approach)

Established 1911; its first ranger, John Otto, built its trails and was paid a
dollar a month (Wikipedia). Only the Delta to Grand Junction leg passes it
off a byway: I-70 west of Grand Junction is the Dinosaur Diamond byway.

### Colorado National Monument (northbound)
- treatment: billboard
- leg: delta_co_us -> grand_junction_co_us
- at_mi: 30.5
- spoken: Billboard: Colorado National Monument, ahead past Grand Junction. Its first ranger, John Otto, built the trails and was paid a dollar a month. You make more.

## The World's Wonder View Tower, Genoa (I-70 Exit 371)

Built in 1926, 65 feet tall, long advertised as showing six states from the
top; closed 2013 and reopened in 2026 after a restoration by Friends of the
Genoa Tower as an art museum (Wikipedia; Denver Gazette, September 23, 2026).
Seasonal: the 2026 season ended September 26. South Dakota's nearest corner
is about 255 miles away by the map.

### Wonder View Tower (westbound)
- treatment: billboard
- leg: burlington_co_us -> denver_co_us
- at_mi: 64.8
- spoken: Billboard: The World's Wonder View Tower, next exit in Genoa. It claims six states from the top. South Dakota is over two hundred fifty miles off.

### Wonder View Tower (westbound)
- treatment: billboard
- leg: kansas_city_mo_us -> denver_co_us
- at_mi: 499.6
- spoken: Billboard: The World's Wonder View Tower, next exit in Genoa. It claims six states from the top. South Dakota is over two hundred fifty miles off.

### Wonder View Tower (eastbound)
- treatment: billboard
- leg: denver_co_us -> burlington_co_us
- at_mi: 97.5
- spoken: Billboard: The World's Wonder View Tower, next exit in Genoa. It claims six states from the top. South Dakota is over two hundred fifty miles off.

### Wonder View Tower (eastbound)
- treatment: billboard
- leg: denver_co_us -> kansas_city_mo_us
- at_mi: 97.5
- spoken: Billboard: The World's Wonder View Tower, next exit in Genoa. It claims six states from the top. South Dakota is over two hundred fifty miles off.

## Garden of the Gods, Colorado Springs (I-25 Exit 146)

Free park and visitor center; the Perkins family gave it to the city in 1909
on condition it stay "a free and public park forever"; Exit 146, Garden of
the Gods Road (gardenofgods.com). Northbound signs stand south of the city on
the legs from Pueblo; the legs that start in Colorado Springs reach Exit 146
four miles out, too close to stand a sign before it.

### Garden of the Gods (northbound)
- treatment: billboard
- leg: pueblo_co_us -> denver_co_us
- at_mi: 40.5
- spoken: Billboard: Garden of the Gods, ahead. Red rock towers, given to the city in nineteen oh-nine on condition it stay free forever. The rocks agreed.

### Garden of the Gods (northbound)
- treatment: billboard
- leg: pueblo_co_us -> cheyenne_wy_us
- at_mi: 40.5
- spoken: Billboard: Garden of the Gods, ahead. Red rock towers, given to the city in nineteen oh-nine on condition it stay free forever. The rocks agreed.

### Garden of the Gods (northbound)
- treatment: billboard
- leg: pueblo_co_us -> fort_collins_co_us
- at_mi: 40.5
- spoken: Billboard: Garden of the Gods, ahead. Red rock towers, given to the city in nineteen oh-nine on condition it stay free forever. The rocks agreed.

### Garden of the Gods (southbound)
- treatment: billboard
- leg: denver_co_us -> colorado_springs_co_us
- at_mi: 55.5
- spoken: Billboard: Garden of the Gods, ahead. Red rock towers, given to the city in nineteen oh-nine on condition it stay free forever. The rocks agreed.

### Garden of the Gods (southbound)
- treatment: billboard
- leg: fort_collins_co_us -> colorado_springs_co_us
- at_mi: 119.4
- spoken: Billboard: Garden of the Gods, ahead. Red rock towers, given to the city in nineteen oh-nine on condition it stay free forever. The rocks agreed.

### Garden of the Gods (southbound)
- treatment: billboard
- leg: denver_co_us -> pueblo_co_us
- at_mi: 55.0
- spoken: Billboard: Garden of the Gods, ahead. Red rock towers, given to the city in nineteen oh-nine on condition it stay free forever. The rocks agreed.

### Garden of the Gods (southbound)
- treatment: billboard
- leg: fort_collins_co_us -> pueblo_co_us
- at_mi: 119.9
- spoken: Billboard: Garden of the Gods, ahead. Red rock towers, given to the city in nineteen oh-nine on condition it stay free forever. The rocks agreed.

### Garden of the Gods (southbound)
- treatment: billboard
- leg: cheyenne_wy_us -> pueblo_co_us
- at_mi: 156.8
- spoken: Billboard: Garden of the Gods, ahead. Red rock towers, given to the city in nineteen oh-nine on condition it stay free forever. The rocks agreed.

## ProRodeo Hall of Fame, Colorado Springs (I-25 Exit 148)

103 Pro Rodeo Drive off Exit 148 at Rockrimmon Boulevard, with truck and RV
parking; open daily May to August and Wednesday to Sunday September to April
(prorodeohalloffame.com). It inducts livestock too, bulls among them
(Wikipedia, "List of ProRodeo Hall of Fame inductees"). Northbound signs read
"next exit" after Exit 146; southbound, Exit 149 is a mile before 148, so
those read "ahead", 2.2 miles after the Garden of the Gods sign.

### ProRodeo Hall of Fame (northbound)
- treatment: billboard
- leg: pueblo_co_us -> denver_co_us
- at_mi: 49.4
- spoken: Billboard: The ProRodeo Hall of Fame, next exit. Champion riders, and a few of the bulls that threw them. Eight seconds was a full day's work.

### ProRodeo Hall of Fame (northbound)
- treatment: billboard
- leg: pueblo_co_us -> cheyenne_wy_us
- at_mi: 49.7
- spoken: Billboard: The ProRodeo Hall of Fame, next exit. Champion riders, and a few of the bulls that threw them. Eight seconds was a full day's work.

### ProRodeo Hall of Fame (northbound)
- treatment: billboard
- leg: pueblo_co_us -> fort_collins_co_us
- at_mi: 49.6
- spoken: Billboard: The ProRodeo Hall of Fame, next exit. Champion riders, and a few of the bulls that threw them. Eight seconds was a full day's work.

### ProRodeo Hall of Fame (northbound)
- treatment: billboard
- leg: colorado_springs_co_us -> denver_co_us
- at_mi: 5.0
- spoken: Billboard: The ProRodeo Hall of Fame, next exit. Champion riders, and a few of the bulls that threw them. Eight seconds was a full day's work.

### ProRodeo Hall of Fame (northbound)
- treatment: billboard
- leg: colorado_springs_co_us -> fort_collins_co_us
- at_mi: 5.1
- spoken: Billboard: The ProRodeo Hall of Fame, next exit. Champion riders, and a few of the bulls that threw them. Eight seconds was a full day's work.

### ProRodeo Hall of Fame (southbound)
- treatment: billboard
- leg: denver_co_us -> colorado_springs_co_us
- at_mi: 57.7
- spoken: Billboard: The ProRodeo Hall of Fame, ahead. Champion riders, and a few of the bulls that threw them. Eight seconds was a full day's work.

### ProRodeo Hall of Fame (southbound)
- treatment: billboard
- leg: fort_collins_co_us -> colorado_springs_co_us
- at_mi: 121.6
- spoken: Billboard: The ProRodeo Hall of Fame, ahead. Champion riders, and a few of the bulls that threw them. Eight seconds was a full day's work.

### ProRodeo Hall of Fame (southbound)
- treatment: billboard
- leg: denver_co_us -> pueblo_co_us
- at_mi: 57.2
- spoken: Billboard: The ProRodeo Hall of Fame, ahead. Champion riders, and a few of the bulls that threw them. Eight seconds was a full day's work.

### ProRodeo Hall of Fame (southbound)
- treatment: billboard
- leg: fort_collins_co_us -> pueblo_co_us
- at_mi: 122.1
- spoken: Billboard: The ProRodeo Hall of Fame, ahead. Champion riders, and a few of the bulls that threw them. Eight seconds was a full day's work.

### ProRodeo Hall of Fame (southbound)
- treatment: billboard
- leg: cheyenne_wy_us -> pueblo_co_us
- at_mi: 159.0
- spoken: Billboard: The ProRodeo Hall of Fame, ahead. Champion riders, and a few of the bulls that threw them. Eight seconds was a full day's work.

## Bishop Castle, Rye (I-25 Exit 74, then 24 miles on CO 165)

"From 1969 until 2019, this monument was constructed one stone, one log, one
weld at a time, by one man, James Roland Bishop"; open every day sunrise to
sunset on donations, visitors "enter at their own risk"; he died November
2024 and his son Daniel is caretaker (thebishopcastle.com; Denver Gazette).
"Take exit 74 at Colorado City ... 24 miles without a turn" (the castle's
earlier site, bishopcastle.org, as quoted in search results). The castle is
on the Frontier Pathways byway; the signs are on I-25, which is not.
Northbound from Walsenburg, the Colorado City callout sits between Exits 71
and 74, so that sign reads "ahead".

### Bishop Castle (southbound)
- treatment: billboard
- leg: pueblo_co_us -> walsenburg_co_us
- at_mi: 22.5
- spoken: Billboard: Bishop Castle, next exit, then twenty-four miles. One man built it by hand over fifty years. Free to climb, at your own risk.

### Bishop Castle (southbound)
- treatment: billboard
- leg: pueblo_co_us -> trinidad_co_us
- at_mi: 22.3
- spoken: Billboard: Bishop Castle, next exit, then twenty-four miles. One man built it by hand over fifty years. Free to climb, at your own risk.

### Bishop Castle (southbound)
- treatment: billboard
- leg: colorado_springs_co_us -> albuquerque_nm_us
- at_mi: 65.0
- spoken: Billboard: Bishop Castle, next exit, then twenty-four miles. One man built it by hand over fifty years. Free to climb, at your own risk.

### Bishop Castle (northbound)
- treatment: billboard
- leg: walsenburg_co_us -> pueblo_co_us
- at_mi: 15.5
- spoken: Billboard: Bishop Castle, ahead. Colorado City exit, then twenty-four miles. One man built it by hand over fifty years. Free to climb, at your own risk.

### Bishop Castle (northbound)
- treatment: billboard
- leg: trinidad_co_us -> pueblo_co_us
- at_mi: 59.3
- spoken: Billboard: Bishop Castle, next exit, then twenty-four miles. One man built it by hand over fifty years. Free to climb, at your own risk.

### Bishop Castle (northbound)
- treatment: billboard
- leg: albuquerque_nm_us -> colorado_springs_co_us
- at_mi: 309.6
- spoken: Billboard: Bishop Castle, next exit, then twenty-four miles. One man built it by hand over fifty years. Free to climb, at your own risk.

## South Park City, Fairplay (US 285)

An outdoor museum of 35 buildings from the 1850s to the 1880s, many moved in
from mining camps, opened 1959 at 100 4th Street; open daily May 15 to
October 15 (Wikipedia; South Park City museum listings).

### South Park City (southbound)
- treatment: billboard
- leg: denver_co_us -> albuquerque_nm_us
- at_mi: 77.0
- spoken: Billboard: South Park City, ahead in Fairplay. More than thirty buildings from the mining days, gathered into one town. The town decided history was worth hauling.

### South Park City (northbound)
- treatment: billboard
- leg: albuquerque_nm_us -> denver_co_us
- at_mi: 327.5
- spoken: Billboard: South Park City, ahead in Fairplay. More than thirty buildings from the mining days, gathered into one town. The town decided history was worth hauling.

## The UFO Watchtower, north of Hooper (CO 17)

Rancher Judy Messoline's sky-watching platform on her barn, opened May 2000,
with a gift shop and campground; about 163 sightings reported there
(Wikipedia, "UFO Watchtower"; NPR, April 2025). Northbound the sign stands
north of Mosca: CO 17 from Alamosa to Mosca is the Los Caminos Antiguos
byway.

### UFO Watchtower (southbound)
- treatment: billboard
- leg: denver_co_us -> albuquerque_nm_us
- at_mi: 185.0
- spoken: Billboard: The UFO Watchtower, ahead near Hooper. A rancher's barn with a sky-watching deck on top. Over a hundred sightings reported. The cattle aren't talking.

### UFO Watchtower (northbound)
- treatment: billboard
- leg: albuquerque_nm_us -> denver_co_us
- at_mi: 218.5
- spoken: Billboard: The UFO Watchtower, ahead near Hooper. A rancher's barn with a sky-watching deck on top. Over a hundred sightings reported. The cattle aren't talking.

## Colorado Gators Reptile Park, Mosca (CO 17)

Over 400 alligators in geothermally warmed water, three miles south of Hooper
on the east side of CO 17; begun as a tilapia farm; open daily
(coloradogators.com; Roadside America tip 3690).

### Colorado Gators (southbound)
- treatment: billboard
- leg: denver_co_us -> albuquerque_nm_us
- at_mi: 190.0
- spoken: Billboard: Colorado Gators Reptile Park, ahead. Hundreds of alligators, seven thousand feet up, in water the earth keeps warm. They have no plans to move south.

### Colorado Gators (northbound)
- treatment: billboard
- leg: albuquerque_nm_us -> denver_co_us
- at_mi: 216.0
- spoken: Billboard: Colorado Gators Reptile Park, ahead. Hundreds of alligators, seven thousand feet up, in water the earth keeps warm. They have no plans to move south.

## Great Sand Dunes National Park (US 160 at CO 150; CO 17 at Mosca)

The tallest dunes in North America, up to 750 feet; reached by US 160 and CO
150 north (about 19 miles on CO 150) or from Mosca on Lane 6 North
(nps.gov/grsa). US 160 between CO 150 and Fort Garland is the Los Caminos
Antiguos byway, so the westbound sign stands east of Fort Garland. Northbound
on US 285 there is no sign: CO 17 from Alamosa to Mosca is the same byway.

### Great Sand Dunes (westbound)
- treatment: billboard
- leg: walsenburg_co_us -> alamosa_co_us
- at_mi: 44.0
- spoken: Billboard: Great Sand Dunes National Park, ahead. North on Highway one fifty, about twenty miles. The tallest dunes in North America. The ocean never showed up.

### Great Sand Dunes (eastbound)
- treatment: billboard
- leg: alamosa_co_us -> walsenburg_co_us
- at_mi: 7.0
- spoken: Billboard: Great Sand Dunes National Park, ahead. North on Highway one fifty, about twenty miles. The tallest dunes in North America. The ocean never showed up.

### Great Sand Dunes (southbound)
- treatment: billboard
- leg: denver_co_us -> albuquerque_nm_us
- at_mi: 202.5
- spoken: Billboard: Great Sand Dunes National Park, turn east at Mosca, the next town. The tallest dunes in North America. The ocean never showed up.

## Durango and Silverton Narrow Gauge Railroad, Durango

Steam trains up the Animas River canyon to Silverton on the line finished in
1882 and run ever since; Silverton trains to November 1, 2026, then the
winter Cascade Canyon train and the holiday train (Wikipedia;
durangotrain.com). The depot is at the Durango node, so the signs stand
before the city on the two legs that reach it off a byway: US 160 from
Pagosa Springs and US 550 from Farmington.

### Durango and Silverton Railroad (westbound)
- treatment: billboard
- leg: pagosa_springs_co_us -> durango_co_us
- at_mi: 50.0
- spoken: Billboard: The Durango and Silverton steam train, ahead in Durango. Up the Animas canyon since eighteen eighty-two. Your truck is faster, and nobody photographs it.

### Durango and Silverton Railroad (northbound)
- treatment: billboard
- leg: farmington_nm_us -> durango_co_us
- at_mi: 42.0
- spoken: Billboard: The Durango and Silverton steam train, ahead in Durango. Up the Animas canyon since eighteen eighty-two. Your truck is faster, and nobody photographs it.

## Washington

## Snoqualmie Falls (I-90 Exit 25)

About 270 feet, a hundred feet taller than Niagara; park open sunrise to
sunset all year; Exit 25 from both directions (snoqualmiefalls.com and its
directions page). Eastbound only: I-90 from East Sunset Way in Issaquah to
Thorp Road is on Washington's scenic system, where off-premise boards are
prohibited (RCW 47.39.020(21), RCW 47.42.040), so these stand in Issaquah
west of it, ten miles out, and there is no westbound sign.

### Snoqualmie Falls (eastbound)
- treatment: billboard
- leg: seattle_wa_us -> moses_lake_wa_us
- at_mi: 13.0
- spoken: Billboard: Snoqualmie Falls, ahead. Two hundred seventy feet, a good hundred taller than Niagara. Nobody up here goes over in a barrel.

### Snoqualmie Falls (eastbound)
- treatment: billboard
- leg: seattle_wa_us -> spokane_wa_us
- at_mi: 13.0
- spoken: Billboard: Snoqualmie Falls, ahead. Two hundred seventy feet, a good hundred taller than Niagara. Nobody up here goes over in a barrel.

### Snoqualmie Falls (eastbound)
- treatment: billboard
- leg: seattle_wa_us -> yakima_wa_us
- at_mi: 13.0
- spoken: Billboard: Snoqualmie Falls, ahead. Two hundred seventy feet, a good hundred taller than Niagara. Nobody up here goes over in a barrel.

### Snoqualmie Falls (eastbound)
- treatment: billboard
- leg: seattle_wa_us -> tri_cities_wa_us
- at_mi: 13.0
- spoken: Billboard: Snoqualmie Falls, ahead. Two hundred seventy feet, a good hundred taller than Niagara. Nobody up here goes over in a barrel.

### Snoqualmie Falls (eastbound)
- treatment: billboard
- leg: everett_wa_us -> wenatchee_wa_us
- at_mi: 34.5
- spoken: Billboard: Snoqualmie Falls, ahead. Two hundred seventy feet, a good hundred taller than Niagara. Nobody up here goes over in a barrel.

### Snoqualmie Falls (eastbound)
- treatment: billboard
- leg: seattle_wa_us -> wenatchee_wa_us
- at_mi: 13.0
- spoken: Billboard: Snoqualmie Falls, ahead. Two hundred seventy feet, a good hundred taller than Niagara. Nobody up here goes over in a barrel.

## Boeing Future of Flight, Mukilteo (I-5 Exit 189)

8415 Paine Field Boulevard; the factory tour goes inside the Everett plant,
the world's largest building by volume; open seven days a week since early
2026 (Everett Herald, February 2026; seattlenorthcountry.com).

### Boeing Future of Flight (northbound)
- treatment: billboard
- leg: seattle_wa_us -> everett_wa_us
- at_mi: 21.8
- spoken: Billboard: Boeing's Future of Flight, next exit in Mukilteo. The factory tour goes inside the world's largest building by volume. Your trailer feels smaller already.

### Boeing Future of Flight (southbound)
- treatment: billboard
- leg: everett_wa_us -> seattle_wa_us
- at_mi: 2.8
- spoken: Billboard: Boeing's Future of Flight, next exit in Mukilteo. The factory tour goes inside the world's largest building by volume. Your trailer feels smaller already.

## The Museum of Flight, Seattle (I-5 Exit 158)

9404 East Marginal Way South, open daily 10 to 5, free parking; the first
presidential jet (SAM 970), a Concorde, and the Red Barn, Boeing's original
factory (museumofflight.org). Northbound, Exit 157 is a mile before 158 and
villages crowd the miles south of it, so that sign reads "ahead".

### Museum of Flight (southbound)
- treatment: billboard
- leg: seattle_wa_us -> tacoma_wa_us
- at_mi: 6.0
- spoken: Billboard: Museum of Flight, next exit. A Concorde, the first jet Air Force One, and the barn where Boeing started. None of them haul freight.

### Museum of Flight (southbound)
- treatment: billboard
- leg: seattle_wa_us -> portland_or_us
- at_mi: 6.0
- spoken: Billboard: Museum of Flight, next exit. A Concorde, the first jet Air Force One, and the barn where Boeing started. None of them haul freight.

### Museum of Flight (northbound)
- treatment: billboard
- leg: portland_or_us -> seattle_wa_us
- at_mi: 158.4
- spoken: Billboard: Museum of Flight, ahead. A Concorde, the first jet Air Force One, and the barn where Boeing started. None of them haul freight.

## The World's Largest Egg, Winlock (I-5 Exit 63)

Twelve feet long, on a pedestal in town, confirmed by Ripley's; Winlock was
once the second-biggest egg-producing town in the country; Exit 63, then about
five miles west on SR 505 (discoverlewiscounty.com).

### World's Largest Egg (southbound)
- treatment: billboard
- leg: olympia_wa_us -> longview_wa_us
- at_mi: 41.5
- spoken: Billboard: The world's largest egg, next exit, five miles west in Winlock. Twelve feet long, up on a pedestal. The chicken has never been located.

### World's Largest Egg (southbound)
- treatment: billboard
- leg: seattle_wa_us -> portland_or_us
- at_mi: 99.7
- spoken: Billboard: The world's largest egg, next exit, five miles west in Winlock. Twelve feet long, up on a pedestal. The chicken has never been located.

### World's Largest Egg (northbound)
- treatment: billboard
- leg: longview_wa_us -> olympia_wa_us
- at_mi: 22.0
- spoken: Billboard: The world's largest egg, next exit, five miles west in Winlock. Twelve feet long, up on a pedestal. The chicken has never been located.

### World's Largest Egg (northbound)
- treatment: billboard
- leg: portland_or_us -> seattle_wa_us
- at_mi: 77.7
- spoken: Billboard: The world's largest egg, next exit, five miles west in Winlock. Twelve feet long, up on a pedestal. The chicken has never been located.

## Mount St. Helens Visitor Center, Silver Lake (I-5 Exit 49)

Washington State Parks' visitor center five miles east of Exit 49 on SR 504,
renovated in 2025; open daily April to October, Wednesday to Sunday November
to March. The 1980 eruption took 1,314 feet off the summit (USGS). Northbound
the Toutle River and Castle Rock callouts leave no slot before Exit 49, so
those signs read "ahead".

### Mount St. Helens Visitor Center (southbound)
- treatment: billboard
- leg: olympia_wa_us -> longview_wa_us
- at_mi: 54.7
- spoken: Billboard: Mount Saint Helens Visitor Center, next exit. The mountain lost thirteen hundred feet off its top in nineteen eighty. It kept the rest.

### Mount St. Helens Visitor Center (southbound)
- treatment: billboard
- leg: seattle_wa_us -> portland_or_us
- at_mi: 114.0
- spoken: Billboard: Mount Saint Helens Visitor Center, next exit. The mountain lost thirteen hundred feet off its top in nineteen eighty. It kept the rest.

### Mount St. Helens Visitor Center (northbound)
- treatment: billboard
- leg: longview_wa_us -> olympia_wa_us
- at_mi: 3.5
- spoken: Billboard: Mount Saint Helens Visitor Center, ahead at Castle Rock. The mountain lost thirteen hundred feet off its top in nineteen eighty. It kept the rest.

### Mount St. Helens Visitor Center (northbound)
- treatment: billboard
- leg: portland_or_us -> seattle_wa_us
- at_mi: 56.0
- spoken: Billboard: Mount Saint Helens Visitor Center, ahead at Castle Rock. The mountain lost thirteen hundred feet off its top in nineteen eighty. It kept the rest.

## Ginkgo Petrified Forest State Park, Vantage (I-90 Exit 136)

Fossil logs about 15.5 million years old, over 40 kinds of wood
(Wikipedia); interpretive center north of Exit 136, trails two miles west.
The center is closed for renovation September 21 to October 2 and reopens
October 3, Friday to Sunday (parks.wa.gov). Westbound, Exit 137 and the
Vantage callout leave no slot before Exit 136, so those signs read "ahead".

### Ginkgo Petrified Forest (westbound)
- treatment: billboard
- leg: moses_lake_wa_us -> seattle_wa_us
- at_mi: 33.0
- spoken: Billboard: Ginkgo Petrified Forest, ahead at Vantage. A forest that turned to stone about fifteen million years ago. It has not needed watering since.

### Ginkgo Petrified Forest (westbound)
- treatment: billboard
- leg: spokane_wa_us -> seattle_wa_us
- at_mi: 135.0
- spoken: Billboard: Ginkgo Petrified Forest, ahead at Vantage. A forest that turned to stone about fifteen million years ago. It has not needed watering since.

### Ginkgo Petrified Forest (westbound)
- treatment: billboard
- leg: moses_lake_wa_us -> yakima_wa_us
- at_mi: 33.5
- spoken: Billboard: Ginkgo Petrified Forest, ahead at Vantage. A forest that turned to stone about fifteen million years ago. It has not needed watering since.

### Ginkgo Petrified Forest (eastbound)
- treatment: billboard
- leg: seattle_wa_us -> moses_lake_wa_us
- at_mi: 132.0
- spoken: Billboard: Ginkgo Petrified Forest, next exit at Vantage. A forest that turned to stone about fifteen million years ago. It has not needed watering since.

### Ginkgo Petrified Forest (eastbound)
- treatment: billboard
- leg: seattle_wa_us -> spokane_wa_us
- at_mi: 132.5
- spoken: Billboard: Ginkgo Petrified Forest, next exit at Vantage. A forest that turned to stone about fifteen million years ago. It has not needed watering since.

### Ginkgo Petrified Forest (eastbound)
- treatment: billboard
- leg: yakima_wa_us -> moses_lake_wa_us
- at_mi: 54.0
- spoken: Billboard: Ginkgo Petrified Forest, next exit at Vantage. A forest that turned to stone about fifteen million years ago. It has not needed watering since.

## The Wild Horses Monument, Vantage (I-90 Exit 139, eastbound)

David Govedare's "Grandfather Cuts Loose the Ponies", fifteen life-size steel
horses on the ridge east of the Vantage Bridge, a 1989-90 gift for the state
centennial where the last great roundup of the region's wild horses took
place in 1906; reached by a path from the eastbound viewpoint off Exit 139
(Wikipedia; Grant County). Eastbound only, where the viewpoint is.

### Wild Horses Monument (eastbound)
- treatment: billboard
- leg: seattle_wa_us -> moses_lake_wa_us
- at_mi: 137.0
- spoken: Billboard: The Wild Horses Monument, next exit. Fifteen steel horses on the ridge, where the last big roundup ran in nineteen oh-six. They are still running.

### Wild Horses Monument (eastbound)
- treatment: billboard
- leg: seattle_wa_us -> spokane_wa_us
- at_mi: 137.3
- spoken: Billboard: The Wild Horses Monument, next exit. Fifteen steel horses on the ridge, where the last big roundup ran in nineteen oh-six. They are still running.

### Wild Horses Monument (eastbound)
- treatment: billboard
- leg: yakima_wa_us -> moses_lake_wa_us
- at_mi: 60.0
- spoken: Billboard: The Wild Horses Monument, next exit. Fifteen steel horses on the ridge, where the last big roundup ran in nineteen oh-six. They are still running.

## The Teapot Dome Service Station, Zillah (I-82 Exit 52)

A 1922 filling station built as a teapot, "a reminder of the Teapot Dome
Scandal", moved in 1978 for I-82 and in 2012 to 117 First Avenue, now Zillah's
visitor center (Wikipedia, "Teapot Dome Service Station"); Exit 52, then half
a mile north (Roadside America). The structure stands in
its own small park; the visitor center inside keeps short seasonal hours.
Signs read "ahead" because Buena, Zillah, Granger and Outlook sit close to
the exits.

### Teapot Dome (eastbound)
- treatment: billboard
- leg: yakima_wa_us -> tri_cities_wa_us
- at_mi: 14.0
- spoken: Billboard: The Teapot Dome gas station, ahead in Zillah. Shaped like a teapot in nineteen twenty-two, to poke fun at a scandal in the other Washington.

### Teapot Dome (eastbound)
- treatment: billboard
- leg: seattle_wa_us -> tri_cities_wa_us
- at_mi: 155.5
- spoken: Billboard: The Teapot Dome gas station, ahead in Zillah. Shaped like a teapot in nineteen twenty-two, to poke fun at a scandal in the other Washington.

### Teapot Dome (westbound)
- treatment: billboard
- leg: tri_cities_wa_us -> yakima_wa_us
- at_mi: 54.0
- spoken: Billboard: The Teapot Dome gas station, ahead in Zillah. Shaped like a teapot in nineteen twenty-two, to poke fun at a scandal in the other Washington.

### Teapot Dome (westbound)
- treatment: billboard
- leg: tri_cities_wa_us -> seattle_wa_us
- at_mi: 53.7
- spoken: Billboard: The Teapot Dome gas station, ahead in Zillah. Shaped like a teapot in nineteen twenty-two, to poke fun at a scandal in the other Washington.

## Notes for the owner

Thirty-four attractions, 108 signs: North Dakota eleven attractions and 20
signs, Colorado fifteen and 56, Washington eight and 32. A dry run of
`tools/bake_billboards.py` on this sheet resolves every leg and bakes all 108
(no `--write`). A spacing check against the source legs, oriented the way the
bake orients them, finds no callout heard in the same direction within 2.2
miles of any sign, counting the other signs on this sheet. Every line is
spelled out with no digits and runs 22 to 26 words. Every joke is original.
No pool line or placed sign already names any of these places (searched
`billboards.rs`, the legs and the sheets).

The one call that is yours: I kept Washington signs off its scenic system,
because the statute bans off-premise boards anywhere visible from it. That
cost Snoqualmie Falls its westbound signs and dropped the Codger Pole and the
Olympic Game Farm entirely. Recommend keeping it that way; if you would
rather the game ignore it, the copy is ready and the slots are easy to add.

Per attraction: sources, status, anything unsure.

North Dakota

- **Salem Sue.** https://en.wikipedia.org/wiki/Salem_Sue,
  https://www.roadsideamerica.com/story/2716. Standing, viewable any time.
- **Enchanted Highway.** https://www.ndtourism.com/regent/attractions/enchanted-highway
  (Exit 72, 32 miles to Regent, seven sculptures, Geese in Flight at the
  exit); Guinness 2002 record per ndtourism and Smithsonian. Unsure: whether
  the record still stands, so the copy says the geese "set" one.
- **Theodore Roosevelt Presidential Library.** https://www.trlibrary.com/visit/directions
  (Exit 24 from the west, 27 from the east),
  https://www.nd.gov/news/theodore-roosevelt-presidential-library-opens-july-4-during-north-dakotas-america-250
  (opened July 4, 2026, year-round), Cowboy State Daily August 9, 2026 and
  Deseret News (living roof of native plants). Admission is $26; the copy
  names no price.
- **Painted Canyon, Theodore Roosevelt National Park.** https://www.nps.gov/thro
  (Exit 32, six miles east of Medora). The overlook is open all year; its
  visitor center is seasonal, about May to October.
- **North Unit, Theodore Roosevelt National Park.**
  https://www.nps.gov/thro/planyourvisit/north-unit.htm (US 85, about fifteen
  miles south of Watford City, "less-visited", bison and bighorn sheep). That
  makes three Roosevelt signs in the state; they are on different roads
  except the Library and Painted Canyon, which are nine miles apart on I-94.
- **Sandy the sandhill crane.** https://www.roadsideamerica.com/tip/1834
  (40 feet, 1998-99, behind the Cobblestone Inn at Exit 200).
- **World's Largest Buffalo.** https://www.ndtourism.com/jamestown/attractions-entertainment/educational-attractions/worlds-largest-buffalo-monument
  (26 feet, 60 tons, 1959, live herd). The eastbound sign is 9.3 miles out,
  squeezed between the James River and Eldridge callouts (2.3 miles each).
- **Fargo woodchipper.** https://www.fargomoorhead.org/plan/visitors-centers/
  (open daily, Exit 348; the original prop). Eastbound only, 12.8 miles out.
  The copy jokes about the prop's retirement, not the film's scene.
- **Bonanzaville.** https://bonanzaville.org (34 buildings; open daily
  through October 12, 2026). Eastbound only. Seasonal: it closes for the
  winter in twelve days, so the sign will advertise a closed village from
  mid-October to spring. Cut it if that bothers you.
- **Rugby marker.** https://en.wikipedia.org/wiki/Rugby,_North_Dakota (1931
  obelisk, moved 1971, USGS says about fifteen miles off). Unsure only in
  that I could not confirm a 2026 photo; nothing suggests it has moved.
- **Lewis & Clark Interpretive Center.** https://www.history.nd.gov/historicsites/lcic/
  (open; winter hours Tuesday to Saturday from October 1).

Colorado

- **Red Rocks.** https://www.redrocksonline.com/explore-red-rocks/visitor-center/
  (Exit 259; 300-foot Ship Rock and Creation Rock; park open daily, visitor
  center closed for construction). Chosen over Dinosaur Ridge, same exit.
- **Buffalo Bill Museum and Grave.** https://buffalobill.org/visit-us/location/
  (westbound Exit 256, eastbound Exit 254), https://en.wikipedia.org/wiki/Buffalo_Bill
  (1948 Cody American Legion reward, Denver Legion guard),
  https://5280.com/2015/10/only-in-colorado-buffalo-bills-grave/ (says the
  National Guard; the copy says only "a guard"). Kansas's Giant Buffalo Bill
  sign at Oakley is on the same Kansas City to Denver leg, so a driver
  heading west past Denver can hear about Buffalo Bill twice; different
  places, different facts.
- **Georgetown Loop Railroad.** https://en.wikipedia.org/wiki/Georgetown_Loop_Railroad
  (two miles apart, 4.5 miles of track), https://www.georgetownlooprr.com/
  (2026 operation, holiday trains on sale). Unsure: the fall season ends
  in October and only the holiday trains run until spring.
- **Old Town Hot Springs.** https://oldtownhotsprings.org/ (open daily but
  Thanksgiving and Christmas), https://en.wikipedia.org/wiki/Steamboat_Springs,_Colorado
  (the name). A search summary said railroad blasting silenced the spring
  around 1909; I could not open a primary source, so the copy leaves it out.
- **Glenwood Hot Springs.** https://hotspringspool.com/press-room/press-kit/fact-sheet-glenwood-hot-springs/
  (1888, 405 feet, 1,071,000 gallons, open 365 days). Chosen over Glenwood
  Caverns, same exit.
- **Colorado National Monument.** https://en.wikipedia.org/wiki/Colorado_National_Monument
  (1911, John Otto, a dollar a month). One sign: only the Delta leg reaches it
  off a byway. "Ahead past Grand Junction": the east entrance is a few miles
  west of downtown.
- **World's Wonder View Tower.** https://en.wikipedia.org/wiki/World%27s_Wonder_View_Tower,
  https://www.denvergazette.com/2026/09/23/hanzon-has-tallest-tower-watchers-seeing-red/
  (reopened 2026 as an art museum; the season ended September 26). It is
  closed until next summer, so it fails "open today" by four days. Kept
  because it is a real, newly reopened roadside landmark whose claim is the
  joke and the copy promises no hours. Cut it if you want strictly open
  today.
- **Garden of the Gods.** https://gardenofgods.com/park-info/get-directions/
  (Exit 146, free, oversized-vehicle parking in the overflow lot),
  https://en.wikipedia.org/wiki/Garden_of_the_Gods (1909 gift, "free and
  public park forever").
- **ProRodeo Hall of Fame.** https://www.prorodeohalloffame.com/plan-a-visit/
  (Exit 148, truck parking, hours),
  https://en.wikipedia.org/wiki/List_of_ProRodeo_Hall_of_Fame_inductees
  (bulls inducted). Garden of the Gods and the ProRodeo Hall share I-25
  through Colorado Springs, so between them that is eighteen signs; each
  driver hears two. Southbound the pair stands exactly 2.2 miles apart, the
  rule's floor. Trimming to the through legs would be reasonable.
- **Bishop Castle.** https://thebishopcastle.com/ (open daily, donations,
  "enter at their own risk", built by one man 1969 to 2019; Jim Bishop died
  November 2024). The 24 miles from Exit 74 are from the castle's older
  site as quoted in search results.
- **South Park City.** https://en.wikipedia.org/wiki/South_Park_City (35
  buildings, opened 1959); open daily May 15 to October 15. Seasonal, like
  Bonanzaville: open now, closed from mid-October.
- **UFO Watchtower.** https://en.wikipedia.org/wiki/UFO_Watchtower (opened
  2000, about 163 sightings), NPR April 30, 2025. Unsure: winter hours were
  not stated anywhere I could open.
- **Colorado Gators.** https://www.coloradogators.com/ (open daily all year),
  https://www.roadsideamerica.com/tip/3690 (over 400 alligators, east side of
  CO 17 three miles south of Hooper).
- **Great Sand Dunes National Park.** https://www.nps.gov/grsa/planyourvisit/directions.htm
  (US 160 east and CO 150 north, or Lane 6 east from Mosca; 750-foot dunes).
  "About twenty miles" on CO 150 is the 19.4 miles from the NPS-cited route.
  No northbound sign on US 285: the stretch before Mosca is a byway.
- **Durango and Silverton.** https://en.wikipedia.org/wiki/Durango_and_Silverton_Narrow_Gauge_Railroad,
  https://www.durangotrain.com/cascade-canyon-express (running, winter
  train). The railroad is converting its engines from coal to oil, so the
  copy says only "steam train".

Washington

- **Snoqualmie Falls.** https://www.snoqualmiefalls.com/ and /directions/
  (270 feet, sunrise to sunset all year, Exit 25 both ways). Wikipedia gives
  268; the copy uses the park's own number. Exit 25 is missing from every
  I-90 interchange list; its milepost is taken two-fifths of the way from
  Exit 27 to Exit 22.
- **Boeing Future of Flight.** Everett Herald, February 7, 2026 (seven days a
  week), seattlenorthcountry.com (Exit 189; world's largest building by
  volume). The southbound sign is 2.8 miles out of the Everett node, right
  after Exit 192.
- **Museum of Flight.** https://museumofflight.org/directions (Exit 158, open
  daily), https://www.museumofflight.org/aircraft/boeing-vc-137b-707-120sam-970-air-force-one
  (first presidential jet). The northbound sign is 15 miles out: the only
  clear slot between Lakeland South and Lakeland North (2.3 and 2.2 miles).
- **World's Largest Egg.** https://discoverlewiscounty.com/winlock/ (Ripley's,
  Exit 63, about five miles west). Size and pedestal are from Roadside
  America and RV Travel summaries; I could not open RV Travel itself.
- **Mount St. Helens Visitor Center.** Washington State Parks via
  https://parks.wa.gov (hours; 2025 renovation); USGS via Wikipedia for the
  1,314 feet. Exit 49 is missing from the Portland to Seattle interchange
  list; it is taken just north of Exit 48.
- **Ginkgo Petrified Forest.** https://parks.wa.gov/node/610 (closed for
  renovation September 21 to October 2, reopens October 3),
  https://en.wikipedia.org/wiki/Ginkgo_Petrified_Forest_State_Park (15.5
  million years).
- **Wild Horses Monument.** https://en.wikipedia.org/wiki/Grandfather_Cuts_Loose_the_Ponies
  (fifteen steel horses, 1989-90, the 1906 roundup, eastbound off-ramp
  path). The work's title draws on Native spiritual imagery, so the copy keeps
  to the horses and the roundup.
- **Teapot Dome.** https://en.wikipedia.org/wiki/Teapot_Dome_Service_Station
  (1922, moved 1978 and 2012, visitor center), Roadside America (Exit 52).
  The building stands in its own park; the visitor center inside keeps short
  seasonal hours, which the copy does not promise.

Dropped:

- **Dinosaur Journey, Fruita.** Open and a good fit, but every slot is on
  I-70 west of Grand Junction, the Dinosaur Diamond byway (Wikipedia,
  "Dinosaur Diamond"), where Colorado bars new boards. The same rule drops
  Dinosaur, Colorado, on US 40, Mesa Verde on US 160 west of Durango (San
  Juan Skyway), Mount Princeton Hot Springs (Collegiate Peaks) and the
  Cumbres and Toltec railroad at Antonito (Los Caminos Antiguos, and
  seasonal).
- **Codger Pole, Colfax; Olympic Game Farm, Sequim; Snoqualmie Falls
  westbound; Roslyn and Cle Elum.** Washington's scenic system (above).
- **Kit Carson County Carousel, Burlington.** Closed for the season since
  Labor Day, and at the Burlington node.
- **Scandinavian Heritage Park, Minot.** Its season ends October 1, and it
  sits at the Minot node.
- **Casselton Can Pile.** Taken down in 2012 (Roadside America).
- **Dinosaur Ridge, Glenwood Caverns, Toppenish murals, Fort Garland
  Museum.** Each competes for the same stretch as Red Rocks, Glenwood Hot
  Springs, Teapot Dome or Great Sand Dunes, the better-known neighbor.
- **Western Museum of Mining and Industry and the Air Force Academy visitor
  center, Colorado Springs.** Same I-25 stretch as Garden of the Gods and the
  ProRodeo Hall; the Academy center's 2026 status was not confirmed.
- **LeMay America's Car Museum, Tacoma.** At the Tacoma node with no honest
  slot. **Fort Vancouver.** The legs south of Longview leave I-5 for I-205
  and never pass it.
- **Chimney Rock National Monument, the Medora Musical, the Dakota Dinosaur
  Museum, the Gorge Amphitheatre.** Seasons over or ending this week.
- **Brewery and winery tours (Coors, Anheuser-Busch Fort Collins, Prosser's
  wine center) and casinos.** Left to you: drinking ads in a driving game,
  and the pools already carry the casino genre.
- **Kalama's totem pole, Whitman Mission.** Native art and a massacre site,
  both needing a respectful treatment, not a billboard joke.
- **Fishers Peak, Pagosa Springs, Pueblo, Durango, Spokane, Bismarck sights
  at their nodes, the Wahpeton catfish (ten miles off I-29), Royal Gorge and
  Pikes Peak (no leg).** No honest slot.

Found along the way (data, not this sheet):

- The Columbia River crossing at Vantage is misplaced on four I-90 legs: on
  Moses Lake to Seattle it is called at mile 54.0, twelve miles west of the
  bridge (Vantage is at 42.3); Spokane to Seattle 158.9 against Vantage
  144.0; Yakima to Moses Lake 56.8, a mile before Vantage instead of just
  after it.
- I-70 west of Denver calls "Mestaa'ėhehe Pass" and, on the Salt Lake City
  leg, "Juniper Pass". Both are on CO 103, the Mount Blue Sky road, not on
  I-70, so a driver hears a pass the truck never climbs.
- The Denver to Albuquerque leg (US 285) lists stops named "Love's Travel
  Stop Pueblo" (mile 97) and "Love's Travel Stop Trinidad" (mile 175), towns
  that leg never passes.
- The existing Leavenworth sign ("The Bavarian Village", Seattle to
  Wenatchee, mile 126) stands on US 97 south of Peshastin, on Washington's
  scenic system, where the state bans such boards; and that leg turns east
  at Peshastin, four miles short of Leavenworth.
