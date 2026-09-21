"""The shared radio ad rotation: fictional businesses, one spot each.

Split out of radio_content_plan.py to keep every file under the repo's
1000-line cap. Pure data, no I/O; the import surface stays
``tools.radio_content_plan``, which re-exports everything here.

Rules baked into this pool:
- Every business is fictional; no real brands.
- Exactly one CB mention in the whole rotation (the chrome-and-
  electronics spot), per owner ruling: modern trucks, modern gear.
- Ad voices never overlap station casting, primary or fallback, so a
  station host is never heard reading a commercial. The ad bench is a
  small cast of voices from the owner's real ElevenLabs account roster,
  reused across spots the way real regional radio reuses a handful of
  VO artists.
- Scripts run 55-75 words (about twenty to thirty seconds read), each
  with a concrete benefit, and ``formats`` lists the STATION_PLAYLISTS
  pools the spot may air on (never "route": the Roadhouse draws no ads).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdPlan:
    key: str
    business: str
    voice: str
    script: str
    formats: tuple[str, ...]


AD_PLAN: tuple[AdPlan, ...] = (
    AdPlan(
        key="ad_red_hawk_travel_centers",
        business="Red Hawk Travel Centers",
        voice="Roger",
        script=(
            "Red Hawk Travel Centers, the big red wing on the big blue "
            "sign. Hot showers that stay hot, parking that's actually "
            "striped for a seventy-footer, and a griddle that never "
            "cools. Reserve a spot from the road and it's still yours "
            "after dark, guaranteed, with pull-through fuel lanes that "
            "get you pumping in minutes. Fuel up, wash up, roll out. Red "
            "Hawk Travel Centers, at the exits drivers actually talk "
            "about."
        ),
        formats=("country", "classic_rock", "blues", "oldies", "tejano", "jazz"),
    ),
    AdPlan(
        key="ad_dellas_blue_plate",
        business="Della's Blue Plate Diner",
        voice="Alexandra",
        script=(
            "Della's Blue Plate Diner says a driver ate here before you "
            "were born, and the meatloaf hasn't changed since. Chicken "
            "fried steak, bottomless coffee, and pie that leaves with "
            "half the parking lot. Order the driver's plate and you're "
            "fed, refilled, and rolling again inside half an hour, with "
            "a slice boxed for mile two hundred. Look for the blue neon "
            "plate off the interstate. Della's. Come hungry, leave happy."
        ),
        formats=("country", "oldies", "gospel", "blues"),
    ),
    AdPlan(
        key="ad_ironline_tire",
        business="Ironline Tire and Retread",
        voice="Archer",
        script=(
            "A blowout doesn't check your schedule first. Ironline Tire "
            "and Retread runs round-the-clock roadside service, steer to "
            "trailer, with casings inspected by people who've mounted a "
            "million of them. One call puts a service truck on your "
            "shoulder inside the hour on most major corridors, and the "
            "invoice says what the phone quote said. Ironline. Get "
            "rolling, stay rolling."
        ),
        formats=("country", "classic_rock", "blues", "tejano", "jazz"),
    ),
    AdPlan(
        key="ad_bearclaw_diesel",
        business="Bearclaw Diesel Treatment",
        voice="Roger",
        script=(
            "Cold mornings, long grades, cheap fuel from that one card "
            "stop you regret. Your injectors forgive nothing. One bottle "
            "of Bearclaw Diesel Treatment every fill keeps the fuel "
            "clean, the burn even, and the miles per gallon honest. "
            "Drivers tell us the same story: easier starts, smoother "
            "pulls, and money spent on miles instead of shop time. "
            "Bearclaw. Feed the bear, not the shop."
        ),
        formats=("country", "classic_rock", "blues"),
    ),
    AdPlan(
        key="ad_meridian_freight_hiring",
        business="Meridian Freight Lines",
        voice="Janet",
        script=(
            "Meridian Freight Lines is hiring company drivers and owner "
            "operators. Late-model equipment, no forced dispatch, and "
            "home time that's written down, not whispered. Orientation "
            "is paid, the rider and pet policy starts day one, and your "
            "dispatcher knows your name by the second load. Talk to a "
            "recruiter who's actually held a wheel. Meridian Freight "
            "Lines. Drive for people who remember what it's like."
        ),
        formats=("country", "classic_rock", "gospel", "tejano", "blues", "jazz"),
    ),
    AdPlan(
        key="ad_wagon_wheel_inn",
        business="Wagon Wheel Motor Inn",
        voice="Alexandra",
        script=(
            "When the sleeper's too small and the night's too long, the "
            "Wagon Wheel Motor Inn keeps truck parking out back, a real "
            "mattress up front, and checkout late enough to matter. Ask "
            "for the driver rate and breakfast rides along free, with a "
            "wake-up call that keeps calling until you actually answer. "
            "Blackout curtains, strong water pressure, no fuss. The "
            "Wagon Wheel. Park it, rest it, earn it back tomorrow."
        ),
        formats=("country", "blues", "oldies", "night"),
    ),
    AdPlan(
        key="ad_loadlasso_app",
        business="LoadLasso",
        voice="Jade",
        script=(
            "Deadhead miles pay nobody. LoadLasso puts live freight on "
            "your phone, rates up front, brokers scored by drivers like "
            "you. Post your empty once and matched loads come to you, "
            "with the slow payers flagged in red before you ever dial. "
            "Book the load, skip the phone tag, get rolling loaded. "
            "LoadLasso, on your app store. Rope the good ones."
        ),
        formats=("country", "classic_rock", "tejano", "synthwave"),
    ),
    AdPlan(
        key="ad_black_kettle_coffee",
        business="Black Kettle Coffee",
        voice="Jade",
        script=(
            "Black Kettle Coffee is roasted for the long haul. Dark, "
            "smooth, and strong enough to introduce itself. It's a slow "
            "roast in small batches, so the last cup out of the thermos "
            "tastes like the first one in. Find the black kettle on the "
            "shelf at travel centers coast to coast, or fill up at the "
            "counter. Black Kettle. The night shift's oldest friend."
        ),
        formats=("night", "jazz", "blues", "oldies", "country"),
    ),
    AdPlan(
        key="ad_granite_shield_insurance",
        business="Granite Shield Insurance",
        voice="Archer",
        script=(
            "Your authority, your truck, your name on the door. Granite "
            "Shield Insurance covers owner operators with plain-language "
            "policies and adjusters who answer at the dock, not next "
            "week. Bundle the tractor, the trailer, and the cargo and "
            "the premium comes down, with one renewal date instead of "
            "three surprises. Granite Shield. Solid under everything "
            "you haul."
        ),
        formats=("country", "classic_rock", "blues", "gospel", "jazz"),
    ),
    AdPlan(
        key="ad_silver_spray_wash",
        business="Silver Spray Truck Wash",
        voice="Alexandra",
        script=(
            "Bugs on the bumper, salt on the frame, shame on the mud "
            "flaps. Silver Spray Truck Wash runs brushless bays big "
            "enough for doubles, hand-finished wheels, and a shine you "
            "can check your teeth in. Most rigs are in and out in twenty "
            "minutes, with an undercarriage rinse that gets the road "
            "salt before it gets your frame. Silver Spray. The load's "
            "heavy, but the rig should gleam."
        ),
        formats=("country", "classic_rock", "tejano", "oldies"),
    ),
    AdPlan(
        key="ad_silver_stack_electronics",
        business="Silver Stack Chrome and Electronics",
        voice="Roger",
        script=(
            "Silver Stack Chrome and Electronics stocks the whole modern "
            "cab: dash cams, electronic logs, GPS units, and yes, CB "
            "radios for the drivers who still like a voice on the "
            "airwaves. Plus enough polished chrome to signal aircraft. "
            "Every install is wired clean while you grab lunch, and it's "
            "guaranteed for as long as you own the truck. Silver Stack, "
            "next to the truck entrance. Light up your rig."
        ),
        formats=("country", "classic_rock", "blues", "oldies", "synthwave"),
    ),
    AdPlan(
        key="ad_weighahead_app",
        business="WeighAhead",
        voice="Janet",
        script=(
            "Rolling the dice at the scale house costs hours you don't "
            "have. WeighAhead reads your axle weights from certified "
            "lots and tells you before the platform does. Catch a heavy "
            "steer in the fuel lane, slide your tandems once, and cruise "
            "past the chicken coop with your day intact. Weigh once, "
            "roll easy. WeighAhead. Know your numbers."
        ),
        formats=("classic_rock", "country", "synthwave"),
    ),
    AdPlan(
        key="ad_roadforge_boots",
        business="Roadforge Boots",
        voice="Archer",
        script=(
            "Fourteen hours on your feet deserves better than cardboard "
            "soles. Roadforge Boots are stitched, not glued, oil-proof "
            "to the welt, and broken in by mile two. Dock to diner to "
            "fuel island, one pair does the whole day, and when the "
            "tread finally gives out, we'll resole them for the price of "
            "the postage. Roadforge. Built like you still fix things."
        ),
        formats=("country", "classic_rock", "blues", "gospel", "tejano"),
    ),
    AdPlan(
        key="ad_skyline_relay",
        business="Skyline Relay",
        voice="Janet",
        script=(
            "Out past the last cell bar, Skyline Relay keeps you "
            "reachable. Satellite messaging that rides your dash, "
            "check-ins for dispatch, and a help button that works in the "
            "middle of absolutely nowhere. One flat monthly rate covers "
            "the whole map, and the battery outlasts a full reset with "
            "room to spare. Skyline Relay. The whole map, covered."
        ),
        formats=("classic_rock", "synthwave", "night", "country", "jazz"),
    ),
    AdPlan(
        key="ad_milepost_ministries",
        business="Milepost Ministries",
        voice="Janet",
        script=(
            "Some loads weigh more than freight. Milepost Ministries "
            "keeps chapel doors open at truck stops across the country, "
            "with hot coffee, a quiet chair, and somebody who'll just "
            "listen. No collection plate, no sign-up sheet, just a light "
            "on and the door unlocked at any hour you finally park. "
            "Every driver welcome. Milepost Ministries. You're never "
            "hauling alone."
        ),
        formats=("gospel", "country", "blues", "night"),
    ),
    AdPlan(
        key="ad_quietcab_headsets",
        business="QuietCab Headsets",
        voice="Jade",
        script=(
            "Eleven hours of engine drone is a tax on your ears. "
            "QuietCab headsets cancel the roar, keep the road sounds you "
            "need, and hold a charge for a week of shifts. Calls come "
            "through clear enough to hear the shrug, and if the cab "
            "doesn't feel bigger after thirty days, send them back, no "
            "questions asked. QuietCab. Save your ears for the music."
        ),
        formats=("classic_rock", "synthwave", "country", "jazz", "night"),
    ),
    AdPlan(
        key="ad_truelane_navigation",
        business="TrueLane Navigation",
        voice="Jade",
        script=(
            "A car app doesn't know what thirteen foot six means until "
            "it's too late. TrueLane Navigation routes by your height, "
            "weight, and hazmat, warns you miles before the low bridge, "
            "and reroutes without drama. Closures and truck-legal "
            "detours come down live, so the route you leave with still "
            "works when you get there. TrueLane. Truck routes for actual "
            "trucks."
        ),
        formats=("country", "classic_rock", "tejano", "oldies", "synthwave", "jazz"),
    ),
    AdPlan(
        key="ad_smokestack_jerky",
        business="Smokestack Jerky Company",
        voice="Roger",
        script=(
            "Smokestack Jerky is smoked slow over real hickory, cut "
            "thick, and sealed the same week. Peppered, teriyaki, or hot "
            "enough to file a complaint. One bag rides shotgun farther "
            "than most codrivers, and the sampler pack settles the "
            "peppered-versus-teriyaki debate one mile marker at a time. "
            "Smokestack Jerky Company, at the register of every good "
            "fuel stop. Grab two."
        ),
        formats=("country", "classic_rock", "blues", "oldies", "tejano", "jazz", "night"),
    ),
    # Second wave, 2026-09-11: twenty more spots so a station's stopsets
    # take hours, not an afternoon, to come back round. Same voice bench.
    AdPlan(
        key="ad_copperline_parts",
        business="Copperline Truck Parts",
        voice="Archer",
        script=(
            "Copperline Truck Parts keeps the counter open around the "
            "clock, and the man behind it has turned wrenches on "
            "everything you drive. Brake shoes, filters, belts, marker "
            "lights, and the odd fitting nobody else stocks, pulled while "
            "you wait. Call ahead from the road and the parts are bagged "
            "with your name on them. Copperline Truck Parts, three doors "
            "down from the scale house. Fixed today, not Tuesday."
        ),
        formats=("country", "classic_rock", "blues", "tejano", "oldies"),
    ),
    AdPlan(
        key="ad_tallgrass_coop",
        business="Tallgrass Co-op",
        voice="Roger",
        script=(
            "The Tallgrass Co-op has been open since before the "
            "interstate, and the coffee pot has never been off. Feed, "
            "seed, fence wire, and diesel out back with room to swing a "
            "fifty-three. If you're hauling ag, the dock crew knows your "
            "paperwork better than you do, and the pie case in the office "
            "is not for show. Tallgrass Co-op. Turn where the grain "
            "elevator is."
        ),
        formats=("country", "gospel", "blues", "oldies"),
    ),
    AdPlan(
        key="ad_harbor_light_seafood",
        business="Harbor Light Seafood Shack",
        voice="Alexandra",
        script=(
            "Harbor Light Seafood Shack fries what the boats brought in "
            "this morning, not what the freezer remembers. Shrimp "
            "baskets, catfish plates, gumbo by the quart, and hushpuppies "
            "that leave before the check does. Truck parking runs along "
            "the seawall, and a to-go order is ready by the time you've "
            "backed in. Harbor Light. Follow the gulls off the causeway "
            "exit."
        ),
        formats=("blues", "jazz", "country", "tejano", "night"),
    ),
    AdPlan(
        key="ad_northstar_driver_health",
        business="Northstar Driver Health",
        voice="Janet",
        script=(
            "A lapsed medical card parks you faster than any weigh "
            "station. Northstar Driver Health does DOT physicals with no "
            "appointment, seven days a week, at clinics right off the "
            "truck routes. Sleep studies, vision checks, and the "
            "paperwork filed with the state before you're back in the "
            "cab. Bring your card, leave with a new one. Northstar Driver "
            "Health. Keep the card current and the wheels turning."
        ),
        formats=("country", "classic_rock", "gospel", "jazz", "tejano", "synthwave"),
    ),
    AdPlan(
        key="ad_prairie_mutual_credit",
        business="Prairie Mutual Credit Union",
        voice="Jade",
        script=(
            "Prairie Mutual Credit Union has financed trucks since trucks "
            "had running boards. Tractor loans with rates written in plain "
            "numbers, payments that flex with a slow month, and a loan "
            "officer who asks about your lanes before your credit score. "
            "Apply from your phone, sign at any branch, and drive off the "
            "lot the same week. Prairie Mutual. Your truck, your name, "
            "your terms."
        ),
        formats=("country", "classic_rock", "blues", "gospel", "oldies"),
    ),
    AdPlan(
        key="ad_ridgeback_mattress",
        business="Ridgeback Mattress",
        voice="Alexandra",
        script=(
            "Ridgeback builds mattresses for sleepers, not showrooms. Cut "
            "to fit your bunk, firm where your back needs it, cool enough "
            "for an idle-free summer night. Every one ships rolled to a "
            "terminal near you and unpacks in five minutes, and if you're "
            "not sleeping better after thirty nights, it goes back on us. "
            "Ridgeback Mattress. The best ten hours of your shift."
        ),
        formats=("country", "classic_rock", "night", "jazz", "synthwave", "blues"),
    ),
    AdPlan(
        key="ad_cinder_block_barbecue",
        business="Cinder Block Barbecue",
        voice="Roger",
        script=(
            "Cinder Block Barbecue smokes brisket for fourteen hours, the "
            "same as your clock. Sliced or chopped, ribs by the half rack, "
            "and sides the size of a hubcap. The lot fits doubles, the "
            "line moves, and they'll walk a tray out to the cab when you'd "
            "rather not lose your spot. Cinder Block Barbecue, where the "
            "smoke crosses the highway. You'll smell us before you see us."
        ),
        formats=("country", "blues", "classic_rock", "oldies", "tejano", "gospel"),
    ),
    AdPlan(
        key="ad_two_rivers_tarp",
        business="Two Rivers Tarp and Strap",
        voice="Archer",
        script=(
            "Two Rivers Tarp and Strap makes securement gear you can trust "
            "at seventy in a crosswind. Lumber tarps with real D-rings, "
            "four-inch straps rated and tagged, chains and binders that "
            "match the load, not the price. Buy at the counter, or off the "
            "truck that meets you at the mill. Two Rivers Tarp and Strap. "
            "Throw it, tie it, forget about it."
        ),
        formats=("country", "classic_rock", "blues"),
    ),
    AdPlan(
        key="ad_sunbreak_lenses",
        business="Sunbreak Driving Lenses",
        voice="Jade",
        script=(
            "Sunbreak makes glasses for people who face the sun for a "
            "living. Polarized for glare off wet pavement, amber for fog "
            "and dusk, and a clear night lens that takes the halo off "
            "oncoming lights. Frames that clear a headset, lenses that "
            "shrug off a dashboard summer, and a spare pair in the box. "
            "Sunbreak Driving Lenses. See the road the road is hiding."
        ),
        formats=("classic_rock", "country", "synthwave", "oldies", "jazz"),
    ),
    AdPlan(
        key="ad_casa_reyes_taqueria",
        business="Casa Reyes Taqueria",
        voice="Alexandra",
        script=(
            "Casa Reyes Taqueria never closes, and neither does the grill. "
            "Barbacoa on Sundays, tacos al pastor off the spit every "
            "night, and breakfast tacos from four in the morning for the "
            "drivers rolling out first. There's truck parking on the side "
            "lot and a walk-up window, so you never lock the cab. Casa "
            "Reyes, on the access road. Come as you are, leave full."
        ),
        formats=("tejano", "country", "blues", "night", "oldies"),
    ),
    AdPlan(
        key="ad_bluebonnet_western",
        business="Bluebonnet Western Wear",
        voice="Roger",
        script=(
            "Bluebonnet Western Wear stocks the hats, the jeans, and the "
            "belt buckles that fit a life spent sitting down. Boots in "
            "widths the mall never heard of, shirts with snaps that "
            "survive a truck stop washer, and a hat steamer running all "
            "day. Try it on, wear it out, and walk taller at the fuel "
            "desk. Bluebonnet Western Wear. Dressed for the long way home."
        ),
        formats=("country", "tejano", "oldies", "gospel"),
    ),
    AdPlan(
        key="ad_hearthside_pet_supply",
        business="Hearthside Pet Supply",
        voice="Janet",
        script=(
            "Your codriver has four legs and no complaints. Hearthside Pet "
            "Supply carries food, harnesses, seat covers, and travel bowls "
            "sized for a cab, at travel centers along the major routes. "
            "Order ahead and it's waiting at the counter with the receipt, "
            "so your dog gets dinner and you get back on the road. "
            "Hearthside Pet Supply. Because they ride along for free."
        ),
        formats=("country", "oldies", "gospel", "blues", "night"),
    ),
    AdPlan(
        key="ad_overdrive_cab_fitness",
        business="Overdrive Cab Fitness",
        voice="Jade",
        script=(
            "Overdrive Cab Fitness is a ten-minute workout you can do in a "
            "sleeper. Resistance bands that anchor to the bunk rail, a "
            "folding mat, and a voice coach on your phone who knows you're "
            "in a truck stop lot, not a gym. Loosen the back, wake up the "
            "legs, and drive the next stretch sitting straighter. Overdrive "
            "Cab Fitness. Stretch it out, then roll on."
        ),
        formats=("classic_rock", "synthwave", "country", "jazz"),
    ),
    AdPlan(
        key="ad_miller_vance_tax",
        business="Miller and Vance Tax",
        voice="Archer",
        script=(
            "Miller and Vance do taxes for drivers and nobody else. Per "
            "diem, quarterly filings, the truck payment, the fuel receipts "
            "you've been keeping in a coffee can. Send them a photo and "
            "it's entered the same day, and the audit letter, if one ever "
            "comes, goes to them and not to your kitchen table. Miller and "
            "Vance Tax. Keep more of every mile."
        ),
        formats=("country", "classic_rock", "blues", "jazz", "gospel"),
    ),
    AdPlan(
        key="ad_sawtooth_chains",
        business="Sawtooth Chains and Winter Gear",
        voice="Roger",
        script=(
            "Sawtooth Chains and Winter Gear sells tire chains you can "
            "hang in the dark with gloves on. Cam-lock sets sized to your "
            "tires, bungees that hold, a headlamp, and a mat to kneel on "
            "that isn't your good jacket. Stock up before the pass, not at "
            "the chain-up area. Sawtooth. When the sign says chains "
            "required, be the truck that's ready."
        ),
        formats=("country", "classic_rock", "blues"),
    ),
    AdPlan(
        key="ad_hilltop_family_restaurant",
        business="Hilltop Family Restaurant",
        voice="Alexandra",
        script=(
            "Hilltop Family Restaurant puts the Sunday buffet out at "
            "eleven and keeps it hot until the last plate. Fried chicken, "
            "greens cooked all morning, biscuits from scratch, and banana "
            "pudding somebody's grandmother approved. Drivers get a booth "
            "by the window where they can see the truck, and a thermos "
            "filled for the road. Hilltop Family Restaurant. Sit a spell, "
            "then we'll send you on."
        ),
        formats=("gospel", "country", "oldies", "blues"),
    ),
    AdPlan(
        key="ad_glassline_windshield",
        business="Glassline Mobile Windshield",
        voice="Archer",
        script=(
            "One rock at seventy and the whole windshield's a spiderweb by "
            "lunch. Glassline Mobile Windshield comes to the truck stop, "
            "the terminal, or the shoulder, fixes a chip in twenty "
            "minutes, and swaps a full glass before your break's over. "
            "Every replacement is DOT-rated and comes with a warranty that "
            "rides with the truck. Glassline. Clear glass, same day, where "
            "you're parked."
        ),
        formats=("country", "classic_rock", "blues", "tejano", "jazz", "synthwave"),
    ),
    AdPlan(
        key="ad_velvet_room",
        business="The Velvet Room",
        voice="Janet",
        script=(
            "The Velvet Room is a supper club two blocks off the truck "
            "route, with live jazz every night from nine and a kitchen "
            "that serves until one. No cover with a valid CDL, a quiet "
            "corner table if you want one, and a lot out back with room "
            "to leave the trailer on. Dress code is clean and awake. The "
            "Velvet Room. Downtown, after the loads are done."
        ),
        formats=("jazz", "night", "blues", "oldies"),
    ),
    AdPlan(
        key="ad_pulse_arcade_bar",
        business="Pulse Arcade Bar",
        voice="Jade",
        script=(
            "Pulse Arcade Bar keeps sixty cabinets from the eighties lit "
            "all night, a synth set on the sound system, and a mocktail "
            "list as long as the beer one. Two hours of pinball resets a "
            "brain better than another cup of coffee, and the lot down the "
            "street lets a tractor sit until sunrise. Pulse Arcade Bar, "
            "off the strip. Insert coin, forget the clock."
        ),
        formats=("synthwave", "night", "classic_rock", "jazz"),
    ),
    AdPlan(
        key="ad_late_shift_pharmacy",
        business="Late Shift Pharmacy",
        voice="Janet",
        script=(
            "Late Shift Pharmacy fills prescriptions at three in the "
            "morning, because three in the morning is when you're there. "
            "Transfers from any pharmacy in the country, over-the-counter "
            "shelves stocked for a cab, and a pharmacist who'll walk out "
            "to the lot if the cold is that bad. Drive-through lanes tall "
            "enough for a tractor. Late Shift Pharmacy. Open when the road "
            "is."
        ),
        formats=("night", "country", "jazz", "blues", "oldies"),
    ),
)
