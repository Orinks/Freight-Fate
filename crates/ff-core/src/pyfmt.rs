//! Python number formatting, reproduced exactly.
//!
//! Spoken strings are asserted verbatim by the ported test suite, and the
//! Python game built them with `round()`, f-string precision specifiers,
//! thousands grouping and `str(float)`. Rust's own formatting agrees with
//! Python on the hard part -- `{:.N}` is correctly rounded, half-to-even on
//! exact ties, same as CPython's `%.Nf` -- but differs at the edges: `{}` on
//! an f64 is shortest-round-trip without Python's exponent rules or the
//! trailing `.0`, `NaN` is capitalised, and there is no grouping flag. Every
//! helper here is pinned against a fixture table CPython itself generated
//! (`tests/gen_pyfmt_fixtures.py` -> `tests/pyfmt_fixtures.json`).
//!
//! There is no Python original for this module.

/// Python `round(x)` as a float: round half to even.
///
/// Python's `round()` with no `ndigits` returns an `int`, so a result of
/// `-0.0` here prints as `0` there. Format with [`round_py_int`] (or cast)
/// where the Python code rounded and then printed the integer.
pub fn round_py(x: f64) -> f64 {
    x.round_ties_even()
}

/// Python `round(x)` as the integer it actually returns (saturating for
/// non-finite input, where Python would raise).
pub fn round_py_int(x: f64) -> i64 {
    x.round_ties_even() as i64
}

// CPython's `float.__round__` short-circuits outside this range of ndigits:
// above it the value is already exact at that precision, below it nothing
// survives but the sign of zero.
const NDIGITS_MAX: i32 = 323;
const NDIGITS_MIN: i32 = -308;

/// Python `round(x, ndigits)`: correctly rounded decimal, half to even on an
/// exact tie of the binary value, for any integer `ndigits`.
pub fn round_py_n(x: f64, ndigits: i32) -> f64 {
    if !x.is_finite() {
        return x;
    }
    if ndigits > NDIGITS_MAX {
        return x;
    }
    if ndigits < NDIGITS_MIN {
        return 0.0 * x;
    }
    if ndigits >= 0 {
        // Rust's precision formatting is exact (Dragon4 on the full binary
        // expansion) with ties to even, which is what CPython's dtoa mode 3
        // does; the round trip through text is the rounding.
        return format!("{:.*}", ndigits as usize, x)
            .parse()
            .expect("a formatted f64 parses back");
    }
    round_negative_digits(x, (-ndigits) as usize)
}

/// `round(x, -k)`: round to a multiple of 10^k, half to even, exactly.
///
/// Done on the exact decimal digits rather than by dividing by a power of
/// ten, because `x / 10^k` is not exact and a tie -- 25 to the nearest ten,
/// 2.5e20 to the nearest 1e20 -- would be decided by the division error
/// instead of by the even rule.
fn round_negative_digits(x: f64, k: usize) -> f64 {
    let negative = x.is_sign_negative();
    let magnitude = x.abs();
    let int_part = magnitude.trunc();
    let frac_nonzero = magnitude - int_part != 0.0;
    // An integral f64 formats to its exact digits at precision 0.
    let digits = format!("{int_part:.0}");
    let digits = digits.as_bytes();
    let len = digits.len();
    let (head, tail): (&[u8], Vec<u8>) = if len > k {
        (&digits[..len - k], digits[len - k..].to_vec())
    } else {
        let mut padded = vec![b'0'; k - len];
        padded.extend_from_slice(digits);
        (&[][..], padded)
    };
    // Compare the dropped digits (plus any fraction) against one half.
    let first = tail[0];
    let rest_nonzero = tail[1..].iter().any(|&d| d != b'0') || frac_nonzero;
    let round_up = match first {
        b'0'..=b'4' => false,
        b'5' if rest_nonzero => true,
        b'5' => {
            // Exact tie: to even on the last kept digit.
            let last = head.last().copied().unwrap_or(b'0');
            (last - b'0') % 2 == 1
        }
        _ => true,
    };
    let mut kept: Vec<u8> = if head.is_empty() {
        vec![b'0']
    } else {
        head.to_vec()
    };
    if round_up {
        let mut i = kept.len();
        loop {
            if i == 0 {
                kept.insert(0, b'1');
                break;
            }
            i -= 1;
            if kept[i] == b'9' {
                kept[i] = b'0';
            } else {
                kept[i] += 1;
                break;
            }
        }
    }
    let mut text = String::with_capacity(kept.len() + k + 1);
    if negative {
        text.push('-');
    }
    text.push_str(std::str::from_utf8(&kept).expect("ascii digits"));
    for _ in 0..k {
        text.push('0');
    }
    text.parse().expect("a decimal integer parses as f64")
}

