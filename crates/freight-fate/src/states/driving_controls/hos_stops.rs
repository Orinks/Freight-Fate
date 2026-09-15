//! Route advice and advance warnings for the next required rest.

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::{hos_mut_of, hos_of};
use ff_core::models::jobs::hos_stops::{plan_hos_stop, HosStopAdvice, StopPlanningRoute};
use ff_core::models::jobs::route_drive_hours;
use ff_core::speech_pacing::{DeliveryStatus, EventPriority, SpeechCategory};

impl DrivingState {
    pub(crate) fn settle_last_hos_stop_warning(
        &mut self,
        ctx: &mut GameContext,
        interrupt_pending: bool,
    ) {
        let Some(key) = self.hos_stop_warning_pending.clone() else {
            return;
        };
        match ctx.event_delivery_status(&key) {
            Some(DeliveryStatus::Pending) if !interrupt_pending => return,
            Some(DeliveryStatus::Completed) => {
                if !hos_of(ctx).warned.contains(&key) {
                    hos_mut_of(ctx).warned.push(key);
                }
            }
            Some(DeliveryStatus::Pending | DeliveryStatus::Interrupted) | None => {
                ctx.reset_event_condition(&key);
                self.hos_stop_check_key = None;
            }
        }
        self.hos_stop_warning_pending = None;
    }

    /// The player cut the warning off: that counts as having heard it.
    ///
    /// An interrupted warning is otherwise said again in full, which is
    /// right when another line cut it and wrong when the player did --
    /// every press of Control brought the whole line back, as many times
    /// as it was pressed (Shane's log, 12 September).
    pub(crate) fn acknowledge_last_hos_stop_warning(&mut self, ctx: &mut GameContext) {
        let Some(key) = self.hos_stop_warning_pending.take() else {
            return;
        };
        if !hos_of(ctx).warned.contains(&key) {
            hos_mut_of(ctx).warned.push(key);
        }
    }

    /// Everything a player's stop-speech key settles at once.
    pub(crate) fn warnings_stopped_by_player(&mut self, ctx: &mut GameContext) {
        self.note_critical_speech_stopped();
        self.acknowledge_last_hos_stop_warning(ctx);
        self.acknowledge_maintenance_warnings();
    }

    pub fn hos_stop_advice(&self, ctx: &GameContext) -> Option<HosStopAdvice> {
        let (trip, local_drive_min) = if self.departure_chain {
            let highway = self.highway_trip.as_ref()?;
            (
                highway,
                route_drive_hours(
                    Some(&self.trip.route),
                    self.trip.position_mi,
                    Some(ctx.world),
                ) * 60.0,
            )
        } else {
            (&self.trip, 0.0)
        };
        plan_hos_stop(
            &StopPlanningRoute {
                route: &trip.route,
                stops: &trip.stops,
                position_mi: trip.position_mi,
                bobtail: trip.bobtail,
                local_drive_min,
                world: Some(ctx.world),
            },
            hos_of(ctx),
            &ctx.settings.hos_mode,
        )
    }

    pub fn warn_last_hos_stop(&mut self, ctx: &mut GameContext) {
        self.settle_last_hos_stop_warning(ctx, false);
        if self.hos_stop_warning_pending.is_some() {
            return;
        }
        if ctx.event_delivery_pending() {
            return;
        }
        if self.departure_chain || self.surface_chain {
            return;
        }
        let Some(limit) = hos_of(ctx).next_limit(&ctx.settings.hos_mode) else {
            return;
        };
        // Route timing walks curves and speed zones. Only do it when an
        // HOS-capable stop enters the same real-time warning window used for
        // exits, then at most once per quarter game minute. A delay can still
        // change the answer while the stop remains ahead.
        let window_mi = self.exit_window_mi();
        let Some(candidate_key) = self.trip.stops.iter().find_map(|stop| {
            let ahead = stop.at_mi - self.trip.position_mi;
            let can_rest = stop
                .actions
                .iter()
                .any(|action| action == "break" || action == "sleep");
            ((0.0..=window_mi).contains(&ahead)
                && stop.parking != "none"
                && stop.accessible_to(self.trip.bobtail)
                && can_rest)
                .then(|| stop.key())
        }) else {
            return;
        };
        let candidate_warning_suffix = format!(":hos-stop:{candidate_key}");
        let candidate_warned = hos_of(ctx)
            .warned
            .iter()
            .any(|key| key.ends_with(&candidate_warning_suffix));
        let check_key = format!(
            "{}:{candidate_key}:{}:{candidate_warned}",
            limit.kind,
            (limit.remaining_min * 4.0).floor() as i64
        );
        if self.hos_stop_check_key.as_deref() == Some(&check_key) {
            return;
        }
        self.hos_stop_check_key = Some(check_key);
        let Some(advice) = self.hos_stop_advice(ctx) else {
            return;
        };
        if advice.destination_reachable {
            return;
        }
        let Some(stop) = &advice.stop else {
            return;
        };
        if advice.ahead_mi > window_mi {
            return;
        }
        let key = format!("{}:hos-stop:{}", advice.limit_kind, stop.key());
        if hos_of(ctx).warned.contains(&key) {
            return;
        }
        let distance = ctx.settings.distance_text(advice.ahead_mi, false);
        let Some(message) = advice.road_warning(&distance) else {
            return;
        };
        ctx.reset_event_condition(&key);
        self.hos_stop_warning_pending = Some(key.clone());
        ctx.say_event_with(
            message,
            SayEvent::queued()
                .priority(EventPriority::Route)
                .key(&key)
                .category(SpeechCategory::Safety)
                .receipt(),
        );
    }
}
