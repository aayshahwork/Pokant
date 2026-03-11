"""
tests/unit/test_captcha_solver.py — Tests for CaptchaSolver detection and solving.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workers.captcha_solver import CaptchaResult, CaptchaSolver


@pytest.fixture
def solver():
    return CaptchaSolver(twocaptcha_api_key="test-api-key")


@pytest.fixture
def solver_no_key():
    return CaptchaSolver(twocaptcha_api_key="")


def _mock_page(captcha_type: str | None = None):
    """Create a mock Playwright page with optional CAPTCHA element."""
    page = AsyncMock()
    page.url = "https://example.com/login"

    async def query_selector(selector):
        if captcha_type == "recaptcha_v2" and ("g-recaptcha" in selector or "recaptcha" in selector):
            return MagicMock()
        if captcha_type == "hcaptcha" and ("h-captcha" in selector or "hcaptcha" in selector):
            return MagicMock()
        if captcha_type == "turnstile" and ("cf-turnstile" in selector or "challenges.cloudflare" in selector):
            return MagicMock()
        return None

    page.query_selector = AsyncMock(side_effect=query_selector)
    return page


class TestDetectCaptcha:
    @pytest.mark.asyncio
    async def test_detect_recaptcha(self, solver):
        page = _mock_page("recaptcha_v2")
        result = await solver.detect_captcha(page)
        assert result == "recaptcha_v2"

    @pytest.mark.asyncio
    async def test_detect_hcaptcha(self, solver):
        page = _mock_page("hcaptcha")
        result = await solver.detect_captcha(page)
        assert result == "hcaptcha"

    @pytest.mark.asyncio
    async def test_detect_turnstile(self, solver):
        page = _mock_page("turnstile")
        result = await solver.detect_captcha(page)
        assert result == "turnstile"

    @pytest.mark.asyncio
    async def test_detect_no_captcha(self, solver):
        page = _mock_page(None)
        result = await solver.detect_captcha(page)
        assert result is None


class TestSolveDispatch:
    @pytest.mark.asyncio
    async def test_solve_no_captcha_detected(self, solver):
        page = _mock_page(None)
        result = await solver.solve(page)
        assert not result.solved
        assert result.error == "no_captcha_detected"

    @pytest.mark.asyncio
    async def test_solve_unsupported_type(self, solver):
        page = _mock_page(None)
        result = await solver.solve(page, captcha_type="unknown_type")
        assert not result.solved
        assert "unsupported_type" in result.error

    @pytest.mark.asyncio
    async def test_solve_recaptcha_no_api_key(self, solver_no_key):
        page = _mock_page("recaptcha_v2")
        result = await solver_no_key.solve(page, captcha_type="recaptcha_v2")
        assert not result.solved
        assert result.error == "no_api_key"

    @pytest.mark.asyncio
    async def test_solve_hcaptcha_no_api_key(self, solver_no_key):
        page = _mock_page("hcaptcha")
        result = await solver_no_key.solve(page, captcha_type="hcaptcha")
        assert not result.solved
        assert result.error == "no_api_key"


class TestSolveRecaptchaV2:
    @pytest.mark.asyncio
    async def test_sitekey_not_found(self, solver):
        page = _mock_page("recaptcha_v2")
        page.evaluate = AsyncMock(return_value=None)
        result = await solver._solve_recaptcha_v2(page)
        assert not result.solved
        assert result.error == "sitekey_not_found"

    @pytest.mark.asyncio
    async def test_submit_failure(self, solver):
        page = _mock_page("recaptcha_v2")
        page.evaluate = AsyncMock(return_value="6LcTestSiteKey")
        page.url = "https://example.com"

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"status": 0, "request": "ERROR_WRONG_USER_KEY"})

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("workers.captcha_solver.aiohttp.ClientSession", return_value=mock_session):
            result = await solver._solve_recaptcha_v2(page)

        assert not result.solved
        assert result.error == "ERROR_WRONG_USER_KEY"

    @pytest.mark.asyncio
    async def test_successful_solve(self, solver):
        page = _mock_page("recaptcha_v2")
        page.evaluate = AsyncMock(return_value="6LcTestSiteKey")
        page.url = "https://example.com"

        submit_response = AsyncMock()
        submit_response.json = AsyncMock(return_value={"status": 1, "request": "12345"})

        poll_response = AsyncMock()
        poll_response.json = AsyncMock(return_value={"status": 1, "request": "03AGdBq24test-token"})

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=submit_response),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=poll_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("workers.captcha_solver.aiohttp.ClientSession", return_value=mock_session):
            result = await solver._solve_recaptcha_v2(page)

        assert result.solved
        assert result.token == "03AGdBq24test-token"
        assert result.captcha_type == "recaptcha_v2"
        assert result.duration_ms > 0


class TestSolveTurnstile:
    @pytest.mark.asyncio
    async def test_turnstile_iframe_not_found(self, solver):
        page = AsyncMock()
        page.query_selector = AsyncMock(return_value=None)
        result = await solver._solve_turnstile(page)
        assert not result.solved
        assert result.error == "turnstile_iframe_not_found"

    @pytest.mark.asyncio
    async def test_turnstile_successful_click(self, solver):
        page = AsyncMock()
        iframe_el = MagicMock()
        iframe_el.bounding_box = AsyncMock(return_value={"x": 100, "y": 200, "width": 50, "height": 30})

        # First query finds iframe, second returns None (for fallback)
        page.query_selector = AsyncMock(side_effect=[iframe_el, None])
        page.mouse = AsyncMock()
        page.mouse.click = AsyncMock()

        # First evaluate returns token immediately
        page.evaluate = AsyncMock(return_value="turnstile-token-123")

        result = await solver._solve_turnstile(page)
        assert result.solved
        assert result.token == "turnstile-token-123"
        assert result.captcha_type == "turnstile"
