from __future__ import annotations

import pygame

from .base import State

HELP_PAGES = [
    (
        "The goal",
        [
            "A new career starts with a choice: company driver carrier or owner-operator start.",
            "Company drivers use assigned carrier equipment and carrier-paid routine costs.",
            "The owner-operator start skips ahead, but fuel, repairs, and business costs are yours.",
            "Start from your company terminal or yard in a metro service area.",
            "Each city stands for a wider freight area with many possible shippers.",
            "Freedom over freight is earned. As a new company hire, dispatch assigns",
            "your load and your route: accept the assignment, deadhead to the shipper,",
            "check in and load the trailer, run the assigned lane, and deliver",
            "across the country, on time and intact.",
            "You can decline a few assigned loads before your next promotion,",
            "but refusals cost standing with dispatch.",
            "At level 8, dispatch trusts you to pick your own loads from the board.",
            "Choosing your own routes is the owner-operator and own-authority reward.",
            "Earn money and experience, level through 30 career ranks, and unlock better freight.",
            "After your first dispatch, Career plan at the terminal explains the next practical step.",
            "The company path prepares for owner-operator work before the later buy-in.",
            "Own authority is an endgame business step with direct freight and higher overhead.",
        ],
    ),
    (
        "Menus",
        [
            "All menus use Up and Down arrows, Enter to select, Escape to go back.",
            "Home and End jump to the first and last option.",
            "Type a letter to jump to options starting with that letter.",
            "Press F1 in any menu for contextual help.",
            "Manage careers on the main menu lets you reset or delete saved careers,",
            "with a confirmation screen before anything destructive happens.",
            "Edited or corrupted career saves may be moved aside at the main menu.",
        ],
    ),
    (
        "Settings",
        [
            "Settings are grouped into categories: Gameplay, Audio, Speech and",
            "weather, and Updates. Open a category to see its settings.",
            "Use Up and Down arrows to choose a setting inside a category.",
            "Use Right arrow or Enter to change the selected setting forward.",
            "Use Left arrow to change it backward. Escape goes back, and changes",
            "are saved as you make them.",
            "Gameplay settings change how the game feels, not your save progress.",
            "Units switches speed and distance between miles and kilometers.",
            "Transmission chooses automatic shifting or manual shifting.",
            "Automatic direction changes chooses how an automatic switches between",
            "forward and reverse. Simple changes after you stop while holding the",
            "control. Deliberate waits for you to release and press it again.",
            "Driving mode changes trip pacing and pressure: Relaxed, Standard, or Realistic.",
            "Relaxed gives more real time, wider hazard windows, gentler damage and fatigue,",
            "and calmer speech while keeping weather, traffic, air brakes, and truck handling.",
            "Standard keeps balanced timing and consequences.",
            "Realistic moves fastest, so decisions arrive sooner without extra forgiveness.",
            "Hours of service changes how strict the legal driving clock is.",
            "Realistic uses the full driving, duty, break, and rest rules.",
            "Relaxed hours rules give longer limits and rarer random road hazards.",
            "Real violations keep their normal consequences in either hours mode.",
            "Lane drift adds an optional lane-position task while you drive.",
            "Off keeps the truck centered in its lane. Light adds gentle drift.",
            "When you drift, a short beep comes from that side.",
            "Steer away from the beep; a softer chime confirms you are centered again.",
            "Realistic adds stronger drift, rumble-strip warnings, and consequences.",
            "Lane changes work in every mode: with drift on, hold the steer",
            "across the lane line; with drift off, tap Left or Right.",
            "Discord presence shows your broad activity in Discord when it is running,",
            "like the main menu, driving a route, or resting, with the route and cargo.",
            "Only general game status is shared, never your saves or personal details.",
            "It is on by default and has no effect if Discord is closed.",
            "Profile sharing can make eligible driver information public on orinks.net,",
            "showing a driver name you choose, your route, cargo, and rough progress.",
            "It can include official achievements, automatic road-journal posts,",
            "career totals, your current truck, and your last-saved city.",
            "Public profiles and eligible posts can appear in the Freight Fate updates feed;",
            "private profiles expose none of this. Full saves and precise location stay private.",
            "Nothing is shared until you set it up: the first time, your browser opens",
            "so you can pick that driver name and confirm before anything is sent.",
            "Drivers online in the main menu reads the same board without sharing anything.",
            "Speech settings include verbosity, the driving event voice, and a toggle",
            "for menu position announcements: turn it off to hear only the option,",
            "not its place like three of ten.",
            "Audio volumes have their own help text in the Audio category with F1.",
        ],
    ),
    (
        "Driving basics",
        [
            "E starts the engine. To shut it down, slow below 5 miles per hour first.",
            "Air brakes need pressure before the truck can move.",
            "Start the engine and wait for air pressure to reach 100 psi.",
            "Press P to release or set the parking brake.",
            "If you hear low air, keep the parking brake set and let pressure build.",
            "Hard repeated braking can use air faster than gentle normal driving.",
            "Hold the Up arrow to accelerate, the Down arrow to brake.",
            "In automatic, once stopped, keep holding the Down arrow to back up slowly.",
            "Touch the Up arrow to brake and return to forward drive.",
            "Hold B for the emergency brake: the hardest possible stop,",
            "for hazards and rest stops you would otherwise overshoot.",
            "K sets adaptive cruise at your current speed with a three second clear-weather gap.",
            "Rain, snow, fog, or low visibility increase the following gap.",
            "It can slow for traffic ahead, but it does not steer for you.",
            "Plus and minus, including the keypad keys, raise and lower the set cruise speed by five miles per hour,",
            "so you can dial it up to the speed you want once cruise is engaged.",
            "Space includes the cruise set speed in the speed readout when cruise is on.",
            "Cruise looks ahead for sharp posted-limit drops and will not hold more than five over the posted limit.",
            "Cruise will not engage on low-speed local roads, like facility access",
            "roads, construction, or heavy traffic; take those manually.",
            "Press K again or touch the brakes to cancel it.",
            "The in-cab radio is optional and stays secondary to safety cues.",
            "M toggles it, brackets tune, and Y reads status;",
            "the radio has its own help page with stations, hosts, and signal ranges.",
            "In automatic mode the truck shifts for itself.",
            "In manual mode, hold Left Shift for the clutch,",
            "then press W to shift up a gear or Q to shift down, or N for neutral.",
            "From neutral or reverse, W selects first gear.",
            "Manual transmission uses Backspace for reverse after pressing the clutch.",
            "J toggles the engine brake for long downhill grades.",
            "Hold H to sound the horn; release H to stop it.",
        ],
    ),
    (
        "Driving information keys",
        [
            "Space speaks your speed, gear, RPM, cruise set speed when cruise is on, air pressure, and brake state.",
            "S speaks the posted speed limit here, the zone if any, and how far over you are.",
            "Tab opens a driving status menu for route, driver, map, and a Driver apps tablet menu.",
            "Inside Driver apps, choose Navigation, Weather, Traffic, Truck stops,",
            "Road chatter, or ELD, then review that app line by line.",
            "F speaks fuel level and range.",
            "C speaks the clock, your deadline, and your hours of service.",
            "R speaks route progress, GPS context, and the next stop or maneuver.",
            "Shift R speaks the next listed highway exit for route context.",
            "X signals for the next announced route exit or cancels that signal.",
            "L speaks which lane you are in and your position inside it.",
            "Directional beeps cue drift direction; steer away from the beep.",
            "A softer chime confirms when you are centered again.",
            "V speaks the weather and the forecast.",
            "A repeats the last route announcement, in case you missed it.",
            "U speaks what is coming up: imposed speed limits, stops, and exits ahead.",
            "Left or Right Control stops the driving event voice.",
            "Escape opens the pause menu.",
        ],
    ),
    (
        "Controller",
        [
            "A game controller works alongside the keyboard, which stays active.",
            "The first connected controller is used automatically, and the game",
            "detects one plugged in or unplugged while you play. Turn controller",
            "support off under Settings, Gameplay if you prefer keyboard only.",
            "Button names use the Xbox layout: A, B, X, Y, the bumpers, and the D-pad.",
            "In menus: D-pad up and down move, D-pad left and right adjust an option,",
            "the A button confirms like Enter, the B button goes back like Escape,",
            "and the Back button reads help like F1.",
            "Driving: right trigger is the gas, left trigger the brake; press the",
            "left trigger fully for the hardest stop. The left stick steers.",
            "Hold the left bumper for the clutch; the A button shifts up a gear and",
            "the X button shifts down. The Y button sets adaptive cruise.",
            "The B button speaks your speed. Click the left stick to honk the horn,",
            "the right stick to toggle the engine brake. Start pauses and unpauses.",
            "D-pad up reads your route, down takes the next exit, left the weather,",
            "and right the clock.",
            "Hold the right bumper for the second layer: plus A starts or stops the",
            "engine, plus B reads fuel, plus Y sets or releases the parking brake,",
            "plus D-pad up reads the next listed exit, plus D-pad down opens rest-stop",
            "actions, plus D-pad left and right lower and raise the cruise speed, and",
            "plus Start opens the status menu.",
        ],
    ),
    (
        "On the road",
        [
            "Loaded trips follow a route made from real highway corridors.",
            "Progress is not just city to city: GPS announces state lines,",
            "intermediate places, traffic, highway changes, and rest-stop exits.",
            "Grades and terrain come from the route you are driving.",
            "Weather, traffic, and construction still vary by time, place, and seed.",
            "Rush hours can make metro corridors busier.",
            "Weather is not just flavor. Driving well over the safe speed for the",
            "conditions on a slick road risks losing traction; high winds and storms",
            "add drag that costs speed and fuel; and low visibility shortens how much",
            "warning you get before a hazard, so slow down in fog and heavy rain.",
            "Your career runs on a calendar that starts in spring and advances as you",
            "drive, rest, and sleep, so the season and weather shift through the year.",
            "The date and season are spoken with the clock on C, in the Tab status",
            "menu, and at the city terminal.",
            "Posted limits come from real map data and change along the corridor.",
            "A change is announced as reduced or raised, and named near a city.",
            "Watch your speed: limits also drop in construction and traffic zones.",
            "Congestion is grounded in real traffic volumes from federal highway",
            "data: busy metro stretches jam at weekday rush hour, roughly seven to",
            "nine in the morning and four to six thirty in the evening, and flow",
            "free late at night and on weekend mornings. Plan departures around",
            "the big cities like a real dispatcher.",
            "State troopers patrol some stretches. Speed badly inside a patrol and a",
            "trooper may light you up: signal with X, brake to a stop on the shoulder,",
            "and sit through a license and logbook check ending in an on-the-spot",
            "ticket or a warning. Ignoring the lights is logged as evasion, which",
            "costs far more. Speeding the patrols miss still adds a quieter charge",
            "at settlement.",
            "CB chatter may mention a bear ahead or enforcement near a work zone.",
            "Use the status menu to review that chatter with other route guidance.",
            "Some hazards come from traffic ahead, such as slow lead vehicles,",
            "merging traffic, lane restrictions, and queues.",
            "Nearby simulated vehicles may merge, brake, pass, or slow in your lane.",
            "Adaptive cruise can follow them, but you still steer and manage space.",
            "Highway stops use clear place names and list the actions available there.",
            "Depending on the stop, you may be able to fuel, eat, rest, save, inspect,",
            "or call for help.",
            "Toll roads, plazas, and electronic gantries are announced while driving.",
            "Tolls and approved company charges are paid or reimbursed at settlement.",
            "They are listed separately from costs you caused, like speeding fines.",
            "Service plazas on toll roads still behave like stops when fuel, food,",
            "breaks, or saves are available.",
            "When you hear Brake now, slow below twenty five miles per hour quickly",
            "to avoid a collision. These warnings are tied to road or traffic context.",
            "When you hear Brake or change lanes, a quick move to a clear lane",
            "works too: with lane drift on, steer across the lane line;",
            "with lane drift off, tap Left or Right to change lanes.",
            "Check the space first. Swerving into traffic is worse than braking.",
            "The interstate runs two lanes each way. Exits leave from the right",
            "lane, and camping the left lane draws CB grumbling: keep right",
            "except to pass.",
            "Construction sometimes closes a lane. The taper callout names the",
            "closed side; move over when told or you will plow through the",
            "barrels and damage the truck.",
            "Hold B for the emergency brake when normal braking is not enough.",
            "Rest stops sit at highway exits, announced a few miles out.",
            "The GPS adds one-mile exit cues and concise turn guidance.",
            "Use X to signal or cancel your intent, slow to forty five for",
            "the ramp, and set up the exit lane when lane drift is enabled.",
            "When speed, lane setup, and route intent are valid,",
            "the truck takes the ramp, then you brake to a stop for the rest stop menu:",
            "refuel, take a break, sleep, or save. Too fast and you miss the exit.",
            "Most ramps end at a real intersection: a traffic light or a stop sign,",
            "called out on the way down the ramp, grounded in map data where tagged.",
            "Red light or stop sign: brake to a full stop at the bar and wait for",
            "green or a clear gap. Rolling through draws horns; blowing through",
            "at speed means cross traffic clips the trailer.",
            "Destination exits are announced with their signed exit and toward cities.",
            "Use X for the destination signal when lane drift is enabled;",
            "with lane drift off, the GPS infers destination intent from the route.",
            "If you miss the destination exit, back up until it is ahead, then set up again.",
            "Ordinary pass-by exits stay out of automatic speech;",
            "use Shift R when you want the next listed exit for context.",
            "T still opens the menu if you simply stop on the highway at one.",
            "If you miss a stop, slow down, back up carefully to it, stop, then press T.",
            "Fuel prices vary by region. Company drivers fuel on the carrier",
            "card at truck stops; owner-operators pay their own diesel.",
            "Running out of fuel means a roadside rescue: owner-operators pay",
            "for it, and company drivers take a service-record hit instead.",
            "If collisions leave the truck badly damaged, open the pause menu",
            "and call a roadside mechanic for a pricey field repair.",
        ],
    ),
    (
        "Hours and rest",
        [
            "The ELD tracks driving, on-duty-not-driving, off-duty, and sleeper time.",
            "You may drive eleven hours after ten consecutive hours off duty,",
            "within a fourteen hour duty window after coming on duty.",
            "A thirty minute break is required after eight cumulative hours of driving.",
            "Any thirty consecutive non-driving minutes satisfy that break rule,",
            "including loading, fueling, inspection, or explicit rest-stop breaks.",
            "Spoken warnings come at two hours, one hour, and thirty minutes left.",
            "Sleeping ten hours at a rest stop, or at a terminal, starts a fresh shift.",
            "At sleep-capable truck parking, the sleeper berth is your cab bunk.",
            "You can choose two, three, seven, or eight hours in the sleeper berth",
            "to build a legal split, or sleep ten hours for the simple full reset.",
            "Driving past a limit risks inspections, fines, and out-of-service orders.",
            "Fatigue builds as you drive, faster at night. A drowsy driver",
            "yawns, drifts onto the rumble strip, and reacts late to hazards.",
            "Late at night, truck parking may be full. Drive on, or risk",
            "a ticket and poor sleep on the shoulder.",
            "You can always find somewhere to sleep. Stopped on the open road with no",
            "stop nearby, the pause menu offers an emergency shoulder sleep: a legal",
            "ten-hour reset, but poor rest, with a possible parking ticket or minor",
            "damage, and the deadline keeps running.",
            "A basic break or fuel stop with no overnight parking offers",
            "Sleep 10 hours in the lot: cramped and poor.",
            "A motel room near the lot costs your own money but gives the same",
            "legal reset with full rest, and it is also offered when parking is full.",
            "Sleep-capable parking still gives the best, fully-rested ten-hour sleep.",
            "When a sleep or duty limit is closing in with no reachable stop, the game",
            "warns you and points you to the shoulder-sleep option.",
            "Settings can make hours rules gentler.",
        ],
    ),
    (
        "The in-cab radio",
        [
            "The radio is optional comfort: speech and safety cues always come first.",
            "M toggles the radio, bracket keys tune up and down the dial,",
            "and Y speaks the station, signal, volume, and streamer-safe status.",
            "The Tab status menu includes a Radio screen listing receivable stations.",
            "The Freight Fate Roadhouse plays road music everywhere, day and night,",
            "and its host breaks in between songs.",
            "The Night Line does the same after dark, with quiet music",
            "and a calm late-night host.",
            "Fictional regional stations cover markets across the map with country,",
            "classic rock, and blues and soul formats and their own songs.",
            "Stations behave like real FM signals with realistic ranges:",
            "clear near their market, thinner with static crackle at the fringe,",
            "and gone past the edge of their coverage.",
            "When a station fades out completely, the radio says so and falls",
            "back to the Roadhouse instead of going silent.",
            "Real public streams, including AFN choices, stay hidden unless you",
            "enable real streams and turn streamer-safe mode off in settings.",
            "If a selected stream cannot play, the radio falls back safely.",
        ],
    ),
    (
        "Deliveries and money",
        [
            "The dispatch board lists freight for the current metro service area.",
            "A metro can contain ports, rail and intermodal ramps, air cargo areas,",
            "parcel hubs, grocery distribution centers, dry warehouses, cold storage,",
            "food processors, farms and grain elevators, manufacturing plants,",
            "steel and industrial sites, automotive suppliers, chemical terminals,",
            "construction yards, mines and quarries, lumber or paper facilities,",
            "cross-docks, and company yards.",
            "Each job names an origin facility and a destination facility.",
            "Cargo follows facility roles, so grain elevators ship different freight",
            "than parcel hubs, ports, warehouses, factories, or cold storage.",
            "Not every market supports every cargo equally.",
            "Regional freight patterns shape the board: ports see containers and bulk,",
            "agricultural regions see grain and food, industrial regions see steel,",
            "machinery, automotive, chemicals, lumber, and construction materials.",
            "Border and gateway metros often offer cross-dock logistics freight.",
            "New company hires see a single assigned load with accept and decline;",
            "the full browsable board opens at level 8.",
            "Press F1 on a dispatch to review its details line by line before deciding.",
            "Dispatch warns when a load may not fit your remaining legal hours.",
            "After accepting a dispatch, leave the terminal bobtail or with an empty trailer.",
            "Pickup legs are local deadhead moves to the origin facility.",
            "At the pickup gate, stop to open the facility menu.",
            "Check in, then load at the assigned dock.",
            "Loading requires the truck to be stopped.",
            "Once loaded and sealed, company drivers depart on dispatch's assigned route;",
            "owner-operators and own-authority drivers pick from the route options.",
            "GPS cues call out highway changes, state lines, places, and rest stops.",
            "Deliver before the deadline for a bonus. Late or damaged cargo pays less.",
            "At the destination facility, stop, then dock and deliver.",
            "Delivery settlement reports gross pay, carrier-paid or reimbursed charges,",
            "driver-responsibility charges, business operating charges, and net driver pay.",
            "After settlement, the truck is parked at the destination service-area terminal.",
            "Company-driver settlements pay wages and bonuses from carrier gross.",
            "Owner-operator and direct freight settlements pay higher gross revenue,",
            "but fuel, repairs, reserves, trailer costs, and fees come out of the business.",
            "Trailer requirements are listed on freight that needs special equipment.",
            "Fragile cargo, like electronics and fresh food, punishes rough driving.",
            "Repair your truck in the terminal garage. Damage reduces engine power.",
            "Normal miles also add tire wear and road grime for the garage to service.",
            "Demanding freight teaches more: specialty and premium cargo earn",
            "bonus experience, and a streak of on-time deliveries compounds it.",
            "Reputation pays continuously: company settlements add a dispatch",
            "trust bonus that grows as your reputation climbs above fifty.",
            "Higher levels widen distance caps, improve low-end pay,",
            "and unlock more facility variety plus refrigerated, heavy-haul, and high-value freight.",
            "Endorsement freight unlocks by level when the carrier sponsors the",
            "training, or earlier if you pay for the course at the terminal.",
            "Cargo markets drift day by day. The dispatch board calls out tight and loose",
            "markets; tight cargo pays well above the usual rate.",
        ],
    ),
    (
        "Markets and route coverage",
        [
            "Freight Fate focuses on major freight areas instead of every town.",
            "The highway map connects those areas with drivable long-haul routes.",
            "Freight variety comes from the facilities inside each area.",
            "A load may route from Chicago to Los Angeles, but the work can be",
            "an intermodal ramp, cold storage, port terminal, parcel hub, or plant.",
            "New dispatches use routes with enough stops to make fuel, rest,",
            "and hours planning playable.",
            "Some common facilities are representative locations for the area.",
            "They still behave like named places with clear cargo roles.",
        ],
    ),
    (
        "The garage",
        [
            "Every terminal garage refuels, repairs, services tires, and washes the active tractor.",
            "Normal miles add slow tire wear and road grime for the garage to service.",
            "Company-driver fuel and routine repairs use the carrier account.",
            "Owner-operators pay garage costs from their business cash.",
            "If an owner-operator cannot afford a full tank or full repair,",
            "the garage buys as much fuel or repair work as the money covers.",
            "The Upgrades menu unlocks after owner-operator status and sells an engine tune,",
            "an aerodynamic kit, a long-range tank, and reinforced brakes.",
            "Upgrades are fleet packages and apply to every tractor you own.",
            "Engine tune gives more pulling power for heavy freight, hills, and mountain grades.",
            "Aerodynamic kit burns less fuel at highway speed; same tank, fewer gallons per mile.",
            "Long-range tank carries fifty more gallons; more fuel onboard, not better efficiency.",
            "Reinforced brakes keep stopping power longer on descents and emergency stops.",
            "The Trucks menu is locked for company drivers, who use assigned equipment.",
            "Owner-operators can buy or switch owned tractors at the garage.",
            "The Trailers menu is carrier-provided for company drivers.",
            "Leased-on owner-operators can add trailer programs; own-authority drivers can buy trailers.",
        ],
    ),
]


