//! The SDL side of the app: the window, the event pump translated into
//! [`InputEvent`]s, the clipboard, and the render fill. Everything `App`
//! does that needs a display lives here so a headless `App` never touches
//! SDL at all.
//!
//! pygame fused `KEYDOWN` and its `unicode`; SDL2 delivers `KeyDown` and
//! then a separate `TextInput`. The pump pairs a `KeyDown` with the
//! `TextInput` that immediately follows it in the same batch (what pygame
//! does internally), so menus' first-letter jump, text entry, and the
//! `+`/`-` fallbacks keep working.

use sdl2::clipboard::ClipboardUtil;
use sdl2::event::{Event, WindowEvent};
use sdl2::keyboard::{Keycode, Mod};
use sdl2::pixels::Color;
use sdl2::render::WindowCanvas;
use sdl2::{EventPump, Sdl, VideoSubsystem};

use crate::controller::sdl::{axis_from_sdl, button_from_sdl};
use crate::states::base::{InputEvent, Key, Mods};

use super::context::Clipboard;
use super::{BG_COLOR, WINDOW_SIZE};

/// The SDL clipboard (UTF-8 through `SDL_SetClipboardText`, so the whole
/// CF_TEXT-drops-non-ASCII workaround of `online_states.py` is gone).
pub struct SdlClipboard {
    util: ClipboardUtil,
}

impl Clipboard for SdlClipboard {
    fn get_text(&self) -> Option<String> {
        self.util.clipboard_text().ok()
    }

    fn set_text(&mut self, text: &str) -> bool {
        match self.util.set_clipboard_text(text) {
            Ok(()) => true,
            Err(e) => {
                log::debug!("clipboard write failed: {e}");
                false
            }
        }
    }
}

/// The window and its pumps.
pub struct SdlShell {
    pub sdl: Sdl,
    pub video: VideoSubsystem,
    canvas: WindowCanvas,
    pump: EventPump,
    #[cfg(target_os = "windows")]
    window_handle: Option<isize>,
}

#[cfg(target_os = "windows")]
fn hide_windows_window_for_process_exit(handle: isize, hide: impl FnOnce(isize)) {
    hide(handle);
}

#[cfg(target_os = "windows")]
fn window_handle(window: &sdl2::video::Window) -> Option<isize> {
    use raw_window_handle::{HasWindowHandle, RawWindowHandle};

    let handle = window.window_handle().ok()?.as_raw();
    match handle {
        RawWindowHandle::Win32(handle) => Some(handle.hwnd.get()),
        _ => None,
    }
}

#[cfg(target_os = "windows")]
fn window_is_visible(handle: isize) -> bool {
    // SAFETY: IsWindowVisible only reads the WS_VISIBLE style of the window
    // and returns FALSE for a handle that is not a window; the handle came
    // from SDL's own window, which this shell keeps alive.
    unsafe { windows_sys::Win32::UI::WindowsAndMessaging::IsWindowVisible(handle as _) != 0 }
}

/// Run `force_show` when the window is not really on screen; returns
/// whether it had to.
///
/// A parent that launches with STARTUPINFO `wShowWindow = SW_HIDE` (Node's
/// `windowsHide`, which is how the Claude desktop app spawns MCP servers)
/// turns the process's FIRST `ShowWindow` into a hide, whatever it asked for
/// (Win32 `ShowWindow`: "nCmdShow is ignored the first time ... if the
/// program that launched the application provides a STARTUPINFO"). SDL's
/// initial show becomes that hide, SDL still believes the window is shown,
/// and its restore and raise are then no-ops: an operator-keys agent server
/// came up with no window at all, not even in Alt+Tab.
#[cfg(target_os = "windows")]
fn force_show_if_hidden(visible: bool, force_show: impl FnOnce()) -> bool {
    if !visible {
        force_show();
    }
    !visible
}

#[cfg(target_os = "windows")]
fn release_at_process_exit<T>(resource: T) {
    // SDL_DestroyRenderer/SDL_DestroyWindow can synchronously wait in the
    // Windows window stack after a long, frequently Alt-Tabbed session. The
    // process is already exiting, so the OS is the faster and safer owner of
    // final resource reclamation.
    std::mem::forget(resource);
}

