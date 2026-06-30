"""OSINT catalog capability layer.

The vendored OSINT Framework snapshot (backend/data/osint_framework.json) is a
flat list of ~1,098 tools, each carrying a homepage `url`, `entityKinds`,
`localInstall`, `registration` and `api` flags. By itself that is a *directory*:
you click a link and use the tool by hand.

This module turns every tool into an in-app *action*, classified honestly by what
its nature actually allows — there is no pretending a desktop installer or a
registration-walled SaaS returns live data through our backend. Three tiers:

  - "live"   — a keyless server-side enricher exists (see osint_enrich.py); the
               app fetches real facts. Highest capability, smallest set.
  - "pivot"  — the tool takes an entity value, so we can pre-fill it: either into
               the tool's *native* search URL (curated, host-keyed) or, for the
               long tail of tools we don't have a native pattern for, a *site*
               -scoped external search of the tool's domain. One click either way.
  - "launch" — no value to pre-fill (no entityKinds) or a local desktop install:
               we open the tool and copy the value to the clipboard for the user.

Pure + deterministic (no I/O, no DB) so it is cheap to apply at catalog load and
trivially testable. Run:  python -m backend.services.osint_catalog_test
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlparse

from backend.services import osint_enrich

_PATTERNS_PATH = Path(__file__).resolve().parents[1] / "data" / "osint_search_patterns.json"

# Single source of truth: which hosts have a keyless live enricher comes from the
# osint_enrich provider registry. A catalog tool on one of these hosts (matching the
# kind) is classified "live". Aliases map common catalog subdomains to the API host
# the registry keys on (e.g. the GreyNoise visualizer vs its API host).
_LIVE_ALIASES: dict[str, str] = {
    "viz.greynoise.io": "greynoise.io",
}
LIVE_HOSTS: dict[str, set[str]] = osint_enrich.live_host_kinds()
for _alias, _canon in _LIVE_ALIASES.items():
    if _canon in LIVE_HOSTS:
        LIVE_HOSTS.setdefault(_alias, set()).update(LIVE_HOSTS[_canon])

# Curated NATIVE search-URL patterns, keyed by host → {kind: template}. `{value}`
# is replaced with the URL-encoded entity. These upgrade a matched catalog tool
# from a bare homepage launch to a one-click native pivot. Intentionally the
# high-traffic, stable hosts — the long tail is handled by the site-scoped fallback.
NATIVE_SEARCH: dict[str, dict[str, str]] = {
    # ── username / social ────────────────────────────────────────────────────
    "github.com": {"username": "https://github.com/{value}"},
    "twitter.com": {"username": "https://twitter.com/{value}"},
    "x.com": {"username": "https://x.com/{value}"},
    "instagram.com": {"username": "https://www.instagram.com/{value}/"},
    "reddit.com": {"username": "https://www.reddit.com/user/{value}"},
    "facebook.com": {"username": "https://www.facebook.com/{value}", "name": "https://www.facebook.com/search/top?q={value}"},
    "flickr.com": {"username": "https://www.flickr.com/people/{value}"},
    "tiktok.com": {"username": "https://www.tiktok.com/@{value}"},
    "t.me": {"username": "https://t.me/{value}"},
    # ── domain / infrastructure ──────────────────────────────────────────────
    "crt.sh": {"domain": "https://crt.sh/?q={value}"},
    "virustotal.com": {"domain": "https://www.virustotal.com/gui/domain/{value}",
                       "ip": "https://www.virustotal.com/gui/ip-address/{value}",
                       "hash": "https://www.virustotal.com/gui/file/{value}"},
    "www.virustotal.com": {"domain": "https://www.virustotal.com/gui/domain/{value}",
                           "ip": "https://www.virustotal.com/gui/ip-address/{value}",
                           "hash": "https://www.virustotal.com/gui/file/{value}"},
    "urlscan.io": {"domain": "https://urlscan.io/domain/{value}"},
    "shodan.io": {"domain": "https://www.shodan.io/search?query={value}", "ip": "https://www.shodan.io/host/{value}"},
    "www.shodan.io": {"domain": "https://www.shodan.io/search?query={value}", "ip": "https://www.shodan.io/host/{value}"},
    "builtwith.com": {"domain": "https://builtwith.com/{value}"},
    "web.archive.org": {"domain": "https://web.archive.org/web/*/{value}"},
    "whois.com": {"domain": "https://www.whois.com/whois/{value}"},
    "securitytrails.com": {"domain": "https://securitytrails.com/domain/{value}/dns"},
    "censys.io": {"ip": "https://search.censys.io/hosts/{value}"},
    "search.censys.io": {"ip": "https://search.censys.io/hosts/{value}"},
    "otx.alienvault.com": {"domain": "https://otx.alienvault.com/indicator/domain/{value}",
                           "ip": "https://otx.alienvault.com/indicator/ip/{value}"},
    "urlhaus.abuse.ch": {"domain": "https://urlhaus.abuse.ch/browse.php?search={value}"},
    # ── ip ───────────────────────────────────────────────────────────────────
    "abuseipdb.com": {"ip": "https://www.abuseipdb.com/check/{value}"},
    "www.abuseipdb.com": {"ip": "https://www.abuseipdb.com/check/{value}"},
    "ipinfo.io": {"ip": "https://ipinfo.io/{value}"},
    "criminalip.io": {"ip": "https://www.criminalip.io/asset/report/{value}"},
    "projecthoneypot.org": {"ip": "https://www.projecthoneypot.org/ip_{value}"},
    # ── email ──────────────────────────────────────────────────────────────
    "emailrep.io": {"email": "https://emailrep.io/{value}"},
    "intelx.io": {"email": "https://intelx.io/?s={value}", "name": "https://intelx.io/?s={value}", "username": "https://intelx.io/?s={value}"},
    "hunter.io": {"domain": "https://hunter.io/search/{value}"},
    "thatsthem.com": {"email": "https://thatsthem.com/email/{value}", "phone": "https://thatsthem.com/phone/{value}"},
    # ── name / records ───────────────────────────────────────────────────────
    "linkedin.com": {"name": "https://www.linkedin.com/search/results/all/?keywords={value}"},
    "www.linkedin.com": {"name": "https://www.linkedin.com/search/results/all/?keywords={value}"},
    "opencorporates.com": {"name": "https://opencorporates.com/companies?q={value}"},
    "aleph.occrp.org": {"name": "https://aleph.occrp.org/search/?q={value}"},
    "courtlistener.com": {"name": "https://www.courtlistener.com/?q={value}"},
    "www.courtlistener.com": {"name": "https://www.courtlistener.com/?q={value}"},
    "sanctionssearch.ofac.treas.gov": {"name": "https://sanctionssearch.ofac.treas.gov/"},
    # ── location ─────────────────────────────────────────────────────────────
    "google.com": {"name": "https://www.google.com/search?q=%22{value}%22",
                   "location": "https://www.google.com/maps/search/{value}"},
    "www.google.com": {"name": "https://www.google.com/search?q=%22{value}%22",
                       "location": "https://www.google.com/maps/search/{value}"},
    "openstreetmap.org": {"location": "https://www.openstreetmap.org/search?query={value}"},
    "www.openstreetmap.org": {"location": "https://www.openstreetmap.org/search?query={value}"},
    "bing.com": {"location": "https://www.bing.com/maps?q={value}", "name": "https://www.bing.com/search?q=%22{value}%22"},
    "www.bing.com": {"location": "https://www.bing.com/maps?q={value}", "name": "https://www.bing.com/search?q=%22{value}%22"},
    "wikimapia.org": {"location": "https://wikimapia.org/#search={value}"},
    # ── phone ──────────────────────────────────────────────────────────────
    "numlookup.com": {"phone": "https://www.numlookup.com/results?phone={value}"},
    "www.numlookup.com": {"phone": "https://www.numlookup.com/results?phone={value}"},
    "truecaller.com": {"phone": "https://www.truecaller.com/search/in/{value}"},
    # ── crypto ─────────────────────────────────────────────────────────────
    "blockchair.com": {"crypto": "https://blockchair.com/search?q={value}"},
    "etherscan.io": {"crypto": "https://etherscan.io/address/{value}"},
    "bscscan.com": {"crypto": "https://bscscan.com/address/{value}"},
    "tronscan.org": {"crypto": "https://tronscan.org/#/address/{value}"},
    "chainabuse.com": {"crypto": "https://www.chainabuse.com/address/{value}"},
    "www.chainabuse.com": {"crypto": "https://www.chainabuse.com/address/{value}"},
    "walletexplorer.com": {"crypto": "https://www.walletexplorer.com/address/{value}"},
    "www.walletexplorer.com": {"crypto": "https://www.walletexplorer.com/address/{value}"},
    "blockchain.com": {"crypto": "https://www.blockchain.com/explorer/search?search={value}"},
    # ── hash / malware ─────────────────────────────────────────────────────
    "bazaar.abuse.ch": {"hash": "https://bazaar.abuse.ch/browse.php?search={value}"},
    "hybrid-analysis.com": {"hash": "https://www.hybrid-analysis.com/search?query={value}"},
    "www.hybrid-analysis.com": {"hash": "https://www.hybrid-analysis.com/search?query={value}"},
    "tria.ge": {"hash": "https://tria.ge/s?q={value}"},
    "threatfox.abuse.ch": {"hash": "https://threatfox.abuse.ch/browse.php?search=ioc%3A{value}",
                           "domain": "https://threatfox.abuse.ch/browse.php?search=ioc%3A{value}",
                           "ip": "https://threatfox.abuse.ch/browse.php?search=ioc%3A{value}"},
    # ── cve ────────────────────────────────────────────────────────────────
    "nvd.nist.gov": {"cve": "https://nvd.nist.gov/vuln/detail/{value}"},
    "cve.org": {"cve": "https://www.cve.org/CVERecord?id={value}"},
    "www.cve.org": {"cve": "https://www.cve.org/CVERecord?id={value}"},
    "cve.mitre.org": {"cve": "https://cve.mitre.org/cgi-bin/cvename.cgi?name={value}"},
    "exploit-db.com": {"cve": "https://www.exploit-db.com/search?cve={value}"},
    "www.exploit-db.com": {"cve": "https://www.exploit-db.com/search?cve={value}"},
    # ── vehicle ──────────────────────────────────────────────────────────────
    "flightradar24.com": {"vehicle": "https://www.flightradar24.com/data/aircraft/{value}"},
    "www.flightradar24.com": {"vehicle": "https://www.flightradar24.com/data/aircraft/{value}"},
    "globe.adsbexchange.com": {"vehicle": "https://globe.adsbexchange.com/?reg={value}"},
    "marinetraffic.com": {"vehicle": "https://www.marinetraffic.com/en/ais/index/search/all?keyword={value}"},
    "www.marinetraffic.com": {"vehicle": "https://www.marinetraffic.com/en/ais/index/search/all?keyword={value}"},
    "vesselfinder.com": {"vehicle": "https://www.vesselfinder.com/vessels?name={value}"},
    "www.vesselfinder.com": {"vehicle": "https://www.vesselfinder.com/vessels?name={value}"},
    # ── media / reverse image ──────────────────────────────────────────────
    "tineye.com": {"media": "https://tineye.com/search?url={value}", "image": "https://tineye.com/search?url={value}"},
    "yandex.com": {"media": "https://yandex.com/images/search?rpt=imageview&url={value}",
                   "image": "https://yandex.com/images/search?rpt=imageview&url={value}"},
    "lens.google.com": {"media": "https://lens.google.com/uploadbyurl?url={value}",
                        "image": "https://lens.google.com/uploadbyurl?url={value}"},
}

# A site-scoped external search for the long tail: search the tool's own domain for
# the value via a general search engine. Honest fallback — it's a real pivot into
# that tool's site, just not the tool's native search box.
_SITE_SEARCH = "https://www.google.com/search?q=site:{host}+{value}"


def host_of(url: str) -> str:
    """Normalized hostname (lowercased, no leading 'www.') for display/site-scope."""
    h = _registry_key(url)
    return h[4:] if h.startswith("www.") else h


def _registry_key(url: str) -> str:
    """The raw lowercased hostname (keeps any 'www.' prefix for exact registry hits)."""
    try:
        return (urlparse(url).hostname or "").lower()
    except (ValueError, TypeError):
        return ""


def _live_kinds(url: str) -> set[str]:
    h = _registry_key(url)
    bare = h[4:] if h.startswith("www.") else h
    return LIVE_HOSTS.get(h) or LIVE_HOSTS.get(bare) or set()


@lru_cache(maxsize=1)
def _search_patterns() -> dict[str, dict[str, str]]:
    """In-code NATIVE_SEARCH seed merged with the curated patterns file (file wins
    per-kind). Missing/corrupt file ⇒ just the seed. Cached."""
    merged: dict[str, dict[str, str]] = {h: dict(k) for h, k in NATIVE_SEARCH.items()}
    try:
        with open(_PATTERNS_PATH, encoding="utf-8") as f:
            for host, kinds in (json.load(f).get("patterns") or {}).items():
                merged.setdefault(host.lower(), {}).update(kinds)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return merged


def _native_map(url: str) -> dict[str, str]:
    pats = _search_patterns()
    h = _registry_key(url)
    bare = h[4:] if h.startswith("www.") else h
    return pats.get(h) or pats.get(bare) or {}


def capability_of(tool: dict) -> str:
    """Classify a catalog tool: 'live' | 'pivot' | 'launch'. Pure function of the
    tool's url + flags + entityKinds."""
    url = tool.get("url") or ""
    kinds = tool.get("entityKinds") or []
    if _live_kinds(url) & set(kinds):
        return "live"
    # A local desktop install can't be driven by a pre-filled URL, no matter its
    # input kind — it's a launch-and-use tool.
    if tool.get("localInstall"):
        return "launch"
    if kinds:
        return "pivot"
    return "launch"


