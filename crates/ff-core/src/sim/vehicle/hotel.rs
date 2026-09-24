//! Reefer TRU and APU hotel power (2.0 v1).
//!
//! Coarse cargo temperature and low diesel burns from the tractor tank.
//! Not a thermal model, not a separate TRU tank, and not a noise/HOS sim.

use super::TruckState;

/// Gallons per game-second while the reefer TRU runs (~0.5× normal idle).
pub const REEFER_BURN_GAL_PER_S: f64 = 0.00011;
/// Gallons per game-second while the APU runs (~0.25× normal idle).
pub const APU_BURN_GAL_PER_S: f64 = 0.000055;

/// Coarse cold-setpoint for reefer freight (°C). Honesty: not cargo-specific.
pub const REEFER_SETPOINT_C: f64 = 2.0;
/// Acceptable band around the setpoint (°C).
pub const REEFER_BAND_C: f64 = 4.0;

/// Approach rate toward setpoint while the TRU is on (fraction of gap per game-second).
const REEFER_HOLD_RATE: f64 = 0.0025;
/// Approach rate toward ambient while the TRU is off.
const REEFER_DRIFT_RATE: f64 = 0.0009;

/// Game minutes cargo may sit outside the band before spoilage starts.
pub const REEFER_SPOIL_GRACE_MIN: f64 = 45.0;
/// Cargo-damage percent per game-minute once past the grace window (× fragility).
const REEFER_SPOIL_PCT_PER_MIN: f64 = 0.08;

/// One-shot cues the driving/speech layer reads after a hotel advance.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct HotelEvents {
    /// Reefer was running and the tractor tank ran dry.
    pub reefer_starved: bool,
    /// APU was running and the tractor tank ran dry.
    pub apu_starved: bool,
    /// Spoilage damage was applied this step.
    pub spoil_tick: bool,
}

impl TruckState {
    /// Whether this truck currently carries freight that needs the reefer.
    pub fn cargo_needs_reefer(&self) -> bool {
        self.cargo_needs_reefer
    }

    pub fn set_cargo_needs_reefer(&mut self, needs: bool) {
        let was = self.cargo_needs_reefer;
        self.cargo_needs_reefer = needs;
        if needs && !was {
            // Fresh reefer load: start near the setpoint if the unit is on,
            // otherwise at ambient so an off unit has work to do.
            self.cargo_temp_c = if self.reefer_on {
                REEFER_SETPOINT_C
            } else {
                self.ambient_temp_c
            };
            self.reefer_out_of_range_min = 0.0;
        }
        if !needs {
            self.reefer_on = false;
            self.reefer_out_of_range_min = 0.0;
        }
    }

    /// Turn the reefer TRU on. Returns false when there is no reefer load.
    pub fn start_reefer(&mut self) -> bool {
        if !self.cargo_needs_reefer || !self.trailer_attached || self.cargo_kg <= 0.0 {
            return false;
        }
        if self.fuel_gal <= 0.0 {
            return false;
        }
        self.reefer_on = true;
        true
    }

    pub fn stop_reefer(&mut self) {
        self.reefer_on = false;
    }

    pub fn start_apu(&mut self) -> bool {
        if self.fuel_gal <= 0.0 {
            return false;
        }
        self.apu_on = true;
        true
    }

    pub fn stop_apu(&mut self) {
        self.apu_on = false;
    }

    /// Burn hotel diesel and advance coarse cargo temp over game-seconds.
    ///
    /// Uses the same game-second denomination as [`Self::update_fuel`]: callers
    /// pass `dt * fuel_burn_mult` from the frame loop, or raw game-seconds from
    /// a scripted rest advance.
    pub fn advance_hotel_power(&mut self, game_seconds: f64) -> HotelEvents {
        let mut events = HotelEvents::default();
        if game_seconds <= 0.0 {
            return events;
        }

        let mut burn = 0.0;
        if self.reefer_on {
            burn += REEFER_BURN_GAL_PER_S * game_seconds;
        }
        if self.apu_on {
            burn += APU_BURN_GAL_PER_S * game_seconds;
        }
        if burn > 0.0 {
            let had_reefer = self.reefer_on;
            let had_apu = self.apu_on;
            let took = self.fuel_gal.min(burn);
            self.fuel_gal -= took;
            if self.fuel_gal <= 0.0 {
                self.fuel_gal = 0.0;
                if had_reefer {
                    self.reefer_on = false;
                    events.reefer_starved = true;
                    self.reefer_just_starved = true;
                }
                if had_apu {
                    self.apu_on = false;
                    events.apu_starved = true;
                }
                // Tractor engine also dies when the tank is empty.
                if self.engine_on {
                    self.stop_engine();
                }
            }
        }

        if self.cargo_needs_reefer && self.trailer_attached && self.cargo_kg > 0.0 {
            let target = if self.reefer_on {
                REEFER_SETPOINT_C
            } else {
                self.ambient_temp_c
            };
            let rate = if self.reefer_on {
                REEFER_HOLD_RATE
            } else {
                REEFER_DRIFT_RATE
            };
            let gap = target - self.cargo_temp_c;
            self.cargo_temp_c += gap * (1.0 - (-rate * game_seconds).exp());

            let in_band = (self.cargo_temp_c - REEFER_SETPOINT_C).abs() <= REEFER_BAND_C;
            let minutes = game_seconds / 60.0;
            if in_band {
                self.reefer_out_of_range_min = 0.0;
            } else {
                self.reefer_out_of_range_min += minutes;
                if self.reefer_out_of_range_min > REEFER_SPOIL_GRACE_MIN {
                    let over = self.reefer_out_of_range_min - REEFER_SPOIL_GRACE_MIN;
                    // Only the minutes in this step past grace, not the whole overage.
                    let spoil_minutes = minutes.min(over);
                    let dmg = REEFER_SPOIL_PCT_PER_MIN * spoil_minutes * self.cargo_fragility;
                    if self.add_cargo_damage(dmg) > 0.0 {
                        events.spoil_tick = true;
                    }
                }
            }
        }

        events
    }

