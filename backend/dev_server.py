"""
Standalone dev server — no database, no Supabase, no Docker needed.
Runs with: uvicorn backend.dev_server:app --reload --port 8000
Uses in-memory mock data and HS256 JWT auth.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import FastAPI, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from pydantic import BaseModel

SECRET_KEY = "dev-secret-key-narrative"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 72

app = FastAPI(title="The Narrative — Dev Server", version="dev")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory stores ─────────────────────────────────────────────────────────

USERS: dict[str, dict] = {}   # email -> user dict
FOLLOWS: dict[str, set] = {}  # user_id -> set of event_ids

MOCK_EVENTS = [
    {
        "id": "evt-001",
        "title": "Federal Reserve holds rates amid recession fears",
        "category": "economics",
        "status": "developing",
        "importance_score": 88,
        "lat": 38.9,
        "lng": -77.0,
        "geography": ["United States", "Global"],
        "sectors": ["finance", "housing", "employment"],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "articles": [
            {"title": "Fed holds rates for fourth straight meeting as recession risk rises", "source": "Reuters", "date": "2026-05-20", "url": "https://reuters.com"},
            {"title": "Bond markets signal prolonged rate pause — traders push back cut bets to 2025", "source": "Bloomberg", "date": "2026-05-19", "url": "https://bloomberg.com"},
            {"title": "Housing affordability index hits 30-year low as elevated rates persist", "source": "Financial Times", "date": "2026-05-18", "url": "https://ft.com"},
            {"title": "Small business optimism falls to 11-year low as credit conditions tighten", "source": "WSJ", "date": "2026-05-17", "url": "https://wsj.com"},
        ],
        "consequence_map": {
            "is_paywalled": False,
            "consequence_chain": [
                {
                    "type": "VERIFIED FACT",
                    "content": "The Federal Reserve voted 7-2 to hold the federal funds rate at 5.25–5.50% for the fourth consecutive meeting.",
                    "evidence": "Federal Reserve press release, March 20, 2024",
                    "children": [
                        {
                            "type": "INFERRED MECHANISM",
                            "content": "Elevated borrowing costs reduce demand for mortgages and auto loans, cooling consumer spending.",
                            "evidence": "30-year fixed mortgage rates remain near 7.1% (Freddie Mac, March 2024)",
                            "children": [
                                {
                                    "type": "SPECULATIVE EFFECT",
                                    "content": "Home prices in rate-sensitive markets (Phoenix, Austin, Denver) may decline 5–12% by Q4 2024.",
                                    "evidence": None,
                                    "children": []
                                }
                            ]
                        },
                        {
                            "type": "INFERRED MECHANISM",
                            "content": "Commercial credit tightens, slowing small business hiring and capital expenditure.",
                            "evidence": "NFIB Small Business Optimism Index fell to 88.5 in February 2024",
                            "children": []
                        }
                    ]
                }
            ],
            "direct_impact": [
                {
                    "sector": "housing",
                    "severity": "high",
                    "description": "First-time homebuyers effectively priced out in 28 major metros with median home price above $400K.",
                    "population_affected": "4.2M prospective buyers",
                    "evidence": "NAR affordability index at 30-year low"
                },
                {
                    "sector": "employment",
                    "severity": "medium",
                    "description": "Construction sector job postings down 18% YoY as housing starts collapse.",
                    "population_affected": "Construction workforce (~8M workers)",
                    "evidence": "BLS JOLTS data, February 2024"
                },
                {
                    "sector": "finance",
                    "severity": "medium",
                    "description": "Regional banks holding long-duration bond portfolios face continued unrealized losses.",
                    "population_affected": "Depositors at 186 at-risk regional banks",
                    "evidence": "FDIC Quarterly Banking Profile Q4 2023"
                }
            ],
            "predictions": [
                {"label": "rate cut by Sept", "confidence": 62},
                {"label": "recession 2024", "confidence": 34}
            ]
        }
    },
    {
        "id": "evt-002",
        "title": "Red Sea shipping disruptions cascade into global supply chains",
        "category": "geopolitics",
        "status": "escalating",
        "importance_score": 91,
        "lat": 15.0,
        "lng": 43.0,
        "geography": ["Yemen", "Middle East", "Global"],
        "sectors": ["transport", "energy", "food"],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "articles": [
            {"title": "Houthi attacks force shipping firms onto 9,000km Cape of Good Hope detour", "source": "Reuters", "date": "2026-05-22", "url": "https://reuters.com"},
            {"title": "Container freight rates surge 340% on Asia-Europe corridor since October", "source": "Bloomberg", "date": "2026-05-21", "url": "https://bloomberg.com"},
            {"title": "European retailers warn of stock shortages as Red Sea crisis deepens", "source": "Financial Times", "date": "2026-05-20", "url": "https://ft.com"},
        ],
        "consequence_map": {
            "is_paywalled": True,
            "consequence_chain": [],
            "direct_impact": [],
            "predictions": [{"label": "6-month disruption", "confidence": 71}]
        }
    },
    {
        "id": "evt-003",
        "title": "EU AI Act enters force — compliance deadline 2026",
        "category": "technology",
        "status": "stable",
        "importance_score": 76,
        "lat": 50.8,
        "lng": 4.4,
        "geography": ["European Union", "Global"],
        "sectors": ["technology", "finance", "healthcare"],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "articles": [
            {"title": "EU AI Act enters force — what companies must do now", "source": "Reuters", "date": "2026-05-18", "url": "https://reuters.com"},
            {"title": "OpenAI, Google face steep compliance costs under new EU AI rules", "source": "Bloomberg", "date": "2026-05-16", "url": "https://bloomberg.com"},
            {"title": "High-risk AI systems face mandatory third-party audits from 2026", "source": "Financial Times", "date": "2026-05-15", "url": "https://ft.com"},
            {"title": "EU AI Act creates $3bn compliance market for consulting firms", "source": "WSJ", "date": "2026-05-14", "url": "https://wsj.com"},
        ],
        "consequence_map": {
            "is_paywalled": False,
            "consequence_chain": [
                {
                    "type": "VERIFIED FACT",
                    "content": "The EU AI Act was published in the Official Journal on July 12, 2024, entering into force 20 days later.",
                    "evidence": "EU Official Journal, 2024/1689",
                    "children": [
                        {
                            "type": "INFERRED MECHANISM",
                            "content": "High-risk AI systems (medical, employment, credit scoring) face mandatory conformity assessments before EU market access.",
                            "evidence": "Article 43, EU AI Act",
                            "children": [
                                {
                                    "type": "SPECULATIVE EFFECT",
                                    "content": "US AI companies without EU compliance infrastructure face effective market exclusion until 2026.",
                                    "evidence": None,
                                    "children": []
                                }
                            ]
                        }
                    ]
                }
            ],
            "direct_impact": [
                {
                    "sector": "technology",
                    "severity": "high",
                    "description": "AI developers serving EU markets must appoint an EU representative and register high-risk systems in EU database.",
                    "population_affected": "~2,400 AI companies active in EU",
                    "evidence": "EU AI Office registry (draft)"
                }
            ],
            "predictions": [
                {"label": "compliance by 2026", "confidence": 78},
                {"label": "US equivalent passed", "confidence": 22}
            ]
        }
    },
    {
        "id": "evt-004",
        "title": "Amazon basin drought reaches 60-year low — river levels critical",
        "category": "climate",
        "status": "escalating",
        "importance_score": 85,
        "lat": -3.5,
        "lng": -60.0,
        "geography": ["Brazil", "Peru", "Colombia", "South America"],
        "sectors": ["food", "energy", "transport"],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "consequence_map": {
            "is_paywalled": True,
            "consequence_chain": [],
            "direct_impact": [],
            "predictions": [{"label": "food shortage Q2", "confidence": 55}]
        }
    },
    {
        "id": "evt-005",
        "title": "India-Pakistan water treaty suspended — Indus basin tensions rise",
        "category": "geopolitics",
        "status": "developing",
        "importance_score": 79,
        "lat": 30.4,
        "lng": 73.1,
        "geography": ["India", "Pakistan", "South Asia"],
        "sectors": ["food", "energy", "security"],
        "created_at": (datetime.now(timezone.utc) - timedelta(hours=18)).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "consequence_map": {
            "is_paywalled": True,
            "consequence_chain": [],
            "direct_impact": [],
            "predictions": [{"label": "military escalation", "confidence": 28}]
        }
    },
    {
        "id": "evt-006",
        "title": "WHO declares mpox public health emergency of international concern",
        "category": "health",
        "status": "developing",
        "importance_score": 83,
        "lat": -4.3,
        "lng": 15.3,
        "geography": ["DR Congo", "Africa", "Global"],
        "sectors": ["healthcare", "transport", "employment"],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=4)).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "articles": [
            {"title": "WHO declares mpox international health emergency for second time", "source": "Reuters", "date": "2026-05-19", "url": "https://reuters.com"},
            {"title": "Mpox clade Ib shows higher lethality — WHO urges emergency vaccine rollout", "source": "Bloomberg", "date": "2026-05-18", "url": "https://bloomberg.com"},
            {"title": "Vaccine supplies critically short as mpox spreads across six African nations", "source": "Financial Times", "date": "2026-05-17", "url": "https://ft.com"},
        ],
        "consequence_map": {
            "is_paywalled": False,
            "consequence_chain": [
                {
                    "type": "VERIFIED FACT",
                    "content": "WHO Director-General declared mpox clade Ib a PHEIC on August 14, 2024, citing spread across DRC and neighboring countries.",
                    "evidence": "WHO Statement, August 14, 2024",
                    "children": [
                        {
                            "type": "INFERRED MECHANISM",
                            "content": "PHEIC status triggers mandatory reporting and accelerates CEPI/Gavi vaccine allocation for 12 African nations.",
                            "evidence": "IHR Article 44 obligations",
                            "children": []
                        }
                    ]
                }
            ],
            "direct_impact": [
                {
                    "sector": "healthcare",
                    "severity": "high",
                    "description": "Healthcare systems in 12 high-burden African countries face surge without adequate diagnostic capacity.",
                    "population_affected": "180M in affected regions",
                    "evidence": "WHO situation report #4"
                }
            ],
            "predictions": [
                {"label": "vaccine deployed Q4", "confidence": 67},
                {"label": "global spread contained", "confidence": 71}
            ]
        }
    },
    {
        "id": "evt-007",
        "title": "Germany enters technical recession — manufacturing output falls 4.4%",
        "category": "economics",
        "status": "stable",
        "importance_score": 72,
        "lat": 52.5,
        "lng": 13.4,
        "geography": ["Germany", "European Union"],
        "sectors": ["employment", "energy", "finance"],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=6)).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "consequence_map": {
            "is_paywalled": True,
            "consequence_chain": [],
            "direct_impact": [],
            "predictions": [{"label": "recovery Q3 2024", "confidence": 43}]
        }
    },
    {
        "id": "evt-008",
        "title": "Taiwan Strait tensions: PLA exercises after Lai inauguration",
        "category": "security",
        "status": "developing",
        "importance_score": 94,
        "lat": 23.7,
        "lng": 121.0,
        "geography": ["Taiwan", "China", "Asia Pacific"],
        "sectors": ["technology", "security", "finance"],
        "created_at": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "articles": [
            {"title": "China launches Joint Sword-2024B military drills encircling Taiwan", "source": "Reuters", "date": "2026-05-24", "url": "https://reuters.com"},
            {"title": "TSMC shares fall 4.2% as PLA exercises simulate blockade scenarios", "source": "Bloomberg", "date": "2026-05-24", "url": "https://bloomberg.com"},
            {"title": "Pentagon dispatches carrier group to South China Sea amid Taiwan exercises", "source": "WSJ", "date": "2026-05-23", "url": "https://wsj.com"},
            {"title": "Semiconductor supply chain at risk as Taiwan tensions escalate", "source": "Financial Times", "date": "2026-05-23", "url": "https://ft.com"},
        ],
        "consequence_map": {
            "is_paywalled": True,
            "consequence_chain": [],
            "direct_impact": [],
            "predictions": [{"label": "semiconductor disruption", "confidence": 45}]
        }
    },
]

MOCK_GRAPH = {
    "nodes": [
        {"id": e["id"], "title": e["title"], "category": e["category"],
         "importance_score": e["importance_score"], "status": e["status"],
         "geography": e["geography"], "lat": e.get("lat"), "lng": e.get("lng")}
        for e in MOCK_EVENTS
    ],
    "edges": [
        {"source_event_id": "evt-001", "target_event_id": "evt-007", "connection_type": "economic_spillover", "weight": 0.72},
        {"source_event_id": "evt-002", "target_event_id": "evt-001", "connection_type": "supply_pressure", "weight": 0.65},
        {"source_event_id": "evt-002", "target_event_id": "evt-004", "connection_type": "shared_sector", "weight": 0.58},
        {"source_event_id": "evt-004", "target_event_id": "evt-006", "connection_type": "climate_health", "weight": 0.48},
        {"source_event_id": "evt-003", "target_event_id": "evt-008", "connection_type": "tech_geopolitics", "weight": 0.61},
        {"source_event_id": "evt-008", "target_event_id": "evt-002", "connection_type": "supply_chain", "weight": 0.55},
    ]
}


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def make_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": user_id, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_user_by_id(user_id: str) -> dict:
    for u in USERS.values():
        if u["id"] == user_id:
            return u
    raise HTTPException(status_code=401, detail="User not found")


def current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    uid = decode_token(authorization)
    return get_user_by_id(uid)


# ─── Auth routes ──────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    email: str
    password: str


@app.post("/api/v1/auth/dev-login")
def dev_login(body: LoginBody):
    email = body.email.lower().strip()
    if not email or not body.password:
        raise HTTPException(status_code=400, detail="Email and password required")

    is_new = email not in USERS
    if is_new:
        uid = str(uuid.uuid4())
        USERS[email] = {
            "id": uid, "email": email, "tier": "paid",
            "city": None, "country": None, "profession": None,
            "stripe_customer_id": None, "created_at": datetime.now(timezone.utc).isoformat()
        }

    user = USERS[email]
    token = make_token(user["id"])
    return {
        "access_token": token,
        "user_id": user["id"],
        "email": user["email"],
        "tier": user["tier"],
        "is_new_user": is_new or user.get("city") is None,
    }


@app.post("/api/v1/auth/exchange")
def exchange(body: dict):
    raise HTTPException(status_code=501, detail="Use /api/v1/auth/dev-login in dev mode")


# ─── User routes ──────────────────────────────────────────────────────────────

@app.get("/api/v1/users/me")
def get_me(authorization: Annotated[str | None, Header()] = None):
    uid = decode_token(authorization)
    user = get_user_by_id(uid)
    return user


@app.patch("/api/v1/users/me")
def patch_me(body: dict, authorization: Annotated[str | None, Header()] = None):
    uid = decode_token(authorization)
    user = get_user_by_id(uid)
    for k in ("city", "country", "profession", "spending_categories"):
        if k in body:
            user[k] = body[k]
    return user


# ─── Events routes ────────────────────────────────────────────────────────────

@app.get("/api/v1/events")
def list_events(
    limit: int = 40,
    category: str | None = None,
    status: str | None = None,
    q: str | None = None,
):
    evs = list(MOCK_EVENTS)
    if category:
        evs = [e for e in evs if e["category"] == category]
    if status:
        statuses = [s.strip() for s in status.split(",")]
        evs = [e for e in evs if e["status"] in statuses]
    if q:
        ql = q.lower()
        evs = [e for e in evs if ql in e["title"].lower()
               or any(ql in g.lower() for g in e.get("geography", []))
               or any(ql in s.lower() for s in e.get("sectors", []))]
    evs = sorted(evs, key=lambda e: e["importance_score"], reverse=True)
    return {"events": evs[:limit]}


@app.get("/api/v1/events/{event_id}")
def get_event(event_id: str, authorization: Annotated[str | None, Header()] = None):
    ev = next((e for e in MOCK_EVENTS if e["id"] == event_id), None)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")

    uid = decode_token(authorization)
    user = get_user_by_id(uid)

    # Gate paywalled content for free users
    result = dict(ev)
    if ev["consequence_map"].get("is_paywalled") and user.get("tier") != "paid":
        result["consequence_map"] = {
            "is_paywalled": True,
            "consequence_chain": [],
            "direct_impact": [],
            "predictions": ev["consequence_map"].get("predictions", [])
        }
    return result


@app.get("/api/v1/events/{event_id}/revisions")
def get_revisions(event_id: str):
    return {"revisions": []}


# ─── Graph routes ─────────────────────────────────────────────────────────────

@app.get("/api/v1/graph/world")
def world_graph(authorization: Annotated[str | None, Header()] = None):
    uid = decode_token(authorization)
    user = get_user_by_id(uid)
    nodes = MOCK_GRAPH["nodes"]
    if user.get("tier") != "paid":
        nodes = nodes[:10]
    return {"nodes": nodes, "edges": MOCK_GRAPH["edges"]}


@app.get("/api/v1/graph/event/{event_id}")
def event_graph(event_id: str):
    # Return the connected subgraph
    connected = {event_id}
    edges = []
    for e in MOCK_GRAPH["edges"]:
        if e["source_event_id"] == event_id or e["target_event_id"] == event_id:
            edges.append(e)
            connected.add(e["source_event_id"])
            connected.add(e["target_event_id"])
    nodes = [n for n in MOCK_GRAPH["nodes"] if n["id"] in connected]
    return {"nodes": nodes, "edges": edges}


# ─── Feed route ───────────────────────────────────────────────────────────────

@app.get("/api/v1/feed")
def get_feed(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"events": sorted(MOCK_EVENTS, key=lambda e: e["importance_score"], reverse=True)}


# ─── Follows routes ───────────────────────────────────────────────────────────

@app.get("/api/v1/follows")
def list_follows(authorization: Annotated[str | None, Header()] = None):
    uid = decode_token(authorization)
    followed_ids = FOLLOWS.get(uid, set())
    follows = []
    for eid in followed_ids:
        ev = next((e for e in MOCK_EVENTS if e["id"] == eid), None)
        if ev:
            follows.append({
                "id": eid,
                "event_id": eid,
                "narrative_event_id": eid,
                "event_title": ev["title"],
                "event_category": ev["category"],
                "event_status": ev["status"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    return {"follows": follows}


class FollowBody(BaseModel):
    event_id: str


@app.post("/api/v1/follows")
def create_follow(body: FollowBody, authorization: Annotated[str | None, Header()] = None):
    uid = decode_token(authorization)
    user = get_user_by_id(uid)
    if user.get("tier") != "paid" and len(FOLLOWS.get(uid, set())) >= 3:
        raise HTTPException(status_code=403, detail="Free tier limited to 3 follows")
    FOLLOWS.setdefault(uid, set()).add(body.event_id)
    return {"followed": True}


@app.delete("/api/v1/follows/{event_id}")
def delete_follow(event_id: str, authorization: Annotated[str | None, Header()] = None):
    uid = decode_token(authorization)
    FOLLOWS.get(uid, set()).discard(event_id)
    return {"unfollowed": True}


# ─── Notifications ────────────────────────────────────────────────────────────

@app.get("/api/v1/notifications/")
def list_notifications(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"notifications": []}


@app.post("/api/v1/notifications/register")
def register_push(body: dict, authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"registered": True}


# ─── Stripe routes ────────────────────────────────────────────────────────────

@app.post("/api/v1/stripe/checkout")
def stripe_checkout(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"checkout_url": "https://checkout.stripe.com/dev-placeholder", "session_id": "cs_dev_placeholder"}


@app.post("/api/v1/stripe/portal")
def stripe_portal(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"portal_url": "https://billing.stripe.com/dev-placeholder"}


@app.post("/api/v1/stripe/webhook")
def stripe_webhook():
    return {"received": True}


# ─── Admin routes (basic) ────────────────────────────────────────────────────

@app.get("/api/v1/admin/dashboard")
def admin_dashboard(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {
        "total_events": len(MOCK_EVENTS),
        "total_articles": 247,
        "total_users": len(USERS) or 1,
        "paid_users": 1,
        "today_claude_cost": 3.42,
        "today_articles_scraped": 187,
        "today_events_mapped": 6,
    }


@app.get("/api/v1/admin/costs")
def admin_costs(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"daily": [{"date": "2026-05-24", "cost_usd": 3.42, "tokens": 284000}], "monthly_total": 58.20}


@app.get("/api/v1/admin/users")
def admin_users(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"users": list(USERS.values()), "total": len(USERS), "paid": sum(1 for u in USERS.values() if u.get("tier") == "paid")}


@app.get("/api/v1/admin/pipeline")
def admin_pipeline(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"runs": []}


@app.get("/api/v1/admin/sources")
def admin_sources(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"sources": [
        {"id": 1, "name": "Reuters", "url": "https://feeds.reuters.com/reuters/topNews", "is_active": True, "scrape_method": "rss"},
        {"id": 2, "name": "AP News", "url": "https://feeds.apnews.com/apnews/topheadlines", "is_active": True, "scrape_method": "rss"},
        {"id": 3, "name": "Financial Times", "url": "https://www.ft.com/rss/home", "is_active": True, "scrape_method": "rss"},
    ]}


@app.post("/api/v1/admin/sources/{source_id}/toggle")
def toggle_source(source_id: int, authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"toggled": True}


@app.get("/api/v1/admin/events")
def admin_events(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"events": MOCK_EVENTS}


@app.get("/api/v1/admin/workers")
def admin_workers(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"workers": [
        {"name": "scrape_worker", "status": "idle", "last_run": None},
        {"name": "embed_worker", "status": "idle", "last_run": None},
        {"name": "mapping_worker", "status": "idle", "last_run": None},
    ]}


@app.post("/api/v1/admin/workers/{worker_name}/trigger")
def trigger_worker(worker_name: str, authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"queued": True, "worker": worker_name}


@app.get("/api/v1/admin/hallucinations")
def admin_hallucinations(authorization: Annotated[str | None, Header()] = None):
    decode_token(authorization)
    return {"flags": []}


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "env": "dev", "mode": "mock-data"}
