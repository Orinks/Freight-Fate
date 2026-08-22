//! Baked curve geometry for the pacenote layer (port of
//! `freight_fate/data/curves.py`).
//!
//! Reads `world_data/us/gameplay/curves.jsonl` -- the per-curve steering
//! rows from the dense geometry sweep (one bake direction per leg; the
//! runtime mirrors records when a route traverses a leg b-to-a). Connector
//! rows (interchange and ramp arcs) are excluded here: ramps carry their own
//! speech and the future curve-nav layer owns them.
//!
//! Severity bands come from the advisory speed the bake computed at 0.3 g
//! lateral -- the same number a posted yellow diamond would show -- with
//! deflection promoting true switchbacks to hairpins regardless of radius.
//!
//! Interstate mainline records are screened for sweep artifacts on the way in
//! (see `INTERSTATE_MIN_RADIUS_FT`); the raw bake keeps every row.
//!
//! US and state routes get a second, narrower screen: sweep artifacts also
//! land on non-interstate mainline (the same city-departure kink that hits an
//! interstate can ride the US-route out of the same city), but road class
//! alone cannot tell those apart from a real switchback -- US-550 and the Salt
//! River Canyon really are that sharp. `curve_artifacts.jsonl`
//! (`tools/screen_curve_artifacts.py`) names the specific `(leg, seq)`
//! records an offline check flagged: flat local ground where no real hairpin
//! can exist, city-departure geometry at a leg's ends off the mountains, and a
//! radius no through highway of any class can bend to. Everything else, sharp
//! or not, is left alone -- nothing in mountain terrain is ever flagged.
//!
//! A third screen applies to mainline of every class and asks only whether a
//! record agrees with itself: a bend's recorded span has to be able to hold
//! the arc its own radius and deflection describe, and opposite-direction
//! curves cannot meet with no straight between them. Terrain cannot excuse
//! either, so unlike the two above, this one does look at mountain roads --
//! which is where it was found (`ARC_CONSISTENCY_MIN`).

use std::collections::{HashMap, HashSet};

use once_cell::sync::OnceCell;
use serde::Deserialize;

use super::data_resources::{baked, read_data_text};
use super::world::{get_world, World};
use super::world_models::{Leg, Route};

pub const HAIRPIN_MAX_MPH: i64 = 25;
pub const SHARP_MAX_MPH: i64 = 35;
pub const MODERATE_MAX_MPH: i64 = 50;
pub const HAIRPIN_DEFLECTION_DEG: f64 = 150.0;

/// Interstate mainline geometry screen. The dense sweep baked some city
/// departure geometry and interchange vertices as mainline rather than as
/// connectors, which put 80-250 ft "hairpins" on roads that cannot bend that
/// hard: an interstate is designed for 50 mph even in mountainous terrain, so
/// its tightest real mainline curve is roughly 500-600 ft of radius (the
/// notorious urban exceptions, posted 35, sit right about there). Anything
/// under 300 ft, or turning more than a switchback's worth, is a digitizing
/// artifact. Only the interstate class is screened -- US and state routes
/// really do switch back (US-550 over Red Mountain Pass, US-40 in the
/// Rockies) and their sharp records are kept exactly as baked.
pub const INTERSTATE_MIN_RADIUS_FT: i64 = 300;
pub const INTERSTATE_MAX_DEFLECTION_DEG: f64 = 150.0;

