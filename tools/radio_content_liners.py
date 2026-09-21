"""Second-wave station identity: liners and a third jingle per station.

Split out of radio_content_plan.py to keep every file under the repo's
1000-line cap. Pure data, no I/O; radio_content_plan.py merges these into
``STATIONS`` at import, so the import surface does not change.

The first batch gave each station two sung jingles (``id_<key>_01``,
``_02``) and one spoken legal ID (``_03``). With a break after every two
songs and an ID in most breaks, three IDs came round often enough to
notice. This wave adds, per station:

- ``LINERS``: two short spoken liners, read in the station's own host
  voice like the legal ID. They become ``id_<key>_05`` and ``_06`` (the
  runner numbers ``id_lines`` after the legal ID from five upward; four is
  the third jingle's key). Every liner names the station, the way a real
  liner does, so a listener who tunes in mid-break still knows where they
  are.
- ``THIRD_JINGLES``: one more sung jingle at ``id_<key>_04``, written to
  sound different from the station's first two (a solo voice where the
  others are harmony, a different tempo or instrument), and stating its
  own length up front the way the runner expects.

Same spoken-text rules as the rest of the plan: player-facing, plain road
language, no key or menu names, no weather promises, no real brands.
"""

from __future__ import annotations

# station key -> two liner scripts, spoken by the station's host voice.
LINERS: dict[str, tuple[str, str]] = {
    "roadhouse": (
        "Freight Fate Roadhouse. Coast to coast, dock to dock, and every mile between.",
        "You're rolling with the Freight Fate Roadhouse. Keep it between the lines.",
    ),
    "nightline": (
        "Freight Fate Night Line. Low lights, long roads, and nobody rushing you.",
        "Stay on the Freight Fate Night Line. The dark is easier with company.",
    ),
    "rawhide": (
        "K-R-W-Z, The Rawhide. Dallas country, loud and proud.",
        "The Rawhide, ninety-eight one. Real country, no apologies.",
    ),
    "bigwheel": (
        "W-H-W-X, Big Wheel Country. Nashville's front porch, coast to coast.",
        "Big Wheel Country, one oh four five. The songs you grew up on, and the ones your kids will.",
    ),
    "prairieline": (
        "K-P-N-L, Prairie Line. Country that goes the distance.",
        "Prairie Line, ninety-five seven, Kansas City. Steady as the horizon.",
    ),
    "bigsky": (
        "K-B-G-K, Big Sky Country. Billings, and everything you can see from here.",
        "Big Sky Country, ninety-nine three. Room to breathe, and songs to match.",
    ),
    "grind": (
        "W-G-D-X, The Grind. Chicago rock for people who clock in.",
        "The Grind, ninety-seven nine. Turn it up and get back to work.",
    ),
    "desertrock": (
        "K-D-R-Z, Desert Rock. Phoenix. Hot roads, heavy riffs.",
        "Desert Rock, one oh one five. The heat's out there. The rock's in here.",
    ),
    "chrome": (
        "K-H-R-Z, Chrome. Los Angeles rock with the shine still on it.",
        "Chrome, one oh six three. Polished, loud, and headed your way.",
    ),
    "ridge": (
        "K-R-I-J, The Ridge. Denver rock, a mile up and climbing.",
        "The Ridge, one oh three seven. Downshift, breathe, rock on.",
    ),
    "sound": (
        "K-S-D-X, The Sound. Seattle rock for the rain and the road.",
        "The Sound, one oh two one. Wipers on, volume up.",
    ),
    "delta": (
        "W-D-T-Q, The Delta. Memphis blues, slow and true.",
        "The Delta, ninety-four three. Every mile is a verse.",
    ),
    "bayou": (
        "W-B-Y-K, Bayou Soul. New Orleans, cher, and don't you forget it.",
        "Bayou Soul, one hundred point nine. Simmering all night long.",
    ),
    "southernsoul": (
        "W-S-O-Z, Southern Soul. Atlanta, with love.",
        "Southern Soul, ninety-six five. Sweet as it gets, strong as you need.",
    ),
    "afterhours": (
        "W-N-A-H, Nashville After Hours. Jazz for the last shift.",
        "Nashville After Hours, ninety-two nine. Keep it low, keep it moving.",
    ),
    "cruisingold": (
        "K-G-O-L, Cruisin' Gold. Oklahoma City's greatest hits, all day long.",
        "Cruisin' Gold, one oh five nine. Every song a memory, every mile a smile.",
    ),
    "gloryroad": (
        "W-G-L-R, Glory Road. Birmingham gospel for the long haul.",
        "Glory Road, ninety-one five. Lift your head, driver. You're almost there.",
    ),
    "purotejano": (
        "K-T-J-O, Puro Tejano. San Antonio, la música de aquí, the music of home.",
        "Puro Tejano, one oh seven one. Súbele, driver. Turn it up.",
    ),
    "neondrive": (
        "K-N-D-R, Neon Drive. Las Vegas, after the lights go down.",
        "Neon Drive, eighty-eight five. Synthesizers on. Glide.",
    ),
}