#[cfg(not(target_os = "windows"))]
fn release_at_process_exit<T>(resource: T) {
    drop(resource);
}

impl SdlShell {
    /// `pygame.init()` + `set_caption` + `set_mode(WINDOW_SIZE)`.
    pub fn new(title: &str) -> Result<Self, String> {
        let sdl = sdl2::init()?;
        let video = sdl.video()?;
        let window = video
            .window(title, WINDOW_SIZE.0, WINDOW_SIZE.1)
            .position_centered()
            .build()
            .map_err(|e| e.to_string())?;
        // A dummy window has no GPU surface. Automatic renderer selection can
        // still enter native graphics drivers before falling back to software;
        // AMD's driver fail-fasts there in restricted Windows environments.
        let canvas = window.into_canvas();
        let canvas = if video.current_video_driver() == "dummy" {
            canvas.software()
        } else {
            canvas
        };
        let canvas = canvas.build().map_err(|e| e.to_string())?;
        // The dummy driver (every headless run: CI, the agent server under
        // FREIGHT_FATE_NO_SPEECH, the playtest benches) has no native window,
        // and the sdl2 crate PANICS rather than erring when asked for one --
        // a windowed headless boot died here the day the handle arrived.
        #[cfg(target_os = "windows")]
        let window_handle = if video.current_video_driver() == "dummy" {
            None
        } else {
            window_handle(canvas.window())
        };
        #[cfg(target_os = "windows")]
        if let Some(handle) = window_handle {
            log::info!(
                "window visible after startup: {}",
                window_is_visible(handle)
            );
        }
        let pump = sdl.event_pump()?;
        // pygame delivered event.unicode for every key; SDL needs text
        // input running for TextInput events.
        video.text_input().start();
        Ok(Self {
            sdl,
            video,
            canvas,
            pump,
            #[cfg(target_os = "windows")]
            window_handle,
        })
    }

    pub fn clipboard(&self) -> SdlClipboard {
        SdlClipboard {
            util: self.video.clipboard(),
        }
    }

    /// Minimize the window so it can never hold keyboard focus.
    ///
    /// The agent server calls this at launch: with the window focused, the
    /// operator's own typing in other apps leaks into the game whenever
    /// focus lands on it (found live -- the spaces in a chat message spoke
    /// the speed readout, over and over). Agent input is injected and does
    /// not need focus; the operator's keyboard must not have it.
    pub fn minimize(&mut self) {
        self.canvas.window_mut().minimize();
    }

    /// Bring a minimized window back and ask for focus, so the operator's
    /// keyboard lands in the game again. A window the launcher's
    /// STARTUPINFO kept hidden is shown first (see [`force_show_if_hidden`]).
    pub fn restore(&mut self) {
        #[cfg(target_os = "windows")]
        self.ensure_visible();
        self.canvas.window_mut().restore();
        self.canvas.window_mut().raise();
    }

    /// Show the window if Windows is keeping it hidden behind SDL's back.
    /// Hide first so SDL's shown flag is cleared and its show is not skipped;
    /// by now the launcher's one-time override is spent, so the show is
    /// honoured. Returns whether a show was forced; `None` without a native
    /// window (the dummy driver).
    #[cfg(target_os = "windows")]
    fn ensure_visible(&mut self) -> Option<bool> {
        let handle = self.window_handle?;
        let visible = window_is_visible(handle);
        let window = self.canvas.window_mut();
        let forced = force_show_if_hidden(visible, || {
            window.hide();
            window.show();
        });
        log::info!(
            "window visible: {visible}, forced show: {}",
            if forced { "yes" } else { "no" }
        );
        Some(forced)
    }

