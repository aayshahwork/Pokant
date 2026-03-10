"""
api/middleware/logging.py — Structured request/response logging with structlog.

Logs: method, path, status_code, duration_ms, account_id, request_id.
NEVER logs: credentials, cookies_encrypted, raw API key values.
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger("api.access")

# Fields that must NEVER appear in logs
_SENSITIVE_FIELDS = frozenset({
    "credentials",
    "cookies_encrypted",
    "x-api-key",
    "authorization",
})


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Attach a request_id and log each request/response with structlog."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        account_id = getattr(request.state, "account_id", None)

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            account_id=str(account_id) if account_id else None,
            request_id=request_id,
        )

        response.headers["X-Request-ID"] = request_id
        return response
