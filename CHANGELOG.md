# Changelog

## Unreleased

### Added

- **You will sometimes hear a trooper run somebody else down.** A siren past
  you, the stop on the shoulder as you pass, maybe the CB calling it -- and a
  bear who has somebody stopped is not watching you.

- **That siren now says whose stop it is.** The moment it starts, a short
  line tells you a trooper has somebody else stopped on the shoulder --
  not you -- so it never reads like your own pull-over beginning. Once in
  a while it names why: speeding, a log check, a light out.

- **The scale ahead now has its own sound.** A short, low two-part cue --
  a heavy thump, then a quick beep -- plays the moment an open weigh
  station is announced, so you know it is the scale before a word is
  spoken, not the same tone used for other roadside checks.

- **You can now pay down what you owe from your own cash.** Whenever you
  carry a balance and have money in hand, the terminal and every truck stop
  offer to pay it all, half, or everything above a 200 dollar fuel cushion.
  Clearing the balance stops settlement collection on the spot.

- **Every Freight Fate station now sounds like a real station.** All the
  regional stations have their own host between songs, sung station jingles,
  spoken station IDs, and fictional commercials for the road: travel
  centers, diners, tire shops, and more. The Roadhouse has a new voice, and
  the Night Line host settles in even closer after dark.

- **Four new stations join the dial.** Cruisin' Gold plays oldies out of
  Oklahoma City, Glory Road brings southern gospel from Birmingham, Puro
  Tejano runs Tejano out of San Antonio, and Neon Drive hums synthwave out
  of Las Vegas. The new stations start with a handful of songs each and
  their playlists will keep growing in the next builds.

- **The engine brake sound is now choosable.** Settings, Audio has a new
  Engine brake voice row: recorded, the real growl drivers call the jake,
  or classic, the synthesized growl from earlier versions. It switches
  instantly, even mid descent, and Learn game sounds plays back whichever
  one you picked.

- **Radio volume now changes from the wheel.** Hold Shift with Page Up or
  Page Down (or Shift with semicolon or apostrophe) to raise or lower the
  in-cab radio volume in ten percent steps, spoken as it moves, without
  leaving the driving seat.

- **You can hear where you are in the lane while you steer.** When the lane
  work is yours, holding a steering direction now brings the soft position
  tock up on its own, panned to where the truck sits inside the lane, and it
  stops with a quiet click when you straighten up. Lining up for an exit, the
  tock comes up as you move over and its beat quickens as you get far enough
  right; the moment the exit lane is set it stops and the signal cancels
  itself, the way it does in a truck when the wheel comes back. That click is
  how you know you are far enough over, with nothing spoken. The I key still
  turns the same tock on and off whenever you want it.

### Changed

- **The overspeed warning no longer chimes at you for cruise's own speed.**
  It used to start warning at 5 miles per hour over the limit, which is
  exactly the pace adaptive cruise holds, so the truck nagged you for a speed
  it had chosen itself -- and the only way out was to switch the whole alert
  off. It now waits until you are more than 7 over: past anything cruise will
  do, still short of where a trooper can act on it, so it warns you while
  slowing down is still free. Because it no longer fires at speeds you did not
  pick, the Overspeed warning setting is gone; there is nothing left to turn
  off. The runaway alarm past 20 over is unchanged.

- **Settings now sit where you would go looking for them.** Speed keeper
  moved from Controls to Driving assistance, with the rest of the driving
  help. Lane and edge cue prominence is now called Lane and edge cue volume
  and lives in Audio, right under Gameplay cues volume, because that is the
  volume it rides on -- and its values now say quieter, standard, and louder,
  which is what you are actually choosing between. Your settings came with
  them: nothing you had chosen was reset. If you have played before, the
  Gameplay menu tells you once where things went.

- **The driving assistance help no longer promises lane centering that does
  not happen.** Lane centering assistance is a row for steering help the
  truck does not do yet, and it used to describe itself as though it did.
  It now says plainly that leaving it on or off makes no difference to how
  the truck steers today, and the Balanced preset describes what it really
  changes.
- **Coming up on your exit no longer slows you to a crawl miles out.**
  Signal for an exit and automatic speed control used to drop straight to
  40 the moment you armed it, with the ramp still miles up the road. Now it
  holds road speed and starts shedding when the exit is genuinely close,
  coming down gradually so you arrive slow enough to take the ramp instead
  of crawling the last stretch of highway. The final approach to a delivery
  works the same way: the road stays at its posted limit until the local
  road to the gate really begins, and that stretch is now measured from
  where the place you are delivering to actually sits, so a dock right off
  the ramp no longer shares its approach with one several miles inland.

- **Your roadside chatter switches now work in terse speech.** Parks,
  rivers, mountain passes, museums, and billboards each have their own
  switch, and in terse speech none of them did anything -- every roadside
  callout was silenced whichever way the switches were set. Now the switch
  alone decides what you hear: leave a kind on and you get it in terse too,
  kept short. A river crossing is the river's name, a park is the park, a
  billboard is the sign itself with nothing wrapped around it. Normal speech
  is unchanged, and town names still follow the place callouts setting.

- **Traffic at exits you are not taking has gone quiet.** The game used to
  call the traffic building at every exit ahead of you, one after another,
  whether or not any of them was yours. Now that call comes only for an
  exit you have signalled for -- or one lane keeping is taking for you --
  and it arrives with the same warning as before. Merging traffic and
  construction taper warnings are unchanged: those are about the road you
  are already on.

- **A speed limit drop now says why, when the road knows.** "Speed limit
  reduced to 35" used to leave you guessing. Now, when the trip's own data
  can honestly explain the drop, it says so: the town you are approaching
  or leaving, a weigh station just ahead, or a real downgrade starting
  right there. When none of those fit, it stays the plain number, same as
  before.

- **Pressing Escape now acts instead of explaining.** At the terminal,
  Escape used to just tell you to use Quit to main menu -- now it takes
  you straight back, the same as that menu item, since progress already
  autosaves. At the main menu, Escape now asks whether you want to quit
  and does it on your say-so, instead of telling you to go press Enter
  on Quit yourself.

- **Blowing past an open weigh station now gets you pulled over.** Scale
  officers watch the bypass lane, and a truck that runs an open scale
  instead of pulling in is caught most of the time -- steep odds, not a
  certainty. Get caught and it is an 1,800 dollar citation on the spot,
  more if you have priors or you are rolling through roadwork, and it
  compounds the same way every other repeat citation does. The trooper
  also runs the full inspection right there on the shoulder, since that is
  the one you tried to skip. Get away with it and nothing happens at all --
  you will not know which one it was going to be.

- **The truck dealer is now one menu choice away.** The drive to city
  services is retired: the dealer opens straight from the terminal menu,
  named for the real local dealership where we have one on record. Fuel,
  repairs, rest, and food stay at truck stops and the terminal garage.

- **The road talks at a human pace now.** Speed limit changes, traffic
  calls, and zone chatter used to arrive back to back, because the
  game's fast clock packs a lot of road into every real minute. Routine
  announcements now keep a few seconds of breathing room from each
  other, in every driving mode -- and when several things change close
  together, you hear the current state of the road, never a stale
  catch-up. Warnings that need your hands -- hazards, emergency braking,
  scales, your planned stops -- never wait, and a serious speed limit
  drop still speaks the moment it happens.

- **Radio stations hold their signal like real ones.** A station used to
  start crackling barely halfway through its coverage and spend most of
  its life in static. Stations now play clean through most of their
  range, reach about twice as far down the road, and only smear into
  static right at the edge -- so a good station lasts a good while
  before the dial asks for a retune.

- **Clearance and weight signs now say what they mean.** The route readout
  used to stack sign jargon into lines like "Posted restriction in 13
  miles: low clearance ahead: posted 13 feet 6 inches" -- posted twice,
  ahead fighting the distance, and no word on whether you had to care.
  It now says "In 13 miles, a low bridge, signed 13 feet 6 inches. Your
  route clears it." -- because your route really does: anything your
  truck could not pass was routed around before you ever set out.

- **Cruise speed now steps onto the fives, with a fine step when you need
  an exact number.** Setting cruise captures your exact speed, so a
  target like 32 used to step to 37, then 42 -- never landing on the
  fives. Plus and minus now snap to the next five first, the way a real
  cruise stalk does: from 32, plus gives you 35, then 40. And holding
  Control with plus or minus changes the target by exactly one mile per
  hour, for picking a precise number without having to catch it on the
  speedometer. The controller's cruise buttons step by fives the same
  way.

- **A latched throttle now gets out of the way of the speed assists, and
  the Latching pedals setting lets you choose.** A latched accelerator
  used to read as your hand insisting on speed, so cruise, the speed
  keeper, and curve assistance all stood down and the truck just kept
  accelerating. Latching pedals now has three settings. Assists first,
  the new standard, makes the latch the quietest voice in the cab: any
  speed assist that is holding or shedding speed drives the pedal, and
  the latch takes over again the moment it lets go -- no need to redo
  the latch gesture -- and latching while cruise or the speed keeper is
  active says who is holding the speed. Latch first keeps the old
  meaning, where the latch overrides the assists until a safety system
  steps in. Off keeps the plain pedals for fully manual driving. A key
  you physically hold down still overrides the assists in every mode,
  exactly as before.

- **The engine now sounds like you are sitting in the cab, not standing
  beside the truck.** The glass and firewall soften the engine's high end,
  the body carries its low rumble, and the sound sits around you the way a
  real cab delivers it. Testers said the engine felt like it was outside
  the truck -- this is the fix. The classic engine voice is untouched.

- **Running off the pavement no longer talks in a loop.** Drifting onto the
  shoulder or into the median now speaks when it happens, again if it gets
  worse, and once more when you are back on the road -- instead of repeating
  the same sentence every few seconds. Between those moments the rumble you
  hear on the side you drifted toward tells you where the truck is, the way it
  always did.

- **The game starts faster still.** The road detail for every leg in the
  country -- grades, exits, landmarks, posted limits and the rest -- used to
  be built the moment the game opened, whether or not you ever drove those
  roads. Now that work waits until you actually drive a leg, so the world is
  ready about eight tenths of a second sooner and the wait before the menu is
  shorter.

