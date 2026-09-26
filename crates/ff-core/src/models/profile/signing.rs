//! Save signing and the packed container: the per-install HMAC key, the
//! canonical payload a signature covers, and the `.ffsave` bytes.

use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use flate2::read::ZlibDecoder;
use flate2::write::ZlibEncoder;
use flate2::Compression;
use hmac::{Hmac, Mac};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};

use super::paths::data_dir;
use super::{
    LEGACY_CONDITION_FIELDS, PROFILE_FIELDS, SAVE_MAGIC, SECRET_FILE, SIGNATURE_FIELD,
    SIGNATURE_VERSION_FIELD,
};
use crate::pyfmt::py_str_float;

/// A save file failed its integrity signature check (or cannot be decoded).
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
#[error("{0}")]
pub struct ProfileIntegrityError(pub String);

/// Where the signing key lives: `data_dir()/profile.key`.
pub fn secret_path() -> PathBuf {
    data_dir().join(SECRET_FILE)
}

/// Thirty-two bytes nobody can guess ahead of time.
///
/// There is no `getrandom` in the dependency tree, so this mixes the
/// standard library's OS-seeded SipHash keys (`RandomState`, which the
/// platform seeds from its CSPRNG) with the clock and the process id through
/// SHA-256. Not DRM: it only has to stop casual JSON edits from silently
/// becoming trusted career state.
fn random_secret() -> [u8; 32] {
    use std::collections::hash_map::RandomState;
    use std::hash::{BuildHasher, Hasher};
    let mut digest = Sha256::new();
    for i in 0..8u64 {
        let mut hasher = RandomState::new().build_hasher();
        hasher.write_u64(i);
        digest.update(hasher.finish().to_le_bytes());
    }
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    digest.update(now.to_le_bytes());
    digest.update(std::process::id().to_le_bytes());
    let stack_address = &digest as *const _ as usize;
    digest.update(stack_address.to_le_bytes());
    digest.finalize().into()
}

/// Per-install save signing key, read from (or created at) `path`.
///
/// This is not DRM: local users can ultimately control local files. It stops
/// casual JSON edits from silently becoming trusted career state.
pub fn profile_secret_at(path: &Path) -> Vec<u8> {
    if let Ok(text) = std::fs::read_to_string(path) {
        if let Ok(bytes) = hex::decode(text.trim()) {
            return bytes;
        }
    }
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let secret = random_secret();
    let tmp = path.with_extension("tmp");
    if std::fs::write(&tmp, hex::encode(secret)).is_ok() {
        let _ = std::fs::rename(&tmp, path);
    }
    secret.to_vec()
}

/// `_profile_secret()`: this install's signing key.
pub fn profile_secret() -> Vec<u8> {
    profile_secret_at(&secret_path())
}

/// `_signed_payload(data, signature_version)`: the keys a signature of that
/// version covers, sorted.
///
/// v3 signs every key the file actually carries, so a code-side field rename
/// or removal can never invalidate a stored signature again. The older
/// versions signed the dataclass field set of their day and must be validated
/// against that day's set, not today's: dropping road_grime_pct from the class
/// (2026-07-20) silently changed the v2 payload and falsely flagged every save
/// signed before it. Removing a field while any v2 saves remain in the wild
/// means adding it to the v2 set below.
pub fn signed_payload(data: &Map<String, Value>, signature_version: i64) -> Vec<(&str, &Value)> {
    let mut keys: Vec<&str> = if signature_version >= 3 {
        data.keys()
            .map(String::as_str)
            .filter(|k| *k != SIGNATURE_FIELD && *k != SIGNATURE_VERSION_FIELD)
            .collect()
    } else {
        let mut allowed: Vec<&str> = PROFILE_FIELDS.to_vec();
        allowed.push("version");
        if signature_version == 2 {
            // Fields signed by v2-era code that have since left the dataclass.
            allowed.push("road_grime_pct");
        }
        if signature_version < 2 {
            // v1 saves signed the flat condition fields, before per-truck
            // conditions replaced them. Validate against that older field set so a
            // legitimately signed v1 save is not quarantined on first load.
            allowed.retain(|k| *k != "truck_conditions");
            allowed.extend_from_slice(LEGACY_CONDITION_FIELDS);
        }
        allowed.sort_unstable();
        allowed.dedup();
        allowed
            .into_iter()
            .filter(|k| data.contains_key(*k))
            .collect()
    };
    keys.sort_unstable();
    keys.into_iter()
        .map(|k| (k, data.get(k).expect("key came from the map")))
        .collect()
}

