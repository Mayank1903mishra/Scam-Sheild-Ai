from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import uuid


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    errors = exc.errors()
    msg = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "VALIDATION_ERROR", "message": msg}},
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": exc.detail}},
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the exception server-side (stack trace only; the request body is
    # never logged) so 500s are debuggable without leaking content to clients.
    import logging
    logging.getLogger("app.errors").error("unhandled exception", exc_info=exc)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}},
    )