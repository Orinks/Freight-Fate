//! Where the truck is on the map and what the clock says there: the road
//! coordinate at a trip mile, the weather sampling cell, the time zones along
//! the route, and the local and appointment clocks (the place-and-time section
//! of `trip.py`).

use crate::data::world_models::Leg;
use crate::sim::timezones::{appointment_text, city_zone, zone_for, TimeZone};
use crate::sim::trip_models::*;
use crate::sim::trip_route_helpers::stop_offset_for_direction;

use super::Trip;

impl Trip {
    /// Linear lat/lon along a leg's route points at an A-to-B offset.
    pub fn leg_latlon_at(leg: &Leg, at_mi: f64) -> (f64, f64) {
        let pts = leg.route_points();
        if pts.is_empty() {
            return (0.0, 0.0);
        }
        let mut prev = &pts[0];
        for pt in pts {
            if pt.at_mi >= at_mi {
                let span = pt.at_mi - prev.at_mi;
                let fraction = if span > 0.0 {
                    (at_mi - prev.at_mi) / span
                } else {
                    0.0
                };
                return (
                    prev.lat + (pt.lat - prev.lat) * fraction,
                    prev.lon + (pt.lon - prev.lon) * fraction,
                );
            }
            prev = pt;
        }
        (prev.lat, prev.lon)
    }

    /// Interpolated road coordinate at a trip position.
    pub fn latlon_at(&self, mile: Option<f64>) -> (f64, f64) {
        let sample_mile = mile.unwrap_or(self.position_mi);
        let (leg_i, leg_start) = self.leg_at_mile(sample_mile);
        let leg = &self.route.legs[leg_i];
        let route_offset = (sample_mile - leg_start).clamp(0.0, leg.miles.max(0.0));
        let forward = self.route.cities[leg_i] == leg.a;
        let native_offset = if forward {
            route_offset
        } else {
            leg.miles - route_offset
        };
        if leg.route_points().len() >= 2 {
            return Self::leg_latlon_at(leg, native_offset);
        }
        // A leg with no baked geometry falls back to interpolating between
        // its two city coordinates -- but a synthetic route names cities the
        // world has never heard of. Answering "no coordinate" is right there.
        let (Some(start), Some(end)) = (
            self.route
                .cities
                .get(leg_i)
                .and_then(|c| self.world.cities.get(c)),
            self.route
                .cities
                .get(leg_i + 1)
                .and_then(|c| self.world.cities.get(c)),
        ) else {
            return (0.0, 0.0);
        };
        let fraction = if leg.miles > 0.0 {
            route_offset / leg.miles
        } else {
            0.0
        };
        (
            start.lat + (end.lat - start.lat) * fraction,
            start.lon + (end.lon - start.lon) * fraction,
        )
    }

    /// Stable 20-mile route cell, cut short at a state line: the state is
    /// part of the key, so crossing a line asks the provider afresh, and
    /// when the crossing happened INSIDE the current cell the truck's own
    /// position is used instead (Brandon, 2026-08-18). None for a route the
    /// world cannot place.
    pub fn weather_location(&self) -> Option<(String, f64, f64)> {
        if self.route.legs.is_empty() {
            return None;
        }
        let (leg_i, leg_start) = self.leg_at_mile(self.position_mi);
        let leg = &self.route.legs[leg_i];
        let route_offset = (self.position_mi - leg_start).clamp(0.0, leg.miles.max(0.0));
        let cell = (route_offset / 20.0).floor() as i64;
        let mut sample_mile = (leg_start + cell as f64 * 20.0).min(leg_start + leg.miles);
        let state = self.state_at(Some(self.position_mi));
        if !state.is_empty() && self.state_at(Some(sample_mile)) != state {
            // The cell straddles a state line: sample the first stretch of
            // it that is in the truck's state, not the truck itself. Sampling
            // the live position moved the station key a few hundred yards at
            // a time for the rest of the cell, and each move was a fresh NWS
            // fetch -- 29 in one minute crossing into Louisiana on I-20
            // (Brandon's log, 2026-09-01). The key must not churn inside one
            // state; neither may the point it is looked up at.
            let mut probe = sample_mile;
            while probe < self.position_mi && self.state_at(Some(probe)) != state {
                probe += 0.25;
            }
            sample_mile = probe.min(self.position_mi);
        }
        let (lat, lon) = self.latlon_at(Some(sample_mile));
        let from = self.route.cities.get(leg_i)?;
        let to = self.route.cities.get(leg_i + 1)?;
        Some((format!("route:{from}:{to}:{cell}:{state}"), lat, lon))
    }

