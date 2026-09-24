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
/// Time still available after reaching an optional, comfortably early stop.
pub const COMFORT_BUFFER_MIN: f64 = 30.0;
/// Avoid advising a stop far too early when the final legal stop is already
/// comfortable. A much earlier stop is still preferable to a tight fallback.
pub const COMFORT_BUFFER_MAX_MIN: f64 = 90.0;

#[derive(Debug, Clone, PartialEq)]
pub struct HosStopOption {
    pub stop: RoadStop,
    pub ahead_mi: f64,
    pub travel_min: f64,
}

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
    /// An earlier compatible stop in the useful 30-to-90-minute buffer window,
    /// or an earlier safe stop when the final fallback is tight. Otherwise the
    /// final stop itself when it has at least 30 minutes of estimated buffer.
    pub suggested: Option<HosStopOption>,
}

impl HosStopAdvice {
    /// Early optional road hint, distinguishing a comfortable plan from the
    /// legal fallback. The full estimates stay in requested readouts.
    pub fn planning_hint(
        &self,
        suggested_distance: &str,
        fallback_distance: &str,
    ) -> Option<String> {
        if self.destination_reachable {
            return None;
        }
        Some(match &self.stop {
            Some(stop) => match &self.suggested {
                Some(suggested) if suggested.stop.at_mi < stop.at_mi => format!(
                    "Plan your next {action} stop early: {suggested_name}, {suggested_distance} ahead. Estimated arrival leaves {buffer:.0} minutes before your hours limit. Last legally reachable fallback: {last_name}, {fallback_distance} ahead.",
                    action = self.action,
                    suggested_name = suggested.stop.spoken_name(),
                    last_name = stop.spoken_name(),
                    buffer = (self.remaining_min - suggested.travel_min).floor(),
                ),
                Some(_) => format!(
                    "Plan your next {action} stop: {name}, {fallback_distance} ahead. Estimated arrival leaves {buffer:.0} minutes before your hours limit. This is also the last legally reachable fallback.",
                    action = self.action,
                    name = stop.spoken_name(),
                    buffer = (self.remaining_min - self.travel_min).floor(),
                ),
                None => format!(
                    "No {action} stop with a 30-minute buffer is reachable. {name}, {fallback_distance} ahead, is the last legally reachable fallback. Plan to stop there.",
                    action = self.action,
                    name = stop.spoken_name(),
                ),
            },
            None => format!(
                "No reachable {action} stop remains on this route before your hours limit. Find a safe place to stop and check your route and hours.",
                action = self.action,
            ),
        })
    }

