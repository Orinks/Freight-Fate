# Review: Mountain West billboard drafts -- 2026-10-01

Drafts for the owner's review; nothing here is baked. Sheets so far:
`nebraska-2026-10-01.md`, `wyoming-2026-10-01.md`,
`montana-2026-10-01.md`, `utah-2026-10-01.md`, `arizona-2026-10-01.md`,
and `mountain-west-reverse-copies-2026-10-01.md`.

## Counts

- Nebraska: 10 attractions, 46 signs, 10 new lines.
- Wyoming: 11 attractions, 83 signs, 11 new lines.
- Montana: 13 attractions, 51 signs, 13 new lines.
- Utah: 12 attractions, 84 signs, 12 new lines.
- Arizona: 19 attractions, 68 signs, 19 new lines.
- Reused-copy signs (older approved copy, other directions and sibling
  legs): 52, in Nebraska (17), Montana (8), Utah (9) and Arizona (18).
- Total so far: 65 attractions, 332 new-copy signs, 65 new lines, 52
  reused-copy signs.

Every sheet dry-runs clean through `tools/bake_billboards.py` (no
`--write`), and a spacing check across all the sheets together finds no
sign within 2.2 miles of another callout heard the same way.

## Decisions

1. **Nebraska law.** Section 39-218 bars off-premise signs on the nine
   scenic byways. Recommendation: as drafted, nothing on US 30 (Lincoln
   Highway), US 385 (Gold Rush) or US 26 (Western Trails); Interstate 80 is
   not a byway and carries the signs.
2. **Wyoming law.** The outdoor advertising act allows signs beside the
   interstates in commercial and industrial areas, and none of the state's
   scenic byways is on a leg. Recommendation: sign as drafted.
3. **Three plain lines with no joke**, for battle sites and a sacred one:
   Fort Phil Kearny, Little Bighorn and Devils Tower. Recommendation: keep
   them plain.
5. **Montana law.** The Outdoor Advertising Act allows signs beside the
   interstates and primary roads in commercial and industrial areas; the
   state's scenic byways are not on these legs. Recommendation: sign as
   drafted.
6. **How the facts were checked.** The session's web-search allowance ran
   out partway through Montana. From there each attraction was checked by
   fetching its own site, the park agency's page or Wikipedia directly; the
   one fact resting on settled history alone (the Missouri Headwaters
   naming) is marked in its sheet. Recommendation: approve on that basis,
   or name any line you want re-checked.
4. **The Old West Museum is signed on all fourteen legs into Cheyenne.**
   Recommendation: keep; a driver only ever hears the one on the road he is
   on. Trim to the Interstate 25 and 80 approaches if it reads as too many.

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

14. Billboard: The Old West Museum, ahead in Cheyenne. The country's largest collection of horse-drawn carriages, a hundred and sixty strong. Every one turns tighter than you.

Oregon Trail Ruts State Historic Site

15. Billboard: The Oregon Trail Ruts, east of the next exit at Guernsey. Wagon wheels wore them five feet deep into sandstone. Mind your own tread.

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

22. Billboard: Lincoln's Fifty Thousand Silver Dollar Bar, next exit in Haugan. The walls hold more than fifty thousand donated dollars. Please do not ask for change.

Old Montana Prison

23. Billboard: The Old Montana Prison, next exit in Deer Lodge. It held inmates for over a century and now holds five museums. Visitors may leave.

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

61. Billboard: Hi Jolly's tomb, ahead in Quartzsite. A stone pyramid topped with a copper camel, for the Army's camel driver. The Army really tried camels.

Yuma Territorial Prison State Historic Park

62. Billboard: Yuma Territorial Prison State Historic Park, ahead. More than three thousand inmates from eighteen seventy-six to nineteen oh-nine. Then the high school moved in.

London Bridge

63. Billboard: London Bridge, ahead in Lake Havasu City, bought in nineteen sixty-eight and rebuilt in Arizona. The buyer swore it was the bridge he wanted.

Tonto Natural Bridge State Park

64. Billboard: Tonto Natural Bridge State Park, ahead, probably the world's largest travertine bridge, a hundred eighty-three feet high. It is rated for hikers only.

Oatman

65. Billboard: Oatman, north of Topock on old Route sixty-six. Wild burros run the main street and expect to be fed. They outrank the cars.
