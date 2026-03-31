"""
computeruse/error_classifier.py — Classify task execution errors into categories.

Categories determine whether a failed task is eligible for automatic retry.
Does NOT import heavy dependencies (anthropic, playwright) — inspects class
names and status codes via duck-typing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class ErrorCategory:
    """Error categories for task failure classification."""

    TRANSIENT_LLM = "transient_llm"
    RATE_LIMITED = "rate_limited"
    TRANSIENT_NETWORK = "transient_network"
    TRANSIENT_BROWSER = "transient_browser"
    PERMANENT_LLM = "permanent_llm"
    PERMANENT_BROWSER = "permanent_browser"
    PERMANENT_TASK = "permanent_task"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifiedError:
    """Result of error classification."""

    category: str
    retriable: bool
    retry_after_seconds: Optional[int] = None
    original_message: str = ""


def classify_error(exc: Exception) -> ClassifiedError:
    """Classify an exception into an error category.

    Inspects the exception's class name, module, status code, and message
    without importing the originating library.
    """
    class_name = type(exc).__name__
    module = getattr(type(exc), "__module__", "") or ""
    message = str(exc)
    status_code = _extract_status_code(exc)
    retry_after = _extract_retry_after(exc)

    # -- Anthropic / LLM API errors ----------------------------------------
    if _is_llm_error(class_name, module):
        if class_name == "RateLimitError" or status_code == 429:
            return ClassifiedError(
                category=ErrorCategory.RATE_LIMITED,
                retriable=True,
                retry_after_seconds=retry_after or 60,
                original_message=message,
            )
        if status_code in (500, 502, 503, 529):
            return ClassifiedError(
                category=ErrorCategory.TRANSIENT_LLM,
                retriable=True,
                retry_after_seconds=retry_after,
                original_message=message,
            )
        if status_code in (400, 401, 403):
            return ClassifiedError(
                category=ErrorCategory.PERMANENT_LLM,
                retriable=False,
                original_message=message,
            )
        if class_name in ("APIConnectionError", "APITimeoutError"):
            return ClassifiedError(
                category=ErrorCategory.TRANSIENT_LLM,
                retriable=True,
                original_message=message,
            )

    # -- Browser / Playwright errors ---------------------------------------
    if _is_browser_error(class_name, module):
        if _is_transient_browser_message(message):
            return ClassifiedError(
                category=ErrorCategory.TRANSIENT_BROWSER,
                retriable=True,
                original_message=message,
            )
        return ClassifiedError(
            category=ErrorCategory.PERMANENT_BROWSER,
            retriable=False,
            original_message=message,
        )

    # -- Network errors ----------------------------------------------------
    if _is_network_error(class_name, message):
        return ClassifiedError(
            category=ErrorCategory.TRANSIENT_NETWORK,
            retriable=True,
            original_message=message,
        )

    # -- Fallback to message-based classification --------------------------
    return classify_error_message(message)


def classify_error_message(error_str: str) -> ClassifiedError:
    """Classify from an error message string when no exception object is available."""
    lower = error_str.lower()

    # LLM transient
    if any(p in lower for p in ("overloaded", "529", "502 ", "503 ", "internal server error")):
        return ClassifiedError(
            category=ErrorCategory.TRANSIENT_LLM,
            retriable=True,
            original_message=error_str,
        )

    # Rate limited
    if "429" in lower or "rate limit" in lower:
        return ClassifiedError(
            category=ErrorCategory.RATE_LIMITED,
            retriable=True,
            retry_after_seconds=60,
            original_message=error_str,
        )

    # Permanent LLM
    if any(p in lower for p in ("401 ", "403 ", "authentication", "invalid api key", "invalid_api_key")):
        return ClassifiedError(
            category=ErrorCategory.PERMANENT_LLM,
            retriable=False,
            original_message=error_str,
        )

    # Browser (checked before network so "playwright timeout" isn't caught by generic "timeout")
    if any(p in lower for p in ("browser", "playwright", "cdp", "page crash")):
        if any(p in lower for p in ("timeout", "navigation failed")):
            return ClassifiedError(
                category=ErrorCategory.TRANSIENT_BROWSER,
                retriable=True,
                original_message=error_str,
            )
        return ClassifiedError(
            category=ErrorCategory.PERMANENT_BROWSER,
            retriable=False,
            original_message=error_str,
        )

    # Network (after browser so "playwright timeout" doesn't match here)
    if any(p in lower for p in ("timeout", "connection refused", "connection reset", "dns resolution")):
        return ClassifiedError(
            category=ErrorCategory.TRANSIENT_NETWORK,
            retriable=True,
            original_message=error_str,
        )

    return ClassifiedError(
        category=ErrorCategory.UNKNOWN,
        retriable=False,
        original_message=error_str,
    )


# -- Helpers ---------------------------------------------------------------


def _is_llm_error(class_name: str, module: str) -> bool:
    return "anthropic" in module.lower() or class_name in (
        "APIError",
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
        "APIStatusError",
        "AuthenticationError",
        "BadRequestError",
        "PermissionDeniedError",
    )


def _is_browser_error(class_name: str, module: str) -> bool:
    return "playwright" in module.lower() or "browser" in class_name.lower()


def _is_transient_browser_message(message: str) -> bool:
    lower = message.lower()
    return any(
        p in lower
        for p in ("timeout", "navigation", "target closed", "session closed", "connection closed")
    )


def _is_network_error(class_name: str, message: str) -> bool:
    if class_name in (
        "ConnectionError",
        "TimeoutError",
        "OSError",
        "ConnectionRefusedError",
        "ConnectionResetError",
    ):
        return True
    lower = message.lower()
    return any(p in lower for p in ("connection refused", "connection reset", "dns resolution"))


def _extract_status_code(exc: Exception) -> Optional[int]:
    """Extract HTTP status code from exception via duck-typing."""
    if hasattr(exc, "status_code"):
        try:
            return int(exc.status_code)
        except (ValueError, TypeError):
            pass
    response = getattr(exc, "response", None)
    if response is not None and hasattr(response, "status_code"):
        try:
            return int(response.status_code)
        except (ValueError, TypeError):
            pass
    return None


def _extract_retry_after(exc: Exception) -> Optional[int]:
    """Extract Retry-After header value from exception."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    retry_after = headers.get("retry-after") or headers.get("Retry-After")
    if retry_after is not None:
        try:
            return int(retry_after)
        except (ValueError, TypeError):
            pass
    return None
