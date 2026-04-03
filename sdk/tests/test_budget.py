"""Tests for computeruse.budget — cost circuit breaker."""

from __future__ import annotations

import time

import pytest

from computeruse.budget import BudgetExceededError, BudgetMonitor


def test_tracking() -> None:
    """Record 5 costs, verify total."""
    m = BudgetMonitor()
    for _ in range(5):
        m.record_cost_direct(2.0)
    assert m.total_cost_cents == 10.0
    assert len(m._step_costs) == 5


def test_exceeded() -> None:
    """Set max=10, record 12 -> BudgetExceededError."""
    m = BudgetMonitor(max_cost_cents=10)
    m.record_cost_direct(5.0)
    m.record_cost_direct(5.0)
    with pytest.raises(BudgetExceededError) as exc_info:
        m.record_cost_direct(2.0)
    assert exc_info.value.accumulated == 12.0
    assert exc_info.value.limit == 10.0


def test_no_limit() -> None:
    """max=None -> never raises."""
    m = BudgetMonitor()
    for _ in range(100):
        m.record_cost_direct(100.0)
    assert m.total_cost_cents == 10_000.0


def test_spend_rate() -> None:
    """Record costs with time.sleep, verify rate > 0."""
    m = BudgetMonitor()
    m.record_cost_direct(10.0)
    time.sleep(0.1)
    rate = m.spend_rate_cents_per_minute
    assert rate > 0


def test_anomaly_spike() -> None:
    """Normal costs + one 10x spike -> warning string."""
    m = BudgetMonitor()
    for _ in range(10):
        m.record_cost_direct(1.0)
    m.record_cost_direct(200.0)
    warning = m.check_anomaly()
    assert warning is not None
    assert "spike" in warning.lower()


def test_anomaly_threshold() -> None:
    """80% of budget -> warning string."""
    m = BudgetMonitor(max_cost_cents=100)
    m.record_cost_direct(85.0)
    warning = m.check_anomaly()
    assert warning is not None
    assert "threshold" in warning.lower() or "budget" in warning.lower()


def test_projected_cost() -> None:
    """Verify projection math."""
    m = BudgetMonitor()
    m.record_cost_direct(10.0)
    m.record_cost_direct(20.0)
    # avg = 30/2 = 15, remaining 3 steps -> 30 + 15*3 = 75
    projected = m.projected_cost(3)
    assert projected == 75.0
