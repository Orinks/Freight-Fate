//! The pad at the wheel: the plain button layer, the right-bumper modified
//! layer, and what happens when the controller is unplugged mid-drive.

use crate::app::GameContext;
use crate::controller::ControllerButton;
use crate::states::base::InputEvent;
use crate::states::driving::DrivingState;

impl DrivingState {
    /// `handle_controller(event, manager)`.
    ///
    /// Same contract as the keyboard: a pad button is a request too, and the
    /// pad is the device where not being able to cut speech hurt most.
    pub fn handle_controller_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        let previous = ctx.player_asked_begin();
        self.handle_controller_button(ctx, event);
        ctx.player_asked_end(previous);
    }

    /// `_handle_controller_button(event, manager)`.
    pub(crate) fn handle_controller_button(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        let button = match event {
            InputEvent::ControllerButtonUp { button, .. } => {
                if *button == ControllerButton::LeftStick {
                    ctx.audio.horn_stop();
                }
                self.trip.truck.horn_on = false; // release L3 to stop the horn
                return;
            }
            InputEvent::ControllerButtonDown { button, .. } => *button,
            _ => return,
        };
        if ctx.controller.modifier {
            self.handle_controller_modified(ctx, button);
            return;
        }
        match button {
            ControllerButton::A => {
                if self.arrival_full_stop_said && self.trip.truck.speed_mph() <= 0.5 {
                    self.open_facility_arrival(ctx);
                } else {
                    self.shift_relative(ctx, 1);
                }
            }
            ControllerButton::X => self.shift_relative(ctx, -1),
            ControllerButton::B => self.speak_speed(ctx),
            ControllerButton::Y => self.toggle_cruise(ctx),
            ControllerButton::Start => {
                ctx.audio.horn_stop();
                self.trip.truck.horn_on = false;
                self.push_pause_menu(ctx);
            }
            ControllerButton::LeftStick => {
                ctx.audio.horn_start();
                self.trip.truck.horn_on = true;
                self.horn_scare_animals(ctx);
            }
            ControllerButton::RightStick => self.toggle_engine_brake(ctx),
            ControllerButton::DPadUp => self.speak_route_status(ctx),
            ControllerButton::DPadDown => {
                if self.pull_over.is_some() {
                    self.signal_pull_over(ctx);
                } else {
                    self.take_exit(ctx);
                }
            }
            ControllerButton::DPadLeft => self.speak_weather(ctx),
            // A pad has no room for the three keyboard hours keys, so this one
            // keeps the whole hours-of-service report it always spoke.
            ControllerButton::DPadRight => self.speak_clock(ctx, true),
            ControllerButton::Back => {
                // The pad had no way to stop the event voice at all -- every
                // other button is bound, and Ctrl is a keyboard key -- so a
                // controller-only driver had to reach for the keyboard to
                // silence an announcement (Sarah R., 2026-08-16). Back stops
                // it while it is speaking and keeps reading help when it is
                // not: pressing Back mid-flood used to answer a driver who
                // wanted quiet with a paragraph of help.
                if ctx.event_voice_busy() {
                    ctx.stop_event_speech();
                    self.note_critical_speech_stopped();
                    self.set_status("Event voice stopped.");
                } else {
                    self.speak_controller_help(ctx);
                }
            }
            _ => {}
        }
    }

    /// `_handle_controller_modified(button)`: secondary bindings while the
    /// right bumper (modifier) is held.
    pub(crate) fn handle_controller_modified(
        &mut self,
        ctx: &mut GameContext,
        button: ControllerButton,
    ) {
        match button {
            // Was the next listed exit, the pad's twin of Shift+R, and goes
            // with it (2026-08-17). Route status instead, so the pad keeps an
            // answer here rather than a dead button -- and so a pad driver is
            // not left with a binding the keyboard no longer has.
            ControllerButton::DPadUp => self.speak_route_status(ctx),
            ControllerButton::DPadDown => self.try_rest_stop(ctx),
            ControllerButton::DPadLeft => self.adjust_cruise(ctx, -1, false),
            ControllerButton::DPadRight => self.adjust_cruise(ctx, 1, false),
            ControllerButton::A => self.toggle_engine(ctx),
            ControllerButton::B => self.speak_fuel(ctx),
            // The pad had no answer to "what is the limit here" at all, so a
            // controller-only driver had to reach for the keyboard's S to ask
            // the one question enforcement acts on (Sarah R., 2026-08-16).
            ControllerButton::X => self.speak_speed_limit(ctx),
            ControllerButton::Y => self.toggle_parking_brake(ctx),
            ControllerButton::RightStick => self.cycle_jake_stage(ctx),
            ControllerButton::Start => self.push_driving_status(ctx),
            _ => {}
        }
    }

    /// `on_controller_disconnect()`.
    ///
    /// Pause so an unplugged pad mid-drive does not leave the truck rolling.
    pub fn handle_controller_disconnect(&mut self, ctx: &mut GameContext) {
        ctx.audio.horn_stop();
        self.trip.truck.horn_on = false;
        self.push_pause_menu(ctx);
    }
}
