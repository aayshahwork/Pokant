"""Tests for observe_stagehand — Stagehand session tracking wrapper."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from computeruse.models import ActionType
from computeruse.stagehand import (
    StagehandConfig,
    TrackedStagehand,
    observe_stagehand,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeSession:
    """Minimal Stagehand session stub."""

    def __init__(self) -> None:
        self.act = AsyncMock(return_value=SimpleNamespace(success=True))
        self.extract = AsyncMock(return_value={"title": "Hello"})
        self.observe = AsyncMock(
            return_value=[SimpleNamespace(selector="#btn", description="A button")]
        )
        self.navigate = AsyncMock(return_value=None)
        self.execute = AsyncMock(return_value=SimpleNamespace(done=True))
        self.end = AsyncMock()
        self.custom_attr = "passthrough_value"


class FakePage:
    """Minimal Playwright Page stub for screenshots."""

    def __init__(self, screenshot_bytes: bytes = b"fake-jpg") -> None:
        self._screenshot_bytes = screenshot_bytes

    async def screenshot(self, **kwargs: Any) -> bytes:
        return self._screenshot_bytes


class FailingPage:
    """Page whose screenshot always raises."""

    async def screenshot(self, **kwargs: Any) -> bytes:
        raise RuntimeError("page closed")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTrackedStagehand:

    async def test_act_records_step(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=False)
        tracked = TrackedStagehand(session, cfg)
        tracked._start()

        result = await tracked.act("click the login button")

        session.act.assert_awaited_once_with(input="click the login button")
        assert result.success is True
        assert len(tracked.steps) == 1
        step = tracked.steps[0]
        assert step.action_type == ActionType.ACT
        assert "click the login button" in step.description
        assert step.success is True
        assert step.duration_ms >= 0

    async def test_extract_records_step(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=False)
        tracked = TrackedStagehand(session, cfg)
        tracked._start()

        schema = {"type": "object", "properties": {"title": {"type": "string"}}}
        result = await tracked.extract("get the title", schema=schema)

        session.extract.assert_awaited_once_with(
            instruction="get the title", schema=schema
        )
        assert result == {"title": "Hello"}
        step = tracked.steps[0]
        assert step.action_type == ActionType.EXTRACT
        assert "get the title" in step.description

    async def test_observe_records_step(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=False)
        tracked = TrackedStagehand(session, cfg)
        tracked._start()

        result = await tracked.observe("what buttons are visible")

        session.observe.assert_awaited_once_with(
            instruction="what buttons are visible"
        )
        assert len(result) == 1
        step = tracked.steps[0]
        assert step.action_type == ActionType.OBSERVE

    async def test_navigate_records_step(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=False)
        tracked = TrackedStagehand(session, cfg)
        tracked._start()

        await tracked.navigate("https://example.com")

        session.navigate.assert_awaited_once_with(url="https://example.com")
        step = tracked.steps[0]
        assert step.action_type == ActionType.NAVIGATE
        assert "https://example.com" in step.description

    async def test_execute_records_step(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=False)
        tracked = TrackedStagehand(session, cfg)
        tracked._start()

        result = await tracked.execute(
            execute_options={"instruction": "fill the form", "max_steps": 5}
        )

        session.execute.assert_awaited_once()
        assert result.done is True
        step = tracked.steps[0]
        assert step.action_type == ActionType.ACT

    async def test_screenshot_captured_with_page(self, tmp_path: Path) -> None:
        session = FakeSession()
        page = FakePage(b"screenshot-data")
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=True)
        tracked = TrackedStagehand(session, cfg, page=page)
        tracked._start()

        await tracked.act("click something")

        step = tracked.steps[0]
        assert step.screenshot_bytes == b"screenshot-data"

    async def test_no_screenshot_without_page(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=True)
        tracked = TrackedStagehand(session, cfg)  # no page
        tracked._start()

        await tracked.act("click something")

        step = tracked.steps[0]
        assert step.screenshot_bytes is None

    async def test_screenshot_failure_returns_none(self, tmp_path: Path) -> None:
        session = FakeSession()
        page = FailingPage()
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=True)
        tracked = TrackedStagehand(session, cfg, page=page)
        tracked._start()

        await tracked.act("click something")

        step = tracked.steps[0]
        assert step.screenshot_bytes is None

    async def test_failed_action_records_error(self, tmp_path: Path) -> None:
        session = FakeSession()
        session.act = AsyncMock(side_effect=RuntimeError("element not found"))
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=False)
        tracked = TrackedStagehand(session, cfg)
        tracked._start()

        with pytest.raises(RuntimeError, match="element not found"):
            await tracked.act("click missing element")

        assert len(tracked.steps) == 1
        step = tracked.steps[0]
        assert step.success is False
        assert "element not found" in step.error

    async def test_passthrough_attribute(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(output_dir=str(tmp_path))
        tracked = TrackedStagehand(session, cfg)

        assert tracked.custom_attr == "passthrough_value"

    async def test_description_truncation(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=False)
        tracked = TrackedStagehand(session, cfg)
        tracked._start()

        long_input = "x" * 200
        await tracked.act(long_input)

        step = tracked.steps[0]
        # Description should truncate the input to 80 chars
        assert len(step.description) <= len("act()") + 80


class TestObserveStagehandContextManager:

    async def test_context_manager_saves_outputs(self, tmp_path: Path) -> None:
        session = FakeSession()
        page = FakePage(b"screenshot-bytes")
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=True)

        async with observe_stagehand(session, config=cfg, page=page) as t:
            await t.act("click login")
            await t.navigate("https://example.com")

        assert len(t.steps) == 2

        # Run metadata saved
        runs_dir = tmp_path / "runs"
        assert runs_dir.exists()
        metadata_file = runs_dir / f"{t._run_id}.json"
        assert metadata_file.exists()
        metadata = json.loads(metadata_file.read_text())
        assert metadata["executor_mode"] == "stagehand"
        assert metadata["steps_count"] == 2

        # Screenshots saved
        ss_dir = tmp_path / "screenshots" / t._run_id
        assert ss_dir.exists()
        assert len(list(ss_dir.glob("*.jpg"))) == 2

    async def test_context_manager_kwargs(self, tmp_path: Path) -> None:
        session = FakeSession()

        async with observe_stagehand(
            session, output_dir=str(tmp_path), capture_screenshots=False
        ) as t:
            await t.act("do something")

        assert len(t.steps) == 1
        # No screenshots directory when capture is off
        ss_dir = tmp_path / "screenshots"
        assert not ss_dir.exists()

    async def test_replay_generation(self, tmp_path: Path) -> None:
        session = FakeSession()
        page = FakePage(b"replay-screenshot")
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=True)

        async with observe_stagehand(session, config=cfg, page=page) as t:
            await t.act("click button")

        replay_path = t.save_replay()
        assert Path(replay_path).exists()
        content = Path(replay_path).read_text()
        assert "replayData" in content

    async def test_generate_replay_string(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(output_dir=str(tmp_path), capture_screenshots=False)

        async with observe_stagehand(session, config=cfg) as t:
            await t.act("click button")

        html = t.generate_replay()
        assert isinstance(html, str)
        assert "replayData" in html

    async def test_api_reporting(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(
            output_dir=str(tmp_path),
            capture_screenshots=False,
            api_url="http://localhost:8000",
            api_key="cu_test_key",
        )

        with patch(
            "computeruse._reporting.report_to_api", new_callable=AsyncMock
        ) as mock_report:
            mock_report.return_value = True
            async with observe_stagehand(session, config=cfg) as t:
                await t.act("click login")

            mock_report.assert_awaited_once()
            kwargs = mock_report.call_args.kwargs
            assert kwargs["task_id"] == t._run_id
            assert kwargs["status"] == "completed"
            assert kwargs["api_url"] == "http://localhost:8000"
            assert kwargs["api_key"] == "cu_test_key"
            assert kwargs["task_description"] == "Stagehand session"

    async def test_api_reporting_on_failure(self, tmp_path: Path) -> None:
        session = FakeSession()
        session.act = AsyncMock(side_effect=RuntimeError("boom"))
        cfg = StagehandConfig(
            output_dir=str(tmp_path),
            capture_screenshots=False,
            api_url="http://localhost:8000",
            api_key="cu_test_key",
        )

        with patch(
            "computeruse._reporting.report_to_api", new_callable=AsyncMock
        ) as mock_report:
            mock_report.return_value = True
            with pytest.raises(RuntimeError):
                async with observe_stagehand(session, config=cfg) as t:
                    await t.act("click login")

            mock_report.assert_awaited_once()
            kwargs = mock_report.call_args.kwargs
            assert kwargs["status"] == "failed"

    async def test_no_reporting_without_config(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(
            output_dir=str(tmp_path), capture_screenshots=False
        )

        with patch(
            "computeruse._reporting.report_to_api", new_callable=AsyncMock
        ) as mock_report:
            async with observe_stagehand(session, config=cfg) as t:
                await t.act("click login")

            mock_report.assert_not_awaited()

    async def test_saves_on_exception(self, tmp_path: Path) -> None:
        session = FakeSession()
        session.act = AsyncMock(side_effect=ValueError("bad input"))
        cfg = StagehandConfig(
            output_dir=str(tmp_path), capture_screenshots=False
        )

        with pytest.raises(ValueError):
            async with observe_stagehand(session, config=cfg) as t:
                await t.act("bad action")

        # Metadata should still be saved despite exception
        runs_dir = tmp_path / "runs"
        assert runs_dir.exists()
        metadata_file = runs_dir / f"{t._run_id}.json"
        assert metadata_file.exists()

    async def test_multiple_step_types(self, tmp_path: Path) -> None:
        session = FakeSession()
        cfg = StagehandConfig(
            output_dir=str(tmp_path), capture_screenshots=False
        )

        async with observe_stagehand(session, config=cfg) as t:
            await t.navigate("https://example.com")
            await t.act("click login")
            await t.extract("get prices", schema={"prices": "list[float]"})
            await t.observe("find buttons")

        assert len(t.steps) == 4
        types = [s.action_type for s in t.steps]
        assert types == [
            ActionType.NAVIGATE,
            ActionType.ACT,
            ActionType.EXTRACT,
            ActionType.OBSERVE,
        ]
        # All succeeded
        assert all(s.success for s in t.steps)
        # Step numbers are sequential
        assert [s.step_number for s in t.steps] == [1, 2, 3, 4]
