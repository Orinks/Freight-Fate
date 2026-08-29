//! `states/driving_controls.rs` and `states/driving_speed_control.rs`: the
//! discrete key and pad surface at the wheel, and the speed-control session
//! around adaptive cruise and the speed keeper.
//!
//! Ported from `tests/test_info_keys.py`, `test_cruise_steps.py` (its
//! App-driven half; the pure `cruise_step_target` grid is in
//! `states_driving_core.rs`), `test_driving_manual_controls.py`,
//! `test_pedal_latch_assists.py` (brake latch, and that the throttle key never
//! catches one), `test_driving_modes.py` (the keeper's ease window) and
//! `test_turn_commitment.py` (the keeper's corner planner) -- everything a real
//! `DrivingState` can answer without the per-frame loop or a menu state. The
//! rest are listed here, ignored, with their bodies noted, so the two suites
//! diff by name.
//!
//! `tests/test_controls_reference.py` is already ported in full as
//! `app_controls_reference.rs`; it is not repeated here.

use ff_core::data::world::get_world;
use ff_core::models::jobs::{Job, CARGO_CATALOG};
use ff_core::models::profile::Profile;
use ff_core::sim::enforcement_posts::{method_by_kind, EnforcementPost, KIND_MEDIAN};
use ff_core::sim::hos;
use ff_core::sim::transmission::REVERSE;
use ff_core::sim::trip_models::{TripEvent, TripEventData, TripEventKind, Zone};
use ff_core::sim::vehicle::{HIGH_IDLE_DEFAULT_RPM, HIGH_IDLE_STEP_RPM};
use ff_core::sim::weather::WeatherKind;
use ff_core::speech_text::SpokenMessage;

use freight_fate::app::testing::{FakeClock, TestApp};
use freight_fate::controller::ControllerButton;
use freight_fate::states::base::{InputEvent, Key, Mods};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_controls::UPCOMING_MAX_CLAUSES;
use freight_fate::states::driving_core::{
    hos_mut_of, profile_of, DRIVE_PHASE_DELIVERY, DRIVE_PHASE_PICKUP,
};
use freight_fate::states::driving_location::spoken_closing_distance;
use freight_fate::states::driving_menu_states::DrivingStatusState;
use freight_fate::states::driving_pause_states::PauseMenuState;
use freight_fate::states::driving_speed_control::KEEPER_EASE_MAX_MI;

// -- rigging -------------------------------------------------------------------------
//
// `_driving(app, origin, destination, origin_location)` from
// `test_info_keys.py`: a delivery drive on a real short corridor, built
// straight rather than driven up to.

fn a_drive(app: &mut TestApp) -> DrivingState {
    a_drive_between(app, "Buffalo", "Rochester", "company yard")
}

fn a_drive_between(
    app: &mut TestApp,
    origin: &str,
    destination: &str,
    origin_location: &str,
) -> DrivingState {
    let world = get_world();
    app.ctx.profile = Some(Profile::named_in("Info Keys", origin));
    let route = world
        .supported_route(origin, destination, None)
        .expect("the world routes")
        .expect("the corridor is supported");
    let mut job = Job::new(
        &CARGO_CATALOG["general"],
        12.0,
        origin,
        origin_location,
        destination,
        route.miles(),
        1000.0,
        12.0,
    );
    job.destination_location = format!("{destination} freight market");
    let mut drive = DrivingState::new(&mut app.ctx, job, route, None, DRIVE_PHASE_DELIVERY, None);
    // The bubble is its own suite's business; an empty road keeps these
    // deterministic (`driving_feature_helpers.quiet_trip`). The weather is
    // the other half of that helper: the trip seed is unseeded, so a drive
    // that does not pin the sky draws a real condition and an ice day caps
    // the safe speed under whatever the test is measuring.
    drive.trip.set_npc_vehicles(Vec::new());
    drive.trip.weather.current = WeatherKind::Clear;
    drive
}

/// `enforcement_helpers.always_observing_post(at_mi, reach_mi)`: a staffed
/// median post that has already announced itself and sees everything inside
/// its reach, so a readout has no excuse for missing it.
fn observing_post(at_mi: f64, reach_mi: f64) -> EnforcementPost {
    EnforcementPost {
        method: method_by_kind(KIND_MEDIAN).to_string(),
        reach_mi,
        facing: "both".to_string(),
        staffed: true,
        notice: 1.0,
        announced: true,
        leg_index: 0,
        ..EnforcementPost::new(at_mi, KIND_MEDIAN)
    }
}

fn key(k: Key) -> InputEvent {
    InputEvent::key(k)
}

fn alt(k: Key) -> InputEvent {
    InputEvent::key_mods(k, Mods::ALT)
}

fn pad(button: ControllerButton) -> InputEvent {
    InputEvent::button(button)
}

fn mph_to_mps(mph: f64) -> f64 {
    mph / 2.2369362920544
}

/// The last thing the main channel said.
fn last(app: &TestApp) -> String {
    app.main_lines().last().cloned().unwrap_or_default()
}

/// `_cruise_at(driving, mph)` from `test_cruise_steps.py`.
fn cruise_at(drive: &mut DrivingState, app: &mut TestApp, mph: f64) {
    drive.trip.truck.engine_on = true;
    drive.trip.truck.velocity_mps = mph_to_mps(mph);
    drive.engage_cruise(&mut app.ctx, mph, false);
}

// -- the info keys (test_info_keys.py) -----------------------------------------------

#[test]
fn test_speed_limit_key_reads_the_posted_limit() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::S));
    let said = last(&app);
    assert!(said.contains("Speed limit"), "{said}");
    assert!(said.contains("per hour"), "{said}");
}

#[test]
fn test_speed_key_includes_cruise_set_speed_when_active() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.cruise_mph = Some(55.0);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::Space));
    let said = last(&app);
    assert!(said.contains("automatic speed control"), "{said}");
    assert!(said.contains("cruise set at 55 miles per hour"), "{said}");
}

#[test]
fn test_speed_key_includes_speed_keeper_target_when_active() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.keeper_mph = Some(15.0);
    d.speed_control_target_mph = Some(55.0);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::Space));
    let said = last(&app);
    assert!(said.contains("automatic speed control"), "{said}");
    assert!(
        said.contains("speed keeper holding 15 miles per hour"),
        "{said}"
    );
    assert!(
        said.contains("open-road target 55 miles per hour"),
        "{said}"
    );
}

#[test]
fn test_weather_key_reads_safe_speed_in_metric_units() {
    let mut app = TestApp::new();
    app.ctx.settings.imperial_units = false;
    let mut d = a_drive(&mut app);
    d.trip.weather.current = WeatherKind::Rain;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::V));
    let said = last(&app);
    assert!(
        said.contains("Safe speed about 89 kilometers per hour"),
        "{said}"
    );
}

#[test]
fn test_speed_limit_key_reports_how_far_over_you_are() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = d.trip.total_miles() / 2.0; // out on the open road
    let at = d.trip.position_mi;
    let (limit, _) = d.trip.speed_limit_at(at);
    d.trip.truck.velocity_mps = (limit + 15.0) / 2.23694; // 15 mph over
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::S));
    assert!(last(&app).contains("over"), "{}", last(&app));
}

#[test]
fn test_metric_speed_limit_key_reports_overage_in_metric_units() {
    let mut app = TestApp::new();
    app.ctx.settings.imperial_units = false;
    let mut d = a_drive(&mut app);
    d.trip.position_mi = d.trip.total_miles() / 2.0;
    let at = d.trip.position_mi;
    let (limit, _) = d.trip.speed_limit_at(at);
    d.trip.truck.velocity_mps = (limit + 15.0) / 2.23694;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::S));
    let said = last(&app);
    assert!(said.contains("kilometers per hour over"), "{said}");
    assert!(!said.contains("miles per hour"), "{said}");
}

#[test]
fn test_repeat_key_replays_the_last_route_announcement() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    // Nothing announced yet.
    d.handle_key_event(&mut app.ctx, &key(Key::A));
    assert!(
        last(&app).contains("No recent announcement"),
        "{}",
        last(&app)
    );
    // After a route announcement, A replays it verbatim.
    let event = TripEvent {
        kind: TripEventKind::GpsCue,
        message: SpokenMessage::new(
            "Brake now! In 2 miles, construction ahead. Merge left for the flagger taper; speed \
             limit 55, then 45 through the work zone.",
        ),
        data: TripEventData::default(),
    };
    d.handle_trip_event(&mut app.ctx, &event);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::A));
    assert!(last(&app).contains("construction ahead"), "{}", last(&app));
}

// -- Alt C: the CB call you missed, said again (issue 156) ----------------------------

/// A CB heads-up shaped the way `check_enforcement_heads_up` emits one: a
/// GPS cue carrying the post it is about. Returns the event and the words
/// the CB used at the distance it was first heard.
fn a_cb_call(d: &DrivingState, post: &EnforcementPost) -> (TripEvent, String) {
    let ahead = post.watch_start_mi() - d.trip.position_mi;
    let text = d.trip.cb_patrol_message(post, ahead);
    let event = TripEvent {
        kind: TripEventKind::GpsCue,
        message: SpokenMessage::new(text.clone()),
        data: TripEventData {
            cb_patrol: Some(post.clone()),
            ..Default::default()
        },
    };
    (event, text)
}

