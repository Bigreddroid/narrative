"""Per-office context overlays for the customer deck — public holidays (Nager.Date,
keyless). Holidays are context, not events: they never enter the event graph. Cached
in-process with a long TTL so the deck can poll cheaply without hammering Nager.Date."""

import time
from datetime import date

from fastapi import APIRouter, Query

from backend.api.dependencies import UserDep
from backend.feeds.holidays import fetch_holidays, upcoming

router = APIRouter(prefix="/context", tags=["context"])

# Holidays change ~never within a year — a 6h TTL keeps Nager.Date essentially untouched.
_CACHE: dict[tuple[str, int], tuple[float, list]] = {}
_TTL = 6 * 3600


async def _holidays_cached(code: str, year: int) -> list[dict]:
    key = (code, year)
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    data = await fetch_holidays(code, year)
    if data:  # never cache an empty result — a transient fetch failure must retry
        _CACHE[key] = (now, data)
    return data


@router.get("/calendar")
async def get_calendar(
    user: UserDep,
    countries: str = Query(..., description="Comma-separated ISO-3166 alpha-2 country codes"),
    days: int = Query(45, ge=1, le=365, description="Look-ahead window in days"),
) -> dict:
    """Upcoming public holidays per country within the look-ahead window. Keyed by
    ISO code so the deck can attach a holiday to each office by its country."""
    codes = [c.strip().upper() for c in countries.split(",") if c.strip()][:20]
    today = date.today()
    out: dict[str, list] = {}
    for code in codes:
        up = upcoming(await _holidays_cached(code, today.year), days, today)
        # A window crossing Dec 31 needs next year's calendar too (e.g. New Year's Day).
        if today.month == 12:
            up += upcoming(await _holidays_cached(code, today.year + 1), days, today)
        out[code] = up
    return {"holidays": out, "as_of": today.isoformat(), "window_days": days}
