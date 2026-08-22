//! What the road posts and what the zones say: zone warnings and entries,
//! the time-zone line, posted-limit arrivals and the advance "drops to X"
//! pacenote (the limit section of `trip.py`).

use crate::pyfmt::round_py_n;
use crate::sim::hos::clock_text;
use crate::sim::trip_models::*;
use crate::sim::trip_route_helpers::zone_key;
use crate::speech_text::SpokenMessage;

use super::{
    limit_reason_by_stop_type, spoken_short_miles, Trip, LIMIT_DOWNGRADE_MIN_MI,
    LIMIT_DOWNGRADE_PCT, LIMIT_DROP_WARN_MIN_DELTA_MPH, LIMIT_REASON_LOOKAHEAD_MI,
    LIMIT_SCAN_MAX_MI, LIMIT_SCAN_STRIDE_MI, LIMIT_SHORT_ZONE_MI, LIMIT_WARNING_MAX_LEAD_MI,
    LIMIT_WARNING_REAL_S, PACENOTE_MARGIN_MPH, PACENOTE_MIN_LEAD_MI, ZONE_WARNING_MIN_MI,
};

impl Trip {
    /// Lead distance for a zone warning, scaled so the player gets roughly
    /// `ZONE_WARNING_REAL_S` of real time despite speed and compression.
    pub fn zone_warning_lookahead_mi(&self) -> f64 {
        let speed = self.truck.speed_mph().max(1.0);
        let miles = ZONE_WARNING_REAL_S * speed * self.effective_time_scale() / 3600.0;
        ZONE_WARNING_LOOKAHEAD_MI.max(miles.min(ZONE_WARNING_MAX_MI))
    }

    /// (closed lane name, direction to merge) for a zone's coned-off lane.
    pub fn closure_phrases(zone: &Zone) -> (&'static str, &'static str) {
        let shut = match zone.closed_side.as_deref() {
            Some("right") => "right",
            Some(_) => "left",
            None => {
                if zone.closed_lane == Some(0) {
                    "right"
                } else {
                    "left"
                }
            }
        };
        (shut, if shut == "right" { "left" } else { "right" })
    }

    pub fn zone_warning_message(&self, zone: &Zone, ahead: f64) -> String {
        if zone.reason == "construction" {
            let merge_part = if zone.closed_side.is_some() {
                let (shut, keep) = Self::closure_phrases(zone);
                format!("The {shut} lane is closed; merge {keep} at the taper. ")
            } else {
                "All lanes stay open through the work; hold your lane. ".to_string()
            };
            return format!(
                "Brake now! In {}, construction ahead. {merge_part}Speed limit {} at the taper, then {} through the work zone.",
                self.ahead_text(ahead),
                self.speed_value(CONSTRUCTION_TAPER_LIMIT_MPH),
                self.speed_value(zone.limit_mph)
            );
        }
        if zone.reason == "heavy traffic" && zone.aadt.is_some() {
            return format!(
                "In {}, {} ahead. Traffic slowing to {}.",
                self.ahead_text(ahead),
                self.congestion_phrase(),
                self.speed_value(zone.limit_mph)
            );
        }
        format!(
            "In {}, {} ahead. Speed limit {}.",
            self.ahead_text(ahead),
            zone.reason,
            self.speed_value(zone.limit_mph)
        )
    }

