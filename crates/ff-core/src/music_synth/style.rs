//! One musical identity per place the synthesized music plays.

use crate::models::business_constants::is_owner_operator;
use crate::music::{is_night, MenuMusicProfile};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum StyleId {
    NewHire,
    FirstRun,
    Regional,
    SeniorCompany,
    TopHand,
    Trainer,
    MillionMile,
    FleetOwner,
    CoastToCoast,
    LegendaryHaul,
    RoadLegend,
    NightMenu,
    DayDrive,
    NightDrive,
}

impl StyleId {
    pub const ALL: [StyleId; 14] = [
        StyleId::NewHire,
        StyleId::FirstRun,
        StyleId::Regional,
        StyleId::SeniorCompany,
        StyleId::TopHand,
        StyleId::Trainer,
        StyleId::MillionMile,
        StyleId::FleetOwner,
        StyleId::CoastToCoast,
        StyleId::LegendaryHaul,
        StyleId::RoadLegend,
        StyleId::NightMenu,
        StyleId::DayDrive,
        StyleId::NightDrive,
    ];

    /// Stable id: used in asset keys and folder names. Never rename one.
    pub fn id(self) -> &'static str {
        style(self).id
    }

    pub fn from_id(id: &str) -> Option<StyleId> {
        Self::ALL.into_iter().find(|s| s.id() == id)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Major,
    Minor,
    Dorian,
    Mixolydian,
}

