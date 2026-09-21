//! Highway exits and the route-shield helpers their spoken phrases use (the
//! `Interchange` half of `world_models.py`).

use once_cell::sync::Lazy;
use regex::Regex;

/// A highway exit/junction along a leg, sourced from OpenStreetMap.
///
/// `ramp_control` is what governs the ramp terminal where the off-ramp meets
/// the surface road: `signal` (a traffic light on a ramp-link node), `stop`
/// (a stop sign), `yield` (a give-way at the terminal), `roundabout` (the
/// terminal node sits on a roundabout way), `none` (free-flow), or `""` when
/// OSM had no control tagged -- the runtime then falls back to a seeded
/// heuristic.
///
/// `ramp_far_end` is what the exit's ramp chains reach, walked from OSM link
/// topology: `motorway` (every chain merges onto another motorway; such exits
/// also carry `ramp_control: none`), `surface` (at least one chain ends off
/// the motorway network), or `""` when the walk could not judge. `surface`
/// tells the runtime NOT to guess free flow off the exit's `via` signage,
/// which points where the exit is signed toward, not at the road the ramp
/// lands on.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct Interchange {
    pub at_mi: f64,
    pub exit_ref: String,
    pub name: String,
    pub destinations: Vec<String>,
    pub via: String,
    pub highway: String,
    pub source: String,
    pub ramp_control: String,
    pub ramp_far_end: String,
    pub ramp_advisory_mph_forward: Option<f64>,
    pub ramp_advisory_mph_backward: Option<f64>,
    pub ramp_advisory_source: String,
}

impl Interchange {
    /// Lower-case lead phrase for GPS announcements.
    pub fn spoken_phrase(&self) -> String {
        let head = if self.exit_ref.is_empty() {
            "exit".to_string()
        } else {
            format!("exit {}", self.exit_ref)
        };
        let mut parts = vec![head];
        let via = format_route_ref(&self.via);
        if !via.is_empty() {
            parts.push(format!("for {via}"));
        }
        let dest = join_destinations(&destinations_without_via(&self.via, &self.destinations));
        if !dest.is_empty() {
            parts.push(format!("toward {dest}"));
        } else if !self.name.is_empty() && self.exit_ref.is_empty() {
            parts.push(format!("for {}", self.name));
        }
        parts.join(" ")
    }

    pub fn near_phrase(&self) -> String {
        let phrase = self.spoken_phrase();
        let mut chars = phrase.chars();
        let head: String = chars
            .next()
            .map(|c| c.to_uppercase().collect())
            .unwrap_or_default();
        format!("{head}{} now.", chars.as_str())
    }

    pub fn exit_label(&self) -> String {
        if self.exit_ref.is_empty() {
            String::new()
        } else {
            format!("exit {}", self.exit_ref)
        }
    }
}

/// "US 31 South;US 280" -> "US-31 South and US-280".
pub fn format_route_ref(value: &str) -> String {
    let mut out: Vec<String> = Vec::new();
    for chunk in value.split(';') {
        let reference = chunk.split_whitespace().collect::<Vec<_>>().join(" ");
        if reference.is_empty() {
            continue;
        }
        let mut parts: Vec<String> = reference.split(' ').map(str::to_string).collect();
        if parts.len() >= 2 && parts[1].chars().next().is_some_and(|c| c.is_numeric()) {
            let joined = format!("{}-{}", parts[0], parts[1]);
            parts.splice(0..2, [joined]);
        }
        out.push(parts.join(" "));
    }
    out.join(" and ")
}

static ROUTE_TOKEN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^\s*((?:I|US|[A-Za-z]{2})[-\s]?\d+)").expect("valid regex"));

/// Leading route shield of a string, normalized for comparison:
/// 'I 70 East' -> 'I70', 'US 1 North' -> 'US1', 'Trenton' -> ''.
pub fn route_token(value: &str) -> String {
    match ROUTE_TOKEN.captures(value.trim()) {
        Some(caps) => caps[1]
            .chars()
            .filter(|c| *c != '-' && !c.is_whitespace())
            .collect::<String>()
            .to_uppercase(),
        None => String::new(),
    }
}

/// Drop destinations that merely restate the via route (via 'I 70' with a
/// destination of 'I 70 East'), so the spoken phrase never says it twice. The
/// via itself still carries the route, so emptying the list reads cleanly
/// ('exit 101A for I-70').
pub fn destinations_without_via(via: &str, destinations: &[String]) -> Vec<String> {
    let token = route_token(via);
    if token.is_empty() {
        return destinations.to_vec();
    }
    destinations
        .iter()
        .filter(|d| route_token(d) != token)
        .cloned()
        .collect()
}

/// ['Trenton', 'New York'] -> 'Trenton and New York'; Oxford-comma 3+.
pub fn join_destinations(destinations: &[String]) -> String {
    let items: Vec<&String> = destinations.iter().filter(|d| !d.is_empty()).collect();
    match items.len() {
        0 => String::new(),
        1 => items[0].clone(),
        2 => format!("{} and {}", items[0], items[1]),
        n => format!(
            "{}, and {}",
            items[..n - 1]
                .iter()
                .map(|s| s.as_str())
                .collect::<Vec<_>>()
                .join(", "),
            items[n - 1]
        ),
    }
}
