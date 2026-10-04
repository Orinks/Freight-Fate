# New Mexico attractions, both directions -- 2026-10-01

Draft for the owner's review, not yet approved.

Thirteen real New Mexico roadside attractions on Interstates 40, 25 and
10 and US 70, US 54, US 62, US 285 and US 491, each signed in every
direction a leg passes it. Every `leg:` is written the way the driver
reads the sign and `at_mi` counts from that end; `tools/bake_billboards.py`
mirrors the milepost onto a leg stored the other way round and records
which way the billboard faces. Block names read "(from <city>)", the city
the driver set out from on that leg.

Mileposts come from projecting each attraction onto the legs' dense
geometry, read against each leg's interchange list. "Next exit" signs stand
between the attraction's exit and the exit before it; "ahead" signs about
five to ten miles out, nearer where a leg starts in the attraction's own
city. Each sits at least 2.2 miles from every other callout heard in the
same direction. No sign stands in Texas, Colorado or Arizona.

Law: New Mexico's Highway Beautification Act (NMSA 1978, chapter 67,
article 12) allows off-premise signs beside the interstates and primary
roads in commercial and industrial areas, and the federal rule bars new
ones on designated scenic byways. Three byways touch these legs:

- **Santa Fe Trail National Scenic Byway** runs I-25 from Raton Pass to
  Springer and Springer to Fort Union (recreation.gov driving directions).
  The Las Vegas to Raton and Raton to Trinidad legs carry none, and the
  through Colorado Springs leg carries none north of Las Vegas.
- **El Camino Real National Scenic Byway** follows old US 85 and uses I-25
  itself only from Bernardo to Alamillo, from Escondida into Socorro, and
  from the south end of NM 1 to NM 181 above Truth or Consequences, plus
  US 84 and 285 north of Santa Fe (its own driving directions on
  recreation.gov). Signs near Socorro and Truth or Consequences stand
  outside those stretches, and the Denver leg carries no Santa Fe sign.
- **Historic Route 66 National Scenic Byway** is the old road beside I-40,
  not I-40 itself (New Mexico True). The **Billy the Kid Trail** (US 70
  between Ruidoso Downs and Hondo) carries none.

The Meow Wolf signs stand on I-25 eight to ten miles outside Santa Fe.

## The Blue Hole, Santa Rosa (I-40)

An artesian sinkhole on old Route 66 in Santa Rosa, more than 80 feet
deep, 62 degrees year round, fed 3,000 gallons a minute; one of the
country's most popular scuba sites (Wikipedia).

### The Blue Hole (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> tucumcari_nm_us
- at_mi: 108.7
- spoken: Billboard: The Blue Hole, ahead in Santa Rosa. A desert spring over eighty feet deep, sixty-two degrees year round. Divers love it; toes are less sure.

### The Blue Hole (from Tucumcari)
- treatment: billboard
- leg: tucumcari_nm_us -> albuquerque_nm_us
- at_mi: 49.3
- spoken: Billboard: The Blue Hole, ahead in Santa Rosa. A desert spring over eighty feet deep, sixty-two degrees year round. Divers love it; toes are less sure.

### The Blue Hole (from Amarillo)
- treatment: billboard
- leg: amarillo_tx_us -> albuquerque_nm_us
- at_mi: 161.7
- spoken: Billboard: The Blue Hole, ahead in Santa Rosa. A desert spring over eighty feet deep, sixty-two degrees year round. Divers love it; toes are less sure.

### The Blue Hole (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> amarillo_tx_us
- at_mi: 108.9
- spoken: Billboard: The Blue Hole, ahead in Santa Rosa. A desert spring over eighty feet deep, sixty-two degrees year round. Divers love it; toes are less sure.

### The Blue Hole (from Dallas)
- treatment: billboard
- leg: dallas_tx_us -> albuquerque_nm_us
- at_mi: 520.9
- spoken: Billboard: The Blue Hole, ahead in Santa Rosa. A desert spring over eighty feet deep, sixty-two degrees year round. Divers love it; toes are less sure.

