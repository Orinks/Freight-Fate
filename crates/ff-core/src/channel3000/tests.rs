//! The Channel 3000 schedule: dayparts, the break rules, the shuffle, the
//! seed, and the committed manifest's integrity.

use super::*;

fn clip(key: &str, kind: ClipKind, dayparts: &[Daypart], duration_s: f64) -> Clip {
    Clip {
        key: key.to_string(),
        kind,
        dayparts: dayparts.to_vec(),
        opener: false,
        title: if kind == ClipKind::Programme {
            format!("Show {key}")
        } else {
            "Channel 3000".to_string()
        },
        duration_s,
    }
}

/// A small station: per daypart two idents, two continuity lines, an
/// opener and its own programmes; ads and shorts in every daypart. Day has
/// three episodes of one show and one of another, to exercise the
/// same-show rule.
fn fixture() -> &'static Manifest {
    use ClipKind::*;
    use Daypart::*;
    let mut clips = vec![
        clip("day_soap_01", Programme, &[Day], 300.0),
        clip("day_soap_02", Programme, &[Day], 300.0),
        clip("day_soap_03", Programme, &[Day], 300.0),
        clip("day_quiz_01", Programme, &[Day], 300.0),
        clip("prime_drama_01", Programme, &[Prime], 400.0),
        clip("prime_comedy", Programme, &[Prime], 400.0),
        clip("prime_news", Programme, &[Prime], 400.0),
        clip("late_horror_01", Programme, &[Late], 350.0),
        clip("late_song", Programme, &[Late], 120.0),
        clip("overnight_film_01", Programme, &[Overnight], 360.0),
        clip("overnight_lullaby", Programme, &[Overnight], 150.0),
        clip("ad_one", Ad, &Daypart::ALL, 30.0),
        clip("ad_two", Ad, &Daypart::ALL, 30.0),
        clip("ad_three", Ad, &Daypart::ALL, 30.0),
        clip("short_one", Short, &Daypart::ALL, 90.0),
        clip("short_two", Short, &Daypart::ALL, 90.0),
    ];
    for part in Daypart::ALL {
        let name = part.name();
        for n in 1..=2 {
            clips.push(clip(&format!("id_{name}_{n:02}"), Ident, &[part], 8.0));
            clips.push(clip(
                &format!("host_{name}_{n:02}"),
                Continuity,
                &[part],
                12.0,
            ));
        }
        let mut opener = clip(&format!("host_{name}_opener"), Continuity, &[part], 15.0);
        opener.opener = true;
        clips.push(opener);
    }
    Box::leak(Box::new(Manifest {
        schema: 1,
        notes: String::new(),
        frequency_mhz: 87.7,
        dayparts: DaypartHours {
            day: [5, 19],
            prime: [19, 22],
            late: [22, 2],
            overnight: [2, 5],
        },
        clips,
    }))
}

fn committed() -> &'static Manifest {
    default_manifest().expect("data/channel3000.json loads and passes its checks")
}

/// Finish the clip on the air at `hour`; the next one is then on the air.
fn finish(schedule: &mut Schedule, hour: f64) -> &'static Clip {
    schedule.start(hour);
    let clip = schedule.on_air().expect("on the air");
    let left = clip.duration_s.max(MIN_CLIP_S) - schedule.elapsed_s();
    schedule.advance(left + 1e-6, hour);
    schedule.on_air().expect("still on the air")
}

/// The keys of the next `count` clips, the first being the one on the air.
fn run(schedule: &mut Schedule, hour: f64, count: usize) -> Vec<&'static Clip> {
    schedule.start(hour);
    let mut out = vec![schedule.on_air().unwrap()];
    while out.len() < count {
        out.push(finish(schedule, hour));
    }
    out
}

fn keys(clips: &[&Clip]) -> Vec<String> {
    clips.iter().map(|c| c.key.clone()).collect()
}

// -- dayparts ----------------------------------------------------------------------

#[test]
fn dayparts_follow_the_local_hour_at_every_boundary() {
    let m = fixture();
    use Daypart::*;
    for (hour, want) in [
        (4.99, Overnight),
        (5.0, Day),
        (12.0, Day),
        (18.99, Day),
        (19.0, Prime),
        (21.99, Prime),
        (22.0, Late),
        (23.99, Late),
        // Late runs across midnight.
        (0.0, Late),
        (1.5, Late),
        (1.99, Late),
        (2.0, Overnight),
        (24.0, Late),
        (-1.0, Late),
    ] {
        assert_eq!(m.daypart_at(hour), want, "hour {hour}");
    }
}

