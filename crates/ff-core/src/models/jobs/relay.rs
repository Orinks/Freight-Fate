//! Dispatch relaying a load from a nearby city when the board here is thin.
//!
//! A dispatcher never sends a truck empty for its own sake. A company driver
//! deadheads because the carrier has a load waiting at a shipper in another
//! town, and the empty miles are the first leg of that assignment. So when
//! the board in the driver's city comes up short -- too few loads they can
//! take, or pay well under what the next town over is offering -- dispatch
//! looks at the boards of the nearest freight towns, picks the load that
//! pays best for the hours it takes including the deadhead, and offers THAT:
//! one assignment, deadhead paid at the empty-mile rate, then the loaded run.
//!
//! Everything here is deterministic from the board's own seed, so the same
//! board relays the same load every time it is reopened.

use crate::data::world::World;
use crate::models::market::Market;
use crate::models::start_options::pay_plan_for_key;
use crate::music::crc32;
use crate::pyfmt::round_py_n;

use super::board::{Candidate, JobBoard, OfferOptions};
use super::deadline::{required_hours, route_drive_hours};
use super::{Job, ASSIGNED_REPOSITION_PAY_FRACTION, MIN_JOB_DISTANCE_MI};

/// Fewer loads than this that the driver can actually take, and the board
/// is thin. Three is the smallest board that still reads as a choice.
pub const THIN_BOARD_LOADS: usize = 3;
/// The board is also thin when its best load, per hour of driving, pays
/// less than this share of the best load a relay would bring: dispatch does
/// not leave a truck earning four-fifths of what the next town pays.
pub const RELAY_RATE_RATIO: f64 = 0.8;
/// A town is also thin when a market within a relay's range has this many
/// times its freight (shippers and receivers on the map). On this map every
/// board fills its rows and pays by the same model, so the shape of the
/// freight around a town is what tells a Tonopah from a Reno: 52 of the
/// 624 towns sit beside a market with twice their freight (probed
/// 2026-09-12), the desert and small-farm towns a carrier really does route
/// its trucks out of.
pub const THIN_MARKET_RATIO: usize = 2;
/// How many of the nearest freight towns dispatch looks at.
pub const RELAY_CANDIDATE_CITIES: usize = 3;
/// How far a relay's deadhead may run. A working day's empty miles is the
/// most a carrier will eat to reposition one truck.
pub const RELAY_RANGE_MI: f64 = 400.0;

/// What dispatch asks for when it weighs a relay.
pub struct RelayRequest<'a> {
    /// The city the truck is parked in (any spelling the world resolves).
    pub here: &'a str,
    pub endorsements: &'a [&'a str],
    pub level: i64,
    pub market: Option<&'a Market>,
    pub carrier_key: Option<&'a str>,
    pub direct_freight: bool,
    /// The board's own seed; the candidate boards draw from it.
    pub seed: i64,
}

/// A load relayed from a nearby city, its deadhead priced and timed.
#[derive(Debug, Clone, PartialEq)]
pub struct RelayLoad {
    /// The load as the board shows it: pay includes the deadhead at the
    /// empty-mile rate, the deadline includes the deadhead hours.
    pub job: Job,
    pub deadhead_mi: f64,
    pub deadhead_h: f64,
    pub deadhead_pay: f64,
    /// Dollars per hour of driving, deadhead included.
    pub rate_per_h: f64,
}

/// Whether the driver could take this load at all: real freight, and every
/// credential it needs in hand.
pub fn usable<S: AsRef<str>>(job: &Job, endorsements: &[S]) -> bool {
    !job.bobtail && job.cargo.missing_credentials(endorsements).is_empty()
}

/// Dollars per hour of driving a load pays, with `extra_pay` earned over
/// `extra_h` more hours folded in (the deadhead). Zero when the hours are.
pub fn load_rate_per_hour(job: &Job, world: &World, extra_pay: f64, extra_h: f64) -> f64 {
    let route = world
        .supported_route(&job.origin, &job.destination, None)
        .ok()
        .flatten();
    let hours = required_hours(job.distance_mi, route.as_ref(), Some(world), None) + extra_h;
    if hours <= 0.0 {
        return 0.0;
    }
    (job.pay + extra_pay) / hours
}

/// How much freight a town has: the shippers and receivers on its map.
pub fn freight_density(world: &World, city_key: &str) -> usize {
    world.city(city_key).map(|c| c.locations.len()).unwrap_or(0)
}

