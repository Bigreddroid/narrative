"""
Live-news streams — curated, embeddable 24/7 news channels for the in-app player.

Default = OFFICIAL broadcaster feeds only (publisher-published HLS or official
YouTube-live embeds). These are REAL live streams, never simulated. iptv-org is
an optional, opt-in expansion (settings.live_news_use_iptv_org) of additional
keyless HLS channels — off by default because it aggregates unofficial restreams.

Tier-aware: free users get a small taster; paid+ get the full curated set (and
the iptv-org expansion when enabled). $0 to serve — just a JSON manifest the
frontend HlsPlayer / YouTube iframe consumes.
"""

from fastapi import APIRouter

from backend.api.dependencies import UserDep
from backend.config import get_settings

router = APIRouter(prefix="/live-news", tags=["live-news"])

# Official, broadcaster-published 24/7 streams. `type`: "hls" (HlsPlayer) or
# "youtube" (official live iframe via channel id). All free-to-embed.
# Ordered most-reliable first: the frontend selects channels[0] by default, so the
# default must be a stream that actually embeds. DW (Akamai) and France 24 send
# permissive CORS and play in-browser; Sky News is an official YouTube embed; the
# Al Jazeera getaj.net streams are kept but can be geo/CORS-restricted in-browser.
LIVE_NEWS_CHANNELS: list[dict] = [
    {
        "id": "dw-en", "name": "DW English", "lang": "en",
        "region": "DE", "type": "hls", "official": True,
        "src": "https://dwamdstream102.akamaized.net/hls/live/2015525/dwstream102/index.m3u8",
    },
    {
        "id": "france24-en", "name": "France 24 English", "lang": "en",
        "region": "FR", "type": "hls", "official": True,
        "src": "https://static.france24.com/live/F24_EN_HI_HLS/live_web.m3u8",
    },
    {
        "id": "skynews", "name": "Sky News", "lang": "en",
        "region": "GB", "type": "youtube", "official": True,
        "src": "https://www.youtube.com/embed/live_stream?channel=UCoMdktPbSTixAyNGwb-UYkQ",
    },
    {
        "id": "aljazeera-en", "name": "Al Jazeera English", "lang": "en",
        "region": "QA", "type": "hls", "official": True,
        "src": "https://live-hls-web-aje.getaj.net/AJE/index.m3u8",
    },
    {
        "id": "aljazeera-ar", "name": "Al Jazeera Arabic", "lang": "ar",
        "region": "QA", "type": "hls", "official": True,
        "src": "https://live-hls-web-aja.getaj.net/AJA/index.m3u8",
    },
]


def _yt(channel_id: str) -> str:
    """Official YouTube-live embed URL for a channel — resolves to its current
    live broadcast, or shows 'offline' gracefully if the channel isn't live."""
    return f"https://www.youtube.com/embed/live_stream?channel={channel_id}"


