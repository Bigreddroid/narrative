"""Property test for the OSINT ingest worker orchestration (no DB/network/LLM).
All I/O is stubbed: fetch, the LLM cost-guard, triage, the DB session, and _upsert.
Run from repo root:  python -m backend.workers.osint_ingest_worker_test
"""

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.workers import osint_ingest_worker as W
from backend.feeds import osint_threatintel, reddit_osint
from backend.services import cost_guard, osint_agent

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# ── Stubs: no DB, no network, no LLM ─────────────────────────────────────────
class _FakeDB:
    def __init__(self):
        self.committed = False
        self.added = []

    def add_all(self, objs):
        self.added.extend(objs)  # decision rows in _log_decisions' own session

    async def commit(self):
        self.committed = True


class _FakeSession:
    async def __aenter__(self):
        return _FakeDB()

    async def __aexit__(self, *a):
        return False


POSTS = [
    {"external_id": "reddit-good", "title": "Missile strike on Kyiv", "selftext": "",
     "score": 10, "created_utc": 1718000000, "subreddit": "worldnews"},
    {"external_id": "reddit-noise", "title": "", "selftext": "",          # triage → None (dropped)
     "score": 1, "created_utc": 1718000000, "subreddit": "worldnews"},
    {"external_id": "reddit-boom", "title": "explodes in triage", "selftext": "",  # triage raises
     "score": 1, "created_utc": 1718000000, "subreddit": "worldnews"},
]


def _fake_triage(post, allow_llm, source="osint_gdelt"):
    if post["external_id"] == "reddit-boom":
        raise RuntimeError("triage blew up")
    if not post.get("title"):
        return None
    return {"external_id": post["external_id"], "source": source, "title": post["title"],
            "summary": post["title"], "category": "conflict", "lat": None, "lng": None,
            "importance": 60, "status": "developing", "geography": [], "ts": None,
            "confidence": 0.5, "evidence_url": ""}


def _decision_for(post, signal, source):
    """Minimal decision record matching osint_agent._decision's shape."""
    return {"external_id": post["external_id"], "source": source,
            "kept": signal is not None, "reason": "test",
            "method": "heuristic", "category": signal["category"] if signal else None,
            "confidence": None, "importance": None, "title": post.get("title")}


def _fake_triage_wd(post, allow_llm, source="osint_gdelt"):
    """Worker calls triage_with_decision → (signal, decision). reddit-boom still raises."""
    signal = _fake_triage(post, allow_llm, source)
    return signal, _decision_for(post, signal, source)


async def _fake_fetch(*a, **k):
    return list(POSTS)


async def _fake_llm_allowed(db):
    return False  # reported back in the worker result as llm=False


_upsert_calls: list[str] = []


async def _fake_upsert(signal, db, require_geo=False):
    _upsert_calls.append(signal["external_id"])
    return True  # treat every upsert as a newly created event


async def _fake_ti_empty(*a, **k):
    return []


async def _fake_di_empty(*a, **k):
    return []


async def _fake_rss_empty(*a, **k):
    return []


# Patch the names as the worker resolves them (module-global lookups at call time).
W.AsyncSessionLocal = _FakeSession
W._osint_source = lambda: (_fake_fetch, "osint_gdelt")  # bypass config/network selection
W.osint_threatintel.fetch_threatintel = _fake_ti_empty  # additive feed off for the base run
W.osint_disinfo.fetch_disinfo = _fake_di_empty          # curated feed off for the base run
W.rss_osint.fetch_rss_osint = _fake_rss_empty           # RSS portfolio off for the base run (no network)
cost_guard.llm_allowed = _fake_llm_allowed
osint_agent.triage_with_decision = _fake_triage_wd
W._upsert = _fake_upsert

res = asyncio.run(W.run_osint_ingest_worker())

ok("worker counts all fetched posts", res["posts"] == 3)
ok("worker triages-in only the good post", res["ingested"] == 1)
ok("worker creates the new event", res["created"] == 1)
ok("worker reports llm flag from cost_guard", res["llm"] is False)
ok("worker reports the selected source", res["source"] == "osint_gdelt")
ok("worker upserts exactly the good signal", _upsert_calls == ["reddit-good"])
ok("bad post (triage raised) does not sink the run", "reddit-boom" not in _upsert_calls)
# Flywheel: a decision is logged for every judged post (good kept + noise dropped);
# reddit-boom raised before a decision could be formed, so it is not logged.
ok("worker logs a decision per judged post", res["logged"] == 2)

