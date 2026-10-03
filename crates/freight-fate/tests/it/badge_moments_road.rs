//! Badges earned at the wheel land on the event that earns them: the
//! weather turning, the work zone or the jam starting, the inspection
//! passing, the dial moving, the drive starting in a manual.

use ff_core::radio::{RadioReception, RadioStation, TERRESTRIAL_GROUP};
use ff_core::sim::roadside_inspection::InspectionLevel;
use ff_core::sim::trip_models::{NavigationCue, TripEvent, TripEventData, TripEventKind, Zone};
use ff_core::sim::weather::WeatherKind;
use ff_core::speech_text::SpokenMessage;
use freight_fate::app::testing::TestApp;
use freight_fate::states::driving::DrivingState;
use serde_json::json;

use crate::badge_moments_support::*;

const CHICAGO: &str = "chicago_il_us";
const CLEVELAND: &str = "cleveland_oh_us";

/// A drive out of Chicago, the truck back at the yard gate.
fn a_drive(app: &mut TestApp) -> DrivingState {
    let mut drive = run(app, CHICAGO, CLEVELAND);
    drive.trip.position_mi = 1.0;
    drive
}

fn event(kind: TripEventKind, data: TripEventData) -> TripEvent {
    TripEvent {
        kind,
        message: SpokenMessage::new("Something changed on the road."),
        data,
    }
}

// -- the sky -----------------------------------------------------------------------

/// The weather turning to `kind` mid-drive.
fn weather_turns(app: &mut TestApp, d: &mut DrivingState, kind: WeatherKind) {
    d.trip.weather.current = kind;
    let turned = event(TripEventKind::WeatherChange, TripEventData::default());
    d.handle_trip_event(&mut app.ctx, &turned);
}

/// Weather turning to `near` does not earn `id`; turning to `far` does.
fn weather_earns(id: &str, near: WeatherKind, far: WeatherKind) {
    let mut app = career_in(CHICAGO);
    let mut d = a_drive(&mut app);
    weather_turns(&mut app, &mut d, near);
    assert!(!earned(&app, id), "{id} came in {near:?}");
    weather_turns(&mut app, &mut d, far);
    assert!(earned(&app, id), "{id} missed {far:?}");
}

#[test]
fn winter_or_wind_lands_when_snow_ice_or_wind_arrives() {
    for kind in [WeatherKind::Snow, WeatherKind::Ice, WeatherKind::Wind] {
        weather_earns("winter_or_wind", WeatherKind::Rain, kind);
    }
}

#[test]
fn low_visibility_lands_when_fog_or_a_thunderstorm_arrives() {
    for kind in [WeatherKind::Fog, WeatherKind::Thunderstorm] {
        weather_earns("low_visibility", WeatherKind::Cloudy, kind);
    }
}

#[test]
fn storm_driving_needs_the_thunderstorm_itself() {
    // Fog is low visibility too, but it is not a storm.
    weather_earns("storm_driving", WeatherKind::Fog, WeatherKind::Thunderstorm);
}

#[test]
fn weather_collector_lands_with_the_last_kind_of_sky() {
    let mut app = career_in(CHICAGO);
    let seen: Vec<&str> = WeatherKind::ALL
        .iter()
        .filter(|kind| **kind != WeatherKind::Wind)
        .map(|kind| kind.name())
        .collect();
    profile(&mut app)
        .achievement_stats
        .insert("weather_seen".to_string(), json!(seen));
    let mut d = a_drive(&mut app);
    // A sky already on the list adds nothing.
    weather_turns(&mut app, &mut d, WeatherKind::Clear);
    assert!(!earned(&app, "weather_collector"));
    weather_turns(&mut app, &mut d, WeatherKind::Wind);
    assert!(earned(&app, "weather_collector"));
}

// -- work zones and jams -----------------------------------------------------------

fn zone_entered(app: &mut TestApp, d: &mut DrivingState, reason: &str) {
    let at = d.trip.position_mi;
    let entered = event(
        TripEventKind::ZoneEnter,
        TripEventData {
            zone: Some(Zone::new(at, at + 2.0, 45.0, reason)),
            ..TripEventData::default()
        },
    );
    d.handle_trip_event(&mut app.ctx, &entered);
}

fn traffic_cue(app: &mut TestApp, d: &mut DrivingState) {
    let at = d.trip.position_mi + 1.0;
    let cue = event(
        TripEventKind::GpsCue,
        TripEventData {
            cue: Some(NavigationCue::new(
                "traffic:test",
                "traffic",
                at,
                "Traffic slowing ahead.",
                "Traffic slowing now.",
            )),
            ..TripEventData::default()
        },
    );
    d.handle_trip_event(&mut app.ctx, &cue);
}

#[test]
fn construction_zone_lands_on_entering_a_work_zone() {
    let mut app = career_in(CHICAGO);
    let mut d = a_drive(&mut app);
    zone_entered(&mut app, &mut d, "heavy traffic");
    assert!(!earned(&app, "construction_zone"));
    zone_entered(&mut app, &mut d, "construction");
    assert!(earned(&app, "construction_zone"));
}

#[test]
fn traffic_slowing_lands_on_a_jam_zone_or_a_traffic_cue() {
    let mut app = career_in(CHICAGO);
    let mut d = a_drive(&mut app);
    zone_entered(&mut app, &mut d, "construction");
    assert!(!earned(&app, "traffic_slowing"));
    zone_entered(&mut app, &mut d, "heavy traffic");
    assert!(earned(&app, "traffic_slowing"));
    drop(d);
    drop(app);

    let mut app = career_in(CHICAGO);
    let mut d = a_drive(&mut app);
    traffic_cue(&mut app, &mut d);
    assert!(earned(&app, "traffic_slowing"));
}