def controls_help_page() -> int:
    """Index of the driving-keys page, so callers can open help straight to it."""
    for i, (title, _lines) in enumerate(HELP_PAGES):
        if title == "Driving information keys":
            return i
    return 0


class HelpState(State):
    """Page-by-page, line-by-line spoken manual."""

    def __init__(self, ctx, start_page: int = 0) -> None:
        super().__init__(ctx)
        self.page = max(0, min(start_page, len(HELP_PAGES) - 1))
        self.line = -1  # -1 = page title

    def enter(self) -> None:
        self.ctx.say(
            "How to play. Left and Right arrows change pages. Up and Down arrows "
            "read line by line. Enter reads the whole page. Left or Right Control "
            "stops the current speech. Escape goes back. " + self._page_title()
        )

    def _page_title(self) -> str:
        title, lines = HELP_PAGES[self.page]
        return f"Page {self.page + 1} of {len(HELP_PAGES)}: {title}. {len(lines)} lines."

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        title, lines = HELP_PAGES[self.page]
        if event.key == pygame.K_ESCAPE:
            self.ctx.audio.play("ui/menu_back")
            self.ctx.pop_state()
        elif event.key in (pygame.K_LCTRL, pygame.K_RCTRL):
            self.ctx.stop_speech()
        elif event.key in (pygame.K_RIGHT, pygame.K_PAGEDOWN):
            self.page = (self.page + 1) % len(HELP_PAGES)
            self.line = -1
            self.ctx.audio.play("ui/menu_move")
            self.ctx.say(self._page_title())
        elif event.key in (pygame.K_LEFT, pygame.K_PAGEUP):
            self.page = (self.page - 1) % len(HELP_PAGES)
            self.line = -1
            self.ctx.audio.play("ui/menu_move")
            self.ctx.say(self._page_title())
        elif event.key == pygame.K_DOWN:
            self.line = min(self.line + 1, len(lines) - 1)
            self.ctx.say(lines[self.line])
        elif event.key == pygame.K_UP:
            self.line = max(self.line - 1, 0)
            self.ctx.say(lines[self.line])
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.ctx.say(f"{title}. " + " ".join(lines))

    def lines(self) -> list[str]:
        title, lines = HELP_PAGES[self.page]
        out = [f"How to play - {title} ({self.page + 1}/{len(HELP_PAGES)})", ""]
        for i, text in enumerate(lines):
            out.append(("> " if i == self.line else "  ") + text)
        return out
