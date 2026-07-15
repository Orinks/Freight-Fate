"""The driving school: spoken lessons on a consequence-free practice road.

The school runs the real driving engine on a disposable copy of the
player's profile: every lesson consequence -- wear, fuel, money, hours,
fatigue -- lands on the copy and dies with the lesson. One guard in
``GameContext.save_profile`` keeps the sandbox off disk, and the practice
drive restores the real profile on every exit path.

Lessons are instructor state machines that duck-type the first-run
``Tutorial`` (see driving_core): the driving code already calls
``on_engine_started`` / ``on_parking_brake_released`` / ``on_gear_engaged``
/ ``update``, so a lesson plugs into those hooks unchanged. Instruction
stays on the speech channel (screen-reader rate, comma repeat, verbosity
all keep working); recorded instructor flavor lines can hang off the same
stage transitions later.
"""

from __future__ import annotations

from ..data.world_models import Leg, Route
from ..models.jobs import CARGO_CATALOG, Job
from ..models.profile import Profile
from .base import MenuItem, MenuState
from .driving import DrivingState
from .driving_core import DRIVE_PHASE_SCHOOL

PRACTICE_ROAD_MILES = 25.0  # long enough that no lesson meets the end of it


def _enter_sandbox(ctx) -> None:
    """Swap the live profile for a throwaway copy; idempotent."""
    if getattr(ctx, "school_sandbox", False):
        return
    ctx.school_real_profile = ctx.profile
    ctx.profile = Profile.from_dict(ctx.profile.to_dict())
    ctx.school_sandbox = True


def _leave_sandbox(ctx) -> None:
    """Restore the real profile; safe to call from every exit path."""
    if not getattr(ctx, "school_sandbox", False):
        return
    ctx.profile = ctx.school_real_profile
    ctx.school_real_profile = None
    ctx.school_sandbox = False


def _practice_route(ctx) -> tuple[Job, Route]:
    """A flat, empty stretch of road going nowhere, starting here."""
    p = ctx.profile
    city = ctx.world.resolve_city_key(p.current_city)
    leg = Leg(
        a=city,
        b=city,
        miles=PRACTICE_ROAD_MILES,
        highway="the practice road",
        terrain="flat",
        stops=(),
    )
    job = Job(
        CARGO_CATALOG["general"],
        0.0,
        city,
        "the training yard",
        city,
        PRACTICE_ROAD_MILES,
        0.0,
        24.0,
        origin_type="company_terminal",
        destination_location="the training yard",
        destination_type="company_terminal",
        bobtail=True,
    )
    return job, Route([city, city], [leg])


