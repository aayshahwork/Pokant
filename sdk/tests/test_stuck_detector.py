"""Tests for computeruse.stuck_detector — stuck agent pattern detection."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from computeruse.models import ActionType, StepData
from computeruse.stuck_detector import StuckDetector, StuckSignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(
    step_number: int = 1,
    action_type: ActionType = ActionType.CLICK,
    screenshot_bytes: bytes | None = None,
    success: bool = True,
    error: str | None = None,
) -> StepData:
    return StepData(
        step_number=step_number,
        timestamp=datetime.now(timezone.utc),
        action_type=action_type,
        description="test step",
        screenshot_bytes=screenshot_bytes,
        success=success,
        error=error,
    )


def _make_agent_history_step(
    screenshot: bytes | None = None,
    action_class_name: str = "ClickElementAction",
    has_error: bool = False,
) -> SimpleNamespace:
    """Simulate a browser_use AgentHistoryStep via SimpleNamespace."""
    state = SimpleNamespace(screenshot=screenshot) if screenshot is not None else SimpleNamespace()
    action_obj = type(action_class_name, (), {})()
    model_output = SimpleNamespace(action=[action_obj])
    if has_error:
        result = [SimpleNamespace(error="element not found")]
    else:
        result = [SimpleNamespace(error=None)]
    return SimpleNamespace(state=state, model_output=model_output, result=result)


# ===================================================================
# StuckSignal
# ===================================================================

class TestStuckSignal:
    def test_defaults(self) -> None:
        sig = StuckSignal()
        assert sig.detected is False
        assert sig.reason == "none"
        assert sig.details == ""
        assert sig.step_number == 0

    def test_frozen(self) -> None:
        sig = StuckSignal(detected=True, reason="visual_stagnation")
        with pytest.raises(AttributeError):
            sig.detected = False  # type: ignore[misc]


# ===================================================================
# check_agent_step — real-time detection
# ===================================================================

class TestCheckAgentStep:
    def test_visual_stagnation_detected(self) -> None:
        det = StuckDetector(screenshot_threshold=4)
        same_img = b"identical-screenshot-bytes"
        for i in range(3):
            step = _make_agent_history_step(screenshot=same_img)
            sig = det.check_agent_step(step)
            assert not sig.detected, f"Should not trigger on step {i + 1}"
        sig = det.check_agent_step(_make_agent_history_step(screenshot=same_img))
        assert sig.detected
        assert sig.reason == "visual_stagnation"

    def test_visual_stagnation_below_threshold(self) -> None:
        det = StuckDetector(screenshot_threshold=4)
        same_img = b"same"
        for _ in range(3):
            sig = det.check_agent_step(_make_agent_history_step(screenshot=same_img))
        assert not sig.detected

    def test_different_screenshots_no_detection(self) -> None:
        det = StuckDetector(screenshot_threshold=4)
        actions = ["ClickElementAction", "InputTextAction", "ScrollAction"]
        for i in range(6):
            sig = det.check_agent_step(
                _make_agent_history_step(
                    screenshot=f"img-{i}".encode(),
                    action_class_name=actions[i % len(actions)],
                )
            )
        assert not sig.detected

    def test_action_repetition_detected(self) -> None:
        det = StuckDetector(action_threshold=5)
        for i in range(4):
            sig = det.check_agent_step(
                _make_agent_history_step(action_class_name="ClickElementAction")
            )
            assert not sig.detected, f"Should not trigger on step {i + 1}"
        sig = det.check_agent_step(
            _make_agent_history_step(action_class_name="ClickElementAction")
        )
        assert sig.detected
        assert sig.reason == "action_repetition"

    def test_action_repetition_below_threshold(self) -> None:
        det = StuckDetector(action_threshold=5)
        for _ in range(4):
            sig = det.check_agent_step(
                _make_agent_history_step(action_class_name="ClickElementAction")
            )
        assert not sig.detected

    def test_mixed_actions_no_detection(self) -> None:
        det = StuckDetector(action_threshold=5)
        actions = ["ClickElementAction", "InputTextAction", "ScrollAction"]
        for i in range(10):
            sig = det.check_agent_step(
                _make_agent_history_step(action_class_name=actions[i % len(actions)])
            )
        assert not sig.detected

    def test_failure_spiral_detected(self) -> None:
        det = StuckDetector(failure_threshold=3)
        for i in range(2):
            sig = det.check_agent_step(_make_agent_history_step(has_error=True))
            assert not sig.detected
        sig = det.check_agent_step(_make_agent_history_step(has_error=True))
        assert sig.detected
        assert sig.reason == "failure_spiral"

    def test_failure_spiral_reset_on_success(self) -> None:
        actions = ["ClickElementAction", "InputTextAction", "ScrollAction",
                    "GoToUrlAction", "WaitAction"]
        det = StuckDetector(failure_threshold=3)
        det.check_agent_step(_make_agent_history_step(has_error=True, action_class_name=actions[0]))
        det.check_agent_step(_make_agent_history_step(has_error=True, action_class_name=actions[1]))
        det.check_agent_step(_make_agent_history_step(has_error=False, action_class_name=actions[2]))  # reset
        det.check_agent_step(_make_agent_history_step(has_error=True, action_class_name=actions[3]))
        sig = det.check_agent_step(_make_agent_history_step(has_error=True, action_class_name=actions[4]))
        assert not sig.detected

    def test_missing_screenshot_safe(self) -> None:
        det = StuckDetector(screenshot_threshold=2)
        step = SimpleNamespace(
            state=SimpleNamespace(),  # no .screenshot
            model_output=None,
            result=None,
        )
        sig = det.check_agent_step(step)
        assert not sig.detected

    def test_missing_action_safe(self) -> None:
        det = StuckDetector()
        step = SimpleNamespace(state=None, model_output=None, result=None)
        sig = det.check_agent_step(step)
        assert not sig.detected

    def test_idempotent_after_detection(self) -> None:
        det = StuckDetector(failure_threshold=2)
        det.check_agent_step(_make_agent_history_step(has_error=True))
        first = det.check_agent_step(_make_agent_history_step(has_error=True))
        assert first.detected
        # Subsequent calls return the cached signal
        second = det.check_agent_step(_make_agent_history_step(has_error=False))
        assert second.detected
        assert second is first


# ===================================================================
# analyze_full_history — post-execution detection
# ===================================================================

class TestAnalyzeFullHistory:
    def test_visual_stagnation_on_enriched_steps(self) -> None:
        det = StuckDetector(screenshot_threshold=4)
        same_img = b"same-page-screenshot"
        steps = [_make_step(i, screenshot_bytes=same_img) for i in range(1, 5)]
        sig = det.analyze_full_history(steps)
        assert sig.detected
        assert sig.reason == "visual_stagnation"

    def test_skips_none_screenshots(self) -> None:
        det = StuckDetector(screenshot_threshold=3)
        steps = [
            _make_step(1, screenshot_bytes=b"a"),
            _make_step(2, screenshot_bytes=None),  # break the chain
            _make_step(3, screenshot_bytes=b"a"),
            _make_step(4, screenshot_bytes=b"a"),
        ]
        sig = det.analyze_full_history(steps)
        assert not sig.detected

    def test_action_repetition_on_enriched_steps(self) -> None:
        det = StuckDetector(action_threshold=5)
        steps = [
            _make_step(i, action_type=ActionType.CLICK)
            for i in range(1, 6)
        ]
        sig = det.analyze_full_history(steps)
        assert sig.detected
        assert sig.reason == "action_repetition"

    def test_failure_spiral_on_enriched_steps(self) -> None:
        det = StuckDetector(failure_threshold=3)
        steps = [_make_step(i, success=False) for i in range(1, 4)]
        sig = det.analyze_full_history(steps)
        assert sig.detected
        assert sig.reason == "failure_spiral"

    def test_mixed_patterns_reports_first(self) -> None:
        """Visual stagnation is checked first, so it wins."""
        det = StuckDetector(screenshot_threshold=3, action_threshold=3, failure_threshold=3)
        same_img = b"img"
        steps = [
            _make_step(i, action_type=ActionType.CLICK, screenshot_bytes=same_img, success=False)
            for i in range(1, 4)
        ]
        sig = det.analyze_full_history(steps)
        assert sig.detected
        assert sig.reason == "visual_stagnation"

    def test_no_detection_normal_workflow(self) -> None:
        det = StuckDetector()
        steps = [
            _make_step(1, ActionType.NAVIGATE, b"page1"),
            _make_step(2, ActionType.CLICK, b"page2"),
            _make_step(3, ActionType.TYPE, b"page3"),
            _make_step(4, ActionType.CLICK, b"page4"),
            _make_step(5, ActionType.EXTRACT, b"page5"),
        ]
        sig = det.analyze_full_history(steps)
        assert not sig.detected

    def test_empty_steps(self) -> None:
        det = StuckDetector()
        sig = det.analyze_full_history([])
        assert not sig.detected

    def test_single_step(self) -> None:
        det = StuckDetector()
        sig = det.analyze_full_history([_make_step(1)])
        assert not sig.detected


# ===================================================================
# reset
# ===================================================================

class TestReset:
    def test_reset_clears_state(self) -> None:
        det = StuckDetector(failure_threshold=2)
        det.check_agent_step(_make_agent_history_step(has_error=True))
        det.check_agent_step(_make_agent_history_step(has_error=True))
        assert det._signal is not None  # stuck detected
        det.reset()
        assert det._signal is None
        assert det._consecutive_failures == 0
        assert len(det._screenshot_hashes) == 0
        assert len(det._recent_actions) == 0
        # After reset, should not be stuck
        sig = det.check_agent_step(_make_agent_history_step(has_error=False))
        assert not sig.detected


# ===================================================================
# Custom thresholds
# ===================================================================

class TestCustomThresholds:
    def test_custom_screenshot_threshold(self) -> None:
        det = StuckDetector(screenshot_threshold=2)
        det.check_agent_step(_make_agent_history_step(screenshot=b"x"))
        sig = det.check_agent_step(_make_agent_history_step(screenshot=b"x"))
        assert sig.detected
        assert sig.reason == "visual_stagnation"

    def test_custom_action_threshold(self) -> None:
        det = StuckDetector(action_threshold=3)
        for _ in range(2):
            det.check_agent_step(_make_agent_history_step(action_class_name="ScrollAction"))
        sig = det.check_agent_step(
            _make_agent_history_step(action_class_name="ScrollAction")
        )
        assert sig.detected
        assert sig.reason == "action_repetition"

    def test_custom_failure_threshold(self) -> None:
        det = StuckDetector(failure_threshold=2)
        det.check_agent_step(_make_agent_history_step(has_error=True))
        sig = det.check_agent_step(_make_agent_history_step(has_error=True))
        assert sig.detected
        assert sig.reason == "failure_spiral"
