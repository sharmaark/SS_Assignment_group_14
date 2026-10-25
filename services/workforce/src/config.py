from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "workforce"
    workforce_port: int = 8002
    workforce_database_url: str = (
        "postgresql+psycopg://workforce_user:workforce_pass@localhost:55432/workforce_db"
    )
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
