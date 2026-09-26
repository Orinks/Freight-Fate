//! One unbroken rest at a stop counts as one: 3 hours in the berth and then
//! 3 more is 6 hours toward the 10-hour reset, and the menu asks only for
//! the 4 that are left (tester report, 2026-09-23).

use ff_core::sim::trip_models::RoadStop;
use freight_fate::playtest::harness::{PlaytestHarness, StartDelivery};
use freight_fate::states::base::Key;
use freight_fate::states::driving_rest_states::RestStopState;

fn hos(h: &PlaytestHarness) -> ff_core::sim::hos::HosClock {
    h.app.ctx.profile.as_ref().expect("a career").hos.clone()
}

#[test]
fn back_to_back_berth_sleeps_count_toward_the_reset() {
    let mut h = PlaytestHarness::new();
    h.app.ctx.settings.hos_mode = "realistic".into();
    h.start_delivery(StartDelivery::named("Rest Stretch"));
    h.with_drive(|d, ctx| {
        d.departure_checked = true;
        let mut stop = RoadStop::new(
            "Test Travel Center",
            d.trip.position_mi.max(1.0),
            "travel_center",
        );
        stop.actions = vec!["break".into(), "sleep".into()];
        stop.parking = "confirmed".into();
        d.trip.position_mi = stop.at_mi;
        d.trip.stops = vec![stop];
        // The tester's clock at the stop: under two hours of window left.
        let clock = &mut ctx.profile.as_mut().expect("a career").hos;
        clock.drive(500.0);
        clock.on_duty(235.0);
    });
    h.press_key(Key::T, Some('t'));
    assert!(h.state_is::<RestStopState>());

    // Each sleep choice previews the cost before a second selection commits it.
    h.select_menu_item("Sleep 3 hours in sleeper berth");
    h.select_menu_item("Sleep 3 hours in sleeper berth");
    h.select_menu_item("Sleep 3 hours in sleeper berth");
    h.clear_speech();
    h.select_menu_item("Sleep 3 hours in sleeper berth");
    let woke = h.app.speech().lines().join(" ");
    assert!(
        woke.contains("Finish the split or sleep 4 hours more here to finish a 10-hour reset"),
        "{woke}"
    );
    assert_eq!(hos(&h).reset_minutes_left(), Some(240.0));

    let before = h.read_drive(|d| d.trip.local_hour());
    h.clear_speech();
    h.select_menu_item("Sleep 4 hours more to finish a 10-hour reset");
    h.clear_speech();
    h.select_menu_item("Sleep 4 hours more to finish a 10-hour reset");
    let woke = h.app.speech().lines().join(" ");
    assert!(woke.contains("You slept 4 hours more"), "{woke}");
    assert!(woke.contains("Hours of service reset"), "{woke}");
    let clock = hos(&h);
    assert_eq!(clock.driving_min, 0.0);
    assert_eq!(clock.duty_min, 0.0);
    let slept = (h.read_drive(|d| d.trip.local_hour()) - before).rem_euclid(24.0);
    assert!((slept - 4.0).abs() < 1e-6, "clock moved {slept} hours");
}