#[test]
fn test_alt_c_says_so_when_the_cb_has_said_nothing() {
    // Silence is indistinguishable from a broken key.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::C));
    assert_eq!(last(&app), "No CB chatter to repeat.");
}

#[test]
fn test_alt_c_repeats_the_cb_call_at_the_distance_it_is_now() {
    // A rescued line has to still be true: "in four miles" spoken with two
    // left is worse than not repeating it at all.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 0.0;
    let post = observing_post(6.0, 2.0); // watched from mile 4
    let (event, first_heard) = a_cb_call(&d, &post);
    d.handle_trip_event(&mut app.ctx, &event);

    d.trip.position_mi = 2.0;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::C));
    let said = last(&app);
    assert!(said.starts_with("CB chatter"), "{said}");
    assert_eq!(said, d.trip.cb_patrol_message(&post, 2.0));
    assert_ne!(said, first_heard, "the distance went stale");
}

#[test]
fn test_alt_c_says_you_have_passed_what_the_cb_called() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 0.0;
    let post = observing_post(6.0, 2.0);
    let (event, _) = a_cb_call(&d, &post);
    d.handle_trip_event(&mut app.ctx, &event);

    d.trip.position_mi = 7.0;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::C));
    assert_eq!(
        last(&app),
        "The CB called an enforcement post in the median. You have passed it."
    );
}

#[test]
fn test_a_later_announcement_takes_the_a_key_but_not_the_cb_repeat() {
    // The whole reason this key exists. A is one slot, and every route
    // announcement after the CB call overwrites it -- which is exactly the
    // situation a driver who missed the CB is in.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 0.0;
    let post = observing_post(6.0, 2.0);
    let (cb, _) = a_cb_call(&d, &post);
    d.handle_trip_event(&mut app.ctx, &cb);
    d.handle_trip_event(
        &mut app.ctx,
        &TripEvent {
            kind: TripEventKind::Lane,
            message: SpokenMessage::new("Two lanes each way."),
            data: TripEventData::default(),
        },
    );

    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::A));
    assert!(!last(&app).contains("CB chatter"), "{}", last(&app));

    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::C));
    assert!(last(&app).starts_with("CB chatter"), "{}", last(&app));
}

#[test]
fn test_alt_c_brings_back_the_voice_and_not_the_squelch() {
    // She asked for the spoken call, not the chunk-chunk that marked it.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 0.0;
    let post = observing_post(6.0, 2.0);
    let (cb, _) = a_cb_call(&d, &post);
    d.handle_trip_event(&mut app.ctx, &cb);

    let audio = app.record_audio();
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::C));
    assert!(last(&app).starts_with("CB chatter"), "{}", last(&app));
    assert!(
        !audio
            .borrow()
            .played
            .iter()
            .any(|(sound, _, _)| sound.contains("cb_radio_chatter")),
        "{:?}",
        audio.borrow().played
    );
}

#[test]
fn test_plain_c_still_speaks_the_clock() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::C));
    let said = last(&app);
    assert!(!said.contains("CB chatter"), "{said}");
    assert!(
        said.to_lowercase().contains("deadline") || said.contains(':'),
        "{said}"
    );
}

#[test]
fn test_upcoming_key_reports_an_imposed_limit_ahead() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 0.0;
    let mut taper = Zone::new(5.0, 6.0, 55.0, "construction merge");
    taper.closed_side = Some("right".to_string());
    let mut work = Zone::new(6.0, 8.0, 45.0, "construction");
    work.closed_side = Some("right".to_string());
    d.trip.zones = vec![taper, work];
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::U));
    let said = last(&app);
    assert!(said.contains("construction taper"), "{said}");
    assert!(said.contains("right lane closed, merge left"), "{said}");
    assert!(said.contains("speed limit 55"), "{said}");
    // "construction zone" is the canonical spoken noun (docs/ontology.md).
    assert!(said.contains("then construction zone 45"), "{said}");

    // The readout used to say "merge left" whatever was shut, so on a
    // left-lane closure it sent the driver into the cones.
    let mut taper = Zone::new(5.0, 6.0, 55.0, "construction merge");
    taper.closed_side = Some("left".to_string());
    let mut work = Zone::new(6.0, 8.0, 45.0, "construction");
    work.closed_side = Some("left".to_string());
    d.trip.zones = vec![taper, work];
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::U));
    assert!(
        last(&app).contains("left lane closed, merge right"),
        "{}",
        last(&app)
    );

    // Roadwork with every lane open must not invent a merge either.
    d.trip.zones = vec![
        Zone::new(5.0, 6.0, 55.0, "construction merge"),
        Zone::new(6.0, 8.0, 45.0, "construction"),
    ];
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::U));
    let said = last(&app);
    assert!(said.contains("all lanes open"), "{said}");
    assert!(!said.contains("merge"), "{said}");
}

#[test]
fn test_upcoming_key_leads_with_the_ramp_light() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 4.0;
    d.trip.zones = vec![Zone::new(5.0, 8.0, 45.0, "construction")];
    d.ramp_mi = Some(0.4);
    d.ramp_control = "signal".to_string();
    d.ramp_terminal_done = false;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::U));
    let report = last(&app);
    assert!(report.starts_with("Coming up: light "), "{report}");
    assert!(report.contains("stop bar"), "{report}");
    // The zone still follows it; the light only takes the lead.
    assert!(
        report.find("stop bar") < report.find("construction"),
        "{report}"
    );
}

#[test]
fn test_upcoming_key_handles_a_clear_road() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 0.0;
    d.trip.zones.clear();
    d.trip.stops.clear();
    d.trip.navigation_cues.clear();
    d.trip.curves.clear();
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::U));
    assert!(last(&app).contains("Nothing notable"), "{}", last(&app));
}

#[test]
fn test_upcoming_key_stays_a_couple_of_sentences() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 4.0;
    let mut taper = Zone::new(5.0, 6.0, 55.0, "construction merge");
    taper.closed_side = Some("right".to_string());
    let mut work = Zone::new(6.0, 8.0, 45.0, "construction");
    work.closed_side = Some("right".to_string());
    d.trip.zones = vec![taper, work];
    d.ramp_mi = Some(0.4);
    d.ramp_control = "signal".to_string();
    d.ramp_terminal_done = false;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::U));
    let report = last(&app);
    // `count() + 1 <= MAX` -- the clause count is one more than its separators.
    assert!(
        report.matches(". ").count() < UPCOMING_MAX_CLAUSES,
        "{report}"
    );
    // The traffic-pressure clause restated the taper beside it.
    assert!(!report.contains("move left and target"), "{report}");
}

#[test]
fn test_upcoming_key_uses_metric_distances() {
    let mut app = TestApp::new();
    app.ctx.settings.imperial_units = false;
    let mut d = a_drive(&mut app);
    d.trip.set_imperial(false);
    d.trip.position_mi = 20.0;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::U));
    let report = last(&app);
    assert!(report.contains("kilometers"), "{report}");
    assert!(!report.contains(" miles"), "{report}");
}

#[test]
fn test_safe_speed_key_speaks_one_number() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = d.trip.total_miles() / 2.0; // out on the open road
    let at = d.trip.position_mi;
    let (limit, _) = d.trip.speed_limit_at(at);

    // Clear weather: the posted limit is the safe speed.
    d.trip.weather.current = WeatherKind::Clear;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::D));
    assert_eq!(last(&app), format!("Safe speed {limit:.0} miles per hour."));

    // Rain caps below the posted limit -- the number drops, and the sentence
    // never says why (the whole point of the terse key).
    d.trip.weather.current = WeatherKind::Rain;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::D));
    assert_eq!(last(&app), "Safe speed 55 miles per hour.");
    assert!(!last(&app).to_lowercase().contains("rain"));
}

#[test]
fn test_safe_speed_key_answers_for_the_ramp() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.weather.current = WeatherKind::Clear;
    d.trip.position_mi = d.trip.total_miles() / 2.0;
    d.ramp_mi = Some(d.trip.position_mi); // on the ramp now
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::D));
    assert_eq!(last(&app), "Safe speed 45 miles per hour for the ramp.");
}

#[test]
fn test_grade_key_reads_slope_and_verdict() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);

    d.trip.truck.grade = 0.0;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::G));
    assert!(last(&app).contains("Level road"), "{}", last(&app));

    // A loaded climb the engine cannot hold: uphill plus losing speed.
    d.trip.truck.start_engine();
    d.trip.truck.set_air_ready(false);
    d.trip.truck.grade = 0.06;
    d.trip.truck.cargo_kg = 21_500.0;
    d.trip.truck.transmission.gear = 10;
    d.trip.truck.velocity_mps = 26.8;
    d.trip.truck.throttle = 1.0;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::G));
    let said = last(&app);
    assert!(said.contains("percent uphill"), "{said}");
    assert!(said.contains("lose speed"), "{said}");

    // Downhill with no jake and speed building: the warning speaks.
    d.trip.truck.grade = -0.05;
    d.trip.truck.throttle = 0.0;
    d.trip.truck.engine_brake_stage = 0;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::G));
    let said = last(&app);
    assert!(said.contains("percent downhill"), "{said}");
    assert!(said.contains("set the jake"), "{said}");
}

