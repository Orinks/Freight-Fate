//! `handle_event` / `_handle_key`: the whole discrete keyboard table at the
//! wheel, plus the assist-off tap lane change the arrows fall back to.

use crate::app::GameContext;
use crate::states::base::{InputEvent, Key};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

use super::{place_fact, PlaceFact};

impl DrivingState {
    /// `handle_event(event)`.
    ///
    /// Everything spoken from here down is an answer to a key the player
    /// pressed, so it may cut the line in progress even though unasked-for
    /// lines queue at the wheel. See `GameContext::player_asked`.
    pub fn handle_key_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        let previous = ctx.player_asked_begin();
        self.handle_key(ctx, event);
        ctx.player_asked_end(previous);
    }

    /// `_handle_key(event)`: the table itself, in source order.
    ///
    /// The order is load-bearing in three places and is reproduced exactly:
    /// `Alt` with a number is checked BEFORE the jake stages, the `+`/`-`
    /// keys fall back to the typed character, and the radio dial reads Ctrl
    /// before Shift so `Ctrl+Shift` still jumps a category.
    pub(crate) fn handle_key(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        if let InputEvent::KeyUp { key: Key::H, .. } = event {
            ctx.audio.horn_stop();
            self.trip.truck.horn_on = false;
            return;
        }
        let Some((key, mods, text)) = event.key_down() else {
            return;
        };

        let automatic = self.trip.truck.transmission.automatic;
        if !automatic && mods.shift {
            self.trip.truck.transmission.clutch = 1.0;
        }
        let plus = matches!(key, Key::Equals | Key::Plus | Key::KpPlus) || text == Some('+');
        let minus = matches!(key, Key::Minus | Key::KpMinus) || text == Some('-');

        if matches!(key, Key::LCtrl | Key::RCtrl) {
            ctx.stop_event_speech();
            self.note_critical_speech_stopped();
            self.set_status("Event voice stopped.");
        } else if key == Key::Escape {
            ctx.audio.horn_stop();
            self.trip.truck.horn_on = false;
            self.push_pause_menu(ctx);
        } else if key == Key::E {
            self.toggle_engine(ctx);
        } else if key == Key::N && !automatic {
            let result = self.trip.truck.transmission.request_gear(0);
            if result.ok {
                ctx.audio
                    .play_bank("vehicle/shift_manual", "vehicle/gear_shift");
                ctx.say("Neutral.");
            }
        } else if key == Key::Backspace && !automatic {
            self.manual_shift(ctx, REVERSE);
        } else if key == Key::W && !automatic {
            let tr = &self.trip.truck.transmission;
            if tr.in_reverse() || tr.in_neutral() {
                self.manual_shift(ctx, 1);
            } else if tr.gear < 10 {
                let next = tr.gear + 1;
                self.manual_shift(ctx, next);
            }
        } else if key == Key::Q
            && !automatic
            && !self.trip.truck.transmission.in_neutral()
            && self.trip.truck.transmission.gear > 1
        {
            let next = self.trip.truck.transmission.gear - 1;
            self.manual_shift(ctx, next);
        } else if key == Key::J {
            if mods.alt {
                self.toggle_auto_jake_enabled(ctx);
            } else {
                self.toggle_engine_brake(ctx);
            }
        } else if let (Some(fact), true) = (place_fact(key), mods.alt) {
            // Checked ahead of the jake stages on purpose: Alt with a number
            // used to fall through to them, so a driver reaching for "what
            // state am I in" changed the engine brake instead.
            match fact {
                PlaceFact::State => self.speak_current_state(ctx),
                PlaceFact::Road => self.speak_current_road(ctx),
                PlaceFact::Town => self.speak_current_town(ctx),
                PlaceFact::Direction => self.speak_current_direction(ctx),
            }
        } else if matches!(key, Key::Num1 | Key::Num2 | Key::Num3) {
            let stage = match key {
                Key::Num1 => 1,
                Key::Num2 => 2,
                _ => 3,
            };
            self.select_jake_stage(ctx, stage);
        } else if key == Key::P {
            self.toggle_parking_brake(ctx);
        } else if key == Key::H {
            ctx.audio.horn_start();
            self.trip.truck.horn_on = true;
            self.horn_scare_animals(ctx);
        } else if key == Key::T {
            if mods.alt {
                // The AMT's manual-mode button: flips the transmission
                // setting; the existing manual shift controls take over.
                ctx.settings.automatic_transmission = !ctx.settings.automatic_transmission;
            } else {
                self.try_rest_stop(ctx);
            }
        } else if key == Key::X {
            if self.pull_over.is_some() {
                self.signal_pull_over(ctx);
            } else {
                self.take_exit(ctx);
            }
        } else if key == Key::K {
            if mods.shift {
                self.resume_cruise(ctx);
            } else {
                self.toggle_cruise(ctx);
            }
        } else if plus {
            self.adjust_cruise(ctx, 1, mods.ctrl);
        } else if minus {
            self.adjust_cruise(ctx, -1, mods.ctrl);
        } else if key == Key::Left && ctx.settings.lane_is_automated() {
            self.tap_lane_change(ctx, 1);
        } else if key == Key::Right && ctx.settings.lane_is_automated() {
            self.tap_lane_change(ctx, -1);
        } else if key == Key::Space {
            self.speak_speed(ctx);
        } else if matches!(key, Key::Return | Key::KpEnter) {
            if self.arrival_full_stop_said && self.trip.truck.speed_mph() <= 0.5 {
                self.open_facility_arrival(ctx);
            }
        } else if key == Key::Tab {
            self.push_driving_status(ctx);
        } else if key == Key::F {
            self.speak_fuel(ctx);
        } else if key == Key::C {
            if mods.alt {
                // C for the CB, on the Alt layer that already answers one
                // narrow question at a time (Alt A/S/D hours, Alt 1 to 4
                // place). Plain C stays the clock, the same way plain S, D,
                // A, J and T keep theirs.
                self.speak_last_cb_chatter(ctx);
            } else {
                self.speak_clock(ctx, false);
            }
        } else if key == Key::R {
            // Shift+R used to read the next listed exit. Removed 2026-08-17:
            // the exit list is reference material the drive never asks the
            // player to act on, and it stays reachable on the status screen,
            // which is where reference material belongs. R answers the same
            // thing shifted or not, so a stray Shift is not silence.
            self.speak_route_status(ctx);
        } else if key == Key::V {
            self.speak_weather(ctx);
        } else if key == Key::L {
            let text = self.lane_status_text();
            ctx.say(&text);
        } else if key == Key::S {
            if mods.alt {
                self.speak_hos_break(ctx);
            } else {
                self.speak_speed_limit(ctx);
            }
        } else if key == Key::D {
            if mods.alt {
                self.speak_hos_drive_left(ctx);
            } else {
                self.speak_safe_speed(ctx);
            }
        } else if key == Key::A {
            if mods.alt {
                self.speak_hos_wheel_time(ctx);
            } else {
                self.speak_last_announcement(ctx);
            }
        } else if key == Key::G {
            self.speak_grade(ctx);
        } else if key == Key::I {
            self.toggle_lane_locator(ctx);
        } else if key == Key::U {
            self.speak_upcoming(ctx, 15.0);
        } else if key == Key::M {
            self.toggle_radio(ctx);
        } else if key == Key::O {
            self.toggle_radio_favorite(ctx);
        } else if matches!(key, Key::PageUp | Key::Semicolon) {
            // Page Down walks to the next station, Page Up to the previous,
            // matching the help browser's Page Up and Page Down paging; with
            // Ctrl they leap a whole category (25 AFN stations in a row buried
            // terrestrial for a linear tune). Semicolon and apostrophe stay as
            // secondary dial keys: Page keys are Fn chords on many laptops and
            // missing on 60 percent keyboards, and there is no key remapping.
            // The dial originally lived on the brackets, which message review
            // now uses to switch categories. Shift raises or lowers the radio
            // volume instead of tuning (Jerry's request) -- checked only when
            // Ctrl is absent, so Ctrl+Shift still falls through to Ctrl's own
            // category jump exactly as it did before Shift existed.
            if mods.ctrl {
                self.jump_radio_category(ctx, -1);
            } else if mods.shift {
                self.adjust_radio_volume(ctx, 1);
            } else {
                self.tune_radio(ctx, -1);
            }
        } else if matches!(key, Key::PageDown | Key::Quote) {
            if mods.ctrl {
                self.jump_radio_category(ctx, 1);
            } else if mods.shift {
                self.adjust_radio_volume(ctx, -1);
            } else {
                self.tune_radio(ctx, 1);
            }
        } else if key == Key::Y {
            if mods.shift {
                self.speak_radio_now_playing(ctx);
            } else {
                self.speak_radio_status(ctx);
            }
        } else if key == Key::F1 {
            self.speak_driving_help(ctx);
        }
    }

    /// `_tap_lane_change(direction)`.
    ///
    /// Assist-off lane change: a timed drift across the line, +1 moves left,
    /// -1 moves right. With steering assist on, the held wheel does this
    /// instead, so the tap handler never runs there.
    pub fn tap_lane_change(&mut self, ctx: &mut GameContext, direction: i64) {
        if self.microsleep_deadline.is_some() {
            return; // the held-key wake-up check owns the arrows right now
        }
        if self.ramp_mi.is_some() {
            ctx.say("You are on the exit ramp. No lanes to change.");
            return;
        }
        if self.lane_change_target.is_some() {
            ctx.say("Still changing lanes.");
            return;
        }
        if !self.trip.truck.engine_on || self.trip.truck.speed_mph() < LANE_MIN_MPH {
            let minimum = ctx.settings.speed_text(LANE_MIN_MPH);
            ctx.say(&format!(
                "Lane changes need the engine running and at least {minimum}."
            ));
            return;
        }
        let lane_count = self.lane.lane_count;
        let target = self.lane.lane + direction;
        if !(0..lane_count).contains(&target) {
            // Answer the side that was asked for. Naming the lane the driver
            // is already in ("you are already in the right lane") is no answer
            // at all to someone asking to go left.
            let side = if direction > 0 { "left" } else { "right" };
            ctx.say(&format!("There is no lane to your {side} here."));
            return;
        }
        // The taper counts: that is where the lane is closing, and letting a
        // driver move into it there is how they ended up inside the cones.
        // Asked of the trip so a jam laid over the roadwork cannot hide the
        // closure, and so the answer follows a road that widens or narrows.
        if Some(target) == self.trip.closed_lane_at(None, Some(lane_count)) {
            let closure = self.trip.active_closure(None);
            let name = lane_label(target, lane_count);
            let closing = closure.is_some_and(|zone| zone.reason != "construction");
            ctx.audio.play("ui/error");
            if closing {
                ctx.say(&format!("The {name} lane closes at the work zone ahead."));
            } else {
                ctx.say(&format!("The {name} lane is closed here."));
            }
            return;
        }
        self.lane_change_target = Some(target);
        self.lane_change_timer = LANE_TAP_CHANGE_S;
        self.lane_signal_timer = 0.0;
        let pan = if direction > 0 { -0.6 } else { 0.6 };
        ctx.audio.play_with("vehicle/signal_tone", 0.8, pan);
        ctx.say(&format!(
            "Changing to the {} lane.",
            lane_label(target, lane_count)
        ));
    }
}
