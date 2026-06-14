import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import admin, auth, events, feed, follows, graph, notifications, search, stripe_routes, users
from backend.config import get_settings
from backend.database import engine

settings = get_settings()

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)

logging.basicConfig(
    level=logging.DEBUG if not settings.is_production else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="The Narrative API",
    description="Dual customer + enterprise Bloomberg-style terminal for world events, news, data, analytics and impact. Lean ingestion + light AI. Dark terminal + light paper editorial themes.",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(feed.router, prefix="/api/v1")
app.include_router(follows.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(stripe_routes.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


@app.on_event("startup")
async def on_startup():
    logging.getLogger(__name__).info("The Narrative API starting — %s", settings.app_env)
