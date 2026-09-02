//! The spoken manual: `HELP_PAGES` and the page-by-page, line-by-line
//! [`HelpState`] reader (port of `freight_fate/states/main_menu_help.py`).

use crate::app::GameContext;
use crate::states::base::{InputEvent, Key, State};

pub static HELP_PAGES: &[(&str, &[&str])] = &[
    (
        "The goal",
        &[
            "A new career starts as a company driver or an owner-operator.",
            "Company drivers use assigned carrier equipment; the carrier pays routine costs.",
            "Owner-operators start with a brand-new truck of their own and pay fuel, repairs, and business costs.",
            "Both start at level one: the choice changes who pays, not how far along you are.",
            "You start from your company terminal or yard in a metro service area.",
            "Each city stands for a wider freight area with many possible shippers.",
            "A new company hire is assigned the load and the route: accept, deadhead to the shipper, check in and load, run the assigned lane, and deliver on time and intact.",
            "Declining an assigned load costs dispatch trust.",
            "At level 8, dispatch lets you pick your own loads from the board. Owner-operators and own-authority drivers also choose their routes.",
            "Earn money and experience, climb 30 career ranks, and unlock better freight.",
            "Career plan at the terminal explains the next practical step.",
            "Own authority is a late business step: direct freight and higher overhead.",
        ],
    ),
    (
        "Menus",
        &[
            "Up and Down arrows move, Enter selects, Escape goes back.",
            "Home and End jump to the first and last option.",
            "Type a letter to jump to options starting with it.",
            "F1 reads help for the current option.",
            "Comma repeats what was just said and keeps stepping back through earlier messages; Period moves forward again.",
            "Control with Comma or Period jumps to the oldest or newest message. The bracket keys switch between all messages, general messages, and driving events. Control C copies the message you are on.",
            "Manage careers resets or deletes saved careers, with a confirmation first.",
            "A save the game cannot read is moved aside at the main menu. A save changed outside the game still loads, marked as modified.",
            "Learn game sounds, on the main menu and the pause menu, plays any sound the road uses and says what it means.",
        ],
    ),
    (
        "Settings",
        &[
            "Settings are grouped into categories: Gameplay, Audio, Speech, Updates, and Problem reports, plus a row that opens the Online menu. Open a category to see its settings.",
            "Gameplay has four screens: Driving assistance, Difficulty and hours of service, World and traffic, and Controls.",
            "Driving assistance holds lane keeping and every driving assist. World and traffic holds the weather, traffic, and parking sources. Audio holds the lane and edge cue volume. Problem reports says where the game log is saved.",
            "Up and Down pick a setting. Right arrow or Enter changes it forward, Left arrow backward. Changes save as you make them.",
            "Units switches miles and kilometers.",
            "Transmission chooses automatic or manual shifting.",
            "Automatic direction changes: Simple reverses after you stop while still holding the control; Deliberate waits for a release and a fresh press.",
            "Driving mode changes trip pacing and pressure: Relaxed, Standard, or Real time.",
            "Relaxed gives more time to respond, wider hazard windows, gentler damage and fatigue, and calmer speech.",
            "Standard keeps balanced timing and consequences and moves the clock twice as fast.",
            "Real time keeps Standard's pressure and runs the driving clock at the speed of a real clock, lined up with your computer's date and time. Delivery time remaining and hours of service do not move.",
            "Any of the three can be changed mid-drive from the pause menu.",
            "Hours of service: Realistic uses the full driving, duty, break, and rest rules. Relaxed gives longer limits and rarer road hazards. Real violations keep their normal consequences in either mode.",
            "Lane keeping sets how much of the lane-holding work the truck does.",
            "Full keeps the truck centered and takes your exits, including the destination exit, with no signal and no exit lane.",
            "Partial adds gentle drift with generous steering help. A short beep comes from the side you drift toward; steer away from it. A softer chime means you are centered again.",
            "Off drifts like a real wheel, with rumble-strip warnings and consequences, and every exit needs its signal and its exit lane.",
            "Lane changes: on partial or off, hold the steer across the lane line; on full, tap Left or Right.",
            "Discord presence shows your broad activity in Discord: the main menu, a route, resting, with the route and cargo. Never your saves or personal details. On by default; nothing happens if Discord is closed.",
            "Profile sharing can show a driver name you choose, your route, cargo, rough progress, achievements, road-journal posts, career totals, your truck, and your last-saved city on orinks.net. Full saves and precise location stay private.",
            "Nothing is shared until you set it up: the first time, your browser opens to pick that driver name and confirm. Connecting the account turns Profile sharing on and starts backing your careers up; each is its own row on the Online menu.",
            "The Online menu on the main menu gathers the drivers list, account setup, cloud backup, and sharing choices. The drivers list reads without sharing anything.",
            "Speech settings hold driving speech, the driving event voice, and menu position announcements; turn those off to hear only the option, not its place like three of ten.",
            "Audio volumes have their own help in the Audio category with F1.",
        ],
    ),
    (
        "Driving basics",
        &[
            "E starts the engine. To shut it down, slow below 5 miles per hour first.",
            "Air brakes need pressure before the truck can move: start the engine and wait for air pressure to reach 100 psi.",
            "Press P to release or set the parking brake. On low air, keep the parking brake set until pressure builds. Hard repeated braking uses air faster.",
            "Hold the Up arrow to accelerate, the Down arrow to brake.",
            "In automatic, once stopped, keep holding the Down arrow to back up slowly. Touch the Up arrow to brake and return to forward.",
            "Hold B for the emergency brake, the hardest possible stop.",
            "K starts automatic speed control: adaptive cruise with a three second clear-weather gap. Rain, snow, fog, or low visibility increase the following gap. It slows for traffic ahead but does not steer.",
            "Plus and minus, including the keypad keys, raise and lower the open-road cruise target by five miles per hour, even while the speed keeper is handling a low-speed zone. Control with plus or minus moves it by one.",
            "Space includes the active speed-control mode and target in the speed readout.",
            "Cruise looks ahead for sharp posted-limit drops and never holds more than five over the posted limit.",
            "The speed keeper handles low-speed local roads, like facility access roads, construction zones, or heavy traffic, then cruise resumes. The keeper eases off early for the next turn or the next lower limit.",
            "Press K again or touch the brakes to cancel the session. At the planned pickup it pauses instead and resumes once the loaded truck is rolling.",
            "The in-cab radio: M toggles it, Page Down and Page Up tune, Shift with either changes the radio volume, Y reads status. The radio has its own help page.",
            "In automatic the truck shifts for itself.",
            "Manual: hold Left Shift for the clutch, then W shifts up, Q shifts down, N is neutral, Backspace is reverse. From neutral or reverse, W selects first gear.",
            "J toggles the engine brake for long downhill grades; while it is on, 1, 2, and 3 select two, four, or six cylinders. J re-engages at the stage you last selected.",
            "Towns ban engine braking as noise: inside a no engine brake zone you are warned first, then fined if it stays on. Downgrades and emergencies are exempt.",
            "Curve speed assistance takes a bend on the service brakes, never the engine brake. On a real downgrade it does raise the jake.",
            "Inside a no engine brake zone, cruise and curve speed assistance keep the jake off and hold speed with the brakes, except on real downgrades.",
            "Hold H to sound the horn; release to stop it.",
            "Learn game sounds, on the pause menu, plays every cue on demand with what it means.",
        ],
    ),
    (
        "Driving information keys",
        &[
            "Space speaks your speed, gear, RPM, active speed-control mode, open-road target, air pressure, and brake state.",
            "S speaks the posted speed limit here, the zone if any, and how far over you are.",
            "D speaks one safe-speed number for right now, with weather grip and an armed exit ramp already in it.",
            "G speaks the grade under the wheels, how far it runs, whether the truck is holding, pulling, or losing it, and the next grade ahead.",
            "Steep grades of three percent or more announce themselves ahead, except on quiet or urgent only speech, where G answers on demand.",
            "Tab opens a driving status menu for route, driver, map, and the Driver apps tablet: Navigation, Weather, Traffic, Truck stops, Road chatter, and ELD, each read line by line.",
            "F speaks fuel level and range.",
            "C speaks the clock, your deadline, and the one hours limit that comes first.",
            "Three keys answer one hours question each.",
            "Alt A speaks time at the wheel so far and time on duty this shift.",
            "Alt S speaks when your 30 minute break is due, or that a break will not help.",
            "Alt D speaks what ends this shift, driving time and duty window both, and where you can legally stop before it.",
            "With enforcement off each of the three says so.",
            "R speaks how far along you are and how far is left, then the road, the state, and the city you are heading toward. With a planned stop set, it counts down to that stop instead.",
            "Four keys answer one part of that each.",
            "Alt 1 speaks the state you are in.",
            "Alt 2 speaks the road you are on, signed the way you would read it.",
            "Alt 3 speaks the town you are in, or the nearest one and how far off the road it sits.",
            "Alt 4 speaks the direction you are travelling.",
            "The keypad numbers work the same way.",
            "X signals for the next announced route exit, or cancels that signal.",
            "L speaks which lane you are in and your position inside it.",
            "I turns the lane locator on and off: a soft tock once a beat, panned to where the truck sits in its lane. It needs lane keeping on partial or off.",
            "Drift beeps come from the side you drift toward; steer away from the beep. A softer chime means you are centered again.",
            "V speaks the weather and the forecast.",
            "A repeats the last driving announcement.",
            "Alt C repeats the last CB chatter on its own, with the distance as it is now, and says so once you have passed what the CB called.",
            "Comma repeats what was just said and keeps stepping back; Period moves forward again. Control with Comma or Period jumps to the oldest or newest message, the bracket keys switch between all messages, general messages, and driving events, and Control C copies the one you are on.",
            "U speaks the road ahead that no other key answers: the ramp control coming up, the next imposed speed limit, the next stop, and the next bend that demands slowing.",
            "Left or Right Control stops the driving event voice.",
            "Escape opens the pause menu.",
        ],
    ),
    (
        "Controller",
        &[
            "A game controller works alongside the keyboard, which stays active. The first connected controller is used, plugged in or unplugged while you play. Controller support is under Settings, Gameplay, Controls.",
            "Button names use the Xbox layout: A, B, X, Y, the bumpers, and the D-pad.",
            "In menus: D-pad up and down move, D-pad left and right adjust an option, A confirms like Enter, B goes back like Escape, Back reads help like F1. While the driving voice is speaking, Back stops it instead.",
            "Driving: right trigger is the gas, left trigger the brake; the left trigger fully in is the hardest stop. The left stick steers.",
            "Hold the left bumper for the clutch; A shifts up, X shifts down. Y starts automatic speed control. B speaks your speed.",
            "Click the left stick for the horn, the right stick for the engine brake. Start pauses and unpauses.",
            "D-pad up reads your route and current location, down signals for the next exit, left the weather, right the clock with your full hours of service.",
            "Hold the right bumper for the second layer: plus A starts or stops the engine, plus B reads fuel, plus X reads the posted speed limit here and how far over you are, plus Y sets or releases the parking brake, plus D-pad up reads the next listed exit, plus D-pad down opens route-stop actions or emergency shoulder sleep when fully stopped away from route points, plus D-pad left and right lower and raise the open-road cruise target, and plus Start opens the status menu.",
        ],
    ),
    (
        "On the road",
        &[
            "Loaded trips follow a route made from real highway corridors.",
            "GPS announces state lines, intermediate places, traffic, highway changes, and rest-stop exits.",
            "Grades and terrain come from the route. Weather, traffic, and construction still vary by time, place, and seed. Rush hours can make metro corridors busier.",
            "Weather matters: well over the safe speed on a slick road risks losing traction; wind and storms add drag that costs speed and fuel; low visibility shortens the warning before a hazard.",
            "Your career runs on a calendar that starts in spring and advances as you drive, rest, and sleep, so the season and weather change through the year. The date is spoken with the clock on C, in the Tab status menu, and at the terminal.",
            "Posted limits come from real map data and change along the corridor. A change is announced as reduced or raised, named near a city. Limits also drop in construction and traffic zones.",
            "Congestion follows real traffic volumes: busy metro stretches jam at weekday rush hour, about seven to nine in the morning and four to six thirty in the evening, and flow free late at night and on weekend mornings.",
            "Enforcement posts sit along the road: median crossovers, weigh station aprons, construction zone details, city units. Most are empty. A post with somebody in it makes a sound before it can see you.",
            "Whether an officer notices you is graded. Five over is seen and ignored; twenty over is certain. A crest blocks a laser, fog blinds an officer's eyes and barely touches radar, and running in a pack at the pack's speed lowers your odds. Officers also see visible damage, no chains inside a chain control, and following far too close.",
            "When a trooper lights you up: signal with X and brake to a stop on the shoulder for a license and logbook check ending in a ticket or a warning. Ignoring the lights is evasion and costs far more.",
            "Fines are real money: a few hundred dollars for lights, thousands for unsafe equipment or running an open scale. Each citation already on your record makes the next one dearer, up to double after your third. A fine inside a construction zone is doubled on top of that.",
            "Some tickets cost more than money. Fifteen or more over the limit, rolling through a failure-to-stop warning, driving through the barrels, and a second run off the road asleep are serious violations. Two inside three years suspend your CDL for sixty days, and you cannot take a load while it runs; a third costs a hundred and twenty. Running from a stop is a major offense: a year the first time, for life the second.",
            "CB chatter passes on what other drivers have seen. It says how sure it is, it is sometimes stale, and it never claims the road is clear. The status menu lets you review that chatter with the route guidance; Alt C says the last CB call again.",
            "Hazards come from traffic ahead: slow lead vehicles, merging traffic, lane restrictions, and queues. Nearby vehicles merge, brake, pass, or slow in your lane. Adaptive cruise follows them; you still steer and manage space.",
            "Highway stops use clear place names and list the actions available there: fuel, eat, rest, save, inspect, or call for help, depending on the stop.",
            "Toll roads, plazas, and electronic gantries are announced. Tolls and approved company charges are paid or reimbursed at settlement, listed separately from fines an earlier load could not cover. Service plazas on toll roads work like stops.",
            "Brake now means slow below twenty five miles per hour quickly to avoid a collision.",
            "Change lanes or brake means a fixed object in your lane. The call ends by naming the open lane: left lane open, right lane open, or either lane open. With lane keeping on partial or off, steer across the lane line; on full, tap Left or Right. Braking works too, but takes nearly a full stop before you can ease around.",
            "Brake with no lane open means nowhere to go around: brake, and do not reach for a lane change.",
            "Lane counts come from real map data, from one lane your side up to several. The drive says when the road widens or narrows, and L speaks which lane you are in. Exits leave from the right lane. Keep right except to pass.",
            "Construction sometimes closes a lane, never where the road runs one lane your side. The taper callout names the closed side; driving through the barrels means truck damage, a citation, and a serious violation.",
            "Rest stops sit at highway exits, announced a few miles out, with one-mile exit cues and turn guidance.",
            "While rolling toward a sleep-capable stop, T plans that stop and names the distance, exit, and whether stopping assistance is on. T never signals: press X to take the exit.",
            "X signals or cancels the exit. Slow to forty five for the ramp and set up the exit lane unless lane keeping is on full. Too fast and you miss the exit. Off the ramp, brake to a stop for the rest stop menu: refuel, take a break, sleep, or save.",
            "Most ramps end at a traffic light or a stop sign, called out on the way down. Lights cycle green, yellow, red, and every change is spoken. Yellow means stop unless you are already at the light.",
            "Red light or stop sign: full stop at the bar, then go on green or in a clear gap. Rolling through draws horns; blowing through at speed means cross traffic clips the trailer.",
            "Destination exits are announced with their signed exit and toward cities. Use X for the destination signal unless lane keeping is on full, which takes it for you. Off the highway, brake to a stop at the receiver gate.",
            "Miss the destination exit and dispatch loops you back through the next safe turnaround.",
            "Ordinary pass-by exits are not spoken; the status screen lists the next exit.",
            "Fully stopped at a route stop, T opens its menu. Fully stopped away from route points, T opens the emergency shoulder-sleep warning instead; nearby route points always take priority.",
            "Miss a stop and T plans the next sleep-capable one. Already safely stopped at the missed route point, T opens its menu.",
            "Fuel prices vary by region. Company drivers fuel on the carrier card; owner-operators pay their own diesel.",
            "Running out of fuel means a roadside rescue: owner-operators pay, company drivers take a service-record hit.",
            "A badly damaged truck: the pause menu calls a roadside mechanic for a pricey field repair.",
        ],
    ),
    (
        "Hours and rest",
        &[
            "The ELD tracks driving, on-duty-not-driving, off-duty, and sleeper time.",
            "Eleven hours of driving after ten consecutive hours off duty, inside a fourteen hour duty window.",
            "A thirty minute break is required after eight cumulative hours of driving. Any thirty consecutive non-driving minutes count: loading, fueling, inspection, or a rest-stop break.",
            "Spoken warnings come at two hours, one hour, and thirty minutes left.",
            "Alt A reads time at the wheel, Alt S when the break is due, Alt D what ends the shift. C reads the clock and the nearest limit; the Tab status menu holds the whole hours report.",
            "Sleeping ten hours at a rest stop or a terminal starts a fresh shift.",
            "At sleep-capable truck parking, the sleeper berth offers two, three, seven, or eight hours to build a legal split, or ten hours for the full reset.",
            "Driving past a limit risks inspections, fines, and out-of-service orders.",
            "Fatigue builds as you drive, faster at night. A drowsy driver yawns, drifts onto the rumble strip, and reacts late.",
            "Late at night, truck parking may be full. A full lot still sells diesel.",
            "Stopped on the open road with no stop nearby, T or the pause menu offers emergency shoulder sleep: a legal ten-hour reset with poor rest, a possible parking ticket or minor damage, and the deadline keeps running.",
            "A basic break or fuel stop with no overnight parking offers Sleep 10 hours in the lot: cramped and poor.",
            "A motel room near the lot costs your own money for the same legal reset with full rest, and is offered when parking is full.",
            "Sleep-capable parking gives the best, fully-rested ten-hour sleep.",
            "When a limit is closing in with no reachable stop, the game warns you and points to shoulder sleep.",
            "Settings can make hours rules gentler.",
        ],
    ),
    (
        "The in-cab radio",
        &[
            "The radio is optional; speech and safety cues always come first. It has power only while the engine runs.",
            "M toggles the radio. Page Down tunes to the next station, Page Up to the previous; semicolon and apostrophe do the same.",
            "Control with any of those jumps a whole category, like AFN to terrestrial. Shift with any of those changes the radio volume in 10 percent steps, on or off. Y speaks the station, signal, volume, and streamer-safe status.",
            "M3U playlist files in the Playlists folder next to your saves each become a station under Your playlists. They play only with streamer-safe mode off.",
            "The Tab status menu has a Radio screen listing receivable stations.",
            "The Freight Fate Roadhouse plays road music everywhere, day and night, with a host between songs. The Night Line does the same after dark, quieter.",
            "Fictional regional stations cover markets across the map with country, classic rock, and blues and soul.",
            "Stations behave like real FM signals: clear near their market, static at the fringe, gone past the edge. The terrestrial category lists the strongest signal first, and the radio turns on to a station that plays clean.",
            "When a station fades out, the radio says so and falls back to the Roadhouse.",
            "Real public streams, including AFN, play out of the box; streamer-safe mode in settings hides them for anyone streaming or recording. A stream that cannot play falls back safely.",
        ],
    ),
    (
        "Deliveries and money",
        &[
            "The dispatch board lists freight for the current metro service area.",
            "A metro can contain ports, rail and intermodal ramps, air cargo areas, parcel hubs, grocery distribution centers, dry warehouses, cold storage, food processors, farms and grain elevators, manufacturing plants, steel and industrial sites, automotive suppliers, chemical terminals, construction yards, mines and quarries, lumber or paper facilities, cross-docks, and company yards.",
            "Each job names an origin facility and a destination facility. Cargo follows facility roles, and not every market supports every cargo equally: ports see containers and bulk, farm regions grain and food, industrial regions steel, machinery, automotive, chemicals, lumber, and construction materials. Border and gateway metros offer cross-dock freight.",
            "New company hires see one assigned load with accept and decline; the full board opens at level 8.",
            "F1 on a dispatch reads its details line by line.",
            "Dispatch warns when a load may not fit your remaining legal hours.",
            "After accepting, leave the terminal bobtail or with an empty trailer. Pickup legs are local deadhead moves to the origin facility.",
            "At the pickup gate, stop to open the facility menu. Check in, then load at the assigned dock. Loading requires the truck to be stopped.",
            "Once loaded and sealed, company drivers depart on dispatch's assigned route; owner-operators and own-authority drivers pick from the route options.",
            "Deliver before the deadline for a bonus. Late or damaged cargo pays less.",
            "At the destination facility, stop, then dock and deliver.",
            "Settlement reports gross pay, carrier-paid or reimbursed charges, fines carried over from earlier loads, business operating charges, and net driver pay. Tickets written on the road were already paid on the spot and are never charged again. Speeding nobody saw costs nothing at all.",
            "After settlement, the truck is parked at the destination terminal.",
            "Company-driver settlements pay wages and bonuses from carrier gross. Owner-operator and direct freight settlements pay higher gross, but fuel, repairs, reserves, trailer costs, and fees come out of the business.",
            "Trailer requirements are listed on freight that needs special equipment. Fragile cargo, like electronics and fresh food, punishes rough driving.",
            "Repair your truck in the terminal garage. Damage climbs in bands: past fifty percent the engine holds power back and burns more fuel; past seventy five, limp mode caps you at forty five miles per hour; past ninety the truck is out of service, with just enough speed to clear the lane before road service comes, and the wait runs hours.",
            "Miles add tire wear and road grime for the garage to service.",
            "Specialty and premium cargo earn bonus experience, and a streak of on-time deliveries compounds it.",
            "Company settlements add a dispatch trust bonus that grows as your reputation climbs above fifty.",
            "Dispatch trust answers to your record and what you owe as well as your reputation. Low trust means fewer and poorer loads, load choice taken back, better equipment held back, and experience at a reduced rate.",
            "Higher levels widen distance caps, improve low-end pay, and unlock more facility variety plus refrigerated, heavy-haul, high-value, and liquid bulk freight.",
            "Carrier certificates unlock by level when the company sponsors the training, or earlier if you pay for the course at the terminal.",
            "The CDL endorsements go further: doubles opens twin-trailer freight, tank opens liquid bulk, and hazmat adds a paid background check that clears over game days while you keep driving.",
            "Late in the career, the TWIC port card opens secure port containers and the LCV certificate opens turnpike doubles where states allow them. Book everything under Licenses and training at any terminal.",
            "Cargo markets drift day by day. The board calls out tight and loose markets; tight cargo pays well above the usual rate.",
        ],
    ),
    (
        "Markets and route coverage",
        &[
            "Freight Fate focuses on major freight areas instead of every town, connected by drivable long-haul routes.",
            "Freight variety comes from the facilities inside each area: a Chicago to Los Angeles load can be an intermodal ramp, cold storage, a port terminal, a parcel hub, or a plant.",
            "New dispatches use routes with enough stops to make fuel, rest, and hours planning playable.",
            "Some common facilities are representative locations for the area and still behave like named places with clear cargo roles.",
        ],
    ),
    (
        "The garage",
        &[
            "Every terminal garage refuels, repairs, services tires, and washes the active tractor.",
            "The garage sells winter equipment. Winter tires grip snow and ice better but wear faster and give up a little on warm dry pavement. Snow chains ride in the side box until a mountain pass calls for them.",
            "A flashing chain-law sign before a snowy or icy grade tells the level: Level 1 needs winter tires or chains, Level 2 needs chains on the drives.",
            "Chain up from the pause menu while stopped. It takes real time, longer and more tiring in the dark. Passing an active chain law out of compliance risks a citation of nearly six hundred dollars, more with citations on your record.",
            "Chains hold on ice, but keep near thirty miles per hour and pull them off before the road turns bare, or they grind apart, snap, and take a bite out of the fender.",
            "Company-driver fuel and routine repairs use the carrier account. Owner-operators pay from business cash; short of a full tank or full repair, the garage sells as much as the money covers.",
            "The Upgrades menu unlocks with owner-operator status: an engine tune, an aerodynamic kit, a long-range tank, and reinforced brakes. Upgrades are fleet packages and apply to every tractor you own.",
            "Engine tune gives more pulling power for heavy freight, hills, and mountain grades.",
            "Aerodynamic kit burns less fuel at highway speed; same tank, fewer gallons per mile.",
            "Long-range tank carries fifty more gallons; more fuel onboard, not better efficiency.",
            "Reinforced brakes keep stopping power longer on descents and emergency stops.",
            "The Trucks menu is locked for company drivers. Owner-operators buy or switch owned tractors at the garage.",
            "Trailers are carrier-provided for company drivers. Leased-on owner-operators can add trailer programs; own-authority drivers can buy trailers.",
        ],
    ),
];

