import json
import urllib.error

from freight_fate.achievements import ACHIEVEMENT_BY_ID
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.online_journal import (
    JournalOutbox,
    OutboxItem,
    profile_snapshot,
    queue_achievement,
    queue_delivery,
    stable_event_id,
)
from freight_fate.online_presence import OnlineIdentity


def test_stable_event_id_is_deterministic_and_fact_sensitive():
    assert stable_event_id("delivery", "job-1", 4) == stable_event_id("delivery", "job-1", 4)
    assert stable_event_id("delivery", "job-1", 4) != stable_event_id("delivery", "job-2", 4)


def test_snapshot_allowlists_saved_career_facts():
    profile = Profile(name="Road Star")
    profile.career.deliveries = 7
    profile.career.total_miles = 1234.56
    result = profile_snapshot(
        profile, city_name="Chicago, Illinois", truck_name="Roadmaster", captured_at_ms=123
    )
    assert result["lastSavedCity"] == "Chicago, Illinois"
    assert result["deliveries"] == 7
    assert result["milesDriven"] == 1234.6
    assert "money" not in result
    assert "active_trip" not in result


def test_outbox_persists_deduplicates_and_retries(tmp_path):
    calls = []
    now = [100.0]

    def transport(url, payload, headers):
        calls.append((url, payload, headers))
        if len(calls) == 1:
            raise OSError("offline")
        return {"ok": True}

    identity = OnlineIdentity("driver-1234", "ffd_" + "a" * 64)
    path = tmp_path / "outbox.json"
    box = JournalOutbox(identity, True, path, transport=transport, clock=lambda: now[0])
    assert box.enqueue("/events", {"value": 1}, "evt-1")
    assert not box.enqueue("/events", {"value": 1}, "evt-1")
    assert box.flush() == 0
    restored = JournalOutbox(identity, True, path, transport=transport, clock=lambda: now[0])
    assert restored.items[0].attempts == 1
    assert restored.flush() == 0
    now[0] = restored.items[0].next_attempt_at
    assert restored.flush() == 1
    assert restored.items == []


def test_disabled_outbox_never_queues_or_posts(tmp_path):
    box = JournalOutbox(
        None,
        False,
        tmp_path / "outbox.json",
        transport=lambda *_: (_ for _ in ()).throw(AssertionError()),
    )
    assert not box.enqueue("/events", {}, "evt")
    assert box.flush() == 0


def test_delivery_payload_is_structured_and_duplicate_completion_is_suppressed(tmp_path):
    identity = OnlineIdentity("driver-1234", "ffd_" + "a" * 64)
    box = JournalOutbox(identity, True, tmp_path / "outbox.json")
    profile = Profile(name="Road Star")
    profile.career.deliveries = 1
    job = Job(
        CARGO_CATALOG["general"], 20, "chicago_il_us", "terminal", "denver_co_us", 1000, 2000, 20
    )
    assert queue_delivery(
        box,
        profile,
        job,
        origin="Chicago, Illinois",
        destination="Denver, Colorado",
        on_time=True,
        occurred_at_ms=123,
        undamaged=True,
    )
    assert not queue_delivery(
        box,
        profile,
        job,
        origin="Chicago, Illinois",
        destination="Denver, Colorado",
        on_time=True,
        occurred_at_ms=456,
        undamaged=True,
    )
    payload = box.items[0].payload
    assert payload["payload"]["weightPounds"] == 40_000
    assert payload["payload"]["notableCondition"] == "Delivered without new truck damage"
    assert "summary" not in payload


def test_achievement_payload_uses_official_definition_and_deduplicates(tmp_path):
    identity = OnlineIdentity("driver-1234", "ffd_" + "a" * 64)
    box = JournalOutbox(identity, True, tmp_path / "outbox.json")
    achievement = ACHIEVEMENT_BY_ID["first_delivery"]
    assert queue_achievement(box, achievement, earned_at_ms=123)
    assert not queue_achievement(box, achievement, earned_at_ms=456)
    assert box.items[0].payload["name"] == achievement.name
    assert box.items[0].payload["description"] == achievement.description


def test_new_snapshot_replaces_stale_queued_snapshot(tmp_path):
    identity = OnlineIdentity("driver-1234", "ffd_" + "a" * 64)
    box = JournalOutbox(identity, True, tmp_path / "outbox.json")
    assert box.enqueue(
        "/api/freight-fate/profile-snapshot", {"snapshot": {"level": 1}}, "profile-1"
    )
    assert box.enqueue(
        "/api/freight-fate/profile-snapshot", {"snapshot": {"level": 2}}, "profile-2"
    )
    assert [item.event_id for item in box.items] == ["profile-2"]


def test_permanent_consent_error_is_dropped_without_retrying(tmp_path):
    identity = OnlineIdentity("driver-1234", "ffd_" + "a" * 64)

    def denied(*_args):
        raise urllib.error.HTTPError("https://example.test", 403, "sharing_not_enabled", {}, None)

    box = JournalOutbox(identity, True, tmp_path / "outbox.json", transport=denied)
    box.enqueue("/events", {}, "evt")
    assert box.flush() == 0
    assert box.items == []


def test_runtime_opt_out_clears_queue_and_reenable_cannot_publish_it(tmp_path):
    posted = []
    identity = OnlineIdentity("driver-1234", "ffd_" + "a" * 64)
    box = JournalOutbox(
        identity,
        True,
        tmp_path / "outbox.json",
        transport=lambda *args: posted.append(args) or {"ok": True},
    )
    box.items.append(OutboxItem("/events", {}, "waiting"))
    box._save()
    box.set_enabled(False)
    assert not box.enqueue("/events", {}, "off")
    assert box.items == []
    assert json.loads((tmp_path / "outbox.json").read_text())["items"] == []
    box.set_enabled(True)
    box.flush()
    assert posted == []
