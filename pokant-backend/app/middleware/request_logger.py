"""
Request logging middleware.
"""

import logging
import time

from fastapi import Request

logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next):
    """Log all API requests and response status/duration."""
    start_time = time.time()

    logger.info("→ %s %s", request.method, request.url.path)

    response = await call_next(request)

    duration = time.time() - start_time
    logger.info(
        "← %s %s status=%s duration=%.2fs",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    return response
