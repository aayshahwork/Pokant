"""Edge-case tests across all SDK reliability modules."""

from __future__ import annotations

import base64
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from computeruse.cost import calculate_cost_cents, calculate_cost_from_steps
from computeruse.error_classifier import (
    ClassifiedError,
    ErrorCategory,
    classify_error,
    classify_error_message,
)
from computeruse.models import ActionType, StepData, TaskResult
from computeruse.replay_generator import ReplayGenerator
from computeruse.retry_policy import (
    MAX_DELAY_SECONDS,
    RETRIABLE_CATEGORIES,
    RetryDecision,
    should_retry_task,
)
from computeruse.stuck_detector import StuckDetector, StuckSignal


# ===================================================================
# error_classifier edge cases
# ===================================================================


class TestClassifyErrorEdgeCases:
    def test_status_code_not_int(self) -> None:
        """status_code attribute that can't be converted to int."""

        class _Exc(Exception):
            __module__ = "anthropic._exceptions"
            status_code = "not-a-number"

        result = classify_error(_Exc("bad"))
        # Falls through to message-based classification
        assert result.category == ErrorCategory.UNKNOWN

    def test_response_status_code_not_int(self) -> None:
        """response.status_code that can't be converted to int."""

        class _Exc(Exception):
            __module__ = "anthropic._exceptions"

        exc = _Exc("err")
        exc.response = SimpleNamespace(status_code="NaN")
        result = classify_error(exc)
        assert result.category == ErrorCategory.UNKNOWN

    def test_retry_after_header_not_int(self) -> None:
        """Retry-After header with non-integer value (e.g. HTTP date)."""

        class _Exc(Exception):
            __module__ = "anthropic._exceptions"
            status_code = 429

        exc = _Exc("rate limited")
        exc.response = SimpleNamespace(
            status_code=429,
            headers={"retry-after": "Thu, 01 Jan 2026 00:00:00 GMT"},
        )
        result = classify_error(exc)
        assert result.category == ErrorCategory.RATE_LIMITED
        # Falls back to default 60 since header isn't an int
        assert result.retry_after_seconds == 60

    def test_none_module(self) -> None:
        """Exception with __module__ = None."""

        class _Exc(Exception):
            __module__ = None  # type: ignore[assignment]

        result = classify_error(_Exc("something"))
        assert result.category == ErrorCategory.UNKNOWN

    def test_anthropic_error_unknown_status_code(self) -> None:
        """Anthropic exception with a non-standard status code (e.g. 418)."""

        class _Exc(Exception):
            __module__ = "anthropic._exceptions"
            status_code = 418

        result = classify_error(_Exc("I'm a teapot"))
        # Not matched by any specific status code rule — falls through to
        # message-based classification
        assert result.category == ErrorCategory.UNKNOWN

    def test_classified_error_frozen(self) -> None:
        ce = ClassifiedError(category="test", retriable=True)
        with pytest.raises(AttributeError):
            ce.category = "changed"  # type: ignore[misc]

    def test_class_names_handled_by_name_alone(self) -> None:
        """Class names that are classified without needing a status_code."""
        # These are matched by class_name checks inside _is_llm_error block
        name_to_category = {
            "RateLimitError": ErrorCategory.RATE_LIMITED,
            "APIConnectionError": ErrorCategory.TRANSIENT_LLM,
            "APITimeoutError": ErrorCategory.TRANSIENT_LLM,
        }
        for name, expected_cat in name_to_category.items():
            cls = type(name, (Exception,), {"__module__": "anthropic._exceptions"})
            result = classify_error(cls("test"))
            assert result.category == expected_cat, (
                f"{name} should map to {expected_cat}"
            )

    def test_llm_class_names_with_status_code(self) -> None:
        """Class names that require a status_code to be classified."""
        # These enter the _is_llm_error block but need a status_code
        names_needing_status = [
            "APIError", "InternalServerError", "APIStatusError",
            "AuthenticationError", "BadRequestError", "PermissionDeniedError",
        ]
        for name in names_needing_status:
            cls = type(name, (Exception,), {"__module__": "anthropic._exceptions"})
            exc = cls("test")
            exc.status_code = 500
            result = classify_error(exc)
            assert result.category == ErrorCategory.TRANSIENT_LLM, (
                f"{name} with status 500 should be transient LLM"
            )

    def test_connection_refused_error(self) -> None:
        result = classify_error(ConnectionRefusedError("refused"))
        assert result.category == ErrorCategory.TRANSIENT_NETWORK

    def test_connection_reset_error(self) -> None:
        result = classify_error(ConnectionResetError("reset"))
        assert result.category == ErrorCategory.TRANSIENT_NETWORK

    def test_message_with_mixed_case(self) -> None:
        result = classify_error_message("RATE LIMIT exceeded")
        assert result.category == ErrorCategory.RATE_LIMITED

    def test_message_internal_server_error(self) -> None:
        result = classify_error_message("HTTP 500 Internal Server Error")
        assert result.category == ErrorCategory.TRANSIENT_LLM

    def test_message_403_permanent(self) -> None:
        result = classify_error_message("403 Forbidden: insufficient permissions")
        assert result.category == ErrorCategory.PERMANENT_LLM

    def test_message_dns_resolution(self) -> None:
        result = classify_error_message("dns resolution failed for api.example.com")
        assert result.category == ErrorCategory.TRANSIENT_NETWORK

    def test_message_cdp_permanent(self) -> None:
        result = classify_error_message("CDP protocol error: invalid selector")
        assert result.category == ErrorCategory.PERMANENT_BROWSER

    def test_message_playwright_navigation_failed(self) -> None:
        result = classify_error_message("Playwright browser navigation failed")
        assert result.category == ErrorCategory.TRANSIENT_BROWSER

    def test_exception_preserves_original_message(self) -> None:
        msg = "Specific error detail: code=42, context='login'"
        result = classify_error(ValueError(msg))
        assert result.original_message == msg

    def test_classify_error_message_preserves_original(self) -> None:
        msg = "Some detailed error text"
        result = classify_error_message(msg)
        assert result.original_message == msg


