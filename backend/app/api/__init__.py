from .health import router as health_router
from .scans import router as scans_router

__all__ = ["health_router", "scans_router"]