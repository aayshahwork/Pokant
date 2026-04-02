"""Tests for AlertConfig and AlertEmitter — SDK-side alerting."""

import json
from unittest.mock import MagicMock, patch

import pytest

from computeruse.alerts import AlertConfig, AlertEmitter


class TestAlertEmitter:

    def test_failure_alert_fires(self) -> None:
        """on_failure callback is invoked with correct args."""
        callback = MagicMock()
        config = AlertConfig(on_failure=callback)
        emitter = AlertEmitter(config)

        emitter.emit_failure("task-123", "element not found", "permanent_dom")

        callback.assert_called_once_with("task-123", "element not found", "permanent_dom")

    def test_failure_alert_with_none_category(self) -> None:
        """on_failure callback works when category is None."""
        callback = MagicMock()
        config = AlertConfig(on_failure=callback)
        emitter = AlertEmitter(config)

        emitter.emit_failure("task-456", "timeout", None)

        callback.assert_called_once_with("task-456", "timeout", None)

    def test_stuck_alert_fires(self) -> None:
        """on_stuck callback is invoked with correct args."""
        callback = MagicMock()
        config = AlertConfig(on_stuck=callback)
        emitter = AlertEmitter(config)

        emitter.emit_stuck("task-789", "visual_stagnation")

        callback.assert_called_once_with("task-789", "visual_stagnation")

    def test_cost_alert_fires_once(self) -> None:
        """on_cost_exceeded fires when threshold crossed, only once."""
        callback = MagicMock()
        config = AlertConfig(
            on_cost_exceeded=callback,
            cost_threshold_cents=50.0,
        )
        emitter = AlertEmitter(config)

        # Below threshold — should NOT fire
        emitter.check_cost("task-abc", 30.0)
        callback.assert_not_called()

        # Exceeds threshold — should fire
        emitter.check_cost("task-abc", 60.0)
        callback.assert_called_once_with("task-abc", 60.0)

        # Already alerted — should NOT fire again
        emitter.check_cost("task-abc", 70.0)
        assert callback.call_count == 1

    def test_cost_alert_no_threshold(self) -> None:
        """No cost alert when threshold is not set."""
        callback = MagicMock()
        config = AlertConfig(on_cost_exceeded=callback, cost_threshold_cents=None)
        emitter = AlertEmitter(config)

        emitter.check_cost("task-def", 1000.0)
        callback.assert_not_called()

    def test_webhook_alert(self) -> None:
        """Webhook POST is sent with correct payload."""
        config = AlertConfig(webhook_url="http://localhost:9999/hook")
        emitter = AlertEmitter(config)

        with patch("computeruse.alerts.urllib.request.urlopen") as mock_urlopen:
            emitter.emit_failure("task-wh", "bad click", "permanent_dom")

            mock_urlopen.assert_called_once()
            request_obj = mock_urlopen.call_args[0][0]
            body = json.loads(request_obj.data.decode("utf-8"))
            assert body["alert_type"] == "failure"
            assert body["task_id"] == "task-wh"
            assert body["error"] == "bad click"
            assert body["error_category"] == "permanent_dom"
            assert "timestamp" in body

    def test_webhook_with_custom_headers(self) -> None:
        """Custom headers are included in webhook POST."""
        config = AlertConfig(
            webhook_url="http://localhost:9999/hook",
            webhook_headers={"Authorization": "Bearer tok"},
        )
        emitter = AlertEmitter(config)

        with patch("computeruse.alerts.urllib.request.urlopen") as mock_urlopen:
            emitter.emit_stuck("task-hdr", "action_loop")

            request_obj = mock_urlopen.call_args[0][0]
            assert request_obj.get_header("Authorization") == "Bearer tok"
            assert request_obj.get_header("Content-type") == "application/json"

    def test_no_alerts_without_config(self) -> None:
        """No callbacks or webhooks fire when AlertConfig has no handlers."""
        config = AlertConfig()
        emitter = AlertEmitter(config)

        # None of these should raise
        emitter.emit_failure("t", "err", "cat")
        emitter.emit_stuck("t", "reason")
        emitter.check_cost("t", 9999.0)

    def test_callback_exception_swallowed(self) -> None:
        """Exception in user callback does not propagate."""
        def bad_callback(*args: object) -> None:
            raise ValueError("user bug")

        config = AlertConfig(on_failure=bad_callback)
        emitter = AlertEmitter(config)

        # Should not raise
        emitter.emit_failure("task-err", "some error", None)

    def test_webhook_failure_swallowed(self) -> None:
        """Failed webhook POST does not propagate."""
        config = AlertConfig(webhook_url="http://unreachable:9999/hook")
        emitter = AlertEmitter(config)

        with patch(
            "computeruse.alerts.urllib.request.urlopen",
            side_effect=ConnectionError("refused"),
        ):
            # Should not raise
            emitter.emit_failure("task-wf", "error", None)
