//! Where the truck is parked, and the career's carrier home terminal.
//!
//! The hub's "parked at" line comes from where the truck really is:
//!
//! 1. the hiring carrier's own terminal ("{Carrier} {City} terminal") when
//!    the truck is in the career's `home_terminal_city`;
//! 2. otherwise the facility the truck last delivered or dropped at, when it
//!    is in the current city;
//! 3. otherwise the current city's `travel_center`, then `truck_parking` pin;
//! 4. otherwise just the city (no invented yard).
//!
//! It is never a yard in another city, never a world `terminal` or
//! `company_yard` pin standing in as a home, and never a bare "Terminal".

use crate::data::world::World;
use crate::data::world_models::HomeTerminal;
use crate::models::carriers::{hiring_carrier, Carrier};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParkedKind {
    /// The hiring carrier's own terminal in the home terminal city.
    CarrierTerminal,
    /// The facility the truck just delivered or dropped at.
    Facility,
    /// A public `travel_center` or `truck_parking` lot in the city.
    PublicLot,
    /// The city itself: nothing honest to name.
    City,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ParkedAt {
    pub kind: ParkedKind,
    /// The place name; for [`ParkedKind::City`] the spoken city.
    pub name: String,
    /// Resolved city key the truck is in.
    pub city_key: String,
}

impl ParkedAt {
    /// " at {name}" for a named place, "" when only the city is known, so a
    /// caller can write `format!("Parked{} in the ...", p.at_clause())`.
    pub fn at_clause(&self) -> String {
        match self.kind {
            ParkedKind::City => String::new(),
            _ => format!(" at {}", self.name),
        }
    }

    /// "at {name} in {city}" or "in {city}".
    pub fn phrase(&self, world: &World) -> String {
        let city = world.spoken_city(&self.city_key, None);
        match self.kind {
            ParkedKind::City => format!("in {city}"),
            _ => format!("at {} in {city}", self.name),
        }
    }

    /// "at {name} in the {city} service area", or "in the {city} service
    /// area" when only the city is known, so a sentence reads "Parked {}."
    /// without inventing a place.
    pub fn service_area_phrase(&self, world: &World) -> String {
        let area = city_service_area(&world.spoken_city(&self.city_key, None));
        match self.kind {
            ParkedKind::City => format!("in {area}"),
            _ => format!("at {} in {area}", self.name),
        }
    }

    /// The name a logbook line or menu title uses.
    pub fn place(&self) -> &str {
        &self.name
    }
}

/// "the {city} service area", dropping the article when the spoken city
/// already starts with one: "The Dalles service area", never "the The
/// Dalles service area".
pub fn city_service_area(city: &str) -> String {
    format!("{} service area", crate::speech_text::the_city(city))
}

/// How far a heavy wrecker is taken to tow a seized truck to a public
/// truck lot, in air miles. A `travel_center` or `truck_parking` pin
/// farther than this is not where a roadside tow ends up.
pub const TOW_LOT_RADIUS_MI: f64 = 100.0;

/// Where a tow leaves the truck: a real facility the hub can say the truck
/// is parked at.
#[derive(Debug, Clone, PartialEq)]
pub struct TowPlace {
    /// World city key the facility is in; becomes `current_city`.
    pub city_key: String,
    /// Facility name; becomes `parked_facility`.
    pub facility: String,
    /// Its `facility_type`.
    pub facility_type: String,
    /// Air miles from the tow point.
    pub miles: f64,
}

impl TowPlace {
    /// Whether this is a public truck lot rather than the fallback.
    pub fn is_public_lot(&self) -> bool {
        is_public_lot_type(&self.facility_type)
    }
}

fn is_public_lot_type(facility_type: &str) -> bool {
    matches!(facility_type, "travel_center" | "truck_parking")
}

/// Where a tow from `(lat, lon)` leaves the truck: the nearest
/// `travel_center` or `truck_parking` facility within
/// [`TOW_LOT_RADIUS_MI`], or, when no public lot is that close, the nearest
/// facility of any type. Only facilities in the country of the city nearest
/// the tow point count, so a tow never crosses a border. `None` only when
/// the world has no facility at all in that country.
pub fn tow_destination(world: &World, lat: f64, lon: f64) -> Option<TowPlace> {
    use crate::data::world::air_miles;
    let country = world
        .cities
        .values()
        .min_by(|a, b| {
            air_miles(lat, lon, a.lat, a.lon).total_cmp(&air_miles(lat, lon, b.lat, b.lon))
        })
        .map(|c| c.country.clone())?;
    let mut nearest_lot: Option<TowPlace> = None;
    let mut nearest_any: Option<TowPlace> = None;
    for (key, city) in &world.cities {
        if city.country != country {
            continue;
        }
        for loc in &city.locations {
            if loc.name.trim().is_empty() {
                continue;
            }
            let miles = air_miles(lat, lon, loc.lat, loc.lon);
            let place = || TowPlace {
                city_key: key.clone(),
                facility: loc.name.clone(),
                facility_type: loc.facility_type.clone(),
                miles,
            };
            if is_public_lot_type(&loc.facility_type)
                && miles <= TOW_LOT_RADIUS_MI
                && nearest_lot.as_ref().is_none_or(|b| miles < b.miles)
            {
                nearest_lot = Some(place());
            }
            if nearest_any.as_ref().is_none_or(|b| miles < b.miles) {
                nearest_any = Some(place());
            }
        }
    }
    nearest_lot.or(nearest_any)
}

/// The career fields [`parked_at`] reads.
#[derive(Debug, Clone, Copy)]
pub struct ParkedInputs<'a> {
    pub carrier_key: &'a str,
    pub carrier_name: &'a str,
    pub business_status: &'a str,
    pub home_terminal_city: &'a str,
    pub current_city: &'a str,
    pub parked_facility: &'a str,
}

