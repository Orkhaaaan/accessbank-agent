"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    database_url: str = "sqlite:///./accessbank.db"
    telegram_bot_token: str = ""
    telegram_supervisor_chat_id: str = ""
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    gmail_sender_email: str = ""
    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_tenant_id: str = ""
    ms_sender_email: str = ""
    escalation_email: str = "support@accessbank.az"
    app_env: str = "development"
    secret_key: str = "dev-secret-change-me"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    rate_limit_per_minute: int = 20
    chroma_persist_dir: str = "./data/chroma"
    skip_email: bool = False

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def use_gmail(self) -> bool:
        return bool(
            self.gmail_client_id
            and self.gmail_client_secret
            and self.gmail_refresh_token
        )

    @property
    def use_microsoft(self) -> bool:
        return bool(
            self.ms_client_id and self.ms_client_secret and self.ms_tenant_id
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
