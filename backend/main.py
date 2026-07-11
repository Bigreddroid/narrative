import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.api.rate_limit import limiter
from backend.api.routes import admin, aircraft, auth, chat, events, exposure, feed, follows, geolocate, graph, market, notifications, osint, search, stripe_routes, users, vessels
from backend.config import get_settings
from backend.database import engine

settings = get_settings()

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)

logging.basicConfig(
    level=logging.DEBUG if not settings.is_production else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Replaces the deprecated @app.on_event("startup") hook (removed in modern
    # Starlette/FastAPI). Runs once on startup; teardown goes after the yield.
    logging.getLogger(__name__).info("The Narrative API starting — %s", settings.app_env)
    yield


app = FastAPI(
    title="The Narrative API",
    description="World consequence intelligence infrastructure",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Rate limiting (FASTAPI-LIMITS-001): per-user/per-IP throttle to mitigate DoS
# and bound expensive work. Registered BEFORE CORS so CORSMiddleware stays the
# outermost layer and 429 responses still carry CORS headers for browser clients.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers on every response (cheap, standard hardening). HSTS/CSP are
# left to the TLS-terminating edge (Railway/Vercel); these are the API-relevant
# ones. (The "server: uvicorn" banner is suppressed at the server layer via
# server_header=False in the run scripts — a middleware override can't remove it,
# it only appends a duplicate.)
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "0",  # modern guidance: disable the legacy, buggy auditor
}


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    for k, v in _SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    return response

app.include_router(auth.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(exposure.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")
app.include_router(vessels.router, prefix="/api/v1")
app.include_router(aircraft.router, prefix="/api/v1")
app.include_router(feed.router, prefix="/api/v1")
app.include_router(follows.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(geolocate.router, prefix="/api/v1")
app.include_router(osint.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(stripe_routes.router, prefix="/api/v1")


@app.get("/health")
@limiter.exempt  # health checks must always respond and not consume the budget
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env}
