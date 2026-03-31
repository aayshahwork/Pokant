"""Tests for computeruse.replay_generator — HTML replay generation."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from computeruse.models import ActionType, StepData
from computeruse.replay_generator import ReplayGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(
    step_number: int = 1,
    action_type: str = "click",
    description: str = "Clicked button",
    screenshot_bytes: bytes | None = None,
    tokens_in: int = 100,
    tokens_out: int = 50,
    duration_ms: int = 500,
    success: bool = True,
    error: str | None = None,
) -> StepData:
    return StepData(
        step_number=step_number,
        timestamp=datetime(2025, 6, 15, 12, 0, step_number, tzinfo=timezone.utc),
        action_type=action_type,
        description=description,
        screenshot_bytes=screenshot_bytes,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        duration_ms=duration_ms,
        success=success,
        error=error,
    )


def _make_metadata(**overrides) -> dict:
    defaults = {
        "task_id": "test-task-001",
        "url": "https://example.com",
        "task": "Extract the page title",
        "generated_at": "2025-06-15T12:00:00Z",
        "duration_ms": 3000,
        "success": True,
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# Template loading
# ===================================================================

class TestTemplateFiles:
    def test_replay_html_exists(self) -> None:
        templates = Path(__file__).parent.parent / "computeruse" / "templates"
        assert (templates / "replay.html").is_file()

    def test_tailwind_css_exists(self) -> None:
        templates = Path(__file__).parent.parent / "computeruse" / "templates"
        assert (templates / "tailwind-subset.css").is_file()

    def test_replay_html_has_placeholder(self) -> None:
        templates = Path(__file__).parent.parent / "computeruse" / "templates"
        html = (templates / "replay.html").read_text()
        assert "/* __TAILWIND_CSS__ */" in html
        assert '__REPLAY_DATA__' in html


# ===================================================================
# _build_replay_json
# ===================================================================

class TestBuildReplayJson:
    def test_basic_structure(self) -> None:
        steps = [_make_step(1), _make_step(2)]
        gen = ReplayGenerator(steps=steps, task_metadata=_make_metadata())
        data = gen._build_replay_json()

        assert data["task_id"] == "test-task-001"
        assert data["url"] == "https://example.com"
        assert data["task_description"] == "Extract the page title"
        assert data["total_steps"] == 2
        assert data["duration_ms"] == 3000
        assert data["success"] is True
        assert len(data["steps"]) == 2

    def test_empty_steps(self) -> None:
        gen = ReplayGenerator(steps=[], task_metadata=_make_metadata())
        data = gen._build_replay_json()
        assert data["total_steps"] == 0
        assert data["steps"] == []

    def test_missing_metadata_keys_default(self) -> None:
        gen = ReplayGenerator(steps=[], task_metadata={})
        data = gen._build_replay_json()
        assert data["task_id"] == ""
        assert data["url"] == ""
        assert data["duration_ms"] == 0
        assert data["success"] is False


# ===================================================================
# _serialize_step
# ===================================================================

class TestSerializeStep:
    def test_step_with_screenshot(self) -> None:
        img = b"\xff\xd8\xff\xe0fake-jpeg-data"
        step = _make_step(1, screenshot_bytes=img)
        gen = ReplayGenerator(steps=[step], task_metadata=_make_metadata())
        serialized = gen._serialize_step(step)

        assert serialized["step_number"] == 1
        assert serialized["action_type"] == "click"
        assert serialized["description"] == "Clicked button"
        assert serialized["screenshot"] is not None
        assert isinstance(serialized["screenshot"], str)
        assert len(serialized["screenshot"]) > 0
        # Verify it's valid base64
        import base64
        decoded = base64.standard_b64decode(serialized["screenshot"])
        assert decoded == img

    def test_step_without_screenshot(self) -> None:
        step = _make_step(1, screenshot_bytes=None)
        gen = ReplayGenerator(steps=[step], task_metadata=_make_metadata())
        serialized = gen._serialize_step(step)
        assert serialized["screenshot"] is None

    def test_step_tokens_and_duration(self) -> None:
        step = _make_step(1, tokens_in=1500, tokens_out=300, duration_ms=2500)
        gen = ReplayGenerator(steps=[step], task_metadata=_make_metadata())
        serialized = gen._serialize_step(step)
        assert serialized["tokens_in"] == 1500
        assert serialized["tokens_out"] == 300
        assert serialized["duration_ms"] == 2500

    def test_step_error(self) -> None:
        step = _make_step(1, success=False, error="Element not found")
        gen = ReplayGenerator(steps=[step], task_metadata=_make_metadata())
        serialized = gen._serialize_step(step)
        assert serialized["success"] is False
        assert serialized["error"] == "Element not found"

    def test_step_timestamp_iso(self) -> None:
        step = _make_step(1)
        gen = ReplayGenerator(steps=[step], task_metadata=_make_metadata())
        serialized = gen._serialize_step(step)
        assert "2025-06-15" in serialized["timestamp"]

    def test_step_action_type_str(self) -> None:
        """ActionType enum values serialize as plain strings."""
        step = _make_step(1, action_type=ActionType.NAVIGATE)
        gen = ReplayGenerator(steps=[step], task_metadata=_make_metadata())
        serialized = gen._serialize_step(step)
        assert serialized["action_type"] == "navigate"

    def test_unicode_description(self) -> None:
        step = _make_step(1, description="Clicked '提交' button")
        gen = ReplayGenerator(steps=[step], task_metadata=_make_metadata())
        serialized = gen._serialize_step(step)
        assert serialized["description"] == "Clicked '提交' button"


# ===================================================================
# generate() — full HTML output
# ===================================================================

class TestGenerate:
    def test_writes_valid_html(self) -> None:
        steps = [
            _make_step(1, action_type="navigate", description="Nav to page",
                       screenshot_bytes=b"\xff\xd8fake-jpeg"),
            _make_step(2, action_type="click", description="Clicked submit"),
        ]
        gen = ReplayGenerator(steps=steps, task_metadata=_make_metadata())

        with tempfile.TemporaryDirectory() as tmpdir:
            out = gen.generate(f"{tmpdir}/replay.html")
            assert Path(out).exists()
            html = Path(out).read_text()

            # CSS was inlined (placeholder replaced)
            assert "/* __TAILWIND_CSS__ */" not in html
            assert "box-sizing: border-box" in html

            # Replay data was inlined
            assert '__REPLAY_DATA__' not in html
            assert "test-task-001" in html

    def test_replay_data_is_valid_json(self) -> None:
        steps = [_make_step(1)]
        gen = ReplayGenerator(steps=steps, task_metadata=_make_metadata())

        with tempfile.TemporaryDirectory() as tmpdir:
            out = gen.generate(f"{tmpdir}/replay.html")
            html = Path(out).read_text()

            # Extract the JSON between "var replayData = " and ";\n"
            marker = "var replayData = "
            start = html.index(marker) + len(marker)
            end = html.index(";\n", start)
            json_str = html[start:end]
            data = json.loads(json_str)

            assert data["task_id"] == "test-task-001"
            assert len(data["steps"]) == 1
            assert data["steps"][0]["step_number"] == 1

    def test_creates_parent_directories(self) -> None:
        gen = ReplayGenerator(
            steps=[_make_step(1)],
            task_metadata=_make_metadata(),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = f"{tmpdir}/deep/nested/dir/replay.html"
            out = gen.generate(nested)
            assert Path(out).exists()

    def test_empty_steps_produces_valid_html(self) -> None:
        gen = ReplayGenerator(steps=[], task_metadata=_make_metadata())
        with tempfile.TemporaryDirectory() as tmpdir:
            out = gen.generate(f"{tmpdir}/empty.html")
            html = Path(out).read_text()
            assert "<html" in html
            assert "test-task-001" in html

    def test_returns_output_path(self) -> None:
        gen = ReplayGenerator(steps=[], task_metadata=_make_metadata())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/out.html"
            result = gen.generate(path)
            assert result == path

    def test_multiple_screenshots_inlined(self) -> None:
        steps = [
            _make_step(i, screenshot_bytes=f"img-{i}".encode())
            for i in range(1, 4)
        ]
        gen = ReplayGenerator(steps=steps, task_metadata=_make_metadata())
        with tempfile.TemporaryDirectory() as tmpdir:
            out = gen.generate(f"{tmpdir}/replay.html")
            html = Path(out).read_text()
            # Each step's screenshot should be base64-encoded in the JSON
            marker = "var replayData = "
            start = html.index(marker) + len(marker)
            end = html.index(";\n", start)
            data = json.loads(html[start:end])
            for step in data["steps"]:
                assert step["screenshot"] is not None