    pub fn summary(&self, suggested_distance: &str, fallback_distance: &str) -> String {
        if self.destination_reachable {
            return format!(
                "Destination estimated reachable before your next hours limit, about {:.0} \
                 minutes including access. No HOS stop is needed first. Traffic can change.",
                self.destination_travel_min.ceil()
            );
        }
        match &self.stop {
            Some(stop) if self.suggested.as_ref().is_some_and(|s| s.stop.at_mi < stop.at_mi) => {
                let suggested = self.suggested.as_ref().expect("checked above");
                format!(
                    "Suggested {action} stop: {suggested_name}, {suggested_distance} ahead, about {suggested_minutes:.0} minutes including access; estimated {buffer:.0} minutes before your next hours limit. Last legally reachable fallback: {last_name}, {fallback_distance} ahead, about {last_minutes:.0} minutes including access. Includes 5 minutes of legal planning margin. Traffic and parking can change.",
                    action = self.action,
                    suggested_name = suggested.stop.spoken_name(),
                    suggested_minutes = suggested.travel_min.ceil(),
                    buffer = (self.remaining_min - suggested.travel_min).floor(),
                    last_name = stop.spoken_name(),
                    last_minutes = self.travel_min.ceil(),
                )
            }
            Some(stop) => format!(
                "Last reachable {action} stop: {name}, {fallback_distance} ahead, about {minutes:.0} minutes including access. Estimated {buffer:.0} minutes remain before your next hours limit; the legal planning margin is 5 minutes. {earlier} Traffic and parking can change. Plan to stop here.",
                action = self.action,
                name = stop.spoken_name(),
                minutes = self.travel_min.ceil(),
                buffer = (self.remaining_min - self.travel_min).floor(),
                earlier = if self.suggested.is_some() {
                    "This stop also has a comfortable estimated buffer."
                } else {
                    "No earlier compatible stop offers a 30-minute estimated buffer."
                },
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
        suggested: None,
    };
    if destination_reachable {
        return Some(plan);
    }
    let mut comfortable = Vec::new();
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
        if minutes + STOP_MARGIN_MIN <= limit.remaining_min {
            if minutes + COMFORT_BUFFER_MIN <= limit.remaining_min {
                comfortable.push(HosStopOption {
                    stop: stop.clone(),
                    ahead_mi: stop.at_mi - request.position_mi,
                    travel_min: minutes,
                });
            }
            if plan
                .stop
                .as_ref()
                .is_none_or(|previous| stop.at_mi > previous.at_mi)
            {
                plan.stop = Some(stop.clone());
                plan.ahead_mi = stop.at_mi - request.position_mi;
                plan.travel_min = minutes;
            }
        }
    }
    if let Some(last) = &plan.stop {
        let earlier = comfortable
            .into_iter()
            .filter(|option| option.stop.at_mi < last.at_mi)
            .max_by(|a, b| a.stop.at_mi.total_cmp(&b.stop.at_mi));
        let last_buffer = plan.remaining_min - plan.travel_min;
        plan.suggested = if earlier
            .as_ref()
            .is_some_and(|option| plan.remaining_min - option.travel_min <= COMFORT_BUFFER_MAX_MIN)
            || last_buffer < COMFORT_BUFFER_MIN
        {
            earlier
        } else if last_buffer >= COMFORT_BUFFER_MIN {
            Some(HosStopOption {
                stop: last.clone(),
                ahead_mi: plan.ahead_mi,
                travel_min: plan.travel_min,
            })
        } else {
            None
        };
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

    fn long_route() -> Route {
        Route::from_legs(
            vec!["A".into(), "B".into()],
            vec![Leg::new("A", "B", 300.0, "I-80", "flat", vec![])],
        )
    }

    fn just_reaches(route: &Route, mile: f64) -> f64 {
        route_drive_hours_between(route, 0.0, mile, None, &curve_ceilings(route)) * 60.0
            + STOP_ACCESS_MIN
            + STOP_MARGIN_MIN
            + 0.1
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
            .summary("5 miles", "5 miles")
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

    #[test]
    fn sleep_hint_picks_a_comfortable_earlier_stop_and_keeps_the_legal_fallback() {
        let route = route();
        let stops = vec![rest(5.0, "sleep"), rest(10.0, "sleep"), rest(40.0, "sleep")];
        let remaining = just_reaches(&route, 40.0);
        let clock = HosClock {
            duty_min: 840.0 - remaining,
            ..Default::default()
        };
        let request = StopPlanningRoute {
            route: &route,
            stops: &stops,
            position_mi: 0.0,
            bobtail: false,
            local_drive_min: 0.0,
            world: None,
        };
        let advice = plan_hos_stop(&request, &clock, "realistic").unwrap();
        assert_eq!(advice.action, "sleep");
        assert_eq!(advice.stop.as_ref().unwrap().at_mi, 40.0);
        let suggested = advice.suggested.as_ref().unwrap();
        assert_eq!(suggested.stop.at_mi, 10.0);
        assert!(remaining - suggested.travel_min >= COMFORT_BUFFER_MIN);
        assert!(remaining - suggested.travel_min <= COMFORT_BUFFER_MAX_MIN);
        let hint = advice.planning_hint("10 miles", "40 miles").unwrap();
        assert!(hint.contains("stop early"), "{hint}");
        assert!(hint.contains("10 miles"), "{hint}");
        assert!(hint.contains("Last legally reachable fallback"), "{hint}");
        assert!(hint.contains("40 miles"), "{hint}");
        let summary = advice.summary("10 miles", "40 miles");
        assert!(summary.contains("Suggested sleep stop"), "{summary}");
        assert!(
            summary.contains("Last legally reachable fallback"),
            "{summary}"
        );
    }

    #[test]
    fn distant_early_stop_is_not_suggested_when_last_stop_has_buffer() {
        let route = long_route();
        let stops = vec![rest(5.0, "sleep"), rest(80.0, "sleep")];
        let remaining = just_reaches(&route, 80.0) + 35.0;
        let clock = HosClock {
            duty_min: 840.0 - remaining,
            ..Default::default()
        };
        let request = StopPlanningRoute {
            route: &route,
            stops: &stops,
            position_mi: 0.0,
            bobtail: false,
            local_drive_min: 0.0,
            world: None,
        };
        let advice = plan_hos_stop(&request, &clock, "realistic").unwrap();
        assert_eq!(advice.stop.as_ref().unwrap().at_mi, 80.0);
        assert_eq!(advice.suggested.as_ref().unwrap().stop.at_mi, 80.0);
        let hint = advice.planning_hint("80 miles", "80 miles").unwrap();
        assert!(
            hint.contains("also the last legally reachable fallback"),
            "{hint}"
        );
    }

    #[test]
    fn distant_early_stop_is_still_suggested_when_last_fallback_is_tight() {
        let route = long_route();
        let stops = vec![rest(5.0, "sleep"), rest(150.0, "sleep")];
        let remaining = just_reaches(&route, 150.0);
        let clock = HosClock {
            duty_min: 840.0 - remaining,
            ..Default::default()
        };
        let request = StopPlanningRoute {
            route: &route,
            stops: &stops,
            position_mi: 0.0,
            bobtail: false,
            local_drive_min: 0.0,
            world: None,
        };
        let advice = plan_hos_stop(&request, &clock, "realistic").unwrap();
        assert_eq!(advice.suggested.as_ref().unwrap().stop.at_mi, 5.0);
        assert_eq!(advice.stop.as_ref().unwrap().at_mi, 150.0);
        assert!(remaining - advice.suggested.as_ref().unwrap().travel_min > COMFORT_BUFFER_MAX_MIN);
    }

    #[test]
    fn break_hint_uses_compatible_accessible_stops_and_retains_sleep_stop_as_fallback() {
        let route = route();
        let mut blocked = rest(30.0, "break");
        blocked.vehicle_access = "bobtail_only".into();
        let mut no_parking = rest(35.0, "break");
        no_parking.parking = "none".into();
        let stops = vec![
            rest(10.0, "break"),
            rest(20.0, "fuel"),
            blocked,
            no_parking,
            rest(40.0, "sleep"),
        ];
        let remaining = just_reaches(&route, 40.0);
        let clock = HosClock {
            since_break_min: 480.0 - remaining,
            ..Default::default()
        };
        let request = StopPlanningRoute {
            route: &route,
            stops: &stops,
            position_mi: 0.0,
            bobtail: false,
            local_drive_min: 0.0,
            world: None,
        };
        let advice = plan_hos_stop(&request, &clock, "realistic").unwrap();
        assert_eq!(advice.action, "break");
        assert_eq!(advice.suggested.as_ref().unwrap().stop.at_mi, 10.0);
        assert_eq!(advice.stop.as_ref().unwrap().at_mi, 40.0);
        let hint = advice.planning_hint("10 miles", "40 miles").unwrap();
        assert!(hint.contains("next break stop early"), "{hint}");
        assert!(hint.contains("Last legally reachable fallback"), "{hint}");
    }

    #[test]
    fn tight_only_stop_is_named_as_fallback_without_a_comfort_claim() {
        let route = route();
        let stops = vec![rest(40.0, "sleep")];
        let remaining = just_reaches(&route, 40.0);
        let clock = HosClock {
            duty_min: 840.0 - remaining,
            ..Default::default()
        };
        let request = StopPlanningRoute {
            route: &route,
            stops: &stops,
            position_mi: 0.0,
            bobtail: false,
            local_drive_min: 0.0,
            world: None,
        };
        let advice = plan_hos_stop(&request, &clock, "realistic").unwrap();
        assert!(advice.suggested.is_none());
        let hint = advice.planning_hint("40 miles", "40 miles").unwrap();
        assert!(
            hint.contains("No sleep stop with a 30-minute buffer"),
            "{hint}"
        );
        assert!(hint.contains("last legally reachable fallback"), "{hint}");
    }
}
