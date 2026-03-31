"""Tests for new model fields — ActionType, StepData extensions, TaskResult extensions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from computeruse.models import ActionType, StepData, TaskConfig, TaskResult


# ===================================================================
# ActionType enum
# ===================================================================

class TestActionType:
    def test_is_str_enum(self) -> None:
        assert isinstance(ActionType.CLICK, str)
        assert ActionType.CLICK == "click"

    def test_all_values(self) -> None:
        expected = {
            "navigate", "click", "type", "scroll", "extract", "wait",
            "inject_credentials", "solve_captcha", "unknown",
            "mouse_move", "key_press", "double_click", "right_click",
            "middle_click", "screenshot", "drag", "triple_click", "zoom",
        }
        actual = {m.value for m in ActionType}
        assert actual == expected

    def test_count(self) -> None:
        assert len(ActionType) == 18

    def test_string_comparison(self) -> None:
        assert ActionType.NAVIGATE == "navigate"
        assert "click" == ActionType.CLICK

    def test_usable_in_sets(self) -> None:
        s = {ActionType.CLICK, ActionType.TYPE, "click"}
        assert len(s) == 2  # "click" and ActionType.CLICK are the same


# ===================================================================
# StepData — new fields and defaults
# ===================================================================

class TestStepDataDefaults:
    def test_minimal_construction(self) -> None:
        """Only step_number and timestamp are required."""
        step = StepData(
            step_number=1,
            timestamp=datetime.now(timezone.utc),
        )
        assert step.action_type == "unknown"
        assert step.description == ""
        assert step.screenshot_path == ""
        assert step.success is True
        assert step.error is None
        assert step.dom_snapshot is None
        assert step.screenshot_bytes is None
        assert step.tokens_in == 0
        assert step.tokens_out == 0
        assert step.duration_ms == 0
        assert step.reasoning is None

    def test_all_fields(self) -> None:
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        step = StepData(
            step_number=5,
            timestamp=ts,
            action_type="click",
            description="Clicked login",
            screenshot_path="/tmp/step5.png",
            dom_snapshot="<html>...</html>",
            success=False,
            error="Element obscured",
            screenshot_bytes=b"\xff\xd8jpeg",
            tokens_in=1200,
            tokens_out=300,
            duration_ms=1500,
            reasoning="Need to click login to proceed",
        )
        assert step.step_number == 5
        assert step.action_type == "click"
        assert step.screenshot_bytes == b"\xff\xd8jpeg"
        assert step.tokens_in == 1200
        assert step.tokens_out == 300
        assert step.duration_ms == 1500
        assert step.reasoning == "Need to click login to proceed"
        assert step.success is False
        assert step.error == "Element obscured"

    def test_step_number_ge_1(self) -> None:
        with pytest.raises(Exception):
            StepData(step_number=0, timestamp=datetime.now(timezone.utc))

    def test_negative_step_number(self) -> None:
        with pytest.raises(Exception):
            StepData(step_number=-1, timestamp=datetime.now(timezone.utc))

    def test_action_type_accepts_enum(self) -> None:
        step = StepData(
            step_number=1,
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.NAVIGATE,
        )
        assert step.action_type == "navigate"


class TestStepDataSerialization:
    def test_screenshot_bytes_excluded_from_model_dump(self) -> None:
        step = StepData(
            step_number=1,
            timestamp=datetime.now(timezone.utc),
            screenshot_bytes=b"\xff\xd8fake-screenshot",
        )
        d = step.model_dump()
        assert "screenshot_bytes" not in d

    def test_screenshot_bytes_still_accessible(self) -> None:
        img = b"\xff\xd8fake"
        step = StepData(
            step_number=1,
            timestamp=datetime.now(timezone.utc),
            screenshot_bytes=img,
        )
        assert step.screenshot_bytes == img

    def test_model_dump_includes_new_fields(self) -> None:
        step = StepData(
            step_number=1,
            timestamp=datetime.now(timezone.utc),
            tokens_in=500,
            tokens_out=100,
            duration_ms=800,
            reasoning="test reasoning",
        )
        d = step.model_dump()
        assert d["tokens_in"] == 500
        assert d["tokens_out"] == 100
        assert d["duration_ms"] == 800
        assert d["reasoning"] == "test reasoning"

    def test_model_dump_json_excludes_bytes(self) -> None:
        step = StepData(
            step_number=1,
            timestamp=datetime.now(timezone.utc),
            screenshot_bytes=b"data",
        )
        j = step.model_dump_json()
        parsed = json.loads(j)
        assert "screenshot_bytes" not in parsed


# ===================================================================
# TaskResult — new fields
# ===================================================================

def _make_result(**overrides: Any) -> TaskResult:
    defaults = {
        "task_id": "task-001",
        "status": "completed",
        "success": True,
        "result": {"title": "Example"},
        "steps": 3,
        "duration_ms": 5000,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "completed_at": datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return TaskResult(**defaults)


class TestTaskResultNewFields:
    def test_default_values(self) -> None:
        r = _make_result()
        assert r.cost_cents == 0.0
        assert r.total_tokens_in == 0
        assert r.total_tokens_out == 0
        assert r.error_category is None
        assert r.step_data == []

    def test_with_cost_data(self) -> None:
        r = _make_result(
            cost_cents=12.5,
            total_tokens_in=50000,
            total_tokens_out=10000,
        )
        assert r.cost_cents == 12.5
        assert r.total_tokens_in == 50000
        assert r.total_tokens_out == 10000

    def test_with_error_category(self) -> None:
        r = _make_result(
            success=False,
            error="rate limited",
            error_category="rate_limited",
        )
        assert r.error_category == "rate_limited"

    def test_with_step_data_list(self) -> None:
        steps = [
            StepData(step_number=1, timestamp=datetime.now(timezone.utc),
                     action_type="click", tokens_in=100, tokens_out=50),
            StepData(step_number=2, timestamp=datetime.now(timezone.utc),
                     action_type="type", tokens_in=200, tokens_out=80),
        ]
        r = _make_result(step_data=steps)
        assert len(r.step_data) == 2
        assert r.step_data[0].tokens_in == 100
        assert r.step_data[1].action_type == "type"


class TestTaskResultSerializationWithNewFields:
    def test_to_dict_includes_new_fields(self) -> None:
        r = _make_result(
            cost_cents=5.25,
            total_tokens_in=3000,
            total_tokens_out=600,
            error_category="transient_llm",
        )
        d = r.to_dict()
        assert d["cost_cents"] == 5.25
        assert d["total_tokens_in"] == 3000
        assert d["total_tokens_out"] == 600
        assert d["error_category"] == "transient_llm"

    def test_to_dict_step_data_pydantic_serialized(self) -> None:
        steps = [
            StepData(step_number=1, timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                     action_type="click", tokens_in=100),
        ]
        r = _make_result(step_data=steps)
        d = r.to_dict()
        assert isinstance(d["step_data"], list)
        assert len(d["step_data"]) == 1
        assert isinstance(d["step_data"][0], dict)
        assert d["step_data"][0]["step_number"] == 1
        assert d["step_data"][0]["tokens_in"] == 100
        # screenshot_bytes excluded from Pydantic model_dump
        assert "screenshot_bytes" not in d["step_data"][0]

    def test_to_json_round_trip_with_new_fields(self) -> None:
        r = _make_result(
            cost_cents=7.5,
            total_tokens_in=10000,
            total_tokens_out=2000,
            error_category="transient_network",
        )
        j = r.to_json()
        restored = TaskResult.from_json(j)
        assert restored.cost_cents == 7.5
        assert restored.total_tokens_in == 10000
        assert restored.total_tokens_out == 2000
        assert restored.error_category == "transient_network"

    def test_from_dict_with_new_fields(self) -> None:
        d = {
            "task_id": "t-1",
            "status": "completed",
            "success": True,
            "cost_cents": 3.14,
            "total_tokens_in": 5000,
            "total_tokens_out": 1000,
            "error_category": "rate_limited",
            "step_data": [],
        }
        r = TaskResult.from_dict(d)
        assert r.cost_cents == 3.14
        assert r.total_tokens_in == 5000
        assert r.error_category == "rate_limited"

    def test_from_dict_ignores_unknown_keys(self) -> None:
        d = {
            "task_id": "t-1",
            "status": "completed",
            "success": True,
            "unknown_field": "should be ignored",
            "another_unknown": 42,
        }
        r = TaskResult.from_dict(d)
        assert r.task_id == "t-1"
        assert not hasattr(r, "unknown_field")

    def test_from_dict_missing_new_fields_uses_defaults(self) -> None:
        """Old serialized data without new fields still deserializes."""
        d = {
            "task_id": "t-old",
            "status": "completed",
            "success": True,
        }
        r = TaskResult.from_dict(d)
        assert r.cost_cents == 0.0
        assert r.total_tokens_in == 0
        assert r.error_category is None
        assert r.step_data == []


# ===================================================================
# Integration: classify → retry → cost pipeline
# ===================================================================

class TestCrossModuleIntegration:
    def test_error_classifier_to_retry_policy(self) -> None:
        from computeruse.error_classifier import classify_error
        from computeruse.retry_policy import should_retry_task

        exc = ConnectionError("Connection refused")
        classified = classify_error(exc)
        decision = should_retry_task(
            error_category=classified.category,
            retry_count=0,
            max_retries=3,
        )
        assert classified.category == "transient_network"
        assert decision.should_retry is True

    def test_cost_from_step_data(self) -> None:
        from computeruse.cost import calculate_cost_from_steps

        steps = [
            StepData(step_number=1, timestamp=datetime.now(timezone.utc),
                     tokens_in=1000, tokens_out=200),
            StepData(step_number=2, timestamp=datetime.now(timezone.utc),
                     tokens_in=2000, tokens_out=500),
        ]
        cost = calculate_cost_from_steps(steps)
        assert cost > 0

    def test_stuck_detector_with_sdk_step_data(self) -> None:
        from computeruse.stuck_detector import StuckDetector

        det = StuckDetector(failure_threshold=3)
        steps = [
            StepData(step_number=i, timestamp=datetime.now(timezone.utc),
                     success=False, error="timeout")
            for i in range(1, 4)
        ]
        sig = det.analyze_full_history(steps)
        assert sig.detected
        assert sig.reason == "failure_spiral"

    def test_replay_generator_with_sdk_step_data(self) -> None:
        import tempfile
        from computeruse.replay_generator import ReplayGenerator

        steps = [
            StepData(step_number=1, timestamp=datetime.now(timezone.utc),
                     action_type="navigate", description="Go to page",
                     screenshot_bytes=b"\xff\xd8jpeg-data", tokens_in=500, tokens_out=100,
                     duration_ms=1200),
        ]
        gen = ReplayGenerator(steps=steps, task_metadata={"task_id": "integ-1"})
        with tempfile.TemporaryDirectory() as tmpdir:
            path = gen.generate(f"{tmpdir}/replay.html")
            assert path.endswith("replay.html")

    def test_full_task_result_with_all_new_fields(self) -> None:
        """Build a TaskResult with step_data, cost, error_category and round-trip it."""
        from computeruse.cost import calculate_cost_from_steps

        steps = [
            StepData(step_number=1, timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
                     action_type="navigate", tokens_in=800, tokens_out=200),
            StepData(step_number=2, timestamp=datetime(2025, 6, 1, 0, 0, 1, tzinfo=timezone.utc),
                     action_type="click", tokens_in=600, tokens_out=150,
                     success=False, error="Element not visible"),
        ]
        cost = calculate_cost_from_steps(steps)

        result = TaskResult(
            task_id="full-test",
            status="failed",
            success=False,
            error="Element not visible",
            steps=2,
            duration_ms=3500,
            cost_cents=cost,
            total_tokens_in=1400,
            total_tokens_out=350,
            error_category="permanent_browser",
            step_data=steps,
        )

        # Round-trip through JSON
        j = result.to_json()
        restored = TaskResult.from_json(j)

        assert restored.task_id == "full-test"
        assert restored.cost_cents == cost
        assert restored.total_tokens_in == 1400
        assert restored.total_tokens_out == 350
        assert restored.error_category == "permanent_browser"
        # step_data comes back as list of dicts (not StepData instances) after JSON round-trip
        assert len(restored.step_data) == 2
        assert restored.step_data[0]["action_type"] == "navigate"
        assert restored.step_data[1]["error"] == "Element not visible"
