"""Driving school: sandboxed lessons that never touch the real career."""

import pygame
import pytest


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def select(menu, label):
    while not menu.items[menu.index].text.startswith(label):
        menu.handle_event(key_event(pygame.K_DOWN))
    menu.handle_event(key_event(pygame.K_RETURN))


@pytest.fixture
def school_app(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState

    app = App()
    app.ctx.profile = Profile(name="Student", current_city="denver_co_us")
    app.ctx.profile.money = 12345.0
    saves: list[str] = []
    monkeypatch.setattr(Profile, "save", lambda self, *a, **k: saves.append(self.name))
    app.push_state(CityMenuState(app.ctx))
    app.saves = saves
    yield app
    app.shutdown()


def test_school_lesson_is_a_sandbox_and_restores_the_real_profile(school_app):
    from freight_fate.states.driving_school import DrivingSchoolState, SchoolDrivingState

    app = school_app
    real = app.ctx.profile

    select(app.state, "Driving school")
    assert isinstance(app.state, DrivingSchoolState)

    select(app.state, "Lesson 1")
    assert isinstance(app.state, SchoolDrivingState)
    # The drive runs on a throwaway copy, not the career.
    assert app.ctx.school_sandbox
    assert app.ctx.profile is not real
    assert app.ctx.profile.name == "Student"

    # Sandbox saves never reach disk.
    app.ctx.save_profile()
    assert app.saves == []

    # Run the lesson: engine, parking brake, roll to 30, stop.
    lesson = app.state.tutorial
    drive = app.state
    lesson.begin()
    lesson.on_engine_started()
    assert lesson.stage == 1
    lesson.on_parking_brake_released()
    assert lesson.stage == 2
    drive.truck.velocity_mps = 31.0 * 0.44704
    lesson.update(1 / 60, drive.truck)
    assert lesson.stage == 3
    # Sandbox damage stays on the copy.
    app.ctx.profile.money -= 500.0
    drive.truck.velocity_mps = 0.0
    lesson.update(1 / 60, drive.truck)
    assert lesson.done

    # Lesson completion pops back to the school with the career restored.
    assert isinstance(app.state, DrivingSchoolState)
    assert not app.ctx.school_sandbox
    assert app.ctx.profile is real
    assert app.ctx.profile.money == 12345.0


def test_escaping_a_lesson_restores_the_profile_too(school_app):
    from freight_fate.states.driving_school import DrivingSchoolState

    app = school_app
    real = app.ctx.profile
    select(app.state, "Driving school")
    select(app.state, "Lesson 1")
    assert app.ctx.profile is not real

    # Any pop of the practice drive restores, no matter how it happens.
    app.pop_state()
    assert isinstance(app.state, DrivingSchoolState)
    assert not app.ctx.school_sandbox
    assert app.ctx.profile is real


def test_real_saves_still_write_after_school(school_app):
    app = school_app
    select(app.state, "Driving school")
    select(app.state, "Lesson 1")
    app.pop_state()  # leave the lesson
    app.ctx.save_profile()
    assert app.saves == ["Student"]