/// The best load a relay would bring, or None when the boards nearby hold
/// nothing the driver can take. `nearby` is every reachable city with its
/// route miles, as the board computes them.
pub fn best_relay(
    world: &World,
    request: &RelayRequest<'_>,
    nearby: &[Candidate],
) -> Option<RelayLoad> {
    let here = world.resolve_city_key(request.here);
    let density = |key: &str| freight_density(world, key);
    let mut towns: Vec<&Candidate> = nearby
        .iter()
        .filter(|(city, miles, _)| {
            *city != here
                && *miles >= MIN_JOB_DISTANCE_MI
                && *miles <= RELAY_RANGE_MI
                && density(city) > 0
        })
        .collect();
    // The thickest freight first, the nearer of equals first.
    towns.sort_by(|a, b| density(&b.0).cmp(&density(&a.0)).then(a.1.total_cmp(&b.1)));
    towns.truncate(RELAY_CANDIDATE_CITIES);
    let plan = pay_plan_for_key(request.carrier_key);
    let mut best: Option<RelayLoad> = None;
    for (city, _, _) in towns {
        let Some(deadhead) = world.supported_route(&here, city, None).ok().flatten() else {
            continue;
        };
        let deadhead_mi = round_py_n(deadhead.miles(), 1);
        let deadhead_h = route_drive_hours(Some(&deadhead), 0.0, Some(world));
        let deadhead_pay = round_py_n(
            deadhead_mi * plan.min_per_mile * ASSIGNED_REPOSITION_PAY_FRACTION,
            2,
        );
        let seed = request.seed ^ i64::from(crc32(city.as_bytes()));
        let mut board = JobBoard::new(world, Some(seed), None);
        let offers = board.offers(
            city,
            request.endorsements,
            OfferOptions {
                count: THIN_BOARD_LOADS,
                level: request.level,
                market: request.market,
                carrier_key: request.carrier_key,
                direct_freight: request.direct_freight,
            },
        );
        for job in offers {
            if !usable(&job, request.endorsements) {
                continue;
            }
            let rate_per_h = load_rate_per_hour(&job, world, deadhead_pay, deadhead_h);
            if best.as_ref().is_some_and(|b| b.rate_per_h >= rate_per_h) {
                continue;
            }
            best = Some(RelayLoad {
                job,
                deadhead_mi,
                deadhead_h,
                deadhead_pay,
                rate_per_h,
            });
        }
    }
    best
}

