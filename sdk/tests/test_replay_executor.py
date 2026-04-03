"""Tests for computeruse.replay_executor — workflow replay with fallback."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from computeruse.compiler import WorkflowCompiler
from computeruse.models import CompiledStep, CompiledWorkflow
from computeruse.replay_executor import (
    ReplayConfig,
    ReplayExecutor,
    ReplayResult,
)


# ---------------------------------------------------------------------------
# Mock page
# ---------------------------------------------------------------------------


class MockPage:
    """Mock Playwright page that succeeds on all actions."""

    def __init__(self, url: str = "https://example.com") -> None:
        self.url = url
        self._click_called = 0
        self._fill_called = 0
        self._fill_args: list[tuple] = []

    async def goto(self, url: str) -> None:
        self.url = url

    async def click(self, selector: str, **kwargs: object) -> None:
        self._click_called += 1

    async def fill(self, selector: str, value: str) -> None:
        self._fill_called += 1
        self._fill_args.append((selector, value))

    async def select_option(self, selector: str, value: str) -> None:
        pass

    async def press(self, selector: str, key: str) -> None:
        pass

    async def dblclick(self, selector: str) -> None:
        pass

    async def hover(self, selector: str) -> None:
        pass

    async def evaluate(self, expr: str) -> None:
        pass

    async def text_content(self, selector: str) -> str:
        return ""

    async def wait_for_timeout(self, ms: int) -> None:
        pass

    async def wait_for_selector(self, sel: str, **kw: object) -> bool:
        return True

    async def content(self) -> str:
        return "<html></html>"


class FailThenSucceedPage(MockPage):
    """Page where primary selector fails but alternate succeeds."""

    def __init__(self) -> None:
        super().__init__()
        self._attempts = 0
        self._fail_selector = "#primary-btn"

    async def click(self, selector: str, **kwargs: object) -> None:
        if selector == self._fail_selector:
            self._attempts += 1
            raise Exception(f"Element not found: {selector}")
        self._click_called += 1

    async def wait_for_selector(self, sel: str, **kw: object) -> bool:
        if sel != self._fail_selector:
            return True
        raise Exception("timeout")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_workflow(
    steps: list[CompiledStep] | None = None,
    name: str = "test-workflow",
    parameters: dict[str, str] | None = None,
) -> CompiledWorkflow:
    """Build a test CompiledWorkflow."""
    if steps is None:
        steps = [
            CompiledStep(
                action_type="click",
                selectors=[
                    {"type": "css", "value": "#btn", "confidence": 0.9},
                ],
                intent="Click button",
                timeout_ms=0,
            ),
        ]
    return CompiledWorkflow(
        name=name,
        steps=steps,
        parameters=parameters or {},
        source_task_id="task-001",
        compiled_at="2026-01-01T00:00:00+00:00",
    )


def _config(**overrides: object) -> ReplayConfig:
    """Build a ReplayConfig with short waits for testing."""
    defaults: dict = {
        "verify_actions": False,
        "max_retries_per_step": 1,
    }
    defaults.update(overrides)
    return ReplayConfig(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_tier0_success() -> None:
    """All selectors work -> steps_deterministic == total."""
    steps = [
        CompiledStep(
            action_type="goto",
            selectors=[],
            intent="Navigate",
            pre_url="https://example.com",
            timeout_ms=0,
        ),
        CompiledStep(
            action_type="click",
            selectors=[{"type": "css", "value": "#btn", "confidence": 0.9}],
            intent="Click button",
            timeout_ms=0,
        ),
    ]
    wf = _make_workflow(steps=steps)
    page = MockPage()
    executor = ReplayExecutor(config=_config())
    result = await executor.execute(wf, page=page)

    assert result.success is True
    assert result.steps_executed == 2
    assert result.steps_deterministic == 2
    assert result.steps_healed == 0
    assert result.steps_ai_recovered == 0
    assert result.error is None
    # Verify goto navigated to the correct URL
    assert page.url == "https://example.com"


async def test_tier1_healing() -> None:
    """Primary fails, alternate works -> steps_healed counted."""
    steps = [
        CompiledStep(
            action_type="click",
            selectors=[
                {"type": "css", "value": "#primary-btn", "confidence": 0.9},
                {"type": "text", "value": "Submit", "confidence": 0.7},
            ],
            intent="Click Submit",
            timeout_ms=0,
        ),
    ]
    wf = _make_workflow(steps=steps)
    executor = ReplayExecutor(config=_config(max_retries_per_step=0))
    page = FailThenSucceedPage()
    result = await executor.execute(wf, page=page)

    assert result.success is True
    assert result.steps_healed == 1
    assert result.steps_deterministic == 0


async def test_tier2_mock() -> None:
    """Mock Anthropic API -> AI selector works."""

    class AIRecoverPage(MockPage):
        """Page where ONLY the AI-provided selector #ok-btn works."""

        async def click(self, selector: str, **kwargs: object) -> None:
            if selector != "#ok-btn":
                raise Exception(f"Element not found: {selector}")
            self._click_called += 1

        async def wait_for_selector(self, sel: str, **kw: object) -> bool:
            if sel == "#ok-btn":
                return True
            raise Exception("timeout")

        @property
        def accessibility(self) -> object:
            mock = MagicMock()
            mock.snapshot = AsyncMock(return_value={"role": "button", "name": "OK"})
            return mock

    steps = [
        CompiledStep(
            action_type="click",
            selectors=[
                {"type": "css", "value": "#broken", "confidence": 0.9},
                {"type": "text", "value": "Broken", "confidence": 0.7},
            ],
            intent="Click OK",
            timeout_ms=0,
        ),
    ]
    wf = _make_workflow(steps=steps)

    api_response = json.dumps({
        "content": [{"text": "#ok-btn"}],
        "usage": {"input_tokens": 500, "output_tokens": 20},
    }).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = api_response
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            executor = ReplayExecutor(config=_config(max_retries_per_step=0))
            result = await executor.execute(wf, page=AIRecoverPage())

    assert result.success is True
    assert result.steps_ai_recovered == 1


