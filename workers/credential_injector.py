"""
workers/credential_injector.py — Secure credential injection into browser login forms.

Fills login form fields via Playwright page.fill(). Credentials are NEVER
logged, stringified, or serialized.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Heuristic selectors for login form detection.
# Priority order: first match wins.
_PASSWORD_SELECTOR = 'input[type="password"]'
_USERNAME_SELECTORS = [
    'input[type="email"]',           # 1st: explicit email inputs
    'input[name*="user"]',           # 2nd: name contains "user" (intentionally broad — password field anchor is primary signal)
    'input[name*="email"]',          # 3rd: name contains "email"
    'input[name*="login"]',          # 4th: name contains "login"
    'input[type="text"]',            # 5th: fallback generic text
]


class AuthFormUnrecognizedError(Exception):
    """Raised when the credential injection heuristic cannot find the login form."""


class CredentialInjector:
    """Injects credentials into browser login forms via Playwright page.fill().

    Credentials are NEVER logged, stringified, or serialized.
    """

    async def inject(
        self,
        page: Any,  # playwright.async_api.Page
        credentials: dict[str, str],
        selectors: dict[str, str] | None = None,
    ) -> bool:
        """Fill login form fields with credentials.

        Args:
            page: Playwright Page instance.
            credentials: Dict with 'username' and 'password' keys.
            selectors: Optional dict with 'username_selector' and 'password_selector'.
                       If None, heuristic detection is used.

        Returns:
            True on success.

        Raises:
            AuthFormUnrecognizedError: If the login form cannot be found.
        """
        username = credentials.get("username", "")
        password = credentials.get("password", "")

        if not username and not password:
            raise AuthFormUnrecognizedError("Credentials dict contains no username or password")

        if selectors:
            username_sel = selectors.get("username_selector")
            password_sel = selectors.get("password_selector")
        else:
            username_sel = None
            password_sel = None

        # Resolve password selector via heuristic if not provided
        if not password_sel:
            password_sel = await self._find_element(page, _PASSWORD_SELECTOR)
            if not password_sel:
                raise AuthFormUnrecognizedError("Could not find password input on page")

        # Resolve username selector via heuristic if not provided
        if not username_sel:
            for candidate in _USERNAME_SELECTORS:
                username_sel = await self._find_element(page, candidate)
                if username_sel:
                    break
            if not username_sel:
                raise AuthFormUnrecognizedError("Could not find username/email input on page")

        # Fill fields — credential values never appear in any log statement
        await page.fill(username_sel, username)
        await page.fill(password_sel, password)

        logger.debug("Credentials injected into form fields")
        return True

    @staticmethod
    async def _find_element(page: Any, selector: str) -> str | None:
        """Return the selector string if a matching element exists, else None."""
        try:
            element = await page.query_selector(selector)
            return selector if element else None
        except Exception:
            return None
