"""Server-side OSINT entity extraction.

Scans free text (event title + summary + consequence-map prose) for investigatable
entities — IPs, CVEs, crypto addresses, file hashes, vessel IDs — so an event can
surface "investigate this" pivots without the client re-implementing the regexes.

Mirrors web/src/lib/osintEntities.js and the backend detect_entity_kind() patterns;
kept deliberately conservative (these feed a manual pivot, so precision > recall).
Order matters: the most specific kind claims a value first.

Run:  python -m backend.services.osint_extract_test
"""

from __future__ import annotations

import re
from typing import Callable

# (kind, compiled regex, optional validator). First/most-specific match wins per value.
_PATTERNS: list[tuple[str, re.Pattern, "Callable | None"]] = [
    ("cve", re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.I), None),
    ("vehicle", re.compile(r"\bIMO\s?\d{7}\b|\bMMSI\s?\d{9}\b", re.I), None),
    ("ip", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), None),
    ("crypto", re.compile(r"\b0x[0-9a-fA-F]{40}\b|\b0x[0-9a-fA-F]{64}\b|\bbc1[a-z0-9]{20,87}\b|\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b"), None),
    ("hash", re.compile(r"\b[0-9a-fA-F]{64}\b|\b[0-9a-fA-F]{40}\b|\b[0-9a-fA-F]{32}\b"), None),
]


def _valid_ip(v: str) -> bool:
    parts = v.split(".")
    if len(parts) != 4 or v == "0.0.0.0":
        return False
    for p in parts:
        if p == "" or not p.isdigit():
            return False
        n = int(p)
        if n < 0 or n > 255 or str(n) != p:
            return False
    return True


_VALIDATORS: dict[str, Callable[[str], bool]] = {"ip": _valid_ip}


def extract_entities(text: str, cap: int = 8) -> list[dict]:
    """Best-effort investigatable entities in `text` → [{value, kind}], de-duped,
    most-specific-kind-wins, capped. Empty input ⇒ []."""
    blob = str(text or "")
    out: list[dict] = []
    seen: set[str] = set()
    for kind, rx, _ in _PATTERNS:
        for m in rx.finditer(blob):
            value = m.group(0)
            validator = _VALIDATORS.get(kind)
            if validator and not validator(value):
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"value": value, "kind": kind})
            if len(out) >= cap:
                return out
    return out


def _map_text(consequence_map) -> str:
    """Flatten the prose fields of a consequence map into one searchable blob."""
    if not isinstance(consequence_map, dict):
        return ""
    parts: list[str] = []
    for key in ("consensus_summary", "prediction_reasoning"):
        v = consequence_map.get(key)
        if isinstance(v, str):
            parts.append(v)
    for key in ("direct_impact", "indirect_impact", "disputed_points", "consequence_chain"):
        v = consequence_map.get(key)
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
        elif isinstance(v, str):
            parts.append(v)
    return "\n".join(parts)


def entities_for_event(title: str | None, summary: str | None,
                       consequence_map=None, cap: int = 8) -> list[dict]:
    """Extract across an event's title, summary and (optionally) its consequence-map
    prose — richer than a client-side title+summary scan."""
    blob = "\n".join(x for x in (title, summary, _map_text(consequence_map)) if x)
    return extract_entities(blob, cap=cap)
