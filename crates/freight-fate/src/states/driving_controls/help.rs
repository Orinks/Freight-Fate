//! F1: the driving layout, spoken for whichever device is in use.
//!
//! The two help texts are long, and they are player-facing word for word, so
//! each `push_str` below is one Python string literal from
//! `driving_controls.py`. Keeping the seams where Python put them is what
//! makes a wording change diffable against the reference implementation.

use crate::app::GameContext;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

impl DrivingState {
    /// `_objective_help()`.
    pub fn objective_help(&self, ctx: &GameContext) -> String {
        if self.phase == DRIVE_PHASE_PICKUP {
            return format!(
                "Your current objective is pickup: drive to {}, stop at the gate, then check in \
                 and load. ",
                self.pickup_facility_text(ctx)
            );
        }
        "Pickup and loading are complete. At your destination, stop, then dock and deliver. "
            .to_string()
    }

    /// `_speak_driving_help()`: keyboard or controller layout, following the
    /// device in use.
    pub fn speak_driving_help(&mut self, ctx: &mut GameContext) {
        self.note_instruction_demonstrated(ctx, "help");
        if ctx.controller.device() == "controller" {
            self.speak_controller_help(ctx);
        } else {
            self.speak_keyboard_help(ctx);
        }
    }

    /// `_speak_keyboard_help()`.
    pub fn speak_keyboard_help(&mut self, ctx: &mut GameContext) {
        let objective_help = self.objective_help(ctx);
        let automatic_help = if ctx.settings.automatic_direction_changes == "deliberate" {
            "In automatic with deliberate direction changes, brake to a stop, \
             then release the Down arrow and press and hold it again to shift \
             into reverse and back slowly. While reversing, hold the Up arrow \
             to brake to a stop, then release it and press and hold again to \
             shift back into forward. A quick tap just brakes. "
        } else {
            "In automatic with simple direction changes, brake to a stop, \
             release the Down arrow, then press and hold it again to shift into \
             reverse and back slowly. While reversing, brake with the Up arrow, \
             and once stopped, release and hold it again to shift back into \
             forward. Holding a brake through a stop just holds the truck. "
        };
        let latch_help = if ctx.settings.pedal_latch != "off" {
            "Tap the brake, then press again and hold half a second, to latch \
             it so it stays applied hands-free: a click and a spoken \
             confirmation mark the catch. Press Down arrow once to take it \
             back; the accelerator releases it instantly. The throttle key \
             never latches. "
        } else {
            ""
        };

        let mut text = String::new();
        text.push_str("Hold Up arrow to accelerate, Down arrow to brake. ");
        text.push_str(latch_help);
        text.push_str(automatic_help);
        text.push_str("Hold B for the emergency brake, the hardest possible stop. ");
        text.push_str("K starts automatic speed control. Adaptive cruise handles open ");
        text.push_str("roads and the speed keeper handles low-speed zones, switching ");
        text.push_str("automatically between them. Bad weather increases the following ");
        text.push_str("gap, and both read the road ahead: cruise eases early for a sharp ");
        text.push_str("posted-limit drop, the keeper for the next turn or the next lower ");
        text.push_str("limit, and the corner call adds Speed keeper easing when it is ");
        text.push_str("taking the turn. ");
        text.push_str("Braking cancels the whole session. At the planned pickup, it pauses while ");
        text.push_str("you check in and load, then resumes once you depart and get rolling. ");
        text.push_str("Plus and minus, including the keypad keys, raise and lower the ");
        text.push_str("remembered open-road target by five, so you can dial it up to the ");
        text.push_str("speed you want; it will not hold above the posted limit. ");
        text.push_str("Control with plus or minus moves it by one mile per hour. ");
        text.push_str("Shift K resumes the last cruise speed after braking canceled it, ");
        text.push_str("like a car's resume button. ");
        text.push_str("Parked with the brake set, K latches a high idle instead -- the ");
        text.push_str("engine holds a faster idle to warm up and build air sooner, plus ");
        text.push_str("and minus adjust it, and releasing the parking brake drops it. ");
        text.push_str("X signals for the next announced route exit, called out by its ");
        text.push_str("number when known, or cancels that signal. Prepare early: slow ");
        text.push_str("to 45 for the ramp, hold the exit ");
        text.push_str("lane unless lane keeping assistance is on full, and the truck takes ");
        text.push_str("the ramp ");
        text.push_str("when your setup is valid. Ramps usually end at a traffic light ");
        text.push_str("or stop sign, called out on the way down; stop for red or the ");
        text.push_str("sign, then pull ahead. X also signals a pull-over if a ");
        text.push_str("trooper lights you up for speeding, scale bypass, or unsafe ");
        text.push_str("equipment: signal, then brake to a stop. Ignoring the lights ");
        text.push_str("gives staged failure-to-stop warnings, then a felony stop ");
        text.push_str("that can cancel the active load. ");
        text.push_str("C also speaks the date and season. ");
        text.push_str("M toggles the in-cab radio. Page Down tunes to the next station ");
        text.push_str("and Page Up to the previous; the semicolon and apostrophe keys ");
        text.push_str("still work. ");
        text.push_str("With Control the tuning keys jump a whole category. With Shift ");
        text.push_str("they change the radio volume instead, in 10 percent steps, up ");
        text.push_str("on Page Up or Shift semicolon and down on Page Down or Shift ");
        text.push_str("apostrophe, whether the radio is on or off. ");
        text.push_str("O saves or unsaves the ");
        text.push_str("current station as a favorite, ");
        text.push_str("and Y speaks radio station, volume, and streamer-safe status. ");
        text.push_str("Shift and Y speaks the song the station is playing, when it ");
        text.push_str("says. The Driver apps tablet has a Radio app to search the ");
        text.push_str("whole dial, tune a station by name, and keep your favorites. ");
        text.push_str("The Tab status menu includes a radio screen with the currently ");
        text.push_str("receivable stations. ");
        text.push_str("E starts the engine, and stops it only below 5 miles per hour. ");
        text.push_str("Air pressure must build before the truck can move. ");
        text.push_str("Press P to release or set the parking brake; if pressure is ");
        text.push_str("below 100 psi, wait with the engine running. ");
        text.push_str(&objective_help);
        text.push_str("Space speed, active speed-control mode, and target. ");
        text.push_str("S posted speed limit. G the grade under the wheels, whether the ");
        text.push_str("truck is holding it, and the next grade ahead. Tab status menu. F fuel. ");
        text.push_str("C clock, deadline, and the hours limit that comes first. ");
        text.push_str("Three keys answer one hours question each, without the rest of ");
        text.push_str("that report: Alt A time at the wheel so far, Alt S when your ");
        text.push_str("30 minute break is due, and Alt D what ends this shift, with ");
        text.push_str("where you can legally stop before it. ");
        text.push_str("R progress, distance left, and where you are. ");
        text.push_str("Four keys answer one part of that each, when you want the fact ");
        text.push_str("without the sentence: Alt 1 the state you are in, Alt 2 the road ");
        text.push_str("you are on, Alt 3 the town you are in or the nearest one, and ");
        text.push_str("Alt 4 the direction you are travelling. The keypad numbers work ");
        text.push_str("the same way. ");
        text.push_str("V weather. L lane position, and whether the lane beside you is ");
        text.push_str("open. After a pass, the truck also says when the lane you came ");
        text.push_str("out of is clear again. I turns the lane locator on and off: a ");
        text.push_str("soft tock once a beat, panned to where you sit inside your lane, ");
        text.push_str("running until you turn it off, on lane keeping partial or off. ");
        text.push_str("A repeats the last driving announcement. ");
        text.push_str("Alt C repeats the last CB chatter on its own, in case something ");
        text.push_str("else was said over the top of it, and gives the distance as it ");
        text.push_str("is now rather than the one you first heard. ");
        text.push_str(
            "Comma repeats what was just said and keeps stepping back, and Period moves \
             forward again. ",
        );
        text.push_str("Control with Comma or Period jumps to the oldest or newest message. ");
        text.push_str(
            "The bracket keys switch between all messages, general messages, and driving \
             events. ",
        );
        text.push_str("Control C copies the message you are on. ");
        text.push_str("U reads the road ahead that no other key answers: the ramp ");
        text.push_str("control coming up, the next imposed limit, the next stop, and ");
        text.push_str("the next bend that demands slowing. ");
        text.push_str("Curves that demand slowing are called before they arrive, ");
        text.push_str("like Sharp left, half a mile, advise 35; D folds the bend ");
        text.push_str("into its one safe-speed number. ");
        text.push_str("The Tab status menu includes a Driver apps tablet menu for ");
        text.push_str("navigation, weather, traffic, truck stops, road chatter, and ELD. ");
        text.push_str("Left or Right Control stops the driving event voice. ");
        text.push_str("Left and Right arrows steer unless lane keeping assistance is on ");
        text.push_str("full; steer across the lane line to change lanes. On full, tap ");
        text.push_str("Left or Right to change lanes instead. Exits leave from the ");
        text.push_str("right lane. Hazards called out as brake or change lanes are ");
        text.push_str("fixed objects in your lane: dodge with a clear lane beside ");
        text.push_str("you, or brake nearly to a stop and ease around. ");
        text.push_str("T plans the next nearby sleep-capable stop while rolling, then X ");
        text.push_str("signals for its exit. When already stopped at a route stop, T opens ");
        text.push_str("its menu: available actions may include fuel, break, sleep, ");
        text.push_str("inspect, roadside assistance, or save when source-backed. Fully ");
        text.push_str("stopped away from route points, T opens the emergency shoulder-sleep ");
        text.push_str("warning instead. H horn. ");
        text.push_str("J engine brake; on an automatic it manages its own stage to hold ");
        text.push_str("your speed, and 1, 2, 3 take manual control. Alt J chooses ");
        text.push_str("whether J runs the automatic mode. Alt T switches between ");
        text.push_str("automatic and manual shifting. Escape pause menu. ");
        if !self.trip.truck.transmission.automatic {
            text.push_str(
                "Hold Left Shift for clutch, then W to shift up or Q to shift down, \
                 Backspace for reverse, N for neutral.",
            );
        }
        ctx.say(&text);
    }

