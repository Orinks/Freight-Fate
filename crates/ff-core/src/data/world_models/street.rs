//! What a facility street chain knows about each street: the posted limit
//! and the kind of value it is, the traffic controls along it, where the
//! chain leaves the public street, and the chains that start at a ramp
//! terminal. Baked by `tools/street_chain.py`; the rules and sources are
//! there and in `facility_approaches.json`'s `generated.street_sources`.

/// A street's posted limit and the kind of value it is.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct StreetLimit {
    pub mph: f64,
    /// `read` (OSM maxspeed on most of its miles), `statutory` (a state
    /// default for an unposted road, which `basis` says), or `assumed`
    /// (neither: the old 25 named / 15 unnamed in town, the table's median
    /// rural default outside it, and every stretch past the driveway).
    pub source: String,
    /// Which statute a filled limit follows: `town` (the in-town district
    /// default, inside the Census boundary the state's code keys on) or
    /// `rural` (the default for an unposted road outside town); "" for a
    /// read limit or a stretch past the driveway.
    pub basis: String,
}

/// A READ traffic control on a street. Where OSM is silent there is none.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct StreetControl {
    /// Miles from the start of the street; 0.0 is the junction ONTO it, the
    /// corner the truck turns to reach it.
    pub at_mi: f64,
    /// `signal`, `all_way_stop`, `stop` (facing the truck) or `give_way`.
    pub kind: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct LocalGeometrySegment {
    pub road: String,
    pub miles: f64,
    pub cue: String,
    pub speed_mph: f64,
    /// Turn angle at the junction onto this segment, degrees; 0.0 unmeasured.
    pub turn_deg: f64,
    /// None on a chain baked before the street detail was.
    pub limit: Option<StreetLimit>,
    pub controls: Vec<StreetControl>,
}

impl Default for LocalGeometrySegment {
    fn default() -> Self {
        LocalGeometrySegment {
            road: String::new(),
            miles: 0.0,
            cue: String::new(),
            speed_mph: 25.0,
            turn_deg: 0.0,
            limit: None,
            controls: Vec::new(),
        }
    }
}

/// Where a chain leaves the public street for the facility's own way: the
/// first node of its final run of `highway=service` or private ways. Derived
/// from road class; OSM maps no property line.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct Driveway {
    /// Miles from the start of the chain.
    pub at_mi: f64,
    pub lat: f64,
    pub lon: f64,
    /// `service_road` or `private_road`.
    pub kind: String,
    pub source: String,
}

/// A facility's street chain from one ramp terminal, whole: the streets a
/// delivery arriving by that exit drives, from the node the ramp ends at.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct ExitChain {
    /// The OSM node the ramp ends at: `Interchange::ramp_terminal_node_*`.
    pub terminal_node: i64,
    pub total_miles: f64,
    pub segments: Vec<LocalGeometrySegment>,
    pub driveway: Option<Driveway>,
}