class RollingBasicsLesson:
    """Lesson 1: engine, air, parking brake, roll to 30, stop.

    Duck-types the first-run Tutorial so the existing driving hooks drive
    the lesson. Stages: 0 start the engine, 1 air and parking brake (or
    first gear on a manual), 2 accelerate to 30, 3 brake to a full stop.
    """

    ROLL_MPH = 30.0
    STOP_MPH = 0.5
    HINT_S = 30.0

    def __init__(self, ctx, driving) -> None:
        self.ctx = ctx
        self.driving = driving
        self.stage = 0
        self.done = False
        self._timer = 0.0
        self._hinted = False

    def _say(self, text: str) -> None:
        self.ctx.say(text, interrupt=False)

    def _advance(self, stage: int) -> None:
        self.stage = stage
        self._timer = 0.0
        self._hinted = False

    def begin(self) -> None:
        self._say(
            "Welcome to the driving school. This is the practice road: "
            "flat, empty, and none of it counts. Nothing you do here "
            "touches your career, your truck, or your money. "
            "Lesson one, rolling basics. First: press "
            f"{self.ctx.control_hint('engine')} to start the engine."
        )

    def on_engine_started(self) -> None:
        if self.stage != 0:
            return
        self._advance(1)
        if self.ctx.settings.automatic_transmission:
            self._say(
                "Engine running. Let the air pressure build. When you hear "
                f"air ready, press {self.ctx.control_hint('parking_brake')} "
                "to release the parking brake, then hold "
                f"{self.ctx.control_hint('accelerate')} to accelerate. "
                "The transmission shifts for you."
            )
        else:
            self._say(
                "Engine running. Let the air pressure build. When you hear "
                f"air ready, press {self.ctx.control_hint('parking_brake')} "
                "to release the parking brake, hold "
                f"{self.ctx.control_hint('clutch')}, select "
                f"{self.ctx.control_hint('gear_first')} for first gear, and "
                "release the clutch."
            )

    def on_parking_brake_released(self) -> None:
        if self.stage != 1:
            return
        if self.ctx.settings.automatic_transmission:
            self._advance(2)
            self._say(
                "Parking brake released. Now hold "
                f"{self.ctx.control_hint('accelerate')} and take it up to "
                "thirty. I will tell you when you are there."
            )
        else:
            self._timer = 0.0
            self._say("Parking brake released. Now shift into first gear.")

    def on_gear_engaged(self) -> None:
        if self.stage != 1:
            return
        self._advance(2)
        self._say(
            "In gear. Now hold "
            f"{self.ctx.control_hint('accelerate')} and take it up to "
            "thirty. I will tell you when you are there."
        )

    def update(self, dt: float, truck) -> None:
        if self.done:
            return
        self._timer += dt
        if self.stage == 2 and truck.speed_mph >= self.ROLL_MPH:
            self._advance(3)
            self._say(
                "Thirty. Nicely done. Now ease off and brake gently with "
                f"{self.ctx.control_hint('brake')} to a full stop. "
                "Smooth is the goal; your freight never wants to meet the cab."
            )
        elif self.stage == 3 and truck.speed_mph <= self.STOP_MPH:
            self.done = True
            self._say(
                "Full stop. That is the whole rhythm of the job: build it "
                "up smooth, bring it down smooth. Lesson one complete. "
                "Returning you to the school."
            )
            self.driving.finish_lesson()
        elif self._timer > self.HINT_S and not self._hinted:
            self._hinted = True
            if self.stage == 0:
                self._say(
                    f"Reminder: press {self.ctx.control_hint('engine')} to "
                    "start the engine."
                )
            elif self.stage == 1 and truck.parking_brake:
                self._say(
                    "Reminder: wait for air pressure to reach one hundred "
                    f"psi, then press {self.ctx.control_hint('parking_brake')} "
                    "to release the parking brake."
                )
            elif self.stage == 2:
                self._say(
                    "Reminder: hold "
                    f"{self.ctx.control_hint('accelerate')} until you reach "
                    "thirty miles per hour."
                )


LESSONS = (
    (
        "Lesson 1: Rolling basics",
        RollingBasicsLesson,
        "Start the engine, build air, release the parking brake, take the "
        "truck to thirty, and brake to a smooth full stop.",
    ),
)


class SchoolDrivingState(DrivingState):
    """A practice drive: the real engine, a sandbox profile, an instructor."""

    def __init__(self, ctx, lesson_cls) -> None:
        job, route = _practice_route(ctx)
        super().__init__(ctx, job, route, phase=DRIVE_PHASE_SCHOOL)
        # The instructor rides the first-run tutorial's hooks; the school
        # replaces whatever the base state decided about the tutorial.
        self.tutorial = lesson_cls(ctx, self)
        self._lesson_finished = False

    def finish_lesson(self) -> None:
        if self._lesson_finished:
            return
        self._lesson_finished = True
        self.ctx.pop_state()

    def exit(self) -> None:
        super().exit()
        # Every path out of a practice drive restores the real profile:
        # lesson completion, Escape, even an abandon from the pause menu.
        _leave_sandbox(self.ctx)


class DrivingSchoolState(MenuState):
    title = "Driving school"
    intro_help = (
        "Pick a lesson. Lessons run on a practice road where nothing "
        "counts: no money, no wear, no hours. Escape returns to the "
        "terminal."
    )

    def enter(self) -> None:
        # Belt and suspenders: if a practice drive ever unwinds without
        # its exit hook, re-entering the school still restores the player.
        _leave_sandbox(self.ctx)
        super().enter()

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                name,
                lambda cls=lesson_cls: self._start(cls),
                help=blurb,
            )
            for name, lesson_cls, blurb in LESSONS
        ]
        items.append(
            MenuItem("Back to terminal", self.go_back, help="Leave the school.")
        )
        return items

    def _start(self, lesson_cls) -> None:
        _enter_sandbox(self.ctx)
        self.ctx.push_state(SchoolDrivingState(self.ctx, lesson_cls))

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
