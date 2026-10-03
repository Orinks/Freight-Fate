//! Liquid surge in a tank trailer: the load that keeps moving after you stop.
//!
//! A tank is never filled to the brim -- liquids expand in transit, and a dense
//! product would blow the axle weights long before the shell was full -- so a
//! tanker is always hauling a free surface. That surface is the whole problem.
//! Brake, and the liquid keeps going at the speed the truck was doing until it
//! piles up against the front head; a while later it runs back. Real drivers are
//! taught the consequence directly: the wave can shove a stopped tractor out into
//! the intersection, and it is why you brake early, gently, and once.
//!
//! The model here is the standard one: the free surface's first sloshing mode is
//! a damped oscillator riding in the tank, driven by the tank's own acceleration.
//!
//! ```text
//!     x'' + 2*zeta*w*x' + w^2 * x = -a_truck
//! ```
//!
//! `x` is how far the slug's centre of mass has moved from where it sits at
//! rest, positive forward. The liquid pushes back on the truck with
//!
//! ```text
//!     F = m_slug * (w^2 * x + 2*zeta*w*x')
//! ```
//!
//! which is positive -- forward, against the brakes -- exactly when the slug is
//! piled up front. Nothing in that is a fudge factor: it is Newton's third law on
//! the sloshing mass, and every behaviour drivers are warned about falls out of
//! it without being written in.
//!
//! Two properties of the solution do the design work:
//!
//! * The force lags the braking. `x` needs a quarter period to build, so the
//!   shove arrives seconds after the pedal went down -- and keeps arriving, in
//!   alternating directions, after the truck has stopped.
//! * Velocity leads displacement by a quarter period. The liquid is loudest --
//!   it is *moving* fastest -- a quarter cycle before it pushes hardest. The
//!   audio layer sonifies `x'` and therefore warns ahead of the force it is
//!   about to deliver, without predicting anything.
//!
//! Frequencies come from shallow-water theory for the first mode in a tank of
//! length `L` filled to depth `h`:
//!
//! ```text
//!     w = sqrt(g * k * tanh(k*h)),  k = pi / L
//! ```
//!
//! which for a 40-foot tank puts the fundamental between about 5.8 seconds (very
//! full) and 11 seconds (a quarter full) -- long, slow water, and a quarter of
//! that is one and a half to three seconds of honest warning.
//!
//! Sources for the behaviour this reproduces: California DMV Commercial Driver
//! Handbook section 8 (tank vehicles: outage, baffled and smooth bore, surge and
//! rollover), and the FMCSA tank-vehicle endorsement material behind it.
//!
//! Deterministic throughout: no RNG, no wall clock. Given a fill level, a tank
//! type and a history of accelerations, the wave is always the same wave.
//!
//! Port of `freight_fate/sim/surge.py`.

use std::f64::consts::PI;

use crate::data::corners::TRUCK_ROLLOVER_G;
use crate::data::curves::ADVISORY_ACCEPTABLE_MAX_G;

pub const G: f64 = 9.81;

// A road tanker is about forty feet of shell on a two-metre bore. Both feed
// the sloshing frequency, so they are named rather than buried in a constant.
pub const TANK_LENGTH_M: f64 = 12.2;
pub const TANK_DEPTH_M: f64 = 2.0;

// Baffles are transverse bulkheads with holes in them. The holes let the
// compartments talk, so the tank does not behave like four short tanks, but
// the wave has a much shorter run before it meets steel -- roughly half.
// Shorter run, higher frequency: a baffled load slaps quickly where a smooth
// bore rolls slowly, which is the difference a driver actually hears.
pub const BAFFLED_LENGTH_MULT: f64 = 0.5;

// How lightly the wave is damped, as a fraction of critical. A smooth bore is
// close to frictionless: the CDL manuals warn that once a smooth-bore load is
// swaying it will keep swaying, and 0.04 reproduces that -- perceptible for
// some ten cycles. Baffles are there precisely to spend that energy.
pub const ZETA_SMOOTH: f64 = 0.04;
pub const ZETA_BAFFLED: f64 = 0.28;

// Damping is only half of what baffles buy. The bulkheads also break the load
// into compartments that slosh largely independently and out of step with each
// other, so their reactions partly cancel and far less of the liquid arrives
// at the head as one slug. That reduction in participating mass -- not the
// damping -- is most of why a baffled tank is the forgiving one. Fore and aft
// only: side to side there is no bulkhead in the way and nothing is reduced.
pub const BAFFLED_MASS_MULT: f64 = 0.45;

