"""
iptv-org catalog — OPTIONAL keyless source of live HLS news channels.

https://github.com/iptv-org/iptv publishes M3U playlists of publicly available
streams by category. We consume the "news" playlist as extra channels for the
embedded player. iptv-org does NOT host streams; it aggregates links others
publish, many of which are unofficial restreams (copyright/geo/uptime risk).
So this is OPT-IN only (settings.live_news_use_iptv_org) and never the shipped
default — the curated official channels in live_news.py are ground truth.

parse_m3u is pure + testable (no I/O); fetch_iptv_news does the HTTP.
"""

import re

# #EXTINF:-1 tvg-id="X" tvg-logo="Y" group-title="News",Channel Name
_EXTINF = re.compile(
    r'#EXTINF:-?\d+\s*(?P<attrs>[^,]*),\s*(?P<name>.+)$'
)
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def _slug(text: str) -> str:
    return "iptv-" + re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:48]


def parse_m3u(text: str, limit: int = 60) -> list[dict]:
    """Extended-M3U playlist text → list of HLS channel dicts (NOT yet tier-gated).

    Only keeps entries whose stream URL looks like HLS (.m3u8) so the existing
    HlsPlayer can play them without a separate transport. Pure: no network.
    """
    out: list[dict] = []
    name: str | None = None
    attrs: dict[str, str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m = _EXTINF.match(line)
            if m:
                name = m.group("name").strip()
                attrs = dict(_ATTR.findall(m.group("attrs") or ""))
            else:
                name, attrs = None, {}
        elif not line.startswith("#") and name:
            url = line
            if ".m3u8" in url.lower():
                out.append({
                    "id": attrs.get("tvg-id") or _slug(name),
                    "name": name,
                    "lang": (attrs.get("tvg-language") or "").split(";")[0] or "",
                    "region": (attrs.get("tvg-country") or "").split(";")[0] or "",
                    "type": "hls",
                    "src": url,
                    "logo": attrs.get("tvg-logo") or "",
                    "official": False,  # aggregated; not a publisher-official feed
                })
            name, attrs = None, {}
            if len(out) >= limit:
                break
    return out


async def fetch_iptv_news(url: str, limit: int = 60) -> list[dict]:
    """Fetch the iptv-org news playlist → HLS channel dicts. Best-effort (returns [])."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return parse_m3u(resp.text, limit=limit)
    except Exception:  # noqa: BLE001 — optional source must never break the route
        return []
