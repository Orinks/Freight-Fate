"""The Online menu: every online feature in one place on the main menu.

These items used to live in Settings under an Online category, which buried
actions a player reaches for by name -- "restore my save on this new
computer", "who is hauling right now" -- behind a settings hunt. The hub
keeps each consent toggle next to the account item that gives it meaning,
and the drivers board sits first because viewing it shares nothing.

Toggles keep the Settings adjust model (Enter or Right changes forward,
Left changes backward) so nothing moves under a player's fingers; action
rows ignore Left and Right the same way the old category did.
"""

from __future__ import annotations

import pygame

from ..online_presence import OnlineIdentity
from .base import MenuItem, MenuState


class OnlineHubState(MenuState):
    title = "Online"
    intro_help = (
        "Use up and down arrows to pick an item. Enter opens an item or "
        "changes a setting forward, Right arrow also changes a setting "
        "forward, and Left arrow changes it backward. Escape goes back. "
        "Nothing here does anything until you connect an orinks.net account, "
        "and everything here can be turned off again."
    )

    def build_items(self) -> list[MenuItem]:
        s = self.ctx.settings
        return [
            MenuItem(
                "Drivers board",
                self._drivers_board,
                help="Hear who is hauling right now on the public orinks.net "
                "drivers board. Viewing the board shares nothing about you.",
            ),
            # This line's master switch survives the move into the hub: one
            # row that stands every orinks.net and sharing service down (or
            # back up) without losing the individual consents beneath it.
            MenuItem(
                lambda: f"Online services: {'on' if s.online_services else 'off'}",
                lambda: self._toggle_online_services(1),
                help="Master switch for the orinks.net and sharing services. "
                "When off, the drivers board, profile sharing, cloud backup, "
                "Mastodon sharing, and Discord presence all behave as "
                "disabled without losing their individual settings. Live "
                "weather, traffic, and parking are separate: they follow "
                "their own toggles under Settings.",
            ),
            MenuItem(
                lambda: (
                    "orinks.net account: connected"
                    if OnlineIdentity.load() is not None
                    else "Set up orinks.net account"
                ),
                self._online_account_setup,
                help="Connect the game to your orinks.net account. Connecting turns "
                "Profile sharing on and starts backing your careers up to that "
                "account; both are single items on this menu if you want either off. "
                "To change your driver name or sign a computer out afterwards, use "
                "Open my driver setup page below.",
            ),
            # Deliberately its own row rather than a job the account row does
            # once connected: that row is also the way back in when
            # orinks.net stops accepting this computer, which is exactly when
            # a player needs to re-activate rather than browse. Keeping both
            # available means the spoken recovery advice (cloud_saves
            # AUTH_HELP) still names something that works, and the row never
            # changes what it does under a player's fingers.
            MenuItem(
                "Open my driver setup page",
                self._open_setup_page,
                help="Opens your orinks.net driver setup page in a browser. "
                "That page is where you change your driver name, turn profile "
                "sharing on or off, see the computers signed in to your "
                "account, and sign any of them out. Nothing about it has to "
                "be typed or remembered: the game knows the address.",
            ),
            MenuItem(
                # The identity check lives INSIDE the label so it is
                # fresh on every read: a captured build-time value went
                # stale the moment setup completed (or the identity file
                # changed on disk) and misreported "on" while dormant.
                lambda: (
                    (
                        "Profile sharing: off requested"
                        if s.profile_sharing_pending_off
                        else f"Profile sharing: {'on' if s.online_presence else 'off'}"
                    )
                    if OnlineIdentity.load() is not None
                    else "Profile sharing: not set up"
                ),
                lambda: self._toggle_online_presence(1),
                help="Profile sharing is one optional public setting for your driver profile, "
                "official achievements, automatic road-journal posts, updates feed, "
                "and on-duty board activity. Career statistics on the public profile "
                "include lifetime career earnings; the money you currently have is "
                "never published. Nothing is shared until you set it up: "
                "Set up the orinks.net account first, which turns this on. "
                "Cloud saves remain private and separate.",
            ),
            MenuItem(
                lambda: (
                    f"Back up saves to your orinks.net account: {'on' if s.cloud_saves else 'off'}"
                    if OnlineIdentity.load() is not None
                    else "Back up saves to your orinks.net account: not set up"
                ),
                lambda: self._toggle_cloud_saves(1),
                help="After each game save, upload that career to your "
                "own orinks.net account so you can restore it on another "
                "computer. Backups are private to your account and never "
                "appear as public downloads. Uses the same orinks.net account "
                "sign-in, and comes on when you connect that account. The "
                "career statistics on your public profile are read from these "
                "backups, so turning this off empties them.",
            ),
            MenuItem(
                "Restore a cloud backup",
                self._cloud_backup_menu,
                help="List the careers backed up to your orinks.net account "
                "and bring one onto this computer.",
            ),
            MenuItem(
                # Same freshness rule as Profile sharing: the identity and
                # linked-handle checks live inside the label.
                lambda: (
                    (
                        f"Share notable deliveries to Mastodon: "
                        f"{'on' if s.mastodon_sharing else 'off'}"
                        if s.mastodon_linked
                        else "Share notable deliveries to Mastodon: not linked"
                    )
                    if OnlineIdentity.load() is not None
                    else "Share notable deliveries to Mastodon: not set up"
                ),
                lambda: self._toggle_mastodon_sharing(1),
                help="When on, finishing a delivery that earns an achievement, a "
                "level, or a perfect streak posts a short public summary "
                "to your own Mastodon account with the Freight Fate Runs "
                "hashtag, which is separate from the Freight Fate tag "
                "players use to talk about the game. Routine deliveries "
                "are never posted. Link a "
                "Mastodon account first with the Mastodon account item.",
            ),
            MenuItem(
                lambda: (
                    (
                        f"Mastodon account: linked as {s.mastodon_linked_handle}"
                        if s.mastodon_linked_handle
                        else "Mastodon account: linked"
                    )
                    if s.mastodon_linked
                    else "Link a Mastodon account"
                ),
                self._mastodon_account,
                help="Opens a page on orinks.net where you authorize your "
                "own Mastodon server, using the same orinks.net sign-in "
                "as driver setup. Unlinking also happens there.",
            ),
            MenuItem(
                lambda: f"Discord presence: {'on' if s.discord_presence else 'off'}",
                lambda: self._toggle_discord_presence(1),
                help="Show broad activity in Discord, like the main menu, "
                "driving a route, or resting. Only general game status "
                "is shared, never your save files or personal details. "
                "Has no effect if Discord is not running. Works without "
                "a driver profile.",
            ),
            MenuItem("Back", self.go_back),
        ]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT:
            self._adjust(1)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT:
            self._adjust(-1)
        else:
            super().handle_event(event)

    def adjust(self, direction: int) -> None:
        # D-pad left/right on a controller maps to the same per-item adjust.
        self._adjust(direction)

    def _adjust(self, direction: int) -> None:
        # The board, account setup, setup page, restore, and Mastodon link
        # rows are actions, so left/right does nothing there instead of
        # changing a nearby toggle. This list is positional: a row added to
        # build_items has to be added here at the same index, or every toggle
        # below it starts answering for its neighbour.
        actions = [
            lambda _d: None,
            self._toggle_online_services,
            lambda _d: None,
            lambda _d: None,
            self._toggle_online_presence,
            self._toggle_cloud_saves,
            lambda _d: None,
            self._toggle_mastodon_sharing,
            lambda _d: None,
            self._toggle_discord_presence,
        ]
        if self.index < len(actions):
            actions[self.index](direction)

    def _announce(self) -> None:
        self.refresh()
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_select")
        self.speak_current()

    def _drivers_board(self) -> None:
        from .online_states import DriversOnlineState

        self.ctx.push_state(DriversOnlineState(self.ctx))

    def _toggle_online_services(self, _d: int) -> None:
        """Toggle the master online services switch.

        When turned off all online features stop immediately. Individual
        toggle values are preserved so re-enabling restores the previous
        configuration without re-setting each service.
        """
        s = self.ctx.settings
        s.online_services = not s.online_services
        s.save()
        # Both directions walk the same list: every live service re-reads the
        # master switch and stands down or reconnects to match.
        self.ctx.apply_presence()
        self.ctx.apply_online_presence()
        self.ctx.apply_cloud_saves()
        self.ctx.apply_mastodon_sharing()
        self._announce()

    def _online_account_setup(self) -> None:
        from .online_states import OnlineSetupState

        self.ctx.push_state(OnlineSetupState(self.ctx))

    def _open_setup_page(self) -> None:
        """Open the driver setup page, or hand over the address if it cannot.

        Same shape as the Mastodon link page's opener: the clipboard write is
        attempted first so the fallback can promise something true, and
        webbrowser.open failing is never the end of the road -- a remote or
        streamed session is the normal case where it does nothing at all.
        """
        import webbrowser

        from ..online_presence import setup_page_url
        from .online_states import write_clipboard_text

        url = setup_page_url()
        copied = write_clipboard_text(url)
        try:
            webbrowser.open(url)
        except Exception:
            if copied:
                self.ctx.say(
                    "The browser could not be opened. The address is on your "
                    "clipboard. Paste it into your browser's address bar.",
                    interrupt=True,
                )
            else:
                # Spelled the way a player has to type it, since neither the
                # browser nor the clipboard is going to carry it for them.
                self.ctx.say(
                    "The browser could not be opened and the clipboard did "
                    f"not take the address. Go to {url} in any browser.",
                    interrupt=True,
                )
            return
        clipboard_note = (
            " The address is also on your clipboard in case the browser did not open."
            if copied
            else ""
        )
        self.ctx.say(
            "Opening your driver setup page in your browser. Sign in there "
            "with your orinks.net account to change your driver name, your "
            "profile sharing, or the computers signed in to your account." + clipboard_note,
            interrupt=True,
        )

    def _toggle_online_presence(self, _d: int) -> None:
        from .online_states import OnlineSetupState, ProfileSharingSyncState

        s = self.ctx.settings
        if OnlineIdentity.load() is None:
            # Not set up yet: the spoken disclosure and browser confirmation
            # happen in the setup state; it flips the setting on success.
            # The setting alone shares nothing without an identity.
            self.ctx.push_state(OnlineSetupState(self.ctx))
            return
        target = False if s.profile_sharing_pending_off else not s.online_presence
        self.ctx.push_state(ProfileSharingSyncState(self.ctx, target))

    def _toggle_cloud_saves(self, _d: int) -> None:
        from .cloud_save_states import CloudBackupConsentState

        s = self.ctx.settings
        if OnlineIdentity.load() is None:
            # Cloud backup rides the same account credentials as the board;
            # without them the setting would be inert, so point at the setup
            # item instead of flipping a switch that does nothing.
            self.ctx.say(
                "Cloud backup uses the same orinks.net sign-in as your driver "
                "profile. Choose Set up orinks.net account on this menu first, "
                "then turn cloud backup on.",
                interrupt=True,
            )
            return
        if not s.cloud_saves:
            self.ctx.push_state(CloudBackupConsentState(self.ctx))
            return
        s.cloud_saves = False
        s.save()
        self.ctx.apply_cloud_saves()
        self._announce()

    def _cloud_backup_menu(self) -> None:
        from .cloud_save_states import CloudBackupState

        self.ctx.push_state(CloudBackupState(self.ctx))

    def _toggle_mastodon_sharing(self, _d: int = 1) -> None:
        s = self.ctx.settings
        if OnlineIdentity.load() is None:
            self.ctx.say(
                "Sharing to Mastodon uses your orinks.net account. Choose "
                "Set up orinks.net account on this menu first, then link a "
                "Mastodon account.",
                interrupt=True,
            )
            return
        if not s.mastodon_linked and not s.mastodon_sharing:
            # No known link: the switch would be inert, so point at the link
            # item instead of flipping it (same shape as cloud backup).
            self.ctx.say(
                "Sharing to Mastodon needs a linked Mastodon account. Choose "
                "Link a Mastodon account on this menu first, then turn "
                "sharing on.",
                interrupt=True,
            )
            return
        s.mastodon_sharing = not s.mastodon_sharing
        self.ctx.apply_mastodon_sharing()
        self._announce()
        if s.mastodon_sharing:
            # The label said "on"; this says what "on" means, every time.
            self.ctx.say(
                "Only deliveries that earn an achievement, a level, or a perfect "
                "streak are posted. Posts are public on your own Mastodon "
                "account and carry the Freight Fate Runs hashtag, which is "
                "separate from the Freight Fate tag players use to talk about "
                "the game.",
                interrupt=False,
            )

    def _mastodon_account(self) -> None:
        from .online_states import MastodonLinkState

        if OnlineIdentity.load() is None:
            self.ctx.say(
                "Linking Mastodon uses your orinks.net sign-in. Choose Set "
                "up orinks.net account on this menu first.",
                interrupt=True,
            )
            return
        self.ctx.push_state(MastodonLinkState(self.ctx))

    def _toggle_discord_presence(self, _d: int) -> None:
        self.ctx.settings.discord_presence = not self.ctx.settings.discord_presence
        self.ctx.apply_presence()
        self._announce()