/// Geometry self-consistency screen, applied to mainline of every class.
///
/// The two screens above ask "could a road of this class bend this hard?" and
/// "does the ground under it allow a hairpin?". Both deliberately leave
/// mountain terrain alone, because that is where real switchbacks live. This
/// third screen asks something neither does and that terrain cannot excuse:
/// does the record agree with ITSELF?
///
/// A curve of radius R turning theta has an arc length of R*theta. The
/// recorded start-to-end span is measured along the same road, so a healthy
/// record spans at least its own arc -- the median mainline row comes in at
/// 1.22x. A row spanning a small fraction of that is not a bend the sweep
/// measured; it is two adjacent route points with a kink between them, and no
/// amount of real mountain justifies it.
///
/// Found on US-285 north of Santa Fe (owner playtest, 2026-08-17): a 160 ft
/// "hairpin" turning 79.9 degrees over 53 feet of road, where that geometry
/// needs 223. It sat in mountain terrain, so both existing screens correctly
/// passed it, and the pacenote layer called a 25 mph hairpin on a road posted
/// 35.
pub const ARC_CONSISTENCY_MIN: f64 = 0.1;
/// What a row with no usable radius/deflection reports: comfortably passing,
/// so an incomplete record is never dropped on arithmetic it never supplied.
const CONSISTENT_ENOUGH: f64 = 9.9;

/// The same artifact's other signature, and the one that caught the US-285
/// case: a digitized kink shows up as opposite-direction curves with NO
/// tangent between them. A real reversal at this radius has straight road in
/// between -- a through highway cannot swap lock at a point. Both sides of the
/// zig-zag go, not just the arithmetically worst one, because the wiggle is
/// spurious as a whole: the road does not really go left-right-left there.
pub const ZIGZAG_MAX_TANGENT_FT: f64 = 1.0;
pub const ZIGZAG_MAX_RADIUS_FT: i64 = 400;
/// One side must also fail arithmetic, at a looser bar than ARC_CONSISTENCY_MIN
/// -- an abrupt reversal alone is suggestive, not proof, and compound S-curves
/// are real.
pub const ZIGZAG_ARC_MAX: f64 = 0.5;

/// One baked curve in bake direction, miles from leg city a.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CurveRecord {
    pub start_mi: f64,
    pub apex_mi: f64,
    pub end_mi: f64,
    /// 'L' | 'R'
    pub direction: char,
    pub advisory_mph: i64,
    pub min_radius_ft: i64,
    pub deflection_deg: f64,
    pub connector: bool,
}

/// A curve mapped onto route miles, in the direction of travel.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RouteCurve {
    pub start_mi: f64,
    pub apex_mi: f64,
    pub end_mi: f64,
    /// 'L' | 'R'
    pub direction: char,
    pub advisory_mph: i64,
    pub min_radius_ft: i64,
    pub deflection_deg: f64,
    pub connector: bool,
}

impl RouteCurve {
    pub fn severity(&self) -> &'static str {
        curve_severity(self.advisory_mph, self.deflection_deg)
    }
}

/// The severity band for an advisory speed and deflection (shared by the
/// route curve and tests over plain records).
pub fn curve_severity(advisory_mph: i64, deflection_deg: f64) -> &'static str {
    if advisory_mph <= HAIRPIN_MAX_MPH || deflection_deg >= HAIRPIN_DEFLECTION_DEG {
        "hairpin"
    } else if advisory_mph <= SHARP_MAX_MPH {
        "sharp"
    } else if advisory_mph <= MODERATE_MAX_MPH {
        "moderate"
    } else {
        "gentle"
    }
}

/// The AASHTO point-mass control, which is what every state design manual
/// republishes: Rmin = V^2 / \[15(0.01*emax + fmax)\]  (FHWA-HRT-17-098, ch. 3;
/// Green Book table 3-7 supplies fmax). This is COMPUTED from the published
/// formula rather than a table typed in from memory, and the values it
/// produces are checked against the TxDOT Roadway Design Manual's own tables
/// 4-6 and 4-7 by `test_the_radius_floor_matches_published_design_tables` --
/// an earlier pass of this screen used 1,330 ft as the interstate floor, which
/// is in fact the SIXTY mph minimum, and let a design-speed step of bad
/// geometry through.
pub const AASHTO_SIDE_FRICTION: &[(i64, f64)] = &[
    (20, 0.27),
    (25, 0.23),
    (30, 0.20),
    (35, 0.18),
    (40, 0.16),
    (45, 0.15),
    (50, 0.14),
    (55, 0.13),
    (60, 0.12),
    (65, 0.11),
    (70, 0.10),
    (75, 0.09),
    (80, 0.08),
];
/// 8 percent is the most permissive superelevation any state builds to, so a
/// curve under this floor is under EVERY standard, not merely under a strict
/// one. Snow states cap at 6 percent and could justify a stricter screen; the
/// looser number is the one that keeps this a screen for the impossible
/// rather than a screen for the unusual.
pub const SUPERELEVATION_MAX: f64 = 0.08;

