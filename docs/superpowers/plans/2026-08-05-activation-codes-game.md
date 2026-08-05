# Activation Codes (Game Half) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the clipboard paste of a Driver ID and token with an activation code the game shows, spells, and can copy, while it polls orinks.net until the player confirms it in their browser.

**Architecture:** A new `online_activation.py` calls the two REST endpoints already live on orinks.net. `OnlineSetupState` loses both paste items and gains a poll loop on the existing `_outcome` mailbox. All clipboard *reading* and all parsing of clipboard text is deleted.

**Tech Stack:** Python 3.12, `uv`, pytest, pygame. No new dependencies.

## Global Constraints

- Repo `Freight-fate`, branch `dev`. 1.9 picks this up at its next merge.
- Spec: `docs/superpowers/specs/2026-08-05-online-activation-design.md`. Read it before Task 3.
- Spoken text is player-facing: no jargon, and use the canonical noun from `docs/ontology.md`. The noun is **activation code** — never "pairing code", "device code", or "setup code".
- The `device_code` is never spoken, never shown, never written to the transcript.
- Headless runs set `FREIGHT_FATE_NO_SPEECH=1`. Tests must not touch the network.
- Keep files at or below 1000 lines. `online_states.py` is ~813 and `online_presence.py` ~726, which is why activation gets its own module.
- Lint `uv run ruff check src tests tools`; tests `uv run pytest`.

## The server contract this consumes

Live on orinks.net as of `feat/activation-codes`. Do not re-derive it.

`POST /api/freight-fate/activate/start` → `200 {device_code, user_code, verification_uri, verification_uri_complete, expires_in, interval}`; `429 {error:"rate_limited"}`; `503 {error:"unavailable"}`.

`POST /api/freight-fate/activate/poll` with `{device_code}` →
`200 {status:"pending"}` | `200 {status:"ready", driver_id, token, display_name}` | `410 {status:"expired"}` | `400 {error:"bad_request"}` | `503 {error:"unavailable"}`.

Three notes that cost a debugging session if missed:

- **400 is not 410.** A malformed `device_code` returns `400 bad_request`, meaning the stored secret is corrupt — setup must start over, not report a timed-out code and loop.
- **An over-cap redeem returns 410**, deliberately. The player learns the real reason (too many computers) in the browser at claim time.
- **`display_name` must be spoken on success.** If someone overhears the code and claims it on their own account, the game receives a token for *their* driver. Saying the name is the only way the player finds out.

---

### Task 1: Delete the paste path, fix the surviving clipboard bug

**Files:** modify `src/freight_fate/states/online_states.py`, `tests/test_online_clipboard.py`

**Delete:** `read_clipboard_text`, `looks_like_driver_id`, `looks_like_token`, `_TOKEN_PREFIX`, `_ID_CHARS`, and the `looks_like_*` tests.

**Keep:** `_clipboard_once`, `_clipboard_holds`, `write_clipboard_text`. Writing still works and is still used — the delivery summary, the message review, the Mastodon link, and (in Task 3) the activation code itself. `write_clipboard_text` verifies by reading back, and on macOS that read-back is `pbpaste`, so the read helper stays.

**The bug to fix in the surviving path.** `_clipboard_once` tries `pygame.SCRAP_TEXT` then `"text/plain;charset=utf-8"` and decodes whichever answers as UTF-8. Verified on Windows: the first is `CF_TEXT`, the second is `CF_UNICODETEXT` and returns **UTF-16LE**. It only survives today because `_clean_clip` strips NULs, which reassembles ASCII while silently dropping every non-ASCII character. Unreachable on native Windows because `CF_TEXT` answers first; reachable under Wine, where an X11 owner advertising only `UTF8_STRING` can leave `CF_TEXT` empty.

- [ ] **Step 1: Write the failing test**