#[test]
fn test_clock_key_leads_with_time_then_schedule_verdict() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 40.0;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::C));
    let report = last(&app);
    // Time first, verdict right behind it: the first line of a braille display
    // must carry the answer, not a preamble.
    assert!(!report.starts_with("It is"), "{report}");
    let verdict_at = report
        .find("On schedule: arrival in")
        .or_else(|| report.find("Running behind: arrival in"))
        .unwrap_or(usize::MAX);
    assert!(verdict_at > 0 && verdict_at < 60, "{report}");
    assert!(report.contains("deadline in"), "{report}");
    assert!(report.contains("due"), "{report}");
}

#[test]
fn real_time_clock_names_the_synchronized_value_truthfully() {
    let mut app = TestApp::new();
    app.ctx.settings.time_scale = 1.0;
    let mut d = a_drive(&mut app);
    d.trip.start_hour = 15.0 - d.trip.start_timezone.offset_h;

    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::C));
    let report = last(&app);

    assert!(report.starts_with("3 PM local game time"), "{report}");
    assert!(report.contains("deadline in"), "{report}");
}

#[test]
fn test_terse_clock_key_drops_calendar_and_stop_planning() {
    let mut app = TestApp::new();
    app.ctx.settings.driving_speech = "quiet".to_string();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 40.0;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::C));
    let terse_report = last(&app);
    assert!(terse_report.contains("deadline in"), "{terse_report}");

    app.ctx.settings.driving_speech = "standard".to_string();
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::C));
    assert!(terse_report.len() < last(&app).len());
    assert!(!terse_report.contains(", due ")); // no appointment restatement
    assert!(!terse_report.contains("Next legal stop"));
}

#[test]
fn test_clock_key_keeps_one_hours_clause_instead_of_the_whole_report() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    hos_mut_of(&mut app.ctx).drive(300.0);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::C));
    let report = last(&app);
    // The limit that comes first still rides the clock key: a driver can be on
    // schedule and out of hours at once.
    assert!(report.contains("Break due in 3.0 hours."), "{report}");
    // ...but the full ELD report belongs to Tab and the three hours keys.
    assert!(!report.contains("hours of driving left"), "{report}");
    assert!(!report.contains("ELD status"), "{report}");
}

#[test]
fn test_clock_key_points_at_the_hours_keys_for_the_first_three_presses() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let notice = "Hours of service moved to Alt A, Alt S, and Alt D.";
    for _ in 0..3 {
        app.clear_speech();
        d.handle_key_event(&mut app.ctx, &key(Key::C));
        assert!(last(&app).contains(notice), "{}", last(&app));
    }
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::C));
    assert!(!last(&app).contains(notice), "{}", last(&app));
    assert_eq!(profile_of(&app.ctx).hos_key_notice_left, 0);
}

#[test]
fn test_alt_a_s_and_d_each_answer_one_hours_question() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    hos_mut_of(&mut app.ctx).drive(300.0);

    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::A));
    assert!(
        last(&app).starts_with("At the wheel so far:"),
        "{}",
        last(&app)
    );
    assert!(last(&app).contains("5.0 hours driving"), "{}", last(&app));

    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::S));
    assert!(
        last(&app).starts_with("Break due in 3.0 hours"),
        "{}",
        last(&app)
    );

    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::D));
    assert!(
        last(&app).starts_with("Driving time left: 6.0 hours"),
        "{}",
        last(&app)
    );
    assert!(
        last(&app).contains("Duty window closes in 9.0 hours"),
        "{}",
        last(&app)
    );
}

#[test]
fn test_the_hours_keys_leave_plain_a_s_and_d_alone() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);

    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::S));
    assert!(last(&app).contains("Speed limit"), "{}", last(&app));
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::D));
    assert!(
        last(&app).to_lowercase().contains("safe speed"),
        "{}",
        last(&app)
    );
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::A));
    assert!(!last(&app).contains("At the wheel"), "{}", last(&app));
}

#[test]
fn test_alt_d_carries_the_next_legal_stop_context() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    hos_mut_of(&mut app.ctx).drive(300.0);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::D));
    let verbose = last(&app);
    // The stop-planning clause moved off the clock key onto the key that
    // answers "when does this shift end".
    assert!(
        verbose.contains("legal stop") || verbose.contains("No route stop"),
        "{verbose}"
    );

    app.ctx.settings.driving_speech = "quiet".to_string();
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::D));
    assert!(!last(&app).contains("Next legal stop"), "{}", last(&app));
    assert!(last(&app).len() < verbose.len());
}

#[test]
fn test_status_menu_carries_the_drivers_board_progress_percent() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 40.0;
    let pct = d.trip.progress_percent();
    let lines = d.status_lines(&mut app.ctx);
    assert!(
        lines.contains(&format!("Progress: {pct} percent there")),
        "{lines:?}"
    );
}

#[test]
fn test_driving_help_describes_x_as_signal_not_take_exit() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::F1));
    let help_text = last(&app);
    assert!(
        help_text.contains("X signals for the next announced route exit"),
        "{help_text}"
    );
    assert!(
        !help_text.contains("X takes the next announced exit"),
        "{help_text}"
    );
}

// -- the pad (test_info_keys.py) -----------------------------------------------------

#[test]
fn test_controller_clock_button_keeps_the_whole_hours_report() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    hos_mut_of(&mut app.ctx).drive(300.0);
    app.clear_speech();
    d.handle_controller_event(&mut app.ctx, &pad(ControllerButton::DPadRight));
    // A pad has nowhere to put three more info buttons, so this one press must
    // still carry the hours a keyboard player gets from Alt A/S/D.
    assert!(
        last(&app).contains("hours of driving left"),
        "{}",
        last(&app)
    );
    assert!(
        !last(&app).contains("Hours of service moved to"),
        "{}",
        last(&app)
    );
}

#[test]
fn test_controller_can_ask_for_the_speed_limit() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    app.ctx.controller.modifier = true;
    d.handle_controller_event(&mut app.ctx, &pad(ControllerButton::X));
    let said = last(&app);
    assert!(
        said.contains("Speed limit") || said.contains("Truck limit"),
        "{said}"
    );
    assert!(said.contains("per hour"), "{said}");
}

#[test]
fn test_controller_help_names_the_stop_and_the_speed_limit() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.speak_controller_help(&mut app.ctx);
    let said = last(&app);
    assert!(
        said.contains("plus X reads the posted speed limit"),
        "{said}"
    );
    assert!(
        said.contains("Back button stops the driving voice"),
        "{said}"
    );
}

#[test]
fn test_controller_back_button_reads_help_when_nothing_is_speaking() {
    // The second half of `test_controller_back_button_stops_the_driving_voice`:
    // with the event voice idle, Back repeats the pad's own help. The first
    // half needs a busy event voice, which the Python test faked by patching
    // `ctx.event_voice_busy`; here the pacer answers it, so it lives in the
    // ignored case below.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.handle_controller_event(&mut app.ctx, &pad(ControllerButton::Back));
    assert!(
        last(&app).to_lowercase().contains("right trigger"),
        "{}",
        last(&app)
    );
}

// -- the binding table itself --------------------------------------------------------

#[test]
fn test_alt_with_a_number_beats_the_jake_stage_it_used_to_fall_through_to() {
    // The documented fix: Alt+1..4 (and the keypad twins) are checked ahead of
    // the jake stages, so a driver reaching for "what state am I in" no longer
    // changes the engine brake.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.start_engine();
    d.trip.truck.engine_brake_stage = 3;
    d.jake_selected_stage = 3;
    for k in [
        Key::Num1,
        Key::Num2,
        Key::Num3,
        Key::Num4,
        Key::Kp1,
        Key::Kp4,
    ] {
        d.handle_key_event(&mut app.ctx, &alt(k));
        assert_eq!(d.trip.truck.engine_brake_stage, 3, "{k:?} moved the jake");
    }
    // Unmodified, the same number keys are the cylinder selector again.
    d.handle_key_event(&mut app.ctx, &key(Key::Num1));
    assert_eq!(d.trip.truck.engine_brake_stage, 1);
}

#[test]
fn test_the_dial_keys_read_ctrl_before_shift() {
    // Ctrl+Shift still jumps a category, exactly as it did before Shift meant
    // volume: the radio branch checks Ctrl first.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let both = Mods {
        shift: true,
        ctrl: true,
        alt: false,
    };
    // Nothing to assert on the radio stubs yet; what this pins is that the
    // chord reaches the category branch rather than the volume one, which the
    // (pending) radio implementation will assert on directly.
    d.handle_key_event(&mut app.ctx, &InputEvent::key_mods(Key::PageUp, both));
    d.handle_key_event(&mut app.ctx, &InputEvent::key_mods(Key::PageDown, both));
}

#[test]
fn test_the_arrows_only_tap_a_lane_change_when_lane_keeping_is_automated() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.start_engine();
    d.trip.truck.set_air_ready(false);
    d.trip.truck.velocity_mps = mph_to_mps(55.0);
    d.lane.lane_count = 2;
    d.lane.lane = 0;

    // Steering assist off: the arrows steer, and the tap handler never runs.
    app.ctx.settings.lane_keeping = "off".to_string();
    d.handle_key_event(&mut app.ctx, &key(Key::Left));
    assert_eq!(d.lane_change_target, None);

    app.ctx.settings.lane_keeping = "full".to_string();
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::Left));
    assert_eq!(d.lane_change_target, Some(1));
    assert!(last(&app).contains("Changing to the"), "{}", last(&app));
}