#[test]
fn jam_and_cones_needs_both_on_one_trip() {
    let mut app = career_in(CHICAGO);
    let mut first = a_drive(&mut app);
    zone_entered(&mut app, &mut first, "construction");
    drop(first);
    // The jam comes on the next trip: the cones were yesterday's.
    let mut second = a_drive(&mut app);
    traffic_cue(&mut app, &mut second);
    assert!(!earned(&app, "jam_and_cones"));
    zone_entered(&mut app, &mut second, "construction");
    assert!(earned(&app, "jam_and_cones"));
}

// -- the scale house ---------------------------------------------------------------

fn clean_inspection(app: &mut TestApp, d: &mut DrivingState) {
    let report = d.inspection_report(&app.ctx, InspectionLevel::DriverOnly);
    assert!(report.clean(), "{:?}", report.findings);
    d.settle_inspection(&mut app.ctx, &report);
}

#[test]
fn inspection_lands_when_a_roadside_inspection_comes_back_clean() {
    let mut app = career_in(CHICAGO);
    let mut d = a_drive(&mut app);
    assert!(!earned(&app, "inspection"));
    clean_inspection(&mut app, &mut d);
    assert!(earned(&app, "inspection"));
}

#[test]
fn scale_regular_lands_on_the_fifth_clean_inspection() {
    let mut app = career_in(CHICAGO);
    profile(&mut app)
        .achievement_stats
        .insert("inspections_passed".to_string(), json!(3));
    let mut d = a_drive(&mut app);
    clean_inspection(&mut app, &mut d);
    assert!(!earned(&app, "scale_regular"), "four is not five");
    clean_inspection(&mut app, &mut d);
    assert!(earned(&app, "scale_regular"));
}

// -- the cab -----------------------------------------------------------------------

#[test]
fn manual_driver_lands_when_a_delivery_starts_in_a_manual() {
    let mut app = career_in(CHICAGO);
    let mut automatic = a_drive(&mut app);
    automatic.trip.truck.transmission.automatic = true;
    automatic.enter_drive(&mut app.ctx);
    assert!(!earned(&app, "manual_driver"));
    drop(automatic);
    let mut manual = a_drive(&mut app);
    manual.trip.truck.transmission.automatic = false;
    manual.enter_drive(&mut app.ctx);
    assert!(earned(&app, "manual_driver"));
}

// -- the dial ----------------------------------------------------------------------

fn a_station(id: &str) -> RadioReception {
    RadioReception::new(
        RadioStation::new(id, "Test Radio", "", "country", "test"),
        None,
        1.0,
        "test",
    )
}

#[test]
fn radio_dial_wanderer_lands_on_the_twenty_fifth_station_heard() {
    let mut app = career_in(CHICAGO);
    let heard: Vec<String> = (0..23).map(|n| format!("ff:heard-{n}")).collect();
    profile(&mut app)
        .achievement_stats
        .insert("radio_stations_heard".to_string(), json!(heard));
    let mut d = a_drive(&mut app);
    d.track_radio_badges(&mut app.ctx, &a_station("ff:heard-24"));
    // The same station again is not a new one.
    d.track_radio_badges(&mut app.ctx, &a_station("ff:heard-24"));
    assert!(!earned(&app, "radio_dial_wanderer"));
    d.track_radio_badges(&mut app.ctx, &a_station("ff:heard-25"));
    assert!(earned(&app, "radio_dial_wanderer"));
}

#[test]
fn radio_faded_out_lands_when_the_tuned_station_drops_past_its_contour() {
    let mut app = career_in("denver_co_us");
    app.ctx.settings.radio_streamer_safe = false;
    let mut d = run(&mut app, "denver_co_us", "salt_lake_city_ut_us");
    d.trip.position_mi = 0.0;
    d.trip.truck.start_engine();
    d.update_audio(&mut app.ctx, 0.0);
    // A short-reach station on Denver's mast, and nothing else local on
    // the air, so the fade has somewhere unambiguous to go.
    let station = RadioStation {
        lat: Some(39.7392),
        lon: Some(-104.9903),
        range_miles: 20.0,
        ..RadioStation::new("kmhf-denver", "Mile High 91.5", "KMHF", "variety", "test")
    };
    let mut catalog = d.radio.catalog.clone();
    catalog.retain(|s| ff_core::radio::dial_group(s) != TERRESTRIAL_GROUP);
    catalog.push(station);
    d.radio.set_catalog(catalog);
    d.with_radio_backend(&mut app.ctx, |radio, backend| {
        radio.select_station("kmhf-denver", Some(backend))
    });
    fn frame(d: &mut DrivingState, app: &mut TestApp) {
        d.sync_radio_settings(&mut app.ctx);
        d.update_radio_reception(&mut app.ctx, 1.5);
    }
    frame(&mut d, &mut app);
    assert_eq!(d.radio.tuned_station().id, "kmhf-denver");
    d.trip.position_mi = 10.0;
    frame(&mut d, &mut app);
    assert!(!earned(&app, "radio_faded_out"), "still inside the contour");
    d.trip.position_mi = 120.0;
    frame(&mut d, &mut app);
    assert!(earned(&app, "radio_faded_out"));
}