```python
def test_utf16_clipboard_payload_round_trips(monkeypatch):
    """The charset=utf-8 scrap type is CF_UNICODETEXT on Windows and answers
    in UTF-16LE. Decoding it as UTF-8 silently eats every non-ASCII character."""
    text = "Delivered to Montréal — 12 tonnes"

    class FakeScrap:
        @staticmethod
        def get_init():
            return True

        @staticmethod
        def get(scrap_type):
            if scrap_type == pygame.SCRAP_TEXT:
                return None  # what Wine yields when the owner offers only UTF8_STRING
            return text.encode("utf-16-le")

    monkeypatch.setattr(pygame, "scrap", FakeScrap)
    assert online_states._clipboard_once() == text
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_online_clipboard.py -k utf16 -v`
Expected: FAIL — the accented characters are dropped.

- [ ] **Step 3: Decode per format**

Give `_SCRAP_TEXT_TYPES` an encoding per entry and decode with it, rather than assuming UTF-8 for both. Strip a trailing NUL before decoding UTF-16.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/test_online_clipboard.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/freight_fate/states/online_states.py tests/test_online_clipboard.py
git commit -m "fix(online): decode clipboard text per scrap format, drop the paste path"
```

---

### Task 2: `online_activation.py`

**Files:** create `src/freight_fate/online_activation.py`, `tests/test_online_activation.py`

**Interfaces:**
- Consumes: `Transport`, `_http_json`, `base_url` from `online_presence`.
- Produces: `Activation` (dataclass: `device_code`, `user_code`, `verification_uri`, `verification_uri_complete`, `expires_at`, `interval`), `start_activation(*, transport=_http_json) -> Activation | None`, `poll_activation(activation, *, transport=_http_json) -> PollResult`, `spell_code(code: str) -> str`.

`PollResult` is a small dataclass or tagged tuple carrying `status` (`"pending" | "ready" | "expired" | "error"`) and, when ready, `driver_id`, `token`, `display_name`.

**Spelling is the point of `spell_code`.** The game has no screen reader review cursor, so a player cannot step through a spoken string character by character. Speaking `WKQR-3468` once as a word is not enough. `spell_code` returns NATO phonetics for letters and plain digits, comma-separated, with the dash spoken: `"Whiskey, Kilo, Quebec, Romeo, dash, three, four, six, eight"`. The alphabet already excludes `O I L S Z 0 1 2 5`, so no phonetic pair collides.

- [ ] **Step 1: Write the failing tests**

```python
def test_spell_code_uses_phonetics_and_speaks_the_dash():
    assert online_activation.spell_code("WKQR-3468") == (
        "Whiskey, Kilo, Quebec, Romeo, dash, three, four, six, eight"
    )


def test_spell_code_accepts_an_undashed_code():
    assert online_activation.spell_code("WKQR3468").startswith("Whiskey, Kilo")


def test_start_returns_an_activation():
    def transport(url, payload, headers, method=None):
        assert url.endswith("/api/freight-fate/activate/start")
        return {
            "device_code": "a" * 64,
            "user_code": "WKQR-3468",
            "verification_uri": "https://orinks.net/activate",
            "verification_uri_complete": "https://orinks.net/activate?code=WKQR-3468",
            "expires_in": 600,
            "interval": 3,
        }

    activation = online_activation.start_activation(transport=transport)
    assert activation is not None
    assert activation.user_code == "WKQR-3468"
    assert activation.interval == 3


def test_poll_ready_carries_the_display_name():
    """The display name is the player's only signal that someone else claimed
    their code -- the game speaks it, so it must survive the poll."""
    def transport(url, payload, headers, method=None):
        return {
            "status": "ready",
            "driver_id": "rig-hauler",
            "token": "ffd_" + "b" * 64,
            "display_name": "Rig Hauler",
        }

    result = online_activation.poll_activation(_an_activation(), transport=transport)
    assert result.status == "ready"
    assert result.display_name == "Rig Hauler"


def test_poll_maps_410_to_expired_and_400_to_corrupt():
    """410 means the code timed out and a new one will fix it. 400 means the
    stored secret is malformed, which retrying the same code never fixes."""
    assert _poll_raising(_http_error(410)).status == "expired"
    assert _poll_raising(_http_error(400)).status == "error"
```

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_online_activation.py -v`

- [ ] **Step 3: Implement the module**

Map HTTP status to result. `urllib` raises `HTTPError` for 4xx/5xx, so catch it and read `.code`: 410 → `expired`, 400 → `error`, anything else → `error`. Never let an exception escape to the caller — a network blip during polling must not crash the menu.

