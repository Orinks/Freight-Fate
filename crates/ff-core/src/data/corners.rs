//! Corner speed for a street turn, from the corner's own turn angle.
//!
//! The advisory a bend on a leg gets comes from `data::curves`, which reads a
//! baked radius. A street corner has no baked radius -- what the map can
//! honestly measure at a junction is the signed heading change, the turn
//! ANGLE -- so this module turns that angle into a speed the way an
//! intersection designer does: angle picks the design radius, radius and a
//! lateral limit pick the speed.
//!
//! What this replaced, and why (owner directive 2026-08-21, after a Spokane
//! arrival he could not follow; `docs/turn-geometry-brief.md` is the standing
//! record): the old corner speed was the street's posted limit clamped between
//! 15 and 20 mph, both ends assumed constants with no cited basis. Every corner
//! in the game got the same answer, from a sweeping 60-degree bend onto an
//! arterial to a square left into a yard. The 15 floor had a second effect
//! worse than the number: a truck already held at 14-15 by the speed keeper was
//! under EVERY corner, so the advisory never spoke at all.
//!
//! # Provenance
//!
//! **Radius is READ** from TxDOT Roadway Design Manual Table 13-7, "Minimum
//! Edge of Pavement Designs for Right Turns for Various Design Vehicles for
//! Turn Angle Varying from 60 to 120 Degrees", WB-67 row. The table's own note:
//! "Values are calculated based on the design vehicle's turning path from the
//! outermost lane of the approach roadway to the outermost lane of the crossing
//! roadway."
//! <https://www.txdot.gov/manuals/des/rdw/chapter-13--intersections/13-10-additional-intersection-design-consideration/13-10-1-minimum-turning-radii.html>
//!
//! Which of the table's three designs to read was the open modelling decision
//! the brief left open, and it is decided here on the geometry. The SIMPLE
//! curve (125 ft at 90 degrees) is the curb return of a design with no
//! transition, and priced at a passenger car's side friction it gives 22-24 mph
//! -- FASTER than the clamp it replaces and plainly wrong for a loaded semi.
//! The 3-centered compound design is the standard one, and its MIDDLE radius is
//! the tightest arc the corner actually contains: 440-65-440 at 90 degrees, so
//! 65 ft. That is the number used. The cross-check that settles it is the
//! table's own 120-degree row, whose middle radius is 45 ft -- the WB-67's
//! minimum design turning radius, i.e. the design has the truck at full lock,
//! which is exactly what a 120-degree corner should mean.
//!
//! **Lateral limit is DERIVED**, from three published numbers and a stated
//! principle: a truck driver holds the same margin below their vehicle's
//! rollover threshold that a car driver holds below theirs.
//!
//! - Cars corner at a MEASURED lateral. TTI 0-4365-4 Table 23 regresses the
//!   85th-percentile free-flow speed near the middle of a right turn as
//!   `V85 = 14.87 + 0.23*Chan + 0.06*CR` mph (`Chan` 0 for a raised island,
//!   `CR` the corner radius in feet, lane length and width at their study
//!   averages). At `CR` 65 ft that is 18.8 mph, which is 0.361 g.
//!   <https://static.tti.tamu.edu/tti.tamu.edu/documents/0-4365-4.pdf>
//! - A car's rollover threshold is its static stability factor, whose
//!   sales-weighted average for passenger cars is 1.41 g.
//!   <https://crashstats.nhtsa.dot.gov/Api/Public/ViewPublication/809868>
//!   So a car takes a city corner at about a quarter of what would roll it.
//! - A loaded tractor-semitrailer's satisfactory static rollover threshold is
//!   0.35 g, and rearward amplification is about 1.0 for this combination, so
//!   the trailer does not amplify it. NHTSA DOT HS 811 734; FHWA
//!   <https://www.fhwa.dot.gov/reports/tswstudy/vehiclsaf.htm>
//!
//! The same fraction of 0.35 g is [`corner_lateral_g`] at full load, about
//! 0.090 g, and the whole model reduces to the truck taking a corner at
//! `sqrt(0.35/1.41)` -- almost exactly half -- of the speed a car takes it at.
//!
//! **The rollover threshold is the LOADED one, so it moves with the load.**
//! 0.35 g describes a van with freight stacked in it; an empty trailer's mass
//! is its own body, sitting much lower, and it does not roll at a ninth of a g.
//! Until 2026-09-20 every corner was priced as though the trailer were full,
//! so a driver deadheading to a pickup was held to 9 mph at a square corner --
//! the owner's report, driving empty to collect a load. The span is DERIVED
//! from UMTRI-83-10 (Ervin et al., "Influence of Size and Weight Variables on
//! the Stability and Control Properties of Heavy Trucks", for FHWA), whose
//! Figure 38 measures the five-axle tractor-semitrailer's rollover threshold
//! against payload centre-of-gravity height: "The strength of the influence is
//! nominally -0.01 g's per inch of payload c.g. height." The same report's
//! Figure 33 states the empty van body's own c.g. height, 60 inches, and puts
//! the load floor at "52 to 55 inches above the ground". Taking the 0.35 g
//! figure as the loaded van it describes -- payload c.g. near 95 inches, the
//! height at which Figure 38's line passes 0.35 g -- and walking that slope
//! down to the empty body's 60 inches gives [`EMPTY_ROLLOVER_G`], 0.70 g.
//! <https://rosap.ntl.bts.gov/view/dot/68509>
//!
//! Between the two ends the threshold is interpolated on the load, which is a
//! straight-line stand-in for the mass-weighted composite c.g. the report
//! actually plots. `tests::the_load_span_tracks_the_composite_centre` runs
//! that composite model and holds the difference under a mile an hour, in the
//! conservative direction: a half-loaded trailer is priced a little slower
//! than its centre of gravity says it has to be, never faster.
//!
//! **Nothing here is ASSUMED except a missing angle.** A corner whose angle the
//! map could not measure is priced at [`ASSUMED_TURN_DEG`], the modal city
//! corner, and callers that care can tell the two apart because the angle
//! arrives as an `Option`.
//!
//! # Calibration
//!
//! The brief set the gate before the model was built: a typical 90-degree city
//! corner must land in the 5-12 mph band that CDL practice and the bottom of
//! the measured TTI distribution both point at, and must never exceed the
//! measured 85th-percentile CAR speed for the same radius. A 90-degree corner
//! comes out at 9.4 mph against a car's 18.8, so it passes both, and it passes
//! them without a constant having been moved: CDL practice was never an input.
//! `tests::the_model_meets_its_calibration_gate` is that check, kept executable
//! so a later edit to any constant has to face it.

