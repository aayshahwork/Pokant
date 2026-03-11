"""Tests for shared/url_validator.py — SSRF prevention."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from shared.url_validator import (
    DNSPinningTransport,
    SSRFBlockedError,
    _is_private_ip,
    _resolve_and_validate,
    validate_url,
    validate_url_async,
    validate_webhook_url,
)


# ---------------------------------------------------------------------------
# _is_private_ip
# ---------------------------------------------------------------------------


class TestIsPrivateIp:
    def test_loopback_v4(self):
        assert _is_private_ip("127.0.0.1") is True

    def test_loopback_v6(self):
        assert _is_private_ip("::1") is True

    def test_rfc1918_10(self):
        assert _is_private_ip("10.0.0.1") is True

    def test_rfc1918_172(self):
        assert _is_private_ip("172.16.0.1") is True

    def test_rfc1918_192(self):
        assert _is_private_ip("192.168.1.1") is True

    def test_link_local(self):
        assert _is_private_ip("169.254.169.254") is True

    def test_fd00(self):
        assert _is_private_ip("fd00::1") is True

    def test_fe80(self):
        assert _is_private_ip("fe80::1") is True

    def test_public_ipv4(self):
        assert _is_private_ip("8.8.8.8") is False

    def test_public_ipv6(self):
        assert _is_private_ip("2001:4860:4860::8888") is False

    def test_invalid_ip_returns_false(self):
        assert _is_private_ip("not-an-ip") is False


# ---------------------------------------------------------------------------
# _resolve_and_validate
# ---------------------------------------------------------------------------


class TestResolveAndValidate:
    @patch("shared.url_validator.socket.getaddrinfo")
    def test_public_ip_passes(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
        ]
        ips = _resolve_and_validate("example.com")
        assert ips == ["93.184.216.34"]

    @patch("shared.url_validator.socket.getaddrinfo")
    def test_private_ip_rejected(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0)),
        ]
        with pytest.raises(SSRFBlockedError, match="private IP"):
            _resolve_and_validate("evil.com")

    @patch("shared.url_validator.socket.getaddrinfo")
    def test_multiple_ips_any_private_rejected(self, mock_dns):
        """If round-robin DNS returns [public, private], reject."""
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.1", 0)),
        ]
        with pytest.raises(SSRFBlockedError, match="private IP"):
            _resolve_and_validate("sneaky.com")

    @patch("shared.url_validator.socket.getaddrinfo")
    def test_gaierror_raises_ssrf_blocked(self, mock_dns):
        """Unresolvable hostname should raise SSRFBlockedError, not raw socket error."""
        mock_dns.side_effect = socket.gaierror("Name or service not known")
        with pytest.raises(SSRFBlockedError, match="could not be resolved"):
            _resolve_and_validate("nonexistent.invalid")

    @patch("shared.url_validator.socket.getaddrinfo")
    def test_empty_results_rejected(self, mock_dns):
        mock_dns.return_value = []
        with pytest.raises(SSRFBlockedError, match="no DNS records"):
            _resolve_and_validate("empty.invalid")

    @patch("shared.url_validator.socket.getaddrinfo")
    def test_deduplicates_ips(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
            (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0, 0, 0)),
        ]
        ips = _resolve_and_validate("example.com")
        assert ips == ["93.184.216.34"]


# ---------------------------------------------------------------------------
# validate_url
# ---------------------------------------------------------------------------


class TestValidateUrl:
    @patch("shared.url_validator.socket.getaddrinfo")
    def test_valid_public_url(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
        ]
        url, ip = validate_url("https://example.com/path")
        assert url == "https://example.com/path"
        assert ip == "93.184.216.34"

    @patch("shared.url_validator.socket.getaddrinfo")
    def test_localhost_rejected(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0)),
        ]
        with pytest.raises(SSRFBlockedError):
            validate_url("http://localhost/admin")

    @patch("shared.url_validator.socket.getaddrinfo")
    def test_dns_rebinding_private_ip(self, mock_dns):
        """Simulate DNS rebinding: domain resolves to private IP."""
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.1", 0)),
        ]
        with pytest.raises(SSRFBlockedError):
            validate_url("http://attacker-controlled.com/exfil")

    def test_ftp_scheme_rejected(self):
        with pytest.raises(SSRFBlockedError, match="scheme 'ftp' is not allowed"):
            validate_url("ftp://example.com/file")

    def test_empty_hostname_rejected(self):
        with pytest.raises(SSRFBlockedError, match="no hostname"):
            validate_url("http:///path")

    def test_no_scheme_rejected(self):
        with pytest.raises(SSRFBlockedError, match="scheme"):
            validate_url("example.com/path")


# ---------------------------------------------------------------------------
# validate_url_async
# ---------------------------------------------------------------------------


class TestValidateUrlAsync:
    @pytest.mark.asyncio
    @patch("shared.url_validator.socket.getaddrinfo")
    async def test_async_public_url(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
        ]
        url, ip = await validate_url_async("https://example.com")
        assert url == "https://example.com"
        assert ip == "93.184.216.34"

    @pytest.mark.asyncio
    @patch("shared.url_validator.socket.getaddrinfo")
    async def test_async_private_ip_rejected(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0)),
        ]
        with pytest.raises(SSRFBlockedError):
            await validate_url_async("https://internal.corp")


# ---------------------------------------------------------------------------
# validate_webhook_url
# ---------------------------------------------------------------------------


class TestValidateWebhookUrl:
    @pytest.mark.asyncio
    @patch("shared.url_validator.socket.getaddrinfo")
    async def test_valid_webhook_returns_url(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
        ]
        result = await validate_webhook_url("https://hooks.example.com/callback")
        assert result == "https://hooks.example.com/callback"

    @pytest.mark.asyncio
    @patch("shared.url_validator.socket.getaddrinfo")
    async def test_private_webhook_rejected(self, mock_dns):
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("172.16.0.1", 0)),
        ]
        with pytest.raises(SSRFBlockedError):
            await validate_webhook_url("https://internal.corp/webhook")


# ---------------------------------------------------------------------------
# SSRFBlockedError
# ---------------------------------------------------------------------------


class TestSSRFBlockedError:
    def test_inherits_computer_use_error(self):
        from shared.errors import ComputerUseError

        err = SSRFBlockedError("http://evil.com", "resolves to private IP 10.0.0.1")
        assert isinstance(err, ComputerUseError)

    def test_error_type_is_invalid_input(self):
        from shared.constants import ErrorCode

        err = SSRFBlockedError("http://evil.com", "resolves to private IP 10.0.0.1")
        assert err.error_type == ErrorCode.INVALID_INPUT

    def test_message_contains_url_and_reason(self):
        err = SSRFBlockedError("http://evil.com", "resolves to private IP 10.0.0.1")
        assert "evil.com" in str(err)
        assert "private IP" in str(err)


# ---------------------------------------------------------------------------
# DNSPinningTransport
# ---------------------------------------------------------------------------


class TestDNSPinningTransport:
    def test_creates_with_ssrf_safe_backend(self):
        transport = DNSPinningTransport()
        from shared.url_validator import _SSRFSafeBackend

        assert isinstance(transport._pool._network_backend, _SSRFSafeBackend)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    @patch("shared.url_validator.socket.getaddrinfo")
    async def test_private_ip_blocked(self, mock_dns):
        """The transport's backend should block connections to private IPs."""
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.1", 0)),
        ]
        transport = DNSPinningTransport()
        backend = transport._pool._network_backend  # type: ignore[attr-defined]
        with pytest.raises(SSRFBlockedError):
            await backend.connect_tcp("evil.com", 443)

    @pytest.mark.asyncio
    @patch("shared.url_validator.socket.getaddrinfo")
    async def test_public_ip_passes_validation(self, mock_dns):
        """The backend validates DNS successfully for public IPs.

        We only test the validation step — actual TCP connect would need a real server.
        """
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
        ]
        # Validation itself should not raise
        from shared.url_validator import _resolve_and_validate

        ips = _resolve_and_validate("example.com")
        assert ips == ["93.184.216.34"]
