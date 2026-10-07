# Review: Mountain West billboard drafts -- 2026-10-01

Drafts for the owner's review; nothing here is baked. Sheets:
`nebraska-2026-10-01.md`, `wyoming-2026-10-01.md`,
`montana-2026-10-01.md`, `utah-2026-10-01.md`, `arizona-2026-10-01.md`,
`new-mexico-2026-10-01.md`, `oklahoma-2026-10-01.md`, and
`mountain-west-reverse-copies-2026-10-01.md`.

## Counts

- Attractions: 92 (Nebraska 10, Wyoming 11, Montana 13, Utah 12, Arizona
  19, New Mexico 13, Oklahoma 14).
- New-copy signs: 450 (Nebraska 46, Wyoming 83, Montana 51, Utah 84,
  Arizona 68, New Mexico 62, Oklahoma 56).
- New lines: 92, one per attraction, listed below.
- Reused-copy signs: 80, older approved copy word for word on the
  directions and sibling legs it missed (Nebraska 17, Montana 8, Utah 9,
  Arizona 18, New Mexico 16, Oklahoma 12). Not listed as new lines.

Every sheet dry-runs clean through `tools/bake_billboards.py` (no
`--write`), and a spacing check across all eight sheets together finds no
sign within 2.2 miles of another callout heard the same way, no name
collision with an existing record, and no digits.

## Decisions

1. **Dallas to St. Louis leg runs the wrong road for its signs.** Its
   geometry goes I-30 to Little Rock and US 67 to St. Louis, but its state
   miles and its Route 66 billboards (Blue Whale, Totem Pole, Galena, Gay
   Parita, Munger Moss, Uranus, Meramec Caverns) assume I-44, so those lines
   are probably heard in Arkansas and the Missouri bootheel. Recommendation:
   re-check that leg's route before baking anything onto it; I added nothing
   to it and put the Whale and Totem Pole copies on the three Tulsa I-44
   legs instead.
2. **Two older Utah signs stand on a scenic byway.** Hole N' the Rock (US
   191 south of Moab) and "Arches and Canyonlands" (US 191 north of Moab)
   are on the Dinosaur Diamond National Scenic Byway, where 23 USC 131(s)
   bars billboards. Recommendation: turn both into landmark callouts, as the
   Keys signs were; I left them as they are.
3. **The placed Winslow sign paraphrases the Eagles lyric** ("a girl in a
   flatbed Ford may slow down to look"). Recommendation: cut that sentence;
   I did not copy it to the other directions, and the Interstate 40 pool's
   Winslow line already covers the corner.
4. **Byway law per state, as drafted.** Recommendation: accept.
   - Nebraska (section 39-218): nothing on US 30 (Lincoln Highway), US 385
     (Gold Rush) or US 26 (Western Trails); I-80 is not a byway.
   - Wyoming (W.S. 24-10) and Montana (MCA 75-15): no byway on these legs.
   - Utah (72-4-303, federal rule): nothing on the Dinosaur Diamond roads
     (US 191 Monticello to Crescent Junction, US 6 and 191 Helper to Green
     River, US 40 east of Duchesne); Provo Canyon's US 189 could not be
     confirmed either way and carries none.
   - Arizona (ADOT scenic and historic roads): no interstate mainline is
     designated; US 89A (Jerome, Oak Creek), US 60 Gila-Pinal, US 93 Joshua
     Forest and AZ 82 Patagonia-Sonoita carry none, and Sedona bans
     off-premise signs.
   - New Mexico: none on I-25 from Raton to Fort Union (Santa Fe Trail) or
     on El Camino Real's three short I-25 stretches (Bernardo to Alamillo,
     Escondida to Socorro, NM 1 to NM 181) or its US 84/285 north of Santa
     Fe; the Route 66 byway is the old road, not I-40. If you would rather
     treat El Camino Real like Colorado's byways, drop the I-25 signs between
     Albuquerque and Las Cruces.
   - Oklahoma (69 O.S. 1271): nothing on US 60 between Ponca City and
     Bartlesville (Osage Nation Heritage Trail); the Route 66 byway is the
     old road and business loops, not the I-40 and I-44 mainlines.
5. **Six plain lines with no joke**, for battle sites, sacred and living
   places: Fort Phil Kearny, Little Bighorn, Devils Tower, Mission San
   Xavier, Acoma Sky City, Sequoyah's Cabin. Recommendation: keep them
   plain.
6. **Big-city attractions are signed on every leg in.** The Old West Museum
   (14 legs into Cheyenne), Golden Spike (20 legs through Brigham City), Hill
   Aerospace (15 through Roy), the Golden Driller (11 into Tulsa), the
   Cowboy Museum (9 into Oklahoma City). Recommendation: keep; a driver only
   hears the one on his road. Trim to the interstate approaches if it reads
   as too many.