### The Blue Hole (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> dallas_tx_us
- at_mi: 107.1
- spoken: Billboard: The Blue Hole, ahead in Santa Rosa. A desert spring over eighty feet deep, sixty-two degrees year round. Divers love it; toes are less sure.

## Sandia Peak Tramway, Albuquerque (I-40 Exit 167, I-25 Exit 234)

The longest aerial tram in the Americas, 2.7 miles, rising 3,819 feet in
fifteen minutes; running Thursday to Monday in 2026 (Wikipedia). Signed on
the I-40 and I-25 approaches into Albuquerque and on the legs leaving it
before their tram exit.

### Sandia Peak Tramway (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> tucumcari_nm_us
- at_mi: 3.5
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Tucumcari)
- treatment: billboard
- leg: tucumcari_nm_us -> albuquerque_nm_us
- at_mi: 154.8
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Amarillo)
- treatment: billboard
- leg: amarillo_tx_us -> albuquerque_nm_us
- at_mi: 266.7
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> amarillo_tx_us
- at_mi: 3.5
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Dallas)
- treatment: billboard
- leg: dallas_tx_us -> albuquerque_nm_us
- at_mi: 631.0
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> dallas_tx_us
- at_mi: 3.5
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Colorado Springs)
- treatment: billboard
- leg: colorado_springs_co_us -> albuquerque_nm_us
- at_mi: 359.2
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> colorado_springs_co_us
- at_mi: 3.5
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Denver)
- treatment: billboard
- leg: denver_co_us -> albuquerque_nm_us
- at_mi: 401.2
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> denver_co_us
- at_mi: 3.5
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> santa_fe_nm_us
- at_mi: 3.5
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

### Sandia Peak Tramway (from Santa Fe)
- treatment: billboard
- leg: santa_fe_nm_us -> albuquerque_nm_us
- at_mi: 45.1
- spoken: Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

## Acoma Sky City (I-40 Exits 102 and 108)

The Acoma pueblo atop a 365-foot mesa, among the oldest continuously
inhabited communities in the country; guided tours from the Sky City
Cultural Center, March through October (Wikipedia). A living community, so
the line is plain.

### Acoma Sky City (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> gallup_nm_us
- at_mi: 44.4
- spoken: Billboard: Acoma Sky City, ahead, a pueblo atop a mesa three hundred sixty-five feet high, home for centuries. Tours begin at the cultural center.

### Acoma Sky City (from Gallup)
- treatment: billboard
- leg: gallup_nm_us -> albuquerque_nm_us
- at_mi: 70.2
- spoken: Billboard: Acoma Sky City, ahead, a pueblo atop a mesa three hundred sixty-five feet high, home for centuries. Tours begin at the cultural center.

### Acoma Sky City (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> phoenix_az_us
- at_mi: 45.9
- spoken: Billboard: Acoma Sky City, ahead, a pueblo atop a mesa three hundred sixty-five feet high, home for centuries. Tours begin at the cultural center.

### Acoma Sky City (from Phoenix)
- treatment: billboard
- leg: phoenix_az_us -> albuquerque_nm_us
- at_mi: 398.8
- spoken: Billboard: Acoma Sky City, ahead, a pueblo atop a mesa three hundred sixty-five feet high, home for centuries. Tours begin at the cultural center.

## El Rancho Hotel, Gallup

Built in 1937 by R. E. Griffith as a base for film crews shooting
Westerns; the rooms carry the names of the stars who stayed; still a
working hotel on Route 66 (Wikipedia).

### El Rancho Hotel (from Holbrook)
- treatment: billboard
- leg: holbrook_az_us -> gallup_nm_us
- at_mi: 86.0
- spoken: Billboard: The El Rancho Hotel, ahead in Gallup, built in nineteen thirty-seven for movie crews. Its rooms are named for the stars who stayed.