    /// (trip mile, zone) along the route, from city and route-point geometry.
    /// State crossings are sampled AT their exact mileposts (owner caught the
    /// Arizona-to-California flip ten miles late, 2026-07-22).
    pub fn timezone_samples(&self) -> Vec<(f64, TimeZone)> {
        let world = self.world;
        let mut samples: Vec<(f64, TimeZone)> = Vec::new();
        for (i, (start, leg)) in self
            .leg_starts
            .iter()
            .zip(self.route.legs.iter())
            .enumerate()
        {
            let forward = self.route.cities[i] == leg.a;
            if let Some(city) = world.cities.get(&self.route.cities[i]) {
                if city.lat != 0.0 || city.lon != 0.0 {
                    samples.push((*start, city_zone(city)));
                }
            }
            for pt in leg.route_points() {
                let offset = stop_offset_for_direction(pt.at_mi, leg.miles, forward);
                let zone = zone_for(pt.lat, pt.lon, &leg_state_at(leg, pt.at_mi));
                samples.push((start + offset, zone));
            }
            for crossing in leg.state_crossings() {
                let offset = stop_offset_for_direction(crossing.at_mi, leg.miles, forward);
                let (lat, lon) = Self::leg_latlon_at(leg, crossing.at_mi);
                let mut before = zone_for(lat, lon, &crossing.from_state);
                let mut after = zone_for(lat, lon, &crossing.state);
                // Traversed backward, the truck meets the crossing from the
                // other side: the A-to-B "to" state is what it is leaving.
                if !forward {
                    std::mem::swap(&mut before, &mut after);
                }
                samples.push(((start + offset - 0.05).max(0.0), before));
                samples.push((start + offset, after));
            }
        }
        if let Some(last) = self.route.cities.last().and_then(|c| world.cities.get(c)) {
            if last.lat != 0.0 || last.lon != 0.0 {
                samples.push((self.total_miles(), city_zone(last)));
            }
        }
        samples.sort_by(|a, b| a.0.partial_cmp(&b.0).expect("finite mileposts"));
        samples
    }

    /// Start zone plus the deduped clock-change mileposts for the route. A
    /// flip that reverts within `TIMEZONE_DWELL_MI` is a road hugging the
    /// boundary, not a crossing, and is dropped.
    pub fn compute_timezone_crossings(&self) -> (TimeZone, Vec<TimezoneCrossing>) {
        let samples = self.timezone_samples();
        if samples.is_empty() {
            return (zone_for(0.0, 0.0, ""), Vec::new());
        }
        let mut current = samples[0].1;
        let start = current;
        let mut crossings = Vec::new();
        for (i, &(mile, zone)) in samples.iter().enumerate() {
            if zone.key == current.key {
                continue;
            }
            let mut settled = true;
            for &(later_mile, later_zone) in &samples[i + 1..] {
                if later_mile - mile > TIMEZONE_DWELL_MI {
                    break;
                }
                if later_zone.key == current.key {
                    settled = false;
                    break;
                }
            }
            if settled {
                crossings.push(TimezoneCrossing {
                    at_mi: mile,
                    from_zone: current,
                    to_zone: zone,
                });
                current = zone;
            }
        }
        (start, crossings)
    }

    /// The time zone in effect at a trip milepost.
    pub fn timezone_at(&self, mile: f64) -> TimeZone {
        let mut zone = self.start_timezone;
        for crossing in &self.timezone_crossings {
            if crossing.at_mi <= mile {
                zone = crossing.to_zone;
            } else {
                break;
            }
        }
        zone
    }

    pub fn current_timezone(&self) -> TimeZone {
        self.timezone_at(self.position_mi)
    }

    pub fn destination_timezone(&self) -> TimeZone {
        self.timezone_at(self.total_miles())
    }

    /// The wall clock where the truck is right now; what the player hears.
    /// `current_hour` stays on the absolute (Eastern-reference) timeline for
    /// durations and deadlines; only speech and day/night feel go local.
    pub fn local_hour(&self) -> f64 {
        (self.current_hour() + self.current_timezone().offset_h).rem_euclid(24.0)
    }

    /// The local wall clock at departure, for day/night placement.
    pub fn local_start_hour(&self) -> f64 {
        (self.start_hour + self.start_timezone.offset_h).rem_euclid(24.0)
    }

    /// The delivery appointment as a receiver would quote it: the wall clock
    /// in the destination's zone. `zone` overrides where the appointment is
    /// read (a pickup drive's caller passes the delivery city's zone).
    pub fn deadline_clock_text(&self, deadline_game_h: f64, zone: Option<TimeZone>) -> String {
        let now = self.start_hour + self.game_minutes / 60.0;
        let remaining = deadline_game_h - self.game_minutes / 60.0;
        appointment_text(
            now,
            remaining,
            zone.unwrap_or_else(|| self.destination_timezone()),
        )
    }
}
