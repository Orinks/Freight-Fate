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
            if endpoint == "/api/freight-fate/profile-snapshot":
                self.items = [item for item in self.items if item.endpoint != endpoint]
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
        threading.Thread(target=self.flush, name="online-journal", daemon=True).start()


def profile_snapshot(profile, *, city_name: str, truck_name: str, captured_at_ms: int) -> dict:
    career = profile.career
    level = int(career.level)
    return {
        "version": 1,
        "level": level,
        "careerTitle": f"Level {level} driver",
        "lastSavedCity": city_name,
        "deliveries": int(career.deliveries),
        "milesDriven": round(float(career.total_miles), 1),
        "reputation": round(float(career.reputation), 1),
        "onTimeDeliveries": int(career.on_time_deliveries),
        "truckName": truck_name,
        "employmentStatus": "Owner-operator"
        if profile.truck in profile.owned_trucks
        else "Company driver",
        "capturedAt": int(captured_at_ms),
    }


def queue_profile_snapshot(
    outbox: JournalOutbox, profile, *, city_name: str, truck_name: str, captured_at_ms: int
) -> bool:
    payload = profile_snapshot(
        profile, city_name=city_name, truck_name=truck_name, captured_at_ms=captured_at_ms
    )
    event_id = stable_event_id("profile", profile.name, captured_at_ms)
    return outbox.enqueue("/api/freight-fate/profile-snapshot", {"snapshot": payload}, event_id)


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
