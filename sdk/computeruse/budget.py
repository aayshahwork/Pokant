"""computeruse/budget.py — Cost circuit breaker for task execution.

Tracks accumulated costs and enforces budget limits to prevent
runaway spending (the "$47K recursive loop" scenario).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .cost import calculate_cost_cents


class BudgetExceededError(Exception):
    """Raised when a run exceeds its cost budget."""

    def __init__(self, accumulated: float, limit: float) -> None:
        self.accumulated = accumulated
        self.limit = limit
        super().__init__(f"Budget exceeded: {accumulated:.2f}\u00a2 > {limit:.2f}\u00a2")


@dataclass
class BudgetMonitor:
    """Tracks accumulated costs and enforces budget limits.

    Used by both wrap() and ReplayExecutor.
    Person A will instantiate this in wrap.py and call record_step_cost()
    in _on_step_end.
    """

    max_cost_cents: float | None = None
    alert_threshold: float = 0.8  # Warn at 80% of budget

    _accumulated_cents: float = field(default=0.0, init=False)
    _step_costs: list[float] = field(default_factory=list, init=False)
    _start_time: float = field(default_factory=time.monotonic, init=False)
    _alerted: bool = field(default=False, init=False)

    def record_step_cost(self, tokens_in: int, tokens_out: int) -> float:
        """Record cost of a step. Returns step cost in cents.

        Raises BudgetExceededError if budget exceeded.
        """
        cost = calculate_cost_cents(tokens_in, tokens_out)
        self._step_costs.append(cost)
        self._accumulated_cents += cost
        self._check_budget()
        return cost

    def record_cost_direct(self, cost_cents: float) -> None:
        """Record a known cost. Raises BudgetExceededError if exceeded."""
        self._step_costs.append(cost_cents)
        self._accumulated_cents += cost_cents
        self._check_budget()

    @property
    def total_cost_cents(self) -> float:
        """Total accumulated cost in cents."""
        return self._accumulated_cents

    @property
    def spend_rate_cents_per_minute(self) -> float:
        """Current spend rate in cents per minute."""
        elapsed_minutes = (time.monotonic() - self._start_time) / 60.0
        if elapsed_minutes <= 0:
            return 0.0
        return self._accumulated_cents / elapsed_minutes

    def projected_cost(self, remaining_steps: int) -> float:
        """Project total cost based on average step cost."""
        if not self._step_costs:
            return self._accumulated_cents
        avg = self._accumulated_cents / len(self._step_costs)
        return self._accumulated_cents + avg * remaining_steps

    def check_anomaly(self, baseline_rate: float = 0.0) -> str | None:
        """Check for spend rate anomalies.

        Returns warning string if:
        - Spend rate > 5x baseline_rate
        - Total cost > alert_threshold * max_cost_cents
        - Any step cost > 10x average step cost (leave-one-out)

        Returns the FIRST anomaly found, or None.
        """
        # Check 1: Spend rate vs baseline
        if baseline_rate > 0:
            current_rate = self.spend_rate_cents_per_minute
            if current_rate > 5 * baseline_rate:
                return (
                    f"Spend rate anomaly: {current_rate:.2f}\u00a2/min "
                    f"is >5x baseline {baseline_rate:.2f}\u00a2/min"
                )

        # Check 2: Approaching budget threshold
        if self.max_cost_cents is not None and self.max_cost_cents > 0:
            if self._accumulated_cents > self.alert_threshold * self.max_cost_cents:
                return (
                    f"Budget threshold: {self._accumulated_cents:.2f}\u00a2 "
                    f"> {self.alert_threshold * 100:.0f}% of "
                    f"{self.max_cost_cents:.2f}\u00a2 limit"
                )

        # Check 3: Step cost spike (leave-one-out average)
        if len(self._step_costs) >= 2:
            total = self._accumulated_cents
            n = len(self._step_costs)
            for cost in self._step_costs:
                avg_others = (total - cost) / (n - 1)
                if avg_others > 0 and cost > 10 * avg_others:
                    return (
                        f"Step cost spike: {cost:.2f}\u00a2 "
                        f"is >10x average {avg_others:.2f}\u00a2"
                    )

        return None

    def _check_budget(self) -> None:
        """Raise BudgetExceededError if budget is exceeded."""
        if (
            self.max_cost_cents is not None
            and self._accumulated_cents > self.max_cost_cents
        ):
            raise BudgetExceededError(self._accumulated_cents, self.max_cost_cents)
