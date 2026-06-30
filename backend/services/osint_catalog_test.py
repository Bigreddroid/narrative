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

# ── entityKinds override recovery ───────────────────────────────────────────────
# A tool the vendored catalog left as entityKinds:[] but the curated override file
# tags should behave as if it carried that kind natively.
overrides = oc._kind_overrides()
ok("override map is non-empty", len(overrides) > 0)
sample_id = next(iter(overrides))
recovered = {"id": sample_id, "url": "https://example.org/", "entityKinds": []}
ok("_effective_kinds falls back to override", oc._effective_kinds(recovered) == overrides[sample_id])
ok("explicit kinds win over override", oc._effective_kinds({"id": sample_id, "entityKinds": ["ip"]}) == ["ip"])
ok("unknown id with no kinds stays empty", oc._effective_kinds({"id": "no-such-id", "entityKinds": []}) == [])
# A recovered tool is no longer a dead launch: it earns a real capability and is
# investigable. (NVD even reaches 'live' via the keyless CVE enricher.)
nvd = {"id": "cyber-threat-intelligence-nvd-nist", "name": "NVD", "url": "https://nvd.nist.gov/",
       "entityKinds": [], "category": "Cyber Threat Intelligence", "pricing": "free", "opsec": "passive"}
ok("recovered NVD escapes launch tier", oc.capability_of(nvd) in {"live", "pivot"})
ok("recovered NVD investigable by cve", any(t["name"] == "NVD" for t in oc.catalog_investigate("CVE-2024-3094", "cve", [nvd])))
# A pure pivot recovery (site-scoped, no live enricher): a VIN decoder → vehicle.
vin = {"id": "transportation-carvertical-vin-decoder", "name": "carVertical", "url": "https://www.carvertical.com/",
       "entityKinds": [], "category": "Transportation", "pricing": "freemium", "opsec": "passive"}
ok("recovered VIN decoder classifies as pivot", oc.capability_of(vin) == "pivot")

# ── reachability: every catalog tool resolves to an action ──────────────────────
# The "every tool reachable" guarantee: no dead links. Each tool must have a
# resolvable host OR be a javascript: bookmarklet (a valid in-browser action).
import json as _json
from pathlib import Path as _Path
_cat = _json.loads((_Path(oc.__file__).resolve().parents[1] / "data" / "osint_framework.json").read_text(encoding="utf-8"))
_all_tools = _cat.get("tools", [])
ok("catalog loaded (1098 tools)", len(_all_tools) == 1098)
_unreachable = [t for t in _all_tools
                if not oc.host_of(t.get("url") or "")
                and not (t.get("url") or "").startswith("javascript:")]
ok("zero unreachable tools (no dead links)", len(_unreachable) == 0)
# Every override id must exist in the real catalog (no rot in the override map).
_ids = {t.get("id") for t in _all_tools}
_orphans = [tid for tid in overrides if tid not in _ids]
ok("no orphan override ids", len(_orphans) == 0)
# Every override tool was genuinely entity-less in the vendored data (honest recovery).
_already = [tid for tid in overrides if (next(t for t in _all_tools if t.get("id") == tid).get("entityKinds") or [])]
ok("overrides only recover entity-less tools", len(_already) == 0)

print(f"\nosint_catalog: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
