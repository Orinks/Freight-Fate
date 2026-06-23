"""Publish the built zip to here.now, reusing the SAME URL across rebuilds.

here.now gives an anonymous site a ``slug`` and a ``claimToken`` on first
publish. To push a new build to the *same* URL we re-use that pair:

    POST /api/v1/publish               -> create (first time only)
    PUT  /api/v1/publish/{slug}        -> update existing site (same URL)
    POST /api/v1/publish/{slug}/finalize

The slug + claimToken are saved to ``.herenow_site.json`` (gitignored) so the
next run updates the same site instead of minting a new URL. Anonymous sites
auto-expire after 24h of inactivity; each publish refreshes that window, so
keep publishing within 24h to keep the URL alive (for a permanent URL, claim
the site with an API key via the printed claimUrl).

Run:  uv run python publish_herenow.py
Prints the live download URL.
"""
import json
import os
import urllib.error
import urllib.request

BASE = "https://here.now"
FP = "dist/FreightFate-osm-expansion-test-windows-portable.zip"
NAME = os.path.basename(FP)
SIZE = os.path.getsize(FP)
CT = "application/zip"
UA = "FreightFate-dev/1.0"
STATE_FILE = ".herenow_site.json"


def call(method, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.status, r.read()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def save_state(slug, claim_token, claim_url):
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump({"slug": slug, "claimToken": claim_token,
                   "claimUrl": claim_url}, fh, indent=2)


def manifest_body(claim_token=None):
    body = {"files": [{"path": NAME, "size": SIZE, "contentType": CT}]}
    if claim_token:
        body["claimToken"] = claim_token
    return json.dumps(body).encode()


def main():
    state = load_state()
    headers = {"Content-Type": "application/json"}

    if state and state.get("slug"):
        slug, claim = state["slug"], state.get("claimToken")
        print(f"updating existing site: {slug}")
        try:
            st, body = call("PUT", f"{BASE}/api/v1/publish/{slug}",
                            manifest_body(claim), headers)
            print("update:", st)
            create = json.loads(body)
            create.setdefault("slug", slug)
            create.setdefault("claimToken", claim)
        except urllib.error.HTTPError as e:
            # Slug expired (404) or token rejected (401/403) -> start fresh.
            print(f"update failed ({e.code}); creating a new site instead.")
            state = None

    if not state or not state.get("slug"):
        st, body = call("POST", f"{BASE}/api/v1/publish", manifest_body(), headers)
        print("create:", st)
        create = json.loads(body)

    slug = create.get("slug")
    claim_token = create.get("claimToken") or (state or {}).get("claimToken")
    print("slug:", slug)

    up = create["upload"]
    entry = next(u for u in up["uploads"] if u["path"] == NAME)

    # Upload bytes to the presigned R2 URL with the headers it specified.
    with open(FP, "rb") as fh:
        data = fh.read()
    st2, _ = call("PUT", entry["url"], data,
                  entry.get("headers", {"Content-Type": CT}))
    print("upload:", st2)

    # Finalize.
    st3, body3 = call("POST", up["finalizeUrl"],
                      json.dumps({"versionId": up["versionId"]}).encode(),
                      headers)
    print("finalize:", st3)
    fin = json.loads(body3)

    claim_url = create.get("claimUrl") or fin.get("claimUrl")
    if slug:
        save_state(slug, claim_token, claim_url)

    site = create.get("siteUrl") or fin.get("siteUrl") or fin.get("url")
    print("\n=== LIVE ===")
    print("site:", site)
    print("download:", f"{site.rstrip('/')}/{NAME}" if site else "(see JSON)")
    print("claimUrl (claim with an API key for a permanent URL):", claim_url)
    print(f"\nsaved {STATE_FILE} -> next build reuses this URL")


if __name__ == "__main__":
    main()
