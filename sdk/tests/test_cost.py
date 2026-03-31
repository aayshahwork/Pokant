"""Tests for computeruse.cost — token cost calculation."""

from types import SimpleNamespace

from computeruse.cost import (
    COST_PER_M_INPUT,
    COST_PER_M_OUTPUT,
    calculate_cost_cents,
    calculate_cost_from_steps,
)


class TestCalculateCostCents:
    def test_zero_tokens(self):
        assert calculate_cost_cents(0, 0) == 0.0

    def test_input_only(self):
        # 1M input tokens at $3/M = $3 = 300 cents
        result = calculate_cost_cents(1_000_000, 0)
        assert result == round(COST_PER_M_INPUT * 100, 4)

    def test_output_only(self):
        # 1M output tokens at $15/M = $15 = 1500 cents
        result = calculate_cost_cents(0, 1_000_000)
        assert result == round(COST_PER_M_OUTPUT * 100, 4)

    def test_mixed_tokens(self):
        # 500K in + 100K out = $1.5 + $1.5 = $3 = 300 cents
        result = calculate_cost_cents(500_000, 100_000)
        expected = round(
            (500_000 * COST_PER_M_INPUT + 100_000 * COST_PER_M_OUTPUT) / 1_000_000 * 100,
            4,
        )
        assert result == expected

    def test_small_token_count(self):
        # 1000 in + 500 out
        result = calculate_cost_cents(1000, 500)
        expected = round(
            (1000 * COST_PER_M_INPUT + 500 * COST_PER_M_OUTPUT) / 1_000_000 * 100,
            4,
        )
        assert result == expected


class TestCalculateCostFromSteps:
    def test_empty_steps(self):
        assert calculate_cost_from_steps([]) == 0.0

    def test_steps_with_tokens(self):
        steps = [
            SimpleNamespace(tokens_in=1000, tokens_out=200),
            SimpleNamespace(tokens_in=2000, tokens_out=300),
        ]
        result = calculate_cost_from_steps(steps)
        assert result == calculate_cost_cents(3000, 500)

    def test_steps_missing_token_attrs(self):
        steps = [SimpleNamespace(), SimpleNamespace()]
        assert calculate_cost_from_steps(steps) == 0.0

    def test_mixed_steps(self):
        steps = [
            SimpleNamespace(tokens_in=1000, tokens_out=100),
            SimpleNamespace(),  # missing attrs, defaults to 0
        ]
        result = calculate_cost_from_steps(steps)
        assert result == calculate_cost_cents(1000, 100)