# station key -> (asset key, Eleven Music prompt) for the third sung jingle.
THIRD_JINGLES: dict[str, tuple[str, str]] = {
    "roadhouse": (
        "id_roadhouse_04",
        "Ten second Americana radio jingle, one gravelly male voice singing "
        "'the Freight Fate Roadhouse' over a lone acoustic guitar and a boot "
        "stomp, ends on a whistle",
    ),
    "nightline": (
        "id_nightline_04",
        "Ten second late night radio jingle, a single hushed female voice "
        "humming then singing 'the Night Line' over brushed snare and upright "
        "bass, fades on a held note",
    ),
    "rawhide": (
        "id_rawhide_04",
        "Ten second country radio jingle, a lone cowboy baritone singing 'The "
        "Rawhide' with a bullwhip crack and a slap of telecaster, ends cold",
    ),
    "bigwheel": (
        "id_bigwheel_04",
        "Ten second Nashville country radio jingle, a sweet female duet "
        "singing 'Big Wheel Country' over mandolin tremolo and a fiddle tag",
    ),
    "prairieline": (
        "id_prairieline_04",
        "Ten second heartland country radio jingle, a plain warm male voice "
        "singing 'Prairie Line' over a slow acoustic strum and a harmonica "
        "sigh, unhurried ending",
    ),
    "bigsky": (
        "id_bigsky_04",
        "Ten second mountain country radio jingle, high lonesome male tenor "
        "singing 'Big Sky Country' over a single acoustic guitar and distant "
        "pedal steel, wide reverb",
    ),
    "grind": (
        "id_grind_04",
        "Ten second classic rock radio jingle, one gravel-throated male voice "
        "yelling 'The Grind' over a stack of power chords and a cymbal choke",
    ),
    "desertrock": (
        "id_desertrock_04",
        "Ten second desert rock radio jingle, a low raspy male voice drawling "
        "'Desert Rock' over a fuzz bass riff and a rattlesnake shaker, dry "
        "ending",
    ),
    "chrome": (
        "id_chrome_04",
        "Ten second arena rock radio jingle, a powerhouse female voice belting "
        "'Chrome' with a stadium crowd chant and a whammy dive, glossy finish",
    ),
    "ridge": (
        "id_ridge_04",
        "Ten second mountain rock radio jingle, soaring male voice singing "
        "'The Ridge' over a chugging riff that climbs a full octave, big hit "
        "ending",
    ),
    "sound": (
        "id_sound_04",
        "Ten second Pacific Northwest rock radio jingle, a relaxed male voice "
        "half-singing 'The Sound' over a jangly guitar and rain on a "
        "windshield, loose ending",
    ),
    "delta": (
        "id_delta_04",
        "Ten second Memphis blues radio jingle, an old weathered male voice "
        "singing 'The Delta' over a slide guitar lick and a foot stomp, ends "
        "on a bent note",
    ),
    "bayou": (
        "id_bayou_04",
        "Ten second New Orleans soul radio jingle, a playful raspy male voice "
        "singing 'Bayou Soul' with a second line snare and a tuba answer, "
        "brass button",
    ),
    "southernsoul": (
        "id_southernsoul_04",
        "Ten second soul radio jingle, a rich female voice singing 'Southern "
        "Soul' with a three-part choir answer, warm electric piano, handclap "
        "ending",
    ),
    "afterhours": (
        "id_afterhours_04",
        "Ten second cool jazz radio jingle, a hushed male crooner singing "
        "'Nashville After Hours' over a muted trumpet line and walking bass, "
        "soft ride cymbal ending",
    ),
    "cruisingold": (
        "id_cruisingold_04",
        "Ten second oldies radio jingle, bright fifties-style jingle singers "
        "in harmony singing 'Cruisin' Gold' over a piano triplet shuffle and "
        "a sax honk",
    ),
    "gloryroad": (
        "id_gloryroad_04",
        "Ten second gospel radio jingle, a soulful lead voice and a full "
        "choir singing 'Glory Road' over rolling piano and a tambourine, a "
        "big held amen",
    ),
    "purotejano": (
        "id_purotejano_04",
        "Ten second Tejano radio jingle, a bright male voice singing 'Puro "
        "Tejano' over a fast button accordion run and bajo sexto, a shouted "
        "ajúa to finish",
    ),
    "neondrive": (
        "id_neondrive_04",
        "Ten second synthwave radio jingle, a breathy female voice through a "
        "vocoder singing 'Neon Drive' over an analog arpeggio and a gated "
        "snare, shimmering tail",
    ),
}
