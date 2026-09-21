//! This week's US average diesel pump price, keyless.
//!
//! The Energy Information Administration surveys retail diesel every Monday
//! (series GASDESW, "US Diesel Sales Price", dollars per gallon, all types).
//! EIA's own API wants a registered key; the St. Louis Fed republishes the
//! same series as a plain CSV with no key at all, one row per week, oldest
//! first. That CSV is what this reads: the last row with a number in it is
//! this week's price. A row whose value is "." is a week the survey missed,
//! and is skipped.
//!
//! The price is a READ value (the survey's own number) and the economy
//! derives every region from it; nothing here is guessed. One fetch a
//! session is plenty, since the number changes once a week, and it is never
//! waited for: the seeded market stands until the answer lands.

use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

use crate::sim::real_traffic::{lock_unpoisoned, Clock, HttpTransport, NoTransport};
use crate::sim::real_weather::monotonic_clock;

/// The keyless CSV of EIA's weekly US diesel retail price.
pub const FRED_DIESEL_URL: &str = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GASDESW";
/// The feed moves once a week; ask again after this long.
pub const FUEL_PRICE_CACHE_TTL_S: f64 = 6.0 * 60.0 * 60.0;
/// A failed fetch is left alone this long before another try.
pub const FUEL_PRICE_RETRY_AFTER_S: f64 = 5.0 * 60.0;
/// A weekly retail diesel price outside this band is not a price the survey
/// has ever published; treat it as a broken row.
pub const PLAUSIBLE_PRICE_RANGE: (f64, f64) = (1.0, 12.0);
const FETCH_TIMEOUT_S: f64 = 8.0;
const USER_AGENT: &str = "FreightFate/1.9 (accessible trucking game; https://orinks.net)";

/// One week's survey figure.
#[derive(Debug, Clone, PartialEq)]
pub struct LiveDieselPrice {
    /// Dollars per gallon, as published.
    pub per_gal: f64,
    /// The survey week, `YYYY-MM-DD`, as published.
    pub week: String,
}

/// The latest priced week in a FRED CSV, or None when the text holds none.
pub fn parse_fred_csv(text: &str) -> Option<LiveDieselPrice> {
    text.lines()
        .rev()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .find_map(|line| {
            let (week, value) = line.split_once(',')?;
            let per_gal: f64 = value.trim().parse().ok()?;
            let (low, high) = PLAUSIBLE_PRICE_RANGE;
            (per_gal.is_finite() && (low..=high).contains(&per_gal)).then(|| LiveDieselPrice {
                per_gal,
                week: week.trim().to_string(),
            })
        })
}

#[derive(Default)]
struct Inner {
    cached: Option<(f64, LiveDieselPrice)>,
    inflight: bool,
    failed_at: Option<f64>,
}

#[derive(Clone)]
struct Shared {
    inner: Arc<Mutex<Inner>>,
    transport: Arc<dyn HttpTransport>,
    clock: Clock,
}

/// Cached, non-blocking source of this week's diesel price.
///
/// `request()` starts a background fetch when nothing fresh is cached;
/// `get()` answers from the cache and never waits.
pub struct FuelPriceProvider {
    shared: Shared,
    threaded: bool,
    workers: Mutex<Vec<JoinHandle<()>>>,
}

impl FuelPriceProvider {
    pub fn new(transport: Arc<dyn HttpTransport>) -> Self {
        Self {
            shared: Shared {
                inner: Arc::new(Mutex::new(Inner::default())),
                transport,
                clock: monotonic_clock(),
            },
            threaded: true,
            workers: Mutex::new(Vec::new()),
        }
    }

    /// No network: every fetch fails and only a seeded price answers.
    pub fn offline() -> Self {
        Self::new(Arc::new(NoTransport)).with_threaded(false)
    }

    pub fn with_threaded(mut self, threaded: bool) -> Self {
        self.threaded = threaded;
        self
    }

