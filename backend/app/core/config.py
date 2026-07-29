from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str | None = None
    bootstrap_operator_password: str | None = None
    database_url: str = "sqlite:///./dev.db"
    seed_demo_data: bool = False
    frontend_url: str = "http://localhost:5173"
    storage_root: str = "storage"
    aws_region: str = "eu-central-1"
    aws_profile: str | None = None
    aws_s3_bucket: str | None = None
    textract_auto_processing_enabled: bool = False
    textract_poll_interval_seconds: int = Field(default=15, ge=5, le=3600)
    textract_max_jobs_per_poll: int = Field(default=20, ge=1, le=200)
    ai_provider: Literal["mock", "bedrock"] = "mock"
    bedrock_model_id: str | None = None
    bedrock_max_tokens: int = Field(default=4096, ge=1, le=65536)
    bedrock_temperature: float = Field(default=0, ge=0, le=1)
    gmail_ingestion_enabled: bool = False
    gmail_imap_host: str = "imap.gmail.com"
    gmail_imap_port: int = Field(default=993, ge=1, le=65535)
    gmail_smtp_host: str = "smtp.gmail.com"
    gmail_smtp_port: int = Field(default=587, ge=1, le=65535)
    gmail_username: str | None = None
    gmail_app_password: str | None = None
    gmail_imap_folder: str = "INBOX"
    gmail_search_criteria: str = "UNSEEN"
    gmail_poll_interval_seconds: int = Field(default=60, ge=15, le=86400)
    gmail_max_messages_per_poll: int = Field(default=25, ge=1, le=500)
    gmail_mark_as_read: bool = True
    openai_api_key: str | None = None
    openai_model: str | None = None
    service_name: str = Field(default="b2b-ai-order-processing-agent")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