/// Where the truck is parked (see the module docs for the order).
pub fn parked_at(world: &World, inputs: ParkedInputs<'_>) -> ParkedAt {
    let here = world.resolve_city_key(inputs.current_city);
    let carrier = hiring_carrier(
        inputs.carrier_key,
        inputs.carrier_name,
        inputs.business_status,
    );
    if let Some(terminal) = carrier_terminal_here(world, carrier, inputs.home_terminal_city, &here)
    {
        return ParkedAt {
            kind: ParkedKind::CarrierTerminal,
            name: terminal,
            city_key: here,
        };
    }
    let Some(city) = world.cities.get(&here) else {
        return ParkedAt {
            kind: ParkedKind::City,
            name: inputs.current_city.to_string(),
            city_key: here,
        };
    };
    let facility = inputs.parked_facility.trim();
    if !facility.is_empty() {
        if let Some(loc) = city
            .locations
            .iter()
            .find(|l| l.name == facility || l.id == facility)
        {
            return ParkedAt {
                kind: ParkedKind::Facility,
                name: loc.name.clone(),
                city_key: here,
            };
        }
    }
    for lot_type in ["travel_center", "truck_parking"] {
        if let Some(loc) = city.locations.iter().find(|l| l.facility_type == lot_type) {
            return ParkedAt {
                kind: ParkedKind::PublicLot,
                name: loc.name.clone(),
                city_key: here,
            };
        }
    }
    ParkedAt {
        kind: ParkedKind::City,
        name: world.spoken_city(&here, Some(true)),
        city_key: here,
    }
}

fn carrier_terminal_here(
    world: &World,
    carrier: Option<&Carrier>,
    home_terminal_city: &str,
    here: &str,
) -> Option<String> {
    let carrier = carrier?;
    if world.resolve_city_key(home_terminal_city) != here {
        return None;
    }
    carrier.terminal_name(world, here)
}

