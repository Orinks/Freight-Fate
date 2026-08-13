# ruff: noqa: F403,F405
from __future__ import annotations

from .base import end_sentence
from .driving_core import *
from .driving_rest_states import ShoulderSleepConfirmationState


def _restore_checkpoint_driver_state(ctx: GameContext, driving: DrivingState) -> None:
    """Discard unsaved driver state before returning to the title.

    The active-trip snapshot represents the last durable route checkpoint.
    HOS and fatigue are mutated directly on the profile while driving, so they
    must be restored before a later application shutdown saves the profile.
    """
    profile = getattr(ctx, "profile", None)
    if profile is None:
        return
    snapshot = profile.active_trip

    if not isinstance(snapshot, dict):
        return

    saved_hos = snapshot.get("hos")
    if isinstance(saved_hos, dict):
        profile.hos = HosClock.from_dict(saved_hos)
        driving.hos = profile.hos

    saved_fatigue = snapshot.get("fatigue")
    if saved_fatigue is not None:
        profile.fatigue = max(0.0, min(100.0, float(saved_fatigue)))


class PauseMenuState(MenuState):
    title = "Paused"

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def enter(self) -> None:
        self.ctx.audio.play("ui/pause")
        self.ctx.audio.stop_world()
        # Everything the road had handed the voice belongs to the mile the
        # player just stopped on. Left alone it sits in the event channel's
        # own queue and is performed over the pause menu, or replayed in full
        # on resume (tester transcript, 2026-08-11).
        self.ctx.pause_event_speech()
        self.driving._pending_ambient_event = None
        self.driving._reverse_cue_active = False
        self.driving._air_cue_active = False
        self.driving._jake_cue_key = None
        super().enter()

    def announce_entry(self) -> None:
        # Pausing and resuming is where the player is, not something that
        # happened on the road. Logging it would leave a "Paused." between
        # every pair of announcements for anyone who checks the menu mid-run.
        self.ctx.say(f"{end_sentence(self.title)}", review=False)
        self.ctx.say(f"{self.current_text()}", interrupt=False, review=False)

    def presence(self):
        from ..discord_presence import PresenceState

        base = self.driving.presence()
        detail = base.detail if base is not None else ""
        return PresenceState("Paused", detail)

    def online_presence(self):
        # A paused player is not actively hauling, so they leave the public
        # drivers board as though they went off duty; the service's off-duty
        # grace absorbs a quick pause-and-resume without bouncing the row.
        # Discord presence (above) still shows "Paused" while the menu is up.
        return None

    def build_items(self) -> list[MenuItem]:
        drive_label = "pickup drive" if self.driving.phase == DRIVE_PHASE_PICKUP else "delivery"
        items = [
            MenuItem("Resume driving", self._resume, help=f"Return to the active {drive_label}."),
            MenuItem(
                "Trip status",
                self._status,
                help="Hear cargo, objective, route progress, and time used.",
            ),
            MenuItem(
                "Controls and help",
                self._controls,
                help="Open the how-to-play reference at the driving keys. "
                "Left and Right arrows change pages, Up and Down read "
                "line by line, Escape returns here.",
            ),
            MenuItem(
                "Learn game sounds",
                self._learn_sounds,
                help="Play any sound the road uses and hear what it means. "
                "The drive is paused while you listen.",
            ),
            MenuItem(
                self._mechanic_label,
                self._mechanic,
                help="A mobile mechanic patches the truck up enough to "
                "drive on. Costs much more than a garage repair, "
                "takes an hour and a half, and the bill is due even "
                "if it puts you in debt.",
            ),
            MenuItem(
                "Settings",
                self._settings,
                help="Change units, transmission, volumes, weather, "
                "voices, update channel, and trip pacing.",
            ),
        ]
        if self.driving.truck.chains_on:
            items.append(
                MenuItem(
                    f"Remove snow chains: about {CHAIN_REMOVE_MIN:.0f} minutes",
                    self._remove_chains,
                    help="Pull the chains off the drives and stow them. Do it "
                    "as soon as the road is bare again; chains grind apart "
                    "fast on pavement.",
                )
            )
        elif self.ctx.profile.chains_owned and self.ctx.profile.chain_wear_pct < 100:
            items.append(
                MenuItem(
                    self._install_chains_label,
                    self._install_chains,
                    help="Stop, kneel on the shoulder, and hang the chain set "
                    "on the drives. Chains bite snow and glare ice like "
                    "nothing else. Keep it near chain speed, about thirty "
                    "miles per hour, and pull them the moment the road is "
                    "bare. Installing in the dark takes longer and takes "
                    "more out of you.",
                )
            )
        items += [
            MenuItem(
                "Drivers board",
                self._drivers_board,
                help="Hear who is hauling right now on the public orinks.net "
                "drivers board. Viewing the board shares nothing about you.",
            ),
            MenuItem(
                "Abandon job",
                self._abandon,
                help="Give up this job. Costs five hundred dollars and "
                "reputation, and returns you to the origin city.",
            ),
            MenuItem(
                "Quit to main menu",
                self._quit_to_menu,
                help="You can only save at a stop, so this drive is not "
                "saved in progress. It resumes from your last stop "
                "when you continue. Use Abandon job to drop the load.",
            ),
        ]
        if self.driving.emergency_shoulder_sleep_reason() is not None:
            items.insert(
                5,
                MenuItem(
                    "Emergency shoulder sleep",
                    self._emergency_shoulder_sleep,
                    help="Emergency-only poor sleep on the shoulder. Resets hours "
                    "of service, but fatigue remains, you may be ticketed, "
                    "minor truck damage can happen, and the deadline keeps "
                    "running.",
                ),
            )
        return items

    def go_back(self) -> None:
        self._resume()

    def _mechanic_label(self) -> str:
        damage = self.driving.truck.damage_pct
        if damage <= FIELD_REPAIR_DAMAGE_PCT:
            return "Call a roadside mechanic: not needed yet"
        cost = road_repair_cost(damage, FIELD_REPAIR_DAMAGE_PCT, MECHANIC_CALLOUT_FEE)
        return f"Call a roadside mechanic: {cost:,.0f} dollars"

    def _mechanic(self) -> None:
        d = self.driving
        damage = d.truck.damage_pct
        if damage <= FIELD_REPAIR_DAMAGE_PCT:
            self.ctx.say(
                "The truck is running well enough. A roadside mechanic "
                f"can help once damage is past "
                f"{FIELD_REPAIR_DAMAGE_PCT:.0f} percent."
            )
            return
        if d.truck.speed_mph > 3:
            self.ctx.say("Come to a complete stop first.")
            return
        p = self.ctx.profile
        cost = road_repair_cost(damage, FIELD_REPAIR_DAMAGE_PCT, MECHANIC_CALLOUT_FEE)
        carrier_paid = not player_pays_operating_costs(p.business_status)
        if not carrier_paid:
            p.money -= cost  # the rescue is never refused; money can go negative
        d.truck.damage_pct = FIELD_REPAIR_DAMAGE_PCT
        _advance_rest_clock(d, MECHANIC_WAIT_MIN)
        d.hos.on_duty(MECHANIC_WAIT_MIN)
        self.ctx.audio.play("ui/notify")
        self.refresh()
        billing = (
            "on the carrier breakdown account"
            if carrier_paid
            else f"for {cost:,.0f} dollars. You have {p.money:,.0f} dollars"
        )
        self.ctx.say(
            f"A mobile mechanic patched the truck up to "
            f"{FIELD_REPAIR_DAMAGE_PCT:.0f} percent damage {billing}. "
            f"The repair took an hour and a half: it is "
            f"{clock_text(d.trip.local_hour)}. {_deadline_text(d)}"
        )

    def _chain_night(self) -> bool:
        return is_night(self.driving.trip.local_hour)

    def _install_chains_label(self) -> str:
        minutes = CHAIN_INSTALL_MIN * (CHAIN_INSTALL_NIGHT_MULT if self._chain_night() else 1.0)
        when = " in the dark" if self._chain_night() else ""
        return f"Install snow chains{when}: about {minutes:.0f} minutes"

    def _install_chains(self) -> None:
        d = self.driving
        p = self.ctx.profile
        if d.truck.speed_mph > 3:
            self.ctx.say("Come to a complete stop first.")
            return
        night = self._chain_night()
        minutes = CHAIN_INSTALL_MIN * (CHAIN_INSTALL_NIGHT_MULT if night else 1.0)
        fatigue = CHAIN_INSTALL_NIGHT_FATIGUE if night else CHAIN_INSTALL_FATIGUE
        _advance_rest_clock(d, minutes, "on_duty_not_driving", "chain up")
        d.hos.on_duty(minutes)
        p.fatigue = min(100.0, p.fatigue + fatigue)
        d.truck.chains_on = True
        d._chains_fast_active = False
        self.ctx.audio.play("ui/notify")
        self.refresh()
        effort = (
            "Kneeling on a dark shoulder by headlamp, it takes everything your gloves have got. "
            if night
            else ""
        )
        bare = (
            " The road here is bare; they will grind apart fast until you reach the snow."
            if d.truck.surface not in ("snow", "ice")
            else ""
        )
        self.ctx.say(
            f"Chains hung on the drives in {minutes:.0f} minutes. {effort}"
            f"Keep it near {self.ctx.settings.speed_text(CHAIN_SAFE_MPH)}, and pull them "
            f"when the road turns bare.{bare} It is "
            f"{clock_text(d.trip.local_hour)}. {_deadline_text(d)}"
        )

    def _remove_chains(self) -> None:
        d = self.driving
        if d.truck.speed_mph > 3:
            self.ctx.say("Come to a complete stop first.")
            return
        _advance_rest_clock(d, CHAIN_REMOVE_MIN, "on_duty_not_driving", "remove chains")
        d.hos.on_duty(CHAIN_REMOVE_MIN)
        p = self.ctx.profile
        p.fatigue = min(100.0, p.fatigue + CHAIN_REMOVE_FATIGUE)
        d.truck.chains_on = False
        self.ctx.audio.play("ui/notify")
        self.refresh()
        wear = d.truck.chain_wear_pct
        state_word = (
            "They are about done; pick up a fresh set at a garage."
            if wear >= 75
            else f"The set is {wear:.0f} percent worn."
            if wear >= 1
            else "The set is still fresh."
        )
        self.ctx.say(
            f"Chains off and stowed in {CHAIN_REMOVE_MIN:.0f} minutes. "
            f"{state_word} It is {clock_text(d.trip.local_hour)}. {_deadline_text(d)}"
        )

    def _emergency_shoulder_sleep(self) -> None:
        reason = self.driving.emergency_shoulder_sleep_reason()
        if reason is None:
            self.ctx.say(
                "Emergency shoulder sleep is not available right now. "
                "Use a route stop for normal breaks and sleep."
            )
            self.refresh()
            return
        if not _secure_truck_for_stopped_menu(self.driving):
            self.ctx.say(
                "Come to a complete stop first. Resume driving, finish stopping, "
                "then reopen the pause menu."
            )
            self.refresh()
            return
        self.ctx.push_state(
            ShoulderSleepConfirmationState(
                self.ctx, self.driving, reason, self.driving.trip.position_mi
            )
        )

    def handle_controller(self, event, manager) -> None:
        # Start pauses and unpauses, so it resumes from the pause menu too.
        if (
            event.type == pygame.CONTROLLERBUTTONDOWN
            and event.button == pygame.CONTROLLER_BUTTON_START
        ):
            self._resume()
            return
        super().handle_controller(event, manager)

    def _resume(self) -> None:
        self.ctx.audio.play("ui/unpause")
        # Anything that reached the voice while the menu was up describes a
        # road the player was not on. They come back to the road as it is now.
        self.ctx.resume_event_speech()
        # The player may have lost the thread across the pause: bring each
        # facility's full name back once (research doc R6).
        self.driving.trip.reset_facility_mentions()
        self.driving._pending_ambient_event = None
        self.ctx.pop_state()
        self.ctx.say("Resumed.", interrupt=False, review=False)

    def _status(self) -> None:
        d = self.driving
        hours_used = d.trip.game_minutes / 60.0
        if d.phase == DRIVE_PHASE_PICKUP:
            self.ctx.say(
                f"Driving to pickup at {d._pickup_facility_text()}. "
                f"{d.job.weight_tons:.0f} tons of {d.job.cargo.label} are "
                f"assigned for {d.job.spoken_destination}. "
                f"{d._pickup_progress_summary()} {hours_used:.1f} hours used. "
                f"{d._air_status_text()}."
            )
            return
        self.ctx.say(
            f"Hauling {d.job.weight_tons:.0f} tons of {d.job.cargo.label} "
            f"to {d.job.spoken_destination}. "
            f"{d.trip.progress_summary(self.ctx.settings.imperial_units)} "
            f"{hours_used:.1f} hours used of {d.job.deadline_game_h:.0f}. "
            f"{d._air_status_text()}."
        )

    def _controls(self) -> None:
        from .main_menu import HelpState, controls_help_page

        self.ctx.push_state(HelpState(self.ctx, start_page=controls_help_page()))

    def _learn_sounds(self) -> None:
        from .learn_sounds import LearnSoundsState

        self.ctx.push_state(LearnSoundsState(self.ctx))

    def _settings(self) -> None:
        from .main_menu import SettingsState

        self.ctx.push_state(SettingsState(self.ctx))

    def _drivers_board(self) -> None:
        from .online_states import DriversOnlineState

        self.ctx.push_state(DriversOnlineState(self.ctx))

    def _abandon(self) -> None:
        # Abandoning is destructive and one keystroke away, so confirm first.
        self.ctx.push_state(AbandonJobConfirmationState(self.ctx, self.driving))

    def _quit_to_menu(self) -> None:
        from .main_menu import MainMenuState

        # Saving happens only at stops, so a mid-drive quit writes nothing: the
        # on-disk save still points at your last stop, and Continue resumes the
        # leg from there. In-progress leg driving is intentionally not preserved.
        _restore_checkpoint_driver_state(self.ctx, self.driving)
        drive_label = "pickup drive" if self.driving.phase == DRIVE_PHASE_PICKUP else "delivery"
        self.ctx.say(
            f"Returning to the title. You can only save at a stop, so this "
            f"{drive_label} will resume from your last stop, not from here.",
            interrupt=True,
        )
        self.ctx.reset_to(MainMenuState(self.ctx))


