//! The windowed shell boots under SDL's dummy video driver -- every
//! headless run (CI, `--agent-server` under `FREIGHT_FATE_NO_SPEECH`, the
//! playtest benches) goes through it. The native window handle taken for
//! the nonblocking Windows shutdown does not exist there, and the sdl2
//! crate panics rather than errs when asked for it, which killed every
//! headless windowed boot the day the handle arrived (2026-09-01).

use freight_fate::app::sdl_shell::SdlShell;

#[test]
fn the_shell_boots_on_the_dummy_video_driver() {
    std::env::set_var("SDL_VIDEODRIVER", "dummy");
    std::env::set_var("SDL_AUDIODRIVER", "dummy");
    let shell = SdlShell::new("Freight Fate headless").expect("the dummy driver hosts a window");
    assert_eq!(shell.video.current_video_driver(), "dummy");
}
