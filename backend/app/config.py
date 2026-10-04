from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./scamshield.db"
    max_upload_mb: int = 5
    allowed_origins: List[str] = ["http://localhost:5173"]
    retention_days: int = 30
    store_content: bool = False
    demo_mode: bool = False
    rate_limit: str = "30/minute"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()


def get_max_upload_bytes() -> int:
    return settings.max_upload_mb * 1024 * 1024


def get_allowed_origins() -> List[str]:
    return settings.allowed_origins