"""
Sanctions — OpenSanctions consolidated targets. Free dataset (FollowTheMoney
entity export). Used as a reference layer mapping sanctioned entities → countries
and topics, feeding Banking/Trade exposure.
  https://data.opensanctions.org/datasets/latest/default/targets.simple.json (one entity per line)

Pure parser (parse_targets) → normalized records. NON-GEO and entity-level (not an
event), so this is a reference feed, not a hazard Signal — wiring it into a
sanctions-exposure layer is the follow-up step.
"""

SANCTION_TOPICS = {"sanction", "sanction.linked", "crime", "crime.fin", "poi"}


def parse_targets(entities: list[dict], limit: int = 500) -> list[dict]:
    """OpenSanctions simple-entity records → normalized sanction records.

    Each input entity looks like:
      {"id","schema","caption","properties":{"country":[...],"topics":[...]},"datasets":[...]}
    """
    out = []
    for e in (entities or [])[:limit]:
        eid = e.get("id")
        caption = e.get("caption")
        if not eid or not caption:
            continue
        props = e.get("properties") or {}
        topics = [t for t in (props.get("topics") or [])]
        countries = [c for c in (props.get("country") or [])]
        is_sanctioned = bool(set(topics) & SANCTION_TOPICS) or "sanction" in (e.get("datasets") or [])
        out.append({
            "external_id": f"opensanctions-{eid}",
            "source": "opensanctions",
            "name": caption,
            "schema": e.get("schema"),
            "countries": countries[:5],
            "topics": topics,
            "sanctioned": is_sanctioned,
            "datasets": e.get("datasets") or [],
        })
    return out


async def fetch_targets() -> list[dict]:
    import httpx  # lazy — keeps parse_targets importable without the dep
    url = "https://data.opensanctions.org/datasets/latest/default/targets.simple.json"
    rows = []
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        # newline-delimited JSON: one entity per line
        for line in resp.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                import json
                rows.append(json.loads(line))
            except ValueError:
                continue
    return parse_targets(rows)
