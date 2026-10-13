from fastapi import APIRouter, Depends
from app.schemas.response import HealthResponse
from app.config import settings


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    if settings.demo_mode:
        mode = "demo"
    else:
        try:
            from app.services.ml_classifier import get_ml_classifier
            mode = "rules+ml" if get_ml_classifier().is_available() else "rules"
        except Exception:
            mode = "rules"
    return HealthResponse(status="ok", mode=mode)