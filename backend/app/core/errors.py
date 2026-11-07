"""Uniform structured error envelope: {"error": {code, message, details, request_id}}"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import log, request_id_ctx


class EpochError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: Any = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if status_code:
            self.status_code = status_code


class ValidationError(EpochError):
    status_code = 422
    code = "validation_error"


class NotFoundError(EpochError):
    status_code = 404
    code = "not_found"


class RateLimitError(EpochError):
    status_code = 429
    code = "rate_limited"


class ProviderError(EpochError):
    status_code = 502
    code = "provider_error"


class UnsafeURLError(EpochError):
    status_code = 400
    code = "unsafe_url"


def _envelope(code: str, message: str, details: Any, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id_ctx.get(),
            }
        },
    )


def install_error_handlers(app) -> None:
    @app.exception_handler(EpochError)
    async def _epoch(request: Request, exc: EpochError):
        if exc.status_code >= 500:
            log.error("epoch_error", extra={"event": exc.code, "extra_data": exc.message})
        return _envelope(exc.code, exc.message, exc.details, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return _envelope("validation_error", "Request validation failed.", exc.errors(), 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return _envelope("http_error", str(exc.detail), None, exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled_exception")
        return _envelope("internal_error", "Unexpected server error.", None, 500)
