"""
Launch Library 2 (The Space Devs) — free, NO key. Upcoming orbital launches with
pad coordinates. Each becomes a 'space'-category signal at its launch pad.
  https://ll.thespacedevs.com/2.2.0/launch/upcoming/

Pure parser (parse_launches) → Signal dicts. Pad lat/lng arrive as strings.
"""

FEED_URL = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/"
LAUNCH_IMPORTANCE = 55  # launches are scheduled, moderate-importance space events. Tunable.


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_launches(data: dict) -> list[dict]:
    """Launch Library 'results' → list of Signal dicts (category 'space')."""
    out = []
    for r in (data or {}).get("results", []):
        pad = r.get("pad") or {}
        lat, lng = _f(pad.get("latitude")), _f(pad.get("longitude"))
        if lat is None or lng is None:
            continue
        loc = (pad.get("location") or {}).get("name") or pad.get("name") or "launch site"
        provider = (r.get("launch_service_provider") or {}).get("name") or "Unknown provider"
        name = r.get("name") or "Orbital launch"
        net = r.get("net") or ""
        out.append({
            "external_id": f"ll2-{r.get('id')}",
            "source": "launchlibrary",
            "title": f"Launch — {name}",
            "summary": f"{provider}: {name} from {loc}" + (f", NET {net}." if net else "."),
            "category": "space",
            "lat": lat,
            "lng": lng,
            "importance": LAUNCH_IMPORTANCE,
            "status": "developing",
            "geography": [loc],
            "ts": None,
        })
    return out


async def fetch_launches() -> list[dict]:
    import httpx  # lazy — keeps parse_launches importable without the dep
    params = {"limit": 20, "mode": "normal"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(FEED_URL, params=params)
        resp.raise_for_status()
        return parse_launches(resp.json())
