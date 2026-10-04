//! Billboards that notice the drive (owner, 2026-09-30).
//!
//! The roadside pool is drawn when a trip starts, so it cannot know what the
//! drive will do. When an everyday pool sign comes up, the driving state may
//! read one of these in its place: Big Jim after a collision, a citation or an
//! out-of-service order; the church signs and all-night diners when the driver
//! is drowsy or it is the small hours; a holiday in its week. Placed
//! attraction signs never change: each one is a place.
//!
//! No line here names an exit, a distance or a service. A sign that sends a
//! driver who cannot see the road toward a stop that is not there costs the
//! drive, so each line is true on any road, on its day.

/// What happened since the last pool sign that Big Jim answers.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Incident {
    Collision,
    Citation,
    OutOfService,
}

/// A holiday whose week puts its own signs up.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Holiday {
    NewYear,
    Independence,
    Halloween,
    Thanksgiving,
    Christmas,
}

pub const COLLISION_LINES: &[&str] = &[
    "Big Jim felt that one from his office. Whatever you hit back there, one call, that's all.",
    "Hit something a few miles back? Big Jim is not saying it was your fault. Big Jim is not saying it wasn't.",
    "That new dent already has a lawyer. Big Jim Tolliver, attorney at law.",
    "Big Jim heard the crunch. Big Jim always hears the crunch.",
];

pub const CITATION_LINES: &[&str] = &[
    "Fresh ticket on the dash? Big Jim reads those for fun.",
    "Big Jim saw the trooper's lights back there. Big Jim sees all the lights. Call Big Jim.",
    "A citation is not the end of the road. It is the start of a phone call to Big Jim.",
];

pub const OUT_OF_SERVICE_LINES: &[&str] = &[
    "Parked by an inspector? Big Jim has argued with a few. He lost, but he was loud about it.",
    "Big Jim cannot fix your brakes. Big Jim can complain about the inspector, by the hour.",
];

/// Church signs and all-night diners, for the drowsy and the small hours.
pub const SMALL_HOURS_LINES: &[&str] = &[
    "Even the Lord rested on the seventh day. You could try the seventh hour.",
    "Open all night: coffee, pie, and a booth soft enough to sleep in. Nobody here will judge you.",
    "Your eyelids are heavy, and so is your load. Rest is holy too.",
    "All-night diner. The waitress has seen that face before. It looked more awake then.",
    "Sleep is a gift. Unwrap it somewhere legal.",
];

pub fn holiday_lines(holiday: Holiday) -> &'static [&'static str] {
    match holiday {
        Holiday::NewYear => &[
            "Happy New Year. Your resolution is a clean logbook. Big Jim's resolution is more clients.",
            "New Year's week. Somewhere a fireworks barn sold out of everything loud, and the dogs are already under the bed.",
        ],
        Holiday::Independence => &[
            "Happy Fourth of July. Somewhere a brother-in-law is lighting the loud ones. Mind the smoke.",
            "Independence week. Flags on every porch, and a grill going in every yard for a thousand miles.",
        ],
        Holiday::Halloween => &[
            "Halloween week. The corn mazes are open, and the scarecrows are judging your lane discipline.",
            "Happy Halloween. The scariest thing on this road is still the weigh station.",
        ],
        Holiday::Thanksgiving => &[
            "Thanksgiving week. Somewhere a turkey is grateful you are hauling freight and not him.",
            "Happy Thanksgiving. Every pie case in the country is full, and every pair of pants is worried.",
        ],
        Holiday::Christmas => &[
            "Merry Christmas. Somewhere a nativity scene has a semi in it this year. It is parked legally.",
            "Big Jim wishes you a merry Christmas. Big Jim still wants you to call.",
            "Christmas week. The freight is presents now, and every dock wants it yesterday.",
        ],
    }
}

/// Local hours the small-hours signs come out: one in the morning until five.
pub const SMALL_HOURS: std::ops::Range<f64> = 1.0..5.0;

/// The holiday whose week a calendar date falls in.
///
/// Thanksgiving is the fourth Thursday of November, which always lands
/// between the 22nd and the 28th, so its week is that span.
pub fn holiday_on(month: u32, day: u32) -> Option<Holiday> {
    match (month, day) {
        (12, 29..=31) | (1, 1) => Some(Holiday::NewYear),
        (6, 28..=30) | (7, 1..=4) => Some(Holiday::Independence),
        (10, 24..=31) => Some(Holiday::Halloween),
        (11, 22..=28) => Some(Holiday::Thanksgiving),
        (12, 10..=25) => Some(Holiday::Christmas),
        _ => None,
    }
}

