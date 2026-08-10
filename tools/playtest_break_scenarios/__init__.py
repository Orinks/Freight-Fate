"""Scenario modules for tools/playtest_break.py, split by system family.

Importing this package registers every scenario into
``playtest_break.SCENARIOS`` via the ``@scenario`` decorator each module
uses. Add a new family by creating a module here and importing it below;
add a new scenario to an existing family by adding a decorated function to
its module.
"""

from __future__ import annotations

from . import (
    assists,
    career_economy,
    dispatch_saveload,
    driving_physics,
    radio_weather,
    resources,
    settings_misc,
)

__all__ = [
    "driving_physics",
    "assists",
    "resources",
    "career_economy",
    "dispatch_saveload",
    "radio_weather",
    "settings_misc",
]
