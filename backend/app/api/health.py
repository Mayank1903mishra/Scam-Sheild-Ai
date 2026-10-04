from fastapi import APIRouter, Depends
from app.schemas.response import HealthResponse
from app.config import settings


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    mode = "demo" if settings.demo_mode else "rules"
    return HealthResponse(status="ok", mode=mode)