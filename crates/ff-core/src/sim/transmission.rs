//! Ten-speed truck transmission with manual and automatic modes.
//!
//! Manual shifting follows the real sequence: press the clutch, pick the target
//! gear, release the clutch. Shifting without the clutch grinds and is refused.
//! Automatic mode shifts on RPM thresholds with a truck-like torque-interrupt delay.
//!
//! Port of `freight_fate/sim/transmission.py`.

/// Eaton-style overdrive 10-speed spread. The top range uses direct 9th and
/// overdrive 10th so the automatic does not reach top gear at city speeds.
pub const GEAR_RATIOS: [f64; 10] = [12.69, 9.29, 6.75, 4.90, 3.62, 2.59, 1.90, 1.38, 1.00, 0.74];
pub const REVERSE_RATIO: f64 = 13.9;
pub const FINAL_DRIVE: f64 = 3.55;
pub const REVERSE: i32 = -1;
pub const NEUTRAL: i32 = 0;

pub const AUTO_UPSHIFT_RPM: f64 = 1750.0;
pub const AUTO_DOWNSHIFT_RPM: f64 = 1050.0;
// Torque-interrupt length. Real AMTs are quickest in the low box -- small
// inertia steps and launch urgency -- and take the longest up top, so the
// time scales with the gear being ENGAGED (owner's ear after the Camp
// Verde-Kingman run, then tightened to modern-AMT figures 2026-07-23:
// power upshifts run 0.25 through the low box to 0.5 in 10th). Downshifts
// keep their own full-second figure: a real box has to rev-match UP into
// the lower gear, which is genuinely slower than a power upshift -- and
// that deliberateness is also what keeps a jake descent from cycling the
// retarder fast enough to break a chained truck loose (physics bench).
// DOWNSHIFT_TIME is also the conservative figure the grade-loss estimate
// uses.
/// Seconds of torque interruption, 10th-gear power-upshift ceiling.
pub const SHIFT_TIME: f64 = 0.5;
/// Through gear 4.
pub const SHIFT_TIME_LOW: f64 = 0.25;
/// Rev-matched downshifts, and the jake preselect.
pub const DOWNSHIFT_TIME: f64 = 1.0;
// Manual shifts: the player's clutch is already the torque interruption, so
// the box only charges the lever's own travel through neutral. Stacking the
// AMT interrupt on top left up to 0.6 s of dead pedal AFTER the clutch was
// out in the top gears (Josh's "manual needs tuning", measured 2026-07-23).
pub const MANUAL_LEVER_TIME: f64 = 0.25;

/// Seconds of torque interruption for a shift engaging `gear`.
pub fn shift_time_for(gear: i32) -> f64 {
    let g = gear.clamp(1, 10);
    if g <= 4 {
        return SHIFT_TIME_LOW;
    }
    SHIFT_TIME_LOW + (SHIFT_TIME - SHIFT_TIME_LOW) * (g - 4) as f64 / 6.0
}

// With the engine brake working, a real automatic pre-selects a lower range
// to put the engine where the retarder bites (high RPM) instead of upshifting
// away from it. Downshift while below the target band, but never into a gear
// that would spin the engine past the ceiling.
pub const JAKE_PRESELECT_RPM: f64 = 1700.0;
pub const JAKE_MAX_RPM: f64 = 2150.0;
pub const PROGRESSIVE_UPSHIFT_RPM: [f64; 10] = [
    1450.0, 1550.0, 1650.0, 1700.0, 1750.0, 1800.0, 1800.0, 1800.0, 1800.0, 1850.0,
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ShiftResult {
    pub ok: bool,
    pub message: String,
    pub grind: bool,
}

impl ShiftResult {
    fn refused(message: &str) -> Self {
        ShiftResult {
            ok: false,
            message: message.to_string(),
            grind: false,
        }
    }
}

/// Everything `auto_update` wants to know about the truck this frame, in
/// the order the Python keyword arguments were declared. `Default` carries
/// the Python defaults so a caller (or a test) names only what it changes.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AutoUpdateArgs {
    pub rpm: f64,
    pub throttle: f64,
    pub moving: bool,
    pub braking: bool,
    pub can_upshift: bool,
    pub minimum_shift_interval_s: f64,
    pub upshift_rpm: f64,
    pub start_gear: i32,
    pub upshift_steps: i32,
    pub downshift_target: Option<i32>,
    pub engine_braking: bool,
    pub downshift_rpm: f64,
    pub retarder_slipping: bool,
}

