//! The registry surface the game's backend picker is built on, against the
//! real library.
//!
//! Everything here skips -- passes without asserting -- when Prism is not
//! loadable, so CI without the library stays green. Nothing speaks except
//! `a_usable_backend_takes_output_and_stop`, which additionally skips when
//! `FREIGHT_FATE_NO_SPEECH` is set (the headless convention shared with the
//! Python suite) or when no backend on the machine is usable.

use std::ops::Deref;
use std::sync::{Mutex, MutexGuard, OnceLock};

use prism::{backend_id, Context, Error, Features};

/// A context plus the lock that keeps these tests from overlapping.
///
/// Each test opens its own `Context`, and two of those on different threads,
/// each acquiring and probing every backend, take the process down inside
/// Prism (STATUS_ACCESS_VIOLATION, roughly four runs in five under the
/// default parallel harness; never once serialised). The game holds one
/// context on one thread, so that is the only arrangement worth testing and
/// the lock makes the harness match it.
struct Live {
    context: Context,
    _guard: MutexGuard<'static, ()>,
}

impl Deref for Live {
    type Target = Context;
    fn deref(&self) -> &Context {
        &self.context
    }
}

fn context() -> Option<Live> {
    static ONE_AT_A_TIME: OnceLock<Mutex<()>> = OnceLock::new();
    let guard = ONE_AT_A_TIME
        .get_or_init(|| Mutex::new(()))
        .lock()
        .unwrap_or_else(|err| err.into_inner());
    match Context::new() {
        Ok(context) => Some(Live {
            context,
            _guard: guard,
        }),
        Err(Error::Unavailable) => {
            eprintln!("prism not loadable here; skipping");
            None
        }
        Err(other) => panic!("unexpected error starting prism: {other}"),
    }
}

/// The game's notion of "can speak right now", from `speech.py::_usable`.
fn usable(features: Features) -> bool {
    features.is_supported_at_runtime() && (features.supports_output() || features.supports_speak())
}

#[test]
fn backend_ids_names_and_priorities_line_up() {
    let Some(context) = context() else { return };
    let ids = context.backend_ids();
    assert_eq!(ids.len(), context.backend_count());
    assert!(
        !ids.is_empty(),
        "a Prism build registers at least one backend"
    );
    let names = context.backend_names();
    assert_eq!(names.len(), ids.len());
    for (index, id) in ids.iter().enumerate() {
        assert_ne!(*id, backend_id::INVALID);
        assert_eq!(context.id_at(index), Some(*id));
        assert!(context.exists(*id));
        let name = context.name_of(*id).expect("a registered id has a name");
        assert_eq!(name, names[index]);
        assert!(!name.is_empty());
        // Priority is whatever Prism says; the call must simply answer for
        // every registered id.
        let _ = context.priority_of(*id);
    }
    // Past the end and unknown ids answer `None`, never a panic.
    assert_eq!(context.id_at(ids.len()), None);
    assert_eq!(context.name_of(backend_id::INVALID), None);
    assert!(!context.exists(backend_id::INVALID));
}

#[test]
fn id_by_name_round_trips_every_registry_name() {
    let Some(context) = context() else { return };
    for id in context.backend_ids() {
        let name = context.name_of(id).unwrap();
        assert_eq!(
            context.id_by_name(&name),
            Some(id),
            "id_by_name({name:?}) should give back {id:#x}"
        );
    }
    assert_eq!(context.id_by_name("no such backend"), None);
    assert_eq!(context.id_by_name(""), None);
    assert_eq!(context.id_by_name("bad\0name"), None);
}

#[cfg(windows)]
#[test]
fn the_windows_registry_knows_the_backends_the_game_names() {
    // `speech.py` asks for these by name: SAPI as the event voice, UIA as
    // the Narrator route it ranks last. Their well-known ids must match too.
    let Some(context) = context() else { return };
    assert_eq!(context.id_by_name("SAPI"), Some(backend_id::SAPI));
    assert_eq!(context.id_by_name("UIA"), Some(backend_id::UIA));
    assert_eq!(context.id_by_name("NVDA"), Some(backend_id::NVDA));
    assert_eq!(context.name_of(backend_id::SAPI).as_deref(), Some("SAPI"));
}

