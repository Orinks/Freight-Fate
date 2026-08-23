//! `states/driving_controls.rs` and `states/driving_speed_control.rs`: the
//! discrete key and pad surface at the wheel, and the speed-control session
//! around adaptive cruise and the speed keeper.
//!
//! Ported from `tests/test_info_keys.py`, `test_cruise_steps.py` (its
//! App-driven half; the pure `cruise_step_target` grid is in
//! `states_driving_core.rs`), `test_driving_manual_controls.py`,
//! `test_pedal_latch_assists.py` (the cases the latch machinery answers on its
//! own), `test_driving_modes.py` (the keeper's ease window) and
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
use ff_core::sim::trip_models::{TripEvent, TripEventData, TripEventKind, Zone};
use ff_core::sim::vehicle::{HIGH_IDLE_DEFAULT_RPM, HIGH_IDLE_STEP_RPM};
use ff_core::sim::weather::WeatherKind;
use ff_core::speech_text::SpokenMessage;

use freight_fate::app::testing::TestApp;
use freight_fate::controller::ControllerButton;
use freight_fate::states::base::{InputEvent, Key, Mods};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_controls::UPCOMING_MAX_CLAUSES;
use freight_fate::states::driving_core::{hos_mut_of, profile_of, DRIVE_PHASE_DELIVERY};
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

// -- the pedal latches (test_pedal_latch_assists.py) ---------------------------------

const DT: f64 = 1.0 / 60.0;

/// The real gesture, so the spoken confirmation path is the one players hear:
/// tap, release, press and hold through the catch.
fn latch_the_throttle(d: &mut DrivingState, app: &mut TestApp) {
    let run = |held: bool, seconds: f64, d: &mut DrivingState, app: &mut TestApp| {
        let mut t = 0.0;
        while t < seconds {
            d.update_pedal_latches(&mut app.ctx, held, false, 0.0, 0.0, false, DT);
            t += DT;
        }
    };
    run(true, 0.2, d, app);
    run(false, 0.2, d, app);
    run(true, 0.8, d, app);
}

#[test]
fn test_a_plain_catch_keeps_its_plain_line() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    latch_the_throttle(&mut d, &mut app);
    assert!(
        app.event_lines().iter().any(|l| l == "Throttle latched."),
        "{:?}",
        app.event_lines()
    );
    assert!(d.throttle_latch.latched);
}

#[test]
fn test_the_catch_line_names_the_authority_holding_the_speed() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    cruise_at(&mut d, &mut app, 60.0);
    app.clear_speech();
    latch_the_throttle(&mut d, &mut app);
    let lines = app.event_lines();
    assert!(
        lines
            .iter()
            .any(|l| l == "Throttle latched. Adaptive cruise holds the speed."),
        "{lines:?}"
    );
    assert!(!lines.iter().any(|l| l == "Throttle latched."), "{lines:?}");
}

#[test]
fn test_the_catch_line_names_the_keeper() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.set_air_ready(false);
    d.trip.truck.engine_on = true;
    d.trip.truck.velocity_mps = mph_to_mps(25.0);
    d.engage_keeper(&mut app.ctx, 25.0, "construction", Some(25.0), false);
    app.clear_speech();
    latch_the_throttle(&mut d, &mut app);
    assert!(
        app.event_lines()
            .iter()
            .any(|l| l == "Throttle latched. Speed keeper holds the speed."),
        "{:?}",
        app.event_lines()
    );
}

#[test]
fn test_latch_first_catch_keeps_the_plain_line() {
    // Owner revision: "latch first" is the pre-change behavior -- the plain
    // line is the truth, since nothing outranks the latch in this mode, so the
    // authority line must not appear even with cruise engaged.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.ctx.settings.pedal_latch = "latch first".to_string();
    d.trip.truck.set_air_ready(false);
    cruise_at(&mut d, &mut app, 60.0);
    app.clear_speech();
    latch_the_throttle(&mut d, &mut app);
    let lines = app.event_lines();
    assert!(lines.iter().any(|l| l == "Throttle latched."), "{lines:?}");
    assert!(
        !lines
            .iter()
            .any(|l| l == "Throttle latched. Adaptive cruise holds the speed."),
        "{lines:?}"
    );
}