// Baffles are transverse. They stand across the tank, so they are in the way
// of liquid running fore and aft and are not in the way of liquid running side
// to side. This single asymmetry is the reason a baffled tanker still rolls
// over, and it is the most important fact in the model.
pub const ZETA_LATERAL: f64 = ZETA_SMOOTH;

// The share of the liquid that actually participates in the first mode. A full
// tank has no free surface and an empty one has no liquid; the worst case is
// in the middle, which is why the manuals single out a half-full tank. The
// 4f(1-f) shape peaks at exactly half and vanishes at both ends.
pub const SLOSH_MASS_PEAK: f64 = 0.55;

// Liquids expand in transit, so room is always left above the load. Even a
// "full" tanker therefore carries a free surface and a little surge -- the
// reason a tanker never behaves quite like a solid load. (Kept internal: the
// trade calls this outage, but the game already uses that word for online
// services and a driver must not hear it mid-drive.)
pub const MAX_FILL_FRACTION: f64 = 0.97;

// How far the slug's centre of mass can travel before it is simply piled
// against the head and cannot go further, as a share of the run available.
// Beyond this the wave is breaking on steel, not translating.
pub const TRAVEL_FRACTION: f64 = 0.14;

// Curve advisories for trucks are posted around this lateral acceleration, so
// a bend taken at its advisory pulls about this much and one taken faster
// pulls with the square of the ratio.
pub const CURVE_DESIGN_LAT_G: f64 = 0.12;

/// The pull, on the scale above, at which a tank priced full goes over in a
/// bend whose sign is priced the way the game prices signs. DERIVED: the
/// wave is driven at `CURVE_DESIGN_LAT_G` where the bend asks the sign's
/// 0.30 g (`ADVISORY_ACCEPTABLE_MAX_G`), and the truck goes over at 0.35 g
/// (`TRUCK_ROLLOVER_G`), so the same ratio on this scale. It is the pull the
/// "twice the steady amplitude" reading is about; see
/// [`LiquidLoad::lateral_overshoot`].
pub const ROLLOVER_SURGE_PULL_G: f64 =
    CURVE_DESIGN_LAT_G * TRUCK_ROLLOVER_G / ADVISORY_ACCEPTABLE_MAX_G;

// Below this the wave is no longer worth a driver's attention: the load has
// settled. Expressed as a share of the travel limit so it means the same thing
// on every tank.
pub const SETTLED_TRAVEL_FRACTION: f64 = 0.06;

// How long the slug spends piling against the head once it gets there. The
// linear spring alone badly understates a smooth bore, because a long tank's
// wave is slow -- small omega, and omega squared times a bounded displacement
// is a modest force. What actually shoves the truck is the *arrival*: the
// whole moving slug stopping against the head over a fraction of a second.
// That impulse is the shove the manuals describe, it is why smooth bore is
// feared and baffles help (a damped wave arrives slowly, or never reaches the
// head at all), and it is the same event the audio layer plays as the hit.
pub const HEAD_IMPACT_S: f64 = 0.8;

// The oscillator is integrated at no coarser than this. A frame is normally
// far shorter, but a paused-and-resumed frame or a slow machine must not be
// allowed to make a stiff spring explode.
pub const MAX_SUBSTEP_S: f64 = 0.02;

/// How long a bend's sideways pull takes to build, in seconds. READ: AASHTO
/// Green Book 2018 Table 3-21 sizes the desirable spiral transition into a
/// curve as 2.0 s of travel, the natural path a vehicle steers. The game's
/// bends begin at a milepost with no transition of their own, so the lateral
/// wave is fed the pull the way the road would have built it; fed as a step,
/// every bend entry would throw the liquid as hard as a swerve does.
pub const SPIRAL_TRANSITION_S: f64 = 2.0;

/// How much of the liquid joins the first sloshing mode, 0 to 1.
///
/// Peaks at half full, which is the case every tanker manual warns about,
/// and falls to nothing at both ends.
pub fn fill_severity(fill_fraction: f64) -> f64 {
    let f = MAX_FILL_FRACTION.min(fill_fraction.max(0.0));
    (4.0 * f * (1.0 - f)).max(0.0)
}

/// One damped sloshing mode: displacement and velocity, nothing else.
#[derive(Debug, Clone, PartialEq)]
pub struct SloshAxis {
    pub omega: f64,
    pub zeta: f64,
    pub travel_m: f64,
    pub x: f64,
    pub v: f64,
    /// Set for exactly one frame when the slug reaches the end of its run and
    /// turns around -- the wave arriving at the head. The audio layer consumes
    /// it; nothing in the physics reads it.
    pub struck: bool,
    pub strike_strength: f64,
    /// Speed the slug carried into the head, and how much of the impact window
    /// is left to spend it over. This is where most of the shove lives.
    pub impact_v: f64,
    pub impact_left_s: f64,
}