/// TxDOT Table 13-7, WB-67 row: turn angle in degrees against the middle
/// radius of the 3-centered compound symmetric design, in feet. Read from the
/// table; the table itself stops at these five angles.
pub const WB67_CORNER_RADII_FT: [(f64, f64); 5] = [
    (60.0, 100.0),
    (75.0, 75.0),
    (90.0, 65.0),
    (105.0, 50.0),
    (120.0, 45.0),
];

/// TTI 0-4365-4 Table 23, the middle-of-turn 85th-percentile equation with a
/// raised island and the study's average lane length and width:
/// `V85 = 14.87 + 0.06 * CR`.
pub const TTI_V85_INTERCEPT_MPH: f64 = 14.87;
pub const TTI_V85_PER_FT: f64 = 0.06;
/// The radius the lateral limit is calibrated at: the 90-degree corner, which
/// is both the modal city corner and inside TTI's 27-86 ft data limits.
pub const CALIBRATION_RADIUS_FT: f64 = 65.0;

/// NHTSA sales-weighted average static stability factor for passenger cars.
pub const CAR_ROLLOVER_G: f64 = 1.41;
/// Satisfactory static rollover threshold for a loaded tractor-semitrailer.
pub const TRUCK_ROLLOVER_G: f64 = 0.35;

/// UMTRI-83-10 Figure 38: how far the rollover threshold moves per inch of
/// payload centre-of-gravity height, in g.
pub const ROLLOVER_G_PER_PAYLOAD_IN: f64 = 0.01;
/// The payload centre-of-gravity height [`TRUCK_ROLLOVER_G`] describes: where
/// Figure 38's line passes 0.35 g, and within an inch or two of a van loaded
/// off a 52-55 inch floor to the 70/30 bottom/top split FHWA reports.
pub const LOADED_PAYLOAD_CG_IN: f64 = 95.0;
/// The empty van body's own centre-of-gravity height, from the Figure 33 case
/// ("Trailer Body - 9000 lbs, Body C.G. Height - 60 inches").
pub const EMPTY_BODY_CG_IN: f64 = 60.0;