### El Rancho Hotel (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> gallup_nm_us
- at_mi: 127.2
- spoken: Billboard: The El Rancho Hotel, ahead in Gallup, built in nineteen thirty-seven for movie crews. Its rooms are named for the stars who stayed.

### El Rancho Hotel (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> phoenix_az_us
- at_mi: 127.5
- spoken: Billboard: The El Rancho Hotel, ahead in Gallup, built in nineteen thirty-seven for movie crews. Its rooms are named for the stars who stayed.

### El Rancho Hotel (from Phoenix)
- treatment: billboard
- leg: phoenix_az_us -> albuquerque_nm_us
- at_mi: 320.5
- spoken: Billboard: The El Rancho Hotel, ahead in Gallup, built in nineteen thirty-seven for movie crews. Its rooms are named for the stars who stayed.

### El Rancho Hotel (from Farmington)
- treatment: billboard
- leg: farmington_nm_us -> gallup_nm_us
- at_mi: 114.9
- spoken: Billboard: The El Rancho Hotel, ahead in Gallup, built in nineteen thirty-seven for movie crews. Its rooms are named for the stars who stayed.

## Meow Wolf's House of Eternal Return, Santa Fe

Opened in 2016 in a renovated bowling alley, with George R. R. Martin's
$2.7 million behind the lease and renovation; still open in 2026
(Wikipedia).

### Meow Wolf (from Colorado Springs)
- treatment: billboard
- leg: colorado_springs_co_us -> albuquerque_nm_us
- at_mi: 312.2
- spoken: Billboard: Meow Wolf, ahead in Santa Fe. A bowling alley became a house with doors to other worlds. A fantasy novelist footed the bill.

### Meow Wolf (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> colorado_springs_co_us
- at_mi: 47.8
- spoken: Billboard: Meow Wolf, ahead in Santa Fe. A bowling alley became a house with doors to other worlds. A fantasy novelist footed the bill.

### Meow Wolf (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> denver_co_us
- at_mi: 49.8
- spoken: Billboard: Meow Wolf, ahead in Santa Fe. A bowling alley became a house with doors to other worlds. A fantasy novelist footed the bill.

### Meow Wolf (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> santa_fe_nm_us
- at_mi: 48.1
- spoken: Billboard: Meow Wolf, ahead in Santa Fe. A bowling alley became a house with doors to other worlds. A fantasy novelist footed the bill.

## Bosque del Apache National Wildlife Refuge, San Antonio (I-25 Exit 139)

Thousands of sandhill cranes and more than 10,000 snow and Ross's geese
winter here, late November to mid-February (Wikipedia). Open all year.

### Bosque del Apache (from Socorro)
- treatment: billboard
- leg: socorro_nm_us -> las_cruces_nm_us
- at_mi: 4.0
- spoken: Billboard: Bosque del Apache National Wildlife Refuge, ahead at San Antonio. Thousands of sandhill cranes winter here with the snow geese. They are louder than you.

### Bosque del Apache (from Las Cruces)
- treatment: billboard
- leg: las_cruces_nm_us -> socorro_nm_us
- at_mi: 127.2
- spoken: Billboard: Bosque del Apache National Wildlife Refuge, ahead at San Antonio. Thousands of sandhill cranes winter here with the snow geese. They are louder than you.

### Bosque del Apache (from El Paso)
- treatment: billboard
- leg: el_paso_tx_us -> albuquerque_nm_us
- at_mi: 171.0
- spoken: Billboard: Bosque del Apache National Wildlife Refuge, ahead at San Antonio. Thousands of sandhill cranes winter here with the snow geese. They are louder than you.

### Bosque del Apache (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> el_paso_tx_us
- at_mi: 80.0
- spoken: Billboard: Bosque del Apache National Wildlife Refuge, ahead at San Antonio. Thousands of sandhill cranes winter here with the snow geese. They are louder than you.

## Truth or Consequences (I-25)

