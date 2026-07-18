"""Property tests for the Mastodon OSINT parser (pure, no network). Run from repo root:
    python -m backend.feeds.mastodon_osint_test"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.feeds import mastodon_osint as M

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# A realistic Mastodon Status object (public tag-timeline shape).
_STATUS = {
    "id": "112233445566",
    "created_at": "2026-07-18T09:15:30.000Z",
    "content": "<p>Explosion reported near the port in <a href=\"#\">Odesa</a> &amp; smoke visible</p>",
    "url": "https://mastodon.social/@user/112233445566",
    "uri": "https://mastodon.social/users/user/statuses/112233445566",
    "favourites_count": 12,
    "replies_count": 3,
    "account": {"bot": False},
    "card": {"title": "Odesa port hit"},
}


def _one(status):
    out = M.parse_mastodon([status], "osint")
    return out[0] if out else None


# ── html stripping + entity unescaping ──────────────────────────────────────
c = _one(_STATUS)
ok("parses a normal status", c is not None)
ok("strips HTML tags", "<p>" not in c["title"] and "<a" not in c["title"])
ok("unescapes entities", "&" in c["selftext"] and "&amp;" not in c["selftext"])
ok("title carries the text", c["title"].startswith("Explosion reported near the port"))

# ── field mapping ───────────────────────────────────────────────────────────
ok("external_id is prefixed + hashed", c["external_id"].startswith("mastodon-")
   and len(c["external_id"]) == len("mastodon-") + 16)
ok("source-context slot names the tag", c["subreddit"] == "mastodon #osint")
ok("url mapped", c["url"] == "https://mastodon.social/@user/112233445566")
ok("counts mapped to score/comments", c["score"] == 12 and c["num_comments"] == 3)
ok("created_at parsed to epoch", isinstance(c["created_utc"], float) and c["created_utc"] > 0)

# ── url falls back to uri ────────────────────────────────────────────────────
no_url = dict(_STATUS, url=None)
ok("url falls back to uri", _one(no_url)["url"] == _STATUS["uri"])

# ── card-title fallback when content is empty ────────────────────────────────
empty_content = dict(_STATUS, content="")
ok("empty content falls back to card title", _one(empty_content)["title"] == "Odesa port hit")

# ── skip rules ───────────────────────────────────────────────────────────────
ok("skips reblogs (boosts)", M.parse_mastodon(
    [dict(_STATUS, content="", card={}, reblog={"id": "x"})], "osint") == [])
ok("skips bot accounts", M.parse_mastodon(
    [dict(_STATUS, account={"bot": True})], "osint") == [])
ok("skips fully-empty items", M.parse_mastodon(
    [dict(_STATUS, content="", card={})], "osint") == [])
ok("tolerates non-dict entries", M.parse_mastodon(["nope", None, 5], "osint") == [])
ok("handles None input", M.parse_mastodon(None, "osint") == [])

# ── batch dedupe by status id ────────────────────────────────────────────────
dupe = M.parse_mastodon([_STATUS, dict(_STATUS)], "osint")
ok("dedupes repeated status id within a batch", len(dupe) == 1)

# ── selftext length cap ──────────────────────────────────────────────────────
long_status = dict(_STATUS, content="<p>" + ("x" * 1000) + "</p>")
ok("selftext capped at 500", len(_one(long_status)["selftext"]) == 500)

# ── bad timestamp degrades to None, not a crash ──────────────────────────────
bad_ts = dict(_STATUS, created_at="not-a-date")
ok("bad timestamp -> None", _one(bad_ts)["created_utc"] is None)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