/// The career's carrier home terminal, when it has a hiring carrier. A stale
/// `home_terminal_city` (not one of this carrier's terminal cities, e.g.
/// after a carrier change) reads as that carrier's nearest terminal to it,
/// within the hiring radius for a regional.
pub fn carrier_home_terminal(
    world: &World,
    carrier_key: &str,
    carrier_name: &str,
    business_status: &str,
    home_terminal_city: &str,
) -> Option<HomeTerminal> {
    let carrier = hiring_carrier(carrier_key, carrier_name, business_status)?;
    carrier
        .home_terminal(world, home_terminal_city)
        .or_else(|| {
            let home = carrier.home_terminal_city(world, home_terminal_city)?;
            carrier.home_terminal(world, &home)
        })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::world::get_world;
    use crate::models::business::{COMPANY_DRIVER, INDEPENDENT_AUTHORITY};

    fn inputs<'a>(
        carrier_key: &'a str,
        business_status: &'a str,
        home: &'a str,
        here: &'a str,
        facility: &'a str,
    ) -> ParkedInputs<'a> {
        ParkedInputs {
            carrier_key,
            carrier_name: "",
            business_status,
            home_terminal_city: home,
            current_city: here,
            parked_facility: facility,
        }
    }

    fn has_lot(city: &crate::data::world_models::City, kind: &str) -> bool {
        city.locations.iter().any(|l| l.facility_type == kind)
    }

    #[test]
    fn test_a_tow_near_a_public_lot_ends_at_that_lot() {
        let world = get_world();
        let healy = &world.cities["healy_ak_us"];
        let lot = healy
            .locations
            .iter()
            .find(|l| l.facility_type == "travel_center")
            .expect("Healy's travel center");
        // A few miles up the Parks Highway from the lot.
        let tow = tow_destination(world, lot.lat + 0.05, lot.lon).expect("a tow place");
        assert!(tow.is_public_lot(), "{tow:?}");
        assert_eq!(tow.facility, lot.name);
        assert_eq!(tow.city_key, "healy_ak_us");
        assert!(tow.miles <= TOW_LOT_RADIUS_MI);
    }

    #[test]
    fn test_a_tow_never_crosses_the_border_to_a_closer_lot() {
        let world = get_world();
        // Just south of the Blaine crossing: the Surrey lot is in Canada.
        let tow = tow_destination(world, 48.98, -122.74).expect("a tow place");
        assert_eq!(world.cities[&tow.city_key].country, "US", "{tow:?}");
        assert_eq!(tow.city_key, "blaine_wa_us");
    }

    #[test]
    fn test_a_tow_with_no_lot_in_range_ends_at_the_nearest_real_facility() {
        let world = get_world();
        let buffalo = &world.cities["buffalo_ny_us"];
        let tow = tow_destination(world, buffalo.lat, buffalo.lon).expect("a tow place");
        assert!(!tow.is_public_lot(), "{tow:?}");
        let city = &world.cities[&tow.city_key];
        assert!(
            city.locations.iter().any(|l| l.name == tow.facility),
            "{tow:?}"
        );
        // Nothing nearer in the same country.
        for (key, c) in &world.cities {
            if c.country != "US" {
                continue;
            }
            for l in &c.locations {
                let d = crate::data::world::air_miles(buffalo.lat, buffalo.lon, l.lat, l.lon);
                assert!(d >= tow.miles - 1e-9, "{key} {} is nearer", l.name);
            }
        }
    }

    #[test]
    fn test_city_service_area_drops_the_article_for_the_dalles() {
        assert_eq!(city_service_area("The Dalles"), "The Dalles service area");
        assert_eq!(city_service_area("Chicago"), "the Chicago service area");
        // Only a leading "The " word counts, not a city that merely starts
        // with the letters.
        assert_eq!(city_service_area("Theodore"), "the Theodore service area");
        let world = get_world();
        let p = parked_at(
            world,
            inputs(
                "northstar",
                COMPANY_DRIVER,
                "chicago_il_us",
                "the_dalles_or_us",
                "",
            ),
        );
        assert_eq!(p.city_key, "the_dalles_or_us");
        let phrase = p.service_area_phrase(world);
        assert!(phrase.ends_with("in The Dalles service area"), "{phrase}");
        assert!(!phrase.contains("the The"), "{phrase}");
    }

    #[test]
    fn test_parked_at_carrier_terminal_in_home_terminal_city() {
        let world = get_world();
        // Delivered facility in the home city still reads the carrier yard:
        // home logic follows home_terminal_city.
        let p = parked_at(
            world,
            inputs(
                "northstar",
                COMPANY_DRIVER,
                "chicago_il_us",
                "Chicago",
                "Chicago Dry Warehouse",
            ),
        );
        assert_eq!(p.kind, ParkedKind::CarrierTerminal);
        assert_eq!(p.name, "Northstar Freight Lines Chicago terminal");
        assert_eq!(p.city_key, "chicago_il_us");
        assert_eq!(
            p.phrase(world),
            "at Northstar Freight Lines Chicago terminal in Chicago"
        );
    }

    #[test]
    fn test_parked_at_delivered_facility_away_from_home() {
        let world = get_world();
        let milwaukee = &world.cities["milwaukee_wi_us"];
        let facility = milwaukee
            .locations
            .iter()
            .find(|l| !matches!(l.facility_type.as_str(), "company_yard" | "terminal"))
            .expect("a Milwaukee facility");
        let p = parked_at(
            world,
            inputs(
                "northstar",
                COMPANY_DRIVER,
                "chicago_il_us",
                "milwaukee_wi_us",
                &facility.name,
            ),
        );
        assert_eq!(p.kind, ParkedKind::Facility);
        assert_eq!(p.name, facility.name);
        // A delivered yard pin is honest too: the truck really is there.
        let yard = world.yard_pin_name("milwaukee_wi_us").expect("yard pin");
        let p = parked_at(
            world,
            inputs(
                "northstar",
                COMPANY_DRIVER,
                "chicago_il_us",
                "milwaukee_wi_us",
                yard,
            ),
        );
        assert_eq!((p.kind, p.name.as_str()), (ParkedKind::Facility, yard));
    }

    #[test]
    fn test_parked_at_ignores_a_facility_in_another_city() {
        let world = get_world();
        let p = parked_at(
            world,
            inputs(
                "northstar",
                COMPANY_DRIVER,
                "chicago_il_us",
                "healy_ak_us",
                "Chicago Dry Warehouse",
            ),
        );
        assert_ne!(p.kind, ParkedKind::Facility);
        assert!(!p.name.contains("Chicago"), "{}", p.name);
    }

    #[test]
    fn test_parked_at_travel_center_then_truck_parking() {
        let world = get_world();
        let p = parked_at(
            world,
            inputs(
                "northstar",
                COMPANY_DRIVER,
                "chicago_il_us",
                "healy_ak_us",
                "",
            ),
        );
        assert_eq!(p.kind, ParkedKind::PublicLot);
        assert!(p.name.starts_with("Fisher Fuel"), "{}", p.name);
        let (key, city) = world
            .cities
            .iter()
            .find(|(_, c)| has_lot(c, "truck_parking") && !has_lot(c, "travel_center"))
            .expect("a city with only truck parking");
        let lot = city
            .locations
            .iter()
            .find(|l| l.facility_type == "truck_parking")
            .unwrap();
        let p = parked_at(
            world,
            inputs("northstar", COMPANY_DRIVER, "chicago_il_us", key, ""),
        );
        assert_eq!(
            (p.kind, p.name.as_str()),
            (ParkedKind::PublicLot, lot.name.as_str())
        );
    }

    #[test]
    fn test_parked_at_city_when_nothing_honest_to_name() {
        let world = get_world();
        let (key, city) = world
            .cities
            .iter()
            .find(|(k, c)| {
                k.as_str() != "chicago_il_us"
                    && !has_lot(c, "travel_center")
                    && !has_lot(c, "truck_parking")
            })
            .expect("a city with no public lot");
        let p = parked_at(
            world,
            inputs("northstar", COMPANY_DRIVER, "chicago_il_us", key, ""),
        );
        assert_eq!(p.kind, ParkedKind::City);
        assert_eq!(p.at_clause(), "");
        assert!(p.phrase(world).starts_with("in "), "{}", p.phrase(world));
        // Never the city's own yard pin standing in as a home.
        if let Some(yard) = world.yard_pin_name(key) {
            assert_ne!(p.name, yard);
        }
        assert_ne!(p.name, "Terminal");
        assert!(p.name.contains(&city.name));
    }

    #[test]
    fn test_parked_at_never_a_carrier_terminal_without_a_carrier_or_off_its_map() {
        let world = get_world();
        // Own authority: no carrier yard, even in Chicago.
        let p = parked_at(
            world,
            inputs(
                "northstar",
                INDEPENDENT_AUTHORITY,
                "chicago_il_us",
                "Chicago",
                "",
            ),
        );
        assert_ne!(p.kind, ParkedKind::CarrierTerminal);
        assert_ne!(Some(p.name.as_str()), world.yard_pin_name("chicago_il_us"));
        // Home city is not one of this carrier's terminal cities.
        let p = parked_at(
            world,
            inputs(
                "great_lakes_training",
                COMPANY_DRIVER,
                "chicago_il_us",
                "Chicago",
                "",
            ),
        );
        assert_ne!(p.kind, ParkedKind::CarrierTerminal);
        // Truck is away from home: the home terminal is not where it is.
        let p = parked_at(
            world,
            inputs(
                "northstar",
                COMPANY_DRIVER,
                "chicago_il_us",
                "Milwaukee",
                "",
            ),
        );
        assert_ne!(p.kind, ParkedKind::CarrierTerminal);
        assert!(!p.name.contains("Northstar"), "{}", p.name);
    }

    #[test]
    fn test_carrier_home_terminal_reads_stale_home_as_nearest_terminal() {
        let world = get_world();
        let t = carrier_home_terminal(
            world,
            "great_lakes_training",
            "",
            COMPANY_DRIVER,
            "chicago_il_us",
        )
        .expect("great lakes terminal");
        assert_eq!(t.name, "Great Lakes Training Transport Milwaukee terminal");
        assert!(carrier_home_terminal(
            world,
            "northstar",
            "",
            INDEPENDENT_AUTHORITY,
            "chicago_il_us"
        )
        .is_none());
    }
}