/// Static rollover threshold with nothing in the trailer, in g.
pub const EMPTY_ROLLOVER_G: f64 =
    TRUCK_ROLLOVER_G + ROLLOVER_G_PER_PAYLOAD_IN * (LOADED_PAYLOAD_CG_IN - EMPTY_BODY_CG_IN);

/// The point-mass control every design manual republishes, `V = sqrt(15 R
/// (e + f))`, with `e = 0`: an at-grade intersection is not superelevated.
pub const INTERSECTION_SUPERELEVATION: f64 = 0.0;

/// A corner the map could not measure is priced as a square one. Ninety
/// degrees is the modal city corner and the middle of the table, so an
/// unmeasured corner is neither the most nor the least forgiving guess.
pub const ASSUMED_TURN_DEG: f64 = 90.0;

/// How fast a car is measured to take the calibration corner, in g.
fn car_lateral_g() -> f64 {
    let v85 = TTI_V85_INTERCEPT_MPH + TTI_V85_PER_FT * CALIBRATION_RADIUS_FT;
    (v85 * v85) / (15.0 * CALIBRATION_RADIUS_FT)
}

/// The static rollover threshold of a combination carrying `load_fraction` of
/// a full payload, in g. Empty is [`EMPTY_ROLLOVER_G`], full is
/// [`TRUCK_ROLLOVER_G`], and a bobtail tractor is priced as empty.
pub fn rollover_threshold_g(load_fraction: f64) -> f64 {
    let load = load_fraction.clamp(0.0, 1.0);
    EMPTY_ROLLOVER_G + (TRUCK_ROLLOVER_G - EMPTY_ROLLOVER_G) * load
}

/// The lateral a combination carrying `load_fraction` takes a street corner
/// at, in g.
///
/// Computed from the published constants above rather than typed in, so a
/// correction to any of them moves the model instead of being argued with it.
pub fn corner_lateral_g(load_fraction: f64) -> f64 {
    (car_lateral_g() / CAR_ROLLOVER_G) * rollover_threshold_g(load_fraction)
}

/// The design radius for a turn of `turn_deg`, in feet.
///
/// Interpolated linearly between the table's rows. Outside the table the ends
/// hold: below 60 degrees because the table does not go there and extrapolating
/// a design radius upward is not supported by anything (a gentle junction is
/// governed by the street's posted limit, which [`corner_speed_mph`]'s caller
/// applies), and above 120 because 45 ft is already the WB-67's minimum turning
/// radius -- the truck is at full lock and a sharper corner cannot be taken
/// faster, only wider.
pub fn corner_radius_ft(turn_deg: f64) -> f64 {
    let first = WB67_CORNER_RADII_FT[0];
    let last = WB67_CORNER_RADII_FT[WB67_CORNER_RADII_FT.len() - 1];
    if turn_deg <= first.0 {
        return first.1;
    }
    if turn_deg >= last.0 {
        return last.1;
    }
    for pair in WB67_CORNER_RADII_FT.windows(2) {
        let (lo_deg, lo_ft) = pair[0];
        let (hi_deg, hi_ft) = pair[1];
        if turn_deg <= hi_deg {
            let t = (turn_deg - lo_deg) / (hi_deg - lo_deg);
            return lo_ft + t * (hi_ft - lo_ft);
        }
    }
    last.1
}

/// The speed a combination carrying `load_fraction` takes a corner of
/// `turn_deg` at, in mph.
///
/// `None` is a corner whose angle the map could not measure, priced at
/// [`ASSUMED_TURN_DEG`].
pub fn corner_speed_mph(turn_deg: Option<f64>, load_fraction: f64) -> f64 {
    let radius = corner_radius_ft(turn_deg.unwrap_or(ASSUMED_TURN_DEG));
    let lateral = INTERSECTION_SUPERELEVATION + corner_lateral_g(load_fraction);
    (15.0 * radius * lateral).sqrt()
}

/// The measured 85th-percentile CAR speed through the same corner, in mph.
///
/// Not a speed the game ever posts. It exists because the calibration gate is
/// written against it: whatever the truck model says, it may never come out
/// above what cars were actually clocked doing.
pub fn car_speed_mph(turn_deg: Option<f64>) -> f64 {
    let radius = corner_radius_ft(turn_deg.unwrap_or(ASSUMED_TURN_DEG));
    TTI_V85_INTERCEPT_MPH + TTI_V85_PER_FT * radius
}

#[cfg(test)]
mod tests {
    use super::*;

    fn close(a: f64, b: f64, tol: f64) -> bool {
        (a - b).abs() <= tol
    }

