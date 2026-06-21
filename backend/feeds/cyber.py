"""
CISA KEV — Known Exploited Vulnerabilities. Free, NO key. Authoritative feed of
vulnerabilities under active exploitation (critical-infrastructure cyber signal).
  https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

Pure parser (parse_kev) → Signal dicts, category 'cyber'. These are NON-GEO
(lat/lng=None), so they need a non-geo ingest path — the geo-gated
hazard_ingest_worker would drop them. Wiring that path is the follow-up step.
"""

BASE_IMPORTANCE = 60
RANSOMWARE_BONUS = 20  # actively used in ransomware campaigns ⇒ higher urgency


def parse_kev(data: dict, limit: int = 100) -> list[dict]:
    """CISA KEV catalog JSON → list of Signal dicts (most recent first, capped)."""
    vulns = (data or {}).get("vulnerabilities") or []
    # dateAdded is ISO 'YYYY-MM-DD' → lexicographic sort is chronological.
    vulns = sorted(vulns, key=lambda v: v.get("dateAdded") or "", reverse=True)[:limit]
    out = []
    for v in vulns:
        cve = v.get("cveID")
        if not cve:
            continue
        ransom = (v.get("knownRansomwareCampaignUse") or "").strip().lower() == "known"
        imp = BASE_IMPORTANCE + (RANSOMWARE_BONUS if ransom else 0)
        vendor = v.get("vendorProject") or ""
        product = v.get("product") or ""
        name = v.get("vulnerabilityName") or cve
        out.append({
            "external_id": cve,
            "source": "cisa",
            "title": f"{cve} — {vendor} {product}".strip(),
            "summary": v.get("shortDescription") or name,
            "category": "cyber",
            "lat": None,
            "lng": None,
            "importance": imp,
            "status": "escalating" if ransom else "developing",
            "geography": [],  # cyber is non-geo — keep vendor out of exposure regions
            "ts": None,
        })
    return out


async def fetch_kev() -> list[dict]:
    import httpx  # lazy — keeps parse_kev importable without the dep
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return parse_kev(resp.json())
