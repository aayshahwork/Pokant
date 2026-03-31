"""
computeruse/retry_policy.py — Retry decision logic for failed tasks.

Determines whether a task should be automatically retried based on
error category, current retry count, and configured limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RetryDecision:
    """Result of a retry policy evaluation."""

    should_retry: bool
    delay_seconds: int = 0
    reason: str = ""


RETRIABLE_CATEGORIES = frozenset({
    "transient_llm",
    "rate_limited",
    "transient_network",
    "transient_browser",
})

# Maximum backoff delay (5 minutes)
MAX_DELAY_SECONDS = 300


def should_retry_task(
    error_category: str,
    retry_count: int,
    max_retries: int = 3,
    base_delay: int = 2,
    retry_after_seconds: Optional[int] = None,
) -> RetryDecision:
    """Decide whether a failed task should be automatically retried.

    Args:
        error_category: Classification from error_classifier.
        retry_count: How many retries have already been attempted.
        max_retries: Maximum allowed retries.
        base_delay: Base delay in seconds for exponential backoff.
        retry_after_seconds: Server-suggested delay (e.g., from Retry-After header).

    Returns:
        RetryDecision with should_retry, delay, and reason.
    """
    if error_category not in RETRIABLE_CATEGORIES:
        return RetryDecision(
            should_retry=False,
            reason=f"Error category '{error_category}' is not retriable",
        )

    if retry_count >= max_retries:
        return RetryDecision(
            should_retry=False,
            reason=f"Retry limit reached ({retry_count}/{max_retries})",
        )

    # Calculate delay: use server hint or exponential backoff
    if retry_after_seconds is not None and retry_after_seconds > 0:
        delay = retry_after_seconds
    else:
        delay = base_delay * (2 ** retry_count)

    delay = min(delay, MAX_DELAY_SECONDS)

    return RetryDecision(
        should_retry=True,
        delay_seconds=delay,
        reason=f"Transient error, retry {retry_count + 1}/{max_retries}",
    )
