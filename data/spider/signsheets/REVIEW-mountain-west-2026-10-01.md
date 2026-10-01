# Review: Mountain West billboard drafts -- 2026-10-01

Drafts for the owner's review; nothing here is baked. Sheets so far:
`nebraska-2026-10-01.md`, `wyoming-2026-10-01.md`, and
`mountain-west-reverse-copies-2026-10-01.md`.

## Counts

- Nebraska: 10 attractions, 46 signs, 10 new lines.
- Wyoming: 11 attractions, 83 signs, 11 new lines.
- Reused-copy signs (older approved copy, other directions and sibling
  legs): 17, all in Nebraska so far.
- Total so far: 21 attractions, 129 new-copy signs, 21 new lines, 17
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
3. **Two plain lines with no joke**, for a battle site and a sacred one:
   Fort Phil Kearny and Devils Tower. Recommendation: keep them plain.
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
