"""
Market layer — free commodity / FX prices, mapped to CPE sectors. NO paid keys.
  • Commodities & indices: stooq.com light CSV (https://stooq.com/q/l/)
  • FX: Frankfurter / ECB (https://api.frankfurter.app)

Pure parsers (parse_stooq_csv, parse_frankfurter) + an async fetch_market(). Output
is a list of MarketRow dicts {symbol, label, sector, price, change_pct}.
"""

# stooq symbol → (label, CPE sector). Commodity futures + regional equity indices.
STOOQ_SYMBOLS = {
    # Commodities (futures)
    "cb.f": ("Brent Crude", "Energy"),
    "cl.f": ("WTI Crude", "Energy"),
    "ng.f": ("Natural Gas", "Energy"),
    "zw.f": ("Wheat", "Agriculture"),
    "zc.f": ("Corn", "Agriculture"),
    "hg.f": ("Copper", "Commodities"),
    "gc.f": ("Gold", "Commodities"),
    # Regional equity indices (region-risk proxies) + global volatility gauge
    "^spx": ("S&P 500", "Equities"),
    "^dax": ("DAX", "Equities"),
    "^nkx": ("Nikkei 225", "Equities"),
    "^hsi": ("Hang Seng", "Equities"),
    "^vix": ("VIX", "Volatility"),
}
# Frankfurter (base USD) → (label, sector). FX as a region-risk proxy.
FX_SYMBOLS = {
    "EUR": ("USD/EUR", "FX"),
    "GBP": ("USD/GBP", "FX"),
    "JPY": ("USD/JPY", "FX"),
    "CNY": ("USD/CNY", "FX"),
}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_stooq_csv(text: str) -> dict | None:
    """One stooq light-CSV row → {symbol, label, sector, price, change_pct} (or None)."""
    if not text:
        return None
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    header = [h.strip().lower() for h in lines[0].split(",")]
    row = lines[1].split(",")
    rec = dict(zip(header, row))
    sym = (rec.get("symbol") or "").strip().lower()
    close, opn = _f(rec.get("close")), _f(rec.get("open"))
    if sym not in STOOQ_SYMBOLS or close is None:
        return None
    label, sector = STOOQ_SYMBOLS[sym]
    change = round((close - opn) / opn * 100, 2) if (opn and opn != 0) else None
    clean = sym.replace(".f", "").lstrip("^")  # "cb.f"→"cb", "^spx"→"spx"
    return {"symbol": clean, "label": label, "sector": sector, "price": close, "change_pct": change}


def parse_frankfurter(data: dict) -> list[dict]:
    """Frankfurter latest JSON → FX MarketRows (USD base)."""
    rates = (data or {}).get("rates") or {}
    out = []
    for cur, (label, sector) in FX_SYMBOLS.items():
        if cur in rates and _f(rates[cur]) is not None:
            out.append({"symbol": f"usd{cur.lower()}", "label": label, "sector": sector,
                        "price": _f(rates[cur]), "change_pct": None})
    return out


async def fetch_market() -> list[dict]:
    import httpx  # lazy — keeps parsers importable without the dep
    rows = []
    headers = {"User-Agent": "the-narrative/1.0"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
        # stooq commodities/indices — best-effort: stooq bot-blocks some hosts
        # (returns its homepage), so a 0-row result here is expected off-VPS.
        for sym in STOOQ_SYMBOLS:
            try:
                r = await client.get(f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcvn&h&e=csv")
                if r.status_code == 200 and (rec := parse_stooq_csv(r.text)):
                    rows.append(rec)
            except Exception:  # noqa: BLE001 — skip a bad symbol, keep the rest
                continue
        # FX via Frankfurter (ECB). Host moved from .app → .dev/v1.
        try:
            fx = await client.get("https://api.frankfurter.dev/v1/latest?base=USD&symbols=" + ",".join(FX_SYMBOLS))
            if fx.status_code == 200:
                rows.extend(parse_frankfurter(fx.json()))
        except Exception:  # noqa: BLE001
            pass
    return rows


def sector_stress(rows: list[dict]) -> dict:
    """Per-sector market stress 0–1 from absolute day moves — feeds the CPE."""
    by_sector: dict[str, list[float]] = {}
    for r in rows:
        if r.get("change_pct") is not None and r.get("sector"):
            by_sector.setdefault(r["sector"], []).append(abs(r["change_pct"]))
    # 5% daily move ⇒ ~max stress.
    return {s: min(1.0, (sum(v) / len(v)) / 5.0) for s, v in by_sector.items() if v}
