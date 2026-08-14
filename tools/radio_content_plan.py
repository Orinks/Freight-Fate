"""Declarative content plan for every fictional Freight Fate station.

Pure data, no I/O: casting, host scripts, station IDs, jingle prompts, the
shared ad pool, the song batches, and the imaging SFX prompts. Consumed by
tools/generate_radio.py at build time and by the copy tests; nothing here
runs in the shipped game.

Conventions (the asset contract):
- ``STATIONS`` is keyed by content key -- the value the catalog's ``host``
  field will carry. Host clips become ``host_<key>_NN.ogg``, produced
  jingles ``id_<key>_01/02``, and the spoken legal ID ``id_<key>_03``.
- Voice names are ElevenLabs premade/library display names. Casting is
  one to one: no two stations share a primary voice, no fallback is
  another station's primary, and no fallback name appears in two
  stations' lists, so any fallback firing still never merges two hosts.
  Ad voices are disjoint from ALL station casting (primary and
  fallback): a station host never reads a commercial on the dial.
- Ad keys are ``ad_<slug>``; ``formats`` lists the STATION_PLAYLISTS pools
  the spot may air on (never "route": the Roadhouse draws no ads).
- Song keys follow the shipped catalog: ``radio_<pool>_<slug>``, with the
  historical stems ``radio_rock_`` for classic_rock and ``radio_night_``
  for the Night Line vocal pool.

Everything in ``host_lines``, ``id_lines``, and ad ``script`` fields is
player-facing spoken text for blind players: plain road language, no key
or menu names, no dates, no weather promises, no real brands.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StationPlan:
    station_id: str  # catalog station id (radio_catalog.json "id")
    name: str  # catalog display name, spoken verbatim in the legal ID
    voice: str  # ElevenLabs display name, unique per station
    voice_fallbacks: tuple[str, str]  # preference order if the primary is gone
    persona: str  # delivery note for the TTS pass
    playlist: str  # STATION_PLAYLISTS pool
    host_lines: tuple[str, ...]  # 8 spoken break lines
    id_lines: tuple[str, ...]  # spoken legal-style IDs (>= 1)
    jingle_prompts: tuple[tuple[str, str], ...]  # (asset_key, Eleven Music prompt)


# The ad rotation and song batches live in radio_content_ads.py and
# radio_content_pools.py (split to honor the 1000-line file cap); this
# module stays the import surface.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from radio_content_ads import AD_PLAN, AdPlan  # noqa: E402
from radio_content_pools import SONG_PLAN, SongPlan  # noqa: E402

__all__ = [
    "AD_PLAN",
    "AdPlan",
    "SFX_PROMPTS",
    "SONG_PLAN",
    "STATIONS",
    "SongPlan",
    "StationPlan",
]


STATIONS: dict[str, StationPlan] = {
    "roadhouse": StationPlan(
        station_id="route_playlist",
        name="Freight Fate Roadhouse",
        voice="Clyde",
        voice_fallbacks=("Brian", "Drew"),
        persona="Warm gravelly daytime trucker DJ, big grin, coast-to-coast friend",
        playlist="route",
        host_lines=(
            "You're rolling with the Freight Fate Roadhouse, coast to coast, "
            "wherever the load takes you. Keep it between the lines, driver.",
            "That rig of yours sounds hungry for miles. More music coming "
            "right up on the Roadhouse.",
            "This one goes out to everybody staring down a long white line "
            "this morning. Hammer down, stay safe.",
            "Roadhouse radio, friend of the working driver. Check your "
            "mirrors, check your coffee, and roll on.",
            "If you're hauling through weather out there, take her slow. The "
            "Roadhouse will keep you company all the way.",
            "From the yard to the receiver and every mile between, this is "
            "the Freight Fate Roadhouse. Back to the music.",
            "Clyde here at the Roadhouse, pouring a fresh cup and pulling "
            "another stack of songs. You bring the miles, I'll bring the music.",
            "Big rigs, box trucks, and everybody in between, the Roadhouse "
            "rides shotgun with all of you. Let's roll.",
        ),
        id_lines=("F-F-R, Freight Fate Roadhouse, coast to coast.",),
        jingle_prompts=(
            (
                "id_roadhouse_01",
                "Ten second Americana radio station jingle, warm male harmony "
                "singers singing 'Freight Fate Roadhouse', acoustic guitar and "
                "harmonica flourish, big friendly finish",
            ),
            (
                "id_roadhouse_02",
                "Twelve second country rock radio sweeper, gravelly band vocals "
                "singing 'the Freight Fate Roadhouse, coast to coast', slide "
                "guitar lick, truck horn accent, clean ending",
            ),
        ),
    ),
    "nightline": StationPlan(
        station_id="ff-night-line",
        name="Freight Fate Night Line",
        voice="Serena",
        voice_fallbacks=("Charlotte", "Matilda"),
        persona=(
            "Smoky, low, intimate late-night confidante; unhurried, confessional, "
            "adult in tone and always clean"
        ),
        playlist="night",
        host_lines=(
            "This is the Night Line. Come in close. The road's empty, the "
            "hour's late, and there's nowhere else I'd rather be.",
            "Some songs only make sense after midnight. I save them for you. "
            "Stay with me on the Night Line.",
            "I'll tell you a secret, driver. I love this shift. The world "
            "gets quiet enough to hear what matters.",
            "Mile after mile, it's just your headlights and my voice. I can "
            "live with that arrangement.",
            "You're not the only one awake out there. Every dark mile has "
            "somebody in it, and they're all listening with us.",
            "The Night Line, easing you through the small hours. Slow songs, "
            "low lights, no hurry at all.",
            "If the cab feels too big and empty tonight, turn me up a "
            "little. That's what I'm here for.",
            "Let the interstate hum its one long note, and I'll lay the "
            "songs down soft around it. Night Line, till the sun takes over.",
        ),
        id_lines=("F-F-N, Freight Fate Night Line, everywhere the dark roads go.",),
        jingle_prompts=(
            (
                "id_nightline_01",
                "Ten second late night radio jingle, hushed female jazz singer "
                "singing 'Freight Fate Night Line', brushed drums, upright bass, "
                "soft fade",
            ),
            (
                "id_nightline_02",
                "Twelve second smoky downtempo radio sweeper, low sultry vocal "
                "singing 'the Night Line, stay with me', warm electric piano, "
                "gentle tape echo, slow dissolve",
            ),
        ),
    ),
    "rawhide": StationPlan(
        station_id="krwl-dallas",
        name="The Rawhide 98.1",
        voice="Josh",
        voice_fallbacks=("Ethan", "Ryan"),
        persona="Big Texas swagger, young gun country DJ, boots-and-chrome bravado",
        playlist="country",
        host_lines=(
            "You're locked onto The Rawhide, ninety-eight one, Dallas. Real "
            "country for folks who work for a living.",
            "That's how we do it on The Rawhide. Boots dusty, chrome shiny, radio loud.",
            "If your trailer's heavy and your coffee's light, we'll even out "
            "the difference right here.",
            "This one goes out to the flatbed crowd tarping in the wind. "
            "The Rawhide's buying the next three minutes.",
            "A reefer driver called from the fuel island asking for more "
            "fiddle. Say less, partner.",
            "Turn it up, cowboy. There ain't a mile between here and the "
            "horizon this station can't shorten.",
            "The Rawhide 98.1, kicking dust on the competition. More country coming at you.",
            "Keep her between the fence posts, friend. We've got songs stacked to the sky.",
        ),
        id_lines=("K-R-W-Z, The Rawhide 98.1, Dallas.",),
        jingle_prompts=(
            (
                "id_rawhide_01",
                "Ten second country radio station jingle, male harmony singers "
                "singing 'The Rawhide, ninety eight point one', bright telecaster "
                "twang and fiddle stab, big finish",
            ),
            (
                "id_rawhide_02",
                "Twelve second outlaw country radio sweeper, swaggering female "
                "singer singing 'The Rawhide, Dallas country', bullwhip crack, "
                "pedal steel flourish, clean ending",
            ),
        ),
    ),
    "bigwheel": StationPlan(
        station_id="whwy-nashville",
        name="Big Wheel Country 104.5",
        voice="Grace",
        voice_fallbacks=("Emily", "Sarah"),
        persona="Warm Nashville sweetheart, easy southern charm, big-hearted",
        playlist="country",
        host_lines=(
            "Big Wheel Country, one oh four five, rolling out of Nashville "
            "with you wherever the load leads.",
            "This is Big Wheel Country, where the songs are about people "
            "like you, doing exactly what you're doing right now.",
            "You keep those eighteen wheels turning, sugar, and I'll keep "
            "the fiddle and steel coming.",
            "Music City's got a soft spot for drivers, and so do I. Stay with us.",
            "It's supper time somewhere on your route, darlin'. Here's one "
            "to go with whatever the special is.",
            "Somebody in Nashville wrote a song about a night just like this "
            "one. Let's go find it.",
            "You haul the freight, honey. We'll haul the feelings.",
            "The Big Wheel keeps on turning. Don't you touch that dial.",
        ),
        id_lines=("W-H-W-X, Big Wheel Country 104.5, Nashville.",),
        jingle_prompts=(
            (
                "id_bigwheel_01",
                "Ten second Nashville country radio jingle, sweet female harmony "
                "singing 'Big Wheel Country, one oh four five', fiddle and pedal "
                "steel swell, warm ending",
            ),
            (
                "id_bigwheel_02",
                "Twelve second country radio sweeper, full band vocals singing "
                "'Big Wheel Country keeps on turning', banjo roll, big major "
                "chord finish",
            ),
        ),
    ),
    "prairieline": StationPlan(
        station_id="kpln-kansas-city",
        name="Prairie Line 95.7",
        voice="Paul",
        voice_fallbacks=("Daniel", "Dave"),
        persona="Steady heartland anchor, plainspoken, dry warmth, no rush",
        playlist="country",
        host_lines=(
            "Prairie Line ninety-five seven, Kansas City, keeping you "
            "company across the long flat middle of everything.",
            "This is the Prairie Line, where the horizon's far and the "
            "songs go all the way out to meet it.",
            "Wheat on one side, beans on the other, and blacktop straight "
            "up the middle. Perfect radio country.",
            "This next singer grew up two gravel roads off the state "
            "highway, and you can hear it in every note.",
            "Steady hands, steady miles. We'll handle the soundtrack.",
            "There's no prettier sight than an open lane and a full tank. Here's a song for both.",
            "Kansas City barbecue and country gold, friend. One of those we "
            "can deliver straight through the radio.",
            "Set your mirrors and settle in. The Prairie Line runs long tonight.",
        ),
        id_lines=("K-P-N-L, Prairie Line 95.7, Kansas City.",),
        jingle_prompts=(
            (
                "id_prairieline_01",
                "Ten second heartland country radio jingle, male quartet singing "
                "'Prairie Line, ninety five seven', acoustic guitar and dobro, "
                "wide open ending",
            ),
            (
                "id_prairieline_02",
                "Twelve second country radio sweeper, warm mixed choir singing "
                "'Prairie Line country, Kansas City', harmonica sweep, gentle "
                "resolve",
            ),
        ),
    ),
    "bigsky": StationPlan(
        station_id="kbsk-billings",
        name="Big Sky Country 99.3",
        voice="Thomas",
        voice_fallbacks=("James", "Fin"),
        persona="Calm weathered mountain-west voice, unhurried, quietly proud",
        playlist="country",
        host_lines=(
            "Big Sky Country, ninety-nine three out of Billings. All that "
            "sky, and just enough radio to fill it.",
            "This is Big Sky Country. Up here the miles are long, the towns "
            "are small, and the songs mean it.",
            "Watch your grades and your gauges through the high country, "
            "driver. We'll be here the whole way down.",
            "Here's one for the driver chaining up alone at the top of the "
            "pass. Big Sky Country salutes you.",
            "Some stretches out here go an hour between mailboxes. That's "
            "not lonely, that's elbow room.",
            "Give the air horn a pull for the kids at the fence line. That never gets old.",
            "Mountains ahead, music on. That's about as good as a workday gets.",
            "Big Sky Country, Billings. Long may the diesel drum and the fiddle answer.",
        ),
        id_lines=("K-B-G-K, Big Sky Country 99.3, Billings.",),
        jingle_prompts=(
            (
                "id_bigsky_01",
                "Ten second mountain country radio jingle, high lonesome male "
                "voice singing 'Big Sky Country, ninety nine three', mandolin "
                "tremolo and fiddle, open air finish",
            ),
            (
                "id_bigsky_02",
                "Twelve second country radio sweeper, duet vocals singing 'Big "
                "Sky Country, Billings', acoustic strum builds to a wide major "
                "chord, echoing ending",
            ),
        ),
    ),
    "grind": StationPlan(
        station_id="wgrx-chicago",
        name="The Grind 97.9",
        voice="Arnold",
        voice_fallbacks=("Harry", "Sam"),
        persona="Gravel-voiced Chicago rock jock, blue-collar pride, zero polish",
        playlist="classic_rock",
        host_lines=(
            "The Grind, ninety-seven nine, Chicago. Rock and roll for people who actually work.",
            "You're on The Grind. The shift's long and the riffs are longer.",
            "Steel, freight, and guitars. That's the whole format, and it ain't broke.",
            "Third shift, first shift, whatever shift this is for you, The "
            "Grind clocks in when you do.",
            "This town was built by people hauling heavy things. Here's your theme music.",
            "Coffee black, amps up. Back to work.",
            "Somebody's got to move eighty thousand pounds through this "
            "city. Might as well be you, with the radio loud.",
            "The Grind never closes, driver. Neither does the interstate.",
        ),
        id_lines=("W-G-D-X, The Grind 97.9, Chicago.",),
        jingle_prompts=(
            (
                "id_grind_01",
                "Ten second classic rock radio jingle, gritty male rock vocals "
                "singing 'The Grind, ninety seven nine', crunchy power chords "
                "and a drum fill, hard stop",
            ),
            (
                "id_grind_02",
                "Twelve second hard rock radio sweeper, gang vocals shouting "
                "'The Grind, Chicago rocks', hammering guitar riff, cymbal "
                "crash ending",
            ),
        ),
    ),
    "desertrock": StationPlan(
        station_id="kdrt-phoenix",
        name="Desert Rock 101.5",
        voice="Callum",
        voice_fallbacks=("Liam", "Jeremy"),
        persona="Raspy sun-baked rock voice, laid-back menace, desert cool",
        playlist="classic_rock",
        host_lines=(
            "Desert Rock, one oh one five, Phoenix. Loud guitars for wide open country.",
            "You're riding with Desert Rock, where the pavement shimmers "
            "and the solos stretch for miles.",
            "Saguaro on the shoulder, semis in the mirror, and a riff that "
            "won't quit. That's the Valley.",
            "This next band cut everything live with the studio doors "
            "open. You can hear the desert leaking in.",
            "Mind the long grades and the runaway ramps out there, friend. The music will keep.",
            "Every mile of this state sounds better with drums behind it.",
            "A driver called from a gravel turnout outside Tucson and "
            "asked us to play it louder. Done and done.",
            "Stay sharp, stay loud. Desert Rock's got the rest.",
        ),
        id_lines=("K-D-R-Z, Desert Rock 101.5, Phoenix.",),
        jingle_prompts=(
            (
                "id_desertrock_01",
                "Ten second desert rock radio jingle, raspy male vocals singing "
                "'Desert Rock, one oh one five', fuzzed guitar slide and floor "
                "tom hits, dry abrupt ending",
            ),
            (
                "id_desertrock_02",
                "Twelve second stoner rock radio sweeper, low chanted vocals "
                "singing 'Desert Rock, Phoenix', heavy detuned riff, rattlesnake "
                "shaker accent, hard stop",
            ),
        ),
    ),
    "chrome": StationPlan(
        station_id="kchm-los-angeles",
        name="Chrome 106.3",
        voice="Domi",
        voice_fallbacks=("Gigi", "Jessica"),
        persona="Confident LA rock queen, glossy attitude, fast smile",
        playlist="classic_rock",
        host_lines=(
            "Chrome, one oh six three, Los Angeles. Polished loud and driven hard.",
            "This is Chrome. If it's got wheels and a heartbeat, we've got its soundtrack.",
            "Ten lanes wide and every one of them listening. Stay in yours, though.",
            "This one's for the night crew at the produce docks. Chrome "
            "doesn't forget who unloads this town.",
            "Nobody in this town eats until a truck shows up. Take a bow, driver.",
            "Legends cut these songs a few blocks from where you're rolling right now.",
            "Sunset in the mirrors, drums in the doors. That's the Chrome way.",
            "Keep it shiny out there. Chrome rides with you bumper to bumper.",
        ),
        id_lines=("K-H-R-Z, Chrome 106.3, Los Angeles.",),
        jingle_prompts=(
            (
                "id_chrome_01",
                "Ten second arena rock radio jingle, powerhouse female vocals "
                "singing 'Chrome, one oh six three', gated drums and glossy "
                "guitar harmonics, big finish",
            ),
            (
                "id_chrome_02",
                "Twelve second glam rock radio sweeper, layered vocals singing "
                "'Chrome, Los Angeles', talkbox guitar lick, crowd roar swell, "
                "clean button ending",
            ),
        ),
    ),
    "ridge": StationPlan(
        station_id="krdg-denver",
        name="The Ridge 103.7",
        voice="Patrick",
        voice_fallbacks=("Will", "Chris"),
        persona="Mile-high rock voice, energetic but grounded, loves the grades",
        playlist="classic_rock",
        host_lines=(
            "The Ridge, one oh three seven, Denver. Rock that starts a mile up and climbs.",
            "You're on The Ridge. Big air, big amps, and a grade ahead. "
            "Check your brakes and crank it.",
            "The morning push is over and the mountain's all yours, "
            "driver. Let's go make some altitude.",
            "Somebody called from the brake-check pullout just to say "
            "thanks for the drum solo. Anytime, friend.",
            "Take the mountain steady, driver. Gear down early and let the song do the racing.",
            "Every switchback deserves a drum fill. We time them the best we can.",
            "You haul it up, gravity hauls it down, and The Ridge plays through both.",
            "Rock from the top of the map. Stay on it.",
        ),
        id_lines=("K-R-I-J, The Ridge 103.7, Denver.",),
        jingle_prompts=(
            (
                "id_ridge_01",
                "Ten second mountain rock radio jingle, soaring male vocals "
                "singing 'The Ridge, one oh three seven', echoing guitar bends "
                "and tom rolls, summit-sized finish",
            ),
            (
                "id_ridge_02",
                "Twelve second classic rock radio sweeper, harmony vocals "
                "singing 'The Ridge, Denver's rock', chugging riff climbing key "
                "changes, cymbal swell ending",
            ),
        ),
    ),
    "sound": StationPlan(
        station_id="ksnd-seattle",
        name="The Sound 102.1",
        voice="River",
        voice_fallbacks=("Aria", "Alice"),
        persona="Laid-back Pacific Northwest voice, wry, unbothered, coffee-warm",
        playlist="classic_rock",
        host_lines=(
            "The Sound, one oh two one, Seattle. Rock that rolled in off the water and never left.",
            "You're tuned to The Sound. Ferries out there, freight out here, guitars everywhere.",
            "Evergreens, espresso, and power chords. We stack them in that order.",
            "A local band cut this next one in a basement that flooded "
            "twice. The song survived. It shows.",
            "Somewhere between the port and the pass, this next one's going to land just right.",
            "Keep your following distance friendly out there. There's plenty of song to go around.",
            "This city put a lot of loud, beautiful noise into the world. We're still spending it.",
            "The Sound rides with the load, driver. All the way to the dock.",
        ),
        id_lines=("K-S-D-X, The Sound 102.1, Seattle.",),
        jingle_prompts=(
            (
                "id_sound_01",
                "Ten second grunge-tinged rock radio jingle, moody male vocals "
                "singing 'The Sound, one oh two one', fuzzy guitar swell over "
                "rain-soft cymbals, feedback fade",
            ),
            (
                "id_sound_02",
                "Twelve second alternative rock radio sweeper, relaxed vocals "
                "singing 'The Sound, Seattle', jangly riff with a ferry horn "
                "accent, easy resolve",
            ),
        ),
    ),
    "delta": StationPlan(
        station_id="wdlt-memphis",
        name="The Delta 94.3",
        voice="Bill",
        voice_fallbacks=("Joseph", "George"),
        persona="Old Memphis bluesman, slow molasses drawl, seen everything twice",
        playlist="blues",
        host_lines=(
            "The Delta, ninety-four three, Memphis. Blues thick as river mud and twice as deep.",
            "You're on The Delta, where every twelve bars tells the truth.",
            "This music came up the river on barges and boxcars. Now it rides with you.",
            "For the driver counting dock doors in the dark right now, The "
            "Delta's got your next verse ready.",
            "If the road's wearing on you, friend, let somebody sing about it a while.",
            "It's past quitting time for everybody but us, friend. Good. "
            "The blues sounds better on overtime.",
            "Every mile you pull is a verse, driver. We just supply the chorus.",
            "Stay low, stay steady. The Delta's got you clear through the dark.",
        ),
        id_lines=("W-D-T-Q, The Delta 94.3, Memphis.",),
        jingle_prompts=(
            (
                "id_delta_01",
                "Ten second blues radio jingle, weathered male blues shout "
                "singing 'The Delta, ninety four three', slide guitar moan and "
                "a slow snare drag, smoky ending",
            ),
            (
                "id_delta_02",
                "Twelve second Memphis soul radio sweeper, gospel-tinged "
                "backing vocals singing 'The Delta, Memphis blues', horn stabs "
                "and tremolo guitar, warm fade",
            ),
        ),
    ),
    "bayou": StationPlan(
        station_id="wbyu-new-orleans",
        name="Bayou Soul 100.9",
        voice="Jessie",
        voice_fallbacks=("Charlie", "Glinda"),
        persona="Raspy New Orleans charmer, simmering and playful, calls everyone cher",
        playlist="blues",
        host_lines=(
            "Bayou Soul, one hundred point nine, New Orleans. Simmered slow and served warm.",
            "You found Bayou Soul, cher. Horns, gravy, and groove, all night long.",
            "This here music's got roux in it. Don't rush it and don't skim it.",
            "This next horn line simmered about forty years before "
            "anybody wrote it down. Taste and see.",
            "Mind them causeways and keep her easy, cher. The band will wait on you.",
            "The trumpet says what words can't. We let it talk plenty.",
            "Somewhere down the road there's a plate with your name on it. "
            "Music till you get there.",
            "Let the good times roll, driver. Bayou Soul keeps the pot warm.",
        ),
        id_lines=("W-B-Y-K, Bayou Soul 100.9, New Orleans.",),
        jingle_prompts=(
            (
                "id_bayou_01",
                "Ten second New Orleans soul radio jingle, brass band and "
                "raspy male vocals singing 'Bayou Soul, one hundred point "
                "nine', second line drum strut, trumpet flourish ending",
            ),
            (
                "id_bayou_02",
                "Twelve second swampy soul radio sweeper, call and response "
                "vocals singing 'Bayou Soul, New Orleans', clavinet groove and "
                "tuba bounce, joyful ending",
            ),
        ),
    ),
    "southernsoul": StationPlan(
        station_id="wsol-atlanta",
        name="Southern Soul 96.5",
        voice="Rachel",
        voice_fallbacks=("Lily", "Laura"),
        persona="Warm Atlanta soul queen, honeyed and maternal, easy laugh",
        playlist="blues",
        host_lines=(
            "Southern Soul, ninety-six five, Atlanta. Sweet tea for your ears, sugar.",
            "This is Southern Soul, where the horns are warm and the welcome's warmer.",
            "You've been carrying that load all day, baby. Let the music carry you a while.",
            "A driver called from a rest area and said this station "
            "sounds like her grandmother's kitchen. Sugar, that's the "
            "whole idea.",
            "Every one of these songs was somebody's whole heart. We handle them gently.",
            "Atlanta traffic will test your patience, honey. Breathe easy, "
            "we've got groove for the slow lanes too.",
            "Soul food for the long haul, and no reservations needed.",
            "Stay sweet and drive safe. Southern Soul's right here.",
        ),
        id_lines=("W-S-O-Z, Southern Soul 96.5, Atlanta.",),
        jingle_prompts=(
            (
                "id_southernsoul_01",
                "Ten second southern soul radio jingle, silky female vocals "
                "singing 'Southern Soul, ninety six five', warm horn section "
                "and electric piano, honeyed ending",
            ),
            (
                "id_southernsoul_02",
                "Twelve second soul radio sweeper, rich choir singing "
                "'Southern Soul, Atlanta', wah guitar and handclaps, uplifting "
                "major finish",
            ),
        ),
    ),
    "afterhours": StationPlan(
        station_id="wnah-nashville",
        name="Nashville After Hours 92.9",
        voice="Michael",
        voice_fallbacks=("Valentino", "Archer"),
        persona="Cool late-night jazz voice, dry wit, never above a murmur",
        playlist="jazz",
        host_lines=(
            "Nashville After Hours, ninety-two nine. The neon's off and the good stuff's on.",
            "This is Nashville After Hours. When the honky-tonks empty "
            "out, the real players stay and play.",
            "Brushed drums, upright bass, and a town that finally stopped talking. Perfect.",
            "Half past late, friend. From here on the coffee's optional. The music isn't.",
            "Somewhere a session man is still holding one last chord. We found the tape.",
            "Ease off the throttle a notch, friend. This next one deserves the scenic tempo.",
            "Late shift on the dial. Nashville After Hours keeps it smooth clear through.",
            "The city sleeps and the freight doesn't. Neither do we.",
        ),
        id_lines=("W-N-A-H, Nashville After Hours 92.9, Nashville.",),
        jingle_prompts=(
            (
                "id_afterhours_01",
                "Ten second late night jazz radio jingle, smooth crooner "
                "singing 'Nashville After Hours', muted trumpet answer, "
                "brushed snare, velvet fade",
            ),
            (
                "id_afterhours_02",
                "Twelve second cool jazz radio sweeper, hushed vocal group "
                "singing 'Nashville After Hours, ninety two nine', walking "
                "bass and piano fill, soft ride cymbal ending",
            ),
        ),
    ),
    "cruisingold": StationPlan(
        station_id="kgol-oklahoma-city",
        name="Cruisin' Gold 105.9",
        voice="Eric",
        voice_fallbacks=("Roger", "Mimi"),
        persona="Bright AM-gold showman, fast patter, grin you can hear",
        playlist="oldies",
        host_lines=(
            "Cruisin' Gold, one oh five nine, Oklahoma City! All the hits "
            "that never stopped shining.",
            "Hey hey, you're rolling with Cruisin' Gold, where every "
            "record's a keeper and every mile's a memory.",
            "Whitewalls, jukeboxes, and chrome for days. Climb aboard, "
            "good neighbor, the oldies are rolling.",
            "Here's to the driver who just let that little four-wheeler "
            "merge like a perfect gentleman. Cruisin' Gold saw that.",
            "That big rig of yours has a dance partner, friend. It's called the radio.",
            "We got a request for the one that goes doo-wop, doo-wop. "
            "Narrowed it down to forty records. Playing them all.",
            "Don't touch that dial, it's a classic too. More greats on the way.",
            "Cruisin' Gold, Oklahoma City, where the hits ride shotgun.",
        ),
        id_lines=("K-G-O-L, Cruisin' Gold 105.9, Oklahoma City.",),
        jingle_prompts=(
            (
                "id_cruisingold_01",
                "Ten second nineteen-sixties style AM radio jingle, bright "
                "doo-wop harmony group singing 'Cruisin' Gold, one oh five "
                "nine', handclaps and rolling piano, sparkling ending",
            ),
            (
                "id_cruisingold_02",
                "Twelve second oldies radio sweeper, cheerful jingle singers "
                "singing 'Cruisin' Gold, Oklahoma City', sock hop saxophone "
                "riff, chimes on the button",
            ),
        ),
    ),
    "gloryroad": StationPlan(
        station_id="wglr-birmingham",
        name="Glory Road 91.5",
        voice="Adam",
        voice_fallbacks=("Mark", "Dorothy"),
        persona="Warm Birmingham preacher cadence, uplifting Sunday-morning glow",
        playlist="gospel",
        host_lines=(
            "Glory Road, ninety-one five, Birmingham. Lifting spirits and lightening loads.",
            "This is Glory Road radio, friend. Whatever you're hauling, you don't haul it alone.",
            "A little singing helps the miles pass and the heart mend. We keep both coming.",
            "This one goes out to the choir of one singing behind a "
            "windshield somewhere eastbound. Glory Road hears you.",
            "Grace rides in the passenger seat, driver. The music just reminds you.",
            "Tired hands, take heart. There's a song up next that knows your name.",
            "Every sunrise is a fresh start and a full tank. Let's roll on gratitude today.",
            "Glory Road, Birmingham. Keep the faith and keep her rolling.",
        ),
        id_lines=("W-G-L-R, Glory Road 91.5, Birmingham.",),
        jingle_prompts=(
            (
                "id_gloryroad_01",
                "Ten second gospel radio jingle, full southern choir singing "
                "'Glory Road, ninety one five', Hammond organ swell and "
                "tambourine, triumphant amen ending",
            ),
            (
                "id_gloryroad_02",
                "Twelve second gospel radio sweeper, soulful lead with choir "
                "answering 'Glory Road, Birmingham', piano runs and "
                "handclaps, rising key change finish",
            ),
        ),
    ),
    "purotejano": StationPlan(
        station_id="ktjo-san-antonio",
        name="Puro Tejano 107.1",
        voice="Mateo",
        voice_fallbacks=("Antoni", "Giovanni"),
        persona=(
            "Bilingual San Antonio firecracker: Spanish colour with enough "
            "English that every sentence lands for an English-only listener"
        ),
        playlist="tejano",
        host_lines=(
            "Puro Tejano, one oh seven one, San Antonio. La música de aquí, the music of home.",
            "Ajúa! You're riding with Puro Tejano, where the accordion never takes a day off.",
            "Órale, driver, that eighteen-wheeler of yours has got rhythm. "
            "Let the cumbia prove it.",
            "Ya mero es hora de cenar, almost supper time somewhere down "
            "the road. Puro Tejano rides with you till the next good plate.",
            "Mi gente, keep those wheels rolling easy. The conjunto will "
            "carry you all the way to the dock.",
            "This next one is pura medicina, pure medicine for a long shift. Súbele, turn it up!",
            "A driver called in from Laredo just to say súbele. You heard "
            "him. We're turning it up.",
            "Gracias for riding with us, amigo. Puro Tejano, siempre contigo, always with you.",
        ),
        id_lines=("K-T-J-O, Puro Tejano 107.1, San Antonio.",),
        jingle_prompts=(
            (
                "id_purotejano_01",
                "Ten second Tejano radio jingle, festive male grito then "
                "harmony singers singing 'Puro Tejano, one oh seven one', "
                "button accordion run and bajo sexto strum, brass hit ending",
            ),
            (
                "id_purotejano_02",
                "Twelve second cumbia radio sweeper, joyful bilingual vocals "
                "singing 'Puro Tejano, San Antonio', accordion and timbales "
                "groove, shouted ajúa on the button",
            ),
        ),
    ),
    "neondrive": StationPlan(
        station_id="kndr-las-vegas",
        name="Neon Drive 88.5",
        voice="Nicole",
        voice_fallbacks=("Freya", "Elli"),
        persona="Hushed close-mic night voice, cool and dreamlike, barely above the synths",
        playlist="synthwave",
        host_lines=(
            "Neon Drive, eighty-eight five, Las Vegas. Synthesizers on, city lights low.",
            "This is Neon Drive. Close your door, roll the volume up soft, and glide.",
            "The desert at night is one long runway, driver. Consider this your approach lighting.",
            "This next track was built from one tape loop and a lot of "
            "patience. Let it wash over the lane lines.",
            "Every arpeggio out here is a mile marker. Count them slow.",
            "The strip glows behind you and the dark opens ahead. We score both sides.",
            "Ease into the lane and let it breathe. The bass line knows the way.",
            "Neon Drive, whispering you down the interstate, one synth line at a time.",
        ),
        id_lines=("K-N-D-R, Neon Drive 88.5, Las Vegas.",),
        jingle_prompts=(
            (
                "id_neondrive_01",
                "Ten second synthwave radio jingle, breathy female vocoder "
                "vocals singing 'Neon Drive, eighty eight five', analog "
                "arpeggio and gated snare, shimmering tail",
            ),
            (
                "id_neondrive_02",
                "Twelve second retrowave radio sweeper, robotic choir singing "
                "'Neon Drive, Las Vegas', pulsing bass synth and laser sweep, "
                "slow neon fade",
            ),
        ),
    ),
}


# Imaging bed: sound-effect prompts for sweepers and transitions between
# jingles, IDs, and music. Procedural keys, ElevenLabs SFX prompts.
SFX_PROMPTS: dict[str, str] = {
    "radio_imaging_whoosh_short": (
        "Quick bright radio imaging whoosh, airy filtered sweep left to "
        "right, about half a second, clean tail, broadcast production element"
    ),
    "radio_imaging_whoosh_long": (
        "Long smooth radio imaging whoosh, deep wind-tunnel sweep rising "
        "then falling, about two seconds, polished broadcast transition"
    ),
    "radio_imaging_impact": (
        "Punchy radio imaging impact hit, deep sub thump with a tight "
        "metallic slap, very short decay, modern broadcast sweeper accent"
    ),
    "radio_imaging_riser": (
        "One second radio imaging riser, filtered noise and synth "
        "climbing fast, builds tension then cuts clean for a voice to land"
    ),
    "radio_imaging_stinger": (
        "Short rock radio stinger, single distorted electric guitar power "
        "chord with a quick reverb tail, punchy broadcast imaging accent"
    ),
    "radio_imaging_shimmer": (
        "Soft glassy radio imaging shimmer, gentle bell tones and reversed "
        "sparkle fading out, dreamy late night broadcast transition"
    ),
}
