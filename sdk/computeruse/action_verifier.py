"""computeruse/action_verifier.py — Post-action verification.

Verifies that browser actions achieved their expected outcomes.
Every check is wrapped in try/except — verification must never break
the workflow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VerificationResult:
    """Result of verifying an action succeeded."""

    passed: bool
    checks_run: int
    checks_passed: int
    failures: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)

    @property
    def has_critical_failure(self) -> bool:
        """URL mismatch = critical. Element/text missing = warning."""
        return any(f["check"] == "url_pattern" for f in self.failures)


class ActionVerifier:
    """Verifies that browser actions achieved their expected outcomes.

    Person A will call verify_action() after each step in track.py and
    wrap.py.  The page parameter is duck-typed (Playwright Page).
    """

    async def verify_action(
        self,
        page: Any,
        action_type: str,
        expected_url_pattern: str = "",
        expected_element: str = "",
        expected_text: str = "",
        pre_url: str = "",
    ) -> VerificationResult:
        """Verify an action produced expected results.

        All checks are optional — only runs checks where expected_* is
        non-empty.  Never raises — returns VerificationResult with pass/fail.
        """
        failures: list[dict] = []
        warnings: list[dict] = []
        checks_run = 0
        checks_passed = 0

        # URL pattern check → critical failure
        if expected_url_pattern:
            checks_run += 1
            result = await self._check_url(page, expected_url_pattern)
            if result:
                failures.append(result)
            else:
                checks_passed += 1

        # Element presence check → warning
        if expected_element:
            checks_run += 1
            result = await self._check_element(page, expected_element)
            if result:
                warnings.append(result)
            else:
                checks_passed += 1

        # Text presence check → warning
        if expected_text:
            checks_run += 1
            result = await self._check_text(page, expected_text)
            if result:
                warnings.append(result)
            else:
                checks_passed += 1

        # URL changed check → warning (only for navigate with pre_url)
        if action_type == "navigate" and pre_url:
            checks_run += 1
            result = await self._check_url_changed(page, pre_url, action_type)
            if result:
                warnings.append(result)
            else:
                checks_passed += 1

        passed = len(failures) == 0

        return VerificationResult(
            passed=passed,
            checks_run=checks_run,
            checks_passed=checks_passed,
            failures=failures,
            warnings=warnings,
        )

    async def _check_url(self, page: Any, pattern: str) -> dict | None:
        """Check current URL matches regex pattern. Returns failure dict or None."""
        try:
            url = await self._safe_get_url(page)
            if not re.search(pattern, url):
                return {
                    "check": "url_pattern",
                    "expected": pattern,
                    "actual": url,
                }
        except Exception:
            pass
        return None

    async def _check_element(self, page: Any, selector: str) -> dict | None:
        """Check element exists on page. Returns failure dict or None."""
        try:
            el = await page.wait_for_selector(selector, timeout=3000)
            if not el:
                return {
                    "check": "element_presence",
                    "expected": selector,
                    "actual": "not found",
                }
        except Exception:
            return {
                "check": "element_presence",
                "expected": selector,
                "actual": "timeout",
            }
        return None

    async def _check_text(self, page: Any, text: str) -> dict | None:
        """Check text appears on page. Returns failure dict or None."""
        try:
            content = await page.content()
            if text not in content:
                return {
                    "check": "text_presence",
                    "expected": text,
                    "actual": "not found",
                }
        except Exception:
            pass
        return None

    async def _check_url_changed(
        self, page: Any, pre_url: str, action_type: str
    ) -> dict | None:
        """For navigate actions, verify URL actually changed."""
        if action_type != "navigate" or not pre_url:
            return None
        try:
            current = await self._safe_get_url(page)
            if current == pre_url:
                return {
                    "check": "url_changed",
                    "expected": "different from " + pre_url,
                    "actual": current,
                }
        except Exception:
            pass
        return None

    async def _check_form_value(
        self, page: Any, selector: str, expected_value: str
    ) -> dict | None:
        """After a fill action, verify the input has the expected value."""
        if not selector or not expected_value:
            return None
        try:
            actual = await page.eval_on_selector(selector, "el => el.value")
            if actual != expected_value:
                return {
                    "check": "form_value",
                    "expected": expected_value,
                    "actual": actual,
                }
        except Exception:
            pass
        return None

    async def _safe_get_url(self, page: Any) -> str:
        """Duck-typed URL access — works with Playwright Page or mocks."""
        try:
            return page.url if hasattr(page, "url") else ""
        except Exception:
            return ""
