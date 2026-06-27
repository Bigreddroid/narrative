"""Property tests for the OSINT Framework routes (no network/DB).
Calls the route handlers directly with a duck-typed user; data comes from the
vendored snapshot (backend/data/osint_framework.json).
Run from repo root:  python -m backend.api.routes.osint_test
"""

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.api.routes.osint import (
    framework, investigate, detect_entity_kind, _templated, _load, _FREE_TOOL_CAP,
)

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


class _FakeUser:  # the handlers only read user.tier
    def __init__(self, tier):
        self.tier = tier


# ── snapshot sanity ───────────────────────────────────────────────────────────
data = _load()
ok("snapshot has tools", len(data.get("tools", [])) > 200)
ok("snapshot has templates", isinstance(data.get("templates"), dict) and len(data["templates"]) > 0)

# ── framework: free taster vs paid full ──────────────────────────────────────
free = asyncio.run(framework(user=_FakeUser("free")))
ok("free tier is limited", free["limited"] is True)
ok("free tier capped at _FREE_TOOL_CAP", len(free["tools"]) <= _FREE_TOOL_CAP)
ok("free taster is free-priced only", all(t["pricing"] == "free" for t in free["tools"]))
ok("free tier hides templates", free["templates"] == {})

paid = asyncio.run(framework(user=_FakeUser("pro")))
ok("paid tier not limited", paid["limited"] is False)
ok("paid tier sees full catalog", len(paid["tools"]) > len(free["tools"]))
ok("paid tier exposes templates", len(paid["templates"]) > 0)

# ── entity-kind detection ────────────────────────────────────────────────────
ok("detect ip", detect_entity_kind("8.8.8.8") == "ip")
ok("detect email", detect_entity_kind("a@b.com") == "email")
ok("detect domain", detect_entity_kind("example.com") == "domain")
ok("detect username", detect_entity_kind("janedoe") == "username")
ok("detect name (multiword)", detect_entity_kind("Jane Doe") == "name")
ok("detect location (coords)", detect_entity_kind("40.7,-74.0") == "location")

# ── templating substitutes + url-encodes ─────────────────────────────────────
dom = _templated("example.com", "domain")
ok("domain templates returned", len(dom) > 0)
ok("templated url substitutes value", any("example.com" in t["url"] for t in dom))
ok("unknown kind → empty", _templated("x", "nonsense") == [])
nm = _templated("Acme Corp", "name")
ok("name value url-encoded (space → %20)", any("Acme%20Corp" in t["url"] for t in nm))

# ── investigate: free gated, paid resolves ───────────────────────────────────
inv_free = asyncio.run(investigate(user=_FakeUser("free"), value="8.8.8.8", kind="ip"))
ok("free investigate gated (empty)", inv_free["tools"] == [] and inv_free["limited"] is True)

inv_paid = asyncio.run(investigate(user=_FakeUser("pro"), value="8.8.8.8", kind="ip"))
ok("paid investigate returns ip tools", len(inv_paid["tools"]) > 0 and inv_paid["kind"] == "ip")

inv_auto = asyncio.run(investigate(user=_FakeUser("pro"), value="example.com", kind=None))
ok("investigate auto-detects kind", inv_auto["kind"] == "domain")

inv_empty = asyncio.run(investigate(user=_FakeUser("pro"), value="", kind=None))
ok("empty value → no tools", inv_empty["tools"] == [])

print(f"\nosint: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