# ===================================================================
# retry_policy edge cases
# ===================================================================


class TestRetryPolicyEdgeCases:
    def test_retry_decision_frozen(self) -> None:
        d = RetryDecision(should_retry=True, delay_seconds=5, reason="test")
        with pytest.raises(AttributeError):
            d.should_retry = False  # type: ignore[misc]

    def test_all_retriable_categories(self) -> None:
        """Every category in RETRIABLE_CATEGORIES gets should_retry=True."""
        for cat in RETRIABLE_CATEGORIES:
            d = should_retry_task(error_category=cat, retry_count=0, max_retries=3)
            assert d.should_retry is True, f"{cat} should be retriable"

    def test_permanent_task_not_retriable(self) -> None:
        d = should_retry_task(
            error_category="permanent_task", retry_count=0, max_retries=3
        )
        assert d.should_retry is False

    def test_empty_string_category_not_retriable(self) -> None:
        d = should_retry_task(
            error_category="", retry_count=0, max_retries=3
        )
        assert d.should_retry is False

    def test_retry_after_zero_uses_backoff(self) -> None:
        d = should_retry_task(
            error_category="transient_llm",
            retry_count=0,
            max_retries=3,
            base_delay=5,
            retry_after_seconds=0,
        )
        assert d.delay_seconds == 5  # backoff, not 0

    def test_retry_after_negative_uses_backoff(self) -> None:
        d = should_retry_task(
            error_category="transient_llm",
            retry_count=0,
            max_retries=3,
            base_delay=5,
            retry_after_seconds=-10,
        )
        assert d.delay_seconds == 5  # backoff, not negative

    def test_very_large_retry_count_capped(self) -> None:
        """Exponential backoff with huge retry_count doesn't overflow — just caps."""
        d = should_retry_task(
            error_category="transient_llm",
            retry_count=50,
            max_retries=100,
            base_delay=2,
        )
        assert d.should_retry is True
        assert d.delay_seconds == MAX_DELAY_SECONDS

    def test_base_delay_zero(self) -> None:
        d = should_retry_task(
            error_category="transient_llm",
            retry_count=0,
            max_retries=3,
            base_delay=0,
        )
        assert d.should_retry is True
        assert d.delay_seconds == 0

    def test_reason_includes_retry_number(self) -> None:
        d = should_retry_task(
            error_category="transient_llm",
            retry_count=2,
            max_retries=5,
        )
        assert "3/5" in d.reason