def search_url_for(tool: dict, kind: str, encoded_value: str) -> tuple[str, bool] | None:
    """Resolve a one-click URL for `tool` against an already-URL-encoded value.

    Returns (url, native) where native=True means the tool's own search, False a
    site-scoped fallback. Returns None when no pivot is possible (launch-only)."""
    url = tool.get("url") or ""
    if tool.get("localInstall"):
        return None
    native = _native_map(url).get(kind)
    if native:
        return native.replace("{value}", encoded_value), True
    if kind in (tool.get("entityKinds") or []):
        h = host_of(url)
        if h:
            return _SITE_SEARCH.replace("{host}", h).replace("{value}", encoded_value), False
    return None


def augment(tool: dict) -> dict:
    """Return a shallow copy of `tool` with a `capability` field added. Used when
    serving the full catalog so every tool is badged by what it can actually do."""
    out = dict(tool)
    out["capability"] = capability_of(tool)
    return out


def catalog_investigate(value: str, kind: str, tools: list[dict], limit: int = 40) -> list[dict]:
    """All catalog tools that accept `kind`, each resolved to a one-click action.

    Ranked live → native pivot → site-scoped pivot → launch. github.com is heavily
    over-represented by code repos that aren't per-value investigations, so it is
    only kept when it has a native pattern for the kind (the username profile URL).
    """
    encoded = quote(value, safe="")
    scored: list[tuple[int, dict]] = []
    for t in tools:
        if kind not in (t.get("entityKinds") or []):
            continue
        cap = capability_of(t)
        resolved = search_url_for(t, kind, encoded)
        h = host_of(t.get("url") or "")
        # Drop the github repo noise unless it's a real native pivot for this kind.
        if h == "github.com" and not (resolved and resolved[1]):
            continue
        if resolved:
            url, native = resolved
            rank = 0 if cap == "live" else (1 if native else 2)
        else:
            url, native = (t.get("url") or ""), False
            rank = 3
        scored.append((rank, {
            "name": t.get("name"),
            "url": url,
            "note": None if native or cap != "launch" else "open tool, then paste the value",
            "templated": bool(resolved),
            "capability": cap,
            "native": native,
            "source": "catalog",
            "category": t.get("category"),
            "pricing": t.get("pricing"),
            "opsec": t.get("opsec"),
            "registration": bool(t.get("registration")),
        }))
    scored.sort(key=lambda x: x[0])
    return [item for _, item in scored[:limit]]


def capability_counts(tools: list[dict]) -> dict[str, int]:
    """Per-tier tool counts across the catalog — for honest 'functional' reporting."""
    out = {"live": 0, "pivot": 0, "launch": 0}
    for t in tools:
        out[capability_of(t)] += 1
    return out
