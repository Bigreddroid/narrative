"""
Seed script for demo data (lean terminal).
Run: python -m backend.seed
Creates a handful of realistic NarrativeEvents + minimal articles/consequence maps
so /feed, /graph/* and mobile show real (non-mock) data.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal
from backend.models.article import Article
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.event_connection import EventConnection
from backend.models.narrative_event import NarrativeEvent


SAMPLE_EVENTS = [
    {
        "canonical_title": "Red Sea Shipping Attacks Escalate",
        "canonical_summary": "Houthi forces intensify strikes on commercial vessels, forcing major rerouting around Africa.",
        "category": "geopolitics",
        "current_status": "escalating",
        "global_importance_score": 87.0,
        "geo_centroid_lat": 15.5,
        "geo_centroid_lng": 42.0,
        "affected_sectors": ["shipping", "energy", "trade"],
        "is_mapped": True,
    },
    {
        "canonical_title": "US Fed Signals Prolonged High Rates",
        "canonical_summary": "Central bank holds rates steady, citing persistent inflation and strong labor data.",
        "category": "economics",
        "current_status": "developing",
        "global_importance_score": 72.0,
        "geo_centroid_lat": 38.9,
        "geo_centroid_lng": -77.0,
        "affected_sectors": ["finance", "housing", "employment"],
        "is_mapped": True,
    },
    {
        "canonical_title": "India Monsoon Delays Hit Agriculture",
        "canonical_summary": "Late and erratic rainfall threatens kharif crop yields across key states.",
        "category": "climate",
        "current_status": "developing",
        "global_importance_score": 61.0,
        "geo_centroid_lat": 20.0,
        "geo_centroid_lng": 77.0,
        "affected_sectors": ["agriculture", "food", "rural"],
        "is_mapped": True,
    },
]

SAMPLE_MAPS = [
    {"prediction_score": 0.68, "confidence": 0.72, "direct_impact": ["Higher fuel and goods prices in Europe and Asia", "Insurance premiums for Red Sea routes up 300%"]},
    {"prediction_score": 0.55, "confidence": 0.61, "direct_impact": ["Mortgage rates remain elevated into 2026", "Consumer spending slowdown in US and Europe"]},
    {"prediction_score": 0.49, "confidence": 0.58, "direct_impact": ["Food price spikes in India and import-dependent nations", "Rural distress and migration pressure"]},
]


async def seed():
    async with AsyncSessionLocal() as db:
        event_ids = []
        for i, ev in enumerate(SAMPLE_EVENTS):
            event = NarrativeEvent(
                id=uuid.uuid4(),
                canonical_title=ev["canonical_title"],
                canonical_summary=ev["canonical_summary"],
                category=ev["category"],
                current_status=ev["current_status"],
                global_importance_score=ev["global_importance_score"],
                geo_centroid_lat=ev["geo_centroid_lat"],
                geo_centroid_lng=ev["geo_centroid_lng"],
                affected_sectors=ev["affected_sectors"],
                is_mapped=ev["is_mapped"],
                first_detected_at=datetime.now(timezone.utc),
            )
            db.add(event)
            await db.flush()
            event_ids.append(event.id)

            # Minimal article for clustering realism
            article = Article(
                id=uuid.uuid4(),
                title=ev["canonical_title"],
                url=f"https://example.com/news/{i}",
                source="seed",
                content=ev["canonical_summary"],
                narrative_event_id=event.id,
                is_embedded=True,
                is_clustered=True,
            )
            db.add(article)

            # Consequence map for impact/prediction in feed + mobile
            cmap = EventConsequenceMap(
                id=uuid.uuid4(),
                narrative_event_id=event.id,
                version=1,
                prediction_score=SAMPLE_MAPS[i]["prediction_score"],
                confidence=SAMPLE_MAPS[i]["confidence"],
                direct_impact=SAMPLE_MAPS[i]["direct_impact"],
                is_suppressed=False,
            )
            db.add(cmap)

        # Add some connections for the graph/world to have edges (for web globe lines like mocks)
        if len(event_ids) >= 2:
            conn1 = EventConnection(
                id=uuid.uuid4(),
                event_a_id=event_ids[0],
                event_b_id=event_ids[1],
                connection_weight=0.75,
                connection_type="causal",
                shared_context="Supply chain and economic ripple effects",
            )
            db.add(conn1)
        if len(event_ids) >= 3:
            conn2 = EventConnection(
                id=uuid.uuid4(),
                event_a_id=event_ids[0],
                event_b_id=event_ids[2],
                connection_weight=0.55,
                connection_type="correlated",
                shared_context="Global trade and agriculture disruption",
            )
            db.add(conn2)

        await db.commit()
        print("Seeded 3 demo events with articles, consequence maps and connections for graph.")


if __name__ == "__main__":
    asyncio.run(seed())
