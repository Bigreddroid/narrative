"""Live keyless OSINT enrichment — Tier 1.

Turns an entity value into *real facts* fetched server-side, using only keyless,
free, passive endpoints. This is the high-value subset of the 1,098-tool catalog
that exposes a machine-readable API with no key or registration.

Architecture — a **provider registry**: each provider is a small best-effort
fetcher tagged with the kinds it handles. `enrich()` runs every provider for the
requested kind and merges their facts. Adding a new keyless source = appending one
`Provider` to `PROVIDERS` (+ a stubbed test).

Design stance (mirrors backend/feeds/osint_threatintel.py):
  * lazy-import httpx so the module imports without the dep (tests stub the network);
  * every fetcher is best-effort with a short timeout and returns [] on ANY failure
    — enrichment is additive, it must never break the investigate flow;
  * each fact is a flat {label, value, source, url} dict the UI renders verbatim;
  * results are cached in Redis (per-kind TTL) so repeat lookups are instant and we
    stay well inside every provider's free rate limit.

Run:  python -m backend.services.osint_enrich_test
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

USER_AGENT = "the-narrative-osint/0.4 (+https://thenarrative.io)"
_TIMEOUT = 8.0

# Per-kind cache TTL (seconds). CVEs are effectively static; IP/geo and chain data
# change slowly enough that a day is fine and keeps us far under free rate limits.
_TTL = {"ip": 86400, "domain": 43200, "cve": 604800, "hash": 604800, "crypto": 21600}


def _fact(label: str, value, source: str, url: str | None = None) -> dict:
    return {"label": label, "value": str(value), "source": source, "url": url}


async def _get_json(client, url: str, headers: dict | None = None):
    resp = await client.get(url, headers=headers) if headers else await client.get(url)
    resp.raise_for_status()
    return resp.json()


# ── per-provider fetchers (keyless) ─────────────────────────────────────────────
async def _ip_api(client, value: str) -> list[dict]:
    facts: list[dict] = []
    d = await _get_json(client, f"http://ip-api.com/json/{value}?fields=status,country,regionName,city,isp,org,as,reverse,proxy,hosting")
    if isinstance(d, dict) and d.get("status") == "success":
        loc = ", ".join(x for x in (d.get("city"), d.get("regionName"), d.get("country")) if x)
        if loc:
            facts.append(_fact("Location", loc, "ip-api.com"))
        if d.get("as"):
            facts.append(_fact("ASN", d["as"], "ip-api.com"))
        if d.get("isp"):
            facts.append(_fact("ISP", d["isp"], "ip-api.com"))
        if d.get("org"):
            facts.append(_fact("Org", d["org"], "ip-api.com"))
        if d.get("reverse"):
            facts.append(_fact("rDNS", d["reverse"], "ip-api.com"))
        flags = [k for k in ("proxy", "hosting") if d.get(k)]
        if flags:
            facts.append(_fact("Flags", "/".join(flags), "ip-api.com"))
    return facts


async def _greynoise(client, value: str) -> list[dict]:
    d = await _get_json(client, f"https://api.greynoise.io/v3/community/{value}")
    if isinstance(d, dict) and d.get("noise") is not None:
        label = f"{d.get('classification', 'unknown')}"
        if d.get("name") and d["name"] != "unknown":
            label += f" · {d['name']}"
        return [_fact("GreyNoise", label, "greynoise.io", f"https://viz.greynoise.io/ip/{value}")]
    return []


async def _ipwhois(client, value: str) -> list[dict]:
    d = await _get_json(client, f"https://ipwho.is/{value}")
    if isinstance(d, dict) and d.get("success"):
        facts = []
        conn = d.get("connection") or {}
        if conn.get("isp") and conn.get("asn"):
            facts.append(_fact("Connection", f"AS{conn['asn']} {conn['isp']}", "ipwho.is"))
        if d.get("type"):
            facts.append(_fact("IP type", d["type"], "ipwho.is"))
        return facts
    return []


async def _rdap_ip(client, value: str) -> list[dict]:
    d = await _get_json(client, f"https://rdap.org/ip/{value}")
    if isinstance(d, dict):
        facts = []
        if d.get("name"):
            facts.append(_fact("Netblock", d["name"], "rdap.org"))
        if d.get("country"):
            facts.append(_fact("Registry country", d["country"], "rdap.org"))
        return facts
    return []


async def _crtsh(client, value: str) -> list[dict]:
    d = await _get_json(client, f"https://crt.sh/?q={value}&output=json")
    facts = []
    if isinstance(d, list) and d:
        names: set[str] = set()
        for row in d:
            for n in (row.get("name_value") or "").splitlines():
                n = n.strip().lower()
                if n and "*" not in n:
                    names.add(n)
        facts.append(_fact("Certificates (crt.sh)", len(d), "crt.sh", f"https://crt.sh/?q={value}"))
        if names:
            sample = sorted(names)[:8]
            facts.append(_fact("Subdomains seen", f"{len(names)} (e.g. {', '.join(sample)})",
                               "crt.sh", f"https://crt.sh/?q={value}"))
    return facts


async def _rdap_domain(client, value: str) -> list[dict]:
    d = await _get_json(client, f"https://rdap.org/domain/{value}")
    facts = []
    if isinstance(d, dict):
        for ent in (d.get("entities") or []):
            roles = ent.get("roles") or []
            if "registrar" in roles:
                # vcard fn is buried in jCard; best-effort.
                vcard = (ent.get("vcardArray") or [None, []])[1]
                fn = next((x[3] for x in vcard if x and x[0] == "fn"), None)
                if fn:
                    facts.append(_fact("Registrar", fn, "rdap.org"))
                break
        for ev in (d.get("events") or []):
            if ev.get("eventAction") == "registration" and ev.get("eventDate"):
                facts.append(_fact("Registered", ev["eventDate"][:10], "rdap.org"))
            if ev.get("eventAction") == "expiration" and ev.get("eventDate"):
                facts.append(_fact("Expires", ev["eventDate"][:10], "rdap.org"))
    return facts


async def _doh(client, value: str) -> list[dict]:
    d = await _get_json(client, f"https://cloudflare-dns.com/dns-query?name={value}&type=A",
                        headers={"accept": "application/dns-json"})
    if isinstance(d, dict) and d.get("Answer"):
        ips = [a["data"] for a in d["Answer"] if a.get("type") == 1]
        if ips:
            return [_fact("A records", ", ".join(ips[:6]), "cloudflare-dns.com")]
    return []


async def _nvd(client, value: str) -> list[dict]:
    d = await _get_json(client, f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={value.upper()}")
    vulns = (d or {}).get("vulnerabilities") or []
    facts = []
    if vulns:
        cve = vulns[0].get("cve", {})
        descs = cve.get("descriptions") or []
        en = next((x["value"] for x in descs if x.get("lang") == "en"), None)
        if en:
            facts.append(_fact("Description", en[:400], "nvd.nist.gov",
                               f"https://nvd.nist.gov/vuln/detail/{value.upper()}"))
        metrics = cve.get("metrics") or {}
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if metrics.get(key):
                m = metrics[key][0].get("cvssData", {})
                facts.append(_fact("CVSS", f"{m.get('baseScore')} ({m.get('baseSeverity', m.get('baseScore'))})", "nvd.nist.gov"))
                break
        if cve.get("published"):
            facts.append(_fact("Published", cve["published"][:10], "nvd.nist.gov"))
    return facts


async def _circl_cve(client, value: str) -> list[dict]:
    d = await _get_json(client, f"https://cve.circl.lu/api/cve/{value.upper()}")
    facts = []
    if isinstance(d, dict) and d:
        if d.get("cvss") is not None:
            facts.append(_fact("CVSS (CIRCL)", d["cvss"], "cve.circl.lu"))
        refs = d.get("references") or []
        if refs:
            facts.append(_fact("References", len(refs), "cve.circl.lu"))
    return facts


async def _malwarebazaar(client, value: str) -> list[dict]:
    resp = await client.post("https://mb-api.abuse.ch/api/v1/", data={"query": "get_info", "hash": value})
    resp.raise_for_status()
    d = resp.json()
    facts = []
    if isinstance(d, dict) and d.get("query_status") == "ok" and d.get("data"):
        row = d["data"][0]
        if row.get("file_type"):
            facts.append(_fact("File type", row["file_type"], "bazaar.abuse.ch"))
        if row.get("signature"):
            facts.append(_fact("Malware family", row["signature"], "bazaar.abuse.ch"))
        if row.get("first_seen"):
            facts.append(_fact("First seen", row["first_seen"], "bazaar.abuse.ch"))
        facts.append(_fact("MalwareBazaar", "known sample", "bazaar.abuse.ch",
                           f"https://bazaar.abuse.ch/sample/{value}/"))
    return facts


async def _blockchair(client, value: str) -> list[dict]:
    chain = "ethereum" if value.lower().startswith("0x") else "bitcoin"
    d = await _get_json(client, f"https://api.blockchair.com/{chain}/dashboards/address/{value}")
    data = ((d or {}).get("data") or {}).get(value) or {}
    addr = data.get("address") or {}
    facts = []
    if addr:
        bal = addr.get("balance")
        if bal is not None:
            unit = "wei" if chain == "ethereum" else "sat"
            facts.append(_fact("Balance", f"{bal} {unit}", "blockchair.com",
                               f"https://blockchair.com/{chain}/address/{value}"))
        txc = addr.get("transaction_count") or addr.get("call_count")
        if txc is not None:
            facts.append(_fact("Transactions", txc, "blockchair.com"))
    return facts


async def _blockchain_info(client, value: str) -> list[dict]:
    # BTC legacy/bech32 only (skip eth 0x).
    if value.lower().startswith("0x"):
        return []
    d = await _get_json(client, f"https://blockchain.info/rawaddr/{value}?limit=0")
    facts = []
    if isinstance(d, dict) and d.get("n_tx") is not None:
        btc = (d.get("final_balance") or 0) / 1e8
        facts.append(_fact("BTC balance", f"{btc:.8f} BTC", "blockchain.info",
                           f"https://www.blockchain.com/explorer/addresses/btc/{value}"))
        facts.append(_fact("BTC tx count", d["n_tx"], "blockchain.info"))
    return facts


# ── registry ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Provider:
    name: str
    host: str
    kinds: tuple[str, ...]
    fetch: Callable[[object, str], Awaitable[list[dict]]]


PROVIDERS: list[Provider] = [
    Provider("ip-api", "ip-api.com", ("ip",), _ip_api),
    Provider("GreyNoise", "greynoise.io", ("ip",), _greynoise),
    Provider("ipwho.is", "ipwho.is", ("ip",), _ipwhois),
    Provider("RDAP (ip)", "rdap.org", ("ip",), _rdap_ip),
    Provider("crt.sh", "crt.sh", ("domain",), _crtsh),
    Provider("RDAP (domain)", "rdap.org", ("domain",), _rdap_domain),
    Provider("Cloudflare DoH", "cloudflare-dns.com", ("domain",), _doh),
    Provider("NVD", "nvd.nist.gov", ("cve",), _nvd),
    Provider("CIRCL cve-search", "cve.circl.lu", ("cve",), _circl_cve),
    Provider("MalwareBazaar", "bazaar.abuse.ch", ("hash",), _malwarebazaar),
    Provider("Blockchair", "blockchair.com", ("crypto",), _blockchair),
    Provider("blockchain.info", "blockchain.info", ("crypto",), _blockchain_info),
]

# Kinds with at least one provider — drives the /enrich + investigate "enrichable" flag.
ENRICHABLE_KINDS = {k for p in PROVIDERS for k in p.kinds}


# ── entity → consequence projection ─────────────────────────────────────────────
# Closes the loop: an enriched entity shouldn't dead-end at a fact list. Each
# investigatable kind maps to a consequence category, and the entity + its live facts
# are run through the SAME deterministic CPE (backend/feeds/synthesize) that maps real
# events — so the analyst sees "what could this entity cause" (sector impacts, severity,
# escalation prediction), explainable and grounded in the actual enrichment.
_KIND_CATEGORY = {"cve": "cyber", "hash": "cyber", "ip": "cyber",
                  "domain": "cyber", "crypto": "sanction"}
_BASE_IMPORTANCE = {"cve": 55, "hash": 60, "ip": 45, "domain": 45, "crypto": 50}


def _cvss_importance(facts: list[dict]) -> int | None:
    """A CVE's CVSS base score (0–10) → importance (0–100), grounding severity in the
    real vulnerability metric rather than a flat default."""
    for f in facts:
        if str(f.get("label", "")).startswith("CVSS"):
            m = re.match(r"\s*([\d.]+)", str(f.get("value", "")))
            if m:
                try:
                    return round(min(10.0, float(m.group(1))) * 10)
                except ValueError:
                    pass
    return None


def project_consequence(value: str, kind: str, facts: list[dict]) -> dict | None:
    """Entity + its live facts → a deterministic consequence projection (sector impacts +
    escalation prediction), via the same engine that maps events. Returns None for kinds
    without a defensible mapping, or when there are no facts to ground the projection."""
    category = _KIND_CATEGORY.get(kind)
    if not category or not facts:
        return None
    from backend.feeds import synthesize as S

    importance = _BASE_IMPORTANCE.get(kind, 45)
    if kind == "cve":
        cvss = _cvss_importance(facts)
        if cvss is not None:
            importance = cvss
    labels = {str(f.get("label", "")).lower() for f in facts}
    blob = " ".join(str(f.get("value", "")).lower() for f in facts)
    if kind == "hash" and "malware family" in labels:
        importance = min(100, importance + 15)        # a named family ⇒ live threat
    if kind == "ip" and ("malicious" in blob or "flags" in labels):
        importance = min(100, importance + 20)        # flagged proxy/hosting/known-bad

    signal = {
        "category": category,
        "importance": importance,
        "title": f"{kind.upper()} {value}",
        "summary": f"OSINT-enriched {kind} {value}: " + "; ".join(
            f"{f.get('label')}: {f.get('value')}" for f in facts[:3]),
        "geography": [],
        "source": "osint_enrich",
    }
    return {
        "category": category,
        "importance": importance,
        "severity": S.severity_from(importance),
        "map": S.synthesize(signal),
    }


def live_host_kinds() -> dict[str, set[str]]:
    """Single source of truth for which catalog hosts have a live enricher → used by
    osint_catalog to classify a tool as 'live'."""
    out: dict[str, set[str]] = {}
    for p in PROVIDERS:
        out.setdefault(p.host, set()).update(p.kinds)
    return out


# ── Redis cache (keeps us inside free rate limits; graceful when Redis is absent) ──
async def _cache_get(kind: str, value: str):
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        raw = await r.get(f"osint:enrich:{kind}:{value}")
        await r.aclose()
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001 — cache is best-effort
        logger.debug("enrich cache get failed: %s", exc)
        return None


async def _cache_set(kind: str, value: str, payload: dict) -> None:
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.set(f"osint:enrich:{kind}:{value}", json.dumps(payload), ex=_TTL.get(kind, 21600))
        await r.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.debug("enrich cache set failed: %s", exc)


async def enrich(value: str, kind: str) -> dict:
    """Live facts for `value` of `kind`, merged across every keyless provider for
    that kind. Cached in Redis. Always returns the standard envelope; `facts` is []
    when the kind isn't enrichable or every provider failed."""
    value = (value or "").strip()
    if not value or kind not in ENRICHABLE_KINDS:
        return {"value": value, "kind": kind, "facts": [], "sources": [],
                "consequence": None, "limited": False}

    cached = await _cache_get(kind, value)
    if cached is not None:
        cached["cached"] = True
        return cached

    import httpx

    facts: list[dict] = []
    providers = [p for p in PROVIDERS if kind in p.kinds]
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True,
                                     headers={"User-Agent": USER_AGENT}) as client:
            for p in providers:
                try:
                    facts.extend(await p.fetch(client, value))
                except Exception as exc:  # noqa: BLE001 — one provider failing never sinks the run
                    logger.debug("provider %s failed for %s/%s: %s", p.name, kind, value, exc)
    except Exception as exc:  # noqa: BLE001 — never raise to the route
        logger.warning("enrich failed (%s/%s): %s", kind, value, exc)
        facts = []

    result = {"value": value, "kind": kind, "facts": facts,
              "sources": sorted({f["source"] for f in facts}),
              "consequence": project_consequence(value, kind, facts), "limited": False}
    if facts:
        await _cache_set(kind, value, result)
    return result