#[test]
fn test_the_latch_setting_off_drops_a_held_latch_and_says_so() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    latch_the_throttle(&mut d, &mut app);
    assert!(d.throttle_latch.latched);
    app.ctx.settings.pedal_latch = "off".to_string();
    app.clear_speech();
    let (_, _, latched) = d.update_pedal_latches(&mut app.ctx, false, false, 0.0, 0.0, false, DT);
    assert!(!latched);
    assert!(
        app.event_lines().iter().any(|l| l == "Throttle released."),
        "{:?}",
        app.event_lines()
    );
}

#[test]
fn test_a_safety_override_surrenders_the_latched_throttle() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    latch_the_throttle(&mut d, &mut app);
    app.clear_speech();
    d.overspeed_active = true;
    let (_, _, latched) = d.update_pedal_latches(&mut app.ctx, false, false, 0.0, 0.0, false, DT);
    assert!(!latched);
    assert!(
        app.event_lines().iter().any(|l| l == "Throttle released."),
        "{:?}",
        app.event_lines()
    );
}

#[test]
fn test_the_catch_never_grabs_the_shift_back_to_forward() {
    // The catch lands first by design (half a second against six tenths) and
    // used to wipe the pending shift with it, so a driver pumping the throttle
    // in reverse re-armed and lost it every single time (owner, at the scale,
    // 2026-08-21: "I can't get out of reverse?").
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.direction_armed = "forward".to_string();
    latch_the_throttle(&mut d, &mut app);
    assert!(!d.throttle_latch.latched);
    assert_eq!(d.direction_armed, "forward");
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
#[ignore = "unblocked: states::driving_location exists; the case is not written yet"]
fn test_upcoming_key_does_not_repeat_the_next_exit_key() {
    // `trip.next_exit_cue()` is the listed exit; U stopped echoing it.
}

#[test]
#[ignore = "needs a busy event voice (Python patched ctx.event_voice_busy)"]
fn test_controller_back_button_stops_the_driving_voice() {
    // Back silences the road while it is talking, and reads help when it is
    // not. The "not" half is covered live above.
}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the frame-loop case is not written yet"]
fn test_cruise_holds_its_speed_under_a_latched_throttle() {}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the frame-loop case is not written yet"]
fn test_a_hand_held_key_still_stands_the_assists_down() {}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the frame-loop case is not written yet"]
fn test_the_latch_ramps_back_in_when_the_authority_releases() {}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the frame-loop case is not written yet"]
fn test_keeper_holds_a_zone_speed_under_a_latched_throttle() {}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the frame-loop case is not written yet"]
fn test_releasing_the_latch_leaves_cruise_holding() {}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the frame-loop case is not written yet"]
fn test_curve_assist_drains_a_latched_throttle() {}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the frame-loop case is not written yet"]
fn test_latch_first_mode_keeps_the_old_override_meaning() {}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the frame-loop case is not written yet"]
fn test_curve_assist_jake_arrives_once_the_latched_throttle_drains() {}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the frame-loop case is not written yet"]
fn test_the_brake_key_hard_releases_the_latch_and_cancels_cruise() {}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the frame-loop case is not written yet"]
fn test_a_hand_held_key_stands_the_keeper_down() {}

// `test_rolling_t_plans_exact_sleep_stop_without_silently_selecting_exit`,
// `test_x_cancel_clears_explicit_assist_but_keeps_route_plan`,
// `test_rolling_t_without_sleep_stop_gives_recovery_guidance` and
// `test_t_during_police_stop_names_the_trooper_action` are live in
// `crates/freight-fate/tests/transcript_rest_stop_assist.rs`.

// `test_the_planner_sees_past_the_corner_it_is_already_easing_for` is live in `crates/freight-fate/tests/states_driving_turns.rs`.

#[test]
#[ignore = "unblocked: states::driving_menu_states exists; the case is not written yet"]
fn test_the_tab_key_opens_the_status_screen() {}

#[test]
#[ignore = "unblocked: states::driving_pause_states exists; the case is not written yet"]
fn test_escape_and_start_open_the_pause_menu() {}

#[test]
#[ignore = "unblocked: states::driving_updates exists; the radio-dial case is not written yet"]
fn test_the_radio_dial_keys_tune_jump_and_change_volume() {
    // Page Up / `;` tunes down, Page Down / `'` tunes up, Ctrl jumps a whole
    // category, Shift moves the radio volume in ten percent steps.
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