impl Default for AutoUpdateArgs {
    fn default() -> Self {
        AutoUpdateArgs {
            rpm: 0.0,
            throttle: 0.0,
            moving: false,
            braking: false,
            can_upshift: true,
            minimum_shift_interval_s: 0.0,
            upshift_rpm: AUTO_UPSHIFT_RPM,
            start_gear: 1,
            upshift_steps: 1,
            downshift_target: None,
            engine_braking: false,
            downshift_rpm: AUTO_DOWNSHIFT_RPM,
            retarder_slipping: false,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Transmission {
    pub automatic: bool,
    /// -1 = reverse, 0 = neutral, 1..10
    pub gear: i32,
    /// 0 engaged .. 1 fully pressed
    pub clutch: f64,
    /// Seconds of torque interruption left on the shift in progress.
    pub shift_timer: f64,
    /// Seconds since the last gear change (the automatic's comfort hold).
    pub gear_hold_timer: f64,
}

impl Default for Transmission {
    fn default() -> Self {
        Transmission {
            automatic: false,
            gear: NEUTRAL,
            clutch: 0.0,
            shift_timer: 0.0,
            gear_hold_timer: 999.0,
        }
    }
}

impl Transmission {
    pub fn num_gears(&self) -> i32 {
        GEAR_RATIOS.len() as i32
    }

    pub fn in_neutral(&self) -> bool {
        self.gear == NEUTRAL
    }

    pub fn in_reverse(&self) -> bool {
        self.gear == REVERSE
    }

    pub fn shifting(&self) -> bool {
        self.shift_timer > 0.0
    }

    /// Overall ratio engine->wheels; zero when no torque path exists.
    pub fn drive_ratio(&self) -> f64 {
        if self.in_neutral() || self.shifting() || self.clutch > 0.5 {
            return 0.0;
        }
        if self.in_reverse() {
            return -REVERSE_RATIO * FINAL_DRIVE;
        }
        GEAR_RATIOS[(self.gear - 1) as usize] * FINAL_DRIVE
    }

    pub fn ratio_for(&self, gear: i32) -> f64 {
        if gear == REVERSE {
            return -REVERSE_RATIO * FINAL_DRIVE;
        }
        if gear != 0 {
            GEAR_RATIOS[(gear - 1) as usize] * FINAL_DRIVE
        } else {
            0.0
        }
    }

    // -- manual ----------------------------------------------------------------

    /// Manual gear selection. Requires the clutch to be pressed.
    pub fn request_gear(&mut self, target: i32) -> ShiftResult {
        if self.automatic {
            return ShiftResult::refused("Transmission is in automatic mode");
        }
        if !(REVERSE <= target && target <= self.num_gears()) {
            return ShiftResult::refused(&format!("No gear {target}"));
        }
        if target == self.gear {
            return ShiftResult::refused(&format!("Already in {}", Self::gear_name(target)));
        }
        if self.clutch < 0.8 && target != NEUTRAL {
            return ShiftResult {
                ok: false,
                message: "Clutch not pressed".to_string(),
                grind: true,
            };
        }
        self.gear = target;
        self.shift_timer = MANUAL_LEVER_TIME;
        ShiftResult {
            ok: true,
            message: Self::gear_name(target),
            grind: false,
        }
    }

    pub fn shift_up(&mut self) -> ShiftResult {
        self.request_gear((self.gear + 1).min(self.num_gears()))
    }

    pub fn shift_down(&mut self) -> ShiftResult {
        self.request_gear((self.gear - 1).max(NEUTRAL))
    }

    // -- automatic ---------------------------------------------------------------

    /// Pick a gear in automatic mode. Returns the new gear when it changes.
    ///
    /// While braking the box never upshifts -- a real automatic holds the gear
    /// for engine braking instead of grabbing a taller one as you slow, which
    /// otherwise read as "geared up while stopping". With the engine brake
    /// active it goes further and pre-selects DOWN toward the retard band,
    /// because a jake in overdrive at low RPM is barely a brake at all.
    pub fn auto_update(&mut self, args: AutoUpdateArgs) -> Option<i32> {
        let AutoUpdateArgs {
            rpm,
            throttle,
            moving,
            braking,
            can_upshift,
            minimum_shift_interval_s,
            upshift_rpm,
            start_gear,
            upshift_steps,
            downshift_target,
            engine_braking,
            downshift_rpm,
            retarder_slipping,
        } = args;
        if !self.automatic || self.shifting() {
            return None;
        }
        if self.in_reverse() {
            return None;
        }
        if self.gear == NEUTRAL {
            if throttle > 0.05 {
                self.gear = start_gear.min(self.num_gears()).max(1);
                self.shift_timer = shift_time_for(self.gear);
                self.gear_hold_timer = 0.0;
                return Some(self.gear);
            }
            return None;
        }
        let restart_gear = start_gear.min(self.num_gears()).max(1);
        if !moving && self.gear > restart_gear {
            // Stopped (or knocked to a crawl by a collision) in a high gear:
            // a real automatic returns to its starting gear -- first when
            // grossed out, third when light -- instead of lugging until the
            // engine dies on every restart. Snapping all the way to first
            // regardless used to throw away the light rig's start gear
            // before the truck had rolled a foot.
            self.gear = restart_gear;
            self.shift_timer = shift_time_for(self.gear);
            self.gear_hold_timer = 0.0;
            return Some(self.gear);
        }
        // The comfort hold between shifts never delays engine protection
        // (road past the jake ceiling upshifts NOW) -- and above the launch
        // box it never delays an upshift the revs have already earned. Two
        // owner rulings meet here: the hold IS part of the approved stately
        // launch feel through the low gears (each gear revs out, then a
        // beat), but past gear five the same hold left the engine hanging
        // at the crest of the pull -- the driver heard the rev top out and
        // then waited a second for the gear (owner report, 2026-07-23).
        // After an upshift the rpm falls a whole ratio step, so up there
        // the rev-out time is all the anti-hunt spacing the box needs.
        let earned_upshift =
            self.gear >= 5 && throttle > 0.2 && rpm > upshift_rpm && can_upshift && !braking;
        if self.gear_hold_timer < minimum_shift_interval_s
            && !(engine_braking && rpm > JAKE_MAX_RPM)
            && !earned_upshift
        {
            return None;
        }
        // Braking or engine-braking holds the gear -- except that a real
        // automatic protects its engine: once the road spins it past the
        // ceiling, the box upshifts anyway. On a downgrade that trades
        // engine safety for a taller gear and a weaker jake, which is
        // exactly the runaway spiral a mismanaged descent earns.
        let hold_gear = (braking || engine_braking) && rpm < JAKE_MAX_RPM;
        if rpm > upshift_rpm && self.gear < self.num_gears() && !hold_gear && can_upshift {
            self.gear = self.num_gears().min(self.gear + upshift_steps.max(1));
            self.shift_timer = shift_time_for(self.gear);
            self.gear_hold_timer = 0.0;
            return Some(self.gear);
        }
        if engine_braking
            && moving
            && self.gear > 1
            && rpm < JAKE_PRESELECT_RPM
            && !retarder_slipping
        {
            // Never pre-select DEEPER while the drive axle is already breaking
            // loose: a lower gear multiplies the retard torque that broke it.
            // Real retarder management is traction-linked for the same reason.
            let lower = GEAR_RATIOS[(self.gear - 2) as usize];
            let current = GEAR_RATIOS[(self.gear - 1) as usize];
            if rpm * lower / current <= JAKE_MAX_RPM {
                self.gear -= 1;
                // Downshifts stay deliberate at the full interruption: the
                // quick low-box time is a POWER-shift feel. On a jake
                // descent the box cycles preselect-down against
                // engine-protect-up, and quick downshifts doubled that
                // cycle rate -- enough extra jake-connected time to break
                // a chained truck loose on ice (physics bench regression).
                self.shift_timer = DOWNSHIFT_TIME;
                self.gear_hold_timer = 0.0;
                return Some(self.gear);
            }
        }
        if rpm < downshift_rpm && self.gear > 1 && moving && !retarder_slipping {
            // The anti-lugging downshift also respects traction while the
            // retarder works: on a low-grip descent the road spins the
            // engine, there is no stall to protect against, and the lower
            // gear would multiply the retard past what the drives can hold.
            let target = match downshift_target {
                None => self.gear - 1,
                Some(t) => t,
            };
            self.gear = (self.gear - 1).min(target).max(1);
            self.shift_timer = DOWNSHIFT_TIME;
            self.gear_hold_timer = 0.0;
            return Some(self.gear);
        }
        None
    }

    /// Emergency single downshift to keep an automatic out of a lugging
    /// gear while still rolling. The normal RPM-threshold downshift can be
    /// outrun by a hard deceleration during the shift delay; this forces the
    /// drop so the engine kicks down instead of stalling. No-op in manual.
    pub fn kickdown(&mut self) -> Option<i32> {
        if !self.automatic || self.gear <= 1 {
            return None;
        }
        self.gear -= 1;
        self.shift_timer = shift_time_for(self.gear);
        self.gear_hold_timer = 0.0;
        Some(self.gear)
    }

    pub fn update(&mut self, dt: f64) {
        self.gear_hold_timer += dt.max(0.0);
        if self.shift_timer > 0.0 {
            self.shift_timer = (self.shift_timer - dt).max(0.0);
        }
    }

    /// Clear a stopped recovery's drive state without a simulated shift.
    pub fn reset_to_neutral(&mut self) {
        self.gear = NEUTRAL;
        self.shift_timer = 0.0;
        self.gear_hold_timer = 0.0;
    }

    pub fn gear_name(gear: i32) -> String {
        if gear == REVERSE {
            return "reverse".to_string();
        }
        if gear == NEUTRAL {
            "neutral".to_string()
        } else {
            format!("gear {gear}")
        }
    }
}

#[cfg(test)]
#[allow(clippy::field_reassign_with_default)]
mod tests {
    //! Port of `tests/test_transmission.py`.
    use super::*;
    use crate::sim::vehicle::TruckSpecs;

    fn auto(gear: i32) -> Transmission {
        Transmission {
            automatic: true,
            gear,
            ..Default::default()
        }
    }

    #[test]
    fn test_starts_in_neutral() {
        let tr = Transmission::default();
        assert!(tr.in_neutral());
        assert_eq!(tr.drive_ratio(), 0.0);
    }

    #[test]
    fn test_manual_shift_requires_clutch() {
        let mut tr = Transmission::default();
        let result = tr.request_gear(1);
        assert!(!result.ok);
        assert!(result.grind);
        tr.clutch = 1.0;
        let result = tr.request_gear(1);
        assert!(result.ok);
        assert_eq!(tr.gear, 1);
    }

    #[test]
    fn test_no_torque_path_while_clutch_pressed_or_shifting() {
        let mut tr = Transmission::default();
        tr.clutch = 1.0;
        tr.request_gear(1);
        assert_eq!(tr.drive_ratio(), 0.0); // still shifting + clutch in
        tr.update(1.0); // shift completes
        assert_eq!(tr.drive_ratio(), 0.0); // clutch still pressed
        tr.clutch = 0.0;
        assert!(tr.drive_ratio() > 0.0);
    }

    #[test]
    fn test_shift_to_neutral_never_needs_clutch() {
        let mut tr = Transmission::default();
        tr.clutch = 1.0;
        tr.request_gear(3);
        tr.update(1.0);
        tr.clutch = 0.0;
        let result = tr.request_gear(NEUTRAL);
        assert!(result.ok);
        assert!(tr.in_neutral());
    }

    #[test]
    fn test_manual_reverse_requires_clutch() {
        let mut tr = Transmission::default();
        let result = tr.request_gear(REVERSE);
        assert!(!result.ok);
        assert!(result.grind);
        tr.clutch = 1.0;
        let result = tr.request_gear(REVERSE);
        assert!(result.ok);
        assert!(tr.in_reverse());
        assert_eq!(result.message, "reverse");
        tr.update(1.0);
        tr.clutch = 0.0;
        assert!(tr.drive_ratio() < 0.0);
    }

    #[test]
    fn test_invalid_gears_rejected() {
        let mut tr = Transmission::default();
        tr.clutch = 1.0;
        assert!(!tr.request_gear(11).ok);
        assert!(!tr.request_gear(-2).ok);
    }

    #[test]
    fn test_manual_rejected_in_automatic_mode() {
        let mut tr = Transmission {
            automatic: true,
            ..Default::default()
        };
        tr.clutch = 1.0;
        assert!(!tr.request_gear(2).ok);
    }

    #[test]
    fn test_auto_upshifts_at_high_rpm() {
        // The upshift point now comes from the caller (the vehicle passes its
        // progressive per-gear schedule); at exactly the threshold the box holds,
        // one RPM over it shifts.
        let mut tr = auto(3);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: AUTO_UPSHIFT_RPM,
                throttle: 0.8,
                moving: true,
                upshift_rpm: AUTO_UPSHIFT_RPM,
                ..Default::default()
            }),
            None
        );
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: AUTO_UPSHIFT_RPM + 1.0,
                throttle: 0.8,
                moving: true,
                upshift_rpm: AUTO_UPSHIFT_RPM,
                ..Default::default()
            }),
            Some(4)
        );
    }

    #[test]
    fn test_auto_downshifts_at_low_rpm() {
        let mut tr = auto(5);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 900.0,
                throttle: 0.1,
                moving: true,
                ..Default::default()
            }),
            Some(4)
        );
    }

    #[test]
    fn test_auto_holds_gear_while_braking_instead_of_upshifting() {
        // High rpm would normally upshift, but braking from speed must not gear up.
        let mut tr = auto(5);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 1800.0,
                throttle: 0.0,
                moving: true,
                braking: true,
                ..Default::default()
            }),
            None
        );
        // Still allowed to downshift as the brake scrubs speed and rpm falls.
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 900.0,
                throttle: 0.0,
                moving: true,
                braking: true,
                ..Default::default()
            }),
            Some(4)
        );
        // Without braking the same high rpm still upshifts (default unchanged).
        let mut tr = auto(5);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 1800.0,
                throttle: 0.8,
                moving: true,
                ..Default::default()
            }),
            Some(6)
        );
    }

    #[test]
    fn test_engine_brake_preselects_down_and_holds_the_retard_band() {
        // Below the retard band with the jake on: drop a gear to make it bite.
        let mut tr = auto(8);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 1400.0,
                throttle: 0.0,
                moving: true,
                engine_braking: true,
                ..Default::default()
            }),
            Some(7)
        );
        tr.update(2.0); // let the shift finish
                        // In the band: hold the gear even though plain RPM rules would upshift.
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 2000.0,
                throttle: 0.0,
                moving: true,
                engine_braking: true,
                ..Default::default()
            }),
            None
        );
        // Never preselect into a gear that would spin the engine past the ceiling.
        let mut tr = auto(7);
        let rpm = JAKE_PRESELECT_RPM - 50.0;
        assert!(rpm * GEAR_RATIOS[5] / GEAR_RATIOS[6] > JAKE_MAX_RPM);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm,
                throttle: 0.0,
                moving: true,
                engine_braking: true,
                ..Default::default()
            }),
            None
        );
    }

    #[test]
    fn test_engine_protection_upshifts_past_the_rpm_ceiling() {
        // The road spinning the engine past the ceiling beats the jake hold:
        // a real automatic protects its engine even mid-descent.
        let mut tr = auto(7);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: JAKE_MAX_RPM + 10.0,
                throttle: 0.0,
                moving: true,
                engine_braking: true,
                ..Default::default()
            }),
            Some(8)
        );
        let mut tr = auto(7);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: JAKE_MAX_RPM + 10.0,
                throttle: 0.0,
                moving: true,
                braking: true,
                ..Default::default()
            }),
            Some(8)
        );
    }

    #[test]
    fn test_auto_engages_first_from_neutral_on_throttle() {
        let mut tr = auto(NEUTRAL);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 600.0,
                throttle: 0.5,
                moving: false,
                ..Default::default()
            }),
            Some(1)
        );
    }

    #[test]
    fn test_auto_drops_to_first_when_stopped_in_high_gear() {
        // Regression: a collision can stop the truck while the box is still in a
        // high gear. The automatic must return to first instead of leaving the
        // engine to lug and stall on every restart (a soft-lock).
        let mut tr = auto(7);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 400.0,
                throttle: 0.0,
                moving: false,
                ..Default::default()
            }),
            Some(1)
        );
        tr.update(1.0);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 600.0,
                throttle: 0.0,
                moving: false,
                ..Default::default()
            }),
            None
        ); // stays put
    }

    #[test]
    fn test_auto_waits_for_shift_to_finish() {
        let mut tr = auto(3);
        tr.auto_update(AutoUpdateArgs {
            rpm: AUTO_UPSHIFT_RPM + 1.0,
            throttle: 0.8,
            moving: true,
            ..Default::default()
        });
        assert!(tr.shifting());
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 1800.0,
                throttle: 0.8,
                moving: true,
                ..Default::default()
            }),
            None
        );
        let duration = shift_time_for(tr.gear);
        tr.update(duration * 0.7);
        assert!(tr.shifting());
        tr.update(duration * 0.4);
        assert!(!tr.shifting());
    }

    #[test]
    fn test_shift_time_scales_with_gear() {
        // Real AMTs are quickest in the low box and slowest up top.
        assert_eq!(shift_time_for(1), SHIFT_TIME_LOW);
        assert_eq!(shift_time_for(4), SHIFT_TIME_LOW);
        assert!(SHIFT_TIME_LOW < shift_time_for(7) && shift_time_for(7) < SHIFT_TIME);
        assert_eq!(shift_time_for(10), SHIFT_TIME);
    }

    #[test]
    fn test_auto_respects_minimum_interval_between_shifts() {
        let mut tr = auto(2);
        let args = AutoUpdateArgs {
            rpm: 1800.0,
            throttle: 0.8,
            moving: true,
            minimum_shift_interval_s: 3.5,
            ..Default::default()
        };
        assert_eq!(tr.auto_update(args), Some(3));
        tr.update(1.0);
        assert!(!tr.shifting());
        assert_eq!(tr.auto_update(args), None);
        tr.update(2.5);
        assert_eq!(tr.auto_update(args), Some(4));
    }

    #[test]
    fn test_auto_does_not_shift_out_of_reverse() {
        let mut tr = auto(REVERSE);
        assert_eq!(
            tr.auto_update(AutoUpdateArgs {
                rpm: 1900.0,
                throttle: 0.5,
                moving: true,
                ..Default::default()
            }),
            None
        );
        assert!(tr.in_reverse());
    }

    fn rpm_at_speed_mph(speed_mph: f64, gear: i32) -> f64 {
        let specs = TruckSpecs::default();
        let meters_per_second = speed_mph / 2.23694;
        let wheel_rps = meters_per_second / (2.0 * std::f64::consts::PI * specs.wheel_radius_m);
        wheel_rps * 60.0 * GEAR_RATIOS[(gear - 1) as usize] * FINAL_DRIVE
    }

    #[test]
    fn test_upper_automatic_gears_are_not_reached_at_city_speed() {
        // Regression for issue #15: the previous hybrid ratio set shifted from
        // 9th into 10th in the mid-40 mph range, making the upper gears feel
        // compressed. At 46 mph, 9th should still be below the upshift threshold.
        assert!(rpm_at_speed_mph(46.0, 9) < AUTO_UPSHIFT_RPM);
        assert!(rpm_at_speed_mph(58.0, 9) >= AUTO_UPSHIFT_RPM);
    }

    #[test]
    fn test_top_gear_cruises_in_diesel_rpm_band() {
        let rpm = rpm_at_speed_mph(60.0, 10);
        assert!((1200.0..=1500.0).contains(&rpm));
    }
}
