"""Tests for computeruse.compiler — workflow compilation."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from computeruse.compiler import CompilationError, WorkflowCompiler
from computeruse.models import CompiledWorkflow

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_enriched_step(
    action_type: str = "click",
    description: str = "Click the submit button",
    selectors: list | None = None,
    intent: str = "Click Submit button",
    fill_value_template: str = "",
    pre_url: str = "https://example.com",
    expected_url_pattern: str = "",
    expected_element: str = "",
    expected_text: str = "",
) -> dict:
    """Build a realistic enriched step dict (matches _serialize_step output)."""
    step: dict = {
        "action_type": action_type,
        "description": description,
        "duration_ms": 150,
        "success": True,
        "tokens_in": 100,
        "tokens_out": 50,
        "screenshot_path": "",
    }
    if selectors is not None:
        step["selectors"] = selectors
    else:
        step["selectors"] = [
            {"type": "css", "value": "#submit-btn", "confidence": 0.9},
            {"type": "text", "value": "Submit", "confidence": 0.7},
        ]
    if intent:
        step["intent"] = intent
    if fill_value_template:
        step["fill_value_template"] = fill_value_template
    if pre_url:
        step["pre_url"] = pre_url
    if expected_url_pattern:
        step["expected_url_pattern"] = expected_url_pattern
    if expected_element:
        step["expected_element"] = expected_element
    if expected_text:
        step["expected_text"] = expected_text
    return step


def _make_run_json(
    status: str = "completed",
    steps: list | None = None,
    task_id: str = "test-task-001",
) -> dict:
    """Build a run metadata dict matching wrap.py _save_run_metadata format."""
    return {
        "task_id": task_id,
        "status": status,
        "step_count": len(steps) if steps else 0,
        "cost_cents": 0.5,
        "error_category": None,
        "error": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "completed_at": "2026-01-01T00:01:00+00:00",
        "duration_ms": 60000,
        "steps": steps or [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_compile_from_run(tmp_path: Path) -> None:
    """Load enriched run JSON -> valid CompiledWorkflow."""
    steps = [
        _make_enriched_step(
            action_type="navigate",
            description="goto(https://example.com)",
            intent="Navigate to example.com",
            pre_url="https://example.com",
        ),
        _make_enriched_step(
            action_type="click",
            description="Click Submit",
            intent="Click Submit button",
        ),
    ]
    run_data = _make_run_json(steps=steps)
    run_file = tmp_path / "test-task-001.json"
    run_file.write_text(json.dumps(run_data))

    compiler = WorkflowCompiler()
    wf = compiler.compile_from_run(str(run_file))

    assert isinstance(wf, CompiledWorkflow)
    assert wf.source_task_id == "test-task-001"
    assert len(wf.steps) == 2
    assert wf.steps[0].action_type == "goto"
    assert wf.steps[1].action_type == "click"


def test_compile_missing_enrichment() -> None:
    """Steps without selectors still compile (empty selectors list)."""
    steps = [
        {
            "action_type": "click",
            "description": "Click something",
            "duration_ms": 100,
            "success": True,
            "tokens_in": 0,
            "tokens_out": 0,
            "screenshot_path": "",
        },
    ]

    compiler = WorkflowCompiler()
    wf = compiler.compile_from_steps(steps)

    assert len(wf.steps) == 1
    assert wf.steps[0].selectors == []
    # Intent should be inferred
    assert wf.steps[0].intent != ""


def test_compile_failed_run(tmp_path: Path) -> None:
    """Failed run -> CompilationError."""
    run_data = _make_run_json(status="failed", steps=[_make_enriched_step()])
    run_file = tmp_path / "failed-run.json"
    run_file.write_text(json.dumps(run_data))

    compiler = WorkflowCompiler()
    with pytest.raises(CompilationError, match="status="):
        compiler.compile_from_run(str(run_file))


def test_parameter_detection() -> None:
    """fill_value_template={{email}} -> parameters populated."""
    steps = [
        _make_enriched_step(
            action_type="type",
            fill_value_template="{{email}}",
            description="Type email",
            intent="Enter email",
        ),
        _make_enriched_step(
            action_type="type",
            fill_value_template="{{phone}}",
            description="Type phone",
            intent="Enter phone",
        ),
        _make_enriched_step(
            action_type="click",
            description="Click submit",
            intent="Click Submit",
        ),
    ]

    compiler = WorkflowCompiler()
    wf = compiler.compile_from_steps(steps)

    assert "email" in wf.parameters
    assert "phone" in wf.parameters
    assert isinstance(wf.parameters, dict)


def test_playwright_script() -> None:
    """Generated script passes ast.parse()."""
    steps = [
        _make_enriched_step(
            action_type="navigate",
            intent="Navigate to site",
            pre_url="https://example.com",
        ),
        _make_enriched_step(
            action_type="type",
            fill_value_template="{{email}}",
            intent="Enter email address",
            selectors=[
                {"type": "css", "value": "#email", "confidence": 0.9},
            ],
        ),
        _make_enriched_step(
            action_type="click",
            intent="Click Login",
            selectors=[
                {"type": "css", "value": "#login-btn", "confidence": 0.9},
            ],
        ),
    ]

    compiler = WorkflowCompiler()
    wf = compiler.compile_from_steps(steps)

    script = compiler.generate_playwright_script(wf)

    # Must be valid Python
    ast.parse(script)

    # Must contain PARAMS
    assert "PARAMS" in script
    assert '"email"' in script


def test_save_workflow(tmp_path: Path) -> None:
    """Save -> reload JSON round-trip."""
    steps = [_make_enriched_step()]
    compiler = WorkflowCompiler()
    wf = compiler.compile_from_steps(
        steps, source_task_id="tid-001"
    )

    out_dir = str(tmp_path / "workflows")
    path = compiler.save_workflow(wf, output_dir=out_dir)

    with open(path) as f:
        loaded = json.load(f)

    assert loaded["source_task_id"] == "tid-001"
    assert len(loaded["steps"]) == 1


def test_selector_sorting() -> None:
    """Selectors are sorted by confidence descending."""
    steps = [
        _make_enriched_step(
            selectors=[
                {"type": "text", "value": "Submit", "confidence": 0.5},
                {"type": "css", "value": "#btn", "confidence": 0.95},
                {"type": "css", "value": '[aria-label="Go"]', "confidence": 0.8},
            ],
        ),
    ]

    compiler = WorkflowCompiler()
    wf = compiler.compile_from_steps(steps)

    sels = wf.steps[0].selectors
    confidences = [s["confidence"] for s in sels]
    assert confidences == sorted(confidences, reverse=True)
    assert sels[0]["confidence"] == 0.95