    /// What to call a live jam: rush hour gets named when it is one.
    pub fn congestion_phrase(&self) -> &'static str {
        let hour = self.current_hour().rem_euclid(24.0);
        let in_rush = RUSH_HOUR_WINDOWS
            .iter()
            .any(|(start, end)| *start <= hour && hour < *end);
        if in_rush && !self.is_weekend_now() {
            "rush hour congestion"
        } else {
            "heavy traffic"
        }
    }

    pub fn zone_entry_message(&self, zone: &Zone) -> String {
        if zone.reason == "construction merge" {
            if zone.closed_side.is_some() {
                let (shut, keep) = Self::closure_phrases(zone);
                return format!(
                    "Construction merge taper. The {shut} lane closes ahead; merge {keep} now. Speed limit {}.",
                    self.speed_value(zone.limit_mph)
                );
            }
            return format!(
                "Construction merge taper. Follow the flagger through the cones. Speed limit {}.",
                self.speed_value(zone.limit_mph)
            );
        }
        if zone.reason == "construction" {
            if zone.closed_side.is_some() {
                let (shut, keep) = Self::closure_phrases(zone);
                // "Keep left" is the same instruction on a two-lane stretch
                // and still true on a wider one.
                return format!(
                    "Work zone active. The {shut} lane is closed; keep {keep} and watch the barrels. Speed limit {}.",
                    self.speed_value(zone.limit_mph)
                );
            }
            return format!(
                "Work zone active. Stay in the lane and watch the barrels. Speed limit {}.",
                self.speed_value(zone.limit_mph)
            );
        }
        if zone.reason == "heavy traffic" && zone.aadt.is_some() {
            return format!(
                "{}. Traffic slowing to {}; hold your gap.",
                crate::data::world_models::py_capitalize(self.congestion_phrase()),
                self.speed_value(zone.limit_mph)
            );
        }
        // Say you are *in* it, not that it is ahead; pairs with the "End of
        // ... zone" exit.
        format!(
            "Entering {} zone. Speed limit {} now.",
            zone.reason,
            self.speed_value(zone.limit_mph)
        )
    }

    pub fn check_zones(&mut self) {
        let lookahead = self.zone_warning_lookahead_mi();
        let pos = self.position_mi;
        // The NEXT zone only, not every zone inside the lookahead (owner
        // playtest, 2026-08-17).
        let mut due: Vec<(f64, usize)> = Vec::new();
        for i in 0..self.zones.len() {
            if self.zones[i].reason == "construction merge" {
                continue;
            }
            if self
                .announced_zone_warnings
                .contains(&zone_key(&self.zones[i]))
            {
                continue;
            }
            let ahead = self.zones[i].start_mi - pos;
            if !(ZONE_WARNING_MIN_MI < ahead && ahead <= lookahead) {
                continue;
            }
            if !self.zone_is_active_index(i) {
                continue;
            }
            due.push((ahead, i));
        }
        // One warning OUTSTANDING at a time, not one per frame.
        if let Some(pending) = self.pending_zone_warning {
            if pos < pending {
                return;
            }
        }
        // Never a heads-up in the same breath as an arrival. Held, not lost.
        let now = self.active_zone_at(pos);
        let entering = !Self::same_zone(now.as_ref(), self.entered_zone.as_ref());
        if !due.is_empty() && !entering {
            let mut best = due[0];
            for pair in &due[1..] {
                if pair.0 < best.0 {
                    best = *pair;
                }
            }
            let (ahead, i) = best;
            let zone = self.zones[i].clone();
            self.announced_zone_warnings.insert(zone_key(&zone));
            self.pending_zone_warning = Some(zone.start_mi);
            let message = self.zone_warning_message(&zone, ahead);
            self.emit(
                TripEventKind::GpsCue,
                SpokenMessage::new(message),
                TripEventData {
                    zone: Some(zone),
                    ..Default::default()
                },
            );
        }
        let zone = self.active_zone_at(pos);
        if !Self::same_zone(zone.as_ref(), self.entered_zone.as_ref()) {
            if let Some(zone) = zone.clone() {
                if zone.reason == "construction" {
                    self.construction_zone_grace_start
                        .insert(zone_key(&zone), zone.start_mi);
                }
                // Holding the colour line back is only safe when the number
                // is not changing for the worse: an entry that CUTS the limit
                // currently in force never waits.
                let old_limit = match self.entered_zone.as_ref() {
                    Some(entered) => {
                        let key = zone_key(entered);
                        Some(
                            self.zones
                                .iter()
                                .find(|z| zone_key(z) == key)
                                .map(|z| z.limit_mph)
                                .unwrap_or(entered.limit_mph),
                        )
                    }
                    None => self.announced_speed_limit,
                };
                let urgent = old_limit.is_some_and(|old| zone.limit_mph < old);
                if urgent || self.event_breather.ready("zone") {
                    self.speak_zone_entry(&zone);
                } else {
                    // Gated, not dropped.
                    self.zone_entry_spoken = false;
                }
                if zone.reason == "heavy traffic" && zone.aadt.is_some() {
                    // Fill the jam with slow metal.
                    self.traffic_manager
                        .inject_congestion(zone.start_mi, zone.limit_mph, pos);
                }
            } else if let Some(previous) = self.entered_zone.clone() {
                self.construction_zone_grace_start
                    .remove(&zone_key(&previous));
                let resumed = self.corridor_limit_at(pos);
                self.announced_speed_limit = Some(resumed);
                let message = format!(
                    "End of {} zone. Speed limit {}.",
                    previous.reason,
                    self.speed_value(resumed)
                );
                self.emit(
                    TripEventKind::ZoneExit,
                    SpokenMessage::new(message),
                    TripEventData::default(),
                );
                self.zone_entry_spoken = true;
            }
            self.entered_zone = zone;
        } else if let Some(zone) = zone {
            if !self.zone_entry_spoken && self.event_breather.ready("zone") {
                // Self-supersede: this zone is still the one governing the
                // truck and its own entry was gated when it started.
                self.speak_zone_entry(&zone);
            }
        }
    }

    pub fn speak_zone_entry(&mut self, zone: &Zone) {
        let quiet = zone.reason == "construction"
            && self.zones.iter().any(|z| {
                z.reason == "construction merge" && (z.end_mi - zone.start_mi).abs() < 0.01
            });
        self.event_breather.spoke("zone");
        let message = self.zone_entry_message(zone);
        self.emit(
            TripEventKind::ZoneEnter,
            SpokenMessage::new(message),
            TripEventData {
                zone: Some(zone.clone()),
                suppress_sound: Some(quiet),
                ..Default::default()
            },
        );
        self.zone_entry_spoken = true;
    }

    /// Announce a clock change the moment the truck passes a zone boundary.
    pub fn check_timezone(&mut self) {
        let zone = self.timezone_at(self.position_mi);
        if zone.key == self.last_timezone.key {
            return;
        }
        let previous = self.last_timezone;
        self.last_timezone = zone;
        // The new local time is the whole message.
        let message = format!(
            "Crossing into {}. It is now {}.",
            zone.name,
            clock_text(self.local_hour())
        );
        self.emit(
            TripEventKind::TimezoneCrossing,
            SpokenMessage::new(message),
            TripEventData {
                from_zone: Some(previous),
                to_zone: Some(zone),
                ..Default::default()
            },
        );
    }

    /// Announce a changed posted limit on the open road. While a zone is
    /// active the zone owns the spoken limit, so this stays quiet.
    pub fn check_speed_limit(&mut self) {
        if self.entered_zone.is_some() {
            return;
        }
        let limit = self.corridor_limit_at(self.position_mi);
        let Some(announced) = self.announced_speed_limit else {
            self.announced_speed_limit = Some(limit); // seed at departure, no cue
            return;
        };
        if limit == announced {
            return;
        }
        let lowered = limit < announced;
        // Routine changes breathe; a serious unannounced drop does not wait.
        let urgent = lowered
            && announced - limit > 10.0
            && !self.limit_drop_preannounced.contains(&round_py_n(limit, 1));
        if !urgent && !self.event_breather.ready("limit") {
            return; // untouched state; the next check self-supersedes
        }
        self.announced_speed_limit = Some(limit);
        if lowered {
            // The advance pacenote or an assist's "easing to X" line may
            // already have named this exact number (owner, 2026-08-12).
            let key = round_py_n(limit, 1);
            if let Some(pos) = self.limit_drop_preannounced.iter().position(|v| *v == key) {
                self.limit_drop_preannounced.remove(pos);
                return;
            }
        }
        let verb = if lowered { "reduced to" } else { "raised to" };
        let near = if lowered {
            self.nearest_urban_city(self.position_mi)
        } else {
            None
        };
        let mut where_ = String::new();
        if let Some((city, city_mp)) = near {
            // A drop while pulling AWAY from town is the road's doing, not
            // the town's (owner-found live, 2026-07-20).
            let direction = if city_mp >= self.position_mi {
                "approaching"
            } else {
                "leaving"
            };
            where_ = format!(" {direction} {}", self.world.spoken_city(&city, None));
        } else if lowered {
            where_ = self.lowered_limit_reason();
        }
        // A short lower zone is a passing event, not a new cruising speed.
        let mut span = String::new();
        if lowered {
            if let Some(length) = self.limit_zone_length(limit) {
                if length <= LIMIT_SHORT_ZONE_MI {
                    span = format!(" for {}", spoken_short_miles(length, self.imperial()));
                }
            }
        }
        self.event_breather.spoke("limit");
        let message = format!(
            "Speed limit {verb} {}{where_}{span}.",
            self.speed_value(limit)
        );
        self.emit(
            TripEventKind::GpsCue,
            SpokenMessage::new(message),
            TripEventData {
                // The road's state, not a turn to act on.
                limit_change: Some(true),
                ..Default::default()
            },
        );
    }

    /// Why a drop with no city to blame is happening: a road stop just
    /// ahead, then a real downgrade just ahead. Bare when neither applies.
    pub fn lowered_limit_reason(&self) -> String {
        let stop_reason = self.lowered_limit_stop_reason();
        if !stop_reason.is_empty() {
            return stop_reason;
        }
        if self.lowered_limit_downgrade_ahead() {
            return " for the downgrade".to_string();
        }
        String::new()
    }

    /// A road stop that plausibly explains a lower posting, ahead only.
    pub fn lowered_limit_stop_reason(&self) -> String {
        let end = self.position_mi + LIMIT_REASON_LOOKAHEAD_MI;
        for stop in &self.stops {
            if self.position_mi <= stop.at_mi && stop.at_mi <= end {
                if let Some(reason) = limit_reason_by_stop_type(&stop.stop_type) {
                    return reason.to_string();
                }
            }
        }
        String::new()
    }

    /// Whether a sustained downgrade starts here -- steep enough on average
    /// over the next half mile to be the road's own reason.
    pub fn lowered_limit_downgrade_ahead(&self) -> bool {
        let mi = self.position_mi;
        let end = self.total_miles().min(mi + LIMIT_DOWNGRADE_MIN_MI);
        if end - mi < LIMIT_DOWNGRADE_MIN_MI {
            return false; // not enough road left to call the downgrade sustained
        }
        let mut samples = Vec::new();
        let mut probe = mi;
        while probe <= end {
            samples.push(self.grade_at(probe) * 100.0);
            probe += LIMIT_SCAN_STRIDE_MI;
        }
        (samples.iter().sum::<f64>() / samples.len() as f64) <= LIMIT_DOWNGRADE_PCT
    }

    /// How far the just-entered corridor limit holds from the current
    /// position, or `None` when it outlasts the scan cap.
    pub fn limit_zone_length(&self, limit: f64) -> Option<f64> {
        let mut mi = self.position_mi;
        let end = self.total_miles().min(mi + LIMIT_SCAN_MAX_MI);
        while mi < end {
            mi = end.min(mi + LIMIT_SCAN_STRIDE_MI);
            if self.corridor_limit_at(mi) != limit {
                return Some(mi - self.position_mi);
            }
        }
        None
    }

    /// Lead distance for the "drops to X" pacenote, in `LIMIT_WARNING_REAL_S`
    /// real seconds at the current pace.
    pub fn limit_drop_warning_lead_mi(&self, speed: f64) -> f64 {
        let speed = speed.max(1.0);
        let miles = LIMIT_WARNING_REAL_S * speed * self.effective_time_scale() / 3600.0;
        PACENOTE_MIN_LEAD_MI.max(miles.min(LIMIT_WARNING_MAX_LEAD_MI))
    }

    /// Record that an assist just spoke the incoming posted limit itself, so
    /// the plain arrival confirmation does not repeat the same number.
    pub fn note_limit_preannounced(&mut self, limit_mph: f64) {
        let key = round_py_n(limit_mph, 1);
        if !self.limit_drop_preannounced.contains(&key) {
            self.limit_drop_preannounced.push(key);
        }
    }

    /// The next corridor limit change ahead, when it is a warn-worthy drop:
    /// `(boundary_mi, new_limit)` for the FIRST change inside the pacenote
    /// window. The scan walks an ABSOLUTE grid so the dedup key stays stable
    /// however the frames land (owner log, 2026-07-23).
    pub fn next_limit_drop(&self) -> Option<(f64, f64)> {
        let current = self.corridor_limit_at(self.position_mi);
        let mut prev = (self.position_mi / LIMIT_SCAN_STRIDE_MI).floor() * LIMIT_SCAN_STRIDE_MI;
        let end = self
            .total_miles()
            .min(self.position_mi + LIMIT_WARNING_MAX_LEAD_MI);
        while prev < end {
            let mi = end.min(prev + LIMIT_SCAN_STRIDE_MI);
            let limit = self.corridor_limit_at(mi);
            if limit != current {
                if current - limit < LIMIT_DROP_WARN_MIN_DELTA_MPH {
                    return None;
                }
                let mut boundary = mi;
                // Anchor the fine probe to ABSOLUTE hundredth-mile marks.
                let mut probe = (prev * 100.0).floor() / 100.0;
                while probe < mi {
                    probe += 0.01;
                    if self.corridor_limit_at(probe) != current {
                        boundary = probe;
                        break;
                    }
                }
                return Some((round_py_n(boundary, 2), limit));
            }
            prev = mi;
        }
        None
    }

    /// Warn before a big posted-limit drop, like a curve pacenote.
    pub fn check_limit_drop_ahead(&mut self) {
        if self.entered_zone.is_some() || self.is_facility_approach_route() {
            return;
        }
        let Some((boundary_mi, limit)) = self.next_limit_drop() else {
            return;
        };
        if self.warned_limit_drops.contains(&boundary_mi) {
            return;
        }
        let speed = self.truck.speed_mph();
        if speed <= limit + PACENOTE_MARGIN_MPH {
            return;
        }
        let ahead = boundary_mi - self.position_mi;
        if ahead > self.limit_drop_warning_lead_mi(speed) {
            return;
        }
        self.warned_limit_drops.push(boundary_mi);
        let key = round_py_n(limit, 1);
        if !self.limit_drop_preannounced.contains(&key) {
            self.limit_drop_preannounced.push(key);
        }
        let message = format!(
            "Speed limit drops to {} in {}.",
            self.speed_value(limit),
            spoken_short_miles(ahead, self.imperial())
        );
        self.emit(
            TripEventKind::GpsCue,
            SpokenMessage::new(message),
            TripEventData {
                limit_change: Some(true),
                ..Default::default()
            },
        );
    }
}