    /// Hand desktop focus back immediately and finish SDL at process exit.
    pub fn shutdown_for_process_exit(self) {
        #[cfg(target_os = "windows")]
        {
            if let Some(handle) = self.window_handle {
                hide_windows_window_for_process_exit(handle, |handle| unsafe {
                    use windows_sys::Win32::UI::WindowsAndMessaging::{ShowWindowAsync, SW_HIDE};

                    ShowWindowAsync(handle as _, SW_HIDE);
                });
            }
            release_at_process_exit(self);
        }

        #[cfg(not(target_os = "windows"))]
        {
            let mut shell = self;
            shell.video.text_input().stop();
            shell.canvas.window_mut().hide();
            release_at_process_exit(shell);
        }
    }

    /// Drain the event queue into game events. `None` when the batch was
    /// lost to a failure inside the pump (the Python loop's
    /// `pygame.event.get()` guard: a controller hot-plug, notably a Bluetooth
    /// resume, can make SDL's internal instance-id map inconsistent; losing
    /// this batch of events is survivable, crashing the game is not).
    pub fn poll(&mut self) -> Option<Vec<InputEvent>> {
        let pump = &mut self.pump;
        let raw = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            pump.poll_iter().collect::<Vec<Event>>()
        }))
        .ok()?;
        Some(translate_events(raw))
    }

    /// `screen.fill(BG_COLOR)` ... `display.flip()`. The text lines are not
    /// drawn: the window is a debug mirror of the speech, and `sdl2::ttf` is
    /// not enabled in this build; `State::lines()` stays for the harness.
    pub fn render(&mut self, _lines: &[String]) {
        self.canvas
            .set_draw_color(Color::RGB(BG_COLOR.0, BG_COLOR.1, BG_COLOR.2));
        self.canvas.clear();
        self.canvas.present();
    }
}

/// SDL events to game events, pairing each `KeyDown` with the `TextInput`
/// that follows it.
pub fn translate_events(raw: Vec<Event>) -> Vec<InputEvent> {
    let mut out = Vec::with_capacity(raw.len());
    let mut pending_text: Option<usize> = None; // index in `out` of the last KeyDown
    for event in raw {
        match event {
            Event::KeyDown {
                keycode,
                keymod,
                repeat,
                ..
            } => {
                let key = keycode.map(key_from_keycode).unwrap_or(Key::Other(0));
                out.push(InputEvent::KeyDown {
                    key,
                    mods: mods_from(keymod),
                    text: None,
                    repeat,
                });
                pending_text = Some(out.len() - 1);
                continue;
            }
            Event::TextInput { text, .. } => {
                if let Some(index) = pending_text.take() {
                    if let Some(InputEvent::KeyDown { text: slot, .. }) = out.get_mut(index) {
                        *slot = text.chars().next();
                    }
                }
                continue;
            }
            Event::KeyUp {
                keycode, keymod, ..
            } => {
                let key = keycode.map(key_from_keycode).unwrap_or(Key::Other(0));
                out.push(InputEvent::KeyUp {
                    key,
                    mods: mods_from(keymod),
                });
            }
            Event::ControllerButtonDown { which, button, .. } => {
                out.push(InputEvent::ControllerButtonDown {
                    button: button_from_sdl(button),
                    instance_id: which,
                });
            }
            Event::ControllerButtonUp { which, button, .. } => {
                out.push(InputEvent::ControllerButtonUp {
                    button: button_from_sdl(button),
                    instance_id: which,
                });
            }
            Event::ControllerAxisMotion {
                which, axis, value, ..
            } => {
                out.push(InputEvent::ControllerAxis {
                    axis: axis_from_sdl(axis),
                    value,
                    instance_id: which,
                });
            }
            Event::ControllerDeviceAdded { which, .. } => {
                out.push(InputEvent::ControllerAdded {
                    device_index: which,
                });
            }
            Event::ControllerDeviceRemoved { which, .. } => {
                out.push(InputEvent::ControllerRemoved { instance_id: which });
            }
            Event::Window {
                win_event: WindowEvent::FocusGained,
                ..
            } => out.push(InputEvent::WindowFocusGained),
            Event::Window {
                win_event: WindowEvent::FocusLost,
                ..
            } => out.push(InputEvent::WindowFocusLost),
            Event::Quit { .. } => out.push(InputEvent::Quit),
            _ => {}
        }
        pending_text = None;
    }
    out
}