/// Python `f"{x:.{prec}f}"`.
///
/// Rust's `{:.N}` already rounds the same way (half to even on exact ties:
/// `0.5` -> `"0"`, `2.5` -> `"2"`, `0.25` at one place -> `"0.2"`) and keeps
/// the sign of a negative value that rounds to zero (`-0.4` -> `"-0"`, and
/// `-0.0` itself -> `"-0"`), both exactly as CPython prints them. Only the
/// non-finite spellings differ.
pub fn fmt_f(x: f64, prec: usize) -> String {
    if x.is_nan() {
        return "nan".to_string();
    }
    format!("{x:.prec$}")
}

/// Python `f"{x:,.{prec}f}"`: [`fmt_f`] with thousands separators in the
/// integer part.
pub fn fmt_grouped(x: f64, prec: usize) -> String {
    let plain = fmt_f(x, prec);
    if !x.is_finite() {
        return plain;
    }
    let (sign, body) = match plain.strip_prefix('-') {
        Some(rest) => ("-", rest),
        None => ("", plain.as_str()),
    };
    let (int_part, frac_part) = match body.split_once('.') {
        Some((i, f)) => (i, Some(f)),
        None => (body, None),
    };
    let mut out = String::with_capacity(plain.len() + plain.len() / 3);
    out.push_str(sign);
    out.push_str(&group_thousands(int_part));
    if let Some(frac) = frac_part {
        out.push('.');
        out.push_str(frac);
    }
    out
}

/// Python `f"{i:,d}"`.
pub fn fmt_int_grouped(i: i64) -> String {
    let digits = i.unsigned_abs().to_string();
    let grouped = group_thousands(&digits);
    if i < 0 {
        format!("-{grouped}")
    } else {
        grouped
    }
}

fn group_thousands(digits: &str) -> String {
    let bytes = digits.as_bytes();
    let mut out = String::with_capacity(digits.len() + digits.len() / 3);
    for (index, &d) in bytes.iter().enumerate() {
        if index > 0 && (bytes.len() - index).is_multiple_of(3) {
            out.push(',');
        }
        out.push(d as char);
    }
    out
}

/// Python `int(x)`: truncation toward zero (saturating where Python raises).
pub fn py_int(x: f64) -> i64 {
    x.trunc() as i64
}

/// Split `{:e}`-style scientific text into (sign, digit string, exponent).
fn split_sci(sci: &str) -> (&'static str, String, i32) {
    let (mantissa, exp) = sci
        .split_once('e')
        .expect("LowerExp always has an exponent");
    let exp: i32 = exp.parse().expect("LowerExp exponent is an integer");
    let (sign, mantissa) = match mantissa.strip_prefix('-') {
        Some(rest) => ("-", rest),
        None => ("", mantissa),
    };
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    (sign, digits, exp)
}

/// The shortest digit string that round-trips to `x`, as CPython's `repr`
/// chooses it: (sign, digits without a point, decimal exponent of the first
/// digit).
///
/// Rust's `{:e}` is also shortest-round-trip, but when two candidates of
/// that length sit at exactly the same distance from `x` (749351580759710.25
/// at sixteen digits: "...710.2" or "...710.3") it does not break the tie to
/// even, and CPython's dtoa does. Rust's exact-precision rendering IS
/// half-to-even, so ask it for the same number of digits and prefer that
/// answer whenever it still round-trips.
fn shortest_digits(x: f64) -> (&'static str, String, i32) {
    let (sign, digits, exp) = split_sci(&format!("{x:e}"));
    if digits.len() > 1 {
        let exact = format!("{:.*e}", digits.len() - 1, x);
        if exact.parse::<f64>().is_ok_and(|back| back == x) {
            let (sign, mut exact_digits, exp) = split_sci(&exact);
            while exact_digits.len() > 1 && exact_digits.ends_with('0') {
                exact_digits.pop();
            }
            return (sign, exact_digits, exp);
        }
    }
    (sign, digits, exp)
}

