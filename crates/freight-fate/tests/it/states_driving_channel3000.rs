//! Channel 3000 on 87.7, in the cab: tuning in by daypart, the schedule
//! running on while the radio is elsewhere, Shift+Y, and the station
//! staying off the dial in a build without its pack.
//!
//! The pack itself is never needed here: the audio is a recorder, so these
//! tests put the station on the dial by hand where a build with the pack
//! would, and take it off where a build without one would.

use ff_core::channel3000::{ClipKind, Daypart, CHANNEL_3000_ID};
use ff_core::data::world::get_world;
use ff_core::models::jobs::{Job, CARGO_CATALOG};
use ff_core::models::profile::Profile;
use ff_core::radio::SAFE_ROUTE_PLAYLIST;

use freight_fate::app::testing::{AudioLog, RecordingAudio, TestApp};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::DRIVE_PHASE_DELIVERY;
use freight_fate::states::driving_updates::radio_channel3000::channel3000_playable;

/// The Denver run, starting at `local_hour` on Denver's clock.
fn a_drive_at(app: &mut TestApp, local_hour: f64) -> DrivingState {
    let build = |app: &mut TestApp, start_hour: f64| {
        let world = get_world();
        app.ctx.profile = Some(Profile::named_in("Channel 3000", "Denver"));
        let route = world
            .route_from_cities(&["Denver", "Salt Lake City"])
            .expect("Denver to Salt Lake City routes");
        let job = Job::new(
            &CARGO_CATALOG["general"],
            12.0,
            "Denver",
            "Denver Dry Warehouse",
            "Salt Lake City",
            520.0,
            2400.0,
            14.0,
        );
        let mut drive = DrivingState::new(
            &mut app.ctx,
            job,
            route,
            Some(3000),
            DRIVE_PHASE_DELIVERY,
            Some(start_hour),
        );
        drive.trip.set_npc_vehicles(Vec::new());
        drive
    };
    // The drive's start hour is on the trip's reference clock; find Denver's
    // offset from it, then start where the local clock reads `local_hour`.
    let probe = build(app, 12.0);
    let offset = probe.trip.local_hour() - 12.0;
    let drive = build(app, (local_hour - offset).rem_euclid(24.0));
    assert!((drive.trip.local_hour() - local_hour).abs() < 1e-6);
    drive
}

fn install_audio(app: &mut TestApp) -> AudioLog {
    let audio = RecordingAudio::new();
    let log = audio.log();
    app.ctx.audio = Box::new(audio);
    log
}

/// A drive at `local_hour`, engine running, with Channel 3000 on the dial
/// as a build with its pack would have it.
fn tuned_at(app: &mut TestApp, local_hour: f64) -> (DrivingState, AudioLog) {
    let mut d = a_drive_at(app, local_hour);
    d.set_channel3000_on_dial(true);
    let log = install_audio(app);
    d.trip.truck.start_engine();
    let said = d.tune_radio_to(&mut app.ctx, CHANNEL_3000_ID);
    assert!(said.contains("Channel 3000"), "{said}");
    (d, log)
}

fn last_track(log: &AudioLog) -> (String, f64) {
    let calls = log.borrow();
    let track = calls.music.last().expect("music played").0.clone();
    let start = *calls.music_start_s.last().unwrap();
    (track, start)
}

fn clip_for(d: &DrivingState, track: &str) -> &'static ff_core::channel3000::Clip {
    let key = track.strip_prefix("c3k/").expect("a Channel 3000 clip");
    d.channel3000
        .as_ref()
        .unwrap()
        .manifest()
        .clips
        .iter()
        .find(|c| c.key == key)
        .expect("the clip is in the manifest")
}

#[test]
fn tuning_in_by_day_plays_a_daytime_clip_part_way_in() {
    let mut app = TestApp::new();
    let (d, log) = tuned_at(&mut app, 10.0);
    let (track, start) = last_track(&log);
    let clip = clip_for(&d, &track);
    assert!(clip.airs_in(Daypart::Day), "{track} at 10:00");
    // Mid-clip, where the station has got to, like any other station.
    let schedule = d.channel3000.as_ref().unwrap();
    assert_eq!(schedule.on_air().unwrap().key, clip.key);
    assert!((0.0..clip.duration_s).contains(&start), "{start}");
    assert!((start - schedule.elapsed_s()).abs() < 1e-6);
}

#[test]
fn tuning_in_by_night_plays_a_late_night_clip() {
    let mut app = TestApp::new();
    let (d, log) = tuned_at(&mut app, 23.5);
    let (track, _) = last_track(&log);
    assert!(
        clip_for(&d, &track).airs_in(Daypart::Late),
        "{track} at 23:30"
    );
}

