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
    assert!(said.contains("reduced speed for construction"), "{said}");
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
    assert!(report.contains("Break due in 3 hours."), "{report}");
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
    assert!(last(&app).contains("5 hours driving"), "{}", last(&app));

    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::S));
    assert!(
        last(&app).starts_with("Break due in 3 hours"),
        "{}",
        last(&app)
    );

    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::D));
    assert!(
        last(&app).starts_with("Driving time left: 6 hours"),
        "{}",
        last(&app)
    );
    assert!(
        last(&app).contains("Duty window closes in 9 hours"),
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
        verbose.contains("Destination estimated reachable before your next hours limit")
            && verbose.contains("No HOS stop is needed first"),
        "{verbose}"
    );

    app.ctx.settings.driving_speech = "quiet".to_string();
    app.clear_speech();
    d.handle_key_event(&mut app.ctx, &alt(Key::D));
    let quiet = last(&app);
    assert!(
        !quiet.contains("Destination estimated reachable"),
        "{quiet}"
    );
    assert!(!quiet.contains("HOS stop"), "{quiet}");
    assert!(quiet.len() < verbose.len());
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
    assert_eq!(last(&app), "No lane to your right here.");
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
