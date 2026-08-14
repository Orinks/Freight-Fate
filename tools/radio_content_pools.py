"""Shared radio song batches for the generation pass.

Split out of radio_content_plan.py (ads live in radio_content_ads.py)
to keep every file under the repo's 1000-line cap. Pure data, no I/O;
the import surface stays ``tools.radio_content_plan``, which re-exports
everything here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SongPlan:
    key: str
    title: str
    description: str
    prompt: str
    length_ms: int
    instrumental: bool


# Song batches, MUSIC_SPECS prompt style: concrete genre, subject, vocal
# and instrumentation notes, a mix/feel tag. Keys extend the shipped
# catalog stems; titles must never collide with music.py.
SONG_PLAN: dict[str, tuple[SongPlan, ...]] = {
    "oldies": (
        SongPlan(
            "radio_oldies_jukebox_in_the_corner",
            "Jukebox in the Corner",
            "Bright doo-wop number about a truck-stop jukebox",
            "Upbeat nineteen-fifties doo-wop song about the jukebox in the "
            "corner of a roadside diner, smooth male lead with bass singer "
            "answers, rolling piano triplets, handclaps, warm AM radio mix",
            168_000,
            False,
        ),
        SongPlan(
            "radio_oldies_milkshake_moon",
            "Milkshake Moon",
            "Slow-dance doo-wop ballad in six-eight",
            "Slow nineteen-fifties doo-wop ballad about sharing a milkshake "
            "under a full moon, tender male falsetto lead, ooh-wah backing "
            "harmonies, six-eight piano and soft snare, prom night feel",
            186_000,
            False,
        ),
        SongPlan(
            "radio_oldies_chrome_fins",
            "Chrome Fins",
            "Surf-rock instrumental for tailfin dreams",
            "Driving early-sixties surf rock instrumental celebrating chrome "
            "tailfins on the open highway, reverb-drenched twang guitar lead, "
            "galloping drums, saxophone honks, hot rod energy, no vocals",
            157_000,
            True,
        ),
        SongPlan(
            "radio_oldies_hop_in_the_hardtop",
            "Hop in the Hardtop",
            "Jump-blues rock and roll dance number",
            "High-energy nineteen-fifties rock and roll jump number inviting "
            "a sweetheart into a shiny hardtop, shouting male vocals, honking "
            "tenor sax solo, boogie piano, slap-back echo, jukebox mix",
            160_000,
            False,
        ),
        SongPlan(
            "radio_oldies_soda_shop_sweetheart",
            "Soda Shop Sweetheart",
            "Girl-group pop with wall-of-sound sparkle",
            "Sparkling early-sixties girl-group pop song about a crush at "
            "the soda shop, lead female vocal with sha-la-la harmonies, "
            "castanets, chiming glockenspiel, big echoing drums, sweet ending",
            172_000,
            False,
        ),
        SongPlan(
            "radio_oldies_drive_in_picture_show",
            "Drive-In Picture Show",
            "Twist-beat rocker about drive-in movie nights",
            "Twist-beat early-sixties rock and roll song about a night at "
            "the drive-in picture show, cheerful male vocals, twanging "
            "guitar riff, saxophone section, dance-craze energy, mono-style mix",
            163_000,
            False,
        ),
        SongPlan(
            "radio_oldies_transistor_summer",
            "Transistor Summer",
            "Sunny beach-pop tune about a pocket radio",
            "Sunny mid-sixties beach pop song about a transistor radio "
            "soundtracking a whole summer, layered male harmonies, bright "
            "twelve-string guitar jangle, bouncing bass, carefree fade",
            170_000,
            False,
        ),
        SongPlan(
            "radio_oldies_sock_hop_saturday",
            "Sock Hop Saturday",
            "Piano-pounding rock and roll dance-floor filler",
            "Rowdy nineteen-fifties rock and roll song about Saturday night "
            "at the sock hop, wild piano glissandos, hiccuping male vocals, "
            "walking upright bass, backbeat handclaps, breathless finish",
            155_000,
            False,
        ),
    ),
    "gospel": (
        SongPlan(
            "radio_gospel_wide_is_the_river",
            "Wide Is the River",
            "Full-choir southern gospel about crossing over",
            "Soaring southern gospel choir song about a river too wide to "
            "cross alone, powerhouse female lead with full choir swells, "
            "Hammond organ, tambourine on the backbeat, triumphant key change",
            214_000,
            False,
        ),
        SongPlan(
            "radio_gospel_set_my_burden_down",
            "Set My Burden Down",
            "Slow-building spiritual of release and rest",
            "Slow-building gospel spiritual about finally setting a heavy "
            "burden down, weathered male lead, humming choir bed, sparse "
            "piano opening blooming into organ and drums, cathartic ending",
            226_000,
            False,
        ),
        SongPlan(
            "radio_gospel_morning_will_come",
            "Morning Will Come",
            "Gentle piano ballad of hope before dawn",
            "Gentle gospel piano ballad promising that morning will come "
            "after the longest night, warm female vocals, soft choir pads, "
            "brushed drums entering late, sunrise swell at the close",
            198_000,
            False,
        ),
        SongPlan(
            "radio_gospel_hands_on_the_wheel",
            "Hands on the Wheel",
            "Trucker gospel shuffle of faith on the road",
            "Mid-tempo country gospel shuffle about a driver keeping hands "
            "on the wheel and heart set higher, sincere male vocals, pedal "
            "steel and piano, quartet harmonies on the chorus, road-hymn feel",
            188_000,
            False,
        ),
        SongPlan(
            "radio_gospel_hallelujah_highway",
            "Hallelujah Highway",
            "Hand-clapping up-tempo gospel celebration",
            "Up-tempo hand-clapping gospel song celebrating the hallelujah "
            "highway home, call-and-response between fiery lead and choir, "
            "rollicking piano, Hammond stabs, joyful double-time finish",
            176_000,
            False,
        ),
        SongPlan(
            "radio_gospel_old_church_bell",
            "Old Church Bell",
            "Close-harmony quartet remembering a country church",
            "Traditional southern gospel quartet song remembering the old "
            "church bell still ringing across the fields, four-part male "
            "close harmony, upright bass singer featured, light piano, warm reverence",
            192_000,
            False,
        ),
        SongPlan(
            "radio_gospel_sunday_sunrise",
            "Sunday Sunrise",
            "Instrumental organ-and-steel Sunday meditation",
            "Peaceful gospel instrumental for a Sunday sunrise drive, "
            "Hammond organ melody answered by weeping pedal steel, gentle "
            "piano arpeggios, slow swelling dynamics, devotional calm, no vocals",
            204_000,
            True,
        ),
        SongPlan(
            "radio_gospel_carry_me_home",
            "Carry Me Home",
            "Slow spiritual with deep soloist and choir",
            "Deep slow gospel spiritual asking to be carried home at the "
            "end of the long road, resonant bass-baritone lead, choir "
            "humming low, sparse organ, unhurried and profound, quiet amen ending",
            234_000,
            False,
        ),
    ),
    "tejano": (
        SongPlan(
            "radio_tejano_camino_de_flores",
            "Camino de Flores",
            "Flower-strewn cumbia for the road home",
            "Joyful Tejano cumbia in Spanish about a road lined with "
            "flowers leading home, warm male vocals, button accordion hooks, "
            "bajo sexto strum, timbales and congas, danceable radio mix",
            182_000,
            False,
        ),
        SongPlan(
            "radio_tejano_mi_troquita",
            "Mi Troquita",
            "Affectionate conjunto polka about a beloved truck",
            "Up-tempo conjunto polka in Spanish praising a beloved old "
            "truck that never quits, playful male vocals with gritos, "
            "virtuosic accordion runs, bajo sexto bounce, party energy",
            165_000,
            False,
        ),
        SongPlan(
            "radio_tejano_luna_de_laredo",
            "Luna de Laredo",
            "Romantic border-moon ranchera ballad",
            "Romantic Tejano ranchera ballad in Spanish about the moon "
            "over Laredo and a love waiting there, passionate male vocals, "
            "slow accordion sighs, nylon guitar, soft brass, longing finish",
            216_000,
            False,
        ),
        SongPlan(
            "radio_tejano_baila_conmigo",
            "Baila Conmigo",
            "Irresistible dance-floor cumbia invitation",
            "Infectious Tejano cumbia in Spanish inviting everyone to "
            "dance, charismatic female vocals, punchy accordion riff, "
            "keyboard stabs, timbales fills, crowd chants on the chorus, "
            "festival energy",
            174_000,
            False,
        ),
        SongPlan(
            "radio_tejano_acordeon_del_alma",
            "Acordeón del Alma",
            "Accordion showcase instrumental with soul",
            "Virtuosic Tejano conjunto instrumental showcasing a soulful "
            "button accordion melody over driving bajo sexto and upright "
            "bass, polka rhythm with cumbia turns, celebratory, no vocals",
            170_000,
            True,
        ),
        SongPlan(
            "radio_tejano_polvo_del_camino",
            "Polvo del Camino",
            "Road-dust conjunto tune for long hauls",
            "Mid-tempo Tejano conjunto song in Spanish about the dust of "
            "the road and the miles still ahead, seasoned male vocals, "
            "steady accordion and bajo sexto groove, resilient and warm",
            190_000,
            False,
        ),
        SongPlan(
            "radio_tejano_corazon_de_cromo",
            "Corazón de Cromo",
            "Modern Tejano pop with a chrome heart",
            "Modern Tejano pop song in Spanish about a heart made of "
            "chrome that still knows how to love, sleek female vocals, "
            "synth pads under accordion hooks, cumbia beat, polished radio mix",
            179_000,
            False,
        ),
        SongPlan(
            "radio_tejano_cumbia_del_mercado",
            "Cumbia del Mercado",
            "Market-day cumbia instrumental",
            "Lively Tejano cumbia instrumental painting a busy market "
            "morning, bright accordion lead trading with keyboard melody, "
            "guiro and congas driving, brass section punches, festive, no vocals",
            168_000,
            True,
        ),
    ),
    "synthwave": (
        SongPlan(
            "radio_synthwave_midnight_grid",
            "Midnight Grid",
            "Pulsing retrowave for empty city freeways",
            "Pulsing synthwave instrumental for cruising an empty midnight "
            "freeway grid, analog arpeggios, gated reverb snare, warm "
            "sawtooth bass, neon retro-futurist mood, no vocals",
            208_000,
            True,
        ),
        SongPlan(
            "radio_synthwave_sodium_lights",
            "Sodium Lights",
            "Amber-lit nocturne of highway lamps",
            "Moody mid-tempo synthwave instrumental evoking amber sodium "
            "lights strobing past a windshield, shimmering pad chords, "
            "slow-attack lead synth, steady electronic drums, hypnotic drift, no vocals",
            222_000,
            True,
        ),
        SongPlan(
            "radio_synthwave_afterglow_avenue",
            "Afterglow Avenue",
            "Dreamwave with soft vocals for the last mile",
            "Dreamy synthwave song about the afterglow of city lights on "
            "the last mile home, soft breathy female vocals, lush analog "
            "pads, slow chorus-drenched guitar, gentle drum machine, nostalgic haze",
            214_000,
            False,
        ),
        SongPlan(
            "radio_synthwave_starlight_odometer",
            "Starlight Odometer",
            "Glittering night-drive arpeggio piece",
            "Glittering synthwave instrumental counting miles under desert "
            "stars, fast sixteenth-note arpeggios, deep pulsing bass, "
            "sparkling bell synths, driving momentum with a weightless bridge, no vocals",
            196_000,
            True,
        ),
        SongPlan(
            "radio_synthwave_neon_mirage",
            "Neon Mirage",
            "Desert-heat retrowave shimmer",
            "Slow-burning synthwave instrumental about a neon city "
            "shimmering like a mirage across the desert night, detuned "
            "analog leads, tom-heavy electronic drums, wide stereo pads, cinematic, no vocals",
            230_000,
            True,
        ),
        SongPlan(
            "radio_synthwave_taillight_river",
            "Taillight River",
            "Flowing red-light meditation for slow lanes",
            "Flowing downtempo synthwave instrumental watching a river of "
            "taillights wind through the dark, liquid arpeggio patterns, "
            "soft side-chained pads, unhurried electronic pulse, meditative, no vocals",
            218_000,
            True,
        ),
        SongPlan(
            "radio_synthwave_analog_heart",
            "Analog Heart",
            "Synthpop love song for machines that feel",
            "Warm synthpop song about an analog heart beating in a digital "
            "world, intimate male vocals with vocoder harmonies, punchy "
            "retro drum machine, hooky lead synth line, bittersweet radio mix",
            192_000,
            False,
        ),
        SongPlan(
            "radio_synthwave_desert_satellites",
            "Desert Satellites",
            "Wide-sky ambient synthwave finale",
            "Expansive ambient-leaning synthwave instrumental for watching "
            "satellites cross a desert sky, slow evolving pad layers, "
            "distant echoing lead, sparse deep kick, vast and serene, no vocals",
            240_000,
            True,
        ),
    ),
    "country": (
        SongPlan(
            "radio_country_split_rail",
            "Split Rail",
            "Fence-line country tune about staying the course",
            "Steady modern country song about split rail fences and "
            "promises that hold, sincere male vocals, telecaster and pedal "
            "steel trading fills, mid-tempo trucker shuffle, warm radio mix",
            184_000,
            False,
        ),
        SongPlan(
            "radio_country_second_gear_sunrise",
            "Second Gear Sunrise",
            "Early-shift country song of first light",
            "Hopeful country song about pulling out of the yard in second "
            "gear as the sun comes up, warm female vocals, acoustic strum "
            "with fiddle answering, gentle build to a big open chorus",
            176_000,
            False,
        ),
        SongPlan(
            "radio_country_gravel_lot_serenade",
            "Gravel Lot Serenade",
            "Parking-lot slow dance for two rigs at dusk",
            "Tender country waltz about two drivers sharing supper on a "
            "gravel lot at dusk, duet of male and female vocals, brushed "
            "drums, weeping pedal steel, small-town dance-floor sway",
            198_000,
            False,
        ),
        SongPlan(
            "radio_country_gooseneck_moon",
            "Gooseneck Moon",
            "Moonlit haul with a trailer full of memories",
            "Wistful country waltz about hauling a gooseneck trailer under "
            "a harvest moon, weathered male vocals, mandolin and dobro, "
            "unhurried three-four sway, nostalgic late-evening feel",
            206_000,
            False,
        ),
        SongPlan(
            "radio_country_cold_coffee_courage",
            "Cold Coffee Courage",
            "Wry country anthem for the last hundred miles",
            "Wry up-tempo country song about running the last hundred "
            "miles on cold coffee and stubbornness, gravelly male vocals, "
            "chicken-pickin' telecaster, driving train beat, grinning finish",
            170_000,
            False,
        ),
        SongPlan(
            "radio_country_last_bale_of_summer",
            "Last Bale of Summer",
            "Harvest-end ballad of fields going quiet",
            "Reflective country ballad about the last hay bale of summer "
            "and the season turning, tender female vocals, fingerpicked "
            "acoustic guitar, fiddle harmony lines, golden-hour warmth",
            212_000,
            False,
        ),
        SongPlan(
            "radio_country_red_dirt_ring",
            "Red Dirt Ring",
            "Stomping red-dirt band instrumental",
            "Stomping red dirt country instrumental built on dueling "
            "fiddle and electric guitar, honky-tonk piano pounding, "
            "double-stop breakdowns, barn dance energy, no vocals",
            166_000,
            True,
        ),
        SongPlan(
            "radio_country_high_line_home",
            "High Line Home",
            "Northern-plains song of the long way back",
            "Big-sky country song about taking the northern high line "
            "home across the plains, earnest male vocals, jangling guitars "
            "with pedal steel swells, steady rolling beat, horizon-wide chorus",
            194_000,
            False,
        ),
    ),
    "classic_rock": (
        SongPlan(
            "radio_rock_ten_ton_heart",
            "Ten Ton Heart",
            "Heavy-hearted highway anthem",
            "Classic rock anthem about hauling a ten ton heart down the "
            "interstate, gritty male vocals, thick guitar riffs, pounding "
            "drums, soaring twin-lead solo, seventies stadium energy",
            202_000,
            False,
        ),
        SongPlan(
            "radio_rock_jake_brake_lullaby",
            "Jake Brake Lullaby",
            "Grinning rocker about the loudest lullaby",
            "Swaggering blues-rock song joking that the jake brake is the "
            "only lullaby a trucker knows, raspy male vocals, growling "
            "slide guitar, half-time stomp groove, cowbell accents, live-room feel",
            180_000,
            False,
        ),
        SongPlan(
            "radio_rock_asphalt_aurora",
            "Asphalt Aurora",
            "Instrumental for northern lights over blacktop",
            "Melodic classic rock instrumental about northern lights "
            "shimmering over an empty highway, expressive lead guitar "
            "melody, organ pads, spacious drums, slow-building epic arc, no vocals",
            226_000,
            True,
        ),
        SongPlan(
            "radio_rock_double_clutch_city",
            "Double Clutch City",
            "Horn-stabbed funk-rock for city hauling",
            "Funky classic rock song about double clutching through city "
            "traffic, confident male vocals, wah guitar riff, punchy horn "
            "section stabs, syncopated drums, seventies street groove",
            174_000,
            False,
        ),
        SongPlan(
            "radio_rock_vulture_pass",
            "Vulture Pass",
            "Menacing desert hard-rock instrumental",
            "Menacing desert hard rock instrumental for climbing a lonely "
            "mountain pass, heavy detuned riffs, tribal floor toms, eerie "
            "slide guitar cries, slow relentless momentum, no vocals",
            210_000,
            True,
        ),
        SongPlan(
            "radio_rock_magnetic_west",
            "Magnetic West",
            "Wanderlust rocker pulled toward the sunset",
            "Driving heartland rock song about a compass heart pulled "
            "magnetic west, earnest male vocals, chiming twelve-string "
            "over crunchy rhythm guitar, galloping beat, wide-open chorus",
            190_000,
            False,
        ),
        SongPlan(
            "radio_rock_timberline_run",
            "Timberline Run",
            "High-altitude boogie above the treeline",
            "Hard-charging boogie rock song about running freight above "
            "the timberline, howling male vocals, twin guitar harmonies, "
            "relentless shuffle drums, mountain-sized breakdown, big finish",
            184_000,
            False,
        ),
        SongPlan(
            "radio_rock_furnace_wind",
            "Furnace Wind",
            "Desert-heat rocker with a slow-burn build",
            "Slow-burning hard rock song about driving into a furnace "
            "wind across the flats, smoky female vocals, hypnotic bass "
            "riff, shimmering ride cymbal groove, explosive final chorus",
            216_000,
            False,
        ),
    ),
    "blues": (
        SongPlan(
            "radio_blues_eleven_bridges",
            "Eleven Bridges",
            "Counting crossings on a heavy-hearted run",
            "Slow-rolling electric blues about counting eleven bridges "
            "between here and forgiveness, weathered male vocals, stinging "
            "guitar bends, organ swells, patient shuffle, late-night club feel",
            218_000,
            False,
        ),
        SongPlan(
            "radio_blues_mudflap_boogie",
            "Mudflap Boogie",
            "Greasy jump-blues floor shaker",
            "Rowdy jump blues boogie about mudflaps slapping time on the "
            "highway, shouting male vocals, honking baritone sax, "
            "barrelhouse piano, walking bass, double-time hand-jive ending",
            162_000,
            False,
        ),
        SongPlan(
            "radio_blues_dock_light_darling",
            "Dock Light Darling",
            "Soul-blues serenade under warehouse lights",
            "Smoldering soul blues serenade to a darling waiting under "
            "the dock lights, velvet female vocals, horn section swells, "
            "tremolo guitar, slow six-eight burn, heartfelt climax",
            204_000,
            False,
        ),
        SongPlan(
            "radio_blues_worn_out_wipers",
            "Worn Out Wipers",
            "Rain-streaked slow blues lament",
            "Mournful slow blues about worn out wipers and a windshield "
            "full of rain, aching male vocals, weeping slide guitar, "
            "sparse piano drips, brushed drums, gray-sky atmosphere",
            224_000,
            False,
        ),
        SongPlan(
            "radio_blues_catfish_county",
            "Catfish County",
            "Swamp-groove instrumental with harmonica lead",
            "Greasy swamp blues instrumental prowling through catfish "
            "county, wailing harmonica lead over muted tremolo guitar, "
            "loping bass, porch-stomp drums, humid and loose, no vocals",
            186_000,
            True,
        ),
        SongPlan(
            "radio_blues_low_water_crossing",
            "Low Water Crossing",
            "Texas blues shuffle about risky crossings",
            "Driving Texas blues shuffle about chancing the low water "
            "crossing one more time, confident male vocals, stinging "
            "stratocaster leads, swinging drums, roadhouse dance-floor heat",
            178_000,
            False,
        ),
        SongPlan(
            "radio_blues_night_shift_queen",
            "Night Shift Queen",
            "Horn-driven soul tribute to a night-shift hero",
            "Strutting horn-driven soul blues celebrating the queen of "
            "the night shift, powerhouse female vocals, tight brass "
            "punches, funky guitar chank, clavinet groove, show-stopping finish",
            192_000,
            False,
        ),
        SongPlan(
            "radio_blues_red_lights_and_regrets",
            "Red Lights and Regrets",
            "Minor-key blues of long stops and old choices",
            "Brooding minor-key blues about red lights, regrets, and "
            "roads not taken, smoky male vocals, jazzy guitar chords, "
            "upright bass, rain-on-glass mood, resigned final verse",
            230_000,
            False,
        ),
    ),
    "jazz": (
        SongPlan(
            "radio_jazz_lower_broad_lullaby",
            "Lower Broad Lullaby",
            "Hushed after-close stroll past dark honky-tonks",
            "Hushed late-night jazz instrumental strolling past shuttered "
            "honky-tonks, muted trumpet melody, brushed snare, upright "
            "bass walking slow, sparse piano comping, wistful and calm, no vocals",
            212_000,
            True,
        ),
        SongPlan(
            "radio_jazz_velvet_downbeat",
            "Velvet Downbeat",
            "Plush mid-tempo swing for late sets",
            "Plush mid-tempo swing jazz instrumental with a velvet "
            "downbeat, warm tenor saxophone lead, piano trio support, "
            "ride cymbal shimmer, sophisticated small-club atmosphere, no vocals",
            198_000,
            True,
        ),
        SongPlan(
            "radio_jazz_neon_and_nylon",
            "Neon and Nylon",
            "Nylon-string jazz under neon light",
            "Intimate jazz instrumental pairing nylon string guitar with "
            "soft neon-lit electric piano, bossa-tinged brushwork, melodic "
            "bass interludes, unhurried midnight romance, no vocals",
            206_000,
            True,
        ),
        SongPlan(
            "radio_jazz_printers_alley_last_call",
            "Printer's Alley Last Call",
            "Smoky last-call blues-jazz crawl",
            "Smoky after-hours jazz instrumental for last call in a "
            "narrow downtown alley, growling plunger-mute trombone, slow "
            "blues-jazz crawl, piano trills, bartender-sweeping-up mood, no vocals",
            220_000,
            True,
        ),
        SongPlan(
            "radio_jazz_brushed_steel",
            "Brushed Steel",
            "Jazz-meets-pedal-steel crossover piece",
            "Nashville crossover jazz instrumental blending brushed drums "
            "with singing pedal steel guitar, jazz chord changes under "
            "country voicings, upright bass, graceful and novel, no vocals",
            190_000,
            True,
        ),
        SongPlan(
            "radio_jazz_midnight_mezzanine",
            "Midnight Mezzanine",
            "Elegant solo-piano-led nocturne",
            "Elegant jazz nocturne overlooking an empty hotel mezzanine "
            "at midnight, lyrical solo piano joined by soft double bass "
            "and feathered brushes, impressionistic harmony, serene, no vocals",
            216_000,
            True,
        ),
        SongPlan(
            "radio_jazz_blue_neon_glow",
            "Blue Neon Glow",
            "Smoky female vocal ballad for the small hours",
            "Smoky late-night jazz ballad about a blue neon glow in an "
            "empty diner window, intimate female vocals, tenor sax "
            "answers, piano trio, slow pulse, torch-song longing",
            228_000,
            False,
        ),
        SongPlan(
            "radio_jazz_cumberland_moonrise",
            "Cumberland Moonrise",
            "Riverside moonrise meditation",
            "Serene jazz instrumental watching the moon rise over a slow "
            "river, flugelhorn melody floating over gentle guitar and "
            "piano interplay, soft mallet cymbals, spacious and reflective, no vocals",
            234_000,
            True,
        ),
    ),
    "night_line": (
        SongPlan(
            "radio_night_paper_cup_moon",
            "Paper Cup Moon",
            "Quiet ballad of vending-machine coffee at midnight",
            "Quiet late-night folk ballad about coffee in a paper cup "
            "under a parking lot moon, hushed female vocals, fingerpicked "
            "guitar, distant pedal steel, barely-there brushes, tender and unhurried",
            196_000,
            False,
        ),
        SongPlan(
            "radio_night_idle_hearts",
            "Idle Hearts",
            "Slow duet for two trucks idling side by side",
            "Slow-burning duet ballad about two idling trucks and two "
            "idle hearts sharing a dark lot, intertwined male and female "
            "vocals, warm electric piano, soft strings, patient swelling chorus",
            218_000,
            False,
        ),
        SongPlan(
            "radio_night_dashboard_glow",
            "Dashboard Glow",
            "Hushed confession lit by instrument lights",
            "Hushed midnight ballad confessing everything to the "
            "dashboard glow, close-mic male vocals, slow arpeggiated "
            "guitar, deep soft bass, sparse piano echoes, intimate and clean",
            204_000,
            False,
        ),
    ),
}
