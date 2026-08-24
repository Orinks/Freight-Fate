//! Python-value shims for the JSON loaders: `str()`, `float()`, `int()`,
//! `bool()` and `repr()` over a `serde_json::Value`, plus the `raw.get(key,
//! default)` helpers the validating parsers lean on, so a parse reads the
//! same way it did in Python.

use serde_json::{Map, Value};

use crate::data::world_models::DataError;
use crate::pyfmt::py_str_float;

// ---------------------------------------------------------------- Python shims

/// Python `repr()` of a str: single quotes unless the text holds a single
/// quote and no double quote.
pub fn py_repr_str(text: &str) -> String {
    let quote = if text.contains('\'') && !text.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::with_capacity(text.len() + 2);
    out.push(quote);
    for ch in text.chars() {
        match ch {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// Python `repr()` of a list of strings: `['a', 'b']`.
pub fn py_repr_list(items: &[String]) -> String {
    format!(
        "[{}]",
        items
            .iter()
            .map(|s| py_repr_str(s))
            .collect::<Vec<_>>()
            .join(", ")
    )
}

/// Python `repr()` of a JSON value.
pub fn py_repr_value(value: &Value) -> String {
    match value {
        Value::Null => "None".to_string(),
        Value::Bool(true) => "True".to_string(),
        Value::Bool(false) => "False".to_string(),
        Value::Number(n) => py_str_number(n),
        Value::String(s) => py_repr_str(s),
        Value::Array(items) => format!(
            "[{}]",
            items
                .iter()
                .map(py_repr_value)
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Value::Object(map) => format!(
            "{{{}}}",
            map.iter()
                .map(|(k, v)| format!("{}: {}", py_repr_str(k), py_repr_value(v)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    }
}

fn py_str_number(n: &serde_json::Number) -> String {
    if let Some(i) = n.as_i64() {
        i.to_string()
    } else if let Some(u) = n.as_u64() {
        u.to_string()
    } else {
        py_str_float(n.as_f64().unwrap_or(f64::NAN))
    }
}

/// Python `str()` of a JSON value (`str(None)` is "None", like Python).
pub fn py_str(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        Value::Number(n) => py_str_number(n),
        _ => py_repr_value(value),
    }
}

/// Python truthiness of a JSON value.
pub fn py_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(items) => !items.is_empty(),
        Value::Object(map) => !map.is_empty(),
    }
}

/// Python `float(value)`.
pub fn py_float(value: &Value) -> Result<f64, DataError> {
    match value {
        Value::Number(n) => n
            .as_f64()
            .ok_or_else(|| DataError::value(format!("could not convert {n} to float"))),
        Value::Bool(b) => Ok(if *b { 1.0 } else { 0.0 }),
        Value::String(s) => s.trim().parse::<f64>().map_err(|_| {
            DataError::value(format!(
                "could not convert string to float: {}",
                py_repr_str(s)
            ))
        }),
        other => Err(DataError::value(format!(
            "float() argument must be a string or a real number, not {}",
            py_type_name(other)
        ))),
    }
}

/// Python `int(value)` (truncating a float toward zero).
pub fn py_int_of(value: &Value) -> Result<i64, DataError> {
    match value {
        Value::Number(n) => n
            .as_i64()
            .or_else(|| n.as_f64().map(|f| f.trunc() as i64))
            .ok_or_else(|| DataError::value(format!("could not convert {n} to int"))),
        Value::Bool(b) => Ok(i64::from(*b)),
        Value::String(s) => s.trim().parse::<i64>().map_err(|_| {
            DataError::value(format!(
                "invalid literal for int() with base 10: {}",
                py_repr_str(s)
            ))
        }),
        other => Err(DataError::value(format!(
            "int() argument must be a string, a bytes-like object or a real number, not {}",
            py_type_name(other)
        ))),
    }
}

fn py_type_name(value: &Value) -> &'static str {
    match value {
        Value::Null => "'NoneType'",
        Value::Bool(_) => "'bool'",
        Value::Number(_) => "'float'",
        Value::String(_) => "'str'",
        Value::Array(_) => "'list'",
        Value::Object(_) => "'dict'",
    }
}

/// `str(raw.get(key, "")).strip()`.
pub fn get_str(raw: &Map<String, Value>, key: &str) -> String {
    raw.get(key)
        .map(py_str)
        .unwrap_or_default()
        .trim()
        .to_string()
}

/// `str(raw.get(key, ""))` without the strip.
pub fn get_str_raw(raw: &Map<String, Value>, key: &str) -> String {
    raw.get(key).map(py_str).unwrap_or_default()
}

/// `float(raw.get(key, default))`.
pub fn get_float(raw: &Map<String, Value>, key: &str, default: f64) -> Result<f64, DataError> {
    match raw.get(key) {
        None => Ok(default),
        Some(v) => py_float(v),
    }
}

/// `float(raw[key])` -- a missing key is Python's `KeyError`.
pub fn req_float(raw: &Map<String, Value>, key: &str) -> Result<f64, DataError> {
    match raw.get(key) {
        None => Err(DataError::key(py_repr_str(key))),
        Some(v) => py_float(v),
    }
}

/// `int(raw.get(key, default))`.
pub fn get_int(raw: &Map<String, Value>, key: &str, default: i64) -> Result<i64, DataError> {
    match raw.get(key) {
        None => Ok(default),
        Some(v) => py_int_of(v),
    }
}

/// `bool(raw.get(key, default))`.
pub fn get_bool(raw: &Map<String, Value>, key: &str, default: bool) -> bool {
    raw.get(key).map(py_truthy).unwrap_or(default)
}

/// `tuple(str(x).strip() for x in raw.get(key, ()) if str(x).strip())`.
pub fn get_str_list(raw: &Map<String, Value>, key: &str) -> Vec<String> {
    get_str_list_unfiltered(raw, key)
        .into_iter()
        .filter(|s| !s.is_empty())
        .collect()
}

/// `tuple(str(x).strip() for x in raw.get(key, ()))` -- empties kept.
pub fn get_str_list_unfiltered(raw: &Map<String, Value>, key: &str) -> Vec<String> {
    match raw.get(key) {
        Some(Value::Array(items)) => items.iter().map(|v| py_str(v).trim().to_string()).collect(),
        Some(Value::String(s)) => s
            .chars()
            .map(|c| c.to_string().trim().to_string())
            .collect(),
        _ => Vec::new(),
    }
}

/// The `Map` behind an object value, or `None` for any other JSON type.
pub fn as_object(value: &Value) -> Option<&Map<String, Value>> {
    value.as_object()
}

/// Iterate a corridor list field (`corridor.get(key, ())`).
pub fn list_field<'a>(raw: &'a Map<String, Value>, key: &str) -> &'a [Value] {
    match raw.get(key) {
        Some(Value::Array(items)) => items,
        _ => &[],
    }
}