#[test]
fn late_does_not_break_for_midnight() {
    // 23:00 to 01:00 is one daypart: no ident-and-opener at midnight.
    let mut s = Schedule::new(fixture(), "midnight");
    let mut seen = run(&mut s, 23.0, 3);
    assert_eq!(seen[2].kind, ClipKind::Programme);
    for _ in 0..12 {
        seen.push(finish(&mut s, 1.0));
    }
    assert!(seen[3..].iter().all(|c| !c.opener), "{:?}", keys(&seen));
    assert!(seen.iter().all(|c| c.airs_in(Daypart::Late)));
}

// -- the break rules ----------------------------------------------------------------

#[test]
fn sign_on_is_the_ident_then_the_opener_then_a_programme() {
    for (hour, part) in [(10.0, Daypart::Day), (20.0, Daypart::Prime)] {
        let mut s = Schedule::new(fixture(), "sign-on");
        let first = run(&mut s, hour, 3);
        assert_eq!(first[0].kind, ClipKind::Ident);
        assert!(first[1].opener);
        assert_eq!(first[2].kind, ClipKind::Programme);
        assert!(first.iter().all(|c| c.airs_in(part)), "{:?}", keys(&first));
    }
}

#[test]
fn a_programme_is_never_cut_off_by_the_hour() {
    let mut s = Schedule::new(fixture(), "no cuts");
    run(&mut s, 18.5, 3);
    let programme = s.on_air().unwrap();
    assert_eq!(programme.kind, ClipKind::Programme);
    let serial = s.serial();
    // Prime begins a few seconds in; the day programme plays on.
    s.advance(10.0, 19.2);
    s.advance(programme.duration_s - 11.0, 19.3);
    assert_eq!(s.serial(), serial);
    assert_eq!(s.on_air().unwrap().key, programme.key);
}

#[test]
fn between_programmes_is_an_ident_then_one_or_two_fillers() {
    let mut s = Schedule::new(fixture(), "breaks");
    let clips = run(&mut s, 12.0, 400);
    let programmes: Vec<usize> = clips
        .iter()
        .enumerate()
        .filter(|(_, c)| c.kind == ClipKind::Programme)
        .map(|(i, _)| i)
        .collect();
    let mut lengths = std::collections::HashSet::new();
    for pair in programmes.windows(2) {
        let glue = &clips[pair[0] + 1..pair[1]];
        assert_eq!(glue[0].kind, ClipKind::Ident, "{:?}", keys(glue));
        // The fillers: runs of continuity, ads (one or two) and shorts.
        let mut groups: Vec<(ClipKind, usize)> = Vec::new();
        for c in &glue[1..] {
            assert!(!c.opener, "an opener only opens its daypart");
            match groups.last_mut() {
                Some((kind, n)) if *kind == c.kind => *n += 1,
                _ => groups.push((c.kind, 1)),
            }
        }
        assert!((1..=2).contains(&groups.len()), "{:?}", keys(glue));
        for (kind, n) in &groups {
            assert!(
                matches!(kind, ClipKind::Continuity | ClipKind::Ad | ClipKind::Short),
                "{:?}",
                keys(glue)
            );
            let most = if *kind == ClipKind::Ad { 2 } else { 1 };
            assert!(*n <= most, "{:?}", keys(glue));
        }
        lengths.insert(groups.len());
    }
    assert_eq!(lengths.len(), 2, "both one filler and two fillers turn up");
}

#[test]
fn a_new_daypart_opens_with_its_ident_and_opener_and_nothing_else() {
    let mut s = Schedule::new(fixture(), "change");
    run(&mut s, 18.0, 3);
    assert_eq!(s.on_air().unwrap().kind, ClipKind::Programme);
    // The day programme ends after prime has begun.
    let next = finish(&mut s, 19.5);
    let opener = finish(&mut s, 19.5);
    let programme = finish(&mut s, 19.5);
    assert_eq!(next.kind, ClipKind::Ident);
    assert!(next.airs_in(Daypart::Prime));
    assert_eq!(opener.key, "host_prime_opener");
    assert_eq!(programme.kind, ClipKind::Programme);
    assert!(programme.airs_in(Daypart::Prime));
}