impl SloshAxis {
    pub fn new(omega: f64, zeta: f64, travel_m: f64) -> Self {
        SloshAxis {
            omega,
            zeta,
            travel_m,
            x: 0.0,
            v: 0.0,
            struck: false,
            strike_strength: 0.0,
            impact_v: 0.0,
            impact_left_s: 0.0,
        }
    }

    /// Advance the mode under a tank acceleration of `drive_accel`.
    pub fn step(&mut self, dt: f64, drive_accel: f64) {
        self.struck = false;
        self.strike_strength = 0.0;
        if self.impact_left_s > 0.0 {
            self.impact_left_s = (self.impact_left_s - dt).max(0.0);
            if self.impact_left_s <= 0.0 {
                self.impact_v = 0.0;
            }
        }
        if dt <= 0.0 || self.omega <= 0.0 || self.travel_m <= 0.0 {
            return;
        }
        let steps = ((dt / MAX_SUBSTEP_S).ceil() as i64).max(1);
        let h = dt / steps as f64;
        for _ in 0..steps {
            let was_moving = self.v;
            // Semi-implicit Euler: stable for this spring at these steps, and
            // it conserves the phase relationship the audio layer depends on.
            let accel = -drive_accel
                - 2.0 * self.zeta * self.omega * self.v
                - self.omega * self.omega * self.x;
            self.v += accel * h;
            self.x += self.v * h;
            if self.x > self.travel_m {
                self.x = self.travel_m;
                self.strike(was_moving, false, true);
            } else if self.x < -self.travel_m {
                self.x = -self.travel_m;
                self.strike(was_moving, false, true);
            } else if was_moving != 0.0 && (was_moving > 0.0) != (self.v > 0.0) {
                // Turned around short of the head: the wave ran out of energy
                // rather than out of tank. Still the moment the push peaks.
                self.strike(was_moving, true, false);
            }
        }
    }

    fn strike(&mut self, incoming_v: f64, ran_out: bool, head_on: bool) {
        if self.struck {
            return;
        }
        let reach = if self.travel_m > 0.0 {
            self.x.abs() / self.travel_m
        } else {
            0.0
        };
        if ran_out && reach < SETTLED_TRAVEL_FRACTION {
            return;
        }
        if head_on {
            // The slug ran out of tank: it stops against the steel and spends
            // its momentum on the truck over the contact window. It stops --
            // liquid piles against a head, it does not bounce off it, and the
            // spring runs it back from there. It used to rebound at nearly its
            // full speed AND hand that speed to the truck, momentum made twice
            // over; the truck's lurch then threw the slug back harder still, so
            // every strike fed the next. Once a half-full tank's wave reached
            // the heads it ran itself up to 18 m/s end to end, shoving the
            // truck back and forth near half a g several times a second and
            // costing the load with no pedal moving (bend sweep, 2026-09-24:
            // 2.5 percent under adaptive cruise up Donner's 3.8 percent).
            self.impact_v = incoming_v;
            self.impact_left_s = HEAD_IMPACT_S;
            self.v = 0.0;
        }
        self.struck = true;
        self.strike_strength = (incoming_v.abs() / self.peak_v().max(1e-6)).min(1.0);
    }

    /// Acceleration per unit sloshing mass from the slug against the head,
    /// while the contact window lasts. Signed the way the slug was moving.
    pub fn impact_accel(&self) -> f64 {
        if self.impact_left_s <= 0.0 {
            return 0.0;
        }
        self.impact_v / HEAD_IMPACT_S
    }

    /// The velocity a slug swinging its full run would carry.
    pub fn peak_v(&self) -> f64 {
        self.omega * self.travel_m
    }

    /// How far out the slug is, 0 at rest, 1 against the head.
    pub fn reach(&self) -> f64 {
        if self.travel_m <= 0.0 {
            return 0.0;
        }
        (self.x.abs() / self.travel_m).min(1.0)
    }

    /// How fast the slug is running, 0 to 1. Leads [`SloshAxis::reach`] by a
    /// quarter period -- this is the anticipation, and it is free.
    pub fn motion(&self) -> f64 {
        let peak = self.peak_v();
        if peak <= 0.0 {
            return 0.0;
        }
        (self.v.abs() / peak).min(1.0)
    }

    pub fn settled(&self) -> bool {
        self.reach() < SETTLED_TRAVEL_FRACTION && self.motion() < SETTLED_TRAVEL_FRACTION
    }
}

