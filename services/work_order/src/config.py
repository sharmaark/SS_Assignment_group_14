from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "work-order"
    work_order_port: int = 8001
    work_order_mongodb_url: str = (
        "mongodb://work_order_user:work_order_pass@localhost:27017/"
        "work_order_db?authSource=work_order_db"
    )
    work_order_mongodb_database: str = "work_order_db"
    max_photo_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
