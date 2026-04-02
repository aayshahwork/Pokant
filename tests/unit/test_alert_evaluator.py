"""Tests for AlertEvaluator — server-side aggregate alert detection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.alert_evaluator import (
    COST_SPIKE_CENTS,
    AlertEvaluator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    status: str = "completed",
    cost_cents: float = 5.0,
    url: str = "https://example.com",
    account_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    """Create a minimal Task-like object for testing."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        account_id=account_id or uuid.uuid4(),
        status=status,
        cost_cents=Decimal(str(cost_cents)),
        url=url,
        created_at=datetime.now(timezone.utc),
    )


def _mock_db_scalars(*values: int | None) -> AsyncMock:
    """Create a mock db session that returns *values* from successive execute calls."""
    db = AsyncMock()
    results = []
    for v in values:
        result = MagicMock()
        result.scalar.return_value = v
        results.append(result)
    db.execute = AsyncMock(side_effect=results)
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAlertEvaluator:

    async def test_success_rate_alert(self) -> None:
        """Alert generated when success rate drops below threshold."""
        account_id = uuid.uuid4()
        task = _make_task(status="completed", account_id=account_id)

        # Query order for status="completed", cost=5:
        # 1. _check_cost_spike: cost < 100, skips (no query)
        # 2. _check_repeated_failures: skipped (status != "failed")
        # 3. _check_success_rate: total = 10
        # 4. _check_success_rate: failed = 5 (50% success)
        # 5. _check_success_rate: dedup = 0
        db = _mock_db_scalars(10, 5, 0)

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.alert_type == "success_rate_drop"
        assert alert.account_id == account_id
        assert "50%" in alert.message
        db.add.assert_called_once()

    async def test_success_rate_no_alert_when_above_threshold(self) -> None:
        """No alert when success rate is above threshold."""
        task = _make_task(status="completed")

        # _check_success_rate: total=10, failed=2 (80% -- above 70%)
        db = _mock_db_scalars(10, 2)

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        assert len(alerts) == 0
        db.add.assert_not_called()

    async def test_success_rate_no_alert_below_min_tasks(self) -> None:
        """No alert when total tasks < minimum."""
        task = _make_task(status="completed")

        # _check_success_rate: total=3 (below min of 5)
        db = _mock_db_scalars(3)

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        assert len(alerts) == 0
        db.add.assert_not_called()

    async def test_cost_spike_alert(self) -> None:
        """Alert generated when single task cost exceeds threshold."""
        account_id = uuid.uuid4()
        task = _make_task(
            status="completed",
            cost_cents=150.0,
            account_id=account_id,
        )

        # Query order for cost=150 (> threshold):
        # 1. _check_cost_spike: dedup = 0 (no existing cost_spike alert)
        # 2. _check_success_rate: total=2 (below min)
        db = _mock_db_scalars(0, 2)

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.alert_type == "cost_spike"
        assert alert.account_id == account_id
        assert "150.0 cents" in alert.message

    async def test_cost_spike_dedup(self) -> None:
        """No duplicate cost_spike when one already exists."""
        task = _make_task(status="completed", cost_cents=200.0)

        # 1. _check_cost_spike: dedup = 1 (already alerted)
        # 2. _check_success_rate: total=2 (below min)
        db = _mock_db_scalars(1, 2)

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        assert len(alerts) == 0
        db.add.assert_not_called()

    async def test_cost_spike_no_alert_below_threshold(self) -> None:
        """No cost alert when cost is within limits."""
        task = _make_task(status="completed", cost_cents=50.0)

        # _check_success_rate: total=2 (below min)
        db = _mock_db_scalars(2)

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        assert len(alerts) == 0
        db.add.assert_not_called()

    async def test_repeated_failure_alert(self) -> None:
        """Alert generated on 3+ failures for same URL."""
        account_id = uuid.uuid4()
        task = _make_task(
            status="failed",
            url="https://example.com/login",
            account_id=account_id,
        )

        # Query order for status="failed", cost=5:
        # 1. _check_cost_spike: cost < 100, skips
        # 2. _check_repeated_failures: count = 4
        # 3. _check_repeated_failures: dedup = 0
        # 4. _check_success_rate: total = 3 (below min)
        db = _mock_db_scalars(4, 0, 3)

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.alert_type == "repeated_failure"
        assert "example.com/login" in alert.message

    async def test_repeated_failure_dedup(self) -> None:
        """No duplicate alert when one already exists within the hour."""
        task = _make_task(status="failed", url="https://example.com/login")

        # 1. _check_repeated_failures: count = 5
        # 2. _check_repeated_failures: dedup = 1 (already alerted)
        # 3. _check_success_rate: total = 3 (below min)
        db = _mock_db_scalars(5, 1, 3)

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        assert len(alerts) == 0
        db.add.assert_not_called()

    async def test_no_alert_below_thresholds(self) -> None:
        """No alerts when all metrics are within normal range."""
        task = _make_task(status="completed", cost_cents=5.0)

        # _check_success_rate: total=10, failed=1 (90% -- above threshold)
        db = _mock_db_scalars(10, 1)

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        assert len(alerts) == 0
        db.add.assert_not_called()

    async def test_non_terminal_status_skipped(self) -> None:
        """No evaluation for non-terminal task statuses."""
        task = _make_task(status="running", cost_cents=500.0)
        db = _mock_db_scalars()  # no queries expected

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        assert len(alerts) == 0
        db.execute.assert_not_awaited()
        db.add.assert_not_called()

    async def test_multiple_alerts(self) -> None:
        """Multiple alert types can fire for a single task."""
        account_id = uuid.uuid4()
        task = _make_task(
            status="failed",
            cost_cents=200.0,
            url="https://example.com/expensive",
            account_id=account_id,
        )

        # Query order for status="failed", cost=200:
        # 1. _check_cost_spike: dedup = 0 (fires)
        # 2. _check_repeated_failures: count = 3
        # 3. _check_repeated_failures: dedup = 0 (fires)
        # 4. _check_success_rate: total = 10
        # 5. _check_success_rate: failed = 5 (50%)
        # 6. _check_success_rate: dedup = 0 (fires)
        db = _mock_db_scalars(0, 3, 0, 10, 5, 0)

        evaluator = AlertEvaluator(db)
        alerts = await evaluator.evaluate(task)

        types = {a.alert_type for a in alerts}
        assert "cost_spike" in types
        assert "repeated_failure" in types
        assert "success_rate_drop" in types
        assert len(alerts) == 3
