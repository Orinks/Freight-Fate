//! Clipboard behaviour underlying the activation-code review items
//! (port of `tests/test_online_clipboard.py`).
//!
//! # The one deliberate difference from the Python
//!
//! Every case in the Python file tested a rung of a per-platform *fallback
//! ladder*: `pygame.scrap` with its X11 selection targets, then `pbcopy` /
//! `pbpaste` on darwin, then a hidden Tk root everywhere else, then a
//! read-back verify that forgave Windows CRLF. That ladder existed because
//! pygame's scrap is a different API on every platform and creating a Tk root
//! inside a running SDL app aborts the process on macOS.
//!
//! None of it survives the port, by design: `GameContext::write_clipboard_text`
//! goes to `Clipboard`, which is SDL's own UTF-8 clipboard in the windowed app
//! (`SDL_SetClipboardText` / `SDL_GetClipboardText`, the same two calls on
//! every platform) and an in-memory string headless. There is no scrap type to
//! choose, no subprocess to spawn, no Tk to avoid, and no encoding table to get
//! wrong -- so there is nothing left for a "does the mac path avoid Tk" case to
//! assert about the mac path.
//!
//! Each Python name is kept, and each asserts the guarantee its rung was
//! protecting, expressed against the one path that replaced them: exact
//! round-trip including non-ASCII and newlines, an empty clipboard reading as
//! nothing, and -- the case that mattered most -- a copy that failed never
//! being reported as one that worked. Where a case's whole subject is gone,
//! the body says so and pins the invariant that made it gone.

use crate::states_online_support::RefusingClipboard;
use freight_fate::app::testing::TestApp;
use freight_fate::app::{Clipboard, MemoryClipboard};

/// A clipboard that mangles what it is given the way the Windows path used
/// to: every newline comes back as CRLF. Nothing in the game does this any
/// more; it stands in for a host clipboard that might.
struct CrlfClipboard {
    text: Option<String>,
}

impl Clipboard for CrlfClipboard {
    fn get_text(&self) -> Option<String> {
        self.text.as_ref().map(|t| t.replace('\n', "\r\n"))
    }
    fn set_text(&mut self, text: &str) -> bool {
        self.text = Some(text.to_string());
        true
    }
}

#[test]
fn test_x11_read_uses_the_type_the_clipboard_actually_offers() {
    // Python: pick the "text/plain;charset=utf-8" selection target, because
    // the bare "text/plain" pygame offers is advertised by nobody. Rust:
    // there is one target, SDL's, and a read returns exactly what a write
    // put there -- trailing whitespace included, because nothing in the game
    // trims a clipboard any more.
    let mut clipboard = MemoryClipboard::default();
    assert!(clipboard.set_text("road-star-abcd1234"));
    assert_eq!(clipboard.get_text().as_deref(), Some("road-star-abcd1234"));
}

#[test]
fn test_x11_write_uses_the_type_x11_accepts() {
    // Python: a write for the wrong target was refused outright. Here the
    // write goes through `ctx.write_clipboard_text`, reports that it landed,
    // and the clipboard holds the bytes it was handed.
    let mut app = TestApp::new();
    let token = format!("ffd_{}", "a".repeat(64));
    assert!(app.ctx.write_clipboard_text(&token));
    assert_eq!(
        app.ctx.clipboard.get_text().as_deref(),
        Some(token.as_str())
    );
}

#[test]
fn test_mac_fallback_reads_pbpaste() {
    // The `pbpaste` rung is gone: macOS reads through the same SDL clipboard
    // as everything else, so there is no subprocess to spawn and no
    // platform branch to take. What survives is that a read answers with
    // whatever the clipboard holds, and only that.
    let mut clipboard = MemoryClipboard {
        text: Some("abc-driver-123".to_string()),
    };
    assert_eq!(clipboard.get_text().as_deref(), Some("abc-driver-123"));
    assert!(clipboard.set_text("something else"));
    assert_eq!(clipboard.get_text().as_deref(), Some("something else"));
}

#[test]
fn test_mac_fallback_never_creates_tk() {
    // The hidden Tk root was the thing that aborted a running SDL app at the
    // C level on darwin. Nothing constructs one now -- the whole ladder is a
    // single trait call -- so the case reduces to: a clipboard that cannot
    // answer answers nothing, and the game carries on.
    let clipboard = RefusingClipboard;
    assert!(clipboard.get_text().is_none());
}

#[test]
fn test_mac_fallback_empty_clipboard_is_none() {
    let clipboard = MemoryClipboard::default();
    assert!(clipboard.get_text().is_none());
}

#[test]
fn test_non_mac_still_uses_tk_fallback() {
    // Python kept Tk on non-darwin because pygame's scrap could fail there.
    // SDL's clipboard is the same call on every platform, so Windows takes
    // the identical path macOS and Linux do -- which is what this now pins.
    let mut app = TestApp::new();
    assert!(app.ctx.write_clipboard_text("ffd_token"));
    assert_eq!(app.ctx.clipboard.get_text().as_deref(), Some("ffd_token"));
}

#[test]
fn test_mac_write_uses_pbcopy_and_never_creates_tk() {
    // The delivery-summary copy is multi-line; it must land verbatim,
    // newlines and all, with nothing appended and nothing stripped.
    let mut app = TestApp::new();
    assert!(app.ctx.write_clipboard_text("summary line one\nline two"));
    assert_eq!(
        app.ctx.clipboard.get_text().as_deref(),
        Some("summary line one\nline two")
    );
}

#[test]
fn test_write_reports_failure_when_read_back_disagrees() {
    // "Copied" must never be optimistic. Python proved that by writing and
    // reading back; the Rust clipboard reports the failure directly, and
    // `write_clipboard_text` passes that answer straight through rather
    // than assuming success.
    let mut app = TestApp::new();
    app.ctx.clipboard = Box::new(RefusingClipboard);
    assert!(!app.ctx.write_clipboard_text("expected text"));
}

#[test]
fn test_read_back_forgives_windows_crlf() {
    // There is no read-back verify to forgive anything: the write's own
    // answer decides. A host clipboard that normalises newlines therefore
    // cannot turn a successful copy into a reported failure -- the bug the
    // Python forgiveness existed to avoid.
    let mut app = TestApp::new();
    app.ctx.clipboard = Box::new(CrlfClipboard { text: None });
    assert!(app.ctx.write_clipboard_text("line one\nline two"));
    assert_eq!(
        app.ctx.clipboard.get_text().as_deref(),
        Some("line one\r\nline two")
    );
}

#[test]
fn test_utf16_clipboard_payload_round_trips_on_windows() {
    // Python decoded the scrap payload per platform and got it wrong on
    // Windows, silently eating every non-ASCII character. Rust never sees
    // bytes: `Clipboard` is `&str` in and `String` out, so the accented
    // characters and the em dash survive by construction.
    let text = "Delivered to Montréal — 12 tonnes";
    let mut app = TestApp::new();
    assert!(app.ctx.write_clipboard_text(text));
    assert_eq!(app.ctx.clipboard.get_text().as_deref(), Some(text));
}

#[test]
fn test_utf8_clipboard_payload_round_trips_on_linux() {
    // The other half of the same pair: one path, so there is no per-platform
    // encoding table left to "simplify" into corrupting the other one.
    let text = "Delivered to Montréal — 12 tonnes";
    let mut clipboard = MemoryClipboard::default();
    assert!(clipboard.set_text(text));
    assert_eq!(clipboard.get_text().as_deref(), Some(text));
}