/// Tightest radius a road of this design speed may legally bend to.
pub fn min_radius_ft(design_speed_mph: f64) -> f64 {
    // Python's `min(speeds, key=...)` keeps the first of equally-near speeds.
    let (v, friction) = AASHTO_SIDE_FRICTION
        .iter()
        .copied()
        .fold(None, |best: Option<(i64, f64)>, (s, f)| match best {
            Some((bs, _))
                if ((bs as f64) - design_speed_mph).abs()
                    <= ((s as f64) - design_speed_mph).abs() =>
            {
                best
            }
            _ => Some((s, f)),
        })
        .expect("the friction table is not empty");
    let v = v as f64;
    (v * v) / (15.0 * (SUPERELEVATION_MAX + friction))
}

/// Which legs the screen may judge at all. It needs to know whether a tight
/// bend is the road or an artifact, and that is a question about terrain.
///
/// TWO PROXIES WERE TRIED AND BOTH FAILED, which is why this reads a bake:
///
///   1. The world's own `terrain` field. Derived from NET elevation change
///      end to end, so a road that climbs and drops all the way along without
///      getting anywhere reads as flat -- I-70 through Glenwood Canyon is
///      tagged "flat", and screening on it took 21 real curves off the canyon.
///   2. Feet of elevation range per mile. Calibrated against HPMS Terrain_Type
///      over a 92-leg sample and measured WEAK: Youden's J of 0.29, and at the
///      threshold it suggested it mislabelled 54 percent of rolling and
///      mountainous legs. A number tuned until it looked right, which is
///      exactly what AGENTS.md says not to ship.
///
/// So the terrain class is read rather than guessed: FHWA HPMS Terrain_Type,
/// baked per leg by tools/build_terrain_type.py. Only HPMS level ground is
/// screened. A leg HPMS calls rolling or mountainous keeps every curve it has,
/// and so does a leg HPMS has nothing to say about -- absence is not evidence
/// of flatness, and the safe direction here is a curve too many.
pub const HPMS_TERRAIN_LEVEL: i64 = 1;

/// True only where HPMS itself says the ground is level.
pub fn leg_is_level(leg: &Leg) -> bool {
    leg.hpms_terrain()
        .is_some_and(|terrain| terrain.terrain_type == HPMS_TERRAIN_LEVEL)
}

/// The speed this leg is built for, from its own baked limits.
///
/// The posted limit is the honest stand-in for design speed and it is real
/// data here -- OSM maxspeed swept per corridor -- so the floor follows the
/// road instead of a guess about its class. The fastest posting on the leg
/// is the one that matters: a curve has to be safe at the speed the road
/// lets a truck reach. Legs with no baked limit fall back to the class
/// default the runtime already uses elsewhere.
pub fn leg_design_speed(leg: &Leg) -> f64 {
    // A sample can carry a null mph (a posting the sweep found but could not
    // read); those say nothing about design speed and must not be compared.
    let fastest = leg
        .speed_limits()
        .iter()
        .filter_map(|s| s.mph)
        .fold(None, |best: Option<f64>, mph| {
            Some(best.map_or(mph, |b| b.max(mph)))
        });
    if let Some(limit) = fastest {
        return limit;
    }
    let highway = leg.highway.to_uppercase();
    if highway.starts_with("I-") {
        70.0
    } else if highway.starts_with("US") {
        55.0
    } else {
        45.0
    }
}

