"""Per-office context overlays for the customer deck — public holidays (Nager.Date,
keyless). Holidays are context, not events: they never enter the event graph. Cached
in-process with a long TTL so the deck can poll cheaply without hammering Nager.Date."""

import asyncio
import time
from datetime import date

from fastapi import APIRouter, Query

from backend.api.dependencies import UserDep
from backend.countries import to_iso2
from backend.feeds.gatherings import gatherings_now
from backend.feeds.holidays import fetch_holidays, upcoming

router = APIRouter(prefix="/context", tags=["context"])

# Holidays change ~never within a year — a 6h TTL keeps Nager.Date essentially untouched.
_CACHE: dict[tuple[str, int], tuple[float, list]] = {}
_TTL = 6 * 3600

# Sized off a real register, not a demo one: the published Wipro office list is 43
# countries, and a global customer's own register will be larger still. Both caps
# exist only to bound a pathological input — anything they drop comes back in
# `omitted` so the caller can say so on screen.
_MAX_NAMES = 120
_MAX_CODES = 80


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
    # Accepts NAMES as well as codes. A site register stores "United Arab Emirates",
    # not "AE", so requiring codes would have pushed a country→ISO table into the
    # browser bundle — a second copy to drift out of step with backend/countries.py.
    codes: list[str] = []
    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for raw in [c.strip() for c in countries.split(",") if c.strip()][:_MAX_NAMES]:
        iso = to_iso2(raw)
        if not iso:
            unresolved.append(raw)
            continue
        resolved[raw] = iso
        if iso not in codes:
            codes.append(iso)

    # 🔴 Whatever the cap drops is REPORTED, never silently discarded. The published
    # register spans 43 countries; the old cap of 20 would have cut 23 of them and
    # returned a response indistinguishable from "those countries have no holidays".
    # A cap is a legitimate defence against a pathological register — hiding what it
    # cut is not.
    omitted, codes = codes[_MAX_CODES:], codes[:_MAX_CODES]

    today = date.today()
    out: dict[str, list] = {}
    # 🔴 Countries the SOURCE does not cover at all. Nager.Date returns 204 for India
    # and the GCC — the customer's largest markets. Without this list a country with
    # no coverage is indistinguishable from a country with no holidays in the window,
    # and a security calendar that silently omits Diwali because of an upstream gap is
    # worse than one that says "we have no holiday source for India".
    no_data: list[str] = []

    # Concurrent, because this went from 5 countries to 43 the day the register was
    # replaced with the published office list. Sequentially that is 43 round trips
    # behind one request — past the deck's 15s client timeout on a cold cache, which
    # the browser would have reported as "no holidays at all".
    async def _for(code: str) -> tuple[str, list, bool]:
        year_all = await _holidays_cached(code, today.year)
        up = upcoming(year_all, days, today)
        # A window crossing Dec 31 needs next year's calendar too (e.g. New Year's Day).
        if today.month == 12:
            up += upcoming(await _holidays_cached(code, today.year + 1), days, today)
        return code, up, bool(year_all)

    for code, up, had_data in await asyncio.gather(*(_for(c) for c in codes)):
        if not had_data:
            no_data.append(code)
        out[code] = up
    # Public gatherings, keyless from Wikidata. This layer used to be absent with the
    # deck stating outright that no keyless source existed — which was measured to be
    # untrue (see backend/feeds/gatherings.py). `gatherings_checked` distinguishes "we
    # asked and there is nothing near you" from "we never asked", because the deck
    # renders those two identically and only one of them is honest.
    # Non-blocking: the cached answer if we have one, else None plus a background
    # warm. Awaiting the fetch here let a 75s Wikidata walk blow the deck's 15s
    # timeout for the ENTIRE response, taking the working holiday layer down with
    # the optional gatherings one.
    gatherings = gatherings_now(days=days)
    return {
        "holidays": out,
        "gatherings": gatherings or [],
        # None means the source could not be reached; [] means it answered "nothing".
        "gatherings_checked": gatherings is not None,
        "no_source_coverage": no_data,
        # Countries the CAP dropped, as opposed to ones the source does not cover.
        "omitted": omitted,
        # The name→ISO map the caller needs to attach a holiday to each site, and the
        # names we could NOT resolve. A country silently missing its holiday layer
        # looks identical to a country with no holidays, and only one of those is true.
        "codes": resolved,
        "unresolved": unresolved,
        "as_of": today.isoformat(),
        "window_days": days,
    }
