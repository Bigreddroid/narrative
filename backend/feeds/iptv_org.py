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


def _is_hls_url(url: str) -> bool:
    """True only for http(s) URLs whose path ends in .m3u8.

    Hardening: the loose `".m3u8" in url` check would pass hostile values like
    `javascript:...//.m3u8` or `data:text/html,...m3u8`. Those don't execute in a
    <video> src, but we reject them anyway (defense-in-depth) — only real http(s)
    HLS manifests reach the player.
    """
    low = (url or "").strip().lower()
    if not (low.startswith("http://") or low.startswith("https://")):
        return False
    path = low.split("?", 1)[0].split("#", 1)[0]
    return path.endswith(".m3u8")


def parse_m3u(text: str, limit: int = 60) -> list[dict]:
    """Extended-M3U playlist text → list of HLS channel dicts (NOT yet tier-gated).

    Only keeps entries whose stream URL looks like HLS (.m3u8) so the existing
    HlsPlayer can play them without a separate transport. Pure: no network.
    """
    out: list[dict] = []
    name: str | None = None
    attrs: dict[str, str] = {}
    for idx, raw in enumerate((text or "").splitlines()):
        if idx >= 50_000:  # bound work on a hostile/huge playlist
            break
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
            if _is_hls_url(url):
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


_MAX_BYTES = 2_000_000  # cap the download so a hostile/huge playlist can't OOM us


async def fetch_iptv_news(url: str, limit: int = 60) -> list[dict]:
    """Fetch the iptv-org news playlist → HLS channel dicts. Best-effort (returns []).

    Streams and stops at _MAX_BYTES so an oversized or malicious playlist can't
    exhaust memory; only http(s) is fetched (the URL is trusted operator config).
    """
    if not (url or "").lower().startswith(("http://", "https://")):
        return []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= _MAX_BYTES:
                        break
        text = b"".join(chunks).decode("utf-8", "replace")
        return parse_m3u(text, limit=limit)
    except Exception:  # noqa: BLE001 — optional source must never break the route
        return []
