"""Tests for computeruse.step_enrichment — rich step data capture."""

from __future__ import annotations

from computeruse.step_enrichment import (
    detect_parameterizable_values,
    extract_desktop_selectors,
    extract_element_metadata,
    extract_selectors,
    infer_intent_from_step,
    snapshot_dom_hash,
)


# ---------------------------------------------------------------------------
# Mock page classes
# ---------------------------------------------------------------------------


class MockPage:
    def __init__(
        self, url: str = "https://example.com", content: str = "<html>test</html>"
    ) -> None:
        self.url = url
        self._content = content

    async def content(self) -> str:
        return self._content

    async def eval_on_selector(self, sel: str, expr: str) -> str:
        return "Submit"

    async def evaluate(self, expr: str) -> dict:
        return {
            "url": self.url,
            "title": "Test Page",
            "count": 5,
            "elements": ["BUTTON:Submit", "INPUT:", "A:Home"],
        }

    async def wait_for_selector(self, sel: str, **kw: object) -> bool:
        return True


class MetadataPage(MockPage):
    async def eval_on_selector(self, sel: str, expr: str) -> dict:
        return {
            "text": "Submit",
            "tag": "button",
            "role": "button",
            "aria_label": "",
            "placeholder": "",
            "name": "submit",
            "type": "submit",
        }


class BrokenPage:
    url: str = "https://example.com"

    async def eval_on_selector(self, sel: str, expr: str) -> None:
        raise Exception("eval failed")

    async def evaluate(self, expr: str) -> None:
        raise Exception("evaluate failed")

    async def content(self) -> str:
        raise Exception("content failed")

    async def wait_for_selector(self, sel: str, **kw: object) -> None:
        raise Exception("selector failed")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_extract_selectors() -> None:
    """Mock page.eval_on_selector, verify multiple strategies."""
    page = MockPage()
    selectors = await extract_selectors(page, "#btn")
    assert len(selectors) >= 1
    # First strategy is always the original CSS selector
    assert selectors[0]["type"] == "css"
    assert selectors[0]["value"] == "#btn"
    assert selectors[0]["confidence"] == 0.9
    # Text strategy should be present (mock returns "Submit")
    text_entries = [s for s in selectors if s["type"] == "text"]
    assert len(text_entries) >= 1
    assert text_entries[0]["value"] == "Submit"


async def test_extract_element_metadata() -> None:
    """Mock evaluate, verify all fields."""
    page = MetadataPage()
    meta = await extract_element_metadata(page, "#btn")
    assert meta["text"] == "Submit"
    assert meta["tag"] == "button"
    assert meta["role"] == "button"
    assert meta["name"] == "submit"
    assert meta["type"] == "submit"


async def test_snapshot_dom_hash() -> None:
    """Same page -> same hash, different page -> different hash."""
    page1 = MockPage(url="https://example.com")
    page2 = MockPage(url="https://other.com")

    hash1 = await snapshot_dom_hash(page1)
    hash1_again = await snapshot_dom_hash(page1)
    hash2 = await snapshot_dom_hash(page2)

    assert hash1 == hash1_again  # Deterministic
    assert hash1 != hash2  # Different page state
    assert len(hash1) == 64  # SHA-256 hex digest


def test_infer_intent() -> None:
    """Various action/element combos -> correct intent strings."""
    # Click + button
    intent, detail = infer_intent_from_step(
        "click", {"text": "Submit", "tag": "button"}
    )
    assert "Submit" in intent
    assert "button" in intent.lower()

    # Fill + input
    intent2, detail2 = infer_intent_from_step(
        "fill", {"placeholder": "Email"}
    )
    assert "Email" in intent2

    # Navigate + url
    intent3, detail3 = infer_intent_from_step(
        "navigate", {"url": "https://example.com/page"}
    )
    assert "example.com" in intent3

    # Select
    intent4, detail4 = infer_intent_from_step(
        "select", {"text": "California"}
    )
    assert "California" in intent4
    assert "dropdown" in detail4.lower()


def test_detect_parameterizable() -> None:
    """Pattern matching for parameterizable values."""
    assert detect_parameterizable_values("user@test.com") == "{{email}}"
    assert detect_parameterizable_values("1234567890") == "{{phone}}"
    assert detect_parameterizable_values("2024-01-15") == "{{date}}"
    assert detect_parameterizable_values("01/15/2024") == "{{date}}"
    assert detect_parameterizable_values("123-45-6789") == "{{ssn}}"
    assert detect_parameterizable_values("90210") == "{{zip_code}}"
    assert detect_parameterizable_values("https://example.com") == "{{url}}"
    assert detect_parameterizable_values("California") == "California"
    assert detect_parameterizable_values("") == ""


def test_desktop_selectors() -> None:
    """Verify UIA + name + coordinate strategies."""
    selectors = extract_desktop_selectors("Notepad", "Button", "Save", (100, 200))
    types = [s["type"] for s in selectors]
    assert "uia" in types
    assert "name" in types
    assert "coordinate" in types
    assert len(selectors) >= 3
    # UIA should have highest confidence
    uia = next(s for s in selectors if s["type"] == "uia")
    assert uia["value"] == "Button:Save"
    assert uia["confidence"] == 0.9


async def test_failure_handling() -> None:
    """page.evaluate throws -> empty defaults, no crash."""
    page = BrokenPage()

    selectors = await extract_selectors(page, "#btn")
    assert isinstance(selectors, list)
    # Should still have the original CSS selector (no page call needed)
    assert len(selectors) >= 1
    assert selectors[0]["value"] == "#btn"

    meta = await extract_element_metadata(page, "#btn")
    assert meta == {}

    hash_val = await snapshot_dom_hash(page)
    assert hash_val == ""
