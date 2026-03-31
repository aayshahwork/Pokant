"""
computeruse/cost.py — Token cost calculation utilities.

Claude Sonnet pricing constants and helper functions for estimating
the dollar cost of a task run from token counts.
"""

from __future__ import annotations

from typing import Any, Sequence

# Claude Sonnet pricing (per million tokens) as of 2025.
COST_PER_M_INPUT = 3.00
COST_PER_M_OUTPUT = 15.00


def calculate_cost_cents(total_tokens_in: int, total_tokens_out: int) -> float:
    """Calculate cost in US cents from token counts.

    Args:
        total_tokens_in: Total input tokens consumed.
        total_tokens_out: Total output tokens produced.

    Returns:
        Cost in US cents, rounded to 4 decimal places.
    """
    dollars = (
        total_tokens_in * COST_PER_M_INPUT + total_tokens_out * COST_PER_M_OUTPUT
    ) / 1_000_000
    return round(dollars * 100, 4)


def calculate_cost_from_steps(steps: Sequence[Any]) -> float:
    """Calculate total cost in cents from a sequence of step objects.

    Each step is inspected via ``getattr`` for ``tokens_in`` and
    ``tokens_out`` attributes, defaulting to 0 if absent.

    Args:
        steps: Sequence of step objects (e.g. StepData instances).

    Returns:
        Cost in US cents, rounded to 4 decimal places.
    """
    total_in = sum(getattr(s, "tokens_in", 0) for s in steps)
    total_out = sum(getattr(s, "tokens_out", 0) for s in steps)
    return calculate_cost_cents(total_in, total_out)
