# Ruth catalog: billboard pool expansion (feat/career-1.9-songs)

For Chelsea to Ruth. Every NEW line since origin/feat/career-1.9 tip (c57a13bc base of this draft).

## Confirms
- ME/VT/AK/HI commercial-board gate in `place_billboards` (Scenic America / FHWA four-state ban). Bubba's Fireworks re-anchored to SC+NC.
- I-40 TN was **not** used as Music Highway paid ads. Beale Street / Graceland / Grand Ole Opry / Ryman are ticketed tourism Approaching only.
- See Rock City absent. META unchanged. SONG_TRIBUTE still only Hank Snow + Del Reeves. `TRIBUTE_DRAW_CHANCE` still 0.1. Density still 35–65 mi.
- Big Buck's remains approach-only (not in ROADSIDE).
- ADULT is always eligible wherever commercial boards are legal. No settings switch, content filter, or default-off path.

## Ruth cut (2026-09-16)
KEEP: GENERIC; ATTORNEY Big Jim; FAITH; ODDITIES; TRUCKER except lumper; RADIO; POP_CULTURE generic dated theatrical-drive-in; BIG_BUCKS approach; corridor ticketed tourism+produce+Tejano SA-Laredo+casinos+Iowa 80+OZ Wamego+Arch+Blueberry Hill+Billy Bob's+Crystal Palace+MoPOP+Harley+Slugger+Space Center+Horse Park+Bristol museum+Corn Palace+Spam+Graceland/Beale/Opry/Ryman+Orlando no-Disney-slogans.

MOVED (Anywhere to States, wired through `regional_genre_signs` + `place_billboards` / `corridor_signs` filter):
- FIREWORKS: AL/AR/FL/GA/IA/IL/IN/KS/KY/LA/MI/MO/MS/NC/OH/OK/PA/SC/TN/TX/VA/WI/WV (southern/midwest fireworks-stand country). Bubba's stays SC+NC on I-95.
- PECAN: TX/GA/LA/AL/MS.
- Sheetz: PA/OH/WV/MD/VA/NC/MI.
- Wawa: FL/NJ/PA/VA/MD/DE (mid-Atlantic + FL, not AZ).
- RaceTrac: AL/AR/FL/GA/KY/LA/MS/NC/SC/TN/TX/VA (southeast + Texas).
- Cracker Barrel: South/Midwest (AL AR FL GA IA IL IN KS KY LA MI MN MO MS NC NE OH OK SC TN TX VA WI WV).
- Love's / Pilot / generic travel-center / motel / QSR stay Anywhere.

KILLED:
- TRUCKER "Lumper service, next warehouse…"
- I-35 "McAllen ahead…" (McAllen is I-2/I-69C/US-281; I-35 ends Laredo). Not relocated onto an unmapped shield. Laredo + San Antonio keep I-35 Tejano.

STILL OUT: lyrics, META growth, Music Highway paid ads, Rock City on I-75, Wall Drug MT only (WY restored: Argus Leader campaign SD/WY/western MN; Greybull WY ~394 mi).

ADULT: Grok Build rewrite, 22 lines, Anywhere invented brands, opaque Lion's Den / next-exit register (superstore, bookstore, gentleman's club, XXX theater). No graphic sex-act copy, no real-chain slogans, no named towns.

## Counts: 186 live new lines (172 draft − 1 lumper − 1 McAllen + 15 net ADULT adds; several relocated off Anywhere)