# ===================================================================
# stuck_detector edge cases
# ===================================================================


class TestStuckDetectorEdgeCases:
    def test_base64_string_screenshot_hashed(self) -> None:
        """Real-time path: screenshot as base64 string (not bytes)."""
        det = StuckDetector(screenshot_threshold=2)
        b64_str = base64.b64encode(b"same-image").decode()
        step1 = SimpleNamespace(
            state=SimpleNamespace(screenshot=b64_str),
            model_output=None,
            result=None,
        )
        det.check_agent_step(step1)
        sig = det.check_agent_step(SimpleNamespace(
            state=SimpleNamespace(screenshot=b64_str),
            model_output=None,
            result=None,
        ))
        assert sig.detected
        assert sig.reason == "visual_stagnation"

    def test_empty_action_list(self) -> None:
        """model_output.action is empty list — should not crash."""
        det = StuckDetector()
        step = SimpleNamespace(
            state=None,
            model_output=SimpleNamespace(action=[]),
            result=None,
        )
        sig = det.check_agent_step(step)
        assert not sig.detected

    def test_non_list_result(self) -> None:
        """result is a single object, not a list."""
        det = StuckDetector(failure_threshold=2)
        step = SimpleNamespace(
            state=None,
            model_output=None,
            result=SimpleNamespace(error="single error"),
        )
        det.check_agent_step(step)
        sig = det.check_agent_step(SimpleNamespace(
            state=None, model_output=None,
            result=SimpleNamespace(error="another error"),
        ))
        assert sig.detected
        assert sig.reason == "failure_spiral"

    def test_action_not_list(self) -> None:
        """model_output.action is a single object, not a list."""
        det = StuckDetector(action_threshold=2)
        action_obj = type("ClickAction", (), {})()
        step = SimpleNamespace(
            state=None,
            model_output=SimpleNamespace(action=action_obj),
            result=None,
        )
        det.check_agent_step(step)
        sig = det.check_agent_step(SimpleNamespace(
            state=None,
            model_output=SimpleNamespace(action=type("ClickAction", (), {})()),
            result=None,
        ))
        assert sig.detected
        assert sig.reason == "action_repetition"

    def test_visual_stagnation_broken_by_different_image(self) -> None:
        """Three identical screenshots then one different — no detection at threshold=4."""
        det = StuckDetector(screenshot_threshold=4)
        same = b"same-img"
        for _ in range(3):
            det.check_agent_step(SimpleNamespace(
                state=SimpleNamespace(screenshot=same),
                model_output=None, result=None,
            ))
        sig = det.check_agent_step(SimpleNamespace(
            state=SimpleNamespace(screenshot=b"different"),
            model_output=None, result=None,
        ))
        assert not sig.detected

    def test_action_repetition_broken_by_different_action(self) -> None:
        """Four same actions then one different — no detection at threshold=5."""
        det = StuckDetector(action_threshold=5)
        for _ in range(4):
            det.check_agent_step(SimpleNamespace(
                state=None,
                model_output=SimpleNamespace(action=[type("ClickAction", (), {})()]),
                result=None,
            ))
        sig = det.check_agent_step(SimpleNamespace(
            state=None,
            model_output=SimpleNamespace(action=[type("TypeAction", (), {})()]),
            result=None,
        ))
        assert not sig.detected

    def test_failure_spiral_exactly_at_threshold(self) -> None:
        det = StuckDetector(failure_threshold=3)
        for _ in range(3):
            sig = det.check_agent_step(SimpleNamespace(
                state=None, model_output=None,
                result=[SimpleNamespace(error="err")],
            ))
        assert sig.detected

    def test_analyze_full_history_action_repetition_wins_over_failure(self) -> None:
        """When visual stagnation absent, action repetition checked before failure spiral."""
        det = StuckDetector(screenshot_threshold=100, action_threshold=3, failure_threshold=3)
        steps = [
            StepData(step_number=i, timestamp=datetime.now(timezone.utc),
                     action_type="click", success=False)
            for i in range(1, 4)
        ]
        sig = det.analyze_full_history(steps)
        assert sig.detected
        assert sig.reason == "action_repetition"

    def test_analyze_full_history_screenshot_none_resets_chain(self) -> None:
        """A None screenshot breaks the visual stagnation chain."""
        actions = ["click", "type", "scroll", "navigate", "extract"]
        det = StuckDetector(screenshot_threshold=3, action_threshold=100, failure_threshold=100)
        steps = [
            StepData(step_number=1, timestamp=datetime.now(timezone.utc),
                     screenshot_bytes=b"img", action_type=actions[0]),
            StepData(step_number=2, timestamp=datetime.now(timezone.utc),
                     screenshot_bytes=b"img", action_type=actions[1]),
            StepData(step_number=3, timestamp=datetime.now(timezone.utc),
                     screenshot_bytes=None, action_type=actions[2]),  # breaks chain
            StepData(step_number=4, timestamp=datetime.now(timezone.utc),
                     screenshot_bytes=b"img", action_type=actions[3]),
            StepData(step_number=5, timestamp=datetime.now(timezone.utc),
                     screenshot_bytes=b"img", action_type=actions[4]),
        ]
        sig = det.analyze_full_history(steps)
        assert not sig.detected

    def test_step_number_on_detected_signal(self) -> None:
        """Signal reports the step_number where detection occurred."""
        det = StuckDetector(failure_threshold=2)
        steps = [
            StepData(step_number=10, timestamp=datetime.now(timezone.utc), success=True),
            StepData(step_number=11, timestamp=datetime.now(timezone.utc), success=False),
            StepData(step_number=12, timestamp=datetime.now(timezone.utc), success=False),
        ]
        sig = det.analyze_full_history(steps)
        assert sig.detected
        assert sig.step_number == 12

    def test_bytearray_screenshot(self) -> None:
        """Real-time path handles bytearray screenshots."""
        det = StuckDetector(screenshot_threshold=2)
        img = bytearray(b"same-data")
        det.check_agent_step(SimpleNamespace(
            state=SimpleNamespace(screenshot=img),
            model_output=None, result=None,
        ))
        sig = det.check_agent_step(SimpleNamespace(
            state=SimpleNamespace(screenshot=img),
            model_output=None, result=None,
        ))
        assert sig.detected

    def test_screenshot_type_unrecognized_ignored(self) -> None:
        """Non-str/bytes/bytearray screenshot is silently ignored."""
        det = StuckDetector(screenshot_threshold=2)
        det.check_agent_step(SimpleNamespace(
            state=SimpleNamespace(screenshot=12345),
            model_output=None, result=None,
        ))
        sig = det.check_agent_step(SimpleNamespace(
            state=SimpleNamespace(screenshot=12345),
            model_output=None, result=None,
        ))
        assert not sig.detected  # ignored, deque stayed empty

    def test_result_none_resets_failure_count(self) -> None:
        """result=None counts as a success (resets consecutive failures)."""
        det = StuckDetector(failure_threshold=3)
        det.check_agent_step(SimpleNamespace(state=None, model_output=None,
                                             result=[SimpleNamespace(error="e")]))
        det.check_agent_step(SimpleNamespace(state=None, model_output=None,
                                             result=None))  # reset
        det.check_agent_step(SimpleNamespace(state=None, model_output=None,
                                             result=[SimpleNamespace(error="e")]))
        sig = det.check_agent_step(SimpleNamespace(state=None, model_output=None,
                                                   result=[SimpleNamespace(error="e")]))
        assert not sig.detected  # only 2 consecutive, not 3


