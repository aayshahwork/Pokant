"""
tests/integration/test_queue.py — Integration tests for Celery task queue wiring.

Tests:
- Atomic claim (duplicate prevention)
- Redis distributed lock
- Tier-based queue routing
- Visibility timeout config
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def task_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_config_json():
    return json.dumps({
        "url": "https://example.com",
        "task": "Click the login button",
        "max_steps": 50,
        "timeout_seconds": 120,
    })


# ---------------------------------------------------------------------------
# Duplicate Prevention
# ---------------------------------------------------------------------------


class TestDuplicatePrevention:
    """Verify that the atomic UPDATE … WHERE status='queued' guard works."""

    @patch("workers.tasks._redis")
    @patch("workers.db.get_sync_session")
    def test_already_claimed_task_skips_execution(
        self, mock_get_session, mock_redis, task_id, sample_config_json
    ):
        """If UPDATE affects 0 rows, the task was already claimed — skip."""
        session = MagicMock()
        mock_get_session.return_value = session

        # 0 rows affected = task already running
        result = MagicMock()
        result.rowcount = 0
        session.execute.return_value = result

        from workers.tasks import execute_task

        # Use Celery's apply() to run synchronously with proper request context
        execute_task.apply(args=[task_id, sample_config_json])

        # Should commit the claim attempt
        session.commit.assert_called_once()
        # Should NOT proceed to lock (redis.lock never called)
        mock_redis.lock.assert_not_called()

    @patch("workers.tasks._redis")
    @patch("workers.db.get_sync_session")
    def test_claimed_task_proceeds_to_lock(
        self, mock_get_session, mock_redis, task_id, sample_config_json
    ):
        """If UPDATE affects 1 row, task was claimed — proceed to Redis lock."""
        session = MagicMock()
        mock_get_session.return_value = session

        # 1 row affected = claim successful
        result = MagicMock()
        result.rowcount = 1
        session.execute.return_value = result

        # Lock acquisition fails so we stop early
        lock = MagicMock()
        lock.acquire.return_value = False
        mock_redis.lock.return_value = lock

        from workers.tasks import execute_task

        execute_task.apply(args=[task_id, sample_config_json])

        # Should have attempted the lock
        mock_redis.lock.assert_called_once()

    @patch("workers.tasks._redis")
    @patch("workers.db.get_sync_session")
    def test_two_workers_only_one_claims(
        self, mock_get_session, mock_redis, sample_config_json
    ):
        """Simulate two workers trying the same task — only one should proceed."""
        session = MagicMock()
        mock_get_session.return_value = session

        task_id = str(uuid.uuid4())
        call_count = 0

        def simulate_claim(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            # First caller claims, second gets 0 rows
            result.rowcount = 1 if call_count == 1 else 0
            return result

        session.execute.side_effect = simulate_claim

        # Lock fails so we don't need executor mocks
        lock = MagicMock()
        lock.acquire.return_value = False
        mock_redis.lock.return_value = lock

        from workers.tasks import execute_task

        # Worker 1 — claims the task
        execute_task.apply(args=[task_id, sample_config_json])
        assert mock_redis.lock.call_count == 1  # Proceeded to lock

        mock_redis.reset_mock()

        # Worker 2 — gets 0 rows
        execute_task.apply(args=[task_id, sample_config_json])
        assert mock_redis.lock.call_count == 0  # Skipped


# ---------------------------------------------------------------------------
# Redis Lock
# ---------------------------------------------------------------------------


class TestRedisLock:
    """Verify Redis distributed lock behaviour."""

    @patch("workers.tasks._redis")
    @patch("workers.db.get_sync_session")
    def test_lock_ttl_is_timeout_plus_60(
        self, mock_get_session, mock_redis, task_id
    ):
        """Lock TTL should be timeout_seconds + 60."""
        session = MagicMock()
        mock_get_session.return_value = session
        result = MagicMock()
        result.rowcount = 1
        session.execute.return_value = result

        lock = MagicMock()
        lock.acquire.return_value = False  # Fail early
        mock_redis.lock.return_value = lock

        config = json.dumps({
            "url": "https://example.com",
            "task": "test",
            "timeout_seconds": 300,
        })

        from workers.tasks import execute_task

        execute_task.apply(args=[task_id, config])

        mock_redis.lock.assert_called_with(f"task_lock:{task_id}", timeout=360)

    @patch("workers.tasks._redis")
    @patch("workers.db.get_sync_session")
    def test_lock_held_skips_execution(
        self, mock_get_session, mock_redis, task_id, sample_config_json
    ):
        """If the lock is already held, the task should skip execution."""
        session = MagicMock()
        mock_get_session.return_value = session
        result = MagicMock()
        result.rowcount = 1
        session.execute.return_value = result

        lock = MagicMock()
        lock.acquire.return_value = False
        mock_redis.lock.return_value = lock

        from workers.tasks import execute_task

        execute_task.apply(args=[task_id, sample_config_json])

        # Lock acquire was attempted but failed — no executor should run
        lock.acquire.assert_called_once_with(blocking=False)

    @patch("workers.tasks._persist_failure")
    @patch("workers.tasks._redis")
    @patch("workers.db.get_sync_session")
    def test_lock_released_in_finally(
        self, mock_get_session, mock_redis, mock_persist_failure, task_id, sample_config_json
    ):
        """Lock should be released even if execution fails."""
        session = MagicMock()
        mock_get_session.return_value = session
        result = MagicMock()
        result.rowcount = 1
        session.execute.return_value = result

        lock = MagicMock()
        lock.acquire.return_value = True
        mock_redis.lock.return_value = lock

        from workers.tasks import execute_task

        # Patch the source module so the local import inside execute_task gets the mock
        with patch("workers.executor.TaskExecutor", side_effect=RuntimeError("boom")):
            execute_task.apply(args=[task_id, sample_config_json])

        lock.release.assert_called_once()


# ---------------------------------------------------------------------------
# Visibility Timeout
# ---------------------------------------------------------------------------


class TestVisibilityTimeout:
    """Verify broker_transport_options.visibility_timeout is configured."""

    def test_visibility_timeout_set_to_900(self):
        """Global visibility timeout should be 900s (enterprise max + buffer)."""
        from workers.main import celery_app

        transport_opts = celery_app.conf.get("broker_transport_options", {})
        assert transport_opts.get("visibility_timeout") == 900

    def test_three_tier_queues_configured(self):
        """All three tier queues should be registered."""
        from workers.main import celery_app

        queues = celery_app.conf.get("task_queues", [])
        queue_names = {q.name for q in queues}
        assert {"tasks:free", "tasks:startup", "tasks:enterprise"} == queue_names

    def test_default_queue_is_free(self):
        """Default queue should be tasks:free."""
        from workers.main import celery_app

        assert celery_app.conf.get("task_default_queue") == "tasks:free"
