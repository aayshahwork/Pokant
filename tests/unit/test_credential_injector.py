"""Tests for workers/credential_injector.py."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from workers.credential_injector import AuthFormUnrecognizedError, CredentialInjector


@pytest.fixture
def injector():
    return CredentialInjector()


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.fill = AsyncMock()
    # By default, query_selector finds an element
    page.query_selector = AsyncMock(return_value=MagicMock())
    return page


# ---------------------------------------------------------------------------
# Injection with explicit selectors
# ---------------------------------------------------------------------------


class TestInjectWithSelectors:
    @pytest.mark.asyncio
    async def test_fills_with_given_selectors(self, injector, mock_page):
        result = await injector.inject(
            mock_page,
            {"username": "alice", "password": "s3cret"},
            selectors={"username_selector": "#user", "password_selector": "#pass"},
        )
        assert result is True
        mock_page.fill.assert_any_call("#user", "alice")
        mock_page.fill.assert_any_call("#pass", "s3cret")

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, injector, mock_page):
        result = await injector.inject(
            mock_page,
            {"username": "u", "password": "p"},
            selectors={"username_selector": "#u", "password_selector": "#p"},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_no_query_selector_called_with_explicit_selectors(self, injector, mock_page):
        """When selectors are provided, heuristic detection is skipped."""
        await injector.inject(
            mock_page,
            {"username": "u", "password": "p"},
            selectors={"username_selector": "#u", "password_selector": "#p"},
        )
        mock_page.query_selector.assert_not_called()


# ---------------------------------------------------------------------------
# Injection with heuristic detection
# ---------------------------------------------------------------------------


class TestInjectWithHeuristic:
    @pytest.mark.asyncio
    async def test_finds_password_and_email_inputs(self, injector, mock_page):
        """Heuristic finds password + first matching username selector."""
        await injector.inject(mock_page, {"username": "alice", "password": "s3cret"})

        # query_selector called for password, then for username candidates
        assert mock_page.query_selector.call_count >= 2
        mock_page.fill.assert_any_call('input[type="password"]', "s3cret")

    @pytest.mark.asyncio
    async def test_no_password_field_raises(self, injector, mock_page):
        """No password input on page → AuthFormUnrecognizedError."""
        mock_page.query_selector = AsyncMock(return_value=None)

        with pytest.raises(AuthFormUnrecognizedError, match="password input"):
            await injector.inject(mock_page, {"username": "u", "password": "p"})

    @pytest.mark.asyncio
    async def test_no_username_field_raises(self, injector, mock_page):
        """Password found but no username candidate → AuthFormUnrecognizedError."""
        call_count = 0

        async def selective_query(selector):
            nonlocal call_count
            call_count += 1
            # First call (password) succeeds, all subsequent (username candidates) fail
            if call_count == 1:
                return MagicMock()
            return None

        mock_page.query_selector = selective_query

        with pytest.raises(AuthFormUnrecognizedError, match="username"):
            await injector.inject(mock_page, {"username": "u", "password": "p"})

    @pytest.mark.asyncio
    async def test_heuristic_prefers_email_over_text(self, injector, mock_page):
        """When multiple username candidates exist, email input is tried first."""
        calls = []

        async def tracking_query(selector):
            calls.append(selector)
            return MagicMock()

        mock_page.query_selector = tracking_query

        await injector.inject(mock_page, {"username": "u", "password": "p"})

        # After password selector, first username candidate should be email
        username_calls = [c for c in calls if c != 'input[type="password"]']
        assert username_calls[0] == 'input[type="email"]'


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestInjectErrors:
    @pytest.mark.asyncio
    async def test_empty_credentials_raises(self, injector, mock_page):
        with pytest.raises(AuthFormUnrecognizedError, match="no username or password"):
            await injector.inject(mock_page, {})

    @pytest.mark.asyncio
    async def test_empty_string_credentials_raises(self, injector, mock_page):
        with pytest.raises(AuthFormUnrecognizedError, match="no username or password"):
            await injector.inject(mock_page, {"username": "", "password": ""})


# ---------------------------------------------------------------------------
# Security: credentials never in logs
# ---------------------------------------------------------------------------


class TestCredentialSecurity:
    @pytest.mark.asyncio
    async def test_credentials_not_in_log_output(self, injector, mock_page, caplog):
        with caplog.at_level(logging.DEBUG, logger="workers.credential_injector"):
            await injector.inject(
                mock_page,
                {"username": "alice_secret_user", "password": "hunter2_secret_pass"},
                selectors={"username_selector": "#u", "password_selector": "#p"},
            )

        for record in caplog.records:
            msg = record.getMessage()
            assert "alice_secret_user" not in msg
            assert "hunter2_secret_pass" not in msg


# ---------------------------------------------------------------------------
# AuthFormUnrecognizedError
# ---------------------------------------------------------------------------


class TestAuthFormUnrecognizedError:
    def test_is_exception_subclass(self):
        assert issubclass(AuthFormUnrecognizedError, Exception)

    def test_message_preserved(self):
        err = AuthFormUnrecognizedError("custom message")
        assert str(err) == "custom message"
