"""Tests for workers/retry_policy.py and _maybe_auto_retry in workers/tasks.py."""

import uuid
from unittest.mock import MagicMock, patch

from workers.retry_policy import (
    MAX_DELAY_SECONDS,
    RetryDecision,
    should_retry_task,
)


# ---------------------------------------------------------------------------
# should_retry_task — pure logic tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _maybe_auto_retry — integration tests with mocked DB + Celery
# ---------------------------------------------------------------------------


def _mock_task(**overrides):
    """Create a mock Task ORM object with sensible defaults."""
    task = MagicMock()
    task.id = overrides.get("id", uuid.uuid4())
    task.account_id = overrides.get("account_id", uuid.uuid4())
    task.url = overrides.get("url", "https://example.com")
    task.task_description = overrides.get("task_description", "test task")
    task.output_schema = overrides.get("output_schema", None)
    task.webhook_url = overrides.get("webhook_url", None)
    task.max_cost_cents = overrides.get("max_cost_cents", None)
    task.session_id = overrides.get("session_id", None)
    task.retry_count = overrides.get("retry_count", 0)
    task.retry_of_task_id = overrides.get("retry_of_task_id", None)
    task.error_category = overrides.get("error_category", None)
    return task


def _mock_account(tier="free"):
    account = MagicMock()
    account.tier = tier
    return account


_CONFIG = {
    "url": "https://example.com",
    "task": "test task",
    "retry_attempts": 3,
    "retry_delay_seconds": 2,
}


class TestMaybeAutoRetry:
    @patch("workers.tasks.celery_app")
    @patch("workers.db.get_sync_session")
    def test_transient_error_creates_retry(self, mock_get_session, mock_celery):
        from workers.tasks import _maybe_auto_retry

        task = _mock_task()
        account = _mock_account("startup")
        session = MagicMock()
        mock_get_session.return_value = session
        session.get.side_effect = [task, account]

        _maybe_auto_retry(str(task.id), "transient_llm", _CONFIG)

        # Should have added a new task and sent to Celery
        session.add.assert_called_once()
        mock_celery.send_task.assert_called_once()
        call_kwargs = mock_celery.send_task.call_args
        assert call_kwargs.kwargs["queue"] == "tasks:startup"

    @patch("workers.tasks.celery_app")
    @patch("workers.db.get_sync_session")
    def test_permanent_error_no_retry(self, mock_get_session, mock_celery):
        from workers.tasks import _maybe_auto_retry

        task = _mock_task()
        session = MagicMock()
        mock_get_session.return_value = session
        session.get.return_value = task

        _maybe_auto_retry(str(task.id), "permanent_llm", _CONFIG)

        # Should NOT create a new task
        session.add.assert_not_called()
        mock_celery.send_task.assert_not_called()

    @patch("workers.tasks.celery_app")
    @patch("workers.db.get_sync_session")
    def test_sets_error_category_even_without_retry(
        self, mock_get_session, mock_celery
    ):
        from workers.tasks import _maybe_auto_retry

        task = _mock_task()
        session = MagicMock()
        mock_get_session.return_value = session
        session.get.return_value = task

        _maybe_auto_retry(str(task.id), "permanent_llm", _CONFIG)

        assert task.error_category == "permanent_llm"
        session.commit.assert_called()

    @patch("workers.tasks.celery_app")
    @patch("workers.db.get_sync_session")
    def test_max_retries_reached_no_retry(self, mock_get_session, mock_celery):
        from workers.tasks import _maybe_auto_retry

        task = _mock_task(retry_count=3)
        session = MagicMock()
        mock_get_session.return_value = session
        session.get.return_value = task

        _maybe_auto_retry(str(task.id), "transient_llm", _CONFIG)

        session.add.assert_not_called()
        mock_celery.send_task.assert_not_called()

    @patch("workers.tasks.celery_app")
    @patch("workers.db.get_sync_session")
    def test_flat_retry_chain(self, mock_get_session, mock_celery):
        """retry_of_task_id should point to the root, not the immediate parent."""
        from workers.tasks import _maybe_auto_retry

        root_id = uuid.uuid4()
        task = _mock_task(retry_of_task_id=root_id, retry_count=1)
        account = _mock_account()
        session = MagicMock()
        mock_get_session.return_value = session
        session.get.side_effect = [task, account]

        _maybe_auto_retry(str(task.id), "transient_llm", _CONFIG)

        new_task = session.add.call_args[0][0]
        assert new_task.retry_of_task_id == root_id
        assert new_task.retry_count == 2

    @patch("workers.tasks.celery_app")
    @patch("workers.db.get_sync_session")
    def test_countdown_from_retry_after(self, mock_get_session, mock_celery):
        from workers.tasks import _maybe_auto_retry

        task = _mock_task()
        account = _mock_account()
        session = MagicMock()
        mock_get_session.return_value = session
        session.get.side_effect = [task, account]

        _maybe_auto_retry(
            str(task.id), "rate_limited", _CONFIG, retry_after_seconds=90
        )

        call_kwargs = mock_celery.send_task.call_args
        assert call_kwargs.kwargs["countdown"] == 90