#[test]
fn the_next_clip_is_chosen_when_the_last_one_ends() {
    // A break planned in the day that runs past 19:00 hands its programme
    // slot to prime, which opens with its own ident and opener.
    let mut s = Schedule::new(fixture(), "late break");
    run(&mut s, 18.0, 3);
    let ident = finish(&mut s, 18.9);
    assert!(ident.airs_in(Daypart::Day));
    let mut rest = Vec::new();
    while rest
        .last()
        .is_none_or(|c: &&Clip| c.kind != ClipKind::Programme)
    {
        rest.push(finish(&mut s, 19.1));
    }
    let n = rest.len();
    assert!(n >= 3, "{:?}", keys(&rest));
    assert_eq!(rest[n - 3].kind, ClipKind::Ident);
    assert!(rest[n - 3].airs_in(Daypart::Prime));
    assert_eq!(rest[n - 2].key, "host_prime_opener");
    assert!(rest[n - 1].airs_in(Daypart::Prime));
}

#[test]
fn the_glue_avoids_its_last_picks() {
    let mut s = Schedule::new(fixture(), "idents");
    let clips = run(&mut s, 12.0, 300);
    let idents: Vec<&str> = clips
        .iter()
        .filter(|c| c.kind == ClipKind::Ident)
        .map(|c| c.key.as_str())
        .collect();
    assert!(idents.windows(2).all(|w| w[0] != w[1]), "{idents:?}");
    let ads: Vec<&str> = clips
        .iter()
        .filter(|c| c.kind == ClipKind::Ad)
        .map(|c| c.key.as_str())
        .collect();
    assert!(ads.windows(2).all(|w| w[0] != w[1]), "{ads:?}");
}

// -- programmes --------------------------------------------------------------------

#[test]
fn programmes_never_repeat_until_the_pool_is_used_up() {
    // Prime's three programmes are three different shows, so a lap is
    // simply every programme once.
    let mut s = Schedule::new(fixture(), "laps");
    let clips = run(&mut s, 20.0, 200);
    let shown: Vec<&str> = clips
        .iter()
        .filter(|c| c.kind == ClipKind::Programme)
        .map(|c| c.key.as_str())
        .collect();
    assert!(shown.len() >= 12);
    for lap in shown.chunks(3).filter(|lap| lap.len() == 3) {
        let distinct: std::collections::HashSet<_> = lap.iter().collect();
        assert_eq!(distinct.len(), 3, "{shown:?}");
    }
}

#[test]
fn the_same_show_never_plays_twice_in_a_row_when_another_is_there() {
    // Day: three episodes of the soap and one quiz. The soap can never
    // follow itself, so it alternates with the quiz.
    let mut s = Schedule::new(fixture(), "soap");
    let clips = run(&mut s, 12.0, 400);
    let shows: Vec<&str> = clips
        .iter()
        .filter(|c| c.kind == ClipKind::Programme)
        .map(|c| c.show())
        .collect();
    assert!(shows.len() > 20);
    assert!(shows.windows(2).all(|w| w[0] != w[1]), "{shows:?}");
}

#[test]
fn every_committed_daypart_rotates_without_back_to_back_shows() {
    let m = committed();
    for (hour, part) in [
        (12.0, Daypart::Day),
        (20.0, Daypart::Prime),
        (23.0, Daypart::Late),
        (3.0, Daypart::Overnight),
    ] {
        let mut s = Schedule::new(m, &format!("committed {}", part.name()));
        let clips = run(&mut s, hour, 1500);
        let programmes: Vec<&Clip> = clips
            .iter()
            .copied()
            .filter(|c| c.kind == ClipKind::Programme)
            .collect();
        let pool = m.pool(part, ClipKind::Programme);
        assert!(programmes.len() > pool.len() * 2, "{}", part.name());
        assert!(programmes.iter().all(|c| c.airs_in(part)));
        assert!(
            programmes.windows(2).all(|w| w[0].show() != w[1].show()),
            "{}: {:?}",
            part.name(),
            keys(&programmes)
        );
        // The first lap plays the whole pool before anything comes back.
        let first: std::collections::HashSet<&str> = programmes[..pool.len()]
            .iter()
            .map(|c| c.key.as_str())
            .collect();
        assert!(
            first.len() + 1 >= pool.len(),
            "{}: {} of {}",
            part.name(),
            first.len(),
            pool.len()
        );
    }
}

