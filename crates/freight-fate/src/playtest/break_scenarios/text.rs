//! Reading numbers back out of spoken lines.
//!
//! Python's scenarios pulled these with `re.search`. The battery is the only
//! caller and every pattern is a literal prefix followed by a number, so
//! these are substring walks rather than a regex dependency -- and they read
//! the same way at the call site.

/// `(\d+) percent` off the front of `text`.
pub fn leading_percent(text: &str) -> Option<f64> {
    let digits: String = text.chars().take_while(char::is_ascii_digit).collect();
    if digits.is_empty() {
        return None;
    }
    if !text[digits.len()..].starts_with(" percent") {
        return None;
    }
    digits.parse().ok()
}

/// `r"damage, now (\d+) percent|Damage (\d+) percent"`.
pub fn spoken_damage_percent(line: &str) -> Option<f64> {
    for prefix in ["damage, now ", "Damage "] {
        if let Some((_, rest)) = line.split_once(prefix) {
            if let Some(number) = leading_percent(rest) {
                return Some(number);
            }
        }
    }
    None
}

/// The first `-?[\d,]+` after `prefix` anywhere in `text`, comma groups
/// removed -- the Python `float(m.group(1).replace(",", ""))`.
pub fn grouped_number_after(text: &str, prefix: &str) -> Option<f64> {
    let (_, rest) = text.split_once(prefix)?;
    let mut digits = String::new();
    for ch in rest.chars() {
        match ch {
            '-' if digits.is_empty() => digits.push('-'),
            ',' if !digits.is_empty() => {}
            _ if ch.is_ascii_digit() => digits.push(ch),
            _ => break,
        }
    }
    if digits.is_empty() || digits == "-" {
        return None;
    }
    digits.parse().ok()
}