/// `"a:b"` -> radius floor, for legs flat enough to judge. Absent key
/// means "do not screen this leg's curves".
pub fn screenable_legs() -> HashMap<String, f64> {
    screenable_legs_of(get_world())
}

/// [`screenable_legs`] against a world handed in, so the baker can screen
/// against the world it just loaded instead of the process singleton.
pub fn screenable_legs_of(world: &World) -> HashMap<String, f64> {
    let mut out = HashMap::new();
    for leg in &world.legs {
        if !leg_is_level(leg) {
            continue;
        }
        let floor = min_radius_ft(leg_design_speed(leg));
        out.insert(format!("{}:{}", leg.a, leg.b), floor);
        out.insert(format!("{}:{}", leg.b, leg.a), floor);
    }
    out
}

/// A bend tighter than its own road may legally hold, on level ground.
///
/// The owner's report, 2026-08-19: "when I'm cruising down the highway or
/// turnpike in a car, it hardly ever curves." Measured, the map disagreed
/// with the road: interstate curve callouts ran 5.7 per hundred miles and
/// the median interstate curve radius sat at 1,342 ft against an 1,815 ft
/// floor for a 70 mph road.
///
/// The tell is the record disagreeing with ITSELF, which is why this needs
/// both halves -- a radius under the floor AND ground HPMS calls level.
/// Rough country earns a tight bend and keeps it.
fn is_flat_ground_artifact(row: &CurveRow, floor: f64) -> bool {
    (row.min_radius_ft as f64) < floor
}

/// `"a:b"` keys, both directions, for interstate-class legs.
fn interstate_leg_keys(world: &World) -> HashSet<String> {
    let mut keys = HashSet::new();
    for leg in &world.legs {
        if leg.highway.to_uppercase().starts_with("I-") {
            keys.insert(format!("{}:{}", leg.a, leg.b));
            keys.insert(format!("{}:{}", leg.b, leg.a));
        }
    }
    keys
}

/// True for a record no interstate mainline could physically hold.
fn is_interstate_artifact(row: &CurveRow) -> bool {
    row.min_radius_ft < INTERSTATE_MIN_RADIUS_FT
        || row.deflection_deg >= INTERSTATE_MAX_DEFLECTION_DEG
}

/// Recorded span as a multiple of the arc this bend's own geometry needs.
///
/// 1.0 means the span exactly holds the curve; the median mainline record is
/// 1.22. Below 1 the record is describing a turn sharper than the road it
/// claims to occupy. Returns a large number when radius or deflection is
/// missing, so an incomplete row is never screened out on arithmetic it
/// never supplied.
pub fn arc_consistency(record: &CurveRecord) -> f64 {
    let need = (record.min_radius_ft as f64) * record.deflection_deg.to_radians();
    if need <= 0.0 {
        return CONSISTENT_ENOUGH;
    }
    let span_ft = (record.end_mi - record.start_mi) * 5280.0;
    span_ft / need
}

fn by_position(a: &CurveRecord, b: &CurveRecord) -> std::cmp::Ordering {
    (a.start_mi, a.apex_mi)
        .partial_cmp(&(b.start_mi, b.apex_mi))
        .unwrap_or(std::cmp::Ordering::Equal)
}