/// Index of the driving-keys page, so callers can open help straight to it.
pub fn controls_help_page() -> usize {
    HELP_PAGES
        .iter()
        .position(|(title, _lines)| *title == "Driving information keys")
        .unwrap_or(0)
}

/// Page-by-page, line-by-line spoken manual.
pub struct HelpState {
    pub page: usize,
    /// `-1` = page title.
    pub line: i64,
}

impl HelpState {
    /// `HelpState(ctx, start_page=0)`.
    pub fn new() -> Self {
        Self::at_page(0)
    }

    /// `HelpState(ctx, start_page=...)`: out-of-range requests clamp.
    pub fn at_page(start_page: usize) -> Self {
        Self {
            page: start_page.min(HELP_PAGES.len() - 1),
            line: -1,
        }
    }

    fn page_title(&self) -> String {
        let (title, lines) = HELP_PAGES[self.page];
        format!(
            "Page {} of {}: {title}. {} lines.",
            self.page + 1,
            HELP_PAGES.len(),
            lines.len()
        )
    }
}

impl Default for HelpState {
    fn default() -> Self {
        Self::new()
    }
}

impl State for HelpState {
    fn enter(&mut self, ctx: &mut GameContext) {
        ctx.say(&format!(
            "How to play. Left and Right arrows change pages, Up and Down read line \
             by line, Enter reads the whole page, Left or Right Control stops \
             speech, Escape goes back. {}",
            self.page_title()
        ));
    }