/// Python `str(x)` / `repr(x)` for a float: the shortest digits that round
/// trip, positional when the decimal exponent is in `[-4, 16)` (with `.0`
/// on an integral value), otherwise `d.ddde[+-]XX` with at least two
/// exponent digits.
pub fn py_str_float(x: f64) -> String {
    if x.is_nan() {
        return "nan".to_string();
    }
    if x.is_infinite() {
        return if x < 0.0 { "-inf" } else { "inf" }.to_string();
    }
    let (sign, digits, exp) = shortest_digits(x);
    // value = 0.<digits> * 10^decpt
    let decpt = exp + 1;
    let mut out = String::from(sign);
    if decpt <= -4 || decpt > 16 {
        out.push_str(&digits[..1]);
        if digits.len() > 1 {
            out.push('.');
            out.push_str(&digits[1..]);
        }
        out.push('e');
        let e = decpt - 1;
        out.push(if e < 0 { '-' } else { '+' });
        out.push_str(&format!("{:02}", e.abs()));
    } else if decpt <= 0 {
        out.push_str("0.");
        for _ in 0..(-decpt) {
            out.push('0');
        }
        out.push_str(&digits);
    } else {
        let decpt = decpt as usize;
        if digits.len() <= decpt {
            out.push_str(&digits);
            for _ in 0..(decpt - digits.len()) {
                out.push('0');
            }
            out.push_str(".0");
        } else {
            out.push_str(&digits[..decpt]);
            out.push('.');
            out.push_str(&digits[decpt..]);
        }
    }
    out
}

