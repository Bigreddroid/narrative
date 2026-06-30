"""
OSINT Framework — in-app catalog of open-source-intelligence tools + an
entity-aware investigator that templates a value (username/domain/IP/…) into the
relevant lookups.

Data is a vendored, curated snapshot of the OSINT Framework
(`backend/data/osint_framework.json`, produced by
`scripts/refresh_osint_framework.py`) — keyless, $0, offline-safe, the same stance
as the curated live-news channels.

Tier-aware: free users get a small taster of the catalog; paid+ get the full
catalog and the full investigate template set. The data is a static JSON manifest
the frontend renders — no paid calls, no DB.
"""

import ipaddress
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter

from backend.api.dependencies import UserDep
from backend.services import osint_catalog, osint_enrich

router = APIRouter(prefix="/osint", tags=["osint"])

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "osint_framework.json"

# The full catalog (all 33 categories / 1,098 tools) is open to every tier; only the
# entity-aware *investigate* templating stays a paid feature.
_VALID_KINDS = {
    "username", "domain", "ip", "email", "name", "location", "phone", "image",
    # entity kinds added for per-category investigators (Blockchain, Malware,
    # Cyber Threat Intel, Transportation, Disinformation & Media Verification):
    "crypto", "hash", "cve", "vehicle", "media",
}


@lru_cache(maxsize=1)
def _load() -> dict:
    """Load + cache the vendored snapshot. Missing/corrupt file ⇒ empty catalog
    (the UI then shows an honest empty state instead of erroring)."""
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"categories": [], "counts": {"tools": 0, "categories": 0}, "templates": {}, "tools": []}


def detect_entity_kind(value: str) -> str:
    """Best-effort classification of a raw entity value → a template kind.
    Used when the caller doesn't pass an explicit ?kind=."""
    v = (value or "").strip()
    if not v:
        return "name"
    if "@" in v and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
        return "email"
    try:
        ipaddress.ip_address(v)
        return "ip"
    except ValueError:
        pass
    if re.fullmatch(r"-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+", v):
        return "location"
    if re.fullmatch(r"CVE-\d{4}-\d{4,}", v, re.I):
        return "cve"
    # crypto: ETH address/tx (0x + 40/64 hex), BTC bech32 (bc1…), BTC legacy (1/3…).
    if (re.fullmatch(r"0x(?:[0-9a-f]{40}|[0-9a-f]{64})", v, re.I)
            or re.fullmatch(r"bc1[a-z0-9]{20,87}", v, re.I)
            or re.fullmatch(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}", v)):
        return "crypto"
    # file hash: md5(32) / sha1(40) / sha256(64) hex — checked before username so a
    # bare hex blob doesn't read as a handle.
    if re.fullmatch(r"[0-9a-f]{32}|[0-9a-f]{40}|[0-9a-f]{64}", v, re.I):
        return "hash"
    if re.fullmatch(r"IMO\s?\d{7}", v, re.I):
        return "vehicle"
    if " " not in v and re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", v, re.I):
        return "domain"
    if " " not in v and re.fullmatch(r"[a-z0-9_.-]+", v, re.I):
        return "username"
    return "name"


def _templated(value: str, kind: str) -> list[dict]:
    """Curated investigate templates for `kind`, with `{value}` substituted
    (URL-encoded). Templates carrying a `note` (manual-entry tools) are returned
    with their base URL unchanged."""
    templates = _load().get("templates", {})
    encoded = quote(value, safe="")
    out: list[dict] = []
    for t in templates.get(kind, []):
        url = t["url"]
        out.append({
            "name": t["name"],
            "url": url.replace("{value}", encoded) if "{value}" in url else url,
            "note": t.get("note"),
            "templated": "{value}" in url,
        })
    return out


@router.get("/framework")
async def framework(user: UserDep) -> dict:
    """The curated OSINT tool catalog — the full set (all 33 categories / 1,098
    tools) is open to every tier. Only the entity-aware *investigate* templating
    stays a paid feature, so the free tier gets the whole catalog but an empty
    `templates` set.

    Every tool is badged with a `capability` (live | pivot | launch) so the UI can
    show, honestly, what each tool can actually do in-app; `capabilities` carries
    the per-tier totals.
    """
    data = _load()
    is_free = user.tier == "free"
    raw_tools = data.get("tools", [])
    return {
        "tier": user.tier,
        "categories": data.get("categories", []),
        "counts": data.get("counts", {}),
        "capabilities": osint_catalog.capability_counts(raw_tools),
        "templates": {} if is_free else data.get("templates", {}),
        "tools": [osint_catalog.augment(t) for t in raw_tools],
        "limited": False,
    }


def _curated_capability(item: dict, kind: str) -> dict:
    """Tag a curated template item with a capability tier so it merges cleanly with
    the catalog-derived tools. Native templated lookups are pivots; manual-entry
    tools (those carrying a `note`) are launches; hosts with a live enricher win."""
    host = osint_catalog.host_of(item.get("url") or "")
    bare = host[4:] if host.startswith("www.") else host
    live = (osint_catalog.LIVE_HOSTS.get(host) or osint_catalog.LIVE_HOSTS.get(bare) or set())
    native = bool(item.get("templated"))
    cap = "live" if kind in live else ("pivot" if native else "launch")
    return {**item, "capability": cap, "native": native, "source": "curated",
            "category": None, "pricing": None, "opsec": None, "registration": False}


@router.get("/investigate")
async def investigate(user: UserDep, value: str, kind: str | None = None) -> dict:
    """Entity-aware pivot: every in-catalog tool that accepts `value`, resolved to a
    one-click action. Combines the curated high-signal lookups with the full catalog
    (native search where we have a pattern, else a site-scoped pivot, else launch).
    Each tool is tagged with a `capability` (live | pivot | launch). `kind` is
    auto-detected when omitted. Paid feature; free tier gets an empty set (gated)."""
    value = (value or "").strip()
    if user.tier == "free" or not value:
        return {"value": value, "kind": kind, "tools": [], "limited": user.tier == "free"}

    resolved = (kind or "").strip().lower()
    if resolved not in _VALID_KINDS:
        resolved = detect_entity_kind(value)

    # Curated high-signal pivots first, then the rest of the catalog for this kind.
    curated = [_curated_capability(t, resolved) for t in _templated(value, resolved)]
    seen = {(t["name"], t["url"]) for t in curated}
    catalog = [t for t in osint_catalog.catalog_investigate(value, resolved, _load().get("tools", []))
               if (t["name"], t["url"]) not in seen]

    tools = curated + catalog
    counts = {"live": 0, "pivot": 0, "launch": 0}
    for t in tools:
        counts[t["capability"]] = counts.get(t["capability"], 0) + 1
    return {"value": value, "kind": resolved, "tools": tools, "capabilities": counts,
            "enrichable": resolved in osint_enrich.ENRICHABLE_KINDS, "limited": False}


@router.get("/enrich")
async def enrich(user: UserDep, value: str, kind: str | None = None) -> dict:
    """Tier 1 live enrichment: real facts fetched server-side from keyless APIs
    (ip/domain/cve/hash/crypto). Paid feature, gated exactly like investigate; free
    tier and non-enrichable kinds get an empty `facts` set."""
    value = (value or "").strip()
    if user.tier == "free" or not value:
        return {"value": value, "kind": kind, "facts": [], "sources": [],
                "limited": user.tier == "free"}

    resolved = (kind or "").strip().lower()
    if resolved not in _VALID_KINDS:
        resolved = detect_entity_kind(value)

    return await osint_enrich.enrich(value, resolved)