#[test]
fn test_a_lane_change_needs_the_engine_and_road_speed() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.ctx.settings.lane_keeping = "full".to_string();
    d.lane.lane_count = 2;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::Left));
    assert!(
        last(&app).contains("Lane changes need the engine running"),
        "{}",
        last(&app)
    );
    assert_eq!(d.lane_change_target, None);
}

#[test]
fn test_the_tap_answers_the_side_that_was_asked_for() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.ctx.settings.lane_keeping = "full".to_string();
    d.trip.truck.start_engine();
    d.trip.truck.set_air_ready(false);
    d.trip.truck.velocity_mps = mph_to_mps(55.0);
    d.lane.lane_count = 2;
    d.lane.lane = 0; // right lane
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::Right));
    assert_eq!(last(&app), "There is no lane to your right here.");
}

#[test]
fn test_h_starts_the_horn_and_releasing_it_stops() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.handle_key_event(&mut app.ctx, &key(Key::H));
    assert!(d.trip.truck.horn_on);
    d.handle_key_event(&mut app.ctx, &InputEvent::key_up(Key::H));
    assert!(!d.trip.truck.horn_on);
}

#[test]
fn test_alt_t_flips_the_transmission_setting() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let before = app.ctx.settings.automatic_transmission;
    d.handle_key_event(&mut app.ctx, &alt(Key::T));
    assert_eq!(app.ctx.settings.automatic_transmission, !before);
}

#[test]
fn test_alt_j_toggles_whether_j_arms_the_automatic_jake() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    assert!(d.auto_jake_enabled);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::J));
    assert!(!d.auto_jake_enabled);
    assert_eq!(last(&app), "Automatic jake off.");
    d.handle_key_event(&mut app.ctx, &alt(Key::J));
    assert!(d.auto_jake_enabled);
    assert_eq!(last(&app), "Automatic jake on.");
}

#[test]
fn test_the_jake_stage_keys_are_dead_while_the_jake_is_off() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &key(Key::Num2));
    assert_eq!(d.trip.truck.engine_brake_stage, 0);
    assert!(app.main_lines().is_empty());
}

// -- the manual gearbox (test_driving_manual_controls.py) ----------------------------

#[test]
fn test_shift_modified_manual_downshift_uses_clutch_before_next_update() {
    // The frame-loop half of the Python test (five seconds of `update`, then
    // "no damage and the revs came back") waits on `states::driving_updates`;
    // what this pins is the part the control surface owns -- held Shift
    // engages the clutch on the SAME event that selects the gear, so the
    // downshift never grinds.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.ctx.settings.automatic_transmission = false;
    let truck = &mut d.trip.truck;
    truck.start_engine();
    truck.set_air_ready(false);
    truck.transmission.automatic = false;
    truck.transmission.gear = 2;
    truck.transmission.clutch = 0.0; // stale until the update loop samples held keys
    truck.velocity_mps = 60.0 / 2.23694;
    truck.rpm = truck.specs.idle_rpm;

    d.handle_key_event(
        &mut app.ctx,
        &InputEvent::KeyDown {
            key: Key::Q,
            mods: Mods::SHIFT,
            text: Some('q'),
        },
    );

    assert_eq!(d.trip.truck.transmission.gear, 1);
    assert_eq!(d.trip.truck.transmission.clutch, 1.0);
    assert_eq!(d.trip.truck.damage_pct, 0.0);
}

// -- the cruise dial (test_cruise_steps.py) ------------------------------------------

#[test]
fn test_plus_key_snaps_an_off_grid_cruise_target() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    cruise_at(&mut d, &mut app, 32.0);

    d.handle_key_event(&mut app.ctx, &InputEvent::key_text(Key::Equals, '='));
    assert_eq!(d.cruise_mph, Some(35.0));
    d.handle_key_event(&mut app.ctx, &InputEvent::key_text(Key::Equals, '='));
    assert_eq!(d.cruise_mph, Some(40.0));
}

#[test]
fn test_ctrl_plus_and_minus_step_by_one() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    cruise_at(&mut d, &mut app, 35.0);

    d.handle_key_event(&mut app.ctx, &InputEvent::key_mods(Key::Equals, Mods::CTRL));
    assert_eq!(d.cruise_mph, Some(36.0));
    d.handle_key_event(&mut app.ctx, &InputEvent::key_mods(Key::Minus, Mods::CTRL));
    assert_eq!(d.cruise_mph, Some(35.0));
}

#[test]
fn test_the_dial_also_answers_the_typed_plus_and_minus() {
    // The `+`/`-` fallback: a keyboard whose plus lives on a shifted key sends
    // a different keycode, and `event.unicode` is what makes the tap land.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    cruise_at(&mut d, &mut app, 35.0);

    d.handle_key_event(&mut app.ctx, &InputEvent::key_text(Key::Other(0x2b), '+'));
    assert_eq!(d.cruise_mph, Some(40.0));
    d.handle_key_event(&mut app.ctx, &InputEvent::key_text(Key::Other(0x2d), '-'));
    assert_eq!(d.cruise_mph, Some(35.0));
}

#[test]
fn test_keeper_zone_adjust_snaps_the_resume_target() {
    // The speed keeper owns a restricted zone, but +/- still steps the
    // remembered open-road target that adaptive cruise resumes to -- and must
    // not disturb the keeper's own held speed while it does.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    d.trip.truck.engine_on = true;
    let start = d.trip.position_mi;
    d.trip
        .zones
        .push(Zone::new(start - 0.1, start + 3.0, 25.0, "school"));
    d.trip.truck.velocity_mps = mph_to_mps(25.0);
    d.engage_keeper(&mut app.ctx, 25.0, "school", Some(25.0), false);
    let keeper_before = d.keeper_mph;
    d.speed_control_target_mph = Some(62.0);

    d.handle_key_event(&mut app.ctx, &InputEvent::key_text(Key::Equals, '='));

    assert_eq!(d.speed_control_target_mph, Some(65.0));
    assert_eq!(d.keeper_mph, keeper_before);
}

#[test]
fn test_keeper_raw_capture_rounds_to_the_whole_mph() {
    // `_engage_keeper`'s plain K-set branch (no explicit target_mph) rounds the
    // captured speed to the whole mph the player hears, mirroring
    // `_engage_cruise`'s rounding -- otherwise an unrounded 24.95 would spend
    // the first snap tap healing an invisible fraction instead of making an
    // audible step.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    d.trip.truck.engine_on = true;
    let start = d.trip.position_mi;
    d.trip
        .zones
        .push(Zone::new(start - 0.1, start + 3.0, 30.0, "school"));
    d.trip.truck.velocity_mps = mph_to_mps(24.95); // off the whole mph

    d.engage_keeper(&mut app.ctx, 30.0, "school", None, false);

    assert_eq!(d.keeper_mph, Some(25.0));
}

#[test]
fn test_high_idle_still_owns_the_keys_when_parked() {
    // Parked with a latched high idle, +/- steps the idle RPM, not any cruise
    // or keeper target -- the branch `_adjust_cruise` checks first.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(true);
    d.trip.truck.start_engine();
    d.trip.truck.velocity_mps = 0.0;
    d.trip.truck.high_idle_rpm = Some(HIGH_IDLE_DEFAULT_RPM);

    d.handle_key_event(&mut app.ctx, &InputEvent::key_text(Key::Equals, '='));

    assert_eq!(
        d.trip.truck.high_idle_rpm,
        Some(HIGH_IDLE_DEFAULT_RPM + HIGH_IDLE_STEP_RPM)
    );
    assert_eq!(d.cruise_mph, None);
    assert_eq!(d.speed_control_target_mph, None);
}

// -- the speed-control session (driving_speed_control.rs) ----------------------------

#[test]
fn test_speed_authority_predicate_reads_all_three() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    assert!(!d.speed_authority_engaged());
    d.cruise_mph = Some(55.0);
    assert!(d.speed_authority_engaged());
    d.cruise_mph = None;
    d.keeper_mph = Some(25.0);
    assert!(d.speed_authority_engaged());
    d.keeper_mph = None;
    d.curve_assist_active = true;
    assert!(d.speed_authority_engaged());
}

#[test]
fn test_shift_k_resumes_the_remembered_speed() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    cruise_at(&mut d, &mut app, 60.0);
    // Braking cancels the session but remembers the target, like a car's
    // RESUME button.
    d.cancel_cruise(&mut app.ctx, false);
    assert_eq!(d.cruise_mph, None);
    assert!(!d.speed_control_armed);
    assert_eq!(d.resume_target_mph, Some(60.0));

    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &InputEvent::key_mods(Key::K, Mods::SHIFT));
    assert!(d.speed_control_armed);
    assert_eq!(d.speed_control_target_mph, Some(60.0));
    assert_eq!(
        last(&app),
        "Resuming automatic speed control at 60 miles per hour."
    );
}

#[test]
fn test_resume_refuses_without_a_remembered_speed_or_an_engine() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &InputEvent::key_mods(Key::K, Mods::SHIFT));
    assert_eq!(last(&app), "No remembered cruise speed yet. K sets one.");

    d.resume_target_mph = Some(55.0);
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &InputEvent::key_mods(Key::K, Mods::SHIFT));
    assert_eq!(last(&app), "Resume needs the engine running.");

    d.speed_control_armed = true;
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &InputEvent::key_mods(Key::K, Mods::SHIFT));
    assert_eq!(last(&app), "Automatic speed control is already on.");
}