/// A tank of liquid riding behind the driver, and how it behaves.
///
/// `fill_fraction` and `baffled` are properties of the load: they are
/// fixed when it is pumped on and they set the wave's size and its period.
/// They are spoken at pickup. What changes moment to moment is the wave.
#[derive(Debug, Clone, PartialEq)]
pub struct LiquidLoad {
    pub fill_fraction: f64,
    pub baffled: bool,
    pub tank_length_m: f64,
    pub longitudinal: SloshAxis,
    pub lateral: SloshAxis,
    /// The sideways pull the lateral wave is being driven by right now, in
    /// m/s2: the bend's pull, built up over [`SPIRAL_TRANSITION_S`].
    pub lateral_drive_mps2: f64,
}

impl Default for LiquidLoad {
    fn default() -> Self {
        LiquidLoad::new(0.5, false)
    }
}

impl LiquidLoad {
    /// `LiquidLoad(fill_fraction=..., baffled=...)` with the default tank.
    pub fn new(fill_fraction: f64, baffled: bool) -> Self {
        Self::with_tank_length(fill_fraction, baffled, TANK_LENGTH_M)
    }

    pub fn with_tank_length(fill_fraction: f64, baffled: bool, tank_length_m: f64) -> Self {
        let fill_fraction = MAX_FILL_FRACTION.min(fill_fraction.max(0.0));
        let severity = fill_severity(fill_fraction);
        let run = tank_length_m * (if baffled { BAFFLED_LENGTH_MULT } else { 1.0 });
        let travel = run * TRAVEL_FRACTION * severity;
        let longitudinal = SloshAxis::new(
            Self::omega_for(fill_fraction, severity, run),
            if baffled { ZETA_BAFFLED } else { ZETA_SMOOTH },
            travel,
        );
        // Side to side the tank is its bore, not its length, and no bulkhead
        // stands in the way. Short run, quick wave, undamped either way.
        let lateral = SloshAxis::new(
            Self::omega_for(fill_fraction, severity, TANK_DEPTH_M),
            ZETA_LATERAL,
            TANK_DEPTH_M * TRAVEL_FRACTION * severity,
        );
        LiquidLoad {
            fill_fraction,
            baffled,
            tank_length_m,
            longitudinal,
            lateral,
            lateral_drive_mps2: 0.0,
        }
    }

    /// First-mode sloshing frequency for a run of `run_m` at this fill.
    fn omega_for(fill_fraction: f64, severity: f64, run_m: f64) -> f64 {
        if run_m <= 0.0 || severity <= 0.0 {
            return 0.0;
        }
        let k = PI / run_m;
        let depth = (fill_fraction * TANK_DEPTH_M).max(0.05);
        (G * k * (k * depth).tanh()).sqrt()
    }

    pub fn severity(&self) -> f64 {
        fill_severity(self.fill_fraction)
    }

    /// How long one full fore-and-aft cycle takes. Rate is the danger:
    /// a slow, long wave is a big one.
    pub fn period_s(&self) -> f64 {
        let w = self.longitudinal.omega;
        if w > 0.0 {
            2.0 * PI / w
        } else {
            0.0
        }
    }

    /// How much of the liquid arrives as one slug on the given axis.
    pub fn slosh_mass_kg(&self, cargo_kg: f64, lateral: bool) -> f64 {
        let mut mass = cargo_kg.max(0.0) * SLOSH_MASS_PEAK * self.severity();
        if self.baffled && !lateral {
            mass *= BAFFLED_MASS_MULT;
        }
        mass
    }

    /// Advance both waves under the tank's own acceleration this frame.
    ///
    /// The sideways pull reaches the lateral wave along a transition: a bend
    /// that asks for its whole pull at once is built up to it over
    /// [`SPIRAL_TRANSITION_S`], and let go of the same way.
    pub fn update(&mut self, dt: f64, accel_mps2: f64, lateral_accel_mps2: f64) {
        let step = lateral_accel_mps2.abs().max(self.lateral_drive_mps2.abs())
            / SPIRAL_TRANSITION_S
            * dt.max(0.0);
        self.lateral_drive_mps2 +=
            (lateral_accel_mps2 - self.lateral_drive_mps2).clamp(-step, step);
        self.longitudinal.step(dt, accel_mps2);
        self.lateral.step(dt, self.lateral_drive_mps2);
    }