/// Drop mainline rows that contradict their own geometry.
///
/// Two rules, both blind to road class and terrain -- see
/// `ARC_CONSISTENCY_MIN` and `ZIGZAG_MAX_TANGENT_FT`. Connectors are
/// exempt, matching the screens above: a ramp really does bend that hard,
/// and its arcs are recorded against a different baseline.
///
/// Together these drop about 2.3% of surviving mainline rows.
pub fn screen_geometry(records: &[CurveRecord]) -> Vec<CurveRecord> {
    let mut mainline: Vec<CurveRecord> = records.iter().filter(|r| !r.connector).copied().collect();
    mainline.sort_by(by_position);
    let mut doomed: HashSet<usize> = HashSet::new();
    for (i, record) in mainline.iter().enumerate() {
        if arc_consistency(record) < ARC_CONSISTENCY_MIN {
            doomed.insert(i);
        }
    }
    for (i, pair) in mainline.windows(2).enumerate() {
        let (left, right) = (&pair[0], &pair[1]);
        if left.direction == right.direction {
            continue;
        }
        if (right.start_mi - left.end_mi) * 5280.0 > ZIGZAG_MAX_TANGENT_FT {
            continue;
        }
        if left.min_radius_ft.min(right.min_radius_ft) > ZIGZAG_MAX_RADIUS_FT {
            continue;
        }
        if arc_consistency(left).min(arc_consistency(right)) >= ZIGZAG_ARC_MAX {
            continue;
        }
        doomed.insert(i);
        doomed.insert(i + 1);
    }
    let mut kept: Vec<CurveRecord> = mainline
        .iter()
        .enumerate()
        .filter(|(i, _)| !doomed.contains(i))
        .map(|(_, r)| *r)
        .collect();
    kept.extend(records.iter().filter(|r| r.connector).copied());
    kept.sort_by(by_position);
    kept
}

/// One line of `curves.jsonl` (the `meta` line is skipped before this).
#[derive(Deserialize)]
struct CurveRow {
    leg: String,
    #[serde(default)]
    seq: Option<i64>,
    start_mi: f64,
    apex_mi: f64,
    end_mi: f64,
    direction: String,
    advisory_mph: i64,
    min_radius_ft: i64,
    deflection_deg: f64,
    #[serde(default)]
    connector: bool,
}

#[derive(Deserialize)]
struct ArtifactRow {
    leg: String,
    seq: i64,
}

fn is_meta_line(line: &str) -> bool {
    serde_json::from_str::<serde_json::Value>(line)
        .ok()
        .is_some_and(|v| v.get("meta").is_some())
}

/// `(leg, seq)` pairs the US/state-route artifact screen flagged.
///
/// Baked offline by `tools/screen_curve_artifacts.py` -- see that tool's
/// docstring for the three discriminators (flat local ground under a
/// hairpin-severity curve, city-departure geometry at a leg's ends off the
/// mountains, and a radius no through highway of any class can bend to).
/// Missing file reads as "nothing flagged" rather than an error, the same
/// fail-open the interstate screen takes when curves.jsonl itself is absent.
fn flagged_artifact_keys_from(text: &str) -> HashSet<(String, i64)> {
    let mut keys = HashSet::new();
    for line in text.lines() {
        if line.trim().is_empty() || is_meta_line(line) {
            continue;
        }
        let row: ArtifactRow = serde_json::from_str(line).expect("curve_artifacts.jsonl row");
        keys.insert((row.leg, row.seq));
    }
    keys
}

static CACHE: OnceCell<HashMap<String, Vec<CurveRecord>>> = OnceCell::new();

/// The screened, per-leg curve table, built once per process (Python's
/// module `_CACHE`). Public so sweep tests can walk every leg.
pub fn load() -> &'static HashMap<String, Vec<CurveRecord>> {
    CACHE.get_or_init(|| {
        // A baked build already holds the screened table: the screens ran at
        // bake time, against this same world, through the code below.
        if let Some(container) = baked() {
            return container.curves().expect("baked curve table decodes");
        }
        let curve_text = read_data_text("world_data/us/gameplay/curves.jsonl");
        let artifact_text =
            read_data_text("world_data/us/gameplay/curve_artifacts.jsonl").unwrap_or_default();
        build_from_sources(
            curve_text.as_deref().unwrap_or(""),
            &artifact_text,
            get_world(),
        )
    })
}