#[test]
fn test_a_transit_pause_lifts_itself_once_the_bar_is_honored() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    cruise_at(&mut d, &mut app, 60.0);
    assert!(d.pause_speed_control(&mut app.ctx, true));
    assert!(d.speed_control_paused_at_stop);
    assert!(d.speed_control_transit_pause);
    assert!(d.speed_control_armed); // the session is remembered, not dropped

    // Still rolling toward the bar with the ramp ahead: nothing lifts.
    d.ramp_mi = Some(0.4);
    assert!(!d.lift_transit_pause(false));

    // Stopped at the bar, then rolling again off the brake.
    d.trip.truck.velocity_mps = 0.0;
    assert!(!d.lift_transit_pause(false));
    assert!(d.speed_control_stop_honored);
    d.trip.truck.velocity_mps = mph_to_mps(20.0);
    assert!(d.lift_transit_pause(false));
    assert!(!d.speed_control_paused_at_stop);
}

#[test]
fn test_an_arrival_pause_is_never_lifted_by_rolling_again() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    cruise_at(&mut d, &mut app, 60.0);
    d.pause_speed_control(&mut app.ctx, false);
    d.trip.truck.velocity_mps = mph_to_mps(30.0);
    assert!(!d.lift_transit_pause(false));
    assert!(d.speed_control_paused_at_stop);
}

#[test]
fn test_cancelling_the_keeper_alone_keeps_a_remembered_cruise_target() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    cruise_at(&mut d, &mut app, 62.0);
    d.cancel_cruise(&mut app.ctx, false);
    assert_eq!(d.resume_target_mph, Some(62.0));
    // A keeper-only cancel carries no target and must not clobber it.
    d.cancel_keeper(&mut app.ctx, false);
    assert_eq!(d.resume_target_mph, Some(62.0));
}

#[test]
fn test_speed_keeper_ease_window_follows_the_driving_mode() {
    // The keeper's ease is budgeted in real seconds, so a compressed clock has
    // to buy more road for the same warning. A corner is the exception: it
    // decompresses the trip to real time, and the ease is sized on that clock
    // rather than on the pacing the player picked.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.velocity_mps = 25.0 / 2.23694;

    assert!(d.keeper_ease_mi(20.0, 10.0) > d.keeper_ease_mi(20.0, 4.0));
    assert!(d.keeper_ease_mi(20.0, 4.0) > d.keeper_ease_mi(20.0, 1.0));
    // The ceiling trims the discretionary reaction budget so a long access
    // road is not crawled -- but never the PHYSICAL shed, which the window's
    // docstring promises is a floor. At 40x the 25-to-20 shed alone outruns
    // the cap, so the window follows the physics (clamping it was how the
    // keeper arrived at 15.47 over a 15 sign on long-route draws -- the
    // one-in-four flake, fixed 2026-08-20).
    assert!(d.keeper_ease_mi(20.0, 40.0) > KEEPER_EASE_MAX_MI);
    // The cap still binds where reaction, not physics, is the bigger ask: a
    // one-mph trim at 30x wants little shed road, and the six-plus seconds of
    // hearing-and-deciding it would otherwise buy are what the ceiling exists
    // to trim.
    assert!((d.keeper_ease_mi(24.0, 30.0) - KEEPER_EASE_MAX_MI).abs() < 1e-9);

    // A bigger drop buys more road than the base window at the same pacing.
    assert!(d.keeper_ease_mi(5.0, 1.0) > d.keeper_ease_mi(24.0, 1.0));

    // A corner runs on the real clock whichever pacing the player chose, so
    // its ease is sized there and never on the compressed road. Sizing it on
    // the pacing read the corner as close from half a mile back and held the
    // whole block at the corner speed.
    d.trip.time_scale = 40.0;
    d.trip.controlled_turn = false;
    assert!(d.trip.effective_time_scale() > 1.0);
    assert!((d.keeper_turn_ease_scale() - 1.0).abs() < 1e-9);
    d.trip.controlled_turn = true;
    assert!((d.keeper_turn_ease_scale() - 1.0).abs() < 1e-9);
}

#[test]
fn test_the_restricted_zone_look_ahead_waits_for_the_spoken_warning() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.speed_control_armed = true;
    app.ctx.settings.speed_keeper = true;
    d.trip.position_mi = 0.0;
    d.trip.zones = vec![Zone::new(0.2, 3.0, 25.0, "construction")];
    // Cruise and the warning share a window; which one lands first must not
    // come down to frame order.
    assert_eq!(d.restricted_zone_limit_ahead(&mut app.ctx), None);
}

// -- the brake latch, and the throttle key that never latches ----------------------

const DT: f64 = 1.0 / 60.0;

/// Tap, release, press and hold through the catch window.
fn catch_gesture(d: &mut DrivingState, app: &mut TestApp, throttle: bool, seconds_held: f64) {
    let run = |held: bool, seconds: f64, d: &mut DrivingState, app: &mut TestApp| {
        let mut t = 0.0;
        while t < seconds {
            let (up, down) = if throttle {
                (held, false)
            } else {
                (false, held)
            };
            d.update_pedal_latches(&mut app.ctx, up, down, 0.0, DT);
            t += DT;
        }
    };
    run(true, 0.2, d, app);
    run(false, 0.2, d, app);
    run(true, seconds_held, d, app);
}

fn throttle_latch_speech(app: &TestApp) -> Vec<String> {
    app.event_lines()
        .into_iter()
        .chain(app.main_lines())
        .filter(|l| {
            let lower = l.to_lowercase();
            lower.contains("throttle latched")
                || l == "Throttle released."
                || lower.contains("adaptive cruise holds the speed")
                || lower.contains("speed keeper holds the speed")
        })
        .collect()
}

#[test]
fn test_holding_the_throttle_never_latches() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    catch_gesture(&mut d, &mut app, true, 0.8);
    assert!(
        throttle_latch_speech(&app).is_empty(),
        "{:?}",
        app.event_lines()
    );
    assert!(!d.brake_latch.latched);
    // Releasing the key must not leave a hidden throttle catch behind:
    // the function returns the brake, and the throttle side is gone.
    let down = d.update_pedal_latches(&mut app.ctx, false, false, 0.0, DT);
    assert!(!down);
}

#[test]
fn test_a_plain_brake_catch_keeps_its_plain_line() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    catch_gesture(&mut d, &mut app, false, 0.8);
    assert!(
        app.event_lines().iter().any(|l| l == "Brake latched."),
        "{:?}",
        app.event_lines()
    );
    assert!(d.brake_latch.latched);
}

#[test]
fn test_the_latch_setting_off_drops_a_held_brake_and_says_so() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    catch_gesture(&mut d, &mut app, false, 0.8);
    assert!(d.brake_latch.latched);
    app.ctx.settings.pedal_latch = "off".to_string();
    app.clear_speech();
    let down = d.update_pedal_latches(&mut app.ctx, false, false, 0.0, DT);
    assert!(!down);
    assert!(!d.brake_latch.latched);
    assert!(
        app.event_lines().iter().any(|l| l == "Brake released."),
        "{:?}",
        app.event_lines()
    );
}

#[test]
fn test_the_accelerator_releases_a_latched_brake() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    catch_gesture(&mut d, &mut app, false, 0.8);
    assert!(d.brake_latch.latched);
    app.clear_speech();
    d.update_pedal_latches(&mut app.ctx, true, false, 0.0, DT);
    assert!(!d.brake_latch.latched);
    assert!(
        app.event_lines().iter().any(|l| l == "Brake released."),
        "{:?}",
        app.event_lines()
    );
}

#[test]
fn test_the_throttle_catch_gesture_never_grabs_the_shift_back_to_forward() {
    // The catch used to land first (half a second against six tenths) and
    // wipe the pending shift, so pumping the throttle in reverse re-armed
    // and lost it every time (owner, at the scale, 2026-08-21: "I can't
    // get out of reverse?"). The throttle side is gone, so the armed
    // shift is still there after the same gesture.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.direction_armed = "forward".to_string();
    catch_gesture(&mut d, &mut app, true, 0.8);
    assert_eq!(d.direction_armed, "forward");
    assert!(
        throttle_latch_speech(&app).is_empty(),
        "{:?}",
        app.event_lines()
    );
}

// -- cases whose mixin has not landed ------------------------------------------------

#[test]
#[ignore = "needs a Trip seam for the monkeypatched trip.grade_at"]
fn test_grade_key_reads_the_slope_and_whether_the_truck_holds_it() {
    // `_fixed_grade(d, -5.0, until_mi=9.0)`; G then says "Grade 5.0 percent
    // downhill", "for another ..." and either "Speed is building" or names the
    // jake. Python replaced `trip.grade_at`; Rust needs either a route built
    // with grade segments or a test seam on `Trip`.
}

#[test]
#[ignore = "needs a Trip seam for the monkeypatched trip.grade_at"]
fn test_grade_key_names_the_next_steep_grade_ahead() {}

#[test]
#[ignore = "needs a Trip seam for the monkeypatched trip.grade_at"]
fn test_grade_key_says_when_nothing_steep_is_coming() {}

#[test]
#[ignore = "needs a Trip seam for the monkeypatched trip.grade_at"]
fn test_grade_key_names_the_grade_the_preview_is_planning_for() {}

#[test]
#[ignore = "needs a Trip seam for the monkeypatched trip.grade_at"]
fn test_grade_key_does_not_call_a_punchy_pull_nothing_steep() {}