    #[test]
    fn the_model_meets_its_calibration_gate() {
        // docs/turn-geometry-brief.md, written before the model existed:
        // a typical 90-degree city corner lands in 5-12 mph, and never above
        // the measured 85th-percentile car speed for the same radius.
        let square = corner_speed_mph(Some(90.0), 1.0);
        assert!(
            (5.0..=12.0).contains(&square),
            "a 90-degree corner came out at {square} mph, outside the 5-12 band \
             CDL practice and the TTI distribution point at"
        );
        // The car ceiling holds at every load, not just the loaded one: an
        // empty trailer is more stable than a full one, never more stable
        // than the cars that were clocked through the same corner.
        for deg in [60.0, 75.0, 90.0, 105.0, 120.0, 150.0, 180.0] {
            let car = car_speed_mph(Some(deg));
            for load in [0.0, 0.25, 0.5, 0.75, 1.0] {
                let truck = corner_speed_mph(Some(deg), load);
                assert!(
                    truck < car,
                    "a {deg}-degree corner at {load} load priced the truck at {truck} mph, \
                     at or above the {car} mph cars were measured taking it"
                );
            }
        }
    }

    #[test]
    fn an_empty_trailer_corners_faster_than_a_loaded_one() {
        // The owner's report, 2026-09-20: deadheading to a pickup and held to
        // 9 mph at a square corner, which is the speed a FULL trailer's centre
        // of gravity asks for.
        let empty = corner_speed_mph(Some(90.0), 0.0);
        let full = corner_speed_mph(Some(90.0), 1.0);
        assert!(
            empty > full + 3.0,
            "empty came out at {empty} mph against {full} loaded -- the load is \
             not reaching the corner model"
        );
        assert!(close(EMPTY_ROLLOVER_G, 0.70, 1e-9));
        assert!(
            close(empty, 13.2, 0.05),
            "empty square corner is {empty} mph"
        );

        // And it is a ladder, not a switch: every step of loading is slower
        // than the one before it.
        let mut previous = f64::INFINITY;
        for step in 0..=10 {
            let speed = corner_speed_mph(Some(90.0), f64::from(step) / 10.0);
            assert!(
                speed <= previous + 1e-9,
                "load {step} of 10 came out faster"
            );
            previous = speed;
        }
    }

    #[test]
    fn the_load_span_tracks_the_composite_centre() {
        // The straight line between empty and loaded stands in for the
        // mass-weighted composite centre of gravity UMTRI-83-10 Figure 33
        // plots. Its case: a 9000 lb van body at 60 inches, 50000 lb of
        // payload, a 52-55 inch load floor, and homogeneous freight stacked
        // to the load fraction inside a 110-inch box, sitting at the 70/30
        // bottom/top split (so 0.40 of the stack height above the floor).
        const BODY_LB: f64 = 9_000.0;
        const PAYLOAD_LB: f64 = 50_000.0;
        const FLOOR_IN: f64 = 53.5;
        const BOX_IN: f64 = 110.0;
        const STACK_SHARE: f64 = 0.40;

        let composite_cg = |load: f64| {
            let payload = PAYLOAD_LB * load;
            let payload_cg = FLOOR_IN + STACK_SHARE * BOX_IN * load;
            (BODY_LB * EMPTY_BODY_CG_IN + payload * payload_cg) / (BODY_LB + payload)
        };
        // Figure 38's slope is per inch of PAYLOAD c.g.; Figure 33's line
        // converts it to per inch of composite c.g.
        let per_composite_in = ROLLOVER_G_PER_PAYLOAD_IN / (PAYLOAD_LB / (BODY_LB + PAYLOAD_LB));
        let loaded_cg = composite_cg(1.0);
        let composite_speed = |load: f64| {
            let threshold = TRUCK_ROLLOVER_G + per_composite_in * (loaded_cg - composite_cg(load));
            let lateral = (car_lateral_g() / CAR_ROLLOVER_G) * threshold;
            (15.0 * CALIBRATION_RADIUS_FT * lateral).sqrt()
        };

        for step in 0..=10 {
            let load = f64::from(step) / 10.0;
            let shipped = corner_speed_mph(Some(90.0), load);
            let modelled = composite_speed(load);
            assert!(
                shipped <= modelled + 1e-9,
                "at {load} load the shipped {shipped:.2} mph is FASTER than the \
                 {modelled:.2} mph the composite centre allows"
            );
            assert!(
                modelled - shipped < 1.0,
                "at {load} load the shipped {shipped:.2} mph is {:.2} mph under the \
                 composite model's {modelled:.2}",
                modelled - shipped
            );
        }
    }

