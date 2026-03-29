from __future__ import annotations

from typing import Any, Dict, Optional


class ComputerUseSDKError(Exception):
    """Base exception for all computeruse SDK errors.

    All SDK-specific exceptions inherit from this class, so callers can
    catch ``ComputerUseSDKError`` to handle any SDK failure in one place.
    """

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        self.message = message
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the exception to a JSON-compatible dict."""
        return {
            "error": type(self).__name__,
            "message": self.message,
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}(message={self.message!r})"


# Backward-compatible alias
ComputerUseError = ComputerUseSDKError


class TaskExecutionError(ComputerUseSDKError):
    """Raised when a browser automation task fails during execution.

    This covers failures that occur after the task has started — for example
    the model getting stuck, an unexpected page state, or an unrecoverable
    mid-task error that is not a timeout or retry exhaustion.
    """

    def __init__(self, message: str = "Task execution failed") -> None:
        super().__init__(message)


class BrowserError(ComputerUseSDKError):
    """Raised when a browser-level operation fails.

    Examples include failure to launch the browser, inability to open a new
    page, navigation errors, or crashes inside the Playwright/browser process.
    """

    def __init__(self, message: str = "A browser error occurred") -> None:
        super().__init__(message)


class ValidationError(ComputerUseSDKError):
    """Raised when the task output does not match the expected schema.

    Thrown by the validator after task completion when the extracted result
    is missing required fields or contains values of the wrong type, as
    defined by ``TaskConfig.output_schema``.
    """

    def __init__(self, message: str = "Output validation failed") -> None:
        super().__init__(message)


class AuthenticationError(ComputerUseSDKError):
    """Raised when login or credential injection fails.

    Thrown when the SDK detects that provided credentials were rejected by
    the target site, a login form could not be located, or the session is
    no longer authenticated mid-task.
    """

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message)


class TaskTimeoutError(ComputerUseSDKError):
    """Raised when a task exceeds its configured wall-clock timeout.

    Thrown when execution time surpasses ``TaskConfig.timeout_seconds``,
    regardless of how many steps have been completed.
    """

    def __init__(self, message: str = "Task exceeded the configured timeout") -> None:
        super().__init__(message)


# Backward-compatible alias
TimeoutError = TaskTimeoutError


class RateLimitError(ComputerUseSDKError):
    """Raised when a rate limit is exceeded.

    Carries ``retry_after_seconds`` so callers know how long to wait
    before retrying.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after_seconds: Optional[float] = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base["retry_after_seconds"] = self.retry_after_seconds
        return base

    def __repr__(self) -> str:
        return f"{type(self).__name__}(message={self.message!r}, " f"retry_after_seconds={self.retry_after_seconds!r})"


class NetworkError(ComputerUseSDKError):
    """Raised when a network-level operation fails.

    Covers connection errors, DNS resolution failures, and other transport
    issues that prevent the SDK from reaching a remote service.
    """

    def __init__(self, message: str = "Network error occurred") -> None:
        super().__init__(message)


class ServiceUnavailableError(ComputerUseSDKError):
    """Raised when a remote service is temporarily unavailable.

    Typically corresponds to HTTP 503 responses or similar transient
    service outages.
    """

    def __init__(self, message: str = "Service is temporarily unavailable") -> None:
        super().__init__(message)


class RetryExhaustedError(ComputerUseSDKError):
    """Raised when all retry attempts have been consumed without success.

    Thrown after the retry loop exhausts ``TaskConfig.retry_attempts``
    consecutive failures. The ``last_error`` attribute preserves the
    underlying exception that triggered the final attempt.
    """

    def __init__(
        self,
        message: str = "Maximum retry attempts reached",
        last_error: Optional[Exception] = None,
    ) -> None:
        self.last_error = last_error
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base["last_error"] = str(self.last_error) if self.last_error else None
        return base

    def __repr__(self) -> str:
        return f"{type(self).__name__}(message={self.message!r}, " f"last_error={self.last_error!r})"


class SessionError(ComputerUseSDKError):
    """Raised when browser session management fails.

    Covers errors during session save, load, restoration, or expiry — for
    example a corrupt session file, an expired session that cannot be
    refreshed, or a mismatch between the stored domain and the active page.
    """

    def __init__(self, message: str = "Session management failed") -> None:
        super().__init__(message)


class APIError(ComputerUseSDKError):
    """Raised when a cloud API call returns an error response.

    Carries the HTTP ``status_code`` and the raw ``response`` body so
    callers can inspect the upstream error without re-parsing it.
    """

    def __init__(
        self,
        message: str = "API request failed",
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.status_code = status_code
        self.response = response
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base["status_code"] = self.status_code
        base["response"] = self.response
        return base

    def __repr__(self) -> str:
        return f"{type(self).__name__}(message={self.message!r}, " f"status_code={self.status_code!r})"