    /// How far the sideways wave has run PAST where the bend asking
    /// `pull_mps2` (on the [`lateral_accel_mps2`] scale) would hold it, as a
    /// share of the steady shift: 0 when it sits where the bend puts it (or
    /// has swung back toward the inside), 1 at twice the steady shift or more.
    ///
    /// Twice is the ceiling because that is what the reading gives: in a
    /// transient manoeuvre the liquid moves "with an amplitude ... that is
    /// twice the level of the steady-state amplitude" (NTSB HAR-11/01 2.3.4,
    /// citing Winkler et al., SAE RR-004). An undamped wave kicked by a step
    /// reaches exactly that, so the oscillator and the report agree.
    ///
    /// Two things this is careful about, both found by the bend sweep
    /// (2026-09-24), where a half-full tank went over at 50 in a gentle bend
    /// on the Siskiyou and at 23 on US-62 with every assist holding it under
    /// its number:
    ///
    /// - The pull is the one the bend under the truck asks NOW, passed in,
    ///   not the drive still being built toward it or the last frame's bend:
    ///   either read a bend's first foot as the whole overshoot.
    /// - The reading is about pulls where the tank goes over. Far below
    ///   that, a leftover swing from the last bend is a small shift of the
    ///   liquid in absolute terms, but as a share of a gentle bend's tiny
    ///   steady shift it read as the whole overshoot and halved the
    ///   threshold. So the share is taken of the steady shift at
    ///   [`ROLLOVER_SURGE_PULL_G`] wherever the bend asks less; at and past
    ///   it, of the bend's own, exactly as the reading is written.
    pub fn lateral_overshoot(&self, pull_mps2: f64) -> f64 {
        let axis = &self.lateral;
        if axis.omega <= 0.0 {
            return 0.0;
        }
        // The spring's rest point under the bend's pull: x'' = -a - w^2 x.
        let w2 = axis.omega * axis.omega;
        let steady = -pull_mps2 / w2;
        if steady.abs() < 1e-9 {
            return 0.0;
        }
        let reference = steady.abs().max(ROLLOVER_SURGE_PULL_G * G / w2);
        let outward = axis.x * steady.signum();
        ((outward - steady.abs()) / reference).clamp(0.0, 1.0)
    }

    /// The overshoot a bend entered along its transition leaves behind: what
    /// an undamped wave of this tank's frequency keeps after a pull ramped in
    /// over [`SPIRAL_TRANSITION_S`], `|sin(wT/2) / (wT/2)|`. DERIVED, the
    /// ramp response of the same oscillator; a property of the tank, so the
    /// assists can price a bend before the truck is in it.
    pub fn entry_overshoot(&self) -> f64 {
        let half = self.lateral.omega * SPIRAL_TRANSITION_S / 2.0;
        if half <= 0.0 {
            return 0.0;
        }
        (half.sin() / half).abs().min(1.0)
    }

    /// The overshoot to plan the next bend against: what a bend entered from
    /// rest leaves ([`Self::entry_overshoot`]), plus the swing the liquid is
    /// still carrying from the last one, on the scale
    /// [`Self::lateral_overshoot`] uses where a bend asks less than the
    /// rollover pull.
    ///
    /// The swing is the free wave's amplitude about where the pull driving it
    /// now would hold it, `sqrt(dx^2 + (v/w)^2)`: its energy, not where it
    /// happens to be this frame, so the price does not breathe with the wave
    /// the way the position does. It is what the next bend can find
    /// running outward at its entry whatever the phase; the wave is nearly
    /// undamped (`ZETA_LATERAL`), so in a run of bends it survives from one
    /// to the next. Priced from rest, a half-full tank held under its number
    /// on I-90's Lookout Pass came within 0.98 of rolling with no warning
    /// (bend sweep, 2026-09-24).
    pub fn planning_overshoot(&self) -> f64 {
        let axis = &self.lateral;
        if axis.omega <= 0.0 {
            return 0.0;
        }
        let w2 = axis.omega * axis.omega;
        let dx = axis.x + self.lateral_drive_mps2 / w2;
        let swing = (dx * dx + (axis.v / axis.omega).powi(2)).sqrt();
        let reference = ROLLOVER_SURGE_PULL_G * G / w2;
        (self.entry_overshoot() + swing / reference).min(1.0)
    }

    /// What the liquid is doing to the truck right now, newtons.
    ///
    /// Positive is forward: the slug piled against the front head pushing the
    /// truck on through the stop it was trying to make.
    pub fn force_n(&self, cargo_kg: f64) -> f64 {
        let axis = &self.longitudinal;
        if axis.omega <= 0.0 {
            return 0.0;
        }
        let m = self.slosh_mass_kg(cargo_kg, false);
        let spring = axis.omega * axis.omega * axis.x + 2.0 * axis.zeta * axis.omega * axis.v;
        m * (spring + axis.impact_accel())
    }

