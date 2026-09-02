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
                "Pickup: drive to {}, stop at the gate, check in and load. ",
                self.pickup_facility_text(ctx)
            );
        }
        "At your destination, stop, then dock and deliver. ".to_string()
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
            "In automatic with deliberate direction changes, stop, release the \
             Down arrow, then press and hold it again to reverse. While \
             reversing, stop with the Up arrow, release, then press and hold \
             again for forward. A quick tap just brakes. "
        } else {
            "In automatic with simple direction changes, stop, release the Down \
             arrow, then press and hold it again to reverse. While reversing, \
             stop with the Up arrow, release, then hold it again for forward. A \
             brake held through a stop just holds the truck. "
        };
        let latch_help = if ctx.settings.pedal_latch != "off" {
            "Tap the brake, then press again and hold half a second to latch it \
             hands-free; a click and a spoken confirmation mark the catch. Down \
             arrow once releases it; the accelerator releases it instantly. The \
             throttle key never latches. "
        } else {
            ""
        };

        let mut text = String::new();
        text.push_str("Hold Up arrow to accelerate, Down arrow to brake. ");
        text.push_str(latch_help);
        text.push_str(automatic_help);
        text.push_str("Hold B for the emergency brake, the hardest possible stop. ");
        text.push_str("K starts automatic speed control: adaptive cruise on open roads, ");
        text.push_str("the speed keeper in low-speed zones. Weather widens the gap. ");
        text.push_str("Cruise eases early for a sharp posted-limit drop, the keeper for ");
        text.push_str("the next turn or the next lower limit. ");
        text.push_str("Braking cancels the session. At the planned pickup it pauses and ");
        text.push_str("resumes once you depart. ");
        text.push_str("Plus and minus, including the keypad keys, change the open-road ");
        text.push_str("target by five; it never holds above the posted limit. Control ");
        text.push_str("with plus or minus, by one. ");
        text.push_str("Shift K resumes the last cruise speed. ");
        text.push_str("Parked with the brake set, K latches a high idle; plus and minus ");
        text.push_str("adjust it, and releasing the parking brake drops it. ");
        text.push_str("X signals for the next announced route exit, by number when ");
        text.push_str("known, or cancels that signal. Slow to 45 for the ramp and hold ");
        text.push_str("the exit lane unless lane keeping is on full. Ramps usually end ");
        text.push_str("at a traffic light or stop sign, called out on the way down. X ");
        text.push_str("also signals a pull-over when a trooper lights you up for speeding, ");
        text.push_str("a scale bypass, or unsafe equipment: signal, then brake to a stop. ");
        text.push_str("Ignoring the lights brings failure-to-stop ");
        text.push_str("warnings, then a stop that cancels the load: a major offense. ");
        text.push_str("C also speaks the date and season. ");
        text.push_str("M toggles the in-cab radio. Page Down tunes to the next station, ");
        text.push_str("Page Up to the previous; semicolon and apostrophe do the same. ");
        text.push_str("Control with the tuning keys jumps a category; Shift changes the ");
        text.push_str("radio volume in 10 percent steps, on or off. ");
        text.push_str("O saves or unsaves the station as a favorite. ");
        text.push_str("Y speaks station, volume, and streamer-safe status; Shift Y speaks ");
        text.push_str("the song when the station says. The Driver apps tablet has a ");
        text.push_str("Radio app to search the dial, tune by name, and keep favorites; ");
        text.push_str("the Tab status menu has a radio screen of receivable stations. ");
        text.push_str("E starts the engine, and stops it only below 5 miles per hour. ");
        text.push_str("Air pressure must build before the truck can move. ");
        text.push_str("P sets or releases the parking brake. It needs 100 psi of air. ");
        text.push_str(&objective_help);
        text.push_str("Space speed, active speed-control mode, and target. ");
        text.push_str("S posted speed limit. G the grade under the wheels, whether the ");
        text.push_str("truck is holding it, and the next grade ahead. Tab status menu. F fuel. ");
        text.push_str("C clock, deadline, and the hours limit that comes first. ");
        text.push_str("Alt A time at the wheel so far, Alt S when your 30 minute break ");
        text.push_str("is due, Alt D what ends this shift and where you can legally stop ");
        text.push_str("before it. ");
        text.push_str("R progress, distance left, and where you are. ");
        text.push_str("Alt 1 the state, Alt 2 the road, Alt 3 the town or the nearest ");
        text.push_str("one, Alt 4 the direction. The keypad numbers work the same way. ");
        text.push_str("V weather. L lane position and whether the lane beside you is ");
        text.push_str("open. I turns the lane locator on and off: a soft tock once a ");
        text.push_str("beat, panned to where you sit in your lane, on lane keeping ");
        text.push_str("partial or off. ");
        text.push_str("A repeats the last driving announcement. ");
        text.push_str("Alt C repeats the last CB chatter, with the distance as it is now. ");
        text.push_str(
            "Comma repeats what was just said and keeps stepping back; Period moves \
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
        text.push_str("Bends that demand slowing are called before they arrive, like ");
        text.push_str("Sharp left, half a mile, advise 35; D gives one safe-speed number ");
        text.push_str("with the bend in it. ");
        text.push_str("The Tab status menu includes a Driver apps tablet for navigation, ");
        text.push_str("weather, traffic, truck stops, road chatter, and ELD. ");
        text.push_str("Left or Right Control stops the driving event voice. ");
        text.push_str("Left and Right arrows steer unless lane keeping is on full; steer ");
        text.push_str("across the lane line to change lanes. On full, tap Left or Right. ");
        text.push_str("Exits leave from the right lane. Change lanes or brake means a ");
        text.push_str("fixed object in your lane: take the open lane it names, or brake ");
        text.push_str("nearly to a stop and ease around. ");
        text.push_str("T plans the next nearby sleep-capable stop while rolling, then X ");
        text.push_str("signals for its exit. Stopped at a route stop, T opens its menu: ");
        text.push_str("fuel, break, sleep, inspect, roadside assistance, or save where ");
        text.push_str("available. Fully stopped away from route points, T opens the ");
        text.push_str("emergency shoulder-sleep warning instead. H horn. ");
        text.push_str("J engine brake; on an automatic it manages its own stage, and 1, ");
        text.push_str("2, 3 take manual control. Alt J chooses whether J runs the ");
        text.push_str("automatic mode. Alt T switches between automatic and manual ");
        text.push_str("shifting. Escape pause menu. ");
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
            "Hold the left bumper for the clutch; the A button shifts up a gear, \
             the X button shifts down. "
        } else if ctx.settings.automatic_direction_changes == "deliberate" {
            "In automatic with deliberate direction changes, stop, let the left \
             trigger return to neutral, then press and hold it again to reverse. \
             While reversing, stop with the right trigger, let it return to \
             neutral, then press and hold again for forward. A quick tap just \
             brakes. "
        } else {
            "In automatic with simple direction changes, stop, let the left \
             trigger return to neutral, then press and hold it again to reverse. \
             While reversing, stop with the right trigger, release, then press it \
             again for forward. A brake held through a stop just holds the truck. "
        };
        let objective_help = self.objective_help(ctx);

        let mut text = String::new();
        text.push_str("Right trigger is the gas, left trigger the brake; the left trigger ");
        text.push_str("fully in is the hardest stop. The left stick steers unless lane ");
        text.push_str("keeping is on full. ");
        text.push_str(gears);
        text.push_str("The Y button starts automatic speed control: adaptive cruise on ");
        text.push_str("open roads, the speed keeper in low-speed zones. Hold the right ");
        text.push_str("bumper and press D-pad left or right to change the open-road ");
        text.push_str("target by five. It pauses through the planned pickup and resumes ");
        text.push_str("once the loaded truck is rolling. Parked with the brake set, the ");
        text.push_str("Y button latches a high idle. ");
        text.push_str("D-pad down signals for the next announced exit, or a pull-over ");
        text.push_str("when a trooper lights you up. ");
        text.push_str("D-pad up reads your route and current location, D-pad left the ");
        text.push_str("weather, D-pad right the clock with your full hours of service. ");
        text.push_str("The B button speaks your speed. ");
        text.push_str("Click the left stick for the horn, the right stick for the engine brake. ");
        text.push_str("Hold the right bumper for the second layer: plus A starts or stops ");
        text.push_str("the engine, plus B reads fuel, plus X reads the posted speed limit ");
        text.push_str("here and how far over you are, plus Y sets or releases the parking ");
        text.push_str("brake, plus D-pad up reads the next listed exit, plus D-pad down ");
        text.push_str("plans a nearby sleep stop while rolling or opens its actions when ");
        text.push_str("stopped at it; away from route points while fully stopped, it opens ");
        text.push_str("emergency shoulder sleep. Plus Start opens the status menu. ");
        text.push_str("Start pauses and unpauses. The Back button stops the driving voice ");
        text.push_str("while it is speaking; when nothing is being said, it repeats this help. ");
        text.push_str(&objective_help);
        ctx.say(&text);
    }
}