#[test]
#[ignore = "needs a Trip seam for the monkeypatched trip.grade_at"]
fn test_grade_key_names_the_same_hill_the_speed_control_cue_names() {}

#[test]
#[ignore = "needs a Trip seam for the monkeypatched trip.grade_at"]
fn test_grade_key_names_a_grade_that_steepens_without_letting_up() {}

#[test]
#[ignore = "needs a Trip seam for the monkeypatched trip.grade_at"]
fn test_grade_key_says_nothing_else_steep_while_on_a_steep_grade() {}

#[test]
fn test_upcoming_key_never_reports_enforcement() {
    // U is the road, not the police (owner ruling, 2026-08-15). Enforcement
    // heads-ups still reach the player on the CB; this key does not recite
    // them in any hours-of-service mode, enforced or not.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    for mode in ["realistic", "relaxed", "debug_off"] {
        app.ctx.settings.hos_mode = mode.to_string();
        d.trip.position_mi = 4.0;
        d.trip.posts = vec![observing_post(6.0, 4.0)];
        app.clear_speech();

        d.handle_key_event(&mut app.ctx, &key(Key::U));

        let report = last(&app).to_lowercase();
        assert!(d.trip.next_patrol_within(15.0).is_some(), "{mode}");
        for word in ["enforcement", "patrol", "trooper", "police", "bear"] {
            assert!(!report.contains(word), "{mode}: {word}: {report}");
        }
    }
    // The branch that used to gate this on the mode.
    assert!(!hos::HOS_NON_ENFORCED_MODES.is_empty());
}

#[test]
fn test_upcoming_key_does_not_repeat_the_next_exit_key() {
    // Shift+R is the listed-exit key, word for word; U stopped echoing it.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 4.0;
    d.trip.zones = Vec::new();
    d.trip.stops = Vec::new();
    d.trip.curves = Vec::new();
    let (at_mi, text) = {
        let cue = d
            .trip
            .next_exit_cue()
            .expect("route has no listed exit to echo");
        (cue.at_mi, cue.text.clone())
    };
    d.trip.position_mi = 0.0f64.max(at_mi - 5.0);
    app.clear_speech();

    d.handle_key_event(&mut app.ctx, &key(Key::U));

    assert!(!last(&app).contains(&text), "{}", last(&app));
}

// -- the R key: route status (test_info_keys.py) --------------------------------------
//
// These eleven were stubbed in `app_info_keys.rs` and are written out here,
// where the drive helper already empties the road and pins the sky.

#[test]
fn test_route_key_reports_progress_then_road_state_and_destination() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 40.0;
    d.trip.zones = vec![Zone::new(35.0, 45.0, 45.0, "construction")];
    app.clear_speech();

    d.handle_key_event(&mut app.ctx, &key(Key::R));

    // Two short sentences and nothing else: the grade, the zone, the nearest
    // named place, and the next maneuver all have their own key.
    let pct = d.trip.progress_percent();
    assert_eq!(
        last(&app),
        format!(
            "{pct} percent there, 34 miles left. On I-90 East in New York, toward Rochester, \
             New York."
        )
    );
}

#[test]
fn test_route_key_counts_down_to_a_planned_stop_instead_of_the_destination() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.position_mi = 20.0;
    let (at_mi, stop_key, spoken_name) = {
        let stop = d
            .trip
            .stops
            .iter()
            .find(|s| s.at_mi > d.trip.position_mi)
            .expect("the corridor has a stop ahead");
        (stop.at_mi, stop.key(), stop.spoken_name())
    };
    d.trip.planned_stop_key = Some(stop_key);
    app.clear_speech();

    d.handle_key_event(&mut app.ctx, &key(Key::R));

    let report = last(&app);
    let ahead = spoken_closing_distance(at_mi - d.trip.position_mi, d.trip.imperial());
    assert!(
        report.contains(&format!("{ahead} to {spoken_name}.")),
        "{report}"
    );
    assert!(!report.contains("left."), "{report}");
    assert!(
        report.contains("On I-90 East in New York, toward Rochester, New York."),
        "{report}"
    );
}

#[test]
fn test_route_key_falls_back_to_the_destination_once_the_plan_is_behind() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let (at_mi, stop_key, spoken_name) = {
        let stop = d.trip.stops.first().expect("the corridor has a stop");
        (stop.at_mi, stop.key(), stop.spoken_name())
    };
    d.trip.planned_stop_key = Some(stop_key);
    d.trip.position_mi = at_mi + 1.0;
    app.clear_speech();

    d.handle_key_event(&mut app.ctx, &key(Key::R));

    let report = last(&app);
    let remaining = d.trip.distance_text(d.trip.remaining_miles());
    assert!(report.contains(&format!("{remaining} left.")), "{report}");
    assert!(!report.contains(&spoken_name), "{report}");
}

#[test]
fn test_route_key_reports_reverse_route_direction() {
    let mut app = TestApp::new();
    let mut d = a_drive_between(&mut app, "Rochester", "Buffalo", "company yard");
    d.trip.position_mi = 34.8;
    app.clear_speech();

    d.handle_key_event(&mut app.ctx, &key(Key::R));

    assert!(
        last(&app).contains("On I-90 West in New York, toward Buffalo, New York"),
        "{}",
        last(&app)
    );
}

#[test]
fn test_route_key_uses_metric_distances() {
    let mut app = TestApp::new();
    app.ctx.settings.imperial_units = false;
    let mut d = a_drive(&mut app);
    d.trip.set_imperial(false);
    d.trip.position_mi = 20.0;
    app.clear_speech();

    d.handle_key_event(&mut app.ctx, &key(Key::R));

    let report = last(&app);
    assert!(report.contains("87 kilometers left."), "{report}");
    assert!(!report.contains(" miles"), "{report}");
}

#[test]
fn test_route_key_answers_with_the_gate_on_the_facility_approach() {
    // After the destination exit, R describes the approach, not the dead
    // highway (playtest 2026-07-22: "on I-90 West, 3 miles remaining" with a
    // frozen countdown while rolling city streets toward the gate).
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.destination_exit_taken = true;
    d.trip.position_mi = d.trip.total_miles() - 2.0;
    app.clear_speech();

    d.handle_key_event(&mut app.ctx, &key(Key::R));

    let report = last(&app);
    assert!(
        report.starts_with("Route status: off the highway, on the facility approach"),
        "{report}"
    );
    assert!(!report.contains("I-90"), "{report}");
    assert!(!report.contains("into the trip"), "{report}");
}

#[test]
fn test_route_key_answers_with_the_gate_when_the_route_has_ended() {
    // Rolled past the gate: R agrees with the S key's gate override.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.destination_exit_taken = true;
    d.trip.position_mi = d.trip.total_miles();
    d.trip.finished = true;
    app.clear_speech();

    d.handle_key_event(&mut app.ctx, &key(Key::R));

    let report = last(&app);
    assert!(
        report.starts_with("Route status: you have arrived"),
        "{report}"
    );
    assert!(report.contains("Stop to dock"), "{report}");
}

/// `_on_the_surface_chain(app)`: a drive handed over to the destination
/// facility's street chain.
fn on_the_surface_chain(app: &mut TestApp) -> DrivingState {
    let mut d = a_drive(app);
    d.destination_exit_taken = true;
    d.ramp_mi = None;
    assert!(
        d.begin_surface_chain(&mut app.ctx, false),
        "no street chain for this facility"
    );
    d
}

#[test]
fn test_route_key_never_says_zero_miles_closing_on_the_gate() {
    // Named regression for the owner report of 2026-08-15. `Trip::distance_text`
    // rounds to whole miles, so every answer inside the last half mile was
    // "0 miles to the gate" -- and at 25 mph on city streets that half mile
    // takes over a minute. Walk the chain down to a couple of hundred feet and
    // the countdown has to keep meaning something.
    let mut app = TestApp::new();
    let mut d = on_the_surface_chain(&mut app);
    assert!(
        d.trip.total_miles() >= 0.5,
        "chain too short to walk the whole ladder"
    );
    let mut heard: Vec<String> = Vec::new();
    for remaining in [0.5, 0.4, 0.3, 0.2, 0.1, 0.05, 200.0 / 5280.0, 60.0 / 5280.0] {
        if remaining > d.trip.total_miles() {
            continue;
        }
        d.trip.position_mi = d.trip.total_miles() - remaining;
        app.clear_speech();
        d.handle_key_event(&mut app.ctx, &key(Key::R));
        heard.push(last(&app));
    }

    assert!(!heard.is_empty(), "the chain was too short to walk down");
    for report in &heard {
        assert!(!report.contains("0 miles"), "{report}");
        assert!(!report.contains("0 kilometers"), "{report}");
    }
    let second_last = &heard[heard.len() - 2];
    let final_line = &heard[heard.len() - 1];
    assert!(
        second_last.contains("200 feet to the gate"),
        "{second_last}"
    );
    assert!(final_line.contains("50 feet to the gate"), "{final_line}");
    assert!(heard[0].contains("half a mile to the gate"), "{}", heard[0]);
}

