# Review: east and south attraction signs -- draft 2026-10-01

DRAFT for owner review. Nothing here is baked; every sheet below dry-runs
clean through `tools/bake_billboards.py` (no `--write`).

- **Attractions:** 86 (84 billboards and 2 respectful `landmark` callouts),
  plus 1 correction to an existing callout.
- **Signs:** 358 blocks on the eight state sheets (357 new signs and the
  correction).
- **New lines:** 104 distinct spoken lines, listed below.
- **Reused-copy signs:** 32, on `east-south-reverse-copies-2026-10-01.md`:
  16 give a one-way sign its other direction on the same leg, 16 put the
  same words on another leg of the same road past the same place.
  Existing approved text, verbatim; not listed as new lines.

| State | Sheet | Attractions | Signs |
|---|---|---|---|
| New York | `new-york-2026-10-01.md` | 14 | 63 |
| Pennsylvania | `pennsylvania-2026-10-01.md` | 15 | 69 |
| Virginia | `virginia-2026-10-01.md` | 13 | 47 |
| North Carolina | `north-carolina-2026-10-01.md` | 11 | 40, and the correction |
| South Carolina | `south-carolina-2026-10-01.md` | 8 | 32 |
| Georgia | `georgia-2026-10-01.md` | 9 | 39 |
| Alabama | `alabama-2026-10-01.md` | 9 | 40 |
| Mississippi | `mississippi-2026-10-01.md` | 7 | 27 |

Spacing: every new and reused sign sits at least 2.2 miles from every
callout heard the same way on its leg (the game's own rule: landmarks with
no `directions`, same-facing billboards, villages within a mile and a half)
and from every other sign on these nine sheets. Every new line starts
"Billboard: " (the two landmark callouts and the correction excepted), has
no digits, and runs 19 to 27 words. Signs stand only where that state's
law allows boards (see each sheet's header; Maryland, the District,
Vermont and Maine carry none of them, except one Chincoteague sign on
Maryland's at-grade US 13, which Maryland permits, as on the northeast
sheet).

## Decisions

1. **The two Thruway legs to New York City announce state lines that are
   not there.** Recommend fixing them before these signs ship (a data fix,
   outside this branch). Rochester to New York says "Crossing into
   Pennsylvania" near Amsterdam, then New Jersey near Newburgh, then New
   York in the Bronx; Buffalo to New York does the same at miles 247, 358
   and 431. Both legs' `state_miles` also give Pennsylvania about 110
   Thruway miles each, which is part of why the sweep scored Pennsylvania
   so thin. Buffalo to New York's geometry further leaves the Thruway at
   Syracuse for I-81 and New York 17 while its checkpoints stay on the
   Thruway, so its signs stand only on its first 149 and last 58 miles.
   No leg runs I-80 across Pennsylvania today.
2. **Flight 93 (Pennsylvania) and the D-Day Memorial at Bedford
   (Virginia).** Recommend keeping both as `landmark` callouts heard both
   ways, in the register of the Appomattox and Edmund Pettus Bridge
   callouts: no joke, one fact. Leave them out if you would rather keep
   those two places off the radio entirely.
3. **Fort Liberty is Fort Bragg again.** Recommend approving the
   correction block on the North Carolina sheet: the existing Greensboro
   to Fayetteville callout still says "Fort Liberty", and the post was
   renamed Fort Bragg on February 14, 2025. The block keeps the record's
   name so a bake replaces it; only the post's name in the line changes.
4. **Reused copy on second legs of the same road (16 signs).** Recommend
   keeping them: the words are approved and true there. One carries the
   existing Talladega line's movie quote ("if you ain't first, you're
   last") onto three more signs.
5. **Two existing signs stand on the wrong road for their place.**
   Recommend, in a follow-up, putting their approved copy on the road that
   passes the place: the USS Alabama line stands only on US 45 out of
   Mobile though the ship sits on I-10's Battleship Parkway, and the
   Madison line stands only on US 129 though I-20 passes Madison at Exit
   114. Not done here, because the brief limited reused copy to the same
   road.
6. **Law checks were cut short.** The session's shared web-search budget
   ran out after New York, Pennsylvania and Virginia had been checked. For
   North Carolina through Mississippi the state statutes and federal
   23 U.S.C. 131(s) are cited, but the state scenic byway lists were not
   checked road by road. Recommend accepting: every sign there stands on
   an Interstate or on a US route (US 17, US 25, US 52, US 61, US 72, US
   76, US 82, US 84, US 264, US 280, US 378, US 431) where boards stand
   today. US 17 at Calabash and Pawleys Island and US 25 at Flat Rock are
   the ones to look at if you want certainty.
