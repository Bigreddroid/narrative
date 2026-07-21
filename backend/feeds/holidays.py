"""
Public holidays — free, NO key (Nager.Date).
  • https://date.nager.at/api/v3/PublicHolidays/{year}/{countryCode}

Holidays are per-office CONTEXT, not consequence events — they never enter the
event graph or the map. The customer deck reads them per office (staffing / road
impact around a site), and slice 6 uses an office-proximate holiday as one input
to derived traffic disruption. Pure parser (`parse_holidays`) + a date-window
filter (`upcoming`) are import-safe and unit-tested; `fetch_holidays` does the I/O.
"""

import json
from datetime import date, datetime

NAGER = "https://date.nager.at/api/v3/PublicHolidays"


def parse_holidays(payload) -> list[dict]:
    """Nager.Date holiday array → minimal holiday dicts. Skips undated rows."""
    out = []
    for h in payload or []:
        d = (h or {}).get("date")
        if not d:
            continue
        name = h.get("name") or h.get("localName") or "Public holiday"
        out.append({
            "date": d,
            "name": name,
            "localName": h.get("localName") or name,
        })
    return out


def upcoming(holidays: list[dict], within_days: int, today: date | None = None) -> list[dict]:
    """Holidays falling in [today, today + within_days], soonest first, each stamped
    with `in_days`. Undated/badly-dated rows are dropped, not raised on."""
    today = today or date.today()
    out = []
    for h in holidays:
        try:
            hd = datetime.strptime(h["date"], "%Y-%m-%d").date()
        except (ValueError, KeyError, TypeError):
            continue
        delta = (hd - today).days
        if 0 <= delta <= within_days:
            out.append({**h, "in_days": delta})
    return sorted(out, key=lambda x: x["in_days"])


async def fetch_holidays(country_code: str, year: int) -> list[dict]:
    """All public holidays for one ISO-3166 alpha-2 country + year. A bad fetch
    degrades to [] — a missing calendar must never break the deck."""
    import httpx  # lazy — keeps the parser importable without the dep
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{NAGER}/{year}/{country_code}")
            # Nager sends 204 (no content) for countries it doesn't cover — e.g.
            # India and the GCC — which fall to the config's curated supplement.
            # Decode the raw bytes as UTF-8 ourselves: httpx's .json() can mangle
            # non-ASCII names (e.g. "Mariä") when the server omits a charset.
            if r.status_code == 200 and r.content:
                return parse_holidays(json.loads(r.content))
    except Exception:  # noqa: BLE001 — one bad calendar must not sink the overlay
        pass
    return []
