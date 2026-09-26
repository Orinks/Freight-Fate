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

    /// The name a logbook line or menu title uses.
    pub fn place(&self) -> &str {
        &self.name
    }
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
/// after a carrier change) reads as that carrier's nearest terminal to it.
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
            let nearest = carrier.nearest_terminal_city(world, home_terminal_city)?;
            carrier.home_terminal(world, &nearest)
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
