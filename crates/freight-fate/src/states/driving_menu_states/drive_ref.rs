//! [`DriveRef`]: how a screen the drive pushed reaches the drive underneath
//! it.
//!
//! # Why this exists
//!
//! Python screens held `self.driving`, a plain reference to the
//! `DrivingState` sitting below them on the stack, and read or wrote it
//! whenever they liked. Rust cannot: the stack owns the drive as
//! `Rc<RefCell<dyn State>>`, and while the app is dispatching to a state that
//! cell is borrowed for the whole handler. So a screen keeps the drive's
//! `Rc` and borrows it per call.
//!
//! That borrow succeeds everywhere except one moment: the instant the drive
//! itself pushes a screen, from inside its own key handler or update, the
//! drive is still borrowed by the app. The screens the drive pushes therefore
//! do their `enter()` work in the push helper -- which HAS `&mut
//! DrivingState` -- and are pushed with `should_enter = false`
//! ([`push_over_drive`]). Nothing about the spoken order changes: the entry
//! announcement still happens at the point Python's `enter()` ran. Every
//! later call (a menu row, a re-entry when a submenu pops, `lines()`) runs
//! with the drive free.
//!
//! # The two empties
//!
//! `with` / `read` / `call` answer `None` for two unrelated reasons, and the
//! difference matters enough that they behave differently. **No drive** is
//! legitimate and quiet: a test drove the screen without pushing a drive under
//! it. **Already borrowed** is never a state of the world -- it means code
//! that already holds the drive reached for it again instead of passing down
//! the one it has -- so it trips a `debug_assert!` naming the call site, and
//! logs a warning in a shipped build. See `nested_borrow` for why: a caller
//! that cannot tell the two apart guesses a default, and a guess said aloud is
//! a lie to a player who has nothing else to go on.

use std::panic::Location;
use std::rc::Rc;

use crate::app::{share, GameContext, SharedState};
use crate::states::base::State;
use crate::states::driving::DrivingState;
use crate::states::driving_school::SchoolDrivingState;

/// A handle on the drive a screen is covering.
///
/// Empty only where a screen was built without one (never in the game; a
/// test that drives a screen without pushing its drive gets a screen that
/// quietly answers nothing rather than a panic).
#[derive(Default)]
pub struct DriveRef(Option<SharedState>);

impl Clone for DriveRef {
    fn clone(&self) -> Self {
        DriveRef(self.0.as_ref().map(Rc::clone))
    }
}

/// The drive was already borrowed further up this same call stack.
///
/// This is never a state of the world, only ever a programming error: some
/// caller that already holds the drive reached for it a second time instead of
/// passing down the one it has. Answering `None` for it is what let the rest
/// stop say "tank is full" over forty gallons of a hundred and fifty, and what
/// emptied the pause menu after a roadside repair -- the caller cannot tell
/// this apart from "there is no drive", so it picks a plausible default and
/// the plausible default is a lie in a player's ear.
///
/// So it fails loudly where a bench or the test suite will catch it, and only
/// warns in a shipped build, where a panic would cost the player their drive.
#[cold]
#[inline(never)]
fn nested_borrow(method: &str, caller: &Location<'_>) {
    debug_assert!(
        false,
        "DriveRef::{method} at {caller}: the drive is already borrowed further \
         up this call stack. Pass the drive that outer borrow already holds \
         down to this code instead of borrowing it again."
    );
    log::warn!(
        "DriveRef::{method} at {caller}: the drive is already borrowed further \
         up this call stack, so this answered with nothing. That is a bug: the \
         caller should pass the borrowed drive down."
    );
}

/// The `DrivingState` inside a state on the stack, whichever wrapper it wears.
///
/// The driving school subclassed `DrivingState` in Python; here it wraps one
/// ([`SchoolDrivingState`]), so a screen pushed from a practice drive has to
/// look through the wrapper as well.
fn as_driving(state: &mut dyn State) -> Option<&mut DrivingState> {
    let any = state.as_any_mut();
    if any.is::<DrivingState>() {
        return any.downcast_mut::<DrivingState>();
    }
    any.downcast_mut::<SchoolDrivingState>()
        .map(SchoolDrivingState::drive_mut)
}

