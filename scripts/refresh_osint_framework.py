#!/usr/bin/env python3
"""Refresh the vendored OSINT Framework catalog.

Fetches the upstream OSINT Framework tree (lockfale/OSINT-Framework `public/arf.json`,
~1100 tools across ~30 categories), CURATES it down to what The Narrative needs, and
writes the canonical snapshot to ``backend/data/osint_framework.json``.

We vendor a snapshot (rather than fetching live) so the in-app OSINT investigator is
$0, offline-safe and versioned — the same stance as the curated live-news channels.
Re-run this script to pull a fresh upstream copy.

Curation ("remodel / delete / edit"):
  * drop dead entries: ``deprecated`` true, or ``status`` in {down, defunct}.
  * keep only the fields the UI uses; flatten the tree to a flat tool list tagged
    with its top-level category.
  * derive ``entityKinds`` from each tool's free-text ``input`` field so the UI can
    filter tools by the kind of thing you're investigating.
  * attach a hand-authored ``templates`` table of reliable, URL-templatable lookups
    per entity kind (the upstream ``editUrl`` flag marks a tool as manually-editable
    but does not say where the value goes, so the investigate templates are curated).

Stdlib only (urllib) so it runs anywhere without installing deps.

Usage:  python scripts/refresh_osint_framework.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ARF_URL = "https://raw.githubusercontent.com/lockfale/OSINT-Framework/master/public/arf.json"
OUT_PATH = Path(__file__).resolve().parent.parent / "backend" / "data" / "osint_framework.json"

# Tools whose upstream status is one of these (or deprecated) are dropped.
DEAD_STATUS = {"down", "defunct"}

# Map free-text `input` descriptions → canonical entity kinds the investigator
# understands. First matching keyword wins; a tool can match several kinds.
KIND_KEYWORDS: list[tuple[str, str]] = [
    ("username", "username"),
    ("email", "email"),
    ("ip address", "ip"),
    ("ip or", "ip"),
    ("mac address", "ip"),
    ("domain", "domain"),
    ("url", "domain"),
    ("website", "domain"),
    ("hostname", "domain"),
    ("phone", "phone"),
    ("image", "image"),
    ("photo", "image"),
    ("coordinate", "location"),
    ("latitude", "location"),
    ("location", "location"),
    ("address", "location"),
    ("geo", "location"),
    ("map", "location"),
    ("person", "name"),
    ("name", "name"),
    ("company", "name"),
    ("entity", "name"),
    ("organization", "name"),
]


def _entity_kinds(input_text: str | None) -> list[str]:
    t = (input_text or "").lower()
    if not t:
        return []
    kinds: list[str] = []
    for kw, kind in KIND_KEYWORDS:
        if kw in t and kind not in kinds:
            kinds.append(kind)
    return kinds


def _slug(category: str, name: str) -> str:
    raw = f"{category}-{name}".lower()
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")[:80]


def _curate(root: dict) -> tuple[list[dict], list[str]]:
    """Flatten the upstream tree → a flat, curated tool list + the category list."""
    tools: list[dict] = []
    categories: list[str] = []
    seen_ids: set[str] = set()

    def walk(node: dict, category: str, subpath: list[str]) -> None:
        if node.get("type") == "url":
            if node.get("deprecated") or (node.get("status") or "").lower() in DEAD_STATUS:
                return
            name = (node.get("name") or "").strip()
            url = (node.get("url") or "").strip()
            if not name or not url:
                return
            tid = _slug(category, name)
            # de-dupe slug collisions (some names repeat across sub-folders)
            base, n = tid, 2
            while tid in seen_ids:
                tid = f"{base}-{n}"
                n += 1
            seen_ids.add(tid)
            tools.append({
                "id": tid,
                "name": name,
                "category": category,
                # subfolder breadcrumb for the hierarchical tree UI; "" = tool sits
                # directly under the top-level category.
                "subcategory": subpath[0] if subpath else "",
                "path": [category, *subpath],
                "url": url,
                "description": (node.get("description") or "").strip(),
                "pricing": (node.get("pricing") or "unknown").strip().lower(),
                "opsec": (node.get("opsec") or "unknown").strip().lower(),
                "bestFor": (node.get("bestFor") or "").strip(),
                "input": (node.get("input") or "").strip(),
                "output": (node.get("output") or "").strip(),
                "entityKinds": _entity_kinds(node.get("input")),
                "localInstall": bool(node.get("localInstall")),
                "registration": bool(node.get("registration")),
                "api": bool(node.get("api")),
            })
            return
        # folder node: descend, extending the breadcrumb with each sub-folder's name.
        for child in node.get("children") or []:
            if child.get("type") == "url":
                walk(child, category, subpath)
            else:
                cname = (child.get("name") or "").strip()
                walk(child, category, [*subpath, cname] if cname else subpath)

    for top in root.get("children") or []:
        cat = (top.get("name") or "").strip()
        if not cat:
            continue
        categories.append(cat)
        walk(top, cat, [])

    return tools, categories


# ── Curated investigate templates ────────────────────────────────────────────
# Reliable, well-known URL patterns with a `{value}` placeholder. The investigate
# endpoint substitutes a URL-encoded entity value. Kept intentionally small and
# stable — these are the high-signal pivots an analyst actually uses.
TEMPLATES: dict[str, list[dict]] = {
    "username": [
        {"name": "WhatsMyName", "url": "https://whatsmyname.app/", "note": "manual: enter username"},
        {"name": "GitHub", "url": "https://github.com/{value}"},
        {"name": "X / Twitter", "url": "https://twitter.com/{value}"},
        {"name": "Instagram", "url": "https://www.instagram.com/{value}/"},
        {"name": "Reddit", "url": "https://www.reddit.com/user/{value}"},
        {"name": "Google (exact)", "url": "https://www.google.com/search?q=%22{value}%22"},
    ],
    "domain": [
        {"name": "Google Dork (site:)", "url": "https://www.google.com/search?q=site:{value}"},
        {"name": "crt.sh certs", "url": "https://crt.sh/?q={value}"},
        {"name": "VirusTotal", "url": "https://www.virustotal.com/gui/domain/{value}"},
        {"name": "urlscan.io", "url": "https://urlscan.io/domain/{value}"},
        {"name": "Shodan", "url": "https://www.shodan.io/search?query={value}"},
        {"name": "Wayback Machine", "url": "https://web.archive.org/web/*/{value}"},
        {"name": "Whois", "url": "https://www.whois.com/whois/{value}"},
        # Cyber Threat Intelligence pivots (keyless):
        {"name": "URLhaus", "url": "https://urlhaus.abuse.ch/browse.php?search={value}"},
        {"name": "ThreatFox", "url": "https://threatfox.abuse.ch/browse.php?search=ioc%3A{value}"},
        {"name": "AlienVault OTX", "url": "https://otx.alienvault.com/indicator/domain/{value}"},
        {"name": "Pulsedive", "url": "https://pulsedive.com/indicator/?ioc={value}"},
    ],
    "ip": [
        {"name": "VirusTotal", "url": "https://www.virustotal.com/gui/ip-address/{value}"},
        {"name": "Shodan", "url": "https://www.shodan.io/host/{value}"},
        {"name": "AbuseIPDB", "url": "https://www.abuseipdb.com/check/{value}"},
        {"name": "GreyNoise", "url": "https://viz.greynoise.io/ip/{value}"},
        {"name": "Censys", "url": "https://search.censys.io/hosts/{value}"},
        {"name": "ipinfo.io", "url": "https://ipinfo.io/{value}"},
        # Cyber Threat Intelligence pivots (keyless):
        {"name": "AlienVault OTX", "url": "https://otx.alienvault.com/indicator/ip/{value}"},
        {"name": "ThreatFox", "url": "https://threatfox.abuse.ch/browse.php?search=ioc%3A{value}"},
        {"name": "Pulsedive", "url": "https://pulsedive.com/indicator/?ioc={value}"},
    ],
    "email": [
        {"name": "EmailRep", "url": "https://emailrep.io/{value}"},
        {"name": "IntelX", "url": "https://intelx.io/?s={value}"},
        {"name": "Google (exact)", "url": "https://www.google.com/search?q=%22{value}%22"},
        {"name": "Have I Been Pwned", "url": "https://haveibeenpwned.com/", "note": "manual: enter email"},
    ],
    "name": [
        {"name": "Google (exact)", "url": "https://www.google.com/search?q=%22{value}%22"},
        {"name": "LinkedIn", "url": "https://www.linkedin.com/search/results/all/?keywords={value}"},
        {"name": "OpenCorporates", "url": "https://opencorporates.com/companies?q={value}"},
        {"name": "OCCRP Aleph", "url": "https://aleph.occrp.org/search/?q={value}"},
        {"name": "IntelX", "url": "https://intelx.io/?s={value}"},
        {"name": "Ahmia (dark web)", "url": "https://ahmia.fi/search/?q={value}"},
    ],
    "location": [
        {"name": "Google Maps", "url": "https://www.google.com/maps/search/{value}"},
        {"name": "OpenStreetMap", "url": "https://www.openstreetmap.org/search?query={value}"},
        {"name": "Bing Maps", "url": "https://www.bing.com/maps?q={value}"},
        {"name": "Wikimapia", "url": "https://wikimapia.org/#search={value}"},
    ],
    "phone": [
        {"name": "Google (exact)", "url": "https://www.google.com/search?q=%22{value}%22"},
        {"name": "NumLookup", "url": "https://www.numlookup.com/results?phone={value}"},
    ],
    "username": [
        {"name": "WhatsMyName", "url": "https://whatsmyname.app/", "note": "manual: enter username"},
        {"name": "GitHub", "url": "https://github.com/{value}"},
        {"name": "X / Twitter", "url": "https://twitter.com/{value}"},
        {"name": "Instagram", "url": "https://www.instagram.com/{value}/"},
        {"name": "Reddit", "url": "https://www.reddit.com/user/{value}"},
        {"name": "Google (exact)", "url": "https://www.google.com/search?q=%22{value}%22"},
        {"name": "IntelX", "url": "https://intelx.io/?s={value}"},
        {"name": "Ahmia (dark web)", "url": "https://ahmia.fi/search/?q={value}"},
    ],
    # ── Blockchain & Cryptocurrency: wallet address / tx hash → explorers ────────
    "crypto": [
        {"name": "Blockchair (multi-chain)", "url": "https://blockchair.com/search?q={value}"},
        {"name": "Etherscan", "url": "https://etherscan.io/address/{value}"},
        {"name": "Blockchain.com", "url": "https://www.blockchain.com/explorer/search?search={value}"},
        {"name": "BscScan", "url": "https://bscscan.com/address/{value}"},
        {"name": "Tronscan", "url": "https://tronscan.org/#/address/{value}"},
        {"name": "ChainAbuse", "url": "https://www.chainabuse.com/address/{value}"},
        {"name": "WalletExplorer", "url": "https://www.walletexplorer.com/address/{value}"},
    ],
    # ── Malicious File Analysis: file hash → sandboxes / malware repos ───────────
    "hash": [
        {"name": "VirusTotal", "url": "https://www.virustotal.com/gui/file/{value}"},
        {"name": "MalwareBazaar", "url": "https://bazaar.abuse.ch/browse.php?search={value}"},
        {"name": "Hybrid Analysis", "url": "https://www.hybrid-analysis.com/search?query={value}"},
        {"name": "Triage (tria.ge)", "url": "https://tria.ge/s?q={value}"},
        {"name": "ThreatFox", "url": "https://threatfox.abuse.ch/browse.php?search=ioc%3A{value}"},
        {"name": "ANY.RUN", "url": "https://app.any.run/submissions", "note": "manual: search hash"},
    ],
    # ── Cyber Threat Intelligence: CVE id → vuln databases ──────────────────────
    "cve": [
        {"name": "NVD", "url": "https://nvd.nist.gov/vuln/detail/{value}"},
        {"name": "CVE.org", "url": "https://www.cve.org/CVERecord?id={value}"},
        {"name": "MITRE", "url": "https://cve.mitre.org/cgi-bin/cvename.cgi?name={value}"},
        {"name": "Exploit-DB", "url": "https://www.exploit-db.com/search?cve={value}"},
        {"name": "GitHub Advisories", "url": "https://github.com/advisories?query={value}"},
        {"name": "CISA KEV", "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog", "note": "manual: search id"},
    ],
    # ── Transportation: flight/tail/IMO/MMSI → live trackers ────────────────────
    "vehicle": [
        {"name": "FlightRadar24", "url": "https://www.flightradar24.com/data/aircraft/{value}"},
        {"name": "ADS-B Exchange", "url": "https://globe.adsbexchange.com/?reg={value}"},
        {"name": "MarineTraffic", "url": "https://www.marinetraffic.com/en/ais/index/search/all?keyword={value}"},
        {"name": "VesselFinder", "url": "https://www.vesselfinder.com/vessels?name={value}"},
        {"name": "OpenSky", "url": "https://opensky-network.org/aircraft-profile?icao24={value}"},
    ],
    # ── Disinformation & Media Verification: image URL / claim → reverse-image + fact-check ─
    "media": [
        {"name": "Google Lens", "url": "https://lens.google.com/uploadbyurl?url={value}"},
        {"name": "Yandex Images", "url": "https://yandex.com/images/search?rpt=imageview&url={value}"},
        {"name": "TinEye", "url": "https://tineye.com/search?url={value}"},
        {"name": "Bing Visual", "url": "https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{value}"},
        {"name": "Google Fact Check", "url": "https://toolbox.google.com/factcheck/explorer/search/{value}"},
        {"name": "InVID", "url": "https://www.invid-project.eu/tools-and-services/invid-verification-plugin/", "note": "manual: verify video/image"},
    ],
}


def main() -> int:
    print(f"Fetching {ARF_URL} ...", file=sys.stderr)
    req = urllib.request.Request(ARF_URL, headers={"User-Agent": "the-narrative-osint-refresh/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            root = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — refresh script, surface and abort
        print(f"ERROR: could not fetch upstream arf.json: {e}", file=sys.stderr)
        print("Aborting — existing snapshot left untouched.", file=sys.stderr)
        return 1

    tools, categories = _curate(root)
    if len(tools) < 200:  # sanity guard against a truncated/garbage upstream
        print(f"ERROR: only {len(tools)} tools after curation — refusing to overwrite.", file=sys.stderr)
        return 1

    snapshot = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": ARF_URL,
        "license": "OSINT Framework data © lockfale/OSINT-Framework (MIT), curated for The Narrative.",
        "categories": categories,
        "counts": {"tools": len(tools), "categories": len(categories)},
        "templates": TEMPLATES,
        "tools": tools,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")

    kinds = sorted({k for t in tools for k in t["entityKinds"]})
    print(f"Wrote {OUT_PATH}", file=sys.stderr)
    print(f"  {len(tools)} tools across {len(categories)} categories", file=sys.stderr)
    print(f"  entity kinds present: {kinds}", file=sys.stderr)
    print(f"  template kinds: {sorted(TEMPLATES)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