    /// The hardest forward shove this load can deliver, newtons.
    ///
    /// A property of the load rather than of the moment, so a stopping
    /// distance built on it is a stable number a driver can learn instead of
    /// one that breathes with the wave.
    ///
    /// Dominated by the head impact: a slug swinging its full run arrives at
    /// `omega * travel` and stops against the steel over the contact
    /// window. That is why a smooth bore is the frightening one -- barely
    /// damped, it arrives at nearly full speed every time -- and why baffles
    /// help, because a damped wave arrives slowly or not at all.
    pub fn peak_force_n(&self, cargo_kg: f64) -> f64 {
        let axis = &self.longitudinal;
        if axis.omega <= 0.0 {
            return 0.0;
        }
        let m = self.slosh_mass_kg(cargo_kg, false);
        // How much of a full swing survives one quarter cycle of damping.
        let arrival = axis.peak_v() * (-axis.zeta * PI / 2.0).exp();
        let impact = m * arrival / HEAD_IMPACT_S;
        let spring = m * axis.omega * axis.omega * axis.travel_m;
        impact + spring
    }

    /// How much the side-to-side wave adds to what a bend is already
    /// asking of the tyres, as a share. Baffles do nothing here.
    pub fn lateral_load_factor(&self) -> f64 {
        self.lateral.reach() * self.severity()
    }

    pub fn settled(&self) -> bool {
        self.longitudinal.settled() && self.lateral.settled()
    }

    pub fn describe_tank(&self) -> &'static str {
        if self.baffled {
            "baffled"
        } else {
            "smooth bore"
        }
    }

    /// How full the tank is, in words. Never "outage" -- see the note on
    /// `MAX_FILL_FRACTION`.
    pub fn describe_fill(&self) -> &'static str {
        let f = self.fill_fraction;
        if f >= 0.9 {
            return "nearly full";
        }
        if f >= 0.7 {
            return "three quarters full";
        }
        if f >= 0.55 {
            return "over half full";
        }
        if f >= 0.45 {
            return "half full";
        }
        if f >= 0.3 {
            return "a third full";
        }
        "lightly loaded"
    }
}

/// What `liquid_load_for` asks of a cargo type: the Python duck-typed
/// `cargo.tank`, `cargo.baffled` and `cargo.fill_fraction(weight_tons)`.
/// `models::jobs::Cargo` implements this.
pub trait LiquidCargo {
    fn tank(&self) -> bool;
    fn baffled(&self) -> bool {
        false
    }
    fn fill_fraction(&self, weight_tons: f64) -> f64;
}

/// The tank aboard for this load, or None if the freight is not liquid.
///
/// Everything the wave does follows from the job: how full the shell is comes
/// from the load's weight against the tank's capacity, and whether it is
/// baffled is a property of the product. The same job therefore always drives
/// the same way -- no randomness anywhere, because a penalty a driver cannot
/// learn to avoid is not a skill test.
pub fn liquid_load_for(cargo: Option<&dyn LiquidCargo>, weight_tons: f64) -> Option<LiquidLoad> {
    let cargo = cargo?;
    if !cargo.tank() {
        return None;
    }
    let fill = cargo.fill_fraction(weight_tons);
    if fill <= 0.0 {
        return None;
    }
    Some(LiquidLoad::new(fill, cargo.baffled()))
}

/// What a bend posted at `advisory_mph` pulls when taken at `speed_mph`.
///
/// Advisories are set around a design lateral acceleration, so the pull goes
/// with the square of how far over the posting the truck is.
pub fn lateral_accel_mps2(speed_mph: f64, advisory_mph: f64) -> f64 {
    if advisory_mph <= 0.0 || speed_mph <= 0.0 {
        return 0.0;
    }
    let ratio = speed_mph / advisory_mph;
    CURVE_DESIGN_LAT_G * G * ratio * ratio
}

#[cfg(test)]
mod tests {
    //! The surge-only half of `tests/test_tanker_surge.py`; the tests that
    //! put the load behind a truck live in `sim::vehicle::tests`.
    use super::*;

