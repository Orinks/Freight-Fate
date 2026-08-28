//! `_update_pedal_latches`: the per-frame half of the control surface.
//!
//! Called once per frame from `update()` with the raw pedal inputs, so it
//! lives with the controls rather than with the update loop that calls it.

use ff_core::sim::pedal_latch::LatchEvent;
use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;

impl DrivingState {
    /// Advance the brake latch and blend it into the pedal state.
    ///
    /// The throttle key never latches: at a standstill it is only for moving
    /// and for the direction-change hold. A latched throttle used to catch
    /// half a second into that hold (against a six-tenth shift) and trap
    /// the truck in reverse, including when the driver pumped the pedal.
    ///
    /// Called once per frame from `update()` with the raw pedal inputs;
    /// returns the effective `key_down` the rest of the frame drives on.
    /// The catch clicks (its own sound, not the gear click) and both
    /// latch and release speak. The opposite pedal always releases a latch
    /// instantly. A latched brake still wins over a pending reverse shift:
    /// latching a pedal means "hold this", never "change direction".
    pub fn update_pedal_latches(
        &mut self,
        ctx: &mut GameContext,
        key_up: bool,
        key_down: bool,
        pad_throttle: f64,
        dt: f64,
    ) -> bool {
        if ctx.settings.pedal_latch == "off" {
            if self.brake_latch.release() {
                self.say_latch(ctx, "Brake released.");
            }
            return key_down;
        }
        match self.brake_latch.update(key_down, dt) {
            Some(LatchEvent::Latched) => {
                // The latch gesture's second press is also a press-and-hold
                // at whatever speed the truck has -- at a standstill that
                // would arm reverse a tenth of a second after the catch.
                // The catch wins: latching a pedal means "hold this", never
                // "change direction".
                self.direction_armed = String::new();
                self.direction_hold_s = 0.0;
                ctx.audio.play_with("ui/tick", 1.0, 0.0);
                self.say_latch(ctx, "Brake latched.");
            }
            Some(LatchEvent::Released) => {
                self.say_latch(ctx, "Brake released.");
            }
            None => {}
        }
        if (key_up || pad_throttle > 0.05) && self.brake_latch.release() {
            self.say_latch(ctx, "Brake released.");
        }
        key_down || self.brake_latch.latched
    }

    /// One queued CONFIRMATION line from the latch machinery.
    fn say_latch(&self, ctx: &mut GameContext, text: &str) {
        ctx.say_event_with(
            text.to_string(),
            SayEvent::queued().category(SpeechCategory::Confirmation),
        );
    }
}