/// `event.mod & KMOD_*`.
pub fn mods_from(keymod: Mod) -> Mods {
    Mods {
        shift: keymod.intersects(Mod::LSHIFTMOD | Mod::RSHIFTMOD),
        ctrl: keymod.intersects(Mod::LCTRLMOD | Mod::RCTRLMOD),
        alt: keymod.intersects(Mod::LALTMOD | Mod::RALTMOD),
    }
}

/// SDL keycode to the game's key set.
pub fn key_from_keycode(keycode: Keycode) -> Key {
    match keycode {
        Keycode::A => Key::A,
        Keycode::B => Key::B,
        Keycode::C => Key::C,
        Keycode::D => Key::D,
        Keycode::E => Key::E,
        Keycode::F => Key::F,
        Keycode::G => Key::G,
        Keycode::H => Key::H,
        Keycode::I => Key::I,
        Keycode::J => Key::J,
        Keycode::K => Key::K,
        Keycode::L => Key::L,
        Keycode::M => Key::M,
        Keycode::N => Key::N,
        Keycode::O => Key::O,
        Keycode::P => Key::P,
        Keycode::Q => Key::Q,
        Keycode::R => Key::R,
        Keycode::S => Key::S,
        Keycode::T => Key::T,
        Keycode::U => Key::U,
        Keycode::V => Key::V,
        Keycode::W => Key::W,
        Keycode::X => Key::X,
        Keycode::Y => Key::Y,
        Keycode::Z => Key::Z,
        Keycode::NUM_0 => Key::Num0,
        Keycode::NUM_1 => Key::Num1,
        Keycode::NUM_2 => Key::Num2,
        Keycode::NUM_3 => Key::Num3,
        Keycode::NUM_4 => Key::Num4,
        Keycode::NUM_5 => Key::Num5,
        Keycode::NUM_6 => Key::Num6,
        Keycode::NUM_7 => Key::Num7,
        Keycode::NUM_8 => Key::Num8,
        Keycode::NUM_9 => Key::Num9,
        Keycode::KP_0 => Key::Kp0,
        Keycode::KP_1 => Key::Kp1,
        Keycode::KP_2 => Key::Kp2,
        Keycode::KP_3 => Key::Kp3,
        Keycode::KP_4 => Key::Kp4,
        Keycode::KP_5 => Key::Kp5,
        Keycode::KP_6 => Key::Kp6,
        Keycode::KP_7 => Key::Kp7,
        Keycode::KP_8 => Key::Kp8,
        Keycode::KP_9 => Key::Kp9,
        Keycode::KP_ENTER => Key::KpEnter,
        Keycode::KP_PLUS => Key::KpPlus,
        Keycode::KP_MINUS => Key::KpMinus,
        Keycode::F1 => Key::F1,
        Keycode::F2 => Key::F2,
        Keycode::F3 => Key::F3,
        Keycode::F4 => Key::F4,
        Keycode::F5 => Key::F5,
        Keycode::F6 => Key::F6,
        Keycode::F7 => Key::F7,
        Keycode::F8 => Key::F8,
        Keycode::F9 => Key::F9,
        Keycode::F10 => Key::F10,
        Keycode::F11 => Key::F11,
        Keycode::F12 => Key::F12,
        Keycode::RETURN => Key::Return,
        Keycode::ESCAPE => Key::Escape,
        Keycode::SPACE => Key::Space,
        Keycode::TAB => Key::Tab,
        Keycode::BACKSPACE => Key::Backspace,
        Keycode::UP => Key::Up,
        Keycode::DOWN => Key::Down,
        Keycode::LEFT => Key::Left,
        Keycode::RIGHT => Key::Right,
        Keycode::HOME => Key::Home,
        Keycode::END => Key::End,
        Keycode::PAGEUP => Key::PageUp,
        Keycode::PAGEDOWN => Key::PageDown,
        Keycode::INSERT => Key::Insert,
        Keycode::DELETE => Key::Delete,
        Keycode::COMMA => Key::Comma,
        Keycode::PERIOD => Key::Period,
        Keycode::SLASH => Key::Slash,
        Keycode::BACKSLASH => Key::Backslash,
        Keycode::BACKQUOTE => Key::Backquote,
        Keycode::EQUALS => Key::Equals,
        Keycode::PLUS => Key::Plus,
        Keycode::MINUS => Key::Minus,
        Keycode::SEMICOLON => Key::Semicolon,
        Keycode::QUOTE => Key::Quote,
        Keycode::LEFTBRACKET => Key::LeftBracket,
        Keycode::RIGHTBRACKET => Key::RightBracket,
        Keycode::LCTRL => Key::LCtrl,
        Keycode::RCTRL => Key::RCtrl,
        Keycode::LSHIFT => Key::LShift,
        Keycode::RSHIFT => Key::RShift,
        Keycode::LALT => Key::LAlt,
        Keycode::RALT => Key::RAlt,
        other => Key::Other(other.into_i32()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keydown_pairs_with_the_following_text_input() {
        let raw = vec![
            Event::KeyDown {
                timestamp: 0,
                window_id: 0,
                keycode: Some(Keycode::A),
                scancode: None,
                keymod: Mod::LSHIFTMOD,
                repeat: false,
            },
            Event::TextInput {
                timestamp: 0,
                window_id: 0,
                text: "A".to_string(),
            },
            Event::KeyDown {
                timestamp: 0,
                window_id: 0,
                keycode: Some(Keycode::LEFT),
                scancode: None,
                keymod: Mod::NOMOD,
                repeat: false,
            },
        ];
        let events = translate_events(raw);
        assert_eq!(
            events,
            vec![
                InputEvent::KeyDown {
                    key: Key::A,
                    mods: Mods::SHIFT,
                    text: Some('A'),
                    repeat: false
                },
                InputEvent::key(Key::Left),
            ]
        );
    }

    #[test]
    fn mods_collapse_left_and_right() {
        assert_eq!(mods_from(Mod::RCTRLMOD), Mods::CTRL);
        assert!(mods_from(Mod::LALTMOD | Mod::LSHIFTMOD).alt);
        assert_eq!(mods_from(Mod::NOMOD), Mods::NONE);
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn final_windows_shutdown_does_not_run_a_blocking_resource_destructor() {
        use std::cell::Cell;
        use std::rc::Rc;

        struct DropNotice(Rc<Cell<bool>>);
        impl Drop for DropNotice {
            fn drop(&mut self) {
                self.0.set(true);
            }
        }

        let dropped = Rc::new(Cell::new(false));
        release_at_process_exit(DropNotice(Rc::clone(&dropped)));
        assert!(
            !dropped.get(),
            "Windows ran the synchronous SDL-style destructor during final exit"
        );
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn final_windows_shutdown_uses_the_nonblocking_hide_path() {
        use std::cell::Cell;

        let async_hide_called = Cell::new(false);
        hide_windows_window_for_process_exit(123, |handle| {
            assert_eq!(handle, 123);
            async_hide_called.set(true);
        });

        assert!(async_hide_called.get());
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn only_a_window_windows_kept_hidden_is_force_shown() {
        use std::cell::Cell;

        let shows = Cell::new(0);
        assert!(!force_show_if_hidden(true, || shows.set(shows.get() + 1)));
        assert_eq!(shows.get(), 0, "a visible window was hidden and shown");
        assert!(force_show_if_hidden(false, || shows.set(shows.get() + 1)));
        assert_eq!(shows.get(), 1, "a hidden window was left hidden");
    }

    #[cfg(target_os = "windows")]
    const HIDDEN_LAUNCH_REPORT: &str = "FREIGHT_FATE_HIDDEN_LAUNCH_REPORT";

    /// The child half of [`a_hidden_launch_still_ends_with_a_visible_window`];
    /// does nothing unless that test launched it.
    #[cfg(target_os = "windows")]
    #[test]
    #[ignore = "child process of a_hidden_launch_still_ends_with_a_visible_window"]
    fn hidden_launch_child() {
        let Some(report) = std::env::var_os(HIDDEN_LAUNCH_REPORT) else {
            return;
        };
        let mut shell = SdlShell::new("Freight Fate - hidden launch check").expect("window");
        let handle = shell.window_handle.expect("a native window");
        let created = window_is_visible(handle);
        // The forced show goes without activation, so the check never takes
        // the desktop's focus from whoever is using it. Not before creation:
        // the launch override applies to SDL's plain first show.
        sdl2::hint::set("SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN", "1");
        let forced = shell.ensure_visible() == Some(true);
        let now = window_is_visible(handle);
        std::fs::write(report, format!("{created} {forced} {now}")).expect("report");
        shell.shutdown_for_process_exit();
    }

    /// Launch the way the desktop app launches an MCP server (STARTUPINFO
    /// `SW_HIDE`; std's `Command` cannot set `wShowWindow` on stable) and
    /// check SDL's window is hidden by it and shown again by the fix.
    #[cfg(target_os = "windows")]
    #[test]
    #[ignore = "opens a real window on the desktop for a moment; run by name"]
    fn a_hidden_launch_still_ends_with_a_visible_window() {
        use std::os::windows::ffi::OsStrExt;
        use windows_sys::Win32::Foundation::CloseHandle;
        use windows_sys::Win32::System::Threading::{
            CreateProcessW, GetExitCodeProcess, WaitForSingleObject, CREATE_UNICODE_ENVIRONMENT,
            PROCESS_INFORMATION, STARTF_USESHOWWINDOW, STARTUPINFOW,
        };
        use windows_sys::Win32::UI::WindowsAndMessaging::SW_HIDE;

        let dir = tempfile::tempdir().expect("temp dir");
        let report = dir.path().join("report.txt");
        let exe = std::env::current_exe().expect("test exe");
        let mut command_line: Vec<u16> = format!(
            "\"{}\" app::sdl_shell::tests::hidden_launch_child --exact --ignored --test-threads=1",
            exe.display()
        )
        .encode_utf16()
        .chain([0])
        .collect();
        // The inherited environment, minus a headless run's dummy video
        // driver, plus where to write the report.
        let mut environment: Vec<u16> = Vec::new();
        for (key, value) in std::env::vars_os() {
            if key.eq_ignore_ascii_case("SDL_VIDEODRIVER") {
                continue;
            }
            environment.extend(key.encode_wide());
            environment.push(u16::from(b'='));
            environment.extend(value.encode_wide());
            environment.push(0);
        }
        environment.extend(HIDDEN_LAUNCH_REPORT.encode_utf16());
        environment.push(u16::from(b'='));
        environment.extend(report.as_os_str().encode_wide());
        environment.extend([0, 0]);

        // SAFETY: STARTUPINFOW and PROCESS_INFORMATION are plain C structs
        // of integers and pointers, for which all-zero is the documented
        // empty value. The command line and environment buffers are
        // NUL-terminated and outlive the call; the process and thread
        // handles are closed exactly once below.
        let exit_code = unsafe {
            let mut startup: STARTUPINFOW = std::mem::zeroed();
            startup.cb = std::mem::size_of::<STARTUPINFOW>() as u32;
            startup.dwFlags = STARTF_USESHOWWINDOW;
            startup.wShowWindow = SW_HIDE as u16;
            let mut process: PROCESS_INFORMATION = std::mem::zeroed();
            let created = CreateProcessW(
                std::ptr::null(),
                command_line.as_mut_ptr(),
                std::ptr::null(),
                std::ptr::null(),
                0,
                CREATE_UNICODE_ENVIRONMENT,
                environment.as_ptr().cast(),
                std::ptr::null(),
                &startup,
                &mut process,
            );
            assert_ne!(created, 0, "CreateProcessW failed");
            WaitForSingleObject(process.hProcess, 60_000);
            let mut code = u32::MAX;
            GetExitCodeProcess(process.hProcess, &mut code);
            CloseHandle(process.hThread);
            CloseHandle(process.hProcess);
            code
        };
        assert_eq!(exit_code, 0, "the child test failed");
        let report = std::fs::read_to_string(&report).expect("child report");
        assert_eq!(
            report, "false true true",
            "expected: hidden by the launch, forced, then visible \
             (created visible, forced, visible now)"
        );
    }
}