The town of Hot Springs renamed itself in March 1950 after Ralph Edwards
promised his radio quiz show's tenth-anniversary broadcast to the first
town that would (Wikipedia). Southbound signs stand north of the byway's
short I-25 stretch, about fifteen miles out.

### Truth or Consequences (from Socorro)
- treatment: billboard
- leg: socorro_nm_us -> las_cruces_nm_us
- at_mi: 56.0
- spoken: Billboard: Truth or Consequences, ahead. In nineteen fifty, Hot Springs renamed itself after a radio quiz show for one broadcast. The name stuck; the show moved on.

### Truth or Consequences (from Las Cruces)
- treatment: billboard
- leg: las_cruces_nm_us -> socorro_nm_us
- at_mi: 65.6
- spoken: Billboard: Truth or Consequences, ahead. In nineteen fifty, Hot Springs renamed itself after a radio quiz show for one broadcast. The name stuck; the show moved on.

### Truth or Consequences (from El Paso)
- treatment: billboard
- leg: el_paso_tx_us -> albuquerque_nm_us
- at_mi: 109.3
- spoken: Billboard: Truth or Consequences, ahead. In nineteen fifty, Hot Springs renamed itself after a radio quiz show for one broadcast. The name stuck; the show moved on.

### Truth or Consequences (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> el_paso_tx_us
- at_mi: 132.0
- spoken: Billboard: Truth or Consequences, ahead. In nineteen fifty, Hot Springs renamed itself after a radio quiz show for one broadcast. The name stuck; the show moved on.

## Hatch (I-25 Exit 41)

The village calls itself the chile capital of the world; its Labor Day
chile festival draws up to 30,000 visitors (Wikipedia).

### Hatch chile (from Socorro)
- treatment: billboard
- leg: socorro_nm_us -> las_cruces_nm_us
- at_mi: 106.2
- spoken: Billboard: Hatch, next exit, the chile capital of the world, by its own count. Its Labor Day festival draws thousands. Mild is a matter of opinion.

### Hatch chile (from Las Cruces)
- treatment: billboard
- leg: las_cruces_nm_us -> socorro_nm_us
- at_mi: 36.4
- spoken: Billboard: Hatch, next exit, the chile capital of the world, by its own count. Its Labor Day festival draws thousands. Mild is a matter of opinion.

### Hatch chile (from El Paso)
- treatment: billboard
- leg: el_paso_tx_us -> albuquerque_nm_us
- at_mi: 80.1
- spoken: Billboard: Hatch, next exit, the chile capital of the world, by its own count. Its Labor Day festival draws thousands. Mild is a matter of opinion.

### Hatch chile (from Albuquerque)
- treatment: billboard
- leg: albuquerque_nm_us -> el_paso_tx_us
- at_mi: 182.5
- spoken: Billboard: Hatch, next exit, the chile capital of the world, by its own count. Its Labor Day festival draws thousands. Mild is a matter of opinion.

## Mesilla, Las Cruces

Mesilla's plaza is a National Historic Landmark; in 1881 the Santa Fe
Railway chose Las Cruces over Mesilla in a dispute over land costs, and
Mesilla stopped growing (Wikipedia).

### Mesilla (from Alamogordo)
- treatment: billboard
- leg: alamogordo_nm_us -> las_cruces_nm_us
- at_mi: 59.1
- spoken: Billboard: Mesilla, ahead by Las Cruces. The railroad bypassed it in eighteen eighty-one over land prices, which kept the old plaza old. Thank the haggling.

### Mesilla (from El Paso)
- treatment: billboard
- leg: el_paso_tx_us -> las_cruces_nm_us
- at_mi: 33.7
- spoken: Billboard: Mesilla, ahead by Las Cruces. The railroad bypassed it in eighteen eighty-one over land prices, which kept the old plaza old. Thank the haggling.

### Mesilla (from Midland)
- treatment: billboard
- leg: midland_tx_us -> las_cruces_nm_us
- at_mi: 338.7
- spoken: Billboard: Mesilla, ahead by Las Cruces. The railroad bypassed it in eighteen eighty-one over land prices, which kept the old plaza old. Thank the haggling.

