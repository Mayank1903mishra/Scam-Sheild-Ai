from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
import uuid
import time
import logging

from app.config import settings, get_allowed_origins, get_max_upload_bytes
from app.api import health_router, scans_router
from app.exceptions import (
    AppError,
    app_error_handler,
    validation_error_handler,
    http_error_handler,
    generic_error_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.db import init_db


limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    init_db()
    yield


app = FastAPI(
    title="ScamShield AI API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Multipart bodies are parsed before the endpoint runs, so oversized uploads
# are rejected here first, before any file buffering. This middleware is
# added before CORS and request-id so both wrap it (its responses still get
# CORS headers and an X-Request-ID).
UPLOAD_PATH = "/api/v1/scans/upload"
MULTIPART_OVERHEAD_BYTES = 64 * 1024


@app.middleware("http")
async def enforce_upload_size_limit(request: Request, call_next):
    if request.method == "POST" and request.url.path == UPLOAD_PATH:
        content_length = request.headers.get("content-length", "")
        if content_length.isdigit():
            limit = get_max_upload_bytes() + MULTIPART_OVERHEAD_BYTES
            if int(content_length) > limit:
                return JSONResponse(
                    status_code=413,
                    content={"error": {
                        "code": "FILE_TOO_LARGE",
                        "message": f"Upload exceeds the {settings.max_upload_mb} MB limit",
                    }},
                )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id_and_logging(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    logging.getLogger("app.access").info(
        f"request_id={request_id} method={request.method} path={request.url.path} "
        f"status={response.status_code} duration_ms={int(duration * 1000)}"
    )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(health_router, prefix="/api/v1")
app.include_router(scans_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"name": "ScamShield AI API", "version": "0.1.0", "docs": "/docs"}