    pub fn with_clock(mut self, clock: Clock) -> Self {
        self.shared.clock = clock;
        self
    }

    /// Put a price in the cache as a fresh fetch would (tests).
    pub fn seed(&self, price: LiveDieselPrice) {
        let now = (self.shared.clock)();
        lock_unpoisoned(&self.shared.inner).cached = Some((now, price));
    }

    /// The cached price, or None when nothing has answered yet.
    pub fn get(&self) -> Option<LiveDieselPrice> {
        lock_unpoisoned(&self.shared.inner)
            .cached
            .as_ref()
            .map(|(_, price)| price.clone())
    }

    /// Make sure a price is cached or on its way. Never blocks.
    pub fn request(&self) {
        let now = (self.shared.clock)();
        {
            let mut inner = lock_unpoisoned(&self.shared.inner);
            if inner.inflight {
                return;
            }
            if let Some((fetched_at, _)) = &inner.cached {
                if now - fetched_at < FUEL_PRICE_CACHE_TTL_S {
                    return;
                }
            }
            if let Some(failed) = inner.failed_at {
                if now - failed < FUEL_PRICE_RETRY_AFTER_S {
                    return;
                }
            }
            inner.inflight = true;
        }
        let shared = self.shared.clone();
        let job = move || fetch_price(&shared);
        if self.threaded {
            let handle = std::thread::Builder::new()
                .name("diesel-price".to_string())
                .spawn(job)
                .expect("spawn fuel price worker");
            lock_unpoisoned(&self.workers).push(handle);
        } else {
            job();
        }
    }

    /// Wait for every worker spawned so far (a test aid).
    pub fn join_background(&self) {
        let handles: Vec<JoinHandle<()>> = lock_unpoisoned(&self.workers).drain(..).collect();
        for handle in handles {
            let _ = handle.join();
        }
    }
}

fn fetch_price(shared: &Shared) {
    let result = shared.transport.get(
        FRED_DIESEL_URL,
        &[("User-Agent", USER_AGENT), ("Accept", "text/csv")],
        FETCH_TIMEOUT_S,
    );
    let now = (shared.clock)();
    let mut inner = lock_unpoisoned(&shared.inner);
    inner.inflight = false;
    let parsed = result
        .ok()
        .and_then(|body| String::from_utf8(body).ok())
        .and_then(|text| parse_fred_csv(&text));
    match parsed {
        Some(price) => {
            log::info!(
                "Live diesel price: {} dollars per gallon, survey week {}",
                price.per_gal,
                price.week
            );
            inner.failed_at = None;
            inner.cached = Some((now, price));
        }
        None => {
            log::debug!("Live diesel price fetch failed or held no priced week");
            inner.failed_at = Some(now);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_the_last_priced_week_wins_and_missing_weeks_are_skipped() {
        let csv = "observation_date,GASDESW\n2026-08-24,5.812\n2026-08-31,5.901\n2026-09-07,5.967\n2026-09-14,.\n";
        let price = parse_fred_csv(csv).expect("a priced week");
        assert_eq!(price.per_gal, 5.967);
        assert_eq!(price.week, "2026-09-07");
        assert_eq!(parse_fred_csv("observation_date,GASDESW\n"), None);
        assert_eq!(parse_fred_csv("<html>not a feed</html>"), None);
        // A number no survey ever published is a broken row, not a price.
        assert_eq!(parse_fred_csv("2026-09-07,59.67"), None);
    }

    #[test]
    fn test_offline_provider_answers_only_what_was_seeded() {
        let provider = FuelPriceProvider::offline();
        assert_eq!(provider.get(), None);
        provider.request();
        assert_eq!(provider.get(), None);
        provider.seed(LiveDieselPrice {
            per_gal: 5.967,
            week: "2026-09-07".to_string(),
        });
        assert_eq!(provider.get().map(|p| p.per_gal), Some(5.967));
    }
}
