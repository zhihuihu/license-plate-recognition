from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger("license_plate.errors")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error_code(status_code: int) -> str:
    return {
        400: "INVALID_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        413: "PAYLOAD_TOO_LARGE",
        422: "RECOGNITION_FAILED",
        429: "TOO_MANY_REQUESTS",
        503: "SERVICE_UNAVAILABLE",
    }.get(status_code, "HTTP_ERROR")


def error_payload(request: Request, status_code: int, message: str) -> dict:
    return {
        "code": status_code,
        "message": message,
        "data": {
            "error_code": _error_code(status_code),
            "request_id": _request_id(request),
        },
    }


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "请求失败"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(request, exc.status_code, message),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, _: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(request, 422, "请求参数校验失败"),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error request_id=%s", _request_id(request), exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=error_payload(request, 500, "服务内部错误"),
    )
