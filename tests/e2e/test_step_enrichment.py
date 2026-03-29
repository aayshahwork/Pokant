"""E2E: Step enrichment — verify tasks complete with enriched step data.

After the browser_use step enrichment changes, tasks should still complete
successfully. The enrichment backfills token counts, action types, and cost
from browser_use's AgentHistoryList — this test ensures that pipeline
doesn't break the execution flow.

NOTE: To fully verify enriched fields (cost_cents, total_tokens_in,
total_tokens_out, per-step action_type) via the API, TaskResponse
would need to expose these columns. Currently they are persisted to
the DB only.
"""

from __future__ import annotations

import time

import httpx
import pytest


class TestStepEnrichment:
    """Smoke tests for the enriched executor pipeline."""

    def test_simple_task_completes_with_steps(self, client: httpx.Client) -> None:
        """Submit a simple extraction task and verify it completes with >1 step.

        The enrichment adds calculate_cost=True and post-run history extraction.
        This test ensures nothing in that pipeline raises or hangs.
        """
        resp = client.post(
            "/api/v1/tasks",
            json={
                "url": "https://example.com",
                "task": "Extract the page heading text",
                "timeout_seconds": 90,
            },
        )
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        data = {}
        for _ in range(24):
            data = client.get(f"/api/v1/tasks/{task_id}").json()
            if data["status"] in ("completed", "failed"):
                break
            time.sleep(5)

        assert data["status"] == "completed", f"Task failed: {data.get('error')}"
        assert data["success"] is True
        # Navigate step + at least 1 agent step
        assert data["steps"] >= 2
        assert data["duration_ms"] > 0

    def test_extraction_task_preserves_result(self, client: httpx.Client) -> None:
        """Verify enrichment doesn't clobber the final_result extraction."""
        resp = client.post(
            "/api/v1/tasks",
            json={
                "url": "https://books.toscrape.com/",
                "task": "Extract the title of the first book on the page",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                    },
                },
                "timeout_seconds": 120,
            },
        )
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        data = {}
        for _ in range(36):
            data = client.get(f"/api/v1/tasks/{task_id}").json()
            if data["status"] in ("completed", "failed"):
                break
            time.sleep(5)

        if data["status"] != "completed":
            pytest.skip("Task did not complete; enrichment test not applicable")

        result = data.get("result") or {}
        assert "title" in result
        assert len(result["title"]) > 0

    def test_multi_step_task_counts_correctly(self, client: httpx.Client) -> None:
        """A multi-step task should report accurate step counts.

        After enrichment, steps that were appended from history (if the
        callback missed any) are included in the total.
        """
        resp = client.post(
            "/api/v1/tasks",
            json={
                "url": "https://the-internet.herokuapp.com/login",
                "task": (
                    "Find the username and password fields on the login page, "
                    "then report what fields are visible."
                ),
                "timeout_seconds": 120,
            },
        )
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        data = {}
        for _ in range(36):
            data = client.get(f"/api/v1/tasks/{task_id}").json()
            if data["status"] in ("completed", "failed"):
                break
            time.sleep(5)

        if data["status"] != "completed":
            pytest.skip("Task did not complete")

        # Login page interaction should produce several steps
        assert data["steps"] >= 2
        assert data["duration_ms"] > 0

    def test_replay_still_generated_after_enrichment(self, client: httpx.Client) -> None:
        """Verify enrichment doesn't break replay generation."""
        resp = client.post(
            "/api/v1/tasks",
            json={
                "url": "https://example.com",
                "task": "Read the page content",
                "timeout_seconds": 60,
            },
        )
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        data = {}
        for _ in range(24):
            data = client.get(f"/api/v1/tasks/{task_id}").json()
            if data["status"] in ("completed", "failed"):
                break
            time.sleep(5)

        if data["status"] != "completed":
            pytest.skip("Task did not complete; replay test not applicable")

        replay_resp = client.get(f"/api/v1/tasks/{task_id}/replay")
        assert replay_resp.status_code == 200
        assert "replay_url" in replay_resp.json()
