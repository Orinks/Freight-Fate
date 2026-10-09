
# West and South Texas attractions, both directions -- 2026-09-30

Draft for the owner's review, not yet approved.

46 real roadside attractions in Texas west of I-35, Laredo and the Rio
Grande Valley, each signed in every direction a leg passes it, 177
signs in all. Four of the sections add directions to places that already
have a placed sign (Cadillac Ranch, the Big Texan, the World's Littlest
Skyscraper, Langtry's Law West of the Pecos) and reuse that sign's copy word
for word. Every `leg:` is written the way the driver reads the sign and
`at_mi` counts from that end; `tools/bake_billboards.py` mirrors the milepost
onto a leg stored the other way round and records which way the billboard
faces.

Mileposts come from projecting each attraction (OpenStreetMap coordinates)
onto the legs' dense geometry, read against each leg's interchange list.
"Next exit" signs stand between the attraction's exit and the exit before
it, one to two miles out; "ahead" signs mostly five to twelve miles out,
as little as a mile where a string of village callouts leaves no other gap. A sign about a
city stands on the legs into it, never on the ones leaving. Each sign sits at
least 2.2 miles from every other callout heard in the same direction (rivers,
museums, villages within a mile and a half of the road, billboards facing the
same way, and every other sign on this sheet). No sign stands on a road where
Texas law bars billboards; see the notes.

## Cadillac Ranch, Amarillo (I-40 between Exits 60 and 62) -- added directions

Ten Cadillacs buried nose-down on the south frontage road west of Amarillo, open every day, free (Roadside America; OpenStreetMap places it at the frontage road, 35.187 N 101.987 W). It is already signed westbound out of Amarillo (mile 8 on the Amarillo to Tucumcari direction). These add the eastbound approaches and the two westbound legs that have none, with the existing copy word for word.

### Cadillac Ranch (eastbound)
- treatment: billboard
- leg: tucumcari_nm_us -> amarillo_tx_us
- at_mi: 96.0
- spoken: Billboard: Cadillac Ranch is ahead. Ten Cadillacs are buried nose-down in a field with their tailfins to the sky, and you are invited to spray-paint them. Bring a can.

### Cadillac Ranch (eastbound)
- treatment: billboard
- leg: albuquerque_nm_us -> amarillo_tx_us
- at_mi: 269.5
- spoken: Billboard: Cadillac Ranch is ahead. Ten Cadillacs are buried nose-down in a field with their tailfins to the sky, and you are invited to spray-paint them. Bring a can.

### Cadillac Ranch (eastbound)
- treatment: billboard
- leg: albuquerque_nm_us -> dallas_tx_us
- at_mi: 269.5
- spoken: Billboard: Cadillac Ranch is ahead. Ten Cadillacs are buried nose-down in a field with their tailfins to the sky, and you are invited to spray-paint them. Bring a can.

### Cadillac Ranch (westbound)
- treatment: billboard
- leg: amarillo_tx_us -> albuquerque_nm_us
- at_mi: 8.0
- spoken: Billboard: Cadillac Ranch is ahead. Ten Cadillacs are buried nose-down in a field with their tailfins to the sky, and you are invited to spray-paint them. Bring a can.

### Cadillac Ranch (westbound)
- treatment: billboard
- leg: dallas_tx_us -> albuquerque_nm_us
- at_mi: 361.0
- spoken: Billboard: Cadillac Ranch is ahead. Ten Cadillacs are buried nose-down in a field with their tailfins to the sky, and you are invited to spray-paint them. Bring a can.

## The Big Texan Steak Ranch, Amarillo (I-40 Exit 75) -- added directions

7701 I-40 East, north side at Exit 75, open daily (bigtexan.com; Roadside America tip 2805). Signed today only westbound on I-40 from Oklahoma City. These add the US 287 and US 60 approaches from the east and the through leg eastbound, with the existing copy word for word.

### The Big Texan Steak Ranch (from Clarendon)
- treatment: billboard
- leg: clarendon_tx_us -> amarillo_tx_us
- at_mi: 46.0
- spoken: Billboard: The Big Texan Steak Ranch is ahead in Amarillo. Finish the seventy-two-ounce steak dinner in one hour and it is free. Many appetites have entered; few have left with dignity.

### The Big Texan Steak Ranch (from Dallas)
- treatment: billboard
- leg: dallas_tx_us -> amarillo_tx_us
- at_mi: 348.0
- spoken: Billboard: The Big Texan Steak Ranch is ahead in Amarillo. Finish the seventy-two-ounce steak dinner in one hour and it is free. Many appetites have entered; few have left with dignity.

### The Big Texan Steak Ranch (westbound)
- treatment: billboard
- leg: dallas_tx_us -> albuquerque_nm_us
- at_mi: 347.5
- spoken: Billboard: The Big Texan Steak Ranch is ahead in Amarillo. Finish the seventy-two-ounce steak dinner in one hour and it is free. Many appetites have entered; few have left with dignity.

### The Big Texan Steak Ranch (from Pampa)
- treatment: billboard
- leg: pampa_tx_us -> amarillo_tx_us
- at_mi: 46.0
- spoken: Billboard: The Big Texan Steak Ranch is ahead in Amarillo. Finish the seventy-two-ounce steak dinner in one hour and it is free. Many appetites have entered; few have left with dignity.

### The Big Texan Steak Ranch (eastbound)
- treatment: billboard
- leg: albuquerque_nm_us -> dallas_tx_us
- at_mi: 283.0
- spoken: Billboard: The Big Texan Steak Ranch is ahead in Amarillo. Finish the seventy-two-ounce steak dinner in one hour and it is free. Many appetites have entered; few have left with dignity.

## Route 66 Midpoint and the Midpoint Cafe, Adrian (I-40 Exit 22)

The Midpoint sign on old Route 66 reads Los Angeles 1139 miles, Chicago 1139 miles; the Midpoint Cafe, 305 West Historic Route 66, opened in 1928 and is open March through October (Wikipedia, Adrian, Texas and Midpoint Cafe; NewsChannel 10, July 2025). Signs stand between Exit 28 or 18 and Exit 22, clear of the leg's own Adrian village callout.

### Route 66 Midpoint (eastbound)
- treatment: billboard
- leg: tucumcari_nm_us -> amarillo_tx_us
- at_mi: 62.6
- spoken: Billboard: The Route sixty-six Midpoint, next exit in Adrian. Chicago and Los Angeles are each eleven hundred thirty-nine miles away. Halfway calls for pie.

### Route 66 Midpoint (westbound)
- treatment: billboard
- leg: amarillo_tx_us -> tucumcari_nm_us
- at_mi: 46.8
- spoken: Billboard: The Route sixty-six Midpoint, next exit in Adrian. Chicago and Los Angeles are each eleven hundred thirty-nine miles away. Halfway calls for pie.

### Route 66 Midpoint (westbound)
- treatment: billboard
- leg: amarillo_tx_us -> albuquerque_nm_us
- at_mi: 48.0
- spoken: Billboard: The Route sixty-six Midpoint, next exit in Adrian. Chicago and Los Angeles are each eleven hundred thirty-nine miles away. Halfway calls for pie.

### Route 66 Midpoint (eastbound)
- treatment: billboard
- leg: albuquerque_nm_us -> amarillo_tx_us
- at_mi: 236.5
- spoken: Billboard: The Route sixty-six Midpoint, next exit in Adrian. Chicago and Los Angeles are each eleven hundred thirty-nine miles away. Halfway calls for pie.

### Route 66 Midpoint (westbound)
- treatment: billboard
- leg: dallas_tx_us -> albuquerque_nm_us
- at_mi: 405.4
- spoken: Billboard: The Route sixty-six Midpoint, next exit in Adrian. Chicago and Los Angeles are each eleven hundred thirty-nine miles away. Halfway calls for pie.

### Route 66 Midpoint (eastbound)
- treatment: billboard
- leg: albuquerque_nm_us -> dallas_tx_us
- at_mi: 234.0
- spoken: Billboard: The Route sixty-six Midpoint, next exit in Adrian. Chicago and Los Angeles are each eleven hundred thirty-nine miles away. Halfway calls for pie.

## The Cross of Our Lord Jesus Christ, Groom (I-40 Exit 112)

A free-standing cross 190 feet tall, nineteen stories, seen from about twenty miles, with a visitor center and the Stations of the Cross, next to I-40 at Exit 112; Groom's leaning water tower stands at the east edge of town (Wikipedia, Groom, Texas; route66news 2022). Exit 112 is not in the leg's interchange list, so both signs read "ahead", about eight miles out.

### The Cross at Groom (westbound)
- treatment: billboard
- leg: oklahoma_city_ok_us -> amarillo_tx_us
- at_mi: 208.5
- spoken: Billboard: The Cross of Our Lord Jesus Christ, ahead in Groom. Nineteen stories tall. The town's water tower leans on purpose, so your mirrors are fine.

### The Cross at Groom (eastbound)
- treatment: billboard
- leg: amarillo_tx_us -> oklahoma_city_ok_us
- at_mi: 33.0
- spoken: Billboard: The Cross of Our Lord Jesus Christ, ahead in Groom. Nineteen stories tall. The town's water tower leans on purpose, so your mirrors are fine.

## Devil's Rope Museum, McLean (I-40 Exits 141 and 142)

The barbed wire and Route 66 museum at 100 Kingsley Street, more than 2,000 kinds of wire, open March through October (barbwiremuseum.com; Texas Highways; Route 66 News, March 2026).

### Devil's Rope Museum (westbound)
- treatment: billboard
- leg: oklahoma_city_ok_us -> amarillo_tx_us
- at_mi: 183.5
- spoken: Billboard: The Devil's Rope Museum, next exit in McLean. More than two thousand kinds of barbed wire under one roof. Please do not lean on the exhibits.

### Devil's Rope Museum (eastbound)
- treatment: billboard
- leg: amarillo_tx_us -> oklahoma_city_ok_us
- at_mi: 68.8
- spoken: Billboard: The Devil's Rope Museum, next exit in McLean. More than two thousand kinds of barbed wire under one roof. Please do not lean on the exhibits.

## Tower Station and U-Drop Inn, Shamrock (I-40 Exit 163)

The 1936 art deco Conoco station and cafe on Route 66 at US 83, now the visitor center, open daily 10 to 4; it inspired Ramone's House of Body Art in Pixar's Cars (National Park Service, Tower Station and U-Drop Inn Cafe; Texas Highways).

### The U-Drop Inn (westbound)
- treatment: billboard
- leg: oklahoma_city_ok_us -> amarillo_tx_us
- at_mi: 162.9
- spoken: Billboard: The U-Drop Inn, next exit in Shamrock. A nineteen thirty-six art deco gas station that helped inspire the movie Cars. No fuel now, just photographs.

### The U-Drop Inn (eastbound)
- treatment: billboard
- leg: amarillo_tx_us -> oklahoma_city_ok_us
- at_mi: 91.3
- spoken: Billboard: The U-Drop Inn, next exit in Shamrock. A nineteen thirty-six art deco gas station that helped inspire the movie Cars. No fuel now, just photographs.

## Charles and Mary Ann Goodnight Ranch State Historic Site, Goodnight (US 287)

The Goodnights' 1887 Victorian ranch house at 2000 US 287, Texas Historical Commission, Tuesday to Saturday, with descendants of their bison herd in the pasture; Mary Ann helped preserve the American bison (thc.texas.gov). No exits on these legs; signs about eight miles out.

### The Goodnight Ranch (westbound)
- treatment: billboard
- leg: clarendon_tx_us -> amarillo_tx_us
- at_mi: 10.0
- spoken: Billboard: The Goodnight Ranch, ahead. The Goodnights' eighteen eighty-seven house, with bison from the herd Mary Ann helped save. The town is Goodnight. Stay awake.

### The Goodnight Ranch (eastbound)
- treatment: billboard
- leg: amarillo_tx_us -> clarendon_tx_us
- at_mi: 33.0
- spoken: Billboard: The Goodnight Ranch, ahead. The Goodnights' eighteen eighty-seven house, with bison from the herd Mary Ann helped save. The town is Goodnight. Stay awake.

### The Goodnight Ranch (eastbound)
- treatment: billboard
- leg: amarillo_tx_us -> dallas_tx_us
- at_mi: 33.0
- spoken: Billboard: The Goodnight Ranch, ahead. The Goodnights' eighteen eighty-seven house, with bison from the herd Mary Ann helped save. The town is Goodnight. Stay awake.

### The Goodnight Ranch (westbound)
- treatment: billboard
- leg: dallas_tx_us -> amarillo_tx_us
- at_mi: 312.5
- spoken: Billboard: The Goodnight Ranch, ahead. The Goodnights' eighteen eighty-seven house, with bison from the herd Mary Ann helped save. The town is Goodnight. Stay awake.

### The Goodnight Ranch (westbound)
- treatment: billboard
- leg: dallas_tx_us -> albuquerque_nm_us
- at_mi: 312.0
- spoken: Billboard: The Goodnight Ranch, ahead. The Goodnights' eighteen eighty-seven house, with bison from the herd Mary Ann helped save. The town is Goodnight. Stay awake.

### The Goodnight Ranch (eastbound)
- treatment: billboard
- leg: albuquerque_nm_us -> dallas_tx_us
- at_mi: 317.5
- spoken: Billboard: The Goodnight Ranch, ahead. The Goodnights' eighteen eighty-seven house, with bison from the herd Mary Ann helped save. The town is Goodnight. Stay awake.

## Woody Guthrie Folk Music Center, Pampa (city node)

320 South Cuyler, in the old Harris Drug store where Woody, who lived in Pampa from 1929, found a broken guitar in the back room; free Friday night jam sessions, concerts on the 2026 calendar (ABC 7 Amarillo; High Plains Public Radio calendar). Pampa is a city node; signs stand on the two legs into it.

### Woody Guthrie Folk Music Center (from Amarillo)
- treatment: billboard
- leg: amarillo_tx_us -> pampa_tx_us
- at_mi: 50.0
- spoken: Billboard: The Woody Guthrie Folk Music Center, ahead in Pampa. He found a busted guitar in the back of this drug store. Bring yours Friday night.

### Woody Guthrie Folk Music Center (from Clarendon)
- treatment: billboard
- leg: clarendon_tx_us -> pampa_tx_us
- at_mi: 39.0
- spoken: Billboard: The Woody Guthrie Folk Music Center, ahead in Pampa. He found a busted guitar in the back of this drug store. Bring yours Friday night.

## Palo Duro Canyon State Park, Canyon (I-27 Exit 106, then SH 217 east)

The second largest canyon in the United States, 120 miles long and about 800 feet deep; open daily (tpwd.texas.gov). SH 217 runs from Canyon about thirteen and a half miles to the park road (Wikipedia, Texas State Highway 217). On I-27 the legs list the Canyon exit as "Canyon, Palo Duro Canyon State Park" (Exit 636 in their numbering); those signs read "next exit". The US 60 legs come through Canyon, so theirs read "ahead through Canyon".

### Palo Duro Canyon (northbound)
- treatment: billboard
- leg: plainview_tx_us -> amarillo_tx_us
- at_mi: 58.0
- spoken: Billboard: Palo Duro Canyon, next exit, then twelve miles east. The second largest canyon in the country. The Panhandle is not as flat as advertised.

### Palo Duro Canyon (northbound)
- treatment: billboard
- leg: midland_tx_us -> amarillo_tx_us
- at_mi: 219.0
- spoken: Billboard: Palo Duro Canyon, next exit, then twelve miles east. The second largest canyon in the country. The Panhandle is not as flat as advertised.

### Palo Duro Canyon (southbound)
- treatment: billboard
- leg: amarillo_tx_us -> plainview_tx_us
- at_mi: 18.6
- spoken: Billboard: Palo Duro Canyon, next exit, then twelve miles east. The second largest canyon in the country. The Panhandle is not as flat as advertised.

### Palo Duro Canyon (southbound)
- treatment: billboard
- leg: amarillo_tx_us -> midland_tx_us
- at_mi: 17.6
- spoken: Billboard: Palo Duro Canyon, next exit, then twelve miles east. The second largest canyon in the country. The Panhandle is not as flat as advertised.

### Palo Duro Canyon (eastbound)
- treatment: billboard
- leg: clovis_nm_us -> amarillo_tx_us
- at_mi: 80.0
- spoken: Billboard: Palo Duro Canyon, ahead through Canyon, then twelve miles east. The second largest canyon in the country. The Panhandle is not as flat as advertised.

### Palo Duro Canyon (eastbound)
- treatment: billboard
- leg: hereford_tx_us -> amarillo_tx_us
- at_mi: 22.0
- spoken: Billboard: Palo Duro Canyon, ahead through Canyon, then twelve miles east. The second largest canyon in the country. The Panhandle is not as flat as advertised.

### Palo Duro Canyon (westbound)
- treatment: billboard
- leg: amarillo_tx_us -> clovis_nm_us
- at_mi: 13.5
- spoken: Billboard: Palo Duro Canyon, ahead through Canyon, then twelve miles east. The second largest canyon in the country. The Panhandle is not as flat as advertised.

### Palo Duro Canyon (westbound)
- treatment: billboard
- leg: amarillo_tx_us -> hereford_tx_us
- at_mi: 13.5
- spoken: Billboard: Palo Duro Canyon, ahead through Canyon, then twelve miles east. The second largest canyon in the country. The Panhandle is not as flat as advertised.

## Ozymandias on the Plains, south Amarillo (I-27 at Sundown Lane)

Two giant legs in a pasture beside I-27, Stanley Marsh 3's joke on Shelley, built by Lightnin' McDuff; pranksters keep painting socks on them and the socks keep coming back (Slate/Atlas Obscura 2013; KFYO; OpenStreetMap, West Sundown Lane, 35.102 N 101.909 W). Visible from the road and the frontage road; the legs pass it about ten miles from the Amarillo stop.

### Ozymandias on the Plains (southbound)
- treatment: billboard
- leg: amarillo_tx_us -> midland_tx_us
- at_mi: 4.5
- spoken: Billboard: Ozymandias on the Plains, ahead beside the highway. Two giant legs standing alone in a pasture, wearing socks. Somebody keeps painting the socks back on.

### Ozymandias on the Plains (southbound)
- treatment: billboard
- leg: amarillo_tx_us -> plainview_tx_us
- at_mi: 4.5
- spoken: Billboard: Ozymandias on the Plains, ahead beside the highway. Two giant legs standing alone in a pasture, wearing socks. Somebody keeps painting the socks back on.

### Ozymandias on the Plains (southbound)
- treatment: billboard
- leg: amarillo_tx_us -> clovis_nm_us
- at_mi: 4.5
- spoken: Billboard: Ozymandias on the Plains, ahead beside the highway. Two giant legs standing alone in a pasture, wearing socks. Somebody keeps painting the socks back on.

### Ozymandias on the Plains (southbound)
- treatment: billboard
- leg: amarillo_tx_us -> hereford_tx_us
- at_mi: 4.5
- spoken: Billboard: Ozymandias on the Plains, ahead beside the highway. Two giant legs standing alone in a pasture, wearing socks. Somebody keeps painting the socks back on.

### Ozymandias on the Plains (northbound)
- treatment: billboard
- leg: plainview_tx_us -> amarillo_tx_us
- at_mi: 64.5
- spoken: Billboard: Ozymandias on the Plains, ahead beside the highway. Two giant legs standing alone in a pasture, wearing socks. Somebody keeps painting the socks back on.

### Ozymandias on the Plains (northbound)
- treatment: billboard
- leg: midland_tx_us -> amarillo_tx_us
- at_mi: 225.0
- spoken: Billboard: Ozymandias on the Plains, ahead beside the highway. Two giant legs standing alone in a pasture, wearing socks. Somebody keeps painting the socks back on.

### Ozymandias on the Plains (northbound)
- treatment: billboard
- leg: clovis_nm_us -> amarillo_tx_us
- at_mi: 91.5
- spoken: Billboard: Ozymandias on the Plains, ahead beside the highway. Two giant legs standing alone in a pasture, wearing socks. Somebody keeps painting the socks back on.

### Ozymandias on the Plains (northbound)
- treatment: billboard
- leg: hereford_tx_us -> amarillo_tx_us
- at_mi: 33.5
- spoken: Billboard: Ozymandias on the Plains, ahead beside the highway. Two giant legs standing alone in a pasture, wearing socks. Somebody keeps painting the socks back on.

## Buddy Holly Center, Lubbock (city node)

1801 Crickets Avenue, Tuesday to Sunday; his guitars and glasses inside and a 750-pound pair of black-rimmed glasses out front, built 2002 (Roadside America tip 6824; visitlubbock.org). Lubbock is a city node; signs stand on each leg into it, plus both directions of the Midland to Amarillo leg that runs through. Midland to Lubbock is left out: it already ends on a "The Buddy Holly Center" museum callout.

### Buddy Holly Center (from Hobbs)
- treatment: billboard
- leg: hobbs_nm_us -> lubbock_tx_us
- at_mi: 102.0
- spoken: Billboard: The Buddy Holly Center, ahead in Lubbock. His guitar and glasses inside, and a seven-hundred-fifty-pound pair of glasses out front. No prescription required.

### Buddy Holly Center (from Roswell)
- treatment: billboard
- leg: roswell_nm_us -> lubbock_tx_us
- at_mi: 200.5
- spoken: Billboard: The Buddy Holly Center, ahead in Lubbock. His guitar and glasses inside, and a seven-hundred-fifty-pound pair of glasses out front. No prescription required.

### Buddy Holly Center (from Abilene)
- treatment: billboard
- leg: abilene_tx_us -> lubbock_tx_us
- at_mi: 156.0
- spoken: Billboard: The Buddy Holly Center, ahead in Lubbock. His guitar and glasses inside, and a seven-hundred-fifty-pound pair of glasses out front. No prescription required.

### Buddy Holly Center (from Dallas)
- treatment: billboard
- leg: dallas_tx_us -> lubbock_tx_us
- at_mi: 316.0
- spoken: Billboard: The Buddy Holly Center, ahead in Lubbock. His guitar and glasses inside, and a seven-hundred-fifty-pound pair of glasses out front. No prescription required.

### Buddy Holly Center (from Plainview)
- treatment: billboard
- leg: plainview_tx_us -> lubbock_tx_us
- at_mi: 40.0
- spoken: Billboard: The Buddy Holly Center, ahead in Lubbock. His guitar and glasses inside, and a seven-hundred-fifty-pound pair of glasses out front. No prescription required.

### Buddy Holly Center (northbound)
- treatment: billboard
- leg: midland_tx_us -> amarillo_tx_us
- at_mi: 108.5
- spoken: Billboard: The Buddy Holly Center, ahead in Lubbock. His guitar and glasses inside, and a seven-hundred-fifty-pound pair of glasses out front. No prescription required.

### Buddy Holly Center (southbound)
- treatment: billboard
- leg: amarillo_tx_us -> midland_tx_us
- at_mi: 114.5
- spoken: Billboard: The Buddy Holly Center, ahead in Lubbock. His guitar and glasses inside, and a seven-hundred-fifty-pound pair of glasses out front. No prescription required.

## Frontier Texas!, Abilene (city node)

625 North First Street, the city's visitor center and frontier museum, with holographic "spirit guides" led by Gunsmoke's Buck Taylor; open daily (authentictexas.com; Group Tour Magazine). Signs stand on the six legs into Abilene.

### Frontier Texas (westbound)
- treatment: billboard
- leg: fort_worth_tx_us -> abilene_tx_us
- at_mi: 142.5
- spoken: Billboard: Frontier Texas, ahead in Abilene. The old frontier, told by a cast of holograms. The only cowboys in Texas who never stop for lunch.

### Frontier Texas (eastbound)
- treatment: billboard
- leg: big_spring_tx_us -> abilene_tx_us
- at_mi: 99.0
- spoken: Billboard: Frontier Texas, ahead in Abilene. The old frontier, told by a cast of holograms. The only cowboys in Texas who never stop for lunch.

### Frontier Texas (from Wichita Falls)
- treatment: billboard
- leg: wichita_falls_tx_us -> abilene_tx_us
- at_mi: 145.0
- spoken: Billboard: Frontier Texas, ahead in Abilene. The old frontier, told by a cast of holograms. The only cowboys in Texas who never stop for lunch.

### Frontier Texas (from Brownwood)
- treatment: billboard
- leg: brownwood_tx_us -> abilene_tx_us
- at_mi: 82.0
- spoken: Billboard: Frontier Texas, ahead in Abilene. The old frontier, told by a cast of holograms. The only cowboys in Texas who never stop for lunch.

### Frontier Texas (from Lubbock)
- treatment: billboard
- leg: lubbock_tx_us -> abilene_tx_us
- at_mi: 153.5
- spoken: Billboard: Frontier Texas, ahead in Abilene. The old frontier, told by a cast of holograms. The only cowboys in Texas who never stop for lunch.

### Frontier Texas (from San Angelo)
- treatment: billboard
- leg: san_angelo_tx_us -> abilene_tx_us
- at_mi: 81.0
- spoken: Billboard: Frontier Texas, ahead in Abilene. The old frontier, told by a cast of holograms. The only cowboys in Texas who never stop for lunch.

## National WASP WWII Museum, Sweetwater (I-20 Exit 240)

210 Avenger Field Road, just off I-20 Exit 240 at Loop 170; Avenger Field became in April 1943 the first air base to train only women pilots; open Tuesday to Saturday (waspmuseum.org, 2026 hours). Exit 240 is not in the legs' interchange lists, so all four read "ahead".

### WASP Museum (eastbound)
- treatment: billboard
- leg: big_spring_tx_us -> abilene_tx_us
- at_mi: 55.0
- spoken: Billboard: The National WASP World War Two Museum, ahead in Sweetwater. The first air base to train only women pilots. They learned in this wind.

### WASP Museum (eastbound)
- treatment: billboard
- leg: lubbock_tx_us -> abilene_tx_us
- at_mi: 111.0
- spoken: Billboard: The National WASP World War Two Museum, ahead in Sweetwater. The first air base to train only women pilots. They learned in this wind.

### WASP Museum (westbound)
- treatment: billboard
- leg: abilene_tx_us -> big_spring_tx_us
- at_mi: 37.5
- spoken: Billboard: The National WASP World War Two Museum, ahead in Sweetwater. The first air base to train only women pilots. They learned in this wind.

### WASP Museum (westbound)
- treatment: billboard
- leg: abilene_tx_us -> lubbock_tx_us
- at_mi: 37.0
- spoken: Billboard: The National WASP World War Two Museum, ahead in Sweetwater. The first air base to train only women pilots. They learned in this wind.

## Permian Basin Petroleum Museum, Midland (I-20, west side)

1500 West I-20, open daily; the 40-acre Oil Patch holds the world's largest collection of antique drilling equipment, and the Chaparral Gallery all of Jim Hall's Midland-built Chaparral race cars (petroleummuseum.org; Roadside America tip 1284). The Midland stop sits beside it, so every leg into Midland gets a sign and none leaving it does.

### The Petroleum Museum (eastbound)
- treatment: billboard
- leg: las_cruces_nm_us -> midland_tx_us
- at_mi: 337.5
- spoken: Billboard: The Petroleum Museum, ahead in Midland. Antique drilling rigs out back, Jim Hall's Chaparral race cars inside. All of it ran on the local product.

### The Petroleum Museum (from Odessa)
- treatment: billboard
- leg: odessa_tx_us -> midland_tx_us
- at_mi: 13.0
- spoken: Billboard: The Petroleum Museum, ahead in Midland. Antique drilling rigs out back, Jim Hall's Chaparral race cars inside. All of it ran on the local product.

### The Petroleum Museum (westbound)
- treatment: billboard
- leg: big_spring_tx_us -> midland_tx_us
- at_mi: 33.0
- spoken: Billboard: The Petroleum Museum, ahead in Midland. Antique drilling rigs out back, Jim Hall's Chaparral race cars inside. All of it ran on the local product.

### The Petroleum Museum (from San Angelo)
- treatment: billboard
- leg: san_angelo_tx_us -> midland_tx_us
- at_mi: 103.0
- spoken: Billboard: The Petroleum Museum, ahead in Midland. Antique drilling rigs out back, Jim Hall's Chaparral race cars inside. All of it ran on the local product.

### The Petroleum Museum (from Lubbock)
- treatment: billboard
- leg: lubbock_tx_us -> midland_tx_us
- at_mi: 110.0
- spoken: Billboard: The Petroleum Museum, ahead in Midland. Antique drilling rigs out back, Jim Hall's Chaparral race cars inside. All of it ran on the local product.

### The Petroleum Museum (from Amarillo)
- treatment: billboard
- leg: amarillo_tx_us -> midland_tx_us
- at_mi: 232.0
- spoken: Billboard: The Petroleum Museum, ahead in Midland. Antique drilling rigs out back, Jim Hall's Chaparral race cars inside. All of it ran on the local product.

## Odessa Meteor Crater (I-20 Exit 108, three miles south)

A 550-foot crater about 63,500 years old, with the Rodman museum and a quarter-mile trail; free, open daily (Wikipedia, Odessa Meteor Crater; Roadside America tip 26091). The legs list Exit 108 as "Moss Avenue, Meteor Crater".

### Odessa Meteor Crater (eastbound)
- treatment: billboard
- leg: las_cruces_nm_us -> midland_tx_us
- at_mi: 320.3
- spoken: Billboard: The Odessa Meteor Crater, next exit. A rock from space hit here sixty-three thousand years ago. Admission is free, and it has not been back.

### Odessa Meteor Crater (westbound)
- treatment: billboard
- leg: midland_tx_us -> las_cruces_nm_us
- at_mi: 26.2
- spoken: Billboard: The Odessa Meteor Crater, next exit. A rock from space hit here sixty-three thousand years ago. Admission is free, and it has not been back.

## Monahans Sandhills State Park (I-20 Exit 86)

Dunes up to 70 feet high on the north side of I-20, Park Road 41; sand discs for rent at headquarters, open daily (tpwd.texas.gov; Roadside America tip 35188). The legs list Exit 86 as "Monahans Sandhills State Park".

### Monahans Sandhills (eastbound)
- treatment: billboard
- leg: las_cruces_nm_us -> midland_tx_us
- at_mi: 297.5
- spoken: Billboard: Monahans Sandhills State Park, next exit. Dunes up to seventy feet tall, and they rent you a disc to ride down. Your boots will bring some home.

### Monahans Sandhills (westbound)
- treatment: billboard
- leg: midland_tx_us -> las_cruces_nm_us
- at_mi: 49.0
- spoken: Billboard: Monahans Sandhills State Park, next exit. Dunes up to seventy feet tall, and they rent you a disc to ride down. Your boots will bring some home.

## West of the Pecos Museum, Pecos (I-20 Exit 42)

120 East Dot Stafford Street at US 285: the 1896 saloon and the 1904 Orient Hotel, joined by a hallway; the town's rodeo began in 1883 (texastimetravel; Texas Historical Commission atlas; hours by season, closed Sunday and Monday in winter).

### West of the Pecos Museum (eastbound)
- treatment: billboard
- leg: las_cruces_nm_us -> midland_tx_us
- at_mi: 254.0
- spoken: Billboard: The West of the Pecos Museum, next exit. An old saloon with a hallway straight to the hotel. The rodeo here dates to eighteen eighty-three.

### West of the Pecos Museum (westbound)
- treatment: billboard
- leg: midland_tx_us -> las_cruces_nm_us
- at_mi: 92.5
- spoken: Billboard: The West of the Pecos Museum, next exit. An old saloon with a hallway straight to the hotel. The rodeo here dates to eighteen eighty-three.

## Paisano Pete, Fort Stockton (city node)

An 11-foot-tall, 22-foot-long roadrunner at Main and Dickinson since 1980, recently repainted (Texas Highways, Finding Fort Stockton; Just a Little Further 2022). Signs on the four legs into Fort Stockton.

### Paisano Pete (eastbound)
- treatment: billboard
- leg: van_horn_tx_us -> fort_stockton_tx_us
- at_mi: 110.5
- spoken: Billboard: Paisano Pete, ahead in Fort Stockton. A twenty-two-foot roadrunner on the same corner since nineteen eighty. Fastest bird in Texas, and he has not moved.

### Paisano Pete (westbound)
- treatment: billboard
- leg: ozona_tx_us -> fort_stockton_tx_us
- at_mi: 99.0
- spoken: Billboard: Paisano Pete, ahead in Fort Stockton. A twenty-two-foot roadrunner on the same corner since nineteen eighty. Fastest bird in Texas, and he has not moved.

### Paisano Pete (from Odessa)
- treatment: billboard
- leg: odessa_tx_us -> fort_stockton_tx_us
- at_mi: 91.0
- spoken: Billboard: Paisano Pete, ahead in Fort Stockton. A twenty-two-foot roadrunner on the same corner since nineteen eighty. Fastest bird in Texas, and he has not moved.

### Paisano Pete (from San Angelo)
- treatment: billboard
- leg: san_angelo_tx_us -> fort_stockton_tx_us
- at_mi: 156.0
- spoken: Billboard: Paisano Pete, ahead in Fort Stockton. A twenty-two-foot roadrunner on the same corner since nineteen eighty. Fastest bird in Texas, and he has not moved.

## Balmorhea State Park, Toyahvale (I-10 Exits 206 and 209, then south)

The 1.3-acre spring-fed pool, 25 feet at its deepest, where TPWD tells snorkelers to "swim with the fish"; two endangered desert fish live in the restored wetlands beside it. Open daily, reservations advised; park construction through September 2026 with the pool open (tpwd.texas.gov; Texas Highways). Westbound the sign stands before Exit 209 (SH 17, Balmorhea); eastbound before Exit 206 (FM 2903, Balmorhea).

### Balmorhea State Park (westbound)
- treatment: billboard
- leg: fort_stockton_tx_us -> van_horn_tx_us
- at_mi: 48.0
- spoken: Billboard: Balmorhea State Park, next exit, then south. A spring-fed pool twenty-five feet deep, out in the desert. Bring a swimsuit. The fish were here first.

### Balmorhea State Park (eastbound)
- treatment: billboard
- leg: van_horn_tx_us -> fort_stockton_tx_us
- at_mi: 64.5
- spoken: Billboard: Balmorhea State Park, next exit, then south. A spring-fed pool twenty-five feet deep, out in the desert. Bring a swimsuit. The fish were here first.

## Prada Marfa, near Valentine (US 90)

Elmgreen and Dragset's 2005 sculpture of a Prada shop on US 90 west of Valentine. In 2013 TxDOT classified it as an illegal outdoor advertising sign; in 2014 Ballroom Marfa leased the land and registered it as a museum with one exhibit (NBC DFW, Texas Monthly; ballroommarfa.org). Westbound the sign stands before the Valentine village callout.

### Prada Marfa (westbound)
- treatment: billboard
- leg: del_rio_tx_us -> van_horn_tx_us
- at_mi: 260.0
- spoken: Billboard: Prada Marfa, ahead. A locked Prada shop alone in the desert, nothing for sale. Texas once ruled it an illegal billboard. This one is legal.

### Prada Marfa (eastbound)
- treatment: billboard
- leg: van_horn_tx_us -> del_rio_tx_us
- at_mi: 29.0
- spoken: Billboard: Prada Marfa, ahead. A locked Prada shop alone in the desert, nothing for sale. Texas once ruled it an illegal billboard. This one is legal.

## Marfa Lights Viewing Area (US 90, nine miles east of Marfa)

The roadside viewing center built in 2003; lights first reported by cowhand Robert Ellison in 1883; a 2004 University of Texas at Dallas study matched many of them to headlights on US 67 (Wikipedia, Marfa lights; visitmarfa.com).

### Marfa Lights (westbound)
- treatment: billboard
- leg: del_rio_tx_us -> van_horn_tx_us
- at_mi: 214.0
- spoken: Billboard: The Marfa Lights Viewing Area, ahead. A cowhand reported strange lights here in eighteen eighty-three. Some may be headlights. Please do not add yours.

### Marfa Lights (eastbound)
- treatment: billboard
- leg: van_horn_tx_us -> del_rio_tx_us
- at_mi: 75.0
- spoken: Billboard: The Marfa Lights Viewing Area, ahead. A cowhand reported strange lights here in eighteen eighty-three. Some may be headlights. Please do not add yours.

## Big Bend National Park, by US 385 south from Marathon

The National Park Service measures the darkest night skies in the lower 48 here; US 385 leaves US 90 in Marathon for the north entrance at Persimmon Gap (nps.gov, The Darkness That Refreshes; DarkSky). US 385 is not on the Transportation Code 391.252 list; the Big Bend roads that are (SH 118, SH 17, FM 170) carry no signs here.

### Big Bend National Park (westbound)
- treatment: billboard
- leg: del_rio_tx_us -> van_horn_tx_us
- at_mi: 165.0
- spoken: Billboard: Big Bend National Park, turn south at Marathon. The darkest measured night skies in the lower forty-eight. Out there, your dash lights count as light pollution.

### Big Bend National Park (eastbound)
- treatment: billboard
- leg: van_horn_tx_us -> del_rio_tx_us
- at_mi: 123.0
- spoken: Billboard: Big Bend National Park, turn south at Marathon. The darkest measured night skies in the lower forty-eight. Out there, your dash lights count as light pollution.

## Seminole Canyon State Park and Historic Site (US 90, nine miles west of Comstock)

Fate Bell Shelter's pictographs, at least 4,000 years old, on a guided walk Wednesday to Sunday (tpwd.texas.gov calendar; Lonely Planet). The entrance is just east of the Pecos River bridge, so the westbound sign sits between the Comstock and Pecos River callouts.

### Seminole Canyon (westbound)
- treatment: billboard
- leg: del_rio_tx_us -> van_horn_tx_us
- at_mi: 35.0
- spoken: Billboard: Seminole Canyon State Park, ahead. Rock paintings at least four thousand years old, seen on a guided walk. The oldest signs on this highway.

### Seminole Canyon (eastbound)
- treatment: billboard
- leg: van_horn_tx_us -> del_rio_tx_us
- at_mi: 257.0
- spoken: Billboard: Seminole Canyon State Park, ahead. Rock paintings at least four thousand years old, seen on a guided walk. The oldest signs on this highway.

## Judge Roy Bean Visitor Center, Langtry (US 90) -- added direction

The TxDOT travel information center at the Jersey Lilly saloon, Loop 25 in Langtry. Already signed southbound into Del Rio on US 277 as "The Law West of the Pecos". This adds the westbound US 90 approach, the only other direction where the existing copy ("Beyond Del Rio lies Langtry") is true, word for word.

### The Law West of the Pecos (westbound)
- treatment: billboard
- leg: del_rio_tx_us -> van_horn_tx_us
- at_mi: 51.0
- spoken: Billboard: Beyond Del Rio lies Langtry, where Judge Roy Bean held court in a saloon and called himself the Law West of the Pecos. He once fined a dead man for carrying a concealed weapon and kept the money.

## Val Verde Winery, Del Rio (city node)

100 Qualia Drive; founded 1883 by Frank Qualia and run by the fourth generation, the oldest bonded winery in Texas; tours and tastings daily (valverdewinery.com; Val Verde County Historical Commission marker). Signs on the four legs into Del Rio.

### Val Verde Winery (from Eagle Pass)
- treatment: billboard
- leg: eagle_pass_tx_us -> del_rio_tx_us
- at_mi: 49.0
- spoken: Billboard: Val Verde Winery, ahead in Del Rio. Texas's oldest winery, one family since eighteen eighty-three. The driver tours. The bottle buckles up.

### Val Verde Winery (from Uvalde)
- treatment: billboard
- leg: uvalde_tx_us -> del_rio_tx_us
- at_mi: 62.0
- spoken: Billboard: Val Verde Winery, ahead in Del Rio. Texas's oldest winery, one family since eighteen eighty-three. The driver tours. The bottle buckles up.

### Val Verde Winery (from San Angelo)
- treatment: billboard
- leg: san_angelo_tx_us -> del_rio_tx_us
- at_mi: 146.0
- spoken: Billboard: Val Verde Winery, ahead in Del Rio. Texas's oldest winery, one family since eighteen eighty-three. The driver tours. The bottle buckles up.

### Val Verde Winery (eastbound)
- treatment: billboard
- leg: van_horn_tx_us -> del_rio_tx_us
- at_mi: 297.0
- spoken: Billboard: Val Verde Winery, ahead in Del Rio. Texas's oldest winery, one family since eighteen eighty-three. The driver tours. The bottle buckles up.

## Ysleta Mission, El Paso (Mission Trail, Zaragoza Road)

131 South Zaragoza Road in Ysleta del Sur Pueblo; built by the Tigua in 1682, the oldest continuously operated parish in Texas (Wikipedia, Ysleta Mission; elpasomissions.org). The I-10 legs pass about two miles north; the Las Cruces to Midland leg runs the border highway, under a mile away.

### Ysleta Mission (eastbound)
- treatment: billboard
- leg: el_paso_tx_us -> van_horn_tx_us
- at_mi: 6.0
- spoken: Billboard: Ysleta Mission, ahead on the Mission Trail. Founded in sixteen eighty-two, the oldest active parish in Texas. It was here before Texas was.

### Ysleta Mission (westbound)
- treatment: billboard
- leg: van_horn_tx_us -> el_paso_tx_us
- at_mi: 99.0
- spoken: Billboard: Ysleta Mission, ahead on the Mission Trail. Founded in sixteen eighty-two, the oldest active parish in Texas. It was here before Texas was.

### Ysleta Mission (eastbound)
- treatment: billboard
- leg: las_cruces_nm_us -> midland_tx_us
- at_mi: 50.5
- spoken: Billboard: Ysleta Mission, ahead on the Mission Trail. Founded in sixteen eighty-two, the oldest active parish in Texas. It was here before Texas was.

### Ysleta Mission (westbound)
- treatment: billboard
- leg: midland_tx_us -> las_cruces_nm_us
- at_mi: 283.0
- spoken: Billboard: Ysleta Mission, ahead on the Mission Trail. Founded in sixteen eighty-two, the oldest active parish in Texas. It was here before Texas was.

## Franklin Mountains State Park, El Paso (Transmountain Road, I-10 Exit 6 and US 54)

24,247 acres, 37 square miles, all inside the El Paso city limits; Transmountain Road (Loop 375) crosses it from I-10 Exit 6 to US 54 (Wikipedia; tpwd.texas.gov history). Inbound from New Mexico the Vinton and Canutillo callouts sit three miles apart between Exits 2 and 6, too close for a sign between them, so those signs stand just inside Texas at the welcome center and read "ahead".

### Franklin Mountains (eastbound)
- treatment: billboard
- leg: las_cruces_nm_us -> el_paso_tx_us
- at_mi: 25.9
- spoken: Billboard: Franklin Mountains State Park, ahead off Transmountain Road. Thirty-seven square miles of mountains, all inside the El Paso city limits. That is quite a backyard.

### Franklin Mountains (eastbound)
- treatment: billboard
- leg: las_cruces_nm_us -> midland_tx_us
- at_mi: 26.1
- spoken: Billboard: Franklin Mountains State Park, ahead off Transmountain Road. Thirty-seven square miles of mountains, all inside the El Paso city limits. That is quite a backyard.

### Franklin Mountains (southbound)
- treatment: billboard
- leg: albuquerque_nm_us -> el_paso_tx_us
- at_mi: 246.8
- spoken: Billboard: Franklin Mountains State Park, ahead off Transmountain Road. Thirty-seven square miles of mountains, all inside the El Paso city limits. That is quite a backyard.

### Franklin Mountains (eastbound)
- treatment: billboard
- leg: tucson_az_us -> el_paso_tx_us
- at_mi: 297.8
- spoken: Billboard: Franklin Mountains State Park, ahead off Transmountain Road. Thirty-seven square miles of mountains, all inside the El Paso city limits. That is quite a backyard.

### Franklin Mountains (westbound)
- treatment: billboard
- leg: el_paso_tx_us -> las_cruces_nm_us
- at_mi: 11.0
- spoken: Billboard: Franklin Mountains State Park, ahead off Transmountain Road. Thirty-seven square miles of mountains, all inside the El Paso city limits. That is quite a backyard.

### Franklin Mountains (westbound)
- treatment: billboard
- leg: midland_tx_us -> las_cruces_nm_us
- at_mi: 315.8
- spoken: Billboard: Franklin Mountains State Park, ahead off Transmountain Road. Thirty-seven square miles of mountains, all inside the El Paso city limits. That is quite a backyard.

### Franklin Mountains (northbound)
- treatment: billboard
- leg: el_paso_tx_us -> albuquerque_nm_us
- at_mi: 11.0
- spoken: Billboard: Franklin Mountains State Park, ahead off Transmountain Road. Thirty-seven square miles of mountains, all inside the El Paso city limits. That is quite a backyard.

### Franklin Mountains (westbound)
- treatment: billboard
- leg: el_paso_tx_us -> tucson_az_us
- at_mi: 11.0
- spoken: Billboard: Franklin Mountains State Park, ahead off Transmountain Road. Thirty-seven square miles of mountains, all inside the El Paso city limits. That is quite a backyard.

### Franklin Mountains (southbound)
- treatment: billboard
- leg: alamogordo_nm_us -> el_paso_tx_us
- at_mi: 71.5
- spoken: Billboard: Franklin Mountains State Park, ahead off Transmountain Road. Thirty-seven square miles of mountains, all inside the El Paso city limits. That is quite a backyard.

### Franklin Mountains (northbound)
- treatment: billboard
- leg: el_paso_tx_us -> alamogordo_nm_us
- at_mi: 6.0
- spoken: Billboard: Franklin Mountains State Park, ahead off Transmountain Road. Thirty-seven square miles of mountains, all inside the El Paso city limits. That is quite a backyard.

## Fort Concho National Historic Landmark, San Angelo (city node)

630 South Oakes Street; the army post founded 1867, home to all four Buffalo Soldier regiments at times, twenty-three original and restored buildings; open daily (fortconcho.com; National Trust). Signs on the six legs into San Angelo.

### Fort Concho (from Brownwood)
- treatment: billboard
- leg: brownwood_tx_us -> san_angelo_tx_us
- at_mi: 88.0
- spoken: Billboard: Fort Concho, ahead in San Angelo. A frontier army post from eighteen sixty-seven, twenty-three buildings still standing. The army moved out. The fort stayed.

### Fort Concho (from Abilene)
- treatment: billboard
- leg: abilene_tx_us -> san_angelo_tx_us
- at_mi: 81.0
- spoken: Billboard: Fort Concho, ahead in San Angelo. A frontier army post from eighteen sixty-seven, twenty-three buildings still standing. The army moved out. The fort stayed.

### Fort Concho (from Del Rio)
- treatment: billboard
- leg: del_rio_tx_us -> san_angelo_tx_us
- at_mi: 148.5
- spoken: Billboard: Fort Concho, ahead in San Angelo. A frontier army post from eighteen sixty-seven, twenty-three buildings still standing. The army moved out. The fort stayed.

### Fort Concho (from Fort Stockton)
- treatment: billboard
- leg: fort_stockton_tx_us -> san_angelo_tx_us
- at_mi: 155.5
- spoken: Billboard: Fort Concho, ahead in San Angelo. A frontier army post from eighteen sixty-seven, twenty-three buildings still standing. The army moved out. The fort stayed.

### Fort Concho (from Junction)
- treatment: billboard
- leg: junction_tx_us -> san_angelo_tx_us
- at_mi: 89.0
- spoken: Billboard: Fort Concho, ahead in San Angelo. A frontier army post from eighteen sixty-seven, twenty-three buildings still standing. The army moved out. The fort stayed.

### Fort Concho (from Midland)
- treatment: billboard
- leg: midland_tx_us -> san_angelo_tx_us
- at_mi: 104.0
- spoken: Billboard: Fort Concho, ahead in San Angelo. A frontier army post from eighteen sixty-seven, twenty-three buildings still standing. The army moved out. The fort stayed.

## Caverns of Sonora (I-10 Exit 392, then south)

Open daily except Christmas, guided tours, camping, a gift shop with homemade fudge (cavernsofsonora.com; Texas Highways). Exit 392 is not in the leg's interchange list (the Sutton County rest area at mile 394 is), so both signs name the exit and stand about eight miles out.

### Caverns of Sonora (westbound)
- treatment: billboard
- leg: junction_tx_us -> ozona_tx_us
- at_mi: 57.5
- spoken: Billboard: The Caverns of Sonora, ahead at exit three ninety-two. A cave so packed with crystal it looks frosted. The gift shop fudge is homemade.

### Caverns of Sonora (eastbound)
- treatment: billboard
- leg: ozona_tx_us -> junction_tx_us
- at_mi: 18.5
- spoken: Billboard: The Caverns of Sonora, ahead at exit three ninety-two. A cave so packed with crystal it looks frosted. The gift shop fudge is homemade.

## Six Flags Fiesta Texas, San Antonio (I-10 Exit 556)

17000 I-10 West; opened March 1992 inside a limestone quarry worked from 1934 to 1988, its walls kept as the backdrop (Mineral Education Coalition, Beckmann Quarry; blooloop). The legs list Exit 556A as "La Cantera Parkway, Fiesta Texas". Open on a seasonal calendar.

### Six Flags Fiesta Texas (westbound)
- treatment: billboard
- leg: san_antonio_tx_us -> kerrville_tx_us
- at_mi: 13.4
- spoken: Billboard: Six Flags Fiesta Texas, next exit. Roller coasters built against the walls of an old limestone quarry. The rock is gone. The screaming is new.

### Six Flags Fiesta Texas (eastbound)
- treatment: billboard
- leg: kerrville_tx_us -> san_antonio_tx_us
- at_mi: 49.0
- spoken: Billboard: Six Flags Fiesta Texas, next exit. Roller coasters built against the walls of an old limestone quarry. The rock is gone. The screaming is new.

## Cascade Caverns, Boerne (I-10 Exit 543)

226 Cascade Caverns Road, about three miles from Exit 543; opened to the public by 1932, the tour ends where a waterfall crashes into a lake in the Cathedral Room; tours hourly, seven days (cascadecaverns.com; Texas Speleological Survey). The legs list Exit 543 as "Scenic Loop Road, Cascade Caverns Road".

### Cascade Caverns (westbound)
- treatment: billboard
- leg: san_antonio_tx_us -> kerrville_tx_us
- at_mi: 26.4
- spoken: Billboard: Cascade Caverns, next exit. A cave open to visitors since nineteen thirty-two, with a waterfall pouring down inside. The only rain you will want today.

### Cascade Caverns (eastbound)
- treatment: billboard
- leg: kerrville_tx_us -> san_antonio_tx_us
- at_mi: 36.2
- spoken: Billboard: Cascade Caverns, next exit. A cave open to visitors since nineteen thirty-two, with a waterfall pouring down inside. The only rain you will want today.

## Stonehenge II, Ingram (TX 27, five miles west of Kerrville)

Al Shepperd's concrete Stonehenge, begun with a leftover slab of limestone from his neighbor Doug Hill, with two Easter Island heads; moved to the Hill Country Arts Foundation, 120 Point Theatre Road South, in 2010; free, daylight hours (Wikipedia; Roadside America; directions: I-10 into Kerrville, then TX 27 about five miles). Signs on the two I-10 legs into Kerrville.

### Stonehenge Two (westbound)
- treatment: billboard
- leg: san_antonio_tx_us -> kerrville_tx_us
- at_mi: 58.5
- spoken: Billboard: Stonehenge Two, in Ingram, five miles west of Kerrville. It began with a neighbor's leftover slab of limestone. Free, with Easter Island heads thrown in.

### Stonehenge Two (eastbound)
- treatment: billboard
- leg: junction_tx_us -> kerrville_tx_us
- at_mi: 45.0
- spoken: Billboard: Stonehenge Two, in Ingram, five miles west of Kerrville. It began with a neighbor's leftover slab of limestone. Free, with Easter Island heads thrown in.

## Lyndon B. Johnson National Historical Park, Johnson City (US 281)

The boyhood home and visitor center, free, daily 9 to 5, guided home tours (nps.gov/lyjo). The town is named for James Polk Johnson, a cousin of LBJ's father (Wikipedia, Johnson City). Both signs stand in Blanco County, north of the US 281 segment where 391.252 bans billboards. The LBJ Ranch on US 290 already has its own "The LBJ Ranch" landmark, and US 290 takes no billboards.

### LBJ Boyhood Home (northbound)
- treatment: billboard
- leg: san_antonio_tx_us -> marble_falls_tx_us
- at_mi: 58.0
- spoken: Billboard: Lyndon Johnson's boyhood home, ahead in Johnson City, free to tour. The town carries his family's name. Most presidents have to wait for an airport.

### LBJ Boyhood Home (southbound)
- treatment: billboard
- leg: marble_falls_tx_us -> san_antonio_tx_us
- at_mi: 16.0
- spoken: Billboard: Lyndon Johnson's boyhood home, ahead in Johnson City, free to tour. The town carries his family's name. Most presidents have to wait for an airport.

## Billy the Kid Museum, Hico (US 281, city callout)

114 North Pecan Street, opened 1987, telling the claim of Brushy Bill Roberts, who said he was Billy the Kid and had not been shot in 1881; donations, Monday to Saturday plus Sunday afternoon (Roadside America; Texas Highways, Billy the Kid Mystery Solved?). Signs stand before the leg's Hico village callout.

### Billy the Kid Museum (northbound)
- treatment: billboard
- leg: lampasas_tx_us -> stephenville_tx_us
- at_mi: 58.5
- spoken: Billboard: The Billy the Kid Museum, ahead in Hico. An old man here swore he was the Kid and never got shot. Hico believed him.

### Billy the Kid Museum (southbound)
- treatment: billboard
- leg: stephenville_tx_us -> lampasas_tx_us
- at_mi: 13.0
- spoken: Billboard: The Billy the Kid Museum, ahead in Hico. An old man here swore he was the Kid and never got shot. Hico believed him.

## Famous Mineral Water Company, Mineral Wells (city node)

209 NW Sixth Street, bottling Crazy Water since 1904, store open Tuesday to Saturday (texastimetravel; Roadside America tip 20500). The Baker Hotel is still under restoration (2027 to 2028) and is not signed.

### Famous Mineral Water Company (northbound)
- treatment: billboard
- leg: stephenville_tx_us -> mineral_wells_tx_us
- at_mi: 34.0
- spoken: Billboard: The Famous Mineral Water Company, ahead in Mineral Wells. Bottling the town's own water since nineteen oh four. With that name, it had to.

### Famous Mineral Water Company (southbound)
- treatment: billboard
- leg: jacksboro_tx_us -> mineral_wells_tx_us
- at_mi: 23.0
- spoken: Billboard: The Famous Mineral Water Company, ahead in Mineral Wells. Bottling the town's own water since nineteen oh four. With that name, it had to.

## Old Rip, Eastland County Courthouse (I-20 Exit 340)

The horned lizard sealed in the 1897 courthouse cornerstone and found alive when it was opened in February 1928; he toured the country, met President Coolidge, and lies in a glass-topped casket in the courthouse lobby (Roadside America; Texas Association of Counties, County magazine, spring 2026). Each sign stands before the exit and clear of the leg's courthouse museum callout.

### Old Rip (eastbound)
- treatment: billboard
- leg: abilene_tx_us -> fort_worth_tx_us
- at_mi: 52.5
- spoken: Billboard: Old Rip, next exit in Eastland. A horned toad sealed in the courthouse cornerstone for thirty-one years came out alive. Your rest break is shorter.

### Old Rip (westbound)
- treatment: billboard
- leg: fort_worth_tx_us -> abilene_tx_us
- at_mi: 92.0
- spoken: Billboard: Old Rip, next exit in Eastland. A horned toad sealed in the courthouse cornerstone for thirty-one years came out alive. Your rest break is shorter.

## Mobley Hotel, Cisco (I-20 Exits 330 and 332)

The first hotel Conrad Hilton bought, in 1919; its forty beds were rented in eight-hour shifts to oil boom workers; now the Conrad Hilton Center, museum and chamber office, closed Sundays (American Oil and Gas Historical Society; Austin Chronicle, 2023).

### Mobley Hotel (eastbound)
- treatment: billboard
- leg: abilene_tx_us -> fort_worth_tx_us
- at_mi: 42.3
- spoken: Billboard: The Mobley Hotel, next exit in Cisco, the first hotel Conrad Hilton bought. Its beds rented in eight-hour shifts. The pillows never got cold.

### Mobley Hotel (westbound)
- treatment: billboard
- leg: fort_worth_tx_us -> abilene_tx_us
- at_mi: 102.5
- spoken: Billboard: The Mobley Hotel, next exit in Cisco, the first hotel Conrad Hilton bought. Its beds rented in eight-hour shifts. The pillows never got cold.

## Thurber ghost town and W.K. Gordon Center (I-20 Exit 367)

The coal and brick company town; its paving bricks still surface Camp Bowie Boulevard in Fort Worth (Fort Worth Magazine; Texas Historical Commission). Tarleton State's Gordon Center museum stands at the smokestack, Tuesday to Sunday (tarleton.edu/gordoncenter).

### Thurber (eastbound)
- treatment: billboard
- leg: abilene_tx_us -> fort_worth_tx_us
- at_mi: 79.0
- spoken: Billboard: Thurber ghost town, next exit, with a museum by the old smokestack. Its bricks still pave streets in Fort Worth. The bricks outlasted the town.

### Thurber (westbound)
- treatment: billboard
- leg: fort_worth_tx_us -> abilene_tx_us
- at_mi: 68.5
- spoken: Billboard: Thurber ghost town, next exit, with a museum by the old smokestack. Its bricks still pave streets in Fort Worth. The bricks outlasted the town.

## The World's Littlest Skyscraper, Wichita Falls (city node) -- added directions

The Newby-McMahon Building, 701 La Salle, four stories built in 1919, standing and home to an antique shop (Wikipedia). Signed today only on the Dallas leg in. These add every other leg into or through Wichita Falls, with the existing copy word for word. The city's rebuilt waterfall is off until about 2028 and is not signed.

### The World's Littlest Skyscraper (from Altus)
- treatment: billboard
- leg: altus_ok_us -> wichita_falls_tx_us
- at_mi: 80.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (from Lawton)
- treatment: billboard
- leg: lawton_ok_us -> wichita_falls_tx_us
- at_mi: 45.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (from Abilene)
- treatment: billboard
- leg: abilene_tx_us -> wichita_falls_tx_us
- at_mi: 145.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (eastbound)
- treatment: billboard
- leg: amarillo_tx_us -> dallas_tx_us
- at_mi: 220.5
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (westbound)
- treatment: billboard
- leg: dallas_tx_us -> amarillo_tx_us
- at_mi: 131.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (westbound)
- treatment: billboard
- leg: dallas_tx_us -> albuquerque_nm_us
- at_mi: 131.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (eastbound)
- treatment: billboard
- leg: albuquerque_nm_us -> dallas_tx_us
- at_mi: 504.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (from Jacksboro)
- treatment: billboard
- leg: jacksboro_tx_us -> wichita_falls_tx_us
- at_mi: 51.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (from Fort Worth)
- treatment: billboard
- leg: fort_worth_tx_us -> wichita_falls_tx_us
- at_mi: 107.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (from McKinney)
- treatment: billboard
- leg: mckinney_tx_us -> wichita_falls_tx_us
- at_mi: 125.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (from Oklahoma City)
- treatment: billboard
- leg: oklahoma_city_ok_us -> wichita_falls_tx_us
- at_mi: 129.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

### The World's Littlest Skyscraper (from Vernon)
- treatment: billboard
- leg: vernon_tx_us -> wichita_falls_tx_us
- at_mi: 47.0
- spoken: Billboard: Wichita Falls is home to the World's Littlest Skyscraper, a four-story swindle. A con man sold shares in a tower, built it four stories tall instead of four hundred feet, and pocketed the difference.

## Republic of the Rio Grande Museum, Laredo (city node)

1005 Zaragoza Street on San Agustin Plaza, Tuesday to Saturday; Laredo was capital of the Republic of the Rio Grande (January to November 1840) and is the one Texas city with seven flags instead of six (webbheritage.org; National Park Service). Signs on the four legs into Laredo; the I-35 one stands eight miles out, inside the Laredo city edge.

### Republic of the Rio Grande Museum (from Brownsville)
- treatment: billboard
- leg: brownsville_tx_us -> laredo_tx_us
- at_mi: 197.0
- spoken: Billboard: The Republic of the Rio Grande Museum, ahead in Laredo. Texas flew six flags. Laredo flew seven, counting a republic that lasted under a year.

### Republic of the Rio Grande Museum (from Corpus Christi)
- treatment: billboard
- leg: corpus_christi_tx_us -> laredo_tx_us
- at_mi: 136.0
- spoken: Billboard: The Republic of the Rio Grande Museum, ahead in Laredo. Texas flew six flags. Laredo flew seven, counting a republic that lasted under a year.

### Republic of the Rio Grande Museum (from McAllen)
- treatment: billboard
- leg: mcallen_tx_us -> laredo_tx_us
- at_mi: 136.5
- spoken: Billboard: The Republic of the Rio Grande Museum, ahead in Laredo. Texas flew six flags. Laredo flew seven, counting a republic that lasted under a year.

### Republic of the Rio Grande Museum (from San Antonio)
- treatment: billboard
- leg: san_antonio_tx_us -> laredo_tx_us
- at_mi: 147.5
- spoken: Billboard: The Republic of the Rio Grande Museum, ahead in Laredo. Texas flew six flags. Laredo flew seven, counting a republic that lasted under a year.

## Roma Historic District (US 83)

The National Historic Landmark river town where Elia Kazan filmed Viva Zapata! with Marlon Brando in 1952; the World Birding Center at Roma Bluffs occupies two restored buildings, free, dawn to dusk (Cine Sol, Valleywood Dreams; Texas Highways). Signs stand before the leg's Roma village callout.

### Historic Roma (westbound)
- treatment: billboard
- leg: brownsville_tx_us -> laredo_tx_us
- at_mi: 105.0
- spoken: Billboard: Historic Roma, ahead. Marlon Brando filmed Viva Zapata on its old plaza in nineteen fifty-two. The plaza still looks ready for its close-up.

### Historic Roma (westbound)
- treatment: billboard
- leg: mcallen_tx_us -> laredo_tx_us
- at_mi: 46.0
- spoken: Billboard: Historic Roma, ahead. Marlon Brando filmed Viva Zapata on its old plaza in nineteen fifty-two. The plaza still looks ready for its close-up.

### Historic Roma (eastbound)
- treatment: billboard
- leg: laredo_tx_us -> brownsville_tx_us
- at_mi: 83.0
- spoken: Billboard: Historic Roma, ahead. Marlon Brando filmed Viva Zapata on its old plaza in nineteen fifty-two. The plaza still looks ready for its close-up.

### Historic Roma (eastbound)
- treatment: billboard
- leg: laredo_tx_us -> mcallen_tx_us
- at_mi: 82.5
- spoken: Billboard: Historic Roma, ahead. Marlon Brando filmed Viva Zapata on its old plaza in nineteen fifty-two. The plaza still looks ready for its close-up.

## Quinta Mazatlan, McAllen (World Birding Center)

600 Sunset Drive: a 1935 adobe mansion, one of the largest adobe buildings in Texas, now the McAllen wing of the World Birding Center; Tuesday to Saturday (Texas Highways; McAllen city, 2026). The I-2 corridor is a string of village callouts, so each sign sits in the first gap of 2.2 miles or more before the city. The Corpus Christi leg's sign is on US 281 near Edinburg, well south of SH 186, where the 391.252 ban ends.

### Quinta Mazatlan (westbound)
- treatment: billboard
- leg: brownsville_tx_us -> mcallen_tx_us
- at_mi: 50.6
- spoken: Billboard: Quinta Mazatlan, ahead in McAllen. A nineteen thirty-five adobe mansion, now a bird sanctuary. Its birds make their own long hauls every spring and fall.

### Quinta Mazatlan (westbound)
- treatment: billboard
- leg: brownsville_tx_us -> laredo_tx_us
- at_mi: 57.0
- spoken: Billboard: Quinta Mazatlan, ahead in McAllen. A nineteen thirty-five adobe mansion, now a bird sanctuary. Its birds make their own long hauls every spring and fall.

### Quinta Mazatlan (eastbound)
- treatment: billboard
- leg: laredo_tx_us -> brownsville_tx_us
- at_mi: 142.0
- spoken: Billboard: Quinta Mazatlan, ahead in McAllen. A nineteen thirty-five adobe mansion, now a bird sanctuary. Its birds make their own long hauls every spring and fall.

### Quinta Mazatlan (eastbound)
- treatment: billboard
- leg: laredo_tx_us -> mcallen_tx_us
- at_mi: 141.0
- spoken: Billboard: Quinta Mazatlan, ahead in McAllen. A nineteen thirty-five adobe mansion, now a bird sanctuary. Its birds make their own long hauls every spring and fall.

### Quinta Mazatlan (southbound)
- treatment: billboard
- leg: corpus_christi_tx_us -> mcallen_tx_us
- at_mi: 151.0
- spoken: Billboard: Quinta Mazatlan, ahead in McAllen. A nineteen thirty-five adobe mansion, now a bird sanctuary. Its birds make their own long hauls every spring and fall.

## Iwo Jima Monument, Harlingen (Marine Military Academy)

Felix de Weldon's full-size molding-plaster working model, from which the Marine Corps War Memorial bronze at Arlington was cast; given to the academy in 1981 and dedicated in 1982. Flag raiser Harlon Block grew up in Weslaco and is buried at the monument. The monument is open; its museum is closed for a new building until spring 2028 (mma-tx.org). It stands on the east side of Harlingen near the airport, three to four miles off I-2.

### Iwo Jima Monument (northbound)
- treatment: billboard
- leg: brownsville_tx_us -> corpus_christi_tx_us
- at_mi: 23.5
- spoken: Billboard: The Iwo Jima Monument, ahead in Harlingen. The full-size original the Arlington bronze was cast from. Flag raiser Harlon Block grew up nearby in Weslaco.

### Iwo Jima Monument (northbound)
- treatment: billboard
- leg: brownsville_tx_us -> laredo_tx_us
- at_mi: 23.5
- spoken: Billboard: The Iwo Jima Monument, ahead in Harlingen. The full-size original the Arlington bronze was cast from. Flag raiser Harlon Block grew up nearby in Weslaco.

### Iwo Jima Monument (northbound)
- treatment: billboard
- leg: brownsville_tx_us -> mcallen_tx_us
- at_mi: 23.5
- spoken: Billboard: The Iwo Jima Monument, ahead in Harlingen. The full-size original the Arlington bronze was cast from. Flag raiser Harlon Block grew up nearby in Weslaco.

### Iwo Jima Monument (southbound)
- treatment: billboard
- leg: corpus_christi_tx_us -> brownsville_tx_us
- at_mi: 126.0
- spoken: Billboard: The Iwo Jima Monument, ahead in Harlingen. The full-size original the Arlington bronze was cast from. Flag raiser Harlon Block grew up nearby in Weslaco.

### Iwo Jima Monument (eastbound)
- treatment: billboard
- leg: laredo_tx_us -> brownsville_tx_us
- at_mi: 169.0
- spoken: Billboard: The Iwo Jima Monument, ahead in Harlingen. The full-size original the Arlington bronze was cast from. Flag raiser Harlon Block grew up nearby in Weslaco.

### Iwo Jima Monument (eastbound)
- treatment: billboard
- leg: mcallen_tx_us -> brownsville_tx_us
- at_mi: 23.0
- spoken: Billboard: The Iwo Jima Monument, ahead in Harlingen. The full-size original the Arlington bronze was cast from. Flag raiser Harlon Block grew up nearby in Weslaco.

## Freddy Fender Museum, San Benito

On East Heywood Street in San Benito, near the Cultural Heritage Museum and the Texas Conjunto Music Hall of Fame; reopened June 13, 2026 with an expanded permanent exhibit. Born Baldemar Huerta in San Benito, he took the name Fender from the guitar (KRGV; Tejano Nation, April 2026; Texas Public Radio). Signs stand before the leg's San Benito village callout.

### Freddy Fender Museum (northbound)
- treatment: billboard
- leg: brownsville_tx_us -> corpus_christi_tx_us
- at_mi: 15.0
- spoken: Billboard: The Freddy Fender Museum, ahead in San Benito. Born Baldemar Huerta, he took his last name off a guitar. It never asked for it back.

### Freddy Fender Museum (northbound)
- treatment: billboard
- leg: brownsville_tx_us -> laredo_tx_us
- at_mi: 15.0
- spoken: Billboard: The Freddy Fender Museum, ahead in San Benito. Born Baldemar Huerta, he took his last name off a guitar. It never asked for it back.

### Freddy Fender Museum (northbound)
- treatment: billboard
- leg: brownsville_tx_us -> mcallen_tx_us
- at_mi: 15.0
- spoken: Billboard: The Freddy Fender Museum, ahead in San Benito. Born Baldemar Huerta, he took his last name off a guitar. It never asked for it back.

### Freddy Fender Museum (southbound)
- treatment: billboard
- leg: corpus_christi_tx_us -> brownsville_tx_us
- at_mi: 137.0
- spoken: Billboard: The Freddy Fender Museum, ahead in San Benito. Born Baldemar Huerta, he took his last name off a guitar. It never asked for it back.

### Freddy Fender Museum (eastbound)
- treatment: billboard
- leg: laredo_tx_us -> brownsville_tx_us
- at_mi: 181.0
- spoken: Billboard: The Freddy Fender Museum, ahead in San Benito. Born Baldemar Huerta, he took his last name off a guitar. It never asked for it back.

### Freddy Fender Museum (eastbound)
- treatment: billboard
- leg: mcallen_tx_us -> brownsville_tx_us
- at_mi: 36.0
- spoken: Billboard: The Freddy Fender Museum, ahead in San Benito. Born Baldemar Huerta, he took his last name off a guitar. It never asked for it back.

## South Padre Island, by SH 100 (I-69E at Russelltown)

SH 100 runs 24 miles from I-69E at Russelltown through Los Fresnos to Port Isabel and the Queen Isabella Causeway, the only road to the island; the Port Isabel Lighthouse is at the causeway (Wikipedia, Texas State Highway 100). Signed southbound only: northbound out of Brownsville the island road is SH 48, not this one.

### South Padre Island (southbound)
- treatment: billboard
- leg: corpus_christi_tx_us -> brownsville_tx_us
- at_mi: 145.5
- spoken: Billboard: South Padre Island, ahead on Highway one hundred, about twenty-five miles east. Beaches, a lighthouse, and a long bridge to the sand. Trailers stay ashore.

### South Padre Island (eastbound)
- treatment: billboard
- leg: laredo_tx_us -> brownsville_tx_us
- at_mi: 189.3
- spoken: Billboard: South Padre Island, ahead on Highway one hundred, about twenty-five miles east. Beaches, a lighthouse, and a long bridge to the sand. Trailers stay ashore.

### South Padre Island (eastbound)
- treatment: billboard
- leg: mcallen_tx_us -> brownsville_tx_us
- at_mi: 44.2
- spoken: Billboard: South Padre Island, ahead on Highway one hundred, about twenty-five miles east. Beaches, a lighthouse, and a long bridge to the sand. Trailers stay ashore.

## Gladys Porter Zoo, Brownsville (city node)

Opened September 3, 1971, given to the city by the Earl C. Sams Foundation; about 1,600 animals including gorillas, tigers and Komodo dragons; open daily (gpz.org; KRIS). Signs on the three legs into Brownsville.

### Gladys Porter Zoo (southbound)
- treatment: billboard
- leg: corpus_christi_tx_us -> brownsville_tx_us
- at_mi: 154.0
- spoken: Billboard: The Gladys Porter Zoo, ahead in Brownsville. Gorillas, tigers and Komodo dragons at the very bottom of Texas. Most came farther than you did.

### Gladys Porter Zoo (eastbound)
- treatment: billboard
- leg: laredo_tx_us -> brownsville_tx_us
- at_mi: 199.0
- spoken: Billboard: The Gladys Porter Zoo, ahead in Brownsville. Gorillas, tigers and Komodo dragons at the very bottom of Texas. Most came farther than you did.

### Gladys Porter Zoo (eastbound)
- treatment: billboard
- leg: mcallen_tx_us -> brownsville_tx_us
- at_mi: 54.0
- spoken: Billboard: The Gladys Porter Zoo, ahead in Brownsville. Gorillas, tigers and Komodo dragons at the very bottom of Texas. Most came farther than you did.

## Notes for the owner

46 attractions, 177 signs. A dry run of `tools/bake_billboards.py`
on this sheet resolves every leg and bakes all 177 (no `--write`). A
spacing check against the current legs, using the bake tool's own parsing and
mirroring, finds no callout heard in the same direction within 2.2 miles of
any sign, and no two signs on this sheet that close. Every new line is spelled
out, no digits, 23 to 26 words. The four reused lines (Cadillac Ranch, Big
Texan, Littlest Skyscraper, Law West of the Pecos) are longer, 29 to 39 words,
because they are copied word for word.

**Billboard law.**

- Texas Highway Beautification Act, Transportation Code chapter 391, rules at
  43 TAC chapter 21, subchapter I: commercial signs along interstates and
  federal-aid primary highways need a TxDOT permit and must stand in a zoned
  or unzoned commercial or industrial area, at least 1,500 feet apart on
  freeways (Justia, 43 TAC 21). The federal act also allows directional signs
  for natural wonders and scenic and historical attractions, which covers
  most of this sheet.
- Transportation Code 391.252 bans new commercial signs visible from a fixed
  list of roads, and SB 941 (2021) made those roads the State Scenic Byways
  (texas.public.law, section 391.252; Senate Research Center bill analysis of
  SB 941). The ones in this region: US 290 from Austin to Fredericksburg; SH
  16 from Kerrville to I-20; US 281 from the Comal County line to SH 306, and
  from SH 186 to I-37 (except Three Rivers); US 77 from SH 186 at Raymondville
  to SH 44 at Robstown; US 90 from San Antonio to Hondo; SH 17, SH 67, SH 118
  and FM 170 in the Big Bend; every state highway in Bandera County.
- No sign on this sheet stands on any of those roads. That rules out the
  whole Austin to Kerrville leg west of Austin, US 77 through Kingsville, US
  281 north of Edinburg, and US 90 through Castroville. The Valley signs on US
  77 are all south of Raymondville; the McAllen sign on US 281 is near
  Edinburg, about thirty miles south of SH 186; the Johnson City signs are in
  Blanco County, north of the Comal County segment.

**Attractions: sources, status, anything unsure.**

- **Cadillac Ranch, Big Texan, Littlest Skyscraper, Law West of the Pecos.**
  Existing copy reused word for word, on legs and directions that had none.
  Big Texan: open daily, Exit 75 (bigtexan.com; Roadside America tip 2805);
  its eastbound departures from Amarillo are left out, because it stands four
  to seven miles from the Amarillo stop. Littlest Skyscraper: standing, an
  antique shop inside (Wikipedia, Newby-McMahon Building). Langtry: only the
  westbound US 90 sign fits the "Beyond Del Rio" wording; eastbound from Van
  Horn has no Langtry sign unless you want new copy for that direction.
- **Route 66 Midpoint, Adrian.** Wikipedia, Midpoint Cafe and Adrian, Texas
  (1139 miles each way); NewsChannel 10, July 2025 (cafe open). Seasonal: the
  cafe is open March to October; the Midpoint sign stands year round. The
  cafe's own slogan is not echoed.
- **Cross of Our Lord Jesus Christ, Groom.** Wikipedia, Groom, Texas;
  route66news. The joke is about the leaning water tower, not the cross.
- **Devil's Rope Museum, McLean.** barbwiremuseum.com; Route 66 News, March
  2026. Seasonal, March to October. Unsure: westbound, McLean's first exit
  (142) is not in the leg's list; the sign is placed about 1.5 miles before
  where Exit 142 falls by the interstate's mileposts.
- **U-Drop Inn, Shamrock.** nps.gov, Tower Station and U-Drop Inn Cafe; Texas
  Highways. Open daily 10 to 4.
- **Goodnight Ranch State Historic Site.** thc.texas.gov/historic-sites/goodnight-ranch.
  Tuesday to Saturday; winter hours shorter. The joke is the town's name.
- **Woody Guthrie Folk Music Center, Pampa.** ABC 7 Amarillo, Panhandle
  Spirit; High Plains Public Radio calendar (events through 2026). The Friday
  jam is a standing weekly event; if it ever stops, the last sentence goes.
- **Palo Duro Canyon State Park.** tpwd.texas.gov (open daily); Wikipedia,
  Texas State Highway 217. "Twelve miles east" rounds SH 217's 13.6 miles from
  Canyon.
- **Ozymandias on the Plains.** Slate/Atlas Obscura 2013; KFYO; High Plains
  Public Radio 2018; OpenStreetMap. A roadside sculpture on private pasture,
  seen from the road. Unsure: no 2026-dated source, but nothing says it was
  removed. The southbound signs stand 4.5 miles from the Amarillo stop, the
  only slot clear of the Catalpa and Coulter Acres callouts.
- **Buddy Holly Center, Lubbock.** visitlubbock.org; Roadside America tip 6824.
- **Frontier Texas!, Abilene.** authentictexas.com; Group Tour Magazine.
  Spoken without the exclamation mark.
- **National WASP WWII Museum, Sweetwater.** waspmuseum.org (2026 hours and
  closures). Read as "WASP," the way the museum says it.
- **Permian Basin Petroleum Museum, Midland.** petroleummuseum.org; Roadside
  America tip 1284 (the Oil Patch and the Chaparral Gallery).
- **Odessa Meteor Crater.** Wikipedia; Roadside America tip 26091. Free, daily.
- **Monahans Sandhills State Park.** tpwd.texas.gov (open daily, disc rental).
- **West of the Pecos Museum.** texastimetravel; Texas Historical Commission atlas.
- **Paisano Pete, Fort Stockton.** Texas Highways; Just a Little Further (2022).
- **Balmorhea State Park.** tpwd.texas.gov; construction through September
  2026 with the pool open; closed a week each spring for pool cleaning.
- **Prada Marfa.** NBC DFW and Texas Monthly (2013 ruling); ballroommarfa.org
  (2014 museum lease). The copy's last line plays on the ruling. Unsure: no
  2026-dated source; it is a permanent installation, vandalized and restored
  more than once.
- **Marfa Lights Viewing Area.** Wikipedia, Marfa lights; visitmarfa.com.
- **Big Bend National Park.** nps.gov, The Darkness That Refreshes; DarkSky.
- **Seminole Canyon State Park.** tpwd.texas.gov tour calendar. Guided walks
  Wednesday to Sunday only.
- **Val Verde Winery, Del Rio.** valverdewinery.com; Val Verde County
  Historical Commission. The joke keeps the bottle away from the driver.
- **Ysleta Mission, El Paso.** Wikipedia; elpasomissions.org.
- **Franklin Mountains State Park.** Wikipedia; tpwd.texas.gov. Unsure: the
  Albuquerque to El Paso sign sits at the state line, mile 246.8, a tenth of a
  mile before the leg's first Texas exit; nudging it into Texas would bring
  it inside 2.2 miles of the Vinton callout.
- **Fort Concho, San Angelo.** fortconcho.com hours via the city of San Angelo.
- **Caverns of Sonora.** cavernsofsonora.com; Texas Highways. The copy names
  no single formation; the famous butterfly helictite has been damaged.
- **Six Flags Fiesta Texas.** Mineral Education Coalition; blooloop. Seasonal
  calendar; no 2026 schedule was checked. In San Antonio's city limits but on I-10 west,
  outside the I-35 lane; drop it if the I-35 sheet already has it.
- **Cascade Caverns, Boerne.** cascadecaverns.com (tours hourly, seven days);
  Texas Speleological Survey.
- **Stonehenge II, Ingram.** Wikipedia; Roadside America (directions). Five
  miles off the legs, through Kerrville on TX 27; the copy says so.
- **Lyndon B. Johnson boyhood home, Johnson City.** nps.gov/lyjo (free, daily;
  Texas White House tours suspended for restoration, which the copy does not
  mention); Wikipedia, Johnson City.
- **Billy the Kid Museum, Hico.** Roadside America (hours, donations); Texas
  Highways. Unsure: no 2026-dated source for hours.
- **Famous Mineral Water Company, Mineral Wells.** texastimetravel; Roadside
  America tip 20500. Unsure: hours from an older listing.
- **Old Rip, Eastland.** Roadside America; County magazine, spring 2026.
- **Mobley Hotel, Cisco.** American Oil and Gas Historical Society; Austin
  Chronicle, 2023.
- **Thurber and the W.K. Gordon Center.** tarleton.edu/gordoncenter (2026
  hours); Fort Worth Magazine and Historic Fort Worth (Camp Bowie bricks).
- **Republic of the Rio Grande Museum, Laredo.** webbheritage.org; nps.gov.
  The San Antonio to Laredo sign is on I-35 eight miles out of Laredo; if the
  I-35 sheet signs Laredo too, keep one.
- **Historic Roma.** Cine Sol, Valleywood Dreams; Texas Highways.
- **Quinta Mazatlan, McAllen.** Texas Highways; city of McAllen (2026 hours).
  An expansion is planned; no closure announced.
- **Iwo Jima Monument, Harlingen.** mma-tx.org. The monument is open; the
  museum is closed until spring 2028. The copy has no joke, on purpose.
- **Freddy Fender Museum, San Benito.** KRGV; Tejano Nation, March and April
  2026 (reopened June 13, 2026). No song is named.
- **South Padre Island.** Wikipedia, Texas State Highway 100. The SH 100
  junction at Russelltown is not in the legs' interchange lists; the signs
  stand about a mile before it and name the highway rather than the exit.
- **Gladys Porter Zoo, Brownsville.** gpz.org; KRIS.
- Mileposts on the Amarillo to Dallas and Dallas to Albuquerque legs come
  from route points rather than dense geometry, which those legs do not
  match; signs there are placed by the legs' own exits and callouts.

**Dropped.**

- **Slug Bug Ranch.** Left Conway in 2023; reopened June 2024 at the Big
  Texan RV Ranch, beside the Big Texan (route66news, May 2024). Same stretch;
  the Big Texan signs cover it.
- **Panhandle-Plains Historical Museum, Canyon.** Same exit as Palo Duro
  Canyon; Palo Duro is better known.
- **American Quarter Horse Hall of Fame, Amarillo.** Amarillo already has
  the Big Texan and Cadillac Ranch.
- **National Ranching Heritage Center, American Windpower Center, Silent
  Wings Museum, Lubbock.** Same approaches as the Buddy Holly Center.
- **Buddy Holly Center from Midland.** That leg already ends on a "The Buddy
  Holly Center" museum callout.
- **Wichita Falls waterfall.** Shut off since 2025; repairs run to about 2028
  (Fox 4, October 2025; NewsChannel 6, January 2026).
- **King Ranch, Kingsville.** US 77 there is on the 391.252 list.
- **National Museum of the Pacific War, Luckenbach, LBJ Ranch, Wildseed
  Farms, Enchanted Rock.** US 290 and SH 16 are on the 391.252 list.
- **Castroville and Hondo.** US 90 from San Antonio to Hondo is on the list.
- **Guadalupe Mountains National Park, Hueco Tanks.** No leg on US 62/180.
- **McDonald Observatory, Fort Davis.** About forty miles off US 90, by SH 17
  and SH 118, both on the list.
- **Longhorn Cavern State Park.** About six miles off US 281 by Park Road 4;
  the junction's milepost on a 35-mile leg could not be pinned down.
- **National Butterfly Center, Mission.** Over two miles off, and closed for
  a time in 2022 after threats; Quinta Mazatlan covers McAllen.
- **Palo Alto Battlefield, Santa Ana Refuge, the Hidalgo killer bee.** Three
  or more miles off, on stretches the zoo and Quinta Mazatlan already use.
- **Baker Hotel, Mineral Wells.** Still under restoration.
- **Wyler Aerial Tramway, El Paso.** Closed.
- **Chamizal National Memorial.** El Paso already has Franklin Mountains and
  the Ysleta Mission.
- **Stonehenge replica at UTPB, Odessa.** Weaker than Ingram's, and Odessa
  already has the crater.
- **Museum of the Big Bend, Alpine; Marfa's Chinati Foundation.** Room on US
  90, but weaker than the four US 90 signs here; easy to add.
- **Cave Without a Name, Dinosaur Valley State Park.** No leg within six miles.
- **Natural Bridge Caverns.** I-35 corridor.
- **Uvalde.** Nothing signed there; a joke billboard in Uvalde reads badly
  after 2022.
- **South Padre Island northbound.** From Brownsville the island road is SH
  48, not SH 100.