/// The screened per-leg curve table built from the two JSONL texts and the
/// world they were baked against.
///
/// This is the body of [`load`], lifted out so the baker can call it with the
/// world it loaded and the files it read. One implementation of the four
/// screens, so the container and the JSON tree cannot screen differently.
pub fn build_from_sources(
    curves_jsonl: &str,
    artifacts_jsonl: &str,
    world: &World,
) -> HashMap<String, Vec<CurveRecord>> {
    {
        let mut by_leg: HashMap<String, Vec<CurveRecord>> = HashMap::new();
        {
            let text = curves_jsonl;
            let interstate_legs = interstate_leg_keys(world);
            let flagged_artifacts = flagged_artifact_keys_from(artifacts_jsonl);
            let screenable = screenable_legs_of(world);
            for line in text.lines() {
                if line.trim().is_empty() || is_meta_line(line) {
                    continue;
                }
                let row: CurveRow = serde_json::from_str(line).expect("curves.jsonl row");
                let connector = row.connector;
                // Screen sweep artifacts off interstate mainline before they
                // can reach any consumer: a bogus hairpin call, a physics
                // shove, and a time-decompression stall all read the same
                // records. Ramps are exempt -- they really are that sharp.
                if !connector && interstate_legs.contains(&row.leg) && is_interstate_artifact(&row)
                {
                    continue;
                }
                // Second screen: US/state-route mainline records an offline
                // terrain check flagged as sitting on flat ground (see
                // flagged_artifact_keys). Keyed by (leg, seq) rather than a
                // runtime rule, because the discriminator needs the dense
                // elevation archive this loader has no reason to carry.
                if !connector
                    && row
                        .seq
                        .is_some_and(|seq| flagged_artifacts.contains(&(row.leg.clone(), seq)))
                {
                    continue;
                }
                // Fourth screen: any class, any route -- a bend tighter than
                // the road's own design speed allows, on ground with no
                // relief to justify it. See is_flat_ground_artifact.
                let floor = screenable.get(&row.leg).copied();
                if !connector && floor.is_some_and(|floor| is_flat_ground_artifact(&row, floor)) {
                    continue;
                }
                // Connector arcs (interchange ramps) stay in the data with
                // their flag: curve physics wants them, spoken layers skip
                // them -- ramps carry their own speech.
                by_leg
                    .entry(row.leg.clone())
                    .or_default()
                    .push(CurveRecord {
                        start_mi: row.start_mi,
                        apex_mi: row.apex_mi,
                        end_mi: row.end_mi,
                        direction: row.direction.chars().next().unwrap_or('L'),
                        advisory_mph: row.advisory_mph,
                        min_radius_ft: row.min_radius_ft,
                        deflection_deg: row.deflection_deg,
                        connector,
                    });
            }
        }
        // Third screen, needing neighbours and so running per leg once the rows
        // are gathered rather than line by line above.
        by_leg
            .into_iter()
            .map(|(key, rows)| (key, screen_geometry(&rows)))
            .collect()
    }
}

/// Baked curves for `"a_slug:b_slug"`, bake direction. Connector arcs are
/// excluded unless asked for.
pub fn leg_curves(leg_key: &str, mainline_only: bool) -> Vec<CurveRecord> {
    let rows = load().get(leg_key).map(Vec::as_slice).unwrap_or(&[]);
    if mainline_only {
        return rows.iter().filter(|r| !r.connector).copied().collect();
    }
    rows.to_vec()
}

fn mirror(direction: char) -> char {
    match direction {
        'L' => 'R',
        'R' => 'L',
        other => other,
    }
}

