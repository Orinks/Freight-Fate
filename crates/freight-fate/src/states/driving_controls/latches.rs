//! `_update_pedal_latches`: the per-frame half of the control surface.
//!
//! Called once per frame from `update()` with the raw pedal inputs, so it
//! lives with the controls rather than with the update loop that calls it.

use ff_core::sim::pedal_latch::LatchEvent;
use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

impl DrivingState {
    /// Advance both pedal latches and blend them into the pedal state.
    ///
    /// Called once per frame from `update()` with the raw pedal inputs;
    /// returns the effective `(key_up, key_down)` the rest of the frame drives
    /// on. The catch clicks (its own sound, not the gear click) and both
    /// directions speak. The opposite pedal always releases a latch instantly,
    /// and safety systems outrank a latched accelerator: a live hazard
    /// (including automatic emergency braking), the emergency brake, and the
    /// overspeed alarm all drop it audibly.
    ///
    /// Returns `(hand_up, key_down, throttle_latched)`: the throttle latch is
    /// reported separately rather than blended in, because a latched throttle
    /// is the lowest-priority speed input -- `update()` lets it drive the pedal
    /// only when no speed authority (cruise, keeper, curve assist) is engaged,
    /// while a hand-held key stays a live manual override. The brake latch
    /// keeps pre-blending: nothing outranks the driver's brake.
    #[allow(clippy::too_many_arguments)]
    pub fn update_pedal_latches(
        &mut self,
        ctx: &mut GameContext,
        key_up: bool,
        key_down: bool,
        pad_throttle: f64,
        pad_brake: f64,
        emergency: bool,
        dt: f64,
    ) -> (bool, bool, bool) {
        if ctx.settings.pedal_latch == "off" {
            if self.throttle_latch.release() {
                self.say_latch(ctx, "Throttle released.", false);
            }
            if self.brake_latch.release() {
                self.say_latch(ctx, "Brake released.", false);
            }
            return (key_up, key_down, false);
        }
        for which in [LatchSide::Throttle, LatchSide::Brake] {
            let held = match which {
                LatchSide::Throttle => key_up,
                LatchSide::Brake => key_down,
            };
            let name = which.name();
            let event = match which {
                LatchSide::Throttle => self.throttle_latch.update(held, dt),
                LatchSide::Brake => self.brake_latch.update(held, dt),
            };
            match event {
                Some(LatchEvent::Latched) => {
                    if self.direction_armed == "forward" {
                        // ...but never over the shift BACK to forward, which is
                        // the same press-and-hold on the same pedal. The catch
                        // lands first by design (half a second against six
                        // tenths) and used to wipe the pending shift with it,
                        // so a driver pumping the throttle in reverse re-armed
                        // and lost it every single time, and once the latch
                        // caught there was no rising edge left to arm with at
                        // all. The only way out was one clean hold from rest,
                        // which nothing tells anybody to do (owner, at the
                        // scale, 2026-08-21: "I can't get out of reverse?").
                        //
                        // Taking reverse by accident is dangerous, so the catch
                        // still wins there. Ending up in forward gear at a
                        // standstill is not, and being stuck in reverse is a
                        // trap, so the shift takes the pedal. Dropping the
                        // latch lands it in "manual": a key still held keeps
                        // driving the pedal without starting a fresh gesture,
                        // and a truck that just changed direction does not pull
                        // away hands-free.
                        match which {
                            LatchSide::Throttle => self.throttle_latch.release(),
                            LatchSide::Brake => self.brake_latch.release(),
                        };
                        continue;
                    }
                    // The latch gesture's second press is also a press-and-hold
                    // at whatever speed the truck has -- at a standstill that
                    // would arm a direction change and grab reverse a tenth of
                    // a second after the catch. The catch wins: latching a
                    // pedal means "hold this", never "change direction".
                    self.direction_armed = String::new();
                    self.direction_hold_s = 0.0;
                    ctx.audio.play_with("ui/tick", 1.0, 0.0);
                    let mut line = format!("{name} latched.");
                    if which == LatchSide::Throttle && ctx.settings.pedal_latch == "assists first" {
                        // A latch caught while something smarter is holding the
                        // speed must say who has the pedal, or the gesture feels
                        // dead -- the latch takes over only when they release.
                        // In "latch first" mode the plain line is the truth: the
                        // latch has the pedal and nothing outranks it.
                        if self.cruise_mph.is_some() {
                            line = "Throttle latched. Adaptive cruise holds the speed.".to_string();
                        } else if self.keeper_mph.is_some() {
                            line = "Throttle latched. Speed keeper holds the speed.".to_string();
                        }
                    }
                    self.say_latch(ctx, &line, false);
                }
                Some(LatchEvent::Released) => {
                    self.say_latch(ctx, &format!("{name} released."), false);
                }
                None => {}
            }
        }
        let throttle_overridden = key_down
            || pad_brake > 0.05
            || emergency
            || self.hazard_deadline.is_some()
            || self.overspeed_active;
        if throttle_overridden && self.throttle_latch.release() {
            // ROUTE, not the ambient default: a safety system (hazard,
            // emergency brake, overspeed, brake override) is silently
            // surrendering the throttle here, unlike the plain settings-off
            // release above -- the driver needs to know the latch let go
            // without their own gesture (automation-handoff sweep, 2026-08-20,
            // the deferred 2026-08-15 audit).
            self.say_latch(ctx, "Throttle released.", true);
        }
        if (key_up || pad_throttle > 0.05) && self.brake_latch.release() {
            self.say_latch(ctx, "Brake released.", false);
        }
        (
            key_up,
            key_down || self.brake_latch.latched,
            self.throttle_latch.latched,
        )
    }

    /// One queued CONFIRMATION line from the latch machinery, at the ambient
    /// default or promoted to ROUTE when a safety system took the pedal.
    fn say_latch(&self, ctx: &mut GameContext, text: &str, route: bool) {
        let mut opts = SayEvent::queued().category(SpeechCategory::Confirmation);
        if route {
            opts = opts.priority(EventPriority::Route);
        }
        ctx.say_event_with(text.to_string(), opts);
    }
}

/// Which pedal a latch belongs to, so the loop over both reads like the
/// Python tuple it came from.
#[derive(Clone, Copy, PartialEq, Eq)]
enum LatchSide {
    Throttle,
    Brake,
}

impl LatchSide {
    fn name(self) -> &'static str {
        match self {
            LatchSide::Throttle => "Throttle",
            LatchSide::Brake => "Brake",
        }
    }
}