class AbandonJobConfirmationState(MenuState):
    """Yes/No guard in front of abandoning a job. Lands on "No" so giving up
    the load takes a deliberate arrow to "Yes"."""

    title = "Abandon job?"
    intro_help = (
        "Use up and down arrows to navigate, Enter to select. "
        "Escape cancels and returns to the pause menu."
    )

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.title} Abandoning gives up this load. You will pay a five "
            "hundred dollar penalty, take a reputation hit, and return to "
            f"{self.ctx.world.spoken_city(self.ctx.profile.current_city)}. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "No, keep driving",
                self.go_back,
                help="Return to the pause menu and keep this job.",
            ),
            MenuItem(
                "Yes, abandon the job",
                self._confirm,
                help="Give up this job. Costs five hundred dollars and "
                "reputation, and returns you to the origin city.",
            ),
        ]

    def _confirm(self) -> None:
        from .city import CityMenuState

        p = self.ctx.profile
        p.money -= 500.0
        p.career.reputation = max(0.0, p.career.reputation - 5.0)
        p.store_truck_condition(self.driving.truck)
        # the hours spent on the failed run still happened: keep the world
        # clock consistent with the HOS and fatigue already accrued
        p.game_hours += self.driving.trip.game_minutes / 60.0
        p.market.advance_to(p.market_day())
        p.active_trip = None
        p.pay_advance_used_for_load = False
        self.ctx.save_profile()
        self.ctx.pop_state()  # close this confirmation
        self.ctx.pop_state()  # close the pause menu
        self.ctx.replace_state(CityMenuState(self.ctx))
        # interrupt=True so this overrides any menu re-announcement during unwind
        self.ctx.say(
            f"Job abandoned. You paid a five hundred dollar penalty and "
            f"returned to {self.ctx.world.spoken_city(p.current_city)}.",
            interrupt=True,
        )
