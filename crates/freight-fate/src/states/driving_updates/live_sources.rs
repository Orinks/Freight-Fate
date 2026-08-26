//! The live-data sources a drive can switch to mid-trip: real weather, real
//! traffic, real truck parking.
//!
//! `GameContext` only hands out borrows of its session-long providers, and a
//! `WeatherSystem`/`Trip` has to OWN its provider, so a switch flipped
//! mid-drive builds this drive's own -- the same class, transport and
//! behaviour, exactly as `driving/init.rs` does at construction.
//!
//! Lifted out of `radio.rs`, which shared the settings pass with these and
//! nothing else.

use std::sync::Arc;

use ff_core::sim::real_traffic::RealTrafficProvider;
use ff_core::sim::real_weather::RealWeatherProvider;
use ff_core::sim::trip_traffic::TrafficProvider;
use ff_core::sim::truck_parking::TruckParkingProvider;
use ff_core::sim::weather::WeatherProvider;

use crate::app::GameContext;
use crate::net::UreqTransport;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

impl DrivingState {
    pub fn sync_weather_source(&mut self, ctx: &mut GameContext) {
        let real = ctx.settings.real_weather;
        let controls_calendar = ctx.settings.live_weather_controls_calendar;
        if real == self.weather_source_real
            && controls_calendar == self.live_weather_controls_calendar
        {
            return;
        }
        self.weather_source_real = real;
        self.live_weather_controls_calendar = controls_calendar;
        self.trip.weather.provider = if real {
            Some(
                Box::new(RealWeatherProvider::with_nws(Arc::new(UreqTransport)))
                    as Box<dyn WeatherProvider>,
            )
        } else {
            None
        };
        self.trip.weather.live_weather_controls_calendar = controls_calendar;
        if !controls_calendar {
            // Include time already driven when the active trip switches back
            // to the independent in-game calendar.
            self.trip.weather.game_hours =
                Some(profile_of(ctx).calendar_game_hours() + self.trip.game_minutes / 60.0);
        }
        if !real {
            self.trip.weather.live = false;
        }
        let effects = self.trip.weather.effects();
        ctx.audio.set_weather(effects.sound);
        ctx.audio.set_wind(effects.wind);
    }

    pub fn sync_traffic_source(&mut self, ctx: &mut GameContext) {
        let real = ctx.settings.real_traffic;
        if real == self.traffic_source_real {
            return;
        }
        self.traffic_source_real = real;
        self.trip.traffic_provider = if real {
            Some(Arc::new(RealTrafficProvider::new(Arc::new(UreqTransport)))
                as Arc<dyn TrafficProvider>)
        } else {
            None
        };
    }

    pub fn sync_parking_source(&mut self, ctx: &mut GameContext) {
        let real = ctx.settings.real_parking;
        if real == self.parking_source_real {
            return;
        }
        self.parking_source_real = real;
        self.trip.parking_provider = if real {
            Some(Arc::new(TruckParkingProvider::new(Arc::new(UreqTransport))))
        } else {
            None
        };
    }
}