#[test]
fn shows_are_keys_without_their_episode_number() {
    let m = fixture();
    let show = |key: &str| {
        m.clips
            .iter()
            .find(|c| c.key == key)
            .unwrap()
            .show()
            .to_string()
    };
    assert_eq!(show("day_soap_02"), "day_soap");
    assert_eq!(show("prime_comedy"), "prime_comedy");
    assert_eq!(show("id_day_01"), "id_day");
}

// -- the seed ----------------------------------------------------------------------

#[test]
fn the_seed_fixes_the_running_order() {
    let a = keys(&run(&mut Schedule::new(fixture(), "trip 7"), 12.0, 60));
    let b = keys(&run(&mut Schedule::new(fixture(), "trip 7"), 12.0, 60));
    let c = keys(&run(&mut Schedule::new(fixture(), "trip 8"), 12.0, 60));
    assert_eq!(a, b);
    assert_ne!(a, c);
}

#[test]
fn a_fixed_seed_pins_its_opening_sequence() {
    let opening = keys(&run(&mut Schedule::new(fixture(), "pinned"), 12.0, 12));
    assert_eq!(opening, PINNED_OPENING, "{opening:?}");
}

/// Sign-on, then three ordinary breaks: an ident and one filler each.
const PINNED_OPENING: [&str; 12] = [
    "id_day_02",
    "host_day_opener",
    "day_soap_03",
    "id_day_01",
    "host_day_01",
    "day_quiz_01",
    "id_day_02",
    "host_day_02",
    "day_soap_02",
    "id_day_01",
    "ad_two",
    "day_quiz_01",
];

#[test]
fn advancing_in_one_step_or_many_lands_in_the_same_place() {
    let mut whole = Schedule::new(fixture(), "steps");
    whole.advance(5000.0, 12.0);
    let mut frames = Schedule::new(fixture(), "steps");
    for _ in 0..(5000 * 4) {
        frames.advance(0.25, 12.0);
    }
    assert_eq!(whole.on_air().unwrap().key, frames.on_air().unwrap().key);
    assert!((whole.elapsed_s() - frames.elapsed_s()).abs() < 1e-3);
    assert_eq!(whole.serial(), frames.serial());
}

// -- asset keys --------------------------------------------------------------------

#[test]
fn clips_play_from_their_own_pack_and_music_from_music() {
    assert_eq!(clip_asset_key("day_weigh_in_01"), "c3k/day_weigh_in_01");
    assert_eq!(
        music_asset_key("c3k/day_weigh_in_01"),
        "c3k/day_weigh_in_01"
    );
    assert_eq!(music_asset_key("open_road"), "music/open_road");
}

// -- the committed manifest --------------------------------------------------------

#[test]
fn the_committed_manifest_is_a_station_that_runs() {
    let m = committed();
    assert_eq!(m.problems(), Vec::<String>::new());
    assert_eq!(m.frequency_mhz, 87.7);
    for part in Daypart::ALL {
        assert!(!m.pool(part, ClipKind::Programme).is_empty());
        assert!(!m.pool(part, ClipKind::Ident).is_empty());
        assert!(m.opener(part).is_some(), "{}", part.name());
    }
    for c in &m.clips {
        assert!(c.duration_s > 0.0, "{}", c.key);
        assert!(!c.title.trim().is_empty(), "{}", c.key);
        assert!(!c.dayparts.is_empty(), "{}", c.key);
    }
}

#[test]
fn a_broken_manifest_says_what_is_wrong() {
    let mut m = fixture().clone();
    m.clips.retain(|c| c.key != "host_late_opener");
    m.clips[0].duration_s = 0.0;
    let problems = m.problems();
    assert!(problems.iter().any(|p| p.contains("late has 0 openers")));
    assert!(problems
        .iter()
        .any(|p| p.contains("day_soap_01 has no duration")));
}
