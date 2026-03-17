import sys

from pydantic import model_validator
from pydantic_settings import BaseSettings

_DEFAULT_JWT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/finmonitor"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800  # seconds — recycle connections after 30 min
    db_pool_pre_ping: bool = True  # validate connection before use (handles stale connections)

    # Cache
    redis_url: str | None = None  # optional — app starts without Redis (cache disabled)

    # Data provider API keys
    finnhub_api_key: str = ""
    alpha_vantage_api_key: str = ""
    news_api_key: str = ""

    # Notifications - PagerDuty
    pagerduty_api_key: str = ""
    pagerduty_service_id: str = ""

    # Notifications - Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "alerts@localhost"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Provider selection
    # Choices: "alphavantage" (free, default) | "finnhub" (premium)
    ipo_provider: str = "alphavantage"

    # Scheduler intervals (seconds)
    news_poll_interval_seconds: int = 60
    ipo_poll_interval_seconds: int = 3600
    quotes_poll_interval_seconds: int = 30

    # Auth
    google_client_id: str = ""
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30

    # Threshold alerts
    alerts_require_premium: bool = False   # flip True to gate feature for free users
    alert_cooldown_minutes: int = 60       # min minutes between re-firing same alert

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        """Prevent startup with insecure defaults in non-development environments."""
        if self.app_env != "development" and self.jwt_secret_key == _DEFAULT_JWT_SECRET:
            print(  # noqa: T201 — intentional, logging not yet configured at import time
                "FATAL: JWT_SECRET_KEY is set to the default placeholder value. "
                "Generate a secure secret with: openssl rand -hex 32\n"
                "Set it via the JWT_SECRET_KEY environment variable or .env file.",
                file=sys.stderr,
            )
            sys.exit(1)
        return self


settings = Settings()