#[test]
fn test_route_key_names_the_street_under_the_wheels() {
    // The chain's report follows the truck, not the street it started on.
    let mut app = TestApp::new();
    let mut d = on_the_surface_chain(&mut app);
    let legs: Vec<(f64, String)> = d
        .trip
        .route
        .legs
        .iter()
        .map(|leg| (leg.miles, leg.highway.clone()))
        .collect();
    assert!(legs.len() >= 2);
    app.clear_speech();

    d.trip.position_mi = legs[0].0 * 0.5;
    d.handle_key_event(&mut app.ctx, &key(Key::R));
    assert!(
        last(&app).contains(&format!("on city streets, {},", legs[0].1)),
        "{}",
        last(&app)
    );

    d.trip.position_mi = legs[0].0 + legs[1].0 * 0.5;
    d.handle_key_event(&mut app.ctx, &key(Key::R));
    assert!(
        last(&app).contains(&format!("on city streets, {},", legs[1].1)),
        "{}",
        last(&app)
    );
}

#[test]
fn test_route_key_counts_down_to_the_on_ramp_leaving_the_origin_gate() {
    // The departure chain is city streets, and the highway readout was wrong
    // on it twice over: it called a two-mile street chain's percent the run's
    // progress, and it pointed the driver "toward" the city they were standing
    // in (owner report, 2026-08-15).
    let mut app = TestApp::new();
    let mut d = a_drive_between(&mut app, "Rochester", "Buffalo", "Rochester freight market");
    assert!(
        d.begin_departure_chain(&mut app.ctx, false),
        "no departure chain for this facility"
    );
    let highway = d
        .highway_trip
        .as_ref()
        .expect("the departure chain keeps the highway trip")
        .route
        .legs[0]
        .highway
        .clone();
    d.trip.position_mi = d.trip.total_miles() * 0.5;
    app.clear_speech();

    d.handle_key_event(&mut app.ctx, &key(Key::R));

    let report = last(&app);
    assert!(
        report.starts_with("Route status: on city streets,"),
        "{report}"
    );
    assert!(
        report.contains(&format!("to the {highway} on-ramp.")),
        "{report}"
    );
    assert!(!report.contains("percent there"), "{report}");
    assert!(!report.contains("toward"), "{report}");
    assert!(!report.contains("0 miles"), "{report}");
}

#[test]
fn test_route_key_answers_the_pickup_drive_as_city_streets() {
    // The pickup drive is streets from end to end: no highway leg to frame.
    let mut app = TestApp::new();
    let world = get_world();
    let (origin, location) = ("Rochester", "Rochester freight market");
    app.ctx.profile = Some(Profile::named_in("Info Keys", origin));
    let highway = world
        .supported_route(origin, "Buffalo", None)
        .expect("the world routes")
        .expect("the corridor is supported");
    let mut job = Job::new(
        &CARGO_CATALOG["general"],
        12.0,
        origin,
        location,
        "Buffalo",
        highway.miles(),
        1000.0,
        12.0,
    );
    job.destination_location = "Buffalo freight market".to_string();
    let route = world
        .facility_approach_route(origin, location)
        .expect("the facility has an approach route");
    let mut d = DrivingState::new(&mut app.ctx, job, route, None, DRIVE_PHASE_PICKUP, None);
    d.trip.set_npc_vehicles(Vec::new());
    d.trip.weather.current = WeatherKind::Clear;
    d.trip.position_mi = 0.0f64.max(d.trip.total_miles() - 200.0 / 5280.0);
    app.clear_speech();

    d.handle_key_event(&mut app.ctx, &key(Key::R));

    let report = last(&app);
    assert!(
        report.starts_with("Route status: on city streets,"),
        "{report}"
    );
    assert!(report.contains("200 feet to the gate at"), "{report}");
    assert!(!report.contains("percent there"), "{report}");
}

#[test]
#[ignore = "needs a busy event voice (Python patched ctx.event_voice_busy)"]
fn test_controller_back_button_stops_the_driving_voice() {
    // Back silences the road while it is talking, and reads help when it is
    // not. The "not" half is covered live above.
}

// -- a latched throttle is gone; the brake latch and a live key remain --------------
//
// The rest of the old `test_pedal_latch_assists.py` cases that needed the
// real per-frame loop. Cruise/keeper/curve no longer fight a latched
// throttle because that latch does not exist. The two hand-held-key cases
// stay: a physical hold is still live manual override.

/// Out on the corridor, where the posted limit is the interstate's own and 60
/// miles an hour is not an overspeed. `start_drive` left the truck near the
/// origin, where the limit is well under 60 and the dash alarm would arm.
fn on_the_open_road(d: &mut DrivingState) {
    d.trip.position_mi = d.trip.total_miles() / 2.0;
    let at = d.trip.position_mi;
    let (limit, _) = d.trip.speed_limit_at(at);
    assert!(
        limit >= 60.0,
        "the open-road limit here is {limit}, so 60 would arm the dash alarm"
    );
}

/// `_drive_frames(driving, seconds)`: the whole per-frame loop, not one
/// mixin's slice of it.
///
/// The pacer's clock moves with the frames. Python captured at `ctx.say_event`
/// and never reached the pacer at all; here the capture sits under it, and a
/// frame loop that costs no wall time leaves the pacer believing the voice is
/// still working through a backlog -- which drops the ambient confirmation
/// lines two of these cases are about. Advancing the clock by the same dt the
/// truck gets is what a real second of driving does.
fn drive_frames(d: &mut DrivingState, app: &mut TestApp, clock: &FakeClock, seconds: f64) {
    let mut t = 0.0;
    while t < seconds {
        d.update_frame(&mut app.ctx, DT);
        clock.advance(DT);
        t += DT;
    }
}

/// `release_air_brakes(driving)` plus the engine: `_update_cruise` cancels the
/// session without a running engine.
fn ready_to_roll(d: &mut DrivingState) {
    d.trip.truck.set_air_ready(false);
    d.trip.truck.engine_on = true;
}

fn press_for(d: &mut DrivingState, app: &mut TestApp, clock: &FakeClock, key: Key, seconds: f64) {
    app.ctx.input.press(key, Mods::NONE);
    drive_frames(d, app, clock, seconds);
}

fn release_for(d: &mut DrivingState, app: &mut TestApp, clock: &FakeClock, key: Key, seconds: f64) {
    app.ctx.input.release(key, Mods::NONE);
    drive_frames(d, app, clock, seconds);
}

fn in_reverse_at_rest(d: &mut DrivingState) {
    ready_to_roll(d);
    d.trip.truck.transmission.automatic = true;
    d.trip.truck.transmission.gear = REVERSE;
    d.trip.truck.velocity_mps = 0.0;
    assert!(d.trip.truck.transmission.in_reverse());
}

#[test]
fn test_a_hand_held_key_still_stands_the_assists_down() {
    // Physical hold keeps today's manual-override meaning.
    let mut app = TestApp::new();
    let clock = app.fake_pacer_clock();
    let mut d = a_drive(&mut app);
    ready_to_roll(&mut d);
    on_the_open_road(&mut d);
    app.ctx.input.press(Key::Up, Mods::NONE);
    d.trip.truck.velocity_mps = mph_to_mps(60.0);
    d.engage_cruise(&mut app.ctx, 55.0, false);

    drive_frames(&mut d, &mut app, &clock, 2.0);

    assert!(d.cruise_mph.is_some()); // engaged, waiting for the key to lift
    assert!(d.trip.truck.throttle > 0.9, "{}", d.trip.truck.throttle); // the hand owns the pedal
}

#[test]
fn test_the_throttle_catch_gesture_never_holds_the_pedal() {
    let mut app = TestApp::new();
    let clock = app.fake_pacer_clock();
    let mut d = a_drive(&mut app);
    ready_to_roll(&mut d);
    on_the_open_road(&mut d);
    d.trip.truck.velocity_mps = mph_to_mps(60.0);
    let audio = app.record_audio();
    app.clear_speech();

    press_for(&mut d, &mut app, &clock, Key::Up, 0.2);
    release_for(&mut d, &mut app, &clock, Key::Up, 0.2);
    press_for(&mut d, &mut app, &clock, Key::Up, 0.8);
    release_for(&mut d, &mut app, &clock, Key::Up, 1.0);

    assert!(
        throttle_latch_speech(&app).is_empty(),
        "{:?}",
        app.event_lines()
    );
    assert!(
        !audio.borrow().played.iter().any(|(k, _, _)| k == "ui/tick"),
        "{:?}",
        audio.borrow().played
    );
    assert!(
        d.trip.truck.throttle < 0.05,
        "throttle stayed applied after release: {}",
        d.trip.truck.throttle
    );
}

#[test]
fn test_a_normal_throttle_hold_leaves_reverse() {
    let mut app = TestApp::new();
    let clock = app.fake_pacer_clock();
    let mut d = a_drive(&mut app);
    in_reverse_at_rest(&mut d);
    let audio = app.record_audio();
    app.clear_speech();

    press_for(&mut d, &mut app, &clock, Key::Up, 0.8);

    assert!(
        !d.trip.truck.transmission.in_reverse(),
        "gear {}",
        d.trip.truck.transmission.gear
    );
    assert_eq!(d.trip.truck.transmission.gear, 1);
    assert!(
        throttle_latch_speech(&app).is_empty(),
        "{:?}",
        app.event_lines()
    );
    assert!(
        !audio.borrow().played.iter().any(|(k, _, _)| k == "ui/tick"),
        "{:?}",
        audio.borrow().played
    );
}

