from functools import lru_cache
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The public dev default for secret_key. auth.py signs JWTs with secret_key, so a
# production deploy left on this string lets anyone forge tokens (incl. admin).
_INSECURE_SECRET = "dev-secret-key-change-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AI
    voyage_api_key: str = ""

    # Provider posture — free/local by default. The LLM is always local (Ollama);
    # the only opt-in paid provider is Voyage embeddings, consulted solely when
    # paid_apis_enabled is True (see embedder.py). With the defaults below the whole
    # pipeline — LLM included — runs at $0 and needs no keys.
    paid_apis_enabled: bool = False        # master kill-switch for paid embeddings
    llm_provider: str = "ollama"           # ollama | off  (local-only)
    embeddings_provider: str = "local"     # local | voyage

    # Local (free) models
    ollama_base_url: str = "http://localhost:11434"
    local_llm_model: str = "llama3.2:latest"               # works out-of-box; qwen2.5:7b = sharper JSON
    # Outcome grading needs a model that reliably emits JSON on the strict JUDGE_SYSTEM
    # prompt. gemma (a common local_llm_model override) returns empty completions ~5/6 of
    # the time here; llama3.2 does it 6/6. Pinned separately so the analyst can still use a
    # different local_llm_model without breaking the calibration label loop.
    outcome_judge_model: str = "llama3.2:latest"
    # Vision (IMINT + geolocate) needs a MULTIMODAL model. Pinned separately for the
    # same reason as the judge: the default local_llm_model (llama3.2) is text-only, so
    # sharing it would make every image request degrade to "can't read images" — while
    # forcing local_llm_model=llava to fix that would blunt the text analyst. Keep them
    # split so each path runs the right model. Empty ⇒ fall back to local_llm_model.
    local_vision_model: str = "llava:latest"
    local_embedding_model: str = "BAAI/bge-large-en-v1.5"  # 1024-dim ⇒ no schema change
    # Where fastembed caches the downloaded model. Empty ⇒ library default (a tmp
    # dir under the ephemeral container FS, re-downloaded every boot). On Railway,
    # point this at a persistent volume (FASTEMBED_CACHE_DIR=/data/models) so the
    # ~1.3 GB bge-large model is fetched once, not on every scheduler restart.
    fastembed_cache_dir: str = ""
    ollama_timeout_seconds: float = 120.0
    # Vision needs its own, much longer deadline. Measured on the documented $0 path
    # (llava on CPU): ~90-170s for a SINGLE call, and /imint makes two back-to-back
    # (interpret, then geolocate). At the 120s text timeout the second call always
    # ReadTimeout'd — an uploaded image could never become an event out of the box.
    ollama_vision_timeout_seconds: float = 600.0

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
    secret_key: str = "dev-secret-key-change-in-production"

    # Payments
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    # Email (cost alerts)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Notifications
    firebase_service_account_json: str = ""

    # Maritime / AIS (optional — server-side vessel source for the maritime overlay)
    aishub_username: str = ""

    # Air traffic / OpenSky. Anonymous works (tight limits, often blocked from
    # datacenter IPs). OAuth2 client-credentials is the current supported auth
    # (basic username/password is deprecated); create an API client in your
    # OpenSky account to get a client id/secret.
    opensky_username: str = ""
    opensky_password: str = ""
    opensky_client_id: str = ""
    opensky_client_secret: str = ""

    # Storage
    cloudflare_r2_access_key: str = ""
    cloudflare_r2_secret_key: str = ""
    cloudflare_r2_bucket: str = "narrative-archive"
    cloudflare_r2_endpoint: str = ""

    # Monitoring
    sentry_dsn: str = ""

    # Pipeline config
    engine_version: str = "2.0"  # versioned scoring/propagation params (the "secret sauce")
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
    # Cadence — tuned so the freshness-critical path (ingest → embed → map →
    # feed) refreshes about every 5 min. Heavy analytics (graph/evolution/
    # exposure/archive) stay on a longer cadence to bound peak RAM/CPU on the
    # CPU-only demo stack. All fields are env-overridable (e.g. EMBED_INTERVAL_MINUTES).
    scrape_interval_hours: int = 2
    embed_interval_minutes: int = 5
    cluster_interval_minutes: int = 10
    importance_interval_minutes: int = 10
    mapping_interval_minutes: int = 5
    graph_interval_hours: int = 1
    evolution_interval_hours: int = 1
    alert_interval_minutes: int = 10
    # feed rebuild is now minute-based (was hourly) so newly ingested events
    # surface in the feed within ~10 min instead of up to an hour.
    feed_rebuild_interval_minutes: int = 10
    exposure_snapshot_interval_hours: int = 1
    hazard_ingest_interval_minutes: int = 5    # free real-time feed ingest
    market_ingest_interval_minutes: int = 5
    osint_ingest_interval_minutes: int = 5     # free keyless OSINT ingest

    # OSINT (open-source intelligence) — keyless GDELT news, always on.
    osint_source: str = "gdelt"    # gdelt (keyless, default)
    osint_subreddits: str = "worldnews,geopolitics,CredibleDefense"
    # OSINT v2 multi-source RSS/Atom collector (additive, keyless, always on). A
    # portfolio so no single blocked source starves ingestion. Override the default
    # feed list with comma-separated 'url|label' (or bare 'url') entries; empty = built-ins.
    osint_rss_enabled: bool = True
    osint_rss_feeds: str = ""
    # OSINT social — keyless Mastodon public tag timeline (additive, always on). One
    # GET per tag against a public instance; no auth. First-party social signal.
    osint_mastodon_enabled: bool = True
    mastodon_instance: str = "mastodon.social"
    mastodon_tags: str = "osint,geopolitics,breakingnews"

    # Free feed keys (optional — most sources need none)
    firms_map_key: str = ""        # NASA FIRMS wildfires
    openweather_api_key: str = ""  # global weather (optional; NWS/NHC need none)
    outcome_eval_interval_days: int = 7
    archive_interval_hours: int = 24

    # Cost control
    claude_daily_cost_alert_usd: float = 20.0    # soft alert (email only), Voyage spend
    claude_monthly_budget_usd: float = 200.0     # soft alert / admin reference
    admin_alert_email: str = ""

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

    @model_validator(mode="after")
    def _require_real_secret_in_prod(self) -> "Settings":
        # Fail closed: a production boot must not run on the public dev SECRET_KEY (or
        # an empty one). auth.py signs JWTs with secret_key, so the default would let
        # anyone mint valid admin tokens. Generate one with: openssl rand -hex 32
        if self.is_production and self.secret_key.strip() in ("", _INSECURE_SECRET):
            raise ValueError(
                "SECRET_KEY is unset or still the insecure dev default while APP_ENV=production. "
                "Set a strong random SECRET_KEY (e.g. `openssl rand -hex 32`) before deploying — "
                "JWTs are signed with it, so leaving the default lets anyone forge tokens."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