- **Facility names are said in full the first time, then kept short.** The
  first time a stop or facility comes up on a leg you hear its full name;
  after that, on the same leg, just the proper name -- so a pickup no longer
  says "cross-dock Chicago Cross-Dock" over and over. The type word is
  dropped whenever the name already contains it ("port Port of Indiana-Burns
  Harbor" becomes "Port of Indiana-Burns Harbor"), and the full name comes
  back once at the start of a new leg or when you resume from a pause.

- **The game stops repeating instructions you have clearly mastered.** After
  you have started the engine, opened the controls help, or signalled for an
  exit a few times, the truck quits telling you which key does it -- "Press E
  to start the engine", "F1 lists the controls", "Press X to signal for the
  exit" fall away, and the information is still one help key away when you
  want it. If you remap a control, switch a controller in, or move to a
  manual gearbox, the matching prompt comes back until you have shown the new
  control the same way.

- **The Learn game sounds screen now teaches the collision as well as the
  all-clear.** Terse speech uses the hazard-clear chime as the whole "you
  made it" confirmation, so its opposite belongs next to it: the collision
  is now a labelled entry in the Hazards group, right after Hazard clear, so
  you can learn both halves of "did I dodge it?" before it matters.

- **A worsening load stops repeating the same advice.** When the freight
  shifts, the truck tells you to brake and corner gently -- once. If the
  load keeps taking damage, each later warning speaks only the new figure
  and what it will cost at the dock, not the coaching line over again.

- **Achievements stay out of your way while you drive.** Earning a badge at
  speed is now its sound and its name -- "New achievement! Night Owl." --
  instead of a paragraph of story read over the road, in normal speech as
  well as terse. The full write-up is never lost: it waits in the message
  log, in the achievements menu, and at the delivery settlement, where a run
  that earned several badges reads them as one line that names them all
  rather than one paragraph each.

- **The first drive no longer buries you in badges.** Accepting your first
  dispatch, building air pressure, and loading your first trailer used to
  each ding their own achievement, stacked right on top of your first
  delivery -- six or seven dings before you had done anything skillful.
  Those three now fold into a single "First Day" badge at pickup, and a
  rookie chain now spreads the early on-time, clean, and speed-legal
  unlocks across your first several runs instead of all landing on run one.

- **The delivery summary is shorter, and skips the rows that say nothing.**
  When a run added no damage, the truck came in undamaged, and the tank is
  more than a quarter full, the settlement no longer reads those rows out --
  along with "No new career messages" and the standing note that carrier
  charges never come out of your pay. They come back the moment they carry
  news: a run that took damage, a low tank, or a truck now carrying wear all
  still speak. Fewer keypresses to walk a clean delivery.

- **The settings menus are reorganized so things are easier to find.**
  Gameplay is now a category that opens its own submenu of four shorter
  screens: Driving assistance, Difficulty and hours of service, World and
  traffic, and Controls. Weather, traffic, and parking sources moved out of
  Speech and weather -- now just Speech -- and into World and traffic, where
  they belong. Nothing about your actual settings changed; this only changes
  where you find them, and the first time you open Gameplay the game tells you
  so. One confusing leftover is gone too: the speed keeper and the lane
  keeping control each had a duplicate row, and now each has exactly one.

- **Terse speech now actually means less speech.** Terse mode's promise is:
  the truck tells you what to do and what it cost, and nothing else. With
  terse on, achievements are their sound and their name -- the story waits
  in the message log and the achievements menu. Traffic coaching shrinks to
  the facts, in a fixed order you can lean on: "Brake lights, 2 miles, 38."
  Stop callouts drop the instructions and keep what your plan turns on:
  "Flying J Travel Center Corfu, exit 48A, 5 miles. Parking confirmed." --
  and a stop with no verified parking still says so, because shorter never
  means less certain. A charged toll is "Toll, 15 dollars, carrier", the
  toll heads-up before it goes quiet, the speed warning is "Limit 65", and
  dodging a hazard is confirmed by the hazard clear sound alone. Normal
  mode is unchanged.

- **The dodgeable hazard warning says the same thing in every speech
  mode.** Terse mode used to shout "Brake or swerve!" where normal mode
  and the help teach "Brake or change lanes" -- two phrases for the one
  cue where there is no time to wonder. It is "Brake or change lanes!"
  everywhere now, and a test keeps it that way.

- **Road announcements stop cutting each other off unless it is a real
  emergency.** Speed zone entries, checkpoint notices, and construction or
  traffic warnings used to interrupt whatever the road voice was saying,
  exactly like a collision warning -- and every cut was a chance to erase a
  warning you still needed. They now wait their short turn instead: spoken
  within about a second, and repeated if something urgent talks over them.
  Only act-now calls, like a hazard in your lane, still interrupt. To keep
  it fair, staying on the accelerator right after a speed limit drops no
  longer burns your braking grace before the announcement has even had
  time to be spoken.

- **While you drive, screen reader speech waits its turn too.** An
  achievement, an assist notice, or an answer to a status key used to cut
  off whatever your screen reader was mid-way through saying. At the
  wheel those lines now queue and speak when the voice is free. Menus are
  unchanged -- moving through a menu still cancels speech instantly, even
  when the menu is open over a drive.

- **Out-of-date roadside chatter is dropped instead of barging in.** A
  state line or weather note the voice could not get to in time --
  describing miles already behind you -- used to force its way in by
  interrupting. It is now quietly dropped, and kept in the message log if
  you want to read back what you missed.

- **The game starts noticeably faster.** Reaching the main menu is quicker
  on every launch: sound loading now overlaps the rest of startup instead
  of stalling the first sound you hear, the main menu no longer re-reads
  your saved careers three times over, and a few startup checks that only
  matter once you connect an online account no longer run for everybody.

- **Chaining very short hops no longer fast-tracks a career.** The on-time
  streak bonus is now capped at the experience the miles themselves teach,
  so a run of twenty-five-mile hops earns its streak bonus on the driving,
  not on the flat per-delivery award. Real freight is untouched: on hauls
  of about eighty miles and up, streak experience is exactly what it was
  before.

- **The radio plays its full dial out of the box.** Real public streams
  and your own playlists no longer hide behind an opt-in: install the
  game and the whole dial is there. The two radio stream settings are
  now one switch, streamer-safe mode, off by default. Turn it on while
  streaming or recording your drive and the radio keeps to built-in
  safe stations only.

- **The terrestrial category now lists the strongest signal first.**
  Tuning through terrestrial at the start of a run used to open on
  whichever fringe station sorted first by call sign, static and all.
  The strongest signal now comes first, and the weakest last, so a
  category jump lands on a station you can actually listen to.

- **Turning the radio on lands on a station that plays clean.** If the
  station you left the radio on has gone fringe or out of range since,
  switching the radio on now retunes to the strongest signal around
  instead of greeting you with static. A station that still comes in
  clearly -- including your playlists and the Freight Fate stations --
  stays right where you left it.

- **The radio draws power from the engine.** A cab with the engine off
  is silent now: the radio cuts off when the engine shuts down and
  comes back on its own when the engine starts. Pressing a radio key in
  a dead cab says so: "The engine is off. The radio has no power." The
  radio status key and the Tab radio screen explain the silence the
  same way.

- **Merging traffic is now announced without a speed to slow to.** A
  vehicle merging into your lane merges behind you or passes on its own,
  so the call is now "Hold your lane and leave a gap" -- no target speed
  attached. Brake lights and slow traffic ahead still tell you the speed
  to be ready for, because those do ask you to change yours.

- **No merge situation hands you a speed anymore.** The earlier fix only
  covered a single merging vehicle; the same rule now covers traffic
  merging onto your highway and traffic squeezing at a construction
  taper -- both now say to hold your lane and leave a gap, with no target
  speed. Exit traffic ahead is unchanged, since that one really is you
  slowing for your own ramp.

- **CB chatter talks about more than bears again.** Work zones and the
  scale now get their own reports on the radio instead of every post
  sounding like a bear sighting: drivers talk about troopers working a
  work zone, and about logs being checked at the scale.

### Added

- **Game sound can step back while the road talks.** A new option drops
  the engine, the weather, and the radio to half volume while the road
  voice speaks, restoring them the moment the line finishes, so a warning
  survives a loud cab without the voice itself getting louder. It is off
  by default -- the engine note is how many drivers read their speed, so
  nothing changes unless you ask. If game sound talks over your speech,
  turn it on under Settings, Audio, "Game sounds step back for speech."

- **Sixty new billboards along the highways.** Seventeen fresh roadside
  jokes about diesel prices, tiny parking lots, and questionable
  steakhouses join the rotation everywhere. And on the corridors that
  raised the music, tribute signs now mark the territory: Bakersfield
  Sound country on the way up the valley, Hank Williams's Alabama,
  Johnny Cash's delta bottomland, and the Franklin County Trucking
  Company's own home turf on the road through Missouri. Billboards
  still respect the roadside chatter setting.

- **Learn what every sound means before you meet it at speed.** A new
  Learn game sounds screen on the main menu, and on the pause menu while
  you drive, plays any cue the road uses on demand. Arrow to a sound,
  press Enter to hear it exactly as the drive plays it -- panned to the
  side it comes from, held for as long as it would really run -- and
  press F1 for what it is telling you and what to do about it. Sounds
  that explain themselves, like the engine and the weather, are left out
  so the list stays worth reading.

- **The game now tells you when you are backing the wrong way.** You
  could put the truck in reverse on the open highway and back up for as
  long as you liked, giving the route back mile after mile, and the only
  thing you would hear was the navigation still calling out the exit you
  were reversing away from. Now the truck speaks up: first that you are
  still in reverse and moving away from your destination, then that
  backing on a travelled lane is illegal and how much of the route you
  have given up, and if you keep going, traffic finds you. Backing where
  it is your job -- in the yard, at a stop, lining up on the receiver's
  dock -- stays silent, as it should.

- **The alpha test book now comes with the build.** The checklists are
  written against particular builds, so testers had to go and find the
  current copy for themselves and could easily end up working an old one.
  Every download now carries it alongside the manual and the changelog, as
  both a plain text file and a page you can open in a browser.

- **The truck now tells you when the lane you passed in is open again.**
  Moving over to pass was a one-way trip: nothing said when you were clear
  of the slower vehicle, so coming back was a guess and a mirror you cannot
  check. Once you are past and there is room to spare, the truck says so --
  "Clear of the box truck. Right lane open." -- once, using the same
  judgment that decides a sideswipe, so a lane it calls open is a lane you
  can take. Press L any time for the same reading on demand: your lane,
  and whether each neighbouring lane is open, blocked, or closed.

- **You now choose which career is your public one.** Your public profile on
  orinks.net shows one career. Until now that was quietly whichever career
  happened to back up first, so playing several careers could put the wrong
  one's level, statistics, and badges on your profile. The Cloud backup menu
  now says "your public career" on the career that fronts your profile, and
  every backed-up career offers "Make this your public career," with a spoken
  confirmation before anything changes. Your other careers keep backing up
  privately; they just stay off your profile.

### Fixed

- **The exit calls stop being talked over.** Every announcement that gets
  you off the highway -- the exit ahead, the exit lane, the gore, and the one
  that tells you lane keeping is taking your destination exit for you -- was
  treated as chatter, so another line landing at the same moment could push
  it out. With lane keeping on full that meant the truck left the highway
  without the warning that it was about to, which reads as the exit taking
  itself. They now come ahead of ordinary road talk.
- **The ramp's traffic light stops going quiet on you.** The lines that get
  you to the stop bar -- the light changing, how far the bar is, and route
  transition assistance telling you it is braking for the light -- were
  treated as chatter, so any other announcement landing at the same moment
  pushed them out entirely. On a busy ramp that meant the truck braked for a
  light and said nothing about it, and going through on a yellow was never
  mentioned. They now take priority over ordinary road talk, the same as the
  exit you are taking.
- **The last call before your exit no longer says "in 0 miles".** Once you
  were inside a mile of a destination exit, the distance was rounded to whole
  miles and came out as zero, so the announcement sounded like the exit had
  already gone by while you still had a third of a mile to take it. Inside a
  mile you now hear a quarter mile, half a mile, or one mile; further out it
  still counts down in whole miles.
- **Other traffic now drives at the speed of the road it is on.** Cars and
  trucks around you ran at fixed speeds that were set before the game knew
  the real posted limit of every road, so on a 75 mile per hour interstate
  everything around you was doing 30 to 55, and the truck would tell you to
  leave room for 30 for a semi on an open highway. Traffic is now paced off
  the limit where it is: it keeps up on a fast corridor, and it slows down
  properly through a town. In states where cars may go faster than trucks,
  the cars going past you really are doing the higher legal number.
- **The speed alert stops dinging once you have slowed down.** It arms at
  seven over, which is where it should be -- but once it had armed it kept
  chiming until you were within one mile per hour of the limit, so a single
  trip over the line nagged you all the way down through six, five and four
  over while you were already slowing. It now goes quiet as soon as you are
  back under the speed it armed at, and holding five over never sounds at
  all.
- **A refused backup now says when the server is the one that is behind.**
  If orinks.net does not recognise the town your career is parked in -- which
  happens when the site has not caught up with a build that added it -- the
  refusal used to be the general "backup not accepted" line, with nothing to
  say why or what to do. It now tells you the server has not caught up, that
  your career on this computer is safe, and that backups resume on their own
  once it has.
- **The truck no longer builds speed for a hill the grade key says is not
  there.** Automatic speed control plans for gentler grades than the ones the
  game calls steep, so you could hear "building speed for the grade ahead" and
  then press G and be told nothing steep was coming for fifteen miles. The
  cue now names the grade it is working for -- "building speed for a 2 percent
  upgrade ahead" -- and G names that same pull after it tells you nothing
  steep is coming, so both answers describe the same road.
- **G now tells you when a grade you are already on is about to get worse.**
  A two percent descent that steepened to six without flattening out in
  between was reported as nothing steep ahead. G now says it steepens, how
  far off it is, and how long it runs. On a steep grade already, the answer
  is "nothing else steep" rather than a flat contradiction of the sentence
  before it.
- **When orinks.net stops accepting this computer, the game now points you at
  a setup that still exists.** The spoken advice described the old
  copy-and-paste connection: an Add computer button on the website and a
  token to paste back into the game. Neither is there any more. It now walks
  you to the Online menu item that asks orinks.net for a fresh activation
  code, the same way connecting a computer works everywhere else.
- **A one-lane road no longer calls itself the right lane.** Pressing L on a
  road with only one lane answered "In the right lane", which invites you to
  wonder what is in the left one when there is no left one. It now says "In
  the lane" and reports your position in it as usual. The call that moves you
  when the road narrows to a single lane has stopped naming a side too.
- **Automatic speed control comes back on its own after a ramp's stop bar.**
  Taking an exit used to switch off both adaptive cruise and the speed
  keeper for the rest of the run, and you had to turn them on again by hand
  to get back up to speed on the approach. Now the ramp only borrows them:
  once you have honored the light or the sign and you are rolling again,
  automatic speed control picks up where it left off, with nothing to press.
  A destination exit still holds it until you leave with your next load, and
  nothing switches itself back on while you are still slowing for the bar.

- **Signalling for an exit early no longer slows you down early.** Signal
  nine miles out and the truck used to start shedding speed straight away,
  with the exit nowhere in sight. Now it holds road speed until it is close
  enough to genuinely need to slow, and how close that is depends on how
  fast you are going: quicker means starting a little sooner. The approach
  itself now runs at real-time pace, the way a ramp and a hard bend already
  do, so the last mile gives you real seconds to work with, and pacing eases
  back up afterwards instead of jumping.

- **Exit speed assistance now carries you to the exit, not just down to
  ramp speed.** It used to slow the truck for the ramp and then let go of the
  pedal entirely, so if you were not driving yourself the truck coasted the
  rest of the way and could roll to a dead stop in the lane, short of your
  own exit. It now holds ramp speed to the gore. Your own pedals still come
  first: brake and it stands aside.

- **Your own playlists work again, and they can now carry internet stations
  as well as music files.** A playlist exported from an internet radio app
  is nothing but station addresses, and every one of those was thrown away,
  so the playlist ended up empty and no station ever reached the dial -- with
  nothing said about it either way. Now a playlist plays whatever it lists,
  music files and internet stations together, in your order, and a stream is
  given time to connect rather than being skipped for being slow. PLS
  playlists are read alongside M3U and M3U8. If nothing in a playlist will
  play, the radio tells you that and names the Playlists folder instead of
  going quietly silent. Opening the Radio status screen re-reads the folder,
  so a playlist you add or repair mid-drive shows up without starting a new
  run.

- **The route report now gives you a real distance as you close on a
  gate.** R used to round everything down to whole miles, so the last half
  mile to a facility gate answered "0 miles to the gate" over and over
  while you were still driving it. Now it counts down in quarter miles and
  then in feet, right down to the entrance. On city streets it also names
  the street under your wheels instead of a highway you already left, and
  pulling out of a gate it counts you down to the on-ramp instead of
  claiming you are partway through the run.

- **The coming-up key is shorter, and no longer reads out police
  activity.** U used to recite the next exit, traffic pressure, patrols
  and three bends on top of everything else, most of which already has its
  own key. It now answers only what nothing else does: the ramp control
  ahead, the next imposed speed limit, the next stop, and the next bend
  that will demand slowing. Enforcement still reaches you on the CB.

- **Saving the game now backs up your career right away and tells you how
  it went.** Choosing Save game at the terminal used to run the cloud
  backup silently in the background some seconds later, so "Game saved."
  sounded exactly the same whether the backup worked, failed, or never
  ran. Now the backup starts immediately and one line follows with the
  result: backed up, already backed up, or exactly what went wrong and
  where to fix it. If your account is set up but cloud backup is off,
  saving says that too instead of leaving you to assume you were covered.

- **A refused cloud backup now says so wherever you are.** The automatic
  saves -- rest stops, motels, deliveries, sleeping, business at the
  terminal -- back up in the background, and until now a refusal only
  changed a status line in the Cloud backup menu, so a career could stop
  backing up without a word. Now the game says it out loud the first time
  it happens, wherever you are: which career was refused and why -- the
  save was not accepted, the cloud copy changed on another computer, or
  your sign-in needs reconnecting. It says it once, not on every retry,
  and when that career's backups start being accepted again it tells you
  that too, by name: backed up again. Ordinary network trouble stays
  quiet and simply retries.

- **A highway narrowing to one lane now tells you when it moves you.** If
  the lane you were in stops existing where the road narrows, you used to
  be shifted over with no warning at all. Now, whenever that actually
  moves you, you hear it and are told which lane you landed in. Already in
  the lane that survives, nothing changes -- it stays silent, same as
  before.

- **A road message that rings its chime now always reaches you -- spoken,
  or at worst waiting for you in message review.** A lane closure, a
  construction taper's merge call, or other roadside colour could ding and
  then say nothing: the words were waiting behind other speech when a
  hazard or a newer notice cleared them out, so the chime played but
  nothing was ever spoken and nothing was there when you checked message
  review afterward. Every line that rings a chime is now recorded the
  moment it is queued, not the moment it is spoken, so it is never lost
  from review even when speech is. Lane closures and work-zone entries and
  warnings also stopped being droppable outright: they now wait in line
  like a planned stop instead of being thrown away.

- **Changing lanes no longer makes cruise slow down for the car you are
  leaving behind.** With adaptive cruise or the follow cue on, passing used
  to have the truck ease off mid-maneuver for slower traffic in the lane you
  were pulling out of. Now, for as long as the lane change is underway, the
  truck drives toward the lane you are entering instead.

- **Changing lanes no longer switches automatic speed control off -- only
  braking does.** Dodging a hazard by changing lanes with adaptive cruise or
  the speed keeper on used to cancel the session outright the instant the
  hazard was called, even if you never touched the brake. Now cruise and the
  keeper stay on through a dodge; only your own brake, the automatic brake
  taking over, or a hazard you never answer at all reaching the truck ends
  the session.

- **When a cloud backup is refused by the server, the game now says so
  instead of blaming your connection.** Retrying "Keep this computer's
  save and back it up" after the server rejected a save used to say
  "Check your connection", sending you off to troubleshoot a network
  that was never the problem. It now tells the real story: a network
  problem still says check your connection, a sign-in problem tells you
  to reconnect, and a save the server flatly refuses says so plainly and
  points you at reporting it, instead of guessing.

- **A refused cloud backup now names the career and the reason.** Both the
  automatic backup status and the "Keep this computer's save and back it
  up" retry used to say only "Backup not accepted" no matter which career
  it was or why, so with more than one career backed up you could not
  tell which one had failed. Both now name the career every time, and
  tell a different story depending on the cause: your game and the
  server disagreeing about a save's shape usually just means a build
  mismatch, while a save whose numbers do not add up says plainly that it
  was flagged for review, and that you can say so if you think that is
  wrong.

- **When two hazards stack, the all-clear now names both.** A deer, then
  slowed traffic right behind it, used to leave you with only one vague
  "Hazard avoided" -- the deer's own outcome never spoken, and the wording
  fit only the second hazard. Every hazard you clear is named now, alone
  or stacked: "Past the deer and the slowed traffic. Well done." No more
  wondering whether you missed the deer.

- **"Lane open" now means open long enough to take it.** The clear-of-traffic
  call and the L lane readout used to describe the lane at the instant you
  asked, so a car you were catching fast -- slowed traffic ahead, or someone
  quick coming up behind -- could reach your blind spot in the seconds it
  takes to hear the answer and drift across, and the lane you were honestly
  told was open ended in a sideswipe. Both readings now look far enough down
  the road to cover the whole move, so when the truck says a lane is open, it
  stays open until you are in it.

- **Choosing the classic engine voice brings back the original engine.** The
  Engine voice setting under Settings, Audio could end up playing the new
  cab recording stretched the old way instead of the sound it promised.
  Classic now always means the engine from earlier versions of the game,
  exactly as it was.

- **Resuming cruise to a high speed no longer floors the engine to get
  there.** Bringing automatic speed control back with Shift+K, or setting it
  when your remembered speed was far above the truck's, used to open the
  throttle all the way at once to close the gap -- loud on the flat, and on a
  downgrade it screamed the engine past redline and wore it down. Cruise now
  eases up to the set speed at a comfortable pace, lifts off the throttle as
  the engine nears its limit, and waits until you are at road speed before it
  takes over on the open road. No more redline scream, and no engine wear,
  from resuming cruise off the line.

- **Terse speech no longer silences your first-drive walkthrough.** If you
  set speech to terse before your very first run, the game used to skip
  the walkthrough entirely -- so you were never told about the speed key,
  the status report, the help key, or what to do when a hazard warning
  sounds. First-run guidance now speaks in full whatever your speech
  setting, and terse takes over the moment the walkthrough is done.
  Finishing it and then switching to terse brings none of it back.

- **What something cost is now always said.** A charged toll, a fine, or a
  citation could be lost without a word if the road was talkative at the
  wrong moment. Money lines now ride the same never-dropped queue as route
  instructions, so what it cost always gets spoken. The "toll point ahead"
  heads-up stays ordinary chatter -- losing the preview costs nothing once
  the charge itself is guaranteed.

- **A ten-hour out-of-service order now shuts the engine down.** Every
  other overnight stop -- sleeper berth, lot, shoulder, motel -- killed the
  engine first; a trooper's out-of-service order skipped it, so the engine
  kept running while the wake-up line told you to start an engine that was
  already on. The order now shuts the engine down like everywhere else,
  and if ten hours parked with it off bled the air down, it tells you to
  build pressure again before you release the brake.

- **A big delivery now announces every rank it passes through.** Jump
  three levels in one haul and only the last promotion used to get a
  line -- the ranks in between, and the unlocks that came with them, went
  unspoken. Every rank you pass now gets its own "Level up" line, in
  order, so nothing you earned goes unheard.

- **Running off the road asleep a third or fourth time now says so.** The
  line telling you it happened again was stuck at "twice now" no matter
  how many times it actually happened. It now counts honestly: twice,
  three times, four times, and on from there.

- **Docking and checking in no longer freeze the engine sound.** Pulling
  into a delivery dock or a pickup gate could leave the engine note stuck
  at whatever rev it was carrying on the approach, revving or lugging
  through the whole stop no matter what the truck was actually doing. The
  engine now settles to a real idle the moment you stop, the same fix
  already shipped for a roadside police stop.

- **A missed destination exit's loop-back now costs what it says it does.**
  Blowing past the destination exit loops you back through the next safe
  turnaround on twenty minutes of clock time, but your hours of service,
  fatigue, and fuel never moved -- the same free-time gap the facility
  gate's loop just had closed. The exit loop now charges real driving
  hours, real fatigue, and a small idle sip of fuel, exactly like the
  gate's.

- **A missed facility gate's loop-back now costs what it says it does.**
  Carrying past the destination gate too fast loops you back for another
  try, and the game always said your hours, the clock, and your fuel kept
  running through it -- but only the clock actually did. The loop now
  spends real hours-of-service time and real fatigue, and burns a small
  idle sip of fuel too, so the line matches what happens.

- **Nineteen radio stations got their apostrophes back.** Imported station
  names like The Big Buffalo s Oldies now read naturally on the dial
  instead of with a stray broken s.

- **Important road announcements that get talked over now repeat themselves
  instead of vanishing.** A hazard warning, a curve call, or an answer to a
  status key could cut off a weigh station notice or a planned stop
  announcement mid-sentence, and the rest of the line was simply gone -- one
  tester blew straight past a weigh station that way. Now the urgent line
  still speaks first, and the announcement it talked over speaks again right
  after it, whether events use their own voice or your main one.

- **The weigh station announcement and the T key now tell the same
  story.** The open-scale call used to end with "press T for inspection
  check-in", but T at highway speed plans a sleep stop -- so following
  the instruction planned a truck stop past the scale, X armed that
  exit instead of the scale's, and doing exactly what the game said
  ended in a bypass pull-over. The announcement now tells you to slow
  below fifteen and signal for the scale exit with the exit key, and to
  press the rest key once you are stopped at the scale. Pressing the
  rest key near an open scale now reminds you the scale comes first
  instead of planning a stop, the exit key prefers a nearer open scale
  over a planned sleep stop, a short reminder speaks half a mile out if
  you are still fast, and if a trooper does light you up, any armed
  exit stands down so the stop is the only thing asking for your hands.

- **Turning streamer-safe mode on now takes effect on the air, not just
  on paper.** Flipping it on from the settings while a real public
  stream was playing left the stream running -- the one thing the mode
  exists to stop -- while the dial silently moved to the silent
  fallback, and turning the mode back off left the radio parked on that
  silence. Now the station leaves the air the moment you flip the
  switch, the cab says so, and the radio lands on the Roadhouse like
  any other handover.

- **The static dies with the station it belongs to.** When a station
  faded past the edge of its range and the radio fell back to the
  Roadhouse, the dead station's hiss and noise splashes kept crackling
  over the new station for a second or two, holding the music quiet.
  The handover now cuts the static the moment it speaks.

- **The Skip on the Far End badge means what it says again.** It is
  meant for pulling in a station from beyond its coverage thanks to
  high ground, but it was awarded for riding any station into its own
  static, so every fading signal handed it out. It now takes a catch
  genuinely past the station's normal reach.

- **The speed keeper comes back up to street speed.** Its number could
  only fall: a session that started on a 15 mile-per-hour service way
  held that crawl over every 25 mile-per-hour street after it, for the
  whole facility approach, even while the zone entry announced the
  higher limit. A new posted number now hands the keeper back up, and
  it says so: "Speed keeper holding 25 miles per hour through the
  facility access road zone." It also stops matching a slower vehicle
  it can see miles ahead -- easing starts when the distance calls for
  it -- and its slow-down for a drop no longer starts a stretch too
  early. Creeping up to a stopped queue and a speed you set by hand
  both work as before.

- **Automatic braking stops the truck on the service brakes, and stops
  draining your air.** The hazard assist pumped the pedal -- pressing,
  easing off as the stop improved, pressing again -- and every re-press
  cost another shot of air, which is why long assisted drives kept
  running the tanks down. Worse, its emergency escalation never actually
  reached the wheels, so "Emergency braking engaged" spent your air and
  gave nothing back. The assist now takes one full service application
  and holds it to the end of the stop -- one application, one air cost --
  and says simply "Automatic braking." The emergency application is
  reserved for the moment the truck is measurably failing to slow, and
  now it really happens when you hear it.

- **A dropping speed limit is one announcement, heard in time.** The
  advance call -- "Speed limit drops to 45 in half a mile" -- used to
  fire so close to the drop that at the game's pace the sentence was
  still being spoken when the limit changed, and then "Speed limit
  reduced to 45" repeated the same number, and cruise repeated it a
  third time. The advance call now comes early enough to hear and act
  on, and once you have heard the number -- from the call or from
  cruise easing to it -- the arrival confirmation stays quiet. A limit
  that changes with no warning still announces itself, and raised
  limits speak as before.

- **Hazard warnings stop telling you to change lanes when there is no
  lane.** On a one-lane road -- or beside a lane closed for roadwork --
  the warning said "Brake or change lanes!" and the reminder said
  "Nearly stop, or change lanes," while the lane keys could only answer
  that no lane exists. When there is nowhere to swerve, the truck now
  says plainly what works: "Brake!" -- and slowing alone has always been
  enough to clear the hazard.

- **Rolling past the stop at your destination's entrance now loops you
  back instead of stranding you.** If you cleared the ramp at the end of
  a delivery too fast to make the stop, nothing happened at all: no
  consequence, no reminder, just an endless quiet ramp -- and worse, a
  paused cruise session could quietly resume and drive you away from the
  very stop you were told to make. Blowing the entrance now works like
  missing the gate anywhere else: you hear what happened, you loop back
  through a safe turnaround with the clock running, and the entrance is
  ahead again. Cruise also stays out of it from the moment you take the
  destination exit until you have actually stopped.

- **The cloud backup list now tells you how to fix a conflict.** A career
  whose backups stopped because another computer changed the cloud copy now
  says, in the list and inside the career, that opening it lets you choose
  which copy to keep.

- **Cloud backup no longer goes quiet after the cloud copy of a career
  disappears.** If your account's cloud storage was reset, or you deleted a
  career's cloud backup from another computer, this computer still remembered
  the old cloud copy and treated the mismatch as a conflict -- and from then
  on it silently stopped backing that career up. That also trapped careers
  whose conflict was real when it was noticed but whose cloud copy later
  vanished. The game now checks whether there is anything in the cloud left
  to protect before staying quiet, starts the career's backups over fresh
  when there is not, and your next save is backed up as usual. Careers with a
  genuine conflict -- a newer copy really is in the cloud -- still wait for
  you to choose a side in the Cloud backup menu.

- **One dip in air pressure is one warning.** Hard or repeated braking
  drags air pressure down around the warning line while the compressor
  catches up, and every little dip below it re-fired the full low-air
  warning. The warning now speaks once and stays quiet until pressure has
  properly recovered -- though the spring-brake emergency at 40 psi still
  speaks the moment it happens, no matter what.

- **Driver name entry now has a caret you can steer.** The arrow keys did
  nothing in the name field, so the only way to find a typo was deleting
  back to it. Left and right now walk the name a character at a time and
  speak each one -- capitals marked, space called out -- Home and End jump
  to either end, and typing and backspace work at the caret, so fixing one
  wrong letter no longer costs the rest of the name.

- **The speed keeper no longer misses the second corner of a short block.**
  On city streets the keeper eased for the corner in front of it and held
  that number through the turn -- and a downtown block is shorter than that
  hold, so the next, slower corner was invisible until too late and the
  truck arrived over the speed the turn needed. Every corner close enough
  to matter now bids, and the slowest one wins.

- **Pulled over means idling, not revving.** When an officer waved you to
  the shoulder, the engine sound kept whatever rev it had when the lights
  came on, and held it there for the whole stop. The truck now settles to
  idle at the roadside, like a truck actually stopped at the roadside.

- **Sleeping at a motel now shuts the engine off.** Every other rest --
  sleeper berth, lot, shoulder -- killed the engine before you slept, but
  a motel room left it running all night, so the game still called it
  running while the wake-up message told you to start an engine that had
  never stopped. The motel now shuts it down like everywhere else, and the
  morning prompt is finally telling the truth.

- **Live weather rides out a quiet station instead of lurching to neutral.**
  When the nearest weather station stopped reporting fresh observations,
  the game dropped your route's weather to temporary neutral conditions and
  kept retrying loudly. It now asks the next-nearest station instead -- the
  closest one is not always a live one, and one parked station used to pin a
  whole stretch of road to fallback weather -- and only when every station
  nearby is quiet does it hold the last real weather it knew until a fresh
  report arrives. Either way, a station gone quiet no longer changes what
  you hear on the road.

- **Date badges now fire on the date you were actually told it is.** With
  the real-time calendar on, April's Fool could arrive in August. A career
  keeps two clocks -- how long you have been driving, and what the
  calendar says -- and every date you hear comes from the second one,
  while these badges were quietly reading the first. Christmas, New Year,
  Friday the thirteenth and the seasonal badges were all reading the
  wrong one too, so a delivery could be counted as a winter run while the
  weather outside said otherwise. They all follow the calendar you hear
  now, whether that is the real date or your career's own.

- **When the truck brakes for you, it now actually stops in time.**
  Automatic braking used the normal brake pedal, held flat out. That is
  enough on a sound truck, but a stop on hot, worn brakes in the wet
  going downhill gets slower while it is happening -- the drums heat up
  under the very application meant to save you -- and the truck could
  ride it all the way into the thing it warned you about. It now starts
  with the normal brakes as before, and if the time left is no longer
  enough for those alone, it stands on everything, the same hardest stop
  you get from the emergency brake yourself. On good brakes on level
  ground nothing changes; you will not get a violent stop you did not
  need.

- **You now get time to answer a hazard warning before the truck brakes
  for you.** "Brake or change lanes" was followed almost instantly by
  automatic emergency braking -- often inside half a second, sometimes
  before the warning had finished being spoken, and on hot brakes or a
  downgrade it fired on the same breath. There was no version of that
  you could beat: a lane change alone takes two and a half seconds to
  make. The warning now comes far enough ahead that you always have time
  to hear it out and act, whatever the truck's speed, the grade, or the
  state of the brakes, and if you are already moving into the next lane
  when the assist would have engaged, it waits for you to finish rather
  than snatching the truck back. Automatic braking still catches you if
  you do nothing.

- **The posted speed limit stops flickering for no reason.** On long runs
  the limit would drop and come straight back with nothing on the road to
  explain it -- in places an 80 became a 45 and an 80 again inside a
  second. Those were never signs: the map splits a road wherever any
  detail about it changes, and a few hundred feet of that is invisible at
  real driving speed but goes by in a blink at the pace the game runs.

  A posting now has to hold long enough to be a sign before the truck
  obeys it, and long enough is measured in the seconds you actually spend
  inside it rather than in miles -- because a mile of a 70 goes by in
  under three seconds while a mile of a 30 takes over ten, and only one
  of those is a flicker. Nothing on any road in the game now changes the
  limit for less than three seconds, and the only changes shorter than
  six are drops to a town speed beside a village the game names out loud,
  so there is always something on the road to explain what you heard. A
  quarter of the postings on the map went, and Strawberry's 35 is still
  Strawberry's 35.

- **Hairpin bends that no road could hold are gone from ordinary roads.**
  Sharp switchback calls were turning up on US and state routes well away
  from the mountains, most often within a mile or two of leaving a town.
  Those came from the shape of the city streets at the start of a leg
  being read as part of the highway, and from a handful of bends tighter
  than a loaded truck's own turning circle. Both are now filtered out, on
  every road in the game. Real switchbacks are untouched: nothing in
  mountain country was removed, so the Million Dollar Highway and the Salt
  River Canyon still bend exactly as hard as they always did.

- **A trooper who saw you no longer forgets because you were busy.** If a
  police contact happened while something else already had your attention
  -- a hazard warning, an exit, a pull-over -- the game held the officer's
  look back so you were not handed two things at once, and then never gave
  it back. On a long run that could mean speeding the whole way and never
  being stopped. The look is now taken when it happens and acted on as
  soon as the cab is quiet, and only dropped if the officer is too far
  behind you to have realistically caught up.

- **The reconnect advice now covers the case where the account is gone,
  not just this computer.** When orinks.net stops accepting your sign-in,
  the game told you to open your driver setup page and choose Add
  computer. That is right when this computer was signed out, but there is
  another way to get the same refusal: the driver itself no longer exists
  on the site, which can happen after the site is rebuilt. Following the
  old advice then led nowhere, because there was no account left to add a
  computer to. You are now told how to tell the two apart, and what to do
  in each case.

- **The assists no longer empty the air tanks stopping for a light or a
  stop sign.** Coming down a ramp to a signal or a sign, route transition
  assistance was pumping the brake pedal several times a second instead
  of holding one steady application. Air went out of the tanks faster
  than the compressor could put it back, and on a bad approach the
  pressure fell far enough that the spring brakes slammed on and stopped
  the truck in the road, short of the line. It now sets the brake once
  and holds it, which is both how a driver does it and what the tanks
  are sized for.

- **The speed keeper no longer stalls the truck on a downhill.** Holding
  a lower speed on a grade, the keeper was doing the same thing: dabbing
  the brake over and over rather than holding it. On anything from a
  gentle two percent down, it could run the air out in under twenty
  seconds, set the spring brakes and leave you parked in a live lane
  with the parking brake latched. It now takes one firm application and
  holds it until the speed is where it should be.

- **When an assist cannot hold your speed, it says so.** On a grade
  steep enough, or with hot brakes or ice underneath, there is a point
  where the assist has everything applied and the truck is still
  running away. It used to just quietly keep losing. Now you are told,
  once: the assist cannot hold the speed here, and you need the service
  brakes yourself.

- **Low air warnings no longer give parked-truck advice to a moving
  driver.** Running low on air at speed, the game told you to keep the
  parking brake set until pressure builds, which is advice for a truck
  that is already stopped. Rolling, you are now told to get stopped and
  let the compressor build, and that the spring brakes set at forty psi.

- **The speed keeper now slows down before a corner instead of at it.**
  Driving to a shipper or a truck stop on city streets, the keeper would
  arrive at a turn still doing the street's speed, and it could not get
  down to the corner's twenty in time. Often you missed the turn
  outright, which cost you eight minutes going around the block -- and
  the keeper switched itself off when that happened. It now looks ahead
  to the next turn or the next lower limit and starts easing early
  enough to arrive at the right speed. The corner call tells you when
  the keeper is taking it.

- **The engine brake is for hills now, not for corners.** The truck used
  to engine brake its way through bends -- loud, constant, and not how
  anyone drives. Slowing for a corner is the ordinary brakes' job, and
  that is now true whoever is driving: the curve assist, adaptive
  cruise, and the automatic gearbox all leave the engine brake alone for
  a bend on level road. Three separate parts of the truck were doing it
  and each has been dealt with, including one that kept the engine brake
  running into a corner when the hill it was holding back ran out.

  Hills are untouched, because that is what the engine brake is for. A
  long descent is still held on it, and a bend part-way down a grade
  still gets it. What changed is that a corner on the flat never does.

  Why it matters beyond the noise: the engine brake pulls on the drive
  wheels only, and a bend is the worst place to be pulling on just those
  -- it is how a trailer comes around on you. Slowing before the corner
  and rolling through it on gentle throttle is what the training says,
  and it is now what the truck does.

- **A construction zone can no longer close the only lane you have.** On a
  stretch of road with one lane your way, a work zone could still cone off
  that lane. The game then told you to move over to a lane that was not
  there, and when you could not, drove you through the barrels for it --
  again and again, damaging the truck and the load each time. Backing out
  earned you a wrong-way warning, and the only way out was to quit to the
  menu and lose the run. Work zones now only close a lane where the road
  really has another one to give you, the whole way through, and if you
  ever do end up somewhere with nowhere to go, the game stops asking.

- **Pulling into a weigh station no longer counts as driving past it.**
  You could signal, take the ramp and be on your way into the scale, and
  still be pulled over and fined 750 dollars for blowing past it. The
  check was looking at your speed at the moment you passed the sign,
  which on the ramp is always too fast. Now taking the scale's own exit
  is exactly what it looks like. Arming the exit and then carrying on
  down the highway is still a bypass, so nothing is gained by faking it.

- **A fine you have already paid is not charged again when you come
  back.** Paying a roadside fine and then returning to the title screen
  meant the stop was waiting for you on your next drive, and it charged
  you again -- for more each time, because it counted the ticket you had
  just paid as a previous offence. One tester lost most of a career's
  money this way. A stop that has been settled now stays settled. This
  covers speeding tickets too.

- **The highway has traffic on it now, and you can hear it go by.** The
  road was very nearly empty -- a few vehicles at the start of a run and
  fewer as it went on, because nothing ever replaced what you drove past
  and nothing ever came up from behind you. On top of that, the pass-by
  sounds for cars, box trucks and semis could not play at all: they were
  only ever attached to a warning about a vehicle ahead, so traffic going
  past your cab was silent. Now the road stays busy around you, vehicles
  come up behind and overtake, and you hear each one go by on the side it
  passed on. How busy it is follows the clock and the weather as you
  drive, so a night run is quiet and a morning one is not, and a long
  trip changes as the hours pass instead of keeping its departure hour's
  traffic all night long.

- **Traffic no longer thins out because of your difficulty or pacing
  settings.** How many vehicles were on the road was being multiplied by
  the random-hazard setting and by your time compression, which between
  them could empty an interstate. Neither of those is a statement about
  how much traffic exists, so neither touches it any more: the road has
  the traffic it has, the same way it has the police it has. Your hazard
  and pacing settings still do everything else they did.

- **A full truck stop no longer means you cannot fuel there.** When the
  overnight parking at a stop was full, the whole stop closed to you --
  your only choices were to drive on, take a motel room, or sleep on the
  shoulder, even at a big truck stop with its pumps right there. On a
  night run that could mean passing stop after stop and running the tank
  dry. The parking lot and the fuel island are separate things now: a
  full lot still costs you the parking, but you can pull to the pumps,
  fill up, and then decide where to spend the night. Stops with no fuel
  of their own, like a plain rest area, are unchanged.

- **Stopping hard no longer wrecks a load that was tied down properly.**
  A firm stop at a light used to be enough to put general freight over
  the line into an exception on the bill, and a load of food or
  electronics close to a claim, from one stop. That was never right:
  freight is secured to survive far harder braking than a truck can
  actually produce. Now a full brake application costs the load nothing,
  however alarming it sounds. Slamming on the emergency brake still
  reaches the freight, and so does a hard stop with a grade pushing you
  down it.

- **Sharp bends are now the ones that hurt the load.** The game used to
  count only how many miles an hour over the advisory you were, so a
  gentle sweeper taken fifteen over cost the freight more than a tight
  mountain hairpin taken the same fifteen over -- even though the
  hairpin throws the load half again as hard. Now it is the sideways
  pull of the bend itself that moves the freight, so the tighter the
  corner, the less room you have over the sign. Taking a bend at its
  posted advisory is free on every curve in the game.

- **A roadside stop that pulls your licence now ends the run properly.**
  Losing your CDL at the roadside still left "Pull back onto the
  highway" as your only choice, so the game took your licence and then
  invited you to drive off with it, with no way to end the trip from the
  shoulder. Now the stop says plainly that you cannot drive the truck
  away, hands the load back to dispatch, and releases you to the
  terminal -- where waiting out the suspension is waiting for you. An
  ordinary ticket still just puts you back on the road.

- **Phantom hairpin turns are gone from ordinary highways.** Some US and
  state routes carried impossibly sharp curves on flat ground, left over
  from how routes were originally traced, so you could hear a hairpin
  warning and slow way down where the real road runs straight. Those are
  now screened out. Real switchbacks in the hills and mountains, like
  the Million Dollar Highway, are exactly as sharp as ever.

- **Cloud backups of 1.9 careers are accepted again.** The server was
  quietly refusing every backup of a company-driver career because it
  still expected drivers to own their truck, which 1.9's assigned
  tractors ended. Your next save after this fix backs up normally; no
  game update is needed. The Cloud backup menu also now says plainly
  when cloud backup is turned off instead of claiming it is ready, and
  offers to turn it on right there.

### Changed

- **Connecting your orinks.net account now turns your public profile and
  cloud backup on.** Connecting used to switch nothing on: profile
  sharing and cloud backup each needed their own separate yes afterwards,
  so drivers who connected and drove away found a public profile that
  said "no career statistics yet" and stayed that way. It said that
  because those statistics are read out of your cloud backup, and there
  was no backup. Connecting now starts both, so your profile fills in
  from your first delivery. The game says so before you connect, in the
  first-run offer, on the setup screen, and in "Hear what gets shared" --
  and each one is still a single item on the Online menu whenever you
  want it off. If you are already connected, nothing changes: whatever
  you chose stays exactly as you left it.

- **Owner-operators now start with a brand-new truck.** Starting as an
  owner-operator used to hand you a tractor that was already four percent
  damaged and two thirds full of fuel, which read like something handed
  down to you rather than something you had just bought. You are buying
  in, so you are buying new: a full tank, no damage, and nothing worn.
  This start is still the hardest way to begin -- fuel, repairs, reserves
  and settlement fees all come out of your own cash, and your working
  capital is thin -- but the truck under you is yours and it is new.

- **Driving through the barrels in a construction zone now costs you.**
  Riding a closed lane until you plough through the cones used to cost
  only truck damage. It is now a fine and a serious mark on your safety
  record, the way running a construction zone really is. You are charged
  once for a given zone no matter how many barrels you take out, and you
  are never charged when the road left you no open lane to move into.

- **Fines across the board now match what they cost a real trucker.**
  Nearly every penalty in the game was a fraction of the real thing.
  Driving with unsafe equipment goes from 900 dollars to 2,300, running
  an open scale from 750 to 1,800, following too close from 250 to 600,
  and improper lane use from 175 to 500. Chain law, lights, shoulder
  parking and failure to stop all rise too. Speeding was already set
  against real schedules and has not changed.

- **Two things now make a fine bigger.** Any fine you earn inside a
  construction zone is doubled, the way most states really do double
  them, and the taper counts as inside because that is where the signs
  stand. Every prior citation in your career also raises the next one,
  which used to apply only to speeding. The two stack on top of each
  other, so a second run past an open scale in roadwork is 5,400 dollars.
  Both stop climbing after the third citation, and no single fine can
  ever cost you the truck on its own. When a fine has been doubled, you
  are told why, and every spoken fine now says the amount actually taken
  from you rather than the base.

- **You never pay a fine into a hole.** Worth saying plainly alongside
  the bigger numbers above, because it has always been true and is easy
  to miss: if you cannot cover a fine, it becomes a balance you owe
  rather than money you do not have. Only a quarter of each settlement
  goes to paying that balance down, so three quarters still reaches you
  and you can keep working. The balance cannot grow past a ceiling, and
  you are warned out loud well before you get near one. A run of bad
  luck costs you time and earnings; it does not strand you.

- **New careers now really do start on the Realistic preset.** The
  settings row has said Realistic for a long time, but lane keeping sat
  outside the presets, so the truck was quietly holding your lane and
  taking your exits the whole time. A fresh install now matches the
  label: you hold the lane yourself, and your destination exit needs
  your signal and your exit lane like every other exit. If you would
  rather the truck did that part, Driving assistance settings has the
  other two presets and the Lane keeping row. Nothing changes for an
  existing career -- your saved setting carries over exactly as it was.

- **The steering setting now says what the truck actually does.** Lane
  drift is now called Lane keeping, and its values changed from off,
  light, and realistic to full, partial, and off. The old names were the
  wrong way round: what used to be called off was the truck holding the
  lane for you and taking your exits, including your destination exit.
  Your setting carried over to the value that behaves exactly the same,
  so nothing about your driving changed, and the row explains the rename
  the first few times you visit it. Lane keeping now also follows the
  driving assistance presets, so the preset row can no longer describe
  less automation than you really have. With it on full, the truck says
  so the first time it sets an exit lane for you and the first time it
  takes your destination exit.

- **The owner-operator start no longer skips the career.** It used to
  open at level eighteen with thirty-five deliveries and forty-two
  thousand miles already behind you -- most of the thirty-level career
  handed over before you had driven a foot, and a history that never
  happened showing on your public profile. Now it starts where every
  career starts, at level one. What the choice actually gives you is the
  hard part: your own tractor, your own working capital, and every
  operating cost coming out of your pocket instead of the carrier's.
  It changes who pays, not how far along you are.

- **Three new keys answer one hours question each.** C used to read the
  clock, the deadline, and your whole hours-of-service position in one
  long breath. Now Alt A says how long you have been at the wheel this
  shift, Alt S says when your break is due, and Alt D says how much
  driving time and duty window you have left. Left to right, they follow
  the shape of a shift, and each starts with a different word so you
  always know which one you pressed. C still works and still opens the
  same way; it now ends with just the limit that matters next, and it
  reminds you about the new keys the first three times you press it. On
  a controller, the clock button still reads the full report.

- **Street corners now ask you to slow down for them.** The approach
  names the turn, the street, the distance, and the speed to be under,
  and arriving too fast means you go by it: the game takes you to the
  next safe turnaround and loops you back, with the clock running. Miss
  the same corner twice, or three anywhere on a run, and the turn is
  made for you so no route can strand you. Highway junctions are
  unchanged.

- **The road under the truck now leans into turns and ramps.** The
  guiding road sound went quiet during every corner and every exit ramp
  -- exactly when you most need to hear where the road is going. It now
  follows you through them.

- **The radio dial moved to Page Down and Page Up.** Page Down tunes to
  the next station and Page Up to the previous, with Control still
  jumping a whole category. The old semicolon and apostrophe keys keep
  working as a second option, so nothing you know breaks. The radio help
  pages and the manual now name the right keys everywhere.

- **Test builds use a staging server for online services.** While 1.9 is
  in testing, the drivers board, profile sharing, and cloud backup talk
  to a separate staging copy of orinks.net with its own accounts and
  data. Connect a fresh account there to help test; nothing you do on
  staging touches your real orinks.net driver, and staging careers and
  backups will not carry over when 1.9 releases.

### Added

- **Tank freight, and a load that keeps moving after you stop.** Bulk
  fuel and liquid food open late in your career, and they drive like
  nothing else: a part-full tank runs forward when you brake and comes
  back into you a beat later, so a half-full smooth-bore tanker needs a
  third more room to stop than a dry van. You hear the wave running
  before you feel it push, which is the whole skill -- brake early,
  brake once, and let it settle. Baffles calm it front to back but do
  nothing side to side, and a bend is where a tanker gets you. The
  walk-around tells you how full the tank is and what kind it is.

- **Police are on the road now, whoever you are.** Enforcement sits at
  real places -- medians, work zones, the apron of a closed scale, town
  limits -- and whether you are seen depends on distance, sight lines
  over crests and round bends, weather, and whether you are running in a
  pack. A clean driver hears police often and pays nothing; a habitual
  speeder gets stopped three or four times in five hundred miles. And
  speeding you were never seen doing no longer bills you at the dock: an
  invisible charge from an officer who was never there is gone.

- **A wrecked truck now drives like one, and eventually not at all.**
  Damage used to cost you a little acceleration and nothing else, so a
  truck at ninety-nine percent still ran down the highway. Now the
  engine holds power back and burns more fuel past fifty percent, winds
  down to a forty-five mile an hour cap past seventy-five, warns you at
  eighty-five, and at ninety percent the truck is out of service: you
  get ten miles an hour to clear the lane, and then road service has to
  come to you. Every step is announced before you feel it, and the cap
  eases in rather than snapping. Repairs cost far more the longer you
  put them off.

- **Bring a company truck back wrecked and the carrier notices.** An
  owner-operator pays the whole repair and waits. A company driver pays
  nothing for it, but dispatch grounds the tractor, puts you in a yard
  spare for the rest of the run, charges a deductible, voids the safety
  bonus, and logs preventable damage against your record -- and a
  pattern of that costs the seat.

- **Your freight can be damaged, and the receiver can refuse it.** Hard
  stops, cornering far too fast, and collisions now hurt the load, and
  the dock inspects before it signs. A little damage is noted as an
  exception, more becomes a claim against the carrier, and a load in bad
  enough shape is refused outright -- no pay for the haul at all, and a
  claim on top. You hear the load take it at the time, and you can check
  its condition while you drive.

- **Traffic law now follows you through your whole career.** Fines scale
  with how far over you were and climb with every citation you have
  already collected, and the serious ones go on a record that outlives
  the trip. Two serious violations in three years suspends your CDL for
  sixty days and takes driving jobs off the dispatch board until it
  clears; three costs a hundred and twenty days. Running from a traffic
  stop is a felony that disqualifies you for a year, and a second one
  ends that driver's commercial career for good -- so running is now
  something you have to deliberately choose, with the cost read to you
  before you commit. Every citation already on your record makes the
  next one dearer, up to a limit: the money stops climbing after the
  third, and from there it is your record that keeps getting worse, not
  your wallet. Your standing is always available to ask for, and
  the game warns you before the next violation is the one that lands.
  A driver who keeps it clean sees none of this.

- **Dispatch trusts you less as your reputation falls.** A good record
  gets you the whole board and your pick of loads. As reputation slides
  you see fewer and worse-paying dispatches, lose the right to choose
  your own load, and get a smaller allowance for turning work down; at
  the bottom your carrier lets you go. Clean, on-time runs rebuild it,
  and the game tells you which way you are moving.

- **Falling asleep at the wheel is now on your record.** Running off the
  road asleep costs reputation as a preventable safety incident, and
  doing it again becomes a fatigued-driving violation on your CDL. When
  you cannot stay awake at all, the truck is genuinely stopped and you
  are out of service for ten hours -- the same rule a real inspector
  would apply.

- **Blow past the facility gate and you now miss it.** Arriving used to
  be automatic no matter how fast you came in. Now the approach warns
  you ahead of the gate with the speed to slow to, and if you carry past
  too fast anyway, you miss the entrance: the game takes you to the next
  safe turnaround and loops you back for another approach while the
  clock keeps running, so a hot approach can cost you a deadline. Miss
  it twice and the game offers braking help. The destination approach
  assist always makes the gate for you.

- **Weigh stations are on the map.** Eighty-seven real scales across
  thirty-two states are now stops on the routes that sign them, so the
  scale rules the game already had -- checking in, and what happens if
  you roll past an open one -- finally have somewhere to happen.

- **Towns now enforce their engine brake ordinances.** Like real
  municipal noise rules, cities and towns along your route are no engine
  brake zones. Coming up on one with the engine brake switched on, you
  hear a spoken heads-up; keep it barking inside the zone and a local
  officer writes an on-the-spot fine that grows if you keep doing it.
  Descending a real grade, reacting to a hazard, and retarding raised by
  cruise or the curve assist are never fined, and open-road engine
  braking is untouched. Your delivery summary lists any citations paid.
  Cruise and the curve assist mind the signs like a courteous driver:
  inside a zone they switch the engine brake off and hold speed with the
  service brakes instead, saying once why the engine note changed --
  unless a real downgrade makes the engine brake the safe tool.

- **Live traffic and truck parking cover far more of the map.** Real
  incident and road-work reports are back in Indiana and now on in
  Minnesota and Colorado, and real work-zone reports arrive in ten more
  states, from Florida to New York to Arizona. Live truck-parking
  counts moved to Wisconsin's real-time sites and now work wherever a
  state publishes them, instead of only near one test area. States
  without a public feed keep the usual simulated traffic.

- **Public profiles now tell more of your career, and the drivers board
  hears your radio.** With Profile sharing on, your board line names the
  station you are tuned to while you drive, and your public career
  statistics grow to include lifetime career earnings, badges earned,
  endorsements, and, for company drivers, your carrier fleet tier.
  Lifetime earnings is the running total your career has ever earned;
  the money you currently have is never published, and the sharing
  disclosure now says both halves plainly.

- **The whole map got its roadside signs.** The curated billboard sweep
  is baked everywhere now: two hundred thirty-three real-place signs
  across every region -- up from forty-two in five regions -- so
  Florida, the Northeast, the Pacific Northwest, the Great Lakes,
  Appalachia, and the rest finally pass their own roadside culture, from
  the Overseas Highway to Route 66, each sign at its attraction's real
  milepost. Meteor Crater, Standin' on the Corner, the Wigwam Motel, the
  Boll Weevil Monument, Little America, and Leavenworth's Bavarian
  village all made the cut, and fifty-nine respectful landmark callouts
  ride along.

- **Achievements are now browsed by category.** The achievements screen
  opens on seven categories -- Out on the Road, The Working Day, Career
  and Rank, The Dial and Song Towns, Weather and the Calendar, Places on
  the Map, and Deep Cuts -- each spoken with how many you have earned of
  its total. Enter a category to review its badges: earned ones tell
  their story, locked ones keep to their title, and a few hidden ones
  stay a secret the manifest is keeping until you find them. With the
  catalog past one hundred seventy badges, one flat list had become a
  long listen.

- **Thirty-one new original songs and beds across the game.** The country
  originals batch joins the music: new daytime and nighttime driving beds,
  ten more songs on the country stations, and a brand-new station --
  Nashville After Hours -- playing late-night Nashville jazz and crossover
  instrumentals. Careers that reach level 21 also get a new menu theme of
  their own.

- **Thousands more real stations on the dial.** Most of the map now has
  its real local radio around it: over eight hundred commercial country,
  rock, sports, talk and oldies stations that come in only near their real
  transmitters, layered under the curated public, community, college, and
  AFN stations already there. Past everything local, a new Web radio band
  carries five thousand internet stations from everywhere, most popular
  first, one category jump to skip past. Real streams stay behind the same
  switch as before, and streamer-safe mode still keeps to the game's own
  stations and your playlists. Built on the station catalog contributed by
  CatalystForChaos in pull request 150.

- **Save your stations with O.** While driving, O keeps the current
  station as a favorite, and pressing it again lets the station go.
  Favorites are their own dial category right after your playlists, one
  category jump from anywhere, so the stations you like are never buried
  in a dial of thousands. A favorite only plays where it can be received,
  and favorites stay with your career save.

- **Tuning a dead station no longer freezes the cab.** The radio now
  connects to a stream in the background and gives up on a station that
  will not answer, so the drive keeps moving while it tries. A station
  that cannot come back is announced and the radio falls back the way it
  always has.

- **Career 1.9 now uses the approved sound mix everywhere.** Source checkouts
  and packaged builds carry the same sound pack, while the original sound
  library recordings remain private and are not distributed in the repository.

- **Roadside sleep now works from T when the truck is fully stopped.** Away
  from a route stop, T opens the existing emergency shoulder-sleep warning
  instead of saying there is no point of interest. Route stops still take
  priority. The truck is secured before a sleep menu opens, so setting the
  parking brake at walking pace and pausing cannot leave you rolling between
  two unavailable choices.

- **Five more AFN bases on the dial.** Iwakuni, Kunsan, Misawa, Okinawa,
  and Sasebo join the AFN section, all of them Pacific stations carrying
  The Eagle. That brings the AFN list to twenty-three bases you can tune
  from anywhere on the map when nothing local is in range.

- **Steer through curves by ear.** With steering assist on, the road sound
  now leans toward where the wheel should go: it slides into a bend as the
  bend arrives and leads you through it, and when you drift it sits toward
  lane center so you can follow it home. Centered on a straight road it
  stays put and nothing new plays. Drift to the road edge and the boundary
  answers with real textures from the side it happens on: a ragged stutter
  as your tires clip the rumble strip, a steady buzz fully on it, and
  loose gravel once you are off the pavement. On an undivided road the
  warning tells the truth: past the centerline you are in the oncoming
  lane, and there is no gravel out there. Ahead of a true hairpin, warning
  bars cut across the whole lane wake you up the way the real ones do --
  three hard grouped rumbles under all your tires, far enough out that
  braking after them still makes the curve. The I key adds an on-demand
  lane locator: a soft repeating tock from wherever you sit in your lane,
  and pressing I again turns it off. Entering a demanding bend ticks a
  bright cue from the bend's side, and coming out the far side the
  co-driver gives the verdict: held your line, caught the edge, or
  through it hot. Changing lanes, your tires roll over the lane line's
  raised markers -- the front-to-back thump-roll of a real crossing,
  from the side you crossed. A new setting, lane and edge cue loudness,
  sets how loud all of it speaks: subtle, standard, or prominent.

- **The road tells you how many lanes it has.** Your road status now says
  the lanes on your side of the road -- "divided, three lanes your side" on
  an interstate, "two lanes your side" on a smaller highway -- and your trip
  briefing sums it up before you roll. As the road widens or narrows, you
  hear it: "road widens to three lanes", "down to two lanes your side". It
  reads the real road, so where the map has no lane data it stays quiet
  rather than guess, and the extra callouts hush in terse speech. Lane
  numbers only for now -- passing and lane changes come later.

- **A warning before every steep grade.** Any climb or descent of three percent
  or more that runs for at least three quarters of a mile is now called out
  before you reach it, with how steep it is, how far it runs, and -- going down
  -- what to do about it before it starts. In a manual that is picking your
  gear and setting the engine brake; in an automatic it is setting the engine
  brake and braking down to speed, which is what puts the transmission in a
  lower gear for you. Short dips stay quiet, so on a mountain route you hear
  the hills that matter and nothing else. Terse speech does not get these
  announcements at all -- press G whenever you want the grade instead. The
  advisory is there so you can decide before the hill starts: when in doubt,
  take manual control of the speed rather than leaving it to cruise.

- **A new song on the country stations.** "Dust on the Highway" opens on a
  lone slide guitar over a rumbling bass, the drums lock in, and organ and
  harmonica trade fills through a gritty lead-guitar solo before the band
  slams back in for the finish. Three and a half minutes with no vocals, so
  it plays under the road without talking over it. You will hear it on The
  Rawhide out of Dallas, Big Wheel Country out of Nashville, Prairie Line
  out of Kansas City, and Big Sky Country out of Billings.

- **G also names the next grade ahead.** Alongside the slope under the wheels
  and the truck's verdict on it, G now tells you what the next steep grade is,
  how far off, and how long it runs -- so one press answers both what you are
  on and what is coming.

- **Review recent spoken messages while driving.** A line lost under an
  overlapping announcement is no longer gone for good. From the cab, comma
  and period step back and forward through what has been said, Ctrl with
  either jumps to the first or latest message, the brackets switch between
  all messages, general ones, and driving events, and Ctrl+C copies the one
  you are on to the clipboard. Routine menu navigation stays out of the
  history so it cannot bury anything worth keeping. Contributed by Day
  Garwood ([@day-garwood](https://github.com/day-garwood)) in
  [PR #122](https://github.com/Orinks/Freight-Fate/pull/122).

- **Walk around the trailer before you pull out.** When you hook a trailer
  out of a drop yard, a new pickup option lets you check the lamps, the
  brake adjustment, and the tires yourself. If something is wrong with it
  you hear exactly what, and you can refuse the box: the yard takes about
  thirty minutes to bring a sound one, and the write-up stays with them
  instead of riding to the first scale house with you. Roll out without
  looking and it is yours.

- **Receivers with a drop yard take the whole trailer.** The delivery end
  works the way the pickup end does now: at a receiver set up for it you
  back the loaded trailer into their yard, hook a clean empty, and go --
  twenty minutes instead of forty-five at a dock. It is also how you finally
  get rid of a trailer you have been dragging a defect around on since the
  shipper.

- **Drop and hook.** Not every pickup is an hour backed into a dock any
  more. Busy shippers -- cross-docks, parcel hubs, retail distribution
  centres, intermodal ramps -- keep loaded trailers standing in a yard, so
  you drop the empty you came in with, hook one that was loaded hours ago,
  and you are gone in twenty-five minutes instead of sixty. The catch is
  the one real drivers know: you get the trailer you get. The game tells
  you which one you hooked and what shape it is in, and if you hooked a
  rough one, the inspector at the next scale finds exactly what your
  walk-around would have. Smaller shippers still load you at a dock.

- **Detention pay.** When a shipper holds you at the dock past two hours,
  the carrier bills them for the wait and it shows up on your settlement as
  money in rather than money out. About one live load in three runs long.
  The clock was going to run anyway; now some of it is working for you.

- **Owning your trailer costs you the fast turn.** Nobody swaps an
  owner-operator's own trailer for one out of a yard, so if you bought your
  box you load at a dock every time, even at a shipper with a drop yard full
  of them. It is a real trade and it is why leased carriers move freight
  faster.

- **The yard has thirty-five tractors in it now, not twelve.** Day cabs and
  sleepers, light tractors that leave the weight for the freight and heavy
  ones spec'd to pull it, aero shapes that sip diesel and long-hood
  conventionals that absolutely do not. Every band of the carrier's fleet
  now holds a real spread instead of two or three trucks, so the truck you
  are handed says something about the work.

- **Dispatch picks the truck to fit the load.** Early in a career you
  slip-seat, the way a new hire really does: no tractor is yours, and the
  yard hands you whatever is free and suited to the run. A load too far to
  finish inside one driving shift comes with a bunk. A heavy load comes with
  the driveline for it. A turn you will be back from tonight comes with a
  day cab. Dispatch tells you which truck and why when it changes. The yard
  leaves you the same few spares, so each one keeps its own fuel, wear, and
  dents and you get to know which of them pulls. Make level nine and that
  ends: seniority means a truck of your own, and you keep it.

- **Twenty-one new achievements, including several that should not count.**
  The radio finally has badges of its own -- riding a station until the hiss
  takes it, catching one from far outside anything it should reach, holding
  one signal across three state lines. So does the driving craft: two miles
  of downgrade held on the engine without touching the service brake, and
  cooking the drums hot enough to start losing them. There are badges for
  Christmas Day, for a Friday the thirteenth that went fine anyway, and for
  fifty deliveries without a single ticket. And there is one for holding
  exactly sixty-nine miles an hour for a solid mile, which means nothing at
  all.

- **Cruise reads the road ahead and drives the hill before it arrives.**
  Like the predictive cruise on a modern truck, it looks a mile and a half
  up the road and plans against what is actually there. It banks a couple
  of miles an hour before a climb so the truck carries that speed up the
  grade instead of meeting the hill at exactly your set speed and falling
  behind from the first yard. Near the top it stops fighting for the last
  few miles an hour the summit is about to hand back, so you keep the gear
  you are in rather than taking a downshift twenty seconds from the crest.
  And it will not build speed just before a downgrade that it would only
  have to brake away again. It tells you the first time it does each of
  these on a hill, so you are never wondering why the truck is doing
  something you did not ask for. On by default, under Settings, Driving
  assistance, Predictive cruise.

- **Cruise says so when a hill has beaten it.** Going downhill the truck
  has long told you when descent control could not hold the grade. Going
  up it said nothing at all: the truck just quietly sank, and unless you
  were watching the tach there was no moment where you were told plainly
  that cruise had run out of truck and it was your call whether to take
  over. Now, once the accelerator is genuinely on the floor and the truck
  is still losing the grade, it says so and tells you what speed it is
  holding. Once per hill, and never on terse speech.

- **Setting the parking brake at speed now dynamites the brakes.** The
  valve works at any speed, just like a real truck -- it is the
  emergency backup -- but pulling it while rolling slams the spring
  brakes on, screeches the tires, grinds flat spots into your tread
  scaled by how fast you were going, and tells you plainly to save it
  for emergencies. Setting it at a stop is as calm as ever.

- **New hires can review the rest of the day's board.** Below level 8,
  dispatch still assigns your load -- but a new board option, "Review
  the rest of today's board", reads out the other postings dispatch put
  up, so you can hear the pool widen as you level even before load
  choice unlocks. It speaks only when you ask.

- **FM radio now behaves like FM radio.** Height is range: climb a grade
  and distant stations reach you from far beyond their normal coverage --
  crest the Mogollon Rim and Phoenix comes in clear. At the edge of coverage
  the station does not just get quieter: a smooth receiver hiss creeps
  in underneath, and at highway speed the signal flickers in quick,
  sharp splashes of noise -- the picket-fencing every driver has heard
  on a fading FM station. The flutter follows your actual speed and the
  station's dial position, slows as you slow, and settles when you park.

- **Cold starts build their air out loud.** Start the engine with low
  tanks and it holds a fast idle while the compressor charges the air
  system, with a soft fill hiss underneath. When the air comes ready the
  hiss stops, the dryer gives its purge pop, and the idle settles down --
  that settling is your cue the parking brake can release. Revving while
  parked really does charge the tanks faster.

- **Parked high idle, on the cruise button -- rev it like a boss.** With
  the parking brake set, K latches a fast idle just like a real
  electronic truck: the engine holds a raised rpm to warm up and build
  air sooner, plus and minus step the setpoint up or down, and you hear
  the compressor charge faster the higher you hold it. Releasing the
  parking brake drops it back to idle on its own, and holding a high
  idle burns real fuel. On a controller it is the Y button.

- **The jake brake finally has its voice.** Switch the engine brake on
  and you hear the growl -- deeper and stronger the more cylinders you
  select and the higher the revs, exactly how the real retarder works.
  It cuts out through every shift and comes back louder in the lower
  gear: the stair-stepping bark every trucker knows from a long grade.
  It goes quiet the moment you touch the throttle, because a real jake
  does.

- **Cruise has a resume button now, like a car.** Braking still cancels
  automatic speed control on the first tap -- but the set speed is
  remembered, and Shift K brings it back: the truck accelerates to the
  old target on its own, or waits until you are rolling and off the
  brakes if you press it early. K by itself still sets a fresh target at
  your current speed.

- **The automatic box now manages its own jake, like a real one.** With
  an automatic transmission, J arms the engine brake in automatic mode:
  it holds the speed you engaged at, stepping its stage up and down on
  its own -- you hear the growl deepen and ease as it works -- and it
  never selects more stage than the road surface can hold. Pressing 1,
  2, or 3 takes manual control of the stage back at any time, and Alt J
  turns the automatic mode off entirely for drivers who stage it by
  hand. Alt T switches between automatic and manual shifting on the
  road. Manual boxes keep the classic stalk exactly as it was.

- **Low-gear shifts are quick now, like a real automated box.** Shifts
  through the bottom four gears take about half a second of torque
  interruption instead of a full second, ramping back up to the old
  timing in the top gears where real boxes take their time too. A
  loaded pull from a stop to 45 gets about three seconds quicker, and
  the launch rhythm finally matches what you hear a real truck do.

- **Curve assistance drives like a trucker now: jake first, brakes to
  trim.** When curve speed assistance needs to slow you and your engine
  brake is off, it switches the jake on at a stage sized to how hot you
  are coming in -- you hear the growl do the work -- and touches the
  service brakes only when you are still well over the advisory. On
  slick roads it does the opposite, exactly like a careful driver: no
  jake on ice, just gentle braking. It releases only the jake it
  engaged; your own selection is never touched.

- **Brakes and gear changes sound like the real mechanisms now.** Pressing
  the brake gives the valve's mechanical clunk, louder the harder you
  press, and letting off releases the air back out -- a hiss that runs
  longer and louder the harder you were braking, including the big pssht
  when you stop and let off. The emergency brake dumps its air in one
  long event. Every shift, manual or automatic, is a real recorded shift,
  and no two in a row sound identical.

- **Real stations reach a lot more of the map.** With streamer-safe mode
  off, the in-cab radio now picks up public, community, and college
  stations in dozens more places -- the Rio Grande Valley, Savannah,
  Amarillo, the Iowa corridor, the northern Plains, the high Rockies, the
  Carolinas coast, the Florida panhandle, and more -- so wherever a load
  takes you, there is a far better chance of catching local news or music
  instead of an empty band. A couple of stations whose streams had gone
  quiet are back on the air as well.

- **The dial now fills out like a real city.** With streamer-safe mode
  off, the in-cab radio no longer catches just one station per town -- it
  picks up the whole non-commercial band a market really has: the public
  news station and its separate classical or jazz sister, the community
  and college stations, and the digital sub-channels that ride alongside
  them, including the ones carrying BBC World Service. Hundreds of real
  stations were added and checked one by one, so from Atlanta to Amarillo
  to the Montana Hi-Line you can tune across a dial that sounds like the
  place you are actually driving through. A few stations whose streams had
  gone quiet are back on the air as well.

- **Reading services for blind listeners are on the dial.** Radio reading
  services -- the stations that read newspapers, magazines, and books
  aloud for blind and print-disabled listeners -- now appear as real
  stations in the cities that have them, from Memphis and New Orleans to
  Phoenix, Chicago, Houston, Atlanta, Nashville, Des Moines, Columbus,
  and Gainesville, and more. Wherever one is in range, it is right there
  on the band with everything else.

- **Community radio joins the dial.** With streamer-safe mode off, the
  radio now carries the volunteer-run and student stations that give a
  place its own voice, right alongside the public and NPR ones -- freeform,
  Pacifica, college, and tribal community radio, from the big cities down
  to small towns in the mountains and plains. Tune across a market and you
  come across the local independents, not just the network feed: WORT in
  Madison, WFMU-style freeform on WTJU and WRFL, the Pacifica stations in
  Los Angeles, New York, and Washington, and the college institutions --
  Berkeley, Stanford, Chapel Hill, Georgia Tech, Austin -- that have been
  on the air for decades. As always, where a town's only community station
  broadcasts solely through a phone app the game cannot reach, the dial
  stays quiet there rather than invent a signal.

- **The loneliest highways have a signal now.** With streamer-safe mode
  off, the emptiest stretches of the map catch a real public-radio
  station where there used to be only static. Across the Nevada high
  desert -- Winnemucca, Battle Mountain, and Elko on Interstate 80,
  Eureka and Ely on US-50 -- the radio now finds the local NPR signal
  as you pass through, and it fades the way a small mountaintop signal
  really does, coming up out of the noise and slipping back into it
  between the ranges. Down in the Big Bend country of far West Texas,
  Marfa, Alpine, Marathon, Presidio, and Del Rio pick up their own
  border-country public stations. A few places stay silent on purpose:
  out where no station truly reaches, the band stays empty rather than
  pretend otherwise.

- **The engine brake grew its real cylinder selector.** J is now the
  dash switch: it turns the engine brake on at whatever stage you last
  selected, and while it is on, 1, 2, and 3 pick two, four, or six
  cylinders of retard, spoken as you change them. Partial stages are
  the icy-descent tool -- stage one stays hooked up on glare ice where
  full retard breaks the drive wheels loose -- and the selector
  remembering your choice means switching the jake back on can never
  surprise you with more braking than you dialed in. On a controller,
  the modifier with the engine brake button steps through the stages.

- **Your own music can play on the in-cab radio.** Drop M3U playlist
  files into the new Playlists folder next to your saves and each one
  becomes a station on the dial, under Your playlists, named from the
  playlist. Files can live anywhere your computer can reach, including
  a network drive, and the usual formats all play. The station picks up
  where it left off when you tune away and back during a drive, and a
  file that will not open is skipped instead of stopping the music.
  Like real public streams, your playlists play only when streamer-safe
  mode is off.

- **The radio dial now jumps by category.** Control with a bracket key
  leaps to the previous or next section of the dial -- route playlist,
  Freight Fate stations, your playlists, terrestrial, AFN, satellite,
  international -- and announces where you landed. No more tuning through
  twenty-five AFN stations one by one to reach the local dial.

- **International public broadcasters are always on the dial.** With
  streamer-safe mode off, a new International section carries English-
  language public radio you can catch anywhere, the way AFN already
  works -- ABC from Australia (triple j, Jazz, Classic, and Double J),
  RTÉ from Ireland (Radio 1, 2FM, and lyric fm), RNZ from New Zealand
  (National and Concert), RFI English from France, and CBC Radio One and
  CBC Music from Canada. Music, news, and classical all in the mix, so
  there is always something to tune to no matter where a load leaves you.

- **The road now names the towns that change your speed limit.** When a
  limit is about to drop for a small town, you hear the town first --
  "Entering Strawberry" -- so a sudden 35 in the middle of a mountain
  highway finally has a reason attached to it instead of arriving out
  of nowhere. Every name is a real place taken from the map, never
  invented. A new Place callouts setting controls how much you hear:
  sparse, the default, speaks only the names that explain a limit
  change; all adds the towns the route passes through or skirts; off
  silences place names entirely. No setting ever reads out every place
  on the map -- the rest of that data waits quietly to answer
  orientation questions on demand.

- **Every stop the game announces is now one your rig can actually
  enter.** Every fuel stop, rest area, and truck stop on the map was
  checked against real-world truck access. Car-scale gas stations that
  a seventy-foot rig cannot turn around in are no longer announced, no
  longer offered as exits, and no longer counted when dispatch plans
  your fuel and sleep stops -- they stay on the map for the day you are
  running tractor-only. In their place, hundreds of real truck stops,
  service plazas, and rest areas the map had never looked for were
  added along thin corridors, so the longest stretches with no legal
  place to sleep are about half as common as before. Where a remote
  highway genuinely has nothing -- and some real ones do -- the game
  now tells you the truth instead of inventing a stop.

- **The stop bar at the end of a delivery ramp finally has a
  position.** Rolling toward the light you now hear the distance count
  down -- one thousand feet, five hundred, three hundred, one hundred
  fifty -- and inside the last stretch a soft tick speeds up as the bar
  closes, parking-sensor style, going quiet when you stop. Press S on
  the ramp any time to hear the light's color and how far the bar is.
  No more stopping a quarter mile short and creeping through three
  greens wondering where the intersection went.

- **The co-driver now warns you before the speed limit drops.** When a
  real posted drop is coming that your speed can't ignore -- a village 30
  at the end of an open 55, a city ring at the end of a fast interstate
  run -- she calls it while there is still room to brake a loaded rig:
  "Speed limit drops to 30 in a quarter mile." Small steps and drops you
  are already slow enough for stay silent. And when a lower limit only
  lasts through a short town, the sign call now says so -- "Speed limit
  reduced to 30 for half a mile" -- so a village main street reads as a
  passing event, not your new cruising speed. Distances follow your
  kilometers setting.

- **An armed exit now counts itself down.** Once your signal is on, the
  exit calls out again at two miles, one mile, and half a mile -- and if
  you are not in the right lane, each call says so while there is still
  road to fix it. No more hearing about an exit once, five twisty miles
  early, and never again until you have missed it.

- **Curve calls now open with a tone on the curve's side.** A short cue
  panned left or right lands just before the spoken call, so a pacenote
  is recognizable as road shape -- never a steering instruction, and
  never mistakable for GPS chatter -- before the first word. The S key
  also grew curve sense: in bend country it speaks the posted limit and
  the bend's advisory speed together, so a legal 55 through hairpins no
  longer sounds like nonsense.

- **A co-driver now reads the road: spoken curve callouts.** Bends that
  demand slowing at your current speed are called before they arrive --
  "Sharp left, half a mile. Advise 35." -- early enough to brake before
  the bend, never in it. Bends you are already slow enough for stay
  silent, so a legal cruise down a straight interstate is as quiet as it
  ever was, while a canyon run finally talks you through. Every call
  comes from the real measured geometry of the road, tight bends link
  into one call ("then right"), the U readout lists the next few bends
  with their advisory speeds, and D folds the bend into its one
  safe-speed number. Turn it off any time under Settings, Driving
  assistance, Curve callouts.

- **Rest stops can now tell you how big the lot is.** Where the official
  federal truck-parking survey covers a stop, the spoken parking note adds
  the counted spaces, like confirmed truck parking, 45 spaces. Lot size
  matters at night too: a small surveyed turnout fills up earlier in the
  evening crunch, while a big travel plaza holds out longer. A couple of
  surveyed public lots also joined sparse corridors as new rest stops.

- **The GPS now calls out posted low bridges and weight limits.** Corridors
  carry real posted clearance and weight signs from the map data, and the
  GPS speaks them ahead of the point like it does toll plazas: in two miles,
  low clearance ahead, posted 13 feet 6 inches. Your route already avoids
  bridges a truck cannot legally pass, so these are heads-up calls, not
  detours.

- **The menus borrow a few songs from the radio.** Six radio instrumentals
  now round out the menu music rotation. By day, the pedal steel of Steel
  String Sunday, the mellow Dobro Dusk, and the rock of Glass Highway take
  turns after your career milestone theme; after dark, the night blues of
  Freight Yard Moon and Midnight Siding and the late-night jazz of Low Beams
  play behind the quiet piano theme. Your milestone theme still always plays
  first, and the menus stay instrumental so they never talk over your screen
  reader.

- **The radio finally sounds like radio: fifty-two new original songs.** The
  fictional stations grew real rotations -- the country stations now spin
  fifteen songs, the classic rock stations seventeen, and the blues and soul
  stations twelve, mixing sung songs with instrumentals in each format.
  The Freight Fate Roadhouse picked up ten fresh daytime instrumentals,
  quiet new night beds joined the after-dark rotation, and the Night Line
  now slips in two late-night vocal ballads between its host breaks.

- **Route-transition assistance now handles the light at the end of the
  ramp.** Stopping a rig exactly on the stop bar, blind, while the light
  cycles was the hardest ask in the game -- and getting it wrong meant
  cross traffic in your trailer. With route-transition assistance on,
  the assist brakes for a red or a dying yellow, stops the truck at the
  bar, and holds the brakes until the green -- you hear every phase,
  and pulling ahead is still yours. A green crossing is kept under a
  safe rolling speed. Turn the assist off and the bar is all yours
  again, exactly as before.

- **Driving assistance reduces workload without driving for you.** One preset coordinates emergency braking, lane and descent support, stop-and-go traffic, curve and route-transition speed help, exit slowing, and stopping at the selected destination arrival point. You still steer, confirm routes and exits, leave long stops, and handle every yard and dock task.

- **Choose how much driving assistance the truck provides.** A new Driving assistance settings category offers Realistic, Balanced, All assists, and Custom presets for emergency braking, lane support, stop-and-go behavior, and interactive descent speed control. Adaptive cruise keeps its existing traffic, posted-limit, and weather behavior. Presets never change trip pacing, hours rules, transmission, weather, or hazard frequency. These assists lay the groundwork for the version 1.9 driving changes.

- **The truck now sounds like a real truck.** The engine voice is built
  from a real cab recording and follows the rpm through its range --
  idle, pulling away, cruising, working up high -- instead of one loop
  stretched faster and slower. You will hear the difference the moment
  the engine settles into idle. Prefer the old sound? A new Engine
  voice setting under Settings, Audio switches between real and
  classic, and it applies instantly, even while driving.

- **Cold starts build their air out loud.** Start the engine with low
  tanks and it holds a fast idle while the compressor charges the air
  system, with a soft fill hiss underneath. When the air comes ready the
  hiss stops, the dryer gives its purge pop, and the idle settles down --
  that settling is your cue the parking brake can release. Revving while
  parked really does charge the tanks faster.

- **Parked high idle, on the cruise button -- rev it like a boss.** With
  the parking brake set, K latches a fast idle just like a real
  electronic truck: the engine holds a raised rpm to warm up and build
  air sooner, plus and minus step the setpoint up or down, and you hear
  the compressor charge faster the higher you hold it. Releasing the
  parking brake drops it back to idle on its own, and holding a high
  idle burns real fuel. On a controller it is the Y button.

- **Brakes and gear changes sound like the real mechanisms now.** Pressing
  the brake gives the valve's mechanical clunk, louder the harder you
  press, and letting off releases the air back out -- a hiss that runs
  longer and louder the harder you were braking, including the big pssht
  when you stop and let off. The emergency brake dumps its air in one
  long event. Every shift, manual or automatic, is a real recorded shift,
  and no two in a row sound identical.

- **The engine brake grew its real cylinder selector.** J is now the
  dash switch: it turns the engine brake on at whatever stage you last
  selected, and while it is on, 1, 2, and 3 pick two, four, or six
  cylinders of retard, spoken as you change them. Partial stages are
  the icy-descent tool -- stage one stays hooked up on glare ice where
  full retard breaks the drive wheels loose -- and the selector
  remembering your choice means switching the jake back on can never
  surprise you with more braking than you dialed in. On a controller,
  the modifier with the engine brake button steps through the stages.

- **Your own music can play on the in-cab radio.** Drop M3U playlist
  files into the new Playlists folder next to your saves and each one
  becomes a station on the dial, under Your playlists, named from the
  playlist. Files can live anywhere your computer can reach, including
  a network drive, and the usual formats all play. The station picks up
  where it left off when you tune away and back during a drive, and a
  file that will not open is skipped instead of stopping the music.
  Like real public streams, your playlists play only when streamer-safe
  mode is off.

- **The radio dial now jumps by category.** Control with a bracket key
  leaps to the previous or next section of the dial -- route playlist,
  Freight Fate stations, your playlists, terrestrial, AFN, satellite --
  and announces where you landed. No more tuning through twenty-five
  AFN stations one by one to reach the local dial.

- **The road now names the towns that change your speed limit.** When a
  limit is about to drop for a small town, you hear the town first --
  "Entering Strawberry" -- so a sudden 35 in the middle of a mountain
  highway finally has a reason attached to it instead of arriving out
  of nowhere. Every name is a real place taken from the map, never
  invented. A new Place callouts setting controls how much you hear:
  sparse, the default, speaks only the names that explain a limit
  change; all adds the towns the route passes through or skirts; off
  silences place names entirely. No setting ever reads out every place
  on the map -- the rest of that data waits quietly to answer
  orientation questions on demand.

- **A bobtail truck is finally just the tractor.** Reposition runs and
  city-service drives now drop the trailer's five-plus tonnes for real: the
  truck jumps off the line, stops shorter, and the dash air gauge no longer
  waits on a trailer line that is not connected. Deadheading to a pickup
  still hauls your empty trailer, and a loaded run still weighs what the
  freight weighs.

### Changed

- **Careers from earlier versions stay in their own era.** Version 1.9
  rebalances the whole career -- pay, trucks, levels -- so every driver
  starts fresh. A career made in Freight Fate 1.8 or earlier still shows
  in your career list, clearly labeled, and picking it explains what
  changed and offers a new career instead; the old save is never touched,
  never deleted, and still works in Freight Fate 1.8. Cloud backups from
  earlier versions stay safe in your account the same way, restorable by
  the version that made them. Careers you started on 1.9 test builds
  carry on unaffected.

- **Every Freight Fate music station now plays everywhere.** The Rawhide,
  Big Wheel Country, The Grind, The Delta, and the rest of the game's own
  stations no longer fade out past their home cities. They sit together
  with Roadhouse and Night Line in the Freight Fate stations category on
  the dial, and they play anywhere on the map, in streamer-safe mode, with
  real streams off -- every player can hear the game's music.

- **Turn signals play a clear tone instead of a soft click.** The blinker,
  the exit signal, and the pull-over signal now mark themselves with a
  clean indicator tone panned to the side you are signaling -- the sound a
  modern cab actually makes -- so the cue carries even for players who
  could not hear the old relay click.

- **Truck status now explains whose truck you are in.** Company drivers
  hear which carrier fleet their tractor comes from and what it is good at.
  Junior drivers also hear that they slip-seat: dispatch matches one of the
  yard's spare tractors to each load, and every spare keeps its own fuel and
  wear between draws, so a fresh truck after a turn is the yard handing you
  a different unit, not your wear disappearing. The level 4 and level 9 rank
  announcements now say the same in plain words, including that a dedicated
  seat of your own comes with seniority.

- **The driving school steps out of this release to finish training.**
  The Driving school item leaves the terminal menu for now: the lessons
  are not complete, and this release locks its features down. The school
  returns finished in the next major version.

- **The radio dial moved to semicolon and apostrophe.** The brackets used to
  tune it; they now switch categories in the new message review, so the dial
  sits on the two keys just right of the home row instead. Semicolon walks
  down the dial, apostrophe walks up, and holding Ctrl with either still
  leaps a whole category. M still turns the radio on and off and Y still
  reads what is playing.

- **Comma and period review your messages while driving.** They still repeat
  and step through recent speech everywhere else in the game. From the cab
  they now walk the message log instead, which is the same gesture doing a
  fuller job: the lines are kept by category and you can copy one out.

- **The R key now answers just "where am I".** Two short sentences: how far
  along you are and how far is left, then the road you are on with its
  direction, the state you are in, and the city it is taking you toward. If
  you have planned a stop, the distance counts down to that stop instead of
  the destination, so R tells you how far to the place you are actually
  driving at. The nearest named place, the grade, the zone, and the next
  maneuver are gone from it, because each of those already has its own key
  or lives in the Tab status menu. U still reads what is coming up, and
  Shift R still reads the next exit.

- **Shorter driving readouts that fit a braille display.** The clock, route,
  weather, and fuel reports now put the answer in the first few words, so a
  one-line braille display shows what matters without panning. The C key
  leads with the time and whether you are on schedule instead of burying the
  verdict at the end, and on the terse speech setting it skips the calendar,
  the appointment restatement, and the stop-planning advice, all of which
  the Tab status menu still carries.

- **Speech verbosity is now a simple choice between terse and normal.** The
  chatty level never said anything normal did not; it only repeated your
  speed a little more often. If you had chatty selected, the game now uses
  normal, and everything you heard before is still there.

- **Rest stops no longer let you sleep twice for nothing.** When you are
  already fully rested at a rest stop, choosing a sleep option now warns you
  that it would only move the clock and your deadline forward, and asks you to
  press Enter again to confirm. This is the same safeguard the terminal bunk
  room already had.

- **Walking away from a parked truck now takes you off the drivers board.**
  If your truck sits stopped with nothing changing for half an hour, you
  leave the public board just as if you had paused the game, and the board
  stops calling you a driver who is on duty. The moment anything changes,
  like rolling again or pulling into a stop, you are back on the board within
  seconds. Deadhead drives also now say how far along they are, on the board
  and in Discord, so a long empty run never looks like a parked truck.

- **The streets into town speak their real speed limit now.** Heading in
  to a customer or a truck stop, the posted limit you hear on each
  approach street comes from the real road -- an arterial posted 35 or 45
  no longer reads as a blanket 25 for miles. Where a street's limit isn't
  on record the sensible default stays, and the slow crawl right at the
  gate is unchanged.

- **Gear changes are quicker, like a modern automated box.** Power
  upshifts now take a quarter second in the low gears and half a second
  at the top, instead of dragging toward a full second. Downshifts keep
  their deliberate rev-matched pace -- that slower beat is real, and it
  is also what keeps the engine brake steady on a slick descent.

- **The game is about a third smaller to download.** The music now uses a
  newer, more efficient audio format, cutting the download from roughly 282
  to 191 megabytes without changing how anything sounds -- welcome news on a
  slow or metered connection. Fifteen tracks were rebuilt from their original
  studio recordings along the way, so those should sound a shade cleaner than
  before.

- **Dispatch stops handing you the same run over and over.** Assigned
  dispatch now remembers your last few delivered routes and leads with a
  load to somewhere you have not just been, whenever the board has one.
  Repeats can still happen when the board is small, but the days of
  bouncing between the same two cities forever are over.

- **Kilometer mode stays kilometers everywhere.** With units set to
  kilometers, the dispatch board, route selection, exit signals, GPS
  and deadhead announcements, city-service errands, settlement
  distance, the radio station list, and the chain-speed and lane-change
  advice all still spoke miles here and there. Every spoken distance
  and speed now follows your units setting, and one mile is finally
  "1 mile", not "1 miles". Thanks to the forum for the report.

- **The player manual caught up with the alpha.** New sections cover
  mountain driving (the engine brake, gearing down, brake heat and
  fade) and winter driving (winter tires, snow chains, chain laws),
  and the manual now documents the driving school, truck-stop meals
  and showers, lane changes and hazard dodges, wear meters, roadside
  chatter switches, the overspeed warning setting, and every new key.

- **Ramp endings are announced early, and play out in real time.** When
  you signal for an exit, the announcement now says how the ramp ends --
  "The ramp ends at a stop sign" -- while there is still a mile of
  highway to plan your braking on, and the U upcoming readout carries
  the same warning. And from the moment you are on a ramp that ends in
  a light or a sign, the game clock drops to real time until you are
  through the intersection: no more hearing about a stop sign two
  seconds before blowing past it because the clock was compressed.

- **Latch a pedal and give your hands a rest.** Tap the accelerator or
  brake, then press again and hold for half a second: a click and a
  spoken confirmation latch the pedal so it stays applied without
  holding the key, like the old hand-throttle knob in a real cab. Press
  the same key once to take the pedal back, or touch the opposite pedal
  and it lets go instantly. Emergency braking, hazards, and the
  overspeed alarm always outrank a latched pedal and release it with a
  spoken note. Made for long pulls, steady downhill braking, and hands
  that tire of holding keys; turn it off any time under Settings,
  Driving assistance, Latching pedals.

- **The repeat key now walks back through recent speech.** Comma still
  re-reads the last spoken line anywhere in the game, and pressing it
  again within a few seconds now steps back through the last twenty
  lines, one per press, from menus and driving events alike. Each older
  line starts with how far back it is, like "2 back", and the moment
  anything new speaks, the key returns to the newest line. A missed
  warning buried under two announcements is never gone anymore.

- **One key now answers "how fast should I be going?"** Press D while
  driving to hear a single safe-speed number for right now, sitting right
  next to the S posted-limit key. Slick weather and an upcoming exit ramp
  are already baked into the number, never into the sentence, so the
  answer is short enough to catch at speed and free to repeat.

- **Career stats now list your endorsements.** The endorsements you hold,
  earned by rank or paid for as a course, used to be announced only once,
  the moment you gained them. The Career stats screen now has an
  Endorsements line you can review any time, so you always know whether
  that refrigerated or heavy-machinery load on the board is yours to take.

- **The driving school opens its doors.** A new Driving school item at the
  terminal offers spoken lessons on a flat, empty practice road where
  nothing counts: no money spent, no wear, no fuel burned, no hours used.
  An instructor walks you through each step and waits for you to do it.
  The first lesson covers rolling basics, from starting the engine and
  releasing the parking brake to a smooth stop from thirty. More lessons
  will follow; use it to learn the controls or just to practice without
  risking your career.

- **Real streets reach the whole map now.** The street and facility data
  sweep re-ran over all six hundred twenty-three cities: sixty percent of
  home-terminal yards now start every load with spoken turn-by-turn
  directions on named local streets, up from a small Midwest batch, and
  nearly every local approach in the country names its real road.

- **Hundreds more facilities now start and end on real city streets.**
  Short yard-to-facility drives used to skip their street route and fall
  back to one straight access road; now any facility whose real path has
  a street chain under five miles uses it, so you hear real road names and
  turns at hundreds more pickup and dropoff sites across the country.
  Deadheads and final approaches at hundreds more warehouses, cross-docks,
  and company yards -- including the Evansville starter yard every new
  company driver leaves first -- speak real turn-by-turn directions on
  named local streets.

- **Truck stops now track loyalty points and rewards.** When you fuel at
  truck stops, you earn loyalty points based on the stop type: major chains
  like Pilot and Flying J give one point per gallon, landmark stops like Big
  Buck's give one and a half points per gallon, and unbranded stops give half
  a point per gallon. Fueling fifty gallons or more also earns shower credits.
  Points can be redeemed for showers, parking discounts, food discounts, and
  laundry discounts through a new loyalty menu at each truck stop. The system
  mimics real-world programs like Pilot Pro Rewards and TA UltraONE.

- **Real-time traffic incidents can be announced while driving.** When
  enabled in Settings, Gameplay, the game fetches live traffic data from
  state 511 APIs and announces high and medium severity incidents near your
  route, such as accidents and construction zones. The system uses Ohio's
  OHGO API as a reference implementation and gracefully falls back to
  simulated traffic when the API is unavailable.

- **Construction zones from the road ahead now read from real state 511
  data.** When a 511 endpoint provides construction work zone data for the
  state you are driving through, the game converts those events into
  approachable zones with taper warnings, reduced speed limits, and lane
  closure announcements -- real construction, where it really is, with the
  real speed reduction. As you cross a state line the system queries that
  state's DOT feed automatically; if no API is configured for the state,
  procedurally generated construction zones take over as before.

- **Twenty-four state DOTs now provide live 511 data for construction
  work zones.** Ohio continues on the OHGO API, five states use the shared
  Iteris platform (Arizona, Connecticut, Georgia, New York, Wisconsin),
  and eighteen states are configured for the federal Work Zone Data
  Exchange (WZDx) standard (California, Colorado, Florida, Idaho, Indiana,
  Maryland, Michigan, Minnesota, Missouri, Nevada, New Jersey, North
  Carolina, Oregon, Pennsylvania, Tennessee, Texas, Utah, Virginia,
  Washington). The remaining states fall back gracefully to simulated
  construction zones -- the game never shows a blank map for an
  unsupported state.

- **Blowing a bend's advisory now costs you for real.** The curves the
  co-driver calls are the same curves the physics feels: enter a bend
  well above its advisory speed and centrifugal force shoves the truck
  toward the outside of the curve -- harder with a heavy load, much
  harder on a slick road -- with a spoken slip warning as the tires
  start to complain. The curve speed assistance setting can ease you
  down toward the advisory before the bend, adaptive cruise drops out
  with a spoken reason when its set speed is too hot for the curve
  ahead, and interchange ramp arcs push the same way the mainline bends
  do. Hold the advisory and none of this touches you.

- **Real-time truck parking availability is announced at stops.** When
  enabled in Settings, Gameplay, the game fetches live parking availability
  from TPIMS APIs and announces how many spaces are available nearby when
  you arrive at a truck stop. The system uses Ohio's OHGO TPIMS as a
  reference implementation and gracefully falls back to static parking
  data when the API is unavailable.

- **Truck stops now offer more realistic amenities.** Eight new amenity
  types have been added to the data layer: CAT scales, laundry facilities,
  game rooms, barber shops, premium wifi, check cashing services, DEF lanes,
  and ATM services. These amenities are recognized at Pilot and Flying J
  locations and can be spoken when you visit those stops.

- **Dispatch assigns your tractor now, and better equipment follows
  seniority.** Like a real fleet, the carrier hands every new hire the same
  trainer-spec rig, then upgrades your assigned tractor as you climb: a
  newer regional unit at level 4, a long-haul sleeper at 9, a premium
  tractor at 13, and first pick of the yard at 17. Each hand-over is spoken
  at settlement and arrives fueled, serviced, and washed. Ten new tractor
  models -- day cabs, long-nose classics, big-bunk conventionals, and
  slippery aero flagships -- fill the fleet, and after the owner-operator
  buy-in the same models are yours to buy at the dealer.

- **Thirty-one new achievements for the bigger map and the longer
  career.** Badges now mark career levels 5 through 30, the owner-operator
  buy-in, activating your own authority, paying for your own endorsement
  course, owning three tractors, and fleet tractor upgrades -- plus
  map-wide progress: twenty-five, seventy-five, and one hundred fifty
  different cities, fifteen and thirty states, and first deliveries into
  the Dakotas, Montana, and northern New England. Twelve more celebrate
  deliveries into cities the jukebox got to first: Muskogee, Memphis,
  Kansas City, Saginaw, Fort Worth, San Antonio, New Orleans, Houston,
  Chattanooga, Abilene, either Jackson the famous duet might mean, and a
  small Arizona town with one very famous corner. Each still nods to a
  country or trucking song.

- **The dash now warns you about your own speed, like a real company
  truck.** Run a few miles per hour over the posted limit and a soft
  chime sounds with a spoken heads-up -- "Watch your speed. The limit is
  65" -- then the chime repeats until you settle back under, politely at
  a few over and escalating to twice a second when a descent is truly
  running away. It stays quiet while you are actively braking down. The
  new Gameplay setting has three positions: on, urgent only -- which
  keeps just the runaway alarm, for drivers who speed on purpose -- and
  off. No more finding out from the fine.

- **G speaks the grade under the wheels and what it is doing to the
  truck.** Press G while driving to hear the slope, how far it runs, and
  the sim's own verdict: whether the hill has the load, whether the jake
  is holding the descent, or whether speed is building and it is time to
  set the jake -- the spoken answer to "why am I slowing down."

- **Comma re-reads the last spoken line, anywhere in the game.** Missed a
  menu item, a status readout, or a road callout under other noise? Press
  Comma and the game says it again -- in menus, in the truck, everywhere.
  The A key still replays the last route announcement while driving.

- **The in-cab radio picks up forty-three more real stations.** With real
  streams allowed in settings, live local radio now reaches Portland, Boise,
  Spokane, Salt Lake City, Las Vegas, Reno, Minneapolis, Milwaukee, Detroit,
  St. Louis, Houston, Pittsburgh, Philadelphia, Baltimore, Washington,
  Nashville, Memphis, Birmingham, Tampa, Miami, and more -- plus the wide
  public radio networks that carry the empty country: the Dakotas, Montana,
  the Texas plains, the Upper Peninsula, northern New England, and West
  Virginia. Real jazz, news, roots, and independent music fades in and out
  as you drive through each market, just like FM.

- **The desert Southwest gets its real radio dial.** Six more live
  stations light up the border-to-canyon country: KTNN out of Window
  Rock, the Voice of the Navajo Nation, whose 50,000-watt AM signal
  carries news and country across most of the Four Corners; Arizona
  Public Radio from Flagstaff; Tucson's KXCI community radio; New Mexico
  music on KANW alongside Albuquerque's KUNM; public radio from Las
  Cruces; and community radio in Yuma on the Colorado River. Turn on
  real public streams in Settings and drive Route 66 with the real
  Navajo Nation blowtorch on the dial.

- **The alpha ships with a test book.** A new guide in the docs folder
  walks through everything this version changes and how to hear each
  change for yourself: what to set up, what to do, what to listen for,
  and when to call it working. Written for screen-reader playtesting from
  the first line, with the winter driving tests in a companion volume.

- **Winter tires are now a real choice at the garage.** A winter-compound set
  bites noticeably harder on snow and ice, and the trade is honest: it wears
  faster and gives up a touch of grip on warm dry pavement. Company tractors
  stay on whatever the carrier specs; owner-operators pick their rubber. The
  rig readout and the garage both say which compound is mounted.

- **Snow chains and chain laws have arrived on the steep grades.** Buy a
  chain set at the garage and it rides in the side box until a flashing sign
  before a snowy or icy pass calls a chain law: Level 1 wants winter tires or
  chains, Level 2 wants chains on the drives. Chaining up happens from the
  pause menu while stopped -- it costs real minutes and real fatigue, and
  doing it in the dark costs more of both. Chained on glare ice the truck
  actually holds: stops shorten dramatically and the engine brake stops
  breaking the drive wheels loose on the descent.

- **Chains are honest equipment, not a magic button.** They want chain speed,
  about thirty miles per hour, and they hate bare pavement: run them fast or
  dry and they grind apart until a chain lets go, whips the fender, and the
  set is scrap. Rolling into an active chain law out of compliance gets a
  spoken warning, and the checkpoint past the sign may write a five hundred
  dollar citation.

- **Freezing rain is now its own weather, and it is the one worth parking
  for.** Rain falling just below freezing glazes the road with ice far
  slicker than snow -- a stop from 40 can take more than twice the room of a
  dry stop from 60. The forecast and weather reports call it out, live
  weather recognizes real freezing rain and sleet, and new road hazards come
  with it. If you drive it, crawl.

- **Hydroplaning now depends on your tires, not just the sky.** Fresh tread
  at highway pressure almost never floats, but the more worn your tires, the
  lower the speed where they start riding the water instead of the road --
  bald tires in a heavy downpour let go near 60. When it happens the truck
  calls it out and steering and braking go soft until you ease off. Deeper
  standing water makes it worse; keeping good rubber on the truck is the fix.

- **The engine brake can now break the drive wheels loose on slick roads.**
  The jake slows only the drive axle, and on ice a full-stage jake in a low
  gear is more than that axle can hold -- the truck warns you the wheels are
  sliding, the retard fades, and the right move is a lighter stage or none at
  all. On dry pavement nothing changes; this is a winter discipline.

- **Your rig now wears with how you drive it -- tires, brakes, and engine each
  have their own meter.** Miles and heavy loads slowly eat tire tread, riding
  the service brakes wears the shoes (hot brakes wear them even faster), and
  hours under load wear the engine -- with over-revving and lugging punishing
  it hardest. Wear talks back: bald tires grip less, worn brakes pull weaker
  and overheat sooner, and a tired engine loses power and burns more fuel. The
  engine brake still costs the shoes nothing, so use it on the long downgrades.
  Your delivery summary tells you what each run added, the truck status
  readouts speak all three meters, and the terminal garage now offers brake
  jobs and engine overhauls alongside tires -- each takes shop time and, for
  owner-operators, real money. Company drivers bill the carrier, as always.

- **Truck stops now sell more than fuel: meals, showers, and rig care that
  keep you and the truck going longer.** A hot meal or an energy drink eases
  fatigue right away and makes the next few hours of driving tire you more
  slowly -- Petro's Iron Skillet dinner beats any roadside diner. At a Pilot
  or Flying J, a fuel purchase makes the shower free, just like real life.
  On the truck side, a Speedco or Love's lube bay slows engine wear for the
  rest of the trip, a tire rotation does the same for tread, and a bottle of
  diesel additive helps a little anywhere you fuel. One food buff and one of
  each rig service at a time -- a new one replaces the old -- and none of it
  ever adds legal driving hours. Your status readout tells you what is
  active and how long it has left.

- **The big-name truck stops along your route now fix your rig -- and each
  brand is good at what it is really known for.** Pull into a Love's or a
  Speedco and their tire bay replaces worn tires fast, close to the garage
  price. TravelCenters of America and Petro run full service shops that also
  do brake jobs on the road. Any other major travel center can mount tires,
  at a road markup -- and an engine overhaul still means a trip to your
  terminal garage. Independent stops fix what their listing says, and Big
  Buck's, famously, fixes nothing. Road shops sell the whole job or none of
  it, so if cash is short, plan for the terminal.

- **The biggest map update yet -- 100 new cities to pick up and deliver in.** A
  city is a place a load can start or end, and the map grew from 249 to 349 of
  them, filling in dead zones that used to have nothing drivable for hundreds of
  miles: the mountain West, the northern plains, the Nevada Great Basin, the
  Oregon and California coast, and Appalachia. Whole corridors that simply were
  not there before now connect city to city on the real roads -- Interstate 70
  over the Colorado Rockies, the US-2 Hi-Line across the northern tier, Interstate
  80 across Nevada, and Interstate 75 through the Kentucky mountains among them. Be careful, though -- there are still some challenging
  routes where you had better watch your fuel and get it when you can. Thanks
  to nromey.

- **The All assists preset now switches lane drift off.** The easiest preset
  used to leave whatever lane drift level you had chosen running, so a player
  who wanted the fully assisted ride could still be stuck holding the wheel
  through every exit. Choosing All assists now also sets lane drift to off:
  the truck keeps its lane for you, a tap of Left or Right changes lanes, and
  the change is spoken when you pick the preset. The other presets still never
  touch lane drift, and you can always set it back yourself.

- **Speed limits follow the real road now, all the way across the map.**
  Every route in the country carries its actual posted limits, read from
  real map data instead of one smooth estimate. You will hear the honest
  zones a mountain highway steps through -- the slow canyon stretches, the
  drop before a long descent, the climb back up to highway speed -- where the
  truck used to hold a single guess for miles. Adaptive cruise, the speed
  keeper, and the spoken limit changes all follow these real limits. The same
  sweep quietly recorded every curve and every real runaway-truck ramp along
  the way, groundwork for the steering and descent features still to come.

- **The career is a months-long arc now, and every level up hands you
  something real.** Experience pays out more honestly -- every settled load
  teaches a flat lesson, on-time streaks compound up to forty-five percent,
  undamaged cargo adds a bonus, and specialty freight teaches half again as
  much -- so early levels land within your first sessions while the road to
  level 30 still takes months of real evenings. Along the way every rank
  unlocks something concrete: an extra load refusal at level 5, a deeper
  dispatch board at 6, 10, and 12, specialty freight favored on your board
  at 11, premium long-haul lanes at 12, the full owner-operator checklist
  read out from level 14, and the fleet tractor upgrades above.

- **The engine brake now works like a real three-stage jake.** It slows the
  truck through the gears, so it pulls hardest in a low gear with the engine
  turning fast, and does very little in top gear -- set your gear and speed
  before the hill starts. An automatic transmission drops a gear to put the
  jake to work, and shifts up to protect the engine if the hill spins it too
  fast, leaving you a weaker jake in a taller gear. Heavy enough loads can
  outrun the jake entirely, so snub the brakes early or crawl.

- **Brakes now heat and cool like real drums.** Dragging the service brakes
  down a long grade overheats them until they fade badly; short firm
  applications with the jake carrying the load keep them cool. Going faster
  no longer cools hot brakes, and letting a downhill rev the engine past its
  limit now wears the engine -- running at governed speed is safe.

- **Each truck now keeps its own condition.** Tire, brake, and engine wear,
  damage, and fuel stay with the truck they happened to, so swapping tractors
  at the dealer no longer carries your wear -- or your empty tank -- onto the
  next rig, and the garage fixes the truck you actually drove in. A new truck
  off the lot rolls out fresh with a full tank. Careers from earlier versions
  load unchanged: your current wear settles onto every truck you own.

- **Career 1.9 playtests now follow more of a driver's real journey.** Reusable transcript checks cover career stages, driving modes, keyboard-operated controls, speech ordering, and deterministic road events so regressions are caught before they reach players. A new pacing model also verifies the months-long level curve stays honest as the balance changes.

- **Relaxed driving now leaves real breathing room without removing the truck.**
  Relaxed pacing keeps weather, traffic, air brakes, fatigue, hazards, and
  consequences understandable, but hazards are spaced farther apart, warnings
  allow more response time, collision damage and fatigue build more gently,
  and routine speech is calmer. Standard keeps the previous balanced pressure,
  while the former Fast pacing is now called Realistic and retains the quickest
  decision cadence. Safety warnings also stay in front of hours and fatigue
  chatter instead of being interrupted.

- **The truck revs each gear out when you accelerate hard.** Flooring
  it from a stop used to shift almost the instant it moved, banging up
  through the gears without ever really revving, so it never sounded
  like it was working for you. Now hard acceleration holds each lower
  gear toward its power before shifting, and you hear the engine climb
  and pull through the gears the way a loaded truck should. Easy
  driving still shifts early and quietly to save fuel, and the truck
  still settles into top gear at a calm, believable cruise.

- **Truck speed limits now match what each state's law actually says.**
  Every state was checked against its own statute, and the results moved
  in both directions. Arizona holds trucks to 65 where the signs say 75,
  and the game had been letting you run the car speed -- that is fixed.
  Oregon's default drops to 55, though the eastern corridors that are
  genuinely posted higher for trucks still run their real limit. Idaho
  repealed its truck limit outright this month, and Nevada and North
  Dakota never had one, so all three now match the posted signs. Montana
  correctly runs 70 on the interstates and 65 everywhere else. If a
  stretch you drive got slower, the sign was never the whole story
  there.

- **The co-driver now says when a speed limit is a truck limit.** In states
  that hold heavy rigs below the number on the sign, pressing S says "Truck
  limit 55. California holds trucks to this" instead of just reading the
  figure. Nothing about how fast you may drive has changed -- those limits
  were already being enforced -- but hearing 55 on a road signed 65 no longer
  sounds like the map got it wrong. It is the law for anything with three
  axles, and now the game tells you so.

### Fixed

- **Live weather is ready when you start driving, and it never quietly
  hands your sky to simulated weather.** The game now starts fetching real
  conditions while you are still parked at the terminal, so a drive begins
  on live weather instead of waiting for it to load. And when a weather
  check fails mid-drive -- a dropped connection, a moment of bad signal --
  the game keeps the last real conditions, says they are last-known, and
  keeps trying. Simulated weather only ever appears when the game has had
  no connection at all since it started.

- **The Online services switch no longer touches weather, traffic, or
  parking.** Two testers turned on real-world weather and heard nothing
  but simulated skies because the Online services master switch was
  quietly standing it down. That switch now governs only the orinks.net
  and sharing services -- the drivers board, profile sharing, cloud
  backup, Mastodon, and Discord presence. Real-world weather, traffic,
  and parking follow their own toggles under Settings, and turning one
  on works no matter how the Online switch is set.

- **No more phantom hairpins on the interstate.** The dense road-geometry
  sweep had baked a few thousand impossible curves onto interstate
  mainline -- city-departure kinks and interchange corners recorded as if
  the highway itself bent that hard. At speed one could fire a bogus
  "Hairpin right, advise twenty", shove the truck toward the shoulder,
  and pin the clock to real time on a road that runs straight. Those
  records are now screened out on load. Real mountain interstates keep
  every genuine bend, and the sharp stuff on two-lane passes -- the
  Million Dollar Highway's switchbacks included -- is untouched.

- **A dead radio stream no longer drops you to silence.** When a real
  stream refuses to play, the radio now says which station went off the
  air, moves you to the next station in the same part of the dial, and
  keeps the dead stream off the dial for the rest of the session instead
  of letting you land on it again.

- **Rest-stop sleep no longer turns into a dead end at the exit.** Pressing T
  while rolling toward a sleep-capable stop now plans and names that exact
  stop, then tells you to press X before leaving the highway. A new optional,
  default-off stopping aid can finish the stop at the entrance after you take
  the selected exit; it never chooses or signals an exit for you. Missing or
  canceling the stop clears the aid and gives spoken recovery guidance.

- **The stop bar's steady tone is calmer.** The tone that means you are on top
  of the stop bar was high and sharp -- hard to sit through for the seconds it
  is meant to hold. It is now a much lower, steadier tone, easy on the ear
  while still carrying over the engine. It stays just as easy to tell from
  the ticks leading up to it: where those quicken, this one drops.

- **The stop bar's steady tone always stops.** The continuous tone that means
  you are on top of the stop bar could be left sounding for the rest of the
  drive: reach it creeping up to a red light, and once you crossed the bar
  the tone stayed on, straight through the menus, until the game was closed.
  It now ends the moment the bar is behind you, whether you waited out the
  red, crossed on the green, or stopped for a sign, and it goes quiet on its
  own if anything else ever gets in the way of ending it -- pausing or
  arriving silences it at once. The tone comes back only when the next stop
  bar is under your bumper. Rumble strip sound left playing when you paused
  on the strip is gone the same way.

- **A damaged settings file no longer takes the game down with it.** If your
  settings file was left half-written by a crash, or ended up holding
  something that is not a volume level where a volume level belongs, the game
  could refuse to start at all. Anything it cannot read as a level now falls
  back to that setting's normal value, and it says so in its log. A level you
  really did set is untouched -- turning something down to nothing still
  means nothing.

- **The engine keeps one voice.** When the game's sound file was older than
  the game itself, the engine could take part of its voice from the old file
  and part from the new one, crossfading between two different recordings as
  the revs climbed. The engine now takes every layer of its voice from the
  same place, so it sounds like one engine again.

- **A bad sound file no longer costs you every sound.** If the game's sound
  file is damaged -- a download that stopped short, a copy that did not
  finish -- the game used to go completely silent. Now it says so in its log
  and plays whatever sound it can still find, and a single unreadable sound
  inside the file costs only that one sound instead of all of them.

- **Cruise no longer claims a hill has beaten it while it is winning.** When
  a rising speed limit or a higher set speed put the target well above the
  truck, cruise flooring the pedal to catch up could be announced as losing
  the grade -- even as the truck accelerated. The call now waits for a real
  grade, ignores the moment of a gear change, and has to stay true for a few
  seconds before it speaks.

- **The engine's voice is now longer than your memory.** The deepest
  layer of the repeating-engine problem: each layer of the engine sound
  was a short recording whose rise and fall a careful ear could learn
  and anticipate. Every layer has been rebuilt three times longer from
  its own recording -- same voice, same working rhythm, but the fine
  texture never repeats, so there is no pattern left to learn.

- **Public-radio stations that had gone silent play again.** A sweep of
  every stream in the catalog turned up a batch that had drifted to stale
  addresses -- big public stations among them, like KUAR Little Rock, WBFO
  Buffalo, Maine Public, South Dakota Public Broadcasting, and Texas Public
  Radio -- and pointed them back at their current feeds, so they tune and
  play instead of coming up quiet. A few whose streams have genuinely gone
  away are set aside for now, so the dial does not hand you dead air where a
  station used to be.

- **The engine never repeats itself exactly anymore.** Even with clean
  loops, a careful ear could catch the engine sound recurring on a
  perfectly fixed cycle at steady revs. Each layer of the engine voice
  now wanders very slightly in speed and level -- the way a real
  engine's rhythm breathes -- so there is no fixed cycle left to
  notice.

- **The repeat key gives back the hazard warning, not the assist that talked
  over it.** With automatic emergency braking on, "Emergency braking engaged."
  cuts in over the warning that set it off. Stepping back with the repeat key
  then handed you the assist announcement, so the warning you actually missed
  sat one press further away than you would expect. The assist no longer takes
  a place in the repeat history, and one step back from a collision reaches
  "Brake now!" again. You still hear it at the time, and it stays in the
  message review list.

- **Cruise control holds your speed down a hill instead of running away
  with it.** Coasting was all cruise could do about going too fast, so a
  downgrade just carried the truck past the speed you set and kept it
  there -- a gentle two percent grade sat nine over, and a steep one kept
  building with nothing to stop it. Now cruise uses the engine brake the
  way you would, stepping it up only as far as the hill needs, and comes
  down on the service brakes in proper snubs when the jake alone will not
  hold. The old behavior dragged the brakes lightly and forever instead,
  which quietly emptied the air tanks until the spring brakes set and
  stopped the truck dead on a downhill.

- **Cruise control answers a hill as you reach it, not ten seconds later.**
  It used to feed the throttle in slowly with no idea what the grade was
  asking for, so every climb cost you speed before it responded and a real
  pull could take twenty miles an hour off the truck. Cruise now reads the
  grade under the wheels and gives it the throttle it needs right away.

- **The automatic gearbox downshifts for a hill instead of lugging up it.**
  With the accelerator on the floor, the road going up, and the truck still
  losing ground, the box used to hold top gear because the engine had not
  quite started lugging yet -- so the truck sank toward a crawl in a gear
  that could never pull it. It now goes looking for a lower gear, the way a
  driver does, as long as that gear genuinely turns the load better.

- **A hill no longer rewrites your cruise speed for the rest of the run.**
  On the All assists setting, descent control lowered your cruising speed
  to 55 the moment a grade steepened -- and left it there afterward, on the
  flat and uphill too, until you noticed and set it again. The safe descent
  speed is now a ceiling that lasts only as long as the hill; your number
  comes back at the bottom.

- **Route-transition assistance no longer traps the truck short of a stop
  bar.** If you braked yourself while the assistance was already braking for
  a stop sign or a red light, the truck could come to rest a little short of
  the line, in a spot where the assistance kept holding the pedals but never
  finished the stop. The accelerator did nothing and the truck could not be
  moved again for the rest of the drive. Coming to a stop short of the line
  now hands the pedals straight back, and you are told how far ahead the bar
  is so you can drive up and stop again on it.

- **Long local approaches step down like real streets.** A facility
  approach longer than a couple of miles now runs 45 on the wide-out
  stretch, drops to 25 for the last two miles, and 15 at the gate --
  instead of a blanket 25 crawl from the moment you left the yard.
  Short approaches and the gate zone are unchanged.

- **No more 35-mile deadheads to a local pickup.** Some facilities'
  map pins landed counties away from their city, and the local
  deadhead drive to them stretched to thirty-plus straight-line miles.
  Local approaches now stay between about two and nine miles -- the
  range a real cross-town deadhead runs -- while the misplaced pins
  get properly re-mapped.

- **A same-city dispatch no longer zones the whole interstate at 25.**
  A job from one facility to another inside the same city -- yard to
  cross-dock around the interstate loop -- was mistaken for a facility
  street approach, blanketing the entire highway run in the 25 mile per
  hour access-road zone and silencing its curve and limit warnings.
  Real street chains keep their street speeds; highway miles keep
  highway rules.

- **Automatic shifts sound like a real gear change now: clunk, sigh,
  clunk.** During a shift the engine used to hang frozen at its old
  revs through the whole interruption, then leap to the new pitch all
  at once -- and the moment the gear actually took was silent. Now the
  revs audibly fall away toward the next gear while the box is between
  gears, exactly like a real automated manual, and the gear taking hold
  gets its own soft clunk as the engine picks the load back up.

- **The engine stopped ticking and the jake stopped breathing.** A faint
  click repeated in the engine sound at cruise -- speeding up and slowing
  down with the revs -- and the jake brake's growl carried a little dip
  that pulsed on every cycle. Two culprits, both fixed: the seams where
  those sounds loop are now clean, and a stray click that had been
  recorded inside the engine sound itself -- repeating on every pass --
  has been patched out. No tick at any speed, no pulse in the growl.

- **Curve warnings now come with time to act on them.** At compressed
  time pacing, "Curve right, half a mile" could go from spoken to "too
  fast" in three real seconds. Any bend the game warns you about now
  plays out in real time from the moment its warning window opens until
  the curve is behind you -- the same rule controlled ramp endings
  already follow -- so the callout, your reaction, and the braking all
  get real seconds at any time compression.

- **A sleep that does not reset your hours says so, first and loudly.**
  Waking from a sleeper-berth rest with the split still pending now
  leads with the consequence: "This sleep did NOT reset your hours.
  Your duty window closes in 4.2 hours, at 6:05 AM" -- before anything
  else. The 60- and 30-minute window warnings also speak again after
  such a sleep instead of staying silent because they had already fired
  earlier in the shift. And the roadside out-of-service stop now
  explains itself completely: which limit you blew, in plain words, and
  that the delivery deadline kept counting while you sat.

- **A serious log-check violation now pulls you over for real.** Getting
  caught over your hours used to play a tone, claim you were stopped,
  and silently jump the clock ten hours while you kept driving. Now it
  is a real roadside stop: lights and siren behind you, signal and
  brake to the shoulder, the officer writes the out-of-service order,
  and the ten hours pass while the truck is actually parked.

- **Dispatch deadlines now respect the hours already on your clock.**
  Accepting a load six hours into your shift used to get a deadline
  planned for a fresh driver -- impossible to make once the law forced
  your 10-hour rest mid-run. The deadline now plans around your actual
  remaining driving hours and duty window, and when it stretches to
  cover a rest, the offer says so: "planned around the 10-hour rest
  your hours will force."

- **Rolling a green light at the ramp end takes you straight onto the
  streets.** Crossing the terminal legally on a green used to leave you
  marooned past the end of the ramp -- the city streets refused to
  start until you came to a dead stop in the middle of the road. The
  street chain now begins at whatever legal speed the light let
  through; only the dock itself still wants you at a crawl.

- **The radio finds its station again after a stop.** A live station
  used to go silent after a dock or terminal visit and stay that way --
  all you got was a mysterious burst of static every few seconds, and
  the only cure was tuning away and back. Now the radio reconnects the
  stream by itself within a moment of rolling out, tells you if the
  station really cannot be reached, and never plays fringe static over
  a station you cannot hear.

- **Fringe static finally sounds like FM.** The old crackle was really
  an AM lightning-storm sound; an FM set between stations plays a
  smooth frying hiss instead. The static you hear at the edge of a
  station's range is now that hiss, shaped the way a real receiver
  shapes it.

- **Speed-limit drop warnings no longer double up.** The advance warning
  before a big posted-limit drop could speak twice back to back. It
  speaks once now.

- **The game no longer says you have arrived while handing you two miles
  of streets.** Coming off the destination exit at a facility with a
  street approach, the end of the ramp announced "You are at [the
  facility], come to a complete stop" -- and then the turn-by-turn
  street directions began. When streets follow the ramp, the arrival
  announcement now waits for the actual gate; the "off the ramp and
  onto city streets" callout owns that moment instead.

- **No more "corridor between" announcements pretending to be towns.**
  Two hundred forty-six legs carried a leftover data placeholder named
  like "CA-99 corridor between Sacramento and Yuba City", and the place
  callouts and route report spoke them as if they were real places. The
  placeholders are gone from the map data, and the routing rule that
  forced them to exist is fixed so every affected road stays dispatchable.

- **The gear change comes at the top of the rev, not a second after.**
  Above the launch gears, the transmission used to rev to its shift
  point and then sit at the crest waiting out an internal timer before
  taking the gear -- you heard the engine top out, then a long beat,
  then the shift. Now the revs earn the shift: the moment the engine
  crests the threshold on a hard pull, the gear comes. The deliberate
  launch cadence through the low gears is unchanged.

- **Ramp-end callouts now tell you the approach speed limit -- the one
  at the bar.** The stop sign and traffic light announcements named the
  control but never how fast you were allowed to approach it. Every
  callout that names the bar now carries the limit of the street you
  are entering -- "Light red, about 800 feet to the stop bar, speed
  limit 25" -- including the repeating status line, and on the lowest
  speech verbosity the countdown compresses to one line with everything
  a driver needs.

- **Manual shifting answers the moment the clutch comes out.** Shifting by
  hand used to leave the truck coasting for up to a second after you
  released the clutch, because the automatic gearbox's internal shift
  delay was charged on top of your own clutch work. Your clutch is the
  interruption now: the box only takes its quarter-second through
  neutral, so a clean shift pulls again as soon as you let the pedal out.

- **Period walks the speech history forward.** Comma has always stepped
  back through recent speech; now Period steps forward again toward the
  newest line, the same comma-and-period pairing screen-reader players
  know from Civilization VI. Pressed on its own, Period simply re-reads
  the newest line.

- **The updater no longer hides a developer snapshot released the same
  day as a stable build.** On the developer snapshots channel, a stable
  release published in the small hours used to mask that morning's
  snapshot -- even when the snapshot carried newer fixes -- because the
  two were compared by date alone. Updates now compare by the actual
  publish moment, so whichever build is genuinely newest is the one
  offered.

- **The route report tells the truth on the facility approach.** After
  taking your destination exit, pressing R used to recite the highway you
  had already left, with a frozen miles-remaining count, while the truck
  rolled city streets toward the gate. Now it answers with the approach:
  the street you are on and how far to the gate -- and once the route has
  ended, it answers with the gate itself, the same answer the S key gives.

- **The engine revs freely when you sit with the parking brake set.**
  Blipping the throttle while parked used to drag the engine up to a
  weak, half-hearted rev and then stall it, with the game repeating that
  you must release the parking brake. Now, whenever the parking brake is
  holding you still, the engine answers the throttle across its whole
  range -- so you can warm it up, build air faster, or just listen to it
  come alive -- and it settles back to a steady idle when you let off.

- **Stop signs at ramp ends finally tell you where to stop.** A
  stop-sign ramp used to say "brake to a full stop there" once and then
  go silent -- no countdown, no closing tick, no answer from the S key
  -- so the first hint of the bar's position was cross traffic in your
  trailer. The sign now gets everything the traffic light already had:
  the distance countdown, the parking-sensor tick that speeds up as the
  bar closes, S answering with the sign and the gap, and guidance when
  you stop short. Route-transition assistance brakes and completes the
  stop for you when it is on.

- **Driving past a facility entrance no longer goes silent.** Arriving at
  a pickup, delivery, or city service used to announce itself once; if
  you rolled on -- easy to do with cruise re-engaged -- the game said
  nothing more for the rest of the drive, and the delivery quietly went
  late. Now the gate repeats its instruction every ten seconds while you
  are still moving, cruise drops each time so the truck is never held at
  speed past a dead end, and the S key answers with the gate itself --
  "At Chicago Port Terminal. Stop to dock." -- instead of a speed limit
  that stopped mattering when the route ended.

- **The route report knows when you have arrived.** Pressing R after
  reaching a facility used to recite the highway route you had already
  left -- "on I-90 West, 3 miles remaining" -- with a countdown that
  never moved. At a facility it now says so: "You have arrived. At
  Chicago Port Terminal. Stop to dock."

- **Adaptive cruise now drives the bends instead of quitting on them.**
  With curve callouts and curve speed assistance on, a bend advised
  well below your set speed used to shut cruise off entirely -- "you
  need manual speed control" -- handing you the pedals mid-corner.
  Cruise now eases its target to the bend's advisory speed, the same
  way it eases for an exit ramp, and climbs back to your set speed once
  the bend is behind you. You only get handed manual control when a
  bend is genuinely too tight for cruise to hold at all.

- **Curve speed assistance stopped talking over itself.** When adaptive
  cruise and the curve brake disagreed, the assist flipped between
  "slowing" and "released" several times a second and said so every
  time. It now holds its decision through the bend and speaks at most
  once every fifteen seconds.

- **Turning on real-time traffic no longer crashes the game.** With
  Traffic source set to real time under Settings, Speech and weather,
  the game closed with an error moments after any drive began. It now
  stays up, and the live incident alerts it was trying to speak work
  properly for the first time: they report crashes and closures near
  where your truck actually is, in the state you are actually driving
  through, instead of a fixed spot in Ohio. Thanks to Stickbear for
  reporting the crash.

- **Curve calls arrive on time and tell the truth about distance.**
  A curve warning could get stuck in line behind scenery chatter and
  reach your ears with the bend seconds away while still saying "a
  quarter mile." Curve calls now cut ahead of everything less urgent,
  a bend closer than a few hundred feet says "just ahead" instead of
  rounding up, and at highway speed every call now comes at least
  thirty seconds before the bend -- the faster you go, the further out
  the co-driver reads. If a call ever cuts something off, the comma
  key steps back through recent speech. And if your own stop-speech
  key silences a curve call mid-sentence, the call comes back once, a
  couple of seconds later, with a fresh distance -- unless you have
  already slowed for the bend, in which case it respects the silence.

- **Chained bends are one call now, not a flood.** In S-bend country
  every "then right" tail was followed seconds later by that same
  bend's own full call, so linked curves talked over the steering they
  were describing. A bend covered by a "then" tail no longer gets its
  own call -- and the tail tells you what it is when it matters:
  "Sharp left, half a mile. Advise 35. Then hairpin right, advise 25."
  One chain, one read, like a proper co-driver.

- **Driving to a local dock no longer sounds like driving to town.**
  On the road out to a pickup or delivery in your own city, the route
  readout said "toward Camp Verde" while you were pulling out of Camp
  Verde -- technically true, thoroughly confusing. Local facility runs
  now name where you are actually going: "toward dry warehouse Camp
  Verde Dry Warehouse," with the destination line to match.

- **Speed-limit calls now know which way the town is.** A limit drop
  just past a city used to say you were approaching it while it shrank
  in your mirrors. If the town is behind you, the call now says
  "leaving" instead -- so a drop on the far side of Sedona no longer
  sounds like you turned around.

- **Town speed limits no longer follow you out of town.** On two-lane
  highways the map sometimes knew a village's 30 but not where it ended,
  and the low limit could rule miles of open road past the last house --
  a player found NY-12 out of Norwich holding 30 for nine miles. The map
  now records where real posted data runs out, and past that point the
  road goes back to a normal open-road limit for its highway type. Nearly
  every corridor gets this in the same sweep.

- **Missing your destination exit on a rural highway no longer strands
  you.** On two-lane highways the game could lose track of the
  destination exit after a second miss: dispatch claimed to reroute you,
  but no exit was ever announced again and the trip sat at zero miles
  remaining while you drove in circles. Every miss now loops you back
  onto a real approach with the exit announced fresh, on every kind of
  road.

- **Live weather no longer flips between rain and freezing rain on its own.**
  When your career keeps its own calendar apart from the live feed, real rain
  is matched to the career season once when it arrives -- so a cold-season
  shower can come in as freezing rain -- and then holds. It no longer switches
  back and forth as the day warms and cools, only changing when the real report
  or the town it is for changes.

- **Downloaded builds no longer crash when you continue a career.** The
  packaged game was missing several data files that the source version
  reads straight from disk: continuing a career crashed on the missing
  buff catalog, and truck-stop purchases, city-service errands, real
  facility driveways, the radio catalog, and the new curve callouts
  could be silently absent from a downloaded build. All of that data now
  ships sealed inside the game itself, and the build check now refuses
  to package a game that cannot load its own career.

- **Taking an exit no longer talks you out of it.** With lane drift on, the
  exit slowdown used to say "confirm the exit when ready" -- but there is no
  confirm control, and pressing the exit key again actually canceled your
  signal and cost you the exit. The prompt now says what to really do: hold
  Right for the exit lane and keep slowing. And within the last mile of an
  exit, a stray press of the exit key keeps your signal on and says so;
  canceling there now takes a deliberate second press. If you tap Left or
  Right near an exit with lane drift on, the game now explains that taps only
  nudge the wheel and you should hold the key instead of leaving you in
  silence, and after a missed exit the short-form turnaround announcement now
  reminds you to signal again for the next pass.

- **You cannot roll over a ladder at 25 anymore.** Hazards called out as
  "brake or change lanes" are fixed objects in your lane -- road debris, a
  blown retread, a stopped vehicle -- and slowing to the moving-hazard safe
  speed used to clear them, which never made sense. Now a fixed object takes
  either the swerve (a lane change into a clear lane, at full speed) or
  braking nearly to a stop before you ease around it. The warning window
  allows for the longer stop, a spoken hint reminds you the object is still
  in your lane if you settle at the old safe speed, and automatic emergency
  braking brings the truck all the way down to a crawl for these. Moving
  hazards -- animals, whiteouts, stopped traffic -- still clear below 25.

- **Emergency braking now saves you even on hot or worn brakes.** The
  automatic emergency braking assist timed its intervention using the
  truck's spec-sheet braking numbers, but hot drums, worn shoes, and a
  heavy load all brake worse than the spec sheet -- so on tired brakes the
  assist could engage two seconds before the collision it was supposed to
  prevent. The assist now measures what the brakes can actually deliver
  right now and engages early enough to matter, with a safety margin for
  the heat the stop itself adds. Hazard warnings also arrive earlier when
  the truck genuinely needs more stopping room.

- **The ramp light says how far back you stopped.** "Creep ahead" was the
  wrong instruction when your cautious stop landed six hundred feet from
  the stop bar -- creeping that far takes several light cycles. When you
  stop well short, the game now says the distance and tells you to drive
  up and stop at the bar, using the red phase to close the gap.

- **The ramp light now tells you where you are, not just what color it is.**
  Stopping cautiously when the ramp light was announced could leave you a
  quarter mile short of the actual stop bar -- too far to cross on one green
  from a standstill -- and the light just kept cycling with no way to know
  why. The game now says when you are stopped short of the light and tells
  you to creep up to the stop bar, the yellow and green announcements say
  whether you have reached the bar, and the first callout says to roll down
  and stop at the light rather than just "brake to a stop."

- **Missing the destination exit twice no longer strands you at the end of
  the road.** The first missed destination exit looped you back for another
  approach, but a second miss silently gave up: the trip pinned at zero miles
  remaining, driving or backing changed nothing, cruise refused to stay on,
  and no exit was left to signal for. Dispatch now reroutes you back for
  another approach every time, and the turnaround drops you far enough out to
  hear the callout, signal, and brake -- a full approach window instead of a
  few compressed seconds.

- **The driving event voice no longer narrates the past.** With the
  separate event voice enabled, a busy stretch could queue announcements
  faster than the voice speaks, so you would arrive at the dock and sit
  through "slow down for the dock, at the dock, delivering" after the
  trailer was already empty, while the backlog talked over traffic-light
  sounds. When queued announcements fall too far behind the moment they
  describe, the stale ones are now dropped and the newest speaks
  immediately, so what you hear is always about what is happening now.

- **Street directions come one turn at a time now.** Setting out on city
  streets used to read the whole route in one burst -- start, turn, and
  continue directions all at once. The navigator now speaks only the next
  maneuver, announcing each turn as you approach it.

- **Street names no longer read out raw map codes.** Some streets spoke
  their entire highway-number list from the source map data, like "North
  Michigan Street, S R 9 3 3, B U S, U S 3 1". Spoken street names now
  keep just the street and its primary route number.

- **The merge instruction is the first thing you hear when you depart.**
  Pulling out with a load used to announce a travel plaza ahead before the
  "merge onto the highway" instruction, all in the same breath as the
  dispatch summary, so the one line you had to act on was easy to miss.
  Navigation now speaks first, and travel plaza and rest stop notices wait
  a moment whenever another road announcement just played.

- **Adaptive cruise no longer crawls behind traffic it has not caught up
  to.** Cruise used to match the speed of any slower vehicle up to two and
  a half miles ahead, so the truck could dawdle far below the limit behind
  someone you could not even hear yet, while "Traffic ahead, adaptive
  cruise reducing speed" repeated every few seconds. Cruise now holds your
  set speed until you are genuinely closing in, eases down smoothly to
  follow at the set gap, and speaks the traffic warning once, not on
  repeat.

- **Braking to a stop no longer drops the truck into reverse -- and
  neither does tapping the brake to check you are stopped.** Holding
  the brake through a stop used to select reverse the moment the truck
  stopped -- including when the game itself said to hold the brakes at
  a red light -- and reverse then swaps the pedals, so your next press
  moved you the wrong way. Now every direction change takes one
  deliberate gesture in both direction-change styles: come to a stop,
  release the control, then press and HOLD it for a moment. A press
  that lands while still rolling is part of the stop, and a quick tap
  at a standstill just brakes -- so confirming the truck is holding
  never grabs a gear. The spoken key help teaches the gesture. This is
  a changed habit if you were used to hold-through reversing.

- **Seven real radio streams play again after a full dial checkup.** KJZZ
  Phoenix, KCRW Los Angeles, KUNM Albuquerque, KUTX Austin, KERA Dallas,
  KCUR Kansas City, and WBUR Boston had all moved or retired their old
  stream addresses, so tuning them fell back to satellite with "station
  unavailable." Every real stream in the catalog was live-tested and the
  dead ones repointed to each station's current stream. WABE Atlanta has
  no working public stream right now and leaves the dial until one
  returns.

- **Ramp-end traffic lights now have a yellow phase, speak every change,
  and no longer punish you for a light that changed behind your back.**
  The light used to announce only its first change: it could say green
  while you were still rolling up, silently flip back to red, and then
  blame you for running it -- with real trailer damage. Now every green,
  yellow, and red is spoken as it happens, greens run long enough to
  cross from a stop, and entering on yellow is legal, exactly like the
  real law. Yellow means stop if you are not already at the light.

- **Interstate speed limits no longer drop to city speeds at the ends of a
  leg.** Leaving or approaching a city, the spoken limit could fall to a
  25 or 30 from a nearby city street and stay there for miles of open
  interstate -- Interstate 10 out of Buckeye held 30 for ten miles. Four
  hundred thirty legs across the interstate network now carry their real
  highway limits the whole way, so the limit you hear is the limit the
  road actually posts, and speeding enforcement matches it.

- **US highways and parkways got the same speed-limit cleanup.** US-60
  out of Phoenix held a baked 25 for twenty-two miles of the
  Superstition Freeway. Two hundred twenty-seven more legs now start at
  their real highway speed, while honest small-town limits -- like
  US-60's real 35 through Globe -- stay exactly as posted. And where a
  town's street speed was the only reading a long route had -- Globe's
  35 used to rule all eighty-eight miles to Show Low -- the route now
  uses honest open-highway speeds instead, on twenty-three more legs.

- **A dropped speed limit now gives you braking time before a strike.**
  When the posted limit steps down, enforcement waits while you actually
  slow -- about the seconds a loaded truck honestly needs -- instead of
  writing a strike the moment the sign changes. Staying on the throttle
  through the drop forfeits the grace, so it rewards compliance, not
  coasting past signs.

- **Touching the brake now switches cruise control off, like a real
  truck.** Any press of the service brake or the emergency brake drops
  cruise immediately and announces it, instead of cruise quietly pulling
  the truck back up to speed after you slowed down on purpose.

- **Port terminals only show up in cities that really have a port now.**
  Inland towns like Dallas, Atlanta, and Lampasas no longer offer loads
  from a make-believe port terminal. Port freight comes from coastal,
  Great Lakes, and navigable-river cities with working docks, and small
  towns far from any rail yard no longer list an intermodal ramp on the
  dispatch board. If a saved dispatch board still shows one of the old
  offers, accepting it politely pulls the load instead of misbehaving.
  And four real Great Lakes ports the old map missed -- Toledo, Detroit,
  Chicago, and Green Bay -- now have working docks of their own.

- **An empty truck no longer machine-guns up through the gears.** Running
  light, the transmission used to grab every single gear about a second
  apart, and sometimes bounce straight back down, because it judged lugging
  as if the truck were fully loaded. A light rig now skip-shifts the way a
  real driver does, starts out in a higher gear, and keeps that launch gear
  at a stop instead of snapping back to first.

- **Updating the game no longer flags your save as changed outside the game.**
  A save written by an earlier version could be wrongly marked as modified the
  first time a newer version loaded it, even though nobody touched the file.
  The check now recognizes saves from earlier versions for what they are, so
  an update never puts that mark on an untouched career.

- **The engine revs freely when you sit with the parking brake set.**
  Blipping the throttle while parked used to drag the engine up to a
  weak, half-hearted rev and then stall it, with the game repeating that
  you must release the parking brake. Now, whenever the parking brake is
  holding you still, the engine answers the throttle across its whole
  range -- so you can warm it up, build air faster, or just listen to it
  come alive -- and it settles back to a steady idle when you let off.

- **Quick manual downshifts now respect the clutch the moment you press it.**
  The previous clutch over-rev fix corrected the truck simulation, but the
  live driving controls still had a timing gap: if you pressed Shift and tapped
  Q or W quickly, the gear-change key could be handled before the next frame
  refreshed the clutch state. That could still produce a false redline warning
  or engine damage even though the clutch was physically held down. Manual
  shift inputs now recognize Shift as clutch-down immediately, so damage only
  starts if you release the clutch while the selected gear is too low for your
  road speed. Sorry for missing this player-input path in the first fix.
  Contributed by corykad ([@corykad](https://github.com/corykad)) in
  [PR #157](https://github.com/Orinks/Freight-Fate/pull/157).

- **Paying down what you owe never empties your wallet anymore.** Every
  payment option at the yard now keeps two hundred dollars of fuel money in
  your pocket, so choosing Pay half can no longer leave you at zero.

## 1.8.8.1 - 2026-08-08

### Added

- **Creating your first career now offers to connect this computer to an
  orinks.net account.** Right after you hear "Welcome aboard" and where your
  truck is parked, the game asks once whether to connect this computer to an
  orinks.net account, with a code and a browser confirmation. It only asks the
  once -- decline with Not now, or just press Escape, and driving starts
  right away with nothing else to answer. Connecting links the computer to an
  account; it does not turn anything on by itself, and you can connect any
  time later from Online on the main menu, where cloud backup and the
  drivers board each stay off until you turn them on yourself.

### Fixed

- **Live weather no longer gives up on a healthy weather service.** Weather
  stations file their reports once an hour, but the game treated any report
  more than thirty minutes old as a failure -- so for most of every hour it
  quietly switched to simulated fallback weather even when the service was
  fine. A report now stays current until it is well past the hourly cycle,
  so live weather stays live, and the weather app still tells you exactly
  how old the reading is.

- **Real-world weather now follows the truck instead of the next city.** Live
  National Weather Service conditions update as you move along a route, and
  weather reports say when conditions are live, still loading, last known, or
  simulated because the live service is unavailable. Old failed-refresh rain
  now expires instead of lingering as if it were current.

- **Loading a career no longer cuts off its own welcome.** Choosing a saved
  career from Continue latest career or Choose career used to say "Welcome
  back" and then get cut off mid-sentence by the terminal announcing where
  you are parked, so you never heard your money or which terminal you loaded
  into. The welcome is now heard in full before the terminal speaks.

- **Backing all the way out of Settings now speaks "Settings saved."**
  Pressing Escape from the settings categories used to say it and then get
  cut off by the main menu announcing itself again, so it was never actually
  heard. It now plays after the main menu's own announcement, so you get the
  confirmation.

## 1.8.8 - 2026-08-05

### Changed

- **Connecting a computer to orinks.net no longer involves copying and
  pasting anything.** Setting up online features used to mean copying a
  Driver ID and a token from the website and pasting each one into the
  game. Now the game shows an activation code, reads it out loud, and can
  spell it letter by letter or copy it to the clipboard if you would
  rather type it into the browser yourself. Once you confirm the code on
  orinks.net, the game finishes connecting on its own.

- **Automatic Mastodon posts moved to their own hashtag.** Deliveries shared
  to your Mastodon account now carry the FreightFateRuns hashtag instead of
  the FreightFate one. Players use the FreightFate tag to share their own
  thoughts about the game, so anyone who had muted it to keep the automatic
  posts out of their timeline was quietly losing those conversations too.
  The two are separate now: FreightFate is for people talking, FreightFateRuns
  is for the game posting. There is nothing to change in the game. If you
  muted the FreightFate tag because of the delivery posts, you can unmute it
  and mute FreightFateRuns instead, and if you liked following other drivers'
  runs, follow FreightFateRuns to keep seeing them. The change is on the
  orinks.net side, so it already applies to every version of the game.

- **The automatic transmission works each gear harder before shifting up.**
  Pulling a load, the engine now runs into a higher, more realistic RPM range
  in every gear instead of grabbing the next one early, so climbs sound and
  feel like the truck is actually working. Running empty, the two-gear jumps
  the box likes on flat ground now land far enough above the downshift point
  that it no longer shifts up and immediately drops back down. Contributed by
  corykad ([@corykad](https://github.com/corykad)) in
  [PR #144](https://github.com/Orinks/Freight-Fate/pull/144).

### Fixed

- **Picking a lower gear with the clutch held no longer damages the engine.**
  Downshifting several gears at highway speed used to bring the redline
  warning and engine damage the moment the gear was selected, even with the
  clutch to the floor and the engine disconnected from the wheels. The
  warning and the damage now begin only if you release the clutch while the
  gear is too low for your road speed. Contributed by corykad
  ([@corykad](https://github.com/corykad)) in
  [PR #144](https://github.com/Orinks/Freight-Fate/pull/144).

- **Copying to the clipboard works on Linux.** On Linux, copying a delivery
  summary, a reviewed message or a link always said the copy did not take.
  Linux desktops offer clipboard text under a different name than Windows
  does, and the game was only ever asking for the Windows one. It now asks for
  the names Linux really uses, so copying out of the game works, including
  copying your activation code during online setup. Windows and Mac are
  unchanged. Thanks to a player report.

- **Continuing a saved run announces the right date and season again.** When
  you picked a run back up, the calendar went back to the day you set out on
  rather than the day you had driven into, so a haul that had rolled past
  midnight came back on yesterday's date, and a long run that had carried you
  into a new season heard the old one, with the weather to match. Continuing a
  drive now puts the calendar at the same moment your trip clock is at, so the
  date, the season and the weather all agree. Contributed by Day Garwood
  ([@day-garwood](https://github.com/day-garwood)) in
  [PR #146](https://github.com/Orinks/Freight-Fate/pull/146).

- **Continuing a saved run no longer pushes your deadline further out.** Every
  time a delivery was picked back up, the game worked the deadline out again
  from where you were and how long you had been going, which quietly gave you
  more hours than dispatch had agreed to. A run you were running late on could
  be rescued just by saving at a stop and continuing. Deadlines now stay where
  dispatch set them. A run already under way gets one last recalculation the
  first time you continue it after this update, so nobody loses hours they had
  been counting on, and it is fixed from then on. Contributed by Day Garwood
  ([@day-garwood](https://github.com/day-garwood)) in
  [PR #146](https://github.com/Orinks/Freight-Fate/pull/146).

- **Quitting mid-drive writes a save that agrees with itself.** Quitting to the
  title mid-drive puts you back at the stop you last saved at, but the save was
  still being written with the hours of service and the fatigue you had built
  up since leaving that stop. Continuing always put them back, so the drive you
  returned to was correct either way, and this only mattered to the cloud
  backup, which was storing a shift that never happened. The save now records
  the stop you will actually resume from. Contributed by Day Garwood
  ([@day-garwood](https://github.com/day-garwood)) in
  [PR #146](https://github.com/Orinks/Freight-Fate/pull/146).

## 1.8.7 - 2026-07-30

### Added

- **The drivers board is now reachable from the pause menu.** You can hear
  who is hauling right now without quitting to the main menu. The new
  "Drivers board" item sits between Settings and Abandon job in the pause
  menu. Viewing the board shares nothing about you. Contributed by wleicht
  ([@wleicht](https://github.com/wleicht)) in
  [PR #136](https://github.com/Orinks/Freight-Fate/pull/136).

### Changed

- **Reviewing what the game said now works the same way everywhere.** Comma
  and period stepped through recent speech on every screen, while a fuller set
  of review keys only ever worked while driving, and the two kept separate
  histories. There is one history now, and every review key works on every
  screen. Comma still repeats what was just said and steps back from there,
  period moves forward, and you can now also jump to the oldest or newest
  message with Ctrl and those same keys, switch between all messages, general
  messages and driving events with the bracket keys, and copy the message you
  are on with Ctrl+C, whether you are driving or sitting in a menu. Each
  press reads the message and nothing else, the last 200 are kept, and moving
  through menus is no longer mixed into the history, so what you step back
  through is what actually happened. Checking the pause menu
  mid-run no longer leaves a "Paused" and a "Resumed" between every pair of
  announcements. New announcements do not move your place while you are
  reviewing, and once you have left the keys alone for ten seconds the next
  press starts fresh from the newest message with all categories showing, so
  comma always repeats what was just said instead of picking up where you
  left off earlier in the run. Typing a driver name still takes punctuation
  as punctuation. Raised by wleicht
  ([@wleicht](https://github.com/wleicht)) in
  [issue #134](https://github.com/Orinks/Freight-Fate/issues/134).

- **Your online driver token is now kept in your computer's password store.**
  If you have linked the game to an Orinks account, the secret half of those
  credentials used to sit in a plain text file alongside your saves, readable
  by anything that could reach the folder. It now lives in Windows Credential
  Manager, the macOS Keychain, or your Linux keyring, the same places your
  browser keeps saved passwords. The change happens by itself the next time
  the game starts, and your Driver ID stays where it was, so there is nothing
  to re-enter and nothing to set up. If secure storage is unavailable, the
  old credentials remain intact instead of being removed, and Windows will
  not put a new token into a plain text fallback file. The setup menu explains
  how to retry without claiming that unsaved credentials connected. Thanks
  to trodick, [PR #133](https://github.com/Orinks/Freight-Fate/pull/133).

### Fixed

- **Automatic speed control no longer says it is resuming as you pull up to
  a pickup.** Rolling up to the gate with cruise or the speed keeper on, you
  were told speed control was paused and would resume after you departed with
  the load, and then a moment later heard it announce that it was resuming
  after all, before it switched off again. It was genuinely re-engaging for a
  fraction of a second. It now stays put until you actually depart, so the
  announcement you hear at the gate is the one about arriving.

## 1.8.6.2 - 2026-07-29

### Fixed

- **Accepting a dispatch after an update no longer closes the game.** The
  dispatch board is kept in your career, so the board you were looking at
  before an update could still list a pickup that the update had closed.
  Pressing Enter on one of those loads shut the game down without a word. The
  board is now rebuilt from the current world the first time you open it after
  an update, so you see loads you can actually take. If you somehow reach a
  closed pickup anyway, the game says so and sends you back for a fresh board
  instead of quitting.

- **Kilometers are now used everywhere, not just out on the road.** With units
  set to metric, the driving cues spoke kilometers but several other screens
  still read miles, so the same trip was measured two different ways depending
  on where you asked. The dispatch board's job details, the distance and rate
  it quotes, the summary you hear when you take a load or deadhead to a
  pickup, the exit and hazard callouts, your remaining distance to a pickup,
  the delivery summary's credited distance, your lifetime distance in career
  stats, and the on-screen speed and trip readouts now all use the unit you
  chose. Career stats also says "Lifetime kilometers" instead of labelling
  kilometers as miles, and the pay rate reads as dollars per kilometer with
  the figure recalculated to match. Nothing changes if you play in miles.
  Contributed by otaviols ([@otaviols](https://github.com/otaviols)) in
  [PR #142](https://github.com/Orinks/Freight-Fate/pull/142).

## 1.8.6.1 - 2026-07-28

### Fixed

- **Quitting to the main menu no longer closes the game.** Choosing "Quit to
  main menu" from the pause menu brought you back to the title screen and then
  shut the game down a moment later. You now land on the title screen and stay
  there, free to continue your career or start another. Reported by smeveriss
  in [issue #132](https://github.com/Orinks/Freight-Fate/issues/132).

## 1.8.6 - 2026-07-28

### Fixed

- **Roadside fuel rescue now leaves your truck safely stopped.** After running
  dry, rescue refuels the truck but clears its previous highway motion before
  you restart, so you pull away normally instead of resuming at road speed.

### Added

- **A warning before every steep grade.** Any climb or descent of three percent
  or more that runs for at least three quarters of a mile is now called out
  before you reach it, with how steep it is, how far it runs, and -- going down
  -- what to do about it before it starts. In a manual that is picking your
  gear and setting the engine brake; in an automatic it is setting the engine
  brake and braking down to speed, which is what puts the transmission in a
  lower gear for you. Short dips stay quiet, so on a mountain route you hear
  the hills that matter and nothing else. Terse speech does not get these
  announcements at all -- press G whenever you want the grade instead. The
  advisory is there so you can decide before the hill starts: when in doubt,
  take manual control of the speed rather than leaving it to cruise.

- **G speaks the grade.** Press G while driving for the slope under the wheels,
  how much further it runs, whether the truck is holding it or losing ground --
  and the next steep grade ahead with how far off it is. It answers "why is my
  speed building" without waiting for anything to be announced.

- **Review recent spoken messages while driving.** Use the message review
  controls to move through general and critical announcements, jump to the
  first or latest message, switch categories, and copy the current message to
  the clipboard. Contributed by Day Garwood
  ([@day-garwood](https://github.com/day-garwood)) in
  [PR #122](https://github.com/Orinks/Freight-Fate/pull/122).

- **Tire sounds now react to your speed.** On supported audio systems, the tire
  hum rises and falls as you accelerate or brake. Above a crawl, soft road-seam
  thumps add texture through sound and controller vibration. Contributed by
  Swarup Baral ([@swarup-developer](https://github.com/swarup-developer)) in
  [PR #114](https://github.com/Orinks/Freight-Fate/pull/114).

- **Linux players get an AppImage.** Alongside the tarball, each release now
  ships `FreightFate-<version>-linux-x86_64.AppImage`: one file you mark
  executable and run, with no extraction step. It carries the libraries the
  Ubuntu build needs, so it also runs on Fedora, Arch, and openSUSE, and
  every build boots on Fedora before it ships. Because the AppImage itself
  is read-only, saves live in `~/.local/share/FreightFate` instead of a
  `saves` folder beside the game. In-game updates work too: the game
  downloads the new AppImage, swaps the file in place, and restarts — and
  if the AppImage sits somewhere your user account cannot write to, the
  game tells you where the downloaded update was saved instead of failing
  quietly.

- **An armed exit now counts itself down.** Once your signal is on, the
  exit calls out again at two miles, one mile, and half a mile. No more
  hearing about an exit once, five miles early, and never again until
  you have missed it. On the terse speech setting the countdown stays
  quiet, so terse drivers hear only the original announcement.

- **Delete a career's cloud backups.** Each career in the Cloud backup menu
  now has a Delete item that removes every kept backup of that career from
  your orinks.net account, after a spoken confirmation. Your saves on this
  computer are never touched, and a career that is still on this computer
  with cloud backup turned on simply starts a fresh backup the next time it
  saves. Handy if a save was backed up by mistake, such as someone else's
  career you had copied onto your computer.
- **Copy your delivery summary to the clipboard.** The delivery complete
  screen has a new item, just before Continue, that copies every settlement
  line as plain text so you can paste the whole run into a message or a
  forum post. The game confirms out loud once the text is really on the
  clipboard, and tells you if the copy did not take.
- **Share notable deliveries to your own Mastodon account.** A new Settings,
  Online option posts a short public summary, with the FreightFate hashtag,
  when a delivery earns you an achievement, a level, or a perfect streak milestone.
  Routine runs are never posted. It is off until you turn it on, and linking
  your Mastodon account happens in your browser on orinks.net using the same
  sign-in as driver setup; the Mastodon account item walks you through it
  and can check whether the link took.

- **The R key now tells you how far along you are.** The route report leads
  with your trip progress, like 53 percent there, followed by the miles left.
  It is the same figure the online drivers board shows for you, and the Tab
  status menu has a matching Progress line. Deadhead drives count too.

### Changed

- **The R key now answers just "where am I".** Two short sentences: how far
  along you are and how far is left, then the road you are on with its
  direction, the state you are in, and the city it is taking you toward. If
  you have planned a stop, the distance counts down to that stop instead of
  the destination, so R tells you how far to the place you are actually
  driving at. The nearest named place, the grade, the zone, and the next
  maneuver are gone from it, because each of those already has its own key
  or lives in the Tab status menu. U still reads what is coming up, and
  Shift R still reads the next exit.
- **Shorter driving readouts that fit a braille display.** The clock, route,
  weather, and fuel reports now put the answer in the first few words, so a
  one-line braille display shows what matters without panning. The C key
  leads with the time and whether you are on schedule instead of burying the
  verdict at the end, and on the terse speech setting it skips the calendar,
  the appointment restatement, and the stop-planning advice, all of which
  the Tab status menu still carries.
- **Speech verbosity is now a simple choice between terse and normal.** The
  chatty level never said anything normal did not; it only repeated your
  speed a little more often. If you had chatty selected, the game now uses
  normal, and everything you heard before is still there.
- **Rest stops no longer let you sleep twice for nothing.** When you are
  already fully rested at a rest stop, choosing a sleep option now warns you
  that it would only move the clock and your deadline forward, and asks you to
  press Enter again to confirm. This is the same safeguard the terminal bunk
  room already had.
- **Everything online now lives in one Online menu on the main menu.** The
  drivers board, orinks.net account setup, Profile sharing, cloud backup and
  restore, Mastodon sharing, and Discord presence moved out of Settings into
  a single Online menu, so restoring a save on a new computer or checking who
  is hauling no longer means hunting through settings categories. The board
  sits first because viewing it shares nothing about you. Choosing Online
  inside Settings still works and opens the same menu, and every toggle keeps
  the familiar Enter, Right, and Left arrow controls.
- **Walking away from a parked truck now takes you off the drivers board.**
  If your truck sits stopped with nothing changing for half an hour, you
  leave the public board just as if you had paused the game, and the board
  stops calling you a driver who is on duty. The moment anything changes,
  like rolling again or pulling into a stop, you are back on the board within
  seconds. Deadhead drives also now say how far along they are, on the board
  and in Discord, so a long empty run never looks like a parked truck.
- **Test builds now introduce themselves as development builds.** The main
  menu welcome and the update screen used to read a bare version number that
  looked like a stable release. A nightly or source build now says, for
  example, "version 1.8.6 development build", so you always know which kind
  of build is talking. Stable releases sound the same as before, and version
  numbers no longer skip when a stable release comes out.

### Fixed

- **Adaptive cruise no longer runs away down a hill.** Cruise could only ever
  add throttle, so on a downgrade it simply came off the fuel and let gravity
  carry the truck -- fifteen miles per hour or more over your set speed, with
  nothing said about it, and a speeding fine at the bottom. It now reaches for
  the engine brake when the truck starts to gain on a descent and snubs the
  service brakes when the engine brake is not enough, holding your set speed
  on grades as steep as eight percent. It hands the engine brake back when the
  hill ends, and never touches the switch when you set it yourself. Climbing,
  cruise now answers a hill as the wheels reach it instead of taking ten
  seconds to work up to full throttle. Cruise is still an assistant, not a
  driver: on a steep or long grade, when in doubt, take manual control of the
  speed. Braking hands the truck straight back to you.

- **Cruise tells you when a grade has beaten it.** If the truck is running well
  past your set speed down a hill, or has lost a lot of it climbing, cruise
  says so once, names the speed you are actually doing, and tells you to brake
  or gear down -- or just to brake, if you are driving an automatic. Before
  this it drifted in silence. It waits until the grade has genuinely won and
  stayed won, so a gear change or a stretch of nearly level road never sets it
  off. Treat it as your cue to take over: when in doubt, brake rather than
  waiting to see whether cruise recovers the speed.

- **Automatic speed control now slows in time for construction zones.** At
  highway speed, adaptive cruise begins braking when the advance warning is
  announced and reaches the work-zone limit before the speed keeper takes over,
  so the game no longer fines you while its own controls are still slowing down.

- **Automatic speed control now slows in time for heavy traffic zones.** The
  same early braking that construction zones already received now applies to
  heavy traffic zones. When the advance warning sounds, adaptive cruise begins
  easing down to the posted limit and hands off to the speed keeper at the
  zone boundary, so the transition is smooth and you enter at the right speed.
  Contributed by wleicht ([@wleicht](https://github.com/wleicht)) in
  [PR #127](https://github.com/Orinks/Freight-Fate/pull/127).

- **The rest-stop arrival cue now leaves real time to set the brake.** Trip
  pacing no longer consumes the whole stopping buffer while even a slow voice
  is still speaking. Terse speech now says "Stop now." If you set the parking
  brake when the stop announces your arrival, the truck can finish stopping
  and open the rest-stop menu; continuing past without stopping still misses
  the stop.

- **A destination exit stays ready after it is announced.** On Standard or
  Fast trip pacing, slowing down while the callout spoke could shrink the
  action window, so pressing X answered "No exit coming up." The exact
  announced exit now remains available through a human reaction window, while
  expired and already-passed exits still cannot be armed. Braking, inspection,
  and other safety warnings also finish before the signaling confirmation.

- **Short hauls no longer pay several times more per mile than long ones.**
  A guaranteed minimum meant a fifty mile hop could pay over a thousand
  dollars, four to five times the per-mile rate of a real cross country run,
  so short hops were always the best money. Short jobs still pay a premium
  per mile, the way real freight does, but it now eases down smoothly as the
  distance grows. Pay for medium and long routes is essentially unchanged.

- **The updater no longer hides a developer snapshot released the same
  day as a stable build.** On the developer snapshots channel, a stable
  release published in the small hours used to mask that morning's
  snapshot -- even when the snapshot carried newer fixes -- because the
  two were compared by date alone. Updates now compare by the actual
  publish moment, so whichever build is genuinely newest is the one
  offered.

- **Driving past a pickup or delivery entrance no longer goes silent.**
  Arriving at a facility used to announce itself once; if you rolled on --
  easy to do with cruise re-engaged -- the game said nothing more for the
  rest of the drive, and the delivery quietly went late. Now the gate
  repeats its instruction every ten seconds while you are still moving,
  cruise drops each time so the truck is never held at speed past a dead
  end, and the S key answers with the gate itself -- "At the receiver.
  Stop to dock." -- instead of a speed limit that stopped mattering when
  the route ended.

- **The road tells you the truth about the terrain.** Stretches that were
  quietly called mountain in flat country -- the East Texas piney woods, the
  Hill Country's gentle dips -- now read as the flat or rolling ground they
  really are, so the status readout no longer puts you in the mountains where
  no Texan would. The real climbs you brace for still call out as mountain
  grades, and every famous grade -- the Grapevine, Monteagle, the Siskiyous,
  the run up to the Continental Divide -- keeps its name. Thanks to nromey,
  [PR #107](https://github.com/Orinks/Freight-Fate/pull/107).

- **Starting a new career no longer talks over itself.** Naming your driver
  and picking a home region and city used to leave those screens announcing
  themselves again on the way out, each one cutting off the last, before the
  terminal menu finally spoke. The screens you have finished with now stay
  quiet, so you hear your new career's terminal and nothing else -- and the
  stray announcements no longer fill up the message review history either.
  Contributed by Day Garwood ([@day-garwood](https://github.com/day-garwood))
  in [PR #129](https://github.com/Orinks/Freight-Fate/pull/129).

## 1.8.5.1 - 2026-07-22

### Fixed

- **Each extracted copy of the game now keeps its saves strictly to itself.**
  Previously, a copy of the game could look one folder up on its first run
  and adopt the saves it found there, so keeping two versions side by side,
  for example a stable install next to a test build, could make one copy
  take over the other's careers, and deleting a save in one copy could make
  it disappear from the other. A copy of the game now only ever reads and
  writes the saves folder inside its own game folder, so you can test as
  many extracted copies as you like without them touching each other.

## 1.8.5 - 2026-07-22

### Added

- **The game can now tell you where its log file is.** Settings has a new
  Problem reports category, and Where the game log is saved reads out the full
  path and shows it in the window. The game has always kept a log of the
  session, including everything it said out loud, but nothing ever pointed you
  at it. Attaching it to a bug report shows exactly what you heard. The
  previous session is kept beside it, so restarting the game to check something
  does not lose it, and both files stay on your computer.
- **The route report now tells you where you are.** Press R, or D-pad up on a
  controller, to hear the current road and direction, state, nearest named city,
  checkpoint, or road stop, along with your progress and upcoming guidance.
- **Live weather can now leave your career calendar running.** The new Live
  weather controls calendar setting keeps today's real date when on. Turn it
  off to keep live city conditions while your career date advances at midnight
  and the seasons pass normally. Live conditions are adjusted to the career
  season so summer snow and cold-season thunderstorms do not slip through. An
  established career begins its independent calendar from today's date when
  you turn the setting off, avoiding a jump back to its old hidden date; a new
  career still begins on March 21. Thanks to TowerAlphaTheta15,
  [PR #88](https://github.com/Orinks/Freight-Fate/pull/88).
- **Map stops now open a full details view, and you can plan your next
  stop.** On the driving Map screen, pressing Enter on a stop now opens its
  details instead of repeating the line: the exit, distance, what it offers,
  parking, and an estimate of how long it will take to reach at your pace,
  including whether you would arrive before your next break, driving limit,
  or duty window. From there, plan to stop at it: approach announcements and
  the upcoming and clock readouts then call it your planned stop, so you know
  exactly when to signal for the exit. Plans can be canceled or replaced any
  time, survive saving and resuming, and clear themselves when you pull in or
  drive past. Thanks to ironcross32,
  [PR #94](https://github.com/Orinks/Freight-Fate/pull/94).
- **Keep speed assistance active across the whole job.** Pressing K now starts one automatic speed-control session: the speed keeper handles facility roads, gate queues, work zones, and congestion, then adaptive cruise takes over on the open road. If started during the deadhead, it pauses through pickup check-in and loading, survives a save there, and resumes once the loaded truck is rolling. It restores your earlier cruise target or uses the new road's limit, and switches back to the keeper for the next restricted zone. Braking outside that planned pickup, a hazard, or pressing K again cancels the whole session so it cannot restart unexpectedly. Plus and Minus adjust the remembered open-road target in either mode.

### Changed

- **The drivers board now checks in a little less often.** With online
  presence on, the game reports you every two and a half minutes instead of
  every minute, and the board waits six minutes before it calls a driver gone.
  You still appear the moment you go on duty, and going off duty, pulling
  over, or starting a new leg still reaches the board within seconds; it is
  only the quiet keep-alive that slowed down. A driver who closes the game may
  sit on the board a few minutes longer than before.
- **Career saves are now sealed files instead of plain text.** Saved careers
  use a new packed format that ordinary text editors cannot open, and every
  save is signed by your own installation. Your existing careers convert
  automatically the first time they load, and a copy of the old file is kept
  beside the new one in case you ever roll back to an older version of the
  game. A save that was changed outside the game, or copied over from another
  computer, still loads and plays normally, but the game tells you once and
  marks that career as modified; shared features may not accept a modified
  career. Thanks to nromey, [PR
  #96](https://github.com/Orinks/Freight-Fate/pull/96).

- **Moving a planned stop now asks first, and each stop only cancels its own
  plan.** A stop's details screen shows the cancel option only when that stop
  is the one you planned. Choosing "Plan to stop" while another stop is already
  planned now tells you which stop is planned and how far ahead it is, and asks
  whether to move your plan here before changing it.

- **Air pressure now bleeds down while the truck is parked with its engine
  off.** After a full night's sleep, you must start the engine and rebuild air
  before releasing the parking brake instead of waking to fully charged tanks.

- **Each truck you own now keeps its own fuel, damage, tire wear, and road
  grime.** Refueling, repairing, or dirtying one truck no longer affects the
  others, and a newly bought truck arrives with a full tank and a clean bill
  of health. Switching trucks no longer moves fuel between them. Careers from
  older versions are updated automatically the first time they load, and the
  game tells you once that the updated save can no longer be opened by older
  versions: the truck you were driving keeps its condition, and your other
  trucks start fueled and fresh. Back up your career save before opening it in
  this version. If the conversion causes a problem, include both the original
  backup and the updated save with your issue report. Thanks to ironcross32,
  [PR #91](https://github.com/Orinks/Freight-Fate/pull/91).

- **On-time deliveries now pay a real bonus.** Delivering on time used to add
  only a sliver of extra pay unless you raced in absurdly far ahead of the
  deadline, so the bonus line at settlement rarely felt like one. Pay now
  works the way real shipper scorecards do: hit the delivery window and you
  earn a flat ten percent on-time bonus every time, and arriving hours early
  pays no more than making the appointment. The settlement summary now calls
  it an on-time delivery bonus. Late and damaged deliveries still pay less,
  exactly as before.

- **You can sleep at turnpike service plazas now.** Service plazas used to
  offer fuel, food, and a short break but never a proper rest, so a tired
  driver had to push on to the next truck stop even while parked at a big
  Thruway or Turnpike plaza with overnight truck parking. Every service
  plaza's stop menu now offers sleep like truck stops and travel centers do,
  and route planning counts them as places you can end your day.

- **The driving assistance presets have been set aside for version 1.9.** Recent developer snapshots briefly offered a Driving assistance settings category with emergency braking, lane support, stop-and-go, and descent control presets. That work now ships complete with version 1.9 instead. The speed keeper stays, now under Settings, Gameplay, and your other settings are untouched.

### Fixed

- **Automatic cruise now leaves enough speed in hand for an exit.** After you
  signal for an exit, cruise aims for 40 miles per hour instead of balancing on
  the 45-mile-per-hour ramp limit. It now stays safely under that limit on a
  downhill approach instead of creeping up to 46 and missing the exit.

- **Distances and speeds no longer say "1 miles".** Anything that comes out to
  exactly one is now read as "1 mile" or "1 kilometer", on map points, stop
  distances, speed readouts, and everywhere else the game speaks a measurement.

- **The Map screen now names the cities on your route.** Its first line read
  the internal data names aloud, so a run down the east coast opened with
  "new underscore york underscore n y underscore u s" and kept going for every
  city on the route. It now says "New York to Philadelphia to Washington", the
  same way the delivery summary and the dispatch board already did.

- **Getting pulled over now judges whether you are actually stopping, not how
  far you rolled.** A loaded truck at highway speed cannot halt on a dime, and
  the old rule could flag a felony stop even when you braked correctly the whole
  way. Now, once the lights come on, the trooper watches your behavior: signal
  and brake down to a stop and you get the ordinary roadside check, and pulling
  over promptly and cleanly gives a small chance a ticket is waived to a warning.
  Keep accelerating, coast along without slowing, or ignore the lights and it
  still ends in a felony stop. You no longer have to hold the emergency brake
  the entire time; braking steadily is enough. Thanks to ironcross32,
  [PR #103](https://github.com/Orinks/Freight-Fate/pull/103).

- **Taking your planned stop's exit no longer warns that you drove past it.**
  When you signal a planned stop and brake down the exit ramp, the game used to
  announce that you had driven past it and cancelled the plan, even though you
  were stopping there. Now the warning only speaks when the stop is truly out of
  reach: if you drive past the exit without signaling, if you signal but are
  going too fast to make the ramp, or if you take the exit but never stop and
  roll on past the end of the ramp. Thanks to ironcross32,
  [PR #102](https://github.com/Orinks/Freight-Fate/pull/102).
- **Taking an exit and never stopping no longer strands you on the ramp.**
  If you took an exit but kept driving without ever coming to a stop, the game
  would quietly wait forever -- speed enforcement stayed off and, miles later,
  stopping would still open that stop's menu. Now, once you roll well past the
  end of the ramp without stopping, the game tells you that you never stopped
  and hands the highway back.
- **The trip mile marker holds while you are on an exit ramp.** The ramp is off
  the highway, so your progress along the route no longer ticks up while you
  brake down it; the highway picks back up where you left it once you rejoin.
- **Live weather no longer announces a simulated forecast while loading.**
  Pressing V before the first live observation arrives now says that live
  weather is still loading instead of describing an invented forecast. This
  also works when Live weather controls calendar is turned off. Route weather
  now names cities whose observations are loading or unavailable instead of
  silently skipping them, and weather-change announcements identify live
  observations and simulated fallback conditions. Thanks to TowerAlphaTheta15,
  [PR #99](https://github.com/Orinks/Freight-Fate/pull/99).
- **Cloud Backup works again on test builds.** Careers from a recent test
  build were being turned away with a message about the backup being
  unreadable. Nothing was wrong with those careers: the game had changed what
  it records about each truck, and the backup service was still expecting the
  older shape. Both sides now agree, and they are kept in step automatically
  so this cannot drift apart again. Released builds were never affected.
- **A career carried between computers can lose its "modified" mark.** Moving
  a save to another machine marks it as changed outside the game, because the
  new machine cannot recognise the old one's signature. When you restore that
  career from Cloud Backup and everything about it checks out, the mark is
  now cleared instead of following you forever.
- **Finishing a delivery no longer risks losing what it reported online.**
  A settlement can report the delivery, a level up, and several badges at
  once, and the game was sending them all at the same moment. They could
  crowd each other out, be sent twice, or in one case be dropped entirely.
  They now go out one after another, so your road journal records everything
  the run earned.
- **Taking a pay advance no longer makes your cloud backup look edited.** A
  pay advance is money from your next load paid early, but your career was
  only crediting the part of the settlement left after the advance came back
  out. Those advanced dollars sat in your bank with nothing in your lifetime
  earnings to account for them, so cloud backup upload could refuse the save
  and mark the driver for review. Lifetime earnings now count the whole
  settlement, and taking an advance no longer counts against you.
- **Planning a stop now plays a single confirmation sound.** Choosing "Plan to
  stop" from a stop's details no longer stacks a menu click and a confirmation
  chime back to back; you hear just the confirmation.
- **Back-to-back road alerts no longer crash the Windows event voice.** Urgent
  hazards still interrupt the current event announcement immediately, without
  making a separate redundant stop call that could crash inside SAPI.
- **Lower speed zones now give you time to brake.** When a construction zone
  or other posted limit drops, releasing the accelerator gives a loaded truck
  a fair braking window before speeding enforcement begins. Staying on the
  throttle forfeits that grace.
- **Missing the destination exit twice no longer strands the delivery.** Every
  missed attempt now loops you back far enough to hear the exit, signal, and
  slow down again instead of leaving the route stuck at zero miles remaining.
- **Automatic speed control now slows you for the destination exit.** When the
  signed delivery exit is announced, adaptive cruise eases the truck to ramp
  speed instead of switching off at highway speed. Press X to take the exit;
  automatic control releases as you enter the ramp, ready for you to brake to
  the facility stop without collecting an unwanted speeding fine.
- **Driving through a city no longer announces the same truck stop twice.**
  A city's stops were counted once for the road coming in and once for the
  road going out, so passing through called out a single Pilot or Love's
  twice, two miles apart, as though they were two places. On a Chicago to Los
  Angeles run that was eight doubled stops. Each facility is now listed once,
  keeping whichever exit number was recorded for it.
- **Signaling for one stop no longer hides that you missed a same-named
  one.** The game works out whether you are taking a stop's exit or blowing
  past it. It compared stops by name, so signaling for any Love's Travel Stop
  counted as taking the exit for the Love's you had planned, and driving past
  your real planned stop went unmentioned. It now checks the actual stop.
- **A planned stop is no longer cancelled by a different stop with the same
  name.** Plans were remembered by name only, so on a route with four Love's
  Travel Stops, driving past the first one told you that you had driven past
  your planned stop and cancelled the plan -- even when the stop you actually
  planned was three hundred miles further on. Every same-name stop also
  announced itself as your planned stop, and pulling into any of them counted
  as arriving at your plan. Your plan now follows the one stop you chose.
  Plans saved by an earlier version still load, pointing at the soonest stop
  of that name you can still reach.
- **Every stop on your route is announced now, not just the first of each
  name.** Chains repeat -- a run from New York to Miami passes four different
  Love's Travel Stops -- and the game only ever called out the first one,
  then went quiet for the rest of the trip. On that route six of its
  twenty-five stops were never mentioned at all. Each stop is now tracked by
  where it actually sits, so all of them announce as you approach.
- **The delivery run no longer warns about a 15 mile per hour limit you
  never reach.** On the way in to a receiver you were told a facility gate
  was coming with a 15 limit, then that limit never arrived, because the gate
  sits in the last half mile of the highway while your destination exit comes
  a mile or more before it -- you left the road before the sign existed.
  Delivery runs now only warn about slower zones you will actually drive
  into. Pickups and facility approach roads still drive to the gate, and
  still get the warning.
- **Signaling for the destination exit no longer says the same thing twice.**
  When the exit callout had already announced adaptive cruise easing to ramp
  speed, pressing X repeated the whole sentence. It now just confirms the
  exit.
- **Entering a slower zone no longer sounds exactly like the warning for
  it.** Both announcements said the same thing -- "facility gate ahead, speed
  limit 15" -- so on the run in to a delivery you heard the gate limit two
  miles out, found the limit had not actually changed, and had no way to tell
  that one was a heads-up and the other was the change itself. The warning
  still says how far ahead the zone is; entering it now says "Entering
  facility gate zone, speed limit 15 now," matching the "End of" call you
  already hear on the way out. Construction, heavy traffic, and destination
  approach zones all read the same way.
- **Signaling for any exit now slows the truck, not just the delivery one.**
  Pressing X told you to slow to ramp speed, but adaptive cruise kept holding
  highway speed, so a truck stop or rest area exit went by at seventy while
  automatic control did nothing. Signaling now eases cruise to ramp speed for
  every exit, and a posted limit above ramp speed no longer cancels that out.
  Pressing X again to stay on the highway hands the open-road speed straight
  back.
- **State-line announcements no longer repeat at the next major city.** When
  the GPS calls out the real state boundary, passing the next city now says
  only the city and onward route instead of claiming that you crossed the same
  state line again.
- **The game no longer crashes when it is installed in a protected folder.**
  If you put Freight Fate somewhere Windows guards, such as Program Files, the
  game could not write next to itself and would crash the moment it tried to
  save, often right as you reached a facility. Freight Fate now notices when
  its own folder is read only and keeps your saves in your personal user
  folder instead, so the game saves and plays normally wherever you install
  it. Saves that are already beside the game are still used as before. Thanks
  to ryanb96, [PR #92](https://github.com/Orinks/Freight-Fate/pull/92).
- **The engine load now follows throttle smoothly.** Engine effort remains
  audible when you accelerate or ease off, while manual releases and
  adaptive-cruise corrections blend gradually instead of making the engine
  volume jump. Automatic shifts retain a brief, gentle unload and recovery.
  Thanks to TowerAlphaTheta15,
  [PR #89](https://github.com/Orinks/Freight-Fate/pull/89).
- **Terminal weather now agrees with the live report on the road.** Time and
  weather uses the real station temperature even when live weather does not
  control the career calendar. If the first observation is still loading, the
  terminal says so instead of announcing a modeled temperature that may change
  when you start driving.
- **Interstates stop enforcing a side street's speed limit mid-route.** A
  handful of highway legs still carried a 25 to 40 mile per hour sample in
  the middle of the corridor, picked up from a nearby city street or ramp
  during the map sweep -- so the GPS would suddenly announce a 35 limit on
  the open interstate and enforcement would treat highway speed as
  speeding. Every such sample is gone (no US interstate mainline posts
  below 45), and an automatic check now keeps them from ever coming back.
  Small-town limits on US and state highways are real and unchanged. Thanks
  to nromey, [PR #86](https://github.com/Orinks/Freight-Fate/pull/86).

- **The destination exit can no longer show up a state early.** On routes
  that finish on rural highways, the game could announce the destination
  exit at the last big interchange anywhere along the way -- one delivery to
  Havre, Montana offered its "destination exit" in Wisconsin, over a
  thousand miles out, and taking it ended the trip and paid the load right
  there. The destination exit now only appears within the final miles of
  your route; where the last stretch has no signed interchange, you get the
  normal final approach to the facility instead.

- **Live weather no longer turns light haze into thick fog.** With real-world
  weather on, weather stations report haze or mist whenever they can see less
  than about seven miles, and the game treated every such report as dense fog:
  fog horns, a forty mile per hour safe speed, and near-zero visibility, often
  for an entire route on a humid summer night. The game now checks how far the
  station can actually see, and only genuinely low visibility becomes fog;
  ordinary haze plays as an overcast sky instead.
- **Highways no longer inherit city-street speed limits near their start
  and end.** On six hundred eighty routes, the posted limit spoken and
  enforced at the edges of a drive could come from a city street beside
  the highway instead of the highway itself, so an interstate might hold
  you to thirty miles per hour for miles of open road. Those stray
  readings are gone: the limit you hear at the wheel now matches the
  road you are actually on, and speeding enforcement judges you against
  that honest number. Thanks to nromey,
  [PR #82](https://github.com/Orinks/Freight-Fate/pull/82).
- **Careers from older versions now trade every cargo type at real market
  prices.** A career started before the cargo list grew to sixteen classes
  kept freight-market prices only for the original eight, so pay for the
  newer cargo types never rose or fell. Loading such a career now fills in
  the missing market prices, which also keeps cloud backups of these older
  careers in step with orinks.net.

## 1.8.3 - 2026-07-14

### Added

- **Cloud restores now get a second integrity check.** Beyond the server's
  signature, a restored profile has to pass the game's own sanity rules --
  wear between zero and one hundred, honest delivery counts, a fuel tank
  that fits in a truck. A file that fails is refused with a plainly spoken
  reason instead of being loaded, and saves from newer versions of the
  game still restore fine.

### Fixed

- **Restoring a cloud backup works again.** Every new server-verified backup
  was wrongly refused with "failed its integrity check" the moment you tried
  to restore it. The refusal was the game's mistake, not a problem with your
  save. Restores of verified backups now complete normally.
- **Cloud backup now tells you when this computer needs to reconnect.** If
  orinks.net stops accepting this computer's sign-in, the cloud backup menu
  now says so and explains the fix, instead of wrongly reporting that your
  backups could not be reached.
- **Long deliveries are easier on the game while you drive.** The destination
  exit is now worked out once and remembered instead of being recalculated
  every moment of the drive, removing a heavy background load tied to a
  reported crash on coast-to-coast routes.

### Changed

- **Playing on more than one computer no longer signs the other one out.**
  orinks.net now gives each of your computers its own token: add a computer
  from the driver setup page and your other machines keep working. If the
  game says your sign-in is no longer accepted, it now points you to the
  computer list on the setup page to get a fresh token for that computer.

## 1.8.1 - 2026-07-13

### Fixed

- **The Mountain Grade driving track sounds right again.** The daytime
  mountain music bed has been replaced with a corrected recording, normalized
  to sit at the same volume as the rest of the soundtrack.

- **Controllers are left alone when controller support is off.** With the setting disabled, the game no longer starts up the controller system or grabs a connected pad; turning support on in Settings, Gameplay activates it, and turning it back off releases the controller again.

- **Engine sound now stays present through automatic gear changes.** Shifts still ease the engine tone briefly, without the repeated volume pumping that could sound like the engine was dropping out.

- **Starting the engine no longer dips in volume.** The running engine sound now
  meets the tail of the ignition sound at the same level, then settles smoothly
  down to idle instead of briefly dropping out.

- **Manual and automatic transmissions behave reliably on steep grades.** The
  diesel governor now holds a safe low-gear road speed without quietly damaging
  the engine, and automatic trucks avoid shifts that cannot pull the hill.
- **Transmission changes now apply when you return to an active drive.** The
  game announces the new automatic or manual mode instead of waiting until the
  next trip.
- **Destination signs no longer send you down an early exit.** Navigation now
  favors the interchange nearest the destination over an earlier sign that
  happens to mention the same city.
- **Speeding fines now follow you on bobtail runs.** Empty repositioning trips
  charge accumulated speeding-strike fines and announce the cost in the arrival
  summary instead of silently letting the fines disappear.

### Changed

- **The engine no longer jumps in volume the instant an automatic shift
  finishes.** It now eases back up to full pull over a brief moment, so completed
  shifts sound smooth instead of abruptly snapping back under load.
- **Route alerts no longer repeat at one mile.** Fuel stops, rest stops, and
  other actionable exits now speak once at five miles. State lines speak once
  as you cross them.
- **The soundtrack now uses the finished music throughout the game.** Menu,
  daytime driving, and nighttime driving tracks have been replaced with their
  full-quality versions, normalized to match the existing music. Urban Roll
  also joins the menu rotation as a separate track from its driving version.
- **Automatic shifting now follows real heavy-truck strategy.** Lower gears use
  progressive shift points, the starting gear responds to load and grade,
  light trucks can skip unneeded gears, and braking selects a useful lower gear
  instead of stepping through every ratio. Engine audio now unloads between
  gears instead of sweeping upward as one continuous high-pitched tone.
- **Freight Fate checks for updates again when you leave a terminal.** Returning
  to the main menu from a city terminal or pickup facility now starts a quiet
  background check, so an available update can be installed before you finish
  the session.

### Added

- **Online sharing now tells orinks.net which game version you are running.**
  When Profile sharing or cloud backup is on, each post carries the release the
  game was built from, such as a stable version or a nightly date. It is used
  only for moderation and troubleshooting, is never shown publicly, and the
  spoken "Hear what gets shared" disclosure now mentions it.

- **The major toll turnpikes now charge realistic tolls.** Running the Kansas
  Turnpike, the Oklahoma turnpikes, the New York Thruway, the Pennsylvania and
  Ohio turnpikes, the Indiana Toll Road, the Illinois Tollway, the Mass Pike, the
  Maine and West Virginia turnpikes now adds an estimated commercial toll to the
  run -- so a toll route is a real cost to weigh against the free way around.

- **The map explodes from 249 cities to 623, coast to coast.** Since the last
  stable release the drivable network has more than doubled: 623 cities to
  pick up and deliver in, joined by about 139,000 miles of real truck routes.
  Dead zones that used to have nothing drivable for hundreds of miles -- the
  mountain West, the northern plains, the Nevada Great Basin, Appalachia, the
  Gulf coast -- now connect city to city on the real roads, town by town.
  The entries below tour the new country region by region; each nightly
  snapshot's notes carried the town-by-town detail. Special thanks to nromey
  for the mapping work behind it. And watch your fuel out there -- some of
  the new country is a long way between diesel pumps.

- **New England and the Northeast fill in.** Rutland, Keene, Lewiston, and
  Barnstable bring Vermont, New Hampshire, Maine, and Cape Cod onto the map;
  Watertown and Jamestown open New York's north country and Southern Tier;
  Williamsport, Altoona, State College, and Meadville put the Pennsylvania
  mountains on real routes; and fourteen short-haul runs stitch the corridor
  from Boston and Manchester down through Providence, Hartford, and
  Philadelphia to the Chesapeake, including the Bay Bridge run to Dover and
  Salisbury and the New York Thruway up the Hudson Valley.

- **The Mid-Atlantic and Appalachia connect through the mountains.** The whole
  Interstate 81 freight run is drivable -- Staunton, Wytheville, Marion,
  Abingdon, Bristol, and Kingsport -- with Interstate 64 east over Afton
  Mountain into Richmond. The Kentucky parkways and the coalfields open
  thirteen storied mountain runs, from Pound Gap and the Cumberland Gap to the
  New River Gorge road to Beckley, with Paducah and Owensboro on the western
  parkways; Cumberland lands on the Interstate 68 climb over the Alleghenies;
  Lynchburg anchors US-460; and Jackson and Cookeville break the long
  Interstate 40 haul clear across Tennessee into real stops.

- **The Carolinas and the Southeast coast come together.** Durham and
  Spartanburg finish Interstate 85 through the Piedmont; Petersburg, Florence,
  and Lumberton close the Interstate 95 gap, so the East Coast's busiest
  freight run finally drives city to city; eastern North Carolina adds
  Greenville, Jacksonville, New Bern, and Rocky Mount; and Myrtle Beach brings
  the Grand Strand onto coastal US-17.

- **Georgia, Alabama, and Mississippi fill in from the mountains to the
  Gulf.** Interstates 75 and 85 stop in real towns the whole way -- Dalton,
  Cartersville, Valdosta, Tifton, Cordele, Opelika, and LaGrange -- Columbus
  and Albany open the wiregrass, and Dothan, the Peanut Capital, ties three
  states together. The Delta and the Blues Highway open at Greenville,
  Clarksdale, Oxford, Tupelo, Grenada, and Hattiesburg, while Gadsden,
  Cullman, Selma, Natchez, and Panama City round out the Deep South. Louisiana
  fills in too, from Ruston and Natchitoches to Hammond and bayou-country
  Houma, with Alexandria anchoring the middle of Interstate 49.

- **Florida runs border to border.** Pensacola and Crestview break up the
  Panhandle, Ocala and Palm Coast fill the peninsula's spine, and Daytona
  Beach, Sarasota, North Port, Fort Myers, and Naples line both coasts -- with
  the run from Naples to Miami crossing the Everglades on Interstate 75's
  Alligator Alley, no services for eighty miles.

- **Arkansas and the Ozarks open up.** Fayetteville and Bentonville climb the
  real Boston Mountains, Jonesboro reaches the rice-country Delta, Harrison
  and Mountain Home carry the winding Ozark truck routes, Hot Springs crosses
  the Ouachita ridges, the Interstate 49 line finishes across the state from
  Fort Smith to Texarkana, and Pine Bluff, El Dorado, Stuttgart, and
  Russellville tie the farm and timber country into Texas, Louisiana, and
  Tennessee.

- **Texas and Oklahoma become town-by-town country.** The US-287
  Ports-to-Plains spine runs from San Antonio clear to Denver through Vernon,
  Childress, Dumas, and the Oklahoma panhandle; US-281 and US-75 open
  north-south routes beside the crowded interstates; Temple completes the
  Interstate 35 spine; Uvalde and Eagle Pass open the border country; the
  plains add Plainview, Big Spring, Brownwood, and Pampa; Longview takes its
  place on Interstate 20 toward Shreveport; and Oklahoma links up through
  Stillwater, McAlester, Muskogee, Durant, Ardmore, Bartlesville, and Ada.

- **The Great Plains ladder is complete.** Interstate 80 across Nebraska is
  now continuous past the hundredth-meridian marker, Kansas adds Lawrence,
  Emporia, Hutchinson, Great Bend, and Liberal, the Dakotas add Jamestown,
  Pierre, and Aberdeen, a Black Hills freight run links Cheyenne through
  Scottsbluff country to Rapid City, and the Missouri and Iowa heartland
  fills in from Sedalia and Saint Joseph up through Ames, Fort Dodge, and
  Mason City, with Cape Girardeau and Poplar Bluff anchoring southeast
  Missouri.

- **The Midwest and Great Lakes lattice comes together.** Twenty-nine new
  cities across five states -- from Springfield, Flint, and Kalamazoo to the
  Upper Peninsula's Marquette and Sault Ste. Marie and the Iron Range's
  Hibbing -- plus central Indiana around Indianapolis, Ohio's Zanesville,
  Mansfield, and Youngstown, Wisconsin's Fox Valley, and nineteen short runs
  lacing Detroit, Toledo, Fort Wayne, and Milwaukee together. Terre Haute and
  Effingham break the long Indianapolis-to-St. Louis drive, Dubuque anchors
  the US-20 Mississippi crossing, and every city comes with real, named
  freight facilities: haul taconite pellets from the Hibbing mine, steel out
  of Gary Works, and new Subarus from Lafayette.

- **The Rockies and the Great Basin connect end to end.** Wolf Creek Pass and
  the Million Dollar Highway open Colorado's steepest crossings, with grades
  past eleven percent over the San Juans; Durango and Farmington meet at the
  Four Corners; fifteen runs link the northern Rockies from Missoula to Miles
  City; the Silver Valley opens Interstate 90 over Lookout Pass; Rawlins
  lands on Interstate 80 across Wyoming, with Logan and Moab opening Utah;
  New Mexico adds Hobbs, Alamogordo, Roswell, Carlsbad, and Socorro; and
  Nevada's US-93 and US-50 -- the Loneliest Road in America -- cross the
  Great Basin through Ely, Austin, and Fallon.

- **Arizona and the desert Southwest fill in.** The Verde Valley, the Beeline
  Highway, and Route 66 country open Camp Verde, Sedona, Payson, Winslow, and
  Holbrook, with Prescott in the highlands; copper country climbs US-60
  through Globe and the Salt River Canyon to Show Low; the border adds
  Nogales, Sierra Vista, and Douglas; the Colorado River runs from Lake
  Havasu City down to Yuma; and US-89 reaches Page and Lake Powell across
  the Navajo Nation.

- **California and the Pacific Northwest round out the coast.** San Luis
  Obispo and Santa Barbara complete the US-101 coast run, Modesto and Merced
  fill Highway 99 through the Central Valley, the Redwood Highway reaches
  Eureka, the eastern Sierra opens the long US-395 run beneath Mount
  Whitney, the Cajon Pass climb connects Riverside to Victorville, and
  fourteen Cascade-pass runs -- Stevens, White, and Santiam, real grades with
  brake checks -- tie Seattle, Tacoma, and Salem to the Columbia Basin, with
  The Dalles seating the Columbia Gorge.

- **Drive the Overseas Highway to Key West.** Key West joins the map at the very
  end of the road, reached from Miami down US-1 through the Florida Keys -- Key
  Largo, Islamorada, Marathon, Big Pine Key -- across the Seven Mile Bridge, all the
  way to the southernmost point in the continental United States.

- **You can now cross the Chesapeake Bay Bridge-Tunnel.** Cape Charles joins the
  map on Virginia's Eastern Shore, and the run north from Norfolk takes you out
  across the seventeen-mile Bridge-Tunnel -- diving into two tunnels beneath the
  shipping channels, past Sea Gull Island, out to where no land is visible in any
  direction, and up the Delmarva peninsula to Salisbury. It carries a hefty truck
  toll, because of course it does.
- **Cloud backups now prove they were accepted by orinks.net before restore.**
  orinks.net validates and signs each private revision, and Freight Fate verifies
  that signature before touching a local career. Public Profile sharing stays
  separate: detailed career statistics come only from an accepted backup and
  are omitted when no verified revision exists.

- **Optional Profile sharing stays quiet during driving.** With Profile sharing on,
  Freight Fate can queue automatic road-journal posts,
  achievements, and updates for the public driver profile. Detailed career
  statistics come only from the latest private Cloud Backup accepted by
  orinks.net. Offline posting retries in the background and never adds a spoken
  interruption while driving.

- **Exits now come straight from real-world maps -- with the correct exit names
  and numbers.** On the Interstates, your stops and your destination exit are
  announced with their actual exit number and name and the places they point to --
  "Exit 33, Yemassee," "toward Beaufort and Port Royal," "Durham" -- taken directly
  from real map data, so you always know the right exit to take. This now covers
  the whole Interstate network.

- **Routes now carry the real posted speed limits.** Instead of estimating a
  limit from the road type, every leg on the map now carries the actual posted
  speed limits from map data (interstates, US highways, and more), so your truck
  runs the real limit on the road it is driving. Rural roads without published
  limits still fall back to a sensible estimate.

- **Truck-stop names read cleanly now.** Spoken stop names across the map no
  longer include bare initials like "T A" or leftover store numbers.

- **Every run now names the real towns and country you pass.** Those are
  checkpoints -- the actual places along a route, spoken as you reach them -- and
  the map went from about 550 of them to over 2,500. Instead of empty miles, a
  haul now names the towns you pass and the state lines along the way, all from
  real geography, and real elevation data means the grades are felt and not
  smoothed flat. Thanks to nromey.

- **Over 1,700 truck stops are now named along your routes.** Real travel centers, truck
  stops, and rest areas -- Love's, Pilot, Flying J, TA, Petro, and independents
  -- each pinned to its real location, so every route now has at least one place
  to fuel or park, and even the emptiest rural stretches point you to a real
  diesel pump you can pull a rig into. For now these are just named on the map;
  making them do something -- rest, showers, repairs, and buffs -- comes in a
  later update. Thanks to nromey.

- **Some hauls now offer more than one way to drive them.** Where two real truck
  routes reach the same place, the map keeps both, so a run can offer a choice --
  a faster interstate or a shorter back road -- instead of a single fixed path.
  Is it winter, and you'd rather take a southern route than a mountainous
  northern one? We've got you covered. Thanks to nromey.

- **See who else is hauling right now with the new drivers board.** A new
  Drivers online item in the main menu reads the live board from orinks.net:
  each driver's name, what they are doing, their route and cargo, and how
  fresh the report is. If you want to appear there yourself, set up sharing
  under Settings, Online. Drivers are Orinks accounts now: the game opens
  the orinks.net setup page where you sign in, pick your driver name and
  whether the public board lists you at all, and copy a Driver ID and a
  one-time posting token; back in the game you paste each from the
  clipboard and choose Connect and save. Nothing is ever shared before
  that, the game speaks exactly what gets shared, and only broad in-game
  activity goes out, like "Driving: Chicago to Dallas, steel coils", never
  your save files, real name, or location. You leave the board within
  minutes of going off duty or turning sharing off.

- **Your careers can now back up to the cloud.** Turn on Back up saves to
  your Orinks account under Settings, Online, and after each game save your
  career quietly uploads to your own orinks.net account -- so a dead hard
  drive no longer means a dead career, and you can pick up the same driver
  on another computer. It uses the same one-time sign-in as the drivers
  board, nothing extra to set up, and backups are private to your account:
  they never appear on the drivers board or anywhere public. The new
  Restore a cloud backup menu reads your backups aloud, newest first, and
  brings one onto this computer -- keeping the save it replaces beside it
  as a fallback. Played the same career on two computers? The game notices
  and asks which copy should win instead of silently overwriting either.
  Cloud backup is off until you turn it on.

- **The map now has real time zones, and your clock changes as you cross
  them.** Drive west out of Tennessee on I-40 and you will hear "Crossing
  into Central Time. It is now 2:15 PM." With terse speech on, it is just
  "Central Time." Every spoken clock -- rest stops, sleep, city arrivals, the driving
  status screens -- now reads the local time where your truck is, and the
  clock readouts name the zone, like "2:15 PM Central Time". Delivery
  deadlines are also quoted the way a real receiver would say them: in the
  destination's local time, like "deliver by 6 PM Central Time tomorrow", on
  the dispatch job details and in the driving deadline readouts. Hours of
  service, deadlines, and pay are untouched; only what the wall clock says
  changes. Boundaries follow the real lines, including split states like
  Tennessee, Kentucky, Indiana, the Florida panhandle, and far west Texas.

### Changed

- **Pausing now takes you off the live drivers board.** The pause menu used to
  keep you listed as "Paused"; now it counts as going off duty, so the public
  board only shows drivers who are actively hauling. A quick pause and resume
  will not bounce you off the board, and Discord presence still shows
  "Paused" to your friends while the menu is open.

- **Dispatches and route planning now always name the state with each
  city.** A job reads as "to McCall, Idaho" even when no other McCall
  exists, so an unfamiliar town still tells you roughly where you are
  headed. And each route option now says which cities it passes through
  right in the option itself -- "through Boise, Idaho, then McCall" --
  instead of only in the F1 help, so you can weigh routes the same way
  the end-of-trip summary describes them. Thanks to a player suggestion.

- **Automatic direction changes can now be simple or deliberate.** Simple is the
  casual default: keep holding the control after the truck stops to change
  between forward and reverse. Deliberate keeps the safer two-step behavior from
  the previous snapshot: stop, release the control, then press it again. Choose
  the style you prefer under Settings, Gameplay. Manual shifting is unchanged.

- **Online settings are now gathered in one place.** The Discord presence
  toggle moved from Settings, Gameplay to Settings, Online, alongside the
  drivers board and the new cloud backup options. And before you have set
  up your Orinks sign-in, the first Online item now says "Driver profile:
  not set up" -- setting it up is one step that unlocks both the drivers
  board and cloud backup.

- **The horn sounds like a real horn held down.** Instead of restarting the
  same short honk over and over, holding the horn now sustains one steady blast
  for as long as you press it, and when you let go the horn rings out and fades
  the way a real one does rather than cutting off abruptly. Pressing the horn
  again while it is still sounding no longer layers a second horn on top.

- **Abandoning a job now asks you to confirm.** Choosing Abandon job from the
  pause menu opens a Yes or No prompt that starts on No, so you have to arrow
  down to Yes to actually give up the load and pay the penalty. Choosing No
  takes you straight back to the pause menu with the job intact.
- **Cities that share a name now always say their state.** With two Jacksons,
  two Portlands, and three Springfields on the map, dispatch offers, route
  planning, GPS announcements, and delivery summaries now say "Jackson,
  Mississippi" or "Jackson, Michigan" wherever the bare name would be
  ambiguous. Cities with a unique name keep their short spoken form, and a few
  places that used to stutter their state twice, like "toward Jackson,
  Michigan, Michigan", now say it once. Existing careers and saved trips carry
  over unchanged.

- **Job details always tell you the state.** Not sure where Baton Rouge is?
  Open a job's detail view from the dispatch board and the origin and
  destination lines now always include the state, like "in Baton Rouge,
  Louisiana", even for cities with a unique name. Board offers stay short.

### Added

- **The Great Lakes split into three regions that each feel like
  themselves.** The Upper Midwest covers Minnesota, Wisconsin, and Michigan's
  Upper Peninsula; the Great Lakes keeps the lower-lakes industrial belt from
  Chicago through Detroit to Buffalo; and the new Corn Belt takes interior
  Illinois, Indiana, and southern Ohio. Each has its own weather, fuel
  prices, freight market flavor, and road hazards, so a winter run out of
  Duluth no longer sounds like a summer haul into Cincinnati.

### Fixed

- **A few routes now name the right highway.** On the runs from Denver to Salt
  Lake City, Santa Rosa to Stockton, and Clarksville to Huntsville, the game
  announced a highway the route never actually takes; it now names the road you
  are really driving.
- **The truck now warns you while the engine is over-revving, instead of
  surprising you with damage at delivery.** Holding the engine at redline --
  easiest to do by backing up fast for a long stretch -- quietly ground the
  truck down, and the first you heard of it was a big damage number on the
  end screen. Now a warning sounds and the game tells you the engine is
  taking damage and the current total, repeating while it goes on, so you
  can ease off and slow down before the repair bill grows. Thanks to a
  player report.

- **Online setup now tells you when orinks.net refuses your pasted
  credentials, instead of blaming your connection.** If the server answered
  but did not accept the Driver ID and token, the game said "could not reach
  orinks.net, check your connection," sending you off to troubleshoot a
  network that was fine. It now says the credentials were not accepted and
  asks you to re-copy them from the setup page. The token paste item also
  checks that the pasted text looks like a real driver token -- they always
  start with the letters F F D and an underscore -- and says so when it does
  not, catching a wrong copy before anything is sent. Thanks to a player
  report.

- **Music keeps playing while the game is paused.** If a music track ended
  while you sat on the pause menu -- or in settings, help, or any other menu
  over a drive -- the music went silent until you resumed driving. The next
  track now starts on its own, so a long pause no longer means a quiet cab.

- **Pasting your Driver ID and token now works on Mac.** Setting up the
  online drivers board no longer crashes the game, or silently does
  nothing in the downloadable app, when you paste your Driver ID or
  driver token from the clipboard on a Mac. Thanks to a player report.

- **No more "brake now" ambushes on the way to a pickup.** The short
  facility access road you deadhead down to reach a shipper no longer
  springs road hazards or emergency-braking events; those belong on the
  open road, not on a two-minute crawl at yard speeds. Thanks to a player
  report.

- **Reconnecting a controller no longer crashes the game or leaves it
  half-working.** Unplugging a pad -- or having it change to another device and
  come back over Bluetooth -- could crash the game outright, or bring the
  controller back with the triggers and bumpers dead so you could steer but not
  brake. The game now recovers from the hot-plug instead of crashing, and
  fully re-acquires the controller when it returns -- even when the system hands
  it back under a new identity -- so braking, throttle, and the bumpers work
  again right away.

- **Controller toggle actions no longer fire twice.** On some controllers --
  notably the Xbox Elite -- setting or releasing the parking brake, or starting
  or shutting down the engine, could trigger twice from a single press, so the
  action immediately undid itself. Each button press now counts once, even when
  the controller reports itself to the system more than once.

- **Construction zones no longer stack or chain together.** Slow zones were
  placed independently, so a construction zone could land inside another
  one, or two could start back to back with no open road between. Zones now
  keep at least eight miles apart, so "end of construction" always means
  open road ahead. Thanks to a player report.

- **Metric mode now covers the whole weather report.** With units set to
  kilometers, pressing V mid-drive still read the temperature in Fahrenheit
  and low visibility in miles. Temperatures now speak in Celsius and
  visibility in kilometers everywhere weather is described: the V report,
  weather-change announcements while driving, trip resume summaries, and
  the terminal weather check. Thanks to a player report.

- **The engine sound now stops when you shut down to sleep.** Going to sleep
  at a rest stop, motel, or on the shoulder shuts the engine down, but the
  engine sound kept playing over the night and after you woke, as if the
  truck were still idling with the engine off. The shutdown is now heard
  when it happens, and the idle goes quiet with it. Thanks to Darren Duff
  for the report.

- **Using the accelerator to brake in reverse no longer speeds you up.** In an
  automatic, pressing the accelerator while rolling backward is meant to slow
  and stop the truck, but at higher reverse speeds it could push you faster
  instead. It now brakes reliably all the way to a stop.

- **Adaptive cruise no longer revs the engine when you press the clutch to
  shift.** With a manual gearbox, holding the clutch under cruise control used
  to send the engine screaming toward the redline. Now cruise eases off the
  moment the clutch goes in, the engine settles back toward idle, and the speed
  is picked back up smoothly once you let the clutch out.

- **The engine no longer re-cranks when you pick a trip back up.** Resuming a
  saved haul with the engine already running -- or coming back from a menu
  mid-drive -- used to replay the ignition sound as if you had just turned the
  key. Now the running engine simply fades back in, and the starter is heard
  only when you actually start the engine yourself. When you do start it, the
  crank now blends smoothly into the running engine instead of being drowned
  out the instant it catches.

- **Your truck no longer idles all night while you sleep.** Bedding down for
  the night -- at a rest stop, in the sleeper berth, in a cramped lot, or on
  the shoulder -- now shuts the engine down first, and you will hear "You
  shut down the engine" as you turn in. When you head back to the road,
  start the engine as usual. Thanks to Bartholomue.

- **Updating the game on Mac now works.** Downloading an update used to end
  with "the download failed" and nothing installed, leaving Mac players to
  fetch each new version by hand. The updater now understands the Mac app
  bundle: it swaps in the new app after the game closes and reopens it for
  you, just like on Windows and Linux. Your saves are untouched. Thanks to
  vlad-a-c.

- **Asking for job details on Back to terminal no longer crashes the game.**
  On the dispatch board, pressing F1 while on the Back to terminal entry used
  to crash; it now simply reads the entry back, like any other menu item.
  Thanks to ironcross32.

- **Resuming a trip no longer repeats a stop it already called out.** When you
  continued a saved run, the game could re-announce a truck stop or rest area
  just ahead that it had already told you about before you saved. It now
  remembers what it said and stays quiet. Thanks to nromey.

## 1.8.0 - 2026-07-05

### Added

- **Report a problem straight from the main menu.** A new Report a problem
  option, just above Quit, opens the Freight Fate bug report page on GitHub
  in your web browser and tells you where to find your game log: the file
  game.log in the logs folder next to the game. The game now also keeps the
  previous run's log as game.prev.log, so if the game crashes, the evidence
  survives restarting it to file the report. Crashes inside the game's audio
  and video engines, which used to vanish without a trace, are now written
  into the log as well.

- **Game controllers are now supported, alongside the keyboard.** Plug in an
  Xbox, PlayStation, or other compatible controller and drive by feel: the right
  and left triggers are the gas and brake, the left stick steers, the left bumper
  is the clutch, and the A and X buttons shift up and down. Menus map to the
  D-pad, the A button confirms, the B button goes back, and the Back button reads
  controller help. The first controller is picked up automatically, hot-plugging
  and unplugging are detected mid-game (unplugging pauses the drive), and spoken
  prompts name controller buttons when you are on a pad and keys when you are on
  the keyboard. Turn it off under Settings, Gameplay, Controller. The keyboard
  always stays active. Thanks to ironcross32.

- **Set the parking brake to let time pass while you wait.** Pressing your
  parking brake while stopped now means deliberate waiting: the clock runs at
  double your trip pacing -- weather blows through, daylight comes, and dock
  time passes without the game ever dropping to real time. Pressing it again
  to leave returns to normal pacing instantly. Only your own brake press arms
  the fast-forward; the brake the game sets for you at trip start or after a
  rest stop never does, so pre-trip setup stays cheap. Each pacing setting
  keeps its relative feel while waiting: relaxed 20 times, standard 40,
  fast 80.

- **The Pacific Northwest fills in with eight new cities.** Tacoma, Everett,
  Olympia, Bellingham, and Yakima in Washington and Medford, Roseburg, and
  Pendleton in Oregon join the map with truck-routed corridors, real named
  ports, mills, and freight facilities, and real truck stops along the way.
  The region finally has short local runs -- Seattle to Tacoma is a
  34-mile hop instead of nothing closer than Portland -- and the empty I-84
  corridor gets its first stop at Pendleton. Thanks to liamerven.

- **Appalachia, the Heartland, and the Southern Plains grow by eighteen
  cities.** Appalachia becomes a real Valley-and-Ridge region: Asheville,
  Johnson City, Beckley, Harrisonburg, Winchester, and Hagerstown line the
  I-81, I-77, and I-40 mountain corridors, Roanoke gains its rail yard and
  distribution work, and the western reaches of Virginia, North Carolina, and
  Maryland now count as Appalachian country. The Heartland adds Sioux City,
  Grand Island, North Platte, Columbia, Joplin, and Rolla along I-70, I-29,
  I-80, and I-44; the Southern Plains add Salina, Dodge City, Garden City,
  Enid, Lawton, and San Angelo with their grain, beef, and oilfield freight.
  Every new city carries real named facilities and every corridor has named
  truck stops. Thanks to liamerven.

### Fixed

- **Switching screen readers no longer leaves the game silent.** The game now
  notices within a few seconds when your screen reader closes or changes, for
  example going from NVDA to Narrator and back to NVDA, and reconnects its
  speech to whichever voice is running, telling you which one it picked.
  While Narrator is running, the game keeps its own Windows voice so that
  moving through menus still cuts speech off crisply; Narrator itself only
  carries the game's speech as a last resort when no other voice on the
  machine works. This also
  works if you start the game before your screen reader: speech simply
  begins once the screen reader is up. Your speech rate, voice, and separate
  event voice settings carry over to the reconnected voice automatically.

- **Release archives no longer ship the build machine's log.** The packaging
  smoke check writes a log inside the build folder; it is now stripped
  alongside saves before archiving, so a fresh download starts with an empty
  logs folder instead of a confusing leftover run.
- **Save migration now explains itself.** When the game folds an old save
  folder into the active one on first run, it writes what moved from where
  to the game log and leaves a small saves-moved.txt breadcrumb at the old
  location, so an unexpectedly familiar career is traceable instead of
  haunted.
- **Spoken help now teaches the W and Q gear keys everywhere.** The engine
  start walkthrough, the transmission setting, and the manual-transmission
  page of How to play still told manual drivers to shift with the number
  row; they now describe holding the clutch and pressing W to shift up and
  Q to shift down, matching how the truck actually shifts. The left and
  right arrows also now toggle the Haptics setting like every other
  gameplay setting row, instead of doing nothing there.
- **Getting up to highway speed no longer costs an hour of game time.** Truck
  physics runs in real time so shifting and braking stay playable, but the
  clock billed every real second at full trip pacing -- so the couple of real
  minutes a loaded rig needs to work through the gears cost most of a game
  hour, burning daylight, deadline, and duty clock. Clock compression now
  ramps with road speed: near real time while stopped or maneuvering, your
  full pacing setting once at cruise. Distance, fuel, fatigue, and the hours
  of service ledger all follow the same effective rate, so the simulation
  stays consistent -- acceleration now costs about five game minutes instead
  of forty-five.
- **The dispatch board no longer offers trivially short hauls.** Because each
  city stands for a whole freight area, a job to a neighbor under 25 miles was a
  pointless across-town hop; the board now skips those destinations and fills
  from real routes instead.
- **The dispatch hours warning now respects a fresh clock.** Sleeping off your
  hours before visiting the dispatch board no longer leaves every long haul
  flagged with "may not fit your duty clock." The warning compared your time
  until the next HOS limit against the route's full legal plan -- including the
  overnight sleeps every multi-day run needs anyway -- so it fired even right
  after a reset. It now only warns when hours already spent this shift would
  force an extra rest that fresh hours would avoid, and the board note says
  sleeping first will clear it.
- **Trucks into New York now take the George Washington Bridge, not the Holland
  Tunnel.** New York freight now routes to the Hunts Point market in the Bronx
  over the GWB on I-95 -- the Hudson crossing a full-height rig can legally use
  -- instead of the height-restricted Holland Tunnel that I-78 feeds into. Trips
  from New Jersey and Pennsylvania have realistic mileage and exit cues as a
  result.
- **Truck speed limits are now capped in Oregon and Idaho too.** Posted limits
  on those states' fastest roads are held to the legal truck maximum (65 in
  Oregon, 70 in Idaho), matching the existing handling for California and other
  truck-restricted states.
- **Control now stops speech in menus too, not just while driving.** Left or
  Right Control already silenced the driving event voice; it now also stops the
  current speech in every menu and in the how-to-play reader, so a long readout
  -- job details, cargo loading, a full help page -- can be cut short with the
  same key everywhere.
- **Dispatch, garage, and driving tools feel clearer.** F1 on a dispatch job now opens a
  reviewable job-detail view with line-by-line facts, long-haul pay has a stronger
  floor, drive-start speech is shorter in terse mode, the horn loops while held,
  truck and upgrade wording is clearer, and the garage can service tire wear and
  wash road grime.
- **Reverse now has its own backing cue.** Shifting into reverse with the engine
  running now starts a backing loop through the main audio backend, and automatic
  reverse selection still gets a spoken confirmation. Thanks to ashleygrobler04
  for the original reverse-loop PR.
- **Lane drift now cues direction before the rumble strip.** When lane drift is
  enabled, a short beep now plays from the side you drift toward, and a dedicated
  centered-lane chime confirms when you are back in the lane.
- **Hazard clears are easier to hear, and speech backs off faster.** Passing a
  road hazard now plays a short achievement-like confirmation sound, and urgent
  events plus driving warnings clear stale spoken messages so old alerts do not
  keep piling up. The brake-now hazard warning cue was also remade as a short,
  louder alert.
- **First-rig menu music refreshed.** The first-owned-truck menu bed now uses
  a cleaner, longer copy and plays for its full length before the menu rotation
  advances.
- **Driving realism polish.** Metric speed warnings,
  speeding strikes, trooper stops, cruise messages, and the speed-limit key now
  use the selected units consistently. Missed destination exits reroute you via
  a safe turnaround instead of telling you to reverse down the highway, and
  recovery no longer loops gate-speed tickets. Dispatch warns when your current
  hours are too short for a load, including when every listed job is risky.
  Bobtail repositioning now counts as off-duty personal conveyance, dispatch
  board facility names are less repetitive, impossible short delivery summaries
  are floored to a practical road time, and automatic shift audio no longer
  flares at full throttle during gear changes.
- **Engine brake and throttle no longer fight each other.** The engine brake now
  refuses to switch on while you are accelerating, and pressing the accelerator
  turns it back off so the truck can make power normally.
- **Destination exits keep the route status honest.** Taking a delivery exit now
  clears the remaining route miles before the dock menu opens, and the GPS no
  longer repeats the destination exit with a second generic interchange cue.
- **Real posted speed limits win near cities.** City approaches still use a
  slower fallback when the route has no posted speed-limit sample, but real
  baked `maxspeed` data is no longer capped just because the route is near a
  city.
- **Truck speed limits now respect state caps.** Baked route speed-limit data
  now applies lower truck maximums in states that cap commercial trucks below
  the general posted limit, and reversed routes read the correct limit profile.
- **Stops no longer announce speculative truck parking.** If a stop's parking
  is confirmed, that still gets spoken; otherwise speculative parking wording
  is dropped from route cues so the game just announces the stop.
- **Adaptive cruise starts slowing before big speed-limit drops.** When the
  posted limit ahead falls sharply, adaptive cruise now looks far enough ahead
  to begin braking before the lower-limit point instead of waiting until the
  truck is already in the slower stretch. Pressing Space while cruise is on now
  also includes the cruise set speed in the speed readout.
- **Adaptive cruise no longer gets you fined while braking for a lower limit.**
  When the posted limit drops sharply, cruise now gets a clean chance to slow
  the truck instead of letting the speeding timer fire while it is already
  braking down.
- **Route status explains road grade clearly.** Pressing R now reports the
  current grade as a percent and uphill, downhill, or level instead of saying
  the vague phrase "Grade level."
- **Delivery windows match the slower, real route model.** New dispatch
  deadlines now use the route's posted-limit profile, city approaches, facility
  gates, HOS breaks, sleep, and practical slack instead of a flat mileage
  average. Older active trips that were saved under the faster estimate get a
  one-time fair deadline floor when they resume, so a source update does not
  make an in-progress load suddenly late.
- **Metric weather readouts use metric safe speed.** Pressing V with metric
  units enabled now reports the weather safe speed in kilometers per hour.
- **No more "dot dot" at the end of menu items.** A menu or list item that was
  already a full sentence (like a settlement summary line) got a second period
  appended before its "N of M" position, which a screen reader voiced as "dot
  dot". The readout now adds a period only when the text does not already end
  in one.
- **You can always find somewhere to sleep.** A sleep option is now reachable
  at any time, so the hours-of-service clock can never strand you with nowhere
  legal to stop. Stopped on the open road with no route stop nearby, you can
  pull over and sleep on the shoulder (poor rest, possible parking ticket);
  the wording escalates when an HOS limit is closing in with no reachable stop.
  Any break/fuel stop you reach -- even one with no sleeper facility -- now
  offers an emergency sleep in the lot: a legal 10-hour reset with poor, cramped
  rest. The "no stop visible" warning also names the shoulder-sleep out, so it
  is a plan rather than a panic. (Proper sleeper stops still give the best,
  fully-rested 10-hour sleep.)
- **The automatic no longer gears up while you brake.** Braking from speed could
  trigger an upshift because the box only watched engine RPM; it now holds the
  gear for engine braking and downshifts cleanly as you slow to a stop.
- **"Air pressure ready" no longer repeats back to back.** The parking-brake
  release threshold sat exactly at the compressor cut-in pressure, so the ready
  state flickered every 100-125 psi cycle and re-announced. The cue now fires
  once, only while the parking brake is actually set (its whole purpose is
  "you can release it now"), and only re-arms after a genuine low-air depletion.
- **Snapshot players move to stable when it catches up.** On the preview
  snapshot channel, the game now offers the stable release whenever it is as
  new as -- or newer than -- the latest nightly, so once those changes ship in
  a stable build you converge back onto stable instead of being left on an
  equivalent nightly.
- **The low-air alarm now sounds on a cold start.** Starting the engine for
  the first time with the air tanks low used to stay silent; the warning now
  plays as soon as the engine is running with pressure below the threshold,
  so you know to wait for the compressor before releasing the brakes. Thanks
  to hannes16.
- **Erie and Evansville moved to their right regions.** Erie sits on the Lake
  Erie shore between Buffalo and Cleveland, so it is now Great Lakes country
  rather than Appalachia; Evansville, down on Indiana's Ohio River border, is
  now the Mid-South rather than the Great Lakes. Spoken region names, weather
  flavor, and regional hazards on runs through both cities now match the
  geography. Thanks to liamerven.

### Fixed
- **Exit warnings now arrive early enough to act on.** At highway speed on
  standard or fast pacing, the destination exit callout used to fire so close
  that by the time it finished speaking the ramp was gone. The warning
  distance now grows with your speed and pacing, so you always get roughly
  the same amount of real listening and braking time, and the exit can be
  armed as soon as you hear the callout.
- **Exit announcements no longer say the same name twice.** Messages like
  "missed exit 5B for exit 5B" and "Signaling for the exit for the warehouse,
  destination exit for the warehouse" now speak each exit and facility name
  exactly once. Distances also read naturally: "in 1 mile" instead of
  "in 1 miles".

### Changed
- **Career stats at the terminal is now a browsable list.** Instead of one
  long spoken paragraph, arrow through your level, reputation, deliveries,
  lifetime miles, and earnings one line at a time; Enter repeats a line. The
  screen also gains your rest status: whether you are fully rested or how
  tired you are, plus your hours of service at a glance.
- **Sleeping at the terminal no longer swallows 10 hours by accident.** If
  your hours of service are fresh and you are not tired, choosing Sleep 10
  hours now warns that sleeping would only move the clock forward, and asks
  you to press Enter again to sleep anyway. So an extra press on the sleep
  option can never quietly cost you a rested clock.
- **New installs now start at relaxed trip pacing.** Fresh installs default to
  the relaxed pace, which gives you the most real time to hear and react to
  spoken warnings like exits and hazards. Existing players keep whatever
  pacing they already chose, and standard and fast are still one setting away
  under Settings, Gameplay, Trip pacing.
- **All music now plays at the same volume.** Six tracks, including the main
  menu themes, Open Road, Night Haul, and Small Hours, were much louder than
  the rest of the soundtrack. They have been brought down to match, so the
  music volume slider now behaves the same no matter which track is playing,
  and the menu no longer greets you louder than the drive that follows.
- **Real-world weather now refreshes three times as often.** With the real
  weather source turned on, the game checks the live conditions for your
  destination every five minutes instead of every fifteen, so fog rolling in,
  a storm firing up, or skies clearing reach your drive much sooner. If your
  connection drops, the game holds the last known weather for the same half
  hour as before switching to simulated conditions.
- **Downloaded builds no longer expose the game's world data files.** The
  world now ships built into the game program itself, so there is no data
  folder to browse or accidentally edit next to the game. Nothing changes
  about how the game plays, and source checkouts keep their editable data
  files.
- **Downloaded builds now ship their sounds as a single packed file.** The
  browsable sounds folder is gone from the download; all sound effects and
  music travel in one pack file the game reads directly. Every sound plays
  exactly as before, the sound and music credits ship as a readable file
  next to the game, and source checkouts keep their editable sound files.
- **During a manual drive.** hold down the clutch (shift) then press W to shift up gears, and q to shift down gears .
- **Hours-of-service rules are more realistic.** Realistic mode now tracks the
  11-hour driving limit, 14-hour duty window, 30-minute break requirement,
  60/70-hour weekly limits, roadside inspections, and legal sleeper-berth split
  rest. Rest menus now make the choice explicit: short breaks, poor emergency
  sleep, full sleeper sleep, or sleeper split planning where the stop supports
  it.
- **Menus can read just the option, not its place.** A new Speech setting,
  "Menu position announcements," turns off the "N of 10" position spoken after
  each menu option, so menus read only the option itself. On by default.
- **In-game help and manual now cover the new systems.** The how-to-play pages,
  the F1 driving help, and the user manual were brought in line: the calendar
  and seasons, weather that bites (traction loss, drag, visibility), the
  always-available shoulder and lot sleep, cruise that declines low-speed local
  roads, and -- newly documented anywhere -- state-trooper speeding pull-overs
  (signal with X) and real changing posted limits.
- **The calendar reads as a real date, in more places.** The career clock now
  speaks an actual date that advances as time passes -- "March 21," then "April
  1," and so on (a new career starts March 21) -- instead of only a day number.
  It is announced on the C clock readout, the Tab status menu, and the on-screen
  status, not just at the terminal, with the season alongside it. With live
  weather on, the date and season follow the real-world calendar.
- **Weather you have to drive to, not just hear.** Three conditions that used to
  be flavor now bite. High wind and storms add real aerodynamic drag, so they
  cost top speed and fuel. Driving well over the conditions-safe speed on a
  slick road risks a traction-loss incident -- hydroplaning in rain, sliding on
  snow -- so the safe-speed readout finally has teeth. And low visibility (fog,
  heavy rain) shortens how much warning you get before a hazard, so you have to
  actually slow down to see and react in time.
- **Speed-limit changes now say why.** A changing posted limit is announced as
  "Speed limit reduced to X" or "raised to X" instead of a bare number, and an
  urban drop names the city ("reduced to 55 approaching Boston"), so a mid-drive
  change is no longer a mystery.
- **No cruise on low-speed local roads.** Adaptive cruise will not engage on a
  facility access road, gate, construction zone, or heavy-traffic stretch -- the
  low-speed local roads a real driver takes manually -- and says so if you try.
- **Relaxed mode now feels emptier on the road.** Relaxed hours-of-service mode
  already made random hazards and trooper patrols rarer; it now also thins
  ambient traffic and the odds of a random roadside log check, so a relaxed run
  centers on driver responsibility -- hours, fuel, fatigue -- with fewer
  interruptions. Fixed checkpoints (weigh stations) and construction-zone
  enforcement are unchanged: a real violation still catches you. Realistic mode
  is untouched.
- **Live weather now reports the real temperature.** With live weather on, the
  cab speaks the actual temperature from the nearest National Weather Service
  station instead of the modeled seasonal estimate, so the degrees match the
  conditions it is already pulling in. The seasonal climate model stays the
  fallback whenever live data is unavailable or a station omits its reading.
- **Dial your cruise speed with Plus and Minus.** Once adaptive cruise is set,
  Plus and Minus raise and lower the target by 5 -- the accelerate and coast
  buttons on a real truck -- so you can engage as soon as you are rolling and
  dial the speed up to where you want it instead of having to reach it manually
  first. The truck accelerates up to a higher target on its own, and the posted
  limit cap still applies, so a higher set speed never makes it speed.
- **Adaptive cruise now respects the posted limit.** Cruise eases off to hold a
  with-traffic pace (about 5 over the posted limit) instead of carrying your set
  speed straight through an urban drop or a lower-limit stretch -- so it keeps
  you moving naturally without driving you into speeding strikes, tickets, and
  trooper stops. It still follows slower traffic and widens its gap in bad
  weather, and a short cue says when it eases off for a lower limit (the
  "Speed limit X" sign cue still names the number).
- **The air-brake system has real sounds now.** When pressure builds, you hear
  an air-dryer purge as the compressor cuts out instead of a generic beep, and
  low-air and spring-brake warnings sound a proper low-air buzzer. The spoken
  cues are unchanged, so nothing is lost if you rely on them.
- **Speeding now costs you out loud, the moment it happens.** When a speeding
  strike is recorded, the cab calls out the running fine ("Speeding strike. The
  limit is 65. Speeding fines now total 160 dollars, due at delivery.") instead
  of the cost landing silently on your settlement. Judged against the corridor's
  real posted limit, with the usual ~10 mph leeway before a strike lands.
- **Posted speed limits can now come from real map data.** Where a corridor
  carries an OpenStreetMap `maxspeed` tag, the game uses that real posted limit
  instead of the highway/region approximation -- and falls back to the
  approximation only on stretches OSM has not tagged. Limits are baked at build
  time (truck-specific `maxspeed:hgv` preferred where present); the spoken
  limit-change cue still calls out posted-limit changes as you drive.
- **The lane-drift rumble is now directional.** When you wander toward a lane
  edge, the rumble strip plays from that side -- drift right and you hear it on
  the right -- so the ear it lands in tells you which way to steer back.
- **Safety announcements no longer get buried, and you get more warning.** Zone
  entries, construction and traffic warnings, and checkpoints now preempt
  ambient chatter (weather, tolls, state lines) on the event voice instead of
  queuing behind it -- so a "construction ahead" never arrives after you have
  already entered the zone. Zone warnings also lead by real time now, not a
  flat distance: the heads-up scales with your speed and pacing, so 70 mph at
  high time compression gets a usefully earlier callout instead of a couple of
  seconds.

### Added
- **Repeat the market watch on the dispatch board.** The board speaks which
  freight is tight or loose when you open it; pressing Tab now repeats just that
  market watch, so you can re-check it without leaving and reopening the board.
- **State troopers can pull you over for speeding.** Routes now have patrol
  windows -- hotter on busy interstates, in construction, and in dense regions,
  cooler out on the plains, with a night DUI bump. Speed badly inside one and a
  trooper lights you up: signal with X, brake to a stop on the shoulder, and sit
  through a license and logbook check that ends in an on-the-spot ticket (paid
  immediately, escalating with each stop) or a warning if it's a first, marginal
  stop or your reputation is strong. Run from the stop and it's logged as
  evasion -- a heavier fine and a serious reputation hit. Speeding the patrols
  don't catch still accrues the quieter safety-record cost at settlement.
  Relaxed mode keeps patrols light.
- **Consult the controls without leaving a drive.** The pause menu now has a
  "Controls and help" entry that opens the how-to-play reference straight to the
  driving keys -- page through it, read it line by line, then escape back to the
  road. The keys list also now includes S, A, and U.
- **HTML player manual.** Portable builds now ship `USER_MANUAL.html` alongside
  the Markdown one: the same manual rendered as a clean, accessible web page
  (semantic headings and real tables) you can open in any browser.
- **Three new on-demand driving keys.** **S** reads the posted speed limit where
  you are -- the zone if any, and how far over you are -- so you no longer have
  to dig into the status menu. **A** repeats the last route announcement, for
  the one you missed before you could react. **U** reads what is coming up:
  imposed speed limits, stops, and exits ahead, so a zone or gate never blindsides
  you. All three are listed in F1 help and the manual.
- **Drowsiness has real consequences now.** Push past severe fatigue and you
  start to nod off: a rumble-strip jolt and a warning give you a moment to steer
  or brake and stay awake. Catch it and you carry on; miss it and you drift onto
  the shoulder for damage and lost speed. Keep driving exhausted and the nods
  come faster and harder until a third miss forces you off the road. Sleep is no
  longer optional once you are running on empty -- and in relaxed mode, where
  hazards are rare, managing fatigue becomes the heart of the drive.
- **Posted speed limits that change by corridor.** The flat 70 everywhere is
  gone. The limit now comes from the highway and region -- rural Interstates run
  70 in the Midwest and East, 75-80 across the West, US highways and state
  routes slower -- and drops to an urban limit on the city stretches. Crossing
  into a new limit is spoken like a sign ("Speed limit 75"), the limit restores
  correctly when you leave a construction zone, and speeding is judged against
  the corridor you are actually on.
- **Seasons and temperature.** Your career now moves through the year, and the
  weather follows. A regional temperature model (a seasonal swing plus a
  day-night swing, warmer in the desert and Gulf, colder across the northern
  tier) decides whether precipitation falls as rain or snow and whether storms
  can brew, so snow is a cold-season risk, thunderstorms a warm-season one, and
  a Great Lakes January night freezes while a Gulf Coast one does not. Because
  hazards are weather-gated, snow squalls and ice now show up in winter and
  hail in summer, on their own. The terminal time-and-weather readout names the
  season, and weather reports include the temperature in your units. With live
  weather turned on, the season follows the real-world calendar so it matches
  the live conditions you are pulling in; otherwise it follows your career clock.
- **Cargo weight now changes how the truck drives.** Gross weight is the
  tractor-and-trailer tare plus the actual payload, so a heavy load pulls away
  gently, lugs harder on grades, and burns more fuel, while a light load or an
  empty pickup deadhead is noticeably brisker. Heavier freight is now a real
  trade-off, not just a number on the dispatch board. The driving status screen
  shows gross tonnage alongside the cargo weight.
- **Load-sensitive braking.** The foundation brakes have a fixed force ceiling
  sized for the rated gross, so a load heavier than the rated weight is
  brake-capacity limited: it decelerates more gently, takes longer to stop, and
  heats and fades the brakes sooner. Loads at or below the rated gross brake
  exactly as before. Overloading a run now bites on a downgrade or a panic stop.
- **Grounded, context-aware road hazards.** Hazards now only happen where and
  when they plausibly would. Standing water and hydroplaning need wet weather;
  snow squalls, bridge-deck ice, and black ice on shaded grades need snow;
  dense-fog brake-lights need fog; crosswind shoves and dust storms need high
  wind in open country; rockfall and runaway-truck hazards need mountain
  terrain. Deer and elk are biased to dawn, dusk, and night, with regional
  species. The implausible ones are gone -- no more farm equipment merging
  onto the interstate or a dust devil on a clear, calm day.

## 1.7.0 - 2026-06-26

### Added

- **Relaxed mode now actually relaxes the road.** In relaxed hours-of-service
  mode, random road hazards are much rarer, so the drive centers on driver
  responsibility -- hours, fueling, repairs, and fatigue -- instead of constant
  emergency braking. Realistic mode is unchanged. The Settings help for Hours
  of service spells out the difference.
- **Dispatcher pay advances (no more soft lock).** A broke driver who can no
  longer afford fuel can now draw a cash advance against the next load -- from
  the terminal hub or any in-trip rest stop -- and it is repaid automatically
  out of the next delivery settlement. The advance is offered only while cash
  is low and is capped, so it stays a recovery line rather than free money. A
  negative balance is no longer a dead end.
- **Discord Rich Presence (optional).** When Discord is running, your profile
  can show broad game activity -- the main menu, the terminal, driving a route,
  resting, or delivering -- with high-level route and cargo context. Only
  general game status is shared, never save files or personal details. It is on
  by default and can be switched off in Settings → Gameplay → Discord presence,
  and the game starts, plays, and exits cleanly whether or not Discord is open.
- **Bigger freight map.** The playable network grows to 194 cities and
  437 routed legs, adding many more regional hubs, shorter connector lanes,
  and route-backed freight choices across the country.
- **Highway exit callouts.** Interstate drives now announce upcoming
  interchanges the way a real sign reads them -- "In 2 miles, exit 7 for
  US-1 North toward Trenton and New York" -- with the exit number, the route
  you would take, and its control cities. Exit data is sourced from
  OpenStreetMap and snapped onto each corridor.
- **Grounded exits and onramps.** When a rest stop sits at a real interchange,
  the exit prompt and ramp now name its number ("Signaling for exit 113, the
  Petro Stopping Centers"; "You take exit 113"). Each run also opens with an
  onramp callout -- "Merge onto I-65 South toward Indianapolis" -- and highway
  changes name the new road and direction.
- **Optional lane drift.** Gameplay settings now include off, light, and
  realistic drift so players can add a gentle steering task, rumble-strip
  warnings, and off-road consequences without making the default drive harder.
- **Packaged changelog and manual.** Portable builds now include
  `CHANGELOG.md` and `USER_MANUAL.md` in the game folder so release notes and
  the player manual are available offline.
- **Player manual.** A new public manual now gathers install, career,
  dispatch, driving, saves, settings, accessibility, and troubleshooting
  guidance in one linkable place.
- **Music remakes.** The main menu theme, Open Road, and Night Haul now use
  new Suno remakes while keeping their familiar Freight Fate music slots.
- **Music rotation.** All menu and driving music beds now play once and rotate
  through their active pool instead of looping.
- **Quieter music by default.** New settings now start background music at half
  volume so speech and driving cues stay comfortably in front.
- **Expanded music beds.** Freight Fate now includes longer menu, facility,
  daytime driving, and nighttime driving music. Menus and freight facility
  screens use a career-aware pool, and active drives use stable day/night
  pools that rotate without reshuffling abruptly while you are on the road.
- **Truck cab sound refresh.** Engine start, idle, shutdown, horn, gear shift,
  parking-brake set and release, and highway road ambience now use an updated
  in-cab vehicle sound set, thanks to [Darren Duff](https://darrenduff.com/).
  The start cue is trimmed so the idle loop takes over cleanly.
- **Night driving ambience.** Night drives now play a new recorded in-cab
  night ambience loop.
- **More music.** New night beds: a menu theme for careers loaded after dark,
  and a late-night driving piece.
- **New drowsiness yawn.** The fatigue yawn cue uses a fresh sound, thanks to
  [Darren Duff](https://darrenduff.com/).
- **New achievement system.** Careers now track achievements across a range
  of categories, with a spoken main-menu viewer and a chime when you unlock
  one. Existing careers carry over. Note: a career saved on a preview snapshot
  may not load on an older stable release.

### Changed

- **Safety announcements no longer get buried, and you get more warning.** Zone
  entries, construction and traffic warnings, and checkpoints now preempt
  ambient chatter (weather, tolls, state lines) on the event voice instead of
  queuing behind it -- so a "construction ahead" never arrives after you have
  already entered the zone. Zone warnings also lead by real time now, not a
  flat distance: the heads-up scales with your speed and pacing, so 70 mph at
  high time compression gets a usefully earlier callout instead of a couple of
  seconds.
- **Truck-legal routing everywhere.** Every corridor's geometry, elevation, and
  grades are now derived from OpenRouteService's heavy-goods (driving-hgv)
  profile. The original cross-country legs (NY-Boston, the I-70/I-80 spine, and
  about a hundred others) were still on the car-routing engine; they now match
  the rest of the network with truck-legal paths and real truck elevation. Their
  grade profiles are finer too -- the old car-engine legs had a single grade per
  corridor, where the truck engine breaks each into the real run of climbs and
  descents -- though no leg's overall terrain rating changed. Distances were
  already accurate, so pay and deadlines are unchanged. The refreshed route
  data is included in the game, so driving still works fully offline.
- **Real weather now uses the National Weather Service.** Optional live weather
  switched from Open-Meteo to the U.S. National Weather Service API
  (api.weather.gov). It is still free and needs no API key, reads each city's
  nearest official station for current conditions, and keeps the same seamless
  fallback to simulated weather when offline.

### Fixed

- **The truck can no longer roll away while you rest.** Opening a truck
  stop or rest-stop menu now sets the parking brake and cuts the throttle, the
  same way pulling into a pickup or delivery does. Before, a rig that crept in
  just under the stop threshold (or idled in gear) could keep drifting down the
  road while the driver slept. Returning to the road now reminds you to release
  the parking brake with P.
- **No more implausible interstate hazards.** The random road-hazard pool no
  longer surfaces things that can't happen on a limited-access interstate, or
  that are really weather rather than a brake-now event: farm equipment merging
  onto the highway, sudden downpours and thunderstorm downpours, and hail. Real
  weather still arrives through the weather system, and genuine road hazards --
  standing water, whiteout squalls, debris, stopped traffic, crosswinds,
  wildlife, rockfall -- stay.
- **Phantom state-line crossings.** Highways that run alongside a river border
  -- I-84 down the Columbia Gorge most of all -- no longer announce a flurry of
  back-and-forth state crossings the driver never makes. I-84 hugs the Oregon
  bank of the Columbia (the Oregon/Washington line) for about 100 miles without
  ever crossing it, but corridor sampling against a simplified boundary used to
  flicker across the line and fabricate the crossings; a Portland run could call
  the Oregon/Washington line four times before the real Oregon/Idaho border. The
  baked route data is now scrubbed of these round trips (71 across 20 legs,
  including I-5, I-24, I-29, I-79, and I-90 corridors), and the enrichment
  pipeline guards against re-introducing them.
- **Salem connected to Portland.** Salem now has a direct I-5 leg to Portland
  (about 46 miles). Before, Salem was wired to Seattle and Tri-Cities but not to
  Portland right next door, so a Salem-to-Portland run routed 176 miles the
  wrong way -- south to Eugene and back north through Salem -- and long hauls out
  of Salem were labeled I-84 from the start even though they leave on I-5. The
  redundant direct Salem-Seattle and Salem-Tri-Cities legs are gone; those trips
  now compose through Portland with correct per-highway signage (I-5 out of
  Salem, I-84 only once you reach the Columbia).
- **Real weather warm-up.** With real weather enabled, a drive now starts in
  neutral clear conditions and waits for live data, instead of briefly showing a
  simulated condition that the live data immediately replaced. That warm-up
  flicker could also wrongly unlock a weather achievement (for example, a rain
  achievement for weather you never drove in). Simulated weather still runs as
  the offline fallback when live data cannot be reached.
- **macOS save location.** Saves now live in
  `~/Library/Application Support/FreightFate` instead of beside the app in
  Applications, matching macOS conventions. Existing saves found next to or
  inside the app bundle are moved into the new location on first launch.
- **Empty reposition arrivals.** Finishing a bobtail (empty reposition) run no
  longer crashes on arrival. The "Repositioned" summary screen now opens and
  reads its relocation summary instead of failing as you reach the new city.
- **Speech setting previews.** Adjusting speech rate, pitch, volume, or voice
  now previews with the voice being changed, so a selected SAPI or OneCore
  voice speaks its own new setting.
- **Truck idling.** The diesel now stays running through pickup check-in,
  loading, route planning, loaded departure, and active-drive resume instead
  of forcing a fresh engine start.
- **Destination exits.** Delivery routes now require taking the real signed
  exit for the destination when one is listed, instead of completing just by
  driving to the end of the highway corridor.
- **Destination exit callouts.** Destination exits now announce the signed exit
  and toward cities before the ramp, then tell you to press X; adaptive cruise
  cancellation includes that exit guidance.
- **OneCore pitch.** Windows OneCore speech now keeps its native default pitch
  unless the player changes the pitch setting.
- **Metric driving status.** Metric mode now reports driving status,
  speed limits, traffic, pickup distance, and legal-stop distance in metric
  units instead of mixing in mph or miles.
- **Metric traffic speed.** The traffic-queue speed shown in the route line now
  reads in kilometers per hour in metric mode, instead of staying in miles per
  hour next to the already-metric distance.
- **Metric navigation cues.** Spoken GPS guidance -- onramp, continue, stop,
  exit, traffic, and construction-zone callouts -- and the Map status screen now
  give distances in kilometers in metric mode instead of miles, matching the
  rest of the metric driving readouts.
- **Metric speed limits.** Construction and traffic zone callouts now speak the
  posted speed limit as a metric value in metric mode instead of the mph number.
- **Live unit switching.** Switching between miles and kilometers mid-drive now
  updates spoken navigation guidance right away, including the distances already
  laid out along the current route.
- **Packaged update checks.** The updater now recognizes standalone packaged
  folders more reliably, so switching to preview snapshots does not leave the
  update screen confused about how the game was installed.
- **Quieter exit guidance.** Ordinary highway exits now stay available in the
  route screen without being announced during the drive unless they lead to a
  stop you can actually take.
- **Route key priority.** Pressing R now keeps the next actionable route detail
  first, while Shift+R reports the next listed highway exit.
- **State-line timing.** State crossing previews now speak about 10 miles out
  instead of 2 miles out, giving the preview and crossing announcements more
  room at highway speed.
- **Upper gear spacing.** Automatic shifting now holds 9th gear longer before
  entering overdrive 10th, so the truck no longer reaches top gear around
  city-road speeds.
- **Portable save folders.** Snapshot builds now move nearby duplicate
  portable save folders into the active `FreightFate\saves` folder instead of
  leaving players with two likely save locations after extraction or updates.
- **Clearer help.** F1 help now focuses on what the selected item does for the
  player instead of repeating menu controls, and garage upgrade help explains
  how each upgrade changes the truck.
- **Updater works in packaged builds again.** Packaged copies are now detected
  correctly, restoring update checks, install, and crash logging.
- **Facility approach speed cues.** Pickup deadheads now use lower-speed
  facility access roads, deliveries slow through a final receiver approach,
  and the last gate prompts are shorter so stopping instructions land faster.
- **Facility gate ambience.** Pickup and destination facility screens now use a
  quieter loading-dock ambience that stays away from truck-idle rumble.
- **Preview sound volume.** The refreshed truck, road, weather, route, and
  facility sounds now play at full source strength before the player's volume
  settings are applied, so lowering and raising sound effects behaves more
  predictably.
- **Achievement speech routing.** Achievement unlocks now speak through the
  screen reader voice instead of the separate driving-event voice, so players
  who miss or interrupt an unlock can still review it later from the
  Achievements menu.
- **Facility and settings audio fixes.** Terminal and yard screens now use
  the new facility-gate ambience, delivery completion no longer buries the
  dock and settlement cues under a generic menu sound, and volume settings
  persist into the next game session.
- **Status and settings navigation.** The driving status panel now opens into
  clear route, driver, truck, and map-style status screens, and Settings uses
  category menus for gameplay, audio, speech, weather, and updates.
- **Menu navigation polish.** Delivery completion now presents settlement,
  route, truck, and career details in one continuous list, while Settings keeps
  its category menus for easier browsing.

## 1.6.0 - 2026-06-19

### Added
- **Contextual route and weather audio.** Driving now uses in-cab rain, snow,
  wind, fog horn, and thunder cues plus short route-event sounds for hazards,
  construction zones, inspections, tolls, state crossings, rest stops, weigh
  stations, facility gates, and docking. The road bed is back in the mix so
  the cab does not feel dry while moving. The experimental vehicle engine sound
  redesign is still being tuned and is not part of this release.
- **Route rest, toll, and settlement realism.** Route planning now uses richer
  truck-stop data, handles shoulder-sleep edge cases more cleanly, and accounts
  for toll and settlement details more explicitly.
- **Air-brake startup and reservoir behavior.** Trucks now build air
  pressure before departure, keep spring brakes engaged until the system is
  ready, and model service and emergency reservoir pressure while driving so
  braking feels more like a heavy truck without stranding new careers.
- **Driving status menu.** Pressing Tab while driving now opens a spoken status
  menu with load, trip, truck, route, and route-stop details from the road.
- **Better route stops.** Dispatch-supported freight now
  relies on curated truck-relevant route stops only: placeholder midpoint
  POIs no longer count as real route support, long-haul lanes must include
  explicit fuel-capable stops, and route summaries/GPS stop details
  now give clearer parking certainty.
- **Auto-updater.** The packaged game now checks GitHub for new releases
  when you reach the main menu. When one is found, a fully spoken prompt
  offers "Download and restart" (downloads the update, swaps it in, and
  relaunches the game for you), "What's new" (reads the update's changelog
  line by line), "Remind me later", and "Skip this version". A new
  Settings entry, "Update channel", picks between stable releases and preview
  builds, and "Check for updates" checks immediately.
- **Real pickup and loading flow.** Job offers now name the origin
  facility as an actual stop on the trip instead of flavor text. After
  accepting a load, you check in at the listed facility, load only while
  stopped, then plan the loaded trip to the destination.
- **Company terminal dispatch flow.** New careers and continued drives now
  frame the service-area hub as a company terminal or yard instead of a
  generic city spawn. Dispatches start with a local deadhead move from the
  terminal to the shipper, and delivery settlement parks the truck at the
  destination area's terminal or yard for the next assignment.
- **Destination facility docking.** Deliveries no longer settle just
  because the truck reached the destination city. The game now warns at
  speed, keeps you in control until a full stop, opens a facility menu
  with a dock/yard cue, and requires "Dock and deliver" before payment.
  "Check paperwork" previews facility, cargo, payout, deadline, and damage
  details without completing the load.
- **Real freight facilities on job boards.** Cities now offer freight from
  classified locations such as terminals, warehouses, ports, intermodal
  yards, air cargo areas, manufacturing plants, food terminals, industrial
  parks, retail distribution hubs, and bulk facilities. Cargo is filtered
  by plausible facility type.
- **Highway exits.** Rest stops now sit at proper exits. They are
  announced a few miles out ("Press X to take the exit for it"); X
  signals for the exit (and X again cancels), you slow to 45 or less for
  the ramp — any faster and you blow past it — then half a mile of ramp
  and brake to a stop, and the rest stop menu opens by itself. The ramp
  is off the highway: hazards and speeding checks pause while you are on
  it. Pressing T while stopped on the highway at a stop still works.
- **Explicit highway stop positions.** Route data now stores named highway
  amenities with explicit mile positions instead of spreading rest stops
  evenly across a leg. The first curated offline stop set uses sourced rest
  areas and travel centers, keeping the game playable without live map lookups.
- **Reverse gear and missed-stop recovery.** Trucks can now back up.
  Automatic players can hold Down while stopped to reverse slowly, then
  touch Up to brake and return to forward drive; manual players can press
  the clutch and Backspace for reverse. If you miss a rest stop, slow
  down, back up carefully, stop, and press T.
- **Cruise control.** K sets cruise at your current speed, matching common
  highway driving expectations, and holds it with a slow throttle governor
  through grades.
  K again, any braking, the emergency brake, a stall, or taking an exit
  cancels it — and a hazard warning hands control straight back to you.
  Space reports speed.
- **Region-flavored road hazards.** The hazard pool now mixes nationwide
  staples with local flavor for the region you are driving through: dust
  devils and tumbleweeds in the Southwest, deer and farm equipment in
  the Midwest, rockfall in the Rockies, elk and standing water in the
  Pacific Northwest, and more.
- **Separate voice for driving events.** Road events — hazard warnings,
  collisions, weather changes, rest stop and city announcements, HOS and
  fatigue warnings, speeding, inspections, speed callouts — now speak
  through a dedicated Windows SAPI voice, so a screen reader reading menus
  or echoing keystrokes can no longer cut off a "Brake now!" mid-sentence.
  A new Settings entry, "Driving event voice" (default: separate SAPI
  voice), switches events back to the screen reader. When SAPI is
  unavailable, or is already the main voice, events fall back to the main
  channel automatically.
- **Emergency brake.** Hold B while driving for the hardest possible stop:
  instant full application plus the spring brakes (about 1.6 times the
  service brakes, still subject to weather grip and brake fade), with a
  loud air-dump cue. Use it for hazards and for rest stops you would
  otherwise overshoot. Mentioned in the tutorial, F1 controls, and the
  manual.
- **Roadside mechanic.** The pause menu while driving now offers "Call a
  roadside mechanic" once damage is past 25 percent: a field patch back
  down to 25 percent damage for a 500-dollar callout plus 110 dollars per
  percent repaired (a steep premium over the garage). The repair takes 90
  in-game minutes against your deadline and duty window, and the bill is
  due even if it puts you in debt — never a dead end.
- **Time and weather in the city.** A new city menu entry speaks the
  clock, the time of day, the day of your career, and current conditions
  in town (live Open-Meteo data when real weather is enabled).
- **Sleep in any city.** A new city menu entry, "Sleep 10 hours", gives a
  full night at your terminal: fresh hours of service, zero fatigue, and
  the clock advances 10 hours. Previously a spent duty window followed
  you into the city with no remedy except driving — illegally — to the
  first rest stop of the next run.

### Fixed
- **Pickup facility sounds.** Pickup gates and loading now use the new facility
  ambience and dock cues instead of the older generic menu notification sounds.
- **Preview builds stay in sync with release notes.** Preview builds now pick up
  player-facing changes that have already been prepared for the next stable
  release, so their "What's new" text no longer falls behind.
- **Save resume keeps traffic zones stable.** Continuing a saved drive now
  seeds trip weather from the saved trip seed too, so traffic and
  construction-zone layouts regenerate consistently across operating
  systems.
- **Updater connections on macOS and Linux.** The packaged game's Python
  runtime looks for certificate authorities at paths that only exist on
  the build machine, so on macOS and Linux every secure connection — the
  update check, the download, and the real-weather fetch (which silently
  fell back to simulated weather) — could fail certificate verification.
  The game now ships its own certificate bundle (certifi) and uses it
  alongside the system store on every connection.
- **Update errors now say what went wrong.** "Could not reach the update
  server" covered everything from a dropped connection to a blocked DNS
  lookup. The check and download now speak the actual reason — "The
  secure connection could not be verified", "The server answered with
  error 403", "The server address could not be found", and so on. The
  packaged game also writes a session log to logs/game.log, so a
  player can share the full error when reporting a problem.
- **Hazard warnings were unbeatable at highway speed.** The reaction
  window was a fixed 3 to 4.5 seconds, but a full-service stop from 65
  to the safe 25 miles per hour takes about 5 — even the emergency brake
  could not make it once you add the time to hear the warning. The
  deadline is now the braking time the truck actually needs from its
  current speed (on the current surface and grade) plus the rolled
  reaction window, so hitting the brakes promptly always succeeds — in
  rain or snow you get the longer stop those surfaces really take.
  Drowsiness now eats into the reaction part only instead of the whole
  window, since a tired driver reacts late but the truck stops no
  slower. Warnings also lead with "Brake now!" instead of ending with
  it, so you can be on the brakes before the sentence finishes.
- **Collision stall soft-lock.** A hard collision could stop the truck
  while the automatic transmission was still in a high gear; the engine
  then stalled the instant it was restarted, every time, stranding the
  player (it read as "too damaged to start", since the same crashes also
  max out damage). The automatic now returns to first gear whenever the
  truck is stopped in a higher gear, and restarting after a stall recovers
  cleanly.
- Pressing E with a bone-dry tank no longer dead-ends on "the engine will
  not start": the out-of-fuel roadside rescue now triggers from there too.
- **The C key's arrival estimate was a constant.** It always assumed
  55 miles per hour, so it never responded to how fast you were actually
  driving. It now tracks your current speed once you are meaningfully
  rolling (and says so), falling back to a typical highway pace while
  parked, and names the basis either way.
- **Abandoning a job lost the hours you drove.** The world clock snapped
  back to the departure time while hours of service and fatigue kept the
  accrued wear, and the freight market did not advance. The time spent on
  the failed run now counts.
- **Trip pacing now applies mid-trip.** Changing "Trip pacing" from the
  pause menu's settings was silently ignored until the next delivery; the
  active trip now picks it up immediately.
- **Unsafe engine shutdown blocked.** Pressing E at road speed no longer
  shuts off the engine. The game now gives spoken feedback and requires a
  safe low-speed stop before shutdown.
- **Delivery at speed blocked.** Arriving at the destination at highway
  speed no longer completes the job. Settlement now requires the full
  stopped facility docking flow.
- **Tampered saves are quarantined.** Career saves now carry an integrity
  signature. Old unsigned saves migrate forward, but edited or corrupted
  saves are moved aside instead of being loaded as valid career data.
- **Implausible route detours filtered.** Route options now reject obvious
  short-haul detours that send drivers far out of the way, while still
  allowing meaningful alternate long-haul routes.
- **State progress announcements improved.** Trips now announce state
  crossings and nearby cities along the route, not only the destination
  state.
- **Construction-zone warnings are actionable again.** Construction zones
  now give a spoken GPS warning about 2 miles before the slowdown begins,
  and troopers will not clock construction-zone speeding until you have
  had about a mile inside the zone to react. Speech-first players can
  slow down in time again instead of being fined on the same update that
  first announces the zone.

### Changed
- **How-to-play driving guidance.** The main-menu guidance for driving controls
  is shorter and more direct.
- **Early career progression and pay.** Low-level jobs now pay enough to
  make early progress feel worthwhile after operating costs, and higher
  levels unlock clearer differences in range, cargo, endorsements, and
  long-haul opportunities.
- **Truck acceleration and shifting.** Loaded trucks reach safe highway
  speeds more plausibly, top gear behaves more like mild overdrive, and
  automatic shift cues are easier to hear without adding air-brake sounds
  to gear changes.
- **Freight market terminology.** Player-facing market wording now uses
  trucking language: tight, loose, and steady, replacing the old generic
  market labels.
- **Real terrain on real highways.** A geography audit corrected 20 of
  the 106 legs. The famous grades are now mountains: Monteagle on I-24
  (Nashville-Atlanta), the Cumberland Plateau on I-40
  (Knoxville-Nashville), the Pennsylvania Turnpike's Allegheny crossings
  (Philadelphia-Pittsburgh and Baltimore-Pittsburgh), and US-95's Idaho
  canyon country (Spokane-Boise). Rolling country stopped pretending to
  be flat: I-70's Missouri River hills, the Flint Hills and Arbuckles on
  I-35, Tennessee's Highland Rim on I-40, Wisconsin's driftless coulees
  on I-94, the Carolinas' piedmont, Connecticut on I-95, and the desert
  passes on I-10 (San Gorgonio, Texas Canyon) among others. Genuinely
  flat country — the high plains, the Gulf coast, Florida, and the Illinois
  prairie — stays flat.
- **Realistic deadlines.** Dispatch can no longer ask for the
  impossible. Deadlines are now built from the hours a law-abiding
  trucker actually needs — driving at an achievable 55 mph average, plus
  the 30-minute break every 8 driving hours and a 10-hour sleep for
  every 11-hour shift the distance demands — with 20 to 50 percent
  shipper slack and a flat hour for fuel on top. San Antonio to Dallas
  now quotes a workable 7-to-8-hour window instead of a sprint.
- **State trooper groundwork.** The next law-enforcement milestone is outlined:
  patrol intensity by corridor, CB chatter warnings, pull-overs, immediate
  fines, and an enforcement setting.
- **Portable saves.** Profiles and settings now live in a `saves` folder
  inside the game's own directory (next to the executable in release
  builds) instead of the per-user data directory. Existing saves are migrated
  over automatically on first launch; the originals are left in place.

## 1.5.0 — 2026-06-10

"On the Clock": hours of service, fatigue, day and night, and overnight
parking. Everything runs on the in-game clock (`settings.time_scale`
compresses it as usual), never wall time.

### Added
- **Hours of service.** Simplified FMCSA rules per shift: 11 hours of
  driving inside a 14-hour duty window, a 30-minute break required after
  8 hours at the wheel, and a 10-hour sleep to reset. Spoken warnings at
  2 hours, 1 hour, and 30 minutes before each limit (each fires once),
  and at the violation itself. The C key now reports the clock time and
  HOS status alongside the deadline; Tab includes it at normal and chatty
  verbosity. Driving past a limit risks roadside inspections with
  escalating fines (200 to 2,000 dollars) and reputation hits — never a
  game over. A new Settings entry, "Hours of service", picks realistic,
  relaxed (every limit 25 percent longer), or off.
- **Rest stop menu.** Pressing T at a rest stop now opens a fully spoken
  menu: refuel (as before), take a 30-minute break, or sleep 10 hours.
  Resting advances the in-game clock, so the delivery deadline keeps
  counting — that is the tension.
- **Fatigue.** Builds with continuous driving (faster at night), eases
  with breaks, and clears with sleep. A drowsy driver yawns, drifts onto
  the rumble strip, hears spoken drowsiness warnings, and reacts late to
  hazards (the reaction window shrinks up to 40 percent). Deterministic
  under the trip seed.
- **Day/night cycle.** Dawn, day, dusk, and night derived from the career
  clock (new careers still start at 6 AM). Nights bring sparser traffic
  zones, a higher hazard chance, a cricket-and-air night ambience layer,
  and the previously unused "Night Haul" track while driving. V, Tab, and
  C mention the time of day, and arrivals speak the clock ("It is 11 PM").
- **Overnight truck parking.** Arriving at a rest stop between 8 PM and
  4 AM, the lot may be full — more likely as the evening wears on,
  deterministic per trip seed. A spoken menu offers driving on to the next
  stop or shoulder parking: a full HOS reset but poor rest (fatigue floor
  of 30) and a 15 percent chance of a 150-dollar ticket.
- New manual page "Hours and rest"; F1 help on all new menus.
- New procedural sounds: `ambient/night` and `driver/yawn`
  (regenerate with `tools/generate_audio.py`).

### Fixed
- **Speech backend selection.** Prism's registry ranks NVDA above every
  other backend whether or not NVDA is running, so on machines without it
  the game bound to a dead NVDA connection and stayed silent. The backend
  choice is now validated against actual runtime support and falls down
  the priority list (JAWS, One Core, SAPI, Speech Dispatcher, ...) to the
  best backend that can really speak. A new
  `FREIGHT_FATE_SPEECH_BACKEND=<name>` environment variable forces a
  specific backend for troubleshooting.

### Compatibility
- Save format version is now 3. Old v2 profiles and pre-1.5 mid-trip
  snapshots load cleanly, defaulting to a fresh HOS clock and a rested
  driver.

## 1.4.0 — 2026-06-10

### Added
- **Home terminal picker.** A new career now asks where it should begin:
  after name entry, a fully spoken menu lists every city labeled by region
  ("Atlanta, the South"), with the usual arrow, Home/End, and first-letter
  navigation plus F1 help. Defaults to Chicago; Escape returns to name
  entry with the typed name intact. Existing profiles are untouched.
- **A real interstate network.** The map grows from 21 cities and 27 legs
  to 59 cities and 106 legs along real corridors (I-95, I-90, I-80, I-75,
  I-70, I-65, I-40, I-35, I-10, I-5, and more), so neighboring cities sit
  roughly 100-250 miles apart. Every new city has real coordinates for the
  live-weather feature, a weather region, and freight locations with
  regional identity: produce out of the Central Valley, autos around
  Detroit, electronics at the container ports, grain and livestock across
  the plains, machinery in the rust belt. Boston and Seattle are no longer
  dead ends; no city has fewer than two highways.
- **Career-arc job generation.** Rookie boards (levels 1-2) offer short
  regional work: mostly single-leg hops to neighboring cities, capped
  around 280-340 miles, with destinations weighted toward nearby cities so
  freight follows plausible lanes. The distance cap grows with level and
  cross-country hauls (600+ miles) unlock around level 4-5 as a dedicated
  long-haul slot on the board. A flat hookup fee keeps short early runs
  profitable after fuel.

### Compatibility
- All 21 original cities and all 27 original direct legs are preserved
  verbatim, so old profiles and mid-trip snapshots load and resume unchanged.

## 1.2.1 — 2026-06-09

### Added
- **Mid-trip save and resume.** "Save and quit to main menu" while driving
  now snapshots the delivery — job, route, position on the route, clock,
  speeding strikes, and trip damage baseline — into the profile. Continue
  (and Load driver) resume the drive right where you left off, parked with
  the engine off, with a spoken recap of cargo, destination, remaining
  miles, and hours used. Construction and traffic zones reappear in the
  same places thanks to a persisted trip seed, and stops or cities already
  passed are not re-announced. The Load driver list shows mid-delivery
  profiles as "on the road to <city>".

### Fixed
- "Save and quit to main menu" no longer silently discards the delivery
  (previously Continue always returned to the city with the job gone).

## 1.2.0 — 2026-06-09

### Added
- **Smoother truck engine audio.** Engine sound now follows RPM more naturally,
  with smoother transitions as you accelerate, shift, and settle into highway
  speed.
- **Garage upgrades** (Garage → Upgrades), money-gated and saved on the
  profile: engine tune (+10% torque per tier, two tiers), aerodynamic kit
  (−12% drag), long-range tank (+50 gallons), and reinforced brakes (fade
  onset pushed 150 degrees hotter). Upgrades feed straight into the driving
  physics.
- **A second truck**: the heavy hauler (Garage → Trucks) — a quarter more
  torque and a 200-gallon tank, but blunter aerodynamics and a thirstier
  engine. Buy it once, then switch between owned trucks at any garage.
- **Freight market**: every cargo class carries a pay multiplier (0.8–1.3)
  that drifts each in-game day on a seeded random walk persisted in the
  profile. Job descriptions call out tight and loose markets,
  and the job board opens with a spoken market watch headline.

### Changed
- Truck status and garage refueling respect the active truck's actual tank
  size instead of assuming 150 gallons.
- Save format version is now 2 (older saves load fine; new fields get
  defaults).

### Notes
- BASS is proprietary software, free for non-commercial use. If Freight Fate
  is ever sold commercially, a paid license from
  [un4seen developments](https://www.un4seen.com/bass.html#license) is
  required. See the README's license section.

## 1.1.0 — 2026-06-09

### Added
- **Real-world weather** (Settings → Weather source): live current
  conditions for each city from the free
  [Open-Meteo](https://open-meteo.com) API (no key required). WMO weather
  codes map onto the game's conditions, including strong-wind promotion.
  Fetches run in background threads with a 15-minute cache; offline or on
  any failure the simulated weather takes over seamlessly.
- City coordinates in the world data.
- With real weather enabled, route planning's W key speaks live conditions
  for the cities along the route, and the V key while driving reports
  "live conditions" for the city you are heading toward.

## 1.0.0 — 2026-06-09

First release. Complete rewrite of the prototype.

### Added
- Career mode: jobs, route planning, deliveries, money, experience levels,
  reputation, and cargo endorsements (refrigerated at level 2, high-value at
  level 4).
- Tuned Class 8 truck physics: ten-speed transmission (manual with clutch or
  automatic), torque curve, grades, traction limits, stalling, brake fade,
  engine braking, and realistic fuel economy (~6 mpg loaded).
- 21-city, 27-leg interstate network with Dijkstra route finding and multiple
  route options per job.
- Dynamic regional weather (eight conditions) affecting grip, drag, and safe
  speed, with forecasts and thunder.
- Trip events: construction and traffic zones, road hazards with reaction
  windows, rest stop refueling, out-of-fuel roadside rescue, speeding fines.
- Screen reader output through Prism (`prismatoid`): NVDA, JAWS, SAPI,
  VoiceOver, Speech Dispatcher, and more, with silent fallback.
- Fully synthesized CC0 sound library (43 effects) and three original music
  tracks, all reproducible from `tools/generate_audio.py`.
- RPM-crossfaded engine audio, speed-tracking road noise, weather ambience.
- Accessible UI: spoken menus with wrap-around and first-letter navigation,
  contextual F1 help, accessible text entry, three speech verbosity levels,
  imperial/metric units, and a visible text mirror of all speech.
- First-drive tutorial, six-page in-game manual.
- Atomic JSON saves with multiple driver profiles.
- Packaged builds for Windows and Linux.

### Removed
- SRAL DLL dependency (replaced by the Prism Python package).
- Legacy prototype files and duplicate data files.
