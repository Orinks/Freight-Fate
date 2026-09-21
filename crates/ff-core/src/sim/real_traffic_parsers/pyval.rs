//! Python semantics over JSON values: `dict.get` with defaults (a present
//! `null` is a value, not a miss), `str()`, truthiness and `float()`.
//!
//! Split out of `real_traffic_parsers` to keep that file under the
//! thousand-line mark.

use serde_json::{Map, Value};

use crate::pyfmt::py_str_float;

/// The value of the first PRESENT key (`d.get(a, d.get(b, ...))`), or
/// `None` when none of them is present.
pub fn chain<'a>(map: &'a Map<String, Value>, keys: &[&str]) -> Option<&'a Value> {
    keys.iter().find_map(|key| map.get(*key))
}

/// `d.get(a, d.get(b, default))` with a string default.
pub fn chain_str(map: &Map<String, Value>, keys: &[&str], default: &str) -> String {
    match chain(map, keys) {
        Some(value) => py_str(value),
        None => default.to_string(),
    }
}

/// Python truthiness of a JSON value.
pub fn truthy(value: &Value) -> bool {
    match value {
        Value::Null | Value::Bool(false) => false,
        Value::Bool(true) => true,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// Python `str()` of a JSON-decoded value: `None`, `True`/`False`,
/// int digits, float repr, the string itself. (Lists and dicts render
/// as compact JSON rather than Python repr; no feed field is one.)
pub fn py_str(value: &Value) -> String {
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
                py_str_float(n.as_f64().unwrap_or(0.0))
            }
        }
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

/// `value or ""` then `str()`: the empty string for a falsy value.
pub fn str_or_empty(value: Option<&Value>) -> String {
    match value {
        Some(v) if truthy(v) => py_str(v),
        _ => String::new(),
    }
}

/// Python `float(x)` for a JSON value: numbers, bools, and numeric
/// strings convert; anything else is a `TypeError`/`ValueError`.
pub fn to_f64(value: &Value) -> Option<f64> {
    match value {
        Value::Number(n) => n.as_f64(),
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        Value::String(s) => {
            let text = s.trim();
            match text.to_ascii_lowercase().as_str() {
                "inf" | "+inf" | "infinity" | "+infinity" => Some(f64::INFINITY),
                "-inf" | "-infinity" => Some(f64::NEG_INFINITY),
                "nan" | "+nan" | "-nan" => Some(f64::NAN),
                _ => text.replace('_', "").parse::<f64>().ok(),
            }
        }
        _ => None,
    }
}

/// Python `int(x)` for a JSON value: ints, bools, whole floats
/// (truncated), and integer strings.
pub fn to_i64(value: &Value) -> Option<i64> {
    match value {
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Some(i)
            } else {
                n.as_f64()
                    .filter(|f| f.is_finite())
                    .map(|f| f.trunc() as i64)
            }
        }
        Value::Bool(b) => Some(i64::from(*b)),
        Value::String(s) => s.trim().replace('_', "").parse::<i64>().ok(),
        _ => None,
    }
}

/// The object behind a value, or an empty one (`d.get(k, {})` read
/// through `isinstance(..., dict)`).
pub fn as_map(value: Option<&Value>) -> Option<&Map<String, Value>> {
    value.and_then(Value::as_object)
}
