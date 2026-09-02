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

use freight_fate::agent_server::{
    await_play_request, build_command, install_ears, policy, serve_lines, Command, CruiseTarget,
    Ears,
};
use freight_fate::app::testing::TestApp;
use freight_fate::states::base::Key;

const FRAME: f64 = 1.0 / 60.0;

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

#[test]
fn a_tap_lands_as_a_finger_tap_not_a_screen_reader_hold() {
    // Two frames, down then up. A press and release inside one frame is
    // what JAWS re-injects for a held key, and the held-key tracker holds
    // such a key for the repeat delay: a tapped brake read as the
    // reverse-selection hold and a tapped P fought the approach assist
    // (found live, 2026-09-01).
    let mut app = TestApp::new();
    let (tx, rx) = mpsc::channel();
    let server_tx = tx.clone(); // the test keeps `tx` so the client never "hangs up"
    let server = std::thread::spawn(move || {
        let mut out = Vec::new();
        serve_lines(
            Cursor::new(call(1, "press", r#"{"key":"space"}"#)),
            &mut out,
            &server_tx,
        );
        out
    });
    let first = await_play_request(&rx).expect("the press wakes the game");
    let mut agent = policy(Ears::shared(), rx, Some(first));
    let mut readings = Vec::new();
    app.run_with_player_input(Some(4), |input, dt| {
        readings.push(input.key_reads_pressed(Key::Space));
        agent.step(input, dt)
    });
    drop(tx);
    let _ = server.join();
    // Frame 1 reads the request, frame 2 sends the down, frame 3 the up.
    assert_eq!(
        readings,
        [false, false, true, false],
        "down for exactly one frame, then released for good (no half-second pulse)"
    );
}

// -- the tools that drive the whole game ---------------------------------------------
//
// Each of these exists because the raw keys could not do the job at pace: a
// hold-then-release through the client is a second or more of round trip,
// and at standard pacing that is twenty seconds of road (agent drive,
// 2026-09-02: every throttle tap overshot the limit and every brake landed
// late; four loop-backs at one gate).

/// The first tool call of a session, served to a policy over a live app.
fn wake(
    script: String,
) -> (
    mpsc::Sender<freight_fate::agent_server::Request>,
    std::thread::JoinHandle<Vec<u8>>,
    freight_fate::agent_server::AgentPolicy,
) {
    let (tx, rx) = mpsc::channel();
    let server_tx = tx.clone();
    let server = std::thread::spawn(move || {
        let mut out = Vec::new();
        serve_lines(Cursor::new(script), &mut out, &server_tx);
        out
    });
    let first = await_play_request(&rx).expect("the call wakes the game");
    (tx, server, policy(Ears::shared(), rx, Some(first)))
}

fn reply_text(answered: &[serde_json::Value]) -> String {
    answered[0]["result"]["content"][0]["text"]
        .as_str()
        .unwrap_or_default()
        .to_string()
}

#[test]
fn a_pedal_is_lifted_by_the_loop_not_the_client() {
    let mut app = TestApp::new();
    let (tx, server, mut agent) = wake(call(1, "pedal", r#"{"key":"up","seconds":0.05}"#));
    let mut readings = Vec::new();
    // Frames are clocked at 60 fps by hand, so the pedal's seconds are frames.
    app.run_with_player_input(Some(60), |input, _dt| {
        readings.push(input.key_reads_pressed(Key::Up));
        agent.step(input, FRAME)
    });
    drop(tx);
    let answered = results(&server.join().unwrap());
    let down = readings.iter().filter(|held| **held).count();
    assert!(
        (2..=6).contains(&down),
        "held for about three frames: {readings:?}"
    );
    assert!(
        !readings[readings.len() - 1],
        "and lifted with no release call"
    );
    assert_eq!(answered.len(), 1, "the reply arrived once the pedal was up");
    assert!(answered[0]["result"]["isError"].is_null(), "{answered:?}");
}

#[test]
fn wait_for_returns_the_moment_a_menu_is_on_screen() {
    let mut app = TestApp::new();
    let (tx, server, mut agent) = wake(call(1, "wait_for", r#"{"menu":true,"seconds":100}"#));
    let mut frames = 0;
    app.run_with_player_input(Some(10), |input, _dt| {
        frames += 1;
        agent.step(input, FRAME)
    });
    drop(tx);
    let answered = results(&server.join().unwrap());
    assert_eq!(
        answered.len(),
        1,
        "the title menu is a menu: answered at once"
    );
    assert!(
        !reply_text(&answered).contains("clock ran out"),
        "{}",
        reply_text(&answered)
    );
}

#[test]
fn wait_for_says_when_the_clock_ran_out() {
    let mut app = TestApp::new();
    let (tx, server, mut agent) = wake(call(
        1,
        "wait_for",
        r#"{"text":"never spoken","seconds":0.1}"#,
    ));
    app.run_with_player_input(Some(20), |input, _dt| agent.step(input, FRAME));
    drop(tx);
    let answered = results(&server.join().unwrap());
    assert_eq!(answered.len(), 1);
    assert!(
        reply_text(&answered).contains("clock ran out"),
        "{}",
        reply_text(&answered)
    );
}

#[test]
fn wait_for_hears_a_line_through_the_ears() {
    // The ears are the tee over the real speech sink; a menu move speaks
    // the row it lands on, and the wait releases on it.
    let mut app = TestApp::new();
    let ears = install_ears(&mut app);
    let (tx, rx) = mpsc::channel();
    let server_tx = tx.clone();
    let script = [
        call(1, "press", r#"{"key":"down"}"#),
        call(2, "wait_for", r#"{"text":"2 of","seconds":100}"#),
    ]
    .join("\n");
    let server = std::thread::spawn(move || {
        let mut out = Vec::new();
        serve_lines(Cursor::new(script), &mut out, &server_tx);
        out
    });
    let first = await_play_request(&rx).expect("the press wakes the game");
    let mut agent = policy(ears, rx, Some(first));
    app.run_with_player_input(Some(30), |input, _dt| agent.step(input, FRAME));
    drop(tx);
    let answered = results(&server.join().unwrap());
    assert_eq!(answered.len(), 2, "{answered:?}");
    let heard = answered[1]["result"]["content"][0]["text"]
        .as_str()
        .unwrap_or_default();
    assert!(heard.contains("2 of"), "{heard}");
    assert!(!heard.contains("clock ran out"), "{heard}");
}

#[test]
fn select_walks_to_the_row_by_part_of_its_label() {
    let mut app = TestApp::new();
    let (tx, server, mut agent) = wake(call(1, "select", r#"{"label":"how to play"}"#));
    let mut downs = 0;
    let mut enters = 0;
    app.run_with_player_input(Some(40), |input, _dt| {
        if input.key_reads_pressed(Key::Down) {
            downs += 1;
        }
        if input.key_reads_pressed(Key::Return) {
            enters += 1;
        }
        agent.step(input, FRAME)
    });
    drop(tx);
    let answered = results(&server.join().unwrap());
    let text = reply_text(&answered);
    assert!(text.starts_with("Selecting row "), "{text}");
    assert!(text.contains("How to play"), "{text}");
    assert!(downs >= 1, "arrowed down to it");
    assert_eq!(enters, 1, "and pressed Enter once");
}

#[test]
fn select_names_the_rows_when_nothing_matches() {
    let mut app = TestApp::new();
    let (tx, server, mut agent) = wake(call(1, "select", r#"{"label":"no such row"}"#));
    app.run_with_player_input(Some(3), |input, _dt| agent.step(input, FRAME));
    drop(tx);
    let answered = results(&server.join().unwrap());
    assert_eq!(answered[0]["result"]["isError"], true, "{answered:?}");
    let text = reply_text(&answered);
    assert!(text.contains("The rows are:"), "{text}");
    assert!(text.contains("1. "), "{text}");
}

#[test]
fn cruise_off_the_road_is_refused_not_hung() {
    let mut app = TestApp::new();
    let (tx, server, mut agent) = wake(call(1, "cruise", r#"{"target":55}"#));
    app.run_with_player_input(Some(3), |input, _dt| agent.step(input, FRAME));
    drop(tx);
    let answered = results(&server.join().unwrap());
    assert_eq!(answered[0]["result"]["isError"], true, "{answered:?}");
    assert!(reply_text(&answered).contains("Not at the wheel"));
}

#[test]
fn cruise_targets_parse_as_a_number_the_limit_or_off() {
    let target = |args: &str| {
        let args = serde_json::from_str(args).unwrap();
        match build_command("cruise", &args) {
            Ok(Command::Cruise { target }) => Ok(target),
            Ok(_) => panic!("not a cruise command"),
            Err(text) => Err(text),
        }
    };
    assert_eq!(target(r#"{"target":55}"#), Ok(CruiseTarget::Mph(55.0)));
    assert_eq!(target(r#"{"target":"60"}"#), Ok(CruiseTarget::Mph(60.0)));
    assert_eq!(target(r#"{"target":"limit"}"#), Ok(CruiseTarget::Limit));
    assert_eq!(target(r#"{"target":"OFF"}"#), Ok(CruiseTarget::Off));
    assert!(target(r#"{"target":"fast"}"#).is_err());
    assert!(target(r#"{"target":0}"#).is_err());
    assert!(target(r#"{}"#).is_err());
}

#[test]
fn pedal_and_wait_for_refuse_a_missing_duration() {
    let args = serde_json::from_str(r#"{"key":"up"}"#).unwrap();
    assert!(build_command("pedal", &args).is_err());
    let args = serde_json::from_str(r#"{"text":"Arrived"}"#).unwrap();
    assert!(build_command("wait_for", &args).is_err());
    let args = serde_json::from_str(r#"{"label":"  "}"#).unwrap();
    assert!(build_command("select", &args).is_err());
}

#[test]
fn the_tool_list_carries_the_driving_tools() {
    let script = rpc(1, "tools/list", "{}");
    let (tx, _rx) = mpsc::channel();
    let mut out = Vec::new();
    serve_lines(Cursor::new(script), &mut out, &tx);
    let answered = results(&out);
    let names: Vec<String> = answered[0]["result"]["tools"]
        .as_array()
        .expect("tools")
        .iter()
        .map(|tool| tool["name"].as_str().unwrap_or_default().to_string())
        .collect();
    for name in ["pedal", "wait_for", "select", "cruise", "status"] {
        assert!(names.iter().any(|n| n == name), "{name} in {names:?}");
    }
}