    /// `_speak_controller_help()`: controller layout help, spoken from the
    /// Back button or F1 on a pad.
    pub fn speak_controller_help(&mut self, ctx: &mut GameContext) {
        let manual = !self.trip.truck.transmission.automatic;
        let gears = if manual {
            "The A button shifts up a gear and the X button shifts down, while \
             you hold the left bumper for the clutch. "
        } else if ctx.settings.automatic_direction_changes == "deliberate" {
            "In automatic with deliberate direction changes, brake to a stop, \
             then let the left trigger return to neutral and press and hold it \
             again to shift into reverse and back slowly. While reversing, hold \
             the right trigger to brake to a stop, then let it return to \
             neutral and press and hold again to shift back into forward. A \
             quick tap just brakes. "
        } else {
            "In automatic with simple direction changes, brake to a stop, let \
             the left trigger return to neutral, then press and hold it again to \
             shift into reverse and back slowly. While reversing, brake with the \
             right trigger, and once stopped, release and press it again to \
             shift back into forward. Holding a brake through a stop just holds \
             the truck. "
        };
        let objective_help = self.objective_help(ctx);

        let mut text = String::new();
        text.push_str("Right trigger is the gas, left trigger the brake; press the left ");
        text.push_str("trigger fully for the hardest stop. The left stick steers unless lane ");
        text.push_str("keeping assistance is on full. ");
        text.push_str(gears);
        text.push_str("The Y button starts automatic speed control, switching between ");
        text.push_str("adaptive cruise and the low-speed keeper as needed. Hold the right ");
        text.push_str("bumper and press D-pad left or right to lower or raise the open-road ");
        text.push_str("cruise target by five. It pauses through the planned pickup and ");
        text.push_str("resumes once the loaded truck is rolling. Parked with the brake ");
        text.push_str("set, the Y button latches a high idle instead. ");
        text.push_str("D-pad down signals for the next announced exit, or signals a ");
        text.push_str("pull-over when a trooper lights you up. ");
        text.push_str("D-pad up reads your route and current location, D-pad left the ");
        text.push_str("weather, D-pad right the clock with your full hours of service; ");
        text.push_str("the keyboard's Alt A, Alt S, and Alt D split those hours into one ");
        text.push_str("answer each. The B button speaks your speed. ");
        text.push_str("Click the left stick to honk, ");
        text.push_str("the right stick to toggle the engine brake. ");
        text.push_str("Hold the right bumper for the second layer: plus A starts or stops ");
        text.push_str("the engine, plus B reads fuel, plus X reads the posted speed limit ");
        text.push_str("here and how far over you are, plus Y sets or releases the parking ");
        text.push_str("brake, plus D-pad up reads the next listed exit, plus D-pad down ");
        text.push_str("plans a nearby sleep stop while rolling or opens its actions when ");
        text.push_str("stopped at it; away from route points while fully stopped, it opens ");
        text.push_str("emergency shoulder sleep. Plus Start opens the status menu. ");
        text.push_str("Start pauses and unpauses. The Back button stops the driving voice ");
        text.push_str("while it is speaking, the way Left or Right Control does on the ");
        text.push_str("keyboard; when nothing is being said, it repeats this help. ");
        text.push_str(&objective_help);
        ctx.say(&text);
    }
}
