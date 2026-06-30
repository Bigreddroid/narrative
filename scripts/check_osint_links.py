#!/usr/bin/env python3
"""OSINT link-rot checker (WS3).

Probes the hosts behind the curated native search patterns and the live-enrichment
providers, reporting any that are unreachable so the patterns file / provider
registry can be pruned. Read-only, network-bound; NOT run in any hot path — run it
manually or on a schedule before a release.

Usage:
  python scripts/check_osint_links.py            # check native pattern hosts
  python scripts/check_osint_links.py --sample 40
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services import osint_catalog as oc  # noqa: E402
from backend.services import osint_enrich as oe  # noqa: E402

UA = "the-narrative-osint-linkcheck/1.0"
TIMEOUT = 10


def probe(host: str) -> tuple[str, bool, str]:
    """HEAD/GET the host root; alive if any HTTP response (even 4xx — the host is up)."""
    url = f"https://{host}/"
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return host, True, str(r.status)
    except urllib.error.HTTPError as e:
        return host, True, f"http {e.code}"  # host responded → alive
    except Exception as e:  # noqa: BLE001
        try:  # some hosts reject HEAD — retry GET once
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return host, True, str(r.status)
        except urllib.error.HTTPError as e2:
            return host, True, f"http {e2.code}"
        except Exception:  # noqa: BLE001
            return host, False, str(e)[:60]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="check only the first N hosts")
    args = ap.parse_args()

    hosts = sorted(set(oc._search_patterns()) | set(oe.live_host_kinds()))
    if args.sample:
        hosts = hosts[: args.sample]

    print(f"Probing {len(hosts)} OSINT hosts (native patterns + live providers)...\n", file=sys.stderr)
    dead: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        for host, alive, info in pool.map(probe, hosts):
            mark = "ok " if alive else "XX "
            print(f"  {mark} {host}  ({info})")
            if not alive:
                dead.append((host, info))

    print(f"\n{len(hosts) - len(dead)}/{len(hosts)} alive.", file=sys.stderr)
    if dead:
        print("DEAD (prune from osint_search_patterns.json / PROVIDERS):", file=sys.stderr)
        for host, info in dead:
            print(f"  - {host}: {info}", file=sys.stderr)
    return 0  # informational; never fails CI


if __name__ == "__main__":
    raise SystemExit(main())
