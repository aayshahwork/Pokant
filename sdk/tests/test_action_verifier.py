"""Tests for computeruse.action_verifier — post-action verification."""

from __future__ import annotations

from computeruse.action_verifier import ActionVerifier, VerificationResult


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
        return {"title": "Test", "elements": 5}

    async def wait_for_selector(self, sel: str, **kw: object) -> bool:
        return True


class NoElementPage(MockPage):
    async def wait_for_selector(self, sel: str, **kw: object) -> None:
        raise Exception("timeout")


class BrokenPage(MockPage):
    async def content(self) -> str:
        raise Exception("page crashed")

    async def wait_for_selector(self, sel: str, **kw: object) -> None:
        raise Exception("selector failed")


class FormPage(MockPage):
    async def eval_on_selector(self, sel: str, expr: str) -> str:
        return "test@email.com"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_url_pattern_pass() -> None:
    v = ActionVerifier()
    page = MockPage(url="https://example.com/dashboard")
    result = await v.verify_action(
        page, "navigate", expected_url_pattern=r"example\.com/dashboard"
    )
    assert result.passed is True
    assert result.checks_run == 1
    assert result.checks_passed == 1


async def test_url_pattern_fail() -> None:
    v = ActionVerifier()
    page = MockPage(url="https://wrong.com")
    result = await v.verify_action(
        page, "navigate", expected_url_pattern=r"example\.com"
    )
    assert result.has_critical_failure is True
    assert result.passed is False


async def test_element_present() -> None:
    v = ActionVerifier()
    page = MockPage()
    result = await v.verify_action(page, "click", expected_element="#submit")
    assert result.passed is True
    assert result.checks_passed == 1


async def test_element_missing() -> None:
    v = ActionVerifier()
    page = NoElementPage()
    result = await v.verify_action(page, "click", expected_element="#missing")
    assert len(result.warnings) > 0
    assert result.warnings[0]["check"] == "element_presence"


async def test_text_present() -> None:
    v = ActionVerifier()
    page = MockPage(content="<html>Welcome to dashboard</html>")
    result = await v.verify_action(page, "navigate", expected_text="Welcome")
    assert result.passed is True


async def test_text_missing() -> None:
    v = ActionVerifier()
    page = MockPage(content="<html>Not here</html>")
    result = await v.verify_action(page, "navigate", expected_text="Welcome")
    assert len(result.warnings) > 0
    assert result.warnings[0]["check"] == "text_presence"


async def test_form_value_correct() -> None:
    v = ActionVerifier()
    page = FormPage()
    result = await v._check_form_value(page, "#email", "test@email.com")
    assert result is None  # No failure


async def test_all_checks_empty() -> None:
    v = ActionVerifier()
    page = MockPage()
    result = await v.verify_action(page, "click")
    assert result.passed is True
    assert result.checks_run == 0


async def test_page_error_handling() -> None:
    v = ActionVerifier()
    page = BrokenPage()
    result = await v.verify_action(
        page, "click", expected_element="#btn", expected_text="Hello"
    )
    assert isinstance(result, VerificationResult)
    # Should not crash — element check returns warning, text check swallowed
    assert result.passed is True
