"""The Cloud backup menu: restore cloud saves and resolve sync conflicts.

Reached from Settings, Online. Everything network runs on daemon threads
with the same mailbox-polling pattern as the drivers board menus: the game
loop and speech stay responsive while orinks.net answers.
"""

from __future__ import annotations

import threading
import time

from .. import cloud_saves
from ..online_presence import OnlineIdentity
from .base import MenuItem, MenuState

CLOUD_DISCLOSURE = (
    "Cloud backup uploads each career save to your own Orinks account after "
    "the game saves it, so you can restore your progress on another computer "
    "or after losing this one. Backups are private to your account: they "
    "never appear on the drivers board or anywhere public. The last ten "
    "backups of each career are kept. You can turn this off any time in "
    "Settings, Online."
)


def _backed_up_text(created_at_ms: float | None) -> str:
    """A speakable freshness phrase from a server epoch-milliseconds stamp."""
    if not created_at_ms:
        return "backup time unknown"
    age_s = max(0.0, time.time() - created_at_ms / 1000.0)
    if age_s < 90:
        return "backed up just now"
    if age_s < 90 * 60:
        return f"backed up {round(age_s / 60)} minutes ago"
    if age_s < 36 * 3600:
        return f"backed up {round(age_s / 3600)} hours ago"
    return f"backed up {round(age_s / 86400)} days ago"


class CloudBackupState(MenuState):
    """Cloud slots as a spoken list: one item per career, newest first.

    Entering fetches the slot list on a worker thread. A slot with a sync
    conflict says so in its label; selecting any slot opens its actions.
    """

    title = "Cloud backup"

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._saves: list[dict] | None = None
        self._fetched = threading.Event()
        self._announced = False

    def enter(self) -> None:
        self._start_fetch()
        super().enter()

    def _identity(self) -> OnlineIdentity | None:
        return OnlineIdentity.load()

    def _service(self):
        return self.ctx.cloud_saves_service()

    def _start_fetch(self) -> None:
        self._saves = None
        self._fetched.clear()
        self._announced = False
        identity = self._identity()
        if identity is None:
            self._fetched.set()
            return

        def worker() -> None:
            self._saves = cloud_saves.list_saves(identity)
            self._fetched.set()

        threading.Thread(target=worker, name="cloud-saves-list", daemon=True).start()

    def _slots(self) -> list[dict]:
        """Latest revision per slot, in the server's newest-first order."""
        seen: dict[str, dict] = {}
        for entry in self._saves or []:
            name = entry.get("saveName")
            if isinstance(name, str) and name not in seen:
                seen[name] = entry
        return list(seen.values())

    def build_items(self) -> list[MenuItem]:
        if self._identity() is None:
            return [
                MenuItem(
                    "Cloud backup needs your Orinks driver account",
                    self.speak_current,
                    help="Set up the drivers board under Settings, Online "
                    "first; cloud backup uses the same sign-in.",
                ),
                MenuItem("Back", self.go_back),
            ]
        if not self._fetched.is_set():
            return [
                MenuItem("Checking your cloud backups", self.speak_current),
                MenuItem("Back", self.go_back),
            ]
        items: list[MenuItem] = []
        if self._saves is None:
            items.append(
                MenuItem(
                    "Your cloud backups could not be reached",
                    self.speak_current,
                    help="orinks.net did not answer. Refresh to try again.",
                )
            )
        elif not self._slots():
            items.append(
                MenuItem(
                    "No cloud backups yet",
                    self.speak_current,
                    help="Backups appear here after the game saves with cloud backup turned on.",
                )
            )
        else:
            conflicts = self._service().conflicts()
            for entry in self._slots():
                name = entry["saveName"]
                bits = [name]
                if entry.get("summary"):
                    bits.append(entry["summary"])
                bits.append(_backed_up_text(entry.get("createdAt")))
                if name in conflicts:
                    bits.append("needs attention: this computer has a different copy")
                items.append(
                    MenuItem(
                        ". ".join(bits),
                        lambda e=entry: self._open_slot(e),
                        help="Enter opens restore choices for this career.",
                    )
                )
        items.append(MenuItem("Hear how cloud backup works", self._speak_disclosure))
        items.append(MenuItem("Refresh", self._refresh_list, help="Check the backups again."))
        items.append(MenuItem("Back", self.go_back))
        return items

    def _speak_disclosure(self) -> None:
        self.ctx.say(CLOUD_DISCLOSURE)

    def _refresh_list(self) -> None:
        self._start_fetch()
        self.refresh(keep_index=False)
        self.ctx.say("Checking your cloud backups.")

    def _open_slot(self, entry: dict) -> None:
        revisions = [e for e in self._saves or [] if e.get("saveName") == entry["saveName"]]
        self.ctx.push_state(CloudSlotState(self.ctx, entry["saveName"], revisions))

    def update(self, dt: float) -> None:
        super().update(dt)
        if self._announced or not self._fetched.is_set() or self._identity() is None:
            return
        self._announced = True
        self.refresh(keep_index=False)
        if self._saves is None:
            self.ctx.say("Your cloud backups could not be reached.", interrupt=True)
            return
        slots = self._slots()
        if not slots:
            self.ctx.say("No cloud backups yet.", interrupt=True)
        else:
            count = f"{len(slots)} career" + ("s are" if len(slots) != 1 else " is")
            self.ctx.say(f"{count} backed up. {self.current_text()}", interrupt=True)


