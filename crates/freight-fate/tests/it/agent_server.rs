//! The `--agent-server` handshake happens without a game. Every Claude Code
//! session start spawns each configured MCP server just to ask for its
//! tool list, and the first shipped server booted the real game (sandbox,
//! single-instance lock, window, audio, speech) BEFORE it read a byte of
//! stdin -- so enabling the server launched a game window into every
//! session and held the one-game-at-a-time lock against the owner (found
//! live, 2026-09-01). Now the handshake is answered from the serve thread
//! alone, the game boots at the first play request, and a client that
//! hangs up takes the game down with it.

use std::io::Cursor;
use std::sync::mpsc;

use freight_fate::agent_server::{await_play_request, policy, serve_lines, Command, Ears};
use freight_fate::app::testing::TestApp;

fn rpc(id: u64, method: &str, params: &str) -> String {
    format!(r#"{{"jsonrpc":"2.0","id":{id},"method":"{method}","params":{params}}}"#)
}

fn call(id: u64, tool: &str, args: &str) -> String {
    rpc(
        id,
        "tools/call",
        &format!(r#"{{"name":"{tool}","arguments":{args}}}"#),
    )
}

fn results(out: &[u8]) -> Vec<serde_json::Value> {
    String::from_utf8_lossy(out)
        .lines()
        .map(|line| serde_json::from_str(line).expect("one JSON-RPC message per line"))
        .collect()
}

#[test]
fn the_handshake_never_asks_for_a_game() {
    let script = [
        rpc(1, "initialize", r#"{"protocolVersion":"2025-06-18"}"#),
        rpc(2, "tools/list", "{}"),
        rpc(3, "ping", "{}"),
    ]
    .join("\n");
    let (tx, rx) = mpsc::channel();
    let mut out = Vec::new();
    serve_lines(Cursor::new(script), &mut out, &tx);

    let answered = results(&out);
    assert_eq!(answered.len(), 3, "every handshake message is answered");
    assert_eq!(
        answered[0]["result"]["serverInfo"]["name"],
        "freight-fate-agent"
    );
    assert!(
        answered[0]["result"]["instructions"]
            .as_str()
            .is_some_and(|text| text.contains("boots")),
        "the client is told the game boots at the first play call"
    );
    assert!(answered[1]["result"]["tools"].is_array());
    assert!(
        matches!(rx.try_recv(), Err(mpsc::TryRecvError::Empty)),
        "no handshake message reaches the game loop"
    );
}

#[test]
fn the_first_play_call_is_what_wakes_the_game() {
    let script = [
        rpc(1, "initialize", r#"{"protocolVersion":"2025-06-18"}"#),
        rpc(2, "tools/list", "{}"),
        call(3, "press", r#"{"key":"enter"}"#),
    ]
    .join("\n");
    let (tx, rx) = mpsc::channel();
    let server = std::thread::spawn(move || {
        let mut out = Vec::new();
        serve_lines(Cursor::new(script), &mut out, &tx);
        out
    });

    let request = await_play_request(&rx).expect("the press is a play request");
    assert!(matches!(request.command(), Command::Press { .. }));
    request.answer(Ok("the game is up".to_string()));

    let answered = results(&server.join().unwrap());
    assert_eq!(answered.len(), 3);
    assert_eq!(
        answered[2]["result"]["content"][0]["text"],
        "the game is up"
    );
}

#[test]
fn quitting_before_the_game_exists_needs_no_game() {
    let script = [call(1, "quit_game", "{}"), call(2, "listen", "{}")].join("\n");
    let (tx, rx) = mpsc::channel();
    let server = std::thread::spawn(move || {
        let mut out = Vec::new();
        serve_lines(Cursor::new(script), &mut out, &tx);
        out
    });

    let request = await_play_request(&rx).expect("the listen is the first play request");
    assert!(matches!(request.command(), Command::Listen));
    request.answer(Ok("heard".to_string()));

    let answered = results(&server.join().unwrap());
    let quit_text = answered[0]["result"]["content"][0]["text"]
        .as_str()
        .unwrap_or_default();
    assert!(
        quit_text.contains("not running"),
        "quit with no game is answered, not booted: {quit_text:?}"
    );
    assert_eq!(answered[1]["result"]["content"][0]["text"], "heard");
}

#[test]
fn a_client_that_hangs_up_before_playing_ends_the_wait() {
    let (tx, rx) = mpsc::channel::<freight_fate::agent_server::Request>();
    drop(tx);
    assert!(
        await_play_request(&rx).is_none(),
        "stdin closing with no play request means no game, ever"
    );
}

#[test]
fn a_client_that_hangs_up_mid_game_quits_it() {
    let mut app = TestApp::new();
    let (tx, rx) = mpsc::channel();
    let ears = Ears::shared();
    let mut agent = policy(ears, rx, None);
    drop(tx);
    let mut frames = 0;
    app.run_with_player_input(Some(30), |input, dt| {
        frames += 1;
        agent.step(input, dt)
    });
    assert_eq!(
        frames, 1,
        "the game loop ends on the first frame after the client is gone"
    );
}