    #[test]
    fn the_lateral_limit_is_the_truck_share_of_the_car_margin() {
        // The derivation, asserted rather than described: cars corner at about
        // a quarter of what would roll them, and the truck gets that same
        // quarter of 0.35 g.
        assert!(close(car_lateral_g(), 0.361, 0.001));
        assert!(close(car_lateral_g() / CAR_ROLLOVER_G, 0.256, 0.001));
        assert!(close(corner_lateral_g(1.0), 0.0897, 0.0001));
    }

    #[test]
    fn the_truck_holds_the_car_margin_at_the_calibration_corner() {
        // Where the lateral was calibrated, the truck takes the corner at
        // exactly sqrt(0.35/1.41) of the car's measured speed -- the equal
        // rollover margin, asserted rather than described.
        let ratio = (TRUCK_ROLLOVER_G / CAR_ROLLOVER_G).sqrt();
        assert_eq!(corner_radius_ft(90.0), CALIBRATION_RADIUS_FT);
        let got = corner_speed_mph(Some(90.0), 1.0) / car_speed_mph(Some(90.0));
        assert!(close(got, ratio, 1e-9), "got {got:.6}, want {ratio:.6}");

        // Away from it the two diverge, because the truck side is a constant
        // lateral through sqrt(R) while the car side is TTI's LINEAR
        // regression in R. That is the deliberate choice: ONE derived lateral,
        // not a curve fitted to a regression outside the 27 to 86 ft of road it
        // was measured on. Over the range real corners occupy the divergence
        // stays small, and the gate test above is what holds its direction.
        // Pinned at the table's ends rather than bounded by a band, so the
        // size of the divergence is a recorded number and not a threshold
        // somebody widened until it passed.
        for (deg, share) in [(60.0, 0.556), (120.0, 0.443)] {
            let got = corner_speed_mph(Some(deg), 1.0) / car_speed_mph(Some(deg));
            assert!(
                close(got, share, 0.001),
                "a {deg}-degree corner is {got:.3} of the car speed, was {share:.3}"
            );
        }
    }

    #[test]
    fn a_sharper_corner_is_never_faster() {
        let mut previous = f64::INFINITY;
        let mut deg = 30.0;
        while deg <= 180.0 {
            let speed = corner_speed_mph(Some(deg), 1.0);
            assert!(
                speed <= previous + 1e-9,
                "a {deg}-degree corner came out faster than the corner before it"
            );
            previous = speed;
            deg += 5.0;
        }
    }

    #[test]
    fn the_table_ends_hold_outside_the_table() {
        // Below 60 degrees the design radius stops growing: the table does not
        // go there, and the street's posted limit is what governs a gentle
        // junction.
        assert_eq!(corner_radius_ft(30.0), corner_radius_ft(60.0));
        assert_eq!(corner_radius_ft(0.0), 100.0);
        // Above 120 the truck is already at full lock.
        assert_eq!(corner_radius_ft(180.0), 45.0);
        assert_eq!(corner_radius_ft(150.0), corner_radius_ft(120.0));
    }

    #[test]
    fn the_table_rows_read_back_exactly() {
        for (deg, ft) in WB67_CORNER_RADII_FT {
            assert_eq!(corner_radius_ft(deg), ft, "TxDOT row {deg} degrees");
        }
        // And between two rows it interpolates rather than snapping.
        let between = corner_radius_ft(82.5);
        assert!(between < 75.0 && between > 65.0, "got {between}");
    }

    #[test]
    fn an_unmeasured_corner_is_priced_as_a_square_one() {
        assert_eq!(
            corner_speed_mph(None, 1.0),
            corner_speed_mph(Some(90.0), 1.0)
        );
    }

    #[test]
    fn the_shipped_ladder_stays_ordered() {
        // What a player learns by ear: a sweeping junction is faster than a
        // square corner, which is faster than a switchback into a yard. The
        // numbers are recorded here so a change to them is deliberate.
        let speeds: Vec<f64> = [60.0, 75.0, 90.0, 105.0, 120.0]
            .iter()
            .map(|d| (corner_speed_mph(Some(*d), 1.0) * 10.0).round() / 10.0)
            .collect();
        assert_eq!(speeds, vec![11.6, 10.0, 9.4, 8.2, 7.8]);
    }
}