/// Every curve on the route, in travel order and direction.
///
/// `cities` is the route's city sequence; each leg is mirrored when the
/// route runs it b-to-a (offsets flip across the leg, left becomes right).
/// Pass `mainline_only=false` to keep connector arcs for physics.
pub fn route_curves(route: &Route, cities: &[String], mainline_only: bool) -> Vec<RouteCurve> {
    let mut out: Vec<RouteCurve> = Vec::new();
    let mut leg_start = 0.0;
    for (from_city, leg) in cities.iter().zip(route.legs.iter()) {
        let forward = *from_city == leg.a;
        for rec in leg_curves(&format!("{}:{}", leg.a, leg.b), mainline_only) {
            let (start, apex, end, direction) = if forward {
                (rec.start_mi, rec.apex_mi, rec.end_mi, rec.direction)
            } else {
                (
                    leg.miles - rec.end_mi,
                    leg.miles - rec.apex_mi,
                    leg.miles - rec.start_mi,
                    mirror(rec.direction),
                )
            };
            out.push(RouteCurve {
                start_mi: leg_start + start,
                apex_mi: leg_start + apex,
                end_mi: leg_start + end,
                direction,
                advisory_mph: rec.advisory_mph,
                min_radius_ft: rec.min_radius_ft,
                deflection_deg: rec.deflection_deg,
                connector: rec.connector,
            });
        }
        leg_start += leg.miles;
    }
    out.sort_by(|a, b| {
        a.start_mi
            .partial_cmp(&b.start_mi)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    out
}

#[cfg(test)]
mod tests {
    //! The pure parts of `tests/test_curve_management.py` (the geometry
    //! screen and the radius floor); the world-backed sweeps live in
    //! `crates/ff-core/tests/data_curve_management.rs`.
    use super::*;

    fn rec(
        start_mi: f64,
        end_mi: f64,
        direction: char,
        radius_ft: i64,
        deflection_deg: f64,
        advisory: i64,
        connector: bool,
    ) -> CurveRecord {
        CurveRecord {
            start_mi,
            apex_mi: (start_mi + end_mi) / 2.0,
            end_mi,
            direction,
            advisory_mph: advisory,
            min_radius_ft: radius_ft,
            deflection_deg,
            connector,
        }
    }

    #[test]
    fn test_a_curve_too_short_to_hold_its_own_arc_is_dropped() {
        // Owner playtest, 2026-08-17: "is a hairpin supposed to be on this
        // route?" on US-285 north of Santa Fe.
        //
        // A 160 ft radius turning 79.9 degrees needs 223 ft of road; that record
        // claimed 53. Both existing screens correctly passed it -- it sits in real
        // mountain terrain, where real switchbacks live -- so the pacenote layer
        // called a 25 mph hairpin on a road posted 35. This screen asks a question
        // terrain cannot excuse: does the record agree with itself?

        // 500 ft radius, 30 degrees: needs 262 ft of arc.
        let honest = rec(1.00, 1.10, 'L', 500, 30.0, 25, false); // 528 ft of span, comfortable
        assert!(arc_consistency(&honest) > 1.0);
        // The same bend claiming to happen in 11 ft.
        let impossible = rec(2.00, 2.002, 'L', 500, 30.0, 25, false);
        assert!(arc_consistency(&impossible) < 0.1);

        let kept = screen_geometry(&[honest, impossible]);
        assert!(kept.contains(&honest));
        assert!(!kept.contains(&impossible));
    }

    #[test]
    fn test_a_zero_tangent_reversal_takes_both_sides_with_it() {
        // A digitized kink reads as opposite-direction curves meeting at a
        // point. A through highway cannot swap lock with no straight between, so
        // the whole wiggle goes -- including the side whose own arithmetic happens
        // to be fine, because the road does not really go left-right there.

        // Left is arithmetically fine on its own; right contradicts itself.
        let left = rec(10.00, 10.05, 'L', 160, 35.4, 25, false);
        let right = rec(10.05, 10.06, 'R', 160, 79.9, 25, false);
        let far = rec(12.00, 12.20, 'R', 900, 20.0, 45, false);

        let kept = screen_geometry(&[left, right, far]);
        assert!(
            !kept.contains(&left),
            "the fine-looking half of a zig-zag stays a zig-zag"
        );
        assert!(!kept.contains(&right));
        assert!(
            kept.contains(&far),
            "an unrelated curve down the road is untouched"
        );
    }

    #[test]
    fn test_a_real_switchback_pair_with_road_between_them_survives() {
        // US-550 over Red Mountain Pass really does reverse. The screen must
        // only take reversals with NO tangent -- otherwise it eats the mountain
        // roads the previous two screens were careful to leave alone.

        // Two tight, honest bends with a tenth of a mile of straight between.
        let first = rec(5.00, 5.10, 'L', 200, 90.0, 25, false);
        let second = rec(5.20, 5.30, 'R', 200, 90.0, 25, false);
        let kept = screen_geometry(&[first, second]);
        assert!(kept.contains(&first) && kept.contains(&second));
    }

    #[test]
    fn test_ramps_are_exempt_like_the_other_screens() {
        // Connectors really are that sharp and are recorded against a different
        // baseline; the screens above exempt them and so does this one.
        let ramp = rec(1.00, 1.001, 'L', 500, 30.0, 25, true);
        let kept = screen_geometry(&[ramp]);
        assert!(kept.contains(&ramp));
    }

    #[test]
    fn test_a_record_missing_its_geometry_is_never_screened_on_arithmetic() {
        let blank = rec(1.00, 1.001, 'L', 0, 0.0, 25, false);
        assert!(arc_consistency(&blank) > 1.0);
        assert!(screen_geometry(&[blank]).contains(&blank));
    }

    #[test]
    fn test_the_radius_floor_matches_published_design_tables() {
        // The floor is computed, so it has to be checked against print.
        //
        // `min_radius_ft` evaluates the AASHTO point-mass control
        // (Rmin = V^2 / [15(0.01*emax + fmax)], FHWA-HRT-17-098 chapter 3) using
        // the Green Book table 3-7 side-friction factors. These expected values
        // are the TxDOT Roadway Design Manual's own tables 4-6 and 4-7, which
        // republish the Green Book controls -- so if either the formula or a
        // friction factor is mistyped, this fails against a published source
        // rather than against my arithmetic.
        //
        // An earlier pass of this screen used 1,330 ft as the interstate floor.
        // That is the SIXTY mph minimum at 6 percent superelevation; a 70 mph road
        // needs 1,815 ft at 8 percent and 2,040 at 6. The screen was letting a
        // whole design-speed step of bad geometry through.
        assert_eq!(SUPERELEVATION_MAX, 0.08); // the most permissive standard built
        for (speed, expected) in [
            (40, 444.0),
            (50, 758.0),
            (60, 1200.0),
            (70, 1810.0),
            (75, 2210.0),
        ] {
            let computed = min_radius_ft(speed as f64);
            assert!(
                (computed - expected).abs() <= 5.0,
                "{speed} mph: computed {computed:.0} ft, TxDOT table 4-7 says {expected} ft"
            );
        }
        // And it really is a floor that rises with speed.
        assert!(min_radius_ft(50.0) < min_radius_ft(60.0));
        assert!(min_radius_ft(60.0) < min_radius_ft(70.0));
    }

    #[test]
    fn test_absence_of_a_terrain_class_is_never_read_as_level() {
        // The safe direction, and the reason this reads a bake rather than a rule.
        //
        // Screening treats level ground as licence to delete geometry, so a leg
        // HPMS never classified must keep every curve it has. Absence of evidence
        // is not evidence of flatness -- getting this backwards would quietly
        // strip curves from exactly the legs we know least about.
        use crate::data::world_models::{CorridorDetail, HpmsTerrain};
        let with = |terrain_type: Option<i64>| {
            Leg::new("a", "b", 10.0, "US-1", "flat", Vec::new()).with_detail(CorridorDetail {
                hpms_terrain: terrain_type.map(|t| HpmsTerrain {
                    terrain_type: t,
                    ..Default::default()
                }),
                ..Default::default()
            })
        };
        assert!(!leg_is_level(&with(None)));
        assert!(!leg_is_level(&with(Some(2))));
        assert!(!leg_is_level(&with(Some(3))));
        assert!(leg_is_level(&with(Some(1))));
    }
}
