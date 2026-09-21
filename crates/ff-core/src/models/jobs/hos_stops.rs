//! Rest-stop estimates from the active shift and remaining route.

use crate::data::world::World;
use crate::data::world_models::Route;
use crate::models::jobs::deadline::{curve_ceilings, route_drive_hours_between};
use crate::sim::hos::{limits, HosClock, BREAK_MIN};
use crate::sim::trip_models::RoadStop;

/// Assumed allowance for leaving the road and parking, in game minutes.
pub const STOP_ACCESS_MIN: f64 = 5.0;
/// Extra planning allowance for slowing, traffic and finding the entrance.
pub const STOP_MARGIN_MIN: f64 = 5.0;

pub struct StopPlanningRoute<'a> {
    pub route: &'a Route,
    pub stops: &'a [RoadStop],
    pub position_mi: f64,
    pub bobtail: bool,
    /// Remaining departure street time before this highway route begins.
    pub local_drive_min: f64,
    pub world: Option<&'a World>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct HosStopAdvice {
    pub action: &'static str,
    pub limit_kind: &'static str,
    pub remaining_min: f64,
    pub stop: Option<RoadStop>,
    pub ahead_mi: f64,
    pub travel_min: f64,
    /// The destination, including arrival access and planning margin, fits
    /// inside the same limit that would otherwise require this stop.
    pub destination_reachable: bool,
    pub destination_travel_min: f64,
}

impl HosStopAdvice {
    pub fn summary(&self, distance: &str) -> String {
        if self.destination_reachable {
            return format!(
                "Destination estimated reachable before your next hours limit, about {:.0} \
                 minutes including access. No HOS stop is needed first. Traffic can change.",
                self.destination_travel_min.ceil()
            );
        }
        match &self.stop {
            Some(stop) => format!(
                "Last reachable {action} stop: {name}, {distance} ahead, about {minutes:.0} \
                 minutes including access. Includes 5 minutes of planning margin. Traffic and \
                 parking can change. Plan to stop here.",
                action = self.action, name = stop.spoken_name(), minutes = self.travel_min.ceil(),
            ),
            None => format!(
                "No reachable {action} stop on the remaining route within the estimated time available, {minutes:.0} minutes before your next hours limit. Find a safe place to stop; shoulder rest may bring a parking ticket.",
                action = self.action, minutes = self.remaining_min.max(0.0),
            ),
        }
    }

    /// Short automatic road call. Full estimates remain in requested readouts.
    pub fn road_warning(&self, distance: &str) -> Option<String> {
        let stop = self.stop.as_ref()?;
        Some(format!(
            "Last reachable {action} stop: {name}, {distance} ahead. Plan to stop here.",
            action = self.action,
            name = stop.spoken_name(),
        ))
    }
}