7. **Verification after search ran out.** From North Carolina on, every
   fact and open status came from the attraction's own site, the National
   Park Service, or Wikipedia, cited in each section. Recommend accepting;
   where only Wikipedia confirms the place is open, it is a long-standing
   institution. Dropped because nothing could confirm they are open: the
   BMW Zentrum, the Tobacco Farm Life Museum, the Georgia Museum of
   Agriculture, the Whistle Stop Cafe, Leland's Jim Henson exhibit, the
   Biedenharn Coca-Cola Museum and the Mendenhall revolving tables.
8. **Brand names.** Pepsi (New Bern), Coca-Cola (Bellingrath's founder),
   Crayola (Easton), HGTV (Laurel), NASA (Infinity) and Mt. Olive (the
   pickle drop) are named nominatively, no slogans. Recommend keeping.
9. **Clanton's line leans on the Peachoid's.** "Gaffney's is bigger" only
   lands if the Peachoid sign is approved too. Recommend keeping both; if
   the Peachoid is cut, end Clanton with "The peaches are real."
10. **Patsy Cline's house.** Recommend leaving the Route 7 and US 50
    approaches to Winchester unsigned: their Virginia Byway status could
    not be confirmed, and Virginia bars boards on byways. The two I-81
    approaches carry it.
11. **Shared legs with the other three regions.** These sheets were checked
    against everything baked today and each other, not against the other
    agents' 2026-10-01 drafts. Recommend one combined spacing pass before
    baking; the shared legs are Atlanta to Dallas, the Tennessee legs into
    Atlanta, Gadsden and Huntsville, the Florida legs into Valdosta,
    Albany, Dothan and Mobile, the Louisiana legs into Gulfport, Natchez and
    Vicksburg, and the Ohio, West Virginia and Maryland legs into Erie,
    Pittsburgh, Carlisle and Winchester.

Left unsigned where a leg's own route points describe a different road
from its geometry (the signs would be placed against the wrong road):
Burlington to Albany (US 7 geometry, I-87 checkpoints), New York to Albany
south of Suffern, Allentown to Bridgeport at the Tappan Zee, Rochester to
New York at Sleepy Hollow, Binghamton to Utica south of Norwich, Washington
to Charlottesville, Roanoke to Greensboro north of Martinsville, Norfolk to
Petersburg, Harrisburg to Wilmington, and State College to Harrisburg.

Also left out: Saratoga (no reliable leg), Corning, Pine Creek Gorge and
Punxsutawney (no leg reaches them), Kings Dominion, Secret Caverns and
Montezuma (same exit as a signed neighbour), Stone Mountain (the carving),
Rock City (standing rule), and the Hank Williams Museum (a pool line names
him already).

## New lines

Numbered, grouped by attraction; the sign count follows each line.

### New York

Niagara Falls State Park, Niagara Falls (on the roads into Buffalo):

1. Billboard: Niagara Falls State Park, twenty miles north of Buffalo. The oldest state park in America, since eighteen eighty-five. The falls have not paused once. (6 signs)

The Anchor Bar, Buffalo:

2. Billboard: The Anchor Bar, ahead in Buffalo, where Buffalo wings were invented in nineteen sixty-four. Before that, wings went into the soup pot. (6 signs)

The Strong National Museum of Play, Rochester:

3. Billboard: The Strong Museum of Play, ahead in Rochester. Its Toy Hall of Fame inducted a stick and a cardboard box. Your trailer has a chance. (7 signs)

Women's Rights National Historical Park, Seneca Falls (Thruway Exit 41):

4. Billboard: Women's Rights National Historical Park, ahead in Seneca Falls. The first women's rights convention met there in eighteen forty-eight. Two days, one long list. (3 signs)

5. Billboard: Women's Rights National Historical Park, next exit, in Seneca Falls. The first women's rights convention met there in eighteen forty-eight. Two days, one long list. (5 signs)

The Oneida Community Mansion House, Oneida (Thruway Exits 33 and 34):

6. Billboard: The Oneida Community Mansion House, ahead in Oneida. A commune shared everything here in the eighteen hundreds. The commune ended. Its spoon business did not. (6 signs)

Herkimer Diamond Mines, Middleville (Thruway Exit 30):

7. Billboard: Herkimer Diamond Mines, ahead, north of Herkimer. Dig your own diamonds. They are quartz, but the people back home do not need to know. (4 signs)

8. Billboard: Herkimer Diamond Mines, next exit, nine miles north. Dig your own diamonds. They are quartz, but the people back home do not need to know. (2 signs)

Howe Caverns, Howes Cave (I-88 Exit 22):

9. Billboard: Howe Caverns, next exit. An elevator drops a hundred fifty-six feet to a boat ride on an underground lake. It has never seen daylight. (2 signs)

Thomas Cole National Historic Site, Catskill (Thruway Exit 21):

10. Billboard: The Thomas Cole National Historic Site, next exit, in Catskill. He founded the Hudson River School of painting, which never had a classroom. (3 signs)

11. Billboard: The Thomas Cole National Historic Site, ahead in Catskill. He founded the Hudson River School of painting, which never had a classroom. (1 sign)

Storm King Art Center, Mountainville (Thruway Exit 16):

12. Billboard: Storm King Art Center, ahead near Mountainville. Five hundred acres of giant sculpture on open hills. Some of the pieces weigh more than your load. (2 signs)

Sleepy Hollow (Thruway Exit 9, at the Mario Cuomo Bridge):

13. Billboard: Sleepy Hollow, next exit. Washington Irving is buried in the old cemetery there. The Headless Horseman is not, which is the worry. (1 sign)

14. Billboard: Sleepy Hollow, ahead by the bridge. Washington Irving is buried in the old cemetery there. The Headless Horseman is not, which is the worry. (1 sign)

Lily Dale Assembly, Lily Dale (I-90 Exit 59):

15. Billboard: Lily Dale, next exit, nine miles south. A whole town of mediums since eighteen seventy-nine. They already know you are not stopping. (1 sign)

16. Billboard: Lily Dale, ahead, south of Dunkirk. A whole town of mediums since eighteen seventy-nine. They already know you are not stopping. (3 signs)

Lily Dale Assembly, on Route 60 (Jamestown to Buffalo):

17. Billboard: Lily Dale, ahead, just off Route Sixty. A whole town of mediums since eighteen seventy-nine. They already know you are not stopping. (2 signs)

The National Comedy Center, Jamestown:

18. Billboard: The National Comedy Center, ahead in Jamestown, Lucille Ball's hometown. A whole museum about comedy. This sign did not make the cut. (2 signs)

The carousels of Binghamton:

19. Billboard: Binghamton, ahead, the Carousel Capital of the World. Six antique merry-go-rounds, free all summer. The fare is one piece of litter. (4 signs)

Boldt Castle, Heart Island, Alexandria Bay (north of Watertown):

20. Billboard: Boldt Castle, north of Watertown in the Thousand Islands. A hotel man reshaped the island into a heart for his wife. Most of us bring flowers. (2 signs)


### Pennsylvania

Valley Forge National Historical Park, King of Prussia (Turnpike Exit 326):

21. Billboard: Valley Forge National Historical Park, ahead. Washington's army spent the winter of seventeen seventy-seven here. Your heater works. Be grateful. (4 signs)

Fallingwater, Mill Run (Turnpike Exit 91, Donegal):

22. Billboard: Fallingwater, ahead, south of the Donegal exit. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted. (4 signs)

23. Billboard: Fallingwater, next exit, nineteen miles south. Frank Lloyd Wright built the house right over a waterfall. The waterfall was not consulted. (6 signs)

Flight 93 National Memorial, Stoystown (Turnpike Exit 110, Somerset):

24. You are passing near Shanksville, where the Flight Ninety-Three National Memorial honors the forty passengers and crew of September eleventh, two thousand one. (5 signs)

The Bedford Coffee Pot, Bedford (Turnpike Exit 146):

25. Billboard: The Bedford Coffee Pot, ahead. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop. (9 signs)

26. Billboard: The Bedford Coffee Pot, next exit. A coffee pot building from nineteen twenty-seven. It has been a bar and a bus stop, never a coffee shop. (1 sign)

The U.S. Army Heritage and Education Center, Carlisle:

27. Billboard: The Army Heritage and Education Center, ahead in Carlisle. Free admission, and an outdoor trail of real tanks and trenches. Those tanks are parked for good. (9 signs)

Hawk Mountain Sanctuary, Kempton (I-78 Exit 29, Hamburg):

28. Billboard: Hawk Mountain Sanctuary, ahead, north of Hamburg. Each fall about eighteen thousand hawks pass its lookout. Not one of them stops for fuel. (2 signs)

The Crayola Experience, Easton (I-78 Exit 75):

29. Billboard: The Crayola Experience, ahead in Easton. Twenty-five rooms of crayons, and you can melt one into a new shape. Coloring outside the lines is encouraged. (6 signs)

Jim Thorpe (I-476 Exit 74, Mahoning Valley):

30. Billboard: Jim Thorpe, next exit. The Olympic champion never set foot in this town. It took his name in nineteen fifty-four, and he rests there now. (1 sign)

Steamtown National Historic Site, Scranton:

31. Billboard: Steamtown National Historic Site, ahead in Scranton. Real steam locomotives in a working roundhouse, and admission is free. The paper company is a different show. (3 signs)

Pioneer Tunnel Coal Mine, Ashland (I-81 at Frackville):

32. Billboard: Pioneer Tunnel Coal Mine, ahead in Ashland. Ride an open mine car eighteen hundred feet into a real coal mine. Your cab has more legroom. (2 signs)

The Pennsylvania Trolley Museum, Washington (I-79 Exit 41):

33. Billboard: The Pennsylvania Trolley Museum, ahead near Washington. Almost fifty trolleys, and admission includes a four-mile ride. The motorman never once has to steer. (6 signs)

Horseshoe Curve National Historic Landmark, Altoona:

34. Billboard: Horseshoe Curve, ahead outside Altoona. The main line climbs the Alleghenies by bending back on itself. The trains do the hard part. You watch. (2 signs)

Penn State Berkey Creamery, State College:

35. Billboard: Penn State's Berkey Creamery, ahead in State College. Ben and Jerry learned ice cream here by mail, in a course they split for five dollars. (2 signs)

The World of Little League Museum, South Williamsport:

36. Billboard: The World of Little League Museum, ahead in South Williamsport. Every August the world watches twelve-year-olds play baseball here. Some throw harder than you. (3 signs)

Presque Isle State Park, Erie:

37. Billboard: Presque Isle State Park, ahead in Erie. Seven miles of sand beach on Lake Erie. Pennsylvania has a seashore, and this is the whole of it. (4 signs)


### Virginia

Natural Bridge State Park, Natural Bridge (I-81 Exits 175 and 180):

38. Billboard: Natural Bridge State Park, next exit. Thomas Jefferson bought it from King George the Third for twenty shillings. Nobody has topped that deal. (2 signs)

Luray Caverns, Luray (I-81 Exit 264, New Market):

39. Billboard: Luray Caverns, next exit, east of New Market. An organ inside taps thirty-seven stalactites, the largest instrument in the world. Nobody has to carry it. (1 sign)

40. Billboard: Luray Caverns, ahead, east of New Market. An organ inside taps thirty-seven stalactites, the largest instrument in the world. Nobody has to carry it. (1 sign)

The Frontier Culture Museum, Staunton (I-81 Exit 222):

41. Billboard: The Frontier Culture Museum, ahead at Staunton. Farms from England, Ireland, Germany and West Africa, rebuilt in one Virginia valley. The cows came separately. (7 signs)

The Mill Mountain Star, Roanoke:

42. Billboard: Roanoke, ahead, the Star City. The Mill Mountain Star is eighty-eight feet of neon, lit since nineteen forty-nine. It was meant to be temporary. (8 signs)

Barter Theatre, Abingdon:

43. Billboard: Barter Theatre, ahead in Abingdon. In nineteen thirty-three a ticket was forty cents or the same in vegetables. Ham for Hamlet, they called it. (4 signs)

The Patsy Cline Historic House, Winchester:

44. Billboard: The Patsy Cline Historic House, ahead in Winchester. She lived there from sixteen to twenty-one, longer than anywhere else. The town still claims her. (2 signs)

Colonial Williamsburg (I-64 Exit 238):

45. Billboard: Colonial Williamsburg, next exit. Eighteenth-century Virginia, open every day of the year. The people in three-cornered hats are on the clock. (4 signs)

The National Museum of the Marine Corps, Triangle (I-95 Exit 150):

46. Billboard: The National Museum of the Marine Corps, ahead at Triangle. Free admission, every day but Thanksgiving and Christmas. Stand up straight on the way in. (3 signs)

Chincoteague Island (US 13 at Route 175):

47. Billboard: Chincoteague Island, ahead, east of here on the coast. Every July its wild ponies swim the channel from Assateague. They never wait for the bridge. (2 signs)

Martinsville Speedway, Ridgeway (US 220):

48. Billboard: Martinsville Speedway, ahead in Ridgeway. NASCAR has raced this half-mile paperclip every year since nineteen forty-nine. Your trailer would not make the turns. (4 signs)

The National D-Day Memorial, Bedford (US 460):

49. You are passing Bedford, home of the National D-Day Memorial. This small town lost more of its sons per capita on D-Day than any other in America. (1 sign)

Battleship Wisconsin at Nauticus, Norfolk:

50. Billboard: The Battleship Wisconsin, ahead in Norfolk. Nearly nine hundred feet of battleship, open daily at Nauticus. Your trailer is fifty-three feet. (5 signs)

King Neptune, Virginia Beach boardwalk:

51. Billboard: Virginia Beach, ahead. A thirty-four-foot bronze King Neptune stands on the boardwalk at Thirty-First Street. Twenty years, and he has never gone in. (3 signs)


### North Carolina

The North Carolina Transportation Museum, Spencer (I-85 Exit 79):

52. Billboard: The North Carolina Transportation Museum, ahead in Spencer. The old railroad shops keep the largest roundhouse left in North America. Trucks get a parking lot. (4 signs)

53. Billboard: The North Carolina Transportation Museum, next exit. The old railroad shops keep the largest roundhouse left in North America. Trucks get a parking lot. (2 signs)

The Big Chair, Thomasville (I-85):

54. Billboard: Thomasville, ahead, the Chair City. A thirty-foot armchair has stood downtown since nineteen fifty-one. It is still waiting on a matching table. (4 signs)

Carowinds, on the state line (I-77 Exit 90):

55. Billboard: Carowinds, ahead, right on the state line. The line is painted across the front gate. Ride in one Carolina, eat lunch in the other. (3 signs)

56. Billboard: Carowinds, next exit, right on the state line. The line is painted across the front gate. Ride in one Carolina, eat lunch in the other. (1 sign)

Old Salem Museums and Gardens, Winston-Salem:

57. Billboard: Old Salem, ahead in Winston-Salem. A Moravian town from seventeen sixty-six, and its bakery still bakes in a wood-fired oven. Arrive hungry. (4 signs)

The Ava Gardner Museum, Smithfield (I-95):

58. Billboard: The Ava Gardner Museum, ahead in Smithfield. The movie star was born nearby, in a place called Grabtown. It still has the better name. (2 signs)

Vollis Simpson Whirligig Park, Wilson:

59. Billboard: The Vollis Simpson Whirligig Park, ahead in Wilson. Giant whirligigs he built from scrap metal spin in the wind downtown. The wind works for free. (4 signs)

Mt. Olive Pickle Company, Mount Olive (east of I-40):

60. Billboard: Mount Olive, ahead, east of the interstate. Its pickle company drops a glowing pickle every New Year's Eve at seven. Everyone is in bed by eight. (2 signs)

The Airborne and Special Operations Museum, Fayetteville:

61. Billboard: The Airborne and Special Operations Museum, ahead in Fayetteville. Free admission. Everyone it honors once jumped out of a perfectly good airplane. (6 signs)

The birthplace of Pepsi, New Bern:

62. Billboard: New Bern, ahead, where Pepsi was born. A druggist mixed it here in eighteen ninety-three and called it Brad's Drink. The name needed work. (2 signs)

Calabash (US 17 at the South Carolina line):

63. Billboard: Calabash, ahead at the state line. The Seafood Capital of the World, frying its catch the same way since the nineteen thirties. Bring napkins. (2 signs)

Carl Sandburg Home National Historic Site, Flat Rock:

64. Billboard: The Carl Sandburg Home, ahead in Flat Rock. The poet wrote here while his wife raised prize dairy goats. The goats still outnumber the poets. (4 signs)

Correction: Fort Liberty is Fort Bragg again (Greensboro to Fayetteville):

65. You are nearing Fayetteville and Fort Bragg, home of the Eighty-Second Airborne and the Green Berets. It is one of the largest military bases on Earth. (1 sign)


### South Carolina

The Peachoid, Gaffney (I-85 between Exits 90 and 92):

66. Billboard: The Peachoid, ahead in Gaffney. A water tower shaped like a peach, a hundred thirty-five feet tall. It holds a million gallons and no peaches. (4 signs)

Riverbanks Zoo and Garden, Columbia:

67. Billboard: Riverbanks Zoo and Garden, ahead in Columbia. Three thousand animals beside the Saluda River. None of them has ever had to merge. (9 signs)

The South Carolina Artisans Center, Walterboro (I-95):

68. Billboard: The South Carolina Artisans Center, ahead in Walterboro. Two hundred artists from forty-one of the state's forty-six counties. The other five are still practicing. (4 signs)

Brookgreen Gardens, Murrells Inlet (US 17):

69. Billboard: Brookgreen Gardens, ahead at Murrells Inlet. America's first public sculpture garden, more than fourteen hundred pieces. Every one of them holds still. (2 signs)

The Original Hammock Shop, Pawleys Island (US 17):

70. Billboard: The Original Hammock Shop, ahead on Pawleys Island. Rope hammocks woven by hand since nineteen thirty-eight. Lie down in one and the drive is over. (2 signs)

Myrtle Beach and the Grand Strand:

71. Billboard: Myrtle Beach, ahead, the middle of the Grand Strand. Sixty miles of beach from Little River to Winyah Bay. The sand will find your cab. (3 signs)

Swan Lake Iris Gardens, Sumter:

72. Billboard: Swan Lake Iris Gardens, ahead in Sumter. The only public park in America with all eight kinds of swan. They set the right of way. (2 signs)

Falls Park on the Reedy, Greenville:

73. Billboard: Falls Park, ahead in Greenville. A waterfall downtown, and a footbridge that curves over it, hung from cables on one side only. It holds. (6 signs)


### Georgia

The giant peanut, Ashburn (I-75 Exit 82):

74. Billboard: Ashburn, next exit. Its giant crowned peanut is a state monument. A hurricane knocked it down in two thousand eighteen, and it got back up. (1 sign)

75. Billboard: Ashburn, ahead. Its giant crowned peanut is a state monument. A hurricane knocked it down in two thousand eighteen, and it got back up. (1 sign)

The Museum of Aviation, Warner Robins (I-75):

76. Billboard: The Museum of Aviation, ahead at Warner Robins. Free admission and more than eighty aircraft, among them the fastest jet ever flown. It is on a long break. (2 signs)

Tellus Science Museum, Cartersville (I-75 Exit 293):

77. Billboard: Tellus Science Museum, next exit. A dinosaur skeleton stands in the lobby, and the planetarium has the rest of the universe. Allow an afternoon. (7 signs)

78. Billboard: Tellus Science Museum, ahead at Cartersville. A dinosaur skeleton stands in the lobby, and the planetarium has the rest of the universe. Allow an afternoon. (2 signs)

Jimmy Carter National Historical Park, Plains (US 280):

79. Billboard: Plains, ahead, home of President Jimmy Carter. The old train depot, the oldest building in town, ran his nineteen seventy-six campaign. Open daily. (2 signs)

Callaway Gardens, Pine Mountain (west of I-185):

80. Billboard: Callaway Gardens, ahead at Pine Mountain. About a thousand butterflies live in its glass conservatory all year. Not one of them keeps a schedule. (2 signs)

The National Infantry Museum, Columbus:

81. Billboard: The National Infantry Museum, ahead in Columbus. Free admission, from the Revolution to today. The infantry walked here. You get to drive. (7 signs)

Ray Charles Plaza, Albany:

82. Billboard: Albany, ahead, where Ray Charles was born. A bronze of him at the piano turns slowly in the plaza downtown. He has not missed a show. (7 signs)

The Big Oak, Thomasville (US 84):

83. Billboard: Thomasville, ahead, the City of Roses. The Big Oak downtown has been growing since about sixteen eighty. It was here before the roses. (2 signs)

Wild Adventures, Valdosta (I-75 Exit 13):

84. Billboard: Wild Adventures, ahead, south of Valdosta. Six roller coasters and a zoo in one park. The animals have chosen not to ride. (6 signs)


### Alabama

The Ave Maria Grotto, Cullman (I-65 Exit 308):

85. Billboard: The Ave Maria Grotto, ahead in Cullman. A monk built a hundred twenty-five tiny landmarks from marbles, shells and cold cream jars. Save your jars. (5 signs)

86. Billboard: The Ave Maria Grotto, next exit. A monk built a hundred twenty-five tiny landmarks from marbles, shells and cold cream jars. Save your jars. (1 sign)

The U.S. Space and Rocket Center, Huntsville:

87. Billboard: The United States Space and Rocket Center, ahead in Huntsville. A whole Saturn Five rocket rests indoors on its side. Your cab has fewer buttons. (6 signs)

Vulcan Park, Birmingham:

88. Billboard: Vulcan, ahead in Birmingham. The largest cast iron statue in the world stands on Red Mountain. His bare backside has faced Homewood since nineteen thirty-nine. (9 signs)

Barber Vintage Motorsports Museum, Leeds (I-20 Exit 140):

89. Billboard: The Barber Vintage Motorsports Museum, next exit. Nine hundred motorcycles on display, the world's largest motorcycle museum. Every one of them gets better mileage. (4 signs)

Unclaimed Baggage, Scottsboro (US 72):

90. Billboard: Unclaimed Baggage, ahead in Scottsboro. A city block of things the airlines lost, all for sale. Your missing suitcase might be on aisle four. (2 signs)

The Alabama Music Hall of Fame, Tuscumbia (US 72):

91. Billboard: The Alabama Music Hall of Fame, ahead in Tuscumbia. Nat King Cole, Hank Williams, Lionel Richie and the band Alabama, all one state's doing. (1 sign)

The Paul W. Bryant Museum, Tuscaloosa:

92. Billboard: The Paul W. Bryant Museum, ahead in Tuscaloosa. Alabama football history, and a houndstooth hat made of Waterford crystal. Nobody has ever worn it. (6 signs)

Bellingrath Gardens and Home, Theodore (I-10 Exit 15):

93. Billboard: Bellingrath Gardens, next exit, south on the Fowl River. A Coca-Cola bottler's sixty-five acres and a quarter million azaleas. Worth the detour. (3 signs)

94. Billboard: Bellingrath Gardens, ahead, south of Theodore. A Coca-Cola bottler's sixty-five acres and a quarter million azaleas. Worth the detour. (1 sign)

The Clanton peach water tower, Clanton (I-65):

95. Billboard: Clanton, ahead. This county grows most of Alabama's peaches, and its water tower is shaped like one. Gaffney's is bigger. Clanton is fine with that. (2 signs)


### Mississippi

Vicksburg National Military Park (I-20 Exit 4B):

96. Billboard: Vicksburg National Military Park, next exit. A sixteen-mile road around the siege lines of eighteen sixty-three, and a Union gunboat raised from the river. (3 signs)

97. Billboard: Vicksburg National Military Park, ahead. A sixteen-mile road around the siege lines of eighteen sixty-three, and a Union gunboat raised from the river. (3 signs)

The B.B. King Museum and Delta Interpretive Center, Indianola (US 82):

98. Billboard: The B B King Museum, ahead in Indianola. It stands in the cotton gin where he worked in the nineteen forties. He called every guitar Lucille. (2 signs)

The Delta Blues Museum, Clarksdale:

99. Billboard: The Delta Blues Museum, ahead in Clarksdale. The old depot holds the cabin Muddy Waters reportedly lived in. The blues never needed much room. (4 signs)

Rowan Oak, Oxford:

100. Billboard: Rowan Oak, ahead in Oxford, William Faulkner's home. He wrote the outline of a novel on his office wall. Guests are asked to use paper. (3 signs)

INFINITY Science Center, Pearlington (I-10 Exit 2):

101. Billboard: The Infinity Science Center, ahead at the welcome center. NASA tests its biggest rocket engines just up the road. Yours is quieter. (4 signs)

102. Billboard: The Infinity Science Center, next exit, at the welcome center. NASA tests its biggest rocket engines just up the road. Yours is quieter. (2 signs)

Laurel (I-59):

103. Billboard: Laurel, ahead, the town from the television show Home Town. Downtown is real, and so is Mississippi's oldest art museum. Somebody even fixed the sign. (4 signs)

Natchez:

104. Billboard: Natchez, ahead, founded in seventeen sixteen. That is two years before New Orleans, and Natchez will mention it. (2 signs)