    fn handle_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        let Some((key, _, _)) = event.key_down() else {
            return;
        };
        let (title, lines) = HELP_PAGES[self.page];
        match key {
            Key::Escape => {
                ctx.audio.play("ui/menu_back");
                ctx.pop_state();
            }
            Key::LCtrl | Key::RCtrl => ctx.stop_speech(),
            Key::Right | Key::PageDown => {
                self.page = (self.page + 1) % HELP_PAGES.len();
                self.line = -1;
                ctx.audio.play("ui/menu_move");
                ctx.say(&self.page_title());
            }
            Key::Left | Key::PageUp => {
                self.page = (self.page + HELP_PAGES.len() - 1) % HELP_PAGES.len();
                self.line = -1;
                ctx.audio.play("ui/menu_move");
                ctx.say(&self.page_title());
            }
            Key::Down => {
                self.line = (self.line + 1).min(lines.len() as i64 - 1);
                ctx.say(lines[self.line as usize]);
            }
            Key::Up => {
                self.line = (self.line - 1).max(0);
                ctx.say(lines[self.line as usize]);
            }
            Key::Return | Key::KpEnter | Key::Space => {
                ctx.say(&format!("{title}. {}", lines.join(" ")));
            }
            _ => {}
        }
    }

    fn lines(&self, _ctx: &GameContext) -> Vec<String> {
        let (title, lines) = HELP_PAGES[self.page];
        let mut out = vec![
            format!(
                "How to play - {title} ({}/{})",
                self.page + 1,
                HELP_PAGES.len()
            ),
            String::new(),
        ];
        for (i, text) in lines.iter().enumerate() {
            let marker = if i as i64 == self.line { "> " } else { "  " };
            out.push(format!("{marker}{text}"));
        }
        out
    }
}
