//! `TruckState` air brakes: the three reservoirs, the governor, the parking
//! brake, the horn's draw, and the save snapshot of all of it.

use serde_json::{json, Value};

use super::TruckState;
use crate::pyfmt::round_py_n;

/// Python's `bool(value)` over a JSON value: None, zero, and empty
/// containers are false, everything else true.
fn py_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().map(|f| f != 0.0).unwrap_or(true),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// Python's `float(value)` over a JSON value, or None where it would raise.
fn py_float(value: &Value) -> Option<f64> {
    match value {
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        Value::Number(n) => n.as_f64(),
        Value::String(s) => s.trim().parse::<f64>().ok(),
        _ => None,
    }
}

impl TruckState {
    // -- air brakes ---------------------------------------------------------------

    /// Compatibility view: the lowest available service/supply reservoir.
    ///
    /// Bobtail there is no trailer line connected, so the trailer reservoir
    /// never gates the gauge, the warnings, or the spring brakes.
    pub fn air_pressure_psi(&self) -> f64 {
        if !self.trailer_attached {
            return self.primary_air_psi.min(self.secondary_air_psi);
        }
        self.primary_air_psi
            .min(self.secondary_air_psi)
            .min(self.trailer_air_psi)
    }

    pub fn set_air_pressure_psi(&mut self, value: f64) {
        self.set_all_air_reservoirs(value);
    }

    pub fn air_low_warning(&self) -> bool {
        self.air_pressure_psi() <= self.specs.air_low_warning_psi
    }

    pub fn spring_brakes_active(&self) -> bool {
        self.air_pressure_psi() <= self.specs.air_spring_brake_psi
    }

    pub fn air_ready(&self) -> bool {
        self.air_pressure_psi() >= self.specs.air_parking_release_psi
    }

    pub fn air_brakes_holding(&self) -> bool {
        self.parking_brake || self.spring_brakes_active()
    }

    /// Parked high idle while the air system is still building.
    ///
    /// A cold-started truck holds a raised idle until the governor releases
    /// the parking brake air; the higher rpm also spins the compressor
    /// faster (see ``update_air_system``), so the truck genuinely charges
    /// sooner. Settles back to the drive idle when the air comes ready --
    /// the audible flip the engine voice keys off.
    pub fn fast_idle_active(&self) -> bool {
        self.engine_on
            && !self.air_ready()
            && self.velocity_mps.abs() < 0.3
            && (self.transmission.in_neutral() || self.parking_brake)
    }

    /// Whether the latched parked high idle may hold (or be set).
    pub fn high_idle_allowed(&self) -> bool {
        self.engine_on && self.parking_brake && self.velocity_mps.abs() < 0.3
    }

    /// The parked idle target: drive idle, air-building fast idle, or the
    /// driver's latched high idle, whichever asks for more.
    pub(super) fn idle_floor_rpm(&self) -> f64 {
        let s = &self.specs;
        let mut floor = if self.fast_idle_active() {
            s.fast_idle_rpm
        } else {
            s.idle_rpm
        };
        if let Some(high) = self.high_idle_rpm {
            floor = floor.max(high);
        }
        floor
    }

    /// Parked trip start: low air, spring/parking brakes set.
    pub fn set_cold_air_start(&mut self) {
        self.set_all_air_reservoirs(self.specs.air_cold_start_psi);
        self.parking_brake = true;
        self.air_compressor_active = false;
        self.last_service_air_application = 0.0;
    }

    /// Compatibility/default state: charged tanks, parked safely.
    pub fn set_air_ready(&mut self, parking_brake: bool) {
        self.set_all_air_reservoirs(self.specs.air_governor_cut_out_psi);
        self.parking_brake = parking_brake;
        self.air_compressor_active = false;
        self.last_service_air_application = 0.0;
    }

    /// Apply reservoir leakage while an engine-off truck is parked.
    pub fn advance_parked_time(&mut self, game_minutes: f64) {
        if game_minutes <= 0.0 || self.engine_on {
            return;
        }
        let loss = self.specs.air_leak_psi_per_game_hour * game_minutes / 60.0;
        self.primary_air_psi = self.clamp_air_psi(self.primary_air_psi - loss);
        self.secondary_air_psi = self.clamp_air_psi(self.secondary_air_psi - loss);
        self.trailer_air_psi = self.clamp_air_psi(self.trailer_air_psi - loss);
        self.sync_air_compressor();
    }

    pub fn set_parking_brake(&mut self) {
        self.parking_brake = true;
    }

    pub fn release_parking_brake(&mut self) -> bool {
        if !self.air_ready() {
            return false;
        }
        self.parking_brake = false;
        self.primary_air_psi = self.clamp_air_psi(self.primary_air_psi - 1.0);
        self.secondary_air_psi = self.clamp_air_psi(self.secondary_air_psi - 1.0);
        self.trailer_air_psi = self.clamp_air_psi(self.trailer_air_psi - 1.5);
        self.sync_air_compressor();
        true
    }

    pub fn air_brake_snapshot(&self) -> Value {
        json!({
            "schema": 2,
            "pressure_psi": round_py_n(self.air_pressure_psi(), 1),
            "primary_psi": round_py_n(self.primary_air_psi, 1),
            "secondary_psi": round_py_n(self.secondary_air_psi, 1),
            "trailer_psi": round_py_n(self.trailer_air_psi, 1),
            "parking_brake": self.parking_brake,
            "compressor_active": self.air_compressor_active,
        })
    }

