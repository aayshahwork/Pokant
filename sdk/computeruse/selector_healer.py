"""computeruse/selector_healer.py — Heal broken selectors during replay.

Tries alternate selector strategies and Playwright built-in locators
when the primary selector fails.  All async methods accept a duck-typed
page object and never import Playwright directly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class SelectorHealer:
    """Heals broken selectors by trying alternates and text-based search."""

    async def heal(
        self,
        page: Any,
        selectors: List[Dict[str, Any]],
        failed_index: int = 0,
    ) -> Optional[str]:
        """Try alternate selectors, skipping the one that failed.

        Returns a working Playwright selector string, or None if all fail.
        """
        if not selectors:
            return None
        if failed_index >= len(selectors):
            failed_index = 0

        candidates = (
            selectors[:failed_index] + selectors[failed_index + 1:]
        )
        for sel_dict in candidates:
            converted = self._convert_selector(sel_dict)
            if not converted:
                continue
            try:
                el = await page.wait_for_selector(converted, timeout=3000)
                if el:
                    return converted
            except Exception:
                continue
        return None

    async def heal_with_text_search(
        self,
        page: Any,
        element_text: str = "",
        element_role: str = "",
        element_tag: str = "",
    ) -> Optional[str]:
        """Last-resort healing using Playwright built-in locator strategies.

        Tries role+name, text content, and tag+text combinations.
        Returns a working selector string, or None if all fail.
        """
        strategies: list[str] = []

        # Escape double quotes in text to prevent selector injection
        safe_text = element_text.replace('"', '\\"') if element_text else ""

        # Strategy 1: role + name
        if element_role and safe_text:
            strategies.append(f'role={element_role}[name="{safe_text}"]')

        # Strategy 2: text content
        if safe_text:
            strategies.append(f"text={element_text}")

        # Strategy 3: tag + :has-text()
        if element_tag and safe_text:
            strategies.append(f'{element_tag}:has-text("{safe_text}")')

        # Strategy 4: just role
        if element_role:
            strategies.append(f"role={element_role}")

        for selector in strategies:
            try:
                el = await page.wait_for_selector(selector, timeout=3000)
                if el:
                    return selector
            except Exception:
                continue

        return None

    @staticmethod
    def _convert_selector(selector_dict: Dict[str, Any]) -> str:
        """Convert a selector dict to a Playwright selector string.

        Returns empty string on failure or for non-browser selectors.
        """
        sel_type = selector_dict.get("type", "")
        value = selector_dict.get("value", "")

        if not value:
            return ""

        if sel_type == "css":
            return value
        if sel_type == "text":
            return f"text={value}"
        if sel_type == "role":
            return value  # already in "role=button[name='X']" format
        if sel_type == "name":
            return f'[name="{value}"]'
        if sel_type in ("uia", "coordinate", "window_control"):
            # Desktop selectors — not usable in browser
            return ""

        # Unknown type — try using value as-is (CSS)
        return value