    /// True when cargo temp is outside the coarse reefer band.
    pub fn reefer_temp_out_of_range(&self) -> bool {
        self.cargo_needs_reefer && (self.cargo_temp_c - REEFER_SETPOINT_C).abs() > REEFER_BAND_C
    }

    /// Spoken cargo-temp readout for reefer loads.
    pub fn reefer_temp_status_text(&self, imperial: bool) -> String {
        if !self.cargo_needs_reefer {
            return String::new();
        }
        if imperial {
            let f = self.cargo_temp_c * 9.0 / 5.0 + 32.0;
            format!("Cargo temperature {:.0} degrees Fahrenheit", f)
        } else {
            format!("Cargo temperature {:.0} degrees Celsius", self.cargo_temp_c)
        }
    }
}

/// Whether a cargo class needs the reefer TRU.
pub fn cargo_needs_reefer_key(key: &str) -> bool {
    key == "food" || key == "refrigerated"
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sim::vehicle::{TruckSpecs, AMBIENT_C};

    fn truck() -> TruckState {
        let mut t = TruckState::new(TruckSpecs::default());
        t.fuel_gal = 100.0;
        t.ambient_temp_c = 25.0;
        t.cargo_temp_c = 25.0;
        t.cargo_kg = 10_000.0;
        t.trailer_attached = true;
        t.cargo_fragility = 2.4;
        t.set_cargo_needs_reefer(true);
        t
    }

    #[test]
    fn reefer_burns_only_when_on() {
        let mut t = truck();
        t.reefer_on = false;
        let before = t.fuel_gal;
        t.advance_hotel_power(3600.0);
        assert!((t.fuel_gal - before).abs() < 1e-9);

        t.reefer_on = true;
        t.advance_hotel_power(3600.0);
        let burned = before - t.fuel_gal;
        assert!(burned > 0.3 && burned < 0.6, "burned {burned}");
    }

    #[test]
    fn temp_holds_when_on_and_drifts_when_off() {
        let mut t = truck();
        t.cargo_temp_c = 25.0;
        t.reefer_on = true;
        t.advance_hotel_power(3600.0 * 2.0);
        assert!(
            (t.cargo_temp_c - REEFER_SETPOINT_C).abs() < 1.5,
            "held at {}",
            t.cargo_temp_c
        );

        t.reefer_on = false;
        t.ambient_temp_c = 30.0;
        t.advance_hotel_power(3600.0 * 3.0);
        assert!(
            t.cargo_temp_c > 10.0,
            "should drift toward ambient, got {}",
            t.cargo_temp_c
        );
    }

    #[test]
    fn spoilage_only_for_reefer_freight_past_threshold() {
        let mut reefer = truck();
        reefer.reefer_on = false;
        reefer.ambient_temp_c = 30.0;
        reefer.cargo_temp_c = 30.0;
        // Drive well past grace while out of range.
        reefer.advance_hotel_power(60.0 * 90.0);
        assert!(
            reefer.cargo_damage_pct > 0.0,
            "reefer should spoil, got {}",
            reefer.cargo_damage_pct
        );

        let mut dry = truck();
        dry.set_cargo_needs_reefer(false);
        dry.cargo_damage_pct = 0.0;
        dry.reefer_on = false;
        dry.ambient_temp_c = 30.0;
        dry.cargo_temp_c = 30.0;
        dry.advance_hotel_power(60.0 * 90.0);
        assert_eq!(dry.cargo_damage_pct, 0.0);
    }

    #[test]
    fn apu_burns_low_and_only_when_on() {
        let mut t = truck();
        t.set_cargo_needs_reefer(false);
        t.apu_on = false;
        let before = t.fuel_gal;
        t.advance_hotel_power(3600.0);
        assert!((t.fuel_gal - before).abs() < 1e-9);

        t.apu_on = true;
        t.advance_hotel_power(3600.0);
        let burned = before - t.fuel_gal;
        assert!(burned > 0.15 && burned < 0.3, "APU burned {burned}");

        // APU alone burns less than reefer alone over the same hour.
        let mut r = truck();
        r.reefer_on = true;
        r.apu_on = false;
        let reefer_before = r.fuel_gal;
        r.advance_hotel_power(3600.0);
        let reefer_burned = reefer_before - r.fuel_gal;
        assert!(reefer_burned > burned);
    }

    #[test]
    fn old_truck_defaults_load_without_hotel_fields() {
        let t = TruckState::new(TruckSpecs::default());
        assert!(!t.reefer_on);
        assert!(!t.apu_on);
        assert!(!t.cargo_needs_reefer);
        assert_eq!(t.reefer_out_of_range_min, 0.0);
        assert_eq!(t.cargo_temp_c, AMBIENT_C);
        assert_eq!(t.ambient_temp_c, AMBIENT_C);
    }

    #[test]
    fn reefer_starves_when_tank_empty() {
        let mut t = truck();
        t.fuel_gal = 0.05;
        t.reefer_on = true;
        let ev = t.advance_hotel_power(3600.0);
        assert!(ev.reefer_starved);
        assert!(!t.reefer_on);
        assert_eq!(t.fuel_gal, 0.0);
    }
}
