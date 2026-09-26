//! The port reads a save the Python game actually wrote.
//!
//! There is no Python original for this module. Every other signing test
//! here signs with Rust and verifies with Rust, which cannot notice the two
//! sides disagreeing: on 2026-08-23 a career created and played entirely in
//! the Python 1.9 game was greeted by the Rust build with "this save was
//! changed outside the game, or copied from another computer", and the flag
//! that sets is sticky and follows the driver into profile sharing. Python
//! agreed the file was validly signed; the port's verifier did not, because
//! serde_json's default float parser landed one ulp away from `float()` on a
//! sixteen-digit duty-log hour, and the signature is an HMAC over those
//! numbers rendered back to text.
//!
//! So the fixture is bytes nobody in this crate produced: a real career,
//! with the driver's name replaced, re-signed by the shipped Python
//! `_signature_for` with the fixed key beside it. See
//! `tests/gen_python_signed_save.py`.

use super::tests::with_data_dir;
use super::*;

/// The save Python signed, and the key it signed it with.
const PYTHON_SAVE: &str = include_str!("../../../tests/python_signed_save.json");
const PYTHON_KEY: &str = include_str!("../../../tests/python_signed_save.key");

fn fixture() -> (Map<String, Value>, Vec<u8>) {
    let (data, packed) =
        decode_save_bytes(PYTHON_SAVE.as_bytes()).expect("the fixture is a readable save");
    assert!(!packed, "the fixture is checked in as reviewable JSON text");
    let secret = hex::decode(PYTHON_KEY.trim()).expect("the fixture key is hex");
    (data, secret)
}

/// The whole point: what Python signed, the port accepts.
#[test]
fn a_save_python_signed_verifies_here() {
    let (data, secret) = fixture();
    let stored = data
        .get(SIGNATURE_FIELD)
        .and_then(Value::as_str)
        .expect("the fixture carries a signature");
    assert_eq!(
        signature_for_with_secret(&data, None, &secret),
        stored,
        "the port disagrees with Python about a save Python signed -- the \
         canonical payload it hashes has drifted from json.dumps(..., \
         sort_keys=True, separators=(',', ':'), ensure_ascii=True)"
    );
}

/// ...and the other direction: re-writing it here does not change a number,
/// so a save the port hands back is still one Python will accept.
#[test]
fn rewriting_that_save_here_keeps_every_number() {
    let (data, secret) = fixture();
    let (round_tripped, packed) =
        decode_save_bytes(&encode_save_bytes(&data)).expect("the container round trips");
    assert!(packed);
    assert_eq!(
        round_tripped, data,
        "packing and re-reading the save changed a value"
    );
    let stored = data.get(SIGNATURE_FIELD).and_then(Value::as_str).unwrap();
    assert_eq!(
        signature_for_with_secret(&round_tripped, None, &secret),
        stored
    );
}

/// End to end through the load gate: no false "changed outside the game".
#[test]
fn loading_that_save_does_not_flag_the_career() {
    with_data_dir(|_| {
        let key_path = signing::secret_path();
        std::fs::create_dir_all(key_path.parent().expect("a parent")).unwrap();
        std::fs::write(&key_path, PYTHON_KEY.trim()).unwrap();
        let path = profiles_dir().join("Fixture Driver.ffsave");
        std::fs::create_dir_all(path.parent().expect("a parent")).unwrap();
        std::fs::write(&path, PYTHON_SAVE).unwrap();

        let profile = Profile::load_with(&path, false).expect("the fixture career loads");
        assert!(
            !profile.integrity_modified,
            "a legitimately signed Python save was marked as modified"
        );
        assert!(!profile.integrity_notice_pending);

        // The gate re-saves the legacy plain-JSON shape as a packed
        // container; loading that back must stay clean too.
        let reloaded = Profile::load_with(&path, false).expect("the resaved career loads");
        assert!(!reloaded.integrity_modified);
        assert!(!reloaded.integrity_notice_pending);
    });
}

/// Why the fixture bites: JSON numbers this long are the ordinary output of
/// a played career, and reading them has to be correctly rounded, exactly as
/// `float()` is on the Python side. serde_json is only that with the
/// `float_roundtrip` feature on; without it the significand is converted to
/// f64 before being scaled, and anything past fifteen significant digits can
/// come back one ulp off.
#[test]
fn long_json_decimals_parse_to_the_same_float_python_reads() {
    // Real duty-log and fatigue values out of the fixture career.
    let literals = [
        "9.171009505452611",
        "6.165700377603232",
        "25.49609033947063",
        "221.7051333866611",
        "585.446366220797",
        "83.05402031629463",
        "772.0070000000001",
        "1.0862762756489799",
    ];
    for literal in literals {
        let (data, _) = decode_save_bytes(format!(r#"{{"n":{literal}}}"#).as_bytes()).unwrap();
        let parsed = data["n"].as_f64().expect("a float");
        let exact: f64 = literal.parse().expect("Rust parses its own literals");
        assert_eq!(
            parsed.to_bits(),
            exact.to_bits(),
            "reading {literal} out of JSON lost a bit -- is serde_json's \
             float_roundtrip feature still on in the workspace Cargo.toml?"
        );
        assert_eq!(crate::pyfmt::py_str_float(parsed), literal);
    }
}
