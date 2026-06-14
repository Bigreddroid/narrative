from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AI
    anthropic_api_key: str = ""
    voyage_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://narrative:narrative@localhost:5432/narrative"
    redis_url: str = "redis://localhost:6379/0"

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

    # Maps
    mapbox_public_token: str = ""

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
    consequence_engine_model: str = "claude-sonnet-4-20250514"
    embedding_model: str = "voyage-3"
    importance_threshold_deep: int = 70
    importance_threshold_light: int = 40
    cluster_similarity_threshold: float = 0.82
    graph_connection_threshold: float = 0.35
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
    outcome_eval_interval_days: int = 7
    archive_interval_hours: int = 24

    # Cost control
    claude_daily_cost_alert_usd: float = 20.0
    claude_monthly_budget_usd: float = 200.0
    admin_alert_email: str = ""

    # Data lifecycle
    hot_data_days: int = 30
    warm_data_months: int = 6

    # App
    app_env: str = "development"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
