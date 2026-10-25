from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "dispatch"
    dispatch_port: int = Field(default=8003, ge=1, le=65535)
    dispatch_database_url: str = "postgresql+psycopg://dispatch_user:dispatch_pass@localhost:55433/dispatch_db"
    work_order_url: str = "http://localhost:8001"
    workforce_url: str = "http://localhost:8002"
    notification_url: str = "http://localhost:8004"
    downstream_timeout_seconds: float = Field(default=1.0, gt=0)
    notification_max_attempts: int = Field(default=3, ge=1, le=10)
    retry_base_seconds: float = Field(default=0.15, ge=0)
    idempotency_wait_seconds: float = Field(default=8.0, ge=0)
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
