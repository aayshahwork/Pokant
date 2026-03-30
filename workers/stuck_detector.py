"""
workers/stuck_detector.py — Detect stuck browser agent patterns.

Identifies three stuck patterns:
- Visual stagnation: consecutive identical screenshots (MD5 hash comparison)
- Action repetition: same action type repeated N consecutive times
- Failure spiral: N consecutive step failures

Operates at two detection points:
- Real-time: check_agent_step() called from on_step_end hook during agent.run()
- Post-execution: analyze_full_history() called on enriched StepData after agent.run()
"""

from __future__ import annotations

import hashlib
import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, List, Optional

from workers.models import StepData

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StuckSignal:
    """Result of stuck pattern analysis."""

    detected: bool = False
    reason: str = "none"  # "visual_stagnation" | "action_repetition" | "failure_spiral" | "none"
    details: str = ""
    step_number: int = 0


_NOT_STUCK = StuckSignal()


class StuckDetector:
    """Sliding-window detector for stuck browser agent patterns.

    Maintains internal state across calls to ``check_agent_step`` for
    real-time detection.  ``analyze_full_history`` is stateless and
    operates on the enriched ``StepData`` list after execution.
    """

    def __init__(
        self,
        screenshot_threshold: int = 4,
        action_threshold: int = 5,
        failure_threshold: int = 3,
    ) -> None:
        self.screenshot_threshold = screenshot_threshold
        self.action_threshold = action_threshold
        self.failure_threshold = failure_threshold

        self._screenshot_hashes: deque[str] = deque(maxlen=screenshot_threshold)
        self._recent_actions: deque[str] = deque(maxlen=action_threshold)
        self._consecutive_failures: int = 0
        self._step_count: int = 0
        self._signal: Optional[StuckSignal] = None

    # ------------------------------------------------------------------
    # Real-time detection (called from on_step_end)
    # ------------------------------------------------------------------

    def check_agent_step(self, agent_history_step: Any) -> StuckSignal:
        """Check a single browser_use AgentHistoryStep for stuck patterns.

        Uses ``getattr`` throughout for resilience against browser_use
        internal changes.  Returns the cached signal once stuck is
        detected — subsequent calls are idempotent.
        """
        if self._signal is not None:
            return self._signal

        self._step_count += 1

        try:
            self._ingest_screenshot(agent_history_step)
            self._ingest_action(agent_history_step)
            self._ingest_result(agent_history_step)

            signal = self._evaluate()
            if signal.detected:
                self._signal = signal
                return signal
        except Exception as exc:
            logger.debug("check_agent_step introspection error: %s", exc)

        return _NOT_STUCK

    def _ingest_screenshot(self, step: Any) -> None:
        state = getattr(step, "state", None)
        if state is None:
            return
        screenshot = getattr(state, "screenshot", None)
        if screenshot is None:
            return
        if isinstance(screenshot, str):
            # base64-encoded string — hash as-is
            h = hashlib.md5(screenshot.encode()).hexdigest()
        elif isinstance(screenshot, (bytes, bytearray)):
            h = hashlib.md5(screenshot).hexdigest()
        else:
            return
        self._screenshot_hashes.append(h)

    def _ingest_action(self, step: Any) -> None:
        model_output = getattr(step, "model_output", None)
        if model_output is None:
            return
        action_list = getattr(model_output, "action", None)
        if not action_list:
            return
        # browser_use stores actions as a list; take the first
        action = action_list[0] if isinstance(action_list, list) else action_list
        action_name = type(action).__name__
        self._recent_actions.append(action_name)

    def _ingest_result(self, step: Any) -> None:
        result = getattr(step, "result", None)
        if result is None:
            self._consecutive_failures = 0
            return
        if not isinstance(result, list):
            result = [result]
        has_error = any(getattr(r, "error", None) for r in result)
        if has_error:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 0

    def _evaluate(self) -> StuckSignal:
        # Visual stagnation
        if len(self._screenshot_hashes) >= self.screenshot_threshold and len(set(self._screenshot_hashes)) == 1:
            return StuckSignal(
                detected=True,
                reason="visual_stagnation",
                details=f"{self.screenshot_threshold} consecutive identical screenshots",
                step_number=self._step_count,
            )

        # Action repetition
        if len(self._recent_actions) >= self.action_threshold and len(set(self._recent_actions)) == 1:
            action = self._recent_actions[0]
            return StuckSignal(
                detected=True,
                reason="action_repetition",
                details=f"{self.action_threshold} consecutive '{action}' actions",
                step_number=self._step_count,
            )

        # Failure spiral
        if self._consecutive_failures >= self.failure_threshold:
            return StuckSignal(
                detected=True,
                reason="failure_spiral",
                details=f"{self._consecutive_failures} consecutive failures",
                step_number=self._step_count,
            )

        return _NOT_STUCK

    # ------------------------------------------------------------------
    # Post-execution analysis (called on enriched StepData)
    # ------------------------------------------------------------------

    def analyze_full_history(self, steps: List[StepData]) -> StuckSignal:
        """Analyze enriched step data for stuck patterns.

        Stateless — does not use or modify internal sliding-window state.
        Returns the first detected pattern.
        """
        try:
            signal = self._check_visual_stagnation(steps)
            if signal.detected:
                return signal

            signal = self._check_action_repetition(steps)
            if signal.detected:
                return signal

            signal = self._check_failure_spiral(steps)
            if signal.detected:
                return signal
        except Exception as exc:
            logger.debug("analyze_full_history error: %s", exc)

        return _NOT_STUCK

    def _check_visual_stagnation(self, steps: List[StepData]) -> StuckSignal:
        consecutive = 0
        prev_hash: Optional[str] = None
        for step in steps:
            if step.screenshot_bytes is None:
                consecutive = 0
                prev_hash = None
                continue
            h = hashlib.md5(step.screenshot_bytes).hexdigest()
            if h == prev_hash:
                consecutive += 1
            else:
                consecutive = 1
                prev_hash = h
            if consecutive >= self.screenshot_threshold:
                return StuckSignal(
                    detected=True,
                    reason="visual_stagnation",
                    details=f"{consecutive} consecutive identical screenshots",
                    step_number=step.step_number,
                )
        return _NOT_STUCK

    def _check_action_repetition(self, steps: List[StepData]) -> StuckSignal:
        consecutive = 0
        prev_action: Optional[str] = None
        for step in steps:
            action = step.action_type
            if action == prev_action:
                consecutive += 1
            else:
                consecutive = 1
                prev_action = action
            if consecutive >= self.action_threshold:
                return StuckSignal(
                    detected=True,
                    reason="action_repetition",
                    details=f"{consecutive} consecutive '{action}' actions",
                    step_number=step.step_number,
                )
        return _NOT_STUCK

    def _check_failure_spiral(self, steps: List[StepData]) -> StuckSignal:
        consecutive = 0
        for step in steps:
            if not step.success:
                consecutive += 1
            else:
                consecutive = 0
            if consecutive >= self.failure_threshold:
                return StuckSignal(
                    detected=True,
                    reason="failure_spiral",
                    details=f"{consecutive} consecutive failures",
                    step_number=step.step_number,
                )
        return _NOT_STUCK

    def reset(self) -> None:
        """Clear all internal state."""
        self._screenshot_hashes.clear()
        self._recent_actions.clear()
        self._consecutive_failures = 0
        self._step_count = 0
        self._signal = None
