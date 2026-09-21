//! Controller input diagnostic tool (port of
//! `freight_fate/controller_diagnostics.py`; `freightfate
//! --controller-diagnostics`).
//!
//! Freight Fate reads controllers through SDL's *GameController* API, which
//! remaps any recognized pad onto the Xbox button layout. On some pads --
//! notably the DualSense -- the D-pad, sticks, stick clicks, and face buttons
//! come through, but the triggers and shoulder buttons do not. That is the
//! signature of an SDL controller-*mapping* gap for that specific device: the
//! raw pad may still be emitting those inputs on the lower *joystick* layer,
//! but SDL never surfaces them as GameController events.
//!
//! To tell those cases apart, this tool listens on **both** layers at once
//! and logs them side by side:
//!
//! * `[GC ]` -- the GameController (`CONTROLLER*`) events, exactly what the
//!   game itself sees.
//! * `[JOY]` -- the raw joystick (`JOY*`) events plus each device's GUID,
//!   name, and axis/button counts, i.e. what SDL actually delivers before
//!   mapping.
//!
//! Press LT/RT/LB/RB on the problem pad and read which layer (if any)
//! reports them:
//!
//! * `[JOY]` only  -> a mapping gap; fixable via an `SDL_GAMECONTROLLERCONFIG`
//!   mapping or a HIDAPI hint.
//! * neither       -> the input never reaches SDL.
//! * both          -> the issue is elsewhere in the game's input path.
//!
//! Everything is printed to the terminal and written to
//! `controller-diagnostics.log` in the current directory (overwritten on each
//! launch). Exit by closing the window or Ctrl+C; the log file is left in
//! place for review.

use std::fs::File;
use std::io::Write;
use std::path::PathBuf;
use std::time::Duration;

use sdl2::event::Event;
use sdl2::joystick::HatState;

use super::AXIS_MAX;

pub const LOG_FILENAME: &str = "controller-diagnostics.log";

/// The terminal-plus-file logger the tool writes through (its own, not the
/// game's: the game's handlers may not be configured when this runs).
struct DiagLog {
    file: Option<File>,
}

impl DiagLog {
    fn info(&mut self, message: &str) {
        let line = format!(
            "{} INFO: {message}",
            chrono::Local::now().format("%Y-%m-%d %H:%M:%S,%3f")
        );
        println!("{line}");
        if let Some(file) = self.file.as_mut() {
            let _ = writeln!(file, "{line}");
        }
    }
}

fn hat_str(state: HatState) -> &'static str {
    match state {
        HatState::Centered => "centered",
        HatState::Up => "up",
        HatState::Right => "right",
        HatState::Down => "down",
        HatState::Left => "left",
        HatState::RightUp => "up right",
        HatState::RightDown => "down right",
        HatState::LeftUp => "up left",
        HatState::LeftDown => "down left",
    }
}

/// Reproduce the game's pre-init environment: the HIDAPI rumble hints that
/// change how SDL binds PlayStation pads, so the pad is enumerated exactly as
/// it is when the game runs. Mirrors `App::new`.
pub fn prepare_environment() {
    for (name, value) in [
        ("SDL_JOYSTICK_HIDAPI_PS4_RUMBLE", "1"),
        ("SDL_JOYSTICK_HIDAPI_PS5_RUMBLE", "1"),
    ] {
        if std::env::var_os(name).is_none() {
            std::env::set_var(name, value);
        }
    }
}

