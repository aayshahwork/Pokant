import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.middleware.error_handler import (
    database_exception_handler,
    generic_exception_handler,
    validation_exception_handler,
)
from app.middleware.metrics import get_metrics_content, track_metrics
from app.middleware.request_logger import log_requests
from app.routers import dashboard, onboarding, patterns, tests, variants
from fastapi.exceptions import RequestValidationError

# Logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            "logs/pokant.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Pokant API",
    description="Voice AI optimization platform backend",
    version="0.1.0",
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(track_metrics)
app.middleware("http")(log_requests)

app.include_router(onboarding.router, prefix="/api", tags=["onboarding"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(patterns.router, prefix="/api", tags=["patterns"])
app.include_router(variants.router, prefix="/api", tags=["variants"])
app.include_router(tests.router, prefix="/api", tags=["tests"])


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check: database and optional Redis.
    Returns 503 if database is unhealthy.
    """
    checks = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": {},
    }

    try:
        db.execute(text("SELECT 1"))
        checks["checks"]["database"] = "healthy"
    except Exception as e:
        checks["checks"]["database"] = f"unhealthy: {str(e)}"
        checks["status"] = "unhealthy"

    try:
        from redis import Redis
        r = Redis.from_url(settings.redis_url)
        r.ping()
        checks["checks"]["redis"] = "healthy"
    except Exception as e:
        checks["checks"]["redis"] = f"unhealthy: {str(e)}"
        if checks["status"] == "healthy":
            checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)


@app.get("/metrics")
async def metrics():
    """Prometheus metrics (if prometheus_client installed)."""
    return Response(
        content=get_metrics_content(),
        media_type="text/plain; charset=utf-8",
    )