/// Python `json.dumps(value, sort_keys=True, separators=(",", ":"),
/// ensure_ascii=True)` -- the bytes a signature is computed over.
pub fn py_json_dumps_compact(value: &Value, out: &mut String) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(n) => {
            if n.is_f64() {
                out.push_str(&py_float_repr(n.as_f64().unwrap_or(0.0)));
            } else {
                out.push_str(&n.to_string());
            }
        }
        Value::String(s) => py_json_string(s, out),
        Value::Array(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                py_json_dumps_compact(item, out);
            }
            out.push(']');
        }
        Value::Object(map) => {
            out.push('{');
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort_unstable();
            for (i, key) in keys.into_iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                py_json_string(key, out);
                out.push(':');
                py_json_dumps_compact(&map[key], out);
            }
            out.push('}');
        }
    }
}

/// `float.__repr__` as `json.dumps` writes it (`NaN`/`Infinity` spellings).
fn py_float_repr(f: f64) -> String {
    if f.is_nan() {
        return "NaN".to_string();
    }
    if f.is_infinite() {
        return if f > 0.0 { "Infinity" } else { "-Infinity" }.to_string();
    }
    py_str_float(f)
}

/// `json.dumps` string escaping with `ensure_ascii=True`.
fn py_json_string(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0c}' => out.push_str("\\f"),
            c if !(' '..='~').contains(&c) => {
                let mut buf = [0u16; 2];
                for unit in c.encode_utf16(&mut buf) {
                    out.push_str(&format!("\\u{unit:04x}"));
                }
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

/// `_signature_for(data, signature_version)` with an explicit key.
pub fn signature_for_with_secret(
    data: &Map<String, Value>,
    signature_version: Option<i64>,
    secret: &[u8],
) -> String {
    let signature_version = signature_version.unwrap_or_else(|| {
        data.get(SIGNATURE_VERSION_FIELD)
            .and_then(Value::as_i64)
            .unwrap_or(1)
    });
    let mut payload = String::from("{");
    for (i, (key, value)) in signed_payload(data, signature_version)
        .into_iter()
        .enumerate()
    {
        if i > 0 {
            payload.push(',');
        }
        py_json_string(key, &mut payload);
        payload.push(':');
        py_json_dumps_compact(value, &mut payload);
    }
    payload.push('}');
    let mut mac = Hmac::<Sha256>::new_from_slice(secret).expect("HMAC accepts any key length");
    mac.update(payload.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

/// `_signature_for(data, signature_version=None)` with this install's key.
pub fn signature_for(data: &Map<String, Value>, signature_version: Option<i64>) -> String {
    signature_for_with_secret(data, signature_version, &profile_secret())
}

/// `_is_signature_valid(data)`.
pub fn is_signature_valid(data: &Map<String, Value>) -> bool {
    let Some(Value::String(signature)) = data.get(SIGNATURE_FIELD) else {
        return false;
    };
    let expected = signature_for(data, None);
    constant_time_eq(signature.as_bytes(), expected.as_bytes())
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

/// Pack an already-signed profile dict into the on-disk container form.
pub fn encode_save_bytes(data: &Map<String, Value>) -> Vec<u8> {
    let text = serde_json::to_string_pretty(&Value::Object(data.clone()))
        .expect("a profile dict serialises");
    let mut encoder = ZlibEncoder::new(Vec::new(), Compression::default());
    encoder
        .write_all(text.as_bytes())
        .expect("writing into a Vec cannot fail");
    let packed = encoder.finish().expect("zlib finishes");
    let mut out = SAVE_MAGIC.to_vec();
    out.extend_from_slice(&packed);
    out
}

/// Parse container or legacy plain-JSON save bytes.
///
/// Returns the profile dict and whether the bytes were a packed container.
/// Errors for bytes that cannot be decoded at all.
pub fn decode_save_bytes(raw: &[u8]) -> Result<(Map<String, Value>, bool), ProfileIntegrityError> {
    let damaged = || ProfileIntegrityError("Save file is damaged and could not be read.".into());
    let packed = raw.starts_with(SAVE_MAGIC);
    let text = if packed {
        let mut decoder = ZlibDecoder::new(&raw[SAVE_MAGIC.len()..]);
        let mut bytes = Vec::new();
        decoder.read_to_end(&mut bytes).map_err(|_| damaged())?;
        String::from_utf8(bytes).map_err(|_| damaged())?
    } else {
        String::from_utf8(raw.to_vec()).map_err(|_| damaged())?
    };
    let data: Value = serde_json::from_str(&text).map_err(|_| damaged())?;
    match data {
        Value::Object(map) => Ok((map, packed)),
        _ => Err(ProfileIntegrityError(
            "Save file is not a profile object.".into(),
        )),
    }
}

/// `_sanitized_stem(name)`: a file-system-safe stem, `"Driver"` when empty.
pub fn sanitized_stem(name: &str) -> String {
    let safe: String = name
        .chars()
        .map(|c| {
            if c.is_alphanumeric() || c == ' ' || c == '-' || c == '_' {
                c
            } else {
                '_'
            }
        })
        .collect();
    let safe = safe.trim();
    if safe.is_empty() {
        "Driver".to_string()
    } else {
        safe.to_string()
    }
}

/// Move an unreadable save aside: `X.ffsave` -> `X.ffsave.invalid`
/// (`.invalid1`, `.invalid2`, ... when that exists already).
pub fn quarantine(path: &Path) -> std::io::Result<PathBuf> {
    let base = path.as_os_str().to_string_lossy().to_string();
    let mut target = PathBuf::from(format!("{base}.invalid"));
    let mut n = 1;
    while target.exists() {
        target = PathBuf::from(format!("{base}.invalid{n}"));
        n += 1;
    }
    std::fs::rename(path, &target)?;
    Ok(target)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn canonical_json_matches_python_json_dumps() {
        let value =
            json!({"b": 1, "a": [1.5, 2.0, true, null, "x\u{e9}\n"], "c": {"z": 0, "y": 1e16}});
        let mut out = String::new();
        py_json_dumps_compact(&value, &mut out);
        assert_eq!(
            out,
            r#"{"a":[1.5,2.0,true,null,"x\u00e9\n"],"b":1,"c":{"y":1e+16,"z":0}}"#
        );
    }

    #[test]
    fn signatures_are_stable_and_version_aware() {
        let secret = [7u8; 32];
        let mut data = Map::new();
        data.insert("name".into(), json!("Driver"));
        data.insert("money".into(), json!(5000.0));
        data.insert("mystery".into(), json!(1));
        data.insert(SIGNATURE_VERSION_FIELD.into(), json!(3));
        let v3 = signature_for_with_secret(&data, None, &secret);
        assert_eq!(v3, signature_for_with_secret(&data, Some(3), &secret));
        // v2 ignores keys outside the dataclass, v3 signs them.
        let v2 = signature_for_with_secret(&data, Some(2), &secret);
        data.remove("mystery");
        assert_eq!(v2, signature_for_with_secret(&data, Some(2), &secret));
        assert_ne!(v3, signature_for_with_secret(&data, Some(3), &secret));
        assert_eq!(v3.len(), 64);
    }

    #[test]
    fn container_round_trips_and_rejects_garbage() {
        let mut data = Map::new();
        data.insert("name".into(), json!("Packed"));
        let bytes = encode_save_bytes(&data);
        assert!(bytes.starts_with(SAVE_MAGIC));
        let (back, packed) = decode_save_bytes(&bytes).unwrap();
        assert!(packed);
        assert_eq!(back, data);
        let (legacy, packed) = decode_save_bytes(br#"{"name": "Plain"}"#).unwrap();
        assert!(!packed);
        assert_eq!(legacy["name"], "Plain");
        assert!(decode_save_bytes(&[SAVE_MAGIC, b"not deflate data"].concat()).is_err());
        assert!(decode_save_bytes(b"[1, 2]").is_err());
        assert!(decode_save_bytes(b"{not json").is_err());
    }

    #[test]
    fn stems_are_filesystem_safe() {
        assert_eq!(
            sanitized_stem("Sketchy/Name<>:\"|?*"),
            "Sketchy_Name_______"
        );
        assert_eq!(sanitized_stem("   "), "Driver");
        assert_eq!(sanitized_stem("Driver A"), "Driver A");
    }
}
