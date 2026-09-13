use super::*;

// These closures replace only native creation/acquisition. The policy used
// by PrismRegistry::acquire itself decides which instance the caller gets.
#[test]
fn recovery_reuses_private_voice_after_startup_and_repeated_refresh() {
    let instances = BackendInstances::new(true);
    let created = Cell::new(0);
    let shared_acquires = Cell::new(0);
    let get = |id| {
        instances.acquire(
            id,
            |id| {
                created.set(created.get() + 1);
                Ok(id)
            },
            |_| {
                shared_acquires.set(shared_acquires.get() + 1);
                Ok(0)
            },
        )
    };
    let event = get(2).unwrap();
    *event.borrow_mut() = 99;
    instances.settle();
    for _ in 0..4 {
        let replayed = get(2).unwrap();
        assert_eq!(
            *replayed.borrow(),
            99,
            "replay or refresh abandoned the private voice"
        );
        assert!(Rc::ptr_eq(&event, &replayed));
    }
    assert_eq!(
        created.get(),
        1,
        "health checks recreated the software voice"
    );
    assert_eq!(
        shared_acquires.get(),
        0,
        "recovery re-entered the poisoned shared cache"
    );
}

#[test]
fn recovery_keeps_distinct_backend_ids_and_worker_generations_isolated() {
    let first = BackendInstances::new(true);
    let next = BackendInstances::new(true);
    let acquire = |cache: &BackendInstances<u64>, id| {
        cache
            .acquire(id, Ok, |_| panic!("recovery used global native cache"))
            .unwrap()
    };
    let main = acquire(&first, 1);
    let event = acquire(&first, 2);
    *main.borrow_mut() = 10;
    *event.borrow_mut() = 20;
    first.settle();
    assert_eq!(*acquire(&first, 1).borrow(), 10);
    assert_eq!(*acquire(&first, 2).borrow(), 20);
    assert_eq!(*acquire(&next, 1).borrow(), 1);
}

#[test]
fn ordinary_startup_retains_native_shared_acquisition() {
    let instances = BackendInstances::new(false);
    for _ in 0..2 {
        assert_eq!(
            *instances
                .acquire(
                    1,
                    |_| panic!("ordinary worker created a private voice"),
                    |_| Ok(42)
                )
                .unwrap()
                .borrow(),
            42
        );
        instances.settle();
    }
}

/// An ordinary registry asks Prism for a backend once and then hands out
/// that instance for the rest of the session. Every acquire-and-free cycle
/// of Prism's OneCore backend leaks a USER object and two handles (measured
/// 2026-09-12), and the 3 s health probe re-acquires the main voice on every
/// pass when no screen reader is running.
#[test]
fn ordinary_registry_acquires_each_backend_once_per_session() {
    let instances = BackendInstances::new(false);
    let acquires = std::cell::Cell::new(0);
    for _ in 0..3 {
        let backend = instances
            .acquire(
                7,
                |_| panic!("ordinary worker created a private voice"),
                |_| {
                    acquires.set(acquires.get() + 1);
                    Ok(70)
                },
            )
            .unwrap();
        assert_eq!(*backend.borrow(), 70);
    }
    assert_eq!(
        acquires.get(),
        1,
        "the main voice was re-acquired on a later probe"
    );

    // A backend that is not there is asked for again next time: a screen
    // reader started mid-session must still be found.
    let misses = std::cell::Cell::new(0);
    for _ in 0..2 {
        let missing = instances.acquire(
            8,
            |_| panic!("ordinary worker created a private voice"),
            |_| {
                misses.set(misses.get() + 1);
                Err(prism::Error::NoBackend)
            },
        );
        assert!(missing.is_err());
    }
    assert_eq!(misses.get(), 2);
}