### Mesilla (from Tucson)
- treatment: billboard
- leg: tucson_az_us -> las_cruces_nm_us
- at_mi: 263.3
- spoken: Billboard: Mesilla, ahead by Las Cruces. The railroad bypassed it in eighteen eighty-one over land prices, which kept the old plaza old. Thank the haggling.

### Mesilla (from Socorro)
- treatment: billboard
- leg: socorro_nm_us -> las_cruces_nm_us
- at_mi: 136.9
- spoken: Billboard: Mesilla, ahead by Las Cruces. The railroad bypassed it in eighteen eighty-one over land prices, which kept the old plaza old. Thank the haggling.

### Mesilla (from El Paso)
- treatment: billboard
- leg: el_paso_tx_us -> tucson_az_us
- at_mi: 34.6
- spoken: Billboard: Mesilla, ahead by Las Cruces. The railroad bypassed it in eighteen eighty-one over land prices, which kept the old plaza old. Thank the haggling.

### Mesilla (from Tucson)
- treatment: billboard
- leg: tucson_az_us -> el_paso_tx_us
- at_mi: 264.4
- spoken: Billboard: Mesilla, ahead by Las Cruces. The railroad bypassed it in eighteen eighty-one over land prices, which kept the old plaza old. Thank the haggling.

## Rockhound State Park, Deming (I-10)

Seven miles southeast of Deming; when it opened in 1966 it was the first
park in the country to let visitors collect rocks and minerals for
personal use (Wikipedia).

### Rockhound State Park (from Las Cruces)
- treatment: billboard
- leg: las_cruces_nm_us -> tucson_az_us
- at_mi: 50.3
- spoken: Billboard: Rockhound State Park, ahead near Deming, the first park in the country to let you take the rocks home. Your suspension gets a vote.

### Rockhound State Park (from Tucson)
- treatment: billboard
- leg: tucson_az_us -> las_cruces_nm_us
- at_mi: 206.7
- spoken: Billboard: Rockhound State Park, ahead near Deming, the first park in the country to let you take the rocks home. Your suspension gets a vote.

### Rockhound State Park (from El Paso)
- treatment: billboard
- leg: el_paso_tx_us -> tucson_az_us
- at_mi: 92.7
- spoken: Billboard: Rockhound State Park, ahead near Deming, the first park in the country to let you take the rocks home. Your suspension gets a vote.

### Rockhound State Park (from Tucson)
- treatment: billboard
- leg: tucson_az_us -> el_paso_tx_us
- at_mi: 206.3
- spoken: Billboard: Rockhound State Park, ahead near Deming, the first park in the country to let you take the rocks home. Your suspension gets a vote.

## White Sands National Park (US 70)

The largest gypsum dunefield on Earth, with sledding on the dunes; the park
and US 70 between Las Cruces and Alamogordo close for hours during missile
tests on the neighboring range (Wikipedia).

### White Sands National Park (from Las Cruces)
- treatment: billboard
- leg: las_cruces_nm_us -> alamogordo_nm_us
- at_mi: 42.9
- spoken: Billboard: White Sands National Park, ahead. The largest gypsum dunefield on Earth, and you may sled it. This road closes now and then for missile tests.

### White Sands National Park (from Alamogordo)
- treatment: billboard
- leg: alamogordo_nm_us -> las_cruces_nm_us
- at_mi: 7.1
- spoken: Billboard: White Sands National Park, ahead. The largest gypsum dunefield on Earth, and you may sled it. This road closes now and then for missile tests.

## New Mexico Museum of Space History, Alamogordo

The International Space Hall of Fame and planetarium; Ham, the chimpanzee
who flew in January 1961, months before the first American astronaut, is
buried on its grounds (Wikipedia).