/// Run the diagnostic session; the process exit code.
pub fn run_controller_diagnostics() -> i32 {
    prepare_environment();
    let log_path = std::env::current_dir()
        .unwrap_or_else(|_| PathBuf::from("."))
        .join(LOG_FILENAME);
    let mut log = DiagLog {
        file: File::create(&log_path).ok(),
    };
    log.info("Controller diagnostics starting.");
    log.info(&format!(
        "Logging to {} (overwritten on each launch).",
        log_path.display()
    ));

    let sdl = match sdl2::init() {
        Ok(sdl) => sdl,
        Err(e) => {
            log.info(&format!("SDL could not start: {e}"));
            return 1;
        }
    };
    // A visible window keeps the OS event pump alive; on Windows, controller
    // and joystick events are not delivered reliably to a windowless process.
    let video = match sdl.video() {
        Ok(video) => video,
        Err(e) => {
            log.info(&format!("SDL video could not start: {e}"));
            return 1;
        }
    };
    let _window = video
        .window("Freight Fate - Controller Diagnostics", 480, 160)
        .position_centered()
        .build()
        .ok();
    // Both input layers, initialized together so the same physical pad
    // reports on each: the GameController layer the game uses, and the raw
    // joystick layer.
    let (Ok(controllers), Ok(joysticks)) = (sdl.game_controller(), sdl.joystick()) else {
        log.info("Controller or joystick subsystem unavailable.");
        return 1;
    };

    // Open every recognized GameController so it emits CONTROLLER* events
    // -- all of them rather than just the first, so a session covers
    // whatever the tester has plugged in.
    let mut opened = Vec::new();
    let count = controllers.num_joysticks().unwrap_or(0);
    for index in 0..count {
        if controllers.is_game_controller(index) {
            match controllers.open(index) {
                Ok(controller) => opened.push(controller),
                Err(e) => log.info(&format!(
                    "Could not open GameController at slot {index}: {e}"
                )),
            }
        }
    }

    // One-time snapshot of every device on both layers. The joystick GUID
    // plus axis/button counts are the decisive clues for a mapping gap.
    log.info("=== Device inventory ===");
    log.info(&format!("SDL sees {count} device slot(s)."));
    for index in 0..count {
        let is_ctrl = controllers.is_game_controller(index);
        let name = controllers
            .name_for_index(index)
            .unwrap_or_else(|_| "unknown".to_string());
        log.info(&format!(
            "  slot {index}: recognized as GameController={is_ctrl}, name={name:?}"
        ));
    }
    let joy_count = joysticks.num_joysticks().unwrap_or(0);
    log.info(&format!("Raw joystick layer sees {joy_count} device(s)."));
    let mut opened_joysticks = Vec::new();
    for index in 0..joy_count {
        match joysticks.open(index) {
            Ok(joy) => {
                let power = joy
                    .power_level()
                    .map(|p| format!("{p:?}"))
                    .unwrap_or_else(|_| "unknown".to_string());
                log.info(&format!(
                    "  joystick {index}: name={:?} guid={} axes={} buttons={} hats={} power={power}",
                    joy.name(),
                    joy.guid(),
                    joy.num_axes(),
                    joy.num_buttons(),
                    joy.num_hats()
                ));
                opened_joysticks.push(joy);
            }
            Err(e) => log.info(&format!("  joystick {index}: could not open: {e}")),
        }
    }
    log.info(
        "=== Press controls now. Triggers=LT/RT, shoulders=LB/RB. Close the window to exit. ===",
    );

    let Ok(mut pump) = sdl.event_pump() else {
        log.info("No event pump.");
        return 1;
    };
    'outer: loop {
        for event in pump.poll_iter() {
            match event {
                Event::Quit { .. } => break 'outer,
                // -- GameController layer (what the game sees) -------------
                Event::ControllerAxisMotion {
                    which, axis, value, ..
                } => log.info(&format!(
                    "[GC ] AXIS  {:<13} raw={value:+6} norm={:+.3} (device {which})",
                    axis.string(),
                    value as f64 / AXIS_MAX
                )),
                Event::ControllerButtonDown { which, button, .. } => log.info(&format!(
                    "[GC ] BTN   {:<13} DOWN (device {which})",
                    button.string()
                )),
                Event::ControllerButtonUp { which, button, .. } => log.info(&format!(
                    "[GC ] BTN   {:<13} UP   (device {which})",
                    button.string()
                )),
                Event::ControllerDeviceAdded { which, .. } => {
                    log.info(&format!("[GC ] device added (slot {which})"))
                }
                Event::ControllerDeviceRemoved { which, .. } => {
                    log.info(&format!("[GC ] device removed (device {which})"))
                }
                // -- Raw joystick layer (what SDL delivers pre-mapping) ------
                Event::JoyAxisMotion {
                    which,
                    axis_idx,
                    value,
                    ..
                } => log.info(&format!(
                    "[JOY] AXIS  index={axis_idx:<2} value={:+.3} (device {which})",
                    value as f64 / AXIS_MAX
                )),
                Event::JoyButtonDown {
                    which, button_idx, ..
                } => log.info(&format!(
                    "[JOY] BTN   index={button_idx:<2} DOWN (device {which})"
                )),
                Event::JoyButtonUp {
                    which, button_idx, ..
                } => log.info(&format!(
                    "[JOY] BTN   index={button_idx:<2} UP   (device {which})"
                )),
                Event::JoyHatMotion {
                    which,
                    hat_idx,
                    state,
                    ..
                } => log.info(&format!(
                    "[JOY] HAT   index={hat_idx:<2} {:?} ({}) (device {which})",
                    state,
                    hat_str(state)
                )),
                Event::JoyDeviceAdded { which, .. } => match joysticks.open(which) {
                    Ok(joy) => {
                        log.info(&format!(
                            "[JOY] device added: name={:?} guid={}",
                            joy.name(),
                            joy.guid()
                        ));
                        opened_joysticks.push(joy);
                    }
                    Err(_) => log.info(&format!("[JOY] device added (slot {which})")),
                },
                Event::JoyDeviceRemoved { which, .. } => {
                    log.info(&format!("[JOY] device removed (device {which})"))
                }
                _ => {}
            }
        }
        std::thread::sleep(Duration::from_millis(16));
    }
    drop(opened); // drop references before quitting SDL
    drop(opened_joysticks);
    log.info(&format!(
        "Controller diagnostics stopped. Log saved to {}",
        log_path.display()
    ));
    0
}
