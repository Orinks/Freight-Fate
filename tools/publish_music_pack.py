"""Publish a rebuilt music.pak to the private download host (a here.now site).

Release builds fetch ``music.pak`` from ``DEFAULT_MUSIC_URL`` in
build_release.py, a Vercel redirect onto a here.now site, and verify it
against ``DEFAULT_MUSIC_SHA256``. After repacking, bump that constant and
the test pins, then run this to put the new bytes behind the same URL.

Update an existing here.now site in place with a new music.pak.

Steps (here.now publish API): GET the site to learn its live files, PUT a
manifest that keeps every existing file and replaces music.pak, stream the
pack to the presigned upload URL, POST finalize. The API key is read from
~/.herenow/credentials and never printed.

Usage: uv run python tools/publish_music_pack.py --login <email>          # emails a code
       uv run python tools/publish_music_pack.py --verify <email> <code>  # stores the key
       uv run python tools/publish_music_pack.py crisp-crystal-9a9y src/freight_fate/music.pak [--dry-run]
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://here.now"
CRED = Path.home() / ".herenow" / "credentials"


def _call(method: str, url: str, body: dict | None = None, key: str | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:600]
        raise SystemExit(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc


def _key() -> str:
    env = os.environ.get("HERENOW_API_KEY")
    if env:
        return env.strip()
    if not CRED.exists():
        raise SystemExit(f"No API key at {CRED}; run --login <email> then --verify <email> <code>")
    return CRED.read_text(encoding="utf-8").strip()


def login(email: str) -> None:
    out = _call("POST", f"{BASE}/api/auth/agent/request-code", {"email": email})
    print("code requested:", {k: v for k, v in out.items() if k != "apiKey"})


def verify(email: str, code: str) -> None:
    out = _call("POST", f"{BASE}/api/auth/agent/verify-code", {"email": email, "code": code})
    api_key = out.get("apiKey")
    if not api_key:
        raise SystemExit(f"no apiKey in response: {list(out)}")
    CRED.parent.mkdir(parents=True, exist_ok=True)
    CRED.write_text(api_key + "\n", encoding="utf-8")
    with contextlib.suppress(OSError):
        CRED.chmod(0o600)
    print(f"API key stored at {CRED} ({len(api_key)} chars, prefix {api_key[:4]})")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _Progress:
    """File-like wrapper that reports upload progress on stderr."""

    def __init__(self, path: Path):
        self.f = path.open("rb")
        self.total = path.stat().st_size
        self.sent = 0
        self.next_mark = 0

    def read(self, n: int = -1) -> bytes:
        chunk = self.f.read(n)
        self.sent += len(chunk)
        if self.sent >= self.next_mark:
            print(f"  uploaded {self.sent / 1e6:,.0f} / {self.total / 1e6:,.0f} MB", flush=True)
            self.next_mark += 50_000_000
        return chunk

    def __len__(self) -> int:
        return self.total


def publish(slug: str, pack: Path, dry_run: bool) -> None:
    key = _key()
    site = _call("GET", f"{BASE}/api/v1/publish/{slug}", key=key)
    print("site:", json.dumps({k: site.get(k) for k in ("slug", "siteUrl", "currentVersionId")}))
    live = _call("GET", f"{BASE}/api/v1/publish/{slug}/files", key=key)
    print("live files:", json.dumps(live)[:1500])

    # Keep every existing file except the one we replace. Existing entries
    # are re-listed with their hashes so the API can skip re-uploading them.
    files = []
    existing = live.get("files") or live.get("items") or []
    for entry in existing:
        path = entry.get("path") or entry.get("name")
        if not path or path.lstrip("/") == pack.name:
            continue
        row = {"path": path.lstrip("/"), "size": entry.get("size")}
        for k in ("contentType", "hash"):
            if entry.get(k):
                row[k] = entry[k]
        files.append(row)
    files.append(
        {
            "path": pack.name,
            "size": pack.stat().st_size,
            "contentType": mimetypes.guess_type(pack.name)[0] or "application/octet-stream",
            "hash": _sha256(pack),
        }
    )
    body = {"files": files}
    base_version = site.get("currentVersionId")
    if base_version:
        body["baseVersionId"] = base_version
    print("manifest:", json.dumps(body, indent=1)[:1500])
    if dry_run:
        print("dry run: not publishing")
        return

    out = _call("PUT", f"{BASE}/api/v1/publish/{slug}", body, key=key)
    upload = out.get("upload") or {}
    print("skipped:", upload.get("skipped"))
    for item in upload.get("uploads") or []:
        local = pack if item["path"].lstrip("/") == pack.name else None
        if local is None:
            raise SystemExit(f"API wants an upload for {item['path']} which we do not have locally")
        headers = dict(item.get("headers") or {})
        headers["Content-Length"] = str(local.stat().st_size)
        body_stream = _Progress(local)
        req = urllib.request.Request(item["url"], data=body_stream, method="PUT", headers=headers)
        print(f"uploading {local.name} ({local.stat().st_size:,} bytes)...", flush=True)
        with urllib.request.urlopen(req, timeout=3600) as resp:
            print("  upload status", resp.status)
    version_id = upload.get("versionId")
    fin = _call("POST", upload["finalizeUrl"], {"versionId": version_id}, key=key)
    print("finalized:", json.dumps({k: fin.get(k) for k in ("currentVersionId", "code", "error")}))
    print("live at:", out.get("siteUrl") or site.get("siteUrl"))


def main(argv: list[str]) -> int:
    if argv[:1] == ["--login"]:
        login(argv[1])
        return 0
    if argv[:1] == ["--verify"]:
        verify(argv[1], argv[2])
        return 0
    dry = "--dry-run" in argv
    args = [a for a in argv if a != "--dry-run"]
    publish(args[0], Path(args[1]), dry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