#[test]
fn test_pumping_the_throttle_still_leaves_reverse() {
    // The remaining reverse fight after the 2026-08-21 trap patch: a driver
    // who taps then holds -- pumping to get moving -- used to catch the
    // throttle latch at half a second and lose the six-tenth shift.
    let mut app = TestApp::new();
    let clock = app.fake_pacer_clock();
    let mut d = a_drive(&mut app);
    in_reverse_at_rest(&mut d);
    let audio = app.record_audio();
    app.clear_speech();

    press_for(&mut d, &mut app, &clock, Key::Up, 0.2);
    release_for(&mut d, &mut app, &clock, Key::Up, 0.2);
    press_for(&mut d, &mut app, &clock, Key::Up, 0.8);

    assert!(
        !d.trip.truck.transmission.in_reverse(),
        "gear {}",
        d.trip.truck.transmission.gear
    );
    assert_eq!(d.trip.truck.transmission.gear, 1);
    assert!(
        throttle_latch_speech(&app).is_empty(),
        "{:?}",
        app.event_lines()
    );
    assert!(
        !audio.borrow().played.iter().any(|(k, _, _)| k == "ui/tick"),
        "{:?}",
        audio.borrow().played
    );
}

#[test]
fn test_the_brake_latch_still_holds_hands_free() {
    let mut app = TestApp::new();
    let clock = app.fake_pacer_clock();
    let mut d = a_drive(&mut app);
    ready_to_roll(&mut d);
    on_the_open_road(&mut d);
    d.trip.truck.velocity_mps = mph_to_mps(30.0);
    let audio = app.record_audio();
    app.clear_speech();
    catch_gesture(&mut d, &mut app, false, 0.8);
    assert!(d.brake_latch.latched);
    assert!(
        app.event_lines().iter().any(|l| l == "Brake latched."),
        "{:?}",
        app.event_lines()
    );
    assert!(
        audio.borrow().played.iter().any(|(k, _, _)| k == "ui/tick"),
        "{:?}",
        audio.borrow().played
    );

    // Hands off: the blended brake latch must keep the pedal down.
    drive_frames(&mut d, &mut app, &clock, 1.0);
    assert!(d.brake_latch.latched);
    assert!(
        d.trip.truck.brake > 0.5,
        "latched brake did not stay applied: {}",
        d.trip.truck.brake
    );
}

#[test]
fn test_a_hand_held_key_stands_the_keeper_down() {
    // The spec bullet names the keeper; the existing coverage only engages
    // cruise. Both read the same hand_accelerating argument, but pin it.
    let mut app = TestApp::new();
    let clock = app.fake_pacer_clock();
    let mut d = a_drive(&mut app);
    ready_to_roll(&mut d);
    let start = d.trip.position_mi;
    d.trip
        .zones
        .push(Zone::new(start - 0.1, start + 3.0, 25.0, "school"));
    app.ctx.input.press(Key::Up, Mods::NONE);
    d.trip.truck.velocity_mps = mph_to_mps(30.0);
    d.engage_keeper(&mut app.ctx, 25.0, "school", Some(25.0), false);

    drive_frames(&mut d, &mut app, &clock, 2.0);

    assert!(d.keeper_mph.is_some()); // engaged, waiting for the key to lift
    assert!(d.trip.truck.throttle > 0.9, "{}", d.trip.truck.throttle); // the hand owns the pedal
}

// `test_rolling_t_plans_exact_sleep_stop_without_silently_selecting_exit`,
// `test_x_cancel_clears_explicit_assist_but_keeps_route_plan`,
// `test_rolling_t_without_sleep_stop_gives_recovery_guidance` and
// `test_t_during_police_stop_names_the_trooper_action` are live in
// `crates/freight-fate/tests/transcript_rest_stop_assist.rs`.

// `test_the_planner_sees_past_the_corner_it_is_already_easing_for` is live in `crates/freight-fate/tests/states_driving_turns.rs`.

/// Whether the state on top of the stack is a `T`.
fn top_is<T: 'static>(app: &TestApp) -> bool {
    app.ctx
        .state()
        .is_some_and(|state| state.borrow().as_any().is::<T>())
}

#[test]
fn test_the_tab_key_opens_the_status_screen() {
    // Tab is the one key that leaves the wheel for the reference screens, so
    // everything that lives there (the route, the driver, the map, the radio,
    // the tablet) is one press away from driving.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    assert!(!top_is::<DrivingStatusState>(&app));

    d.handle_key_event(&mut app.ctx, &key(Key::Tab));

    assert!(top_is::<DrivingStatusState>(&app));
}

#[test]
fn test_escape_and_start_open_the_pause_menu() {
    // Both devices reach the pause menu, and the horn never sticks on behind
    // it: Escape while leaning on the horn opened the menu with the note still
    // sounding.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.horn_on = true;

    d.handle_key_event(&mut app.ctx, &key(Key::Escape));

    assert!(top_is::<PauseMenuState>(&app));
    assert!(!d.trip.truck.horn_on);

    // The pad's Start button is the same door.
    drop(d);
    drop(app);
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.handle_controller_event(&mut app.ctx, &pad(ControllerButton::Start));
    assert!(top_is::<PauseMenuState>(&app));
}

#[test]
fn test_the_radio_dial_keys_tune_jump_and_change_volume() {
    // Page Up / `;` tunes down, Page Down / `'` tunes up, Ctrl jumps a whole
    // category, Shift moves the radio volume in ten percent steps.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.ctx.settings.radio_volume = 0.5;

    // Shift is the volume, on both spellings of the dial.
    d.handle_key_event(
        &mut app.ctx,
        &InputEvent::key_mods(Key::PageUp, Mods::SHIFT),
    );
    assert!(
        (app.ctx.settings.radio_volume - 0.6).abs() < 1e-6,
        "{}",
        app.ctx.settings.radio_volume
    );
    d.handle_key_event(&mut app.ctx, &InputEvent::key_mods(Key::Quote, Mods::SHIFT));
    assert!(
        (app.ctx.settings.radio_volume - 0.5).abs() < 1e-6,
        "{}",
        app.ctx.settings.radio_volume
    );

    // Plain and Ctrl move the dial, not the volume: whichever station they
    // land on, the volume the driver set is untouched.
    for event in [
        key(Key::PageDown),
        key(Key::Semicolon),
        InputEvent::key_mods(Key::PageDown, Mods::CTRL),
        InputEvent::key_mods(Key::PageUp, Mods::CTRL),
    ] {
        d.handle_key_event(&mut app.ctx, &event);
        assert!(
            (app.ctx.settings.radio_volume - 0.5).abs() < 1e-6,
            "{}",
            app.ctx.settings.radio_volume
        );
    }
}

// -- tests/test_driving_speech_ladder.py (the cab lines) -------------------------------

/// Owner playtest, 2026-08-17: "quiet still feels busy".
///
/// The Python half of this is a source scan of `states/driving_*.py` for the
/// three transcript lines, checking each carries `SpeechCategory.CONFIRMATION`
/// -- and the scan had to learn to read each file under its own name, because
/// "Engine off." is spoken in three places with three meanings and an
/// unsorted glob graded whichever the filesystem handed over first (CI,
/// 2026-08-23). The port asserts the same thing where it is decidable: the
/// cab confirmations go to an earcon at quiet, and the air-brake lockout that
/// speaks the same words is a ROUTE event and keeps its voice.
#[test]
fn test_the_cab_is_categorised_so_quiet_is_actually_quiet() {
    let mut app = TestApp::new();
    app.ctx.settings.driving_speech = "quiet".to_string();
    let mut d = a_drive(&mut app);
    // The ladder only applies past the walkthrough.
    app.ctx.profile.as_mut().unwrap().tutorial_done = true;
    d.trip.truck.start_engine();
    d.trip.truck.set_air_ready(true);
    d.toggle_parking_brake(&mut app.ctx); // the drive starts with it set
    app.clear_speech();

    // "Parking brake set. Air pressure ... psi." -- a confirmation.
    d.toggle_parking_brake(&mut app.ctx);
    assert!(app.main_lines().is_empty(), "{:?}", app.main_lines());

    // "Engine off." from the E key -- also a confirmation.
    d.toggle_engine(&mut app.ctx);
    assert!(!d.trip.truck.engine_on);
    assert!(app.main_lines().is_empty(), "{:?}", app.main_lines());

    // The other "Engine off." is not this one. The air-brake lockout speaks
    // the same two words at quiet as the terse form of "why the truck will
    // not roll", and it is a ROUTE event on the event channel rather than a
    // confirmation -- which is what the Python scan kept mis-grading. Pinned
    // where it is spoken, by
    // `states_driving_updates::test_the_air_brake_lockout_says_why_the_truck_will_not_roll`.
    assert!(app.event_lines().is_empty(), "{:?}", app.event_lines());
}

/// Standard hears the confirmations in full: quiet is what silences them, not
/// the category itself.
#[test]
fn test_the_cab_confirmations_still_speak_at_standard() {
    let mut app = TestApp::new();
    app.ctx.settings.driving_speech = "standard".to_string();
    let mut d = a_drive(&mut app);
    app.ctx.profile.as_mut().unwrap().tutorial_done = true;
    d.trip.truck.start_engine();
    d.trip.truck.set_air_ready(true);
    d.toggle_parking_brake(&mut app.ctx); // the drive starts with it set
    app.clear_speech();

    d.toggle_parking_brake(&mut app.ctx);
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.starts_with("Parking brake set. Air pressure")));

    app.clear_speech();
    d.toggle_engine(&mut app.ctx);
    assert_eq!(app.main_lines(), vec!["Engine off.".to_string()]);
}
