"""Tests for computeruse.retry_policy — retry decision logic."""

from computeruse.retry_policy import (
    MAX_DELAY_SECONDS,
    RetryDecision,
    should_retry_task,
)


class TestShouldRetryTask:
    def test_transient_llm_first_retry(self):
        decision = should_retry_task(
            error_category="transient_llm",
            retry_count=0,
            max_retries=3,
            base_delay=2,
        )
        assert decision.should_retry is True
        assert decision.delay_seconds == 2  # 2 * 2^0

    def test_transient_llm_second_retry(self):
        decision = should_retry_task(
            error_category="transient_llm",
            retry_count=1,
            max_retries=3,
            base_delay=2,
        )
        assert decision.should_retry is True
        assert decision.delay_seconds == 4  # 2 * 2^1

    def test_transient_llm_third_retry(self):
        decision = should_retry_task(
            error_category="transient_llm",
            retry_count=2,
            max_retries=3,
            base_delay=2,
        )
        assert decision.should_retry is True
        assert decision.delay_seconds == 8  # 2 * 2^2

    def test_rate_limited_retriable(self):
        decision = should_retry_task(
            error_category="rate_limited", retry_count=0, max_retries=3
        )
        assert decision.should_retry is True

    def test_transient_network_retriable(self):
        decision = should_retry_task(
            error_category="transient_network", retry_count=0, max_retries=3
        )
        assert decision.should_retry is True

    def test_transient_browser_retriable(self):
        decision = should_retry_task(
            error_category="transient_browser", retry_count=0, max_retries=3
        )
        assert decision.should_retry is True

    def test_permanent_llm_not_retriable(self):
        decision = should_retry_task(
            error_category="permanent_llm", retry_count=0, max_retries=3
        )
        assert decision.should_retry is False
        assert "not retriable" in decision.reason

    def test_permanent_browser_not_retriable(self):
        decision = should_retry_task(
            error_category="permanent_browser", retry_count=0, max_retries=3
        )
        assert decision.should_retry is False

    def test_unknown_not_retriable(self):
        decision = should_retry_task(
            error_category="unknown", retry_count=0, max_retries=3
        )
        assert decision.should_retry is False

    def test_retry_limit_reached(self):
        decision = should_retry_task(
            error_category="transient_llm", retry_count=3, max_retries=3
        )
        assert decision.should_retry is False
        assert "limit reached" in decision.reason.lower()

    def test_retry_limit_exceeded(self):
        decision = should_retry_task(
            error_category="transient_llm", retry_count=5, max_retries=3
        )
        assert decision.should_retry is False

    def test_server_hint_overrides_backoff(self):
        decision = should_retry_task(
            error_category="rate_limited",
            retry_count=0,
            max_retries=3,
            base_delay=2,
            retry_after_seconds=120,
        )
        assert decision.should_retry is True
        assert decision.delay_seconds == 120

    def test_delay_capped_at_max(self):
        decision = should_retry_task(
            error_category="transient_llm",
            retry_count=10,
            max_retries=20,
            base_delay=100,
        )
        assert decision.should_retry is True
        assert decision.delay_seconds == MAX_DELAY_SECONDS

    def test_server_hint_capped_at_max(self):
        decision = should_retry_task(
            error_category="rate_limited",
            retry_count=0,
            max_retries=3,
            retry_after_seconds=600,
        )
        assert decision.delay_seconds == MAX_DELAY_SECONDS

    def test_zero_max_retries(self):
        decision = should_retry_task(
            error_category="transient_llm", retry_count=0, max_retries=0
        )
        assert decision.should_retry is False

    def test_exponential_backoff_sequence(self):
        delays = []
        for i in range(5):
            d = should_retry_task(
                error_category="transient_llm",
                retry_count=i,
                max_retries=10,
                base_delay=2,
            )
            delays.append(d.delay_seconds)
        assert delays == [2, 4, 8, 16, 32]