/// Dispatch's decision: the load to relay onto a thin local board, or None
/// when the board here is good enough. `local` is the board as generated
/// for this city.
pub fn relay_load(
    world: &World,
    request: &RelayRequest<'_>,
    local: &[Job],
    nearby: &[Candidate],
) -> Option<RelayLoad> {
    let usable_local: Vec<&Job> = local
        .iter()
        .filter(|job| usable(job, request.endorsements))
        .collect();
    let best_local_rate = usable_local
        .iter()
        .map(|job| load_rate_per_hour(job, world, 0.0, 0.0))
        .fold(0.0, f64::max);
    let mut relay = best_relay(world, request, nearby)?;
    let here = world.resolve_city_key(request.here);
    let here_density = freight_density(world, &here);
    let market_density = nearby
        .iter()
        .filter(|(city, miles, _)| {
            *city != here && *miles >= MIN_JOB_DISTANCE_MI && *miles <= RELAY_RANGE_MI
        })
        .map(|(city, _, _)| freight_density(world, city))
        .max()
        .unwrap_or(0);
    let thin = usable_local.len() < THIN_BOARD_LOADS
        || best_local_rate < RELAY_RATE_RATIO * relay.rate_per_h
        || market_density >= here_density * THIN_MARKET_RATIO;
    if !thin {
        return None;
    }
    // The deadhead is part of the assignment: paid at the empty-mile rate,
    // and given its hours in the deadline.
    relay.job.pay = round_py_n(relay.job.pay + relay.deadhead_pay, 2);
    relay.job.deadline_game_h = round_py_n(relay.job.deadline_game_h + relay.deadhead_h, 1);
    Some(relay)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::world::get_world;

    fn nearby(world: &World, here: &str) -> Vec<Candidate> {
        let here = world.resolve_city_key(here);
        let mut out = Vec::new();
        for dest in world.city_names() {
            if dest == here {
                continue;
            }
            if let Ok(Some(route)) = world.supported_route(&here, &dest, None) {
                out.push((dest, route.miles(), route.legs.len()));
            }
        }
        out
    }

    fn request<'a>(here: &'a str, endorsements: &'a [&'a str]) -> RelayRequest<'a> {
        RelayRequest {
            here,
            endorsements,
            level: 3,
            market: None,
            carrier_key: None,
            direct_freight: false,
            seed: 7,
        }
    }

    #[test]
    fn test_an_empty_board_relays_a_paid_deadhead_to_a_nearby_load() {
        let world = get_world();
        let endorsements: [&str; 0] = [];
        let request = request("Sherman", &endorsements);
        let nearby = nearby(world, "Sherman");
        let relay = relay_load(world, &request, &[], &nearby).expect("a load within range");
        let here = world.resolve_city_key("Sherman");
        assert_ne!(world.resolve_city_key(&relay.job.origin), here);
        assert!(relay.deadhead_mi >= MIN_JOB_DISTANCE_MI && relay.deadhead_mi <= RELAY_RANGE_MI);
        assert!(relay.deadhead_pay > 0.0);
        assert!(relay.deadhead_h > 0.0);
        assert!(!relay.job.bobtail);
        // The same board relays the same load.
        let again = relay_load(world, &request, &[], &nearby).expect("deterministic");
        assert_eq!(again.job.origin, relay.job.origin);
        assert_eq!(again.job.destination, relay.job.destination);
        assert_eq!(again.job.pay, relay.job.pay);
    }

    #[test]
    fn test_a_full_board_paying_well_is_left_alone() {
        let world = get_world();
        let endorsements: [&str; 0] = [];
        let request = request("Sherman", &endorsements);
        let nearby = nearby(world, "Sherman");
        let relay = best_relay(world, &request, &nearby).expect("a relay exists to compare");
        // Three local loads the driver can take, each paying far more per
        // hour than the best relay: no reason to send anyone anywhere.
        let mut rich = relay.job.clone();
        rich.origin = world.resolve_city_key("Sherman");
        rich.pay = relay.job.pay * 4.0;
        let local = vec![rich.clone(), rich.clone(), rich];
        assert!(relay_load(world, &request, &local, &nearby).is_none());
        // Two loads, however rich, is a thin board.
        let local = vec![local[0].clone(), local[1].clone()];
        assert!(relay_load(world, &request, &local, &nearby).is_some());
    }

    #[test]
    fn test_a_board_paying_far_under_the_next_town_is_thin() {
        let world = get_world();
        let endorsements: [&str; 0] = [];
        let request = request("Sherman", &endorsements);
        let nearby = nearby(world, "Sherman");
        let relay = best_relay(world, &request, &nearby).expect("a relay exists to compare");
        let mut poor = relay.job.clone();
        poor.origin = world.resolve_city_key("Sherman");
        poor.pay = relay.job.pay * 0.2;
        let local = vec![poor.clone(), poor.clone(), poor.clone(), poor];
        let chosen = relay_load(world, &request, &local, &nearby).expect("the poor board relays");
        assert!(chosen.job.pay > relay.job.pay, "the deadhead is paid");
        assert!(
            chosen.job.deadline_game_h > relay.job.deadline_game_h,
            "and timed"
        );
    }

    #[test]
    fn test_a_small_town_beside_a_big_market_relays_even_off_a_full_board() {
        // Tonopah, Nevada: five shippers on the map, with Reno's and Las
        // Vegas's markets of twice that within a day's deadhead. A full,
        // well-paid local board does not keep a carrier's truck there.
        let world = get_world();
        let endorsements: [&str; 0] = [];
        let request = request("Tonopah", &endorsements);
        let nearby = nearby(world, "Tonopah");
        let relay = best_relay(world, &request, &nearby).expect("a market in range");
        let mut rich = relay.job.clone();
        rich.origin = world.resolve_city_key("Tonopah");
        rich.pay = relay.job.pay * 4.0;
        let local = vec![rich.clone(), rich.clone(), rich.clone(), rich];
        let chosen = relay_load(world, &request, &local, &nearby).expect("Tonopah relays");
        assert!(
            freight_density(world, &chosen.job.origin)
                >= freight_density(world, &world.resolve_city_key("Tonopah")) * THIN_MARKET_RATIO
        );
        // Chicago is nobody's thin market: the same full board stays put.
        let chicago = self::request("Chicago", &endorsements);
        let around_chicago = self::nearby(world, "Chicago");
        let relay =
            best_relay(world, &chicago, &around_chicago).expect("a relay exists to compare");
        let mut rich = relay.job.clone();
        rich.origin = world.resolve_city_key("Chicago");
        rich.pay = relay.job.pay * 4.0;
        let local = vec![rich.clone(), rich.clone(), rich.clone(), rich];
        assert!(relay_load(world, &chicago, &local, &around_chicago).is_none());
    }

    #[test]
    fn test_nothing_nearby_means_no_relay() {
        let world = get_world();
        let endorsements: [&str; 0] = [];
        let request = request("Sherman", &endorsements);
        assert!(relay_load(world, &request, &[], &[]).is_none());
    }
}