7. **How the facts were checked.** The session's web-search allowance ran
   out partway through Montana. From there each attraction was checked by
   fetching its own site, the park agency's page or Wikipedia directly; two
   facts rest on long-documented history, not a fetch, and are marked in
   their sheets (the Missouri Headwaters naming, Petrified Forest's
   mailed-back wood). Places whose status could not be confirmed were
   dropped, not guessed. Recommendation: approve on that basis, or name any
   line you want re-checked.

## New lines

### Nebraska

Strategic Air Command and Aerospace Museum

1. Billboard: The Strategic Air Command Museum, next exit. Thirty aircraft indoors, including the Blackbird, the fastest jet ever flown. Parked, it is slower than you.

Henry Doorly Zoo

2. Billboard: The Henry Doorly Zoo, ahead in Omaha, with an indoor rainforest and a desert under a glass dome. Nebraska weather is optional inside.

Stuhr Museum

3. Billboard: The Stuhr Museum, ahead in Grand Island. An eighteen-nineties railroad town of sixty buildings, many moved here. Somebody hauled a lot of oversize loads.

Harold Warp Pioneer Village

4. Billboard: Harold Warp Pioneer Village, next exit, then twelve miles south in Minden. Fifty thousand old things on twenty acres. Nobody here ever threw anything away.

Heartland Museum of Military Vehicles

5. Billboard: The Heartland Museum of Military Vehicles, next exit. About a hundred tanks, jeeps and helicopters, many still running. Every one of them wins a merge.

Robert Henri Museum

6. Billboard: The Robert Henri Museum, next exit in Cozad. The painter grew up here as Robert Cozad, then left town in a hurry under a new name.

Fort Cody Trading Post

7. Billboard: Fort Cody Trading Post, ahead in North Platte, where Buffalo Bill's Wild West Show runs in twenty thousand hand-carved figures. Tiny horses, no cleanup.

Ole's Big Game Steakhouse

8. Billboard: Ole's Big Game Steakhouse, next exit in Paxton. More than two hundred trophy mounts and a polar bear in the bar. He never buys a round.

Front Street, Ogallala

9. Billboard: Front Street, ahead in Ogallala. A rebuilt cattle-trail main street with a cowboy museum and a jail cell. Visit the museum. Skip the cell.

Homestead National Historical Park

10. Billboard: Homestead National Historical Park, ahead at Beatrice, on the first homestead claim, filed ten minutes after midnight on New Year's Day. Some people cannot wait.

### Wyoming

Bear River State Park

11. Billboard: Bear River State Park, ahead in Evanston. A small bison herd and a few bull elk, right by the trail. The elk are bachelors by policy.

Fort Bridger State Historic Site

12. Billboard: Historic Fort Bridger, ahead. Jim Bridger opened a trading post here in eighteen forty-three to supply the wagon trains. Business has slowed since.

Wyoming Frontier Prison

13. Billboard: The Wyoming Frontier Prison, ahead in Rawlins. The penitentiary opened in nineteen oh-one; guided tours take you inside. They also let you out.

Cheyenne Frontier Days Old West Museum

14. Billboard: The Old West Museum, ahead in Cheyenne. The country's largest collection of horse-drawn carriages, a hundred sixty strong. None of them has a turn signal.

Oregon Trail Ruts State Historic Site

15. Billboard: The Oregon Trail Ruts, east of the next exit at Guernsey. Wagon wheels wore them five feet deep into sandstone. Your tires lack ambition.

Douglas, home of the jackalope

16. Billboard: Douglas, ahead, home of the jackalope, the antlered rabbit a local taxidermist dreamed up. Several statues in town. Wild sightings remain unconfirmed.

National Historic Trails Interpretive Center

17. Billboard: The National Historic Trails Interpretive Center, ahead in Casper. Half a million emigrants followed the river through here on the way west. Most of them walked.

The Occidental Hotel

18. Billboard: The Occidental Hotel, ahead in Buffalo. Owen Wister found characters for The Virginian in its lobby. The saloon kept its bullet holes, for the atmosphere.

Fort Phil Kearny State Historic Site

19. Billboard: Fort Phil Kearny State Historic Site, next exit. The Bozeman Trail fort Red Cloud's alliance fought to close. In eighteen sixty-eight, the army left.

King's Saddlery

20. Billboard: King's Saddlery, ahead in Sheridan. Ropes made on site and a museum of nearly six hundred saddles. Your seat has never felt so plain.

