from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    database_url: str = "sqlite:///./dev.db"
    frontend_url: str = "http://localhost:5173"
    storage_root: str = "storage"
    openai_api_key: str | None = None
    openai_model: str | None = None
    service_name: str = Field(default="b2b-ai-order-processing-agent")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
