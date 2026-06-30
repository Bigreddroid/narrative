"""Property tests for the OSINT catalog capability layer (no network/DB).
Run from repo root:  python -m backend.services.osint_catalog_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.services import osint_catalog as oc

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# ── host normalization ────────────────────────────────────────────────────────
ok("host strips www", oc.host_of("https://www.shodan.io/host/1.1.1.1") == "shodan.io")
ok("host lowercases", oc.host_of("https://CRT.sh/?q=x") == "crt.sh")
ok("host empty on junk", oc.host_of("not a url") == "")

# ── capability classification ──────────────────────────────────────────────────
live_tool = {"url": "https://crt.sh/", "entityKinds": ["domain"], "localInstall": False}
ok("live host+kind → live", oc.capability_of(live_tool) == "live")

pivot_tool = {"url": "https://example-osint.org/tool", "entityKinds": ["domain"], "localInstall": False}
ok("entity-bearing non-native → pivot", oc.capability_of(pivot_tool) == "pivot")

local_tool = {"url": "https://maltego.com/", "entityKinds": ["domain"], "localInstall": True}
ok("local install → launch even with entity kinds", oc.capability_of(local_tool) == "launch")

no_kind_tool = {"url": "https://reference.example/", "entityKinds": [], "localInstall": False}
ok("no entity kinds → launch", oc.capability_of(no_kind_tool) == "launch")

# ── search URL resolution ──────────────────────────────────────────────────────
native = oc.search_url_for({"url": "https://www.shodan.io/", "entityKinds": ["ip"]}, "ip", "8.8.8.8")
ok("native search resolves with flag", native is not None and native[1] is True and "8.8.8.8" in native[0])

site = oc.search_url_for({"url": "https://obscure-osint.example/", "entityKinds": ["domain"]}, "domain", "x.com")
ok("site-scoped fallback for long tail", site is not None and site[1] is False and "site:obscure-osint.example" in site[0])

ok("no pivot for local install", oc.search_url_for({"url": "https://x.io/", "entityKinds": ["ip"], "localInstall": True}, "ip", "1.1.1.1") is None)
ok("no pivot for wrong kind", oc.search_url_for({"url": "https://x.io/", "entityKinds": ["domain"]}, "ip", "1.1.1.1") is None)

# ── value is url-encoded by catalog_investigate (search_url_for takes it pre-encoded) ──
enc_tools = [{"id": "z", "name": "Obscure Name Tool", "url": "https://obscure.example/",
              "entityKinds": ["name"], "category": "People", "pricing": "free", "opsec": "passive"}]
enc_res = oc.catalog_investigate("Jane Doe", "name", enc_tools)
ok("site-scoped url-encodes value", any("Jane%20Doe" in t["url"] for t in enc_res))

# ── catalog_investigate ranking + shape ────────────────────────────────────────
sample_tools = [
    {"id": "a", "name": "Shodan", "url": "https://www.shodan.io/", "entityKinds": ["ip"], "category": "IP", "pricing": "freemium", "opsec": "passive"},
    {"id": "b", "name": "Obscure IP Tool", "url": "https://obscure-ip.example/", "entityKinds": ["ip"], "category": "IP", "pricing": "free", "opsec": "passive"},
    {"id": "c", "name": "GreyNoise", "url": "https://viz.greynoise.io/", "entityKinds": ["ip"], "category": "IP", "pricing": "freemium", "opsec": "passive"},
    {"id": "d", "name": "Some Repo", "url": "https://github.com/foo/bar", "entityKinds": ["ip"], "category": "Tools", "pricing": "free", "opsec": "passive"},
    {"id": "e", "name": "Domain Only", "url": "https://dom.example/", "entityKinds": ["domain"], "category": "Domain", "pricing": "free", "opsec": "passive"},
]
res = oc.catalog_investigate("8.8.8.8", "ip", sample_tools)
names = [t["name"] for t in res]
ok("catalog_investigate filters to kind", "Domain Only" not in names)
ok("catalog_investigate drops github repo noise", "Some Repo" not in names)
ok("live ranked first", res[0]["capability"] == "live")
ok("items carry capability + native + source", all({"capability", "native", "source"} <= set(t) for t in res))
ok("native shodan present", any(t["name"] == "Shodan" and t["native"] for t in res))
ok("limit respected", len(oc.catalog_investigate("8.8.8.8", "ip", sample_tools, limit=1)) == 1)

# ── capability_counts sums to total ────────────────────────────────────────────
counts = oc.capability_counts(sample_tools)
ok("counts sum to tool total", sum(counts.values()) == len(sample_tools))
ok("counts has all three tiers", set(counts) == {"live", "pivot", "launch"})

print(f"\nosint_catalog: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
