"""
Wipro demo — scenario seeder.

Seeds a small, clearly-labelled demo scenario built from the client's own stated
concerns in the QBR (UAE/Saudi staff safety, Europe presence, cyber, and the wish for
cross-domain connections): two geographic clusters of events from DIFFERENT intelligence
disciplines converging in space + time, so the corroboration engine fuses them and the
/wipro dashboard's fusion strip fires on real engine output — not mocked UI.

  Cluster GULF (≤400 km, ≤72 h — the corroboration gate):
    • Strait of Hormuz tanker incident        conflict → HUMINT
    • UAE ports ransomware campaign (Dubai)   cyber    → CYBINT
    • Gulf freight & war-risk premium spike   market   → FININT
  Cluster EUROPE (Black Sea):
    • Grain-corridor disruption (Constanța)   conflict → HUMINT
    • Romanian grid intrusion attempts        cyber    → CYBINT
  Plus one Riyadh advisory event so a Saudi trip in the travel panel shows "Advise".

Written through hazard_ingest_worker._upsert — the SAME canonical path every live feed
uses (dedupe, consequence map, embedding, graph linkage). Idempotent: fixed
(source, external_id) pairs mean re-runs refresh instead of duplicating.

Run from the repo root (host venv or inside the api container):
    python demo/wipro/seed_scenario.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import update  # noqa: E402

from backend.database import AsyncSessionLocal  # noqa: E402
from backend.models.narrative_event import NarrativeEvent  # noqa: E402
from backend.workers.hazard_ingest_worker import _upsert  # noqa: E402

# All sources share this prefix (cleanup + the dashboard's ?source_prefix= fetch),
# but each signal carries its own DISTINCT source below: the corroboration engine
# only counts *independent* sources, so a single shared source would mean the
# clusters could never fuse — the original design bug this fixed.
SOURCE_PREFIX = "wipro_demo"  # unknown to SOURCE_DISCIPLINE → discipline derives from category
LEGACY_SOURCE = "wipro_demo"  # rows seeded before the per-signal split

SIGNALS = [
    # ── Cluster GULF — three disciplines converge near Dubai/Hormuz ─────────────
    {
        "title": "[DEMO] Tanker reports close-quarters incident in Strait of Hormuz",
        "summary": "A commercial tanker reported an aggressive close-quarters approach in the "
                   "Strait of Hormuz; transit traffic advised heightened readiness. Demo scenario event.",
        "category": "conflict", "importance": 72, "status": "escalating",
        "geography": ["United Arab Emirates", "Strait of Hormuz"],
        "lat": 26.57, "lng": 56.25, "external_id": "wipro-gulf-hormuz-1",
        "source": "wipro_demo_maritime",
    },
    {
        "title": "[DEMO] Ransomware campaign targets UAE port and logistics operators",
        "summary": "Coordinated ransomware intrusions reported across UAE port community systems "
                   "and freight forwarders; container processing delayed. Demo scenario event.",
        "category": "cyber", "importance": 65, "status": "developing",
        "geography": ["United Arab Emirates", "Dubai"],
        "lat": 25.20, "lng": 55.27, "external_id": "wipro-gulf-cyber-1",
        "source": "wipro_demo_cyber",
    },
    {
        "title": "[DEMO] Gulf freight rates and war-risk premiums spike on transit fears",
        "summary": "War-risk insurance premiums for Gulf transits repriced sharply; freight "
                   "surcharges follow as carriers reroute. Demo scenario event.",
        "category": "market", "importance": 58, "status": "developing",
        "geography": ["United Arab Emirates", "Gulf"],
        "lat": 25.10, "lng": 55.40, "external_id": "wipro-gulf-market-1",
        "source": "wipro_demo_market",
    },
    # ── Cluster EUROPE — Black Sea: the ME↔Europe↔Ukraine connection ────────────
    {
        "title": "[DEMO] Black Sea grain-corridor transit disrupted off Constanța",
        "summary": "Commercial transits through the western Black Sea corridor suspended after "
                   "reported drone debris near shipping lanes. Demo scenario event.",
        "category": "conflict", "importance": 68, "status": "escalating",
        "geography": ["Romania", "Black Sea"],
        "lat": 44.17, "lng": 28.65, "external_id": "wipro-eu-blacksea-1",
        "source": "wipro_demo_maritime",
    },
    {
        "title": "[DEMO] Intrusion attempts probe Romanian power-grid operators",
        "summary": "Romanian CERT reports credential-phishing and OT reconnaissance against grid "
                   "operators; no outages, elevated monitoring. Demo scenario event.",
        "category": "cyber", "importance": 55, "status": "developing",
        "geography": ["Romania", "Bucharest"],
        "lat": 44.43, "lng": 26.10, "external_id": "wipro-eu-cyber-1",
        "source": "wipro_demo_cyber",
    },
    # ── Travel-security driver — makes a Riyadh trip read "Advise", not "Proceed" ─
    {
        "title": "[DEMO] Security advisory: heightened posture around Riyadh business district",
        "summary": "Authorities raised protective posture around central Riyadh following a "
                   "regional alert; movement unaffected, vigilance advised. Demo scenario event.",
        "category": "unrest", "importance": 55, "status": "developing",
        "geography": ["Saudi Arabia", "Riyadh"],
        "lat": 24.71, "lng": 46.68, "external_id": "wipro-ksa-advisory-1",
        "source": "wipro_demo_advisory",
    },
]


async def main() -> None:
    created = 0
    async with AsyncSessionLocal() as db:
        # Migrate rows seeded under the old shared source to their per-signal
        # source, so _upsert refreshes them in place instead of duplicating.
        for s in SIGNALS:
            await db.execute(
                update(NarrativeEvent)
                .where(NarrativeEvent.source == LEGACY_SOURCE)
                .where(NarrativeEvent.external_id == s["external_id"])
                .values(source=s["source"])
            )
        for s in SIGNALS:
            if await _upsert(dict(s), db, require_geo=True):
                created += 1
        await db.commit()
    print(f"wipro demo scenario: {len(SIGNALS)} signals upserted ({created} new). "
          f"Re-runs refresh in place — external_ids are fixed.")


if __name__ == "__main__":
    asyncio.run(main())