/// What the drive offers a pool sign to react to.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct BillboardMoment {
    pub incident: Option<Incident>,
    /// Drowsy, or the small hours on the local clock.
    pub tired: bool,
    pub holiday: Option<Holiday>,
    /// Pool signs already heard this trip: paces the swaps and walks each
    /// pool in order, so a trip does not hear one line twice in a row.
    pub nth: usize,
}

/// The line to read in place of an everyday pool sign, or None to read it.
///
/// Big Jim answers every incident, once, at the next sign. The small hours
/// take every other sign and a holiday every third, so the ordinary roadside
/// still shows through.
pub fn dynamic_billboard(moment: BillboardMoment) -> Option<&'static str> {
    let pick = |pool: &'static [&'static str]| pool[moment.nth % pool.len()];
    if let Some(incident) = moment.incident {
        return Some(pick(match incident {
            Incident::Collision => COLLISION_LINES,
            Incident::Citation => CITATION_LINES,
            Incident::OutOfService => OUT_OF_SERVICE_LINES,
        }));
    }
    if moment.tired && moment.nth.is_multiple_of(2) {
        return Some(pick(SMALL_HOURS_LINES));
    }
    match moment.holiday {
        Some(holiday) if moment.nth.is_multiple_of(3) => Some(pick(holiday_lines(holiday))),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const HOLIDAYS: [Holiday; 5] = [
        Holiday::NewYear,
        Holiday::Independence,
        Holiday::Halloween,
        Holiday::Thanksgiving,
        Holiday::Christmas,
    ];

    fn every_line() -> Vec<&'static str> {
        let mut lines: Vec<&str> = [
            COLLISION_LINES,
            CITATION_LINES,
            OUT_OF_SERVICE_LINES,
            SMALL_HOURS_LINES,
        ]
        .concat();
        for holiday in HOLIDAYS {
            lines.extend(holiday_lines(holiday));
        }
        lines
    }

    #[test]
    fn every_line_is_speakable_and_promises_no_stop() {
        for line in every_line() {
            assert!(!line.chars().any(|c| c.is_ascii_digit()), "{line}");
            assert!(line.split_whitespace().count() <= 25, "{line}");
            let lower = line.to_lowercase();
            for claim in ["next exit", "miles ahead", "exit ", "turn off"] {
                assert!(!lower.contains(claim), "{line} names a stop");
            }
        }
    }

    #[test]
    fn holiday_weeks_cover_the_day_itself() {
        assert_eq!(holiday_on(1, 1), Some(Holiday::NewYear));
        assert_eq!(holiday_on(12, 31), Some(Holiday::NewYear));
        assert_eq!(holiday_on(7, 4), Some(Holiday::Independence));
        assert_eq!(holiday_on(7, 5), None);
        assert_eq!(holiday_on(10, 31), Some(Holiday::Halloween));
        assert_eq!(holiday_on(12, 25), Some(Holiday::Christmas));
        assert_eq!(holiday_on(12, 26), None);
        // The fourth Thursday of November: the 26th in 2026, the 22nd in 2029.
        assert_eq!(holiday_on(11, 26), Some(Holiday::Thanksgiving));
        assert_eq!(holiday_on(11, 22), Some(Holiday::Thanksgiving));
        assert_eq!(holiday_on(11, 21), None);
        assert_eq!(holiday_on(9, 30), None);
    }

    #[test]
    fn big_jim_answers_an_incident_before_anything_else() {
        let moment = BillboardMoment {
            incident: Some(Incident::Citation),
            tired: true,
            holiday: Some(Holiday::Christmas),
            nth: 0,
        };
        assert!(CITATION_LINES.contains(&dynamic_billboard(moment).unwrap()));
        let moment = BillboardMoment {
            incident: Some(Incident::Collision),
            nth: 7,
            ..Default::default()
        };
        assert!(COLLISION_LINES.contains(&dynamic_billboard(moment).unwrap()));
    }

    #[test]
    fn the_ordinary_roadside_still_shows_through() {
        let tired = |nth| BillboardMoment {
            tired: true,
            nth,
            ..Default::default()
        };
        assert!(dynamic_billboard(tired(0)).is_some());
        assert!(dynamic_billboard(tired(1)).is_none());
        let holiday = |nth| BillboardMoment {
            holiday: Some(Holiday::Halloween),
            nth,
            ..Default::default()
        };
        let swapped = (0..9).filter(|&n| dynamic_billboard(holiday(n)).is_some());
        assert_eq!(swapped.count(), 3);
        assert_eq!(dynamic_billboard(BillboardMoment::default()), None);
    }
}