# ===================================================================
# cost edge cases
# ===================================================================


class TestCostEdgeCases:
    def test_very_large_token_counts(self) -> None:
        result = calculate_cost_cents(100_000_000, 50_000_000)
        assert result > 0
        assert isinstance(result, float)

    def test_negative_tokens(self) -> None:
        """Negative tokens produce negative cost (garbage in, garbage out)."""
        result = calculate_cost_cents(-1000, 0)
        assert result < 0

    def test_cost_precision(self) -> None:
        """Result rounded to 4 decimal places."""
        result = calculate_cost_cents(1, 1)
        parts = str(result).split(".")
        if len(parts) == 2:
            assert len(parts[1]) <= 4

    def test_steps_with_zero_tokens(self) -> None:
        steps = [
            SimpleNamespace(tokens_in=0, tokens_out=0),
            SimpleNamespace(tokens_in=0, tokens_out=0),
        ]
        assert calculate_cost_from_steps(steps) == 0.0

    def test_single_step(self) -> None:
        steps = [SimpleNamespace(tokens_in=1_000_000, tokens_out=0)]
        result = calculate_cost_from_steps(steps)
        assert result == calculate_cost_cents(1_000_000, 0)


# ===================================================================
# replay_generator edge cases
# ===================================================================


class TestReplayGeneratorEdgeCases:
    def test_html_special_chars_in_description(self) -> None:
        """Descriptions with HTML-like content are safely embedded in JSON."""
        step = StepData(
            step_number=1,
            timestamp=datetime.now(timezone.utc),
            description='Clicked <button id="submit">&amp; submitted',
            action_type="click",
        )
        gen = ReplayGenerator(steps=[step], task_metadata={"task_id": "xss-test"})
        serialized = gen._serialize_step(step)
        assert "<button" in serialized["description"]
        # When embedded in HTML via JSON, the data is inside a JS variable
        # so HTML entities are not interpreted by the browser

    def test_binary_screenshot_not_jpeg(self) -> None:
        """Non-JPEG bytes still base64-encode without error."""
        png_header = b"\x89PNG\r\n\x1a\n"
        step = StepData(
            step_number=1,
            timestamp=datetime.now(timezone.utc),
            screenshot_bytes=png_header,
        )
        gen = ReplayGenerator(steps=[step], task_metadata={})
        serialized = gen._serialize_step(step)
        decoded = base64.standard_b64decode(serialized["screenshot"])
        assert decoded == png_header

    def test_empty_screenshot_bytes(self) -> None:
        """Empty bytes b'' is falsy — treated as no screenshot."""
        step = StepData(
            step_number=1,
            timestamp=datetime.now(timezone.utc),
            screenshot_bytes=b"",
        )
        gen = ReplayGenerator(steps=[step], task_metadata={})
        serialized = gen._serialize_step(step)
        assert serialized["screenshot"] is None

    def test_metadata_with_special_chars(self) -> None:
        meta = {
            "task_id": 'task-"quoted"',
            "task": "Find <items> & count 'em",
        }
        gen = ReplayGenerator(steps=[], task_metadata=meta)
        data = gen._build_replay_json()
        assert data["task_id"] == 'task-"quoted"'
        assert data["task_description"] == "Find <items> & count 'em"

    def test_generate_html_is_valid_json_with_special_chars(self) -> None:
        """Special chars in metadata survive JSON embedding in HTML."""
        step = StepData(
            step_number=1,
            timestamp=datetime.now(timezone.utc),
            description='Line with "quotes" and <tags>',
        )
        gen = ReplayGenerator(
            steps=[step],
            task_metadata={"task_id": "special", "task": 'Task with "quotes"'},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out = gen.generate(f"{tmpdir}/replay.html")
            html = Path(out).read_text()
            marker = "var replayData = "
            start = html.index(marker) + len(marker)
            end = html.index(";\n", start)
            data = json.loads(html[start:end])
            assert data["steps"][0]["description"] == 'Line with "quotes" and <tags>'

    def test_large_number_of_steps(self) -> None:
        """100 steps should generate without issue."""
        steps = [
            StepData(step_number=i, timestamp=datetime.now(timezone.utc),
                     action_type="click", tokens_in=100, tokens_out=50)
            for i in range(1, 101)
        ]
        gen = ReplayGenerator(steps=steps, task_metadata={"task_id": "big"})
        with tempfile.TemporaryDirectory() as tmpdir:
            out = gen.generate(f"{tmpdir}/replay.html")
            html = Path(out).read_text()
            marker = "var replayData = "
            start = html.index(marker) + len(marker)
            end = html.index(";\n", start)
            data = json.loads(html[start:end])
            assert data["total_steps"] == 100
            assert len(data["steps"]) == 100


# ===================================================================
# models edge cases
# ===================================================================


class TestStepDataEdgeCases:
    def test_step_number_exactly_1(self) -> None:
        step = StepData(step_number=1, timestamp=datetime.now(timezone.utc))
        assert step.step_number == 1

    def test_large_step_number(self) -> None:
        step = StepData(step_number=9999, timestamp=datetime.now(timezone.utc))
        assert step.step_number == 9999

    def test_action_type_preserves_string(self) -> None:
        step = StepData(step_number=1, timestamp=datetime.now(timezone.utc),
                        action_type="custom_action")
        assert step.action_type == "custom_action"

    def test_tokens_default_zero(self) -> None:
        step = StepData(step_number=1, timestamp=datetime.now(timezone.utc))
        assert step.tokens_in == 0
        assert step.tokens_out == 0
        assert step.duration_ms == 0

    def test_screenshot_bytes_none_vs_empty(self) -> None:
        s1 = StepData(step_number=1, timestamp=datetime.now(timezone.utc),
                      screenshot_bytes=None)
        s2 = StepData(step_number=1, timestamp=datetime.now(timezone.utc),
                      screenshot_bytes=b"")
        assert s1.screenshot_bytes is None
        assert s2.screenshot_bytes == b""

    def test_model_dump_mode_json(self) -> None:
        """model_dump(mode='json') produces JSON-serializable output."""
        step = StepData(step_number=1, timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                        tokens_in=100, reasoning="think")
        d = step.model_dump(mode="json")
        # Should be JSON serializable
        j = json.dumps(d)
        assert "screenshot_bytes" not in j


class TestTaskResultEdgeCases:
    def test_to_dict_with_plain_dict_step_data(self) -> None:
        """step_data can contain plain dicts (e.g. after from_dict deserialization)."""
        r = TaskResult(
            task_id="t", status="completed", success=True,
            step_data=[{"step_number": 1, "action_type": "click"}],
        )
        d = r.to_dict()
        assert d["step_data"][0]["step_number"] == 1

    def test_from_dict_invalid_datetime_becomes_none(self) -> None:
        d = {
            "task_id": "t", "status": "done", "success": True,
            "created_at": "not-a-date",
        }
        r = TaskResult.from_dict(d)
        assert r.created_at is None

    def test_to_json_with_none_values(self) -> None:
        r = TaskResult(
            task_id="t", status="failed", success=False,
            result=None, error=None, replay_url=None,
            error_category=None,
        )
        j = r.to_json()
        parsed = json.loads(j)
        assert parsed["result"] is None
        assert parsed["error_category"] is None

    def test_to_json_indent(self) -> None:
        r = TaskResult(task_id="t", status="done", success=True)
        j = r.to_json(indent=2)
        assert "\n" in j
        assert "  " in j

    def test_step_data_default_empty_list(self) -> None:
        """Each TaskResult instance gets its own step_data list."""
        r1 = TaskResult(task_id="t1", status="done", success=True)
        r2 = TaskResult(task_id="t2", status="done", success=True)
        r1.step_data.append({"step": 1})
        assert len(r2.step_data) == 0  # independent list

    def test_from_json_round_trip_preserves_all_fields(self) -> None:
        original = TaskResult(
            task_id="round-trip",
            status="completed",
            success=True,
            result={"key": "value"},
            error=None,
            replay_url="https://example.com/replay",
            replay_path="/tmp/replay.html",
            steps=5,
            duration_ms=12345,
            created_at=datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
            completed_at=datetime(2025, 6, 1, 12, 1, 0, tzinfo=timezone.utc),
            cost_cents=42.5,
            total_tokens_in=50000,
            total_tokens_out=10000,
            error_category=None,
            step_data=[],
        )
        restored = TaskResult.from_json(original.to_json())
        assert restored.task_id == original.task_id
        assert restored.success == original.success
        assert restored.steps == original.steps
        assert restored.duration_ms == original.duration_ms
        assert restored.cost_cents == original.cost_cents
        assert restored.total_tokens_in == original.total_tokens_in
        assert restored.total_tokens_out == original.total_tokens_out
        assert restored.replay_url == original.replay_url
        assert restored.replay_path == original.replay_path
        assert restored.result == original.result
        assert restored.created_at == original.created_at
        assert restored.completed_at == original.completed_at
