//! The grounded road-hazard catalog (the hazard half of
//! `freight_fate/sim/trip_models.py`): each hazard tagged with the
//! conditions under which it is plausible, and the eligibility filter that
//! draws only what the region, weather, terrain and hour allow.

use crate::sim::hos::time_of_day;
use crate::sim::weather::WeatherKind;

const CROSSWIND_REGIONS: &[&str] = &[
    "southern_plains",
    "heartland",
    "great_basin",
    "desert_southwest",
    "rockies",
];
const WET: &[WeatherKind] = &[
    WeatherKind::Rain,
    WeatherKind::HeavyRain,
    WeatherKind::Thunderstorm,
];
const HEAVY_WET: &[WeatherKind] = &[WeatherKind::HeavyRain, WeatherKind::Thunderstorm];
const WILDLIFE_TIMES: [&str; 3] = ["dawn", "dusk", "night"];

/// One grounded road hazard and the conditions under which it can occur.
///
/// `None` on `regions`/`weather`/`terrain` means "no restriction on that
/// axis". `animal` hazards are biased to dawn, dusk, and night. `name` is the
/// short noun phrase a resolution line names this hazard by ("the deer").
///
/// `in_lane` marks a hazard that sits in YOUR lane and no other: an object
/// on the pavement, a car stopped on the shoulder, a coned-off lane. It is a
/// property of the THING, and it is deliberately not the same question as
/// whether the hazard can be dodged -- that also needs a lane to dodge into,
/// which is a property of the ROAD (`Trip::has_open_adjacent_lane_at`). Fog,
/// ice, a crosswind and a deer that may bolt either way are not in-lane: they
/// span the road, so no lane change answers them however many lanes there
/// are. The two are combined once, at the emitter.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct HazardDef {
    pub text: &'static str,
    pub weight: f64,
    pub regions: Option<&'static [&'static str]>,
    pub weather: Option<&'static [WeatherKind]>,
    pub terrain: Option<&'static [&'static str]>,
    pub animal: bool,
    pub in_lane: bool,
    pub name: &'static str,
}

const fn hz(text: &'static str, weight: f64, name: &'static str) -> HazardDef {
    HazardDef {
        text,
        weight,
        regions: None,
        weather: None,
        terrain: None,
        animal: false,
        in_lane: false,
        name,
    }
}

const DEER_REGIONS: &[&str] = &[
    "northeast",
    "appalachia",
    "great_lakes",
    "upper_midwest",
    "corn_belt",
    "heartland",
    "mid_south",
    "atlantic_southeast",
    "southern_plains",
    "gulf_coast",
    "florida",
    "california",
];