impl DriveRef {
    /// The drive that is pushing this screen: the active state, taken
    /// without borrowing it (the drive is inside its own handler right now).
    pub fn active(ctx: &GameContext) -> DriveRef {
        DriveRef(ctx.state())
    }

    /// A handle on an already-shared drive (the test rig, and the harness).
    pub fn of(state: &SharedState) -> DriveRef {
        DriveRef(Some(Rc::clone(state)))
    }

    /// No drive at all.
    pub fn empty() -> DriveRef {
        DriveRef(None)
    }

    pub fn is_empty(&self) -> bool {
        self.0.is_none()
    }

    /// The shared state itself, for a screen that has to compare identity
    /// (`ctx._app.state is driving`).
    pub fn shared(&self) -> Option<&SharedState> {
        self.0.as_ref()
    }

    /// True when the drive is the active state right now
    /// (`ctx._app.state is self.driving`).
    pub fn is_active(&self, ctx: &GameContext) -> bool {
        match (self.0.as_ref(), ctx.state()) {
            (Some(mine), Some(top)) => Rc::ptr_eq(mine, &top),
            _ => false,
        }
    }

    /// Run `f` on the drive. `None` when there is no drive.
    ///
    /// A drive that is already borrowed further up the stack also answers
    /// `None`, but noisily -- see `nested_borrow`.
    #[track_caller]
    pub fn read<R>(&self, f: impl FnOnce(&mut DrivingState) -> R) -> Option<R> {
        let shared = self.0.as_ref()?;
        let Ok(mut borrowed) = shared.try_borrow_mut() else {
            nested_borrow("read", Location::caller());
            return None;
        };
        let drive = as_driving(&mut *borrowed)?;
        Some(f(drive))
    }

    /// Run `f` on the drive with the context. Same availability rule.
    #[track_caller]
    pub fn with<R>(
        &self,
        ctx: &mut GameContext,
        f: impl FnOnce(&mut DrivingState, &mut GameContext) -> R,
    ) -> Option<R> {
        let shared = self.0.as_ref()?;
        let Ok(mut borrowed) = shared.try_borrow_mut() else {
            nested_borrow("with", Location::caller());
            return None;
        };
        let drive = as_driving(&mut *borrowed)?;
        Some(f(drive, ctx))
    }

    /// Run `f` on the screen, the context, and the drive together.
    ///
    /// Takes `self` by value so the call site clones the handle first
    /// (`self.driving.clone().call(self, ctx, ...)`), which is what lets the
    /// screen be borrowed mutably at the same time.
    #[track_caller]
    pub fn call<S, R>(
        self,
        state: &mut S,
        ctx: &mut GameContext,
        f: impl FnOnce(&mut S, &mut GameContext, &mut DrivingState) -> R,
    ) -> Option<R> {
        let shared = self.0.as_ref()?;
        let Ok(mut borrowed) = shared.try_borrow_mut() else {
            nested_borrow("call", Location::caller());
            return None;
        };
        let drive = as_driving(&mut *borrowed)?;
        Some(f(state, ctx, drive))
    }
}

/// Push a screen the drive built over the drive itself.
///
/// The screen's `enter()` has already run (in the push helper, which holds
/// `&mut DrivingState`), so the stack takes it without entering it again.
pub fn push_over_drive<S: State + 'static>(ctx: &mut GameContext, state: S) {
    ctx.push_state_with(state, false);
}

/// Replace the drive with a screen it built (`ctx.replace_state(X)`).
///
/// Same rule: the screen has already entered, so `reentry` is false. The
/// drive's own `exit` is deferred by the stack, because the drive is
/// borrowed for the handler that asked for this.
pub fn replace_drive_with<S: State + 'static>(ctx: &mut GameContext, state: S) {
    ctx.replace_shared_with(share(state), true, false);
}