# ── additive threat-intel batch is triaged under its own source tag ──────────
ti_sources: list[str] = []


def _capture_triage(post, allow_llm, source="osint_gdelt"):
    if post["external_id"].startswith("threatintel-"):
        ti_sources.append(source)
    signal = _fake_triage(post, allow_llm, source)
    return signal, _decision_for(post, signal, source)


async def _fake_ti_one(*a, **k):
    return [{"external_id": "threatintel-x", "title": "Ransomware attack: grp claims Acme",
             "selftext": "", "score": 0, "created_utc": None, "subreddit": "ransomware.live"}]


_upsert_calls.clear()
W.osint_threatintel.fetch_threatintel = _fake_ti_one
osint_agent.triage_with_decision = _capture_triage
res2 = asyncio.run(W.run_osint_ingest_worker())

ok("threat-intel batch adds to post count", res2["posts"] == 4)
ok("threat-intel post upserted", "threatintel-x" in _upsert_calls)
ok("threat-intel triaged with its own source tag", ti_sources == ["osint_threatintel"])

# ── additive RSS/Atom portfolio batch is triaged under its own source tag ─────
rss_sources: list[str] = []


def _capture_rss_triage(post, allow_llm, source="osint_gdelt"):
    if post["external_id"].startswith("rss-"):
        rss_sources.append(source)
    signal = _fake_triage(post, allow_llm, source)
    return signal, _decision_for(post, signal, source)


async def _fake_rss_one(*a, **k):
    return [{"external_id": "rss-x", "title": "Earthquake strikes coast", "selftext": "",
             "score": 0, "created_utc": None, "subreddit": "news.google.com"}]


_upsert_calls.clear()
W.osint_threatintel.fetch_threatintel = _fake_ti_empty
W.rss_osint.fetch_rss_osint = _fake_rss_one
osint_agent.triage_with_decision = _capture_rss_triage
res_rss = asyncio.run(W.run_osint_ingest_worker())

ok("rss batch adds to post count", res_rss["posts"] == 4)  # 3 reddit + 0 ti + 1 rss
ok("rss post upserted", "rss-x" in _upsert_calls)
ok("rss triaged with its own source tag", rss_sources == ["osint_rss"])

# reset RSS to empty so the disinfo-test post counts below are unaffected
W.rss_osint.fetch_rss_osint = _fake_rss_empty

# ── curated disinfo feed upserts directly, bypassing triage ───────────────────
triage_seen: list[str] = []


def _watch_triage(post, allow_llm, source="osint_gdelt"):
    triage_seen.append(post["external_id"])
    signal = _fake_triage(post, allow_llm, source)
    return signal, _decision_for(post, signal, source)


async def _fake_di_two(*a, **k):
    return [
        {"external_id": "disinfo-a", "source": "osint_disinfo", "title": "False flood photo",
         "summary": "x", "category": "disinfo", "lat": None, "lng": None, "importance": 45,
         "status": "developing", "geography": [], "ts": None, "confidence": 0.5, "evidence_url": ""},
        {"external_id": "disinfo-b", "source": "osint_disinfo", "title": "Doctored clip",
         "summary": "y", "category": "disinfo", "lat": None, "lng": None, "importance": 45,
         "status": "developing", "geography": [], "ts": None, "confidence": 0.5, "evidence_url": ""},
    ]


_upsert_calls.clear()
W.osint_threatintel.fetch_threatintel = _fake_ti_empty
W.osint_disinfo.fetch_disinfo = _fake_di_two
osint_agent.triage_with_decision = _watch_triage
res3 = asyncio.run(W.run_osint_ingest_worker())

ok("disinfo feed adds to post count", res3["posts"] == 5)  # 3 reddit + 0 ti + 2 disinfo
ok("disinfo signals upserted directly", "disinfo-a" in _upsert_calls and "disinfo-b" in _upsert_calls)
ok("disinfo bypasses triage", "disinfo-a" not in triage_seen and "disinfo-b" not in triage_seen)

print(f"\nosint_ingest_worker: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