impl Mode {
    /// Semitone offsets of the seven scale degrees.
    pub fn intervals(self) -> [i32; 7] {
        match self {
            Mode::Major => [0, 2, 4, 5, 7, 9, 11],
            Mode::Minor => [0, 2, 3, 5, 7, 8, 10],
            Mode::Dorian => [0, 2, 3, 5, 7, 9, 10],
            Mode::Mixolydian => [0, 2, 4, 5, 7, 9, 10],
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Lead {
    Pluck,
    Keys,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Drums {
    None,
    Brushes,
    Kit,
}

#[derive(Debug)]
pub struct Style {
    pub id: &'static str,
    /// Spoken in the synth piece title.
    pub title: &'static str,
    /// MIDI note of the tonic in the bass octave (e.g. 43 = G2).
    pub root: i32,
    pub mode: Mode,
    pub bpm: (f64, f64),
    /// Progressions as 0-based scale degrees, one chord per bar.
    pub progressions: &'static [&'static [usize]],
    pub lead: Lead,
    pub drums: Drums,
    /// 0 = straight eighths, up to ~0.3 = shuffled.
    pub swing: f64,
    /// Chance a melody slot is a rest; higher is sparser and calmer.
    pub rest: f64,
}

const WARM: &[&[usize]] = &[&[0, 4, 5, 3], &[0, 3, 4, 3], &[0, 5, 3, 4], &[0, 3, 0, 4]];
const OPEN: &[&[usize]] = &[&[0, 6, 3, 0], &[0, 4, 3, 0], &[0, 3, 6, 4], &[0, 6, 5, 4]];
const MOODY: &[&[usize]] = &[&[0, 5, 2, 6], &[0, 3, 4, 0], &[0, 5, 3, 4], &[0, 6, 5, 6]];

static STYLES: [Style; 14] = [
    Style {
        id: "new_hire",
        title: "New Hire",
        root: 43,
        mode: Mode::Major,
        bpm: (72.0, 80.0),
        progressions: WARM,
        lead: Lead::Pluck,
        drums: Drums::None,
        swing: 0.0,
        rest: 0.35,
    },
    Style {
        id: "first_run",
        title: "First Run",
        root: 45,
        mode: Mode::Major,
        bpm: (84.0, 92.0),
        progressions: WARM,
        lead: Lead::Pluck,
        drums: Drums::Brushes,
        swing: 0.1,
        rest: 0.3,
    },
    Style {
        id: "regional",
        title: "Regional",
        root: 38,
        mode: Mode::Mixolydian,
        bpm: (90.0, 98.0),
        progressions: OPEN,
        lead: Lead::Pluck,
        drums: Drums::Brushes,
        swing: 0.15,
        rest: 0.25,
    },
    Style {
        id: "company_senior",
        title: "Senior Driver",
        root: 41,
        mode: Mode::Major,
        bpm: (76.0, 84.0),
        progressions: WARM,
        lead: Lead::Keys,
        drums: Drums::Brushes,
        swing: 0.1,
        rest: 0.35,
    },
    Style {
        id: "company_top_hand",
        title: "Top Hand",
        root: 43,
        mode: Mode::Major,
        bpm: (80.0, 88.0),
        progressions: WARM,
        lead: Lead::Keys,
        drums: Drums::Brushes,
        swing: 0.2,
        rest: 0.3,
    },
    Style {
        id: "company_trainer",
        title: "Trainer",
        root: 40,
        mode: Mode::Dorian,
        bpm: (78.0, 86.0),
        progressions: MOODY,
        lead: Lead::Keys,
        drums: Drums::Brushes,
        swing: 0.15,
        rest: 0.35,
    },
    Style {
        id: "company_million_mile",
        title: "Million Mile",
        root: 45,
        mode: Mode::Major,
        bpm: (84.0, 92.0),
        progressions: OPEN,
        lead: Lead::Keys,
        drums: Drums::Kit,
        swing: 0.1,
        rest: 0.3,
    },
    Style {
        id: "owner_fleet",
        title: "Fleet Owner",
        root: 40,
        mode: Mode::Mixolydian,
        bpm: (96.0, 104.0),
        progressions: OPEN,
        lead: Lead::Pluck,
        drums: Drums::Kit,
        swing: 0.0,
        rest: 0.2,
    },
    Style {
        id: "owner_coast_to_coast",
        title: "Coast to Coast",
        root: 42,
        mode: Mode::Major,
        bpm: (100.0, 110.0),
        progressions: OPEN,
        lead: Lead::Pluck,
        drums: Drums::Kit,
        swing: 0.05,
        rest: 0.2,
    },
    Style {
        id: "owner_legendary_haul",
        title: "Legendary Haul",
        root: 38,
        mode: Mode::Dorian,
        bpm: (96.0, 106.0),
        progressions: MOODY,
        lead: Lead::Pluck,
        drums: Drums::Kit,
        swing: 0.0,
        rest: 0.2,
    },
    Style {
        id: "owner_road_legend",
        title: "Road Legend",
        root: 43,
        mode: Mode::Mixolydian,
        bpm: (104.0, 112.0),
        progressions: OPEN,
        lead: Lead::Keys,
        drums: Drums::Kit,
        swing: 0.1,
        rest: 0.18,
    },
    Style {
        id: "night_menu",
        title: "Midnight Terminal",
        root: 45,
        mode: Mode::Minor,
        bpm: (64.0, 72.0),
        progressions: MOODY,
        lead: Lead::Keys,
        drums: Drums::None,
        swing: 0.0,
        rest: 0.45,
    },
    Style {
        id: "drive_day",
        title: "Day Drive",
        root: 45,
        mode: Mode::Major,
        bpm: (88.0, 100.0),
        progressions: OPEN,
        lead: Lead::Pluck,
        drums: Drums::Brushes,
        swing: 0.1,
        rest: 0.25,
    },
    Style {
        id: "drive_night",
        title: "Night Drive",
        root: 45,
        mode: Mode::Minor,
        bpm: (66.0, 76.0),
        progressions: MOODY,
        lead: Lead::Keys,
        drums: Drums::None,
        swing: 0.0,
        rest: 0.4,
    },
];

pub fn style(id: StyleId) -> &'static Style {
    let index = StyleId::ALL.iter().position(|s| *s == id).unwrap_or(0);
    &STYLES[index]
}

/// The synthesized ladder: today's thresholds rung for rung, split on
/// business status from rung 3, and rung 1 earned by driving rather than by
/// the tractor (a company driver's carrier tractor is not a milestone).
pub fn menu_rung(profile: Option<&dyn MenuMusicProfile>) -> StyleId {
    let Some(p) = profile else {
        return StyleId::NewHire;
    };
    let (level, deliveries, miles) = (p.level(), p.deliveries(), p.total_miles());
    let owner = is_owner_operator(&p.business_status());
    let branch = |company: StyleId, owner_style: StyleId| if owner { owner_style } else { company };
    if level >= 21 || deliveries >= 75 || miles >= 40_000.0 {
        return branch(StyleId::MillionMile, StyleId::RoadLegend);
    }
    if level >= 9 || deliveries >= 40 || miles >= 20_000.0 {
        return branch(StyleId::Trainer, StyleId::LegendaryHaul);
    }
    if level >= 7 || miles >= 10_000.0 {
        return branch(StyleId::TopHand, StyleId::CoastToCoast);
    }
    if level >= 5 || p.owned_truck_count() >= 2 {
        return branch(StyleId::SeniorCompany, StyleId::FleetOwner);
    }
    if level >= 3 || miles >= 2_500.0 {
        return StyleId::Regional;
    }
    if level >= 2 || deliveries >= 3 {
        return StyleId::FirstRun;
    }
    StyleId::NewHire
}

/// The style a menu plays right now: the night menu after dark, else the rung.
pub fn menu_style(profile: Option<&dyn MenuMusicProfile>) -> StyleId {
    if profile.is_some_and(|p| is_night(p.game_hours() % 24.0)) {
        return StyleId::NightMenu;
    }
    menu_rung(profile)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::business_constants::{
        COMPANY_DRIVER, INDEPENDENT_AUTHORITY, LEASED_OWNER_OPERATOR,
    };

    struct P {
        level: i64,
        deliveries: i64,
        miles: f64,
        owned: usize,
        truck: &'static str,
        status: &'static str,
        hours: f64,
    }

    impl MenuMusicProfile for P {
        fn game_hours(&self) -> f64 {
            self.hours
        }
        fn level(&self) -> i64 {
            self.level
        }
        fn deliveries(&self) -> i64 {
            self.deliveries
        }
        fn total_miles(&self) -> f64 {
            self.miles
        }
        fn owned_truck_count(&self) -> usize {
            self.owned
        }
        fn active_truck_key(&self) -> String {
            self.truck.into()
        }
        fn name(&self) -> String {
            "T".into()
        }
        fn current_city(&self) -> String {
            "Denver".into()
        }
        fn business_status(&self) -> String {
            self.status.into()
        }
    }

    fn p(level: i64, status: &'static str) -> P {
        P {
            level,
            deliveries: 0,
            miles: 0.0,
            owned: 1,
            truck: "rig",
            status,
            hours: 12.0,
        }
    }

    #[test]
    fn ids_are_unique_and_round_trip() {
        for s in StyleId::ALL {
            assert_eq!(StyleId::from_id(s.id()), Some(s));
        }
        let mut ids: Vec<_> = StyleId::ALL.iter().map(|s| s.id()).collect();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), 14);
    }

