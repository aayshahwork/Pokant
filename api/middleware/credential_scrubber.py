"""
api/middleware/credential_scrubber.py — structlog processor that strips sensitive keys.

Prevents credentials, passwords, API keys, and other secrets from leaking into
structured log output, even if a developer accidentally passes them to a logger.
"""

from __future__ import annotations

from typing import Any

_SCRUB_KEYS = frozenset({
    "credentials",
    "password",
    "secret",
    "cookies_encrypted",
    "api_key",
    "api_secret",
    "token",
    "authorization",
    "x-api-key",
})


def _scrub_value(value: Any) -> Any:
    """Recursively scrub sensitive keys from dicts and lists."""
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if k.lower() in _SCRUB_KEYS else _scrub_value(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(_scrub_value(item) for item in value)
    return value


class CredentialScrubber:
    """structlog processor that strips sensitive keys from log event dicts.

    Matches keys case-insensitively against _SCRUB_KEYS and replaces their
    values with "[REDACTED]".

    Usage in structlog.configure():
        structlog.configure(processors=[..., CredentialScrubber(), ...])
    """

    def __call__(self, logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        return _scrub_value(event_dict)