Devils Tower National Monument

21. Billboard: Devils Tower, next exit, then about thirty miles north. Proclaimed the nation's first national monument in nineteen oh-six, and sacred to many Plains tribes.

### Montana

Lincoln's 50,000 Silver Dollar Bar

22. Billboard: Lincoln's Fifty Thousand Silver Dollar Bar, next exit in Haugan. The walls hold more than fifty thousand donated dollars. Making change here is frowned upon.

Old Montana Prison

23. Billboard: The Old Montana Prison, next exit in Deer Lodge. It held inmates for over a century and now holds five museums. Friendlier guests now.

World Museum of Mining

24. Billboard: The World Museum of Mining, ahead in Butte, on top of the old Orphan Girl mine. Fifty buildings up here. Nobody counts what is down there.

Missouri Headwaters State Park

25. Billboard: Missouri Headwaters State Park, ahead at Three Forks. Three rivers meet to make the Missouri. Lewis and Clark named all three after their bosses.

Greycliff Prairie Dog Town State Park

26. Billboard: Greycliff Prairie Dog Town State Park, next exit. A whole town of black-tailed prairie dogs beside the interstate. Please do not feed the residents.

Little Bighorn Battlefield National Monument

27. Billboard: Little Bighorn Battlefield National Monument, ahead at Crow Agency. Where the Lakota, Northern Cheyenne and Arapaho defeated Custer's Seventh Cavalry in June of eighteen seventy-six.

Pompeys Pillar National Monument

28. Billboard: Pompeys Pillar, next exit. William Clark carved his name here in eighteen oh-six, the expedition's only trace left on the trail. Do not add yours.

Makoshika State Park

29. Billboard: Makoshika State Park, ahead at Glendive. Eleven thousand acres of badlands, and a triceratops skull in the visitor center. It has waited longer than you.

Bannack State Park

30. Billboard: Bannack State Park, west of the next exit. Montana's first territorial capital, now a ghost town of more than fifty buildings. The government left first.

Giant Springs State Park

31. Billboard: Giant Springs, ahead in Great Falls, feeds the Roe River, once the world's shortest at two hundred feet. Your trailer is a quarter of it.

Glacier National Park

32. Billboard: Glacier National Park, ahead at West Glacier. Going-to-the-Sun Road takes nothing longer than twenty-one feet over Logan Pass. Your rig is not invited.

Kootenai Falls

33. Billboard: Kootenai Falls, ahead between Libby and Troy, the largest undammed falls in Montana, with a swinging bridge below. It swings. That is the point.

Grizzly and Wolf Discovery Center

34. Billboard: The Grizzly and Wolf Discovery Center, ahead in West Yellowstone. Grizzlies and gray wolves that cannot live in the wild. These bears skip hibernation.

### Utah

St. George Dinosaur Discovery Site

35. Billboard: The Dinosaur Discovery Site, ahead in Saint George, where a retired eye doctor found dinosaur tracks in two thousand. Good eyes run in the profession.

Kolob Canyons, Zion National Park

36. Billboard: The Kolob Canyons of Zion National Park, next exit. A five-mile drive into red finger canyons. The crowds all went to the other entrance.

Cove Fort

37. Billboard: Historic Cove Fort, ahead. An eighteen sixty-seven way station of black volcanic rock, halfway between Fillmore and Beaver. Rest areas were sturdier then.

Territorial Statehouse

38. Billboard: The Territorial Statehouse, ahead in Fillmore. Utah's first capitol was built one wing at a time. The first wing was also the last.

Fremont Indian State Park

39. Billboard: Fremont Indian State Park, ahead. The largest known Fremont village turned up when this interstate was built. Road work has rarely been so interesting.

Museum of Ancient Life

40. Billboard: The Museum of Ancient Life, ahead in Lehi, with one of the world's largest collections of mounted dinosaur skeletons. Extinction was never this tidy.

Hill Aerospace Museum

41. Billboard: The Hill Aerospace Museum, ahead at Roy. More than seventy aircraft, biplanes to stealth jets, beside a working air base. The neighbors are louder.

Golden Spike National Historical Park

42. Billboard: Golden Spike National Historical Park, west of Brigham City, where the first transcontinental railroad was joined in eighteen sixty-nine. Even that ran two days late.

Bonneville Salt Flats

43. Billboard: The Bonneville Salt Flats, next exit. A wheel-driven car hit four hundred forty-nine miles an hour out there. Dispatch would still call you late.

Utah Olympic Park

44. Billboard: Utah Olympic Park, next exit. The ski jumps and bobsled track from the two thousand two Winter Games, still in use. Mind your own downhill.

