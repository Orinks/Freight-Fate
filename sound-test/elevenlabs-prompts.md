# ElevenLabs text-to-SFX prompts (draft, to splice into shortlist)

## 1. Curve cue tones

1. "A single clean marimba note, soft mallet on a wooden bar, pitched around
   G4, 250 milliseconds total including its natural decay. Dry, close-mic'd,
   no reverb tail, no room. One hit only, no repeat."
2. "A short sonar-style sine ping, pitched around 900 hertz, 180 milliseconds,
   fast attack and a smooth exponential fade. Pure tone, no harmonics, no
   echo, no underwater ambience. Single ping only."
3. "A small glass bell struck once, bright but not piercing, 300 milliseconds,
   recorded dry with no reverb. Gentle enough to hear a hundred times in a
   row without fatigue. One strike, silence after."

Ladder note: run each prompt three times asking for three pitches (low /
mid / high) so entry, apex and back-to-center share one timbre and differ
only in pitch. Same instrument across the ladder is the whole point.

## 2. Rumble strip + gravel shoulder

1. "Continuous heavy truck tires running over a milled highway rumble strip
   at 60 miles per hour, 12 seconds, steady unchanging buzz-drone with a
   sharp repeating flutter. Recorded from inside the cab, no engine, no
   music, no variation in speed."
2. "Loose gravel and small stones crunching continuously under heavy truck
   tires on a road shoulder at low speed, 12 seconds, dense and steady, no
   engine, no gear changes, no fade in or out."
3. "Corrugated washboard dirt road under truck tires, 10 seconds, rapid even
   rattling texture, constant speed, dry outdoor recording, no engine noise."

Loop note: ask for 10-12 seconds and constant speed explicitly; anything
that ramps or fades cannot be loop-cut cleanly.

## 3. Turn-signal relay

1. "A single vintage automotive flasher relay click, dry mechanical snap of
   a bimetallic contact, 60 milliseconds, close-mic'd on the relay itself,
   no cabin ambience, no engine. One click only."
2. "An old truck turn signal relay ticking steadily, 8 seconds, roughly 85
   clicks per minute, alternating harder on-click and softer off-click,
   dry and mechanical, nothing else in the recording."

## 4. Driveline clunk + air/turbo for shifts

1. "A heavy truck driveline clunk as the gear engages, one dull metallic
   thud with a short low-end thump, 350 milliseconds, mechanical and
   weighty, no engine tone, no reverb."
2. "Diesel turbo blow-off between gearshifts, a quick rising whistle then a
   sharp pressurized release, 700 milliseconds total, big-rig scale not
   sports car, no engine note underneath."
3. "Short pneumatic air line release on a heavy truck, crisp hiss, 400
   milliseconds, decaying naturally, dry close recording, no ambience."

## 5. Brake-release air sigh

1. "Air brake release on a parked semi truck, the long pneumatic sigh as
   pressure drops, 1.5 seconds, deep and airy with a soft tail, recorded
   close outside the tractor, no engine, no traffic."
2. "Parking brake knob popping out on a heavy truck followed by a sharp
   pressurized pshhh, 1 second total, dry mechanical then airy, nothing
   else in the recording."
3. "Short service brake air release, quick punchy psshh, 600 milliseconds,
   truck scale not train scale, dry, no reverb tail."

Scale note: say "truck, not train" in every prompt here -- the model
defaults to a much bigger, longer rail-yard release otherwise.

## 6. Repair / rig-wear foley

1. "Pneumatic impact wrench spinning a lug nut off a truck wheel, one burst,
   1.5 seconds, hammering rattle then the nut spinning free, dry garage
   recording, no voices."
2. "Hydraulic shop lift raising, low motor hum with a rising pneumatic
   groan, 6 seconds steady, no clanking, no voices."
3. "Air compressor in a repair bay kicking on and running, 10 seconds
   steady, mechanical drone with a pulsing motor, no voices, no tools."

## 7. Mini-game / UI stingers

1. "A bright two-note correct-answer ding, ascending perfect fifth on a
   glass bell, 400 milliseconds, cheerful and clean, no reverb, no music."
2. "A short wrong-answer buzzer, low square-wave buzz, 500 milliseconds,
   flat and blunt, not harsh or distorted, one buzz only."
3. "A small warm crowd applause, 3 seconds, twenty or thirty people
   clapping in a diner-sized room, starting immediately and fading
   naturally, no cheering, no whistles."

## 8. Windshield rain (three-rate crossfade layer)

Texture only -- lives under engine/road/wipers and a muffling cab, so it
just has to read as "rain on glass." ElevenLabs, not Splice credits.

1. "Light steady drizzle on a truck windshield, heard from inside the cab.
   Fine delicate droplets lightly tapping and speckling the glass, soft and
   sparse, even and continuous. No wipers, no thunder, no wind gusts, no
   music -- a seamless, unchanging loop of gentle rain on the windshield."
2. "Steady moderate rain on a truck windshield, heard from inside the cab.
   A consistent patter of raindrops striking and running down the glass,
   even and continuous, medium intensity. No wipers, no thunder, no wind,
   no music -- a seamless, constant loop of rain on the windshield."
3. "Heavy downpour drumming on a truck windshield, heard from inside the
   cab. Dense insistent rain hammering the glass with running sheets of
   water, loud and full but even and unchanging. No wipers, no thunder, no
   wind, no music -- a seamless, constant loop of heavy rain on the
   windshield."

Loop/crossfade note: turn the Loop toggle ON, ~11s, and keep the STEADIEST
take of 2-3 -- any gust, thunder crack, or volume swell breaks both the loop
and the light->heavy crossfade. Keep the three tonally matched ("inside the
cab, on the glass") so the crossfade stays in one space. Three rates is
enough: driving into rain walks up the ladder; drive speed just nudges
level/brightness on top. Wipers stay a separate layer (Norm has them).
