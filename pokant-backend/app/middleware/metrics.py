"""
Request metrics for monitoring (Prometheus-style).

Optional: install prometheus_client for /metrics endpoint.
"""

import time

from fastapi import Request

# Optional Prometheus metrics (graceful if not installed)
try:
    from prometheus_client import Counter, Histogram, generate_latest

    request_count = Counter(
        "pokant_requests_total",
        "Total requests",
        ["method", "endpoint", "status"],
    )
    request_duration = Histogram(
        "pokant_request_duration_seconds",
        "Request duration",
        ["method", "endpoint"],
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    request_count = None
    request_duration = None
    generate_latest = None


async def track_metrics(request: Request, call_next):
    """Track request count and duration."""
    if not PROMETHEUS_AVAILABLE:
        return await call_next(request)

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Normalize path for cardinality (e.g. /api/patterns/123 -> /api/patterns/{id})
    path = request.url.path
    if path.startswith("/api/patterns/") and len(path) > 14:
        path = "/api/patterns/{id}"
    elif path.startswith("/api/dashboard/") and len(path) > 15:
        path = "/api/dashboard/{id}"
    elif path.startswith("/api/variants/") and len(path) > 14:
        path = "/api/variants/{id}"

    request_count.labels(
        method=request.method,
        endpoint=path,
        status=response.status_code,
    ).inc()
    request_duration.labels(method=request.method, endpoint=path).observe(duration)

    return response


def get_metrics_content():
    """Return Prometheus text format for /metrics."""
    if PROMETHEUS_AVAILABLE and generate_latest is not None:
        return generate_latest()
    return b"# Prometheus client not installed\n"
