"""
Global error handling for FastAPI.
"""

import logging
import traceback

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings

logger = logging.getLogger(__name__)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "details": errors,
        },
    )


async def database_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Handle database errors."""
    logger.error("Database error: %s", exc)

    settings = get_settings()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Database Error",
            "message": "An error occurred while accessing the database",
            "detail": str(exc) if settings.debug else None,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other exceptions."""
    logger.error("Unhandled exception: %s", exc)
    logger.error(traceback.format_exc())

    settings = get_settings()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.debug else None,
        },
    )
