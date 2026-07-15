"""The terminal's Career stats screen: a reviewable menu with rest status."""

import pygame
import pytest


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def select(menu, label):
    while not menu.items[menu.index].text.startswith(label):
        menu.handle_event(key_event(pygame.K_DOWN))
    menu.handle_event(key_event(pygame.K_RETURN))


@pytest.mark.smoke
def test_career_stats_is_a_reviewable_menu_with_rest_status():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.career_stats import CareerStatsState
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        app.ctx.profile = Profile(name="Stats", current_city="Austin")
        p = app.ctx.profile
        p.career.deliveries = 4
        p.career.on_time_deliveries = 3
        p.career.total_miles = 1234.0
        p.career.total_earnings = 5678.0
        app.push_state(CityMenuState(app.ctx))

        select(app.state, "Career stats")
        assert isinstance(app.state, CareerStatsState)
        labels = [item.text for item in app.state.items]
        assert any(label.startswith("Level 1 driver") for label in labels)
        # A level 1 driver holds nothing; the line still exists so the
        # screen always answers "what am I cleared to haul?"
        assert "Endorsements: none yet" in labels
        assert "Deliveries: 4, 75 percent on time" in labels
        assert "Lifetime miles: 1,234" in labels
        assert "Lifetime earnings: 5,678 dollars" in labels
        assert "Rest: fully rested" in labels
        assert any(label.startswith("Hours:") for label in labels)
        assert labels[-1] == "Back"

        # Enter repeats the current line without leaving the screen.
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CareerStatsState)

        # A tired driver hears fatigue instead of "fully rested".
        p.fatigue = 40.0
        p.hos.drive(120)
        app.state.refresh()
        labels = [item.text for item in app.state.items]
        assert "Rest: fatigue 40 percent" in labels
        assert "Rest: fully rested" not in labels

        # Endorsements are a reviewable record, not a one-time level-up
        # announcement: a driver holding reefer and high-value hears both.
        p.career.purchased_endorsements.extend(["refrigerated", "high_value"])
        app.state.refresh()
        labels = [item.text for item in app.state.items]
        assert "Endorsements: high-value, refrigerated" in labels

        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, CityMenuState)
    finally:
        app.shutdown()
