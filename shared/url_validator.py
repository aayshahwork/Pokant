"""
shared/url_validator.py — SSRF prevention: URL validation and DNS pinning.

Validates that user-supplied URLs do not resolve to private/internal IP addresses.
Provides both sync (for Celery workers) and async (for FastAPI routes) variants.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpcore
import httpx

from shared.constants import ErrorCode
from shared.errors import ComputerUseError

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SSRFBlockedError(ComputerUseError):
    """Raised when a URL resolves to a private/internal IP address."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(
            message=f"URL blocked: {url} — {reason}",
            error_type=ErrorCode.INVALID_INPUT,
        )
        self.url = url
        self.reason = reason


# ---------------------------------------------------------------------------
# Private network definitions
# ---------------------------------------------------------------------------

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fd00::/8"),
    ipaddress.ip_network("fe80::/10"),
]


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address falls within any private/reserved network."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in network for network in _PRIVATE_NETWORKS)


def _resolve_and_validate(hostname: str) -> list[str]:
    """Resolve hostname via DNS and validate ALL returned IPs.

    Raises SSRFBlockedError if ANY resolved IP is private, or if the
    hostname cannot be resolved at all.

    Returns list of validated (public) IP strings.
    """
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise SSRFBlockedError(hostname, f"hostname '{hostname}' could not be resolved")

    if not results:
        raise SSRFBlockedError(hostname, f"hostname '{hostname}' returned no DNS records")

    ips: list[str] = []
    for family, _type, _proto, _canonname, sockaddr in results:
        ip_str = sockaddr[0]
        if ip_str not in ips:
            ips.append(ip_str)

    for ip_str in ips:
        if _is_private_ip(ip_str):
            raise SSRFBlockedError(hostname, f"resolves to private IP {ip_str}")

    return ips


def validate_url(url: str) -> tuple[str, str]:
    """Validate a URL for SSRF safety (sync version for Celery workers).

    Parses the URL, resolves DNS, and rejects private IPs.

    Returns:
        Tuple of (original_url, first_pinned_ip).

    Raises:
        SSRFBlockedError: If the URL resolves to a private IP or is invalid.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise SSRFBlockedError(url, f"scheme '{parsed.scheme}' is not allowed (only http/https)")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFBlockedError(url, "URL has no hostname")

    ips = _resolve_and_validate(hostname)
    return (url, ips[0])


async def validate_url_async(url: str) -> tuple[str, str]:
    """Validate a URL for SSRF safety (async version for FastAPI routes).

    Runs DNS resolution in a thread executor to avoid blocking the event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, validate_url, url)


async def validate_webhook_url(url: str) -> str:
    """Validate a webhook URL for SSRF safety. Returns the URL string."""
    validated_url, _ip = await validate_url_async(url)
    return validated_url


# ---------------------------------------------------------------------------
# DNS-pinning transport for httpx (defense-in-depth)
# ---------------------------------------------------------------------------


class _SSRFSafeBackend(httpcore.AsyncNetworkBackend):
    """Network backend that validates resolved IPs before TCP connect.

    Wraps httpcore's default backend, injecting DNS validation at the
    connection layer — before any TCP handshake occurs.
    """

    def __init__(self) -> None:
        # Import the default async backend (anyio-based)
        from httpcore._backends.auto import AutoBackend

        self._inner = AutoBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        """Validate DNS then delegate to the real backend."""
        _resolve_and_validate(str(host))
        return await self._inner.connect_tcp(
            host, port, timeout=timeout, local_address=local_address, socket_options=socket_options,
        )

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._inner.connect_unix_socket(path, timeout=timeout, socket_options=socket_options)

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class DNSPinningTransport(httpx.AsyncHTTPTransport):
    """httpx transport with SSRF-safe DNS validation at the network layer.

    Replaces the connection pool's network backend with _SSRFSafeBackend,
    which validates all resolved IPs before opening TCP connections.

    Usage:
        transport = DNSPinningTransport()
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.get("https://example.com")
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Replace the pool's network backend with our SSRF-safe version.
        # Accessing _pool is necessary because httpx.AsyncHTTPTransport
        # doesn't expose network_backend as a constructor parameter.
        # Pinned to httpx 0.27.x where this internal attribute is stable.
        self._pool._network_backend = _SSRFSafeBackend()  # type: ignore[attr-defined]
