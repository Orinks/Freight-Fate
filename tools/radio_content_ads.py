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
)
