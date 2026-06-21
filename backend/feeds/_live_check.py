"""Ad-hoc live check: hit each no-key feed's real endpoint and report what the
parser produced. Read-only (no DB writes). Run: python -m backend.feeds._live_check"""

import asyncio

from backend.feeds import usgs, weather, gdacs, gdelt, launches, spaceweather, cyber, market


async def check(name, coro):
    try:
        r = await asyncio.wait_for(coro, timeout=25)
        if isinstance(r, list):
            sample = r[0] if r else None
            title = (sample or {}).get("title") if isinstance(sample, dict) else sample
            print(f"  OK  {name:16} {len(r):>4} items   e.g. {str(title)[:70]}")
        else:
            print(f"  OK  {name:16} value={r}")
    except Exception as exc:  # noqa: BLE001
        print(f"  XX  {name:16} {type(exc).__name__}: {str(exc)[:90]}")


async def main():
    await check("usgs", usgs.fetch_earthquakes())
    await check("weather", weather.fetch_weather())
    await check("gdacs", gdacs.fetch_gdacs())
    await check("gdelt", gdelt.fetch_gdelt())
    await check("launches", launches.fetch_launches())
    await check("spaceweather", spaceweather.fetch_kp())
    await check("cisa_kev", cyber.fetch_kev())
    await check("market", market.fetch_market())


if __name__ == "__main__":
    asyncio.run(main())
