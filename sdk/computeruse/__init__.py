"""
ComputerUse SDK - One API to automate any web workflow

Example:
    from computeruse import ComputerUse

    cu = ComputerUse()
    result = cu.run_task(
        url="https://example.com",
        task="Extract the page title",
        output_schema={"title": "str"}
    )

    print(result.result["title"])
"""

from computeruse.client import ComputerUse
from computeruse.exceptions import (
    APIError,
    AuthenticationError,
    BrowserError,
    ComputerUseError,
    ComputerUseSDKError,
    NetworkError,
    RateLimitError,
    RetryExhaustedError,
    ServiceUnavailableError,
    SessionError,
    TaskExecutionError,
    TaskTimeoutError,
    TimeoutError,
    ValidationError,
)
from computeruse.models import TaskConfig, TaskResult

__version__ = "0.1.0"

__all__ = [
    # Client
    "ComputerUse",
    # Models
    "TaskConfig",
    "TaskResult",
    # Exceptions (primary names)
    "ComputerUseSDKError",
    "TaskExecutionError",
    "BrowserError",
    "ValidationError",
    "AuthenticationError",
    "TaskTimeoutError",
    "RateLimitError",
    "NetworkError",
    "ServiceUnavailableError",
    "RetryExhaustedError",
    "SessionError",
    "APIError",
    # Backward-compatible aliases
    "ComputerUseError",
    "TimeoutError",
    # Metadata
    "__version__",
]