pub static HAZARDS: &[HazardDef] = &[
    // Nationwide staples. Named debris, not "debris": a driver clearing a lane
    // blind needs to know WHAT is in it (Brandon, 2026-08-20). The split's
    // weights sum to the 1.2 the one generic entry carried.
    HazardDef {
        in_lane: true,
        ..hz(
            "a ladder fallen from a truck in the lane",
            0.25,
            "the ladder",
        )
    },
    HazardDef {
        in_lane: true,
        ..hz("loose lumber dropped across the lane", 0.25, "the lumber")
    },
    HazardDef {
        in_lane: true,
        ..hz("a mattress lying in the lane", 0.2, "the mattress")
    },
    HazardDef {
        in_lane: true,
        ..hz("spilled cargo boxes across the lane", 0.2, "the boxes")
    },
    HazardDef {
        in_lane: true,
        ..hz("a shredded truck tarp in the lane", 0.15, "the tarp")
    },
    HazardDef {
        in_lane: true,
        ..hz("debris on the road", 0.15, "the debris")
    },
    HazardDef {
        in_lane: true,
        ..hz("retread debris from a blown tire", 1.0, "the tire debris")
    },
    // The move-over law in action: shift a lane away from the shoulder.
    HazardDef {
        in_lane: true,
        ..hz(
            "a vehicle stopped on the shoulder",
            1.0,
            "the stopped vehicle",
        )
    },
    // "A slow vehicle ahead" is deliberately NOT here (owner call,
    // 2026-08-20): a slow vehicle in the flow is the traffic bubble's job.
    HazardDef {
        in_lane: true,
        ..hz("a sudden lane closure ahead", 0.8, "the lane closure")
    },
    hz(
        "stopped traffic around a fender bender",
        0.9,
        "the stopped traffic",
    ),
    // Wildlife: dawn/dusk/night, regional species.
    HazardDef {
        animal: true,
        regions: Some(DEER_REGIONS),
        ..hz("a deer crossing the road", 1.3, "the deer")
    },
    HazardDef {
        animal: true,
        regions: Some(&["rockies", "great_basin", "pacific_northwest"]),
        ..hz("an elk crossing the road", 1.1, "the elk")
    },
    // Named animals for the generic slot, weights summing to the 0.7 the one
    // generic entry carried.
    HazardDef {
        animal: true,
        ..hz("a dog loose on the road", 0.2, "the dog")
    },
    HazardDef {
        animal: true,
        ..hz("a coyote crossing the road", 0.15, "the coyote")
    },
    HazardDef {
        animal: true,
        ..hz("loose livestock on the road", 0.15, "the livestock")
    },
    HazardDef {
        animal: true,
        ..hz("a raccoon in the lane", 0.1, "the raccoon")
    },
    HazardDef {
        animal: true,
        ..hz("an animal on the road", 0.1, "the animal")
    }, // honest fallback
    // Wet weather only.
    HazardDef {
        weather: Some(WET),
        in_lane: true,
        ..hz(
            "standing water flooding the lane",
            1.1,
            "the standing water",
        )
    },
    HazardDef {
        weather: Some(HEAVY_WET),
        ..hz(
            "the trailer hydroplaning on standing water",
            1.0,
            "the hydroplaning",
        )
    },
    HazardDef {
        weather: Some(&[WeatherKind::Thunderstorm]),
        regions: Some(&[
            "southern_plains",
            "heartland",
            "corn_belt",
            "mid_south",
            "rockies",
            "great_lakes",
        ]),
        ..hz("hail hammering the windshield", 0.7, "the hail")
    },
    // Snow and ice only.
    HazardDef {
        weather: Some(&[WeatherKind::Snow]),
        ..hz("a snow squall whiting out the lane", 1.0, "the snow squall")
    },
    HazardDef {
        weather: Some(&[WeatherKind::Snow, WeatherKind::Ice]),
        ..hz("ice on the bridge deck", 1.0, "the ice")
    },
    HazardDef {
        weather: Some(&[WeatherKind::Snow, WeatherKind::Ice]),
        terrain: Some(&["mountain", "hills"]),
        ..hz("black ice on the shaded grade", 1.1, "the black ice")
    },
    // Freezing rain only.
    HazardDef {
        weather: Some(&[WeatherKind::Ice]),
        ..hz("glaze ice sheeting the whole lane", 1.3, "the glaze ice")
    },
    HazardDef {
        weather: Some(&[WeatherKind::Ice]),
        in_lane: true,
        ..hz("a car spun out on the glaze ahead", 1.1, "the spun-out car")
    },
    // Dense fog only.
    HazardDef {
        weather: Some(&[WeatherKind::Fog]),
        ..hz("brake lights looming in dense fog", 1.2, "the brake lights")
    },
    // High wind: crosswind shove and blowing debris in open country.
    HazardDef {
        weather: Some(&[WeatherKind::Wind]),
        regions: Some(CROSSWIND_REGIONS),
        ..hz(
            "a crosswind gust shoving the trailer",
            1.2,
            "the crosswind gust",
        )
    },
    HazardDef {
        weather: Some(&[WeatherKind::Wind]),
        regions: Some(&["desert_southwest", "southern_plains", "great_basin"]),
        ..hz("a dust storm dropping visibility", 0.9, "the dust storm")
    },
    HazardDef {
        weather: Some(&[WeatherKind::Wind]),
        regions: Some(&["desert_southwest", "great_basin", "southern_plains"]),
        in_lane: true,
        ..hz("tumbleweeds piling in your lane", 0.5, "the tumbleweeds")
    },
    // Mountain terrain only.
    HazardDef {
        terrain: Some(&["mountain"]),
        regions: Some(&[
            "rockies",
            "appalachia",
            "great_basin",
            "pacific_northwest",
            "california",
        ]),
        in_lane: true,
        ..hz("rockfall debris on the road", 1.0, "the rockfall")
    },
    HazardDef {
        terrain: Some(&["mountain"]),
        ..hz(
            "a runaway truck on the grade ahead",
            0.8,
            "the runaway truck",
        )
    },
];

/// Whether this hazard sits in your lane alone -- the half of "can I go
/// around it" that belongs to the hazard rather than to the road.
pub fn hazard_is_in_lane(text: &str) -> bool {
    HAZARDS.iter().any(|h| h.in_lane && h.text == text)
}

/// The short noun phrase a resolution line names this hazard by; "it" for a
/// text that somehow is not in the table rather than ever failing mid-drive.
pub fn hazard_name(text: &str) -> &'static str {
    HAZARDS
        .iter()
        .find(|h| h.text == text)
        .map(|h| h.name)
        .unwrap_or("it")
}

/// Hazards plausible for the current context, as `(text, weight)` pairs.
/// The nationwide staples have no restrictions, so the list is never empty.
pub fn eligible_hazards(
    region: &str,
    weather: WeatherKind,
    terrain: &str,
    game_hours: f64,
) -> Vec<(&'static str, f64)> {
    let nocturnal = WILDLIFE_TIMES.contains(&time_of_day(game_hours));
    let mut out = Vec::new();
    for hazard in HAZARDS {
        if hazard.regions.is_some_and(|r| !r.contains(&region)) {
            continue;
        }
        if hazard.weather.is_some_and(|w| !w.contains(&weather)) {
            continue;
        }
        if hazard.terrain.is_some_and(|t| !t.contains(&terrain)) {
            continue;
        }
        let mut weight = hazard.weight;
        if hazard.animal {
            weight *= if nocturnal { 2.2 } else { 0.25 };
        }
        out.push((hazard.text, weight));
    }
    out
}
