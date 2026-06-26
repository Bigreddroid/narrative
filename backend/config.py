from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AI
    anthropic_api_key: str = ""
    voyage_api_key: str = ""

    # Provider posture — free/local by default. Paid providers are opt-in and
    # only consulted when paid_apis_enabled is True (see backend/services/llm.py
    # and embedder.py). With the defaults below the whole pipeline runs at $0.
    paid_apis_enabled: bool = False        # master kill-switch for ALL paid calls
    llm_provider: str = "ollama"           # ollama | anthropic | off
    embeddings_provider: str = "local"     # local | voyage

    # Local (free) models
    ollama_base_url: str = "http://localhost:11434"
    local_llm_model: str = "llama3.2:latest"               # works out-of-box; qwen2.5:7b = sharper JSON
    local_embedding_model: str = "BAAI/bge-large-en-v1.5"  # 1024-dim ⇒ no schema change
    ollama_timeout_seconds: float = 120.0

    # Database
    database_url: str = "postgresql+asyncpg://narrative:narrative@localhost:5432/narrative"
    redis_url: str = "redis://localhost:6379/0"

    @field_validator("database_url")
    @classmethod
    def _force_asyncpg_driver(cls, v: str) -> str:
        # The app's engine (backend/database.py) uses create_async_engine and
        # requires the asyncpg driver. Managed hosts (e.g. Railway) inject a
        # plain "postgresql://" URL, which makes migrations pass but crashes the
        # app on boot. Normalize any plain scheme to "postgresql+asyncpg://".
        if v.startswith("postgresql+asyncpg://"):
            return v
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    # Auth
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    secret_key: str = "dev-secret-key-change-in-production"

    # Payments
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""
    revenuecat_api_key: str = ""

    # Email (cost alerts)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Notifications
    firebase_service_account_json: str = ""

    # Maritime / AIS (optional — server-side vessel source for the maritime overlay)
    aishub_username: str = ""

    # Air traffic / OpenSky (optional — anonymous works; creds raise rate limits)
    opensky_username: str = ""
    opensky_password: str = ""

    # Storage
    cloudflare_r2_access_key: str = ""
    cloudflare_r2_secret_key: str = ""
    cloudflare_r2_bucket: str = "narrative-archive"
    cloudflare_r2_endpoint: str = ""

    # Bias data
    allsides_api_key: str = ""

    # Monitoring
    sentry_dsn: str = ""
    posthog_api_key: str = ""

    # Pipeline config
    engine_version: str = "2.0"  # versioned scoring/propagation params (the "secret sauce")
    consequence_engine_model: str = "claude-opus-4-8"
    embedding_model: str = "voyage-3"
    importance_threshold_deep: int = 70
    importance_threshold_light: int = 40
    max_deep_mappings_per_run: int = 8  # budget-aware routing: cap deep Claude maps/run
    cluster_similarity_threshold: float = 0.82  # legacy single-threshold (superseded below)
    cluster_attach_threshold: float = 0.80      # join an *established* cluster
    cluster_strong_threshold: float = 0.84      # always-attach bar (clearly same story)
    cluster_min_established: int = 2             # member count to count as "established"
    cluster_time_window_days: int = 14          # only consider events newer than this
    cluster_time_decay_days: float = 7.0        # similarity decays with article↔event time gap
    graph_connection_threshold: float = 0.35
    # Evolution / drift (Priority 6) — unified pressure vs staleness-adjusted threshold
    evolution_base_threshold: float = 0.15
    evolution_staleness_tau_hours: float = 168.0
    evolution_volume_weight: float = 0.5
    evolution_volume_tau: float = 2.0
    max_chain_steps: int = 6
    scrape_interval_hours: int = 2
    embed_interval_minutes: int = 15
    cluster_interval_minutes: int = 30
    importance_interval_minutes: int = 30
    mapping_interval_minutes: int = 15
    graph_interval_hours: int = 1
    evolution_interval_hours: int = 1
    alert_interval_minutes: int = 30
    feed_rebuild_interval_hours: int = 1
    exposure_snapshot_interval_hours: int = 1
    hazard_ingest_interval_minutes: int = 30   # free real-time feed ingest
    market_ingest_interval_minutes: int = 30
    osint_ingest_interval_minutes: int = 30    # free keyless OSINT ingest

    # OSINT (open-source intelligence) — keyless GDELT news by default. Reddit is kept
    # available but blocks anonymous reads AND app-credential creation, so it is opt-in
    # via OSINT_SOURCE=reddit (then add reddit_client_id/secret for app-only OAuth).
    osint_source: str = "gdelt"    # gdelt (keyless, default) | reddit
    osint_subreddits: str = "worldnews,geopolitics,CredibleDefense"
    reddit_user_agent: str = ""    # descriptive UA for Reddit (required by Reddit)
    reddit_client_id: str = ""     # Reddit app-only OAuth (the anon endpoint 403s)
    reddit_client_secret: str = ""

    # Live news (embedded player). Default = curated OFFICIAL channels only.
    # iptv-org is a huge keyless HLS catalog but aggregates unofficial restreams
    # (copyright/geo/uptime risk) — opt-in only, never the shipped default.
    live_news_use_iptv_org: bool = False
    live_news_iptv_org_url: str = "https://iptv-org.github.io/iptv/categories/news.m3u"

    # Free feed keys (optional — most sources need none)
    firms_map_key: str = ""        # NASA FIRMS wildfires
    openweather_api_key: str = ""  # global weather (optional; NWS/NHC need none)
    outcome_eval_interval_days: int = 7
    archive_interval_hours: int = 24

    # Cost control
    claude_daily_cost_alert_usd: float = 20.0    # soft alert (email only)
    claude_monthly_budget_usd: float = 200.0     # soft alert / admin reference
    admin_alert_email: str = ""
    # Enforced hard caps (NOT just alerts). When the active paid LLM provider is
    # selected, a call is blocked once today's / this-month's spend reaches these.
    # 0.0 ⇒ no paid spend permitted, so callers degrade to the free path.
    claude_hard_cap_daily_usd: float = 0.0
    claude_hard_cap_monthly_usd: float = 0.0

    # Data lifecycle
    hot_data_days: int = 30
    warm_data_months: int = 6

    # App
    app_env: str = "development"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    app_base_url: str = "https://app.thenarrative.io"  # used for Stripe redirect URLs

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
