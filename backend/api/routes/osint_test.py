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
    framework, investigate, detect_entity_kind, _templated, _load,
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

# ── framework: full catalog for everyone; investigate templates paid-only ─────
all_tools = _load().get("tools", [])
free = asyncio.run(framework(user=_FakeUser("free")))
ok("free tier sees full catalog (all tools)", len(free["tools"]) == len(all_tools) > 1000)
ok("free tier sees all 33 categories", len(free["categories"]) == 33)
ok("free tier not limited", free["limited"] is False)
ok("free tier hides investigate templates", free["templates"] == {})

paid = asyncio.run(framework(user=_FakeUser("pro")))
ok("paid tier sees full catalog too", len(paid["tools"]) == len(free["tools"]))
ok("paid tier exposes templates", len(paid["templates"]) > 0)

# ── entity-kind detection ────────────────────────────────────────────────────
ok("detect ip", detect_entity_kind("8.8.8.8") == "ip")
ok("detect email", detect_entity_kind("a@b.com") == "email")
ok("detect domain", detect_entity_kind("example.com") == "domain")
ok("detect username", detect_entity_kind("janedoe") == "username")
ok("detect name (multiword)", detect_entity_kind("Jane Doe") == "name")
ok("detect location (coords)", detect_entity_kind("40.7,-74.0") == "location")
# new per-category entity kinds
ok("detect cve", detect_entity_kind("CVE-2024-3094") == "cve")
ok("detect crypto (eth addr)", detect_entity_kind("0x" + "a" * 40) == "crypto")
ok("detect crypto (btc legacy)", detect_entity_kind("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2") == "crypto")
ok("detect hash (sha256)", detect_entity_kind("a" * 64) == "hash")
ok("detect vehicle (imo)", detect_entity_kind("IMO 9074729") == "vehicle")

# ── templating substitutes + url-encodes ─────────────────────────────────────
dom = _templated("example.com", "domain")
ok("domain templates returned", len(dom) > 0)
ok("templated url substitutes value", any("example.com" in t["url"] for t in dom))
ok("unknown kind → empty", _templated("x", "nonsense") == [])
nm = _templated("Acme Corp", "name")
ok("name value url-encoded (space → %20)", any("Acme%20Corp" in t["url"] for t in nm))
# per-category investigator templates resolve
cr = _templated("0x" + "a" * 40, "crypto")
ok("crypto templates returned", len(cr) > 0 and any("etherscan" in t["url"] for t in cr))
ha = _templated("d" * 64, "hash")
ok("hash templates returned", len(ha) > 0 and any("virustotal.com/gui/file" in t["url"] for t in ha))
cve = _templated("CVE-2024-3094", "cve")
ok("cve templates returned", len(cve) > 0 and any("nvd.nist.gov" in t["url"] for t in cve))
veh = _templated("IMO 9074729", "vehicle")
ok("vehicle templates returned", len(veh) > 0)
med = _templated("https://example.com/x.jpg", "media")
ok("media templates returned + url-encoded", len(med) > 0 and any("%3A%2F%2F" in t["url"] for t in med))

# ── investigate: free gated, paid resolves ───────────────────────────────────
inv_free = asyncio.run(investigate(user=_FakeUser("free"), value="8.8.8.8", kind="ip"))
ok("free investigate gated (empty)", inv_free["tools"] == [] and inv_free["limited"] is True)

inv_paid = asyncio.run(investigate(user=_FakeUser("pro"), value="8.8.8.8", kind="ip"))
ok("paid investigate returns ip tools", len(inv_paid["tools"]) > 0 and inv_paid["kind"] == "ip")

inv_auto = asyncio.run(investigate(user=_FakeUser("pro"), value="example.com", kind=None))
ok("investigate auto-detects kind", inv_auto["kind"] == "domain")

inv_cve = asyncio.run(investigate(user=_FakeUser("pro"), value="CVE-2024-3094", kind=None))
ok("investigate auto-detects cve", inv_cve["kind"] == "cve" and len(inv_cve["tools"]) > 0)

inv_empty = asyncio.run(investigate(user=_FakeUser("pro"), value="", kind=None))
ok("empty value → no tools", inv_empty["tools"] == [])

print(f"\nosint: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
