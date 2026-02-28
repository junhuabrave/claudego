from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/finmonitor"

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

    # Scheduler intervals (seconds)
    news_poll_interval_seconds: int = 60
    ipo_poll_interval_seconds: int = 3600
    quotes_poll_interval_seconds: int = 30

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