# Curated official 24/7 channels. Best-effort channel IDs; the opt-in iptv-org
# expansion (settings.live_news_use_iptv_org) supplies the validated HLS bulk
# that takes paid users well past 50 channels.
LIVE_NEWS_CHANNELS += [
    {"id": "abcnews-us", "name": "ABC News (US)", "lang": "en", "region": "US", "type": "youtube", "official": True, "src": _yt("UCBi2mrWuNuyYy4gbM6fU18Q")},
    {"id": "nbcnews", "name": "NBC News NOW", "lang": "en", "region": "US", "type": "youtube", "official": True, "src": _yt("UCeY0bbntWzzVIaj2z3QigXg")},
    {"id": "cbsnews", "name": "CBS News", "lang": "en", "region": "US", "type": "youtube", "official": True, "src": _yt("UC8p1vwvWtl6T73JiExfWs1g")},
    {"id": "reuters", "name": "Reuters", "lang": "en", "region": "GB", "type": "youtube", "official": True, "src": _yt("UChqUTb7kYRX8-EiaN3XFrSQ")},
    {"id": "bloomberg", "name": "Bloomberg", "lang": "en", "region": "US", "type": "youtube", "official": True, "src": _yt("UCIALMKvObZNtJ6AmdCLP7Lg")},
    {"id": "cnbc", "name": "CNBC", "lang": "en", "region": "US", "type": "youtube", "official": True, "src": _yt("UCvJJ_dt2ZPg3Tug9hd9-LwQ")},
    {"id": "dw-news", "name": "DW News", "lang": "en", "region": "DE", "type": "youtube", "official": True, "src": _yt("UCknLrEdhRCp1aegoMqRaCZg")},
    {"id": "france24-yt", "name": "FRANCE 24 English", "lang": "en", "region": "FR", "type": "youtube", "official": True, "src": _yt("UCQfwfsi5VrQ8yKZ-UWmAEFg")},
    {"id": "aljazeera-yt", "name": "Al Jazeera English", "lang": "en", "region": "QA", "type": "youtube", "official": True, "src": _yt("UCNye-wNBqNL5ZzHSJj3l8Bg")},
    {"id": "trtworld", "name": "TRT World", "lang": "en", "region": "TR", "type": "youtube", "official": True, "src": _yt("UC7fWeaHhqgM4Ry-RMpM2YYw")},
    {"id": "euronews", "name": "Euronews English", "lang": "en", "region": "FR", "type": "youtube", "official": True, "src": _yt("UCSrZ3UV4jOidv8ppoVuvW9Q")},
    {"id": "wion", "name": "WION", "lang": "en", "region": "IN", "type": "youtube", "official": True, "src": _yt("UC_gUM8rL-Lrg6O3adPW9K1g")},
    {"id": "indiatoday", "name": "India Today", "lang": "en", "region": "IN", "type": "youtube", "official": True, "src": _yt("UCYPvAwZP8pZhSMW8qs7cVCw")},
    {"id": "ndtv", "name": "NDTV 24x7", "lang": "en", "region": "IN", "type": "youtube", "official": True, "src": _yt("UCZFMm1mMw0F81Z37aaEzTUA")},
    {"id": "cna", "name": "CNA (Channel NewsAsia)", "lang": "en", "region": "SG", "type": "youtube", "official": True, "src": _yt("UC4p_I9eiRewn2KoU-nawc7g")},
    {"id": "abc-au", "name": "ABC News (Australia)", "lang": "en", "region": "AU", "type": "youtube", "official": True, "src": _yt("UCVgO39Bk5sMo66-6o6Spn6Q")},
    {"id": "globalnews-ca", "name": "Global News (Canada)", "lang": "en", "region": "CA", "type": "youtube", "official": True, "src": _yt("UChLtXXpo4Ge1ReTEboVvTDg")},
]

_FREE_CHANNEL_IDS = {"dw-en", "france24-en", "abcnews-us", "aljazeera-yt"}  # free-tier taster


@router.get("/streams")
async def list_streams(user: UserDep) -> dict:
    """Tier-aware manifest of embeddable live-news channels.

    free → 2-channel taster; paid+ → full curated set, plus the opt-in iptv-org
    expansion when enabled. Always returns the curated list even if iptv fetch fails.
    """
    s = get_settings()
    is_free = user.tier == "free"

    channels = (
        [c for c in LIVE_NEWS_CHANNELS if c["id"] in _FREE_CHANNEL_IDS]
        if is_free else list(LIVE_NEWS_CHANNELS)
    )

    if not is_free and s.live_news_use_iptv_org:
        from backend.feeds.iptv_org import fetch_iptv_news
        extra = await fetch_iptv_news(s.live_news_iptv_org_url)
        # De-dupe by id against the curated set (curated wins).
        seen = {c["id"] for c in channels}
        channels.extend(c for c in extra if c["id"] not in seen)

    return {"channels": channels, "tier": user.tier, "total": len(channels)}