/// Last compatible stop whose estimated arrival leaves a five-minute margin.
pub fn plan_hos_stop(
    request: &StopPlanningRoute<'_>,
    clock: &HosClock,
    mode: &str,
) -> Option<HosStopAdvice> {
    let limit = clock.next_limit(mode)?;
    let (_, duty_limit, _) = limits(mode)?;
    let needs_sleep = limit.kind != "break"
        || duty_limit - clock.duty_min <= limit.remaining_min + BREAK_MIN + STOP_MARGIN_MIN;
    let action = if needs_sleep { "sleep" } else { "break" };
    let ceilings = curve_ceilings(request.route);
    let destination_travel_min = route_drive_hours_between(
        request.route,
        request.position_mi,
        request.route.miles(),
        request.world,
        &ceilings,
    ) * 60.0
        + request.local_drive_min.max(0.0)
        + STOP_ACCESS_MIN;
    let destination_reachable = destination_travel_min + STOP_MARGIN_MIN <= limit.remaining_min;
    let mut plan = HosStopAdvice {
        action,
        limit_kind: limit.kind,
        remaining_min: limit.remaining_min,
        stop: None,
        ahead_mi: 0.0,
        travel_min: 0.0,
        destination_reachable,
        destination_travel_min,
    };
    if destination_reachable {
        return Some(plan);
    }
    for stop in request.stops {
        if stop.at_mi < request.position_mi
            || stop.at_mi > request.route.miles()
            || stop.parking == "none"
            || !stop.accessible_to(request.bobtail)
            || !stop
                .actions
                .iter()
                .any(|a| a == action || (action == "break" && a == "sleep"))
        {
            continue;
        }
        let minutes = route_drive_hours_between(
            request.route,
            request.position_mi,
            stop.at_mi,
            request.world,
            &ceilings,
        ) * 60.0
            + request.local_drive_min.max(0.0)
            + STOP_ACCESS_MIN;
        if minutes + STOP_MARGIN_MIN <= limit.remaining_min
            && plan
                .stop
                .as_ref()
                .is_none_or(|previous| stop.at_mi > previous.at_mi)
        {
            plan.stop = Some(stop.clone());
            plan.ahead_mi = stop.at_mi - request.position_mi;
            plan.travel_min = minutes;
        }
    }
    Some(plan)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::world_models::{Leg, Stop};
    use crate::sim::trip::Trip;

    fn route() -> Route {
        Route::from_legs(
            vec!["A".into(), "B".into()],
            vec![Leg::new("A", "B", 100.0, "I-80", "flat", vec![])],
        )
    }

    fn rest(at_mi: f64, action: &str) -> RoadStop {
        let mut stop = RoadStop::new("Rest", at_mi, "travel_center");
        stop.actions = vec![action.into()];
        stop
    }

    #[test]
    fn access_margin_and_local_departure_can_make_stop_unreachable() {
        let route = route();
        let stops = vec![rest(11.0, "sleep")];
        let clock = HosClock {
            duty_min: 820.0,
            ..Default::default()
        };
        let mut request = StopPlanningRoute {
            route: &route,
            stops: &stops,
            position_mi: 10.0,
            bobtail: false,
            local_drive_min: 0.0,
            world: None,
        };
        assert!(plan_hos_stop(&request, &clock, "realistic")
            .unwrap()
            .stop
            .is_some());
        request.local_drive_min = 15.0;
        assert!(plan_hos_stop(&request, &clock, "realistic")
            .unwrap()
            .stop
            .is_none());
    }

    #[test]
    fn reachable_destination_does_not_recommend_an_unneeded_stop() {
        let route = route();
        let stops = vec![rest(95.0, "sleep")];
        let clock = HosClock {
            duty_min: 700.0,
            ..Default::default()
        };
        let request = StopPlanningRoute {
            route: &route,
            stops: &stops,
            position_mi: 90.0,
            bobtail: false,
            local_drive_min: 0.0,
            world: None,
        };
        let plan = plan_hos_stop(&request, &clock, "realistic").unwrap();
        assert!(plan.destination_reachable);
        assert!(plan.stop.is_none());
        assert!(plan
            .summary("5 miles")
            .contains("No HOS stop is needed first"));
    }

    #[test]
    fn late_duty_window_requires_sleep_before_break_deadline() {
        let route = route();
        let stops = vec![rest(11.0, "sleep"), rest(12.0, "break"), rest(13.0, "food")];
        let clock = HosClock {
            duty_min: 800.0,
            since_break_min: 460.0,
            ..Default::default()
        };
        let request = StopPlanningRoute {
            route: &route,
            stops: &stops,
            position_mi: 10.0,
            bobtail: false,
            local_drive_min: 0.0,
            world: None,
        };
        let plan = plan_hos_stop(&request, &clock, "realistic").unwrap();
        assert_eq!(plan.action, "sleep");
        assert_eq!(plan.stop.unwrap().at_mi, 11.0);
        assert!(plan_hos_stop(&request, &clock, "off").is_none());
        let restored = HosClock::from_dict(&clock.to_dict());
        assert_eq!(
            plan_hos_stop(&request, &clock, "realistic"),
            plan_hos_stop(&request, &restored, "realistic")
        );
    }

    #[test]
    fn route_stops_respect_reverse_direction_and_vehicle_access() {
        // Confirmed parking: a nameless travel center with only assumed
        // parking is screened to bobtail-only at load, which is not what
        // this case is about.
        let stop = Stop {
            name: "Reverse stop".into(),
            at_mi: 20.0,
            actions: vec!["sleep".into()],
            directions: vec!["reverse".into()],
            parking: "confirmed".into(),
            ..Default::default()
        };
        let route = Route::from_legs(
            vec!["B".into(), "A".into()],
            vec![Leg::new("A", "B", 100.0, "I-80", "flat", vec![stop])],
        );
        let stops = Trip::route_stops(&route, false);
        assert_eq!(stops.len(), 1);
        assert_eq!(stops[0].at_mi, 80.0);
    }
}