class CloudSlotState(MenuState):
    """Actions for one cloud slot: restore the latest backup, restore an
    older one, or resolve a conflict by choosing which copy wins.

    Restores overwrite the local save file for this career; the previous
    local file is kept beside it and the choice is confirmed before anything
    is touched. The download and any upload run on a worker thread; a small
    mailbox hands the outcome back to ``update`` for speech.
    """

    def __init__(self, ctx, save_name: str, revisions: list[dict]) -> None:
        super().__init__(ctx)
        self.save_name = save_name
        self.revisions = revisions  # newest first, from the list fetch
        self.title = f"Cloud backup: {save_name}"
        self._busy = False
        self._outcome: str | None = None  # worker -> update() mailbox
        self._restored_path = None

    def _conflict(self) -> dict | None:
        return self.ctx.cloud_saves_service().conflicts().get(self.save_name)

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        conflict = self._conflict()
        if conflict is not None:
            items.append(
                MenuItem(
                    self._conflict_label(conflict),
                    self.speak_current,
                    help="Backups for this career stopped because the cloud "
                    "copy changed on another computer. Pick which copy to "
                    "keep below; nothing changes until you choose.",
                )
            )
            items.append(
                MenuItem(
                    "Keep this computer's save and back it up",
                    self._keep_mine,
                    help="Uploads this computer's save over the cloud copy "
                    "and turns backups for this career back on.",
                )
            )
            items.append(
                MenuItem(
                    "Use the cloud copy on this computer",
                    lambda: self._confirm_restore(self.revisions[0] if self.revisions else None),
                    help="Downloads the cloud copy over this computer's "
                    "save. The current local save is kept as a fallback "
                    "file beside it.",
                )
            )
        else:
            items.append(
                MenuItem(
                    self._restore_label,
                    lambda: self._confirm_restore(self.revisions[0] if self.revisions else None),
                    help="Replaces this career's local save with the cloud "
                    "backup. The current local save is kept as a fallback "
                    "file beside it.",
                )
            )
            for entry in self.revisions[1:]:
                items.append(
                    MenuItem(
                        f"Restore an older backup: {_backed_up_text(entry.get('createdAt'))}"
                        + (f". {entry['summary']}" if entry.get("summary") else ""),
                        lambda e=entry: self._confirm_restore(e),
                        help="Replaces the local save with this older backup.",
                    )
                )
        items.append(MenuItem("Back", self.go_back))
        return items

    def _restore_label(self) -> str:
        if self._busy:
            return "Working on it"
        latest = self.revisions[0] if self.revisions else None
        if latest is None:
            return "No backups for this career yet"
        return f"Restore the latest backup, {_backed_up_text(latest.get('createdAt'))}"

    def _conflict_label(self, conflict: dict) -> str:
        summary = conflict.get("latestSummary")
        detail = f" The cloud copy is {summary}." if summary else ""
        return f"This career needs attention: the cloud copy changed on another computer.{detail}"

    # -- actions ----------------------------------------------------------------

    def _confirm_restore(self, entry: dict | None) -> None:
        if self._busy:
            self.ctx.say("Still working on the last choice.", interrupt=True)
            return
        if entry is None:
            self.ctx.say("There is no backup to restore for this career.", interrupt=True)
            return
        self.ctx.push_state(ConfirmRestoreState(self.ctx, self, entry))

    def start_restore(self, entry: dict) -> None:
        """Called by the confirmation state after the player says yes."""
        identity = OnlineIdentity.load()
        if identity is None:
            self.ctx.say("Cloud backup is not set up on this computer.", interrupt=True)
            return
        self._busy = True
        self.refresh()
        self.ctx.say("Downloading the backup.", interrupt=True)
        revision = entry.get("revision")

        def worker() -> None:
            payload = cloud_saves.download_save(
                identity,
                save_name=self.save_name,
                revision=revision if isinstance(revision, int) else None,
            )
            if payload is None:
                self._outcome = "download_failed"
                return
            try:
                path = cloud_saves.restore_to_disk(
                    payload, self.ctx.cloud_saves_service().sync_state
                )
            except Exception:
                self._outcome = "restore_failed"
                return
            self._restored_path = path
            self._outcome = "restored"

        threading.Thread(target=worker, name="cloud-saves-restore", daemon=True).start()

    def _keep_mine(self) -> None:
        if self._busy:
            self.ctx.say("Still working on the last choice.", interrupt=True)
            return
        from ..models.profile import Profile, profiles_dir

        path = profiles_dir() / f"{self.save_name}.json"
        try:
            profile_dict = Profile.load(path).to_dict()
        except Exception:
            self.ctx.say(
                "This computer's save for that career could not be read, so "
                "it cannot be uploaded. You can still use the cloud copy.",
                interrupt=True,
            )
            return
        self._busy = True
        self.refresh()
        self.ctx.say("Backing up this computer's save.", interrupt=True)

        def worker() -> None:
            ok = self.ctx.cloud_saves_service().resolve_keep_mine(self.save_name, profile_dict)
            self._outcome = "kept_mine" if ok else "keep_mine_failed"

        threading.Thread(target=worker, name="cloud-saves-keep-mine", daemon=True).start()

    def update(self, dt: float) -> None:
        super().update(dt)
        outcome, self._outcome = self._outcome, None
        if outcome is None:
            return
        self._busy = False
        self.refresh()
        if outcome == "restored":
            self._reload_active_profile()
            self.ctx.audio.play("ui/menu_select")
            self.ctx.say(
                f"Backup restored. {self.save_name} on this computer now "
                "matches the cloud copy, and the save it replaced was kept "
                "beside it as a fallback file.",
                interrupt=True,
            )
        elif outcome == "kept_mine":
            self.ctx.audio.play("ui/menu_select")
            self.ctx.say(
                "Done. The cloud copy now matches this computer's save, and "
                "backups for this career are on again.",
                interrupt=True,
            )
        elif outcome == "keep_mine_failed":
            self.ctx.say(
                "The upload did not go through. Check your connection and "
                "try again; nothing was changed.",
                interrupt=True,
            )
        else:
            self.ctx.say(
                "The backup could not be downloaded. Check your connection "
                "and try again; your local save was not touched.",
                interrupt=True,
            )

    def _reload_active_profile(self) -> None:
        """If the restored career is the one currently loaded, re-read it so
        a later save cannot overwrite the restore with stale memory."""
        profile = self.ctx.profile
        if profile is None or cloud_saves.save_slot_name(profile.name) != self.save_name:
            return
        from ..models.profile import Profile

        try:
            self.ctx.profile = Profile.load(profile.path)
        except Exception:
            self.ctx.profile = None


class ConfirmRestoreState(MenuState):
    """One spoken yes/no gate before a restore overwrites a local save."""

    title = "Restore this backup?"

    def __init__(self, ctx, slot_state: CloudSlotState, entry: dict) -> None:
        super().__init__(ctx)
        self._slot_state = slot_state
        self._entry = entry

    def announce_entry(self) -> None:
        entry = self._entry
        summary = f" It is {entry['summary']}," if entry.get("summary") else ""
        self.ctx.say(
            f"Restore the backup of {self._slot_state.save_name}, "
            f"{_backed_up_text(entry.get('createdAt'))}?{summary} replacing "
            "this computer's save for that career. The replaced save is kept "
            f"as a fallback file. {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem("Yes, restore this backup", self._yes),
            MenuItem("No, keep this computer's save", self.go_back),
        ]

    def _yes(self) -> None:
        self.ctx.pop_state()
        self._slot_state.start_restore(self._entry)
