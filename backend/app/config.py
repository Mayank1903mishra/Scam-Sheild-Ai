from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import json
import os


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./scamshield.db"
    max_upload_mb: int = 5
    # Accepted as a comma-separated list or a JSON array (see
    # get_allowed_origins). Covers both the Vite dev server ports used by
    # this repo (3000 in package.json, 5173 in the README).
    allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )
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

    # Intelligence layer (independent source adapters)
    # Master switch: when false both sources report "disabled" and no
    # outbound request is made (analysis runs exactly as before).
    intel_lookups_enabled: bool = True
    intel_timeout_seconds: float = 3.0
    intel_cache_seconds: int = 1800
    # Google Safe Browsing Lookup API v4. Empty = source reported as
    # disabled; the key is read from the environment and never committed.
    google_safe_browsing_api_key: str = ""
    # Official I4C (Ministry of Home Affairs) public resource pages.
    i4c_advisory_url: str = "https://cybercrime.gov.in/Webform/Advisory.aspx"
    i4c_digest_url: str = "https://cybercrime.gov.in/Webform/daily-digest.aspx"

    model_config = SettingsConfigDict(
        # ".env" is read from the process working directory (backend/ when
        # uvicorn is started as documented); "../.env" covers a copy left at
        # the repository root by the README quick start.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()


def get_max_upload_bytes() -> int:
    return settings.max_upload_mb * 1024 * 1024


def get_allowed_origins() -> List[str]:
    """Parse ALLOWED_ORIGINS as a JSON array or a comma-separated list.

    A bare value such as ``http://localhost:5173`` is accepted too: pydantic
    refuses to coerce a plain string into ``List[str]``, which would otherwise
    stop the app from starting when the shipped ``.env.example`` is copied
    verbatim.
    """
    raw = (settings.allowed_origins or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(origin).strip() for origin in parsed if str(origin).strip()]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]