    pub fn restore_air_brake_snapshot(&mut self, data: &Value, default_ready: bool) {
        let data = match data.as_object() {
            Some(map) => map,
            None => {
                if default_ready {
                    self.set_air_ready(true);
                } else {
                    self.set_cold_air_start();
                }
                return;
            }
        };
        let fallback = data
            .get("pressure_psi")
            .cloned()
            .unwrap_or_else(|| json!(self.specs.air_governor_cut_out_psi));
        self.primary_air_psi =
            self.snapshot_air_value(data.get("primary_psi").unwrap_or(&fallback));
        self.secondary_air_psi =
            self.snapshot_air_value(data.get("secondary_psi").unwrap_or(&fallback));
        self.trailer_air_psi =
            self.snapshot_air_value(data.get("trailer_psi").unwrap_or(&fallback));
        self.parking_brake = data.get("parking_brake").map(py_truthy).unwrap_or(true);
        self.air_compressor_active = data
            .get("compressor_active")
            .map(py_truthy)
            .unwrap_or(false);
        self.last_service_air_application = 0.0;
        if self.spring_brakes_active() {
            self.parking_brake = true;
        }
        self.sync_air_compressor();
    }

    fn clamp_air_psi(&self, value: f64) -> f64 {
        self.specs.air_governor_cut_out_psi.min(value).max(0.0)
    }

    fn snapshot_air_value(&self, value: &Value) -> f64 {
        match py_float(value) {
            Some(f) => self.clamp_air_psi(f),
            None => self.specs.air_governor_cut_out_psi,
        }
    }

    fn set_all_air_reservoirs(&mut self, value: f64) {
        let pressure = self.clamp_air_psi(value);
        self.primary_air_psi = pressure;
        self.secondary_air_psi = pressure;
        self.trailer_air_psi = pressure;
    }

    pub(super) fn sync_air_compressor(&mut self) {
        if !self.engine_on {
            self.air_compressor_active = false;
            return;
        }
        let lowest = self
            .primary_air_psi
            .min(self.secondary_air_psi)
            .min(self.trailer_air_psi);
        if lowest <= self.specs.air_governor_cut_in_psi {
            self.air_compressor_active = true;
        } else if lowest >= self.specs.air_governor_cut_out_psi {
            self.air_compressor_active = false;
        }
    }

    pub(super) fn update_air_system(&mut self, dt: f64) {
        self.consume_brake_air(dt);
        if self.spring_brakes_active() {
            self.parking_brake = true;
        }
        self.sync_air_compressor();
        if self.air_compressor_active && self.engine_on {
            let rpm_span = (self.specs.max_rpm - self.specs.idle_rpm).max(1.0);
            let rpm_factor = ((self.rpm - self.specs.idle_rpm) / rpm_span).clamp(0.0, 1.0);
            let rate = self.specs.air_build_idle_psi_per_s
                + (self.specs.air_build_fast_psi_per_s - self.specs.air_build_idle_psi_per_s)
                    * rpm_factor;
            self.primary_air_psi = self.clamp_air_psi(self.primary_air_psi + rate * dt);
            self.secondary_air_psi = self.clamp_air_psi(self.secondary_air_psi + rate * 0.96 * dt);
            self.trailer_air_psi = self.clamp_air_psi(self.trailer_air_psi + rate * 0.85 * dt);
        }
        self.sync_air_compressor();
    }

    // The air horn draws off the same tanks as the service brakes -- one
    // small valve against four brake chambers, so it is charged at half the
    // hold rate of a full brake application (an in-model ratio, stated as
    // such). Leaning on the horn for a minute costs real air; a blast costs
    // almost nothing; the existing low-air machinery does any warning
    // (Brandon, 2026-08-20: same air for brakes and horn, like a real truck).
    pub const HORN_AIR_PSI_PER_S: f64 = 0.125;
    // FMVSS 121 requires accessories to be pressure-protected so they can
    // never deplete the brake circuits: a pressure protection valve closes
    // and the HORN goes silent, the brakes keep their air. Typical closing
    // pressures sit around 70 psi. So the honk-to-zero spring-brake lockout
    // is mechanically impossible on a compliant tractor -- the first version
    // of this feature got that wrong and a realism audit caught it
    // (2026-08-20; 49 CFR 571.121 and NHTSA interpretation nht95-2.25).
    pub const HORN_PROTECTION_PSI: f64 = 70.0;

    /// Whether the pressure protection valve is still feeding the horn.
    pub fn horn_available(&self) -> bool {
        self.air_pressure_psi() > Self::HORN_PROTECTION_PSI
    }

    fn consume_brake_air(&mut self, dt: f64) {
        if self.horn_on && self.horn_available() {
            let draw = Self::HORN_AIR_PSI_PER_S * dt;
            self.primary_air_psi -= draw;
            self.secondary_air_psi -= draw * 0.5;
        }
        let mut application = self.brake.clamp(0.0, 1.0);
        if self.emergency_brake {
            application = 1.0;
        }
        let rising = (application - self.last_service_air_application).max(0.0);
        let hold = application * self.specs.air_loss_hold_psi_per_s * dt;
        if rising > 0.0 {
            self.primary_air_psi -= rising * self.specs.air_loss_primary_per_application_psi;
            self.secondary_air_psi -= rising * self.specs.air_loss_secondary_per_application_psi;
            self.trailer_air_psi -= rising * self.specs.air_loss_trailer_per_application_psi;
        }
        if application > 0.0 && !self.parking_brake {
            self.primary_air_psi -= hold * 1.15;
            self.secondary_air_psi -= hold * 0.95;
            self.trailer_air_psi -= hold * 0.55;
        }
        if self.emergency_brake {
            self.trailer_air_psi -= hold * 1.5;
        }
        self.primary_air_psi = self.clamp_air_psi(self.primary_air_psi);
        self.secondary_air_psi = self.clamp_air_psi(self.secondary_air_psi);
        self.trailer_air_psi = self.clamp_air_psi(self.trailer_air_psi);
        self.last_service_air_application = application;
    }
}
