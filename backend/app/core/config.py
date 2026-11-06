"""Runtime settings. Business rates do not live here; they live in the database."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "HRIS"
    env: str = "development"
    secret_key: str = "dev-only-change-me-please-32b"
    field_encryption_key: str = ""

    mongo_uri: str = "mongodb://127.0.0.1:27020/?replicaSet=rs0"
    mongo_db: str = "hris"

    redis_url: str = "redis://127.0.0.1:6379/2"

    access_token_minutes: int = 15
    refresh_token_days: int = 14
    mfa_token_minutes: int = 5
    lockout_attempts: int = 5
    lockout_minutes: int = 15

    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cors_origins: str = "http://127.0.0.1:5174,http://localhost:5174"

    storage_dir: str = "storage"
    public_base_url: str = "http://127.0.0.1:5174"
    api_base_url: str = "http://127.0.0.1:8010"

    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_from: str = "HRIS <hris@localhost>"
    smtp_user: str = ""
    smtp_password: str = ""

    sso_google_client_id: str = ""
    sso_google_client_secret: str = ""
    sso_microsoft_client_id: str = ""
    sso_microsoft_client_secret: str = ""
    sso_microsoft_tenant: str = "common"

    sentry_dsn: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
