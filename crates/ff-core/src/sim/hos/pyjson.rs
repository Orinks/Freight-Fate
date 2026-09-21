//! The Python coercions the tolerant save loaders lean on.
//!
//! `HosClock.from_dict` and friends accept whatever an old or hand-edited
//! save carries and either coerce it the way `float(...)` / `str(...)` would
//! or give up on the whole record (a `TypeError`/`ValueError` in Python).
//! These helpers reproduce those coercions over `serde_json::Value` so the
//! "fresh clock on garbage" rule keeps the same edges it had in Python.

use serde_json::Value;

use crate::pyfmt::py_str_float;

/// Python `float(value)` for a JSON value: numbers as they are, `True`/
/// `False` as 1/0 (bool is an int subclass), numeric strings parsed the way
/// `float(str)` parses them, and `None` for anything that would raise.
pub(super) fn py_float(value: &Value) -> Option<f64> {
    match value {
        Value::Number(n) => n.as_f64(),
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        Value::String(s) => py_float_str(s),
        _ => None,
    }
}

/// `float(data.get(key, default))`: a missing key is the default, a present
/// one must coerce or the caller's record is unreadable.
pub(super) fn py_float_or(value: Option<&Value>, default: f64) -> Option<f64> {
    match value {
        None => Some(default),
        Some(v) => py_float(v),
    }
}

/// Python `float(str)`: surrounding whitespace stripped, `inf`/`nan` in any
/// case with an optional sign, exponents, and PEP 515 underscores between
/// digits. Anything else is a `ValueError` (`None` here).
pub(super) fn py_float_str(text: &str) -> Option<f64> {
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return None;
    }
    let cleaned: String = if trimmed.contains('_') {
        let bytes = trimmed.as_bytes();
        for (i, b) in bytes.iter().enumerate() {
            if *b == b'_' {
                let before = i > 0 && bytes[i - 1].is_ascii_digit();
                let after = i + 1 < bytes.len() && bytes[i + 1].is_ascii_digit();
                if !(before && after) {
                    return None;
                }
            }
        }
        trimmed.chars().filter(|c| *c != '_').collect()
    } else {
        trimmed.to_string()
    };
    // Rust's grammar matches Python's on the rest: optional sign, digits with
    // an optional point on either side, an exponent, or inf/infinity/nan in
    // any case. Neither accepts hex, a bare point, or a trailing exponent.
    cleaned.parse::<f64>().ok()
}

/// Python `str(value)` for a JSON value.
pub(super) fn py_str(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        _ => py_repr(value),
    }
}

/// Python `str(data.get(key, default))`.
pub(super) fn py_str_or(value: Option<&Value>, default: &str) -> String {
    match value {
        None => default.to_string(),
        Some(v) => py_str(v),
    }
}

/// Python `repr(value)` for a JSON value: the same as `str` except that
/// strings are quoted, which matters inside lists and dicts.
pub(super) fn py_repr(value: &Value) -> String {
    match value {
        Value::Null => "None".to_string(),
        Value::Bool(true) => "True".to_string(),
        Value::Bool(false) => "False".to_string(),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                i.to_string()
            } else if let Some(u) = n.as_u64() {
                u.to_string()
            } else {
                py_str_float(n.as_f64().unwrap_or(f64::NAN))
            }
        }
        Value::String(s) => py_repr_str(s),
        Value::Array(items) => {
            let parts: Vec<String> = items.iter().map(py_repr).collect();
            format!("[{}]", parts.join(", "))
        }
        Value::Object(map) => {
            let parts: Vec<String> = map
                .iter()
                .map(|(k, v)| format!("{}: {}", py_repr_str(k), py_repr(v)))
                .collect();
            format!("{{{}}}", parts.join(", "))
        }
    }
}

/// Python `repr(str)`: single quotes unless the text holds a single quote
/// and no double quote, backslash escapes for the quote, backslashes and
/// control characters.
pub(super) fn py_repr_str(text: &str) -> String {
    let quote = if text.contains('\'') && !text.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::with_capacity(text.len() + 2);
    out.push(quote);
    for c in text.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if (c as u32) < 0x20 || c as u32 == 0x7f => {
                out.push_str(&format!("\\x{:02x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// Python truthiness of a JSON value (`value or fallback`).
pub(super) fn py_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(items) => !items.is_empty(),
        Value::Object(map) => !map.is_empty(),
    }
}

/// `for item in data.get(key, [])`: a missing key iterates nothing, a list
/// its items, a string its characters, a dict its keys; a number, bool or
/// `None` raises `TypeError` (`None` here).
pub(super) fn py_iter(value: Option<&Value>) -> Option<Vec<Value>> {
    match value {
        None => Some(Vec::new()),
        Some(Value::Array(items)) => Some(items.clone()),
        Some(Value::String(s)) => Some(s.chars().map(|c| Value::String(c.to_string())).collect()),
        Some(Value::Object(map)) => Some(map.keys().map(|k| Value::String(k.clone())).collect()),
        Some(_) => None,
    }
}

/// Python `max(a, b)`: `b` only when it is strictly greater, so a NaN or a
/// negative zero on the right never wins.
pub(super) fn py_max(a: f64, b: f64) -> f64 {
    if b > a {
        b
    } else {
        a
    }
}

/// Python `min(a, b)`: `b` only when it is strictly smaller.
pub(super) fn py_min(a: f64, b: f64) -> f64 {
    if b < a {
        b
    } else {
        a
    }
}