Heber Valley Railroad

45. Billboard: The Heber Valley Railroad, ahead in Heber City. A ninety-minute round trip into Provo Canyon. Locals called it the Heber Creeper, and it never argued.

John Wesley Powell River History Museum

46. Billboard: The John Wesley Powell River History Museum, ahead in Green River. In eighteen sixty-nine, a one-armed major boated these unmapped canyons. Then he mapped them.

### Arizona

Petrified Forest National Park

47. Billboard: Petrified Forest National Park, next exit, with trees turned to stone two hundred twenty-five million years ago. Thieves keep mailing pieces back.

Walnut Canyon National Monument

48. Billboard: Walnut Canyon National Monument, next exit. Twenty-five cliff dwelling rooms down a trail that drops a hundred eighty-five feet. The climb back is included.

Lowell Observatory

49. Billboard: Lowell Observatory, ahead in Flagstaff. Pluto was found here in nineteen thirty. It has since been demoted, and the observatory took it well.

Bearizona

50. Billboard: Bearizona, ahead in Williams. Drive through a pine forest past black bears, wolves and bison. Windows up; the bears have no manners.

Montezuma Castle National Monument

51. Billboard: Montezuma Castle National Monument, ahead near Camp Verde. A five-story cliff dwelling ninety feet up. Montezuma never lived there, and it is not a castle.

Sunset Crater Volcano National Monument

52. Billboard: Sunset Crater Volcano National Monument, ahead. It last erupted around the year ten eighty-five and has been quiet since. Keep it that way.

Cameron Trading Post

53. Billboard: Cameron Trading Post, ahead, trading since nineteen sixteen beside the Little Colorado River gorge. The Navajo taco covers the whole plate.

Horseshoe Bend

54. Billboard: Horseshoe Bend, ahead before Page. A short trail ends a thousand feet above a hairpin loop of the Colorado River. Your hairpin turns are smaller.

Pima Air and Space Museum

55. Billboard: The Pima Air and Space Museum, ahead in Tucson. Nearly four hundred aircraft on eighty acres, beside the Air Force boneyard. Even the planes found parking.

Rooster Cogburn Ostrich Ranch

56. Billboard: Rooster Cogburn Ostrich Ranch, next exit at Picacho Peak. Feed ostriches, goats, deer and even stingrays. The ostriches do not wait their turn.

Kartchner Caverns State Park

57. Billboard: Kartchner Caverns State Park, ahead near Benson. Two cavers found it in nineteen seventy-four and kept it secret for fourteen years. The secret is out.

Rex Allen Arizona Cowboy Museum

58. Billboard: The Rex Allen Arizona Cowboy Museum, ahead in Willcox. He sang, rode Koko through nineteen Westerns, and narrated for Disney. Koko gets a memorial too.

Titan Missile Museum

59. Billboard: The Titan Missile Museum, next exit at Sahuarita. An inert Titan Two stands in its silo, with a hole cut in the nose to prove it.

Mission San Xavier del Bac

60. Billboard: Mission San Xavier del Bac, ahead. Built between seventeen eighty-three and seventeen ninety-seven, the White Dove of the Desert still serves its parish.

Hi Jolly's tomb

61. Billboard: Hi Jolly's tomb, ahead in Quartzsite. A stone pyramid topped with a copper camel, for the Army's camel driver. The Army did try camels.

Yuma Territorial Prison State Historic Park

62. Billboard: Yuma Territorial Prison State Historic Park, ahead. More than three thousand inmates from eighteen seventy-six to nineteen oh-nine. Then the high school moved in.

London Bridge

63. Billboard: London Bridge, ahead in Lake Havasu City, bought in nineteen sixty-eight and rebuilt in Arizona. The buyer swore it was the bridge he wanted.

Tonto Natural Bridge State Park

64. Billboard: Tonto Natural Bridge State Park, ahead, probably the world's largest travertine bridge, a hundred eighty-three feet high. It is rated for hikers only.

Oatman

65. Billboard: Oatman, north of Topock on old Route sixty-six. Wild burros run the main street and expect to be fed. They outrank the cars.

### New Mexico

The Blue Hole

66. Billboard: The Blue Hole, ahead in Santa Rosa. A desert spring over eighty feet deep, sixty-two degrees year round. Divers love it; toes are less sure.

Sandia Peak Tramway

67. Billboard: The Sandia Peak Tramway, ahead. The longest aerial tram in the Americas climbs nearly four thousand feet in fifteen minutes. Pack a jacket.

Acoma Sky City

68. Billboard: Acoma Sky City, ahead, a pueblo atop a mesa three hundred sixty-five feet high, home for centuries. Tours begin at the cultural center.

