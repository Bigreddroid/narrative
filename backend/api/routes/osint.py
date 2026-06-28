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

router = APIRouter(prefix="/osint", tags=["osint"])

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "osint_framework.json"

# Free tier sees a small taster of the catalog (the full set is a paid feature).
_FREE_TOOL_CAP = 40
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
    """The curated OSINT tool catalog.

    free → a capped taster of free-pricing tools; paid+ → the full catalog plus
    the full investigate template set.
    """
    data = _load()
    tools = data.get("tools", [])
    is_free = user.tier == "free"

    if is_free:
        taster = [t for t in tools if t.get("pricing") == "free"][:_FREE_TOOL_CAP]
        cats = sorted({t["category"] for t in taster})
        return {
            "tier": user.tier,
            "categories": cats,
            "counts": {"tools": len(taster), "categories": len(cats)},
            "templates": {},  # investigate templating is a paid feature
            "tools": taster,
            "limited": True,
            "total_available": len(tools),
        }

    return {
        "tier": user.tier,
        "categories": data.get("categories", []),
        "counts": data.get("counts", {}),
        "templates": data.get("templates", {}),
        "tools": tools,
        "limited": False,
    }


@router.get("/investigate")
async def investigate(user: UserDep, value: str, kind: str | None = None) -> dict:
    """Entity-aware pivot: return the curated lookups for `value`, with the value
    templated in. `kind` is auto-detected when omitted. Paid feature; free tier
    gets an empty set (gated)."""
    value = (value or "").strip()
    if user.tier == "free" or not value:
        return {"value": value, "kind": kind, "tools": [], "limited": user.tier == "free"}

    resolved = (kind or "").strip().lower()
    if resolved not in _VALID_KINDS:
        resolved = detect_entity_kind(value)

    return {"value": value, "kind": resolved, "tools": _templated(value, resolved), "limited": False}
