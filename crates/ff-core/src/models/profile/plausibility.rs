//! The one arithmetic check the load gate makes: a bank balance no career of
//! this game could hold.
//!
//! The signature catches a save edited on disk. It cannot catch a balance
//! rewritten in memory while the game runs, because the game then signs the
//! edited number itself. This check reads the number instead of the file.
//!
//! The server's validator holds money to starting cash plus lifetime earnings
//! plus the outstanding advance, to the dollar, and refuses the upload when it
//! is over. It does NOT mark the career, because arithmetic that tight has
//! accused honest drivers before (the owner-operator start, debt careers). A
//! mark made here is sticky and spoken, so the ceiling here is deliberately
//! looser and is derived, not tuned: every dollar the game can credit is
//! either
//!
//! - the richest career start ([`all_start_options`]),
//! - delivery pay, all of which is counted in `career.total_earnings`,
//! - a pay advance, capped at [`PAY_ADVANCE_LIMIT`],
//! - or equipment handed back (a repossession's equity, the carrier's buy-back
//!   on a return to company driving), which pays [`REPOSSESSION_EQUITY_SHARE`]
//!   of catalog price. A driver can hold each catalog tractor and trailer once,
//!   so one hand-back can never pay more than that share of the whole catalog.
//!
//! An honest balance sits under the sum of those four. A typed-in 999,999,999
//! does not.

use crate::models::economy::PAY_ADVANCE_LIMIT;
use crate::models::solvency::REPOSSESSION_EQUITY_SHARE;
use crate::models::start_options::all_start_options;
use crate::models::trailers::TRAILER_CATALOG;
use crate::models::trucks::TRUCK_CATALOG;

/// Rounding room: balances are kept to the cent, the terms above are not.
const CEILING_SLACK: f64 = 1.0;

/// The most any single equipment hand-back could pay: the equity share of
/// every tractor and trailer in the catalog at once.
pub fn equipment_hand_back_ceiling() -> f64 {
    let tractors: f64 = TRUCK_CATALOG.values().map(|model| model.price).sum();
    let trailers: f64 = TRAILER_CATALOG
        .iter()
        .map(|trailer| trailer.purchase_price)
        .sum();
    (tractors + trailers) * REPOSSESSION_EQUITY_SHARE
}

/// The highest balance a career with these lifetime earnings could hold.
pub fn money_ceiling(total_earnings: f64) -> f64 {
    let richest_start = all_start_options()
        .iter()
        .map(|option| option.starting_money)
        .fold(0.0, f64::max);
    richest_start
        + total_earnings.max(0.0)
        + PAY_ADVANCE_LIMIT
        + equipment_hand_back_ceiling()
        + CEILING_SLACK
}

/// Whether `money` is more than the career behind it could have made. A
/// balance that is not a number at all counts: no honest save holds one.
pub fn money_is_impossible(money: f64, total_earnings: f64) -> bool {
    !money.is_finite() || !total_earnings.is_finite() || money > money_ceiling(total_earnings)
}