El Rancho Hotel

69. Billboard: The El Rancho Hotel, ahead in Gallup, built in nineteen thirty-seven for movie crews. Its rooms are named for the stars who stayed.

Meow Wolf

70. Billboard: Meow Wolf, ahead in Santa Fe. A bowling alley became a house with doors to other worlds. A fantasy novelist footed the bill.

Bosque del Apache National Wildlife Refuge

71. Billboard: Bosque del Apache National Wildlife Refuge, ahead at San Antonio. Thousands of sandhill cranes winter here with the snow geese. They are louder than you.

Truth or Consequences

72. Billboard: Truth or Consequences, ahead. In nineteen fifty, Hot Springs renamed itself after a radio quiz show for one broadcast. The name stuck; the show moved on.

Hatch

73. Billboard: Hatch, next exit, the chile capital of the world, by its own count. Its Labor Day festival draws thousands. Mild is a matter of opinion.

Mesilla

74. Billboard: Mesilla, ahead by Las Cruces. The railroad bypassed it in eighteen eighty-one over land prices, which kept the old plaza old. Thank the haggling.

Rockhound State Park

75. Billboard: Rockhound State Park, ahead near Deming, the first park in the country to let you take the rocks home. Your suspension gets a vote.

White Sands National Park

76. Billboard: White Sands National Park, ahead. The largest gypsum dunefield on Earth, and you may sled it. This road closes now and then for missile tests.

New Mexico Museum of Space History

77. Billboard: The New Mexico Museum of Space History, ahead in Alamogordo. Ham, the first chimpanzee in space, is buried on the grounds. He went first.

Carlsbad Caverns National Park

78. Billboard: Carlsbad Caverns National Park, southwest of Carlsbad. The Big Room is the largest cave chamber in North America. Your whole fleet would fit.

### Oklahoma

Stafford Air and Space Museum

79. Billboard: The Stafford Air and Space Museum, ahead in Weatherford. The town's own astronaut flew four missions, one around the Moon. His Gemini capsule retired here.

Oklahoma Route 66 Museum

80. Billboard: The Oklahoma Route sixty-six Museum, ahead in Clinton. It covers Chicago to Santa Monica in a single building. Much quicker than driving it.

Sequoyah's Cabin

81. Billboard: Sequoyah's Cabin, ahead near Sallisaw. Sequoyah lived here from eighteen twenty-nine; he gave the Cherokee their written language. Now a Cherokee Nation museum.

Rock Cafe

82. Billboard: The Rock Cafe, ahead in Stroud, built of leftover Route sixty-six sandstone and open since nineteen thirty-nine. Its owner inspired Sally, the Porsche in Cars.

Will Rogers Memorial Museum

83. Billboard: The Will Rogers Memorial Museum, ahead in Claremore. He never met a man he didn't like, he said. He never met your dispatcher.

Coleman Theatre

84. Billboard: The Coleman Theatre, ahead in Miami, Oklahoma, a nineteen twenty-nine movie palace on Route sixty-six. Its Wurlitzer organ is a year older than the building.

The Golden Driller

85. Billboard: The Golden Driller, ahead in Tulsa, seventy-six feet tall with one hand on a real oil derrick. His belt buckle once said Tesla, briefly.

National Cowboy and Western Heritage Museum

86. Billboard: The National Cowboy and Western Heritage Museum, ahead in Oklahoma City, with twenty-eight thousand pieces of the West and a whole cow town indoors.

Turner Falls Park

87. Billboard: Turner Falls Park, ahead near Davis, a seventy-seven-foot waterfall in the Arbuckle Mountains, and a stone castle a professor built for his summers.

WinStar World Casino

88. Billboard: WinStar World Casino, ahead at Thackerville, the biggest casino floor in the country, one exit before Texas. Leave the trailer keys in the truck.

Wichita Mountains Wildlife Refuge

89. Billboard: Wichita Mountains Wildlife Refuge, ahead near Lawton. The bison herd began with fifteen from the Bronx Zoo in nineteen oh-seven. None of them miss New York.

Woolaroc

90. Billboard: Woolaroc, ahead near Bartlesville, an oilman's ranch with bison and longhorns, and the plane that won the nineteen twenty-seven air race to Hawaii.

Marland Mansion

91. Billboard: The Marland Mansion, ahead in Ponca City. An oilman built fifty-five rooms, lost his company to Wall Street, and moved out. Easy come.

Boise City Bomb Memorial

92. Billboard: Boise City, ahead. In nineteen forty-three a lost bomber crew dropped practice bombs on the town square. Nobody was hurt. The crew skipped the reunion.
