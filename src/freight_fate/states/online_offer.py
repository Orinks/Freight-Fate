"""The one-time offer to connect this computer to an orinks.net account.

Shown once, straight after a first career is created, because nothing else
tells a new player the feature exists. Online is optional and stays optional:
declining takes one keypress, sets the gate, and is never asked again.

The copy says exactly what connecting does: it turns cloud backup and Profile
sharing on. It does, since 1.9 -- a connected account that publishes nothing
and backs nothing up is a connection that did nothing for the player, and the
career statistics on the public profile are read from the backup. The rule
behind the wording is unchanged though: a player must never walk away from
this prompt with a wrong idea of what is backed up or public, in either
direction.
"""

from __future__ import annotations

from ..online_presence import OnlineIdentity
from .base import MenuItem, MenuState


def _stored_identity():
    """The saved account credentials, or None. Split out so tests can pin it
    without touching the platform secret store."""
    return OnlineIdentity.load()


def should_offer_online(ctx) -> bool:
    """Whether a first-run player should hear the offer at all."""
    if ctx.settings.online_offer_seen:
        return False
    return _stored_identity() is None


class OnlineOfferState(MenuState):
    title = "Connect to orinks.net"
    intro_help = "Choose Set up now to connect this computer, or Not now to start driving."

    def announce_entry(self) -> None:
        # Queued, not interrupting: career creation speaks the welcome line
        # immediately before pushing this state, and the player has to hear
        # where they are and what they own before being asked anything.
        self.ctx.say(
            "Before you set off. You can connect this computer to an "
            "orinks.net account. That backs your career up so you can bring "
            "it to another computer, and puts your driver profile and on-duty "
            "activity on the public site. You can turn either of those off "
            "afterwards from Online on the main menu. It takes a code and "
            "your browser, and you can do it any time instead. "
            f"{self.current_text()}",
            interrupt=False,
        )

    def build_items(self) -> list[MenuItem]:
        # Not now first, so the cursor starts on the answer that changes
        # nothing. Escape takes the same path.
        return [
            MenuItem(
                "Not now", self._decline, help="Start driving. You can connect later from Online."
            ),
            MenuItem(
                "Set up now",
                self._accept,
                help="Connect this computer to an orinks.net account, which turns on "
                "cloud backup and your public driver profile.",
            ),
        ]

    def _spend_the_offer(self) -> None:
        self.ctx.settings.online_offer_seen = True
        self.ctx.settings.save()

    def _enter_world(self) -> None:
        from .city import CityMenuState

        # The city menu queues its own announcement, so a line spoken on the
        # way out of here -- "You can connect any time from Online" -- is heard
        # in full instead of being cut off by "Parked at ...".
        self.ctx.replace_state(CityMenuState(self.ctx, queue_entry_announcement=True))

    def _decline(self) -> None:
        self._spend_the_offer()
        self.ctx.say(
            "No problem. You can connect any time from Online on the main menu.",
            interrupt=True,
        )
        self._enter_world()

    def _accept(self) -> None:
        # The player already said "Set up now" -- pushing OnlineSetupState
        # with autostart=True starts activation immediately instead of
        # asking them to confirm the same decision again from a menu. The
        # city menu goes underneath (replace, not push) so that backing out
        # of setup lands the player in the world, not back on this offer.
        from .online_states import OnlineSetupState

        self._spend_the_offer()
        self._enter_world()
        self.ctx.push_state(OnlineSetupState(self.ctx, autostart=True))

    def go_back(self) -> None:
        # Escape means Not now. The player must never be stuck here, and
        # backing out still spends the offer so it cannot reappear.
        self._decline()
