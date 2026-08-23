//! Spoken in-cab Record of Duty Status screens (port of
//! `freight_fate/states/logbook.py`).
//!
//! The Python functions took the optional `DrivingState` to read
//! `driving.trip.game_minutes`; here the caller passes that number
//! (`trip_game_minutes`, `None` when not driving), so the logbook does not
//! depend on the driving state's type.

use ff_core::sim::hos::{clock_text, duration_text, duty_status_label};

use crate::app::GameContext;
use crate::impl_state_for_menu;
use crate::states::base::{Menu, MenuCore, MenuItem};

/// The logbook as spoken lines: status, hours summary, today's totals, and
/// the recent entries.
pub fn logbook_lines(ctx: &GameContext, trip_game_minutes: Option<f64>) -> Vec<String> {
    let Some(p) = ctx.profile.as_ref() else {
        return Vec::new();
    };
    let now = current_hour(p.game_hours, trip_game_minutes);
    let log = &p.duty_log;
    let day_start = (now / 24.0).floor() * 24.0;
    let totals = log.totals_since(day_start, now);
    let mut lines = vec![
        format!(
            "Current duty status: {}",
            duty_status_label(log.current_status())
        ),
        p.hos
            .summary(&ctx.settings.hos_mode)
            .trim_end_matches('.')
            .to_string(),
        format!(
            "Today's totals: driving {}, on duty not driving {}, off duty {}, sleeper berth {}.",
            duration_text(totals.driving),
            duration_text(totals.on_duty_not_driving),
            duration_text(totals.off_duty),
            duration_text(totals.sleeper_berth),
        ),
    ];
    let recent = log.recent(8);
    if recent.is_empty() {
        lines.push("No logbook entries yet.".to_string());
        return lines;
    }
    lines.push("Recent logbook entries:".to_string());
    for segment in recent {
        let note = if segment.note.is_empty() {
            String::new()
        } else {
            format!(", {}", segment.note)
        };
        lines.push(format!(
            "{} to {}, {}, {}, {}{note}.",
            clock_text(segment.start_hour),
            clock_text(segment.end_hour),
            duty_status_label(&segment.status),
            duration_text(segment.duration_hours()),
            segment.location,
        ));
    }
    lines
}

/// What a roadside officer reads off the logbook.
pub fn traffic_stop_logbook_summary(ctx: &GameContext, trip_game_minutes: Option<f64>) -> String {
    let lines = logbook_lines(ctx, trip_game_minutes);
    if lines.len() <= 3 {
        return "Logbook has no recent duty entries yet.".to_string();
    }
    let latest = &lines[lines.len() - 1];
    let totals = lines[2]
        .strip_prefix("Today's totals: ")
        .unwrap_or(&lines[2]);
    format!("Logbook shows {totals} Latest entry: {latest}")
}

/// A reviewable spoken Record of Duty Status.
pub struct LogbookState {
    menu: MenuCore<Self>,
    /// `driving.trip.game_minutes` when opened from a drive.
    pub trip_game_minutes: Option<f64>,
}

impl LogbookState {
    /// `LogbookState(ctx, driving=None)`.
    pub fn new(trip_game_minutes: Option<f64>) -> Self {
        Self {
            menu: MenuCore::new("Logbook").with_intro_help(
                "Use up and down arrows to review logbook lines. Enter repeats the \
                 current line. Escape goes back.",
            ),
            trip_game_minutes,
        }
    }
}

impl Default for LogbookState {
    fn default() -> Self {
        Self::new(None)
    }
}

impl Menu for LogbookState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let text = format!("{}. {}", self.menu.title, self.current_text(ctx));
        ctx.say(&text);
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let mut items: Vec<MenuItem<Self>> = logbook_lines(ctx, self.trip_game_minutes)
            .into_iter()
            .map(|line| {
                let spoken = line.clone();
                MenuItem::new(line, move |_s: &mut Self, ctx| ctx.say(&spoken))
                    .help("Repeat this logbook line.")
            })
            .collect();
        items.push(
            MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx))
                .help("Return to the previous menu."),
        );
        items
    }
}

impl_state_for_menu!(LogbookState);

fn current_hour(game_hours: f64, trip_game_minutes: Option<f64>) -> f64 {
    match trip_game_minutes {
        None => game_hours,
        Some(minutes) => game_hours + minutes / 60.0,
    }
}
