//! Touch gestures at the wheel: a slot gesture runs the command the player's
//! touch bindings give it, with no menu in between.

use crate::app::GameContext;
use crate::bindings::TouchCommand;
use crate::states::driving::DrivingState;
use crate::touch::Gesture;

impl DrivingState {
    /// `true` when `gesture` is a driving slot and ran (or deliberately did
    /// nothing); a fixed gesture is left to the key it stands for.
    ///
    /// Same contract as a key: a gesture is a request, so its answer may cut
    /// the line in progress.
    pub fn handle_touch_gesture(&mut self, ctx: &mut GameContext, gesture: Gesture) -> bool {
        let Some(command) = ctx.bindings.touch_command(gesture) else {
            return false;
        };
        let previous = ctx.player_asked_begin();
        match command {
            TouchCommand::Action(action) => self.run_key_action(ctx, action),
            TouchCommand::Pause => {
                ctx.audio.horn_stop();
                self.trip.truck.horn_on = false;
                self.push_pause_menu(ctx);
            }
            TouchCommand::Nothing => {}
        }
        ctx.player_asked_end(previous);
        true
    }
}