### Museum of Space History (from El Paso)
- treatment: billboard
- leg: el_paso_tx_us -> alamogordo_nm_us
- at_mi: 79.3
- spoken: Billboard: The New Mexico Museum of Space History, ahead in Alamogordo. Ham, the first chimpanzee in space, is buried on the grounds. He went first.

### Museum of Space History (from Roswell)
- treatment: billboard
- leg: roswell_nm_us -> alamogordo_nm_us
- at_mi: 108.0
- spoken: Billboard: The New Mexico Museum of Space History, ahead in Alamogordo. Ham, the first chimpanzee in space, is buried on the grounds. He went first.

### Museum of Space History (from Las Cruces)
- treatment: billboard
- leg: las_cruces_nm_us -> alamogordo_nm_us
- at_mi: 60.9
- spoken: Billboard: The New Mexico Museum of Space History, ahead in Alamogordo. Ham, the first chimpanzee in space, is buried on the grounds. He went first.

## Carlsbad Caverns National Park (southwest of Carlsbad)

Eighteen miles southwest of Carlsbad on US 62/180; the Big Room is the
largest cave chamber in North America (Wikipedia). Signed on the three legs
into Carlsbad.

### Carlsbad Caverns (from Hobbs)
- treatment: billboard
- leg: hobbs_nm_us -> carlsbad_nm_us
- at_mi: 59.2
- spoken: Billboard: Carlsbad Caverns National Park, southwest of Carlsbad. The Big Room is the largest cave chamber in North America. Your whole fleet would fit.

### Carlsbad Caverns (from Odessa)
- treatment: billboard
- leg: odessa_tx_us -> carlsbad_nm_us
- at_mi: 152.9
- spoken: Billboard: Carlsbad Caverns National Park, southwest of Carlsbad. The Big Room is the largest cave chamber in North America. Your whole fleet would fit.

### Carlsbad Caverns (from Roswell)
- treatment: billboard
- leg: roswell_nm_us -> carlsbad_nm_us
- at_mi: 64.9
- spoken: Billboard: Carlsbad Caverns National Park, southwest of Carlsbad. The Big Room is the largest cave chamber in North America. Your whole fleet would fit.

## Notes for the owner

Sources: https://en.wikipedia.org/wiki/Blue_Hole_(New_Mexico) ,
https://en.wikipedia.org/wiki/Sandia_Peak_Tramway ,
https://en.wikipedia.org/wiki/Acoma_Pueblo ,
https://en.wikipedia.org/wiki/El_Rancho_Hotel_%26_Motel ,
https://en.wikipedia.org/wiki/Meow_Wolf ,
https://en.wikipedia.org/wiki/Bosque_del_Apache_National_Wildlife_Refuge ,
https://en.wikipedia.org/wiki/Truth_or_Consequences,_New_Mexico ,
https://en.wikipedia.org/wiki/Hatch,_New_Mexico ,
https://en.wikipedia.org/wiki/Mesilla,_New_Mexico ,
https://en.wikipedia.org/wiki/Rockhound_State_Park ,
https://en.wikipedia.org/wiki/White_Sands_National_Park ,
https://en.wikipedia.org/wiki/New_Mexico_Museum_of_Space_History ,
https://en.wikipedia.org/wiki/Carlsbad_Caverns_National_Park ,
https://www.recreation.gov/gateways/13639 (El Camino Real directions),
https://www.recreation.gov/gateways/13832 (Santa Fe Trail directions),
https://www.newmexico.org/places-to-visit/scenic-byways/route-66-national/ .

Dropped:

- **Bottomless Lakes State Park.** The Roswell to Lubbock leg leaves town
  to the northeast and never passes the park's turnoff.
- **McGinn's PistachioLand, the New Mexico Mining Museum, Russell's car
  museum at Glenrio.** Present status could not be confirmed this session.
- **Fort Union, Raton, Springer.** On the Santa Fe Trail byway stretch of
  I-25.
- **Aztec Ruins.** US 550 north of Farmington may be part of the Trail of
  the Ancients byway; not confirmed either way, so left out.
