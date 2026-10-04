from pydantic_settings import BaseSettings, SettingsConfigDict
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

    # Image upload limits
    max_image_pixels: int = 25_000_000
    max_image_dimension: int = 10_000

    # OCR (Tesseract)
    tesseract_cmd: str = ""
    ocr_timeout_seconds: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()


def get_max_upload_bytes() -> int:
    return settings.max_upload_mb * 1024 * 1024


def get_allowed_origins() -> List[str]:
    return settings.allowed_origins