| Pool | Exact text | SignAnchor | Research |
|---|---|---|---|
| GENERIC | Next exit: homemade jerky and a gift shop that sells the same jerky. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | We have ice. We have bait. We have opinions about your bumper sticker. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Diesel, showers, and a fried pie that will change your itinerary. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | All-you-can-eat catfish. Bring a bigger belt. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | World's largest frying pan. Breakfast is served. Bring a forklift. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Homemade pie, next exit. Made this morning. The coffee is older. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Fresh peaches, next exit. Pick your own or grab a bag. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Antiques and ammunition. One building. Two hobbies. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | If you lived here, you'd be home by now. Nobody lives here. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Truck wash, next exit. Your trailer used to be white. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | The coffee is fine. The pie is better. The gossip is unbeatable. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Concrete deer and yard gnomes, next exit. We help you load them. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Gift shop, next exit. Dashboard hula girls, half off. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Local honey. Local jam. Local opinions, free with every purchase. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | The steak is bigger than the plate. The plate is bigger than your budget. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Next exit: homemade ice cream. The cows are local. The freezer is older than you. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Gun show this weekend, craft fair the next. Same tent. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| GENERIC | Buffet: if it isn't on a steam table, it isn't dinner. | Anywhere | invented Americana / roadfood boards (OAAA restaurant/service genre) |
| FIREWORKS | Fireworks, fireworks, fireworks. You're already past it. | States ['AL','AR','FL','GA','IA','IL','IN','KS','KY','LA','MI','MO','MS','NC','OH','OK','PA','SC','TN','TX','VA','WI','WV'] (MOVED off Anywhere) | southern/midwest fireworks-barn OOH; state-line stand genre |
| FIREWORKS | Fireworks barn, next exit. If you can still hear, you haven't shopped enough. | States ['AL','AR','FL','GA','IA','IL','IN','KS','KY','LA','MI','MO','MS','NC','OH','OK','PA','SC','TN','TX','VA','WI','WV'] (MOVED off Anywhere) | southern/midwest fireworks-barn OOH; state-line stand genre |
| FIREWORKS | Family fireworks. Professional regret. Open till the sheriff gets here. | States ['AL','AR','FL','GA','IA','IL','IN','KS','KY','LA','MI','MO','MS','NC','OH','OK','PA','SC','TN','TX','VA','WI','WV'] (MOVED off Anywhere) | southern/midwest fireworks-barn OOH; state-line stand genre |
| FIREWORKS | Buy one crate, get the ringing in your ears free. | States ['AL','AR','FL','GA','IA','IL','IN','KS','KY','LA','MI','MO','MS','NC','OH','OK','PA','SC','TN','TX','VA','WI','WV'] (MOVED off Anywhere) | southern/midwest fireworks-barn OOH; state-line stand genre |
| FIREWORKS | Stand back. Light fuse. That's the whole business plan. Next exit. | States ['AL','AR','FL','GA','IA','IL','IN','KS','KY','LA','MI','MO','MS','NC','OH','OK','PA','SC','TN','TX','VA','WI','WV'] (MOVED off Anywhere) | southern/midwest fireworks-barn OOH; state-line stand genre |
| FIREWORKS | Roman candles, bottle rockets, and a very optimistic fire extinguisher. | States ['AL','AR','FL','GA','IA','IL','IN','KS','KY','LA','MI','MO','MS','NC','OH','OK','PA','SC','TN','TX','VA','WI','WV'] (MOVED off Anywhere) | southern/midwest fireworks-barn OOH; state-line stand genre |
| FIREWORKS | Closed on Christmas. Open on every other bad idea. | States ['AL','AR','FL','GA','IA','IL','IN','KS','KY','LA','MI','MO','MS','NC','OH','OK','PA','SC','TN','TX','VA','WI','WV'] (MOVED off Anywhere) | southern/midwest fireworks-barn OOH; state-line stand genre |
| FIREWORKS | Fireworks warehouse. No smoking. We are serious. Look at the inventory. | States ['AL','AR','FL','GA','IA','IL','IN','KS','KY','LA','MI','MO','MS','NC','OH','OK','PA','SC','TN','TX','VA','WI','WV'] (MOVED off Anywhere) | southern/midwest fireworks-barn OOH; state-line stand genre |
| FIREWORKS | Your brother-in-law already bought the loud ones. Catch up, next exit. | States ['AL','AR','FL','GA','IA','IL','IN','KS','KY','LA','MI','MO','MS','NC','OH','OK','PA','SC','TN','TX','VA','WI','WV'] (MOVED off Anywhere) | southern/midwest fireworks-barn OOH; state-line stand genre |
| PECAN | World's largest pecan. You'll smell it before you see it. Next exit. | States ['AL','GA','LA','MS','TX'] (MOVED off Anywhere) | south-central pecan-stand interstate ads; giant-pecan rivalry (Seguin/Brunswick real; copy unnamed) |
| PECAN | Pecan logs, pecan pie, pecan everything. Your passenger will complain. Buy two. | States ['AL','GA','LA','MS','TX'] (MOVED off Anywhere) | south-central pecan-stand interstate ads; giant-pecan rivalry (Seguin/Brunswick real; copy unnamed) |
| PECAN | If it isn't pecans, it isn't a gift. Next exit, we will not be argued with. | States ['AL','GA','LA','MS','TX'] (MOVED off Anywhere) | south-central pecan-stand interstate ads; giant-pecan rivalry (Seguin/Brunswick real; copy unnamed) |
| PECAN | World's second-largest pecan. The biggest one is three exits back and they know it. | States ['AL','GA','LA','MS','TX'] (MOVED off Anywhere) | south-central pecan-stand interstate ads; giant-pecan rivalry (Seguin/Brunswick real; copy unnamed) |
| PECAN | Fresh roasted pecans. The sample is free. The bag is not. | States ['AL','GA','LA','MS','TX'] (MOVED off Anywhere) | south-central pecan-stand interstate ads; giant-pecan rivalry (Seguin/Brunswick real; copy unnamed) |
| PECAN | Pecan pralines, next exit. Sticky steering wheels since nineteen fifty. | States ['AL','GA','LA','MS','TX'] (MOVED off Anywhere) | south-central pecan-stand interstate ads; giant-pecan rivalry (Seguin/Brunswick real; copy unnamed) |
| PECAN | Nuts. We sell them. We attract them. Next exit. | States ['AL','GA','LA','MS','TX'] (MOVED off Anywhere) | south-central pecan-stand interstate ads; giant-pecan rivalry (Seguin/Brunswick real; copy unnamed) |
| PECAN | Pecan brittle so hard it needs a load rating. | States ['AL','GA','LA','MS','TX'] (MOVED off Anywhere) | south-central pecan-stand interstate ads; giant-pecan rivalry (Seguin/Brunswick real; copy unnamed) |
| ADULT | Adult superstore, next exit. Truckers welcome. We will not tell. | Anywhere | rural interstate adult-superstore off-ramp OOH; Lion's Den opaque next-exit register; invented copy (Grok Build 2026-09-16) |
| ADULT | Adult bookstore, next exit. Magazines you will not read. Parking you will use. | Anywhere | adult-bookstore off-ramp OOH; opaque teasing; invented copy (Grok Build) |
| ADULT | Eighteen and over. Eighteen wheels preferred. Next exit. | Anywhere | adult-superstore trucker-welcome register (Grok Build) |
| ADULT | The sign just says Superstore. You already know which one. Next exit. | Anywhere | opaque superstore vinyl; families on the same road (Grok Build) |
| ADULT | Late night, well lit, no questions. Your logbook does not need this stop. | Anywhere | late-night adult-superstore OOH (Grok Build) |
| ADULT | Adult gifts, next exit. For someone else, obviously. | Anywhere | adult-gift/novelty off-ramp register (Grok Build) |
| ADULT | If the billboard is this vague, the store is not. Next exit. | Anywhere | opaque-on-purpose highway vinyl (Grok Build) |
| ADULT | Gentleman's club, next exit. Cold beer. Warm welcome. Dispatch stays outside. | Anywhere | gentleman's-club interstate off-ramp OOH; invented (Grok Build) |
| ADULT | XXX theater, next exit. Dark room. Cheap seats. Nobody looking at you. | Anywhere | XXX/adult theater roadside placard register (Grok Build) |
| ADULT | Open all night. Cash if you prefer. Adult superstore, next exit. | Anywhere | all-night adult-superstore OOH (Grok Build) |
| ADULT | Adult bookstore, next exit. The back room is in the back. You already knew. | Anywhere | adult-bookstore back-room wink; not a sex-act line (Grok Build) |
| ADULT | No cover for truckers. Cover your tracks yourself. Next exit. | Anywhere | gentleman's-club trucker-cover register (Grok Build) |
| ADULT | Feature starts when you sit down. Adult theater, next exit. | Anywhere | adult theater continuous-show placard (Grok Build) |
| ADULT | We sell what the other stores will not name. Superstore, next exit. | Anywhere | adult-superstore opaque inventory tease (Grok Build) |
| ADULT | Your CB will not mention this stop. Adult superstore, next exit. | Anywhere | trucker-welcome adult-superstore OOH (Grok Build) |
| ADULT | Last chance before morning. Gentleman's club, next exit. Last call is whenever. | Anywhere | late-night gentleman's-club OOH (Grok Build) |
| ADULT | Locked cabinet. Open mind. Adult bookstore, next exit. | Anywhere | adult-bookstore locked-cabinet register (Grok Build) |
| ADULT | Couples welcome. Couples optional. Next exit. | Anywhere | club/superstore couples-welcome tease (Grok Build) |
| ADULT | Big lot. Tall doors. Adult superstore. You will fit. | Anywhere | trucker-lot adult-superstore OOH (Grok Build) |
| ADULT | Continuous shows. Discreet exits. XXX theater, next exit. | Anywhere | XXX theater continuous-show placard (Grok Build) |
| ADULT | Stage is small. Tips are not. Gentleman's club, next exit. | Anywhere | gentleman's-club stage/tips register; not graphic (Grok Build) |
| ADULT | Come for the magazines. Leave with a bag you will hide. Bookstore, next exit. | Anywhere | adult-bookstore bag-in-the-cab tease (Grok Build) |
| ATTORNEY | Big Jim saw that lane change. He is not mad. He is drafting. | Anywhere | OAAA #1 Legal Services; truck-wreck PI bulletin genre; Big Jim invented |
| ATTORNEY | Rollover? Call Big Jim. He answers on the first ring. | Anywhere | OAAA #1 Legal Services; truck-wreck PI bulletin genre; Big Jim invented |
| ATTORNEY | Big Jim Tolliver: because your insurance company has a lawyer too. | Anywhere | OAAA #1 Legal Services; truck-wreck PI bulletin genre; Big Jim invented |
| ATTORNEY | Whiplash? Big Jim has a cousin who had that. Call him anyway. | Anywhere | OAAA #1 Legal Services; truck-wreck PI bulletin genre; Big Jim invented |
| ATTORNEY | Big Jim does not sleep. Big Jim's paralegal does not sleep. The bill does not sleep. | Anywhere | OAAA #1 Legal Services; truck-wreck PI bulletin genre; Big Jim invented |
| ATTORNEY | Hurt? Not your fault? Big Jim agrees, and he has not even met you. | Anywhere | OAAA #1 Legal Services; truck-wreck PI bulletin genre; Big Jim invented |
| ATTORNEY | Big Jim's number is on the next six boards. You will remember it. | Anywhere | OAAA #1 Legal Services; truck-wreck PI bulletin genre; Big Jim invented |
| ATTORNEY | Work injury? Big Jim used to drive. Now he sues the people who do. | Anywhere | OAAA #1 Legal Services; truck-wreck PI bulletin genre; Big Jim invented |
| ATTORNEY | Big Jim. Not the other Jim. The billboard Jim. Write it on the visor. | Anywhere | OAAA #1 Legal Services; truck-wreck PI bulletin genre; Big Jim invented |
| ATTORNEY | If the other guy had a lawyer, you would want Big Jim. | Anywhere | OAAA #1 Legal Services; truck-wreck PI bulletin genre; Big Jim invented |
| FAITH | A missed exit is not a sign from God. The next weigh station might be. | Anywhere | church-sign / gospel bulletin genre (CAM-style interstate presence) |
| FAITH | Pray for travelers. Then use your turn signal. | Anywhere | church-sign / gospel bulletin genre (CAM-style interstate presence) |
| FAITH | Church bake sale, next exit. Salvation and a cookie, in that order. | Anywhere | church-sign / gospel bulletin genre (CAM-style interstate presence) |
| FAITH | God is good. The coffee at the next truck stop is merely adequate. | Anywhere | church-sign / gospel bulletin genre (CAM-style interstate presence) |
| FAITH | Don't make me come down there. Signed, God. Also your safety director. | Anywhere | church-sign / gospel bulletin genre (CAM-style interstate presence) |
| FAITH | This is your sign. The actual church is the next exit. | Anywhere | church-sign / gospel bulletin genre (CAM-style interstate presence) |
| FAITH | Sunday service, seven in the morning. The doughnuts go first. | Anywhere | church-sign / gospel bulletin genre (CAM-style interstate presence) |
| FAITH | Eternity is a long haul. Pack accordingly. | Anywhere | church-sign / gospel bulletin genre (CAM-style interstate presence) |
| FAITH | Blessed are the peacemakers, and the folks who stay out of the left lane. | Anywhere | church-sign / gospel bulletin genre (CAM-style interstate presence) |
| FAITH | Got faith? Keep both hands on the wheel anyway. | Anywhere | church-sign / gospel bulletin genre (CAM-style interstate presence) |
| ODDITIES | World's largest rocking chair. You may not sit in it. Next exit. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | See the albino alligator. He is on break. The gift shop is not. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | Gravity hill ahead. Your truck already knew. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | Mystery house. Crooked floors. Straight prices. Nine ninety-five. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | Live rattlesnakes. Dead air conditioning. Next exit. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | Petrified wood, petrified staff, very lively gift shop. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | Cave tours, next exit. The crystals in the gift shop are glass. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | World's largest ketchup bottle. French fries not included. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | Two-headed calf, stuffed. One-headed cashier, not. Next exit. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | See the thing in a jar. We will not say which jar. Nine dollars. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | Miniature village, next exit. Your rig will not fit down Main Street. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| ODDITIES | Tornado museum, next exit. Step inside the storm cellar. | Anywhere | mystery-spot / giant-object / reptile-farm tourist-trap boards |
| TRUCKER | Showers with actual hot water. We are as surprised as you are. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | Truck parking, next exit. One spot left, behind the dumpster. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | Diesel and a hot dog that's been on the roller grill since Tuesday. Next exit. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | We put out cones for truck parking. Cars park in them anyway. Next exit. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | Tire shop that does not flinch at your recaps. Next exit. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | Bugs on the windshield? Free squeegee with every fill-up. Next exit. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER (KILLED) | Lumper service, next warehouse. Bring cash and patience, not in that order. | KILLED | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | CB shop, next exit. New antennas, and a guy who will talk your ear off. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | Reefer repair. If it is warm, we can tell from here. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | The lot has spaces. They are occupied by people who said they would only be a minute. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | Fuel desk open all night. The smile closes at ten. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | Need a shower, a stall, and a twenty-minute lie-down. We can do two of those. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| TRUCKER | We buy wrecks, runners, and whatever is smoking behind you. Cash today. | Anywhere | truck-stop service OOH (showers, parking, DEF, tire, lumper) |
| RADIO | AM radio, this hour: farm report, funeral notices, and a song you forgot you loved. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | Gospel hour on the local AM. The preacher is selling a tent, not a timeshare. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | Your local station: three songs, two ads, and a birthday shout-out for someone named Dale. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | Classic country all night. We play the hits and the ones the hits replaced. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | AM trucking radio. Static included at no extra charge. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | The station that plays only driving songs. You are the whole audience. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | Tune us in. Tune the other guy out. All request, no sleep. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | Overnight trucker radio. Road reports and old country till sunrise. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | Ten thousand watts of somebody's uncle with a stack of records. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | If your radio still has a knob, we still have a tower. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | Weather, crop reports, and a hymn at sunrise. You know the station. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | All truck, all night, all the same three commercials. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| RADIO | Keep it here. The next station is somebody's talk show and a car dealership. | Anywhere | regional AM/FM station frequency+format boards (no real call signs) |
| TRAVEL_PLAZA | Love's ahead. Diesel, a shower, and a coffee that will keep you legal for one more state. | Anywhere | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | Sheetz next exit. Made-to-order, open late, and somehow always has a line. | States ['PA','OH','WV','MD','VA','NC','MI'] (MOVED off Anywhere) | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | Wawa, next exit. Hoagies, coffee, and a parking lot that thinks it is a city. | States ['FL','NJ','PA','VA','MD','DE'] (MOVED off Anywhere) | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | RaceTrac next exit. Fuel, drinks, and a bathroom you will actually use. | States ['AL','AR','FL','GA','KY','LA','MS','NC','SC','TN','TX','VA'] (MOVED off Anywhere) | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | Pilot next exit. Parking if you are lucky. Coffee if you are desperate. | Anywhere | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | Travel center: showers, diesel, and a gift shop selling hats you already own. | Anywhere | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | Motel vacancy. Free ice. Free Wi-Fi. Free regret about the mattress. | Anywhere | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | Chain hotel, next exit. Continental breakfast starts when the waffle iron wakes up. | Anywhere | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | Cracker Barrel, next exit. Rocking chairs out front, biscuits inside. | States South/Midwest (MOVED off Anywhere) | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | Burger drive-thru, next exit. The bag is small. The line is not. | Anywhere | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | Exit food: burgers, fries, and a soda the size of a fuel can. | Anywhere | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| TRAVEL_PLAZA | Truck parking and a sit-down special. The special is that they still have parking. | Anywhere | OAAA hotels/QSR + Love's MegaBrands #46; Sheetz/Wawa/RaceTrac/Pilot nominative original copy |
| POP_CULTURE | Now showing: a movie about a truck. You are living the sequel. | Anywhere | dated theatrical/streaming promo register (Universal/Disney OOH rotates; not permanent franchise-country) |
| POP_CULTURE | Coming soon to the drive-in: a movie about a truck. You've seen the real thing. | Anywhere | dated theatrical/streaming promo register (Universal/Disney OOH rotates; not permanent franchise-country) |
| POP_CULTURE | Weekend double feature at the drive-in. Windows up if it rains. Windows down if it smells. | Anywhere | dated theatrical/streaming promo register (Universal/Disney OOH rotates; not permanent franchise-country) |
| POP_CULTURE | Now playing: something with explosions. Popcorn is extra. | Anywhere | dated theatrical/streaming promo register (Universal/Disney OOH rotates; not permanent franchise-country) |
| POP_CULTURE | Coming Friday: the one with the car chase. Please do not practice on this interstate. | Anywhere | dated theatrical/streaming promo register (Universal/Disney OOH rotates; not permanent franchise-country) |
| POP_CULTURE | Matinee special. Matinee is when you should be sleeping. We know. | Anywhere | dated theatrical/streaming promo register (Universal/Disney OOH rotates; not permanent franchise-country) |
| POP_CULTURE | Streaming now, and somehow also on a billboard. Eyes on the road. | Anywhere | dated theatrical/streaming promo register (Universal/Disney OOH rotates; not permanent franchise-country) |
| POP_CULTURE | Now showing: a comedy about a road trip. You already know how it ends. | Anywhere | dated theatrical/streaming promo register (Universal/Disney OOH rotates; not permanent franchise-country) |
| POP_CULTURE | Coming soon: a documentary about highways. You could have narrated it. | Anywhere | dated theatrical/streaming promo register (Universal/Disney OOH rotates; not permanent franchise-country) |
| POP_CULTURE | Drive-in movies, weekends only. Two features for one ticket. | Anywhere | dated theatrical/streaming promo register (Universal/Disney OOH rotates; not permanent franchise-country) |
| BIG_BUCKS | Big Buck's. The beaver has a restroom. You have a bladder. Race is on. One hundred twenty miles. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | Kolaches at Big Buck's. You do not know what that is. You will. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | The beaver says the coffee is fresh. The beaver says a lot of things. Eighty miles. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | Big Buck's jerky wall: taller than your trailer is long. One hundred miles. Stretch. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | Cleanest floors in the state. You will take your boots off in the parking lot. You will not. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | Beaver nuggets, beaver soda, beaver everything. Your cardiologist has left the group chat. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | One hundred forty miles to a bathroom you will photograph. Do not photograph it. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | Big Buck's: so many snacks the cart needs a CDL. Next few exits, then a few more. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | The beaver is judging your fuel choice. Diesel is not on the menu. Drop the trailer. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | Big Buck's gift wall. You will buy a shirt. You will wear it ironically. You will mean it. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | Hold it like you mean it. Forty more miles. The beaver believes in you, mostly. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| BIG_BUCKS | They have a car wash for cars. They have a dream for you. Big Buck's, keep holding. | Big Buck's approach pool only | Buc-ee's countdown / restroom / food-wall register; original parody; approach-only |
| CORRIDOR I-90 | Cleveland ahead. The Rock and Roll Hall of Fame sits on the lake. Chuck Berry, Aretha Franklin, and a glass pyramid you can actually visit. | Approaching ['cleveland_oh_us'] | Rock & Roll Hall of Fame, Cleveland — paying museum on I-90 |
| CORRIDOR I-90 | Mitchell, South Dakota -- the Corn Palace is a real building they redecorate with corn. You may look. The pigeons already did. | States ['SD'] | World's Only Corn Palace, Mitchell SD — I-90 exits 330/332 |
| CORRIDOR I-90 | Minnesota. The Spam Museum is a real place they built for a canned lunch. Samples included. The trailer is not. | States ['MN'] | Spam Museum, Austin MN on I-90 — paying attraction |
| CORRIDOR I-95 | Virginia peanuts, next exit. Cooked in the shell. Your cab will smell like a ballpark for a week. | States ['VA'] | produce-stand interstate boards (not See Rock City) |
| CORRIDOR I-10 | San Antonio ahead. Fiesta in the spring, Tejano all year. The Alamo does not take eighteen-wheelers. | Approaching ['san_antonio_tx_us'] | I-10 south Texas Tejano/Spanish radio + tourism OOH |
| CORRIDOR I-10 | New Orleans ahead. Preservation Hall still sells a seat for the jazz. Leave the trailer off the Quarter. | Approaching ['new_orleans_la_us'] | Preservation Hall, New Orleans — ticketed jazz venue |
| CORRIDOR I-10 | Cajun country. Boudin, cracklins, and a drive-thru that does not need a window. Next exit. | States ['LA'] | I-10 Acadiana food boards |
| CORRIDOR I-15 | Las Vegas ahead. Another casino, another buffet bigger than your trailer. The odds are not. | Approaching ['las_vegas_nv_us'] | I-15 casino approach OOH (OK tribal / NV Strip-Reno) |
| CORRIDOR I-40 | Memphis ahead. Graceland is a real house with a real ticket line. Elvis lived there. The jumpsuits are in the museum. | Approaching ['memphis_tn_us'] | ticketed Memphis/Nashville music tourism (not Music Highway state signs) |
| CORRIDOR I-40 | Oklahoma City ahead. Casino billboards outnumber the cattle. You have been warned. | Approaching ['oklahoma_city_ok_us'] | I-40 casino approach OOH (OK tribal / NV Strip-Reno) |
| CORRIDOR I-40 | Memphis. Beale Street still sells a ticket. The freight uses a different door. | Approaching ['memphis_tn_us'] | ticketed Memphis/Nashville music tourism (not Music Highway state signs) |
| CORRIDOR I-40 | Nashville ahead. The Grand Ole Opry still sells a ticket. Bring a song or bring freight. They take both. | Approaching ['nashville_tn_us'] | ticketed Memphis/Nashville music tourism (not Music Highway state signs) |
| CORRIDOR I-40 | Albuquerque ahead. Red chile, green chile, and a sky that does not quit. Fuel up. | Approaching ['albuquerque_nm_us'] | NM chile / tourism boards on I-40 |
| CORRIDOR I-80 | Reno ahead. Biggest Little City, and the neon starts early. Cash the bonus, not the truck. | Approaching ['reno_nv_us'] | I-80 casino approach OOH (OK tribal / NV Strip-Reno) |
| CORRIDOR I-80 | Iowa Eighty, the world's largest truck stop, is on this road. Parking is a competitive sport. So is the food court. | States ['IA'] | Iowa 80 Truckstop, Walcott IA on I-80 |
| CORRIDOR I-70 | Kansas sky, as advertised. The Oz Museum is a few exits off this road in Wamego. Ruby slippers not required. | States ['KS'] | OZ Museum, Wamego KS — documented I-70 billboards |
| CORRIDOR I-70 | Saint Louis ahead. The Gateway Arch is the big one. You may look. The trailer stays on this side of the river. | Approaching ['st_louis_mo_us'] | Gateway Arch tourism, St. Louis I-70 approach |
| CORRIDOR I-44 | Tulsa ahead. Casino lights off the right. Don't bet the load. | Approaching ['tulsa_ok_us'] | I-44 casino approach OOH (OK tribal / NV Strip-Reno) |
| CORRIDOR I-44 | Saint Louis ahead. Chuck Berry's Blueberry Hill is a real room. The duck walk is not a traffic pattern. | Approaching ['st_louis_mo_us'] | Blueberry Hill / Chuck Berry room, Delmar Loop — paying venue |
| CORRIDOR I-35 | Laredo ahead. Tejano on the AM and the river just south. Keep the accordion, skip the sightseeing detour. | Approaching ['laredo_tx_us'] | I-35 south Texas Tejano/Spanish radio + tourism OOH |
| CORRIDOR I-35 | San Antonio ahead. Tejano weekend on the AM. Conjunto is a dance hall and this highway. | Approaching ['san_antonio_tx_us'] | I-35 south Texas Tejano/Spanish radio + tourism OOH |
| CORRIDOR I-35 | Oklahoma City ahead. Native casino country. The boards started a hundred miles ago. | Approaching ['oklahoma_city_ok_us'] | I-35 casino approach OOH (OK tribal / NV Strip-Reno) |
| CORRIDOR I-35 (KILLED) | McAllen ahead. Tejano country. The towers never sleep and neither does the dance hall. | KILLED (I-35 does not reach McAllen) | I-35 south Texas Tejano/Spanish radio + tourism OOH |
| CORRIDOR I-35 | Fort Worth ahead. Billy Bob's Texas is a real honky-tonk with a zip code. Bob Wills already got the other board. | Approaching ['fort_worth_tx_us'] | Billy Bob's Texas, Fort Worth — paying honky-tonk |
| CORRIDOR I-35 | Waco ahead. West, Texas, is kolache country. The bakery has been stopping traffic since the interstate was new. | Approaching ['waco_tx_us'] | West TX kolache stands on I-35 (Czech Stop genre); original copy |
| CORRIDOR I-5 | Seattle ahead. The museum of pop culture is the colorful blob by the Needle. Jimi Hendrix is inside; the rain is not. | Approaching ['seattle_wa_us'] | MoPOP Seattle — paying museum by Space Needle |
| CORRIDOR I-5 | Buck Owens' Crystal Palace is a real room in Bakersfield. The Sound was born here. The freight just passes through. | States ['CA'] | Buck Owens' Crystal Palace, Bakersfield — paying venue |
| CORRIDOR I-65 | Nashville, Music City. The Ryman Auditorium is the mother church. Hats off, then back on the interstate. | Approaching ['nashville_tn_us'] | ticketed Memphis/Nashville music tourism (not Music Highway state signs) |
| CORRIDOR I-75 | Georgia peaches, next few exits. The stands are real. The claims about whose are best are advertising. | States ['GA'] | produce-stand interstate boards (not See Rock City) |
| CORRIDOR I-75 | Florida citrus, next few exits. The bags are heavy. The claims about fresh are mostly true. | States ['FL'] | produce-stand interstate boards (not See Rock City) |
| CORRIDOR I-75 | Horse country. The Kentucky Horse Park is a real farm with a hall of fame. Your trailer is not invited to the paddock. | States ['KY'] | Kentucky Horse Park — paying attraction north of Lexington on I-75 |
| CORRIDOR I-94 | Wisconsin. Cheese, really good cheese, and a dairy billboard that has been up since your last inspection. | States ['WI'] | I-94 corridor paying board / tourism or genre OOH |
| CORRIDOR I-94 | Milwaukee ahead. The Harley-Davidson Museum is a real building. The bikes inside are not street-legal, and neither is your trailer in the lobby. | Approaching ['milwaukee_wi_us'] | Harley-Davidson Museum, Milwaukee — paying, I-94 |
| CORRIDOR I-81 | Bristol, on the state line. The Birthplace of Country Music Museum is a real hall. Carter Family country starts here. | States ['TN', 'VA'] | Birthplace of Country Music Museum, Bristol TN/VA — Smithsonian affiliate |
| CORRIDOR I-64 | Louisville ahead. They make the bats here. The Louisville Slugger Museum is the giant one you cannot miss. | Approaching ['louisville_ky_us'] | Louisville Slugger Museum & Factory — paying, I-64 |
| CORRIDOR I-4 | Orlando ahead. The theme parks are off this road and not for freight. Fuel up, look once, keep going. | Approaching ['orlando_fl_us'] | I-4 Orlando theme-park approach tourism OOH; no Disney slogans |
| CORRIDOR I-45 | Houston ahead. Space Center Houston is a real room they flew from. The trailer stays on the planet. | Approaching ['houston_tx_us'] | Space Center Houston — I-45 tourism OOH |
