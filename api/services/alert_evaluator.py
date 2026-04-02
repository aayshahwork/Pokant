"""
api/services/alert_evaluator.py -- Server-side aggregate alert detection.

Evaluates newly ingested/completed tasks for anomaly patterns:
  - Success rate drop (<70% over the last hour, minimum 5 tasks)
  - Cost spike (single task > 100 cents / $1.00)
  - Repeated failures (3+ failures on the same URL in the last hour)

Usage::

    evaluator = AlertEvaluator(db)
    alerts = await evaluator.evaluate(task)
    if alerts:
        await db.commit()
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.alert import Alert
from api.models.task import Task

logger = structlog.get_logger("api.alerts")

# ---------------------------------------------------------------------------
# Thresholds (could be made configurable per-account in the future)
# ---------------------------------------------------------------------------

SUCCESS_RATE_THRESHOLD = 0.70  # alert if success rate drops below 70%
SUCCESS_RATE_MIN_TASKS = 5     # minimum tasks in window to evaluate
COST_SPIKE_CENTS = 100         # alert if single task exceeds $1.00
REPEATED_FAILURE_COUNT = 3     # alert if same URL fails 3+ times
LOOKBACK_HOURS = 1             # evaluation window


class AlertEvaluator:
    """Evaluate a task for aggregate alert conditions.

    Adds Alert objects to the session but does NOT commit -- the caller
    is responsible for committing the transaction.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    _TERMINAL_STATUSES = frozenset({"completed", "failed", "timeout", "cancelled"})

    async def evaluate(self, task: Task) -> list[Alert]:
        """Evaluate alert conditions after a task completes or fails.

        Returns the list of Alert ORM objects that were added to the
        session.  May return an empty list.  Only evaluates tasks in
        terminal statuses.
        """
        if task.status not in self._TERMINAL_STATUSES:
            return []

        alerts: list[Alert] = []

        alerts.extend(await self._check_cost_spike(task))

        if task.status == "failed":
            alerts.extend(await self._check_repeated_failures(task))

        alerts.extend(await self._check_success_rate(task))

        return alerts

    # -- Detection rules ---------------------------------------------------

    async def _check_success_rate(self, task: Task) -> list[Alert]:
        """Alert if success rate in the last hour is below threshold."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

        # Count total and failed tasks in the window
        total_stmt = (
            select(func.count())
            .select_from(Task)
            .where(Task.account_id == task.account_id)
            .where(Task.created_at >= cutoff)
            .where(Task.status.in_(("completed", "failed")))
        )
        total = (await self._db.execute(total_stmt)).scalar() or 0

        if total < SUCCESS_RATE_MIN_TASKS:
            return []

        failed_stmt = (
            select(func.count())
            .select_from(Task)
            .where(Task.account_id == task.account_id)
            .where(Task.created_at >= cutoff)
            .where(Task.status == "failed")
        )
        failed = (await self._db.execute(failed_stmt)).scalar() or 0

        success_rate = (total - failed) / total
        if success_rate >= SUCCESS_RATE_THRESHOLD:
            return []

        # Dedup: check if we already raised this alert in the last hour
        if await self._recent_alert_exists(
            task.account_id, "success_rate_drop", cutoff
        ):
            return []

        alert = Alert(
            id=uuid.uuid4(),
            account_id=task.account_id,
            alert_type="success_rate_drop",
            message=(
                f"Success rate dropped to {success_rate:.0%} over the last hour "
                f"({failed}/{total} tasks failed)"
            ),
            task_id=task.id,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(alert)
        return [alert]

    async def _check_cost_spike(self, task: Task) -> list[Alert]:
        """Alert if a single task cost exceeds the threshold."""
        cost = float(task.cost_cents or 0)
        if cost <= COST_SPIKE_CENTS:
            return []

        # Dedup: limit to one cost_spike alert per account per hour
        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
        if await self._recent_alert_exists(
            task.account_id, "cost_spike", cutoff
        ):
            return []

        alert = Alert(
            id=uuid.uuid4(),
            account_id=task.account_id,
            alert_type="cost_spike",
            message=f"Task cost {cost:.1f} cents (threshold: {COST_SPIKE_CENTS} cents)",
            task_id=task.id,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(alert)
        return [alert]

    async def _check_repeated_failures(self, task: Task) -> list[Alert]:
        """Alert if the same URL has failed 3+ times in the last hour."""
        if not task.url:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

        count_stmt = (
            select(func.count())
            .select_from(Task)
            .where(Task.account_id == task.account_id)
            .where(Task.url == task.url)
            .where(Task.status == "failed")
            .where(Task.created_at >= cutoff)
        )
        count = (await self._db.execute(count_stmt)).scalar() or 0

        if count < REPEATED_FAILURE_COUNT:
            return []

        # Dedup: check if we already raised this alert recently
        if await self._recent_alert_exists(
            task.account_id, "repeated_failure", cutoff
        ):
            return []

        alert = Alert(
            id=uuid.uuid4(),
            account_id=task.account_id,
            alert_type="repeated_failure",
            message=f"{count} failures on {task.url} in the last hour",
            task_id=task.id,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(alert)
        return [alert]

    # -- Helpers -----------------------------------------------------------

    async def _recent_alert_exists(
        self,
        account_id: uuid.UUID,
        alert_type: str,
        since: datetime,
    ) -> bool:
        """Check if an alert of the given type already exists since *since*."""
        stmt = (
            select(func.count())
            .select_from(Alert)
            .where(Alert.account_id == account_id)
            .where(Alert.alert_type == alert_type)
            .where(Alert.created_at >= since)
        )
        count = (await self._db.execute(stmt)).scalar() or 0
        return count > 0