async def test_budget_exceeded() -> None:
    """Low budget + Tier 2 costs -> BudgetExceededError."""

    class FailPage(MockPage):
        async def click(self, selector: str, **kwargs: object) -> None:
            raise Exception("not found")

        async def wait_for_selector(self, sel: str, **kw: object) -> bool:
            raise Exception("timeout")

        @property
        def accessibility(self) -> object:
            mock = MagicMock()
            mock.snapshot = AsyncMock(return_value={"role": "button"})
            return mock

    steps = [
        CompiledStep(
            action_type="click",
            selectors=[{"type": "css", "value": "#x", "confidence": 0.9}],
            intent="Click",
            timeout_ms=0,
        ),
    ]
    wf = _make_workflow(steps=steps)

    api_response = json.dumps({
        "content": [{"text": "#btn"}],
        "usage": {"input_tokens": 999_999, "output_tokens": 999_999},
    }).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = api_response
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            executor = ReplayExecutor(
                config=_config(max_cost_cents=0.001, max_retries_per_step=0)
            )
            result = await executor.execute(wf, page=FailPage())

    assert result.success is False
    assert "Budget exceeded" in (result.error or "")


async def test_verification_after_step() -> None:
    """ActionVerifier.verify_action called after each step."""
    steps = [
        CompiledStep(
            action_type="click",
            selectors=[{"type": "css", "value": "#btn", "confidence": 0.9}],
            intent="Click",
            timeout_ms=0,
        ),
        CompiledStep(
            action_type="click",
            selectors=[{"type": "css", "value": "#btn2", "confidence": 0.9}],
            intent="Click 2",
            timeout_ms=0,
        ),
    ]
    wf = _make_workflow(steps=steps)
    executor = ReplayExecutor(config=_config(verify_actions=True))

    call_count = 0
    original_verify = executor._verifier.verify_action

    async def counting_verify(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        return await original_verify(*args, **kwargs)

    executor._verifier.verify_action = counting_verify  # type: ignore[assignment]

    result = await executor.execute(wf, page=MockPage())

    assert result.success is True
    assert call_count == 2


async def test_params_substitution() -> None:
    """{{email}} + params -> correct fill value."""
    steps = [
        CompiledStep(
            action_type="fill",
            selectors=[{"type": "css", "value": "#email", "confidence": 0.9}],
            intent="Enter email",
            fill_value_template="{{email}}",
            timeout_ms=0,
        ),
    ]
    wf = _make_workflow(steps=steps, parameters={"email": ""})
    executor = ReplayExecutor(config=_config())
    page = MockPage()

    result = await executor.execute(
        wf, params={"email": "test@example.com"}, page=page
    )

    assert result.success is True
    assert page._fill_args == [("#email", "test@example.com")]


async def test_execute_from_file(tmp_path: Path) -> None:
    """Load workflow JSON -> execute -> ReplayResult."""
    wf = _make_workflow()
    compiler = WorkflowCompiler()
    out_dir = str(tmp_path / "workflows")
    path = compiler.save_workflow(wf, output_dir=out_dir)

    executor = ReplayExecutor(config=_config())
    result = await executor.execute_from_file(path, page=MockPage())

    assert isinstance(result, ReplayResult)
    assert result.success is True
    assert result.steps_executed == 1