    const CARGO_KG: f64 = 20_000.0;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() <= 1e-6 * b.abs().max(1e-12)
    }

    fn argmax(values: &[f64]) -> usize {
        let mut best = 0;
        for (i, v) in values.iter().enumerate() {
            if *v > values[best] {
                best = i;
            }
        }
        best
    }

    #[test]
    fn test_only_tank_cargo_gets_a_liquid_load() {
        use crate::models::jobs::cargo_type;
        for key in ["general", "electronics", "steel", "grain", "refrigerated"] {
            let cargo: &dyn LiquidCargo = cargo_type(key).unwrap();
            assert!(liquid_load_for(Some(cargo), 20.0).is_none(), "{key}");
        }
        assert!(liquid_load_for(None, 20.0).is_none());
        let fuel: &dyn LiquidCargo = cargo_type("fuel_bulk").unwrap();
        assert!(liquid_load_for(Some(fuel), 13.0).is_some());
    }

    #[test]
    fn test_fill_severity_is_worst_at_half_and_vanishes_at_both_ends() {
        assert!(approx(fill_severity(0.5), 1.0));
        assert_eq!(fill_severity(0.0), 0.0);
        assert!(approx(fill_severity(0.25), fill_severity(0.75)));
        // A tank is never filled to the brim -- liquids expand in transit -- so
        // even a "full" load keeps a little free surface, and a little surge.
        assert!(0.0 < fill_severity(1.0) && fill_severity(1.0) < 0.2);
        assert_eq!(LiquidLoad::new(1.0, false).fill_fraction, MAX_FILL_FRACTION);
    }

    #[test]
    fn test_baffles_shorten_the_period_and_smooth_bore_is_the_slow_heavy_one() {
        let smooth = LiquidLoad::new(0.5, false);
        let baffled = LiquidLoad::new(0.5, true);
        // Rate carries the danger: the slow wave is the big one.
        assert!(smooth.period_s() > baffled.period_s() * 1.5);
        assert!(5.0 < smooth.period_s() && smooth.period_s() < 12.0);
        assert!(baffled.period_s() < 5.0);
        assert!(approx(
            baffled.slosh_mass_kg(CARGO_KG, false),
            smooth.slosh_mass_kg(CARGO_KG, false) * BAFFLED_MASS_MULT
        ));
    }

    #[test]
    fn test_baffles_do_nothing_at_all_for_lateral_surge() {
        // The single most important asymmetry in the model, and the reason a
        // baffled tanker still rolls over.
        let smooth = LiquidLoad::new(0.5, false);
        let baffled = LiquidLoad::new(0.5, true);
        assert_eq!(baffled.lateral.zeta, smooth.lateral.zeta);
        assert!(approx(baffled.lateral.omega, smooth.lateral.omega));
        assert!(approx(baffled.lateral.travel_m, smooth.lateral.travel_m));
        assert!(approx(
            baffled.slosh_mass_kg(CARGO_KG, true),
            smooth.slosh_mass_kg(CARGO_KG, true)
        ));
    }

    #[test]
    fn test_the_force_arrives_after_the_braking_not_with_it() {
        // Surge is a lag, not a multiplier. If the shove were simultaneous it
        // would just be a weaker brake; the delay is the whole hazard.
        fn trace(decel: f64) -> Vec<f64> {
            let mut load = LiquidLoad::new(0.5, false);
            let mut out = Vec::new();
            for step in 0..400 {
                // 8 s; braking for the first two
                load.update(0.02, if step < 100 { -decel } else { 0.0 }, 0.0);
                out.push(load.force_n(CARGO_KG));
            }
            out
        }

        let forces = trace(4.0);
        let peak = forces.iter().cloned().fold(f64::MIN, f64::max);
        let peak_at = argmax(&forces) as f64 * 0.02;
        assert!(peak > 0.0);
        // Essentially nothing at the moment the pedal goes down: the liquid has
        // not gone anywhere yet.
        assert!(forces[0] < 0.01 * peak);
        assert!(peak_at > 0.5); // the shove is most of a second behind the pedal
                                // And it keeps coming back after the driver has stopped braking.
        assert!(forces[150..].iter().cloned().fold(f64::MIN, f64::max) > 0.0);

        // Brake gently and the wave takes longer to arrive -- it has to travel the
        // tank either way, and a soft application does not throw it forward as
        // fast. Braking early and gently is the whole tanker technique.
        let gentle = trace(1.2);
        let gentle_at = argmax(&gentle) as f64 * 0.02;
        assert!(gentle_at > peak_at);
        assert!(gentle.iter().cloned().fold(f64::MIN, f64::max) < peak);
    }

    #[test]
    fn test_the_liquid_is_loudest_before_it_pushes_hardest() {
        // The anticipation the audio layer is built on: the oscillator's velocity
        // leads its displacement by a quarter period, so sonifying motion warns
        // ahead of the force without predicting anything.
        let mut load = LiquidLoad::new(0.5, false);
        let mut motion = Vec::new();
        let mut reach = Vec::new();
        for step in 0..500 {
            load.update(0.02, if step < 100 { -4.0 } else { 0.0 }, 0.0);
            motion.push(load.longitudinal.motion());
            reach.push(load.longitudinal.reach());
        }
        let motion_peak = argmax(&motion);
        let reach_peak = argmax(&reach);
        assert!(motion_peak < reach_peak);
        let lead_s = (reach_peak - motion_peak) as f64 * 0.02;
        // A quarter of a seven-to-eight second period: over a second of warning.
        assert!(lead_s > 0.5);
    }

    #[test]
    fn test_the_wave_settles_and_says_so() {
        let mut baffled = LiquidLoad::new(0.5, true);
        for step in 0..2000 {
            baffled.update(0.02, if step < 100 { -4.0 } else { 0.0 }, 0.0);
        }
        assert!(baffled.settled());
    }

    #[test]
    fn test_a_smooth_bore_is_still_moving_long_after_a_baffled_one_has_settled() {
        let mut smooth = LiquidLoad::new(0.5, false);
        let mut baffled = LiquidLoad::new(0.5, true);
        for step in 0..600 {
            // 12 s
            let drive = if step < 100 { -4.0 } else { 0.0 };
            smooth.update(0.02, drive, 0.0);
            baffled.update(0.02, drive, 0.0);
        }
        assert!(baffled.settled());
        assert!(!smooth.settled());
    }

    #[test]
    fn test_the_wave_is_deterministic() {
        // No RNG and no wall clock: an unlearnable penalty is not a skill test.
        let mut runs: Vec<Vec<(f64, f64)>> = Vec::new();
        for _ in 0..2 {
            let mut load = LiquidLoad::new(0.42, false);
            let mut trace = Vec::new();
            for step in 0..300 {
                load.update(0.02, if step < 90 { -3.5 } else { 0.4 }, 0.0);
                trace.push((load.longitudinal.x, load.longitudinal.v));
            }
            runs.push(trace);
        }
        assert_eq!(runs[0], runs[1]);
    }

    #[test]
    fn test_a_coarse_frame_does_not_blow_up_the_oscillator() {
        let mut load = LiquidLoad::new(0.5, false);
        for _ in 0..50 {
            load.update(0.5, -4.0, 0.0); // half-second frames: a stall or a resume
        }
        assert!(load.longitudinal.x.is_finite());
        assert!(load.longitudinal.x.abs() <= load.longitudinal.travel_m + 1e-9);
    }

    #[test]
    fn test_a_bend_pulls_harder_the_further_over_the_advisory_you_take_it() {
        let at_advisory = lateral_accel_mps2(35.0, 35.0);
        let over = lateral_accel_mps2(45.0, 35.0);
        assert!(over > at_advisory);
        assert!(approx(over / at_advisory, (45.0_f64 / 35.0).powi(2)));
        assert_eq!(lateral_accel_mps2(45.0, 0.0), 0.0); // a straight pulls nothing
    }

    #[test]
    fn test_outage_is_never_spoken() {
        // Correct tanker jargon, but the game already uses the word for online
        // services -- a driver hearing it mid-drive would think the site dropped.
        for fill in [0.1, 0.3, 0.5, 0.8, 0.97] {
            let spoken = LiquidLoad::new(fill, false).describe_fill();
            assert!(!spoken.to_lowercase().contains("outage"));
            assert!(!spoken.to_lowercase().contains("ullage"));
            assert!(spoken.contains("full") || spoken.contains("loaded"));
        }
    }

    #[test]
    fn test_how_full_the_tank_is_comes_from_the_load_weight() {
        use crate::models::jobs::cargo_type;
        use crate::models::trailers::TANK_CAPACITY_TONS;
        let cargo = cargo_type("fuel_bulk").unwrap();
        assert!((cargo.fill_fraction(TANK_CAPACITY_TONS / 2.0) - 0.5).abs() < 1e-9);
        assert_eq!(cargo.fill_fraction(TANK_CAPACITY_TONS * 2.0), 1.0);
        assert_eq!(cargo_type("general").unwrap().fill_fraction(13.0), 0.0);
        // The same job therefore always drives the same way.
        let tank: &dyn LiquidCargo = cargo;
        let a = liquid_load_for(Some(tank), 13.0).unwrap();
        let b = liquid_load_for(Some(tank), 13.0).unwrap();
        assert_eq!(a.fill_fraction, b.fill_fraction);
        assert_eq!(a.period_s(), b.period_s());
    }
}