/// Python `f"{i:02d}"`: two digits, zero padded (the sign counts toward the
/// width, so `-5` stays `"-5"`).
pub fn pct02(i: i64) -> String {
    format!("{i:02}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    fn fixtures() -> Value {
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/pyfmt_fixtures.json");
        let text =
            std::fs::read_to_string(path).expect("pyfmt_fixtures.json next to the generator");
        serde_json::from_str(&text).expect("valid fixture JSON")
    }

    fn f(v: &Value) -> f64 {
        v.as_str()
            .expect("floats are repr strings")
            .parse()
            .expect("repr parses")
    }

    fn same_float(a: f64, b: f64) -> bool {
        (a.is_nan() && b.is_nan()) || (a == b && a.is_sign_negative() == b.is_sign_negative())
    }

    #[test]
    fn test_round_py_is_half_to_even() {
        assert_eq!(round_py(0.5), 0.0);
        assert_eq!(round_py(1.5), 2.0);
        assert_eq!(round_py(2.5), 2.0);
        assert_eq!(round_py(-2.5), -2.0);
        assert_eq!(round_py(0.49999999999999994), 0.0);
        assert_eq!(round_py_int(-0.4), 0);
        assert_eq!(round_py_int(2.5), 2);
    }

    #[test]
    fn test_fmt_f_ties_match_python() {
        assert_eq!(fmt_f(0.5, 0), "0");
        assert_eq!(fmt_f(2.5, 0), "2");
        assert_eq!(fmt_f(1.5, 0), "2");
        assert_eq!(fmt_f(0.25, 1), "0.2");
        // CPython prints the sign of a zero result, and we match it.
        assert_eq!(fmt_f(-0.0, 0), "-0");
        assert_eq!(fmt_f(-0.4, 0), "-0");
        assert_eq!(fmt_f(f64::NAN, 2), "nan");
        assert_eq!(fmt_f(f64::INFINITY, 2), "inf");
    }

    #[test]
    fn test_round_py_n_negative_digits_are_exact_ties() {
        assert_eq!(round_py_n(25.0, -1), 20.0);
        assert_eq!(round_py_n(35.0, -1), 40.0);
        assert_eq!(round_py_n(250.0, -2), 200.0);
        assert_eq!(round_py_n(1250.0, -2), 1200.0);
        assert_eq!(round_py_n(1251.0, -2), 1300.0);
        assert_eq!(round_py_n(999.5, -3), 1000.0);
        assert!(same_float(round_py_n(-0.3, -1), -0.0));
        assert_eq!(round_py_n(2.5e20, -20), 2e20);
        assert_eq!(round_py_n(2.675, 2), 2.67);
        assert_eq!(round_py_n(0.125, 2), 0.12);
        assert_eq!(round_py_n(0.375, 2), 0.38);
    }

    #[test]
    fn test_py_str_float_rules() {
        assert_eq!(py_str_float(1e16), "1e+16");
        assert_eq!(py_str_float(1e15), "1000000000000000.0");
        assert_eq!(py_str_float(0.0001), "0.0001");
        assert_eq!(py_str_float(0.00001), "1e-05");
        assert_eq!(py_str_float(1.0), "1.0");
        assert_eq!(py_str_float(-0.0), "-0.0");
        assert_eq!(py_str_float(1.5e16), "1.5e+16");
        assert_eq!(py_str_float(5e-324), "5e-324");
        assert_eq!(py_str_float(0.1 + 0.2), "0.30000000000000004");
        assert_eq!(py_str_float(f64::NAN), "nan");
        assert_eq!(py_str_float(f64::NEG_INFINITY), "-inf");
    }

    #[test]
    fn test_grouping() {
        assert_eq!(fmt_grouped(1234567.891, 2), "1,234,567.89");
        assert_eq!(fmt_grouped(-1234567.891, 0), "-1,234,568");
        assert_eq!(fmt_grouped(999.5, 0), "1,000");
        assert_eq!(fmt_grouped(-0.0, 0), "-0");
        assert_eq!(fmt_int_grouped(0), "0");
        assert_eq!(fmt_int_grouped(-1000), "-1,000");
        assert_eq!(fmt_int_grouped(i64::MIN), "-9,223,372,036,854,775,808");
        assert_eq!(pct02(5), "05");
        assert_eq!(pct02(-5), "-5");
        assert_eq!(py_int(-2.9), -2);
    }

    #[test]
    fn test_round_py_matches_cpython_fixtures() {
        // The fixture holds Python's int: no sign on zero, exact at any size.
        for row in fixtures()["round_py"].as_array().unwrap() {
            let x = f(&row[0]);
            let want_text = row[1].as_str().unwrap();
            let want: f64 = want_text.parse().unwrap();
            let got = round_py(x);
            assert_eq!(got, want, "round({x:?}) = {got:?}, want {want:?}");
            if let Ok(want_int) = want_text.parse::<i64>() {
                assert_eq!(round_py_int(x), want_int, "int(round({x:?}))");
            }
        }
    }

    #[test]
    fn test_round_py_n_matches_cpython_fixtures() {
        for row in fixtures()["round_py_n"].as_array().unwrap() {
            let x = f(&row[0]);
            let n = row[1].as_i64().unwrap() as i32;
            let want = f(&row[2]);
            let got = round_py_n(x, n);
            assert!(
                same_float(got, want),
                "round({x:?}, {n}) = {got:?}, want {want:?}"
            );
        }
    }

    #[test]
    fn test_fmt_f_matches_cpython_fixtures() {
        for row in fixtures()["fmt_f"].as_array().unwrap() {
            let x = f(&row[0]);
            let p = row[1].as_u64().unwrap() as usize;
            let want = row[2].as_str().unwrap();
            assert_eq!(fmt_f(x, p), want, "f\"{{{x:?}:.{p}f}}\"");
        }
    }

    #[test]
    fn test_fmt_grouped_matches_cpython_fixtures() {
        for row in fixtures()["fmt_grouped"].as_array().unwrap() {
            let x = f(&row[0]);
            let p = row[1].as_u64().unwrap() as usize;
            let want = row[2].as_str().unwrap();
            assert_eq!(fmt_grouped(x, p), want, "f\"{{{x:?}:,.{p}f}}\"");
        }
    }

    #[test]
    fn test_fmt_int_grouped_matches_cpython_fixtures() {
        for row in fixtures()["fmt_int_grouped"].as_array().unwrap() {
            let i = row[0].as_i64().unwrap();
            assert_eq!(
                fmt_int_grouped(i),
                row[1].as_str().unwrap(),
                "f\"{{{i}:,d}}\""
            );
        }
    }

    #[test]
    fn test_py_int_matches_cpython_fixtures() {
        for row in fixtures()["py_int"].as_array().unwrap() {
            let x = f(&row[0]);
            assert_eq!(py_int(x), row[1].as_i64().unwrap(), "int({x:?})");
        }
    }

    #[test]
    fn test_py_str_float_matches_cpython_fixtures() {
        for row in fixtures()["py_str_float"].as_array().unwrap() {
            let x = f(&row[0]);
            assert_eq!(py_str_float(x), row[1].as_str().unwrap(), "str({x:?})");
        }
    }

    #[test]
    fn test_pct02_matches_cpython_fixtures() {
        for row in fixtures()["pct02"].as_array().unwrap() {
            let i = row[0].as_i64().unwrap();
            assert_eq!(pct02(i), row[1].as_str().unwrap(), "f\"{{{i}:02d}}\"");
        }
    }
}