    #[test]
    fn company_and_owner_branches_split_from_rung_three() {
        for (level, company, owner) in [
            (5, StyleId::SeniorCompany, StyleId::FleetOwner),
            (7, StyleId::TopHand, StyleId::CoastToCoast),
            (9, StyleId::Trainer, StyleId::LegendaryHaul),
            (21, StyleId::MillionMile, StyleId::RoadLegend),
        ] {
            assert_eq!(menu_rung(Some(&p(level, COMPANY_DRIVER))), company);
            assert_eq!(menu_rung(Some(&p(level, LEASED_OWNER_OPERATOR))), owner);
            assert_eq!(menu_rung(Some(&p(level, INDEPENDENT_AUTHORITY))), owner);
        }
        assert_eq!(menu_rung(Some(&p(3, COMPANY_DRIVER))), StyleId::Regional);
        assert_eq!(
            menu_rung(Some(&p(3, INDEPENDENT_AUTHORITY))),
            StyleId::Regional
        );
    }

    #[test]
    fn a_carrier_tractor_alone_is_not_the_first_run() {
        let mut fresh = p(1, COMPANY_DRIVER);
        fresh.truck = "carrier_cascadia";
        assert_eq!(menu_rung(Some(&fresh)), StyleId::NewHire);
        fresh.deliveries = 3;
        assert_eq!(menu_rung(Some(&fresh)), StyleId::FirstRun);
    }

    #[test]
    fn night_menu_leads_after_dark_and_no_profile_is_new_hire() {
        let mut night = p(21, COMPANY_DRIVER);
        night.hours = 23.0;
        assert_eq!(menu_style(Some(&night)), StyleId::NightMenu);
        assert_eq!(menu_style(None), StyleId::NewHire);
    }
}