#[test]
fn shift_y_names_the_programme_on_the_air() {
    let mut app = TestApp::new();
    let (mut d, _log) = tuned_at(&mut app, 10.0);
    // Run the station on to its next programme.
    for _ in 0..20 {
        let schedule = d.channel3000.as_ref().unwrap();
        let clip = schedule.on_air().unwrap();
        if clip.kind == ClipKind::Programme {
            break;
        }
        let left = clip.duration_s - schedule.elapsed_s() + 0.01;
        d.advance_radio_airtime(left);
    }
    let clip = d.channel3000.as_ref().unwrap().on_air().unwrap();
    assert_eq!(clip.kind, ClipKind::Programme);
    let stop = if clip.title.ends_with(['.', '!', '?']) {
        ""
    } else {
        "."
    };
    assert_eq!(
        d.radio_now_playing_text(&mut app.ctx),
        format!("Now playing on Channel 3000: {}{stop}", clip.title)
    );
}

#[test]
fn shift_y_on_the_station_s_own_glue_says_its_name_once() {
    let mut app = TestApp::new();
    let (mut d, _log) = tuned_at(&mut app, 10.0);
    for _ in 0..40 {
        let schedule = d.channel3000.as_ref().unwrap();
        let clip = schedule.on_air().unwrap();
        if matches!(clip.kind, ClipKind::Ident | ClipKind::Continuity) {
            break;
        }
        let left = clip.duration_s - schedule.elapsed_s() + 0.01;
        d.advance_radio_airtime(left);
    }
    assert_eq!(
        d.radio_now_playing_text(&mut app.ctx),
        "Now playing on Channel 3000."
    );
}

#[test]
fn each_new_clip_plays_as_the_schedule_reaches_it() {
    let mut app = TestApp::new();
    let (mut d, log) = tuned_at(&mut app, 10.0);
    let (first, _) = last_track(&log);
    let schedule = d.channel3000.as_ref().unwrap();
    let left = schedule.on_air().unwrap().duration_s - schedule.elapsed_s();
    d.update_audio(&mut app.ctx, left + 0.05);
    let (next, start) = last_track(&log);
    assert_ne!(next, first);
    assert!(next.starts_with("c3k/"), "{next}");
    assert_eq!(
        d.channel3000.as_ref().unwrap().on_air().unwrap().key,
        next.trim_start_matches("c3k/")
    );
    assert!(start < 1.0, "a new clip starts from its top: {start}");
}

#[test]
fn the_station_keeps_broadcasting_while_the_radio_is_elsewhere() {
    let mut app = TestApp::new();
    let (mut d, log) = tuned_at(&mut app, 10.0);
    let before = d.channel3000.as_ref().unwrap().serial();
    d.tune_radio_to(&mut app.ctx, SAFE_ROUTE_PLAYLIST);
    // Half an hour on the Roadhouse, then half an hour with the radio off.
    for _ in 0..1800 {
        d.update_audio(&mut app.ctx, 1.0);
    }
    d.toggle_radio(&mut app.ctx);
    assert!(!d.radio.enabled);
    for _ in 0..1800 {
        d.update_audio(&mut app.ctx, 1.0);
    }
    let schedule = d.channel3000.as_ref().unwrap();
    assert!(schedule.serial() > before, "the schedule ran on");
    let on_air = schedule.on_air().unwrap().key.clone();
    d.tune_radio_to(&mut app.ctx, CHANNEL_3000_ID);
    let (track, _) = last_track(&log);
    assert_eq!(track, format!("c3k/{on_air}"));
}

#[test]
fn without_its_pack_the_station_is_off_the_dial() {
    let mut app = TestApp::new();
    let mut d = a_drive_at(&mut app, 10.0);
    d.set_channel3000_on_dial(false);
    let log = install_audio(&mut app);
    d.trip.truck.start_engine();
    assert!(!d
        .radio
        .receivable_stations()
        .iter()
        .any(|r| r.station.id == CHANNEL_3000_ID));
    d.tune_radio_to(&mut app.ctx, CHANNEL_3000_ID);
    assert!(log
        .borrow()
        .music
        .iter()
        .all(|(track, _)| !track.starts_with("c3k/")));
    // And the build's own check agrees: no schedule, no station.
    assert!(!channel3000_playable(None));
}

#[test]
fn on_the_dial_the_station_sits_with_the_freight_fate_stations() {
    let mut app = TestApp::new();
    let mut d = a_drive_at(&mut app, 10.0);
    d.set_channel3000_on_dial(true);
    let reception = d
        .radio
        .receivable_stations()
        .into_iter()
        .find(|r| r.station.id == CHANNEL_3000_ID)
        .expect("on the dial");
    assert_eq!(ff_core::radio::dial_group(&reception.station), 1);
    assert_eq!(reception.station.frequency_mhz, 87.7);
    assert_eq!(reception.signal_label(), "always available");
}
