"""Quiet, durable publishing of allowlisted Freight Fate profile facts."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import urllib.error
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .online_presence import OnlineIdentity, Transport, _http_json, base_url

log = logging.getLogger(__name__)
MAX_OUTBOX_ITEMS = 100
BASE_RETRY_S = 30.0
MAX_RETRY_S = 3600.0


def stable_event_id(kind: str, *parts: object) -> str:
    canonical = json.dumps([kind, *parts], ensure_ascii=True, separators=(",", ":"))
    return f"{kind}-{hashlib.sha256(canonical.encode()).hexdigest()[:24]}"


@dataclass
class OutboxItem:
    endpoint: str
    payload: dict
    event_id: str
    attempts: int = 0
    next_attempt_at: float = 0.0


@dataclass
class JournalOutbox:
    identity: OnlineIdentity | None
    enabled: bool
    path: Path
    transport: Transport = _http_json
    clock: Callable[[], float] = time.time
    items: list[OutboxItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        # One sender at a time. A settlement can queue a delivery, a level up,
        # and several achievements in the same breath, each asking to flush --
        # left unguarded that is a thread per call, all walking the same due
        # list, posting the same events twice and colliding on the server's
        # per-driver write counter. Asking while a flush runs sets the rerun
        # flag instead, so the last caller's items still go out.
        self._flushing = False
        self._flush_again = False
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = [OutboxItem(**item) for item in raw.get("items", [])][-MAX_OUTBOX_ITEMS:]
        except (OSError, ValueError, TypeError):
            self.items = []

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled) and self.identity is not None
        if not self.enabled:
            with self._lock:
                self.items.clear()
                self._save()

    def set_identity(self, identity: OnlineIdentity | None) -> None:
        self.identity = identity
        if identity is None:
            self.enabled = False

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps({"version": 1, "items": [item.__dict__ for item in self.items]}, indent=2),
            encoding="utf-8",
        )
        temp.replace(self.path)

    def enqueue(self, endpoint: str, payload: dict, event_id: str) -> bool:
        if not self.enabled or self.identity is None:
            return False
        with self._lock:
            if any(item.event_id == event_id for item in self.items):
                return False
            self.items.append(OutboxItem(endpoint, payload, event_id))
            self.items = self.items[-MAX_OUTBOX_ITEMS:]
            self._save()
        return True

    def flush(self) -> int:
        """Attempt due items once. Never raises or blocks gameplay callers."""
        if not self.enabled or self.identity is None:
            return 0
        sent = 0
        now = self.clock()
        with self._lock:
            due = [item for item in self.items if item.next_attempt_at <= now]
        for item in due:
            try:
                reply = self.transport(
                    f"{base_url()}{item.endpoint}",
                    {"driverId": self.identity.driver_id, **item.payload},
                    {"Authorization": f"Bearer {self.identity.driver_token}"},
                )
                ok = bool(reply.get("ok"))
            except urllib.error.HTTPError as error:
                # Authentication, consent, and validation failures cannot heal
                # through retries. Rate limiting and server failures can.
                if error.code in {400, 401, 403, 404}:
                    with self._lock:
                        self.items = [
                            value for value in self.items if value.event_id != item.event_id
                        ]
                        self._save()
                    continue
                log.debug("Road journal post failed: HTTP %s", error.code)
                ok = False
            except Exception as error:
                log.debug("Road journal post failed: %s", error)
                ok = False
            with self._lock:
                current = next(
                    (value for value in self.items if value.event_id == item.event_id), None
                )
                if current is None:
                    continue
                if ok:
                    self.items.remove(current)
                    sent += 1
                else:
                    current.attempts += 1
                    current.next_attempt_at = now + min(
                        MAX_RETRY_S, BASE_RETRY_S * 2 ** min(current.attempts - 1, 7)
                    )
                self._save()
        return sent

    def flush_async(self) -> None:
        """Ask for a flush without blocking, and without racing one already in
        flight. Anything queued before this call still goes out: a request made
        mid-flush schedules one more pass rather than a second sender."""
        with self._lock:
            if self._flushing:
                self._flush_again = True
                return
            self._flushing = True
        threading.Thread(target=self._flush_until_idle, name="online-journal", daemon=True).start()

    def _flush_until_idle(self) -> None:
        try:
            while True:
                self.flush()
                with self._lock:
                    if not self._flush_again:
                        self._flushing = False
                        return
                    self._flush_again = False
        except BaseException:
            # Never strand the flag: a sender that died without clearing it
            # would silence the journal for the rest of the session.
            with self._lock:
                self._flushing = False
                self._flush_again = False
            raise


def queue_delivery(
    outbox: JournalOutbox,
    profile,
    job,
    *,
    origin: str,
    destination: str,
    on_time: bool,
    occurred_at_ms: int,
    undamaged: bool,
) -> bool:
    event_id = stable_event_id(
        "delivery",
        profile.name,
        profile.career.deliveries,
        job.cargo.key,
        job.origin,
        job.destination,
        round(job.distance_mi, 1),
    )
    payload = {
        "eventId": event_id,
        "occurredAt": occurred_at_ms,
        "payload": {
            "version": 1,
            "cargo": job.cargo.label,
            "weightPounds": round(job.weight_tons * 2000),
            "origin": origin,
            "destination": destination,
            "distanceMiles": round(job.distance_mi, 1),
            "onTime": bool(on_time),
            **({"notableCondition": "Delivered without new truck damage"} if undamaged else {}),
        },
    }
    return outbox.enqueue("/api/freight-fate/events/delivery", payload, event_id)


def queue_mastodon_share(
    outbox: JournalOutbox,
    profile,
    job,
    *,
    origin: str,
    destination: str,
    on_time: bool,
    occurred_at_ms: int,
    reasons: list[dict],
) -> bool:
    """Queue a notable delivery for the player's own Mastodon account.

    ``reasons`` is what made the run notable -- new badges, a level up, a
    perfect-streak milestone. An empty list means the delivery was routine,
    and routine runs are never posted: the server refuses reason-free shares
    too, so the quiet path is enforced on both ends. The server composes the
    actual post text from these allowlisted facts and adds the FreightFate
    hashtag; nothing free-form leaves the game."""
    if not reasons:
        return False
    event_id = stable_event_id(
        "mastodon",
        profile.name,
        profile.career.deliveries,
        job.cargo.key,
        job.origin,
        job.destination,
    )
    payload = {
        "eventId": event_id,
        "occurredAt": occurred_at_ms,
        "payload": {
            "version": 1,
            "cargo": job.cargo.label,
            "origin": origin,
            "destination": destination,
            "distanceMiles": round(job.distance_mi, 1),
            "onTime": bool(on_time),
            "reasons": reasons,
        },
    }
    return outbox.enqueue("/api/freight-fate/mastodon/share", payload, event_id)


def queue_achievement(outbox: JournalOutbox, achievement, *, earned_at_ms: int) -> bool:
    event_id = stable_event_id("achievement", achievement.id)
    return outbox.enqueue(
        "/api/freight-fate/events/achievement",
        {
            "eventId": event_id,
            "achievementKey": achievement.id,
            "name": achievement.name,
            "description": achievement.description,
            "earnedAt": earned_at_ms,
        },
        event_id,
    )


def queue_career_milestones(
    outbox: JournalOutbox,
    profile,
    *,
    previous_level: int,
    occurred_at_ms: int,
) -> int:
    milestones: list[tuple[str, int | None]] = []
    if profile.career.deliveries == 1:
        milestones.append(("first_delivery", None))
    if profile.career.level > previous_level:
        milestones.append(("career_level", int(profile.career.level)))
    queued = 0
    for milestone_type, level in milestones:
        event_id = stable_event_id(
            "career", milestone_type, profile.name, level or profile.career.deliveries
        )
        payload = {
            "eventId": event_id,
            "milestoneType": milestone_type,
            **({"level": level} if level is not None else {}),
            "occurredAt": occurred_at_ms,
        }
        queued += int(
            outbox.enqueue("/api/freight-fate/events/career-milestone", payload, event_id)
        )
    return queued