#[test]
fn every_backend_reports_features_without_speaking() {
    // Acquiring initialises a backend but says nothing; features are the
    // first thing the picker reads and must never fail or panic.
    let Some(context) = context() else { return };
    let mut by_priority: Vec<_> = context
        .backend_ids()
        .into_iter()
        .map(|id| (context.priority_of(id), id))
        .collect();
    by_priority.sort_by_key(|entry| std::cmp::Reverse(entry.0));
    for (_, id) in by_priority {
        let Ok(backend) = context.acquire(id) else {
            continue;
        };
        let features = backend.features();
        assert_eq!(backend.name(), context.name_of(id).unwrap());
        // A backend that can be driven at all advertises a speaking path.
        if features.is_supported_at_runtime() {
            assert!(
                features.supports_speak() || features.supports_output(),
                "{} is live but has no speech entry point: {features:?}",
                backend.name()
            );
        }
        // Read-only property getters are allowed to refuse (NOT_IMPLEMENTED
        // on screen readers) but not to crash.
        let _ = backend.rate();
        let _ = backend.pitch();
        let _ = backend.volume();
        let _ = backend.voices_count();
        let _ = backend.voice();
        let _ = backend.is_speaking();
    }
}

#[test]
fn voice_names_come_back_for_a_backend_that_lists_them() {
    let Some(context) = context() else { return };
    for id in context.backend_ids() {
        let Ok(backend) = context.acquire(id) else {
            continue;
        };
        let features = backend.features();
        if !(features.supports_count_voices() && features.supports_get_voice_name()) {
            continue;
        }
        let Ok(count) = backend.voices_count() else {
            continue;
        };
        for index in 0..count {
            let name = backend
                .voice_name(index)
                .unwrap_or_else(|err| panic!("{} voice {index}: {err}", backend.name()));
            assert!(
                !name.is_empty(),
                "{} voice {index} has no name",
                backend.name()
            );
        }
        // One past the end is a range error, not a crash.
        assert!(backend.voice_name(count).is_err());
    }
}

#[test]
fn empty_text_is_refused_before_reaching_the_library() {
    let Some(context) = context() else { return };
    let Some(id) = context.backend_ids().first().copied() else {
        return;
    };
    let Ok(mut backend) = context.acquire(id) else {
        return;
    };
    assert!(matches!(backend.output("", true), Err(Error::EmptyText)));
    assert!(matches!(backend.speak("", true), Err(Error::EmptyText)));
    assert!(matches!(backend.braille(""), Err(Error::EmptyText)));
    assert!(matches!(
        backend.output("a\0b", true),
        Err(Error::InteriorNul)
    ));
}

#[test]
fn a_usable_backend_takes_output_and_stop() {
    // The one test that speaks. Picks the way the game does -- highest
    // priority usable backend, UIA (Narrator) excluded because it claims
    // runtime support unconditionally -- says a short line, then stops it.
    if std::env::var_os("FREIGHT_FATE_NO_SPEECH").is_some_and(|v| !v.is_empty()) {
        eprintln!("FREIGHT_FATE_NO_SPEECH set; skipping");
        return;
    }
    let Some(context) = context() else { return };
    let mut candidates: Vec<_> = context
        .backend_ids()
        .into_iter()
        .filter(|id| context.name_of(*id).as_deref() != Some("UIA"))
        .map(|id| (context.priority_of(id), id))
        .collect();
    candidates.sort_by_key(|entry| std::cmp::Reverse(entry.0));
    let mut picked = None;
    for (_, id) in candidates {
        if let Ok(backend) = context.acquire(id) {
            if usable(backend.features()) {
                picked = Some(backend);
                break;
            }
        }
    }
    let Some(mut backend) = picked else {
        eprintln!("no usable speech backend on this machine; skipping");
        return;
    };
    let features = backend.features();
    let spoke = if features.supports_output() {
        backend.output("Freight Fate speech check.", true)
    } else {
        backend.speak("Freight Fate speech check.", true)
    };
    spoke.unwrap_or_else(|err| panic!("{} refused to speak: {err}", backend.name()));
    if features.supports_stop() {
        backend
            .stop()
            .unwrap_or_else(|err| panic!("{} refused to stop: {err}", backend.name()));
    }
}
