//! Release notes as speakable lines.

use once_cell::sync::Lazy;
use regex::Regex;

static HEADING: Lazy<Regex> = Lazy::new(|| Regex::new(r"^#{1,6}\s+").unwrap());
static BULLET: Lazy<Regex> = Lazy::new(|| Regex::new(r"^[-*+]\s+").unwrap());
static LINK: Lazy<Regex> = Lazy::new(|| Regex::new(r"\[([^\]]+)\]\([^)]*\)").unwrap());
static EMPHASIS: Lazy<Regex> = Lazy::new(|| Regex::new(r"(\*\*|__|\*|_|`)").unwrap());

/// Release-notes markdown as plain, speakable lines.
pub fn flatten_markdown(body: Option<&str>) -> Vec<String> {
    let mut lines = Vec::new();
    for raw in body.unwrap_or("").lines() {
        let line = raw.trim();
        if line.is_empty() || line.chars().all(|c| matches!(c, '-' | '=' | '*' | '_')) {
            continue;
        }
        let line = HEADING.replace(line, ""); // headings
        let line = BULLET.replace(&line, ""); // bullets
        let line = LINK.replace_all(&line, "$1"); // links
        let line = EMPHASIS.replace_all(&line, ""); // emphasis/code
        if !line.is_empty() {
            lines.push(line.into_owned());
        }
    }
    lines
}
