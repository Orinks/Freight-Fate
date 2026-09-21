use super::*;

#[test]
fn quiet_speaks_a_real_lane_opening_but_urgent_only_does_not_buffer_it() {
    for mode in ["quiet", "urgent_only"] {
        let mut app = TestApp::new();
        let mut drive = a_gap_drive(&mut app);
        app.ctx.settings.driving_speech = mode.to_string();
        app.ctx.profile.as_mut().unwrap().tutorial_done = true;
        rolling(&mut drive, 60.0);
        app.clear_speech();
        let before = app.ctx.message_log.messages.len();
        pass_a_box_truck(&mut drive, &mut app);
        // The lane must remain blocked while another vehicle is alongside.
        clear_the_box_truck(&mut drive);
        drive.trip.traffic_manager.vehicles.push(npc(
            drive.trip.position_mi + 0.1,
            0,
            45.0,
            "car",
            "second",
        ));
        drive.update_lane_gap(&mut app.ctx, 0.1);
        assert!(openings(&app).is_empty());
        clear_the_box_truck(&mut drive);
        drive.update_lane_gap(&mut app.ctx, 0.1);
        if mode == "quiet" {
            assert_eq!(openings(&app), vec!["Right lane open."]);
            assert_eq!(
                app.ctx.message_log.messages.last().unwrap().text,
                "Right lane open."
            );
        } else {
            assert!(openings(&app).is_empty());
            assert_eq!(app.ctx.message_log.messages.len(), before);
        }
        assert!(drive.lane_status_text().contains("Right lane open."));
        app.shutdown();
    }
}

#[test]
fn urgent_only_keeps_the_fuel_rescue_restart_instruction() {
    let mut app = TestApp::new();
    let mut drive = a_gap_drive(&mut app);
    app.ctx.settings.driving_speech = "urgent_only".to_string();
    app.clear_speech();
    drive.handle_out_of_fuel(&mut app.ctx);
    assert!(app
        .event_lines()
        .iter()
        .any(|line| line.contains("restart the engine")));
    app.shutdown();
}