- [ ] **Step 4: Run the tests**

- [ ] **Step 5: Commit**

```bash
git add src/freight_fate/online_activation.py tests/test_online_activation.py
git commit -m "feat(online): activation start, poll, and phonetic code spelling"
```

---

### Task 3: Rework `OnlineSetupState`

**Files:** modify `src/freight_fate/states/online_states.py`, `tests/test_online_setup.py` (create if absent)

Read the spec's "Menu", "Reviewing the code", and "Spoken behavior and errors" sections first.

**The menu is static at five items**, as the class docstring requires — players build positional memory and `refresh()` preserves indices, not identity:

1. Set up this computer with orinks.net
2. Say my activation code again
3. Copy my activation code
4. Hear what gets shared
5. Cancel

Items 2 and 3 are the review affordances. The game cannot offer a screen reader review cursor, so item 2 spells the code phonetically via `spell_code` and item 3 writes it to the clipboard with `write_clipboard_text`, speaking whether that succeeded — never claim a copy that failed. Both stay available for as long as an activation is live, and both are the fallback when `webbrowser.open` does nothing.

**Polling** reuses the existing `_outcome` mailbox that `update()` already drains, with a daemon thread and a `threading.Event` that stops it when the player leaves the menu. Interval: 3 seconds for the first 30, then 8, until expiry.

**On success**, speak the display name: "Connected to orinks.net as Rig Hauler." That is the player's only way to learn that someone else claimed their code.

Every failure is spoken and none is a dead end. Start failure, expiry (offer a new code), a 400 meaning the stored secret is corrupt, a browser that would not open (speak the address and the code, keep polling), and the existing keyring-failure message reused verbatim on save.

- [ ] **Step 1: Write the failing tests**

Cover, with an injected transport so nothing touches the network: starting speaks the code; the repeat item spells it; the copy item reports success and reports failure honestly; a pending poll keeps waiting; a ready poll adopts the identity and speaks the display name; expiry speaks the recovery; leaving the menu stops the worker.

- [ ] **Step 2: Run and watch them fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the suite**

Run: `uv run pytest && uv run ruff check src tests tools`

- [ ] **Step 5: Commit**

---

### Task 4: Reach a protected preview

**Files:** modify `src/freight_fate/online_presence.py`, `tests/test_online_presence.py`

Vercel preview deployments sit behind Deployment Protection, so pointing the game at one with `FREIGHT_FATE_ONLINE_URL` currently gets a 302 to SSO instead of JSON. Add an env-gated header in `_http_json`'s `all_headers`:

```python
    bypass = os.environ.get("FREIGHT_FATE_ONLINE_BYPASS")
    if bypass:
        # Vercel preview deployments are behind Deployment Protection, which
        # answers an unauthenticated API call with a redirect to SSO. This
        # lets a test build reach one without the project having to turn that
        # protection off for everybody. Unset in every shipped build.
        all_headers["x-vercel-protection-bypass"] = bypass
```

Test that the header is absent when the variable is unset and present when it is set. This is a permanent testing affordance, not scaffolding.

- [ ] **Step 5: Commit**

---

### Task 5: Player-facing documentation

**Files:** modify `CHANGELOG.md`, `ROADMAP.md`, `docs/ontology.md`

- `CHANGELOG.md`: an entry under `## Unreleased`, bold lead sentence then plain player language about what they will hear. CI fails this PR without one, because `src/` changed.
- `ROADMAP.md`: a bullet in the current release-line section.
- `docs/ontology.md`: the **activation code** row, plus **device code** marked as internal and never spoken.

- [ ] **Step 3: Commit**

---

## Manual verification

Run against the branch preview with both env vars set:

```bash
FREIGHT_FATE_ONLINE_URL=https://orinks-net-git-feat-activation-codes-orinks-projects.vercel.app FREIGHT_FATE_ONLINE_BYPASS=<secret> uv run freight-fate
```

Walk it with a screen reader running, since the review affordances are the point: start setup, hear the code, ask for it again and confirm the phonetic spelling is followable, copy it and paste it somewhere to confirm the copy is real, then confirm in the browser and check the game says the right display name. Then let a code expire without claiming it and confirm the spoken recovery.
